import base64,hashlib,hmac,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;P4=HERE.parent/'p4_complete_bank_v1_20261111';CFG=json.loads((HERE/'.private.json').read_text())
def read(p):return json.loads(Path(p).read_text()) if Path(p).is_file() else None
def scheduler(job):return subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20).stdout
def state():
    j=read(HERE/'JOB.json');done=read(HERE/'COMPLETE.json');error=read(HERE/'STOP.json');s=scheduler(j) if j else ''
    failed=any(x in s for x in ['FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL']);stage='STOP' if error or failed else 'COMPLETE' if done else 'RUNNING' if '|RUNNING|' in s else 'SUBMITTED'
    return dict(version='TABM_TRANSFER_REPAIR_V1',stage=stage,job=j,scheduler=s,detail=read(HERE/'PROGRESS.json'),error=error,p3_complete=read(HERE/'results/RUN_COMPLETE.json'),p4_complete=read(HERE/'p4_results/COMPLETE.json'),controls_complete=read(P4/'results/controls/COMPLETE.json'),corrected_lineage=read(HERE/'HISTORY_LINEAGE_COUNTS_CORRECTED.json'),previous_failed_job='183549',replaced_pending_job='183552',updated_unix=time.time())
def receipts():
    files={};paths=[HERE/n for n in ['JOB.json','CPU_PARITY_DIAGNOSIS.json','ARITHMETIC_DIAGNOSIS.json','STOP.json','COMPLETE.json','RESOURCE_USAGE.json','REPLACED_DEPENDENCY.json']]
    for directory in ['results','p4_results']:
        p=HERE/directory
        if p.exists():paths+=list(p.glob('*.json'))+list(p.glob('*.csv'))+list(p.glob('*.md'))
    for p in paths:
        if p.is_file():
            b=p.read_bytes();assert len(b)<64*1024**2;files[p.relative_to(HERE).as_posix()]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    for p in HERE.glob('slurm-*.*'):
        if p.suffix in ['.out','.err']:
            b=p.read_bytes()[-32768:];files['logs/'+p.name]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
    return dict(files=files)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            token,action=self.path.strip('/').split('/');assert hmac.compare_digest(token,CFG['token']) and action in ['state','results'];b=json.dumps(state() if action=='state' else receipts()).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        except Exception as e:self.send_error(409,str(e)[:300])
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',18884),Handler);timer=threading.Timer(7*86400,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
