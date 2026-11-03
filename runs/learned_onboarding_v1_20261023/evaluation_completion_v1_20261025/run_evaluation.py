"""One authorized evaluation, reusing sealed V4 inputs without fitting or retries."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback

SPEC_SHA = 'a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8'
PARENT = '/srv/paper04/learned_onboarding_20261024_v4'
NEW_ROOT = '/srv/paper04/learned_onboarding_eval_20261025_v1'
UNIT = 'paper04-learned-onboarding-eval-20261025-v1'
PACKAGE = 'runs/learned_onboarding_v1_20261023'
OUTPUT_LIMIT = 2 * 1024**3
RSS_LIMIT = 8 * 1024**3
HARD_LIMIT = 16 * 1024**3
REUSED = ['tests', 'prepare', 'validate', 'preflight', 'fit', 'calibration', 'target']
POOLS = ('CIC_DEV', 'UNSW_DEV')
ARMS = ('BASE', 'V3', 'L_STANDARD', 'L_HARD', 'L_QUERY_ONLY')
BANKS = ('OLD_BANK', 'B0', 'B1', 'B2')


class Stop(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Stop(message)


def now():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            h.update(block)
    return h.hexdigest()


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name+'.tmp-'+str(os.getpid()))
    with tmp.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(tmp, path)


def safe_child(root, name):
    path = (Path(root)/name).resolve()
    require(Path(root).resolve() in path.parents, 'PATH_ESCAPE:'+str(name))
    return path


def size(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file())


def expected_cells():
    main = {(p, b, a) for p in POOLS for b in BANKS for a in ARMS}
    controls = {(p, b, a) for p in POOLS for b in ('EMPTY', 'WRONG') for a in ARMS[2:]}
    return main, controls


def verify_seal(folder, expected=None):
    folder = Path(folder).resolve()
    seal_path = folder/'SEAL.json'
    if expected is not None:
        require(sha(seal_path) == expected, 'SEAL_IDENTITY:'+str(folder))
    value = read(seal_path)
    require(value['status'] == 'SEALED' and value['spec_sha256'] == SPEC_SHA, 'SEAL_SPEC')
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*')
              if p.is_file() and p.name != 'SEAL.json'}
    require(actual == set(value['files']), 'SEAL_EXTRA_OR_MISSING_FILES:'+str(folder))
    for name, expected_sha in value['files'].items():
        require(sha(safe_child(folder, name)) == expected_sha, 'SEALED_FILE_CHANGED:'+name)
    return value


def verify_inventory(parent, inventory, *, full=True):
    parent = Path(parent).resolve()
    for name, item in inventory['files'].items():
        p = safe_child(parent, name)
        require(p.is_file(), 'PROTECTED_FILE_MISSING:'+name)
        stat = p.stat()
        require(stat.st_size == item['bytes'] and stat.st_mtime_ns == item['mtime_ns'],
                'PROTECTED_FILE_STAT_CHANGED:'+name)
        if full:
            require(sha(p) == item['sha256'], 'PROTECTED_FILE_SHA_CHANGED:'+name)
    for name in inventory['census_roots']:
        folder = safe_child(parent, name)
        actual = {p.relative_to(parent).as_posix() for p in folder.rglob('*') if p.is_file()}
        expected = {p for p in inventory['files'] if p.startswith(name+'/')}
        require(actual == expected, 'PROTECTED_DIRECTORY_CENSUS_CHANGED:'+name)


def budget_plan(inventory):
    """Conservative forecast from prior fixed-data artifacts, never a raised limit."""
    files = inventory['files']
    per_pool = {}
    for pool in POOLS:
        prefix = PACKAGE+'/results/evaluation/predictions/'+pool+'/'
        samples = [v['bytes'] for p, v in files.items()
                   if p.startswith(prefix) and p.endswith('/predictions.jsonl.gz')]
        require(bool(samples), 'MISSING_OUTPUT_SIZE_EVIDENCE:'+pool)
        per_pool[pool] = dict(observed_files=len(samples), max_cell_bytes=max(samples),
                              expected_cells=26, predicted_upper_bytes=2*26*max(samples))
    summaries = [v['bytes'] for p, v in files.items() if p.startswith(PACKAGE+'/results/evaluation/')
                 and p.endswith('/summary.json')]
    require(bool(summaries), 'MISSING_SUMMARY_SIZE_EVIDENCE')
    control_bytes = files[PACKAGE+'/results/evaluation/control_plan.json']['bytes']
    predictions = sum(v['predicted_upper_bytes'] for v in per_pool.values())
    summary_upper = 2*52*max(summaries)
    # Main paired_summary duplicates forty summaries; the second copy is explicit.
    paired_upper = 2*40*max(summaries) + 1024**2
    metadata_upper = 16*1024**2
    total = predictions + 2*control_bytes + summary_upper + paired_upper + metadata_upper
    require(total <= OUTPUT_LIMIT, 'EVALUATION_OUTPUT_FORECAST_EXCEEDS_REGISTERED_LIMIT')
    memory = max(inventory['parent_peak_rss']+512*1024**2, inventory['parent_estimated_peak_rss'])
    require(memory <= RSS_LIMIT, 'EVALUATION_MEMORY_FORECAST_EXCEEDS_REGISTERED_LIMIT')
    return dict(schema='learned-onboarding-evaluation-resource-plan-v1', status='READY',
                estimates_only=True, expected_main_cells=40, expected_control_cells=12,
                expected_prediction_rows=26*sum(inventory['pool_rows'].values()),
                empirical_cell_size_safety_factor=2, per_pool=per_pool,
                control_plan_upper_bytes=2*control_bytes, summaries_upper_bytes=summary_upper,
                paired_summary_upper_bytes=paired_upper, metadata_upper_bytes=metadata_upper,
                estimated_output_upper_bytes=total, output_limit_bytes=OUTPUT_LIMIT,
                estimated_peak_rss=memory, rss_guard_bytes=RSS_LIMIT,
                retained_parent_results_bytes=inventory['parent_results_bytes'],
                output_budget_scope='new evaluation results only; retained V4 is read-only input',
                parent_original_chain_remains_exception_stop=True,
                scientific_recipe_changed=False, new_training_updates=0,
                cpu_threads=4, heavy_workers=1, environment_memory_ceiling_bytes=HARD_LIMIT)


def inspect_parent(parent):
    """Read-only input/size inventory for preparing the pinned execution contract."""
    parent = Path(parent).resolve()
    require(str(parent) == PARENT, 'UNEXPECTED_PARENT_ROOT')
    deployment = read(parent/'DEPLOYMENT_MANIFEST.json')
    paths = {parent/name for name in deployment['files']}
    paths.update((parent/'DEPLOYMENT_MANIFEST.json', parent/'state/EXCEPTION_STOP.json',
                  parent/'state/status.json', parent/'state/execution_contract.json'))
    census = [PACKAGE+'/results', 'inputs/target_bundle', 'inputs/source_head_archive']
    for name in census:
        paths.update(p for p in (parent/name).rglob('*') if p.is_file())
    entries = {}
    for path in sorted(paths):
        require(path.is_file() and parent in path.resolve().parents, 'PARENT_INVENTORY_PATH')
        stat = path.stat()
        entries[path.relative_to(parent).as_posix()] = dict(
            bytes=stat.st_size, mtime_ns=stat.st_mtime_ns, sha256=sha(path))
    for name, entry in deployment['files'].items():
        expected = entry['sha256'] if isinstance(entry, dict) else entry
        require(entries[name]['sha256'] == expected, 'PARENT_DEPLOYMENT_CHANGED:'+name)
    results = parent/PACKAGE/'results'
    state = read(parent/'state/status.json')
    require(state['status'] == 'EXCEPTION_STOP' and state['error'] == 'OUTER_RESOURCE_OUTPUT_LIMIT',
            'UNEXPECTED_PARENT_TERMINAL_STATE')
    require(not (parent/'state/CHAIN_COMPLETE.json').exists(), 'PARENT_ALREADY_COMPLETE')
    require(set(REUSED) <= set(state['completed_stages']), 'PARENT_SOURCE_STAGES_INCOMPLETE')
    verify_seal(results/'fit'); verify_seal(results/'calibration'); verify_seal(results/'preflight')
    pool_rows, identities = {}, {}
    for pool in POOLS:
        summary = read(results/'evaluation/predictions'/pool/'B0/BASE/summary.json')
        pool_rows[pool] = summary['rows']
        identities[pool] = {k: summary[k] for k in ('rows','ordered_uid_sha256','base_score_sha256','cut')}
    return dict(schema='learned-onboarding-evaluation-parent-inventory-v1', parent_root=str(parent),
                checked_at=now(), files=entries, census_roots=census,
                parent_results_bytes=size(results), parent_peak_rss=state['peak_process_tree_rss'],
                parent_estimated_peak_rss=read(results/'preflight/resource_plan.json')['estimated_peak_rss'],
                pool_rows=pool_rows, pool_identities=identities)


def verify_payload(root, expected_sha):
    require(len(expected_sha or '') == 64, 'NEW_PAYLOAD_MANIFEST_SHA_REQUIRED')
    root = Path(root).resolve()
    manifest = root/'DEPLOYMENT_MANIFEST.json'
    require(sha(manifest) == expected_sha, 'NEW_PAYLOAD_MANIFEST_CHANGED')
    data = read(manifest)
    require(data['spec_sha256'] == SPEC_SHA, 'NEW_PAYLOAD_SPEC')
    for name, item in data['files'].items():
        p = safe_child(root, name)
        require(p.stat().st_size == item['bytes'] and sha(p) == item['sha256'], 'NEW_PAYLOAD_CHANGED:'+name)
    return read(root/'contract.json'), read(root/'parent_inventory.json')


def worker(root, manifest_sha):
    """Bootstrap original modules and call only their frozen evaluation function."""
    root = Path(root).resolve()
    contract, inventory = verify_payload(root, manifest_sha)
    parent = Path(contract['parent_root'])
    package = parent/PACKAGE
    stage = root/'state/stages/evaluation'
    output = root/'results/evaluation'
    for key in ('OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','NUMEXPR_NUM_THREADS'):
        require(os.environ.get(key) == '4', 'NUMERIC_THREAD_ENVIRONMENT:'+key)
    sys.path.insert(0, str(parent/'repo/ood'))
    sys.path.insert(0, str(package/'src'))
    import common as c
    import learning
    import pipeline
    from source_inputs import ARCHIVE_WANTED, prepare_source
    from bundle_io import load_targets
    learning._setup()
    c.check_spec()
    require(c.ROOT.resolve() == parent.resolve(), 'ORIGINAL_MODULE_ROOT_CHANGED')
    runtime = c.environment()
    require(runtime == read(package/'results/fit/runtime.json')['runtime'], 'FIT_RUNTIME_CHANGED')
    require(runtime == read(package/'results/calibration/runtime.json')['runtime'], 'CAL_RUNTIME_CHANGED')
    write(stage/'runtime.json', dict(runtime=runtime, executable=sys.executable, recorded_at=now()))
    c.verify_seal(package/'results/fit'); c.verify_seal(package/'results/calibration')
    c.verify_seal(package/'results/preflight')
    pipeline._verify_fit_code(package/'results/fit')
    assets = package/'results/source_assets'
    require(all((assets/name).is_file() for name in ARCHIVE_WANTED), 'EXISTING_SOURCE_ASSET_MISSING')
    write(stage/'worker.json', dict(status='RUNNING', stage='prepare_source_existing_assets',
                                    new_training_updates=0, updated_at=now()))
    config_path = package/'deployment_20261024/remote_config.json'
    config = read(config_path)
    require(config['schema'] == 'learned-onboarding-local-config-v1' and
            config['spec_sha256'] == SPEC_SHA, 'CONFIG_SPEC')
    source = prepare_source(config=config['source'], output_dir=assets, validate_only=False)
    require(source['binding'] == read(package/'results/fit/input_binding.json'), 'SOURCE_BINDING_CHANGED')
    plan = read(package/'results/preflight/resource_plan.json')
    require(plan['status'] == 'READY' and plan['synthetic_timing_complete'] and
            plan['spec_sha256'] == SPEC_SHA and plan['config_sha256'] == sha(config_path) and
            plan['input_binding_digest'] == c.digest(source['binding']) and
            plan['execution_slot'] == 'exclusive-existing-remote', 'PARENT_PREFLIGHT_IDENTITY')
    target = parent/'inputs/target_bundle/target_manifest.json'
    target_sha = inventory['files'][target.relative_to(parent).as_posix()]['sha256']
    require(sha(target) == target_sha, 'TARGET_MANIFEST_CHANGED')
    verify_inventory(parent, inventory, full=False)
    write(stage/'SOURCE_REUSE_VERIFIED.json', dict(status='PASS', verified_at=now(),
          source_binding=source['binding'], runtime_unchanged=True, target_manifest_sha256=target_sha,
          new_training_updates=0, calibration_recomputed=False, original_code_unchanged=True))
    loader = lambda: load_targets(target, expected_sha256=target_sha,
        source_binding_digest=c.digest(source['binding']), cut=source['cut'],
        normalizer_sha256=source['binding']['normalizer_sha256'], source_binding=source['binding'])
    require(not output.exists(), 'FRESH_EVALUATION_OUTPUT_REQUIRED')
    write(stage/'worker.json', dict(status='RUNNING', stage='evaluation', updated_at=now(),
                                   new_training_updates=0))
    guard = c.Guard(output, budget_folder=root/'results')
    decision = pipeline.evaluate_targets(source, package/'results/fit', package/'results/calibration',
                                         loader, output, guard=guard)
    write(stage/'WORKER_COMPLETE.json', dict(status='COMPLETE', completed_at=now(),
          scientific_decision_status=decision['status'], new_training_updates=0,
          evaluation_seal_sha256=sha(output/'SEAL.json')))
    return 0


def validate_evaluation(root, parent, inventory, progress=None):
    output = Path(root)/'results/evaluation'
    verify_seal(output)
    done = read(output/'EVALUATION_COMPLETE.json')
    require(done['status'] == 'COMPLETE' and done['cells'] == 40 and done['synthetic_only'] is False,
            'EVALUATION_COMPLETION_IDENTITY')
    paired = read(output/'paired_summary.json')
    main, controls = expected_cells()
    require(paired['status'] == 'COMPLETE' and len(paired['cells']) == 40 and
            {(x['pool'],x['bank'],x['arm']) for x in paired['cells']} == main, 'MAIN_MATRIX_INCOMPLETE')
    summaries = {tuple(p.relative_to(output/'predictions').parts[:3]): p
                 for p in (output/'predictions').rglob('summary.json')}
    require(set(summaries) == main | controls, 'FULL_52_CELL_MATRIX_INCOMPLETE')
    prior_prefix = PACKAGE+'/results/evaluation/predictions/'
    prior_cells = {tuple(p[len(prior_prefix):].split('/')[:3]) for p in inventory['files']
                   if p.startswith(prior_prefix) and p.endswith('/summary.json')}
    require(prior_cells <= set(summaries), 'PREVIOUS_SUMMARY_SET_NOT_COVERED')
    embedded = {(x['pool'], x['bank'], x['arm']): x['summary'] for x in paired['cells']}
    compared = 0
    count = 0
    for key in sorted(summaries):
        summary = read(summaries[key])
        if key in main:
            require(embedded[key] == summary, 'PAIRED_SUMMARY_FILE_MISMATCH:'+str(key))
        require((summary['pool'],summary['bank'],summary['arm']) == key and
                summary['spec_sha256'] == SPEC_SHA, 'CELL_IDENTITY')
        require(all(summary[k] == v for k,v in inventory['pool_identities'][key[0]].items()),
                'CELL_BASELINE_CHANGED')
        previous = Path(parent)/PACKAGE/'results/evaluation/predictions'/Path(*key)/'summary.json'
        if previous.is_file():
            require(read(previous) == summary, 'PREVIOUS_COMPLETED_SUMMARY_CHANGED:'+str(key))
            compared += 1
        # Stream to EOF: verifies gzip CRC/trailer and complete query counts without large buffers.
        n = 0
        with gzip.open(summaries[key].parent/'predictions.jsonl.gz', 'rb') as stream:
            for line in stream:
                require(line.endswith(b'\n'), 'PREDICTION_ROW_TRUNCATED')
                n += 1
        require(n == summary['rows'], 'PREDICTION_ROW_COUNT:'+str(key))
        count += n
        if progress:
            progress(key)
    require(compared == len(prior_cells), 'PREVIOUS_SUMMARY_COMPARISON_COUNT')
    decision = read(output/'decision.json')
    require(decision['status'] == 'EVALUATED' and decision['automatic_promotion'] is False,
            'SCIENTIFIC_DECISION_RECORD_MISSING')
    return dict(status='PASS', main_cells=40, control_cells=12, prediction_rows=count,
                gzip_crc_and_row_count_verified=True, prior_summaries_equal=compared,
                evaluation_seal_sha256=sha(output/'SEAL.json'), scientific_decision=decision,
                engineering_completion_does_not_assert_scientific_pass=True)


def terminate_child(child):
    """Popen alone owns waitpid for its direct child; retain the actual return code."""
    if child is None or child.poll() is not None:
        return
    import psutil
    try:
        descendants = psutil.Process(child.pid).children(recursive=True)
    except psutil.NoSuchProcess:
        descendants = []
    for process in reversed(descendants):
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    child.terminate()
    try:
        child.wait(timeout=10)
    except subprocess.TimeoutExpired:
        child.kill(); child.wait(timeout=10)
    _, alive = psutil.wait_procs(descendants, timeout=5)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass


class Runner:
    def __init__(self, root, manifest_sha):
        self.root = Path(root).resolve()
        self.manifest_sha = manifest_sha
        self.contract, self.inventory = verify_payload(self.root, manifest_sha)
        require(self.contract['root'] == str(self.root) == NEW_ROOT and
                self.contract['parent_root'] == PARENT and self.contract['unit'] == UNIT,
                'EXECUTION_ROOT_IDENTITY')
        require(self.contract['output_limit_bytes'] == OUTPUT_LIMIT and
                self.contract['rss_guard_bytes'] == RSS_LIMIT, 'REGISTERED_LIMIT_CHANGED')
        self.parent = Path(PARENT)
        self.state = self.root/'state'
        self.started = time.monotonic()
        self.started_at = now()
        self.peak = 0
        self.child = None
        self.owns_state = False
        self.last_status = -float('inf')
        self.last_inventory_check = -float('inf')
        self.phase = 'verify_protected_inputs'
        self.complete = False

    def disk(self):
        n = size(self.root/'results')
        remaining = max(0, OUTPUT_LIMIT-n)
        return dict(output_bytes=n, output_limit_bytes=OUTPUT_LIMIT,
                    retained_parent_results_bytes=self.inventory['parent_results_bytes'],
                    disk_free_bytes=shutil.disk_usage(self.root).free,
                    minimum_disk_free_bytes=2*remaining,
                    output_budget_scope='new evaluation results; retained V4 inputs separately recorded')

    def guard(self, force=False):
        import psutil
        process = psutil.Process()
        rss = 0
        for p in [process]+process.children(recursive=True):
            try:
                rss += p.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        self.peak = max(self.peak, rss)
        require(rss <= RSS_LIMIT, 'OUTER_RESOURCE_RSS_LIMIT')
        report = self.disk()
        require(report['output_bytes'] <= OUTPUT_LIMIT, 'OUTER_RESOURCE_OUTPUT_LIMIT')
        require(report['disk_free_bytes'] >= report['minimum_disk_free_bytes'], 'INSUFFICIENT_DISK_HEADROOM')
        require(time.monotonic()-self.started <= 24*3600, 'CHAIN_ADMINISTRATIVE_TIME_LIMIT')
        require(size(self.state) <= 64*1024**2, 'STATE_LOG_OUTPUT_LIMIT')
        if force or time.monotonic()-self.last_inventory_check >= 30:
            verify_payload(self.root, self.manifest_sha)
            verify_inventory(self.parent, self.inventory, full=False)
            self.last_inventory_check = time.monotonic()
        self.status('RUNNING', force=force)

    def status(self, status, force=False, **extra):
        current = time.monotonic()
        if not force and current-self.last_status < 5:
            return
        self.last_status = current
        progress = self.root/'results/evaluation/status.json'
        if progress.is_file():
            last_internal = read(progress)
            worker_status = (last_internal if status == 'RUNNING' else dict(
                status=status, stage=self.phase, updated_at=now(),
                new_training_updates=0, last_internal_snapshot=last_internal))
            write(self.state/'stages/evaluation/worker.json', worker_status)
        elif status != 'RUNNING':
            previous = self.state/'stages/evaluation/worker.json'
            write(previous, dict(status=status, stage=self.phase, updated_at=now(),
                  new_training_updates=0,
                  last_internal_snapshot=read(previous) if previous.is_file() else None))
        write(self.state/'status.json', dict(
            schema='learned-onboarding-deployment-progress-v1', version='V4-EVAL1',
            status=status, stage='evaluation', execution_phase=self.phase,
            parent_root=PARENT, started_at=self.started_at, updated_at=now(),
            elapsed_seconds=current-self.started, reused_stages=REUSED,
            completed_stages=REUSED+(['evaluation'] if self.complete else []),
            new_training_updates=0, automatic_retry=False, peak_process_tree_rss=self.peak,
            rss_guard_bytes=RSS_LIMIT, chain_administrative_limit_seconds=24*3600,
            **self.disk(), **extra))

    def execute(self):
        require(not self.state.exists() and not (self.root/'results').exists(),
                'FRESH_STATE_REQUIRED_NO_RESUME')
        self.state.mkdir()
        self.owns_state = True
        write(self.state/'execution_contract.json', dict(self.contract, started_at=self.started_at,
            output_budget_scope='new evaluation results only; original V4 remains failed and retained',
            counted_outputs=[str(self.root/'results')], reused_stages=REUSED,
            initial_disk_report=self.disk(), administrative_limit_is_not_training_eta=True))
        self.guard(force=True)
        verify_inventory(self.parent, self.inventory, full=True)
        verify_seal(self.parent/PACKAGE/'results/fit')
        verify_seal(self.parent/PACKAGE/'results/calibration')
        plan = budget_plan(self.inventory)
        require(self.disk()['disk_free_bytes'] >= 2*plan['estimated_output_upper_bytes'],
                'PREFLIGHT_DISK_HEADROOM')
        write(self.state/'resource_plan.json', plan)
        self.phase = 'source_identity_then_evaluation'
        stage = self.state/'stages/evaluation'
        stage.mkdir(parents=True)
        command = [sys.executable,'-B','-u',str(self.root/'run_evaluation.py'),
                   '--root',str(self.root),'--manifest-sha256',self.manifest_sha,'--worker']
        write(stage/'invocation.json', dict(command=command, started_at=now(), automatic_retry=False))
        started = time.monotonic()
        completion_observed, termination_requested = False, False
        with (stage/'output.log').open('xb') as log:
            self.child = subprocess.Popen(command, cwd=str(self.root), stdin=subprocess.DEVNULL,
                                          stdout=log, stderr=subprocess.STDOUT)
            try:
                while True:
                    self.guard()
                    try:
                        rc = self.child.wait(timeout=1)
                        completion_observed = True
                        break
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                termination_requested = True
                terminate_child(self.child)
                raise
            finally:
                if self.child.poll() is not None:
                    write(stage/'process_exit.json', dict(returncode=self.child.returncode,
                        completion_observed=completion_observed, termination_requested=termination_requested,
                        normal_exit_observed=completion_observed and not termination_requested,
                        elapsed_seconds=time.monotonic()-started, ended_at=now()))
        self.child = None
        require(rc == 0, 'EVALUATION_WORKER_NONZERO:'+str(rc))
        require(read(stage/'WORKER_COMPLETE.json')['status'] == 'COMPLETE', 'WORKER_NOT_COMPLETE')
        self.phase = 'final_output_and_input_verification'
        self.guard(force=True)
        accepted = validate_evaluation(self.root, self.parent, self.inventory,
                                      progress=lambda key: self.guard())
        verify_inventory(self.parent, self.inventory, full=True)
        self.guard(force=True)
        write(self.state/'ACCEPTANCE.json', accepted)
        self.complete = True
        self.phase = 'complete'
        write(self.state/'CHAIN_COMPLETE.json', dict(
            schema='learned-onboarding-deployment-complete-v1', status='COMPLETE', ended_at=now(),
            execution_scope='evaluation-only completion using sealed V4 source stages',
            parent_root=PARENT, parent_original_status='EXCEPTION_STOP', parent_inputs_preserved=True,
            reused_stages=REUSED, newly_completed_stages=['evaluation'],
            completed_stages=REUSED+['evaluation'], new_training_updates=0, automatic_retry=False,
            evaluation_seal_sha256=accepted['evaluation_seal_sha256'],
            scientific_decision=str(self.root/'results/evaluation/decision.json'),
            engineering_completion_does_not_assert_scientific_pass=True))
        self.status('COMPLETE', force=True)
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(NEW_ROOT))
    parser.add_argument('--manifest-sha256')
    parser.add_argument('--worker', action='store_true')
    parser.add_argument('--inspect-parent', action='store_true')
    args = parser.parse_args(argv)
    if args.inspect_parent:
        print(json.dumps(inspect_parent(PARENT), ensure_ascii=False))
        return 0
    if args.worker:
        try:
            return worker(args.root, args.manifest_sha256)
        except BaseException as error:
            write(args.root/'state/stages/evaluation/child_exception.json', dict(
                status='EXCEPTION_STOP', error_type=type(error).__name__, error=str(error),
                stopped_at=now(), traceback=traceback.format_exc(), automatic_retry=False))
            traceback.print_exc()
            return 1
    runner = None
    try:
        runner = Runner(args.root, args.manifest_sha256)
        def interrupted(signum, frame):
            raise Stop('EXTERNAL_SIGNAL:'+str(signum))
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        return runner.execute()
    except BaseException as error:
        if runner is not None:
            terminate_child(runner.child)
            if runner.owns_state:
                # Stop reporting must work even when the guard itself failed.
                runner.status('EXCEPTION_STOP', force=True, error=str(error))
                write(runner.state/'EXCEPTION_STOP.json', dict(
                    schema='learned-onboarding-deployment-exception-v1', status='EXCEPTION_STOP',
                    stage='evaluation', execution_phase=runner.phase, error_type=type(error).__name__,
                    error=str(error), traceback=traceback.format_exc(), stopped_at=now(),
                    completed_stages=REUSED, automatic_retry=False, existing_artifacts_retained=True))
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
