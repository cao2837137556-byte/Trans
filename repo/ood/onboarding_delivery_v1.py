"""A single fixed reference-preparation and paired-evaluation chain, no training.

Each heavy stage runs in a fresh process. Raw preparation owns its scratch-file
monitor; the supervisor never races a child process's private SQLite cleanup.
"""
import argparse
import importlib.metadata
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import continuous_common_v3 as c
import onboarding_resources_v1 as resources
from engineering_progress_v1 import disk_bytes
from legacy_unsw_archival_runtime_v1 import tree_rss
from resource_observation_v1 import StageRecorder, RSS_SCOPE

PROTOCOL_SHA = '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5'
DESIGN_SHA = 'c6027a90f1f997b1bb1e8dd44409237531d7dc97cc13813e9bec364dc40b21af'
POOLS = ('CIC_DEV', 'UNSW_DEV')
POLICIES = ('B0', 'B1', 'B2')
STAGES = tuple('raw-'+p for p in POOLS) + tuple('encode-'+p+'-'+b for p in POOLS for b in POLICIES) + ('evaluate',)


def check_run_scope(root, runtime):
    root = Path(root).resolve(); run = root/'runs/onboarding'
    c.require(run.resolve() == run, 'ONBOARDING_RUN_PATH_REDIRECTED')
    for relative in ('raw', 'encoded', 'evaluation', 'encoder_runtime', 'monitor', 'logs'):
        path = run/relative
        c.require(path.resolve() == path, 'ONBOARDING_RUN_PATH_REDIRECTED:'+relative)
    inputs = [Path(p).resolve() for p in runtime['paths'].values()]
    inputs += [Path(s['capture']['path']).resolve() for s in runtime['captures'].values()]
    for source in inputs:
        c.require(not run.is_relative_to(source) and not source.is_relative_to(run), 'ONBOARDING_INPUT_OUTPUT_OVERLAP')
    return run


def load_contract(root, require_allocation=False):
    root = Path(root).resolve(); c.verify(root, exact=False)
    runtime = c.read(root/'runtime_contract.json')
    plan = resources.load(root/'resource_plan.json')
    c.pin(root/'protocol.json', PROTOCOL_SHA); c.pin(root/'query_tail_design.json', DESIGN_SHA)
    c.require(runtime['protocol_sha256'] == PROTOCOL_SHA and runtime['query_tail_design_sha256'] == DESIGN_SHA and
              runtime['arm'] == 'QUERY_TAIL' and runtime['retries'] == 0 and runtime['optimizer_updates'] == 0,
              'ONBOARDING_FROZEN_METHOD')
    c.require(runtime['resource_plan_sha256'] == c.sha(root/'resource_plan.json'), 'ONBOARDING_RUNTIME_PLAN')
    identity = plan['workload_identity']
    c.require(identity['protocol_sha256'] == PROTOCOL_SHA and identity['query_tail_design_sha256'] == DESIGN_SHA and
              identity['head_package_seal_sha256'] == runtime['head_package_seal_sha256'] and
              identity['target_pools'] == list(POOLS) and identity['target_policies'] == ['OLD_BANK']+list(POLICIES),
              'ONBOARDING_WORKLOAD_IDENTITY')
    for field in ('cpus', 'memory_gib', 'guard_gib', 'disk_gib', 'minimum_free_gib',
                  'wall_seconds', 'export_included_limit_gib', 'state_storage', 'slurm_time'):
        c.require(runtime[field] == plan[field], 'ONBOARDING_RUNTIME_DRIFT:'+field)
    for path, digest in runtime['scientific_code_sha256'].items():
        c.pin(root/'repo/ood'/path, digest)
    c.require(set(runtime['captures']) == set(POOLS), 'ONBOARDING_CAPTURE_ROSTER')
    paths = {name:Path(value).resolve() for name,value in runtime['paths'].items()}
    c.require(paths['head_run'] == paths['head_root']/'runs/query_tail', 'ONBOARDING_HEAD_RUN_SCOPE')
    for source in paths.values():
        c.require(not root.is_relative_to(source) and not source.is_relative_to(root), 'ONBOARDING_INPUT_OUTPUT_OVERLAP')
    for spec in runtime['captures'].values():
        raw = Path(spec['capture']['path']).resolve()
        c.require(not raw.is_relative_to(root) and not root.is_relative_to(raw), 'ONBOARDING_RAW_OUTPUT_OVERLAP')
    if require_allocation:
        c.require(os.environ.get('SLURM_JOB_ID'), 'ONBOARDING_SLURM_REQUIRED')
        c.require(os.environ.get('ONBOARDING_RESOURCE_SHA') == c.sha(root/'resource_plan.json'), 'ONBOARDING_SUBMITTED_PLAN')
        c.require(int(os.environ.get('SLURM_CPUS_PER_TASK', '0')) == plan['cpus'] and
                  int(os.environ.get('SLURM_MEM_PER_NODE', '0')) == plan['memory_gib']*1024 and
                  int(os.environ.get('SLURM_JOB_NUM_NODES', '1')) == 1, 'ONBOARDING_SLURM_ALLOCATION')
    return runtime, plan


def preflight(root):
    """Read-only prerequisites, no model loading, fitting, decoding or scoring."""
    root = Path(root).resolve(); runtime, plan = load_contract(root)
    c.require(sys.version_info[:2] == (3, 9), 'PYTHON39_REQUIRED')
    for name, version in runtime['versions'].items():
        c.require(importlib.metadata.version(name).split('+')[0] == version, 'ONBOARDING_VERSION:'+name)
    for name in runtime['additional_required_packages']:
        importlib.metadata.version(name)
    for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
        c.require(os.environ.get(name) == '4', 'ONBOARDING_THREADS:'+name)
    c.require(shutil.disk_usage(root).free >= plan['minimum_free_gib']*1024**3, 'ONBOARDING_FREE_DISK')
    paths = runtime['paths']; parent = Path(paths['parent']); head = Path(paths['head_run'])
    c.pin(Path(paths['head_root'])/'SHA256SUMS', runtime['head_package_seal_sha256'])
    c.verify(paths['head_root'], exact=False)
    import constrained_onboarding_query_tail_adapter_v2 as adapter
    adapter._required_files(parent, head, root/'query_tail_design.json')
    for name, digest in adapter.PARENT_PINS.items():
        c.pin(parent/name, digest)
    for name in ('inputs', 'features', 'normalizers'):
        design = c.read(root/'query_tail_design.json')
        key = {'inputs':'input_manifest_sha256','features':'feature_manifest_sha256','normalizers':'normalizer_manifest_sha256'}[name]
        c.pin(parent/name/'SHA256SUMS', design['provenance'][key]); c.verify(parent/name)
    c.pin(parent/'spool/snapshots.sqlite', design['provenance']['spool_sha256'])
    c.pin(parent/'normalizers/RECENT.npz', runtime['normalizer_sha256'])
    c.verify(head)
    for name in ('P_COMPLETE.json', 'T_COMPLETE.json', 'K_COMPLETE.json'):
        c.require(c.read(head/name)['status'] == 'COMPLETE', 'ONBOARDING_HEAD_NOT_COMPLETE:'+name)
    c.pin(paths['checkpoint'], runtime['checkpoint_sha256'])
    tshark = shutil.which(runtime['tshark'])
    c.require(tshark is not None, 'TSHARK_MISSING')
    version = subprocess.run([tshark, '--version'], capture_output=True, text=True, check=True, timeout=30).stdout
    c.require(runtime['tshark_version'] in version.splitlines()[0], 'TSHARK_VERSION')
    for spec in runtime['captures'].values():
        capture = spec['capture']; path = c.pin(capture['path'], capture['sha256'])
        c.require(path.stat().st_size == capture['bytes'] and capture['expected_packets'] > 0,
                  'ONBOARDING_RAW_IDENTITY')
    return dict(status='PREREQUISITES_VERIFIED_NO_EXPERIMENT_STARTED',
                head_run=str(head), head_seal_sha256=c.sha(head/'SHA256SUMS'),
                parent=str(parent), checkpoint_sha256=runtime['checkpoint_sha256'],
                tshark=tshark, tshark_sha256=c.sha(tshark), tshark_version=version,
                resource_plan_sha256=c.sha(root/'resource_plan.json'))


def make_encoder_runtime(root, run, runtime):
    """Copy pinned vendor code and one pinned checkpoint into our own tree."""
    destination = run/'encoder_runtime'
    c.require(not destination.exists(), 'ENCODER_RUNTIME_EXISTS')
    c.pin(runtime['paths']['checkpoint'], runtime['checkpoint_sha256'])
    shutil.copytree(root/'vendor', destination/'vendor')
    model = destination/'vendor/netFound-base/model.safetensors'
    c.require(not model.exists(), 'UNEXPECTED_PACKAGED_WEIGHTS')
    shutil.copyfile(runtime['paths']['checkpoint'], model)
    c.pin(model, runtime['checkpoint_sha256']); c.seal(destination); c.verify(destination)
    c.write(run/'encoder_runtime_identity.json', dict(manifest_sha256=c.sha(destination/'SHA256SUMS'),
            checkpoint_sha256=runtime['checkpoint_sha256'], model_bytes=model.stat().st_size,
            source_vendor_seal=c.sha(root/'SHA256SUMS'), copied_not_symlinked=True))


def stage(root, name):
    root = Path(root).resolve(); runtime, plan = load_contract(root, require_allocation=True)
    c.require(name in STAGES, 'ONBOARDING_UNKNOWN_STAGE')
    run = check_run_scope(root, runtime); launch = c.read(run/'launch.json')
    c.require(launch['package_seal_sha256'] == c.sha(root/'SHA256SUMS') and
              launch['resource_plan_sha256'] == c.sha(root/'resource_plan.json'), 'ONBOARDING_STAGE_IDENTITY')
    c.require(launch['stages'] == list(STAGES) and launch['arm'] == 'QUERY_TAIL', 'ONBOARDING_STAGE_SCOPE')
    stage_launch = c.read(run/'stage_launch.json')
    c.require(stage_launch['stage'] == name and stage_launch['resource_plan_sha256'] == c.sha(root/'resource_plan.json'),
              'ONBOARDING_STAGE_LAUNCH')
    remaining = stage_launch['remaining_disk_gib']
    c.require(type(remaining) in (int, float) and math.isfinite(remaining) and 0 < remaining <= plan['disk_gib'],
              'ONBOARDING_STAGE_DISK_BUDGET')
    import constrained_onboarding_reference_v2 as reference
    if name.startswith('raw-'):
        pool = name[4:]; config = dict(runtime['captures'][pool])
        config.update(tshark=c.read(run/'preflight.json')['tshark'], state_storage=plan['state_storage'],
                      limits=dict(wall_seconds=plan['wall_seconds'], memory_gib=plan['guard_gib'],
                                  disk_gib=remaining),
                      protected_paths=list(runtime['paths'].values()))
        reference.prepare_raw_capture(config, run/'raw'/pool)
    elif name.startswith('encode-'):
        _, pool, policy = name.split('-')
        prepared = run/'raw'/pool/'prepared'/policy
        encoder = run/'encoder_runtime'
        config = dict(prepared_receipt_sha256=c.sha(prepared/'receipt.json'),
            runtime_root=str(encoder), runtime_manifest_sha256=c.read(run/'encoder_runtime_identity.json')['manifest_sha256'],
            normalizer=str(Path(runtime['paths']['parent'])/'normalizers/RECENT.npz'),
            normalizer_sha256=runtime['normalizer_sha256'], protected_paths=list(runtime['paths'].values()))
        reference.encode_selected(prepared, run/'encoded'/pool/policy, config)
    else:
        import constrained_onboarding_query_tail_adapter_v2 as adapter
        import constrained_onboarding_runner_v2 as runner
        bundle = adapter.prepare_query_tail(runtime['paths']['parent'], runtime['paths']['head_run'],
                                           root/'query_tail_design.json', arm=runtime['arm'])
        runner.attach_reference_banks(bundle, run/'banks_manifest.json')
        c.require(all(set(bundle['targets'][p]['banks']) == {'OLD_BANK', *POLICIES} for p in POOLS),
                  'ONBOARDING_INCOMPLETE_BANK_MATRIX')
        bundle['provenance'].setdefault('protected_paths', []).extend([str(root/'protocol.json'), str(run/'banks_manifest.json')])
        result = runner.run_development(bundle, run/'evaluation', root/'protocol.json')
        # The adapter covers two development pools only; absent third-pool evidence
        # must never be promoted by a wrapper into complete-system PASS.
        c.require(result['status'] == 'COMPLETE' and result['optimizer_updates'] == 0 and
                  not result['automatic_model_selection'], 'ONBOARDING_RESULT_SCOPE')
        c.require(all(value['status'] != 'PASS' for value in result['scientific_decisions'].values()),
                  'ONBOARDING_MISSING_REGRESSION_CANNOT_PASS')


def make_banks_manifest(run):
    pools = {}
    for pool in POOLS:
        pools[pool] = {}
        for policy in POLICIES:
            folder = run/'encoded'/pool/policy
            receipt = c.read(folder/'receipt.json')
            c.require(receipt['status'] == 'COMPLETE' and not receipt['synthetic_only'] and
                      receipt['policy'] == policy, 'ONBOARDING_ENCODE_INCOMPLETE')
            pools[pool][policy] = dict(path=folder.relative_to(run).as_posix(),
                                      receipt_sha256=c.sha(folder/'receipt.json'), wrong_reference_controls=[])
    c.write(run/'banks_manifest.json', dict(pools=pools))
    c.write(run/'bank_controls_status.json', dict(
            controls_status='NOT_AVAILABLE_NO_PREDECLARED_METADATA_DONOR_PLAN', selection_used_target_scores=False))


def terminate_group(process):
    if os.name == 'posix':
        try: os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError: pass
    elif process.poll() is None:
        process.kill()
    process.wait(timeout=30)


def launch_stage(root, run, name, runtime, plan, started):
    """Monitor child RSS/time, and disk without scanning another process's scratch."""
    before = disk_bytes(run)
    remaining = plan['disk_gib']-before/1024**3
    c.require(remaining > 0, 'ONBOARDING_WORKING_DISK_LIMIT')
    c.write(run/'stage_launch.json', dict(stage=name, remaining_disk_gib=remaining,
            resource_plan_sha256=c.sha(root/'resource_plan.json')), replace=True)
    log = run/'logs'/(name+'.log'); monitor = run/'monitor'/name
    monitor.mkdir(parents=True, exist_ok=False); recorder = StageRecorder(monitor)
    child = None; peak = 0; last_write = 0.; last_disk = 0.; observed_disk = before
    active_raw = run/'raw'/name[4:] if name.startswith('raw-') else None
    begin = time.monotonic()
    try:
        with log.open('x', encoding='utf-8') as stream:
            child = subprocess.Popen([sys.executable, '-B', str(Path(__file__).resolve()), 'stage',
                '--root', str(root), '--name', name, '--authorize-chain'], stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=os.name == 'posix')
            while True:
                now = time.monotonic(); rss = tree_rss(); peak = max(peak, rss)
                c.require(now-started < plan['wall_seconds'], 'ONBOARDING_WALL_TIME_LIMIT')
                c.require(rss < plan['guard_gib']*1024**3, 'ONBOARDING_COMBINED_MEMORY_LIMIT')
                c.require(not (run/'STOP_REQUESTED').exists(), 'ONBOARDING_STOP_REQUESTED')
                if now-last_disk > 10:
                    if active_raw is None or child.poll() is not None:
                        observed_disk = disk_bytes(run)
                    else:
                        # Active raw owns a stricter remaining-budget disk guard.
                        # Other run subtrees are stable/atomic and contain no child scratch.
                        observed_disk = sum(disk_bytes(p) if p.is_dir() else p.stat().st_size
                            for p in run.iterdir() if p.name != 'raw')
                        rawroot = run/'raw'
                        if rawroot.exists():
                            observed_disk += sum(disk_bytes(p) for p in rawroot.iterdir() if p != active_raw)
                    c.require(observed_disk < plan['disk_gib']*1024**3, 'ONBOARDING_WORKING_DISK_LIMIT')
                    c.require(shutil.disk_usage(run).free > 1024**3, 'ONBOARDING_DISK_FREE_LIMIT')
                    last_disk = now
                recorder.observe(name, rss)
                if now-last_write >= 5:
                    c.write(monitor/'status.json', dict(status='RUNNING', stage=name, child_pid=child.pid,
                        elapsed_seconds=now-begin, rss_gib=rss/1024**3, sampled_peak_tree_rss_gib=peak/1024**3,
                        observed_stable_disk_bytes=observed_disk, active_raw_scratch_guard='CHILD_OWNED' if active_raw else None,
                        resource_measure=RSS_SCOPE, optimizer_updates=0,retries=0), replace=True)
                    last_write = now
                if child.poll() is not None:
                    break
                time.sleep(.5)
            c.require(child.returncode == 0, 'ONBOARDING_STAGE_FAILED:'+name)
            c.require(disk_bytes(run) < plan['disk_gib']*1024**3, 'ONBOARDING_FINAL_DISK_LIMIT')
        recorder.observe(name, peak, force=True)
        c.write(monitor/'status.json', dict(status='COMPLETE',stage=name,exit_code=0,
                elapsed_seconds=time.monotonic()-begin,sampled_peak_tree_rss_gib=peak/1024**3,retries=0),replace=True)
    except BaseException as exc:
        if child is not None: terminate_group(child)
        c.write(monitor/'status.json', dict(status='STOPPED_NO_RETRY',stage=name,error=repr(exc),
                exit_code=child.returncode if child else None,retries=0),replace=True)
        raise


def run(root, explicit):
    c.require(explicit, 'ONBOARDING_CHAIN_NOT_AUTHORIZED')
    root = Path(root).resolve(); runtime, plan = load_contract(root, require_allocation=True)
    target = check_run_scope(root, runtime); c.require(not target.exists(), 'ONBOARDING_RUN_EXISTS_NO_RETRY')
    prereqs = preflight(root)
    target.mkdir(parents=True, exist_ok=False)
    (target/'logs').mkdir(); (target/'raw').mkdir(); (target/'encoded').mkdir()
    for pool in POOLS: (target/'encoded'/pool).mkdir()
    started = time.monotonic(); current = 'PREFLIGHT'
    def stop_signal(signum, frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    handlers = {sig:signal.signal(sig, stop_signal) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        c.write(target/'preflight.json', prereqs)
        c.write(target/'launch.json', dict(stages=list(STAGES),arm=runtime['arm'],
                resource_plan_sha256=c.sha(root/'resource_plan.json'), package_seal_sha256=c.sha(root/'SHA256SUMS'),
                head_run=runtime['paths']['head_run'], optimizer_updates=0,retries=0))
        import constrained_onboarding_reference_v2 as reference
        c.write(target/'environment.json', reference._environment())
        make_encoder_runtime(root, target, runtime)
        for name in STAGES:
            current = name
            if name == 'evaluate': make_banks_manifest(target)
            c.write(target/'status.json', dict(status='RUNNING',stage=name,retries=0),replace=True)
            launch_stage(root,target,name,runtime,plan,started)
        result = c.read(target/'evaluation/result.json')
        c.write(target/'COMPLETE.json', dict(status='COMPLETE',scope='TWO_POOL_PAIRED_ONBOARDING_DEVELOPMENT',
                scientific_decisions=result['scientific_decisions'], evaluation_result_sha256=c.sha(target/'evaluation/result.json'),
                required_three_device_regression='NOT_RUN',independent_confirmation='NOT_RUN',optimizer_updates=0,retries=0))
        c.write(target/'status.json', dict(status='COMPLETE',stage='COMPLETE',elapsed_seconds=time.monotonic()-started,
                                         optimizer_updates=0,retries=0),replace=True)
    except BaseException as exc:
        c.write(target/'status.json', dict(status='STOPPED_NO_RETRY',stage=current,error=repr(exc),retries=0),replace=True)
        raise
    finally:
        for sig, handler in handlers.items(): signal.signal(sig,handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('preflight','run','stage'));parser.add_argument('--root',required=True)
    parser.add_argument('--authorize-chain',action='store_true');parser.add_argument('--name',choices=STAGES)
    args = parser.parse_args()
    if args.mode == 'preflight': print(preflight(args.root))
    elif args.mode == 'run': run(args.root,args.authorize_chain)
    else:
        c.require(args.authorize_chain and args.name, 'ONBOARDING_STAGE_NOT_AUTHORIZED')
        stage(args.root,args.name)


if __name__ == '__main__':
    main()
