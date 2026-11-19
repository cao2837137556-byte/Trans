"""Use the previous deployment's authenticated SOCKS transport in a new run scope."""

import importlib.util
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
PREVIOUS = HERE.parent / "p4_dual_component_mean_v1_20261117"
sys.path.append(str(PREVIOUS))
spec = importlib.util.spec_from_file_location("accepted_dual_transport", PREVIOUS / "delivery.py")
transport = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transport)
transport.HERE = HERE
transport.RUN = HERE.name
transport.PRIVATE = HERE / ".private"
transport.TAG = ".p04_v12_next18"
transport.PORT = 18897


def save(path, value):
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_bytes((json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode())
    temp.replace(path)


transport.save = save
if __name__ == "__main__":
    transport.PRIVATE.mkdir(exist_ok=True)
    (transport.PRIVATE / "START.txt").write_bytes((transport.start_command() + "\n").encode("ascii"))
