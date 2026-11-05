"""Pin already accepted inputs; source data remain unchanged."""
import base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(4*1024**2),b''):h.update(b)
 return h.hexdigest()
def main():
 private=HERE/'.private';private.mkdir(exist_ok=True);plan={};paths={};catalog=read(ROOT/'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/metadata/resolved_raw_catalog.json')
 def add(key,p,h,kind):
  assert p.exists();plan[key]=dict(name=p.name,bytes=p.stat().st_size,sha256=h,kind=kind,local_relative=str(p.relative_to(ROOT)).replace('\\','/'));paths[key]=str(p)
 for i,r in enumerate(catalog):
  p=ROOT/('runs/'+r['path'].split('/runs/',1)[1]);assert p.stat().st_size==r['bytes'];add('raw'+str(i),p,r['sha256'],'raw')
 for folder,selected,kind in [('runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared',['LEARN.jsonl.gz','CIC_DEV.jsonl.gz','UNSW_DEV.jsonl.gz','LEARN_q.npy','CIC_DEV_q.npy','UNSW_DEV_q.npy','FIT.npz','CAL.npz','normalizer.npz'],'prepared'),('runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features',['LEARN.npy','CIC_DEV.npy','UNSW_DEV.npy'],'e3')]:
  base=ROOT/folder;pins={line.split()[1]:line.split()[0] for line in (base/'SHA256SUMS').read_text().splitlines() if line.strip()}
  for name in selected:add(kind+str(len(plan)),base/name,pins[name],kind)
 (HERE/'ASSET_PLAN.json').write_text(json.dumps(plan,indent=2));(private/'local_paths.json').write_text(json.dumps(paths))
 old=read(ROOT/'runs/device_context_stream_gate_v1_20261105/.private/connection.json');connection=dict(token=secrets.token_hex(32),socks_port=old['socks_port'],remote_port=18841);(private/'connection.json').write_text(json.dumps(connection))
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';payload=base64.b64encode((HERE/'asset_service.py').read_bytes()).decode()
 script="import base64,json,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_DELIVERY_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18841));s.close()\np.mkdir(parents=True)\n(p/'asset_service.py').write_bytes(base64.b64decode("+repr(payload)+"))\n(p/'.private.json').write_text("+repr(json.dumps(dict(token=connection['token'])))+")\nwith (p/'service.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'asset_service.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('DEVICE_TRAIN_ASSET_SERVICE_STARTED',proc.pid,18841)\n"
 encoded=base64.b64encode(zlib.compress(script.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))'))
 print(json.dumps(dict(files=len(plan),total_gib=sum(v['bytes'] for v in plan.values())/2**30,training_submitted=False)))
if __name__=='__main__':main()
