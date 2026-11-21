"""Deliver over the user-established connection and verify small results on D."""
import http.client
import time

from history_common import HERE, RUN, artifact, check, read, sha, write
from report_history import paper
from transport_history import channel


def state(stage,**extra):
    write(HERE/"LOCAL_PROGRESS.json",dict(stage=stage,updated_unix=time.time(),**extra))


def receive(relay,remote,seal,mode):
    man=relay.request("manifest-"+mode,timeout=20)
    if not man:
        return False
    dest=HERE/"received";dest.mkdir(exist_ok=True)
    for n,pin in man["files"].items():
        path=dest/n
        assert path.parent==dest and pin["file"]==n and n.endswith((".json",".csv",".md")) and 0<pin["bytes"]<32<<20
        if not path.is_file() or sha(path)!=pin["sha256"]:
            relay.request("file-"+mode+"-"+n,destination=(path,pin),timeout=90)
        check(path,pin)
    write(dest/"RETURN.json",man)
    stage=remote["chain"]["stage"]
    if stage=="COMPLETE":
        cert=read(dest/"ACCEPTANCE.json")
        assert cert==remote["acceptance"] and cert["scope"]=="FROZEN_V12_HISTORY60_REPLAY"
        assert cert["manifest_sha256"]==seal["manifest"]
        result=read(dest/"RESULT.json")
        assert cert["gate"]==result["advance"] and result["baseline_cells"]==seal["baseline_views"]
        check(dest/"RESULTS_FOR_PAPER.md",cert["paper"])
        assert (dest/"RESULTS_FOR_PAPER.md").read_bytes()==paper(dest).encode("utf8")
        for phase,j in cert["jobs"].items():
            s=read(dest/f"SCHEDULER_{phase}.json")
            assert s["job_id"]==j and s["state"]=="COMPLETED"
            assert any(x.split("|")[:3]==[j,"COMPLETED","0:0"] for x in s["account"]["stdout"].splitlines())
        write(dest/"LOCAL_ACCEPTANCE.json",dict(status="PASS",jobs=cert["jobs"],gate=cert["gate"],
              rules_sha256=seal["rule_sha256"],return_sha256=sha(dest/"RETURN.json"),verified_files=len(man["files"])))
        stage="ACCEPTED"
    state(stage,remote=remote)
    return True


def run():
    local=read(HERE/"LOCAL_SEAL.json")
    package=check(HERE/".private/package.tar.gz",local["package"])
    assert sha(HERE/"PACKAGE_MANIFEST.json")==local["manifest"]
    api=channel.get_client();connect=api.transport();cfg=channel.config()
    attempt=local.get("attempt",0)
    mode="dual" if not attempt else f"r{attempt}"
    if attempt:
        from repair_history import PORT
        cfg=dict(cfg,port=PORT)
    run_name=local.get("run",RUN)
    current=None;installed=False
    while True:
        try:
            ports=[current] if current else api.ssh_socks_ports()
            for p in ports:
                relay=api.Relay(cfg,p,connect)
                try:
                    remote=relay.request("state-"+mode,timeout=8)
                except (OSError,http.client.HTTPException):
                    continue
                current=p
                break
            else:
                current=None
                state("CONNECTION_PAUSED" if installed else ("WAITING_TERMINAL" if ports else "WAITING_SSH"))
                time.sleep(10)
                continue
            if not remote["install"]:
                state("UPLOADING")
                reply=relay.request("install-"+mode,"POST",package.read_bytes(),{"X-SHA256":local["package"]["sha256"]},timeout=100)
                assert reply["run"]==run_name
                remote=relay.request("state-"+mode,timeout=15)
            seal=remote["install"]
            assert seal["run"]==run_name and seal["manifest_sha256"]==local["manifest"]
            assert seal["archive_sha256"]==local["package"]["sha256"]
            if not installed:
                write(HERE/"INSTALL_READBACK.json",seal)
            installed=True
            stage=(remote["chain"] or {}).get("stage","INSTALLED")
            state(stage,remote=remote)
            if stage in ("COMPLETE","STOP") and receive(relay,remote,local,mode):
                break
            time.sleep(10)
        except (OSError,http.client.HTTPException):
            current=None
            time.sleep(6)


if __name__=="__main__":
    try:
        run()
    except Exception as exc:
        state("LOCAL_STOP",error=str(exc) or repr(exc))
        raise
