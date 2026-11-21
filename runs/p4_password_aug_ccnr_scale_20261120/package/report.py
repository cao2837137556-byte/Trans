from shared import MODELS,ARMS,HEADS,table,read


def paper(out):
    focus=table(out/"FOCUS.csv")
    metrics=table(out/"METRICS.csv")
    scales=table(out/"SCALES.csv")
    attribution=table(out/"NORMAL_ATTRIBUTION.csv")
    for r in metrics:
        v={k:int(r[k]) for k in ("before","after","gained","lost","retained","neither","total")}
        assert v["retained"]+v["gained"]==v["after"] and v["retained"]+v["lost"]==v["before"]
        assert v["after"]+v["lost"]+v["neither"]==v["total"]
    for pool,n in (("UNSW_DEV",1336),("EDGE",214)):
        cells=[r for r in attribution if r["pool"]==pool]
        assert len(cells)==6 and sum(int(r["count"]) for r in cells)==n
    def one(pool,kind,view,model,arm,stage):
        r,=[r for r in focus if (r["pool"],r["kind"],r["view"],r["model"],r["arm"],r["stage"],r["seed"])==
            (pool,kind,view,model,arm,stage,"ensemble")]
        return r
    lines=["# v12 与 r1 的 CCNR 扣分对照","",
           "三组均在相同查询上使用 p=4、λ=0.25 和原参考库。尺度和标准化集成阈值只使用 CIC 源数据。",
           "Windows 10 为同采集跨主机诊断，CCNR 按逻辑主机配对。Edge 密码预先确认 23,650 条，其中 42 条缺少可评价帧。",
           "","| 模型 | 尺度及集成 | 阶段 | Windows 10 固定失警队列中告警 / 15,849 | Edge 密码检出 / 23,608 | 登录 POST 检出 / 23,608 | Edge 消除原新增 / 214；新引入 | UNSW 消除原新增 / 1,336；新引入 |",
           "|---|---|---|---:|---:|---:|---:|---:|"]
    baseline=[r for r in scales if r["seed"]=="27"]
    b={r["model"]:float(r["span"]) for r in baseline}
    for m in MODELS:
        for arm,title in zip(ARMS,("原尺度与原平均","自身跨度与原平均","自身跨度标准化平均")):
            for stage in ("RAW","CCNR"):
                def cell(p,k,v): return one(p,k,v,m,arm,stage)
                w=cell("WINDOWS","attack","data_connections_any_packet")
                edge=cell("EDGE_PASSWORD","attack","any_eligible_inbound");post=cell("EDGE_PASSWORD","attack","confirmed_login_POST")
                ne=cell("EDGE","normal","post_all");nu=cell("UNSW_DEV","normal","post_all")
                assert int(w["fixed_cohort"])==15849 and int(edge["total"])==int(post["total"])==23608
                lines.append(f"| {m} | {title} | {stage} | {w['cohort_alerted']} | {edge['alerts']} | {post['alerts']} | {ne['cohort_silent']} / {ne['added_vs_r1_original_final']} | {nu['cohort_silent']} / {nu['added_vs_r1_original_final']} |")
    lines.extend(["","Windows 队列固定为 r1 原基础头曾告警且原 CCNR 整条失警的带数据连接。正常侧“原新增”固定为原 r1 CCNR 有警且 v12 CCNR 无警的查询，“新引入”计原 r1 CCNR 安静、当前有警的全部正常查询。",
        "",f"种子 27 在原 CIC FIT 权重下的 Q90−Q10，v12 为 {b['v12']:.6f}，r1 为 {b['r1']:.6f}，变化 {(b['r1']/b['v12']-1)*100:+.2f}%。",
        "","Edge 同设备正常连接、HTTP 与 UDP 泛洪、CIC 和 UNSW 建档后查询，以及三个单种子结果见 METRICS.csv。FOCUS.csv 单列旧告警保留、新增和消除；正常误报归因与 Windows 同包裕度分位数另表。"])
    return "\n".join(lines)+"\n"
