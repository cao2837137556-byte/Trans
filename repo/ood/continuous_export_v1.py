"""Standalone stdlib export; safe even when numeric dependencies fail to import."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):h.update(block)
    return h.hexdigest()


def export(root):
    root=Path(root);target=root/'repair_pullback.tar.gz'
    if target.exists():raise RuntimeError('EXPORT_EXISTS_NO_OVERWRITE')
    included={};omitted={};total=0
    for p in sorted(root.rglob('*')):
        if not p.is_file() or p.is_symlink():continue
        rel=p.relative_to(root).as_posix()
        if rel.startswith(('vendor/','repo/','frozen/','submit_claim/')) or rel.endswith('.json.next'):continue
        if rel.startswith('runs/real_repair/spool/') or ('features_worker_' in rel and ('/block_' in rel or 'tensor_receipts' in rel)) or rel.startswith('runs/real_repair/features/'):
            omitted[rel]=dict(bytes=p.stat().st_size,reason='large causal cache retained remotely; use stage seals')
        else:
            included[rel]=dict(bytes=p.stat().st_size,sha256=sha(p));total+=p.stat().st_size
    if total>2*1024**3:raise RuntimeError('EXPORT_SIZE_LIMIT_KEEP_REMOTE')
    manifest=root/'export_manifest.json'
    with manifest.open('x',encoding='utf-8',newline='\n') as out:
        json.dump(dict(included=included,omitted=omitted,remote_cache_preserved=True),out,indent=2)
    with tarfile.open(target,'x:gz',compresslevel=1) as tar:
        for rel in included:tar.add(root/rel,arcname=rel,recursive=False)
        tar.add(manifest,arcname='export_manifest.json',recursive=False)
    Path(str(target)+'.sha256').write_bytes((sha(target)+'  '+target.name+'\n').encode())
    print('PULLBACK_READY '+str(target),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True)
    export(parser.parse_args().root)
