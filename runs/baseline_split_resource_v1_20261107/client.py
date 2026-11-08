"""Existing SOCKS transport; summaries only, never retrieve models/arrays."""
import base64,hashlib,http.client,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DISPLAY=ROOT/'runs/device_context_training_v1_20261105'
s=importlib.util.spec_from_file_location('old_transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
def request(action,data=None):
 cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18875,timeout=60);c.sock=t.connect(cfg,60)
 try:
  c.request('POST' if data is not None else 'GET','/'+cfg['token']+'/'+action,body=json.dumps(data).encode() if data is not None else None);r=c.getresponse();b=r.read();assert r.status==200,'HTTP_'+str(r.status)+':'+b.decode(errors='replace')[-700:];return json.loads(b)
 finally:c.close()
def retrieve():
 r=request('results');pins={}
 for n,v in r['files'].items():
  assert '/' not in n and '\\' not in n and n.endswith('.json');b=base64.b64decode(v['base64']);assert len(b)<2*1024**2 and hashlib.sha256(b).hexdigest()==v['sha256'];(HERE/n).write_bytes(b);pins[n]=v['sha256']
 t.write(HERE/'RETRIEVAL.json',dict(sha256=pins))
def main():
 until=time.monotonic()+36*3600
 while time.monotonic()<until:
  try:
   p=request('state')
   if p['stage']=='WAITING_UPLOAD' and not (HERE/'START_INTENT.json').exists():
    pins=t.read(HERE/'.private/config.json')['pins'];request('upload',{n:base64.b64encode((HERE/n).read_bytes()).decode() for n in pins})
    for name,spec in t.read(HERE/'ASSETS.json').items():
     asset=HERE/'.private'/name;assert asset.stat().st_size==spec['bytes'] and hashlib.sha256(asset.read_bytes()).hexdigest()==spec['sha256'];offset=request('state').get('asset_bytes',{}).get(name,0);assert 0<=offset<=spec['bytes']
     with asset.open('rb') as f:
      f.seek(offset)
      for b in iter(lambda:f.read(2*1024**2),b''):
       r=request('asset',dict(name=name,offset=offset,data=base64.b64encode(b).decode()));offset+=len(b);assert r['received']==offset
       up=dict(version='BASELINE_SPLIT_RESOURCE_V1',stage='UPLOADING',detail=name+' '+str(round(offset/1024**2,1))+'/'+str(round(spec['bytes']/1024**2,1))+' MiB',done=0,total=8,updated_unix=time.time());t.write(HERE/'PROGRESS.json',up);t.write(DISPLAY/'PROGRESS.json',up)
    t.write(HERE/'START_INTENT.json',dict(authorized=True));t.write(HERE/'JOB.json',request('start',{}));p=request('state')
   t.write(HERE/'PROGRESS.json',p);t.write(DISPLAY/'PROGRESS.json',p)
   if p['stage'] in ('COMPLETE','STOP'):retrieve();return
  except (OSError,http.client.HTTPException) as e:t.write(HERE/'CONNECTION_STATUS.json',dict(status='INTERRUPTED',type=type(e).__name__))
  except Exception as e:
   error=dict(version='BASELINE_SPLIT_RESOURCE_V1',stage='STOP',error=type(e).__name__+':'+str(e)[:700],updated_unix=time.time());t.write(HERE/'PROGRESS.json',error);t.write(DISPLAY/'PROGRESS.json',error);raise
  time.sleep(10)
 raise RuntimeError('OBSERVATION_CAP')
if __name__=='__main__':main()
