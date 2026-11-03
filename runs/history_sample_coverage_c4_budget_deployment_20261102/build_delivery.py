"""Prepare a code-only delivery over the user's existing authenticated tunnel."""
import ast
import base64
import hashlib
import io
import json
from pathlib import Path
import secrets
import sys
import tarfile
import zlib

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE = HERE.parent/'history_sample_coverage_c4_batch_resume_v1_20261102'
REMOTE = '/public/home/jiangxinwei.zr/work/paper04'
PYTHON = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8-sig'))


def write(p, v):
    Path(p).write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def pack(b):
    return base64.b64encode(zlib.compress(b, 9)).decode()


def relocate(v, data):
    if isinstance(v, dict):
        return {k:('/share/software/tshark-4.6.6/bin/tshark' if k == 'tshark' else relocate(x, data)) for k,x in v.items()}
    if isinstance(v, list):
        return [relocate(x, data) for x in v]
    if isinstance(v, str):
        n = v.replace('\\', '/')
        for local, remote in ((ROOT.as_posix(), REMOTE), (data.as_posix(), REMOTE+'/data_external/unsw_iotraffic_2025')):
            if n == local or n.startswith(local+'/'):
                return remote+n[len(local):]
    return v


def main():
    assert not (HERE/'DELIVERY_MANIFEST.json').exists(), 'DELIVERY_ONCE'
    sys.path.insert(0, str(PACKAGE))
    import run
    from hnr.common import digest
    card = run.verify('evaluate')
    run.budget_plan(card)
    assert read(PACKAGE/'IMPLEMENTATION_CHECK.json')['status'] == 'PASS'
    original = read(PACKAGE/'config/EXECUTION.json')
    mapped = relocate(original, Path(original['devices'][0]['raw']['path']).parent.parent)
    assert digest(run.semantic(mapped)) == card['config_semantic_sha256'], 'MAPPED_SCIENCE_SAME'
    script = (PACKAGE/'hpc/run_encode.slurm').read_bytes()
    assert b'\r' not in script and b'--time=05:00:00' in script
    names = sorted(set(card['code_sha256']) | {'EXECUTION_CARD.json', 'EXECUTION_CARD.json.sha256',
        'config/EXECUTION.json', 'IMPLEMENTATION_CHECK.json', 'BUDGET_SEAL_RECEIPT.json'})
    files = {}
    with tarfile.open(HERE/'bundle.tar', 'x:') as ar:
        for name in names:
            payload = (json.dumps(mapped, indent=2)+'\n').encode() if name == 'config/EXECUTION.json' else (PACKAGE/name).read_bytes()
            files[name] = dict(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
            info = tarfile.TarInfo(name); info.size = len(payload); info.mode = 0o600
            ar.addfile(info, io.BytesIO(payload))
    private = HERE/'.private'; private.mkdir(exist_ok=True)
    previous = read(HERE.parent/'history_sample_coverage_c4_preflight_repair_20261102/.private/connection.json')
    connection = dict(token=secrets.token_hex(24), socks_port=previous['socks_port'])
    write(private/'connection.json', connection)
    deployment_check = read(HERE/'DEPLOYMENT_ENGINEERING_RECEIPT.json')
    assert deployment_check['exit_code'] == 0
    assert all(sha(HERE/name) == expected for name,expected in deployment_check['source_sha256'].items()), 'DEPLOYMENT_CHECKED_CODE_PIN'
    test_modules = sorted(p.stem for p in PACKAGE.glob('test_*.py')) + sorted(p.stem for p in HERE.glob('test_*.py'))
    config = dict(token=connection['token'], bundle=dict(bytes=(HERE/'bundle.tar').stat().st_size, sha256=sha(HERE/'bundle.tar')),
                  files=files, execution_card_sha256=sha(PACKAGE/'EXECUTION_CARD.json'),
                  preflight_worker_sha256=sha(HERE/'preflight_worker.py'), test_modules=test_modules,
                  expected_test_count=read(PACKAGE/'IMPLEMENTATION_CHECK.json')['tests_run']+deployment_check['tests_run'],
                  environment_sha256='8da8564e759d51df121eaf9230a3e34c358e3abd10d9ce8dc8fe4b92e0763fcf',
                  previous_hpc_config_sha256='b2c80539fa91008191cecb1fa81899e0ce49e3a3f0c764a05d98677b7bed7c3d')
    write(private/'receiver_config.json', config)
    bootstrap_names = ('controller.py', 'preflight_worker.py', 'client.py', 'pipeline.py',
                       'test_controller.py', 'test_pipeline.py', 'test_preflight_worker.py', 'test_client.py')
    boot_files = {n:pack((HERE/n).read_bytes()) for n in bootstrap_names}
    for n in boot_files:
        ast.parse((HERE/n).read_text(encoding='utf-8'))
    remote_dir = REMOTE+'/runs/'+HERE.name
    launch = (
        'import base64,zlib,json,pathlib,subprocess;'
        'd=pathlib.Path('+repr(remote_dir)+');d.mkdir(parents=True,exist_ok=True);'
        'items=json.loads(zlib.decompress(base64.b64decode('+repr(pack(json.dumps(boot_files).encode()))+')));'
        'assert not any((d/k).exists() for k in items);'
        '[(d/k).write_bytes(zlib.decompress(base64.b64decode(v))) for k,v in items.items()];'
        'q=d/".private";q.mkdir(exist_ok=True);c=q/"receiver_config.json";assert not c.exists();'
        'c.write_bytes(zlib.decompress(base64.b64decode('+repr(pack(json.dumps(config).encode()))+')));c.chmod(0o600);'
        'f=(d/"controller.log").open("ab");'
        'subprocess.Popen(['+repr(PYTHON)+',"-u","-B","-c",'
        '"import sys;sys.path.insert(0,"+repr(str(d))+");from controller import main,read;main(read("+repr(str(c))+"))"],'
        'stdin=subprocess.DEVNULL,stdout=f,stderr=f,start_new_session=True);'
        'print("C4_BUDGET_CONTROL_STARTED")')
    ast.parse(launch)
    command = PYTHON+' -B -c "import base64,zlib;exec(zlib.decompress(base64.b64decode(\''+pack(launch.encode())+'\')))"'
    (HERE/'RUN_IN_HPC_TERMINAL.txt').write_text(command+'\n', encoding='utf-8')
    write(HERE/'DELIVERY_MANIFEST.json', dict(state='READY_NOT_SUBMITTED', bundle=config['bundle'],
          files=files, raw_asset_bytes_transferred=0, execution_card_sha256=config['execution_card_sha256'],
          remote_deployment=remote_dir, command_sha256=sha(HERE/'RUN_IN_HPC_TERMINAL.txt'),
          command_characters=len(command), controller_sha256=sha(HERE/'controller.py'),
          preflight_worker_sha256=config['preflight_worker_sha256']))
    print(json.dumps(dict(status='READY_NOT_SUBMITTED', code_bytes=config['bundle']['bytes'],
                          files=len(files), raw_asset_bytes=0, command_characters=len(command))))


if __name__ == '__main__':
    main()
