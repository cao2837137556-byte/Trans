"""Ordinary bounded transport/progress; never creates SSH or authenticates."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import base64,hashlib,http.client,importlib.util,json,threading,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
def request(action,data=None):
    config=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18840,timeout=30);c.sock=t.connect(config,30)
    try:
        b=json.dumps(data).encode() if data is not None else None
        c.request('POST' if b is not None else 'GET','/'+config['token']+'/'+action,body=b,headers={'Content-Type':'application/json'})
        r=c.getresponse();assert r.status==200,'HTTP_'+str(r.status);return json.loads(r.read())
    finally:c.close()
def sync():
    deadline=time.monotonic()+12*3600
    while time.monotonic()<deadline:
        try:
            state=request('state')
            if state['stage']=='WAITING_UPLOAD' and not (HERE/'START_INTENT.json').exists():
                config=t.read(HERE/'.private/config.json')
                payload={name:base64.b64encode((HERE/('.private/AB_SAMPLES.json.gz' if name=='AB_SAMPLES.json.gz' else name)).read_bytes()).decode() for name in config['pins']}
                upload=request('upload',payload);t.write(HERE/'UPLOAD.json',upload)
                t.write(HERE/'START_INTENT.json',dict(status='START_REQUESTED_NO_AUTOMATIC_RETRY'))
                t.write(HERE/'START_RECEIPT.json',request('start',{}))
                state=request('state')
            state['observed_utc']=t.utc();t.write(HERE/'REMOTE_STATE.json',state);t.write(HERE/'CONNECTION.json',dict(status='CONNECTED',utc=t.utc()))
            if state['stage'] in ['PASS','STOP']:
                r=request('results');pins={}
                for name,item in r['files'].items():
                    assert name in [phase+'_'+kind+'.json' for phase in ['PREFLIGHT','FULL'] for kind in ['RESULT','STOP','SCHEDULER','JOB']] + ['TRAINING_SPEC_FROZEN.json','TRAINING_FREEZE_RECEIPT.json']
                    b=base64.b64decode(item['base64']);assert hashlib.sha256(b).hexdigest()==item['sha256'];(HERE/name).write_bytes(b);pins[name]=item['sha256']
                t.write(HERE/'RETRIEVAL.json',dict(state=r['state'],sha256=pins))
                if r['state']['stage']=='PASS':
                    from accept_results import accept
                    try:accept()
                    except Exception as e:t.write(HERE/'ARTIFACT_ACCEPTANCE.json',dict(status='FAIL',error=repr(e)))
                return
        except Exception as e:t.write(HERE/'CONNECTION.json',dict(status='WAITING_OR_INTERRUPTED',error=type(e).__name__,utc=t.utc()))
        time.sleep(10)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=='/':data=(HERE/'index.html').read_bytes();kind='text/html'
        elif self.path=='/state':
            d={n[:-5]:t.read(HERE/n) if (HERE/n).exists() else None for n in ['REMOTE_STATE.json','PREFLIGHT_RESULT.json','FULL_RESULT.json','CONNECTION.json','ARTIFACT_ACCEPTANCE.json','TRAINING_FREEZE_RECEIPT.json']}
            data=json.dumps(d).encode();kind='application/json'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    threading.Thread(target=sync,daemon=True).start();ThreadingHTTPServer(('127.0.0.1',18805),Handler).serve_forever()
