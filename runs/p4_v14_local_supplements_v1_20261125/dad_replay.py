"""Replay all 544 original DAD positives using the sealed Monday TCP bank."""
import csv
import hashlib
import json
from pathlib import Path
import sys
import tarfile
import types

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_dad_normal_h60_local_v1_20261125"))
from normal_frames import DAD, FROZEN, OWNER, OWNER_MAC, PREP, bind_sources, load_reader, pin, read
from history_stream import History, decode, records
from replay import ASSETS, HEADS, FeatureCache, geometry_check
from frozen_score import adjusted, calibration, digest_order, e3_batch, inputs790, models, scores, sealed_runtime
from bank import match
from audit import save

ATTACK=("wed","thu","fri","sat")


def read_normal(path):
    files={}
    for x in (path/"SHA256SUMS").read_text("ascii").splitlines():
        sha,n=x.split("  ",1)
        assert pin(path/n)["sha256"]==sha
        files[n]=sha
    status=read(path/"RUN_STATUS.json")
    assert status["stage"]=="ACCEPTED" and status["manifest"]==pin(path/"SHA256SUMS")
    assert status["receipt"]==pin(path/"ACCEPTANCE.json")
    assert read(path/"ACCEPTANCE.json")["status"]=="PASS"
    return len(files)


def load_causal_audit():
    load_reader()
    with tarfile.open(DAD/".private/package.tar.gz","r|gz") as arc:
        for item in arc:
            if item.name=="dad_audit.py":
                payload=arc.extractfile(item).read()
                break
        else:
            raise FileNotFoundError("pinned DAD causal audit")
    assert hashlib.sha256(payload).hexdigest()==read(DAD/"PACKAGE_MANIFEST.json")["files"]["dad_audit.py"]
    name="dad_v14_pinned_audit"
    obj=types.ModuleType(name)
    obj.__file__=str(PREP/"dad_audit.py")
    sys.modules[name]=obj
    parents=sys.path.copy()
    try:
        exec(compile(payload,obj.__file__,"exec"),obj.__dict__)
    finally:
        sys.path[:]=parents
    return obj


def history_for(cache,day):
    p,=cache.glob(f"*_{day}.pcap")
    h=History()
    data={}
    for frame,ns,raw in records(p):
        h.advance(ns)
        pkt=decode(raw,False)
        if pkt is None or pkt.proto!=6 or pkt.macs[0]==pkt.macs[1] or OWNER not in pkt.macs:
            continue
        incoming=pkt.macs[1]==OWNER
        h.observe(OWNER,pkt,incoming)
        oriented=pkt.endpoints if incoming else pkt.endpoints[::-1]
        v=h.handshakes[h.group(OWNER,oriented)]
        _,active_h,role=h.value(OWNER,pkt,incoming)
        if incoming:
            assert v==active_h
        data[frame]=(h.clock,int(v),bool(pkt.syn),oriented[1][1],int(role))
    return data


def matrix(order,meta,features):
    x=[features[u] for u in order]
    iv=[meta[u] for u in order]
    return dict(uid=np.array(order),z=np.stack([z[0] for z in x]),q=np.stack([z[1] for z in x]),
                physical=np.stack([z[2] for z in x]),
                **{key:np.array([r[key] for r in iv]) for key in ("day","clock","frame","component","h","guard","port","role")})


def report(query,raw,cc,ms,support,cuts):
    flags=(raw>cuts,cc>cuts,ms>cuts)
    assert (flags[1]<=flags[2]).all() and (flags[2]<=flags[0]).all()
    with (DAD/"received/DAILY_METRICS.csv").open(encoding="utf-8-sig") as f:
        old={(x["group"],x["head"]):x for x in csv.DictReader(f)}
    out=[]
    for day in (*ATTACK,"attack"):
        mask=np.ones(len(raw),dtype=bool) if day=="attack" else query["day"]==day
        for j,head in enumerate(HEADS):
            a,b,c=(x[mask,j] for x in flags)
            n,ra,co,mu=len(a),int(a.sum()),int(b.sum()),int(c.sum())
            previous=old[day,head]
            assert (n,ra,co,int((support[0,mask]>0).sum()))==tuple(
                int(previous[k]) for k in ("N","raw_TP","ccnr_TP","positive_support"))
            out.append(dict(day=day,head=head,unit="query",denominator=n,raw_detected=ra,seconds_ccnr_detected=co,
                 multiscale_detected=mu,raw_tpr=ra/n,seconds_ccnr_tpr=co/n,multiscale_tpr=mu/n,
                 preserved_raw_fraction=mu/ra if ra else "",recovered_vs_seconds=int((~b&c).sum()),
                 lost_vs_seconds=int((b&~c).sum())))
    return out


def main(normal,raw_out,small):
    assert (normal/"features").is_dir()
    files_checked=read_normal(normal)
    cache,sources,truth,ref_order=bind_sources()
    for name,expected in read(PREP/"INPUTS.json")["files"].items():
        assert pin(cache/name)=={k:expected[k] for k in ("sha256","bytes")}
    for receipt in ("DAILY_METRICS.csv","DATA_BINDING.json","FORMAL.json","ACCEPTANCE.json"):
        expected=read(DAD/"received/RETURN.json")["files"][receipt]
        assert pin(DAD/"received"/receipt)["sha256"]==expected["sha256"]
    binding=read(DAD/"received/DATA_BINDING.json")
    assert read(DAD/"received/ACCEPTANCE.json")["status"]=="PASS"
    ref_set=set(ref_order)
    h={day:history_for(cache,day) for day in ("mon",*ATTACK)}
    raw_out.mkdir(parents=True,exist_ok=True)
    small.mkdir(parents=True,exist_ok=True)
    with sealed_runtime() as (cfg,weights):
        import torch
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        prior=FeatureCache(normal,weights,pilot=False)
        assert ref_set<=prior.values.keys()
        from constrained_onboarding_reference_v2 import query_descriptor, reference_descriptor
        from continuous_input_v3 import digest
        audit=load_causal_audit()
        rows={}
        info={}
        pending=[]
        seen={day:[] for day in ATTACK}
        def collect(day,frame,ns,ctx,engine,comp,event,start,cutoff,clock,flag_label,source):
            if not ctx.query_allowed or comp is None or comp[0]!=6:
                return
            uid=digest([source,frame,OWNER_MAC])
            reference=day=="mon" and uid in ref_set
            if not reference and not (day in ATTACK and event and flag_label==1):
                return
            time,hand,guard,port,role=h[day][frame]
            assert time==clock and uid not in rows
            space=(OWNER_MAC,day,comp)
            cc=digest([OWNER_MAC,comp])
            row=dict(uid=uid,source_sha256=source,frame=frame,timestamp=ns/audit.NS,capture_id=day,
                     partition="EXTERNAL_ARCHIVAL_EVALUATION",owner=OWNER_MAC,device=audit.BROKER,
                     protocol=6,canonical_key=comp,component_id=cc,session_id=digest(space),
                     use="REFERENCE" if reference else "QUERY",label=0 if reference else 1)
            if reference:
                row.update(reference_end=cutoff/audit.NS,bank_end_frame=1304)
            flow,numeric,prov=ctx.states[space].snapshot()
            source_body=dict(flow=flow,state=numeric,provenance=prov,source_sha256=source)
            q,f=(reference_descriptor if reference else query_descriptor)(source_body,row)
            x=np.asarray(engine.features(OWNER,6),dtype=np.float64)
            assert bool(f["syn_no_ack"])==guard
            info[uid]=dict(day=day,clock=clock,frame=frame,component=cc,h=hand,guard=guard,port=port,role=role)
            rows[uid]=row
            if reference:
                _,oq,ox=prior.values[uid]
                assert np.array_equal(q,oq) and np.array_equal(x,ox)
            else:
                seen[day].append(uid)
                pending.append((uid,frame,flow,prov,q,x))

        observed=audit.audit(cache,"C:/Program Files/Wireshark/tshark.exe",observer=collect)
        assert hashlib.sha256((json.dumps(observed,indent=2)+"\n").encode()).hexdigest()==pin(PREP/"AUDIT.json")["sha256"]
        for day,n in zip(ATTACK,(104,56,192,192)):
            previous=binding["query_orders"][day+"_positive"]
            assert previous==dict(rows=n,sha256=digest_order(seen[day])) and len(seen[day])==n
        order=[u for day in ATTACK for u in seen[day]]
        assert [r[0] for r in pending]==order and len(order)==544
        ref=matrix(ref_order,info,prior.values)
        assert len(set(ref["component"]))==16
        za,encoder,batches=e3_batch(pending,weights)
        query=matrix(order,info,{r[0]:(z,r[4],r[5]) for r,z in zip(pending,za,strict=True)})
        assert not query["guard"].any()
        source=cfg["method"]
        cuts=np.asarray(source["cuts"])
        assert cuts.tolist()==read(DAD/"received/FORMAL.json")["cic_witness"]["source_cuts"]
        assert source["p"]==4 and source["lambda_value"]==.25
        norm=calibration(weights)
        raw=scores(models(ASSETS),inputs790(query["z"],query["q"],query["physical"],norm))
        support,legal,compatible=match(query,ref,cfg,norm)
        assert (legal[0]==16).all() and (legal[2]==16).all()
        base=adjusted(raw,support[0],query["guard"],source)
        ms=adjusted(raw,support[2],query["guard"],source)
        idx=np.unique(np.r_[np.linspace(0,len(order)-1,48,dtype=int),np.flatnonzero((raw>cuts).any(1))])
        check=geometry_check(query,ref,types.SimpleNamespace(rows=rows,pins=weights),idx,support,cfg)
        metrics=report(query,raw,base,ms,support,cuts)
    result=small/"DAD_ATTACK_MS.csv"
    with result.open("w",encoding="utf8",newline="\n") as f:
        writer=csv.DictWriter(f,fieldnames=list(metrics[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(metrics)
    np.savez_compressed(raw_out/"ATTACK_DECISIONS.npz",uid=query["uid"],frame=query["frame"],day=query["day"],
                        h=query["h"],raw=raw,seconds_ccnr=base,multiscale_ccnr=ms,cuts=cuts,
                        support=support[[0,2]],compatible_components=compatible[[0,2]])
    save(small/"DAD_REPLAY.json",dict(status="PASS",raw_sources=read(PREP/"INPUTS.json")["files"],
         normal_cache_manifest=pin(normal/"SHA256SUMS"),normal_cache_checked=files_checked,
         reference_rows=len(ref_order),reference_order=digest_order(ref_order),components=16,
         attack_rows=len(order),attack_order=digest_order(order),encoder=encoder,physical_batches=batches,
         source_method=source,geometry=pin(FROZEN/"GEOMETRY.json"),parity="daily and pooled v12 RAW/3D counts for each head",
         independent_geometry=check,h60_support_changed_queries=int((support[0]!=support[2]).sum()),
         h60_ensemble_score_changed_queries=int((base[:,3]!=ms[:,3]).sum()),
         h60_ranges={d:[int(query["h"][query["day"]==d].min()),
                                                  int(query["h"][query["day"]==d].max())] for d in ATTACK},
         decision_file=str((raw_out/"ATTACK_DECISIONS.npz").resolve()),
         decisions=pin(raw_out/"ATTACK_DECISIONS.npz"),result=pin(result)))
    print("DAD positives replay PASS",[(r["day"],r["denominator"],r["raw_detected"],r["multiscale_detected"])
                                         for r in metrics if r["head"]=="ensemble"],flush=True)


if __name__=="__main__":
    main(*map(Path,sys.argv[1:4]))
