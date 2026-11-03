"""Sequential cloud job, visible status, immutable stages, no automatic retry."""
import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import traceback
import package_io as io

FAMILIES = ('MLP_QUERY_BCE', 'TabM', 'LightGBM')
SEEDS = (27, 127, 227)
HEAD_STAGES = ('P',) + tuple('T_' + f + '_' + str(s) for f in FAMILIES for s in SEEDS) + ('K',)
MODULE_STAGES = tuple('M_' + f for f in FAMILIES)
STAGES = HEAD_STAGES + MODULE_STAGES


class Progress:
    def __init__(self, path):
        self.path = Path(path); self.stage = 'START'; self.optimizer_updates = 0; self.last = 0

    def tick(self, completed, total, force=False):
        if force or completed == total or time.monotonic() - self.last >= 5:
            io.write(self.path, dict(status='RUNNING', stage=self.stage, completed=int(completed),
                total=int(total), optimizer_updates=int(self.optimizer_updates), updated_epoch=time.time()), replace=True)
            self.last = time.monotonic()


def scope(config):
    run = Path(config['run']).resolve()
    protected = [Path(config['source_config'][k]).resolve() for k in ('cache', 'head_run', 'query_root', 'lineage_root')]
    protected += [io.ROOT, Path(config['onboarding_package']).resolve(), Path(config['banks_manifest']).resolve().parent]
    for source in protected:
        io.require(not run.is_relative_to(source) and not source.is_relative_to(run), 'INPUT_OUTPUT_OVERLAP')
    return run


def preflight(config, context, mode):
    import modern_adapter as adapter
    run = scope(config); plan = io.read(io.ROOT / 'resource_plan.json')
    io.require(shutil.disk_usage(run.parent).free >= plan['minimum_free_gib'] * 1024**3, 'FREE_DISK')
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        io.require(os.environ.get(name) == '4', 'FOUR_THREADS_REQUIRED:' + name)
    adapter.source_state(config, context)
    bank_identity = adapter.banks(config, context) if mode != 'heads' else None
    if mode == 'modules': adapter.verified_heads(config, context)
    return dict(status='READY_NO_EXPERIMENT_STARTED', mode=mode, lineage='NEW_RECONSTRUCTION_LINEAGE',
        bank_identity=bank_identity, runtime=adapter.runtime(),
        resource_plan_sha256=io.sha(io.ROOT / 'resource_plan.json'),
        code_manifest_sha256=io.sha(io.ROOT / 'code_manifest.json'))


def tree_rss():
    if os.name != 'posix': return 0
    table = {}
    for path in Path('/proc').glob('[0-9]*'):
        try:
            fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            table[int(path.name)] = (int(fields[1]), int((path / 'statm').read_text().split()[1]) * os.sysconf('SC_PAGE_SIZE'))
        except (OSError, ValueError, IndexError):
            pass
    ids = {os.getpid()}
    while True:
        found = {pid for pid, (parent, rss) in table.items() if parent in ids} - ids
        if not found: break
        ids.update(found)
    return sum(table.get(pid, (0, 0))[1] for pid in ids)


def disk_bytes(folder):
    return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file())


def terminate(child):
    if child is None or child.poll() is not None: return
    if os.name == 'posix': os.killpg(child.pid, signal.SIGTERM)
    else: child.terminate()
    try: child.wait(timeout=20)
    except subprocess.TimeoutExpired:
        if os.name == 'posix': os.killpg(child.pid, signal.SIGKILL)
        else: child.kill()
        child.wait(timeout=10)


def worker(config, name):
    import modern_adapter as adapter
    context = adapter.boot(config); run = scope(config)
    launch = io.read(run / 'stage_launch.json')
    io.require(launch['stage'] == name and launch['code_manifest_sha256'] == io.sha(io.ROOT / 'code_manifest.json'), 'WORKER_AUTHORITY')
    progress = Progress(run / 'monitor' / (name + '.json'))
    progress.stage = name; progress.tick(0, 1, force=True)
    if name == 'P': adapter.prepare(config, context, progress)
    elif name.startswith('T_'):
        family, seed = name[2:].rsplit('_', 1)
        adapter.train_one(config, context, family, int(seed), progress)
    elif name == 'K': adapter.evaluate(config, context, progress)
    else: adapter.onboard(config, context, name[2:], progress)
    progress.stage = name + '_COMPLETE'; progress.tick(1, 1, force=True)


def run(config, mode, authorized):
    io.require(authorized, 'EXPLICIT_CHAIN_REQUIRED')
    runroot = scope(config); plan = io.read(io.ROOT / 'resource_plan.json')
    if mode == 'modules':
        io.require(runroot.exists() and not (runroot / 'MODULES_STARTED.json').exists(), 'MODULE_NO_RETRY')
    else:
        io.require(not runroot.exists(), 'RUN_NO_RETRY')
        runroot.mkdir(parents=True)
        for name in ('heads/endpoints', 'logs', 'monitor', 'onboarding'):
            (runroot / name).mkdir(parents=True)
    stages = HEAD_STAGES if mode == 'heads' else MODULE_STAGES if mode == 'modules' else STAGES
    io.write(runroot / ('module_authorization.json' if mode == 'modules' else 'authorization.json'), dict(
        mode=mode, registered_scope='three_fixed_heads_plus_three_fixed_module_pairs',
        registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json'),
        code_manifest_sha256=io.sha(io.ROOT / 'code_manifest.json'), retries=0))
    started = time.monotonic(); child = None; stage = 'PREFLIGHT'; completed = []
    def stop(signum, frame): raise RuntimeError('SIGNAL:' + str(signum))
    previous = {s: signal.signal(s, stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        # Preflight in a separate process releases all import and metadata residency.
        cmd = [sys.executable, '-B', str(io.ROOT / 'modern_service.py'), 'preflight', '--mode', mode,
               '--receipt', str(runroot / ('module_preflight.json' if mode == 'modules' else 'preflight.json'))]
        with (runroot / 'logs' / ('module_preflight.log' if mode == 'modules' else 'preflight.log')).open('x') as stream:
            child = subprocess.Popen(cmd, stdout=stream, stderr=subprocess.STDOUT, start_new_session=os.name == 'posix')
            while child.poll() is None:
                io.require(tree_rss() < plan['guard_gib'] * 1024**3, 'MEMORY_GUARD')
                io.require(time.monotonic()-started < plan['wall_seconds'], 'WALL_GUARD')
                io.write(runroot / 'status.json', dict(status='RUNNING', stage='PREFLIGHT', completed_stages=0,
                    total_stages=len(stages), updated_epoch=time.time(), failure=None), replace=True)
                time.sleep(5)
            io.require(child.returncode == 0, 'PREFLIGHT_FAILED:' + str(child.returncode))
        for index, stage in enumerate(stages):
            if stage == MODULE_STAGES[0]:
                io.write(runroot / 'MODULES_STARTED.json', dict(
                    head_complete_sha256=io.sha(runroot / 'HEADS_COMPLETE.json'),
                    registration_sha256=io.sha(io.ROOT / 'supplementary_registration.json'),
                    banks_manifest_sha256=config['banks_manifest_sha256']))
            io.write(runroot / 'stage_launch.json', dict(stage=stage,
                code_manifest_sha256=io.sha(io.ROOT / 'code_manifest.json')), replace=True)
            peak = 0; last_check = 0
            with (runroot / 'logs' / (stage + '.log')).open('x', encoding='utf-8') as stream:
                child = subprocess.Popen([sys.executable, '-B', str(io.ROOT / 'modern_service.py'),
                    'worker', '--stage', stage], stdout=stream, stderr=subprocess.STDOUT,
                    start_new_session=os.name == 'posix')
                while True:
                    now = time.monotonic(); peak = max(peak, tree_rss())
                    io.require(peak < plan['guard_gib'] * 1024**3, 'MEMORY_GUARD')
                    io.require(now-started < plan['wall_seconds'], 'WALL_GUARD')
                    io.require(not (runroot / 'STOP_REQUESTED').exists(), 'STOP_REQUESTED')
                    if now-last_check >= 5:
                        io.require(disk_bytes(runroot) < plan['disk_gib'] * 1024**3, 'DISK_GUARD')
                        io.require(shutil.disk_usage(runroot).free > 1024**3, 'DISK_FREE_GUARD')
                        status = dict(status='RUNNING', stage=stage, completed_stages=index,
                            total_stages=len(stages), sampled_peak_tree_rss_bytes=peak,
                            elapsed_seconds=now-started, updated_epoch=time.time(), failure=None)
                        worker_status = runroot / 'monitor' / (stage + '.json')
                        if worker_status.is_file(): status['worker'] = io.read(worker_status)
                        module_status = runroot / 'onboarding' / stage[2:] / 'status.json'
                        if stage.startswith('M_') and module_status.is_file(): status['module'] = io.read(module_status)
                        io.write(runroot / 'status.json', status, replace=True)
                        last_check = now
                    if child.poll() is not None: break
                    time.sleep(.5)
                io.require(child.returncode == 0, 'STAGE_FAILED:' + stage + ':' + str(child.returncode))
            completed.append(stage)
            io.write(runroot / 'monitor' / (stage + '_receipt.json'), dict(status='COMPLETE',
                sampled_peak_tree_rss_bytes=peak, elapsed_seconds=time.monotonic()-started))
        status = 'HEADS_COMPLETE_MODULES_PENDING' if mode == 'heads' else 'COMPLETE'
        if mode != 'heads':
            io.write(runroot / 'COMPLETE.json', dict(status='COMPLETE', lineage='NEW_RECONSTRUCTION_LINEAGE',
                head_complete_sha256=io.sha(runroot / 'HEADS_COMPLETE.json'), paired_families=list(FAMILIES),
                three_device_regression='NOT_RUN', independent_confirmation='NOT_RUN', automatic_selection=False))
        io.write(runroot / 'status.json', dict(status=status, stage=status, completed_stages=len(stages),
            total_stages=len(stages), elapsed_seconds=time.monotonic()-started, updated_epoch=time.time(), failure=None), replace=True)
    except BaseException as exc:
        io.write(runroot / 'status.json', dict(status='STOPPED_NO_RETRY', stage=stage, completed=completed,
            failure=dict(error=repr(exc), traceback=traceback.format_exc()), updated_epoch=time.time()), replace=True)
        raise
    finally:
        terminate(child)
        for sig, handler in previous.items(): signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'run', 'worker'))
    parser.add_argument('--mode', choices=('full', 'heads', 'modules'), default='full')
    parser.add_argument('--stage', choices=STAGES)
    parser.add_argument('--receipt')
    parser.add_argument('--authorize-chain', action='store_true')
    args = parser.parse_args(); config = io.package()
    if args.action == 'run': run(config, args.mode, args.authorize_chain)
    elif args.action == 'worker':
        io.require(args.stage is not None, 'WORKER_STAGE_REQUIRED'); worker(config, args.stage)
    else:
        import modern_adapter as adapter
        result = preflight(config, adapter.boot(config), args.mode)
        if args.receipt: io.write(args.receipt, result)
        print(result, flush=True)


if __name__ == '__main__':
    main()
