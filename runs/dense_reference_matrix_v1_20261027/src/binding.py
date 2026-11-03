"""Metadata-only dense/WRONG preparation. No score loading or model execution.

The third-pool branch deliberately distinguishes absent assets from an existing
frozen bank whose producer did not define a commissioning window.
"""
from collections import Counter, defaultdict
import argparse
import gzip
import hashlib
import heapq
import json
import math
from pathlib import Path

DENSE_SALT = 'claude-dense-reference-r1-20261025'
DONOR_SALT = 'paper04-wrong-v1|'
THIRD_POOL = 'CIC_THREE_DEVICE_REGRESSION_CONSUMED'
IDENTITY = ('uid', 'partition', 'device', 'protocol', 'source_sha256',
            'capture_id', 'component_id', 'frame', 'timestamp')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha256(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 ** 2), b''):
            result.update(block)
    return result.hexdigest()


def uid_hash(uids):
    return hashlib.sha256(('\n'.join(uids) + '\n').encode()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def read_rows(path):
    opener = gzip.open if str(path).endswith('.gz') else open
    with opener(path, 'rt', encoding='utf-8-sig') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_json(path, value):
    path = Path(path)
    require(not path.exists(), 'OUTPUT_ALREADY_EXISTS:' + str(path))
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
        allow_nan=False) + '\n', encoding='utf-8')


def asset(root, path, expected=None, **extra):
    root, path = Path(root).resolve(), Path(path).resolve()
    require(path.is_file(), 'MISSING_ASSET:' + str(path))
    actual = sha256(path)
    require(expected is None or actual == expected, 'ASSET_SHA256_MISMATCH:' + str(path))
    return dict(path=path.relative_to(root).as_posix() if path.is_relative_to(root)
                else path.as_posix(), sha256=actual, bytes=path.stat().st_size, **extra)


def verify_asset(root, entry):
    path = Path(root) / entry['path']
    require(path.is_file() and sha256(path) == entry['sha256'], 'ASSET_CHANGED:' + str(path))
    require(path.stat().st_size == entry['bytes'], 'ASSET_SIZE_CHANGED:' + str(path))
    return path


def _rank(uid, salt=DENSE_SALT):
    return hashlib.sha256((salt + '|' + uid).encode()).hexdigest(), uid


def _uniform_time(rows, count, salt):
    ordered = sorted(rows, key=lambda r: (r['timestamp'], _rank(r['uid'], salt)))
    if count == len(ordered):
        return ordered
    lo, hi = ordered[0]['timestamp'], ordered[-1]['timestamp']
    targets = [(lo + hi) / 2] if count == 1 else [
        lo + (hi - lo) * j / (count - 1) for j in range(count)]
    result, start = [], 0
    for j, target in enumerate(targets):
        stop = len(ordered) - (count - j - 1)
        index = min(range(start, stop), key=lambda i: (
            abs(ordered[i]['timestamp'] - target), _rank(ordered[i]['uid'], salt)))
        result.append(ordered[index])
        start = index + 1
    return result


def subsample_dense(rows, count, salt=DENSE_SALT):
    """Same all-encoded, no-anchor branch as frozen dense-position selection."""
    require(type(count) is int and count >= 0, 'INVALID_SUBSAMPLE_COUNT')
    if not rows or count == 0:
        return []
    components = defaultdict(list)
    for row in rows:
        components[row['component_id']].append(row)
    ranks = {key: min(_rank(r['uid'], salt) for r in rr)
             for key, rr in components.items()}
    order = sorted(components, key=ranks.__getitem__)
    quota = {key: 0 for key in order}
    queue = [(0, ranks[key], key) for key in order]
    heapq.heapify(queue)
    for _ in range(min(count, len(rows))):
        occupied, rank, key = heapq.heappop(queue)
        quota[key] += 1
        if quota[key] < len(components[key]):
            heapq.heappush(queue, (occupied + 1, rank, key))
    chosen = [r for key in order if quota[key]
              for r in _uniform_time(components[key], quota[key], salt)]
    return sorted(chosen, key=lambda r: r['uid'])


def _window_signature(windows, partition, device):
    result = []
    for window in windows:
        if (window.get('partition'), window.get('device')) != (partition, device):
            continue
        require(all(field in window for field in ('source_sha256', 'capture_id',
                    'start', 'end', 'reference_end')), 'EXPLICIT_WINDOW_REQUIRED')
        require(window['start'] <= window['end'] <= window['reference_end'], 'INVALID_WINDOW')
        result.append({k: v for k, v in window.items() if k != 'device'})
    require(result, 'EXPLICIT_WINDOW_REQUIRED:' + device)
    return digest(sorted(result, key=lambda r: (r['source_sha256'], r['capture_id'], r['start'])))


def freeze_wrong_reference_plan(pool_id, rows, windows, *, expected_selected_uid_sha256=None,
                                dense_salt=DENSE_SALT):
    """Freeze r3 donors by identity only; labels and scores are not inspected.

    Rows are the already-frozen dense bank, not all raw candidates. A donor
    with fewer than n points supplies all of them. No donor is NOT_EVALUABLE.
    """
    rows = [{field: row[field] for field in IDENTITY} for row in rows]
    uids = [r['uid'] for r in rows]
    require(len(uids) == len(set(uids)), 'DUPLICATE_DENSE_UID')
    require(expected_selected_uid_sha256 is None or uid_hash(uids) ==
            expected_selected_uid_sha256, 'FROZEN_DENSE_UIDS_CHANGED')
    groups = defaultdict(list)
    for row in rows:
        require(row['protocol'] in (6, 17) and type(row['frame']) is int and row['frame'] > 0
                and math.isfinite(row['timestamp']), 'DENSE_ROW_IDENTITY')
        legal = [w for w in windows if w['partition'] == row['partition'] and
                 w['device'] == row['device'] and w['source_sha256'] == row['source_sha256']
                 and w['capture_id'] == row['capture_id'] and
                 w['start'] <= row['timestamp'] <= w['end'] and
                 row['frame'] <= w.get('frame_end', row['frame'])]
        require(bool(legal), 'DENSE_ROW_OUTSIDE_WINDOW:' + row['uid'])
        groups[(row['partition'], row['device'], row['protocol'])].append(row)
    signatures = {(p, d): _window_signature(windows, p, d) for p, d, _ in groups}
    table = []
    for (partition, device, protocol), own in sorted(groups.items()):
        available = sorted({d for p, d, proto in groups if p == partition and proto == protocol},
            key=lambda d: (hashlib.sha256((DONOR_SALT + d).encode()).hexdigest(), d))
        start = available.index(device)
        candidates = [available[(start + step) % len(available)]
                      for step in range(1, len(available))]
        candidates = [d for d in candidates if signatures[(partition, d)] == signatures[(partition, device)]]
        item = dict(pool_id=pool_id, partition=partition, device=device, protocol=protocol,
            target_positions=len(own), target_components=len({r['component_id'] for r in own}),
            target_uid_sha256=uid_hash(sorted(r['uid'] for r in own)), window_sha256=signatures[(partition, device)])
        if not candidates:
            item.update(status='NOT_EVALUABLE', reason='NO_OTHER_DEVICE_SAME_PROTOCOL_WINDOW',
                donor_device=None, donor_positions=0, donor_components=0,
                selected_positions=0, selected_components=0, density_ratio=0.0, selected_uids=[])
        else:
            donor = candidates[0]
            donor_rows = groups[(partition, donor, protocol)]
            selected = subsample_dense(donor_rows, len(own), dense_salt)
            item.update(status='EVALUABLE', donor_device=donor,
                donor_positions=len(donor_rows), donor_components=len({r['component_id'] for r in donor_rows}),
                selected_positions=len(selected), selected_components=len({r['component_id'] for r in selected}),
                density_ratio=len(selected) / len(own), selected_uids=[r['uid'] for r in selected])
        item['selected_uid_sha256'] = uid_hash(item['selected_uids'])
        item.update(target_n=item['target_positions'], donor_n=item['donor_positions'],
                    uid_sha256=item['selected_uid_sha256'])
        table.append(item)
    result = dict(schema='dense-reference-wrong-plan-v1', pool_id=pool_id,
        donor_salt=DONOR_SALT, dense_salt=dense_salt, groups=table,
        dense_uid_sha256=uid_hash(uids), label_or_score_selection=False,
        lambda_source='R-DENSE_SOURCE_CAL_SAME_EPSILON',
        comparison_denominator='same query eligible under both own and wrong; no fallback claim')
    result['plan_sha256'] = digest(result)
    return result


def prepare_real(root, output):
    """Freeze local producer identities without opening any feature or score array."""
    root, output = Path(root).resolve(), Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    assets = root / 'runs/diagnostics_d1_d2_v1_20261022/assets'
    prepared = assets / 'heads/run/prepared'
    evaluation = assets / 'onboarding/run/evaluation'
    inventory = root / 'runs/diagnostics_c5_step2_package_v1_20261025/target_inventory'
    cache = root / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022'
    pins = {}
    def pin(path, expected=None, **extra):
        entry = asset(root, path, expected, **extra)
        pins[entry['path']] = entry
        return entry
    def seal(path):
        pin(path)
        return {line.split('  ', 1)[1]: line.split('  ', 1)[0]
                for line in path.read_text().splitlines() if line.strip()}
    prep_seal = seal(prepared / 'SHA256SUMS')
    feature_seal = seal(cache / 'features/SHA256SUMS')
    bank_manifest = json.loads((assets / 'onboarding/run/banks_manifest.json').read_text())
    pin(assets / 'onboarding/run/banks_manifest.json')
    pin(inventory / 'RESULT.json', '428f8e6711d9dbe6616cf540ff15131894997c2ad610a2ba8b99fa21c9a2f43c')
    pin(inventory / 'OUTPUT_SHA256.json', '82a7979e2190c4a5af51f8ce69bf6fa163740623756fcbd9a7c133c8afd8e050')
    inventory_seal = {r['path']: r['sha256'] for r in
                      json.loads((inventory / 'OUTPUT_SHA256.json').read_text())}
    pools, all_pairs = [], {}
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        receipt_path = assets / 'onboarding/run/encoded' / pool / 'B2/receipt.json'
        receipt_entry = pin(receipt_path, bank_manifest['pools'][pool]['B2']['receipt_sha256'])
        receipt = json.loads(receipt_path.read_text())
        query_entry = pin(prepared / (pool + '.jsonl.gz'), prep_seal[pool + '.jsonl.gz'])
        query_rows = read_rows(root / query_entry['path'])
        query_uids = [r['uid'] for r in query_rows]
        require(len(query_uids) == len(set(query_uids)), 'QUERY_UIDS_DUPLICATE')
        uid_path = output / (pool + '_query_uids.json')
        write_json(uid_path, query_uids)
        uid_entry = pin(uid_path)
        b2_rows_entry = pin(receipt_path.parent / 'references.jsonl.gz', receipt['metadata_sha256'])
        b2_array = pin(receipt_path.parent / 'bank.npz', receipt['bank_npz_sha256'])
        b2_rows = read_rows(root / b2_rows_entry['path'])
        plan_path = inventory / pool / 'DENSE_PLAN.json'
        pin(plan_path, inventory_seal[pool + '/DENSE_PLAN.json'])
        plan = json.loads(plan_path.read_text())
        selected_entry = pin(inventory / pool / 'SELECTED_REFERENCES.jsonl.gz',
                             inventory_seal[pool + '/SELECTED_REFERENCES.jsonl.gz'])
        dense_rows = read_rows(root / selected_entry['path'])
        require([r['uid'] for r in dense_rows] == plan['selected_uids'], 'FROZEN_DENSE_ROW_ORDER')
        require(uid_hash(plan['selected_uids']) == plan['selected_uid_sha256'], 'FROZEN_DENSE_PLAN_UID_HASH')
        wrong = freeze_wrong_reference_plan(pool, dense_rows, plan['windows'],
            expected_selected_uid_sha256=plan['selected_uid_sha256'], dense_salt=plan['salt'])
        write_json(output / (pool + '_WRONG_PLAN.json'), wrong)
        wrong_entry = pin(output / (pool + '_WRONG_PLAN.json'))
        pairs = pair_budget(query_rows, b2_rows, dense_rows, wrong)
        all_pairs[pool] = pairs
        saved_score_seal = seal(evaluation / pool / 'B2/SHA256SUMS')
        score_entry = pin(evaluation / pool / 'B2/scores.npz', saved_score_seal['scores.npz'],
                          key='head', uid_key='uid')
        trace_entry = pin(evaluation / pool / 'B2/trace.jsonl.gz', saved_score_seal['trace.jsonl.gz'])
        query = dict(rows=query_entry,
            e3=pin(cache / 'features' / (pool + '.npy'), feature_seal[pool + '.npy'], column_slice=[0, 768]),
            q14=pin(prepared / (pool + '_q.npy'), prep_seal[pool + '_q.npy']),
            logits=score_entry, feature_uids=uid_entry, q_uids=uid_entry,
            feature_uid_sha256=uid_hash(query_uids), q_uid_sha256=uid_hash(query_uids),
            ordered_uid_sha256=uid_hash(query_uids), upstream_uid_binding='pinned cache feature seal and prepared metadata seal; runtime must validate NPZ score uid')
        b2_bank = dict(rows=b2_rows_entry, e3=dict(b2_array, key='e3'), q14=dict(b2_array, key='q14'),
            producer_receipt=receipt_entry, uid_key='uid',
            feature_uid_sha256=uid_hash([r['uid'] for r in b2_rows]), q_uid_sha256=uid_hash([r['uid'] for r in b2_rows]))
        dense_bank = dict(status='BLOCKED_SUPPLEMENT_ENCODING_REQUIRED', rows=selected_entry,
            expected_rows=len(dense_rows), expected_ordered_uid_sha256=uid_hash([r['uid'] for r in dense_rows]),
            e3=None, q14=pin(inventory / pool / 'SELECTED_Q14.npz',
                inventory_seal[pool + '/SELECTED_Q14.npz'], key='q14', uid_key='uid'),
            required_runtime_producer='verified encoding output banks/' + pool + '/bank.npz and receipt.json')
        pools.append(dict(pool_id=pool, mode='DENSE_MATRIX', query=query, b2_bank=b2_bank,
            dense_bank=dense_bank, windows=plan['windows'], wrong_groups=wrong['groups'],
            wrong_plan=wrong_entry, saved_v3_trace=trace_entry,
            query_rows=len(query_rows), b2_rows=len(b2_rows), dense_rows=len(dense_rows),
            new_encoding_positions=len(plan['supplemental_encoding_uids'])))
    # Broader historical and V4 inventory checks: absent is not an empty-window receipt.
    old_base = root / 'runs/onboarding_new_lineage_v1_20261022'
    history_paths = [old_base / 'package_v3/frozen_onboarding/protocol.json',
        old_base / 'package_v3/config.json', old_base / 'package_v3/onboarding_service.py',
        old_base / 'package_v3/constrained_onboarding_runner_v3.py',
        old_base / 'analysis/evidence_v3/run/evaluation/result.json',
        root / 'runs/learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/parent_inventory.json',
        root / 'runs/learned_onboarding_v1_20261023/evaluation_completion_v1_20261025/analysis/completion_review_20261025/ANALYSIS_SUMMARY.json',
        root / 'runs/learned_onboarding_v1_20261023/memory_revision_v4_20261024/deployment_20261024/staging/runs/learned_onboarding_v1_20261023/deployment_20261024/target_manifest_adapter.py']
    evidence = [pin(p) for p in history_paths]
    old_protocol = json.loads(history_paths[0].read_text())
    old_results = json.loads(history_paths[4].read_text())
    parent_inventory = json.loads(history_paths[5].read_text())
    require(THIRD_POOL in old_protocol['evaluation']['required_complete_system_pools'], 'THIRD_POOL_CONTRACT_CHANGED')
    require(all(THIRD_POOL in decision['missing_evidence'] for decision in
                old_results['scientific_decisions'].values()), 'HISTORICAL_THIRD_POOL_STATUS_CHANGED')
    third_members = [key for key in parent_inventory['files'] if THIRD_POOL in key]
    require(not third_members and THIRD_POOL not in bank_manifest['pools'], 'THIRD_POOL_NEW_EVIDENCE_REQUIRES_REVIEW')
    third = dict(pool_id=THIRD_POOL, **third_pool_mode(), windows=None,
        query=None, b2_bank=None, dense_bank=None, wrong_groups=[],
        historical_status=old_protocol['evaluation']['three_device_status'],
        V4_inventory_matching_members=third_members, evidence=evidence,
        no_new_window_or_BASE_or_bank_created=True)
    pools.append(third)
    calibration = {name: pin(evaluation / 'calibration' / (name + '.json'))
                   for name in ('geometry', 'cuts', 'scales', 'protection')}
    calibration['normalizer'] = pin(prepared / 'normalizer.npz', prep_seal['normalizer.npz'])
    result = dict(schema='dense-reference-matrix-input-v1',
        status='METADATA_PREPARATION_COMPLETE_PRODUCTION_BLOCKED', root=root.as_posix(),
        supplement_encoding_complete=False, dense_source_cal_complete=False,
        full_matrix_ready=False, blockers=['SUPPLEMENT_E3_AND_ORIGINAL104_BYTE_GATE_PENDING',
            'TRUE_DENSE_SOURCE_CAL_PENDING', 'FROZEN_THIRD_POOL_BASE_B2_ASSETS_ABSENT'],
        calibration=calibration, source_cal_result=None, source_preparations=None,
        pools=pools, target_logits_loaded=False, E3_forwards=0, training_runs=0,
        target_evaluations=0, distances_computed=0)
    write_json(output / 'bindings.json', result)
    budget = dict(schema='dense-reference-pair-budget-v1', pools=all_pairs,
        AB_total_distance_pairs=sum(p['total_distance_pairs'] for p in all_pairs.values()),
        third_pool_distance_pairs=None, third_pool_status=third['mode'],
        new_encoding_positions={'SOURCE_REFS': 4624, 'CIC_DEV': 5237, 'UNSW_DEV': 11799,
                                THIRD_POOL: None},
        distance_work_not_multiplied_by_seed_or_epsilon=True,
        throughput='NOT_MEASURED_NEEDS_SAME_KERNEL_BENCHMARK', runtime_estimate=None,
        target_scores_or_labels_used_for_donor_selection=False)
    write_json(output / 'PAIR_BUDGET.json', budget)
    pins[asset(root, output / 'bindings.json')['path']] = asset(root, output / 'bindings.json')
    pins[asset(root, output / 'PAIR_BUDGET.json')['path']] = asset(root, output / 'PAIR_BUDGET.json')
    write_json(output / 'INPUT_OUTPUT_PINS.json', dict(schema='dense-reference-metadata-pins-v1',
        assets=pins, all_hashes_actually_read=True))
    return result, budget


def verify_wrong_plan(plan, pool_id, rows, windows):
    require(plan == freeze_wrong_reference_plan(pool_id, rows, windows,
        expected_selected_uid_sha256=plan['dense_uid_sha256'], dense_salt=plan['dense_salt']),
        'WRONG_PLAN_CHANGED')


def third_pool_mode(*, base=None, b2_bank=None, receipt=None):
    if not base or not b2_bank or not receipt:
        return dict(mode='BLOCKED_MISSING_FROZEN_BASE_B2',
            reason='Frozen BASE, B2 metadata/features and producer receipt are all prerequisites',
            new_encoding_positions=None, dense_arms='BLOCKED', b2_arm='BLOCKED')
    fields = ('t0', 'cutoff', 'source_sha256', 'cutoff_frame')
    explicit = all(key in receipt for key in fields)
    require(explicit or not any(key in receipt for key in ('t0', 'cutoff', 'cutoff_frame')),
            'THIRD_POOL_PARTIAL_WINDOW_RECEIPT')
    if not explicit:
        return dict(mode='B2_REGRESSION_ONLY', reason='FROZEN_RECEIPT_HAS_NO_COMMISSIONING_WINDOW',
            new_encoding_positions=0, dense_arms='NOT_APPLICABLE', b2_arm='APPLICABLE')
    require(receipt['t0'] <= receipt['cutoff'] and receipt['cutoff_frame'] > 0,
            'THIRD_POOL_INVALID_FROZEN_WINDOW')
    return dict(mode='DENSE_MATRIX', reason='FROZEN_RECEIPT_DEFINES_COMMISSIONING_WINDOW',
        new_encoding_positions='REQUIRES_EXACT_ENUMERATION', dense_arms='PENDING_ENUMERATION', b2_arm='APPLICABLE')


def require_full_matrix(bindings):
    pools = {p['pool_id']: p for p in bindings['pools']}
    require(set(pools) == {'CIC_DEV', 'UNSW_DEV', THIRD_POOL}, 'THREE_REGISTERED_POOLS_REQUIRED')
    require(not any(p['mode'].startswith('BLOCKED') for p in pools.values()),
            'FROZEN_THIRD_POOL_INPUTS_MISSING')
    require(bindings.get('supplement_encoding_complete') is True and
            bindings.get('dense_source_cal_complete') is True, 'ENCODING_AND_DENSE_CAL_REQUIRED')


def pair_budget(query_rows, b2_rows, dense_rows, wrong_plan):
    """Exact timestamp/frame/component-ready pair counts, without labels."""
    result = {}
    groups = defaultdict(list)
    for row in dense_rows:
        groups[(row['partition'], row['device'], row['protocol'])].append(row)
    for arm, refs in (('R-B2', b2_rows), ('R-DENSE', dense_rows)):
        own = defaultdict(list)
        for row in refs:
            own[(row['partition'], row['device'], row['protocol'])].append(row)
        table = []
        for key, rr in sorted(own.items()):
            end = {r['reference_end'] for r in rr}
            require(len(end) == 1, 'REFERENCE_CUTOFF_DRIFT')
            end = next(iter(end))
            frames = {r['capture_id']: r['bank_end_frame'] for r in rr if 'bank_end_frame' in r}
            ready = sum((r['partition'], r['device'], r['protocol']) == key and
                        r['timestamp'] > end and r['frame'] > frames.get(r['capture_id'], -1)
                        for r in query_rows)
            comp = len({r['component_id'] for r in rr})
            table.append(dict(partition=key[0], device=key[1], protocol=key[2],
                positions=len(rr), components=comp, ready_queries=ready,
                distance_pairs=ready * len(rr) if comp >= 2 else 0))
        result[arm] = dict(groups=table, distance_pairs=sum(g['distance_pairs'] for g in table))
    own_counts = {(r['partition'], r['device'], r['protocol']): r
                  for r in result['R-DENSE']['groups']}
    table = []
    for group in wrong_plan['groups']:
        key = group['partition'], group['device'], group['protocol']
        ready = own_counts[key]['ready_queries']
        eligible = group['status'] == 'EVALUABLE' and group['selected_components'] >= 2
        table.append(dict(partition=key[0], device=key[1], protocol=key[2],
            donor_device=group['donor_device'], ready_queries=ready,
            selected_positions=group['selected_positions'], selected_components=group['selected_components'],
            distance_pairs=ready * group['selected_positions'] if eligible else 0,
            eligible_geometry_queries=ready if eligible else 0,
            paired_eligible_queries=ready if eligible and own_counts[key]['components'] >= 2 else 0))
    result['R-DENSE-WRONG'] = dict(groups=table, distance_pairs=sum(g['distance_pairs'] for g in table))
    result['total_distance_pairs'] = sum(result[a]['distance_pairs'] for a in ('R-B2', 'R-DENSE', 'R-DENSE-WRONG'))
    result['support_reused_across_epsilon_and_seed'] = True
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepared, budget = prepare_real(args.root, args.output)
    print(json.dumps(dict(status=prepared['status'], blockers=prepared['blockers'],
                         AB_total_distance_pairs=budget['AB_total_distance_pairs'])))
