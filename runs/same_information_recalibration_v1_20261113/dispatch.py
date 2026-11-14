"""Durable, idempotent Slurm control and small result acceptance on the login node."""
import argparse
import getpass
import os
import re
import subprocess
import time
import traceback
from pathlib import Path

from common_round1 import (HERE, JOB_NAMES, ROOT, RUN, Inputs, artifact, config_at, dump, job_id,
                           load, require, sha, verify_package, verify_artifact, verify_runtime_paths, write_text)

TERMINAL = {'BOOT_FAIL', 'CANCELLED', 'DEADLINE', 'FAILED', 'NODE_FAIL', 'OUT_OF_MEMORY',
            'PREEMPTED', 'REVOKED', 'SPECIAL_EXIT', 'TIMEOUT', 'COMPLETED'}
JOB_PATTERN = re.compile(r'p04-ref-recal|same[_-]information[_-]recalibration', re.I)
JOB_FIELDS = 'JobIDRaw,JobName%100,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem'
RESULT_FILES = ['THRESHOLD_SEAL.json','QUERY_EVALUATION.json','METRICS.json','METRICS.csv',
                'PAIRED_CHANGES.json','PAIRED_CHANGES.csv','REAL_PREFLIGHT.json','RESOURCES_first.json',
                'RUNTIME_first.json','FIRST_COMPLETE.json','STOP_first.json','SLURM_STOP_first.json',
                'STARTUP_first.json','PROGRESS_first.json',
                *[p + '_CHANGED_UIDS.jsonl.gz' for p in ('CIC_DEV','UNSW_DEV','EDGE')]]
CONTROL_FILES = ['DUPLICATE_AUDIT.json','DEPENDENCY_GATE.json','CHAIN_STATE.json',
                 'REMOTE_ADMISSION_PROGRESS.json','JOB_first.json','SCHEDULER_first.json',
                 'TEST_ONLY_first.json','SUBMIT_INTENT_first.json','FINAL_ACCEPTANCE.json',
                 'RESULTS_FOR_PAPER.md','DISPATCH_STOP.json']

def command(argv, timeout=40):
    p = subprocess.run(argv, capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)
    return dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)


def checked(argv):
    r = command(argv)
    require(r['returncode'] == 0, 'SCHEDULER_QUERY_FAILED:' + argv[0] + ':' + r['stderr'][-900:])
    return r['stdout']


def maybe(path):
    return load(path) if path.is_file() else None


def inspect_existing(project, run_dir):
    user = getpass.getuser()
    recent = checked(['sacct', '-X', '-n', '-P', '-u', user, '-S', '2026-11-11', '-o', JOB_FIELDS])
    live = checked(['squeue', '-u', user, '-h', '-o', '%i|%j|%T|%R'])
    receipts = [maybe(run_dir / f'JOB_{phase}.json') for phase in JOB_NAMES]
    owned = {r['job_id'] for r in receipts if r is not None}
    def matching(data):
        return [line.strip() for line in data.splitlines()
                if len(line.split('|')) > 2 and JOB_PATTERN.search(line.split('|')[1])]
    matched = matching(recent) + matching(live)
    other_jobs = sorted({line for line in matched if line.split('|')[0] not in owned})
    other_dirs = [str(p) for p in sorted((project / 'runs').iterdir())
                  if p.is_dir() and p != run_dir and not p.name.startswith('.' + RUN + '_relay_') and
                  JOB_PATTERN.search(p.name)]
    return dict(status='PASS' if not (other_jobs or other_dirs) else 'EXISTING_WORK_NEEDS_RECONCILIATION',
                known_receipts=sorted(owned), matching_scheduler_records=sorted(set(matched)),
                unmatched_jobs=other_jobs, other_run_directories=other_dirs,
                checked_squeue=True, checked_sacct_since='2026-11-11')


def scheduler(control, phase, job):
    j = job['job_id']
    accounting = command(['sacct', '-j', j, '-n', '-P', '-o', JOB_FIELDS])
    active = command(['squeue', '-j', j, '-h', '-o', '%i|%T|%R'])
    primary = [line.strip().split('|') for line in accounting['stdout'].splitlines()
               if line.split('|')[0].strip() == j]
    latest = next((line.strip().split('|') for line in active['stdout'].splitlines()
                   if line.split('|')[0].strip() == j), None)
    state = primary[-1][2].strip().split()[0].rstrip('+') if primary else 'ACCOUNTING_PENDING'
    exit_code = primary[-1][3].strip() if primary else None
    if latest and state not in TERMINAL:
        state = latest[1]
    live_usage = None
    if state == 'RUNNING':
        try:
            live_usage = command(['sstat', '-j', j + '.batch', '-n', '-P', '-o',
                                  'AveCPU,MaxRSS,MaxDiskRead,MaxDiskWrite'], timeout=10)
        except (OSError, subprocess.TimeoutExpired):
            pass
    record = dict(phase=phase, job_id=j, state=state, exit_code=exit_code, reason=latest[2] if latest else None,
                  accounting=accounting, active=active, live_usage=live_usage, observed_unix=time.time())
    dump(control / f'SCHEDULER_{phase}.json', record)
    return record


def dispatch_job(control, out, project, phase, partition, mem, wall):
    receipt = control / f'JOB_{phase}.json'
    if receipt.is_file():
        return load(receipt)
    intent = control / f'SUBMIT_INTENT_{phase}.json'
    require(not intent.exists(), 'UNRESOLVED_PRIOR_SUBMIT_INTENT:' + phase)
    require(phase in JOB_NAMES and partition == 'amd' and isinstance(mem, int) and isinstance(wall, int),
            'JOB_RESOURCE_SCHEMA')
    logs = out / 'logs'
    logs.mkdir(exist_ok=True)
    hrs, rem = divmod(wall, 3600)
    minutes, seconds = divmod(rem, 60)
    args = ['sbatch', '--parsable', '--no-requeue', '--nodes=1', '--ntasks=1', '--cpus-per-task=1',
            '--job-name=' + JOB_NAMES[phase], '--partition=' + partition, '--mem=' + str(mem) + 'M',
            f'--time={hrs:02d}:{minutes:02d}:{seconds:02d}', '--chdir=' + str(HERE),
            '--output=' + str(logs / (phase + '-%j.out')), '--error=' + str(logs / (phase + '-%j.err')),
            str(HERE / 'run.slurm'), phase, str(out), str(project), str(mem)]
    test = command([args[0], '--test-only', *args[2:]])
    unsupported = (test['returncode'] != 0 and 'test-only' in test['stderr'] and
                   any(x in test['stderr'].lower() for x in ('unrecognized option', 'not supported', 'invalid option')))
    dump(control / f'TEST_ONLY_{phase}.json',
         dict(test, status='UNSUPPORTED' if unsupported else 'PASS' if test['returncode'] == 0 else 'FAIL'))
    require(test['returncode'] == 0 or unsupported, 'SBATCH_TEST_ONLY:' + test['stderr'][-1500:])
    payload = dict(phase=phase, job_name=JOB_NAMES[phase], partition=partition, cpu=1,
                   memory_mib=mem, wall_seconds=wall, package_manifest_sha256=sha(HERE / 'PACKAGE_MANIFEST.json'),
                   created_unix=time.time(), args=args)
    dump(intent, payload)
    output = command(args)
    require(output['returncode'] == 0, 'SBATCH_FAILED:' + output['stderr'][-1600:])
    payload.update(job_id=job_id(output['stdout']), sbatch_stdout=output['stdout'].strip())
    dump(receipt, payload)
    return payload


def track(control, out, phase, job):
    until = time.monotonic() + 86400 + job['wall_seconds']
    first_terminal = None
    while time.monotonic() < until:
        s = scheduler(control, phase, job)
        state = s['state']
        prog = maybe(out / f'PROGRESS_{phase}.json')
        error = maybe(out / f'STOP_{phase}.json') or maybe(out / f'SLURM_STOP_{phase}.json')
        if error or state in TERMINAL - {'COMPLETED'}:
            raise RuntimeError(f'{phase}_SCHEDULER_OR_WORKER_FAILURE:{state}:{error and error.get("error", error)}')
        if state == 'COMPLETED':
            require(s['exit_code'] == '0:0', 'NONZERO_JOB_EXIT:' + phase)
            receipt = out / ('FIRST_COMPLETE.json' if phase == 'first' else 'EVAL_COMPLETE.json')
            if receipt.is_file():
                r = load(receipt)
                require(r['slurm_job_id'] == job['job_id'] and
                        r['package_manifest_sha256'] == job['package_manifest_sha256'],
                        'WORKER_COMPLETION_IDENTITY:' + phase)
                return r
            first_terminal = first_terminal or time.monotonic()
            require(time.monotonic() - first_terminal < 40, 'POST_RESULT_MISSING_COMPLETION:' + phase)
        status = ('RUNNING' if state == 'RUNNING' else
                  'COMPUTE_COMPLETED_VERIFYING' if state == 'COMPLETED' else 'SUBMITTED')
        dump(control / 'CHAIN_STATE.json', dict(stage=status, phase=phase, job_id=job['job_id'],
            scheduler_state=state, scheduler_reason=s['reason'], detail=prog,
            live_usage=s['live_usage'], updated_unix=time.time()))
        time.sleep(10)
    raise RuntimeError('BOUNDED_WAIT_EXPIRED:' + phase)

def finalize(control, out, result):
    receipt = out / 'THRESHOLD_SEAL.json'
    threshold = load(receipt)
    ev = load(out / 'QUERY_EVALUATION.json')
    real = load(out / 'REAL_PREFLIGHT.json')
    require(result['status'] == threshold['status'] == ev['status'] == real['status'] == 'PASS' and
            sha(receipt) == result['threshold_sha256'] == ev['threshold_sha256'] and
            result['query_rows'] == 388202 and result['reference_rows'] == 79069 and
            threshold['evaluation_used'] is False, 'FINAL_RECAL_ACCEPTANCE')
    for item in ev['outputs'].values():
        verify_artifact(out,item)
    for pool in result['pools']:
        verify_artifact(out,threshold['pools'][pool]['reference_scores'])
        verify_artifact(out,ev['pools'][pool]['changed_uid_index'])
    metrics = load(out / 'METRICS.json')
    names = dict(RAW='源阈值 RAW',P4_MAIN='完整库 p4',
                 RECAL_WITH_GUARD='目标阈值（保留保护）',RECAL_NO_GUARD='目标阈值（无保护）')
    lines = ['# 同一批正常资料下的阈值对照', '',
             '结果：冻结 p4 与同资料阈值重校准已在原查询上完成对照。',
             '影响：完整库 p4 保留为主方法。本对照检验如何使用同一批正常资料。',
             '下一步：论文可使用下表与完整配对数据。', '',
             '| 测试床 | 方法 | 查询组 | 告警／查询 | 普通率 | 分层加权率 | HT |',
             '|---|---|---|---:|---:|---:|---:|']
    for row in metrics:
        pool = row['pool']
        if (row['head'] != 'ensemble' or row['guard_stratum'] != 'ALL' or
            row['view'] != ('full' if pool=='EDGE' else 'post_window_primary') or
            row['group'] not in (('NORMAL','HTTP','UDP') if pool=='EDGE' else ('NORMAL','ATTACK'))):
            continue
        ht = f"{row['HT_rate']:.4%}" if 'HT_rate' in row else '—'
        lines.append(f"| {pool} | {names[row['config']]} | {row['group']} | "
                     f"{row['alarm_count']:,}/{row['rows']:,} | {row['sample_rate']:.4%} | "
                     f"{row['hierarchical_rate']:.4%} | {ht} |")
    lines.extend(['','完整四头、各视图、设备和协议、保护分层、以及逐查询新增与撤回见 METRICS 和 PAIRED_CHANGES。',
                  '带保护重校准的 1% 只约束未命中保护的参考拟合集。UNSW 攻击全部命中保护。',
                  '两臂在评价上的工作点可能不同，阈值不由评价数据反推。'])
    write_text(control/'RESULTS_FOR_PAPER.md','\n'.join(lines)+'\n')
    verdict = dict(result, baseline_metric_rows=sum(v['baseline_metric_rows'] for v in ev['pools'].values()),
                   original_p4_main_kept=True, training_updates=0, query_model_forwards=0,
                   raw_pcap_encodings=0, reference_rows_scored=79069,
                   conditional_unguarded_budget=.01, coverage=ev['pools'])
    dump(control/'FINAL_ACCEPTANCE.json',verdict)
    return verdict


def pull_manifest(control, out):
    files = {}
    for prefix, base, allowed in [('',control,CONTROL_FILES),('results/',out,RESULT_FILES)]:
        for name in allowed:
            p = base/name
            if p.is_file():
                files[prefix+name] = artifact(p)
    for p in (out/'logs').glob('*'):
        if re.fullmatch(r'first-[0-9]+\.(out|err)',p.name) and p.is_file() and p.stat().st_size < 1024**2:
            files['results/logs/'+p.name] = artifact(p)
    dump(control/'PULLBACK_MANIFEST.json',dict(files=files,transfer_scope='small metrics/receipts/UID indices'))


def main(control, project):
    out = control/'results'
    out.mkdir(exist_ok=True)
    phase = 'INSTALL'
    try:
        verify_package(HERE)
        cfg = config_at()
        duplicate = inspect_existing(project,control)
        dump(control/'DUPLICATE_AUDIT.json',duplicate)
        require(duplicate['status']=='PASS','EXISTING_WORK_NEEDS_RECONCILIATION')
        dump(control/'CHAIN_STATE.json',dict(stage='VERIFYING_REMOTE_INPUTS',updated_unix=time.time()))
        def admission(stage, done, total, **detail):
            dump(control/'REMOTE_ADMISSION_PROGRESS.json',dict(
                 stage=stage,done=done,total=total,updated_unix=time.time(),**detail))
        store = Inputs(project,load(HERE/'INPUT_PINS.json'),('reference',),progress=admission)
        gate = store.verify()
        dump(control/'DEPENDENCY_GATE.json',gate)
        require(gate['status']=='PASS','DEPENDENCY_GATE:' + ','.join(gate['failures']))
        dump(control/'DEPENDENCY_GATE.json',dict(gate,runtime=verify_runtime_paths(project),
             query_files_checked='after threshold sealing in the compute job'))
        job = dispatch_job(control,out,project,'first',cfg['partition'],cfg['memory_mib'],cfg['wall_seconds'])
        phase = 'FIRST'
        result = track(control,out,'first',job)
        phase = 'FINALIZE'
        verdict = finalize(control,out,result)
        dump(control/'CHAIN_STATE.json',dict(stage='ACCEPTED',job_id=job['job_id'],
             acceptance=verdict,updated_unix=time.time()))
        pull_manifest(control,out)
    except Exception as exc:
        stage = maybe(out/'SLURM_STOP_first.json') or {}
        classification = ('INSTALL_OR_SUBMIT_FAILURE' if phase=='INSTALL' else
                          'POST_RESULT_FAILURE' if phase=='FINALIZE' else
                          'COMPUTE_STARTUP_FAILURE' if stage.get('stage')=='COMPUTE_STARTUP'
                          or not (out/'RUNTIME_first.json').is_file() else 'RUNTIME_FAILURE')
        error = dict(stage='STOP',phase=phase,error=str(exc),classification=classification,
                     updated_unix=time.time(),traceback=traceback.format_exc())
        dump(control/'DISPATCH_STOP.json',error)
        dump(control/'CHAIN_STATE.json',error)
        pull_manifest(control,out)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--control',type=Path,required=True)
    parser.add_argument('--project',type=Path,default=ROOT)
    args=parser.parse_args()
    require(args.control.resolve()==(args.project/'runs'/RUN).resolve(),'RUN_SCOPE')
    main(args.control.resolve(),args.project.resolve())
