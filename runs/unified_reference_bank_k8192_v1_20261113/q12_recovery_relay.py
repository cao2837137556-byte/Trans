"""Two scoped delivery routes and a read-only inspection of frozen HPC assets."""
import argparse
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile
import threading

BASE = 'unified_reference_bank_k8192_v1_20261113'
PARENT = BASE+'_early_183987'
RUNS = {'uid':BASE+'_uidfix_184105', 'heads':'p4_head_transfer_followup_v1_20261115'}
LIMIT = 5 * 1024**2
POOLS = ('CIC_DEV','UNSW_DEV','EDGE')


def read(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def write(path, value):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
    tmp.replace(path)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):
            h.update(block)
    return h.hexdigest()


def install(stage, mode, data):
    runs = stage.parent
    target = runs/RUNS[mode]
    archive_sha = hashlib.sha256(data).hexdigest()
    if target.exists():
        receipt = read(target/'INSTALL.json')
        if receipt and receipt['archive_sha256'] == archive_sha and (target/'CONTROLLER_PID.json').is_file():
            return receipt
        raise ValueError('EXISTING_RUN_REQUIRES_RECONCILIATION:'+target.name)
    scratch = stage/('extract_'+mode)
    scratch.mkdir()
    with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
        members = archive.getmembers()
        if len(members) > 160 or sum(m.size for m in members) > 32*1024**2:
            raise ValueError('PACKAGE_MEMBER_BOUNDS')
        names = {m.name for m in members}
        if len(names) != len(members):
            raise ValueError('DUPLICATE_PACKAGE_MEMBER')
        for member in members:
            relative = PurePosixPath(member.name)
            if not member.isfile() or relative.is_absolute() or '..' in relative.parts or (
                    len(relative.parts) > 5 or relative.as_posix() != member.name):
                raise ValueError('PACKAGE_MEMBER_PATH')
            to = scratch/relative
            to.parent.mkdir(parents=True,exist_ok=True)
            with archive.extractfile(member) as src,to.open('xb') as dst:
                shutil.copyfileobj(src,dst)
    manifest = read(scratch/'PACKAGE_MANIFEST.json')
    if manifest['run'] != target.name or set(manifest['files'])|{'PACKAGE_MANIFEST.json'} != names:
        raise ValueError('PACKAGE_MANIFEST_SCOPE')
    for name, sha in manifest['files'].items():
        if digest(scratch/name) != sha:
            raise ValueError('PACKAGE_MEMBER_SHA:'+name)
    target.mkdir()
    scratch.rename(target/'package')
    receipt = dict(status='INSTALLED',run=target.name,archive_sha256=archive_sha,
                   manifest_sha256=digest(target/'package/PACKAGE_MANIFEST.json'))
    write(target/'INSTALL.json',receipt)
    with (target/'dispatch.log').open('ab') as log:
        child = subprocess.Popen([sys.executable,'-X','utf8','-B',str(target/'package/launch.py'),
                                  str(runs.parent),str(target)],stdin=subprocess.DEVNULL,stdout=log,
                                  stderr=log,start_new_session=True)
    write(target/'CONTROLLER_PID.json',dict(pid=child.pid))
    return receipt


def probe(runs):
    import numpy as np
    project = runs.parent
    old = runs/PARENT
    out = dict(scheduler={})
    for command in (['squeue','-h','-u',os.environ['USER'],'-o','%i|%j|%T|%R'],
                    ['sacct','-n','-P','-X','-j','183971,183987,184105',
                     '-o','JobIDRaw,JobName%55,State,ExitCode,ElapsedRaw,MaxRSS']):
        res = subprocess.run(command,capture_output=True,text=True,timeout=15)
        out['scheduler'][command[0]] = dict(
            code=res.returncode,stdout=res.stdout if command[0]=='sacct' else '\n'.join(
                row for row in res.stdout.splitlines() if any(s in row for s in ('k8192','head-transfer'))))
    out['seals'] = {}
    for kind in ('preflight','candidate'):
        path = old/kind/'CANDIDATE.json'
        receipt = read(path)
        if receipt:
            out['seals'][kind] = dict(receipt_sha256=digest(path), status=receipt['status'],
                selection=receipt['selection'], pools={p:v['feature']['arrays'] for p,v in receipt['pools'].items()})
    pins = read(old/'package/REMOTE_ASSET_PINS.json')['files']
    out['contexts'] = {}
    for pool in POOLS[:2]:
        p = project/pins[pool+':query_context_uids']['paths'][0]
        q = runs/'p4_complete_bank_v1_20261111/artifacts'/(pool+'_QUERY.npz')
        if p.is_file() and q.is_file():
            with np.load(p,allow_pickle=False) as meta,np.load(q,allow_pickle=False) as query:
                uid, exp = meta['uid'], query['uid']
                a,b = uid.astype('U64'),exp.astype('U64')
                out['contexts'][pool]=dict(meta_dtype=uid.dtype.str,query_dtype=exp.dtype.str,
                    meta_shape=list(a.shape),query_shape=list(b.shape),dtype_normalized_exact=np.array_equal(a,b),
                    set_equal=set(a.tolist())==set(b.tolist()),uid_sha256=digest(p),meta_keys=meta.files,
                    reference_meta=read(old/'package/CONTINUATION_SOURCE_PINS.json')['job'])
    paths = [
        'p4_complete_bank_v1_20261111/artifacts',
        'baseline_author_defaults_v1_20261108/EVALUATION_INPUTS.json',
        'baseline_author_defaults_v1_20261108/evaluate_CatBoost_27_RESULT.json',
        'baseline_author_defaults_v1_20261108/artifacts/evaluation',
        'baseline_author_defaults_v1_20261108/artifacts/CatBoost',
        'baseline_slad_eval_repair_v1_20261108/artifacts/evaluation',
        'baseline_training_readiness_v6_20261107/artifacts/source',
        'device_context_training_v2_20261105/metadata',
        'device_context_head_training_v2_20261105',
    ]
    out['head_assets'] = {}
    for name in paths:
        p = runs/name
        if p.is_file() and p.stat().st_size < 120000:
            out['head_assets'][name] = read(p)
        elif p.is_dir():
            out['head_assets'][name] = sorted(x.name for x in p.iterdir())[:80]
        else:
            out['head_assets'][name] = None
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage',type=Path)
    p.add_argument('port',type=int)
    a = p.parse_args()
    stage = a.stage.resolve()
    token = (stage/'token').read_text().strip()
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):
            pass

        def route(self):
            t,sep,route = self.path.removeprefix('/').partition('/')
            if not sep or not hmac.compare_digest(token,t):
                raise PermissionError('RELAY_AUTH')
            return route

        def respond(self, value):
            raw = json.dumps(value,ensure_ascii=True).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            try:
                route = self.route()
                if route == 'probe':
                    return self.respond(probe(stage.parent))
                verb,mode,*other = route.split('-',2)
                target = stage.parent/RUNS[mode]
                if verb == 'state':
                    return self.respond({k:read(target/f) for k,f in zip(
                        ('install','chain','progress','prep','replay','acceptance'),
                        ('INSTALL.json','CHAIN_STATE.json','PROGRESS.json','PREP_RECEIPT.json',
                         'REPLAY_RECEIPT.json','ACCEPTANCE.json'))})
                manifest = read(target/'RETURN.json')
                if verb == 'manifest':
                    return self.respond(manifest)
                if verb != 'file' or len(other) != 1 or manifest is None or other[0] not in manifest['files']:
                    raise ValueError('UNMANIFESTED_RESULT')
                path = target/other[0]
                if path.parent != target or path.stat().st_size > 32*1024**2:
                    raise ValueError('RESULT_PATH_OR_SIZE')
                self.send_response(200)
                self.send_header('Content-Length',str(path.stat().st_size))
                self.end_headers()
                with path.open('rb') as src:
                    shutil.copyfileobj(src,self.wfile,length=1024**2)
            except (ConnectionError,BrokenPipeError):
                pass
            except Exception as e:
                self.send_error(409,str(e)[:300])

        def do_POST(self):
            try:
                verb,mode = self.route().split('-',1)
                size = int(self.headers['Content-Length'])
                if verb != 'install' or mode not in RUNS or not 0 < size <= LIMIT:
                    raise ValueError('INSTALL_ROUTE_OR_SIZE')
                content = self.rfile.read(size)
                if len(content) != size or hashlib.sha256(content).hexdigest() != self.headers['X-SHA256']:
                    raise ValueError('INSTALL_ARCHIVE_SHA')
                with lock:
                    value = install(stage,mode,content)
                self.respond(value)
            except (ConnectionError,BrokenPipeError):
                pass
            except Exception as e:
                self.send_error(409,str(e)[:300])

    os.umask(0o077)
    with ThreadingHTTPServer(('127.0.0.1',a.port),Handler) as http:
        timer=threading.Timer(3*86400,http.shutdown)
        timer.daemon=True
        timer.start()
        http.serve_forever()


if __name__=='__main__':
    main()
