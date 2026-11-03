"""Independent count checks and metadata-only coverage supplement; no model imports."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import numpy as np
import legacy_reference_executor_common_v1 as c

ROOT = Path(__file__).resolve().parents[2]
DIAG = ROOT/'runs/legacy_reference_dev_mechanism_diagnosis_v1_20260922'
AUDIT = ROOT/'runs/legacy_reference_hpc_saved_score_audit_v1_20260922'
HPC = ROOT/'runs/legacy_reference_hpc_preparation_v1_20260918'
RUN = HPC/'pullback/extracted/runs/real_dev'
OUT = ROOT/'runs/legacy_reference_dev_diagnosis_validation_v1_20260922'


def main():
    c.require(not OUT.exists(), 'NEW_OUTPUT_REQUIRED')
    c.verify_seal(DIAG); c.verify_seal(AUDIT)
    recipe = c.recipe(); theta = recipe['legacy']['threshold_probability']
    specs = recipe['data']['manifests']
    for role in ('LEARN', 'DEV', 'REFERENCE'):
        c.pin(c.confined(ROOT, specs[role]['path']), specs[role]['sha256'])
    rows = list(c.rows(c.confined(ROOT, specs['DEV']['path'])))
    with np.load(RUN/'evaluation_DEV/logits.npz', allow_pickle=False) as f:
        c.require(list(f['uid']) == [r['uid'] for r in rows], 'UID_ORDER')
        # Independent probability-space thresholding, not the diagnostic's logit comparison.
        predictions = {a: 1/(1+np.exp(-f[a].astype(np.float64))) >= theta for a in ('R','Q','M','C')}
    old = c.load(AUDIT/'DEV_saved_score_statistics.json')['reports']
    paired = c.load(DIAG/'paired_changes.json')
    groups = c.load(DIAG/'DEV_groups.json')
    checks = {}; max_weight_delta = 0.
    for y, label in ((0, 'normal'), (1, 'attack')):
        ix = [i for i, r in enumerate(rows) if r['label'] == y]
        for arm, p in predictions.items():
            count = sum(bool(p[i]) for i in ix)
            wden = math.fsum(1/rows[i]['label_metric_weight_denominator'] for i in ix)
            rate = math.fsum(1/rows[i]['label_metric_weight_denominator'] for i in ix if p[i])/wden
            expected = old[arm]['overall'][label]
            c.require(count == expected['positive'] and len(ix) == expected['rows'], 'TOTAL_COUNT_DRIFT')
            delta = abs(rate-expected['weighted_rate']); max_weight_delta=max(max_weight_delta,delta)
            c.require(delta < 1e-12, 'WEIGHTED_TOTAL_DRIFT')
        for arm in ('M','C'):
            flips = Counter((bool(predictions['Q'][i]),bool(predictions[arm][i])) for i in ix)
            loss_key, gain_key = ('normal_fixed','normal_new_fp') if y == 0 else ('attack_new_miss','attack_recovered')
            c.require(flips[(True,False)] == paired[arm][loss_key]['rows'] and flips[(False,True)] == paired[arm][gain_key]['rows'], 'PAIR_DRIFT')
            checks[arm+'_'+label] = {str(k):v for k,v in flips.items()}
    for group in groups:
        ix=[i for i,r in enumerate(rows) if all(str(r[k])==v for k,v in group['group'].items())]
        c.require(len(ix)==group['stats']['rows'], 'GROUP_DENOMINATOR_DRIFT')
        for arm,p in predictions.items():
            c.require(sum(bool(p[i]) for i in ix)==group['stats']['arms'][arm]['positive'], 'GROUP_COUNT_DRIFT')

    service=Counter(); units={}; sessions=defaultdict(list)
    for i,r in enumerate(rows): sessions[(r['device'],r['label'],r['session_id'])].append(i)
    session_out=[]
    for device in sorted({r['device'] for r in rows}):
        for y in (0,1):
            ss=[ix for (d,lab,_),ix in sessions.items() if d==device and lab==y]
            session_out.append(dict(device=device,label=y,sessions=len(ss),
                any_alarm={a:sum(any(bool(p[i]) for i in ix) for ix in ss) for a,p in predictions.items()},
                note='Exploratory any-query alarm per session, not the frozen query-rate endpoint or timely detection.'))
    for role in ('LEARN','DEV'):
        counts=Counter(); components=defaultdict(set); captures=defaultdict(set); unique_sessions=defaultdict(set)
        source=rows if role=='DEV' else c.rows(c.confined(ROOT,specs[role]['path']))
        for r in source:
            key=(r['device'],r['label']); counts[key]+=1
            components[key].add(r['component_id']); captures[key].add(r['capture_id']);unique_sessions[key].add(r['session_id'])
            has80=any(endpoint[1]==80 for endpoint in r['canonical_key'][1:])
            service[(role,r['device'],r['label'],'either_endpoint_80' if has80 else 'neither_endpoint_80')]+=1
        units[role]=[dict(device=d,label=y,queries=count,sessions=len(unique_sessions[(d,y)]),components=len(components[(d,y)]),captures=len(captures[(d,y)])) for (d,y),count in sorted(counts.items())]
    refs=defaultdict(list)
    for r in c.rows(c.confined(ROOT,specs['REFERENCE']['path'])):
        if r['partition'] in ('LEARN','DEV'): refs[r['device']].append(r)
    ref_units=[dict(device=d,references=len(rr),sessions=len({r['session_id'] for r in rr}),components=len({r['component_id'] for r in rr}),captures=len({r['capture_id'] for r in rr}),activities=sorted({r['activity'] for r in rr})) for d,rr in sorted(refs.items())]

    # Ensure audited source is the delivered code (packaging only canonicalizes LF).
    names=['legacy_reference_executor_model_v1.py','legacy_reference_executor_train_v1.py',
           'legacy_reference_feature_adapter_v1.py','legacy_reference_context_scope_v1.py',
           'legacy_reference_sample_prepare_v1.py','legacy_reference_executor_features_v1.py',
           'issue27ckda_d0_resource_pilot_v1.py']
    bundle=HPC/'bundle/legacy_reference_hpc_dev_v1_20260918'
    c.verify_seal(bundle)
    code_pins={}
    for name in names:
        p=ROOT/'repo/ood'/name; q=bundle/'repo/ood'/name
        c.require(p.read_bytes().replace(b'\r\n',b'\n')==q.read_bytes().replace(b'\r\n',b'\n'), 'DELIVERED_CODE_DRIFT:'+name)
        code_pins[name]=dict(local_sha256=c.sha(p),delivered_sha256=c.sha(q))
    OUT.mkdir()
    c.atomic_json(OUT/'validation.json',dict(status='PASS',pair_tables=checks,checked_groups=len(groups),max_weighted_rate_delta=max_weight_delta,
        model_forwards=0,optimizer_steps=0,threshold_searches=0,holdout_queries_opened=False,code_pins=code_pins,
        diagnostic_seal_sha256=c.sha(DIAG/'SHA256SUMS'),script_sha256=c.sha(Path(__file__))))
    c.atomic_json(OUT/'service_coverage.json',{'counts':{'|'.join(map(str,k)):v for k,v in sorted(service.items())},'interpretation':'Endpoint port metadata only; not local port, direction, direct model input, or causal shortcut evidence.'})
    c.atomic_json(OUT/'independence_units.json',dict(queries=units,references=ref_units,DEV_session_any_alarm=session_out))
    c.seal(OUT)
    print('PASS',OUT,flush=True)


if __name__=='__main__':main()
