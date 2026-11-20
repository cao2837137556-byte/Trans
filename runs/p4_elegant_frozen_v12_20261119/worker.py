"""ELEGANT compute-node preflight and formal replay using the accepted v12 CPU runtime."""
import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import time
import traceback

import numpy as np
from common_ton import HERE, Progress, artifact, csv_table, dump, read, require, sha
from seal import NORMAL, COUNTS, GROUPS, census, order
from metrics import SMALL, tables, validate_files


def boot(project):
    from frozen_env import setup
    older,freeze,cfg,geometry=setup(project)
    card=read(HERE/"CARD.json")
    for run,pin in card["parents"].items():
        parent=project/"runs"/run/"package"
        manifest=parent/"PACKAGE_MANIFEST.json"
        require(sha(manifest)==pin,"PARENT_MANIFEST:"+run)
        for name,value in read(manifest)["files"].items():
            require(sha(parent/name)==value,"PARENT_MEMBER:"+name)
        sys.path.append(str(parent))
    return older,freeze,cfg,geometry


def run(phase,project,out):
    older,freeze,cfg,geometry=boot(project)
    if phase=="score":
        # Separate the neural-head import stack, as in the accepted DAD run.
        from dad_worker import score
        return score(project,out,freeze,cfg,Progress(out,"score"))
    from elegant_frontend import ensure_cache,replay_inputs
    from frozen_env import decoder,store
    from representations import encoder,forward_batch
    from dad_geometry import top_two,direct
    from reference_inputs import normalized_context
    from replay_geometry import plan_queries
    from analysis_core import guard
    from vendor import constrained_onboarding_core_v3 as core,p4_worker

    pilot=phase=="preflight"
    require(pilot or phase=="formal","PHASE")
    pkgpin=sha(HERE/"PACKAGE_MANIFEST.json")
    if not pilot:
        pre=read(out/"PREFLIGHT.json")
        require(pre["status"]=="PASS" and pre["package_sha256"]==pkgpin and pre["job"]==read(out/"JOB_preflight.json")["job_id"],"REAL_COMPUTE_PREFLIGHT")
    folder=out/phase;folder.mkdir(exist_ok=False)
    progress=Progress(out,phase)
    progress("CENSUS",description="核对原包、事件标记、参考及查询 UID",force=True)
    start=time.monotonic();exe=decoder();cache=out/"source_cache"
    ensure_cache(HERE,cache)
    truth=read(HERE/"INPUT_SEAL.json")
    require(census(cache,read(HERE/"EVIDENCE.json"),read(HERE/"SOURCES.json"))==truth,"COMPLETE_INDEPENDENT_CENSUS")
    runtime,encoder_id=encoder(project,freeze)
    seal=replay_inputs(folder,HERE,exe,pilot,progress,runtime[3])
    require(seal["components"]==1 and (pilot or (seal["references"],seal["queries"])==(4096,15016)),
            "SEALED_SCOPE")
    expected=read(HERE/"LOCAL_REPLAY.json")
    if not pilot:require(seal["selected_uid_order"]==expected["selected_uid_order"],"LOCAL_REMOTE_FULL_ORDER")
    else:require(seal["queries"]+seal["references"]==expected["pilot_positions"],"REAL_PILOT_SIZE")
    seal.update(files={k:artifact(folder/k) for k in ("input.npz","examples.sqlite","rows.jsonl")},
                encoder=encoder_id,census_sha256=sha(HERE/"INPUT_SEAL.json"),package_sha256=pkgpin)
    dump(folder/"INPUT_SEAL.json",seal)
    prep_seconds=time.monotonic()-start
    with np.load(folder/"input.npz",allow_pickle=False) as a:
        ids,q,x=a["uid"],a["q"],a["x"]
    rows=[json.loads(line) for line in (folder/"rows.jsonl").read_text(encoding="utf8").splitlines()]
    positions={v:i for i,v in enumerate(ids.tolist())}
    n=seal["references"];refs=rows[:n];queries=rows[n:]
    require([r["uid"] for r in rows]==ids.tolist() and len(positions)==len(rows),"INPUT_ORDER")
    require(any(r["capture_id"]==NORMAL[-1] and r["frame"]==31782 for r in refs) and
            queries[0]["frame"]==31784 and all(any(r["group"]==g for r in queries) for g in GROUPS),"BOUNDARY_AND_EVENTS")
    z=np.empty((len(ids),768),np.float32);seen=np.zeros(len(ids),bool)
    db=sqlite3.connect((folder/"examples.sqlite").resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    then=time.monotonic()
    for bid in range(seal["batches"]):
        u,v,_=forward_batch(db,bid,runtime)
        ix=np.array([positions[k] for k in u])
        require(len(set(u))==len(u) and not seen[ix].any(),"CACHED_ENCODER_UID")
        z[ix]=v;seen[ix]=True
        progress("ENCODING",bid+1,seal["batches"],description="冻结 netFound CPU 编码")
    db.close();require(seen.all() and np.isfinite(z).all(),"ENCODER_COVERAGE")
    encode_seconds=time.monotonic()-then
    del runtime
    np.savez(folder/"encoded.npz",uid=ids,e3=z)
    subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"worker.py"),"score",str(project),str(folder)],check=True)
    with np.load(folder/"scores.npz",allow_pickle=False) as a:
        require(np.array_equal(a["uid"],ids),"SCORE_JOIN");raw=a["raw"][n:]
    assets=store(project,freeze)
    def norm(key):
        with np.load(assets.get(key),allow_pickle=False) as a:return a["mean"],a["scale"]
    context=normalized_context(x,norm("context_normalizer"));rid=ids[:n].tolist()
    bank=core.ReferenceBank(refs,z[:n],q[:n],norm("e3_normalizer"),feature_uids=rid,q_uids=rid,allow_prebank_history=True)
    boundary=next(r for r in refs if r["capture_id"]==NORMAL[-1] and r["frame"]==31782)
    _,limits=plan_queries(bank,[dict(boundary,use="QUERY"),queries[0]],geometry)
    require(limits["opening"][0]!="" and limits["opening"][1]=="" and limits["legal_component_count"].tolist()==[0,1],"STRICT_OPEN")
    g=top_two(queries,z[n:],q[n:],context[n:],bank,context[:n],geometry,progress)
    require(np.all(g["opening"]=="") and np.all(g["geometry_ready"]) and np.all(g["legal_rows"]==n)
            and np.all(g["legal_component_count"]==1) and np.all(g["donors"][:,0]>=0),"LEGAL_BANK")
    sample=np.arange(len(queries)) if pilot else np.unique(np.linspace(0,len(queries)-1,48,dtype=int))
    sl={k:v[sample] for k,v in g.items() if isinstance(v,np.ndarray)}
    _,_,err=direct([queries[i] for i in sample],z[n:][sample],q[n:][sample],context[n:][sample],bank,context[:n],geometry,sl)
    support=g["weak"];method=cfg["method"];cuts=np.asarray(method["cuts"])
    flags=guard(q[n:]);corrected=p4_worker.correct(raw,support,q[n:],method["scales"],True,power=method["p"])
    decision_path=folder/"QUERY_DECISIONS.npz"
    np.savez(decision_path,uid=ids[n:],group=[r["group"] for r in queries],frame=[r["frame"] for r in queries],
             member=[r["capture_id"] for r in queries],support=support,raw=raw,ccnr=corrected,raw_alarm=raw>cuts,
             ccnr_alarm=corrected>cuts,cuts=cuts,bypass=flags,legal_components=g["legal_component_count"],
             distances=g["m"],donors=g["donors"])
    events,normal,consistent=tables(decision_path,not pilot)
    group_orders={g:order(ids[n:][np.array([r["group"]==g for r in queries])].tolist()) for g in GROUPS}
    if not pilot:require(group_orders==truth["query_orders"],"FINAL_GROUP_UIDS")
    proof=dict(status="PASS",phase=phase,node=os.environ["SLURMD_NODENAME"],job=os.environ["SLURM_JOB_ID"],
               package_sha256=pkgpin,source_seal_sha256=sha(HERE/"INPUT_SEAL.json"),input_seal=artifact(folder/"INPUT_SEAL.json"),
               queries=len(queries),references=n,components=1,batches=seal["batches"],tshark=artifact(exe),
               group_orders=group_orders,preparation_seconds=prep_seconds,encoding_seconds=encode_seconds,
               independent_distances=len(sample),max_distance_error=err,CIC=read(folder/"CIC_WITNESS.json"),
               neural_inputs=artifact(folder/"encoded.npz"),head_cache=artifact(folder/"scores.npz"),decisions=artifact(decision_path),
               bank_order=seal["physical_reference_order"],query_order=seal["physical_query_order"])
    if pilot:
        proof.update(pilot_witnesses=seal["pilot_witnesses"],uid_zero_checks=consistent,
                     formal_wall_seconds=max(7200,int((prep_seconds+1800+3*encode_seconds*19112/len(ids))/600+1)*600))
        dump(out/"PREFLIGHT.json",proof)
    else:
        with np.load(out/"preflight/QUERY_DECISIONS.npz",allow_pickle=False) as p:
            ix=np.array([positions[k]-n for k in p["uid"].tolist()])
            require((ix>=0).all() and np.allclose(raw[ix],p["raw"],rtol=0,atol=2e-4)
                    and np.array_equal(raw[ix]>cuts,p["raw_alarm"]),"FORMAL_PREFLIGHT_PARITY")
        for fname,table in (("EVENTS.csv",events),("NORMAL.csv",normal),("UID_CONSISTENCY.csv",consistent)):
            csv_table(out/fname,table)
        proof["checks"]=validate_files(out);proof["outputs"]={k:artifact(out/k) for k in SMALL if k.endswith(".csv")}
        dump(out/"FORMAL.json",proof)
    progress("COMPLETE",1,1,description="已逐 UID 核对支持、分数及判决",force=True)


if __name__=="__main__":
    phase,project,target=sys.argv[1:];out=Path(target);begin=time.monotonic()
    try:run(phase,Path(project),out)
    except Exception as exc:
        dump(out/f"FAILURE_{phase}.json",dict(error=str(exc),traceback=traceback.format_exc(),job=os.environ.get("SLURM_JOB_ID")))
        raise
    finally:
        if phase in ("preflight","formal"):
            dump(out/f"RESOURCES_{phase}.json",dict(seconds=time.monotonic()-begin,
                 maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                 child_maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
