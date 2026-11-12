import base64,hashlib,http.client,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];SCIENCE=ROOT/'runs/paper_reading_ablations_v2_20261111'
sp=importlib.util.spec_from_file_location('existing_tunnel',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(sp);sp.loader.exec_module(t)
def request(action):
    cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18881,timeout=90);c.sock=t.connect(cfg,90)
    try:
        c.request('GET','/'+cfg['token']+'/'+action);r=c.getresponse();b=r.read();assert r.status==200,(r.status,b[:100]);return json.loads(b)
    finally:c.close()
def retrieve():
    pins={}
    for name,v in request('results')['files'].items():
        p=Path(name);assert not p.is_absolute() and '..' not in p.parts and '\\' not in name
        assert p.suffix in ['.json','.md','.csv','.txt','.out','.err']
        b=base64.b64decode(v['base64']);assert len(b)<64*1024**2 and hashlib.sha256(b).hexdigest()==v['sha256']
        dest=HERE/'received'/p;dest.parent.mkdir(parents=True,exist_ok=True);temp=dest.with_suffix(dest.suffix+'.tmp');temp.write_bytes(b);temp.replace(dest);pins[name]=v['sha256']
    t.write(HERE/'RETRIEVAL.json',dict(sha256=pins))
def main():
    last_items=None;last_fetch=0
    for _ in range(7*8640):
        try:
            p=request('state');t.write(HERE/'PROGRESS.json',p);t.write(ROOT/'runs/device_context_training_v1_20261105/PROGRESS.json',p)
            flags=tuple(bool(p['items'][n]) for n in ['guard','exponent'])
            if flags!=last_items or time.monotonic()-last_fetch>60 or p['stage'] in ['COMPLETE','STOP']:
                retrieve();last_items=flags;last_fetch=time.monotonic()
            t.write(HERE/'CONNECTION_STATUS.json',dict(status='CONNECTED',updated_unix=time.time()))
            if p['stage'] in ['COMPLETE','STOP']:return
        except (OSError,http.client.HTTPException) as e:t.write(HERE/'CONNECTION_STATUS.json',dict(status='INTERRUPTED',type=type(e).__name__,updated_unix=time.time()))
        time.sleep(10)
if __name__=='__main__':main()
