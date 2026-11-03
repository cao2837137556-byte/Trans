"""Stdlib-only successful/failed run export, no model loading or retry."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2), b''): h.update(block)
    return h.hexdigest()


def export(root):
    root = Path(root); target = root/'query_tail_pullback.tar.gz'
    if target.exists() or (root/'export_manifest.json').exists(): raise RuntimeError('EXPORT_EXISTS_NO_OVERWRITE')
    included = {}; omitted = {}
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink(): continue
        rel = path.relative_to(root).as_posix()
        if rel.startswith(('repo/', 'synthetic_tmp/', 'submit_claim/')) or rel.endswith('.json.next'): continue
        if rel.startswith('runs/query_tail/prepared/') and path.suffix == '.npy':
            omitted[rel] = dict(bytes=path.stat().st_size, sha256=sha(path), reason='deterministic q/window cache retained remotely')
        else:
            included[rel] = dict(bytes=path.stat().st_size, sha256=sha(path))
    if sum(v['bytes'] for v in included.values()) > 2*1024**3: raise RuntimeError('EXPORT_SIZE_LIMIT_KEEP_REMOTE')
    manifest = root/'export_manifest.json'
    with manifest.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(dict(included=included, omitted=omitted, parent_run_read_only=True, retries=0), stream, indent=2)
    with tarfile.open(target, 'x:gz', compresslevel=1) as tar:
        for rel in included: tar.add(root/rel, arcname=rel, recursive=False)
        tar.add(manifest, arcname='export_manifest.json', recursive=False)
    Path(str(target)+'.sha256').write_bytes((sha(target)+'  '+target.name+'\n').encode())
    print('PULLBACK_READY '+str(target), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--root', required=True)
    export(parser.parse_args().root)
