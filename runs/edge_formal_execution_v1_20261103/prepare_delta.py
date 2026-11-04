"""Package only the explicit engineering delta; no network or submission."""
import io
import json
from pathlib import Path
import tarfile

from checkpoint import atomic_json, require, sha
from streaming import ROOT

HERE = Path(__file__).resolve().parent
RECEIPTS = (
    'FORMAL_EXECUTION_CARD_DRAFT.json', 'ENGINEERING_GATE_CARD_DRAFT.json',
    'CHECKPOINT_TEST_RECEIPT.json', 'STREAMING_TEST_RECEIPT.json',
    'STATISTICS_TEST_RECEIPT.json', 'STATISTICS_METADATA_VERIFICATION.json',
    'POPULATION_TEMPORAL_CENSUS.json', 'POPULATION_TEMPORAL_CENSUS_SUMMARY.json',
    'MEASURED_BUDGET.json', 'BUDGET_TEST_RECEIPT.json', 'UDP_PROBE_RESULT.json', 'UDP_PROBE_SUPERVISOR.json',
    'ENGINEERING_REVIEW_BUDGET_AGENT.json', 'ENGINEERING_GATE_TEST_RECEIPT.json',
    'ENGINEERING_GATE_INDEPENDENT_REVIEW.json',
)


def main():
    paths = sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.md'))
    for name in RECEIPTS:
        path = HERE/name
        require(path.is_file(), 'DELIVERY_REQUIRED_FILE:'+name)
        paths.append(path)
    paths = sorted(set(paths))
    require(all(p.parent == HERE and p.stat().st_size < 8*1024**2 for p in paths), 'DELTA_SMALL_FILE_SCOPE')
    pins = {p.relative_to(ROOT).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in paths}
    private = HERE/'.private'
    private.mkdir(exist_ok=True)
    archive = private/'engineering_delta.tar'
    with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as tar:
        for path in paths:
            data = path.read_bytes()
            info = tarfile.TarInfo(path.relative_to(ROOT).as_posix())
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            tar.addfile(info, io.BytesIO(data))
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        require({m.name for m in members} == set(pins) and len(members) == len(pins), 'DELTA_MEMBER_COVERAGE')
        import hashlib
        for member in members:
            payload = tar.extractfile(member).read()
            pin = pins[member.name]
            require(len(payload) == pin['bytes'] and hashlib.sha256(payload).hexdigest() == pin['sha256'],
                    'DELTA_MEMBER_SHA_SIZE')
    receipt = dict(schema='EDGE_FORMAL_ENGINEERING_DELTA_V1', status='LOCAL_PACKAGE_VERIFIED_NOT_SUBMITTED',
        archive=dict(path=archive.relative_to(ROOT).as_posix(), bytes=archive.stat().st_size, sha256=sha(archive)),
        files=pins, existing_data_reupload_required=False, formal_evaluation_authorized=False,
        cloud_jobs_submitted=0, automatic_resubmit=False,
        remote_prerequisite='Existing verified181418 full root/assets/raw inputs; verify card artifact pins before any model call')
    atomic_json(HERE/'DELIVERY_DELTA_MANIFEST.json', receipt)
    print(json.dumps(dict(status=receipt['status'], members=len(paths), archive=receipt['archive'])))


if __name__ == '__main__':
    main()
