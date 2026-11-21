"""Bind the replay adapters to the previously accepted evaluation functions."""
import ast
import gzip
import io
import tarfile
from pathlib import Path
import csv
import hashlib
import json
from shared import HERE,read,write,sha,artifact,check

RUNS=HERE.parent
BASE=RUNS/"p4_password_aug_v1_20261120"
RESULTS=BASE/"received/r1"


def sub(text,old,new):
    if text.count(old)!=1: raise ValueError("Adapter anchor: "+old)
    return text.replace(old,new,1)


def adapt(archive):
    def source(name,symbol):
        body=archive.extractfile(name).read().decode()
        node,=[n for n in ast.parse(body).body if isinstance(n,ast.FunctionDef) and n.name==symbol]
        return ast.get_source_segment(body,node)
    win=source("compare.py","windows")
    win=sub(win,"r[14],r[13]))","r[14],r[13],r[1]))")
    win=sub(win,"conn,off,data,q,x=zip","conn,off,data,q,x,frames=zip")
    win=sub(win,"    results=[]",'''        zeros=np.zeros(len(ids),bool)
        capture("WINDOWS",ids,raw,a["support"],q,frames,kind,~zeros,conn,off,data,zeros,kind)
    results=[]''')
    reg=source("compare.py","regressions")
    reg=sub(reg,'        y=np.array(','''        capture_pool(pool,rows,raw,g["support3"] if pool!="EDGE" else support,q,active,HERE)
        y=np.array(''')
    edge=source("edge_evaluation.py","assess")
    edge=sub(edge,"controls, raw_pair, paired","controls, paired")
    edge=sub(edge,"    results=[]",'''    off=~((q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0))
    capture("EDGE_PASSWORD",ids,raw,g["support3"],q,frames,np.repeat("attack",len(ids)),
            np.ones(len(ids),bool),stream,off,np.asarray(posts,bool),np.asarray(posts,bool),np.repeat("password",len(ids)))
    results=[]''')
    edge=sub(edge,'    save(out/"EDGE_PASSWORD.csv",results)\n    shutil.copyfile(folder/"INPUTS.json",out/"EDGE_INPUTS.json")',
                  '    return results')
    return ('''import json, os, sqlite3
from pathlib import Path
import numpy as np
from compare import by_seed, count_pairs, paired
from collect_inputs import capture,capture_pool,raw_pair
HERE=Path(os.environ["ACCEPTED_R1"])/"package"
from edge_evaluation import SOURCE,TARGET,OWNER
'''+win+"\n\n"+reg+"\n\n"+edge+"\n").encode()


def build(slot):
    assert slot in (2,3,4)
    spec=read(RESULTS/"RETURN.json")
    for n,v in spec["files"].items():check(RESULTS/n,v)
    acceptance=read(RESULTS/"ACCEPTANCE.json")
    assert acceptance["scope"]=="TRAINED_FROZEN_AND_EVALUATED" and read(RESULTS/"LOCAL_ACCEPTANCE.json")["status"]=="PASS"
    archive=BASE/".private/package.tar.gz"
    assert sha(archive)==read(RESULTS/"INSTALL.json")["archive_sha256"]
    contract=dict(parent="p4_password_aug_v1_20261120_r1",package_sha=acceptance["package_sha256"],
        accepted_sha={n:v["sha256"] for n,v in spec["files"].items() if n in (
        "CANDIDATE_FREEZE.json","EDGE_INPUTS.json","TRAINING_INPUTS.json","EDGE_PASSWORD.csv","WINDOWS_CONNECTIONS.csv","FLOOD_NORMAL.csv","ACCEPTANCE.json")},
        populations=dict(win=15849,edge_password=23608,unscorable=42,edge_added=214,unsw_added=1336),
        scope="frozen v12 and r1; source FIT/CAL only; no training; p=4, lambda=0.25",
        normalization="(seed raw score - seed source threshold) / seed CIC FIT span; mean; recalibrate ensemble only",
        decision_sha=sha(RUNS/"mainline_docs/collab/20261120_paper04_aug_scale_review_decision_codex.md"))
    original=read(RUNS/"p4_ton_password_frozen_v12_20261118/FROZEN.json")
    new=read(RESULTS/"CANDIDATE_FREEZE.json")
    contract.update(base_scales=original["method"]["scales"],cuts=dict(v12=original["method"]["cuts"],r1=new["cuts"]),
        heads=dict(v12={s:original["extra_pins"]["head_"+s]["sha256"] for s in ("27","127","227")},r1=new["head_sha256"]))
    training = RUNS / "device_context_head_training_v2_20261105"
    accepted = read(training / "FINAL_TRAINING_ACCEPTANCE.json")
    assert accepted["result"] == "PASS"
    seeds = ("27", "127", "227")
    assert contract["base_scales"] == [accepted["heads"][f"REFIT782_{s}"]["scale"] for s in seeds]
    contract["v12_fit_spans"] = [accepted["heads"][f"FUSION790_{s}"]["scale"] for s in seeds]
    contract["v12_training_receipts"] = {}
    for i,seed in enumerate(seeds):
        name = f"TRAIN_FUSION790_{seed}_RESULT.json"
        digest = sha(training / name)
        receipt = read(training / name)
        assert digest == accepted["receipt_sha256"][name]
        assert receipt["seed"] == int(seed) and receipt["head_sha256"] == contract["heads"]["v12"][seed]
        assert receipt["calibration"]["scale"] == contract["v12_fit_spans"][i]
        contract["v12_training_receipts"][seed] = digest
    write(HERE/"CONTRACT.json",contract)
    names=("CONTRACT.json","shared.py","source_scales.py","replay.py","collect_inputs.py","scale_job.py","report.py","launch.py")
    files={n:(HERE/n).read_bytes().replace(b"\r\n",b"\n") for n in names}
    with tarfile.open(archive) as t:
        manifest=json.load(t.extractfile("PACKAGE_MANIFEST.json"))
        for n,h in manifest["files"].items():
            assert hashlib.sha256(t.extractfile(n).read()).hexdigest()==h
        files["frozen_readers.py"]=adapt(t)
        for n in ("common_round1.py","slurm_base.py","reports.py"):
            files[n]=t.extractfile(n).read()
        files["run.slurm"]=t.extractfile("run.slurm").read().replace(b"/compute.py",b"/scale_job.py")
        assert b'/scale_job.py' in files["run.slurm"]
    for n,b in files.items():
        if n.endswith(".py"):compile(b,n,"exec")
    remote=contract["parent"].rsplit("_",1)[0]+f"_r{slot}"
    pins={n:hashlib.sha256(b).hexdigest() for n,b in sorted(files.items())}
    files["PACKAGE_MANIFEST.json"]=(json.dumps(dict(run=remote,analysis=HERE.name,files=pins),indent=2)+"\n").encode()
    private=HERE/".private";private.mkdir(exist_ok=True)
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as t:
        for n,b in sorted(files.items()):
            m=tarfile.TarInfo(n);m.size=len(b);m.mtime=0
            t.addfile(m,io.BytesIO(b))
    pkg=private/"package.tar.gz"
    pkg.write_bytes(gzip.compress(buf.getvalue(),mtime=0))
    (HERE/"PACKAGE_MANIFEST.json").write_bytes(files["PACKAGE_MANIFEST.json"])
    write(HERE/"LOCAL_SEAL.json",dict(slot=slot,run=remote,package=artifact(pkg),manifest=sha(HERE/"PACKAGE_MANIFEST.json"),
           previous_return_files_verified=len(spec["files"]),parent_sha=contract["package_sha"]))
    print(remote, pkg.stat().st_size, sha(pkg))


if __name__=="__main__":
    import sys
    build(int(sys.argv[1]))
