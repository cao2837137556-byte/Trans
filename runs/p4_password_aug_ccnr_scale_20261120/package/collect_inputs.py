"""Retain the score/support rows already used by the frozen r1 evaluation."""
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import numpy as np
from shared import HERE,PARENT,read,write,sha,artifact,uid_sha,table,save


def raw_pair(stuff,ids,z,q,x):
    parent=stuff.project/"runs"/PARENT
    with tempfile.TemporaryDirectory(dir=os.environ["REPLAY_OUTPUT"],prefix="score-input-") as tmp:
        folder=Path(tmp)
        for key,value in (("uid",np.asarray(ids,dtype="U64")),("z",z),("q",q),("x",x)):
            np.save(folder/(key+".npy"),value,allow_pickle=False)
        subprocess.run([sys.executable,"-B",str(parent/"package/compare.py"),str(stuff.project),str(parent),
                        str(folder),"paired"],check=True)
        with np.load(folder/"scores.npz",allow_pickle=False) as a:
            assert np.array_equal(a["uid"],ids)
            return a["old"],a["new"]


def capture(pool,ids,raw,support,q,frame,kind,active,group,off,data,post,activity):
    out=Path(os.environ["REPLAY_OUTPUT"])
    n=len(ids)
    arrays=dict(uid=np.asarray(ids,dtype="U64"),v12=raw[0],r1=raw[1],support=support,
                guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0),frame=np.asarray(frame),
                kind=np.asarray(kind),active=np.asarray(active,bool),group=np.asarray(group),
                off=np.asarray(off,bool),data=np.asarray(data,bool),post=np.asarray(post,bool),activity=np.asarray(activity))
    assert len(set(ids))==n and all(len(a)==n and a.dtype.kind!="O" for a in arrays.values())
    assert np.array_equal(~arrays["guard"],arrays["off"]) and np.isfinite(support).all()
    assert np.all((support>=0)&(support<=1))
    for version in ("v12","r1"):
        v=arrays[version]
        assert v.shape==(n,4) and np.isfinite(v).all() and np.array_equal(v[:,:3].mean(axis=1),v[:,3])
    dest=out/(pool+".npz")
    np.savez(dest,**arrays)
    write(out/(pool+"_INDEX.json"),dict(rows=n,uid_order=uid_sha(ids),cache=artifact(dest)))


def capture_pool(pool,rows,raw,support,q,active,root):
    y=np.asarray([r["label"] for r in rows])
    group=np.arange(len(y))
    if pool=="EDGE":
        ix=np.flatnonzero((y==0)&active)
        with np.load(root/"normal_streams.npz",allow_pickle=False) as a:
            assert {rows[i]["source_sha256"] for i in ix}=={str(a["source_sha"])}
            group[ix]=a["stream"][[rows[i]["frame"] for i in ix]]
        assert len(np.unique(group[ix]))==19543
    guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
    zeros=np.zeros(len(y),bool)
    activity=[r["source_role"] if pool=="EDGE" else r.get("activity") or "unknown" for r in rows]
    capture(pool,[r["uid"] for r in rows],raw,support,q,[r["frame"] for r in rows],np.where(y,"attack","normal"),
            active,group,~guard,zeros,zeros,activity)


def verify_edge(parent):
    edge=parent/"edge"
    pin=read(parent/"EDGE_INPUTS.json")
    assert pin==read(edge/"INPUTS.json") and sha(edge/"queries.sqlite")==pin["database_sha"]
    db=sqlite3.connect((edge/"queries.sqlite").resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    proof={}
    for j in range(8):
        p=edge/f"e3_{j}.npz"
        uids=[r[0] for r in db.execute("SELECT uid FROM batch WHERE batch % 8=? ORDER BY batch,slot",(j,))]
        with np.load(p,allow_pickle=False) as a:
            assert np.array_equal(a["uid"].astype("U64"),uids)
            assert a["z"].dtype==np.float32 and a["z"].shape==(len(uids),768) and np.isfinite(a["z"]).all()
        proof[str(j)]=dict(sha256=sha(p),uid_order=uid_sha(uids),rows=len(uids))
    db.close()
    assert sum(v["rows"] for v in proof.values())==pin["queries"]
    return proof


def verify_parent(project):
    p=project/"runs"/PARENT
    spec=read(HERE/"CONTRACT.json")
    assert sha(p/"package/PACKAGE_MANIFEST.json")==spec["package_sha"]
    for n,h in read(p/"package/PACKAGE_MANIFEST.json")["files"].items():
        assert sha(p/"package"/n)==h,n
    for n,h in spec["accepted_sha"].items():
        assert sha(p/n)==h,n
    return p


def same_rows(actual,path):
    expected=table(path)
    assert len(expected)==len(actual)
    for i,(a,b) in enumerate(zip(actual,expected)):
        assert {k:str(v) for k,v in a.items()}==b,(path.name,i)


def reproduce(project,out):
    parent=verify_parent(project)
    sys.path.append(str(parent/"package"))
    from frozen_readers import windows,regressions,assess
    from compare import controls
    s=controls(project,parent)
    files={"WINDOWS_CONNECTIONS.csv":windows(project,s),"FLOOD_NORMAL.csv":regressions(project,s)}
    proof=verify_edge(parent)
    files["EDGE_PASSWORD.csv"]=assess(project,parent)
    for n,rows in files.items():
        same_rows(rows,parent/n)
    from replay import verify_original_caches
    cells=verify_original_caches(out,parent)
    pools=("WINDOWS","CIC_DEV","UNSW_DEV","EDGE","EDGE_PASSWORD")
    write(out/"REPRODUCTION.json",dict(rows_checked={n:len(rows) for n,rows in files.items()},cached_paired_cells=cells,edge_shards=proof,
          caches={p:read(out/(p+"_INDEX.json")) for p in pools},source_sha=sha(out/"SOURCE.json")))
