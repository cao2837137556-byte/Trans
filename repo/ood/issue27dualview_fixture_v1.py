"""Generated-only fixtures; audit hook denies real run data and network access."""
import copy
import csv
import gzip
import json
import os
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
TEST_ROOT=ROOT/'tmp/dualview_synthetic_v1'


def guard(event,args):
    if event in ('socket.connect','socket.getaddrinfo'):raise RuntimeError('SYNTHETIC_NETWORK_BLOCKED')
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    if os.fsdecode(args[0]).casefold()==os.devnull.casefold():return
    path=Path(os.fsdecode(args[0])).resolve()
    if ROOT/'runs' in path.parents and ROOT/'runs/mainline_docs' not in path.parents:
        raise RuntimeError('SYNTHETIC_BLOCKED_REAL_RUN_ACCESS:'+str(path))


sys.addaudithook(guard)
import numpy as np
import torch
import issue27dualview_support_v1 as s
import issue27dualview_model_v1 as m
import issue27dualview_pipeline_v1 as pipeline
import issue27dualview_control_v1 as control
import issue27dualview_metrics_v1 as metrics


def pin(p):return dict(path=str(p),sha256=s.sha(p))


def context(key,y,owner='A',role='train',events=(0,2),id_row=False):
    ts=[]
    for event in events:
        uid=('id_calib:' if id_row else '')+key+':'+str(event)
        ts.append(dict(uid=uid,context_key=key,event=event,event_index=event,label=y,owner=owner,old_hard=y,
            component_id=key,new_role=role,attack_family='attack'+str(len(key)%2),device_family='normal_family',
            source_group=key,member=key,position=event,timestamp_epoch=100.+event))
    return dict(key=key,role=role,component=key,length=3,targets=ts,x=np.random.default_rng(len(key)).normal(size=(3,131)).astype('<f4'))


def csv_write(path,rows):
    opener=gzip.open if str(path).endswith('.gz') else open
    with opener(path,'wt',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)


def cache(base,name,targets,extra=False):
    rows=[dict(t) for t in targets]
    if extra:
        rows.append(dict(uid='forbidden_select_row',owner='A',position=0,timestamp_epoch=1.))
    rng=np.random.default_rng(99);x=rng.normal(size=(len(rows),768)).astype('<f4');x[:,0]=7.
    missing=np.array([t['owner']=='B' for t in rows],dtype=np.bool_)
    x[missing]=np.nan
    if extra:x[-1]=np.nan
    path=base/(name+'.npz')
    np.savez_compressed(path,representation=x,uid=np.array([t['uid'] for t in rows],dtype=np.str_),missing=missing,
        candidate_id=np.array(['E3']),plan_sha256=np.array([pipeline.PLANS[name]]),contract_sha256=np.array([pipeline.CONTRACT]))
    side=base/(name+'.npz.metadata.csv.gz')
    csv_write(side,[dict(uid=t['uid'],session_id=__import__('hashlib').sha256(t['uid'].encode()).hexdigest(),timestamp_epoch=t['timestamp_epoch'],event_position=t['position']) for t in rows])
    return dict(pin(path),bytes=path.stat().st_size,shape=list(x.shape),missing=int(missing.sum()),metadata_sidecar=pin(side))


def assets(base):
    s.require(TEST_ROOT.resolve() in base.resolve().parents,'FIXTURE_ROOT');base.mkdir(parents=True)
    m.configure();r=copy.deepcopy(s.recipe())
    train=[context('a-normal',0),context('a-attack',1),context('b-normal',0,'B'),context('b-attack',1,'B')]
    train[0]['targets'][0]['old_hard']=1
    checks=[context('check-normal',0,role='check',events=(0,),id_row=True),context('check-attack',1,role='check',events=(0,)),context('check-b',0,'B',role='check',events=(0,))]
    contexts=train+checks;offset=0
    with (base/'features.f32le').open('wb') as f:
        for c in contexts:
            raw=c.pop('x').tobytes();c['offset']=offset;offset+=len(raw);f.write(raw)
            for t in c['targets']:t['feature_prefix_sha256']=s.prefix(raw,t['event'])
    plan=dict(contexts=contexts);s.atomic_json(base/'plan.json',plan)
    rows=s.targets(contexts);csv_write(base/'membership.csv',[{k:t[k] for k in ('uid','context_key','component_id','new_role','owner','label','position')} for t in rows])
    components=[dict(component_id=c['component'],role=c['role'],context_keys=[c['key']]) for c in contexts]
    s.atomic_json(base/'components.json',components);s.atomic_json(base/'edges.json',[])
    for key,name in [('plan','plan.json'),('membership','membership.csv'),('train_check_features','features.f32le')]:r['inputs'][key]=pin(base/name)
    r['inputs']['dependencies']={'components':pin(base/'components.json'),'edges':pin(base/'edges.json')}
    r['data'].update(train_targets=8,train_contexts=4,train_components=4,ID_check_targets=1)
    for owner in 'AB':r['data'][owner]=dict(targets=4,attack=2,benign=2,contexts=2)
    r['data']['check']=dict(targets=3,contexts=3,components=3)
    r['training'].update(epochs=50,batches_per_epoch=1,batch_final_size=8,updates_per_arm=50,updates_total=100,label_presentations_per_arm=400)
    # Build a genuine original Student checkpoint from generated tensors only.
    from issue27frontend_paired_train_model_v1 import Student
    original=Student();ab=base/'AB';ab.mkdir();torch.save(original.state_dict(),ab/'candidate_AB.pt')
    init=dict(pin(ab/'candidate_AB.pt'),state_sha256=m.state_hash(original),bytes=(ab/'candidate_AB.pt').stat().st_size)
    receipt=dict(file_sha256=init['sha256'],state_sha256=init['state_sha256'],epoch=40,updates=7880,initial_state_sha256='generated')
    s.atomic_json(ab/'candidate_AB.receipt.json',receipt);s.atomic_json(ab/'supervisor_terminal.json',dict(verdict=dict(status='PAIRED_COMPARISON_COMPLETE')));s.seal(ab)
    r['inputs']['initial_AB']=init;r['inputs']['initial_AB_receipt']=dict(pin(ab/'candidate_AB.receipt.json'),epoch=40,updates=7880,initial_state_sha256='generated')
    r['inputs']['initial_AB_terminal']=pin(ab/'supervisor_terminal.json');r['inputs']['historical_train_manifest']=pin(ab/'SHA256SUMS')
    s.atomic_json(base/'old_check.json',{'A':[dict(t,hard=t['label']) for t in s.targets(checks)]})
    r['inputs']['historical_check_scores']=pin(base/'old_check.json')
    r['evaluation']['new_candidate_retention_diagnostics'].update(targets=2,attacks=1)
    r['inputs']['e3_caches']['fit_select']=cache(base,'fit_select',rows,extra=True)
    expanded=base/'expanded';member=expanded/'members'/'generated';member.mkdir(parents=True)
    baseline=[];ec=[];offset=0
    with (member/'features.f32le').open('wb') as f:
        for i,y in enumerate((1,1,1,0,0,0)):
            c=context('exp'+str(i),y,'A' if i%2==0 else 'B',role='expanded',events=(0,))
            raw=c.pop('x').tobytes();c['offset']=offset;offset+=len(raw);f.write(raw)
            t=c['targets'][0];t['feature_prefix_sha256']=s.prefix(raw,0);ec.append(c);q=float(3-i)
            baseline.append(dict(uid=t['uid'],label=y,old_hard=y,old_missing=int(t['owner']=='B'),a_hard=int(q>=0),ab_hard=int(q>=0),
                a_logit=q,ab_logit=q,context_key=c['key'],member_id='generated',event_index=0,feature_prefix_sha256=t['feature_prefix_sha256'],
                attack_family='f'+str(i%2),pool='p'+str(i%2),source_group=t['source_group'],device_family=t['device_family'],role='future_query' if i==0 else 'other'))
    with gzip.open(member/'contexts.jsonl.gz','wt',encoding='utf-8') as f:
        for c in ec:f.write(json.dumps(c)+'\n')
    s.atomic_json(expanded/'preparation_receipt.json',dict(members=[dict(member_id='generated',feature_bytes=offset)]))
    csv_write(expanded/'baseline.csv.gz',baseline);s.seal(expanded)
    r['inputs']['expanded_manifest']=pin(expanded/'SHA256SUMS');r['inputs']['expanded_preparation']=pin(expanded/'preparation_receipt.json')
    for key in ('expanded_A_predictions','expanded_AB_P2_predictions'):r['inputs'][key]=pin(expanded/'baseline.csv.gz')
    csv_write(base/'expanded_targets.csv.gz',[dict(t,position=0) for t in baseline])
    r['implementation_metadata']={'expanded_targets':pin(base/'expanded_targets.csv.gz')}
    r['inputs']['e3_caches']['expanded']=cache(base,'expanded',s.targets(ec))
    r['data']['expanded'].update(targets=6,contexts=6,benign_OOD_targets=3)
    r['evaluation'].update(targets_per_arm=17,targets_all_arms=34)
    r['evaluation']['old_attack_reference_exact']=dict(detected=3,targets=3);r['evaluation']['old_future_reference_exact']=dict(detected=1,targets=1)
    r['stages']['P'].update(AB_target_states=8,E3_numeric_rows=4)
    r['stages']['E'].update(AB_target_states=9,E3_numeric_rows=5,head_scores_per_arm=17,head_scores_total=34)
    for arm in ('C0_AB','H_AB'):
        d=base/arm;d.mkdir();files={}
        for role,ts in [('train',s.targets(train)),('check',s.targets(checks)),('expanded',baseline)]:
            p=d/(arm+'_'+role+'.csv.gz');metrics.save_predictions(p,{t['uid']:float(t['label']*2-1) for t in ts});files[role]=pin(p)
        s.seal(d);r['historical_score_references'][arm]=dict(manifest=pin(d/'SHA256SUMS'),files=files)
    return r,plan


def run_direct(base):
    from unittest.mock import patch
    r,plan=assets(base/'assets');outputs={k:base/k for k in 'PTE'};result={}
    with patch.dict(s.OUTPUTS,outputs):
        for stage,fn in [('P',pipeline.prepare),('T',pipeline.fit),('E',pipeline.evaluate)]:
            out=outputs[stage];out.mkdir();budget=control.Budget(out,time.monotonic(),dict(seconds=120));budget.stage=stage;budget.targets_total=r['stages']['E']['head_scores_total']
            result[stage]=fn(r,out,budget);pipeline.verify_stage(stage,out,r,budget)
            s.atomic_json(out/'access.json',dict(budget.access));s.atomic_json(out/'supervisor_terminal.json',dict(status='COMPLETE',verified=True,recipe_sha256=s.RECIPE_SHA));s.seal(out)
    return r,outputs,result


def main():
    from unittest.mock import patch
    mode= sys.argv[1];out=Path(sys.argv[2]).resolve()
    s.require(TEST_ROOT.resolve() in out.parents,'GENERATED_ONLY')
    if mode=='chain':
        r,_=assets(out/'assets')
        r['resource_caps'].update(P_wall_seconds=90,T_wall_seconds=90,E_wall_seconds=90,process_tree_RSS_bytes=2*1024**3,new_artifact_bytes=32*1024**2)
        rp=out/'recipe.json';s.atomic_json(rp,r);outputs={k:out/k for k in 'PTE'}
        with patch.dict(s.OUTPUTS,outputs):
            results=[]
            for stage in 'PTE':
                cmd=[str(s.PYTHON),'-B',str(Path(__file__).resolve()),'worker',str(outputs[stage]),stage,str(rp)]
                result=control.supervise(stage,outputs[stage],control.caps(r,stage),cmd,synthetic=True)
                results.append(result)
                if result['status']!='COMPLETE':break
        print(json.dumps(results));return
    if mode in ('failure','wall'):
        cmd=[str(s.PYTHON),'-B',str(Path(__file__).resolve()),'fault',str(out),mode]
        result=control.supervise('P',out,dict(seconds=4 if mode=='wall' else 30,memory=2*1024**3,output=8*1024**2),cmd,synthetic=True)
        print(json.dumps(result));return
    if mode=='fault':
        if sys.argv[3]=='wall':time.sleep(30);return
        s.atomic_json(out/'worker_terminal.json',dict(status='STOP',stage='P',recipe_sha256=s.RECIPE_SHA,reason='GENERATED_FAILURE'))
        raise SystemExit(1)
    stage=sys.argv[3];rp=Path(sys.argv[4]);r=s.read_json(rp)
    with patch.dict(s.OUTPUTS,{k:out.parent/k for k in 'PTE'}),patch.object(control,'readiness',return_value=r):
        raise SystemExit(control.worker(stage,synthetic=True))


if __name__=='__main__':main()
