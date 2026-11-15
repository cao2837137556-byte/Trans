"""Reference-only primitives for the acfe0a1 single-wave K8192 selection."""
import hashlib
import heapq
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

CAP = 8192
SALT = 'C4_HISTORY_SAMPLE_COVERAGE_V1_20261101'
FORBIDDEN = frozenset(('score','scores','logits','support','prediction','predictions',
                       'is_fp','query_uid','nearest_query','nearest_distance'))
RAW_SHA = re.compile(r'[0-9a-f]{64}\Z')
MAC = re.compile(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}\Z')


def need(ok, error):
    if not ok:
        raise ValueError(error)


def physical(row):
    raw, ordinal, owner = (row[k] for k in ('origin_raw_sha256','origin_packet_ordinal','owner'))
    need(isinstance(raw,str) and RAW_SHA.fullmatch(raw), 'RAW_SHA')
    need(type(ordinal) is int and ordinal > 0, 'ORIGINAL_ORDINAL')
    need(isinstance(owner,str) and MAC.fullmatch(owner), 'OWNER')
    return raw, ordinal, owner


def rank(origin):
    payload=json.dumps([SALT,*origin],separators=(',',':'),ensure_ascii=True).encode('ascii')
    return int.from_bytes(hashlib.sha256(payload).digest(),'big')


def verify_snapshot_row(row, entry):
    # The census round-trips through JSON; RECENT still returns nested tuples.
    def canonical(value):
        return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                          allow_nan=False)
    need(entry['uid'] == row['uid'] and canonical(entry['row']) == canonical(row),
         'SEALED_SNAPSHOT_ROW_JOIN:' + row['uid'])


def validate_row(row, sources):
    need(not FORBIDDEN.intersection(row), 'TARGET_FEEDBACK_FIELD')
    need(row.get('use')=='REFERENCE' and type(row.get('label')) is int and row['label']==0 and
         row.get('history_role')=='HIST_REF', 'NORMAL_HIST_REF_ONLY')
    raw, ordinal, owner = origin = physical(row)
    key = row['device'],raw,owner,row['capture_id']
    need(key in sources, 'UNADMITTED_SOURCE')
    source = sources[key]
    need(row['partition']==source['partition'] and row['protocol'] in (6,17), 'REFERENCE_SCOPE')
    need(type(row['timestamp_us']) is int and row['timestamp_us'] <= source['reference_end_us'] and
         type(row['frame']) is int and 0 < row['frame'] <= source['bank_end_frame'] and
         ordinal <= source['raw_packet_count'] and row['reference_end_us']==source['reference_end_us'] and
         row['bank_end_frame']==source['bank_end_frame'], 'FROZEN_HIST_REF_TIME_AND_FRAME')
    need(RAW_SHA.fullmatch(row['uid']) and RAW_SHA.fullmatch(row['component_id']), 'REFERENCE_IDS')
    return origin


def select(candidates, sources, index_path, *, old_rows=(), cap=CAP):
    """One selection from complete census iterators; SQLite indexes all origins and ranks."""
    need(not old_rows and type(cap) is int and cap==CAP, 'FROZEN_SINGLE_WAVE_CAP_OR_OLD_PRIORITY')
    index_path=Path(index_path)
    with index_path.open('xb'):
        pass
    db = sqlite3.connect(index_path)
    heaps=defaultdict(list)
    totals=Counter()
    try:
        db.execute('CREATE TABLE seen (raw TEXT, ordinal INTEGER, owner TEXT, uid TEXT UNIQUE, '
                   'digest BLOB UNIQUE, body TEXT, PRIMARY KEY(raw,ordinal,owner)) WITHOUT ROWID')
        for row in candidates:
            origin=validate_row(row,sources)
            body=json.dumps(row,sort_keys=True,separators=(',',':'),ensure_ascii=True,allow_nan=False)
            key=row['device'],row['protocol']
            digest=rank(origin)
            try:
                db.execute('INSERT INTO seen VALUES (?,?,?,?,?,?)',
                           (*origin,row['uid'],digest.to_bytes(32,'big'),body))
            except sqlite3.IntegrityError:
                old=db.execute('SELECT body FROM seen WHERE raw=? AND ordinal=? AND owner=?',origin).fetchone()
                need(old is not None and old[0]==body,'PHYSICAL_ID_UID_OR_HASH_CONFLICT')
                continue
            totals[key]+=1
            heap=heaps[key]
            entry=(-digest,dict(row))
            if len(heap)<cap:
                heapq.heappush(heap,entry)
            elif entry[0]>heap[0][0]:
                heapq.heapreplace(heap,entry)
        db.commit()
    finally:
        db.close()
    return sorted((row for group in heaps.values() for _,row in group),key=lambda x:x['uid']), dict(totals)


def from_census(path, expected_counts):
    """Read a byte-verified old census; count both roles and yield only HIST_REF."""
    db=sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        counts=dict(db.execute('SELECT role,count(*) FROM candidates GROUP BY role'))
        need(counts==expected_counts,'COMPLETE_CENSUS_ROLE_COUNTS')
        sql=('SELECT c.uid,c.device,c.protocol,c.component_id,c.timestamp,c.frame,c.role,c.body,'
             'p.raw_sha,p.ordinal,p.owner FROM candidates c LEFT JOIN physical_origins p ON c.uid=p.uid '
             'WHERE c.role=?')
        for uid,device,proto,component,timestamp,frame,role,body,raw,ordinal,owner in db.execute(sql,('HIST_REF',)):
            row=json.loads(body)
            need([row[k] for k in ('uid','device','protocol','component_id','timestamp','frame','history_role')]
                 ==[uid,device,proto,component,timestamp,frame,role] and
                 physical(row)==(raw,ordinal,owner), 'CENSUS_METADATA_JOIN')
            yield row
    finally:
        db.close()


def scan_census(path, expected_counts, *, raw_sha, owner, max_ordinal, progress=None):
    """Join two table scans with an in-memory ordinal index, without SQLite point lookups."""
    import numpy as np

    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        db.execute('PRAGMA cache_size=-32768')
        all_rows, refs, dev = db.execute(
            "SELECT count(*), count(CASE WHEN role='HIST_REF' THEN 1 END), "
            "count(CASE WHEN role='HIST_DEV' THEN 1 END) FROM candidates NOT INDEXED"
        ).fetchone()
        counts = {k:n for k,n in (('HIST_REF', refs), ('HIST_DEV', dev)) if n}
        need(counts == expected_counts and all_rows == refs+dev, 'COMPLETE_CENSUS_ROLE_COUNTS')
        present = bytearray(max_ordinal+1)
        by_ordinal = np.empty(max_ordinal+1, dtype='V32')
        count = 0
        for raw, ordinal, mac, uid in db.execute(
            'SELECT raw_sha,ordinal,owner,uid FROM physical_origins NOT INDEXED'
        ):
            need(raw == raw_sha and mac == owner and type(ordinal) is int and 0 < ordinal <= max_ordinal
                 and not present[ordinal] and RAW_SHA.fullmatch(uid), 'CENSUS_ORDINAL_MAP')
            present[ordinal] = 1
            by_ordinal[ordinal] = bytes.fromhex(uid)
            count += 1
            if progress is not None and count % 65536 == 0:
                progress(count, all_rows)
        need(count == all_rows, 'CENSUS_PHYSICAL_COUNT')
        if progress is not None:
            progress(count, all_rows)

        rows = db.execute('SELECT uid,device,protocol,component_id,timestamp,frame,role,body '
                          'FROM candidates NOT INDEXED WHERE role=?', ('HIST_REF',))
        seen = 0
        for uid,device,proto,component,timestamp,frame,role,body in rows:
            row = json.loads(body)
            raw, ordinal, mac = physical(row)
            need((raw, mac) == (raw_sha, owner) and ordinal <= max_ordinal and present[ordinal] == 1 and
                 bytes(by_ordinal[ordinal]) == bytes.fromhex(uid), 'CENSUS_ORDINAL_JOIN')
            need([row[k] for k in ('uid','device','protocol','component_id','timestamp','frame','history_role')]
                 == [uid,device,proto,component,timestamp,frame,role], 'CENSUS_METADATA_JOIN')
            present[ordinal] = 2
            seen += 1
            yield row
        need(seen == refs, 'CENSUS_STREAM_ROW_COUNT')
    finally:
        db.close()


def select_census_stream(candidates, sources, expected_rows, *, cap=CAP):
    """Select the same top-K from one verified complete census per disjoint raw source."""
    import numpy as np

    need(type(cap) is int and cap == CAP and type(expected_rows) is int and expected_rows > 0,
         'FROZEN_SINGLE_WAVE_CAP_OR_ROW_COUNT')
    need(len({key[1] for key in sources}) == len(sources), 'CENSUS_SOURCE_ORIGIN_OVERLAP')
    uids = np.empty(expected_rows, dtype='V32')
    digests = np.empty(expected_rows, dtype='V32')
    heaps = defaultdict(list)
    totals = Counter()
    count = 0
    for row in candidates:
        need(count < expected_rows, 'CENSUS_STREAM_ROW_COUNT')
        origin = validate_row(row, sources)
        value = rank(origin)
        uid = row['uid']
        uids[count] = bytes.fromhex(uid)
        digests[count] = value.to_bytes(32,'big')
        key = row['device'], row['protocol']
        totals[key] += 1
        heap = heaps[key]
        # count disambiguates an otherwise identical tuple; the full-array
        # equality checks below still reject either UID or digest duplicates.
        entry = (-value, count, row)
        if len(heap) < cap:
            heapq.heappush(heap, entry)
        elif entry[0] > heap[0][0]:
            heapq.heapreplace(heap, entry)
        count += 1
    need(count == expected_rows, 'CENSUS_STREAM_ROW_COUNT')
    for values in (uids, digests):
        values.sort()
        need(not np.any(values[1:] == values[:-1]), 'PHYSICAL_ID_UID_OR_HASH_CONFLICT')
    selected = sorted((row for heap in heaps.values() for _,_,row in heap), key=lambda row:row['uid'])
    return selected, dict(totals)
