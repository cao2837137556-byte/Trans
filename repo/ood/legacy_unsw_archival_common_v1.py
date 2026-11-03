"""Versioned archival evaluation utilities. No real input reads on import."""
import gzip
import hashlib
import json
import os
from pathlib import Path

RECIPE_SHA = '1476a79dcd13f814dcf57dfe26d195d41191205adc79dcc8db40cd8351fb9b97'
PREP = 'runs/legacy_commissioning_unsw_evaluation_preparation_v1_20260926'
ROLE = 'EXTERNAL_ARCHIVAL_EVALUATION'
SEEDS = (27, 127, 227)


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024**2), b''):
            h.update(b)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value, replace=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    require(replace or not path.exists(), 'FILE_EXISTS:' + str(path))
    temp = path.with_name(path.name + '.next')
    with temp.open('w', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(temp), str(path))


def confined(root, rel):
    root = Path(root).resolve()
    p = (root / rel).resolve()
    require(p.is_relative_to(root), 'PATH_ESCAPE')
    return p


def pin(path, expected):
    require(sha(path) == expected, 'SHA_MISMATCH:' + str(path))
    return Path(path)


def seal(folder):
    folder = Path(folder)
    with (folder / 'SHA256SUMS').open('x', encoding='utf-8', newline='\n') as f:
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p != folder / 'SHA256SUMS':
                f.write(sha(p) + '  ' + p.relative_to(folder).as_posix() + '\n')


def verify(folder, exact=True):
    folder = Path(folder)
    names = set()
    for line in (folder / 'SHA256SUMS').read_text(encoding='utf-8-sig').splitlines():
        h, rel = line.split('  ', 1)
        require(rel not in names, 'DUPLICATE_SEAL_ENTRY')
        names.add(rel)
        pin(confined(folder, rel), h)
    if exact:
        actual = {p.relative_to(folder).as_posix() for p in folder.rglob('*') if p.is_file()}
        require(actual == names | {'SHA256SUMS'}, 'SEAL_FILE_SET')
    return len(names)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def save_rows(path, records):
    with gzip.open(path, 'xt', encoding='utf-8', newline='\n') as f:
        for r in records:
            f.write(json.dumps(r, separators=(',', ':'), allow_nan=False) + '\n')


def contracts(root):
    p = Path(root) / PREP
    verify(p)
    recipe = read(pin(p / 'evaluation_recipe.json', RECIPE_SHA))
    require(recipe['role'] == ROLE, 'ARCHIVAL_ROLE')
    roster = read(p / 'device_roster.json')
    lineage = read(p / 'lineage_audit.json')
    require(len({d['mac'] for d in roster}) == len(roster) == 5, 'ROSTER')
    require(not set(d['mac'] for d in roster) & set(lineage['training_owner_rows']), 'TRAIN_OWNER_OVERLAP')
    require(not set(s['sha256'] for s in recipe['sources']) &
            set(s['sha256'] for s in lineage['learning_sources']), 'TRAIN_SOURCE_OVERLAP')
    require(all(d['role'] == ROLE and not d['used_for_optimizer'] and not d['used_for_calibration']
                for d in roster), 'FORBIDDEN_TRAIN_OR_CAL_ROLE')
    return recipe, roster, read(p / 'label_contract.json'), read(p / 'matched_control_plan.json')
