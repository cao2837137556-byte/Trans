"""Exact causal time-window/cardinality queries, including cross-key clock regressions.

Offline time sweep with frame-prefix Fenwick trees. A source/connection is present
in a frame prefix iff its minimum active frame is in that prefix. Thus future
frames never contribute even though the sweep sorts timestamp ranges offline.
"""
import bisect,collections,heapq,struct
import numpy as np

class Fenwick:
 def __init__(self,n):self.v=[0]*(n+1)
 def add(self,i,x):
  i+=1
  while i<len(self.v):self.v[i]+=x;i+=i&-i
 def prefix(self,i):
  out=0;i+=1
  while i:out+=self.v[i];i-=i&-i
  return out

class Distinct:
 def __init__(self,frames,active):self.frames=frames;self.active=active;self.heaps={};self.tree=Fenwick(len(frames))
 def change(self,key,frame,add):
  h=self.heaps.get(key,[]);old=h[0] if h else None
  if add:heapq.heappush(h,frame)
  while h and not self.active[h[0]]:heapq.heappop(h)
  new=h[0] if h else None
  if old!=new:
   if old is not None:self.tree.add(bisect.bisect_left(self.frames,old),-1)
   if new is not None:self.tree.add(bisect.bisect_left(self.frames,new),1)
  if h:self.heaps[key]=h
  else:self.heaps.pop(key,None)

def calculate(events,queries,window,progress=lambda *a:None):
 """events tuples(time_ns,frame,IPbytes,sourceIP,connectionID); queries(time_ns,frame)."""
 if not queries:return np.empty((0,4),np.float64)
 qs=sorted(enumerate(queries),key=lambda x:(x[1][0],x[1][1]));frames=sorted(q[1] for q in queries)
 assert len(frames)==len(set(frames))
 ev=sorted(events,key=lambda x:(x[0],x[1]));active=bytearray(max([e[1] for e in events]+frames)+1)
 nt,bt=Fenwick(len(frames)),Fenwick(len(frames));st,ct=Distinct(frames,active),Distinct(frames,active)
 out=np.empty((len(queries),4),np.float64);lo=hi=0;ns=int(window*1e9)
 def change(e,sign):
  tm,frame,size,src,key=e;idx=bisect.bisect_left(frames,frame)
  active[frame]=int(sign==1);nt.add(idx,sign);bt.add(idx,sign*size)
  st.change(src,frame,sign==1);ct.change(key,frame,sign==1)
 for done,(ix,(tm,frame)) in enumerate(qs):
  # Evict before adding to avoid retaining an entire large time gap.
  while lo<hi and ev[lo][0]<=tm-ns:change(ev[lo],-1);lo+=1
  while hi<len(ev) and ev[hi][0]<=tm:
   if ev[hi][0]>tm-ns:change(ev[hi],1)
   else:lo=hi+1
   hi+=1
  k=bisect.bisect_right(frames,frame)-1
  out[ix]=[nt.prefix(k)/window,bt.prefix(k)/window,st.tree.prefix(k),ct.tree.prefix(k)]
  if done%1000==0:progress(done,len(qs))
 return out

def brute(events,queries,window):
 out=[]
 for t,f in queries:
  rows=[e for e in events if e[1]<=f and t-int(window*1e9)<e[0]<=t]
  out.append([len(rows)/window,sum(e[2] for e in rows)/window,len({e[3] for e in rows}),len({e[4] for e in rows})])
 return np.asarray(out,np.float64).reshape(-1,4)

def regression():
 rng=np.random.default_rng(20261104)
 # Deliberate timestamp reversals, ties, exact lower boundary, repeated keys,
 # future-frame packets earlier in event time, and sparse selected frames.
 events=[(int(t),i+1,int(rng.integers(28,1500)),int(rng.integers(0,8)),int(rng.integers(0,20))) for i,t in enumerate(rng.integers(0,30,400)*1000000000)]
 queries=[(events[i][0],events[i][1]) for i in range(0,400,7)]
 for w in [1,10]:assert np.array_equal(calculate(events,queries,w),brute(events,queries,w)),'EXACT_RANGE_REGRESSION'
 return dict(status='PASS',queries=len(queries),windows=[1,10],cases=['time_reversal','ties','exclusive_lower_boundary','future_frame_exclusion','distinct_repeated_keys','sparse_queries'])

def packets(path):
 """Raw Ethernet IPv4 TCP/UDP tuples; integer nanoseconds, no labels/scores."""
 with path.open('rb') as f:
  h=f.read(24);formats={b'\xd4\xc3\xb2\xa1':('<',1000),b'\xa1\xb2\xc3\xd4':('>',1000),b'\x4d\x3c\xb2\xa1':('<',1),b'\xa1\xb2\x3c\x4d':('>',1)}
  endian,mult=formats[h[:4]];assert struct.unpack_from(endian+'I',h,20)[0]==1
  frame=0
  while h:=f.read(16):
   assert len(h)==16;sec,sub,cap,wire=struct.unpack(endian+'IIII',h);b=f.read(cap);assert len(b)==cap;frame+=1;tm=sec*1000000000+sub*mult
   p=None;reason='NON_IPV4';off=14
   if len(b)>=14:
    eth=struct.unpack_from('!H',b,12)[0]
    while eth in (0x8100,0x88a8) and len(b)>=off+4:eth=struct.unpack_from('!H',b,off+2)[0];off+=4
    if eth==0x0800 and len(b)>=off+20:
     ihl=(b[off]&15)*4;total=struct.unpack_from('!H',b,off+2)[0];frag=struct.unpack_from('!H',b,off+6)[0];proto=b[off+9];reason='NON_TCP_UDP'
     if proto in (6,17):
      reason='FRAGMENT_OR_INCOMPLETE'
      if b[off]>>4==4 and ihl>=20 and total>=ihl+(20 if proto==6 else 8) and not frag&0x3fff and len(b)>=off+total:
       sport,dport=struct.unpack_from('!HH',b,off+ihl);src=int.from_bytes(b[off+12:off+16],'big');dst=int.from_bytes(b[off+16:off+20],'big')
       p=(proto,total,src,dst,sport,dport,b[:6].hex(),b[6:12].hex());reason='ELIGIBLE'
   yield frame,tm,p,reason

def quant(x):
 return dict(zip(['min','p01','p10','p50','p90','p99','max'],map(float,np.quantile(x,[0,.01,.1,.5,.9,.99,1])))) if len(x) else None
def auc(negative,positive):
 if not len(negative) or not len(positive):return None
 a=np.sort(negative);return float(np.sum((np.searchsorted(a,positive,'left')+np.searchsorted(a,positive,'right'))*.5)/(len(a)*len(positive)))
