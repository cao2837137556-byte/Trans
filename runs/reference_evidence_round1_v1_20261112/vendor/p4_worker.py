"""P4 controlled replay and metadata audit. No selection, bank deletion or training."""
import collections,csv,gc,gzip,hashlib,importlib.util,json,sys,time,traceback
from pathlib import Path
import numpy as np
import analysis_core as ac
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];ART=HERE/'artifacts';OUT=None
AB=ROOT/'runs/paper_reading_ablations_v2_20261111';FULL=ROOT/'runs/same_bank_context_v6_20261106';COMM=ROOT/'runs/context_geometry_attribution_v2_20261106';TABM=ROOT/'runs/tabm_3d_transfer_v1_20261111'
SIX=['P4_2D_SELF','P4_2D_BASE','P4_3D_SELF','P4_GUARD_OFF','P4_COMMISSION_2D','P4_COMMISSION_3D']
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def uidsha(ids):return hashlib.sha256(('\n'.join(ids)+'\n').encode()).hexdigest()
def write(name,v):
    p=OUT/name;p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_suffix(p.suffix+'.tmp');tmp.write_text(json.dumps(v,ensure_ascii=False,allow_nan=False,indent=2),encoding='utf8');tmp.replace(p)
def progress(stage,done=0,total=1):
    import psutil
    rss=psutil.Process().memory_info().rss;assert rss<7*1024**3,'MEMORY_HEADROOM';write('PROGRESS.json',dict(stage=stage,done=int(done),total=int(total),updated_unix=time.time(),rss_bytes=rss))
def load(name,path):
    sp=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m
def four(a):return np.column_stack((a,np.stack([a[:,j] for j in range(3)]).mean(0,dtype=np.float64)))
def correct(raw,s,q,scales,guard=True,power=4):
    assert np.isfinite(s).all() and ((s>=0)&(s<=1)).all()
    g=np.where(s>0,1.-np.power(1.-s,power),0.);x=raw[:,:3].copy()
    for j,b in enumerate(scales):x[g>0,j]=raw[g>0,j]-(.25*b)*g[g>0]
    if guard:x[ac.guard(q)]=raw[ac.guard(q),:3]
    return four(x)
def check_metric_rows(actual,expected):
    lookup={(r['pool'],r['view'],r['head'],r['group'],r['guard_stratum']):r for r in actual};count=0
    for e in expected:
        a=lookup[e['pool'],e['view'],e['head'],e['group'],e.get('guard_stratum','ALL')]
        for k in ['rows','alarm_count','sample_rate','hierarchical_rate','weighted_numerator','weighted_denominator','HT_rate']:
            if k in e:assert abs(a[k]-e[k])<=2e-10,'METRIC_PARITY:'+str((e['pool'],k))
        count+=1
    return count
def export_tables(metrics,pairs):
    for name,rows in [('METRICS',metrics),('PAIRED_CHANGES',pairs)]:
        write(name+'.json',rows);keys=list(dict.fromkeys(k for r in rows for k in r))
        with (OUT/(name+'.csv')).open('w',encoding='utf8',newline='') as f:
            wr=csv.DictWriter(f,keys);wr.writeheader();wr.writerows(rows)
    lines=['# p=4完整库主配置与配套对照','', '结果：本项计算及身份/不变量门通过，全部配置保留，主结果采用用户选择的完整库P4；科学结论待完整验收。','影响：两小时库仅作覆盖消融，不替换主表。未删参考、未重训或重调阈值。','', '|池|视图|配置|组|告警/查询|普通%|加权%|HT%|','|---|---|---|---|---|---|---|---|']
    for r in metrics:
        if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:
            ht=f"{100*r['HT_rate']:.6f}" if 'HT_rate' in r else '--';lines.append(f"|{r['pool']}|{r['view']}|{r['config']}|{r['group']}|{r['alarm_count']}/{r['rows']}|{100*r['sample_rate']:.6f}|{100*r['hierarchical_rate']:.6f}|{ht}|")
    lines+=['','配对表n10为左臂有告警右臂无告警，n01反向；正常误报与攻击撤警联合报告，不能将四头计数相加为独立查询。完整种子、全视图、设备/活动/保护分组见JSON/CSV。']
    (OUT/'RESULT_READOUT.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
def changed(pool,left,right,d,a,b):
    path=ART/(pool+'_'+left+'_vs_'+right+'.jsonl.gz');n=0
    with gzip.open(path,'wt',encoding='utf8') as f:
        for i in np.flatnonzero(np.any(a!=b,axis=1)):
            r=d['rows'][i];f.write(json.dumps(dict(uid=str(d['ids'][i]),row=int(i),label=r['label'],device=r['device'],left=a[i].astype(int).tolist(),right=b[i].astype(int).tolist(),heads=ac.HEADS))+'\n');n+=1
    return dict(path=str(path),rows=n,sha256=sha(path))
def collect(pool,d,values,cuts,comparisons,metrics,pairs,manifest):
    pred={n:v>cuts[n] for n,v in values.items()}
    for n,p in pred.items():metrics.extend(dict(config=n,**r) for r in ac.metrics(pool,d['rows'],p,d['views'],d['q'],d['expansion'],d['population']))
    for left,right in comparisons:
        pairs.extend(dict(left=left,right=right,**r) for r in ac.paired(pool,d['rows'],pred[left],pred[right],d['views'],d['q'],d['expansion']))
        manifest[pool+'/'+left+'/'+right]=changed(pool,left,right,d,pred[left],pred[right])
def save_query(pool,d):
    rowsfile=ART/(pool+'_ROWS.jsonl.gz')
    with gzip.open(rowsfile,'wt',encoding='utf8') as f:
        for r in d['rows']:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    path=ART/(pool+'_QUERY.npz');arrays=dict(uid=d['ids'],q=d['q'],support3=d['s'])
    for name,(ix,w) in d['views'].items():arrays[name+'_ix']=ix;arrays[name+'_weight']=w
    if d['expansion'] is not None:arrays['expansion']=d['expansion']
    np.savez(path,**arrays);return dict(rows_file=rowsfile.name,rows_sha256=sha(rowsfile),array_file=path.name,array_sha256=sha(path),views=list(d['views']),population=d['population'])
def reference_inventory(c,pool):
    spec=read(FULL/'HISTORY_INPUTS.json');inventory=read(AB/'provenance/HISTORY_INVENTORY.json');seen=set();packs=[];equivalent=collections.defaultdict(list);context={}
    if pool!='EDGE':
        hc=read(FULL/'PREFLIGHT_RESULT.json')['pools'][pool]['history_context'];hp=FULL/hc['file'];assert sha(hp)==hc['sha256']
        with np.load(hp,allow_pickle=False) as a:context=dict(zip(a['uid'].tolist(),a['features']))
    for pack in spec['packs'].get(pool,[]):
        key=pack['rows'];asset=spec['assets'][key];path=Path(inventory[key]['path']);assert sha(path)==asset['sha256']
        with gzip.open(path,'rt') as f:allrows=[json.loads(x) for x in f]
        keep=[i for i,r in enumerate(allrows) if not pack.get('device') or r['device']==pack['device']];rows=[allrows[i] for i in keep]
        if 'count' in pack:assert len(rows)==pack['count']
        assert all(r['use']=='REFERENCE' and r['label']==0 and r['timestamp']<=r['reference_end'] for r in rows)
        assert not seen.intersection(r['uid'] for r in rows);seen.update(r['uid'] for r in rows)
        if pool=='UNSW_DEV':assert all(r['history_role']=='HIST_REF' and r['frame']<=r['bank_end_frame'] for r in rows)
        ap=Path(inventory[pack['arrays']]['path']);assert sha(ap)==spec['assets'][pack['arrays']]['sha256']
        with np.load(ap,allow_pickle=False) as a:
            assert a['uid'].tolist()==[r['uid'] for r in allrows]
            e3=a['e3'];q14=a['q14']
            for i in keep:
                r=allrows[i];assert r['uid'] in context
                # Conservative same-component eligibility equivalence. With a
                # valid bank_end_frame, an admitted query must be after it;
                # otherwise keep exact frame in the key. Never merge components.
                end=r.get('bank_end_frame');frame_key=None if end is not None and r['frame']<=end else r['frame']
                key=[r.get(k) for k in ['partition','device','protocol','component_id','capture_id','reference_end','bank_end_frame']]+[frame_key]
                digest=hashlib.sha256(json.dumps(key,sort_keys=True).encode())
                for x in [e3[i],q14[i],context[r['uid']]]:digest.update(np.asarray(x,dtype=np.float64).tobytes())
                equivalent[digest.hexdigest()].append(r['uid'])
        groups=collections.defaultdict(list)
        for r in rows:groups[r['device'],r['protocol']].append(r)
        packs.append(dict(asset_key=key,path=str(path),sha256=asset['sha256'],rows=len(rows),groups=[dict(device=k[0],protocol=k[1],rows=len(rr),components=len({r['component_id'] for r in rr}),captures=len({r['capture_id'] for r in rr}),first_time=min(r['timestamp'] for r in rr),last_time=max(r['timestamp'] for r in rr),origins=dict(collections.Counter(str(r.get('origin','UNRECORDED')) for r in rr))) for k,rr in sorted(groups.items())]))
    expected=289 if pool=='CIC_DEV' else 52835 if pool=='UNSW_DEV' else 0;assert len(seen)==expected
    duplicate_groups=[v for v in equivalent.values() if len(v)>1]
    return dict(status='PASS',history_rows=len(seen),packs=packs,selection_reexecuted=False,compression_performed=False,query_scores_used_for_inventory=False,exact_equivalence_inventory=dict(scope='historical references only; same component/eligibility key and exactly equal raw E3/q14/context8; no target score or error UID used',equivalence_groups=len(equivalent),duplicate_groups=len(duplicate_groups),potential_redundant_rows=sum(len(v)-1 for v in duplicate_groups),largest_group=max(map(len,equivalent.values()),default=0),note='Candidates only: no rows deleted; any future deduplication needs identical per-query support/decision replay before claiming lossless compression'))

def controls():
    b=load('old_baseline_loader',AB/'run.py');b.OUT=OUT/'baseline_audit';b.OUT.mkdir();b.progress=progress
    c,inputs,reporting,freeze=b.bootstrap();loaded,cuts,base=b.prepare(c,inputs,reporting,freeze);own=np.array([freeze['heads'][s]['scale'] for s in ac.HEADS[:3]])
    expected=read(HERE/'P4_EXPECTED_METRICS.json');prior=read(COMM/'DIAGNOSE_RESULT.json');pre=read(COMM/'PREFLIGHT_RESULT.json');full=read(FULL/'DIAGNOSE_RESULT.json');metrics=[];pairs=[];manifest={};gates={};queries={};banks={};details=[]
    old_assets=read(b.EVAL/'OLD_ASSETS.json');bank_inventory={}
    for pool,d in loaded.items():
        progress('P4_CACHE_PARITY_'+pool)
        with np.load(FULL/full['pools'][pool]['artifact']['file'],allow_pickle=False) as a:full2=a['support2'].copy()
        a=prior['pools'][pool]['large_artifacts'];path=COMM/a['file'];assert path.stat().st_size==a['bytes'] and sha(path)==a['sha256']
        with np.load(path,allow_pickle=False) as z:
            assert z['uid'].tolist()==d['ids'].tolist() and np.array_equal(z['RAW'],d['raw'])
            s2=z['support2'].copy();s3=z['support3'].copy()
            for dim,s in [('2D',s2),('3D',s3)]:
                v=correct(d['raw'],s,d['q'],base,power=3);old=z['C5_'+dim+'_OLD'];assert np.max(np.abs(v-old))<=2e-10 and np.array_equal(v>cuts,old>cuts),'COMMISSION_P3_SCORE_PARITY'
                mm=ac.metrics(pool,d['rows'],v>cuts,d['views'],d['q'],d['expansion'],d['population']);view='full' if pool=='EDGE' else 'post_window_primary'
                ee=[dict(pool=pool,view=view,head=h,group=g,**r) for h,gs in prior['pools'][pool]['metrics']['C5_'+dim+'_OLD'].items() for g,r in gs.items()];check_metric_rows(mm,ee)
        rc=pre['pools'][pool]['reference_context'];rp=COMM/rc['file'];assert sha(rp)==rc['sha256']
        with np.load(rp,allow_pickle=False) as z:refids=z['uid'].tolist()
        expected_uid=freeze['references'][pool]['uid_sha256'] if pool=='EDGE' else old_assets['pools'][pool]['dense_bank']['expected_ordered_uid_sha256'];assert uidsha(refids)==expected_uid,'COMMISSION_BANK_IDENTITY'
        banks[pool]=dict(commission_rows=len(refids),commission_uid_sha256=uidsha(refids),full_bank=freeze['references'][pool],commission_support_artifact=a)
        p4=correct(d['raw'],d['s'],d['q'],base);mm=ac.metrics(pool,d['rows'],p4>cuts,d['views'],d['q'],d['expansion'],d['population']);checked=check_metric_rows(mm,[r for r in expected if r['pool']==pool])
        values={'RAW':d['raw'],'P4_MAIN':p4,'P4_2D_SELF':correct(d['raw'],full2,d['q'],own),'P4_2D_BASE':correct(d['raw'],full2,d['q'],base),'P4_3D_SELF':correct(d['raw'],d['s'],d['q'],own),'P4_GUARD_OFF':correct(d['raw'],d['s'],d['q'],base,guard=False)}
        if pool=='EDGE':
            assert np.allclose(s2,full2,rtol=0,atol=2e-10) and np.allclose(s3,d['s'],rtol=0,atol=2e-10),'EDGE_BANK_SCOPE_IDENTITY'
            for ss,vv in [(s2,values['P4_2D_BASE']),(s3,p4)]:
                same=correct(d['raw'],ss,d['q'],base);assert np.max(np.abs(same-vv))<=2e-10 and np.array_equal(same>cuts,vv>cuts),'EDGE_P4_ALIAS_PARITY'
            values['P4_COMMISSION_2D']=values['P4_2D_BASE'];values['P4_COMMISSION_3D']=p4
        else:
            values['P4_COMMISSION_2D']=correct(d['raw'],s2,d['q'],base);values['P4_COMMISSION_3D']=correct(d['raw'],s3,d['q'],base)
        assert np.all(d['s']<=full2+2e-10) and np.all(s3<=s2+2e-10),'GEOMETRY_INTERSECTION'
        assert np.all(d['s']>=s3-2e-10) and np.all(full2>=s2-2e-10),'BANK_SUPERSET_SUPPORT'
        for n,v in values.items():assert np.isfinite(v).all() and not np.any((v>cuts)&~(d['raw']>cuts)),n
        g=ac.guard(d['q']);assert np.array_equal(values['P4_GUARD_OFF'][~g],p4[~g]) and not np.any((values['P4_GUARD_OFF']>cuts)&~(p4>cuts))
        for hi,lo in [('P4_MAIN','P4_2D_BASE'),('P4_3D_SELF','P4_2D_SELF'),('P4_COMMISSION_3D','P4_COMMISSION_2D'),('P4_COMMISSION_3D','P4_MAIN'),('P4_COMMISSION_2D','P4_2D_BASE')]:assert np.all(values[hi]>=values[lo]-2e-10) and not np.any((values[lo]>cuts)&~(values[hi]>cuts)),'MONOTONE:'+hi
        comparisons=[('RAW','P4_MAIN')]+[('P4_MAIN',n) for n in SIX]+[('P4_2D_SELF','P4_3D_SELF'),('P4_COMMISSION_2D','P4_COMMISSION_3D')]
        collect(pool,d,values,{n:cuts for n in values},comparisons,metrics,pairs,manifest)
        target=ART/(pool+'_CONTROLS.npz');np.savez(target,uid=d['ids'],**values);queries[pool]=dict(save_query(pool,d),scores_file=target.name,scores_sha256=sha(target))
        bank_inventory[pool]=reference_inventory(c,pool)
        gates[pool]=dict(status='PASS',p4_metric_rows_reused=checked,raw_supports=True,commission_p3_reproduced=True,edge_alias_reused=pool=='EDGE',subset_and_monotonicity=True)
        if pool=='CIC_DEV':
            old_manifest=read(HERE/'PRIOR_CHANGED_MANIFEST.json')['exponent/CIC_DEV_BASE_vs_P4_changed.jsonl.gz'];path=Path(old_manifest['remote_path']);assert sha(path)==old_manifest['sha256']
            with gzip.open(path,'rt') as f:changed_rows=[json.loads(x) for x in f]
            wanted={r['uid'] for r in changed_rows if r['label']==1 and r['left'][3]==1 and r['right'][3]==0}
            take=np.flatnonzero(np.array([r['label']==1 for r in d['rows']])&(d['base'][:,3]>cuts[3])&(p4[:,3]<=cuts[3]));assert set(d['ids'][take])==wanted and len(take)==6
            for i in take:details.append(dict(original_metadata=d['rows'][i],uid=str(d['ids'][i]),q14=d['q'][i].tolist(),tcp_syn=bool(d['q'][i,2]),tcp_ack=bool(d['q'][i,5]),guard=bool(g[i]),support3=float(d['s'][i]),heads=ac.HEADS,raw=d['raw'][i].tolist(),cuts=cuts.tolist(),raw_margin=(d['raw'][i]-cuts).tolist(),deduction_p3=(d['raw'][i]-d['base'][i]).tolist(),deduction_p4=(d['raw'][i]-p4[i]).tolist(),score_p3=d['base'][i].tolist(),score_p4=p4[i].tolist(),unit='query, not independently identified attack event'))
    export_tables(metrics,pairs);write('CHANGED_UID_MANIFEST.json',manifest);write('REFERENCE_BANKS.json',banks);write('HISTORY_LINEAGE_COUNTS.json',bank_inventory);write('CIC_SIX_WITHDRAWALS.json',details);write('QUERY_ASSETS.json',queries)
    write('VERIFICATION.json',dict(status='PASS',gates=gates,reference_identity=banks,main_p4_metrics_reused=True,new_controls=SIX,reference_rows_removed=0,distances_recomputed=False,training=False))

def tabm():
    complete=read(TABM/'results/RUN_COMPLETE.json');assert complete['status']=='PASS';cal=read(TABM/'results/TABM_SOURCE_CALIBRATION.json');ev=read(TABM/'results/EVALUATION_GATES.json')
    assert cal['p']==3 and cal['lambda_value']==.25 and cal['guard'] and not cal['corrected_scores_clipped'];assert ev['status']=='PASS'
    for n in ['TABM_SOURCE_CALIBRATION.json','TABM_RAW_REPRODUCTION.json','TABM_NATIVE_METRIC_REPRODUCTION.json','EVALUATION_GATES.json']:assert sha(TABM/'results'/n)==complete['output_sha256'][n]
    control=HERE/'results/controls';assert read(control/'COMPLETE.json')['status']=='PASS';query=read(control/'QUERY_ASSETS.json');f=read(HERE/'P3_METHOD_REFERENCE.json');mc=np.array([f['heads'][s]['cut'] for s in ac.HEADS[:3]]+[f['ensemble']['cut']]);tc=np.array(cal['cuts']);scales=np.array(cal['scales']);metrics=[];pairs=[];manifest={};gates={}
    for pool,a in query.items():
        progress('TABM_P4_CACHED_'+pool)
        for filekey,shakey in [('rows_file','rows_sha256'),('array_file','array_sha256'),('scores_file','scores_sha256')]:assert sha(ART/a[filekey])==a[shakey]
        with gzip.open(ART/a['rows_file'],'rt',encoding='utf8') as ff:rows=[json.loads(x) for x in ff]
        with np.load(ART/a['array_file'],allow_pickle=False) as z:d=dict(rows=rows,ids=z['uid'].copy(),q=z['q'].copy(),s=z['support3'].copy(),views={n:(z[n+'_ix'].copy(),z[n+'_weight'].copy()) for n in a['views']},expansion=z['expansion'].copy() if 'expansion' in z else None,population=a['population'])
        p=TABM/'artifacts'/(pool+'_FIVE_ROWS.npz');assert sha(p)==ev['pools'][pool]['five_score_artifact_sha256']
        with np.load(p,allow_pickle=False) as z:
            assert z['uid'].tolist()==d['ids'].tolist() and np.array_equal(z['support3'],d['s']);raw=z['TabM-RAW'].copy();old=z['TabM-3D-SELF'].copy();mlpraw=z['MLP-RAW'].copy();mlpold=z['MLP-3D-SELF'].copy()
        assert np.array_equal(correct(raw,d['s'],d['q'],scales,power=3),old),'TABM_P3_BRIDGE'
        new=correct(raw,d['s'],d['q'],scales);assert np.all(new<=old) and not np.any((new>tc)&~(old>tc));assert np.array_equal(new[ac.guard(d['q'])],raw[ac.guard(d['q'])])
        with np.load(ART/a['scores_file'],allow_pickle=False) as z:
            assert np.array_equal(z['RAW'],mlpraw);values={'MLP_RAW':mlpraw,'MLP_3D_SELF_P4':z['P4_3D_SELF'].copy(),'TABM_RAW':raw,'TABM_3D_SELF_P4':new,'P4_MAIN':z['P4_MAIN'].copy(),'TABM_3D_SELF_P3':old,'MLP_3D_SELF_P3':mlpold}
        cuts={n:tc if n.startswith('TABM') else mc for n in values};comparisons=[('TABM_RAW','TABM_3D_SELF_P4'),('MLP_RAW','MLP_3D_SELF_P4'),('TABM_3D_SELF_P3','TABM_3D_SELF_P4'),('MLP_3D_SELF_P3','MLP_3D_SELF_P4'),('P4_MAIN','TABM_3D_SELF_P4')]
        collect(pool,d,values,cuts,comparisons,metrics,pairs,manifest);np.savez(ART/(pool+'_TABM_P4.npz'),uid=d['ids'],**values);gates[pool]=dict(status='PASS',raw_unchanged=True,p3_bridge_exact=True,p4_subset_of_p3=True,score_sha256=sha(ART/(pool+'_TABM_P4.npz')))
    export_tables(metrics,pairs);write('CHANGED_UID_MANIFEST.json',manifest);write('VERIFICATION.json',dict(status='PASS',gates=gates,tabm_source_calibration=cal,main_rows=['MLP_RAW','MLP_3D_SELF_P4','TABM_RAW','TABM_3D_SELF_P4','P4_MAIN'],bridge_rows=['TABM_3D_SELF_P3','MLP_3D_SELF_P3'],new_forward=False,training=False,clipping=False))

def main(task):
    global OUT
    dest=HERE/'results'/task;assert not dest.exists(),'NEW_OUTPUT_ONLY';dest.mkdir(parents=True);OUT=dest;ART.mkdir(exist_ok=True)
    for n,h in read(HERE/'PACKAGE_MANIFEST.json')['files'].items():assert sha(HERE/n)==h,'PACKAGE_SHA:'+n
    for n,h in read(HERE/'INPUT_PINS.json').items():assert sha(ROOT/n)==h,'DEPENDENCY_SHA:'+n
    start=time.monotonic();{'controls':controls,'tabm':tabm}[task]();import resource
    write('COMPLETE.json',dict(status='PASS',task=task,seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,outputs_sha256={p.name:sha(p) for p in OUT.iterdir() if p.is_file() and p.name!='PROGRESS.json'}));progress('COMPLETE',1,1)
if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception as e:
        if OUT is not None:write('STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()))
        raise
