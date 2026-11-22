"""Qualify the local runtime, then produce paired normal false-alarm tables."""
from collections import defaultdict
import csv
from pathlib import Path
import sys

from frozen_score import HEADS, digest_order, sealed_runtime
from audit import NS, identity, join, read, save, timestamp
from audit_formal import collect_aligned
from bank import ARMS, evaluate_pairs, materialize, open_bank, packet_stream
from schedule import BURST, ORDINARY, RATES
import numpy as np


def run_slice(out,pilot,assets,cfg,pins):
    cap=read(pilot/"CAPTURE.json")
    report,align,fields=join(pilot,cap)
    assert report["status"]=="PASS" and read(out/"QUICK_CHECK.json")["status"]=="PASS"
    pcap=pilot/"login.pcap"
    t0=min(timestamp(r) for r in fields if r["tcp.dstport"]==str(cap["server_port"]))
    stop=t0+65*NS
    end=max(int(r["frame.number"]) for r in fields if timestamp(r)<=stop)
    cut=dict(first_qualifying_ns=t0,reference_end_ns=stop,cutoff_frame=end)
    candidates=[r[0] for r in packet_stream(pcap,cap,fields,cut)]
    take={r["frame"]:r["uid"] for r in candidates[::max(1,len(candidates)//64)]}
    earlier,_=materialize(pcap,cap,fields,cut,take,pins)
    starts=sorted([r for r in align if r["aligned"] and r["frame_ns"]>stop],key=lambda r:r["frame"])[:12]
    later,proof=materialize(pcap,cap,fields,None,{r["frame"]:r["capture_uid"] for r in starts},pins)
    score,decision,s,legal,pair=evaluate_pairs(later,earlier,cfg,pins,assets)
    assert score.shape==(4,len(starts),4) and np.array_equal(later["h"],[r["handshakes_60s"] for r in starts])
    assert len(set(earlier["component"]))>=2 and (earlier["clock"]<=stop).all()
    assert (later["clock"]>stop).all() and (legal[0]>=2).all()
    assert np.array_equal(s[0],s[1]) and np.array_equal(decision[1],decision[2])
    save(out/"ENGINEERING_SLICE.json",dict(status="PASS",source_pcap=report["pcap"],rows=len(starts),
                   training_reference_records=len(take),feature_witness=proof,
                   real_rows_with_two_compatible_components=(pair>=2).sum(axis=1).tolist(),
                   arms=list(ARMS),support_receipt="causal real pilot-prefix engineering slice"))


def build(out,pins):
    folder=out/"enrollment"
    c,_,_,fields=collect_aligned(folder)
    receipt=open_bank(folder,c,fields,pins)
    assert receipt["reference_components"]>=2 and receipt["same_service_components"]>=2
    save(out/"BANK_READY.json",receipt)


def csv_write(path,rows):
    with path.open("w",encoding="utf8",newline="") as stream:
        w=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def summarize(align,dec,legal,compatible):
    groups=[("overall",np.ones(len(align),bool))]
    groups.extend((k,np.array([r["scenario"]==k for r in align])) for k in (*ORDINARY,BURST))
    groups.extend((f"reconnect_{rate}_per_min",np.array([r["scenario"]==BURST and r["scheduled_rate"]==rate for r in align]))
                  for rate in RATES)
    stream=np.asarray([r["tcp_stream"] for r in align])
    answer=[]
    for group,sel in groups:
        distinct,index=np.unique(stream[sel],return_inverse=True)
        assert sel.any()
        for j,head in enumerate((*HEADS,"ensemble")):
            for k,arm in enumerate(ARMS):
                raw=dec[0,sel,j]
                active=dec[k,sel,j]
                why=np.zeros(len(active),np.int8)
                if k:
                    with_ref=legal[k-1,sel]>=2
                    match=compatible[k-1,sel]>=2
                    why[active]=np.where(match[active],3,np.where(with_ref[active],2,1))
                    assert np.array_equal(why>0,active) and (match<=with_ref).all()
                else:
                    why[active]=4
                raw_conn=np.zeros(len(distinct),bool)
                np.logical_or.at(raw_conn,index,raw)
                why_conn=np.zeros(len(distinct),np.int8)
                np.maximum.at(why_conn,index,why)
                # A connection with a matched alert is counted once in that category.
                for unit,n,b,r in (("request",int(sel.sum()),int(raw.sum()),why),
                                    ("connection",len(distinct),int(raw_conn.sum()),why_conn)):
                    after=int((r>0).sum())
                    categories=np.bincount(r,minlength=5)
                    assert b>=after
                    answer.append(dict(group=group,head=head,arm=arm,unit=unit,denominator=n,
                                       raw_false_positives=b,false_positives=after,removed=b-after,
                                       raw_fallback_legal_components_lt2=int(categories[1]) if k else "",
                                       raw_fallback_compatible_components_lt2=int(categories[2]) if k else "",
                                       matched_still_false_positive=int(categories[3]) if k else ""))
    return answer


def render(rows,bank,trace,report,quick,minutes):
    names={"overall":"全部","successful_login":"成功登录","mistake_then_retry":"同 TCP 连接内输错后成功",
           "cross_connection_retry":"重建 TCP 后重试成功","burst_reconnect":"短时合法重连合计",
           **{f"reconnect_{r}_per_min":f"每分钟 {r} 次合法重连" for r in RATES}}
    lines=["# 同服务正式正常采集和误报评价","",
           f"从原帧 {bank['boundary']['first_qualifying_frame']} 起计满 7,200 秒，参考截止帧为 {bank['boundary']['cutoff_frame']}，"
           f"第 {bank['boundary']['crossing_frame']} 帧提供跨界证据。封存 {bank['reference_rows']:,} 条参考、"
           f"{bank['same_service_components']:,} 个同服务组件。两期使用同一服务实例和端口。","",
           f"评价共 {report['checks']['aligned_requests']} 次正常请求、{report['checks']['tcp_connections']} 条连接。"
           f"{len(minutes)} 个一分钟区块的重连次数均由原 SYN 核实。计划好的输错请求按正常行为统计。","",
           "| 三种子集成 | 单位 | 分母 | RAW | 原 CCNR | R2＋U1 | 相对握手距离 |",
           "|---|---|---:|---:|---:|---:|---:|"]
    idx={(r["group"],r["unit"],r["arm"]):r for r in rows if r["head"]=="ensemble"}
    for k,label in names.items():
        for unit in ("request","connection"):
            a=[idx[k,unit,arm] for arm in ARMS]
            lines.append("| "+" | ".join([label,"请求" if unit=="request" else "连接",
                         str(a[0]["denominator"]),*[str(r["false_positives"]) for r in a]])+" |")
    lines+=["","## 跨连接重试和突发重连",""]
    for group in ("cross_connection_retry","burst_reconnect"):
        lines.append(f"**{names[group]}**")
        lines.append("")
        for arm in ARMS[1:]:
            q=idx[group,"request",arm]
            c=idx[group,"connection",arm]
            a=q["raw_fallback_legal_components_lt2"]+q["raw_fallback_compatible_components_lt2"]
            b=c["raw_fallback_legal_components_lt2"]+c["raw_fallback_compatible_components_lt2"]
            lines.append(f"- {arm} 参考不足沿用 RAW 后误报 {a} 次请求、{b} 条连接。"
                         f"完成匹配后仍误报 {q['matched_still_false_positive']} 次请求、{c['matched_still_false_positive']} 条连接。")
        lines.append("")
    lines.extend(("连接出现任一评估请求告警即计一次。如同一连接兼有两类告警，优先归于完成匹配后仍误报。"
                  "小表再将参考不足拆为合法组件少于两个、合法组件充足但相容组件少于两个。","",
                  "四组使用同一批评价 UID、原源阈值、冻结模型和固定的 p=4、λ=0.25。"
                  "R2＋U1 按实际握手角色及服务端口筛选。相对握手距离由同设备、同源 IP、同服务端口的 60 秒观测计算。","",
                  "单种子与集成结果见配对表。",""))
    return "\n".join(lines)


def evaluation(out,assets,cfg,pins):
    folder=out/"evaluation"
    c,report,result,fields=collect_aligned(folder)
    b=read(out/"BANK_READY.json")
    collect=read(out/"COLLECTION_DONE.json")
    first=read(out/"enrollment/CAPTURE.json")
    assert c["service_instance"]==b["service_instance"]==collect["service_instance"]==first["service_instance"]
    assert c["service_pid"]==first["service_pid"] and c["endpoints"]==first["endpoints"]
    assert c["capture"]["first_qualifying_ns"]>first["capture"]["last_frame_ns"]+60*NS
    ref_path=out/"enrollment/REFERENCE.npz"
    assert identity(ref_path)==b["reference"]
    with np.load(ref_path,allow_pickle=False) as x:
        ref={k:x[k] for k in x.files}
    align=sorted([r for r in result if r["aligned"]],key=lambda r:r["frame"])
    q,proof=materialize(folder/"login.pcap",c,fields,None,{r["frame"]:r["capture_uid"] for r in align},pins)
    assert digest_order(q["uid"])==report["checks"]["request_uid_order_sha256"] and np.array_equal(q["h"],[r["handshakes_60s"] for r in align])
    assert not set(q["uid"])&set(ref["uid"])
    assert (q["clock"]>b["reference_end_ns"]).all() and (ref["clock"]<=b["reference_end_ns"]).all()
    values,dec,support,legal,compatible=evaluate_pairs(q,ref,cfg,pins,assets)
    path=folder/"DECISIONS.npz"
    np.savez_compressed(path,uid=q["uid"],frame=q["frame"],h=q["h"],decision=dec,scores=values,
                        support=support,legal_components=legal,compatible_components=compatible,
                        stream=[r["tcp_stream"] for r in align],arms=np.asarray(ARMS))
    paired=summarize(align,dec,legal,compatible)
    csv_write(out/"PAIRED.csv",paired)
    minute=read(folder/"MINUTES.json")["blocks"]
    fast=read(out/"QUICK_CHECK.json")
    (out/"RESULTS_FOR_PAPER.md").write_bytes(render(paired,b,c,report,fast,minute).encode("utf8"))
    receipt=dict(status="PASS",normal_requests=len(align),connections=report["checks"]["tcp_connections"],
                 cutoff=b["boundary"],same_service_components=b["same_service_components"],
                 test_query_uid_order=proof["uid_order_sha256"],service_instance=c["service_instance"],
                 feature_witness=proof,decisions=identity(path),paired=identity(out/"PAIRED.csv"),
                 minutes=minute,cutoff_sha=identity(out/"BANK_READY.json"),asset_check=identity(out/"QUICK_CHECK.json"))
    save(out/"ACCEPTANCE.json",receipt)
    stable=["METHOD.md","EXECUTION.json","WINDOWS_REPAIR.json","QUICK_CHECK.json","ENGINEERING_SLICE.json","PILOT_SCORES.npz","BANK_READY.json",
            "COLLECTION_DONE.json","PAIRED.csv","RESULTS_FOR_PAPER.md","ACCEPTANCE.json"]
    for folder_name in ("enrollment","evaluation","frozen_quick_check_assets"):
        stable.extend((p.relative_to(out).as_posix() for p in (out/folder_name).iterdir() if p.is_file()))
    hashes={n:identity(out/n)["sha256"] for n in sorted(stable)}
    (out/"SHA256SUMS").write_bytes("".join(f"{h}  {n}\n" for n,h in hashes.items()).encode("ascii"))
    assert all(identity(out/n)["sha256"]==h for n,h in hashes.items())
    return receipt


if __name__=="__main__":
    mode=sys.argv[1]
    out,assets=map(Path,sys.argv[2:4])
    with sealed_runtime() as (cfg,pins):
        if mode=="slice":
            run_slice(out,Path(sys.argv[4]),assets,cfg,pins)
        elif mode=="enrollment":
            build(out,pins)
        else:
            evaluation(out,assets,cfg,pins)
