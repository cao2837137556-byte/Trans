"""Bounded-memory tar chunks and verified, resumable download preparation."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

GIB = 1024**3
CHUNK_BYTES = 256*1024**2


def require(value,message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024**2),b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    path = Path(path)
    require(not path.exists(),'NO_OVERWRITE:'+str(path))
    temporary = path.with_name(path.name+'.next')
    with temporary.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(temporary,path)


class ChunkWriter:
    """Write a tar stream once; at most one bounded partial chunk is open."""
    def __init__(self,folder,chunk_bytes=CHUNK_BYTES):
        require(0 < chunk_bytes <= CHUNK_BYTES,'CHUNK_SIZE')
        self.folder = Path(folder)
        self.chunk_bytes = chunk_bytes
        self.parts = []
        self.stream = None
        self.used = 0
        self.digest = None

    def start(self):
        require(shutil.disk_usage(self.folder).free > self.chunk_bytes+512*1024**2,'EXPORT_DISK_HEADROOM')
        self.name = 'part-%06d.tar'%len(self.parts)
        self.partial = self.folder/(self.name+'.partial')
        self.stream = self.partial.open('xb')
        self.used = 0
        self.digest = hashlib.sha256()

    def commit(self):
        if self.stream is None:
            return
        self.stream.flush();os.fsync(self.stream.fileno());self.stream.close()
        self.stream = None
        os.replace(self.partial,self.folder/self.name)
        self.parts.append(dict(name=self.name,bytes=self.used,sha256=self.digest.hexdigest()))

    def write(self,data):
        view = memoryview(data)
        total = len(data)
        while view:
            if self.stream is None:
                self.start()
            count = min(len(view),self.chunk_bytes-self.used)
            self.stream.write(view[:count])
            self.digest.update(view[:count]);self.used += count
            view = view[count:]
            if self.used == self.chunk_bytes:
                self.commit()
        return total

    def finish(self):
        self.commit()
        return self.parts

    def abandon(self):
        if self.stream is not None:
            self.stream.close();self.stream = None


def fileset(sources,excluded=()):
    """Sources are (archive-prefix, directory/file); symlinks are recorded, not followed."""
    files,links = [],[]
    names = set()
    for prefix,source in sources:
        require(re.fullmatch('[A-Za-z0-9_-]+',prefix) is not None,'ARCHIVE_PREFIX')
        source = Path(source)
        require(source.exists(),'EXPORT_SOURCE_MISSING:'+str(source))
        paths = sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in paths:
            relative = path.relative_to(source).as_posix() if source.is_dir() else path.name
            name = prefix+'/'+relative
            if any(name==entry or name.startswith(entry.rstrip('/')+'/') for entry in excluded):
                continue
            require(name not in names,'DUPLICATE_ARCHIVE_NAME')
            if path.is_symlink():
                links.append(dict(path=name,target=os.readlink(path)));names.add(name)
            elif path.is_file():
                require(not path.name.endswith(('.next','.partial')),'UNFINISHED_EXPORT_SOURCE:'+str(path))
                files.append((name,path,path.stat().st_size));names.add(name)
    return files,links


def create_backup(sources,out,*,scope,identity,chunk_bytes=CHUNK_BYTES,excluded=()):
    out = Path(out).resolve()
    require(not out.exists() and out.parent.is_dir(),'NEW_EXPORT_DIRECTORY_REQUIRED')
    for _,source in sources:
        source = Path(source).resolve()
        require(not out.is_relative_to(source) and not source.is_relative_to(out),'EXPORT_SCOPE_OVERLAP')
    files,links = fileset(sources,excluded)
    # This is an uncompressed portable stream; estimate includes PAX/tar headers.
    estimated = sum(size+4096 for _,_,size in files)+10240
    require(shutil.disk_usage(out.parent).free > estimated+GIB,'EXPORT_TOTAL_DISK_REQUIRED')
    out.mkdir()
    writer = ChunkWriter(out,chunk_bytes)
    try:
        with tarfile.open(fileobj=writer,mode='w|',format=tarfile.PAX_FORMAT) as archive:
            for name,path,size in files:
                require(path.stat().st_size == size,'EXPORT_SOURCE_SIZE_CHANGED')
                archive.add(path,arcname=name,recursive=False)
                require(path.stat().st_size == size,'EXPORT_SOURCE_SIZE_CHANGED')
        parts = writer.finish()
        manifest = dict(schema='paper04-chunked-backup-v1',scope=scope,identity=identity,
            compression='none',format='tar-stream-concatenate-parts-in-order',chunk_bytes=chunk_bytes,
            chunks=parts,bytes=sum(x['bytes'] for x in parts),source_bytes=sum(x[2] for x in files),
            files=len(files),symlinks_not_followed=links,excluded_files=sorted(excluded),complete=True,
            receipts_after_export='Service final_status and exit-code sidecars are separate; download state separately')
        write(out/'BACKUP_INDEX.json',manifest)
        return dict(directory=str(out),manifest_sha256=sha(out/'BACKUP_INDEX.json'),**manifest)
    except BaseException:
        writer.abandon()
        raise


def validate_index(index):
    require(index['schema']=='paper04-chunked-backup-v1' and index['complete'] is True,'BACKUP_NOT_COMPLETE')
    total = 0
    require(index['chunks'] and 0 < index['chunk_bytes'] <= CHUNK_BYTES,'BACKUP_CHUNK_SIZE')
    for i,item in enumerate(index['chunks']):
        require(item['name']=='part-%06d.tar'%i and 0 < item['bytes'] <= index['chunk_bytes'] and
                re.fullmatch('[0-9a-f]{64}',item['sha256']) is not None,'BACKUP_CHUNK_IDENTITY')
        total += item['bytes']
    require(total==index['bytes'],'BACKUP_TOTAL_BYTES')


def verify_download(folder,index_sha):
    folder = Path(folder)
    require(sha(folder/'BACKUP_INDEX.json')==index_sha,'BACKUP_INDEX_SHA')
    index = read(folder/'BACKUP_INDEX.json');validate_index(index)
    missing,bad,good = [],[],[]
    for item in index['chunks']:
        path = folder/item['name']
        if not path.is_file():
            missing.append(item['name'])
        elif path.stat().st_size != item['bytes'] or sha(path)!=item['sha256']:
            bad.append(item['name'])
        else:
            good.append(item['name'])
    return dict(status='COMPLETE' if not missing and not bad else 'INCOMPLETE',
        valid_chunks=good,missing_chunks=missing,corrupt_chunks=bad,bytes=index['bytes'])


def download(target,remote,local,index_sha,*,port=22):
    """Explicit operator command, SSH keys only; no credentials or remote shell code."""
    require(re.fullmatch('[A-Za-z0-9_.@-]+',target) is not None and not target.startswith('-'),'SSH_TARGET')
    require(re.fullmatch('/[A-Za-z0-9_./-]+',remote) is not None and '..' not in Path(remote).parts,'REMOTE_PATH')
    require(1 <= port <= 65535,'SSH_PORT')
    local = Path(local).resolve();local.mkdir(parents=True,exist_ok=True)
    def fetch(name,path):
        subprocess.run(['scp','-oBatchMode=yes','-oConnectTimeout=20','-P',str(port),
                        target+':'+remote.rstrip('/')+'/'+name,str(path)],check=True)
    index_path = local/'BACKUP_INDEX.json'
    if not index_path.is_file() or sha(index_path)!=index_sha:
        pending = local/'BACKUP_INDEX.download'
        fetch('BACKUP_INDEX.json',pending)
        require(sha(pending)==index_sha,'BACKUP_INDEX_SHA')
        os.replace(pending,index_path)
    index = read(index_path);validate_index(index)
    needed = [item for item in index['chunks'] if not (local/item['name']).is_file() or
              (local/item['name']).stat().st_size != item['bytes'] or sha(local/item['name']) != item['sha256']]
    # Reject an undersized D: before any large download; use another volume for cache.
    require(shutil.disk_usage(local).free > sum(x['bytes'] for x in needed)+512*1024**2,'LOCAL_DOWNLOAD_DISK_REQUIRED')
    for item in needed:
        pending = local/(item['name']+'.download')
        fetch(item['name'],pending)
        require(pending.stat().st_size==item['bytes'] and sha(pending)==item['sha256'],'DOWNLOADED_CHUNK_SHA')
        os.replace(pending,local/item['name'])
    return verify_download(local,index_sha)
