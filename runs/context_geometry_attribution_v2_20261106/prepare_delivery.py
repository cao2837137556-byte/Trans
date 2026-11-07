import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def main():
 assert not (HERE/'START_INTENT.json').exists()
 for f in HERE.glob('*.py'):ast.parse(f.read_text())
 assert json.loads((HERE/'LOCAL_REGRESSION.json').read_text())['status']=='PASS'
 names=['worker.py','geometry.py','attribution.py','physical.py','stream_core.py','source_packets.py','packet_reader.py','SOURCE_REFS.jsonl.gz','INPUT_PINS.json','dependency_gate.py','SPEC.json','test_contract.py']
 cfg=dict(token=secrets.token_hex(32),pins={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in names})
 private=HERE/'.private';(private/'config.json').write_text(json.dumps(cfg))
 conn=json.loads((ROOT/'runs/common_threshold_audit_v1_20261106/.private/connection.json').read_text());conn.update(token=cfg['token'],remote_port=18862);(private/'connection.json').write_text(json.dumps(conn))
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python';receiver=(HERE/'receiver.py').read_bytes()
 script="import base64,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_VERSION_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18862));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode(receiver).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(cfg))+")\nwith (p/'receiver.log').open('ab') as f:proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\nprint('CONTEXT_GEOMETRY_RECEIVER_STARTED',proc.pid,18862)\n"
 enc=base64.b64encode(zlib.compress(script.encode(),9)).decode();(private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
 receipt=dict(status='PREPARED',scope='READONLY_ATTRIBUTION_AND_3D_C5_COUNTERFACTUAL',pins=cfg['pins'],receiver_sha256=hashlib.sha256(receiver).hexdigest(),cpu=1,memory_gib=8,budget_minutes=[30,88],training=False,deployment_change=False,automatic_retries=0)
 (HERE/'DELIVERY.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode());print('CONTEXT_GEOMETRY_PREPARED')
if __name__=='__main__':main()
