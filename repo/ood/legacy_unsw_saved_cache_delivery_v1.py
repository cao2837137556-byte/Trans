"""Python3.9 stdlib-only installer/exporter, including export after environment failure."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2), b''):
            h.update(block)
    return h.hexdigest()


def install(archive, destination):
    archive,destination=Path(archive).resolve(),Path(destination).resolve()
    expected,name=Path(str(archive)+'.sha256').read_text(encoding='utf-8').strip().split()
    require(name==archive.name and sha(archive)==expected, 'ARCHIVE_SHA')
    require(not destination.exists(), 'DESTINATION_EXISTS_PRESERVE_IT')
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers(); names=set()
        require(sum(m.size for m in members)<8*1024**2,'PACKAGE_SIZE')
        for m in members:
            rel=PurePosixPath(m.name)
            require(m.isfile() and not rel.is_absolute() and '..' not in rel.parts and
                    '\\' not in m.name and ':' not in m.name and m.name not in names,'UNSAFE_MEMBER')
            names.add(m.name)
        require('SHA256SUMS' in names,'MISSING_INNER_SEAL')
        destination.mkdir(parents=True,exist_ok=False)
        for m in members:
            target=destination.joinpath(*PurePosixPath(m.name).parts)
            target.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(m) as src,target.open('xb') as dst:
                for block in iter(lambda:src.read(1024**2),b''):
                    dst.write(block)
    sealed=set()
    for line in (destination/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        expected,rel=line.split('  ',1)
        require(rel in names and rel not in sealed and sha(destination/rel)==expected,'INNER_SHA')
        sealed.add(rel)
    require(names==sealed|{'SHA256SUMS'},'INNER_FILE_SET')
    print('INSTALLED_VERIFIED_NO_REAL_CACHE_READ '+str(destination))


def export_output(root):
    root=Path(root).resolve()
    target=root/'cache_audit_pullback.tar.gz'
    require(not target.exists() and not target.with_suffix('.partial').exists(),'EXPORT_EXISTS')
    files=sorted(p for folder in ('runs/cache_audit','logs','validation')
                 for p in (root/folder).rglob('*') if p.is_file())
    files += [root/name for name in ('job.id','exit_code.txt','input_contract.json') if (root/name).is_file()]
    require(all(not p.is_symlink() and root in p.resolve().parents for p in files),'EXPORT_PATH')
    require(sum(p.stat().st_size for p in files)<128*1024**2,'EXPORT_SIZE_LIMIT')
    manifest={p.relative_to(root).as_posix():dict(sha256=sha(p),bytes=p.stat().st_size) for p in files}
    (root/'export_manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf-8'))
    files.append(root/'export_manifest.json')
    with tarfile.open(target.with_suffix('.partial'),'x:gz',compresslevel=1) as tar:
        for path in files:
            tar.add(path,arcname=path.relative_to(root).as_posix(),recursive=False)
    target.with_suffix('.partial').replace(target)
    Path(str(target)+'.sha256').write_bytes((sha(target)+'  '+target.name+'\n').encode('ascii'))
    print('PULLBACK_READY '+str(target),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('install','export'))
    parser.add_argument('--archive',type=Path)
    parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.command=='install':
        require(args.archive is not None and args.destination is not None,'INSTALL_ARGUMENTS')
        install(args.archive,args.destination)
    else:
        export_output(Path(__file__).resolve().parent)
