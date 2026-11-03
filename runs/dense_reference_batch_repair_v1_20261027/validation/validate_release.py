"""Build and test a local repair release; never execute a model or submit a job."""
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
from datetime import datetime, timezone

OVERLAY = Path(__file__).resolve().parents[1]
REPOSITORY = OVERLAY.parents[1]
ORIGINAL = REPOSITORY/'runs/dense_reference_matrix_v1_20261027/distribution/r2/validation/extracted/dense_reference_matrix_v1_20261027'
OUT = OVERLAY/'validation/final_r1'
DIST = OVERLAY/'distribution/r1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_bytes((json.dumps(value, sort_keys=True, indent=2)+'\n').encode())


def run(argv, cwd, name, env):
    process = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                             creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,
                             timeout=180)
    (OUT/(name+'.stdout.log')).write_bytes(process.stdout)
    (OUT/(name+'.stderr.log')).write_bytes(process.stderr)
    if process.returncode:
        raise RuntimeError(name+':EXIT'+str(process.returncode))
    return dict(returncode=0, stdout_sha256=sha(OUT/(name+'.stdout.log')),
                stderr_sha256=sha(OUT/(name+'.stderr.log')))


def main():
    OUT.mkdir(exist_ok=False)
    DIST.mkdir(parents=True, exist_ok=False)
    files=sorted(path for path in OVERLAY.iterdir() if path.is_file() and path.name!='OVERLAY_SHA256SUMS')
    assert len(files)==15
    assert all(b'\r' not in path.read_bytes() for path in files)
    assert json.loads((OVERLAY/'APPROVAL_TEMPLATE.json').read_bytes())['user_authorized'] is False
    (OVERLAY/'OVERLAY_SHA256SUMS').write_bytes(''.join(sha(path)+'  '+path.name+'\n' for path in files).encode())
    sys.path.insert(0, str(OVERLAY))
    import repair_gate
    proof=repair_gate.verify_inputs(ORIGINAL, OVERLAY)
    old_launch=repair_gate.verify_tree(REPOSITORY/'runs/dense_reference_launch_repair_v1_20261027',
        'OVERLAY_SHA256SUMS','12bac486285b6cbaa0a58df7c8ded17dc6c1a74d79632f2ff7763e33f4c34300',5,
        ignored=('.private','runtime','validation','distribution'))
    old_diagnostic=repair_gate.verify_tree(REPOSITORY/'runs/dense_reference_original104_batch_diagnostic_v1_20261027',
        'PACKAGE_SHA256SUMS','0d6d59c904b6a6e0a29725c99fc628c760e2489fdb2bbbbcf90027bb79c1f1d5',9,
        ignored=('.private','runtime','validation','distribution'))
    env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PAPER04_FROZEN_R2_TEST_ROOT=str(ORIGINAL))
    checks={}
    checks['tests']=run([sys.executable,'-B','-m','unittest','discover','-s',str(OVERLAY),'-p','test_*.py','-v'],OVERLAY,'local_tests',env)
    checks['dry_run']=run([sys.executable,'-B',str(OVERLAY/'run_repaired_chain.py'),'--original',str(ORIGINAL)],OVERLAY,'local_dry_run',env)
    checks['bash_syntax']=run(['C:/Program Files/Git/bin/bash.exe','-n',str(OVERLAY/'run_repair.slurm')],OVERLAY,'bash_syntax',env)
    archive=DIST/(OVERLAY.name+'.tar.gz')
    with archive.open('xb') as raw, gzip.GzipFile(filename='',mode='wb',fileobj=raw,mtime=0) as compressed:
        with tarfile.open(fileobj=compressed,mode='w') as tar:
            for path in files+[OVERLAY/'OVERLAY_SHA256SUMS']:
                data=path.read_bytes()
                member=tarfile.TarInfo(OVERLAY.name+'/'+path.name)
                member.size=len(data);member.mode=0o755 if path.suffix=='.slurm' else 0o644
                member.mtime=0;member.uid=member.gid=0
                tar.addfile(member,io.BytesIO(data))
    extracted=OUT/'extracted'
    extracted.mkdir()
    with tarfile.open(archive,'r:gz') as tar:
        members=tar.getmembers()
        assert all(m.isfile() and len(Path(m.name).parts)==2 and Path(m.name).parts[0]==OVERLAY.name for m in members)
        tar.extractall(extracted)
    unpacked=extracted/OVERLAY.name
    extracted_proof=repair_gate.verify_inputs(ORIGINAL,unpacked)
    assert extracted_proof==proof
    checks['extracted_tests']=run([sys.executable,'-B','-m','unittest','discover','-s',str(unpacked),'-p','test_*.py','-v'],unpacked,'extracted_tests',env)
    checks['extracted_dry_run']=run([sys.executable,'-B',str(unpacked/'run_repaired_chain.py'),'--original',str(ORIGINAL)],unpacked,'extracted_dry_run',env)
    assert 'Ran 26 tests' in (OUT/'extracted_tests.stderr.log').read_text()
    assert 'Ran 26 tests' in (OUT/'local_tests.stderr.log').read_text()
    for name in ('local_dry_run','extracted_dry_run'):
        observed=json.loads((OUT/(name+'.stdout.log')).read_bytes())
        assert observed['status']=='DRY_RUN_PASS' and observed['physical_positions']==22514
        assert observed['real_forwards']==observed['checkpoint_loads']==observed['remote_submissions']==0
    result=dict(schema='paper04-singleton-repair-release-validation-v1',status='PASS',
        created_utc=datetime.now(timezone.utc).isoformat(),proof=proof,checks=checks,
        source_tests=26,extracted_tests=26,all_source_files_lf=True,approval_template_false=True,
        original_package_unchanged=proof['original'],old_launch_unchanged=old_launch,old_diagnostic_unchanged=old_diagnostic,
        archive=str(archive.relative_to(OVERLAY)),archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
        physical_positions=22514,logical_rows=21764,logical_new_positions=21660,clone_positions=750,
        real_forwards=0,checkpoint_loads=0,optimizer_updates=0,target_evaluations=0,remote_submissions=0,
        original104_real_replay='PENDING_NEW_AUTHORIZED_JOB',full_matrix_ready=False,
        remaining_blockers=['FROZEN_THIRD_POOL_BASE_B2_ASSETS_ABSENT'])
    write(OUT/'ACCEPTANCE.json',result)
    write(DIST/'ARCHIVE.json',dict(archive=archive.name,archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
        overlay_manifest_sha256=proof['overlay']['manifest_sha256'],sealed_files=proof['overlay']['files']))
    print(json.dumps(dict(status='PASS',archive_sha256=sha(archive),overlay=proof['overlay'],tests=26,extracted_tests=26)))


if __name__=='__main__':
    main()
