"""Evaluation-only repair. Frozen training inputs and checkpoints are read-only."""
import os,sys,time,traceback
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
sys.path.insert(0,str(OLD))
import formal as f
import pipeline_parent as p
# Required before torch.load unpickles algorithms.slad.SLAD in a clean process.
sys.path.insert(0,str(OLD/'vendor/slad'))

def main():
    os.environ['BASELINE_METHOD']='SLAD';f.setup(27)
    for n,h in p.read(HERE/'PARENT_PINS.json').items():assert p.sha(OLD/n)==h,'PARENT_SHA:'+n
    for n,h in p.read(HERE/'.private.json')['pins'].items():assert p.sha(HERE/n)==h,'PACKAGE_SHA:'+n
    p.HERE=HERE;f.HERE=HERE
    p.progress('REPAIR_REAL_PIPELINE');result=p.pipeline();assert result['status']=='PASS';p.write('PIPELINE_RESULT.json',result)
    src=OLD/'artifacts/evaluation';out=HERE/'artifacts/evaluation';out.mkdir(parents=True,exist_ok=True)
    spec=p.read(OLD/'EVALUATION_INPUTS.json')
    for pool,v in spec['pools'].items():
        for suffix,key in [('_X.npy','x_sha256'),('_ROWS.json','rows_sha256')]:
            a=src/(pool+suffix);assert p.sha(a)==v[key];(out/a.name).symlink_to(a)
        if pool!='EDGE':(out/(pool+'_VIEWS.npz')).symlink_to(src/(pool+'_VIEWS.npz'))
    p.write('EVALUATION_INPUTS.json',spec)
    gate={}
    import numpy as np,torch
    for seed in [27,127,227]:
        receipt=p.read(OLD/('train_SLAD_'+str(seed)+'_RESULT.json'));assert receipt['status']=='PASS' and receipt['epochs']==100
        source=OLD/'artifacts/SLAD'/str(seed)/'checkpoint.pt';assert p.sha(source)==receipt['checkpoint_sha256']
        dest=HERE/'artifacts/SLAD'/str(seed);dest.mkdir(parents=True,exist_ok=True);(dest/'checkpoint.pt').symlink_to(source)
        fn=f.predictor('SLAD',seed);x=np.load(out/'CAL_X.npy',mmap_mode='r')[:32].copy()
        with torch.inference_mode():scores=np.asarray(fn(x));again=np.asarray(f.predictor('SLAD',seed)(x))
        assert scores.shape==(32,) and np.isfinite(scores).all() and np.array_equal(scores,again)
        gate[str(seed)]=dict(checkpoint_sha256=receipt['checkpoint_sha256'],rows=32,reload_scores_exact=True)
    p.write('CLEAN_PREDICTOR_GATE.json',dict(status='PASS',seeds=gate,trained_again=False))
    p.progress('SLAD_REPAIRED_EVALUATION');r=f.evaluate('SLAD');p.write('EVALUATE_RESULT.json',r)
    for seed,v in gate.items():assert p.sha(OLD/'artifacts/SLAD'/seed/'checkpoint.pt')==v['checkpoint_sha256']
    p.write('COMPLETE.json',dict(status='PASS',trained_again=False,main_model_changed=False))

if __name__=='__main__':
    t=time.monotonic()
    try:main()
    except Exception as e:
        p.HERE=HERE;p.write('STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc(),seconds=time.monotonic()-t));raise
