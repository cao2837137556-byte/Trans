"""Independent saved-source readback and direct Euclidean sample verification."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import numpy as np

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
CAL=ROOT/'runs/c5_kernel_independent_replay_codex_20261102/source_cal'
BANK=ROOT/'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027/evidence179602/science/encode/banks/SOURCE_REFS'
PREP=ROOT/'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared'
sys.path.insert(0,str(ROOT/'repo/ood'))
from constrained_onboarding_core_v3 import class_weights


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(8*2**20),b''):h.update(chunk)
    return h.hexdigest()


def loadrows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:return [json.loads(x) for x in f]


def require(ok,message):
    if not ok:raise RuntimeError(message)


def main():
    result=json.loads((OUT/'SOURCE_CALIBRATION.json').read_text(encoding='utf-8-sig'))
    require(sha(OUT/'SOURCE_KNN_ARRAYS.npz')==result['arrays_sha256'],'ARRAY_IDENTITY')
    seal=json.loads((OUT/'SOURCE_INPUT_SEAL.json').read_text(encoding='utf-8-sig'))
    for name,key in [('knn5.py','implementation_sha256'),('calibrate_source.py','calibration_script_sha256'),
                     ('CONTRACT.json','contract_sha256')]:
        require(sha(OUT/name)==seal[key],'SEALED_IMPLEMENTATION:'+name)
    rows=loadrows(CAL/'CAL_QUERIES.jsonl.gz');refs=loadrows(BANK/'references.jsonl.gz')
    with np.load(CAL/'CAL_FIXED_INPUTS.npz',allow_pickle=False) as z:
        raw=z['raw_decisions'].copy();normal_ix=z['normal_indices'].copy()
    with np.load(OUT/'SOURCE_KNN_ARRAYS.npz',allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in rows],'UID_JOIN')
        distance=z['distance'].copy();output=z['decisions'].copy();reason=z['reason'].copy()
    nw=class_weights([rows[i] for i in normal_ix]);normal_distance=distance[normal_ix]
    finite=np.isfinite(normal_distance)
    require(np.array_equal(output[~np.isfinite(distance)],raw[~np.isfinite(distance)]),'RAW_FALLBACK')
    threshold_minimality=[]
    for j,cut in enumerate(result['cuts']):
        require(cut is not None,'SOURCE_CUT_REQUIRED')
        expected=raw[:,j].copy();mask=np.isfinite(distance);expected[mask]=distance[mask]>cut
        require(np.array_equal(output[:,j],expected),'STRICT_GREATER_DECISIONS')
        target=math.fsum(nw[raw[normal_ix,j]])
        actual=math.fsum(nw[output[normal_ix,j]])
        require(actual<=target+1e-15,'WEIGHTED_FPR_MATCH')
        below=normal_distance[finite & (normal_distance<cut)]
        prior=None if len(below)==0 else float(np.max(below))
        if prior is not None:
            trial=raw[normal_ix,j].copy();trial[finite]=normal_distance[finite]>prior
            require(math.fsum(nw[trial])>target,'CUT_NOT_MINIMAL')
        threshold_minimality.append(dict(cut=cut,previous_distinct=prior,minimal=True))
    e3=np.load(CAL/'CAL_E3.npy',mmap_mode='r',allow_pickle=False)
    with np.load(PREP/'normalizer.npz',allow_pickle=False) as z:mean=z['mean'];scale=z['scale']
    with np.load(BANK/'bank.npz',allow_pickle=False) as z:reference_e3=z['e3'].copy()
    groups={}
    for i,row in enumerate(refs):groups.setdefault((row['partition'],row['device'],row['protocol']),[]).append(i)
    candidate=np.flatnonzero(np.isfinite(distance))
    # Fixed evenly-spaced indices; no selection by distance or alarm outcome.
    sample=candidate[np.linspace(0,len(candidate)-1,min(64,len(candidate)),dtype=np.int64)]
    maximum_error=0.
    for i in sample:
        row=rows[i];key=(row['partition'],row['device'],row['protocol'])
        indices=[j for j in groups[key] if refs[j]['capture_id']!=row['capture_id']
                 or refs[j]['frame']<row['frame']]
        z=(reference_e3[indices].astype(np.float64)-mean)/scale
        z/=np.linalg.norm(z,axis=1)[:,None]
        q=(np.asarray(e3[i],dtype=np.float64)-mean)/scale;q/=np.linalg.norm(q)
        direct=np.sqrt(np.sum((z-q[None,:])**2,axis=1))
        expected=np.sort(direct)[4]
        error=abs(float(expected)-float(distance[i]));maximum_error=max(maximum_error,error)
        require(error<5e-14,'DIRECT_EUCLIDEAN_5TH_NEIGHBOUR')
        require(reason[i]=='KNN5_SCORED','SCORED_REASON')
    verification=dict(status='PASS',array_and_source_join=True,raw_fallback_exact=True,
        strict_threshold_decisions_exact=True,source_normal_weighted_fpr_match=True,
        threshold_minimality=threshold_minimality,direct_euclidean_sample_rows=len(sample),
        maximum_absolute_distance_error=maximum_error,external_arrays_read=False,
        source_result_sha256=sha(OUT/'SOURCE_CALIBRATION.json'))
    (OUT/'VERIFICATION.json').write_text(json.dumps(verification,indent=2)+'\n',encoding='utf8')
    print(json.dumps(verification))


if __name__=='__main__':main()
