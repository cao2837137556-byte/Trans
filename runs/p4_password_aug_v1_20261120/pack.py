"""Package the validated code, source receipts and small Gotham inputs for Slurm."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile
from zipfile import ZipFile

HERE=Path(__file__).resolve().parent
RUNS=HERE.parent
PRIVATE=HERE/".private"
TON=RUNS/"p4_ton_password_frozen_v12_20261118"
DUAL=RUNS/"p4_dual_component_mean_v1_20261117"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encoded(obj):
    return (json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()


def inspect_edge_roster(original):
    import numpy as np
    root=RUNS/"edge_query_selection_v1_20261103/seal20k"
    run=RUNS/"edge_formal_evaluation_resume_v2_20261104/retrieved/outputs/gate_182089"
    index_bytes=(run/"encoded/COMPLETE.json").read_bytes()
    assets=json.loads((DUAL/"received/INPUTS_formal.json").read_bytes())["assets"]
    assert sha(index_bytes)==assets["EDGE:encoded_complete"]["sha256"]
    index=json.loads(index_bytes)
    plan=json.loads((run/"BATCH_PLAN.json").read_bytes())
    assert [(b["batch_id"],b["uids"]) for b in plan]==[(b["batch_id"],b["uids"]) for b in index["batches"]]
    selected=set()
    for group in ("NORMAL","HTTP","UDP"):
        with gzip.open(root/(group+"_SELECTED_QUERIES.jsonl.gz"),"rt") as f:
            records=[json.loads(line) for line in f]
        ids=[r["uid"] for r in records]
        assert ids==(root/(group+"_SELECTED_UIDS.txt")).read_text().splitlines()
        assert len(set(ids))==len(ids)==20000 and selected.isdisjoint(ids)
        selected.update(ids)
        if group=="NORMAL":
            with np.load(PRIVATE/"normal_streams.npz",allow_pickle=False) as a:
                assert {r["source_sha256"] for r in records}=={str(a["source_sha"])}
                streams=a["stream"][[r["frame"] for r in records]]
                assert (streams!=0).all()
                normal_connections=len(np.unique(streams))
    ordered=[u for batch in index["batches"] for u in batch["uids"]]
    references=set((root/"REFERENCE_UIDS.txt").read_text().splitlines())
    assert len(references)==4124 and references.isdisjoint(selected)
    assert len(ordered)==len(set(ordered))==64124 and set(ordered)==selected|references
    witness=sha("".join(u+"\n" for u in ordered if u in selected).encode())
    assert witness==original["query_uid_sha256"]["EDGE"]
    with (HERE/"EDGE_POSTS.csv").open(newline="") as f:
        posts=list(csv.DictReader(f))
    assert len(posts)==len({r["post_frame"] for r in posts})==len({r["tcp_stream"] for r in posts})==23650
    return dict(batches=len(plan),queries=len(selected),reference_rows=len(references),
                uid_order_sha256=witness,represented_normal_connections=normal_connections)


def build(attempt=0):
    if type(attempt) is not int or attempt not in range(5):
        raise ValueError("Unknown attempt")
    remote_run=HERE.name if attempt==0 else f"{HERE.name}_r{attempt}"
    from train_candidate import training_weights
    import numpy as np
    card=json.loads((HERE/"EXPERIMENT.json").read_bytes())
    normal=card["training_normal_groups_with_data"]
    groups=[];lab=[]
    for key,n in card["training_attack_groups"].items():
        groups.extend([key]*(n+normal[key]))
        lab.extend([1]*n+[0]*normal[key])
    y=np.array(lab);g=np.array(groups)
    w=training_weights(np.array([.15,.35,.5]),np.array([0,0,1]),y,g,card["mix"])[3:]
    assert all(abs(w[(g==k)&(y==1)].sum()-1/30)<1e-12 for k in normal)
    assert w[y==0].max()<=.0005 and abs(w[y==0].sum()-.047)<1e-12
    pins=json.loads((TON/"received/HPC_ARTIFACT_SHA.json").read_bytes())
    audit=json.loads((HERE/"LOCAL_FRONTEND_AUDIT.json").read_bytes())
    assert audit["gotham_real_anchors"]==12 and audit["edge_scored"] is False and audit["edge_admitted"]>0
    ret=json.loads((TON/"received/RETURN.json").read_bytes())["files"]
    assert ret["HPC_ARTIFACT_SHA.json"]["sha256"]==sha((TON/"received/HPC_ARTIFACT_SHA.json").read_bytes())
    files={p.name:p.read_bytes().replace(b"\r\n",b"\n") for p in (
        HERE/n for n in ("EXPERIMENT.json","compute.py","auxiliary.py","compare.py","edge_evaluation.py","final_report.py",
                         "snapshot_gotham.py","train_candidate.py","launch.py","EDGE_ASSET.json","EDGE_POSTS.csv",
                         "GOTHAM_CONNECTIONS.csv","GOTHAM_SNAPSHOTS.json"))}
    files["TON_PINS.json"]=encoded({k:pins[k] for k in ("snapshots.sqlite","ORDERED_E3.npy","192.168.1.152","192.168.1.195")})
    original=json.loads((DUAL/"FROZEN.json").read_bytes())
    old_edge=inspect_edge_roster(original)
    witness={key:original[key] for key in ("metadata_sha","query_uid_sha256")}
    metrics_path=RUNS/"unified_reference_bank_k8192_v1_20261113_uidfix_184105/received/METRICS.csv"
    with metrics_path.open(encoding="utf-8-sig",newline="") as f:
        witness["baseline"]=[{key:r[key] for key in ("pool","head","group","rows","alarm_count")} for r in csv.DictReader(f)
            if r["config"]=="P4_UNIFIED_HIST_K8192_V1" and r["guard_stratum"]=="ALL"
            and (r["view"]=="full" if r["pool"]=="EDGE" else r["view"]=="post_window_primary")
            and r["group"] in ("NORMAL","ATTACK","HTTP","UDP")]
    assert len(witness["baseline"])==32
    witness["edge"]=old_edge
    files["REGRESSION_PINS.json"]=encoded(witness)
    files["original_v12_inputs.py"]=(DUAL/"inputs.py").read_bytes().replace(b"\r\n",b"\n")
    archived=json.loads((DUAL/"PACKAGE_MANIFEST.json").read_bytes())
    assert sha(files["original_v12_inputs.py"])==archived["files"]["inputs.py"]
    files["MAIN_BANK.json"]=(RUNS/"unified_reference_bank_k8192_v1_20261113_uidfix_184105/received/CANDIDATE_SHA.json").read_bytes()
    files["normal_streams.npz"]=(PRIVATE/"normal_streams.npz").read_bytes()
    sources=json.loads(files["GOTHAM_SNAPSHOTS.json"])
    seen=set()
    with (HERE/"GOTHAM_CONNECTIONS.csv").open(newline="") as f:
        anchors={(r["member"],r["frame"]):r for r in csv.DictReader(f)}
    assert len(anchors)==len({(r["member"],r["connection"]) for r in anchors.values()})==1567
    for s in sources:
        b=(PRIVATE/s["file"]).read_bytes()
        assert sha(b)==s["sha256"] and len(gzip.decompress(b).splitlines())==s["rows"]
        for line in gzip.decompress(b).splitlines():
            r=json.loads(line)
            anchor=anchors[r["member"],str(r["frame"])]
            assert str(r["connection"])==anchor["connection"] and r["label"]==int(anchor["label"])
            assert r["uid"] not in seen and len(r["q"])==14 and len(r["context"])==8
            seen.add(r["uid"])
        files["snapshots/"+s["file"]]=b
    pilot,=[s for s in sources if "raw/benign/iotsim-air-quality-1_" in s["member"]]
    archive=RUNS.parent.parents[1]/"datasets/gotham2025/raw/GothamDataset2025.zip"
    with ZipFile(archive) as z: files["pilot_raw.pcap"]=z.read(pilot["member"])
    assert sha(files["pilot_raw.pcap"])==pilot["raw_sha256"]
    files["common_round1.py"]=(RUNS/"same_information_recalibration_v1_20261113/common_round1.py").read_bytes()
    files["common_ton.py"]=(TON/"common_ton.py").read_bytes()
    files["slurm_base.py"]=(DUAL/"launch.py").read_bytes()
    files["reports.py"]=(DUAL/"reports.py").read_bytes()
    for name in ("slurm_base.py","reports.py","common_round1.py","common_ton.py"):
        files[name]=files[name].replace(b"\r\n",b"\n")
    files["run.slurm"]=(TON/"run.slurm").read_bytes().replace(b"\r\n",b"\n").replace(b"worker_ton.py",b"compute.py")
    ingress=(TON/"asset_ingress.py").read_bytes().replace(b"\r\n",b"\n")
    assert ingress.count(b".p04_tonpw18/token")==1 and ingress.count(b"PORT = 18899")==1
    files["asset_ingress.py"]=ingress.replace(b".p04_tonpw18/token",b".p04_pwaug20/token").replace(b"PORT = 18899",b"PORT = 18919")
    for name,b in files.items():
        if name.endswith(".py"):compile(b,name,"exec")
    pins={n:sha(s) for n,s in sorted(files.items())}
    files["PACKAGE_MANIFEST.json"]=encoded(dict(run=remote_run,attempt=attempt,files=pins))
    target=PRIVATE/"package.tar.gz"
    raw=io.BytesIO()
    with tarfile.open(fileobj=raw,mode="w") as t:
        for name,data in sorted(files.items()):
            info=tarfile.TarInfo(name);info.size=len(data);info.mtime=0;info.mode=0o600
            t.addfile(info,io.BytesIO(data))
    archive=gzip.compress(raw.getvalue(),mtime=0)
    assert len(archive)<=5*1024**2 and len(files)<160 and sum(map(len,files.values()))<=32*1024**2
    target.write_bytes(archive)
    with tarfile.open(fileobj=io.BytesIO(archive),mode="r:gz") as t:
        assert set(t.getnames())==set(files) and all(t.extractfile(n).read()==b for n,b in files.items())
    (HERE/"PACKAGE_MANIFEST.json").write_bytes(files["PACKAGE_MANIFEST.json"])
    (HERE/"LOCAL_VALIDATION.json").write_bytes(encoded(dict(status="PASS_LOCAL_PACKAGE",archive_sha256=sha(archive),
          files=len(files),archive_bytes=len(archive),gotham_snapshots=sum(s["rows"] for s in sources),
          remote_run=remote_run,attempt=attempt,
          auxiliary_attack_candidates=len(y[y==1]),normal_candidates=len(y[y==0]),edge_scored=False,
          edge_original_roster=old_edge,compute_preflight="pending",source_calibration="unchanged CIC normal CAL rule")))
    print("Validated package:",len(files),"files,",len(archive),"bytes")


if __name__=="__main__":
    import argparse
    cli=argparse.ArgumentParser()
    cli.add_argument("--attempt",type=int,choices=range(5),default=0)
    build(cli.parse_args().attempt)
