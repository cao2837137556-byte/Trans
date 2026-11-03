"""Generated feature/model fixture; never loads traffic, checkpoints or labels."""
from copy import deepcopy
import numpy as np
import torch
import legacy_qref_common_v1 as c
from legacy_qref_data_v1 import class_weights
from legacy_qref_model_v1 import Metric
from legacy_reference_executor_model_v1 import FrozenR,Residual

def fixture(plan,qrecipe):
    plan=deepcopy(plan);rows=[];refs=[];donors=[]
    counts={'Borun Camera':{6:2,17:2},'Netatmo Camera':{6:0,17:2},'Ring Basestation':{6:1,17:0}}
    def row(device,proto,i,label=0,reference=False,part='DEVICE_HOLDOUT'):
        uid=c.digest([device,proto,i,label,reference,part])
        return dict(uid=uid,device=device,protocol=proto,partition=part,use='REFERENCE' if reference else 'QUERY',
            label=label,timestamp=1.+i*.01 if reference else 100.+i,reference_end=10.,component_id=uid,
            session_id=uid,capture_id=device+str(proto)+str(label),activity='NORMAL' if not label else str(proto),
            normal_activity_stratum='unknown',reference_dependency_stratum='different',packet_sha256=uid)
    for name,protos in counts.items():
        for proto,n in protos.items():
            refs.extend(row(name,proto,i,reference=True) for i in range(n))
            rows.extend(row(name,proto,i,label=i%2) for i in range(8))
    for proto in (6,17):donors.extend(row('Synthetic donor',proto,i,reference=True,part='LEARN') for i in range(2))
    for label in (0,1):
        rr=[r for r in rows if r['label']==label]
        for r,w in zip(rr,class_weights(rr)):r['label_metric_weight_denominator']=round(1/w)
    devices=[];controls=[]
    for name,pc in counts.items():
        rr=[r for r in rows if r['device']==name]
        devices.append(dict(device=name,normal=sum(r['label']==0 for r in rr),attack=sum(r['label']==1 for r in rr),references=sum(pc.values()),reference_components_by_protocol={str(k):v for k,v in pc.items()}))
        for proto,n in pc.items():
            if n<2:controls.append(dict(device=name,protocol=proto,status='NOT_APPLICABLE'));continue
            controls.append(dict(device=name,protocol=proto,status='MATCHED',donor='Synthetic donor',count=2,recipient_observation_start=20.,
                correct_reference_uids=[r['uid'] for r in refs if r['device']==name and r['protocol']==proto],
                wrong_reference_uids=[r['uid'] for r in donors if r['protocol']==proto]))
    plan['data'].update(devices=devices,query_rows=len(rows),own_reference_rows=len(refs));plan['arms']['controls']=controls
    plan['synthetic_only']=True
    state=dict(normalizer_mean=np.zeros(768),normalizer_scale=np.ones(768),
        **{'p2__0.weight':np.zeros((128,769),np.float32),'p2__0.bias':np.zeros(128,np.float32),
           'p2__3.weight':np.zeros((1,128),np.float32),'p2__3.bias':np.zeros(1,np.float32)})
    base=FrozenR(state);qs={'Q_'+str(s):Residual('Q').eval().requires_grad_(False) for s in c.SEEDS}
    ms={a+'_'+str(s):Metric(s).eval().requires_grad_(False) for a in ('FULL','NO_CF') for s in c.SEEDS}
    def features(rr):
        x=np.zeros((len(rr),768),np.float32)
        for i,r in enumerate(rr):x[i,0]=1 if r['label']==0 else -1
        return x
    return plan,dict(base=base,qs=qs,ms=ms,rows=rows,features=features(rows),refs=refs,ref_features=features(refs),donors=donors,donor_features=features(donors))

def run(root,out):
    from pathlib import Path
    from legacy_qconfirm_common_v1 import recipe,Progress,validate_metadata
    from legacy_qconfirm_evaluate_v1 import evaluate
    torch.set_num_threads(4);q=c.load_recipe(root);plan,inputs=fixture(recipe(root),q)
    validate_metadata(plan,inputs['rows'],inputs['refs'])
    progress=Progress(out,hours=.5)
    with torch.inference_mode():result=evaluate(plan,q,inputs,Path(out)/'evaluation',progress,synthetic=True)
    progress.finish('COMPLETE',synthetic_only=True,scientific_gate=result['gate']);c.seal(out);c.verify(out)
    return result

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--root',required=True);p.add_argument('--out',required=True);a=p.parse_args()
    run(a.root,a.out);print('CONFIRMATION_SYNTHETIC_COMPLETE; NO_REAL_QUERY_READ; NO_UPDATES')
