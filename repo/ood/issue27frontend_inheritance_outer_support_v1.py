"""Shared primitives for the fixed post-N3 outer-development comparison."""
from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from pathlib import Path

import issue27frontend_inheritance_n1_support_v1 as base

ROOT = Path(__file__).resolve().parents[2]
DOCS = 'runs/mainline_docs/'
PACKAGE = 'runs/frontend_inheritance_outer_implementation_v1_20260909'
METADATA = 'runs/frontend_inheritance_outer_metadata_v1_20260909'
REAL = 'runs/frontend_inheritance_outer_comparison_v1_20260909'
AUTH = 'I_AUTHORIZE_ONE_OUTER_INPUT_PREPARATION_AND_FIXED_N3_COMPARISON'
DESIGN = DOCS + 'frontend_inheritance_post_n3_whole_pool_comparison_design_20260908.md'
DESIGN_SHA = '9956cdbfb5c3205a4c95877b9dcb58a6e45fd9cd9a9f9f3e25675bcad0679602'
EXPECTED = {'A1C': 2000, 'A0C': 1174, 'A0W': 2, 'B0N': 1224}
B_KEYS = {'iotsim-combined-cycle': (998, 844), 'iotsim-domotic-monitor': (226, 50)}
SOURCES = {
    'iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0': (600, 462),
    'iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0': (600, 465),
    'iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0': (600, 463),
    'iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0': (600, 192),
    'normal_scanning1.pcap': (2000, 2000),
}
CLAIMS = {'broader_inheritance': 'NOT_PROVED', 'F5_eligible': False,
          'deployment': False, 'K': 'NOT_AUTHORIZED', 'new_device': 'NOT_EVALUATED',
          'causal_B_training_benefit': 'NOT_TESTED', 'evidence': 'EXPOSED_DEVELOPMENT'}
Stop, require = base.Stop, base.require
digest, sha_file, json_bytes = base.digest, base.sha_file, base.json_bytes
manifest, Writer = base.manifest, base.Writer


def read_pinned(root, name, expected, max_bytes=64 * 1024**2):
    path = root / name
    require(path.stat().st_size <= max_bytes, 'INPUT_SIZE')
    data = path.read_bytes()
    require(digest(data) == expected, 'INPUT_HASH_' + Path(name).name)
    return data


def atomic_json(path, value):
    raw = json_bytes(value)
    require(len(raw) < 65536, 'STATUS_SIZE')
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def seal(folder):
    require(not (folder / 'SHA256SUMS').exists(), 'ALREADY_SEALED')
    entries = {p.name: sha_file(p) for p in sorted(folder.iterdir()) if p.is_file()}
    with (folder / 'SHA256SUMS').open('xb') as stream:
        stream.write(''.join(h + '  ' + n + '\n' for n, h in entries.items()).encode('ascii'))
    return entries


def verify_seal(folder, expected=None):
    raw = (folder / 'SHA256SUMS').read_bytes()
    if expected is not None:
        require(digest(raw) == expected, 'SEAL_IDENTITY')
    pins = manifest(raw)
    require(set(p.name for p in folder.iterdir() if p.is_file()) == set(pins) | {'SHA256SUMS'},
            'SEALED_FILE_SET')
    for name, value in pins.items():
        require('/' not in name and sha_file(folder / name) == value, 'SEALED_MEMBER_HASH')
    return pins


def categorize(row):
    key = (row['owner'], row['label'], row['teacher_kind'])
    values = {('A', 1, 'attack_hard'): 'A1C', ('A', 0, 'benign_normal'): 'A0C',
              ('A', 0, 'benign_hard'): 'A0W', ('B', 0, 'none'): 'B0N'}
    require(key in values, 'OUTER_CATEGORY')
    return values[key]


def validate_population(contexts, real=True):
    require([c['key'] for c in contexts] == sorted({c['key'] for c in contexts}), 'CONTEXT_ORDER')
    seen, counts = set(), Counter()
    for c in contexts:
        require(c['split'] == 'internal_val' and 1 <= c['length'] <= 256 and c['targets'], 'CONTEXT_RANGE')
        events = set()
        for t in c['targets']:
            require(t['uid'] not in seen and t['event'] not in events, 'DUPLICATE_TARGET')
            seen.add(t['uid']); events.add(t['event'])
            require(type(t['event']) is int and 0 <= t['event'] < c['length'], 'TARGET_EVENT')
            require(type(t['label']) is int and t['label'] in (0, 1), 'LABEL_TYPE')
            require(t['category'] == categorize(t) and t['source_group'] == c['source'], 'TARGET_ATTACHMENT')
            counts[t['category']] += 1
        require(max(events) + 1 == c['length'], 'PREFIX_TRIM')
    if real:
        require(counts == EXPECTED and len(contexts) == 3582, 'POPULATION_COUNTS')
        sources = {name: (sum(len(c['targets']) for c in contexts if c['source'] == name),
                          sum(c['source'] == name for c in contexts)) for name in {c['source'] for c in contexts}}
        require(sources == SOURCES, 'SOURCE_COUNTS')
        b = [(c, t) for c in contexts for t in c['targets'] if t['category'] == 'B0N']
        groups = {k: (sum(t['device_family'] == k for c, t in b),
                      len({c['key'] for c, t in b if t['device_family'] == k}))
                  for k in {t['device_family'] for c, t in b}}
        require(groups == B_KEYS, 'B_GROUP_COUNTS')
    return dict(counts)


def measurements(contexts, predictions, real=True):
    validate_population(contexts, real)
    wanted = {t['uid']: (c, t) for c in contexts for t in c['targets']}
    require(set(wanted) == set(predictions), 'INCOMPLETE_PREDICTIONS')
    rows = []
    for uid in sorted(wanted):
        c, t = wanted[uid]
        q = predictions[uid]
        require(type(q) is float and math.isfinite(q), 'NONFINITE_LOGIT')
        hard, old = q >= 0, t['teacher_kind'] != 'benign_normal'
        rows.append({**t, 'context': c['key'], 'source': c['source'], 'split': c['split'],
                     'member': c['member'], 'tier': t['tier'], 'logit': q, 'hard': hard,
                     'old_hard': old, 'old_decision_origin': 'missing_hard_fallback' if t['owner'] == 'B'
                     else 'sealed_F1_teacher_category', 'old_correct': old == bool(t['label']),
                     'new_correct': hard == bool(t['label'])})

    def summary(subset):
        return {'targets': len(subset), 'contexts': len({r['context'] for r in subset}),
                'hard': sum(r['hard'] for r in subset),
                'errors': [r['uid'] for r in subset if not r['new_correct']],
                'old_correct_new_wrong': [r['uid'] for r in subset if r['old_correct'] and not r['new_correct']],
                'old_wrong_new_correct': [r['uid'] for r in subset if not r['old_correct'] and r['new_correct']]}

    categories = {k: summary([r for r in rows if r['category'] == k]) for k in EXPECTED}
    a = [r for r in rows if r['owner'] == 'A']
    flips = sum(r['old_correct'] and not r['new_correct'] for r in a)
    b = [r for r in rows if r['owner'] == 'B']

    def utility(subset):
        contexts_all = {r['context'] for r in subset}
        normal_contexts = contexts_all - {r['context'] for r in subset if r['hard']}
        return {'targets': len(subset), 'contexts': len(contexts_all),
                'normal_targets': sum(not r['hard'] for r in subset),
                'all_B_benign_normal_contexts': len(normal_contexts),
                'normal_context_members': sorted(normal_contexts)}

    groups = {k: utility([r for r in b if r['device_family'] == k]) for k in sorted({r['device_family'] for r in b})}
    total = utility(b)
    a_ok = not categories['A1C']['errors'] and not categories['A0C']['errors']
    b_status = ('POSITIVE_IN_BOTH_REPRESENTED_GROUPS' if set(groups) == set(B_KEYS)
                and all(g['all_B_benign_normal_contexts'] > 0 for g in groups.values())
                else 'PARTIAL' if total['normal_targets'] else 'ZERO')
    result = {'status': 'OUTER_COMPARISON_COMPLETE', 'complete': True, 'targets': len(rows),
              'contexts': len(contexts), 'A_retention': 'COMPLETE_ON_THIS_POOL' if a_ok else 'REGRESSION_ON_THIS_POOL',
              'B_utility': b_status, 'categories': categories, 'B_groups': groups, 'B_totals': total,
              'A_negative_flip_rate': {'numerator': flips, 'denominator': len(a)},
              'A_conditional_loss': {'numerator': flips, 'denominator': sum(r['old_correct'] for r in a)},
              'groups': {field: {key: summary([r for r in rows if r[field] == key])
                                 for key in sorted({r[field] for r in rows})}
                         for field in ('source', 'attack_family', 'tier')}, **CLAIMS}
    return result, rows
