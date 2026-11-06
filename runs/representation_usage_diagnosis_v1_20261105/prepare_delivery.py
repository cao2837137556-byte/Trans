"""Freeze the isolated source-gate delivery; never establish a connection."""
import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 assert not (HERE/'START_INTENT.json').exists()
 for f in HERE.glob('*.py'):ast.parse(f.read_text())
 for n in ['LOCAL_REGRESSION.json']:assert json.loads((HERE/n).read_text())['status']=='PASS'
 names=['worker.py','analysis_core.py','PARENT_PINS.json','DIAGNOSTIC_SPEC.json','EDGE_CARD.json','stream_core.py']
 cfg=dict(token=secrets.token_hex(32),pins={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in names});private=HERE/'.private';(private/'config.json').write_text(json.dumps(cfg));conn=json.loads((ROOT/'runs/device_context_evaluation_v1_20261105/.private/connection.json').read_text());conn.update(token=cfg['token'],remote_port=18847);(private/'connection.json').write_text(json.dumps(conn))
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';receiver=(HERE/'receiver.py').read_bytes()
 script="import base64,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_VERSION_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18847));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode(receiver).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(cfg))+")\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('REPRESENTATION_DIAG_V1_RECEIVER_STARTED',proc.pid,18847)\n"
 enc=base64.b64encode(zlib.compress(script.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
 receipt=dict(result='PREPARED',impact='Frozen-head functional dependence, normal false-positive and C5 factor diagnosis; no fitting',next='PREFLIGHT -> DIAGNOSE',pins=cfg['pins'],receiver_sha256=hashlib.sha256(receiver).hexdigest(),cpu=1,memory_gib=8,phase_wall_seconds={'PREFLIGHT':1800,'DIAGNOSE':7200},automatic_job_retries=0,training_jobs=0)
 (HERE/'DELIVERY.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print('REPRESENTATION_DIAG_V1_CHAIN_READY')
if __name__=='__main__':main()
