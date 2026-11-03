"""B route metadata and frozen component split. No model or feature APIs."""
from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import json
import math
import os
import sys
import types
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

import issue27frontend_f0_zero_training_semantics_v1 as engine

ROOT = Path(__file__).resolve().parents[2]
FREEZE = 'runs/frontend_paired_learning_freeze_v1_20260909'
FREEZE_SHA = '534bcbbb251cc93d70df4809054d5f1c24715b3dccc19eb7cff03503561dc5f0'
PACKAGE = 'runs/frontend_paired_metadata_implementation_v1_20260909'
REAL = 'runs/frontend_paired_metadata_v1_20260909'
AUTH = 'I_AUTHORIZE_ONE_B_ROUTE_METADATA_PASS_AND_MEMBERSHIP_SEAL'
CAPS = {'wall_seconds': 3600, 'memory_bytes': 8 * 1024**3, 'output_bytes': 64 * 1024**2,
        'reserve_bytes': 1024**2, 'packets': 8207642, 'targets': 6737, 'members': 22}
LEGACY = {
    'issue27frontend_f0_zero_training_semantics_real_v1.py': 'ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60',
    'issue27ckbu_unified_tshark_causal_frontend_v1.py': '127efd212932d9330af790f17a069a84b3ee48205d68bed7e2e9f00778bb2820',
    'issue27ckda_d1_e3_embed_local_twopass_v1.py': '9f11d03b31e640de28f11fd7570b1495c7b9452b124b8b99b248689031b24ca2',
    'issue27frontend_f3_conflict_field_sufficiency_v1.py': '80b4de6c931b77f528bafaf64a4a0e449295c8a78fb1d9776a8fed1d35eb9791',
    'issue27frontend_inheritance_outer_runner_v1.py': 'e40dab584f2c564b1ec39aae3befc947b0bf89d19037e4ed195b96930ba20c56',
}


class Stop(RuntimeError):
    pass


def require(ok, reason):
    if not ok:
        raise Stop(reason)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def sha_file(path, check=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024**2), b''):
            check(); h.update(chunk)
    return h.hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def atomic_json(path, value):
    raw = canonical(value) + b'\n'
    require(len(raw) < 64 * 1024**2, 'JSON_OUTPUT_SIZE')
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('wb') as f:
        f.write(raw); f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def write_csv(path, rows):
    require(bool(rows), 'EMPTY_OUTPUT_TABLE')
    temp = path.with_suffix(path.suffix + '.tmp')
    with temp.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def read_csv(path):
    opener = gzip.open if Path(path).suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def verify_manifest(folder, expected=None, allow_doc_links=False):
    raw = (folder / 'SHA256SUMS').read_bytes()
    require(expected is None or digest(raw) == expected, 'MANIFEST_IDENTITY')
    names = set()
    for line in raw.decode('utf-8').splitlines():
        h, name = line.split('  ', 1)
        require(name not in names and len(h) == 64, 'MANIFEST_DUPLICATE_OR_HASH')
        names.add(name)
        local = '/' not in name and '\\' not in name and name not in ('.', '..', 'SHA256SUMS')
        doc = allow_doc_links and name.startswith('../mainline_docs/') and '/' not in name[len('../mainline_docs/'):]
        require(local or doc, 'MANIFEST_PATH')
        require(sha_file(folder / name) == h, 'SEALED_MEMBER_DRIFT_' + Path(name).name)
    local_names = {n for n in names if '/' not in n}
    require({p.name for p in folder.iterdir() if p.is_file()} == local_names | {'SHA256SUMS'}, 'SEALED_FILE_SET')
    return names


def seal(folder):
    with (folder / 'SHA256SUMS').open('xb') as f:
        f.write(''.join(sha_file(p) + '  ' + p.name + '\n' for p in sorted(folder.iterdir())
                       if p.is_file() and p.name != 'SHA256SUMS').encode('utf-8'))
    verify_manifest(folder)


def project_legacy(filename, functions, constants=(), extra=None):
    """Compile only pinned pure declarations, never import a historical runner."""
    path = ROOT / 'repo/ood' / filename
    require(sha_file(path) == LEGACY[filename], 'LEGACY_SOURCE_DRIFT')
    tree = ast.parse(path.read_text(encoding='utf-8-sig'))
    selected, seen = [], set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in functions:
            selected.append(node); seen.add(node.name)
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            if node.targets[0].id in constants:
                selected.append(node); seen.add(node.targets[0].id)
    require(seen == set(functions) | set(constants), 'LEGACY_PROJECTION_SET')
    mod = types.ModuleType('_paired_projection_' + Path(filename).stem)
    mod.__dict__.update({'math': math, 'dataclass': dataclass, 'Path': Path, 'Stop': Stop,
                         'ZT2Failure': Stop, 'F3Failure': Stop, **(extra or {})})
    sys.modules[mod.__name__] = mod
    future = ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0)
    unit = ast.fix_missing_locations(ast.Module(body=[future] + selected, type_ignores=[]))
    exec(compile(unit, str(path), 'exec'), mod.__dict__)
    return mod


def parsers():
    zt = project_legacy('issue27frontend_f0_zero_training_semantics_real_v1.py',
                        {'parse_int', 'parse_float', 'raw_to_event'}, {'TSHARK_FIELDS'})
    old = project_legacy('issue27ckbu_unified_tshark_causal_frontend_v1.py',
                         {'as_int', 'as_float', 'as_bool', 'normalize_port', 'PacketEvent', 'event_from_tshark'})
    sess = project_legacy('issue27ckda_d1_e3_embed_local_twopass_v1.py', {'canonical_session'})
    return zt, old, sess


class StableEndpointValues:
    """Injective raw endpoint equality instead of first-seen integers; hashes only persist."""
    def token(self, endpoint):
        return str(endpoint)


def descriptor(raw, target, parser_set):
    # target is a projected, label-free mapping. No owner/label/score lookup here.
    zt, old, sess = parser_set
    event = zt.raw_to_event(engine, raw, target['source_group'], target['member'], target['position'], target['uid'])
    require(not engine._event_missing_reason(event), 'TARGET_SEMANTIC_MISSING')
    require(event.timestamp == float(target['timestamp_epoch']), 'TARGET_TIMESTAMP_IDENTITY')
    route = engine.classify_route(event, StableEndpointValues())
    require(route.tier == target['tier'], 'TARGET_TIER_IDENTITY')
    scope = (target['source_group'], target['member'])
    old_key = sess.canonical_session(old.event_from_tshark(raw))
    legacy_hash = '' if old_key is None else digest(repr(scope + (old_key,)).encode('utf-8'))
    # A metadata are all H1. This additional conservative edge can connect an
    # F0 H1 IPv6 route even when CKBU omitted ipv6.nxt and called the B target missing.
    f0_hash = ''
    if route.tier == 'H1':
        pair = tuple(sorted(((str(event.src_endpoint), int(event.src_port)),
                             (str(event.dst_endpoint), int(event.dst_port)))))
        key = (int(event.ip_protocol),) + pair
        f0_hash = digest(repr(scope + (key,)).encode('utf-8'))
    return {'uid': target['uid'], 'source_group': scope[0], 'member': scope[1],
            'position': target['position'], 'tier': route.tier,
            'timestamp_epoch': target['timestamp_epoch'],
            'base_route_sha256': digest(canonical(['paired-b-route-v1', *scope, route.tier, route.base_key])),
            'canonical_old_session_sha256': legacy_hash, 'f0_h1_compatibility_session_sha256': f0_hash}


def load_inputs(root=ROOT):
    folder = root / FREEZE
    verify_manifest(folder, FREEZE_SHA, True)
    pins = read_json(folder / 'frozen_dependency_pins.json')
    for rel, h in pins['verified_source_pins'].items():
        require(sha_file(root / rel) == h, 'FROZEN_SOURCE_DRIFT')
    targets = read_csv(folder / 'lawful_target_metadata.csv.gz')
    members = read_csv(folder / 'proposed_B_route_metadata_members.csv')
    for t in targets:
        for k in ('label', 'position', 'event_index', 'context_events'):
            t[k] = int(t[k])
        require(t['owner'] in ('A', 'B') and t['label'] in (0, 1), 'TARGET_CATEGORY')
        require(t['new_split_role'] == 'UNASSIGNED_PENDING_DEPENDENCY_QUALIFICATION', 'HISTORICAL_ROLE_DRIFT')
        require(t['owner'] != 'A' or (t['tier'] == 'H1' and t['session_kind'] == 'GENUINE_CANONICAL_OLD_SESSION'), 'A_BRIDGE_PREREQUISITE')
    for m in members:
        for k in ('container_bytes', 'selected_B_targets', 'maximum_B_position_inclusive', 'single_pass_prefix_packets'):
            m[k] = int(m[k])
        require(m['status'] == 'PROPOSAL_ONLY_NOT_AUTHORIZED_OR_EXECUTED', 'MEMBER_SCOPE')
    require(len(targets) == len({t['uid'] for t in targets}) == 18266, 'LEGAL_DENOMINATOR')
    require(len({t['context_key'] for t in targets}) == 12889, 'CONTEXT_DENOMINATOR')
    require(Counter(t['owner'] + str(t['label']) for t in targets) == {'A0': 7347, 'A1': 4182, 'B0': 6666, 'B1': 71}, 'OWNER_DENOMINATOR')
    require(len(members) == 22 and len({(m['source_group'], m['member']) for m in members}) == 22, 'MEMBER_DENOMINATOR')
    require(sum(m['single_pass_prefix_packets'] for m in members) == CAPS['packets'], 'PACKET_CEILING')
    for m in members:
        group = [t for t in targets if t['owner'] == 'B' and (t['source_group'], t['member']) == (m['source_group'], m['member'])]
        require(len(group) == m['selected_B_targets'] and max(t['position'] for t in group) == m['maximum_B_position_inclusive'], 'MEMBER_TARGETS')
        require(m['single_pass_prefix_packets'] == m['maximum_B_position_inclusive'] + 1, 'MEMBER_CUTOFF')
    return targets, members


class Components:
    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, k):
        require(k in self.parent, 'UNKNOWN_CONTEXT_EDGE')
        while k != self.parent[k]:
            self.parent[k] = self.parent[self.parent[k]]; k = self.parent[k]
        return k

    def union(self, a, b):
        a, b = self.find(a), self.find(b)
        if a != b:
            lo, hi = sorted((a, b)); self.parent[hi] = lo


def build_membership(targets, descriptors):
    require(len(targets) == len({t['uid'] for t in targets}), 'DUPLICATE_TARGET')
    wanted = {t['uid']: t for t in targets if t['owner'] == 'B'}
    require(len(descriptors) == len({d['uid'] for d in descriptors}) and {d['uid'] for d in descriptors} == set(wanted), 'DESCRIPTOR_UID_SET')
    by_uid = {d['uid']: d for d in descriptors}
    context_rows = defaultdict(list)
    for t in targets:
        require(t['owner'] in ('A', 'B') and t['label'] in (0, 1), 'TARGET_CATEGORY')
        require(0 <= t['event_index'] < t['context_events'] <= 256, 'TARGET_PREFIX')
        context_rows[t['context_key']].append(t)
    uf = Components(context_rows)
    identities, edges, context_routes = {}, [], {}
    for t in sorted(targets, key=lambda x: x['uid']):
        scope, key = (t['source_group'], t['member']), t['context_key']
        links = []
        if t['owner'] == 'A':
            require(t['tier'] == 'H1' and t['session_kind'] == 'GENUINE_CANONICAL_OLD_SESSION', 'A_SESSION_QUALIFICATION')
            links.append(('old_session', *scope, t['old_session_id']))
        else:
            d = by_uid[t['uid']]
            require(all(d[k] == t[k] for k in ('uid', 'source_group', 'member', 'position', 'tier', 'timestamp_epoch')), 'DESCRIPTOR_ATTACHMENT')
            route = d['base_route_sha256']
            require(len(route) == 64 and all(c in '0123456789abcdef' for c in route), 'ROUTE_HASH')
            require(key not in context_routes or context_routes[key] == route, 'CONTEXT_ROUTE_CONFLICT')
            context_routes[key] = route
            links.append(('B_route', *scope, route))
            for field in ('canonical_old_session_sha256', 'f0_h1_compatibility_session_sha256'):
                h = d[field]
                require(not h or (len(h) == 64 and all(c in '0123456789abcdef' for c in h)), 'SESSION_HASH')
                if h:
                    links.append(('old_session', *scope, h))
            if 'TIMESTAMP_REGRESSION' in t['session_kind']:
                require(bool(d['canonical_old_session_sha256']), 'TIMESTAMP_REGRESSION_BRIDGE_MISSING')
        for link in links:
            if link in identities:
                prev = identities[link]; uf.union(prev, key)
                if prev != key:
                    edges.append({'left': prev, 'right': key, 'kind': link[0], 'identity_sha256': digest(canonical(link))})
            else:
                identities[link] = key
    groups = defaultdict(list)
    for key in sorted(context_rows):
        groups[uf.find(key)].append(key)
    components, strata = {}, defaultdict(list)
    for keys in groups.values():
        cid = digest(canonical(keys))
        rows = [t for key in keys for t in context_rows[key]]
        strata_key = tuple(sorted({(t['source_group'], t['owner'], t['label'], t['attack_family'], t['device_family']) for t in rows}))
        components[cid] = {'component_id': cid, 'context_keys': keys, 'stratum': [list(v) for v in strata_key]}
        strata[strata_key].append(cid)
    assignments = {}
    for stratum, ids in strata.items():
        ordered = sorted(ids, key=lambda cid: (digest(canonical(['paired-split-v1', 2705, cid])), cid))
        checks = max(1, len(ids) // 5) if len(ids) >= 2 else 0
        for i, cid in enumerate(ordered):
            c = components[cid]
            c.update(role='check' if i < checks else 'train', singleton_stratum=len(ids) == 1)
            for key in c['context_keys']:
                assignments[key] = (cid, c['role'], c['singleton_stratum'])
    require(all(assignments[e['left']][1] == assignments[e['right']][1] for e in edges), 'CROSS_ROLE_DEPENDENCY')
    membership = []
    for t in sorted(targets, key=lambda x: x['uid']):
        cid, role, singleton = assignments[t['context_key']]
        membership.append({k: t[k] for k in ('uid', 'context_key', 'source_group', 'member', 'owner', 'label',
                           'attack_family', 'device_family', 'event_index', 'context_events', 'position', 'timestamp_epoch', 'history')} |
                          {'component_id': cid, 'new_role': role, 'singleton_stratum': singleton})
    coverage, gaps = coverage_table(membership)
    scheduling = schedule_receipt(membership)
    counts = Counter(r['new_role'] for r in membership)
    summary = {'status': 'MEMBERSHIP_QUALIFIED' if not gaps else 'METADATA_COMPLETE_COVERAGE_INSUFFICIENT',
               'targets': len(targets), 'contexts': len(context_rows), 'components': len(components),
               'train_targets': counts['train'], 'check_targets': counts['check'], 'coverage_gaps': gaps,
               'cross_role_dependency_edges': 0, 'dependency_edges': len(edges),
               'scientific_capability': 'NOT_TESTED', 'training_authorized': False,
               'untouched_confirmation': False, 'physical_device_independence': 'NOT_PROVED',
               'B_prefix_byte_exposure': 'A supervision control; non-target B byte exposure is not certified absent'}
    return {'membership': membership, 'components': [components[c] for c in sorted(components)],
            'dependency_edges': edges, 'coverage': coverage, 'schedule': scheduling, 'summary': summary}


def coverage_table(rows):
    table = []
    buckets = defaultdict(list)
    for r in rows:
        buckets[(r['source_group'], r['owner'], r['label'], r['attack_family'], r['device_family'])].append(r)
    for key, values in sorted(buckets.items()):
        item = dict(zip(('source_group', 'owner', 'label', 'attack_family', 'device_family'), key))
        for role in ('train', 'check'):
            part = [r for r in values if r['new_role'] == role]
            item[role + '_targets'] = len(part)
            item[role + '_contexts'] = len({r['context_key'] for r in part})
            item[role + '_components'] = len({r['component_id'] for r in part})
            item[role + '_time_min'] = min((float(r['timestamp_epoch']) for r in part), default=None)
            item[role + '_time_max'] = max((float(r['timestamp_epoch']) for r in part), default=None)
        both = bool(item['train_targets'] and item['check_targets'])
        item['same_behavior_check'] = 'PRESENT_EXPOSED_DEVELOPMENT' if both else 'NOT_ESTABLISHED'
        item['target_time_intervals_overlap'] = (max(item['train_time_min'], item['check_time_min']) <=
                                                min(item['train_time_max'], item['check_time_max'])) if both else None
        table.append(item)
    gaps = []
    for owner, label in (('A', 1), ('A', 0), ('B', 0)):
        if not any(r['owner'] == owner and r['label'] == label and r['train_targets'] and r['check_targets'] for r in table):
            gaps.append('MISSING_COVERED_' + owner + str(label))
    # The singled-out ToN gaps cannot be hidden by another source's coverage.
    for source, owner in (('normal_scanning1.pcap', 'A'), ('password_normal1.pcap', 'A'),
                           ('normal_1.pcap', 'A'), ('normal_1.pcap', 'B')):
        present = [r for r in table if r['source_group'] == source and r['owner'] == owner]
        if present and not all(r['train_targets'] and r['check_targets'] for r in present):
            gaps.append('MISSING_TON_TRAIN_CHECK:' + source + ':' + owner)
    return table, gaps


def schedule_receipt(rows):
    groups = {g: {} for g in ('A', 'B')}
    for r in rows:
        if r['new_role'] == 'train':
            d = groups[r['owner']]
            d[r['context_key']] = max(d.get(r['context_key'], 0), r['event_index'] + 1)
    na, nb = len(groups['A']), len(groups['B'])
    steps = (na + 31) // 32
    if not na or not nb:
        return {'status': 'EMPTY_TRAINING_GROUP', 'N_A': na, 'N_B': nb}
    hashes, padding, events = [], Counter(), Counter()
    for epoch in range(1, 41):
        orders = {g: sorted(d, key=lambda k: (digest(canonical(['paired-order-v1', 2705, epoch, g, k])), k)) for g, d in groups.items()}
        hashes.append({'epoch': epoch, **{g + '_order_sha256': digest(canonical(order)) for g, order in orders.items()}})
        for g, order in orders.items():
            q, rem = divmod(len(order), steps); cursor = 0
            for i in range(steps):
                count = q + (i < rem); bucket = order[cursor:cursor+count]; cursor += count
                for j in range(0, len(bucket), 32):
                    micro = bucket[j:j+32]
                    padding[g] += len(micro) * max(groups[g][k] for k in micro)
                    events[g] += sum(groups[g][k] for k in micro)
            require(cursor == len(order), 'SCHEDULE_CONSERVATION')
    return {'status': 'METADATA_SCHEDULE_SEALED_NOT_TRAINING', 'N_A': na, 'N_B': nb,
            'steps_per_epoch': steps, 'epochs': 40, 'updates_per_arm': steps * 40,
            'epoch_order_hashes': hashes, 'train_context_events_both_arms': 2 * events['A'] + events['B'],
            'train_padded_slots_both_arms': 2 * padding['A'] + padding['B'],
            'full_initialization_or_model_created': False}
