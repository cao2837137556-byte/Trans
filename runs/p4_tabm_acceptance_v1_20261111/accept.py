"""Small-receipt acceptance only. No model forwards, distance or bank changes."""
import csv,hashlib,json,math,shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];R=ROOT/'runs/tabm_transfer_eval_repair_v1_20261111';C=ROOT/'runs/p4_complete_bank_v1_20261111'
CHECKS=0
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,msg):
    global CHECKS
    CHECKS+=1;assert x,msg
def close(a,b):return math.isclose(a,b,rel_tol=2e-10,abs_tol=2e-12)
def key(r):return tuple(r[n] for n in ['config','pool','view','head','group','guard_stratum'])
def save(n,v):(HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
def audit_tables(folder):
    m=read(folder/'METRICS.json');p=read(folder/'PAIRED_CHANGES.json');lookup={key(r):r for r in m};need(len(lookup)==len(m),'METRIC_UNIQUE')
    for r in m:
        need(0<=r['alarm_count']<=r['rows'],'COUNT_RANGE');need(close(r['sample_rate'],r['alarm_count']/r['rows']),'ORDINARY_RATE');need(close(r['hierarchical_rate'],r['weighted_numerator']/r['weighted_denominator']),'WEIGHTED_RATE')
        if 'HT_rate' in r:need(close(r['HT_rate'],r['ht_alarm_total']/r['HT_denominator']),'HT_RATE')
    for r in p:
        tail=tuple(r[n] for n in ['pool','view','head','group','guard_stratum']);a=lookup[(r['left'],)+tail];b=lookup[(r['right'],)+tail]
        need(r['rows']==a['rows']==b['rows'],'PAIR_POPULATION');need(sum(r['n'+s] for s in ['00','01','10','11'])==r['rows'],'PAIR_PARTITION')
        need(r['n10']+r['n11']==a['alarm_count'] and r['n01']+r['n11']==b['alarm_count'],'PAIR_MARGINALS')
        need(close(r['weighted_n10']+r['weighted_n11'],a['weighted_numerator']) and close(r['weighted_n01']+r['weighted_n11'],b['weighted_numerator']),'PAIR_WEIGHT_MARGINALS')
        need(close(sum(r['weighted_n'+s] for s in ['00','01','10','11']),r['weighted_denominator']),'PAIR_WEIGHT_PARTITION')
        if 'ht_n10' in r:need(close(r['ht_n10']+r['ht_n11'],a['ht_alarm_total']) and close(r['ht_n01']+r['ht_n11'],b['ht_alarm_total']),'PAIR_HT_MARGINALS')
    for name,rr in [('METRICS',m),('PAIRED_CHANGES',p)]:
        with (folder/(name+'.csv')).open(encoding='utf8',newline='') as f:actual=list(csv.DictReader(f))
        need(len(actual)==len(rr),'CSV_COUNT')
        for a,b in zip(actual,rr):
            for k,v in a.items():
                if k not in b:need(v=='','CSV_MISSING')
                elif isinstance(b[k],str):need(v==b[k],'CSV_TEXT')
                else:need(close(float(v),b[k]),'CSV_VALUE')
    return m,p,lookup
def assert_alias(left,right,a,b):
    for k,r in left.items():
        if k[0]==a:
            t=right[(b,)+k[1:]]
            for field in ['rows','alarm_count','sample_rate','hierarchical_rate','HT_rate','weighted_numerator','weighted_denominator']:
                if field in r:need(close(r[field],t[field]),'CROSS_ITEM_ALIAS:'+field)
def main():
    for root in [C,R]:
        for n,h in read(root/'RETRIEVAL.json')['sha256'].items():need(sha(root/'received'/n)==h,'RETRIEVAL_SHA')
    need(read(R/'PROGRESS.json')['stage']=='COMPLETE','REPAIR_COMPLETE')
    for r in read(R/'received/CPU_PARITY_DIAGNOSIS.json').values():need(r['max_score_abs_error']==0 and r['decision_differences']==0 and r['differing_values']==0,'CPU_EXACT_GATE')
    folders={'controls':C/'received/results/controls','tabm_p3':R/'received/results','tabm_p4':R/'received/p4_results'};allm={};allp={};maps={};assets={}
    for name,folder in folders.items():
        completion=read(folder/('RUN_COMPLETE.json' if name=='tabm_p3' else 'COMPLETE.json'));need(completion['status']=='PASS','ITEM_COMPLETE')
        hashes=completion['output_sha256' if name=='tabm_p3' else 'outputs_sha256']
        for n,h in hashes.items():need(sha(folder/n)==h,'ITEM_OUTPUT_SHA')
        m,p,lookup=audit_tables(folder);allm[name]=m;allp[name]=p;maps[name]=lookup;dest=HERE/name;dest.mkdir(exist_ok=True)
        for path in folder.glob('*'):
            if path.suffix in ['.json','.csv','.md'] and path.name!='PROGRESS.json':shutil.copyfile(path,dest/path.name)
        assets[name]=dict(metrics=len(m),pairs=len(p),receipt_sha256=sha(folder/('RUN_COMPLETE.json' if name=='tabm_p3' else 'COMPLETE.json')))
    need(len({r['config'] for r in allm['controls']})==8,'SIX_CONTROLS_PLUS_RAW_MAIN')
    for a,b in [('RAW','MLP_RAW'),('P4_MAIN','P4_MAIN'),('P4_3D_SELF','MLP_3D_SELF_P4')]:assert_alias(maps['controls'],maps['tabm_p4'],a,b)
    for a,b in [('MLP-RAW','MLP_RAW'),('TabM-RAW','TABM_RAW'),('MLP-3D-SELF','MLP_3D_SELF_P3'),('TabM-3D-SELF','TABM_3D_SELF_P3')]:assert_alias(maps['tabm_p3'],maps['tabm_p4'],a,b)
    old=read(ROOT/'runs/paper_reading_ablations_acceptance_v1_20261111/METRICS.json')
    for r in old:
        if r['config']=='P4':
            q=maps['controls'][('P4_MAIN',)+key(r)[1:]]
            for f in ['rows','alarm_count','sample_rate','hierarchical_rate','HT_rate']:
                if f in r:need(close(r[f],q[f]),'ACCEPTED_P4_MAIN_PARITY')
    for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
        for r in allp['controls']:
            if r['pool']==pool and r['left']=='P4_MAIN' and r['right']=='P4_GUARD_OFF':
                need(r['n01']==0,'P4_GUARD_SUBSET')
                if r['guard_stratum']=='GUARD_OFF':need(r['n10']==0,'ONLY_GUARD_CHANGED')
        for r in allp['tabm_p4']:
            if r['pool']==pool and r['left']=='TABM_3D_SELF_P3' and r['right']=='TABM_3D_SELF_P4':need(r['n01']==0,'TABM_P4_MONOTONE')
    six=read(folders['controls']/'CIC_SIX_WITHDRAWALS.json');need(len(six)==6 and len({r['uid'] for r in six})==6,'SIX_QUERIES')
    for r in six:
        need(r['original_metadata']['label']==1 and r['original_metadata']['device']=='HeimVision Camera' and not r['guard'],'SIX_IDENTITY')
        need(r['deduction_p3'][3]<r['raw_margin'][3]<=r['deduction_p4'][3],'SIX_MARGIN_CROSSING')
    original=read(folders['controls']/'HISTORY_LINEAGE_COUNTS.json');corrected=read(R/'HISTORY_LINEAGE_COUNTS_CORRECTED.json')
    for pool,v in original.items():
        need(v['history_rows']==corrected[pool]['history_rows'] and v['exact_equivalence_inventory']==corrected[pool]['exact_equivalence_inventory'],'LINEAGE_COUNTS_UNCHANGED')
    for n in ['HISTORY_LINEAGE_COUNTS_CORRECTED.json','LINEAGE_METADATA_CORRECTION.json']:shutil.copyfile(R/n,HERE/n)
    for n in ['CPU_PARITY_DIAGNOSIS.json','ARITHMETIC_DIAGNOSIS.json','RESOURCE_USAGE.json','REPLACED_DEPENDENCY.json']:shutil.copyfile(R/'received'/n,HERE/n)
    cal=read(folders['tabm_p3']/'TABM_SOURCE_CALIBRATION.json');need(cal['p']==3 and cal['lambda_value']==.25 and cal['guard'] and not cal['corrected_scores_clipped'],'TABM_FIXED_PROTOCOL')
    need(max(cal['scales'])<=1 and min(cal['scales'])>=0,'TABM_PROBABILITY_SCALE')
    save('FORMAL_ACCEPTANCE.json',dict(status='PASS',checks=CHECKS,items=assets,completed_controls_job='183551',repair_job='183558',failed_job_preserved='183549',obsolete_pending_replaced='183552',original_bitwise_gate_retained=True,new_forward_in_repair=False,reference_rows_removed=0,compression_validated=False,source_scale=cal,root_cause_limit='Original GPU-host failure did not log the numeric residual; CPU same-input replays pass bitwise. Specific hardware/dispatch cause not established.',changed_uid_files='HPC only; producer SHA manifests returned, not downloaded'))
    for name,rows in allm.items():
        lines=['|池|配置|组|告警/查询|普通%|加权%|HT%|','|---|---|---|---|---|---|---|']
        for r in rows:
            if r['head']=='ensemble' and r['guard_stratum']=='ALL' and r['view']==('full' if r['pool']=='EDGE' else 'post_window_primary') and r['group'] in ['NORMAL','ATTACK','HTTP','UDP']:
                ht=f"{100*r['HT_rate']:.6f}" if 'HT_rate' in r else '--';lines.append(f"|{r['pool']}|{r['config']}|{r['group']}|{r['alarm_count']}/{r['rows']}|{100*r['sample_rate']:.6f}|{100*r['hierarchical_rate']:.6f}|{ht}|")
        (HERE/name/'MAIN_TABLE.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    print(json.dumps(dict(status='PASS',checks=CHECKS,items=assets)))
if __name__=='__main__':main()
