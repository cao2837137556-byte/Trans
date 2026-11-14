"""Create the raw-order Motion index and its stable UTC chronological permutation."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import struct

import numpy as np

from hnr.history import _block, role_binding
from motion_ingress import ARCHIVE_BYTES, ARCHIVE_SHA, RAW_SHA, digest
from frozen_selector import need

INDEX_DTYPE = np.dtype([
    ('timestamp_us', '<i8'), ('block_offset', '<u8'),
    ('original_packet_ordinal', '<u4'), ('captured_bytes', '<u4'),
    ('wire_bytes', '<u4'), ('interface_id', '<u4'),
])


def ethernet_microsecond_interface(block, endian):
    need(struct.unpack_from(endian+'H', block, 8)[0] == 1, 'MOTION_ETHERNET_REQUIRED')
    pos = 16
    resolution = 6
    offset = 0
    while pos+4 <= len(block)-4:
        code, length = struct.unpack_from(endian+'HH', block, pos)
        pos += 4
        need(pos+length <= len(block)-4, 'MOTION_IDB_OPTION_BOUNDS')
        value = block[pos:pos+length]
        pos += (length+3)//4*4
        if code == 0:
            break
        if code == 9:
            need(length == 1, 'MOTION_IDB_TSRESOL')
            resolution = value[0]
        if code == 14:
            need(length == 8, 'MOTION_IDB_TSOFFSET')
            offset = struct.unpack(endian+'q', value)[0]
    need(resolution == 6 and offset == 0, 'MOTION_IDB_FROZEN_CLOCK')


def build(archive, folder, witness, progress):
    archive = Path(archive)
    need(archive.stat().st_size == ARCHIVE_BYTES and digest(archive) == ARCHIVE_SHA,
         'MOTION_COMPRESSED_INPUT_PIN')
    folder.mkdir(parents=True, exist_ok=False)
    raw = folder / 'BelkinWemoMotionSensor_ec1a59832811.pcap'
    with gzip.open(archive, 'rb') as source, raw.open('xb') as output:
        shutil.copyfileobj(source, output, length=8*1024**2)
    need(raw.stat().st_size == witness['raw_bytes'], 'MOTION_RAW_SIZE')
    index_path = folder / 'packet_index.npy'
    index = np.lib.format.open_memmap(index_path, mode='w+', dtype=INDEX_DTYPE,
                                     shape=(witness['packets'],), version=(1,0))
    sha = hashlib.sha256()
    i = 0
    with raw.open('rb') as stream:
        kind, block, endian = _block(stream)
        need(kind == 0x0a0d0d0a, 'MOTION_PCAPNG_SECTION')
        sha.update(block)
        kind, block, _ = _block(stream, endian)
        need(kind == 1, 'MOTION_PCAPNG_INTERFACE')
        ethernet_microsecond_interface(block, endian)
        sha.update(block)
        while stream.tell() < witness['raw_bytes']:
            where = stream.tell()
            kind, block, _ = _block(stream, endian)
            sha.update(block)
            need(kind not in (0x0a0d0d0a, 1, 2, 3), 'MOTION_UNSUPPORTED_PCAPNG_LAYOUT')
            if kind != 6:
                continue
            iface, hi, lo, cap, wire = struct.unpack_from(endian+'IIIII', block, 8)
            need(iface == 0 and cap <= wire and 28+cap <= len(block)-4 and i < len(index),
                 'MOTION_EPB_SCHEMA')
            index[i] = (hi << 32 | lo, where, i+1, cap, wire, iface)
            i += 1
            if i % 65536 == 0:
                progress('MOTION_INDEX', i, len(index))
        need(stream.tell() == witness['raw_bytes'], 'MOTION_RAW_TRAILER')
    need(i == len(index) and sha.hexdigest() == witness['raw_sha256'] == RAW_SHA,
         'MOTION_COMPLETE_RAW_IDENTITY')
    times = index['timestamp_us']
    need(int(np.count_nonzero(times[1:] < times[:-1])) == witness['backward_steps'], 'MOTION_RAW_ORDER')
    order = np.argsort(times, kind='stable').astype('<i8', copy=False)
    order_path = folder / 'chronological_order.npy'
    with order_path.open('xb') as stream:
        np.save(stream, order, allow_pickle=False)
    binding = role_binding(index, order, witness)
    for name in ('observed_utc_dates', 'ref_dates', 'dev_dates', 'first_dev_frame'):
        need(binding[name] == witness[name], 'MOTION_ROLE_WITNESS:' + name)
    index.flush()
    del times, index
    pins = {
        'raw': dict(path=str(raw), sha256=RAW_SHA, bytes=witness['raw_bytes']),
        'packet_index': dict(path=str(index_path), sha256=digest(index_path)),
        'chronological_order': dict(path=str(order_path), sha256=digest(order_path)),
    }
    (folder / 'ROLE_BINDING.json').write_text(json.dumps(dict(binding, assets=pins), indent=2)+'\n')
    progress('MOTION_INDEX', i, i)
    return pins
