import base64,hashlib,hmac,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;CFG=json.loads((HERE/'.private.json').read_text())
def read(p):return json.loads(Path(p).read_text()) if Path(p).is_file() else None
def state():
    tasks={}
    for name in ['controls','tabm']:
        job=read(HERE/(name+'_JOB.json'));done=read(HERE/'results'/name/'COMPLETE.json');err=read(HERE/'results'/name/'STOP.json');s=''
        if job:s=subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20).stdout
        failed=any(t in s for t in ['FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL']);stage='STOP' if err or failed else 'COMPLETE' if done else 'RUNNING' if '|RUNNING|' in s else 'SUBMITTED'
        tasks[name]=dict(stage=stage,job=job,complete=done,error=err,scheduler=s,detail=read(HERE/'results'/name/'PROGRESS.json'))
    # Explicitly display upstream dependency failure without cancelling/restarting it.
    dep=subprocess.run(['sacct','-j','183549','-n','-P','--format=JobID,State,ExitCode,Elapsed'],capture_output=True,text=True,timeout=20).stdout
    if any(v in dep for v in ['FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL']) and tasks['tabm']['stage']=='SUBMITTED':tasks['tabm'].update(stage='UPSTREAM_STOP',error=dict(error='Original p3 job 183549 failed; dependent p4 is not released'))
    stage='COMPLETE' if all(v['stage']=='COMPLETE' for v in tasks.values()) else 'METHOD_STOP' if any(v['stage'] in ['STOP','UPSTREAM_STOP'] for v in tasks.values()) else 'RUNNING'
    return dict(version='P4_COMPLETE_BANK_V1',stage=stage,updated_unix=time.time(),tasks=tasks,tabm_p3_upstream=dep,reference_audit=read(HERE/'results/controls/HISTORY_LINEAGE_COUNTS.json'))
def receipts():
    files={};paths=list(HERE.glob('*_JOB.json'))+list(HERE.glob('*_RESOURCE.json'))+[HERE/'DEPENDENCY_GATE.json']
    for task in ['controls','tabm']:
        d=HERE/'results'/task
        if d.exists():paths+=list(d.glob('*.json'))+list(d.glob('*.md'))+list(d.glob('*.csv'))
        if (d/'baseline_audit').exists():paths+=list((d/'baseline_audit').glob('*.json'))
    for p in paths:
        if p.is_file():
            b=p.read_bytes();assert len(b)<64*1024**2;files[p.relative_to(HERE).as_posix()]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    for p in HERE.glob('slurm-*.*'):
        if p.suffix in ['.err','.out']:
            b=p.read_bytes()[-32768:];files['logs/'+p.name]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    return dict(files=files)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        try:
            token,action=self.path.strip('/').split('/');assert hmac.compare_digest(token,CFG['token']) and action in ['state','results'];b=json.dumps(state() if action=='state' else receipts()).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        except Exception as e:self.send_error(409,str(e)[:300])
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',18883),Handler);timer=threading.Timer(7*86400,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
