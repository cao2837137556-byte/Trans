"""Produce publication tables from UID-paired connection verdicts."""
import math
from pathlib import Path

import numpy as np

from frozen_assets import HERE, combine, reduced
from protocol_reconnect import HANDSHAKE_CUT, RATES
from sources import ARMS, identity, save, table

METHODS = (*ARMS,"handshake_only")
LABELS = ("RAW","CCNR-3D","CCNR-MS","仅握手频次")
GROUPS = {"new_legal":"新增合法重连","low_attack":"封存低速攻击","medium_attack":"封存中速攻击"}
HANDOFF_NAME = "20261126_paper04_v14_legal_reconnect_stress_handoff_codex.md"


def verdict(data, cuts):
    h, scores = reduced(data)
    discrete = h>HANDSHAKE_CUT
    return h, np.column_stack((scores[:,:,3].T>cuts[:,3],discrete))


def aggregate(data, cuts, level, rate=None, batch=None, replicate=None):
    _, flags = verdict(data,cuts)
    n = len(flags)
    row = dict(cohort=data["name"],level=level,rate_per_client=rate,batch=batch,replicate=replicate,
               unit="connection",denominator=n)
    for i,method in enumerate(METHODS):
        alarm = int(flags[:,i].sum())
        row.update({method+"_n":alarm,method+"_rate":alarm/n})
    return row


def mcnemar_two_sided(x,y):
    n = x+y
    if n==0:
        return 1.0
    return min(1.0,2*sum(math.comb(n,i) for i in range(min(x,y)+1))/(2**n))


def by_frequency(datasets,cuts):
    entries = []
    for name,data in datasets.items():
        h, flags = verdict(data,cuts)
        assert (h>=1).all()
        selections = [("all",np.ones(len(h),bool)),*((str(i),h==i) for i in range(1,9)),(">=9",h>=9)]
        for label,take in selections:
            p,q = flags[take,2],flags[take,3]
            n = len(p)
            both, neither = int((p&q).sum()),int((~p&~q).sum())
            only_ms, only_count = int((p&~q).sum()),int((~p&q).sum())
            assert both+neither+only_ms+only_count==n
            entries.append(dict(group=name,unit="connection",observed_h60=label,
                                denominator=n,ms_alarms=int(p.sum()),count_alarms=int(q.sum()),
                                ms_rate=float(p.mean()) if n else None,count_rate=float(q.mean()) if n else None,
                                both_alarm=both,ms_only=only_ms,count_only=only_count,neither_alarm=neither,
                                mcnemar_exact_two_sided_p=mcnemar_two_sided(only_ms,only_count) if n else None))
        subset = [row for row in entries if row["group"]==name]
        assert sum(row["denominator"] for row in subset[1:])==len(h)
        for field in ("ms_only","count_only","both_alarm","neither_alarm"):
            assert sum(row[field] for row in subset[1:])==subset[0][field]
    return entries


def quant_text(n,d):
    return f"{n}/{d}（{n/d:.2%}）" if d else "0/0（不适用）"


def tables_markdown(table1,table2):
    lines = ["### 四方案合法重连误报", "",
             "| 范围 | 每客户端目标速率 | 连接数 | RAW | CCNR-3D | CCNR-MS | 仅握手频次 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for row in table1:
        labels = {"new_total":"独立新批合计","historical":"旧压力对照（单列）",
                  "rate":"档位合计","batch":f"第 {row['replicate']} 批"}
        rate = f"{row['rate_per_client']}/分钟" if row["rate_per_client"] else "—"
        n = row["denominator"]
        values = [quant_text(row[k+"_n"],n) for k in METHODS]
        lines.append("| "+" | ".join([labels[row["level"]],rate,str(n),*values])+" |")
    lines += ["","### 相同实测握手频次的配对","",
              "| 组 | 实测 h | 连接数 | MS 告警 | 计数告警 | MS 独报 | 计数独报 | 均报 | 均未报 | 双侧精确 p |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for row in table2:
        p = row["mcnemar_exact_two_sided_p"]
        n = row["denominator"]
        h = row["observed_h60"].replace(">=9","≥9").replace("all","合计")
        if h in ("5","6","7"):
            h = f"**{h}**"
        vals = [GROUPS[row["group"]],h,str(n),quant_text(row["ms_alarms"],n),quant_text(row["count_alarms"],n),
                *(str(row[k]) for k in ("ms_only","count_only","both_alarm","neither_alarm")),
                f"{p:.6g}" if p is not None else "不适用"]
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)


def direction(rows):
    totals = {r["group"]:r for r in rows if r["observed_h60"]=="all"}
    normal, low, mid = (totals[key] for key in GROUPS)
    saved = normal["count_alarms"]-normal["ms_alarms"]
    if saved>=0:
        normal_delta = f"多尺度比纯计数少报 {saved} 条合法连接"
    else:
        normal_delta = f"多尺度比纯计数多报 {-saved} 条合法连接"
    return (f"新增正常压力组 {normal['denominator']} 条，CCNR-MS 误报 "
            f"{quant_text(normal['ms_alarms'],normal['denominator'])}，纯握手误报 "
            f"{quant_text(normal['count_alarms'],normal['denominator'])}，{normal_delta}。"
            f"封存低速攻击上，CCNR-MS 独报 {low['ms_only']} 条，纯计数独报 {low['count_only']} 条，"
            f"总检出分别为 {low['ms_alarms']}/{low['denominator']}、{low['count_alarms']}/{low['denominator']}。"
            f"封存中速攻击上，两个方向依次为 {mid['ms_only']}、{mid['count_only']} 条，"
            f"总检出分别为 {mid['ms_alarms']}/{mid['denominator']}、{mid['count_alarms']}/{mid['denominator']}。")


def deliver(e, pin, sealed, prior):
    cuts = np.asarray(pin["cuts"])
    new = combine([data for _,_,data in sealed],"new_legal")
    assert len(reduced(new)[0])==600
    rows = [aggregate(new,cuts,"new_total")]
    for rate in RATES:
        strata = sorted((x for x in sealed if x[0]["scheduled_rate"]==rate),key=lambda x:x[0]["replicate"])
        group = combine([data for _,_,data in strata],f"rate{rate:02d}")
        assert len(reduced(group)[0])==120 and len(strata)==3
        rows.append(aggregate(group,cuts,"rate",rate))
        for item,_,data in strata:
            rows.append(aggregate(data,cuts,"batch",rate,item["key"],item["replicate"]))
    rows.append(aggregate(prior["historical_51"],cuts,"historical"))
    freq = by_frequency(dict(new_legal=new,low_attack=prior["low_attack"],medium_attack=prior["medium_attack"]),cuts)
    assert tuple(rows[0][method+"_n"] for method in ("relative_handshake","handshake_only")) == (
        freq[0]["ms_alarms"],freq[0]["count_alarms"])
    for level in ("rate","batch"):
        selected = [row for row in rows if row["level"]==level]
        assert sum(row["denominator"] for row in selected)==600
        assert all(sum(row[method+"_n"] for row in selected)==rows[0][method+"_n"] for method in METHODS)
    table(e/"TABLE1_LEGAL_RECONNECT.csv",rows)
    table(e/"TABLE2_MATCHED_H60_MCNEMAR.csv",freq)
    text = direction(freq)
    (e/"RESULTS_FOR_PAPER.md").write_text(
        f"# 同端点合法重连压力复测\n\n{text}\n\n"+tables_markdown(rows,freq)+"\n",encoding="utf8",newline="\n")
    save(e/"RESULT_SUMMARY.json",dict(status="COMPLETE",new=rows[0],historical=rows[-1],
         frequency_totals=[r for r in freq if r["observed_h60"]=="all"],conclusion=text))
    return rows,freq,text


def sha_all(folder):
    index = folder/"SHA256SUMS"
    paths = sorted(p for p in folder.rglob("*") if p.is_file() and p!=index)
    hashes = {p.relative_to(folder).as_posix():identity(p)["sha256"] for p in paths}
    index.write_bytes("".join(f"{h}  {n}\n" for n,h in hashes.items()).encode("ascii"))
    assert all(identity(folder/n)["sha256"]==h for n,h in hashes.items())
    return len(hashes)


def render_handoff(root, pin, rows, freq, text):
    evidence = root/"evidence"
    repo = HERE.parent.parent
    collab = repo/"runs/mainline_docs/collab"/HANDOFF_NAME
    base = f"../../{HERE.name}/received"
    d = evidence.as_posix()
    table_link = f"[表 1 四方案压力误报]({base}/TABLE1_LEGAL_RECONNECT.csv)"
    freq_link = f"[表 2 同频次配对]({base}/TABLE2_MATCHED_H60_MCNEMAR.csv)"
    relevant = [row for row in freq if row["observed_h60"] in ("5","6","7")]
    compact = tables_markdown(rows[:1]+rows[-1:],relevant)
    doc = f"""# Paper04 v14 同端点合法重连压力复测 · 致 anti

{text}

新采集是每客户端 3、5、6、7、8 次/分钟各三批，每批 40 条合法重连，共 600 条。批次间抓包边界相隔超过 60 秒。另有 15 条预检重连，单独留档。每批三条起始登录进入因果历史。表中重连都是一次成功认证的独立 TCP 连接。原 51 条压力连接作为历史对照，旧攻击两档各 600 条沿用封存的分数、标签和握手记录。

冻结 v12 三种子集成，复用 `formal_20261122_402788` 的 4,096 条参考、393 个组件和 `rank5_20261124_022354` 的 1,000 条同端点正常校准阈值。RAW 阈值 {pin['cuts'][0][3]:.12g}，CCNR-3D 与 CCNR-MS 分别为 {pin['cuts'][1][3]:.12g} 和 {pin['cuts'][2][3]:.12g}。均取同一连接内合格 POST 的最高分，严格超过才报警。纯握手在合格 POST 上取最大实测 h_60s，阈值 {pin['handshake_threshold']}。两种 CCNR 沿用双组件、SYN 弃权、p=4、λ=0.25。完整多尺度使用封存的 ln(3) 比带。

- **表 6** 用表 1 的新增总计、五档及旧 51 条对照。分批数据也在表 1。分母和比例均为连接级。{table_link}
- **同频对照表** 用表 2 的 h=1…8 和 ≥9，重点是 h=5、6、7。p 值是每格对同一连接的两个判决做的双侧精确 McNemar 检验。单个采集批次中的连接共享历史。{freq_link}
- **图 4** 的合法压力面板使用表 1，频次对照使用表 2，保留每格实际样本数。日常留出继续用原 1,000 条。{table_link} · {freq_link}

{compact}

[预登记与验收]({base}/ACCEPTANCE.json) · [全证据 SHA-256]({base}/SHA256SUMS) · [D 盘原始证据]({d}) · [本机性能回执]({root.as_posix()}/live/BENCHMARK_STATUS.json)
"""
    collab.write_text(doc,encoding="utf8",newline="\n")
    return collab
