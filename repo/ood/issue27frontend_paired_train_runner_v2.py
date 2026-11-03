"""Separate authorized preparation/training; no raw capture or old model APIs."""
import copy
import time
import traceback
from pathlib import Path
import numpy as np
import torch
import issue27frontend_paired_train_support_v2 as s
import issue27frontend_paired_train_model_v1 as m
import issue27frontend_paired_train_metrics_v1 as metrics
from issue27frontend_paired_train_prefix_fix_v2 import prefix_digest


class Budget:
    def __init__(self,output,caps,start,expected=None):
        self.output,self.caps,self.start,self.expected=output,caps,start,expected
        self.counts=dict(events=0,padded_slots=0,targets=0,contexts=0)
        self.state={'phase':'STARTING','updates':0,'updates_total':0,'retries':0}
        self.last=-1

    def check(self,force=False,**state):
        self.state.update(state)
        elapsed=time.monotonic()-self.start
        s.require(elapsed<self.caps['wall_seconds']-2,'WORKER_WALL_CAP')
        if force or elapsed-self.last>=1:
            self.last=elapsed
            s.atomic_json(self.output/'progress.json',dict(status=self.state['phase'],elapsed_seconds=elapsed,
                **self.state,counts=self.counts))

    def charge(self,batch):
        for k,v in s.charges(batch).items():
            self.counts[k]+=v
            if self.expected:s.require(self.counts[k]<=self.expected[k],'ACTION_CAP_'+k)
        self.check()


def output_hashes(output,names):
    return {n:s.sha_file(output/n) for n in names}


def prepare_data(plan,sources,output,budget):
    """Identity hash, then read exact qualified numeric ranges from two sealed arrays."""
    access={'feature_files':0,'feature_hash_bytes':0,'feature_decoded_bytes':0,'prefixes_verified':0,
            'model_forwards':0,'optimizer_steps':0,'raw_packets':0,'retries':0}
    for name,spec in sources.items():
        path=Path(spec['path']);s.require(path.stat().st_size==spec['bytes'],'SOURCE_SIZE')
        budget.check(True,phase='HASHING_FEATURE_IDENTITY',source=name)
        s.require(s.sha_file(path,budget.check)==spec['sha256'],'FEATURE_IDENTITY')
        access['feature_hash_bytes']+=spec['bytes']
    handles={}
    try:
        for name,spec in sources.items():handles[name]=Path(spec['path']).open('rb')
        with (output/'features.f32le').open('xb') as dest:
            for i,c in enumerate(plan['contexts']):
                budget.check(phase='PREPARING_FEATURE_VIEWS',contexts_complete=i,contexts_total=len(plan['contexts']))
                f=handles[c['source']];f.seek(c['source_offset']);raw=f.read(c['length']*524)
                s.require(len(raw)==c['length']*524,'FEATURE_SHORT_READ')
                x=np.frombuffer(raw,dtype='<f4').reshape(c['length'],131)
                s.require(np.isfinite(x).all(),'FEATURE_NONFINITE')
                for t in c['targets']:
                    s.require(prefix_digest(raw,t['event'])==t['feature_prefix_sha256'],'PREFIX_IDENTITY')
                    access['prefixes_verified']+=1
                s.require(dest.tell()==c['offset'],'PREP_OFFSET')
                dest.write(raw);access['feature_decoded_bytes']+=len(raw)
        access['feature_files']=len(handles)
    finally:
        for f in handles.values():f.close()
    s.require((output/'features.f32le').stat().st_size==plan['feature_bytes'],'PREP_BYTES')
    return access


def load_prepared(plan,path,budget):
    contexts=[]
    with path.open('rb') as f:
        for c in plan['contexts']:
            budget.check(phase='LOADING_PREPARED_FEATURES')
            s.require(f.tell()==c['offset'],'PREP_LAYOUT')
            raw=f.read(c['length']*524)
            s.require(len(raw)==c['length']*524,'PREP_TRUNCATED')
            x=np.frombuffer(raw,dtype='<f4').copy().reshape(c['length'],131)
            s.require(np.isfinite(x).all(),'PREP_NONFINITE')
            contexts.append({**c,'x':torch.from_numpy(x)})
        s.require(f.read(1)==b'','PREP_EXTRA_BYTES')
    return contexts


def save_state(output,name,model,**receipt):
    path=output/(name+'.pt')
    with path.open('xb') as f:torch.save(model.state_dict(),f)
    data=dict(file_sha256=s.sha_file(path),state_sha256=m.state_hash(model),**receipt)
    s.atomic_json(output/(name+'.receipt.json'),data)
    return data


def paired_fit(contexts,initial,output,budget,epochs=40):
    """epochs override exists only for generated direct tests; real worker requires 40."""
    models={'A':copy.deepcopy(initial),'AB':copy.deepcopy(initial)}
    initial_hash=m.state_hash(initial)
    s.require(all(m.state_hash(v)==initial_hash for v in models.values()),'INITIAL_EQUALITY')
    groups={g:{c['key']:c for c in s.views(contexts,'train',g)} for g in ('A','B')}
    na,nb=len(groups['A']),len(groups['B']);s.require(na>0 and nb>0,'EMPTY_OWNER')
    steps=(na+31)//32;receipts={};updates={'A':0,'AB':0};exposure={}
    for arm,model in models.items():
        model.train();opt=m.optimizer(model);a_orders=[]
        for epoch in range(1,epochs+1):
            ak=s.order(groups['A'],epoch,'A');bk=s.order(groups['B'],epoch,'B')
            a_orders.append(s.digest(s.canonical(ak)))
            loss_sum=0.
            for step,(a,b) in enumerate(zip(s.buckets(ak,steps),s.buckets(bk,steps)),1):
                budget.check(phase='TRAINING',arm=arm,epoch=epoch,epochs=epochs,
                             step=step,steps_per_epoch=steps,updates=updates[arm],updates_total=epochs*steps)
                loss_sum+=m.update(model,opt,[groups['A'][k] for k in a],
                    [groups['B'][k] for k in b] if arm=='AB' else [],steps,na,nb,budget.charge)
                updates[arm]+=1
            with (output/'training_log.jsonl').open('ab') as log:
                log.write(s.canonical({'arm':arm,'epoch':epoch,'updates':updates[arm],
                                      'mean_step_training_loss':loss_sum/steps})+b'\n')
            budget.check(True,updates=updates[arm],training_loss=loss_sum/steps)
        receipts[arm]=save_state(output,'candidate_'+arm,model,epoch=epochs,updates=updates[arm],initial_state_sha256=initial_hash)
        exposure[arm]=a_orders
        del opt
    s.require(exposure['A']==exposure['AB'],'A_EXPOSURE_ORDER')
    # This barrier is persisted and verified before even the training-fit forward.
    barrier={'status':'BOTH_TERMINAL_CANDIDATES_SEALED','candidates':receipts,'updates':updates,
             'A_order_hashes':exposure['A'],'initial_state_sha256':initial_hash}
    s.atomic_json(output/'candidates_sealed.json',barrier)
    for arm in models:
        s.require(s.sha_file(output/('candidate_'+arm+'.pt'))==receipts[arm]['file_sha256'],'CANDIDATE_DISK_HASH')
    return models,barrier


def terminal_checks(contexts,models,barrier,output,budget):
    s.require((output/'candidates_sealed.json').exists(),'BOTH_CANDIDATES_REQUIRED')
    s.require(s.read_json(output/'candidates_sealed.json')==barrier,'CANDIDATE_BARRIER')
    checks={};fit={}
    for arm,model in models.items():
        s.require(m.state_hash(model)==barrier['candidates'][arm]['state_sha256'],'CANDIDATE_STATE')
        budget.check(True,phase='POSTFIT_CHECK',arm=arm)
        cs=s.views(contexts,'train',arm)
        fit[arm]=metrics.evaluate(cs,m.infer(model,cs,budget.charge))
        budget.check(True,phase='COMMON_CHECK',arm=arm)
        checks[arm]=m.infer(model,s.views(contexts,'check','AB'),budget.charge)
        s.require(m.state_hash(model)==barrier['candidates'][arm]['state_sha256'],'EVALUATION_MUTATED_MODEL')
    result,rows=metrics.comparison(contexts,checks['A'],checks['AB'])
    s.atomic_json(output/'postfit_predictions.json',fit)
    s.atomic_json(output/'check_predictions.json',rows)
    s.atomic_json(output/'comparison.json',result)
    return result


def worker(output,config,stage,started):
    plan=s.read_json(s.ROOT/s.PACKAGE/'plan.json')
    budget=Budget(output,config['caps'],started,plan['accounting']['total'] if stage=='train' else None)
    try:
        m.configure()
        if stage=='prepare':
            access=prepare_data(plan,config['feature_sources'],output,budget)
            s.atomic_json(output/'preparation_receipt.json',dict(status='PAIRED_FEATURES_PREPARED',access=access,
                plan_sha256=config['plan_sha256'],feature_bytes=plan['feature_bytes'],features_sha256=s.sha_file(output/'features.f32le')))
            names=['features.f32le','preparation_receipt.json']
            verdict={'status':'PAIRED_FEATURES_PREPARED','training_started':False}
        else:
            prep=s.ROOT/s.PREP
            s.verify_manifest(prep)
            receipt=s.read_json(prep/'preparation_receipt.json')
            s.require(receipt['plan_sha256']==config['plan_sha256'] and receipt['features_sha256']==s.sha_file(prep/'features.f32le'),'PREP_IDENTITY')
            contexts=load_prepared(plan,prep/'features.f32le',budget)
            initial=m.Student()
            expected=s.read_json(s.ROOT/s.PACKAGE/'initial.receipt.json')
            s.require(m.state_hash(initial)==expected['state_sha256'],'FRESH_INITIALIZATION_PIN')
            save_state(output,'initial',initial,origin='new_default_seed2705_not_historical')
            models,barrier=paired_fit(contexts,initial,output,budget)
            s.require(barrier['updates']=={'A':7880,'AB':7880},'UPDATE_DENOMINATOR')
            verdict=metrics.compact_result(terminal_checks(contexts,models,barrier,output,budget))
            s.require(budget.counts==plan['accounting']['total'],'FINAL_FORWARD_ACCOUNTING')
            access={'model_initializations':1,'historical_checkpoint_loads':0,'teacher_forwards':0,'raw_packets':0,
                    'optimizer_steps':15760,'retries':0,'check_passes_per_arm':1,'postfit_passes_per_arm':1,
                    'feature_decoded_bytes':plan['feature_bytes']}
            names=['initial.pt','initial.receipt.json','candidate_A.pt','candidate_A.receipt.json','candidate_AB.pt',
                   'candidate_AB.receipt.json','candidates_sealed.json','training_log.jsonl','postfit_predictions.json',
                   'check_predictions.json','comparison.json']
        s.atomic_json(output/'access_receipt.json',access);names.append('access_receipt.json')
        budget.check(True,phase='SEALING')
        terminal={'status':'WORK_COMPLETE','verdict':verdict,'counts':budget.counts,'output_hashes':output_hashes(output,names),
                  'plan_sha256':config['plan_sha256'],'stage':stage}
    except Exception as exc:
        terminal={'status':'INPUT_OR_EXECUTION_STOP','reason':type(exc).__name__+': '+str(exc)[:1500],
                  'traceback':traceback.format_exc()[-10000:],'counts':budget.counts,'stage':stage}
    s.atomic_json(output/'worker_terminal.json',terminal)
