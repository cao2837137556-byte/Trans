"""Device/protocol reference-only fitting, then application to frozen query logits."""

from collections import Counter, defaultdict
from fractions import Fraction
from math import fsum

import numpy as np

from analysis_core import HEADS, guard
from calibration import hierarchical_weights, weighted_cut
from common_round1 import require

PRIMARY = "GROUP_SOURCE_FALLBACK"
SENS = "GROUP_POOL_FALLBACK"
POOL_ARM = "RECAL_WITH_GUARD"


def group_key(device, protocol):
    return f"{device}|{int(protocol)}"


def effective_size(rows, eligible):
    # Common weights within a device are 1/(#captures * #components in capture * #rows in leaf).
    leaves = Counter((r["capture_id"], r["component_id"]) for r in rows)
    branches = Counter(c for c, _ in leaves)
    denoms = Counter(
        branches[r["capture_id"]] * leaves[r["capture_id"], r["component_id"]]
        for r, ok in zip(rows, eligible)
        if ok
    )
    mass = sum((Fraction(n, k) for k, n in denoms.items()), Fraction())
    squared = sum((Fraction(n, k * k) for k, n in denoms.items()), Fraction())
    return mass * mass / squared if squared else Fraction()


def tail(scores, weights, cut):
    if not len(weights):
        return dict(cut=float(cut), strict_mass=None, tie_mass=None, above_count=0)
    return dict(
        cut=float(cut),
        strict_mass=fsum(weights[scores > cut]),
        tie_mass=fsum(weights[scores == cut]),
        above_count=int(np.sum(scores > cut)),
    )


def fit_groups(rows, scores, q, source, pool_cuts, devices, rule):
    require(
        rule["min_neff"] == 100
        and rule["budget"] == 0.01
        and len(rows) == len(q) == len(scores)
        and scores.shape[1] == len(source) == len(pool_cuts) == 4,
        "GROUP_CONTRACT",
    )
    by_group = defaultdict(list)
    for i, r in enumerate(rows):
        require(
            r["use"] == "REFERENCE"
            and r["label"] == 0
            and r["device"] in devices
            and r["protocol"] in rule["protocols"],
            "NORMAL_REFERENCE_ROSTER",
        )
        by_group[r["device"], r["protocol"]].append(i)
    protected = guard(q)
    result = {}
    for dev in devices:
        for proto in rule["protocols"]:
            idx = np.array(by_group[dev, proto], dtype=int)
            local = [rows[i] for i in idx]
            keep = ~protected[idx]
            w = hierarchical_weights(local)[0][keep] if local else np.array([])
            base_mass = fsum(w)
            if w.size:
                w = w / base_mass
            neff = effective_size(local, keep)
            require(
                not len(w) or np.isclose(float(neff), 1.0 / fsum(w * w), rtol=1e-12), "KISH_REFERENCE_WEIGHTS"
            )
            reason = (
                "EMPTY"
                if not len(idx)
                else "ALL_BYPASS"
                if not len(w)
                else "SMALL"
                if neff < rule["min_neff"]
                else "FIT"
            )
            eligible = scores[idx[keep]]
            heads = {}
            for j, head in enumerate(HEADS):
                x = eligible[:, j]
                fitted = weighted_cut(x, w, 0.01)["cut"] if reason == "FIT" else None
                primary = tail(x, w, source[j] if fitted is None else fitted)
                sensitive = tail(x, w, pool_cuts[j] if fitted is None else fitted)
                heads[head] = dict(
                    primary=dict(origin="GROUP_FIT" if reason == "FIT" else "SOURCE", **primary),
                    sensitivity=dict(
                        origin="GROUP_FIT" if reason == "FIT" else "TESTBED_GUARDED", **sensitive
                    ),
                )
            result[group_key(dev, proto)] = dict(
                device=dev,
                protocol=proto,
                reference_rows=len(idx),
                eligible_rows=len(w),
                conditional_mass_before_normalization=base_mass,
                captures=len({r["capture_id"] for r in local}),
                components=len({r["component_id"] for r in local}),
                n_eff=float(neff),
                eligible_components=len({r["component_id"] for r, k in zip(local, keep) if k}),
                reason=reason,
                heads=heads,
            )
    return result


def apply_groups(d, fits, method, pooled):
    raw = d["raw"]
    source = np.asarray(method["cuts"])
    raw_pred = raw > source
    protected = guard(d["q"])
    active = d["active"]
    apply = active & ~protected
    predictions = {k: raw_pred.copy() for k in (POOL_ARM, PRIMARY, SENS)}
    predictions.update(RAW=raw_pred, P4_MAIN=d["p4"] > source)
    predictions[POOL_ARM][apply] = raw[apply] > pooled
    route = np.full(len(raw), "PRE_OPEN", dtype="U18")
    route[active & protected] = "BYPASS"
    groups = defaultdict(list)
    for i in np.flatnonzero(apply):
        row = d["rows"][i]
        groups[group_key(row["device"], row["protocol"])].append(i)
    for k, ix in groups.items():
        f = fits.get(k)
        reason = f["reason"] if f else "EMPTY"
        route[ix] = reason
        for arm, label, default in ((PRIMARY, "primary", source), (SENS, "sensitivity", pooled)):
            cut = [f["heads"][h][label]["cut"] for h in HEADS] if f else default
            predictions[arm][ix] = raw[ix] > cut
    require(
        all(np.array_equal(x[~apply], raw_pred[~apply]) for x in predictions.values()), "QUERY_RAW_FALLBACK"
    )
    fallback = apply & (route != "FIT")
    require(
        np.array_equal(predictions[PRIMARY][fallback], raw_pred[fallback])
        and np.array_equal(predictions[SENS][fallback], predictions[POOL_ARM][fallback])
        and np.array_equal(predictions[PRIMARY][~fallback], predictions[SENS][~fallback]),
        "FALLBACK_ONLY_SENSITIVITY",
    )
    return predictions, route
