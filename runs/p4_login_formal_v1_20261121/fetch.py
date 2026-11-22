"""Read back the tiny frozen assets through the operator-established SSH tunnel."""
import gzip
import http.client
import io
import json
from pathlib import Path
import sys
import tarfile
import time

HERE = Path(__file__).resolve().parent
PILOT = HERE.parent/"p4_login_pilot_v1_20261121"
sys.path.insert(0, str(PILOT))
from audit import identity, read, save, sha
sys.path.insert(0, str(HERE.parent/"p4_password_aug_v1_20261120"))
from transport import channel

channel.HERE = HERE
channel.RUN = HERE.name
channel.PRIVATE = HERE/".private"
channel.PORT = 18936
channel.TAG = ".p04_login21"

NAMES = ("INSTALL.json","ACCEPTANCE.json","ATTACK_FIXTURE.npz","head_27.npz","head_127.npz","head_227.npz")


def small_receipt(directory,n):
    pin = read(directory/"RETURN.json")["files"][n]
    assert all(identity(directory/n)[k]==pin[k] for k in ("bytes","sha256"))
    return read(directory/n)


def package(slot):
    assert 0<=slot<3
    history = HERE.parent/"p4_ccnr_history60_v1_20261120"
    received = history/"received"
    h = small_receipt(received,"EDGE_PASSWORD_INPUT.json")
    assert small_receipt(received,"ACCEPTANCE.json")["scope"]=="FROZEN_V12_HISTORY60_REPLAY"
    other = HERE.parent/"p4_ccnr_relative_handshake_v1_20261121/received"
    accepted = small_receipt(other,"ACCEPTANCE.json")
    assert accepted["status"]=="PASS" and accepted["scope"]=="FROZEN_V12_DEVICE_LOCAL_HANDSHAKES"
    decision = small_receipt(other,"HPC_ARRAY_SHA.json")["pools"]["EDGE_PASSWORD"]["decisions"]
    source = read(history/"INPUT_PINS.json")
    frozen = read(HERE.parent/"p4_ton_password_frozen_v12_20261118/FROZEN.json")
    pin = dict(heads={str(s):frozen["extra_pins"][f"head_{s}"] for s in (27,127,227)},
               method=frozen["method"],
               history_run=small_receipt(received,"INSTALL.json")["run"], history=h,
               decision_run=small_receipt(other,"INSTALL.json")["run"], decision=decision,
               edge_source_run="p4_password_aug_v1_20261120_r1", edge_inputs=source["edge_pw"]["inputs"],
               edge_raw_sha256=source["edge_pw"]["raw"]["sha256"], edge_shards=source["scale"]["edge_shards"])
    files={"launch.py":(HERE/"archive_export.py").read_bytes().replace(b"\r\n",b"\n"),
           "ARCHIVE_PINS.json":json.dumps(pin,sort_keys=True).encode("ascii")}
    compile(files["launch.py"],"launch.py","exec")
    manifest=dict(run=f"{HERE.name}_r{slot}", files={n:sha(d) for n,d in files.items()})
    files["PACKAGE_MANIFEST.json"]=json.dumps(manifest,sort_keys=True).encode("ascii")
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode="w") as archive:
        for n,d in sorted(files.items()):
            meta=tarfile.TarInfo(n)
            meta.size=len(d)
            meta.mode=0o600
            archive.addfile(meta,io.BytesIO(d))
    return gzip.compress(buf.getvalue(),mtime=0),manifest["run"],sha(files["PACKAGE_MANIFEST.json"]),pin


def download(out, slot=0):
    dest=out/"frozen_quick_check_assets"
    dest.mkdir(exist_ok=True)
    bundle,run,manifest,pins=package(slot)
    if (dest/"LOCAL_RECEIPT.json").is_file():
        receipt=read(dest/"LOCAL_RECEIPT.json")
        assert set(receipt["files"])==set(NAMES) and receipt["manifest_sha256"]==manifest
        assert all(identity(dest/n)==v for n,v in receipt["files"].items())
        return dest
    api=channel.get_client()
    connect=api.transport()
    settings=channel.config()
    mode=f"r{slot}"
    while True:
        for p in api.ssh_socks_ports():
            relay=api.Relay(settings,p,connect)
            try:
                remote=relay.request("state-"+mode,timeout=4)
            except (OSError,http.client.HTTPException):
                continue
            if not remote["install"]:
                install=relay.request("install-"+mode,"POST",bundle,{"X-SHA256":sha(bundle)},timeout=45)
            else:
                install=remote["install"]
            assert install["run"]==run and install["manifest_sha256"]==manifest and install["archive_sha256"]==sha(bundle)
            save(out/"EXPORT_PROGRESS.json",dict(stage="EXPORTING_FROZEN_FIXTURE",installed=install))
            while True:
                try:
                    remote=relay.request("state-"+mode,timeout=10)
                    phase=(remote["chain"] or {}).get("stage")
                    if phase=="STOP":
                        raise RuntimeError(remote["chain"]["error"])
                    if phase!="COMPLETE":
                        time.sleep(4)
                        continue
                    reply=relay.request("manifest-"+mode,timeout=12)["files"]
                    assert set(reply)==set(NAMES)
                    for name,v in reply.items():
                        assert v["file"]==name and 0<v["bytes"]<2**21
                        path=dest/name
                        if not path.is_file() or identity(path)["sha256"]!=v["sha256"]:
                            relay.request("file-"+mode+"-"+name,destination=(path,v),timeout=45)
                        assert all(identity(path)[k]==v[k] for k in ("bytes","sha256"))
                    for seed,v in pins["heads"].items():
                        assert identity(dest/f"head_{seed}.npz")["sha256"]==v["sha256"]
                    assert read(dest/"ACCEPTANCE.json")["status"]=="PASS"
                    save(dest/"LOCAL_RECEIPT.json",dict(manifest_sha256=manifest,
                         files={n:identity(dest/n) for n in NAMES},run=run))
                    save(out/"EXPORT_PROGRESS.json",dict(stage="FROZEN_FIXTURE_READY",run=run))
                    return dest
                except (OSError,http.client.HTTPException):
                    break
        save(out/"EXPORT_PROGRESS.json",dict(stage="WAITING_TERMINAL"))
        time.sleep(7)


if __name__=="__main__":
    download(Path(sys.argv[1]),int(sys.argv[2]) if len(sys.argv)>2 else 0)
