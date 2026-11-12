import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
if __name__=='__main__':
    task=sys.argv[1];assert task in ['controls','tabm'];assert not (HERE/'results'/task).exists()
    started=time.monotonic();p=subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'worker.py'),task],cwd=HERE);u=resource.getrusage(resource.RUSAGE_CHILDREN)
    r=dict(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,wall_seconds=time.monotonic()-started,user_cpu_seconds=u.ru_utime,system_cpu_seconds=u.ru_stime,maxrss_kib=u.ru_maxrss,job_id=os.environ.get('SLURM_JOB_ID'))
    tmp=HERE/(task+'_RESOURCE.tmp');tmp.write_text(json.dumps(r,indent=2));tmp.replace(HERE/(task+'_RESOURCE.json'));sys.exit(p.returncode)
