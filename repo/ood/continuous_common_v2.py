"""Versioned repair identities, durable files and truthful progress."""
import gzip
import hashlib
import json
import os
import signal
from pathlib import Path
import time

from legacy_unsw_archival_runtime_v2 import Progress as PriorProgress

DESIGN_SHA = '8396629e6e2495d98bfc1d4a5288f0570bc1a95d653596419005eb96470f55bd'
SEEDS = (27, 127, 227)
ARMS = ('OLD_MATCHED', 'RECENT', 'RECENT_STATE')


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def pin(path, expected):
    path = Path(path)
    require(path.is_file() and sha(path) == expected, 'IDENTITY:' + str(path))
    return path


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value, replace=False):
    path = Path(path)
    require(replace or not path.exists(), 'NO_OVERWRITE:' + str(path))
    temp = path.with_name(path.name + '.json.next')
    with temp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2, allow_nan=False)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(str(temp), str(path))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def uid_sha(values):
    return hashlib.sha256(''.join(u + '\n' for u in sorted(values)).encode()).hexdigest()


def seal(folder):
    folder = Path(folder)
    require(not (folder/'SHA256SUMS').exists(), 'ALREADY_SEALED')
    paths = sorted(p for p in folder.rglob('*') if p.is_file() and p.name not in ('status.json', 'STOP_REQUESTED'))
    with (folder/'SHA256SUMS').open('x', encoding='utf-8', newline='\n') as stream:
        for p in paths:
            stream.write(sha(p) + '  ' + p.relative_to(folder).as_posix() + '\n')
        stream.flush(); os.fsync(stream.fileno())


def verify(folder, exact=True):
    folder = Path(folder).resolve()
    listed = set()
    for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h, rel = line.split('  ', 1)
        path = (folder/rel).resolve()
        require(path.is_relative_to(folder), 'SEAL_ESCAPE')
        require(rel not in listed, 'SEAL_DUPLICATE')
        listed.add(rel)
        pin(path, h)
    if exact:
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()
                  and p.name not in ('status.json', 'STOP_REQUESTED') and p != folder/'SHA256SUMS'}
        require(actual == listed, 'SEAL_FILE_SET')


def save_arrays(path, **values):
    import numpy as np
    with Path(path).open('xb') as stream:
        np.savez(stream, **values)
        stream.flush(); os.fsync(stream.fileno())
    with np.load(path, allow_pickle=False) as check:
        require(set(check.files) == set(values), 'NPZ_KEYS')
        for key, value in values.items():
            require(np.array_equal(check[key], value), 'NPZ_READBACK:' + key)


def authorize(root, explicit):
    # Authority checked before reading package, raw, model, or result files.
    require(explicit, 'REAL_CHAIN_NOT_AUTHORIZED')
    root = Path(root)
    verify(root, exact=False)  # The immutable package may contain the declared run directory and checkpoint link.
    design = read(pin(root/'design_contract.json', DESIGN_SHA))
    runtime = read(root/'runtime_contract.json')
    require(runtime['design_sha256'] == DESIGN_SHA and runtime['retries'] == 0, 'RUNTIME_CONTRACT')
    return design, runtime


class Progress(PriorProgress):
    def watch(self):
        while not self.closed.wait(2):
            try:
                self.guard()
            except Exception as exc:
                self.record_failure(exc, 'watchdog')
                self.kill_children()
                return

    def kill_children(self):
        for process in list(self.children):
            try:
                if getattr(process, 'continuous_group', False): os.killpg(process.pid, signal.SIGTERM)
                elif process.poll() is None: process.kill()
            except ProcessLookupError: pass

    def stop(self, status, error=None, **extra):
        if status != 'COMPLETE': self.kill_children()
        super().stop(status, error=error, **extra)

    def guard(self):
        require(self.error is None, self.error or 'PRIOR_FAILURE')
        now = time.monotonic()
        if now - getattr(self, '_last_guard', 0) >= 1:
            self._last_guard = now
            super().guard()

    def emit(self, status='RUNNING', **extra):
        # Old frozen evaluator hardcoded optimizer_updates=0; do not inherit that claim.
        with self.write_lock:
            write(self.out/'status.json', dict(status=status, stage=self.stage,
                elapsed_seconds=time.monotonic()-self.started, updated_epoch=time.time(),
                rss_gib=self.rss/1024**3, retries=0,
                optimizer_updates=getattr(self, 'optimizer_updates', 0),
                historical_holdout_opened=False, **extra), replace=True)
