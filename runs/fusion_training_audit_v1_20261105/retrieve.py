import hashlib,http.client,importlib.util,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
s=importlib.util.spec_from_file_location('transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18849,timeout=30);c.sock=t.connect(cfg,30)
try:
 c.request('GET','/'+cfg['token']+'/result');r=c.getresponse();assert r.status==200
 b=r.read(16*1024**2+1);assert len(b)<=16*1024**2
 data=json.loads(b);assert data['status']=='PASS' and len(data['heads'])==9
 assert data['training_jobs']==0 and data['external_data_read'] is False
 (HERE/'RESULT.json').write_bytes(b)
 t.write(HERE/'RETRIEVAL.json',dict(status='PASS',sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),updated_utc=t.utc()))
 print(json.dumps(dict(heads=len(data['heads']),bytes=len(b),seconds=data['seconds'])))
finally:c.close()
