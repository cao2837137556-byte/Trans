"""Exercise the real local relay, archive installation, resume and result route."""
import hashlib
import http.client
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

from common_round1 import HERE, RUN, dump, require, sha


def main():
    archive = HERE / '.private' / (RUN + '.tar.gz')
    with tempfile.TemporaryDirectory(prefix='p04-round1-relay-') as tmp:
        test = Path(tmp)
        project = test / 'project'
        (project / 'runs').mkdir(parents=True)
        target = project / 'runs' / RUN
        relay = test / 'relay'
        relay.mkdir()
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        token = 'isolated-test-token'
        shutil.copyfile(HERE / 'relay.py', relay / 'relay.py')
        dump(relay / 'connection.json', dict(project=str(project), run=RUN, port=port,
                                             token=token, sha256=sha(archive), bytes=archive.stat().st_size))
        proc = subprocess.Popen([sys.executable, '-B', str(relay / 'relay.py')],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def send(action, data=None, headers=None):
            with_response = http.client.HTTPConnection('127.0.0.1', port, timeout=10)
            try:
                with_response.request('GET' if data is None else 'POST', '/' + token + '/' + action,
                                      body=data, headers=headers or {})
                with with_response.getresponse() as r:
                    return r.status, r.read()
            finally:
                with_response.close()
        try:
            until = time.monotonic() + 5
            while True:
                try:
                    status, body = send('state')
                    require(status == 200 and json.loads(body)['uploaded_bytes'] == 0, 'RELAY_START')
                    break
                except OSError:
                    require(time.monotonic() < until and proc.poll() is None, 'RELAY_DID_NOT_START')
                    time.sleep(.1)
            require(send('install', b'')[0] == 409, 'PARTIAL_INSTALL_MUST_FAIL')
            data = archive.read_bytes()
            for start, chunk in [(0, data[:100]), (100, data[100:])]:
                headers = {'X-Offset': str(start), 'X-SHA256': hashlib.sha256(chunk).hexdigest()}
                require(send('upload', chunk, headers)[0] == 200, 'CHUNK_RESUME')
                require(send('upload', chunk, headers)[0] == 409, 'DUPLICATE_CHUNK_ACCEPTED')
            # Exercise refusal to overwrite an existing target, then idempotent install.
            target.mkdir()
            require(send('install', b'')[0] == 409, 'UNPROVEN_TARGET_ACCEPTED')
            target.rename(target.with_name('unproven-preserved'))
            # Use the extracted staged package and a matching receipt, as on restart.
            package = relay / 'extract'
            target.mkdir()
            shutil.copytree(package, target / 'package')
            dump(target / 'INSTALL.json', dict(package_manifest_sha256=sha(package / 'PACKAGE_MANIFEST.json')))
            dump(target / 'DISPATCH_INTENT.json', {'fixture': 'skip submission'})
            require(send('install', b'')[0] == 200, 'SAME_PACKAGE_RESUME')
            path = target / 'package' / 'CONFIG.json'
            path.write_text('{}', encoding='utf-8')
            require(send('install', b'')[0] == 409, 'DIFFERENT_INSTALLED_BYTES')
            proof = target / 'FINAL_ACCEPTANCE.json'
            dump(proof, {'fixture': True})
            dump(target / 'PULLBACK_MANIFEST.json', dict(files={proof.name: {'sha256': sha(proof)}}))
            require(send('result/' + proof.name) == (200, proof.read_bytes()), 'STREAM_RESULT')
            require(send('result/connection.json')[0] == 409, 'UNLISTED_RESULT')
        finally:
            proc.terminate()
            proc.wait(timeout=5)
    print('RELAY_LOCAL_CONTRACT_PASS')


if __name__ == '__main__':
    main()
