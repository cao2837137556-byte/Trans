"""Post hoc diagnostics on frozen LEARN/DEV manifests and existing scores only.

No model is instantiated, no scores are inferred, no threshold is selected.
No DEVICE_HOLDOUT query manifest is opened. All derived evidence is separate.
"""
from pathlib import Path
from collections import Counter, defaultdict
import datetime as dt
import math
import numpy as np
import legacy_reference_executor_common_v1 as c

ROOT = Path(__file__).resolve().parents[2]
PULL = ROOT/'runs/legacy_reference_hpc_preparation_v1_20260918/pullback/extracted'
RUN = PULL/'runs/real_dev'
AUDIT = ROOT/'runs/legacy_reference_hpc_saved_score_audit_v1_20260922'
OUT = ROOT/'runs/legacy_reference_dev_mechanism_diagnosis_v1_20260922'


def quantile(x):
    return dict(zip(('min', 'q10', 'median', 'q90', 'max'), map(float, np.quantile(x, [0, .1, .5, .9, 1])))) if len(x) else None


def load(role, recipe):
    c.require(role in ('LEARN', 'DEV', 'REFERENCE'), 'ROLE_FORBIDDEN')
    spec = recipe['data']['manifests'][role]; path = c.confined(ROOT, spec['path']); c.pin(path, spec['sha256'])
    return c.rows(path)


def scores(path, n, names):
    with np.load(path, allow_pickle=False) as source:
        result = {k: source[k].copy() for k in names}
    c.require(all(v.shape == (n,) and np.isfinite(v).all() for v in result.values()), 'SCORE_SCHEMA')
    return result


def main():
    c.require(not OUT.exists(), 'NEW_OUTPUT_REQUIRED')
    c.verify_seal(AUDIT)
    manifest = c.load(PULL/'EXPORT_MANIFEST.json')
    for item in manifest['included']:
        # Scores, models and requests all remain immutable prior evidence.
        c.pin(c.confined(PULL, item['path']), item['sha256'])
    recipe = c.recipe(); theta = recipe['legacy']['threshold_probability']; threshold = math.log(theta/(1-theta))
    rows = list(load('DEV', recipe)); n = len(rows)
    names = ['R', 'Q', 'M', 'C'] + [a+'_'+str(s) for a in ('Q','M','C') for s in (27,127,227)]
    logits = scores(RUN/'evaluation_DEV/logits.npz', n, names)
    with np.load(RUN/'evaluation_DEV/logits.npz', allow_pickle=False) as z:
        c.require(list(z['uid']) == [r['uid'] for r in rows], 'UID_ORDER')
    pred = {k: v.astype(np.float64) >= threshold for k,v in logits.items()}
    label = np.array([r['label'] for r in rows]); weight = np.array([1/r['label_metric_weight_denominator'] for r in rows])

    def stats(mask):
        ix = np.flatnonzero(mask); result = {'rows':len(ix), 'arms':{}}
        for arm in names:
            positive = pred[arm][ix]
            result['arms'][arm] = dict(positive=int(positive.sum()), rate=float(positive.mean()) if len(ix) else None,
                weighted_rate=float(np.sum(weight[ix]*positive)/np.sum(weight[ix])) if len(ix) else None)
        return result

    paired = {}
    for arm in ('M','C'):
        groups = {
            'normal_fixed':(label==0)&pred['Q']&~pred[arm],
            'normal_new_fp':(label==0)&~pred['Q']&pred[arm],
            'attack_new_miss':(label==1)&pred['Q']&~pred[arm],
            'attack_recovered':(label==1)&~pred['Q']&pred[arm],
        }
        paired[arm] = {}
        for name, mask in groups.items():
            ix = np.flatnonzero(mask)
            paired[arm][name] = dict(rows=len(ix), sessions=len({rows[i]['session_id'] for i in ix}),
                components=len({rows[i]['component_id'] for i in ix}), captures=len({rows[i]['capture_id'] for i in ix}),
                cells=dict(Counter(rows[i]['device']+'|'+rows[i]['activity']+'|'+rows[i]['capture_id'] for i in ix)),
                margins={a:quantile(logits[a][ix]-threshold) for a in ('R','Q','M','C')},
                delta_vs_Q=quantile(logits[arm][ix]-logits['Q'][ix]),
                same_decision_all_three_seeds=int(np.all(np.stack([pred[arm+'_'+str(s)][ix] for s in (27,127,227)])==pred[arm][ix],axis=0).sum()))
    grouped = []
    for fields in [('device','label','activity'), ('device','label','capture_id'), ('device','label','normal_activity_stratum')]:
        groups = defaultdict(list)
        for i,r in enumerate(rows):groups[tuple(str(r[k]) for k in fields)].append(i)
        for key, ix in sorted(groups.items()):
            mask = np.zeros(n,dtype=bool); mask[ix]=True
            grouped.append(dict(group=dict(zip(fields,key)), stats=stats(mask), sessions=len({rows[i]['session_id'] for i in ix}),
                components=len({rows[i]['component_id'] for i in ix}),
                dates=sorted({dt.datetime.fromtimestamp(rows[i]['timestamp'],dt.timezone.utc).date().isoformat() for i in ix})))
    q_errors = []
    for i in np.flatnonzero(pred['Q']!=label):
        r=rows[i];q_errors.append(dict(r, logits={a:float(logits[a][i]) for a in names}))
    errors = {a:(pred[a]!=label) for a in ('Q','M','C')}
    overlap = {str(y):{'M_C_common_errors':int(((label==y)&errors['M']&errors['C']).sum()),
        'Q_M_C_common_errors':int(((label==y)&errors['Q']&errors['M']&errors['C']).sum())} for y in (0,1)}

    interventions=[];control_numerics=[]
    for control in recipe['evaluation']['interventions']:
        if control.get('partition')!='DEV':continue
        ix=np.array([i for i,r in enumerate(rows) if r['device']==control['device'] and r['timestamp']>control['applicable_after']])
        c.require(len(ix)==control['applicable_query_count'] and c.digest(sorted(rows[i]['uid'] for i in ix))==control['applicable_query_uid_hash'],'INTERVENTION_ID')
        paths={k:RUN/'evaluation_DEV'/(control['device'].replace(' ','_')+'_'+k+'.npz') for k in ('correct','wrong')}
        values={k:scores(p,len(ix),names) for k,p in paths.items()}
        for arm in ['R','Q','Q_27','Q_127','Q_227']:
            own=values['correct'][arm];wrong=values['wrong'][arm];original=logits[arm][ix]
            c.require(np.array_equal(own,wrong),'CONTROL_REFERENCE_INDEPENDENCE')
            # The subset has different batch composition from the full DEV pass.
            # Preserve the existing numerical preflight tolerances and additionally
            # require exactly the same decisions; this is not a scientific gate.
            c.require(np.allclose(own,original,rtol=1e-4,atol=1e-5) and
                      np.array_equal(own.astype(np.float64)>=threshold,original.astype(np.float64)>=threshold),'CONTROL_QUERY_CHANGED')
            control_numerics.append(dict(device=control['device'],arm=arm,correct_wrong_exact=True,
                subset_full_max_abs=float(np.max(np.abs(own-original))),subset_full_decisions_exact=True))
        for arm in ('M','C'):
            for y in (0,1):
                local=label[ix]==y;a=values['correct'][arm][local];b=values['wrong'][arm][local]
                ha=a.astype(np.float64)>=threshold;hb=b.astype(np.float64)>=threshold
                interventions.append(dict(device=control['device'],arm=arm,label=y,rows=int(local.sum()),
                    correct_positive=int(ha.sum()),wrong_positive=int(hb.sum()),correct_to_wrong_lost=int((ha&~hb).sum()),
                    correct_to_wrong_gained=int((~ha&hb).sum()),wrong_minus_correct=quantile(b-a),
                    original_Q_margin_among_wrong_recovered=quantile(logits['Q'][ix][local][~ha&hb]-threshold)))
    small=scores(RUN/'evaluation_DEV/budget16_logits.npz',n,names);budget=[]
    for device in sorted({r['device'] for r in rows}):
        for arm in ('Q','M','C'):
            for y in (0,1):
                ix=np.array([i for i,r in enumerate(rows) if r['device']==device and r['label']==y]);p=small[arm][ix].astype(np.float64)>=threshold
                budget.append(dict(device=device,arm=arm,label=y,full_positive=int(pred[arm][ix].sum()),budget16_positive=int(p.sum()),
                    full_to_small_lost=int((pred[arm][ix]&~p).sum()),full_to_small_gained=int((~pred[arm][ix]&p).sum()),
                    score_difference=quantile(small[arm][ix]-logits[arm][ix])))

    # Independently inspect cross-partition equality and chronology. No HOLDOUT queries.
    keys=('uid','owner','device','capture_id','source_sha256','session_id','component_id','packet_sha256')
    dev_sets={k:{r[k] for r in rows} for k in keys}
    dev_packet_time={(r['packet_sha256'],round(r['timestamp']*1e6)) for r in rows}
    dev_canonical={json_key(r['canonical_key']) for r in rows}
    common={k:set() for k in keys};common['packet_time']=set();common['canonical_without_owner']=set()
    learn_counts=Counter();learn_devices=set();learn_times=defaultdict(lambda:[math.inf,-math.inf]);learn_sources={}
    all_query_times=defaultdict(lambda:[math.inf,-math.inf]);services=Counter()
    for r in rows:
        t=all_query_times[r['device']];t[0]=min(t[0],r['timestamp']);t[1]=max(t[1],r['timestamp'])
        services[(r['device'],r['label'],'either_endpoint_port80' if any(x[1]==80 for x in r['canonical_key'][1:]) else 'other_ports')]+=1
    for r in load('LEARN',recipe):
        c.require(r['partition']=='LEARN','LEARN_SCOPE');learn_counts[(r['device'],r['label'],r['activity'])]+=1;learn_devices.add(r['device'])
        t=all_query_times[r['device']];t[0]=min(t[0],r['timestamp']);t[1]=max(t[1],r['timestamp'])
        learn_sources[r['capture_id']]=r['source_sha256']
        for k in keys:
            if r[k] in dev_sets[k]:common[k].add(r[k])
        tkey=(r['packet_sha256'],round(r['timestamp']*1e6))
        if tkey in dev_packet_time:common['packet_time'].add(tkey)
        canon=json_key(r['canonical_key'])
        if canon in dev_canonical:common['canonical_without_owner'].add(canon)
        c.require(r['timestamp']>r['reference_end'],'LEARN_REFERENCE_TIME')
    reference=defaultdict(list)
    for r in load('REFERENCE',recipe):
        if r['partition'] not in ('LEARN','DEV'):continue
        reference[r['device']].append(r)
    time_checks=[]
    for device,refs in reference.items():
        c.require(all(r['label']==0 and r['use']=='REFERENCE' for r in refs),'REFERENCE_NORMAL')
        first,last=all_query_times[device];refmax=max(r['timestamp'] for r in refs);end=max(r['reference_end'] for r in refs)
        c.require(refmax<=end<first,'CAUSAL_REFERENCE')
        time_checks.append(dict(device=device,partition=refs[0]['partition'],references=len(refs),normal_activities=sorted({r['activity'] for r in refs}),
            reference_protocols=dict(Counter(r['protocol'] for r in refs)),seconds_reference_end_to_first_query=first-end,
            query_days_span=(last-first)/86400,reference_capture_overlap_DEV=len({r['capture_id'] for r in refs}&dev_sets['capture_id']),
            reference_packet_time_overlap_DEV=sum((r['packet_sha256'],round(r['timestamp']*1e6)) in dev_packet_time for r in refs)))
    for r in rows:c.require(r['timestamp']>r['reference_end'],'DEV_REFERENCE_TIME')
    split=dict(overlaps={k:len(v) for k,v in common.items()},learn_devices=sorted(learn_devices),dev_devices=sorted(dev_sets['device']),
        learn_counts={'|'.join(map(str,k)):v for k,v in learn_counts.items()},reference_chronology=time_checks,
        dev_port80_counts={'|'.join(map(str,k)):v for k,v in services.items()},
        limitation='Exact current packet equality and source identities only; normalized prefix/feature similarity and foundation pretraining overlap not evaluated.')
    # Active normal PCAPs contain multiple owners. Shared source files are a
    # capture-environment dependence, not by themselves duplicated samples.
    split['shared_capture_ids'] = sorted(common['capture_id'])
    split['shared_capture_interpretation'] = ('Multi-device normal captures shared across partitions; owner/context isolation must be audited separately. '
        'Zero current-packet-and-time overlap does not prove prefix-feature independence.')
    c.require(not any(split['overlaps'][k] for k in ('uid','owner','device','session_id','component_id','packet_time')),'SAMPLE_OR_OWNER_SPLIT_OVERLAP')
    print('SPLIT_AND_SAVED_SCORE_DIAGNOSTICS_READY',flush=True)

    OUT.mkdir()
    for name,value in [('paired_changes',paired),('DEV_groups',grouped),('Q_errors',q_errors),('error_overlap',overlap),
                       ('reference_interventions',interventions),('control_numerics',control_numerics),('budget16_effect',budget),('split_and_reference',split)]:
        c.atomic_json(OUT/(name+'.json'),value)
    c.atomic_json(OUT/'receipt.json',dict(status='COMPLETE_POSTHOC_DIAGNOSTIC',source_job=172780,threshold_probability=theta,
        source_science_gate_changed=False,model_forwards=0,optimizer_steps=0,holdout_queries_opened=False,
        selected_models_or_thresholds=False,scope='Existing DEV predictions and LEARN/DEV metadata; exploratory diagnosis, not confirmatory validation',
        pins={str(p.relative_to(ROOT)).replace('\\','/'):c.sha(p) for p in [Path(__file__),AUDIT/'SHA256SUMS',PULL/'EXPORT_MANIFEST.json',RUN/'SHA256SUMS']}))
    c.seal(OUT)
    print('COMPLETE',OUT,flush=True)


def json_key(value):
    import json
    return json.dumps(value,separators=(',',':'))


if __name__=='__main__':main()
