# Inlined by build_inventory.py. Read-only file presence and identity probe.
import hashlib
import json
from pathlib import Path
import shutil
import stat
import subprocess

ROOT = Path(PROBE_MANIFEST['project']).resolve()
HASHES = {}


def digest(path):
    value=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(8*1024**2),b''):
            value.update(block)
    return value.hexdigest()


def inspect(spec):
    found=[]
    for rel in spec['paths']:
        path=ROOT/rel
        try:
            st=path.stat()
        except FileNotFoundError:
            found.append(dict(path=rel,status='MISSING'))
            continue
        except OSError as e:
            found.append(dict(path=rel,status='UNREADABLE',error=str(e)))
            continue
        item=dict(path=rel,bytes=st.st_size,mtime_ns=st.st_mtime_ns,links=st.st_nlink)
        if not path.resolve().is_relative_to(ROOT):
            item['status']='PATH_OUTSIDE_PROJECT'
            found.append(item)
            continue
        if not stat.S_ISREG(st.st_mode):
            item['status']='NOT_REGULAR_FILE'
        elif 'bytes' in spec and spec['bytes'] is not None and st.st_size!=spec['bytes']:
            item['status']='SIZE_MISMATCH'
        elif spec['sha256'] and spec['group']!='query':
            try:
                identity=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
                item['sha256']=HASHES[identity] if identity in HASHES else digest(path)
                end=path.stat()
                if (st.st_ino,st.st_size,st.st_mtime_ns)!=(end.st_ino,end.st_size,end.st_mtime_ns):
                    item['status']='CHANGED_DURING_READ'
                else:
                    HASHES[identity]=item['sha256']
                    item['status']='SHA_MATCH' if item['sha256']==spec['sha256'] else 'SHA_MISMATCH'
            except OSError as e:
                item.update(status='UNREADABLE',error=str(e))
        else:
            item['status']='PRESENT_QUERY_BYTES_UNREAD' if spec['group']=='query' else 'PRESENT_NEEDS_IDENTITY_GATE'
        found.append(item)
    return found


def scheduler():
    result={}
    for label,argv in [
        ('squeue',['squeue','-h','-u',__import__('getpass').getuser(),'-o','%i|%j|%T']),
        ('sacct',['sacct','-X','-n','-P','-u',__import__('getpass').getuser(),
                  '-S','2026-11-11','-o','JobIDRaw,JobName%100,State,ExitCode']),
    ]:
        try:
            p=subprocess.run(argv,capture_output=True,text=True,timeout=30)
            match=[x for x in p.stdout.splitlines() if any(k in x.lower() for k in ('k8192','p04-unified'))]
            result[label]=dict(returncode=p.returncode,matches=match)
        except (OSError,subprocess.TimeoutExpired) as e:
            result[label]=dict(error=type(e).__name__)
    return result


result=dict(status='READ_ONLY_HPC_INVENTORY',frozen_card_sha256=PROBE_MANIFEST['frozen_card_sha256'],
            target_run_exists=(ROOT/'runs'/PROBE_MANIFEST['run']).exists(),
            free_bytes=shutil.disk_usage(ROOT).free,scheduler=scheduler(),files={},
            query_file_bodies_read=False,submitted_jobs=0)
for key,spec in PROBE_MANIFEST['files'].items():
    found=inspect(spec)
    result['files'][key]=found
    print(key,','.join(x['status'] for x in found),flush=True)
summary={'target_run_exists':result['target_run_exists'],'free_bytes':result['free_bytes'],
         'scheduler':result['scheduler'],'verified_path_index':{},'unresolved':{}}
for key,found in result['files'].items():
    good=[i for i,x in enumerate(found,1) if x['status']=='SHA_MATCH']
    if good:
        summary['verified_path_index'][key]=good[0]
    elif not any(x['status']=='PRESENT_QUERY_BYTES_UNREAD' for x in found):
        summary['unresolved'][key]=[x['status'] for x in found]
print('PAPER04_K8192_JSON_BEGIN')
print(json.dumps(result,ensure_ascii=True,separators=(',',':')))
print('PAPER04_K8192_JSON_END')
print('PAPER04_K8192_SUMMARY')
print(json.dumps(summary,ensure_ascii=True,separators=(',',':')))
