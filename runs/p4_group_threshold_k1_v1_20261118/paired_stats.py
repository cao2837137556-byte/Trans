"""Portable acceptance checks for both directions of a weighted paired comparison."""

import csv
from pathlib import Path

from common_round1 import require

KEYS = ("pool", "view", "head", "group", "guard_stratum")


def check_pairs(metric_rows, cells, *, subset=False):
    indexed = {(r["config"], *(r[k] for k in KEYS)): r for r in metric_rows}
    require(len(indexed) == len(metric_rows), "DUPLICATE_METRIC")
    headlines = []
    observed = set()
    for p in cells:
        key = tuple(p[k] for k in KEYS)
        unique = (p["left"], p["right"], *key)
        require(unique not in observed, "DUPLICATE_PAIRED_CELL")
        observed.add(unique)
        a, b = (indexed[(p[n], *key)] for n in ("left", "right"))
        n00, n10, n01, n11 = (int(p["n" + v]) for v in ("00", "10", "01", "11"))
        require(
            int(a["rows"]) == int(b["rows"]) == int(p["rows"]) == n00 + n01 + n10 + n11
            and int(a["alarm_count"]) == n10 + n11
            and int(b["alarm_count"]) == n01 + n11
            and (not subset or n01 == 0),
            "PAIRED_MARGINALS_OR_SUBSET",
        )
        for r, cell in ((a, "10"), (b, "01")):
            require(
                abs(float(r["weighted_denominator"]) - float(p["weighted_denominator"])) <= 2e-10
                and abs(
                    float(r["weighted_numerator"]) - float(p["weighted_n11"]) - float(p["weighted_n" + cell])
                )
                <= 2e-10,
                "WEIGHTED_PAIRED_MARGINALS",
            )
            if r.get("HT_denominator") not in (None, ""):
                rate = (float(p["ht_n11"]) + float(p["ht_n" + cell])) / int(r["HT_denominator"])
                require(abs(rate - float(r["HT_rate"])) <= 2e-10, "EDGE_HT_PAIRED_MARGINALS")
        if p["guard_stratum"] == "GUARD_ON":
            require(n10 == n01 == 0, "BYPASS_DECISION_CHANGE")
        if p["group"] in ("NORMAL", "ATTACK", "HTTP", "UDP") and p["guard_stratum"] == "ALL":
            headlines.append(
                dict(
                    pool=p["pool"],
                    view=p["view"],
                    head=p["head"],
                    group=p["group"],
                    left=p["left"],
                    right=p["right"],
                    rows=int(p["rows"]),
                    left_alarms=n10 + n11,
                    right_alarms=n01 + n11,
                    withdrawn=n10,
                    added=n01,
                )
            )
    return headlines


def expected_cells(current, original, configs):
    def key(r):
        return (r["config"], *(r[k] for k in KEYS))

    current = {key(r): r for r in current if r["config"] in configs}
    expected = [r for r in original if r["config"] in configs]
    require(expected and len(set(key(r) for r in expected)) == len(expected), "BASELINE_CELL_SET")
    for e in expected:
        a = current[key(e)]
        for k in ("rows", "alarm_count", "HT_denominator"):
            require(a.get(k) == e.get(k), "BASELINE_COUNT:" + str(key(e)))
        for k in (
            "sample_rate",
            "weighted_numerator",
            "weighted_denominator",
            "hierarchical_rate",
            "ht_alarm_total",
            "ht_selected_expansion_total",
            "HT_rate",
        ):
            if k in e:
                require(abs(a[k] - e[k]) <= 2e-10, "BASELINE_VALUE:" + k)
    return len(expected)


def csv_write(path, rows, empty_fields=()):
    fields = list(dict.fromkeys(k for r in rows for k in r)) or list(empty_fields)
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def csv_read(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
