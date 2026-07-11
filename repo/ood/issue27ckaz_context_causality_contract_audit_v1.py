"""CKAZ: executable causal-context and split-boundary audit for CKAW.

This is an audit only.  It never supplies a feature or a training label.  It
checks the contracts that make CKAW's stateful representation deployable:

* changing a timestamp-later packet must not alter a target's representation;
* changing raw truth labels must not alter a target's representation;
* changing a timestamp-earlier packet may alter the representation;
* the strict held family is absent from fit and select model rows.

The audit also records the deliberate context policy: state is built from all
*previously observed, label-free* packets in a source.  This is an online
history policy, not a ground-truth-cleaned history; cleaning it by true attack
labels would be unavailable at deployment and therefore invalid.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw  # noqa: E402


ISSUE = "issue27ckaz_context_causality_contract_audit_v1_2026-07-11"
ROOT = cko.ROOT
DEFAULT_CACHE = ROOT / "runs" / "issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_local_150k"
HELD = [
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "domotic-monitor",
    "combined-cycle",
    "iotsim-ip-camera-street",
]


def synthetic_frame() -> pd.DataFrame:
    # row 1 has a later timestamp than the target row 2 but appears first in
    # storage order.  This exercises canonical timestamp replay rather than
    # merely checking a convenient file-order prefix.
    return pd.DataFrame(
        [
            {"frame.time": "2026-01-01T00:00:10Z", "frame.len": 70, "frame.protocols": "eth:ip:udp", "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "eth.src": "", "eth.dst": "", "ip.proto": 17, "tcp.srcport": 0, "tcp.dstport": 0, "udp.srcport": 1111, "udp.dstport": 53, "tcp.flags": 0, "label": "BENIGN"},
            {"frame.time": "2026-01-01T00:00:30Z", "frame.len": 70, "frame.protocols": "eth:ip:udp", "ip.src": "10.0.0.9", "ip.dst": "10.0.0.8", "eth.src": "", "eth.dst": "", "ip.proto": 17, "tcp.srcport": 0, "tcp.dstport": 0, "udp.srcport": 3333, "udp.dstport": 4444, "tcp.flags": 0, "label": "ATTACK"},
            {"frame.time": "2026-01-01T00:00:20Z", "frame.len": 70, "frame.protocols": "eth:ip:udp", "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "eth.src": "", "eth.dst": "", "ip.proto": 17, "tcp.srcport": 0, "tcp.dstport": 0, "udp.srcport": 1111, "udp.dstport": 53, "tcp.flags": 0, "label": "OOD"},
        ]
    )


def feature_for(frame: pd.DataFrame) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "synthetic.zip"
        member = "synthetic.csv"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(member, frame.to_csv(index=False))
        cache = ckaw.CanonicalEpisodeCache(archive)
        matrix, _audit, _summary = cache.compute(member, np.asarray([2], dtype=np.int64))
        return matrix[0]


def synthetic_contract() -> dict[str, object]:
    base = synthetic_frame()
    reference = feature_for(base)

    future_changed = base.copy()
    future_changed.loc[1, ["frame.len", "ip.src", "ip.dst", "udp.dstport"]] = [99999, "99.0.0.1", "99.0.0.2", 65000]
    label_changed = base.copy()
    label_changed["label"] = ["ATTACK", "OOD", "BENIGN"]
    past_changed = base.copy()
    past_changed.loc[0, ["ip.dst", "udp.dstport"]] = ["10.0.0.99", 65000]

    future_equal = bool(np.array_equal(reference, feature_for(future_changed)))
    label_equal = bool(np.array_equal(reference, feature_for(label_changed)))
    past_changes = bool(not np.array_equal(reference, feature_for(past_changed)))
    return {
        "raw_label_in_raw_usecols": "label" in ckaw.RAW_USECOLS,
        "future_packet_invariant": future_equal,
        "raw_label_invariant": label_equal,
        "past_packet_sensitive": past_changes,
        "pass": bool(("label" not in ckaw.RAW_USECOLS) and future_equal and label_equal and past_changes),
    }


def role_boundary_audit() -> pd.DataFrame:
    _unused, frames, _audit, _meta = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    rows: list[dict[str, object]] = []
    for held in HELD:
        for role in ("support_train", "id_calib", "ood_val", "ood_stress"):
            for phase in ("fit", "select"):
                all_indices = ckao.role_indices_filtered(frames, role, phase, cko.FULL_CAP)
                retained = ckao.role_indices_filtered(frames, role, phase, cko.FULL_CAP, exclude=("device_family", held))
                held_in_retained = int((frames[role].iloc[retained]["device_family"].astype(str) == held).sum()) if len(retained) else 0
                rows.append({
                    "held_value": held,
                    "role": role,
                    "phase": phase,
                    "all_rows": int(len(all_indices)),
                    "retained_after_exclusion": int(len(retained)),
                    "held_rows_after_exclusion": held_in_retained,
                    "pass": held_in_retained == 0,
                })
    return pd.DataFrame(rows)


def cache_audit(cache_root: Path) -> dict[str, object]:
    root = cache_root / "canonical_episode_cache"
    records = []
    for path in sorted(root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        source = payload.get("source_audit", {})
        targets = payload.get("target_audit", [])
        records.append({
            "file": path.name,
            "source_label_read": bool(source.get("raw_label_column_read", True)),
            "targets": len(targets),
            "target_label_read_true": int(sum(bool(row.get("raw_label_column_read", True)) for row in targets)),
            "past_only_targets": int(sum(row.get("chronology_status") == "CANONICAL_TIMESTAMP_PAST_ONLY" for row in targets)),
            "unparseable_targets": int(sum(row.get("chronology_status") == "TARGET_TIMESTAMP_UNPARSEABLE" for row in targets)),
        })
    return {
        "cache_root": str(cache_root),
        "cache_json_files": len(records),
        "source_label_reads": int(sum(row["source_label_read"] for row in records)),
        "target_label_reads": int(sum(row["target_label_read_true"] for row in records)),
        "past_only_targets": int(sum(row["past_only_targets"] for row in records)),
        "unparseable_targets": int(sum(row["unparseable_targets"] for row in records)),
        "records": records,
    }


def run(args: argparse.Namespace) -> None:
    out = ROOT / "runs" / (ISSUE if not args.run_tag else f"{ISSUE}_{args.run_tag}")
    out.mkdir(parents=True, exist_ok=True)
    synthetic = synthetic_contract()
    boundaries = role_boundary_audit()
    cache = cache_audit(Path(args.cache_root))
    boundaries.to_csv(out / "strict_role_boundary_audit.csv", index=False)
    (out / "context_cache_audit.json").write_text(json.dumps(cache, indent=2) + "\n", encoding="utf-8")
    result = {
        "synthetic_causality_contract": synthetic,
        "role_boundary_pass": bool(boundaries["pass"].all()),
        "cache_label_free_pass": cache["source_label_reads"] == 0 and cache["target_label_reads"] == 0,
        "online_context_policy": "all timestamp-earlier raw packets in the same source; no raw label and no future timestamp state; roles are not used to clean history",
        "deployment_equivalence_requirement": "the deployed state must use the same timestamp-earlier unlabeled packet stream and must not use truth-label cleaning",
    }
    result["pass"] = bool(synthetic["pass"] and result["role_boundary_pass"] and result["cache_label_free_pass"])
    (out / "audit_result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    lines = [f"# {ISSUE}", "", f"overall_pass: `{result['pass']}`", "", "## Contract", "", f"- label excluded from raw frontend: `{not synthetic['raw_label_in_raw_usecols']}`", f"- future packet invariant: `{synthetic['future_packet_invariant']}`", f"- raw-label invariant: `{synthetic['raw_label_invariant']}`", f"- past packet affects state: `{synthetic['past_packet_sensitive']}`", f"- strict held-family fit/select exclusion: `{result['role_boundary_pass']}`", f"- cached frontend label-free: `{result['cache_label_free_pass']}`", "", "## Deliberate online policy", "", "Past packets of any eventual truth class may affect history, but their labels cannot. This is deployment-realistic and is not ground-truth cleaning. It must be analysed separately as history-contamination robustness, never repaired with true labels."]
    (out / "codex_readout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"out": str(out), "pass": result["pass"]}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", default=str(DEFAULT_CACHE))
    parser.add_argument("--run-tag", default="local_150k")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
