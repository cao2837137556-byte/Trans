"""Read-only FIT coverage / attack-tail audit from sealed source pilot arrays."""
import argparse,gc,gzip,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
import psutil
import torch
import coverage_core as cc
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];PILOT=ROOT/'runs/source_risk_preservation_pilot_v2_20261106'
sys.path.insert(0,str(PILOT))
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
pw=module('sealed_source_pilot',PILOT/'worker.py');k=pw.k;c=pw.c
PHASE='PREFLIGHT';PEAK=0
def write(name,value):c.write(HERE/name,value,replace=True)
class Progress:
    stage='LOAD_SOURCE';last=0
    def tick(self,done,total):
        global PEAK
        now=time.monotonic()
        if now-self.last<2 and done!=total:return
        self.last=now;PEAK=max(PEAK,psutil.Process().memory_info().rss);assert PEAK<7*2**30
        write(PHASE+'_PROGRESS.json',dict(stage=self.stage,done=int(done),total=int(total),rss_mib=PEAK/2**20,updated_unix=time.time()))
LEVELS={'device':['device'],'activity':['device','activity'],'semantic':['device','activity','protocol'],'leaf':['device','activity','capture_id','session_id','protocol']}
def stash(details,name,value):
    if PHASE!='COVERAGE':return
    path=HERE/(name+'.json.gz')
    with gzip.open(path,'wt',encoding='utf8',compresslevel=1) as f:json.dump(value,f,allow_nan=False)
    details[name]=dict(path=str(path),sha256=c.sha(path),bytes=path.stat().st_size)
def audit(p,small):
    begun=time.monotonic();data=pw.parent.load(p,False);receipt=c.read(PILOT/'PILOT_RESULT.json')
    rr={role:[data['rows'][int(i)] for i in data[role]] for role in ['fit','cal']}
    labels={role:np.array([r['label'] for r in rows]) for role,rows in rr.items()}
    weights={role:np.zeros(len(rows)) for role,rows in rr.items()}
    for role in rr:
        for y in (0,1):
            ix=np.flatnonzero(labels[role]==y);weights[role][ix]=.5*k.class_weights([rr[role][i] for i in ix])
    cache={role:{lev:cc.groups(rows,fields) for lev,fields in LEVELS.items()} for role,rows in rr.items()}
    out=dict(scope='SOURCE_FIT_COVERAGE_PRIMARY_CAL_SEMANTIC_COMPARISON_DESCRIPTIVE',heads={},counterfactual_training=False)
    seeds=[27] if small else [27,127,227];details={};ensemble={role:{name:[] for name in ['baseline','candidate','baseline_zero','candidate_zero']} for role in rr}
    selections=None
    for seed in seeds:
        p.stage='LOAD_SEALED_SOURCE_'+str(seed);p.tick(0,1)
        head=receipt['heads'][str(seed)];folder=PILOT/'heads'/str(seed);c.verify(folder)
        c.pin(folder/'head.npz',head['head_sha256'])
        identity=np.load(c.pin(folder/'sample_identity.npz',head['sample_identity_sha256']),allow_pickle=False)
        ix=identity['fit_local_index'];assert identity['uid'].tolist()==[rr['fit'][i]['uid'] for i in ix]
        assert np.array_equal(identity['weights'],pw.r.batch_weights(data['w'][ix],labels['fit'][ix])),'PILOT_WEIGHT_PARITY'
        mask=np.zeros(len(rr['fit']),bool);mask[ix]=True
        assert np.array_equal(ix,pw.r.sample(labels['fit'])) and mask.sum()==16384
        if selections is None:selections=cc.proposed_samples(labels['fit'],weights['fit'],mask) if not small else {'ACTUAL_8192_EACH':mask}
        else:assert np.array_equal(mask,selections['ACTUAL_8192_EACH'])
        arrays={}
        for role in rr:
            info=head['arrays'][role]
            with np.load(c.pin(info['path'],info['sha256']),allow_pickle=False) as a:
                assert a['uid'].tolist()==[r['uid'] for r in rr[role]]
                arrays[role]={n:a[n].copy() for n in ensemble[role]}
                for n in ensemble[role]:ensemble[role][n].append(arrays[role][n])
            # Independently recover accepted actual decision counts / score-tail quantile.
            a=arrays[role]
            for y,name in [(0,'normal'),(1,'attack')]:
                take=labels[role]==y;expected=head['metrics'][role][name]
                assert int((a['candidate'][take]>head['cut']).sum())==expected['candidate_alarms']
                assert abs(float(np.quantile((a['candidate'][take]-a['baseline'][take])/head['scale'],.01))-expected['standardized_score_change']['p01'])<1e-8
        out['heads'][str(seed)]=analyze(str(seed),arrays,rr,labels,weights,cache,selections,head['cut'],head['scale'],head['normal_upper'],details,p)
        del arrays;gc.collect()
    if not small:
        means={role:{name:pw.parent.onboarding.ordered_ensemble(dict(zip(seeds,values))) for name,values in columns.items()} for role,columns in ensemble.items()}
        cut=receipt['ensemble']['cut'];scale=sum(h['scale'] for h in receipt['heads'].values())/3;upper=sum(h['normal_upper'] for h in receipt['heads'].values())/3
        out['heads']['ensemble']=analyze('ensemble',means,rr,labels,weights,cache,selections,cut,scale,upper,details,p)
        path=HERE/'ALL_STRATA.json.gz'
        with gzip.open(path,'wt',encoding='utf8') as f:json.dump(details,f,allow_nan=False)
        out['large_details']=dict(path=str(path),sha256=c.sha(path),bytes=path.stat().st_size)
        path=HERE/'FIT_MEMBERSHIP_COUNTERFACTUALS.npz';c.save_arrays(path,uid=np.asarray([r['uid'] for r in rr['fit']]),**selections)
        out['memberships']=dict(path=str(path),sha256=c.sha(path),bytes=path.stat().st_size)
    out['seconds']=time.monotonic()-begun;return out

def analyze(name,arrays,rows,labels,weights,cache,selections,cut,scale,upper,details,p):
    result={'fit':{},'cal_descriptive':{}};actual=None
    for mode,selected in selections.items():
        result['fit'][mode]={}
        for lev,(keys,ids) in cache['fit'].items():
            p.stage=name+'_'+mode+'_'+lev;p.tick(0,1)
            a=arrays['fit'];v=cc.summarize(keys,ids,labels['fit'],weights['fit'],selected,a['baseline'],a['candidate'],a['baseline_zero'],a['candidate_zero'],cut,scale,upper)
            result['fit'][mode][lev]={label:values['summary'] for label,values in v.items()}
            stash(details,name+'_'+mode+'_'+lev,v)
            if mode=='ACTUAL_8192_EACH' and lev=='semantic':actual=v
            p.tick(1,1)
    # CAL is only compared with FIT semantic strata; never match capture/session IDs across splits.
    keys,ids=cache['cal']['semantic'];a=arrays['cal'];selected=np.zeros(len(rows['cal']),bool)
    v=cc.summarize(keys,ids,labels['cal'],weights['cal'],selected,a['baseline'],a['candidate'],a['baseline_zero'],a['candidate_zero'],cut,scale,upper)
    for label in ['normal','attack']:
        lookup={tuple(r['key']):r for r in actual[label]['records']};records=[]
        for item in v[label]['records']:
            match=lookup.get(tuple(item['key']));records.append(dict(cal=item,fit=match,source_support='SEMANTIC_STRATUM_PRESENT' if match else 'NO_FIT_SEMANTIC_STRATUM'))
        # Ranking is display-only; cannot influence membership counterfactuals constructed above.
        field='residual_alarm_mass' if label=='normal' else 'objective_risk_mass'
        result['cal_descriptive'][label]=dict(top20=sorted(records,key=lambda x:-x['cal'][field])[:20],
            risk_mass_no_FIT_semantic_support=sum(x['cal'][field] for x in records if x['fit'] is None),
            risk_mass_FIT_present_but_not_sampled=sum(x['cal'][field] for x in records if x['fit'] is not None and x['fit']['pilot_rows']==0),
            warning='Semantic support is not feature-distribution equivalence; CAL never enters selection or gradients')
        stash(details,name+'_CAL_'+label,records)
    return result

def main():
    start=time.monotonic();p=Progress()
    for n,h in c.read(HERE/'.private.json')['pins'].items():c.pin(HERE/n,h)
    for n,h in c.read(HERE/'INPUT_PINS.json').items():c.pin(ROOT/n,h)
    import test_coverage;test_coverage.main(HERE/'LINUX_REGRESSION.json')
    torch.set_num_threads(1);torch.use_deterministic_algorithms(True)
    if PHASE=='PREFLIGHT':
        old=ROOT/'runs/fusion_score_anchor_v2_20261105';sys.path.insert(0,str(old));aw=module('engineering_replay',old/'worker.py');aw.HERE=HERE
        decode=aw.decode(p);gc.collect()
        small=audit(p,True);forecast=2*12*small['seconds']+120;assert forecast<=3600,'COVERAGE_BUDGET'
        write('RUNTIME_FORECAST.json',dict(audit_seconds=forecast,budget_seconds=3600))
        result=dict(status='PASS',engineering=decode,source_preflight=small,forecast_seconds=forecast)
    else:
        torch.set_num_interop_threads(1);assert c.read(HERE/'PREFLIGHT_RESULT.json')['status']=='PASS'
        result=dict(status='PASS',coverage=audit(p,False))
    result.update(phase=PHASE,seconds=time.monotonic()-start,rss_peak_bytes=PEAK,optimizer_updates=0,new_models=0,
                  external_candidate_scoring=False,CAL_used_for_sampling=False,threshold_refit=False,parameter_gradients_measured=False)
    write(PHASE+'_RESULT.json',result);p.stage=PHASE+'_COMPLETE';p.tick(1,1)
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--phase',choices=['PREFLIGHT','COVERAGE'],required=True);PHASE=parser.parse_args().phase
    try:main()
    except BaseException as e:write(PHASE+'_STOP.json',dict(status='STOP',error=repr(e),traceback=traceback.format_exc()));raise
