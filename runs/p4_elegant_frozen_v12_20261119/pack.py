"""Assemble the experiment with the accepted parents and six verified original members."""
import hashlib
import io
import json
import os
from pathlib import Path
import gzip
import tarfile
from seal import check, read, sha

HERE=Path(__file__).resolve().parent
DAD=HERE.parent/"p4_dad_frozen_v12_20261119"
TON=HERE.parent/"p4_ton_password_frozen_v12_20261118"
PRIVATE=HERE/".private"
SOURCE=("seal.py","elegant_frontend.py","worker.py","metrics.py","launch.py")


def build():
    dad=read(DAD/"PACKAGE_MANIFEST.json")
    dadpin=read(DAD/"received/ACCEPTANCE.json")["package_sha256"]
    tonpin=read(TON/"received/ACCEPTANCE.json")["package_sha256"]
    check(sha((DAD/"PACKAGE_MANIFEST.json").read_bytes())==dadpin and sha((TON/"PACKAGE_MANIFEST.json").read_bytes())==tonpin,"PARENT_PINS")
    cache=Path(os.environ["LOCALAPPDATA"])/"Paper04/datasets/ELEGANT2021"
    files={n:(HERE/n).read_bytes().replace(b"\r\n",b"\n") for n in SOURCE}
    for name in ("SOURCES.json","EVIDENCE.json","INPUT_SEAL.json","LOCAL_REPLAY.json","README.md"):
        files[name]=(HERE/name).read_bytes()
    check(sha(files["INPUT_SEAL.json"])==read(HERE/"LOCAL_REPLAY.json")["input_seal_sha256"],"LOCAL_SEAL")
    with tarfile.open(DAD/".private/package.tar.gz","r:gz") as t:
        for n in ("common_ton.py","common_round1.py","FROZEN.json","frozen_env.py","onboarding_dense_reference_v1.py",
                  "slurm_base.py","reports.py","run.slurm"):
            b=t.extractfile(n).read()
            check(sha(b)==dad["files"][n],"ACCEPTED_PARENT_FILE:"+n)
            files[n]=b.replace(b"dad_worker.py",b"worker.py") if n=="run.slurm" else b
    for name,v in read(HERE/"SOURCES.json").items():
        b=(cache/(name+".xz")).read_bytes()
        check(len(b)==v["xz_bytes"] and sha(b)==v["xz_sha256"] and sha((cache/name).read_bytes())==v["sha256"],"ORIGINAL_FILE:"+name)
        files["raw/"+name+".xz"]=b
    def add(n,obj):
        files[n]=(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode()
        (HERE/n).write_bytes(files[n])
    add("CARD.json",dict(run=HERE.name,parents={DAD.name:dadpin,TON.name:tonpin},method=read(DAD/"DAD_CARD.json")["frozen_parameter_source_sha256"],
        input_seal_sha256=sha(files["INPUT_SEAL.json"]),evidence_sha256=sha(files["EVIDENCE.json"]),
        query_counts={"normal":3334,"F1":3547,"F2":2765,"F3":5370},normal_components=1,rollback="strict zero numerical difference"))
    add("PACKAGE_MANIFEST.json",dict(run=HERE.name,files={k:sha(v) for k,v in sorted(files.items())}))
    target=PRIVATE/"package.tar.gz";tmp=target.with_suffix(".tmp")
    with tmp.open("wb") as fd,gzip.GzipFile(fileobj=fd,mode="wb",filename="",mtime=0) as gz,tarfile.open(fileobj=gz,mode="w") as tar:
        for n,b in sorted(files.items()):
            if n.endswith(".py"):compile(b,n,"exec")
            ti=tarfile.TarInfo(n);ti.size=len(b);ti.mode=0o700 if n.endswith(".slurm") else 0o600
            tar.addfile(ti,io.BytesIO(b))
    check(tmp.stat().st_size<5*1024**2,"SCOPED_RELAY_BOUND")
    tmp.replace(target)
    with tarfile.open(target,"r:gz") as tar:
        check(set(tar.getnames())==set(files) and all(tar.extractfile(k).read()==v for k,v in files.items()),"BUNDLE_READBACK")
    proof=dict(status="PASS",archive_sha256=sha(target.read_bytes()),archive_bytes=target.stat().st_size,
               manifest_sha256=sha(files["PACKAGE_MANIFEST.json"]),input_seal_sha256=sha(files["INPUT_SEAL.json"]),
               replay=read(HERE/"LOCAL_REPLAY.json"))
    (HERE/"LOCAL_VALIDATION.json").write_bytes((json.dumps(proof,indent=2)+"\n").encode())
    print("validated",proof["archive_bytes"],proof["archive_sha256"])


if __name__=="__main__":build()
