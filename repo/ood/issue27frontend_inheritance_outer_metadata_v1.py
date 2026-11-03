"""Metadata projection only: never decode signatures, model arrays or scores."""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import re
import time
from collections import Counter, defaultdict

import issue27frontend_inheritance_outer_support_v1 as s

CORPUS = 'runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_contexts.jsonl.gz'
TARGET = 'runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_fit_select_target_metadata.csv'
PACKET = 'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv'
R0 = 'runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json'
SCOPE = 'runs/frontend_f5_unified_student_v1_20260906_local/preflight/uid_scope.csv'
F1_MANIFEST = 'runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_corpus_manifest.json'
TEACHER_CENSUS = 'runs/frontend_f1_d0_census_v1_20260902_local_r2/f1_d0_teacher_coverage_census.json'
BENIGN = 'runs/frontend_f1_teacher_benign_count_only_v1_20260902_local/f1_teacher_benign_uid_verdicts.csv.gz'
PINS = {
    TEACHER_CENSUS: 'f9dc000b9fb115bf10080a67efd7bd3490762b683aa452a5daa5b95acc9e1ee9',
    BENIGN: 'f7deceac0ac76fb25e577714f7a94da047e15ed77cb9bee19a9ea9c2954c493b',
    CORPUS: '623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e',
    TARGET: 'd6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d',
    PACKET: '5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c',
    R0: '41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11',
    SCOPE: '529ec944e31463f98173ec1103920f6ca21e4a7ad9cff080bd85cebb3b9394e9',
    F1_MANIFEST: '748cd9aa98a15d491b6b4b5f7b84d2679c566ca417084fb17e6236227a4e162b',
    s.DESIGN: s.DESIGN_SHA,
}
STRING = re.compile(r'"(?:[^"\\\x00-\x1f]|\\(?:["\\/bfnrt]|u[0-9a-fA-F]{4}))*"')
ATOM = re.compile(r'(?:-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?|true|false|null|NaN)')
TARGET_FIELDS = {'uid', 'event_index', 'owner', 'label', 'teacher_kind', 'role',
                 'source_group', 'device_family', 'attack_family', 'timestamp_epoch'}


def ordinal(value):
    # Historical CSV export spells integral packet positions as e.g. 42.0.
    s.require(isinstance(value, str) and re.fullmatch(r'(?:0|[1-9][0-9]*)(?:\.0+)?', value), 'PACKET_ORDINAL')
    return int(value.split('.')[0])


def ws(text, i):
    while i < len(text) and text[i] in ' \r\n\t':
        i += 1
    return i


def skip(text, i, depth=0):
    """Validate token syntax without constructing the skipped JSON values."""
    s.require(depth <= 12 and i < len(text), 'JSON_DEPTH_OR_END')
    if text[i] == '"':
        match = STRING.match(text, i)
        s.require(match is not None, 'JSON_STRING')
        return match.end()
    if text[i] not in '[{':
        match = ATOM.match(text, i)
        s.require(match is not None, 'JSON_ATOM')
        return match.end()
    opening, closing = text[i], ']' if text[i] == '[' else '}'
    i = ws(text, i + 1)
    if i < len(text) and text[i] == closing:
        return i + 1
    while True:
        if opening == '{':
            s.require(i < len(text) and text[i] == '"', 'JSON_KEY')
            i = ws(text, skip(text, i, depth + 1))
            s.require(i < len(text) and text[i] == ':', 'JSON_COLON')
            i = ws(text, i + 1)
        i = ws(text, skip(text, i, depth + 1))
        s.require(i < len(text), 'JSON_END')
        if text[i] == closing:
            return i + 1
        s.require(text[i] == ',', 'JSON_SEPARATOR')
        i = ws(text, i + 1)


def spans(text, object_mode=True):
    text = text.strip()
    s.require(text and text[0] == ('{' if object_mode else '['), 'JSON_CONTAINER')
    s.require(skip(text, 0) == len(text), 'JSON_TRAILING')
    result, i = ({} if object_mode else []), ws(text, 1)
    while text[i] not in '}]':
        if object_mode:
            end = skip(text, i)
            key = json.loads(text[i:end])
            s.require(key not in result, 'DUPLICATE_JSON_KEY')
            i = ws(text, end)
            s.require(text[i] == ':', 'JSON_COLON')
            i = ws(text, i + 1)
        end = skip(text, i)
        if object_mode:
            result[key] = text[i:end]
        else:
            result.append(text[i:end])
        i = ws(text, end)
        if text[i] == ',':
            i = ws(text, i + 1)
    return result


def project_context(line, audit, decode_signatures=False):
    raw = spans(line)
    s.require(set(raw) == {'context_key', 'source_group', 'split', 'signatures', 'targets'}, 'CORPUS_SCHEMA')
    split, source, key = (json.loads(raw[k]) for k in ('split', 'source_group', 'context_key'))
    s.require(split in ('train', 'internal_val') and (source in s.SOURCES) == (split == 'internal_val'),
              'OUTER_SPLIT_SOURCE')
    parts = key.split('\x1f')
    s.require(len(parts) == 3 and parts[0] and re.fullmatch('[0-9a-f]{64}', parts[1]), 'CONTEXT_ID')
    s.base.integer(parts[2])
    rows = []
    for item in spans(raw['targets'], False):
        target = spans(item)
        s.require(set(target) == TARGET_FIELDS, 'TARGET_SCHEMA')
        keep = TARGET_FIELDS - {'timestamp_epoch'} if split == 'internal_val' else {'uid', 'event_index'}
        row = {k: json.loads(target[k]) for k in keep}
        row['event'] = row.pop('event_index')
        s.require(type(row['event']) is int and 0 <= row['event'] < 256, 'TARGET_EVENT')
        rows.append(row)
    s.require(rows, 'EMPTY_CONTEXT')
    length = max(t['event'] for t in rows) + 1
    audit['context_rows'] = audit.get('context_rows', 0) + 1
    result = {'key': key, 'source': source, 'split': split, 'member': parts[0],
              'length': length, 'targets': rows}
    if decode_signatures and split == 'internal_val':
        result['signatures'] = json.loads(raw['signatures'])
        s.require(isinstance(result['signatures'], list) and len(result['signatures']) == length
                  and all(type(v) is str for v in result['signatures']), 'SIGNATURE_SHAPE')
        audit['selected_signature_contexts_decoded'] = audit.get('selected_signature_contexts_decoded', 0) + 1
    else:
        s.require(raw['signatures'].startswith('['), 'SIGNATURE_CONTAINER')
    return result


def corpus(blob, audit, decode_signatures=False, check=lambda: None):
    result, total, seen = [], 0, set()
    with gzip.GzipFile(fileobj=io.BytesIO(blob)) as stream:
        while True:
            check()
            line = stream.readline(1024**2 + 1)
            if not line:
                break
            total += len(line)
            s.require(len(line) <= 1024**2 and total <= 128 * 1024**2 and len(result) < 12889,
                      'CORPUS_SIZE')
            item = project_context(line.decode('utf-8'), audit, decode_signatures)
            s.require(item['key'] not in seen, 'DUPLICATE_CORPUS_CONTEXT')
            seen.add(item['key']); result.append(item)
    audit['corpus_decompressed_bytes'] = total
    audit['signatures_numeric_decoded'] = False
    audit['skipped_json_values_lexically_scanned'] = True
    return result


def selected_csv(blob, selector, fields, audit, compressed=False, check=lambda: None):
    stream = gzip.GzipFile(fileobj=io.BytesIO(blob)) if compressed else io.BytesIO(blob)
    total = 0
    def lines():
        nonlocal total
        while True:
            check()
            line = stream.readline(65537)
            if not line:
                break
            total += len(line)
            s.require(len(line) <= 65536 and total <= 64 * 1024**2, 'CSV_SIZE')
            yield line.decode('utf-8-sig')
    result = []
    try:
        reader = csv.DictReader(lines(), strict=True)
        s.require(reader.fieldnames and len(reader.fieldnames) == len(set(reader.fieldnames))
                  and set(fields) <= set(reader.fieldnames), 'CSV_SCHEMA')
        count = 0
        for row in reader:
            count += 1
            s.require(count <= 25467 and None not in row and all(v is not None for v in row.values()), 'CSV_ROW')
            if selector(row):
                result.append({k: row[k] for k in fields})
        audit.update(rows_tokenized=count, retained=len(result), projected_fields=list(fields),
                     unselected_payload_retained=0, full_csv_row_transient_tokenization=True)
    finally:
        stream.close()
    return result


def qualify(root, output):
    start = time.monotonic()
    def check():
        s.require(time.monotonic() - start < 600, 'METADATA_WALL_CAP')
        s.require(s.base.peak_memory() < 1024**3, 'METADATA_MEMORY_CAP')
    data = {name: s.read_pinned(root, name, sha) for name, sha in PINS.items()}
    audit = {'raw_captures_opened': 0, 'feature_arrays_decoded': 0, 'model_loads': 0,
             'model_forwards': 0, 'teacher_forwards': 0, 'optimizer_steps': 0}
    all_contexts = corpus(data[CORPUS], audit, check=check)
    selected = sorted((c for c in all_contexts if c['split'] == 'internal_val'), key=lambda c: c['key'])
    parent = [c for c in all_contexts if c['split'] == 'train']
    lookup = {}
    all_uids = set()
    for c in all_contexts:
        for t in c['targets']:
            s.require(t['uid'] not in all_uids, 'DUPLICATE_CORPUS_UID')
            all_uids.add(t['uid'])
            if c['split'] == 'internal_val':
                lookup[t['uid']] = (c, t)
    s.require(len(all_contexts) == 12889 and len(all_uids) == 18266 and len(parent) == 9307,
              'CORPUS_DENOMINATOR')
    parent_uids = {t['uid'] for c in parent for t in c['targets']}
    scopes = selected_csv(data[SCOPE], lambda row: True, ('uid', 'split', 'source', 'owner', 'context'),
                          audit.setdefault('F5_scope', {}), check=check)
    s.require(len(scopes) == len(parent_uids) == 13866 and {r['uid'] for r in scopes} == parent_uids,
              'F5_PARENT_UID_JOIN')
    parent_map = {t['uid']: c for c in parent for t in c['targets']}
    for row in scopes:
        c = parent_map[row['uid']]
        s.require(row['context'] == c['key'] and row['source'] == c['source']
                  and row['split'] in ('train', 'val', 'internal_val'), 'F5_PARENT_CONTEXT_JOIN')
    s.require(not {c['member'] for c in selected} & {c['member'] for c in parent}
              and not {c['source'] for c in selected} & {c['source'] for c in parent}, 'FIT_DEPENDENCY_OVERLAP')
    fields = ('uid', 'phase', 'source_group', 'role', 'dataset_kind', 'container_path',
              'raw_source_path', 'target_event_position_within_capture', 'label_metric_only')
    targets = selected_csv(data[TARGET], lambda row: row['uid'] in lookup, fields,
                           audit.setdefault('raw_target_identity', {}), check=check)
    s.require(len(targets) == len(lookup) == 4400 and {r['uid'] for r in targets} == set(lookup), 'RAW_UID_JOIN')
    member_targets = defaultdict(list)
    for row in targets:
        c, t = lookup[row['uid']]
        s.require(row['phase'] == 'fit' and row['source_group'] == c['source']
                  and row['role'] == t['role'] and row['raw_source_path'] == c['member'], 'RAW_TARGET_ATTACHMENT')
        position = ordinal(row['target_event_position_within_capture'])
        t['position'] = position
        t['category'] = s.categorize(t)
        t['protected'] = t['category'] in ('A1C', 'A0C')
        key = (row['dataset_kind'], row['container_path'], row['raw_source_path'])
        member_targets[key].append({'uid': t['uid'], 'source_group': c['source'],
            'expected_context_key': c['key'], 'expected_event_index': t['event'],
            'position': position, 'scope': 'outer_internal_val'})
    packet_fields = ('dataset_kind', 'container_path', 'container_bytes', 'container_sha256',
        'published_identity_if_archive', 'raw_source_path', 'member_uncompressed_bytes_if_archive',
        'member_crc32_if_archive', 'source_group', 'maximum_target_event_position_inclusive', 'is_report', 'is_final')
    packets = selected_csv(data[PACKET], lambda row: (row['dataset_kind'], row['container_path'],
                           row['raw_source_path']) in member_targets, packet_fields,
                           audit.setdefault('packet_identity', {}), check=check)
    s.require(len(packets) == len(member_targets) == 5, 'MEMBER_COUNT')
    members = []
    seen_members = set()
    for packet in packets:
        key = tuple(packet[k] for k in ('dataset_kind', 'container_path', 'raw_source_path'))
        s.require(key not in seen_members, 'DUPLICATE_MEMBER'); seen_members.add(key)
        s.require(packet['is_report'].lower() == packet['is_final'].lower() == 'false', 'FORBIDDEN_MEMBER')
        ts = sorted(member_targets[key], key=lambda r: r['position'])
        s.require(len({t['position'] for t in ts}) == len(ts), 'DUPLICATE_RAW_POSITION')
        maximum = max(t['position'] for t in ts)
        s.require(maximum <= ordinal(packet['maximum_target_event_position_inclusive']), 'RAW_CUTOFF')
        members.append({'identity': packet, 'maximum': maximum, 'packets': maximum + 1, 'targets': ts})
    # Context tiers are identity metadata in the legal-fit census, never guessed from A/B.
    import issue27frontend_inheritance_n0_inventory_v1 as n0
    d0_blob = s.read_pinned(root, n0.MIXED, n0.PINS[n0.MIXED])
    tiers = selected_csv(d0_blob, lambda row: row['uid'] in lookup,
        ('uid', 'phase', 'legal_fit', 'cross_phase_context', 'owner', 'label_kind', 'context_tier', 'semantic_context_key'),
        audit.setdefault('legal_fit_tiers', {}), compressed=True, check=check)
    s.require(len(tiers) == 4400 and {r['uid'] for r in tiers} == set(lookup), 'LEGAL_FIT_JOIN')
    for row in tiers:
        c, t = lookup[row['uid']]
        s.require(row['phase'] == 'fit' and row['legal_fit'] == 'True' and row['cross_phase_context'] == 'False'
                  and row['semantic_context_key'] == c['key'] and row['owner'] == t['owner']
                  and row['label_kind'] == ('attack' if t['label'] else 'benign'), 'LEGAL_FIT_ATTACHMENT')
        s.require(row['context_tier'] in ('H1', 'H2', 'H3', 'H4'), 'TIER_SCHEMA')
        t['tier'] = row['context_tier']
    counts = s.validate_population(selected)
    teacher = json.loads(data[TEACHER_CENSUS])
    s.require(teacher['fit_attack_anchor_all_hard'] is True
              and teacher['a_true_attack_hard_rows'] == teacher['a_true_attack_rows'] == 4182
              and teacher['missing_score_pinning_used_as_teacher'] is False
              and teacher['teacher_benign_uid_verdicts_sha256'] == PINS[BENIGN], 'TEACHER_PROVENANCE')
    benign_uids = {u for u, (c, t) in lookup.items() if t['category'] in ('A0C', 'A0W')}
    benign = selected_csv(data[BENIGN], lambda row: row['uid'] in benign_uids, ('uid', 'hard'),
                          audit.setdefault('benign_teacher', {}), compressed=True, check=check)
    s.require(len(benign) == 1176 and {r['uid'] for r in benign} == benign_uids, 'BENIGN_TEACHER_UIDS')
    for row in benign:
        s.require(row['hard'] in ('true', 'false') and (row['hard'] == 'true')
                  == (lookup[row['uid']][1]['category'] == 'A0W'), 'BENIGN_TEACHER_ATTACHMENT')
    audit['attack_teacher_provenance'] = 'sealed universal legal-fit all-hard census plus exact fit UID join; no new score read'
    events = sum(c['length'] for c in selected)
    padded = sum(len(selected[i:i+32]) * max(c['length'] for c in selected[i:i+32])
                 for i in range(0, len(selected), 32))
    result = {'status': 'OUTER_METADATA_QUALIFIED', 'contexts': selected,
        'members': sorted(members, key=lambda m: tuple(m['identity'][k] for k in ('dataset_kind', 'container_path', 'raw_source_path'))),
        'categories': counts, 'raw_packets': sum(m['packets'] for m in members), 'events': events,
        'feature_bytes': events * 524, 'batches': (len(selected) + 31) // 32, 'padded_slots': padded,
        'maximum_prefix': max(c['length'] for c in selected), 'input_pins': {**PINS, n0.MIXED: n0.PINS[n0.MIXED]},
        'tshark_identity': json.loads(data[R0])['tshark_identity'],
        'exclusion': {'F5_parent_UID_overlap': 0, 'F5_parent_context_overlap': 0, 'F5_parent_member_overlap': 0,
            'F5_parent_source_overlap': 0, 'N3_fit_exclusion': 'by verified F5 parent and sealed N3 subset contract',
            'F1_validation_and_frontend_design_exposed': True, 'old_sessions': 'UNKNOWN',
            'pretraining_overlap': 'UNKNOWN', 'physical_device_independence': 'UNKNOWN'},
        'access': audit, **s.CLAIMS}
    output.mkdir(parents=True, exist_ok=False)
    with (output / 'qualified_metadata.json').open('xb') as stream:
        stream.write(s.json_bytes(result))
    s.atomic_json(output / 'qualification_receipt.json', {'status': result['status'], 'targets': 4400,
        'contexts': 3582, 'members': 5, 'raw_packets': result['raw_packets'], 'events': events,
        'feature_bytes': result['feature_bytes'], 'batches': result['batches'], 'padded_slots': padded,
        'access': audit, 'elapsed_seconds': time.monotonic() - start, **s.CLAIMS})
    s.seal(output)
    return {k: result[k] for k in ('status', 'categories', 'raw_packets', 'events', 'feature_bytes', 'batches', 'padded_slots')}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualify-metadata', action='store_true', required=True)
    parser.parse_args()
    print(json.dumps(qualify(s.ROOT, s.ROOT / s.METADATA)), flush=True)
