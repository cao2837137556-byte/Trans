"""Audit frozen compact receipts; no model fitting or large-array retrieval."""
import hashlib,json,math
from pathlib import Path
import scoreboard
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'fusion_anchor_evaluation_v1_20261105'
ARMS=scoreboard.ARMS;HEADS=scoreboard.HEADS;checks=0
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())
def check(x):
 global checks
 assert x;checks+=1
def near(x,y):check(math.isclose(x,y,abs_tol=1e-10,rel_tol=1e-9))
def same(a,b):
 if isinstance(a,dict):
  check(set(a)==set(b))
  for k in a:same(a[k],b[k])
 elif isinstance(a,list):
  check(len(a)==len(b))
  for x,y in zip(a,b):same(x,y)
 elif isinstance(a,(int,float)) and not isinstance(a,bool):near(a,b)
 else:check(a==b)
def goal(f,rs):return 'PASS' if f<.02 and all(v>=.999 for v in rs) else 'FAIL'
def count_metric(m,nkey,ratekey):
 n=m[nkey];v=m['alarm_count'];check(isinstance(n,int) and 0<=v<=n)
 check(m['no_alarm_count']==n-v)
 if n:near(m[ratekey],v/n)
def main():
 done=read(HERE/'EVALUATION_COMPLETION.json');ret=read(HERE/'RETRIEVAL.json');state=read(HERE/'CHAIN_STATE.json')
 check(done['scope']=='ENGINEERING_COMPLETION_NOT_EFFICACY');check(ret['state']['stage']==state['stage']=='PILOT_TRANSFER_EVALUATION_COMPLETE')
 check(done['receipt_sha256']==ret['sha256'])
 for n,h in done['receipt_sha256'].items():check(sha(HERE/n)==h)
 for n,h in read(HERE/'DELIVERY.json')['pins'].items():check(sha(HERE/n)==h)
 resources={}
 for phase in ['PREFLIGHT','AB','EDGE']:
  d=read(HERE/(phase+'_RESULT.json'));check(d['status']=='PASS')
  for k in ['training','threshold_fitting','model_selection']:check(d[k] is False)
  job=read(HERE/(phase+'_JOB.json'));sched=read(HERE/(phase+'_SCHEDULER.json'));check(sched['returncode']==0)
  lines=[x.split('|') for x in sched['stdout'].splitlines()];row=next(x for x in lines if x[0]==job['job_id']);check(row[1:3]==['COMPLETED','0:0'])
  h,m,s=map(int,row[3].split(':'));seconds=h*3600+m*60+s
  check(seconds<=job['wall_seconds'] and job['cpu']==1 and job['memory_gib']==8)
  peak=max([int(x[4][:-1])*1024 for x in lines if x[4].endswith('K')]+[0]);check(0<peak<8*1024**3)
  resources[phase]=dict(job=job['job_id'],seconds=seconds,slurm_peak_bytes=peak,process_peak_bytes=d['rss_peak_bytes'])
 pre=read(HERE/'PREFLIGHT_RESULT.json');enc=pre['real_encoder_distance']
 check(enc['status']=='PASS' and enc['encoded_rows']==112 and enc['encoded_batches']==7 and enc['query_rows']==4 and enc['reference_rows']==4124)
 for k in ['e3_max_abs_error','cached_support_error','fresh_support_error']:near(enc[k],0)
 ab=read(HERE/'AB_RESULT.json');edge=read(HERE/'EDGE_RESULT.json');oldab=read(OLD/'AB_RESULT.json');olde=read(OLD/'EDGE_RESULT.json')
 board={};large={};safeties={};gates={};margins={};trans={}
 for pool,d in ab['pools'].items():
  check((d['rows'],d['primary_rows'])==({'CIC_DEV':(179886,175097),'UNSW_DEV':(148316,146997)}[pool]))
  for v in d['baseline_errors'].values():near(v,0)
  for arm in ['OLD782','FUSION790']:same(d['primary'][arm],oldab['pools'][pool]['primary'][arm])
  safeties[pool]={};gates[pool]=d['candidate_gates'];large[pool]=d['scores'];trans[pool]=d['transitions_vs_fusion']
  for arm in ARMS:
   safeties[pool][arm]={}
   g=d['candidate_gates'][arm];check(g['status']==('FAIL' if any(x['status']=='FAIL' for x in g['checks']) else 'PASS'))
   for method in ['RAW','C5_P3']:
    for head in HEADS:
     metric=d['primary'][arm][method][head]
     for group in metric['groups'].values():
      for m in group.values():count_metric(m,'rows','unweighted_rate')
     n=metric['groups']['pool']['normal'];a=metric['groups']['pool']['attack'];check(n['rows']+a['rows']==d['primary_rows'])
     if method=='C5_P3':
      safeties[pool][arm][head]=metric['c5_safety']
      raw=d['primary'][arm]['RAW'][head]['groups']['pool']
      check(n['alarm_count']<=raw['normal']['alarm_count'] and a['alarm_count']<=raw['attack']['alarm_count'])
  board[pool]=scoreboard.extract(d['primary'])
 for v in edge['baseline_errors'].values():near(v,0)
 for arm in ['OLD782','FUSION790']:same(edge['arms'][arm],olde['arms'][arm])
 safeties['EDGE']={};margins['EDGE']={};large['EDGE']=edge['scores'];trans['EDGE']=edge['transitions_vs_fusion']
 for arm in ARMS:
  safeties['EDGE'][arm]={};margins['EDGE'][arm]={}
  for head in HEADS:
   raw=edge['arms'][arm]['methods']['RAW']['heads'][head];after=edge['arms'][arm]['methods']['C5_P3']['heads'][head]
   for role in ['NORMAL','HTTP','UDP']:
    for m in [raw['roles'][role],after['roles'][role]]:count_metric(m,'selected_rows','exact_selected_sample_alarm_rate');check(m['selected_rows']==20000)
    check(after['roles'][role]['alarm_count']<=raw['roles'][role]['alarm_count'])
   safety=after['raw_cumulative_safety'];safeties['EDGE'][arm][head]=safety
   check(safety['status']==('FAIL' if any(g['status']=='FAIL' for g in safety['groups'].values()) else 'PASS'))
   margins['EDGE'][arm][head]={}
   for role in ['HTTP','UDP']:
    m=edge['margins'][arm]['scenario:'+role][head]
    check(m['withdrawn_raw_TP']==raw['roles'][role]['alarm_count']-after['roles'][role]['alarm_count'])
    near(m['delta']['p50'],edge['margins']['FUSION790']['scenario:'+role][head]['delta']['p50'])
    if role=='UDP':near(m['delta']['max'],0)
    margins['EDGE'][arm][head][role]={k:m[k] for k in ['raw_margin','corrected_margin','delta','withdrawn_raw_TP','correction_bound']}
 board['EDGE']=scoreboard.extract(edge['arms'],True)
 for pool,rows in board.items():
  same(rows,state['scoreboard'][pool])
  for row in rows:check(row['target']==goal(row['fpr'],[row['http'],row['udp']] if pool=='EDGE' else [row['recall']]))
  for arm in ARMS[1:]:
   for method,labels in trans[pool][arm].items():
    for label,t in labels.items():
     for j,head in enumerate(HEADS):
      check(t['added'][j]+t['removed'][j]+t['unchanged'][j]==t['rows'])
      if pool=='EDGE':
       roles=['NORMAL'] if label=='0' else ['HTTP','UDP']
       before=sum(edge['arms']['FUSION790']['methods'][method]['heads'][head]['roles'][r]['alarm_count'] for r in roles)
       after=sum(edge['arms'][arm]['methods'][method]['heads'][head]['roles'][r]['alarm_count'] for r in roles)
      else:
       key='normal' if label=='0' else 'attack';p=ab['pools'][pool]['primary']
       before=p['FUSION790'][method][head]['groups']['pool'][key]['alarm_count'];after=p[arm][method][head]['groups']['pool'][key]['alarm_count']
      check(after-before==t['added'][j]-t['removed'][j])
 # Guard inactive for seed227: actual fixed-domain metrics must match stratified.
 for pool,d in ab['pools'].items():
  for method in ['RAW','C5_P3']:same(d['primary']['RISK_STRATIFIED'][method]['227'],d['primary']['RISK_GUARDED'][method]['227'])
 for method in ['RAW','C5_P3']:same(edge['arms']['RISK_STRATIFIED']['methods'][method]['heads']['227'],edge['arms']['RISK_GUARDED']['methods'][method]['heads']['227'])
 check(all(r['target']=='FAIL' for r in board['EDGE']))
 check(all(r['target']=='PASS' for p in ['CIC_DEV','UNSW_DEV'] for r in board[p] if r['method']=='C5_P3' and (r['head']=='ensemble' or r['arm']!='FUSION790')))
 summary=dict(board=board,resources=resources,total_seconds=sum(v['seconds'] for v in resources.values()),safety=safeties,legacy_gates=gates,edge_margins=margins['EDGE'],transitions=trans,large_artifacts=large,checks=checks)
 write('ACCEPTANCE_SUMMARY.json',summary)
 final=dict(engineering='PASS',overall_target='NOT_ACHIEVED',AB_ensemble_C5_sample_and_weighted='ALL_FOUR_PASS',EDGE_all_heads_and_arms_joint_target='NONE_PASS',checks=checks,summary_sha256=sha(HERE/'ACCEPTANCE_SUMMARY.json'),receipt_sha256=done['receipt_sha256'],new_training=False,large_arrays_rescored_locally=False,limitations=['Compact metrics and receipt hashes audited, not independent re-inference of large HPC arrays.','Consumed development datasets, not untouched external confirmation.','Source NO_GO and original scientific gates remain unchanged.'])
 write('FINAL_EVALUATION_ACCEPTANCE.json',final);print(json.dumps({'engineering':'PASS','checks':checks,'seconds':summary['total_seconds'],'goal':'NOT_ACHIEVED'}))
if __name__=='__main__':main()
