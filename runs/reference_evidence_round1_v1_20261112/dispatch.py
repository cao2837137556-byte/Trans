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
JOB_PATTERN = re.compile(r'p04-ref-r1|ref(?:erence)?[-_. ]*(?:evidence|round[-_. ]*1|budget)|d[-_. ]*m[-_. ]*c0', re.I)
JOB_FIELDS = 'JobIDRaw,JobName%100,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem'
RESULT_FILES = [
    'REAL_PREFLIGHT.json', 'BASELINE_PARITY.json', 'D_SUMMARY.json', 'D_DIAGNOSIS.json', 'D_DIAGNOSIS.csv',
    'BASELINE_METRICS.json', 'BASELINE_METRICS.csv', 'BASELINE_PAIRED_CHANGES.json', 'BASELINE_PAIRED_CHANGES.csv',
    'INPUT_VERIFICATION_first.json', 'INPUT_VERIFICATION_eval.json',
    'INPUT_VERIFICATION_select-m-c0.json', 'INPUT_VERIFICATION_select-c1.json',
    'RESOURCE_PLAN.json', 'RESOURCES_first.json', 'RESOURCES_eval.json',
    'RESOURCES_select-m-c0.json', 'RESOURCES_select-c1.json',
    'RUNTIME_first.json', 'RUNTIME_eval.json', 'FIRST_COMPLETE.json', 'EVAL_COMPLETE.json',
    'M_SEAL.json', 'C0_SEAL.json', 'C1_SEAL.json', 'C1_CARDINALITY.json',
    'C0_CONSTRUCTION_STOP.json', 'C0_EVALUATION_STOP.json', 'C0_RELEASE.json', 'C1_BLOCKED.json',
    *[f'{name}_{suffix}' for name in ('M', 'C0', 'C1') for suffix in (
        'METRICS.json', 'METRICS.csv', 'PAIRED_CHANGES.json', 'PAIRED_CHANGES.csv',
        'VERIFICATION.json', 'REAL_SLICE.json', 'CONTINUOUS_DIFFERENCE_UIDS.jsonl.gz',
        'CHANGED_VS_P4_MAIN.jsonl.gz')],
    'M_CHANGED_VS_P4_COMMISSION_3D.jsonl.gz',
    *[f'{prefix}_{phase}.json' for phase in ('first', 'eval', 'select-m-c0', 'select-c1')
      for prefix in ('STOP', 'SLURM_STOP', 'STARTUP', 'PROGRESS')],
]
CONTROL_FILES = ['DUPLICATE_AUDIT.json', 'DEPENDENCY_GATE.json', 'CHAIN_STATE.json',
                 'REMOTE_ADMISSION_PROGRESS.json',
                 'JOB_first.json', 'JOB_eval.json', 'SCHEDULER_first.json', 'SCHEDULER_eval.json',
                 'TEST_ONLY_first.json', 'TEST_ONLY_eval.json', 'SUBMIT_INTENT_first.json', 'SUBMIT_INTENT_eval.json',
                 'FINAL_ACCEPTANCE.json', 'RESULTS_FOR_PAPER.md', 'DISPATCH_STOP.json']


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


def verify_return(control, out, first, second):
    base = load(out / 'BASELINE_PARITY.json')
    real = load(out / 'REAL_PREFLIGHT.json')
    d = load(out / 'D_SUMMARY.json')
    require(first['d_diagnosis_sha256'] == sha(out / 'D_DIAGNOSIS.json') and
            first['real_gate_sha256'] == sha(out / 'REAL_PREFLIGHT.json') and
            first['baseline_sha256'] == sha(out / 'BASELINE_PARITY.json'), 'FINAL_FIRST_ARTIFACT_IDENTITY')
    require(base['status'] == real['status'] == d['status'] == 'PASS' and
            base['rows'] == d['rows'] == 148316 and
            base['heads'] == ['27', '127', '227', 'ensemble'] and real['rows'] >= 100,
            'FULL_BASELINE_AND_REAL_GATE_REQUIRED')
    require(sum(r['count'] for r in d['aggregate'] if r['kind'] == 'FIRST_BLOCKER') == 22411,
            'D_TOTAL')
    verify_artifact(out, d['detail'])
    comparisons = {}
    for name in second['comparisons']:
        v = load(out / (name + '_VERIFICATION.json'))
        comparisons[name] = v
        require(v['rows'] == 148316 and v['status'] == second['comparisons'][name]['status'],
                'COMPARISON_RETURN_SCHEMA:' + name)
        for a in [v['arrays'], v['continuous_difference_uids'], *v['paired_changes'].values()]:
            verify_artifact(out, a)
        seal = load(out / (name + '_SEAL.json'))
        require(seal['query_assets_read'] == 0 and seal['package_manifest_sha256'] ==
                second['package_manifest_sha256'], 'CANDIDATE_PROVENANCE:' + name)
        for a in (seal['roster'], seal['mapping']):
            if a is not None:
                verify_artifact(out, a)
    require(comparisons['M']['status'] == 'PASS' and load(out / 'M_SEAL.json')['rows'] == 13247, 'M_REQUIRED')
    complete = second['status'] == 'PASS'
    if complete:
        require(comparisons['C0']['status'] == comparisons['C1']['status'] == 'PASS' and
                comparisons['C0']['outcome'] == 'DECISION_PRESERVING' and
                comparisons['C0']['numeric_comparison'] == 'NUMERICALLY_EQUIVALENT' and
                comparisons['C0']['metric_rows_equal'] > 0 and
                load(out / 'C0_SEAL.json')['rows'] == 61146, 'C0_STRICT_EQUIVALENCE_REQUIRED')
        c1 = load(out / 'C1_SEAL.json')
        n = load(out / 'C1_CARDINALITY.json')
        require(n['total'] == c1['rows'] and sha(out / 'C1_CARDINALITY.json') == c1['cardinality_sha256'],
                'C1_CARDINALITY_BEFORE_SELECTION')
        c = comparisons['C1']
        zero = sum(c['numeric']['decision_changes_by_head']) == 0
        require(zero == (c['outcome'] == 'DECISION_PRESERVING') and (not zero or c['metric_rows_equal'] > 0),
                'C1_DECISION_POLICY')
    else:
        require(second['status'] == 'PARTIAL_C0_FAILED' and 'C1' not in comparisons and
                (out / 'C1_BLOCKED.json').is_file(), 'C0_STOP_GATE')
    engineering_failed = any((out / name).is_file() for name in
                             ('C0_EVALUATION_STOP.json', 'C0_CONSTRUCTION_STOP.json'))
    result = dict(status='PASS' if complete else 'PARTIAL_C0_FAILED',
                  execution_class=('SCIENTIFIC_GO' if comparisons['C1']['outcome'] == 'DECISION_PRESERVING'
                                   else 'SCIENTIFIC_NO_GO') if complete else
                                  'RUNTIME_FAILURE' if engineering_failed else 'SCIENTIFIC_NO_GO',
                  evidence_scope='fixed UNSW queries; CIC and Edge reused from p4 acceptance',
                  original_p4_main_kept=True, default_reference_bank_changed=False,
                  training_updates=0, model_forwards=0, new_raw_pcap_encodings=0,
                  input_package_sha256=second['package_manifest_sha256'],
                  jobs=[first['slurm_job_id'], second['slurm_job_id']],
                  real_preflight_rows=real['rows'], comparisons=second['comparisons'],
                  changed_uids_retained=True)
    paper_readout(control, out, result, comparisons)
    dump(control / 'FINAL_ACCEPTANCE.json', result)
    return result


def paper_readout(control, out, result, comparisons):
    md = ['# 正常参考补证首轮结果入口', '',
          '结果：D 与 M 已生成。' + ('C0 通过严格数值与判定核验。' if result['status'] == 'PASS'
                                    else 'C0 未通过，C1 未进入重放。'),
          '影响：只评价既定 UNSW 查询；现行完整参考库继续作为主结果。',
          '下一步：论文对话可用下面的固定视图结果及全部附表。', '',
          '作业：' + '、'.join(result['jobs']), '',
          '## D：两小时库建档后残留误报', '',
          '| 首个阻断条件 | 条数 | 占该头残留误报 | 按原权重占比 |',
          '|---|---:|---:|---:|']
    d = load(out / 'D_SUMMARY.json')
    names = dict(REFERENCE_NOT_OPEN='参考尚未开放', NO_LEGAL_REFERENCE='无合法参考',
                 ONE_LEGAL_COMPONENT='恰一个合法组件', GEOMETRY_UNAVAILABLE='必要几何不可用',
                 ZERO_JOINT_SUPPORT_2D='二维联合支持为零', ZERO_JOINT_SUPPORT_3D_ONLY='二维有支持、三维为零',
                 GUARD_PREVENTED_WITHDRAWAL='保护实际阻断撤警', DEDUCTION_INSUFFICIENT='扣分仍不足')
    for r in d['aggregate']:
        if r['kind'] == 'FIRST_BLOCKER':
            md.append(f"| {names[r['category']]} | {r['count']:,} | {r['fraction']:.3%} | {r['weighted_fraction']:.3%} |")
    for r in d['aggregate']:
        if r['category'] in ('SINGLE_COMPONENT_ACTUAL_WITHDRAWAL', 'THEORETICAL_LIMIT_RESIDUAL'):
            label = '保留保护后单组件实际可撤警' if r['category'].startswith('SINGLE') else '超过理论最大扣分额度'
            md.append(f"\n{label}：{r['count']:,}/{r['denominator_rows']:,}。")
    md += ['', '## 固定工作点对照', '',
           '| 配置 | 正常误报/查询 | 普通 FPR | 加权 FPR | 攻击告警/查询 | 普通检出 | 加权检出 |',
           '|---|---:|---:|---:|---:|---:|---:|']
    baseline = load(HERE / 'evidence' / 'BASELINE_EXPECTED.json')['metrics']
    def headline(rows, title):
        r = {x['group']: x for x in rows if x['head'] == 'ensemble' and x['guard_stratum'] == 'ALL' and
             x['view'] == 'post_window_primary' and x['group'] in ('NORMAL', 'ATTACK')}
        n, a = r['NORMAL'], r['ATTACK']
        return (f"| {title} | {n['alarm_count']:,}/{n['rows']:,} | {n['sample_rate']:.6%} | "
                f"{n['hierarchical_rate']:.6%} | {a['alarm_count']:,}/{a['rows']:,} | "
                f"{a['sample_rate']:.6%} | {a['hierarchical_rate']:.6%} |")
    for name, title in [('RAW', 'RAW'), ('P4_COMMISSION_3D', '两小时库 p4'), ('P4_MAIN', '完整库 p4')]:
        md.append(headline([r for r in baseline if r['config'] == name], title))
    for name, r in comparisons.items():
        md.append(headline(r['metrics_headline'], name))
    md += ['', 'M 为 10,011 条两小时参考与 3,236 条历史参考的唯一固定候选。内容、组件和时间覆盖同时变化。',
           '完整与建档后视图、三个种子及集成、设备和协议、普通与加权指标均在各配置的指标和配对表。',
           '配对表中 n10 是从左臂到右臂的撤警，n01 是新增告警。CIC 和 Edge（含适用的 HT）见原验收复用表。']
    if 'C1' in comparisons:
        c = comparisons['C1']
        n = load(out / 'C1_CARDINALITY.json')
        flips = c['numeric']['decision_changes_by_head']
        md += ['', f"C1 精确保留 {n['total']:,} 条（历史 {n['history']:,} 条）。"
                   f"四头逐查询翻转数依次为 {flips}，判定验收为 {c['outcome']}。",
               f"连续值比较为 {c['numeric_comparison']}。任何保持性结论只覆盖本批固定查询。"]
    md += ['', '本地入口：FINAL_ACCEPTANCE.json、PULLBACK_MANIFEST.json、results/ 下的 D、M、C0、C1 文件。']
    write_text(control / 'RESULTS_FOR_PAPER.md', '\n'.join(md) + '\n')


def pull_manifest(control, out):
    files = {}
    for prefix, base, allowed in [('', control, CONTROL_FILES), ('results/', out, RESULT_FILES)]:
        for name in allowed:
            p = base / name
            if p.is_file():
                files[prefix + name] = artifact(p)
    for p in (out / 'logs').glob('*'):
        if re.fullmatch(r'(first|eval)-[0-9]+\.(out|err)', p.name) and p.is_file() and p.stat().st_size < 1024 ** 2:
            files['results/logs/' + p.name] = artifact(p)
    if (control / 'dispatch.log').is_file() and (control / 'dispatch.log').stat().st_size < 1024 ** 2:
        files['dispatch.log'] = artifact(control / 'dispatch.log')
    dump(control / 'PULLBACK_MANIFEST.json', dict(files=files, transfer_scope='small metrics/receipts/UID indices'))


def main(control, project):
    out = control / 'results'
    out.mkdir(exist_ok=True)
    config = config_at()
    resource = config['resource']
    stage = 'INSTALL'
    try:
        verify_package(HERE)
        audit = inspect_existing(project, control)
        dump(control / 'DUPLICATE_AUDIT.json', audit)
        require(audit['status'] == 'PASS', 'EXISTING_WORK_NEEDS_RECONCILIATION')
        dump(control / 'CHAIN_STATE.json', dict(stage='VERIFYING_REMOTE_INPUTS', updated_unix=time.time()))
        def admission_progress(stage, done, total, **detail):
            dump(control / 'REMOTE_ADMISSION_PROGRESS.json', dict(
                stage=stage, done=done, total=total, updated_unix=time.time(), **detail))
        store = Inputs(project, load(HERE / 'INPUT_PINS.json'), ('reference', 'query'),
                       progress=admission_progress)
        gate = store.verify()
        dump(control / 'DEPENDENCY_GATE.json', gate)
        require(gate['status'] == 'PASS', 'DEPENDENCY_GATE:' + ','.join(gate['failures']))
        runtime = verify_runtime_paths(project)
        dump(control / 'DEPENDENCY_GATE.json', dict(gate, runtime=runtime))
        first_job = dispatch_job(control, out, project, 'first', resource['partition'],
                                 resource['first_memory_mib'], resource['first_wall_seconds'])
        stage = 'FIRST'
        first = track(control, out, 'first', first_job)
        require(first['status'] == 'PASS', 'FIRST_RESULT_GATE')
        stage = 'MEASURED_RESOURCE_GATE'
        plan = load(out / 'RESOURCE_PLAN.json')
        require(plan['status'] == 'PASS' and
                0 < plan['eval_wall_seconds'] <= resource['eval_max_wall_seconds'] and
                0 < plan['eval_memory_mib'] <= resource['eval_max_memory_mib'], 'MEASURED_RESOURCE_BUDGET_STOP')
        eval_job = dispatch_job(control, out, project, 'eval', plan['partition'],
                                plan['eval_memory_mib'], plan['eval_wall_seconds'])
        stage = 'EVAL'
        second = track(control, out, 'eval', eval_job)
        stage = 'FINALIZE'
        v = verify_return(control, out, first, second)
        dump(control / 'CHAIN_STATE.json', dict(stage='ACCEPTED' if v['status'] == 'PASS' else 'PARTIAL_C0_FAILED',
             job_id=eval_job['job_id'], acceptance=v, updated_unix=time.time()))
        pull_manifest(control, out)
    except Exception as exc:
        sc = (maybe(control / 'SCHEDULER_' + stage.lower() + '.json') or {})
        start = maybe(out / ('SLURM_STOP_' + stage.lower() + '.json')) or {}
        marker = maybe(out / ('STOP_' + stage.lower() + '.json')) or {}
        phase = stage.lower()
        classification = ('INSTALL_OR_SUBMIT_FAILURE' if stage == 'INSTALL' else
                          'POST_RESULT_FAILURE' if stage == 'FINALIZE' else
                          'COMPUTE_STARTUP_FAILURE' if start.get('stage') == 'COMPUTE_STARTUP' or
                          (phase in ('first', 'eval') and not (out / f'RUNTIME_{phase}.json').is_file()) else
                          'RUNTIME_FAILURE')
        error = dict(stage='STOP', phase=stage, error=str(exc), classification=classification,
                     scheduler_state=sc.get('state'), worker_marker=marker.get('stage'),
                     updated_unix=time.time(), traceback=traceback.format_exc())
        dump(control / 'DISPATCH_STOP.json', error)
        dump(control / 'CHAIN_STATE.json', error)
        pull_manifest(control, out)
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--project', type=Path, default=ROOT)
    args = parser.parse_args()
    require(args.control.resolve() == (args.project / 'runs' / RUN).resolve(), 'RUN_SCOPE')
    main(args.control.resolve(), args.project.resolve())
