"""Local progress, ordinary bounded remote synchronization, no AI polling required."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import hashlib,http.client,importlib.util,json,threading,time
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
spec=importlib.util.spec_from_file_location('existing_transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
def request(route):
    config=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18835,timeout=20);c.sock=t.connect(config,20)
    try:
        c.request('GET','/'+config['token']+'/'+route);r=c.getresponse();assert r.status==200,'HTTP_STATUS';return json.loads(r.read())
    finally:c.close()
def sync():
    for iteration in range(3600):
        if (HERE/'.private/connection.json').exists():
            try:
                v=request('state');assert v['receiver_sha256']==t.sha(HERE/'receiver.py'),'RECEIVER_IDENTITY'
                v['observed_utc']=t.utc();t.write(HERE/'REMOTE_STATE.json',v)
                if v['stage'] in ('PASS','STOP'):
                    result=request('results')
                    # JSON is decoded; preserve and verify exact remote file bytes through canonical reserialization separately.
                    for name,item in result.get('files',{}).items():
                        assert name in ('EDGE_DIAGNOSIS.json','EDGE_COMPLETE.json','EDGE_STOP.json','PREFLIGHT_COMPLETE.json')
                        body=json.dumps(item['data'],ensure_ascii=False,allow_nan=False,indent=2).encode()
                        assert hashlib.sha256(body).hexdigest()==item['sha256'],'RESULT_SHA:'+name
                        (HERE/'local'/name).write_bytes(body)
                    t.write(HERE/'REMOTE_RETRIEVAL.json',result)
                    return
            except Exception as e:t.write(HERE/'CONNECTION_STATUS.json',dict(status='WAITING_OR_INTERRUPTED',error=type(e).__name__,utc=t.utc()))
        time.sleep(10)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        if self.path=='/':data=(HERE/'index.html').read_bytes();kind='text/html'
        elif self.path=='/state':
            value={}
            for key,p in [('ab',HERE/'local/AB_PROGRESS.json'),('remote',HERE/'REMOTE_STATE.json'),('connection',HERE/'CONNECTION_STATUS.json')]:
                value[key]=t.read(p) if p.exists() else None
            value['results']={p.stem:t.read(p) for p in (HERE/'local').glob('*DIAGNOSIS.json')}
            data=json.dumps(value).encode();kind='application/json'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',kind+'; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    threading.Thread(target=sync,daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',18801),Handler).serve_forever()
