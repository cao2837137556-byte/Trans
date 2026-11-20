"""Produce the paper-facing paired counts and independently check marginal identities."""
import csv
import json


def table(path):
    with path.open(encoding="utf8",newline="") as f:
        rows=list(csv.DictReader(f))
    for r in rows:
        for k in ("v12","candidate","total","gained","lost","retained","neither","delta"):
            r[k]=int(r[k])
        assert r["v12"]==r["retained"]+r["lost"] and r["candidate"]==r["retained"]+r["gained"]
        assert r["delta"]==r["candidate"]-r["v12"] and r["total"]==r["neither"]+r["retained"]+r["gained"]+r["lost"]
    return rows


def paper_text(out):
    primary=table(out/"EDGE_PASSWORD.csv")
    win=table(out/"WINDOWS_CONNECTIONS.csv")
    others=table(out/"FLOOD_NORMAL.csv")
    seal=json.loads((out/"EDGE_INPUTS.json").read_bytes())
    assert seal["capture_connections"]==23650 and len(primary)==16
    assert len({(r["head"],r["seed"],r["view"]) for r in primary})==16
    for r in primary:
        assert r["total"]+int(r["without_eligible_query"])==23650
        assert r["total"]==seal["connections" if r["view"]=="any_eligible_inbound" else "posts"]
    keep=[r for r in primary if r["seed"]=="ensemble"]
    keep.extend(r for r in win if r["seed"]=="ensemble" and r["view"]=="data_connections_any_packet")
    keep.extend(r for r in others if r["seed"]=="ensemble" and r["view"] in ("post_all","post_sampled_normal"))
    normals=[r for r in keep if r["source"]=="EDGE" and r["view"]=="post_sampled_normal"]
    assert len(normals)==2
    statements=[]
    for stage in ("RAW","CCNR"):
        attack,=[r for r in keep if r["source"]=="Edge Password" and r["view"]=="any_eligible_inbound" and r["head"]==stage]
        normal,=[r for r in normals if r["head"]==stage]
        diagnostic,=[r for r in keep if r["source"]=="ToN Windows 10" and r["head"]==stage and r["kind"]=="attack"]
        assert diagnostic["total"]==18194
        statements.append(f"{stage}，Edge 的 {attack['total']:,} 条可评价密码关联连接中，增强头多检出 {attack['gained']:,} 条，丢失原检出 {attack['lost']:,} 条。"
                          f"同设备已有正常业务的 {normal['total']:,} 条被抽样查询覆盖的连接中，新增误报 {normal['gained']:,} 条，消除原误报 {normal['lost']:,} 条。"
                          f"Windows 10 的 18,194 条带数据攻击关联连接中，多检出 {diagnostic['gained']:,} 条，丢失 {diagnostic['lost']:,} 条。")
    lines=["# 密码增强头与冻结 v12 的配对结果","","Edge 密码场景在模型冻结后评分。"
           f"全抓包确认 23,650 条连接，实际有合格评分帧的连接为 {seal['connections']:,} 条。"
           f"其中 {seal['unscorable_connections']:,} 条缺合格入站查询。ToN Windows 10 属同采集跨主机诊断，CCNR 按逻辑主机配对。"
           "Edge 正常侧为同设备已有业务，合法网页登录的正常分母缺失。下表为三种子集成，单种子附在各配对表。","",*statements,"",
           "| 来源 | 阶段 | 类别 | 范围 | 单位 | 分母 | 原告警 | 新告警 | 新增 | 丢失 |",
           "|---|---|---|---|---|---:|---:|---:|---:|---:|"]
    for r in keep:
        lines.append("| "+" | ".join(str(r[k]) for k in ("source","head","kind","view","unit","total","v12","candidate","gained","lost"))+" |")
    return "\n".join(lines)+"\n"


def report(out):
    (out/"RESULTS_FOR_PAPER.md").write_bytes(paper_text(out).encode("utf8"))
