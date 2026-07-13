"""CKBJ: label-free C1 feature-cache extension for CKBI report sources.

The frozen 26-source CKAT cache remains immutable.  This helper materializes
the *same* canonical-time C1 feature schema for exactly the four CKBI
report-only sources and exactly the target coordinates frozen by CKBI.  It is
invoked inside the metrics-producing M1 Slurm job; it is not a standalone
preflight or an additional model-selection stage.

No raw truth-label column is requested by :class:`CanonicalTimeC1Cache`.
Fit/select membership is checked from the existing sidecars and must be zero
for every extension source before any raw source is opened.
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

import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13"
ROOT = cko.ROOT
DEFAULT_TGN_EXTENSION = ROOT / "runs" / "issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
DEFAULT_OUT = ROOT / "runs" / "issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
EXPECTED_BASE_C1_PLAN_SHA256 = "414616332159eb90553213d6656c3d072a701ea93a02df464acdfa6cebC128f2".lower()
EXPECTED_BASE_C1_TARGET_SHA256 = "74a1699e29b7b1e227f4532ff81f1546a9ba239f2d2d323d390efa5b07437158"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def feature_schema_sha256() -> str:
    return hashlib.sha256("\n".join(ckai.FEATURE_NAMES).encode("utf-8")).hexdigest()


def _all_true(series: pd.Series) -> bool:
    return bool(series.astype(str).str.strip().str.lower().map({"true": True, "false": False}).fillna(False).all())


def _all_false(series: pd.Series) -> bool:
    return bool(series.astype(str).str.strip().str.lower().map({"true": True, "false": False}).fillna(True).eq(False).all())


def validate_base_contract(base_plan: Path, base_targets: Path) -> dict[str, Any]:
    if not base_plan.is_file() or not base_targets.is_file():
        raise RuntimeError("CKBJ requires the frozen CKAT source plan and target manifest")
    plan_hash = sha256_path(base_plan)
    target_hash = sha256_path(base_targets)
    if plan_hash != EXPECTED_BASE_C1_PLAN_SHA256:
        raise RuntimeError(f"frozen CKAT source plan hash changed: {plan_hash}")
    if target_hash != EXPECTED_BASE_C1_TARGET_SHA256:
        raise RuntimeError(f"frozen CKAT target manifest hash changed: {target_hash}")
    plan = pd.read_csv(base_plan)
    targets = pd.read_csv(base_targets)
    if len(plan) != 26 or len(targets) != 34622:
        raise RuntimeError("unexpected frozen CKAT cardinality; expected 26 sources / 34,622 targets")
    return {
        "base_c1_plan_sha256": plan_hash,
        "base_c1_target_sha256": target_hash,
        "base_c1_sources": int(len(plan)),
        "base_c1_targets": int(len(targets)),
    }


def load_ckbi_targets(tgn_extension: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    manifest_path = tgn_extension / "report_only_extension_manifest_frozen.csv"
    target_path = tgn_extension / "report_extension_recorded_targets.csv"
    exclusion_path = tgn_extension / "report_only_fit_select_exclusion_audit.csv"
    if not all(path.is_file() for path in (manifest_path, target_path, exclusion_path)):
        raise RuntimeError("CKBJ requires the completed CKBI report-only contract")
    manifest = pd.read_csv(manifest_path)
    targets = pd.read_csv(target_path)
    exclusion = pd.read_csv(exclusion_path)
    expected = set(ckbi.EXTENSION_SOURCES)
    actual = set(manifest["source_group"].astype(str))
    if len(manifest) != 4 or actual != expected:
        raise RuntimeError(f"CKBI source boundary changed: {sorted(actual)}")
    if not _all_true(manifest["target_positions_complete"]):
        raise RuntimeError("CKBI target alignment is incomplete")
    if not _all_false(manifest["raw_label_column_read"]):
        raise RuntimeError("CKBI metadata says that a raw label column was read")
    use_rows = exclusion.loc[exclusion["required_zero"].notna()]
    if use_rows.empty or not _all_true(use_rows["pass"]) or int(pd.to_numeric(use_rows["extension_source_rows_used"]).sum()) != 0:
        raise RuntimeError("CKBI extension source appears in a fit/select scope")
    required = {"source_group", "recorded_index", "report_role"}
    if not required.issubset(targets.columns):
        raise RuntimeError(f"CKBI target index lacks columns: {sorted(required - set(targets.columns))}")
    targets = targets.loc[:, ["source_group", "recorded_index", "report_role"]].copy()
    targets["source_group"] = targets["source_group"].astype(str)
    targets["recorded_index"] = pd.to_numeric(targets["recorded_index"], errors="raise").astype(np.int64)
    targets = targets.drop_duplicates(["source_group", "recorded_index"], keep="first").sort_values(
        ["source_group", "recorded_index"], kind="mergesort"
    ).reset_index(drop=True)
    if set(targets["source_group"]) != expected:
        raise RuntimeError("CKBI recorded-target source set does not match its manifest")
    for source, role in ckbi.EXTENSION_SOURCES.items():
        roles = set(targets.loc[targets["source_group"].eq(source), "report_role"].astype(str))
        if roles != {role}:
            raise RuntimeError(f"unexpected CKBI role for {source}: {sorted(roles)}")
    return targets, {
        "tgn_extension_manifest_sha256": sha256_path(manifest_path),
        "tgn_extension_target_index_sha256": sha256_path(target_path),
        "tgn_extension_targets": int(len(targets)),
        "report_only_fit_select_rows": 0,
    }


def build_plan(targets: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    plan_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for source, part in targets.groupby("source_group", sort=True):
        indices = np.sort(part["recorded_index"].astype(np.int64).unique())
        key = ckat.source_cache_key(str(source))
        plan_rows.append({
            "source_group": str(source),
            "source_cache_key": key,
            "requested_unique_rows": int(len(indices)),
            "max_recorded_index": int(indices[-1]),
            "prefix_rows_to_read": int(indices[-1] + 1),
            "stages": "report_only",
            "roles": str(part["report_role"].iloc[0]),
        })
        for index in indices.tolist():
            target_rows.append({
                "source_group": str(source),
                "source_cache_key": key,
                "recorded_index": int(index),
                "stage": "report_only",
                "role": str(part.loc[part["recorded_index"].eq(index), "report_role"].iloc[0]),
            })
    return pd.DataFrame(plan_rows), pd.DataFrame(target_rows)


def materialize(
    out: Path, tgn_extension: Path, base_plan: Path, base_targets: Path,
) -> dict[str, Any]:
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"refusing to overwrite non-empty CKBJ output: {out}")
    out.mkdir(parents=True, exist_ok=True)
    base_audit = validate_base_contract(base_plan, base_targets)
    targets, ckbi_audit = load_ckbi_targets(tgn_extension)
    plan, target_index = build_plan(targets)
    plan_path = out / "canonical_source_load_plan.csv"
    target_path = out / "canonical_source_target_index.csv"
    plan.to_csv(plan_path, index=False)
    target_index.to_csv(target_path, index=False)
    cache_dir = out / "c1_report_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    source_rows: list[dict[str, Any]] = []
    for source in plan["source_group"].astype(str).tolist():
        indices = np.sort(target_index.loc[target_index["source_group"].eq(source), "recorded_index"].astype(np.int64).unique())
        key = ckat.source_cache_key(source)
        cache = ckat.CanonicalTimeC1Cache(cko.GOTHAM_ZIP)
        features = cache.features_for_member(source, indices)
        audits = cache.audit_for_member(source)
        matrix = np.vstack([features[int(index)] for index in indices]).astype(np.float32)
        npz_path = cache_dir / f"{key}.npz"
        json_path = cache_dir / f"{key}.json"
        np.savez_compressed(npz_path, recorded_index=indices, features=matrix)
        target_audit = []
        for index in indices.tolist():
            item = dict(audits.get(int(index), {}))
            item["recorded_index"] = int(index)
            target_audit.append(item)
        payload = {
            "issue": ISSUE,
            "source_group": source,
            "source_cache_key": key,
            "feature_schema_hash": feature_schema_sha256(),
            "report_only": True,
            "raw_label_column_read": False,
            "source_audit": cache.audit_rows[-1] if cache.audit_rows else {},
            "target_audit": target_audit,
        }
        json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        aligned = sum(bool(item.get("alignment_ok", False)) for item in target_audit)
        source_rows.append({
            "source_group": source,
            "report_role": ckbi.EXTENSION_SOURCES[source],
            "source_cache_key": key,
            "target_rows": int(len(indices)),
            "aligned_target_rows": int(aligned),
            "target_positions_complete": bool(aligned == len(indices)),
            "raw_label_column_read": False,
            "report_only": True,
            "fit_select_rows_used": 0,
            "feature_schema_hash": feature_schema_sha256(),
            "npz_sha256": sha256_path(npz_path),
            "json_sha256": sha256_path(json_path),
        })
    manifest = pd.DataFrame(source_rows).sort_values("source_group", kind="mergesort").reset_index(drop=True)
    if not bool(manifest["target_positions_complete"].all()):
        raise RuntimeError("CKBJ canonical C1 report target alignment is incomplete")
    manifest_path = out / "c1_report_only_extension_manifest.csv"
    manifest.to_csv(manifest_path, index=False)
    manifest_hash = sha256_path(manifest_path)
    (out / "c1_report_only_extension_manifest_sha256.txt").write_text(manifest_hash + "\n", encoding="utf-8")
    ready = {
        "issue": ISSUE,
        "source_count": int(len(manifest)),
        "target_rows": int(manifest["target_rows"].sum()),
        "manifest_sha256": manifest_hash,
        "source_plan_sha256": sha256_path(plan_path),
        "target_index_sha256": sha256_path(target_path),
        "feature_schema_hash": feature_schema_sha256(),
        "raw_label_column_read": False,
        "report_only_fit_select_exclusion_pass": True,
        **base_audit,
        **ckbi_audit,
    }
    (out / "c1_report_extension_ready.json").write_text(json.dumps(ready, indent=2) + "\n", encoding="utf-8")
    return ready


def validate_extension(out: Path, tgn_extension: Path, base_plan: Path, base_targets: Path) -> dict[str, Any]:
    base_audit = validate_base_contract(base_plan, base_targets)
    targets, ckbi_audit = load_ckbi_targets(tgn_extension)
    ready_path = out / "c1_report_extension_ready.json"
    manifest_path = out / "c1_report_only_extension_manifest.csv"
    hash_path = out / "c1_report_only_extension_manifest_sha256.txt"
    plan_path = out / "canonical_source_load_plan.csv"
    target_path = out / "canonical_source_target_index.csv"
    if not all(path.is_file() for path in (ready_path, manifest_path, hash_path, plan_path, target_path)):
        raise RuntimeError("incomplete CKBJ C1 report extension")
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    manifest = pd.read_csv(manifest_path)
    actual_hash = sha256_path(manifest_path)
    if actual_hash != hash_path.read_text(encoding="utf-8").strip() or actual_hash != str(ready.get("manifest_sha256", "")):
        raise RuntimeError("CKBJ manifest hash mismatch")
    if set(manifest["source_group"].astype(str)) != set(ckbi.EXTENSION_SOURCES) or len(manifest) != 4:
        raise RuntimeError("CKBJ source boundary changed")
    if not _all_true(manifest["target_positions_complete"]) or not _all_false(manifest["raw_label_column_read"]):
        raise RuntimeError("CKBJ alignment/label-free contract failed")
    if int(pd.to_numeric(manifest["fit_select_rows_used"]).sum()) != 0:
        raise RuntimeError("CKBJ report extension entered fit/select")
    if int(manifest["target_rows"].sum()) != len(targets):
        raise RuntimeError("CKBJ target cardinality no longer matches CKBI")
    if sha256_path(plan_path) != str(ready.get("source_plan_sha256", "")) or sha256_path(target_path) != str(ready.get("target_index_sha256", "")):
        raise RuntimeError("CKBJ plan/target hash mismatch")
    cache_dir = out / "c1_report_cache"
    for row in manifest.itertuples(index=False):
        npz_path = cache_dir / f"{row.source_cache_key}.npz"
        json_path = cache_dir / f"{row.source_cache_key}.json"
        if not npz_path.is_file() or not json_path.is_file():
            raise RuntimeError(f"missing CKBJ source cache: {row.source_group}")
        if sha256_path(npz_path) != str(row.npz_sha256) or sha256_path(json_path) != str(row.json_sha256):
            raise RuntimeError(f"CKBJ source cache hash mismatch: {row.source_group}")
    return {**ready, **base_audit, **ckbi_audit, "extension_root": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--tgn-extension", default=str(DEFAULT_TGN_EXTENSION))
    parser.add_argument("--base-plan", required=True)
    parser.add_argument("--base-targets", required=True)
    parser.add_argument("--mode", choices=("materialize", "validate"), default="materialize")
    args = parser.parse_args()
    if args.mode == "materialize":
        result = materialize(Path(args.out), Path(args.tgn_extension), Path(args.base_plan), Path(args.base_targets))
    else:
        result = validate_extension(Path(args.out), Path(args.tgn_extension), Path(args.base_plan), Path(args.base_targets))
    print(json.dumps({"status": "ok", **result}, indent=2))


if __name__ == "__main__":
    main()
