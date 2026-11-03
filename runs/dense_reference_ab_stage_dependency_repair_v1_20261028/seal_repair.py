"""Create a fresh self-contained overlay seal/archive; never submit work."""
import hashlib
import json
from pathlib import Path
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
DIST=ROOT/'runs/dense_reference_ab_stage_dependency_repair_distribution_20261028/r1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest=HERE/'PACKAGE_SHA256SUMS'
    if manifest.exists() or DIST.exists():
        raise RuntimeError('FRESH_REPAIR_SEAL_AND_DISTRIBUTION_REQUIRED')
    files=sorted(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts
        and p.relative_to(HERE).parts[0] not in ('.private','runtime','local_progress'))
    manifest.write_text(''.join(sha(p)+'  '+p.relative_to(HERE).as_posix()+'\n' for p in files),
                        encoding='utf-8',newline='\n')
    DIST.mkdir(parents=True)
    archive=DIST/(HERE.name+'.tar.gz')
    with tarfile.open(archive,'w:gz',compresslevel=6) as bundle:
        for path in files+[manifest]:
            bundle.add(path,arcname=HERE.name+'/'+path.relative_to(HERE).as_posix(),recursive=False)
    receipt=dict(status='PREPARED_NOT_AUTHORIZED',package_manifest_sha256=sha(manifest),
        archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,
        package_files=len(files),archive=archive.as_posix(),scientific_retries=0,
        original_candidate_modified=False,target_evaluations=0)
    (DIST/'PACKAGE_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


if __name__=='__main__': main()
