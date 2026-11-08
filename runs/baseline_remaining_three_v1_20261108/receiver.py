import base64,hashlib,hmac,importlib.util,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'baseline_slad_eval_repair_v1_20261108'
CFG=json.loads((HERE/'.private.json').read_text())
sp=importlib.util.spec_from_file_location('repaired_parent_receiver',OLD/'receiver.py');parent=importlib.util.module_from_spec(sp);sp.loader.exec_module(parent)
def read(n):return json.loads((HERE/n).read_text()) if (HERE/n).exists() else None
def scheduler(j):
    return subprocess.run(['sacct','-j',j['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=20).stdout
def state():
    p=parent.state();p.update(total=6,version='BASELINE_SIX_V1',updated_unix=time.time(),pending_methods={},removed=['ModernNCA'],preflight_job=read('JOB.json'))
    p['detail']=read('PREFLIGHT_DETAIL.json');p['preflight_error']=read('PREFLIGHT_STOP.json')
    if p['preflight_job']:p['preflight_scheduler']=scheduler(p['preflight_job'])
    for name in ['TabM','TabR','DisentAD']:
        j=read(name+'_JOB.json');done=read(name+'_COMPLETE.json');stop=read(name+'_STOP.json')
        s=dict(stage='COMPLETE' if done else 'STOP' if stop else 'SUBMITTED' if j else 'WAITING_GATE',job=j,detail=read(name+'_DETAIL.json'),error=stop or read(name+'_ERROR.json'),qualification=read(name+'_QUALIFY.json'),release=read(name+'_RELEASE.json'))
        if j:
            s['scheduler']=scheduler(j)
            if any(k in s['scheduler'] for k in ['FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL']):s['stage']='STOP'
            elif '|RUNNING|' in s['scheduler'] and not done and not stop:s['stage']='TRAINING_OR_EVALUATING' if s['release'] else 'RESOURCE_CHECK'
        p['methods'][name]=s
    p['done']=sum(m['stage']=='COMPLETE' for m in p['methods'].values())
    p['stage']='COMPLETE' if p['done']==6 else 'METHOD_STOP' if p['preflight_error'] or any(m['stage']=='STOP' for m in p['methods'].values()) else 'FORMAL_RUNNING'
    return p
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        try:
            tok,action=self.path.strip('/').split('/');assert hmac.compare_digest(tok,CFG['token'])
            if action=='state':v=state()
            else:
                assert action=='results';files={}
                for q in HERE.glob('*.json'):
                    if q.name.startswith('.') or q.name in ['CONFIG.json','CAL_ROWS.json','PARENT_PINS.json']:continue
                    b=q.read_bytes();assert len(b)<4*1024**2;files[q.name]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
                v=dict(files=files)
            b=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
        except Exception as e:self.send_error(409,str(e)[:500])
if __name__=='__main__':
    s=ThreadingHTTPServer(('127.0.0.1',18878),Handler);timer=threading.Timer(14*86400,s.shutdown);timer.daemon=True;timer.start();s.serve_forever()
