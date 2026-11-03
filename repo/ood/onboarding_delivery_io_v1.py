"""Stdlib-only, local onboarding installation and complete result export.

Neither command loads a model, scores data, retries a job, or contacts a server.
The install receipt is adjacent to the installed directory, outside its seal.
The export manifest describes every included and deliberately omitted file;
the manifest itself is protected by the archive SHA sidecar.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile


VERSION = 'onboarding-delivery-io-v1-20261017'
PACKAGE_LIMIT_BYTES = 200 * 1024**2
EXPORT_NAME = 'onboarding_pullback.tar.gz'
MANIFEST_NAME = 'onboarding_export_manifest.json'
_HEX = re.compile(r'^[0-9a-f]{64}$')
_RESERVED = {'con', 'prn', 'aux', 'nul'} | {
    prefix + str(i) for prefix in ('com', 'lpt') for i in range(1, 10)}


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode('utf-8')


def _relative(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or path.as_posix() != name or
            any(p in ('.', '..') for p in path.parts) or '\\' in name or ':' in name or
            any(p.endswith((' ', '.')) or p.split('.')[0].lower() in _RESERVED
                for p in path.parts)):
        raise RuntimeError('UNSAFE_MEMBER:' + name)
    return path


def _seal(content, names):
    sealed = {}
    for line in content.decode('utf-8').splitlines():
        try:
            digest, name = line.split('  ', 1)
        except ValueError as exc:
            raise RuntimeError('MALFORMED_INNER_SEAL') from exc
        _relative(name)
        if not _HEX.fullmatch(digest) or name in sealed or name == 'SHA256SUMS':
            raise RuntimeError('MALFORMED_INNER_SEAL:' + name)
        sealed[name] = digest
    if set(sealed) | {'SHA256SUMS'} != names:
        raise RuntimeError('INNER_FILE_SET')
    return sealed


def install(archive, destination):
    """Verify archive and every sealed member before creating a new directory."""
    archive = Path(archive).resolve()
    destination = Path(destination).absolute()
    receipt_path = destination.with_name(destination.name + '.install_receipt.json')
    if os.path.lexists(destination) or os.path.lexists(receipt_path):
        raise RuntimeError('DESTINATION_OR_RECEIPT_EXISTS_NO_OVERWRITE')
    destination = destination.resolve()
    fields = Path(str(archive) + '.sha256').read_text(encoding='utf-8').strip().split()
    if (len(fields) != 2 or not _HEX.fullmatch(fields[0]) or fields[1] != archive.name or
            sha(archive) != fields[0]):
        raise RuntimeError('ARCHIVE_SHA')
    with tarfile.open(archive, 'r:gz') as tar:
        members = tar.getmembers()
        if sum(m.size for m in members) > PACKAGE_LIMIT_BYTES:
            raise RuntimeError('PACKAGE_SIZE')
        names, portable_names = set(), set()
        for member in members:
            path = _relative(member.name)
            key = member.name.casefold()
            if not member.isfile() or member.size < 0 or key in portable_names:
                raise RuntimeError('UNSAFE_OR_DUPLICATE_MEMBER:' + member.name)
            names.add(member.name)
            portable_names.add(key)
        for name in names:
            if any(parent.as_posix().casefold() in portable_names
                   for parent in PurePosixPath(name).parents if parent.as_posix() != '.'):
                raise RuntimeError('FILE_DIRECTORY_COLLISION:' + name)
        if 'SHA256SUMS' not in names:
            raise RuntimeError('MISSING_INNER_SEAL')
        with tar.extractfile('SHA256SUMS') as stream:
            seal_bytes = stream.read()
        sealed = _seal(seal_bytes, names)
        for name, expected in sealed.items():
            digest = hashlib.sha256()
            with tar.extractfile(name) as stream:
                for block in iter(lambda: stream.read(4 * 1024**2), b''):
                    digest.update(block)
            if digest.hexdigest() != expected:
                raise RuntimeError('INNER_SHA:' + name)
        # A failed filesystem write leaves a visibly incomplete new directory.
        # It is never removed, reused, or silently replaced by this installer.
        destination.mkdir(parents=True, exist_ok=False)
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(member) as source, target.open('xb') as output:
                for block in iter(lambda: source.read(4 * 1024**2), b''):
                    output.write(block)
            os.chmod(target, member.mode & 0o777)
            expected = hashlib.sha256(seal_bytes).hexdigest() if member.name == 'SHA256SUMS' else sealed[member.name]
            if sha(target) != expected:
                raise RuntimeError('EXTRACTED_SHA:' + member.name)
    receipt = dict(version=VERSION, status='INSTALLED_AND_VERIFIED_NO_EXPERIMENT_STARTED',
                   archive=str(archive), archive_sha256=fields[0], destination=str(destination),
                   internal_seal_sha256=hashlib.sha256(seal_bytes).hexdigest(),
                   installed_files=len(members), installed_bytes=sum(m.size for m in members),
                   utc=datetime.now(timezone.utc).isoformat(), remote_access=False,
                   retries=0, scoring_started=False)
    with receipt_path.open('xb') as stream:
        stream.write(_json_bytes(receipt))
    return receipt


def _omit_reason(parts):
    if parts[0] in ('repo', 'vendor', 'synthetic_tmp'):
        return 'delivery source/vendor or generated synthetic test data; sealed input retained separately'
    if parts[:4] == ('runs', 'onboarding', 'encoder_runtime', 'vendor'):
        return 'copied frozen encoder source/checkpoint; runtime SHA256SUMS and identity receipt retained'
    if parts[:2] == ('runs', 'onboarding') and any(p.startswith('reference-working-') for p in parts[2:-1]):
        # These filenames are never disposable, even if a caller puts them in
        # an unexpected scratch directory. Avoid a broad *.sqlite exclusion:
        # parent or selected snapshot databases can be essential evidence.
        if parts[-1] in ('selected_snapshots.jsonl.gz', 'candidates.jsonl.gz', 'census_receipt.json'):
            return None
        return 'private reference-working directory: temporary SQLite/context snapshot scratch, not resumable evidence'
    return None


def _files(root):
    """Reject links/special files; do not silently skip evidence or follow links."""
    for folder, directories, files in os.walk(root, followlinks=False):
        for name in sorted(directories + files):
            path = Path(folder) / name
            mode = path.lstat().st_mode
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise RuntimeError('EXPORT_LINK_OR_ESCAPE:' + path.relative_to(root).as_posix())
            if stat.S_ISDIR(mode):
                continue
            if not stat.S_ISREG(mode):
                raise RuntimeError('EXPORT_SPECIAL_FILE:' + path.relative_to(root).as_posix())
            yield path


class _HashingReader:
    def __init__(self, source):
        self.source = source
        self.digest = hashlib.sha256()
        self.size = 0

    def read(self, size=-1):
        block = self.source.read(size)
        self.digest.update(block)
        self.size += len(block)
        return block


def export(root):
    """Export complete successful or failed-run evidence; never truncate to fit."""
    root = Path(root).resolve()
    archive = root / EXPORT_NAME
    manifest_path = root / MANIFEST_NAME
    sidecar = Path(str(archive) + '.sha256')
    if any(os.path.lexists(path) for path in (archive, manifest_path, sidecar)):
        raise RuntimeError('EXPORT_EXISTS_NO_OVERWRITE')
    contract = json.loads((root / 'runtime_contract.json').read_text(encoding='utf-8'))
    limit = contract.get('export_included_limit_gib')
    if isinstance(limit, bool) or not isinstance(limit, (int, float)) or not math.isfinite(limit) or limit <= 0:
        raise RuntimeError('INVALID_EXPORT_LIMIT')
    limit_bytes = int(limit * 1024**3)
    included, omitted = {}, {}
    for path in sorted(_files(root)):
        relative = path.relative_to(root)
        info = dict(bytes=path.stat().st_size, sha256=sha(path))
        reason = _omit_reason(relative.parts)
        if reason:
            info['reason'] = reason
            omitted[relative.as_posix()] = info
        else:
            included[relative.as_posix()] = info
    manifest = dict(version=VERSION, included=included, omitted=omitted,
                    included_payload_bytes=sum(item['bytes'] for item in included.values()),
                    manifest_bytes=0, included_limit_bytes=limit_bytes,
                    failure_outputs_supported=True, retries=0, scoring_started=False,
                    remote_access=False, parent_inputs_read_only=True,
                    manifest_integrity='covered by archive SHA256 sidecar; not self-hashed')
    for _ in range(10):
        content = _json_bytes(manifest)
        if manifest['manifest_bytes'] == len(content):
            break
        manifest['manifest_bytes'] = len(content)
    else:
        raise RuntimeError('MANIFEST_SIZE_DID_NOT_CONVERGE')
    if manifest['included_payload_bytes'] + len(content) > limit_bytes:
        raise RuntimeError('EXPORT_SIZE_LIMIT_KEEP_ALL_RESULTS_NO_TRUNCATION')
    created = []
    try:
        with manifest_path.open('xb') as stream:
            created.append(manifest_path)
            stream.write(content)
        with archive.open('xb') as raw:
            created.append(archive)
            with tarfile.open(fileobj=raw, mode='w:gz', compresslevel=1) as tar:
                for relative, expected in included.items():
                    path = root / relative
                    if path.is_symlink() or not path.resolve().is_relative_to(root):
                        raise RuntimeError('EXPORT_CHANGED_LINK:' + relative)
                    info = tar.gettarinfo(str(path), arcname=relative)
                    if not info.isfile() or info.size != expected['bytes']:
                        raise RuntimeError('EXPORT_CHANGED_FILE:' + relative)
                    with path.open('rb') as source:
                        reader = _HashingReader(source)
                        tar.addfile(info, reader)
                    if reader.size != expected['bytes'] or reader.digest.hexdigest() != expected['sha256']:
                        raise RuntimeError('EXPORT_CHANGED_CONTENT:' + relative)
                tar.add(manifest_path, arcname=MANIFEST_NAME, recursive=False)
        with sidecar.open('xb') as stream:
            created.append(sidecar)
            stream.write((sha(archive) + '  ' + archive.name + '\n').encode('ascii'))
    except BaseException:
        for path in reversed(created):
            path.unlink()
        raise
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    installer = commands.add_parser('install')
    installer.add_argument('--archive', required=True)
    installer.add_argument('--destination', required=True)
    exporter = commands.add_parser('export')
    exporter.add_argument('--root', required=True)
    args = parser.parse_args()
    if args.command == 'install':
        receipt = install(args.archive, args.destination)
        print(receipt['status'] + ' ' + receipt['destination'], flush=True)
    else:
        manifest = export(args.root)
        print('PULLBACK_READY ' + str(Path(args.root).resolve() / EXPORT_NAME) +
              ' included_files=' + str(len(manifest['included'])), flush=True)


if __name__ == '__main__':
    main()
