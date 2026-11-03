"""Separate explicit gates for feature preparation and one paired experiment."""
import argparse
import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path
import issue27frontend_paired_train_support_v2 as s
from issue27frontend_paired_metadata_monitor_fix_v2 import directory_bytes
from issue27frontend_inheritance_outer_control_v1 import Job as OldJob, pid_alive
from issue27frontend_inheritance_n1_support_v1 import peak_memory

class Job(OldJob):
    def __init__(self, process, limit):
        super().__init__(process, limit)
        try:
            info=self.Extended()
            s.require(self.kernel.QueryInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info),None),'JOB_QUERY')
            info.BasicLimitInformation.ActiveProcessLimit=1
            s.require(self.kernel.SetInformationJobObject(self.handle,9,ctypes.byref(info),ctypes.sizeof(info)),'SINGLE_WORKER_LIMIT')
        except Exception:
            self.close(); raise


def readiness(stage):
    package=s.ROOT/s.PACKAGE
    s.verify_manifest(package)
    config=s.read_json(package/'execution_config.json')
    acceptance=s.read_json(package/'synthetic_acceptance.json')
    s.require(acceptance['status']=='PAIRED_TRAIN_IMPLEMENTATION_ACCEPTANCE_PASS' and
              acceptance['tests_passed']==acceptance['tests_run']>=30 and
              acceptance['real_feature_bytes_decoded']==acceptance['real_optimizer_steps']==0 and
              acceptance['config_sha256']==s.sha_file(package/'execution_config.json'),'IMPLEMENTATION_ACCEPTANCE')
    for rel,h in config['code_and_document_pins'].items():s.require(s.sha_file(s.ROOT/rel)==h,'CODE_DOCUMENT_IDENTITY')
    for rel,h in config['metadata_pins'].items():s.require(s.sha_file(s.ROOT/rel)==h,'METADATA_IDENTITY')
    for path,h in config['runtime_pins'].items():s.require(s.sha_file(Path(path))==h,'RUNTIME_IDENTITY')
    s.require(Path(sys.executable).resolve()==Path(config['python_path']).resolve(),'PYTHON_IDENTITY')
    s.require(config['training_caps']==s.CAPS and config['preparation_caps']==s.PREP_CAPS,'RESOURCE_DRIFT')
    s.verify_manifest(s.ROOT/s.MEMBERSHIP,s.MEMBERSHIP_SHA)
    s.require(s.sha_file(package/'plan.json')==config['plan_sha256'],'PLAN_IDENTITY')
    if stage=='train':
        prep=s.ROOT/s.PREP
        s.verify_manifest(prep)
        s.require(s.read_json(prep/'supervisor_terminal.json')['verdict']['status']=='PAIRED_FEATURES_PREPARED','PREP_NOT_COMPLETE')
        receipt=s.read_json(prep/'preparation_receipt.json')
        s.require(receipt['plan_sha256']==config['plan_sha256'] and
                  receipt['features_sha256']==s.sha_file(prep/'features.f32le'),'PREP_PIN')
    return dict(config,caps=config['preparation_caps'] if stage=='prepare' else config['training_caps'],stage=stage)


def validate_worker(receipt,folder,config,synthetic=False):
    if receipt['status']=='INPUT_OR_EXECUTION_STOP':
        return {'status':'INPUT_OR_EXECUTION_STOP','reason':receipt['reason'],'scientific_capability':'NOT_TESTED'}
    s.require(not synthetic and receipt['status']=='WORK_COMPLETE','WORKER_STATUS')
    s.require(receipt['plan_sha256']==config['plan_sha256'] and receipt['stage']==config['stage'],'WORKER_IDENTITY')
    plan=s.read_json(s.ROOT/s.PACKAGE/'plan.json')
    required={'access_receipt.json','features.f32le','preparation_receipt.json'} if config['stage']=='prepare' else {
        'access_receipt.json','initial.pt','initial.receipt.json','candidate_A.pt','candidate_A.receipt.json',
        'candidate_AB.pt','candidate_AB.receipt.json','candidates_sealed.json','training_log.jsonl',
        'postfit_predictions.json','check_predictions.json','comparison.json'}
    s.require(set(receipt['output_hashes'])==required,'OUTPUT_SET')
    for name,h in receipt['output_hashes'].items():s.require(s.sha_file(folder/name)==h,'OUTPUT_IDENTITY')
    access=s.read_json(folder/'access_receipt.json')
    s.require(access['retries']==access['raw_packets']==0,'FORBIDDEN_ACTION')
    if config['stage']=='prepare':
        r=s.read_json(folder/'preparation_receipt.json')
        s.require(r['access']==access and access['feature_files']==2 and access['prefixes_verified']==18266 and
                  access['feature_decoded_bytes']==plan['feature_bytes'] and
                  access['feature_hash_bytes']==sum(x['bytes'] for x in config['feature_sources'].values()) and
                  access['model_forwards']==access['optimizer_steps']==0,'PREP_ACTION_COUNTS')
        s.require(r['plan_sha256']==config['plan_sha256'] and r['features_sha256']==s.sha_file(folder/'features.f32le') and
                  r['feature_bytes']==(folder/'features.f32le').stat().st_size==plan['feature_bytes'],'PREP_BYTES')
        return {'status':'PAIRED_FEATURES_PREPARED','training_started':False}
    s.require(receipt['counts']==plan['accounting']['total'] and access['optimizer_steps']==15760 and
              access['check_passes_per_arm']==access['postfit_passes_per_arm']==1 and
              access['historical_checkpoint_loads']==access['teacher_forwards']==0,'TRAIN_ACTION_COUNTS')
    initial=s.read_json(s.ROOT/s.PACKAGE/'initial.receipt.json')['state_sha256']
    barrier=s.read_json(folder/'candidates_sealed.json')
    s.require(barrier['initial_state_sha256']==initial and barrier['updates']=={'A':7880,'AB':7880},'CANDIDATE_BARRIER')
    s.require(barrier['A_order_hashes']==[e['A_order_sha256'] for e in plan['accounting']['epoch_order_hashes']],'A_ORDER')
    import json
    log=[json.loads(line) for line in (folder/'training_log.jsonl').read_text().splitlines()]
    s.require([(r['arm'],r['epoch'],r['updates']) for r in log]==[(a,e,e*197) for a in ('A','AB') for e in range(1,41)],'TRAIN_LOG')
    for arm in ('A','AB'):
        r=s.read_json(folder/('candidate_'+arm+'.receipt.json'))
        s.require(r==barrier['candidates'][arm] and r['file_sha256']==s.sha_file(folder/('candidate_'+arm+'.pt')) and
                  r['epoch']==40 and r['updates']==7880 and r['initial_state_sha256']==initial,'CANDIDATE_PIN')
    from issue27frontend_paired_train_metrics_v1 import comparison,evaluate,compact_result
    rows=s.read_json(folder/'check_predictions.json')
    result,normalized=comparison(plan['contexts'],{r['uid']:r['logit'] for r in rows['A']},{r['uid']:r['logit'] for r in rows['AB']})
    s.require(rows==normalized and result==s.read_json(folder/'comparison.json') and compact_result(result)==receipt['verdict'],'COMPARISON_RECOMPUTATION')
    fit=s.read_json(folder/'postfit_predictions.json')
    for arm in ('A','AB'):
        s.require(fit[arm]==evaluate(s.views(plan['contexts'],'train',arm),{r['uid']:r['logit'] for r in fit[arm]}),'POSTFIT_RECOMPUTATION')
    return compact_result(result)

def supervise(command, output, config, synthetic=False, validator=None):
    output.mkdir(parents=True, exist_ok=False)
    started, process, job, reason, peak = time.monotonic(), None, None, None, 0
    caps = config['caps']
    s.atomic_json(output / 'attempt.json', {'controller_pid': os.getpid(), 'started_unix': time.time(),
        'caps': caps, 'synthetic': synthetic, 'restarts': 0})
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONHASHSEED='2705')
        process = subprocess.Popen(command, cwd=str(s.ROOT), env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
        job = Job(process, caps['memory_bytes'] - caps['controller_reserve_bytes'])
        s.atomic_json(output / 'worker_gate.json', {'worker_pid': process.pid, 'parent_pid': os.getpid(), 'started': started})
        while process.poll() is None:
            controller_peak = peak_memory()
            peak = max(peak, job.peak() + controller_peak)
            if controller_peak > caps['controller_reserve_bytes'] or peak > caps['memory_bytes']:
                reason = 'AGGREGATE_MEMORY_CAP'
            if time.monotonic() - started > caps['wall_seconds'] - 2:
                reason = 'WALL_CAP'
            if directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']:
                reason = 'OUTPUT_CAP'
            if reason:
                job.terminate(); break
            time.sleep(0.1)
        process.wait(timeout=10)
        peak = max(peak, job.peak() + peak_memory())
    except Exception as exc:
        reason = type(exc).__name__ + ': ' + str(exc)[:1000]
    finally:
        if process is not None and process.poll() is None:
            if job is not None: job.terminate()
            else: process.kill()
            process.wait(timeout=10)
        if job is not None: job.close()
    verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': reason or 'WORKER_TERMINAL_MISSING', 'scientific_capability': 'NOT_TESTED'}
    if not reason and process is not None and process.returncode == 0:
        try:
            path = output / 'worker_terminal.json'
            s.require(path.stat().st_size <= 65536, 'WORKER_TERMINAL_SIZE')
            if validator is None:
                validator = validate_worker
            verdict = validator(s.read_json(path), output, config, synthetic)
        except Exception as exc:
            verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': type(exc).__name__ + ': ' + str(exc)[:1000], 'scientific_capability': 'NOT_TESTED'}
    peak = max(peak, peak_memory())
    try:
        if (time.monotonic() - started > caps['wall_seconds'] or peak > caps['memory_bytes']
                or directory_bytes(output) > caps['output_bytes'] - caps['reserve_bytes']):
            verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'FINAL_RESOURCE_CAP', 'scientific_capability': 'NOT_TESTED'}
    except Exception as exc:
        verdict = {'status': 'INPUT_OR_EXECUTION_STOP', 'reason': 'FINAL_OUTPUT_SNAPSHOT: ' + str(exc)[:1000],
                   'scientific_capability': 'NOT_TESTED'}
    s.atomic_json(output / 'supervisor_terminal.json', {'verdict': verdict, 'synthetic': synthetic,
        'worker_count': int(process is not None), 'worker_exit_code': None if process is None else process.returncode,
        'restarts': 0, 'elapsed_seconds': time.monotonic() - started, 'aggregate_peak_bytes_upper_bound': peak,
        'enforcement': 'Windows job single worker, reserved controller memory, external wall/output monitor; no retry'})
    s.seal(output)
    return verdict

def status(output):
    if not output.exists():
        return {'status': 'NOT_STARTED', 'final': False}
    try:
        if (output / 'supervisor_terminal.json').exists() and (output / 'SHA256SUMS').exists():
            s.verify_manifest(output)
            terminal = s.read_json(output / 'supervisor_terminal.json')
            v = terminal['verdict']['status']
            return {**terminal, 'status': v, 'final': True, 'seal_verified': True}
        attempt = s.read_json(output / 'attempt.json')
        if not pid_alive(attempt['controller_pid']):
            return {'status': 'INTERRUPTED_DO_NOT_RESTART', 'final': False}
        if (output / 'worker_terminal.json').exists():
            return {'status': 'SEALING', 'final': False}
        if (output / 'progress.json').exists():
            return {**s.read_json(output / 'progress.json'), 'final': False}
        return {'status': 'STARTING', 'final': False}
    except (OSError, ValueError, KeyError, s.Stop):
        return {'status': 'RECEIPT_OR_SEAL_INVALID_DO_NOT_RESTART', 'final': False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('status','check-readiness','run-real','worker'))
    parser.add_argument('--stage',choices=('prepare','train'),required=True)
    parser.add_argument('--authorization')
    args=parser.parse_args();folder=s.ROOT/(s.PREP if args.stage=='prepare' else s.REAL)
    if args.mode=='status':print(s.canonical(status(folder)).decode());return
    if args.mode=='check-readiness':
        readiness(args.stage);s.require(not folder.exists(),'ATTEMPT_ALREADY_EXISTS')
        print(s.canonical({'status':'READY_FOR_SEPARATELY_AUTHORIZED_'+args.stage.upper(),'real_started':False}).decode());return
    s.require(args.authorization==(s.PREP_AUTH if args.stage=='prepare' else s.TRAIN_AUTH),'EXPLICIT_STAGE_AUTHORIZATION_REQUIRED')
    if args.mode=='worker':
        until=time.monotonic()+30
        while not (folder/'worker_gate.json').exists():
            s.require(time.monotonic()<until,'GATE_TIMEOUT');time.sleep(.05)
        gate=s.read_json(folder/'worker_gate.json')
        s.require(gate['worker_pid']==os.getpid() and gate['parent_pid']==os.getppid(),'WORKER_GATE_IDENTITY')
        config=readiness(args.stage)
        from issue27frontend_paired_train_runner_v2 import worker
        worker(folder,config,args.stage,gate['started']);return
    config=readiness(args.stage)
    os.environ.update(PYTHONHASHSEED='2705',OMP_NUM_THREADS='4',MKL_NUM_THREADS='4')
    command=[sys.executable,'-B',str(Path(__file__).resolve()),'worker','--stage',args.stage,'--authorization',args.authorization]
    print(s.canonical(supervise(command,folder,config,validator=validate_worker)).decode(),flush=True)


if __name__=='__main__':main()
