"""Use the established SSH tunnel with a separate DAD receiver."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.append(str(HERE.parent / "p4_dual_component_mean_v1_20261117"))
import delivery as channel

channel.HERE = HERE
channel.RUN = HERE.name
channel.PRIVATE = HERE / ".private"
channel.PORT = 18900
channel.TAG = ".p04_dad19"


def setup():
    channel.PRIVATE.mkdir(exist_ok=True)
    (channel.PRIVATE / "START.txt").write_bytes((channel.start_command() + "\n").encode("ascii"))


if __name__ == "__main__":
    setup()
