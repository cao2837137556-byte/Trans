"""Qualify the Windows fix with the affected real batches, then the complete archived bank."""
import argparse
import hashlib
from pathlib import Path
import time

import numpy as np

from frozen_score import e3_batch, sealed_runtime
from audit import identity, join, read, save
from audit_formal import scene_callback
from bank import boundary, evaluate_pairs, materialize, packet_stream, select_frozen, snapshots

FEATURE=Path(__file__).resolve().parent.parent/"p4_login_pilot_v1_20261121/feature_witness.py"


def reference_inputs(source,witness):
    folder=source/"enrollment"
    c=read(folder/"CAPTURE.json")
    pcap=folder/"login.pcap"
    assert identity(pcap)==witness["archive"]
    report,_,fields=join(folder,c,scene_callback(read(folder/"SCHEDULE.json"),"enrollment",[]))
    assert report["status"]=="PASS"
    assert report["checks"]["aligned_requests"]==witness["requests"]
    cut=boundary(c,fields)
    assert cut==witness["boundaries"]
    candidates=[r[0] for r in packet_stream(pcap,c,fields,cut)]
    chosen,components,_=select_frozen(candidates,cut)
    assert len(chosen)==witness["rows"] and components==witness["components"]
    matrix,inputs=snapshots(pcap,c,fields,cut,{r["frame"]:r["uid"] for r in chosen})
    return matrix,inputs


def replay(source,out):
    fault=source/"FAULT_PROBE_V2.json"
    defect=read(fault)
    cases=[]
    samples=[]
    with sealed_runtime() as (_,pins):
        for batch in defect["cases"]:
            name=batch["batch"]
            assert Path(name).name==name
            matrix,inputs=reference_inputs(source.parent/name,batch)
            position={uid:i for i,uid in enumerate(matrix["uid"])}
            for expected in batch["cases"]:
                uid=expected["uid"]
                i=position[uid]
                assert int(matrix["frame"][i])==expected["frame"]
                cases.append(dict(**expected,archive=name))
                samples.append(inputs[i])
        vectors,encoder,batches=e3_batch(samples,pins)
    assert vectors.shape==(len(cases),768) and batches==len(cases)
    actual={v["uid"]:v for v in encoder["windows_singleton_checks"]}
    for expected in cases:
        uid=expected["uid"]
        if expected["four_thread_spread"]:
            check=actual[uid]
            assert check["original_max_abs_spread"]==check["repeated_max_abs_spread"]==expected["four_thread_spread"]
            assert check["first_row_repeat_delta"]==0. and check["representative_slot"]==0
        else:
            assert uid not in actual
    receipt=dict(status="PASS",cases=cases,source=source.name,archive_proofs=defect["cases"],
                 repeated_singleton_checks=list(actual.values()),implementation=identity(FEATURE),probe=identity(fault))
    save(out/"WINDOWS_REPAIR.json",receipt)
    print(f"WINDOWS_REPAIR PASS {len(cases)} singleton batches across two existing captures",flush=True)


def full_archive(source,out,pilot):
    checked=read(out/"WINDOWS_REPAIR.json")
    assert checked["status"]=="PASS" and checked["implementation"]==identity(FEATURE)
    expected,=[x for x in checked["archive_proofs"] if x["batch"]==source.name]
    last=0.
    def progress(done,total):
        nonlocal last
        now=time.monotonic()
        if done==total or now-last>3.:
            try:
                save(out/"ARCHIVED_BANK_PROGRESS.json",dict(completed=done,total=total,source=source.name))
                last=now
            except PermissionError:
                pass
    with sealed_runtime() as (cfg,pins):
        ref,inputs=reference_inputs(source,expected)
        progress(0,len(inputs))
        z,encoder,batches=e3_batch(inputs,pins,progress=progress)
        assert z.shape==(expected["rows"],768)
        ref["z"]=z
        failed={r["uid"] for r in expected["cases"] if r["four_thread_spread"]}
        recovered={x["uid"] for x in encoder["windows_singleton_checks"]}
        assert failed==recovered

        cap=read(pilot/"CAPTURE.json")
        report,align,fields=join(pilot,cap)
        assert report["status"]=="PASS"
        small=sorted((r for r in align if r["aligned"]),key=lambda r:r["frame"])[:12]
        q,_=materialize(pilot/"login.pcap",cap,fields,None,{r["frame"]:r["capture_uid"] for r in small},pins)
        values,dec,support,legal,compatible=evaluate_pairs(q,ref,cfg,pins,out/"frozen_quick_check_assets")
        assert dec.shape==(4,12,4) and np.isfinite(values).all()
        assert (legal[0]>=2).all() and np.array_equal(support[0],support[1])
    receipt=dict(status="PASS",purpose="engineering check using sealed captures",source=source.name,
                 archive=expected["archive"],rows=len(ref["uid"]),physical_batches=batches,
                 encoder=encoder,embeddings_sha256=hashlib.sha256(ref["z"].tobytes()).hexdigest(),
                 real_score_queries=len(small),score_arms=dec.shape[0],implementation=identity(FEATURE))
    save(out/"SEALED_REFERENCE_CHECK.json",receipt)
    print(f"SEALED_REFERENCE_CHECK PASS {len(ref['uid'])} rows and {len(small)} real four-arm queries",flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("source",type=Path)
    parser.add_argument("out",type=Path)
    parser.add_argument("--full",type=Path)
    args=parser.parse_args()
    if args.full:
        full_archive(args.source,args.out,args.full)
    else:
        replay(args.source,args.out)
