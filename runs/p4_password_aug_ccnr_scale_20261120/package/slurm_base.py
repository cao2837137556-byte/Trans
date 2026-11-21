"""Submit the formal replay only after the separate compute-node pilot has passed."""
import fcntl
import getpass
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

from common_round1 import artifact, dump, load, require, sha, verify_artifact
from reports import HEADS, POOLS, headline

HERE = Path(__file__).resolve().parent
RUN = 'p4_dual_component_mean_v1_20261117'
NAMES = {'preflight':'p04-dual17-pre', 'formal':'p04-dual17-mean'}
FAIL = {'BOOT_FAIL','CANCELLED','DEADLINE','FAILED','NODE_FAIL','OUT_OF_MEMORY','PREEMPTED','TIMEOUT','REVOKED'}


def command(args):
    retries = 3 if args[0] in ('squeue','sacct') else 1
    for attempt in range(retries):
        try:
            p = subprocess.run(args, capture_output=True, text=True, timeout=55)
            if p.returncode == 0 or attempt+1 == retries:
                return dict(returncode=p.returncode, stdout=p.stdout, stderr=p.stderr)
        except subprocess.TimeoutExpired:
            if attempt+1 == retries:
                if args[0] == 'sbatch':
                    raise
                return dict(returncode=124,stdout='',stderr='scheduler read timeout')
        time.sleep(2)


def live(out, stage, **data):
    dump(out/'CHAIN_STATE.json',dict(stage=stage,updated_unix=time.time(),**data))


def submission(project, out, phase):
    name = NAMES[phase]
    user = getpass.getuser()
    queue = command(['squeue','-h','-u',user,'-o','%i|%j'])
    acct = command(['sacct','-X','-n','-P','-u',user,'-S','2026-11-17','-o','JobIDRaw,JobName%80'])
    require(queue['returncode'] == acct['returncode'] == 0, 'SCHEDULER_LOOKUP')
    matches = {x[0] for p in (queue,acct) for line in p['stdout'].splitlines()
               for x in [line.strip().split('|')] if len(x) > 1 and x[1] == name and x[0].isdigit()}
    intent = out/f'SUBMIT_INTENT_{phase}.json'
    receipt = out/f'JOB_{phase}.json'
    if receipt.is_file():
        job = load(receipt)['job_id']
        require(intent.is_file() and matches <= {job}, 'SCHEDULER_ID_CONFLICT')
        return job
    if intent.exists():
        require(len(matches) == 1, 'AMBIGUOUS_PRIOR_SUBMISSION:' + phase)
        job = matches.pop()
    else:
        require(not matches, 'EXISTING_UNBOUND_JOB:' + phase)
        wall = 2700 if phase == 'preflight' else 7200
        args = ['sbatch','--partition=amd','--no-requeue','--nodes=1','--ntasks=1','--cpus-per-task=4',
                '--time=' + ('00:45:00' if phase == 'preflight' else '02:00:00'),
                '--mem=12288M','--job-name='+name,'--chdir='+str(HERE),
                '--output='+str(out/(phase+'-%j.out')),'--error='+str(out/(phase+'-%j.err')),
                str(HERE/'run.slurm'),phase,str(project),str(out),str(wall)]
        test = command([args[0],'--test-only',*args[1:]])
        dump(out/f'TEST_ONLY_{phase}.json',test)
        require(test['returncode'] == 0, 'SBATCH_TEST_ONLY:' + test['stderr'])
        dump(intent,dict(argv=args, time=time.time()))
        r = command([args[0],'--parsable',*args[1:]])
        dump(out/f'SBATCH_{phase}.json',r)
        job = r['stdout'].strip().split(';')[0]
        require(r['returncode'] == 0 and job.isdigit(), 'SBATCH_RECEIPT:' + r['stderr'])
    dump(receipt,dict(job_id=job,name=name,phase=phase))
    return job


def wait_job(out, phase, job):
    live(out,'SUBMITTED',phase=phase,job_id=job)
    while True:
        q = command(['squeue','-h','-j',job,'-o','%i|%T|%R'])
        a = command(['sacct','-n','-P','-j',job,'-o','JobIDRaw,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem'])
        queue = [r.split('|') for r in q['stdout'].splitlines() if r.split('|')[0] == job]
        acct = [r.split('|') for r in a['stdout'].splitlines() if r.split('|')[0] == job]
        state = acct[-1][1].split()[0].rstrip('+') if acct else 'SUBMITTED'
        if queue and state != 'COMPLETED' and state not in FAIL:
            state = queue[0][1]
        dump(out/f'SCHEDULER_{phase}.json',dict(job_id=job,state=state,account=a,queue=q))
        if state == 'COMPLETED':
            require(acct[-1][2] == '0:0', 'SLURM_EXIT:' + phase)
            return
        if state in FAIL:
            error = out/f'FAILURE_{phase}.json'
            raise RuntimeError(f'{phase} {job} {state} ' + (load(error)['error'] if error.is_file() else ''))
        live(out,state,phase=phase,job_id=job,reason=queue[0][2] if queue else None)
        time.sleep(12)


def manifest(out):
    names = {'INSTALL.json','PREFLIGHT.json','SCIENCE.json','ACCEPTANCE.json','ARTIFACTS.json',
             'METRICS.csv','METRICS.json','PAIRED.json','PAIRED.csv','HEADLINE.csv','HEADLINE.json',
             'RESULTS_FOR_PAPER.md','CONTROLLER_FAILURE.json'}
    for phase in NAMES:
        for key in ('INPUTS','RUNTIME','RESOURCES','SUBMIT_INTENT','SBATCH','TEST_ONLY','JOB','SCHEDULER','FAILURE','SLURM_STOP'):
            names.add(f'{key}_{phase}.json')
    dump(out/'RETURN.json',dict(files={n:artifact(out/n) for n in sorted(names) if (out/n).is_file()}))


def main(project, out):
    require(out == project/'runs'/RUN and HERE == out/'package', 'DEPLOYMENT_SCOPE')
    with (out/'.dispatch.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/'ACCEPTANCE.json').is_file():
            return
        try:
            jobs = {}
            package = sha(HERE/'PACKAGE_MANIFEST.json')
            for phase in NAMES:
                live(out,'VALIDATE_SUBMISSION',phase=phase)
                jobs[phase] = submission(project,out,phase)
                wait_job(out,phase,jobs[phase])
                if phase == 'preflight':
                    p = load(out/'PREFLIGHT.json')
                    require(p['status'] == 'PASS' and p['job_id'] == jobs[phase] and
                            p['package_sha256'] == package and p['inputs_sha256'] == sha(out/'INPUTS_preflight.json')
                            and p['real_frontend']['actual_forwards'] > 0 and
                            set(p['pools']) == set(POOLS), 'REQUIRED_REAL_PREFLIGHT')
                    for v in p['pools'].values():
                        require(v['status'] == 'PASS' and v['direct_max_distance_error'] <= 2e-10
                                and v['paired_cells'] > 0, 'PREFLIGHT_ORACLE')
                        verify_artifact(out/'artifacts',v['values'])
            science = load(out/'SCIENCE.json')
            require(science['status'] == 'PASS' and science['job_id'] == jobs['formal'] and
                    science['preflight_job'] == jobs['preflight'] and science['package_sha256'] == package and
                    science['rows'] == 388202 and science['heads'] == list(HEADS), 'FORMAL_RECEIPT_IDENTITY')
            for pin in science['outputs'].values():
                verify_artifact(out,pin)
            require(headline(load(out/'METRICS.json'),load(out/'PAIRED.json')) == load(out/'HEADLINE.json'),
                    'FINAL_PAIRED_RECOUNT')
            dump(out/'ACCEPTANCE.json',dict(status='PASS',jobs=jobs,queries=science['rows'],heads=list(HEADS),
                 original_weak_metric_rows=sum(x['weak_metric_rows'] for x in science['baseline'].values()),
                 package_sha256=package,science=artifact(out/'SCIENCE.json'),scheduler={
                    k:artifact(out/f'SCHEDULER_{k}.json') for k in jobs},subset_violations=0))
            manifest(out)
            live(out,'COMPLETE',job_id=jobs['formal'],jobs=jobs)
        except Exception as error:
            dump(out/'CONTROLLER_FAILURE.json',dict(error=str(error),traceback=traceback.format_exc()))
            manifest(out)
            live(out,'STOP',error=str(error))
            raise


if __name__ == '__main__':
    main(*map(Path,sys.argv[1:]))
