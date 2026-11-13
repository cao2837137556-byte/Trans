"""Frozen production geometry for a bank subset, with per-device work measurement."""
from collections import Counter, defaultdict
from time import monotonic

import numpy as np

from common_round1 import TOL, require
from reference_inputs import key, uids
from vendor import constrained_onboarding_core_v3 as core, geometry_frozen
from vendor.fast_geometry import Reducer


def radii(config, protocol):
    zq = core._radius(config['geometry'], protocol)
    c = config['context_radii'][str(protocol)]
    require(c['status'] in ('READY', 'NO_SOURCE_GEOMETRY_SUPPORT'), 'CONTEXT_RADIUS_STATUS')
    if c['status'] == 'READY':
        require(np.isfinite(c['rho_c']) and c['rho_c'] >= 0, 'CONTEXT_RADIUS')
    return zq, c['rho_c'] if c['status'] == 'READY' else None


def joint3(d2, dc, rho):
    return np.maximum(d2, core._ratio(dc, rho))


def reference_joint(z, q, c, center, candidates, zq, rho):
    dz = np.clip(1. - z[candidates] @ z[center], 0., 2.)
    dq = geometry_frozen.rms(q[center:center + 1], q[candidates])[0]
    dc = geometry_frozen.rms(c[center:center + 1], c[candidates])[0]
    d2 = np.maximum(core._ratio(dz, zq[0]), core._ratio(dq, zq[1]))
    return joint3(d2, dc, rho)


def plan_queries(bank, rows, config):
    grouped = defaultdict(list)
    for i, row in enumerate(rows):
        grouped[key(row)].append(i)
    plans = {}
    counts = np.zeros(len(rows), dtype=np.int64)
    legal_rows = np.zeros(len(rows), dtype=np.int64)
    opening = np.full(len(rows), '', dtype='<U36')
    ready = np.zeros(len(rows), dtype=bool)
    for k, queries in grouped.items():
        time_end = bank.ends.get(k[:2])
        refs = bank.groups.get(k, [])
        rr = [bank.rows[i] for i in refs]
        caps = defaultdict(int)
        for row in rr:
            caps[row['capture_id']] = max(caps[row['capture_id']], row['frame'])
        zq, rho = radii(config, k[-1])
        patterns = defaultdict(list)
        cache = {}
        for i in queries:
            row = rows[i]
            capture, frame = row['capture_id'], row['frame']
            frame_end = bank.frame_ends.get((*k[:2], capture))
            if time_end is not None and row['timestamp'] <= time_end:
                opening[i] = 'TIME'
                continue
            if frame_end is not None and frame <= frame_end:
                opening[i] = 'FRAME'
                continue
            pattern = None if frame > caps[capture] else (capture, frame)
            if pattern not in cache:
                legal = tuple(j for j, ref in zip(refs, rr) if ref['capture_id'] != capture or ref['frame'] < frame)
                cache[pattern] = legal, len({bank.rows[j]['component_id'] for j in legal})
            legal, components = cache[pattern]
            legal_rows[i] = len(legal)
            counts[i] = components
            ready[i] = zq is not None and rho is not None
            if legal:
                patterns[legal].append(i)
        plans[k] = patterns
    overlap = np.asarray([i for i, row in enumerate(rows) if row['uid'] in bank.by_uid], dtype=np.int64)
    require(np.all(opening[overlap] != '') and not counts[overlap].any(), 'REFERENCE_OVERLAP_MUST_FALL_BACK')
    return plans, dict(opening=opening, legal_component_count=counts, legal_rows=legal_rows,
                       geometry_ready=ready)


def replay(d, bank, context, config, progress, stage, *, single_mask=None, auxiliary=False):
    setup = monotonic()
    rows = d['rows']
    ids = uids(rows)
    z, q = bank._queries(rows, d['z'], d['q'], ids, ids)
    plans, result = plan_queries(bank, rows, config)
    count = result['legal_component_count']
    n = len(rows)
    support2 = np.zeros(n, dtype=np.float64)
    support3 = np.zeros(n, dtype=np.float64)
    single = np.zeros(n, dtype=np.float64)
    single_joint = np.full(n, np.inf, dtype=np.float64)
    seconds = {name: np.full(n, np.inf) for name in ('second_dz', 'second_dq', 'second_dc')}
    if single_mask is None:
        single_mask = np.zeros(n, dtype=bool)
    total = int(np.sum((count >= 2) | ((count == 1) & single_mask & result['geometry_ready'])))
    done = 0
    setup_seconds = monotonic() - setup
    timing = []
    for k, patterns in plans.items():
        start = monotonic()
        begin_done = done
        pair_count = 0
        zq, rho = radii(config, k[-1])
        for legal, query_ix in patterns.items():
            ix = np.asarray(query_ix, dtype=np.int64)
            one = count[ix[0]] == 1
            if one:
                ix = ix[single_mask[ix] & result['geometry_ready'][ix]]
            if not len(ix):
                continue
            ri = np.asarray(legal, dtype=np.int64)
            comp = [bank.rows[j]['component_id'] for j in ri]
            reducer = None if one else Reducer(comp)
            # Retain the production batch bound and its axis-wise RMS reductions.
            bz, bq, bc = bank.z[ri].T, bank.q14[ri], context[ri]
            chunk = max(1, min(core.BLOCK_ROWS, core.PAIR_BUDGET // len(ri)))
            for offset in range(0, len(ix), chunk):
                use = ix[offset:offset + chunk]
                uz = core._unit(z[use], bank.normalizer)
                dz = np.clip(1. - uz @ bz, 0., 2.)
                dq = geometry_frozen.rms(q[use], bq)
                dc = geometry_frozen.rms(d['context'][use], bc)
                if auxiliary and not one:
                    seconds['second_dz'][use] = reducer.second(dz)
                    seconds['second_dq'][use] = reducer.second(dq)
                    seconds['second_dc'][use] = reducer.second(dc)
                if zq is not None:
                    d2 = np.maximum(core._ratio(dz, zq[0]), core._ratio(dq, zq[1]))
                    if one:
                        single_joint[use] = np.min(joint3(d2, dc, rho), axis=1)
                        single[use] = np.clip(1. - single_joint[use], 0., 1.)
                    else:
                        support2[use] = np.clip(1. - reducer.second(d2), 0., 1.)
                        positive = support2[use] > 0
                        if rho is not None and positive.any():
                            s3 = reducer.second(joint3(d2[positive], dc[positive], rho))
                            support3[use[positive]] = np.clip(1. - s3, 0., 1.)
                done += len(use)
                pair_count += len(use) * len(ri)
                if offset == 0 or offset % (chunk * 20) == 0 or done == total:
                    progress(stage, done, total, device=k[1], protocol=k[2])
        timing.append(dict(key=list(k), seconds=monotonic() - start,
                           scored_rows=done - begin_done, pairs=pair_count))
    require(np.all((0 <= support3) & (support3 <= 1)) and
            np.all(support3 <= support2 + TOL) and
            np.all(support2[count < 2] == 0) and done == total, 'GEOMETRY_INVARIANTS')
    result.update(support2=support2, support3=support3, single=single, single_joint=single_joint,
                  timing=dict(setup_seconds=setup_seconds, groups=timing, chunk_pairs=core.PAIR_BUDGET))
    if auxiliary:
        result.update(seconds)
    return result


def choose_representatives(assets, groups, normalized, config, progress):
    selected = list(range(assets.dense_count))
    mapping = {i: i for i in selected}
    bank = assets.full_bank
    compared = 0
    count = len(groups)
    for step, (sig, members) in enumerate(groups.items(), 1):
        ids = np.asarray(sorted(members, key=lambda i: assets.rows[i]['uid']), dtype=np.int64)
        n = len(ids)
        if n == 1:
            selected.append(int(ids[0]))
            mapping[int(ids[0])] = int(ids[0])
        else:
            zq, rho = radii(config, sig[2])
            require(zq is not None and rho is not None, 'C1_REQUIRED_SOURCE_RADIUS')
            chosen = np.zeros(n, dtype=bool)
            nearest = np.full(n, np.inf)
            representatives = np.full(n, -1, dtype=np.int64)
            local = 0
            for _ in range((n + 1) // 2):
                chosen[local] = True
                center = int(ids[local])
                selected.append(center)
                distance = reference_joint(bank.z, bank.q14, normalized, center, ids, zq, rho)
                require(not np.isnan(distance).any(), 'C1_NONFINITE_DISTANCE')
                compared += n
                current = representatives.clip(min=0)
                better = ((representatives < 0) | (distance < nearest) |
                          ((distance == nearest) & (local < current)))
                nearest[better] = distance[better]
                representatives[better] = local
                # The array is in original UID order, so argmax breaks exact ties by UID.
                local = int(np.argmax(np.where(chosen, -np.inf, nearest)))
            for i, rep in enumerate(representatives):
                mapping[int(ids[i])] = int(ids[i] if chosen[i] else ids[rep])
        if step == 1 or step % 128 == 0 or step == count:
            progress('C1_SELECT_REFERENCES', step, count, evaluated_reference_pairs=compared)
    return np.asarray(sorted(selected), dtype=np.int64), mapping, compared
