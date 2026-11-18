"""Publish only the frozen experiment or its verified small returns on the project mainline."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
REF = 'refs/heads/codex/exp-mainline'
SOURCES = ('.gitattributes','README.md','FROZEN.json','RUNTIME_PACKAGE_MANIFEST.json','PACKAGE_MANIFEST.json',
           'LOCAL_VALIDATION.json','pack.py','worker.py','geometry.py','inputs.py','boundary_checks.py',
           'reports.py','launch.py','run.slurm','verify_local.py','delivery.py','dashboard.py','progress.html',
           'archive_run.py')


def git(args, env=None, *, check=True):
    return subprocess.run(['git',*args],cwd=PROJECT,env=env,capture_output=True,text=True,
                          encoding='utf-8',errors='replace',timeout=60,check=check)


def publish(phase):
    if phase == 'freeze':
        paths = [HERE/n for n in SOURCES]
        paths.append(HERE.parent/'mainline_docs/collab/20261117_paper04_v12_dual_component_mean_support_handoff_codex.md')
        message = 'Freeze Paper04 table 9 paired weak versus mean component support replay'
    else:
        dest=HERE/'received'
        receipt=json.loads((dest/'LOCAL_ACCEPTANCE.json').read_bytes())
        if receipt['status'] != 'PASS':
            raise ValueError('UNACCEPTED_RESULTS')
        names=list(json.loads((dest/'RETURN.json').read_bytes())['files'])+['RETURN.json','LOCAL_ACCEPTANCE.json']
        if any(Path(n).name != n or n.endswith(('.npz','.npy','.gz')) for n in names):
            raise ValueError('SMALL_ACCEPTED_FILES_ONLY')
        paths=[dest/n for n in names]+[HERE/'INSTALL_READBACK.json']
        message='Accept Paper04 paired weak versus mean support experiment '+receipt['jobs']['formal']
    names=[p.relative_to(PROJECT).as_posix() for p in paths]
    for attempt in range(3):
        advertised=git(['ls-remote','--exit-code','origin',REF]).stdout.strip().split()
        if len(advertised) != 2 or advertised[1] != REF:
            raise ValueError('GIT_MAINLINE_REF')
        base=advertised[0]
        if git(['cat-file','-e',base+'^{commit}'],check=False).returncode:
            git(['fetch','--quiet','--no-write-fetch-head','--no-tags','origin',base])
        remote_manifest=git(['show',base+':'+(HERE/'PACKAGE_MANIFEST.json').relative_to(PROJECT).as_posix()],check=False)
        if remote_manifest.returncode == 0 and json.loads(remote_manifest.stdout) != json.loads((HERE/'PACKAGE_MANIFEST.json').read_bytes()):
            raise ValueError('REMOTE_RUN_ALREADY_HAS_DIFFERENT_PACKAGE')
        with tempfile.TemporaryDirectory(prefix='p04-paired-index-') as folder:
            env=dict(os.environ,GIT_INDEX_FILE=str(Path(folder)/'index'))
            git(['read-tree',base],env)
            git(['add','-f','--',*names],env)
            changed=git(['diff','--cached','--name-only','-z',base,'--'],env).stdout.split('\0')
            if not set(filter(None,changed)).issubset(names):
                raise ValueError('GIT_PATH_SCOPE')
            if not any(changed):
                return base
            tree=git(['write-tree'],env).stdout.strip()
            commit=git(['commit-tree',tree,'-p',base,'-m',message],env).stdout.strip()
        pushed=git(['push','origin',commit+':'+REF],check=False)
        if pushed.returncode == 0:
            return commit
        if attempt==2 or not any(s in pushed.stderr for s in ('fetch first','non-fast-forward','failed to update ref','stale info')):
            raise RuntimeError('SCOPED_GIT_PUSH:'+pushed.stderr.strip())


if __name__=='__main__':
    if sys.argv[1:] not in (['freeze'],['results']):
        raise SystemExit('Expected freeze or results')
    print(publish(sys.argv[1]))
