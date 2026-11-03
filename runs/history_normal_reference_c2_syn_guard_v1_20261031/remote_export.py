"""Temporary, loopback-only export of explicitly pinned existing C2 inputs.

Only reads original files. No experiment runner, inference, PCAP decode or job
submission. Temporary bundle is removed on expiry or successful retrieval.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import threading

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04')
PORT = 18792
LIMIT = 512 * 1024**2


def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(chunk)
    return value.hexdigest()


def main(request, token):
    assert request['schema'] == 'c2-fixed-saved-input-export-v1'
    assert len(token) == 32 and all(c in '0123456789abcdef' for c in token)
    records = []
    names = set()
    for item in request['files']:
        rel, name = item['remote_relative_path'], item['local_relative_path']
        assert all(not PurePosixPath(p).is_absolute() and '\\' not in p and
                   all(s not in ('', '.', '..') for s in p.split('/')) for p in (rel, name))
        path = ROOT / rel
        assert path.resolve().is_relative_to(ROOT.resolve()) and path.is_file()
        assert name not in names
        names.add(name)
        actual = sha(path)
        assert actual == item['sha256'], 'FROZEN_INPUT_HASH:' + rel
        records.append(dict(item, bytes=path.stat().st_size))
    assert sum(r['bytes'] for r in records) < LIMIT

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            if self.path != '/' + token + '/bundle.tar':
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', 'application/x-tar')
            self.send_header('Content-Length', str(bundle.stat().st_size))
            self.send_header('X-Content-SHA256', bundle_sha)
            self.end_headers()
            try:
                with bundle.open('rb') as stream:
                    shutil.copyfileobj(stream, self.wfile, 1024**2)
                self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
            threading.Thread(target=server.shutdown, daemon=True).start()

    server = HTTPServer(('127.0.0.1', PORT), Handler)
    temp = Path(tempfile.mkdtemp(prefix='paper04-c2-export-'))
    try:
        inventory = dict(schema=request['schema'], status='EXISTING_INPUTS_PINNED', files=records,
                         new_model_forwards=0, new_distances=0, scientific_submissions=0)
        body = (json.dumps(inventory, indent=2) + '\n').encode()
        bundle = temp / 'bundle.tar'
        with tarfile.open(bundle, 'w') as archive:
            meta = tarfile.TarInfo('REMOTE_INPUT_INVENTORY.json')
            meta.size = len(body)
            archive.addfile(meta, io.BytesIO(body))
            for item in records:
                archive.add(ROOT / item['remote_relative_path'], arcname=item['local_relative_path'], recursive=False)
        assert bundle.stat().st_size < LIMIT
        bundle_sha = sha(bundle)
        print('C2_EXPORT_READY port=' + str(PORT) + ' bytes=' + str(bundle.stat().st_size), flush=True)
        timer = threading.Timer(2400, server.shutdown)
        timer.daemon = True
        timer.start()
        server.serve_forever(poll_interval=.5)
        timer.cancel()
        print('C2_EXPORT_CLOSED original_files_unchanged', flush=True)
    finally:
        server.server_close()
        shutil.rmtree(temp)
