import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'baseline_author_defaults_v1_20261108'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert json.loads((HERE/'LOCAL_REGRESSION.json').read_text())['status']=='PASS'
    for q in HERE.glob('*.py'):ast.parse(q.read_text())
    names=['worker.py','preflight.py','controller.py','receiver.py','client.py','CONFIG.json','PARENT_PINS.json','LOCAL_REGRESSION.json']
    cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in names});conn=json.loads((OLD/'.private/connection.json').read_text());conn.update(token=cfg['token'],remote_port=18878);(HERE/'.private/connection.json').write_text(json.dumps(conn))
    project='/public/home/jiangxinwei.zr/work/paper04';remote=project+'/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
    env='source '+project+'/frontend_compat_v1/environment.sh\nexport PYTHONPATH='+project+'/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/runtime/numpy201:'+project+'/environment/vendor_py311_v1:${PYTHONPATH:-}\nexport OMP_NUM_THREADS=8 MKL_NUM_THREADS=8 OPENBLAS_NUM_THREADS=8 NUMEXPR_NUM_THREADS=8 PYTHONDONTWRITEBYTECODE=1 CUBLAS_WORKSPACE_CONFIG=:4096:8\n'
    script='#!/bin/bash\n#SBATCH --partition=amd\n#SBATCH --ntasks=1\n#SBATCH --cpus-per-task=8\n#SBATCH --mem=24576M\n#SBATCH --time=02:00:00\n#SBATCH --no-requeue\n#SBATCH --job-name=base-remaining3\n#SBATCH --output='+remote+'/job-%j.out\n#SBATCH --error='+remote+'/job-%j.err\nset -euo pipefail\numask 077\n'+env+'exec '+py+' -X utf8 -B '+remote+'/preflight.py\n'
    payload={n:base64.b64encode((HERE/n).read_bytes()).decode() for n in names}
    code="import os,json,base64,hashlib,subprocess,socket\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_RUN_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18878));s.close()\np.mkdir(parents=True)\nfiles="+repr(payload)+"\ncfg="+repr(cfg)+"\nfor n,v in files.items():\n b=base64.b64decode(v);assert hashlib.sha256(b).hexdigest()==cfg['pins'][n];(p/n).write_bytes(b)\n(p/'.private.json').write_text(json.dumps(cfg))\n(p/'job.slurm').write_text("+repr(script)+")\nr=subprocess.run(['sbatch','--parsable',str(p/'job.slurm')],capture_output=True,text=True,timeout=30)\nassert r.returncode==0,r.stderr\njob=r.stdout.strip().split(';')[0];assert job.isdigit()\n(p/'JOB.json').write_text(json.dumps(dict(job_id=job,cpu=8,memory_gib=24,wall_seconds=7200)))\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('REMAINING_THREE_SUBMITTED',job,'RECEIVER',proc.pid)\n"
    enc=base64.b64encode(zlib.compress(code.encode(),9)).decode();(HERE/'.private/RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'DELIVERY.json').write_text(json.dumps(dict(status='PREPARED',pins=cfg['pins'],main_model_changed=False,removed='ModernNCA'),indent=2));print('PREPARED',len(names))
if __name__=='__main__':main()
