"""Submit the preparation job and release exactly one formal replay on verified completion."""
import argparse
import getpass
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import traceback

from frozen_selector import need
from motion_ingress import ARCHIVE_BYTES, ARCHIVE_SHA, FAILED_PREP_JOB, REPAIR_RUN, RUN, digest

PACKAGE = Path(__file__).resolve().parent
NAMES = {'prepare':'p04-k8192-prepare', 'replay':'p04-k8192-replay'}
TERMINAL = {'BOOT_FAIL', 'CANCELLED', 'COMPLETED', 'DEADLINE', 'FAILED', 'NODE_FAIL',
            'OUT_OF_MEMORY', 'PREEMPTED', 'REVOKED', 'SPECIAL_EXIT', 'TIMEOUT'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def write(path, data):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+'\n',
                         encoding='utf-8')
    temporary.replace(path)


def command(argv, timeout=45):
    proc = subprocess.run(argv, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    return dict(returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def checked(argv):
    result = command(argv)
    need(result['returncode'] == 0, 'SCHEDULER:' + argv[0] + ':' + result['stderr'][-500:])
    return result['stdout']


def state(target, stage, **info):
    write(target/'CHAIN_STATE.json', dict(stage=stage, updated_unix=time.time(), **info))


def prior_jobs(target, project, retry_job):
    user = getpass.getuser()
    live = checked(['squeue','-h','-u',user,'-o','%i|%j|%T'])
    past = checked(['sacct','-X','-n','-P','-u',user,'-S','2026-11-11',
                    '-o','JobIDRaw,JobName%100,State,ExitCode'])
    def matching(text):
        return [x.split('|') for x in text.splitlines()
                if len(x.split('|')) >= 3 and re.search('k8192|p04-unified', x.split('|')[1], re.I)]
    active, history = matching(live), matching(past)
    if retry_job:
        parent = project/'runs'/RUN
        failure = read(parent/'FAILURE_prepare.json')
        old_submit = read(parent/'SBATCH_prepare.json')
        receipt = read(parent/'RETURN.json')
        allowed = [x for x in history if x[0] == retry_job and x[1] == NAMES['prepare']
                   and x[2] == 'FAILED' and x[3] == '1:0']
        need(target.name == REPAIR_RUN and len(allowed) == 1 and failure is not None and
             failure['stage'] == 'REFERENCE_E3_Q14_UNSW_DEV' and failure['error'] == 'SEALED_SNAPSHOT_ROW_JOIN'
             and old_submit['stdout'].strip().split(';',1)[0] == retry_job and
             digest(parent/'FAILURE_prepare.json') == receipt['files']['FAILURE_prepare.json']['sha256'] and
             all(not (parent/name).exists() for name in ('SUBMIT_INTENT_replay.json','SBATCH_replay.json',
                   'FORMAL_REPLAY_STARTED','REPLAY_RECEIPT.json','ACCEPTANCE.json')),
             'PREDECESSOR_PREP_FAILURE_AND_ZERO_FORMAL_REPLAYS_REQUIRED')
        history = [x for x in history if x not in allowed]
    write(target/'DUPLICATE_GATE.json', dict(status='PASS' if not (active or history) else 'STOP',
          active=active, other_history=history, reconciled_failed_prepare=retry_job))
    need(not active and not history, 'EXISTING_K8192_JOB_REQUIRES_RECONCILIATION')


def submit(target, project, archive, phase, mem_mib, wall_seconds):
    intent = target/f'SUBMIT_INTENT_{phase}.json'
    need(not intent.exists(), 'SUBMIT_INTENT_ALREADY_EXISTS:' + phase)
    hh, rest = divmod(wall_seconds, 3600)
    mm, ss = divmod(rest, 60)
    argv = ['sbatch','--no-requeue','--nodes=1','--ntasks=1','--cpus-per-task=4','--partition=amd',
        '--job-name='+NAMES[phase], '--mem='+str(mem_mib)+'M', f'--time={hh:02}:{mm:02}:{ss:02}',
        '--chdir='+str(PACKAGE), '--output='+str(target/f'{phase}-%j.out'),
        '--error='+str(target/f'{phase}-%j.err'), str(PACKAGE/'run.slurm'),
        phase, str(project), str(target), str(archive), str(mem_mib-2048), str(wall_seconds)]
    check = command([argv[0],'--test-only',*argv[1:]])
    write(target/f'SBATCH_TEST_{phase}.json', check)
    need(check['returncode'] == 0, 'SBATCH_TEST_ONLY:' + check['stderr'][-500:])
    with intent.open('x', encoding='utf-8') as stream:
        json.dump(dict(phase=phase, args=argv, timestamp=time.time()), stream)
        stream.flush()
        os.fsync(stream.fileno())
    result = command([argv[0],'--parsable',*argv[1:]])
    write(target/f'SBATCH_{phase}.json', result)
    job = result['stdout'].strip().split(';', 1)[0]
    need(result['returncode'] == 0 and job.isdigit(),
         'SBATCH_RECEIPT_MISSING_OR_AMBIGUOUS:' + phase + ':' + result['stderr'][-500:])
    state(target, 'SUBMITTED', phase=phase, job_id=job, memory_mib=mem_mib, wall_seconds=wall_seconds)
    return job


def wait(target, phase, job, wall):
    end = time.monotonic() + 86400 + wall
    terminal_seen = None
    while time.monotonic() < end:
        active = command(['squeue','-h','-j',job,'-o','%i|%T|%R'], timeout=20)
        acct = command(['sacct','-n','-P','-j',job,
            '-o','JobIDRaw,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem'])
        records = [line.split('|') for line in acct['stdout'].splitlines() if line.split('|')[0] == job]
        record = records[-1] if records else None
        current = record[1].strip().split()[0].rstrip('+') if record else 'ACCOUNTING_PENDING'
        live = [s.split('|') for s in active['stdout'].splitlines() if s.split('|')[0] == job]
        if live and current not in TERMINAL:
            current = live[0][1].strip()
        write(target/f'SCHEDULER_{phase}.json', dict(job_id=job, state=current, account=acct, live=active))
        failure = read(target/f'FAILURE_{phase}.json') or read(target/f'SLURM_STOP_{phase}.json')
        if failure or current in TERMINAL - {'COMPLETED'}:
            raise RuntimeError(f'{phase}:{job}:{current}:{failure}')
        if current == 'COMPLETED':
            need(record[2] == '0:0', 'NONZERO_SLURM_EXIT:' + phase)
            receipt = read(target/('PREP_RECEIPT.json' if phase=='prepare' else 'REPLAY_RECEIPT.json'))
            if receipt is not None:
                need(receipt['job_id'] == job, 'JOB_RECEIPT_IDENTITY')
                return receipt
            terminal_seen = terminal_seen or time.monotonic()
            need(time.monotonic()-terminal_seen < 45, 'COMPUTE_COMPLETED_WITHOUT_WORKER_RECEIPT')
        state(target, current if current in ('RUNNING','PENDING','COMPLETED') else 'SUBMITTED',
              phase=phase, job_id=job, scheduler_state=current, reason=live[0][2] if live else None,
              worker_preflight=(read(target/'PREFLIGHT.json') or {}).get('status'))
        time.sleep(12)
    raise TimeoutError('SLURM_WAIT_DEADLINE:' + phase)


def seal_results(target):
    eligible = {'PREFLIGHT.json','PREP_RECEIPT.json','REPLAY_RECEIPT.json','FORMAL_SIZING.json',
                'ACCEPTANCE.json','RESULT_INDEX.json','RESULTS_FOR_PAPER.md','CONTROLLER_FAILURE.json',
                'DUPLICATE_GATE.json','INSTALL.json','INPUT_SHA.json','CANDIDATE_SHA.json',
                'PREPARATION_REUSE.json','SNAPSHOT_REGRESSION.json'}
    prefixes = ('RUNTIME_', 'RESOURCES_', 'SBATCH_', 'SCHEDULER_', 'FAILURE_', 'SLURM_STOP_',
                'METRICS.', 'PAIRED.', 'ZERO_DEGRADATION.')
    files = {}
    for path in target.iterdir():
        if path.is_file() and (path.name in eligible or path.name.startswith(prefixes) or
                              path.name.endswith('_CHANGED_UIDS.jsonl.gz')):
            files[path.name] = dict(sha256=digest(path), bytes=path.stat().st_size)
    write(target/'RETURN.json', dict(files=files))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('project', type=Path)
    parser.add_argument('target', type=Path)
    parser.add_argument('stage', type=Path)
    parser.add_argument('--retry-prepare-job', choices=(FAILED_PREP_JOB,))
    args = parser.parse_args()
    project, target, archive = args.project, args.target, args.stage/'motion.pcap.gz'
    try:
        state(target, 'WAITING_FOR_VERIFIED_MOTION')
        expires = time.monotonic()+3600
        while not (args.stage/'MOTION_REMOTE.json').is_file():
            need(time.monotonic() < expires, 'MOTION_TRANSFER_RECEIPT_TIMEOUT')
            time.sleep(10)
        received = read(args.stage/'MOTION_REMOTE.json')
        need(received['status'] == 'VERIFIED_MOTION_ARCHIVE' and
             archive.stat().st_size == ARCHIVE_BYTES and digest(archive) == ARCHIVE_SHA,
             'MOTION_UPLOAD_SHA')
        state(target, 'SLURM_ADMISSION')
        need(shutil.disk_usage(target).free >= 75*1024**3, 'SCRATCH_SPACE_75_GIB_REQUIRED')
        prior_jobs(target, project, args.retry_prepare_job)
        prepare_wall = 18*3600
        prep = submit(target, project, archive, 'prepare', 12288, prepare_wall)
        result = wait(target, 'prepare', prep, prepare_wall)
        sizing = read(target/'FORMAL_SIZING.json')
        preflight = read(target/'PREFLIGHT.json')
        need(result['status'] == 'READY_FOR_ONE_PAIRED_REPLAY' and preflight['status'] == 'PASS' and
             result['preflight']['sha256'] == digest(target/'PREFLIGHT.json') and
             result['sizing']['sha256'] == digest(target/'FORMAL_SIZING.json') and sizing['status'] == 'PASS',
             'PREP_RECEIPT_OR_PREFLIGHT_FAILED')
        candidate = read(target/'candidate'/'CANDIDATE.json')
        need(result['candidate']['sha256'] == digest(target/'candidate'/'CANDIDATE.json') and
             candidate['status'] == 'CANDIDATE_SEALED', 'CANDIDATE_RECEIPT_GATE')
        write(target/'INPUT_SHA.json', candidate['verified_inputs'])
        write(target/'CANDIDATE_SHA.json', dict(receipt=result['candidate'],
              sources=read(target/'candidate'/'SELECTION.json'), features=candidate['pools']))
        wall = sizing['planned_wall_seconds']
        need(type(wall) is int and 3600 <= wall <= 21600 and sizing['memory_mib'] == 12288,
             'FORMAL_RESOURCE_PLAN_SCHEMA')
        replay = submit(target, project, archive, 'replay', sizing['memory_mib'], wall)
        result = wait(target, 'replay', replay, wall)
        acceptance = read(target/'ACCEPTANCE.json')
        need(result['status'] == 'FORMAL_REPLAY_COMPLETE' and
             result['acceptance']['sha256'] == digest(target/'ACCEPTANCE.json') and
             acceptance['formal_replays'] == 1 and acceptance['status'] == result['outcome'],
             'FINAL_ACCEPTANCE_RECEIPT_GATE')
        index = read(target/'RESULT_INDEX.json')
        lines = ['# 统一建库 K8192 配对重放', '', '结果为 '+index['status']+'。', '',
            '左侧 P4_MAIN，右侧 P4_UNIFIED_HIST_K8192_V1。旧库、阈值和成绩继续作为主方法基准。', '',
            '集成建档后指标见 [RESULT_INDEX.json](RESULT_INDEX.json)。全部头的配对变化见 '
            '[PAIRED.csv](PAIRED.csv)，逐池逐组零退化验收见 [ZERO_DEGRADATION.csv](ZERO_DEGRADATION.csv)。', '']
        (target/'RESULTS_FOR_PAPER.md').write_text('\n'.join(lines), encoding='utf-8')
        state(target, 'COMPLETE', phase='replay', job_id=replay, outcome=index['status'])
    except Exception as err:
        error = str(err)
        write(target/'CONTROLLER_FAILURE.json', dict(status='ENGINEERING_STOP', error=error,
                                                     traceback=traceback.format_exc()))
        state(target, 'STOP', error=error)
        raise
    finally:
        seal_results(target)


if __name__ == '__main__':
    main()
