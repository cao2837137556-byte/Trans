"""Build a private deployment archive from verified local data. Only metadata enters Git."""

import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import tarfile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
PREP = RUNS / "dad_frozen_v12_preparation_20261119"
TON = RUNS / "p4_ton_password_frozen_v12_20261118"
DUAL = RUNS / "p4_dual_component_mean_v1_20261117"
RECAL = RUNS / "same_information_recalibration_v1_20261113"
DOC = RUNS / "mainline_docs/collab/20261119_paper04_dad_frozen_v12_execution_card_codex.md"
SRC = ("dad_worker.py", "dad_stats.py", "dad_frontend.py", "launch.py")
PRIVATE = HERE / ".private"


def hexdigest(b):
    return hashlib.sha256(b).hexdigest()


def norm(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def encode(o):
    return (json.dumps(o, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def read(p):
    return json.loads(p.read_bytes())


def build():
    pins = read(PREP / "INPUTS.json")
    root = Path(os.environ["LOCALAPPDATA"]) / "Paper04/datasets/DAD" / pins["commit"]
    files = {k: norm(HERE / k) for k in SRC}
    for p, h in [
        (PREP / "INPUTS.json", "1daeff850ff8400d39e8fc34bed91e3f4fcb77a155f4c891e2d84b0a06743ea9"),
        (PREP / "AUDIT.json", "e54a90fd8fd7826e597658371ff421ddb6ccbe37b2356bbbb9d5036d6fb59666"),
        (DUAL / "FROZEN.json", "fa8b6e3a94f9aab62cacc801d07db3a271c58d3925f8b6993214f863a8e03150"),
    ]:
        assert hexdigest(p.read_bytes()) == h, p
    previous = read(TON / "PACKAGE_MANIFEST.json")["files"]
    for name in ("common_ton.py", "frozen_env.py", "onboarding_dense_reference_v1.py"):
        path = TON / name if name != "onboarding_dense_reference_v1.py" else RUNS.parent / "repo/ood" / name
        files[name] = norm(path)
        assert hexdigest(files[name]) == previous[name]
    f = read(TON / "FROZEN.json")
    method = read(DUAL / "FROZEN.json")["method"]
    assert method == f["method"] and hexdigest(norm(TON / "FROZEN.json")) == previous["FROZEN.json"]
    files["FROZEN.json"] = encode(
        {
            k: f[k]
            for k in (
                "method",
                "extra_pins",
                "runtime_package",
                "runtime_manifest_sha256",
                "source_config_sha256",
                "source_geometry_sha256",
            )
        }
    )
    files.update(
        {
            "INPUTS.json": (PREP / "INPUTS.json").read_bytes(),
            "AUDIT.json": (PREP / "AUDIT.json").read_bytes(),
            "card.md": norm(DOC),
            "dad_geometry.py": norm(DUAL / "geometry.py"),
            "slurm_base.py": norm(DUAL / "launch.py"),
            "reports.py": norm(DUAL / "reports.py"),
            "common_round1.py": norm(RECAL / "common_round1.py"),
        }
    )
    assert hexdigest(files["dad_geometry.py"]) == read(DUAL / "PACKAGE_MANIFEST.json")["files"]["geometry.py"]
    raw_audit = norm(PREP / "audit.py")
    anchor = b"            if not event or proto != 6:"
    assert raw_audit.count(anchor) == 1 and raw_audit.count(b"def audit(cache, tshark):") == 1
    files["dad_audit.py"] = raw_audit.replace(
        b"def audit(cache, tshark):", b"def audit(cache, tshark, observer=None):"
    ).replace(
        anchor,
        b"            if observer is not None:\n                observer(day,frame,ns,contexts,engine,comp,event,start,cutoff,clock,flag_label,digest)\n"
        + anchor,
    )
    shell = norm(TON / "run.slurm")
    assert hexdigest(shell) == previous["run.slurm"]
    files["run.slurm"] = (
        shell.replace(b'argument="$4"', b"")
        .replace(b"worker_ton.py", b"dad_worker.py")
        .replace(b' "$argument"', b"")
    )
    for name, p in pins["files"].items():
        blob = (root / name).read_bytes()
        assert len(blob) == p["bytes"] and hexdigest(blob) == p["sha256"]
        assert hashlib.sha1(b"blob " + str(len(blob)).encode() + b"\0" + blob).hexdigest() == p["git_blob"]
        files["raw/" + name] = blob
    card = dict(
        source_commit=pins["commit"],
        execution_card_sha256=hexdigest(files["card.md"]),
        audit_source_sha256=hexdigest(raw_audit),
        frozen_parameter_source_sha256=hexdigest((DUAL / "FROZEN.json").read_bytes()),
        ton_package_sha256=read(TON / "received/ACCEPTANCE.json")["package_sha256"],
        bank_uid_order=read(PREP / "AUDIT.json")["selected_bank"]["selected_uid_sha256"],
        queries=18317,
        normal=17773,
        attack=544,
        thursday=56,
        tuesday_scored=0,
        model_updates=0,
        threshold_changes=0,
    )
    files["DAD_CARD.json"] = encode(card)
    files["PACKAGE_MANIFEST.json"] = encode(
        dict(run=HERE.name, files={k: hexdigest(v) for k, v in sorted(files.items())})
    )
    PRIVATE.mkdir(exist_ok=True)
    for n in ("DAD_CARD.json", "PACKAGE_MANIFEST.json"):
        (HERE / n).write_bytes(files[n])
    path = PRIVATE / "package.tar.gz"
    with (
        path.open("wb") as real,
        gzip.GzipFile(fileobj=real, filename="", mtime=0, mode="wb") as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for name, data in sorted(files.items()):
            if name.endswith(".py"):
                compile(data, name, "exec")
            m = tarfile.TarInfo(name)
            m.size = len(data)
            m.mode = 0o700 if name.endswith(".slurm") else 0o600
            tar.addfile(m, io.BytesIO(data))
    assert path.stat().st_size <= 5 * 1024**2
    print("Private bundle", path.stat().st_size, hexdigest(path.read_bytes()))


if __name__ == "__main__":
    build()
