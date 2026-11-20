"""Independent original-frame census. No learned parameters or model outputs."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
OWNER = "0c:c4:7a:0b:5b:ae"
MASTER = "10.2.33.223"
SLAVE = "10.2.32.133"
PART = "EXTERNAL_ARCHIVAL_EVALUATION"
NS = 10**9
NORMAL = ("cap_00001_20210318035345", "cap_00002_20210318044452", "cap_00003_20210318053559")
ATTACK = ("cap_00001_20210318095210", "cap_00001_20210318100414", "cap_00001_20210318101444")
GROUPS = ("normal", "F1", "F2", "F3")
COUNTS = dict(zip(GROUPS, (3334, 3547, 2765, 5370)))


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(obj):
    return sha(json.dumps(obj, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode())


def order(uids):
    return sha("".join(v + "\n" for v in uids).encode())


def tick(utc):
    stamp, fraction = utc.removesuffix("Z").split(".")
    return int(datetime.fromisoformat(stamp).replace(tzinfo=timezone.utc).timestamp()) * NS + int(fraction.ljust(9, "0"))


def uid(pin, frame):
    return canonical([pin, frame, OWNER])


def frames(data):
    pos = 0
    frame = 0
    resolution = None
    while pos < len(data):
        kind, size = struct.unpack_from("<II", data, pos)
        end = pos + size
        check(size >= 12 and size % 4 == 0 and end <= len(data)
              and struct.unpack_from("<I", data, end-4)[0] == size, "PCAPNG_BLOCK")
        if kind == 1:
            check(struct.unpack_from("<H", data, pos+8)[0] == 1, "ETHERNET_REQUIRED")
            opt = pos + 16
            resolution = 6
            while opt + 4 <= end-4:
                tag, length = struct.unpack_from("<HH", data, opt)
                if tag == 9:
                    resolution = data[opt+4]
                opt += 4 + ((length+3)//4)*4
        if kind == 6:
            iface, hi, lo, cap, wire = struct.unpack_from("<5I", data, pos+8)
            check(resolution == 9 and iface == 0 and cap == wire and cap+32 <= size, "EPB_CLOCK_LENGTH")
            frame += 1
            yield frame, (hi << 32) + lo, data[pos+28:pos+28+cap]
        pos = end


def network(b):
    if b[12:14] != b"\x08\x00":
        return None
    proto = b[23]
    if proto not in (6, 17):
        return None
    ihl = (b[14] & 15)*4
    size = int.from_bytes(b[16:18], "big")
    check(not int.from_bytes(b[20:22], "big") & 0x3fff and len(b) >= 14+size and ihl >= 20, "IP_HEADER")
    t = 14+ihl
    sp, dp = struct.unpack_from("!HH", b, t)
    hlen = (b[t+12] >> 4)*4 if proto == 6 else 8
    check(size >= ihl+hlen and hlen >= (20 if proto==6 else 8), "TRANSPORT_HEADER")
    return (socket.inet_ntoa(b[26:30]), socket.inet_ntoa(b[30:34]), b[6:12].hex(":"), b[:6].hex(":"),
            proto, sp, dp, b[t+13] if proto==6 else 0, b[t+hlen:14+size])


def choose(rows):
    """B2's sole last-component anchor, then the frozen dense selector.

    Replace only its O(N*K) Python nearest-point scan with the identical
    full-interval NumPy minimum; use the original salted rank for ties.
    """
    import onboarding_dense_reference_v1 as dense
    from constrained_onboarding_reference_v2 import VERSION, plan_banks
    end = rows[0]["reference_end"]
    last = max(rows, key=lambda r:(r["timestamp"], r["frame"], r["uid"]))
    start = end-7200
    check(len({r["component_id"] for r in rows}) == 1, "REFERENCE_COMPONENT_CENSUS")
    census = dict(generator_version=VERSION, status="COMPLETE", enumeration="ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT",
                  window_closed=True, duration_seconds=7200, t0=start, cutoff=end, candidate_rows=1,
                  candidates_sha256=canonical([last]), decoder_identity={"reader":"PCAPNG_NS_ORIGINAL_FRAMES"},
                  source_sha256=last["source_sha256"], normality_evidence="Publisher clean rolling capture",
                  device_registry=[dict(device=MASTER,owner=OWNER,partition=PART)], capture_id=last["capture_id"],
                  cutoff_frame=last["bank_end_frame"])
    anchors = {r["uid"] for r in plan_banks([last],census,t0=start,policy="B2")["rows"]}
    check(anchors == {last["uid"]}, "B2_LAST_COMPONENT")
    scopes = {r["capture_id"]:dict(partition=PART,device=MASTER,capture_id=r["capture_id"],
                source_sha256=r["source_sha256"],start=start,end=end,reference_end=end,frame_end=r["bank_end_frame"]) for r in rows}

    def nearest(rr, count, salt):
        ranked = sorted(rr, key=lambda r:(r["timestamp"], dense._rank(r["uid"],salt)))
        if len(rr)==count:
            return ranked
        times=np.array([r["timestamp"] for r in ranked],dtype=np.float64)
        lo,hi=float(times[0]),float(times[-1])
        picked=[]; begin=0
        for j in range(count):
            goal=(lo+hi)/2 if count==1 else lo+(hi-lo)*j/(count-1)
            stop=len(ranked)-(count-j-1)
            distance=np.abs(times[begin:stop]-goal)
            tied=np.flatnonzero(distance == distance.min())+begin
            best=min(tied,key=lambda k:dense._rank(ranked[k]["uid"],salt))
            picked.append(ranked[best]); begin=int(best)+1
        return picked

    original = dense._uniform_time
    try:
        dense._uniform_time = nearest
        result = dense.plan_dense_positions(rows,list(scopes.values()),encoded_uids=anchors,mandatory_uids=anchors)
    finally:
        dense._uniform_time = original
    check(len(result["selected_uids"])==4096 and anchors <= set(result["selected_uids"]), "DENSE_BANK")
    return result["selected_uids"]


def census(cache, proof, pins):
    start=tick(proof["normal"]["start"]["utc"]); cut=start+7200*NS
    check(cut==tick(proof["normal"]["cut"]), "CUTOFF")
    normal_frames={x[0]:x[1] for x in proof["normal"]["normal_members"]}
    normal_ends={**normal_frames,NORMAL[-1]:proof["normal"]["last_any_direction_reference_frame_in_third_member"]}
    specs={}; refs=[]; query={g:[] for g in GROUPS}; ref_in=0
    normal_hash=hashlib.sha256()
    for i,name in enumerate(NORMAL+ATTACK):
        src=pins[name]["sha256"]; data=(cache/name).read_bytes()
        check(sha(data)==src and len(data)==pins[name]["bytes"], "SOURCE:"+name)
        benign=i<3
        if benign:
            normal_hash.update(data)
        e=None if benign else proof["events"][i-3]
        stop=normal_frames[name] if benign else e["end"]["n"]
        group="normal" if benign else GROUPS[i-2]
        marks=[]; cover=[]; resolved=[]; all_inside=0; max_ns=0
        for f,ns,b in frames(data):
            if f>stop:break
            check(ns>=max_ns,"TIMESTAMP_ORDER");max_ns=ns
            h=network(b)
            if not h:continue
            sip,dip,sm,dm,proto,sp,dp,flag,body=h
            incoming=dip==MASTER and dm==OWNER
            outgoing=sip==MASTER and sm==OWNER
            if not (incoming or outgoing):continue
            if e and proto==17 and dp==502 and (b"__MiTM_ATTACK_START__" in body or b"__MiTM_ATTACK_END__" in body):
                key="start" if b"__MiTM_ATTACK_START__" in body else "end"
                target=e[key];check((f,ns,sip,dip,sm,dm)==(target["n"],tick(target["utc"]),target["src"],MASTER,target["sm"],OWNER), "EVENT_MARKER")
                marks.append(key)
            if proto!=6:continue
            comp=(proto,*sorted(((sip,sp),(dip,dp))))
            if benign and start<=ns<=cut:
                ref_in+=int(incoming)
                refs.append(dict(uid=uid(src,f),source_sha256=src,frame=f,timestamp=ns/NS,owner=OWNER,device=MASTER,
                                 partition=PART,protocol=proto,canonical_key=comp,component_id=canonical([OWNER,comp]),
                                 session_id=canonical([OWNER,name,comp]),capture_id=name,label=0,use="REFERENCE",
                                 activity="UNKNOWN",activity_verified=False,reference_end=cut/NS,bank_end_frame=normal_ends[name]))
            if not incoming:continue
            if benign:
                cover.append(ns)
                include=ns>cut
            else:
                in_window=e["start"]["n"]<f<e["end"]["n"]
                all_inside+=int(in_window)
                include=in_window and sip==SLAVE and sp==502 and sm==e["start"]["sm"]
                if include:
                    check(flag==0x18 and len(body)>=8 and body[2:4]==b"\0\0" and
                          int.from_bytes(body[4:6],"big")+6==len(body) and body[7]==3,"FORWARDED_MODBUS_RESPONSE")
            if include:
                resolved.append(f);query[group].append(uid(src,f))
        if e:
            check(marks==["start","end"] and len(resolved)==e["offguard"] and all_inside==e["all_inbound_TCP_between_markers"] and
                  (resolved[0],resolved[-1])==(e["first"]["n"],e["last"]["n"]), "EVENT_CENSUS:"+group)
        specs[name]=dict(group=group,stop=stop,frames=resolved,bank_end=normal_ends.get(name),
                         inbound_span_ns=[cover[0],cover[-1]] if cover else [])
    check(len(refs)==214703 and ref_in==71568 and all(len(query[g])==n for g,n in COUNTS.items()),"POPULATIONS")
    check(refs[0]["frame"]==2 and refs[-1]["frame"]==31782 and
          specs[NORMAL[-1]]["frames"][0]==31784 and specs[NORMAL[-1]]["frames"][-1]==41783,"NORMAL_BOUNDARIES")
    bank=choose(refs); saved=set(bank)
    for name in NORMAL+ATTACK:
        specs[name]["selected_reference_frames"]=[r["frame"] for r in refs if r["capture_id"]==name and r["uid"] in saved]
    allq=sum((query[g] for g in GROUPS),[])
    check(len(set(bank+allq))==len(bank)+len(allq),"UID_COLLISION")
    return dict(schema="ELEGANT_V12_PRE_SCORE_V1",target=MASTER,owner=OWNER,start_ns=start,cut_ns=cut,
                normal_logical_sha256=normal_hash.hexdigest(),members=specs,reference_uids=bank,
                reference_order=order(bank),candidate_rows=len(refs),legal_reference_components=1,
                query_orders={g:order(query[g]) for g in GROUPS},query_counts=COUNTS,all_query_order=order(allq),
                model_evaluations_at_seal=0)


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("cache",type=Path)
    args=parser.parse_args()
    sys.path.insert(0,str(HERE.parents[1]/"repo/ood"))
    seal=census(args.cache,read(HERE/"EVIDENCE.json"),read(HERE/"SOURCES.json"))
    payload=(json.dumps(seal,separators=(",",":"),allow_nan=False)+"\n").encode()
    path=HERE/"INPUT_SEAL.json"
    if path.exists():check(path.read_bytes()==payload,"PREVIOUS_INPUT_SEAL_CONFLICT")
    else:path.write_bytes(payload)
    print("Input seal",sha(payload),seal["reference_order"],seal["all_query_order"])
