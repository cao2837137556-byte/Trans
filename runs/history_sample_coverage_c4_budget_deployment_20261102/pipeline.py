"""Ordinary bounded worker: upload, preflight, submit once, retrieve and verify."""
from datetime import datetime,timezone,timedelta
import http.client
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import traceback
import psutil

from client import HERE,PACKAGE,request,upload,retrieve,read,write,sha,need

record={}


def progress(stage,**fields):
    if record.get('stage')!=stage:
        for key in ('file','done_bytes','total_bytes','bytes_per_second','worker','network_error'):record.pop(key,None)
    record.update(stage=stage,**fields,updated_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'))
    try:write(HERE.parent/'history_sample_coverage_c4_deployment_20261101/PROGRESS.json',record)
    except PermissionError:pass


class BudgetDeadline:
    """Conservative local copy of the remote 18,000s deadline; queue is excluded."""
    def __init__(self,clock=time.monotonic):self.clock=clock;self.deadline=None;self.started_utc=None
    def observe(self,state,request_started):
        remaining=state.get('budget_remaining_seconds');worker=state.get('STATUS.json',{})
        if remaining is None:
            need(not worker.get('started_utc'),'REMOTE_STARTED_WITHOUT_GLOBAL_DEADLINE');return
        need(type(remaining) in (int,float) and math.isfinite(remaining) and 0<=remaining<=18000,'REMOTE_REMAINING_BUDGET')
        proposed=request_started+remaining
        self.deadline=proposed if self.deadline is None else min(self.deadline,proposed)
        self.started_utc=state.get('encoding_started_utc') or worker.get('started_utc') or self.started_utc
        self.guard()
    def guard(self):
        if self.deadline is None:return None
        remaining=self.deadline-self.clock();need(remaining>0,'GLOBAL_ADDITIONAL_18000_SECOND_WALL_LIMIT');return remaining
    def timeout(self,maximum=30):
        left=self.guard();return maximum if left is None else max(.1,min(maximum,left))
    def receipt(self):
        remaining=self.guard();need(remaining is not None,'ENCODING_START_REQUIRED')
        return dict(encoding_started_utc=self.started_utc,additional_wall_limit_seconds=18000,
            conservative_additional_wall_seconds=18000-remaining,remaining_seconds=remaining,
            includes_retrieval_evaluation_independent_verification=True,queue_seconds_included=False,automatic_science_retry=False)


def descendants(process):
    try:return psutil.Process(process.pid).children(recursive=True)
    except psutil.NoSuchProcess:return []


def stop_local_group(process,known):
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:pass
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    else:
        # Preserve handles to descendants observed while the leader was alive.
        # A completed leader must not hide a surviving worker from cleanup.
        for child in reversed(list(known.values())):
            try:child.terminate()
            except psutil.NoSuchProcess:pass
        if process.poll() is None:process.terminate()
        _,alive=psutil.wait_procs(list(known.values()),timeout=3)
        for child in alive:
            try:child.kill()
            except psutil.NoSuchProcess:pass
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill()
    process.wait(timeout=3)


def local_stage(arguments,stage,budget):
    need(budget.guard() is not None,'LOCAL_STAGE_REQUIRES_REMOTE_START');progress(stage)
    options=dict(start_new_session=True) if os.name=='posix' else dict(creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW)
    process=None;known={}
    with (HERE/(stage+'.log')).open('x',encoding='utf-8') as log:
        try:
            process=subprocess.Popen([sys.executable,'-X','utf8','-B',*arguments],cwd=PACKAGE,
                stdout=log,stderr=subprocess.STDOUT,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),**options)
            while True:
                for child in descendants(process):known[child.pid]=child
                if process.poll() is not None:break
                remaining=budget.guard();folder='verification' if stage=='INDEPENDENT_VERIFICATION' else 'evaluation'
                status=PACKAGE/'outputs'/folder/'STATUS.json'
                if status.exists():
                    try:progress(stage,worker=read(status),global_remaining_seconds=remaining)
                    except (OSError,ValueError):pass
                time.sleep(min(.5,remaining))
        finally:
            if process is not None:stop_local_group(process,known)
    budget.guard();need(process.returncode==0,stage+'_FAILED: see '+str(HERE/(stage+'.log')))


def main():
    with (HERE/'PIPELINE_ATTEMPT.json').open('x',encoding='utf-8') as f:json.dump(dict(pid=os.getpid(),automatic_science_retry=False),f)
    manifest=read(HERE/'DELIVERY_MANIFEST.json');need(sha(PACKAGE/'EXECUTION_CARD.json')==manifest['execution_card_sha256'],'LOCAL_CARD_PIN')
    progress('UPLOADING',code_only=True);upload(progress)
    progress('INSTALLING');write(HERE/'INSTALL_RECEIPT.json',request('install',timeout=120))
    progress('PREFLIGHT',worker=dict(phase='分阶段环境、旧产物和工程检查'));request('preflight')
    preflight_deadline=time.monotonic()+660
    labels={'PIN_ENVIRONMENT_AND_CARD':'核对环境与新执行卡','ENVIRONMENT_IMPORTS':'加载固定 Python 3.11 环境',
        'SCIENTIFIC_CODE_PINS':'核对冻结源码','REAL_246_HEADER_QUALIFICATION':'核验246个真实包头',
        'PREVIOUS_FAILURE_AND_BUDGET_RECEIPTS':'核对旧失败及累计预算','COMPLETE_PREPARED_SMALL_RECEIPTS':'核对完整PREPARED回执',
        'COMPLETED_ENCODING_TP_LINK':'核验TP Link旧编码','COMPLETED_ENCODING_WEMO_POWER':'核验Power旧编码',
        'COMPLETED_ENCODING_SAMSUNG':'核验Samsung旧编码','ALL_REGISTERED_ENGINEERING_TESTS':'运行全部工程检查','FINAL_CODE_PIN_RECHECK':'最终复核源码'}
    while time.monotonic()<preflight_deadline:
        state=request('state');write(HERE/'PREFLIGHT_PROGRESS.json',state);worker=state.get('PREFLIGHT_STATUS.json',{})
        progress('PREFLIGHT',worker=dict(phase=labels.get(worker.get('current_stage'),worker.get('current_stage','启动预检')),
            elapsed_seconds=worker.get('elapsed_seconds'),completed=sum(s['status']=='DONE' for s in worker.get('stages',[])),total=11))
        if state['status']=='PREFLIGHT_PASS':break
        need(state['status'] not in ('PREFLIGHT_FAIL','CONTROLLER_ERROR'),'HPC_PREFLIGHT_FAILED:'+str(state.get('preflight') or state.get('error') or state.get('preflight_log_tail')))
        time.sleep(5)
    else:raise TimeoutError('PREFLIGHT_CONTROL_DEADLINE')
    write(HERE/'PREFLIGHT_RECEIPT.json',state)
    progress('SUBMITTING');submitted=request('submit',timeout=45);write(HERE/'SUBMIT_RECEIPT.json',submitted)
    need(submitted.get('submitted') and str(submitted.get('job_id','')).isdigit(),'SUBMISSION_FAILED_OR_UNCERTAIN_NO_RETRY')
    job=submitted['job_id'];write(HERE.parent/'history_sample_coverage_c4_deployment_20261101/CURRENT_SUBMIT_RECEIPT.json',
        dict(submitted,budget_deployment=HERE.name))
    budget=BudgetDeadline();queue_deadline=time.monotonic()+24*3600
    progress('HPC_RUNNING',job_id=job,worker=dict(phase='已提交，等待调度'))
    while True:
        budget.guard();need(time.monotonic()<queue_deadline,'QUEUE_OR_COMPLETION_WAIT_LIMIT')
        sent=time.monotonic()
        try:state=request('state',timeout=budget.timeout())
        except (OSError,http.client.HTTPException) as exc:
            progress('HPC_CONNECTION_INTERRUPTED',job_id=job,network_error=str(exc));time.sleep(min(15,budget.timeout(15)));continue
        budget.observe(state,sent);write(HERE/'STATE_RECEIPT.json',state);worker=state.get('STATUS.json',{})
        progress('HPC_RUNNING',job_id=job,worker=worker,scheduler=state.get('squeue') or state.get('sacct'),
            global_remaining_seconds=budget.guard(),network_error=None)
        need(state['status'] not in ('CONTROLLER_ERROR','BUDGET_EXPIRED'),'HPC_CONTROL_STOP:'+str(state.get('error')))
        need(worker.get('technical_status')!='EXCEPTION_STOPPED','HPC_WORKER_STOPPED:'+str(worker.get('error')))
        need(not any(s in state.get('sacct','') for s in ('FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL')),'HPC_SCHEDULER_FAILURE')
        if state.get('STAGE_RECEIPT.json',{}).get('technical_status')=='COMPLETED':break
        need(not ('COMPLETED' in state.get('sacct','')),'HPC_EXITED_WITHOUT_ENCODING_RECEIPT')
        time.sleep(budget.timeout(30))
    progress('RETRIEVING',job_id=job);encoded=retrieve(progress,budget=budget.guard)
    local_stage(['run.py','evaluate','--execute-real-data','--encoded-dir',str(encoded)],'LOCAL_EVALUATION',budget)
    local_stage(['verify_result.py'],'INDEPENDENT_VERIFICATION',budget)
    acceptance=read(PACKAGE/'FINAL_ACCEPTANCE.json');result=read(PACKAGE/'outputs/evaluation/RESULT.json')
    need(acceptance['status']=='PASS','FINAL_ACCEPTANCE_REQUIRED');write(HERE/'GLOBAL_BUDGET_RECEIPT.json',budget.receipt())
    payload=dict(final_acceptance_sha256=sha(PACKAGE/'FINAL_ACCEPTANCE.json'),
        verification_stage_receipt_sha256=sha(PACKAGE/'outputs/verification/STAGE_RECEIPT.json'))
    acknowledgement_error=None
    try:write(HERE/'COMPLETE_ACK.json',request('complete',json.dumps(payload).encode(),{'Content-Type':'application/json'},timeout=budget.timeout(15)))
    except (OSError,http.client.HTTPException,ValueError) as exc:acknowledgement_error=str(exc)
    progress('COMPLETE',job_id=job,acceptance=acceptance,result=result,completion_acknowledgement_error=acknowledgement_error)


if __name__=='__main__':
    try:main()
    except BaseException as exc:
        progress('STOPPED',error=str(exc));write(HERE/'PIPELINE_ERROR.json',dict(error=str(exc),traceback=traceback.format_exc(),automatic_science_retry=False));raise
