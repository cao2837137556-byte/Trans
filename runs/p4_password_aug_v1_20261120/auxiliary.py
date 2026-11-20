"""Materialize frozen-encoder auxiliary inputs on a compute node."""
from collections import Counter, defaultdict
import ipaddress
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import zlib

import numpy as np

HERE = Path(__file__).resolve().parent


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4*1024**2), b""):
            h.update(block)
    return h.hexdigest()


def windows_history(project, targets):
    """Rebuild FIT-only device windows with Win10 omitted, preserving the actual frame clock."""
    from capture import frames,decode
    from common_ton import HERE as accepted_package
    sys.path.insert(0,str(project/"runs/device_context_training_v2_20261105"))
    from stream_core import Engine
    import struct
    inputs=json.loads((accepted_package/"SCOPED_INPUTS.json").read_bytes())["sources"]
    actual=json.loads((accepted_package.parent/"VERIFIED_INPUTS.json").read_bytes())["inputs"]
    held=ipaddress.IPv4Address("192.168.1.195")
    changed={}
    original={}
    checked=0
    train={ip for anchors in targets.values() for ip,_ in anchors.values()}
    for role,anchors in targets.items():
        pin=inputs[role]
        path=Path(actual[role]["path"])
        assert path.stat().st_size==pin["bytes"] and sha(path)==pin["sha256"]
        full=Engine()
        isolated=Engine()
        for frame,ts,_,packet in frames(path,pin):
            h=decode(packet)
            event=None
            if h and h.dst in train and h.src!=h.dst:
                key=struct.pack("!BIIHH",h.proto,h.src,h.dst,h.sport,h.dport)
                event=(h.dst,h.proto,h.iplen,h.src,key)
            full.advance(frame,ts,role,event)
            isolated.advance(frame,ts,role,None if event and h.src==int(held) else event)
            if frame in anchors:
                host,proto=anchors[frame]
                key=(role,frame)
                before=np.asarray(full.features(host,proto),dtype="<f8").tobytes()
                after=np.asarray(isolated.features(host,proto),dtype="<f8").tobytes()
                original[key]=before
                if before!=after:
                    changed[key]=after
                checked+=1
    assert checked==sum(map(len,targets.values()))
    return original,changed


def ton_rows(project, pilot, freeze, geometry, folder):
    from evaluate_ton import QUERY
    pins = json.loads((HERE / "TON_PINS.json").read_bytes())
    paths = {}
    for name, pin in pins.items():
        if name not in ("snapshots.sqlite","ORDERED_E3.npy") and not (pilot and name=="192.168.1.152"):
            continue
        p = project/"runs/p4_ton_password_frozen_v12_20261118/formal"/pin["file"]
        if p.stat().st_size != pin["bytes"] or sha(p) != pin["sha256"]:
            raise ValueError(f"ToN asset changed: {name}")
        paths[name] = p
    db = sqlite3.connect(paths["snapshots.sqlite"].resolve().as_uri()+"?mode=ro&immutable=1", uri=True)
    e3 = np.load(paths["ORDERED_E3.npy"], mmap_mode="r")
    used = set()
    rows = []
    order = hashlib.sha256()
    pilot_refs = []
    anchors=defaultdict(dict)
    candidates=defaultdict(set)
    for role,frame,host,proto in db.execute(
            "SELECT role,frame,host,proto FROM point WHERE selected=1 AND off=1 AND data=1 "
            "AND kind IN ('normal','attack') AND host IN ('192.168.1.152','192.168.1.190')"):
        anchors[role][frame]=(int(ipaddress.IPv4Address(host)),proto)
    original,isolated=windows_history(project,anchors)
    corrected=Counter()
    pilot_original={}
    for i, record in enumerate(db.execute(QUERY)):
        role, frame, ts, host, owner, proto, comp, uid, kind, conn, off, data, cross, ctx, q, key = record
        order.update((uid + "\n").encode())
        if pilot and kind == "reference" and host == "192.168.1.152" and proto == 6:
            pilot_refs.append((i,comp,q,ctx,ts))
        if host not in ("192.168.1.152", "192.168.1.190") or kind not in ("normal", "attack") or not off or not data:
            continue
        candidates[host,int(kind=="attack")].add((role,conn))
        assert ctx==original[role,frame], "cached context differs from full traffic replay"
        if any(str(ip) in ("192.168.1.195",str(int(ipaddress.IPv4Address("192.168.1.195")))) for ip, _ in json.loads(key)[1:]):
            continue
        connection = (role, host, kind, conn)
        if connection in used:
            continue
        used.add(connection)
        if pilot: pilot_original[uid]=ctx
        if (role,frame) in isolated:
            ctx=isolated[role,frame]
            corrected[host,int(kind=="attack")]+=1
        rows.append((host, int(kind == "attack"), uid, i, q, ctx))
    db.close()
    observed = Counter((r[0],r[1]) for r in rows)
    if (order.hexdigest() != "186a11e2ebf0500228dd9198565140e7b09a1eed61b63e9bf6302297deaec2ca"
            or i + 1 != len(e3) or len(used) != len(rows)):
        raise ValueError("ToN frozen row binding")
    expected = {("192.168.1.152",0):30,("192.168.1.152",1):7775,
                ("192.168.1.190",0):16,("192.168.1.190",1):32145}
    assert {key:len(v) for key,v in candidates.items()}==expected
    if not all(0 < observed[k] <= n for k,n in expected.items()) or set(observed) != set(expected):
        raise ValueError("ToN auxiliary group coverage")
    from compute import write
    write(folder/"TON_SELECTION.json",dict(held_out="192.168.1.195",verified_cached_contexts=len(original),
          contexts_changed_after_Windows10_removal=len(isolated),
          groups=[dict(host=h,label=y,candidates=n,included=observed[h,y],excluded=n-observed[h,y],
                       selected_contexts_changed=corrected[h,y])
                  for (h,y),n in expected.items()]))
    if pilot:
        rows = [item for key in expected for item in [r for r in rows if r[:2] == key][:3]]
        selected=[r for r in rows if r[0]=="192.168.1.152"]
        np.savez(folder/"pilot_geometry.npz",ref_index=[r[0] for r in pilot_refs],
                 comp=[r[1] for r in pilot_refs],
                 ref_q=np.stack([np.frombuffer(r[2],"<f4") for r in pilot_refs]),
                 ref_x=np.stack([np.frombuffer(r[3],"<f8") for r in pilot_refs]),
                 query_index=[r[3] for r in selected],uid=[r[2] for r in selected],
                 q=np.stack([np.frombuffer(r[4],"<f4") for r in selected]),
                 x=np.stack([np.frombuffer(pilot_original[r[2]],"<f8") for r in selected]))
        from compute import run_child
        run_child([sys.executable,"-B",str(HERE/"auxiliary.py"),str(project),str(folder)],folder,"ton-geometry")
    for group, label, uid, i, q, ctx in rows:
        yield group,label,uid,e3[i],np.frombuffer(q,"<f4"),np.frombuffer(ctx,"<f8")


def gotham_rows(project, freeze, pilot):
    from continuous_features_v3 import tokenize
    from continuous_input_v3 import verify_tokenized
    from representations import encoder, forward_batch
    runtime, _ = encoder(project, freeze)
    db = sqlite3.connect(":memory:")
    db.executescript("CREATE TABLE feature(uid TEXT PRIMARY KEY,shape TEXT,example BLOB);"
                     "CREATE TABLE batch(batch INTEGER,slot INTEGER,uid TEXT UNIQUE);")
    info = {}
    for entry in json.loads((HERE/"GOTHAM_SNAPSHOTS.json").read_bytes()):
        path = HERE/"snapshots"/entry["file"]
        if sha(path) != entry["sha256"]:
            raise ValueError("Gotham snapshot SHA")
        with gzip.open(path, "rt", encoding="utf8") as f:
            for idx, line in enumerate(f):
                if pilot and idx >= 3:
                    break
                rec = json.loads(line)
                uid = rec["uid"]
                if uid in info:
                    raise ValueError("duplicate Gotham training UID")
                flow = rec["flow"]
                example = tokenize(runtime[3], flow)
                verify_tokenized(flow, rec["provenance"], example)
                shape = f"06-{max(example['dataset_burst_sizes'])+1:04d}-{len(example['dataset_burst_sizes']):02d}"
                blob = json.dumps(example,separators=(",",":"),default=lambda a:a.tolist()).encode()
                db.execute("INSERT INTO feature VALUES(?,?,?)",(uid,shape,zlib.compress(blob,1)))
                info[uid] = (rec["label"],rec["q"],rec["context"])
    batch = 0
    for (shape,) in list(db.execute("SELECT DISTINCT shape FROM feature ORDER BY shape")):
        rows = db.execute("SELECT uid FROM feature WHERE shape=? ORDER BY uid",(shape,))
        while chunk := rows.fetchmany(16):
            db.executemany("INSERT INTO batch VALUES(?,?,?)",[(batch,j,r[0]) for j,r in enumerate(chunk)])
            ids, z, _ = forward_batch(db,batch,runtime)
            for uid, embedding in zip(ids,z):
                label,q,ctx = info[uid]
                yield "gotham",label,uid,embedding,q,ctx
            batch += 1
    db.close()


def prepare(project, out, pilot):
    parent = project/"runs/p4_ton_password_frozen_v12_20261118/package"
    sys.path.insert(0,str(parent))
    from frozen_env import setup
    _, freeze, _, geometry = setup(project)
    records = list(gotham_rows(project,freeze,pilot))
    records.extend(ton_rows(project,pilot,freeze,geometry,out))
    counts = Counter((g,int(y)) for g,y,*_ in records)
    group,label,uid,z,q,x = zip(*records)
    if len(set(uid)) != len(uid) or set(group) != {"gotham","192.168.1.152","192.168.1.190"}:
        raise ValueError("auxiliary split")
    if not pilot and (counts["gotham",1], counts["gotham",0]) != (1519,48):
        raise ValueError("Gotham coverage")
    np.savez(out/"auxiliary.npz",group=group,label=label,uid=uid,z=np.array(z,dtype=np.float32),
             q=np.array(q,dtype=np.float32),context=np.array(x,dtype=np.float64))
    print({str(k):v for k,v in counts.items()},flush=True)


def pilot_geometry(project,folder):
    sys.path.insert(0,str(project/"runs/p4_ton_password_frozen_v12_20261118/package"))
    from frozen_env import setup,store
    _,freeze,_,geometry=setup(project)
    from reference_inputs import normalized_context
    from replay_geometry import radii
    from vendor import constrained_onboarding_core_v3 as core,geometry_frozen
    pins=json.loads((HERE/"TON_PINS.json").read_bytes())
    st=store(project,freeze)
    with np.load(st.get("e3_normalizer")) as a,np.load(st.get("context_normalizer")) as b:
        zn=(a["mean"],a["scale"]);cn=(b["mean"],b["scale"])
    ep=Path(pins["ORDERED_E3.npy"]["path"]);sp=Path(pins["192.168.1.152"]["path"])
    assert sha(ep)==pins["ORDERED_E3.npy"]["sha256"] and sha(sp)==pins["192.168.1.152"]["sha256"]
    e3=np.load(ep,mmap_mode="r")
    with np.load(sp,allow_pickle=False) as a:
        support=dict(zip(a["uid"].astype("U64"),a["support"]))
    with np.load(folder/"pilot_geometry.npz",allow_pickle=False) as a:
        rz=core._unit(e3[a["ref_index"]],zn)
        rq=a["ref_q"];rc=normalized_context(a["ref_x"],cn)
        rr,rhoc=radii(geometry,6)
        assert len(a["uid"]) and len(set(a["comp"]))>=2
        for uid,index,q,x in zip(a["uid"],a["query_index"],a["q"],a["x"]):
            dz=np.clip(1-core._unit(e3[index:index+1],zn)@rz.T,0,2)[0]
            dq=geometry_frozen.rms(q[None,:],rq)[0]
            dc=geometry_frozen.rms(normalized_context(x[None,:],cn),rc)[0]
            dist=np.maximum.reduce((core._ratio(dz,rr[0]),core._ratio(dq,rr[1]),core._ratio(dc,rhoc)))
            by_comp={}
            for comp,value in zip(a["comp"],dist):
                by_comp[comp]=min(by_comp.get(comp,np.inf),value)
            assert abs(support[uid]-np.clip(1-sorted(by_comp.values())[1],0,1))<2e-10


if __name__=="__main__":
    pilot_geometry(*map(Path,sys.argv[1:3]))
