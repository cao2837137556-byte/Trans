"""Metadata-only deterministic bounded selection and the two cutoff views.

The census stays on disk. Component summaries and a single component's sorted
positions are SQLite temporary tables in guarded process memory; Python holds
at most twice a row cap in the allocation queue and only selected metadata. No
features, scores, labels, or distances are read by the allocation algorithm.
"""
from collections import Counter
import hashlib
import heapq
import json
from pathlib import Path
import sqlite3

from .common import (DEV_CAP, REF_CAP, HEIM, SALT, TARGETS, VERSION, digest,
                     require, sha, write, write_rows)


def point_rank(uid):
    return hashlib.sha256((SALT + '|' + uid).encode()).hexdigest(), uid


def _uniform_time_db(db, device, protocol, role, component, count):
    """Exact dense binding._uniform_time, using indexed disk positions.

    At each target the frozen greedy search restricts the selectable index
    interval, then minimizes (absolute time difference, point rank). Only the
    nearest timestamp on either side can win; ties within that timestamp use
    point rank. This gives the same answer without loading a giant component.
    """
    require(type(count) is int and count > 0, 'INVALID_UNIFORM_COUNT')
    db.execute('DROP TABLE IF EXISTS temp.uniform_positions')
    db.execute('''CREATE TEMP TABLE uniform_positions AS
        SELECT row_number() OVER (ORDER BY timestamp,rank,uid)-1 AS idx,
               timestamp,rank,uid
        FROM candidates WHERE device=? AND protocol=? AND role=? AND component_id=?''',
        (device, protocol, role, component))
    db.execute('CREATE UNIQUE INDEX temp.uniform_idx ON uniform_positions(idx)')
    db.execute('CREATE INDEX temp.uniform_time ON uniform_positions(timestamp,rank,uid)')
    n, lo, hi = db.execute('SELECT count(*),min(timestamp),max(timestamp) FROM uniform_positions').fetchone()
    require(count <= n, 'UNIFORM_QUOTA_EXCEEDS_COMPONENT')
    if count == n:
        return [r[0] for r in db.execute('SELECT uid FROM uniform_positions ORDER BY idx')]
    targets = [(lo + hi) / 2] if count == 1 else [
        lo + (hi - lo) * j / (count - 1) for j in range(count)]
    result, start = [], 0
    for j, target in enumerate(targets):
        stop = n - (count - j - 1)
        options = []
        for relation, direction in (('<=', 'DESC'), ('>=', 'ASC')):
            hit = db.execute(f'''SELECT timestamp FROM uniform_positions
                WHERE idx>=? AND idx<? AND timestamp {relation} ?
                ORDER BY timestamp {direction} LIMIT 1''', (start, stop, target)).fetchone()
            if hit is not None:
                row = db.execute('''SELECT idx,timestamp,rank,uid FROM uniform_positions
                    WHERE idx>=? AND idx<? AND timestamp=? ORDER BY rank,uid LIMIT 1''',
                    (start, stop, hit[0])).fetchone()
                options.append(row)
        require(options, 'UNIFORM_EMPTY_INTERVAL')
        picked = min(options, key=lambda r: (abs(r[1] - target), r[2], r[3]))
        result.append(picked[3])
        start = picked[0] + 1
    return result


def _allocate(db, device, role, cap, protocol=None, *, prioritize_new=False):
    """Allocate component seats; load only groups which can receive a seat."""
    where, args = 'g.device=? AND g.role=?', [device, role]
    if protocol is not None:
        where += ' AND g.protocol=?'
        args.append(protocol)
    total, components = db.execute(f'SELECT coalesce(sum(n),0),count(*) FROM census_groups g WHERE {where}', args).fetchone()
    new_where = where + ''' AND NOT EXISTS(SELECT 1 FROM old_components o
        WHERE o.device=g.device AND o.protocol=g.protocol AND o.component_id=g.component_id)'''
    new_count = db.execute(f'SELECT count(*) FROM census_groups g WHERE {new_where}', args).fetchone()[0]
    summaries = {}
    reserved = []
    if prioritize_new:
        reserved = list(db.execute(f'''SELECT protocol,component_id,n,point_order
            FROM census_groups g WHERE {new_where}
            ORDER BY point_order,component_id LIMIT ?''', args + [cap]))
        summaries.update({(r[0], r[1]): r for r in reserved})
    top = db.execute(f'''SELECT protocol,component_id,n,point_order FROM census_groups g
        WHERE {where} ORDER BY point_order,component_id LIMIT ?''', args + [cap])
    summaries.update({(r[0], r[1]): r for r in top})
    quotas = {key: 0 for key in summaries}
    for row in reserved:
        quotas[(row[0], row[1])] = 1
    queue = [(quotas[key], row[3], key) for key, row in summaries.items()
             if quotas[key] < row[2]]
    heapq.heapify(queue)
    seats = sum(quotas.values())
    while seats < min(cap, total):
        require(queue, 'ALLOCATION_QUEUE_EXHAUSTED')
        occupied, rank, key = heapq.heappop(queue)
        quotas[key] += 1
        seats += 1
        if quotas[key] < summaries[key][2]:
            heapq.heappush(queue, (occupied + 1, rank, key))
    selected = []
    selected_components = set()
    for key in sorted(quotas, key=lambda k: (summaries[k][3], k)):
        if not quotas[key]:
            continue
        selected_components.add(key)
        selected.extend(_uniform_time_db(db, device, key[0], role, key[1], quotas[key]))
    old = {(r[0], r[1]) for r in db.execute(
        'SELECT protocol,component_id FROM old_components WHERE device=?', (device,))}
    new_selected = selected_components - old
    return selected, dict(device=device, role=role, protocol=protocol, cap=cap,
        candidate_rows=total, candidate_components=components,
        no_old_anchor_components=new_count, selected_rows=len(selected),
        selected_components=len(selected_components), new_components=len(new_selected),
        uncovered_components=components-len(selected_components),
        uncovered_no_old_anchor_components=new_count-len(new_selected),
        priority='NO_OLD_ANCHOR_FIRST' if prioritize_new else 'ALL_COMPONENT_ROUND_ROBIN',
        component_rank='MIN(SHA256(salt+"|"+uid),uid)',
        time_selection='DENSE_BINDING_UNIFORM_TIME_EXACT')


def select_candidates(db_path, old_rows, output_dir, *, devices=None):
    """Select the complete legal endpoint census, with a replayable receipt.

    Required table: candidates(uid PRIMARY KEY,device,protocol,component_id,
    timestamp,frame,role,rank,body). Roles are HIST_REF/HIST_DEV (REF/DEV aliases
    are accepted and normalized in the working connection). `body` is full
    metadata JSON. Output is capped at 24576 REF and 12288 DEV rows. Inputs are
    opened read-only; temporary tables use process memory, so the runtime RSS
    watchdog counts them and no unaccounted external temporary disk is used.
    `devices` optionally restricts this exact same policy to explicit registered
    device strings, allowing independent member preparation within disk limits.
    """
    db_path, output_dir = Path(db_path).resolve(), Path(output_dir).resolve()
    registered = {r['device']: r for r in TARGETS.values()}
    devices = list(registered) if devices is None else list(devices)
    require(devices and len(devices) == len(set(devices)) and
            set(devices) <= set(registered), 'SELECTION_DEVICE_SCOPE')
    require(db_path.is_file(), 'CENSUS_DATABASE_MISSING')
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {role: output_dir / name for role, name in (
        ('HIST_REF', 'HIST_REF.jsonl.gz'), ('HIST_DEV', 'HIST_DEV.jsonl.gz'))}
    require(not any(p.exists() for p in paths.values()) and
            not (output_dir / 'SELECTION.json').exists(), 'SELECTION_OUTPUT_EXISTS')
    # A view performs the role alias mapping without mutating the real census.
    db = sqlite3.connect('file:' + db_path.as_posix() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA temp_store=MEMORY')
        db.execute('PRAGMA cache_size=-32768')
        db.create_function('frozen_rank', 1, lambda uid: point_rank(uid)[0], deterministic=True)
        columns = {r[1] for r in db.execute('PRAGMA main.table_info(candidates)')}
        require({'uid','device','protocol','component_id','timestamp','frame','role','rank','body'} <= columns,
                'CENSUS_SCHEMA')
        # Only alias synthetic/legacy spellings when necessary. Keeping the
        # canonical role column direct lets SQLite use every leading column of
        # the real census's component lookup index for large member streams.
        actual_roles = {r[0] for r in db.execute('SELECT DISTINCT role FROM main.candidates')}
        if actual_roles & {'REF', 'DEV'}:
            db.execute('''CREATE TEMP VIEW candidates AS SELECT uid,device,protocol,
                component_id,timestamp,frame,
                CASE role WHEN 'REF' THEN 'HIST_REF' WHEN 'DEV' THEN 'HIST_DEV' ELSE role END AS role,
                rank,body FROM main.candidates''')
        require(db.execute('''SELECT count(*) FROM candidates WHERE
            role NOT IN ('HIST_REF','HIST_DEV') OR protocol NOT IN (6,17) OR
            timestamp IS NULL OR frame<=0 OR length(uid)!=64 OR length(rank)!=64 OR
            uid GLOB '*[^0-9a-f]*' OR rank!=frozen_rank(uid)''').fetchone()[0] == 0,
            'CENSUS_INVALID_IDENTITY')
        require(db.execute('SELECT count(*)-count(DISTINCT uid) FROM candidates').fetchone()[0] == 0,
                'CENSUS_DUPLICATE_UID')
        require(set(r[0] for r in db.execute('SELECT DISTINCT device FROM candidates')) <=
                {r['device'] for r in TARGETS.values()}, 'CENSUS_UNREGISTERED_DEVICE')
        db.execute('''CREATE TEMP TABLE old_components(device TEXT,protocol INTEGER,
            component_id TEXT,PRIMARY KEY(device,protocol,component_id)) WITHOUT ROWID''')
        db.executemany('INSERT OR IGNORE INTO old_components VALUES(?,?,?)',
            ((r['device'], r['protocol'], r['component_id']) for r in old_rows))
        db.execute('''CREATE TEMP TABLE census_groups AS SELECT device,protocol,
            role,component_id,count(*) AS n,min(rank||uid) AS point_order
            FROM candidates GROUP BY device,protocol,role,component_id''')
        db.execute('CREATE INDEX temp.group_lookup ON census_groups(device,role,protocol,point_order)')
        selections = {'HIST_REF': [], 'HIST_DEV': []}
        groups, stops = [], []
        for target in (registered[device] for device in devices):
            device = target['device']
            for protocol in (6, 17):
                chosen, stats = _allocate(db, device, 'HIST_REF', REF_CAP, protocol,
                                          prioritize_new=True)
                selections['HIST_REF'].extend(chosen)
                groups.append(stats)
            chosen, stats = _allocate(db, device, 'HIST_DEV', DEV_CAP)
            selections['HIST_DEV'].extend(chosen)
            groups.append(stats)
            ref_stats = [r for r in groups if r['device'] == device and r['role'] == 'HIST_REF']
            if not sum(r['selected_rows'] for r in ref_stats):
                stops.append(dict(device=device, status='STOP_EMPTY_HIST_REF'))
            if not stats['selected_rows']:
                stops.append(dict(device=device, status='STOP_EMPTY_HIST_DEV'))
            if not sum(r['new_components'] for r in ref_stats):
                stops.append(dict(device=device, status='STOP_NO_NEW_COMPONENT'))
        require(not(set(selections['HIST_REF']) & set(selections['HIST_DEV'])), 'HISTORY_ROLE_UID_OVERLAP')
        specifications = {}
        for role, uids in selections.items():
            selected = []
            for uid in sorted(uids):
                value = db.execute('SELECT body,rank,device,protocol,component_id,timestamp,frame,role FROM candidates WHERE uid=?', (uid,)).fetchone()
                body = json.loads(value[0])
                require(body['uid'] == uid and point_rank(uid)[0] == value[1], 'CENSUS_POINT_RANK')
                require(all(body[k] == v for k, v in zip(
                    ('device','protocol','component_id','timestamp','frame'), value[2:7])), 'CENSUS_BODY_JOIN')
                require(value[7] == role, 'CENSUS_ROLE_JOIN')
                selected.append(body)
            write_rows(paths[role], selected)
            specifications[role] = dict(path=paths[role].as_posix(), sha256=sha(paths[role]),
                rows=len(selected), uid_sha256=digest(sorted(uids)))
        result = dict(version=VERSION, schema='history-selection-v1',
            status=stops[0]['status'] if stops else 'SELECTED', stops=stops,
            salt=SALT, ref_cap_per_device_protocol=REF_CAP, dev_cap_per_device=DEV_CAP,
            device_scope=devices,
            candidate_domain='ALL_LEGAL_ENDPOINTS', census_sha256=sha(db_path),
            ref_rows=specifications['HIST_REF'], dev_rows=specifications['HIST_DEV'],
            groups=groups, label_or_score_selection=False)
        result['selection_sha256'] = digest(result)
        write(output_dir / 'SELECTION.json', result)
        return result
    finally:
        db.close()


def bank_views(original_rows, historical_rows, pool):
    """Keep original rows byte-value intact; add history with two causal ends."""
    require(pool in ('CIC_DEV', 'UNSW_DEV'), 'AB_POOL')
    original_rows, historical_rows = list(original_rows), list(historical_rows)
    original_uids = [r['uid'] for r in original_rows]
    require(len(original_uids) == len(set(original_uids)), 'DUPLICATE_ORIGINAL_UID')
    ends = {}
    for row in original_rows:
        key = row['partition'], row['device']
        if key in ends:
            require(ends[key] == row['reference_end'], 'COMPLETE_BANK_END_MISMATCH')
        ends[key] = row['reference_end']
    allowed = {(HEIM['partition'], HEIM['device'])} if pool == 'CIC_DEV' else {
        (r['partition'], r['device']) for r in TARGETS.values()}
    seen = set(original_uids)
    additions, hist_dev = [], []
    historical_ends = {}
    for original in historical_rows:
        row = dict(original)
        require(row['uid'] not in seen, 'HISTORICAL_UID_OVERLAP')
        seen.add(row['uid'])
        key = row['partition'], row['device']
        require(key in allowed and key in ends, 'UNREGISTERED_HISTORY_DEVICE')
        require(row.get('use') == 'REFERENCE' and row.get('label') == 0, 'HISTORY_REFERENCE_ROLE')
        require(isinstance(row['capture_id'], str) and row['capture_id'], 'HISTORY_CAPTURE_STRING')
        require(row['timestamp'] <= row['reference_end'] <= ends[key], 'HISTORY_AB_CAUSAL_END')
        if pool == 'UNSW_DEV' or 'bank_end_frame' in row:
            require(type(row.get('bank_end_frame')) is int and row['frame'] <= row['bank_end_frame'],
                    'HISTORY_FRAME_CUTOFF')
        if key in historical_ends:
            require(historical_ends[key] == row['reference_end'], 'HISTORY_COMPLETE_END_MISMATCH')
        historical_ends[key] = row['reference_end']
        if pool == 'UNSW_DEV':
            target = next(r for r in TARGETS.values() if r['device'] == row['device'])
            require(row['reference_end'] == target['reference_end_us']/1e6 and
                    row['bank_end_frame'] == target['bank_end_frame'], 'HISTORY_PINNED_CUTOFF')
            hist_dev.append(dict(row))
        row['history_reference_end'] = row['reference_end']
        row['reference_end'] = ends[key]
        additions.append(row)
    return dict(AB_BANK=original_rows + additions, HIST_DEV_BANK=hist_dev)
