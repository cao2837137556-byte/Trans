"""One nearest distinct component with the original decision rule and frozen row order."""

import numpy as np

from analysis_core import guard
from common_round1 import require, TOL
from vendor import p4_worker

K1 = "P4_SINGLE_COMPONENT"
K2 = "P4_MAIN"


def replay(d, cache, method):
    n = len(d["ids"])
    first, second = cache["m1"], cache["m2"]
    donors = cache["bank_rows"]
    count = cache["legal_components"]
    ready = (cache["opening"] == "") & cache["geometry_ready"]
    one = ready & (count >= 1)
    two = ready & (count >= 2)
    require(
        first.shape == second.shape == (n,)
        and donors.shape == (n, 2)
        and donors.dtype.kind == "i"
        and count.dtype.kind in "iu"
        and np.all(count >= 0)
        and np.all(first >= 0)
        and np.all(first <= second)
        and np.array_equal(donors[:, 0] >= 0, one)
        and np.array_equal(donors[:, 1] >= 0, two)
        and np.isposinf(first[~one]).all()
        and np.isposinf(second[~two]).all(),
        "RECOVERED_COMPONENT_DISTANCE_SCHEMA",
    )
    admitted = two & (second < 1.0)
    weak = np.zeros(n, dtype=np.float64)
    weak[admitted] = 1.0 - second[admitted]
    s1 = np.zeros_like(weak)
    s1[one] = np.clip(1.0 - first[one], 0.0, 1.0)
    require(
        np.array_equal(admitted, cache["admitted"])
        and np.array_equal(weak, cache["weak"])
        and np.allclose(weak, d["saved"], rtol=0, atol=TOL)
        and np.all(s1 >= weak)
        and not np.any((s1 > 0) & ~d["active"]),
        "K2_SUPPORT_REPRODUCTION_AND_K1_GATE",
    )
    sc2 = p4_worker.correct(d["raw"], weak, d["q"], method["scales"], True, power=4)
    sc1 = p4_worker.correct(d["raw"], s1, d["q"], method["scales"], True, power=4)
    pa, pb = sc2 > method["cuts"], sc1 > method["cuts"]
    raw = d["raw"] > method["cuts"]
    bypass = guard(d["q"])
    require(
        np.allclose(sc2, d["p4"], rtol=0, atol=TOL)
        and np.array_equal(sc2, cache["scores_a"])
        and np.array_equal(pa, d["p4"] > method["cuts"])
        and np.array_equal(pa, cache["alarms_a"])
        and np.all(sc1 <= sc2)
        and not (pb & ~pa).any()
        and not (pa & ~raw).any()
        and np.array_equal(sc1[bypass | (s1 == 0)], d["raw"][bypass | (s1 == 0)]),
        "ROW_SCORE_AND_ALARM_CONTAINMENT",
    )
    mean = cache["alarms_b"]
    require(
        np.array_equal(mean, cache["scores_b"] > method["cuts"])
        and not (mean & ~pa).any()
        and np.array_equal(mean[bypass], raw[bypass]),
        "ACCEPTED_MEAN_WITNESS",
    )
    new = (weak == 0) & (s1 > 0)
    stronger = admitted & (s1 > weak)
    pathway = np.full(n, "equal_or_zero", dtype="U24")
    pathway[new] = "new_positive_from_zero"
    pathway[stronger] = "stronger_existing_dual"
    removed = pa & ~pb
    require(
        not np.any(removed[~(new | stronger) | bypass])
        and np.array_equal(sc1[~(new | stronger)], sc2[~(new | stronger)]),
        "WITHDRAWAL_MECHANISM_PARTITION",
    )
    return dict(
        raw=raw,
        k2=pa,
        k1=pb,
        mean=mean,
        s1=s1,
        weak=weak,
        pathway=pathway,
        reduced_scores=sc1 < sc2,
        admitted=admitted,
    )


def validate_donors(d, cache, refs):
    idx = cache["bank_rows"]
    require(np.all((idx >= -1) & (idx < len(refs))), "REFERENCE_ROW_INDEX_RANGE")
    names = np.array([r["component_id"] for r in refs], object)
    both = idx[:, 1] >= 0
    require(np.all(names[idx[both, 0]] != names[idx[both, 1]]), "DISTINCT_DONOR_COMPONENTS")
    for column in idx.T:
        for i in np.flatnonzero(column >= 0):
            r = refs[column[i]]
            q = d["rows"][i]
            require(
                all(r[k] == q[k] for k in ("partition", "device", "protocol"))
                and q["timestamp"] > r["reference_end"]
                and (
                    r["capture_id"] != q["capture_id"]
                    or (r["frame"] < q["frame"] and q["frame"] > r.get("bank_end_frame", -1))
                ),
                "DONOR_ELIGIBILITY",
            )
