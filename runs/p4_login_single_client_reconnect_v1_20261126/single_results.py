"""Report historical, synchronized and rotated cohorts with frozen paired decisions."""
from pathlib import Path

import numpy as np

from single_inputs import BASE, HERE, combine
from assessment import saved_formal
from results_reconnect import LABELS, METHODS, aggregate, by_frequency, quant_text, sha_all
from single_protocol import CLIENTS, RATES, REFERENCE
from sources import identity, save, table
from wsl_replay import subset

HANDOFF = "20261126_paper04_v14_single_client_reconnect_handoff_codex.md"
NORMAL = {"historical_51":"旧合法重连 51 条","synchronized_600":"三客户端同步合法重连压力",
          "single_client_600":"单客户端轮换合法重连压力"}
COHORTS = dict(**NORMAL,low_attack="封存低速攻击",medium_attack="封存中速攻击")
NAMES = ("TABLE1_LEGAL_RECONNECT.csv","TABLE2_MATCHED_H60_MCNEMAR.csv","RESULTS_FOR_PAPER.md","RESULT_SUMMARY.json")


def row(data,cut,cohort,level,rate=None,batch=None,client=None):
    out = aggregate(data,cut,level,rate,batch)
    out.update(cohort=cohort,client=client)
    return out


def detail(cohort,batches,cut):
    rows = []
    for rate in sorted({item["scheduled_rate"] for item,_,_ in batches}):
        group = sorted((b for b in batches if b[0]["scheduled_rate"]==rate),key=lambda x:x[0]["key"])
        both = combine([data for _,_,data in group],cohort)
        rows.append(row(both,cut,cohort,"rate",rate))
        for item,_,data in group:
            rows.append(row(data,cut,cohort,"batch",rate,item["key"],item.get("client")))
    return rows


def old_blocks(login,data):
    aligned,_ = saved_formal(login/REFERENCE)
    by_uid = {r["capture_uid"]:r for r in aligned}
    selected = [by_uid[uid] for uid in data["uid"]]
    batches = []
    for block in sorted({r["scenario_id"] for r in selected}):
        take = np.array([r["scenario_id"]==block for r in selected])
        configured = [r for r,t in zip(selected,take,strict=True) if t]
        rate, = {r["scheduled_rate"] for r in configured}
        client, = {r["client"] for r in configured}
        assert len(configured)==rate
        batches.append((dict(key=block,scheduled_rate=rate,client=client),None,subset(data,take,block)))
    assert len(batches)==12
    return batches


def normals_markdown(rows):
    lines = ["| 正常压力组 | 档位 | 批次 | 客户端 | 连接数 | RAW | CCNR-3D | CCNR-MS | 纯握手 |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        n = r["denominator"]
        vals = [NORMAL[r["cohort"]],str(r["rate_per_client"] or "合计"),r["batch"] or "—",str(r["client"] or "—"),
                str(n),*(quant_text(r[k+"_n"],n) for k in METHODS)]
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)


def frequency_markdown(rows):
    lines = ["| 组 | 实测 h | 连接数 | MS 告警 | 纯握手告警 | MS 独报 | 纯握手独报 | 均报 | 均未报 | 双侧精确 p |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        h = r["observed_h60"].replace(">=9","≥9").replace("all","合计")
        if h in ("5","6","7"):
            h = f"**{h}**"
        n,p = r["denominator"],r["mcnemar_exact_two_sided_p"]
        vals = [COHORTS[r["group"]],h,str(n),quant_text(r["ms_alarms"],n),quant_text(r["count_alarms"],n),
                *(str(r[k]) for k in ("ms_only","count_only","both_alarm","neither_alarm")),
                f"{p:.6g}" if p is not None else "不适用"]
        lines.append("| "+" | ".join(vals)+" |")
    return "\n".join(lines)


def conclusion(totals,frequency):
    lines = []
    for row in totals:
        name,n = NORMAL[row["cohort"]],row["denominator"]
        ms,hand = (row[k+"_n"] for k in ("relative_handshake","handshake_only"))
        effect = f"少报 {hand-ms} 条" if ms<=hand else f"多报 {ms-hand} 条"
        lines.append(f"{name}中，MS 误报 {quant_text(ms,n)}，纯握手误报 {quant_text(hand,n)}，MS {effect}。")
    for r in frequency:
        if r["group"].endswith("_attack") and r["observed_h60"]=="all":
            n = r["denominator"]
            lines.append(f"{COHORTS[r['group']]}中，MS 检出 {quant_text(r['ms_alarms'],n)}，纯握手检出 {quant_text(r['count_alarms'],n)}。"
                         f"MS 独报 {r['ms_only']} 条，纯握手独报 {r['count_only']} 条。")
    return "".join(lines)


def deliver(root,pin,batches,sync,prior):
    evidence = root/"evidence"
    cut = np.asarray(pin["cuts"])
    legal = {"historical_51":prior["historical_51"],
             "synchronized_600":combine([x[2] for x in sync],"synchronized_600"),
             "single_client_600":combine([x[2] for x in batches],"single_client_600")}
    totals = [row(data,cut,name,"total") for name,data in legal.items()]
    assert [r["denominator"] for r in totals]==[51,600,600]
    assert {(x[0]["client"],x[0]["scheduled_rate"]) for x in batches}=={(c,r) for c in CLIENTS for r in RATES}
    details = [*detail("historical_51",old_blocks(root.parent,prior["historical_51"]),cut),
               *detail("synchronized_600",sync,cut),*detail("single_client_600",batches,cut)]
    for total in totals:
        for level in ("rate","batch"):
            rows = [r for r in details if r["cohort"]==total["cohort"] and r["level"]==level]
            for col in ("denominator",*(key+"_n" for key in METHODS)):
                assert sum(r[col] for r in rows)==total[col]
    all_normal = [*totals,*details]
    frequency = by_frequency({**legal,**{k:prior[k] for k in ("low_attack","medium_attack")}},cut)
    assert len(frequency)==50
    text = conclusion(totals,frequency)
    table(evidence/NAMES[0],all_normal)
    table(evidence/NAMES[1],frequency)
    sections = ["# 同端点合法重连压力汇总","",text,"","## 三类合法压力误报","",
                normals_markdown(all_normal),"","## 实测握手频次与双侧精确 McNemar","",
                frequency_markdown(frequency)]
    (evidence/NAMES[2]).write_text("\n".join(sections)+"\n",encoding="utf8",newline="\n")
    save(evidence/NAMES[3],dict(status="COMPLETE",normal=totals,
         overall_pairing=[r for r in frequency if r["observed_h60"]=="all"],conclusion=text))
    return totals,frequency,text


def handoff(root,pin,totals,frequency,text):
    repo = HERE.parent.parent
    doc = repo/"runs/mainline_docs/collab"/HANDOFF
    prefix = f"../../{HERE.name}/received"
    sync = f"../../{BASE.name}/received"
    sample = [r for r in frequency if r["observed_h60"] in ("5","6","7")]
    d = (root/"evidence").as_posix()
    bench = pin["benchmark"]["directory"]
    body = f"""# Paper04 v14 单客户端轮换合法重连 · 致 anti

{text}

原 600 条保留为**三客户端同步合法重连压力**。本轮 600 条为**单客户端轮换合法重连压力**。每客户端完成 3、5、6、7、8 次/分钟各一批，每批 40 条。预登记固定客户端轮换、每客户端的档位顺序、逐次 ±0.35 秒均匀抖动及随机种子。批间实测静默超过 60 秒。合格 POST 在原始 PCAP 的 1 秒和 10 秒窗口均只见该客户端的入站 IPv4 和单播源 MAC。冻结八维入站状态与独立原帧复算逐条一致。

四方案共用冻结 v12、4,096 条参考和 Rank-5 阈值。RAW 集成阈值 {pin['cuts'][0][3]:.12g}，原 CCNR 和 MS 集成阈值依次为 {pin['cuts'][1][3]:.12g}、{pin['cuts'][2][3]:.12g}，纯握手严格 h>4。合格 POST 每连接取最大分数，严格越阈判警。原 p=4、λ=0.25、双组件和 SYN 弃权沿用。

{normals_markdown(totals)}

- **表 6 与图 4** 分开画旧 51 条、同步 600 条、单客户端 600 条。表 1 给出三组总计、档位、逐批次误报，实际频次来自各批逐 POST 输出。[表 1 压力误报]({prefix}/{NAMES[0]})
- **同频配对表** 用表 2。每格对同一连接内的 MS 和纯握手做双侧精确 McNemar，各采集组分列。批内连接共享历史。保留 h=5、6、7 的实际样本量，两档攻击计数来自原封存评价。[表 2 同频配对]({prefix}/{NAMES[1]})
- **§4.4** 继续使用已验收的本机性能数值，输入来自同步压力组。计时定义与完整回执在原交接中。[性能表]({sync}/performance/PERFORMANCE.csv) · [性能验收]({sync}/performance/ACCEPTANCE.json) · [D 盘性能证据]({bench})

{frequency_markdown(sample)}

[本轮合稿表和结论]({prefix}/{NAMES[2]}) · [本轮验收]({prefix}/ACCEPTANCE.json) · [SHA-256 清单]({prefix}/SHA256SUMS) · [D 盘封存原始证据]({d}) · [原同步压力交接](20261126_paper04_v14_legal_reconnect_stress_handoff_codex.md)
"""
    doc.write_text(body,encoding="utf8",newline="\n")
    return doc
