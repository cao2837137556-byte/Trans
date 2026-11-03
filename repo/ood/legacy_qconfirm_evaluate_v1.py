"""Frozen inference only; no training or calibration entry point."""
from pathlib import Path
import numpy as np
import torch
import legacy_qref_common_v1 as c
from legacy_qref_model_v1 import Bank,Raw,veto
from legacy_qref_evaluate_v1 import score_models
from legacy_qref_runner_v1 import derive,q_scores,model_from_arrays
from legacy_reference_executor_model_v1 import FrozenR,probability
from legacy_reference_executor_common_v1 import STATE_KEYS
from legacy_qconfirm_common_v1 import validate_controls
from legacy_qconfirm_report_v1 import group_tables,gate

def models(root,plan,qrecipe):
    for n,h in plan['immutable']['artifact_pins'].items():c.pin(c.confined(root,n),h)
    qs={};ms={}
    for seed in c.SEEDS:qs['Q_'+str(seed)]=model_from_arrays(c.confined(root,qrecipe['immutable']['Q_heads'][str(seed)]['path']),'Q').requires_grad_(False)
    for name in [a+'_'+str(s) for a in ('FULL','NO_CF') for s in c.SEEDS]:
        rel=next(p for p in plan['immutable']['artifact_pins'] if p.endswith('/'+name+'/head.npz'))
        ms[name]=model_from_arrays(c.confined(root,rel),'METRIC').requires_grad_(False)
    path=c.confined(root,qrecipe['immutable']['legacy']['probe_state_path'])
    with np.load(path,allow_pickle=False) as f:state={k:f[k].copy() for k in STATE_KEYS}
    return FrozenR(state),qs,ms

def predict(plan,qrecipe,base,qs,ms,rows,features,refs,ref_features,donors,donor_features,progress):
    allrefs=refs+donors;validate_controls(plan,allrefs)
    progress.begin('FROZEN_R_QUERY_INPUTS',(len(rows)+255)//256);z,h,b=derive(base,features,progress)
    progress.begin('FROZEN_R_REFERENCE_INPUTS',1);rz=derive(base,np.concatenate([ref_features,donor_features]),progress)[0]
    ends={r['device']:r['reference_end'] for r in refs}
    registered=torch.tensor([r['device'] in ends and ends[r['device']]<r['timestamp'] for r in rows])
    progress.begin('FROZEN_Q',(len(rows)+255)//256);logits=q_scores(qs,z,h,b,progress,registered)
    theta=plan['immutable']['Q_probability_threshold'];qb={k:probability(v)>=theta for k,v in logits.items()}
    predictions=dict(qb,R=probability(b.numpy())>=theta);bases={k:qb[k] for k in qb};bases['R']=qb['Q']
    bank=Bank(allrefs,rz,{'DEVICE_HOLDOUT','LEARN'});cuts=plan['immutable']['cuts'];scores_out={};validity={};cut_out={}
    progress.begin('FROZEN_REFERENCE_SCORES',(len(rows)+255)//256)
    scores,valid=score_models(dict(ms,RAW=Raw()),z,rows,bank,qrecipe,progress)
    def add(name,score,mask,cut,base_pred):
        predictions[name]=veto(base_pred,score,mask,cut);bases[name]=base_pred;scores_out[name]=score;validity[name]=mask;cut_out[name]=cut
    for name,s in scores.items():
        seed=name.rsplit('_',1)[-1];qbase=qb['Q_'+seed] if seed in ('27','127','227') else qb['Q']
        add(name,s,valid,cuts[name],qbase)
    add('FULL_empty_inner',scores['FULL'],np.zeros(len(rows),bool),cuts['FULL'],qb['Q'])
    full={k:v for k,v in ms.items() if k.startswith('FULL_')}
    progress.begin('BUDGET16',(len(rows)+255)//256)
    small,mask=score_models(full,z,rows,bank,qrecipe,progress,budget=16)
    add('FULL_budget16_per_protocol',small['FULL'],mask,cuts['FULL'],qb['Q'])
    for which in ('correct','wrong'):
        progress.begin('MATCHED_'+which.upper(),(len(rows)+255)//256)
        override={(x['device'],x['protocol']):x[which+'_reference_uids'] for x in plan['arms']['controls'] if x['status']=='MATCHED'}
        v,mask=score_models(full,z,rows,bank,qrecipe,progress,override=override)
        add('FULL_matched_'+which,v['FULL'],mask,cuts['FULL'],qb['Q'])
        for seed in c.SEEDS:
            name='FULL_'+str(seed);add('FULL_matched_'+which+'_'+str(seed),v[name],mask,cuts[name],qb['Q_'+str(seed)])
    c.require(np.array_equal(predictions['FULL_empty_inner'],qb['Q']),'EMPTY_NOT_Q')
    c.require(np.array_equal(predictions['FULL'][~valid],qb['Q'][~valid]),'INNER_FALLBACK')
    for r,i in zip(rows,range(len(rows))):
        if r['device']=='Ring Basestation' or (r['device']=='Netatmo Camera' and r['protocol']==6):
            c.require(not valid[i] and predictions['FULL'][i]==qb['Q'][i],'MANDATORY_Q_FALLBACK')
    c.require(np.array_equal(logits['Q'][~registered.numpy()],b.numpy()[~registered.numpy()]),'OUTER_NOT_R')
    base.unchanged()
    return predictions,bases,valid,dict(logits=logits,scores=scores_out,masks=validity,cuts=cut_out,registered=registered.numpy())

def evaluate(plan,qrecipe,inputs,out,progress,synthetic=False,annotations=None,exclusions=None):
    out=Path(out);out.mkdir(exist_ok=False)
    predictions,bases,valid,details=predict(plan,qrecipe,**inputs,progress=progress)
    rows=inputs['rows']
    if annotations is not None:
        by={a['uid']:a for a in annotations}
        c.require(len(by)==len(annotations) and {r['uid'] for r in rows}<=set(by),'REPORT_ANNOTATIONS')
        # Diagnostic fields join only after predictions; never become model inputs.
        rows=[dict(r,**{k:v for k,v in by[r['uid']].items() if k.startswith('report_')}) for r in rows]
    reports=group_tables(rows,predictions,bases,valid,out/'groups',progress)
    targets=[]
    for label,target in [('normal',.01),('attack',.99)]:
        m=reports['FULL']['overall'][label]
        ok=(m['rate']<=target and m['weighted_rate']<=target) if label=='normal' else (m['rate']>=target and m['weighted_rate']>=target)
        targets.append(dict(group={'scope':'aggregate'},label=label,target=target,meets_descriptive_target=ok))
    for key in ['device','device/activity']:
        for g in reports['FULL']['groups'][key]:
            for label,target in [('normal',.01),('attack',.99)]:
                m=g['metrics'][label]
                if m['rows']:
                    ok=(m['rate']<=target and m['weighted_rate']<=target) if label=='normal' else (m['rate']>=target and m['weighted_rate']>=target)
                    targets.append(dict(group=g['group'],label=label,target=target,meets_descriptive_target=ok))
    result=dict(status='COMPLETE',synthetic_only=synthetic,rows=len(rows),reports=reports,gate=gate(reports,rows,valid),
        original_recipe_sha256=qrecipe.get('recipe_sha256',c.RECIPE_SHA),confirmation_recipe_digest=c.digest(plan),
        independent_ID_test='NOT_RUN',historical_attack_and_OOD='NOT_REOPENED',heldout_opened=not synthetic,
        optimizer_updates=0,new_calibrations=0,reference_counts={d['device']:d['references'] for d in plan['data']['devices']},
        controls=plan['arms']['controls'],absolute_targets=dict(descriptive_only=True,cells=targets),
        data_scope=dict(devices=plan['data']['devices'],sample_unit=plan['data'].get('sample_unit'),
            selection=plan['data'].get('selection'),original_exclusions=exclusions,
            support_boundary=plan['immutable'].get('unsupported'),service_bias=plan.get('leakage',{}).get('service_bias'),
            diagnostic_annotations='Post-prediction direction/port strata; descriptive, not causal attribution'),
        limits=['Clean reference assumed','Shared collection dates/source bias','Only two potentially adaptive devices; Ring fallback'])
    with (out/'decisions.npz').open('xb') as f:np.savez_compressed(f,uid=np.array([r['uid'] for r in rows]),eligible=valid,**predictions)
    with (out/'evidence.npz').open('xb') as f:np.savez_compressed(f,**details['scores'],**{k+'__valid':v for k,v in details['masks'].items()},**details['logits'],registered=details['registered'])
    c.write(out/'operating_rules.json',dict(cuts=details['cuts'],Q_threshold=plan['immutable']['Q_probability_threshold'],no_new_calibration=True))
    c.write(out/'report.json',result);c.seal(out);c.verify(out);return result
