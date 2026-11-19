"""Local transport through the user's existing SSH SOCKS session."""

import hmac
from hashlib import sha256
import shlex
import sys

from common_ton import HERE, RUN, read

OLD = HERE.parent / "unified_reference_bank_k8192_v1_20261113"
sys.path.append(str(OLD))
from motion_transfer import PROJECT, PYTHON, get_client as get_client

PORT = 18898
INPUT_PORT = 18899
STAGE = ".p04_tonpw18"
PREVIOUS = ".p04_q12_20261115_relay"


def config(port=PORT):
    key = read(OLD / ".private/Q12_CONNECTION.json")["token"].encode()
    return dict(port=port, token=hmac.digest(key, RUN.encode(), "sha256").hex())


def prepare():
    pin = sha256((OLD / "q12_recovery_relay.py").read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    # Report just the files in the experiment's registered input list.
    sources = read(HERE / "SCOPED_INPUTS.json")["sources"]
    candidates = {k: v["paths"][:2] for k, v in sources.items()}
    from base64 import b64encode
    import json, zlib

    lookup = b64encode(zlib.compress(json.dumps(candidates).encode(), 9)).decode()
    code = (
        "from pathlib import Path as P; import base64,zlib,json,sys,hmac,relay as r; "
        f'd=P(sys.argv[1]); n="{RUN}"; '
        f'(d/"token").write_text(hmac.digest((P("{PREVIOUS}")/"token").read_bytes().strip(),n.encode(),"sha256").hex()); '
        f'paths=json.loads(zlib.decompress(base64.b64decode("{lookup}"))); '
        "r.probe=lambda runs:{k:[dict(path=i,bytes=(runs.parent/i).stat().st_size) for i in paths[k] "
        'if (runs.parent/i).is_file()] for k in paths}; r.RUNS={"ton":n}; r.main()'
    )
    cmd = (
        f"cd {PROJECT}/runs && umask 077 && mkdir -p {STAGE} && "
        f'echo "{pin}  {PREVIOUS}/relay.py" | sha256sum -c --status && '
        f"PYTHONPATH={PREVIOUS} nohup flock -n {STAGE}/lock {PYTHON} -B -c {shlex.quote(code)} "
        f"{STAGE} {PORT} </dev/null >>{STAGE}/relay.log 2>&1 &"
    )
    (HERE / ".private/START.txt").write_bytes((cmd + "\n").encode("ascii"))


if __name__ == "__main__":
    prepare()
