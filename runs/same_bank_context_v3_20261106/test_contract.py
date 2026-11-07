import ast,json,tempfile,struct,hashlib
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
for f in P.glob('*.py'):ast.parse(f.read_text());check(True)
(P/'LOCAL_REGRESSION.json').write_text(json.dumps(dict(status='PASS',checks=checks,scope='window boundary, capture reset, indexed seek order, cutoff negatives, syntax'),indent=2)+'\n',encoding='utf-8')
print('LOCAL_CHECKS',checks)
