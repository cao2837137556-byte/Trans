"""Submit the real-data preflight and five transfer configurations in one Slurm job."""
import getpass
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from common_round1 import artifact,dump,load,require,sha

HERE=Path(__file__).resolve().parent
NAME='p04-head-transfer'
FAILED={'FAILED','OUT_OF_MEMORY','TIMEOUT','CANCELLED','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE'}


def command(argv):
    r=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=45)
    return dict(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr)


def live(out,stage,**extra):
    dump(out/'CHAIN_STATE.json',dict(stage=stage,phase='heads',updated_unix=time.time(),**extra))


def existing(out):
    user=getpass.getuser()
    commands=(['squeue','-h','-u',user,'-o','%i|%j|%T'],
              ['sacct','-X','-n','-P','-u',user,'-S','2026-11-13','-o','JobIDRaw,JobName%80,State,ExitCode'])
    snapshots=[command(c) for c in commands]
    require(all(r['returncode']==0 for r in snapshots),'SCHEDULER_DUPLICATE_CHECK')
    rows=[l for r in snapshots for l in r['stdout'].splitlines() if NAME in l.split('|')[1:2]]
    dump(out/'DUPLICATE_GATE.json',dict(status='PASS' if not rows else 'STOP',matching=rows))
    require(not rows,'EXISTING_HEAD_TRANSFER_JOB')


def submit(project,out):
    existing(out)
    run=['sbatch','--partition=amd','--no-requeue','--nodes=1','--ntasks=1','--cpus-per-task=4',
         '--job-name='+NAME,'--mem=12288M','--time=02:00:00','--chdir='+str(HERE),
         '--output='+str(out/'heads-%j.out'),'--error='+str(out/'heads-%j.err'),
         str(HERE/'run.slurm'),str(project),str(out)]
    check=command([run[0],'--test-only',*run[1:]])
    dump(out/'SBATCH_TEST_heads.json',check)
    require(check['returncode']==0,'SBATCH_TEST_ONLY:'+check['stderr'])
    with (out/'SUBMIT_INTENT_heads.json').open('x',encoding='utf-8') as f:
        import json
        json.dump(dict(args=run,timestamp=time.time()),f)
        f.flush()
        os.fsync(f.fileno())
    r=command([run[0],'--parsable',*run[1:]])
    dump(out/'SBATCH_heads.json',r)
    job=r['stdout'].strip().split(';',1)[0]
    require(r['returncode']==0 and job.isdigit(),'SBATCH_RECEIPT')
    live(out,'SUBMITTED',job_id=job)
    return job


def wait(out,job):
    expires=time.monotonic()+26*3600
    while time.monotonic()<expires:
        s=command(['squeue','-h','-j',job,'-o','%i|%T|%R'])
        a=command(['sacct','-n','-P','-j',job,
                   '-o','JobIDRaw,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem'])
        queue=[l.split('|') for l in s['stdout'].splitlines() if l.split('|')[0]==job]
        status=[l.split('|') for l in a['stdout'].splitlines() if l.split('|')[0]==job]
        row=status[-1] if status else None
        flag=row[1].split()[0].rstrip('+') if row else 'ACCOUNTING_PENDING'
        if queue and flag!='COMPLETED':
            flag=queue[0][1]
        dump(out/'SCHEDULER_heads.json',dict(job_id=job,state=flag,account=a,live=s))
        error=out/'FAILURE_heads.json'
        if error.is_file() or flag in FAILED:
            raise RuntimeError(f'{job} {flag} '+(load(error)['error'] if error.is_file() else ''))
        if flag=='COMPLETED':
            require(row[2]=='0:0','HEAD_JOB_EXIT_CODE')
            return
        live(out,flag if flag in ('RUNNING','PENDING') else 'SUBMITTED',job_id=job,
             reason=queue[0][2] if queue else None,worker_preflight='PASS' if (
             out/'PREFLIGHT.json').is_file() else None)
        time.sleep(12)
    raise TimeoutError('HEAD_JOB_POLL_DEADLINE')


def manifest(out):
    names={'INSTALL.json','ACCEPTANCE.json','PREFLIGHT.json','RESULT_INDEX.json','RESULTS_FOR_PAPER.md',
           'CALIBRATION.json','CHANGED_UID_INDEX.json','RESOURCES.json','FAILURE_heads.json',
           'CONTROLLER_FAILURE.json','DUPLICATE_GATE.json','SCHEDULER_heads.json','SBATCH_heads.json',
           'SBATCH_TEST_heads.json','METRICS.csv','METRICS.json','PAIRED.csv','PAIRED.json'}
    files={}
    for p in out.iterdir():
        if p.is_file() and (p.name in names or p.name.endswith('_CHANGED_UIDS.jsonl.gz')):
            files[p.name]={k:v for k,v in artifact(p).items() if k in ('bytes','sha256')}
    dump(out/'RETURN.json',dict(files=files))


def main():
    project,out=map(Path,sys.argv[1:])
    try:
        require(out.name=='p4_head_transfer_followup_v1_20261115','HEAD_OUTPUT_SCOPE')
        live(out,'CHECKPOINT_ADMISSION')
        job=submit(project,out)
        wait(out,job)
        receipt=load(out/'ACCEPTANCE.json')
        require(receipt['job_id']==job and receipt['status']=='PASS' and
                receipt['method_configurations']==5 and not receipt['retraining'] and
                all(receipt[k]['sha256']==sha(out/name) for k,name in (
                    ('preflight','PREFLIGHT.json'),('metrics','METRICS.json'),
                    ('paired','PAIRED.json'),('calibration','CALIBRATION.json'))),'HEAD_FINAL_ACCEPTANCE')
        (out/'RESULTS_FOR_PAPER.md').write_text(
            '# 检测头迁移补证\n\n五个配置已验收。'
            '\n\n[集成汇总](RESULT_INDEX.json) · [全部指标](METRICS.csv) · '
            '[配对结果](PAIRED.csv) · [源尺度](CALIBRATION.json) · [验收](ACCEPTANCE.json)\n',
            encoding='utf-8')
        live(out,'COMPLETE',job_id=job,outcome='ACCEPTED')
    except Exception as e:
        dump(out/'CONTROLLER_FAILURE.json',dict(error=str(e),traceback=traceback.format_exc()))
        live(out,'STOP',error=str(e))
        raise
    finally:
        manifest(out)


if __name__=='__main__':
    main()
