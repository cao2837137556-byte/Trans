"""Replay only the missing reference contexts and physical Edge metadata."""
import collections,json,struct,time
from decimal import Decimal
from pathlib import Path
import numpy as np
from stream_core import Engine
from source_packets import packets

def replay(rows,path,sha_expected,c,progress,segments=None,oracle=False):
 path=c.pin(path,sha_expected);before=(path.stat().st_size,path.stat().st_mtime_ns)
 targets=collections.defaultdict(list)
 for i,r in enumerate(rows):targets[int(r.get('original_frame',r['frame']))].append(i)
 owners={r['owner'].replace(':','').lower() for r in rows};last=max(targets)
 segments=segments or [dict(first_frame=1,last_frame=last)]
 engine=Engine(1000000,4096);segment=0;previous=None;startclock=None;history=collections.deque()
 x=np.full((len(rows),8),np.nan);age=np.full(len(rows),np.nan);inbound=np.zeros(len(rows),bool);seen=0;checks=0
 for frame,t,p,reason in packets(path):
  while frame>segments[segment]['last_frame']:segment+=1
  if segment!=previous:startclock=t;history.clear();previous=segment
  event=None
  if p and p[-2] in owners:
   proto,size,src,dst,sp,dp,md,ms=p;event=(md,proto,size,src,struct.pack('!BIIHH',proto,src,dst,sp,dp))
  clock=engine.advance(frame,t,segment,event)
  if oracle:
   while history and history[0][0]<=clock-10**10:history.popleft()
   if event:history.append((clock,event))
  if frame in targets:
   for i in targets[frame]:
    r=rows[i];owner=r['owner'].replace(':','').lower()
    assert p and p[0]==r['protocol'] and owner in p[-2:],'RAW_IDENTITY'
    if 'timestamp_ns' in r:assert t==r['timestamp_ns']
    else:assert float(Decimal(t)/Decimal(10**9))==r['timestamp']
    x[i]=engine.features(owner,p[0]);age[i]=(clock-startclock)/1e9;inbound[i]=(p[-2]==owner);seen+=1
    if oracle:
     brute=[]
     for width in [10**9,10**10]:
      ev=[e for tm,e in history if clock-width<tm<=clock and e[0]==owner and e[1]==p[0]]
      brute.extend([len(ev)/(width/1e9),sum(e[2] for e in ev)/(width/1e9),len({e[3] for e in ev}),len({e[4] for e in ev})])
     assert np.array_equal(x[i],brute);checks+=1
  if frame%100000==0:progress('RAW_CONTEXT_'+path.name,frame,last)
  if frame==last:break
 assert seen==len(rows) and np.isfinite(x).all() and before==(path.stat().st_size,path.stat().st_mtime_ns)
 return dict(features=x,age_seconds=age,inbound=inbound),dict(rows=seen,frames=frame,oracle_checks=checks,peak_entries=engine.peak_entries)

def source_refs(rows,c,progress,small=False):
 cat={r['capture_id']:r for r in c.read(c.SOURCE/'RAW_CATALOG.json')}
 plan=c.read(c.SOURCE/'ASSET_PLAN.json');resolved=c.read(c.SOURCE/'RESOLVED_ASSETS.json')
 paths={v['sha256']:resolved[k] for k,v in plan.items() if v['kind']=='raw'}
 groups=collections.defaultdict(list)
 for i,r in enumerate(rows):
  assert r['use']=='REFERENCE' and r['label']==0 and r['timestamp']<=r['reference_end']
  assert cat[r['capture_id']]['sha256']==r['source_sha256'];groups[r['capture_id']].append(i)
 out=np.full((len(rows),8),np.nan);receipts={}
 for cap,ix in groups.items():
  selected=ix[:2] if small else ix
  rr=[rows[i] for i in selected];r,receipt=replay(rr,paths[rr[0]['source_sha256']],rr[0]['source_sha256'],c,progress,oracle=small)
  out[selected]=r['features'];receipts[cap]=receipt
 return out,receipts

def edge(rows,c,progress,small=False):
 card=c.read(c.HERE/'EDGE_CARD.json');paths=c.read(c.PROJECT/'runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json');out={};receipts={}
 for role in ['NORMAL','HTTP','UDP']:
  rr=[r for r in rows if r['source_role']==role]
  if small:rr=sorted(rr,key=lambda r:r.get('original_frame',r['frame']))[:8]
  segments=card['capture_boundaries']['normal_segments'] if role=='NORMAL' else None
  a,receipt=replay(rr,paths[role],card['raw_inputs'][role]['sha256'],c,progress,segments,small);receipts[role]=receipt
  for i,r in enumerate(rr):out[r['uid']]={k:v[i] for k,v in a.items()}
 return out,receipts
