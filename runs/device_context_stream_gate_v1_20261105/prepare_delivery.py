"""Prepare bounded delivery; reuse established connection, never start SSH."""
import ast,base64,hashlib,json,secrets,shlex,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert json.loads((HERE/'LOCAL_CHECKS.json').read_text())['status']=='PASS'
 for p in HERE.glob('*.py'):ast.parse(p.read_text())
 names=['worker.py','stream_core.py','test_core.py','packet_reader.py','freeze_spec.py','VALIDATION_PLAN.json','SLICES.json','TRAINING_SPEC_PROPOSED.json']
 pins={name:sha(HERE/('.private/'+name if name=='AB_SAMPLES.json.gz' else name)) for name in names}
 payload_bytes=len(json.dumps({name:base64.b64encode((HERE/('.private/'+name if name=='AB_SAMPLES.json.gz' else name)).read_bytes()).decode() for name in names}).encode());assert payload_bytes<2*1024**2
 private=HERE/'.private';private.mkdir(exist_ok=True);config=dict(token=secrets.token_hex(32),pins=pins)
 (private/'config.json').write_text(json.dumps(config))
 old=json.loads((ROOT/'runs/input_model_forensics_v2_20261104/.private/connection.json').read_text());connection=dict(token=config['token'],socks_port=old['socks_port'],remote_port=18840)
 (private/'connection.json').write_text(json.dumps(connection))
 remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name;py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
 script="import base64,json,os,socket,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path("+repr(remote)+")\nassert not p.exists(),'NEW_DELIVERY_ONLY'\ns=socket.socket();s.bind(('127.0.0.1',18840));s.close()\np.mkdir(parents=True)\n(p/'receiver.py').write_bytes(base64.b64decode("+repr(base64.b64encode((HERE/'receiver.py').read_bytes()).decode())+"))\n(p/'.private.json').write_text("+repr(json.dumps(config))+")\nwith (p/'receiver.log').open('ab') as log:\n proc=subprocess.Popen(["+repr(py)+",'-X','utf8','-B',str(p/'receiver.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)\nprint('DEVICE_STREAM_RECEIVER_STARTED',proc.pid,'18840')\n"
 encoded=base64.b64encode(zlib.compress(script.encode(),9)).decode();command=py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(encoded)+')))')
 (private/'RUN_IN_EXISTING_HPC.txt').write_text(command,encoding='utf-8')
 receipt=dict(status='PREPARED_NOT_SUBMITTED',remote=remote,pins=pins,receiver_sha256=sha(HERE/'receiver.py'),upload_bytes=payload_bytes,cpu=1,memory_gib=8,preflight_seconds=300,full_seconds=1500,automatic_retries=0,source_writes=0)
 (HERE/'DELIVERY.json').write_text(json.dumps(receipt,indent=2));print(json.dumps({k:v for k,v in receipt.items() if k!='pins'}))
if __name__=='__main__':main()
