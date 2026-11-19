"""Build a small content-addressed delivery from the two previously accepted experiments."""

import ast
import gzip
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import tarfile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
DUAL = RUNS / "p4_dual_component_mean_v1_20261117"
RECAL = RUNS / "same_information_recalibration_v1_20261113"
BASE = RUNS / "unified_reference_bank_k8192_v1_20261113"
DOC = RUNS / "mainline_docs/collab/20261118_paper04_v12_next_experiments_handoff_codex.md"
REMOTE_FILES = (
    "worker.py",
    "runtime_v12.py",
    "group_threshold.py",
    "mechanism.py",
    "port_audit.py",
    "tables_v12.py",
    "paired_stats.py",
    "regressions.py",
    "launch.py",
    "accept_v12.py",
    "EXPERIMENT_CARD.json",
    "RULE_FREEZE.json",
)
PRIVATE = HERE / ".private"


def read(path):
    return json.loads(path.read_bytes().decode("utf-8-sig"))


def source(path):
    return path.read_bytes().replace(b"\r\n", b"\n")


def digest(b):
    return sha256(b).hexdigest()


def encoded(obj):
    return (json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()


def provenance():
    dual = read(DUAL / "received/ACCEPTANCE.json")
    prior = read(RECAL / "received/FINAL_ACCEPTANCE.json")
    assert (
        dual["status"] == prior["status"] == "PASS"
        and dual["jobs"]["formal"] == "184893"
        and prior["slurm_job_id"] == "183937"
    )
    freeze = read(HERE / "RULE_FREEZE.json")
    assert digest(source(HERE / "EXPERIMENT_CARD.json")) == freeze["card_sha256"]
    handoff = source(DOC)
    if digest(handoff) != freeze["handoff_sha256"]:
        # The owner added four collaboration instructions after the experimental rule was sealed.
        before = re.sub(
            r"^## 负责人给实验聊天的四项长期协作约束\n[\s\S]*?(?=^## 1\. 外部资料)",
            "",
            handoff.decode(),
            flags=re.M,
        )
        assert digest(before.encode()) == freeze["handoff_sha256"], "SCIENTIFIC_HANDOFF_CHANGED"
    pairs = read(DUAL / "received/ARTIFACTS.json")
    certificate = read(DUAL / "received/SCIENCE.json")
    assert digest(source(DUAL / "received/SCIENCE.json")) == dual["science"]["sha256"]
    assert (
        digest(source(DUAL / "received/ARTIFACTS.json")) == certificate["outputs"]["ARTIFACTS.json"]["sha256"]
    )
    old = read(RECAL / "received/PULLBACK_MANIFEST.json")["files"]
    seal = read(RECAL / "received/results/THRESHOLD_SEAL.json")
    assert digest(source(RECAL / "received/results/THRESHOLD_SEAL.json")) == prior["threshold_sha256"]
    paths = {}
    for field, filename in (
        ("original_thresholds", "THRESHOLD_SEAL.json"),
        ("original_metrics", "METRICS.json"),
    ):
        filename = "results/" + filename
        p = old[filename]
        assert digest(source(RECAL / "received" / filename)) == p["sha256"]
        paths[field] = dict(path="runs/" + RECAL.name + "/" + filename, sha256=p["sha256"])
    older = read(DUAL / "FROZEN.json")
    orig_manifest = read(DUAL / "RUNTIME_PACKAGE_MANIFEST.json")["files"]
    paths["baseline_expected"] = dict(
        path=older["runtime_package"] + "/EXPECTED_BASELINE.json",
        sha256=orig_manifest["EXPECTED_BASELINE.json"],
    )

    def meta(p):
        return {k: v for k, v in p.items() if k in ("sha256", "bytes", "rows")}

    headers = read(RUNS / "same_bank_context_v6_20261106/HISTORY_INPUTS.json")
    pins = read(BASE / "REMOTE_ASSET_PINS.json")["files"]
    raw = [dict(raw_key=k, sha256=pins[k]["sha256"]) for k in ("a30", "a31", "a32")]
    for t in headers["b_targets"]:
        raw.append(
            dict(
                raw_key=t["raw"]["asset"],
                index_key=t["packet_index"]["asset"],
                sha256=t["raw"]["sha256"],
                bank_end_frame=t["bank_end_frame"],
                clock_offset=t.get("timestamp_offset_seconds", 0),
            )
        )
    adapter = RUNS / "edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py"
    tree = ast.parse(source(adapter))
    constants = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id in ("OWNER", "TARGET_IP")
    }
    return dict(
        rule_sha256=freeze["card_sha256"],
        current_handoff_sha256=digest(handoff),
        geometry_run=DUAL.name,
        geometry_package=dual["package_sha256"],
        **paths,
        paired={
            p: dict(
                path=f"runs/{DUAL.name}/artifacts/" + v["paired_arrays"]["file"], **meta(v["paired_arrays"])
            )
            for p, v in pairs.items()
        },
        reference_scores={
            p: dict(
                path=f"runs/{RECAL.name}/results/" + v["reference_scores"]["file"],
                **meta(v["reference_scores"]),
            )
            for p, v in seal["pools"].items()
        },
        query_uid_sha256=older["query_uid_sha256"],
        bank_uid_sha256={p: v["reference_uid_order_sha256"] for p, v in pairs.items()},
        normal_headers=raw,
        edge_binding=dict(
            owner=constants["OWNER"],
            ip=constants["TARGET_IP"],
            source=adapter.relative_to(RUNS.parent).as_posix(),
            sha256=digest(source(adapter)),
        ),
        accepted_weak_mean_headlines=read(DUAL / "received/HEADLINE.json"),
    )


def build():
    PRIVATE.mkdir(exist_ok=True)
    files = {n: source(HERE / n) for n in REMOTE_FILES}
    files.update(
        {
            "ASSETS.json": encoded(provenance()),
            "protocol.md": source(DOC),
            "common_round1.py": source(RECAL / "common_round1.py"),
            "slurm_base.py": source(DUAL / "launch.py"),
            "reports.py": source(DUAL / "reports.py"),
            "run.slurm": source(DUAL / "run.slurm"),
        }
    )
    for n, b in files.items():
        if n.endswith(".py"):
            compile(b, n, "exec")
    manifest = dict(run=HERE.name, files={n: digest(b) for n, b in sorted(files.items())})
    files["PACKAGE_MANIFEST.json"] = encoded(manifest)
    for n in ("ASSETS.json", "PACKAGE_MANIFEST.json"):
        (HERE / n).write_bytes(files[n])
    archive = PRIVATE / "package.tar.gz"
    with (
        archive.open("wb") as raw,
        gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as gz,
        tarfile.open(fileobj=gz, mode="w") as tar,
    ):
        for name, blob in sorted(files.items()):
            item = tarfile.TarInfo(name)
            item.size = len(blob)
            item.mode = 0o700 if name == "run.slurm" else 0o600
            tar.addfile(item, io.BytesIO(blob))
    print("package bytes", archive.stat().st_size, "SHA256", digest(archive.read_bytes()))


if __name__ == "__main__":
    build()
