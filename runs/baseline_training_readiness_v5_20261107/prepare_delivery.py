import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_bytes((json.dumps(v,indent=2,ensure_ascii=False)+'\n').encode())
def main():
 assert not (HERE/'START_INTENT.json').exists()
 assert json.loads((HERE/'LOCAL_REGRESSION.json').read_text())['status']=='PASS'
 assert json.loads((HERE/'DEPENDENCY_CLOSURE_CHECK.json').read_text())['status']=='PASS'
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 base=ROOT/'runs/device_context_evaluation_v1_20261105'
 names=['common.py','inputs.py','edge_context.py','preflight_encoder.py','stream_core.py','source_packets.py','packet_reader.py','ASSET_PLAN.json','EDGE_CARD.json','FINAL_TRAINING_ACCEPTANCE.json','LEGACY_RUNTIME_PINS.json','METHOD_FREEZE.json','NORMALIZER.json','OLD_ASSETS.json','SOURCE_FEATURE_ACCEPTANCE.json','TRAINING_DELIVERY.json']
 deps={str((base/n).relative_to(ROOT)).replace('\\','/'):sha(base/n) for n in names}
 spec=ROOT/'runs/device_context_head_training_v2_20261105/TRAINING_SPEC_FROZEN.json';deps[str(spec.relative_to(ROOT)).replace('\\','/')]=sha(spec)
 freeze=ROOT/'runs/paper_results_freeze_v1_20261107/METHOD_FREEZE.json';assert sha(freeze)==sha(HERE/'METHOD_FREEZE.json'),'PORTABLE_FREEZE_IDENTITY'
 write(HERE/'INPUT_PINS.json',deps)
 files=['worker.py','readiness.py','pipeline_parent.py','adapters.py','controller.py','TRAINING_PROTOCOL.json','DTE_PROVENANCE.json','METHOD_FREEZE.json','REPAIR.json','DEPENDENCY_CLOSURE_CHECK.json','EXECUTION_CARD.md','REPRODUCTION_AUDIT.md','SPEC.json','ASSETS.json','INPUT_PINS.json']+[str(p.relative_to(HERE)).replace('\\','/') for p in sorted((HERE/'vendor').rglob('*')) if p.is_file()]
 cfg=dict(token=secrets.token_hex(32),pins={n:sha(HERE/n) for n in files});private=HERE/'.private';private.mkdir(exist_ok=True);write(private/'config.json',cfg)
 conn=json.loads((HERE/'.private/connection_previous.json').read_text());conn.update(token=cfg['token'],remote_port=18873);write(private/'connection.json',conn)
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
 script="import base64,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_VERSION_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18873));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode((HERE/'receiver.py').read_bytes()).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(cfg))+")\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('BASELINE_QUAL_RECEIVER_STARTED',proc.pid,18873)\n"
 asset_copy="\nimport shutil,hashlib\nold=Path('/public/home/jiangxinwei.zr/work/paper04/runs/baseline_training_readiness_v4_20261107/assets')\n(p/'assets').mkdir()\n"
 for name,spec in json.loads((HERE/'ASSETS.json').read_text()).items():
  asset_copy+="src=old/"+repr(name)+"\nif src.exists():\n assert src.stat().st_size=="+str(spec['bytes'])+" and hashlib.sha256(src.read_bytes()).hexdigest()=="+repr(spec['sha256'])+"\n shutil.copyfile(src,p/'assets'/"+repr(name)+")\n"
 script=script.replace("\nwith (p/'receiver.log')",asset_copy+"\nwith (p/'receiver.log')")
 enc=base64.b64encode(zlib.compress(script.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
 write(HERE/'DELIVERY.json',dict(status='PREPARED',scope='SOURCE_FULL_TRAINING_RESOURCE_PREFLIGHT',pins=cfg['pins'],receiver_sha256=sha(HERE/'receiver.py'),cpu=1,memory_gib=8,wall_seconds=7200,main_model_changed=False,full_training_authorized=False,automatic_retries=0))
 print('BASELINE_QUAL_PREPARED',len(files),'files',len(deps),'dependencies')
if __name__=='__main__':main()
