"""Seal the A-only evaluator; verify full startup without loading a real model."""
import ast
import os
import subprocess
import tempfile
from pathlib import Path
import issue27frontend_a_expanded_eval_v1 as a
s=a.s


def main():
    s.require(not a.REAL.exists() and not (a.PACKAGE/'SHA256SUMS').exists(),'ALREADY_FROZEN_OR_STARTED')
    tests=s.read_json(a.PACKAGE/'tests.json');s.require(tests['status']=='PASS' and tests['tests_run']==tests['tests_passed']==9,'TESTS')
    a.verify_manifest(s.PACKAGE,'9208679615bcd30dbb9f0b43542db00d7b83c7f41adf426bf586ba3d0b1eba46')
    base=s.read_json(s.PACKAGE/'config.json');pins=dict(base['code_pins'])
    new=[p.relative_to(s.ROOT).as_posix() for p in (s.ROOT/'repo/ood').glob('issue27frontend_a_expanded_eval*_v1.py')]
    new+=['scripts/start_frontend_a_expanded_eval_local.ps1','scripts/show_frontend_a_expanded_eval_status.ps1',
          'runs/mainline_docs/frontend_a_expanded_eval_execution_20260911.md']
    doc=s.ROOT/new[-1];doc.with_suffix('.sha256').write_text(s.sha_file(doc)+'  '+doc.name+'\n',encoding='utf-8')
    new.append(doc.with_suffix('.sha256').relative_to(s.ROOT).as_posix())
    for rel in new:
        if rel.endswith('.py'):ast.parse((s.ROOT/rel).read_text(encoding='utf-8'))
        pins[rel]=s.sha_file(s.ROOT/rel)
    for rel,h in pins.items():s.require(s.sha_file(s.ROOT/rel)==h,'CODE_IDENTITY')
    a.verify_manifest(a.SOURCE,a.SOURCE_SEAL)
    source_pins={}
    for line in (a.SOURCE/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h,rel=line.split('  ',1)
        if '/' not in rel:source_pins[(a.SOURCE/rel).relative_to(s.ROOT).as_posix()]=h
    source_pins[(a.SOURCE/'SHA256SUMS').relative_to(s.ROOT).as_posix()]=a.SOURCE_SEAL
    train=a.CANDIDATE.parent
    for line in (train/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h,rel=line.split('  ',1)
        if rel in ('candidate_A.pt','candidate_A.receipt.json','candidates_sealed.json'):
            s.require(s.sha_file(train/rel)==h,'A_TRAINING_IDENTITY');source_pins[(train/rel).relative_to(s.ROOT).as_posix()]=h
    cfg={'authorization':a.AUTH,'caps':a.CAPS,'code_pins':pins,'runtime_pins':base['runtime_pins'],
         'input_pins':source_pins,'unrelated_tracked_sha256':base['unrelated_tracked_sha256'],
         'git_path':'C:/Program Files/Git/mingw64/bin/git.exe',
         'git_sha256':'fc0f1cae1304fcdcf4d0749f421c5ed21471efc856301f92f56d4b844be84363'}
    s.atomic_json(a.PACKAGE/'config.json',cfg)
    s.atomic_json(a.PACKAGE/'acceptance.json',{**tests,'config_sha256':s.sha_file(a.PACKAGE/'config.json'),'powershell_parse':'PASS'})
    s.seal(a.PACKAGE)
    # Exercise precisely the full worker readiness inside the same Job process limit.
    with tempfile.TemporaryDirectory(dir=s.ROOT/'tmp') as d:
        gate=Path(d)/'gate'
        code="import pathlib,sys,time; gate=pathlib.Path(sys.argv[1]);\nwhile not gate.exists():time.sleep(.01)\nsys.path.insert(0,sys.argv[2]);import issue27frontend_a_expanded_eval_v1 as a;a.readiness();print('READY_INSIDE_JOB')"
        p=subprocess.Popen([str(s.PYTHON),'-B','-c',code,str(gate),str(s.ROOT/'repo/ood')],cwd=s.ROOT,
                           stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        job=None
        try:
            job=a.Job(p,512*1024**2);gate.touch();stdout,stderr=p.communicate(timeout=60)
            s.require(p.returncode==0 and b'READY_INSIDE_JOB' in stdout,stderr.decode())
        finally:
            if p.poll() is None:
                if job:job.terminate()
                else:p.kill()
                p.wait(timeout=10)
            if job:job.close()
    folder=s.ROOT/'runs/frontend_a_expanded_eval_startup_verification_v1_20260911';folder.mkdir()
    s.atomic_json(folder/'verification.json',{'status':'PASS','full_sealed_readiness_inside_job':True,
                  'model_loads':0,'raw_decodes':0,'real_attempts':0,'implementation_manifest_sha256':s.sha_file(a.PACKAGE/'SHA256SUMS')})
    s.seal(folder);print('A implementation sealed; 9 tests and full Job readiness PASS')


if __name__=='__main__':main()
