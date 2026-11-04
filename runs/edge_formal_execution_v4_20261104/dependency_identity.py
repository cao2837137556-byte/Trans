"""Full verified base envelope plus exact local Python inventories; no imports.

The base manifest is the already byte-verified 863-file Linux delivery, including
the frozen vendor/model tree. All its members enter the execution AND snapshot
binding conservatively. A new envelope never silently adopts old v1 spools.
"""
import json
from pathlib import Path

from checkpoint import require, sha

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BASE = 'runs/edge_linux_preflight_package_v1_20261103/PACKAGE_MANIFEST.json'
BASE_SHA = 'f61af6ca64c629565e6914ef520c85352b65a5987e7af6d9515d1848cc4ccbd6'
INVENTORIES = ('repo/ood', 'runs/history_normal_reference_keyrepair_v1_20261031/hnr',
               HERE.relative_to(ROOT).as_posix())


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def path_in(root, relative):
    root = Path(root).resolve()
    value = Path(relative)
    require(not value.is_absolute() and '..' not in value.parts, 'DEPENDENCY_RELATIVE_PATH')
    raw = root/value
    require(not raw.is_symlink() and raw.resolve().is_relative_to(root), 'DEPENDENCY_PATH_SCOPE')
    return raw


def python_inventory(root, relative):
    folder = path_in(root, relative)
    require(folder.is_dir(), 'DEPENDENCY_SOURCE_DIRECTORY:'+relative)
    paths = sorted(p for p in folder.rglob('*.py') if '__pycache__' not in p.parts)
    require(paths and all(not p.is_symlink() for p in paths), 'DEPENDENCY_SOURCE_INVENTORY')
    return {p.relative_to(Path(root).resolve()).as_posix(): sha(p) for p in paths}


def build(root=ROOT):
    root = Path(root).resolve()
    manifest = path_in(root, BASE)
    require(sha(manifest) == BASE_SHA, 'ORIGINAL_BASE_MANIFEST_IDENTITY')
    files = read(manifest)['files']
    pins = {BASE: BASE_SHA}
    for relative, spec in files.items():
        p = path_in(root, relative)
        require(p.is_file() and p.stat().st_size == spec['bytes'] and sha(p) == spec['sha256'],
                'BASE_MEMBER_IDENTITY:'+relative)
        pins[relative] = spec['sha256']
    inventories = {}
    for folder in INVENTORIES:
        inventory = python_inventory(root, folder)
        for relative, digest in inventory.items():
            require(relative not in pins or pins[relative] == digest, 'BASE_SOURCE_CHANGED:'+relative)
        pins.update(inventory)
        inventories[folder] = inventory
    return dict(schema='EDGE_FULL_DEPENDENCY_ENVELOPE_V2',
                base_manifest=dict(path=BASE, sha256=BASE_SHA), source_inventories=inventories), pins


def verify(card, root=ROOT):
    root = Path(root).resolve()
    envelope = card.get('dependency_envelope', {})
    require(envelope.get('schema') == 'EDGE_FULL_DEPENDENCY_ENVELOPE_V2', 'DEPENDENCY_ENVELOPE_REQUIRED')
    spec = envelope['base_manifest']
    require(spec['path'] == BASE, 'BASE_MANIFEST_PATH')
    manifest = path_in(root, spec['path'])
    require(sha(manifest) == spec['sha256'], 'BASE_MANIFEST_SHA')
    required = {spec['path']: spec['sha256']}
    for relative, pin in read(manifest)['files'].items():
        p = path_in(root, relative)
        require(p.is_file() and p.stat().st_size == pin['bytes'], 'BASE_MEMBER_SIZE:'+relative)
        required[relative] = pin['sha256']
    inventories = envelope['source_inventories']
    require(set(inventories) == set(INVENTORIES), 'DEPENDENCY_INVENTORY_ROOTS')
    for relative, expected in inventories.items():
        require(python_inventory(root, relative) == expected, 'DEPENDENCY_SOURCE_TREE_CHANGED:'+relative)
        for name, digest in expected.items():
            require(name not in required or required[name] == digest, 'DEPENDENCY_CONFLICT:'+name)
        required.update(expected)
    for name, digest in required.items():
        # Exact same envelope is bound into both execution and complete-role reuse.
        require(card.get('artifact_pins', {}).get(name) == digest and
                card.get('scientific_input_artifact_pins', {}).get(name) == digest,
                'DEPENDENCY_NOT_BOUND:'+name)
    for field in ('artifact_pins', 'scientific_input_artifact_pins'):
        pins = card.get(field)
        require(type(pins) is dict and pins, 'DEPENDENCY_PINS_REQUIRED')
        for name, digest in pins.items():
            p = path_in(root, name)
            require(p.is_file() and sha(p) == digest, 'DEPENDENCY_FILE_CHANGED:'+name)
    return dict(status='PASS_FULL_BASE_AND_SOURCE_INVENTORIES', members=len(required))
