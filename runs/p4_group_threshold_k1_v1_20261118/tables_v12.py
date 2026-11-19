"""Statistics on the original query views and weights, including both directions of change."""

import numpy as np

from analysis_core import groups, metrics, paired, HEADS
from evaluation import by_protocol


def comparison_tables(pool, d, predictions, comparisons, routes):
    masks = groups(d["rows"])
    labels = {k: m for k, m in masks.items() if k in ("NORMAL", "ATTACK", "HTTP", "UDP")}
    masks.update(by_protocol(d["rows"]))
    for name, mask in routes.items():
        for label, g in labels.items():
            masks[f"{name} / {label}"] = mask & g
    args = d["views"], d["q"], d["expansion"]
    metrics_rows = []
    for name, pred in predictions.items():
        result = metrics(pool, d["rows"], pred, *args, d["population"], group_masks=masks)
        metrics_rows.extend(dict(config=name, **r) for r in result)
    cells = []
    for left, right in comparisons:
        result = paired(pool, d["rows"], predictions[left], predictions[right], *args, group_masks=masks)
        cells.extend(dict(left=left, right=right, **r) for r in result)
    return metrics_rows, cells


def views_by_outcome(pool, d, geo):
    import analysis_core as ac

    records = []
    guards = ac.guard(d["q"])
    label = np.array([r["label"] for r in d["rows"]])
    role = np.array([r.get("source_role", "") for r in d["rows"]])
    group = {"NORMAL": label == 0, "ATTACK": label == 1}
    if pool == "EDGE":
        group.update(HTTP=role == "HTTP", UDP=role == "UDP")
    for view, (ix, w) in d["views"].items():
        for name, mask in group.items():
            for stratum, g in (("ALL", True), ("GUARD_ON", guards), ("GUARD_OFF", ~guards)):
                valid = mask & g
                for pathway in ("new_positive_from_zero", "stronger_existing_dual", "equal_or_zero"):
                    ii = ix[(valid & (geo["pathway"] == pathway))[ix]]
                    for j, h in enumerate(HEADS):
                        a = geo["k2"][ii, j]
                        b = geo["k1"][ii, j]
                        records.append(
                            dict(
                                pool=pool,
                                view=view,
                                head=h,
                                group=name,
                                guard_stratum=stratum,
                                pathway=pathway,
                                rows=len(ii),
                                weighted_denominator=float(w[ii].sum()),
                                lower_score=int(geo["reduced_scores"][ii, j].sum()),
                                withdrawn=int((a & ~b).sum()),
                                added=int((~a & b).sum()),
                                weighted_withdrawn=float(w[ii][a & ~b].sum()),
                            )
                        )
    return records
