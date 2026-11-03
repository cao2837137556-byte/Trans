"""Immutable recipe, identity checks and metadata for task-knowledge transfer."""
import hashlib
import json
import os
import statistics
import struct
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STEM = 'frontend_ab_start_control_'
RECIPE = ROOT / 'runs/mainline_docs' / (STEM + 'recipe_v1_20260912.json')
RECIPE_SHA = '5ce8f2e39c62c20eb8c23ee4d7462d77f038665c77da46d1be793eae9c7699ee'
DESIGN_SHA = 'a37e55fc2550bb35660d4cd28c5cb50c42930cb628c697f3ff6ec8492cb2f825'
PACKAGE = ROOT / 'runs/frontend_ab_start_control_implementation_v1_20260912'
OUTPUTS = {p: ROOT / ('runs/frontend_ab_start_control_' + p.lower() + '_v1_20260912') for p in 'TE'}
PYTHON = Path('C:/Users/28371/AppData/Local/Programs/Python/Python39/python.exe')
TOKENS = {p: 'I_AUTHORIZE_ONE_AB_START_CONTROL_V1_' + p for p in ('T','E','TE')}


class Stop(RuntimeError):
    pass


def require(value, reason):
    if not value:
        raise Stop(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(path, check=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
            check()
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.tmp')
    with tmp.open('wb') as f:
        f.write(canonical(value) + b'\n')
    os.replace(tmp, path)


def recipe():
    require(sha(RECIPE) == RECIPE_SHA, 'RECIPE_IDENTITY')
    r = read_json(RECIPE)
    require(sha(ROOT / r['design_document']) == DESIGN_SHA, 'DESIGN_IDENTITY')
    return r


def pin(item, check=lambda: None):
    p = ROOT / item['path']
    require(sha(p, check) == item['sha256'], 'INPUT_DRIFT:' + item['path'])
    return p


def manifest(folder, expected=None, check=lambda: None):
    folder = Path(folder).resolve()
    if expected:
        require(sha(folder/'SHA256SUMS', check) == expected, 'MANIFEST_IDENTITY')
    paths = {}
    for line in (folder/'SHA256SUMS').read_text(encoding='utf-8').splitlines():
        h, rel = line.split('  ', 1)
        p = (folder/rel).resolve()
        require(folder in p.parents and rel not in paths, 'MANIFEST_PATH')
        require(sha(p, check) == h, 'SEALED_FILE_DRIFT:' + rel)
        paths[rel] = h
    require(paths, 'EMPTY_MANIFEST')
    return paths


def seal(folder, check=lambda: None):
    require(not (folder/'SHA256SUMS').exists(), 'ALREADY_SEALED')
    files = sorted(p for p in folder.rglob('*') if p.is_file())
    lines = [sha(p, check)+'  '+p.relative_to(folder).as_posix()+'\n' for p in files]
    with (folder/'SHA256SUMS').open('x', encoding='utf-8', newline='\n') as f:
        f.writelines(lines)


def prefix(raw, event):
    return hashlib.sha256(b'F4_INPUT_V1\0' + struct.pack('<II', event+1, 131) + raw[:(event+1)*524]).hexdigest()


def order(keys, epoch, owner):
    return sorted(keys, key=lambda k: (hashlib.sha256(canonical(['paired-order-v1',2705,epoch,owner,k])).hexdigest(), k))


def buckets(keys, steps):
    q, r = divmod(len(keys), steps)
    offset = 0
    for i in range(steps):
        n = q + (i < r)
        yield keys[offset:offset+n]
        offset += n
    require(offset == len(keys), 'BUCKET_CONSERVATION')


def targets(contexts):
    return [t for c in contexts for t in c['targets']]


def train_metadata(plan, r):
    cs = [c for c in plan['contexts'] if c['role'] == 'train']
    ts = targets(cs)
    require(len(cs) == r['data']['train_contexts'] and len(ts) == r['data']['train_targets'], 'TRAIN_COUNTS')
    require(len({t['uid'] for t in ts}) == len(ts), 'TRAIN_UID_DUPLICATE')
    for c in cs:
        require(len({t['label'] for t in c['targets']}) == 1, 'CONTEXT_LABEL_MIX')
        require(len({t['owner'] for t in c['targets']}) == 1, 'CONTEXT_OWNER_MIX')
        require(all(t['new_role'] == 'train' and t['context_key'] == c['key'] for t in c['targets']), 'TRAIN_JOIN')
    for g in 'AB':
        group = [t for t in ts if t['owner'] == g]
        expected = r['data'][g]
        require(len(group) == expected['targets'] and sum(t['label'] for t in group) == expected['attack'], 'OWNER_COUNT')
        require(len({t['context_key'] for t in group}) == expected['contexts'], 'OWNER_CONTEXT_COUNT')
    check = [c for c in plan['contexts'] if c['role'] == 'check']
    require(not ({c['component'] for c in cs} & {c['component'] for c in check}), 'COMPONENT_LEAK')
    require(not ({t['uid'] for t in ts} & {t['uid'] for t in targets(check)}), 'UID_LEAK')
    return cs


def teacher_targets(contexts, r):
    ts = sorted([t for c in contexts if c['role'] == 'train' for t in c['targets']
                 if t['owner'] == 'A' and t['old_hard'] == t['label']], key=lambda t: t['uid'])
    f = r['teacher_cache']
    require(len(ts) == len({t['uid'] for t in ts}) == f['expected_targets'], 'TEACHER_DENOMINATOR')
    for y, name in [(0,'benign_targets'),(1,'attack_targets')]:
        group = [t for t in ts if t['label'] == y]
        require(len(group) == f[name], 'TEACHER_CLASS_COUNT')
        require(len({t['context_key'] for t in group}) == f['expected_N_T'+str(y)], 'TEACHER_CONTEXT_COUNT')
    return ts


def guard_metadata(contexts, saved, r):
    import math
    actual = {t['uid']: t for t in targets(contexts) if t['owner'] == 'A'}
    require(len(saved) == len(actual) and {t['uid'] for t in saved} == set(actual), 'A_SCORE_UIDS')
    groups = defaultdict(list)
    for t in saved:
        require(all(t[k] == v for k,v in actual[t['uid']].items()), 'A_SCORE_JOIN')
        require(math.isfinite(t['logit']) and t['hard'] == int(t['logit'] >= 0), 'A_SCORE_FINITE_HARD')
        if t['hard'] == t['label']:
            groups[t['context_key']].append(t)
    for vs in groups.values():
        vs.sort(key=lambda t: t['uid'])
    scale = max(1., statistics.median(statistics.mean(abs(t['logit']) for t in vs) for vs in groups.values()))
    f = r['losses']['A_guard']
    require(scale == f['s_A'] and len(groups) == f['eligible_contexts'], 'GUARD_SCALE_CONTEXTS')
    require(sum(map(len,groups.values())) == f['eligible_targets'], 'GUARD_TARGET_COUNT')
    return dict(groups), scale


def guard_pairs(batch, groups, epoch, scale):
    reps = []
    for c in batch:
        eligible = groups.get(c['key'], [])
        if eligible:
            start = int(hashlib.sha256(c['key'].encode('utf-8')).hexdigest(), 16) % len(eligible)
            reps.append(eligible[(start+epoch-1) % len(eligible)])
    return [(a, b, min(1., (a['logit']-b['logit'])/(2*scale)))
            for a in reps if a['label'] == 1 for b in reps if b['label'] == 0
            and a['component_id'] != b['component_id']]


# Immutable historical I/O fix: single-writer append-only progress journal.
from issue27frontend_transfer_io_v2 import read_json, atomic_json
