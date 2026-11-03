"""One bounded authorized delivery and completion worker; no agent polling loop."""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from client import HERE,PACKAGE,upload,request,retrieve,read,write,need

record={}
def progress(stage,**fields):
    if record.get('stage')!=stage:
        for k in ('file','done_bytes','total_bytes','bytes_per_second','worker','remote','network_error'):record.pop(k,None)
    record.update(stage=stage,**fields,updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'))
    try:write(HERE.parent/'history_sample_coverage_c4_deployment_20261101/PROGRESS.json',record)
    except PermissionError:pass

def local_stage(args,stage):
    progress(stage)
    with (HERE/(stage+'.log')).open('x',encoding='utf-8') as log:
        p=subprocess.Popen([sys.executable,'-X','utf8','-B',*args],cwd=PACKAGE,stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        while p.poll() is None:
            status=PACKAGE/'outputs/evaluation/STATUS.json'
            if status.exists():
                try:progress(stage,worker=read(status))
                except (OSError,ValueError):pass
            time.sleep(5)
    need(p.returncode==0,stage+'_FAILED: see '+str(HERE/(stage+'.log')))

def main():
    with (HERE/'PIPELINE_ATTEMPT.json').open('x') as f:json.dump(dict(pid=os.getpid(),automatic_science_retry=False),f)
    state=request('state');need(state['status']=='INSTALLED' and not state['submitted'],'REPAIRED_READY_STATE')
    progress('PREFLIGHT');pre=request('preflight');write(HERE/'PREFLIGHT_RECEIPT.json',pre)
    need(pre['status']=='PREFLIGHT_PASS','HPC_PREFLIGHT_FAILED')
    progress('SUBMITTING');submitted=request('submit');write(HERE/'SUBMIT_RECEIPT.json',submitted)
    need(submitted['submitted'],'SUBMISSION_FAILED');job=submitted['job_id'];progress('HPC_RUNNING',job_id=job)
    with (HERE.parent/'history_sample_coverage_c4_deployment_20261101/SUBMIT_RECEIPT.json').open('x',encoding='utf-8') as f:json.dump(dict(submitted,repair_deployment=HERE.name),f,indent=2)
    deadline=time.monotonic()+10*3600
    while time.monotonic()<deadline:
        try:state=request('state')
        except (OSError,ValueError,RuntimeError) as e:
            progress('HPC_CONNECTION_INTERRUPTED',job_id=job,network_error=str(e));time.sleep(30);continue
        write(HERE/'STATE_RECEIPT.json',state);worker=state.get('STATUS.json',{})
        progress('HPC_RUNNING',job_id=job,worker=worker,scheduler=state.get('squeue') or state.get('sacct'),network_error=None)
        if state.get('STAGE_RECEIPT.json',{}).get('technical_status')=='COMPLETED':break
        need(worker.get('technical_status')!='EXCEPTION_STOPPED','HPC_WORKER_STOPPED: '+str(worker.get('error')))
        need(not any(s in state.get('sacct','') for s in ('FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL')),'HPC_SCHEDULER_FAILURE')
        if 'COMPLETED' in state.get('sacct','') and not state.get('STAGE_RECEIPT.json'):raise RuntimeError('HPC_EXITED_WITHOUT_ENCODING_RECEIPT')
        time.sleep(30)
    else:raise TimeoutError('HPC_COMPLETION_WAIT_LIMIT')
    progress('RETRIEVING',job_id=job);encoded=retrieve()
    local_stage(['run.py','evaluate','--execute-real-data','--encoded-dir',str(encoded)],'LOCAL_EVALUATION')
    local_stage(['verify_result.py'],'INDEPENDENT_VERIFICATION')
    acceptance=read(PACKAGE/'FINAL_ACCEPTANCE.json');result=read(PACKAGE/'outputs/evaluation/RESULT.json')
    progress('COMPLETE',job_id=job,acceptance=acceptance,result=result)

if __name__=='__main__':
    try:main()
    except BaseException as e:
        progress('STOPPED',error=str(e));write(HERE/'PIPELINE_ERROR.json',dict(error=str(e),traceback=traceback.format_exc(),automatic_retry=False));raise
