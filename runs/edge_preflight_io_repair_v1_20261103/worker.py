"""Run the byte-pinned original probe worker with bounded local scratch I/O."""
import argparse
from contextlib import contextmanager
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import sys
import time
import traceback
from types import SimpleNamespace
import uuid

HERE = Path(__file__).resolve().parent
LOCAL_FILESYSTEMS = {'ext2', 'ext3', 'ext4', 'xfs', 'btrfs', 'tmpfs', 'ramfs', 'zfs', 'overlay'}
SCRATCH_FREE_BYTES = 2 * 1024 ** 3


def write(path, body):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(body, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    temporary.replace(path)


def mount_unescape(value):
    for encoded, plain in (('\\040', ' '), ('\\011', '\t'), ('\\012', '\n'), ('\\134', '\\')):
        value = value.replace(encoded, plain)
    return value


def filesystem_for(path, mountinfo=None):
    path = Path(path).resolve()
    content = Path('/proc/self/mountinfo').read_text() if mountinfo is None else mountinfo
    matches = []
    for line in content.splitlines():
        left, separator, right = line.partition(' - ')
        if not separator:
            continue
        fields, tail = left.split(), right.split()
        mount = Path(mount_unescape(fields[4]))
        if path == mount or path.is_relative_to(mount):
            matches.append((len(str(mount)), tail[0], str(mount)))
    if not matches:
        raise ValueError('SCRATCH_MOUNT_NOT_IDENTIFIED')
    _, filesystem, mount = max(matches)
    return filesystem, mount


def validate_scratch(candidate, persistent_roots, *, filesystem_probe=filesystem_for,
                     stat=os.stat, disk_usage=shutil.disk_usage):
    candidate = Path(candidate).resolve(strict=True)
    if not candidate.is_dir():
        raise ValueError('SCRATCH_NOT_DIRECTORY')
    filesystem, mount = filesystem_probe(candidate)
    if filesystem not in LOCAL_FILESYSTEMS:
        raise ValueError('SCRATCH_NOT_VERIFIED_LOCAL_FILESYSTEM:' + filesystem)
    device = stat(candidate).st_dev
    if device in {stat(Path(p).resolve(strict=True)).st_dev for p in persistent_roots}:
        raise ValueError('SCRATCH_SHARES_PERSISTENT_DEVICE')
    free = disk_usage(candidate).free
    if free < SCRATCH_FREE_BYTES:
        raise ValueError('SCRATCH_FREE_SPACE_LESS_THAN_2_GIB')
    return dict(path=str(candidate), filesystem=filesystem, mount=mount,
                device=device, free_bytes=free, required_free_bytes=SCRATCH_FREE_BYTES)


class OwnedScratch:
    def __init__(self, parent, facts):
        self.parent = Path(parent).resolve(strict=True)
        self.token = uuid.uuid4().hex
        self.path = self.parent / ('edge_preflight_' + self.token)
        self.path.mkdir(mode=0o700)
        self.marker = self.path / '.owned_edge_preflight'
        self.marker.write_text(self.token, encoding='ascii')
        self.facts = dict(facts, owned_path=str(self.path))

    def cleanup(self):
        # A marker and containment check are required even for our own path.
        if (self.path.is_symlink() or self.path.resolve().parent != self.parent
                or self.path.name != 'edge_preflight_' + self.token
                or not self.marker.is_file() or self.marker.is_symlink()
                or self.marker.read_text(encoding='ascii') != self.token):
            raise ValueError('REFUSE_UNOWNED_SCRATCH_CLEANUP')
        shutil.rmtree(self.path)


def create_scratch(persistent_roots):
    attempted = []
    candidates = list(dict.fromkeys(x for x in (os.environ.get('SLURM_TMPDIR'),
                    os.environ.get('TMPDIR'), '/tmp') if x))
    for candidate in candidates:
        try:
            facts = validate_scratch(candidate, persistent_roots)
            return OwnedScratch(candidate, facts)
        except (OSError, ValueError) as error:
            attempted.append(dict(path=candidate, error=repr(error)))
    raise ValueError('NO_VERIFIED_NODE_LOCAL_SCRATCH:' + json.dumps(attempted))


class DeadlineExceeded(TimeoutError):
    pass


def check_deadline(deadline):
    if time.monotonic() >= deadline:
        raise DeadlineExceeded('COOPERATIVE_PREFLIGHT_DEADLINE_RECEIPT_RESERVED')


def progress_class(original, deadline, observed):
    class DeadlineProgress(original):
        def __init__(self, out, seconds=600):
            super().__init__(out, seconds=seconds)
            self.seconds = min(seconds, max(0., deadline - self.started))
            self._next_memory_guard = 0.
            observed['progress'] = self

        def guard(self):
            check_deadline(deadline)
            # Replay invokes this on every raw frame. Process-tree scans must
            # not themselves become the new per-frame bottleneck.
            now = time.monotonic()
            if now >= self._next_memory_guard:
                super().guard()
                self._next_memory_guard = now + 1.

    return DeadlineProgress


class LoaderProxy:
    def __init__(self, loader, deadline, observed):
        self.loader, self.deadline, self.observed = loader, deadline, observed

    def create_module(self, spec):
        method = getattr(self.loader, 'create_module', None)
        return method(spec) if method else None

    def exec_module(self, module):
        self.loader.exec_module(module)
        module.Progress = progress_class(module.Progress, self.deadline, self.observed)

    def __getattr__(self, name):
        return getattr(self.loader, name)


class UtilProxy:
    def __init__(self, original, deadline, observed):
        self.original, self.deadline, self.observed = original, deadline, observed

    def spec_from_file_location(self, name, path, *args, **kwargs):
        spec = self.original.spec_from_file_location(name, path, *args, **kwargs)
        if name == '_edge_original_preflight_runner':
            spec.loader = LoaderProxy(spec.loader, self.deadline, self.observed)
        return spec

    def __getattr__(self, name):
        return getattr(self.original, name)


@contextmanager
def inject_progress(probe_module, deadline, observed):
    original = probe_module.importlib
    # Only this module sees the proxy. The shared importlib.util remains intact.
    probe_module.importlib = SimpleNamespace(util=UtilProxy(original.util, deadline, observed))
    try:
        yield
    finally:
        probe_module.importlib = original


@contextmanager
def alarm_deadline(deadline):
    if not hasattr(signal, 'setitimer'):
        yield
        return
    previous = signal.getsignal(signal.SIGALRM)
    previous_timer = signal.getitimer(signal.ITIMER_REAL)
    def expired(signum, frame):
        raise DeadlineExceeded('COOPERATIVE_PREFLIGHT_DEADLINE_RECEIPT_RESERVED')
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, max(.001, deadline - time.monotonic()))
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)
        if previous_timer[0] > 0:
            signal.setitimer(signal.ITIMER_REAL, *previous_timer)


def load_probe(root):
    path = root / 'runs/edge_query_selection_v1_20261103/run_preflight_with_probes.py'
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('_edge_frozen_strict_probe_worker', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_heartbeat(out, deadline, started, observed, guard):
    def heartbeat(stage, **extra):
        guard()
        progress = observed.get('progress')
        if progress is not None:
            # The frozen save() owns status/stage/elapsed/stages keys.
            progress.save(stage, replay=dict(extra))
        value = dict(extra)
        value.update(stage=stage, replay_elapsed_seconds=extra.get('elapsed_seconds'),
                     elapsed_seconds=time.monotonic() - started,
                     deadline_remaining_seconds=max(0., deadline-time.monotonic()))
        write(out / 'IO_HEARTBEAT.json', value)
    return heartbeat


def worker(args):
    out = Path(args.output).resolve()
    out.mkdir(parents=True, exist_ok=False)
    deadline = args.deadline_monotonic
    observed = {}
    scratch = None
    code = 1
    started = time.monotonic()
    try:
        check_deadline(deadline)
        root = Path(args.frozen_root).resolve(strict=True)
        scratch = create_scratch([root, out])
        write(out / 'SCRATCH_RECEIPT.json', scratch.facts)
        sys.path.insert(0, str(root / 'runs/edge_external_test1_engineering_v1_20261103/adapter'))
        edge_module = importlib.import_module('edge_adapter')
        probe = load_probe(root)
        from replay_io import install

        def guard():
            check_deadline(deadline)
            if 'progress' in observed:
                observed['progress'].guard()

        heartbeat = make_heartbeat(out, deadline, started, observed, guard)

        with inject_progress(probe, deadline, observed), alarm_deadline(deadline):
            with install(edge_module, output=out, cache_root=Path(args.cache_root),
                         scratch_root=scratch.path, deadline=deadline, guard=guard, heartbeat=heartbeat):
                code = probe.run_worker(args)
    except BaseException as error:
        write(out / 'RESULT.json', dict(status='STOPPED_NO_RETRY', error=repr(error),
            traceback=traceback.format_exc(), final_linux_runtime_gate_pass=False,
            scope='ENGINEERING_ONLY_NOT_EXTERNAL_EVALUATION', external_quality_metrics=False,
            training=False, automatic_retry=False))
    finally:
        cleanup = dict(status='NOT_CREATED')
        if scratch is not None:
            try:
                scratch.cleanup()
                cleanup = dict(status='OWNED_SCRATCH_REMOVED', owned_path=str(scratch.path))
            except BaseException as error:
                cleanup = dict(status='CLEANUP_REFUSED_OR_FAILED', error=repr(error))
                code = 1
        write(out / 'SCRATCH_CLEANUP.json', cleanup)
        if not (out / 'STRICT_SHAPE_PROBE_SUMMARY.json').is_file():
            write(out / 'STRICT_SHAPE_PROBE_SUMMARY.json', dict(status='NOT_STARTED',
                    strict_byte_identity_unchanged=True, external_quality_used=False))
        result_path = out / 'RESULT.json'
        actual = json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else dict(
                status='STOPPED_NO_RETRY', error='ORIGINAL_PROBE_WORKER_NO_RECEIPT')
        summary = json.loads((out / 'STRICT_SHAPE_PROBE_SUMMARY.json').read_text(encoding='utf-8'))
        from launch_preflight import acceptance
        if not acceptance(code, dict(actual, strict_shape_probes=summary)):
            code = 1
            actual.update(status='STOPPED_NO_RETRY', final_linux_runtime_gate_pass=False)
        actual.update(io_repair_schema='EDGE_NODE_LOCAL_REPLAY_IO_V1',
                      strict_shape_probes=summary, scratch_cleanup=cleanup,
                      hard_deadline_monotonic=args.hard_deadline_monotonic,
                      cooperative_deadline_monotonic=deadline)
        write(result_path, actual)
        write(out / 'STATUS.json', actual)
        for name in ('RESULT.json', 'STATUS.json', 'STRICT_SHAPE_PROBE_SUMMARY.json'):
            path = out / name
            path.with_name(path.name+'.sha256').write_text(hashlib.sha256(path.read_bytes()).hexdigest()
                        + '  ' + path.name + '\n', encoding='utf-8')
    return code


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--slice', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--strict-runtime', action='store_true')
    parser.add_argument('--tshark')
    parser.add_argument('--raw-directory')
    parser.add_argument('--frozen-root', required=True)
    parser.add_argument('--cache-root', required=True)
    parser.add_argument('--deadline-monotonic', type=float, required=True)
    parser.add_argument('--hard-deadline-monotonic', type=float, required=True)
    args = parser.parse_args(argv)
    if args.hard_deadline_monotonic - args.deadline_monotonic < 14.9:
        parser.error('at least 15 seconds must be reserved for STOP receipts')
    return worker(args)


if __name__ == '__main__':
    raise SystemExit(main())
