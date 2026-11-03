"""Cache-only, explicitly authorized chain; synthetic fixtures use the same stages."""
from pathlib import Path
import argparse
import json
import math
import sys
import numpy as np
import torch
import legacy_qref_common_v1 as c
from legacy_qref_data_v1 import load_cache, validate_controls
from legacy_qref_model_v1 import Bank, Raw
from legacy_qref_train_v1 import train, helper_predictions, q_forward
from legacy_qref_evaluate_v1 import calibrate, evaluate, score_models
from legacy_reference_executor_model_v1 import FrozenR, Residual, probability


def authorize(root,cache,out,authorization,execute):
    c.require(execute and authorization is not None,'REAL_EXECUTION_NOT_AUTHORIZED')
    scope=c.read(authorization)
    c.require(scope.get('execution_authorized') is True and scope.get('recipe_sha256')==c.RECIPE_SHA,'SCOPE_AUTHORITY')
    c.require(scope.get('stages')==['CACHE_PARITY','HELPERS','VERIFIERS','CAL','DEV'] and scope.get('retries')==0 and scope.get('holdout') is False,'SCOPE_STAGES')
    for name,path in [('root',root),('cache',cache),('output',out)]:
        c.require(Path(scope[name]).resolve()==Path(path).resolve(),'SCOPE_PATH_'+name)
    impl=Path(root)/c.IMPLEMENTATION_REL
    c.verify(impl)
    acceptance=c.read(impl/'acceptance.json')
    c.require(acceptance['status']=='PASS' and acceptance['real_model_forwards']==0 and acceptance['real_optimizer_steps']==0,'IMPLEMENTATION_ACCEPTANCE')
    for path,h in c.read(impl/'code_pins.json').items():
        c.pin(c.confined(root,path),h)
    c.require(not Path(out).exists(),'OUTPUT_EXISTS_NO_RETRY')


def model_from_arrays(path,kind):
    from legacy_qref_model_v1 import Metric
    model=Residual('Q') if kind=='Q' else Metric(27)
    with np.load(path,allow_pickle=False) as a:
        c.require(set(a.files)==set(model.state_dict()),'HEAD_KEYS')
        state={k:torch.from_numpy(a[k].copy()) for k in a.files}
    c.require(all(bool(torch.isfinite(v).all()) for v in state.values()),'HEAD_NONFINITE')
    model.load_state_dict(state,strict=True); return model.eval()


def derive(base,features,progress):
    n=len(features); z=torch.empty((n,768)); h=torch.empty((n,128)); b=torch.empty(n)
    for start in range(0,n,256):
        end=min(start+256,n)
        zz,hh,bb=base.inputs(np.array(features[start:end],dtype=np.float32))
        c.require(bool(torch.isfinite(zz).all()) and bool(torch.isfinite(hh).all()) and bool(torch.isfinite(bb).all()),'BASE_NONFINITE')
        z[start:end]=zz;h[start:end]=hh;b[start:end]=bb
        progress.tick()
    return z,h,b


def q_scores(models,z,h,b,progress,registered=None):
    if registered is None:registered=torch.ones(len(z),dtype=torch.bool)
    c.require(registered.shape==(len(z),) and registered.dtype==torch.bool,'REGISTRATION_MASK')
    scores={name:[] for name in models}
    with torch.inference_mode():
        for start in range(0,len(z),256):
            end=start+256
            for name,m in models.items():
                scores[name].append(q_forward(m,z[start:end],h[start:end],b[start:end],registered[start:end]).numpy())
            progress.tick()
    scores={k:np.concatenate(v) for k,v in scores.items()}
    scores['Q']=np.stack([scores['Q_'+str(s)] for s in c.SEEDS]).mean(0,dtype=np.float32)
    # Averaging three equal float32 values can still round differently from the original.
    scores['Q'][~registered.numpy()]=b.numpy()[~registered.numpy()]
    return scores


def runtime_probe(recipe):
    """Target-runtime synthetic numerical check before real checkpoint/cache loading."""
    from legacy_qref_model_v1 import Metric, protected_cut, veto
    from legacy_qref_fixture_v1 import fixture
    c.require(sys.version_info >= (3,9),'PYTHON_39_REQUIRED')
    torch.set_num_threads(4);torch.use_deterministic_algorithms(True)
    mini,inputs=fixture(recipe)
    refs=inputs['rows']['REFERENCE'];ix=[i for i,r in enumerate(refs) if r['partition']=='LEARN']
    bank=Bank([refs[i] for i in ix],inputs['tensors']['REFERENCE'][0][ix],{'LEARN'})
    rows=inputs['rows']['LEARN'][:8];z=inputs['tensors']['LEARN'][0][:8].clone().requires_grad_(True)
    model=Metric(27);scores,valid=bank.own(z,rows,model,mini,minimum=1)
    c.require(bool(valid.all()) and bool(torch.isfinite(scores).all()),'RUNTIME_SCORE')
    scores.sum().backward()
    c.require(bool(torch.isfinite(model.W.grad).all()) and bool(torch.isfinite(z.grad).all()),'RUNTIME_GRADIENT')
    cut=protected_cut([0.,.9]);c.require(bool(veto([True],[.9],[True],cut)[0]),'RUNTIME_CUT')
    c.require(np.array_equal(np.stack([np.zeros(3,dtype=np.float32)]*3).mean(0,dtype=np.float32),np.zeros(3,dtype=np.float32)),'RUNTIME_Q_AVERAGE')
    return dict(status='PASS',python=sys.version,numpy=np.__version__,torch=torch.__version__,synthetic_only=True,
        real_checkpoint_reads=0,real_feature_reads=0,optimizer_updates=0)


def real_inputs(root,cache,recipe,progress):
    root=Path(root)
    # Verify report dependencies and replay files BEFORE any real forward.
    pins=c.read(root/c.IMPLEMENTATION_REL/'input_pins.json')
    for path,h in pins.items():
        c.pin(c.confined(root,path),h)
    from legacy_qref_delivery_v1 import coverage
    report_coverage=coverage(root,pins)
    for key in ('census','metadata_review'):
        p=recipe['data'][key];c.pin(c.confined(root,p['path']),p['sha256'])
    loaded,roles=load_cache(root,cache,recipe)
    state_path=c.confined(root,recipe['immutable']['legacy']['probe_state_path'])
    c.pin(state_path,recipe['immutable']['legacy']['probe_state_sha256'])
    from legacy_reference_executor_common_v1 import STATE_KEYS
    with np.load(state_path,allow_pickle=False) as a:
        state={k:a[k].copy() for k in STATE_KEYS}
    base=FrozenR(state)
    models={}
    for seed in c.SEEDS:
        spec=recipe['immutable']['Q_heads'][str(seed)]
        models['Q_'+str(seed)]=model_from_arrays(c.pin(c.confined(root,spec['path']),spec['sha256']),'Q')
    tensors={};q={}; parity={}
    for role in ('REFERENCE','LEARN','DEV'):
        progress.stage='CACHE_PARITY_'+role;progress.emit()
        tensors[role]=derive(base,loaded[role][1],progress)
        if role!='REFERENCE':
            q[role]=q_scores(models,*tensors[role],progress)
            rel='runs/legacy_reference_hpc_preparation_v1_20260918/pullback/extracted/runs/real_dev/evaluation_'+role+'/logits.npz'
            with np.load(c.confined(root,rel),allow_pickle=False) as old:
                c.require(np.array_equal(old['uid'],[r['uid'] for r in loaded[role][0]]),'Q_REPLAY_UID')
                for name,value in q[role].items():
                    c.require(np.array_equal(value,old[name]),'Q_NUMERIC_REPLAY_'+role+'_'+name)
            parity[role]='EXACT_FLOAT32_EQUAL'
    c.write(progress.out/'base_parity.json',dict(status='PASS',parity=parity,no_E3_forward=True))
    validate_controls(loaded['DEV'][0],loaded['REFERENCE'][0],recipe)
    base.unchanged(); progress.finish_stage('CACHE_PARITY')
    return dict(rows={k:v[0] for k,v in loaded.items()},tensors=tensors,roles=roles,q=q,base=base,coverage=report_coverage)


def run_chain(recipe,inputs,progress,synthetic=False,inject_failure=None):
    """No holdout input/branch. Production inputs only obtained after authorize()."""
    rr=inputs['rows']['REFERENCE']; ref_z=inputs['tensors']['REFERENCE'][0]
    ri=[i for i,r in enumerate(rr) if r['partition']=='LEARN']
    learn_bank=Bank([rr[i] for i in ri],ref_z[ri],{'LEARN'})
    all_bank=Bank(rr,ref_z,{'LEARN','DEV'})
    learn=inputs['rows']['LEARN']; roles=inputs['roles']; fit=[learn[int(i)] for i in roles['FIT']]
    fit_t=tuple(v[roles['FIT']] for v in inputs['tensors']['LEARN'])
    hard=set(); endpoints={};helper_receipts=[]
    for fold in recipe['hard_normal_helpers']['folds']:
        ix=[i for i,r in enumerate(fit) if r['device'] in fold['training_devices']]
        subset=[fit[i] for i in ix]
        c.require(len(ix)==fold['train_rows'] and c.uid_sha(r['uid'] for r in subset)==fold['train_uid_sha256'],'FOLD_TRAIN_IDENTITY')
        held=[i for i,r in enumerate(fit) if r['device'] in fold['held_devices']]
        c.require(len(held)==fold['oof_fit_rows'] and c.uid_sha(fit[i]['uid'] for i in held)==fold['oof_uid_sha256'],'FOLD_OOF_IDENTITY')
        normal=[i for i in held if fit[i]['label']==0]; models=[]
        for seed in c.SEEDS:
            name='HELPER_%s_%s'%(fold['fold'],seed);progress.stage=name;progress.emit()
            if inject_failure==name:raise c.Stop('INJECTED_SYNTHETIC_FAILURE')
            m,receipt=train(recipe,subset,*(v[ix] for v in fit_t),learn_bank,'HELPER',seed,progress.out/name,progress,
                held_devices=fold['held_devices'],synthetic=synthetic)
            c.require(receipt['updates']==fold['updates_per_seed'],'HELPER_UPDATE_COUNT')
            models.append(m);helper_receipts.append(receipt);progress.finish_stage(name)
        hard |= helper_predictions(models,[fit[i] for i in normal],*(v[normal] for v in fit_t),
            recipe['immutable']['legacy']['threshold_probability'],progress)
    hrows=[r for r in fit if r['uid'] in hard]
    hdir=progress.out/'hard_normals';hdir.mkdir()
    groups={}
    for r in hrows:
        key=r['device']+'|'+r['activity'];groups[key]=groups.get(key,0)+1
    c.write(hdir/'hard.json',dict(uids=sorted(hard),uid_sha256=c.uid_sha(hard),rows=len(hard),
        devices=sorted({r['device'] for r in hrows}),components=len({r['component_id'] for r in hrows}),
        device_activity_counts=groups,helper_endpoints=helper_receipts))
    c.seal(hdir);c.verify(hdir)
    gate=recipe['hard_normal_helpers']['feasibility_gate']
    c.require(len({r['device'] for r in hrows})>=gate['min_H_devices'] and
        len({r['component_id'] for r in hrows})>=gate['min_H_components'],'STOP_NO_HARD_TRANSFER_SIGNAL')
    progress.finish_stage('H_GATE')
    receipts={}
    for arm in ('FULL','NO_CF'):
        for seed in c.SEEDS:
            name=arm+'_'+str(seed);progress.stage=name;progress.emit()
            m,receipt=train(recipe,fit,*fit_t,learn_bank,arm,seed,progress.out/name,progress,hard=hard,synthetic=synthetic)
            c.require(receipt['updates']==recipe['training']['updates_per_verifier'],'VERIFIER_UPDATE_COUNT')
            endpoints[name]=m;receipts[name]=receipt;progress.finish_stage(name)
    for seed in c.SEEDS:
        a=receipts['FULL_'+str(seed)];b=receipts['NO_CF_'+str(seed)]
        c.require(all(a[k]==b[k] for k in ('order_hashes','subset_hashes','weight_sha256','uid_sha256')),'UNMATCHED_EXPOSURE')
    for name in endpoints:c.verify(progress.out/name)
    c.verify(hdir)
    cal=[learn[int(i)] for i in roles['CAL']];cal_z=inputs['tensors']['LEARN'][0][roles['CAL']]
    progress.stage='CAL';progress.emit()
    cuts=calibrate(endpoints,cal_z,cal,learn_bank,recipe,progress.out/'calibration',progress,synthetic)
    progress.finish_stage('CAL')
    ni=[i for i,r in enumerate(cal) if r['label']==0]
    if ni:
        evidence,valid=score_models(dict(endpoints,RAW=Raw()),cal_z[ni],[cal[i] for i in ni],learn_bank,recipe,progress)
        c.write(progress.out/'CAL_normal_diagnostic.json',dict(rows=len(ni),eligible=int(valid.sum()),
            diagnostics={k:dict(above_cut=int(((v>cuts[k])&valid).sum()),cut=cuts[k]) for k,v in evidence.items()},
            used_for_cut_selection=False))
    progress.stage='DEV';progress.emit()
    result=evaluate(endpoints,inputs['tensors']['DEV'][0],inputs['rows']['DEV'],all_bank,recipe,
        inputs['q']['DEV'],cuts,progress.out/'evaluation_DEV',progress,synthetic,coverage=inputs.get('coverage'))
    progress.finish_stage('DEV')
    if inputs.get('base') is not None:inputs['base'].unchanged()
    c.require(progress.done==recipe['training']['total_updates'],'CHAIN_UPDATE_COUNT')
    progress.guard();progress.finish('COMPLETE',scientific_gate=result['gate'],synthetic_only=synthetic)
    c.seal(progress.out);c.verify(progress.out)
    return result


def execute(root,cache,out,authorization,explicit):
    authorize(root,cache,out,authorization,explicit)
    recipe=c.load_recipe(root); rt=recipe['runtime_plan']['proposed_HPC']
    progress=c.Progress(out,recipe['training']['total_updates'],rt['wall_limit_hours'],rt['RAM_GiB'],rt['new_output_disk_limit_GiB'])
    try:
        progress.stage='TARGET_RUNTIME_SYNTHETIC_CHECK';progress.emit()
        c.write(progress.out/'target_runtime.json',runtime_probe(recipe))
        progress.finish_stage('TARGET_RUNTIME_SYNTHETIC_CHECK')
        inputs=real_inputs(root,cache,recipe,progress)
        return run_chain(recipe,inputs,progress)
    except BaseException as exc:
        progress.finish('STOPPED_NO_RETRY',error=repr(exc),synthetic_only=False)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    s=sub.add_parser('status');s.add_argument('--out',required=True)
    x=sub.add_parser('run');x.add_argument('--root',required=True);x.add_argument('--cache',required=True)
    x.add_argument('--out',required=True);x.add_argument('--authorization',required=True);x.add_argument('--execute',action='store_true')
    args=p.parse_args()
    if args.command=='status':print(json.dumps(c.status(args.out),ensure_ascii=False,indent=2))
    else:execute(args.root,args.cache,args.out,args.authorization,args.execute)


if __name__=='__main__':main()
