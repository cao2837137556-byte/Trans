"""Fixed endpoint evaluation, tie-aware pooled ranking and full risk tables."""
import csv
import gzip
import json
import math
from collections import defaultdict
from fractions import Fraction
import numpy as np
import torch
import issue27frontend_abstart_support_v1 as s
import issue27frontend_abstart_model_v1 as m
from issue27frontend_abstart_train_v1 import load_contexts


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


def infer(model, contexts, budget, phase, source=None, observer=None):
    result = {}; handles = {}
    try:
        with torch.inference_mode():
            for start in range(0,len(contexts),32):
                batch = contexts[start:start+32]; sequences = []
                for c in batch:
                    if source is None:
                        sequences.append(c['x']); continue
                    member = c['member_id']
                    if member not in handles:
                        handles[member] = (source/'members'/member/'features.f32le').open('rb')
                    f = handles[member]; f.seek(c['offset']); raw = f.read(c['length']*524)
                    s.require(len(raw) == c['length']*524, 'EXPANDED_SHORT_FEATURES')
                    for t in c['targets']:
                        s.require(s.prefix(raw,t['event']) == t['feature_prefix_sha256'], 'EXPANDED_PREFIX')
                    sequences.append(torch.from_numpy(np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)))
                    budget.access['feature_bytes_decoded'] += len(raw)
                if observer is None:
                    qs = model(sequences,[c['key'] for c in batch])
                else:
                    qs,hs = model(sequences,[c['key'] for c in batch],with_hidden=True)
                    observer(batch,qs,hs)
                budget.access['student_forwards'] += 1
                for c,q in zip(batch,qs):
                    for t in c['targets']:
                        s.require(t['uid'] not in result and math.isfinite(float(q[t['event']])), 'PREDICTION_IDENTITY')
                        result[t['uid']] = float(q[t['event']]); budget.access['evaluated_targets'] += 1
                budget.check(phase=phase,targets_complete=budget.access['evaluated_targets'],targets_total=560632)
    finally:
        for f in handles.values():
            f.close()
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


def guard_audit(contexts,guard,r,predictions,budget):
    groups,scale = guard; a = {c['key']:c for c in contexts if c['targets'][0]['owner'] == 'A'}
    seen = set(); counts = defaultdict(lambda:dict(pairs=0,violations=0,worst_gap_minus_margin=None))
    for epoch in range(1,r['schedule']['epochs']+1):
        for ks in s.buckets(s.order(a,epoch,'A'),r['schedule']['steps_per_epoch']):
            for left,right,margin in s.guard_pairs([a[k] for k in ks],groups,epoch,scale):
                pair = (left['uid'],right['uid'])
                if pair in seen:
                    continue
                seen.add(pair)
                gap = (predictions[pair[0]]-predictions[pair[1]])/scale-margin
                family = left.get('attack_family','unknown')
                for key in ('ALL',family):
                    c = counts[key]; c['pairs'] += 1; c['violations'] += int(gap < 0)
                    c['worst_gap_minus_margin'] = gap if c['worst_gap_minus_margin'] is None else min(c['worst_gap_minus_margin'],gap)
            budget.check(phase='FINAL_TRAIN_PAIR_AUDIT')
    s.require(len(seen) == r['losses']['A_guard']['unique_pairs'], 'FINAL_PAIR_UNION')
    return dict(counts)


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


class EndpointObservation:
    def __init__(self,cache,projection,r):
        self.cache,self.projection,self.r=cache,projection,r
        self.q_loss=self.r_loss=0.
        self.sums=defaultdict(float)

    def __call__(self,batch,qs,hs):
        qloss,rloss,stats=m.teacher_terms(batch,qs,hs,self.projection,self.cache,
            {y:self.r['teacher_cache']['expected_N_T'+str(y)] for y in (0,1)},1)
        self.q_loss+=float(qloss);self.r_loss+=float(rloss)
        for k,v in stats.items():self.sums[k]+=v

    def finish(self,out,arm,r):
        n=self.sums['teacher_targets']
        s.require(n==r['teacher_cache']['expected_targets'],'ENDPOINT_TEACHER_COVERAGE')
        s.atomic_json(out/(arm+'_train_transfer_fit.json'),dict(targets=int(n),
            task_score_loss=self.q_loss,residual_loss=self.r_loss,
            raw_logit_MAE=self.sums['raw_error_abs_sum']/n,
            normalized_MAE=self.sums['normalized_error_abs_sum']/n,
            teacher_hard_agreement=self.sums['task_hard_agree']/n,
            unweighted_residual_huber=self.sums['residual_huber_sum']/n,
            extra_student_forwards=0,scientific_success=False))


def evaluate(r,out,budget):
    train_dir = s.OUTPUTS['T']; s.manifest(train_dir,check=budget.check)
    s.require(s.read_json(train_dir/'supervisor_terminal.json')['status'] == 'COMPLETE', 'T_NOT_COMPLETE')
    barrier = s.read_json(train_dir/'candidates_sealed.json')
    s.require(barrier['status'] == 'BOTH_FINAL_CANDIDATES_SEALED' and barrier['recipe_sha256'] == s.RECIPE_SHA, 'ALL_FINAL_BARRIER')
    s.require(set(barrier['candidates'])=={'C0_AB','R_AB'},'FINAL_ARM_SET')
    plan = s.read_json(s.pin(r['inputs']['plan'],budget.check))
    original = s.train_metadata(plan,r)
    from issue27frontend_abstart_reuse_v1 import load_guard, load_prepared
    guard = load_guard(original,r,budget)
    cache = load_prepared(original,r,budget)
    prepared = load_contexts(plan['contexts'],s.pin(r['inputs']['train_check_features'],budget.check),budget)
    baseline,expanded,source = expanded_inputs(r,budget)
    check_reference = s.read_json(s.pin(r['inputs']['historical_check_scores'],budget.check))['A']
    check_A = {t['uid']:t['hard'] for t in check_reference if t['owner'] == 'A'}
    models = {}; expanded_predictions = {}; details = {}; verification = {}
    for arm in ('C0_AB','R_AB'):
        budget.check(True,phase='LOADING_FINAL',arm=arm)
        path = train_dir/(arm+'.pt'); receipt = barrier['candidates'][arm]
        s.require(s.sha(path,budget.check) == receipt['file_sha256'], 'FINAL_FILE_SHA')
        model = m.Student(); model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True); model.eval()
        budget.access['new_candidate_loads'] += 1
        before = m.state_hash(model); s.require(before == receipt['state_sha256'], 'FINAL_STATE_SHA')
        projection = None
        if arm=='R_AB':
            dp=train_dir/'R_AB_projection_training_only.pt'
            s.require(s.sha(dp,budget.check)==receipt['projection_file_sha256'],'R_PROJECTION_SHA')
            projection=m.Projection();projection.load_state_dict(torch.load(dp,map_location='cpu',weights_only=True),strict=True);projection.eval()
            budget.access['new_projection_loads']=budget.access.get('new_projection_loads',0)+1
        observation = EndpointObservation(cache,projection,r)
        preds = {}
        for role in ('train','check'):
            cs = [c for c in prepared if c['role'] == role]
            preds[role] = infer(model,cs,budget,role.upper()+'_EVALUATION',observer=observation if role=='train' else None)
            save_predictions(out/(arm+'_'+role+'.csv.gz'),preds[role])
            s.require(read_predictions(out/(arm+'_'+role+'.csv.gz'),preds[role]) == preds[role], 'PREDICTION_ROUNDTRIP')
        observation.finish(out,arm,r)
        q = infer(model,expanded,budget,'EXPANDED_EVALUATION',source)
        save_predictions(out/(arm+'_expanded.csv.gz'),q)
        s.require(read_predictions(out/(arm+'_expanded.csv.gz'),q) == q, 'EXPANDED_PREDICTION_ROUNDTRIP')
        expanded_predictions[arm] = q
        hard = {k:int(v >= 0) for k,v in preds['check'].items()}
        ca = [t for t in s.targets(prepared) if t['new_role'] == 'check' and t['owner'] == 'A']
        ids = [t for t in s.targets(prepared) if t['new_role'] == 'check' and t['uid'].startswith('id_calib:')]
        s.require(len(ca) == r['evaluation']['new_candidate_retention_diagnostics']['targets'] and len(ids) == r['data']['ID_check_targets'], 'CHECK_DIAGNOSTIC_COUNTS')
        details[arm] = dict(check=fixed([t for t in s.targets(prepared) if t['new_role'] == 'check'],hard),
            train=fixed(s.targets(original),{k:int(v >= 0) for k,v in preds['train'].items()}),
            ID_check=fixed(ids,hard),retention_old_P2=flips(ca,{t['uid']:t['old_hard'] for t in ca},hard),
            retention_fixed_A=flips(ca,check_A,hard),final_train_guard=guard_audit(original,guard,r,preds['train'],budget))
        s.require(m.state_hash(model) == before, 'INFERENCE_MUTATED_STATE')
        verification[arm] = dict(state_unchanged=True,prediction_roundtrip=True,targets=sum(map(len,preds.values()))+len(q))
        del model,projection
    s.require(budget.access['evaluated_targets'] == r['evaluation']['targets_all_arms'], 'E_TARGET_BUDGET')
    all_q = dict(expanded_predictions,A={t['uid']:t['a_logit'] for t in baseline},AB={t['uid']:t['ab_logit'] for t in baseline})
    for key,names in [('transfer_E',('C0','C1','C2')),('aligned_E',('Q','R'))]:
        archive=s.pin(r['historical_reference_seals'][key],budget.check)
        entries=s.manifest(archive.parent,r['historical_reference_seals'][key]['sha256'],budget.check)
        for name in names:
            s.require(name not in all_q,'REFERENCE_NAME_COLLISION')
            path=archive.parent/(name+'_expanded.csv.gz')
            s.require(s.sha(path,budget.check)==entries[path.name],'HISTORICAL_SCORE_PIN')
            all_q[name]=read_predictions(path,[t['uid'] for t in baseline])
    for name,q in all_q.items():
        budget.check(phase='ENDPOINT_METRICS',arm=name)
        models[name] = dict(fixed=fixed(baseline,{k:int(v >= 0) for k,v in q.items()}),ranking=ranking(baseline,q))
    old = {t['uid']:t['old_hard'] for t in baseline}
    models['old_P2'] = dict(fixed=fixed(baseline,old),ranking=None)
    s.require(models['old_P2']['fixed']['overall']['detected'] == r['evaluation']['old_attack_reference_exact']['detected'], 'OLD_ATTACK_REFERENCE')
    s.require(models['old_P2']['fixed']['future']['detected'] == r['evaluation']['old_future_reference_exact']['detected'], 'OLD_FUTURE_REFERENCE')
    contrasts = {name:contrast(models[name.split('-')[1]],models[name.split('-')[0]]) for name in r['evaluation']['contrasts']}
    for a in ('C0_AB','R_AB'):
        qh = {k:int(v >= 0) for k,v in all_q[a].items()}
        references = ['old_P2','A','AB','C0','C1','C2','Q','R']+(['C0_AB'] if a=='R_AB' else [])
        for b in references:
            bh = old if b == 'old_P2' else {k:int(v >= 0) for k,v in all_q[b].items()}
            with gzip.open(out/(a+'_vs_'+b+'_flips.json.gz'),'wt',encoding='utf-8') as f:
                json.dump(flips(baseline,bh,qh),f,ensure_ascii=False,allow_nan=False)
    tails = {name:tail_composition(baseline,q,models[name]['ranking']) for name,q in all_q.items()}
    ab_tail = {arm:compare_ab_tail(models[arm],models['AB']) for arm in ('C0_AB','R_AB')}
    result = dict(tail_composition=tails,AB_tail_comparison=ab_tail,models=models,contrasts=contrasts,check_and_train=details,verification=verification,
                  evidence='EXPOSED_DEVELOPMENT_ONLY',original_strict_verdict='HISTORICAL_FAIL_UNCHANGED',
                  practical_success='MANUAL_SCIENTIFIC_REVIEW_REQUIRED',commissioning='NOT_EVALUATED')
    s.atomic_json(out/'comparison.json',result)
    lines = ['# AB 起点对照：终点结果','', '开发证据；原严格继承失败记录保持，新设备入网尚未评估。','',
             '| 模型 | 攻击召回 | future召回 | OOD池均误报 | 最差池误报 | 合并TPR@1%FPR | TPR@0.1%FPR |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name in ('old_P2','A','AB','C0','C1','C2','Q','R','C0_AB','R_AB'):
        v=models[name]; f=v['fixed']; rank='—' if v['ranking'] is None else '%.4f%%'%(100*v['ranking']['points']['0.01']['tpr'])
        low='—' if v['ranking'] is None else '%.4f%%'%(100*v['ranking']['points']['0.001']['tpr'])
        lines.append('| %s | %.4f%% | %.4f%% | %.4f%% | %.4f%% | %s | %s |'%(name,100*f['overall']['recall'],100*f['future']['recall'],100*f['benign_pool_macro_fpr'],100*f['worst_pool_fpr'],rank,low))
    lines += ['', '完整分族、各正常池、A/B、ID及翻转见 comparison.json 和 flips 文件。',
              '1%为合并正常OOD描述点，ID另报；实用目标须结合完整风险表，不自动宣布继承成功。',
              'AB起点此前额外40轮B监督；新增训练预算相同不等于累计数据暴露相同。']
    (out/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(targets=budget.access['evaluated_targets'],candidates=list(verification),status='EVALUATION_COMPLETE')
