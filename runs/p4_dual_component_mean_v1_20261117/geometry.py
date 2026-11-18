"""Two distinct-component matches in the frozen three-space geometry."""
import numpy as np

from common_round1 import TOL, require
from replay_geometry import joint3, plan_queries, radii
from vendor import constrained_onboarding_core_v3 as core, geometry_frozen
from vendor.fast_geometry import Reducer


def supports(first, second, eligible):
    require(first.shape == second.shape == eligible.shape and not np.isnan(first).any()
            and np.all(first >= 0) and np.all(second >= first), 'JOINT_DISTANCE_ORDER')
    admitted = eligible & (second < 1.0)
    weak = np.zeros(len(first), dtype=np.float64)
    mean = weak.copy()
    weak[admitted] = 1.0 - second[admitted]
    mean[admitted] = ((1.0 - first[admitted]) + weak[admitted]) / 2.0
    difference = (second[admitted] - first[admitted]) / 2.0
    require(np.array_equal(weak > 0, admitted) and np.array_equal(mean > 0, admitted)
            and np.all(mean >= weak) and np.all(mean <= 1)
            and np.allclose((mean - weak)[admitted], difference, atol=TOL, rtol=0),
            'SHARED_GATE_AND_RAW_SUPPORT_IDENTITY')
    return admitted, weak, mean


def top_two(rows, z, q, context, bank, reference_context, geometry, progress):
    ids = [r['uid'] for r in rows]
    z, q = bank._queries(rows, z, q, ids, ids)
    plans, flags = plan_queries(bank, rows, geometry)
    n = len(rows)
    distances = np.full((n, 2), np.inf)
    donors = np.full((n, 2), -1, dtype=np.int64)
    ready = (flags['opening'] == '') & flags['geometry_ready']
    counts = flags['legal_component_count']
    work = int(np.count_nonzero(ready & (counts > 0)))
    done = pairs = 0
    for key, patterns in plans.items():
        zq, rho = radii(geometry, key[-1])
        if zq is None or rho is None:
            continue
        for legal, positions in patterns.items():
            ri = np.asarray(legal, dtype=np.int64)
            names = [bank.rows[j]['component_id'] for j in ri]
            reducer = Reducer(names) if counts[positions[0]] >= 2 else None
            bz, bq, bc = bank.z[ri].T, bank.q14[ri], reference_context[ri]
            chunk = max(1, min(core.BLOCK_ROWS, core.PAIR_BUDGET // len(ri)))
            for start in range(0, len(positions), chunk):
                ix = np.asarray(positions[start:start + chunk])
                dz = np.clip(1.0 - core._unit(z[ix], bank.normalizer) @ bz, 0.0, 2.0)
                dq = geometry_frozen.rms(q[ix], bq)
                dc = geometry_frozen.rms(context[ix], bc)
                joint = joint3(np.maximum(core._ratio(dz, zq[0]), core._ratio(dq, zq[1])), dc, rho)
                if reducer is None:
                    best = np.argmin(joint, axis=1)
                    donors[ix, 0] = ri[best]
                    distances[ix, 0] = joint[np.arange(len(ix)), best]
                else:
                    second, best = reducer.second(joint, representatives=True)
                    distances[ix] = np.take_along_axis(joint, best, axis=1)
                    donors[ix] = ri[best]
                    require(np.array_equal(distances[ix, 1], second)
                            and np.all(reducer.component[best[:, 0]] != reducer.component[best[:, 1]]),
                            'TWO_DISTINCT_JOINT_COMPONENTS')
                pairs += len(ix) * len(ri)
                done += len(ix)
                progress('COMPONENT_DISTANCES', done, work, device=key[1], protocol=key[2])
    require(done == work and np.array_equal(donors[:, 1] >= 0, ready & (counts >= 2)),
            'DISTANCE_COVERAGE')
    gate, weak, mean = supports(*distances.T, ready & (counts >= 2))
    return dict(m=distances, donors=donors, gate=gate, weak=weak, mean=mean, pairs=pairs, **flags)


def direct(rows, z, q, context, bank, reference_context, geometry, result):
    """Independent row-wise enumeration of eligibility and the two component minima."""
    expected = np.full((len(rows), 2), np.inf)
    gate = np.zeros(len(rows), dtype=bool)
    for i, row in enumerate(rows):
        key = row['partition'], row['device'], row['protocol']
        opened = (row['timestamp'] > bank.ends.get(key[:2], np.inf) and
                  row['frame'] > bank.frame_ends.get((*key[:2], row['capture_id']), -1))
        members = [j for j in bank.groups.get(key, ()) if opened and
                   (bank.rows[j]['capture_id'] != row['capture_id'] or bank.rows[j]['frame'] < row['frame'])]
        names = [bank.rows[j]['component_id'] for j in members]
        require(len(set(names)) == result['legal_component_count'][i], 'DIRECT_COMPONENT_COUNT')
        zq, rho = radii(geometry, key[-1])
        if not members or zq is None or rho is None:
            continue
        ix = np.asarray(members)
        unit = core._unit(z[i:i+1], bank.normalizer)[0]
        dz = np.clip(1.0 - bank.z[ix] @ unit, 0.0, 2.0)
        dq = np.sqrt(np.mean((bank.q14[ix] - np.asarray(q[i], dtype=np.float64)) ** 2, axis=1))
        dc = np.sqrt(np.mean((np.asarray(reference_context[ix], dtype=np.float64) - context[i]) ** 2, axis=1))
        joint = np.maximum.reduce((core._ratio(dz, zq[0]), core._ratio(dq, zq[1]), core._ratio(dc, rho)))
        minima = {}
        for name, distance in zip(names, joint):
            minima[name] = min(minima.get(name, np.inf), distance)
        first_two = sorted(minima.values())[:2]
        expected[i, :len(first_two)] = first_two
        gate[i] = len(first_two) == 2 and first_two[1] < 1
        locations = dict(zip(members, joint))
        for j, donor in enumerate(result['donors'][i, :len(first_two)]):
            require(donor in locations and np.isclose(locations[donor], first_two[j], atol=TOL, rtol=0),
                    'DIRECT_DONOR_DISTANCE')
    finite = np.isfinite(expected)
    require(np.array_equal(finite, np.isfinite(result['m'])) and np.array_equal(gate, result['gate']),
            'DIRECT_SHARED_GATE')
    error = float(np.max(np.abs(expected[finite] - result['m'][finite]), initial=0))
    weak = np.zeros(len(rows))
    mean = np.zeros(len(rows))
    weak[gate] = 1.0 - expected[gate, 1]
    mean[gate] = 1.0 - expected[gate].mean(axis=1)
    require(error <= TOL and np.allclose(weak, result['weak'], rtol=0, atol=TOL)
            and np.allclose(mean, result['mean'], rtol=0, atol=TOL), 'DIRECT_COMPONENT_MINIMA_AND_SUPPORT')
    return weak, mean, error
