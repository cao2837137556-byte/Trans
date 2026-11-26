"""Check prior P4_MAIN metrics and inventory inputs for the pending comparisons."""
import csv
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
RUNS=HERE.parent
sys.path.insert(0,str(RUNS/"p4_login_calibration_v1_20261122"))
from sources import HEADS, identity, read, save, table

BASE=RUNS/"p4_complete_bank_v1_20261111/received/results/controls"
TRANSFER=RUNS/"p4_head_transfer_followup_v1_20261115"
REL=RUNS/"p4_ccnr_relative_handshake_v1_20261121/received"
R1=RUNS/"p4_password_aug_v1_20261120/received/r1"
SCALE=RUNS/"p4_password_aug_ccnr_scale_20261120/received"
TON=RUNS/"p4_ton_password_frozen_v12_20261118/received"


def records(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def verify_return(root,name):
    expected=read(root/"RETURN.json")["files"][name]
    actual=identity(root/name)
    assert all(actual[k]==expected[k] for k in ("sha256","bytes"))
    return actual


def hetero(out):
    done=read(BASE/"COMPLETE.json")
    assert done["status"]=="PASS"
    for n in ("METRICS.csv","REFERENCE_BANKS.json","QUERY_ASSETS.json"):
        assert identity(BASE/n)["sha256"]==done["outputs_sha256"][n]
    accepted=TRANSFER/"received"
    for n in ("METRICS.csv","CALIBRATION.json","ACCEPTANCE.json"):
        verify_return(accepted,n)
    assert read(accepted/"ACCEPTANCE.json")["status"]=="PASS"
    spec=read(TRANSFER/"HEAD_ASSETS.json")
    assert read(BASE/"REFERENCE_BANKS.json")==spec["bank"]
    assert read(BASE/"QUERY_ASSETS.json")==spec["query"]
    normal=read(accepted/"CALIBRATION.json")
    mlp_cuts=read(TON/"MODEL_FREEZE_CHECK.json")["cuts"]
    a=records(BASE/"METRICS.csv")
    b=records(accepted/"METRICS.csv")
    select=[("CIC_DEV","post_window_primary","NORMAL",96041),("CIC_DEV","post_window_primary","ATTACK",79056),
            ("UNSW_DEV","post_window_primary","NORMAL",74444),("UNSW_DEV","post_window_primary","ATTACK",72553),
            ("EDGE","full","NORMAL",20000),("EDGE","full","HTTP",20000),("EDGE","full","UDP",20000)]
    modes={"RAW":"RAW","P4_2D_BASE":"2D","P4_MAIN":"3D"}
    aa={(modes[r["config"]],r["pool"],r["view"],r["group"],r["head"]):r for r in a
        if r["guard_stratum"]=="ALL" and r["config"] in modes}
    bb={(r["method"],r["configuration"],r["pool"],r["view"],r["group"],r["head"]):r for r in b
        if r["guard_stratum"]=="ALL"}
    output=[]
    for method in ("MLP","TabM","CatBoost","SLAD"):
        for pool,view,group,n in select:
            digest=spec["bank"][pool]["full_bank"]
            for i,h in enumerate(HEADS):
                scores=[]
                for config in ("RAW","2D","3D"):
                    key=config,pool,view,group,h
                    r=aa[key] if method=="MLP" else bb[(method,*key)]
                    alarm=int(r["alarm_count"])
                    assert int(r["rows"])==n and abs(alarm/n-float(r["sample_rate"]))<1e-14
                    cut=mlp_cuts[i] if method=="MLP" else normal[method]["cuts"][i]
                    output.append(dict(head=method,configuration=config,pool=pool,view=view,group=group,seed=h,unit="query",
                        reference_bank="P4_MAIN",bank_rows=digest["rows"],bank_order_sha256=digest["uid_sha256"],
                        threshold_scope="SOURCE_CAL_NORMAL",threshold=cut,n=alarm,denominator=n,sample_rate=alarm/n,
                        hierarchical_rate=r["hierarchical_rate"]))
                    scores.append(alarm)
                assert scores[1]<=scores[2]<=scores[0]
    table(out/"HETERO_P4_MAIN_VERIFIED.csv",output)
    return spec,normal,len(output)


def wanted(spec):
    need=[]
    def put(task,file,sha,why,bytes_=None):
        need.append(dict(task=task,file=file,sha256=sha,bytes=bytes_,purpose=why))
    for pool,meta in spec["query"].items():
        for name in ("rows","array","scores"):
            put("Table14",meta[name+"_file"],meta[name+"_sha256"],
                f"{pool} UID, view, frozen features and P4_MAIN baseline support")
        put("Table14",pool+"_TABM_P4.npz",spec["TabM"]["gates"][pool]["score_sha256"],"TabM per-seed frozen scores")
        for method in ("CatBoost","SLAD"):
            put("Table14",method+"_"+pool+"_scores.npy",spec[method]["scores"][pool]["sha256"],"per-seed raw score cache")
        put("Table14",pool+"_ROWS.json",spec["old_evaluation"]["pools"][pool]["rows_sha256"],"UID bridge to old head order")
    m=read(REL/"HPC_ARRAY_SHA.json")["pools"]
    for pool in ("CIC_DEV","UNSW_DEV","EDGE","TON"):
        for kind,x in m[pool].items():
            if pool in ("CIC_DEV","UNSW_DEV"):
                why=f"{pool} {kind} from unified bank; use UID to restore h60, rebuild joint match on P4_MAIN"
            elif pool=="EDGE":
                why="identical Edge bank; UID align h60 and support before replay"
            else:
                why="Win10 h60 and source support with matching query UIDs"
            put("Table14" if pool!="TON" else "Win10",x["file"],x["sha256"],why,x["bytes"])
    w=read(SCALE/"REPRODUCTION.json")["caches"]
    for pool in ("WINDOWS","CIC_DEV","UNSW_DEV","EDGE"):
        x=w[pool]["cache"]
        put("Win10",x["file"],x["sha256"],"same rows v12/r1 scores and regression captures",x["bytes"])
    for seed,sha in read(R1/"CANDIDATE_FREEZE.json")["head_sha256"].items():
        put("Win10",f"head_{seed}.npz",sha,"frozen r1 checkpoint for WSL extension")
    return need


def inventory(want):
    project=RUNS.parents[2]
    internal=project/"data_external"
    dataset=project/"datasets"
    args=["rg","--files","--hidden","--no-ignore","-g","!**/.git/**"]
    for n in sorted({x["file"] for x in want}):
        args+=["-g",n]
    args+=list(map(str,(RUNS,internal,dataset)))
    hits=subprocess.run(args,check=False,capture_output=True,text=True,encoding="utf8")
    assert hits.returncode in (0,1), hits.stderr[:500]
    found={}
    for line in hits.stdout.splitlines():
        path=Path(line)
        if path.is_file():
            found.setdefault(path.name,[]).append(path)
    result=[]
    for row in want:
        same=found.get(row["file"],[])
        paths=[str(p) for p in same if (row["bytes"] is None or p.stat().st_size==row["bytes"])
               and identity(p)["sha256"]==row["sha256"]]
        result.append(dict(**row,verified_local=paths,local_name_matches=len(same)))
    return result


def win10(out):
    verify_return(R1,"WINDOWS_CONNECTIONS.csv")
    verify_return(R1,"CANDIDATE_FREEZE.json")
    verify_return(REL,"PAIRED.csv")
    p=[r for r in records(R1/"WINDOWS_CONNECTIONS.csv") if r["seed"]=="ensemble" and
       r["view"]=="off_bypass_payload_packets" and r["kind"]=="attack"]
    m=[r for r in records(REL/"PAIRED.csv") if r["seed"]=="ensemble" and r["group"]=="TON.195.payload.c" and
       r["arm"] in ("RAW","v12","v12_H60")]
    assert all(r["total"]=="18194" for r in [*p,*m])
    r0,=[r for r in p if r["head"]=="RAW"]
    ms,=[r for r in m if r["arm"]=="v12_H60"]
    assert (r0["v12"],r0["candidate"],ms["alarm"])==("14024","18172","14013")
    table(out/"WIN10_EXISTING_COUNTS.csv",[
        dict(arm="v12 RAW",unit="off_bypass_payload_connection",alarm=14024,denominator=18194,
             scope="existing",source=str(R1/"WINDOWS_CONNECTIONS.csv")),
        dict(arm="r1 RAW",unit="off_bypass_payload_connection",alarm=18172,denominator=18194,
             scope="existing augmented-head ablation",source=str(R1/"WINDOWS_CONNECTIONS.csv")),
        dict(arm="v12 CCNR",unit="off_bypass_payload_connection",alarm=245,denominator=18194,
             scope="existing",source=str(REL/"PAIRED.csv")),
        dict(arm="v12 multiscale",unit="off_bypass_payload_connection",alarm=14013,denominator=18194,
             scope="existing registered control",source=str(REL/"PAIRED.csv"))])
    source=read(TON/"VERIFIED_INPUTS.json")
    archive=RUNS.parents[2]/"datasets/external/ton_iot_raw_network/raw_pcap_pilot_v1/password_normal1.pcap"
    proof=identity(archive)
    assert proof=={k:source["inputs"]["password"][k] for k in ("bytes","sha256")}
    registry={}
    project=RUNS.parents[2]
    local=read(TON.parent/"SCOPED_INPUTS.json")["sources"]
    for role in ("events","zeek","normal1log","normal2log"):
        expected={k:source["inputs"][role][k] for k in ("bytes","sha256")}
        matches=[str(path) for n in local[role]["paths"] if (path:=project/n).is_file() and identity(path)==expected]
        registry[role]=dict(expected=expected,verified_local=matches)
    return dict(password_pcap=proof,labels_and_flow_logs=registry,base_missed_connections=4170,
                windows_per_query=read(SCALE/"REPRODUCTION.json")["caches"]["WINDOWS"],
                r1_calibration=read(R1/"CANDIDATE_FREEZE.json"),registered_arms=["v12 plus H60","r1 plus H60","conditional supplementation"])


def main(out):
    spec,cal,rows=hetero(out)
    windows=win10(out)
    local=inventory(wanted(spec))
    align=read(RUNS/"p4_dad_normal_h60_local_v1_20261125/launch_receipts/BANK_ALIGNMENT.json")
    save(out/"HETERO_WIN10_ASSETS.json",dict(status="AUDITED",checked_existing_hetero_rows=rows,p4_main=spec["bank"],
         source_cuts_and_scales=cal,bank_relationship=align["banks"],candidate_arrays=local,win10=windows,
         table14_ms_ready=all(x["verified_local"] for x in local if x["task"]=="Table14"),
         win10_replay_ready=all(x["verified_local"] for x in local if x["task"]=="Win10")))
    print("prior head rows verified",rows,"expected array assets",len(local),
          "verified local",sum(bool(x["verified_local"]) for x in local),flush=True)


if __name__=="__main__":
    main(Path(sys.argv[1]))
