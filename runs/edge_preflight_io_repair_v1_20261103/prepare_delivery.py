"""Freeze small repair files; reuse inputs and the user's authenticated channel."""
import base64
import hashlib
import json
from pathlib import Path
import shlex
import zlib

HERE = Path(__file__).resolve().parent
OLD = HERE.parent / 'edge_linux_preflight_deployment_v1_20261103'
ROOT = '/public/home/jiangxinwei.zr/work/paper04'
NAMES = ('launch_preflight.py', 'worker.py', 'replay_io.py', 'remote_receiver.py', 'ACTIVE_SLICE_CARD.json')


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    (HERE / 'ACTIVE_SLICE_CARD.json').write_bytes(
        (HERE.parent / 'edge_linux_preflight_package_v1_20261103/ACTIVE_SLICE_CARD.json').read_bytes())
    files = {name: dict(bytes=(HERE/name).stat().st_size,
                       sha256=hashlib.sha256((HERE/name).read_bytes()).hexdigest()) for name in NAMES}
    contract = dict(schema='EDGE_PREFLIGHT_IO_REPAIR_V1', prior_job_id='181403',
                    cpu=1, memory_gib=6, wall_seconds=600, training=False,
                    formal_external_evaluation=False, allowed_new_jobs=1,
                    automatic_resubmission=False, method='C5_P3_UNCHANGED',
                    logical_endpoints=91, physical_prefix_packets=484214,
                    original_package_manifest_sha256='f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6',
                    scratch='VALIDATED_NODE_LOCAL_ONLY_NO_SHARED_FALLBACK',
                    cache='COMPLETE_ROLES_ONLY_BINDING_AND_BYTE_PINS', files=files)
    write(HERE / 'REPAIR_CONTRACT.json', contract)
    delivery = json.loads((OLD/'DELIVERY.json').read_text(encoding='utf-8-sig'))
    delivery.update(schema='EDGE_PREFLIGHT_IO_REPAIR_DELIVERY_V1',
        status='READY_NOT_SUBMITTED', remote_port=18819,
        remote_directory=ROOT+'/runs/'+HERE.name,
        receiver_source_sha256=files['remote_receiver.py']['sha256'],
        repaired_prior_job_id='181403', automatic_resubmission=False)
    delivery.pop('bootstrap_sha256', None)
    write(HERE / 'DELIVERY.json', delivery)
    private = HERE / '.private'
    private.mkdir(exist_ok=True)
    connection = json.loads((OLD/'.private/connection.json').read_text(encoding='utf-8-sig'))
    connection['remote_port'] = 18819
    write(private/'connection.json', connection)
    contents = {name: base64.b64encode((HERE/name).read_bytes()).decode('ascii')
                for name in (*NAMES, 'REPAIR_CONTRACT.json')}
    encoded = base64.b64encode(zlib.compress(json.dumps(contents).encode(), 9)).decode('ascii')
    bootstrap = '''import base64,hashlib,json,os,pathlib,platform,subprocess,zlib
assert platform.system() == 'Linux', 'LINUX_TERMINAL_REQUIRED'
root=pathlib.Path(ROOT_LITERAL)
here=root/'runs'/NAME_LITERAL
old=root/'runs'/'edge_linux_preflight_deployment_v1_20261103'
assert hashlib.sha256((old/'remote_receiver.py').read_bytes()).hexdigest() == 'e33aae00c97ab52d8ed51a9c4650c00cea845890755f26b0ba71bf8412892a80'
assert json.loads((old/'SUBMIT_RECEIPT.json').read_text())['job_id'] == '181403'
contents=json.loads(zlib.decompress(base64.b64decode(PAYLOAD_LITERAL)))
here.mkdir(mode=0o700,exist_ok=False)
for name,content in contents.items():
    assert pathlib.PurePosixPath(name).name == name
    with (here/name).open('xb') as out: out.write(base64.b64decode(content))
contract=json.loads((here/'REPAIR_CONTRACT.json').read_text())
for name,pin in contract['files'].items():
    data=(here/name).read_bytes()
    assert len(data) == pin['bytes'] and hashlib.sha256(data).hexdigest() == pin['sha256']
config=json.loads((old/'.receiver_private.json').read_text())
with os.fdopen(os.open(here/'.receiver_private.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as out: json.dump(config,out)
with (here/'receiver.log').open('xb') as out:
    child=subprocess.Popen(['/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python','-X','utf8','-B',str(here/'remote_receiver.py')],cwd=here,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
(here/'RECEIVER_PID.json').write_text(json.dumps({'pid':child.pid,'port':18819,'new_jobs_allowed':1}))
print('EDGE_IO_REPAIR_RECEIVER_STARTED',flush=True)
'''.replace('ROOT_LITERAL', repr(ROOT)).replace('NAME_LITERAL', repr(HERE.name)).replace('PAYLOAD_LITERAL', repr(encoded))
    (private/'bootstrap.py').write_text(bootstrap, encoding='utf-8')
    compile(bootstrap, 'bootstrap.py', 'exec')
    source64=base64.b64encode(zlib.compress(bootstrap.encode(),9)).decode('ascii')
    command="/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -X utf8 -B -c " + shlex.quote(
        "import base64,zlib;exec(compile(zlib.decompress(base64.b64decode(" + repr(source64) + ")),'<edge-io-repair-bootstrap>','exec'))")
    (HERE/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n',encoding='utf-8')
    write(HERE/'BOOTSTRAP_MANIFEST.json',dict(
        transferred_files={name:dict(bytes=len(base64.b64decode(data)),
            sha256=hashlib.sha256(base64.b64decode(data)).hexdigest()) for name,data in contents.items()},
        bootstrap_sha256=hashlib.sha256(bootstrap.encode()).hexdigest(),
        transfer_contains_credentials=False, full_inputs_reuploaded=False,
        receiver_port=18819, prior_namespace_unchanged=True, jobs_submitted=0))
    print('REPAIR_DELIVERY_FROZEN_SMALL_FILES_ONLY')


if __name__ == '__main__':
    main()
