"""Code-only C4 delivery, durable preflight, and one fail-closed Slurm submit."""
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import signal
import subprocess
import tarfile
import threading
import time
import traceback

ROOT=Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE=ROOT/'runs/history_sample_coverage_c4_batch_resume_v1_20261102'
HERE=ROOT/'runs/history_sample_coverage_c4_budget_deployment_20261102'
PYTHON='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
PORT=18816
MAX_RESULT=512*2**20
MAX_CHUNK=16*2**20


def need(ok,message):
    if not ok:raise ValueError(message)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(4*2**20),b''):h.update(b)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name('.'+path.name+'.'+str(os.getpid())+'.'+str(threading.get_ident())+'.tmp')
    tmp.write_text(json.dumps(value,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8');tmp.replace(path)


def safe_name(name):
    p=PurePosixPath(name)
    need(isinstance(name,str) and bool(name) and not p.is_absolute() and '..' not in p.parts and
        '\\' not in name and ':' not in name and p.as_posix()==name and name not in ('.',''),'ARCHIVE_PATH')
    return p


def validate_archive(archive,expected):
    members=archive.getmembers();names=[m.name for m in members]
    need(len(names)==len(set(names)) and set(names)==set(expected),'EXACT_ARCHIVE_MEMBERS')
    for member in members:
        safe_name(member.name);need(member.isfile(),'ARCHIVE_REGULAR_FILES_ONLY')
        item=expected[member.name];need(member.size==item['bytes'],'ARCHIVE_MEMBER_SIZE')
        stream=archive.extractfile(member);h=hashlib.sha256();count=0
        for b in iter(lambda:stream.read(4*2**20),b''):count+=len(b);h.update(b)
        need(count==item['bytes'] and h.hexdigest()==item['sha256'],'ARCHIVE_MEMBER_PIN')
    return members


def stop_group(process):
    """Always target the session group, even if its leader has already exited."""
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:pass
    elif process.poll() is None:process.terminate()
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:pass
    if os.name=='posix':
        try:os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError:pass
    elif process.poll() is None:process.kill()
    process.wait(timeout=3)


def run_group(command,*,timeout,cwd=None):
    p=subprocess.Popen(command,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        out,err=p.communicate(timeout=timeout)
        return subprocess.CompletedProcess(command,p.returncode,out,err)
    finally:stop_group(p)


def tail(path,count=6000):
    path=Path(path)
    if not path.exists():return ''
    with path.open('rb') as f:f.seek(max(0,path.stat().st_size-count));return f.read().decode(errors='replace')


class BudgetController:
    def __init__(self,config,*,root=ROOT,here=HERE,package=PACKAGE,clock=time.monotonic,wallclock=time.time):
        self.config=config;self.root=Path(root);self.here=Path(here);self.package=Path(package)
        self.clock=clock;self.wallclock=wallclock;self.lock=threading.RLock();self.child=None;self.deadline=None
        need(re.fullmatch('[0-9a-f]{48}',config['token']) is not None,'TOKEN_SHAPE')
        need(type(config['bundle']['bytes']) is int and 0<config['bundle']['bytes']<=64*2**20,'CODE_BUNDLE_SIZE')
        need(re.fullmatch('[0-9a-f]{64}',config['execution_card_sha256']) is not None,'CARD_PIN_SHAPE')
        need(bool(config['files']) and 'EXECUTION_CARD.json' in config['files'],'CODE_MANIFEST')
        for name in config['files']:safe_name(name)
        self.here.mkdir(parents=True,exist_ok=True)
        need(not (self.here/'STATE.json').exists(),'NEW_CONTROLLER_STATE')
        need(not self.package.exists(),'SCIENCE_PACKAGE_MUST_BE_NEW')
        self.state=dict(status='READY',submitted=False,candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',
            execution_card_sha256=config['execution_card_sha256'],automatic_science_retry=False,code_only_upload=True)
        keys=('execution_card_sha256','environment_sha256','previous_hpc_config_sha256',
              'expected_environment','test_modules','expected_test_count')
        write(self.here/'PREFLIGHT_CONFIG.json',{k:config[k] for k in keys if k in config})
        self.save()

    def save(self):write(self.here/'STATE.json',self.state)

    def transfer(self):
        path=self.here/'bundle.tar';part=self.here/'bundle.part';spec=self.config['bundle']
        if path.exists():need(path.stat().st_size==spec['bytes'] and sha(path)==spec['sha256'],'RETAINED_CODE_BUNDLE_PIN')
        return dict(complete=path.exists(),offset=path.stat().st_size if path.exists() else part.stat().st_size if part.exists() else 0,total=spec['bytes'])

    def upload(self,offset,payload,chunk_sha):
        need(self.state['status'] in ('READY','UPLOADING','UPLOADED'),'UPLOAD_PHASE')
        need(type(offset) is int and len(payload)>0 and len(payload)<=MAX_CHUNK,'UPLOAD_CHUNK')
        need(hashlib.sha256(payload).hexdigest()==chunk_sha,'CHUNK_PIN')
        current=self.transfer();need(not current['complete'] and offset==current['offset'],'UPLOAD_OFFSET')
        need(offset+len(payload)<=current['total'],'UPLOAD_SIZE')
        part=self.here/'bundle.part'
        with part.open('xb' if offset==0 else 'ab') as f:f.write(payload)
        self.state['status']='UPLOADING'
        if part.stat().st_size==current['total']:
            need(sha(part)==self.config['bundle']['sha256'],'CODE_BUNDLE_PIN')
            part.rename(self.here/'bundle.tar');self.state['status']='UPLOADED'
        self.save();return self.transfer()

    def install(self):
        need(self.state['status']=='UPLOADED' and not self.package.exists(),'ONE_NEW_INSTALL')
        bundle=self.here/'bundle.tar';need(sha(bundle)==self.config['bundle']['sha256'],'CODE_BUNDLE_PIN')
        pending=self.package.with_name(self.package.name+'.install');need(not pending.exists(),'NEW_INSTALL_STAGING')
        with tarfile.open(bundle,'r:') as archive:
            members=validate_archive(archive,self.config['files'])
            pending.mkdir(parents=True,exist_ok=False)
            for member in members:
                target=pending/member.name;target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as dst:
                    src=archive.extractfile(member)
                    for b in iter(lambda:src.read(4*2**20),b''):dst.write(b)
                need(sha(target)==self.config['files'][member.name]['sha256'],'INSTALLED_FILE_PIN')
        need(sha(pending/'EXECUTION_CARD.json')==self.config['execution_card_sha256'],'INSTALLED_CARD_PIN')
        need(not self.package.exists(),'NO_PACKAGE_OVERWRITE');pending.rename(self.package)
        self.state['status']='INSTALLED';self.save();return dict(self.state)

    def preflight(self):
        need(self.state['status']=='INSTALLED' and self.child is None,'PREFLIGHT_ONCE')
        need(sha(self.here/'preflight_worker.py')==self.config['preflight_worker_sha256'],'PREFLIGHT_WORKER_PIN')
        need(sha(self.package/'EXECUTION_CARD.json')==self.config['execution_card_sha256'],'SCIENCE_CARD_PIN')
        script='set -euo pipefail\nsource '+shlex.quote(str(self.root/'frontend_compat_v1/environment.sh'))+'\n'
        script+='export PYTHONPATH='+shlex.quote(str(self.root/'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201')+':'+str(self.root/'environment/vendor_py311_v1'))+':"${PYTHONPATH:-}"\n'
        script+='export OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUTF8=1\n'
        script+='exec '+shlex.quote(PYTHON)+' -u -B '+shlex.quote(str(self.here/'preflight_worker.py'))+' --root '+shlex.quote(str(self.root))+' --output '+shlex.quote(str(self.here))+' --config '+shlex.quote(str(self.here/'PREFLIGHT_CONFIG.json'))+'\n'
        (self.here/'preflight.sh').write_text(script,encoding='utf-8')
        with (self.here/'PREFLIGHT.log').open('xb') as log:
            self.child=subprocess.Popen(['bash','--noprofile','--norc',str(self.here/'preflight.sh')],stdin=subprocess.DEVNULL,
                stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        self.preflight_started=self.clock();self.state.update(status='PREFLIGHT_RUNNING',preflight_pid=self.child.pid);self.save()
        return dict(self.state)

    def poll_preflight(self):
        if self.child is None or self.state['status']!='PREFLIGHT_RUNNING':return
        if self.child.poll() is None:
            if self.clock()-self.preflight_started<=600:return
            stop_group(self.child);self.state.update(status='PREFLIGHT_FAIL',error='PREFLIGHT_PROCESS_GROUP_TIMEOUT')
        else:
            stop_group(self.child);path=self.here/'PREFLIGHT_RESULT.json'
            value=read(path) if path.exists() else dict(status='FAIL',error='PREFLIGHT_EXIT_WITHOUT_RESULT')
            self.state.update(status='PREFLIGHT_PASS' if self.child.returncode==0 and value['status']=='PASS' else 'PREFLIGHT_FAIL',preflight=value,preflight_exit=self.child.returncode)
        self.state['preflight_log_tail']=tail(self.here/'PREFLIGHT.log');self.save()

    def submit(self):
        self.poll_preflight()
        if self.state.get('submitted'):return dict(self.state)
        need(self.state['status']=='PREFLIGHT_PASS','ONE_SUBMIT_AFTER_PREFLIGHT')
        need(sha(self.package/'EXECUTION_CARD.json')==self.config['execution_card_sha256'],'SCIENCE_CARD_PIN')
        need(not (self.package/'ENCODE_ATTEMPT.json').exists() and not (self.package/'outputs').exists(),'SCIENCE_NOT_STARTED')
        with (self.here/'SUBMIT_ATTEMPT.json').open('x',encoding='utf-8') as f:json.dump(dict(automatic_retry=False),f)
        self.state['status']='SUBMITTING';self.save()
        try:ran=run_group(['sbatch','--parsable',str(self.package/'hpc/run_encode.slurm')],timeout=30,cwd=self.package)
        except BaseException as exc:
            self.state.update(status='SUBMISSION_UNCERTAIN_NO_RETRY',error=str(exc));self.save();raise
        self.state['submission']=dict(returncode=ran.returncode,stdout=ran.stdout,stderr=ran.stderr)
        job=ran.stdout.strip().split(';')[0]
        if ran.returncode==0 and job.isdigit():self.state.update(status='SUBMITTED',submitted=True,job_id=job)
        else:self.state.update(status='SUBMISSION_UNCERTAIN_NO_RETRY' if ran.returncode==0 else 'SUBMIT_FAILED_NO_RETRY')
        self.save();need(self.state.get('submitted'),'SUBMISSION_FAILED_OR_UNCERTAIN_NO_RETRY');return dict(self.state)

    def observe_budget(self,worker):
        started=worker.get('started_utc')
        if not started:return
        stamp=datetime.fromisoformat(started.replace('Z','+00:00'));need(stamp.tzinfo is not None,'AWARE_ENCODING_START')
        age=self.wallclock()-stamp.timestamp();need(age>=-5,'ENCODING_START_IN_FUTURE')
        proposed=self.clock()+18000-max(0,age)
        self.deadline=proposed if self.deadline is None else min(self.deadline,proposed)
        self.state['encoding_started_utc']=started

    def budget_remaining(self):return None if self.deadline is None else max(0.,self.deadline-self.clock())

    def cancel_if_expired(self):
        if self.state.get('status')=='COMPLETE':return
        path=self.package/'outputs/encoding/STATUS.json'
        if path.exists():self.observe_budget(read(path))
        if self.deadline is None or self.clock()<self.deadline:return
        if self.state.get('status')=='BUDGET_EXPIRED':return
        self.state.update(status='BUDGET_EXPIRED',error='ADDITIONAL_18000_SECOND_WALL_BUDGET_EXHAUSTED')
        receipt=self.package/'outputs/encoding/STAGE_RECEIPT.json'
        if self.state.get('job_id') and not (receipt.exists() and read(receipt).get('technical_status')=='COMPLETED'):
            with (self.here/'BUDGET_CANCEL_ATTEMPT.json').open('x') as f:json.dump(dict(job_id=self.state['job_id'],automatic_retry=False),f)
            try:
                ran=run_group(['scancel',self.state['job_id']],timeout=15)
                self.state['budget_cancel']=dict(returncode=ran.returncode,stdout=ran.stdout,stderr=ran.stderr)
            except Exception as exc:self.state['budget_cancel_error']=str(exc)
        self.save()

    def snapshot(self,*,scheduler=True):
        self.poll_preflight();self.cancel_if_expired();result=dict(self.state)
        result.update(transfers=dict(code=self.transfer()),free_bytes=shutil.disk_usage(self.root).free,
            budget_remaining_seconds=self.budget_remaining())
        for name in ('PREFLIGHT_STATUS.json','PREFLIGHT_RESULT.json'):
            p=self.here/name
            if p.exists():result[name]=read(p)
        for name in ('STATUS.json','RESULT.json','STAGE_RECEIPT.json'):
            p=self.package/'outputs/encoding'/name
            if p.exists():result[name]=read(p)
        if result.get('STATUS.json',{}).get('started_utc'):
            self.observe_budget(result['STATUS.json'])
            result.update(encoding_started_utc=self.state['encoding_started_utc'],budget_remaining_seconds=self.budget_remaining())
        if scheduler and self.state.get('job_id'):
            job=self.state['job_id']
            try:
                ran=run_group(['squeue','-h','-j',job,'-o','%T|%R|%M'],timeout=15);result['squeue']=ran.stdout.strip()
                if ran.returncode:result['scheduler_error']=ran.stderr.strip()
                elif not result['squeue']:
                    ran=run_group(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','-P'],timeout=15);result['sacct']=ran.stdout.strip()
                    if ran.returncode:result['scheduler_error']=ran.stderr.strip()
            except (OSError,subprocess.TimeoutExpired) as exc:result['scheduler_error']=str(exc)
            result['log_tail']=tail(self.package/('SLURM-'+job+'.log'))
        result['preflight_log_tail']=tail(self.here/'PREFLIGHT.log')
        if result.get('STATUS.json',{}).get('technical_status')=='EXCEPTION_STOPPED':
            result['worker_errors']={}
            for stage in ('prepare','encode'):
                p=self.package/'outputs/encoding/workers'/('NETATMO_'+stage+'_ERROR.json')
                if p.exists():result['worker_errors'][stage]=read(p)
                result['worker_errors'][stage+'_log_tail']=tail(p.with_name('NETATMO_'+stage+'.log'))
        return result

    def result_archive(self):
        self.cancel_if_expired();need(self.state['status']!='BUDGET_EXPIRED','RESULT_AFTER_BUDGET_EXHAUSTION')
        source=self.package/'outputs/encoding';receipt=read(source/'STAGE_RECEIPT.json')
        need(receipt.get('technical_status')=='COMPLETED' and receipt.get('scientific_status')=='C4_ENCODING_COMPLETE','ENCODING_NOT_COMPLETE')
        result=read(source/'RESULT.json');need(result['execution_card_sha256']==self.config['execution_card_sha256'],'RESULT_CARD')
        names=sorted(set(receipt['outputs'])|{'STATUS.json','STAGE_RECEIPT.json'})
        total=0
        for name in names:
            safe_name(name);p=source/name
            need(p.resolve().is_relative_to(source.resolve()) and p.is_file() and not p.is_symlink(),'RESULT_FILE_SCOPE')
            need(p.suffix.lower() not in ('.pcap','.pcapng','.sqlite') and p.name not in ('contexts_1.sqlite','contexts_2.sqlite'),'RESULT_EXCLUDES_LARGE_REPLAY_SCRATCH')
            total+=p.stat().st_size
            if name in receipt['outputs']:need(sha(p)==receipt['outputs'][name],'RESULT_OUTPUT_PIN:'+name)
        need(total+len(names)*2048<MAX_RESULT,'RESULT_BOUNDED_512_MIB')
        target=self.here/'result.tar'
        if not target.exists():
            part=self.here/'result.part';need(not part.exists(),'NEW_RESULT_ARCHIVE')
            with tarfile.open(part,'w') as ar:
                for name in names:ar.add(source/name,arcname=name,recursive=False)
            need(part.stat().st_size<MAX_RESULT,'RESULT_TAR_SIZE');part.rename(target)
        return target

    def complete(self,payload):
        self.cancel_if_expired();need(self.state.get('submitted') and self.state['status']!='BUDGET_EXPIRED','COMPLETE_WITHIN_BUDGET')
        need(read(self.package/'outputs/encoding/STAGE_RECEIPT.json')['technical_status']=='COMPLETED','ENCODING_BEFORE_LOCAL_ACCEPTANCE')
        for key in ('final_acceptance_sha256','verification_stage_receipt_sha256'):
            need(re.fullmatch('[0-9a-f]{64}',payload.get(key,'')) is not None,'LOCAL_ACCEPTANCE_PIN')
        self.state.update(status='COMPLETE',local_acceptance=payload);self.save();return dict(self.state)


def main(config):
    control=BudgetController(config);closed=threading.Event()
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(30)
        def log_message(self,*args):pass
        def route(self):
            prefix='/'+config['token']+'/';need(self.path.startswith(prefix),'TOKEN_ROUTE');return self.path[len(prefix):]
        def send(self,value,status=200):
            body=json.dumps(value,ensure_ascii=False,allow_nan=False).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_GET(self):
            try:
                route=self.route()
                if route=='state':
                    with control.lock:result=control.snapshot()
                    self.send(result);return
                if route=='result':
                    with control.lock:path=control.result_archive()
                    size=path.stat().st_size;offset=0;range_value=self.headers.get('Range')
                    if range_value:
                        match=re.fullmatch(r'bytes=(\d+)-',range_value);need(match is not None,'RESULT_RANGE');offset=int(match[1]);need(0<=offset<size,'RESULT_RANGE_OFFSET')
                    self.send_response(206 if offset else 200);self.send_header('Content-Length',str(size-offset))
                    self.send_header('X-Content-SHA256',sha(path));self.send_header('X-Content-Total-Bytes',str(size))
                    if offset:self.send_header('Content-Range',f'bytes {offset}-{size-1}/{size}')
                    self.end_headers()
                    with path.open('rb') as f:
                        f.seek(offset)
                        for b in iter(lambda:f.read(4*2**20),b''):self.wfile.write(b)
                    return
                self.send(dict(error='UNKNOWN_ROUTE'),404)
            except Exception as exc:self.send(dict(error=str(exc),traceback=traceback.format_exc()),409)
        def do_POST(self):
            try:
                route=self.route();length=int(self.headers.get('Content-Length','0'))
                with control.lock:
                    if route=='upload/code':
                        need(0<length<=MAX_CHUNK,'UPLOAD_CONTENT_LENGTH');value=control.upload(int(self.headers['X-Offset']),self.rfile.read(length),self.headers['X-Chunk-SHA256'])
                    elif route=='complete':
                        need(0<length<65536,'COMPLETE_CONTENT_LENGTH');value=control.complete(json.loads(self.rfile.read(length)))
                    else:
                        need(length==0,'NO_ACTION_BODY')
                        if route=='install':value=control.install()
                        elif route=='preflight':value=control.preflight()
                        elif route=='submit':value=control.submit()
                        elif route=='cancel_budget':control.cancel_if_expired();value=dict(control.state)
                        else:raise ValueError('UNKNOWN_ROUTE')
                self.send(value)
            except Exception as exc:self.send(dict(error=str(exc),traceback=traceback.format_exc()),409)
    def watchdog():
        while not closed.wait(1):
            try:
                with control.lock:control.poll_preflight();control.cancel_if_expired()
            except Exception as exc:
                with control.lock:control.state.update(status='CONTROLLER_ERROR',error=str(exc));control.save()
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler)
    threading.Thread(target=watchdog,daemon=True,name='c4-bounded-control').start()
    timer=threading.Timer(config.get('controller_lifetime_seconds',36*3600),server.shutdown);timer.daemon=True;timer.start()
    print('C4_BUDGET_DELIVERY_READY port='+str(PORT),flush=True)
    try:server.serve_forever(poll_interval=.5)
    finally:
        closed.set();timer.cancel();server.server_close()
        if control.child is not None:stop_group(control.child)


if __name__=='__main__':main(read(HERE/'.private/receiver_config.json'))
