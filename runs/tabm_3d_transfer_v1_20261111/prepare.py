import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    result=json.loads((HERE/'LOCAL_VALIDATION.json').read_text());assert result['status']=='PASS'
    for n,h in result['source_sha256'].items():assert sha(HERE/n)==h,'STALE_LOCAL_CHECK'
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    names=['transfer.py','analysis_core.py','launch.py','run.slurm','EXECUTION_CARD.md','INPUT_PINS.json','METHOD_FREEZE.json','TABM_EXPECTED_METRICS.json','TABM_EVALUATE_PIN.json','EVALUATION_INPUTS_PIN.json','MLP_EXPECTED_METRICS.json','LOCAL_VALIDATION.json','client.py','receiver.py']
    manifest=dict(files={n:sha(HERE/n) for n in names},training=False,configuration_count=5,p=3,lambda_value=.25,guard=True,raw_score_tolerance=2e-7,raw_decision_differences=0)
    (HERE/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');names+=['PACKAGE_MANIFEST.json']
    cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in names})
    (HERE/'.private/connection.json').write_text(json.dumps(dict(token=cfg['token'],socks_port=53960,remote_port=18882)))
    remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';payload={n:(HERE/n).read_bytes().decode('utf8') for n in names}
    code="import os,json,base64,hashlib,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_RUN_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18882));s.close()\np.mkdir(parents=True)\nfiles="+repr(payload)+"\ncfg="+repr(cfg)+"\nfor n,v in files.items():\n b=v.encode('utf8');assert hashlib.sha256(b).hexdigest()==cfg['pins'][n];(p/n).write_bytes(b)\n(p/'.private.json').write_text(json.dumps(cfg))\nchecked=0\nfor n,h in json.loads((p/'INPUT_PINS.json').read_text()).items():\n q=p.parents[1]/n;assert q.is_file() and hashlib.sha256(q.read_bytes()).hexdigest()==h,'DEPENDENCY_SHA:'+n\n checked+=1\n(p/'DEPENDENCY_GATE.json').write_text(json.dumps(dict(status='PASS',checked=checked,before_sbatch=True)))\nr=subprocess.run(['sbatch','--parsable','run.slurm'],cwd=p,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr\njob=r.stdout.strip().split(';')[0];assert job.isdigit()\n(p/'JOB.json').write_text(json.dumps(dict(job_id=job,cpu=8,memory_gib=16,gpu='one RTX4090',wall_seconds=7200,scope='REPRODUCE_TABM_RAW_THEN_OWN_SCALE_3D_TRANSFER',training=False)))\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('TABM_TRANSFER_SUBMITTED',job,'RECEIVER',proc.pid,'DEPENDENCIES',checked)\n"
    enc=base64.b64encode(zlib.compress(code.encode(),9)).decode();(HERE/'.private/RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'DELIVERY.json').write_text(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',pins=cfg['pins'],training=False,main_method_changed=False),indent=2));print('TRANSFER_PREPARED')
if __name__=='__main__':main()
