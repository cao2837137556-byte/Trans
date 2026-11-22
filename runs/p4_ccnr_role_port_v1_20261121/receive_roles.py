"""Ship the sealed package over the existing session and accept only small signed results."""
from pathlib import Path
import hashlib
import http.client
import json
import os
import time

from transport_roles import channel, HERE, settings
from report_roles import paper


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    tmp=path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes((json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n").encode("utf8"))
    tmp.replace(path)


def state(stage,**kwargs):
    write(HERE/"LOCAL_PROGRESS.json",dict(stage=stage,updated_unix=time.time(),**kwargs))


def check(path,pin):
    assert path.is_file() and path.stat().st_size==pin["bytes"] and sha(path)==pin["sha256"],str(path)


def pull(relay,mode,remote,seal):
    man=relay.request("manifest-"+mode,timeout=15)
    if not man:
        return False
    dest=HERE/"received";dest.mkdir(exist_ok=True)
    for n,pin in man["files"].items():
        f=dest/n
        assert f.parent==dest and n==pin["file"] and n.endswith((".csv",".json",".md")) and 0<pin["bytes"]<32<<20
        if not f.is_file() or sha(f)!=pin["sha256"]:
            relay.request("file-"+mode+"-"+n,destination=(f,pin),timeout=95)
        check(f,pin)
    write(dest/"RETURN.json",man)
    stage=remote["chain"]["stage"]
    if stage=="COMPLETE":
        v=read(dest/"ACCEPTANCE.json")
        assert v==remote["acceptance"] and v["scope"]=="ROLE_PORT_FROZEN_V12_PAIRED" and v["main"]=="R2_U1"
        assert v["manifest_sha256"]==seal["manifest_sha256"]
        check(dest/"RESULTS_FOR_PAPER.md",v["paper"])
        assert (dest/"RESULTS_FOR_PAPER.md").read_bytes()==paper(dest).encode("utf8")
        for phase,j in v["jobs"].items():
            s=read(dest/f"SCHEDULER_{phase}.json")
            assert s["job_id"]==j and s["state"]=="COMPLETED"
            assert any(x.split("|")[:3]==[j,"COMPLETED","0:0"] for x in s["account"]["stdout"].splitlines())
        write(dest/"LOCAL_ACCEPTANCE.json",dict(status="PASS",jobs=v["jobs"],verified_files=len(man["files"]),
             return_sha256=sha(dest/"RETURN.json"),method_sha256=seal["method_sha256"],main="R2_U1"))
        stage="ACCEPTED"
    state(stage,remote=remote)
    return True


def run():
    seal=read(HERE/"LOCAL_SEAL.json")
    mode=f"r{seal['slot']}"
    package=HERE/".private/package.tar.gz";check(package,seal["package"])
    assert sha(HERE/"PACKAGE_MANIFEST.json")==seal["manifest_sha256"]
    api=channel.get_client();connect=api.transport();cfg=settings(seal)
    port=None;installed=False
    while True:
        try:
            ports=[port] if port else api.ssh_socks_ports()
            for p in ports:
                r=api.Relay(cfg,p,connect)
                try:
                    remote=r.request("state-"+mode,timeout=8)
                except (OSError,http.client.HTTPException):
                    continue
                port=p
                break
            else:
                state("CONNECTION_PAUSED" if installed else ("WAITING_TERMINAL" if ports else "WAITING_SSH"))
                port=None;time.sleep(12);continue
            if not remote["install"]:
                state("UPLOADING")
                v=r.request("install-"+mode,"POST",package.read_bytes(),{"X-SHA256":seal["package"]["sha256"]},timeout=95)
                assert v["run"]==seal["run"]
                remote=r.request("state-"+mode,timeout=15)
            v=remote["install"]
            assert v["run"]==seal["run"] and v["manifest_sha256"]==seal["manifest_sha256"]
            assert v["archive_sha256"]==seal["package"]["sha256"]
            if not installed:
                write(HERE/"INSTALL_READBACK.json",v)
            installed=True
            c=remote["chain"] or {}
            stage=c.get("stage","INSTALLED")
            if c.get("job_id"):
                write(HERE/"SUBMISSION_READBACK.json",remote)
            if remote.get("prep"):
                assert remote["prep"]["status"]=="PASS" and remote["prep"]["role_scope"]=="full"
                write(HERE/"ROLE_PREFLIGHT_READBACK.json",remote["prep"])
            state(stage,remote=remote)
            if stage in ("STOP","COMPLETE") and pull(r,mode,remote,seal):
                return
            time.sleep(10)
        except (OSError,http.client.HTTPException):
            port=None
            time.sleep(6)


if __name__=="__main__":
    try:
        run()
    except Exception as exc:
        state("LOCAL_STOP",error=str(exc) or repr(exc))
        raise
