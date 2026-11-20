"""Freeze the accepted cache paths and checksums; ship only code and reference receipts."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
TON = RUNS / "p4_ton_password_frozen_v12_20261118"
DUAL = RUNS / "p4_dual_component_mean_v1_20261117"
DOC = RUNS / "mainline_docs/collab/20261119_paper04_ton_lambda_connection_replay_handoff_codex.md"
PRIVATE = HERE / ".private"
SRC = ("connection_tables.py", "result_checks.py", "cached_replay.py", "launch.py")


def hexdigest(b):
    return hashlib.sha256(b).hexdigest()


def norm(p):
    return p.read_bytes().replace(b"\r\n", b"\n")


def read(p):
    return json.loads(p.read_bytes())


def encode(o):
    return (json.dumps(o, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def build():
    src = TON / "received"
    man = read(src / "RETURN.json")["files"]
    acc = read(src / "ACCEPTANCE.json")
    assert acc["status"] == "PASS" and acc["jobs"]["evaluate"] == "185491"
    names = [
        "SCIENCE.json",
        "RAW_INFERENCE.json",
        "HPC_ARTIFACT_SHA.json",
        "RAW_TARGETS.csv",
        "CCNR_PAIRED.csv",
        "ACCEPTANCE.json",
    ]
    for n in names:
        assert hexdigest((src / n).read_bytes()) == man[n]["sha256"]
    assert acc["science"] == man["SCIENCE.json"] and acc["arrays"] == man["HPC_ARTIFACT_SHA.json"]
    old = read(TON / "PACKAGE_MANIFEST.json")
    assert (
        hexdigest(norm(TON / "PACKAGE_MANIFEST.json")) == acc["package_sha256"]
        and hexdigest(norm(TON / "FROZEN.json")) == old["files"]["FROZEN.json"]
    )
    identity = read(TON / "DIAGNOSTIC_CARD.json")
    assert hexdigest(norm(TON / "DIAGNOSTIC_CARD.json")) == acc["card_sha256"]
    assets = read(src / "HPC_ARTIFACT_SHA.json")
    science = read(src / "SCIENCE.json")
    raw = read(src / "RAW_INFERENCE.json")
    hosts = identity["hosts"]
    paired = [
        h
        for h, v in science["references"].items()
        if v.get("ready") and v.get("protocols", {}).get("6", {}).get("components", 0) >= 2
    ]
    assert set(paired) == {"192.168.1.152", "192.168.1.190", "192.168.1.195"} and all(
        v["main_identity"] == "UNCONFIRMED" for v in hosts.values()
    )
    pins = {
        k: assets[k] for k in ("snapshots.sqlite", "RAW.npy", "INPUT_SEAL.json", "RAW_PROOF.json", *hosts)
    }
    assert all(v["path"].endswith("/" + TON.name + "/formal/" + v["file"]) for v in pins.values())
    card = dict(
        parent=TON.name,
        source_job=acc["jobs"]["evaluate"],
        source_return_sha256=hexdigest((src / "RETURN.json").read_bytes()),
        freeze_sha256=old["files"]["FROZEN.json"],
        inputs=pins,
        hosts=hosts,
        paired_hosts=paired,
        method=read(TON / "FROZEN.json")["method"],
        populations=science["query_populations"],
        order=raw["uid_order_sha256"],
        levels=[0.25, 0.20, 0.15, 0.10, 0.05, 0.0],
        handoff_sha256=hexdigest(norm(DOC)),
        connection_key=["capture", "kind", "host", "original conn"],
        view="all eligible inbound packets",
        table3_quantile="NumPy linear; first RAW-positive by original frame. Each cohort defined by full RAW-positive and zero baseline-positive connections.",
    )
    files = {n: norm(HERE / n) for n in SRC}
    files.update(
        {
            "CACHE_PINS.json": encode(card),
            "handoff.md": norm(DOC),
            "slurm_base.py": norm(DUAL / "launch.py"),
            "reports.py": norm(DUAL / "reports.py"),
            "common_round1.py": norm(RUNS / "same_information_recalibration_v1_20261113/common_round1.py"),
            "common_ton.py": norm(TON / "common_ton.py"),
        }
    )
    for n in ("RAW_TARGETS.csv", "CCNR_PAIRED.csv"):
        files[n] = (src / n).read_bytes()
    files["run.slurm"] = (
        norm(TON / "run.slurm")
        .replace(b'argument="$4"', b"")
        .replace(b"worker_ton.py", b"cached_replay.py")
        .replace(b' "$argument"', b"")
    )
    # The cached phases use NumPy and SQLite only.
    files["run.slurm"] = files["run.slurm"].replace(
        b"if ! command -v tshark >/dev/null 2>&1; then module load apps/tshark/4.6.6; fi", b""
    )
    for n, b in files.items():
        if n.endswith(".py"):
            compile(b, n, "exec")
    manifest = dict(run=HERE.name, files={n: hexdigest(b) for n, b in sorted(files.items())})
    files["PACKAGE_MANIFEST.json"] = encode(manifest)
    for n in ("CACHE_PINS.json", "PACKAGE_MANIFEST.json"):
        (HERE / n).write_bytes(files[n])
    PRIVATE.mkdir(exist_ok=True)
    dest = PRIVATE / "package.tar.gz"
    with (
        dest.open("wb") as f,
        gzip.GzipFile(filename="", fileobj=f, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w") as t,
    ):
        for n, b in sorted(files.items()):
            m = tarfile.TarInfo(n)
            m.size = len(b)
            m.mode = 0o700 if n == "run.slurm" else 0o600
            t.addfile(m, io.BytesIO(b))
    print(dest.stat().st_size, hexdigest(dest.read_bytes()))


if __name__ == "__main__":
    build()
