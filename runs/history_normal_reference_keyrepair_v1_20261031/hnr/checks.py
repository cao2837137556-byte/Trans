"""Read-only execution acceptance: no decoder, encoder, logits or support calls."""
from pathlib import Path

import numpy as np

from .common import PACKAGE, ROOT, TARGETS, VERSION, read, require, sha
from .history import role_binding
from .runtime import code_identity

PLAN_DOCUMENTS = {
    'runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_for_codex.md':
        'dc566523f91256de7616391634bcfc348d1434e3a4227b0f8414122984a9dbf0',
    'runs/mainline_docs/collab/20261031_well_history_normal_reference_execution_plan_r2_review_response_codex.md':
        'f73c0bdd2dd6aa3a114a58ef3b4f56f9bd99e30ca53c4a7ffd1d5f3351f9b803',
}
INDEX_FIELDS = {'timestamp_us': ('i', 8), 'block_offset': ('u', 8),
                'original_packet_ordinal': ('u', 4), 'captured_bytes': ('u', 4),
                'wire_bytes': ('u', 4), 'interface_id': ('u', 4)}
NORMALIZER_SHA = 'ba92b5439255435e854ee14b74738cae0e3606060456de37927b2b6a0e2ab8b2'


def _hex(value):
    return isinstance(value, str) and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def verify_package(root=ROOT):
    """Verify the implementation seal and the two authoritative design documents."""
    root = Path(root).resolve()
    pins = {}
    for relative, expected in PLAN_DOCUMENTS.items():
        path = root / relative
        require(path.is_file() and sha(path) == expected, 'FROZEN_DESIGN_CHANGED:' + relative)
        pins[relative] = expected
    manifest_path = PACKAGE / 'CODE_MANIFEST.json'
    require(manifest_path.is_file(), 'IMPLEMENTATION_CODE_SEAL_MISSING')
    manifest = read(manifest_path)
    require(manifest.get('code_sha256') == code_identity(), 'IMPLEMENTATION_CODE_CHANGED')
    return dict(status='SEALED', code_manifest_sha256=sha(manifest_path), design_pins=pins)


def _path(value, root):
    require(isinstance(value, str) and bool(value.strip()), 'INPUT_PATH_REQUIRED')
    return (root / value).resolve()


def _file(spec, root, name, blockers, *, verify_hash=True):
    require(isinstance(spec, dict) and _hex(spec.get('sha256')), 'INPUT_PIN_REQUIRED:' + name)
    path = _path(spec.get('path'), root)
    record = dict(path=str(path), expected_sha256=spec['sha256'], exists=path.is_file(),
                  hash_verified=False)
    if not path.is_file():
        blockers.append(dict(code='MISSING_INPUT', name=name, path=str(path)))
        return None, record
    record['bytes'] = path.stat().st_size
    if 'bytes' in spec:
        require(type(spec['bytes']) is int and spec['bytes'] > 0, 'INPUT_EXPECTED_SIZE:' + name)
        require(record['bytes'] == spec['bytes'], 'INPUT_SIZE:' + name)
    if verify_hash:
        require(sha(path) == spec['sha256'], 'INPUT_SHA256:' + name)
        record['hash_verified'] = True
    return path, record


def _runtime_inventory(config, root, blockers):
    encoder = config.get('encoder', {})
    require(encoder.get('normalizer_sha256') == NORMALIZER_SHA, 'FROZEN_NORMALIZER_PIN')
    value = encoder.get('runtime_root')
    expected = encoder.get('runtime_manifest_sha256')
    if not isinstance(value, str) or not value.strip():
        blockers.append(dict(code='ENCODER_RUNTIME_PATH_UNRESOLVED', name='encoder.runtime_root'))
        return dict(status='PENDING')
    runtime_root = _path(value, root)
    external_manifest = encoder.get('runtime_files_manifest')
    manifest_path = (_path(external_manifest.get('path'), root) if isinstance(external_manifest, dict)
                     else runtime_root / 'SHA256SUMS')
    result = dict(root=str(runtime_root), manifest=str(manifest_path), payload_hashes_verified=False,
                  model_loaded=False)
    if not runtime_root.is_dir():
        blockers.append(dict(code='ENCODER_RUNTIME_MISSING', path=str(runtime_root)))
        return dict(result, status='PENDING')
    if not manifest_path.is_file():
        blockers.append(dict(code='ENCODER_RUNTIME_MANIFEST_MISSING', path=str(manifest_path)))
        return dict(result, status='PENDING')
    if external_manifest is not None:
        require(isinstance(external_manifest, dict) and _hex(external_manifest.get('sha256')),
                'ENCODER_RUNTIME_FILES_MANIFEST_PIN')
        expected = external_manifest['sha256']
    if not _hex(expected):
        blockers.append(dict(code='ENCODER_RUNTIME_MANIFEST_PIN_UNRESOLVED', path=str(manifest_path)))
        return dict(result, status='PENDING')
    require(sha(manifest_path) == expected, 'ENCODER_RUNTIME_MANIFEST_SHA256')
    listed = {}
    if external_manifest is not None:
        manifest_body = read(manifest_path)
        require(isinstance(manifest_body.get('files'), dict) and manifest_body['files'],
                'RUNTIME_FILES_MANIFEST_SCHEMA')
        entries = [(checksum, relative) for relative, checksum in manifest_body['files'].items()]
    else:
        entries = []
        for line in manifest_path.read_text(encoding='utf-8').splitlines():
            require('  ' in line, 'RUNTIME_MANIFEST_LINE')
            entries.append(tuple(line.split('  ', 1)))
    for checksum, relative in entries:
        require(_hex(checksum) and relative and relative not in listed, 'RUNTIME_MANIFEST_ENTRY')
        candidate = (runtime_root / relative).resolve()
        require(candidate.is_relative_to(runtime_root), 'RUNTIME_MANIFEST_ESCAPE')
        listed[relative] = checksum
        if not candidate.is_file():
            blockers.append(dict(code='ENCODER_RUNTIME_FILE_MISSING', path=str(candidate)))
    actual = {p.relative_to(runtime_root).as_posix()
              for folder in ('vendor/netFound', 'vendor/netFound-base')
              for p in (runtime_root / folder).rglob('*')
              if p.is_file() and '__pycache__' not in p.parts}
    require(actual and actual <= set(listed), 'RUNTIME_VENDOR_TREE_NOT_PINNED')
    require(any(p.startswith('vendor/netFound-base/') and p.endswith(('.safetensors', '.bin'))
                for p in actual), 'FROZEN_ENCODER_WEIGHTS_REQUIRED')
    normalizer_spec = dict(path=encoder.get('normalizer'), sha256=encoder.get('normalizer_sha256'))
    _, normalizer_record = _file(normalizer_spec, root, 'encoder.normalizer', blockers)
    return dict(result, status='INVENTORIED', manifest_sha256=expected,
                manifest_format='JSON_FILES' if external_manifest is not None else 'SHA256SUMS',
                listed_files=len(listed), vendor_files=len(actual), normalizer=normalizer_record,
                note='Vendor payload hashes are checked by the execution encoder before model loading.')


def _asset_inventory(config, root, blockers):
    value = config.get('assets_manifest', str(PACKAGE / 'config/ASSETS.json'))
    if isinstance(value, dict):
        path, manifest_record = _file(value, root, 'assets_manifest', blockers)
    else:
        path = _path(value, root)
        manifest_record = dict(path=str(path), exists=path.is_file())
    if path is None or not path.is_file():
        if path is not None:
            blockers.append(dict(code='ASSETS_MANIFEST_MISSING', path=str(path)))
        return dict(manifest=manifest_record, files=[])
    manifest = read(path)
    require(manifest.get('schema') == 'history-normal-reference-assets-v1', 'ASSET_SCHEMA')
    specs = []
    def visit(value):
        if isinstance(value, dict):
            if 'path' in value and 'sha256' in value:
                specs.append(value)
            else:
                for child in value.values():
                    visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(manifest)
    records = {}
    for spec in specs:
        # Do not load or hash the large A/B arrays during this acceptance stage.
        # Their strong UID/payload validation remains inside the post-DEV loader.
        file_path, record = _file(spec, root, 'asset:' + spec['path'], blockers,
                                  verify_hash=False)
        key = record['path']
        require(key not in records or records[key]['expected_sha256'] == record['expected_sha256'],
                'ASSET_CONTRADICTORY_PIN')
        records[key] = record
    return dict(manifest=manifest_record, files=list(records.values()),
                payloads_loaded=False, payload_hashes_verified=False,
                note='A/B payload hashes and UID joins are checked only after DEV passes.')


def preflight(config, *, verify_raw_hash=False):
    """Accept already prepared indexes and paths without activating data roles.

    The optional raw SHA pass reads bytes for integrity only. It never decodes
    packets. Role boundaries below are pure validation of the existing time
    indexes; no reference/query files, snapshots or scientific values are made.
    Invalid/tampered pins raise; absent runtime assets are returned as blockers.
    """
    require(isinstance(config, dict), 'EXECUTION_CONFIG')
    root = _path(str(config.get('root', ROOT)), ROOT)
    seal = verify_package(root)
    blockers = []
    devices = config.get('devices')
    require(isinstance(devices, list) and len(devices) == len(TARGETS), 'TARGET_DEVICE_COUNT')
    expected_owners = {r['owner']: r for r in TARGETS.values()}
    require({r.get('owner') for r in devices} == set(expected_owners), 'TARGET_DEVICE_REGISTRY')
    captures = set()
    accepted = []
    for spec in devices:
        target = expected_owners[spec['owner']]
        require(all(spec.get(k) == target[k] for k in
                    ('partition', 'device', 'reference_end_us', 'bank_end_frame',
                     'first_dev_time_us', 'packets')), 'FROZEN_DEVICE_BINDING')
        capture = spec.get('capture_id')
        require(isinstance(capture, str) and capture and capture == capture.strip(), 'CAPTURE_ID_STRING')
        require(capture not in captures, 'CAPTURE_ID_DUPLICATE')
        captures.add(capture)
        require(isinstance(spec.get('known_macs'), list) and spec['owner'] in spec['known_macs'],
                'HISTORY_KNOWN_MAC_REGISTRY')
        require(isinstance(spec.get('normality_evidence'), str) and spec['normality_evidence'],
                'NORMALITY_EVIDENCE_REQUIRED')
        files = {}
        paths = {}
        for name in ('raw', 'packet_index', 'chronological_order'):
            paths[name], files[name] = _file(spec.get(name), root, target['device'] + ':' + name,
                                            blockers, verify_hash=name != 'raw' or verify_raw_hash)
        boundary = None
        if paths['packet_index'] is not None and paths['chronological_order'] is not None:
            index = np.load(paths['packet_index'], mmap_mode='r', allow_pickle=False)
            order = np.load(paths['chronological_order'], mmap_mode='r', allow_pickle=False)
            require(set(index.dtype.names or ()) == set(INDEX_FIELDS), 'PACKET_INDEX_SCHEMA')
            for name, expected in INDEX_FIELDS.items():
                dtype = index.dtype.fields[name][0]
                require((dtype.kind, dtype.itemsize) == expected, 'PACKET_INDEX_DTYPE:' + name)
            boundary = role_binding(index, order, target)
            if paths['raw'] is not None:
                require(np.all(index['block_offset'] < files['raw']['bytes']), 'INDEX_RAW_OFFSET_RANGE')
            require(np.all(index['captured_bytes'] <= index['wire_bytes']) and
                    np.all(index['interface_id'] == 0), 'INDEX_INTERFACE_LENGTH')
        accepted.append(dict(device=target['device'], owner=target['owner'], capture_id=capture,
                             files=files, role_boundary_validation=boundary))
    tshark = config.get('tshark')
    if not isinstance(tshark, str) or not tshark.strip():
        blockers.append(dict(code='TSHARK_PATH_UNRESOLVED', name='tshark'))
        decoder = dict(exists=False)
    else:
        path = _path(tshark, root)
        decoder = dict(path=str(path), exists=path.is_file(), executed=False)
        if not path.is_file():
            blockers.append(dict(code='TSHARK_EXECUTABLE_MISSING', path=str(path)))
    runtime = _runtime_inventory(config, root, blockers)
    assets = _asset_inventory(config, root, blockers)
    return dict(version=VERSION,
                status='IMPLEMENTED_RUNTIME_ASSETS_PENDING' if blockers else 'READY',
                code_seal=seal, devices=accepted, encoder=runtime, decoder=decoder,
                assets=assets, blockers=blockers, raw_hashes_verified=bool(verify_raw_hash),
                role_files_created=False, packet_decodes=0, snapshots_created=0,
                model_forwards=0, new_scores=0, distances=0, references_added=0,
                execution_authorized=False)
