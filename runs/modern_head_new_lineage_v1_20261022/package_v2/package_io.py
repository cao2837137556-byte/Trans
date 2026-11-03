"""Small, dependency-free package and output identity helpers."""
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def require(value, message):
    if not value:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def pin(path, digest):
    p = Path(path)
    require(p.is_file() and sha(p) == digest, 'IDENTITY:' + str(p))
    return p


def write(path, data, replace=False):
    path = Path(path)
    require(replace or not path.exists(), 'NO_OVERWRITE:' + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.next')
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    os.replace(tmp, path)


def verify_manifest(folder, manifest):
    folder = Path(folder).resolve()
    value = read(manifest)
    for name, digest in value['files'].items():
        path = (folder / name).resolve()
        require(path.is_relative_to(folder), 'MANIFEST_ESCAPE')
        pin(path, digest)
    return value


def package():
    manifest = verify_manifest(ROOT, ROOT / 'code_manifest.json')
    require({'config.json', 'modern_adapter.py', 'modern_service.py',
             'experiment_contract.json', 'supplementary_registration.json'} <= set(manifest['files']),
            'INCOMPLETE_PACKAGE')
    config = read(ROOT / 'config.json')
    registration = read(ROOT / 'supplementary_registration.json')
    require(registration['original_contract_sha256'] == sha(ROOT / 'experiment_contract.json'),
            'REGISTRATION_CONTRACT_DRIFT')
    require(registration['paired_families'] == ['MLP_QUERY_BCE', 'TabM', 'LightGBM'] and
            registration['policies'] == ['OLD_BANK', 'B0', 'B1', 'B2'] and
            registration['seeds'] == [27, 127, 227] and
            registration['target_calibration'] is False and
            registration['front_end_regeneration'] is False, 'REGISTRATION_SCOPE')
    return config
