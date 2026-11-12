import ast,base64,hashlib,json,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;SCIENCE=HERE.parent/'paper_reading_ablations_v2_20261111'
def main():
    ast.parse((HERE/'launch_accounted.py').read_text());assert 'import resource' not in (HERE/'run.slurm').read_text() if (HERE/'run.slurm').exists() else True
    script=(SCIENCE/'run.slurm').read_text().replace('exec /usr/bin/time -v -o "$TASK_DIR/RESOURCE_USAGE.txt" /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B "$TASK_DIR/run.py"','exec /share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B "$PROJECT_DIR/runs/'+HERE.name+'/launch_accounted.py"')
    assert '/usr/bin/time' not in script
    project='/public/home/jiangxinwei.zr/work/paper04';remote=project+'/runs/'+HERE.name;science=project+'/runs/'+SCIENCE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
    data=(HERE/'launch_accounted.py').read_bytes();digest=hashlib.sha256(data).hexdigest()
    code="import json,base64,hashlib,subprocess\nfrom pathlib import Path\np=Path("+repr(remote)+")\ns=Path("+repr(science)+")\n"+"""old=json.loads((p/'JOB.json').read_text());assert old['job_id']=='183529'
assert not (s/'results').exists(),'NO_HOT_EDIT_OR_SCIENCE_RESTART'
assert not (p/'RETRY_JOB.json').exists(),'ONE_RETRY_ONLY'
r=subprocess.run(['sacct','-j','183529','-n','-P','--format=JobID,State,ExitCode'],capture_output=True,text=True,timeout=20)
assert '183529|FAILED|127:0' in r.stdout
"""+'b=base64.b64decode('+repr(base64.b64encode(data).decode())+');assert hashlib.sha256(b).hexdigest()=='+repr(digest)+"\n(p/'launch_accounted.py').write_bytes(b)\n(p/'retry.slurm').write_text("+repr(script)+")\n"+"""r=subprocess.run(['sbatch','--parsable',str(p/'retry.slurm')],cwd=s,capture_output=True,text=True,timeout=30);assert r.returncode==0,r.stderr
job=r.stdout.strip().split(';')[0];assert job.isdigit()
(p/'FAILED_JOB_183529.json').write_text(json.dumps(old))
new=dict(old,job_id=job,previous_failed_job='183529',repair='Python resource accounting replaces unavailable /usr/bin/time; frozen science unchanged')
(p/'RETRY_JOB.json').write_text(json.dumps(new));tmp=p/'JOB.tmp';tmp.write_text(json.dumps(new));tmp.replace(p/'JOB.json')
print('PAPER_ABLATIONS_RETRY_SUBMITTED',job)
"""
    enc=base64.b64encode(zlib.compress(code.encode())).decode();(HERE/'.private/RETRY_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'LAUNCH_REPAIR.json').write_text(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',failed_job='183529',failed_seconds=1,failed_exit='127:0',reason='compute node lacks /usr/bin/time',science_started=False,science_unchanged=True,launcher_sha256=digest,uses_optional_time_binary=False),indent=2));print('ACCOUNTING_LAUNCH_REPAIR_PREPARED')
if __name__=='__main__':main()
