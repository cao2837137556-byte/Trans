"""Read only the explicit 180435 evidence allowlist; export one temporary tar.

Run in the existing HPC terminal. No training, distances, submission, source
edits, credential edits or writes to the original experiment output directory.
The temporary server is loopback-only, uses an unguessable path, and expires.
"""
from collections import Counter
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import io
import json
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
import threading
import time

ROOT = Path('/public/home/jiangxinwei.zr/work/paper04/runs/history_normal_reference_keyrepair_v1_20261031/outputs/c1_keyrepair_once_20261031')
FILES = ['RESULT.json', 'ab/CIC_DEV/DECISIONS.npz', 'ab/UNSW_DEV/DECISIONS.npz',
         'dev/DEV_DECISIONS.npz', 'dev/QUERIES.jsonl.gz']
for key in ('TP_LINK', 'WEMO_POWER', 'SAMSUNG'):
    FILES += ['history/'+key+'/'+p for p in ('PREPARE_RESULT.json', 'INTERMEDIATE_CLEANUP.json',
              'selection/SELECTION.json', 'encoded/ENCODE_RESULT.json',
              'encoded/references.jsonl.gz', 'encoded/references.npz')]
SNAPSHOTS = ['history/'+k+'/selected_snapshots.jsonl.gz' for k in ('TP_LINK','WEMO_POWER','SAMSUNG')]


def fingerprint(relative, transfer):
    path = ROOT / relative
    if not path.is_file() or not path.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError('missing/outside output: '+relative)
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(4*1024**2), b''):h.update(part)
    record = dict(path=relative,bytes=path.stat().st_size,sha256=h.hexdigest(),transfer=transfer)
    if relative.endswith('references.jsonl.gz') or relative=='dev/QUERIES.jsonl.gz':
        roles=Counter()
        with gzip.open(path,'rt') as stream:
            for line in stream:
                row=json.loads(line);roles[row.get('history_role','MISSING')]+=1
        record['roles']=dict(roles);record['rows']=sum(roles.values())
    return record


def main():
    token=sys.argv[1]
    if len(token)!=32 or any(c not in '0123456789abcdef' for c in token):raise ValueError('token format')
    # Bind first: a repeated command cannot start a second export on this port.
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_GET(self):
            if self.path != '/'+token+'/bundle.tar':
                self.send_error(404);return
            self.send_response(200)
            self.send_header('Content-Type','application/x-tar')
            self.send_header('Content-Length',str(bundle.stat().st_size))
            self.send_header('X-Content-SHA256',bundle_sha)
            self.end_headers()
            try:
                with bundle.open('rb') as source:shutil.copyfileobj(source,self.wfile,1024**2)
                self.wfile.flush()
            except (BrokenPipeError,ConnectionResetError):return
            threading.Thread(target=server.shutdown,daemon=True).start()
    server=HTTPServer(('127.0.0.1',18790),Handler)
    server.timeout=30
    temp=Path(tempfile.mkdtemp(prefix='paper04-d2-export-'))
    try:
        records=[fingerprint(p,True) for p in FILES]
        # Snapshots are only inventoried, never transferred.
        records += [fingerprint(p,False) for p in SNAPSHOTS]
        assert sum(r.get('roles',{}).get('HIST_REF',0) for r in records)==24163
        assert sum(r.get('roles',{}).get('HIST_DEV',0) for r in records)==12288
        assert sum(r['bytes'] for r in records if r['transfer'])<256*1024**2
        inventory=dict(status='READ_ONLY_INVENTORY',root=str(ROOT),files=records,
                       new_distances=0,model_forwards=0,scientific_submissions=0)
        body=(json.dumps(inventory,indent=2)+'\n').encode()
        bundle=temp/'bundle.tar'
        with tarfile.open(bundle,'w') as archive:
            meta=tarfile.TarInfo('REMOTE_TRACE_INVENTORY.json');meta.size=len(body)
            archive.addfile(meta,io.BytesIO(body))
            for rel in FILES:archive.add(ROOT/rel,arcname=rel,recursive=False)
        h=hashlib.sha256()
        with bundle.open('rb') as source:
            for part in iter(lambda:source.read(4*1024**2),b''):h.update(part)
        bundle_sha=h.hexdigest()
        print('D2_EXPORT_READY port=18790 bytes='+str(bundle.stat().st_size),flush=True)
        timer=threading.Timer(1800,server.shutdown);timer.daemon=True;timer.start()
        server.serve_forever(poll_interval=.5)
        timer.cancel()
        print('D2_EXPORT_CLOSED original_files_unchanged',flush=True)
    finally:
        server.server_close()
        # Only the freshly created temporary export folder is removed.
        shutil.rmtree(temp)


if __name__=='__main__':main()
