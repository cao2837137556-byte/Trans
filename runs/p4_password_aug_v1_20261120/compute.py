"""Run the candidate training phases inside the existing pinned compute runtime."""
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = "p4_password_aug_v1_20261120"


def write(path, data):
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data,indent=2,allow_nan=False)+"\n",encoding="utf8")
    tmp.replace(path)


def progress(out,phase,description,done=0,total=0):
    write(out/"PROGRESS.json",dict(phase=phase,description=description,done=done,total=total,
          job=os.environ["SLURM_JOB_ID"],updated_unix=time.time()))


def run_child(args,out,name):
    job=os.environ["SLURM_JOB_ID"]
    path=out/f"{name}-{job}.stderr"
    with path.open("wb") as stream:
        result=subprocess.run(args,stderr=stream)
    if result.returncode:
        with path.open("rb") as stream:
            stream.seek(max(0,path.stat().st_size-16384))
            detail=stream.read().decode("utf8","replace")
        raise RuntimeError(f"{name} exited {result.returncode}\n{detail}")


def run(project, out, phase):
    from auxiliary import sha
    manifest = json.loads((HERE/"PACKAGE_MANIFEST.json").read_bytes())
    assert not sys.flags.optimize and os.environ.get("SLURMD_NODENAME") and os.environ["SLURM_JOB_ID"].isdigit()
    attempt=manifest["attempt"]
    target=RUN if attempt==0 else f"{RUN}_r{attempt}"
    assert attempt in range(5) and manifest["run"] == target and out == project/"runs"/target and HERE == out/"package"
    for name, pin in manifest["files"].items():
        assert sha(HERE/name) == pin, name
    pilot = phase == "preflight"
    folder = out/("pilot" if pilot else "formal")
    folder.mkdir(exist_ok=True)
    if not pilot:
        pf = json.loads((out/"PREFLIGHT.json").read_bytes())
        assert pf["status"] == "PASS" and pf["package"] == sha(HERE/"PACKAGE_MANIFEST.json")
    progress(out,phase,"计算节点已开始读取本阶段输入")
    if phase.startswith("edge_") or phase in ("windows","regression"):
        seal=json.loads((out/"FREEZE.json").read_bytes())
        assert seal["package"]==sha(HERE/"PACKAGE_MANIFEST.json") and seal["candidate_sha256"]==sha(out/"CANDIDATE_FREEZE.json")
    if pilot or phase == "prepare":
        if pilot:
            sys.path.insert(0,str(project/"runs/device_context_training_v2_20261105"))
            sys.path.append(str(project/"runs/unified_reference_bank_k8192_v1_20261113_early_183987/package/repo/ood"))
            from snapshot_gotham import snapshots
            with (HERE/"GOTHAM_CONNECTIONS.csv").open(newline="") as f:
                points=[r for r in csv.DictReader(f) if r["device"]=="iotsim-air-quality-1" and r["label"]=="0"]
            with gzip.open(next((HERE/"snapshots").glob("iotsim-air-quality-1*normal.jsonl.gz")),"rt") as f:
                expected=[json.loads(line) for line in f]
            p=HERE/"pilot_raw.pcap"
            got=list(snapshots(p,points[0]["member"],{int(r["frame"]):r for r in points},sha(p),shutil.which("tshark")))
            assert len(got)==12 and json.loads(json.dumps(got))==expected, "compute-node prefix parity"
            run_child([sys.executable,"-B",str(HERE/"compute.py"),"baseline",str(project),str(out)],out,"baseline")
        for mode in ("encode","source"):
            run_child([sys.executable,"-B",str(HERE/"compute.py"),mode,str(project),str(out),
                            "pilot" if pilot else "formal"],out,mode)
    if pilot or phase.startswith("train_"):
        seed=27 if pilot else int(phase.split("_")[1])
        if pilot:
            run_child([sys.executable,"-B",str(HERE/"compute.py"),"pilot_train",str(project),str(out)],out,"pilot-train")
            steps=json.loads((folder/"PILOT_UPDATES.json").read_bytes())["steps"]
        else:
            from train_candidate import train_one
            steps=train_one(project,folder,seed,False)
        assert steps>0
        with np.load(folder/f"head_{seed}.npz",allow_pickle=False) as model:
            assert all(np.isfinite(v).all() for v in model.values())
        logits = np.load(folder/f"cal_{seed}.npy")
        assert np.isfinite(logits).all() and len(logits)>0
    if phase == "freeze":
        from train_candidate import source
        worker, d = source(project)
        nr=[d["rows"][int(i)] for i in d["cal"] if d["rows"][int(i)]["label"]==0]
        arr = np.stack([np.load(folder/f"cal_{s}.npy") for s in (27,127,227)],axis=1)
        assert arr.shape == (len(nr),3) and len(nr)==33147
        with np.load(folder/"fit_meta.npz",allow_pickle=False) as m:
            assert np.array_equal(m["cal_uid"],[r["uid"] for r in nr])
        arr=np.column_stack([arr,arr.astype(np.float64).mean(axis=1)])
        cuts=[worker.k.threshold(a,nr,.01) for a in arr.T]
        w=worker.k.class_weights(nr)
        fpr=[float(w[a>t].sum()) for a,t in zip(arr.T,cuts)]
        assert max(fpr)<=.01+1e-13
        write(out/"CANDIDATE_FREEZE.json",dict(cuts=cuts,cal_normal_connections_scope="original CIC CAL packet queries",
              cal_queries=len(nr),weighted_fprs=fpr,
              head_sha256={s:sha(folder/f"head_{s}.npz") for s in (27,127,227)},
              control="frozen v12", calibration_sha256=sha(folder/"fit_meta.npz"),
              method_sha256=sha(HERE/"EXPERIMENT.json"), edge_scored=False))
    if phase in ("windows","regression"):
        from compare import controls,windows,regressions,save
        stuff=controls(project,out)
        rows=windows(project,stuff) if phase=="windows" else regressions(project,stuff)
        save(out/("WINDOWS_CONNECTIONS.csv" if phase=="windows" else "FLOOD_NORMAL.csv"),rows)
    if phase.startswith("edge_"):
        from edge_evaluation import prepare,encode,assess
        if phase=="edge_prepare": prepare(project,out)
        elif phase=="edge_assess": assess(project,out)
        else: encode(project,out,int(phase.split("_")[1]))
    receipt=dict(status="PASS",phase=phase,package=sha(HERE/"PACKAGE_MANIFEST.json"),job=os.environ["SLURM_JOB_ID"])
    if phase=="freeze": receipt["candidate_sha256"]=sha(out/"CANDIDATE_FREEZE.json")
    if pilot:
        receipt.update(original_frames_replayed=12,train_updates=steps,calibration_scores=len(logits),
                       frozen_control_sha256=sha(out/"V12_BASELINE.csv"),node=os.environ["SLURMD_NODENAME"])
    write(out/(phase.upper()+".json"),receipt)


if __name__=="__main__":
    phase,project,out=sys.argv[1:4]; project=Path(project);out=Path(out)
    if phase=="baseline":
        from compare import controls,regressions,save
        original=controls(project,out,baseline_only=True)
        rows=regressions(project,original)
        assert rows and all(r["gained"]==r["lost"]==0 for r in rows)
        save(out/"V12_BASELINE.csv",rows)
    elif phase=="pilot_train":
        from train_candidate import train_one
        steps=train_one(project,out/"pilot",27,True)
        write(out/"pilot/PILOT_UPDATES.json",dict(steps=steps))
    elif phase in ("encode","source"):
        folder=out/sys.argv[4]; pilot=folder.name=="pilot"
        if phase=="encode":
            from auxiliary import prepare
            prepare(project,folder,pilot)
        else:
            from train_candidate import materialize
            materialize(project,folder,pilot)
    else:
        try:
            run(project,out,phase)
        except Exception as exc:
            write(out/f"FAILURE_{phase}.json",dict(phase=phase,error=str(exc) or repr(exc),
                  job=os.environ.get("SLURM_JOB_ID"),traceback=traceback.format_exc()))
            raise
