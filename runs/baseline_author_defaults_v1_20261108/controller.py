"""Measured preflight directly gates result-producing method jobs."""
import argparse,os,subprocess,sys,time
import psutil
from pipeline_parent import HERE,read,write,dependencies
METHODS=['DTE-C','SLAD','CatBoost']

def run(label,args,limit,memory=10240):
    t=time.monotonic();peak=0;reason=None
    with (HERE/(label+'.log')).open('wb') as log:
        p=subprocess.Popen([sys.executable,'-X','utf8','-B']+args,stdout=log,stderr=log)
        while p.poll() is None:
            try:peak=max(peak,sum(q.memory_info().rss for q in [psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True))/2**20)
            except psutil.NoSuchProcess:pass
            if time.monotonic()-t>limit:reason='MEASURED_WALL_GATE'
            if peak>memory:reason='MEASURED_MEMORY_GATE'
            if reason:
                p.terminate()
                try:p.wait(timeout=15)
                except subprocess.TimeoutExpired:p.kill();p.wait()
                break
            time.sleep(1)
    result=dict(status='PASS' if p.returncode==0 and not reason else 'STOP',returncode=p.returncode,reason=reason,seconds=time.monotonic()-t,peak_mib=peak)
    write(label+'_PROCESS.json',result)
    assert result['status']=='PASS',label+':'+str(result)
    return result

def submit(method,seconds):
    minutes=max(60,int((seconds+59)//60));assert minutes<=24*60,'METHOD_EXCEEDS_24H_ALLOCATION'
    project=str(HERE.parents[1]);script='#!/bin/bash\n#SBATCH --partition=amd\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=12288M\n#SBATCH --time='+str(minutes)+'\n#SBATCH --no-requeue\n#SBATCH --job-name=base-'+method+'\n#SBATCH --output='+str(HERE/(method+'-%j.out'))+'\n#SBATCH --error='+str(HERE/(method+'-%j.err'))+'\nset -euo pipefail\numask 077\nsource '+project+'/frontend_compat_v1/environment.sh\nexport OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1\nexport PYTHONPATH='+project+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+project+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexec '+sys.executable+' -X utf8 -B '+str(HERE/'controller.py')+' --method '+method+' --budget '+str(minutes*60)+'\n'
    path=HERE/(method+'.slurm');path.write_text(script)
    assert not (HERE/(method+'_JOB.json')).exists(),'ONE_SUBMISSION_PER_METHOD'
    r=subprocess.run(['sbatch','--parsable',str(path)],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
    job=r.stdout.strip().split(';')[0];assert job.isdigit();write(method+'_JOB.json',dict(job_id=job,cpu=1,memory_gib=12,wall_seconds=minutes*60))

def preflight():
    run('ENVIRONMENT',[str(HERE/'gate_worker.py'),'--phase','ENVIRONMENT'],240)
    run('FIDELITY',[str(HERE/'gate_worker.py'),'--phase','FIDELITY'],240)
    run('PIPELINE',[str(HERE/'gate_worker.py'),'--phase','PIPELINE'],600)
    # All evaluation identities fixed before formal training; no scores computed.
    run('INPUTS',[str(HERE/'formal.py'),'--action','inputs'],1200)
    decisions={}
    for method in METHODS:
        process=run('QUALIFY_'+method,[str(HERE/'formal.py'),'--action','qualify','--method',method],1800)
        r=read(HERE/('qualify_'+method+'_27_RESULT.json'))
        if method=='CatBoost':evaluation=1800
        else:
            n=sum(v['rows'] for v in read(HERE/'EVALUATION_INPUTS.json')['pools'].values())
            evaluation=r['score_1024_seconds']*n/1024*3*2+600
        budget=3*r['estimated_train_seconds']+evaluation+1200
        decisions[method]=dict(qualification=r,process=process,requested_seconds=budget)
        if budget>24*3600:
            decisions[method]['status']='NEEDS_RESOURCES';continue
        submit(method,budget);decisions[method]['status']='SUBMITTED'
        write('RELEASE.json',dict(status='PARTIAL_RELEASE',methods=decisions))
    write('PREFLIGHT_RESULT.json',dict(status='PASS',methods=decisions,main_model_changed=False))

def main():
    p=argparse.ArgumentParser();p.add_argument('--method');p.add_argument('--budget',type=int,default=7200);a=p.parse_args();dependencies();start=time.monotonic()
    label=a.method or 'PREFLIGHT'
    try:
        if a.method:
            # Each worker writes into its method-specific directory and progress file.
            os.environ['BASELINE_METHOD']=a.method
            for seed in [27,127,227]:
                run(a.method+'_'+str(seed),[str(HERE/'formal.py'),'--action','train','--method',a.method,'--seed',str(seed)],max(1,a.budget-300-(time.monotonic()-start)))
            run(a.method+'_EVALUATE',[str(HERE/'formal.py'),'--action','evaluate','--method',a.method],max(1,a.budget-120-(time.monotonic()-start)))
            write(a.method+'_COMPLETE.json',dict(status='PASS',seconds=time.monotonic()-start,main_model_changed=False))
        else:preflight()
        dependencies();return 0
    except Exception as e:
        write(label+'_STOP.json',dict(status='STOP',error=str(e),seconds=time.monotonic()-start));raise
if __name__=='__main__':sys.exit(main())
