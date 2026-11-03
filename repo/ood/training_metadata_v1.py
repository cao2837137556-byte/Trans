"""Lossless training-field projection, dictionary encoded and read-only mmap.

Full audit metadata stays in the original sealed JSONL. No features, weights,
labels or sample ordering are inferred or changed by this storage adapter.
"""
from collections.abc import Mapping, Sequence
import hashlib
import json
from pathlib import Path
import numpy as np
import continuous_common_v3 as c

SCHEMA = 'query-tail-training-metadata-v1'
FIELDS = ('uid', 'partition', 'fit_role', 'use', 'device', 'activity',
          'capture_id', 'session_id', 'component_id', 'label')


def projection(row):
    values = [row[field] for field in FIELDS]
    c.require(all(type(v) is str for v in values[:-1]) and type(values[-1]) is int
              and values[-1] in (0, 1), 'TRAINING_METADATA_TYPES')
    return values


def digest_row(digest, values):
    digest.update(json.dumps(values, ensure_ascii=True, separators=(',', ':'),
                             allow_nan=False).encode('utf-8')+b'\n')


def build(rows, output, count, source_sha256):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    c.require(type(count) is int and count > 0, 'METADATA_COUNT')
    codes = np.lib.format.open_memmap(out/'codes.npy', mode='w+', dtype='<u4',
                                     shape=(count, len(FIELDS)))
    vocabularies = [{} for _ in FIELDS[:-1]]
    digest = hashlib.sha256(); uid_digest = hashlib.sha256(); used = 0
    for i, row in enumerate(rows):
        c.require(i < count, 'METADATA_EXTRA_ROW')
        values = projection(row); digest_row(digest, values)
        uid_digest.update((values[0]+'\n').encode('utf-8'))
        for j, value in enumerate(values[:-1]):
            vocabulary = vocabularies[j]
            code = vocabulary.get(value)
            if code is None:
                code = len(vocabulary); vocabulary[value] = code
            codes[i, j] = code
        codes[i, -1] = values[-1]; used += 1
    c.require(used == count, 'METADATA_MISSING_ROW')
    codes.flush(); del codes
    c.require(len(vocabularies[0]) == count, 'METADATA_DUPLICATE_UID')
    sorted_uid_sha256 = c.uid_sha(vocabularies[0])
    columns = {}
    for field, vocabulary in zip(FIELDS[:-1], vocabularies):
        offsets = np.lib.format.open_memmap(out/(field+'.offsets.npy'), mode='w+',
                                            dtype='<u8', shape=(len(vocabulary)+1,))
        offset = 0; offsets[0] = 0
        with (out/(field+'.utf8')).open('xb') as stream:
            for i, value in enumerate(vocabulary):
                blob = value.encode('utf-8'); stream.write(blob); offset += len(blob)
                offsets[i+1] = offset
        offsets.flush(); del offsets
        columns[field] = dict(values=len(vocabulary), bytes=offset)
        vocabulary.clear()
    c.write(out/'receipt.json', dict(schema=SCHEMA, rows=count, fields=list(FIELDS),
            source_sha256=source_sha256, projection_sha256=digest.hexdigest(),
            uid_sha256=sorted_uid_sha256, ordered_uid_sha256=uid_digest.hexdigest(),
            columns=columns, read_only=True))
    c.seal(out); c.verify(out)
    return out


class Row(Mapping):
    __slots__ = ('table', 'index')

    def __init__(self, table, index):
        self.table, self.index = table, index

    def __getitem__(self, field):
        j = self.table.field_index[field]
        code = int(self.table.codes[self.index, j])
        if field == 'label':
            return code
        cache = self.table.small_vocab.get(field)
        if cache is not None:
            return cache[code]
        return self.table.decode(field, code)

    def __iter__(self):
        return iter(FIELDS)

    def __len__(self):
        return len(FIELDS)


class Rows(Sequence):
    def __init__(self, folder, *, expected_source_sha256, expected_uid_sha256=None):
        self.folder = Path(folder); c.verify(self.folder)
        self.receipt = receipt = c.read(self.folder/'receipt.json')
        c.require(receipt['schema'] == SCHEMA and receipt['fields'] == list(FIELDS) and
                  receipt['source_sha256'] == expected_source_sha256, 'METADATA_SOURCE_IDENTITY')
        if expected_uid_sha256 is not None:
            c.require(receipt['uid_sha256'] == expected_uid_sha256, 'METADATA_UID_IDENTITY')
        self.codes = np.load(self.folder/'codes.npy', mmap_mode='r', allow_pickle=False)
        c.require(self.codes.shape == (receipt['rows'], len(FIELDS)) and
                  self.codes.dtype == np.dtype('<u4'), 'METADATA_CODES_SCHEMA')
        self.field_index = {field:i for i, field in enumerate(FIELDS)}
        self.offsets, self.blobs, self.small_vocab = {}, {}, {}
        for j, field in enumerate(FIELDS[:-1]):
            spec = receipt['columns'][field]
            offsets = np.load(self.folder/(field+'.offsets.npy'), mmap_mode='r', allow_pickle=False)
            c.require(offsets.dtype == np.dtype('<u8') and offsets.shape == (spec['values']+1,) and
                      offsets[0] == 0 and offsets[-1] == spec['bytes'] and
                      np.all(offsets[1:] >= offsets[:-1]), 'METADATA_OFFSETS')
            self.offsets[field] = offsets
            self.blobs[field] = np.memmap(self.folder/(field+'.utf8'), mode='r', dtype='u1') if spec['bytes'] else b''
            c.require(len(self.blobs[field]) == spec['bytes'] and np.all(self.codes[:,j] < spec['values']), 'METADATA_CODES_RANGE')
            if spec['values'] <= 4096:
                self.small_vocab[field] = tuple(self.decode(field, i) for i in range(spec['values']))
        c.require(np.all(self.codes[:,-1] <= 1), 'METADATA_LABEL_RANGE')

    def decode(self, field, code):
        offsets = self.offsets[field]
        a, b = int(offsets[code]), int(offsets[code+1])
        return bytes(self.blobs[field][a:b]).decode('utf-8')

    def __len__(self):
        return len(self.codes)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [self[i] for i in range(*index.indices(len(self)))]
        index = int(index)
        if index < 0: index += len(self)
        if not 0 <= index < len(self): raise IndexError(index)
        return Row(self, index)

    def close(self):
        for array in [self.codes]+list(self.offsets.values())+list(self.blobs.values()):
            mapping = getattr(array, '_mmap', None)
            if mapping is not None: mapping.close()
        self.small_vocab.clear()


def verify_projection(rows):
    digest = hashlib.sha256()
    for row in rows: digest_row(digest, projection(row))
    c.require(digest.hexdigest() == rows.receipt['projection_sha256'], 'METADATA_PROJECTION_DRIFT')
    return digest.hexdigest()
