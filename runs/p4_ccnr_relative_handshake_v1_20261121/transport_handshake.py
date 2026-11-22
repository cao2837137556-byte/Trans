"""Register a bounded receiver only for this experiment and isolated retries."""
import hashlib
import hmac
import json
from pathlib import Path
import shlex
import sys

HERE = Path(__file__).resolve().parent
RUN = HERE.name
PORT = 18935
TAG = ".p04_hrel21"
sys.path.insert(0, str(HERE.parent / "p4_password_aug_v1_20261120"))
from transport import channel

channel.HERE = HERE
channel.RUN = RUN
channel.PRIVATE = HERE / ".private"
channel.PORT = PORT
channel.TAG = TAG


def settings(seal):
    assert seal["run"] == f"{RUN}_r{seal['slot']}"
    return channel.config()


def make_command():
    relay_source = channel.OLD / "q12_recovery_relay.py"
    pin = hashlib.sha256(relay_source.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
    code = (
        "from pathlib import Path as P; import sys,hmac,relay as r; "
        f"n={RUN!r}; s=P(sys.argv[1]); "
        f"(s/'token').write_text(hmac.digest((P({channel.OLD_STAGE!r})/'token').read_bytes().strip(),n.encode(),'sha256').hex()); "
        "r.RUNS={f'r{i}':f'{n}_r{i}' for i in range(5)}; r.main()"
    )
    cmd = (
        f"cd {channel.PROJECT}/runs && umask 077 && mkdir -p {TAG} && "
        f"echo '{pin}  {channel.OLD_STAGE}/relay.py' | sha256sum -c --status && "
        f"PYTHONPATH={channel.OLD_STAGE} nohup flock -n {TAG}/lock {channel.PYTHON} -B -c {shlex.quote(code)} "
        f"{TAG} {PORT} </dev/null >>{TAG}/relay.log 2>&1 &"
    )
    channel.PRIVATE.mkdir(exist_ok=True)
    (channel.PRIVATE / "START.txt").write_bytes((cmd + "\n").encode("ascii"))


if __name__=="__main__":
    make_command()
