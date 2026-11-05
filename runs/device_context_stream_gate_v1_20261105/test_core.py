"""Independent prefix oracle and adversarial boundary/restart checks."""
import hashlib,random
from stream_core import Engine,CapacityError
def oracle(records,owner,proto,now,segment):
 out=[]
 for w in [10**9,10**10]:
  rr=[e for t,seg,e in records if seg==segment and now-w<t<=now and e is not None and e[0]==owner and e[1]==proto]
  out.extend([len(rr),sum(e[2] for e in rr),len({e[3] for e in rr}),len({e[4] for e in rr})])
 return tuple(out)
def run():
 rng=random.Random(20261105);engine=Engine();records=[];clock=None;old_segment=None;checks=0
 # Reversals, ties, exact boundaries, idle expiry, segment reset and two protocols/devices.
 seq=[0,0,10**9,10**9-1,10**10,10**10+1,50*10**9]
 seq += [int(60*10**9+i*10**7+rng.choice([-1,0,0,1])*2*10**7) for i in range(2500)]
 for i,t in enumerate(seq,1):
  segment=i//700
  if segment!=old_segment:clock=t;old_segment=segment
  else:clock=max(clock,t)
  event=None if i%5==0 else (str(i%3),6 if i%2 else 17,28+i%100,('v6' if i%7==0 else 'v4',i%11),(i%3,i%13,i%7))
  got=engine.advance(i,t,segment,event);assert got==clock;records.append((clock,segment,event))
  for owner,proto in [(str(i%3),6),(str(i%3),17)]:
   x=oracle(records,owner,proto,clock,segment);assert engine.integers(owner,proto)==x
   y=tuple(float(v) if j not in [4,5] else v/10. for j,v in enumerate(x));assert engine.features(owner,proto)==y;checks+=1
  if i%503==0:
   b=engine.checkpoint('TEST');engine=Engine.restore(b,hashlib.sha256(b).hexdigest(),'TEST')
 b=engine.checkpoint('TEST')
 for payload,digest,binding in [(b,b'bad','TEST'),(b,hashlib.sha256(b).hexdigest(),'WRONG')]:
  try:Engine.restore(payload,digest,binding)
  except ValueError:pass
  else:raise AssertionError('MISSING_CHECKPOINT_GUARD')
 small=Engine(max_entries=8)
 for i in range(1,5):small.advance(i,0,0,('x',17,28,i,i))
 try:small.advance(5,0,0,('x',17,28,5,5))
 except CapacityError:pass
 else:raise AssertionError('MISSING_ENTRY_CAP')
 assert small.integers('x',17)==(4,112,4,4,4,112,4,4)
 small.advance(5,11*10**9,0,None);assert not any(small.queues) and not any(small.groups)
 groups=Engine(max_groups=2)
 groups.advance(1,0,0,('a',6,40,1,1));groups.advance(2,0,0,('b',17,28,1,1))
 try:groups.advance(3,0,0,('c',6,40,1,1))
 except CapacityError:pass
 else:raise AssertionError('MISSING_GROUP_CAP')
 return dict(status='PASS',integer_and_float_checks=checks,frames=len(seq),checkpoint_restores=4,capacity_failure_before_insertion=True,empty_state_after_idle=True,cases=['current_packet','equal_time_prefix','lower_boundary','regression','two_protocols','three_owners','outbound_no_insert','IPv6_identity','segment_reset','idle_cleanup','checkpoint_sha_and_binding'])
if __name__=='__main__':print(run())
