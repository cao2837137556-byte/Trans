"""Single preregistered source-score anchor; existing runtime and FIT/CAL roles."""
import argparse,gc,hashlib,importlib.util,json,math,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
import torch
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent/'device_context_head_training_v2_20261105'
EVAL=HERE.parent/'device_context_evaluation_v1_20261105';PHASE='DECODE_PREFLIGHT'
sys.path.append(str(PARENT))
import context_core as k
import anchor_train
c=k.c
spec=importlib.util.spec_from_file_location('parent_training_worker',PARENT/'worker.py');parent=importlib.util.module_from_spec(spec);spec.loader.exec_module(parent)
def write(n,v):c.write(HERE/n,v,replace=True)
class Progress:
    stage='LOAD_SOURCE';optimizer_updates=0;peak=0;last=0
    def tick(self,done,total):
        now=time.monotonic()
        if now-self.last<2 and done!=total:return
        self.last=now;self.peak=max(self.peak,psutil.Process().memory_info().rss)
        assert self.peak<7*2**30,'MEMORY_LIMIT'
        write(PHASE+'_PROGRESS.json',dict(stage=self.stage,done=int(done),total=int(total),optimizer_updates=self.optimizer_updates,rss_mib=self.peak/2**20,updated_unix=time.time()))
def verify():
    for n,h in c.read(HERE/'.private.json')['pins'].items():c.pin(HERE/n,h)
    for n,h in c.read(HERE/'PARENT_PINS.json').items():c.pin(PARENT/n,h)
    accepted=c.read(HERE/'TRAINING_ACCEPTANCE.json')
    assert accepted['result']=='PASS' and accepted['new_heads']==9
    for n,h in accepted['receipt_sha256'].items():c.pin(PARENT/n,h)
    assert c.read(HERE/'SPEC.json')['anchor_lambda']==1.0

def teacher(data,seed):
    result=c.read(PARENT/f'TRAIN_REFIT782_{seed}_RESULT.json');folder=PARENT/'heads'/f'REFIT782_{seed}'
    path=c.pin(folder/'calibration/fit_logits.npy',result['calibration']['logits_sha256']['fit']);targets=np.load(path)
    assert targets.shape==(len(data['fit']),) and targets.dtype==np.float32
    model=k.classifier(seed,782);saved=np.load(c.pin(folder/'train/head.npz',result['head_sha256']))
    model.load_state_dict({n:torch.from_numpy(saved[n].copy()) for n in saved.files});model.eval().requires_grad_(False)
    actual=k.scores(model,data['values'],data['q'],data['fit'][:1024],data['norm'],782)
    assert np.array_equal(actual,targets[:1024]),'TEACHER_FIT_READBACK'
    endpoint=c.read(c.pin(folder/'train/endpoint.json',result['endpoint_sha256']))
    assert endpoint['uid_sha256']==data['spec']['data_identity']['FIT']['uid_sha256']
    return targets,result['calibration']['scale']

def one(data,seed,progress,gate):
    start=time.monotonic();targets,scale=teacher(data,seed)
    folder=HERE/('runtime_smoke' if gate else 'heads')/f'ANCHOR790_{seed}';folder.mkdir(parents=True,exist_ok=False)
    design=dict(training=data['spec']['training']['parent_recipe'],source_score_anchor=c.read(HERE/'SPEC.json'))
    model=anchor_train.train(design,data['rows'],data['values'],data['q'],data['norm'],data['fit'],data['stages'],'FUSION790',seed,folder/'train',progress,runtime_batches=128 if gate else None,teacher_scores=targets,teacher_scale=scale)
    endpoint=c.read(folder/'train/endpoint.json')
    cal=parent.calibration(model,data,'FUSION790',folder/'calibration',progress)
    result=dict(status='PASS',arm='ANCHOR790',seed=seed,epochs=endpoint['epochs'],updates=endpoint['updates'],runtime_gate_only=gate,calibration=cal,teacher_scale=scale,scale_ratio=cal['scale']/scale,head_sha256=endpoint['head_sha256'],endpoint_sha256=c.sha(folder/'train/endpoint.json'),seconds=time.monotonic()-start,profile=endpoint['profile'],epoch_checkpoints=len(list((folder/'train').glob('epoch_*_head.npz'))),rss_peak_bytes=progress.peak)
    if gate:
        profile=endpoint['profile'][0]
        # batch_seconds includes epoch checkpoint and source probe: multiplying by all batches is conservative.
        estimate=40*(profile['tail_seconds']+2414*profile['batch_seconds']/128)
        result['forecast_seconds']=1.5*(estimate+data['load_seconds']+cal['seconds']+max(0,result['seconds']-profile['tail_seconds']-profile['batch_seconds']-cal['seconds']))+30
    c.write(folder/'RESULT.json',result);del model;gc.collect();return result

def ensemble(data,gate):
    folder=HERE/('runtime_smoke' if gate else 'heads');values=[]
    for seed in [27,127,227]:
        p=folder/f'ANCHOR790_{seed}';r=c.read(p/'RESULT.json');values.append(np.load(c.pin(p/'calibration/cal_logits.npy',r['calibration']['logits_sha256']['cal'])))
    logits=parent.onboarding.ordered_ensemble(dict(zip([27,127,227],values)))
    rows=[data['rows'][int(i)] for i in data['cal']];normal=np.asarray([r['label']==0 for r in rows]);nr=[r for r in rows if r['label']==0]
    cut=k.threshold(logits[normal],nr,.01);w=k.class_weights(nr);fpr=math.fsum(w[logits[normal]>cut]);assert fpr<=.01+1e-14
    return dict(status='PASS',cut=cut,weighted_normal_fpr=fpr,unweighted_normal_fpr=float((logits[normal]>cut).mean()),normal_rows=len(nr),seeds=[27,127,227],comparison='>',runtime_gate_only=gate)

def decode(progress):
    sys.path.insert(0,str(EVAL));import common,inputs,preflight_encoder,edge_context
    common.verify()
    def report(stage,done=0,total=1,**kwargs):progress.stage=stage;progress.tick(done,total)
    common.progress=inputs.progress=preflight_encoder.progress=edge_context.progress=report
    _,norm,arms=common.models();data=inputs.edge()
    result=preflight_encoder.run(data,norm)
    # Verify selected real cached queries pass through all original heads and C5, with metric receipt.
    chosen={}
    for i,r in enumerate(data['rows']):chosen.setdefault((r['source_role'],r['protocol']),i)
    ix=np.asarray(sorted(chosen.values()));all_ix,ctx=edge_context.join(data['rows']);assert np.array_equal(all_ix,np.arange(60000))
    import metrics
    rows=[data['rows'][i] for i in ix];pred={}
    for r in rows:r.setdefault('scenario',r['source_role'])
    for name,a in arms.items():
        raw=common.score(k,norm,a,data['z'][ix],data['q'][ix],ctx[ix]);pred[name]={'RAW':common.four(raw)>a['cuts']}
        if name!='STATS8':pred[name]['C5_P3']=common.four(common.correction(raw,data['support'][ix],data['q'][ix],a['scales']))>a['cuts']
    report_metrics=metrics.summarize(rows,pred,{'primary':(np.arange(len(rows)),np.ones(len(rows)))})
    write('DECODE_METRICS_ENGINEERING_ONLY.json',report_metrics)
    return dict(status='PASS',real_encoder_distance=result,evaluation_receipt_sha256=c.sha(HERE/'DECODE_METRICS_ENGINEERING_ONLY.json'),external_scores_used_for_fitting=False)

def main():
    start=time.monotonic();torch.set_num_threads(1);torch.set_num_interop_threads(1);torch.use_deterministic_algorithms(True)
    verify();progress=Progress()
    if PHASE=='DECODE_PREFLIGHT':result=decode(progress)
    else:
        assert c.read(HERE/'DECODE_PREFLIGHT_RESULT.json')['status']=='PASS'
        if PHASE!='TRAIN_PREFLIGHT':assert c.read(HERE/'TRAIN_PREFLIGHT_RESULT.json')['status']=='PASS'
        if PHASE=='TRAIN_PREFLIGHT':
            import test_anchor;test_anchor.main()
            (HERE/'LINUX_REGRESSION.json').write_bytes((HERE/'LOCAL_REGRESSION.json').read_bytes())
        data=parent.load(progress,False)
        if PHASE=='TRAIN_PREFLIGHT':
            heads={str(seed):one(data,seed,progress,True) for seed in [27,127,227]};ens=ensemble(data,True)
            forecasts={seed:r['forecast_seconds'] for seed,r in heads.items()};write('RUNTIME_FORECAST.json',dict(forecasts=forecasts,budget_seconds=3600))
            assert max(forecasts.values())<=3600,'SOURCE_ANCHOR_RUNTIME_BUDGET'
            result=dict(status='PASS',runtime_gate_only=True,heads=heads,ensemble=ens,forecasts=forecasts)
        elif PHASE=='CALIBRATION':result=dict(status='PASS',ensemble=ensemble(data,False),new_heads=3,evaluation_pending=True)
        else:
            result=one(data,int(PHASE.split('_')[1]),progress,False)
            assert result['updates']==96560 and result['epoch_checkpoints']==40
    result.update(seconds=time.monotonic()-start,rss_peak_bytes=progress.peak,external_data_used_for_training=False)
    write(PHASE+'_RESULT.json',result);progress.stage=PHASE+'_COMPLETE';progress.tick(1,1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',required=True,choices=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','TRAIN_27','TRAIN_127','TRAIN_227','CALIBRATION']);PHASE=parser.parse_args().phase
    try:main()
    except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
