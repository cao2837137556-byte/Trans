"""Deterministic dense-reference position planning; no decoder, scores or E3.

Callers supply pinned, trusted commissioning scopes. Labels are never consulted
by the planner. Materialization checks trust and labels separately, after the
selection has been frozen. Source FIT/CAL queries cannot silently become normal
references. Existing encoded positions are used before any encoding requests.
"""
import hashlib
import heapq
import math
from collections import Counter, defaultdict


SALT = 'claude-dense-reference-r1-20261025'
MAX_POSITIONS = 4096
SCHEMA = 'onboarding-dense-position-plan-v1'
IDENTITY_FIELDS = ('uid', 'partition', 'device', 'protocol', 'source_sha256',
                   'capture_id', 'component_id', 'frame', 'timestamp')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _rank(uid, salt):
    return hashlib.sha256((salt + '|' + uid).encode('utf-8')).hexdigest(), uid


def _row(row):
    require(all(isinstance(row.get(k), str) and row[k] for k in
                ('uid', 'partition', 'device', 'source_sha256', 'capture_id',
                 'component_id')), 'DENSE_ROW_IDENTITY')
    require(row.get('protocol') in (6, 17) and type(row.get('frame')) is int and
            row['frame'] > 0, 'DENSE_ROW_PROTOCOL_FRAME')
    require(type(row.get('timestamp')) in (int, float) and
            math.isfinite(row['timestamp']), 'DENSE_ROW_TIME')


def _scopes(windows):
    result, ends = defaultdict(list), {}
    require(bool(windows), 'EXPLICIT_COMMISSIONING_SCOPES_REQUIRED')
    for item in windows:
        require(all(isinstance(item.get(k), str) and item[k] for k in
                    ('partition', 'device', 'source_sha256', 'capture_id')),
                'DENSE_SCOPE_IDENTITY')
        require(all(type(item.get(k)) in (int, float) and math.isfinite(item[k])
                    for k in ('start', 'end', 'reference_end')) and
                item['start'] <= item['end'] <= item['reference_end'],
                'DENSE_SCOPE_TIME')
        if 'frame_end' in item:
            require(type(item['frame_end']) is int and item['frame_end'] > 0,
                    'DENSE_SCOPE_FRAME')
        key = item['partition'], item['device']
        require(ends.setdefault(key, item['reference_end']) == item['reference_end'],
                'DENSE_DEVICE_CUTOFF_MISMATCH')
        result[key + (item['source_sha256'], item['capture_id'])].append(item)
    return result, ends


def _uniform_time(rows, count, salt):
    """Nearest positions to equally spaced times, without repeated positions.

    At each target retain enough subsequent positions for the remaining targets.
    Salted UID order breaks equal-time/equal-distance ties. A one-point quota
    selects the temporal midpoint. This rule is fixed before inspecting scores.
    """
    ordered = sorted(rows, key=lambda r: (r['timestamp'], _rank(r['uid'], salt)))
    if count == len(ordered):
        return ordered
    lo, hi = ordered[0]['timestamp'], ordered[-1]['timestamp']
    targets = [(lo + hi) / 2] if count == 1 else [
        lo + (hi - lo) * j / (count - 1) for j in range(count)]
    selected, start = [], 0
    for j, target in enumerate(targets):
        stop = len(ordered) - (count - j - 1)
        pick = min(range(start, stop), key=lambda i:
                   (abs(ordered[i]['timestamp'] - target),
                    _rank(ordered[i]['uid'], salt)))
        selected.append(ordered[pick])
        start = pick + 1
    return selected


def _balanced_select(rows, limit, salt, *, already_selected=()):
    if not rows or limit == 0:
        return []
    components = defaultdict(list)
    for row in rows:
        components[row['component_id']].append(row)
    ranks = {c: min(_rank(r['uid'], salt) for r in rr)
             for c, rr in components.items()}
    order = sorted(components, key=ranks.__getitem__)
    prior_counts = Counter(r['component_id'] for r in already_selected)
    quota = {c: 0 for c in order}
    # Existing anchors/encoded selections already occupy a component's turns.
    # Resetting counts between phases can spend the remaining budget on a
    # populated component while an available component has no selected point.
    queue = [(prior_counts[c], ranks[c], c) for c in order]
    heapq.heapify(queue)
    left = min(limit, len(rows))
    while left:
        occupied, rank, component = heapq.heappop(queue)
        quota[component] += 1
        left -= 1
        if quota[component] < len(components[component]):
            heapq.heappush(queue, (occupied + 1, rank, component))
    answer = []
    for component in order:
        if quota[component]:
            answer.extend(_uniform_time(components[component], quota[component], salt))
    return answer


def plan_dense_positions(candidates, windows, *, encoded_uids, mandatory_uids=(),
                         cap=MAX_POSITIONS, salt=SALT):
    """Plan at most cap positions per (partition, device, protocol).

    Mandatory original-bank UIDs are retained. Remaining slots first admit
    encoded positions, then unencoded legal candidates, using component round
    robin quotas and uniform times within each component. The caller enumerates
    *legal* candidates; a raw packet count is not a legal-position census.
    No label, fit role, score, stage, or feature value affects this selection.
    """
    require(type(cap) is int and 0 < cap <= MAX_POSITIONS, 'DENSE_CAP')
    require(isinstance(salt, str) and bool(salt), 'DENSE_SALT')
    scopes, ends = _scopes(windows)
    encoded, mandatory = set(encoded_uids), set(mandatory_uids)
    require(mandatory <= encoded, 'MANDATORY_REFERENCE_NOT_ENCODED')
    by_uid, indices, groups = {}, {}, defaultdict(list)
    excluded = duplicates = 0
    for i, row in enumerate(candidates):
        _row(row)
        uid = row['uid']
        if uid in by_uid:
            require(all(row[k] == by_uid[uid][k] for k in IDENTITY_FIELDS),
                    'DENSE_CONFLICTING_DUPLICATE_UID')
            duplicates += 1
            continue
        by_uid[uid], indices[uid] = row, i
        key = row['partition'], row['device'], row['source_sha256'], row['capture_id']
        legal = any(s['start'] <= row['timestamp'] <= s['end'] and
                    ('frame_end' not in s or row['frame'] <= s['frame_end'])
                    for s in scopes.get(key, ()))
        if legal:
            groups[(row['partition'], row['device'], row['protocol'])].append(row)
        else:
            excluded += 1
    admitted = {r['uid'] for rr in groups.values() for r in rr}
    require(mandatory <= admitted, 'MANDATORY_REFERENCE_OUTSIDE_SCOPE')
    selected, reports = [], []
    for key in sorted(groups):
        rows = groups[key]
        anchors = sorted((r for r in rows if r['uid'] in mandatory),
                         key=lambda r: _rank(r['uid'], salt))
        require(len(anchors) <= cap, 'MANDATORY_REFERENCE_EXCEEDS_CAP')
        known = [r for r in rows if r['uid'] in encoded and r['uid'] not in mandatory]
        new = [r for r in rows if r['uid'] not in encoded]
        chosen = anchors + _balanced_select(known, cap - len(anchors), salt,
                                            already_selected=anchors)
        chosen += _balanced_select(new, cap - len(chosen), salt,
                                   already_selected=chosen)
        chosen = sorted(chosen, key=lambda r: r['uid'])
        selected.extend(chosen)
        reports.append(dict(partition=key[0], device=key[1], protocol=key[2],
            reference_end=ends[key[:2]], legal_candidate_positions=len(rows),
            legal_components=len({r['component_id'] for r in rows}),
            available_encoded_positions=len(anchors) + len(known),
            mandatory_positions=len(anchors), selected_positions=len(chosen),
            selected_components=len({r['component_id'] for r in chosen}),
            selected_encoded_positions=sum(r['uid'] in encoded for r in chosen),
            supplemental_encoding_positions=sum(r['uid'] not in encoded for r in chosen),
            selected_uids=[r['uid'] for r in chosen]))
    uids = [r['uid'] for r in selected]
    return dict(schema=SCHEMA, cap=cap, salt=salt, windows=windows, groups=reports,
                excluded_positions=excluded, duplicate_positions=duplicates,
                selected_uids=uids, selected_indices=[indices[u] for u in uids],
                supplemental_encoding_uids=[u for u in uids if u not in encoded],
                selected_uid_sha256=hashlib.sha256(
                    ('\n'.join(uids) + '\n').encode()).hexdigest(),
                label_or_score_selection=False)


def materialize_source_metadata(plan, candidates, *, trusted_scope_verified,
                                 cal_components=(), available_encoded_uids=None):
    """Audit labels after frozen selection, never silently relabel attacks.

    Supplemental positions remain forbidden by default. After a separate
    encoding operation, callers can supply the complete available UID set to
    consume the original frozen plan without selecting positions again. This
    checks availability; the caller still binds vectors to the pinned encoder.
    """
    require(plan.get('schema') == SCHEMA, 'DENSE_PLAN_SCHEMA')
    require(trusted_scope_verified is True, 'TRUSTED_SOURCE_SCOPE_NOT_VERIFIED')
    if available_encoded_uids is None:
        require(not plan['supplemental_encoding_uids'], 'SOURCE_E3_ENCODING_REQUIRED')
    else:
        require(set(plan['selected_uids']) <= set(available_encoded_uids),
                'SOURCE_SELECTED_UID_NOT_ENCODED')
    forbidden = set(cal_components)
    ends = {(r['partition'], r['device']): r['reference_end'] for r in plan['groups']}
    answer = []
    for uid, index in zip(plan['selected_uids'], plan['selected_indices']):
        row = candidates[index]
        require(row['uid'] == uid, 'DENSE_PLAN_UID_JOIN')
        require(row['partition'] == 'LEARN', 'SOURCE_REFERENCE_PARTITION')
        require(row.get('label') == 0, 'SELECTED_SOURCE_WINDOW_HAS_NONNORMAL_LABEL')
        require(row['component_id'] not in forbidden and row.get('fit_role') != 'CAL',
                'DENSE_CAL_REFERENCE_LEAKAGE')
        answer.append(dict(row, use='REFERENCE',
                           reference_end=ends[(row['partition'], row['device'])]))
    return answer
