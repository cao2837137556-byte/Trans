"""Freeze the isolated source-gate delivery; never establish a connection."""
import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 assert not (HERE/'START_INTENT.json').exists()
 for f in HERE.glob('*.py'):ast.parse(f.read_text())
 for n in ['LOCAL_REGRESSION.json']:assert json.loads((HERE/n).read_text())['status']=='PASS'
 names=sorted([f.name for f in HERE.glob('*.py') if f.name not in ['prepare_delivery.py','chain_client.py','receiver.py','test_evaluation.py','accept_evaluation.py']]+['ASSET_PLAN.json','TRAINING_SPEC_FROZEN.json','FINAL_TRAINING_ACCEPTANCE.json','NORMALIZER.json','TRAINING_DELIVERY.json','SOURCE_FEATURE_ACCEPTANCE.json','METHOD_FREEZE.json','OLD_ASSETS.json','EDGE_CARD.json','LEGACY_RUNTIME_PINS.json','EXECUTION_AUTHORIZATION.json'])
 cfg=dict(token=secrets.token_hex(32),pins={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in names});private=HERE/'.private';(private/'config.json').write_text(json.dumps(cfg));conn=json.loads((ROOT/'runs/device_context_training_v1_20261105/.private/connection.json').read_text());conn.update(token=cfg['token'],remote_port=18846);(private/'connection.json').write_text(json.dumps(conn))
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';receiver=(HERE/'receiver.py').read_bytes()
 script="import base64,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_VERSION_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18846));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode(receiver).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(cfg))+")\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('DEVICE_EVAL_V1_RECEIVER_STARTED',proc.pid,18846)\n"
 enc=base64.b64encode(zlib.compress(script.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
 receipt=dict(result='PREPARED',impact='Fixed model evaluation; no retraining or recalibration',next='PREFLIGHT -> CONTEXT -> AB -> EDGE',pins=cfg['pins'],receiver_sha256=hashlib.sha256(receiver).hexdigest(),cpu=1,memory_gib=8,phase_wall_seconds={'PREFLIGHT':1800,'CONTEXT':1800,'AB':3600,'EDGE':3600},automatic_job_retries=0,training_jobs=0)
 (HERE/'DELIVERY.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print('EVAL_V1_CHAIN_READY')
if __name__=='__main__':main()
