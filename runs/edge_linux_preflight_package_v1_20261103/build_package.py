"""Deterministic archive of frozen dependencies + sealed selection; no model imports.

Raw PCAPs are separately pinned remote inputs, never duplicated into this bundle.
Run only after the selected-UID seal exists. Never overwrites an archive.
"""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import shutil
import tarfile

from verify_package import sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENGINEERING = ROOT / 'runs/edge_external_test1_engineering_v1_20261103'
RUNTIME = ROOT / 'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def project_path(value):
    path = Path(value)
    return (path if path.is_absolute() else ROOT / path).resolve()


def write(path, body):
    path = Path(path)
    path.write_text(json.dumps(body, sort_keys=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    sidecar(path)


def sidecar(path):
    path = Path(path)
    path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')


def inputs(selection_dir, seal, slice_path):
    paths = set()

    def add(path, expected=None):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file():
            raise ValueError('MISSING_OR_ESCAPE:' + str(path))
        if expected and sha(path) != expected:
            raise ValueError('SOURCE_PIN_CHANGED:' + str(path))
        paths.add(path)
        if path.with_name(path.name + '.sha256').is_file():
            paths.add(path.with_name(path.name + '.sha256'))

    # One complete stdlib-auditable local-module namespace avoids a fragile
    # guessed import closure; these are only ~12 MB, never executed at build.
    for path in (ROOT / 'repo/ood').glob('*.py'):
        add(path)
    for relative in ('preflight/run_preflight.py', 'preflight/engine.py', 'preflight/SLICE_CARD.json',
                     'preflight/RUNTIME_PREFLIGHT_REQUEST.json', 'preflight/README.md',
                     'adapter/edge_adapter.py', 'adapter/preflight_plan_r2_stratified/SLICE_FRAME_PLAN.json',
                     'evaluation.py', 'baselines/knn5.py', 'baselines/SOURCE_CALIBRATION.json'):
        add(ENGINEERING / relative)
    add(ENGINEERING / 'ENGINEERING_CARD_R2.json')
    for name in ('METHOD_FREEZE.json', 'METHOD_FREEZE.json.sha256'):
        add(ROOT / 'runs/c5_method_freeze_v1_20261102' / name)
    add(ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json',
        'ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7')
    add(ROOT / 'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json')
    for path in (ENGINEERING / 'adapter/population_v1').iterdir():
        if path.is_file() and path.suffix in ('.json', '.bin'):
            add(path)
    add(ENGINEERING / 'adapter/population_v1/REFERENCE_ROWS.jsonl.gz')
    for name in ('POPULATION_SEAL.json', 'REFERENCE_ROWS.jsonl.gz'):
        add(ENGINEERING / 'adapter/population_sealed_v1' / name)
    add(ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
    asset_spec = read(ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')

    def collect(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                add(ROOT / value['path'], value['sha256'])
            else:
                for item in value.values():
                    collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)

    for category in ('heads', 'calibration'):
        collect(asset_spec[category])
    history = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'
    for path in (history / 'hnr').glob('*.py'):
        add(path)
    for name in ('EXECUTION.json', 'ENCODER_RUNTIME_FILES.json'):
        add(history / 'config' / name)
    for name, expected in read(history / 'config/ENCODER_RUNTIME_FILES.json')['files'].items():
        add(RUNTIME / name, expected)
    for name in ('CAL_E3.npy', 'CAL_FIXED_INPUTS.npz'):
        path = ROOT / 'runs/c5_kernel_independent_replay_codex_20261102/source_cal' / name
        expected = path.with_name(path.name + '.sha256').read_text(encoding='utf-8-sig').split()[0]
        add(path, expected)
    add(ROOT / 'runs/c5_kernel_independent_replay_codex_20261102/ab/replay.py')
    for path in selection_dir.rglob('*'):
        if not path.is_file() or path.suffix in ('.sqlite', '.tmp', '.log', '.npy', '.npz'):
            continue
        if path.parent == selection_dir and path.name in ('PROGRESS.md', 'PROGRESS.md.sha256'):
            continue
        if path.name.endswith(('.sqlite-wal', '.sqlite-shm', '.sqlite-journal',
                               '.db', '.db-wal', '.db-shm', '.db-journal')):
            continue
        if path.name.endswith('_metadata.tsv.gz') or path.name.endswith('_metadata.tsv.gz.sha256'):
            continue
        if path.name.endswith(('.tsv', '.tsv.gz', '.tsv.sha256', '.tsv.gz.sha256')):
            continue
        if '__pycache__' in path.parts or any(x in path.parts for x in ('working', 'scratch', 'temp')):
            continue
        # Keep stopped shape-attempt receipts for provenance, but never carry
        # its scratch state. The active slice's own shape directory is sealed.
        shape_parts = [x for x in path.relative_to(selection_dir).parts if x == 'shapes' or x.startswith('shapes_')]
        if shape_parts and not path.is_relative_to(slice_path.parent):
            if path.name not in ('FAILURE.json', 'FAILURE.json.sha256', 'PROGRESS.json',
                                 'PROGRESS.json.sha256', 'INTERRUPTION.json', 'INTERRUPTION.json.sha256',
                                 'ABORT_RECEIPT.json', 'ABORT_RECEIPT.json.sha256'):
                continue
        if path.stat().st_size > 64 * 1024**2:
            raise ValueError('UNREVIEWED_LARGE_SELECTION_FILE:' + str(path))
        add(path)
    if seal not in paths:
        raise ValueError('SELECTION_SEAL_NOT_INCLUDED')
    for name in ('EXECUTION_OVERLAY.json', 'run_preflight_with_probes.py', 'strict_shape_probes.py'):
        add(selection_dir / name)
    selected_spec = read(seal)
    add(ROOT / selected_spec['source_contract']['path'], selected_spec['source_contract']['sha256'])
    add(ROOT / selected_spec['references']['source_path'], selected_spec['references']['source_sha256'])
    add(slice_path)
    shape_plan = project_path(read(slice_path)['plan_path'])
    add(shape_plan, read(slice_path)['plan_sha256'])
    if (shape_plan.parent / 'VERIFICATION.json').is_file():
        add(shape_plan.parent / 'VERIFICATION.json')
    shape_spec = read(shape_plan)
    if shape_spec.get('schema') == 'EDGE_FULL_AND_TARGET_SHAPE_COVERAGE_DERIVATION_V1':
        add(project_path(shape_spec['source_census_path']), shape_spec['source_census_sha256'])
        add(project_path(shape_spec['parent_slice_path']), shape_spec['parent_slice_sha256'])
        if (project_path(shape_spec['source_census_path']).parent / 'VERIFICATION.json').is_file():
            add(project_path(shape_spec['source_census_path']).parent / 'VERIFICATION.json')
    for name in ('verify_package.py', 'runtime_identity.py', 'launch_preflight.py', 'preflight.slurm',
                 'build_package.py', 'test_package.py', 'TEST_RECEIPT.json',
                 'README.md', 'ACTIVE_SLICE_CARD.json', 'PACKAGE_CONTRACT.json'):
        add(HERE / name)
    prior_pins = read(ENGINEERING / 'ENGINEERING_CARD_R2.json')['artifact_pins']
    for path in paths:
        old_pin = prior_pins.get(path.relative_to(ROOT).as_posix())
        if old_pin and sha(path) != old_pin:
            raise ValueError('PRIOR_SEALED_ENGINEERING_FILE_CHANGED:' + str(path))
    return sorted(paths)


def tar_add(archive, source, name):
    info = tarfile.TarInfo(name)
    info.size = source.stat().st_size
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ''
    info.mode = 0o755 if source.suffix == '.slurm' else 0o644
    with source.open('rb') as stream:
        archive.addfile(info, stream)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--selection-dir', required=True)
    parser.add_argument('--selection-seal', required=True)
    parser.add_argument('--slice', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    selection_dir, seal, slice_path = (Path(x).resolve() for x in
        (args.selection_dir, args.selection_seal, args.slice))
    output = Path(args.output).resolve()
    if output.exists() or output.with_suffix(output.suffix + '.tmp').exists():
        raise ValueError('NO_OVERWRITE_PACKAGE')
    if not seal.is_relative_to(selection_dir):
        raise ValueError('SELECTION_SEAL_SCOPE')
    expected = seal.with_name(seal.name + '.sha256').read_text(encoding='utf-8-sig').split()[0]
    if sha(seal) != expected:
        raise ValueError('SELECTION_SEAL_SHA')
    selection_spec = read(seal)
    if (selection_spec.get('schema') != 'EDGE_QUERY_SELECTION_SEAL_V1'
            or selection_spec.get('status') != 'SEALED_METADATA_ONLY_BASE_QUOTA'
            or selection_spec.get('model_forwards') != 0
            or selection_spec.get('external_quality_evaluations') != 0):
        raise ValueError('SELECTION_SEAL_NOT_COMPLETE_METADATA_ONLY')
    for name, pin in selection_spec['output_pins'].items():
        path = (seal.parent / name).resolve()
        if not path.is_relative_to(seal.parent) or path.stat().st_size != pin['bytes'] or sha(path) != pin['sha256']:
            raise ValueError('SELECTION_OUTPUT_PIN:' + name)
    for name, expected_code in selection_spec['selection_code_pins'].items():
        if sha(selection_dir / name) != expected_code:
            raise ValueError('SELECTION_SOURCE_CHANGED:' + name)
    slice_spec = read(slice_path)
    required_shapes = {tuple(r['shape']) for r in slice_spec['shape_expansion']['required']['representatives']}
    base_rows = sum(len(x['frames']) for x in slice_spec['slices'])
    if (slice_spec['mode'] != 'FIXED_HEADER_ONLY_ENGINEERING_SLICE' or not required_shapes
            or base_rows + len(required_shapes) > 100):
        raise ValueError('SLICE_AND_REQUIRED_PROBES_BUDGET')
    shape_plan = project_path(slice_spec['plan_path'])
    if not shape_plan.is_relative_to(ROOT) or sha(shape_plan) != slice_spec['plan_sha256']:
        raise ValueError('SHAPE_CENSUS_PATH_ESCAPE')
    coverage = read(shape_plan)
    if coverage.get('schema') == 'EDGE_FULL_AND_TARGET_SHAPE_COVERAGE_DERIVATION_V1':
        if coverage.get('status') != 'PASS_METADATA_ONLY' or coverage['selection_seal_sha256'] != expected:
            raise ValueError('DERIVED_SHAPE_COVERAGE_NOT_COMPLETE_OR_SELECTION_BOUND')
        shape_path = project_path(coverage['source_census_path'])
        if not shape_path.is_relative_to(ROOT) or sha(shape_path) != coverage['source_census_sha256']:
            raise ValueError('DERIVED_SHAPE_CENSUS_SOURCE_SHA')
    else:
        shape_path = shape_plan
    shapes = read(shape_path)
    if (shapes['status'] != 'COMPLETE_NO_MODEL' or shapes['model_forwards'] != 0
            or shapes['selection_seal_sha256'] != expected
            or sum(shapes['target_shape_counts'].values()) != selection_spec['total_logical_encoding_rows']):
        raise ValueError('SHAPE_CENSUS_NOT_COMPLETE_OR_NOT_SELECTION_BOUND')
    shutil.copyfile(slice_path, HERE / 'ACTIVE_SLICE_CARD.json')
    sidecar(HERE / 'ACTIVE_SLICE_CARD.json')
    card = read(ROOT / 'runs/external_scope_review_codex_20261103/EDGE_EXECUTION_CARD_DRAFT.json')
    contract = dict(schema='EDGE_LINUX_PREFLIGHT_PACKAGE_V1',
        status='PACKAGE_PREPARED_NOT_SUBMITTED_OR_RUNTIME_PASSED',
        scope='ENGINEERING_ONLY_NO_FULL_EXTERNAL_EVALUATION',
        selection_seal=seal.relative_to(ROOT).as_posix(), selection_seal_sha256=expected,
        preflight_entry=(selection_dir / 'run_preflight_with_probes.py').relative_to(ROOT).as_posix(),
        active_slice= slice_path.relative_to(ROOT).as_posix(), active_slice_sha256=sha(slice_path),
        shape_census_sha256=sha(shape_path), ordinary_slice_endpoints=base_rows,
        shape_coverage_plan_sha256=sha(shape_plan),
        required_singleton_shape_probes=len(required_shapes),
        total_preflight_logical_with_probes=base_rows+len(required_shapes),
        budget=dict(cpu=1, ram_gib=6, slurm_wall_seconds=600, outer_child_max_seconds=540,
                    unique_encoding_endpoint_cap=100, small_distance_pair_limit=10000),
        raw_inputs_separate_not_archived={role:dict(filename=Path(v['path'].replace('\\', '/')).name,
            bytes=v['bytes'], sha256=v['sha256']) for role,v in card['raw_inputs'].items()},
        expected_runtime=read(ENGINEERING / 'preflight/RUNTIME_PREFLIGHT_REQUEST.json')['required_existing_runtime'],
        full_execution_ready=False, full_streaming_resume_worker_ready=False,
        shape_extreme_coverage_not_assumed=True, full_quality_evaluation_authorized=False,
        automatic_retry=False, automatic_full_evaluation_on_pass=False, training=False,
        post_preflight='Return receipts to Codex/Claude; measured budget and any shape gaps must close before formal evaluation authorization.')
    write(HERE / 'PACKAGE_CONTRACT.json', contract)
    paths = inputs(selection_dir, seal, slice_path)
    manifest = dict(schema='EDGE_DELIVERY_BYTE_MANIFEST_V1', root_prefix='edge_preflight_checkout',
        files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size, sha256=sha(p)) for p in paths})
    write(HERE / 'PACKAGE_MANIFEST.json', manifest)
    paths += [HERE / 'PACKAGE_MANIFEST.json', HERE / 'PACKAGE_MANIFEST.json.sha256']
    needed = sum(p.stat().st_size for p in paths) + 128 * 1024**2
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < needed:
        raise ValueError('INSUFFICIENT_ARCHIVE_SPACE')
    temporary = output.with_suffix(output.suffix + '.tmp')
    with tarfile.open(temporary, 'w', format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(paths):
            tar_add(archive, path, 'edge_preflight_checkout/' + path.relative_to(ROOT).as_posix())
    temporary.replace(output)
    sidecar(output)
    # Read archive bytes directly and compare every archived member against the
    # source manifest. This checks the actual deliverable, not just source paths.
    checked = 0
    with tarfile.open(output, 'r') as archive:
        for name, item in manifest['files'].items():
            member = archive.getmember('edge_preflight_checkout/' + name)
            if member.size != item['bytes']:
                raise ValueError('ARCHIVE_SIZE:' + name)
            import hashlib
            digest = hashlib.sha256()
            with archive.extractfile(member) as stream:
                for block in iter(lambda: stream.read(4 * 1024**2), b''):
                    digest.update(block)
            if digest.hexdigest() != item['sha256']:
                raise ValueError('ARCHIVE_SHA:' + name)
            checked += 1
    receipt = dict(status='ARCHIVE_BYTES_VERIFIED_NOT_RUNTIME_PASS',
        created_utc=datetime.now(timezone.utc).isoformat(), archive_path=str(output),
        archive_bytes=output.stat().st_size, archive_sha256=sha(output),
        archived_manifest_files_verified=checked, manifest_sha256=sha(HERE / 'PACKAGE_MANIFEST.json'),
        selection_seal_sha256=expected, active_slice_sha256=sha(slice_path),
        raw_pcaps_archived=False, model_loaded=False, hpc_submitted=False,
        full_execution_ready=False)
    write(HERE / 'BUILD_RECEIPT.json', receipt)
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    main()
