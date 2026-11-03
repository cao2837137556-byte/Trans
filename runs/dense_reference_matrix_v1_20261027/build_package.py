"""Seal a fresh portable distribution; never upload, authorize or submit it."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import tarfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'src'))
from common import read, require, sha, verify_package, write


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    destination = Path(args.output).resolve()
    require(not destination.exists(), 'FRESH_DISTRIBUTION_REQUIRED')
    destination.mkdir(parents=True)
    package = destination / 'package'
    package.mkdir()
    for directory in ('src', 'tests', 'config', 'assets', 'vendor', 'wheels', 'hpc'):
        shutil.copytree(HERE / directory, package / directory,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in ('README.md', 'PROTOCOL.md', 'EXECUTION_CARD.md'):
        shutil.copyfile(HERE / name, package / name)
    shutil.copytree(HERE / 'preparation/frozen_final', package / 'preparation/frozen_final')
    for pattern in ('*REVIEW.md', '*REVIEW.json', '*AUDIT.md', '*AUDIT.json', 'ASSET_CLOSURE_RECEIPT.json'):
        for path in (HERE / 'preparation').glob(pattern):
            shutil.copyfile(path, package / 'preparation' / path.name)
    # Pin the confirmed scientific documents alongside the executable contract.
    protocol = package / 'protocol'
    protocol.mkdir()
    document_names = (
        '20261025_c1_c3_readout_and_step2_r1_claude.md',
        '20261025_c2b_c4_dryrun_readout_r2_claude.md',
        '20261026_c5_readout_matrix_spec_r3_claude.md',
        '20261026_step4_source_controls_r1_claude.md',
    )
    documents = []
    for name in document_names:
        original = HERE.parents[1] / 'runs/mainline_docs/collab' / name
        shutil.copyfile(original, protocol / name)
        documents.append(dict(path='protocol/' + name, sha256=sha(original)))
    write(protocol / 'PROVENANCE.json', dict(documents=documents,
        interpretation='confirmed epsilon and scope; latest r3 WRONG; step4 corrects proxy overclaims'))
    for path in (package / 'hpc').glob('*.slurm'):
        path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n'))
    files = sorted(p for p in package.rglob('*') if p.is_file())
    (package / 'PACKAGE_SHA256SUMS').write_text(''.join(
        sha(p) + '  ' + p.relative_to(package).as_posix() + '\n' for p in files), encoding='utf-8')
    package_sha = verify_package(package)
    archive = destination / (HERE.name + '.tar.gz')
    with tarfile.open(archive, 'w:gz', compresslevel=6) as stream:
        for path in sorted(package.rglob('*')):
            info = stream.gettarinfo(str(path), arcname=HERE.name + '/' + path.relative_to(package).as_posix())
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            if path.suffix == '.slurm':
                info.mode = 0o755
            if path.is_file():
                with path.open('rb') as handle:
                    stream.addfile(info, handle)
            else:
                stream.addfile(info)
    receipt = dict(schema='dense-reference-distribution-v1', status='SEALED',
        created_utc=datetime.now(timezone.utc).isoformat(), files=len(files),
        package_sha256=package_sha, archive_sha256=sha(archive), archive_bytes=archive.stat().st_size,
        archive=str(archive), full_matrix_ready=False,
        blockers=read(package / 'config/chain.json')['matrix_execution_blockers'],
        cloud_authorized=False, submitted_jobs=0, real_forwards=0, new_target_evaluations=0)
    write(destination / 'PACKAGE_RECEIPT.json', receipt)
    print(package_sha)


if __name__ == '__main__':
    main()
