"""Optional exact-timestamp/packet-byte duplicate audit; not automatically run.

Generated SQLite is capped at <=120,000,000 bytes by max_page_count.
This is only useful after causal/7200-second gates survive. No model/network.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import tempfile
import time

from scan_raw import RawRecords, sha

HARD_DB_LIMIT = 120_000_000


def audit(raw, database, *, max_seconds=600, database_limit=HARD_DB_LIMIT):
    raw, database = Path(raw).resolve(), Path(database).resolve()
    if raw == database or database.exists():
        raise ValueError('database overlaps input or already exists; use a new audit database')
    if not 65536 <= database_limit <= HARD_DB_LIMIT:
        raise ValueError('database bound must be 65536..120000000 bytes')
    if not 0 < max_seconds <= 1800:
        raise ValueError('active audit bound must be <=1800s; caller must charge shared budget')
    started = time.monotonic()
    before_sha = sha(raw)
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database)
    conn.execute('PRAGMA page_size=4096')
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    conn.execute('PRAGMA temp_store=MEMORY')
    conn.execute('PRAGMA cache_size=-4096')
    max_pages = database_limit // 4096
    conn.execute(f'PRAGMA max_page_count={max_pages}')
    conn.execute('CREATE TABLE seen(ts INTEGER NOT NULL, digest BLOB NOT NULL, first_frame INTEGER NOT NULL, interface TEXT NOT NULL, PRIMARY KEY(ts,digest)) WITHOUT ROWID')
    conn.commit()
    records, duplicates, cross_interface, no_time = 0, 0, 0, 0
    examples = []
    error = None
    reader = RawRecords(raw)
    try:
        for frame, (ns, payload, caplen, wirelen, link, interface, snaplen) in enumerate(reader, 1):
            records += 1
            if ns is None:
                no_time += 1
                continue
            # Include linktype and caplen in the exact packet representation.
            digest = hashlib.sha256(struct.pack('!II', link, caplen) + payload).digest()
            cur = conn.execute('INSERT OR IGNORE INTO seen VALUES(?,?,?,?)', (ns, digest, frame, str(interface)))
            if cur.rowcount == 0:
                duplicates += 1
                first_frame, first_interface = conn.execute('SELECT first_frame,interface FROM seen WHERE ts=? AND digest=?', (ns, digest)).fetchone()
                cross_interface += int(str(interface) != first_interface)
                if len(examples) < 20:
                    examples.append({'first_frame': first_frame, 'duplicate_frame': frame,
                                     'timestamp_ns': ns, 'packet_sha256': digest.hex(),
                                     'first_interface': first_interface, 'duplicate_interface': str(interface)})
            if records % 10000 == 0:
                conn.commit()
                if time.monotonic() - started > max_seconds:
                    raise TimeoutError('active duplicate-audit seconds exhausted')
        conn.commit()
    except Exception as exc:
        error = f'{type(exc).__name__}: {exc}'
        try:
            conn.rollback()
        except sqlite3.Error:
            pass
    retained = conn.execute('SELECT COUNT(*) FROM seen').fetchone()[0]
    page_count = conn.execute('PRAGMA page_count').fetchone()[0]
    conn.close()
    after_sha = sha(raw)
    missing_precision = no_time > 0 or reader.meta.get('subnanosecond_records', 0) > 0
    complete = error is None and not missing_precision
    result = {'schema': 'EXACT_TIMESTAMP_PACKET_DUPLICATE_AUDIT_V1', 'input': str(raw),
              'input_sha256': before_sha, 'input_sha256_after': after_sha,
              'input_unchanged': before_sha == after_sha, 'records_processed': records,
              'complete': complete, 'error': error, 'records_without_timestamp': no_time,
              'subnanosecond_records': reader.meta.get('subnanosecond_records', 0),
              'duplicate_observations_in_processed_prefix': duplicates,
              'cross_interface_exact_duplicate_observations_in_prefix': cross_interface,
              'committed_unique_keys': retained, 'examples': examples,
              'database': str(database), 'database_bytes': database.stat().st_size,
              'database_page_count': page_count, 'database_max_pages': max_pages,
              'database_bound_bytes': database_limit, 'elapsed_seconds': time.monotonic() - started,
              'scope': 'Exact integer timestamp + same linktype, caplen and captured packet bytes; interfaces intentionally ignored in duplicate key.',
              'limits': ['Repeated payload at different timestamps is not called a duplicate.',
                         'Clock-shifted mirrored packets are not detected.',
                         'This does not prove raw-file provenance or persistent device identity.',
                         'Partial/error audits must not be claimed as whole-file duplicate counts.',
                         'SQLite generated audit is disposable and not intended as a resumable scientific asset.']}
    assert result['database_bytes'] <= database_limit
    return result


def self_test():
    with tempfile.TemporaryDirectory(prefix='dup_selftest_', dir=Path(__file__).resolve().parent) as d:
        d = Path(d)
        p = d / 'fixture.pcap'
        payload = b'abcde'
        with p.open('wb') as f:
            f.write(b'\xd4\xc3\xb2\xa1' + struct.pack('<HHiIII', 2, 4, 0, 0, 65535, 1))
            for sec in (1000, 1000, 1001):
                f.write(struct.pack('<IIII', sec, 0, len(payload), len(payload)) + payload)
        r = audit(p, d / 'seen.sqlite', database_limit=65536)
        assert r['complete'] and r['records_processed'] == 3
        assert r['duplicate_observations_in_processed_prefix'] == 1 and r['committed_unique_keys'] == 2
        assert r['input_unchanged'] and r['database_bytes'] <= 65536
    return {'status': 'PASS', 'checks': ['same-time identical bytes duplicate', 'different-time repeated bytes retained', 'strict page cap', 'input unchanged']}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path)
    p.add_argument('--database', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--max-seconds', type=float, default=600)
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        print(json.dumps(self_test()))
        return
    if not all((args.input, args.database, args.output)):
        p.error('--input --database --output required')
    if args.output.resolve() in (args.input.resolve(), args.database.resolve()):
        p.error('output overlaps raw input or database')
    r = audit(args.input, args.database, max_seconds=args.max_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(r, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'complete': r['complete'], 'records': r['records_processed'], 'error': r['error'], 'database_bytes': r['database_bytes']}))
    if not r['complete'] or not r['input_unchanged']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
