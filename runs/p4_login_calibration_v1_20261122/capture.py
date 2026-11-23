"""Capture calibration and holdout on one isolated WSL service."""
from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback

from sources import HERE, identity, read
from collect_formal import (
    DISK_RESERVE, NS, PORT, SERVER, FreeBudget, LoginServer, LoginHandler, isolate, phase,
    process_start, boot_id, publish_progress, save_json,
)
from plans import normal_plan


class NormalBudget:
    def __init__(self,out,control):
        self.out=out
        self.control=control

    def append(self,name,record):
        stage=(self.control/"phase").read_text()
        assert stage in ("calibration","holdout")
        return FreeBudget(self.out/stage,self.control).append(name,record)


def serve(out,ctl):
    with LoginServer((SERVER,PORT),LoginHandler) as server:
        server.password=(ctl/"credential").read_text()
        server.budget=NormalBudget(out,ctl)
        (ctl/"ready").write_text(str(os.getpid()))
        server.serve_forever()


def launch_service(stack,server,out,ctl):
    p=subprocess.Popen(["ip","netns","exec",server,sys.executable,"-B",str(HERE/"capture.py"),
                        "serve",str(out),str(ctl)])
    def stop():
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=2)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=2)
    stack.callback(stop)
    for _ in range(100):
        if (ctl/"ready").is_file():
            return p,int((ctl/"ready").read_text())
        assert p.poll() is None
        time.sleep(.025)
    raise RuntimeError("Login service did not publish its ready marker.")


def keeper(out):
    try:
        ids=read(out/"COLLECTOR_IDENTITY.json")
        cal=read(out/"calibration/CAPTURE.json")
        addr=cal["endpoints"][0]
        pid=ids["service_pid"]
        expected=f"p4lc-{ids['instance'][:8]}-srv"
        return (ids["boot"]==boot_id() and ids["instance"]==cal["service_instance"]
                and pid==cal["service_pid"] and addr["netns"]==expected
                and os.path.samefile(f"/proc/{pid}/ns/net",Path("/run/netns")/expected)
                and ids["collector_start"]==process_start(ids["collector_pid"])
                and ids["service_start"]==process_start(pid))
    except (OSError,ValueError,KeyError,IndexError):
        return False


def await_thresholds(out,service,meta,step):
    ready=out/"CALIBRATION_READY.json"
    while True:
        if service.poll() is not None:
            raise RuntimeError("The WSL login service exited before holdout.")
        if shutil.disk_usage(out).free<=DISK_RESERVE:
            raise RuntimeError("D: reached its reserve during calibration.")
        if ready.is_file() and time.time_ns()>step["capture"]["last_frame_ns"]+60*NS:
            r=read(ready)
            assert r["status"]=="PASS" and r["service_instance"]==meta["service_instance"]
            assert r["capture_receipt"]==identity(out/"calibration/CAPTURE.json")
            assert r["thresholds"]==identity(out/"THRESHOLDS.json")
            return
        publish_progress(out,stage="THRESHOLD_CALIBRATION",service_instance=meta["service_instance"],
                         service_pid=meta["service_pid"])
        time.sleep(1.)


def main(out):
    pre=read(out/"PREFLIGHT.json")
    assert pre["status"]=="PASS" and shutil.disk_usage(out).free>DISK_RESERVE
    instance=secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix="p4cal-"+instance+"-") as temp, ExitStack() as stack:
        ctl=Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20))
        server,clients,endpoints=isolate(stack,"p4lc-"+instance[:8])
        for k in ("ip","mac"):
            assert endpoints[0][k]==pre["service_endpoint"][k]
        assert PORT==pre["server_port"]
        service,pid=launch_service(stack,server,out,ctl)
        meta=dict(service_instance=instance,service_pid=pid,server_port=PORT,
                  endpoints=endpoints,kernel=os.uname().release,frozen_reference_source=pre["archive"])
        save_json(out/"COLLECTOR_IDENTITY.json",dict(boot=boot_id(),instance=instance,
                  collector_pid=os.getpid(),collector_start=process_start(os.getpid()),
                  service_pid=pid,service_start=process_start(pid)))
        initial=phase(out,"calibration",ctl,server,clients,normal_plan("calibration"),meta)
        await_thresholds(out,service,meta,initial)
        final=phase(out,"holdout",ctl,server,clients,normal_plan("holdout"),meta)
        assert final["capture"]["first_qualifying_ns"]>initial["capture"]["last_frame_ns"]+60*NS
    save_json(out/"COLLECTION_DONE.json",dict(status="PASS",service_instance=instance,namespaces_released=True))


if __name__=="__main__":
    op=sys.argv[1]
    out=Path(sys.argv[2])
    if op=="serve":
        serve(out,Path(sys.argv[3]))
    elif op=="probe":
        sys.exit(0 if keeper(out) else 1)
    else:
        assert op=="run"
        signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
        try:
            main(out)
        except Exception as exc:
            save_json(out/"COLLECTION_FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
            raise
