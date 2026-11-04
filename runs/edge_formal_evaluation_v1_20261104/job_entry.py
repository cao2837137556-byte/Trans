"""Bound launch within the single Slurm allocation; no retries or scoring."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
CHECKOUT=HERE.parents[1]
DEPLOY=CHECKOUT.parent
CODE=CHECKOUT/'runs/edge_formal_execution_v4_20261104'
sys.path.insert(1,str(CODE))
from checkpoint import atomic_json,require,sha


def main():
    preflight = sys.argv[1:] == ['--preflight']
    require(preflight or not sys.argv[1:], 'LAUNCH_ARGUMENTS')
    job=os.environ['SLURM_JOB_ID'];require(job.isdigit(),'SLURM_JOB_ID')
    output=DEPLOY/'outputs'/(('preflight_' if preflight else 'gate_')+job);output.mkdir(parents=True,exist_ok=False)
    started=time.monotonic()
    try:
        require(os.environ.get('SLURM_CPUS_PER_TASK')=='1','SLURM_ONE_CPU')
        require(int(os.environ['SLURM_MEM_PER_NODE'])==8192,'SLURM_8_GIB')
        allowed=os.sched_getaffinity(0);os.sched_setaffinity(0,{min(allowed)})
        scratch=Path('/tmp').resolve()
        fs=subprocess.run(['findmnt','-n','-o','FSTYPE','--target',str(scratch)],capture_output=True,text=True,check=True,timeout=5).stdout.strip()
        require(fs in ('xfs','ext4','ext3','btrfs') and scratch.stat().st_dev!=output.stat().st_dev,'REAL_NODE_LOCAL_SCRATCH')
        require(shutil.disk_usage(scratch).free>=32*1024**3,'NODE_SCRATCH_FREE_32_GIB')
        runtime=dict(tshark='/share/software/tshark-4.6.6/bin/tshark',scratch_root=str(scratch),
                     raw_paths=json.loads((DEPLOY/'RAW_PATHS.json').read_text()))
        runtime_path=output/'RUNTIME.json';atomic_json(runtime_path,runtime)
        atomic_json(output/'LAUNCH.json',dict(job_id=job,cpu=1,memory_gib=8,wall_seconds=1800 if preflight else 86400,phase='preflight' if preflight else 'gate',
            affinity=sorted(os.sched_getaffinity(0)),scratch_filesystem=fs,
            scratch_free_bytes=shutil.disk_usage(scratch).free,card_sha256=sha(HERE/'ENGINEERING_CARD.json')))
        if preflight:
            from real_slice_preflight import run
        else:
            from preflight_acceptance import validate_saved
            validate_saved(DEPLOY, HERE/'ENGINEERING_CARD.json')
            from formal_job import run
        run(HERE/'ENGINEERING_CARD.json',HERE/'AUTHORIZATION.json',runtime_path,output)
    except BaseException as exc:
        atomic_json(output/'LAUNCH_STOP.json',dict(status='STOP',reason=type(exc).__name__+':'+str(exc),
            elapsed_seconds=time.monotonic()-started,automatic_resubmit=False))
        raise


if __name__=='__main__':main()
