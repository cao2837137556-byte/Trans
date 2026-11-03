"""Bind reviewed bytes to a loopback receiver on the user's existing tunnel.

Does not log in, execute remote commands, run a model or submit a job.
The generated bootstrap contains a private one-use channel token; keep it out
of Git and use it only in the already authenticated Linux terminal.
"""
import base64
import hashlib
import json
from pathlib import Path
import secrets
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = ROOT / 'runs/edge_linux_preflight_package_v1_20261103'
REMOTE = '/public/home/jiangxinwei.zr/work/paper04/runs/edge_linux_preflight_deployment_v1_20261103'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    receiver = HERE / 'remote_receiver.py'
    if not receiver.is_file():
        raise ValueError('RECEIVER_NOT_READY')
    build = read(PACKAGE / 'BUILD_RECEIPT.json')
    archive = PACKAGE / 'edge_linux_preflight_20261103.tar'
    if archive.stat().st_size != build['archive_bytes'] or sha(archive) != build['archive_sha256']:
        raise ValueError('REVIEWED_ARCHIVE_CHANGED')
    card = read(ROOT / 'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json')
    files = {'archive': dict(path=str(archive), filename=archive.name,
                           bytes=build['archive_bytes'], sha256=build['archive_sha256'])}
    for key, pin in card['raw_inputs'].items():
        source = Path(pin['path'])
        if source.stat().st_size != pin['bytes'] or sha(source) != pin['sha256']:
            raise ValueError('LOCAL_RAW_PIN:' + key)
        files[key] = dict(path=str(source), filename=source.name, bytes=pin['bytes'], sha256=pin['sha256'])
    private = HERE / '.private'
    private.mkdir(exist_ok=True)
    connection_path = private / 'connection.json'
    connection = read(connection_path) if connection_path.exists() else dict(
        token=secrets.token_hex(24), socks_port=49782, remote_port=18817)
    write(connection_path, connection)
    config = dict(token=connection['token'], files={k:{n:v[n] for n in ('filename','bytes','sha256')}
        for k,v in files.items()}, archive_manifest_sha256=build['manifest_sha256'])
    encoded_source = base64.b64encode(zlib.compress(receiver.read_bytes(), 9)).decode('ascii')
    encoded_config = base64.b64encode(zlib.compress(json.dumps(config).encode(), 9)).decode('ascii')
    bootstrap = f'''import base64,hashlib,http.client,json,os,pathlib,subprocess,sys,time,zlib
os.umask(0o077)
here=pathlib.Path({REMOTE!r})
here.mkdir(parents=True,exist_ok=True)
source=zlib.decompress(base64.b64decode({encoded_source!r}))
config=zlib.decompress(base64.b64decode({encoded_config!r}))
source_path=here/'remote_receiver.py'
config_path=here/'.receiver_private.json'
if config_path.exists():
    old=json.loads(config_path.read_text())
    assert old==json.loads(config),'EXISTING_RECEIVER_IDENTITY_DIFFERS'
source_path.write_bytes(source)
config_path.write_bytes(config)
os.chmod(config_path,0o600)
entry='import json,runpy;ns=runpy.run_path('+repr(str(source_path))+');ns["main"](json.load(open('+repr(str(config_path))+')))'
with (here/'receiver.log').open('ab',buffering=0) as log:
    process=subprocess.Popen([sys.executable,'-u','-B','-c',entry],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
(here/'RECEIVER_PID.txt').write_text(str(process.pid)+'\\n')
token=json.loads(config)['token']
ready=False
for unused in range(50):
    try:
        connection=http.client.HTTPConnection('127.0.0.1',18817,timeout=1)
        connection.request('GET','/'+token+'/state')
        response=connection.getresponse()
        assert response.status==200
        json.loads(response.read())
        connection.close()
        ready=True
        break
    except Exception:
        if process.poll() is not None:break
        time.sleep(.1)
assert ready,'EDGE_RECEIVER_NOT_READY: see '+str(here/'receiver.log')
print('EDGE_PREFLIGHT_DELIVERY_READY',flush=True)
'''
    packed = base64.b64encode(zlib.compress(bootstrap.encode('utf-8'), 9)).decode('ascii')
    command = PYTHON + ' -B -c "import base64,zlib;exec(zlib.decompress(base64.b64decode(\'' + packed + '\')))"'
    command_file = HERE / 'RUN_IN_HPC_TERMINAL.txt'
    command_file.write_text(command + '\n', encoding='utf-8')
    public = dict(schema='EDGE_PREFLIGHT_DEPLOYMENT_V1', scope='ONE_BOUNDED_LINUX_PREFLIGHT_ONLY',
        status='READY_FOR_USER_TERMINAL_BOOTSTRAP_NOT_SUBMITTED',
        files=files, archive_manifest_sha256=build['manifest_sha256'],
        receiver_source_sha256=sha(receiver), bootstrap_sha256=sha(command_file),
        remote_port=18817, manual_connection_reused=True,
        remote_directory=REMOTE, cpu=1, ram_gib=6, slurm_seconds=600,
        reviewer='Antigravity PASS relayed by the human user; no new on-disk review asserted',
        model_training=False, formal_external_evaluation=False, automatic_resubmission=False)
    write(HERE / 'DELIVERY.json', public)
    print(json.dumps(dict(status=public['status'], transfer_bytes=sum(x['bytes'] for x in files.values()),
        file_count=len(files), bootstrap_characters=len(command), receiver_sha256=sha(receiver))))


if __name__ == '__main__':
    main()
