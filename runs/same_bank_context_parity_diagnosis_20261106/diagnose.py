"""Read-only local replay of already-present SHA-pinned arrays. No HPC/data copies."""
from pathlib import Path
import sys,json,gzip,hashlib,types,collections,time
import numpy as np
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];P=ROOT/'runs/same_bank_context_v4_20261106';EVAL=ROOT/'runs/device_context_evaluation_v1_20261105'
sys.path[:0]=[str(P),str(ROOT/'runs/onboarding_new_lineage_v1_20261022/package_v3'),str(ROOT/'repo/ood')]
import history_context as hist,fast_geometry as fast,base_worker as w
import constrained_onboarding_core_v3 as core
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
pins={}
def pin(p,h):
 assert sha(p)==h,str(p);pins[str(p)]=h;return p
def asset(s):return pin(ROOT/s['path'],s['sha256'])
def rr(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def main():
 start=time.monotonic();m=read(EVAL/'OLD_ASSETS.json');s=m['pools']['UNSW_DEV'];rows=rr(asset(s['query']['rows']));z=np.load(asset(s['query']['e3']),mmap_mode='r');q=np.load(asset(s['query']['q14']),mmap_mode='r')
 norm=np.load(asset(m['calibration']['normalizer']));norm=norm['mean'],norm['scale'];geom=read(asset(m['calibration']['geometry']))
 ds=s['dense_bank'];refs=rr(asset(ds['rows']));a=np.load(asset(ds['e3']));assert a['uid'].tolist()==[r['uid'] for r in refs];dense=refs,a['e3'].copy(),a['q14'].copy();a.close()
 c=types.SimpleNamespace(ROOT=ROOT,PROJECT=ROOT,read=read,sha=sha,pin=pin);history=hist.load_history('UNSW_DEV',c);refs,rz,rq=hist.union(dense,history)
 rs=read(EVAL/'ASSET_PLAN.json')['UNSW_DEV_replay'];replay=np.load(pin(ROOT/rs['relative'],rs['sha256']));assert replay['uid'].tolist()==[r['uid'] for r in rows]
 support=replay['kernel_support'][replay['candidate_names'].tolist().index('1')]
 ix=w.select_small(dict(rows=rows));d=dict(rows=[rows[i] for i in ix],z=z[ix],q=q[ix],context=np.zeros((len(ix),8)),support=support[ix],parity_mask=np.zeros(len(ix),bool))
 # Suppress only the external stored-support assertion to inspect discrepancies.
 # This probe cannot produce scientific PASS or launch a full job.
 rhoc={str(p):dict(status='READY',rho_c=1.) for p in [6,17]}
 optimized=fast.evaluate(d,refs,rz,rq,np.zeros((len(refs),8)),norm,geom,rhoc,core,lambda *args,**kw:None)[0]
 ids=[r['uid'] for r in refs];bank=core.ReferenceBank(refs,rz,rq,norm,feature_uids=ids,q_uids=ids,allow_prebank_history=True);uids=[r['uid'] for r in d['rows']]
 original=bank.own(d['rows'],d['z'][:,:768],d['q'],geom,feature_uids=uids,q_uids=uids)
 error=np.abs(optimized['support']-original['support']);assert error.max()<=2e-10
 donor_differences=int(np.count_nonzero(optimized['matched_reference_uids']!=original['matched_reference_uids']))
 bad=np.flatnonzero(np.abs(optimized['support']-d['support'])>2e-10);examples=[]
 for i in bad:
  row=d['rows'][i];examples.append(dict(row=row,saved=float(d['support'][i]),original=float(original['support'][i]),optimized=float(optimized['support'][i]),guard=bool(d['q'][i,0]==1 and d['q'][i,2]==1 and d['q'][i,5]==0),reason=original['reason'][i],matched=original['matched_reference_uids'][i].tolist()))
 out=dict(status='DIAGNOSIS_ONLY',rows=len(ix),mismatch_count=len(bad),optimized_original_max_error=float(error.max()),optimized_original_donor_differences=donor_differences,mismatch_by_device=dict(collections.Counter(v['row']['device'] for v in examples)),mismatch_by_guard=dict(collections.Counter(str(v['guard']) for v in examples)),examples=examples,seconds=time.monotonic()-start,input_pins=pins)
 (HERE/'RESULT.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ['examples','input_pins']}))
 if '--verify-repair' in sys.argv:
  sys.path.insert(0,str(ROOT/'runs/same_bank_context_v5_20261106'));import support_contract as contract
  small=contract.audit('UNSW_DEV',d['rows'],d['q'],optimized['support'],d['support']);assert small['status']=='PASS' and small['excluded_rows']==0
  keep=np.asarray([i for i,r in enumerate(rows) if r['device'] not in contract.C4_DEVICES]);dd=dict(rows=[rows[i] for i in keep],z=z[keep],q=q[keep],context=np.zeros((len(keep),8)),support=support[keep],parity_mask=np.zeros(len(keep),bool))
  full=fast.evaluate(dd,refs,rz,rq,np.zeros((len(refs),8)),norm,geom,rhoc,core,lambda *a,**kw:None)[0]
  untouched=contract.audit('UNSW_DEV',dd['rows'],dd['q'],full['support'],dd['support']);assert untouched['status']=='PASS' and untouched['excluded_rows']==0
  a=m['pools']['CIC_DEV'];ar=rr(asset(a['query']['rows']));aq=np.load(asset(a['query']['q14']),mmap_mode='r');spec=read(EVAL/'ASSET_PLAN.json')['CIC_DEV_replay'];saved=np.load(pin(ROOT/spec['relative'],spec['sha256']));assert saved['uid'].tolist()==[r['uid'] for r in ar]
  av=saved['kernel_support'][saved['candidate_names'].tolist().index('1')];ag=(aq[:,0]==1)&(aq[:,2]==1)&(aq[:,5]==0);assert np.all(av[ag]==0.)
  result=dict(status='PASS',B_real_960=small,B_all_untouched=untouched,A_full_guarded_rows=int(ag.sum()),A_full_guard_stored_zero=True,excluded_rows=0,scope='real frozen arrays; all B untouched rows and A full guard storage; no model or dataset fitting',seconds=time.monotonic()-start)
  (HERE/'REPAIR_VALIDATION.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
