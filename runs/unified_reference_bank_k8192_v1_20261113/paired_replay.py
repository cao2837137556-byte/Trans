"""One paired replay against the accepted P4_MAIN decisions."""
from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from time import monotonic

import numpy as np

import analysis_core as metrics_core
from common_round1 import read_rows, table, uid_sha, write_rows
from evaluation import baseline_parity, by_protocol, load_query
from frozen_selector import need, physical
from reference_assets import bank as accepted_bank
from reference_inputs import normalized_context
from replay_geometry import joint3, plan_queries, radii, replay
from runtime_support import HERE, POOLS, asset, digest, read, write
from vendor import constrained_onboarding_core_v3 as core, geometry_frozen, p4_worker
from zero_degradation import paired_cell

TOL = 2e-10
CANDIDATE = 'P4_UNIFIED_HIST_K8192_V1'


def ref_bank(rows, z, q, norm):
    ids = [r['uid'] for r in rows]
    return core.ReferenceBank(rows, z, q, norm, feature_uids=ids, q_uids=ids,
                              allow_prebank_history=True)


def effective_history(history, window_rows):
    windows = {(r['partition'], r['device']): r for r in window_rows}
    return [dict(r, reference_end=windows[r['partition'], r['device']]['reference_end'],
                 historical_reference_end=r['reference_end'],
                 historical_bank_end_frame=r['bank_end_frame']) for r in history]


def source_key(row):
    if 'origin_raw_sha256' in row:
        return physical(row)
    return row['source_sha256'], row['frame'], row['owner']


def isolation(history, dense, queries, pool, source_config, *, probe):
    from itertools import chain
    used_keys = {source_key(r) for r in chain(dense,queries)}
    used_uids = {r['uid'] for r in chain(dense,queries)}
    times = {}
    for row in queries:
        k = row['device']
        times[k] = min(times.get(k, float('inf')), row['timestamp'])
    for row in history:
        need(source_key(row) not in used_keys and row['uid'] not in used_uids, 'CROSS_ROLE_PHYSICAL_ENDPOINT')
        need(row['reference_end'] < times[row['device']], 'HISTORY_PRECEDES_DEVICE_QUERY')
    if pool == 'CIC_DEV':
        for spec in source_config['short']:
            need(spec['first_query_us'] / 10**6 <= times[spec['device']],
                 'CIC_FROZEN_EARLIEST_QUERY_TIME')


def load_features(store, pool, rows, q, context_norm):
    with np.load(store.get(pool+':query_context_uids'), allow_pickle=False) as a:
        need(a['uid'].tolist() == [r['uid'] for r in rows], 'QUERY_CONTEXT_UID_BINDING')
    z = np.load(store.get(pool+':query_e3'), mmap_mode='r', allow_pickle=False)[:, :768]
    own_q = np.load(store.get(pool+':query_q'), mmap_mode='r', allow_pickle=False)
    x = np.load(store.get(pool+':query_context'), mmap_mode='r', allow_pickle=False)
    need(np.array_equal(own_q, q) and z.shape == (len(rows),768) and x.shape == (len(rows),8),
         'FROZEN_QUERY_FEATURE_BINDING')
    return z, normalized_context(x, context_norm)


def direct_oracle(d, bank, context, geom, geo):
    ids = [r['uid'] for r in d['rows']]
    old = bank.own(d['rows'], d['z'], d['q'], geom['geometry'], feature_uids=ids, q_uids=ids)
    need(np.array_equal(old['legal_component_count'], geo['legal_component_count']) and
         np.max(np.abs(old['support']-geo['support2']), initial=0) <= TOL,
         'REFERENCE_SLICE_SUPPORT2_ORACLE')
    p3 = np.zeros(len(ids))
    for i, row in enumerate(d['rows']):
        zq, rho = radii(geom, row['protocol'])
        if not old['eligible'][i] or old['support'][i] == 0 or rho is None:
            continue
        key = row['partition'], row['device'], row['protocol']
        ix = np.asarray([j for j in bank.groups[key] if
            bank.rows[j]['capture_id'] != row['capture_id'] or bank.rows[j]['frame'] < row['frame']])
        z = core._unit(d['z'][i:i+1], bank.normalizer)
        dz = np.clip(1.-z @ bank.z[ix].T, 0., 2.)
        dq = geometry_frozen.rms(d['q'][i:i+1], bank.q14[ix])
        dc = geometry_frozen.rms(d['context'][i:i+1], context[ix])
        d2 = np.maximum(core._ratio(dz, zq[0]), core._ratio(dq, zq[1]))
        comp = [bank.rows[j]['component_id'] for j in ix]
        second, _ = core._second_distinct(joint3(d2, dc, rho), comp)
        p3[i] = np.clip(1.-second[0], 0., 1.)
    old_score = correct(d['raw'], p3, d['q'], geom['method'])
    new_score = correct(d['raw'], geo['support3'], d['q'], geom['method'])
    cuts = np.asarray(geom['method']['cuts'])
    error = float(np.max(np.abs(p3-geo['support3']), initial=0))
    need(error <= TOL and np.array_equal(old_score > cuts, new_score > cuts),
         'REFERENCE_SLICE_SUPPORT3_ORACLE')
    return dict(max_support3_difference=error, decision_differences=0,
                distance_rows=int(np.count_nonzero(geo['legal_component_count'] >= 2)))


def correct(raw, support, q, method):
    return p4_worker.correct(raw, support, q, method['scales'], True, power=method['p'])


def split(d, indices):
    return dict(rows=[d['rows'][i] for i in indices], **{
        k: d[k][indices] for k in ('raw', 'z', 'q', 'context')})


def probe_indices(d, bank, geom):
    plans, flags = plan_queries(bank, d['rows'], geom)
    keep = set(np.flatnonzero(flags['opening'] != '')[:8].tolist())
    for patterns in plans.values():
        for members in patterns.values():
            keep.update(members[i] for i in np.linspace(0, len(members)-1, min(8,len(members)), dtype=int))
    need(keep, 'NO_REAL_QUERY_SLICE')
    return np.array(sorted(keep))


def exact_gate(rows, views, groups, old, new, pool):
    output = []
    for view, (ix, weight) in views.items():
        for group in ('NORMAL', 'ATTACK', *sorted(g for g in groups if g.startswith('device:'))):
            device_group = group.startswith('device:')
            if device_group and view == 'full' and pool != 'EDGE':
                continue
            if group == 'NORMAL':
                members = ix[np.asarray([rows[i]['label'] == 0 for i in ix])]
            elif group == 'ATTACK':
                members = ix[np.asarray([rows[i]['label'] == 1 for i in ix])]
            else:
                members = ix[groups[group][ix]]
            for i, head in enumerate(metrics_core.HEADS):
                value = paired_cell(old[members,i], new[members,i], weight[members],
                                    attack=group.endswith('ATTACK'))
                output.append(dict(pool=pool, view=view, group=group, head=head, **value))
    return output


def edge_identity(old, new, lhs, rhs, population):
    need(np.array_equal(old,new), 'EDGE_ALL_QUERY_DECISIONS')
    need(population == {'NORMAL': 1220126, 'HTTP': 152352, 'UDP': 2898830}, 'EDGE_HT_POPULATION')
    def groups(rows):
        return [r for r in rows if r['group'] in population and r['guard_stratum'] == 'ALL']
    a, b = groups(lhs), groups(rhs)
    need(len(a) == len(b) == 12 and a == b and
         all(x['HT_denominator'] == population[x['group']] for x in a), 'EDGE_HT_METRIC_PARITY')
    return dict(status='PASS', decisions=len(old)*4, groups=a, history=0)


def run(store, candidate, target, cfg, geom, progress, *, probe, sizing_only=False):
    manifest = read(candidate/'CANDIDATE.json')
    expected_state = 'PROBE_FEATURES_SEALED' if probe else 'CANDIDATE_SEALED'
    need(manifest['status'] == expected_state and
         digest(candidate/'SELECTION.json') == manifest['selection']['sha256'], 'SELECTION_SEAL')
    sealed = read(candidate/'SELECTION.json')
    need(sealed['query_access'] is False and sealed['cap'] == 8192, 'NO_QUERY_ACCESS_BEFORE_SEAL')
    expected = read(HERE/'EXPECTED_BASELINE.json')
    source_cfg = read(HERE/'REFERENCE_SOURCES.json')
    with np.load(store.get('e3_normalizer'), allow_pickle=False) as a:
        norm = core._normalizer((a['mean'], a['scale']))
    with np.load(store.get('context_normalizer'), allow_pickle=False) as a:
        context_norm = a['mean'], a['scale']
    cuts = np.asarray(cfg['method']['cuts'])
    metrics, pairs, gates, result = [], [], [], {}
    for pool in POOLS:
        with progress.measure('EVALUATION_INPUTS_'+pool):
            rows, z, q, x = accepted_bank(store, cfg, pool, progress)
            qr, ids, raw, p4, q14, active, views, expansion, pop = load_query(store, cfg, pool, rows)
            with np.load(store.get(pool+':query_array'), allow_pickle=False) as a:
                old_s3 = a['support3']
            need(old_s3.dtype == np.float64 and old_s3.shape == (len(qr),) and
                 np.all((old_s3 >= 0) & (old_s3 <= 1)) and not np.any(old_s3[~active]),
                 'ACCEPTED_SUPPORT3_RANGE')
            recalculated = correct(raw, old_s3, q14, cfg['method'])
            old = p4 > cuts
            need(np.max(np.abs(recalculated-p4), initial=0) <= TOL and
                 np.array_equal(recalculated > cuts, old), 'FROZEN_P4_SCORE_DECISION_REPRODUCTION')
            lhs = metrics_core.metrics(pool, qr, old, views, q14, expansion, pop)
            raw_metrics = metrics_core.metrics(pool, qr, raw > cuts, views, q14, expansion, pop)
            baseline_n = baseline_parity([dict(config='RAW', **r) for r in raw_metrics] +
                    [dict(config='P4_MAIN', **r) for r in lhs], expected, pool)
        if pool == 'EDGE':
            need(len(rows) == 4124 and sealed['EDGE']['added_historical'] == 0, 'EDGE_SAME_BANK')
            ref_identity = dict(uid_sha256=uid_sha([r['uid'] for r in rows]),
                 features={k:sha256(np.ascontiguousarray(v).tobytes()).hexdigest()
                           for k,v in (('e3', z), ('q14', q), ('context8', x))})
            need(np.array_equal(p4,recalculated), 'EDGE_FROZEN_SCORE_IDENTITY')
            new = recalculated > cuts
            rhs = metrics_core.metrics(pool, qr, new, views, q14, expansion, pop)
            result[pool] = dict(baseline_rows=baseline_n, reference=ref_identity,
                                edge=edge_identity(old, new, lhs, rhs, pop))
        else:
            history_file = candidate/(pool+'_HISTORY.jsonl.gz')
            h = read_rows(history_file)
            path = candidate/pool/'REFERENCES.npz'
            need(digest(history_file) == sealed[pool]['rows']['sha256'] and
                 digest(path) == manifest['pools'][pool]['feature']['arrays']['sha256'], 'CANDIDATE_FEATURE_SEAL')
            dense_n = cfg['reference'][pool]['commission_rows']
            isolation(h, rows[:dense_n], qr, pool, source_cfg, probe=probe)
            windows = cfg['windows'][pool]
            effective = effective_history(h, windows)
            with np.load(path, allow_pickle=False) as a:
                need(a['uid'].tolist() == [r['uid'] for r in h], 'CANDIDATE_ORDERED_UIDS')
                bank = ref_bank(rows[:dense_n]+effective, np.concatenate((z[:dense_n], a['e3'])),
                                np.concatenate((q[:dense_n], a['q14'])), norm)
                context = normalized_context(np.concatenate((x[:dense_n], a['context'])), context_norm)
            base = ref_bank(rows, z, q, norm)
            expected_ends = {(w['partition'], w['device']): w['reference_end'] for w in windows}
            need(bank.ends == base.ends == expected_ends, 'NO_EARLY_REFERENCE_OPENING')
            for key, value in base.frame_ends.items():
                need(bank.frame_ends.setdefault(key,value) == value, 'ORIGINAL_FRAME_CUTOFF_CHANGED')
            zq, xc = load_features(store, pool, qr, q14, context_norm)
            d = dict(rows=qr, z=zq, q=q14, context=xc, raw=raw)
            sl = probe_indices(d, bank, geom)
            tiny = split(d, sl)
            start = monotonic()
            with progress.measure('BASELINE_DISTANCE_WITNESS_'+pool):
                old_geo = replay(tiny, base, normalized_context(x, context_norm), geom, progress, 'P4_MAIN_REAL_SLICE')
                old_check = correct(raw[sl], old_geo['support3'], q14[sl], cfg['method'])
                need(np.max(np.abs(old_geo['support3']-old_s3[sl]), initial=0) <= TOL and
                     np.array_equal(old_check > cuts, old[sl]), 'BASELINE_REAL_GEOMETRY_PARITY')
            with progress.measure('CANDIDATE_DISTANCE_WITNESS_'+pool):
                new_geo = replay(tiny, bank, context, geom, progress, 'CANDIDATE_REAL_SLICE')
                oracle = direct_oracle(tiny, bank, context, geom, new_geo)
            probe_pairs = sum(g['pairs'] for g in new_geo['timing']['groups'])
            planned, flags = plan_queries(bank, qr, geom)
            total_pairs = sum(len(refs)*len(members) for v in planned.values() for refs,members in v.items()
                if flags['legal_component_count'][members[0]] >= 2)
            result[pool] = dict(baseline_rows=baseline_n, rows=len(qr), dense=dense_n, history=len(h),
                probe=dict(query_rows=len(sl), pairs=probe_pairs, seconds=monotonic()-start,
                    geometry_seconds=sum(g['seconds'] for g in new_geo['timing']['groups']), **oracle),
                pair_count=total_pairs, query_uid_sha256=uid_sha(ids))
            if probe or sizing_only:
                probe_preds = correct(raw[sl], new_geo['support3'], q14[sl], cfg['method']) > cuts
                weights = views['full'][1][sl]
                valid = {name:(np.flatnonzero(np.isin(sl, ix)), w[sl]) for name,(ix,w) in views.items()}
                sliced_metrics = metrics_core.metrics(pool,tiny['rows'],probe_preds,valid,q14[sl])
                need(probe_pairs > 0 and len(sliced_metrics) > 0 and (weights > 0).all(), 'REAL_SLICE_EVALUATION')
                result[pool]['probe'].update(metrics_rows=len(sliced_metrics))
                continue
            with progress.measure('FORMAL_PAIRED_DISTANCE_'+pool):
                geo = replay(d, bank, context, geom, progress, 'K8192_REPLAY')
                need(np.max(np.abs(geo['support3'][sl]-new_geo['support3']), initial=0) <= TOL,
                     'FORMAL_GEOMETRY_SLICE_PARITY')
                new_scores = correct(raw, geo['support3'], q14, cfg['method'])
                new = new_scores > cuts
                need(np.array_equal(new[sl], correct(raw[sl],new_geo['support3'],q14[sl],cfg['method']) > cuts)
                     and np.array_equal(new_scores[~active | metrics_core.guard(q14)],
                                        raw[~active | metrics_core.guard(q14)]), 'PROTECTED_AND_SLICE_DECISIONS')
                need(sum(x['pairs'] for x in geo['timing']['groups']) == total_pairs, 'FORMAL_PAIR_ACCOUNTING')
                rhs = metrics_core.metrics(pool, qr, new, views, q14, expansion, pop)
                result[pool]['geometry_timing'] = geo['timing']
        if probe or sizing_only:
            continue
        subgroup = by_protocol(qr)
        for name, p, m in (('P4_MAIN',old,lhs), (CANDIDATE,new,rhs)):
            metrics += [dict(config=name, **v) for v in m]
            metrics += [dict(config=name, **v) for v in metrics_core.metrics(
                pool, qr, p, views, q14, expansion, pop, group_masks=subgroup)]
        for group in (None, subgroup):
            pairs += metrics_core.paired(pool, qr, old, new, views, q14, expansion, group_masks=group)
        gates += exact_gate(qr, views, subgroup, old, new, pool)
        changed = np.flatnonzero(np.any(old != new, axis=1))
        changes = target/(pool+'_CHANGED_UIDS.jsonl.gz')
        count = write_rows(changes, (dict(uid=ids[i], label=qr[i]['label'], device=qr[i]['device'],
            protocol=qr[i]['protocol'], post_window=bool(active[i]), protected=bool(metrics_core.guard(q14[i:i+1])[0]),
            old=old[i].tolist(), candidate=new[i].tolist()) for i in changed))
        need(count == len(changed), 'CHANGED_UID_INDEX')
        result[pool].update(changed_uids=asset(changes, count=count))
    if not probe and not sizing_only:
        table(target, 'METRICS', metrics)
        table(target, 'PAIRED', pairs)
        table(target, 'ZERO_DEGRADATION', gates)
    return dict(pools=result, gates=len(gates), failures=[r for r in gates if r['status']=='FAIL'],
                baseline_scores_reproduced=True, inputs=store.checked)
