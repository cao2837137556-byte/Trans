"""Prepare a checksummed package and a pasteable bootstrap for an authenticated terminal."""
import argparse
import ast
import base64
import gzip
import hashlib
import io
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import tarfile
import tempfile
import textwrap
import zlib

from common_round1 import (HERE, PYTHON, ROOT, RUN, artifact, dump, load, require, sha,
                           verify_package, write_text)
BASE_FILES = [
    'CONFIG.json', 'INPUT_PINS.json', 'EXPECTED_BASELINE.json', 'README.md', 'common_round1.py',
    'dispatch.py', 'calibration.py', 'evaluation.py', 'analysis_core.py', 'reference_assets.py',
    'worker.py', 'run.slurm',
]
RELAY_PORT = 18886


def pack(private):
    names = sorted(BASE_FILES)
    for n in names:
        data = (HERE / n).read_bytes()
        require(b'\r' not in data, 'NOT_LF:' + n)
        if n.endswith('.py'):
            ast.parse(data, filename=n, feature_version=(3, 10))
    manifest = dict(files={name: sha(HERE / name) for name in names},
                    parent_commit=load(HERE / 'CONFIG.json')['parent_commit'],
                    purpose='same-normal-reference threshold recalibration', text_bytes='UTF-8 and LF')
    dump(HERE / 'PACKAGE_MANIFEST.json', manifest)
    names.append('PACKAGE_MANIFEST.json')
    path = private / (RUN + '.tar.gz')
    temp = path.with_suffix('.tmp')
    with temp.open('wb') as f, gzip.GzipFile(fileobj=f, mode='wb', filename='', mtime=0) as gz, \
            tarfile.open(fileobj=gz, mode='w', format=tarfile.USTAR_FORMAT) as tar:
        for name in names:
            blob = (HERE / name).read_bytes()
            info = tarfile.TarInfo(name)
            info.size, info.mtime, info.mode = len(blob), 0, 0o600
            tar.addfile(info, io.BytesIO(blob))
    temp.replace(path)
    with tempfile.TemporaryDirectory(prefix='paper04-round1-') as tmp:
        extracted = Path(tmp)
        with tarfile.open(path, 'r:gz') as tar:
            require([m.name for m in tar] == names and all(m.isfile() for m in tar), 'BUNDLE_MEMBER_CLOSURE')
            for name in names:
                p = extracted / name
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(tar.extractfile(name).read())
        require(verify_package(extracted) == manifest and
                sha(extracted / 'PACKAGE_MANIFEST.json') == sha(HERE / 'PACKAGE_MANIFEST.json'),
                'BUNDLE_REEXTRACTION_SHA')
        p = subprocess.run([os.sys.executable, '-X', 'utf8', '-B', 'worker.py', '--help'],
                           cwd=extracted, check=True, capture_output=True, text=True)
        require('--project' in p.stdout, 'EXTRACTED_IMPORT')
    return path, manifest


def bootstrap(private, archive, python):
    cfg = dict(port=RELAY_PORT, project=ROOT.as_posix(), run=RUN,
               token=secrets.token_hex(32), sha256=sha(archive), bytes=archive.stat().st_size)
    local_cfg = private / 'connection.json'
    if local_cfg.is_file():
        prev = load(local_cfg)
        if prev['sha256'] == cfg['sha256']:
            cfg['token'] = prev['token']
    dump(local_cfg, cfg)
    relay = (HERE / 'relay.py').read_bytes()
    ast.parse(relay)
    packed = base64.b64encode(zlib.compress(relay, 9)).decode('ascii')
    relay_dir = (ROOT / 'runs' / ('.' + RUN + '_relay_' + cfg['sha256'][:12])).as_posix()
    code = textwrap.dedent(f"""
        import base64, hashlib, json, os, socket, subprocess, sys, time, zlib
        from pathlib import Path
        os.umask(0o077)
        relay_dir = Path({relay_dir!r})
        config = {cfg!r}
        payload = zlib.decompress(base64.b64decode({packed!r}))
        if hashlib.sha256(payload).hexdigest() != {hashlib.sha256(relay).hexdigest()!r}:
            raise RuntimeError('RELAY_SOURCE_SHA')
        relay_dir.mkdir(exist_ok=True)
        for name, data in [('relay.py', payload), ('connection.json', json.dumps(config, indent=2).encode())]:
            p = relay_dir / name
            if p.exists() and p.read_bytes() != data:
                raise RuntimeError('EXISTING_RELAY_DIFFERS:' + name)
            if not p.exists():
                p.write_bytes(data)
        try:
            with socket.create_connection(('127.0.0.1', config['port']), timeout=1):
                print('ROUND1_RELAY_PORT_ALREADY_LISTENING', config['port'])
        except OSError:
            with (relay_dir / 'relay.log').open('ab') as log:
                proc = subprocess.Popen([sys.executable, '-X', 'utf8', '-B', str(relay_dir / 'relay.py')],
                                        stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            for _ in range(30):
                if proc.poll() is not None:
                    raise RuntimeError('RELAY_START_FAILED:' + str(relay_dir / 'relay.log'))
                try:
                    with socket.create_connection(('127.0.0.1', config['port']), timeout=1):
                        print('ROUND1_RELAY_READY', config['port'])
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError('RELAY_START_TIMEOUT')
        print('ROUND1_RELAY_LOG', relay_dir / 'relay.log')
        """).strip() + '\n'
    ast.parse(code)
    launcher = shlex.quote(python.as_posix()) + ' -X utf8 -B - <<\'PAPER04_ROUND1_BOOTSTRAP\'\n'
    cmd = ('(\n  set -o pipefail\n  umask 077\n  {\n'
           + launcher + code + 'PAPER04_ROUND1_BOOTSTRAP\n'
           + '  rc=$?\n  printf "ROUND1_BOOTSTRAP_EXIT=%s\\n" "$rc"\n  exit "$rc"\n'
           + '  } 2>&1 | tee -a ' + shlex.quote((ROOT / 'runs' / ('.' + RUN + '_bootstrap.log')).as_posix()) + '\n)\n')
    file = private / 'HPC_TERMINAL.sh'
    write_text(file, cmd)
    # A single line avoids the remote terminal's multiline paste prompt.
    wrapped = base64.b64encode(zlib.compress(cmd.encode('utf-8'), 9)).decode('ascii')
    launcher_code = ('import base64, subprocess, sys, zlib; '
                     'sys.exit(subprocess.run(["bash"], input=zlib.decompress(base64.b64decode('
                     + repr(wrapped) + '))).returncode)')
    ast.parse(launcher_code)
    write_text(private / 'HPC_TERMINAL_ONE_LINE.txt', ' ' + shlex.quote(python.as_posix())
               + ' -X utf8 -B -c ' + shlex.quote(launcher_code))
    return file


def main():
    args = argparse.ArgumentParser()
    args.add_argument('--bash', required=True)
    a = args.parse_args()
    private = HERE / '.private'
    private.mkdir(exist_ok=True)
    archive, manifest = pack(private)
    terminal = bootstrap(private, archive, PYTHON)
    for file in [HERE / 'run.slurm', terminal, private / 'HPC_TERMINAL_ONE_LINE.txt']:
        # Git for Windows bash receives a relative path from the package directory.
        subprocess.run([a.bash, '-n', file.relative_to(HERE).as_posix()], cwd=HERE, check=True)
    dump(HERE / 'PACKAGE_RECEIPT.json', dict(status='PREPARED_NOT_SUBMITTED',
         package=artifact(archive), package_local_path=str(archive),
         manifest_sha256=sha(HERE / 'PACKAGE_MANIFEST.json'), files=len(manifest['files']),
         clean_reextraction=True, lf=True, python_ast_and_extracted_import=True,
         local_tool_sha256={name: sha(HERE / name) for name in
                           ('relay.py', 'local_client.py', 'start_local.py', 'dashboard.py', 'progress.html')},
         bash_syntax=True, sbatch_test_only='pending actual login node',
         real_compute_slice='pending actual Slurm job', new_job_ids=[]))
    print('PACKAGE_PREPARED', archive.stat().st_size, sha(archive))


if __name__ == '__main__':
    main()
