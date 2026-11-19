"""Known failures at the eligibility, effective-sample-size, and port-role boundaries."""

import numpy as np


def boundaries():
    from common_round1 import require
    from calibration import four
    from group_threshold import fit_groups, apply_groups, PRIMARY, SENS
    from mechanism import replay
    from port_audit import classify_pair, identity
    from hashlib import sha256
    import json

    def row(i, dev):
        return dict(
            uid=f"{dev}-{i}",
            device=dev,
            protocol=6,
            capture_id="c",
            component_id="x",
            use="REFERENCE",
            label=0,
        )

    rows = [row(i, dev) for dev, n in [("fit", 100), ("small", 99), ("guard", 1)] for i in range(n)]
    q = np.zeros((200, 14))
    q[:, 0] = 1
    q[-1, 2] = 1
    score = four(np.repeat((np.arange(200) % 4).astype(float)[:, None], 3, axis=1))
    source = [-1.0] * 4
    pool_cut = [2.0] * 4
    f = fit_groups(
        rows,
        score,
        q,
        source,
        pool_cut,
        ["fit", "small", "guard", "empty"],
        dict(budget=0.01, min_neff=100, protocols=[6, 17]),
    )
    require(
        f["fit|6"]["reason"] == "FIT"
        and f["fit|6"]["n_eff"] == 100
        and f["small|6"]["reason"] == "SMALL"
        and f["guard|6"]["reason"] == "ALL_BYPASS"
        and f["empty|6"]["reason"] == "EMPTY",
        "KISH_ONE_PERCENT_BOUNDARY",
    )
    require(
        f["fit|6"]["heads"]["27"]["primary"]["strict_mass"] == 0
        and f["fit|6"]["heads"]["27"]["primary"]["tie_mass"] == 0.25,
        "STRICT_TIED_MAXIMUM",
    )
    tr = [row(0, x) for x in ("small", "fit", "empty", "guard", "new")]
    raw = four(np.ones((5, 3)))
    fq = np.zeros((5, 14))
    fq[3, [0, 2]] = 1
    d = dict(
        rows=tr, ids=[r["uid"] for r in tr], raw=raw, p4=raw, q=fq, active=np.array([1, 1, 1, 1, 0], bool)
    )
    method = dict(cuts=source, scales=[4.0] * 3)
    pred, route = apply_groups(d, f, method, pool_cut)
    require(
        pred[PRIMARY][:, 0].tolist() == [True, False, True, True, True]
        and pred[SENS][:, 0].tolist() == [False, False, False, True, True]
        and route.tolist() == ["SMALL", "FIT", "EMPTY", "BYPASS", "PRE_OPEN"],
        "QUERY_FALLBACK_PRIMARY_SENSITIVITY",
    )
    from vendor import p4_worker

    cache = dict(
        m1=np.array([0.1, 0.2, 1.0, 0.1, np.inf]),
        m2=np.array([np.inf, 0.8, 1.0, 0.5, np.inf]),
        bank_rows=np.array([[0, -1], [0, 1], [0, 1], [0, 1], [-1, -1]]),
        opening=np.array(["", "", "", "", "TIME"]),
        geometry_ready=np.array([1, 1, 1, 1, 0], bool),
        legal_components=np.array([1, 2, 2, 2, 0]),
    )
    cache["admitted"] = cache["m2"] < 1
    d["saved"] = cache["weak"] = np.where(cache["admitted"], 1 - cache["m2"], 0.0)
    method["cuts"] = [0.1] * 4
    d["p4"] = cache["scores_a"] = p4_worker.correct(raw, d["saved"], fq, method["scales"], True, power=4)
    cache["alarms_a"] = d["p4"] > method["cuts"]
    cache["scores_b"] = d["p4"]
    cache["alarms_b"] = cache["alarms_a"]
    a = replay(d, cache, method)
    require(
        a["pathway"].tolist()
        == [
            "new_positive_from_zero",
            "stronger_existing_dual",
            "equal_or_zero",
            "stronger_existing_dual",
            "equal_or_zero",
        ]
        and a["k1"][3].all()
        and not a["k1"][0].any(),
        "K1_GATES",
    )

    def key(p):
        c = [6, ["192.0.2.1", p], ["192.0.2.2", 5555]]
        x = dict(
            canonical_key=c,
            protocol=6,
            owner="test",
            component_id=sha256(json.dumps(["test", c], separators=(",", ":")).encode()).hexdigest(),
        )
        return identity(x)

    ids = [key(4100), key(4200), None]
    require(
        classify_pair(0, 1, {}, ids) == ("ONE_PORT", "UNKNOWN", "UNKNOWN")
        and classify_pair(0, 1, {0: ("192.0.2.2", None), 1: ("192.0.2.2", None)}, ids)
        == ("ONE_PORT", "OTHER_END", "UNKNOWN")
        and classify_pair(1, 2, {}, ids)[0] == "UNKNOWN_IDENTITY",
        "DONOR_PORT_ROLE_EVIDENCE",
    )
    return dict(
        status="PASS",
        group_neff_99_100=True,
        conditional_weights_ties_empty_and_bypass=True,
        k1_single_donor_strict_radius_pathways=True,
        endpoint_role_and_unknown=True,
    )
