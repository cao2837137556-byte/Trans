"""Bind observed header statistics to the frozen cache rows and seal the source threshold."""
from collections import Counter, defaultdict
from pathlib import Path
import math
import sys

import numpy as np

from history_common import HERE, SOURCE, HOSTS, EDGE_PW, POOLS, artifact, progress, read, save, sha, uid_sha, write, check
from history_stream import trace
from inputs_history import PIN, source_cal, context_inputs, flat, ton, edge_pw, mac, zipped_rows
from paired_history import verify_base, correct, boundaries, min_lambda, severity


def ethernet(project, rows):
    raw=context_inputs(project)
    specs={}
    for capture in {r["capture_id"] for r in rows}:
        ref=raw[capture]
        specs[capture]=dict(path=Path(ref["raw_path"]),
            pin=dict(sha256=ref["source_sha256"],bytes=ref["raw_bytes"]),expected_owners=ref["owners"])
    for r in rows:
        assert r["source_sha256"]==raw[r["capture_id"]]["source_sha256"]
    return specs


def edge_records(project, rows):
    remote=read(project/"runs/edge_formal_evaluation_resume_v2_20261104/RAW_PATHS.json")
    card=PIN["edge"]
    specs={}
    for role in ("NORMAL","HTTP","UDP"):
        pin=card["raw_inputs"][role]
        options=[Path(remote[role]),project/pin["path"]]
        path=next((p for p in options if p.is_file() and p.stat().st_size==pin["bytes"]),options[0])
        specs[role]=dict(path=path,pin=pin,edges=card["normal_segments"] if role=="NORMAL" else ())
    for r in rows:
        assert r["source_sha256"]==card["raw_inputs"][r["source_role"]]["sha256"]
        r["capture_id"]=r["source_role"]
    return specs


def pool_data(project,pool):
    refs=[]
    if pool=="TON":
        rows,a,refs,specs=ton(project)
        for s in specs.values():
            s["expected_owners"]=HOSTS
    elif pool=="EDGE_PASSWORD":
        rows,a,raw=edge_pw(project)
        specs={pool:raw}
    else:
        rows,a=flat(pool,project)
        if pool=="EDGE":
            p=PIN["edge"]["reference_rows"]
            refs=[dict(r,source_role="NORMAL") for r in zipped_rows(check(project/p["path"],p))]
            assert len(refs)==4124
            specs=edge_records(project,[*rows,*refs])
        else:
            specs=ethernet(project,rows)
    if pool!="TON":
        for r in [*rows,*refs]:
            r["owner"]=mac(r["owner"])
    return rows,a,refs,specs


def replay(project,out,phase,rows,specs,pilot=False):
    sys.path.append(str(project/"runs"/SOURCE))
    captures=defaultdict(list)
    for r in rows:
        assert isinstance(r["frame"],int) and r["frame"]>0
        captures[r["capture_id"]].append(r)
    values={};summary={}
    for i,(cap,rr) in enumerate(captures.items(),1):
        progress(out,phase,"正在复核原始帧、方向与 60 秒因果窗口",capture=cap,done=i-1,total=len(captures))
        specs_={k:v for k,v in specs[cap].items() if k in ("path","pin","cooked","edges","expected_owners")}
        rr_values,replay_proof=trace(rows=rr,**specs_,pilot=pilot)
        values.update(rr_values);summary[cap]=replay_proof
    assert len(values)==len(rows)
    return values,summary


def class_weights(rows):
    branches=defaultdict(set)
    count=Counter()
    keys=[]
    for r in rows:
        key=tuple(r[k] for k in ("device","activity","capture_id","session_id"))
        keys.append(key)
        count[key]+=1
        for depth in range(4):
            branches[key[:depth]].add(key[depth])
    w=np.array([1./(count[key]*math.prod(len(branches[key[:d]]) for d in range(4))) for key in keys])
    assert abs(math.fsum(w)-1.)<1e-12
    return w


def quantile(values,weights,p):
    order=np.argsort(values,kind="stable")
    cumulative=np.cumsum(weights[order]/math.fsum(weights),dtype=np.float64)
    cumulative[-1]=1.0
    return int(values[order[np.searchsorted(cumulative,p,side="left")]])


def calibrate(project,out):
    rows=source_cal(project)
    specs=ethernet(project,rows)
    for r in rows:
        r["owner"]=mac(r["owner"])
    values,proof=replay(project,out,"calibrate",rows,specs)
    order=np.array([values[r["uid"]][:4] for r in rows],dtype=np.int64)
    w=class_weights(rows)
    t=quantile(order[:,0],w,.999)
    tail=math.fsum(w[order[:,0]>t])
    assert tail<=.001+1e-12
    np.savez(out/"SOURCE_CAL.npz",uid=[r["uid"] for r in rows],counts=order,weights=w)
    write(out/"THRESHOLD.json",dict(threshold=t,rows=len(rows),inbound=int(order[:,3].sum()),
          quantile=.999,weighted_tail=tail,clock_seconds=60,cal_query_order=uid_sha(r["uid"] for r in rows),
          arrays=artifact(out/"SOURCE_CAL.npz"),captures=len(proof),
          source_role="frozen CIC source CAL normal TCP including zero-coded outbound",target_used=False))
    return dict(threshold_sha256=sha(out/"THRESHOLD.json"),captures=proof)


def process(project,out,phase,pool,contract,expected):
    rows,a,refs,specs=pool_data(project,pool)
    _,_,_,_,seen=verify_base(pool,a,contract,expected)
    values,proof=replay(project,out,phase,[*rows,*refs],specs)
    names=("count","handshake","clock","inbound","proto","payload","role","src","sport","dst","dport")
    ordered=np.array([values[r["uid"]] for r in rows],dtype=np.int64)
    for k,column in zip(names,ordered.T):
        a[k]=column.astype(bool) if k=="inbound" else column
    assert np.array_equal(a["uid"],[r["uid"] for r in rows])
    if pool=="EDGE_PASSWORD":
        assert (a["payload"][a["post"]]>0).all() and a["guard"].sum()==23614
    if pool=="TON":
        assert a["inbound"].all() and np.array_equal(a["payload"]>0,a["data"])
    path=out/(pool+".npz")
    np.savez(path,**a)
    write(out/(pool+"_INPUT.json"),dict(**artifact(path),uid_order=uid_sha(a["uid"]),rows=len(rows),baseline_cells=seen))
    if refs:
        p=out/(pool+"_REF_ENDPOINTS.npz")
        np.savez(p,uid=[r["uid"] for r in refs],
                 evidence=np.array([values[r["uid"]] for r in refs],dtype=np.int64))
        write(out/(pool+"_REF_ENDPOINTS.json"),artifact(p))
    return dict(captures=proof,rows=len(rows),baseline_cells=seen,input_sha256=sha(out/(pool+"_INPUT.json")))


def sample_rows(rows,count=10,min_captures=None):
    by=defaultdict(list)
    for r in rows:
        by[r["capture_id"]].append(r)
    picks=[]
    for cap,rr in list(by.items())[:min_captures]:
        rr.sort(key=lambda r:r["frame"])
        picks.extend(rr[:count])
    return picks


def preflight(project,out,contract,expected):
    phase="preflight"
    src=source_cal(project)
    handful=sample_rows(src,8,2)
    source_specs=ethernet(project,handful)
    for r in handful:
        r["owner"]=mac(r["owner"])
    x,cert=replay(project,out,phase,handful,source_specs,True)
    proof={"source":cert}
    baseline_cells=0
    for pool in POOLS:
        rows,a,_,specs=pool_data(project,pool)
        raw,original,g,_,seen=verify_base(pool,a,contract,expected)
        baseline_cells+=seen
        chosen=sample_rows(rows,count=24,min_captures=2 if pool in ("CIC_DEV","UNSW_DEV") else None)
        x,pr=replay(project,out,phase,chosen,specs,True)
        idx={u:j for j,u in enumerate(a["uid"])}
        ix=np.asarray([idx[r["uid"]] for r in chosen])
        g=g[ix];logits=a["v12"][ix]
        cuts=np.array(contract["cuts"]);scales=np.array(contract["scales"])
        assert np.array_equal(correct(logits,g,scales,.25,cuts),original[ix])
        assert np.array_equal(correct(logits,g,scales,0.,cuts),raw[ix])
        h=np.array([data[0] for data in x.values()])
        assert h.shape==(len(ix),) and (h>=0).all()
        # Use the real slice to check that each IEEE breakpoint brackets its original decision.
        b=boundaries(logits,g,scales,cuts,original[ix],3)
        valid=b>=0
        if valid.any():
            assert correct(logits[valid],g[valid],scales,b[valid,None],cuts)[:,3].all()
            assert not correct(logits[valid],g[valid],scales,np.nextafter(b[valid,None],np.inf),cuts)[:,3].any()
        proof[pool]=dict(captures=pr,rows=len(ix),boundary_rows=int(valid.sum()),baseline_cells=seen)
    assert baseline_cells==len(expected)
    return dict(status="PASS",real_source_and_target=proof,baseline_cells=baseline_cells)
