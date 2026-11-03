"""Frozen commissioning contracts. Standard library only; import performs no I/O."""
import hashlib
import json
import math
import re
from pathlib import Path, PureWindowsPath

POLICY_REL = 'runs/legacy_commissioning_policy_v1_20260924/commissioning_policy.json'
POLICY_SHA = '5e8004ddeacdef3b0b506e23795bcb7867c1fd8c6c7c10524d5307b15ed84319'
CONTRACT_REL = 'runs/legacy_commissioning_policy_v1_20260924/frozen_detector_contract.json'
CONTRACT_SHA = '8575edcadd7b20a3e3f2f36044565a9e2e31cb15ecd982427bcf046e8cda4d6f'
PHASES = (
    ('startup_or_safe_reconnect', 0, 300), ('idle', 300, 900),
    ('local_primary_functions', 900, 1800), ('remote_primary_functions', 1800, 2700),
    ('normal_state_transition', 2700, 3000), ('settled_operation', 3000, 3600))
SALT = 'commissioning-reference-v1-20260924'
CONSUMED = {'borun camera', 'netatmo camera', 'ring basestation'}


class Stop(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise Stop(reason)


def fields(value, required, optional=()):
    require(isinstance(value, dict), 'EXPECTED_OBJECT')
    require(set(value) == set(required) | (set(value) & set(optional)),
            'SCHEMA_FIELDS:' + ','.join(sorted(set(value) ^ set(required))))


def text(value, name):
    require(isinstance(value, str) and bool(value.strip()) and '\x00' not in value, name)
    return value


def number(value, name):
    require(type(value) in (int, float) and math.isfinite(value), name)
    return value


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, name)
    return value


def boolean(value, name):
    require(type(value) is bool, name)
    return value


def sha_text(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None, 'SHA256_FORMAT')
    return value


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def legacy_digest(value):
    # Exact legacy_reference_sample_prepare_v1.digest: insertion order is intentional.
    return hashlib.sha256(json.dumps(value, separators=(',', ':'), ensure_ascii=True,
                                    allow_nan=False).encode()).hexdigest()


def confined(root, name):
    require(isinstance(name, str) and bool(name), 'PATH_EMPTY')
    win = PureWindowsPath(name)
    require(not win.drive and not win.root and not Path(name).is_absolute(), 'PATH_ABSOLUTE')
    rel = name.replace('\\', '/')
    require('..' not in rel.split('/') and ':' not in rel, 'PATH_ESCAPE')
    root = Path(root).resolve()
    path = (root / rel).resolve()
    require(path != root and root in path.parents, 'PATH_ESCAPE')
    return path


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def parse_json(raw):
    def invalid(value):
        raise Stop('NONFINITE_JSON:' + value)
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=invalid)


def pinned_json(path, expected):
    raw = Path(path).read_bytes()
    require(hashlib.sha256(raw).hexdigest() == sha_text(expected), 'FILE_IDENTITY')
    return parse_json(raw.decode('utf-8-sig'))


def load_contracts(root):
    return (pinned_json(confined(root, POLICY_REL), POLICY_SHA),
            pinned_json(confined(root, CONTRACT_REL), CONTRACT_SHA))


def write_new(path, value):
    # Python 3.9 compatible: Path.write_text(newline=...) is intentionally avoided.
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
