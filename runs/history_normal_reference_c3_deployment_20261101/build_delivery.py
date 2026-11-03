"""Package only new C3 files. Existing HPC scientific sources remain immutable."""
import base64
import hashlib
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tarfile
import zlib

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent / 'history_normal_reference_c3_small_bank_v1_20261101'


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def write(p, value): Path(p).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    card = read(PACKAGE / 'EXECUTION_CARD.json')
    for name, expected in card['code_sha256'].items(): assert sha(PACKAGE / name) == expected
    assert read(PACKAGE / 'IMPLEMENTATION_CHECK.json')['execution_card_sha256'] == sha(PACKAGE / 'EXECUTION_CARD.json')
    assert read(PACKAGE / 'PREPARE_RUNTIME.json')['status'] == 'COMPLETE'
    assert read(PACKAGE / 'prepared/PREPARE_RESULT.json')['new_rows'] == 278
    tested = subprocess.run([sys.executable, '-B', str(HERE / 'test_delivery.py'), '-v'], capture_output=True, text=True)
    (HERE / 'DELIVERY_TESTS.log').write_text(tested.stdout + tested.stderr, encoding='utf-8')
    assert tested.returncode == 0 and 'Ran 5 tests' in tested.stderr
    request = dict(candidate=card['candidate'], prepared_sha256={p.name: sha(p) for p in (PACKAGE / 'prepared').iterdir() if p.is_file()},
                   execution_card_sha256=sha(PACKAGE / 'EXECUTION_CARD.json'), new_rows=278, new_TCP=212, new_UDP=66,
                   expected_HPC_environment=dict(python='3.11.11', numpy='2.0.1', torch='2.5.1'),
                   expected_HPC_C1_config_sha256='b2c80539fa91008191cecb1fa81899e0ce49e3a3f0c764a05d98677b7bed7c3d')
    write(PACKAGE / 'ENCODE_REQUEST.json', request)
    names = list(card['code_sha256']) + ['EXECUTION_CARD.json', 'EXECUTION_CARD.json.sha256', 'INPUT_MANIFEST.json', 'INPUT_MANIFEST.json.sha256',
        'IMPLEMENTATION_CHECK.json', 'TESTS.log', 'ENCODE_REQUEST.json', 'PREPARE_RUNTIME.json', 'PREPARE_ATTEMPT.json']
    names += ['prepared/' + p.name for p in (PACKAGE / 'prepared').iterdir() if p.is_file()]
    files = {name: dict(bytes=(PACKAGE / name).stat().st_size, sha256=sha(PACKAGE / name)) for name in sorted(names)}
    bundle = HERE / 'bundle.tar'
    with tarfile.open(bundle, 'w') as out:
        for name in sorted(files): out.add(PACKAGE / name, arcname=name, recursive=False)
    private = HERE / '.private'; private.mkdir(exist_ok=True)
    config_file = private / 'connection.json'
    if config_file.exists(): connection = read(config_file)
    else:
        connection = dict(token=secrets.token_hex(24), socks_port=61324); write(config_file, connection)
    config = dict(token=connection['token'], bundle_sha256=sha(bundle), bundle_bytes=bundle.stat().st_size, files=files)
    payload = base64.b64encode(zlib.compress((HERE / 'receiver.py').read_bytes(), 9)).decode()
    packed_config = base64.b64encode(zlib.compress(json.dumps(config).encode(), 9)).decode()
    command = '/share/software/miniconda3.2025/envs/torch_demo_2025/bin/python -c "import base64,zlib,json;exec(zlib.decompress(base64.b64decode(\'' + payload + '\')));main(json.loads(zlib.decompress(base64.b64decode(\'' + packed_config + '\'))))"'
    (HERE / 'RUN_IN_HPC_TERMINAL.txt').write_text(command + '\n', encoding='utf-8')
    write(HERE / 'DELIVERY_MANIFEST.json', dict(files=files, bundle_bytes=config['bundle_bytes'], bundle_sha256=config['bundle_sha256'],
        receiver_sha256=sha(HERE / 'receiver.py'), bootstrap_sha256=sha(HERE / 'RUN_IN_HPC_TERMINAL.txt'), tests_passed=5,
        command_characters=len(command), state='READY_TO_DELIVER_NOT_SUBMITTED'))
    print(json.dumps(dict(state='READY_TO_DELIVER_NOT_SUBMITTED', files=len(files), bundle_bytes=config['bundle_bytes'], tests=5, command_characters=len(command))))


if __name__ == '__main__': main()
