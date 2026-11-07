"""Frozen chronological HIST_REF replay; never decode HIST_DEV packets."""
import collections,gzip,json,struct,time
from decimal import Decimal
from pathlib import Path
import numpy as np
from stream_core import Engine
from source_packets import decode
import physical
HERE=Path(__file__).resolve().parent

def resolve(c,key):
 spec=c.read(HERE/'HISTORY_INPUTS.json')['assets'][key];candidates=[HERE/'assets'/key]
 for rel in spec['candidates']:
  for root in [c.PROJECT,c.ROOT]:candidates.append(root/rel)
 cfg=c.PROJECT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/EXECUTION.json'
 if cfg.exists():
  for t in c.read(cfg)['devices']:
   for k in ['raw','packet_index','chronological_order']:
    if t[k]['sha256']==spec['sha256']:candidates.append(Path(t[k]['path']))
 for path in candidates:
  if path.is_file() and path.stat().st_size==spec['bytes'] and c.sha(path)==spec['sha256']:return c.pin(path,spec['sha256'])
 raise RuntimeError('MISSING_HISTORY_ASSET:'+key+':'+spec['candidates'][0])

def load_history(pool,c):
 m=c.read(HERE/'HISTORY_INPUTS.json');rows=[];z=[];q=[]
 for spec in m['packs'][pool]:
  with gzip.open(resolve(c,spec['rows']),'rt') as f:rr=[json.loads(line) for line in f]
  with np.load(resolve(c,spec['arrays']),allow_pickle=False) as a:
   assert a['uid'].tolist()==[r['uid'] for r in rr]
   ix=[i for i,r in enumerate(rr) if not spec.get('device') or r['device']==spec['device']]
   if 'count' in spec:assert len(ix)==spec['count']
   rows.extend(rr[i] for i in ix);z.append(a['e3'][ix]);q.append(a['q14'][ix])
 assert len({r['uid'] for r in rows})==len(rows)
 assert all(r['label']==0 and r['use']=='REFERENCE' and r['timestamp']<=r['reference_end'] for r in rows)
 if pool=='CIC_DEV':assert len(rows)==289
 else:assert all(r['history_role']=='HIST_REF' and r['frame']<=r['bank_end_frame'] for r in rows)
 return rows,np.concatenate(z),np.concatenate(q)

def union(dense,history):
 rr,z,q=dense;hr,hz,hq=history;ends={}
 for r in rr:
  key=(r['partition'],r['device']);assert ends.setdefault(key,r['reference_end'])==r['reference_end']
 ix=[i for i,r in enumerate(hr) if (r['partition'],r['device']) in ends];assert len(ix)==len(hr)
 extra=[dict(hr[i],reference_end=ends[hr[i]['partition'],hr[i]['device']],historical_reference_end=hr[i]['reference_end']) for i in ix]
 out=rr+extra;assert len({r['uid'] for r in out})==len(out)
 return out,np.concatenate([z,hz[ix]]),np.concatenate([q,hq[ix]])

def block(f,endian=None):
 head=f.read(8);assert len(head)==8
 if head[:4]==b'\x0a\x0d\x0d\x0a':
  bom=f.read(4);assert bom in [b'\x4d\x3c\x2b\x1a',b'\x1a\x2b\x3c\x4d'];endian='<' if bom[0]==77 else '>'
  n=struct.unpack(endian+'I',head[4:])[0];assert 28<=n<=16*1024**2 and n%4==0;b=head+bom+f.read(n-12)
 else:
  assert endian in ['<','>'];n=struct.unpack(endian+'I',head[4:])[0];assert 12<=n<=16*1024**2 and n%4==0;b=head+f.read(n-8)
 assert len(b)==n and struct.unpack_from(endian+'I',b,n-4)[0]==n
 return struct.unpack_from(endian+'I',b)[0],b,endian

def indexed_packets(raw,index,order,target,stop):
 assert 1<=stop<=target['bank_end_frame']<len(order)
 with raw.open('rb') as f:
  kind,b,endian=block(f);assert kind==0x0a0d0d0a
  kind,b,_=block(f,endian);assert kind==1 and struct.unpack_from(endian+'H',b,8)[0]==1
  # Original C1-C4 index was decoded on microsecond interface, with optional signed seconds offset.
  denom=10**6;offset=0;pos=16
  while pos+4<=len(b)-4:
   code,n=struct.unpack_from(endian+'HH',b,pos);pos+=4;v=b[pos:pos+n];pos+=(n+3)//4*4
   if code==0:break
   if code==9:assert n==1;ex=v[0];denom=(2 if ex&128 else 10)**(ex&127)
   if code==14:assert n==8;offset=struct.unpack(endian+'q',v)[0]
  assert denom==10**6 and offset==target.get('timestamp_offset_seconds',0),'HISTORY_TIMESTAMP_INTERFACE'
  previous=-1;prior_origin=-1
  for frame in range(1,stop+1):
   i=int(order[frame-1]);assert 0<=i<len(index);item=index[i];ordinal=int(item['original_packet_ordinal']);assert ordinal==i+1
   t=int(item['timestamp_us']);assert previous<=t<=target['reference_end_us'],'HIST_REF_TIME_BOUNDARY'
   if t==previous:assert ordinal>prior_origin,'STABLE_TIMESTAMP_ORDER'
   previous=t;prior_origin=ordinal
   f.seek(int(item['block_offset']));kind,b,_=block(f,endian);assert kind==6
   iface,hi,lo,cap,wire=struct.unpack_from(endian+'IIIII',b,8)
   assert iface==int(item['interface_id'])==0 and cap==int(item['captured_bytes']) and wire==int(item['wire_bytes'])
   assert ((hi<<32)|lo)+offset*10**6==t and 28+cap<=len(b)-4
   packet,reason=decode(b[28:28+cap]);yield frame,t*1000,packet,reason,ordinal

def replay_b(rows,target,c,progress,small=False):
 raw=resolve(c,target['raw']['asset']);index=np.load(resolve(c,target['packet_index']['asset']),mmap_mode='r');order=np.load(resolve(c,target['chronological_order']['asset']),mmap_mode='r')
 assert len(index)==len(order)==target['packets'];end=target['bank_end_frame']
 assert int(index[int(order[end-1])]['timestamp_us'])==target['reference_end_us']
 assert int(index[int(order[end])]['timestamp_us'])==target['first_dev_time_us']>target['reference_end_us']
 rr=sorted(rows,key=lambda r:(r['frame'],r['uid']))[:8] if small else rows
 targets=collections.defaultdict(list)
 for i,r in enumerate(rr):
  assert r['origin_raw_sha256']==target['raw']['sha256'] and r['bank_end_frame']==end and r['reference_end_us']==target['reference_end_us'];targets[r['frame']].append(i)
 stop=max(targets) if small else end;x=np.full((len(rr),8),np.nan);engine=Engine();history=collections.deque();owner=target['owner'].replace(':','').lower();checks=0;seen=0;start=time.monotonic()
 for frame,t,p,reason,ordinal in indexed_packets(raw,index,order,target,stop):
  event=None
  if p and p[-2]==owner:
   proto,size,src,dst,sp,dp,md,ms=p;event=(md,proto,size,src,struct.pack('!BIIHH',proto,src,dst,sp,dp))
  clock=engine.advance(frame,t,target['key'],event)
  if small:
   while history and history[0][0]<=clock-10**10:history.popleft()
   if event:history.append((clock,event))
  for i in targets.get(frame,[]):
   r=rr[i];assert ordinal==r['origin_packet_ordinal'] and t==r['timestamp_us']*1000
   assert p and owner in p[-2:] and p[0]==r['protocol'];x[i]=engine.features(owner,p[0]);seen+=1
   if small:
    brute=[]
    for width in [10**9,10**10]:
     ev=[e for tm,e in history if clock-width<tm<=clock and e[0]==owner and e[1]==p[0]]
     brute.extend([len(ev)/(width/1e9),sum(e[2] for e in ev)/(width/1e9),len({e[3] for e in ev}),len({e[4] for e in ev})])
    assert np.array_equal(x[i],brute),'CHRONOLOGICAL_ORACLE_GATE';checks+=1
  if frame%50000==0:progress('HISTORY_CHRONOLOGICAL_'+target['key'],frame,stop)
 assert frame==stop and seen==len(rr) and np.isfinite(x).all()
 return rr,x,dict(rows=seen,frames=frame,bank_end_frame=end,decoded_hist_dev=0,oracle_checks=checks,seconds=time.monotonic()-start,peak_entries=engine.peak_entries)

def contexts(pool,rows,c,progress,small=False):
 m=c.read(HERE/'HISTORY_INPUTS.json');parts=[];receipts={}
 if pool=='CIC_DEV':
  for spec in m['a_captures']:
   rr=[r for r in rows if r['source_sha256']==spec['sha256']];assert rr
   if small:rr=sorted(rr,key=lambda r:r['frame'])[:8]
   x,rec=physical.replay(rr,resolve(c,spec['asset']),spec['sha256'],c,progress,oracle=small)
   parts.extend(zip(rr,x['features']));receipts[spec['capture_id']]=dict(rec,independent_engine=True)
 else:
  for spec in m['b_targets']:
   rr=[r for r in rows if r['origin_raw_sha256']==spec['raw']['sha256']];assert rr
   rr,x,rec=replay_b(rr,spec,c,progress,small);parts.extend(zip(rr,x));receipts[spec['key']]=rec
 byuid={r['uid']:x for r,x in parts};assert len(byuid)==len(parts)
 if not small:assert set(byuid)=={r['uid'] for r in rows}
 return byuid,receipts
