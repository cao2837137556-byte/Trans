"""Verify incoming delivery and reuse equal destinations; never replace files."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def install(manifest_path, incoming, destination, verify_only=False):
    body = json.loads(Path(manifest_path).read_text(encoding='utf-8-sig'))
    incoming, destination = Path(incoming).resolve(), Path(destination).resolve()
    require(str(destination) == body['remote_root'], 'REMOTE_ROOT_MISMATCH')
    planned = []
    for row in body['files']:
        relative = PurePosixPath(row['remote_relative_path'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'REMOTE_PATH_ESCAPE')
        source, target = incoming / str(relative), destination / str(relative)
        require(target.resolve().is_relative_to(destination), 'DESTINATION_PATH_ESCAPE')
        for parent in target.parents:
            if parent == destination:
                break
            require(not parent.is_symlink() and (not parent.exists() or parent.is_dir()),
                    'UNSAFE_DESTINATION_PARENT:' + str(parent))
        if target.exists() or target.is_symlink():
            require(target.is_file() and not target.is_symlink() and
                    target.stat().st_size == row['bytes'] and sha(target) == row['sha256'],
                    'EXISTING_DESTINATION_DIVERGES_NO_OVERWRITE:' + str(target))
        else:
            planned.append((source, target, row))
        # A verified identical remote destination needs no duplicate upload.
        if source.exists() or source.is_symlink() or not target.exists():
            require(source.is_file() and not source.is_symlink(), 'INCOMING_FILE_MISSING_OR_LINK:' + str(source))
            require(source.stat().st_size == row['bytes'] and sha(source) == row['sha256'],
                    'INCOMING_FILE_CHANGED:' + str(source))
            require(source.resolve().is_relative_to(incoming), 'INCOMING_PATH_ESCAPE')
    # All incoming and existing destinations pass before installing any file.
    if verify_only:
        return dict(status='VERIFIED_NO_MUTATION', files=len(body['files']), missing=len(planned))
    installed = 0
    for source, target, row in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, target)
        except FileExistsError:
            require(target.is_file() and not target.is_symlink() and sha(target) == row['sha256'],
                    'CONCURRENT_DESTINATION_DIVERGENCE:' + str(target))
        except OSError:
            # Exclusive creation keeps the same no-overwrite guarantee cross-filesystem.
            with source.open('rb') as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 4 * 1024**2)
        require(target.stat().st_size == row['bytes'] and sha(target) == row['sha256'],
                'INSTALLED_FILE_CHANGED:' + str(target))
        installed += 1
    return dict(status='INSTALLED_WITHOUT_OVERWRITE', installed=installed,
                reused=len(body['files']) - len(planned), files=len(body['files']))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--incoming', required=True, type=Path)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    print(json.dumps(install(args.manifest, args.incoming, args.destination, args.verify_only)))
