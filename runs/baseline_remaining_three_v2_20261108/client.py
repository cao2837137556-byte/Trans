import base64,hashlib,http.client,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sp=importlib.util.spec_from_file_location('transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(sp);sp.loader.exec_module(t)
def request(action):
    cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18879,timeout=90);c.sock=t.connect(cfg,90)
    try:
        c.request('GET','/'+cfg['token']+'/'+action);r=c.getresponse();b=r.read();assert r.status==200;return json.loads(b)
    finally:c.close()
def retrieve():
    pins={}
    for n,v in request('results')['files'].items():
        assert '/' not in n and '\\' not in n and n.endswith('.json');b=base64.b64decode(v['base64']);assert hashlib.sha256(b).hexdigest()==v['sha256'] and len(b)<4*1024**2;(HERE/n).write_bytes(b);pins[n]=v['sha256']
    t.write(HERE/'RETRIEVAL.json',dict(sha256=pins))
def main():
    last=0
    for _ in range(14*8640):
        try:
            p=request('state');t.write(HERE/'PROGRESS.json',p);t.write(ROOT/'runs/device_context_training_v1_20261105/PROGRESS.json',p)
            if time.monotonic()-last>60:retrieve();last=time.monotonic()
            if p['stage']=='COMPLETE':retrieve();return
        except (OSError,http.client.HTTPException) as e:t.write(HERE/'CONNECTION_STATUS.json',dict(status='INTERRUPTED',type=type(e).__name__))
        time.sleep(10)
if __name__=='__main__':main()
