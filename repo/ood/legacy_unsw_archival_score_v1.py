"""Frozen detector application and prospective archival reports; no fitting API."""
import math
from collections import defaultdict
from pathlib import Path
import numpy as np
import torch
import legacy_unsw_archival_common_v1 as c
from legacy_reference_executor_model_v1 import FrozenR, Residual, probability
from legacy_qref_model_v1 import Bank, Metric, Raw, veto, evidence_ensemble


def load_head(path, kind):
    model = Residual('Q') if kind == 'Q' else Metric(27)
    with np.load(path, allow_pickle=False) as f:
        c.require(set(f.files)==set(model.state_dict()),'HEAD_KEYS')
        arrays={k:f[k].copy() for k in f.files}
    c.require(all(v.dtype==np.float32 and np.isfinite(v).all() and
                  v.shape==tuple(model.state_dict()[k].shape) for k,v in arrays.items()),'HEAD_SHAPE_DTYPE')
    model.load_state_dict({k:torch.from_numpy(v) for k,v in arrays.items()},strict=True)
    model.eval(); model.requires_grad_(False)
    return model


def derived(base, features, progress):
    # Same 256-row float32 computation as the frozen Q replay runner.
    z=torch.empty((len(features),768)); h=torch.empty((len(features),128)); b=torch.empty(len(features))
    with torch.inference_mode():
        for start in range(0,len(features),256):
            end=min(start+256,len(features))
            zz,hh,bb=base.inputs(np.array(features[start:end],dtype=np.float32))
            c.require(all(bool(torch.isfinite(v).all()) for v in (zz,hh,bb)),'BASE_NONFINITE')
            z[start:end]=zz; h[start:end]=hh; b[start:end]=bb
            progress.tick(end,len(features))
    return z,h,b


def predict_q(models,z,h,b,registered,progress):
    scores={name:[] for name in models}
    with torch.inference_mode():
        for start in range(0,len(z),256):
            end=min(start+256,len(z)); n=end-start
            for name,model in models.items():
                scores[name].append(model(z[start:end],h[start:end],b[start:end],
                    torch.zeros((n,1,768)),registered[start:end,None]).numpy())
            progress.tick(end,len(z))
    scores={k:np.concatenate(v) for k,v in scores.items()}
    scores['Q']=np.stack([scores['Q_'+str(s)] for s in c.SEEDS]).mean(0,dtype=np.float32)
    scores['Q'][~registered.numpy()]=b.numpy()[~registered.numpy()]
    return scores


def evidences(models,z,rows,bank,progress,override=None):
    # No budgets or new selection. Bank.subset's salt is unused without a budget.
    adapter_recipe={'evaluation':{'control_salt':'UNUSED_NO_SUBSETTING'}}
    values={k:[] for k in models}; masks=[]
    with torch.inference_mode():
        for start in range(0,len(rows),256):
            previous=None
            for name,model in models.items():
                score,mask=bank.own(z[start:start+256],rows[start:start+256],model,adapter_recipe,override=override)
                c.require(previous is None or torch.equal(previous,mask),'REFERENCE_MASK_DRIFT')
                previous=mask; values[name].append(score.numpy())
            masks.append(previous.numpy()); progress.tick(min(start+256,len(rows)),len(rows))
    values={k:np.concatenate(v) for k,v in values.items()}
    for arm in ('FULL','NO_CF'):
        if all(arm+'_'+str(s) in values for s in c.SEEDS):
            values[arm]=evidence_ensemble([values[arm+'_'+str(s)] for s in c.SEEDS])
    return values,np.concatenate(masks)


def measure(rows,pred,q):
    result={}
    for label,name in ((0,'normal'),(1,'attack')):
        ix=[i for i,r in enumerate(rows) if r['label']==label]
        weights=[1/rows[i]['label_metric_weight_denominator'] for i in ix]
        n=len(ix); positive=int(pred[ix].sum())
        result[name]=dict(rows=n,positive=positive,rate=positive/n if n else None,
            weighted_rate=math.fsum(int(pred[i])*w for i,w in zip(ix,weights))/math.fsum(weights) if n else None)
        if label==0:
            expansion=[rows[i]['population_group_count']/rows[i]['selected_group_count'] for i in ix]
            result[name]['population_size_corrected_FPR_estimate']=(
                math.fsum(int(pred[i])*w for i,w in zip(ix,expansion))/math.fsum(expansion) if n else None)
            result[name]['population_estimate_is_not_full_packet_score']=True
    y=np.array([r['label'] for r in rows])
    result['paired']=dict(new_attack_misses=int(((y==1)&q&~pred).sum()),
        recovered_attack=int(((y==1)&~q&pred).sum()),normal_fixed=int(((y==0)&q&~pred).sum()),
        new_normal_alarms=int(((y==0)&~q&pred).sum()))
    return result


def report(rows,pred,q):
    groups={}
    for fields in (('device',),('device','protocol'),('device','reference_available'),
                   ('device','reference_shared_component'),('device','hour_block'),
                   ('device','annotation_id','attack_rate'),('device','component_id')):
        buckets=defaultdict(list)
        for i,r in enumerate(rows): buckets[tuple(str(r[k]) for k in fields)].append(i)
        groups['/'.join(fields)]=[dict(group=dict(zip(fields,key)),
            metrics=measure([rows[i] for i in ix],pred[ix],q[ix])) for key,ix in sorted(buckets.items())]
    return dict(overall=measure(rows,pred,q),groups=groups)


def gates(reports,roster,controls):
    full=reports['FULL']['overall']; q=reports['Q']['overall']; reasons=[]
    preservation={name:reports[name]['overall']['paired']['new_attack_misses']==0
                  for name in ['FULL']+['FULL_'+str(s) for s in c.SEEDS]}
    if not all(preservation.values()): reasons.append('ADDED_ATTACK_MISSES')
    fq=full['normal']['weighted_rate']; qq=q['normal']['weighted_rate']
    reduction=1-fq/qq if qq is not None and qq>0 else None
    def by_device(name):
        return {x['group']['device']:x['metrics'] for x in reports[name]['groups']['device']}
    fd,qd=by_device('FULL'),by_device('Q')
    eligible=[d['device_id'] for d in roster if not d['fallback_protocols']]
    gains=[d for d in eligible if fd[d]['normal']['weighted_rate']<qd[d]['normal']['weighted_rate']]
    if reduction is None or reduction<.30 or len(gains)<2: reasons.append('NORMAL_GAIN_INSUFFICIENT')
    raw=reports['RAW']['overall']; no=reports['NO_CF']['overall']
    learned_raw=(not reasons and fq<raw['normal']['weighted_rate'] and
                 full['attack']['positive']>=raw['attack']['positive'])
    dominates=(fq<=no['normal']['weighted_rate'] and full['attack']['positive']>=no['attack']['positive'] and
               (fq<no['normal']['weighted_rate'] or full['attack']['positive']>no['attack']['positive']))
    personal=[]
    for control in controls:
        if control['status']!='PLANNED_MATCHED':
            personal.append(dict(control=control,status='NOT_ELIGIBLE')); continue
        def direction(suffix):
            a=control['results']['correct'+suffix]; b=control['results']['wrong'+suffix]
            af,bf=a['normal']['weighted_rate'],b['normal']['weighted_rate']
            return af is not None and bf is not None and af<bf and a['paired']['new_attack_misses']<=b['paired']['new_attack_misses']
        supported=direction('') and sum(direction('_'+str(s)) for s in c.SEEDS)>=2
        personal.append(dict(device=control['device_id'],protocol=control['protocol'],supported=supported))
    return dict(archival_milestone_pass=not reasons,reasons=reasons,attack_preservation=preservation,
        normal_relative_reduction=reduction,positive_both_protocol_devices=gains,
        learned_over_RAW=learned_raw,learned_over_NO_CF=not reasons and dominates,
        learned_mechanism_supported=learned_raw and dominates,personalization=personal,
        historical_job174666_FAIL_unchanged=True,paper_or_deployment_certified=False)


def evaluate(root,out,recipe,roster,control_plan,query,refs,features,progress):
    root,out=Path(root),Path(out); out.mkdir(exist_ok=False)
    runtime=c.read(root/'runtime_contract.json'); torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    with np.load(root/runtime['models']['state'],allow_pickle=False) as f:
        c.require(set(f.files)==set(recipe['immutable_e3']['state_array_allowlist']),'STATE_ALLOWLIST')
        state={k:f[k].copy() for k in f.files}
    base=FrozenR(state)
    models={name:load_head(root/path,'Q' if name.startswith('Q_') else 'METRIC')
            for name,path in runtime['models']['heads'].items()}
    allrows=query+refs
    c.require(features.shape==(len(allrows),768) and features.dtype==np.float32,'FEATURE_SHAPE')
    z,h,b=derived(base,features,progress); n=len(query)
    registered=torch.tensor([any(t['device']==r['device'] and t['reference_end']<r['timestamp'] for t in refs) for r in query])
    c.require(bool(registered.all()),'FROZEN_ROSTER_REGISTRATION_DRIFT')
    bank=Bank(refs,z[n:],{c.ROLE})
    qlogits=predict_q({k:v for k,v in models.items() if k.startswith('Q_')},z[:n],h[:n],b[:n],registered,progress)
    theta=recipe['immutable_detector']['Q_probability_threshold']
    q={k:probability(v)>=theta for k,v in qlogits.items()}
    metric={k:v for k,v in models.items() if not k.startswith('Q_')}; metric['RAW']=Raw()
    scores,valid=evidences(metric,z[:n],query,bank,progress)
    c.require(np.array_equal(valid,[r['reference_available'] for r in query]),'MANIFEST_REFERENCE_MASK')
    cuts=recipe['immutable_detector']['cuts']; predictions=dict(q); predictions['R']=probability(b[:n].numpy())>=theta
    bases=dict(q); bases['R']=q['Q']
    for name,score in scores.items():
        suffix=name.rsplit('_',1)[-1]
        qbase=q['Q_'+suffix] if suffix in ('27','127','227') else q['Q']
        predictions[name]=veto(qbase,score,valid,cuts[name]); bases[name]=qbase
    reports={name:report(query,pred,bases[name]) for name,pred in predictions.items()}
    for name in scores:
        p=reports[name]['overall']['paired']
        c.require(p['recovered_attack']==p['new_normal_alarms']==0,'VETO_MONOTONICITY')
    controls=[]; control_arrays={}
    for ordinal,ctrl in enumerate(control_plan['controls']):
        item=dict(ctrl)
        if ctrl['status']=='PLANNED_MATCHED':
            ix=[i for i,r in enumerate(query) if r['device']==ctrl['device_id'] and r['protocol']==ctrl['protocol']]
            rr=[query[i] for i in ix]; item['query_rows']=len(ix); item['results']={}; item['reference_UIDs']={}
            for which,device in (('correct',ctrl['device_id']),('wrong',ctrl['donor_device_id'])):
                uu=sorted(r['uid'] for r in refs if r['device']==device and r['protocol']==ctrl['protocol'])[:ctrl['count_each']]
                c.require(len(uu)==ctrl['count_each']>=2,'MATCHED_REFERENCE_COUNT')
                item['reference_UIDs'][which]=uu
                ev,mask=evidences({k:v for k,v in metric.items() if k.startswith('FULL_')},z[ix],rr,bank,progress,
                    override={(ctrl['device_id'],ctrl['protocol']):uu})
                c.require(mask.all(),'MATCHED_TEMPORAL_GUARD')
                for name,score in ev.items():
                    suffix='' if name=='FULL' else '_'+name.rsplit('_',1)[1]
                    qb=q['Q'+suffix][ix]; pred=veto(qb,score,mask,cuts[name])
                    item['results'][which+suffix]=measure(rr,pred,qb)
                    control_arrays[str(ordinal)+'_'+which+suffix]=pred
                    control_arrays[str(ordinal)+'_'+which+suffix+'_evidence']=score
            control_arrays[str(ordinal)+'_uid']=np.array([r['uid'] for r in rr])
        controls.append(item)
    decision=gates(reports,roster,controls)
    with (out/'decisions.npz').open('xb') as f: np.savez_compressed(f,uid=np.array([r['uid'] for r in query]),**predictions)
    with (out/'evidence.npz').open('xb') as f: np.savez_compressed(f,valid=valid,**scores,**qlogits)
    with (out/'matched_controls.npz').open('xb') as f: np.savez_compressed(f,**control_arrays)
    c.write(out/'controls.json',controls)
    c.write(out/'report.json',dict(status='COMPLETE',recipe_sha256=c.RECIPE_SHA,reports=reports,gate=decision,
        independent_ID='NOT_RUN',scope=recipe['claim'],full_foundation_lineage='UNRESOLVED',
        packet_IID_confidence_intervals=False,real_mixed_stream='NOT_TESTED',optimizer_updates=0,calibration_updates=0))
    lines=['# UNSW external archival evaluation','', 'Scientific milestone: '+str(decision['archival_milestone_pass']),
           '', '| Arm | Normal sample FPR | Normal primary weighted FPR | Attack TPR | Added attack misses vs own Q |',
           '|---|---:|---:|---:|---:|']
    for name in ('Q','RAW','FULL','NO_CF','R'):
        m=reports[name]['overall']
        lines.append('| %s | %.6f | %.6f | %.6f | %d |'%(name,m['normal']['rate'],m['normal']['weighted_rate'],m['attack']['rate'],m['paired']['new_attack_misses']))
    lines+=['','Independent ID NOT_RUN. Passive external archive only; full-foundation independence unresolved.',
            'Normal and attack captures are separate; this is not a live mixed-stream demonstration.',
            'All five devices, all three seeds, all 15 attack intervals and deficient-reference fallback remain in report.json.']
    (out/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    base.unchanged(); c.seal(out); c.verify(out)
    return decision
