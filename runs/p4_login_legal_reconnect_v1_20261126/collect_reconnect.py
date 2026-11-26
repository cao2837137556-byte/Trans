"""Capture only successful setup and reconnect POSTs on the existing isolated service."""
from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import signal
import sys
import tempfile

from protocol_reconnect import REFERENCE, STAGE, registration

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent/"p4_login_calibration_v1_20261122"))
from capture import DISK_RESERVE, PORT, boot_id, isolate, launch_service, phase, process_start, save_json
from sources import read


def collect(root, key, evidence):
    pin = read(evidence/"REGISTRATION.json")
    assert pin["plan"]==registration()
    item, = (b for b in [pin["plan"]["preflight"], *pin["plan"]["formal"]] if b["key"]==key)
    instance = secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix=f"p4reconnect-{instance}-") as temp, ExitStack() as stack:
        ctl = Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20), encoding="ascii")
        server, clients, endpoints = isolate(stack, f"p4lr-{instance[:8]}")
        assert [[x["ip"],x["mac"]] for x in endpoints]==pin["endpoints"]
        assert PORT==pin["server_port"] and os.uname().release==pin["kernel"]
        service, pid = launch_service(stack,server,root,ctl)
        meta = dict(service_instance=instance, service_pid=pid, service_start=process_start(pid),
                    collector_pid=os.getpid(), collector_start=process_start(os.getpid()), boot=boot_id(),
                    server_port=PORT, endpoints=endpoints, kernel=os.uname().release,
                    frozen_reference_source=REFERENCE, registered_batch=key)
        save_json(root/"COLLECTOR_IDENTITY.json",meta)
        trace = phase(root,STAGE,ctl,server,clients,item["schedule"],meta)
        assert service.poll() is None and trace["remaining_bytes"]>DISK_RESERVE
    save_json(root/"COLLECTION_DONE.json",dict(status="PASS",service_instance=instance,namespaces_released=True))


def active(root):
    try:
        meta = read(root/"COLLECTOR_IDENTITY.json")
        collector = process_start(meta["collector_pid"])
        return meta["boot"]==boot_id() and collector is not None and collector==meta["collector_start"]
    except (OSError,ValueError,KeyError,IndexError):
        return False


if __name__=="__main__":
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
    mode, root, *args = sys.argv[1:]
    root = Path(root)
    if mode=="probe":
        sys.exit(0 if active(root) else 1)
    assert mode=="capture"
    collect(root,args[0],Path(args[1]))
