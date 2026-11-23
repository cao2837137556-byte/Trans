"""Capture only the scheduled legitimate login sessions in a fresh namespace."""

from contextlib import ExitStack
from pathlib import Path
import os
import secrets
import signal
import sys
import tempfile

import design
from capture import DISK_RESERVE, PORT, boot_id, isolate, launch_service, phase, process_start, save_json
from sources import read


def collect(root, batch, contract):
    plan = contract["schedules"][batch]
    assert plan == design.schedule(batch)
    assert not (root / "holdout").exists()
    instance = secrets.token_hex(8)
    with tempfile.TemporaryDirectory(prefix=f"p4holdout-{instance}-") as temp, ExitStack() as stack:
        control = Path(temp)
        (control / "credential").write_text(secrets.token_urlsafe(20))
        server, clients, endpoints = isolate(stack, f"p4lh-{instance[:8]}")
        assert [[x["ip"], x["mac"]] for x in endpoints] == contract["endpoints"]
        assert PORT == contract["server_port"]
        assert os.uname().release == contract["kernel"]
        service, pid = launch_service(stack, server, root, control)
        meta = dict(service_instance=instance, service_pid=pid, service_start=process_start(pid),
                    collector_pid=os.getpid(), collector_start=process_start(os.getpid()),
                    boot=boot_id(), server_port=PORT, endpoints=endpoints,
                    kernel=os.uname().release, frozen_reference_source=contract["reference_archive"])
        trace = phase(root, "holdout", control, server, clients, plan, meta)
        assert service.poll() is None and trace["remaining_bytes"] > DISK_RESERVE
    save_json(root / "COLLECTION_DONE.json",
              dict(status="PASS", service_instance=instance, namespaces_released=True))


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))
    collect(Path(sys.argv[1]), int(sys.argv[2]), read(Path(sys.argv[3])))
