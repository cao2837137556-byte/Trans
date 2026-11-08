"""Bounded single-allocation qualification, subprocess isolation, measured RSS."""
import json, os, subprocess, sys, time
from pathlib import Path
import psutil
from worker import HERE,read,write,sha,dependencies
PHASES=['PIPELINE','FIDELITY','TabM','TabR','SLAD','NCA_SCALE']
CAPS=dict(PIPELINE=1800,FIDELITY=600,TabM=600,TabR=1200,SLAD=900,NCA_SCALE=1800)
def main():
 dependencies();start=time.monotonic();results={}
 for i,phase in enumerate(PHASES):
  t=time.monotonic();cap=CAPS[phase];peak=0.;reason=None
  with (HERE/(phase+'.log')).open('wb') as log:
   p=subprocess.Popen([sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),'--phase',phase],stdout=log,stderr=log)
   while p.poll() is None:
    try:peak=max(peak,sum(x.memory_info().rss for x in [psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True))/2**20)
    except psutil.NoSuchProcess:pass
    detail=read(HERE/'DETAIL.json') if (HERE/'DETAIL.json').exists() else {}
    write('PROGRESS.json',dict(version='BASELINE_FIDELITY_V2',stage='RUNNING',phase=phase,job_id=os.environ.get('SLURM_JOB_ID'),done=i,total=len(PHASES),detail=detail.get('detail',phase),inner_done=detail.get('done'),inner_total=detail.get('total'),results=results,rss_mib=peak,updated_unix=time.time()))
    if time.monotonic()-t>cap:reason='STAGE_TIME_BUDGET'
    if peak>7168:reason='STAGE_MEMORY_BUDGET'
    if reason:p.terminate();p.wait(timeout=20);break
    time.sleep(2)
  resultfile=HERE/(phase+'_RESULT.json')
  if p.returncode==0 and resultfile.exists():r=read(resultfile)
  else:
   stop=HERE/(phase+'_STOP.json');r=dict(status='NEEDS_RESOURCES' if reason else 'FAIL',error=reason or (read(stop)['error'] if stop.exists() else 'EXIT_'+str(p.returncode)))
  r.update(seconds=time.monotonic()-t,rss_peak_mib=peak);write(phase+'_RESULT.json',r);results[phase]=r
  if r['status']!='PASS':
   write('RESULT.json',dict(status='INCOMPLETE',results=results,seconds=time.monotonic()-start,automatic_retries=0));write('PROGRESS.json',dict(version='BASELINE_FIDELITY_V2',stage='STOP',phase=phase,error=r.get('error'),job_id=os.environ.get('SLURM_JOB_ID'),done=i,total=len(PHASES),results=results,updated_unix=time.time()));return 1
 dependencies();write('RESULT.json',dict(status='PASS',scope='ENGINEERING_ONLY',full_training_authorized=False,results=results,seconds=time.monotonic()-start))
 write('PROGRESS.json',dict(version='BASELINE_FIDELITY_V2',stage='COMPLETE',job_id=os.environ.get('SLURM_JOB_ID'),done=len(PHASES),total=len(PHASES),detail='真实预检结束，正式训练资源与调参仍须单独封存',results=results,updated_unix=time.time()));return 0
if __name__=='__main__':sys.exit(main())
