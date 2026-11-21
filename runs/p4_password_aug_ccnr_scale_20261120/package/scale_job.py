"""Compute-node only entry points for preflight, baseline reproduction, and cache replay."""
import os
import sqlite3
import subprocess
import sys
import time
import traceback
from pathlib import Path
import numpy as np
from shared import HERE,PARENT,read,write,sha,artifact,uid_sha
from collect_inputs import raw_pair,verify_parent


def status(out,phase,message):
    write(out/"PROGRESS.json",dict(phase=phase,description=message,job=os.environ["SLURM_JOB_ID"],updated_unix=time.time()))


def pilot(project,out):
    parent=verify_parent(project)
    sys.path.append(str(parent/"package"))
    from compare import controls
    controls_=controls(project,parent)
    from evaluate_ton import QUERY
    pins=read(parent/"package/TON_PINS.json")
    for key in ("snapshots.sqlite","ORDERED_E3.npy","192.168.1.195"):
        p=Path(pins[key]["path"])
        assert p.stat().st_size==pins[key]["bytes"] and sha(p)==pins[key]["sha256"]
    from vendor import p4_worker
    with np.load(pins["192.168.1.195"]["path"],allow_pickle=False) as scores:
        ix=np.unique(np.r_[np.linspace(0,len(scores["index"])-1,64,dtype=int),
                            np.flatnonzero(scores["support"]>0)[:12],np.flatnonzero(~scores["off_bypass"])[:12]])
        indices=scores["index"][ix];uids=scores["uid"][ix].astype("U64")
        ref=scores["raw_alarm"][ix];ref2=scores["ccnr_alarm"][ix]
        support=scores["support"][ix]
    take=set(indices)
    db=sqlite3.connect(Path(pins["snapshots.sqlite"]["path"]).as_uri()+"?mode=ro&immutable=1",uri=True)
    rows=[r for i,r in enumerate(db.execute(QUERY)) if i in take]
    db.close()
    assert [r[7] for r in rows]==list(uids) and all(r[3]=="192.168.1.195" for r in rows)
    q=np.stack([np.frombuffer(r[14],"<f4") for r in rows])
    x=np.stack([np.frombuffer(r[13],"<f8") for r in rows])
    z=np.load(pins["ORDERED_E3.npy"]["path"],mmap_mode="r")[indices]
    raw=raw_pair(controls_,uids,z,q,x)
    cfg=controls_.cfg["method"]
    real=p4_worker.correct(raw[0],support,q,cfg["scales"],True,4)
    assert np.array_equal(raw[0]>cfg["cuts"],ref) and np.array_equal(real>cfg["cuts"],ref2)
    status(out,"preflight","真实 Windows 10 切片已复现 v12 原判决，正在核对 CIC 源跨度和阈值")
    subprocess.run([sys.executable,"-B",str(HERE/"source_scales.py"),str(project),str(out)],check=True)
    from replay import decisions
    source=read(out/"SOURCE.json")
    guard=(q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0)
    for model,arr in zip(("v12","r1"),raw):
        arm=decisions(arr,support,guard,np.array(cfg["scales"]),source["models"][model])
        cut=np.array(source["models"][model]["cuts"])
        expected=p4_worker.correct(arr,support,q,cfg["scales"],True,4)
        assert np.array_equal(arm["original"][1]>0,expected>cut)
        assert np.max(np.abs(arm["original"][1]-(expected-cut)))<1e-10
        group=np.unique([r[9] for r in rows],return_inverse=True)[1]
        ag=np.zeros((group.max()+1,4),bool);np.logical_or.at(ag,group,arm["standardized"][1]>0)
        assert len(ag)>0
    return dict(real_queries=len(uids),uid_order=uid_sha(uids),guarded=int(guard.sum()),positive_support=int((support>0).sum()),
                source_sha=sha(out/"SOURCE.json"),seed_and_ensemble_parity=True)


def main(phase,project,out):
    manifest=read(HERE/"PACKAGE_MANIFEST.json")
    assert not sys.flags.optimize and os.environ["SLURM_JOB_ID"].isdigit() and os.environ["SLURMD_NODENAME"]
    assert HERE==out/"package" and out==project/"runs"/manifest["run"]
    for n,h in manifest["files"].items(): assert sha(HERE/n)==h,n
    os.environ["REPLAY_OUTPUT"]=str(out)
    os.environ["ACCEPTED_R1"]=str(project/"runs"/PARENT)
    start=time.monotonic()
    status(out,phase,{"preflight":"核验冻结输入与真实计算节点小切片","reproduce":"逐查询复现 v12 和 r1，封存分数与支持度",
           "formal":"对同批查询回放三种尺度和集成方式"}[phase])
    proof={}
    if phase=="preflight":
        proof=pilot(project,out)
    else:
        assert read(out/"PREFLIGHT.json")["source_sha"]==sha(out/"SOURCE.json")
        if phase=="reproduce":
            from collect_inputs import reproduce
            reproduce(project,out)
            proof["reproduction_sha"]=sha(out/"REPRODUCTION.json")
        elif phase=="formal":
            assert read(out/"REPRODUCE.json")["reproduction_sha"]==sha(out/"REPRODUCTION.json")
            from replay import evaluate
            from report import paper
            evaluate(out);(out/"RESULTS_FOR_PAPER.md").write_bytes(paper(out).encode("utf8"))
        else: raise ValueError(phase)
    write(out/(phase.upper()+".json"),dict(status="PASS",job=os.environ["SLURM_JOB_ID"],phase=phase,
          node=os.environ["SLURMD_NODENAME"],package=sha(HERE/"PACKAGE_MANIFEST.json"),seconds=time.monotonic()-start,**proof))


if __name__=="__main__":
    phase=sys.argv[1];project,out=map(Path,sys.argv[2:4])
    try: main(phase,project,out)
    except Exception as exc:
        write(out/f"FAILURE_{phase}.json",dict(error=str(exc) or repr(exc),traceback=traceback.format_exc()))
        raise
