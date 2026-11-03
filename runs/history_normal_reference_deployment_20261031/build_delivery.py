"""Build a path-relocated, hash-bound delivery without copying scientific data."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PACKAGE_REL = Path('runs/history_normal_reference_v1_20261031')
PACKAGE = ROOT / PACKAGE_REL
REMOTE_ROOT = '/public/home/jiangxinwei.zr/work/paper04'
ORIGINAL_SEAL_SHA = '31ab70c41014427a49c5ce134dba269e2bbade54e911ca5e1d674ab3ad95b84e'
PLANS = {
    '20261031_well_history_normal_reference_execution_plan_r2_for_codex.md':
        'dc566523f91256de7616391634bcfc348d1434e3a4227b0f8414122984a9dbf0',
    '20261031_well_history_normal_reference_execution_plan_r2_review_response_codex.md':
        'f73c0bdd2dd6aa3a114a58ef3b4f56f9bd99e30ca53c4a7ffd1d5f3351f9b803',
}


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2) + '\n')


def scientific_semantic(value):
    if isinstance(value, dict):
        return {k: scientific_semantic(v) for k, v in value.items()
                if not (k in ('root', 'path', 'tshark', 'runtime_root', 'normalizer', 'assets_manifest')
                        and isinstance(v, str))}
    if isinstance(value, list):
        return [scientific_semantic(v) for v in value]
    return value


def relocate(value, data_root, tshark):
    if isinstance(value, dict):
        return {k: (tshark if k == 'tshark' else relocate(v, data_root, tshark))
                for k, v in value.items()}
    if isinstance(value, list):
        return [relocate(v, data_root, tshark) for v in value]
    if isinstance(value, str):
        normalized = value.replace('\\', '/')
        for local, remote in ((ROOT.as_posix(), REMOTE_ROOT),
                              (data_root.as_posix(), REMOTE_ROOT + '/data_external/unsw_iotraffic_2025')):
            if normalized == local or normalized.startswith(local + '/'):
                return remote + normalized[len(local):]
    return value


def build(tshark):
    require(tshark.startswith('/') and '..' not in PurePosixPath(tshark).parts, 'ABSOLUTE_TSHARK_REQUIRED')
    stage = HERE / 'staged_root'
    require(not stage.exists() and not (HERE / 'DELIVERY_INPUTS.json').exists(), 'DELIVERY_ALREADY_EXISTS_NO_OVERWRITE')
    original_manifest = PACKAGE / 'CODE_MANIFEST.json'
    require(sha(original_manifest) == ORIGINAL_SEAL_SHA, 'ORIGINAL_CODE_SEAL_CHANGED')
    manifest = read(original_manifest)
    sys.path.insert(0, str(PACKAGE))
    from hnr.runtime import code_identity
    require(code_identity() == manifest['code_sha256'], 'ORIGINAL_CODE_INVENTORY_CHANGED')
    original_config = read(PACKAGE / 'config/EXECUTION.json')
    data_root = Path(original_config['devices'][0]['raw']['path']).parent.parent.resolve()
    mapped_config = relocate(original_config, data_root, tshark)
    require(scientific_semantic(mapped_config) == scientific_semantic(original_config), 'SCIENTIFIC_BINDING_CHANGED')
    inputs = {}
    hashed = {}

    def add(local, relative, expected=None, size=None, category='scientific_input'):
        local, relative = Path(local).resolve(), PurePosixPath(str(relative).replace('\\', '/'))
        require(not relative.is_absolute() and '..' not in relative.parts, 'UNSAFE_REMOTE_RELATIVE_PATH')
        require(local.is_file(), 'MISSING_INPUT:' + str(local))
        checksum = hashed.setdefault(str(local), None)
        if checksum is None:
            checksum = hashed[str(local)] = sha(local)
        require(expected is None or checksum == expected, 'INPUT_SHA_CHANGED:' + str(local))
        require(size is None or local.stat().st_size == size, 'INPUT_SIZE_CHANGED:' + str(local))
        key = relative.as_posix()
        if key in inputs:
            require(inputs[key]['sha256'] == checksum, 'CONTRADICTORY_DESTINATION:' + key)
            if category not in inputs[key]['categories']:
                inputs[key]['categories'].append(category)
            return
        inputs[key] = dict(local_path=str(local), remote_relative_path=key, sha256=checksum,
                           bytes=local.stat().st_size, categories=[category],
                           install_policy='REUSE_IF_IDENTICAL_ELSE_FAIL_NO_OVERWRITE')

    def copy_file(source, relative, expected=None, category='staged_source'):
        source, destination = Path(source), stage / relative
        require(source.is_file(), 'MISSING_STAGE_SOURCE:' + str(source))
        require(expected is None or sha(source) == expected, 'STAGE_SOURCE_SHA_CHANGED:' + str(source))
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(not destination.exists(), 'STAGE_DESTINATION_EXISTS:' + str(destination))
        shutil.copyfile(source, destination)
        add(destination, relative, expected=expected, category=category)

    for key, expected in manifest['code_sha256'].items():
        if key == 'config/EXECUTION.json':
            continue
        require(not key.startswith('@encoder/'), 'UNEXPECTED_EXTERNAL_ENCODER_PATH')
        relative = Path(key[6:]) if key.startswith('@root/') else PACKAGE_REL / key
        source = ROOT / relative
        copy_file(source, relative, expected)
    config_path = stage / PACKAGE_REL / 'config/EXECUTION.json'
    write(config_path, mapped_config)
    add(config_path, PACKAGE_REL / 'config/EXECUTION.json', category='path_only_relocated_config')
    relocated_manifest = copy.deepcopy(manifest)
    relocated_manifest['code_sha256']['config/EXECUTION.json'] = sha(config_path)
    changed = [k for k in manifest['code_sha256']
               if manifest['code_sha256'][k] != relocated_manifest['code_sha256'][k]]
    require(changed == ['config/EXECUTION.json'], 'UNEXPECTED_CODE_SEAL_DIFFERENCE')
    manifest_path = stage / PACKAGE_REL / 'CODE_MANIFEST.json'
    write(manifest_path, relocated_manifest)
    add(manifest_path, PACKAGE_REL / 'CODE_MANIFEST.json', category='relocated_code_seal')

    test_pins = read(PACKAGE / 'validation/IMPLEMENTATION_RECEIPT.json')['test_sources_sha256']
    for name, expected in test_pins.items():
        copy_file(PACKAGE / 'tests' / name, PACKAGE_REL / 'tests' / name, expected, 'generated_test')
    for name in ('README.md', 'EXECUTION_CARD.md'):
        copy_file(PACKAGE / name, PACKAGE_REL / name, category='original_implementation_document')
    for name, expected in PLANS.items():
        relative = Path('runs/mainline_docs/collab') / name
        copy_file(ROOT / relative, relative, expected, 'frozen_design')

    deployment_rel = HERE.relative_to(ROOT)
    for name in ('CODE_MANIFEST.json', 'config/EXECUTION.json', 'config/ASSETS.json',
                 'config/ENCODER_RUNTIME_FILES.json', 'validation/IMPLEMENTATION_RECEIPT.json'):
        copy_file(PACKAGE / name, deployment_rel / 'provenance' / name,
                  category='unmodified_original_provenance')
    for name in ('build_delivery.py', 'install_delivery.py', 'remote_preflight.py', 'submit_once.py', 'README.md'):
        copy_file(HERE / name, deployment_rel / name, category='deployment_tool')

    runtime_root = Path(original_config['encoder']['runtime_root'])
    runtime_manifest = read(PACKAGE / 'config/ENCODER_RUNTIME_FILES.json')['files']
    actual_vendor = {p.relative_to(runtime_root).as_posix()
                     for folder in ('vendor/netFound', 'vendor/netFound-base')
                     for p in (runtime_root / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts}
    require(actual_vendor == set(runtime_manifest), 'FROZEN_VENDOR_INVENTORY_CHANGED')
    for relative, expected in runtime_manifest.items():
        path = runtime_root / relative
        add(path, path.relative_to(ROOT), expected, category='frozen_encoder_runtime')

    assets = read(PACKAGE / 'config/ASSETS.json')
    asset_files = {}
    def visit(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                path = ROOT / value['path']
                asset_files[str(path.resolve())] = value
                add(path, path.relative_to(ROOT), value['sha256'], value.get('bytes'), 'frozen_asset')
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(assets)
    require(len(asset_files) == 34, 'FROZEN_ASSET_COUNT')
    for device in original_config['devices']:
        for field in ('raw', 'packet_index', 'chronological_order'):
            spec = device[field]
            path = Path(spec['path'])
            remote_relative = Path('data_external/unsw_iotraffic_2025') / path.relative_to(data_root)
            add(path, remote_relative, spec['sha256'], spec.get('bytes'), 'historical_' + field)
    roster = original_config['known_macs_source']
    roster_path = Path(roster['path'])
    add(roster_path, roster_path.relative_to(ROOT), roster['sha256'], category='known_macs_source')

    authorization = dict(status='AUTHORIZED_SINGLE_EXECUTION', user_message='允许下一步',
        authorization_date_local='2026-10-31', timezone='Asia/Shanghai',
        authorized_actions=['HPC delivery', 'environment acceptance', 'one real C1/P-DEVONLY attempt'],
        limits=dict(cpu=4, memory_gib=16, wall_hours=8, intermediate_gib=20),
        candidate='C1', path='P-DEVONLY', automatic_retry=False, training_authorized=False,
        stop_gate='DEV gate must pass before A/B payload evaluation')
    auth_path = stage / deployment_rel / 'AUTHORIZATION.json'
    write(auth_path, authorization)
    add(auth_path, deployment_rel / 'AUTHORIZATION.json', category='execution_authorization_record')
    body = dict(schema='history-normal-reference-delivery-inputs-v1', remote_root=REMOTE_ROOT,
        created_utc=datetime.now(timezone.utc).isoformat(), stage_root=str(stage),
        original_code_manifest_sha256=ORIGINAL_SEAL_SHA,
        relocated_code_manifest_sha256=sha(manifest_path), code_manifest_changed_keys=changed,
        frozen_scientific_semantics_equal=True, existing_destination_policy='ERROR_ON_ANY_DIVERGENCE',
        file_count=len(inputs), total_unique_bytes=sum(r['bytes'] for r in inputs.values()),
        scientific_asset_file_count=34, runtime_vendor_file_count=len(runtime_manifest),
        files=[inputs[k] for k in sorted(inputs)])
    write(HERE / 'DELIVERY_INPUTS.json', body)
    receipt = dict(status='LOCAL_DELIVERY_BUILT_NOT_UPLOADED', original_package_modified=False,
        original_code_manifest_sha256=ORIGINAL_SEAL_SHA,
        relocated_code_manifest_sha256=sha(manifest_path),
        delivery_inputs_sha256=sha(HERE / 'DELIVERY_INPUTS.json'), changed_keys=changed,
        files=len(inputs), total_unique_bytes=body['total_unique_bytes'],
        data_copies_created=0, remote_operations=0, job_id=None)
    write(HERE / 'BUILD_RECEIPT.json', receipt)
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tshark', default='/usr/bin/tshark')
    build(parser.parse_args().tshark)
