"""Use the authenticated password-experiment receiver and validate the small return on D."""
import http.client
import sys
import time
from shared import HERE,artifact,check,read,write,sha
from report import paper

sys.path.insert(0,str(HERE.parent/"p4_password_aug_v1_20261120"))
from transport import channel
from repair_transport import PORT


def state(stage,**extra):
    write(HERE/"LOCAL_PROGRESS.json",dict(stage=stage,updated_unix=time.time(),**extra))


def run():
    seal=read(HERE/"LOCAL_SEAL.json")
    pkg=check(HERE/".private/package.tar.gz",seal["package"])
    mode="r"+str(seal["slot"])
    api=channel.get_client();connect=api.transport();cfg=dict(channel.config(),port=PORT)
    current=None
    while True:
        try:
            ports=[current] if current else api.ssh_socks_ports()
            for p in ports:
                relay=api.Relay(cfg,p,connect)
                try: remote=relay.request("state-"+mode,timeout=10)
                except (OSError,http.client.HTTPException):continue
                current=p
                break
            else:
                current=None;state("CONNECTION_PAUSED");time.sleep(12);continue
            if not remote["install"]:
                state("UPLOADING")
                reply=relay.request("install-"+mode,"POST",pkg.read_bytes(),{"X-SHA256":seal["package"]["sha256"]},timeout=100)
                assert reply["run"]==seal["run"]
                remote=relay.request("state-"+mode)
            receipt=remote["install"]
            assert receipt["run"]==seal["run"] and receipt["manifest_sha256"]==seal["manifest"]
            assert receipt["archive_sha256"]==seal["package"]["sha256"]
            if not (HERE/"INSTALL_READBACK.json").exists():write(HERE/"INSTALL_READBACK.json",receipt)
            c=remote["chain"] or {};stage=c.get("stage","INSTALLED")
            state(stage,remote=remote)
            if stage in ("COMPLETE","STOP"):
                man=relay.request("manifest-"+mode)
                if not man:time.sleep(4);continue
                dest=HERE/"received";dest.mkdir(exist_ok=True)
                for n,s in man["files"].items():
                    assert (dest/n).parent==dest and s["file"]==n and n.endswith((".json",".csv",".md")) and 0<s["bytes"]<32<<20
                    path=dest/n
                    if not path.exists() or sha(path)!=s["sha256"]:
                        relay.request("file-"+mode+"-"+n,destination=(path,s),timeout=90)
                    check(path,s)
                write(dest/"RETURN.json",man)
                if stage=="COMPLETE":
                    a=read(dest/"ACCEPTANCE.json")
                    assert a==remote["acceptance"] and a["manifest_sha"]==seal["manifest"] and a["scope"]=="NO_TRAINING_PAIRED_SCALE_REPLAY"
                    for ph,j in a["jobs"].items():
                        sched=read(dest/f"SCHEDULER_{ph}.json")
                        assert sched["job_id"]==j and sched["state"]=="COMPLETED"
                        assert any(r.split("|")[:3]==[j,"COMPLETED","0:0"] for r in sched["account"]["stdout"].splitlines())
                    assert (dest/"RESULTS_FOR_PAPER.md").read_bytes()==paper(dest).encode("utf8")
                    write(dest/"LOCAL_ACCEPTANCE.json",dict(status="PASS",jobs=a["jobs"],verified_files=len(man["files"]),
                          return_sha=sha(dest/"RETURN.json")))
                    stage="ACCEPTED"
                state(stage,remote=remote);return
            time.sleep(10)
        except (OSError,http.client.HTTPException):
            current=None;time.sleep(8)


if __name__=="__main__":
    try:run()
    except Exception as e:
        state("LOCAL_STOP",error=str(e) or repr(e))
        raise
