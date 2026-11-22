"""Connect the original v12 banks, query metadata and cached scores to physical frames."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import sys

import numpy as np

from history_common import HERE, TON, EDGE_PW, SOURCE, HOSTS, check, read, sha, uid_sha, progress
from inputs_history import flat, ton, edge_pw, npz, context_inputs, mac, zipped_rows
from paired_history import verify_base
from roles import NAMES, scan, role_columns

CACHE=read(HERE/"ROLE_PINS.json")
UNIFIED=CACHE["unified"]
HISTORY=CACHE["history_remote"]


def frozen_geometry(project, runtime=None):
    # The two accepted packages both contain common_ton.py. Resolve the
    # frozen environment before exposing the Edge-only feature reader.
    parent=project/"runs"/TON/"package"
    sys.path.insert(0,str(parent))
    from frozen_env import setup,store
    import common_ton
    assert Path(common_ton.__file__).resolve().parent==parent.resolve(), "FROZEN_COMMON_TON_SOURCE"
    _,freeze,cfg,geom=setup(project,local_runtime=runtime)
    sys.path.append(str(project/"runs"/EDGE_PW/"package"))
    return store(project,freeze),cfg,geom


def role_receipt(project,pool):
    p=CACHE["history_arrays"][pool]
    path=check(project/"runs"/HISTORY/p["file"],p)
    a=npz(path)
    assert len(a["uid"])==p["rows"] and uid_sha(a["uid"])==p["uid_order"]
    return a


def bind_history(a,b):
    for k in ("uid","v12","support","guard","frame","kind","active","group","off","data","post","activity"):
        assert np.array_equal(a[k],b[k]),("HISTORY_PARENT_BIND",k)


def source_paths(project):
    folder=project/"runs"/SOURCE
    manifest=context_inputs(project)
    catalog=read(check(folder/"RAW_CATALOG.json",CACHE["source_catalog"]))
    plan=read(check(folder/"ASSET_PLAN.json",CACHE["source_plan"]))
    resolved=read(folder/"RESOLVED_ASSETS.json")
    result={x["sha256"]:dict(path=Path(resolved[k]),pin=x) for k,x in plan.items() if x["kind"]=="raw"}
    for entry in catalog:
        digest=entry["sha256"]
        assert digest in result
        if entry["capture_id"] not in manifest:
            continue
        m=manifest[entry["capture_id"]]
        assert digest==m["source_sha256"] and entry["bytes"]==m["raw_bytes"]
    for _,v in UNIFIED["sources"].items():
        if isinstance(v,dict) and "raw" in v:
            raw=v["raw"];digest=raw["sha256"]
            if digest not in result or not result[digest]["path"].is_file():
                result[digest]=dict(path=Path(raw["path"]),pin=raw)
    return result


def catalog_edge(project):
    remote=read(project/"runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json")
    inputs=CACHE["edge"]["raw_inputs"]
    result={}
    for group,pin in inputs.items():
        options=[Path(remote[group]),project/pin["path"]]
        chosen=next((p for p in options if p.is_file() and p.stat().st_size==pin["bytes"]),options[0])
        result[pin["sha256"]]=dict(path=chosen,pin=pin,
                 edges=CACHE["edge"]["normal_segments"] if group=="NORMAL" else [])
    return result


def build_bank(project, s, cfg, pool):
    from reference_assets import bank as original_bank
    from paired_replay import effective_history, ref_bank
    from reference_inputs import normalized_context
    geom_norm=s.get("e3_normalizer")
    ctx_norm=s.get("context_normalizer")
    with np.load(geom_norm,allow_pickle=False) as a:
        zn=a["mean"],a["scale"]
    with np.load(ctx_norm,allow_pickle=False) as a:
        xn=a["mean"],a["scale"]
    rows,z,q,x=original_bank(s,cfg,pool,lambda *a:None)
    base=ref_bank(rows,z,q,zn)
    if pool=="EDGE":
        assert len(rows)==4124
        return rows,base,normalized_context(x,xn),xn
    choices=[project/"runs"/p/"candidate" for p in CACHE["unified_paths"]]
    candidate=next((p for p in choices if (p/"CANDIDATE.json").is_file() and
                    sha(p/"CANDIDATE.json")==UNIFIED["receipt"]["sha256"]),None)
    if candidate is None:
        raise FileNotFoundError("Accepted unified candidate manifest unavailable")
    extra=zipped_rows(check(candidate/(pool+"_HISTORY.jsonl.gz"),UNIFIED["sources"][pool]["rows"]))
    path=check(candidate/pool/"REFERENCES.npz",UNIFIED["features"][pool]["feature"]["arrays"])
    dense=cfg["reference"][pool]["commission_rows"]
    with np.load(path,allow_pickle=False) as temp:
        assert temp["uid"].tolist()==[r["uid"] for r in extra]
        rr=rows[:dense]+effective_history(extra,cfg["windows"][pool])
        ref=ref_bank(rr,np.concatenate((z[:dense],temp["e3"])),np.concatenate((q[:dense],temp["q14"])),zn)
        ctx=normalized_context(np.concatenate((x[:dense],temp["context"])),xn)
    assert len(rr)=={"CIC_DEV":9538,"UNSW_DEV":90658}[pool]
    assert ref.ends==base.ends
    for key,frame in base.frame_ends.items():
        assert ref.frame_ends.setdefault(key,frame)==frame
    return rr,ref,ctx,xn


def struct_ab(project,store,cfg,pool):
    rows,a=flat(pool,project)
    refs,bank,rc,xn=build_bank(project,store,cfg,pool)
    inputs=source_paths(project)
    before=role_receipt(project,pool)
    bind_history(a,before)
    return dict(rows=rows, a=before, refs=refs, bank=bank, rc=rc, xn=xn,
                inputs=inputs, feature_kind=pool)


def struct_ton(project,store):
    from paired_replay import ref_bank
    from reference_inputs import normalized_context
    rows,a,refs,specs=ton(project)
    before=role_receipt(project,"TON")
    bind_history(a,before)
    for r in refs:
        win=CACHE["ton_windows"][r["device"]]
        r.update(reference_end=win["window"]["reference_end"],bank_end_frame=win["window"]["frame_end"])
    for host,win in CACHE["ton_windows"].items():
        rr=[r["uid"] for r in refs if r["device"]==host]
        assert uid_sha(sorted(rr))==win["order"] and len(rr)==win["selected"]
    ze=CACHE["ton_encoding"]
    z=np.load(check(Path(ze["path"]),ze),allow_pickle=False,mmap_mode="r")
    with np.load(store.get("e3_normalizer"),allow_pickle=False) as v:
        zn=v["mean"],v["scale"]
    with np.load(store.get("context_normalizer"),allow_pickle=False) as v:
        xn=v["mean"],v["scale"]
    rq,rx=from_bytes(refs)
    geom_refs=[dict(r,owner=r["geometry_owner"]) for r in refs]
    geom_rows=[dict(r,owner=r["geometry_owner"]) for r in rows]
    bank=ref_bank(geom_refs,z[[r["index"] for r in refs]],rq,zn)
    return dict(rows=geom_rows,a=before,refs=geom_refs,bank=bank,rc=normalized_context(rx,xn),xn=xn,
                z_all=z,inputs=specs,feature_kind="TON")


def struct_edge(project,store,cfg,pool):
    refs,bank,rc,xn=build_bank(project,store,cfg,"EDGE")
    if pool=="EDGE":
        rows,a=flat("EDGE",project)
        specs=catalog_edge(project)
    else:
        rows,a,raw=edge_pw(project)
        specs=catalog_edge(project)
        psha=raw["pin"]["sha256"]
        specs[psha]=raw
        origin=refs[0]
        source=CACHE["edge_pw"]["source_ip"];target=CACHE["edge_pw"]["target_ip"]
        from common_ton import digest
        rows=[dict(r,owner=origin["owner"],device=origin["device"],partition=origin["partition"],
                   label=1,use="QUERY",capture_id="edge-password-v5",source_sha256=psha,
                   component_id=digest([origin["owner"],[6,*sorted(((source,r["sport"]),(target,80)))]]))
              for r in rows]
    before=role_receipt(project,pool)
    bind_history(a,before)
    return dict(rows=rows,a=before,refs=refs,bank=bank,rc=rc,xn=xn,inputs=specs,feature_kind=pool)


def structure(project,pool,contract):
    store,cfg,geom=frozen_geometry(project)
    for original_pool,digest in CACHE["context_uid_hash"].items():
        store.specs[original_pool+":query_context_uids"]["sha256"]=digest
    assert cfg["method"]["cuts"]==contract["cuts"] and cfg["method"]["scales"]==contract["scales"]
    if pool in ("CIC_DEV","UNSW_DEV"):
        data=struct_ab(project,store,cfg,pool)
    elif pool=="TON":
        data=struct_ton(project,store)
    else:
        data=struct_edge(project,store,cfg,pool)
    data.update(store=store,geom=geom)
    rows,a=data["rows"],data["a"]
    assert np.array_equal(a["uid"],[r["uid"] for r in rows])
    assert np.array_equal(a["proto"],[r["protocol"] for r in rows])
    return data


def physical_anchor(row,roster,pool,specs):
    c=dict(row,roster=roster)
    if pool=="TON":
        cap=row["capture_id"]
        c["owner"]=row["device"]
        return cap,c
    cap=row.get("origin_raw_sha256",row.get("source_sha256"))
    if "origin_packet_ordinal" in row:
        assert row.get("origin_raw_sha256")
        c["frame"]=row["origin_packet_ordinal"]
        # The historical catalogue stores microsecond source timestamps.
        if "timestamp_us" in row:
            c["timestamp_ns"]=row["timestamp_us"]*1000
    c["owner"]=mac(row["owner"])
    return cap,c


def extract(project,out,phase,pool,data):
    by=defaultdict(list)
    for name,rows in (("query",data["rows"]),("reference",data["refs"])):
        for r in rows:
            cap,p=physical_anchor(r,name,pool,data["inputs"])
            assert cap in data["inputs"], ("REGISTERED_PHYSICAL_SOURCE",cap,r["uid"])
            by[cap].append(p)
    assigned={};proof={}
    for j,(cap,targets) in enumerate(by.items(),1):
        progress(out,phase,"按原始帧回放初始 SYN、角色与服务端口",capture=str(cap)[:16],done=j-1,total=len(by))
        evidence,cert=scan(data["inputs"][cap],targets,lambda done,total:None,audit_controls=j<=8)
        assert len(evidence)==len(targets) and not (assigned.keys() & evidence.keys())
        assigned.update(evidence);proof[cap]=cert
    qroles=role_columns(assigned,data["rows"],"query")
    rroles=role_columns(assigned,data["refs"],"reference")
    for roles,rows in ((qroles,data["rows"]),(rroles,data["refs"])):
        assert np.array_equal(roles[:,0]==3,[r["protocol"]==17 for r in rows])
    return qroles,rroles,proof


def from_bytes(rows):
    q=np.stack([np.frombuffer(r["q"],"<f4") for r in rows])
    x=np.stack([np.frombuffer(r["x"],"<f8") for r in rows])
    return q,x


def materialize(project,data,selection):
    pool=data["feature_kind"]
    rows=data["rows"]
    s=data["store"]
    sel=np.asarray(selection,dtype=np.int64)
    wanted=[rows[i] for i in sel]
    if pool=="TON":
        q,x=from_bytes(wanted)
        z=data["z_all"][[r["index"] for r in wanted]]
    elif pool=="EDGE_PASSWORD":
        q,x=from_bytes(wanted)
        lookup={r["uid"]:i for i,r in enumerate(wanted)}
        z=np.empty((len(wanted),768),np.float32)
        done=np.zeros(len(wanted),bool)
        for i,pin in CACHE["edge_shards"].items():
            folder=project/"runs"/EDGE_PW/"edge"
            with np.load(check(folder/f"e3_{i}.npz",pin),allow_pickle=False) as a:
                u=a["uid"].astype("U64")
                assert uid_sha(u)==pin["uid_order"]
                pairs=[(j,lookup[x]) for j,x in enumerate(u) if x in lookup]
                if pairs:
                    orig,new=np.asarray(pairs).T
                    assert not done[new].any() and len(set(new))==len(new)
                    z[new]=a["z"][orig];done[new]=True
        assert done.all()
    else:
        with np.load(s.get(pool+":query_array"),allow_pickle=False) as a:
            assert np.array_equal(a["uid"].astype("U64"),[r["uid"] for r in rows])
            all_q=a["q"]
        if pool=="EDGE":
            from original_v12_inputs import edge_features
            zz,xx=edge_features(s,rows,[r["uid"] for r in rows],all_q)
            z,x=zz[sel],xx[sel]
        else:
            prefix=pool+":query_"
            with np.load(s.get(prefix+"context_uids"),allow_pickle=False) as a:
                assert np.array_equal(a["uid"].astype("U64"),[r["uid"] for r in rows])
            z=np.load(s.get(prefix+"e3"),mmap_mode="r")[sel,:768]
            x=np.load(s.get(prefix+"context"),mmap_mode="r")[sel]
            assert np.array_equal(all_q,np.load(s.get(prefix+"q"),mmap_mode="r"))
        q=all_q[sel]
    from reference_inputs import normalized_context
    assert z.shape==(len(wanted),768) and q.shape==(len(wanted),14) and x.shape==(len(wanted),8)
    return wanted,z,q,normalized_context(x,data["xn"])
