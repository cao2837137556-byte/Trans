"""D3: audit saved scores, weights, metadata and D2 traces; no new distances.

Writes only to this audit directory. Does not read E3 arrays, decode raw packets,
fit a model, select new reference points, or evaluate an actual C3 candidate.
"""
from collections import Counter, defaultdict
from fractions import Fraction
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
C2 = ROOT / 'runs/history_normal_reference_c2_syn_guard_v1_20261031'
D2 = ROOT / 'runs/history_normal_reference_d2_trace_v1_20261031'
POWER = 'unsw-attack-traces-2018:ec:1a:59:79:f4:89'
PINS = {}


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def pin(path, expected=None):
    path = Path(path).resolve()
    assert path.is_relative_to(ROOT)
    value = sha(path)
    if expected is not None:
        assert value == expected, str(path)
    key = path.relative_to(ROOT).as_posix()
    assert key not in PINS or PINS[key] == value
    PINS[key] = value
    return path


def read(path, expected=None):
    return json.loads(pin(path, expected).read_text(encoding='utf-8-sig'))


def gzrows(path, expected=None):
    with gzip.open(pin(path, expected), 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def asset_path(item):
    path = pin(ROOT / item['path'], item['sha256'])
    assert path.stat().st_size == item['bytes']
    return path


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, pin(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def quantiles(values):
    values = list(values)
    return dict(zip(('min', 'p25', 'p50', 'p75', 'max'),
                    np.quantile(values, [0, .25, .5, .75, 1]).tolist())) if values else None


def fraction(value):
    return dict(exact=str(value), value=float(value))


def flags(q):
    return sum(1 << b for b in range(9) if q[b + 1] == 1)


def exact_weights(rows, pool, metrics):
    """Reconstruct integer hierarchy denominators, rather than rationalizing floats."""
    output = [Fraction(0)] * len(rows)
    for label in (0, 1):
        fields = metrics.hierarchy_fields(pool, label)
        keys = {i: tuple(str(row[f]) for f in fields) for i, row in enumerate(rows)
                if row['label'] == label}
        branches, leaves = defaultdict(set), Counter(keys.values())
        for key in keys.values():
            for depth in range(len(fields)):
                branches[key[:depth]].add(key[depth])
        for i, key in keys.items():
            output[i] = Fraction(1, leaves[key] * math.prod(
                len(branches[key[:d]]) for d in range(len(fields))))
        assert not keys or sum(output[i] for i in keys) == 1
    assert np.array_equal(np.array(list(map(float, output))), metrics.hierarchical_weights(rows, pool))
    return output


def heim_audit(rows, q, saved, weights):
    ix = [i for i, r in enumerate(rows) if r['device'] == 'HeimVision Camera' and r['label'] == 0]
    mass = sum(weights[i] for i in ix)
    fp = [i for i in ix if saved['corrected'][i, 3]]
    tcp = [i for i in fp if rows[i]['protocol'] == 6]
    udp = [i for i in fp if rows[i]['protocol'] == 17]
    assert len(ix) == 672 and len(fp) == 52 and len(tcp) == 42 and len(udp) == 10
    rate = sum(weights[i] for i in fp) / mass
    required = rate - Fraction(1, 50)
    tcp_weights = [weights[i] / mass for i in tcp]
    bounds = {}
    for order, descending in [('largest_weights_first', True), ('smallest_weights_first', False)]:
        ordered = sorted(tcp_weights, reverse=descending)
        rates = [rate - sum(ordered[:n]) for n in range(len(ordered) + 1)]
        first = next(n for n, value in enumerate(rates) if value <= Fraction(1, 50))
        bounds[order] = dict(minimum_count=first, previous_fpr=fraction(rates[first - 1]),
                             first_passing_fpr=fraction(rates[first]),
                             fpr_after_37=fraction(rates[37]))
    captures = {}
    for capture in sorted({rows[i]['capture_id'] for i in ix}):
        group = [i for i in ix if rows[i]['capture_id'] == capture]
        group_mass = sum(weights[i] for i in group)
        captures[capture] = dict(rows=len(group), sessions=len({rows[i]['session_id'] for i in group}),
            timestamp_min=min(rows[i]['timestamp'] for i in group),
            timestamp_max=max(rows[i]['timestamp'] for i in group),
            fp=sum(bool(saved['corrected'][i, 3]) for i in group),
            conditional_fpr=fraction(sum(weights[i] for i in group if saved['corrected'][i, 3]) / group_mass))
    return dict(normal_rows=len(ix), fp_rows=len(fp), tcp_fp_rows=len(tcp), udp_fp_rows=len(udp),
        normal_mass=fraction(mass), weighted_fpr=fraction(rate),
        unweighted_fpr=fraction(Fraction(len(fp), len(ix))),
        tcp_fp_weight=fraction(sum(tcp_weights)), udp_fp_weight=fraction(sum(weights[i] for i in udp) / mass),
        required_tcp_removed_weight_for_device_fpr_le_2pct=fraction(required),
        tcp_fp_conditional_weight_histogram=dict(Counter(map(str, tcp_weights))),
        counting_bounds=bounds, captures=captures,
        unique_sessions=len({rows[i]['session_id'] for i in ix}),
        tcp_rows=[dict(uid=rows[i]['uid'], capture=rows[i]['capture_id'], session=rows[i]['session_id'],
                      conditional_weight=fraction(weights[i] / mass), flags=flags(q[i]),
                      saved_support=float(saved['support'][i])) for i in tcp],
        assumptions='Ten UDP alarms unchanged; no newly added alarms; row counts are bounds, not a selection rule.',
        uncertainty='No IID or weighted confidence interval estimated. Captures/sessions are dependent candidates for clustering, not proven independent units.')


def power_bound(rows, saved, weights, core, scales, cut):
    ix = np.array([i for i, r in enumerate(rows) if r['device'] == POWER and r['label'] == 0], dtype=np.int64)
    mass = math.fsum(weights[ix])
    raw = saved['raw_logits'][ix]
    guard = saved['guard'][ix]
    # An optimistic arithmetic ceiling, not distances or actual candidate scores.
    ideal = core.apply_correction(raw, np.ones(len(ix)), scales, .25)
    ideal[guard] = raw[guard]
    still_fp = core.ordered_ensemble(ideal) > cut
    current_fp = saved['corrected'][ix, 3]
    assert not np.any(still_fp & ~current_fp)
    needed = (core.ordered_ensemble(raw) - cut) / (.25 * np.mean(scales['scales']))
    by_protocol = {}
    for protocol in sorted({rows[i]['protocol'] for i in ix}):
        mask = np.array([rows[i]['protocol'] == protocol for i in ix])
        by_protocol[str(protocol)] = dict(normal_rows=int(mask.sum()), fp_rows=int((mask & current_fp).sum()),
            support_one_still_fp=int((mask & still_fp).sum()),
            weighted_fp_contribution_to_device=math.fsum(weights[ix[mask & current_fp]]) / mass,
            weighted_floor_contribution_to_device=math.fsum(weights[ix[mask & still_fp]]) / mass)
    return dict(normal_rows=len(ix), residual_fp_rows=int(current_fp.sum()),
        guarded_residual_rows=int((guard & current_fp).sum()),
        zero_support_residual_rows=int(((saved['support'][ix] == 0) & current_fp).sum()),
        weighted_fpr=math.fsum(weights[ix[current_fp]]) / mass,
        support_one_still_fp_rows=int(still_fp.sum()),
        amplitude_clearable_residual_rows=int((current_fp & ~still_fp).sum()),
        optimistic_fpr_floor_with_C2_guard=math.fsum(weights[ix[still_fp]]) / mass,
        residual_support=quantiles(saved['support'][ix[current_fp]]),
        residual_required_support_algebraic=quantiles(needed[current_fp]), by_protocol=by_protocol,
        note='Algebraic required support is descriptive; support=1 verdict uses frozen apply_correction/ordered_ensemble strict > arithmetic. This ignores attainable neighbors and protection of attacks.')


def power_traces(traces, refs, refq, lookup, rows, q, saved, core, scales, cut):
    by_component, by_uid = defaultdict(list), {}
    for row, qr in zip(refs, refq):
        assert row['uid'] not in by_uid
        by_uid[row['uid']] = (row, qr)
        by_component[row['component_id']].append((float(row['timestamp']), flags(qr), int(qr[13])))
    groups = {}
    for cohort in ['P4_WEMO_POWER_RESIDUAL', 'P4_WEMO_POWER_RESCUED']:
        rr = [r for r in traces if r['cohort'] == cohort]
        assert len(rr) == 1024
        values = defaultdict(list)
        counts = Counter()
        flag_counts, sources = Counter(), Counter()
        for r in rr:
            i = lookup[r['query']['uid']]
            assert rows[i]['device'] == POWER and rows[i]['label'] == 0
            assert np.array_equal(q[i], r['query_q14'])
            assert np.array_equal(saved['raw_logits'][i], r['raw_logits'])
            assert np.array_equal(saved['corrected'][i], r['corrected'])
            assert abs(saved['support'][i] - r['trace']['support']) < 1e-12
            assert bool(saved['corrected'][i, 3]) == (cohort == 'P4_WEMO_POWER_RESIDUAL')
            assert not saved['guard'][i]
            pair = r['neighbors']
            assert len(pair) == 2
            counts['same_component_between_two_neighbors'] += pair[0]['reference']['component_id'] == pair[1]['reference']['component_id']
            z = max(n['dz_over_rho'] for n in pair)
            dq = max(n['dq_over_rho'] for n in pair)
            counts['pair_limiter_z_ge_q'] += z >= dq
            counts['pair_limiter_q_gt_z'] += dq > z
            counts['pair_z_radius_blocked'] += z >= 1
            counts['pair_q_radius_blocked'] += dq >= 1
            values['pair_max_z_ratio'].append(z)
            values['pair_max_q_ratio'].append(dq)
            values['support'].append(saved['support'][i])
            values['neighbor_pair_time_gap_days'].append(abs(pair[0]['reference']['timestamp'] - pair[1]['reference']['timestamp']) / 86400)
            flag = flags(q[i])
            flag_counts[str(flag)] += 1
            counts['both_neighbor_flags_equal_query'] += all(flags(n['q14']) == flag for n in pair)
            counts['both_neighbor_flags_and_context_direction_equal_query'] += all(flags(n['q14']) == flag and n['q14'][13] == q[i, 13] for n in pair)
            own = by_component.get(rows[i]['component_id'], [])
            assert bool(own) == r['trace']['same_component']
            counts['query_component_present_in_reference_bank'] += bool(own)
            if own:
                values['query_component_nearest_saved_timestamp_gap_days'].append(min(abs(rows[i]['timestamp'] - t) for t, _, _ in own) / 86400)
                counts['query_component_contains_query_flags'] += any(f == flag for _, f, _ in own)
            for rank, n in enumerate(pair):
                ref, qr = by_uid[n['reference']['uid']]
                assert ref['component_id'] == n['reference']['component_id'] and ref['timestamp'] == n['reference']['timestamp']
                assert np.array_equal(qr, n['q14'])
                sources[n['source']] += 1
                component = by_component[ref['component_id']]
                values['matched_component_selected_point_count'].append(len(component))
                values['matched_component_time_span_days'].append((max(t for t, _, _ in component) - min(t for t, _, _ in component)) / 86400)
                values['matched_component_nearest_saved_timestamp_gap_days'].append(min(abs(rows[i]['timestamp'] - t) for t, _, _ in component) / 86400)
                counts['matched_component_contains_query_flags'] += any(f == flag for _, f, _ in component)
                counts['matched_component_contains_query_flags_and_context_direction'] += any(f == flag and d == q[i, 13] for _, f, d in component)
                values[f'neighbor_{rank + 1}_z_ratio'].append(n['dz_over_rho'])
                values[f'neighbor_{rank + 1}_q_ratio'].append(n['dq_over_rho'])
                values['matched_query_minus_reference_days'].append(n['query_minus_reference_seconds'] / 86400)
        indices = np.array([lookup[r['query']['uid']] for r in rr])
        raw = saved['raw_logits'][indices]
        ideal = core.apply_correction(raw, np.ones(len(indices)), scales, .25)
        floor_fp = core.ordered_ensemble(ideal) > cut
        need = (core.ordered_ensemble(raw) - cut) / (.25 * np.mean(scales['scales']))
        counts['support_one_still_fp'] = int(floor_fp.sum())
        counts['support_one_not_fp'] = int((~floor_fp).sum())
        counts['guarded_queries'] = int(saved['guard'][indices].sum())
        values['required_support_algebraic'] = need
        values['required_minus_current_support_algebraic'] = need - saved['support'][indices]
        groups[cohort] = dict(rows=len(rr), counts=dict(counts),
            query_flags=dict(flag_counts), neighbor_sources=dict(sources),
            quantiles={k: quantiles(v) for k, v in values.items()},
            uid_sha256=core._uid_hash([r['query']['uid'] for r in rr]))
    return groups


def main():
    started = time.perf_counter()
    review = ROOT / 'runs/mainline_docs/collab/20261031_history_normal_reference_c2_review_and_c3_contract_antigravity.md'
    pin(review, '8cc5aeb3bd23a2993bc7d83ae408c19103147ce961d03749c69b5b0726e38449')
    pin(Path(__file__))
    sys.path.insert(0, str(ROOT / 'repo/ood'))
    import constrained_onboarding_core_v3 as core
    pin(core.__file__)
    metrics = module('d3_original_metrics', ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py')
    assets = read(ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031/config/ASSETS.json')
    scales, cuts = (read(asset_path(assets['calibration'][k])) for k in ('scales', 'cuts'))
    c2result = read(C2 / 'output/RESULT.json', '092ff373b6231b52969d59aa54f84b976ab8ef3facb1c0a3bd67c891cfc722e8')
    assert read(C2 / 'FINAL_ACCEPTANCE.json', '8528bba55bdc0ef2c7571e9c409742a67566ed10fa2b3550f158e8a0248f503d')['status'] == 'PASS'
    artifacts = read(C2 / 'output/ARTIFACTS.json')
    d2pins = read(D2 / 'EVIDENCE_SHA256.json')
    traces = gzrows(D2 / 'output/NEIGHBORS.jsonl.gz', d2pins['output/NEIGHBORS.jsonl.gz'])
    output = dict(schema='history-normal-reference-d3-readonly-v1', evidence='CONSUMED_DEVELOPMENT_ONLY',
        operation='Saved-score arithmetic and saved-neighbor description only',
        raw_decodes=0, model_forwards=0, E3_arrays_loaded=0, new_distance_pairs=0,
        new_reference_selections=0, actual_C3_evaluations=0, remote_operations=0,
        interval_estimates=0, lambda_value=.25, quantile_order=['min', 'p25', 'p50', 'p75', 'max'])
    for pool, item in assets['pools'].items():
        full = gzrows(asset_path(item['query']['rows']))
        with np.load(pin(C2 / f'output/ab/{pool}/DECISIONS.npz', artifacts[f'ab/{pool}/DECISIONS.npz']['sha256']), allow_pickle=False) as z:
            saved = {k: z[k] for k in z.files}
        assert saved['uid'].tolist() == [r['uid'] for r in full]
        assert float(saved['selected_lambda']) == .25
        q = np.load(asset_path(item['query']['q14']), allow_pickle=False)
        assert q.shape == (len(full), 14)
        assert np.array_equal(saved['guard'], (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0))
        assert np.array_equal(saved['corrected'][:, 3], core.ordered_ensemble(saved['corrected_logits']) > cuts['ensemble_cut'])
        metrics.validate_full_weights(full, pool)
        ix = np.flatnonzero(metrics.post_window_mask(full, item['windows']))
        rows = [full[i] for i in ix]
        weights = metrics.hierarchical_weights(rows, pool)
        view = c2result['pools'][pool]['views']['post_window_primary']
        assert core._uid_hash([r['uid'] for r in rows]) == view['retained_uid_sha256']
        assert sha_bytes(weights.tobytes()) == view['weights_sha256']
        primary = {k: v[ix] for k, v in saved.items() if np.ndim(v) > 0}
        if pool == 'CIC_DEV':
            output['heim'] = heim_audit(rows, q[ix], primary, exact_weights(rows, pool, metrics))
        else:
            output['power_all_primary_normals'] = power_bound(rows, primary, weights, core, scales, cuts['ensemble_cut'])
            refs, refq = [], []
            for meta, npz, expected_meta, expected_npz in [
                (D2 / 'retrieved/history/WEMO_POWER/encoded/references.jsonl.gz', D2 / 'retrieved/history/WEMO_POWER/encoded/references.npz',
                 d2pins['retrieved/history/WEMO_POWER/encoded/references.jsonl.gz'], d2pins['retrieved/history/WEMO_POWER/encoded/references.npz']),
                (ROOT / item['dense_bank']['rows']['path'], ROOT / item['dense_bank']['q14']['path'],
                 item['dense_bank']['rows']['sha256'], item['dense_bank']['q14']['sha256'])]:
                rr = gzrows(meta, expected_meta)
                # NPZ is lazy: read uid/q14 only; deliberately do not access e3.
                with np.load(pin(npz, expected_npz), allow_pickle=False) as z:
                    ids, qq = z['uid'].tolist(), z['q14']
                assert ids == [r['uid'] for r in rr]
                for row, descriptor in zip(rr, qq):
                    if row['device'] == POWER:
                        refs.append(row)
                        refq.append(descriptor)
            output['power_saved_trace_cohorts'] = power_traces(traces, refs, refq,
                {r['uid']: i for i, r in enumerate(rows)}, rows, q[ix], primary, core, scales, cuts['ensemble_cut'])
    pre = read(C2 / 'output/source/G1/S/PRECHECK.json', artifacts['source/G1/S/PRECHECK.json']['sha256'])
    cmp = pre['comparisons']['C']['own']['ensemble']
    output['source_G1_S_C_own'] = dict(normal_rows=cmp['after']['normal_count'],
        normal_guard_rows=pre['normal_guard_rows'], before=cmp['before'], after=cmp['after'],
        returned_normal_alarm_count=cmp['returned_normal_alarm_count'], devices=cmp['groups']['device'],
        limitation='SYN without ACK on current query is verified; retransmission/repeated-flow behavior is not established by these arrays.')
    output['B_admitted_HIST_REF_census'] = {}
    for member in ('TP_LINK', 'SAMSUNG', 'WEMO_POWER'):
        name = f'retrieved/history/{member}/selection/SELECTION.json'
        selected = read(D2 / name, d2pins[name])
        output['B_admitted_HIST_REF_census'][member] = [
            {k: g[k] for k in ('protocol', 'candidate_rows', 'candidate_components', 'selected_rows', 'cap')}
            for g in selected['groups'] if g['role'] == 'HIST_REF']
    output['scope_notes'] = [
        'Power trace cohorts are two deterministic 1024-row samples, not the whole residual/rescued population.',
        'Temporal nearest means nearest saved timestamp in a named component, not a new feature-space search.',
        'A missing query component is not a violation: original rule uses two legal distinct reference components.',
        'Positive support and matching TCP flags do not establish full behavioral coverage.',
        'Long historical time gaps do not by themselves establish temporal sparsity or causality.',
        'No A/B-based choice of reference points, K, lambda or endpoints was performed.']
    for path, expected in PINS.items():
        assert sha(ROOT / path) == expected, path
    output['inputs_unchanged'] = True
    output['input_sha256'] = PINS
    output['elapsed_seconds'] = time.perf_counter() - started
    output['status'] = 'READ_ONLY_DIAGNOSTIC_COMPLETE_C3_NOT_RUN'
    destination = HERE / 'D3_EVIDENCE.json'
    with destination.open('x', encoding='utf-8') as stream:
        json.dump(output, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    for path in (Path(__file__), destination):
        path.with_name(path.name + '.sha256').write_text(sha(path) + '  ' + path.name + '\n', encoding='utf-8')
    print(json.dumps(dict(status=output['status'], seconds=output['elapsed_seconds'],
                         pinned_inputs=len(PINS), power=output['power_all_primary_normals']), ensure_ascii=False))


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


if __name__ == '__main__':
    main()
