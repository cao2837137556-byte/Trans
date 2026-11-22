"""Build an immutable, receipt-bound package with reused readers."""
from pathlib import Path
import gzip
import hashlib
import io
import sys
import tarfile

# Standalone packaging uses the trusted helpers from the accepted parent.
HERE=Path(__file__).resolve().parent
RUNS=HERE.parent
H=RUNS/"p4_ccnr_history60_v1_20261120"
sys.path.insert(0,str(H))
from history_common import artifact, check, read, sha, write
sys.path.pop(0)
TON=RUNS/"p4_ton_password_frozen_v12_20261118"
SCALE=RUNS/"p4_password_aug_ccnr_scale_20261120"
AB=RUNS/"unified_reference_bank_k8192_v1_20261113_uidfix_184105"
DUAL=RUNS/"p4_dual_component_mean_v1_20261117"
SOURCE=RUNS/"device_context_training_v2_20261105"
POOLS=("CIC_DEV","UNSW_DEV","EDGE","TON","EDGE_PASSWORD")


def collect():
    for folder in (H,TON,SCALE,DUAL,AB):
        d=folder/"received"
        for n,v in read(d/"RETURN.json")["files"].items():
            check(d/n,v)
    ok=read(H/"received/ACCEPTANCE.json")
    assert ok["scope"]=="FROZEN_V12_HISTORY60_REPLAY"
    archive=check(H/".private/package.tar.gz",read(H/"LOCAL_SEAL.json")["package"])
    hist_pin=read(H/"INPUT_PINS.json")
    v=read(TON/"received/SCIENCE.json")["references"]
    win={}
    for h in ("192.168.1.152","192.168.1.190","192.168.1.195"):
        win[h]=dict(window=v[h]["window"],order=v[h]["ordered_roster_sha256"],selected=v[h]["selected"])
    context=read(DUAL/"received/INPUTS_formal.json")["assets"]
    pins=dict(history_remote=read(H/"received/INSTALL.json")["run"],
              history_arrays={p:read(H/"received"/f"{p}_INPUT.json") for p in POOLS},
              previous_role_source=ok["manifest_sha256"],unified=read(AB/"received/CANDIDATE_SHA.json"),
              unified_paths=[AB.name,"unified_reference_bank_k8192_v1_20261113_early_183987"],
              source_plan=artifact(SOURCE/"ASSET_PLAN.json"),
              source_catalog=artifact(SOURCE/"RAW_CATALOG.json"),
              edge=hist_pin["edge"],edge_pw=hist_pin["edge_pw"],edge_shards=hist_pin["scale"]["edge_shards"],
              ton_windows=win,ton_encoding=hist_pin["ton"]["arrays"]["ORDERED_E3.npy"],
              old_donors=read(H/"received/DONOR_DIAGNOSTIC.json")["large_files"]["EDGE_DONOR_ROWS.npz"],
              context_uid_hash={p:context[p+":query_context_uids"]["sha256"] for p in ("CIC_DEV","UNSW_DEV")},
              source_cal=read(H/"received/THRESHOLD.json")["arrays"])
    baseline=read(H/"BASELINE.json")
    assert baseline["TON.195.payload.c"][-1]==[18194,14024,245] and len(baseline)==30
    assert baseline["EDGE.password.POST"][-1]==[23608,23606,19200]
    cfg=read(H/"CONTRACT.json")
    rule=dict(main="R2_U1",method_sha256=sha(HERE/"METHOD.md"),original_history=ok["manifest_sha256"],
             cuts=cfg["cuts"],scales=cfg["scales"],p=4,lambda0=.25,training=False,
             previous_budgets_reference_only=cfg["budgets"])
    for n,value in (("ROLE_PINS.json",pins),("INPUT_PINS.json",hist_pin),("BASELINE.json",baseline),("CONTRACT.json",rule)):
        write(HERE/n,value)
    return archive,ok,rule


def build(attempt, history_spare=False):
    assert 0<=attempt<5
    archive,parent,rule=collect()
    own=("ROLE_PINS.json","INPUT_PINS.json","CONTRACT.json","BASELINE.json","METHOD.md",
         "roles.py","screen_geometry.py","role_inputs.py","role_results.py","worker_roles.py","launch.py","report_roles.py")
    files={n:(HERE/n).read_bytes().replace(b"\r\n",b"\n") for n in own}
    assert hashlib.sha256(files["METHOD.md"]).hexdigest()==rule["method_sha256"]
    with tarfile.open(archive) as t:
        raw=t.extractfile("PACKAGE_MANIFEST.json").read()
        assert hashlib.sha256(raw).hexdigest()==parent["manifest_sha256"]
        pin=read(H/"PACKAGE_MANIFEST.json")["files"]
        for n in ("history_common.py","history_stream.py","inputs_history.py","paired_history.py",
                  "common_round1.py","slurm_base.py","reports.py","run.slurm"):
            b=t.extractfile(n).read();assert hashlib.sha256(b).hexdigest()==pin[n]
            files[n]=b
    old=b'r["kind"]=="reference" and host==HOSTS[2]'
    assert files["inputs_history.py"].count(old)==1
    files["inputs_history.py"]=files["inputs_history.py"].replace(old,b'r["kind"]=="reference"')
    files["run.slurm"]=files["run.slurm"].replace(b"/worker_history.py",b"/worker_roles.py")
    assert b"/worker_roles.py" in files["run.slurm"] and b"\r\n" not in files["run.slurm"]
    for n,b in files.items():
        if n.endswith(".py"):
            compile(b,n,"exec")
    if history_spare:
        assert attempt in (3,4)
    run=(H.name if history_spare else HERE.name)+f"_r{attempt}"
    hashes={k:hashlib.sha256(b).hexdigest() for k,b in sorted(files.items())}
    write(HERE/"PACKAGE_MANIFEST.json",dict(run=run,experiment=HERE.name,attempt=attempt,files=hashes,
                                               preflight="role_census_and_real_slice"))
    files["PACKAGE_MANIFEST.json"]=(HERE/"PACKAGE_MANIFEST.json").read_bytes()
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as t:
        for n,b in sorted(files.items()):
            f=tarfile.TarInfo(n);f.size=len(b);f.mtime=0;f.mode=0o600
            t.addfile(f,io.BytesIO(b))
    (HERE/".private").mkdir(exist_ok=True)
    dst=HERE/".private/package.tar.gz"
    dst.write_bytes(gzip.compress(buf.getvalue(),mtime=0))
    with tarfile.open(dst) as t:
        assert set(t.getnames())==set(files)
        assert all(t.extractfile(n).read()==b for n,b in files.items())
    write(HERE/"LOCAL_SEAL.json",dict(run=run,slot=attempt,transport="history_spare" if history_spare else "dedicated",
         manifest_sha256=sha(HERE/"PACKAGE_MANIFEST.json"),
         package=artifact(dst),method_sha256=rule["method_sha256"]))
    print(run,len(files),dst.stat().st_size,sha(dst))


if __name__=="__main__":
    build(int(sys.argv[1]) if len(sys.argv)>1 else 0,sys.argv[2:]==["history-spare"])
