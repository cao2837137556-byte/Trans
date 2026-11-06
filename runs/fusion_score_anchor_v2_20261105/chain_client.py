"""Bounded ordinary submission/monitor/retrieval, current dashboard stays at 18806."""
import base64,hashlib,http.client,importlib.util,json,time
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DISPLAY=ROOT/'runs/device_context_training_v1_20261105'
s=importlib.util.spec_from_file_location('old_transport',ROOT/'runs/edge_linux_preflight_deployment_v1_20261103/client.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
PHASES=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','TRAIN_27','TRAIN_127','TRAIN_227','CALIBRATION']
def request(action,data=None):
 cfg=t.read(HERE/'.private/connection.json');c=http.client.HTTPConnection('127.0.0.1',18851,timeout=30);c.sock=t.connect(cfg,30)
 try:
  c.request('POST' if data is not None else 'GET','/'+cfg['token']+'/'+action,body=json.dumps(data).encode() if data is not None else None);r=c.getresponse();assert r.status==200,'HTTP_'+str(r.status);return json.loads(r.read())
 finally:c.close()
def main():
 deadline=time.monotonic()+36*3600
 while time.monotonic()<deadline:
  try:
   state=request('state')
   if state['stage']=='WAITING_UPLOAD' and not (HERE/'START_INTENT.json').exists():
    cfg=t.read(HERE/'.private/config.json');request('upload',{n:base64.b64encode((HERE/n).read_bytes()).decode() for n in cfg['pins']});t.write(HERE/'START_INTENT.json',dict(started=True));t.write(HERE/'START_RECEIPT.json',request('start',{}))
   t.write(HERE/'CHAIN_STATE.json',state);t.write(DISPLAY/'CHAIN_STATE.json',state);phase=state.get('phase','DECODE_PREFLIGHT');p=state.get(phase+'_PROGRESS') or {};p.update(stage=p.get('stage',state['stage']),updated_utc=t.utc(),phase=phase,job_id=state.get('job_id'),version='ANCHOR_V2',completed_phases=state.get('completed_phases',0),total_phases=6)
   if state['stage'] in ['STOP','ANCHOR_TRAINING_COMPLETE']:p.update(stage=state['stage'],error=state.get('error'))
   t.write(HERE/'PROGRESS.json',p);t.write(DISPLAY/'PROGRESS.json',p)
   if state['stage'] in ['ANCHOR_TRAINING_COMPLETE','STOP']:
    r=request('results');pins={};allowed=[ph+'_'+k+'.json' for ph in PHASES for k in ['RESULT','STOP','SCHEDULER','JOB']]+['RUNTIME_FORECAST.json','LINUX_REGRESSION.json','LINUX_THREAD_REGRESSION.json']
    for name,v in r['files'].items():
     assert name in allowed;b=base64.b64decode(v['base64']);assert hashlib.sha256(b).hexdigest()==v['sha256'];(HERE/name).write_bytes(b);pins[name]=v['sha256']
    t.write(HERE/'RETRIEVAL.json',dict(state=state,sha256=pins))
    if state['stage']=='ANCHOR_TRAINING_COMPLETE':
     heads=[t.read(HERE/(ph+'_RESULT.json')) for ph in ['TRAIN_27','TRAIN_127','TRAIN_227']]
     assert all(h['updates']==96560 and h['epoch_checkpoints']==40 for h in heads)
     assert t.read(HERE/'CALIBRATION_RESULT.json')['ensemble']['weighted_normal_fpr']<=.01+1e-14
     t.write(HERE/'TRAINING_COMPLETION.json',dict(status='PASS',scope='TRAINING_AND_SOURCE_CAL_ONLY',new_heads=3,updates=289680,evaluation_pending=True,receipt_sha256=pins))
    return
  except (OSError,http.client.HTTPException) as e:t.write(HERE/'CONNECTION_STATUS.json',dict(status='INTERRUPTED',type=type(e).__name__))
  time.sleep(10)
 raise RuntimeError('CHAIN_OBSERVATION_CAP')
if __name__=='__main__':main()
