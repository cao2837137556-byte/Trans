"""Resume one pinned Motion asset through the existing user-established tunnel."""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import threading

LIMIT = 4 * 1024**2
RAW_SHA = 'e1a9de0a5eb30c72c26309edbb1345b9b1116bee3ab2937de2f88b549e8aaa1b'
ARCHIVE_SHA = '99dce213bbb215e3e107bac3abbdf9eee6dd6dad494cc61d0350c5456efa0be4'
ARCHIVE_BYTES = 338708100
CARD_SHA = '3a346a76bc05d8428a60dbd0e73c7951463d21b2452230b12e620b59088e5368'
RUN = 'unified_reference_bank_k8192_v1_20261113'
FAILED_PREP_JOB = '183971'
REPAIR_RUN = RUN + '_repair_' + FAILED_PREP_JOB


def digest(path):
    sha = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            sha.update(block)
    return sha.hexdigest()


def load(path):
    return json.loads(path.read_text()) if path.is_file() else None


def save(path, value):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(value) + '\n')
    temporary.replace(path)


def install(stage, archive_stage, target, data, failed_job):
    project = stage.parent.parent
    if target.exists():
        receipt = load(target / 'INSTALL.json')
        if (receipt and receipt['archive_sha256'] == hashlib.sha256(data).hexdigest() and
                (target/'CONTROLLER_PID.json').is_file()):
            return receipt
        raise ValueError('RUN_EXISTS_RECONCILE_BEFORE_LAUNCH')
    upload = stage / 'package.tar.gz'
    if not upload.exists():
        with upload.open('xb') as stream:
            stream.write(data)
    if hashlib.sha256(data).hexdigest() != digest(upload):
        raise ValueError('PACKAGE_DIFFERS')
    scratch = stage / 'extract'
    scratch.mkdir()
    with tarfile.open(upload, 'r:gz') as archive:
        members = archive.getmembers()
        names = {item.name for item in members}
        if len(names) != len(members) or len(members) > 240 or sum(m.size for m in members) > 48*1024**2:
            raise ValueError('PACKAGE_MEMBER_COUNT_OR_BYTES')
        for item in members:
            path = PurePosixPath(item.name)
            if not item.isfile() or not path.parts or path.is_absolute() or '..' in path.parts:
                raise ValueError('UNSAFE_PACKAGE_MEMBER')
            dest = scratch / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as source, dest.open('xb') as stream:
                shutil.copyfileobj(source, stream, length=1024**2)
    manifest = load(scratch / 'PACKAGE_MANIFEST.json')
    if (manifest['card_sha256'] != CARD_SHA or digest(scratch / 'freeze.md') != CARD_SHA or
            set(manifest['files']) | {'PACKAGE_MANIFEST.json'} != names or
            not {'dispatch.py', 'run.slurm', 'worker.py'}.issubset(names)):
        raise ValueError('PACKAGE_MANIFEST_SCOPE')
    for name, sha in manifest['files'].items():
        if digest(scratch / name) != sha:
            raise ValueError('PACKAGE_MEMBER_SHA:' + name)
    target.mkdir()
    scratch.rename(target / 'package')
    receipt = dict(status='INSTALLED', project=str(project), run=target.name, archive_sha256=digest(upload),
                   package_manifest_sha256=digest(target / 'package' / 'PACKAGE_MANIFEST.json'))
    if failed_job:
        receipt['failed_prepare_job'] = failed_job
    save(target / 'INSTALL.json', receipt)
    with (target / 'dispatch.log').open('ab') as log:
        argv = [sys.executable, '-X', 'utf8', '-B',
                str(target / 'package' / 'dispatch.py'), str(project), str(target), str(archive_stage)]
        if failed_job:
            argv += ['--retry-prepare-job', failed_job]
        process = subprocess.Popen(argv,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    save(target / 'CONTROLLER_PID.json', dict(pid=process.pid))
    return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--retry-prepare-job', choices=(FAILED_PREP_JOB,))
    args = parser.parse_args()
    stage = args.stage.resolve()
    token = (stage / 'token').read_text().strip()
    if len(token) != 64:
        raise ValueError('INVALID_RELAY_TOKEN')
    archive_stage = stage.with_name('.' + RUN + '_motion_ingress') if args.retry_prepare_job else stage
    archive = archive_stage / 'motion.pcap.gz.part'
    final = archive_stage / 'motion.pcap.gz'
    lock = threading.Lock()
    target = stage.parent / (REPAIR_RUN if args.retry_prepare_job else RUN)

    def state():
        return dict(scope='P04_K8192_MOTION_V1', run=target.name, total_bytes=ARCHIVE_BYTES,
                    bytes=final.stat().st_size if final.exists() else
                    archive.stat().st_size if archive.exists() else 0,
                    complete=final.is_file(), raw_sha256=RAW_SHA)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def route(self):
            parts = self.path.strip('/').split('/')
            if len(parts) != 2 or not hmac.compare_digest(parts[0], token):
                raise PermissionError('MOTION_RELAY_AUTH')
            return parts[1]

        def respond(self, payload):
            data = json.dumps(payload).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            try:
                route = self.route()
                if route == 'state':
                    with lock:
                        status = state()
                    return self.respond(status)
                if route == 'experiment':
                    return self.respond(dict(install=load(target / 'INSTALL.json'),
                        chain=load(target / 'CHAIN_STATE.json'),
                        prep=load(target / 'PREP_RECEIPT.json'),
                        replay=load(target / 'REPLAY_RECEIPT.json'),
                        progress=load(target / 'PROGRESS.json'),
                        acceptance=load(target / 'ACCEPTANCE.json')))
                if route == 'results':
                    return self.respond(load(target / 'RETURN.json'))
                if route.startswith('result-'):
                    name = route.removeprefix('result-')
                    manifest = load(target / 'RETURN.json')
                    if manifest is None or Path(name).name != name or name not in manifest['files']:
                        raise ValueError('RESULT_SCOPE')
                    path = target / name
                    size = path.stat().st_size
                    if size > 32 * 1024**2:
                        raise ValueError('RESULT_TOO_LARGE')
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/octet-stream')
                    self.send_header('Content-Length', str(size))
                    self.end_headers()
                    with path.open('rb') as stream:
                        shutil.copyfileobj(stream, self.wfile, length=LIMIT)
                    return
                raise ValueError('MOTION_RELAY_ROUTE')
            except (ConnectionError, BrokenPipeError):
                pass
            except (OSError, ValueError) as err:
                self.send_error(409, str(err))

        def do_POST(self):
            try:
                route = self.route()
                if route == 'install':
                    size = int(self.headers['Content-Length'])
                    if not 0 < size <= LIMIT:
                        raise ValueError('PACKAGE_COMPRESSED_BYTES')
                    data = self.rfile.read(size)
                    if len(data) != size or hashlib.sha256(data).hexdigest() != self.headers['X-SHA256']:
                        raise ValueError('PACKAGE_UPLOAD_SHA')
                    with lock:
                        receipt = install(stage, archive_stage, target, data, args.retry_prepare_job)
                    return self.respond(receipt)
                if args.retry_prepare_job:
                    raise ValueError('REPAIR_USES_EXISTING_VERIFIED_MOTION')
                if route == 'finish':
                    with lock:
                        path = final if final.is_file() else archive
                        if path.stat().st_size != ARCHIVE_BYTES or digest(path) != ARCHIVE_SHA:
                            raise ValueError('MOTION_ARCHIVE_SHA_OR_BYTES')
                        if path == archive:
                            archive.rename(final)
                        info = dict(state(), status='VERIFIED_MOTION_ARCHIVE',
                                    archive_sha256=ARCHIVE_SHA)
                        save(stage / 'MOTION_REMOTE.json', info)
                    return self.respond(info)
                if route != 'upload':
                    raise ValueError('MOTION_RELAY_ROUTE')
                size = int(self.headers['Content-Length'])
                start = int(self.headers['X-Offset'])
                if not 0 < size <= LIMIT or not 0 <= start <= ARCHIVE_BYTES-size:
                    raise ValueError('MOTION_UPLOAD_RANGE')
                data = self.rfile.read(size)
                if len(data) != size or hashlib.sha256(data).hexdigest() != self.headers['X-SHA256']:
                    raise ValueError('MOTION_CHUNK_SHA')
                with lock:
                    status = state()
                    if status['complete'] or start != status['bytes']:
                        raise ValueError('MOTION_UPLOAD_OFFSET')
                    with archive.open('ab') as stream:
                        stream.write(data)
                self.respond(dict(bytes=start+size))
            except (ConnectionError, BrokenPipeError):
                pass
            except (OSError, ValueError, TypeError) as err:
                self.send_error(409, str(err))

    os.umask(0o077)
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        server.timeout = 10
        timer = threading.Timer(3 * 86400, server.shutdown)
        timer.daemon = True
        timer.start()
        print('P04_K8192_MOTION_INGRESS_READY', flush=True)
        server.serve_forever()


if __name__ == '__main__':
    main()
