"""One bounded resource allocation. Resource insufficiency is not model failure."""
import os,subprocess,sys,time
import psutil
from pipeline_parent import HERE,read,write,dependencies

def main():
    dependencies();spec=read(HERE/'SPEC.json');start=time.monotonic();results={};phases=spec['phases']
    for i,phase in enumerate(phases):
        t=time.monotonic();cap=min(spec['phase_caps_seconds'][phase],max(1,6600-(t-start)));peak=0.;reason=None
        write('DETAIL.json',dict(detail=phase,done=0,total=1))
        with (HERE/(phase+'.log')).open('wb') as log:
            p=subprocess.Popen([sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),'--phase',phase],stdout=log,stderr=log)
            while p.poll() is None:
                try:peak=max(peak,sum(x.memory_info().rss for x in [psutil.Process(p.pid)]+psutil.Process(p.pid).children(recursive=True))/2**20)
                except psutil.NoSuchProcess:pass
                detail=read(HERE/'DETAIL.json')
                write('PROGRESS.json',dict(version=spec['version'],stage='RUNNING',phase=phase,job_id=os.environ.get('SLURM_JOB_ID'),done=i,total=len(phases),detail=detail.get('detail',phase),inner_done=detail.get('done'),inner_total=detail.get('total'),results=results,rss_mib=peak,elapsed_seconds=time.monotonic()-start,updated_unix=time.time()))
                if time.monotonic()-t>cap:reason='STAGE_TIME_BUDGET'
                if peak>6656:reason='STAGE_MEMORY_BUDGET'
                if reason:
                    p.terminate()
                    try:p.wait(timeout=15)
                    except subprocess.TimeoutExpired:p.kill();p.wait()
                    break
                time.sleep(1)
        rf=HERE/(phase+'_RESULT.json')
        if p.returncode==0 and rf.exists():r=read(rf)
        else:
            sf=HERE/(phase+'_STOP.json');r=dict(status='NEEDS_RESOURCES' if reason else 'FAIL',error=reason or (read(sf)['error'] if sf.exists() else 'EXIT_'+str(p.returncode)))
        r.update(seconds=time.monotonic()-t,rss_peak_mib=peak);write(phase+'_RESULT.json',r);results[phase]=r
        # Only independent resource probes may continue after an explicit resource
        # limit. Implementation/data/fidelity failures always stop the chain.
        allowed=r['status']=='PASS' or (phase in spec['resource_phases'] and r['status']=='NEEDS_RESOURCES')
        if not allowed:
            write('RESULT.json',dict(status='INCOMPLETE',results=results,automatic_retries=0,seconds=time.monotonic()-start))
            write('PROGRESS.json',dict(version=spec['version'],stage='STOP',phase=phase,error=r.get('error',r.get('reason')),done=i,total=len(phases),results=results,job_id=os.environ.get('SLURM_JOB_ID'),updated_unix=time.time()));return 1
    dependencies();write('RESULT.json',dict(status='PASS_WITH_RESOURCE_GATES',results=results,seconds=time.monotonic()-start,formal_training_started=False))
    write('PROGRESS.json',dict(version=spec['version'],stage='COMPLETE',done=len(phases),total=len(phases),results=results,job_id=os.environ.get('SLURM_JOB_ID'),detail='资源报告与方案已封存；NEEDS_RESOURCES须单列，尚未启动正式训练',updated_unix=time.time()));return 0
if __name__=='__main__':sys.exit(main())
