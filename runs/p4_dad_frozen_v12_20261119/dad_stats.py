"""Summarize original alerts and actual paired withdrawals on identical packet UIDs."""

import csv

HEADS = ("27", "127", "227", "ensemble")
COUNTS = {"mon": 8448, "sun": 9325, "wed": 104, "thu": 56, "fri": 192, "sat": 192}
ATTACK = ("wed", "thu", "fri", "sat")
NAMES = {
    "mon": "周一建档后正常",
    "sun": "周日纯正常",
    "normal": "两天正常合计",
    "wed": "周三修改",
    "thu": "周四复制",
    "fri": "周五混合",
    "sat": "周六混合",
    "attack": "攻击合计",
}
SMALL = {
    "INSTALL.json",
    "PREFLIGHT.json",
    "FORMAL.json",
    "ACCEPTANCE.json",
    "RUNTIME_preflight.json",
    "RUNTIME_formal.json",
    "DATA_BINDING.json",
    "ARTIFACT_SHA.json",
    "DAILY_METRICS.csv",
    "THURSDAY_DUPLICATION.csv",
    "TUESDAY_DIAGNOSTIC.json",
    "RESULTS_FOR_PAPER.md",
    "CONTROLLER_FAILURE.json",
}
for phase in ("preflight", "formal"):
    SMALL.update(
        f"{s}_{phase}.json"
        for s in ("SBATCH", "JOB", "SUBMIT_INTENT", "TEST_ONLY", "SCHEDULER", "FAILURE", "RESOURCES")
    )


def require(ok, message):
    if not ok:
        raise ValueError(message)


def ratio(n, d):
    return n / d if d else "不适用"


def table(rows, raw, corrected, support, guard, cuts):
    import numpy as np

    a, b = raw > cuts, corrected > cuts
    require(
        np.isfinite(raw).all()
        and np.isfinite(corrected).all()
        and np.isfinite(support).all()
        and np.all((support >= 0) & (support <= 1))
        and np.all(corrected <= raw)
        and not np.any(b & ~a)
        and np.array_equal(raw[guard], corrected[guard])
        and np.array_equal(raw[support == 0], corrected[support == 0]),
        "PAIRED_DECISION_INVARIANTS",
    )
    days = np.array([r["capture_id"] for r in rows])
    output = []
    for k in NAMES:
        is_attack = k in (*ATTACK, "attack")
        members = np.isin(days, ATTACK if k == "attack" else ("mon", "sun") if k == "normal" else [k])
        n = int(members.sum())
        for j, head in enumerate(HEADS):
            aa, bb = a[members, j], b[members, j]
            pos = support[members] > 0
            A = int(aa.sum())
            B = int((aa & pos).sum())
            W = int((aa & ~bb).sum())
            C = int(bb.sum())
            row = dict(
                group=k,
                scenario=NAMES[k],
                head=head,
                N=n,
                bypassed=int(guard[members].sum()),
                positive_support=int(pos.sum()),
                no_support=n - int(pos.sum()),
                raw_alarms=A,
                ccnr_alarms=C,
                withdrawn=W,
                added=int((~aa & bb).sum()),
            )
            if is_attack:
                row.update(
                    raw_TP=A,
                    raw_FN=n - A,
                    raw_TPR=ratio(A, n),
                    ccnr_TP=C,
                    ccnr_FN=n - C,
                    ccnr_TPR=ratio(C, n),
                    A=A,
                    B=B,
                    W=W,
                    retained=A - W,
                    retention=ratio(A - W, A),
                    withdrawal_given_support=ratio(W, B),
                )
            else:
                row.update(
                    raw_FP=A, ccnr_FP=C, raw_FPR=ratio(A, n), ccnr_FPR=ratio(C, n), normal_FP_reduced=W
                )
            output.append(row)
    return output


def validate(rows, thursday, *, formal=True):
    idx = {(r["group"], r["head"]): r for r in rows}
    require(
        len(rows) == len(idx) == 32 and set(idx) == {(k, h) for k in NAMES for h in HEADS}, "TABLE_COVERAGE"
    )
    require(thursday == [r for r in rows if r["group"] == "thu"], "DEDICATED_THURSDAY_ROWS")
    for (k, h), r in idx.items():
        num = lambda f: int(r[f])
        n = num("N")
        a = num("raw_alarms")
        c = num("ccnr_alarms")
        w = num("withdrawn")
        require(
            0 <= c <= a <= n
            and a - c == w
            and num("added") == 0
            and num("positive_support") + num("no_support") == n,
            "COUNT_PARTITION",
        )
        if formal:
            expected = COUNTS.get(k, 544 if k == "attack" else 17773)
            require(
                n == expected and num("bypassed") == (16 if k in ("sun", "normal") else 0),
                "FROZEN_DENOMINATOR",
            )
        if k in (*ATTACK, "attack"):
            B = num("B")
            require(
                num("A") == num("raw_TP") == a
                and w == num("W")
                and 0 <= w <= B <= min(a, num("positive_support"))
                and num("retained") == num("ccnr_TP") == c
                and num("raw_FN") == n - a
                and num("ccnr_FN") == n - c
                and num("bypassed") == 0,
                "ATTACK_COUNTS",
            )
            rates = {
                "retention": (c, a),
                "withdrawal_given_support": (w, B),
                "raw_TPR": (a, n),
                "ccnr_TPR": (c, n),
            }
        else:
            require(
                num("raw_FP") == a and num("ccnr_FP") == c and num("normal_FP_reduced") == w, "NORMAL_COUNTS"
            )
            rates = {"raw_FPR": (a, n), "ccnr_FPR": (c, n)}
        for field, (x, y) in rates.items():
            require(abs(float(r[field]) - x / y) <= 2e-15 if y else r[field] == "不适用", "RATE:" + field)
    for head in HEADS:
        for pool, days in [("normal", ("mon", "sun")), ("attack", ATTACK)]:
            for f in (
                "N",
                "positive_support",
                "raw_alarms",
                "ccnr_alarms",
                "withdrawn",
                *(("A", "B", "W", "retained") if pool == "attack" else ()),
            ):
                require(int(idx[pool, head][f]) == sum(int(idx[d, head][f]) for d in days), "DAY_SUM:" + f)
    return dict(rows=len(rows), thursday_rows=len(thursday), subset_violations=0)


def load_tables(folder):
    def read(name):
        with (folder / name).open(encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    rows = read("DAILY_METRICS.csv")
    th = read("THURSDAY_DUPLICATION.csv")
    return rows, validate(rows, th)


def paper(rows):
    x = {r["group"]: r for r in rows if r["head"] == "ensemble"}
    d = x["thu"]
    a = x["attack"]
    n = x["normal"]
    m = x["mon"]
    s = x["sun"]
    pct = lambda v: v if v == "不适用" else f"{100 * float(v):.4f}%"
    return (
        f"在 DAD 虚拟 MQTT broker 的冻结 v12 外测中，三种子集成在 544 条攻击查询上原检出 {a['A']} 条，基础头漏检 {a['raw_FN']} 条；CCNR 又撤回 {a['W']} 条原本正确的告警，保留 {a['retained']} 条。"
        f"周四 56 条旁路外复制异常中，基础头检出 {d['A']}/56、漏检 {d['raw_FN']} 条。原告警中 {d['B']} 条获得正常支持，{d['W']} 条实际误撤，保留 {d['retained']} 条。总体保留率为 {pct(d['retention'])}，有正支持时的误撤率为 {pct(d['withdrawal_given_support'])}。"
        f"周一建档后的 8,448 条正常查询中，误报由 {m['raw_FP']} 变为 {m['ccnr_FP']} 条；周日 9,325 条由 {s['raw_FP']} 变为 {s['ccnr_FP']} 条。两天共减少 {n['withdrawn']} 条误报。\n\n"
        "周三为修改，周五和周六各保留混合标签；周二删包仅作诊断。\n\n[逐日及种子结果](DAILY_METRICS.csv) · [周四复制异常](THURSDAY_DUPLICATION.csv) · [验收回执](ACCEPTANCE.json)\n"
    )
