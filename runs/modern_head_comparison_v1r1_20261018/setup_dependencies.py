"""Install the sealed wheels into this package only, offline and without training."""
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

ROOT=Path(__file__).resolve().parent


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if sys.version_info[:2]!=(3,9) or sys.platform!='linux' or platform.machine()!='x86_64':
        raise RuntimeError('TARGET_REQUIRES_LINUX_X86_64_PYTHON39')
    libc,version=platform.libc_ver()
    if libc!='glibc' or tuple(map(int,version.split('.')[:2]))<(2,28):
        raise RuntimeError('LIGHTGBM_WHEEL_REQUIRES_GLIBC_2_28; do not alter the frozen recipe')
    declared={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (ROOT/'SHA256SUMS').read_text().splitlines()}
    for rel,expected in declared.items():
        p=(ROOT/rel).resolve()
        if not p.is_relative_to(ROOT) or sha(p)!=expected: raise RuntimeError('PACKAGE_IDENTITY:'+rel)
    dest=ROOT/'extra_deps'
    if dest.exists(): raise RuntimeError('DEPENDENCY_DIRECTORY_EXISTS; inspect previous installation rather than overwrite')
    specs=['lightgbm==4.6.0','rtdl_num_embeddings==0.0.12','scipy==1.13.1','typing_extensions==4.14.1']
    subprocess.run([sys.executable,'-m','pip','install','--disable-pip-version-check','--no-index','--no-deps','--no-compile',
                    '--find-links',str(ROOT/'wheelhouse'),'--target',str(dest)]+specs,check=True)
    record=dict(status='INSTALLED_OFFLINE_NOT_EXPERIMENT',requirements=specs,
                wheels={p.name:sha(p) for p in sorted((ROOT/'wheelhouse').glob('*.whl'))},
                installed_files={p.relative_to(dest).as_posix():sha(p) for p in sorted(dest.rglob('*')) if p.is_file()})
    (ROOT/'dependency_install_receipt.json').write_text(json.dumps(record,indent=2)+'\n')
    print(record['status'])


if __name__=='__main__': main()
