"""Verify each POST, reconstruct its raw source windows, then use the frozen scorer."""
from collections import Counter
from ipaddress import IPv4Address

import numpy as np

from single_inputs import scoring_runtime
from assessment import arrays, get_array, roster, scores_for
from audit import NS, join, write_tables
from audit_formal import new_after_close
from bank import packet_stream
from frozen_score import digest_order
from protocol_reconnect import HANDSHAKE_CUT
from schedule import BURST, ORDINARY
from single_protocol import REFERENCE, STAGE
from sources import ARMS, HEADS, identity, read, save, table


def audit_capture(folder,cap,item):
    action, = item["schedule"]["actions"]
    client,rate,key = item["client"],item["scheduled_rate"],action["scenario_id"]
    count = item["connections"]
    pacing = []

    def verify(aligned,events,handshakes,packets):
        assert len(handshakes)==len(aligned)==count+1
        assert len({r["tcp_stream"] for r in aligned})==count+1
        assert all(r["aligned"] and r["normal"] and r["authenticated"] and r["client"]==client
                   and r["request_index"]==1 and r["observed_status"]==r["expected_status"]==200 for r in aligned)
        origin, = [r for r in aligned if r["scenario_id"]==key+"-setup" and r["scenario"]==ORDINARY[0]]
        ordered = sorted((r for r in aligned if r["scenario_id"]==key and r["scenario"]==BURST),
                         key=lambda r:r["reconnect_step"])
        assert len(ordered)==count and [r["reconnect_step"] for r in ordered]==list(range(1,count+1))
        assert all(r["scheduled_rate"]==rate for r in ordered)
        assert all(new_after_close(a,b,handshakes,packets,require_reset=True)
                   for a,b in zip([origin,*ordered[:-1]],ordered,strict=True))
        event, = [x for x in events[key] if x["event"]=="minute_start"]
        assert event["scheduled_rate"]==rate
        syn = [handshakes[r["tcp_stream"]][0]["ns"] for r in ordered]
        assert syn==sorted(syn) and syn[0]>=event["time_ns"]
        offsets = [(t-event["time_ns"])/NS for t in syn]
        windows = Counter(int(t//60) for t in offsets)
        assert windows==Counter(int(t//60) for t in action["within_minute_s"])
        for i,row in enumerate(ordered):
            minute = int(offsets[i]//60)
            pacing.append(dict(client=client,ordinal=i+1,scheduled_rate=rate,minute=minute+1,
                               actual_connections_in_minute=windows[minute],jitter_s=item["jitter_s"][i],
                               planned_offset_s=action["within_minute_s"][i],observed_syn_offset_s=offsets[i],
                               syn_ns=syn[i],h60=row["handshakes_60s"],connection=row["tcp_stream"]))
        return [dict(scenario=scene,cases=1,proved_cases=1,requests=n,connections=n,aligned=n,
                     unaligned=0,observed_200=n,observed_401=0) for scene,n in ((ORDINARY[0],1),(BURST,count))]

    report,bound,fields = join(folder,cap,verify)
    assert report["status"]=="PASS"
    checks = report["checks"]
    assert checks["aligned_requests"]==checks["complete_duplex_handshakes"]==count+1
    directions = checks["direction_counts"]
    active = cap["endpoints"][client]["ip"]
    assert min(directions[active].values())>0
    assert all(not any(v.values()) for ip,v in directions.items() if ip!=active)
    write_tables(folder,report,bound)
    table(folder/"PACING.csv",pacing)
    return roster(r for r in bound if r["scenario"]==BURST),fields


def source_windows(pcap,cap,rows,client):
    from history_stream import decode, records

    server,active = cap["endpoints"][0],cap["endpoints"][client]
    target_mac = bytes.fromhex(server["mac"].replace(":",""))
    active_mac = bytes.fromhex(active["mac"].replace(":",""))
    target_ip = IPv4Address(server["ip"]).packed
    active_ip = IPv4Address(active["ip"]).packed
    anchors = {r["frame"]:r for r in rows}
    clock, ipv4, layer2, features, observations = 0, [], [], {}, []
    for frame,ns,packet in records(pcap):
        assert len(packet)>=14
        clock = max(clock,ns)
        if packet[:6]==target_mac:
            layer2.append((clock,packet[6:12]))
        ip_offset = 14
        eth_type = packet[12:14]
        while eth_type in (b"\x81\x00",b"\x88\xa8"):
            eth_type = packet[ip_offset+2:ip_offset+4]
            ip_offset += 4
        inbound = eth_type==b"\x08\x00" and packet[ip_offset+16:ip_offset+20]==target_ip
        if inbound:
            assert packet[:6]==target_mac and packet[ip_offset]>>4==4
            origin = packet[ip_offset+12:ip_offset+16]
            protocol = packet[ip_offset+9]
            size = int.from_bytes(packet[ip_offset+2:ip_offset+4],"big")
            tcp = decode(packet,False) if protocol==6 else None
            assert tcp is not None or protocol!=6
            ipv4.append((clock,origin,packet[6:12],size,tcp))
        if frame not in anchors:
            continue

        post = anchors[frame]
        assert inbound and tcp is not None and tcp.data>0
        assert origin==active_ip and packet[6:12]==active_mac and ns==post["frame_ns"]
        line = dict(uid=post["capture_uid"],frame=frame,frame_ns=ns,prefix_clock_ns=clock,
                    client=client,client_ip=active["ip"],client_mac=active["mac"])
        context = []
        for seconds in (1,10):
            left = clock-seconds*NS
            current = [item for item in ipv4 if item[0]>left]
            sources = {(ip,mac) for _,ip,mac,_,_ in current}
            macs = {mac for when,mac in layer2 if when>left}
            assert sources=={(active_ip,active_mac)} and macs=={active_mac}, ("SOURCE_WINDOW",frame,seconds)
            transport = [(size,tcp) for _,_,_,size,tcp in current if tcp is not None]
            source_n = len({tcp.endpoints[0][0] for _,tcp in transport})
            conn_n = len({tcp.endpoints for _,tcp in transport})
            byte_n = sum(size for size,_ in transport)
            assert source_n==1 and transport
            context.extend((len(transport)/seconds,byte_n/seconds,float(source_n),float(conn_n)))
            line.update({f"ipv4_src_n_{seconds}s":len(sources),f"unicast_mac_src_n_{seconds}s":len(macs),
                         f"tcp_src_n_{seconds}s":source_n,f"inbound_ipv4_frames_{seconds}s":len(current),
                         f"tcp_frames_{seconds}s":len(transport),f"tcp_bytes_{seconds}s":byte_n})
        observations.append(line)
        features[frame] = context
    assert list(features)==list(anchors) and len(observations)==len(rows)
    return observations, features


def score(root,attempt,item,pin):
    e = root/"evidence"
    folder = attempt/STAGE
    cap = read(folder/"CAPTURE.json")
    assert cap["registered_batch"]==item["key"] and cap["active_client"]==item["client"]
    assert cap["inactive_client_interfaces"]==[c for c in (1,2,3) if c!=item["client"]]
    assert read(folder/"SCHEDULE.json")==item["schedule"]
    assert [[x["ip"],x["mac"]] for x in cap["endpoints"]]==pin["endpoints"]
    assert cap["server_port"]==pin["server_port"] and cap["kernel"]==pin["kernel"]
    assert cap["capture"]["capture_kernel_drops"]==0 and cap["capture"]["stop_reason"]=="PLANNED"
    assert read(attempt/"COLLECTION_DONE.json")==dict(status="PASS",service_instance=cap["service_instance"],namespaces_released=True)
    rows,fields = audit_capture(folder,cap,item)
    pcap = folder/"login.pcap"
    windows,oracle = source_windows(pcap,cap,rows,item["client"])
    table(folder/"SOURCE_WINDOWS.csv",windows)
    uid,stream = arrays(rows)
    assert len(uid)==len(set(stream))==item["connections"]
    save(attempt/"QUALIFIED_ROSTER.json",dict(status="PASS",uid_order=digest_order(uid),
         pcap=identity(pcap),uids=uid.tolist(),streams=stream.tolist(),windows=identity(folder/"SOURCE_WINDOWS.csv")))

    reference = root.parent/REFERENCE
    assert identity(reference/"enrollment/REFERENCE.npz")==pin["reference"]
    assert identity(root.parent/pin["rank5_archive"]/"THRESHOLDS.json")==pin["rank5_thresholds"]
    with scoring_runtime(root/"live") as (cfg,pins):
        assert cfg["method"]["cuts"]==pin["cic_cuts"]
        observed = {row["frame"]:tuple(x) for row,_,x,*_ in packet_stream(pcap,cap,fields,None) if row["frame"] in oracle}
        assert observed=={k:tuple(v) for k,v in oracle.items()}
        q,proof = scores_for(reference,folder,cap,fields,rows,cfg,pins)
    assert np.array_equal(q["uid"],uid) and np.array_equal(q["stream"],stream)
    assert np.array_equal(q["h"],[r["handshakes_60s"] for r in rows])
    cut = np.asarray(pin["cuts"])
    decisions = q["scores"]>cut[:,None,:]
    hflags = q["h"]>HANDSHAKE_CUT
    if item["key"]=="preflight":
        assert hflags.any() and not hflags.all()
    np.savez_compressed(attempt/"SCORES.npz",**q,arms=np.asarray(ARMS),head_names=np.asarray(HEADS),
                        local_cuts=cut,local_decisions=decisions,handshake_only=hflags,frame=[r["frame"] for r in rows])
    files = sorted(p for p in attempt.rglob("*") if p.is_file() and p.name!="BATCH_ACCEPTANCE.json")
    receipt = dict(status="PASS",batch=item["key"],rate=item["scheduled_rate"],client=item["client"],
                   connections=len(rows),posts=len(rows),setup=1,duplex=len(rows)+1,authenticated=len(rows)+1,
                   capture_drops=0,unaligned_posts=0,instance=cap["service_instance"],
                   start_ns=cap["capture"]["start_ns"],last_frame_ns=cap["capture"]["last_frame_ns"],end_ns=cap["capture"]["end_ns"],
                   uid_order=digest_order(uid),plan=identity(e/"REGISTRATION.json"),features=proof,
                   one_source_1s=len(windows),one_source_10s=len(windows),device_8d_parity=len(observed),
                   source_windows=identity(folder/"SOURCE_WINDOWS.csv"),
                   flags=[*(int(n) for n in decisions[:,:,3].sum(axis=1)),int(hflags.sum())],
                   h60=dict(sorted(Counter(q["h"].tolist()).items())),
                   files={p.relative_to(attempt).as_posix():identity(p) for p in files})
    save(attempt/"BATCH_ACCEPTANCE.json",receipt)
    print(item["key"],"PASS",len(rows),"aligned single-source POSTs",flush=True)


def verified(attempt,item,pin,pin_file):
    cert = read(attempt/"BATCH_ACCEPTANCE.json")
    n = item["connections"]
    assert cert["status"]=="PASS" and cert["batch"]==item["key"]
    assert cert["client"]==item["client"] and cert["rate"]==item["scheduled_rate"]
    assert all(cert[key]==n for key in ("connections","posts","one_source_1s","one_source_10s","device_8d_parity"))
    assert cert["duplex"]==cert["authenticated"]==n+1 and cert["capture_drops"]==cert["unaligned_posts"]==0
    assert cert["plan"]==identity(pin_file) and cert["features"]["rows"]==n
    for name,value in cert["files"].items():
        p = (attempt/name).resolve()
        assert p.is_relative_to(attempt.resolve()) and identity(p)==value
    data = get_array(attempt/"SCORES.npz")
    assert len(data["uid"])==len(set(data["stream"]))==n and digest_order(data["uid"])==cert["uid_order"]
    assert tuple(data["arms"])==ARMS and tuple(data["head_names"])==HEADS
    assert np.array_equal(data["local_cuts"],pin["cuts"])
    assert np.array_equal(data["local_decisions"],data["scores"]>data["local_cuts"][:,None,:])
    assert np.array_equal(data["handshake_only"],data["h"]>HANDSHAKE_CUT)
    return cert,dict(name=item["key"],uid=data["uid"],stream=data["stream"],score=data["scores"],h=data["h"],normal=True)
