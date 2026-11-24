"""Seal the rank-five cuts and compare policies on identical held-out rows."""
import math
import time

import numpy as np

from protocol import CAL_CONNECTIONS, OLD_CONNECTIONS, RANK
from assessment import connection_scores
from evidence import combine
from plans import SCENARIOS
from schedule import RATES
from sources import ARMS, HEADS, identity, save, table

ARMLABEL=dict(RAW="RAW",v12_CCNR="原 CCNR",relative_handshake="CCNR＋相对握手")


def rank5(maxes):
    assert maxes.shape==(len(ARMS),CAL_CONNECTIONS,len(HEADS)) and np.isfinite(maxes).all()
    position=CAL_CONNECTIONS-RANK
    tau=np.partition(maxes,position,axis=1)[:,position,:]
    alarm=(maxes>tau[:,None,:]).sum(axis=1)
    equal=(maxes==tau[:,None,:]).sum(axis=1)
    assert (alarm<RANK).all() and (alarm+equal>=RANK).all()
    return tau,alarm,equal


def statistical_bound():
    a,b=0.,.05
    for _ in range(64):
        p=(a+b)/2
        lower_tail=sum(math.comb(CAL_CONNECTIONS,k)*p**k*(1-p)**(CAL_CONNECTIONS-k) for k in range(RANK))
        if lower_tail>.05:
            a=p
        else:
            b=p
    return (a+b)/2


def check_rank5():
    x=np.arange(CAL_CONNECTIONS,dtype=np.float64)
    v=np.broadcast_to(x[None,:,None],(len(ARMS),CAL_CONNECTIONS,len(HEADS)))
    tau,alarms,eq=rank5(v)
    assert (tau==995).all() and (alarms==4).all() and (eq==1).all()
    x[-6:]=x[-1]
    tau,alarms,eq=rank5(v)
    assert (tau==999).all() and (alarms==0).all() and (eq==6).all()
    assert round(statistical_bound()*100,3)==.913


def seal(out,prior,new,old,pins):
    merged=combine([prior,*new],"calibration")
    assert prior["connections"]==OLD_CONNECTIONS and merged["connections"]==CAL_CONNECTIONS
    vals=connection_scores(merged["scores"],merged["stream"])
    tau,alarms,tie=rank5(vals)
    table(out/"THRESHOLD_COMPARISON.csv",[
        dict(arm=a,head=h,old_threshold=old[i,j],new_threshold=tau[i,j],
             calibration_connections=CAL_CONNECTIONS,descending_rank=RANK,strict_alarm=int(alarms[i,j]),
             equal_to_threshold=int(tie[i,j]),threshold_change=tau[i,j]-old[i,j])
        for i,a in enumerate(ARMS) for j,h in enumerate(HEADS)])
    body=dict(status="PASS",arms=ARMS,heads=HEADS,strict_greater_than=True,old_connections=OLD_CONNECTIONS,
              added_connections=CAL_CONNECTIONS-OLD_CONNECTIONS,calibration_connections=CAL_CONNECTIONS,
              descending_rank=RANK,thresholds=tau.tolist(),old_thresholds=identity(out/"THRESHOLDS_206.json"),
              old_scores=pins["previous_calibration"],added_scores=[x["score_sha"] for x in new],
              calibration_fp=alarms.tolist(),equal_to_threshold=tie.tolist(),
              one_sided_95pct_iid_continuous_tail_bound=statistical_bound())
    save(out/"THRESHOLDS.json",body)
    save(out/"THRESHOLD_SEAL.json",dict(status="PASS",thresholds=identity(out/"THRESHOLDS.json"),
         input_manifest=identity(out/"INPUTS.json"),sealed_at_ns=time.time_ns(),normal_connections=CAL_CONNECTIONS,
         table=identity(out/"THRESHOLD_COMPARISON.csv")))
    return tau


def compare(data,old,new,stress=False):
    types=np.array([x["scenario"] for x in data["rows"]])
    selectors={"overall":np.ones(len(types),dtype=bool)}
    if stress:
        rates=np.array([x["scheduled_rate"] for x in data["rows"]])
        selectors.update({f"reconnect_{x}_per_min":rates==x for x in RATES})
    else:
        selectors.update({x:types==x for x in SCENARIOS})
    rows=[]
    for group,mask in selectors.items():
        if not mask.any():
            continue
        vv=data["scores"][:,mask,:]
        for unit,values in (("request",vv),("connection",connection_scores(vv,data["stream"][mask]))):
            n=values.shape[1]
            flags1=values>old[:,None,:]
            flags2=values>new[:,None,:]
            for i,a in enumerate(ARMS):
                for j,h in enumerate(HEADS):
                    a1,a2=flags1[i,:,j],flags2[i,:,j]
                    n1,n2=int(a1.sum()),int(a2.sum())
                    rows.append(dict(split=data["name"],group=group,unit=unit,arm=a,head=h,denominator=n,
                                     old_fp=n1,new_fp=n2,old_rate=n1/n,new_rate=n2/n,
                                     both=int((a1&a2).sum()),old_only=int((a1&~a2).sum()),
                                     new_only=int((~a1&a2).sum()),neither=int((~a1&~a2).sum()),
                                     old_meets_1pct=n1*100<=n if unit=="connection" else "",
                                     new_meets_1pct=n2*100<=n if unit=="connection" else ""))
    return rows


def tables(out,hold,fixed,all_old,stress,old,new):
    daily=combine(hold,"new_daily")
    assert daily["connections"]==1000
    rows=[r for part in [*hold,daily,*fixed,all_old] for r in compare(part,old,new)]
    stress_rows=compare(stress,old,new,stress=True)
    table(out/"PAIRED.csv",rows)
    table(out/"STRESS_PAIRED.csv",stress_rows)
    items={(x["split"],x["arm"]):x for x in rows+stress_rows
           if (x["group"],x["unit"],x["head"])==("overall","connection","ensemble")}
    main=[]
    for suffix,name in (("old","原 206 条"),("new","新 1,000 条")):
        for arm in ARMS:
            a=items["new_daily",arm]
            b=items["old_daily",arm]
            s=items["old_stress",arm]
            main.append(dict(threshold=name,arm=arm,daily_fp=a[suffix+"_fp"],daily_connections=a["denominator"],
                             daily_meets_1pct=a[suffix+"_meets_1pct"],archived_daily_fp=b[suffix+"_fp"],
                             archived_daily_connections=b["denominator"],stress_fp=s[suffix+"_fp"],
                             stress_connections=s["denominator"],attack_detected="",attack_connections="",attack_status="待测"))
    table(out/"DAILY_AND_ATTACK.csv",main)
    with (out/"RESULTS_FOR_PAPER.md").open("w",encoding="utf8",newline="\n") as f:
        f.write("# 同服务第 5 高校准结果\n\n")
        f.write("原 206 条加新 794 条普通连接，合计 1,000 条用于校准。下表主栏为阈值封存后独立采集的 1,000 条普通留出。\n\n")
        f.write("| 阈值 | 三种子集成 | 新日常误报／连接 | 达到 1% | 旧日常对照 | 合法重连压力 | 攻击检出 |\n")
        f.write("|---|---|---:|---|---:|---:|---|\n")
        for x in main:
            f.write(f"| {x['threshold']} | {ARMLABEL[x['arm']]} | {x['daily_fp']}/{x['daily_connections']} | "
                    f"{'是' if x['daily_meets_1pct'] else '否'} | {x['archived_daily_fp']}/{x['archived_daily_connections']} | "
                    f"{x['stress_fp']}/{x['stress_connections']} | 待测 |\n")
        f.write("\n各子批次和 POST 级新旧配对见配对表。合法重连压力按每分钟 1、3、5、8 次另列。"
                "攻击待同端点独立抓包和可绑定到请求与连接的可信标签。\n")
