import base64,hashlib,hmac,importlib.util,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
CFG=json.loads((HERE/'.private.json').read_text())
sp=importlib.util.spec_from_file_location('parent_receiver',OLD/'receiver.py');parent=importlib.util.module_from_spec(sp);sp.loader.exec_module(parent)
def read(n):return json.loads((HERE/n).read_text()) if (HERE/n).exists() else None
def state():
    p=parent.state();job=read('JOB.json');complete=read('COMPLETE.json');stop=read('STOP.json')
    original=p['methods']['SLAD'];s=dict(stage='COMPLETE' if complete else 'STOP' if stop else 'SUBMITTED',job=job,detail=read('SLAD_DETAIL.json'),error=stop,previous_failed_job=original['job'])
    if job:
        r=subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20);s['scheduler']=r.stdout
        if any(x in r.stdout for x in ['FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL']):s['stage']='STOP'
        elif '|RUNNING|' in r.stdout and not complete and not stop:s['stage']='RUNNING'
    p['methods']['SLAD']=s;p['done']=sum(m['stage']=='COMPLETE' for m in p['methods'].values())
    p['stage']='COMPLETE' if p['done']==3 else 'METHOD_STOP' if any(m['stage']=='STOP' for m in p['methods'].values()) else 'FORMAL_RUNNING'
    p['slad_repair']='Evaluation only; all three completed checkpoints reused';return p
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            tok,action=self.path.strip('/').split('/');assert hmac.compare_digest(tok,CFG['token'])
            if action=='state':v=state()
            else:
                assert action=='results';files={}
                for name in ['JOB.json','STOP.json','PIPELINE_RESULT.json','CLEAN_PREDICTOR_GATE.json','EVALUATE_RESULT.json','COMPLETE.json','SLAD_METRICS.json']:
                    q=HERE/name
                    if q.exists():
                        b=q.read_bytes();assert len(b)<4*1024**2;files[name]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
                v=dict(files=files)
            b=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        except Exception as e:self.send_error(409,str(e)[:500])
if __name__=='__main__':
    s=ThreadingHTTPServer(('127.0.0.1',18877),Handler);timer=threading.Timer(96*3600,s.shutdown);timer.daemon=True;timer.start();s.serve_forever()
