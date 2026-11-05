"""Pinned source metadata/weights and raw ownership admission; no fitting or scoring."""
import collections,gc,gzip,hashlib,json,math,os,time
from pathlib import Path
import numpy as np
HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def write(n,d):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(d,indent=2,allow_nan=False));t.replace(p)
def progress(stage,done,total,**kw):write('ADMISSION_PROGRESS.json',dict(stage=stage,done=done,total=total,updated_unix=time.time(),**kw))
def resolve():
 plan=read(HERE/'ASSET_PLAN.json');inv=read(HERE/'INVENTORY.json');result={}
 for i,(k,v) in enumerate(plan.items()):
  progress('ASSET_SHA',i,len(plan),file=v['name']);candidates=inv['files'][k]['candidates']+[str(HERE/'assets'/(k+'.part'))]
  for s in candidates:
   p=Path(s)
   if p.is_file() and p.stat().st_size==v['bytes'] and sha(p)==v['sha256']:result[k]=str(p);break
  assert k in result,'NO_SHA_MATCH:'+k
 write('RESOLVED_ASSETS.json',result);return plan,result
def uid_sha(values):return hashlib.sha256(''.join(u+'\n' for u in sorted(values)).encode()).hexdigest()
def validate_owner(row,capture,registry):
 owner=row['owner'].replace(':','').lower()
 if capture.get('external'):
  assert owner in registry['unsw_known'] and row['device']=='unsw-attack-traces-2018:'+row['owner'].lower(),'UNSW_OWNER_REGISTRY'
 else:
  registered=registry['cic'][row['device']];assert registered['owner']==owner and registered['partition']==row['partition'],'CIC_OWNER_REGISTRY'
  if capture.get('owner') is not None:assert capture['owner'].replace(':','').lower()==owner,'SINGLE_OWNER_CATALOG'
  else:assert capture['mode']=='ACTIVE_UNANNOTATED' and capture['capture_id'].startswith('active-'),'UNREGISTERED_SHARED_CAPTURE'
 return owner
def main():
 start=time.monotonic();plan,paths=resolve();spec=read(HERE/'TRAINING_SPEC_FROZEN.json');catalog=read(HERE/'RAW_CATALOG.json');registry=read(HERE/'OWNER_REGISTRY.json');cat={r['capture_id']:r for r in catalog};assert len(cat)==len(catalog)
 byname={(v['kind'],v['name']):Path(paths[k]) for k,v in plan.items()};queries=collections.defaultdict(list);roles={};all_uid=set();metadata=HERE/'metadata';metadata.mkdir(exist_ok=True);fit=np.load(byname['prepared','FIT.npz'])['indices'];cal=np.load(byname['prepared','CAL.npz'])['indices'];assert not set(fit)&set(cal)
 for role_id,role in enumerate(['LEARN','CIC_DEV','UNSW_DEV']):
  role_total=np.load(byname['e3',role+'.npy'],mmap_mode='r').shape[0]
  rows=[];counts=collections.Counter();uids=[];owners=[];devices=[];scenarios=[];y=[];proto=[];metric=[];fitrole=[];weight_keys=[];branches={0:collections.defaultdict(set),1:collections.defaultdict(set)};keycounts={0:collections.Counter(),1:collections.Counter()}
  if role=='LEARN':membership=np.zeros(len(fit)+len(cal),np.uint8);membership[fit]=1;membership[cal]=2;assert np.all(membership>0)
  with gzip.open(byname['prepared',role+'.jsonl.gz'],'rt') as f:
   for i,line in enumerate(f):
    r=json.loads(line);uid=r['uid'];assert uid not in all_uid,'DUPLICATE_UID';all_uid.add(uid);c=cat[r['capture_id']];assert r['source_sha256']==c['sha256'];owner=r['owner'].replace(':','').lower();assert len(owner)==12 and r['protocol'] in [6,17] and r['use']!='REFERENCE'
    assert validate_owner(r,c,registry)==owner
    fr=int(membership[i]) if role=='LEARN' else 0
    if role=='LEARN':assert r['fit_role']==('FIT' if fr==1 else 'CAL') and r['partition']=='LEARN'
    else:assert r['partition']==('DEV' if role=='CIC_DEV' else 'EXTERNAL_ARCHIVAL_EVALUATION')
    assert 0<r['frame']<=c['expected_packets'] and r['reference_end']<r['timestamp']
    queries[r['capture_id']].append((role_id,i,r['frame'],r['timestamp'],owner,r['protocol'],uid));uids.append(uid);owners.append(owner);devices.append(r['device']);scenarios.append(r['activity']);y.append(r['label']);proto.append(r['protocol']);metric.append(1/r['label_metric_weight_denominator']);fitrole.append(fr);counts[str(fr)+'/'+str(r['label'])+'/'+str(r['protocol'])]+=1
    if role=='LEARN':
     key=(r['device'],r['activity'],r['capture_id'],r['session_id']);weight_keys.append(key)
     if fr==1:
      label=r['label'];keycounts[label][key]+=1
      for depth in range(4):branches[label][key[:depth]].add(key[depth])
    if i%100000==0:progress('METADATA_'+role,i,role_total,unit='rows')
  n=len(uids);z=np.load(byname['e3',role+'.npy'],mmap_mode='r');q=np.load(byname['prepared',role+'_q.npy'],mmap_mode='r');assert z.shape==(n,794) and z.dtype==np.float32 and q.shape==(n,14) and q.dtype==np.float32
  for j in range(0,n,8192):assert np.isfinite(z[j:j+8192]).all() and np.isfinite(q[j:j+8192]).all() and np.all((q[j:j+8192]>=0)&(q[j:j+8192]<=1))
  if role=='LEARN':
   w=np.zeros(n,np.float64)
   for idx in fit:
    i=int(idx);label=y[i];key=weight_keys[i];w[i]=.5/(keycounts[label][key]*math.prod(len(branches[label][key[:d]]) for d in range(4)))
   assert math.isclose(math.fsum(w),1.,abs_tol=1e-12);digest=hashlib.sha256(w[fit].tobytes()).hexdigest();assert digest=='a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de','FIT_WEIGHT_IDENTITY'
   for name,ix in [('FIT',fit),('CAL',cal)]:assert len(ix)==spec['data_identity'][name]['rows'] and uid_sha([uids[int(j)] for j in ix])==spec['data_identity'][name]['uid_sha256'],'FIT_CAL_UID'
   np.save(metadata/'FIT_weights_all.npy',w);np.save(metadata/'FIT.npy',fit);np.save(metadata/'CAL.npy',cal)
  np.savez(metadata/(role+'.npz'),uid=np.asarray(uids,dtype='S64'),owner=np.asarray(owners,dtype='S12'),device=np.asarray(devices),scenario=np.asarray(scenarios),label=np.asarray(y,np.uint8),protocol=np.asarray(proto,np.uint8),metric_weight=np.asarray(metric,np.float64),fit_role=np.asarray(fitrole,np.uint8))
  roles[role]=dict(rows=n,uid_sha256=uid_sha(uids),ordered_uid_sha256=hashlib.sha256(''.join(u+'\n' for u in uids).encode()).hexdigest(),counts=dict(counts),z_sha256=sha(byname['e3',role+'.npy']),q_sha256=sha(byname['prepared',role+'_q.npy']))
  del z,q,uids,owners,devices,scenarios,weight_keys,branches,keycounts;gc.collect()
 querydir=HERE/'queries';querydir.mkdir(exist_ok=True);manifest={}
 for capture,rr in queries.items():
  rr.sort(key=lambda x:(x[2],x[0],x[1]));c=cat[capture];key=next(k for k,v in plan.items() if v['kind']=='raw' and v['sha256']==c['sha256']);f=querydir/(capture+'.npz')
  np.savez(f,role=np.asarray([v[0] for v in rr],np.uint8),index=np.asarray([v[1] for v in rr],np.int64),frame=np.asarray([v[2] for v in rr],np.int64),timestamp=np.asarray([v[3] for v in rr],np.float64),owner=np.asarray([v[4] for v in rr],dtype='S12'),protocol=np.asarray([v[5] for v in rr],np.uint8),uid=np.asarray([v[6] for v in rr],dtype='S64'))
  manifest[capture]=dict(raw_key=key,raw_path=paths[key],source_sha256=c['sha256'],raw_bytes=c['bytes'],expected_frames=c['expected_packets'],queries=len(rr),query_sha256=sha(f),owners=sorted({v[4] for v in rr}))
 write('QUERY_MANIFEST.json',manifest)
 result=dict(status='PASS',phase='ADMISSION',seconds=time.monotonic()-start,assets_verified=len(paths),raw_catalog=len(cat),queried_captures=len(queries),roles=roles,fit_weight_sha256=digest,query_manifest_sha256=sha(HERE/'QUERY_MANIFEST.json'),training_started=False,notes='Metadata and whole-asset SHA gate; per-packet direction/parser/clock qualification follows before training')
 write('ADMISSION_RESULT.json',result);progress('PASS',1,1)
if __name__=='__main__':
 import traceback
 try:main()
 except Exception as e:write('ADMISSION_STOP.json',dict(status='FAIL',error=repr(e),traceback=traceback.format_exc()));raise
