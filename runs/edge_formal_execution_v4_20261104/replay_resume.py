"""Atomic mid-role checkpoints around the unchanged causal adapter.

Only at a completed physical-frame boundary: flush selected snapshots, commit
all resident states to SQLite, back up SQLite, save every context ledger, then
publish one hashed manifest. Decoder replay always starts at raw frame one;
numerical updates start after the verified checkpoint. No raw filtering.
"""
from collections import Counter, deque
from contextlib import closing
import hashlib
import io
import os
from pathlib import Path
import pickle
import shutil
import sqlite3
import struct
import time
import uuid

from checkpoint import (PackedRoleSpool, PrimitiveUnpickler, atomic_json, bind_directory,
    canonical, fsync_directory, read_json, require, safe_id, sha, write_bytes)

EXCLUDED = {'api', 'states', 'append', 'close'}


class StateUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == 'collections' and name in ('Counter', 'deque'):
            return {'Counter': Counter, 'deque': deque}[name]
        if module == 'continuous_input_v3' and name == 'RecentState':
            from continuous_input_v3 import RecentState
            return RecentState
        raise ValueError('REPLAY_CHECKPOINT_GLOBAL_FORBIDDEN:'+module+'.'+name)


def load_state(blob):
    return StateUnpickler(io.BytesIO(blob)).load()


def seed_role(source, target_output, role, binding, expected_rows):
    """Import an explicitly selected stopped v4 run, with an identical binding.

    Immutable files may be hardlinked. Never import v3 partial snapshots, never
    edit the origin, and never replace a newer checkpoint in the target.
    """
    source, target_output = Path(source), Path(target_output)
    expected = sorted(expected_rows)
    require((source/'spools'/role/'BINDING.json').is_file(), 'RESUME_SOURCE_BINDING_REQUIRED')
    old = PackedRoleSpool(source/'spools'/role, binding, role, expected)
    target = PackedRoleSpool(target_output/'spools'/role, binding, role, expected)
    if target.is_complete(): return
    target_manager = Checkpoints(target_output/'replay_checkpoints'/role, target, expected_rows)
    if target_manager.load() is not None: return
    def link_file(origin, destination):
        require(origin.is_file() and not origin.is_symlink(), 'RESUME_SOURCE_FILE')
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(not destination.is_symlink(), 'RESUME_TARGET_FILE')
        if destination.exists(): require(sha(origin) == sha(destination), 'RESUME_SEED_CONFLICT')
        else: os.link(origin, destination)
    if old.is_complete():
        manifest = read_json(old.root/'COMPLETE.json')
        for row in old.headers(): old.load(row['uid'])
        for record in manifest['chunks']:
            for name in ('snapshots.bin', 'INDEX.json', 'CHUNK.json'):
                relative = Path(manifest['attempt'])/record['name']/name
                link_file(old.root/relative, target.root/relative)
        require((old.root/'REPLAY_COVERAGE.json').is_file(), 'RESUME_COMPLETE_COVERAGE')
        link_file(old.root/'REPLAY_COVERAGE.json', target.root/'REPLAY_COVERAGE.json')
        atomic_json(target.root/'COMPLETE.json', manifest)
        require(target.is_complete(), 'RESUME_SEEDED_COMPLETE')
    else:
        cp_root = source/'replay_checkpoints'/role
        require((cp_root/'BINDING.json').is_file() and (cp_root/'CURRENT.json').is_file(),
                'RESUME_DURABLE_CONTEXT_REQUIRED')
        manager = Checkpoints(cp_root, old, expected_rows)
        directory, value = manager.load()
        partial = value['partial']
        for record in partial['chunks']:
            for name in ('snapshots.bin', 'INDEX.json', 'CHUNK.json'):
                relative = Path(partial['attempt'])/record['name']/name
                link_file(old.root/relative, target.root/relative)
        generation = target_manager.root/directory.name
        for name in ('states.sqlite', 'context.pickle', 'MANIFEST.json'):
            link_file(directory/name, generation/name)
        atomic_json(target_manager.root/'CURRENT.json', read_json(cp_root/'CURRENT.json'))
        require(target_manager.load()[1]['frame'] == value['frame'], 'RESUME_SEED_FRAME')
    atomic_json(target.root/'RESUME_SOURCE.json', dict(source=str(source), role=role,
        binding_sha256=target.binding_sha256, status='IDENTICAL_BINDING_SEED_VERIFIED'))


def seed_explicit_source(card, output, binding, refs, selected):
    name = card.get('replay_checkpoint_source')
    if name is None: return
    from streaming import ROOT
    from runtime_control import current_status
    source = Path(name)
    require(source.is_absolute() and not source.is_symlink() and source.resolve().is_relative_to(ROOT.parents[1])
            and source.resolve() != Path(output).resolve(), 'RESUME_SOURCE_SCOPE')
    require(current_status(source)['status'] == 'STOP', 'RESUME_SOURCE_MUST_BE_STOPPED')
    for role in ('NORMAL', 'HTTP', 'UDP'):
        expected = (refs if role == 'NORMAL' else [])+selected[role]
        seed_role(source, output, role, binding, {r['uid']: r for r in expected})


def validate_prefix(spool, partial, frame, expected_rows):
    require(partial['binding_sha256'] == spool.binding_sha256, 'RESUME_SPOOL_BINDING')
    seen, records = set(), partial['chunks']
    expected = {uid for uid, row in expected_rows.items() if row['frame'] <= frame}
    require(set(partial['seen']) == expected, 'RESUME_EXACT_SELECTED_PREFIX')
    if not records:
        require(not expected and partial['attempt'] is None, 'RESUME_EMPTY_PREFIX')
        return None
    attempt = spool.root/safe_id(partial['attempt'])
    require(attempt.is_dir() and not attempt.is_symlink(), 'RESUME_ATTEMPT_DIRECTORY')
    for ordinal, record in enumerate(records):
        require(record['name'] == 'chunk-%06d' % ordinal, 'RESUME_CHUNK_ORDER')
        folder = attempt/record['name']
        require(not folder.is_symlink() and read_json(folder/'CHUNK.json') == record, 'RESUME_CHUNK_MANIFEST')
        for filename, field in (('snapshots.bin', 'data'), ('INDEX.json', 'index')):
            path, pin = folder/filename, record[field]
            require(not path.is_symlink() and path.stat().st_size == pin['bytes']
                    and sha(path) == pin['sha256'], 'RESUME_CHUNK_SHA')
        entries = read_json(folder/'INDEX.json')
        require(len(entries) == record['rows'], 'RESUME_CHUNK_ROWS')
        offset = 0
        with (folder/'snapshots.bin').open('rb') as source:
            for entry in entries:
                require(entry['offset'] == offset+8 and 0 < entry['bytes'] <= 16*1024**2, 'RESUME_OFFSET')
                require(struct.unpack('<Q', source.read(8))[0] == entry['bytes'], 'RESUME_LENGTH')
                blob = source.read(entry['bytes']); offset += entry['bytes']+8
                require(hashlib.sha256(blob).hexdigest() == entry['sha256'], 'RESUME_SNAPSHOT_SHA')
                snapshot = PrimitiveUnpickler(io.BytesIO(blob)).load()
                header = PackedRoleSpool._header(snapshot); uid = snapshot['uid']
                require(uid in expected and uid not in seen and canonical(header) == canonical(entry['header'])
                        and header['row']['frame'] == expected_rows[uid]['frame'], 'RESUME_SNAPSHOT_IDENTITY')
                seen.add(uid)
        require(offset == record['data']['bytes'], 'RESUME_TRAILING_DATA')
    require(seen == expected, 'RESUME_PREFIX_COVERAGE')
    return attempt


class Checkpoints:
    def __init__(self, root, spool, expected_rows, *, failpoint=None):
        self.spool, self.expected_rows = spool, expected_rows
        self.root, self.binding = bind_directory(root, dict(schema='EDGE_REPLAY_CONTEXT_CHECKPOINT_V1',
            spool_binding_sha256=spool.binding_sha256, role=spool.role))
        self.failpoint = failpoint or (lambda stage: None)

    def load(self):
        pointer = self.root/'CURRENT.json'
        if not pointer.exists(): return None
        reference = read_json(pointer)
        directory = self.root/safe_id(reference['generation'])
        require(directory.name.startswith('gen-') and not directory.is_symlink(), 'RESUME_GENERATION')
        require(sha(directory/'MANIFEST.json') == reference['manifest_sha256'], 'RESUME_MANIFEST_SHA')
        value = read_json(directory/'MANIFEST.json')
        require(value['binding_sha256'] == self.binding and type(value['frame']) is int
                and 0 < value['frame'] < max(r['frame'] for r in self.expected_rows.values()), 'RESUME_FRAME_BINDING')
        require(set(value['files']) == {'context.pickle', 'states.sqlite'}, 'RESUME_FILES')
        for name, pin in value['files'].items():
            path = directory/name
            limit = (1024**3 if name == 'context.pickle' else 8*1024**3)
            require(not path.is_symlink() and 0 < path.stat().st_size <= limit
                    and path.stat().st_size == pin['bytes'] and sha(path) == pin['sha256'], 'RESUME_PAYLOAD_SHA')
        validate_prefix(self.spool, value['partial'], value['frame'], self.expected_rows)
        return directory, value

    def restore_spool(self, saved):
        directory, value = saved
        partial = value['partial']
        old = validate_prefix(self.spool, partial, value['frame'], self.expected_rows)
        require(self.spool.attempt is None and not self.spool.seen, 'RESUME_ONLY_FRESH_SPOOL')
        if old is not None:
            target = self.spool.root/('attempt-'+uuid.uuid4().hex); target.mkdir()
            for record in partial['chunks']:
                folder = target/record['name']; folder.mkdir()
                for name in ('snapshots.bin', 'INDEX.json', 'CHUNK.json'):
                    os.link(old/record['name']/name, folder/name)
                fsync_directory(folder)
            fsync_directory(target)
            self.spool.attempt = target
        self.spool.chunk_records = list(partial['chunks'])
        self.spool.seen = set(partial['seen'])

    def save(self, context):
        frame = context.frame
        require(0 < frame < max(r['frame'] for r in self.expected_rows.values()), 'CHECKPOINT_BEFORE_LAST_SELECTED')
        started = time.monotonic(); spool = self.spool
        spool._flush()
        partial = dict(binding_sha256=spool.binding_sha256,
            attempt=spool.attempt.name if spool.attempt else None,
            chunks=list(spool.chunk_records), seen=sorted(spool.seen))
        require(set(partial['seen']) == {uid for uid, row in self.expected_rows.items() if row['frame'] <= frame},
                'CHECKPOINT_FRAME_SNAPSHOT_ATOMIC_BOUNDARY')
        store = context.states
        store._check()
        # Commit resident mutable values too; SQLite alone otherwise misses them.
        for key, state in store.cache.items():
            store.db.execute('UPDATE objects SET value=? WHERE key=?', (store.encode(state), store._key(key)))
        store.db.commit()
        attrs = {k: v for k, v in context.__dict__.items() if k not in EXCLUDED}
        require(not any(callable(v) for v in attrs.values()), 'CONTEXT_FUNCTION_NOT_SERIALIZABLE')
        generation = 'gen-'+uuid.uuid4().hex
        directory = self.root/('.pending-'+generation); directory.mkdir()
        with (directory/'context.pickle').open('xb') as stream:
            pickle.dump(dict(attrs=attrs, count=store.count, stats=store.stats, resident_limit=store.limit), stream, protocol=5)
            stream.flush(); os.fsync(stream.fileno())
        with closing(sqlite3.connect(str(directory/'states.sqlite'))) as destination:
            store.db.backup(destination)
        with (directory/'states.sqlite').open('rb+') as stream: stream.flush(); os.fsync(stream.fileno())
        self.failpoint('after_payload')
        value = dict(schema='EDGE_REPLAY_CONTEXT_COMMIT_V1', binding_sha256=self.binding,
            frame=frame, capture=context.capture, partial=partial,
            files={name: dict(bytes=(directory/name).stat().st_size, sha256=sha(directory/name))
                   for name in ('context.pickle', 'states.sqlite')}, seconds=time.monotonic()-started)
        write_bytes(directory/'MANIFEST.json', canonical(value)); fsync_directory(directory)
        self.failpoint('before_commit')
        final = self.root/generation; os.rename(directory, final); fsync_directory(self.root)
        old = read_json(self.root/'CURRENT.json') if (self.root/'CURRENT.json').exists() else None
        atomic_json(self.root/'CURRENT.json', dict(generation=generation, manifest_sha256=sha(final/'MANIFEST.json')))
        self.failpoint('after_commit')
        # Keep current plus its predecessor. Only this bound checkpoint directory.
        keep = {generation, old['generation'] if old else None}
        for path in self.root.iterdir():
            if path.is_dir() and (path.name.startswith('gen-') or path.name.startswith('.pending-gen-')) and path.name not in keep:
                require(not path.is_symlink() and path.resolve().parent == self.root.resolve(), 'CHECKPOINT_CLEANUP_SCOPE')
                shutil.rmtree(path)
        return value

    def restore_context(self, context, saved):
        directory, value = saved
        with (directory/'context.pickle').open('rb') as source: saved_state = StateUnpickler(source).load()
        attrs = saved_state['attrs']
        require(set(attrs) == set(context.__dict__)-EXCLUDED and attrs['capture'] == context.capture
                and attrs['frame'] == value['frame'] and attrs['known'] == context.known
                and attrs['required'] == context.required and attrs['max_states'] == context.max_states,
                'RESUME_CONTEXT_SCHEMA')
        store = context.states
        require(not store.cache and store.count == 0 and store.limit == saved_state['resident_limit'], 'RESUME_EMPTY_STORE')
        with closing(sqlite3.connect('file:'+str(directory/'states.sqlite')+'?mode=ro', uri=True)) as database:
            database.backup(store.db)
        require(store.db.execute('SELECT count(*) FROM objects').fetchone()[0] == saved_state['count']
                and store.db.execute('SELECT count(*) FROM objects WHERE value IS NULL').fetchone()[0] == 0,
                'RESUME_DB_ROWS')
        store.count, store.stats, store.decode = saved_state['count'], saved_state['stats'], load_state
        context.__dict__.update(attrs)


def snapshots(adapter, patched, spool, expected_rows, checkpoint_root, role, frames, working,
              *, interval_seconds=600, checkpoint_frame=None, failpoint=None, **kwargs):
    """The original selected_snapshots remains the numerical/metadata oracle."""
    manager = Checkpoints(checkpoint_root, spool, expected_rows, failpoint=failpoint)
    saved = manager.load()
    resume_frame = saved[1]['frame'] if saved else 0
    if saved: manager.restore_spool(saved)
    remaining = [f for f in frames if f > resume_frame]
    require(remaining, 'RESUME_REMAINING_SELECTED_REQUIRED')
    kwargs['reference_frames'] = [f for f in kwargs.get('reference_frames', ()) if f > resume_frame]
    original_decode, original_context = adapter.decode_rows, adapter.numerical_context
    current = [None]; last_saved = [time.monotonic()]; appended = [0]
    last_selected_frame = max(frames)
    def numerical(*args, **kw):
        ctx = original_context(*args, **kw)
        if saved and ctx.capture == saved[1]['capture']:
            manager.restore_context(ctx, saved)
        current[0] = ctx
        return ctx
    def decode(*args, **kw):
        stream = original_decode(*args, **kw)
        try:
            for packet in stream:
                frame = int(packet['frame.number'])
                if frame <= resume_frame: continue
                yield packet
                # Adapter has appended the frame; consumer has persisted any selected snapshot.
                appended[0] += 1
                if frame < last_selected_frame and (frame == checkpoint_frame or time.monotonic()-last_saved[0] >= interval_seconds):
                    require(current[0] is not None and current[0].frame == frame, 'CHECKPOINT_SAFE_BOUNDARY')
                    value = manager.save(current[0]); last_saved[0] = time.monotonic()
                    patched.status('REPLAY_CHECKPOINT_COMMITTED', checkpoint_frame=frame, checkpoint_seconds=value['seconds'])
        finally:
            stream.close()
    adapter.decode_rows, adapter.numerical_context = decode, numerical
    patched.active['selected_persisted'] = len(spool.seen)
    try:
        stream = patched.original['selected_snapshots'](role, remaining, working, **kwargs)
        try:
            yield from stream
        finally:
            stream.close()
    finally:
        adapter.decode_rows, adapter.numerical_context = original_decode, original_context
        atomic_json(manager.root/'LAST_ATTEMPT.json', dict(resume_from_frame=resume_frame,
            numerical_frames_appended=appended[0], selected_saved=len(spool.seen)))
