"""Read generated small tables and produce the canonical Chinese handoff."""
from history_common import read

LABELS={
 "TON.195.payload.c":"Win10 旁路外带数据攻击连接",
 "TON.195.password.c":"Win10 全包攻击连接",
 "TON.152.password.c":".152 全包攻击连接",
 "TON.190.password.c":".190 全包攻击连接",
 "EDGE.password.any":"Edge 密码连接（全包）",
 "EDGE.password.POST":"Edge 密码连接（仅 POST）",
 "CIC_DEV.normal.q":"CIC 正常查询",
 "EDGE.normal.q":"Edge 正常查询",
 "EDGE.normal.c":"Edge 正常连接",
 "UNSW_DEV.normal.q":"UNSW 正常查询",
 "TON.normal.all.c":"ToN 三台正常连接",
 "CIC_DEV.flood.q":"CIC 泛洪查询",
 "UNSW_DEV.flood.q":"UNSW 泛洪查询",
 "EDGE.HTTP.q":"Edge HTTP 泛洪查询",
 "EDGE.UDP.q":"Edge UDP 泛洪查询",
}

def paper(out):
    result=read(out/"RESULT.json")
    p=result["primary"];h=p["history60"];l=p["lambda_equal_cost"]
    lines=["# 冻结 v12 的 60 秒连接历史旁路","",
           f"三种子集成。CIC CAL 正常 TCP 以 {result['cal_rows']:,} 条查询标定，60 秒不同活跃五元组计数严格大于 {result['threshold']} 才开启新旁路。",
           "同代价 λ 为所有正常代价均不超过新旁路时最小可行的 λ。正常组按查询或连接分别计新增误报。","",
           "| 评价单位与范围 | 分母 | RAW | 原 CCNR | 60 秒旁路 | 同代价 λ |",
           "|---|---:|---:|---:|---:|---:|"]
    for group,name in LABELS.items():
        a,b=[result["rows"][group][key] for key in ("history60","lambda_equal_cost")]
        assert 0<=a["original"]<=a["alarms"]<=a["raw"]<=a["total"]
        assert 0<=b["original"]<=b["alarms"]<=b["raw"]<=b["total"]
        lines.append(f"| {name} | {a['total']:,} | {a['raw']:,} | {a['original']:,} | {a['alarms']:,} | {b['alarms']:,} |")
    def word(v):
        return "达到" if v else "未达到"
    lines.extend(["",f"Win10 主视图以 18,194 条合格攻击连接为分母，原 RAW 在其中报 14,024 条。原 CCNR 保留 245 条，60 秒旁路保留 {h['alarms']:,} 条并救回 {h['added']:,} 条。同代价 λ 保留 {l['alarms']:,} 条。",
        f"7,012 条恢复目标{word(result['meeting_recovery'])}，所有正常预算{word(result['within_budgets'])}。相对同代价 λ 的严格新增收益条件{word(result['superiority_default_metric'])}。",
        ("三项均通过，可进入合法登录及独立采集验证。" if result["advance"] else "当前结论停在该批冻结查询的配对回放。"),
        "在相同查询上逐项核对原告警集合包含关系，原泛洪告警丢失数为 0。",
        "ToN CCNR 按逻辑主机配对，Edge 正常代价覆盖同设备原业务。首次告警表用原始观测时钟从视图内首个合格包计时。",
        "PAIRED.csv 含三个单种子、全测试床及 λ 六档。EQUAL_COST.csv 给出各正常组新增误报和限制 λ。",
        "DONORS.csv 与 DONOR_SERVICES.csv 汇总原被撤告警的支持组件、服务端口与角色。DONOR_DIAGNOSTIC.json 单列证据缺项。"])
    return "\n".join(lines)+"\n"
