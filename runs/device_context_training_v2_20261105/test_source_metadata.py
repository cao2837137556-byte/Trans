"""Full existing metadata regression without materializing new local feature arrays."""
import collections,gzip,hashlib,json,math
from pathlib import Path
import numpy as np
from source_admission import validate_owner,uid_sha,read,write
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 registry=read(HERE/'OWNER_REGISTRY.json');catalog={r['capture_id']:r for r in read(HERE/'RAW_CATALOG.json')};base=ROOT/'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared';spec=read(HERE/'TRAINING_SPEC_FROZEN.json');counts={};shared=collections.Counter();examples=[]
 fit=np.load(base/'FIT.npz')['indices'];cal=np.load(base/'CAL.npz')['indices'];member=np.zeros(len(fit)+len(cal),np.uint8);member[fit]=1;member[cal]=2;assert np.all(member>0)
 for role in ['LEARN','CIC_DEV','UNSW_DEV']:
  uids=[];keys=[];labels=[];branches={0:collections.defaultdict(set),1:collections.defaultdict(set)};keycounts={0:collections.Counter(),1:collections.Counter()}
  with gzip.open(base/(role+'.jsonl.gz'),'rt') as f:
   for i,line in enumerate(f):
    row=json.loads(line);cap=catalog[row['capture_id']];validate_owner(row,cap,registry);assert row['source_sha256']==cap['sha256'] and 0<row['frame']<=cap['expected_packets'] and row['reference_end']<row['timestamp'];uids.append(row['uid'])
    if not cap.get('owner') and not cap.get('external'):shared[cap['capture_id']]+=1
    if len(examples)<3 or cap.get('external') and len(examples)<4:examples.append((row,cap))
    if role=='LEARN':
     fr=member[i];assert row['fit_role']==('FIT' if fr==1 else 'CAL');key=(row['device'],row['activity'],row['capture_id'],row['session_id']);keys.append(key);labels.append(row['label'])
     if fr==1:
      label=row['label'];keycounts[label][key]+=1
      for d in range(4):branches[label][key[:d]].add(key[d])
  assert len(uids)==len(set(uids));counts[role]=len(uids)
  if role=='LEARN':
   for name,ix in [('FIT',fit),('CAL',cal)]:assert uid_sha([uids[int(i)] for i in ix])==spec['data_identity'][name]['uid_sha256']
   weights=np.array([.5/(keycounts[labels[int(i)]][keys[int(i)]]*math.prod(len(branches[labels[int(i)]][keys[int(i)][:d]]) for d in range(4))) for i in fit]);assert math.isclose(math.fsum(weights),1,abs_tol=1e-12);digest=hashlib.sha256(weights.tobytes()).hexdigest();assert digest=='a15d8badee167e8a50dafe6862522413a52e72a67e54b6d895efda5546b710de'
 for row,cap in examples:
  bad=dict(row,owner='ff:ff:ff:ff:ff:ff')
  try:validate_owner(bad,cap,registry)
  except (AssertionError,KeyError):pass
  else:raise AssertionError('OWNER_MISMATCH_NOT_REJECTED')
 result=dict(status='PASS',rows=counts,all_rows=sum(counts.values()),shared_capture_counts=dict(shared),fit_cal_uid='EXACT_PARENT',fit_weight_sha256=digest,wrong_owner_rejected=len(examples),raw_packet_gate='PENDING_LINUX',training_started=False)
 write('LOCAL_METADATA_REGRESSION.json',result);print(json.dumps(result))
if __name__=='__main__':main()
