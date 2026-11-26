"""Audit the paced reconnects and replay the frozen four-arm decisions."""
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

from frozen_assets import scoring_runtime
from assessment import arrays, get_array, roster, scores_for
from audit import NS, join, write_tables
from audit_formal import new_after_close
from frozen_score import digest_order
from protocol_reconnect import HANDSHAKE_CUT, REFERENCE, STAGE
from schedule import BURST, ORDINARY
from sources import ARMS, HEADS, identity, read, save, table


def audit_capture(folder, cap, item):
    pacing = []
    plan = item["schedule"]
    rate = item["scheduled_rate"]

    def verify(aligned, events, handshakes, packets):
        by_id = defaultdict(list)
        for row in aligned:
            assert row["aligned"] and row["normal"] and row["authenticated"]
            assert row["request_index"]==1 and row["observed_status"]==row["expected_status"]==200
            by_id[row["scenario_id"]].append(row)
        planned = {action["scenario_id"] for action in plan["actions"]}
        assert set(by_id)==planned|{key+"-setup" for key in planned}
        assert len(handshakes)==len(aligned)==item["connections"]+3
        assert len({row["tcp_stream"] for row in aligned})==len(handshakes)
        for action, size in zip(plan["actions"],item["per_client"],strict=True):
            key = action["scenario_id"]
            client = action["client"]+1
            origin, = by_id[key+"-setup"]
            assert origin["client"]==client and origin["scenario"]==ORDINARY[0]
            order = sorted(by_id[key],key=lambda r:r["reconnect_step"])
            assert len(order)==size and [r["reconnect_step"] for r in order]==list(range(1,size+1))
            assert all(r["scheduled_rate"]==rate and r["scenario"]==BURST and r["client"]==client for r in order)
            assert all(new_after_close(a,b,handshakes,packets,require_reset=True)
                       for a,b in zip([origin,*order[:-1]],order,strict=True))
            minute_start, = [event for event in events[key] if event["event"]=="minute_start"]
            assert minute_start["scheduled_rate"]==rate
            start = minute_start["time_ns"]
            syn = [handshakes[r["tcp_stream"]][0]["ns"] for r in order]
            assert syn==sorted(syn) and start<=syn[0]
            offsets = [(t-start)/NS for t in syn]
            windows = Counter(int(t//60) for t in offsets)
            expected = Counter(int(t//60) for t in action["within_minute_s"])
            assert windows==expected
            for j,row in enumerate(order):
                minute = int(offsets[j]//60)
                pacing.append(dict(client=client,ordinal=j+1,rate_per_client=rate,minute=minute+1,
                                   planned_minute_connections=expected[minute],observed_minute_connections=windows[minute],
                                   planned_offset_s=action["within_minute_s"][j],observed_syn_offset_s=offsets[j],
                                   syn_ns=syn[j],h60=row["handshakes_60s"],connection=row["tcp_stream"]))
        return [dict(scenario=scene,cases=3,proved_cases=3,requests=count,connections=count,aligned=count,
                     unaligned=0,observed_200=count,observed_401=0)
                for scene,count in ((ORDINARY[0],3),(BURST,item["connections"]))]

    report, bound, fields = join(folder,cap,verify)
    assert report["status"]=="PASS"
    checks = report["checks"]
    assert checks["complete_duplex_handshakes"]==checks["aligned_requests"]==item["connections"]+3
    assert all(min(value.values())>0 for value in checks["direction_counts"].values())
    write_tables(folder,report,bound)
    table(folder/"PACING.csv",pacing)
    return report, roster(r for r in bound if r["scenario"]==BURST), fields


def score_attempt(root, attempt, item, pin):
    e = root/"evidence"
    folder = attempt/STAGE
    cap = read(folder/"CAPTURE.json")
    assert cap["registered_batch"]==item["key"] and read(folder/"SCHEDULE.json")==item["schedule"]
    assert [[x["ip"],x["mac"]] for x in cap["endpoints"]]==pin["endpoints"]
    assert cap["server_port"]==pin["server_port"] and cap["kernel"]==pin["kernel"]
    assert cap["capture"]["capture_kernel_drops"]==0 and cap["capture"]["stop_reason"]=="PLANNED"
    assert read(attempt/"COLLECTION_DONE.json")==dict(status="PASS",service_instance=cap["service_instance"],
                                                      namespaces_released=True)
    audit, rows, fields = audit_capture(folder,cap,item)
    uid,stream = arrays(rows)
    assert len(uid)==len(set(stream))==item["connections"]
    query = dict(status="PASS",batch=item["key"],ordered_uid_sha256=digest_order(uid),uid=uid.tolist(),
                 scope="registered reconnect POST only, one successful POST per connection",
                 pcap=identity(folder/"login.pcap"),connections=stream.tolist())
    save(attempt/"QUALIFIED_ROSTER.json",query)

    ref = root.parent/REFERENCE
    assert identity(ref/"enrollment/REFERENCE.npz")==pin["reference"]
    assert identity(root.parent/pin["rank5_archive"]/"THRESHOLDS.json")==pin["rank5_thresholds"]
    with scoring_runtime(root/"live") as (cfg, pins):
        assert cfg["method"]["cuts"]==pin["cic_cuts"]
        q, proof = scores_for(ref,folder,cap,fields,rows,cfg,pins)
    p = np.asarray(pin["cuts"])
    decisions = q["scores"]>p[:,None,:]
    assert np.array_equal(q["uid"],uid) and np.array_equal(q["stream"],stream)
    assert all(r["handshakes_60s"]==h for r,h in zip(rows,q["h"],strict=True))
    h_flags = q["h"]>HANDSHAKE_CUT
    if item["key"]=="preflight":
        assert h_flags.any() and not h_flags.all()
    score = attempt/"SCORES.npz"
    np.savez_compressed(score,**q,arms=np.asarray(ARMS),head_names=np.asarray(HEADS),local_cuts=p,
                        local_decisions=decisions,handshake_only=h_flags,frame=[r["frame"] for r in rows])
    files = sorted(p for p in attempt.rglob("*") if p.is_file() and p.name!="BATCH_ACCEPTANCE.json")
    receipt = dict(status="PASS",batch=item["key"],scheduled_rate=item["scheduled_rate"],
                   connections=len(stream),eligible_posts=len(rows),setup_connections=3,
                   complete_duplex_handshakes=audit["checks"]["complete_duplex_handshakes"],kernel_drops=0,
                   unaligned_posts=0,auth_successes=len(rows)+3,instance=cap["service_instance"],
                   start_ns=cap["capture"]["start_ns"],first_frame_ns=cap["capture"]["first_qualifying_ns"],
                   last_frame_ns=cap["capture"]["last_frame_ns"],end_ns=cap["capture"]["end_ns"],
                   uid_order=digest_order(uid),plan=identity(e/"REGISTRATION.json"),features=proof,
                   flags=dict(zip((*ARMS,"handshake_only"),[*(int(n) for n in decisions[:,:,3].sum(axis=1)),int(h_flags.sum())])),
                   h60=dict(sorted(Counter(q["h"].tolist()).items())),
                   files={p.relative_to(attempt).as_posix():identity(p) for p in files})
    save(attempt/"BATCH_ACCEPTANCE.json",receipt)
    print(item["key"],"PASS",receipt["connections"],receipt["flags"],flush=True)


def verified_batch(attempt,item,pin,pin_file):
    receipt = read(attempt/"BATCH_ACCEPTANCE.json")
    assert receipt["status"]=="PASS" and receipt["batch"]==item["key"]
    assert receipt["connections"]==receipt["eligible_posts"]==item["connections"]
    assert receipt["complete_duplex_handshakes"]==receipt["auth_successes"]==item["connections"]+3
    assert receipt["kernel_drops"]==receipt["unaligned_posts"]==0 and receipt["plan"]==identity(pin_file)
    for name,digest in receipt["files"].items():
        path = (attempt/name).resolve()
        assert path.is_relative_to(attempt.resolve()) and identity(path)==digest
    p = get_array(attempt/"SCORES.npz")
    assert len(p["uid"])==len(set(p["stream"]))==item["connections"]
    assert digest_order(p["uid"])==receipt["uid_order"] and tuple(p["arms"])==ARMS
    assert np.array_equal(p["local_cuts"],pin["cuts"])
    assert np.array_equal(p["local_decisions"],p["scores"]>p["local_cuts"][:,None,:])
    assert np.array_equal(p["handshake_only"],p["h"]>HANDSHAKE_CUT)
    return receipt, dict(name=item["key"],uid=p["uid"],stream=p["stream"],score=p["scores"],h=p["h"],normal=True)
