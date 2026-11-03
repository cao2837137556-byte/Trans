"""Install presealed purelib/platlib wheels without pip or network access."""
import base64
import csv
import hashlib
import io
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sys
import zipfile
import package_io as p


def wheel_members(wheel):
    """Validate every wheel member against RECORD before any extraction."""
    with zipfile.ZipFile(wheel) as z:
        names = z.namelist()
        p.require(len(names) == len(set(names)), 'WHEEL_DUPLICATE_NAME')
        records = [n for n in names if n.endswith('.dist-info/RECORD')]
        p.require(len(records) == 1, 'WHEEL_RECORD_REQUIRED')
        rows = list(csv.reader(io.StringIO(z.read(records[0]).decode('utf-8'))))
        entries = {r[0]: r[1:] for r in rows}
        p.require(len(entries) == len(rows), 'WHEEL_RECORD_DUPLICATE')
        files = [n for n in names if not n.endswith('/')]
        p.require(set(files) == set(entries), 'WHEEL_RECORD_FILE_SET')
        result = []
        for name in files:
            q = PurePosixPath(name)
            p.require(not q.is_absolute() and '..' not in q.parts and '\\' not in name and
                      ':' not in name and not any(part.endswith('.data') for part in q.parts),
                      'WHEEL_UNSUPPORTED_PATH:' + name)
            info = z.getinfo(name)
            p.require((info.external_attr >> 16) & 0o170000 != 0o120000, 'WHEEL_SYMLINK')
            raw = z.read(name)
            digest, size = entries[name]
            if name == records[0]:
                p.require(not digest and not size, 'RECORD_SELF_HASH')
            else:
                expected = 'sha256=' + base64.urlsafe_b64encode(hashlib.sha256(raw).digest()).decode().rstrip('=')
                p.require(digest == expected and size == str(len(raw)), 'WHEEL_RECORD_HASH:' + name)
            result.append((name, raw))
        return result


def main():
    p.package()
    p.require(sys.version_info[:2] == (3, 9) and sys.platform == 'linux' and
              platform.machine() == 'x86_64', 'REQUIRES_LINUX_X86_64_PY39')
    libc, version = platform.libc_ver()
    p.require(libc == 'glibc' and tuple(map(int, version.split('.')[:2])) >= (2, 28),
              'GLIBC_2_28_REQUIRED')
    target, temporary = p.ROOT / 'extra_deps', p.ROOT / 'extra_deps.installing'
    p.require(not target.exists() and not temporary.exists(), 'INSTALL_DIRECTORY_EXISTS')
    files = {}; wheels = {}
    # Validate all RECORDs first; these ~40MiB wheels fit the bounded installer.
    for wheel in sorted((p.ROOT / 'wheelhouse').glob('*.whl')):
        wheels[wheel.name] = p.sha(wheel)
        for name, raw in wheel_members(wheel):
            p.require(name not in files, 'WHEEL_COLLISION:' + name)
            files[name] = raw
    p.require(len(wheels) == 4, 'FOUR_SEALED_WHEELS_REQUIRED')
    temporary.mkdir()
    for name, raw in files.items():
        path = (temporary / name).resolve()
        p.require(path.is_relative_to(temporary.resolve()), 'EXTRACTION_ESCAPE')
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(raw)
    os.replace(temporary, target)
    p.write(p.ROOT / 'dependency_install_receipt.json', dict(
        status='INSTALLED_OFFLINE_NOT_EXPERIMENT', method='RECORD_VERIFIED_WHEEL_EXTRACTION',
        python=platform.python_version(), wheels=wheels,
        files={name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}))
    print('INSTALLED_OFFLINE_NOT_EXPERIMENT', flush=True)


if __name__ == '__main__':
    main()
