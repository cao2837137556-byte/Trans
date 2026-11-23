"""Calibrate each frozen arm by connection maximum and evaluate the same held-out UIDs."""
from pathlib import Path
import sys

import numpy as np

from sources import HERE, ARMS, HEADS, check_attacks, check_seal, flood, identity, read, save, table
from audit import NS, join
from audit_formal import collect_aligned, scene_callback
from bank import evaluate_pairs, materialize
from frozen_score import digest_order, sealed_runtime
from schedule import BURST, RATES, RECOVER, ORDINARY
from plans import normal_plan

KEPT=np.array([0,1,3])
MODES=("CIC_source","login_calibrated")


def get_array(path):
    with np.load(path,allow_pickle=False) as raw:
        return {k:raw[k] for k in raw.files}


def roster(align):
    return sorted((r for r in align if r["aligned"]),key=lambda x:x["frame"])


def arrays(align):
    return (np.array([r["capture_uid"] for r in align]),
            np.array([r["tcp_stream"] for r in align],dtype=np.int64))


def saved_formal(base):
    stored=get_array(base/"evaluation/DECISIONS.npz")
    assert tuple(stored["arms"][KEPT])==ARMS
    with (base/"evaluation/ALIGNMENT.jsonl").open("r",encoding="utf8") as file:
        import json
        rows=roster(json.loads(line) for line in file)
    ids,conns=arrays(rows)
    assert np.array_equal(ids,stored["uid"]) and np.array_equal(conns,stored["stream"])
    assert np.array_equal([r["frame"] for r in rows],stored["frame"]) and all(r["normal"] for r in rows)
    assert len(rows)==243 and len(set(conns))==207
    return rows,stored


def scores_for(base,folder,cap,fields,aligned,cfg,pins):
    ref=get_array(base/"enrollment/REFERENCE.npz")
    q,proof=materialize(folder/"login.pcap",cap,fields,None,{r["frame"]:r["capture_uid"] for r in aligned},pins)
    uid,stream=arrays(aligned)
    assert np.array_equal(q["uid"],uid) and proof["uid_order_sha256"]==digest_order(uid)
    assert np.array_equal(q["h"],[r["handshakes_60s"] for r in aligned])
    assert (q["clock"]>ref["clock"].max()).all() and not set(uid)&set(ref["uid"])
    values,dec,support,legal,compatible=evaluate_pairs(q,ref,cfg,pins,base/"frozen_quick_check_assets")
    return dict(uid=uid,stream=stream,scores=values[KEPT],cic_flags=dec[KEPT],h=q["h"],
                support=support[[0,2]],legal=legal[[0,2]],compatible=compatible[[0,2]]),proof


def connection_scores(values, stream):
    groups,member=np.unique(stream,return_inverse=True)
    assert len(groups) and values.shape==(len(ARMS),len(stream),len(HEADS)) and np.isfinite(values).all()
    result=np.full((len(groups),len(ARMS),len(HEADS)),-np.inf)
    np.maximum.at(result,member,values.transpose(1,0,2))
    assert np.isfinite(result).all()
    return result.transpose(1,0,2)


def fit(values,stream):
    maxima=connection_scores(values,stream)
    n=maxima.shape[1]
    limit=n//100
    rank=n-limit-1
    thresholds=np.partition(maxima,rank,axis=1)[:,rank,:]
    exceed=(maxima>thresholds[:,None,:]).sum(axis=1)
    boundary=(maxima==thresholds[:,None,:]).sum(axis=1)
    assert np.all(exceed<=limit) and np.all(exceed+boundary>limit)
    return thresholds,n,limit,exceed,boundary


def fit_check():
    one=np.arange(102,dtype=np.float64)
    one[100:]=one[99]
    score=np.broadcast_to(one[None,:,None],(3,len(one),4))
    tau,n,k,f,eq=fit(score,np.arange(len(one)))
    assert n==102 and k==1 and np.all(tau==99) and np.all(f==0) and np.all(eq==3)
    stream=np.repeat(np.arange(100),2)
    s=np.broadcast_to(np.arange(200)[None,:,None],(3,len(stream),4))
    tau,n,k,_,_=fit(s,stream)
    assert n==100 and k==1 and np.all(tau==197)


def preflight(out,base,cfg,pins):
    ref,first,old,manifest=check_seal(base)
    attack=check_attacks(out,base,first)
    flood(out)
    fit_check()
    folder=base/"evaluation"
    rows,stored=saved_formal(base)
    counts=[]
    report,align,fields=join(folder,old,scene_callback(read(folder/"SCHEDULE.json"),"evaluation",counts))
    assert report["status"]=="PASS" and len(counts)==12 and all(m["confirmed"] for m in counts)
    assert [r["capture_uid"] for r in rows]==[r["capture_uid"] for r in roster(align)]
    actual,proof=scores_for(base,folder,old,fields,rows,cfg,pins)
    delta=float(np.max(np.abs(actual["scores"]-stored["scores"][KEPT])))
    assert delta<=.0005 and np.array_equal(actual["cic_flags"],stored["decision"][KEPT])
    assert np.array_equal(actual["h"],stored["h"])
    cuts=read(base/"QUICK_CHECK.json")["threshold"]
    assert cuts==cfg["method"]["cuts"]
    save(out/"PREFLIGHT.json",dict(status="PASS",archive=base.name,manifest=identity(base/"SHA256SUMS"),
         archive_files_checked=len(manifest),reference=ref["reference"],reference_rows=ref["reference_rows"],
         service_endpoint=ref["server_endpoint"],server_port=ref["server_port"],cic_cuts=cuts,features=proof,
         original_evaluation_end_ns=old["capture"]["end_ns"],rechecked_archived_queries=len(rows),
         maximum_score_delta=delta,old_cic_flags_identical=True,old_stress_blocks=len(counts),
         attack=attack["status"],flood=identity(out/"FLOOD_CHECK.json")))


def get_normal(out,base,stage,cfg,pins):
    folder=out/stage
    assert read(folder/"SCHEDULE.json")==normal_plan(stage)
    cap,report,align,fields=collect_aligned(folder)
    old=read(base/"enrollment/CAPTURE.json")
    assert cap["scope"]==stage and cap["capture"]["capture_kernel_drops"]==0
    assert cap["server_port"]==old["server_port"] and cap["kernel"]==old["kernel"]
    assert [(x["ip"],x["mac"]) for x in cap["endpoints"]]==[(x["ip"],x["mac"]) for x in old["endpoints"]]
    assert cap["capture"]["first_qualifying_ns"]>read(out/"PREFLIGHT.json")["original_evaluation_end_ns"]+60*NS
    aligned=roster(align)
    assert len(aligned)==report["checks"]["aligned_requests"] and len(set(x["tcp_stream"] for x in aligned))==report["checks"]["tcp_connections"]
    q,proof=scores_for(base,folder,cap,fields,aligned,cfg,pins)
    path=folder/"SCORES.npz"
    np.savez_compressed(path,**q,arms=np.array(ARMS),cic_cuts=np.array(cfg["method"]["cuts"]))
    return cap,report,aligned,q,proof,identity(path)


def calibration(out,base,cfg,pins):
    cap,report,aligned,q,proof,score=get_normal(out,base,"calibration",cfg,pins)
    tau,n,budget,exceed,ties=fit(q["scores"],q["stream"])
    assert n==report["checks"]["tcp_connections"]
    source=cfg["method"]["cuts"]
    rows=[]
    for i,a in enumerate(ARMS):
        for j,h in enumerate(HEADS):
            rows.append(dict(arm=a,head=h,threshold=tau[i,j],comparison=">",
                             CIC_source_threshold=source[j],calibration_connections=n,
                             maximum_fp=budget,observed_fp=int(exceed[i,j]),at_threshold=int(ties[i,j]),
                             observed_fpr=float(exceed[i,j])/n))
    table(out/"THRESHOLDS.csv",rows)
    save(out/"THRESHOLDS.json",dict(arms=ARMS,heads=HEADS,thresholds=tau.tolist(),comparison="strict_greater_than",
         budget_numerator=1,budget_denominator=100,calibration_connections=n,maximum_fp=budget,
         calibration_fp=exceed.tolist(),cic_cuts=source,calibration_scores=score,
         calibration_uid_order=proof["uid_order_sha256"],reference=read(out/"PREFLIGHT.json")["reference"]))
    save(out/"CALIBRATION_READY.json",dict(status="PASS",service_instance=cap["service_instance"],
         calibration_capture=identity(out/"calibration/login.pcap"),capture_receipt=identity(out/"calibration/CAPTURE.json"),
         thresholds=identity(out/"THRESHOLDS.json"),threshold_table=identity(out/"THRESHOLDS.csv"),
         calibration_requests=len(aligned),calibration_connections=n,max_fp=budget,features=proof))


def pairing(split,aligned,q,thresholds,source):
    scenes=np.array([r["scenario"] for r in aligned])
    rates=np.array([r["scheduled_rate"] or 0 for r in aligned])
    selectors={"overall":np.ones(len(aligned),dtype=bool)}
    if split=="stress":
        selectors.update({f"reconnect_{r}_per_min":rates==r for r in RATES})
    else:
        selectors.update({r:scenes==r for r in (*ORDINARY,RECOVER)})
    answer=[]
    for name,sel in selectors.items():
        if not sel.any():
            continue
        vv=q["scores"][:,sel,:]
        cc=connection_scores(vv,q["stream"][sel])
        for mode,tau in zip(MODES,(np.broadcast_to(source,thresholds.shape),thresholds)):
            for unit,values in (("request",vv),("connection",cc)):
                alarms=values>tau[:,None,:]
                n=values.shape[1]
                for i,a in enumerate(ARMS):
                    for j,h in enumerate(HEADS):
                        raw=alarms[0,:,j]
                        v=alarms[i,:,j]
                        fp=int(v.sum())
                        answer.append(dict(split=split,group=name,mode=mode,arm=a,head=h,unit=unit,
                                           denominator=n,false_positives=fp,fpr=fp/n,raw_false_positives=int(raw.sum()),
                                           both_alarm=int((raw&v).sum()),raw_only=int((raw&~v).sum()),
                                           arm_only=int((~raw&v).sum()),neither=int((~raw&~v).sum()),
                                           meets_one_pct_budget=(fp*100<=n) if unit=="connection" else ""))
    return answer


def render(out,normal,stress,seal):
    labels=dict(RAW="RAW",v12_CCNR="原 CCNR",relative_handshake="CCNR＋相对握手")
    lines=["# 同服务阈值校准结果","",
           f"校准用了 {seal['calibration_requests']} 次请求、{seal['calibration_connections']} 条连接。"
           f"各组允许的校准误报上限为 {seal['max_fp']} 条连接。","",
           "## 独立正常留出","",
           "| 阈值 | 三种子集成 | 误报请求／正常请求 | 误报连接／正常连接 | 连接级误报率 | 达到 1% |",
           "|---|---|---:|---:|---:|---|"]
    def append_group(rows):
        overall={(r["mode"],r["arm"],r["unit"]):r for r in rows if r["group"]=="overall" and r["head"]=="ensemble"}
        for mode,m in ((MODES[1],"登录服务校准"),(MODES[0],"CIC 固定")):
            for a in ARMS:
                q=overall[mode,a,"request"]
                c=overall[mode,a,"connection"]
                met="是" if c["meets_one_pct_budget"] else "否"
                lines.append(f"| {m} | {labels[a]} | {q['false_positives']}/{q['denominator']} | "
                             f"{c['false_positives']}/{c['denominator']} | {c['fpr']:.2%} | {met} |")
    append_group(normal)
    lines+=["","**攻击检出待测。** 现有带标签记录属于其他登录端点，当前比较无法回答在预算内哪组多抓住攻击。","",
            "## 旧批次突发重连压力测试","",
            "以下为此前 51 条重连连接的独立结果。每分钟 1、3、5、8 次的分层见压力测试配对小表。","",
            "| 阈值 | 三种子集成 | 误报请求／正常请求 | 误报连接／正常连接 | 连接级误报率 | 达到 1% |",
            "|---|---|---:|---:|---:|---|"]
    append_group(stress)
    lines+=["","## 原 CIC、UNSW 与 Edge 回检","",
            "在 CIC 固定阈值下，复核两份已验收的原口径配对表。各数据集的泛洪及正常计数见回检小表。","",
            "两批新采集使用同一个 WSL 服务进程及上批相同的登录端点。固定参考库来自上批服务进程。",""]
    (out/"RESULTS_FOR_PAPER.md").write_bytes("\n".join(lines).encode("utf8"))


def evaluation(out,base,cfg,pins):
    seal=read(out/"CALIBRATION_READY.json")
    policy=read(out/"THRESHOLDS.json")
    assert seal["status"]=="PASS" and identity(out/"THRESHOLDS.json")==seal["thresholds"]
    source=np.array(cfg["method"]["cuts"])
    assert np.array_equal(source,policy["cic_cuts"]) and policy["reference"]==identity(base/"enrollment/REFERENCE.npz")
    assert identity(out/"calibration/SCORES.npz")==policy["calibration_scores"]
    cap,report,aligned,q,proof,score=get_normal(out,base,"holdout",cfg,pins)
    prev=read(out/"calibration/CAPTURE.json")
    done=read(out/"COLLECTION_DONE.json")
    assert done["status"]=="PASS" and done["namespaces_released"]
    assert cap["service_instance"]==prev["service_instance"]==seal["service_instance"]==done["service_instance"]
    assert cap["service_pid"]==prev["service_pid"] and cap["endpoints"]==prev["endpoints"]
    assert cap["capture"]["first_qualifying_ns"]>prev["capture"]["last_frame_ns"]+60*NS
    old_cal=get_array(out/"calibration/SCORES.npz")
    assert not set(old_cal["uid"])&set(q["uid"])
    fixed=np.array(policy["thresholds"])
    assert np.array_equal(fit(old_cal["scores"],old_cal["stream"])[0],fixed)
    table_data=pairing("holdout",aligned,q,fixed,source)
    table(out/"PAIRED.csv",table_data)
    old_align,archive=saved_formal(base)
    mask=np.array([r["scenario"]==BURST for r in old_align])
    assert mask.sum()==51 and len(set(archive["stream"][mask]))==51
    assert not set(archive["uid"])&(set(q["uid"])|set(old_cal["uid"]))
    stress=pairing("stress",[r for r,m in zip(old_align,mask) if m],
                   dict(scores=archive["scores"][KEPT][:,mask,:],stream=archive["stream"][mask]),fixed,source)
    table(out/"STRESS_PAIRED.csv",stress)
    render(out,table_data,stress,seal)
    receipt=dict(status="PASS",arm_count=len(ARMS),holdout_queries=len(aligned),holdout_connections=report["checks"]["tcp_connections"],
                 calibration=identity(out/"CALIBRATION_READY.json"),holdout_features=proof,holdout_scores=score,
                 sealed_reference=identity(base/"enrollment/REFERENCE.npz"),stress_source=identity(base/"evaluation/DECISIONS.npz"),
                 stress_connections=51,attacks="PENDING_ATTACK_EVALUATION",flood_check=identity(out/"FLOOD_CHECK.json"),
                 paired=identity(out/"PAIRED.csv"),stress_paired=identity(out/"STRESS_PAIRED.csv"))
    save(out/"ACCEPTANCE.json",receipt)
    evidence=["METHOD.md","EXECUTION.json","PREFLIGHT.json","ATTACK_QUALIFICATION.csv","ATTACK_QUALIFICATION.json",
              "ORIGINAL_FLOOD_CHECK.csv","FLOOD_CHECK.json","THRESHOLDS.csv","THRESHOLDS.json",
              "CALIBRATION_READY.json","COLLECTION_DONE.json","PAIRED.csv","STRESS_PAIRED.csv","RESULTS_FOR_PAPER.md","ACCEPTANCE.json"]
    for folder in ("calibration","holdout"):
        evidence.extend(x.relative_to(out).as_posix() for x in (out/folder).iterdir() if x.is_file())
    rows={n:identity(out/n)["sha256"] for n in sorted(evidence)}
    (out/"SHA256SUMS").write_bytes("".join(f"{h}  {n}\n" for n,h in rows.items()).encode("ascii"))
    assert all(identity(out/n)["sha256"]==h for n,h in rows.items())


if __name__=="__main__":
    mode=sys.argv[1]
    out,base=map(Path,sys.argv[2:4])
    with sealed_runtime() as (cfg,pins):
        {"preflight":preflight,"calibration":calibration,"holdout":evaluation}[mode](out,base,cfg,pins)
    print(f"{mode} PASS",flush=True)
