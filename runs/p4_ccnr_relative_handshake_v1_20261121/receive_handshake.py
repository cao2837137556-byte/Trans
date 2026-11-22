"""Upload once and verify only the experiment's manifested small results."""
import hashlib
import http.client
import json
import os
import time

from report_handshake import paper
from transport_handshake import HERE, channel, settings


def read(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes((json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False)+"\n").encode("utf8"))
    for retry in range(5):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            if retry == 4:
                raise
            time.sleep(.08)


def state(stage, **data):
    write(HERE/"LOCAL_PROGRESS.json", dict(stage=stage, updated_unix=time.time(), **data))


def verify(path, pin):
    assert path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], str(path)


def pull(relay, mode, remote, seal):
    manifest = relay.request("manifest-"+mode, timeout=15)
    if not manifest:
        return False
    stage = remote["chain"]["stage"]
    folder = HERE/"received" if stage == "COMPLETE" else HERE/"attempts"/seal["run"]
    folder.mkdir(parents=True, exist_ok=True)
    for n, pin in manifest["files"].items():
        f = folder/n
        assert f.parent == folder and n == pin["file"] and f.suffix in (".csv",".json",".md")
        assert 0 < pin["bytes"] < 32 << 20
        if not f.is_file() or sha(f) != pin["sha256"]:
            relay.request("file-"+mode+"-"+n, destination=(f,pin), timeout=95)
        verify(f, pin)
    write(folder/"RETURN.json", manifest)
    if stage == "COMPLETE":
        a = read(folder/"ACCEPTANCE.json")
        assert a == remote["acceptance"] and a["scope"] == "FROZEN_V12_DEVICE_LOCAL_HANDSHAKES"
        assert a["status"] == "PASS" and a["manifest_sha256"] == seal["manifest_sha256"]
        verify(folder/"PREP_RECEIPT.json", a["preflight"])
        verify(folder/"RESULTS_FOR_PAPER.md", a["paper"])
        assert (folder/"RESULTS_FOR_PAPER.md").read_bytes() == paper(folder).encode("utf8")
        for phase,j in a["jobs"].items():
            s = read(folder/f"SCHEDULER_{phase}.json")
            assert s["job_id"] == j and s["state"] == "COMPLETED"
            assert any(line.split("|")[:3] == [j,"COMPLETED","0:0"] for line in s["account"]["stdout"].splitlines())
        (folder/"SHA256SUMS").write_bytes("".join(f"{v['sha256']}  {n}\n" for n,v in manifest["files"].items()).encode("ascii"))
        write(folder/"LOCAL_ACCEPTANCE.json", dict(status="PASS", jobs=a["jobs"], verified_files=len(manifest["files"]),
              return_sha256=sha(folder/"RETURN.json"), method_sha256=seal["method_sha256"]))
        stage = "ACCEPTED"
    state(stage, remote=remote)
    return True


def run():
    seal = read(HERE/"LOCAL_SEAL.json")
    mode = f"r{seal['slot']}"
    package = HERE/".private/package.tar.gz"
    verify(package, seal["archive"])
    assert sha(HERE/"PACKAGE_MANIFEST.json") == seal["manifest_sha256"]
    api = channel.get_client()
    connect = api.transport()
    cfg = settings(seal)
    port, installed = None, False
    while True:
        try:
            ports = [port] if port else api.ssh_socks_ports()
            for p in ports:
                relay = api.Relay(cfg, p, connect)
                try:
                    remote = relay.request("state-"+mode, timeout=8)
                except (OSError, http.client.HTTPException):
                    continue
                port = p
                break
            else:
                state("CONNECTION_PAUSED" if installed else ("WAITING_TERMINAL" if ports else "WAITING_SSH"))
                port = None
                time.sleep(10)
                continue
            if not remote["install"]:
                state("UPLOADING")
                v = relay.request("install-"+mode,"POST",package.read_bytes(),{"X-SHA256":seal["archive"]["sha256"]},timeout=95)
                assert v["run"] == seal["run"]
                remote = relay.request("state-"+mode, timeout=15)
            v = remote["install"]
            assert v["run"] == seal["run"] and v["manifest_sha256"] == seal["manifest_sha256"]
            assert v["archive_sha256"] == seal["archive"]["sha256"]
            if not installed:
                write(HERE/"INSTALL_READBACK.json",v)
            installed = True
            chain = remote.get("chain") or {}
            stage = chain.get("stage","INSTALLED")
            if chain.get("job_id") or chain.get("jobs"):
                write(HERE/"SUBMISSION_READBACK.json", remote)
            if remote.get("prep"):
                assert remote["prep"]["status"] == "PASS" and remote["prep"]["experiment"] == HERE.name
                write(HERE/"PREFLIGHT_READBACK.json", remote["prep"])
            state(stage, remote=remote)
            if stage in ("STOP","COMPLETE") and pull(relay,mode,remote,seal):
                return
            time.sleep(8)
        except (OSError,http.client.HTTPException):
            port = None
            time.sleep(6)


if __name__ == "__main__":
    try:
        run()
    except Exception as exc:
        state("LOCAL_STOP", error=str(exc) or repr(exc))
        raise
