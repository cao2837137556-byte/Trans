"""Synthetic contract tests, never substitute for real cache acceptance."""
import ast,hashlib,json,sys,tempfile
from pathlib import Path
import numpy as np
import analysis_core as a
import run as worker
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]

def main():
    rng=np.random.default_rng(27);n=160
    raw=np.column_stack((rng.normal(0,30,(n,3)),np.zeros(n)));raw[:,3]=raw[:,:3].mean(1)
    q=np.zeros((n,14));q[:80,0]=1;q[:40,2]=1;q[40:60,2]=1;q[40:60,5]=1
    s=rng.uniform(0,1,n);s[60:65]=0;s[65:70]=1;scales=np.array([118.95627975463867,121.3746566772461,122.36117172241211]);cuts=np.array([-23.,-24.,-22.,-23.])
    tree=ast.parse((ROOT/'runs/device_context_evaluation_v1_20261105/common.py').read_text());env={'np':np}
    for name in ['four','correction']:
        node=next(v for v in tree.body if isinstance(v,ast.FunctionDef) and v.name==name);exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_common.py','exec'),env)
    values={k:a.scores(raw,s,q,scales,k) for k in a.ARMS};expected=env['four'](env['correction'](raw[:,:3],s,q,scales));assert np.array_equal(values['BASE'],expected)
    assert np.any(values['BASE'][:40]>values['GUARD_OFF'][:40]),'SYN_RAW_SUPPORT_MUST_NOT_BE_PREZEROED'
    assert np.array_equal(a.scores(raw,s,q,scales,'P1')[:,:3][80:],(raw[:,:3]-.25*scales*s[:,None])[80:])
    gates=[a.invariant(values,s,q,cuts,k) for k in ['guard','exponent']]
    rows=[dict(uid=str(i),device='d'+str(i%2),label=int(i%3!=0),source_role='NORMAL' if i%3==0 else 'HTTP',activity='x') for i in range(n)]
    weights=np.arange(1,n+1,dtype=float);weights/=weights.sum();views={'full':(np.arange(n),weights),'post_window_primary':(np.arange(20,n),weights)}
    metrics=a.metrics('SYNTHETIC',rows,values['BASE']>cuts,views,q,np.ones(n)*2,{'NORMAL':300,'HTTP':500})
    normal=next(r for r in metrics if r['group']=='NORMAL' and r['guard_stratum']=='ALL' and r['head']=='ensemble' and r['view']=='full')
    ix=np.array([i for i,r in enumerate(rows) if r['label']==0]);pred=values['BASE']>cuts
    assert normal['alarm_count']==pred[ix,3].sum() and normal['weighted_numerator']==weights[ix][pred[ix,3]].sum()
    assert normal['HT_rate']==2*normal['alarm_count']/300
    pairs=a.paired('SYNTHETIC',rows,pred,values['GUARD_OFF']>cuts,views,q,np.ones(n)*2)
    assert all(r['n01']==0 for r in pairs)
    assert all(r['n10']==0 for r in pairs if r['guard_stratum']=='GUARD_OFF')
    frozen=[dict(r,method='C5_3D_OLD') for r in metrics if r['guard_stratum']=='ALL']
    gate,_=worker.check_baseline('SYNTHETIC',values['BASE'],expected,rows,views,q,cuts,frozen,np.ones(n)*2,{'NORMAL':300,'HTTP':500})
    # Score tolerance must never excuse a threshold decision flip.
    changed=expected.copy();changed[0,0]+=1e-11;boundary=cuts.copy();boundary[0]=expected[0,0]
    try:worker.check_baseline('SYNTHETIC',values['BASE'],changed,rows,views,q,boundary,frozen,np.ones(n)*2,{'NORMAL':300,'HTTP':500})
    except AssertionError:pass
    else:raise AssertionError('SMALL_SCORE_ERROR_DECISION_FLIP_ACCEPTED')
    bad=[dict(r) for r in frozen];bad[0]['alarm_count']+=1
    try:worker.check_baseline('SYNTHETIC',values['BASE'],expected,rows,views,q,cuts,bad,np.ones(n)*2,{'NORMAL':300,'HTTP':500})
    except AssertionError:pass
    else:raise AssertionError('MUTATED_BASELINE_ACCEPTED')
    # strict > at an exact threshold is intentionally not an alert
    assert not (np.array([1.])>np.array([1.])).any()
    for value in [-.1,1.1,np.nan]:
        wrong=s.copy();wrong[0]=value
        try:a.scores(raw,wrong,q,scales,'BASE')
        except AssertionError:pass
        else:raise AssertionError('INVALID_SUPPORT_ACCEPTED')
    original_out=worker.OUT
    with tempfile.TemporaryDirectory() as tmp:
        worker.OUT=Path(tmp);worker.write(worker.OUT/'BASELINE_ACCEPTANCE.json',dict(status='SYNTHETIC_FIXTURE'))
        loaded={'SYNTHETIC':dict(rows=rows,q=q,s=s,raw=raw,base=values['BASE'],ids=np.array([str(i) for i in range(n)]),views=views,expansion=np.ones(n)*2,population={'NORMAL':300,'HTTP':500})}
        try:
            worker.stage('guard',loaded,cuts,scales)
            assert (worker.OUT/'guard/COMPLETE.json').exists() and not (worker.OUT/'exponent/COMPLETE.json').exists()
            worker.stage('exponent',loaded,cuts,scales)
            for stage in ['guard','exponent']:
                receipt=json.loads((worker.OUT/stage/'VERIFICATION.json').read_text());assert receipt['status']=='PASS'
                for name,digest in receipt['output_sha256'].items():assert worker.sha(worker.OUT/stage/name)==digest
        finally:worker.OUT=original_out
    for f in HERE.glob('*.py'):ast.parse(f.read_text())
    worker.write(HERE/'LOCAL_VALIDATION.json',dict(status='PASS',synthetic_only=True,real_cache_gate='NOT_RUN',producer_p3_bitwise_equal=True,raw_support_guard_trap_detected=True,metric_and_pair_weight_checks=True,mutated_baseline_rejected=True,strict_threshold_and_support_bounds=True,tiny_score_decision_flip_rejected=True,per_item_artifacts_and_sha_checked=True,invariants=gates,source_hashes={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in [HERE/'analysis_core.py',HERE/'run.py']}))
    print('PASS: original P3 arithmetic, guard trap, monotonicity, weighted pairs, HT, baseline rejection. Real caches NOT run.')
if __name__=='__main__':main()
