"""Local-only acceptance of retrieved summaries; never a remote runtime dependency."""
from pathlib import Path
import json,hashlib,math
P=Path(__file__).resolve().parent;ROOT=P.parents[1];checks=0
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def check(value):
 global checks
 checks+=1;assert value,checks
def main():
 completion=read(P/'EVALUATION_COMPLETION.json');check(completion['status']=='PASS')
 for name,h in completion['receipt_sha256'].items():check(sha(P/name)==h)
 for name,h in read(P/'DELIVERY.json')['pins'].items():check(sha(P/name)==h)
 d=read(P/'DIAGNOSE_RESULT.json');pre=read(P/'PREFLIGHT_RESULT.json');old=read(ROOT/'runs/context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json')
 spec=read(P/'SPEC.json');check(sha(ROOT/'runs/context_geometry_attribution_v2_20261106/DIAGNOSE_RESULT.json')==spec['prior_result_sha256'])
 elapsed=0;jobs=[]
 for phase,cap in [('PREFLIGHT',1800),('DIAGNOSE',5400)]:
  job=read(P/(phase+'_JOB.json'));check(job['cpu']==1 and job['memory_gib']==8 and job['wall_seconds']==cap)
  row=next(v for v in read(P/(phase+'_SCHEDULER.json'))['stdout'].splitlines() if v.startswith(job['job_id']+'|'));fields=row.split('|');check(fields[1:3]==['COMPLETED','0:0']);h,m,s=map(int,fields[3].split(':'));seconds=h*3600+m*60+s;check(seconds<=cap);elapsed+=seconds;jobs.append(dict(job_id=job['job_id'],seconds=seconds))
 check(pre['status']==d['status']=='PASS' and not d['training'] and not d['deployment_change']);check(pre['forecast_seconds']<5400);check(max(pre['rss_peak_bytes'],d['rss_peak_bytes'])<8*1024**3)
 check(pre['real_encoder']['status']=='PASS' and pre['real_encoder']['e3_max_abs_error']==0)
 oracle_count=0;row_count=0;exceptions=[];primary_heads_pass=True
 methods={'RAW','C5_FROZEN','C5_2D_FUSION','C5_2D_OLD','C5_3D_FUSION','C5_3D_OLD'};heads={'27','127','227','ensemble'}
 for pool,r in d['pools'].items():
  g=r['parity_gate'];row_count+=r['rows'];check(g['status']=='PASS' and g['support_excluded_rows']==0 and g['support_compared_rows']==r['rows']);check(g['decision_differences']==0 and g['score_max_abs_error']<=2e-10 and g['support_max_abs_error']<=2e-10)
  op=pre['pools'][pool]['optimization_parity'];check(op['status']=='PASS' and op['donor_uids_and_metadata_exact']);check(all(x<=2e-10 for x in op['max_abs_errors'].values()))
  for v in pre['pools'][pool].get('oracle_replay',{}).values():oracle_count+=v['oracle_checks'];check(v['oracle_checks']==8)
  if pool=='UNSW_DEV':
   for v in pre['pools'][pool]['history_replay'].values():check(v['decoded_hist_dev']==0 and v['frames']==v['bank_end_frame'])
  for view,mm in r['views'].items():
   check(set(mm)==methods)
   for method,hh in mm.items():
    check(set(hh)==heads)
    for head,rr in hh.items():
     for role,v in rr.items():
      check(type(v['rows']) is int and type(v['alarm_count']) is int and 0<=v['alarm_count']<=v['rows']);check(abs(v['sample_rate']-v['alarm_count']/v['rows'])<1e-12)
      check(0<=v['hierarchical_rate']<=1+1e-12 and v['added_vs_RAW']==0)
      raw=mm['RAW'][head][role];check(v['rows']==raw['rows'] and raw['alarm_count']-v['alarm_count']==v['removed_vs_RAW'])
      if method=='C5_2D_FUSION':
       frozen=mm['C5_FROZEN'][head][role];check(v['alarm_count']==frozen['alarm_count']);check(all(abs(v[k]-frozen[k])<=2e-10 for k in ['sample_rate','hierarchical_rate']))
      if method.startswith('C5_3D'):
       base=mm[method.replace('_3D_','_2D_')][head][role];check(v['alarm_count']>=base['alarm_count'])
      if pool=='EDGE':
       expected=old['pools']['EDGE']['metrics'][method][head][role];check(v['alarm_count']==expected['alarm_count'] and v['rows']==expected['rows']);check(all(abs(v[k]-expected[k])<=2e-10 for k in ['sample_rate','hierarchical_rate','HT_rate']))
      if method=='C5_3D_OLD':
       normal=role=='NORMAL' or role.endswith('/ NORMAL');failed=[k for k in ['sample_rate','hierarchical_rate'] if (v[k]>=.02 if normal else v[k]<.999)]
       if failed:exceptions.append(dict(pool=pool,view=view,head=head,group=role,failed=failed,rates={k:v[k] for k in failed}))
       if pool!='EDGE' and view=='post_window_primary' and role in ['NORMAL','ATTACK'] and failed:primary_heads_pass=False
     if pool!='EDGE':
      for role in ['NORMAL','ATTACK']:
       device=[v for name,v in rr.items() if name.startswith('device:') and name.endswith('/ '+role)];check(sum(v['rows'] for v in device)==rr[role]['rows']);check(sum(v['alarm_count'] for v in device)==rr[role]['alarm_count'])
   if pool!='EDGE':
    for method in methods:
     for head in heads:
      full=r['views']['full'][method][head];primary=r['views']['post_window_primary'][method][head];check(full['ATTACK']['alarm_count']==primary['ATTACK']['alarm_count']);check(full['NORMAL']['rows']>=primary['NORMAL']['rows'])
  if pool!='EDGE':
   audit=r['donor_retention'];groups=[v for name,v in audit.items() if name.startswith('all/')];normal=r['views']['full']['RAW']['ensemble']['NORMAL'];check(sum(v['rows'] for v in groups)==normal['rows'])
   for group in groups:
    check(group['positive3']+group['lost_positive']==group['positive2']);check(0<=group['both_dc_over_rho_gt1']<=group['either_dc_over_rho_gt1']<=group['matched_pairs_with_context']<=group['rows'])
   for method in methods:
    for head in heads:check(sum(v['false_alarms'][method][head] for v in groups)==r['views']['full'][method][head]['NORMAL']['alarm_count'])
 check(oracle_count==56 and row_count==388202 and primary_heads_pass)
 result=dict(status='ACCEPTED_WITH_EXPLICIT_LIMITATIONS',engineering='PASS',scientific='SUPPORTED_SAME_BANK_POSTPROCESSING_IMPROVEMENT_NOT_ALL_TARGETS_MET',checks=checks,compared_rows=row_count,excluded_rows=0,history_oracle_points=oracle_count,jobs=jobs,successful_chain_seconds=elapsed,rss_sample_peak_gib=max(pre['rss_peak_bytes'],d['rss_peak_bytes'])/2**30,candidate='FUSION790 + full historical bank + C5_3D_OLD',AB_primary_all_four_heads_pooled_2pct_999=True,all_views_devices_heads_original_target=False,exceptions=exceptions,training_started=False,deployment_changed=False,evidence_role='A/B development; Edge previously consumed diagnostic transfer evaluation',receipt_sha256=completion['receipt_sha256'])
 (P/'FORMAL_ACCEPTANCE.json').write_bytes((json.dumps(result,indent=2)+'\n').encode());print(json.dumps({k:v for k,v in result.items() if k not in ['exceptions','receipt_sha256']}))
if __name__=='__main__':main()
