"""Verify completed frozen diagnostics and derive report tables without fitting."""
import hashlib,json,math
from pathlib import Path
HERE=Path(__file__).resolve().parent

def read(n):return json.loads((HERE/n).read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(HERE/n).write_bytes((json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode())

def main():
 accepted=read('FINAL_DIAGNOSIS_ACCEPTANCE.json');retrieval=read('RETRIEVAL.json');assert accepted['scope']=='DIAGNOSTIC_EXECUTION_ONLY' and retrieval['state']['stage']=='DIAGNOSIS_COMPLETE'
 assert accepted['receipt_sha256']==retrieval['sha256']
 for n,h in accepted['receipt_sha256'].items():assert sha(HERE/n)==h,n
 for n,h in read('DELIVERY.json')['pins'].items():assert sha(HERE/n)==h,n
 r=read('DIAGNOSE_RESULT.json');assert r['status']=='PASS' and not r['training'] and not r['threshold_fitting'] and not r['model_selection']
 jobs=[]
 for phase in ['PREFLIGHT','DIAGNOSE']:
  j=read(phase+'_JOB.json');assert j['cpu']==1 and j['memory_gib']==8
  ss=[s.split('|') for s in read(phase+'_SCHEDULER.json')['stdout'].splitlines()];row=next(s for s in ss if s[0]==j['job_id']);assert row[1:3]==['COMPLETED','0:0']
  h,m,s=map(int,row[3].split(':'));jobs.append(dict(phase=phase,job_id=j['job_id'],elapsed_seconds=3600*h+60*m+s,max_rss_kib=max(int(v[4][:-1]) for v in ss if v[4].endswith('K'))))
 perm=[];factor=[];artifacts={};maxerr=0
 for pool,n in [('CIC_DEV',179886),('UNSW_DEV',148316),('EDGE',60000)]:
  d=r['pools'][pool];assert d['rows']==n and set(d['forward_checks'])=={'OLD782','REFIT782','STATS8','FUSION790'};artifacts[pool]=d['artifacts']
  for name,v in d['forward_checks'].items():assert v['forward_error']==0 and v['decomposition_decision_roundoff']==0;maxerr=max(maxerr,v['decomposition_error'])
  assert d['functional_summary']['OLD782']==d['functional_summary']['REFIT782']
  for arm,f in d['functional_summary'].items():
   assert set(f['coalitions'])==set(map(str,range(8))) and len(f['permutations'])==6
   # Every reported rate agrees with its count; perturbations cannot exceed cohort size.
   for v in f['coalitions'].values():
    for g,classes in v.items():
     for label,heads in classes.items():
      for head,m in heads.items():
       if m['rows']:assert math.isclose(m['sample_rate'],m['alarms']/m['rows'],abs_tol=1e-14)
   for key,groups in f['permutations'].items():
    for g,heads in groups.items():
     for h,m in heads.items():assert m['changed_decisions']==m['added_alarms']+m['removed_alarms']<=m['rows']
   for block in ['E3','Q14','CONTEXT8']:
    for seed in [20261105,20261106]:
     values={}
     for lab,num in [('normal',0),('attack',1)]:
      base=f['coalitions']['7']['pool'][lab]['ensemble'];v=f['permutations'][block+'_'+str(seed)]['label:'+str(num)]['ensemble'];count=base['alarms']+v['added_alarms']-v['removed_alarms'];assert 0<=count<=base['rows']
      values[lab]=dict(rows=base['rows'],base_alarms=base['alarms'],permuted_alarms=count,base_rate=base['sample_rate'],permuted_rate=count/base['rows'],changed=v['changed_decisions'],median_abs_score_change=v['absolute_delta']['p50'])
     perm.append(dict(pool=pool,arm=arm,block=block,seed=seed,metrics=values))
  for key,values in d['c5_factorial'].items():
   factor.append(dict(pool=pool,configuration=key,heads={h:dict(normal=values['pool']['normal'][h],attack=values['pool']['attack'][h],HTTP=values.get('scenario:HTTP',{}).get('attack',{}).get(h),UDP=values.get('scenario:UDP',{}).get('attack',{}).get(h)) for h in ['27','127','227','ensemble']}))
 e=r['pools']['EDGE'];udp=e['input_profile']['1:17:UDP'];assert udp['tokenized_input_unique']==1 and udp['E3']['varying_dimensions_above_1e_6']==0 and udp['Q14']['unique_float32_rows']==1
 assert all(v['new_FP']['outside_fit_range_count']==0 for v in e['normal_errors_primary'].values())
 # Shapley decomposition of the 2x2x2 *false-positive counts*, not learned causal effects.
 factorial_shapley={}
 for h in ['27','127','227','ensemble']:
  counts={}
  for mask in range(8):
   arms=['FUSION790' if mask&(1<<i) else 'OLD782' for i in range(3)];key=arms[0]+'__cut_'+arms[1]+'__scale_'+arms[2];counts[mask]=e['c5_factorial'][key]['pool']['normal'][h]['alarms']
  attrib=[]
  for b in range(3):
   value=0.
   for mask in range(8):
    if mask&(1<<b):continue
    size=bin(mask).count('1');value+=math.factorial(size)*math.factorial(2-size)/6*(counts[mask|(1<<b)]-counts[mask])
   attrib.append(value)
  assert abs(sum(attrib)-(counts[7]-counts[0]))<1e-9
  factorial_shapley[h]=dict(old_FP=counts[0],new_FP=counts[7],score_function=attrib[0],threshold=attrib[1],scale=attrib[2],meaning='Order-averaged finite counterfactual count attribution; interactions allocated; not a deployable scale rule')
 write('DIAGNOSTIC_TABLES.json',dict(permutation=perm,c5_factorial=factor,factorial_count_attribution=factorial_shapley))
 write('COMPLETION_AUDIT.json',dict(status='PASS',scope='Local receipt/code pin audit, arithmetic and all registered arms; large artifacts retained remotely, no independent raw rerun this turn',jobs=jobs,total_elapsed_seconds=sum(j['elapsed_seconds'] for j in jobs),peak_rss_gib=max(j['max_rss_kib'] for j in jobs)/1024**2,forward_max_abs_error=0,decomposition_max_abs_error=maxerr,decomposition_decision_changes=0,receipt_sha256=accepted['receipt_sha256'],interpretation='Functional use established; external feature and score/calibration/C5 compatibility limitations remain',new_training_jobs=0))
 write('REMOTE_ARTIFACTS.json',dict(root='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name,files={pool:{'DIAGNOSE_'+pool+'_'+name:value for name,value in entries.items()} for pool,entries in artifacts.items()}))
 import matplotlib
 matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 import numpy as np
 fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
 for i,pool in enumerate(['CIC_DEV','UNSW_DEV']):
  p=next(v for v in perm if v['pool']==pool and v['arm']=='OLD782' and v['block']=='E3' and v['seed']==20261105);m=p['metrics']['attack'];axes[0].bar([i*3,i*3+1],[100*m['base_rate'],100*m['permuted_rate']],color=['#4c78a8','#e28b34'])
 axes[0].set_xticks([.5,3.5],['A / CIC_DEV','B / UNSW_DEV']);axes[0].set_ylim(0,110);axes[0].set_ylabel('RAW sample attack recall (%)');axes[0].set_title('OLD782: original (blue) vs E3 shuffled (orange)')
 conf=['FUSION790__cut_OLD782__scale_OLD782','FUSION790__cut_FUSION790__scale_OLD782','FUSION790__cut_OLD782__scale_FUSION790','FUSION790__cut_FUSION790__scale_FUSION790']
 vals=[e['c5_factorial'][v]['pool']['normal']['127']['alarms']/200 for v in conf];bars=axes[1].bar(range(4),vals,color=['#4c78a8','#4c78a8','#e28b34','#c94c4c']);axes[1].bar_label(bars,labels=[f'{v:.3f}%' for v in vals],padding=4);axes[1].set_ylim(0,30);axes[1].set_xticks(range(4),['Old cut\nOld scale','New cut\nOld scale','Old cut\nNew scale','New cut\nNew scale']);axes[1].set_ylabel('Edge normal sample FPR (%)');axes[1].set_title('Seed 127: same FUSION790 scores, fixed contrasts')
 fig.savefig(HERE/'DIAGNOSTIC_EVIDENCE.png',dpi=180);fig.savefig(HERE/'DIAGNOSTIC_EVIDENCE.pdf');plt.close(fig)
 print('DIAGNOSIS_AUDIT_PASS',sum(j['elapsed_seconds'] for j in jobs),factorial_shapley)
if __name__=='__main__':main()
