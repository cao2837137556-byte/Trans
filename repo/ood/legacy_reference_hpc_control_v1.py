"""Linux Slurm DEV-only supervisor, eight bounded workers, no retries."""
from __future__ import annotations
import argparse,os,signal,subprocess,sys,time,traceback
from pathlib import Path
import legacy_reference_executor_common_v1 as c
import legacy_reference_hpc_runtime_v1 as rt
ROOT=rt.ROOT
WORKERS=8

def directory_bytes(folder):
    total=0
    for path in folder.rglob('*'):
        try:
            if path.is_file():total+=path.stat().st_size
        except FileNotFoundError:
            # Atomic publication may remove a listed .tmp before stat.
            continue
    return total

def group_stop(process):
    if process.poll() is None:
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            try:os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:pass
            process.wait(timeout=10)

def jobs(tasks,run,deadline):
    pending=list(tasks);active=[];done=[];last_output=-100.;last_disk=-100.
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='27',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',OPENBLAS_NUM_THREADS='4',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false')
    try:
        while pending or active:
            c.require(time.monotonic()<deadline,'CHAIN_WALL_TIME_LIMIT')
            c.require(not (run/'STOP_REQUESTED').exists(),'USER_STOP_REQUESTED')
            if time.monotonic()-last_disk>30:
                size=directory_bytes(run)
                c.require(size<=64*2**30,'OUTPUT_DISK_LIMIT');last_disk=time.monotonic()
            while pending and len(active)<WORKERS:
                task=pending.pop(0);path=run/'requests'/(task['name']+'.json')
                c.atomic_json(path,task)
                log=path.with_suffix('.log').open('xb')
                process=subprocess.Popen([sys.executable,'-B','-u',str(Path(__file__).resolve()),'worker','--run',str(run),'--request',str(path)],cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                active.append((task,process,log,time.time()))
            for item in list(active):
                task,process,log,started=item
                if process.poll() is None:continue
                log.close();active.remove(item)
                c.atomic_json(run/'requests'/(task['name']+'.exit.json'),dict(exit_code=process.returncode,started_epoch=started,finished_epoch=time.time(),attempts=1,retries=0))
                c.require(process.returncode==0,'WORKER_FAILED:'+task['name'])
                done.append(task['name'])
            now=time.monotonic()
            if now-last_output>10:
                progress=[]
                for task,process,_,_ in active:
                    path=Path(task['out'])/'status.json'
                    update=c.load(path) if path.is_file() else {}
                    progress.append(dict(task=task['name'],pid=process.pid,progress=update))
                state=dict(status='RUNNING',completed_tasks=done,pending_tasks=len(pending),active=progress,output_bytes=size,retries=0,updated_epoch=time.time())
                c.atomic_json(run/'status.json',state)
                print('HPC_PROGRESS '+__import__('json').dumps(state,separators=(',',':')),flush=True);last_output=now
            time.sleep(1)
        return done
    finally:
        for _,process,log,_ in active:group_stop(process);log.close()

def worker(run,request):
    run=c.confined(ROOT,run);request=c.confined(run/'requests',request)
    q=c.load(request);r=rt.install(run);out=c.confined(run,q['out'])
    op=q['operation'];c.require(op in ('FEATURES','TRAIN','EVALUATE'),'NO_HOLDOUT_OPERATION')
    import legacy_reference_executor_features_v1 as f
    if op=='FEATURES':
        c.verify_seal(run/'plan');plan=c.load(run/'plan/plan.json');ix=q['shard']
        c.require(0<=ix<plan['workers'],'SHARD_SCOPE')
        sr=c.load(plan['shard_recipes'][ix])
        f.prepare(sr,out,'LEARN_DEV');return
    state=f.load_state(r);role='LEARN' if op=='TRAIN' else q['role']
    c.require(role in ('LEARN','DEV'),'NO_HOLDOUT_ROLE')
    values,rows=f.load_cache(run/'features_LEARN_DEV',role,c.digest(r))
    reference,ref_rows=f.load_cache(run/'features_LEARN_DEV','REFERENCE',c.digest(r))
    if op=='TRAIN':
        import numpy as np
        from legacy_reference_executor_train_v1 import train_endpoint
        ix=[i for i,x in enumerate(ref_rows) if x['partition']=='LEARN']
        train_endpoint(r,state,values,rows,np.array(reference[ix],dtype=np.float32),[ref_rows[i] for i in ix],q['arm'],q['seed'],out)
    else:
        from legacy_reference_executor_evaluate_v1 import evaluate
        evaluate(r,state,values,rows,reference,ref_rows,run,out,role)

def preflight(folder):
    import legacy_reference_hpc_compat_v1 as compat
    folder=c.confined(ROOT,folder);c.require(not folder.exists(),'PREFLIGHT_ALREADY_ATTEMPTED');folder.mkdir()
    try:
        r=rt.install(folder,create=True)
        inputs=rt.input_check()
        compat.compute(r,ROOT/'compatibility/inputs',folder/'numeric')
        result=compat.compare(ROOT/'compatibility/windows_golden',folder/'numeric')
        result.update(bundle_sha256=c.sha(ROOT/'SHA256SUMS'),checked_inputs=inputs,environment=rt.environment(),real_traffic_rows=0)
        c.atomic_json(folder/'PASS.json',result);c.seal(folder);print('HPC_PREFLIGHT_PASS',flush=True)
    except BaseException as error:
        c.atomic_json(folder/'FAILURE.json',dict(status='STOPPED_NO_RETRY',reason=repr(error),retries=0));raise

def run_chain(run,preflight_dir):
    c.require(sys.platform=='linux' and os.environ.get('SLURM_JOB_ID'),'SLURM_COMPUTE_NODE_REQUIRED')
    c.require(os.environ.get('SLURM_JOB_PARTITION')=='amd','PARTITION_CONTRACT')
    c.require(int(os.environ.get('SLURM_CPUS_PER_TASK','0'))>=32,'CPU_ALLOCATION')
    c.require(int(os.environ.get('SLURM_MEM_PER_NODE','0'))>=128*1024,'MEMORY_ALLOCATION')
    run=c.confined(ROOT,run);c.require(not run.exists(),'OUTPUT_EXISTS_NO_RETRY')
    preflight_dir=c.confined(ROOT,preflight_dir);c.verify_seal(preflight_dir)
    check=c.load(preflight_dir/'PASS.json');c.require(check['status']=='PASS' and check['bundle_sha256']==c.sha(ROOT/'SHA256SUMS'),'PREFLIGHT_IDENTITY')
    run.mkdir();(run/'requests').mkdir();deadline=time.monotonic()+71.5*3600;stages=[]
    try:
        r=rt.install(run,create=True)
        from legacy_reference_hpc_parallel_v1 import plan,merge
        partition=plan(r,run/'plan',WORKERS)
        expected=c.load(ROOT/'frozen/parallel_partition.json')
        c.require(c.digest(partition['capture_assignment'])==expected['capture_assignment_sha256'] and partition['loads']==expected['loads'],'FROZEN_PARTITION_DRIFT')
        feature_tasks=[dict(name='FEATURES_'+str(i),operation='FEATURES',shard=i,out=str(run/('features_shard_'+str(i)))) for i in range(WORKERS)]
        stages+=jobs(feature_tasks,run,deadline)
        merge(r,run/'plan',[x['out'] for x in feature_tasks],run/'features_LEARN_DEV');stages.append('MERGE')
        train_tasks=[dict(name='TRAIN_'+arm+'_'+str(seed),operation='TRAIN',arm=arm,seed=seed,out=str(run/('train_'+arm+'_'+str(seed)))) for seed in r['optimization']['seeds'] for arm in r['optimization']['arms']]
        stages+=jobs(train_tasks,run,deadline)
        from legacy_reference_executor_evaluate_v1 import check_endpoints
        check_endpoints(run,r)
        stages+=jobs([dict(name='EVALUATE_'+role,operation='EVALUATE',role=role,out=str(run/('evaluation_'+role))) for role in ('LEARN','DEV')],run,deadline)
        gate=c.load(run/'evaluation_DEV/gate.json')
        result=dict(status='COMPLETE_DEV_ONLY',stages=stages,gate=gate,heldout_opened=False,holdout_owner='RESERVED_LOCAL_NO_AUTOMATIC_TRANSFER',retries=0,scientific_recipe_sha256=c.RECIPE_SHA,effective_recipe_digest=c.digest(r),slurm_job_id=os.environ['SLURM_JOB_ID'])
        c.atomic_json(run/'result.json',result);c.atomic_json(run/'status.json',result);c.seal(run)
        print('HPC_DEV_COMPLETE; HOLDOUT_NOT_OPENED',flush=True)
    except BaseException as error:
        result=dict(status='STOPPED_NO_RETRY',error=repr(error),completed_stages=stages,retries=0,heldout_opened=False)
        c.atomic_json(run/'failure.json',result);c.atomic_json(run/'status.json',result)
        if not (run/'SHA256SUMS').exists():c.seal(run)
        raise

def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['preflight','run','worker']);parser.add_argument('--run',required=True);parser.add_argument('--request');parser.add_argument('--preflight')
    a=parser.parse_args()
    if a.command=='preflight':preflight(Path(a.run))
    elif a.command=='worker':worker(Path(a.run),Path(a.request))
    else:run_chain(Path(a.run),Path(a.preflight))
if __name__=='__main__':main()
