import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
    assert not (HERE/'results').exists(),'NEW_OUTPUT_ONLY'
    import torch,numpy,psutil
    start=time.monotonic();p=subprocess.run([sys.executable,'-X','utf8','-B',str(HERE/'transfer.py')],cwd=HERE)
    u=resource.getrusage(resource.RUSAGE_CHILDREN);result=dict(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,wall_seconds=time.monotonic()-start,user_cpu_seconds=u.ru_utime,system_cpu_seconds=u.ru_stime,maxrss_kib=u.ru_maxrss,torch=torch.__version__,numpy=numpy.__version__,job_id=os.environ.get('SLURM_JOB_ID'))
    temp=HERE/'RESOURCE_USAGE.tmp';temp.write_text(json.dumps(result,indent=2));temp.replace(HERE/'RESOURCE_USAGE.json');return p.returncode
if __name__=='__main__':sys.exit(main())
