"""Freeze deterministic UDP slices before opening feature/score arrays."""
import collections,gzip,hashlib,json,sqlite3
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def rank(uid):return hashlib.sha256(('context-v1|'+uid).encode()).hexdigest()
def main():
 (HERE/'.private').mkdir(exist_ok=True);spec=read(ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json');freeze=read(ROOT/'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json')
 con=sqlite3.connect((ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/spool/snapshots.sqlite').as_uri()+'?mode=ro',uri=True)
 selected=[];pins={};sources={};counts={}
 for pool in ['CIC_DEV','UNSW_DEV']:
  s=spec['pools'][pool]['query'];p=ROOT/s['rows']['path'];assert sha(p)==s['rows']['sha256'];pins[str(p.relative_to(ROOT))]=sha(p)
  with gzip.open(p,'rt') as f:rows=[json.loads(l) for l in f]
  replay=ROOT/f'runs/c5_kernel_independent_replay_codex_20261102/ab/{pool}_REPLAY.npz';assert sha(replay)==freeze['immutable_asset_pins'][replay.relative_to(ROOT).as_posix()]['sha256']
  pins[replay.relative_to(ROOT).as_posix()]=sha(replay)
  with np.load(replay) as z:keep=z['primary_indices'].copy();assert z['uid'].tolist()==[r['uid'] for r in rows]
  groups=collections.defaultdict(list)
  for i in keep:
   r=rows[int(i)]
   if r['protocol']==17:groups[(r['device'],int(r['label']))].append(int(i))
  sources[pool]=(s,rows)
  for (device,label),ix in sorted(groups.items()):
   take=sorted(ix,key=lambda i:rank(rows[i]['uid']))[:32 if pool=='CIC_DEV' else 8]
   counts[pool+'/'+device+'/'+str(label)]=dict(available=len(ix),selected=len(take))
   selected.extend((pool,i) for i in take)
 # Seal UID membership before loading any E3/q14/logits.
 selection=dict(plan_sha256=sha(HERE/'PLAN.json'),groups=counts,samples=[dict(dataset=p,uid=sources[p][1][i]['uid']) for p,i in selected])
 (HERE/'SELECTION.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
 arrays={};samples=[]
 for pool,(s,rows) in sources.items():
  for name in ['q14','e3','logits','q_uids','feature_uids']:
   p=ROOT/s[name]['path'];assert sha(p)==s[name]['sha256'];pins[s[name]['path']]=s[name]['sha256']
  assert read(ROOT/s['q_uids']['path'])==read(ROOT/s['feature_uids']['path'])==[r['uid'] for r in rows]
  scores=np.load(ROOT/s['logits']['path']);assert scores['uid'].tolist()==[r['uid'] for r in rows]
  arrays[pool]=(np.load(ROOT/s['e3']['path'],mmap_mode='r'),np.load(ROOT/s['q14']['path'],mmap_mode='r'),scores)
 for pool,i in selected:
  row=sources[pool][1][i];body=json.loads(con.execute('SELECT body FROM snapshots WHERE uid=?',(row['uid'],)).fetchone()[0]);z,q,s=arrays[pool]
  assert body['provenance']['query_frame']==row['frame']
  samples.append(dict(dataset=pool,group=('ATTACK' if row['label'] else 'NORMAL')+'/'+row['device'],uid=row['uid'],row=row,body=body,expected_e3=z[i,:768].tolist(),expected_q14=q[i].tolist(),expected_scores=s['head'][i].tolist()))
 con.close();payload=HERE/'.private/AB_SAMPLES.json.gz'
 with payload.open('wb') as f:
  with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as g:g.write(json.dumps(samples,separators=(',',':')).encode())
 receipt=dict(rows=len(samples),payload_sha256=sha(payload),payload_bytes=payload.stat().st_size,selection_sha256=sha(HERE/'SELECTION.json'),source_pins=pins)
 (HERE/'SAMPLE_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(dict(rows=len(samples),bytes=payload.stat().st_size,groups=counts)))
if __name__=='__main__':main()
