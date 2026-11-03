"""Role-isolated P preparation, matched T heads and one complete E endpoint."""
import csv
import gzip
import hashlib
import json
import math
import zipfile
from pathlib import Path
import numpy as np
import torch
import issue27dualview_support_v1 as s
import issue27dualview_model_v1 as m
import issue27dualview_metrics_v1 as metrics

CONTRACT='ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9'
PLANS={'fit_select':'eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac',
       'expanded':'3b97498c505cea5c646e91ecf247972926eb8c8fe4a6c51ef61a17e940a93c70'}
EXPANDED_TARGETS={'path':'runs/frontend_expanded_eval_implementation_v1_20260910/targets.csv.gz',
                  'sha256':'6e22b8ee1e45de960f45ba85f44529b978b0198c381d04937e72a37d65112915'}


def metadata(r,budget):
    plan=s.read_json(s.pin(r['inputs']['plan'],budget.check));s.train_metadata(plan,r)
    s.pin(r['inputs']['membership'],budget.check)
    components=s.read_json(s.pin(r['inputs']['dependencies']['components'],budget.check))
    edges=s.read_json(s.pin(r['inputs']['dependencies']['edges'],budget.check))
    assignments={k:(c['component_id'],c['role']) for c in components for k in c['context_keys']}
    s.require(len(assignments)==sum(len(c['context_keys']) for c in components),'COMPONENT_DUPLICATES')
    s.require(all(assignments.get(c['key'])==(c['component'],c['role']) for c in plan['contexts']),'COMPONENT_ASSIGNMENTS')
    s.require(all(assignments[e['left']][1]==assignments[e['right']][1] for e in edges),'CROSS_ROLE_EDGE')
    with s.pin(r['inputs']['membership'],budget.check).open(encoding='utf-8',newline='') as f:
        members=list(csv.DictReader(f))
    lookup={t['uid']:t for t in members};ts=s.targets(plan['contexts'])
    s.require(len(lookup)==len(members)==len(ts) and set(lookup)=={t['uid'] for t in ts},'MEMBERSHIP_UIDS')
    for t in ts:
        old=lookup[t['uid']]
        s.require(all(str(t[k])==old[k] for k in ('context_key','component_id','new_role','owner','label','position')),'MEMBERSHIP_JOIN')
    return plan


def native_AB_receipt(r,budget):
    spec=r['inputs'];p=s.pin(spec['historical_train_manifest'],budget.check)
    entries={line.split('  ',1)[1]:line.split('  ',1)[0] for line in p.read_text(encoding='utf-8').splitlines()}
    for name in ('initial_AB','initial_AB_receipt','initial_AB_terminal'):
        path=s.pin(spec[name],budget.check)
        s.require(path.parent==p.parent and entries[path.name]==spec[name]['sha256'],'AB_NATIVE_MANIFEST')
    receipt=s.read_json(s.ROOT/spec['initial_AB_receipt']['path']);terminal=s.read_json(s.ROOT/spec['initial_AB_terminal']['path'])
    s.require(terminal['verdict']['status']=='PAIRED_COMPARISON_COMPLETE','AB_TERMINAL')
    s.require(receipt['state_sha256']==spec['initial_AB']['state_sha256'] and receipt['file_sha256']==spec['initial_AB']['sha256'],'AB_RECEIPT')
    s.require(all(receipt[k]==spec['initial_AB_receipt'][k] for k in ('epoch','updates','initial_state_sha256')),'AB_HISTORY')


def extract(model,contexts,path,budget,expanded=False):
    targets=sorted(s.targets(contexts),key=lambda t:t['uid']);positions={t['uid']:i for i,t in enumerate(targets)}
    s.require(len(positions)==len(targets),'EXTRACT_DUPLICATE_UID')
    values=np.empty((len(targets),128),dtype='<f4');seen=set();handles={}
    try:
        with torch.inference_mode():
            for start in range(0,len(contexts),32):
                batch=contexts[start:start+32];xs=[]
                for c in batch:
                    source=path/'members'/c['member_id']/'features.f32le' if expanded else path
                    if source not in handles:handles[source]=source.open('rb')
                    f=handles[source];f.seek(c['offset']);raw=f.read(c['length']*524)
                    s.require(len(raw)==c['length']*524 and 1<=c['length']<=256,'PREFIX_BYTES')
                    for t in c['targets']:
                        s.require(0<=t['event']<c['length'] and s.prefix(raw,t['event'])==t['feature_prefix_sha256'],'PREFIX_IDENTITY')
                    xs.append(torch.from_numpy(np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)))
                    budget.access['feature_bytes_decoded']+=len(raw)
                hidden=model(xs,[c['key'] for c in batch]);budget.access['encoder_forwards']+=1
                for c,h in zip(batch,hidden):
                    for t in c['targets']:
                        uid=t['uid'];s.require(uid not in seen,'DUPLICATE_HIDDEN');seen.add(uid)
                        values[positions[uid]]=h[t['event']].numpy();budget.access['AB_target_states']+=1
                budget.check(phase='ENCODER_EXTRACTION',targets_complete=budget.access['AB_target_states'])
    finally:
        for f in handles.values():f.close()
    s.require(len(seen)==len(targets) and np.isfinite(values).all(),'HIDDEN_COVERAGE')
    return targets,values


def selective_rows(path,indices,shape,budget):
    s.require(indices==sorted(set(indices)) and all(0<=i<shape[0] for i in indices),'ROW_INDICES')
    values=np.empty((len(indices),shape[1]),dtype='<f4');wanted={j:i for i,j in enumerate(indices)}
    with zipfile.ZipFile(path) as z:
        s.require(z.namelist().count('representation.npy')==1,'REPRESENTATION_MEMBER')
        with z.open('representation.npy') as f:
            version=np.lib.format.read_magic(f)
            s.require(version in ((1,0),(2,0)),'NPY_VERSION')
            header=np.lib.format.read_array_header_1_0 if version==(1,0) else np.lib.format.read_array_header_2_0
            dims,fortran,dtype=header(f)
            s.require(tuple(dims)==tuple(shape) and not fortran and dtype==np.dtype('<f4'),'REPRESENTATION_HEADER')
            for i in range(shape[0]):
                raw=f.read(shape[1]*4);s.require(len(raw)==shape[1]*4,'SHORT_REPRESENTATION')
                budget.access['opaque_E3_bytes_streamed']+=len(raw)
                if i in wanted:
                    row=np.frombuffer(raw,dtype='<f4');s.require(np.isfinite(row).all(),'SELECTED_NONFINITE')
                    values[wanted[i]]=row;budget.access['E3_numeric_rows']+=1
                if i%256==0:budget.check(phase='SELECTING_E3_ROWS',E3_rows_complete=budget.access['E3_numeric_rows'])
            s.require(f.read(1)==b'','REPRESENTATION_TRAILING_BYTES')
    return values


def e3_rows(r,kind,targets,budget):
    s.require((budget.stage=='P' and kind=='fit_select' and all(t['new_role']=='train' for t in targets)) or
              (budget.stage=='E' and (kind=='expanded' or all(t['new_role']=='check' for t in targets))),'E3_ROLE_BOUNDARY')
    spec=r['inputs']['e3_caches'][kind];path=s.pin(spec,budget.check)
    s.require(path.stat().st_size==spec['bytes'],'E3_FILE_BYTES')
    names=('uid','missing','candidate_id','plan_sha256','contract_sha256')
    with zipfile.ZipFile(path) as z:
        s.require(all(z.namelist().count(k+'.npy')==1 for k in names),'E3_METADATA_MEMBERS')
    with np.load(path,allow_pickle=False) as z: meta={k:z[k] for k in names}
    n=spec['shape'][0];uids=meta['uid'];missing=meta['missing']
    s.require(uids.shape==missing.shape==(n,) and uids.dtype.kind=='U' and missing.dtype==np.bool_,'E3_METADATA_SCHEMA')
    s.require(meta['candidate_id'].tolist()==['E3'] and meta['plan_sha256'].tolist()==[PLANS[kind]] and meta['contract_sha256'].tolist()==[CONTRACT],'E3_PROVENANCE')
    mapping={str(u):i for i,u in enumerate(uids)}
    s.require(len(mapping)==n and int(missing.sum())==spec['missing'],'E3_UID_MISSING_COUNTS')
    wanted={t['uid']:t for t in targets};s.require(len(wanted)==len(targets) and set(wanted)<=set(mapping),'E3_UID_JOIN')
    mask=np.array([not missing[mapping[t['uid']]] for t in targets],dtype=np.bool_)
    for t,valid in zip(targets,mask):
        expected=(t['owner']=='A') if kind=='fit_select' else (not t['old_missing'])
        s.require(bool(valid)==expected,'E3_AVAILABILITY_MISMATCH')
    side=s.pin(spec['metadata_sidecar'],budget.check);seen=set();sessions={}
    with gzip.open(side,'rt',encoding='utf-8',newline='') as f:
        for row in csv.DictReader(f):
            uid=row['uid']
            if uid not in wanted:continue
            s.require(uid not in seen,'PREFIX_DUPLICATE_UID');seen.add(uid);t=wanted[uid]
            s.require(int(row['event_position'])==int(t['position']) and math.isfinite(float(row['timestamp_epoch'])) and len(row['session_id'])==64,'OLD_PREFIX_JOIN')
            if 'timestamp_epoch' in t:s.require(float(row['timestamp_epoch'])==float(t['timestamp_epoch']),'OLD_TIMESTAMP_JOIN')
            if not missing[mapping[uid]]:sessions[uid]=row['session_id']
    s.require(seen==set(wanted),'OLD_PREFIX_COVERAGE')
    indices=sorted(mapping[t['uid']] for t,valid in zip(targets,mask) if valid)
    selected=selective_rows(path,indices,spec['shape'],budget);inverse={j:i for i,j in enumerate(indices)}
    result=np.zeros((len(targets),768),dtype='<f4')
    for i,(t,valid) in enumerate(zip(targets,mask)):
        if valid:result[i]=selected[inverse[mapping[t['uid']]]]
    return result,mask,sessions


def save_matrix(out,name,x,targets,budget):
    path=out/(name+'.f32le')
    with path.open('xb') as f:
        for i in range(0,len(x),1024):f.write(x[i:i+1024].tobytes());budget.check()
    s.atomic_json(out/(name+'_index.json'),targets)
    return dict(path=path.name,sha256=s.sha(path,budget.check),shape=list(x.shape),index=name+'_index.json',index_sha256=s.sha(out/(name+'_index.json'),budget.check))


def load_matrix(folder,rec,budget):
    path=folder/rec['path'];s.require(path.parent==folder and s.sha(path,budget.check)==rec['sha256'],'PREPARED_MATRIX_HASH')
    idx=folder/rec['index'];s.require(idx.parent==folder and s.sha(idx,budget.check)==rec['index_sha256'],'PREPARED_INDEX_HASH')
    ts=s.read_json(idx);raw=path.read_bytes()
    s.require(rec['shape']==[len(ts),897] and len(raw)==len(ts)*897*4 and [t['uid'] for t in ts]==sorted({t['uid'] for t in ts}),'PREPARED_SHAPE_UIDS')
    x=np.frombuffer(raw,dtype='<f4').copy().reshape(rec['shape'])
    s.require(np.isfinite(x).all() and np.isin(x[:,896],[0,1]).all() and (x[x[:,896]==0,128:896]==0).all(),'PREPARED_CONTENT_SCHEMA')
    return ts,x


def barrier(stage,budget):
    folder=s.OUTPUTS[stage];s.manifest(folder,check=budget.check)
    terminal=s.read_json(folder/'supervisor_terminal.json')
    s.require(terminal['status']=='COMPLETE' and terminal.get('verified') and terminal.get('recipe_sha256')==s.RECIPE_SHA,'PRIOR_STAGE_INCOMPLETE')
    return folder


def prepare(r,out,budget):
    plan=metadata(r,budget);native_AB_receipt(r,budget)
    contexts=sorted([c for c in plan['contexts'] if c['role']=='train'],key=lambda c:c['key'])
    model,identity=m.load_encoder(r,budget)
    targets,ab=extract(model,contexts,s.pin(r['inputs']['train_check_features'],budget.check),budget)
    m.verify_encoder(model,identity);del model
    e3,mask,sessions=e3_rows(r,'fit_select',targets,budget)
    s.require(int(mask.sum())==r['stages']['P']['E3_numeric_rows'],'P_E3_DENOMINATOR')
    mean,scale=m.normalizers(ab,e3,mask);x=m.normalize(ab,e3,mask,mean,scale)
    norm=out/'normalizers.npz';np.savez(norm,mean=mean,scale=scale)
    rec=dict(status='TRAIN_REPRESENTATIONS_PREPARED',recipe_sha256=s.RECIPE_SHA,
             encoder_sha256=identity,AB_file_sha256=r['inputs']['initial_AB']['sha256'],
             encoder_unchanged=True,normalizer_sha256=s.sha(norm),normalizer_rows={'AB':len(targets),'E3':int(mask.sum())},
             train=save_matrix(out,'train',x,targets,budget),sessions=sessions)
    s.atomic_json(out/'preparation_receipt.json',rec)
    return rec


def prepared(r,budget):
    folder=barrier('P',budget);rec=s.read_json(folder/'preparation_receipt.json')
    s.require(rec['recipe_sha256']==s.RECIPE_SHA and rec['encoder_unchanged'] and rec['AB_file_sha256']==r['inputs']['initial_AB']['sha256'],'P_ENCODER_RECEIPT')
    s.require(rec['normalizer_rows']=={'AB':r['data']['train_targets'],'E3':r['stages']['P']['E3_numeric_rows']},'P_NORMALIZER_COUNTS')
    targets,x=load_matrix(folder,rec['train'],budget)
    s.require(all(t['new_role']=='train' for t in targets) and len(targets)==r['data']['train_targets'],'PREPARED_TRAIN_SCOPE')
    return folder,rec,targets,x


def fit(r,out,budget):
    folder,prec,targets,x=prepared(r,budget);initials={};orders={};candidates={}
    y=np.array([t['label'] for t in targets],dtype=np.int64);counts=np.bincount(y,minlength=2)
    expected=np.array([r['data']['A']['benign']+r['data']['B']['benign'],r['data']['A']['attack']+r['data']['B']['attack']])
    s.require(np.array_equal(counts,expected) and (counts>0).all(),'TRAIN_CLASS_COUNTS')
    weights=torch.from_numpy((len(y)/(2.*counts[y])).astype(np.float32));yt=torch.from_numpy(y.astype(np.float32));xt=torch.from_numpy(x)
    epochs=r['training']['epochs'];bs=r['training']['batch_size']
    for arm in ('U0','U1'):
        model=m.head();initials[arm]=m.state_hash(model);opt=m.optimizer(model,r)
        s.require(not opt.state,'OPTIMIZER_NOT_EMPTY');generator=torch.Generator().manual_seed(2705)
        orders[arm]=[];updates=presentations=0
        for epoch in range(1,epochs+1):
            order=torch.randperm(len(y),generator=generator);orders[arm].append(hashlib.sha256(order.numpy().tobytes()).hexdigest())
            model.train();loss_sum=0.
            for start in range(0,len(y),bs):
                take=order[start:start+bs]
                loss,norm=m.update(model,opt,m.arm_input(xt[take],arm),yt[take],weights[take])
                loss_sum+=loss*len(take);updates+=1;presentations+=len(take)
                budget.access['optimizer_steps']+=1;budget.access['head_training_forwards']+=1
                budget.check(phase='TRAINING',arm=arm,epoch=epoch,epochs=epochs,updates=budget.access['optimizer_steps'],updates_total=r['training']['updates_total'])
            with (out/'epoch_log.jsonl').open('ab') as f:
                f.write(s.canonical(dict(arm=arm,epoch=epoch,label_loss=loss_sum/len(y),last_gradient_L2=norm,order_sha256=orders[arm][-1],updates=updates))+b'\n')
        s.require(updates==r['training']['updates_per_arm'] and presentations==r['training']['label_presentations_per_arm'],'TRAIN_BUDGET')
        path=out/(arm+'.pt')
        with path.open('xb') as f:torch.save(model.state_dict(),f)
        candidates[arm]=dict(file_sha256=s.sha(path,budget.check),state_sha256=m.state_hash(model),initial_state_sha256=initials[arm],updates=updates,label_presentations=presentations,epoch=epochs)
        s.atomic_json(out/(arm+'.receipt.json'),candidates[arm]);del model,opt
    s.require(initials['U0']==initials['U1'] and orders['U0']==orders['U1'],'MATCHED_ARMS')
    s.manifest(folder,check=budget.check)
    rec=dict(status='BOTH_FINAL_HEADS_SEALED',recipe_sha256=s.RECIPE_SHA,candidates=candidates,order_hashes=orders,P_receipt_sha256=s.sha(folder/'preparation_receipt.json'),encoder_sha256=prec['encoder_sha256'])
    s.atomic_json(out/'candidates_sealed.json',rec)
    return rec


def score(model,x,targets,arm,budget):
    result={};model.eval();before=m.state_hash(model)
    with torch.inference_mode():
        for start in range(0,len(x),256):
            batch=torch.from_numpy(x[start:start+256]);q=model(m.arm_input(batch,arm)).reshape(-1).numpy()
            s.require(np.isfinite(q).all(),'NONFINITE_LOGITS')
            for t,v in zip(targets[start:start+256],q):result[t['uid']]=float(v)
            budget.access['head_evaluation_forwards']+=1;budget.access['evaluated_targets']+=len(q)
            budget.check(phase='EVALUATION',arm=arm,targets_complete=budget.access['evaluated_targets'],targets_total=budget.targets_total)
    s.require(m.state_hash(model)==before,'HEAD_INFERENCE_MUTATED')
    return result


def evaluate(r,out,budget):
    train_dir=barrier('T',budget);final=s.read_json(train_dir/'candidates_sealed.json')
    s.require(final['status']=='BOTH_FINAL_HEADS_SEALED' and final['recipe_sha256']==s.RECIPE_SHA and set(final['candidates'])=={'U0','U1'},'T_BARRIER')
    pdir,prec,train_targets,train_x=prepared(r,budget)
    s.require(final['P_receipt_sha256']==s.sha(pdir/'preparation_receipt.json') and final['encoder_sha256']==prec['encoder_sha256'],'T_P_LINEAGE')
    norm=pdir/'normalizers.npz';s.require(s.sha(norm)==prec['normalizer_sha256'],'NORMALIZER_IDENTITY')
    with np.load(norm,allow_pickle=False) as z:mean,scale=z['mean'],z['scale']
    plan=metadata(r,budget);checks=sorted([c for c in plan['contexts'] if c['role']=='check'],key=lambda c:c['key'])
    baseline,expanded,source=metrics.expanded_inputs(r,budget)
    expanded_spec=r.get('implementation_metadata',{}).get('expanded_targets',EXPANDED_TARGETS)
    with gzip.open(s.pin(expanded_spec,budget.check),'rt',encoding='utf-8',newline='') as f:rows=list(csv.DictReader(f))
    original={t['uid']:t for t in rows};s.require(len(original)==len(rows)==len(baseline) and set(original)=={t['uid'] for t in baseline},'EXPANDED_POSITION_UIDS')
    for t in baseline:
        a=original[t['uid']]
        s.require(all(str(t[k])==str(a[k]) for k in ('label','source_group','attack_family','device_family')),'EXPANDED_POSITION_JOIN')
        t['position']=int(a['position'])
    model,identity=m.load_encoder(r,budget);s.require(identity==prec['encoder_sha256'],'E_ENCODER_IDENTITY')
    check_targets,ab=extract(model,checks,s.pin(r['inputs']['train_check_features'],budget.check),budget)
    e3,mask,sessions=e3_rows(r,'fit_select',check_targets,budget)
    s.require(not(set(sessions.values()) & set(prec['sessions'].values())),'OLD_SESSION_CROSS_ROLE')
    check_x=m.normalize(ab,e3,mask,mean,scale);check_rec=save_matrix(out,'check',check_x,check_targets,budget)
    extracted,ab=extract(model,expanded,source,budget,expanded=True)
    lookup={t['uid']:t for t in baseline};expanded_targets=[lookup[t['uid']] for t in extracted]
    e3,mask,_=e3_rows(r,'expanded',expanded_targets,budget);expanded_x=m.normalize(ab,e3,mask,mean,scale)
    expanded_rec=save_matrix(out,'expanded',expanded_x,expanded_targets,budget)
    m.verify_encoder(model,identity);del model,ab,e3,mask
    datasets={'train':(train_targets,train_x),'check':(check_targets,check_x),'expanded':(expanded_targets,expanded_x)}
    all_q={};details={}
    check_ref=s.read_json(s.pin(r['inputs']['historical_check_scores'],budget.check))['A']
    check_A={t['uid']:t['hard'] for t in check_ref if t['owner']=='A'}
    for arm in ('U0','U1'):
        path=train_dir/(arm+'.pt');rec=final['candidates'][arm]
        s.require(s.sha(path)==rec['file_sha256'],'HEAD_FILE_SHA')
        model=m.head();model.load_state_dict(torch.load(path,map_location='cpu',weights_only=True),strict=True);budget.access['new_candidate_loads']+=1
        s.require(m.state_hash(model)==rec['state_sha256'],'HEAD_STATE_SHA');preds={}
        for role,(targets,x) in datasets.items():
            preds[role]=score(model,x,targets,arm,budget);dest=out/(arm+'_'+role+'.csv.gz')
            metrics.save_predictions(dest,preds[role]);s.require(metrics.read_predictions(dest,preds[role])==preds[role],'PREDICTION_ROUNDTRIP')
        details[arm]=metrics.check_details(r,plan['contexts'],preds,check_A);all_q[arm]=preds['expanded'];del model
    all_q['AB']={t['uid']:t['ab_logit'] for t in baseline}
    for name,ref in r['historical_score_references'].items():
        s.pin(ref['manifest'],budget.check)
        all_q[name]=metrics.read_predictions(s.pin(ref['files']['expanded'],budget.check),all_q['AB'])
    models=metrics.model_metrics(baseline,all_q,budget)
    for key,scope in [('old_attack_reference_exact','overall'),('old_future_reference_exact','future')]:
        ref=r['evaluation'][key];v=models['old_P2']['fixed'][scope]
        s.require(v['detected']==ref['detected'] and v['attacks']==ref['targets'],'OLD_REFERENCE_DENOMINATOR')
    contrasts={name:metrics.contrast(models[name.split('-')[1]],models[name.split('-')[0]]) for name in r['evaluation']['contrasts']}
    for arm in ('U0','U1'):
        for ref in (['AB','old_P2'] if arm=='U0' else ['U0','AB','old_P2']):
            old={t['uid']:t['old_hard'] for t in baseline} if ref=='old_P2' else {u:int(q>=0) for u,q in all_q[ref].items()}
            value=metrics.flips(baseline,old,{u:int(q>=0) for u,q in all_q[arm].items()})
            with gzip.open(out/(arm+'_vs_'+ref+'_flips.json.gz'),'wt',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,allow_nan=False)
    result=dict(models=models,contrasts=contrasts,check_and_train=details,
                tail_composition={name:metrics.tail_composition(baseline,q,models[name]['ranking']) for name,q in all_q.items()},
                AB_tail_comparison={name:metrics.compare_ab_tail(models[name],models['AB']) for name in ('U0','U1')},
                evidence='EXPOSED_DEVELOPMENT_ONLY',original_strict_verdict='HISTORICAL_FAIL_UNCHANGED',commissioning='NOT_EVALUATED',
                scientific_success=False,next_boundary='REVIEW_FULL_CAPABILITY_AND_RISK; NO_AUTOMATIC_PROMOTION_OR_TUNING')
    s.atomic_json(out/'comparison.json',result)
    s.atomic_json(out/'evaluation_receipt.json',dict(encoder_unchanged=True,encoder_sha256=identity,check=check_rec,expanded=expanded_rec,targets=budget.access['evaluated_targets']))
    lines=['# 双视图终点结果','', '开发证据；固定阈值与低误报排序点分别报告。新设备入网未评估。','',
           '|模型|攻击召回|future召回|正常池均误报|最差池误报|TPR@1%|TPR@0.1%|','|---|---:|---:|---:|---:|---:|---:|']
    for name in ('old_P2','AB','C0_AB','H_AB','U0','U1'):
        v=models[name];f=v['fixed'];rank=v['ranking']
        cells=[100*f['overall']['recall'],100*f['future']['recall'],100*f['benign_pool_macro_fpr'],100*f['worst_pool_fpr']]
        tails=['—','—'] if rank is None else ['%.4f%%'%(100*rank['points'][k]['tpr']) for k in ('0.01','0.001')]
        lines.append('|'+name+'|'+'|'.join(['%.4f%%'%c for c in cells]+tails)+'|')
    lines+=['',*(name+': '+v['status'] for name,v in contrasts.items()),'',
            '完整族/池、A/B、CHECK/ID、翻转及尾部见 comparison.json 和 flips 文件。CHECK近天花板不能单独证明突破。']
    (out/'result.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return dict(status='EVALUATION_COMPLETE',targets=budget.access['evaluated_targets'],candidates=['U0','U1'])


def verify_stage(stage,out,r,budget):
    a=budget.access
    s.require(all(a[k]==0 for k in ('E3_model_loads','E3_forwards','teacher_passes','raw_decodes','retries','network_requests')),'FORBIDDEN_ACTION')
    if stage=='P':
        rec=s.read_json(out/'preparation_receipt.json');targets,x=load_matrix(out,rec['train'],budget)
        s.require(a['optimizer_steps']==0 and a['historical_student_loads']==1 and a['AB_target_states']==r['stages']['P']['AB_target_states'] and a['E3_numeric_rows']==r['stages']['P']['E3_numeric_rows'],'P_COUNTS')
        s.require(int(x[:,896].sum())==r['stages']['P']['E3_numeric_rows'] and all(t['new_role']=='train' for t in targets),'P_CONTENT_COUNTS')
    elif stage=='T':
        rec=s.read_json(out/'candidates_sealed.json')
        s.require(set(rec['candidates'])=={'U0','U1'} and a['optimizer_steps']==r['training']['updates_total'] and a['historical_student_loads']==a['encoder_forwards']==a['E3_numeric_rows']==0,'T_COUNTS')
        s.require(rec['order_hashes']['U0']==rec['order_hashes']['U1'],'T_MATCHED_ORDER')
    else:
        rec=s.read_json(out/'evaluation_receipt.json');result=s.read_json(out/'comparison.json')
        s.require(a['historical_student_loads']==1 and a['new_candidate_loads']==2 and a['optimizer_steps']==0 and a['AB_target_states']==r['stages']['E']['AB_target_states'] and a['E3_numeric_rows']==r['stages']['E']['E3_numeric_rows'] and a['evaluated_targets']==r['stages']['E']['head_scores_total'],'E_COUNTS')
        s.require(rec['encoder_unchanged'] and set(result['contrasts'])==set(r['evaluation']['contrasts']) and result['scientific_success'] is False,'E_VERDICT')
    s.atomic_json(out/'verification.json',dict(status='VERIFIED',stage=stage,recipe_sha256=s.RECIPE_SHA,access=dict(a),scientific_success=False))
