"""Independent per-method resource gate, then real training/CAL/evaluation."""
import os,subprocess,sys,time,traceback
from pathlib import Path
import worker as w
p=w.p;HERE=w.HERE;CFG=w.CFG
assert Path(w.__file__).resolve()==Path(__file__).resolve().with_name('worker.py'),'LOCAL_WORKER_IDENTITY'
assert HERE.resolve()==Path(__file__).resolve().parent,'LOCAL_RUN_IDENTITY'

def environment():
    project=str(HERE.parents[1])
    return 'source '+project+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+project+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+project+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1 CUBLAS_WORKSPACE_CONFIG=:4096:8\n'

def submit(method):
    path=HERE/(method+'_JOB.json')
    if path.exists():return p.read(path)
    script='#!/bin/bash\n#SBATCH --partition=gpu\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=8\n#SBATCH --mem=32768M\n#SBATCH --gres=gpu:nvidia_geforce_rtx_4090:1\n#SBATCH --time=7-00:00:00\n#SBATCH --no-requeue\n#SBATCH --job-name=base-'+method+'\n#SBATCH --output='+str(HERE/(method+'-%j.out'))+'\n#SBATCH --error='+str(HERE/(method+'-%j.err'))+'\nset -euo pipefail\numask 077\n'+environment()+'exec '+sys.executable+' -X utf8 -B '+str(HERE/'controller.py')+' '+method+'\n'
    slurm=HERE/(method+'.slurm');slurm.write_text(script)
    r=subprocess.run(['sbatch','--parsable',str(slurm)],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
    job=r.stdout.strip().split(';')[0];assert job.isdigit();result=dict(job_id=job,cpu=8,memory_gib=32,gpu='one RTX4090',wall_seconds=CFG['method_wall_seconds'],scope='resource qualification THEN conditional three-seed formal training and evaluation')
    p.write(method+'_JOB.json',result);return result

def run(action,method,budget):
    import psutil
    t=time.monotonic();peak=0;reason=None
    with (HERE/(method+'_'+action+'.log')).open('ab') as out:
        child=subprocess.Popen([sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),action,method],stdout=out,stderr=out,start_new_session=True)
        while child.poll() is None:
            try:peak=max(peak,sum(q.memory_info().rss for q in [psutil.Process(child.pid)]+psutil.Process(child.pid).children(recursive=True))/2**30)
            except psutil.NoSuchProcess:pass
            if time.monotonic()-t>budget:reason='WALL_BUDGET_GATE'
            if peak>29:reason='HOST_MEMORY_HEADROOM_GATE'
            if reason:
                import signal
                os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=30);break
            time.sleep(2)
    result=dict(status='PASS' if child.returncode==0 and reason is None else 'STOP',returncode=child.returncode,reason=reason,seconds=time.monotonic()-t,peak_host_gib=peak)
    p.write(method+'_'+action+'_PROCESS.json',result);assert result['status']=='PASS',str(result)

def main(method):
    w.init();os.environ['BASELINE_METHOD']=method;t=time.monotonic()
    try:
        p.progress(method+'_RESOURCE_GATE');run('qualify',method,6*3600)
        p.write(method+'_RELEASE.json',dict(status='PASS',stage='FORMAL_RELEASED',qualification_sha256=p.sha(HERE/(method+'_QUALIFY.json')),source_only=True))
        for seed in [27,127,227]:run('train-'+str(seed),method,max(1,CFG['method_wall_seconds']-(time.monotonic()-t)-3600))
        run('evaluate',method,max(1,CFG['method_wall_seconds']-(time.monotonic()-t)-300))
        p.write(method+'_COMPLETE.json',dict(status='PASS',seconds=time.monotonic()-t,main_model_changed=False))
    except Exception as e:p.write(method+'_STOP.json',dict(status='STOP',error=str(e),traceback=traceback.format_exc()));raise

if __name__=='__main__':main(sys.argv[1])
