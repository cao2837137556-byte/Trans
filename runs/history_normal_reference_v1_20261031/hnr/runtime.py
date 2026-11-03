"""One-shot execution guards and durable progress; importing this runs no science."""
from datetime import datetime, timezone
import os
from pathlib import Path
import signal
import threading
import time
import traceback

import psutil

from .common import PACKAGE, ROOT, VERSION, PAIR_LIMIT, read, require, sha, write

LIMITS = dict(cpu=4, rss_bytes=16 * 2**30, output_bytes=20 * 2**30,
              wall_seconds=8 * 3600, pairs=PAIR_LIMIT, encoded=36864)


def utc():
    return datetime.now(timezone.utc).isoformat()


def code_identity():
    paths = [PACKAGE / 'run.py', PACKAGE / 'progress.py', PACKAGE / 'progress.html',
             *PACKAGE.glob('hpc/*.slurm'), *PACKAGE.glob('hnr/*.py'), *PACKAGE.glob('config/*.json')]
    result = {p.relative_to(PACKAGE).as_posix(): sha(p) for p in sorted(paths) if p.is_file()}
    external_roots = [ROOT / 'repo/ood',
                      ROOT / 'runs/dense_reference_matrix_v1_20261027/vendor/encoding_v2/repo/ood',
                      ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/vendor/encoding_v2/repo/ood']
    external = [p for folder in external_roots for p in folder.rglob('*.py') if p.is_file()]
    external.extend(ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src' / name
                    for name in ('matrix.py', 'metrics.py'))
    for path in sorted(set(external)):
        if path.is_file():
            result['@root/' + path.relative_to(ROOT).as_posix()] = sha(path)
    # Seal the actual encoder Python tree as well, without importing it. A
    # missing runtime is reported by acceptance rather than guessed elsewhere.
    config = PACKAGE / 'config/EXECUTION.json'
    if config.is_file():
        runtime_value = read(config).get('encoder', {}).get('runtime_root')
        if isinstance(runtime_value, str) and runtime_value:
            runtime_root = (ROOT / runtime_value).resolve()
            for path in sorted(runtime_root.rglob('*.py')):
                if path.is_file() and '__pycache__' not in path.parts:
                    key = ('@root/' + path.relative_to(ROOT).as_posix()
                           if path.is_relative_to(ROOT) else
                           '@encoder/' + path.relative_to(runtime_root).as_posix())
                    result[key] = sha(path)
    return result


class Runtime:
    """One experiment budget, with no resume/retry or terminal-output overwrite.

    ``update`` / ``tick`` mean worker progress. The watchdog only advances the
    service heartbeat: a live monitor cannot make a blocked worker look fresh.
    Counter charges must precede the work they authorize.
    """
    def __init__(self, output, *, mode='execute', synthetic=False, limits=None, monitor=True):
        require(mode in ('check', 'execute'), 'RUNTIME_MODE')
        require(limits is None or synthetic, 'REAL_LIMITS_ARE_FROZEN')
        self.output = Path(output).resolve()
        require(synthetic or self.output.is_relative_to(PACKAGE / 'outputs'),
                'OUTPUT_MUST_BE_NEW_PACKAGE_OUTPUT')
        self.mode, self.synthetic = mode, synthetic
        self.limits = dict(LIMITS if limits is None else limits)
        if mode == 'check':
            self.limits.update(pairs=0, encoded=0)
        self.monitor = monitor
        self._pairs = self._encoded = self.peak_rss = self.peak_output = 0
        self.state, self.children = {}, []
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread = None
        self._finished = False
        self._old_affinity = None
        self._last_flush = 0.
        self._watch_error = None
        self._old_handlers = {}

    def __enter__(self):
        # Never adopt a preexisting directory (including failed/terminal runs).
        self.output.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.identity = code_identity()
        write(self.output / 'OWNER.json', dict(version=VERSION, pid=os.getpid(),
              started_utc=utc(), mode=self.mode, synthetic=self.synthetic,
              automatic_retry=False, code_sha256=self.identity))
        try:
            proc = psutil.Process()
            require(hasattr(proc, 'cpu_affinity'), 'CPU_AFFINITY_UNAVAILABLE')
            self._old_affinity = proc.cpu_affinity()
            require(bool(self._old_affinity), 'CPU_AFFINITY_EMPTY')
            proc.cpu_affinity(self._old_affinity[:self.limits['cpu']])
            if threading.current_thread() is threading.main_thread():
                for signum in (signal.SIGTERM, signal.SIGINT):
                    self._old_handlers[signum] = signal.signal(signum, self._on_signal)
            self.state.update(technical_status='RUNNING', phase='STARTING', mode=self.mode,
                              started_utc=utc(), work_heartbeat_utc=utc(),
                              automatic_retry=False, synthetic=self.synthetic)
            self.checkpoint(force=True)
        except BaseException as exc:
            self._record_failure(type(exc), exc, exc.__traceback__)
            self._restore_affinity()
            raise
        if self.monitor:
            self._thread = threading.Thread(target=self._watch, daemon=True,
                                            name='history-resource-watchdog')
            self._thread.start()
        return self

    def _usage(self):
        process = psutil.Process()
        rss = 0
        for proc in [process, *process.children(recursive=True)]:
            try:
                rss += proc.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        size = 0
        for path in self.output.rglob('*'):
            try:
                if path.is_file():
                    size += path.stat().st_size
            except FileNotFoundError:
                pass
        self.peak_rss = max(self.peak_rss, rss)
        self.peak_output = max(self.peak_output, size)
        return dict(elapsed_seconds=time.monotonic() - self.started,
                    process_tree_rss_bytes=rss, output_bytes=size)

    def _validate(self, usage):
        for field, key in (('elapsed_seconds', 'wall_seconds'),
                           ('process_tree_rss_bytes', 'rss_bytes'),
                           ('output_bytes', 'output_bytes')):
            require(usage[field] <= self.limits[key], key.upper() + '_LIMIT')
        require(self._pairs <= self.limits['pairs'], 'PAIRS_LIMIT')
        require(self._encoded <= self.limits['encoded'], 'ENCODED_LIMIT')

    def checkpoint(self, *, force=False):
        """Check resource limits; this is not evidence of worker progress."""
        with self._lock:
            if self._watch_error is not None:
                raise self._watch_error
            require(not self._finished, 'RUNTIME_ALREADY_FINALIZED')
            require(time.monotonic() - self.started <= self.limits['wall_seconds'],
                    'WALL_SECONDS_LIMIT')
            now = time.monotonic()
            if not force and now - self._last_flush < .5:
                return
            usage = self._usage()
            self._validate(usage)
            self.state.update(usage, pairs=self._pairs, encoded_rows=self._encoded,
                              peak_process_tree_rss_bytes=self.peak_rss,
                              peak_output_bytes=self.peak_output,
                              limits=self.limits, service_heartbeat_utc=utc())
            write(self.output / 'STATUS.json', self.state)
            self._last_flush = now

    def guard(self):
        return self.checkpoint()

    def update(self, stage=None, **fields):
        with self._lock:
            require(not self._finished, 'RUNTIME_ALREADY_FINALIZED')
            # Callers cannot overwrite the monitor's terminal/resource fields.
            require(not any(k in fields for k in ('technical_status', 'limits', 'pairs',
                        'encoded_rows', 'work_heartbeat_utc', 'service_heartbeat_utc')),
                    'RESERVED_PROGRESS_FIELD')
            if stage is not None and str(stage) != self.state.get('phase'):
                for key in ('done','completed','total','raw_packets','decoder_pass',
                            'selected_snapshots','encoding_batches'):
                    self.state.pop(key, None)
            self.state.update(fields)
            if stage is not None:
                self.state['phase'] = str(stage)
            self.state['work_heartbeat_utc'] = utc()
            # Preserve detailed counters even when a fast loop is throttled.
            self.checkpoint()

    def tick(self, done=None, total=None, **fields):
        if done is not None:
            fields['done'] = int(done)
        if total is not None:
            fields['total'] = int(total)
        self.update(**fields)

    def _charge(self, field, limit, count):
        require(type(count) is int and count >= 0, 'NONNEGATIVE_INTEGER_COUNT')
        with self._lock:
            value = getattr(self, field) + count
            require(value <= self.limits[limit], limit.upper() + '_LIMIT')
            setattr(self, field, value)
            self.state['work_heartbeat_utc'] = utc()
            self.checkpoint()

    def count_pairs(self, count):
        self._charge('_pairs', 'pairs', count)

    def count_encoded(self, count):
        self._charge('_encoded', 'encoded', count)

    pairs = count_pairs
    encoded = count_encoded
    add_pairs = count_pairs

    def write_json(self, name, value):
        path = (self.output / name).resolve()
        require(path.is_relative_to(self.output), 'OUTPUT_PATH_ESCAPE')
        require(path.name not in ('OWNER.json', 'STATUS.json', 'STAGE_RECEIPT.json'),
                'RESERVED_OUTPUT_FILE')
        write(path, value)
        self.checkpoint()

    def _terminate_children(self):
        # Popen handles cover a child started just before psutil enumeration.
        for child in list(self.children):
            try:
                if child.poll() is None:
                    child.terminate()
            except (OSError, ProcessLookupError):
                pass
        for proc in psutil.Process().children(recursive=True):
            try:
                proc.terminate()
            except psutil.NoSuchProcess:
                pass

    def _on_signal(self, signum, frame):
        raise RuntimeError('SIGNAL_STOP:' + signal.Signals(signum).name)

    def _watch(self):
        while not self._stop.wait(1):
            try:
                self.checkpoint(force=True)
            except BaseException as exc:
                self._watch_error = exc
                self._record_failure(type(exc), exc, exc.__traceback__)
                self._terminate_children()
                # A Python/BLAS/model call can block beyond the next checkpoint.
                # Real runs must stop immediately rather than just set a flag.
                if not self.synthetic:
                    os._exit(70)
                return

    def _record_failure(self, typ, exc, tb):
        write(self.output / 'EXCEPTION.json', dict(type=typ.__name__, message=str(exc),
              traceback=''.join(traceback.format_exception(typ, exc, tb)),
              automatic_retry=False, preserved=True))
        self.state.update(technical_status='EXCEPTION_STOPPED', error=str(exc),
                          ended_utc=utc(), service_heartbeat_utc=utc())
        write(self.output / 'STATUS.json', self.state)

    def finish(self, result):
        with self._lock:
            self.checkpoint(force=True)
            require(code_identity() == self.identity, 'CODE_CHANGED_DURING_RUN')
            self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        with self._lock:
            write(self.output / 'RESULT.json', result)
            usage = self._usage()
            self._validate(usage)
            outputs = {p.relative_to(self.output).as_posix(): sha(p)
                       for p in sorted(self.output.rglob('*'))
                       if p.is_file() and p.name not in ('STATUS.json', 'STAGE_RECEIPT.json')}
            status = result.get('scientific_status', result.get('status', 'NOT_EVALUATED'))
            receipt = dict(version=VERSION, technical_status='COMPLETED',
                           scientific_status=status, mode=self.mode, synthetic=self.synthetic,
                           code_sha256=self.identity, outputs=outputs, limits=self.limits,
                           pairs=self._pairs, encoded_rows=self._encoded,
                           peak_process_tree_rss_bytes=self.peak_rss,
                           peak_output_bytes=self.peak_output,
                           automatic_retry=False, **usage)
            write(self.output / 'STAGE_RECEIPT.json', receipt)
            self.state.update(usage, technical_status='COMPLETED', scientific_status=status,
                              ended_utc=utc(), pairs=self._pairs, encoded_rows=self._encoded)
            write(self.output / 'STATUS.json', self.state)
            self._validate(self._usage())
            self._finished = True
            return receipt

    def _restore_affinity(self):
        if threading.current_thread() is threading.main_thread():
            for signum, handler in self._old_handlers.items():
                signal.signal(signum, handler)
            self._old_handlers.clear()
        if self._old_affinity is not None:
            psutil.Process().cpu_affinity(self._old_affinity)

    def __exit__(self, typ, value, tb):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self._restore_affinity()
        if typ is not None:
            self._terminate_children()
            self._record_failure(typ, value, tb)
        elif not self._finished:
            error = RuntimeError('RUN_DID_NOT_FINALIZE')
            self._record_failure(type(error), error, None)
            raise error
        return False
