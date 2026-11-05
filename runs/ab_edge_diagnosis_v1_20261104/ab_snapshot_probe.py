"""Score-independent existing A/B snapshot slices, read-only SQLite, q14 replay."""
from pathlib import Path
import collections,gzip,hashlib,json,math,sqlite3
import numpy as np
from diagnose import read,sha,pin,write
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=read(ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
database=ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/spool/snapshots.sqlite'
con=sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)
result={}
for pool in ('CIC_DEV','UNSW_DEV'):
    asset=spec['pools'][pool]['query'];path=pin(ROOT/asset['rows']['path'],asset['rows']['sha256'])
    with gzip.open(path,'rt',encoding='utf-8') as stream:rows=[json.loads(line) for line in stream]
    qs=np.load(pin(ROOT/asset['q14']['path'],asset['q14']['sha256']),mmap_mode='r',allow_pickle=False)
    for label in (0,1):
        for proto in (6,17):
            take=sorted((r['uid'],i,r) for i,r in enumerate(rows) if r['label']==label and r['protocol']==proto)[:128]
            bodies=[]
            for uid,i,row in take:
                body=json.loads(con.execute('SELECT body FROM snapshots WHERE uid=?',(uid,)).fetchone()[0])
                p=body['provenance'];assert p['query_frame']==row['frame'] and p['namespace_sha256']==row['session_id']
                matches=[(h,body['flow']['directions'][j]) for j,b in enumerate(p['bursts']) for frame,h in zip(b['frames'],b['headers']) if frame==row['frame']]
                assert len(matches)==1;h,direction=matches[0];flags=h[5] if proto==6 else 0
                q=[float(proto==6)]+[float(bool(flags&(1<<b))) for b in range(9)]
                q += [math.log1p(h[2])/math.log(65536),math.log1p(h[6])/math.log(65536) if proto==6 else 0.,math.log1p(h[5])/math.log(65536) if proto==17 else 0.,float(direction)]
                assert np.array_equal(np.asarray(q,dtype=np.float32),qs[i]),'SAVED_SNAPSHOT_Q14_EXACT'
                bodies.append(body)
            result[f'{pool}/{label}/{proto}']=dict(rows=len(take),selection='First 128 UIDs in full fixed pool, independent of scores; descriptive slice only',
                uid_sha256=hashlib.sha256(json.dumps([v[0] for v in take]).encode()).hexdigest(),q14_replay_exact=True,
                packets=dict(collections.Counter(str(sum(b['flow']['counts'])) for b in bodies)),
                bursts=dict(collections.Counter(str(len(b['flow']['counts'])) for b in bodies)),
                reset_reasons=dict(collections.Counter(b['provenance']['reset_reason'] for b in bodies)),
                unique_flow_bodies=len({hashlib.sha256(json.dumps(b['flow'],sort_keys=True).encode()).hexdigest() for b in bodies}))
con.close()
write(HERE/'AB_SNAPSHOT_DIAGNOSIS.json',result)
print('PASS: A/B saved snapshot identity and q14 replay; slice context counts recorded')
