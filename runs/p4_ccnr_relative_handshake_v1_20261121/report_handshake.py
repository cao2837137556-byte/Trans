"""Render the same compact Chinese result from the returned small tables."""
import csv
import json


def rows(path):
    with path.open(encoding="utf8", newline="") as stream:
        return list(csv.DictReader(stream))


def paper(out):
    all_paired = rows(out / "PAIRED.csv")
    all_mechanism = rows(out / "MECHANISM.csv")
    exact = json.loads((out / "UNSW_ATTRIBUTION.json").read_bytes())
    paired = {(x["group"], x["arm"]): x for x in all_paired if x["seed"] == "ensemble"}
    delta = {(x["group"], x["baseline_arm"]): x for x in all_mechanism if x["seed"] == "ensemble"}
    normal = [
        ("CIC 正常查询", "CIC_DEV.normal.q"), ("UNSW 正常查询", "UNSW_DEV.normal.q"),
        ("UNSW 正常连接", "UNSW_DEV.normal.c"), ("Edge 正常查询", "EDGE.normal.q"),
        ("Edge 正常连接", "EDGE.normal.c"), ("ToN 正常连接合计", "TON.normal.all.c"),
    ] + [(f"ToN .{host} 正常连接", f"TON.{host}.normal.c") for host in (152, 190, 195)]
    attack = [
        ("Win10 旁路外带数据连接", "TON.195.payload.c"),
        ("Win10 全包连接", "TON.195.password.c"),
        ("Edge 登录 POST 连接", "EDGE.password.POST"), ("Edge 密码连接", "EDGE.password.any"),
        ("ToN .152 密码连接", "TON.152.password.c"),
        ("ToN .190 密码连接", "TON.190.password.c"),
    ]
    for name, want in (
        (("TON.195.payload.c", "RAW"), (18194, 14024)),
        (("TON.195.payload.c", "v12"), (18194, 245)),
        (("TON.195.payload.c", "R1_U1"), (18194, 14024)),
        (("EDGE.password.POST", "v12"), (23608, 19200)),
        (("EDGE.password.any", "v12"), (23608, 23122)),
    ):
        value = paired[name]
        assert (int(value["total"]), int(value["alarm"])) == want
    flood = [(name+" 泛洪查询", key) for name,key in
             (("CIC","CIC_DEV.flood.q"),("UNSW","UNSW_DEV.flood.q"),
              ("Edge","EDGE.flood.q"),("Edge HTTP","EDGE.HTTP.q"),("Edge UDP","EDGE.UDP.q"))]
    lines = [
        "# 冻结 v12 的设备本地相对握手次数对照",
        "",
        "三种子集成。Win10 主视图为旁路外有传输层数据的连接，ToN 为按逻辑主机配对的补充分析。"
        "原始 v12 保留 245／14,024 条 RAW 已告警连接，单独加 R1＋U1 保留 14,024 条，增加的 13,779 条属于角色筛选的效果。",
        "",
        "每个增量单元格按「新增告警／其中因不足两个合格组件」报告。后者合计包含参考握手记录缺失、"
        "握手距离门槛、四空间联合相容三类。逐步归因、单种子和查询／连接视图见小表。",
    ]
    for title, group in (("攻击告警", attack), ("正常误报", normal), ("原泛洪回检", flood)):
        lines.extend((
            "", f"## {title}", "",
            "| 视图 | 分母 | RAW | v12 | R1＋U1 | v12＋握手 | R1＋U1＋握手 | 握手增量③－① | 握手增量④－② |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ))
        for label, name in group:
            a = [paired[name, arm] for arm in ("RAW", "v12", "R1_U1", "v12_H60", "R1_U1_H60")]
            more = [delta[name, arm] for arm in ("v12","R1_U1")]
            cells = [label, f"{int(a[0]['total']):,}", *(f"{int(r['alarm']):,}" for r in a),
                     *(f"{int(d['gain']):,}／{int(d['shortage_total']):,}" for d in more)]
            assert all(d["lost"] == "0" for d in more)
            lines.append("| " + " | ".join(cells) + " |")
    by = exact["queries_by_original_connection"]
    links = exact["affected_connections"]
    lines.extend(("", "## 上一轮 UNSW 误报归因", "",
        f"按同一批 74,444 条 UNSW 建档后正常查询，{exact['added_queries']:,} 条新增误报中，"
        f"{by['previously_alerted']:,} 条落在原 v12 已有告警的 {links['previously_alerted']:,} 条连接上，"
        f"{by['previously_quiet']:,} 条落在原来整条无警的 {links['previously_quiet']:,} 条连接上。"
        "这 26 条是上一轮覆盖对照新增的误报连接。逐设备、角色、服务端口和原连接计数随附。", ""))
    return "\n".join(lines)
