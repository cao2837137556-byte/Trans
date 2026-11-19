"""Count only paired original positives in A/B/W. Missing identity is not a zero outcome."""

import csv
from pathlib import Path

from common_ton import HEADS, LAYERS, require

MAIN = "主分析：跨抓包同目标身份有独立证据"
LOGICAL = "补充分析：按逻辑主机配对"
BLANK = ""
COUNTS = (
    "A",
    "B",
    "W",
    "retained",
    "normal_fp_raw",
    "normal_fp_ccnr",
    "normal_fp_reduced",
    "attack_n",
    "normal_n",
    "not_open",
    "open_no_support",
    "positive_support",
    "actual_deduction",
    "attack_not_open",
    "attack_open_no_support",
    "attack_actual_deduction",
    "normal_not_open",
    "normal_open_no_support",
    "normal_actual_deduction",
)


def rate(n, d):
    return n / d if d else "不适用"


def fill(row, tally):
    a, b, w = (int(tally[k]) for k in ("A", "B", "W"))
    require(
        0 <= w <= b <= a <= int(tally["attack_n"])
        and int(tally["retained"]) == a - w
        and int(tally["normal_fp_reduced"])
        == int(tally["normal_fp_raw"]) - int(tally["normal_fp_ccnr"])
        >= 0,
        "PAIRED_COUNTS",
    )
    row.update({k: int(tally[k]) for k in COUNTS})
    row.update(
        overall_retention=rate(a - w, a),
        withdrawal_given_positive_support=rate(w, b),
        withdrawal_among_raw_positives=rate(w, a),
    )
    return row


def empty(row):
    row.update({k: "未评价" for k in COUNTS})
    row.update(
        overall_retention="未评价",
        withdrawal_given_positive_support="未评价",
        withdrawal_among_raw_positives="未评价",
    )
    return row


def build_tables(host, data, support, scores, base, ccnr, open_mask, protocol_ready, card, admission):
    import numpy as np

    def flags(x):
        return np.asarray(x, dtype=bool)

    attack = flags([r["kind"] == "attack" for r in data])
    normal = ~attack
    off = flags([r["off"] for r in data])
    payload = flags([r["data"] for r in data])
    cross = flags([r["crossing"] for r in data])
    connections = np.asarray([r["conn"] for r in data], dtype=object)
    cuts = np.asarray(admission["cuts"])
    pred = ccnr > cuts if ccnr is not None else None
    if pred is not None:
        require(np.array_equal(pred[~off], base[~off]) and not np.any(pred & ~base), "CCNR_BYPASS_AND_SUBSET")
    reasons = {(x["host"], x["kind"], x["layer"]): x for x in admission["counts"]}
    outputs = {k: [] for k in ("raw", "main", "supplement", "boundary")}
    for j, h in enumerate(HEADS):
        for layer, take in zip(LAYERS, (np.ones(len(data), bool), off, off & payload)):
            att = take & attack
            norm = take & normal
            tp = int(base[att, j].sum())
            fp = int(base[norm, j].sum())
            arow = reasons.get((host, "attack", layer), {})
            nrow = reasons.get((host, "normal", layer), {})
            item = dict(
                host=host,
                logical_role=card["hosts"][host]["role"],
                head=h,
                layer=layer,
                attack_candidates=int(arow.get("candidate", 0)),
                attack_candidate_connections=int(arow.get("candidate_connections", 0)),
                attack_included=int(att.sum()),
                attack_excluded=int(arow.get("candidate", 0)) - int(att.sum()),
                attack_connections=len(set(connections[att])),
                TP=tp,
                FN=int(att.sum()) - tp,
                TPR=rate(tp, int(att.sum())),
                normal_candidates=int(nrow.get("candidate", 0)),
                normal_candidate_connections=int(nrow.get("candidate_connections", 0)),
                normal_included=int(norm.sum()),
                normal_excluded=int(nrow.get("candidate", 0)) - int(norm.sum()),
                normal_connections=len(set(connections[norm])),
                FP=fp,
                FPR=rate(fp, int(norm.sum())),
            )
            item["attack_connections_with_detection"] = len(set(connections[att & base[:, j]]))
            item["attack_connections_entirely_missed"] = (
                item["attack_connections"] - item["attack_connections_with_detection"]
            )
            item["normal_connections_with_false_alarm"] = len(set(connections[norm & base[:, j]]))
            outputs["raw"].append(item)
            if pred is None:
                continue
            for boundary, mask in [
                ("CROSSES_NORMAL_FILE_BOUNDARY", cross),
                ("FIRST_SEEN_IN_NORMAL_2", ~cross),
            ]:
                ix = norm & mask
                outputs["boundary"].append(
                    dict(
                        host=host,
                        head=h,
                        layer=layer,
                        boundary=boundary,
                        normal_n=int(ix.sum()),
                        normal_connections=len(set(connections[ix])),
                        raw_fp=int(base[ix, j].sum()),
                        logical_paired_n=int((ix & protocol_ready).sum()),
                        logical_ccnr_fp=int(pred[ix & protocol_ready, j].sum()),
                    )
                )
            for key, label in [("main", MAIN), ("supplement", LOGICAL)]:
                spec = card["hosts"][host]
                row = dict(
                    analysis=label,
                    host=host,
                    logical_role=spec["role"],
                    head=h,
                    layer=layer,
                    reverse_sll_changed=spec["reverse_sll_changed"],
                    raw_attack_included=int(att.sum()),
                    raw_normal_included=int(norm.sum()),
                )
                if key == "main" and spec["main_identity"] != "CONFIRMED":
                    outputs[key].append(empty(dict(row, status="未评价", reason="跨抓包同目标身份未证实")))
                    continue
                if not admission["ready"]:
                    outputs[key].append(
                        empty(dict(row, status="未评价", reason="同目标或同协议的两小时正常参考不足"))
                    )
                    continue
                pair = take & protocol_ready
                ia = pair & attack
                inn = pair & normal
                positive = support > 0
                deduct = ccnr[:, j] < scores[:, j]
                hit = ia & base[:, j]
                withdrawn = hit & ~pred[:, j]
                require(not np.any(withdrawn & ~positive), "WITHDRAWAL_WITHOUT_SUPPORT")
                tally = dict(
                    A=int(hit.sum()),
                    B=int((hit & positive).sum()),
                    W=int(withdrawn.sum()),
                    retained=int((hit & pred[:, j]).sum()),
                    attack_n=int(ia.sum()),
                    normal_n=int(inn.sum()),
                    normal_fp_raw=int(base[inn, j].sum()),
                    normal_fp_ccnr=int(pred[inn, j].sum()),
                    normal_fp_reduced=int((inn & base[:, j] & ~pred[:, j]).sum()),
                    not_open=int((pair & ~open_mask).sum()),
                    open_no_support=int((pair & open_mask & ~positive).sum()),
                    positive_support=int((pair & positive).sum()),
                    actual_deduction=int((pair & deduct).sum()),
                    attack_not_open=int((ia & ~open_mask).sum()),
                    attack_open_no_support=int((ia & open_mask & ~positive).sum()),
                    attack_actual_deduction=int((ia & deduct).sum()),
                    normal_not_open=int((inn & ~open_mask).sum()),
                    normal_open_no_support=int((inn & open_mask & ~positive).sum()),
                    normal_actual_deduction=int((inn & deduct).sum()),
                )
                outputs[key].append(fill(dict(row, status="已评价", reason=""), tally))
    return outputs


def aggregate(rows):
    total = []
    for head in HEADS:
        for layer in LAYERS:
            rr = [r for r in rows if r["head"] == head and r["layer"] == layer and r["host"] != "ALL"]
            valid = [r for r in rr if r["status"] == "已评价"]
            base = dict(
                analysis=rr[0]["analysis"],
                host="ALL",
                logical_role="合格目标合计",
                head=head,
                layer=layer,
                reverse_sll_changed="见逐目标行",
                raw_attack_included=sum(int(r["raw_attack_included"]) for r in rr),
                raw_normal_included=sum(int(r["raw_normal_included"]) for r in rr),
                paired_hosts=len(valid),
            )
            if valid:
                total.append(
                    fill(
                        dict(base, status="已评价", reason=""),
                        {k: sum(int(r[k]) for r in valid) for k in COUNTS},
                    )
                )
            else:
                total.append(empty(dict(base, status="未评价", reason="没有可配对的目标")))
    return total


def read_table(p):
    with Path(p).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def verify(out, card):
    raw = read_table(out / "RAW_TARGETS.csv")
    look = {(r["host"], r["head"], r["layer"]): r for r in raw}
    require(len(look) == len(raw) == len(card["hosts"]) * 4 * 3, "RAW_TARGET_HEAD_LAYER_COVERAGE")
    for r in raw:
        require(
            int(r["TP"]) + int(r["FN"]) == int(r["attack_included"])
            and int(r["FP"]) <= int(r["normal_included"])
            and int(r["attack_candidates"]) == int(r["attack_excluded"]) + int(r["attack_included"])
            and int(r["normal_candidates"]) == int(r["normal_excluded"]) + int(r["normal_included"]),
            "RAW_MARGINALS",
        )
    boundary = read_table(out / "NORMAL_BOUNDARY.csv")
    for k, r in look.items():
        bs = [x for x in boundary if (x["host"], x["head"], x["layer"]) == k]
        require(
            len(bs) == 2
            and sum(int(x["normal_n"]) for x in bs) == int(r["normal_included"])
            and sum(int(x["raw_fp"]) for x in bs) == int(r["FP"]),
            "CROSS_FILE_PARTITION",
        )
    checked = 0
    for name, label in [("CCNR_MAIN.csv", MAIN), ("CCNR_PAIRED.csv", LOGICAL)]:
        rows = read_table(out / name)
        require(
            len(rows) == (len(card["hosts"]) + 1) * 4 * 3 and all(r["analysis"] == label for r in rows),
            "PAIR_TABLE_COVERAGE",
        )
        for r in rows:
            if r["status"] == "未评价":
                require(
                    all(r[k] == "未评价" for k in COUNTS) and r["overall_retention"] == "未评价",
                    "MISSING_NOT_ZERO",
                )
            else:
                rebuilt = fill({}, r)
                for k in (
                    "overall_retention",
                    "withdrawal_given_positive_support",
                    "withdrawal_among_raw_positives",
                ):
                    require(str(rebuilt[k]) == str(r[k]), "RATE_DENOMINATOR:" + k)
                if r["host"] != "ALL":
                    base = look[r["host"], r["head"], r["layer"]]
                    require(
                        int(r["A"]) <= int(base["TP"]) and int(r["normal_fp_raw"]) <= int(base["FP"]),
                        "RAW_PAIRED_BINDING",
                    )
                    if r["attack_n"] == base["attack_included"]:
                        require(r["A"] == base["TP"], "RAW_ATTACK_COMPLETE_PAIR")
                    if r["normal_n"] == base["normal_included"]:
                        require(r["normal_fp_raw"] == base["FP"], "RAW_NORMAL_COMPLETE_PAIR")
            checked += 1
        for want in aggregate(rows):
            row = next(
                r
                for r in rows
                if r["host"] == "ALL" and r["head"] == want["head"] and r["layer"] == want["layer"]
            )
            require(
                all(
                    str(row[k]) == str(want[k])
                    for k in (*COUNTS, "overall_retention", "withdrawal_given_positive_support")
                ),
                "NO_DOUBLE_COUNTED_AGGREGATE",
            )
    return dict(raw_cells=len(raw), paired_cells=checked, boundary_cells=len(boundary))


def paper(out, card):
    rows = [r for r in read_table(out / "RAW_TARGETS.csv") if r["head"] == "ensemble" and r["layer"] == "all"]
    v = lambda k: sum(int(r[k]) for r in rows)
    strict = read_table(out / "CCNR_MAIN.csv")
    supp = read_table(out / "CCNR_PAIRED.csv")
    lines = [
        "# ToN-IoT 密码攻击 · 冻结 v12 诊断",
        "",
        f"四个登记目标共有 {v('attack_candidates'):,} 个密码攻击关联入站候选包，其中 {v('attack_included'):,} 个符合冻结输入资格。三种子集成检出 {v('TP'):,} 个，漏掉 {v('FN'):,} 个。同地址正常评价纳入 {v('normal_included'):,} 个包，误报 {v('FP'):,} 个。一个连接可贡献多个包，数据包数量不等于登录尝试次数。",
        "",
        "|登记目标|纳入攻击包／连接|检出|漏检|纳入正常包／连接|误报|",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"|{r['host']}（{r['logical_role']}）|{r['attack_included']}／{r['attack_connections']}|{r['TP']}|{r['FN']}|{r['normal_included']}／{r['normal_connections']}|{r['FP']}|"
        )
    for table, title in ((strict, MAIN), (supp, LOGICAL)):
        lines += ["", "## " + title, ""]
        if title == LOGICAL:
            lines.append(
                "四个地址在密码抓包中的回向 SLL 发送地址均与正常抓包不同。本表只放宽跨抓包身份定义。"
            )
        for k, name in [("off_bypass", "旁路外"), ("off_bypass_with_transport_data", "旁路外且带传输层数据")]:
            r = next(r for r in table if r["host"] == "ALL" and r["head"] == "ensemble" and r["layer"] == k)
            if r["status"] == "未评价":
                lines.append(f"{name}的 CCNR 未评价。{r['reason']}。")
            else:
                percent = lambda key: r[key] if r[key] == "不适用" else f"{100 * float(r[key]):.4f}%"
                lines.append(
                    f"{name}共 {int(r['attack_n']):,} 个可配对攻击包。基础头原有告警 A={r['A']}，其中获得正支持 B={r['B']}，实际误撤 W={r['W']}。总体保留率 {percent('overall_retention')}，获得正支持后的误撤率 {percent('withdrawal_given_positive_support')}。同层正常查询减少 {r['normal_fp_reduced']} 条误报。"
                )
    lines += [
        "",
        "[基础头逐目标与种子](RAW_TARGETS.csv) · [主分析](CCNR_MAIN.csv) · [按逻辑主机配对](CCNR_PAIRED.csv) · [正常跨文件连接](NORMAL_BOUNDARY.csv) · [输入资格](ADMISSION_COUNTS.csv) · [验收](ACCEPTANCE.json)",
    ]
    return "\n\n".join(lines[:3]) + "\n" + "\n".join(lines[3:]) + "\n"
