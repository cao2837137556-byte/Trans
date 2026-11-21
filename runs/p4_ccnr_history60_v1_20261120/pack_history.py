"""Build a compact authenticated deployment from accepted receipts and source code."""
from pathlib import Path
from collections import defaultdict
import csv
import gzip
import hashlib
import io
import json
import tarfile

from history_common import HERE, remote_run, TON, SOURCE, HEADS, HOSTS, sha, read, write, check, artifact

RUNS=HERE.parent
AMP=RUNS/"p4_password_aug_v1_20261120"
R1=AMP/"received/r1"
SC=RUNS/"p4_password_aug_ccnr_scale_20261120"
DUAL=RUNS/"p4_dual_component_mean_v1_20261117"


def read_csv(path):
    with path.open(encoding="utf-8-sig",newline="") as f:
        return list(csv.DictReader(f))


def expected():
    groups=defaultdict(dict)
    for row in read_csv(R1/"FLOOD_NORMAL.csv"):
        pool,kind,view,seed=(row[k] for k in ("source","kind","view","seed"))
        arm=row["head"]
        if view=="post_all":
            name=pool+(".normal.q" if kind=="normal" else ".flood.q")
        elif pool=="EDGE" and view=="post_sampled_normal":
            name="EDGE.normal.c"
        elif pool=="EDGE" and view in ("post_HTTP","post_UDP"):
            name="EDGE."+view[5:]+".q"
        else:
            continue
        groups[name][seed,arm]=(int(row["total"]),int(row["v12"]))
    for file,qual in [("WINDOWS_CONNECTIONS.csv", "off_bypass_payload_packets"),("EDGE_PASSWORD.csv",None)]:
        for row in read_csv(R1/file):
            if file=="WINDOWS_CONNECTIONS.csv":
                if row["view"]!=qual or row["kind"]!="attack":
                    continue
                group="TON.195.payload.c"
            else:
                group="EDGE.password.POST" if row["view"]=="confirmed_login_POST" else "EDGE.password.any"
            groups[group][row["seed"],row["head"]]=(int(row["total"]),int(row["v12"]))
            if group.endswith(".POST"):
                groups[group+".q"][row["seed"],row["head"]]=(int(row["total"]),int(row["v12"]))
    ton=RUNS/TON/"received"
    for r in read_csv(ton/"CCNR_PAIRED.csv"):
        host=r["host"]
        if host not in (*HOSTS,"ALL"):
            continue
        seed=r["head"];role=r["layer"]
        if role=="all":
            base="TON." + host.rsplit(".",1)[1] if host!="ALL" else "TON"
            q=base+".normal.q" if host!="ALL" else "TON.normal.all.q"
            groups[q][seed,"RAW"]=(int(r["normal_n"]),int(r["normal_fp_raw"]))
            groups[q][seed,"CCNR"]=(int(r["normal_n"]),int(r["normal_fp_ccnr"]))
            if host=="ALL":
                continue
            q=base+".password.q"
        elif role=="off_bypass_with_transport_data" and host!="ALL":
            q="TON."+host.rsplit(".",1)[1]+".payload.q"
        else:
            continue
        groups[q][seed,"RAW"]=(int(r["attack_n"]),int(r["A"]))
        groups[q][seed,"CCNR"]=(int(r["attack_n"]),int(r["retained"]))
    fn=RUNS/"p4_ton_connection_lambda_v1_20261119/received/LAMBDA_CONNECTIONS.csv"
    for r in read_csv(fn):
        if float(r["lambda_value"])!=.25:
            continue
        host=r["host"];seed=r["head"]
        base="TON."+host.rsplit(".",1)[1] if host!="ALL" else "TON"
        q=base+".normal.c" if host!="ALL" else "TON.normal.all.c"
        groups[q][seed,"RAW"]=(int(r["normal_total"]),int(r["normal_raw_alerted"]))
        groups[q][seed,"CCNR"]=(int(r["normal_total"]),int(r["normal_alerted"]))
        if host!="ALL":
            q=base+".password.c"
            groups[q][seed,"RAW"]=(int(r["attack_total"]),int(r["attack_raw_alerted"]))
            groups[q][seed,"CCNR"]=(int(r["attack_total"]),int(r["attack_alerted"]))
    result={}
    for g,rows in groups.items():
        assert len(rows)==8,(g,rows.keys())
        result[g]=[]
        for head in HEADS:
            nr,raw=rows[head,"RAW"];nc,final=rows[head,"CCNR"]
            assert nr==nc and 0<=final<=raw<=nr
            result[g].append([nr,raw,final])
    assert result["TON.195.payload.c"][-1]==[18194,14024,245]
    assert result["EDGE.password.any"][-1]==[23608,23608,23122]
    assert result["EDGE.password.POST"][-1]==[23608,23606,19200]
    return result


def deployment_pin():
    sr=SC/"received";tr=RUNS/TON/"received"
    for run in (sr,tr,R1,DUAL/"received",RUNS/"p4_ton_connection_lambda_v1_20261119/received"):
        for k,v in read(run/"RETURN.json")["files"].items():
            check(run/k,v)
    assert read(sr/"LOCAL_ACCEPTANCE.json")["status"]==read(R1/"LOCAL_ACCEPTANCE.json")["status"]=="PASS"
    assert read(sr/"REPRODUCTION.json")["cached_paired_cells"]==192
    source=RUNS/SOURCE
    audit=read(source/"ADMISSION_RESULT.json")
    spec=read(RUNS/"device_context_head_training_v2_20261105/TRAINING_SPEC_FROZEN.json")
    sources=dict(plan=artifact(source/"ASSET_PLAN.json"),
        query_manifest=dict(sha256=audit["query_manifest_sha256"]),cal_membership=spec["data_identity"]["CAL"]["uid_sha256"],
        normal_cal_order=read(sr/"SOURCE.json")["cal_order"])
    verification=read(DUAL/"received/INPUTS_formal.json")["assets"]
    def relative(a):
        return dict(a,path=a["path"].split("/work/paper04/",1)[1])
    flat={pool:relative(verification[pool+":query_rows"]) for pool in ("CIC_DEV","UNSW_DEV","EDGE")}
    e=read(RUNS/"device_context_evaluation_v1_20261105/EDGE_CARD.json")
    t=read(tr/"SCIENCE.json")["references"]["192.168.1.195"]
    verified=read(RUNS/TON/"PACKAGE_MANIFEST.json")["files"]
    expected_scales=read(RUNS/TON/"FROZEN.json")["method"]
    assert expected_scales["p"]==4 and expected_scales["lambda_value"]==.25
    ap=read(AMP/"EDGE_ASSET.json")
    pins=dict(source=sources,scale=read(sr/"REPRODUCTION.json"),flat_rows=flat,
        ton=dict(package={k:{"sha256":verified[k]} for k in ("SCOPED_INPUTS.json","DIAGNOSTIC_CARD.json")},
                sources=artifact(tr/"VERIFIED_INPUTS.json"),arrays=read(tr/"HPC_ARTIFACT_SHA.json"),
                order=read(tr/"RAW_INFERENCE.json")["uid_order_sha256"],win_reference=t["window"],
                win_ref_order=t["ordered_roster_sha256"]),
        edge=dict(raw_inputs=e["raw_inputs"],
                  normal_segments=[s["first_frame"] for s in e["capture_boundaries"]["normal_segments"]],
                  reference_rows=relative(verification["EDGE:reference_rows"])),
        edge_pw=dict(raw=dict(sha256=ap["pcap_sha256"],bytes=ap["pcap_bytes"]),
                     inputs=artifact(R1/"EDGE_INPUTS.json"),owner="dc:a6:32:fb:69:b5",
                     source_ip="192.168.0.170",target_ip="192.168.0.128"))
    return pins,expected_scales


def build(attempt=0):
    run=remote_run(attempt)
    pins,method=deployment_pin()
    contract=dict(rule_sha256=sha(HERE/"METHOD.md"),window_sec=60,calibration="CIC normal TCP CAL weighted P99.9",
        p=4,lambda0=.25,cuts=method["cuts"],scales=method["scales"],no_model_evaluation_or_training=True,
        budgets={"CIC_DEV.normal.q":20,"EDGE.normal.q":20,"EDGE.normal.c":20,"UNSW_DEV.normal.q":74,"TON.normal.all.c":2},
        win10_primary={"n":18194,"raw":14024,"ccnr":245,"goal":7012})
    write(HERE/"INPUT_PINS.json",pins)
    write(HERE/"CONTRACT.json",contract)
    write(HERE/"BASELINE.json",expected())
    names=("METHOD.md","CONTRACT.json","INPUT_PINS.json","BASELINE.json","history_common.py",
           "history_stream.py","inputs_history.py","extract_history.py","donors_history.py","paired_history.py","worker_history.py","launch.py","report_history.py")
    files={n:(HERE/n).read_bytes().replace(b"\r\n",b"\n") for n in names}
    assert hashlib.sha256(files["METHOD.md"]).hexdigest()==contract["rule_sha256"]
    previous=check(SC/".private/package.tar.gz",read(SC/"LOCAL_SEAL.json")["package"])
    with tarfile.open(previous) as t:
        for name in ("common_round1.py","slurm_base.py","reports.py"):
            files[name]=t.extractfile(name).read()
        shell=t.extractfile("run.slurm").read()
        assert shell.count(b"/scale_job.py")==1 and b"\r\n" not in shell
        files["run.slurm"]=shell.replace(b"/scale_job.py",b"/worker_history.py")
    g=(DUAL/"geometry.py").read_bytes().replace(b"\r\n",b"\n")
    assert hashlib.sha256(g).hexdigest()==read(DUAL/"PACKAGE_MANIFEST.json")["files"]["geometry.py"]
    files["donor_geometry.py"]=g
    for fn,b in files.items():
        if fn.endswith(".py"):
            compile(b,fn,"exec")
    pins={k:hashlib.sha256(b).hexdigest() for k,b in sorted(files.items())}
    write(HERE/"PACKAGE_MANIFEST.json",dict(run=run,attempt=attempt,files=pins))
    files["PACKAGE_MANIFEST.json"]=(HERE/"PACKAGE_MANIFEST.json").read_bytes()
    archive=io.BytesIO()
    with tarfile.open(fileobj=archive,mode="w") as tar:
        for name,data in sorted(files.items()):
            member=tarfile.TarInfo(name);member.size=len(data);member.mtime=0;member.mode=0o600
            tar.addfile(member,io.BytesIO(data))
    path=HERE/".private/package.tar.gz"
    path.write_bytes(gzip.compress(archive.getvalue(),mtime=0))
    with tarfile.open(path) as tar:
        assert set(tar.getnames())==set(files)
        assert all(tar.extractfile(n).read()==b for n,b in files.items())
    write(HERE/"LOCAL_SEAL.json",dict(run=run,attempt=attempt,package=artifact(path),manifest=sha(HERE/"PACKAGE_MANIFEST.json"),
                                       baseline_views=len(expected()),rule_sha256=contract["rule_sha256"]))
    print(run,len(files),path.stat().st_size,sha(path))


if __name__=="__main__":
    import sys
    build(int(sys.argv[1]) if len(sys.argv)>1 else 0)
