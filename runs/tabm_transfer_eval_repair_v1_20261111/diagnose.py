import sys,json,hashlib
from pathlib import Path
root=Path('/public/home/jiangxinwei.zr/work/paper04')
sys.path.insert(0,str(root/'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201'))
import numpy as np
old=root/'runs/tabm_3d_transfer_v1_20261111';p4=root/'runs/p4_complete_bank_v1_20261111';out=root/'runs/tabm_transfer_eval_repair_v1_20261111';out.mkdir(exist_ok=True)
r=json.loads((old/'results/SCALE_AND_THRESHOLD_FREEZE.json').read_text());scales=np.asarray(r['mlp_own_scales']);cuts=np.asarray(r['mlp_cuts']);results={}
for pool in ['CIC_DEV','UNSW_DEV','EDGE']:
 with np.load(p4/'artifacts'/(pool+'_QUERY.npz')) as q:qq=q['q'];s=q['support3']
 with np.load(root/'runs/same_bank_context_v6_20261106'/(pool+'_SAME_BANK.npz')) as a:raw=a['RAW'];stored=a['C5_3D_FUSION']
 g=np.where(s>0,1.-np.power(1.-s,3),0.);x=raw[:,:3].copy()
 for j,b in enumerate(scales):x[g>0,j]=raw[g>0,j]-(.25*b)*g[g>0]
 guard=(qq[:,0]==1)&(qq[:,2]==1)&(qq[:,5]==0);x[guard]=raw[guard,:3];new=np.column_stack((x,np.stack([x[:,j] for j in range(3)]).mean(0,dtype=np.float64)))
 diff=new-stored;ix=np.flatnonzero((g>1e-8)&~guard)
 implied=[float(np.median((raw[ix,j]-stored[ix,j])/(.25*g[ix]))) for j in range(3)]
 bad=np.argwhere(diff!=0);examples=[dict(row=int(i),head=int(j),new=float(new[i,j]),saved=float(stored[i,j]),diff=float(diff[i,j])) for i,j in bad[:4]]
 results[pool]=dict(max_error=float(np.max(np.abs(diff))),differing_values=len(bad),decision_flips=int(np.count_nonzero((new>cuts)!=(stored>cuts))),implied_scale=implied,expected_scale=scales.tolist(),support_dtype=str(s.dtype),examples=examples)
(out/'ARITHMETIC_DIAGNOSIS.json').write_text(json.dumps(results,indent=2));print('ARITHMETIC_DIAGNOSIS',json.dumps(results))
