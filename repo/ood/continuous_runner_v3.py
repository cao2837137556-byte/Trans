"""One explicit P/T/K chain. No restart, fallback model, or automatic retry."""
import argparse
import importlib.metadata
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import numpy as np
import torch
import continuous_common_v3 as c
import continuous_model_v3 as m
import continuous_data_v3 as d
import continuous_features_v3 as f
import continuous_train_v3 as t
import continuous_evaluate_v3 as e
import continuous_audit_v3 as audit_api


def matrices(run, metadata, role):
    run = Path(run)
    new = np.load(run/'features'/(role+'.npy'), mmap_mode='r', allow_pickle=False)
    old = np.load(c.read(run/'inputs/old_features.json')[role], mmap_mode='r', allow_pickle=False)
    if role == 'UNSW_DEV': old = old[:len(metadata[role])]
    c.require(len(old) == len(new) == len(metadata[role]), 'MATRIX_ROW_JOIN')
    return dict(rows=metadata[role], OLD_MATCHED=old, RECENT=new[:,:768], RECENT_STATE=new)


def norms_from(run):
    c.verify(Path(run)/'normalizers')
    result = {}
    for arm in c.ARMS:
        with np.load(Path(run)/'normalizers'/(arm+'.npz'), allow_pickle=False) as saved:
            result[arm] = (saved['mean'].copy(), saved['scale'].copy())
    return result


def bank_from(run, metadata, role, partition, norm):
    allowed={partition} if isinstance(partition,str) else set(partition)
    rows = metadata[role]; ix = [i for i,r in enumerate(rows) if r['partition'] in allowed]
    array = np.load(Path(run)/'features'/(role+'.npy'), mmap_mode='r', allow_pickle=False)
    return m.Bank([rows[i] for i in ix], m.normalized(array, np.asarray(ix), norm), allowed)


def eligible(rows, indices, bank):
    # Frozen census eligible_rows/SHA uses >=2, distinct from the loss API's minimum=1.
    return np.asarray([i for i in indices if len(bank.groups.get((rows[i]['device'], rows[i]['protocol']),[]))>=2
        and bank.ends[rows[i]['device']] < rows[i]['timestamp']], dtype=np.int64)


def prepare_normalizers(run, metadata, design, progress):
    out = Path(run)/'normalizers'; out.mkdir()
    values = matrices(run, metadata, 'LEARN')
    with np.load(Path(run)/'inputs/FIT.npz', allow_pickle=False) as saved: fit = saved['indices'].copy()
    norms = {}
    for arm in c.ARMS:
        progress.stage = 'P_FIT_NORMALIZER_'+arm; progress.tick()
        norms[arm] = m.fit_normalizer(values[arm], metadata['LEARN'], fit)
        c.save_arrays(out/(arm+'.npz'), mean=norms[arm][0], scale=norms[arm][1])
    bank = bank_from(run, metadata, 'SOURCE_REFS', 'LEARN', norms['RECENT_STATE'])
    for role in ('FIT','CAL'):
        with np.load(Path(run)/('inputs/'+role+'.npz'), allow_pickle=False) as saved: ix = saved['indices'].copy()
        use = eligible(metadata['LEARN'], ix, bank); spec = design['data']['fit_cal_identity'][role]
        c.require(len(use) == spec['eligible_rows'] and c.uid_sha(metadata['LEARN'][i]['uid'] for i in use) == spec['eligible_uid_sha256'], 'ELIGIBILITY_'+role)
        c.save_arrays(out/(role+'_eligible.npz'), indices=use)
    c.write(out/'receipt.json', dict(status='COMPLETE', fit_rows=len(fit), external_used=False, reference_used=False))
    c.seal(out); c.verify(out)


def read_metadata(run):
    return {role:list(c.rows(Path(run)/'inputs'/(role+'.jsonl.gz'))) for role in
            ('LEARN','CIC_DEV','SOURCE_REFS','UNSW_DEV','UNSW_REFS')}


def train_worker(root, run, arm, seed, explicit):
    design, runtime = c.authorize(root, explicit)
    run = Path(run); c.pin(run/'P_COMPLETE.json', c.read(run/'launch_T.json')['P_sha256'])
    c.verify(run/'inputs'); c.verify(run/'features'); c.verify(run/'normalizers')
    progress = c.Progress(run/('train_monitor_'+arm+'_'+str(seed)), runtime['worker_limits'])
    progress.stage = 'T_'+arm+'_'+str(seed)
    try:
        metadata = read_metadata(run); values = matrices(run, metadata, 'LEARN'); norms = norms_from(run)
        kind = 'RECENT_STATE' if arm == 'LEARNED' else arm
        index_file = 'normalizers/FIT_eligible.npz' if arm == 'LEARNED' else 'inputs/FIT.npz'
        with np.load(run/index_file, allow_pickle=False) as saved: ix = saved['indices'].copy()
        bank = bank_from(run, metadata, 'SOURCE_REFS', 'LEARN', norms[kind]) if arm == 'LEARNED' else None
        t.train(design, metadata['LEARN'], values[kind], norms[kind], ix, bank, arm, seed,
                run/'endpoints'/(arm+'_'+str(seed)), progress)
        progress.stop('COMPLETE')
    except BaseException as exc:
        progress.record_failure(exc, 'train_worker'); progress.stop('STOPPED_NO_RETRY', error=repr(exc)); raise


def launch(root, run, tasks, concurrency, progress):
    pending = list(tasks); active = []; finished = []; launched = []
    def stop_children():
        # Workers create new sessions; kill their complete process groups, including decoders.
        for item in active:
            p = item['process']
            try:
                if os.name != 'nt': os.killpg(p.pid, signal.SIGTERM)
                elif p.poll() is None: p.terminate()
            except ProcessLookupError: pass
        for item in active:
            try: item['process'].wait(timeout=10)
            except subprocess.TimeoutExpired: item['process'].kill(); item['process'].wait()
            item['stream'].close()
    try:
        while pending or active:
            progress.guard()
            while pending and len(active) < concurrency:
                name, args, status_path = pending.pop(0)
                stream = (Path(run)/'logs'/(name+'.log')).open('x', encoding='utf-8')
                command = [sys.executable, str(Path(root)/'repo/ood/continuous_runner_v3.py'), *args,
                    '--root',str(root),'--run',str(run),'--authorize-chain']
                p = subprocess.Popen(command, stdout=stream, stderr=subprocess.STDOUT, start_new_session=os.name!='nt')
                p.continuous_group = os.name!='nt'
                progress.children.append(p); active.append(dict(name=name, process=p, stream=stream, status=status_path));launched.append(active[-1])
            for item in active[:]:
                code = item['process'].poll()
                if code is None: continue
                item['stream'].close()
                if code != 0:
                    reason = Path(run)/item['status'].parent/'first_failure.json'
                    detail = c.read(reason) if reason.exists() else {'worker':item['name'],'exit_code':code}
                    raise RuntimeError('WORKER_FAILED:'+str(detail))
                c.require(c.read(Path(run)/item['status'])['status']=='COMPLETE', 'WORKER_FALSE_COMPLETION')
                active.remove(item); finished.append(item['name'])
            states = []
            for _,_,rel in tasks:
                path=Path(run)/rel
                if path.exists(): states.append(c.read(path))
            if progress.stage=='P_FEATURE_WORKERS':
                progress.tick(sum(x.get('completed',0) for x in states),c.read(Path(run)/'spool/receipt.json')['rows'])
            elif progress.stage=='T_FIXED_12_HEADS':
                progress.optimizer_updates=sum(x.get('optimizer_updates',0) for x in states)
                progress.tick(progress.optimizer_updates,sum(x.get('total',0) for x in states))
            else: progress.tick(len(finished),len(tasks))
            if active: progress.closed.wait(2)
        c.write(Path(run)/(progress.stage+'_workers.json'), dict(completed=finished, retries=0))
    except BaseException as exc:
        progress.record_failure(exc,'launcher'); stop_children(); raise
    finally:
        c.write(Path(run)/(progress.stage+'_terminal_states.json'),
                [dict(worker=x['name'],pid=x['process'].pid,exit_code=x['process'].poll()) for x in launched])


def runtime_environment(root, runtime):
    c.require(sys.version_info[:2] == (3,9), 'PYTHON_39_REQUIRED')
    versions = {name:importlib.metadata.version(name) for name in runtime['versions']}
    c.require(all(versions[k].split('+')[0] == v for k,v in runtime['versions'].items()), 'TARGET_VERSION:'+str(versions))
    tshark = shutil.which(runtime['tshark']); c.require(tshark is not None, 'TSHARK_MISSING')
    result = subprocess.run([tshark,'--version'], capture_output=True, text=True, check=True)
    c.require('4.6.6' in result.stdout.splitlines()[0], 'TSHARK_VERSION')
    c.require(int(os.environ.get('SLURM_CPUS_PER_TASK','0')) >= runtime['cpus'], 'CPU_ALLOCATION')
    c.require(shutil.disk_usage(root).free >= runtime['minimum_free_gib']*1024**3, 'DISK_RESERVE')
    c.pin(runtime['checkpoint'], runtime['checkpoint_sha256'])
    link = Path(root)/'vendor/netFound-base/model.safetensors'
    c.require(not link.exists() and not link.is_symlink(), 'CHECKPOINT_LINK_EXISTS')
    link.symlink_to(runtime['checkpoint'])
    return dict(versions=versions, tshark=result.stdout.splitlines()[0], checkpoint_sha256=runtime['checkpoint_sha256'])


def numeric_probe(root, run, runtime, design, progress):
    """One predeclared worst-shape synthetic timing and numerical check; real pinned E3."""
    from test_continuous_repair_v3 import state, packet
    embed, _, model, tokenizer, collator = f.e3_runtime(root)
    examples = []
    for peer in range(16):
        s = state()
        for burst in range(12):
            for pos in range(6):
                frame = burst*6+pos+1
                s.append(packet(frame, burst*20_000_000+pos*1_000_000, flags=2 if peer%2 else 16, seq=100+peer))
        flow, _, proof = s.snapshot(); encoded = f.tokenize(tokenizer,flow)
        f.verify_tokenized(flow,proof,encoded); examples.append(encoded)
    single, full, shifted = collator([examples[0]]), collator(examples), collator(examples[1:]+examples[:1])
    c.require(f.tensor_hash(single,0)==f.tensor_hash(full,0)==f.tensor_hash(shifted,15), 'PROBE_TENSOR_INVARIANCE')
    results=[];seconds=[]
    for batch in (single,full,shifted):
        progress.guard(); start=time.monotonic()
        results.append(embed.core.e3_forward_batches(model,[batch],'cpu')); seconds.append(time.monotonic()-start)
    tol=design['input']['runtime_numeric_probe']
    c.require(np.allclose(results[0][0],results[1][0],rtol=tol['rtol'],atol=tol['atol']) and
              np.allclose(results[0][0],results[2][15],rtol=tol['rtol'],atol=tol['atol']), 'PROBE_E3_INVARIANCE')
    batches=c.read(Path(run)/'spool/receipt.json')['batches']
    estimated = (batches/runtime['feature_workers']+1)*max(seconds[1:])*runtime['timing_safety_factor']
    elapsed=time.monotonic()-progress.started
    budget=dict(generated_rows=33,forward_calls=3,worst_shape=[6,73,12],seconds=seconds,
        batch_count=batches,estimated_feature_seconds=estimated,elapsed_seconds=elapsed,
        reserve_training_and_scoring_seconds=runtime['post_features_reserve_seconds'],
        tensor_exact=True,embedding_atol=tol['atol'],embedding_rtol=tol['rtol'], real_data_forwards=0)
    c.write(Path(run)/'target_probe.json',budget)
    c.require(elapsed+estimated+runtime['post_features_reserve_seconds'] < runtime['limits']['wall_seconds'], 'STOP_RESOURCE_BUDGET')
    del model


def run_chain(root, explicit):
    design, runtime=c.authorize(root,explicit)
    root=Path(root);run=root/'runs/real_repair'
    progress=c.Progress(run,runtime['limits']);(run/'logs').mkdir()
    def requested_stop(signum,frame): raise RuntimeError('SIGNAL_STOP:'+str(signum))
    signal.signal(signal.SIGTERM,requested_stop);signal.signal(signal.SIGINT,requested_stop)
    try:
        c.write(run/'launch.json',dict(design_sha256=c.DESIGN_SHA,scope='P_T_K_FIXED_DEVELOPMENT',retries=0,package_sha256=c.sha(root/'SHA256SUMS')))
        progress.stage='P_ENVIRONMENT';progress.tick()
        c.write(run/'environment.json',runtime_environment(root,runtime))
        progress.stage='P_INPUT_IDENTITIES';progress.tick()
        metadata,specs=d.load_inputs(root,runtime,design,run/'inputs')
        audit_api.preflight(root,run/'anomaly_preflight',metadata,specs,runtime,design,progress)
        d.old_tail_audit(metadata,c.read(run/'inputs/old_features.json'),run/'old_tail_audit.json')
        f.spool(root,run/'spool',metadata,specs,runtime,progress)
        c.write(run/'spool_pin.json',dict(sha256=c.sha(run/'spool/snapshots.sqlite')))
        progress.stage='P_TARGET_NUMERIC_RESOURCE_PROBE';progress.tick()
        numeric_probe(root,run,runtime,design,progress)
        progress.stage='P_FEATURE_WORKERS'
        launch(root,run,[(str(i),['feature-worker','--shard',str(i)],Path('features_worker_%02d/status.json'%i)) for i in range(runtime['feature_workers'])],runtime['feature_workers'],progress)
        progress.stage='P_MERGE';progress.tick();f.merge_features(run,metadata,runtime)
        prepare_normalizers(run,metadata,design,progress)
        c.write(run/'P_COMPLETE.json',dict(status='COMPLETE',rows=design['data']['new_feature_rows'],
            input_seal=c.sha(run/'inputs/SHA256SUMS'),feature_seal=c.sha(run/'features/SHA256SUMS'),normalizer_seal=c.sha(run/'normalizers/SHA256SUMS'),real_optimizer_updates=0))
        c.write(run/'launch_T.json',dict(P_sha256=c.sha(run/'P_COMPLETE.json')));(run/'endpoints').mkdir()
        progress.stage='T_FIXED_12_HEADS'
        tasks=[(arm+'_'+str(seed),['train-worker','--arm',arm,'--seed',str(seed)],Path('train_monitor_'+arm+'_'+str(seed))/'status.json') for arm in (*c.ARMS,'LEARNED') for seed in c.SEEDS]
        launch(root,run,tasks,runtime['train_workers'],progress)
        c.seal(run/'endpoints');c.verify(run/'endpoints')
        progress.optimizer_updates=sum(c.read(run/'endpoints'/name/'endpoint.json')['updates'] for name,_,_ in tasks)
        c.write(run/'T_COMPLETE.json',dict(status='COMPLETE',heads=12,updates=progress.optimizer_updates,endpoint_seal_sha256=c.sha(run/'endpoints/SHA256SUMS')))
        norms=norms_from(run)
        classifiers={arm:{seed:t.load_model(run/'endpoints'/(arm+'_'+str(seed)),arm,seed,design) for seed in c.SEEDS} for arm in c.ARMS}
        metrics={seed:t.load_model(run/'endpoints'/('LEARNED_'+str(seed)),'LEARNED',seed,design) for seed in c.SEEDS}
        bank=bank_from(run,metadata,'SOURCE_REFS','LEARN',norms['RECENT_STATE'])
        learn=matrices(run,metadata,'LEARN')
        with np.load(run/'inputs/CAL.npz',allow_pickle=False) as saved: ix=saved['indices'].copy()
        cal={k:([v[i] for i in ix] if k=='rows' else v[ix]) for k,v in learn.items()}
        progress.stage='K_SOURCE_CAL';progress.tick()
        tau,cuts=e.calibrate(design,classifiers,metrics,cal,norms,bank,run/'calibration',progress)
        del cal,learn
        outcomes={};controls=c.read(run/'inputs/controls.json')
        for pool,ref,partition in [('CIC_DEV','SOURCE_REFS',{'LEARN','DEV'}),('UNSW_DEV','UNSW_REFS','EXTERNAL_ARCHIVAL_EVALUATION')]:
            progress.stage='K_'+pool;progress.tick()
            bank=bank_from(run,metadata,ref,partition,norms['RECENT_STATE'])
            outcomes[pool]=e.evaluate(design,classifiers,metrics,matrices(run,metadata,pool),norms,bank,tau,cuts,controls[pool],pool,run/pool,progress)
        c.write(run/'decision.json',dict(execution='COMPLETE',core_capability_pass=all(x['core_capability_pass'] for x in outcomes.values()),
            adaptation_gain_pass=all(x['adaptation_gain_pass'] for x in outcomes.values()),pools=outcomes,independent_ID='NOT_RUN',retries=0))
        progress.stop('COMPLETE',scientific_gate=all(x['core_capability_pass'] for x in outcomes.values()))
    except BaseException as exc:
        progress.record_failure(exc,'main_chain');progress.stop('STOPPED_NO_RETRY',error=repr(exc));raise


def main():
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['run','feature-worker','train-worker'])
    parser.add_argument('--root',required=True);parser.add_argument('--run');parser.add_argument('--shard',type=int)
    parser.add_argument('--arm');parser.add_argument('--seed',type=int);parser.add_argument('--authorize-chain',action='store_true')
    args=parser.parse_args()
    c.require(args.authorize_chain,'REAL_CHAIN_NOT_AUTHORIZED')
    if args.mode=='run':run_chain(args.root,args.authorize_chain)
    elif args.mode=='feature-worker':f.feature_worker(args.root,args.run,args.shard,args.authorize_chain)
    else:train_worker(args.root,args.run,args.arm,args.seed,args.authorize_chain)


if __name__=='__main__':main()
