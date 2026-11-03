"""Pinned endpoint metric semantics, reused without historical model execution."""

import csv, gzip, json, math

from collections import defaultdict

from fractions import Fraction

import numpy as np

import issue27dualview_support_v1 as s

def ranking(rows, logits):
    labels = np.array([t['label'] for t in rows],dtype=np.int64)
    scores = np.array([logits[t['uid']] for t in rows],dtype=np.float64)
    s.require(np.isfinite(scores).all() and set(labels) == {0,1}, 'RANKING_INPUT')
    order = np.argsort(-scores,kind='stable'); q,y = scores[order],labels[order]
    ends = np.r_[np.flatnonzero(q[1:] != q[:-1]),len(q)-1]
    tp = np.cumsum(y)[ends]; fp = np.cumsum(1-y)[ends]
    p,n = int(labels.sum()),int((1-labels).sum())
    x = np.r_[0.,fp/n]; z = np.r_[0.,tp/p]
    auc = float(np.sum(np.diff(x)*(z[1:]+z[:-1])*.5))
    points = {}
    for cap,denominator in [('0.01',100),('0.001',1000)]:
        valid = np.flatnonzero(fp*denominator <= n)
        if len(valid):
            i = int(valid[-1]); threshold = float(q[ends[i]])
            detected, alarms = int(tp[i]),int(fp[i])
        else:
            threshold = None; detected = alarms = 0
        families = defaultdict(lambda:[0,0])
        for t in rows:
            if t['label']:
                g = families[t['attack_family']]; g[1] += 1
                g[0] += int(threshold is not None and logits[t['uid']] >= threshold)
        points[cap] = dict(threshold=threshold,threshold_semantics='>=; null means predict no attacks',
                          detected=detected,attacks=p,false_alarms=alarms,benign=n,tpr=detected/p,fpr=alarms/n,
                          family_recall={k:dict(detected=v[0],targets=v[1],recall=v[0]/v[1]) for k,v in sorted(families.items())})
    return dict(auroc=auc,points=points,threshold_deployable=False)

def fixed(rows, predictions):
    def count(ts):
        p = sum(t['label'] for t in ts); n = len(ts)-p
        tp = sum(t['label'] == 1 and predictions[t['uid']] for t in ts)
        fp = sum(t['label'] == 0 and predictions[t['uid']] for t in ts)
        return dict(targets=len(ts),attacks=p,benign=n,detected=tp,false_alarms=fp,recall=tp/p if p else None,fpr=fp/n if n else None)
    grouped = defaultdict(list)
    for t in rows:
        if t['label']:
            grouped[('attack_family',t['attack_family'])].append(t)
        else:
            grouped[('pool',t.get('pool','non-expanded'))].append(t)
        owner = t.get('owner') or ('B' if t['old_missing'] else 'A')
        for dimension,key in [('owner',owner),('source_group',t['source_group']),('device_family',t['device_family'])]:
            grouped[(dimension,key)].append(t)
    groups = {d:{} for d in ('attack_family','pool','owner','source_group','device_family')}
    for (d,k),ts in sorted(grouped.items()):
        groups[d][k] = count(ts)
    recalls = [v['recall'] for v in groups['attack_family'].values()]
    fprs = [v['fpr'] for v in groups['pool'].values()]
    future = [t for t in rows if t.get('role') == 'future_query']
    return dict(overall=count(rows),future=count(future),groups=groups,
                family_macro_recall=float(np.mean(recalls)) if recalls else None,
                benign_pool_macro_fpr=float(np.mean(fprs)) if fprs else None,
                worst_pool_fpr=max(fprs) if fprs else None)

def flips(rows, old, new):
    bad = [t['uid'] for t in rows if old[t['uid']] == t['label'] and new[t['uid']] != t['label']]
    good = [t['uid'] for t in rows if old[t['uid']] != t['label'] and new[t['uid']] == t['label']]
    return dict(negative=len(bad),positive=len(good),negative_uids=bad,positive_uids=good,is_zero_regression=not bad)

def contrast(old, new):
    a,b = old['fixed'],new['fixed']
    deltas = {
        'pooled_TPR_at_1pct':new['ranking']['points']['0.01']['tpr']-old['ranking']['points']['0.01']['tpr'],
        'attack_recall':b['overall']['recall']-a['overall']['recall'],
        'future_recall':b['future']['recall']-a['future']['recall'],
        'family_macro_recall':b['family_macro_recall']-a['family_macro_recall'],
        'benign_pool_macro_fpr':b['benign_pool_macro_fpr']-a['benign_pool_macro_fpr'],
        'worst_pool_fpr':b['worst_pool_fpr']-a['worst_pool_fpr']}
    def exact(v):
        f = v['fixed']
        ratio = lambda c,n,d: Fraction(c[n],c[d])
        family = list(f['groups']['attack_family'].values())
        pools = list(f['groups']['pool'].values())
        return [ratio(v['ranking']['points']['0.01'],'detected','attacks'),
                ratio(f['overall'],'detected','attacks'), ratio(f['future'],'detected','attacks'),
                sum((ratio(c,'detected','attacks') for c in family),Fraction())/len(family),
                -sum((ratio(c,'false_alarms','benign') for c in pools),Fraction())/len(pools),
                -max(ratio(c,'false_alarms','benign') for c in pools)]
    desired = [y-x for x,y in zip(exact(old),exact(new))]
    status = 'DEVELOPMENT_DIRECTIONAL_JOINT_GAIN' if all(v >= 0 for v in desired) and any(v > 0 for v in desired) else (
             'NO_CHANGE' if all(v == 0 for v in desired) else ('TRADEOFF' if any(v > 0 for v in desired) else 'NO_JOINT_GAIN'))
    families = {k:b['groups']['attack_family'][k]['recall']-v['recall'] for k,v in a['groups']['attack_family'].items()}
    pools = {k:b['groups']['pool'][k]['fpr']-v['fpr'] for k,v in a['groups']['pool'].items()}
    return dict(status=status,deltas=deltas,exact_desired_deltas=[str(v) for v in desired],
                family_recall_deltas=families,pool_fpr_deltas=pools,
                worst_family_recall_delta=min(families.values()),practical_success='MANUAL_SCIENTIFIC_REVIEW_REQUIRED',
                limit='single seed, exposed development; small positive differences are not a breakthrough')

def compare_ab_tail(candidate, reference):
    result = {}
    for cap in ('0.01','0.001'):
        c,b = candidate['ranking']['points'][cap],reference['ranking']['points'][cap]
        delta = Fraction(c['detected'],c['attacks'])-Fraction(b['detected'],b['attacks'])
        result[cap] = dict(relation='LESS' if delta<0 else 'GREATER' if delta>0 else 'EQUAL',
                           exact_tpr_delta=str(delta),diagnostic_only=True)
    return result

def tail_composition(rows, scores, rank):
    result = {}
    for cap, point in rank['points'].items():
        threshold = point['threshold']
        selected = [t for t in rows if t['label']==0 and threshold is not None and scores[t['uid']]>=threshold]
        s.require(len(selected)==point['false_alarms'],'TAIL_FP_COUNTS')
        groups = {}
        for field in ('pool','source_group','event_index'):
            counts = defaultdict(int)
            for t in selected: counts[str(t[field])] += 1
            groups[field] = dict(sorted(counts.items()))
        result[cap] = dict(false_alarms=len(selected),groups=groups,threshold_deployable=False)
    return result

def read_baseline(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
        rows = list(csv.DictReader(f))
    for t in rows:
        for k in ('label','old_hard','old_missing','a_hard','ab_hard','event_index'):
            t[k] = int(t[k])
        for k in ('a_logit','ab_logit'):
            t[k] = float(t[k]); s.require(math.isfinite(t[k]), 'REFERENCE_NONFINITE')
        s.require(t['a_hard'] == int(t['a_logit'] >= 0) and t['ab_hard'] == int(t['ab_logit'] >= 0), 'REFERENCE_HARD')
    s.require(len(rows) == len({t['uid'] for t in rows}), 'REFERENCE_UIDS')
    return rows

def expanded_inputs(r,budget):
    src = s.ROOT / r['inputs']['expanded_manifest']['path']; src = src.parent
    s.manifest(src,r['inputs']['expanded_manifest']['sha256'],budget.check)
    prep = s.read_json(s.pin(r['inputs']['expanded_preparation'],budget.check))
    s.pin(r['inputs']['expanded_AB_P2_predictions'],budget.check)
    rows = read_baseline(s.pin(r['inputs']['expanded_A_predictions'],budget.check))
    s.require(len(rows) == r['data']['expanded']['targets'], 'EXPANDED_TARGETS')
    lookup = {t['uid']:t for t in rows}; contexts = []
    for rec in prep['members']:
        member = rec['member_id']; offset = 0
        with gzip.open(src/'members'/member/'contexts.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                c = json.loads(line)
                s.require(c['offset'] == offset and 1 <= c['length'] <= 256, 'EXPANDED_LAYOUT')
                for t in c['targets']:
                    old = lookup[t['uid']]
                    s.require(old['context_key'] == c['key'] and old['member_id'] == member and old['event_index'] == t['event']
                              and old['feature_prefix_sha256'] == t['feature_prefix_sha256'], 'EXPANDED_JOIN')
                c['member_id'] = member; contexts.append(c); offset += c['length']*524
        s.require(offset == rec['feature_bytes'], 'EXPANDED_MEMBER_BYTES')
    s.require(len(contexts) == len({c['key'] for c in contexts}) == r['data']['expanded']['contexts'], 'EXPANDED_CONTEXTS')
    ts = s.targets(contexts)
    s.require(len(ts) == len({t['uid'] for t in ts}) == len(rows) and {t['uid'] for t in ts} == set(lookup), 'EXPANDED_TARGET_JOIN')
    return rows,sorted(contexts,key=lambda c:c['key']),src

def save_predictions(path, predictions):
    with gzip.open(path,'wt',encoding='utf-8',newline='') as f:
        writer = csv.writer(f,lineterminator='\n'); writer.writerow(['uid','logit','hard'])
        for uid,q in sorted(predictions.items()):
            writer.writerow([uid,repr(q),int(q >= 0)])

def read_predictions(path, expected):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
        rows = list(csv.DictReader(f))
    s.require(len(rows) == len(expected) and {t['uid'] for t in rows} == set(expected), 'OUTPUT_UIDS')
    result = {t['uid']:float(t['logit']) for t in rows}
    s.require(all(math.isfinite(result[t['uid']]) and int(t['hard']) == int(result[t['uid']] >= 0) for t in rows), 'OUTPUT_LOGITS')
    return result

def check_details(r,prepared,preds,check_A):
    rows = s.targets(prepared)
    hard = {k:int(v>=0) for k,v in preds['check'].items()}
    ca = [t for t in rows if t['new_role']=='check' and t['owner']=='A']
    ids = [t for t in rows if t['new_role']=='check' and t['uid'].startswith('id_calib:')]
    spec = r['evaluation']['new_candidate_retention_diagnostics']
    s.require(len(ca)==spec.get('targets',2127) and sum(t['label'] for t in ca)==spec.get('attacks',825)
              and len(ids)==r['data']['ID_check_targets'] and not any(t['label'] for t in ids), 'CHECK_DIAGNOSTIC_COUNTS')
    s.require(set(check_A)=={t['uid'] for t in ca},'COMMON_A_CHECK_UIDS')
    return dict(check=fixed([t for t in rows if t['new_role']=='check'],hard),
                train=fixed([t for t in rows if t['new_role']=='train'],{k:int(v>=0) for k,v in preds['train'].items()}),
                ID_check=fixed(ids,hard),retention_old_P2=flips(ca,{t['uid']:t['old_hard'] for t in ca},hard),
                retention_fixed_A=flips(ca,check_A,hard))

def model_metrics(baseline,all_q,budget):
    models = {}
    for name,q in all_q.items():
        budget.check(phase='ENDPOINT_METRICS',arm=name)
        models[name] = dict(fixed=fixed(baseline,{k:int(v>=0) for k,v in q.items()}),ranking=ranking(baseline,q))
    models['old_P2'] = dict(fixed=fixed(baseline,{t['uid']:t['old_hard'] for t in baseline}),ranking=None)
    return models
