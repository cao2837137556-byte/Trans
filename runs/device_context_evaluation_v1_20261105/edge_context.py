import collections,gzip,struct,time
import numpy as np
from common import *
from stream_core import Engine
from source_packets import packets

def build(small=False):
 card=read(HERE/'EDGE_CARD.json');rawpaths=read(PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json')
 base=ROOT/'runs/edge_query_selection_v1_20261103/seal20k';seal=read(base/'QUERY_SELECTION_SEAL.json');out={};checks=0
 for role in ['NORMAL','HTTP','UDP']:
  v=seal['roles'][role]
  with gzip.open(pin(base/v['selected_file'],v['selected_sha256']),'rt') as f:rr=[json.loads(line) for line in f]
  if small:rr=[r for proto in sorted({r['protocol'] for r in rr}) for r in sorted((r for r in rr if r['protocol']==proto),key=lambda r:r['frame'])[:8]]
  rr=sorted(rr,key=lambda r:r['frame']);targets={r['frame']:i for i,r in enumerate(rr)};assert len(targets)==len(rr)
  spec=card['raw_inputs'][role];path=pin(rawpaths[role],spec['sha256']);before=(path.stat().st_size,path.stat().st_mtime_ns)
  segments=card['capture_boundaries']['normal_segments'] if role=='NORMAL' else [dict(first_frame=1,last_frame=spec['records'])]
  engine=Engine(1000000,4096);history=collections.deque();segment=0;lastsegment=None;oracleclock=None;last=max(targets) if small else spec['records'];values=np.full((len(rr),8),np.nan);seen=0;debt=0;replica=None;restart=0;start=time.monotonic();split=max(1,last//2)
  for frame,t,p,reason in packets(path):
   while frame>segments[segment]['last_frame']:segment+=1
   if segment!=lastsegment:history.clear();oracleclock=None;lastsegment=segment
   event=None
   if p and p[-2]=='dca632fb69b5':
    proto,size,src,dst,sp,dp,md,ms=p;event=(md,proto,size,src,struct.pack('!BIIHH',proto,src,dst,sp,dp))
   c=engine.advance(frame,t,segment,event);debt=max(debt,c-t)
   if replica is not None:assert replica.advance(frame,t,segment,event)==c
   if small:
    oracleclock=t if oracleclock is None else max(oracleclock,t);assert c==oracleclock
    while history and history[0][0]<=c-10**10:history.popleft()
    if event:history.append((c,event))
   if frame in targets:
    i=targets[frame];row=rr[i];assert p and p[0]==row['protocol'] and t==row['timestamp_ns'] and 'dca632fb69b5' in p[-2:]
    values[i]=engine.features('dca632fb69b5',p[0]);seen+=1
    if replica is not None:assert replica.features('dca632fb69b5',p[0])==tuple(values[i]);restart+=1
    if small:
     brute=[]
     for width in [10**9,10**10]:
      ev=[e for tm,e in history if c-width<tm<=c and e[1]==p[0]];brute.extend([len(ev)/(width/1e9),sum(e[2] for e in ev)/(width/1e9),len({e[3] for e in ev}),len({e[4] for e in ev})])
     assert np.array_equal(values[i],brute);checks+=1
   if frame==split:
    binding=dict(raw=spec['sha256'],engine=sha(HERE/'stream_core.py'));payload=engine.checkpoint(binding);name=('SMALL_' if small else '')+role+'_CHECKPOINT.bin';(HERE/name).write_bytes(payload);replica=Engine.restore(payload,sha(HERE/name),binding)
   if frame%100000==0:progress('CONTEXT_'+role,frame,last,frames_per_second=frame/max(.001,time.monotonic()-start))
   if frame==last:break
  assert frame==last and seen==len(rr) and np.isfinite(values).all() and np.all(values>=0) and debt<=10**9
  assert before==(path.stat().st_size,path.stat().st_mtime_ns)
  name=('SMALL_' if small else '')+role+'_CONTEXT.npz';np.savez(HERE/name,uid=np.asarray([r['uid'] for r in rr]),features=values)
  out[role]=dict(rows=len(rr),frames=frame,sha256=sha(HERE/name),file=name,source_sha256=spec['sha256'],max_clock_debt_ns=debt,restart_queries=restart,seconds=time.monotonic()-start,peak_entries=engine.peak_entries)
 write(('SMALL_' if small else '')+'CONTEXT_RESULT.json',dict(status='PASS',roles=out,independent_checks=checks,selection='first8 per source role/protocol by frame' if small else 'all sealed 60000 queries'))
 return out

def join(rows,small=False):
 receipt=read(HERE/(('SMALL_' if small else '')+'CONTEXT_RESULT.json'));mapping={}
 for r in receipt['roles'].values():
  a=np.load(pin(HERE/r['file'],r['sha256']))
  for u,v in zip(a['uid'],a['features']):assert str(u) not in mapping;mapping[str(u)]=v
 indices=np.asarray([i for i,r in enumerate(rows) if r['uid'] in mapping])
 if not small:assert len(indices)==len(rows)==len(mapping)==60000
 return indices,extra_normalized(np.asarray([mapping[rows[i]['uid']] for i in indices]))
