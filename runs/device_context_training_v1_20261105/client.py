"""Reuse established SOCKS; no SSH or login."""
import hashlib,http.client,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
s=importlib.util.spec_from_file_location('old_transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
def request(route,data=None,headers=None):
 cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18841,timeout=90);c.sock=t.connect(cfg,90)
 try:
  if isinstance(data,dict):data=json.dumps(data).encode()
  c.request('GET' if data is None else 'POST','/'+cfg['token']+'/'+route,body=data,headers=headers or {});r=c.getresponse();assert r.status==200,'HTTP_'+str(r.status);return json.loads(r.read())
 finally:c.close()
if __name__=='__main__':
 state=request('state')
 if state['stage']=='WAITING_PLAN':print(request('plan',t.read(HERE/'ASSET_PLAN.json')))
 else:print(state)
