"""Verify a separately extracted, byte-pinned preflight checkout; no imports/models."""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(block)
    return value.hexdigest()


def verify(root, manifest):
    root = Path(root).resolve()
    spec = json.loads(Path(manifest).read_text(encoding='utf-8'))
    for name, item in spec['files'].items():
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('PACKAGE_PATH_OR_MISSING:' + name)
        if path.stat().st_size != item['bytes'] or sha(path) != item['sha256']:
            raise ValueError('PACKAGE_BYTE_PIN:' + name)
    return {'status': 'PACKAGE_BYTES_PASS_NOT_RUNTIME_PASS', 'files': len(spec['files']),
            'bytes': sum(x['bytes'] for x in spec['files'].values()),
            'manifest_sha256': sha(manifest)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--manifest', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root, args.manifest), indent=2))
