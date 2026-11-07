"""Exact batched geometry. Frozen eligibility and UID/component tie order remain intact."""
import collections
import time
import numpy as np
from geometry_frozen import rms


class Reducer:
    def __init__(self, components):
        groups = collections.defaultdict(list)
        for i, name in enumerate(components):
            groups[name].append(i)
        assert len(groups) >= 2
        self.order = np.asarray([i for ids in groups.values() for i in ids])
        self.starts = np.cumsum([0] + [len(ids) for ids in groups.values()][:-1])
        self.component = np.empty(len(components), dtype=int)
        for j, ids in enumerate(groups.values()):
            self.component[ids] = j

    def second(self, distance, representatives=False):
        minima = np.minimum.reduceat(distance[:, self.order], self.starts, axis=1)
        # Stable component order is its first UID in the frozen sorted bank.
        chosen = np.argsort(minima, axis=1, kind='stable')[:, :2]
        value = np.take_along_axis(minima, chosen[:, 1:2], axis=1).ravel()
        if not representatives:
            return value
        best = []
        for col in range(2):
            target = chosen[:, col]
            match = ((self.component[None, :] == target[:, None]) &
                     (distance == minima[np.arange(len(distance)), target, None]))
            assert match.any(axis=1).all()
            best.append(np.argmax(match, axis=1))
        return value, np.stack(best, axis=1)


def evaluate(d, refs, rz, rq, rc, norm, geom, rhoc, core, progress):
    begin = time.monotonic()
    uids = [r['uid'] for r in refs]
    bank = core.ReferenceBank(refs, rz, rq, norm, feature_uids=uids, q_uids=uids,
                              allow_prebank_history=True)
    rows = d['rows']; uu = [r['uid'] for r in rows]
    z, q = bank._queries(rows, d['z'][:, :768], d['q'], uu, uu)
    old = bank._empty(len(rows)); new = np.zeros(len(rows))
    matched = np.full((len(rows), 2), np.nan); second_dc = np.full(len(rows), np.nan)
    groups = collections.defaultdict(list)
    for i, row in enumerate(rows):
        groups[(row['partition'], row['device'], row['protocol'])].append(i)
    setup_seconds = time.monotonic() - begin; group_times = []; done = 0
    for key, queries in groups.items():
        started = time.monotonic(); ri = bank.groups.get(key, [])
        if not ri:
            group_times.append(dict(key=list(key), rows=len(queries), seconds=time.monotonic()-started))
            continue
        rr = [refs[i] for i in ri]; end = bank.ends[key[:2]]
        components = [r['component_id'] for r in rr]
        radii = core._radius(geom, key[2]); cr = rhoc[str(key[2])]
        old['bank_end'][queries] = end; old['geometry_supported'][queries] = radii is not None
        maxframe = {}
        for r in rr:
            maxframe[r['capture_id']] = max(maxframe.get(r['capture_id'], 0), r['frame'])
        # One eligibility scan per distinct cutoff pattern, not per query.
        cache = {}; patterns = {}
        for i in queries:
            row = rows[i]; cap = row['capture_id']; frame = row['frame']
            frame_end = bank.frame_ends.get(key[:2] + (cap,))
            old['bank_end_frame'][i] = frame_end
            if row['timestamp'] <= end:
                old['reason'][i] = 'BANK_NOT_YET_AVAILABLE'; continue
            if frame_end is not None and frame <= frame_end:
                old['reason'][i] = 'BANK_FRAME_NOT_YET_AVAILABLE'; continue
            signature = ('ALL',) if frame > maxframe.get(cap, 0) else (cap, frame)
            if signature not in cache:
                legal = tuple(j for j, r in enumerate(rr) if r['capture_id'] != cap or r['frame'] < frame)
                names = {components[j] for j in legal}
                cache[signature] = (legal, names)
                patterns[signature] = []
            legal, names = cache[signature]
            old['legal_component_count'][i] = len(names)
            old['same_component'][i] = row['component_id'] in names
            if len(names) < 2:
                old['reason'][i] = 'FEWER_THAN_TWO_LEGAL_COMPONENTS'; continue
            old['eligible'][i] = True
            old['reason'][i] = 'NO_SOURCE_GEOMETRY_SUPPORT' if radii is None else 'ELIGIBLE_ZERO_SUPPORT'
            patterns[signature].append(i)
        for signature, ix in patterns.items():
            if not ix: continue
            legal, _ = cache[signature]; indices = np.asarray([ri[j] for j in legal])
            comp = [components[j] for j in legal]; reducer = Reducer(comp)
            # Materialize bank blocks once, outside the query batch loop.
            bz, bq, bc = bank.z[indices].T, bank.q14[indices], rc[indices]
            uid_array = np.asarray([refs[j]['uid'] for j in indices], dtype=object)
            chunk = max(1, min(256, 262144 // len(indices)))
            for start in range(0, len(ix), chunk):
                use = np.asarray(ix[start:start+chunk]); uz = core._unit(z[use], norm)
                dz = np.clip(1. - uz @ bz, 0., 2.)
                dq = rms(q[use], bq); dc = rms(d['context'][use], bc)
                old['second_dz'][use] = reducer.second(dz)
                old['second_dq'][use] = reducer.second(dq)
                second_dc[use] = reducer.second(dc)
                if radii is not None:
                    joint = np.maximum(core._ratio(dz, radii[0]), core._ratio(dq, radii[1]))
                    sec, best = reducer.second(joint, True)
                    support = np.clip(1. - sec, 0., 1.)
                    old['second_joint'][use] = sec; old['support'][use] = support
                    old['reason'][use[support > 0]] = 'SUPPORTED'
                    old['matched_reference_uids'][use] = uid_array[best]
                    old['matched_components'][use] = np.asarray(comp, dtype=object)[best]
                    matched[use] = np.take_along_axis(dc, best, axis=1)
                    positive = support > 0
                    if positive.any() and cr['status'] == 'READY':
                        joint3 = np.maximum(joint[positive], core._ratio(dc[positive], cr['rho_c']))
                        new[use[positive]] = np.clip(1. - reducer.second(joint3), 0., 1.)
                done += len(use)
                if start == 0 or start % (chunk*20) == 0:
                    progress('JOINT_2D_3D_DISTANCE', done, len(rows))
        group_times.append(dict(key=list(key), rows=len(queries), seconds=time.monotonic()-started))
    overlap = [i for i, r in enumerate(rows) if r['uid'] in bank.by_uid]
    if overlap:
        assert not old['eligible'][overlap].any() and not old['support'][overlap].any()
        assert all(x is None for x in old['matched_reference_uids'][overlap].flat)
    # Stored-support schema parity is enforced by worker on every query.
    # This kernel returns unmodified geometric support for both dimensions.
    assert np.all(new <= old['support']+2e-10), 'INTERSECTION_SUPPORT_MONOTONICITY'
    d['_distance_timing'] = dict(setup_seconds=setup_seconds, groups=group_times)
    return old, new, matched, second_dc


def compare(expected, actual):
    """Frozen implementation oracle, including donor identity and ineligible rows."""
    errors = {}
    for name, value in expected[0].items():
        other = actual[0][name]
        if value.dtype.kind in 'fc':
            assert np.array_equal(np.isfinite(value), np.isfinite(other)), name
            assert np.array_equal(np.isnan(value), np.isnan(other)), name
            finite = np.isfinite(value)
            error = float(np.max(np.abs(value[finite]-other[finite]), initial=0))
            assert error <= 2e-10, (name, error)
            errors[name] = error
        else:
            assert np.array_equal(value, other), name
    for j in range(1, 4):
        a, b = expected[j], actual[j]
        assert np.array_equal(np.isfinite(a), np.isfinite(b))
        finite = np.isfinite(a); error = float(np.max(np.abs(a[finite]-b[finite]), initial=0))
        assert error <= 2e-10, (j, error); errors[str(j)] = error
    return dict(status='PASS', max_abs_errors=errors, donor_uids_and_metadata_exact=True)
