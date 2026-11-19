"""Seal the diagnostic sources, original model identities and the two analysis definitions."""

from hashlib import sha256
import gzip
import io
import json
import tarfile

from common_ton import HERE, dump, read, require, sha

RUNS = HERE.parent
PREVIOUS = RUNS / "p4_dual_component_mean_v1_20261117"
RECAL = RUNS / "same_information_recalibration_v1_20261113"
OLD = RUNS / "unified_reference_bank_k8192_v1_20261113"
DOC = RUNS / "mainline_docs/collab/20261118_paper04_ton_password_frozen_v12_handoff_codex.md"
PRIVATE = HERE / ".private"
SCIENCE = (
    "common_ton.py",
    "capture.py",
    "admission.py",
    "wire.py",
    "frontend.py",
    "representations.py",
    "frozen_env.py",
    "evaluate_ton.py",
    "report_ton.py",
    "worker_ton.py",
    "launch.py",
    "launch_names.py",
    "asset_ingress.py",
    "run.slurm",
    "SCOPED_INPUTS.json",
    "PASSWORD_SAMPLE.json",
    "LOCAL_CENSUS.json",
    "LOCAL_HEADER_PARITY.json",
    "HOST_IDENTITY_AUDIT.json",
    "RAW_HOST_EVIDENCE.json",
    "DIAGNOSTIC_CARD.json",
)


def normalized(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def block(v):
    return (json.dumps(v, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def runtime_files():
    cfg = read(PREVIOUS / "FROZEN.json")
    contract = read(RECAL / "INPUT_PINS.json")["inputs"]
    inputs = {
        k: dict(paths=v["remote"], sha256=v["sha256"], bytes=v.get("bytes"), group="reference")
        for k, v in contract.items()
        if k.startswith(("head_", "model:"))
    }
    inputs.update(cfg["additional_pins"])
    metadata = read(OLD.parent / (OLD.name + "_uidfix_184105") / "RECOVERY_INPUTS.json")["contexts"][
        "CIC_DEV"
    ]
    original = read(OLD / "REMOTE_ASSET_PINS.json")["files"]["CIC_DEV:query_context_uids"]
    inputs["CIC_DEV:query_context_uids"] = dict(original, sha256=metadata["uid_sha256"])
    manifest = read(PREVIOUS / "RUNTIME_PACKAGE_MANIFEST.json")["files"]
    source = {}
    for name in ("continuous_input_v3", "legacy_reference_context_scope_v1"):
        rel = "repo/ood/" + name + ".py"
        data = normalized(RUNS.parent / rel)
        require(sha256(data).hexdigest() == manifest[rel], "FROZEN_FRONTEND_SOURCE:" + name)
        # Replace only the two L2 identity lookups with explicit verified L3 role tags.
        data = data.replace(b"'eth.src'", b"'ton.owner.src'").replace(b"'eth.dst'", b"'ton.owner.dst'")
        if name == "continuous_input_v3":
            data = data.replace(
                b"import legacy_reference_context_scope_v1 as guard", b"import ton_scope as guard"
            )
            source["ton_recent.py"] = data
        else:
            source["ton_scope.py"] = data
    dense = RUNS.parent / "repo/ood/onboarding_dense_reference_v1.py"
    source["onboarding_dense_reference_v1.py"] = normalized(dense)
    freeze = dict(
        runtime_package=cfg["runtime_package"],
        runtime_manifest_sha256=cfg["runtime_manifest_sha256"],
        method=cfg["method"],
        extra_pins=inputs,
        source_config_sha256=manifest["CONFIG.json"],
        source_geometry_sha256=manifest["GEOMETRY.json"],
        original_source=cfg["query"]["CIC_DEV"],
        dense_selector_sha256=sha256(source["onboarding_dense_reference_v1.py"]).hexdigest(),
        diagnostic_card_sha256=sha(HERE / "DIAGNOSTIC_CARD.json"),
    )
    return source, freeze


def build():
    files, freeze = runtime_files()
    dump(HERE / "FROZEN.json", freeze)
    files.update({name: normalized(HERE / name) for name in (*SCIENCE, "FROZEN.json")})
    files["handoff.md"] = normalized(DOC)
    for name, data in files.items():
        if name.endswith(".py"):
            compile(data, name, "exec")
    manifest = dict(
        run=HERE.name, files={name: sha256(data).hexdigest() for name, data in sorted(files.items())}
    )
    files["PACKAGE_MANIFEST.json"] = block(manifest)
    (HERE / "PACKAGE_MANIFEST.json").write_bytes(files["PACKAGE_MANIFEST.json"])
    path = PRIVATE / "package.tar.gz"
    with (
        path.open("wb") as raw,
        gzip.GzipFile(fileobj=raw, filename="", mtime=0, mode="wb") as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for name, data in sorted(files.items()):
            entry = tarfile.TarInfo(name)
            entry.size = len(data)
            entry.mode = 0o700 if name.endswith(".slurm") else 0o600
            tar.addfile(entry, io.BytesIO(data))
    print("frozen package", path.stat().st_size, sha(path))


if __name__ == "__main__":
    build()
