"""Generated fixtures with a process-wide block on all non-document real run files."""
import copy
import gzip
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
TEST_ROOT=ROOT/'tmp/readout_synthetic_v1'


def no_real_numeric(event,args):
    if event!='open' or not isinstance(args[0],(str,bytes,os.PathLike)):return
    if os.fsdecode(args[0]).casefold()==os.devnull.casefold():return
    path=Path(os.fsdecode(args[0])).resolve()
    if ROOT/'runs' in path.parents and ROOT/'runs/mainline_docs' not in path.parents:
        raise RuntimeError('SYNTHETIC_BLOCKED_REAL_RUN_ACCESS:'+str(path))


sys.addaudithook(no_real_numeric)
import issue27frontend_readout_support_v1 as s
import issue27frontend_readout_control_v1 as control


def pin(path):return dict(path=str(path),sha256=s.sha(path))


def context(key,y,owner='A',events=(0,2),role='train',old=None):
    import torch
    ts=[dict(uid=key+':'+str(i),context_key=key,event=i,label=y,owner=owner,
        old_hard=y if old is None else old,component_id=key,new_role=role,
        attack_family='attack' if y else 'normal',device_family='device',source_group=key)
        for i in events]
    return dict(key=key,role=role,component=key,length=3,targets=ts,x=torch.randn(3,131))


def generated_assets(base):
    import numpy as np
    import torch
    import issue27frontend_readout_model_v1 as m
    import issue27frontend_readout_evaluate_v1 as e
    base=Path(base).resolve();s.require(TEST_ROOT.resolve() in base.parents,'FIXTURE_ROOT')
    base.mkdir();m.configure()
    cs=[context('a0',0,events=(0,1,2)),context('a1',1),context('a2',0,events=(1,)),
        context('a3',1,events=(2,)),context('a_wrong',0,events=(0,),old=1),
        context('b0',0,'B'),context('b1',1,'B',events=(1,))]
    checks=[context(k,y,g,events=(0,),role='check') for k,y,g in
            [('id_calib:g0',0,'A'),('check_attack',1,'A'),('check_b0',0,'B'),('check_b1',1,'B')]]
    r=copy.deepcopy(s.recipe());epochs=2;steps=1;ts=s.targets(cs)
    r['schedule'].update(epochs=epochs,steps_per_epoch=steps,updates_per_arm=epochs,
        updates_all_arms=epochs,target_presentations_per_arm=len(ts)*epochs,target_presentations_all_arms=len(ts)*epochs)
    r['data'].update(train_targets=len(ts),train_contexts=len(cs),ID_check_targets=1)
    r['data']['check'].update(targets=len(s.targets(checks)),contexts=len(checks))
    for g in 'AB':
        part=[t for t in ts if t['owner']==g]
        r['data'][g]=dict(targets=len(part),attack=sum(t['label'] for t in part),benign=sum(not t['label'] for t in part),contexts=len({t['context_key'] for t in part}))
    ev=sum(c['length'] for c in cs)
    r['schedule']['expected_counts_per_arm']=dict(targets=len(ts)*epochs,contexts=len(cs)*epochs,
        events=ev*epochs,padded_slots=ev*epochs,forwards=2*epochs,updates=epochs)
    r['stages']['T'].update(optimizer_steps=epochs,student_forwards=2*epochs,expected_feature_bytes_decoded=ev*524)
    offset=0
    with (base/'features.f32le').open('wb') as f:
        for c in cs+checks:
            raw=c.pop('x').numpy().astype('<f4').tobytes();c['offset']=offset;offset+=len(raw);f.write(raw)
            for t in c['targets']:t['feature_prefix_sha256']=s.prefix(raw,t['event'])
    orders=[{g+'_order_sha256':hashlib.sha256(s.canonical(s.order([c['key'] for c in cs if c['targets'][0]['owner']==g],epoch,g))).hexdigest() for g in 'AB'} for epoch in range(1,epochs+1)]
    plan=dict(contexts=cs+checks,accounting=dict(epoch_order_hashes=orders))
    s.atomic_json(base/'plan.json',plan);(base/'membership.csv').write_text('generated identity\n')
    model=m.Student();ab=base/'AB_checkpoint';ab.mkdir()
    torch.save(model.state_dict(),ab/'candidate_AB.pt')
    init=pin(ab/'candidate_AB.pt');init.update(state_sha256=m.state_hash(model),bytes=(ab/'candidate_AB.pt').stat().st_size)
    s.atomic_json(ab/'candidate_AB.receipt.json',dict(file_sha256=init['sha256'],state_sha256=init['state_sha256'],epoch=40,updates=7880,initial_state_sha256='generated-origin'))
    s.atomic_json(ab/'supervisor_terminal.json',dict(verdict=dict(status='PAIRED_COMPARISON_COMPLETE')));s.seal(ab)
    r['inputs']['initial_AB']=init
    r['inputs']['initial_AB_receipt']=dict(pin(ab/'candidate_AB.receipt.json'),epoch=40,updates=7880,initial_state_sha256='generated-origin')
    r['inputs']['initial_AB_terminal']=pin(ab/'supervisor_terminal.json')
    r['inputs']['historical_train_manifest']=pin(ab/'SHA256SUMS')
    for k,name in [('plan','plan.json'),('membership','membership.csv'),('train_check_features','features.f32le')]:r['inputs'][k]=pin(base/name)
    s.atomic_json(base/'old_check.json',{'A':[dict(t,hard=t['label']) for t in s.targets(checks)]})
    r['inputs']['historical_check_scores']=pin(base/'old_check.json')
    r['evaluation']['new_candidate_retention_diagnostics'].update(targets=2,attacks=1)
    oldT=base/'C0_AB_T';oldT.mkdir()
    old_result=dict(candidates={'C0_AB':dict(initial_state_sha256=init['state_sha256'],counts=r['schedule']['expected_counts_per_arm'],epoch=epochs)},
                    order_hashes={'C0_AB':[{'A':o['A_order_sha256'],'B':o['B_order_sha256']} for o in orders]})
    s.atomic_json(oldT/'worker_terminal.json',dict(status='WORK_COMPLETE_VERIFIED',stage='T',recipe_sha256=r['base_contract']['sha256'],result=old_result))
    s.atomic_json(oldT/'supervisor_terminal.json',dict(status='COMPLETE'));s.seal(oldT)
    r['comparison_training_receipt'].update(manifest=pin(oldT/'SHA256SUMS'),terminal=pin(oldT/'worker_terminal.json'))
    expanded=base/'expanded';member=expanded/'members'/'generated';member.mkdir(parents=True)
    baseline=[];ec=[];offset=0
    with (member/'features.f32le').open('wb') as f:
        for i,y in enumerate((1,1,1,0,0,0)):
            c=context('exp'+str(i),y,'A' if i%2==0 else 'B',events=(0,))
            raw=c.pop('x').numpy().astype('<f4').tobytes();c['offset']=offset;offset+=len(raw);f.write(raw)
            t=c['targets'][0];t['feature_prefix_sha256']=s.prefix(raw,0);ec.append(c);q=float(3-i)
            baseline.append(dict(uid=t['uid'],label=y,old_hard=y,old_missing=int(t['owner']=='B'),a_hard=int(q>=0),ab_hard=int(q>=0),
                a_logit=q,ab_logit=q,context_key=c['key'],member_id='generated',event_index=0,feature_prefix_sha256=t['feature_prefix_sha256'],
                attack_family='f'+str(i%2),pool='p'+str(i%2),source_group='g'+str(i),device_family='dev',role='future_query' if i==0 else 'other'))
    with gzip.open(member/'contexts.jsonl.gz','wt',encoding='utf-8') as f:
        for c in ec:f.write(json.dumps(c)+'\n')
    s.atomic_json(expanded/'preparation_receipt.json',dict(members=[dict(member_id='generated',feature_bytes=offset)]))
    with gzip.open(expanded/'baseline.csv.gz','wt',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(baseline[0]));writer.writeheader();writer.writerows(baseline)
    s.seal(expanded)
    r['inputs']['expanded_manifest']=pin(expanded/'SHA256SUMS');r['inputs']['expanded_preparation']=pin(expanded/'preparation_receipt.json')
    for k in ('expanded_A_predictions','expanded_AB_P2_predictions'):r['inputs'][k]=pin(expanded/'baseline.csv.gz')
    r['data']['expanded'].update(targets=len(baseline),contexts=len(ec),benign_OOD_targets=3)
    total=len(ts)+len(s.targets(checks))+len(baseline)
    r['evaluation'].update(targets_per_arm=total,targets_all_arms=total)
    r['stages']['E'].update(evaluated_targets=total,student_forwards=3)
    r['evaluation']['old_attack_reference_exact']=dict(detected=3,targets=3)
    r['evaluation']['old_future_reference_exact']=dict(detected=1,targets=1)
    for key,names in [('C0_C1_C2',('C0','C1','C2')),('Q_R',('Q','R')),('C0_AB_R_AB',('C0_AB','R_AB'))]:
        directory=base/key;directory.mkdir()
        for name in names:e.save_predictions(directory/(name+'_expanded.csv.gz'),{t['uid']:t['a_logit']-.1 for t in baseline})
        s.seal(directory);r['historical_score_references'][key]['manifest']=pin(directory/'SHA256SUMS')
    return r,plan


def generated_pipeline(base):
    from unittest.mock import patch
    import issue27frontend_readout_train_v1 as train
    import issue27frontend_readout_evaluate_v1 as e
    from issue27frontend_readout_verify_v1 import verify_stage
    r,plan=generated_assets(base/'assets');outputs={k:base/k for k in 'TE'};results={}
    with patch.dict(s.OUTPUTS,outputs):
        for stage,fn in [('T',train.train),('E',e.evaluate)]:
            out=outputs[stage];out.mkdir();budget=control.Budget(out,time.monotonic(),dict(seconds=120,memory=2*1024**3,output=32*1024**2))
            results[stage]=fn(r,out,budget);verify_stage(stage,out,r,budget)
            s.atomic_json(out/'access.json',budget.access)
            s.atomic_json(out/'supervisor_terminal.json',dict(status='COMPLETE'));s.seal(out)
    return r,outputs,results


def main():
    mode,out=sys.argv[1],Path(sys.argv[2]).resolve()
    s.require(TEST_ROOT.resolve() in out.parents,'GENERATED_DIRECTORY_ONLY')
    if mode in ('supervise','supervise-fail','supervise-wall'):
        worker_mode={'supervise':'worker','supervise-fail':'worker-fail','supervise-wall':'worker-wall'}[mode]
        command=[str(s.PYTHON),'-B',str(Path(__file__).resolve()),worker_mode,str(out)]
        result=control.supervise('T',out,dict(seconds=3 if mode=='supervise-wall' else 45,memory=2*1024**3,output=16*1024**2),command,synthetic=True)
        print(json.dumps(result));return
    deadline=time.monotonic()+30
    while not (out/'worker_gate.json').exists():
        s.require(time.monotonic()<deadline,'GATE_TIMEOUT');time.sleep(.01)
    gate=s.read_json(out/'worker_gate.json');s.require(gate['pid']==os.getpid() and gate['parent_pid']==os.getppid(),'GATE')
    if mode=='worker-wall':
        time.sleep(30);return
    if mode=='worker-fail':
        s.atomic_json(out/'worker_terminal.json',dict(status='STOP',reason='GENERATED_FAILURE',stage='T',recipe_sha256=s.RECIPE_SHA))
        raise SystemExit(1)
    for i in range(200):
        s.atomic_json(out/'progress.json',dict(phase='GENERATED_IO_STRESS',updates=i,padding='x'*4096));time.sleep(.002)
    (out/'generated.txt').write_text('generated progress complete',encoding='utf-8')
    s.atomic_json(out/'worker_terminal.json',dict(status='WORK_COMPLETE_VERIFIED',stage='T',recipe_sha256=s.RECIPE_SHA,
        output_hashes={'generated.txt':s.sha(out/'generated.txt')}))


if __name__=='__main__':main()
