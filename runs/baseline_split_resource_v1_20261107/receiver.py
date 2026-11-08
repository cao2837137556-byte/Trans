"""Private existing-tunnel delivery; fixed files and one bounded sbatch only."""
import base64,hashlib,hmac,json,subprocess,threading,time
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
HERE=Path(__file__).resolve().parent;CONFIG=json.loads((HERE/'.private.json').read_text());LOCK=threading.Lock()
PY='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
PROJECT='/public/home/jiangxinwei.zr/work/paper04'
def read(n):return json.loads((HERE/n).read_text()) if (HERE/n).exists() else None
def write(n,v):
 p=HERE/n;t=p.with_suffix('.tmp');t.write_text(json.dumps(v,indent=2));t.replace(p)
def state():
 p=read('PROGRESS.json') or dict(stage='WAITING_UPLOAD',version='BASELINE_SPLIT_RESOURCE_V1')
 job=read('JOB.json')
 if not job:
  p['asset_bytes']={}
  for name,spec in (read('ASSETS.json') or {}).items():
   target=HERE/'assets'/name;part=HERE/'assets'/(name+'.part')
   if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==spec['sha256']
   p['asset_bytes'][name]=target.stat().st_size if target.exists() else part.stat().st_size if part.exists() else 0
 if job:
  p['job_id']=job['job_id'];r=subprocess.run(['sacct','-j',job['job_id'],'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=15);write('SCHEDULER.json',dict(stdout=r.stdout,returncode=r.returncode))
  if any(x in r.stdout for x in ('FAILED','TIMEOUT','OUT_OF_MEMORY','CANCELLED','NODE_FAIL')) and p['stage']!='STOP':p.update(stage='STOP',error='SCHEDULER_FAILURE: '+r.stdout[:1500])
 return p
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def action(self):
  v=self.path.split('/');assert len(v)==3 and hmac.compare_digest(v[1],CONFIG['token']);return v[2]
 def reply(self,v):
  b=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  try:
   action=self.action()
   if action=='state':return self.reply(state())
   assert action=='results';files={}
   for n in ['RESULT.json','JOB.json','SCHEDULER.json','DEPENDENCY_GATE.json','FORMAL_PLAN_SEALED.json']+[p+'_'+s+'.json' for p in ['ENVIRONMENT', 'FIDELITY', 'PIPELINE', 'SPLIT', 'DTE_EPOCH', 'SLAD_EPOCH', 'TABM_EPOCH', 'RESOURCE_REVIEW'] for s in ['RESULT','STOP']]:
    if (HERE/n).exists():
     b=(HERE/n).read_bytes();assert len(b)<2*1024**2;files[n]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
   return self.reply(dict(files=files))
  except Exception as e:self.send_error(409,str(e)[:400])
 def do_POST(self):
  try:
   action=self.action();n=int(self.headers['Content-Length']);assert 0<=n<8*1024**2;data=json.loads(self.rfile.read(n))
   with LOCK:
    assert not (HERE/'START_INTENT.json').exists(),'ONE_SUBMISSION_ONLY'
    if action=='upload':
     assert set(data)==set(CONFIG['pins'])
     for name,value in data.items():
      b=base64.b64decode(value);assert hashlib.sha256(b).hexdigest()==CONFIG['pins'][name];p=HERE/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
     return self.reply(dict(status='UPLOADED'))
    if action=='asset':
     specs=read('ASSETS.json');name=data['name'];spec=specs[name];folder=HERE/'assets';folder.mkdir(exist_ok=True);part=folder/(name+'.part');target=folder/name
     assert not target.exists();offset=data['offset'];assert type(offset) is int and offset==(part.stat().st_size if part.exists() else 0)
     b=base64.b64decode(data['data']);assert offset+len(b)<=spec['bytes']
     with part.open('ab') as f:f.write(b)
     if part.stat().st_size==spec['bytes']:
      assert hashlib.sha256(part.read_bytes()).hexdigest()==spec['sha256'];part.replace(target)
     return self.reply(dict(received=offset+len(b)))
    assert action=='start'
    for name,spec in read('ASSETS.json').items():
     p=HERE/'assets'/name;assert p.stat().st_size==spec['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==spec['sha256'],'ASSET_GATE'

    from pipeline_parent import dependencies
    checked=dependencies();write('DEPENDENCY_GATE.json',dict(status='PASS',checked=checked))
    env='source '+PROJECT+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+PROJECT+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+PROJECT+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1\n'
    script='#!/bin/bash\n#SBATCH --job-name=baseline-ready\n#SBATCH --partition=amd\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=8192M\n#SBATCH --time=02:00:00\n#SBATCH --no-requeue\n#SBATCH --output='+str(HERE/'job-%j.out')+'\n#SBATCH --error='+str(HERE/'job-%j.err')+'\nset -euo pipefail\numask 077\n'+env+'exec '+PY+' -X utf8 -B '+str(HERE/'controller.py')+'\n'
    (HERE/'job.slurm').write_text(script);write('START_INTENT.json',dict(authorized_scope='SOURCE_FULL_TRAINING_RESOURCE_PREFLIGHT',cpu=1,memory_gib=8,wall_seconds=7200))
    r=subprocess.run(['sbatch','--parsable',str(HERE/'job.slurm')],capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
    job=r.stdout.strip().split(';')[0];assert job.isdigit();write('JOB.json',dict(job_id=job,cpu=1,memory_gib=8,wall_seconds=7200))
    write('PROGRESS.json',dict(stage='SUBMITTED',version='BASELINE_SPLIT_RESOURCE_V1',job_id=job,done=0,total=8,updated_unix=time.time()));return self.reply(read('JOB.json'))
  except Exception as e:self.send_error(409,str(e)[:400])
if __name__=='__main__':
 server=ThreadingHTTPServer(('127.0.0.1',18875),Handler);timer=threading.Timer(36*3600,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
