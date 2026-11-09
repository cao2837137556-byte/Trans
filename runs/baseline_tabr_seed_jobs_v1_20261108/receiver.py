import base64,hashlib,hmac,json,importlib.util,subprocess,time,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
HERE=Path(__file__).resolve().parent
sp=importlib.util.spec_from_file_location('six_parent',HERE.parent/'baseline_remaining_three_v2_20261108/receiver.py');parent=importlib.util.module_from_spec(sp);sp.loader.exec_module(parent)
# Reuse only authenticated HTTP machinery; bind its files/token to this run.
old_state=parent.state
CFG=json.loads((HERE/'.private.json').read_text())
def read(n):return json.loads((HERE/n).read_text()) if (HERE/n).exists() else None
def state():
    p=old_state()
    jobs={};stop=read('prepare_STOP.json');done=read('TabR_COMPLETE.json')
    for name in ['seed-27','seed-127','seed-227','evaluate']:
        j=read(name+'_JOB.json');err=read(name+'_STOP.json');s=parent.scheduler(j) if j else ''
        if err:stop=err
        if any(v in s for v in ['FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY','NODE_FAIL']):stop=stop or dict(error=name+': '+s)
        jobs[name]=dict(job=j,scheduler=s,detail=read(name+'_DETAIL.json'),complete=read(name+'_COMPLETE.json'))
    active=next((v for v in jobs.values() if '|RUNNING|' in v['scheduler']),None)
    detail=(active or {}).get('detail') or read('prepare_DETAIL.json')
    p['methods']['TabR']=dict(stage='COMPLETE' if done else 'STOP' if stop else 'TRAINING_OR_EVALUATING' if active else 'SUBMITTED',job=read('seed-27_JOB.json') or read('JOB.json'),detail=detail,error=stop,subjobs=jobs,previous_failed_job='182807')
    p['done']=sum(v['stage']=='COMPLETE' for v in p['methods'].values());p['stage']='COMPLETE' if p['done']==6 else 'METHOD_STOP' if any(v['stage']=='STOP' for v in p['methods'].values()) else 'FORMAL_RUNNING';p['updated_unix']=time.time();return p
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
    s=ThreadingHTTPServer(('127.0.0.1',18880),Handler);timer=threading.Timer(28*86400,s.shutdown);timer.daemon=True;timer.start();s.serve_forever()
