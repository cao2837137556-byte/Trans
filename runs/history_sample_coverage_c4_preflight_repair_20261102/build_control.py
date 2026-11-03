"""Seal only the replacement deployment controller and staged preflight."""
import ast,base64,hashlib,json,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
REMOTE='/public/home/jiangxinwei.zr/work/paper04/runs/'+HERE.name
def pack(b):return base64.b64encode(zlib.compress(b,9)).decode()
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    assert HERE.name=='history_sample_coverage_c4_preflight_repair_20261102'
    files={name:(HERE/name).read_bytes() for name in ('controller.py','preflight_worker.py')}
    for b in files.values():ast.parse(b.decode())
    connection=json.loads((HERE/'.private/connection.json').read_text())
    payload=json.dumps({k:pack(v) for k,v in files.items()})
    launch="import base64,zlib,json,pathlib,subprocess;d=pathlib.Path("+repr(REMOTE)+");d.mkdir(parents=True,exist_ok=True);items=json.loads(zlib.decompress(base64.b64decode("+repr(pack(payload.encode()))+")));assert not any((d/k).exists() for k in items);[(d/k).write_bytes(zlib.decompress(base64.b64decode(v))) for k,v in items.items()];q=d/'.private';q.mkdir(exist_ok=True);c=q/'connection.json';assert not c.exists();c.write_text("+repr(json.dumps(connection))+");c.chmod(0o600);f=(d/'controller.log').open('ab');subprocess.Popen(['/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python','-u','-B',str(d/'controller.py')],stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True);print('C4_PREFLIGHT_CONTROL_STARTED')"
    command='/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -B -c "import base64,zlib;exec(zlib.decompress(base64.b64decode(\''+pack(launch.encode())+'\')))"'
    ast.parse(launch)
    (HERE/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n')
    (HERE/'DELIVERY_MANIFEST.json').write_text(json.dumps(dict(remote_deployment=REMOTE,files={k:sha(v) for k,v in files.items()},installed_card='fdd491483c8408b8054cf195de5cfaee82c2f0772d56313ee1ae5ca34633350b',scientific_code_changed=False,large_assets_transferred=0,command_sha256=sha(command.encode()),command_characters=len(command)),indent=2))
    print(json.dumps(dict(remote_deployment=REMOTE,command_characters=len(command),code_bytes=sum(len(x) for x in files.values()))))
if __name__=='__main__':main()
