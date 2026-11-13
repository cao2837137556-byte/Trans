"""Loopback-only relay used through the user's already established SSH forwarding."""
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
import time

HOME = Path(__file__).resolve().parent
CFG = json.loads((HOME / 'connection.json').read_text())
PROJECT = Path(CFG['project'])
TARGET = PROJECT / 'runs' / CFG['run']
ARCHIVE = HOME / 'upload.tar.gz.part'
LIMIT = 512 * 1024
lock = threading.Lock()


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def save(path, value):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=True), encoding='utf-8')
    temp.replace(path)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def offset():
    return ARCHIVE.stat().st_size if ARCHIVE.is_file() else 0


def file_manifest(folder):
    return read(folder / 'PACKAGE_MANIFEST.json')['files']


def install():
    with lock:
        need(offset() == CFG['bytes'] and digest(ARCHIVE) == CFG['sha256'], 'ARCHIVE_SHA_OR_SIZE')
        stage = HOME / 'extract'
        if not stage.exists():
            stage.mkdir()
            with tarfile.open(ARCHIVE, 'r:gz') as tar:
                members = tar.getmembers()
                names = set()
                for m in members:
                    p = PurePosixPath(m.name)
                    need(m.isfile() and m.name == p.as_posix() and not p.is_absolute() and
                         '..' not in p.parts and len(p.parts) <= 3 and m.name not in names and
                         m.size <= 12 * 1024 ** 2, 'ARCHIVE_MEMBER_SCOPE')
                    names.add(m.name)
                need(sum(m.size for m in members) <= 28 * 1024 ** 2, 'ARCHIVE_SIZE')
                for m in members:
                    path = stage / m.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(m) as src, path.open('xb') as dst:
                        shutil.copyfileobj(src, dst, length=LIMIT)
            files = file_manifest(stage)
            need(set(files) | {'PACKAGE_MANIFEST.json'} == names, 'ARCHIVE_CLOSURE')
        files = file_manifest(stage)
        for name, sha in files.items():
            p = stage / name
            need(digest(p) == sha and b'\r' not in p.read_bytes(), 'EXTRACTED_INPUT:' + name)
        receipt = TARGET / 'INSTALL.json'
        package_sha = digest(stage / 'PACKAGE_MANIFEST.json')
        if TARGET.exists():
            known = read(receipt)
            need(known and known['package_manifest_sha256'] == package_sha, 'EXISTING_RUN_IDENTITY_UNPROVEN')
            for name, sha in files.items():
                need(digest(TARGET / 'package' / name) == sha, 'INSTALLED_TARGET_DIFFERS:' + name)
            need(digest(TARGET / 'package' / 'PACKAGE_MANIFEST.json') == package_sha, 'INSTALLED_MANIFEST_DIFFERS')
        else:
            TARGET.mkdir()
            shutil.copytree(stage, TARGET / 'package')
            save(receipt, dict(status='PASS', archive_sha256=CFG['sha256'], package_manifest_sha256=package_sha))
        intent = TARGET / 'DISPATCH_INTENT.json'
        if not intent.exists():
            save(intent, dict(created_unix=time.time(), package_manifest_sha256=package_sha))
            with (TARGET / 'dispatch.log').open('ab') as log:
                proc = subprocess.Popen([sys.executable, '-X', 'utf8', '-B',
                    str(TARGET / 'package' / 'dispatch.py'), '--control', str(TARGET), '--project', str(PROJECT)],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
            save(TARGET / 'DISPATCH_PID.json', dict(pid=proc.pid))
        return dict(status='INSTALLED', package_manifest_sha256=package_sha)


def status():
    chain = read(TARGET / 'CHAIN_STATE.json')
    if chain is None:
        chain = dict(stage='INSTALLING' if (TARGET / 'INSTALL.json').is_file() else 'WAITING_UPLOAD')
    phase = chain.get('phase', 'first')
    phase = phase if phase in ('first', 'eval') else 'first'
    out = TARGET / 'results'
    dispatch = read(TARGET / 'DISPATCH_PID.json')
    if dispatch and chain.get('stage') not in ('ACCEPTED', 'PARTIAL_C0_FAILED', 'STOP'):
        try:
            os.kill(dispatch['pid'], 0)
        except ProcessLookupError:
            chain = dict(chain, stage='STOP', error='DISPATCH_PROCESS_EXITED_WITHOUT_COMPLETION')
    return dict(chain, remote_root=str(TARGET), uploaded_bytes=offset(), total_bytes=CFG['bytes'],
                current_progress=(read(TARGET / 'REMOTE_ADMISSION_PROGRESS.json')
                                  if chain['stage'] == 'VERIFYING_REMOTE_INPUTS' else
                                  read(out / ('PROGRESS_' + phase + '.json'))),
                jobs={p: read(TARGET / ('JOB_' + p + '.json')) for p in ('first', 'eval')},
                dispatch=dispatch,
                has_pullback=(TARGET / 'PULLBACK_MANIFEST.json').is_file())


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def route(self):
        pieces = self.path.strip('/').split('/', 2)
        need(len(pieces) >= 2 and hmac.compare_digest(pieces[0], CFG['token']), 'RELAY_AUTH')
        return pieces[1:]

    def body(self, b, fmt='application/json'):
        self.send_response(200)
        self.send_header('Content-Type', fmt)
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def respond(self, item):
        self.body(json.dumps(item, ensure_ascii=True).encode())

    def do_GET(self):
        try:
            route = self.route()
            if route == ['state']:
                return self.respond(status())
            manifest = read(TARGET / 'PULLBACK_MANIFEST.json')
            if route == ['manifest']:
                need(manifest is not None, 'PULLBACK_NOT_READY')
                return self.respond(manifest)
            need(len(route) == 2 and route[0] == 'result' and manifest and route[1] in manifest['files'],
                 'RESULT_NOT_IN_MANIFEST')
            p = TARGET / route[1]
            size = p.stat().st_size
            need(p.is_file() and size <= 32 * 1024 ** 2, 'RESULT_SIZE_OR_MISSING')
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Length', str(size))
            self.end_headers()
            with p.open('rb') as stream:
                shutil.copyfileobj(stream, self.wfile, length=LIMIT)
        except (ConnectionError, BrokenPipeError):
            pass
        except Exception as exc:
            self.send_error(409, str(exc)[:300])

    def do_POST(self):
        try:
            route = self.route()
            if route == ['install']:
                return self.respond(install())
            need(route == ['upload'], 'INVALID_UPLOAD_ROUTE')
            length = int(self.headers['Content-Length'])
            start = int(self.headers['X-Offset'])
            need(0 < length <= LIMIT, 'UPLOAD_CHUNK_SIZE')
            block = self.rfile.read(length)
            need(len(block) == length and hashlib.sha256(block).hexdigest() == self.headers['X-SHA256'],
                 'UPLOAD_CHUNK_SHA')
            with lock:
                need(start == offset() and start + length <= CFG['bytes'], 'UPLOAD_OFFSET')
                with ARCHIVE.open('ab') as f:
                    f.write(block)
            return self.respond(dict(bytes=start + length))
        except (ConnectionError, BrokenPipeError):
            pass
        except Exception as exc:
            self.send_error(409, str(exc)[:300])


if __name__ == '__main__':
    os.umask(0o077)
    server = ThreadingHTTPServer(('127.0.0.1', CFG['port']), Handler)
    timer = threading.Timer(2 * 86400, server.shutdown)
    timer.daemon = True
    timer.start()
    print('ROUND1_RELAY_READY', flush=True)
    server.serve_forever()
