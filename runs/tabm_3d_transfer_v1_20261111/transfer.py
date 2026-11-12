"""Five fixed rows, source-only native-score scaling; no optimizer or selection."""
import gc,gzip,hashlib,importlib.util,json,os,sys,time,traceback,csv
from pathlib import Path
import numpy as np
import analysis_core as ac
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];OUT=HERE/'results';ART=HERE/'artifacts'
TABM=ROOT/'runs/baseline_remaining_three_v2_20261108';AB=ROOT/'runs/paper_reading_ablations_v2_20261111';STARTED=False
HEADS=['27','127','227','ensemble'];NAMES=['MLP-RAW','MLP-3D-SELF','TabM-RAW','TabM-3D-SELF','FROZEN-MAIN']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(name,obj):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(obj,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');tmp.replace(p)
def progress(stage,done=0,total=1,**kw):
    import psutil
    rss=psutil.Process().memory_info().rss;assert rss<14*1024**3,'HOST_MEMORY_HEADROOM'
    write('PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),rss_bytes=rss,updated_unix=time.time(),**kw))
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def equal(a,b,path=''):
    if isinstance(a,dict):
        assert isinstance(b,dict) and set(a)==set(b),'METRIC_KEYS:'+path
        for k in a:equal(a[k],b[k],path+'/'+k)
    elif isinstance(a,list):
        assert isinstance(b,list) and len(a)==len(b),'METRIC_LIST:'+path
        for i,(x,y) in enumerate(zip(a,b)):equal(x,y,path+'/'+str(i))
    elif isinstance(a,(float,int)) and not isinstance(a,bool):assert isinstance(b,(float,int)) and abs(a-b)<=2e-10,'METRIC_VALUE:'+path
    else:assert a==b,'METRIC_VALUE:'+path
def table(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (OUT/name).open('w',encoding='utf8',newline='') as f:
        wr=csv.DictWriter(f,keys);wr.writeheader();wr.writerows(rows)

def initialize():
    for n,h in read(HERE/'PACKAGE_MANIFEST.json')['files'].items():assert sha(HERE/n)==h,'PACKAGE_SHA:'+n
    for n,h in read(HERE/'INPUT_PINS.json').items():assert sha(ROOT/n)==h,'DEPENDENCY_SHA:'+n
    w=load('fixed_tabm_worker',TABM/'worker.py');w.init(27)
    import torch
    assert torch.cuda.is_available() and torch.cuda.get_device_name()=='NVIDIA GeForce RTX 4090','SAME_GPU_REQUIRED'
    b=load('frozen_geometry_audit',AB/'run.py');b.OUT=OUT/'frozen_audit';b.OUT.mkdir();b.progress=progress
    c,inputs,reporting,freeze=b.bootstrap()
    # Actual decode/encode/distance slice, isolated from all frozen outputs.
    p=w.p;p.HERE=ART/'real_chain';p.HERE.mkdir(parents=True);p.progress=progress
    progress('REAL_PIPELINE_PREFLIGHT');t=time.monotonic();chain=p.pipeline();assert chain['status']=='PASS';chain['wall_seconds']=time.monotonic()-t;write('REAL_PIPELINE.json',chain)
    c.progress=inputs.progress=progress
    loaded,mlp_cuts,old_scales=b.prepare(c,inputs,reporting,freeze)
    torch.set_num_threads(8)
    import context_core as k,constrained_onboarding_core_v3 as geometry,metrics
    return w,b,c,inputs,reporting,freeze,loaded,mlp_cuts,old_scales,k,geometry,metrics

def source_assets(c,inputs,k,geometry,freeze):
    progress('SOURCE_FIT_IDENTITY_AND_WEIGHTS')
    rows,z,q,ctx=inputs.source_role('LEARN');fit=np.load(c.SOURCE/'metadata/FIT.npy');rr=[rows[int(i)] for i in fit]
    training=read(c.TRAIN/'TRAINING_SPEC_FROZEN.json');uid=k.c.uid_sha(r['uid'] for r in rr);assert uid==training['data_identity']['FIT']['uid_sha256'] and len(rr)==617908
    labels=np.asarray([r['label'] for r in rr]);weight=k.weights(rr)
    assert hashlib.sha256(weight.tobytes()).hexdigest()=='a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de'
    assert all(abs(weight[labels==v].sum()-.5)<1e-12 for v in [0,1])
    source=ROOT/'runs/baseline_training_readiness_v6_20261107';spec=read(source/'SOURCE_RESULT.json');xp=source/'artifacts/source/FIT_X.npy';yp=xp.with_name('FIT_y.npy')
    assert sha(xp)==spec['sha256'][xp.name] and sha(yp)==spec['sha256'][yp.name];assert np.array_equal(np.load(yp),labels)
    x=np.load(xp,mmap_mode='r');assert x.shape==(617908,790) and x.dtype==np.float32
    np.save(ART/'FIT_WEIGHTS.npy',weight)
    mlp=[]
    for seed in HEADS[:3]:
        folder=c.TRAIN/'heads'/('FUSION790_'+seed)/'calibration';r=read(folder/'RESULT.json');fp=folder/'fit_logits.npy';assert sha(fp)==r['logits_sha256']['fit']
        score=np.load(fp,mmap_mode='r');assert score.shape==(len(rr),)
        lo=geometry.weighted_quantile(score,weight,.1);hi=geometry.weighted_quantile(score,weight,.9)
        assert lo==r['q10'] and hi==r['q90'] and hi-lo==r['scale']==freeze['heads'][seed]['scale']
        mlp.append(dict(seed=seed,q10=lo,q90=hi,scale=hi-lo,fit_scores_sha256=sha(fp)))
    write('SOURCE_FIT_IDENTITY.json',dict(status='PASS',rows=len(rr),uid_sha256=uid,fit_x_path=str(xp),fit_x_sha256=sha(xp),weight_sha256=sha(ART/'FIT_WEIGHTS.npy'),class_mass=[float(weight[labels==v].sum()) for v in [0,1]],rule='fixed source device/activity/capture/session hierarchy, each class mass 0.5',mlp_self_scales=mlp))
    del rows,rr,z,q,ctx;gc.collect();return x,weight,np.asarray([v['scale'] for v in mlp])

def tabm_raw(w,c,k,geometry,fit_x,weight):
    import torch
    expected=read(HERE/'TABM_EXPECTED_METRICS.json');evalpin=read(HERE/'TABM_EVALUATE_PIN.json');spec=read(HERE/'EVALUATION_INPUTS_PIN.json')['pools'];folder=TABM/'artifacts/evaluation'
    assert sha(TABM/'TabM_METRICS.json')==evalpin['metrics_sha256']
    data={'FIT':fit_x};rows={};stored={};scores={};assets={};times={};modelpins={};oldcuts=np.asarray(expected['CAL']['cuts'])
    for pool in ['CAL','CIC_DEV','UNSW_DEV','EDGE']:
        xp=folder/(pool+'_X.npy');rp=folder/(pool+'_ROWS.json');sp=folder/('TabM_'+pool+'_scores.npy')
        assert sha(xp)==spec[pool]['x_sha256'] and sha(rp)==spec[pool]['rows_sha256'] and sha(sp)==evalpin['scores'][pool]['sha256']
        data[pool]=np.load(xp,mmap_mode='r');rows[pool]=read(rp);assert k.c.uid_sha(r['uid'] for r in rows[pool])==spec[pool]['uid_sha256']==evalpin['scores'][pool]['uid_sha256']
        stored[pool]=np.load(sp,mmap_mode='r');assert stored[pool].shape==(len(rows[pool]),4)
        assets[pool]=dict(input=spec[pool],scores_sha256=sha(sp),scores_path=str(sp))
    for pool,x in data.items():scores[pool]=np.lib.format.open_memmap(ART/(pool+'_RESCORED.npy'),mode='w+',dtype=np.float64,shape=(len(x),4))
    for j,seed in enumerate(HEADS[:3]):
        dest=TABM/'artifacts/TabM'/seed/'refit';r=read(dest/'COMPLETE.json');mp=dest/'best.pt';assert r['status']=='PASS' and sha(mp)==r['best_sha256']
        s=torch.load(mp,weights_only=False,map_location='cpu');assert s['config_sha256']==sha(TABM/'CONFIG.json')
        model=w.model('TabM','cuda');model.load_state_dict(s['model']);model.eval().requires_grad_(False)
        modelpins[seed]=dict(path=str(mp),sha256=sha(mp),receipt_sha256=sha(dest/'COMPLETE.json'),selected_epoch=r['best_epoch'])
        for pool,x in data.items():
            t=time.monotonic()
            with torch.inference_mode():
                for off in range(0,len(x),256):
                    q=torch.as_tensor(np.array(x[off:off+256],copy=True),device='cuda');scores[pool][off:off+len(q),j]=w.score(model,'TabM',q).astype(np.float64)
                    if off%16384==0:progress('TabM_'+seed+'_FORWARD_'+pool,off,len(x))
            torch.cuda.synchronize();times[seed+'/'+pool]=time.monotonic()-t
        del model,s;gc.collect();torch.cuda.empty_cache()
    gates={}
    for pool,a in scores.items():
        a[:,3]=np.stack([a[:,j] for j in range(3)]).mean(0,dtype=np.float64);a.flush();assert np.isfinite(a).all() and ((a>=0)&(a<=1)).all()
        if pool!='FIT':
            err=float(np.max(np.abs(a-stored[pool])));flips=int(np.count_nonzero((a>oldcuts)!=(stored[pool]>oldcuts)))
            assert err<=2e-7 and flips==0,'TABM_FULL_RAW_REPRODUCTION:'+pool
            gates[pool]=dict(status='PASS',max_score_abs_error=err,decision_differences=flips,rows=len(a))
    # Preserve original published native RAW scores; no target-based recalibration.
    calrows=rows['CAL'];cal=np.asarray(stored['CAL']);cuts=np.array([k.threshold(cal[:,j],calrows,.01) for j in range(4)])
    assert np.array_equal(cuts,oldcuts),'TABM_SOURCE_CAL_REPRODUCTION'
    ww=k.class_weights(calrows);fpr=[float(ww[cal[:,j]>cuts[j]].sum()) for j in range(4)];assert max(fpr)<=.010000000001
    quantiles=[(geometry.weighted_quantile(scores['FIT'][:,j],weight,.1),geometry.weighted_quantile(scores['FIT'][:,j],weight,.9)) for j in range(3)]
    scales=np.array([hi-lo for lo,hi in quantiles]);assert np.isfinite(scales).all() and ((scales>=0)&(scales<=1)).all()
    write('TABM_SOURCE_CALIBRATION.json',dict(status='PASS',seeds=HEADS[:3],score='per-model mean of 32 member class-1 probabilities; float32 native output promoted to float64; seed-order float64 arithmetic mean',q10=[lo for lo,hi in quantiles],q90=[hi for lo,hi in quantiles],scales=scales.tolist(),zero_scale_seeds=[HEADS[j] for j,v in enumerate(scales) if v==0],cuts=cuts.tolist(),ensemble_cut_independently_calibrated=True,normal_cal_rows=len(calrows),weighted_cal_fpr=fpr,scale_role='SOURCE_FIT',threshold_role='SOURCE_CAL_NORMAL',lambda_value=.25,p=3,guard=True,corrected_scores_clipped=False))
    write('TABM_RAW_REPRODUCTION.json',dict(status='PASS',gates=gates,model_assets=modelpins,input_assets=assets,forward_seconds=times,fit_scored_new=True,all_fit_rows=len(fit_x),training=False,fit_score_sha256=sha(ART/'FIT_RESCORED.npy')))
    return stored,rows,cuts,scales,expected

def compare_metrics(r,expected):
    lookup={(v['pool'],v['view'],v['head'],v['group']):v for v in r if v['guard_stratum']=='ALL'};count=0
    for e in expected:
        a=lookup[e['pool'],e['view'],e['head'],e['group']]
        for n in ['rows','alarm_count','sample_rate','hierarchical_rate','HT_rate']:
            if n in e:assert abs(a[n]-e[n])<=2e-10,'FROZEN_MLP_METRIC:'+n
        count+=1
    return count

def evaluate(c,reporting,legacy_metrics,loaded,mlp_cuts,mlp_scales,tabraw,tabrows,tabcuts,tabscales,expected):
    records=[];pairs=[];gates={};uid_manifest={};ranges={};mlpexpected=read(HERE/'MLP_EXPECTED_METRICS.json');source=ROOT/'runs/same_bank_context_v6_20261106'
    cuts={n:tabcuts if n.startswith('TabM') else mlp_cuts for n in NAMES}
    native_gates={}
    for pool,d in loaded.items():
        progress('RAW_METRIC_AND_REFERENCE_JOIN_'+pool)
        rr=tabrows[pool];assert [r['uid'] for r in rr]==d['ids'].tolist(),'SUPPORT_TABM_UID_ALIGNMENT'
        assert all(a['label']==b['label'] and a['protocol']==b['protocol'] for a,b in zip(rr,d['rows']))
        raw=np.asarray(tabraw[pool]);pp=raw>tabcuts
        # Reproduce every available native RAW metric before introducing C5.
        if pool=='EDGE':
            pop=c.read(c.ROOT/'runs/edge_formal_execution_v4_20261104/POPULATION_TEMPORAL_CENSUS.json');native=reporting.summarise(rr,{'RAW':pp},population=pop,prediction_uids={'RAW':[r['uid'] for r in rr]},raw_name='RAW',independent_methods=());native.pop('ordered_query_uids',None)
            want={k:v for k,v in expected[pool].items() if k!='ranking_full_ordinary'};equal(native,want,pool)
        else:
            vv={'full':d['views']['full'],'primary':d['views']['post_window_primary']};native=legacy_metrics.summarize(rr,{'TabM':{'RAW':pp}},vv)
            equal(native,{k:expected[pool][k] for k in ['full','primary']},pool)
        native_gates[pool]=dict(status='PASS',all_original_raw_metrics=True,uid_alignment=True)
    write('TABM_NATIVE_METRIC_REPRODUCTION.json',dict(status='PASS',pools=native_gates,before_any_reference_correction=True))
    for pool,d in loaded.items():
        progress('FIVE_ROW_REFERENCE_COMPARISON_'+pool);raw=np.asarray(tabraw[pool])
        artifact=read(source/'DIAGNOSE_RESULT.json')['pools'][pool]['artifact']
        with np.load(source/artifact['file'],allow_pickle=False) as a:mlpself=a['C5_3D_FUSION'].copy()
        rebuilt=c.four(c.correction(d['raw'][:,:3],d['s'],d['q'],mlp_scales));assert np.array_equal(rebuilt,mlpself),'MLP_SELF_SCALE_SCORE_PARITY'
        corrected=c.four(c.correction(raw[:,:3],d['s'],d['q'],tabscales))
        values={'MLP-RAW':d['raw'],'MLP-3D-SELF':mlpself,'TabM-RAW':raw,'TabM-3D-SELF':corrected,'FROZEN-MAIN':d['base']}
        preds={n:v>cuts[n] for n,v in values.items()};guard=ac.guard(d['q'])
        for a,b in [('MLP-RAW','MLP-3D-SELF'),('MLP-RAW','FROZEN-MAIN'),('TabM-RAW','TabM-3D-SELF')]:
            assert np.all(values[b]<=values[a]) and not np.any(preds[b]&~preds[a]),'SUBTRACTIVE_CEILING'
            assert np.array_equal(values[a][guard],values[b][guard]),'GUARD_PARITY'
        for name,pp in preds.items():
            r=ac.metrics(pool,d['rows'],pp,d['views'],d['q'],d['expansion'],d['population']);records.extend(dict(config=name,**v) for v in r)
        for left,right in [('MLP-RAW','MLP-3D-SELF'),('TabM-RAW','TabM-3D-SELF'),('MLP-RAW','FROZEN-MAIN'),('MLP-RAW','TabM-RAW'),('MLP-3D-SELF','TabM-3D-SELF'),('FROZEN-MAIN','TabM-3D-SELF')]:
            p=ac.paired(pool,d['rows'],preds[left],preds[right],d['views'],d['q'],d['expansion']);pairs.extend(dict(left=left,right=right,**v) for v in p)
            target=ART/(pool+'_'+left+'_vs_'+right+'_changed.jsonl.gz');count=0
            with gzip.open(target,'wt',encoding='utf8') as f:
                for i in np.flatnonzero(np.any(preds[left]!=preds[right],axis=1)):
                    f.write(json.dumps(dict(uid=str(d['ids'][i]),row=int(i),guard=bool(guard[i]),label=d['rows'][i]['label'],device=d['rows'][i]['device'],left=preds[left][i].astype(int).tolist(),right=preds[right][i].astype(int).tolist(),heads=HEADS))+'\n');count+=1
            uid_manifest[target.name]=dict(path=str(target),rows=count,sha256=sha(target))
        ranges[pool]={n:dict(min=np.min(v,axis=0).tolist(),max=np.max(v,axis=0).tolist(),negative_rows=(v<0).sum(0).tolist()) for n,v in values.items()}
        np.savez(ART/(pool+'_FIVE_ROWS.npz'),uid=d['ids'],support3=d['s'],**values)
        gates[pool]=dict(status='PASS',native_raw_metrics_reproduced=True,uid_aligned=True,subtractive_subset=True,guard_parity=True,five_score_artifact_sha256=sha(ART/(pool+'_FIVE_ROWS.npz')))
    mlp_checks={}
    for name,source_name in [('MLP-RAW','RAW'),('MLP-3D-SELF','C5_3D_FUSION'),('FROZEN-MAIN','C5_3D_OLD')]:mlp_checks[name]=compare_metrics([r for r in records if r['config']==name],[r for r in mlpexpected if r['method']==source_name])
    write('METRICS.json',records);table('METRICS.csv',records);write('PAIRED_CHANGES.json',pairs);table('PAIRED_CHANGES.csv',pairs);write('CHANGED_UID_MANIFEST.json',uid_manifest)
    write('EVALUATION_GATES.json',dict(status='PASS',pools=gates,mlp_metric_rows_verified=mlp_checks,score_ranges=ranges,configurations=NAMES,clipped=False,reference_support='raw support3, exact frozen geometry; no TabM representation search',main_method_changed=False))
    lines=['# TabM检测头与3D正常参考迁移结果','', '结果：五行已按固定口径计算，原生TabM RAW及三条MLP旧结果核验通过。性能优劣以表及配对代价判断，不以完成状态代替科学结论。','影响：不替换主方法、不调整p/λ/阈值，不裁剪概率域修正后的判别分数。','', '|池|视图|配置|组|告警/查询|普通%|加权%|HT%|','|---|---|---|---|---|---|---|---|']
    for r in records:
        if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:
            ht=f"{100*r['HT_rate']:.6f}" if 'HT_rate' in r else '--';lines.append(f"|{r['pool']}|{r['view']}|{r['config']}|{r['group']}|{r['alarm_count']}/{r['rows']}|{100*r['sample_rate']:.6f}|{100*r['hierarchical_rate']:.6f}|{ht}|")
    lines+=['','## 各头参考修正的收益与攻击代价（集成主视图）']
    for r in pairs:
        if (r['left'],r['right']) in [('MLP-RAW','MLP-3D-SELF'),('TabM-RAW','TabM-3D-SELF')] and r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP'] and r['view']==('full' if r['pool']=='EDGE' else 'post_window_primary'):
            lines.append(f"- {r['pool']} / {r['left']}→{r['right']} / {r['group']}：撤去{r['n10']}/{r['rows']}条查询告警，加权减少{100*r['weighted_n10']/r['weighted_denominator']:.6f}个百分点；新增{r['n01']}条。")
    lines+=['','全部种子、full/建档后、保护命中与设备/活动分解见JSON/CSV。两种训练流程/目标存在差异，不声称只隔离架构因果作用。TabM修正分数不再是概率，负值保留。','本候选是已有评价结果后提出的追加迁移比较，不自动晋升，不将同一数据重新称为新独立确认。来源中Edge开发历史表述冲突不由本计算自动裁决。']
    (OUT/'RESULT_READOUT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')

def main():
    global STARTED
    assert not OUT.exists() and not ART.exists(),'NEW_OUTPUT_ONLY';OUT.mkdir();ART.mkdir();STARTED=True;start=time.monotonic()
    w,b,c,inputs,reporting,freeze,d,mlpcuts,oldscales,k,geometry,legacy=initialize()
    x,weight,mlpscales=source_assets(c,inputs,k,geometry,freeze)
    raw,rows,cuts,scales,expected=tabm_raw(w,c,k,geometry,x,weight)
    write('SCALE_AND_THRESHOLD_FREEZE.json',dict(status='FROZEN_BEFORE_TARGET_CORRECTION',mlp_own_scales=mlpscales.tolist(),tabm_own_scales=scales.tolist(),frozen_main_scales=oldscales.tolist(),mlp_cuts=mlpcuts.tolist(),tabm_cuts=cuts.tolist(),p=3,lambda_value=.25,guard=True,refit=False))
    evaluate(c,reporting,legacy,d,mlpcuts,mlpscales,raw,rows,cuts,scales,expected)
    write('ASSET_IDENTITY.json',dict(status='PASS',runtime_resolved_pins=c.PINS,package_sha256=sha(HERE/'PACKAGE_MANIFEST.json'),frozen_method_sha256=sha(HERE/'METHOD_FREEZE.json'),support_cache_identity=read(OUT/'frozen_audit/BASELINE_ACCEPTANCE.json')['pools'],source_input_pins=read(HERE/'INPUT_PINS.json')))
    import resource
    import torch
    files={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='PROGRESS.json'}
    write('RUN_COMPLETE.json',dict(status='PASS',seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,gpu_peak_torch_allocated_bytes=torch.cuda.max_memory_allocated(),training=False,new_fit_forward=True,target_based_selection=False,output_sha256=files,code_snapshot=read(HERE/'PACKAGE_MANIFEST.json')));progress('COMPLETE',1,1)
if __name__=='__main__':
    try:main()
    except Exception as e:
        if STARTED:write('STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()))
        raise
