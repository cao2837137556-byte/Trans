import base64,hashlib,hmac,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;OUT=HERE/'results';CFG=json.loads((HERE/'.private.json').read_text())
def read(p):return json.loads(Path(p).read_text()) if Path(p).is_file() else None
def state():
    job=read(HERE/'JOB.json');done=read(OUT/'RUN_COMPLETE.json');stop=read(OUT/'STOP.json')
    p=dict(version='TABM_3D_TRANSFER_V1',updated_unix=time.time(),job=job,detail=read(OUT/'PROGRESS.json'),raw_reproduction=read(OUT/'TABM_RAW_REPRODUCTION.json'),calibration=read(OUT/'TABM_SOURCE_CALIBRATION.json'),evaluation=read(OUT/'EVALUATION_GATES.json'),error=stop,stage='COMPLETE' if done else 'STOP' if stop else 'SUBMITTED')
    if job:
        text=subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20).stdout;p['scheduler']=text
        if any(s in text for s in ['FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL']):p['stage']='STOP'
        elif '|RUNNING|' in text and not done and not stop:p['stage']='RUNNING'
    return p
def receipts():
    files={};paths=[HERE/n for n in ['JOB.json','DEPENDENCY_GATE.json','RESOURCE_USAGE.json','DELIVERY.json']]
    if OUT.exists():paths+=list(OUT.glob('*.json'))+list(OUT.glob('*.md'))+list(OUT.glob('*.csv'))
    audit=OUT/'frozen_audit'
    if audit.exists():paths += list(audit.glob('*.json'))
    for p in paths:
        if not p.is_file():continue
        b=p.read_bytes();assert len(b)<64*1024**2;files[p.relative_to(HERE).as_posix()]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    job=read(HERE/'JOB.json')
    if job:
        for ext in ['err','out']:
            path=HERE/('slurm-'+job['job_id']+'.'+ext)
            if path.exists():
                b=path.read_bytes()[-32768:];files['logs/slurm_tail.'+ext]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    return dict(files=files)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            token,action=self.path.strip('/').split('/');assert hmac.compare_digest(token,CFG['token']) and action in ['state','results']
            b=json.dumps(state() if action=='state' else receipts()).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        except Exception as e:self.send_error(409,str(e)[:350])
if __name__=='__main__':
    s=ThreadingHTTPServer(('127.0.0.1',18882),Handler);timer=threading.Timer(7*86400,s.shutdown);timer.daemon=True;timer.start();s.serve_forever()
