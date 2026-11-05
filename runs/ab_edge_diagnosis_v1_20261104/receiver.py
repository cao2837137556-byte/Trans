"""Private loopback endpoint for this one existing-artifact diagnostic job only."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import hashlib,hmac,json,os,subprocess,threading,time
HERE=Path(__file__).resolve().parent
PYTHON='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
PROJECT='/public/home/jiangxinwei.zr/work/paper04'
SOURCE=PROJECT+'/runs/edge_formal_evaluation_resume_v2_20261104/outputs/gate_182089'
CHECKOUT=PROJECT+'/runs/edge_formal_evaluation_resume_v2_20261104/checkout'
def read(p):return json.loads(Path(p).read_text())
def write(p,d):
    p=Path(p);t=p.with_suffix('.tmp');t.write_text(json.dumps(d));t.replace(p)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def maybe(p):return read(p) if Path(p).exists() else None
CONFIG=read(HERE/'.private.json')
for name,digest in CONFIG['pins'].items():assert sha(HERE/name)==digest,'DELIVERY_PIN:'+name
ENV=('source '+PROJECT+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+PROJECT+
    '/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+PROJECT+
    '/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1\n')
COMMAND=PYTHON+' -X utf8 -B '+str(HERE/'diagnose.py')+' --root '+CHECKOUT+' --source '+SOURCE+' --out '+str(HERE/'outputs')
def launch():
    try:
        if (HERE/'SUBMIT_RECEIPT.json').exists():return
        assert not (HERE/'SUBMIT_INTENT.json').exists(),'SUBMISSION_OUTCOME_UNKNOWN_NO_RETRY'
        write(HERE/'STATE.json',dict(stage='REAL_RESULT_PREFLIGHT',message='核验真实已存编码与128条结果切片'))
        with (HERE/'preflight.log').open('ab') as log:
            result=subprocess.run(['bash','-c',ENV+'exec '+COMMAND+' --mode preflight'],stdout=log,stderr=log,timeout=180)
        assert result.returncode==0 and read(HERE/'outputs/PREFLIGHT_COMPLETE.json')['status']=='PASS','REAL_SLICE_PREFLIGHT_FAILED'
        script='#!/usr/bin/env bash\n#SBATCH --job-name=ab-edge-audit\n#SBATCH --nodes=1\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=8192M\n#SBATCH --time=01:00:00\n#SBATCH --no-requeue\n#SBATCH --output='+str(HERE/'audit-%j.out')+'\n#SBATCH --error='+str(HERE/'audit-%j.err')+'\nset -euo pipefail\numask 077\n'+ENV+'exec '+COMMAND+' --mode edge\n'
        (HERE/'diagnostic.slurm').write_text(script)
        write(HERE/'SUBMIT_INTENT.json',dict(stage='INTENT',allowed_jobs=1,cpu=1,memory_gib=8,wall_seconds=3600))
        result=subprocess.run(['sbatch','--parsable','--partition=amd',str(HERE/'diagnostic.slurm')],capture_output=True,text=True,timeout=30)
        assert result.returncode==0,'SBATCH_FAILED:'+result.stderr[-1500:]
        job=result.stdout.strip().split(';')[0];assert job.isdigit()
        write(HERE/'SUBMIT_RECEIPT.json',dict(job_id=job,cpu=1,memory_gib=8,wall_seconds=3600,automatic_retry=False,source_writes=0))
        write(HERE/'STATE.json',dict(stage='SUBMITTED',job_id=job))
    except Exception as e:write(HERE/'STATE.json',dict(stage='STOP',error=repr(e)))
def state():
    v=maybe(HERE/'STATE.json') or dict(stage='STARTING');v['job']=maybe(HERE/'SUBMIT_RECEIPT.json')
    v['preflight']=maybe(HERE/'outputs/PREFLIGHT_COMPLETE.json');v['progress']=maybe(HERE/'outputs/EDGE_PROGRESS.json')
    v['complete']=maybe(HERE/'outputs/EDGE_COMPLETE.json');v['stop']=maybe(HERE/'outputs/EDGE_STOP.json')
    if v['job']:
        j=v['job']['job_id'];cp=subprocess.run(['sacct','-j',j,'-n','-P','--format=JobID,State,ExitCode,Elapsed,MaxRSS,AllocCPUS,ReqMem'],capture_output=True,text=True,timeout=10)
        v['scheduler']=dict(stdout=cp.stdout,returncode=cp.returncode)
        if cp.returncode==0 and (j+'|COMPLETED|0:0|') in cp.stdout and v['complete']:v['stage']='PASS'
        elif v['stop'] or any(x in cp.stdout for x in ('FAILED','TIMEOUT','CANCELLED','OUT_OF_MEMORY')):v['stage']='STOP'
        elif '|RUNNING|' in cp.stdout:v['stage']='RUNNING'
    v['receiver_sha256']=sha(__file__);return v
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        try:
            parts=self.path.split('/');assert len(parts)==3 and hmac.compare_digest(parts[1],CONFIG['token'])
            if parts[2]=='state':v=state()
            elif parts[2]=='results':
                v={'state':state(),'files':{}}
                names=['EDGE_DIAGNOSIS.json','EDGE_COMPLETE.json','EDGE_STOP.json','PREFLIGHT_COMPLETE.json']
                for name in names:
                    p=HERE/'outputs'/name
                    if p.exists():assert p.stat().st_size<4*1024**2;v['files'][name]=dict(sha256=sha(p),data=read(p))
                for name in ('preflight.log',):
                    p=HERE/name
                    if p.exists():v[name]=p.read_text(errors='replace')[-5000:]
                p=HERE/'outputs/EDGE_INPUT_SHA.json'
                if p.exists():v['hpc_input_manifest']=dict(path=str(p),sha256=sha(p),files=len(read(p)['files']))
            else:raise ValueError('UNKNOWN_ROUTE')
            data=json.dumps(v).encode();self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        except Exception as e:
            data=json.dumps(dict(error=type(e).__name__)).encode();self.send_response(409);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    server=ThreadingHTTPServer(('127.0.0.1',18835),Handler)
    threading.Thread(target=launch,daemon=True).start()
    timer=threading.Timer(8*3600,server.shutdown);timer.daemon=True;timer.start()
    server.serve_forever()
