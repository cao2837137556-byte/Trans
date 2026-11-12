"""Portable Linux accounting: no optional /usr/bin/time executable required."""
import json,os,resource,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;SCIENCE=HERE.parent/'paper_reading_ablations_v2_20261111'
def main():
    assert not (SCIENCE/'results').exists(),'NEW_SCIENCE_OUTPUT_ONLY'
    # Qualify interpreter modules in the actual compute-node environment first.
    import numpy,psutil
    start=time.monotonic()
    p=subprocess.run([sys.executable,'-X','utf8','-B',str(SCIENCE/'run.py')],cwd=SCIENCE)
    usage=resource.getrusage(resource.RUSAGE_CHILDREN)
    r=dict(status='PASS' if p.returncode==0 else 'FAIL',returncode=p.returncode,wall_seconds=time.monotonic()-start,user_cpu_seconds=usage.ru_utime,system_cpu_seconds=usage.ru_stime,maxrss_kib=usage.ru_maxrss,measurement='Linux resource.getrusage(RUSAGE_CHILDREN); Slurm sacct independently',job_id=os.environ.get('SLURM_JOB_ID'),numpy_version=numpy.__version__)
    tmp=SCIENCE/'RESOURCE_USAGE.tmp';tmp.write_text(json.dumps(r,indent=2));tmp.replace(SCIENCE/'RESOURCE_USAGE.txt')
    return p.returncode
if __name__=='__main__':sys.exit(main())
