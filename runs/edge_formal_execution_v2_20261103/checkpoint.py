"""Atomic, identity-bound batches and complete-role snapshot spools.

This module performs no model inference. A committed batch directory is the
authoritative transaction; LEDGER.json is a recoverable summary. A partial role
never supplies scientific encoder inputs and cannot resume numerical contexts
from an arbitrary frame.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import pickle
import re
import shutil
import struct
import uuid

import numpy as np

SCHEMA = 'EDGE_ATOMIC_BATCH_V1'
MAX_JSON_BYTES = 32 * 1024**2
MAX_SNAPSHOT_BYTES = 16 * 1024**2


def require(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('utf-8') + b'\n'


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def fsync_directory(path):
    # Windows does not expose POSIX directory fsync. Payload files are always
    # flushed and fsynced; Linux adds directory-entry durability here.
    if os.name == 'posix':
        handle = os.open(str(path), os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(handle)
        finally:
            os.close(handle)


def write_bytes(path, payload):
    path = Path(path)
    with path.open('xb') as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    write_bytes(temp, canonical(value))
    os.replace(temp, path)
    fsync_directory(path.parent)


def read_json(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink() and
            path.stat().st_size <= MAX_JSON_BYTES, 'CHECKPOINT_JSON_SCOPE_SIZE')
    return json.loads(path.read_text(encoding='utf-8'))


def safe_id(value):
    require(type(value) is str and
            re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', value) is not None,
            'CHECKPOINT_ID')
    return value


def check_uids(uids):
    require(type(uids) in (list, tuple) and 0 < len(uids), 'CHECKPOINT_UID_LIST')
    value = list(uids)
    require(all(type(item) is str and 0 < len(item) <= 256 and
                '\n' not in item and '\r' not in item and '\x00' not in item
                for item in value), 'CHECKPOINT_UID_TYPE')
    require(len(value) == len(set(value)), 'CHECKPOINT_DUPLICATE_UID')
    return value


def primitive(value, depth=0, count=None):
    if count is None:
        count = [1_000_000]
    count[0] -= 1
    require(depth <= 128 and count[0] >= 0, 'SNAPSHOT_STRUCTURE_LIMIT')
    typ = type(value)
    if value is None or typ in (str, bytes, int, bool):
        return
    if typ is float:
        require(math.isfinite(value), 'SNAPSHOT_FINITE')
        return
    require(typ in (dict, tuple, list), 'SNAPSHOT_PRIMITIVE_TYPES')
    for item in value.items() if typ is dict else value:
        primitive(item, depth + 1, count)


class PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise ValueError('SNAPSHOT_GLOBAL_FORBIDDEN')


def bind_directory(root, binding):
    root = Path(root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    require(not root.is_symlink(), 'CHECKPOINT_ROOT_SYMLINK')
    encoded = canonical(binding)
    target = root / 'BINDING.json'
    if target.exists():
        require(target.read_bytes() == encoded, 'CHECKPOINT_BINDING_CHANGED')
    else:
        write_bytes(target, encoded)
        fsync_directory(root)
    return root, hashlib.sha256(encoded).hexdigest()


class BatchStore:
    """Single-writer store; byte-identical committed batches may be reused.

    commit failpoints receive names ``after_payload``, ``after_manifest``,
    ``after_commit`` and ``after_ledger``. Tests may terminate the process at a
    point; production callers leave the hook None.
    """
    def __init__(self, root, binding, max_rows=16):
        require(type(max_rows) is int and 1 <= max_rows <= 16, 'BATCH_ROW_BOUND')
        self.max_rows = max_rows
        self.root, self.binding_sha256 = bind_directory(root, dict(
            schema=SCHEMA, identity=binding, max_rows=max_rows,
            arrays={'E3': {'dtype': '<f4', 'columns': 768},
                    'q14': {'dtype': '<f4', 'columns': 14}}))
        self.batches = self.root / 'batches'
        self.pending = self.root / 'pending'
        for p in (self.batches, self.pending):
            p.mkdir(exist_ok=True)
            require(not p.is_symlink(), 'CHECKPOINT_DIRECTORY_SYMLINK')
        self.records = {}
        self.uid_owner = {}
        self._recover()

    def _pin(self, path):
        return dict(bytes=path.stat().st_size, sha256=sha(path))

    def _validate(self, path, expected_uids=None):
        require(path.is_dir() and not path.is_symlink(), 'BATCH_DIRECTORY')
        record = read_json(path / 'MANIFEST.json')
        require(record.get('schema') == SCHEMA and record.get('status') == 'COMMITTED'
                and record.get('binding_sha256') == self.binding_sha256
                and record.get('batch_id') == path.name, 'BATCH_MANIFEST_BINDING')
        uids = check_uids(record.get('uids'))
        require(1 <= len(uids) <= self.max_rows and record.get('rows') == len(uids), 'BATCH_ROWS')
        if expected_uids is not None:
            require(uids == check_uids(expected_uids), 'BATCH_UID_ORDER_CHANGED')
        require(set(record.get('files', {})) == {'E3.npy', 'q14.npy', 'uids.json', 'rows.json'},
                'BATCH_EXACT_PAYLOAD_FILES')
        for name, pin in record['files'].items():
            target = path / name
            require(target.is_file() and not target.is_symlink()
                    and target.stat().st_size == pin['bytes']
                    and sha(target) == pin['sha256'], 'BATCH_FILE_SHA_SIZE:' + name)
        require(read_json(path/'uids.json') == uids, 'BATCH_SAVED_UIDS')
        rows = read_json(path/'rows.json')
        require(type(rows) is list and len(rows) == len(uids)
                and all(type(row) is dict and row.get('uid') == uid
                        for row, uid in zip(rows, uids)), 'BATCH_SAVED_ROWS')
        for name, width in (('E3', 768), ('q14', 14)):
            array = np.load(path/(name+'.npy'), allow_pickle=False, mmap_mode='r')
            require(array.dtype == np.dtype('<f4') and array.shape == (len(uids), width)
                    and np.isfinite(array).all(), 'BATCH_ARRAY_SCHEMA:' + name)
            require(record['arrays'][name] == dict(dtype='<f4', shape=[len(uids), width]),
                    'BATCH_ARRAY_MANIFEST:' + name)
            del array
        return record

    def _ledger(self):
        atomic_json(self.root/'LEDGER.json', dict(schema=SCHEMA,
            binding_sha256=self.binding_sha256,
            authoritative_batch_manifests='batches/<batch_id>/MANIFEST.json',
            committed_batches=len(self.records),
            committed_rows=len(self.uid_owner)))

    def _recover(self):
        for path in sorted(self.batches.iterdir()):
            safe_id(path.name)
            record = self._validate(path)
            for uid in record['uids']:
                require(uid not in self.uid_owner, 'BATCH_CROSS_BATCH_UID_OVERLAP')
                self.uid_owner[uid] = path.name
            self.records[path.name] = record
        # A renamed committed directory is authoritative even if the process
        # died before LEDGER replacement. Pending directories are never loaded.
        self._ledger()

    def has(self, batch_id, expected_uids):
        safe_id(batch_id)
        expected_uids = check_uids(expected_uids)
        if batch_id not in self.records:
            return False
        self._validate(self.batches/batch_id, expected_uids)
        return True

    def load(self, batch_id, expected_uids=None):
        safe_id(batch_id)
        require(batch_id in self.records, 'BATCH_NOT_COMMITTED')
        path = self.batches/batch_id
        record = self._validate(path, expected_uids)
        return dict(batch_id=batch_id, uids=list(record['uids']),
                    rows=read_json(path/'rows.json'),
                    e3=np.load(path/'E3.npy', allow_pickle=False),
                    q14=np.load(path/'q14.npy', allow_pickle=False), manifest=record)

    def commit(self, batch_id, uids, e3, q14, rows=None, failpoint=None):
        safe_id(batch_id)
        uids = check_uids(uids)
        require(len(uids) <= self.max_rows, 'BATCH_ROW_BOUND')
        for array, width in ((e3, 768), (q14, 14)):
            require(type(array) is np.ndarray and array.dtype == np.dtype('<f4')
                    and array.shape == (len(uids), width) and np.isfinite(array).all(),
                    'BATCH_INPUT_ARRAY_SCHEMA')
        rows = [{'uid': uid} for uid in uids] if rows is None else rows
        require(type(rows) is list and len(rows) == len(uids)
                and all(type(row) is dict and row.get('uid') == uid
                        for row, uid in zip(rows, uids)), 'BATCH_INPUT_ROWS')
        rows_bytes = canonical(rows)
        if self.has(batch_id, uids):
            old = self.load(batch_id, uids)
            require(old['e3'].tobytes() == np.ascontiguousarray(e3).tobytes()
                    and old['q14'].tobytes() == np.ascontiguousarray(q14).tobytes()
                    and canonical(old['rows']) == rows_bytes, 'BATCH_RECOMPUTED_BYTES_CHANGED')
            return old['manifest']
        require(not (self.root/'COMPLETE.json').exists(), 'BATCH_STORE_ALREADY_FINISHED')
        require(not set(uids) & set(self.uid_owner), 'BATCH_CROSS_BATCH_UID_OVERLAP')
        attempt = self.pending/(batch_id+'.'+uuid.uuid4().hex)
        attempt.mkdir(exist_ok=False)
        atomic_json(attempt/'OWNERSHIP.json', dict(binding_sha256=self.binding_sha256,
                                                   batch_id=batch_id))
        for name, value in (('E3', e3), ('q14', q14)):
            with (attempt/(name+'.npy')).open('xb') as out:
                np.save(out, np.ascontiguousarray(value), allow_pickle=False)
                out.flush()
                os.fsync(out.fileno())
        write_bytes(attempt/'uids.json', canonical(uids))
        write_bytes(attempt/'rows.json', rows_bytes)
        if failpoint:
            failpoint('after_payload')
        record = dict(schema=SCHEMA, status='COMMITTED', batch_id=batch_id,
            binding_sha256=self.binding_sha256, rows=len(uids), uids=uids,
            arrays={'E3': dict(dtype='<f4', shape=[len(uids), 768]),
                    'q14': dict(dtype='<f4', shape=[len(uids), 14])},
            files={name: self._pin(attempt/name)
                   for name in ('E3.npy', 'q14.npy', 'uids.json', 'rows.json')})
        write_bytes(attempt/'MANIFEST.json', canonical(record))
        fsync_directory(attempt)
        if failpoint:
            failpoint('after_manifest')
        os.rename(attempt, self.batches/batch_id)
        fsync_directory(self.batches)
        if failpoint:
            failpoint('after_commit')
        self.records[batch_id] = self._validate(self.batches/batch_id, uids)
        self.uid_owner.update({uid: batch_id for uid in uids})
        self._ledger()
        if failpoint:
            failpoint('after_ledger')
        return record

    def finish(self, expected_batches):
        expected = [(safe_id(name), check_uids(uids)) for name, uids in expected_batches]
        require(len(expected) == len({name for name, _ in expected}), 'BATCH_DUPLICATE_EXPECTED_ID')
        require(set(self.records) == {name for name, _ in expected}, 'BATCH_FINAL_EXACT_COVERAGE')
        all_uids = [uid for _, uids in expected for uid in uids]
        require(len(all_uids) == len(set(all_uids)), 'BATCH_FINAL_DUPLICATE_UID')
        for name, uids in expected:
            require(self.has(name, uids), 'BATCH_FINAL_MISSING')
        value = dict(schema=SCHEMA, status='COMPLETE', binding_sha256=self.binding_sha256,
            batches=[dict(batch_id=name, uids=uids,
                          manifest_sha256=sha(self.batches/name/'MANIFEST.json'))
                     for name, uids in expected],
            ordered_uids_sha256=hashlib.sha256(canonical(all_uids)).hexdigest(),
            rows=len(all_uids))
        target = self.root/'COMPLETE.json'
        if target.exists():
            require(read_json(target) == value, 'BATCH_FINAL_ORDER_CHANGED')
        else:
            atomic_json(target, value)
        return value


class RoleSpool:
    """Snapshot inputs become reusable only after full role reconstruction.

    The caller must call complete() only after the original numerical context
    generator exhausted and its final raw identity check passed. Merely having
    saved all selected snapshots does not establish that contract.
    """
    def __init__(self, root, binding, role, expected_uids):
        self.role = safe_id(role)
        self.expected = check_uids(expected_uids)
        self.expected_set = set(self.expected)
        self.root, self.binding_sha256 = bind_directory(root, dict(
            schema='EDGE_COMPLETE_ROLE_SNAPSHOT_SPOOL_V1', identity=binding,
            role=role, ordered_expected_uids=self.expected))
        self.attempt = None
        self.entries = []
        self.by_uid = {}

    def _read_complete(self):
        path = self.root/'COMPLETE.json'
        if not path.exists():
            return None
        value = read_json(path)
        require(value.get('binding_sha256') == self.binding_sha256
                and value.get('generator_exhausted') is True
                and value.get('raw_final_identity_pass') is True
                and value.get('uids') == self.expected, 'ROLE_COMPLETE_BINDING')
        require(safe_id(value['attempt']) == value['attempt'], 'ROLE_ATTEMPT_PATH')
        entries = value['entries']
        require([entry['uid'] for entry in entries] == self.expected, 'ROLE_COMPLETE_UID_ORDER')
        for entry in entries:
            self._load(value['attempt'], entry)
        return value

    def is_complete(self):
        return self._read_complete() is not None

    def append(self, snapshot):
        require(not (self.root/'COMPLETE.json').exists(), 'ROLE_ALREADY_COMPLETE')
        primitive(snapshot)
        require(type(snapshot) is dict and type(snapshot.get('row')) is dict,
                'ROLE_SNAPSHOT_SCHEMA')
        uid = snapshot.get('uid')
        require(uid in self.expected_set and snapshot['row'].get('uid') == uid,
                'ROLE_SNAPSHOT_UID')
        require(uid not in self.by_uid, 'ROLE_DUPLICATE_UID')
        if self.attempt is None:
            self.attempt = self.root/('attempt-'+uuid.uuid4().hex)
            self.attempt.mkdir(exist_ok=False)
        payload = pickle.dumps(snapshot, protocol=5)
        require(0 < len(payload) <= MAX_SNAPSHOT_BYTES, 'ROLE_SNAPSHOT_SIZE')
        name = '%08d.pickle' % len(self.entries)
        write_bytes(self.attempt/name, payload)
        entry = dict(uid=uid, file=name, bytes=len(payload),
                     sha256=hashlib.sha256(payload).hexdigest())
        self.entries.append(entry)
        self.by_uid[uid] = entry
        atomic_json(self.attempt/'PARTIAL.json', dict(binding_sha256=self.binding_sha256,
            persisted_count=len(self.entries), last_snapshot=entry,
            partial_role_reusable=False))
        return entry

    def complete(self, *, generator_exhausted=False, raw_final_identity_pass=False):
        require(generator_exhausted is True and raw_final_identity_pass is True,
                'ROLE_ORIGINAL_GENERATOR_AND_FINAL_RAW_REQUIRED')
        previous = self._read_complete()
        if previous is not None:
            return previous
        require(self.attempt is not None and set(self.by_uid) == self.expected_set,
                'ROLE_COMPLETE_EXACT_UID_COVERAGE')
        entries = [self.by_uid[uid] for uid in self.expected]
        value = dict(binding_sha256=self.binding_sha256, role=self.role,
            attempt=self.attempt.name, uids=self.expected, entries=entries,
            generator_exhausted=True, raw_final_identity_pass=True)
        for entry in entries:
            self._load(self.attempt.name, entry)
        fsync_directory(self.attempt)
        atomic_json(self.root/'COMPLETE.json', value)
        return value

    def _load(self, attempt, entry):
        require(re.fullmatch(r'\d{8}\.pickle', entry['file']) is not None,
                'ROLE_SNAPSHOT_PATH')
        path = self.root/attempt/entry['file']
        require(path.is_file() and not path.is_symlink()
                and 0 < path.stat().st_size <= MAX_SNAPSHOT_BYTES
                and path.stat().st_size == entry['bytes']
                and sha(path) == entry['sha256'], 'ROLE_SNAPSHOT_SHA_SIZE')
        value = PrimitiveUnpickler(io.BytesIO(path.read_bytes())).load()
        primitive(value)
        require(type(value) is dict and value.get('uid') == entry['uid']
                and type(value.get('row')) is dict
                and value['row'].get('uid') == entry['uid'], 'ROLE_SNAPSHOT_UID')
        return value

    def load_complete(self):
        value = self._read_complete()
        require(value is not None, 'ROLE_INCOMPLETE_CANNOT_ENCODE')
        for entry in value['entries']:
            yield self._load(value['attempt'], entry)

    def discard_partial(self):
        """Only remove this instance's uncommitted attempt, never old evidence."""
        if self.attempt is not None and not (self.root/'COMPLETE.json').exists():
            require(self.attempt.parent == self.root and not self.attempt.is_symlink(),
                    'ROLE_PARTIAL_CLEANUP_SCOPE')
            shutil.rmtree(self.attempt)
            self.attempt = None
            self.entries, self.by_uid = [], {}


class PackedRoleSpool:
    """Bounded snapshot chunks with a complete-role-only scientific index.

    At most 128 serialized snapshots / 64 MiB are buffered. A restarted process
    verifies each committed chunk once, caches only its lightweight index, and
    loads individual snapshot bodies on demand. Incomplete attempts never
    supply headers or model inputs, even if all expected UIDs were appended.
    """
    def __init__(self, root, binding, role, expected_uids, *, chunk_rows=128,
                 chunk_bytes=64*1024**2, failpoint=None):
        self.role = safe_id(role)
        self.expected = check_uids(expected_uids)
        self.expected_set = set(self.expected)
        require(type(chunk_rows) is int and 1 <= chunk_rows <= 128
                and type(chunk_bytes) is int and 1024 <= chunk_bytes <= 64*1024**2,
                'PACKED_CHUNK_BOUNDS')
        self.chunk_rows, self.chunk_bytes = chunk_rows, chunk_bytes
        self.root, self.binding_sha256 = bind_directory(root, dict(
            schema='EDGE_PACKED_COMPLETE_ROLE_V1', identity=binding, role=role,
            expected_uids=self.expected, chunk_rows=chunk_rows, chunk_bytes=chunk_bytes))
        self.attempt = None
        self.failpoint = failpoint
        self.buffer, self.buffer_bytes = [], 0
        self.seen, self.chunk_records = set(), []
        self._complete, self._index, self._chunk_paths = None, None, None

    def _fail(self, name):
        if self.failpoint is not None:
            self.failpoint(name)

    @staticmethod
    def _header(snapshot):
        require(type(snapshot) is dict and type(snapshot.get('row')) is dict
                and type(snapshot.get('body')) is dict, 'PACKED_SNAPSHOT_SCHEMA')
        uid, row = snapshot.get('uid'), snapshot['row']
        require(type(uid) is str and row.get('uid') == uid, 'PACKED_SNAPSHOT_UID')
        flow = snapshot['body'].get('flow')
        require(type(flow) is dict and flow.get('protocol') in (6, 17), 'PACKED_FLOW_PROTOCOL')
        counts = flow.get('counts')
        require(type(counts) is list and 1 <= len(counts) <= 12
                and all(type(n) is int and 1 <= n <= 6 for n in counts), 'PACKED_FLOW_COUNTS')
        protocol = flow['protocol']
        require(row.get('protocol') == protocol, 'PACKED_ROW_FLOW_PROTOCOL')
        q14 = snapshot.get('q14')
        require(type(q14) is list and len(q14) == 14
                and all(type(n) in (int, float) and math.isfinite(n) for n in q14),
                'PACKED_Q14')
        return dict(uid=uid, row=row, q14=q14,
                    shape=[protocol, max(counts)*(12 if protocol == 6 else 6)+1, len(counts)])

    def append(self, snapshot):
        require(not (self.root/'COMPLETE.json').exists(), 'PACKED_ROLE_ALREADY_COMPLETE')
        primitive(snapshot)
        header = self._header(snapshot)
        uid = header['uid']
        require(uid in self.expected_set and uid not in self.seen, 'PACKED_UID_COVERAGE_OR_DUPLICATE')
        payload = pickle.dumps(snapshot, protocol=5)
        require(0 < len(payload) <= MAX_SNAPSHOT_BYTES, 'PACKED_SNAPSHOT_SIZE')
        require(len(payload)+8 <= self.chunk_bytes, 'PACKED_SNAPSHOT_EXCEEDS_CHUNK')
        if self.buffer and (len(self.buffer) >= self.chunk_rows or
                            self.buffer_bytes+len(payload)+8 > self.chunk_bytes):
            self._flush()
        self.buffer.append((header, payload))
        self.buffer_bytes += len(payload)+8
        self.seen.add(uid)
        if len(self.buffer) >= self.chunk_rows or self.buffer_bytes >= self.chunk_bytes:
            self._flush()

    def _flush(self):
        if not self.buffer:
            return
        if self.attempt is None:
            self.attempt = self.root/('attempt-'+uuid.uuid4().hex)
            self.attempt.mkdir(exist_ok=False)
        name = 'chunk-%06d' % len(self.chunk_records)
        staging = self.attempt/('.'+name+'.'+uuid.uuid4().hex+'.partial')
        staging.mkdir(exist_ok=False)
        entries, offset = [], 0
        data_path = staging/'snapshots.bin'
        with data_path.open('xb') as stream:
            for header, payload in self.buffer:
                stream.write(struct.pack('<Q', len(payload)))
                stream.write(payload)
                entries.append(dict(uid=header['uid'], offset=offset+8, bytes=len(payload),
                                    sha256=hashlib.sha256(payload).hexdigest(), header=header))
                offset += len(payload)+8
            stream.flush()
            os.fsync(stream.fileno())
        write_bytes(staging/'INDEX.json', canonical(entries))
        self._fail('after_chunk_payload')
        record = dict(name=name, rows=len(entries),
            data=dict(bytes=data_path.stat().st_size, sha256=sha(data_path)),
            index=dict(bytes=(staging/'INDEX.json').stat().st_size,
                       sha256=sha(staging/'INDEX.json')))
        write_bytes(staging/'CHUNK.json', canonical(record))
        fsync_directory(staging)
        os.rename(staging, self.attempt/name)
        fsync_directory(self.attempt)
        self.chunk_records.append(record)
        self.buffer, self.buffer_bytes = [], 0
        self._fail('after_chunk_commit')

    def _ensure_complete(self):
        if self._complete is not None:
            return self._complete
        path = self.root/'COMPLETE.json'
        require(path.exists(), 'PACKED_ROLE_INCOMPLETE_CANNOT_ENCODE')
        value = read_json(path)
        require(value.get('schema') == 'EDGE_PACKED_COMPLETE_ROLE_V1'
                and value.get('binding_sha256') == self.binding_sha256
                and value.get('generator_exhausted') is True
                and value.get('raw_final_identity_pass') is True
                and value.get('uids') == self.expected, 'PACKED_COMPLETE_BINDING')
        safe_id(value['attempt'])
        attempt = self.root/value['attempt']
        require(attempt.is_dir() and not attempt.is_symlink(), 'PACKED_ATTEMPT_DIRECTORY')
        index, chunks = {}, {}
        records = value.get('chunks')
        require(type(records) is list and len(records) > 0, 'PACKED_COMPLETE_CHUNKS')
        for ordinal, record in enumerate(records):
            name = 'chunk-%06d' % ordinal
            require(record.get('name') == name and 1 <= record.get('rows', 0) <= self.chunk_rows,
                    'PACKED_CHUNK_ID_ROWS')
            folder = attempt/name
            require(folder.is_dir() and not folder.is_symlink(), 'PACKED_CHUNK_DIRECTORY')
            require(read_json(folder/'CHUNK.json') == record, 'PACKED_CHUNK_MANIFEST')
            for file, pin, limit in [('snapshots.bin', record['data'], self.chunk_bytes),
                                     ('INDEX.json', record['index'], MAX_JSON_BYTES)]:
                target = folder/file
                require(target.is_file() and not target.is_symlink()
                        and 0 < target.stat().st_size <= limit
                        and target.stat().st_size == pin['bytes']
                        and sha(target) == pin['sha256'], 'PACKED_CHUNK_SHA_SIZE:' + file)
            entries = read_json(folder/'INDEX.json')
            require(type(entries) is list and len(entries) == record['rows'], 'PACKED_INDEX_ROWS')
            offset = 0
            with (folder/'snapshots.bin').open('rb') as stream:
                for entry in entries:
                    require(entry.get('offset') == offset+8 and type(entry.get('bytes')) is int
                            and 0 < entry['bytes'] <= MAX_SNAPSHOT_BYTES,
                            'PACKED_INDEX_RECORD_BOUNDS')
                    stream.seek(offset)
                    size = stream.read(8)
                    require(len(size) == 8 and struct.unpack('<Q', size)[0] == entry['bytes'],
                            'PACKED_RECORD_LENGTH')
                    offset += entry['bytes']+8
                    require(offset <= record['data']['bytes'], 'PACKED_RECORD_OVERFLOW')
                    uid, header = entry.get('uid'), entry.get('header')
                    require(uid in self.expected_set and uid not in index and type(header) is dict
                            and header.get('uid') == uid and type(header.get('row')) is dict
                            and header['row'].get('uid') == uid
                            and type(header.get('q14')) is list and len(header['q14']) == 14
                            and type(header.get('shape')) is list and len(header['shape']) == 3,
                            'PACKED_INDEX_UID_HEADER')
                    index[uid] = dict(entry, chunk=name)
            require(offset == record['data']['bytes'], 'PACKED_CHUNK_TRAILING_BYTES')
            chunks[name] = folder/'snapshots.bin'
        require(set(index) == self.expected_set and len(index) == len(self.expected),
                'PACKED_COMPLETE_EXACT_UID_COVERAGE')
        self._complete, self._index, self._chunk_paths = value, index, chunks
        return value

    def is_complete(self):
        if not (self.root/'COMPLETE.json').exists():
            return False
        self._ensure_complete()
        return True

    def complete(self, *, generator_exhausted=False, raw_final_identity_pass=False):
        require(generator_exhausted is True and raw_final_identity_pass is True,
                'PACKED_ORIGINAL_GENERATOR_AND_FINAL_RAW_REQUIRED')
        if (self.root/'COMPLETE.json').exists():
            return self._ensure_complete()
        require(self.seen == self.expected_set, 'PACKED_COMPLETE_EXACT_UID_COVERAGE')
        self._flush()
        require(self.attempt is not None, 'PACKED_EMPTY_ROLE')
        value = dict(schema='EDGE_PACKED_COMPLETE_ROLE_V1', binding_sha256=self.binding_sha256,
            role=self.role, attempt=self.attempt.name, uids=self.expected,
            chunks=self.chunk_records, generator_exhausted=True, raw_final_identity_pass=True)
        self._fail('before_complete')
        atomic_json(self.root/'COMPLETE.json', value)
        self._fail('after_complete')
        return self._ensure_complete()

    def headers(self):
        self._ensure_complete()
        # Return a detached JSON header; caller mutation cannot alter our index.
        for uid in self.expected:
            yield json.loads(canonical(self._index[uid]['header']))

    def load(self, uid):
        self._ensure_complete()
        require(uid in self._index, 'PACKED_LOAD_UNKNOWN_UID')
        entry = self._index[uid]
        path = self._chunk_paths[entry['chunk']]
        with path.open('rb') as stream:
            stream.seek(entry['offset'])
            payload = stream.read(entry['bytes'])
        require(len(payload) == entry['bytes']
                and hashlib.sha256(payload).hexdigest() == entry['sha256'], 'PACKED_SNAPSHOT_SHA_SIZE')
        snapshot = PrimitiveUnpickler(io.BytesIO(payload)).load()
        primitive(snapshot)
        require(canonical(self._header(snapshot)) == canonical(entry['header']),
                'PACKED_LOADED_HEADER_IDENTITY')
        return snapshot

    def load_complete(self):
        self._ensure_complete()
        for uid in self.expected:
            yield self.load(uid)
