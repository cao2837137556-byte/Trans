"""Independent saved-array verification; no new encoding or distance pairs."""
import json
from pathlib import Path
import numpy as np
from run import PACKAGE,ROOT,read,rows,sha,require,corrected,load_assets,report,verify
from hnr.common import write
from gates import dev_gate,final_gate

def main():
    verify('evaluate');out=PACKAGE/'outputs/evaluation';result=read(out/'RESULT.json')
    receipt=read(out/'STAGE_RECEIPT.json')
    for rel,digest in receipt['outputs'].items():require(sha(out/rel)==digest,'SAVED_OUTPUT_PIN:'+rel)
    inputs=read(PACKAGE/'INPUT_MANIFEST.json');assets=load_assets();frozen=assets.calibration()
    rr=list(rows(out/'dev/QUERIES.jsonl.gz'))
    with np.load(out/'dev/DECISIONS.npz',allow_pickle=False) as z:
        require(z['uid'].tolist()==[r['uid'] for r in rr],'DEV_UID')
        logits,dec,g=corrected(z['raw_logits'],z['q14'],z['support'],frozen)
        require(np.array_equal(logits,z['corrected_logits']) and np.array_equal(dec,z['corrected']) and np.array_equal(g,z['guard']),'DEV_SCORE_REPLAY')
        gate=dev_gate(rr,z['before'],dec)
    require(gate==result['dev']==read(out/'dev/GATE.json'),'DEV_GATE_REPLAY')
    pools={};before_pools=read(ROOT/inputs['c3_result'])['pools'];normals=attacks=0;untouched=True
    if result['AB_evaluated']:
        require(gate['status']=='PASS_DEV','DEV_BEFORE_AB')
        for pool in ('CIC_DEV','UNSW_DEV'):
            spec=assets.spec['pools'][pool];rr=assets.inputs.rows(spec['query']['rows']);q=np.load(assets.inputs.pin(spec['query']['q14']),allow_pickle=False)
            with np.load(out/'ab'/pool/'DECISIONS.npz',allow_pickle=False) as z:now={k:z[k].copy() for k in z.files}
            with np.load(ROOT/inputs['c3_decisions'][pool],allow_pickle=False) as z:old={k:z[k].copy() for k in z.files}
            require(np.array_equal(now['uid'],old['uid']) and now['uid'].tolist()==[r['uid'] for r in rr],'AB_UID')
            require(np.array_equal(now['raw_logits'],old['raw_logits']) and np.array_equal(now['base'],old['base']),'AB_RAW')
            logits,dec,g=corrected(now['raw_logits'],q,now['support'],frozen)
            require(np.array_equal(logits,now['corrected_logits']) and np.array_equal(dec,now['corrected']) and np.array_equal(g,now['guard']),'AB_ALL_HEAD_REPLAY')
            actual=report(pool,dict(rows=rr),old,dec,now['support'],now['eligible'],spec)
            # C3 stores additional historical comparison annotations. Core
            # population/weights and metric fields must reproduce exactly.
            for view,v in actual['views'].items():
                saved=result['pools'][pool]['views'][view]
                require(all(v[k]==saved[k] for k in ('rows','retained_uid_sha256','weights_sha256')),'VIEW_BINDING')
                for suffix,r in v['reports'].items():
                    for key,value in r.items():require(saved['reports'][suffix][key]==value,'REPORT_REPLAY:'+key)
            pools[pool]=actual
            if pool=='CIC_DEV':
                require(sha(out/'ab'/pool/'DECISIONS.npz')==sha(ROOT/inputs['c3_decisions'][pool]),'A_BYTE_EXACT')
            else:
                normal=np.array([r['label']==0 for r in rr]);motion=np.array([r['device'].endswith('ec:1a:59:83:28:11') for r in rr])
                normals=int((normal[:,None]&~old['corrected']&dec).sum());attacks=int((~normal[:,None]&old['corrected']&~dec).sum())
                untouched=np.array_equal(dec[motion],old['corrected'][motion]) and np.array_equal(logits[motion],old['corrected_logits'][motion])
        terminal=final_gate(before_pools,pools,normals,attacks,untouched)
        for key,value in terminal.items():require(result[key]==value,'TERMINAL_REPLAY')
    else:require(gate['status']=='STOP_DEV_FAIL' and not (out/'ab').exists(),'NO_AB_AFTER_DEV_FAIL')
    assets.immutable()
    write(PACKAGE/'FINAL_ACCEPTANCE.json',dict(status='PASS',scientific_status=result['status'],result_sha256=sha(out/'RESULT.json'),
        independent_saved_array_replay=True,new_distance_pairs=0,new_model_forwards=0,AB_evaluated=result['AB_evaluated']))
    print('C4_FINAL_ACCEPTANCE_PASS')

if __name__=='__main__':main()
