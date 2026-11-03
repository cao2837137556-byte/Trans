"""Cache-only P/E3/normalizer reconstruction. No T, K, retry, or source mutation."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
# A reconstruction never writes Python cache files into the frozen source tree.
sys.dont_write_bytecode = True
import continuous_common_v3 as c
import continuous_data_v3 as data
import continuous_runner_v3 as original
import continuous_features_engineering_v1 as features
import continuous_audit_engineering_v1 as audit
import frontend_resources_v1 as resources
from engineering_progress_v1 import Progress

CODE_FILES = ('continuous_rebuild_engineering_v1.py', 'frontend_resources_v1.py',
              'continuous_features_engineering_v1.py', 'continuous_audit_engineering_v1.py',
              'continuous_input_engineering_v1.py', 'spill_mapping_v1.py',
              'feature_batches_engineering_v1.py', 'engineering_progress_v1.py', 'resource_observation_v1.py',
              'scratch_registry_v1.py')


def code_identity():
    return {name: c.sha(Path(__file__).parent/name) for name in CODE_FILES}


def verify_frozen_sources(root):
    """The engineering entry may live outside root; its scientific imports must match."""
    source = Path(root)/'repo/ood'
    c.require((source/'continuous_runner_v3.py').is_file(), 'FRONTEND_FROZEN_SOURCES_MISSING')
    for frozen in source.glob('*.py'):
        if frozen.name not in CODE_FILES:
            c.pin(Path(__file__).parent/frozen.name, c.sha(frozen))


def authorize(root, plan_path, explicit):
    c.require(explicit, 'CACHE_REBUILD_NOT_AUTHORIZED')
    root = Path(root).resolve(); plan_path = Path(plan_path).resolve()
    design, base = c.authorize(root, explicit)
    verify_frozen_sources(root)
    plan = resources.load(plan_path)
    c.require(plan['workload_identity'] == dict(design_sha256=c.DESIGN_SHA,
              runtime_sha256=c.sha(root/'runtime_contract.json'), package_seal_sha256=c.sha(root/'SHA256SUMS')),
              'FRONTEND_WORKLOAD_IDENTITY')
    runtime = resources.runtime(base, plan)
    # This executable targets the declared Slurm job. Local tests mock the environment;
    # no implicit workstation execution or guessed allocation is enabled.
    c.require(bool(os.environ.get('SLURM_JOB_ID')), 'FRONTEND_SLURM_ALLOCATION_REQUIRED')
    c.require(os.environ.get('FRONTEND_RESOURCE_SHA') == c.sha(plan_path), 'FRONTEND_SUBMITTED_PLAN')
    c.require(int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) == plan['cpus'], 'FRONTEND_SLURM_CPUS')
    c.require(int(os.environ.get('SLURM_MEM_PER_NODE', '0')) == plan['memory_gib']*1024, 'FRONTEND_SLURM_MEMORY')
    c.require(int(os.environ.get('SLURM_JOB_NUM_NODES', '1')) == 1, 'FRONTEND_SINGLE_NODE')
    c.require(base['threads_per_worker'] == 4 and base['retries'] == 0, 'FRONTEND_FROZEN_RUNTIME')
    c.require(sys.version_info[:2] == (3, 9), 'PYTHON_39_REQUIRED')
    for package, expected in base['versions'].items():
        c.require(importlib.metadata.version(package).split('+')[0] == expected, 'TARGET_VERSION:'+package)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        c.require(os.environ.get(name) == '4', 'FRONTEND_THREADS:'+name)
    return design, runtime


def output_scope(root, run, runtime, *, existing=False):
    root, run = Path(root).resolve(), Path(run).resolve()
    protected = [root]
    for field in ('source_cache', 'source_inputs', 'external_run', 'external_raw', 'checkpoint'):
        protected.append(Path(runtime[field]).resolve())
    for source in protected:
        c.require(not run.is_relative_to(source) and not source.is_relative_to(run), 'FRONTEND_OUTPUT_SOURCE_OVERLAP')
    c.require(run.parent.is_dir(), 'FRONTEND_OUTPUT_PARENT_MISSING')
    c.require(run.is_dir() if existing else not run.exists(), 'FRONTEND_OUTPUT_ALREADY_EXISTS_OR_INVALID')
    return run


def environment(root, run, runtime):
    root = Path(root)
    c.require(shutil.disk_usage(run.parent).free >= runtime['minimum_free_gib']*1024**3, 'FRONTEND_DISK_RESERVE')
    checkpoint = c.pin(runtime['checkpoint'], runtime['checkpoint_sha256'])
    fixed = root/'vendor/netFound-base/model.safetensors'
    c.require(fixed.is_file(), 'FIXED_VENDOR_CHECKPOINT_MISSING:'+str(fixed))
    c.pin(fixed, runtime['checkpoint_sha256'])
    # Unlike frozen runtime_environment(), do not create a symlink in root/vendor.
    tshark = shutil.which(runtime['tshark']); c.require(tshark is not None, 'TSHARK_MISSING')
    version = subprocess.run([tshark, '--version'], capture_output=True, text=True, check=True).stdout.splitlines()[0]
    c.require('4.6.6' in version, 'TSHARK_VERSION')
    import torch
    info = dict(versions={x:importlib.metadata.version(x) for x in runtime['versions']},
                tshark=version, checkpoint_sha256=c.sha(checkpoint), threads_per_worker=4,
                torch_cpu_capability=torch.backends.cpu.get_cpu_capability(),
                lscpu=subprocess.run(['lscpu'], capture_output=True, text=True, check=True).stdout)
    return info


def authorize_worker(root, run, explicit):
    c.require(explicit, 'CACHE_REBUILD_NOT_AUTHORIZED')
    root, run = Path(root).resolve(), Path(run).resolve()
    launch = c.read(run/'launch.json')
    c.require(launch['scope'] == 'CACHE_ONLY_P_E3_NORMALIZERS' and launch['run'] == str(run) and
              launch['root'] == str(root), 'FRONTEND_WORKER_SCOPE')
    plan_path = Path(launch['resource_plan_path'])
    c.pin(plan_path, launch['resource_plan_sha256'])
    design, runtime = authorize(root, plan_path, explicit)
    output_scope(root, run, runtime, existing=True)
    c.require(launch['engineering_code'] == code_identity() and launch['package_seal_sha256'] == c.sha(root/'SHA256SUMS'),
              'FRONTEND_WORKER_CODE_IDENTITY')
    return design, runtime


def launch_features(root, run, runtime, progress):
    """Spawn only the planned E3 workers, carrying the same plan SHA and code path."""
    jobs = []
    try:
        for shard in range(runtime['feature_workers']):
            progress.guard()
            stream = (run/'logs'/('feature_%02d.log' % shard)).open('x', encoding='utf-8')
            command = [sys.executable, str(Path(__file__).resolve()), 'feature-worker', '--root', str(root),
                       '--run', str(run), '--shard', str(shard), '--authorize-cache-rebuild']
            try:
                child = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=os.name != 'nt')
            except BaseException:
                stream.close(); raise
            child.continuous_group = os.name != 'nt'; progress.children.append(child)
            jobs.append((shard, child, stream))
        while any(child.poll() is None for _,child,_ in jobs):
            progress.guard()
            for shard, child, _ in jobs:
                c.require(child.poll() in (None, 0), 'FRONTEND_WORKER_FAILED:'+str(shard))
            progress.closed.wait(2)
        for shard, child, _ in jobs:
            c.require(child.returncode == 0, 'FRONTEND_WORKER_FAILED:'+str(shard))
            c.require(c.read(run/('features_worker_%02d' % shard)/'status.json')['status'] == 'COMPLETE',
                      'FRONTEND_WORKER_FALSE_COMPLETION')
    finally:
        progress.kill_children()
        for _, child, stream in jobs:
            try: child.wait(timeout=10)
            except subprocess.TimeoutExpired: child.kill(); child.wait()
            stream.close()
        c.write(run/'feature_worker_exit_codes.json', {str(shard):child.returncode for shard,child,_ in jobs})


def rebuild(root, run, plan_path, explicit):
    design, runtime = authorize(root, plan_path, explicit)
    root, plan_path = Path(root).resolve(), Path(plan_path).resolve()
    run = output_scope(root, run, runtime)
    # All preflight is read-only and precedes output reservation or model loading.
    env = environment(root, run, runtime)
    run.mkdir(exist_ok=False); (run/'logs').mkdir()
    progress = Progress(run/'monitor', runtime['limits'], storage_scope=run)
    def stop_signal(signum, frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    old_handlers = {sig:signal.signal(sig, stop_signal) for sig in (signal.SIGTERM,signal.SIGINT)}
    try:
        c.write(run/'launch.json', dict(scope='CACHE_ONLY_P_E3_NORMALIZERS', root=str(root), run=str(run),
            design_sha256=c.DESIGN_SHA, package_seal_sha256=c.sha(root/'SHA256SUMS'),
            resource_plan_path=str(plan_path), resource_plan_sha256=c.sha(plan_path), engineering_code=code_identity(),
            real_optimizer_updates=0, target_scoring=False, retries=0))
        c.write(run/'environment.json', env)
        progress.stage = 'P_INPUT_IDENTITIES'; progress.tick()
        metadata, specs = data.load_inputs(root, runtime, design, run/'inputs')
        audit.preflight(root, run/'anomaly_preflight', metadata, specs, runtime, design, progress)
        data.old_tail_audit(metadata, c.read(run/'inputs/old_features.json'), run/'old_tail_audit.json')
        features.spool(root, run/'spool', metadata, specs, runtime, progress)
        c.write(run/'spool_pin.json', dict(sha256=c.sha(run/'spool/snapshots.sqlite')))
        progress.stage = 'P_TARGET_NUMERIC_RESOURCE_PROBE'; progress.tick()
        original.numeric_probe(root, run, runtime, design, progress)
        progress.stage = 'E3_WORKERS'; progress.tick()
        launch_features(root, run, runtime, progress)
        # Recheck plan and engineering source identity before joining the workers.
        authorize_worker(root, run, explicit)
        progress.stage = 'MERGE_NORMALIZE'; progress.tick()
        features.merge_features(run, metadata, runtime)
        original.prepare_normalizers(run, metadata, design, progress)
        c.write(run/'P_COMPLETE.json', dict(status='COMPLETE', scope='CACHE_ONLY_P_E3_NORMALIZERS',
            design_sha256=c.DESIGN_SHA, rows=design['data']['new_feature_rows'],
            input_seal=c.sha(run/'inputs/SHA256SUMS'), feature_seal=c.sha(run/'features/SHA256SUMS'),
            normalizer_seal=c.sha(run/'normalizers/SHA256SUMS'), real_optimizer_updates=0,
            target_scoring=False, resource_plan_sha256=c.sha(plan_path)))
        progress.stop('COMPLETE')
    except BaseException as exc:
        progress.record_failure(exc, 'cache_only_rebuild'); progress.stop('STOPPED_NO_RETRY', error=repr(exc)); raise
    finally:
        for sig, handler in old_handlers.items(): signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('rebuild', 'feature-worker'))
    parser.add_argument('--root', required=True); parser.add_argument('--run', required=True)
    parser.add_argument('--plan'); parser.add_argument('--shard', type=int)
    parser.add_argument('--authorize-cache-rebuild', action='store_true'); args = parser.parse_args()
    if args.mode == 'rebuild':
        c.require(args.plan is not None, 'FRONTEND_PLAN_PATH_REQUIRED')
        rebuild(args.root, args.run, args.plan, args.authorize_cache_rebuild)
    else:
        _, runtime = authorize_worker(args.root, args.run, args.authorize_cache_rebuild)
        c.require(args.shard is not None and 0 <= args.shard < runtime['feature_workers'], 'FRONTEND_SHARD')
        features.feature_worker(args.root, args.run, args.shard, args.authorize_cache_rebuild,
                                authorization=authorize_worker)


if __name__ == '__main__': main()
