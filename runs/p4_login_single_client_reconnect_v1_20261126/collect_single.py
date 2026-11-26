"""Reuse the isolated login service with a single active client interface."""
from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import signal
import sys
import tempfile

from single_protocol import REFERENCE, STAGE, registration

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_login_calibration_v1_20261122"))
from capture import DISK_RESERVE, PORT, boot_id, isolate, launch_service, phase, process_start, save_json
from collect import DEVICE, ip
from sources import read


def capture(attempt,key,evidence):
    pin = read(evidence/"REGISTRATION.json")
    plan = pin["single_plan"]
    assert plan==registration()
    item, = (b for b in [plan["preflight"],*plan["formal"]] if b["key"]==key)
    instance = secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix=f"p4single-{instance}-") as temp, ExitStack() as stack:
        ctl = Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20),encoding="ascii")
        server,clients,endpoints = isolate(stack,f"p4sl-{instance[:8]}")
        assert [[x["ip"],x["mac"]] for x in endpoints]==pin["endpoints"]
        assert PORT==pin["server_port"] and os.uname().release==pin["kernel"]
        inactive = [idx for idx in range(1,4) if idx!=item["client"]]
        for idx in inactive:
            ip("-n",clients[idx-1],"link","set",DEVICE,"down")
        service,pid = launch_service(stack,server,attempt,ctl)
        meta = dict(service_instance=instance,service_pid=pid,service_start=process_start(pid),
                    collector_pid=os.getpid(),collector_start=process_start(os.getpid()),boot=boot_id(),
                    server_port=PORT,endpoints=endpoints,kernel=os.uname().release,
                    frozen_reference_source=REFERENCE,registered_batch=key,
                    active_client=item["client"],inactive_client_interfaces=inactive)
        save_json(attempt/"COLLECTOR_IDENTITY.json",meta)
        record = phase(attempt,STAGE,ctl,server,clients,item["schedule"],meta)
        assert service.poll() is None and record["remaining_bytes"]>DISK_RESERVE
    save_json(attempt/"COLLECTION_DONE.json",dict(status="PASS",service_instance=instance,namespaces_released=True))


def active(attempt):
    try:
        meta = read(attempt/"COLLECTOR_IDENTITY.json")
        start = process_start(meta["collector_pid"])
        return meta["boot"]==boot_id() and start is not None and start==meta["collector_start"]
    except (OSError,ValueError,KeyError,IndexError):
        return False


if __name__=="__main__":
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
    mode,attempt,*args = sys.argv[1:]
    if mode=="probe":
        sys.exit(0 if active(Path(attempt)) else 1)
    assert mode=="capture"
    capture(Path(attempt),args[0],Path(args[1]))
