"""Future user-run installation; standard library only, no training/submission."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,tarfile,shutil
ROOT='/public/home/jiangxinwei.zr/work/legacy_qref_device_confirmation_v1_20260923'
RECIPE='092d57859cc36b40ec241281355bca1a9861d38e355755a8d5e3511fcf7efc47'
def require(ok,message):
    if not ok:raise RuntimeError(message)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def inventory(path):
    side=path.with_name(path.name+'.sha256').read_text().strip().split()
    require(len(side)==2 and side[1]==path.name and sha(path)==side[0],'ARCHIVE_CHECKSUM:'+path.name)
    with tarfile.open(path) as t:
        members=t.getmembers();names=[]
        for m in members:
            p=PurePosixPath(m.name)
            require(m.isfile() and not p.is_absolute() and '..' not in p.parts and '\\' not in m.name,'UNSAFE_MEMBER')
            names.append(m.name)
        require(len(set(names))==len(names),'DUPLICATE_MEMBER')
    return set(names)
def install(code,inputs,authorization,destination):
    require(str(destination)==ROOT and not destination.exists(),'DESTINATION_MUST_BE_NEW_EXACT_ROOT')
    scope=json.loads(authorization.read_text())
    require(scope.get('execution_authorized') is True and scope.get('package_inputs') is True and scope.get('recipe_sha256')==RECIPE,'AUTHORIZATION')
    require(scope.get('root')==ROOT and scope.get('output')==ROOT+'/runs/confirmation' and scope.get('training') is False and scope.get('calibration') is False and scope.get('retries')==0,'SCOPE')
    a=inventory(code);b=inventory(inputs);require(not a&b,'PACKAGE_COLLISION')
    require('SHA256SUMS' in a and 'runs/legacy_reference_sample_preparation_v1_20260917/finalized/device_holdout.jsonl.gz' in b,'PACKAGE_CONTENTS')
    destination.mkdir()
    # Every archive member was checked; no links/directories or overwrites are accepted.
    for archive in (code,inputs):
        with tarfile.open(archive) as t:
            for member in t:
                p=destination/member.name;p.parent.mkdir(parents=True,exist_ok=True)
                with t.extractfile(member) as src,p.open('xb') as dst:shutil.copyfileobj(src,dst)
    for line in (destination/'SHA256SUMS').read_text().splitlines():
        h,name=line.split('  ',1);p=(destination/name).resolve()
        require(destination.resolve() in p.parents and sha(p)==h,'INSTALLED_CODE_PIN')
    shutil.copyfile(authorization,destination/'authorization.json')
    print('INSTALLED_VERIFIED_NOT_SUBMITTED')
if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('code','inputs','authorization','destination'):p.add_argument('--'+name,required=True,type=Path)
    a=p.parse_args();install(a.code,a.inputs,a.authorization,a.destination)
