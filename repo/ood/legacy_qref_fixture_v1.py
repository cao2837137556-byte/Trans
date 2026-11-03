"""Small generated 768-D fixture; never reads real features/checkpoints/logits."""
from copy import deepcopy
import hashlib
import math
import numpy as np
import torch
import legacy_qref_common_v1 as c
from legacy_qref_data_v1 import split, class_weights


def fixture(recipe):
    r=deepcopy(recipe);r['synthetic_only']=True
    hp=r['training']['hyperparameters'];hp['epochs']=2;hp['batch_size']=16
    devices=['Amcrest Camera','Philips Hue Bridge','SimCam','Atomi Coffee Maker','ArloQ Camera','Globe Lamp']
    devs=['Eufy Home Base','HeimVision Camera']; refs=[];learn=[];dev=[]
    def row(d,partition,i,label=0,reference=False):
        uid=hashlib.sha256((d+partition+str(i)+str(reference)).encode()).hexdigest()
        return dict(uid=uid,device=d,owner=d,partition=partition,use='REFERENCE' if reference else 'QUERY',
            protocol=17,label=label,timestamp=float(i)/100 if reference else 100.+i,reference_end=1.,
            component_id=uid,session_id=uid,capture_id=d+'_capture',activity='WAN_WATCH' if not label else 'UDP',
            normal_activity_stratum='reference_not_covered',reference_dependency_stratum='different_canonical_component')
    for d in devices+devs:
        part='LEARN' if d in devices else 'DEV'
        refs.extend(row(d,part,i,reference=True) for i in range(3))
        dest=learn if part=='LEARN' else dev
        dest.extend(row(d,part,i,label=i%2) for i in range(24 if part=='LEARN' else 12))
    roles=split(learn,[a for a in refs if a['partition']=='LEARN'],r['data']['split_salt'])
    for role,ix in roles.items():
        for i in ix:learn[int(i)]['fit_role']=role
    for rows in (learn,dev):
        for label in (0,1):
            rr=[x for x in rows if x['label']==label]
            for x,w in zip(rr,class_weights(rr)):
                x['label_metric_weight_denominator']=round(1/w)
    generator=torch.Generator().manual_seed(27)
    def tensors(rows):
        z=torch.randn((len(rows),768),generator=generator)*.01
        for i,x in enumerate(rows):z[i,0]=1. if x['label']==0 else -1.
        return z,torch.zeros((len(rows),128)),torch.zeros(len(rows))
    ts={k:tensors(v) for k,v in [('LEARN',learn),('DEV',dev),('REFERENCE',refs)]}
    fit=[learn[int(i)] for i in roles['FIT']];cal=[learn[int(i)] for i in roles['CAL']]
    r['data']['FIT']={'rows':len(fit),'normal':sum(x['label']==0 for x in fit),'attack':sum(x['label']==1 for x in fit)}
    r['data']['CAL']={'rows':len(cal),'normal':sum(x['label']==0 for x in cal),'attack':sum(x['label']==1 for x in cal),
                    'attack_donor_pairs':sum(x['label']==1 for x in cal)*len(devices)}
    r['data']['DEV']={'rows':len(dev),'normal':12,'attack':12}
    helper_updates=0
    for f in r['hard_normal_helpers']['folds']:
        tr=[x for x in fit if x['device'] in f['training_devices']]
        he=[x for x in fit if x['device'] in f['held_devices']]
        f.update(train_rows=len(tr),train_uid_sha256=c.uid_sha(x['uid'] for x in tr),oof_fit_rows=len(he),
            oof_uid_sha256=c.uid_sha(x['uid'] for x in he),updates_per_seed=hp['epochs']*math.ceil(len(tr)/hp['batch_size']))
        helper_updates+=3*f['updates_per_seed']
    vupdates=hp['epochs']*math.ceil(len(fit)/hp['batch_size'])
    r['training'].update(FIT_rows=len(fit),updates_per_verifier=vupdates,helper_updates=helper_updates,
        verifier_updates=6*vupdates,total_updates=helper_updates+6*vupdates)
    controls=[]
    for d in devs:
        own=[x['uid'] for x in refs if x['device']==d]
        wrong=[x['uid'] for x in refs if x['device']==devices[0]]
        queries=[x for x in dev if x['device']==d]
        controls.append(dict(status='MATCHED',device=d,protocol=17,rows=len(queries),count=3,donor=devices[0],
            query_uid_sha256=c.uid_sha(x['uid'] for x in queries),correct_reference_uids=own,wrong_reference_uids=wrong))
    r['evaluation']['controls']=controls
    r['evaluation']['system_gate'].update(focal_normal_denominator=6,focal_baseline_FP=6,focal_Eufy_WAN_WATCH_FP_max=3)
    # Fixture baseline alerts on everything; useful for exercising both retention and veto.
    q={role:{name:np.zeros(len(rows),dtype=np.float32) for name in ['Q']+['Q_'+str(s) for s in c.SEEDS]}
       for role,rows in [('LEARN',learn),('DEV',dev)]}
    return r,dict(rows={'LEARN':learn,'DEV':dev,'REFERENCE':refs},tensors=ts,roles=roles,q=q,base=None)


def main():
    import argparse
    from pathlib import Path
    from legacy_qref_runner_v1 import run_chain
    p=argparse.ArgumentParser();p.add_argument('--recipe',required=True);p.add_argument('--out',required=True)
    p.add_argument('--inject-failure');a=p.parse_args()
    source=Path(a.recipe);c.pin(source,c.RECIPE_SHA)
    recipe,inputs=fixture(c.read(source))
    progress=c.Progress(a.out,recipe['training']['total_updates'],hours=.5)
    c.write(progress.out/'synthetic_recipe.json',recipe)
    try:
        run_chain(recipe,inputs,progress,synthetic=True,inject_failure=a.inject_failure)
    except BaseException as exc:
        progress.finish('STOPPED_NO_RETRY',error=repr(exc),synthetic_only=True)
        raise
    print('SYNTHETIC_CHAIN_COMPLETE',a.out)


if __name__=='__main__':main()
