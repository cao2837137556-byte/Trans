"""Compute-node role census, real geometry preflight, and frozen paired replays."""
import os
from pathlib import Path
import resource
import sys
import time
import traceback

import numpy as np
from history_common import HERE, artifact, check, progress, read, save, sha, uid_sha, write

PHASE_POOLS={"cic":"CIC_DEV","unsw":"UNSW_DEV","edge":"EDGE","ton":"TON","password":"EDGE_PASSWORD"}


def checkpoints(a,qroles):
    # First real rows from each scoped geometry and observed role, including
    # rows with and without archived support. No data-dependent method choice.
    groups={}
    for j in range(len(qroles)):
        key=(int(qroles[j,0]),str(a["kind"][j]),bool(a["support"][j]>0),bool(a["guard"][j]))
        box=groups.setdefault(key,[])
        if len(box)<3:
            box.append(j)
    return np.array(sorted(i for box in groups.values() for i in box))


def dispatch(phase,project,out,package):
    from role_inputs import structure,extract,materialize,npz
    from role_results import role_coverage,summarize_pool,edge_focal_indices
    from paired_history import verify_base
    from screen_geometry import supports,decisions
    do_pilot=phase.startswith("check_")
    stem=phase[6:] if do_pilot else phase
    pool=PHASE_POOLS[stem]
    contract=read(HERE/"CONTRACT.json");expect=read(HERE/"BASELINE.json")
    assert sha(HERE/"METHOD.md")==contract["method_sha256"]
    data=structure(project,pool,contract)
    a=data["a"]
    _,_,_,_,seen=verify_base(pool,a,contract,expect)
    roles_path=out/f"{pool}_ROLE_BIND.npz"
    witness_name=out/f"{pool}_ROLE_CENSUS.json"
    if do_pilot:
        qr,rr,p=extract(project,out,phase,pool,data)
        coverage=role_coverage(pool,qr,rr,a,data["refs"])
        role_proof=dict(captures=len(p),physical_frames=sum(v["frames"] for v in p.values()),
                   all_frames_attributed=True,raw_samples=sum(len(v["samples"]) for v in p.values()))
        role_io=out/f"{pool}_RAW_ANCHORS.json"
        write(role_io,dict(captures=p))
        np.savez(roles_path,query_uid=[r["uid"] for r in data["rows"]],ref_uid=[r["uid"] for r in data["refs"]],
                 query=qr,ref=rr)
        write(witness_name,dict(**artifact(roles_path),coverage=coverage,proof=role_proof,raw_proof=artifact(role_io)))
        take=checkpoints(a,qr)
        if pool=="EDGE":
            focus=edge_focal_indices(project,a)
            take=np.unique(np.r_[take,focus[502][:3],focus[443]])
        progress(out,phase,"角色覆盖已清点，正在以真实切片复现 v12 并核验全部筛选臂",rows=len(take))
    else:
        planned=read(out/"PREP_RECEIPT.json")
        p=read(out/f"CHECK_{stem.upper()}.json")
        assert planned["status"]==p["status"]=="PASS" and p["package"]==package
        assert planned["checks_sha256"][stem]==sha(out/f"CHECK_{stem.upper()}.json")
        assert p["role_census_sha256"]==sha(witness_name)
        witness=read(witness_name)
        roles=npz(check(roles_path,witness))
        assert np.array_equal(roles["query_uid"],a["uid"])
        assert np.array_equal(roles["ref_uid"],[x["uid"] for x in data["refs"]])
        qr,rr=roles["query"],roles["ref"]
        take=np.arange(len(qr))
        progress(out,phase,"正在全量检索各筛选臂的两个不同相容组件",queries=len(take))
    rows,z,q,x=materialize(project,data,take)
    aa={k:v[take] for k,v in a.items()}
    role=qr[take]
    masks,proof=supports(rows,z,q,x,role,rr,data["bank"],data["rc"],data["geom"],aa["support"],
                         lambda n:progress(out,phase,"三空间检索进行中",checked_queries=n),pilot=do_pilot)
    outs=decisions(aa,masks,contract)
    if do_pilot:
        assert proof["matrix_pairs"]>0 and witness_name.is_file()
        result=dict(role_census_sha256=sha(witness_name),coverage=coverage,raw=role_proof,small_slice=len(take),
                    geometry=proof,uid_order=uid_sha(r["uid"] for r in rows),baseline_views=seen)
        if pool=="CIC_DEV":
            from role_inputs import CACHE,HISTORY
            ref=CACHE["source_cal"]
            cp=project/"runs"/HISTORY/ref["file"]
            if cp.is_file():
                with np.load(check(cp,ref),allow_pickle=False) as obj:
                    hs=obj["counts"][:,1]
                    assert len(hs)==16430
                    vals=np.percentile(hs,[50,90,99,99.9,100])
                result["source_handshake"]=dict(group="CIC_CAL.normal_TCP",kind="normal",unit="query",
                    aggregation="one_value_per_query",total=len(hs),
                    **dict(zip(("P50","P90","P99","P999","Max"),map(float,vals))))
        return result
    npzfile=out/f"{pool}_DECISIONS.npz"
    np.savez(npzfile,uid=a["uid"],reference_uid=[r["uid"] for r in data["refs"]],
        **outs,U1_support=masks["U1"][0],U2_support=masks["U2"][0],
        U1_r2_legal=masks["U1"][1],U2_r2_legal=masks["U2"][1])
    tablepins=summarize_pool(project,out,pool,data,qr,rr,outs,masks)
    return dict(tables=tablepins,large=artifact(npzfile),baseline_views=seen,geometry=proof,
                query_uid_order_sha256=uid_sha(a["uid"]))


def main(phase,project,out):
    manifest=read(HERE/"PACKAGE_MANIFEST.json")
    assert manifest["experiment"]=="p4_ccnr_role_port_v1_20261121"
    assert HERE==out/"package" and out==project/"runs"/manifest["run"]
    assert not sys.flags.optimize and os.environ["SLURM_JOB_ID"].isdigit() and os.environ["SLURMD_NODENAME"]
    for name,pin in manifest["files"].items():
        check(HERE/name,{"sha256":pin})
    pkg=sha(HERE/"PACKAGE_MANIFEST.json")
    now=time.monotonic()
    progress(out,phase,"真实计算节点校验冻结分数、输入和参考库")
    r=dispatch(phase,project,out,pkg)
    write(out/(phase.upper()+".json"),dict(status="PASS",phase=phase,package=pkg,
        job=os.environ["SLURM_JOB_ID"],node=os.environ["SLURMD_NODENAME"],seconds=time.monotonic()-now,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**r))
    progress(out,phase,"已写通过回执")


if __name__=="__main__":
    phase=sys.argv[1];project,out=map(Path,sys.argv[2:4])
    try:
        main(phase,project,out)
    except Exception as exc:
        write(out/f"FAILURE_{phase}.json",dict(error=str(exc) or repr(exc),traceback=traceback.format_exc()))
        raise
