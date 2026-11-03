"""Identity, fresh outputs and durable metadata; no scientific computation."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(6):
            try:
                os.replace(temporary, path)
                break
            except OSError as exc:
                if os.name != 'nt' or getattr(exc, 'winerror', None) not in (5, 32, 33) or attempt == 5:
                    raise
                time.sleep(.01 * 2**attempt)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def confined(root, relative):
    root = Path(root).resolve()
    require(isinstance(relative, str) and relative and '\\' not in relative,
            'PORTABLE_RELATIVE_PATH_REQUIRED')
    lexical = Path(relative)
    require(not lexical.is_absolute() and '..' not in lexical.parts, 'PATH_ESCAPE')
    result = (root / lexical).resolve()
    require(result.is_relative_to(root) and result != root, 'PATH_ESCAPE')
    return result


def verify_package(package):
    package = Path(package).resolve()
    manifest = package / 'PACKAGE_SHA256SUMS'
    entries = {}
    for line in manifest.read_text(encoding='utf-8').splitlines():
        digest, relative = line.split('  ', 1)
        require(len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)
                and relative not in entries, 'MANIFEST_ENTRY')
        path = confined(package, relative)
        require(path.is_file() and sha(path) == digest, 'PACKAGE_SHA:' + relative)
        entries[relative] = digest
    actual = {p.relative_to(package).as_posix() for p in package.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts and p != manifest
              and p.relative_to(package).parts[0] not in ('runtime', '.private', 'local_progress')}
    require(set(entries) == actual, 'PACKAGE_MEMBER_SET')
    return sha(manifest)


def validate_approval(approval, package_sha, stages):
    require(approval.get('user_authorized') is True and
            approval.get('package_sha256') == package_sha and
            approval.get('scope') == 'DENSE_REFERENCE_V1', 'PRODUCTION_APPROVAL_REQUIRED')
    allowed = approval.get('stages', [])
    require(isinstance(allowed, list) and set(stages) <= set(allowed), 'STAGE_NOT_AUTHORIZED')
    require(approval.get('retries') == 0, 'NO_AUTOMATIC_RETRY')


def assemble_view(manifest, source_root, bundled_root, output):
    """Bind immutable existing inputs to the canonical paths required by CAL.

    Only explicitly registered aliases are tried. An absent or changed input
    stops; this function does not search other projects, copy or modify sources.
    """
    source_root, bundled_root, output = map(lambda p: Path(p).resolve(),
                                           (source_root, bundled_root, output))
    require(not output.exists(), 'FRESH_ASSET_VIEW_REQUIRED')
    entries = manifest['files']
    names, verified = set(), []
    for item in entries:
        relative = item['path']
        require(relative not in names, 'DUPLICATE_ASSET_PATH')
        names.add(relative)
        candidates = [confined(bundled_root, relative), confined(source_root, relative)]
        candidates += [confined(source_root, alias) for alias in item.get('aliases', [])]
        valid = []
        for path in candidates:
            if path.is_file() and path.stat().st_size == item['bytes']:
                if sha(path) == item['sha256']:
                    valid.append(path)
        require(bool(valid), 'MISSING_OR_CHANGED_ASSET:' + relative)
        verified.append((relative, valid[0], item['sha256']))
    # Validate all identities before creating even a partial logical tree.
    output.mkdir(parents=True)
    for relative, source, _ in verified:
        destination = output / relative
        require(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
                'ASSET_PATH_ESCAPE')
        destination.parent.mkdir(parents=True, exist_ok=True)
        # The registered HPC inputs and package share /public. Hard links keep
        # canonical paths inside the view and consume no second data payload.
        # Cross-filesystem placement is a technical preflight failure, never a
        # silent full copy or a relaxed path-validation fallback.
        os.link(source, destination)
    return dict(status='PASS', files=len(verified), sources=[
        dict(path=name, resolved_source=str(source), sha256=digest)
        for name, source, digest in verified])
