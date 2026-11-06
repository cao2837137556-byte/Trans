"""Prepare bounded read-only log delivery over the existing user connection."""
import ast, base64, hashlib, json, secrets, shlex, zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
def main():
    private=HERE/'.private';private.mkdir(exist_ok=True)
    pins={}
    for arm in ['REFIT782','STATS8','FUSION790']:
        for seed in [27,127,227]:
            key=f'{arm}_{seed}';p=ROOT/'runs/device_context_head_training_v2_20261105'/f'TRAIN_{key}_RESULT.json'
            r=json.loads(p.read_text());pins[key]={k:r[k] for k in ['head_sha256','initial_sha256','endpoint_sha256']}
    b=(json.dumps(pins,indent=2)+'\n').encode();(HERE/'PINS.json').write_bytes(b)
    cfg=json.loads((ROOT/'runs/representation_usage_diagnosis_v2_20261105/.private/connection.json').read_text())
    cfg.update(token=secrets.token_hex(32),remote_port=18849)
    (private/'connection.json').write_text(json.dumps(cfg))
    remote='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name
    py='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'
    server='''from http.server import BaseHTTPRequestHandler,HTTPServer
import hmac,json,threading
from pathlib import Path
HERE=Path(__file__).resolve().parent
token=(HERE/'.token').read_text()
class H(BaseHTTPRequestHandler):
 def log_message(self,*a): pass
 def do_GET(self):
  if not hmac.compare_digest(self.path,'/'+token+'/result'):self.send_error(403);return
  b=(HERE/'RESULT.json').read_bytes();self.send_response(200);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
s=HTTPServer(('127.0.0.1',18849),H)
t=threading.Timer(3600,s.shutdown);t.daemon=True;t.start();s.serve_forever()
'''
    (HERE/'receiver.py').write_bytes(server.encode());ast.parse(server)
    payload={n:base64.b64encode((HERE/n).read_bytes()).decode() for n in ['export_logs.py','PINS.json','receiver.py']}
    script='import os,base64,subprocess\nfrom pathlib import Path\nos.umask(0o077)\np=Path('+repr(remote)+')\nassert not p.exists(),"NEW_VERSION_ONLY"\np.mkdir(parents=True)\n'
    script+='files='+repr(payload)+'\nfor n,b in files.items():(p/n).write_bytes(base64.b64decode(b))\n'
    script+='(p/".token").write_text('+repr(cfg['token'])+')\n'
    script+='subprocess.run(['+repr(py)+',"-B",str(p/"export_logs.py")],check=True,timeout=90)\n'
    script+='with (p/"receiver.log").open("ab") as f:proc=subprocess.Popen(['+repr(py)+',"-B",str(p/"receiver.py")],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True)\n'
    script+='print("TRAIN_LOG_AUDIT_READY",proc.pid,18849)\n'
    enc=base64.b64encode(zlib.compress(script.encode(),9)).decode()
    (private/'RUN_IN_EXISTING_HPC.txt').write_text(py+' -c '+shlex.quote('import base64,zlib;exec(zlib.decompress(base64.b64decode('+repr(enc)+')))'))
    (HERE/'DELIVERY.json').write_text(json.dumps(dict(scope='READ_ONLY_NINE_TRAIN_LOGS',training_jobs=0,port=18849,service_lifetime_seconds=3600,pins={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in payload}),indent=2)+'\n')
    print('LOG_AUDIT_PREPARED_NO_TRAINING')
if __name__=='__main__':main()
