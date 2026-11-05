"""Score-independent A/B saved input slices for same-runtime remote replay."""
import gzip,hashlib,json,sqlite3
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
spec=read(ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
db=ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/spool/snapshots.sqlite'
con=sqlite3.connect(db.as_uri()+'?mode=ro',uri=True);samples=[];pins={}
for pool in ['CIC_DEV','UNSW_DEV']:
    s=spec['pools'][pool]['query']
    for name in ['rows','q14','e3','logits']:
        p=ROOT/s[name]['path'];assert sha(p)==s[name]['sha256'];pins[s[name]['path']]=s[name]['sha256']
    with gzip.open(ROOT/s['rows']['path'],'rt') as f:rows=[json.loads(x) for x in f]
    q=np.load(ROOT/s['q14']['path'],mmap_mode='r');z=np.load(ROOT/s['e3']['path'],mmap_mode='r')
    scores=np.load(ROOT/s['logits']['path']);assert scores['uid'].tolist()==[r['uid'] for r in rows]
    groups={}
    for i,r in enumerate(rows):
        group=('ATTACK_'+r['activity'] if pool=='CIC_DEV' else 'ATTACK_SYN') if r['label'] else 'NORMAL_'+str(r['protocol'])
        if group=='ATTACK_TCP':continue
        groups.setdefault(group,[]).append((r['uid'],i))
    for group,values in sorted(groups.items()):
        for uid,i in sorted(values)[:(2 if group.startswith('ATTACK') else 1)]:
            body=json.loads(con.execute('SELECT body FROM snapshots WHERE uid=?',(uid,)).fetchone()[0])
            assert body['provenance']['query_frame']==rows[i]['frame']
            samples.append(dict(dataset=pool,group=group,uid=uid,row=rows[i],body=body,
                                expected_e3=z[i,:768].tolist(),expected_q14=q[i].tolist(),expected_scores=scores['head'][i].tolist()))
con.close()
payload=HERE/'.private/AB_SAMPLES.json.gz'
with gzip.open(payload,'wt',encoding='utf-8') as f:json.dump(samples,f,separators=(',',':'))
runtime=read(ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/runtime_effective.json')
receipt=dict(selection='First UID(s) per predeclared activity/protocol class, independent of scores',rows=len(samples),
             samples=[{k:r[k] for k in ['dataset','group','uid']} for r in samples],payload_sha256=sha(payload),payload_bytes=payload.stat().st_size,
             source_pins=pins,ab_encoder_checkpoint_sha256=runtime['checkpoint_sha256'],ab_runtime_versions=runtime['versions'],
             tolerances=dict(e3_abs=0.0002,head_abs=0.002),
             comparison='Fresh singleton-as-16-identical-clones vs original saved batching; numerical tolerance predeclared, decisions also checked')
(HERE/'SAMPLE_RECEIPT.json').write_text(json.dumps(receipt,indent=2))
print('Prepared',len(samples),'samples;',payload.stat().st_size,'bytes')
