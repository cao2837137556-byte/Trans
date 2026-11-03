"""Once-only CAL protection and complete paired DEV reporting."""
from pathlib import Path
from collections import defaultdict
import math
import numpy as np
import torch
import legacy_qref_common_v1 as c
from legacy_qref_model_v1 import Raw, evidence_ensemble, protected_cut, veto
from legacy_qref_data_v1 import class_weights


def score_models(models,z,rows,bank,recipe,progress,**kwargs):
    result={k:[] for k in models}; masks=[]
    with torch.inference_mode():
        for start in range(0,len(rows),256):
            rr=rows[start:start+256]; zz=z[start:start+256]; prior=None
            for name,model in models.items():
                value,valid=bank.own(zz,rr,model,recipe,**kwargs)
                if prior is not None:
                    c.require(torch.equal(valid,prior),'MODEL_MASK_DIFFERENCE')
                prior=valid; result[name].append(value.numpy())
            masks.append(prior.numpy()); progress.tick()
    result={k:np.concatenate(v) for k,v in result.items()}
    for arm in ('FULL','NO_CF'):
        keys=[arm+'_'+str(s) for s in c.SEEDS]
        if all(k in result for k in keys):
            result[arm]=evidence_ensemble([result[k] for k in keys])
    return result,np.concatenate(masks)


def calibrate(models,z,rows,bank,recipe,out,progress,synthetic=False):
    c.require(all(r['partition']=='LEARN' and r['fit_role']=='CAL' for r in rows),'CAL_ROLE')
    c.require(all(r['partition']=='LEARN' for r in bank.rows),'CAL_DONOR_ROLE')
    ix=[i for i,r in enumerate(rows) if r['label']==1]
    c.require(len(ix)==recipe['data']['CAL']['attack'],'CAL_ATTACK_COUNT')
    attack=[rows[i] for i in ix]; zz=z[ix]
    all_models=dict(models,RAW=Raw()); chunks={k:[] for k in all_models}; chunks.update(FULL=[],NO_CF=[])
    pairs=[]
    with torch.inference_mode():
        for start in range(0,len(attack),256):
            rr=attack[start:start+256]; batch=zz[start:start+256]; matrices={}; common=None
            for name,model in all_models.items():
                matrix,mask=bank.matrix(batch,rr,model,recipe,minimum=2)
                if common is not None:
                    c.require(torch.equal(mask,common),'CAL_MASK_DIFFERENCE')
                common=mask; matrices[name]=matrix.numpy()
            c.require(bool(common.any(1).all()),'CAL_NO_CONTEXT')
            mask=common.numpy()
            for arm in ('FULL','NO_CF'):
                # Average per bank first; -inf denotes the same unavailable bank for every seed.
                matrices[arm]=evidence_ensemble([matrices[arm+'_'+str(s)] for s in c.SEEDS])
            for name,mat in matrices.items():
                chunks[name].append(mat[mask])
            ri,bi=np.nonzero(mask)
            pairs.extend((start+int(i),int(j)) for i,j in zip(ri,bi)); progress.tick()
    c.require(len(pairs)==recipe['data']['CAL']['attack_donor_pairs'],'CAL_CONTEXT_COUNT')
    out=Path(out); out.mkdir(exist_ok=False)
    arrays={k:np.concatenate(v) for k,v in chunks.items()}
    cuts={name:protected_cut(v) for name,v in arrays.items()}
    with (out/'attack_context_scores.npz').open('xb') as f:
        np.savez(f,pairs=np.asarray(pairs,dtype=np.int64),uid=np.array([r['uid'] for r in attack]),**arrays)
    tails={}
    for name,v in arrays.items():
        indices=np.argsort(-v,kind='stable')[:20]
        tails[name]=[dict(uid=attack[pairs[i][0]]['uid'],bank=list(bank.keys[pairs[i][1]]),score=float(v[i])) for i in indices]
    c.write(out/'cuts.json',dict(cuts=cuts,attack_rows=len(attack),contexts=len(pairs),tails=tails,
        recipe_digest=c.digest(recipe),synthetic_only=synthetic,no_useful_correction=[k for k,v in cuts.items() if v>=1]))
    c.seal(out); c.verify(out)
    # Reapply cuts after their seal to saved scores, not merely to training maxima.
    saved_cuts=c.read(out/'cuts.json')['cuts']
    with np.load(out/'attack_context_scores.npz',allow_pickle=False) as saved:
        for k,cut in saved_cuts.items():
            c.require(np.isfinite(saved[k]).all() and not (saved[k]>cut).any(),'CAL_REAPPLY_FAILURE')
    return cuts


def measure(rows,pred):
    result={}
    for y,key in ((0,'normal'),(1,'attack')):
        ix=[i for i,r in enumerate(rows) if r['label']==y]
        if not ix:
            result[key]=dict(rows=0,positive=0,rate=None,weighted_rate=None)
            continue
        den=[rows[i]['label_metric_weight_denominator'] for i in ix]
        c.require(all(isinstance(d,int) and d>0 for d in den),'METRIC_WEIGHTS')
        w=[1/d for d in den]; positives=int(np.asarray(pred)[ix].sum())
        result[key]=dict(rows=len(ix),positive=positives,rate=positives/len(ix),
            weighted_rate=math.fsum(v*int(pred[i]) for i,v in zip(ix,w))/math.fsum(w))
    return result


def paired(rows,pred,q):
    y=np.array([r['label'] for r in rows])
    new=(y==1)&q&~pred
    sessions=defaultdict(list)
    for i,r in enumerate(rows):
        if r['label']==1:
            sessions[r['device'],r['session_id']].append(i)
    return dict(new_attack_misses=int(new.sum()),recovered_attack=int(((y==1)&~q&pred).sum()),
        normal_fixed=int(((y==0)&q&~pred).sum()),normal_new_FP=int(((y==0)&~q&pred).sum()),
        affected_attack_sessions=sum(bool(new[ix].any()) for ix in sessions.values()),
        newly_wholly_missed_sessions=sum(bool(q[ix].any()) and not bool(pred[ix].any()) for ix in sessions.values()))


def report(rows,pred,q,valid):
    groups={}
    for fields in [('device',),('device','activity'),('device','protocol'),('device','capture_id'),
                   ('device','session_id'),('device','component_id'),('device','normal_activity_stratum'),
                   ('device','reference_dependency_stratum')]:
        ix_by=defaultdict(list)
        for i,r in enumerate(rows):
            ix_by[tuple(str(r.get(k,'NA')) for k in fields)].append(i)
        groups['/'.join(fields)]=[dict(group=dict(zip(fields,key)),metrics=measure([rows[i] for i in ix],pred[ix]),
            paired=paired([rows[i] for i in ix],pred[ix],q[ix])) for key,ix in sorted(ix_by.items())]
    return dict(overall=measure(rows,pred),paired=paired(rows,pred,q),groups=groups,
        reference_eligibility=[dict(valid=flag,metrics=measure([r for r,v in zip(rows,valid) if bool(v)==flag],pred[valid==flag])) for flag in (False,True)])


def gates(reports,recipe):
    full=reports['FULL']; q=reports['Q']; s=recipe['evaluation']['system_gate']
    why=[]
    if full['paired']['new_attack_misses']!=0: why.append('NEW_ATTACK_MISSES')
    fq=full['overall']['normal']['weighted_rate']; qq=q['overall']['normal']['weighted_rate']
    if qq is None or qq<=0 or fq>qq*(1-s['weighted_normal_FPR_relative_reduction_min']): why.append('NORMAL_GAIN_INSUFFICIENT')
    focal=[g for g in full['groups']['device/activity'] if g['group']=={'device':'Eufy Home Base','activity':'WAN_WATCH'}]
    if len(focal)!=1 or focal[0]['metrics']['normal']['rows']!=s['focal_normal_denominator']:
        why.append('FOCAL_DENOMINATOR')
    elif focal[0]['metrics']['normal']['positive']>s['focal_Eufy_WAN_WATCH_FP_max']:
        why.append('FOCAL_FP_NOT_HALVED')
    seed_ok=sum(reports['FULL_'+str(seed)]['paired']['new_attack_misses']==0 and
        reports['FULL_'+str(seed)]['paired']['normal_fixed']>0 for seed in c.SEEDS)
    if seed_ok<s['min_individual_FULL_seeds_with_zero_new_attack_misses_and_positive_weighted_normal_gain']:
        why.append('SEED_SUPPORT_INSUFFICIENT')
    c.require(all(v['paired']['normal_new_FP']==0 and v['paired']['recovered_attack']==0 for v in reports.values()),'VETO_MONOTONICITY')
    raw=reports['RAW']; no=reports['NO_CF']
    learned=not why and fq<raw['overall']['normal']['weighted_rate'] and raw['paired']['new_attack_misses']==0
    no_fpr=no['overall']['normal']['weighted_rate']; no_miss=no['paired']['new_attack_misses']
    cf_supported=not why and fq<=no_fpr and full['paired']['new_attack_misses']<=no_miss and (fq<no_fpr or full['paired']['new_attack_misses']<no_miss)
    personalization=[]
    for entry in reports['FULL_matched_correct']['groups']['device']:
        device=entry['group']['device']
        def direction(suffix):
            a=next(x for x in reports['FULL_matched_correct'+suffix]['groups']['device'] if x['group']['device']==device)
            b=next(x for x in reports['FULL_matched_wrong'+suffix]['groups']['device'] if x['group']['device']==device)
            return a['metrics']['normal']['weighted_rate']<b['metrics']['normal']['weighted_rate'] and a['paired']['new_attack_misses']<=b['paired']['new_attack_misses']
        personalization.append(dict(device=device,support=direction('') and sum(direction('_'+str(seed)) for seed in c.SEEDS)>=2))
    return dict(system_pass=not why,reasons=why,individual_seeds_passing=seed_ok,
        learned_over_raw=learned,worst_reference_constraint_supported=cf_supported,
        personalized_reference_supported=any(x['support'] for x in personalization),personalization=personalization,
        learned_mechanism_supported=learned and cf_supported,holdout_open=False,
        evidence='INSPECTED_DEV_ONLY_NOT_INDEPENDENT_OR_DEPLOYMENT_CERTIFICATION')


def evaluate(models,z,rows,bank,recipe,q_logits,cuts,out,progress,synthetic=False,coverage=None):
    c.require(all(r['partition']=='DEV' for r in rows) and len(rows)==recipe['data']['DEV']['rows'],'DEV_SCOPE')
    c.require(synthetic or coverage is not None,'REPORT_DEPENDENCIES_REQUIRED')
    # Original metric weights must match hierarchy, not an arbitrary supplied denominator.
    for label in (0,1):
        rr=[r for r in rows if r['label']==label]
        w=class_weights(rr)
        c.require(np.allclose(w,[1/r['label_metric_weight_denominator'] for r in rr],rtol=0,atol=1e-15),'DEV_WEIGHT_DRIFT')
    from legacy_reference_executor_model_v1 import probability
    theta=recipe['immutable']['legacy']['threshold_probability']
    q={k:probability(v)>=theta for k,v in q_logits.items()}
    main=q['Q']; allmodels=dict(models,RAW=Raw())
    scores,valid=score_models(allmodels,z,rows,bank,recipe,progress)
    predictions={'Q':main}; validity={'Q':np.ones(len(rows),dtype=bool)}; score_outputs={}; thresholds={}; bases={'Q':main}
    def add(name,score,mask,cut,qbase):
        predictions[name]=veto(qbase,score,mask,cut); validity[name]=mask
        score_outputs[name]=score; thresholds[name]=cut; bases[name]=qbase
    for name,score in scores.items():
        base=q['Q_'+name.rsplit('_',1)[1]] if name.rsplit('_',1)[-1] in {'27','127','227'} else main
        add(name,score,valid,cuts[name],base)
    add('FULL_cut_zero_diagnostic_only',scores['FULL'],valid,0.,main)
    add('FULL_empty_inner',scores['FULL'],np.zeros(len(rows),dtype=bool),cuts['FULL'],main)
    c.require(np.array_equal(predictions['FULL_empty_inner'],main),'EMPTY_INNER_NOT_Q')
    fullmodels={k:v for k,v in models.items() if k.startswith('FULL_')}
    budget,mask=score_models(fullmodels,z,rows,bank,recipe,progress,budget=16)
    add('FULL_budget16',budget['FULL'],mask,cuts['FULL'],main)
    for which in ('correct','wrong'):
        override={(x['device'],x['protocol']):x[which+'_reference_uids'] for x in recipe['evaluation']['controls'] if x['status']=='MATCHED'}
        values,mask=score_models(fullmodels,z,rows,bank,recipe,progress,override=override)
        add('FULL_matched_'+which,values['FULL'],mask,cuts['FULL'],main)
        for seed in c.SEEDS:
            name='FULL_'+str(seed)
            add('FULL_matched_'+which+'_'+str(seed),values[name],mask,cuts[name],q['Q_'+str(seed)])
    reports={}
    for name,pred in predictions.items():
        reports[name]=report(rows,pred,bases[name],validity[name]); progress.tick(report_arm=name)
    out=Path(out); out.mkdir(exist_ok=False)
    with (out/'decisions.npz').open('xb') as f:
        np.savez(f,uid=np.array([r['uid'] for r in rows]),**predictions)
    with (out/'normal_evidence.npz').open('xb') as f:
        np.savez(f,**score_outputs,**{k+'__valid':v for k,v in validity.items()},**q_logits,
            **{k+'__probability':probability(v) for k,v in q_logits.items()})
    c.write(out/'operating_rules.json',dict(cuts=thresholds,Q_threshold=theta,
        reason='Q-negative => kept_normal; Q-positive invalid reference => kept_Q; Q-positive score>cut => cancelled_by_normal_evidence; otherwise kept_Q',
        reference_UIDs=[r['uid'] for r in bank.rows],controls=recipe['evaluation']['controls'],
        route='All original DEV rows registered; unregistered outer route remains R; empty-inner is Q.',
        no_composite_probability=True))
    result=dict(status='COMPLETE',synthetic_only=synthetic,recipe_digest=c.digest(recipe),rows=len(rows),
        reports=reports,gate=gates(reports,recipe),coverage=coverage,ID=recipe['immutable']['legacy']['ID_anchor'],
        independent_ID_test='NOT_RUN',historical_attack_and_OOD='NOT_REOPENED',heldout_open=False,
        service_source_bias='Unresolved: all DEV attacks involve endpoint80; no DEV normal does; ports not direct neural input.')
    c.write(out/'report.json',result); c.seal(out); c.verify(out)
    return result
