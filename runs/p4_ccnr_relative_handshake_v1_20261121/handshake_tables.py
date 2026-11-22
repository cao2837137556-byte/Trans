"""Build small census and paired outcomes, retaining each frozen denominator."""
import numpy as np

from handshake_geometry import ARMS, COMPARISONS, STEPS
from handshake_inputs import MISSING, UDP
from history_common import HEADS, artifact, save
from paired_history import unit_views


def distribution(pool, data, histories):
    a = data["a"]
    q, r = histories["query"], histories["reference"]
    rosters = []
    rosters.extend(((pool, "reference", r), (pool, "queries_all", q), (pool, "queries_evaluation", q[a["active"]])))
    for kind in ("normal", "attack"):
        scope = a["active"] & (a["kind"] == kind)
        if scope.any():
            rosters.append((pool, f"queries_{kind}", q[scope]))
    if pool == "TON":
        devices = np.asarray([row["device"] for row in data["refs"]])
        for host in np.unique(a["activity"]):
            rosters.extend(((host, "reference", r[devices == host]),
                            (host, "queries_evaluation", q[(a["activity"] == host) & a["active"]])))
    names = ("P25", "P50", "P90", "P99", "P99_9", "max")
    result = []
    for group, roster, array in rosters:
        assert len(array)
        for label, sel in (
            ("all", np.ones(len(array), bool)),
            ("inbound", array[:, 1] == 1), ("outbound", array[:, 1] == 0),
            ("unverified_direction", array[:, 1] == -1),
        ):
            if not sel.any():
                continue
            h, _, warm, _ = array[sel].T
            valid = h >= 0
            missing = int((h == MISSING).sum())
            udp = int((h == UDP).sum())
            assert missing + udp + valid.sum() == len(h)
            quantiles = np.percentile(h[valid], [25, 50, 90, 99, 99.9, 100]).tolist() if valid.any() else [""] * len(names)
            result.append(dict(pool=pool, group=group, roster=roster, unit="reference_record" if roster=="reference" else "query",
                               direction=label, total=len(h), TCP=len(h)-udp, valid=int(valid.sum()),
                               missing_TCP=missing, UDP_not_applicable=udp, valid_zero=int((h == 0).sum()),
                               observed_prefix_lt60s=int((valid & (warm == 1)).sum()),
                               coverage_given_TCP=(float(valid.sum() / (len(h)-udp)) if len(h)>udp else ""),
                               **dict(zip(names, quantiles))))
    return result


def summarize(out, pool, a, scores, evidence, qh):
    rows, stages = [], []
    for group, view in unit_views(pool, a).items():
        dec = {arm: view.any(array) for arm, array in scores.items()}
        missing = view.any(qh == MISSING)
        for h, seed in enumerate(HEADS):
            raw = int(dec["RAW"][:, h].sum())
            orig = int(dec["v12"][:, h].sum())
            header = dict(group=group, kind=view.view.kind, unit=view.view.unit, seed=seed, total=view.n,
                          raw=raw, original_v12=orig)
            for arm in ("RAW", *ARMS):
                out_ = dec[arm][:, h]
                count = int(out_.sum())
                assert orig <= count <= raw <= view.n
                rows.append(dict(**header, arm=arm, alarm=count, added_vs_v12=count-orig,
                                 retention_vs_raw=(count/raw if raw else ""),
                                 detection_or_fpr=(count/view.n if view.n else "")))
            for old, new in COMPARISONS:
                start, final = dec[old][:, h], dec[new][:, h]
                names = [f"{new}_{step}" for step in STEPS]
                staged = [dec[stage][:, h] for stage in names]
                co = [int((r & ~l).sum()) for l, r in zip([start, *staged], [*staged, final])]
                assert sum(co) == int((final & ~start).sum())
                assert all(np.all(l<=r) for l,r in zip([start, *staged], [*staged, final]))
                stages.append(dict(**header, baseline_arm=old, handshake_arm=new, baseline_alarms=int(start.sum()),
                                   new_alarms=int(final.sum()), gain=sum(co), lost=int((start & ~final).sum()),
                                   shortage_missing_ref=co[0], shortage_handshake_band=co[1],
                                   shortage_joint_compatibility=co[2], weakened_positive_support=co[3],
                                   shortage_total=sum(co[:3]), units_with_any_missing_query=int(missing.sum())))
    tables = {}
    for suffix, values in (("PAIRED", rows), ("MECHANISM", stages)):
        path = out / f"{pool}_{suffix}.csv"
        save(path, values)
        tables[path.name] = artifact(path)
    return tables
