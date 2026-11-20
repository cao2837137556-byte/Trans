"""Independent checks on the three returned tables, including their denominators."""

import csv
import json
import math

FILES = ("LAMBDA_CONNECTIONS.csv", "RAW_MISSED_CONNECTIONS.csv", "MARGIN_SUPPORT.csv")
SMALL = set(FILES) | {
    "INSTALL.json",
    "PREFLIGHT.json",
    "FORMAL.json",
    "ACCEPTANCE.json",
    "RESULTS_FOR_PAPER.md",
    "CONTROLLER_FAILURE.json",
}
for phase in ("preflight", "formal"):
    SMALL.update(
        f"{name}_{phase}.json"
        for name in (
            "SBATCH",
            "JOB",
            "SUBMIT_INTENT",
            "TEST_ONLY",
            "SCHEDULER",
            "FAILURE",
            "RUNTIME",
            "RESOURCES",
        )
    )

LEVELS = (0.25, 0.20, 0.15, 0.10, 0.05, 0.0)
HEADS = ("27", "127", "227", "ensemble")
WIN = "192.168.1.195"
MID = "192.168.1.152"
ORCH = "192.168.1.190"
W7 = "192.168.1.193"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def is_ratio(v, n, d):
    return abs(float(v) - n / d) <= 1e-14 if d else v == "不适用"


def validate(one, two, three, *, formal=True):
    paired = (MID, ORCH, WIN)
    hosts = (*paired, "ALL")
    lookup = {(r["host"], r["head"], float(r["lambda_value"])): r for r in one}
    require(
        len(lookup) == len(one) == 4 * 4 * 6
        and set(lookup) == {(h, s, l) for h in hosts for s in HEADS for l in LEVELS},
        "SWEEP_SCOPE",
    )
    for host in hosts:
        for seed in HEADS:
            for kind in ("attack", "normal"):
                key = lambda lam: lookup[host, seed, lam]

                def count(r, field):
                    return int(r[kind + "_" + field])

                old = count(key(0.25), "alerted")
                raw = count(key(0.0), "alerted")
                last = old
                for lam in LEVELS:
                    r = key(lam)
                    v = count(r, "alerted")
                    n = count(r, "total")
                    gain = count(r, "restored_vs_025")
                    lost = count(r, "fully_withdrawn_at_025")
                    require(
                        r["analysis"] == "按逻辑主机配对（补充分析）"
                        and 0 <= old <= last <= v <= raw <= n
                        and n == count(key(0.25), "total")
                        and count(r, "baseline_alerted") == old
                        and count(r, "raw_alerted") == raw
                        and gain == v - old
                        and lost == raw - old
                        and is_ratio(r[kind + "_restored_fraction"], gain, lost),
                        "CONNECTION_MARGINALS",
                    )
                    last = v
                    if host == "ALL":
                        for field in (
                            "total",
                            "raw_alerted",
                            "baseline_alerted",
                            "alerted",
                            "restored_vs_025",
                            "fully_withdrawn_at_025",
                        ):
                            require(
                                count(r, field) == sum(count(lookup[h, seed, lam], field) for h in paired),
                                "SUM_HOSTS",
                            )
                        require(
                            int(r["windows10_attack_restored"])
                            == int(lookup[WIN, seed, lam]["attack_restored_vs_025"])
                            and int(r["middleware_normal_realerted"])
                            == int(lookup[MID, seed, lam]["normal_restored_vs_025"]),
                            "TRADEOFF_COLUMN",
                        )
    missed = {r["host"]: r for r in two}
    require(len(missed) == len(two) == 5 and set(missed) == {*hosts, W7}, "RAW_FOUR_HOSTS")
    for host, r in missed.items():
        n, hit, loss, empty, data, pure, other = [
            int(r[k])
            for k in (
                "attack_connections",
                "raw_alerted",
                "entirely_missed",
                "zero_data_connections",
                "has_data_connections",
                "pure_SYN_only",
                "other_zero_data",
            )
        ]
        flags = json.loads(r["observed_flag_sets"])
        require(
            n == hit + loss
            and loss == empty + data
            and empty == pure + other == sum(flags.values())
            and pure == flags.get("SYN", 0)
            and is_ratio(r["zero_data_fraction_of_missed"], empty, loss)
            and is_ratio(r["has_data_fraction_of_missed"], data, loss),
            "RAW_MISSED_PARTITION",
        )
        if host in paired:
            require(
                n == int(lookup[host, "ensemble", 0]["attack_total"])
                and hit == int(lookup[host, "ensemble", 0]["attack_alerted"]),
                "CROSS_TABLE_RAW",
            )
    tot = missed["ALL"]
    for field in (
        "attack_connections",
        "raw_alerted",
        "entirely_missed",
        "zero_data_connections",
        "has_data_connections",
        "pure_SYN_only",
        "other_zero_data",
    ):
        require(int(tot[field]) == sum(int(missed[h][field]) for h in (*paired, W7)), "MISSED_HOST_SUM")
    if formal:
        require(
            tuple(int(tot[k]) for k in ("attack_connections", "raw_alerted", "entirely_missed"))
            == (76677, 61866, 14811),
            "FROZEN_RAW_COUNTS",
        )
        require(
            int(lookup["ALL", "ensemble", 0]["attack_total"]) == 71436
            and int(lookup["ALL", "ensemble", 0]["normal_total"]) == 96,
            "PAIRED_CONNECTION_COUNTS",
        )
    require(
        len(three) == 4
        and {(r["host"], r["weighting"]) for r in three}
        == {(h, v) for h in (MID, WIN) for v in ("first_RAW_alarm_per_connection", "all_RAW_alarm_packets")},
        "QUANTILE_SCOPE",
    )
    for host, kind in ((WIN, "attack"), (MID, "normal")):
        pair = [r for r in three if r["host"] == host]
        require(len({int(r["original_alarm_packets"]) for r in pair}) == 1, "SAME_COHORT_PACKET_COUNT")
        for r in pair:
            n = int(r["cohort_connections"])
            packets = int(r["original_alarm_packets"])
            obs = int(r["observations"])
            require(
                r["kind"] == kind
                and r["quantile_method"] == "linear"
                and n == int(lookup[host, "ensemble", 0.25][kind + "_fully_withdrawn_at_025"])
                and n <= packets
                and obs == (n if r["weighting"].startswith("first_") else packets),
                "COHORT_DENOMINATOR",
            )
            for key in ("margin", "support"):
                vals = [r[key + "_" + p] for p in ("P25", "median", "P75")]
                if n:
                    lo, med, hi = map(float, vals)
                    require(
                        0 < lo <= med <= hi and math.isfinite(hi) and (key != "support" or hi <= 1),
                        "QUANTILE_VALUE",
                    )
                else:
                    require(vals == ["不适用"] * 3 and packets == 0, "EMPTY_QUANTILES")
    return dict(
        sweep_rows=len(one),
        raw_rows=len(two),
        quantile_rows=len(three),
        ensemble_missed=int(tot["entirely_missed"]),
    )


def tables_read(out):
    t = []
    for n in FILES:
        with (out / n).open(encoding="utf8", newline="") as f:
            t.append(list(csv.DictReader(f)))
    return t, validate(*t)


def paper(one, two, three):
    totals = [r for r in one if r["host"] == "ALL" and r["head"] == "ensemble"]
    r = next(x for x in two if x["host"] == "ALL")
    lines = [
        "# ToN 密码攻击连接级诊断",
        "",
        "在三台按固定 IP 和登记角色配对的逻辑主机上，保持 p=4，以 λ=0.25 为共同对照。下表列出全部合格入站包上，整条连接从零告警变为至少一次告警的数量。严格跨实例主分析的 CCNR 未评价。",
        "",
        "|λ|恢复的攻击连接|重新误报的正常连接|Windows 10 恢复攻击连接|中间件服务器重新误报正常连接|",
        "|---:|---:|---:|---:|---:|",
    ]
    for x in totals:
        lines.append(
            f"|{x['lambda_value']}|{x['attack_restored_vs_025']}|{x['normal_restored_vs_025']}|{x['windows10_attack_restored']}|{x['middleware_normal_realerted']}|"
        )
    lines += [
        "",
        f"按四目标基础头计，76,677 条攻击关联连接中 61,866 条至少告警一次，14,811 条全程漏检。在后者中，{int(r['zero_data_connections']):,} 条的所有合格入站包均无传输层数据（其中 {int(r['pure_SYN_only']):,} 条仅观察到纯 SYN），{int(r['has_data_connections']):,} 条至少有一个带传输层数据的入站包。",
        "",
        "|原版完全撤警队列|统计单位|连接数|包数／观测数|裕度 P25／中位／P75|支持度 P25／中位／P75|",
        "|---|---|---:|---:|---|---|",
    ]
    for x in three:
        fmt = lambda v: v if v == "不适用" else f"{float(v):.6g}"
        trip = lambda k: " / ".join(fmt(x[k + "_" + v]) for v in ("P25", "median", "P75"))
        who = "Windows 10 攻击" if x["host"] == WIN else "中间件服务器正常"
        unit = "每连接首个原告警" if x["weighting"].startswith("first_") else "全部原告警包"
        lines.append(
            f"|{who}|{unit}|{x['cohort_connections']}|{x['observations']}|{trip('margin')}|{trip('support')}|"
        )
    lines += [
        "",
        "分位数使用线性插值。上述 λ 比较是原 ToN 缓存上的敏感性分析，冻结 v12 的 λ 仍为 0.25。",
        "",
        "[表 1 · 扣分与连接恢复](LAMBDA_CONNECTIONS.csv) · [表 2 · RAW 全漏](RAW_MISSED_CONNECTIONS.csv) · [表 3 · 裕度和正常支持](MARGIN_SUPPORT.csv)",
    ]
    return "\n".join(lines) + "\n"
