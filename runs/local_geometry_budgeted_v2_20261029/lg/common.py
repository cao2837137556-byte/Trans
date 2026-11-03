"""Small, side-effect-free identities and durable JSON helpers."""
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
SPEC_SHA = '797a08dc7cd540f6c1c2d498490e520cb40d6938da8c6ceec350f5b80b17fc51'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    path = Path(path)
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns) == (after.st_size, after.st_mtime_ns),
            'INPUT_CHANGED_DURING_HASH:' + str(path))
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    tmp.replace(path)


def array_sha(array):
    return hashlib.sha256(array.tobytes(order='C')).hexdigest()


def uid_sha(uids):
    return hashlib.sha256((''.join(str(uid) + '\n' for uid in uids)).encode('utf-8')).hexdigest()


def resolve_asset(root, value):
    """Map a saved Windows absolute path to this checkout; never read outside it."""
    root = Path(root).resolve()
    value = str(value).replace('\\', '/')
    if '/runs/' in value:
        value = 'runs/' + value.split('/runs/', 1)[1]
    elif '/repo/' in value:
        value = 'repo/' + value.split('/repo/', 1)[1]
    path = (root / value).resolve()
    require(path.is_relative_to(root), 'ASSET_OUTSIDE_ROOT')
    return path
