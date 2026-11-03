"""One bounded authorized delivery and completion worker; no agent polling loop."""
from datetime import datetime,timezone,timedelta
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
from client import HERE,PACKAGE,request,retrieve,read,write,need

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
    progress('PREFLIGHT',worker=dict(phase='启动逐阶段超算预检'))
    request('preflight')
    deadline=time.monotonic()+660
    stage_labels={'PIN_ENVIRONMENT_AND_CARD':'核对环境及执行卡','ENVIRONMENT_IMPORTS':'加载固定计算环境','SCIENTIFIC_CODE_PINS':'核对冻结源码','REAL_246_HEADER_QUALIFICATION':'核验246个真实包头','PREVIOUS_FAILURE_AND_BUDGET_RECEIPTS':'核对恢复边界和累计预算','RETAINED_CHECKPOINT_SMALL_RECEIPTS':'核对已保存的候选清单与选点','COMPLETED_ENCODING_TP_LINK':'核验TP Link已完成编码','COMPLETED_ENCODING_WEMO_POWER':'核验Power已完成编码','COMPLETED_ENCODING_SAMSUNG':'核验Samsung已完成编码','REGISTERED_59_ENGINEERING_TESTS':'运行59项工程检查','FINAL_CODE_PIN_RECHECK':'复核执行源码'}
    while time.monotonic()<deadline:
        pre=request('state');write(HERE/'PREFLIGHT_PROGRESS.json',pre)
        st=pre.get('PREFLIGHT_STATUS.json',{})
        progress('PREFLIGHT',worker=dict(phase=stage_labels.get(st.get('current_stage'),st.get('current_stage','启动固定环境')),elapsed_seconds=st.get('elapsed_seconds'),completed=sum(s['status']=='DONE' for s in st.get('stages',[])),total=11))
        if pre['status']=='PREFLIGHT_PASS':break
        need(pre['status'] not in ('PREFLIGHT_FAIL','CONTROLLER_ERROR'),'HPC_PREFLIGHT_FAILED: '+str(pre.get('error') or pre.get('PREFLIGHT_RESULT.json',{}).get('error') or pre.get('preflight_log_tail','')))
        time.sleep(5)
    else:raise TimeoutError('PREFLIGHT_CONTROL_DEADLINE')
    write(HERE/'PREFLIGHT_RECEIPT.json',pre)
    progress('SUBMITTING');submitted=request('submit');write(HERE/'SUBMIT_RECEIPT.json',submitted)
    need(submitted['submitted'],'SUBMISSION_FAILED');job=submitted['job_id'];progress('HPC_RUNNING',job_id=job)
    write(HERE.parent/'history_sample_coverage_c4_deployment_20261101/CURRENT_SUBMIT_RECEIPT.json',dict(submitted,preflight_repair_deployment=HERE.name))
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
