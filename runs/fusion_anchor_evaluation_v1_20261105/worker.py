"""Frozen five-arm evaluation. No fitting, selection, or modification of parent assets."""
import argparse,gc,hashlib,json,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
HERE=Path(__file__).resolve().parent;EVAL=HERE.parent/'device_context_evaluation_v1_20261105'
TRAIN=HERE.parent/'fusion_score_anchor_v2_20261105';PHASE='PREFLIGHT';PEAK=0
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(n,v):
    p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done=0,total=1,**kw):
    global PEAK
    PEAK=max(PEAK,psutil.Process().memory_info().rss);assert PEAK<7*1024**3,'MEMORY_LIMIT'
    write(PHASE+'_PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_mib=PEAK/2**20,updated_unix=time.time(),**kw))
def initialize():
    for n,h in read(HERE/'.private.json')['pins'].items():assert sha(HERE/n)==h,'DELIVERY:'+n
    for n,h in read(HERE/'PARENT_PINS.json').items():assert sha(EVAL/n)==h,'PARENT:'+n
    for n,h in read(HERE/'REMOTE_TRAINING_PINS.json').items():assert sha(TRAIN/n)==h,'TRAIN_RECEIPT:'+n
    a=read(HERE/'TRAINING_ACCEPTANCE.json');assert a['result']=='PASS' and a['scope']=='TRAINING_AND_SOURCE_CALIBRATION_ONLY'
    sys.path.insert(0,str(EVAL));import common as c
    c.verify();c.progress=progress
    import inputs,edge_context,metrics,reporting
    inputs.progress=edge_context.progress=progress
    k,norm,arms=c.models()
    import torch
    nets=[];cuts=[];scales=[]
    for seed in [27,127,227]:
        result=read(TRAIN/f'TRAIN_{seed}_RESULT.json');h=a['heads'][str(seed)]
        assert result['epochs']==40 and result['updates']==96560 and result['epoch_checkpoints']==40 and not result['runtime_gate_only']
        assert result['head_sha256']==h['head_sha256'] and result['calibration']['cut']==h['cut'] and result['calibration']['scale']==h['scale']
        path=c.pin(TRAIN/'heads'/f'ANCHOR790_{seed}'/'train/head.npz',h['head_sha256'])
        model=k.classifier(seed,790)
        with np.load(path,allow_pickle=False) as saved:model.load_state_dict({n:torch.from_numpy(saved[n].copy()) for n in saved.files})
        model.eval().requires_grad_(False);nets.append(model);cuts.append(h['cut']);scales.append(h['scale'])
    assert read(TRAIN/'CALIBRATION_RESULT.json')['ensemble']==a['ensemble']
    arms['ANCHOR790']=dict(models=nets,dimension=790,cuts=np.asarray(cuts+[a['ensemble']['cut']]),scales=np.asarray(scales))
    assert list(arms)==['OLD782','REFIT782','STATS8','FUSION790','ANCHOR790']
    return c,k,norm,arms,inputs,edge_context,metrics,reporting

def baseline_check(saved_uids,uids,saved,scores,arms,ix=None):
    assert saved_uids==uids,'BASELINE_UID_ORDER'
    errors={}
    for arm in ['OLD782','REFIT782','STATS8','FUSION790']:
        for method,actual in scores[arm].items():
            expected=saved[arm+'_'+method]
            if ix is not None:expected=expected[ix]
            assert actual.shape==expected.shape,'BASELINE_SHAPE'
            err=float(np.max(np.abs(actual-expected)));assert err<=.002,'BASELINE_SCORE:'+arm+method
            assert np.array_equal(actual>arms[arm]['cuts'],expected>arms[arm]['cuts']),'BASELINE_DECISIONS:'+arm+method
            errors[arm+'_'+method]=err
    return errors

def candidate_gates(report,metrics):
    original=report['primary']
    mapped={'primary':{'OLD782':original['OLD782'],'FUSION790':original['ANCHOR790']}}
    result=metrics.gates(mapped);result['evaluated_candidate']='ANCHOR790';result['legacy_function_alias_only']='FUSION790'
    return result

def load(pool,c,inputs,context,small=False):
    data=inputs.edge() if pool=='EDGE' else inputs.ab(pool)
    for r in data['rows']:
        r.setdefault('scenario',r.get('activity',r.get('source_role','UNKNOWN')))
        r.setdefault('source_role','NORMAL' if r['label']==0 else r['scenario'])
    if pool=='EDGE':
        ix,data['context']=context.join(data['rows']);assert np.array_equal(ix,np.arange(60000))
    receipt=read(EVAL/('EDGE_RESULT.json' if pool=='EDGE' else 'AB_RESULT.json'))
    scores=receipt['scores'] if pool=='EDGE' else receipt['pools'][pool]['scores']
    assert sha(scores['path'])==scores['sha256'],'BASELINE_ARRAY_SHA'
    saved=np.load(scores['path'],allow_pickle=False);uids=[r['uid'] for r in data['rows']]
    assert saved['uid'].tolist()==uids,'BASELINE_UID_ORDER'
    ix=None
    if small:
        chosen={}
        for i,r in sorted(enumerate(data['rows']),key=lambda pair:pair[1]['uid']):chosen.setdefault((r['device'],r['protocol'],r['label'],r['source_role']),i)
        ix=np.asarray(sorted(chosen.values()))
        data={n:([v[i] for i in ix] if n=='rows' else v[ix]) for n,v in data.items() if n in ['rows','z','q','context','support']}
        data['views']={'primary':(np.arange(len(ix)),np.ones(len(ix)))}
    return data,saved,uids,ix

def forward(data,c,k,norm,arms,metrics):
    pred={};scores={};margins={};n=len(data['rows'])
    for name,a in arms.items():
        progress('MODEL_FORWARD_'+name,0,n)
        raw=c.score(k,norm,a,data['z'],data['q'],data['context']);full=c.four(raw)
        assert full.shape==(n,4) and np.isfinite(full).all()
        scores[name]={'RAW':full};pred[name]={'RAW':full>a['cuts']}
        if name!='STATS8':
            corrected=c.four(c.correction(raw,data['support'],data['q'],a['scales']))
            assert np.isfinite(corrected).all() and np.all(corrected<=full+1e-12)
            scores[name]['C5_P3']=corrected;pred[name]['C5_P3']=corrected>a['cuts']
            keep=data['views']['primary'][0] if 'views' in data else np.arange(n)
            margins[name]=metrics.margins(data['rows'],full,corrected,a['cuts'],a['scales'],keep)
    return pred,scores,margins

def seed_errors(data,pred):
    ix=data['views']['primary'][0] if 'views' in data else np.arange(len(data['rows']))
    normal=np.asarray([data['rows'][int(i)]['label']==0 for i in ix]);out={}
    for name,pp in pred.items():
        out[name]={}
        for method,values in pp.items():
            v=values[ix][normal,:3]
            out[name][method]=dict(normal_rows=len(v),seed_fp_counts=v.sum(0).tolist(),ensemble_fp_count=int(values[ix][normal,3].sum()),three_seed_intersection=int(v.all(1).sum()),three_seed_union=int(v.any(1).sum()),seed_disagreement_rows=int((v.any(1)&~v.all(1)).sum()))
    return out
def save_scores(pool,data,scores):
    p=HERE/(pool+'_SCORES.npz');np.savez(p,uid=np.asarray([r['uid'] for r in data['rows']]),**{a+'_'+m:v for a,methods in scores.items() for m,v in methods.items()})
    return dict(path=str(p),sha256=sha(p),bytes=p.stat().st_size)

def main():
    start=time.monotonic();c,k,norm,arms,inputs,context,metrics,reporting=initialize();progress('IDENTITY_VERIFIED')
    if PHASE!='PREFLIGHT':assert read(HERE/'PREFLIGHT_RESULT.json')['status']=='PASS','REAL_CHAIN_REQUIRED'
    if PHASE=='PREFLIGHT':
        # FrozenBackend is sole owner of interop initialization in this process.
        import preflight_encoder
        preflight_encoder.progress=progress
        data=inputs.edge();encoder=preflight_encoder.run(data,norm);del data;gc.collect()
        checks={}
        for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
            d,saved,uids,ix=load(pool,c,inputs,context,True)
            pred,scores,margins=forward(d,c,k,norm,arms,metrics)
            errors=baseline_check(saved['uid'].tolist(),uids,saved,scores,arms,ix)
            m=metrics.summarize(d['rows'],pred,d['views']);gate=candidate_gates(m,metrics)
            write(pool+'_SMALL_ENGINEERING_METRICS.json',m)
            checks[pool]=dict(rows=len(d['rows']),baseline_errors=errors,metric_receipt_sha256=sha(HERE/(pool+'_SMALL_ENGINEERING_METRICS.json')),candidate_gates_computed=True,scientific_selection=False)
            saved.close();del d,pred,scores,margins,m;gc.collect()
        result=dict(status='PASS',real_encoder_distance=encoder,checks=checks,scope='REAL_ENGINEERING_GATE_ONLY')
    elif PHASE=='AB':
        result=dict(status='PASS',pools={})
        for pool in ['CIC_DEV','UNSW_DEV']:
            d,saved,uids,ix=load(pool,c,inputs,context);pred,scores,margins=forward(d,c,k,norm,arms,metrics)
            errors=baseline_check(saved['uid'].tolist(),uids,saved,scores,arms)
            m=metrics.summarize(d['rows'],pred,d['views']);write(pool+'_METRICS.json',m);write(pool+'_MARGINS.json',margins)
            result['pools'][pool]=dict(rows=len(d['rows']),primary_rows=len(d['views']['primary'][0]),baseline_errors=errors,primary=m['primary'],candidate_gates=candidate_gates(m,metrics),margins=margins,seed_errors=seed_errors(d,pred),full_metrics_sha256=sha(HERE/(pool+'_METRICS.json')),scores=save_scores(pool,d,scores))
            saved.close();del d,pred,scores,margins,m;gc.collect()
    else:
        d,saved,uids,ix=load('EDGE',c,inputs,context);pred,scores,margins=forward(d,c,k,norm,arms,metrics)
        errors=baseline_check(saved['uid'].tolist(),uids,saved,scores,arms)
        population=read(c.ROOT/'runs/edge_formal_execution_v4_20261104/POPULATION_TEMPORAL_CENSUS.json');reports={}
        for name,pp in pred.items():
            r=reporting.summarise(d['rows'],pp,population=population,prediction_uids={m:[r['uid'] for r in d['rows']] for m in pp},raw_name='RAW',independent_methods=())
            write(name+'_EDGE_METRICS.json',r);r.pop('ordered_query_uids',None);reports[name]=r
        write('EDGE_MARGINS.json',margins)
        result=dict(status='PASS',rows=len(d['rows']),arms=reports,margins=margins,baseline_errors=errors,seed_errors=seed_errors(d,pred),scores=save_scores('EDGE',d,scores))
        saved.close()
    result.update(seconds=time.monotonic()-start,rss_peak_bytes=PEAK,phase=PHASE,training=False,threshold_fitting=False,model_selection=False,scientific_failures_stop_chain=False,interpretation='Consumed diagnostic evaluation; all fixed seeds/arms; original gates retained')
    write(PHASE+'_RESULT.json',result);write(PHASE+'_PINS.json',c.PINS);progress(PHASE+'_COMPLETE',1,1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['PREFLIGHT','AB','EDGE'],required=True);PHASE=parser.parse_args().phase
    try:main()
    except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
