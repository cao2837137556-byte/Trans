"""Audit small returned receipts independently; no inference or target selection."""
import csv,hashlib,json,math,re,shutil,subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
DEPLOY=ROOT/'runs/paper_reading_ablations_deploy_v1_20261111';SOURCE=DEPLOY/'received';SCIENCE=ROOT/'runs/paper_reading_ablations_v2_20261111'
checks=0
def need(ok,why):
    global checks
    checks+=1
    assert ok,why
def close(a,b):return math.isclose(a,b,rel_tol=2e-10,abs_tol=2e-12)
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,value):
    p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n',encoding='utf8')
def csv_table(name,rows):
    keys=list(dict.fromkeys(k for r in rows for k in r))
    with (HERE/name).open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def metric_key(r):return tuple(r[n] for n in ['config','pool','view','head','group','guard_stratum'])
def pair_metric_key(r,side):return (r[side],)+tuple(r[n] for n in ['pool','view','head','group','guard_stratum'])
def csv_parity(path,rows):
    with Path(path).open(encoding='utf8',newline='') as f:actual=list(csv.DictReader(f))
    need(len(actual)==len(rows),'CSV_ROW_COUNT')
    for a,b in zip(actual,rows):
        for k,v in a.items():
            if k not in b:need(v=='','CSV_MISSING_FIELD');continue
            if isinstance(b[k],str):need(v==b[k],'CSV_STRING')
            elif isinstance(b[k],(int,float)):need(close(float(v),b[k]),'CSV_NUMBER')
def md_table(path,headers,rows):
    text='| '+' | '.join(headers)+' |\n| '+' | '.join(['---']*len(headers))+' |\n'
    text+=''.join('| '+' | '.join(map(str,r))+' |\n' for r in rows)
    (HERE/path).write_text(text,encoding='utf8')
def main():
    retrieval=read(DEPLOY/'RETRIEVAL.json')['sha256']
    for name,digest in retrieval.items():need(sha(SOURCE/name)==digest,'RETRIEVAL_SHA:'+name)
    snap=read(DEPLOY/'ACCEPTANCE_SCHEDULER_SNAPSHOT.json');need(snap['stage']=='COMPLETE' and '183530|COMPLETED|0:0' in snap['scheduler'],'SCHEDULER_SUCCESS')
    b=read(SOURCE/'results/BASELINE_ACCEPTANCE.json');freeze=read(SCIENCE/'METHOD_FREEZE.json')
    need(b['status']=='PASS' and b['all_pools_before_variants'] and b['metric_rows']==156,'BASELINE_ALL_POOLS')
    need(b['method_freeze_sha256']==sha(SCIENCE/'METHOD_FREEZE.json'),'FREEZE_SHA')
    expected_pools={'CIC_DEV':179886,'UNSW_DEV':148316,'EDGE':60000}
    for pool,r in b['pools'].items():
        need(r['status']=='PASS' and r['max_score_abs_error']==0 and r['uid_head_decision_differences']==0,'BASELINE_EXACT')
        need(r['rows']==expected_pools[pool],'BASELINE_N')
        need(r['raw_support_field']=='support3' and r['support3_before_guard'],'SUPPORT_SEMANTICS')
        need(r['input_artifact']==freeze['result_artifacts'][pool] and r['reference']==freeze['references'][pool],'CACHE_REFERENCE_IDENTITY')
    need(sum(r['rows'] for r in b['pools'].values())==388202,'TOTAL_QUERIES')
    need(b['pools']['UNSW_DEV']['raw_support_positive_on_historical_zero_rows']==2306,'HISTORICAL_ZERO_NOT_RAW_SUPPORT')
    identity=read(SOURCE/'results/ASSET_IDENTITY.json');need(identity['package_manifest_sha256']==sha(SCIENCE/'PACKAGE_MANIFEST.json'),'RUNTIME_PACKAGE_SHA')
    need(identity['method_freeze_sha256']==sha(SCIENCE/'METHOD_FREEZE.json'),'RUNTIME_FREEZE_SHA')
    manifest=read(SCIENCE/'PACKAGE_MANIFEST.json')
    for name,digest in manifest['files'].items():need(sha(SCIENCE/name)==digest,'CODE_PAYLOAD_SHA')
    for name in ['run.py','analysis_core.py']:
        gitbytes=subprocess.check_output(['git','show','f3c754a:'+str((SCIENCE/name).relative_to(ROOT)).replace('\\','/')],cwd=ROOT)
        need(hashlib.sha256(gitbytes).hexdigest()==sha(SCIENCE/name),'COMMITTED_CODE_IDENTITY')
    loc=read(SOURCE/'results/DEPENDENCY_LOCATIONS.json')
    need(loc['status']=='PASS' and loc['history_inventory_semantic_parity'] and len(loc['files'])==67,'DEPENDENCY_LOCATIONS')
    need(sum(v['isolated_provenance'] for v in loc['files'].values())==4,'FOUR_PROVENANCE_ONLY')
    merged={};stage_pairs={};uid_manifest={};stage_info={}
    for stage in ['guard','exponent']:
        folder=SOURCE/'results'/stage;complete=read(folder/'COMPLETE.json');v=read(folder/'VERIFICATION.json')
        need(complete['status']=='PASS' and complete['verification_sha256']==sha(folder/'VERIFICATION.json'),'ITEM_COMPLETE_SHA')
        need(v['status']=='PASS' and not v['distances_recomputed'] and not v['trained'] and not v['threshold_refit'] and v['raw_support3'],'ITEM_SCOPE')
        need(v['baseline_acceptance_sha256']==sha(SOURCE/'results/BASELINE_ACCEPTANCE.json'),'ITEM_BASELINE_SHA')
        need(all(x['status']=='PASS' for x in v['invariants'].values()),'RUNTIME_QUERY_INVARIANTS')
        for n,digest in v['output_sha256'].items():need(sha(folder/n)==digest,'ITEM_OUTPUT_SHA')
        metrics=read(folder/'METRICS.json');pairs=read(folder/'PAIRED_CHANGES.json');csv_parity(folder/'METRICS.csv',metrics);csv_parity(folder/'PAIRED_CHANGES.csv',pairs)
        need(v['metrics_rows']==len(metrics) and v['pair_rows']==len(pairs),'ITEM_TABLE_ROWS')
        for r in metrics:
            key=metric_key(r)
            if key in merged:need(merged[key]==r,'SHARED_BASE_IDENTICAL')
            merged[key]=r
            need(0<=r['alarm_count']<=r['rows'] and r['rows']>0,'METRIC_COUNT')
            need(close(r['sample_rate'],r['alarm_count']/r['rows']),'ORDINARY_RATE')
            need(r['weighted_denominator']>0 and 0<=r['weighted_numerator']<=r['weighted_denominator']+1e-12,'WEIGHT_MASS')
            need(close(r['hierarchical_rate'],r['weighted_numerator']/r['weighted_denominator']),'WEIGHTED_RATE')
            if 'HT_rate' in r:need(close(r['HT_rate'],r['ht_alarm_total']/r['HT_denominator']),'HT_RATE')
        for r in pairs:
            left=merged[pair_metric_key(r,'left')];right=merged[pair_metric_key(r,'right')]
            need(r['rows']==left['rows']==right['rows'],'PAIRED_POPULATION')
            need(r['n00']+r['n01']+r['n10']+r['n11']==r['rows'],'PAIRED_PARTITION')
            need(r['n10']+r['n11']==left['alarm_count'] and r['n01']+r['n11']==right['alarm_count'],'PAIRED_MARGINALS')
            need(close(sum(r['weighted_n'+k] for k in ['00','01','10','11']),r['weighted_denominator']),'WEIGHTED_PARTITION')
            need(close(r['weighted_n10']+r['weighted_n11'],left['weighted_numerator']),'LEFT_WEIGHTED_MARGINAL')
            need(close(r['weighted_n01']+r['weighted_n11'],right['weighted_numerator']),'RIGHT_WEIGHTED_MARGINAL')
            if 'ht_n10' in r:
                need(close(r['ht_n10']+r['ht_n11'],left['ht_alarm_total']),'LEFT_HT_MARGINAL')
                need(close(r['ht_n01']+r['ht_n11'],right['ht_alarm_total']),'RIGHT_HT_MARGINAL')
            if stage=='guard':
                need(r['n01']==0,'GUARD_OFF_SUBSET')
                if r['guard_stratum']=='GUARD_OFF':need(r['n10']==0,'ONLY_GUARDED_QUERY_CHANGED')
            else:
                power={'P1':1,'P2':2,'BASE':3,'P4':4};increasing=power[r['left']]<power[r['right']]
                need(r['n01' if increasing else 'n10']==0,'EXPONENT_ALERT_MONOTONICITY')
                if r['guard_stratum']=='GUARD_ON':need(r['n10']+r['n01']==0,'GUARD_BYPASS_STABLE')
        # Validate unique-changed-UID counts without downloading the UID files.
        um=read(folder/'CHANGED_UID_MANIFEST.json')
        pair_names=sorted({(r['pool'],r['left'],r['right']) for r in pairs})
        for pool,left,right in pair_names:
            n=pool+'_'+left+'_vs_'+right+'_changed.jsonl.gz';item=um[n]
            counts=[]
            for head in ['27','127','227','ensemble']:
                rr=[r for r in pairs if (r['pool'],r['left'],r['right'],r['head'],r['view'],r['guard_stratum'])==(pool,left,right,head,'full','ALL') and r['group'] in ['NORMAL','ATTACK']]
                need(len(rr)==2,'UID_COUNT_BASE_GROUPS');counts.append(sum(r['n01']+r['n10'] for r in rr))
            need(max(counts)<=item['rows']<=sum(counts),'UID_UNION_BOUNDS')
            need(re.fullmatch('[a-f0-9]{64}',item['sha256']) is not None,'UID_SHA_FORMAT')
            uid_manifest[stage+'/'+n]=dict(item,remote_path='/public/home/jiangxinwei.zr/work/paper04/runs/paper_reading_ablations_v2_20261111/results/'+stage+'/'+n)
        stage_pairs[stage]=pairs;stage_info[stage]=dict(metrics=len(metrics),pairs=len(pairs),seconds=v['seconds'],verification_sha256=sha(folder/'VERIFICATION.json'))
    metrics=list(merged.values());need(len(metrics)==3680 and {r['config'] for r in metrics}=={'BASE','GUARD_OFF','P1','P2','P4'},'EXACTLY_FIVE_CONFIGS')
    frozen=read(SCIENCE/'BASE_EXPECTED_METRICS.json')
    for r in frozen:
        actual=merged[('BASE',r['pool'],r['view'],r['head'],r['group'],'ALL')]
        for k in ['rows','alarm_count','sample_rate','hierarchical_rate','HT_rate']:
            if k in r:need(close(actual[k],r[k]),'FROZEN_FULL_METRIC_PARITY')
    # Guard-on/off partitions sum to ALL for every reported metric stratum.
    for key,r in merged.items():
        if key[-1]!='ALL':continue
        parts=[merged[key[:-1]+(v,)] for v in ['GUARD_ON','GUARD_OFF'] if key[:-1]+(v,) in merged]
        for field in ['rows','alarm_count','weighted_numerator','weighted_denominator']:need(close(sum(x[field] for x in parts),r[field]),'GUARD_STRATA_PARTITION')
    save('METRICS.json',metrics);csv_table('METRICS.csv',metrics)
    pairs=[dict(experiment=stage,**r) for stage,rr in stage_pairs.items() for r in rr];save('PAIRED_CHANGES.json',pairs);csv_table('PAIRED_CHANGES.csv',pairs);save('CHANGED_UID_MANIFEST.json',uid_manifest)
    main=[r for r in metrics if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['view']==('full' if r['pool']=='EDGE' else 'post_window_primary') and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']]
    headers=['Pool','View','Config','Group','Alarms/N','Ordinary %','Weighted %','HT %']
    table_rows=[[r['pool'],r['view'],r['config'],r['group'],f"{r['alarm_count']}/{r['rows']}",f"{100*r['sample_rate']:.6f}",f"{100*r['hierarchical_rate']:.6f}",f"{100*r['HT_rate']:.6f}" if 'HT_rate' in r else '--'] for r in main]
    md_table('MAIN_METRICS.md',headers,table_rows)
    primary=lambda r:r['view']==('full' if r['pool']=='EDGE' else 'post_window_primary')
    selected_pairs=[r for r in pairs if primary(r) and r['guard_stratum']=='ALL' and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']]
    csv_table('ALL_HEAD_MAIN_PAIRED.csv',selected_pairs)
    md_table('ALL_HEAD_MAIN_PAIRED.md',['Pool','Head','Group','Left','Right','LeftOnly(n10)','RightOnly(n01)','WeightedLeftOnly pp','WeightedRightOnly pp'],[[r['pool'],r['head'],r['group'],r['left'],r['right'],r['n10'],r['n01'],f"{100*r['weighted_n10']/r['weighted_denominator']:.6f}",f"{100*r['weighted_n01']/r['weighted_denominator']:.6f}"] for r in selected_pairs])
    # Preserve small original receipts, without duplicating large UID/feature arrays.
    evidence=HERE/'evidence';evidence.mkdir(exist_ok=True)
    for n in ['BASELINE_ACCEPTANCE.json','ASSET_IDENTITY.json','DEPENDENCY_LOCATIONS.json','RUN_COMPLETE.json']:shutil.copyfile(SOURCE/'results'/n,evidence/n)
    for stage in ['guard','exponent']:
        for n in ['VERIFICATION.json','COMPLETE.json','CHANGED_UID_MANIFEST.json']:shutil.copyfile(SOURCE/'results'/stage/n,evidence/(stage+'_'+n))
    shutil.copyfile(SOURCE/'RESOURCE_USAGE.txt',evidence/'RESOURCE_USAGE.json');shutil.copyfile(DEPLOY/'ACCEPTANCE_SCHEDULER_SNAPSHOT.json',evidence/'SCHEDULER_SNAPSHOT.json')
    for stage in ['guard','exponent']:
        p=HERE/stage;p.mkdir(exist_ok=True);shutil.copyfile(SOURCE/'results'/stage/'RESULT_READOUT.md',p/'RESULT_READOUT.md')
    run=read(SOURCE/'results/RUN_COMPLETE.json');usage=read(SOURCE/'RESOURCE_USAGE.txt')
    need(run['status']=='PASS' and usage['returncode']==0 and run['configurations']==5 and not run['training'] and not run['distances_recomputed'],'COMPLETION_SCOPE')
    save('FORMAL_ACCEPTANCE.json',dict(status='PASS',checks=checks,job_id='183530',code_snapshot_commit='f3c754a',compute_cache_queries=388202,baseline_score_error=0,baseline_decision_differences=0,baseline_metric_rows=156,metric_rows=len(metrics),paired_rows=len(pairs),changed_uid_files=len(uid_manifest),original_retrieval_pins=read(DEPLOY/'RETRIEVAL.json'),stages=stage_info,resource=usage,scientific_scope='fixed five-arm sensitivity; neither parameter reselection nor general optimality',main_method_changed=False,large_artifacts='HPC only; manifests validated and union bounds checked; gzip bytes not downloaded or independently re-read in this acceptance',data_role_conflict='Edge development-role descriptions differ across current writing documents and experimental chat history; this acceptance makes no unseen-domain claim'))
    print(json.dumps(dict(status='PASS',checks=checks,metric_rows=len(metrics),paired_rows=len(pairs),uid_files=len(uid_manifest),wall_seconds=usage['wall_seconds'],peak_gib=usage['maxrss_kib']/1024**2)))
if __name__=='__main__':main()
