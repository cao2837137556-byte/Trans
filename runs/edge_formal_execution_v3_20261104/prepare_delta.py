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
    'ENGINEERING_GATE_TEST_RECEIPT.json', 'REPAIR_REGRESSION_RECEIPT.json',
    'LOCAL_REGRESSION_RECEIPT.json', 'PROGRESS_IO_TEST_RECEIPT.json',
    'V3_INTEGRATION_TEST_RECEIPT.json', 'V3_PROVENANCE.json',
)


def main():
    paths = sorted(HERE.glob('*.py')) + sorted(HERE.glob('*.md'))
    paths += sorted(p for p in (HERE/'validation_history').rglob('*') if p.is_file())
    for name in RECEIPTS:
        path = HERE/name
        require(path.is_file(), 'DELIVERY_REQUIRED_FILE:'+name)
        paths.append(path)
    # Carry every pin absent from the verified base, not only the new folder.
    # This includes previously sealed provenance arrays; none go into Git.
    from dependency_identity import BASE, read, verify
    card = read(HERE/'ENGINEERING_GATE_CARD_DRAFT.json')
    verify(card, ROOT)
    base_files = read(ROOT/BASE)['files']
    for relative in card['artifact_pins']:
        if relative not in base_files:
            paths.append(ROOT/relative)
    paths = sorted(set(paths))
    require(all(p.resolve().is_relative_to(ROOT.resolve()) and p.stat().st_size < 16*1024**2
                for p in paths), 'DELTA_FILE_SCOPE')
    require(sum(p.stat().st_size for p in paths) < 128*1024**2, 'DELTA_TOTAL_BOUND')
    require(set(card['artifact_pins']) <= set(base_files) | {p.relative_to(ROOT).as_posix() for p in paths},
            'BASE_PLUS_DELTA_PIN_COVERAGE')
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
    receipt = dict(schema='EDGE_FORMAL_ENGINEERING_DELTA_V3', status='LOCAL_PACKAGE_VERIFIED_NOT_SUBMITTED',
        archive=dict(path=archive.relative_to(ROOT).as_posix(), bytes=archive.stat().st_size, sha256=sha(archive)),
        files=pins, raw_and_model_reupload_required=False, formal_evaluation_authorized=False,
        base_manifest_sha256=sha(ROOT/BASE), all_card_pins_covered_by_base_plus_delta=True,
        note='Delta includes small historical provenance assets absent from base; models/raw are reused',
        cloud_jobs_submitted=0, automatic_resubmit=False,
        remote_prerequisite='Verified863-file base plus this delta and existing full raw inputs; run full dependency verification before models or spool reuse')
    atomic_json(HERE/'DELIVERY_DELTA_MANIFEST.json', receipt)
    print(json.dumps(dict(status=receipt['status'], members=len(paths), archive=receipt['archive'])))


if __name__ == '__main__':
    main()
