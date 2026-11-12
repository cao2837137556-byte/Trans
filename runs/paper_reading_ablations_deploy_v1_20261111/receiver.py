"""Read-only progress and small receipts over the user's existing SSH tunnel."""
import base64,hashlib,hmac,importlib.util,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
SCIENCE=ROOT/'runs/paper_reading_ablations_v2_20261111';RESULT=SCIENCE/'results'
CFG=json.loads((HERE/'.private.json').read_text())
def read(path):return json.loads(Path(path).read_text()) if Path(path).is_file() else None
def state():
    job=read(HERE/'JOB.json');done=read(RESULT/'RUN_COMPLETE.json');stop=read(RESULT/'STOP.json')
    p=dict(version='PAPER_READING_ABLATIONS_V1',updated_unix=time.time(),job=job,detail=read(RESULT/'PROGRESS.json'),baseline=read(RESULT/'BASELINE_ACCEPTANCE.json'),items={name:read(RESULT/name/'COMPLETE.json') for name in ['guard','exponent']},error=stop)
    p['stage']='COMPLETE' if done else 'STOP' if stop else 'SUBMITTED'
    if job:
        s=subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20).stdout;p['scheduler']=s
        if any(x in s for x in ['FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL']):p['stage']='STOP'
        elif '|RUNNING|' in s and not done and not stop:p['stage']='RUNNING'
    p['baseline_jobs']=read(HERE/'BASELINE_STATUS_SNAPSHOT.json')
    return p
def receipts():
    files={}
    paths=[HERE/n for n in ['JOB.json','DEPENDENCY_GATE.json','DEPLOYMENT.json','BASELINE_STATUS_SNAPSHOT.json']]
    paths += [RESULT/n for n in ['PROGRESS.json','BASELINE_ACCEPTANCE.json','ASSET_IDENTITY.json','DEPENDENCY_LOCATIONS.json','RUN_COMPLETE.json','STOP.json']]
    paths += [SCIENCE/'RESOURCE_USAGE.txt']
    for item in ['guard','exponent']:
        # Never retrieve a half-written item or large changed-UID gzip data.
        if (RESULT/item/'COMPLETE.json').exists():
            paths += [RESULT/item/n for n in ['RESULT_READOUT.md','METRICS.json','METRICS.csv','PAIRED_CHANGES.json','PAIRED_CHANGES.csv','CHANGED_UID_MANIFEST.json','VERIFICATION.json','COMPLETE.json']]
    for q in paths:
        if not q.is_file():continue
        key=('delivery/'+q.name) if q.parent==HERE else q.relative_to(SCIENCE).as_posix()
        b=q.read_bytes();assert len(b)<64*1024**2;files[key]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    job=read(HERE/'JOB.json')
    if job:
        for ext in ['out','err']:
            path=SCIENCE/('slurm-'+job['job_id']+'.'+ext)
            if path.exists():
                b=path.read_bytes()[-32768:];files['delivery/slurm_tail.'+ext]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    return dict(files=files)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            parts=self.path.strip('/').split('/');assert len(parts)==2 and hmac.compare_digest(parts[0],CFG['token'])
            assert parts[1] in ['state','results'];v=state() if parts[1]=='state' else receipts()
            data=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except Exception as e:self.send_error(409,str(e)[:350])
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',18881),Handler);timer=threading.Timer(7*86400,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
