"""Hard resource budgets, immutable stage receipts, and explicit successor gates."""
from datetime import datetime, timezone
import os
from pathlib import Path
import threading
import time
import traceback

import psutil

from .common import PACKAGE, ROOT, SPEC_SHA, read_json, require, sha, write_json

LIMITS = {
    'check': dict(cpu=4, rss_bytes=8*2**30, wall_seconds=1800, output_bytes=512*2**20, pairs=0, forwards=0),
    'source': dict(cpu=4, rss_bytes=8*2**30, wall_seconds=14400, output_bytes=2*2**30,
                   pairs=2_000_000_000, forwards=4_600_362),
    'target': dict(cpu=4, rss_bytes=8*2**30, wall_seconds=14400, output_bytes=2*2**30,
                   pairs=9_000_000_000, forwards=0),
}


def code_seal():
    files = [PACKAGE/'run.py', PACKAGE/'DEPENDENCIES.json', PACKAGE/'EXPERIMENT_PLAN.md',
             *PACKAGE.glob('lg/*.py')]
    return {p.relative_to(PACKAGE).as_posix(): sha(p) for p in sorted(files) if p.is_file()}


def verify_package(root=ROOT):
    require(sha(PACKAGE/'EXPERIMENT_PLAN.md') == SPEC_SHA, 'FROZEN_PLAN_CHANGED')
    dependencies = read_json(PACKAGE/'DEPENDENCIES.json')
    require(dependencies['spec_sha256'] == SPEC_SHA, 'DEPENDENCY_PLAN_MISMATCH')
    for path, expected in dependencies['files'].items():
        require(sha(Path(root)/path) == expected, 'LEGACY_DEPENDENCY_CHANGED:' + path)
    return dependencies


def verify_predecessor(path):
    path = Path(path).resolve()
    receipt = read_json(path.parent/'STAGE_RECEIPT.json')
    status = read_json(path.parent/'STATUS.json')
    require(status.get('technical_status') == 'COMPLETED', 'SOURCE_NOT_FINALIZED')
    require(receipt['stage'] == 'source' and receipt['technical_status'] == 'COMPLETED'
            and receipt['spec_sha256'] == SPEC_SHA and receipt['code_sha256'] == code_seal()
            and receipt['result_sha256'] == sha(path), 'INVALID_SOURCE_RECEIPT')
    for rel, expected in receipt['outputs'].items():
        item = (path.parent/rel).resolve()
        require(item.is_relative_to(path.parent) and sha(item) == expected, 'SOURCE_OUTPUT_CHANGED:' + rel)
    result = read_json(path)
    require(result.get('scientific_status') == 'SOURCE_SIGNAL_PASS', 'SOURCE_GATE_NOT_PASS')
    for field, limit in (('elapsed_seconds', 'wall_seconds'),
                         ('peak_process_tree_rss_bytes', 'rss_bytes'),
                         ('output_bytes', 'output_bytes'), ('pairs', 'pairs'),
                         ('head_forward_rows', 'forwards')):
        require(0 <= receipt[field] <= LIMITS['source'][limit], 'SOURCE_BUDGET_EXCEEDED:' + field)
    return result, receipt


class StageRuntime:
    def __init__(self, stage, output, *, limits=None, monitor=True, root=ROOT):
        require(stage in LIMITS, 'UNKNOWN_STAGE')
        self.stage, self.output = stage, Path(output).resolve()
        self.root = Path(root).resolve()
        self.limits = dict(LIMITS[stage] if limits is None else limits)
        self.monitor_enabled = monitor
        self.stop = threading.Event()
        self.lock = threading.RLock()
        self.pairs = self.forwards = self.peak_rss = 0
        self.state = {}
        self.started = time.monotonic()
        self.thread = None
        self.finished = False

    def __enter__(self):
        self.output.mkdir(parents=True, exist_ok=False)
        self.started = time.monotonic()
        self.identity = code_seal()
        proc = psutil.Process()
        self.old_affinity = proc.cpu_affinity() if hasattr(proc, 'cpu_affinity') else None
        try:
            if self.old_affinity is not None:
                proc.cpu_affinity(self.old_affinity[:self.limits['cpu']])
            else:
                raise RuntimeError('CPU_AFFINITY_UNAVAILABLE')
            self.checkpoint('STARTING')
        except BaseException as exc:
            if self.old_affinity is not None:
                proc.cpu_affinity(self.old_affinity)
            write_json(self.output/'EXCEPTION.json', dict(reason=str(exc), phase='ENTER', preserved=True))
            raise
        if self.monitor_enabled:
            self.thread = threading.Thread(target=self._watch, daemon=True)
            self.thread.start()
        return self

    def _usage(self):
        proc = psutil.Process()
        rss = 0
        for p in [proc, *proc.children(recursive=True)]:
            try:
                rss += p.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        self.peak_rss = max(self.peak_rss, rss)
        size = sum(p.stat().st_size for p in self.output.rglob('*') if p.is_file())
        return dict(elapsed_seconds=time.monotonic()-self.started,
                    process_tree_rss_bytes=rss, output_bytes=size)

    def _validate(self, usage):
        for field, maximum, code in (
            ('elapsed_seconds', self.limits['wall_seconds'], 'WALL_LIMIT'),
            ('process_tree_rss_bytes', self.limits['rss_bytes'], 'RSS_LIMIT'),
            ('output_bytes', self.limits['output_bytes'], 'OUTPUT_LIMIT')):
            require(usage[field] <= maximum, code)
        require(self.pairs <= self.limits['pairs'], 'DISTANCE_PAIR_LIMIT')
        require(self.forwards <= self.limits['forwards'], 'HEAD_FORWARD_LIMIT')

    def checkpoint(self, stage=None, **fields):
        with self.lock:
            usage = self._usage()
            self._validate(usage)
            self.state.update(fields)
            if stage is not None:
                self.state['step'] = stage
            self.state.update(stage=self.stage, pid=os.getpid(), technical_status='RUNNING',
                              updated_utc=datetime.now(timezone.utc).isoformat(), **usage,
                              peak_process_tree_rss_bytes=self.peak_rss, pairs=self.pairs,
                              head_forward_rows=self.forwards, limits=self.limits, automatic_retry=False)
            write_json(self.output/'STATUS.json', self.state)

    def add_pairs(self, count):
        require(isinstance(count, int) and count >= 0, 'PAIR_COUNT_INTEGER')
        with self.lock:
            require(self.pairs + count <= self.limits['pairs'], 'DISTANCE_PAIR_LIMIT')
            self.pairs += count

    def add_forwards(self, count):
        require(isinstance(count, int) and count >= 0, 'FORWARD_COUNT_INTEGER')
        with self.lock:
            require(self.forwards + count <= self.limits['forwards'], 'HEAD_FORWARD_LIMIT')
            self.forwards += count

    def write_json(self, name, value):
        path = (self.output/name).resolve()
        require(path.is_relative_to(self.output), 'OUTPUT_PATH_ESCAPE')
        write_json(path, value)
        self.checkpoint()

    def _watch(self):
        while not self.stop.wait(1):
            try:
                self.checkpoint()
            except BaseException as exc:
                write_json(self.output/'EXCEPTION.json', dict(reason=str(exc), preserved=True, automatic_retry=False))
                write_json(self.output/'STATUS.json', dict(self.state, technical_status='EXCEPTION_STOPPED', error=str(exc)))
                for child in psutil.Process().children(recursive=True):
                    try:
                        child.terminate()
                    except psutil.NoSuchProcess:
                        pass
                os._exit(70)

    def finish(self, result):
        self.write_json('RESULT.json', result)
        require(code_seal() == self.identity, 'CODE_CHANGED_DURING_EXECUTION')
        verify_package(self.root)
        # Keep watchdog active while potentially large numeric outputs are hashed.
        outputs = {p.relative_to(self.output).as_posix(): sha(p) for p in sorted(self.output.rglob('*'))
                   if p.is_file() and p.name not in ('STATUS.json', 'STAGE_RECEIPT.json')}
        self._validate(self._usage())
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
        usage = self._usage()
        self._validate(usage)
        receipt = dict(stage=self.stage, technical_status='COMPLETED', spec_sha256=SPEC_SHA,
                       scientific_status=result.get('scientific_status', result.get('status')),
                       code_sha256=self.identity, result_sha256=sha(self.output/'RESULT.json'),
                       outputs=outputs, limits=self.limits, pairs=self.pairs, head_forward_rows=self.forwards,
                       peak_process_tree_rss_bytes=self.peak_rss, **usage, automatic_retry=False)
        write_json(self.output/'STAGE_RECEIPT.json', receipt)
        write_json(self.output/'STATUS.json', dict(self.state, technical_status='COMPLETED',
                                                  scientific_status=receipt['scientific_status']))
        # Include the terminal receipt/status themselves in the final budget.
        usage = self._usage()
        self._validate(usage)
        receipt.update(usage)
        write_json(self.output/'STAGE_RECEIPT.json', receipt)
        self._validate(self._usage())
        self.finished = True
        return receipt

    def __exit__(self, typ, value, tb):
        self.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.old_affinity is not None:
            psutil.Process().cpu_affinity(self.old_affinity)
        if typ is not None:
            write_json(self.output/'EXCEPTION.json', dict(type=typ.__name__, message=str(value),
                       traceback=''.join(traceback.format_exception(typ, value, tb)), preserved=True))
            write_json(self.output/'STATUS.json', dict(self.state, technical_status='EXCEPTION_STOPPED', error=str(value)))
        elif not self.finished:
            raise RuntimeError('STAGE_DID_NOT_FINALIZE')
        return False
