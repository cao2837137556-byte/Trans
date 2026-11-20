"""Connection-level statistics on cached packet decisions."""

from collections import Counter
import json
import numpy as np

LEVELS = (0.25, 0.20, 0.15, 0.10, 0.05, 0.0)
HEADS = ("27", "127", "227", "ensemble")
WIN = "192.168.1.195"
MID = "192.168.1.152"
NA = "不适用"
FLAGS = ("FIN", "SYN", "RST", "PSH", "ACK", "URG", "ECE", "CWR", "NS")


def require(value, message):
    if not value:
        raise ValueError(message)


def fraction(n, d):
    return n / d if d else NA


def predictions(d, method):
    raw = d["raw"]
    s = d["support"]
    off = d["off_bypass"]
    cuts = np.asarray(method["cuts"])
    gain = np.where(s > 0, 1.0 - np.power(1.0 - s, 4), 0.0)
    require(
        raw.shape == (len(s), 4)
        and np.isfinite(raw).all()
        and np.all((s >= 0) & (s <= 1))
        and tuple(method["heads"]) == HEADS
        and method["p"] == 4
        and method["lambda_value"] == 0.25,
        "FROZEN_METHOD",
    )
    previous = None
    for lam in LEVELS:
        x = raw[:, :3].copy()
        use = (gain > 0) & off
        for j, scale in enumerate(method["scales"]):
            x[use, j] = raw[use, j] - (lam * scale) * gain[use]
        score = np.column_stack((x, np.stack([x[:, j] for j in range(3)]).mean(axis=0, dtype=np.float64)))
        flags = score > cuts
        require(
            np.array_equal(score[~off], raw[~off]) and np.array_equal(flags[~off], d["raw_alarm"][~off]),
            "BYPASS",
        )
        if previous is not None:
            require(
                np.all(score >= previous) and not np.any((previous > cuts) & ~flags), "PACKET_MONOTONICITY"
            )
        if lam == 0.25:
            require(
                np.allclose(score, d["ccnr"], rtol=0, atol=2e-10) and np.array_equal(flags, d["ccnr_alarm"]),
                "REPRODUCE_025",
            )
        if lam == 0:
            require(np.array_equal(score, raw) and np.array_equal(flags, d["raw_alarm"]), "REPRODUCE_RAW")
        previous = score
        yield lam, flags


def by_connection(hits, indices, n):
    out = np.zeros((n, 4), dtype=bool)
    np.logical_or.at(out, indices, hits)
    return out


def classified_misses(d, ix, index, raw):
    n = len(raw)
    miss = ~raw[:, 3]
    has_data = np.zeros(n, bool)
    np.logical_or.at(has_data, index, d["transport_data"][ix])
    empty = miss & ~has_data
    with_data = int((miss & has_data).sum())
    # Each signature is a set of observed per-packet flag combinations, not a bitwise union.
    patterns = {}
    for row, cid in zip(ix[empty[index]], index[empty[index]]):
        code = int(d["flags"][row])
        name = (
            "UDP"
            if d["proto"][row] == 17
            else "+".join(f for bit, f in enumerate(FLAGS) if code & (1 << bit)) or "TCP_NO_FLAGS"
        )
        patterns.setdefault(int(cid), set()).add(name)
    signatures = Counter(" | ".join(sorted(v)) for v in patterns.values())
    total = int(miss.sum())
    zero = int(empty.sum())
    require(sum(signatures.values()) == zero and total == zero + with_data, "MISSED_PARTITION")
    return dict(
        attack_connections=n,
        raw_alerted=int(raw[:, 3].sum()),
        entirely_missed=total,
        zero_data_connections=zero,
        has_data_connections=with_data,
        pure_SYN_only=signatures["SYN"],
        other_zero_data=zero - signatures["SYN"],
        observed_flag_sets=dict(signatures),
    )


def quantiles(d, ix, index, in_cohort, host, cut):
    alarm = ix[d["raw_alarm"][ix, 3] & in_cohort[index]]
    order = alarm[np.argsort(d["frame"][alarm], kind="stable")]
    _, first = np.unique(d["conn"][order], return_index=True)
    n = int(in_cohort.sum())
    require(len(first) == n, "FIRST_RAW_ALARM_COVERAGE")
    out = []
    for unit, take in [("first_RAW_alarm_per_connection", order[first]), ("all_RAW_alarm_packets", alarm)]:
        r = dict(
            host=host,
            kind="attack" if host == WIN else "normal",
            weighting=unit,
            cohort_connections=n,
            original_alarm_packets=len(alarm),
            observations=len(take),
            quantile_method="linear",
        )
        margin = d["raw"][take, 3] - cut
        s = d["support"][take]
        require(
            np.all(margin > 0)
            and np.all(s > 0)
            and np.all(d["off_bypass"][take])
            and not d["ccnr_alarm"][take, 3].any(),
            "FULLY_WITHDRAWN_COHORT",
        )
        for label, x in [("margin", margin), ("support", s)]:
            pct = np.quantile(x, [0.25, 0.5, 0.75], method="linear") if len(x) else [NA] * 3
            r.update({label + "_" + k: v for k, v in zip(("P25", "median", "P75"), pct)})
        out.append(r)
    return out


def frozen_packet_marginals(d, host):
    packet_audit = []
    for kind in ("attack", "normal"):
        ix = np.flatnonzero(d["attack"] == (kind == "attack"))
        for label, mask in [
            ("all", np.ones(len(ix), bool)),
            ("off_bypass", d["off_bypass"][ix]),
            ("off_bypass_with_transport_data", d["off_bypass"][ix] & d["transport_data"][ix]),
        ]:
            jj = ix[mask]
            ng = len(np.unique(d["conn"][jj]))
            for k, h in enumerate(HEADS):
                hit = d["raw_alarm"][jj, k]
                cc = d["ccnr_alarm"][jj, k]
                packet_audit.append(
                    dict(
                        host=host,
                        head=h,
                        layer=label,
                        kind=kind,
                        N=len(jj),
                        connections=ng,
                        raw_positive=int(hit.sum()),
                        raw_positive_connections=len(np.unique(d["conn"][jj[hit]])),
                        B=int((hit & (d["support"][jj] > 0)).sum()),
                        withdrawn=int((hit & ~cc).sum()),
                        ccnr_positive=int(cc.sum()),
                    )
                )
    return packet_audit


def summarize_host(d, host, method, eligible):
    preds = dict(predictions(d, method))
    result = {(head, lam): dict(host=host, head=head, lambda_value=lam) for head in HEADS for lam in LEVELS}
    missed = None
    quant = []
    packet_audit = frozen_packet_marginals(d, host)
    for kind in ("attack", "normal"):
        ix = np.flatnonzero(d["attack"] == (kind == "attack"))
        ids, index = np.unique(d["conn"][ix], return_inverse=True)
        n = len(ids)
        raw = by_connection(d["raw_alarm"][ix], index, n)
        base = by_connection(d["ccnr_alarm"][ix], index, n)
        if kind == "attack":
            missed = classified_misses(d, ix, index, raw)
        if not eligible:
            continue
        require(d["reference_eligible"][ix].all(), "LOGICAL_PAIRABILITY")
        lost = raw & ~base
        if (host, kind) in ((WIN, "attack"), (MID, "normal")):
            quant.extend(quantiles(d, ix, index, lost[:, 3], host, method["cuts"][3]))
        previous = base
        for lam, p in preds.items():
            cur = by_connection(p[ix], index, n)
            require(not np.any(previous & ~cur) and not np.any(cur & ~raw), "CONNECTION_MONOTONICITY")
            restored = cur & ~base
            for j, h in enumerate(HEADS):
                slot = result[h, lam]
                for field, value in [
                    ("total", n),
                    ("raw_alerted", raw[:, j].sum()),
                    ("baseline_alerted", base[:, j].sum()),
                    ("alerted", cur[:, j].sum()),
                    ("fully_withdrawn_at_025", lost[:, j].sum()),
                    ("restored_vs_025", restored[:, j].sum()),
                ]:
                    slot[kind + "_" + field] = int(value)
            previous = cur
    return list(result.values()) if eligible else [], dict(host=host, **missed), quant, packet_audit


def finish_sweep(rows):
    fields = [k for k in rows[0] if k.startswith(("normal_", "attack_"))]
    totals = []
    for h in HEADS:
        for lam in LEVELS:
            group = [r for r in rows if r["head"] == h and r["lambda_value"] == lam]
            require({r["host"] for r in group} == {MID, WIN, "192.168.1.190"}, "THREE_PAIRED_HOSTS")
            total = dict(host="ALL", head=h, lambda_value=lam)
            total.update({k: sum(r[k] for r in group) for k in fields})
            total["windows10_attack_restored"] = next(
                r["attack_restored_vs_025"] for r in group if r["host"] == WIN
            )
            total["middleware_normal_realerted"] = next(
                r["normal_restored_vs_025"] for r in group if r["host"] == MID
            )
            totals.append(total)
    rows.extend(totals)
    for r in rows:
        r["analysis"] = "按逻辑主机配对（补充分析）"
        for kind in ("attack", "normal"):
            r[kind + "_restored_fraction"] = fraction(
                r[kind + "_restored_vs_025"], r[kind + "_fully_withdrawn_at_025"]
            )
    return rows


def finish_misses(rows):
    total = {"host": "ALL"}
    total.update({k: sum(r[k] for r in rows) for k in rows[0] if k not in ("host", "observed_flag_sets")})
    flags = Counter()
    for r in rows:
        flags.update(r["observed_flag_sets"])
    total["observed_flag_sets"] = dict(flags)
    rows.append(total)
    for r in rows:
        r["observed_flag_sets"] = json.dumps(r["observed_flag_sets"], sort_keys=True, separators=(",", ":"))
        for k in ("zero_data", "has_data"):
            r[k + "_fraction_of_missed"] = fraction(r[k + "_connections"], r["entirely_missed"])
    return rows
