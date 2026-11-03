"""One authorized feature/scoring/report chain, no training or calibration."""
from pathlib import Path
import argparse,os,signal,subprocess,sys,time,json
import numpy as np
import legacy_qref_common_v1 as c
import legacy_qconfirm_common_v1 as d

def stop_group(process):
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:return
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait(timeout=5)

def tree_memory(pid):
    try:
        rss=int(Path('/proc/%s/statm'%pid).read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
        kids=Path('/proc/%s/task/%s/children'%(pid,pid)).read_text().split()
        return rss+sum(tree_memory(int(k)) for k in kids)
    except (FileNotFoundError,ProcessLookupError):return 0

def jobs(root,scope_path,out,taskpaths,scope,progress):
    pending=list(enumerate(taskpaths));active=[];finished=[];last=0
    try:
        while pending or active:
            progress.guard()
            c.require(tree_memory(os.getpid())<=128*2**30,'PROCESS_TREE_MEMORY')
            while pending and len(active)<scope['workers']:
                ix,task=pending.pop(0);log=(out/'tasks'/('%d.log'%ix)).open('xb')
                args=[sys.executable,'-B','-u',str(Path(__file__).resolve()),'worker','--root',str(root),'--authorization',str(scope_path),'--out',str(out),'--task',str(task)]
                try:p=subprocess.Popen(args,cwd=root,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
                except BaseException:log.close();raise
                active.append((ix,p,log))
            for item in list(active):
                ix,p,log=item
                if p.poll() is None:continue
                log.close();active.remove(item)
                c.write(out/'tasks'/('%d.exit.json'%ix),dict(exit_code=p.returncode,retries=0))
                if p.returncode:stop_group(p);raise c.Stop('FEATURE_WORKER_FAILED:'+str(ix))
                finished.append(ix)
            if time.monotonic()-last>=10:
                states=[dict(shard=i,pid=p.pid,progress=c.status(out/('shard_'+str(i)))) for i,p,_ in active]
                progress.emit(completed_shards=finished,shards_total=len(taskpaths),active=states);last=time.monotonic()
            time.sleep(1)
        return [out/('shard_'+str(i)) for i in range(len(taskpaths))]
    finally:
        for _,p,log in active:stop_group(p);log.close()

def worker(root,scope_path,out,taskpath):
    scope=c.read(scope_path);d.authorize(scope,root,out,True,worker=True);d.implementation_check(root)
    taskpath=c.confined(out/'plan',taskpath);c.verify(out/'plan')
    receipt=c.read(out/'scope_receipt.json');c.require(receipt==scope,'SCOPE_CHANGED')
    task=c.read(taskpath);c.require(taskpath.name==str(task['index'])+'.json','TASK_IDENTITY')
    from legacy_qconfirm_runtime_v1 import install
    from legacy_reference_executor_features_v1 import build_runtime
    from legacy_qconfirm_features_v1 import materialize
    effective=install(root,scope,out/'runtime');runtime=build_runtime(effective)
    progress=d.Progress(out/('shard_'+str(task['index'])));progress.heldout_opened=True
    catalog=c.read(out/'plan/catalog.json');devices=c.read(Path(root)/'runs/legacy_reference_sample_preparation_v1_20260917/devices.json')
    try:materialize(task,catalog,[x['mac'] for x in devices],runtime,progress.out,progress)
    except BaseException as exc:progress.finish('STOPPED_NO_RETRY',error=repr(exc));raise

def execute(root,scope_path,out,explicit):
    root=Path(root).resolve();out=Path(out).resolve();scope=c.read(scope_path)
    d.authorize(scope,root,out,explicit);plan=d.implementation_check(root)
    c.require(sys.platform=='linux','HPC_LINUX_ONLY')
    progress=d.Progress(out);c.write(out/'scope_receipt.json',scope)
    try:
        # Validate metadata/report dependencies and pinned models before touching the query manifest.
        for n,h in plan['immutable']['artifact_pins'].items():c.pin(c.confined(root,n),h)
        from legacy_qconfirm_runtime_v1 import install,prepare_catalog,inventory
        from legacy_qconfirm_features_v1 import partition,merge
        from legacy_qconfirm_evaluate_v1 import models,evaluate
        from legacy_reference_executor_features_v1 import build_runtime,feature_batch
        from legacy_qref_runner_v1 import runtime_probe
        effective=install(root,scope,out/'runtime',create=True)
        qrecipe=c.load_recipe(root)
        c.write(out/'input_inventory.json',inventory(root,scope,plan,qrecipe))
        progress.begin('TARGET_SYNTHETIC',1)
        c.write(out/'runtime_probe.json',runtime_probe(qrecipe))
        # The generated E3 fixture/golden is provided and identity-pinned by the implementation package.
        flows=c.read(root/d.IMPLEMENTATION/'encoder_fixture.json')
        runtime=build_runtime(effective);got=feature_batch(runtime,flows);del runtime
        golden=np.load(root/d.IMPLEMENTATION/'encoder_golden.npy',allow_pickle=False)
        c.require(got.shape==golden.shape and got.dtype==golden.dtype and np.allclose(got,golden,rtol=1e-4,atol=1e-5),'ENCODER_NUMERIC_COMPATIBILITY')
        c.write(out/'encoder_compatibility.json',dict(status='PASS',synthetic_packets_only=True,rtol=1e-4,atol=1e-5))
        progress.finish_stage('TARGET_SYNTHETIC')
        progress.heldout_opened=True;progress.begin('AUTHORIZED_QUERY_IDENTITY',1)
        allrefs=d.load_source(root,plan['data']['reference']);refs=[r for r in allrefs if r['partition']=='DEVICE_HOLDOUT']
        rows=d.load_source(root,plan['data']['query']);d.validate_metadata(plan,rows,refs)
        donorrows,donorfeatures=d.read_donors(root,scope['donor_cache'],plan,qrecipe);d.validate_controls(plan,refs+donorrows)
        progress.begin('RAW_INPUT_HASH_CHECK',1);catalog=prepare_catalog(root,scope,rows,refs,plan)
        chunks=partition(rows,refs,catalog,scope['workers']);(out/'plan').mkdir();(out/'tasks').mkdir()
        c.write(out/'plan/catalog.json',catalog);taskpaths=[]
        for i,chunk in enumerate(chunks):
            path=out/'plan'/(str(i)+'.json');c.write(path,dict(chunk,index=i));taskpaths.append(path)
        c.seal(out/'plan');progress.begin('E3_SHARDS',len(chunks))
        shards=jobs(root,scope_path,out,taskpaths,scope,progress)
        values=merge(shards,rows,refs,out/'cache',progress)
        progress.finish_stage('HOLDOUT_FEATURES')
        base,qs,ms=models(root,plan,qrecipe)
        inputs=dict(base=base,qs=qs,ms=ms,rows=rows,features=values[len(refs):],refs=refs,ref_features=values[:len(refs)],donors=donorrows,donor_features=donorfeatures)
        result=evaluate(plan,qrecipe,inputs,out/'evaluation',progress,
            annotations=c.rows(out/'cache/annotations.jsonl.gz'),
            exclusions=c.read(root/'runs/legacy_reference_sample_preparation_v1_20260917/finalized/excluded_capture_modes.json'))
        progress.finish_stage('FROZEN_EVALUATION');progress.finish_stage('REPORT')
        for n,h in plan['immutable']['artifact_pins'].items():c.pin(c.confined(root,n),h)
        progress.finish('COMPLETE',scientific_gate=result['gate'],synthetic_only=False)
        c.seal(out);c.verify(out)
    except BaseException as exc:
        progress.finish('STOPPED_NO_RETRY',error=repr(exc),synthetic_only=False);raise

def main():
    p=argparse.ArgumentParser();p.add_argument('command',choices=['run','worker','status','check-scope']);p.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);p.add_argument('--authorization',type=Path);p.add_argument('--out',required=True,type=Path);p.add_argument('--task',type=Path);p.add_argument('--execute',action='store_true');a=p.parse_args()
    if a.command=='status':print(json.dumps(c.status(a.out),indent=2));return
    c.require(a.authorization is not None,'AUTHORIZATION_FILE_REQUIRED')
    if a.command=='check-scope':d.authorize(c.read(a.authorization),a.root,a.out,a.execute);print('SCOPE_VALID_NO_DATA_OPENED')
    elif a.command=='run':execute(a.root,a.authorization,a.out,a.execute)
    else:worker(a.root,a.authorization,a.out,a.task)

if __name__=='__main__':main()
