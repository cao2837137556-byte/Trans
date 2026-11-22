"""Canonical Chinese decision summary assembled from the paired small tables."""
import csv

PRIMARY=("TON.195.payload.c","EDGE.password.POST","EDGE.password.any")
NORMAL=("CIC_DEV.normal.q","UNSW_DEV.normal.q","EDGE.normal.q","EDGE.normal.c","TON.normal.all.c")
LABEL={
    "TON.195.payload.c":"Win10 旁路外带数据攻击连接", "TON.195.password.c":"Win10 全包攻击连接",
    "TON.152.password.c":".152 全包攻击连接", "TON.190.password.c":".190 全包攻击连接",
    "EDGE.password.POST":"Edge 登录 POST 连接", "EDGE.password.any":"Edge 密码全包连接",
    "CIC_DEV.normal.q":"CIC 正常查询", "UNSW_DEV.normal.q":"UNSW 正常查询",
    "EDGE.normal.q":"Edge 正常查询", "EDGE.normal.c":"Edge 正常连接",
    "TON.normal.all.c":"ToN 三台正常连接",
    "CIC_DEV.flood.q":"CIC 泛洪查询", "UNSW_DEV.flood.q":"UNSW 泛洪查询",
    "EDGE.HTTP.q":"Edge HTTP 泛洪查询", "EDGE.UDP.q":"Edge UDP 泛洪查询",
}


def rows(path):
    with path.open(encoding="utf8",newline="") as f:
        return list(csv.DictReader(f))


def paper(folder):
    pairs=rows(folder/"PAIRED.csv")
    arms={}
    for r in pairs:
        assert int(r["lost"])==0
        assert int(r["alert"])-int(r["original"])==int(r["added"])
        assert int(r["original"])<=int(r["alert"])<=int(r["raw"])<=int(r["total"])
        if r["seed"]=="ensemble":
            arms[r["group"],r["arm"]]=r
    mechanisms={(r["group"],r["membership"]):r for r in rows(folder/"MECHANISM.csv") if r["seed"]=="ensemble"}
    focus=rows(folder/"EDGE_502_443.csv")
    w=arms[PRIMARY[0],"R2_U1"]
    assert (w["total"],w["raw"],w["original"])==("18194","14024","245")
    assert (arms[PRIMARY[1],"R2_U1"]["raw"],arms[PRIMARY[1],"R2_U1"]["original"])==("23606","19200")
    assert (arms[PRIMARY[2],"R2_U1"]["total"],arms[PRIMARY[2],"R2_U1"]["original"])==("23608","23122")
    def added(n):
        return f"{int(arms[n,'R2_U1']['added']):,}"
    acc=f"{100*float(w['retention_vs_raw']):.2f}%"
    det=f"{100*float(w['detection_or_fpr']):.2f}%"
    mech=mechanisms[PRIMARY[0],"U1"]
    lines=["# 冻结 v12 的 TCP 角色与服务端口筛选","",
        f"主配置 R2＋U1 多保住 Win10 {added(PRIMARY[0])} 条旁路外带数据攻击连接，最终保留 {int(w['alert']):,} 条。原有告警保留率 {acc}，全部连接检出率 {det}。Edge 多保住 {added(PRIMARY[1])} 条登录 POST 连接、{added(PRIMARY[2])} 条全包攻击连接。",
        f"正常新增误报为 CIC {added(NORMAL[0])} 条查询、UNSW {added(NORMAL[1])} 条查询、Edge {added(NORMAL[2])} 条查询与 {added(NORMAL[3])} 条连接，ToN 三台合计 {added(NORMAL[4])} 条连接。",
        f"Win10 主要新增中，{int(mech['coverage']):,} 条来自同角色同服务参考不足两个合法组件，{int(mech['rematch']):,} 条来自覆盖足够后的重新匹配。下表为三种子集成，各种子和全部配置附表。","",
        "| 范围 | 分母 | RAW | 原 v12 | R2＋U1 | 新增 | 组件不足 | 重新匹配 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for group,label in LABEL.items():
        r=arms[group,"R2_U1"];m=mechanisms[group,"U1"]
        assert int(m["coverage"])+int(m["rematch"])==int(r["added"])
        cells=(r["total"],r["raw"],r["original"],r["alert"],r["added"],m["coverage"],m["rematch"])
        lines.append(f"| {label} | "+" | ".join(f"{int(x):,}" for x in cells)+" |")
    lines.extend(["","UDP 逐查询一致。原泛洪告警逐查询未丢失。ToN 采用逻辑主机配对。Edge 正常来自同设备原有业务，合格合法网页登录正常样本为 0 条。",""])
    for f in focus:
        if f["unknown_policy"]!="U1":
            continue
        lines.append(f"原 1883 供体支持撤警的 {f['total']} 条 {f['historical_service']} 查询中，R2＋U1 重新误报 {f['new_fp_total']} 条，另有 {f['replacement_two_compatible']} 条找到两个相容替代组件。原两小时建档库中该端口的 TCP 服务端组件数为 {f['ref_TCP_server_same_port_components']}。")
    lines.extend(["","上轮阈值目标与正常误报预算仅作参照。本轮为完整中性配对，不据目标组结果改动 R2＋U1。","",
        "配对计数见 PAIRED.csv，两类变化见 MECHANISM.csv，Edge 服务分层见 EDGE_NORMAL_BY_SERVICE.csv，重点队列见 EDGE_502_443.csv。预检角色覆盖见 ROLE_COVERAGE.csv，缓存握手分位数见 HANDSHAKE.csv。"])
    return "\n".join(lines)+"\n"
