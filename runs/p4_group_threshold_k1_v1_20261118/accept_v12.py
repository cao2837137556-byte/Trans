"""Cross-check each formal arm, attribution sums, and the audited donor denominators."""

from collections import defaultdict

from common_round1 import load, require
from paired_stats import check_pairs, csv_read

TASKS = ("preflight", "groups", "k1", "ports")
HEADS = ("27", "127", "227", "ensemble")
G = "GROUP_SOURCE_FALLBACK"
S = "GROUP_POOL_FALLBACK"
P = "RECAL_WITH_GUARD"
K = "P4_MAIN"
ONE = "P4_SINGLE_COMPONENT"


def totals_key(row):
    return tuple(row[k] for k in ("pool", "view", "head", "group", "guard_stratum"))


def verify_results(out, assets):
    counts = {}
    for mode in ("GROUP", "K1"):
        metrics = csv_read(out / (mode + "_METRICS.csv"))
        pairs = csv_read(out / (mode + "_PAIRS.csv"))
        heads = check_pairs(metrics, pairs, subset=mode == "K1")
        printed = csv_read(out / (mode + "_HEADLINE.csv"))
        require([{k: str(v) for k, v in r.items()} for r in heads] == printed, "HEADLINE_FROM_PAIRS:" + mode)
        idx = {(r["left"], r["right"], *totals_key(r)): r for r in pairs}
        required = {(K, ONE)} if mode == "K1" else {(a, b) for a in ("RAW", P, K) for b in (G, S)} | {(G, S)}
        require({k[:2] for k in idx} == required, "COMPARISON_COVERAGE")
        require(
            {r["head"] for r in heads} == set(HEADS)
            and {r["pool"] for r in heads} == {"CIC_DEV", "UNSW_DEV", "EDGE"},
            "POOL_HEAD_COVERAGE",
        )
        counts[mode] = idx
    gp = counts["GROUP"]
    for key, r in gp.items():
        if key[5] not in ("NORMAL", "ATTACK", "HTTP", "UDP"):
            continue
        sub = [
            gp.get((*key[:5], "APPLIED_" + route + " / " + key[5], key[6]))
            for route in ("PRE_OPEN", "BYPASS", "FIT", "EMPTY", "ALL_BYPASS", "SMALL")
        ]
        for f in ("rows", "n01", "n10", "n11", "n00"):
            require(sum(int(x[f]) for x in sub if x is not None) == int(r[f]), "GROUP_ROUTE_PARTITION")
    path_rows = csv_read(out / "K1_PATHWAYS.csv")
    withdrawals = {(*totals_key(r), r["pathway"]): int(r["withdrawn"]) for r in path_rows}
    by_key = defaultdict(lambda: [0, 0])
    for r in path_rows:
        v = by_key[totals_key(r)]
        v[0] += int(r["rows"])
        v[1] += int(r["withdrawn"])
        require(
            int(r["added"]) == 0 and int(r["withdrawn"]) <= int(r["lower_score"]) <= int(r["rows"]),
            "K1_PATHWAY_COUNTS",
        )
    kp = counts["K1"]
    for key, (n, loss) in by_key.items():
        row = kp.get((K, ONE, *key))
        require(
            (n == loss == 0) if row is None else (int(row["rows"]) == n and int(row["n10"]) == loss),
            "K1_PATHWAY_PARTITION",
        )
    port = csv_read(out / "PORT_HEADLINE.csv")
    index = {(r["scope"], *totals_key(r)): r for r in port}
    require(len(index) == len(port), "DUPLICATE_PORT_CELL")
    for key, r in index.items():

        def num(k):
            return int(r[k])

        same = num("same_ips_ports_differ")
        require(
            num("rows") == num("no_second_ranked") + num("two_legal_outside") + num("two_compatible")
            and num("no_second_ranked")
            == num("reference_not_open") + num("open_geometry_unavailable") + num("open_ready_too_few")
            and num("ranked_two") == num("two_legal_outside") + num("two_compatible")
            and num("two_legal_outside")
            == num("outside_unknown") + num("outside_different_ips") + num("outside_same_ips_ports_differ")
            and num("ranked_same_ips_ports_differ") == num("outside_same_ips_ports_differ") + same
            and num("ranked_identified")
            == num("ranked_two") - num("outside_unknown") - num("identity_unknown")
            and num("two_compatible") == num("identity_unknown") + num("different_ip_pair") + same
            and num("identified_compatible_pairs") == num("different_ip_pair") + same
            and same
            == num("one_endpoint_port_differs") + num("both_endpoint_ports_differ")
            == num("port_only_exactly_two_legal") + num("port_only_more_than_two_legal")
            and same == sum(num("local_" + k) for k in ("target_only", "peer_only", "both", "unknown"))
            and same
            == sum(num("handshake_" + k) for k in ("initiator_only", "responder_only", "both", "unknown")),
            "DONOR_AUDIT_PARTITION",
        )
        if key[0] == "K2_TO_K1":
            cell = kp.get((K, ONE, *key[1:]))
            require(num("rows") == (int(cell["n10"]) if cell else 0), "INDEPENDENT_PORT_AND_K1_COUNTS")
        if key[0] == "RAW_TO_K2":
            raw = gp.get(("RAW", G, *key[1:]))
            baseline = gp.get((K, G, *key[1:]))
            alarm_count = lambda c: int(c["n10"]) + int(c["n11"]) if c else 0
            require(num("rows") == alarm_count(raw) - alarm_count(baseline), "PORT_BASELINE_WITHDRAWALS")
        if key[0].startswith("K2_TO_K1_"):
            require(num("rows") == withdrawals[(*key[1:], key[0][len("K2_TO_K1_") :])], "PORT_PATHWAY_COUNTS")
    for r in assets["accepted_weak_mean_headlines"]:
        key = ("K2_TO_MEAN", r["pool"], r["view"], r["head"], r["group"], "ALL")
        require(int(index[key]["rows"]) == r["withdrawn"], "184893_PORT_BASELINE")
    seal = load(out / "GROUP_THRESHOLDS.json")
    for pool, v in seal["pools"].items():
        for f in v["groups"].values():
            for head, c in f["heads"].items():
                j = HEADS.index(head)
                if f["reason"] == "FIT":
                    require(
                        c["primary"]["origin"] == c["sensitivity"]["origin"] == "GROUP_FIT"
                        and c["primary"]["cut"] == c["sensitivity"]["cut"]
                        and c["primary"]["strict_mass"] <= 0.01 + 1e-14,
                        "SEALED_GROUP_FIT",
                    )
                else:
                    require(
                        c["primary"]["cut"] == seal["source_cuts"][j]
                        and c["sensitivity"]["cut"] == v["pooled"][j],
                        "SEALED_GROUP_FALLBACK",
                    )
    return dict(
        group_pair_cells=len(gp),
        k1_pair_cells=len(kp),
        donor_cells=len(port),
        mechanism_cells=len(path_rows),
        subset_violations=0,
    )


def paper(out, jobs):
    group = csv_read(out / "GROUP_HEADLINE.csv")
    k1 = csv_read(out / "K1_HEADLINE.csv")
    port = csv_read(out / "PORT_HEADLINE.csv")

    def chosen(r):
        return r["head"] == "ensemble" and (
            r["view"] == "post_window_primary"
            if r["pool"] != "EDGE"
            else r["group"] in ("NORMAL", "HTTP", "UDP")
        )

    def where(rows, **choice):
        return [r for r in rows if chosen(r) and all(r[k] == v for k, v in choice.items())]

    m = where(k1, left=K, right=ONE)
    normal = sum(int(r["withdrawn"]) for r in m if r["group"] == "NORMAL")
    attacks = sum(int(r["withdrawn"]) for r in m if r["group"] != "NORMAL")
    group_names = {"CIC_DEV": "CIC 建档后", "UNSW_DEV": "UNSW 建档后", "EDGE": "Edge 选中查询"}
    label_names = {"NORMAL": "正常", "ATTACK": "攻击", "HTTP": "HTTP", "UDP": "UDP"}
    agg = [r for r in port if chosen(r) and r["scope"] == "K2_TO_K1" and r["guard_stratum"] == "ALL"]
    eligible = sum(int(r["two_compatible"]) for r in agg)
    known = sum(int(r["identified_compatible_pairs"]) for r in agg)
    same = sum(int(r["same_ips_ports_differ"]) for r in agg)
    seal = load(out / "GROUP_THRESHOLDS.json")
    udp = next(f for f in seal["pools"]["EDGE"]["groups"].values() if f["protocol"] == 17)
    edge = next(r for r in where(group, left=P, right=G) if r["pool"] == "EDGE" and r["group"] == "UDP")
    lines = [
        "# v12 原模型补证结果",
        "",
        f"复用同一开发对照库、冻结 MLP 和源阈值，单组件最近邻较原双组件规则在三种子集成上额外撤回 {normal:,} 条正常误报和 {attacks:,} 条原有攻击告警。CIC 与 UNSW 采用建档后视图，Edge 采用选中查询。"
        f"在这些撤回中，{eligible:,} 条原已匹配两个组件，{known:,} 条可核对两个供体的 IP 对，其中 {same:,} 条的 IP 对相同、端口组合不同。该计数描述原来的两名最近供体。",
        "",
        f"使用测试床级阈值时，Edge UDP 检出 {int(edge['left_alarms']):,} 条。设备 × 协议主对照检出 {int(edge['right_alarms']):,} 条。该组有 {udp['reference_rows']} 条正常参考，有效参考量为 {udp['n_eff']:.2f}，主对照采用源阈值，这部分结果计入小样本回退。",
        "",
        "|测试床和视图|查询组|基础头|测试床级阈值|分组阈值（源回退）|分组阈值（测试床回退）|双组件|单组件|",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for r in m:
        k = (r["pool"], r["group"])

        def cell(arm):
            a = next(v for v in where(group, left="RAW", right=arm) if (v["pool"], v["group"]) == k)
            return int(a["right_alarms"]), int(a["left_alarms"])

        g, raw = cell(G)
        s, _ = cell(S)
        pooled = next(v for v in where(group, left=P, right=G) if (v["pool"], v["group"]) == k)
        lines.append(
            f"|{group_names[k[0]]}|{label_names[k[1]]}（{int(r['rows']):,}）|{raw:,}|{int(pooled['left_alarms']):,}|{g:,}|{s:,}|{int(r['left_alarms']):,}|{int(r['right_alarms']):,}|"
        )
    lines += [
        "",
        "预检、分组阈值、单组件、端口审计作业依次为 " + "、".join(jobs[p] for p in TASKS) + "。",
        "",
        "[分组阈值配对](GROUP_PAIRS.csv) · [实际分组阈值与来源](GROUP_THRESHOLDS.json) · "
        "[单组件配对](K1_PAIRS.csv) · [新获支持与既有支持增强](K1_PATHWAYS.csv) · "
        "[供体分母及未定角色](PORT_HEADLINE.csv) · [设备与协议明细](PORT_BY_DEVICE.csv) · [正式验收](ACCEPTANCE.json)",
    ]
    return "\n".join(lines) + "\n"
