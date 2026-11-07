"""Audit bounded receipts and endpoint consistency; never fit or deploy a cut."""
import hashlib,json,math
from pathlib import Path
P=Path(__file__).resolve().parent
def read(n):return json.loads((P/n).read_text(encoding='utf-8-sig'))
checks=0
def check(v):
 global checks
 assert v
 checks+=1
completion=read('EVALUATION_COMPLETION.json')
for n,h in completion['receipt_sha256'].items():check(hashlib.sha256((P/n).read_bytes()).hexdigest()==h)
for n,h in read('DELIVERY.json')['pins'].items():check(hashlib.sha256((P/n).read_bytes()).hexdigest()==h)
for ph in ['PREFLIGHT','SCAN']:
 d=read(ph+'_RESULT.json');check(d['status']=='PASS');check(d['original_rate_parity_checks']==544)
 check(not d['training'] and not d['deployment_threshold_changed'])
 check(d['rss_peak_bytes']<8*1024**3)
 check('|COMPLETED|0:0|' in read(ph+'_SCHEDULER.json')['stdout'])
e=read('PREFLIGHT_RESULT.json')['real_encoder_distance']
check(e['status']=='PASS' and e['encoded_rows']==112 and e['reference_rows']==4124)
check(all(e[k]==0 for k in ['e3_max_abs_error','cached_support_error','fresh_support_error']))
d=read('SCAN_RESULT.json');count=0;ab=[]
for arm,methods in d['results'].items():
 for method,heads in methods.items():
  for head,h in heads.items():
   check(h['partitions']>1000)
   check(len(h['results'])==8)
   for scope,r in h['results'].items():
    count+=1;check(r['status']=='INFEASIBLE');check(r['feasible_point'] is None)
    lo=r['fpr_constrained'];hi=r['recall_constrained'];check(hi['cut']<lo['cut'])
    for key in r['constraints']:
     normal=key.endswith('/NORMAL')
     check(lo['rates'][key]['rate']<.02 if normal else hi['rates'][key]['rate']>=.999-1e-15)
    for point in [lo,hi,h['source_point']]:
     for key,v in point['rates'].items():
      check(math.isfinite(v['rate']) and v['denominator']>0)
      check(0<=v['alarm_count']<=v['rows'])
      if '/sample/' in key:check(abs(v['rate']-v['alarm_count']/v['rows'])<1e-15)
   if method=='C5_P3' and head=='ensemble':
    for endpoint in ['source_point','sample_fpr','all_basis_fpr']:
     point=h['source_point'] if endpoint=='source_point' else h['results']['ALL_DATASETS/'+('sample' if endpoint=='sample_fpr' else 'ALL_BASES')]['fpr_constrained']
     ok=all(v['rate']<.02 if k.endswith('/NORMAL') else v['rate']>=.999 for k,v in point['rates'].items() if not k.startswith('EDGE/'))
     ab.append(dict(arm=arm,endpoint=endpoint,all_ab_bases_pass=ok))
check(count==256)
out=dict(status='PASS',checks=checks,scope='RECEIPT_HASH_AND_SUMMARY_ENDPOINT_AUDIT',infeasible_cases=count,ab_checks=ab,
 conclusion='NO_COMMON_THRESHOLD_ON_FROZEN_SCORES',deployment_changed=False,
 limits='No independent local rescore of remote large arrays. Worker verified 544 old metrics and direct endpoint sums. Empirical diagnostic on consumed datasets, not deployment guarantee.')
(P/'ACCEPTANCE.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8')
print(json.dumps(out,indent=2))
