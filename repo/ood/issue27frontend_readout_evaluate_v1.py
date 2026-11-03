"""Fixed endpoint evaluation, tie-aware pooled ranking and full risk tables."""
import csv
import gzip
import json
import math
from collections import defaultdict
from fractions import Fraction
import numpy as np
import torch
import issue27frontend_readout_support_v1 as s
import issue27frontend_readout_model_v1 as m
from issue27frontend_readout_train_v1 import load_contexts


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
                budget.check(phase=phase,targets_complete=budget.access['evaluated_targets'],targets_total=budget.targets_total)
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


def historical_predictions(r,baseline,budget):
    all_q = {name:{t['uid']:t[field] for t in baseline} for name,field in [('A','a_logit'),('AB','ab_logit')]}
    for key,names in [('C0_C1_C2',('C0','C1','C2')),('Q_R',('Q','R')),('C0_AB_R_AB',('C0_AB','R_AB'))]:
        spec = r['historical_score_references'][key]
        archive = s.pin(spec['manifest'],budget.check)
        entries = s.manifest(archive.parent,spec['manifest']['sha256'],budget.check)
        for name in names:
            s.require(name not in all_q,'REFERENCE_NAME_COLLISION')
            path = archive.parent/(name+'_expanded.csv.gz')
            s.require(s.sha(path,budget.check)==entries[path.name],'HISTORICAL_SCORE_PIN')
            all_q[name] = read_predictions(path,[t['uid'] for t in baseline])
    return all_q


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


def evaluate(r,out,budget):
    budget.targets_total = r['evaluation']['targets_all_arms']
    train_dir = s.OUTPUTS['T']; s.manifest(train_dir,check=budget.check)
    s.require(s.read_json(train_dir/'supervisor_terminal.json')['status']=='COMPLETE','T_NOT_COMPLETE')
    barrier = s.read_json(train_dir/'candidates_sealed.json')
    s.require(barrier['status']=='FINAL_CANDIDATE_SEALED' and barrier['recipe_sha256']==s.RECIPE_SHA
              and set(barrier['candidates'])=={'H_AB'},'FINAL_BARRIER')
    plan = s.read_json(s.pin(r['inputs']['plan'],budget.check)); s.train_metadata(plan,r)
    prepared = load_contexts(plan['contexts'],s.pin(r['inputs']['train_check_features'],budget.check),budget)
    baseline,expanded,source = expanded_inputs(r,budget)
    check_ref = s.read_json(s.pin(r['inputs']['historical_check_scores'],budget.check))['A']
    check_A = {t['uid']:t['hard'] for t in check_ref if t['owner']=='A'}
    budget.check(True,phase='LOADING_FINAL',arm='H_AB')
    receipt = barrier['candidates']['H_AB']; path = train_dir/'H_AB.pt'
    s.require(s.sha(path,budget.check)==receipt['file_sha256'],'FINAL_FILE_SHA')
    s.require(receipt['initial_state_sha256']==r['inputs']['initial_AB']['state_sha256'],'FINAL_INITIAL_IDENTITY')
    model = m.Student(); model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True); model.eval()
    budget.access['new_candidate_loads'] += 1
    before = m.state_hash(model); s.require(before==receipt['state_sha256'],'FINAL_STATE_SHA')
    frozen = m.freeze(model)
    s.require(frozen==receipt['initial_frozen_tensor_hashes']==receipt['final_frozen_tensor_hashes'],'FINAL_FROZEN_IDENTITY')
    preds = {}
    for role in ('train','check'):
        cs = [c for c in prepared if c['role']==role]
        preds[role] = infer(model,cs,budget,role.upper()+'_EVALUATION')
        save_predictions(out/('H_AB_'+role+'.csv.gz'),preds[role])
        s.require(read_predictions(out/('H_AB_'+role+'.csv.gz'),preds[role])==preds[role],'PREDICTION_ROUNDTRIP')
    q = infer(model,expanded,budget,'EXPANDED_EVALUATION',source)
    save_predictions(out/'H_AB_expanded.csv.gz',q)
    s.require(read_predictions(out/'H_AB_expanded.csv.gz',q)==q,'EXPANDED_PREDICTION_ROUNDTRIP')
    details = check_details(r,prepared,preds,check_A)
    m.verify_frozen(model,frozen)
    s.require(m.state_hash(model)==before,'INFERENCE_MUTATED_STATE')
    verification = dict(state_unchanged=True,frozen_tensor_hashes=frozen,prediction_roundtrip=True,
                        targets=sum(map(len,preds.values()))+len(q))
    del model
    s.require(budget.access['evaluated_targets']==r['evaluation']['targets_all_arms'],'E_TARGET_BUDGET')
    all_q = historical_predictions(r,baseline,budget)
    s.require('H_AB' not in all_q,'REFERENCE_NAME_COLLISION'); all_q['H_AB'] = q
    models = model_metrics(baseline,all_q,budget)
    old_fixed = models['old_P2']['fixed']
    s.require(old_fixed['overall']['detected']==r['evaluation']['old_attack_reference_exact']['detected']
              and old_fixed['future']['detected']==r['evaluation']['old_future_reference_exact']['detected'],'OLD_P2_REFERENCE')
    contrasts = {name:contrast(models[name.split('-')[1]],models[name.split('-')[0]]) for name in r['evaluation']['contrasts']}
    qh = {k:int(v>=0) for k,v in q.items()}
    for name in list(all_q)+['old_P2']:
        if name=='H_AB':continue
        old = {t['uid']:t['old_hard'] for t in baseline} if name=='old_P2' else {k:int(v>=0) for k,v in all_q[name].items()}
        with gzip.open(out/('H_AB_vs_'+name+'_flips.json.gz'),'wt',encoding='utf-8') as f:
            json.dump(flips(baseline,old,qh),f,ensure_ascii=False,allow_nan=False)
    result = dict(models=models,contrasts=contrasts,check_and_train={'H_AB':details},verification={'H_AB':verification},
                  tail_composition={name:tail_composition(baseline,scores,models[name]['ranking']) for name,scores in all_q.items()},
                  AB_tail_comparison={'H_AB':compare_ab_tail(models['H_AB'],models['AB'])},
                  evidence='EXPOSED_DEVELOPMENT_ONLY',original_strict_verdict='HISTORICAL_FAIL_UNCHANGED',
                  practical_success='MANUAL_SCIENTIFIC_REVIEW_REQUIRED',commissioning='NOT_EVALUATED',
                  next_boundary='MANUAL_RISK_REVIEW_NO_AUTOMATIC_PROMOTION' if contrasts['H_AB-AB']['status']=='DEVELOPMENT_DIRECTIONAL_JOINT_GAIN'
                  else 'END_ADJACENT_SAME_TRAIN_TUNING_REQUIRE_INPUT_OR_TRAINING_SUPPORT_EVIDENCE')
    s.atomic_json(out/'comparison.json',result)
    lines = ['# 固定AB表示、完整检测头适配：终点结果','',
             '已暴露开发证据；历史严格继承FAIL保持，新设备入网尚未评估。','',
             '| 模型 | 攻击召回 | future召回 | OOD池均误报 | 最差池误报 | 合并TPR@1%FPR | TPR@0.1%FPR |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name in ('old_P2','A','AB','C0','C1','C2','Q','R','C0_AB','R_AB','H_AB'):
        v = models[name]; f = v['fixed']
        low = ['—','—'] if v['ranking'] is None else ['%.4f%%'%(100*v['ranking']['points'][cap]['tpr']) for cap in ('0.01','0.001')]
        lines.append('| %s | %.4f%% | %.4f%% | %.4f%% | %.4f%% | %s | %s |'%(name,100*f['overall']['recall'],100*f['future']['recall'],
                     100*f['benign_pool_macro_fpr'],100*f['worst_pool_fpr'],*low))
    lines += ['', '主要对比：'+', '.join(name+'='+v['status'] for name,v in contrasts.items()),
              '固定编码器不保证最终排序保持；0.1%与逐族/逐池风险必须独立审阅。',
              '1%/0.1%为18000条正常OOD上的描述点；普通ID151另报，不是部署阈值。',
              'H_AB和C0_AB直接标签历史相同，参数更新范围不同。没有教师或保护项观察。',
              '下一边界：'+result['next_boundary'], '全部分组与翻转见comparison.json及flips文件。']
    (out/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(status='EVALUATION_COMPLETE',targets=budget.access['evaluated_targets'],candidates=['H_AB'])

