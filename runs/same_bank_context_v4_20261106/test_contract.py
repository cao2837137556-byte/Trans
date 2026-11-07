import ast,json,tempfile,struct,hashlib,sys
from pathlib import Path
import numpy as np
import history_context as h
from stream_core import Engine
P=Path(__file__).resolve().parent;checks=0
def check(v):
 global checks
 checks+=1;assert v
# Exact current-inclusive, left-open boundary; independent capture reset.
e=Engine();event=('a',17,28,1,b'flow');e.advance(1,0,0,event);e.advance(2,10**9,0,event);check(e.features('a',17)==(1.,28.,1.,1.,.2,5.6,1.,1.));e.advance(3,10**9,1,event);check(e.features('a',17)[4]==.1)
# Deliberately out-of-order raw EPB blocks. Only sealed chronological prefix may be decoded.
with tempfile.TemporaryDirectory() as td:
 p=Path(td)/'test.pcapng'
 def block(kind,body):
  n=12+len(body);return struct.pack('<II',kind,n)+body+struct.pack('<I',n)
 shb=block(0x0a0d0d0a,struct.pack('<IHHq',0x1a2b3c4d,1,0,-1));idb=block(1,struct.pack('<HHI',1,0,65535));payload=b'\0'*14
 chunks=[shb,idb];entries=[];offset=len(shb)+len(idb)
 for i,t in enumerate([3,1,2]):
  b=block(6,struct.pack('<IIIII',0,0,t,len(payload),len(payload))+payload+b'\0'*2);entries.append((i+1,t,offset,0,14,14));chunks.append(b);offset+=len(b)
 p.write_bytes(b''.join(chunks));dtype=[('original_packet_ordinal','i8'),('timestamp_us','i8'),('block_offset','i8'),('interface_id','i4'),('captured_bytes','i4'),('wire_bytes','i4')]
 idx=np.asarray(entries,dtype=dtype);order=np.asarray([1,2,0]);target=dict(bank_end_frame=2,reference_end_us=2,first_dev_time_us=3)
 seen=list(h.indexed_packets(p,idx,order,target,2));check([v[4] for v in seen]==[2,3]);check([v[1] for v in seen]==[1000,2000])
 for bad_order,bad_stop in [(np.array([0,1,2]),2),(order,3)]:
  try:list(h.indexed_packets(p,idx,bad_order,target,bad_stop))
  except AssertionError:check(True)
  else:raise AssertionError('INVALID_TIMELINE_ACCEPTED')
check(not any(n.endswith('/DELIVERY.json') for n in json.loads((P/'INPUT_PINS.json').read_text())))
sys.path[:0]=[str(P.parents[1]/'runs/onboarding_new_lineage_v1_20261022/package_v3'),str(P.parents[1]/'repo/ood')]
import constrained_onboarding_core_v3 as core
import geometry_frozen as frozen
import fast_geometry as fast
rng=np.random.default_rng(127)
for components in [['a','b','a','c','b'],['a','b','c','d'],['b','b','a','a']]:
 for values in [rng.random((17,len(components))),np.zeros((17,len(components))),np.full((17,len(components)),np.inf)]:
  a,b=core._second_distinct(values,components);x,y=fast.Reducer(components).second(values,True)
  check(np.array_equal(a,x) and np.array_equal(b,y))
refs=[dict(uid=f'r{i:04}',partition='DEV',protocol=6,device='x',component_id=f'c{i%7}',capture_id='old' if i%2 else 'shared',frame=i+1,timestamp=float(i)/10,reference_end=100.,use='REFERENCE',label=0) for i in range(180)]
rows=[dict(uid=f'q{i:04}',partition='DEV',protocol=6 if i%17 else 17,device='x',component_id=f'c{i%9}',capture_id='shared' if i%3 else 'new',frame=i+1,timestamp=90. if i%11==0 else 200.,use='QUERY',label=i%2) for i in range(260)]
rz=rng.normal(size=(180,768)).astype(np.float32);rq=rng.integers(0,2,(180,14)).astype(np.float32);rc=rng.random((180,8)).astype(np.float32)
z=rng.normal(size=(260,768)).astype(np.float32);q=rng.integers(0,2,(260,14)).astype(np.float32);xc=rng.random((260,8)).astype(np.float32);norm=(np.zeros(768),np.ones(768))
for radius in [0.,2.]:
 geom={'protocols':{str(p):dict(status='READY',rho_z=radius,rho_q=radius) for p in [6,17]}};rhoc={str(p):dict(status='READY',rho_c=radius) for p in [6,17]}
 bank=core.ReferenceBank(refs,rz,rq,norm,feature_uids=[r['uid'] for r in refs],q_uids=[r['uid'] for r in refs],allow_prebank_history=True)
 old=bank.own(rows,z,q,geom,feature_uids=[r['uid'] for r in rows],q_uids=[r['uid'] for r in rows])
 d=dict(rows=rows,z=z,q=q,context=xc,support=old['support']);args=(d,refs,rz,rq,rc,norm,geom,rhoc,core,lambda *a,**kw:None)
 check(fast.compare(frozen.evaluate(*args),fast.evaluate(*args))['status']=='PASS')
check('w.write(\'RUNTIME_FORECAST.json\'' in (P/'worker.py').read_text() and (P/'worker.py').read_text().index("w.write('RUNTIME_FORECAST.json'") < (P/'worker.py').read_text().index("assert forecast<5400"))
for f in P.glob('*.py'):ast.parse(f.read_text());check(True)
(P/'LOCAL_REGRESSION.json').write_text(json.dumps(dict(status='PASS',checks=checks,scope='window boundary, capture reset, indexed seek order, cutoff negatives, syntax'),indent=2)+'\n',encoding='utf-8')
print('LOCAL_CHECKS',checks)
