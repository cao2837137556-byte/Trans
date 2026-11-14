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
