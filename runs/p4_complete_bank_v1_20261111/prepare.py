import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def slurm(task,remote,project,py):
    assert task in ['controls','tabm']
    return '#!/bin/bash\n#SBATCH --job-name=p4-'+task+'\n#SBATCH --partition=amd\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=1\n#SBATCH --mem=8192M\n#SBATCH --time=01:00:00\n#SBATCH --no-requeue\n#SBATCH --output=slurm-%j.out\n#SBATCH --error=slurm-%j.err\nset -euo pipefail\numask 077\nsource '+project+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+project+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+project+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONDONTWRITEBYTECODE=1\nexec '+py+' -X utf8 -B '+remote+'/launch.py '+task+'\n'
def main():
    test=json.loads((HERE/'LOCAL_VALIDATION.json').read_text());assert test['status']=='PASS' and test['worker_sha256']==sha(HERE/'worker.py')
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    names=['worker.py','analysis_core.py','launch.py','receiver.py','client.py','P3_METHOD_REFERENCE.json','P4_METHOD.json','P4_EXPECTED_METRICS.json','PRIOR_CHANGED_MANIFEST.json','INPUT_PINS.json','EXECUTION_CARD.md','REFERENCE_DECISION_AUDIT.md','REFERENCE_AUDIT_PINS.json','LOCAL_VALIDATION.json']
    manifest=dict(files={n:sha(HERE/n) for n in names},p=4,full_bank_main=True,controls=6,compression_trial=False,reference_inventory_only=True)
    (HERE/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n');names+=['PACKAGE_MANIFEST.json']
    cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in names});(HERE/'.private/connection.json').write_text(json.dumps(dict(token=cfg['token'],socks_port=53960,remote_port=18883)))
    project='/public/home/jiangxinwei.zr/work/paper04';remote=project+'/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';payload={n:(HERE/n).read_bytes().decode('utf8') for n in names}
    scripts={n:slurm(n,remote,project,py) for n in ['controls','tabm']}
    code="import os,json,hashlib,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_RUN_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18883));s.close()\np.mkdir(parents=True)\nfiles="+repr(payload)+"\ncfg="+repr(cfg)+"\nfor n,v in files.items():\n b=v.encode('utf8');assert hashlib.sha256(b).hexdigest()==cfg['pins'][n];(p/n).write_bytes(b)\n(p/'.private.json').write_text(json.dumps(cfg))\nfor n,h in json.loads((p/'INPUT_PINS.json').read_text()).items():\n q=p.parents[1]/n;assert q.is_file() and hashlib.sha256(q.read_bytes()).hexdigest()==h,'DEPENDENCY_SHA:'+n\n(p/'DEPENDENCY_GATE.json').write_text(json.dumps(dict(status='PASS',source_pins_checked=True)))\nscripts="+repr(scripts)+"\nfor n,s in scripts.items():(p/(n+'.slurm')).write_text(s)\n"+"""r=subprocess.run(['sbatch','--parsable','controls.slurm'],cwd=p,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
job=r.stdout.strip().split(';')[0];assert job.isdigit()
(p/'controls_JOB.json').write_text(json.dumps(dict(job_id=job,cpu=1,memory_gib=8,wall_seconds=3600)))
r=subprocess.run(['sbatch','--parsable','--dependency=afterok:183549:'+job,'tabm.slurm'],cwd=p,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
tabm=r.stdout.strip().split(';')[0];assert tabm.isdigit()
(p/'tabm_JOB.json').write_text(json.dumps(dict(job_id=tabm,cpu=1,memory_gib=8,wall_seconds=3600,afterok=['183549',job])))
"""+"with (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('P4_UPGRADE_SUBMITTED',job,'TABM_P4',tabm,'RECEIVER',proc.pid)\n"
    ast.parse(code);enc=base64.b64encode(zlib.compress(code.encode(),9)).decode();(HERE/'.private/RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'DELIVERY.json').write_text(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',pins=cfg['pins'],original_p3_job_untouched='183549',compression_performed=False),indent=2));print('P4_CONTROLS_AND_DEPENDENT_TABM_PREPARED')
if __name__=='__main__':main()
