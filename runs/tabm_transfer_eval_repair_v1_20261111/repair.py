"""Resume only cached evaluation. Original strict gates and data stay unchanged."""
import gc,gzip,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
OLD=ROOT/'runs/tabm_3d_transfer_v1_20261111';P4=ROOT/'runs/p4_complete_bank_v1_20261111';EVAL=ROOT/'runs/device_context_evaluation_v1_20261105'
OUT=HERE/'results';ART=HERE/'artifacts';CREATED=False
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');tmp.replace(path)
def progress(stage,done=0,total=1,**kw):
    import psutil
    rss=psutil.Process().memory_info().rss;assert rss<11*1024**3,'HOST_HEADROOM'
    write(HERE/'PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),updated_unix=time.time(),rss_bytes=rss))
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
    global CREATED
    assert not OUT.exists(),'NEW_REPAIR_OUTPUT_ONLY';OUT.mkdir();ART.mkdir();CREATED=True
    for n,h in read(HERE/'PACKAGE_MANIFEST.json')['files'].items():assert sha(HERE/n)==h,'PACKAGE_SHA:'+n
    for n,h in read(HERE/'INPUT_PINS.json').items():assert sha(ROOT/n)==h,'INPUT_SHA:'+n
    for n,h in read(HERE/'RECOVERY_PINS.json').items():assert sha(OLD/n)==h,'FAILED_JOB_VALID_OUTPUT_SHA:'+n
    progress('VERIFY_REUSABLE_TABM_OUTPUTS')
    rawgate=read(OLD/'results/TABM_RAW_REPRODUCTION.json');cal=read(OLD/'results/TABM_SOURCE_CALIBRATION.json');native=read(OLD/'results/TABM_NATIVE_METRIC_REPRODUCTION.json');scale=read(OLD/'results/SCALE_AND_THRESHOLD_FREEZE.json')
    assert rawgate['status']==cal['status']==native['status']=='PASS'
    assert all(v['max_score_abs_error']==0 and v['decision_differences']==0 for v in rawgate['gates'].values())
    assert sha(OLD/'artifacts/FIT_RESCORED.npy')==rawgate['fit_score_sha256']
    fitinfo=read(OLD/'results/SOURCE_FIT_IDENTITY.json');wp=OLD/'artifacts/FIT_WEIGHTS.npy';assert sha(wp)==fitinfo['weight_sha256']
    for seed,v in rawgate['model_assets'].items():assert sha(Path(v['path']))==v['sha256']
    sys.path.insert(0,str(EVAL));import common as c,reporting,metrics
    assert Path(c.__file__).resolve()==EVAL/'common.py';c.verify();c.progress=progress
    sys.path.insert(0,str(c.TRAIN));import context_core as k,constrained_onboarding_core_v3 as geometry
    fit=np.load(OLD/'artifacts/FIT_RESCORED.npy',mmap_mode='r');w=np.load(wp)
    assert fit.shape==(617908,4)
    q10=[geometry.weighted_quantile(fit[:,j],w,.1) for j in range(3)];q90=[geometry.weighted_quantile(fit[:,j],w,.9) for j in range(3)]
    assert q10==cal['q10'] and q90==cal['q90'] and np.array_equal(np.asarray(q90)-q10,cal['scales'])
    folder=ROOT/'runs/baseline_remaining_three_v2_20261108/artifacts/evaluation';raw={};rows={}
    for pool,v in rawgate['input_assets'].items():
        sp=Path(v['scores_path']);assert sha(sp)==v['scores_sha256'];rp=folder/(pool+'_ROWS.json');assert sha(rp)==v['input']['rows_sha256']
        raw[pool]=np.load(sp,mmap_mode='r');rows[pool]=read(rp);assert k.c.uid_sha(r['uid'] for r in rows[pool])==v['input']['uid_sha256']
    cuts=np.asarray(cal['cuts']);assert np.array_equal([k.threshold(raw['CAL'][:,j],rows['CAL'],.01) for j in range(4)],cuts)
    assert scale['tabm_own_scales']==cal['scales'] and scale['tabm_cuts']==cal['cuts']
    # Use compact pinned query metadata produced by the completed controls job.
    control=read(P4/'results/controls/COMPLETE.json');assert control['status']=='PASS'
    for n,h in control['outputs_sha256'].items():assert sha(P4/'results/controls'/n)==h
    assets=read(P4/'results/controls/QUERY_ASSETS.json');loaded={};diagnosis={}
    for pool,a in assets.items():
        progress('CPU_CACHE_PARITY_'+pool)
        for filekey,shakey in [('array_file','array_sha256'),('rows_file','rows_sha256'),('scores_file','scores_sha256')]:assert sha(P4/'artifacts'/a[filekey])==a[shakey]
        with gzip.open(P4/'artifacts'/a['rows_file'],'rt',encoding='utf8') as f:rr=[json.loads(x) for x in f]
        with np.load(P4/'artifacts'/a['array_file'],allow_pickle=False) as z:d=dict(rows=rr,ids=z['uid'].copy(),q=z['q'].copy(),s=z['support3'].copy(),views={n:(z[n+'_ix'].copy(),z[n+'_weight'].copy()) for n in a['views']},expansion=z['expansion'].copy() if 'expansion' in z else None,population=a['population'])
        oldresult=read(ROOT/'runs/same_bank_context_v6_20261106/DIAGNOSE_RESULT.json')['pools'][pool]['artifact'];fp=ROOT/'runs/same_bank_context_v6_20261106'/oldresult['file'];assert sha(fp)==oldresult['sha256']
        with np.load(fp,allow_pickle=False) as z:
            assert np.array_equal(d['ids'],z['uid']) and np.array_equal(d['s'],z['support3']);d['raw']=z['RAW'].copy();d['base']=z['C5_3D_OLD'].copy();saved=z['C5_3D_FUSION'].copy()
        assert d['ids'].tolist()==[r['uid'] for r in rows[pool]]
        rebuilt=c.four(c.correction(d['raw'][:,:3],d['s'],d['q'],np.asarray(scale['mlp_own_scales'])));mc=np.asarray(scale['mlp_cuts']);diff=rebuilt-saved
        diagnosis[pool]=dict(max_score_abs_error=float(np.abs(diff).max()),differing_values=int(np.count_nonzero(diff)),decision_differences=int(np.count_nonzero((rebuilt>mc)!=(saved>mc))))
        write(HERE/'CPU_PARITY_DIAGNOSIS.json',diagnosis)
        assert np.array_equal(rebuilt,saved),'ORIGINAL_BITWISE_MLP_GATE_RETAINED'
        loaded[pool]=d
    t=load('original_transfer_evaluation',OLD/'transfer.py');t.OUT=OUT;t.ART=ART;t.progress=progress
    for n in ['SOURCE_FIT_IDENTITY.json','TABM_SOURCE_CALIBRATION.json','TABM_RAW_REPRODUCTION.json','TABM_NATIVE_METRIC_REPRODUCTION.json','SCALE_AND_THRESHOLD_FREEZE.json']:write(OUT/n,read(OLD/'results'/n))
    progress('RESUME_P3_EVALUATION_ONLY')
    t.evaluate(c,reporting,metrics,loaded,np.asarray(scale['mlp_cuts']),np.asarray(scale['mlp_own_scales']),raw,rows,cuts,np.asarray(cal['scales']),read(OLD/'TABM_EXPECTED_METRICS.json'))
    write(OUT/'RUN_COMPLETE.json',dict(status='PASS',recovery='CPU cached evaluation; original bitwise gate unchanged',training=False,new_forward=False,original_gpu_job='183549',output_sha256={p.name:sha(p) for p in OUT.iterdir() if p.is_file()}))
    del loaded,rows,raw,fit,w;gc.collect()
    progress('RESUME_P4_CACHED_BRIDGE')
    p4art=HERE/'p4_artifacts';p4art.mkdir();p4out=HERE/'p4_results';p4out.mkdir()
    for a in assets.values():
        for n in ['array_file','rows_file','scores_file']:(p4art/a[n]).symlink_to(P4/'artifacts'/a[n])
    bridge=load('original_p4_cached_bridge',P4/'worker.py');bridge.TABM=HERE;bridge.ART=p4art;bridge.OUT=p4out;bridge.progress=progress
    bridge.tabm()
    write(p4out/'COMPLETE.json',dict(status='PASS',task='tabm',training=False,new_forward=False,outputs_sha256={p.name:sha(p) for p in p4out.iterdir() if p.is_file()}))
    write(HERE/'COMPLETE.json',dict(status='PASS',p3_complete=True,p4_complete=True,original_bitwise_gate_retained=True,training=False,new_forward=False));progress('COMPLETE',2,2)
if __name__=='__main__':
    try:main()
    except Exception as e:
        if CREATED:write(HERE/'STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()))
        raise
