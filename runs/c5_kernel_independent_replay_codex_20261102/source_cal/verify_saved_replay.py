"""Read-only matrix/decision/input identity audit; no distances or model calls."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='2'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import hashlib,json,math
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]


def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(8*2**20),b''):h.update(b)
    return h.hexdigest()
def require(x,m):
    if not x:raise RuntimeError(m)


def main():
    sys.path.insert(0,str(ROOT/'repo/ood'))
    import constrained_onboarding_core_v3 as core
    result=read(OUT/'RESULT.json');seal=read(OUT/'INPUT_SEAL.json')
    require(result['status']=='PASS','RESULT_NOT_COMPLETE')
    checks=[]
    for x in seal['inputs']:
        require(sha(ROOT/x['path'])==x['sha256'],'INPUT_DRIFT:'+x['path'])
        checks.append(x['path'])
    output_checks=[]
    for name,want in result['output_sha256'].items():
        require(sha(OUT/name)==want,'OUTPUT_DRIFT:'+name)
        output_checks.append(name)
    support=np.load(OUT/'ATTACK_SUPPORT.npy',mmap_mode='r')
    eligible=np.load(OUT/'ATTACK_ELIGIBLE.npy',mmap_mode='r')
    joint=np.load(OUT/'ATTACK_SECOND_JOINT.npy',mmap_mode='r')
    require(np.array_equal(support,np.clip(1-joint,0,1)),'JOINT_TO_SUPPORT_EXACT')
    require(not np.any(support[~eligible]),'INELIGIBLE_SUPPORT')
    with np.load(OUT/'CAL_FIXED_INPUTS.npz',allow_pickle=False) as z:
        raw=z['raw_logits'];q=z['q14'];base=z['raw_decisions'];ai=z['attack_indices'];ni=z['normal_indices']
    calib=ROOT/'runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/calibration'
    cuts=read(calib/'cuts.json');cut=np.array(cuts['cuts']);scales=read(calib/'scales.json')['scales']
    def decide(x):return np.column_stack((x>cut,core.ordered_ensemble(x)>cuts['ensemble_cut']))
    guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
    with np.load(OUT/'NORMAL_OWN_SUPPORT.npz',allow_pickle=False) as z:
        ns=z['support'].copy();nj=z['second_joint'].copy()
    require(np.array_equal(ns,np.clip(1-nj,0,1)),'NORMAL_JOINT_SUPPORT_EXACT')
    replay={}
    for name in ('p1','p2','p3','p4','positive_saturation'):
        p=None if name=='positive_saturation' else int(name[1:])
        def transform(s):
            if p is None:return (s>0).astype(float)
            if p==1:return s.copy()
            return np.where(s>0,1-(1-s)**p,0.)
        missed=np.zeros((len(ai),4),dtype=bool)
        for j in range(support.shape[1]):
            s=transform(np.clip(1-joint[:,j],0,1));s[guard[ai]]=0
            dec=decide(core.apply_correction(raw[ai],s,scales,.25))
            missed|=base[ai]&~dec&eligible[:,j,None]
        s=transform(np.clip(1-nj,0,1));s[guard[ni]]=0
        normal_dec=decide(core.apply_correction(raw[ni],s,scales,.25))
        with np.load(OUT/(name+'_DECISIONS.npz'),allow_pickle=False) as z:
            require(np.array_equal(z['normal_corrected'],normal_dec),'NORMAL_REPLAY:'+name)
            require(np.array_equal(z['attack_union_added_fn'],missed),'DONOR_UNION_REPLAY:'+name)
        replay[name]=dict(normal_exact=True,attack_all_donor_union_exact=True,
            added_FN_counts=missed.sum(axis=0).tolist())
    # Independently identify cap-reachable UIDs using the same conservative
    # existence-of-positive-support scope as the original source selector.
    pos=np.any((support>0)&eligible,axis=1)
    full=decide(core.apply_correction(raw[ai],pos.astype(float),scales,.25))
    reach=base[ai]&~full
    legacy=read(ROOT/'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science/source_cal/R-DENSE/PREPARATION.json')['legacy_protection']['candidates'][-1]
    counts={s:int(reach[:,k].sum()) for k,s in enumerate(('27','127','227','ensemble'))}
    require(counts==legacy['cap_reachable_detected_attack_count'],'CAP_REACHABLE_ORIGINAL_IDENTITY')
    answer=dict(status='PASS',new_model_forwards=0,new_distance_pairs=0,
        source_support_rebuild_result_sha256=sha(OUT/'RESULT.json'),
        verifier_sha256=sha(Path(__file__)),inputs_post_verified=len(checks),
        outputs_verified=len(output_checks),joint_support_exact=True,
        cap_reachable_counts=counts,kernel_saved_decision_replay=replay)
    (OUT/'SAVED_ARRAY_VERIFICATION.json').write_text(json.dumps(answer,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(answer,indent=2))


if __name__=='__main__':main()
