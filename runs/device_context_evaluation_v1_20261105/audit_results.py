"""Read-only receipt audit and derived tables/figures; never fit or select a model."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent

def read(n):return json.loads((HERE/n).read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode())

def main():
 acceptance=read('FINAL_EVALUATION_ACCEPTANCE.json');retrieval=read('RETRIEVAL.json')
 assert acceptance['scope']=='ENGINEERING_COMPLETION_NOT_EFFICACY' and retrieval['state']['stage']=='EVALUATION_COMPLETE'
 assert acceptance['receipt_sha256']==retrieval['sha256']
 for n,h in acceptance['receipt_sha256'].items():assert digest(HERE/n)==h,n
 for n,h in read('DELIVERY.json')['pins'].items():assert digest(HERE/n)==h,n
 jobs=[]
 for phase in ['PREFLIGHT','CONTEXT','AB','EDGE']:
  job=read(phase+'_JOB.json');result=read(phase+'_RESULT.json');scheduler=read(phase+'_SCHEDULER.json')
  assert result['status']=='PASS' and job['cpu']==1 and job['memory_gib']==8
  lines=[s.split('|') for s in scheduler['stdout'].splitlines()];line=next(s for s in lines if s[0]==job['job_id']);assert line[1:3]==['COMPLETED','0:0']
  hours,minutes,seconds=map(int,line[3].split(':'));elapsed=3600*hours+60*minutes+seconds
  rss=max(int(s[4][:-1]) for s in lines if s[4].endswith('K'));jobs.append(dict(phase=phase,job_id=job['job_id'],elapsed_seconds=elapsed,max_rss_kib=rss))
 pre=read('PREFLIGHT_RESULT.json')['checks']['real_encoder_distance'];assert pre['e3_max_abs_error']==pre['cached_support_error']==pre['fresh_support_error']==0
 context=read('CONTEXT_RESULT.json');assert sum(v['rows'] for v in context['roles'].values())==60000
 assert all(v['restart_queries']>0 and v['max_clock_debt_ns']<=10**9 and v['peak_entries']<=1000000 for v in context['roles'].values())
 ab=read('AB_RESULT.json');edge=read('EDGE_RESULT.json');rows=[];abrows=[];failures={}
 assert edge['rows']==60000 and edge['old_forward_error']==0 and len(edge['arms'])==4
 assert edge['arms']['OLD782']==edge['arms']['REFIT782'],'REFIT_METRIC_PARITY'
 for arm,r in edge['arms'].items():
  assert set(r['methods'])==({'RAW'} if arm=='STATS8' else {'RAW','C5_P3'})
  for method,v in r['methods'].items():
   assert set(v['heads'])=={'27','127','227','ensemble'}
   for head,h in v['heads'].items():
    for role,s in h['roles'].items():
     assert s['selected_rows']==20000 and s['alarm_count']+s['no_alarm_count']==20000
     assert math.isclose(s['exact_selected_sample_alarm_rate'],s['alarm_count']/20000,abs_tol=1e-14)
     assert math.isclose(s['ht_population_alarm_estimate'],s['ht_expanded_alarm_count']/s['population_count'],abs_tol=1e-14)
     if method!='RAW':assert s['alarm_count']<=r['methods']['RAW']['heads'][head]['roles'][role]['alarm_count']
     rows.append(dict(arm=arm,method=method,head=head,role=role,rows=20000,alarms=s['alarm_count'],sample_rate=s['exact_selected_sample_alarm_rate'],ht_rate=s['ht_population_alarm_estimate'],hierarchical_rate=s['selected_hierarchical_alarm_rate'],safety=h['raw_cumulative_safety']['status']))
 for pool,v in ab['pools'].items():
  assert v['old_forward_error']==0 and v['primary']['OLD782']==v['primary']['REFIT782']
  failures[pool]=[c for c in v['gates']['checks'] if c['status']=='FAIL']
  assert v['gates']['status']==('FAIL' if failures[pool] else 'PASS')
  for arm,methods in v['primary'].items():
   for method,heads in methods.items():
    for head,h in heads.items():
     for group,labels in h['groups'].items():
      for label,m in labels.items():
       assert m['rows']==m['alarm_count']+m['no_alarm_count']
       if m['rows']:assert math.isclose(m['unweighted_rate'],m['alarm_count']/m['rows'],abs_tol=1e-14)
     abrows.append(dict(pool=pool,arm=arm,method=method,head=head,groups=h['groups'],c5_safety=h['c5_safety']['status']))
 assert ab['source_cal']['gates']['status']=='PASS'
 write('RESULT_TABLES.json',dict(edge=rows,ab=abrows,failures=failures))
 audit=dict(status='PASS',scope='Receipt identities, pinned evaluator code, all registered heads, counts/rates, scheduler resources; no large-array download or new scoring',engineering='PASS',scientific_acceptance='NOT_PASSED',ab_gates=acceptance['scientific_gates'],edge_fusion_c5_safety={h:v['raw_cumulative_safety']['status'] for h,v in edge['arms']['FUSION790']['methods']['C5_P3']['heads'].items()},jobs=jobs,total_elapsed_seconds=sum(j['elapsed_seconds'] for j in jobs),peak_rss_gib=max(j['max_rss_kib'] for j in jobs)/1024**2,receipt_sha256=acceptance['receipt_sha256'],refit_old_report_parity=True,real_encoder_distance=pre,model_selection=False,new_jobs=0)
 write('COMPLETION_AUDIT.json',audit)
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 fig,axes=plt.subplots(2,2,figsize=(11,7),layout='constrained')
 for row,role in enumerate(['HTTP','UDP']):
  for col,arm in enumerate(['OLD782','FUSION790']):
   ax=axes[row,col];v=edge['margins'][arm]['scenario:'+role]['ensemble'];hist=v['raw_margin_histogram'];edges=np.asarray(hist['edges']);counts=np.asarray(hist['counts'])
   if edges[-1]-edges[0]<1e-4:ax.bar([v['raw_margin']['p50']],[100],width=.8,color='#4a79a8')
   else:ax.bar(edges[:-1],100*counts/sum(counts),width=np.diff(edges),align='edge',color='#4a79a8')
   ax.axvline(0,color='black',lw=1,label='Decision boundary');ax.axvline(v['correction_bound'],color='#c44e52',ls='--',label='Maximum C5 deduction')
   ax.set_title(arm+' / '+role);ax.set_xlabel('RAW ensemble score minus frozen CAL threshold');ax.set_ylabel('Selected queries (%)');ax.set_xlim(-35,55)
   ax.text(.02,.95,'Median %.2f | margin > bound: %.2f%%'%(v['raw_margin']['p50'],100*v['fraction_margin_gt_bound']),transform=ax.transAxes,va='top',fontsize=9)
 axes[0,0].legend(fontsize=8,loc='center left');fig.suptitle('Edge fixed diagnostic sample: RAW margin distributions (n=20,000 per role)')
 fig.savefig(HERE/'EDGE_MARGIN_DISTRIBUTIONS.png',dpi=180);fig.savefig(HERE/'EDGE_MARGIN_DISTRIBUTIONS.pdf');plt.close(fig)
 write('ARTIFACT_SHA256.json',{n:digest(HERE/n) for n in ['COMPLETION_AUDIT.json','RESULT_TABLES.json','EDGE_MARGIN_DISTRIBUTIONS.png','EDGE_MARGIN_DISTRIBUTIONS.pdf']})
 print(json.dumps({k:audit[k] for k in ['status','engineering','scientific_acceptance','total_elapsed_seconds','peak_rss_gib']}))
if __name__=='__main__':main()
