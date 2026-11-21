"""Open existing sealed metadata and scores without rerunning any detector."""
from collections import defaultdict
from pathlib import Path
import gzip
import json
import sqlite3
import sys

import numpy as np

from history_common import HERE, TON, SCALE, EDGE_PW, SOURCE, HOSTS, sha, check, read, uid_sha

PIN = read(HERE/"INPUT_PINS.json")


def db_open(path):
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def zipped_rows(path):
    with gzip.open(path, "rt", encoding="utf-8-sig") as stream:
        return [json.loads(line) for line in stream]


def npz(path):
    with np.load(path, allow_pickle=False) as a:
        return {key:a[key] for key in a.files}


def mac(value):
    assert isinstance(value, str) and len(value.replace(":", "")) == 12
    return value.replace(":", "").lower()


def source_cal(project):
    folder=project/"runs"/SOURCE
    plan=read(check(folder/"ASSET_PLAN.json",PIN["source"]["plan"]))
    loc=read(folder/"RESOLVED_ASSETS.json")
    key,=[k for k,v in plan.items() if v["kind"]=="prepared" and v["name"]=="LEARN.jsonl.gz"]
    asset=check(Path(loc[key]),plan[key])
    ix=np.load(folder/"metadata/CAL.npy",allow_pickle=False)
    assert len(ix)==148819 and len(set(ix))==len(ix)
    lookup=set(ix)
    rows={}
    with gzip.open(asset,"rt",encoding="utf-8-sig") as f:
        for i,line in enumerate(f):
            if i in lookup:
                r=json.loads(line)
                assert r["partition"]=="LEARN" and r["fit_role"]=="CAL"
                rows[i]=r
    ordered=[rows[i] for i in ix]
    assert uid_sha(sorted(r["uid"] for r in ordered))==PIN["source"]["cal_membership"]
    normal=[r for r in ordered if r["label"]==0]
    assert len(normal)==33147 and uid_sha(r["uid"] for r in normal)==PIN["source"]["normal_cal_order"]
    selected=[r for r in normal if r["protocol"]==6]
    assert len(selected)==16430
    return selected


def context_inputs(project):
    run=project/"runs"/SOURCE
    manifest=read(check(run/"QUERY_MANIFEST.json",PIN["source"]["query_manifest"]))
    return manifest


def accepted(pool, project):
    rec=PIN["scale"]["caches"][pool]
    path=check(project/"runs"/SCALE/rec["cache"]["file"],rec["cache"])
    a=npz(path)
    ids=a["uid"]
    assert ids.dtype.kind=="U" and len(ids)==len(set(ids))==rec["rows"]
    assert uid_sha(ids)==rec["uid_order"]
    assert a["v12"].shape==(len(ids),4) and np.isfinite(a["v12"]).all()
    assert np.array_equal(a["v12"][:,:3].mean(axis=1),a["v12"][:,3])
    assert a["support"].shape==(len(ids),) and np.isfinite(a["support"]).all()
    assert ((a["support"]>=0)&(a["support"]<=1)).all() and np.array_equal(a["off"],~a["guard"])
    return {k:v for k,v in a.items() if k!="r1"}


def flat(pool,project):
    a=accepted(pool,project)
    meta_pin=PIN["flat_rows"][pool]
    rows=zipped_rows(check(project/meta_pin["path"],meta_pin))
    assert np.array_equal(a["uid"],[r["uid"] for r in rows])
    assert np.array_equal(a["frame"],[r["frame"] for r in rows])
    assert np.array_equal(a["kind"],["attack" if r["label"] else "normal" for r in rows])
    if pool=="CIC_DEV":
        a["group"]=np.asarray([r["session_id"] for r in rows])
    elif pool=="UNSW_DEV":
        assert all(r.get("stream_id") not in (None,"") for r in rows)
        group=[(r["capture_id"],r["device"],r["protocol"],r["stream_id"]) for r in rows]
        a["group"]=np.array([ "|".join(map(str,g)) for g in group])
    else:
        mask=a["kind"]=="normal"
        assert len(np.unique(a["group"][mask]))==19543 and int(mask.sum())==20000
    for r,g in zip(rows,a["guard"]):
        r["guard"]=bool(g)
    return rows,a


def ton_env(project):
    folder=project/"runs"/TON
    for key in ("SCOPED_INPUTS.json","DIAGNOSTIC_CARD.json"):
        check(folder/"package"/key,PIN["ton"]["package"][key])
    sys.path.append(str(folder/"package"))
    sources=read(folder/"package/SCOPED_INPUTS.json")["sources"]
    paths=read(check(folder/"VERIFIED_INPUTS.json",PIN["ton"]["sources"]))["inputs"]
    for role in ("normal1","normal2","password"):
        assert all(paths[role][k]==sources[role][k] for k in ("sha256","bytes"))
    specs={k:dict(pin=sources[k],path=Path(paths[k]["path"]),cooked=sources[k]) for k in ("normal1","normal2","password")}
    return folder,specs


def ton(project):
    folder,specs=ton_env(project)
    from evaluate_ton import QUERY
    db=db_open(check(Path(PIN["ton"]["arrays"]["snapshots.sqlite"]["path"]),PIN["ton"]["arrays"]["snapshots.sqlite"]))
    entries=defaultdict(list); all_ids=[]
    for i,r in enumerate(db.execute(QUERY)):
        cap,frame,ns,host,owner,proto,comp,uid,kind,conn,off,data,cross,x,q,key=r
        all_ids.append(uid)
        if host not in HOSTS:
            continue
        point=dict(uid=uid, frame=frame, timestamp_ns=ns, timestamp=ns/10**9, device=host, owner=host,
                   geometry_owner=owner, capture_id=cap, protocol=proto, component_id=comp, kind=kind,
                   group=str(conn), guard=not off, data=bool(data), q=q, x=x, index=i,
                   canonical_key=json.loads(key), expect_inbound=kind!="reference",
                   partition="EXTERNAL_ARCHIVAL_EVALUATION", label=int(kind=="attack"),
                   use="REFERENCE" if kind=="reference" else "QUERY")
        entries[host].append(point)
    db.close()
    assert uid_sha(all_ids)==PIN["ton"]["order"]
    rows=[];refs=[];parts=defaultdict(list)
    for host in HOSTS:
        cache=PIN["ton"]["arrays"][host]
        a=npz(check(Path(cache["path"]),cache))
        p=[r for r in entries[host] if r["kind"]!="reference"]
        refs.extend(r for r in entries[host] if r["kind"]=="reference" and host==HOSTS[2])
        assert np.array_equal(a["index"],[r["index"] for r in p])
        assert np.array_equal(a["uid"].astype("U64"),[r["uid"] for r in p])
        assert np.array_equal(a["off_bypass"],[not r["guard"] for r in p])
        assert np.array_equal(a["transport_data"],[r["data"] for r in p])
        n=len(p)
        # Keep original capture and target in the grouping key even when short conn IDs coincide.
        parts["group"].append(np.array([r["capture_id"]+"|"+host+"|"+r["group"] for r in p]))
        for k in ("frame","kind","uid","guard","data"):
            parts[k].append(np.asarray([r[k] for r in p]))
        parts["active"].append(np.ones(n,bool));parts["off"].append(a["off_bypass"])
        parts["post"].append(np.zeros(n,bool));parts["activity"].append(np.repeat(host,n))
        parts["support"].append(a["support"]);parts["v12"].append(a["raw"])
        parts["ccnr_alarm"].append(a["ccnr_alarm"]);parts["raw_alarm"].append(a["raw_alarm"])
        rows.extend(p)
    return rows,{k:np.concatenate(values) for k,values in parts.items()},refs,specs


def edge_pw(project):
    from hashlib import sha256
    folder=project/"runs"/EDGE_PW
    apin=PIN["edge_pw"]
    raw=check(folder/"edge/password.pcap",apin["raw"])
    sealed=read(check(folder/"EDGE_INPUTS.json",apin["inputs"]))
    assert sealed["input_sha"]==apin["raw"]["sha256"]
    db=db_open(check(folder/"edge/queries.sqlite",dict(sha256=sealed["database_sha"])))
    a=accepted("EDGE_PASSWORD",project)
    p=list(db.execute("SELECT uid,frame,stream,ns,post,q,x,sport FROM metadata ORDER BY frame"))
    db.close()
    assert len(p)==143600 and sum(r[4] for r in p)==23608 and len({r[2] for r in p})==23608
    for key,col in (("uid",0),("frame",1),("group",2),("post",4)):
        assert np.array_equal(a[key],[r[col] for r in p]), key
    owner=apin["owner"]
    rows=[]
    for uid,f,_,ns,_,q,x,sport in p:
        assert uid==sha256(json.dumps([apin["raw"]["sha256"],f,owner],separators=(",",":")).encode()).hexdigest()
        flags=np.frombuffer(q,"<f4")
        rows.append(dict(uid=uid,frame=f,timestamp_ns=ns,timestamp=ns/10**9,capture_id="EDGE_PASSWORD",
                         owner=owner,protocol=6,sport=sport,q=q,x=x,guard=bool(flags[2]==1 and flags[5]==0),
                         expect_inbound=True))
    assert np.array_equal(a["guard"],[r["guard"] for r in rows])
    return rows,a,dict(path=raw,pin=apin["raw"])


def geometry_setup(project):
    sys.path.append(str(project/"runs"/EDGE_PW/"package"))
    sys.path.append(str(project/"runs"/TON/"package"))
    from frozen_env import setup,store
    runtime,fr,cfg,geom=setup(project)
    return store(project,fr),cfg,geom
