"""CKBI: label-free report-only TGN cache extension for formal M1.

The original 26-source CKBE cache remains immutable.  This program writes a
separate four-source cache only for report coverage missing from CKBE:
future-query air-quality/building-monitor plus sealed museum/street sources.
It never reads a raw label column and never creates fit/select inputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbe_tgn_fullsupport_event_cache_v1 as ckbe  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12"
ROOT = cko.ROOT
DEFAULT_OUT = ROOT / "runs" / "issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
EXTENSION_SOURCES = {
    "processed/iotsim-air-quality-1.csv": "future_query",
    "processed/iotsim-building-monitor-1.csv": "future_query",
    "processed/iotsim-ip-camera-museum-2.csv": "sealed_final_ood",
    "processed/iotsim-ip-camera-street-1.csv": "sealed_final_attack",
}
REPORT_SPECS = {
    "future_query": "all",
    "sealed_final_ood": "report_only",
    "sealed_final_attack": "report_only",
}
M1_FIT_SELECT_SCOPES = (
    ("tgn_ssl_and_verifier", "support_train", "fit"),
    ("tgn_ssl_and_verifier", "id_calib", "fit"),
    ("tgn_ssl_and_verifier", "ood_val", "fit"),
    ("tgn_ssl_and_verifier", "ood_stress", "fit"),
    ("c1_fit_and_standardize", "support_train", "fit"),
    ("c1_fit_and_standardize", "id_calib", "fit"),
    ("c1_fit_and_standardize", "ood_val", "fit"),
    ("c1_fit_and_standardize", "ood_stress", "fit"),
    ("gate_and_threshold_select", "support_val", "select"),
    ("gate_and_threshold_select", "id_calib", "select"),
    ("gate_and_threshold_select", "ood_val", "select"),
    ("gate_and_threshold_select", "ood_stress", "select"),
)


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def report_targets(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Use only source/recorded-index coordinates from report-role manifests."""
    rows: list[pd.DataFrame] = []
    for role, phase in REPORT_SPECS.items():
        frame = frames[role]
        part = frame if phase == "all" else frame.loc[frame["phase"].astype(str).eq(phase)]
        part = part.loc[part["source_group"].astype(str).isin(EXTENSION_SOURCES)].copy()
        if part.empty:
            continue
        part = part.loc[:, ["source_group", "recorded_index"]]
        part["report_role"] = role
        part["report_phase_policy"] = "report_only"
        rows.append(part)
    if not rows:
        raise RuntimeError("no report-only target indices found for CKBI extension")
    result = pd.concat(rows, ignore_index=True)
    result["source_group"] = result["source_group"].astype(str)
    result["recorded_index"] = pd.to_numeric(result["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    result = result.loc[result["recorded_index"] >= 0].drop_duplicates(
        ["source_group", "report_role", "recorded_index"], keep="first"
    ).sort_values(["source_group", "report_role", "recorded_index"], kind="mergesort").reset_index(drop=True)
    actual = set(result["source_group"].tolist())
    if actual != set(EXTENSION_SOURCES):
        raise RuntimeError(f"CKBI source set mismatch: expected={sorted(EXTENSION_SOURCES)} actual={sorted(actual)}")
    for source, role in EXTENSION_SOURCES.items():
        found = set(result.loc[result["source_group"].eq(source), "report_role"].astype(str).tolist())
        if found != {role}:
            raise RuntimeError(f"CKBI report role mismatch for {source}: {sorted(found)}")
    return result


def report_only_exclusion(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source in sorted(EXTENSION_SOURCES):
        for scope, role, phase in M1_FIT_SELECT_SCOPES:
            frame = frames[role]
            part = frame.loc[frame["phase"].astype(str).eq(phase)]
            used = int(part["source_group"].astype(str).eq(source).sum())
            rows.append({
                "source_group": source, "scope": scope, "role": role, "phase": phase,
                "extension_source_rows_used": used, "required_zero": 0, "pass": bool(used == 0),
            })
        role = EXTENSION_SOURCES[source]
        rows.append({
            "source_group": source, "scope": "report_only_extension", "role": role,
            "phase": "report_only", "extension_source_rows_used": int(
                (frames[role]["source_group"].astype(str).eq(source)).sum()
            ), "required_zero": np.nan, "pass": True,
        })
    return pd.DataFrame(rows)


def materialize_all(out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    _x, frames, input_audit, _labels = cko.load_role_inputs(False)
    del _x, _labels
    targets = report_targets(frames)
    exclusion = report_only_exclusion(frames)
    if not bool(exclusion.loc[exclusion["required_zero"].notna(), "pass"].all()):
        raise RuntimeError("report-only extension source leaked into an M1 fit/select scope")

    target_index = out / "report_extension_recorded_targets.csv"
    targets.to_csv(target_index, index=False)
    cache_dir = out / "tgn_event_cache"
    runtime_dir = out / "source_runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    alignment_parts: list[pd.DataFrame] = []
    audit_rows: list[dict[str, Any]] = []

    for source in sorted(EXTENSION_SOURCES):
        source_part = targets.loc[targets["source_group"].eq(source)].copy()
        indices = source_part["recorded_index"].astype(np.int64).unique()
        summary = ckbe.materialize_source(source, indices, cache_dir)
        key = ckbe.source_key(source)
        npz_path = cache_dir / f"{key}.npz"
        with np.load(npz_path, allow_pickle=False) as data:
            lookup = {
                int(recorded): int(position)
                for recorded, position in zip(data["target_recorded_index"].tolist(), data["target_event_position"].tolist())
            }
        source_part["target_event_position"] = source_part["recorded_index"].map(lookup).fillna(-1).astype(np.int64)
        alignment_parts.append(source_part)
        runtime = {
            **summary,
            "issue": ISSUE,
            "report_role": EXTENSION_SOURCES[source],
            "report_only": True,
            "raw_source_path": source,
            "raw_label_column_read": False,
        }
        (runtime_dir / f"{key}.json").write_text(json.dumps(runtime, indent=2) + "\n", encoding="utf-8")
        audit_rows.append({
            "source_group": source, "report_role": EXTENSION_SOURCES[source], "source_cache_key": key,
            "raw_source_path": source, "target_rows": int(len(indices)),
            "target_positions_found": int(np.sum(source_part["target_event_position"].to_numpy() >= 0)),
            "target_positions_complete": bool(np.all(source_part["target_event_position"].to_numpy() >= 0)),
            "raw_label_column_read": False, "event_schema": json.dumps(summary["event_schema"]),
            "source_local_anonymous_ids": True, "npz_bytes": int(npz_path.stat().st_size),
        })

    alignment = pd.concat(alignment_parts, ignore_index=True).sort_values(
        ["source_group", "report_role", "recorded_index"], kind="mergesort"
    ).reset_index(drop=True)
    alignment_path = out / "report_extension_target_alignment.csv"
    alignment.to_csv(alignment_path, index=False)
    audit = pd.DataFrame(audit_rows).sort_values("source_group", kind="mergesort").reset_index(drop=True)
    audit_path = out / "report_extension_cache_audit.csv"
    audit.to_csv(audit_path, index=False)
    exclusion_path = out / "report_only_fit_select_exclusion_audit.csv"
    exclusion.to_csv(exclusion_path, index=False)

    manifest = audit.loc[:, [
        "source_group", "report_role", "raw_source_path", "source_cache_key", "target_rows",
        "target_positions_found", "target_positions_complete", "raw_label_column_read", "event_schema",
        "source_local_anonymous_ids", "npz_bytes",
    ]].copy()
    manifest["target_alignment_csv"] = alignment_path.name
    manifest["target_alignment_sha256"] = sha256_path(alignment_path)
    manifest["recorded_target_index_csv"] = target_index.name
    manifest["recorded_target_index_sha256"] = sha256_path(target_index)
    manifest_path = out / "report_only_extension_manifest_frozen.csv"
    manifest.to_csv(manifest_path, index=False)
    manifest_hash = sha256_path(manifest_path)
    (out / "report_only_extension_manifest_sha256.txt").write_text(manifest_hash + "\n", encoding="utf-8")

    ready = {
        "issue": ISSUE, "source_count": int(len(manifest)), "target_rows": int(len(alignment)),
        "extension_manifest": manifest_path.name, "extension_manifest_sha256": manifest_hash,
        "recorded_target_index_sha256": sha256_path(target_index),
        "target_alignment_sha256": sha256_path(alignment_path),
        "raw_label_column_read": False, "report_only_fit_select_exclusion_pass": bool(
            exclusion.loc[exclusion["required_zero"].notna(), "pass"].all()
        ), "target_positions_complete": bool(audit["target_positions_complete"].all()),
        "event_schema": ckbe.RAW_MSG_NAMES, "input_audit": input_audit,
    }
    (out / "extension_ready.json").write_text(json.dumps(ready, indent=2) + "\n", encoding="utf-8")
    if not (ready["report_only_fit_select_exclusion_pass"] and ready["target_positions_complete"] and ready["source_count"] == 4):
        raise RuntimeError("CKBI extension contract failed")
    print(json.dumps({"status": "extension_materialized", "out": str(out), **ready}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--mode", choices=("materialize-all",), default="materialize-all")
    args = parser.parse_args()
    materialize_all(Path(args.out))


if __name__ == "__main__":
    main()
