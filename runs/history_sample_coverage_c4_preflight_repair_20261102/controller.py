"""Resume installed C4 with durable asynchronous preflight and one submission."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib,json,os,shlex,signal,subprocess,threading,time,traceback,tarfile
from pathlib import Path

ROOT=Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE=ROOT/'runs/history_sample_coverage_c4_header_repair_v1_20261101'
HERE=ROOT/'runs/history_sample_coverage_c4_preflight_repair_20261102'
OLD=ROOT/'runs/history_sample_coverage_c4_header_deployment_20261101'
PYTHON='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
CARD='fdd491483c8408b8054cf195de5cfaee82c2f0772d56313ee1ae5ca34633350b'
PORT=18812
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*2**20),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    p=Path(p);q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n');q.replace(p)
def need(ok,msg):
    if not ok:raise ValueError(msg)
def tail(p,n=6000):
    p=Path(p)
    if not p.exists():return ''
    with p.open('rb') as f:f.seek(max(0,p.stat().st_size-n));return f.read().decode(errors='replace')

def stop_group(process):
    """The leader may exit before descendants: always clean its process group."""
    try:os.killpg(process.pid,signal.SIGTERM)
    except ProcessLookupError:pass
    try:process.wait(timeout=5)
    except subprocess.TimeoutExpired:pass
    try:os.killpg(process.pid,signal.SIGKILL)
    except ProcessLookupError:pass
    process.wait(timeout=5)

def process_diagnostics():
    """Read only this user's preflight processes, without command arguments."""
    observed=[]
    for p in Path('/proc').glob('[0-9]*'):
        try:
            if p.stat().st_uid!=os.getuid():continue
            cmd=(p/'cmdline').read_bytes()
            if b'import platform,json,unittest;' not in cmd and b'preflight_worker.py' not in cmd:continue
            status=(p/'status').read_text();stat=(p/'stat').read_text().rsplit(')',1)[1].split()
            observed.append(dict(pid=int(p.name),ppid=int(stat[1]),state=stat[0],wchan=(p/'wchan').read_text(),rss=[x for x in status.splitlines() if x.startswith('VmRSS:')]))
        except (OSError,ValueError):continue
    return observed

def main(token):
    need(len(token)==48 and not (HERE/'STATE.json').exists(),'NEW_CONTROLLER_STATE')
    need(sha(PACKAGE/'EXECUTION_CARD.json')==CARD,'INSTALLED_SCIENCE_CARD')
    need(not read(OLD/'STATE.json')['submitted'],'NO_PRIOR_SUBMISSION')
    need(not (PACKAGE/'ENCODE_ATTEMPT.json').exists() and not (PACKAGE/'outputs').exists(),'NO_PRIOR_REAL_WORK')
    lock=threading.Lock();child=None;state=dict(status='INSTALLED',submitted=False,candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',execution_card_sha256=CARD)
    write(HERE/'INITIAL_PROCESS_DIAGNOSTICS.json',process_diagnostics())
    def save():write(HERE/'STATE.json',state)
    def poll_preflight():
        nonlocal child
        if child is None:return
        result=HERE/'PREFLIGHT_RESULT.json'
        if child.poll() is None:
            if time.monotonic()-state['_preflight_started_monotonic']>600:
                stop_group(child)
                state.update(status='PREFLIGHT_FAIL',error='PREFLIGHT_PROCESS_GROUP_TIMEOUT',preflight_log_tail=tail(HERE/'PREFLIGHT.log'));save()
            return
        if state['status']!='PREFLIGHT_RUNNING':return
        state['preflight_exit']=child.returncode
        if result.exists():
            state['preflight']=read(result)
            state['status']='PREFLIGHT_PASS' if child.returncode==0 and state['preflight']['status']=='PASS' else 'PREFLIGHT_FAIL'
        else:state.update(status='PREFLIGHT_FAIL',error='PREFLIGHT_EXIT_WITHOUT_RESULT')
        state['preflight_log_tail']=tail(HERE/'PREFLIGHT.log');save()
    def watchdog():
        while not closed.wait(1):
            try:
                with lock:poll_preflight()
            except Exception as exc:
                with lock:state.update(status='CONTROLLER_ERROR',error=str(exc),traceback=traceback.format_exc());save()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,value,status=200):
            b=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        def route(self):
            need(self.path.startswith('/'+token+'/'),'TOKEN');return self.path[len(token)+2:]
        def do_GET(self):
            try:
                route=self.route()
                if route=='diagnostics':
                    self.send(dict(processes=process_diagnostics(),preflight_log=tail(HERE/'PREFLIGHT.log'),initial=read(HERE/'INITIAL_PROCESS_DIAGNOSTICS.json')));return
                if route=='state':
                    with lock:poll_preflight();result={k:v for k,v in state.items() if not k.startswith('_')}
                    for name in ('PREFLIGHT_STATUS.json','PREFLIGHT_RESULT.json'):
                        if (HERE/name).exists():result[name]=read(HERE/name)
                    result['preflight_log_tail']=tail(HERE/'PREFLIGHT.log')
                    for name in ('STATUS.json','RESULT.json','STAGE_RECEIPT.json'):
                        p=PACKAGE/'outputs/encoding'/name
                        if p.exists():result[name]=read(p)
                    if state.get('job_id'):
                        job=state['job_id'];ran=subprocess.run(['squeue','-h','-j',job,'-o','%T|%R|%M'],capture_output=True,text=True,timeout=15);result['squeue']=ran.stdout.strip()
                        if not result['squeue']:
                            ran=subprocess.run(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','-P'],capture_output=True,text=True,timeout=15);result['sacct']=ran.stdout.strip()
                        result['log_tail']=tail(PACKAGE/('SLURM-'+job+'.log'))
                    if result.get('STATUS.json',{}).get('technical_status')=='EXCEPTION_STOPPED':
                        result['worker_errors']={}
                        for stage in ('prepare','encode'):
                            p=PACKAGE/'outputs/encoding/workers'/('NETATMO_'+stage+'_ERROR.json')
                            if p.exists():result['worker_errors'][stage]=read(p)
                            result['worker_errors'][stage+'_log_tail']=tail(p.with_name('NETATMO_'+stage+'.log'))
                    self.send(result);return
                if route=='result':
                    source=PACKAGE/'outputs/encoding';need(read(source/'STAGE_RECEIPT.json')['technical_status']=='COMPLETED','ENCODING_NOT_COMPLETE')
                    target=HERE/'result.tar'
                    if not target.exists():
                        with tarfile.open(target.with_suffix('.part'),'w') as ar:
                            for p in sorted(source.rglob('*')):
                                if p.is_file():need(not p.is_symlink(),'RESULT_LINK');ar.add(p,arcname=p.relative_to(source).as_posix(),recursive=False)
                        target.with_suffix('.part').rename(target)
                    need(target.stat().st_size<2*2**30,'RESULT_SIZE')
                    self.send_response(200);self.send_header('Content-Length',str(target.stat().st_size));self.send_header('X-Content-SHA256',sha(target));self.end_headers()
                    with target.open('rb') as f:
                        for b in iter(lambda:f.read(4*2**20),b''):self.wfile.write(b)
                    return
                self.send(dict(error='UNKNOWN_ROUTE'),404)
            except Exception as exc:self.send(dict(error=str(exc),traceback=traceback.format_exc()),409)
        def do_POST(self):
            nonlocal child
            try:
                route=self.route();need(int(self.headers.get('Content-Length','0'))==0,'NO_ACTION_BODY')
                with lock:
                    if route=='preflight':
                        need(state['status']=='INSTALLED' and child is None,'PREFLIGHT_ONCE')
                        need(not process_diagnostics(),'NO_ORPHAN_PREFLIGHT')
                        script='set -euo pipefail\nsource '+shlex.quote(str(ROOT/'frontend_compat_v1/environment.sh'))+'\nexport PYTHONPATH='+shlex.quote(str(ROOT/'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201')+':'+str(ROOT/'environment/vendor_py311_v1'))+':"${PYTHONPATH:-}"\nexport OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONUTF8=1\nprintf "C4_FIXED_ENVIRONMENT_READY\\n"\nexec '+shlex.quote(PYTHON)+' -u -B '+shlex.quote(str(HERE/'preflight_worker.py'))+'\n'
                        (HERE/'preflight.sh').write_text(script)
                        log=(HERE/'PREFLIGHT.log').open('xb')
                        child=subprocess.Popen(['bash','--noprofile','--norc',str(HERE/'preflight.sh')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);log.close()
                        state.update(status='PREFLIGHT_RUNNING',preflight_pid=child.pid,_preflight_started_monotonic=time.monotonic());save();self.send({k:v for k,v in state.items() if not k.startswith('_')});return
                    if route=='submit':
                        poll_preflight();need(state['status']=='PREFLIGHT_PASS' and not state['submitted'],'ONE_SUBMIT_AFTER_PREFLIGHT')
                        need(sha(PACKAGE/'EXECUTION_CARD.json')==CARD and not (PACKAGE/'ENCODE_ATTEMPT.json').exists(),'SCIENCE_NOT_STARTED')
                        need(not read(OLD/'STATE.json')['submitted'],'OLD_CONTROLLER_NOT_SUBMITTED')
                        with (HERE/'SUBMIT_ATTEMPT.json').open('x') as f:json.dump(dict(candidate=state['candidate']),f)
                        state['status']='SUBMITTING';save()
                        try:ran=subprocess.run(['sbatch','--parsable',str(PACKAGE/'hpc/run_encode.slurm')],cwd=PACKAGE,capture_output=True,text=True,timeout=30)
                        except BaseException as exc:
                            state.update(status='SUBMISSION_UNCERTAIN_NO_RETRY',error=str(exc));save();raise
                        state['submission']=dict(returncode=ran.returncode,stdout=ran.stdout,stderr=ran.stderr)
                        state['status']='SUBMITTED' if ran.returncode==0 else 'SUBMIT_FAILED_NO_RETRY'
                        if ran.returncode==0:
                            job=ran.stdout.strip().split(';')[0]
                            if not job.isdigit():
                                state.update(status='SUBMISSION_UNCERTAIN_NO_RETRY',error='INVALID_SBATCH_JOB_ID');save();raise ValueError('JOB_ID')
                            state.update(submitted=True,job_id=job)
                        save();self.send({k:v for k,v in state.items() if not k.startswith('_')});return
                    self.send(dict(error='UNKNOWN_ROUTE'),404)
            except Exception as exc:self.send(dict(error=str(exc),traceback=traceback.format_exc()),409)
    closed=threading.Event();save();threading.Thread(target=watchdog,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',PORT),Handler);timer=threading.Timer(36000,server.shutdown);timer.daemon=True;timer.start()
    print('C4_PREFLIGHT_REPAIR_READY port='+str(PORT),flush=True)
    try:server.serve_forever(poll_interval=.5)
    finally:closed.set();timer.cancel();server.server_close()

if __name__=='__main__':main(read(HERE/'.private/connection.json')['token'])
