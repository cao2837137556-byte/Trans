import gzip,json
import numpy as np
from common import *

def asset(key):
 s=read(HERE/'ASSET_PLAN.json')[key];paths=read(HERE/'INVENTORY.json')['files'][key]['candidates']+[str(HERE/'assets'/(key+'.part'))]
 for p in paths:
  if Path(p).is_file() and Path(p).stat().st_size==s['bytes'] and sha(p)==s['sha256']:return pin(p,s['sha256'])
 raise RuntimeError('MISSING_ASSET:'+key)

def source_role(role):
 plan=read(SOURCE/'ASSET_PLAN.json');resolved=read(SOURCE/'RESOLVED_ASSETS.json');wanted={}
 for key,v in plan.items():
  if (v['kind'],v['name']) in [('e3',role+'.npy'),('prepared',role+'_q.npy'),('prepared',role+'.jsonl.gz')]:wanted[v['kind'],v['name']]=pin(resolved[key],v['sha256'])
 with gzip.open(wanted['prepared',role+'.jsonl.gz'],'rt') as f:rows=[json.loads(s) for s in f]
 z=np.load(wanted['e3',role+'.npy'],mmap_mode='r');q=np.load(wanted['prepared',role+'_q.npy'],mmap_mode='r')
 receipt=read(HERE/'SOURCE_FEATURE_ACCEPTANCE.json');context=np.load(pin(SOURCE/'features8'/(role+'.npy'),receipt['arrays'][role]['sha256']),mmap_mode='r')
 uid=np.load(SOURCE/'metadata'/(role+'.npz'))['uid'];assert np.array_equal(uid,np.asarray([r['uid'] for r in rows],dtype='S64'))
 assert len(rows)==len(z)==len(q)==len(context)
 return rows,z,q,context

def ab(pool):
 rows,z,q,context=source_role(pool);rep=np.load(asset(pool+'_replay'));old=np.load(asset(pool+'_old_logits'));ids=[r['uid'] for r in rows]
 assert rep['uid'].tolist()==old['uid'].tolist()==ids
 keep=rep['primary_indices'];assert len(set(keep))==len(keep)
 w=rep['full_weights'].copy();wp=np.zeros(len(rows));wp[keep]=rep['primary_weights']
 return dict(rows=rows,z=z,q=q,context=extra_normalized(context),support=rep['kernel_support'][rep['candidate_names'].tolist().index('1')].copy(),
             old_raw=old['head'].astype(np.float64),old_c5_pred=rep['decisions'][rep['candidate_names'].tolist().index('3')].copy(),
             views={'full':(np.arange(len(rows)),w),'primary':(keep,wp)})

def edge():
 enc=read(pin(EDGE/'encoded/COMPLETE.json','7b0ffe2288281e8b15d91d8955392710f747604d051ce248b053f7ab9266ca01'))
 original=read(pin(EDGE/'evaluation/METRICS.json','df53579503268da97ef7041102988e61995f3e5356c9200e08678686cdb2c4f8'))
 ids=[];parts={k:[] for k in ['raw_scores','support','RAW','C5_P3']};chunkpins={}
 paths=sorted((EDGE/'evaluation/chunks').glob('q*/MANIFEST.json'));assert len(paths)==469
 for i,p in enumerate(paths):
  m=read(p);chunkpins[str(p)]=sha(p);a=np.load(pin(p.parent/'RESULT.npz',m['sha256']));ids.extend(m['uids'])
  for k in parts:parts[k].append(a[k].copy())
 parts={k:np.concatenate(v) for k,v in parts.items()};assert len(ids)==len(set(ids))==60000 and set(ids)==set(original['ordered_query_uids'])
 pos={u:i for i,u in enumerate(ids)};rows=[None]*len(ids);z=np.empty((len(ids),768),np.float32);q=np.empty((len(ids),14),np.float32);refs=[];rz=[];rq=[];lookup={};batches={}
 for i,b in enumerate(enc['batches']):
  base=EDGE/'encoded/batches'/b['batch_id'];m=read(pin(base/'MANIFEST.json',b['manifest_sha256']))
  for n,v in m['files'].items():pin(base/n,v['sha256'])
  rr=read(base/'rows.json');zz=np.load(base/'E3.npy');qq=np.load(base/'q14.npy');assert [r['uid'] for r in rr]==b['uids']
  batches[b['batch_id']]=b
  for j,r in enumerate(rr):
   lookup[r['uid']]=(b['batch_id'],j)
   if r['uid'] in pos:
    k=pos[r['uid']];assert rows[k] is None;rows[k]=r;z[k]=zz[j];q[k]=qq[j]
   else:assert r['use']=='REFERENCE';refs.append(r);rz.append(zz[j]);rq.append(qq[j])
  if i%100==0:progress('EDGE_CACHE_VERIFY',i,len(enc['batches']))
 assert all(r is not None for r in rows) and len(refs)==4124
 for role in ['NORMAL','HTTP','UDP']:
  mask=np.asarray([r['source_role']==role for r in rows]);assert mask.sum()==20000
  for method in ['RAW','C5_P3']:
   for j,h in enumerate(['27','127','227','ensemble']):assert int(parts[method][mask,j].sum())==original['methods'][method]['heads'][h]['roles'][role]['alarm_count']
 return dict(rows=rows,z=z,q=q,support=parts['support'],old_raw=parts['raw_scores'],old_c5_pred=parts['C5_P3'],
             old_raw_pred=parts['RAW'],refs=refs,rz=np.asarray(rz),rq=np.asarray(rq),lookup=lookup,batches=batches)
