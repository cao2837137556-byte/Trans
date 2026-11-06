"""One authorized bounded preflight/full context chain on existing HPC login."""
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import base64,hashlib,hmac,json,subprocess,threading,time
HERE=Path(__file__).resolve().parent;CONFIG=json.loads((HERE/'.private.json').read_text())
PHASES=['PREFLIGHT','CONTRIBUTION','GRADIENT']
PY='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
PROJECT='/public/home/jiangxinwei.zr/work/paper04'
ENV=('source '+PROJECT+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+PROJECT+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+PROJECT+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1\n')
def write(name,value):
    p=HERE/name;t=p.with_suffix('.tmp');t.write_text(json.dumps(value));t.replace(p)
def read(name):
    p=HERE/name;return json.loads(p.read_text()) if p.exists() else None
def run(phase,minutes):
    for name,expected in CONFIG['pins'].items():assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==expected,'SOURCE_PIN:'+name
    script=('#!/bin/bash\n#SBATCH --job-name=context-diag\n#SBATCH --partition=amd\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=8192M\n#SBATCH --time=%02d:%02d:00\n' % (minutes//60, minutes%60))
    script+='#SBATCH --no-requeue\n#SBATCH --output='+str(HERE/(phase+'-%j.out'))+'\n#SBATCH --error='+str(HERE/(phase+'-%j.err'))+'\nset -euo pipefail\numask 077\n'+ENV+'exec '+PY+' -X utf8 -B '+str(HERE/'worker.py')+' --phase '+phase+'\n'
    path=HERE/(phase+'.slurm');path.write_text(script)
    assert not (HERE/(phase+'_INTENT.json')).exists(),'NO_RETRY_INTENT'
    write(phase+'_INTENT.json',dict(phase=phase,cpu=1,memory_gib=8,wall_seconds=minutes*60))
    cp=subprocess.run(['sbatch','--parsable',str(path)],capture_output=True,text=True,timeout=30)
    assert cp.returncode==0,'SBATCH:'+cp.stderr[-1000:]
    job=cp.stdout.strip().split(';')[0];assert job.isdigit()
    write(phase+'_JOB.json',dict(job_id=job,phase=phase,cpu=1,memory_gib=8,wall_seconds=minutes*60))
    write('STATE.json',dict(stage=phase+'_SUBMITTED',job_id=job,phase=phase))
    until=time.monotonic()+5*3600
    while time.monotonic()<until:
        cp=subprocess.run(['sacct','-j',job,'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=15)
        write(phase+'_SCHEDULER.json',dict(stdout=cp.stdout,returncode=cp.returncode))
        stop=read(phase+'_STOP.json')
        if stop:raise RuntimeError(phase+':'+stop['error'])
        if any(v in cp.stdout for v in ['FAILED','CANCELLED','TIMEOUT','OUT_OF_MEMORY','NODE_FAIL','PREEMPTED','BOOT_FAIL','DEADLINE']):raise RuntimeError(phase+':SCHEDULER_FAILURE')
        if job+'|COMPLETED|0:0|' in cp.stdout:
            assert read(phase+'_RESULT.json')['status']=='PASS',phase+'_RESULT_NOT_PASS';return
        if '|RUNNING|' in cp.stdout:write('STATE.json',dict(stage=phase+'_RUNNING',job_id=job,phase=phase))
        time.sleep(10)
    raise RuntimeError('BOUNDED_RECEIVER_OBSERVATION_EXPIRED')
def launch():
    try:
        
        for phase in PHASES:run(phase,60 if phase=='GRADIENT' else 30)
        write('STATE.json',dict(stage='CONTEXT_ANCHOR_DIAGNOSIS_COMPLETE',phase='GRADIENT'))
    except Exception as e:write('STATE.json',dict(stage='STOP',error=str(e)))
def state():
    d=read('STATE.json') or dict(stage='WAITING_UPLOAD')
    d['completed_phases']=sum(bool(read(phase+'_RESULT.json')) for phase in PHASES)
    d['total_phases']=3
    d['runtime_forecast']=read('RUNTIME_FORECAST.json')
    for phase in PHASES:
        for kind in ['JOB','PROGRESS','SCHEDULER','STOP']:d[phase+'_'+kind]=read(phase+'_'+kind+'.json')
    return d
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def auth(self):
        pieces=self.path.split('/');assert len(pieces)==3 and hmac.compare_digest(pieces[1],CONFIG['token']);return pieces[2]
    def reply(self,value):
        b=json.dumps(value).encode();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
    def do_GET(self):
        try:
            action=self.auth()
            if action=='state':return self.reply(state())
            assert action=='results';out={}
            for name in [phase+'_'+name+'.json' for phase in PHASES for name in ['RESULT','STOP','SCHEDULER','JOB']]:
                p=HERE/name
                if p.exists():
                    b=p.read_bytes();assert len(b)<8*1024**2;out[name]=dict(base64=base64.b64encode(b).decode(),sha256=hashlib.sha256(b).hexdigest())
            return self.reply(dict(state=state(),files=out))
        except Exception as e:self.send_error(409,type(e).__name__)
    def do_POST(self):
        try:
            action=self.auth();n=int(self.headers['Content-Length']);assert 0<=n<8*1024**2
            data=json.loads(self.rfile.read(n))
            if action=='upload':
                assert not (HERE/'STARTED.json').exists()
                assert set(data)==set(CONFIG['pins'])
                for name,value in data.items():
                    b=base64.b64decode(value);assert hashlib.sha256(b).hexdigest()==CONFIG['pins'][name];(HERE/name).write_bytes(b)
                return self.reply(dict(status='UPLOADED'))
            assert action=='start' and not (HERE/'STARTED.json').exists()
            write('STARTED.json',dict(authorized=True,automatic_retries=0))
            threading.Thread(target=launch,daemon=True).start();return self.reply(dict(status='STARTED'))
        except Exception as e:self.send_error(409,type(e).__name__)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',18853),Handler)
    timer=threading.Timer(36*3600,server.shutdown);timer.daemon=True;timer.start();server.serve_forever()
