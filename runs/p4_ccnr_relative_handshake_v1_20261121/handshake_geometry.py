"""Tighten frozen distance jointly with prior observed handshake evidence."""
from collections import defaultdict

import numpy as np

from paired_history import correct, severity
from screen_geometry import TOL, supports

ARMS = ("v12", "R1_U1", "v12_H60", "R1_U1_H60")
COMPARISONS = (("v12", "v12_H60"), ("R1_U1", "R1_U1_H60"))
STEPS = ("missing_ref", "handshake_band", "joint_gate")
LOG3 = np.log(3.)


def in_handshake_band(anchor, refs):
    lo = np.minimum(anchor + 1, refs + 1)
    hi = np.maximum(anchor + 1, refs + 1)
    return (refs >= 0) & (hi < 3 * lo)


def component_counts(components, valid, band):
    return (len(np.unique(components[valid])), len(np.unique(components[band])))


def exact_second(joint, components):
    """Independent check of component minima on the real preflight subset."""
    minima = {}
    for c, val in zip(components, joint):
        minima[c] = min(minima.get(c, np.inf), val)
    return sorted(minima.values())[1] if len(minima) >= 2 else np.inf


def replay(rows, z, q, x, data, qr, rr, qh, rh, base, tick, pilot=False):
    from replay_geometry import plan_queries, radii
    from vendor import constrained_onboarding_core_v3 as core, geometry_frozen
    from vendor.fast_geometry import Reducer

    bank, context, cfg = data["bank"], data["rc"], data["geom"]
    if pilot:
        unchanged, precheck = supports(rows, z, q, x, qr, rr, bank, context, cfg, base[0], tick, pilot=True)
        s1 = unchanged["U1"][0][0]
        error = float(np.max(np.abs(s1 - base[1]), initial=0.))
        assert error <= TOL, ("REAL_SLICE_R1_SUPPORT_PARITY", error)
        precheck["max_r1_support_diff"] = error
    else:
        precheck = {}
    ids = [r["uid"] for r in rows]
    z, q = bank._queries(rows, z, q, ids, ids)
    plans, ready = plan_queries(bank, rows, cfg)
    evidence = np.zeros((2, 2, len(rows)), np.int32)
    result = base.copy()
    proof = dict(matrix_pairs=0, oracle_comparisons=0, precheck=precheck)
    for key, patterns in plans.items():
        if key[-1] != 6:
            continue
        radii2, rho = radii(cfg, key[-1])
        if radii2 is None or rho is None:
            continue
        for legal, positions in patterns.items():
            ri = np.asarray(legal)
            names = np.asarray([bank.rows[j]["component_id"] for j in ri])
            _, component = np.unique(names, return_inverse=True)
            refcounts = rh[ri]
            positive = refcounts >= 0
            refroles = rr[ri, 0]
            refz, refq, refc = bank.z[ri].T, bank.q14[ri], context[ri]
            counts = {}
            for i in positions:
                h = qh[i]
                if h < 0:
                    continue
                for slot, role in enumerate((-1, int(qr[i, 0]))):
                    identity = role, int(h)
                    if identity not in counts:
                        valid = positive if role == -1 else positive & (refroles == role)
                        band = valid & in_handshake_band(h, refcounts)
                        counts[identity] = component_counts(component, valid, band)
                    evidence[slot, :, i] = counts[identity]
                    if evidence[slot, 1, i] < 2:
                        result[slot, i] = 0.
            candidates = np.asarray([i for i in positions if qh[i] >= 0 and
                bool(np.any((evidence[:, 1, i] >= 2) & ((base[:, i] > 0.) | pilot)))], dtype=np.int64)
            stride = max(1, min(core.BLOCK_ROWS, core.PAIR_BUDGET // len(ri)))
            for offset in range(0, len(candidates), stride):
                use = candidates[offset:offset + stride]
                dz = np.clip(1. - core._unit(z[use], bank.normalizer) @ refz, 0., 2.)
                dq = geometry_frozen.rms(q[use], refq)
                dc = geometry_frozen.rms(x[use], refc)
                joint3 = np.maximum.reduce((core._ratio(dz, radii2[0]), core._ratio(dq, radii2[1]),
                                            core._ratio(dc, rho)))
                proof["matrix_pairs"] += len(ri) * len(use)
                for slot in range(2):
                    by_band = defaultdict(list)
                    for j, i in enumerate(use):
                        if evidence[slot, 1, i] >= 2 and (base[slot, i] > 0. or pilot):
                            by_band[(int(qr[i, 0]) if slot else -1, int(qh[i]))].append(j)
                    for (role, h), inds in by_band.items():
                        keep = in_handshake_band(h, refcounts)
                        if role != -1:
                            keep &= refroles == role
                        cols = np.flatnonzero(keep)
                        dd = np.abs(np.log1p(h) - np.log1p(refcounts[cols])) / LOG3
                        # Integer band comparison is authoritative at distance 1.
                        dd = np.minimum(dd, np.nextafter(1., 0.))
                        assert (dd >= 0).all()
                        joint4 = np.maximum(joint3[np.ix_(inds, cols)], dd)
                        reducer = Reducer(component[cols].tolist())
                        m2 = reducer.second(joint4)
                        ix = use[inds]
                        new = np.clip(1. - m2, 0., 1.)
                        assert np.all(new <= base[slot, ix] + TOL), ("SUPPORT_SUBSET", slot)
                        result[slot, ix] = np.minimum(new, base[slot, ix])
                        if pilot:
                            for k, cell in enumerate(joint4):
                                want = exact_second(cell, component[cols])
                                assert want == m2[k]
                                proof["oracle_comparisons"] += 1
                if offset == 0 or offset % (stride * 20) == 0:
                    tick(proof["matrix_pairs"])
    assert np.all(result <= base) and np.all(result[1] <= result[0])
    assert np.array_equal(result[:, qh < 0], base[:, qh < 0])
    enabled = ready["geometry_ready"] & (qh >= 0)
    assert np.all(result[(evidence[:, 1] < 2) & enabled[None, :]] == 0.)
    return result, evidence, enabled, proof


def alarms(a, contract, base_support, hs_support, evidence, enabled):
    cuts = np.array(contract["cuts"])
    scales = np.array(contract["scales"])
    raw = a["v12"] > cuts
    scores = {"RAW": raw}
    for slot, (old, new) in enumerate(COMPARISONS):
        for name, support in ((old, base_support[slot]), (new, hs_support[slot])):
            g = severity(dict(support=support, guard=a["guard"]))
            scores[name] = correct(a["v12"], g, scales, .25, cuts)
        masks = (enabled & (evidence[slot, 0] < 2), enabled & (evidence[slot, 1] < 2),
                 enabled & (hs_support[slot] == 0.))
        stage = scores[old]
        for suffix, mask in zip(STEPS, masks):
            flags = np.where(mask[:, None], raw, scores[old])
            assert np.all(stage <= flags)
            stage = scores[f"{new}_{suffix}"] = flags
        assert np.all(stage <= scores[new]) and np.all(scores[new] <= raw)
    assert np.all(scores["v12"] <= scores["R1_U1"])
    assert np.all(scores["v12_H60"] <= scores["R1_U1_H60"])
    same = a["proto"] == 17
    for old, new in COMPARISONS:
        assert np.array_equal(scores[old][same], scores[new][same])
    for head in scores.values():
        assert np.array_equal(head[a["guard"]], raw[a["guard"]])
    return scores
