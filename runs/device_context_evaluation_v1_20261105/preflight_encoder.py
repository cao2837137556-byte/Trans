"""Re-encode complete original batches, then recompute legal bank distances."""
import io,sys,hashlib
import numpy as np
from common import *

def run(data,norm):
 sys.path.insert(0,str(ROOT/'runs/edge_formal_execution_v4_20261104'))
 from streaming import FrozenBackend
 from checkpoint import PrimitiveUnpickler
 from constrained_onboarding_core_v3 import ReferenceBank
 chosen=[]
 for role,proto in sorted({(r['source_role'],r['protocol']) for r in data['rows']}):
  chosen.append(min((i for i,r in enumerate(data['rows']) if (r['source_role'],r['protocol'])==(role,proto)),key=lambda i:data['rows'][i]['frame']))
 wanted={data['lookup'][data['rows'][i]['uid']][0] for i in chosen}
 for proto in (6,17):
  seen=set()
  for r in sorted(data['refs'],key=lambda r:r['uid']):
   if r['protocol']==proto and r['component_id'] not in seen:
    wanted.add(data['lookup'][r['uid']][0]);seen.add(r['component_id'])
    if len(seen)==2:break
 ids={u for b in wanted for u in data['batches'][b]['uids']};snapshots={};shapes={}
 imported=read(pin(EDGE/'COMPLETE_IMPORT.json','2b169a24e39b250b58e6cd8ba227ec3b03b0215f5227ccf64dd8ec5c0e8416af'))
 for role in ('NORMAL','HTTP','UDP'):
  root=EDGE/'spools'/role;complete=read(pin(root/'COMPLETE.json',imported['roles'][role]['complete_sha256']))
  for chunk in complete['chunks']:
   folder=root/complete['attempt']/chunk['name'];index=read(pin(folder/'INDEX.json',chunk['index']['sha256']))
   selected=[e for e in index if e['uid'] in ids]
   if not selected:continue
   path=pin(folder/'snapshots.bin',chunk['data']['sha256'])
   with path.open('rb') as f:
    for e in selected:
     f.seek(e['offset']);payload=f.read(e['bytes']);assert hashlib.sha256(payload).hexdigest()==e['sha256']
     v=PrimitiveUnpickler(io.BytesIO(payload)).load();assert v['uid']==e['uid'];snapshots[e['uid']]=v;shapes[e['uid']]=tuple(e['header']['shape'])
 assert set(snapshots)==ids
 backend=FrozenBackend();maximum=0.;fresh={};encoded=0
 for b in sorted(wanted):
  uids=data['batches'][b]['uids'];shape=shapes[uids[0]];assert all(shapes[u]==shape for u in uids)
  z,q,receipt=backend.encode([snapshots[u] for u in uids],shape)
  base=EDGE/'encoded/batches'/b;oldz=np.load(base/'E3.npy');oldq=np.load(base/'q14.npy');oldrows=read(base/'rows.json')
  err=float(np.max(np.abs(z-oldz)));maximum=max(maximum,err);assert err<=2e-4 and np.array_equal(q,oldq),'ENCODER_PARITY'
  for i,u in enumerate(uids):
   assert receipt['inputs'][i]['input_tensor_sha256']==oldrows[i]['_input_tensor_sha256'];fresh[u]=(z[i],q[i])
  encoded+=len(uids);progress('REAL_ENCODER',encoded,len(ids))
 del backend,snapshots
 refs=data['refs'];uids=[r['uid'] for r in refs]
 bank=ReferenceBank(refs,data['rz'],data['rq'],norm,feature_uids=uids,q_uids=uids)
 rr=[data['rows'][i] for i in chosen];uu=[r['uid'] for r in rr];geometry=read(HERE/'METHOD_FREEZE.json')['calibration']['geometry']
 cached=bank.own(rr,data['z'][chosen],data['q'][chosen],geometry,feature_uids=uu,q_uids=uu)
 actual=bank.own(rr,np.asarray([fresh[u][0] for u in uu]),np.asarray([fresh[u][1] for u in uu]),geometry,feature_uids=uu,q_uids=uu)
 cache_error=float(np.max(np.abs(cached['support']-data['support'][chosen])));fresh_error=float(np.max(np.abs(actual['support']-cached['support'])))
 assert cache_error<=1e-12 and fresh_error<=.002,'DISTANCE_PARITY'
 return dict(status='PASS',query_rows=len(chosen),reference_rows=len(refs),encoded_rows=encoded,encoded_batches=len(wanted),e3_max_abs_error=maximum,cached_support_error=cache_error,fresh_support_error=fresh_error)
