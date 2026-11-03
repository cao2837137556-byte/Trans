"""Seal a disabled, reviewable candidate outside the source directory."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import tarfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = ROOT / 'runs/dense_reference_ab_stage_distribution_20261028/r1'


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024**2), b''):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    if OUTPUT.exists():
        raise RuntimeError('DISTRIBUTION_ALREADY_EXISTS_NEVER_OVERWRITE')
    payload = OUTPUT / 'payload'
    payload.mkdir(parents=True)
    files = []
    for path in sorted(HERE.rglob('*')):
        relative = path.relative_to(HERE)
        if '__pycache__' in relative.parts or relative.parts[0] in ('.private', 'preparation'):
            continue
        if path.is_symlink():
            raise RuntimeError('CANDIDATE_SYMLINK_REJECTED')
        if not path.is_file():
            continue
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        if sha(path) != sha(target):
            raise RuntimeError('COPY_IDENTITY_FAILURE')
        files.append(target)
    if (payload / '.private/APPROVED.json').exists():
        raise RuntimeError('PRODUCTION_APPROVAL_MUST_NOT_BE_BUNDLED')
    sums = payload / 'PACKAGE_SHA256SUMS'
    sums.write_text(''.join(sha(path) + '  ' + path.relative_to(payload).as_posix() + '\n'
        for path in files), encoding='utf-8', newline='\n')
    archive = OUTPUT / 'dense_reference_ab_stage_candidate_v1_20261028.tar.gz'
    with tarfile.open(archive, 'w:gz', compresslevel=5) as stream:
        for path in sorted(payload.rglob('*')):
            if path.is_file():
                stream.add(path, arcname=path.relative_to(payload).as_posix(), recursive=False)
    receipt = dict(schema='paper04-dense-ab-stage-candidate-package-v1',
        status='SEALED_CANDIDATE_NOT_AUTHORIZED', created_utc=datetime.now(timezone.utc).isoformat(),
        package_sha256=sha(sums), archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
        payload_files=len(files)+1, manifest_sha256=sha(payload/'config/MATRIX_CANDIDATE_HPC.json'),
        source_cal_result_sha256=json.loads((payload/'config/APPROVAL.template.json').read_text(
            encoding='utf-8'))['source_cal_result_sha256'],
        production_authorization_bundled=False, real_target_evaluations=0, remote_operations=0,
        original_registered_matrix_complete=False)
    (OUTPUT/'PACKAGE_RECEIPT.json').write_text(json.dumps(receipt, indent=2, sort_keys=True)+'\n',
        encoding='utf-8', newline='\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
