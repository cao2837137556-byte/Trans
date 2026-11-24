"""Use the established isolated WSL service to capture a registered normal batch."""
from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import signal
import sys
import tempfile

from protocol import registration
from capture import DISK_RESERVE, PORT, boot_id, isolate, launch_service, phase, process_start, save_json
from sources import identity, read


def collect(root,key,source):
    pin=read(source/"INPUTS.json")
    item=pin["batches"][key]
    assert item==registration()[key]
    stage="holdout" if item["stage"]=="preflight" else item["stage"]
    if item["stage"]=="holdout":
        release=read(source/"THRESHOLD_SEAL.json")
        assert release["status"]=="PASS"
        assert identity(source/"THRESHOLDS.json")==release["thresholds"]
        assert release["input_manifest"]==identity(source/"INPUTS.json")
    instance=secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix=f"p4rank5-{instance}-") as temp, ExitStack() as stack:
        ctl=Path(temp)
        (ctl/"credential").write_text(secrets.token_urlsafe(20))
        server,clients,endpoints=isolate(stack,f"p4r5-{instance[:8]}")
        assert [[x["ip"],x["mac"]] for x in endpoints]==pin["endpoints"]
        assert PORT==pin["server_port"] and os.uname().release==pin["kernel"]
        service,pid=launch_service(stack,server,root,ctl)
        meta=dict(service_instance=instance,service_pid=pid,service_start=process_start(pid),
                  collector_pid=os.getpid(),collector_start=process_start(os.getpid()),boot=boot_id(),
                  server_port=PORT,endpoints=endpoints,kernel=os.uname().release,
                  frozen_reference_source=pin["reference_archive"],registered_batch=key)
        save_json(root/"COLLECTOR_IDENTITY.json",meta)
        trace=phase(root,stage,ctl,server,clients,item["schedule"],meta)
        assert service.poll() is None and trace["remaining_bytes"]>DISK_RESERVE
    save_json(root/"COLLECTION_DONE.json",dict(status="PASS",service_instance=instance,namespaces_released=True))


def probe(root):
    try:
        x=read(root/"COLLECTOR_IDENTITY.json")
        pid=x["collector_pid"]
        return boot_id()==x["boot"] and process_start(pid)==x["collector_start"]
    except (OSError,ValueError,KeyError,IndexError):
        return False


if __name__=="__main__":
    signal.signal(signal.SIGTERM,lambda *_:sys.exit(143))
    path=Path(sys.argv[2])
    if sys.argv[1]=="probe":
        sys.exit(0 if probe(path) else 1)
    assert sys.argv[1]=="capture"
    collect(path,sys.argv[3],Path(sys.argv[4]))
