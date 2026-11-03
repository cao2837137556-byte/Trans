"""Read-only C3 saved-array integration check; no distances or inference."""
import json
import numpy as np
from run import PACKAGE,ROOT,read,rows,require,load_assets,corrected,report,saved_dev,old_references

def main():
    assets=load_assets();frozen=assets.calibration()
    oldroot=ROOT/'runs/history_normal_reference_c3_progress_repair_v1_20261101/output'
    expected=read(oldroot/'RESULT.json')['pools'];checks={}
    for pool in ('CIC_DEV','UNSW_DEV'):
        spec=assets.spec['pools'][pool];rr=assets.inputs.rows(spec['query']['rows'])
        q=np.load(assets.inputs.pin(spec['query']['q14']),allow_pickle=False)
        with np.load(oldroot/'ab'/pool/'DECISIONS.npz',allow_pickle=False) as z:old={k:z[k].copy() for k in z.files}
        logits,dec,g=corrected(old['raw_logits'],q,old['support'],frozen)
        require(np.array_equal(logits,old['corrected_logits']) and np.array_equal(dec,old['corrected']) and np.array_equal(g,old['guard']),'BASELINE_ALGEBRA')
        actual=report(pool,dict(rows=rr),old,dec,old['support'],old['eligible'],spec)
        for view,v in actual['views'].items():
            prior=expected[pool]['views'][view]
            require(all(prior[k]==v[k] for k in ('rows','retained_uid_sha256','weights_sha256')),'BASELINE_POPULATION')
            for head,r in v['reports'].items():
                require(all(prior['reports'][head][k]==value for k,value in r.items()),'BASELINE_METRICS')
        checks[pool]=dict(rows=len(rr),all_four_heads_and_both_views=True)
    if (PACKAGE/'INPUT_MANIFEST.json').exists():
        inputs=read(PACKAGE/'INPUT_MANIFEST.json');dev,saved=saved_dev(inputs);refs=old_references()
        checks['old_history']=dict(dev=len(dev['rows']),references=len(refs['rows']))
    assets.immutable();print(json.dumps(dict(status='PASS',checks=checks,new_distances=0,model_forwards=0)))

if __name__=='__main__':main()
