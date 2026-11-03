"""Fixed modern-head comparison followed by two predeclared onboarding pairs."""
import argparse
import gc
import importlib.metadata
import os
from pathlib import Path
import platform
import shutil
import signal
import subprocess
import sys
import time
import numpy as np
import torch
import continuous_common_v3 as c
import modern_head_resources_v1 as resources
import query_tail_core_v2 as k
import query_tail_prepare_v2 as prepare
import constrained_onboarding_query_tail_adapter_v2 as prior
from engineering_progress_v1 import disk_bytes
from legacy_unsw_archival_runtime_v1 import tree_rss
from onboarding_delivery_v1 import terminate_group
from resource_observation_v1 import StageRecorder, RSS_SCOPE

FAMILIES=('MLP_QUERY_BCE','TabM','LightGBM')
STAGES=('P',)+tuple('T_'+f+'_'+str(s) for f in FAMILIES for s in c.SEEDS)+('K','M_TabM','M_LightGBM')
HEAD_STAGES=STAGES[:-2]
MODULE_STAGES=STAGES[-2:]


def scope(root, runtime):
    root=Path(root).resolve(); run=root/'runs/modern_heads'
    for relative in ('','heads','heads/endpoints','monitor','logs','onboarding'):
        path=run/relative
        c.require(path.resolve()==path,'MODERN_OUTPUT_REDIRECT')
    for source in runtime['paths'].values():
        source=Path(source).resolve()
        c.require(not source.is_relative_to(root) and not root.is_relative_to(source),'MODERN_INPUT_OUTPUT_OVERLAP')
    return run


def contract(root, allocation=False):
    root=Path(root).resolve(); c.verify(root,exact=False)
    config=c.read(root/'experiment_contract.json'); runtime=c.read(root/'runtime_contract.json')
    plan=resources.load(root/'resource_plan.json')
    from modern_head_models_v1 import validate_config
    from modern_head_evaluate_v1 import validate_config as validate_evaluation
    validate_config(config); validate_evaluation(config,c.read(c.pin(root/'query_tail_design.json',k.DESIGN_SHA)))
    c.pin(root/'protocol.json',prior.PROTOCOL_SHA256)
    c.require(runtime['experiment_contract_sha256']==c.sha(root/'experiment_contract.json') and
              runtime['resource_plan_sha256']==c.sha(root/'resource_plan.json') and runtime['retries']==0,'MODERN_CONTRACT_BINDING')
    identity=plan['workload_identity']
    c.require(identity['experiment_contract_sha256']==runtime['experiment_contract_sha256'] and
              identity['families']==list(FAMILIES) and identity['seeds']==list(c.SEEDS) and
              identity['onboarding_families']==['TabM','LightGBM'],'MODERN_WORKLOAD_BINDING')
    c.require(runtime['export_included_limit_gib']==plan['export_included_limit_gib'],'MODERN_EXPORT_LIMIT_DRIFT')
    scope(root,runtime)
    if allocation:
        c.require(os.environ.get('SLURM_JOB_ID') and os.environ.get('MODERN_HEAD_AUTHORIZED')==runtime['experiment_contract_sha256'] and
                  os.environ.get('MODERN_HEAD_RESOURCE_SHA')==runtime['resource_plan_sha256'],'MODERN_SUBMITTED_IDENTITY')
        c.require(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))==plan['cpus'] and
                  int(os.environ.get('SLURM_MEM_PER_NODE','0'))==plan['memory_gib']*1024 and
                  int(os.environ.get('SLURM_JOB_NUM_NODES','1'))==1,'MODERN_ALLOCATION')
    return config,runtime,plan


def environment():
    return dict(python=platform.python_version(),numpy=np.__version__,torch=torch.__version__,
                torch_config=torch.__config__.show(),cpu_capability=torch.backends.cpu.get_cpu_capability(),
                machine=platform.machine(),threads=4)


def dependency_check(runtime):
    c.require(sys.version_info[:2]==(3,9),'MODERN_PYTHON39')
    for name,value in runtime['versions'].items():
        c.require(importlib.metadata.version(name).split('+')[0]==value,'MODERN_DEPENDENCY:'+name)
    from modern_head_models_v1 import official_tabm
    official_tabm()
    import lightgbm
    c.require(lightgbm.__version__=='4.6.0','MODERN_LIGHTGBM')
    if sys.platform=='linux':
        name,version=platform.libc_ver()
        c.require(name=='glibc' and tuple(map(int,version.split('.')[:2]))>=(2,28),'MODERN_WHEEL_GLIBC_2_28_REQUIRED')


def inputs_head(root,runtime,full=True):
    parent=Path(runtime['paths']['parent']); old=Path(runtime['paths']['prepared_run'])
    oldroot=old.parent.parent
    c.pin(oldroot/'SHA256SUMS',runtime['query_tail_package_seal_sha256']); c.verify(oldroot,exact=False)
    prior._required_files(parent,old,Path(root)/'query_tail_design.json')
    if full: c.verify(old)
    for rel,digest in prior.PARENT_PINS.items(): c.pin(parent/rel,digest)
    for marker in ('P','T','K'):
        c.require(c.read(old/(marker+'_COMPLETE.json'))['status']=='COMPLETE','MODERN_PREPARED_INCOMPLETE')
    c.require(c.read(old/'T_COMPLETE.json')['total_updates']==869040,'MODERN_PREPARED_T')
    c.pin(old/'decision.json',c.read(old/'K_COMPLETE.json')['decision_sha256'])
    seal=c.read(old/'P_COMPLETE.json')['prepared_seal']; c.pin(old/'prepared/SHA256SUMS',seal)
    c.verify(old/'prepared'); c.verify(old/'training_metadata')
    compact=c.read(old/'compact_metadata_receipt.json')
    c.pin(old/'training_metadata/SHA256SUMS',compact['seal'])
    c.require(compact['source_sha256']==c.sha(old/'prepared/LEARN.jsonl.gz'),'MODERN_COMPACT_SOURCE')
    return parent,old


def inputs_module(root,runtime):
    bankroot=Path(runtime['paths']['onboarding_root']); bankrun=bankroot/'runs/onboarding'
    c.pin(bankroot/'SHA256SUMS',runtime['onboarding_package_seal_sha256']); c.verify(bankroot,exact=False)
    complete=c.read(bankrun/'COMPLETE.json')
    c.require(complete['status']=='COMPLETE' and complete['optimizer_updates']==0,'MODERN_BANK_PREPARATION_REQUIRED')
    spec=c.read(bankrun/'banks_manifest.json'); c.require(set(spec)=={'pools'} and set(spec['pools'])=={'CIC_DEV','UNSW_DEV'},'MODERN_BANK_POOLS')
    for pool,banks in spec['pools'].items():
        c.require(set(banks)=={'B0','B1','B2'},'MODERN_BANK_POLICIES')
        for policy,item in banks.items():
            folder=(bankrun/item['path']).resolve()
            c.require(folder.is_relative_to((bankrun/'encoded'/pool).resolve()),'MODERN_BANK_PATH_ESCAPE')
            receipt=c.read(c.pin(folder/'receipt.json',item['receipt_sha256']))
            c.require(receipt['status']=='COMPLETE' and receipt['synthetic_only'] is False and receipt['policy']==policy,'MODERN_BANK_RECEIPT')
            c.verify(folder)
    return bankrun


def execution_mode(heads_only=False,modules_only=False):
    c.require(not (heads_only and modules_only),'MODERN_EXECUTION_MODE_CONFLICT')
    return 'heads' if heads_only else 'modules' if modules_only else 'full'


def verified_heads(run,config):
    run=Path(run); head=run/'heads'; done=c.read(run/'HEADS_COMPLETE.json')
    c.require(done.get('status')=='COMPLETE' and done.get('config_digest')==c.digest(config),
              'MODERN_HEADS_COMPLETE_REQUIRED')
    c.pin(head/'SHA256SUMS',done['head_seal_sha256']); c.verify(head)
    for marker in ('P','T','K'):
        receipt=c.read(head/(marker+'_COMPLETE.json'))
        c.require(receipt.get('status')=='COMPLETE' and receipt.get('config_digest')==c.digest(config),
                  'MODERN_HEADS_STAGE_IDENTITY:'+marker)
    k_done=c.read(head/'K_COMPLETE.json')
    c.require(k_done['decision_sha256']==done['decision_sha256'],'MODERN_HEADS_DECISION_IDENTITY')
    c.pin(head/'decision.json',done['decision_sha256'])
    return done


def preflight(root,heads_only=False,modules_only=False):
    mode=execution_mode(heads_only,modules_only)
    config,runtime,plan=contract(root); dependency_check(runtime)
    parent,old=inputs_head(root,runtime)
    result=dict(status='READY_NO_EXPERIMENT_STARTED',execution_mode=mode,config_digest=c.digest(config),
                prepared_seal=c.sha(old/'prepared/SHA256SUMS'))
    if mode!='heads':
        bankrun=inputs_module(root,runtime)
        result['banks_manifest_sha256']=c.sha(bankrun/'banks_manifest.json')
    if mode=='modules':
        run=scope(root,runtime); verified_heads(run,config)
        c.require(not (run/'MODULES_STARTED.json').exists(),'MODERN_MODULES_NO_RETRY')
        c.require(not any((run/'onboarding').iterdir()),'MODERN_MODULE_OUTPUT_EXISTS')
    c.require(shutil.disk_usage(root).free>=plan['minimum_free_gib']*1024**3,'MODERN_FREE_DISK')
    return result


class Tick:
    def __init__(self,path): self.path=Path(path); self.stage='START'; self.optimizer_updates=0; self.last=0.
    def tick(self,done,total,force=False):
        if force or time.monotonic()-self.last>5:
            c.write(self.path,dict(stage=self.stage,completed=int(done),total=int(total),optimizer_updates=self.optimizer_updates),replace=True)
            self.last=time.monotonic()


def prepare_phase(root,run,config,runtime,progress):
    parent,old=inputs_head(root,runtime)
    design=c.read(root/'query_tail_design.json')
    metadata,indices=prepare.load_metadata(parent,design)
    arrays,norm=prepare.arrays(parent,design,progress=progress)
    prior._prepared_inputs(parent,old,design,indices,norm)
    fingerprints=environment(); reuse={'status':'TRAIN_REQUIRED','reason':'BASELINE_NUMERIC_RUNTIME_FINGERPRINT_UNAVAILABLE'}
    old_env=old/'numeric_runtime.json'
    if old_env.is_file():
        # Only a fingerprint sealed with the original run is evidence.
        names={line.split('  ',1)[1] for line in (old/'SHA256SUMS').read_text().splitlines()}
        c.require('numeric_runtime.json' in names,'MODERN_UNSEALED_BASELINE_ENV')
        if c.read(old_env)!=fingerprints:
            reuse['reason']='BASELINE_NUMERIC_RUNTIME_DIFFERS'
        else:
            del metadata,arrays,indices; gc.collect()
            try:
                bundle=prior.prepare_query_tail(parent,old,root/'query_tail_design.json',arm='QUERY_BCE',progress=progress)
            except RuntimeError as exc:
                if not str(exc).startswith(('ADAPTER_SCORE_NOT_BITWISE','ADAPTER_HEAD_DECISION_DRIFT')): raise
                reuse['reason']='BASELINE_NUMERIC_REPLAY_FAILED'; reuse['detail']=str(exc)
            else:
                fit=bundle['source_fit']['rows']
                import hashlib
                ordered=hashlib.sha256(''.join(r['uid']+'\n' for r in fit).encode()).hexdigest()
                proofs={}
                replay=bundle['replay_evidence']
                c.write(run/'heads/reuse_adapter_replay.json',replay)
                import modern_head_train_v1 as train
                preconditions={}
                for seed in c.SEEDS:
                    folder=old/'endpoints'/('QUERY_BCE_'+str(seed)); endpoint=c.read(folder/'endpoint.json')
                    proofs[str(seed)]=dict(status='PASS',runtime_compatible=True,runtime_fingerprint=fingerprints,
                        score_and_decision_bitwise={pool:bool(evidence['heads'][str(seed)]['score']['bitwise_equal'] and
                            evidence['heads'][str(seed)]['decision']['bitwise_equal']) for pool,evidence in replay['pools'].items()},seed=seed,
                        adapter_replay_evidence=replay,adapter_replay_sha256=c.sha(run/'heads/reuse_adapter_replay.json'),
                        ordered_uid_sha256=ordered,original_head_sha256=endpoint['head_sha256'],
                        original_endpoint_sha256=c.sha(folder/'endpoint.json'),original_design_digest=c.digest(design))
                    data=bundle['source_fit']
                    preconditions[str(seed)]=train.reuse_mlp_preconditions(folder,design,config,fit,
                        data['e3'],data['q14'],bundle['normalizer'],np.arange(len(fit),dtype=np.int64),proofs[str(seed)])
                replay_checks={seed:proof['score_and_decision_bitwise'] for seed,proof in proofs.items()}
                replay_ok=all(set(v)=={'CAL','CIC_DEV','UNSW_DEV'} and all(v.values()) for v in replay_checks.values())
                if replay_ok and all(v['status']=='PASS' for v in preconditions.values()):
                    reuse=dict(status='REUSE_VERIFIED',proofs=proofs,preconditions=preconditions)
                else:
                    reuse=dict(status='TRAIN_REQUIRED',reason='BASELINE_REUSE_PRECONDITIONS_FAILED',
                               preconditions=preconditions,replay_checks=replay_checks)
    c.write(run/'heads/reuse_plan.json',reuse)
    c.write(run/'heads/numeric_runtime.json',fingerprints)
    c.write(run/'heads/P_COMPLETE.json',dict(status='COMPLETE',config_digest=c.digest(config),
            prepared_seal=c.sha(old/'prepared/SHA256SUMS')))


def train_phase(root,run,config,runtime,family,seed,progress):
    import training_metadata_v1 as compact
    import modern_head_train_v1 as train
    old=Path(runtime['paths']['prepared_run']); parent=Path(runtime['paths']['parent'])
    c.pin(old/'prepared/SHA256SUMS',c.read(run/'heads/P_COMPLETE.json')['prepared_seal']); c.verify(old/'prepared')
    receipt=c.read(old/'compact_metadata_receipt.json'); c.pin(old/'training_metadata/SHA256SUMS',receipt['seal'])
    design=c.read(root/'query_tail_design.json')
    rows=compact.Rows(old/'training_metadata',expected_source_sha256=receipt['source_sha256'],expected_uid_sha256=design['data']['uid_sha256']['LEARN'])
    try:
        with np.load(old/'prepared/FIT.npz',allow_pickle=False) as f: ix=f['indices'].copy()
        with np.load(old/'prepared/normalizer.npz',allow_pickle=False) as f: norm=f['mean'].copy(),f['scale'].copy()
        pins=prepare.manifest(parent/'features',design['provenance']['feature_manifest_sha256'])
        values=np.load(c.pin(parent/'features/LEARN.npy',pins['LEARN.npy']),mmap_mode='r',allow_pickle=False)
        q=np.load(old/'prepared/LEARN_q.npy',mmap_mode='r',allow_pickle=False)
        out=run/'heads/endpoints'/(family+'_'+str(seed)); reuse=c.read(run/'heads/reuse_plan.json')
        if family=='MLP_QUERY_BCE' and reuse['status']=='REUSE_VERIFIED':
            try:
                train.adopt_mlp(old/'endpoints'/('QUERY_BCE_'+str(seed)),design,config,rows,values,q,norm,ix,out,reuse['proofs'][str(seed)])
            except train.ReuseIneligible as exc:
                # This typed exception is raised before creating output. Hash/seal
                # corruption is never caught as a reason to silently retrain.
                c.require(not out.exists(),'MODERN_REUSE_PARTIAL_OUTPUT')
                c.write(run/'heads'/('reuse_fallback_'+str(seed)+'.json'),dict(status='TRAIN_REQUIRED',reason=exc.reason))
                train.train(config,rows,values,q,norm,ix,family,seed,out,progress)
        else: train.train(config,rows,values,q,norm,ix,family,seed,out,progress)
    finally: rows.close()


def stage(root,name):
    root=Path(root).resolve(); config,runtime,plan=contract(root,True); dependency_check(runtime)
    run=scope(root,runtime); launch=c.read(run/'stage_launch.json')
    c.require(launch==dict(stage=name,resource_plan_sha256=c.sha(root/'resource_plan.json'),
                          contract_sha256=c.sha(root/'experiment_contract.json')),'MODERN_STAGE_LAUNCH')
    progress=Tick(run/'monitor'/name/'worker_status.json')
    if name=='P': prepare_phase(root,run,config,runtime,progress)
    elif name.startswith('T_'):
        family,seed=name[2:].rsplit('_',1); train_phase(root,run,config,runtime,family,int(seed),progress)
    elif name=='K':
        import modern_head_evaluate_v1 as evaluate
        parent=Path(runtime['paths']['parent']); old=Path(runtime['paths']['prepared_run']); design=c.read(root/'query_tail_design.json')
        metadata,indices=prepare.load_metadata(parent,design); arrays,norm=prepare.arrays(parent,design,progress=progress)
        q=prior._prepared_inputs(parent,old,design,indices,norm)
        evaluate.evaluate(root,parent,run/'heads',config,metadata,indices,arrays,q,norm,progress)
        c.seal(run/'heads'); c.verify(run/'heads')
    else:
        import modern_head_onboarding_v1 as adapter
        import constrained_onboarding_runner_v2 as module
        family=name[2:]; banks=Path(runtime['paths']['onboarding_root'])/'runs/onboarding/banks_manifest.json'
        heads_done=verified_heads(run,config)
        module_start=c.read(run/'MODULES_STARTED.json')
        c.require(module_start['config_digest']==c.digest(config) and
                  module_start['head_seal_sha256']==heads_done['head_seal_sha256'],'MODERN_MODULE_CONTRACT')
        c.pin(banks,module_start['banks_manifest_sha256'])
        bundle=adapter.prepare_modern(runtime['paths']['parent'],runtime['paths']['prepared_run'],run/'heads',
                                      root/'query_tail_design.json',root/'experiment_contract.json',family,progress)
        module.attach_reference_banks(bundle,banks)
        c.require(all(set(v['banks'])=={'OLD_BANK','B0','B1','B2'} for v in bundle['targets'].values()),'MODERN_BANK_MATRIX')
        result=module.run_development(bundle,run/'onboarding'/family,root/'protocol.json')
        c.require(result.get('optimizer_updates')==0,'MODERN_MODULE_NO_OPTIMIZER_UPDATES')
        c.require(result['status']=='COMPLETE' and not result['automatic_model_selection'] and
                  all(v['status']!='PASS' for v in result['scientific_decisions'].values()),'MODERN_NO_FULL_PASS')


def launch(root,run,name,plan,started):
    c.write(run/'stage_launch.json',dict(stage=name,resource_plan_sha256=c.sha(root/'resource_plan.json'),
                                       contract_sha256=c.sha(root/'experiment_contract.json')),replace=True)
    monitor=run/'monitor'/name; monitor.mkdir(); recorder=StageRecorder(monitor); child=None; peak=0
    try:
        with (run/'logs'/(name+'.log')).open('x',encoding='utf-8') as stream:
            child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'stage','--root',str(root),
                                    '--name',name,'--authorize-chain'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=os.name=='posix')
            last_disk=0.
            while True:
                now=time.monotonic(); rss=tree_rss(); peak=max(peak,rss); recorder.observe(name,rss)
                c.require(rss<plan['guard_gib']*1024**3,'MODERN_MEMORY_LIMIT')
                c.require(now-started<plan['wall_seconds'],'MODERN_TIME_LIMIT')
                c.require(not (run/'STOP_REQUESTED').exists(),'MODERN_STOP_REQUESTED')
                if now-last_disk>10:
                    c.require(disk_bytes(run)<plan['disk_gib']*1024**3 and shutil.disk_usage(run).free>1024**3,'MODERN_DISK_LIMIT'); last_disk=now
                if child.poll() is not None: break
                time.sleep(.5)
            c.require(child.returncode==0,'MODERN_STAGE_FAILED:'+name+':'+str(child.returncode))
            c.require(disk_bytes(run)<plan['disk_gib']*1024**3,'MODERN_FINAL_DISK_LIMIT')
        c.write(monitor/'status.json',dict(status='COMPLETE',sampled_peak_tree_rss_bytes=peak,measure=RSS_SCOPE,exit_code=0))
    finally:
        if child is not None and child.poll() is None: terminate_group(child)


def run(root,explicit,heads_only=False,modules_only=False):
    c.require(explicit,'MODERN_EXPLICIT_CHAIN_REQUIRED'); root=Path(root).resolve()
    mode=execution_mode(heads_only,modules_only)
    config,runtime,plan=contract(root,True); preflight(root,heads_only,modules_only); target=scope(root,runtime)
    if mode!='modules':
        c.require(not target.exists(),'MODERN_NO_RETRY'); target.mkdir(parents=True)
        for name in ('heads/endpoints','monitor','logs','onboarding'): (target/name).mkdir(parents=True)
    else:
        verified_heads(target,config)
        c.require(not (target/'MODULES_STARTED.json').exists(),'MODERN_MODULES_NO_RETRY')
    auth='module_authorization.json' if mode=='modules' else 'authorization.json'
    c.write(target/auth,dict(execution_mode=mode,contract_sha256=c.sha(root/'experiment_contract.json'),resource_sha256=c.sha(root/'resource_plan.json'),retries=0))
    started=time.monotonic(); current='START'
    def stop(signum,frame): raise RuntimeError('MODERN_SIGNAL:'+str(signum))
    previous={s:signal.signal(s,stop) for s in (signal.SIGTERM,signal.SIGINT)}
    try:
        for name in (HEAD_STAGES if mode=='heads' else MODULE_STAGES if mode=='modules' else STAGES):
            current=name
            if name==MODULE_STAGES[0]:
                completed=verified_heads(target,config)
                banks=inputs_module(root,runtime)
                c.write(target/'MODULES_STARTED.json',dict(config_digest=c.digest(config),
                    head_seal_sha256=completed['head_seal_sha256'],banks_manifest_sha256=c.sha(banks/'banks_manifest.json')))
            if name=='K':
                endpoints=[c.read(target/'heads/endpoints'/(f+'_'+str(s))/'endpoint.json') for f in FAMILIES for s in c.SEEDS]
                c.write(target/'heads/T_COMPLETE.json',dict(status='COMPLETE',config_digest=c.digest(config),endpoints=endpoints))
            launch(root,target,name,plan,started)
            if name=='K':
                c.verify(target/'heads')
                c.write(target/'HEADS_COMPLETE.json',dict(status='COMPLETE',config_digest=c.digest(config),
                    head_seal_sha256=c.sha(target/'heads/SHA256SUMS'),decision_sha256=c.sha(target/'heads/decision.json')))
                c.write(target/'head_status.json',dict(status='COMPLETE',stages=list(HEAD_STAGES),elapsed_seconds=time.monotonic()-started))
        if mode!='heads':
            c.write(target/'COMPLETE.json',dict(status='COMPLETE',head_decision_sha256=c.sha(target/'heads/decision.json'),
                onboarding_families=['TabM','LightGBM'],required_three_device_regression='NOT_RUN',independent_confirmation='NOT_RUN',automatic_selection=False))
            c.write(target/'module_status.json',dict(status='COMPLETE',elapsed_seconds=time.monotonic()-started))
        c.write(target/'status.json',dict(status='HEADS_COMPLETE_MODULES_PENDING' if mode=='heads' else 'COMPLETE',
            execution_mode=mode,elapsed_seconds=time.monotonic()-started),replace=mode=='modules')
    except BaseException as exc:
        state=dict(status='STOPPED_NO_RETRY',execution_mode=mode,stage=current,error=repr(exc))
        c.write(target/('module_status.json' if current.startswith('M_') or mode=='modules' else 'status.json'),state,replace=True)
        raise
    finally:
        for s,handler in previous.items(): signal.signal(s,handler)


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('mode',choices=('resources','preflight','run','stage'))
    parser.add_argument('--root',required=True); parser.add_argument('--name',choices=STAGES)
    modes=parser.add_mutually_exclusive_group(); modes.add_argument('--heads-only',action='store_true'); modes.add_argument('--modules-only',action='store_true')
    parser.add_argument('--authorize-chain',action='store_true'); parser.add_argument('--slurm-fields',action='store_true'); args=parser.parse_args()
    if args.mode=='resources':
        config,runtime,plan=contract(args.root)
        print('%s %s %s %s'%(plan['memory_gib'],plan['cpus'],runtime['resource_plan_sha256'],runtime['experiment_contract_sha256']) if args.slurm_fields else 'MODERN_RESOURCES_VALID')
    elif args.mode=='preflight': print(preflight(args.root,args.heads_only,args.modules_only))
    elif args.mode=='run': run(args.root,args.authorize_chain,args.heads_only,args.modules_only)
    else:
        c.require(args.authorize_chain and args.name,'MODERN_STAGE_AUTHORITY'); stage(args.root,args.name)


if __name__=='__main__': main()
