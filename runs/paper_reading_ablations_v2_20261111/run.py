"""Cached final-3D ablations. Fail closed before any variant on baseline mismatch."""
import csv,gc,gzip,hashlib,importlib.util,json,os,sys,time,traceback
from pathlib import Path
import numpy as np
import analysis_core as ac
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SOURCE=ROOT/'runs/same_bank_context_v6_20261106';EVAL=ROOT/'runs/device_context_evaluation_v1_20261105'
OUT=HERE/'results';HEADS=ac.HEADS;CREATED=False

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def write(p,v):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');tmp.replace(p)
def progress(stage,done=0,total=1):
    import psutil
    rss=psutil.Process().memory_info().rss;assert rss<7*1024**3,'RSS_HEADROOM_GATE'
    write(OUT/'PROGRESS.json',dict(stage=stage,done=done,total=total,updated_unix=time.time(),rss_bytes=rss))
def table(path,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w',newline='',encoding='utf8') as f:
        wr=csv.DictWriter(f,fieldnames=keys);wr.writeheader();wr.writerows(rows)
def check_baseline(pool,values,stored,rows,views,q,cuts,expected,expansion=None,population=None,raw=None):
    err=float(np.max(np.abs(values-stored)));flips=int(np.count_nonzero((values>cuts)!=(stored>cuts)))
    assert err<=2e-10 and flips==0,'BASE_SCORE_OR_UID_DECISION_MISMATCH'
    metrics=ac.metrics(pool,rows,values>cuts,views,q,expansion,population)
    lookup={(r['view'],r['head'],r['group']):r for r in metrics if r['guard_stratum']=='ALL'};n=0;group_masks=ac.groups(rows)
    for e in expected:
        if e['pool']!=pool:continue
        r=lookup[e['view'],e['head'],e['group']]
        for key in ['rows','alarm_count']:assert r[key]==e[key],f'BASE_COUNT:{pool}:{key}'
        for key in ['sample_rate','hierarchical_rate','HT_rate']:
            if key in e:assert abs(r[key]-e[key])<=2e-10,f'BASE_RATE:{pool}:{key}'
        if 'added_vs_RAW' in e or 'removed_vs_RAW' in e:
            assert raw is not None
            ix=views[e['view']][0];ix=ix[group_masks[e['group']][ix]];j=HEADS.index(e['head']);a=values[ix,j]>cuts[j];b=raw[ix,j]>cuts[j]
            assert int((a&~b).sum())==e['added_vs_RAW'] and int((~a&b).sum())==e['removed_vs_RAW'],'BASE_RAW_PAIRED_COUNT'
        n+=1
    assert n>0
    return dict(status='PASS',max_score_abs_error=err,uid_head_decision_differences=flips,frozen_metric_rows_verified=n),metrics

def bootstrap():
    manifest=read(HERE/'PACKAGE_MANIFEST.json')
    for n,h in manifest['files'].items():assert sha(HERE/n)==h,'PACKAGE_SHA:'+n
    locations=read(HERE/'PIN_LOCATIONS.json')
    allowed={'runs/same_bank_context_v6_20261106/'+n:'provenance/'+n for n in ['FORMAL_ACCEPTANCE.json','EVALUATION_COMPLETION.json','DELIVERY.json','HISTORY_INVENTORY.json']}
    assert locations==allowed,'PROVENANCE_MAPPING_SCOPE'
    resolved={}
    for n,h in read(HERE/'INPUT_PINS.json').items():
        path=HERE/locations[n] if n in locations else ROOT/n
        assert sha(path)==h,'DEPENDENCY_SHA:'+n
        resolved[n]=dict(path=str(path),sha256=h,isolated_provenance=n in locations)
        if n.endswith('/HISTORY_INVENTORY.json'):
            assert read(ROOT/n)==read(path),'HISTORY_INVENTORY_SEMANTICS'
            resolved[n]['original_remote_sha256']=sha(ROOT/n)
    write(OUT/'DEPENDENCY_LOCATIONS.json',dict(status='PASS',files=resolved,history_inventory_semantic_parity=True))
    sys.path.insert(0,str(EVAL));import common as c,inputs,reporting
    assert Path(c.__file__).resolve()==EVAL/'common.py'
    c.progress=inputs.progress=progress;c.verify()
    f=read(HERE/'METHOD_FREEZE.json');trained=read(EVAL/'FINAL_TRAINING_ACCEPTANCE.json')
    for seed in HEADS[:3]:
        a=trained['heads']['FUSION790_'+seed];b=f['heads'][seed]
        assert a['head_sha256']==b['head_sha256'] and a['cut']==b['cut']
        c.pin(c.TRAIN/'heads'/('FUSION790_'+seed)/'train/head.npz',b['head_sha256'])
    assert trained['ensembles']['FUSION790']['cut']==f['ensemble']['cut']
    return c,inputs,reporting,f

def prepare(c,inputs,reporting,freeze):
    result=read(SOURCE/'DIAGNOSE_RESULT.json');cuts=np.array([freeze['heads'][h]['cut'] for h in HEADS[:3]]+[freeze['ensemble']['cut']]);scales=np.array(freeze['correction']['scales'])
    assert freeze['correction']['lambda_value']==.25 and freeze['correction']['p']==3
    expected=read(HERE/'BASE_EXPECTED_METRICS.json');loaded={};audit={}
    for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
        progress('BASELINE_LOAD_'+pool);a=result['pools'][pool]['artifact'];path=SOURCE/a['file'];assert path.stat().st_size==a['bytes'];assert sha(path)==a['sha256']
        assert a==freeze['result_artifacts'][pool],'FROZEN_CACHE_IDENTITY'
        assert freeze['references'][pool]==dict(rows=result['pools'][pool]['reference_rows'],uid_sha256=result['pools'][pool]['reference_uid_sha256']),'FROZEN_REFERENCE_IDENTITY'
        d=inputs.edge() if pool=='EDGE' else inputs.ab(pool);rows=d['rows'];q=np.asarray(d['q']).copy()
        for r in rows:r.setdefault('device',r.get('owner','PINNED_EDGE_TARGET'))
        with np.load(path,allow_pickle=False) as cache:
            assert {'uid','support3','RAW','C5_3D_OLD','c2_stored_zero_mask'}<=set(cache.files),'RAW_SUPPORT3_REQUIRED'
            ids=cache['uid'].copy();assert ids.tolist()==[r['uid'] for r in rows] and len(set(ids))==len(ids),'QUERY_UID_ORDER'
            s=cache['support3'].copy();raw=cache['RAW'].copy();stored=cache['C5_3D_OLD'].copy();historical_zero=cache['c2_stored_zero_mask'].copy()
        expansion=population=None
        if pool=='EDGE':
            weights=reporting._hierarchical_weights(rows);views={'full':(np.arange(len(rows)),weights)};expansion,_=reporting._weights(rows)
            old=read(EVAL/'EDGE_RESULT.json');population={role:old['arms']['FUSION790']['methods']['RAW']['heads']['ensemble']['roles'][role]['population_count'] for role in ['NORMAL','HTTP','UDP']}
            assert all(sum(r['source_role']==role for r in rows)==20000 for role in population)
        else:views={'full':d['views']['full'],'post_window_primary':d['views']['primary']}
        del d;gc.collect()
        values=ac.scores(raw,s,q,scales,'BASE')
        producer=c.four(c.correction(raw[:,:3],s,q,scales));assert np.array_equal(values,producer),'PRODUCER_ARITHMETIC_PARITY'
        gate,_=check_baseline(pool,values,stored,rows,views,q,cuts,expected,expansion,population,raw)
        guard=ac.guard(q)
        if pool=='UNSW_DEV':assert guard[np.array([r['label']==1 for r in rows])].all(),'UNSW_ATTACK_GUARD_CONTRACT'
        audit[pool]=dict(**gate,input_artifact=a,reference=freeze['references'][pool],raw_support_field='support3',support3_before_guard=True,rows=len(rows),guard_rows=int(guard.sum()),guard_positive_support_rows=int((guard&(s>0)).sum()),historical_zero_mask_rows=int(historical_zero.sum()),raw_support_positive_on_historical_zero_rows=int((historical_zero&(s>0)).sum()),q14_sha256=hashlib.sha256(q.tobytes()).hexdigest(),uid_order_sha256=hashlib.sha256('\n'.join(ids).encode()).hexdigest(),q14_shape=list(q.shape),q14_dtype=str(q.dtype))
        loaded[pool]=dict(rows=rows,q=q,s=s,raw=raw,views=views,expansion=expansion,population=population,base=values,ids=ids)
        write(OUT/'BASELINE_PARTIAL.json',audit)
    assert sum(v['frozen_metric_rows_verified'] for v in audit.values())==len(expected)
    write(OUT/'BASELINE_ACCEPTANCE.json',dict(status='PASS',all_pools_before_variants=True,pools=audit,metric_rows=len(expected),method_freeze_sha256=sha(HERE/'METHOD_FREEZE.json')))
    write(OUT/'ASSET_IDENTITY.json',dict(status='PASS',resolved_source_pins=c.PINS,producer_pins=read(HERE/'INPUT_PINS.json'),support_semantics='raw geometry support3; historical effective-zero arrays never used',method_freeze_sha256=sha(HERE/'METHOD_FREEZE.json'),package_manifest_sha256=sha(HERE/'PACKAGE_MANIFEST.json')))
    return loaded,cuts,scales

def stage(name,loaded,cuts,scales):
    dest=OUT/name;dest.mkdir();start=time.monotonic();records=[];pairs=[];gates={};changed_manifest={}
    arms=['BASE','GUARD_OFF'] if name=='guard' else ['P1','P2','BASE','P4']
    for pool,d in loaded.items():
        progress(name.upper()+'_'+pool)
        values={a:d['base'] if a=='BASE' else ac.scores(d['raw'],d['s'],d['q'],scales,a) for a in arms}
        gates[pool]=ac.invariant(values,d['s'],d['q'],cuts,name);pred={a:v>cuts for a,v in values.items()}
        for arm,pp in pred.items():
            rows=ac.metrics(pool,d['rows'],pp,d['views'],d['q'],d['expansion'],d['population']);records.extend(dict(config=arm,**r) for r in rows)
        for a,b in ac.PAIRS[name]:
            r=ac.paired(pool,d['rows'],pred[a],pred[b],d['views'],d['q'],d['expansion']);pairs.extend(dict(left=a,right=b,**v) for v in r)
            target=dest/(pool+'_'+a+'_vs_'+b+'_changed.jsonl.gz');g=ac.guard(d['q']);count=0
            with gzip.open(target,'wt',encoding='utf8') as f:
                for i in np.flatnonzero(np.any(pred[a]!=pred[b],axis=1)):
                    row=d['rows'][i];v=dict(uid=str(d['ids'][i]),row_index=int(i),label=row['label'],device=row['device'],guard=bool(g[i]),source_role=row.get('source_role'),activity=row.get('activity'),support3=float(d['s'][i]),left=pred[a][i].astype(int).tolist(),right=pred[b][i].astype(int).tolist(),heads=HEADS,views=[view for view,(ix,_) in d['views'].items() if view=='full' or i in view_sets(d)[view]])
                    f.write(json.dumps(v,ensure_ascii=False)+'\n');count+=1
            changed_manifest[target.name]=dict(rows=count,sha256=sha(target),bytes=target.stat().st_size,storage='HPC_ONLY')
    write(dest/'METRICS.json',records);table(dest/'METRICS.csv',records);write(dest/'PAIRED_CHANGES.json',pairs);table(dest/'PAIRED_CHANGES.csv',pairs)
    write(dest/'CHANGED_UID_MANIFEST.json',changed_manifest)
    report=['# '+('SYN保护开关' if name=='guard' else '支持指数')+'消融回执','', '结果：基准复现及本项不变量检查通过；以下为全部配置的选中查询结果，不据结果替换冻结参数。','影响：NORMAL为误报，攻击为攻击关联查询检出；降低告警同时可能减少正常误报和攻击检出。普通/加权不可混用。','', '|池|视图|配置|组|告警/查询|普通率(%)|加权率(%)|HT率(%)|','|---|---|---|---|---|---|---|---|']
    for r in records:
        if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:
            ht='--' if 'HT_rate' not in r else f"{100*r['HT_rate']:.6f}"
            report.append(f"|{r['pool']}|{r['view']}|{r['config']}|{r['group']}|{r['alarm_count']}/{r['rows']}|{100*r['sample_rate']:.6f}|{100*r['hierarchical_rate']:.6f}|{ht}|")
    report+=['','## 配对变化（集成，各头完整结果见JSON）','n10为左配置告警、右配置不告警；n01相反。各头不能相加作为独立查询。','', '|池|视图|左→右|组|n10|n01|','|---|---|---|---|---|---|']
    for r in pairs:
        if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:report.append(f"|{r['pool']}|{r['view']}|{r['left']}→{r['right']}|{r['group']}|{r['n10']}|{r['n01']}|")
    report+=['','保护命中/未命中、设备和活动/攻击类别分解及加权交叉计数见配对文件。无总体人口分母的Edge子组仅报告HT总量贡献，不生成虚构的子组人口率。','大规模改变UID明细留超算，SHA见CHANGED_UID_MANIFEST。此为缓存后处理计算耗时，不是端到端吞吐。']
    conclusions=[]
    for r in pairs:
        wanted=('BASE','GUARD_OFF') if name=='guard' else ('P1','BASE')
        primary='full' if r['pool']=='EDGE' else 'post_window_primary'
        if (r['left'],r['right'])==wanted and r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['view']==primary and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:
            effect='开启保护额外保留' if name=='guard' else '指数从1变为3撤去'
            conclusions.append(f"- {r['pool']} / {primary} / {r['group']}：{effect} {r['n10']} 条告警（分母 {r['rows']} 条查询），加权变化 {100*r['weighted_n10']/r['weighted_denominator']:.6f} 个百分点；反向变化 {r['n01']} 条。")
    report[2:2]=['## 本项结论（固定集成，完整视图与单头见下表）',*conclusions,'']
    (dest/'RESULT_READOUT.md').write_text('\n'.join(report)+'\n',encoding='utf8')
    write(dest/'VERIFICATION.json',dict(status='PASS',stage=name,invariants=gates,seconds=time.monotonic()-start,distances_recomputed=False,trained=False,threshold_refit=False,metrics_rows=len(records),pair_rows=len(pairs),raw_support3=True,baseline_acceptance_sha256=sha(OUT/'BASELINE_ACCEPTANCE.json'),output_sha256={n:sha(dest/n) for n in ['METRICS.json','METRICS.csv','PAIRED_CHANGES.json','PAIRED_CHANGES.csv','RESULT_READOUT.md','CHANGED_UID_MANIFEST.json']}))
    write(dest/'COMPLETE.json',dict(status='PASS',verification_sha256=sha(dest/'VERIFICATION.json')))

def view_sets(d):
    if '_view_sets' not in d:d['_view_sets']={n:set(map(int,ix)) for n,(ix,_) in d['views'].items()}
    return d['_view_sets']

def main():
    global CREATED
    assert not OUT.exists(),'NEW_OUTPUT_ONLY; preserve previous outputs and use a new version on retry'
    OUT.mkdir();CREATED=True;start=time.monotonic();c,inputs,reporting,freeze=bootstrap();loaded,cuts,scales=prepare(c,inputs,reporting,freeze)
    stage('guard',loaded,cuts,scales);progress('GUARD_COMPLETE',1,2)
    stage('exponent',loaded,cuts,scales)
    import resource
    write(OUT/'RUN_COMPLETE.json',dict(status='PASS',seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,guard_complete=True,exponent_complete=True,configurations=5,distances_recomputed=False,training=False))
    progress('COMPLETE',2,2)

if __name__=='__main__':
    try:main()
    except Exception as e:
        if CREATED:write(OUT/'STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()))
        raise
