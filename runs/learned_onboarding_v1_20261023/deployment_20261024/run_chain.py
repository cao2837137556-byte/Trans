"""Execute the frozen stages once, serially, under an outer process-tree guard.

No scheduler, polling of other jobs, retries, training resume or source changes.
The service manager must independently impose its existing 16 GiB hard limit.
"""
import argparse
from datetime import datetime, timezone
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

import psutil


PACKAGE = 'runs/learned_onboarding_v1_20261023'
SPEC = 'runs/learned_onboarding_pilot_v1_20261023/EXECUTION_SPEC_V1.md'
SPEC_SHA = 'a07d736c7c9c756478a7d163873611132ff0b14abc855ab3a3709257433674b8'
RSS_LIMIT = 8 * 1024 ** 3
OUTPUT_LIMIT = 2 * 1024 ** 3
STAGING_LIMIT = 2 * 1024 ** 3
CHAIN_LIMIT = 24 * 3600


class Stop(RuntimeError):
    pass


def require(condition, reason):
    if not condition:
        raise Stop(reason)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp-' + str(os.getpid()))
    with temporary.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def output_bytes(roots):
    return sum(path.stat().st_size for root in roots if root.exists()
               for path in root.rglob('*') if path.is_file())


def tree_rss():
    parent = psutil.Process()
    total = 0
    for process in [parent] + parent.children(recursive=True):
        try:
            total += process.memory_info().rss
        except psutil.NoSuchProcess:
            pass
    return total


def terminate_tree(process):
    """Stop this child and descendants; preserve every existing output."""
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
        for child in reversed(children):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        parent.terminate()
        _, alive = psutil.wait_procs(children + [parent], timeout=5)
        for item in alive:
            try:
                item.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=5)
    except psutil.NoSuchProcess:
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def package_identity(root, config, deployment_manifest):
    """Hash source, test and dependency closure before any real-data stage."""
    package = root / PACKAGE
    manifest = read(package / 'implementation_manifest.json')
    require(manifest['spec_sha256'] == SPEC_SHA and sha(root / SPEC) == SPEC_SHA,
            'FROZEN_SPEC_IDENTITY')
    deployment = read(deployment_manifest)
    require(deployment['spec_sha256'] == SPEC_SHA, 'DEPLOYMENT_MANIFEST_SPEC')
    require(deployment['engineering_manifest_sha256'] == sha(package / 'implementation_manifest.json'),
            'DEPLOYMENT_ENGINEERING_MANIFEST_IDENTITY')
    require(isinstance(deployment.get('files'), dict) and deployment['files'],
            'DEPLOYMENT_MANIFEST_FILES')
    for name, item in deployment['files'].items():
        path = (root / name).resolve()
        require(root in path.parents, 'DEPLOYMENT_MANIFEST_PATH_ESCAPE')
        expected = item['sha256'] if isinstance(item, dict) else item
        require(sha(path) == expected, 'DEPLOYMENT_MANIFEST_SHA:' + name)
        if isinstance(item, dict) and 'bytes' in item:
            require(path.stat().st_size == item['bytes'], 'DEPLOYMENT_MANIFEST_SIZE:' + name)
    for name, item in manifest['artifacts'].items():
        if name.startswith(('src/', 'tests/')):
            require(sha(package / name) == item['sha256'], 'IMPLEMENTATION_ARTIFACT_CHANGED:' + name)
    paths = set((package / 'src').glob('*.py'))
    paths.update((package / 'tests').rglob('*.py'))
    paths.update((root / 'repo/ood').rglob('*.py'))
    paths.update((package / 'deployment_20261024').glob('*.py'))
    paths.update((root / SPEC, package / 'implementation_manifest.json'))
    require(paths and (root / 'repo/ood').is_dir(), 'PACKAGE_INCOMPLETE')
    return dict(schema='learned-onboarding-deployment-package-v1', spec_sha256=SPEC_SHA,
                config_path=str(config), config_sha256=sha(config),
                deployment_manifest=str(deployment_manifest),
                deployment_manifest_sha256=sha(deployment_manifest),
                files={str(p.relative_to(root)).replace('\\', '/'): sha(p) for p in sorted(paths)})


class Runner:
    def __init__(self, args):
        self.args = args
        self.root = args.root.resolve()
        self.package = self.root / PACKAGE
        self.state = args.state.resolve()
        self.deployment_manifest = (args.deployment_manifest or self.root / 'DEPLOYMENT_MANIFEST.json').resolve()
        self.results = self.package / 'results'
        self.target_staging = self.root / 'inputs/target_bundle'
        self.source_archive = self.root / 'inputs/source_head_archive'
        self.started = time.monotonic()
        self.completed = []
        self.peak_rss = 0
        self.active = None
        self.child = None
        self.identity = None
        self.owns_state = False
        self.expected_runtime = None
        self.last_write = -float('inf')

    def disk_report(self):
        results = output_bytes([self.results])
        target = output_bytes([self.target_staging])
        archive = output_bytes([self.source_archive])
        state = output_bytes([self.state])
        remaining = max(0, OUTPUT_LIMIT - results) + max(0, STAGING_LIMIT - target)
        return dict(output_bytes=results, target_input_staging_bytes=target,
                    source_archive_staging_bytes=archive, state_and_log_bytes=state,
                    combined_new_artifacts_bytes=results + target + archive + state,
                    output_limit_bytes=OUTPUT_LIMIT, input_staging_limit_bytes=STAGING_LIMIT,
                    remaining_write_upper_bound_bytes=remaining,
                    disk_free_bytes=shutil.disk_usage(self.root).free,
                    minimum_disk_free_bytes=2 * remaining)

    def status(self, status, force=False, **extra):
        current = time.monotonic()
        if not force and current - self.last_write < 5:
            return
        self.last_write = current
        write(self.state / 'status.json', dict(
            schema='learned-onboarding-deployment-progress-v1', status=status,
            stage=self.active, updated_at=now(), elapsed_seconds=current - self.started,
            completed_stages=self.completed, peak_process_tree_rss=self.peak_rss,
            rss_guard_bytes=RSS_LIMIT, chain_administrative_limit_seconds=CHAIN_LIMIT,
            automatic_retry=False, **self.disk_report(), **extra))

    def guard(self, stage_start):
        rss = tree_rss()
        self.peak_rss = max(self.peak_rss, rss)
        require(rss <= RSS_LIMIT, 'OUTER_RESOURCE_RSS_LIMIT')
        disk = self.disk_report()
        require(disk['output_bytes'] <= OUTPUT_LIMIT, 'OUTER_RESOURCE_OUTPUT_LIMIT')
        require(disk['target_input_staging_bytes'] <= STAGING_LIMIT, 'TARGET_INPUT_STAGING_LIMIT')
        require(disk['disk_free_bytes'] >= disk['minimum_disk_free_bytes'], 'INSUFFICIENT_DISK_HEADROOM')
        require(time.monotonic() - self.started <= CHAIN_LIMIT, 'CHAIN_ADMINISTRATIVE_TIME_LIMIT')
        if self.active == 'fit':
            require(time.monotonic() - stage_start <= 10 * 3600, 'OUTER_FIT_TIME_LIMIT')

    def verify_identity(self):
        require(package_identity(self.root, self.args.config.resolve(), self.deployment_manifest) == self.identity,
                'DEPLOYMENT_PACKAGE_CHANGED')

    def stage(self, name, target_manifest=None, target_sha=None):
        self.verify_identity()
        self.active = name
        stage_dir = self.state / 'stages' / name
        require(not stage_dir.exists(), 'STAGE_ALREADY_ATTEMPTED:' + name)
        stage_dir.mkdir(parents=True)
        if name not in ('tests', 'target'):
            require(not (self.results / name).exists(), 'OUTPUT_ALREADY_EXISTS:' + name)
        if name == 'target':
            require(not (self.root / 'inputs/target_bundle').exists(), 'TARGET_BUNDLE_ALREADY_EXISTS')
        command = [sys.executable, '-u', str(self.package / 'deployment_20261024/run_stage.py'),
                   '--root', str(self.root), '--config', str(self.args.config.resolve()),
                   '--state', str(self.state), '--source-assets', str(self.args.source_assets.resolve()),
                   '--stage', name]
        if self.expected_runtime is not None:
            command += ['--expected-runtime-file', str(self.expected_runtime)]
        if target_manifest is not None:
            command += ['--target-manifest', str(target_manifest), '--target-manifest-sha256', target_sha]
        started = time.monotonic()
        self.guard(started)
        self.status('RUNNING', force=True, stage_elapsed_seconds=0)
        write(stage_dir / 'invocation.json', dict(
            schema='learned-onboarding-deployment-invocation-v1', command=command,
            started_at=now(), package_manifest_sha256=sha(self.state / 'package_manifest.json'),
            automatic_retry=False))
        environment = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONDONTWRITEBYTECODE='1')
        with (stage_dir / 'output.log').open('xb') as log:
            self.child = subprocess.Popen(command, cwd=str(self.root), env=environment,
                                          stdout=log, stderr=subprocess.STDOUT)
            try:
                while True:
                    self.guard(started)
                    self.status('RUNNING', stage_elapsed_seconds=time.monotonic() - started)
                    try:
                        returncode = self.child.wait(timeout=1)
                        break
                    except subprocess.TimeoutExpired:
                        pass
            except BaseException:
                terminate_tree(self.child)
                raise
            finally:
                if self.child.poll() is not None:
                    write(stage_dir / 'process_exit.json', dict(
                        schema='learned-onboarding-deployment-process-exit-v1',
                        returncode=self.child.returncode, elapsed_seconds=time.monotonic() - started,
                        peak_chain_process_tree_rss=self.peak_rss, ended_at=now()))
        self.child = None
        require(returncode == 0, 'STAGE_NONZERO_EXIT:' + name + ':' + str(returncode))
        self.guard(started)
        self.verify_identity()
        runtime_path = stage_dir / 'runtime.json'
        require(runtime_path.is_file(), 'STAGE_RUNTIME_MISSING:' + name)
        if self.expected_runtime is None:
            self.expected_runtime = runtime_path
        else:
            require(read(runtime_path)['runtime'] == read(self.expected_runtime)['runtime'],
                    'STAGE_RUNTIME_CHANGED:' + name)
        if name == 'preflight':
            plan = read(self.results / 'preflight/resource_plan.json')
            require(plan['status'] == 'READY' and plan['synthetic_timing_complete'], 'PREFLIGHT_NOT_READY')
            require(plan['runtime'] == read(self.expected_runtime)['runtime'], 'PREFLIGHT_RUNTIME_CHANGED')
        self.completed.append(name)
        self.status('RUNNING', force=True, stage_elapsed_seconds=time.monotonic() - started)

    def execute(self):
        require(not self.state.exists(), 'STATE_ALREADY_EXISTS_NO_AUTOMATIC_RESUME')
        require(self.args.source_assets.resolve() == self.results / 'source_assets',
                'SOURCE_ASSET_PATH_MUST_BE_RESULTS_SOURCE_ASSETS')
        require(not self.results.exists() or not any(self.results.iterdir()),
                'RESULTS_NOT_EMPTY_NO_AUTOMATIC_RESUME')
        self.state.mkdir(parents=True)
        self.owns_state = True
        self.identity = package_identity(self.root, self.args.config.resolve(), self.deployment_manifest)
        write(self.state / 'package_manifest.json', self.identity)
        write(self.state / 'execution_contract.json', dict(
            schema='learned-onboarding-deployment-contract-v1', started_at=now(),
            source_assets=str(self.args.source_assets.resolve()), execution_slot='exclusive-existing-remote',
            cpu_threads=4, heavy_workers=1, rss_guard_bytes=RSS_LIMIT,
            environment_memory_ceiling_bytes=16 * 1024 ** 3,
            hard_limit_provider='External service manager; this runner does not assert or install the hard limit',
            output_limit_bytes=OUTPUT_LIMIT, counted_outputs=[str(self.results)],
            input_staging_limit_bytes=STAGING_LIMIT, target_input_staging=str(self.target_staging),
            source_archive_staging=str(self.source_archive),
            staging_scope='Transport/format conversion of frozen inputs; no frontend extraction or fitting',
            separate_input_staging_budget_does_not_change_results_limit=True,
            initial_disk_report=self.disk_report(),
            fit_limit_seconds=10 * 3600, auxiliary_limit_seconds_each=4 * 3600,
            module_limit_seconds_combined=2 * 3600,
            chain_administrative_limit_seconds=CHAIN_LIMIT,
            administrative_limit_is_not_training_eta=True, automatic_retry=False))
        for name in ('tests', 'prepare', 'validate', 'preflight', 'fit', 'calibration'):
            self.stage(name)
        if self.args.through_calibration:
            self.active = None
            self.status('SOURCE_COMPLETE', force=True)
            write(self.state / 'SOURCE_CHAIN_COMPLETE.json', dict(
                status='SOURCE_COMPLETE', completed_stages=self.completed, completed_at=now(),
                training_success_does_not_assert_scientific_success=True, automatic_retry=False))
            return 0
        adapter = self.package / 'deployment_20261024/target_manifest_adapter.py'
        if not adapter.is_file():
            self.active = None
            self.status('WAITING_TARGET_ADAPTER', force=True)
            write(self.state / 'WAITING_TARGET_ADAPTER.json', dict(
                status='WAITING_TARGET_ADAPTER', completed_stages=self.completed,
                updated_at=now(), automatic_retry=False, source_retraining_required=False))
            return 0
        self.stage('target')
        target = self.root / 'inputs/target_bundle/target_manifest.json'
        require(target.is_file(), 'TARGET_MANIFEST_MISSING')
        target_sha = sha(target)
        self.stage('evaluation', target, target_sha)
        self.active = None
        self.status('COMPLETE', force=True)
        write(self.state / 'CHAIN_COMPLETE.json', dict(
            schema='learned-onboarding-deployment-complete-v1', status='COMPLETE',
            completed_stages=self.completed, ended_at=now(),
            target_manifest=str(target), target_manifest_sha256=target_sha,
            scientific_decision=str(self.results / 'evaluation/decision.json'), automatic_retry=False))
        return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--source-assets', type=Path, required=True)
    parser.add_argument('--deployment-manifest', type=Path,
                        help='Defaults to ROOT/DEPLOYMENT_MANIFEST.json; verified before every stage')
    parser.add_argument('--through-calibration', action='store_true')
    args = parser.parse_args(argv)
    runner = Runner(args)
    def interrupted(signum, frame):
        raise Stop('EXTERNAL_SIGNAL:' + str(signum))
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        return runner.execute()
    except BaseException as error:
        if runner.child is not None:
            terminate_tree(runner.child)
        # Refusing an existing state must not overwrite that previous attempt.
        if runner.owns_state:
            runner.status('EXCEPTION_STOP', force=True, error=str(error))
            write(runner.state / 'EXCEPTION_STOP.json', dict(
                schema='learned-onboarding-deployment-exception-v1', status='EXCEPTION_STOP',
                stage=runner.active, error_type=type(error).__name__, error=str(error),
                traceback=traceback.format_exc(), completed_stages=runner.completed,
                stopped_at=now(), automatic_retry=False, existing_artifacts_retained=True))
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
