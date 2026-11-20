"""Continuous normal-rotation replay with an immutable physical-frame scoring roster."""
import csv
from decimal import Decimal
import hashlib
import json
import lzma
import os
from pathlib import Path
import sqlite3
import subprocess
import zlib

import numpy as np
from seal import ATTACK, NORMAL, COUNTS, GROUPS, MASTER, OWNER, PART, NS, canonical, check, order, read, uid

FIELDS = ("frame.number frame.time_epoch frame.len frame.cap_len eth.src eth.dst ip.src ip.dst ip.proto "
          "ip.hdr_len ip.dsfield ip.len ip.flags ip.frag_offset ip.ttl tcp.srcport tcp.dstport tcp.flags "
          "tcp.window_size_value tcp.seq_raw tcp.ack_raw tcp.urgent_pointer tcp.hdr_len tcp.len "
          "udp.srcport udp.dstport udp.length").split()


def ensure_cache(pkg, cache):
    from common_ton import sha
    cache.mkdir(exist_ok=True, parents=True)
    for member, spec in read(pkg/"SOURCES.json").items():
        path = cache/member
        if path.is_file():
            check(path.stat().st_size == spec["bytes"] and sha(path) == spec["sha256"], "CACHE_IDENTITY:"+member)
            continue
        packed = pkg/"raw"/(member+".xz")
        check(sha(packed) == spec["xz_sha256"], "PACKED_SHA:"+member)
        data = lzma.decompress(packed.read_bytes())
        check(len(data) == spec["bytes"] and hashlib.sha256(data).hexdigest()==spec["sha256"], "SOURCE_SHA:"+member)
        temp=path.with_suffix(f".{os.getpid()}.tmp")
        temp.write_bytes(data);temp.replace(path)


def decoded(exe, path, limit):
    args=[str(exe),"-n","-r",str(path),"-c",str(limit),"-T","fields","-E","header=y","-E","occurrence=f"]
    for field in FIELDS: args.extend(["-e",field])
    with subprocess.Popen(args, stdout=subprocess.PIPE, text=True, encoding="utf-8") as proc:
        yield from csv.DictReader(proc.stdout,delimiter="\t")
        check(proc.wait()==0,"TSHARK_READ:"+path.name)


def replay_inputs(folder, pkg, exe, pilot, progress, tokenizer=None, cache=None):
    from continuous_input_v3 import Contexts, verify_tokenized
    import issue27ckbu_unified_tshark_causal_frontend_v1 as ethernet
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    from vendor.stream_core import Engine
    if tokenizer is not None:
        from continuous_features_v3 import tokenize
    seal=read(pkg/"INPUT_SEAL.json");pins=read(pkg/"SOURCES.json")
    cache=folder.parent/"source_cache" if cache is None else cache
    ensure_cache(pkg,cache)
    refs=seal["reference_uids"]; refset=set(refs)
    pilots=set(refs[::256]+[refs[-1]])
    for name,spec in seal["members"].items():
        for key in ("frames","selected_reference_frames"):
            positions=spec[key]
            if positions:
                for pos in positions[:2]+positions[-2:]+positions[::max(1,len(positions)//10)]:
                    pilots.add(uid(pins[name]["sha256"],pos))
    seen_refs=set(); seen={g:[] for g in GROUPS}; values={}; trace=[]
    db=sqlite3.connect(folder/"examples.sqlite")
    db.executescript("CREATE TABLE feature(uid TEXT PRIMARY KEY,shape TEXT,example BLOB); "
                     "CREATE TABLE batch(batch INTEGER,slot INTEGER,uid TEXT UNIQUE,PRIMARY KEY(batch,slot));")
    for i,name in enumerate(NORMAL+ATTACK):
        physical=pins[name]["sha256"];spec=seal["members"][name];group=spec["group"]
        normal=name in NORMAL
        logical="normal_roll" if normal else name
        logical_sha=seal["normal_logical_sha256"] if normal else physical
        if i==0 or not normal:
            ctx=Contexts(logical,[OWNER],ethernet)
            engine=Engine();offset=0
        progress("CAUSAL_REPLAY",i,6,description="按原帧顺序重放 "+name,force=True)
        qframes=set(spec["frames"]);rframes=set(spec["selected_reference_frames"])
        selected=qframes|rframes;check(len(selected)==len(qframes)+len(rframes),"OVERLAP")
        for local,row in enumerate(decoded(exe,cache/name,spec["stop"]),1):
            check(local==int(row["frame.number"]), "ORIGINAL_FRAME")
            frame=offset+local;row["frame.number"]=str(frame)
            ns=int(Decimal(row["frame.time_epoch"])*NS)
            src,dst=row["ip.src"],row["ip.dst"];sm,dm=row["eth.src"],row["eth.dst"]
            proto=int(row["ip.proto"] or 0);transport="tcp" if proto==6 else "udp"
            event=None
            if dst==MASTER and dm==OWNER and src!=MASTER and proto in (6,17):
                check(int(row["ip.frag_offset"] or "0")==0 and not int(row["ip.flags"],16)&1
                      and row["frame.len"]==row["frame.cap_len"],"INBOUND_HEADER")
                conn=(proto,src,int(row[transport+".srcport"]),dst,int(row[transport+".dstport"]))
                event=(OWNER,proto,int(row["ip.len"]),src,conn)
            engine.advance(frame,ns,logical,event)
            owner,namespace,_=ctx.append(row)
            if local not in selected:continue
            check(ctx.query_allowed and owner==OWNER and namespace[:2]==(OWNER,logical),"FROZEN_ADMISSION")
            rid=uid(physical,local);isref=local in rframes
            if isref:
                check(rid in refset and ns<=seal["cut_ns"] and normal, "REFERENCE_ID")
                seen_refs.add(rid)
            else:
                check(event and proto==6 and ns>seal["cut_ns"],"QUERY_DIRECTION_TIME")
                seen[group].append(rid)
            if pilot and rid not in pilots:continue
            comp=namespace[-1]
            meta=dict(uid=rid,source_sha256=physical,frame=local,timestamp=ns/NS,timestamp_ns=ns,
                      owner=OWNER,device=MASTER,partition=PART,protocol=proto,canonical_key=comp,
                      component_id=canonical([OWNER,comp]),capture_id=name,session_id=canonical([OWNER,name,comp]),
                      use="REFERENCE" if isref else "QUERY",label=int(not isref and not normal),group=group)
            if isref:meta.update(reference_end=seal["cut_ns"]/NS,bank_end_frame=spec["bank_end"])
            flow,numeric,provenance=ctx.states[namespace].snapshot()
            # The transform validates the continuous capture namespace and global ordinal.
            # Features are attached only to the separately verified original member UID.
            desc=dict(meta,uid=uid(logical_sha,frame),capture_id=logical,session_id=canonical(namespace),
                      frame=frame,source_sha256=logical_sha)
            if isref:desc["bank_end_frame"]=sum(seal["members"][n]["stop"] for n in NORMAL[:2])+seal["members"][NORMAL[-1]]["bank_end"]
            body=dict(flow=flow,state=numeric,provenance=provenance,source_sha256=logical_sha)
            q,info=(reference_descriptor if isref else query_descriptor)(body,desc)
            x=np.asarray(engine.features(OWNER,proto),dtype=np.float64)
            check(not info["syn_no_ack"] if not isref else True, "QUERY_BYPASS")
            check(rid not in values and np.isfinite(x).all() and x.shape==(8,),"SNAPSHOT_UID")
            values[rid]=(meta,q,x)
            if rid in pilots:trace.append([name,local,frame,rid])
            if tokenizer is not None:
                example=tokenize(tokenizer,flow)
                verify_tokenized(flow,provenance,example)
                shape=f"{proto:02d}-{max(example['dataset_burst_sizes'])+1:04d}-{len(example['dataset_burst_sizes']):03d}"
                blob=json.dumps(example,separators=(",",":"),default=lambda x:x.tolist(),allow_nan=False).encode()
                db.execute("INSERT INTO feature VALUES(?,?,?)",(rid,shape,zlib.compress(blob,1)))
        check(local==spec["stop"],"UNEXPECTED_CAPTURE_END")
        offset+=local
    check(seen_refs==refset and {g:order(v) for g,v in seen.items()}==seal["query_orders"],"PRE_SCORE_UID_JOIN")
    refids=[v for v in refs if v in values]
    queryids=[v for g in GROUPS for v in seen[g] if v in values]
    ids=refids+queryids
    check(len(ids)==len(values) and (pilot or len(queryids)==sum(COUNTS.values())),"COMPLETE_SCOPE")
    if pilot:check(set(ids)==pilots,"PILOT_SCOPE")
    with (folder/"rows.jsonl").open("w",encoding="utf8",newline="\n") as f:
        for rid in ids:f.write(json.dumps(values[rid][0],separators=(",",":"))+"\n")
    np.savez(folder/"input.npz",uid=ids,q=np.stack([values[v][1] for v in ids]),x=np.stack([values[v][2] for v in ids]))
    batches=0
    if tokenizer is not None:
        db.execute("CREATE INDEX by_shape ON feature(shape,uid)")
        for shape, in db.execute("SELECT DISTINCT shape FROM feature ORDER BY shape").fetchall():
            cursor=db.execute("SELECT uid FROM feature WHERE shape=? ORDER BY uid",(shape,))
            while chunk:=cursor.fetchmany(16):
                db.executemany("INSERT INTO batch VALUES(?,?,?)",[(batches,i,u) for i,(u,) in enumerate(chunk)])
                batches+=1
    db.commit();db.close()
    return dict(references=len(refids),queries=len(queryids),batches=batches,selected_uid_order=order(ids),
                physical_reference_order=order(refids),physical_query_order=order(queryids),
                complete_census_orders=seal["query_orders"],pilot_witnesses=trace,
                components=len({values[v][0]["component_id"] for v in refids}))
