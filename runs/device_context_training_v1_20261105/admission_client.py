"""Ordinary submission and receipt sync for the bounded source admission job."""
import base64,hashlib,http.client,json,time
import client
H=client.HERE;t=client.t
def request(action,data=None):
 cfg=t.read(H/'.private/admission_connection.json');c=http.client.HTTPConnection('127.0.0.1',18842,timeout=30);c.sock=t.connect(cfg,30)
 try:
  c.request('POST' if data is not None else 'GET','/'+cfg['token']+'/'+action,body=json.dumps(data).encode() if data is not None else None);r=c.getresponse();assert r.status==200,'HTTP_'+str(r.status);return json.loads(r.read())
 finally:c.close()
def main():
 deadline=time.monotonic()+5*3600
 while time.monotonic()<deadline:
  try:
   s=request('state')
   if s['stage']=='WAITING_UPLOAD' and not (H/'ADMISSION_START_INTENT.json').exists():
    cfg=t.read(H/'.private/admission_config.json');request('upload',{n:base64.b64encode((H/n).read_bytes()).decode() for n in cfg['pins']});t.write(H/'ADMISSION_START_INTENT.json',dict(started=True));t.write(H/'ADMISSION_START_RECEIPT.json',request('start',{}))
   t.write(H/'CHAIN_STATE.json',s);p=s.get('ADMISSION_PROGRESS') or {};p.update(stage=p.get('stage',s['stage']),updated_utc=t.utc(),job_id=s.get('job_id'));t.write(H/'PROGRESS.json',p)
   if s['stage'] in ['PASS','STOP']:
    results=request('results');pins={}
    for n,v in results['files'].items():
     assert n in ['ADMISSION_'+k+'.json' for k in ['RESULT','STOP','SCHEDULER','JOB']];b=base64.b64decode(v['base64']);assert hashlib.sha256(b).hexdigest()==v['sha256'];(H/n).write_bytes(b);pins[n]=v['sha256']
    t.write(H/'ADMISSION_RETRIEVAL.json',dict(state=s,sha256=pins));t.write(H/'METADATA_ADMISSION.json',dict(status='PASS' if s['stage']=='PASS' else 'FAIL',error=s.get('error'),next='PER_PACKET_FEATURE_GATE' if s['stage']=='PASS' else 'DIAGNOSE_STOP'));return
  except (OSError,http.client.HTTPException) as e:t.write(H/'CONNECTION_STATUS.json',dict(status='INTERRUPTED',type=type(e).__name__))
  time.sleep(10)
 raise RuntimeError('ADMISSION_OBSERVATION_CAP')
if __name__=='__main__':main()
