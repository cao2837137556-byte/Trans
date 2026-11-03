"""Finite local supervisor. Real execution requires a separately authorized scope."""
from __future__ import annotations
import argparse,os,subprocess,sys,time,traceback
from pathlib import Path
import legacy_reference_executor_common_v1 as c
def directory_bytes(folder):return sum(p.stat().st_size for p in Path(folder).rglob('*') if p.is_file())
def stop_child(child,job):
    if job is not None:job.terminate()
    elif child.poll() is None:
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW,check=False)
    if child.poll() is None:child.wait(timeout=15)
def launch(request,request_path,python,chain,deadline,limits):
    from issue27frontend_inheritance_outer_control_v1 import Job
    request_path=Path(request_path);c.atomic_json(request_path,request)
    permit=request_path.with_suffix('.permit.json');log=request_path.with_suffix('.log')
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONHASHSEED='27',PYTHONIOENCODING='utf-8',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1')
    child=None;job=None;start=time.monotonic();peak=0;last_disk=-1.;disk=0;terminal={}
    try:
        with log.open('xb') as output:
            child=subprocess.Popen([str(python),'-B','-X','utf8',str(Path(__file__).resolve()),'worker','--request',str(request_path)],
                                   cwd=str(c.ROOT),env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
            job=Job(child,int(limits['ram_process_tree_limit_GiB']*2**30))
            c.atomic_json(permit,dict(request_sha256=c.sha(request_path),supervisor_pid=os.getpid()))
            while True:
                now=time.monotonic();peak=max(peak,job.peak())
                if now-last_disk>=5:disk=directory_bytes(chain);last_disk=now
                c.require(now<deadline,'WALL_TIME_LIMIT')
                c.require(disk<=limits['disk_new_output_limit_GiB']*2**30,'DISK_LIMIT')
                if (Path(chain)/'STOP_REQUESTED').exists():raise c.Stop('USER_STOP_REQUESTED')
                status_path=Path(request['out'])/'status.json'
                update=c.load(status_path) if status_path.exists() else {}
                c.emit(chain,request['operation'],update.get('done',0),update.get('total',0),status='RUNNING',worker=update,
                       supervisor_pid=os.getpid(),child_pid=child.pid,stage_elapsed_seconds=now-start,peak_job_bytes=peak,output_bytes=disk,retries=0)
                if child.poll() is not None:break
                time.sleep(.5)
            c.require(child.returncode==0,'WORKER_EXIT_'+str(child.returncode)+':'+str(log))
            disk=directory_bytes(chain);c.require(disk<=limits['disk_new_output_limit_GiB']*2**30,'DISK_LIMIT')
            terminal=dict(exit_code=child.returncode,peak_job_committed_bytes=peak,elapsed_seconds=time.monotonic()-start,output_bytes=disk)
            return terminal
    finally:
        if child is not None and child.poll() is None:stop_child(child,job)
        if job is not None:job.close()
        terminal.setdefault('exit_code',child.returncode if child else None);terminal.setdefault('peak_job_committed_bytes',peak)
        c.atomic_json(request_path.with_suffix('.supervisor.json'),dict(terminal,attempts=1,retries=0,child_pid=child.pid if child else None,finished_epoch=time.time()))
def run_chain(scope_path=None,authorized=False,fixture_path=None,out=None):
    synthetic=fixture_path is not None
    if synthetic:
        fixture=c.check_fixture(fixture_path);r=fixture['recipe'];out=c.confined(c.PACKAGE/'synthetic',out)
        scope=dict(synthetic_only=True,execution_authorized=False);c.require(not out.exists(),'OUTPUT_EXISTS_NO_RETRY')
    else:
        scope,out=c.authorize(scope_path,authorized);fixture=None;r=c.recipe()
    out=Path(out);out.mkdir(exist_ok=False);(out/'requests').mkdir()
    c.atomic_json(out/'execution_scope.json',scope);c.atomic_json(out/'recipe.json',r)
    start=time.monotonic();limits=dict(r['runtime']);deadline=start+limits['wall_time_chain_limit_hours']*3600
    worker_receipts={};stages=[]
    def run(operation,folder,**extra):
        request=dict(operation=operation,out=str(folder),chain=str(out),recipe_sha256=c.sha(out/'recipe.json'),fixture=str(fixture_path) if synthetic else None,**extra)
        path=out/'requests'/(operation+'.json')
        python=r['runtime']['encoder_python'] if operation.startswith('PREPARE') else r['runtime']['training_python']
        worker_receipts[operation]=launch(request,path,python,out,deadline,limits);stages.append(operation)
    try:
        if fixture and fixture.get('inject_failure')=='before_features':run('FAULT',out/'fault')
        run('PREPARE_LEARN_DEV',out/'features_LEARN_DEV')
        for seed in r['optimization']['seeds']:
            for arm in r['optimization']['arms']:run('TRAIN_'+arm+'_'+str(seed),out/('train_'+arm+'_'+str(seed)),arm=arm,seed=seed)
        run('EVALUATE_LEARN',out/'evaluation_LEARN',role='LEARN')
        run('EVALUATE_DEV',out/'evaluation_DEV',role='DEV')
        gate=c.load(out/'evaluation_DEV/gate.json')
        if synthetic and fixture.get('force_gate') is not None:
            gate=dict(gate,open=bool(fixture['force_gate']),synthetic_gate_override=True)
            c.atomic_json(out/'synthetic_gate.json',gate)
        if gate['open']:
            c.atomic_json(out/'holdout_open_claim.json',dict(gate=gate,opened_epoch=time.time(),once=True))
            run('PREPARE_HOLDOUT',out/'features_HOLDOUT')
            run('EVALUATE_HOLDOUT',out/'evaluation_DEVICE_HOLDOUT',role='DEVICE_HOLDOUT')
        if not synthetic:c.scope_metadata()
        result=dict(status='COMPLETE',synthetic_only=synthetic,stages=stages,gate=gate,heldout_opened=gate['open'],worker_receipts=worker_receipts,
                    recipe_digest=c.digest(r),elapsed_seconds=time.monotonic()-start,retries=0,scientific_claim='See fixed-threshold reports and limited development gate; engineering completion is not scientific success.')
        c.atomic_json(out/'result.json',result);c.emit(out,'COMPLETE',len(stages),len(stages),status='COMPLETE',heldout_opened=gate['open'],retries=0)
        c.seal(out);c.verify_seal(out);return result
    except BaseException as error:
        c.atomic_json(out/'failure.json',dict(status='STOPPED_NO_RETRY',reason=type(error).__name__+': '+str(error),completed_stages=stages,retries=0,synthetic_only=synthetic))
        c.emit(out,'STOPPED',len(stages),0,status='STOPPED_NO_RETRY',error=str(error),retries=0)
        if not (out/'SHA256SUMS').exists():c.seal(out)
        raise
def worker(request_path):
    request_path=Path(request_path);q=c.load(request_path);chain=Path(q['chain'])
    c.require(request_path.resolve().parent==(chain/'requests').resolve(),'WORKER_REQUEST_LOCATION')
    permit=request_path.with_suffix('.permit.json');started=time.monotonic()
    while not permit.exists():
        c.require(time.monotonic()-started<60,'SUPERVISOR_PERMIT_TIMEOUT');time.sleep(.1)
    c.require(c.load(permit)['request_sha256']==c.sha(request_path),'REQUEST_CHANGED')
    c.pin(chain/'recipe.json',q['recipe_sha256']);r=c.load(chain/'recipe.json')
    synthetic=q.get('fixture') is not None
    fixture=c.check_fixture(q['fixture']) if synthetic else None
    scope=c.load(chain/'execution_scope.json')
    c.require((synthetic and scope.get('synthetic_only') is True and r==fixture['recipe']) or
              (not synthetic and scope.get('execution_authorized') is True and r==c.recipe()),'WORKER_AUTHORITY')
    c.confined(chain,q['out'])
    if q['operation'].startswith('SYNTHETIC_'):
        c.require(synthetic,'TEST_OPERATION_REQUIRES_FIXTURE')
        folder=Path(q['out']);folder.mkdir(exist_ok=False)
        if q['operation']=='SYNTHETIC_CHILD':
            child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=subprocess.CREATE_NO_WINDOW)
            c.atomic_json(folder/'child.json',dict(pid=child.pid))
        elif q['operation']=='SYNTHETIC_DISK':
            (folder/'payload.bin').write_bytes(bytes(1024*1024))
        elif q['operation']=='SYNTHETIC_MEMORY':
            allocation=bytearray(256*1024*1024)
        else:raise c.Stop('UNKNOWN_SYNTHETIC_OPERATION')
        time.sleep(30);return
    if q['operation']=='FAULT':
        c.require(synthetic,'FAULT_SYNTHETIC_ONLY');raise c.Stop('INJECTED_SYNTHETIC_FAILURE')
    gate=None
    if 'HOLDOUT' in q['operation']:
        from legacy_reference_executor_evaluate_v1 import check_endpoints
        check_endpoints(chain,r);c.verify_seal(chain/'evaluation_DEV')
        gate=c.load(chain/'synthetic_gate.json') if synthetic and (chain/'synthetic_gate.json').exists() else c.load(chain/'evaluation_DEV/gate.json')
        from legacy_reference_executor_features_v1 import require_holdout
        require_holdout(gate,c.digest(r))
        c.require((chain/'holdout_open_claim.json').exists(),'HOLDOUT_NOT_CLAIMED')
    from legacy_reference_executor_features_v1 import prepare,load_cache,load_state
    if q['operation'].startswith('PREPARE'):
        prepare(r,q['out'],'HOLDOUT' if 'HOLDOUT' in q['operation'] else 'LEARN_DEV',gate,fixture);return
    state=load_state(r,fixture)
    folder=chain/('features_HOLDOUT' if q.get('role')=='DEVICE_HOLDOUT' else 'features_LEARN_DEV')
    role=q.get('role','LEARN');features,metadata=load_cache(folder,role,c.digest(r));ref_features,ref_rows=load_cache(folder,'REFERENCE',c.digest(r))
    if q['operation'].startswith('TRAIN'):
        from legacy_reference_executor_train_v1 import train_endpoint
        ix=[i for i,row in enumerate(ref_rows) if row['partition']=='LEARN']
        import numpy as np
        train_endpoint(r,state,features,metadata,np.array(ref_features[ix],dtype=np.float32),[ref_rows[i] for i in ix],q['arm'],q['seed'],q['out'],synthetic)
    else:
        from legacy_reference_executor_evaluate_v1 import evaluate
        evaluate(r,state,features,metadata,ref_features,ref_rows,chain,q['out'],role)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['validate','run','worker'])
    parser.add_argument('--scope');parser.add_argument('--authorize-chain',action='store_true');parser.add_argument('--request')
    a=parser.parse_args()
    if a.command=='validate':c.authorize(a.scope,a.authorize_chain);print('AUTHORIZED_SCOPE_VALID')
    elif a.command=='run':run_chain(a.scope,a.authorize_chain)
    else:
        q=c.load(a.request);audit={'synthetic_only':bool(q.get('fixture')),'real_checkpoint_reads':0,'real_raw_reads':0,'blocked_asset_attempts':0}
        opened=set()
        if q.get('fixture'):
            def guard(event,args):
                if event!='open' or not args or not isinstance(args[0],(str,bytes,os.PathLike)):return
                path=Path(os.fsdecode(args[0])).resolve()
                if path.suffix.lower() in ('.safetensors','.pcap','.pcapng','.npz','.npy'):
                    if not path.is_relative_to((c.PACKAGE/'synthetic').resolve()):
                        audit['blocked_asset_attempts']+=1
                        raise c.Stop('SYNTHETIC_REAL_ASSET_FORBIDDEN:'+str(path))
                    opened.add(str(path))
            sys.addaudithook(guard)
        try:worker(a.request)
        finally:
            audit['fixture_numpy_assets_opened']=len(opened)
            c.atomic_json(Path(a.request).with_suffix('.access.json'),audit)
if __name__=='__main__':main()

