"""One ordinary bounded delivery process; never reconnects SSH or resubmits."""
import argparse
import http.client
from pathlib import Path
import time
import traceback

from client import (HERE, need, read, request, retrieve_results, upload_files,
                    utc, validate_local_files, write)

NETWORK_ERRORS = (OSError, http.client.HTTPException)
record = {}


def progress(stage, **fields):
    if record.get('stage') != stage:
        for key in ('file', 'file_done_bytes', 'file_total_bytes', 'done_bytes',
                    'total_bytes', 'bytes_per_second', 'network_error'):
            record.pop(key, None)
    record.update(stage=stage, updated_utc=utc(), **fields)
    record.update(scope='LINUX_ENGINEERING_PREFLIGHT_ONLY',
                  automatic_retry_or_resubmission=False,
                  formal_external_evaluation=False, full_execution_ready=False)
    write(HERE / 'PROGRESS.json', record)


def known_job(state):
    job = state.get('job') or {}
    value = job.get('job_id') if isinstance(job, dict) else None
    need(value is None or str(value).isdigit(), 'REMOTE_JOB_ID_SCHEMA')
    return dict(job, job_id=str(value)) if value is not None else None


def submit_once(*, action=request):
    """A saved local intent forbids a second POST after an ambiguous request."""
    state = action('state')
    job = known_job(state)
    if job:
        write(HERE / 'SUBMIT_RECEIPT.json', job)
        return job
    attempt = HERE / 'SUBMIT_ATTEMPT.json'
    need(not attempt.exists(), 'PRIOR_SUBMISSION_UNCERTAIN_NO_AUTOMATIC_RETRY')
    write(attempt, dict(started_utc=utc(), status='INTENT_PERSISTED_BEFORE_REQUEST',
                        automatic_retry=False))
    try:
        response = action('submit', timeout=90)
        job = known_job(response) if 'job' in response else known_job({'job': response})
        need(job is not None, 'SUBMISSION_RESPONSE_WITHOUT_JOB_ID')
    except BaseException:
        # Reading the one remote intent/receipt is safe. It does not re-run
        # sbatch, and a missing receipt leaves the attempt explicitly uncertain.
        try:
            job = known_job(action('state'))
        except BaseException:
            job = None
        if job is None:
            write(HERE / 'SUBMIT_UNCERTAIN.json', dict(status='UNKNOWN_DO_NOT_RESUBMIT',
                                                       observed_utc=utc(), automatic_retry=False))
            raise RuntimeError('SUBMISSION_OUTCOME_UNKNOWN_NO_AUTOMATIC_RETRY') from None
    write(HERE / 'SUBMIT_RECEIPT.json', job)
    return job


def prepared_receipt(state):
    receipt = state.get('prepare_receipt') or state.get('preparation_receipt')
    if isinstance(receipt, dict) and receipt.get('status') == 'PREPARED_NOT_SUBMITTED':
        return receipt
    if isinstance(receipt, dict) and state.get('status') in ('PREPARED', 'SUBMITTED', 'COMPLETE', 'COMPLETED'):
        return receipt
    if state.get('status') in ('PREPARED', 'PREPARED_NOT_SUBMITTED'):
        return state
    return None


def prepare_once(*, action=request, maximum=900, interval=5,
                 clock=time.monotonic, pause=time.sleep):
    """A disconnect during preparation is reconciled with GET, never re-POST."""
    started = clock()
    state = action('state')
    ready = prepared_receipt(state)
    if ready is not None:
        return ready
    attempt = HERE / 'PREPARE_ATTEMPT.json'
    if not attempt.exists():
        write(attempt, dict(started_utc=utc(), status='INTENT_PERSISTED_BEFORE_REQUEST',
                            automatic_retry=False))
        try:
            value = action('prepare', timeout=maximum)
            need(value.get('status') not in ('FAILED', 'STOPPED', 'STOPPED_NO_RETRY'),
                 'REMOTE_PREPARATION_FAILED')
            return value
        except NETWORK_ERRORS:
            pass
    while clock() - started < maximum:
        try:
            state = action('state')
        except NETWORK_ERRORS:
            pause(min(interval, max(0, maximum-(clock()-started))))
            continue
        ready = prepared_receipt(state)
        if ready is not None:
            return ready
        need(state.get('status') not in ('FAILED', 'STOPPED', 'STOPPED_NO_RETRY',
                                          'PREPARE_FAILED', 'PREPARATION_FAILED'),
             'REMOTE_PREPARATION_FAILED')
        need(not state.get('last_error'), 'REMOTE_PREPARATION_FAILED_RECORDED')
        progress('PREPARING_REMOTE', message='远端准备尚未结束；仅查询状态，不重复执行准备动作。',
                 worker=state.get('prepare_status') or state.get('delivery_status') or {},
                 remote_status=state.get('status'))
        pause(min(interval, max(0, maximum-(clock()-started))))
    raise TimeoutError('PREPARATION_OUTCOME_UNRESOLVED_NO_AUTOMATIC_RETRY')


def terminal_state(state):
    if state.get('delivery_result'):
        return True
    if state.get('results_ready') is True or state.get('result_ready') is True:
        return True
    return str(state.get('status', '')).upper() in (
        'COMPLETE', 'COMPLETED', 'LINUX_PREFLIGHT_PASS', 'STOPPED_NO_RETRY',
        'JOB_FAILED', 'JOB_FINISHED', 'FINISHED', 'FAILED')


def watch_and_retrieve(seconds=1800, interval=20, *, action=request,
                       retrieve=retrieve_results, clock=time.monotonic, pause=time.sleep):
    deadline = clock() + seconds
    while clock() < deadline:
        try:
            state = action('state')
        except NETWORK_ERRORS:
            progress('CONNECTION_INTERRUPTED', network_error='既有通道暂不可达；不会自动重连或重投。')
            pause(min(interval, max(0, deadline-clock())))
            continue
        job = known_job(state)
        scheduler = state.get('scheduler') or (job or {}).get('state') or (job or {}).get('scheduler')
        if isinstance(scheduler, dict):
            scheduler = (scheduler.get('state') or scheduler.get('State') or scheduler.get('status')
                         or scheduler.get('stdout') or scheduler.get('error'))
        fields = dict(job_id=job['job_id'] if job else record.get('job_id'),
                      scheduler=scheduler,
                      remote_status=state.get('status'),
                      worker=state.get('delivery_status') or state.get('worker') or {},
                      remote_error=state.get('last_error'))
        progress('HPC_PREFLIGHT', **fields)
        if terminal_state(state):
            try:
                receipt = retrieve(progress, action=action)
            except NETWORK_ERRORS:
                progress('CONNECTION_INTERRUPTED', network_error='结果取回连接中断；保留作业与现场，不重投。', **fields)
                pause(min(interval, max(0, deadline-clock())))
                continue
            write(HERE / 'FINAL_ACCEPTANCE.json', dict(receipt, completed_utc=utc()))
            progress('LINUX_PREFLIGHT_PASS' if receipt['linux_actual_preflight_pass'] else 'PREFLIGHT_STOPPED',
                     result=receipt, **fields)
            return receipt
        pause(min(interval, max(0, deadline-clock())))
    progress('OBSERVATION_WINDOW_ENDED', message='本次自动取回窗口结束；作业不会因此重投或取消。')
    return None


def run(wait_for_receiver=0, observe_seconds=1800, interval=20, *, action=request):
    try:
        need(0 <= wait_for_receiver <= 1800 and 0 <= observe_seconds <= 1800
             and 1 <= interval <= 60, 'LOCAL_BOUNDED_WINDOWS')
        specs = validate_local_files(progress)
        deadline = time.monotonic() + wait_for_receiver
        while True:
            try:
                action('state')
                break
            except NETWORK_ERRORS:
                if time.monotonic() >= deadline:
                    raise
                progress('WAITING_FOR_USER_BOOTSTRAP', message='请在已手动连接的超算终端执行 RUN_IN_HPC_TERMINAL.txt 的整行命令；程序将自动接续上传与单次提交。')
                time.sleep(min(5, max(0, deadline-time.monotonic())))
        progress('UPLOADING')
        upload_files(specs, progress, action=action)
        progress('PREPARING_REMOTE')
        prepared = prepare_once(action=action)
        write(HERE / 'PREPARE_RECEIPT.json', prepared)
        progress('SUBMITTING')
        job = submit_once(action=action)
        progress('SUBMITTED', job_id=job['job_id'], message='10分钟预检已提交；不自动启动正式评价。')
        if observe_seconds:
            watch_and_retrieve(observe_seconds, interval, action=action)
        return 0
    except BaseException as error:
        # Never include token-bearing URLs or remote response bodies.
        safe_error = type(error).__name__ + ': ' + str(error)
        private = HERE / '.private/connection.json'
        if private.is_file():
            token = read(private).get('token')
            if token:
                safe_error = safe_error.replace(token, '[REDACTED]')
        write(HERE / 'PIPELINE_FAILURE.json', dict(status='STOPPED_NO_RETRY',
              error=safe_error, stopped_utc=utc(), automatic_retry=False,
              formal_external_evaluation=False))
        progress('STOPPED', error=safe_error)
        return 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--wait-for-receiver-seconds', type=int, default=0)
    parser.add_argument('--observe-seconds', type=int, default=1800)
    parser.add_argument('--interval-seconds', type=int, default=20)
    args = parser.parse_args()
    raise SystemExit(run(args.wait_for_receiver_seconds, args.observe_seconds, args.interval_seconds))
