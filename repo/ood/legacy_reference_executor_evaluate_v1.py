"""Fixed-threshold reports and the predeclared device/mode DEV gate."""
from __future__ import annotations
from collections import defaultdict
from pathlib import Path
import math,time
import numpy as np
import torch
import legacy_reference_executor_common_v1 as c
from legacy_reference_executor_model_v1 import FrozenR,ReferenceBank,probability
from legacy_reference_executor_train_v1 import load_head
def measure(rows,hard):
    result={}
    for label,name in [(0,'normal'),(1,'attack')]:
        indices=[i for i,r in enumerate(rows) if r['label']==label]
        if not indices:result[name]=dict(rows=0,positive=0,rate=None,weighted_rate=None);continue
        weights=np.array([1/rows[i]['label_metric_weight_denominator'] for i in indices],dtype=np.float64)
        values=np.asarray(hard)[indices]
        positive=int(values.sum())
        result[name]=dict(rows=len(indices),positive=positive,rate=positive/len(indices),
                          weighted_rate=float(np.dot(weights,values)/weights.sum()))
    return result
def grouped(rows,pred,fields):
    groups=defaultdict(list)
    for i,r in enumerate(rows):groups[tuple(str(r.get(k,'NA')) for k in fields)].append(i)
    return [dict(group=dict(zip(fields,key)),metrics=measure([rows[i] for i in ix],pred[ix]))
            for key,ix in sorted(groups.items())]
def report(rows,logits,theta,baseline=None):
    pred=probability(logits)>=theta
    result=dict(overall=measure(rows,pred),devices=grouped(rows,pred,('device',)),
                device_attack_modes=grouped(rows,pred,('device','activity')),
                activity_strata=grouped(rows,pred,('device','normal_activity_stratum')),
                dependency_strata=grouped(rows,pred,('device','reference_dependency_stratum')),
                captures=grouped(rows,pred,('device','capture_id')),
                statistical_scope='Sampled UID denominators; hierarchical weights; descriptive clusters, no packet-binomial CI.')
    control=[i for i,r in enumerate(rows) if r['device']=='Philips Hue Bridge' and r['label']==0
             and r.get('protocol')==6 and r.get('report_direction')=='inbound' and r.get('report_local_port')==80]
    result['philips_local_inbound_tcp80']=measure([rows[i] for i in control],pred[control])
    if baseline is not None:
        original=probability(baseline)>=theta;changes=defaultdict(lambda:[0,0,0])
        for i,r in enumerate(rows):
            if r['label']!=1:continue
            key=(r['device'],r['activity'],r['capture_id']);v=changes[key];v[2]+=1
            v[0]+=int(original[i] and not pred[i]);v[1]+=int(not original[i] and pred[i])
        result['paired_attack_changes']=[dict(device=k[0],mode=k[1],capture=k[2],new_misses=v[0],new_detections=v[1],attack_rows=v[2]) for k,v in sorted(changes.items())]
    return result
def gate_from_reports(reports,expected_devices,recipe_digest,all_sealed):
    reasons={};passed=[]
    def by_device(report):return {x['group']['device']:x['metrics'] for x in report['devices']}
    def modes(report):return {(x['group']['device'],x['group']['activity']):x['metrics']['attack'] for x in report['device_attack_modes'] if x['metrics']['attack']['rows']}
    base=reports['R'];bd=by_device(base);bm=modes(base)
    expected={d['device']:d for d in expected_devices if d['partition']=='DEV'}
    def compare(arm,against='R'):
        target=reports[arm];ref=reports[against];td=by_device(target);rd=by_device(ref);tm=modes(target);rm=modes(ref);why=[]
        if not all_sealed:why.append('NINE_ENDPOINTS_NOT_SEALED')
        if not expected or set(td)!=set(expected) or set(rd)!=set(expected):why.append('DEVICE_CELLS_MISSING')
        for name,device in expected.items():
            if name not in td or name not in rd:continue
            for label in ('normal','attack'):
                a,b=td[name][label],rd[name][label]
                if not a['rows'] or not b['rows'] or a['rows']!=b['rows']:why.append(name+':MISSING_OR_UNMATCHED_'+label);continue
                if label=='normal' and a['weighted_rate']>b['weighted_rate']:why.append(name+':NORMAL_FPR_INCREASE')
                if label=='attack' and a['weighted_rate']<b['weighted_rate']-.01-1e-12:why.append(name+':ATTACK_LOSS_GT_1PP')
            for mode in device['attack_modes']:
                key=(name,mode)
                if key not in tm or key not in rm or tm[key]['rows']!=rm[key]['rows']:why.append(name+':MISSING_MODE:'+mode)
                elif tm[key]['weighted_rate']<rm[key]['weighted_rate']-.01-1e-12:why.append(name+':MODE_LOSS_GT_1PP:'+mode)
        rates=[td[d]['normal']['weighted_rate'] for d in expected if d in td]
        reference=[rd[d]['normal']['weighted_rate'] for d in expected if d in rd]
        if len(rates)!=len(expected) or any(x is None for x in rates+reference) or not math.fsum(rates)<math.fsum(reference):why.append('NO_MACRO_NORMAL_REDUCTION')
        return why
    for arm in ('M','C'):
        reasons[arm]=compare(arm)
        if not reasons[arm]:passed.append(arm)
    cm=compare('C','M')
    return dict(open=bool(passed),passing_arms=passed,reasons=reasons,recipe_digest=recipe_digest,
                all_nine_endpoints_sealed=bool(all_sealed),C_vs_M_joint_comparison_pass=not cm,C_vs_M_reasons=cm,
                scientific_status='DEVELOPMENT_POINT_ESTIMATE_ONLY')
def check_endpoints(chain,recipe):
    receipts={}
    for seed in recipe['optimization']['seeds']:
        baseline=None
        for arm in ('Q','M','C'):
            folder=Path(chain)/('train_'+arm+'_'+str(seed));c.verify_seal(folder);r=c.load(folder/'endpoint.json')
            c.require(r['status']=='COMPLETE' and r['arm']==arm and r['seed']==seed and r['recipe_digest']==c.digest(recipe),'ENDPOINT_IDENTITY')
            c.require(r['updates']==recipe['optimization']['updates_per_model'],'ENDPOINT_UPDATES')
            c.pin(folder/'head.npz',r['head_sha256'])
            signature={k:r[k] for k in ('R_identity','updates','epochs','row_exposures','permutation_sha256','uid_sha256','weight_sha256')}
            if baseline is None:baseline=signature
            c.require(signature==baseline,'UNMATCHED_ARM_EXPOSURE')
            receipts[arm+'_'+str(seed)]=c.sha(folder/'endpoint.json')
    c.require(len(receipts)==9,'NINE_ENDPOINTS_REQUIRED');return receipts
def score(rows,features,base,bank,models,batch=256,uid_override=None,budget=None,progress=None):
    last=time.monotonic()
    values={'R':np.empty(len(rows),dtype=np.float32)}
    values.update({name:np.empty(len(rows),dtype=np.float32) for name in models})
    with torch.inference_mode():
        for start in range(0,len(rows),batch):
            part=rows[start:start+batch];z,h,b=base.inputs(np.array(features[start:start+batch],dtype=np.float32));refs,mask=bank.batch(part,uid_override,budget)
            values['R'][start:start+len(part)]=b.numpy()
            for name,model in models.items():values[name][start:start+len(part)]=model(z,h,b,refs,mask).numpy()
            if progress and time.monotonic()-last>=5:
                progress(start+len(part),len(rows));last=time.monotonic()
    for arm in ('Q','M','C'):
        keys=[name for name in models if name.startswith(arm+'_')]
        c.require(len(keys)==3,'THREE_SEEDS_REQUIRED')
        values[arm]=np.stack([values[k] for k in keys]).mean(0,dtype=np.float32)
        absent=np.array([r['device'] not in bank.by_device for r in rows])
        values[arm][absent]=values['R'][absent]
    return values
def evaluate(recipe,state,features,rows,ref_features,ref_rows,chain,out,role):
    c.require(role in ('LEARN','DEV','DEVICE_HOLDOUT') and all(r['partition']==role for r in rows),'EVALUATION_ROLE')
    endpoints=check_endpoints(chain,recipe);out=Path(out);out.mkdir(exist_ok=False)
    base=FrozenR(state);bank=ReferenceBank(ref_rows,ref_features,base)
    models={arm+'_'+str(seed):load_head(Path(chain)/('train_'+arm+'_'+str(seed))/'head.npz',arm)
            for arm in ('Q','M','C') for seed in recipe['optimization']['seeds']}
    c.emit(out,'SCORE_'+role,0,len(rows),status='RUNNING')
    logits=score(rows,features,base,bank,models,progress=lambda done,total:c.emit(out,'SCORE_'+role,done,total,status='RUNNING'))
    with (out/'logits.npz').open('xb') as f:np.savez(f,uid=np.array([r['uid'] for r in rows],dtype='U64'),**logits)
    theta=recipe['legacy']['threshold_probability']
    reports={name:report(rows,values,theta,logits['R']) for name,values in logits.items()}
    interventions=[];directional=False
    if role!='LEARN':
        small=score(rows,features,base,bank,models,budget=16,progress=lambda done,total:c.emit(out,'BUDGET16_'+role,done,total,status='RUNNING'))
        c.atomic_json(out/'budget16.json',{name:report(rows,small[name],theta,logits['R']) for name in small})
        with (out/'budget16_logits.npz').open('xb') as f:np.savez(f,**small)
        for control in recipe['evaluation']['interventions']:
            if control.get('partition')!=role:
                if control.get('device') in {r['device'] for r in rows} and control['status']!='DEFINED':interventions.append(control)
                continue
            ix=[i for i,r in enumerate(rows) if r['device']==control['device'] and r['timestamp']>control['applicable_after']]
            subset=[rows[i] for i in ix]
            c.require(len(ix)==control['applicable_query_count'] and __import__('legacy_reference_sample_prepare_v1').digest(sorted(r['uid'] for r in subset))==control['applicable_query_uid_hash'],'INTERVENTION_QUERY_IDENTITY')
            own=control['correct_reference_uids'];wrong=control['wrong_reference_uids']
            from collections import Counter
            c.require(len(own)==len(wrong)==control['equal_count'],'INTERVENTION_BUDGET')
            for uid in own:c.require(bank.rows[bank.by_uid[uid]]['device']==control['device'],'CORRECT_OWNER')
            for uid in wrong:c.require(bank.rows[bank.by_uid[uid]]['device']==control['donor'],'WRONG_OWNER')
            c.require(Counter(bank.rows[bank.by_uid[u]]['protocol'] for u in own)==Counter(bank.rows[bank.by_uid[u]]['protocol'] for u in wrong),'INTERVENTION_PROTOCOL')
            c.require(all(bank.rows[bank.by_uid[u]]['timestamp']<control['applicable_after'] for u in own+wrong),'INTERVENTION_CAUSALITY')
            values={}
            for label,refs in [('correct',own),('wrong',wrong)]:
                scores=score(subset,np.array(features[ix],dtype=np.float32),base,bank,models,uid_override=refs,progress=lambda done,total:c.emit(out,'REFERENCE_INTERVENTION_'+label,done,total,status='RUNNING'))
                values[label]={name:report(subset,scores[name],theta,scores['R']) for name in scores}
                with (out/(control['device'].replace(' ','_')+'_'+label+'.npz')).open('xb') as f:np.savez(f,**scores)
            a=values['correct']['C']['overall'];b=values['wrong']['C']['overall']
            supports=(a['normal']['weighted_rate'] is not None and b['normal']['weighted_rate'] is not None
                      and a['normal']['weighted_rate']<b['normal']['weighted_rate']
                      and a['attack']['weighted_rate'] is not None and a['attack']['weighted_rate']>=b['attack']['weighted_rate']-.01-1e-12)
            directional|=supports
            interventions.append(dict(device=control['device'],status='DEFINED',directional_support=supports,comparisons=values,control=control))
    from collections import Counter
    coverage=dict(supported_target_ip_protocols=[6,17],sampled_queries=len(rows),protocol_counts=dict(Counter(r['protocol'] for r in rows)),
                  unsupported_protocols='Excluded before sampling, never credited as learned attack detections.',missing_capability_cells=[])
    for device in recipe['data']['devices']:
        if device['partition']!=role:continue
        subset=[r for r in rows if r['device']==device['device']]
        for label in (0,1):
            if not any(r['label']==label for r in subset):coverage['missing_capability_cells'].append(dict(device=device['device'],label=label))
        for mode in device['attack_modes']:
            if not any(r['label']==1 and r['activity']==mode for r in subset):coverage['missing_capability_cells'].append(dict(device=device['device'],attack_mode=mode))
    if not recipe.get('synthetic_only',False):
        coverage['excluded_capture_modes']=c.load(c.SAMPLE/'finalized/excluded_capture_modes.json')
        receipts=c.load(c.SAMPLE/'capture_receipts.json');reasons=Counter()
        for receipt in receipts:reasons.update(receipt.get('context_reasons',{}))
        coverage['preparation_context_exclusions_287_indexed_captures']=dict(reasons)
        coverage['counts_scope']='Metadata preparation across all indexed captures, not scored full-packet denominators; separately listed excluded HTTP captures were not indexed.'
    result=dict(role=role,coverage=coverage,synthetic_only=recipe.get('synthetic_only',False),recipe_digest=c.digest(recipe),rows=len(rows),reports=reports,
                interventions=interventions,reference_costs=recipe['data']['reference_costs'],ID_anchor=recipe['legacy']['ID_anchor'],
                in_sample=(role=='LEARN'),missing_cells='See explicit zero-row cells, source exclusions and unavailable controls; no silent regrouping.',
                claim_exclusions=recipe['claim_exclusions'])
    if role=='DEV':
        gate=gate_from_reports(reports,recipe['data']['devices'],c.digest(recipe),True)
        gate['endpoint_receipt_pins']=endpoints
        gate['C_mechanism_claim_supported']=bool('C' in gate['passing_arms'] and gate['C_vs_M_joint_comparison_pass'] and directional)
        gate['intervention_direction_rule']='Correct reference lowers normal FPR versus equal-budget wrong reference with at most 1pp overall attack loss on >=1 DEV device; report every mode separately, no significance claim.'
        result['gate']=gate;c.atomic_json(out/'gate.json',gate)
    base.unchanged();c.atomic_json(out/'report.json',result)
    c.emit(out,'EVALUATION_COMPLETE',len(rows),len(rows),status='COMPLETE');c.seal(out)
    return result

