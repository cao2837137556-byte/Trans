"""Loopback-only C4 transfer and one fixed Slurm submission over existing SSH."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import tarfile
import threading
import time

ROOT=Path('/public/home/jiangxinwei.zr/work/paper04')
PACKAGE=ROOT/'runs/history_sample_coverage_c4_execution_v1_20261101'
DEPLOY=ROOT/'runs/history_sample_coverage_c4_deployment_repair_v1_20261101'
PYTHON='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
ENVFILE=ROOT/'frontend_compat_v1/environment.sh'

def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
    return h.hexdigest()
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p,v):
    q=p.with_name(p.name+'.tmp');q.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');q.replace(p)

def validate_archive(archive,expected):
    members=archive.getmembers();need(len(members)==len(expected) and {m.name for m in members}==set(expected),'EXACT_ARCHIVE_MEMBERS')
    for m in members:
        p=Path(m.name);need(m.isfile() and not p.is_absolute() and '..' not in p.parts and '\\' not in m.name,'ARCHIVE_PATH')
        f=archive.extractfile(m);h=hashlib.sha256();count=0
        for b in iter(lambda:f.read(4*1024**2),b''):count+=len(b);h.update(b)
        need(count==expected[m.name]['bytes'] and h.hexdigest()==expected[m.name]['sha256'],'ARCHIVE_MEMBER_PIN')
    return members

def main(config):
    DEPLOY.mkdir(parents=True,exist_ok=True)
    need(len(config['token'])==48 and not (DEPLOY/'STATE.json').exists(),'NEW_RECEIVER_STATE')
    repair_receipt=repair_configuration(config['repair'])
    state=dict(status='INSTALLED',submitted=False,candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',repair=repair_receipt);lock=threading.Lock()
    assets=config['assets'];need(len(assets)==3,'NETATMO_RAW_AND_TWO_INDICES_ONLY')
    for item in assets:
        p=(ROOT/item['remote_relative']).resolve();need(p.is_relative_to(ROOT/'data_external/unsw_iotraffic_2025'),'ASSET_SCOPE')
    def save():write(DEPLOY/'STATE.json',state)
    def transfer_path(index):
        if index=='code':return ROOT/'runs/history_sample_coverage_c4_deployment_20261101/bundle.tar',config['bundle']
        need(index.isdigit() and 0<=int(index)<len(assets),'ASSET_INDEX')
        s=assets[int(index)];return ROOT/s['remote_relative'],s
    def offsets():
        result={}
        for index in ['code',*[str(i) for i in range(len(assets))]]:
            p,s=transfer_path(index);part=p.with_name(p.name+'.c4part')
            result[index]=dict(complete=p.exists(),offset=p.stat().st_size if p.exists() else part.stat().st_size if part.exists() else 0,total=s['bytes'])
        return result
    def run_python(code,timeout=300):
        script='source '+shlex.quote(str(ENVFILE))+'\nexport PYTHONPATH='+shlex.quote(str(ROOT/'runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201')+':'+str(ROOT/'environment/vendor_py311_v1'))+':"${PYTHONPATH:-}"\nexport OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 NUMEXPR_NUM_THREADS=4 PYTHONUTF8=1 HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1\ncd '+shlex.quote(str(PACKAGE))+'\n'+shlex.quote(PYTHON)+' -B -c '+shlex.quote(code)
        return subprocess.run(['bash','-lc',script],capture_output=True,text=True,timeout=timeout)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def route(self):
            prefix='/'+config['token']+'/';need(self.path.startswith(prefix),'TOKEN_ROUTE');return self.path[len(prefix):]
        def send(self,v,status=200):
            b=json.dumps(v,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Length',str(len(b)));self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b)
        def do_GET(self):
            try:
                route=self.route()
                if route=='state':
                    result=dict(state,transfers=offsets(),free_bytes=shutil.disk_usage(ROOT).free)
                    for filename in ('STATUS.json','RESULT.json','STAGE_RECEIPT.json'):
                        p=PACKAGE/'outputs/encoding'/filename
                        if p.exists():result[filename]=read(p)
                    if state.get('job_id'):
                        job=state['job_id']
                        ran=subprocess.run(['squeue','-h','-j',job,'-o','%T|%R|%M'],capture_output=True,text=True,timeout=15)
                        result['squeue']=ran.stdout.strip()
                        if not ran.stdout.strip():
                            ran=subprocess.run(['sacct','-n','-X','-j',job,'--format=JobID,State,ExitCode','-P'],capture_output=True,text=True,timeout=15)
                            result['sacct']=ran.stdout.strip()
                        log=PACKAGE/('SLURM-'+job+'.log')
                        if log.exists():
                            with log.open('rb') as f:
                                f.seek(max(0,log.stat().st_size-6000));result['log_tail']=f.read().decode(errors='replace')
                    self.send(result);return
                if route=='result':
                    source=PACKAGE/'outputs/encoding';receipt=read(source/'STAGE_RECEIPT.json')
                    need(receipt['technical_status']=='COMPLETED','ENCODING_NOT_COMPLETED')
                    target=DEPLOY/'result.tar'
                    if not target.exists():
                        with tarfile.open(target.with_suffix('.part'),'w') as archive:
                            for p in sorted(source.rglob('*')):
                                if p.is_file():
                                    need(not p.is_symlink(),'RESULT_LINK');archive.add(p,arcname=p.relative_to(source).as_posix(),recursive=False)
                        target.with_suffix('.part').rename(target)
                    need(target.stat().st_size<2*2**30,'RESULT_SIZE')
                    self.send_response(200);self.send_header('Content-Length',str(target.stat().st_size));self.send_header('X-Content-SHA256',sha(target));self.end_headers()
                    with target.open('rb') as f:
                        for b in iter(lambda:f.read(4*1024**2),b''):self.wfile.write(b)
                    return
                self.send(dict(error='UNKNOWN_ROUTE'),404)
            except Exception as e:self.send(dict(error=str(e)),409)
        def do_POST(self):
            try:
                route=self.route()
                with lock:
                    if route.startswith('upload/'):
                        index=route.split('/')[1];p,s=transfer_path(index);part=p.with_name(p.name+'.c4part')
                        n=int(self.headers.get('Content-Length','-1'));offset=int(self.headers.get('X-Offset','-1'))
                        need(0<n<=16*2**20 and not p.exists(),'UPLOAD_SIZE_OR_EXISTS')
                        need(offset==(part.stat().st_size if part.exists() else 0) and offset+n<=s['bytes'],'UPLOAD_OFFSET')
                        p.parent.mkdir(parents=True,exist_ok=True)
                        data=self.rfile.read(n);need(len(data)==n and hashlib.sha256(data).hexdigest()==self.headers.get('X-Chunk-SHA256'),'CHUNK_PIN')
                        with part.open('ab') as f:f.write(data)
                        if offset+n==s['bytes']:
                            need(sha(part)==s['sha256'],'COMPLETE_ASSET_SHA');part.rename(p)
                        self.send(dict(offset=offset+n,complete=p.exists()));return
                    need(int(self.headers.get('Content-Length','0'))==0,'ACTION_BODY_FORBIDDEN')
                    if route=='install':
                        need(state['status']=='READY' and not PACKAGE.exists(),'NEW_PACKAGE_REQUIRED')
                        for index in ['code',*[str(i) for i in range(3)]]:
                            p,s=transfer_path(index);need(p.stat().st_size==s['bytes'] and sha(p)==s['sha256'],'ASSET_FINAL_PIN')
                        with tarfile.open(DEPLOY/'bundle.tar','r:') as archive:
                            members=validate_archive(archive,config['files']);PACKAGE.mkdir(exist_ok=False)
                            for m in members:
                                p=PACKAGE/m.name;p.parent.mkdir(parents=True,exist_ok=True)
                                with p.open('xb') as f:
                                    source=archive.extractfile(m)
                                    for b in iter(lambda:source.read(4*1024**2),b''):f.write(b)
                        state['status']='INSTALLED';save();self.send(state);return
                    if route=='preflight':
                        need(state['status']=='INSTALLED','PREFLIGHT_ORDER')
                        need(sha(ENVFILE)=='8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf','ENV_PIN')
                        need(sha(ROOT/'runs/history_normal_reference_keyrepair_v1_20261031/config/EXECUTION.json')=='b2c80539fa91008191cecb1fa81899e0ce49e3a3f0c764a05d98677b7bed7c3d','PRIOR_HPC_CONFIG')
                        code="import platform,json,unittest; import numpy as np,torch; observed=dict(python=platform.python_version(),numpy=np.__version__,torch=str(torch.__version__).split('+')[0]); print(json.dumps(observed),flush=True); assert observed==dict(python='3.11.11',numpy='2.0.1',torch='2.5.1'); import run; run.verify('encode'); cfg=run.read(run.PACKAGE/'config/EXECUTION.json'); [run.require(run.sha(d[k]['path'])==d[k]['sha256'],'RAW_INPUT') for d in cfg['devices'] for k in ('raw','packet_index','chronological_order')]; suite=unittest.defaultTestLoader.loadTestsFromNames(['test_runner','test_topup']); r=unittest.TextTestRunner(verbosity=2).run(suite); assert r.wasSuccessful() and r.testsRun==23"
                        ran=run_python(code,600);(DEPLOY/'PREFLIGHT.log').write_text(ran.stdout+ran.stderr,encoding='utf-8')
                        state['preflight']=dict(returncode=ran.returncode,tail=(ran.stdout+ran.stderr)[-5000:]);state['status']='PREFLIGHT_PASS' if ran.returncode==0 else 'PREFLIGHT_FAIL';save();self.send(state);return
                    if route=='submit':
                        need(state['status']=='PREFLIGHT_PASS' and not state['submitted'],'ONE_SUBMIT')
                        with (DEPLOY/'SUBMIT_ATTEMPT.json').open('x') as f:json.dump(dict(candidate=state['candidate']),f)
                        ran=subprocess.run(['sbatch','--parsable',str(PACKAGE/'hpc/run_encode.slurm')],cwd=PACKAGE,capture_output=True,text=True,timeout=30)
                        state['submission']=dict(returncode=ran.returncode,stdout=ran.stdout,stderr=ran.stderr)
                        state['status']='SUBMITTED' if ran.returncode==0 else 'SUBMIT_FAILED_NO_RETRY'
                        if ran.returncode==0:
                            job=ran.stdout.strip().split(';')[0];need(job.isdigit(),'JOB_ID');state.update(job_id=job,submitted=True)
                        save();self.send(state);return
                    self.send(dict(error='UNKNOWN_ROUTE'),404)
            except Exception as e:state['last_error']=str(e);save();self.send(dict(error=str(e),state=state),409)
    save();server=ThreadingHTTPServer(('127.0.0.1',18798),Handler)
    print('C4_REPAIR_READY port=18798',flush=True)
    timer=threading.Timer(36000,server.shutdown);timer.daemon=True;timer.start()
    try:server.serve_forever(poll_interval=.5)
    finally:timer.cancel();server.server_close()

def repair_configuration(spec):
    import base64
    previous=ROOT/'runs/history_sample_coverage_c4_deployment_20261101'
    state=read(previous/'STATE.json')
    need(state['status']=='PREFLIGHT_FAIL' and state['submitted'] is False,'ONLY_PRE_SUBMISSION_FAILURE')
    need('CONFIG_SEMANTICS' in state['preflight']['tail'],'EXPECTED_FAILURE')
    need(not (previous/'SUBMIT_ATTEMPT.json').exists() and not (PACKAGE/'ENCODE_ATTEMPT.json').exists() and not (PACKAGE/'outputs').exists(),'NO_SCIENCE_OR_SUBMISSION')
    need(sha(PACKAGE/'EXECUTION_CARD.json')==spec['execution_card_sha256'],'UNCHANGED_CARD')
    p=PACKAGE/'config/EXECUTION.json';need(sha(p)==spec['before_sha256'],'EXPECTED_FAILED_CONFIG')
    payload=base64.b64decode(spec['payload_b64']);need(hashlib.sha256(payload).hexdigest()==spec['after_sha256'],'REPAIR_PAYLOAD_PIN')
    need(json.loads(p.read_bytes())==json.loads(payload),'IDENTICAL_CONFIG_VALUES')
    with (DEPLOY/'EXECUTION.failed.json').open('xb') as f:f.write(p.read_bytes())
    temporary=DEPLOY/'EXECUTION.corrected.json';temporary.write_bytes(payload);temporary.replace(p)
    result=dict(status='CONFIG_ORDER_REPAIRED',before_sha256=spec['before_sha256'],after_sha256=sha(p),identical_json_values=True,model_forwards=0,new_distances=0,previous_submissions=0)
    write(DEPLOY/'REPAIR_RECEIPT.json',result);return result

if __name__=="__main__":
    main(read(Path(__file__).with_name("receiver_config.json")))
