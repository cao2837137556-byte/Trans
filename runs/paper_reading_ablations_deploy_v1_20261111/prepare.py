"""Prepare one bounded submission via an existing authenticated terminal."""
import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;SCIENCE=HERE.parent/'paper_reading_ablations_v2_20261111'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    assert json.loads((HERE/'LOCAL_DELIVERY_CHECK.json').read_text())['status']=='PASS'
    for p in HERE.glob('*.py'):ast.parse(p.read_text())
    receipt=json.loads((SCIENCE/'PACKAGE_RECEIPT.json').read_text());archive=SCIENCE.parent/receipt['archive'];assert sha(archive)==receipt['sha256']
    manifest=json.loads((SCIENCE/'PACKAGE_MANIFEST.json').read_text());assert all(sha(SCIENCE/n)==h for n,h in manifest['files'].items())
    names=['receiver.py','client.py','BASELINE_STATUS_SNAPSHOT.json','LOCAL_DELIVERY_CHECK.json']
    cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in names})
    private=HERE/'.private';private.mkdir(exist_ok=True);conn=dict(token=cfg['token'],socks_port=53960,remote_port=18881);(private/'connection.json').write_text(json.dumps(conn))
    project='/public/home/jiangxinwei.zr/work/paper04';remote=project+'/runs/'+HERE.name;science=project+'/runs/'+SCIENCE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
    payload={n:base64.b64encode((HERE/n).read_bytes()).decode() for n in names};zip64=base64.b64encode(archive.read_bytes()).decode()
    code="""import os,json,base64,hashlib,subprocess,socket,zipfile,io
from pathlib import Path
os.umask(0o077)
"""+'root=Path('+repr(project)+')\np=Path('+repr(remote)+')\nscience=Path('+repr(science)+')\n'+"""assert not p.exists() and not science.exists(),'NEW_DELIVERY_AND_SCIENCE_ONLY'
s=socket.socket();s.bind(('127.0.0.1',18881));s.close()
"""+'blob=base64.b64decode('+repr(zip64)+')\nassert hashlib.sha256(blob).hexdigest()=='+repr(receipt['sha256'])+'\n'+"""with zipfile.ZipFile(io.BytesIO(blob)) as z:
 assert z.testzip() is None
 for n in z.namelist():
  q=Path(n);assert not q.is_absolute() and '..' not in q.parts and q.parts[0]==science.name
 z.extractall(root/'runs')
m=json.loads((science/'PACKAGE_MANIFEST.json').read_text())
for n,h in m['files'].items():assert hashlib.sha256((science/n).read_bytes()).hexdigest()==h,'PACKAGE_SHA:'+n
locations=json.loads((science/'PIN_LOCATIONS.json').read_text())
allowed={'runs/same_bank_context_v6_20261106/'+n:'provenance/'+n for n in ['FORMAL_ACCEPTANCE.json','EVALUATION_COMPLETION.json','DELIVERY.json','HISTORY_INVENTORY.json']}
assert locations==allowed,'PROVENANCE_MAPPING_SCOPE'
checked=0
for n,h in json.loads((science/'INPUT_PINS.json').read_text()).items():
 q=(science/locations[n] if n in locations else root/n).resolve();assert q.is_relative_to(root) and q.is_file(),'MISSING_DEPENDENCY:'+n
 assert hashlib.sha256(q.read_bytes()).hexdigest()==h,'DEPENDENCY_SHA:'+n
 if n.endswith('/HISTORY_INVENTORY.json'):assert json.loads((root/n).read_text())==json.loads(q.read_text()),'HISTORY_INVENTORY_SEMANTICS'
 checked+=1
p.mkdir(parents=True)
"""+'files='+repr(payload)+'\ncfg='+repr(cfg)+'\n'+"""for n,v in files.items():
 b=base64.b64decode(v);assert hashlib.sha256(b).hexdigest()==cfg['pins'][n];(p/n).write_bytes(b)
(p/'.private.json').write_text(json.dumps(cfg))
(p/'DEPENDENCY_GATE.json').write_text(json.dumps(dict(status='PASS',files_checked=checked,before_sbatch=True)))
"""+'(p/\'DEPLOYMENT.json\').write_text(json.dumps(dict(package_sha256='+repr(receipt['sha256'])+',science='+repr(science)+',original_package_unchanged=True)))\n'+"""r=subprocess.run(['sbatch','--parsable','run.slurm'],cwd=science,capture_output=True,text=True,timeout=30)
assert r.returncode==0,r.stderr
job=r.stdout.strip().split(';')[0];assert job.isdigit()
(p/'JOB.json').write_text(json.dumps(dict(job_id=job,cpu=1,memory_gib=8,wall_seconds=3600,scope='BASELINE_THEN_GUARD_THEN_EXPONENT_CACHED_ABLATIONS')))
"""+'with (p/\'receiver.log\').open(\'ab\') as f:proc=subprocess.Popen(['+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\n"+"print('PAPER_ABLATIONS_SUBMITTED',job,'RECEIVER',proc.pid,'DEPENDENCIES',checked)\n"
    enc=base64.b64encode(zlib.compress(code.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'DELIVERY.json').write_text(json.dumps(dict(status='PREPARED_NOT_SUBMITTED',package_sha256=receipt['sha256'],pins=cfg['pins'],cpu=1,memory_gib=8,wall_seconds=3600),indent=2));print('PREPARED: identical science ZIP; 1CPU/8GiB/1h; authenticated read-only receipt service')
if __name__=='__main__':main()
