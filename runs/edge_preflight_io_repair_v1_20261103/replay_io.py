"""Scoped storage/observability repair; frozen packet and snapshot semantics stay unchanged.

Completed snapshots are internal, bounded protocol-5 checkpoints containing only
primitive Python values. They are SHA checked before a restricted unpickler is
used. Partial roles are evidence only, never an arbitrary-frame resume point.
The caller must verify scratch_root is node-local before entering install().
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import inspect
import io
import json
import marshal
import math
import os
from pathlib import Path
import pickle
import platform
import shutil
import sys
import tempfile
import time
import uuid

VERSION = 'EDGE_PREFLIGHT_IO_REPAIR_V1_20261103'
MAX_SNAPSHOT_BYTES = 16 * 1024**2
MAX_MANIFEST_BYTES = 8 * 1024**2


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8')


def _write_json(path, value):
    path = Path(path)
    temporary = path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    with temporary.open('xb') as stream:
        stream.write(_canonical(value)+b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _json(path, limit=MAX_MANIFEST_BYTES):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise RuntimeError('INTERNAL_CACHE_MANIFEST_GATE')
    return json.loads(path.read_text(encoding='utf-8'))


def _primitive(value, depth=0, remaining=None):
    if remaining is None:
        remaining = [1_000_000]
    remaining[0] -= 1
    if remaining[0] < 0 or depth > 128:
        raise RuntimeError('INTERNAL_SNAPSHOT_STRUCTURE_LIMIT')
    typ = type(value)
    if value is None or typ in (str, bytes, int, bool):
        return
    if typ is float and math.isfinite(value):
        return
    if typ in (list, tuple, dict):
        iterable = value.items() if typ is dict else value
        for item in iterable:
            _primitive(item, depth+1, remaining)
        return
    raise RuntimeError('INTERNAL_SNAPSHOT_NON_PRIMITIVE:'+typ.__name__)


class _PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise RuntimeError('INTERNAL_SNAPSHOT_GLOBAL_FORBIDDEN')


def _load_snapshot(path, entry):
    path = Path(path)
    if (path.is_symlink() or not path.is_file() or
            not 0 < path.stat().st_size <= MAX_SNAPSHOT_BYTES or
            path.stat().st_size != entry['bytes'] or sha(path) != entry['sha256']):
        raise RuntimeError('INTERNAL_SNAPSHOT_SIZE_OR_SHA_GATE')
    blob = path.read_bytes()
    value = _PrimitiveUnpickler(io.BytesIO(blob)).load()
    _primitive(value)
    if type(value) is not dict or set(value) != {'uid', 'row', 'body', 'q14', 'info'}:
        raise RuntimeError('INTERNAL_SNAPSHOT_TYPE_GATE')
    if type(value['row']) is not dict or value['row'].get('frame') != entry['frame']:
        raise RuntimeError('INTERNAL_SNAPSHOT_FRAME_GATE')
    return value


def _file_identity(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))


def _function_identity(fn):
    code = getattr(fn, '__code__', None)
    return hashlib.sha256(marshal.dumps(code)).hexdigest() if code is not None else repr(fn)


def _code_identities(edge):
    result = {'repair': _file_identity(__file__)}
    source = getattr(edge, '__file__', None)
    if source and Path(source).is_file():
        result['adapter'] = _file_identity(source)
    root = getattr(edge, 'ROOT', None)
    if root is not None:
        # Conservative binding to the complete frozen input/descriptor source
        # tree also covers dynamically imported legacy runtime helpers.
        tree = Path(root)/'repo'/'ood'
        for path in sorted(tree.glob('*.py')):
            result['ood/'+path.name] = _file_identity(path)
    result['selected_snapshots_code'] = _function_identity(edge.selected_snapshots)
    result['numerical_context_code'] = _function_identity(edge.numerical_context)
    result['decode_rows_code'] = _function_identity(edge.decode_rows)
    return result


class _Repair:
    def __init__(self, edge, output, cache_root, scratch_root, deadline, guard, heartbeat):
        self.edge, self.output = edge, Path(output).resolve()
        self.cache_root, scratch = Path(cache_root).resolve(), Path(scratch_root).resolve()
        if not scratch.is_dir():
            raise RuntimeError('VERIFIED_SCRATCH_ROOT_REQUIRED')
        self.output.mkdir(parents=True, exist_ok=True)
        self.cache_root.mkdir(parents=True, exist_ok=True)
        self.deadline, self.guard, self.callback = float(deadline), guard, heartbeat
        self.start, self.last_heartbeat = time.monotonic(), 0.0
        self.original = {name: getattr(edge, name) for name in
                         ('selected_snapshots', 'numerical_context', 'decode_rows')}
        self.code = _code_identities(edge)
        self.scratch = Path(tempfile.mkdtemp(prefix='edge-numeric-owned-', dir=str(scratch)))
        self.active, self.contexts, self.stopped = None, [], False
        self.closed_contexts = []
        self.sequence = 0
        _write_json(self.scratch/'OWNERSHIP.json', dict(version=VERSION, pid=os.getpid(),
                                                      output=str(self.output)))

    def status(self, stage, **extra):
        state = self.active or {}
        contexts = list(self.closed_contexts)
        for ctx in self.contexts:
            store = getattr(ctx, 'states', None)
            path = getattr(store, 'path', None)
            sizes = {}
            if path is not None:
                for suffix in ('', '-journal', '-wal', '-shm'):
                    candidate = Path(str(path)+suffix)
                    if candidate.exists():
                        sizes[candidate.name] = candidate.stat().st_size
            contexts.append(dict(capture=getattr(ctx, 'capture', None),
                                 spill=dict(getattr(store, 'stats', {})), files=sizes))
        value = dict(version=VERSION, stage=stage, role=state.get('role'),
                     frame=state.get('frame', 0), elapsed_seconds=time.monotonic()-self.start,
                     role_elapsed_seconds=time.monotonic()-state.get('start', self.start),
                     append_seconds=state.get('append_seconds', 0.0),
                     decoder_next_seconds=state.get('decoder_next_seconds', 0.0),
                     selected_persisted=state.get('selected_persisted', 0),
                     contexts=contexts, scratch=str(self.scratch), **extra)
        _write_json(self.output/'REPLAY_HEARTBEAT.json', value)
        self.last_heartbeat = time.monotonic()
        if self.callback is not None:
            self.callback(stage, **{k: v for k, v in value.items() if k != 'stage'})
        return value

    def stop(self, reason):
        if not self.stopped:
            self.stopped = True
            # STOP must survive even when the caller's optional UI callback fails.
            callback, self.callback = self.callback, None
            try:
                value = self.status('STOP', reason=reason, partial_role_reusable=False)
            finally:
                self.callback = callback
            _write_json(self.output/'REPLAY_STOP.json', value)
            if self.active and self.active.get('attempt'):
                _write_json(Path(self.active['attempt'])/'STOP.json', value)

    def check(self):
        try:
            if time.monotonic() >= self.deadline:
                raise TimeoutError('EDGE_REPLAY_DEADLINE')
            if self.guard is not None:
                self.guard()
        except BaseException as exc:
            self.stop(type(exc).__name__+':'+str(exc))
            raise

    def numerical_context(self, capture, api, working, first_frame=1, max_states=4_000_000):
        self.check()
        self.sequence += 1
        # Ignore caller's numerical DB path only; stderr and outputs stay where
        # the frozen adapter requested. All numerical constructor args survive.
        path = self.scratch/('%04d.sqlite' % self.sequence)
        ctx = self.original['numerical_context'](capture, api, path, first_frame, max_states)
        original_append = ctx.append
        original_close = ctx.close

        def append(packet):
            self.check()
            started = time.monotonic()
            try:
                return original_append(packet)
            finally:
                if self.active is not None:
                    self.active['append_seconds'] += time.monotonic()-started

        ctx.append = append
        self.contexts.append(ctx)
        closed = [False]

        def close():
            if not closed[0]:
                self.closed_contexts.append(dict(capture=capture,
                    spill=dict(getattr(ctx.states, 'stats', {})), closed=True,
                    database_bytes=sum(Path(str(path)+s).stat().st_size for s in
                        ('', '-journal', '-wal', '-shm') if Path(str(path)+s).exists())))
                original_close()
                closed[0] = True
                self.contexts.remove(ctx)
        ctx.close = close
        return ctx

    def decode_rows(self, *args, **kwargs):
        stream = self.original['decode_rows'](*args, **kwargs)
        try:
            while True:
                self.check()
                started = time.monotonic()
                try:
                    packet = next(stream)
                except StopIteration:
                    return
                finally:
                    if self.active is not None:
                        self.active['decoder_next_seconds'] += time.monotonic()-started
                self.check()
                if self.active is not None:
                    self.active['frame'] = int(packet['frame.number'])
                    if (self.active['frame'] % 4096 == 0 or
                            time.monotonic()-self.last_heartbeat >= 5):
                        self.status('RAW_PREFIX_REPLAY')
                yield packet
        finally:
            stream.close()

    def binding(self, role, frames, refs, value, tshark):
        raw_spec = value['raw_inputs'][role]
        raw = Path(raw_spec['path'])
        self.check()
        if raw.stat().st_size != raw_spec['bytes'] or sha(raw) != raw_spec['sha256']:
            raise RuntimeError('CACHE_RAW_IDENTITY_GATE')
        decoder = _file_identity(tshark) if Path(tshark).is_file() else dict(path=str(tshark))
        return dict(version=VERSION, role=role, frames=frames, reference_frames=refs,
                    raw=dict(raw_spec), full_card=value,
                    namespace_owner=getattr(self.edge, 'OWNER', None),
                    capture_boundaries=self.edge.segments(role, value),
                    code=self.code, decoder=decoder,
                    runtime=dict(python=sys.version, executable=sys.executable,
                                 implementation=platform.python_implementation(),
                                 platform=platform.platform(), byteorder=sys.byteorder))

    def selected_snapshots(self, role, frames, working_directory, *, tshark=None,
                           reference_frames=(), value=None, deadline=None):
        value = self.edge.card() if value is None else value
        tshark = self.edge.TSHARK if tshark is None else tshark
        frames, refs = sorted(set(map(int, frames))), sorted(set(map(int, reference_frames)))
        if not frames or not set(refs) <= set(frames):
            raise RuntimeError('SELECTED_FRAME_SET')
        binding = self.binding(role, frames, refs, value, tshark)
        key = hashlib.sha256(_canonical(binding)).hexdigest()
        cache = self.cache_root/key
        cache.mkdir(exist_ok=True)
        if cache.is_symlink() or cache.resolve().parent != self.cache_root:
            raise RuntimeError('INTERNAL_CACHE_DIRECTORY_GATE')
        binding_path = cache/'BINDING.json'
        if binding_path.exists():
            if _json(binding_path) != binding:
                raise RuntimeError('CACHE_BINDING_GATE')
        else:
            _write_json(binding_path, binding)
        self.active = dict(role=role, frame=0, start=time.monotonic(),
                           append_seconds=0.0, decoder_next_seconds=0.0, selected_persisted=0)
        complete_path = cache/'COMPLETE.json'
        if complete_path.exists():
            complete = _json(complete_path)
            if (complete.get('binding_sha256') != key or complete.get('frames') != frames or
                    complete.get('original_generator_exhausted') is not True):
                raise RuntimeError('CACHE_COMPLETE_GATE')
            attempt_name = complete['attempt']
            if Path(attempt_name).name != attempt_name:
                raise RuntimeError('CACHE_ATTEMPT_PATH_GATE')
            attempt = cache/attempt_name
            if attempt.is_symlink() or not attempt.is_dir() or attempt.resolve().parent != cache:
                raise RuntimeError('INTERNAL_CACHE_ATTEMPT_DIRECTORY_GATE')
            entries = complete['entries']
            if [e['frame'] for e in entries] != frames:
                raise RuntimeError('CACHE_FRAME_ORDER_GATE')
            self.status('COMPLETED_ROLE_CACHE_REUSE', binding_sha256=key)
            for entry in entries:
                self.check()
                if entry['file'] != str(entry['frame'])+'.pickle':
                    raise RuntimeError('CACHE_SNAPSHOT_PATH_GATE')
                yield _load_snapshot(attempt/entry['file'], entry)
            self.check()
            raw = Path(value['raw_inputs'][role]['path'])
            if sha(raw) != value['raw_inputs'][role]['sha256']:
                raise RuntimeError('CACHE_RAW_FINAL_IDENTITY_GATE')
            self.status('ROLE_COMPLETE_REUSED', binding_sha256=key)
            self.active = None
            return
        attempt = cache/('attempt-'+uuid.uuid4().hex)
        attempt.mkdir(exist_ok=False)
        self.active['attempt'] = str(attempt)
        _write_json(attempt/'START.json', dict(binding_sha256=key,
                                             partial_role_reusable=False))
        entries = []
        stream = self.original['selected_snapshots'](
            role, frames, working_directory, tshark=tshark, reference_frames=refs,
            value=value, deadline=min(self.deadline, deadline) if deadline is not None else self.deadline)
        exhausted = False
        try:
            self.status('ROLE_START', binding_sha256=key)
            for snapshot in stream:
                self.check()
                _primitive(snapshot)
                frame = snapshot['row']['frame']
                if frame not in frames or any(e['frame'] == frame for e in entries):
                    raise RuntimeError('CACHE_SELECTED_FRAME_IDENTITY')
                blob = pickle.dumps(snapshot, protocol=5)
                if not 0 < len(blob) <= MAX_SNAPSHOT_BYTES:
                    raise RuntimeError('INTERNAL_SNAPSHOT_SIZE_GATE')
                destination = attempt/(str(frame)+'.pickle')
                with destination.open('xb') as saved:
                    saved.write(blob)
                    saved.flush()
                    os.fsync(saved.fileno())
                entries.append(dict(frame=frame, file=destination.name, bytes=len(blob),
                                    sha256=hashlib.sha256(blob).hexdigest()))
                self.active['selected_persisted'] = len(entries)
                _write_json(attempt/'PARTIAL.json', dict(binding_sha256=key, entries=entries,
                                                        partial_role_reusable=False))
                yield snapshot
            # This point is reachable only after original generator's finally
            # and final raw identity checks have returned successfully.
            exhausted = True
            self.check()
            entries.sort(key=lambda e: e['frame'])
            if [e['frame'] for e in entries] != frames:
                raise RuntimeError('CACHE_COMPLETED_FRAME_COVERAGE')
            _write_json(complete_path, dict(binding_sha256=key, frames=frames,
                       attempt=attempt.name, entries=entries, original_generator_exhausted=True))
            self.status('ROLE_COMPLETE', binding_sha256=key)
        except BaseException as exc:
            self.stop(type(exc).__name__+':'+str(exc))
            raise
        finally:
            try:
                stream.close()
            finally:
                if not exhausted:
                    _write_json(attempt/'INCOMPLETE.json', dict(binding_sha256=key,
                                partial_role_reusable=False, persisted=len(entries)))
                self.active = None

    def close(self):
        for name, value in self.original.items():
            setattr(self.edge, name, value)
        # A consumer may have abandoned a generator. Close numerical handles
        # before removing only the mkdtemp directory created by this instance.
        for ctx in list(self.contexts):
            ctx.close()
        shutil.rmtree(self.scratch)


@contextmanager
def install(edge_module, *, output, cache_root, scratch_root, deadline, guard, heartbeat=None):
    repair = _Repair(edge_module, output, cache_root, scratch_root, deadline, guard, heartbeat)
    try:
        edge_module.numerical_context = repair.numerical_context
        edge_module.decode_rows = repair.decode_rows
        edge_module.selected_snapshots = repair.selected_snapshots
        yield repair
    finally:
        repair.close()
