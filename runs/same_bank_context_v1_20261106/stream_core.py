"""Exact current-inclusive prefix-clock device statistics; no I/O/model/labels."""
from collections import Counter,deque
import hashlib,pickle
NS=1000000000
VERSION='DEVICE_CONTEXT_D1_CURRENT_INCLUSIVE_V1'
class CapacityError(RuntimeError):pass
class Stats:
 def __init__(self):self.n=0;self.bytes=0;self.sources=Counter();self.connections=Counter()
 def change(self,size,src,conn,sign):
  self.n+=sign;self.bytes+=sign*size
  for c,key in [(self.sources,src),(self.connections,conn)]:
   c[key]+=sign
   if not c[key]:del c[key]
 def values(self):return (self.n,self.bytes,len(self.sources),len(self.connections))
class Engine:
 def __init__(self,max_entries=1000000,max_groups=4096):
  self.max_entries=max_entries;self.max_groups=max_groups;self.clock=None;self.frame=0;self.segment=None
  self.queues=[deque(),deque()];self.groups=[{},{}];self.peak_entries=0;self.peak_groups=0;self.resets=0
 def advance(self,frame,raw_ns,segment,event=None):
  """event=(protected_owner,protocol,IPbytes,source_identity,directed_5tuple), inbound only."""
  if frame!=self.frame+1:raise ValueError('NONCONTIGUOUS_FRAME')
  if type(raw_ns) is not int or raw_ns<0:raise ValueError('INTEGER_NS_REQUIRED')
  if segment!=self.segment:
   self.clock=None;self.queues=[deque(),deque()];self.groups=[{},{}];self.resets+=1;self.segment=segment
  now=raw_ns if self.clock is None else max(self.clock,raw_ns)
  for wi,w in enumerate([NS,10*NS]):
   queue=self.queues[wi];groups=self.groups[wi]
   while queue and queue[0][0]<=now-w:
    _,key,size,src,conn=queue.popleft();st=groups[key];st.change(size,src,conn,-1)
    if not st.n:del groups[key]
  if event is not None:
   owner,proto,size,src,conn=event
   if proto not in (6,17) or type(size) is not int or size<=0:raise ValueError('EVENT_SCHEMA')
   key=(owner,proto)
   if sum(map(len,self.queues))+2>self.max_entries:raise CapacityError('ACTIVE_ENTRY_CAP')
   if key not in self.groups[1] and len(self.groups[1])+1>self.max_groups:raise CapacityError('GROUP_CAP')
   record=(now,key,size,src,conn)
   for queue,groups in zip(self.queues,self.groups):
    queue.append(record)
    if key not in groups:groups[key]=Stats()
    groups[key].change(size,src,conn,1)
  self.clock=now;self.frame=frame;self.peak_entries=max(self.peak_entries,sum(map(len,self.queues)));self.peak_groups=max(self.peak_groups,len(self.groups[1]))
  return now
 def integers(self,owner,proto):
  key=(owner,proto);out=[]
  for groups in self.groups:
   out.extend(groups[key].values() if key in groups else (0,0,0,0))
  return tuple(out)
 def features(self,owner,proto):
  x=self.integers(owner,proto);return (float(x[0]),float(x[1]),float(x[2]),float(x[3]),x[4]/10.,x[5]/10.,float(x[6]),float(x[7]))
 def checkpoint(self,binding):
  return pickle.dumps(dict(version=VERSION,binding=binding,engine=self),protocol=5)
 @staticmethod
 def restore(payload,expected_sha256,binding):
  if hashlib.sha256(payload).hexdigest()!=expected_sha256:raise ValueError('CHECKPOINT_SHA')
  value=pickle.loads(payload) # only locally produced, SHA-bound checkpoint
  if value['version']!=VERSION or value['binding']!=binding:raise ValueError('CHECKPOINT_BINDING')
  return value['engine']
