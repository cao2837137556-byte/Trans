from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22"
ISSUE26A = ROOT / "runs" / "issue26a_within_dataset_temporal_validation_for_enhanced_lowguard_top64_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE23 = ROOT / "runs" / "issue23_locked_validation_for_enhanced_v2_top64_2026-05-18"
ISSUE22 = ROOT / "runs" / "issue22_v2_hard_shift_enhancement_pilot_2026-05-18"
ISSUE22B = ROOT / "runs" / "issue22b_enhanced_v2_primary_nonregression_check_2026-05-18"
ISSUE18 = ROOT / "runs" / "issue18_row_level_score_persistence_and_ood_target_sensitivity_2026-05-15"


FIELD_PATTERNS = {
    "contains_timestamp": [r"\btimestamp\b", r"\btime_stamp\b", r"\bwindow_start\b", r"\bwindow_end\b"],
    "contains_packet_order": [r"\bpacket_order\b", r"\bpacket_id\b", r"\bpacket_index\b"],
    "contains_bin_id": [r"\bbin_id\b", r"\beval_bins?\b", r"\btrain_bins?\b", r"\bholdout_bin_\d+\b"],
    "contains_row_id": [r"\brow_id\b", r"\bselected_attack_row_id\b", r"\boot?d_row_id\b"],
    "contains_split_label": [r"\bsplit\b", r"\bsplit_name\b", r"\btrain\b", r"\bcalib", r"\bvalidation\b", r"\beval\b"],
    "contains_support_id": [r"\bsupport_id\b", r"\bselected_attack_row_id\b", r"\bsupport_method\b"],
    "contains_eval_id": [r"\beval_id\b", r"\battack_eval\b", r"\bood_eval\b", r"\bfinal_ood_eval\b"],
    "contains_attack_family": [r"\battack_family\b", r"\battack_window\b", r"\bhigh_purity\b"],
    "contains_capture_id": [r"\bcapture_id\b", r"\bcapture\b"],
}


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def read_text_head(path: Path, max_bytes: int = 65536) -> str:
    try:
        if path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                return f.readline()
        if path.suffix.lower() in {".json", ".md", ".py", ".txt"}:
            data = path.read_bytes()[:max_bytes]
            return data.decode("utf-8", errors="replace")
    except Exception as exc:
        return f"READ_ERROR: {type(exc).__name__}: {exc}"
    return ""


def read_csv(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path)
    return pd.DataFrame()


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str] | None = None) -> None:
    if columns is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        columns = keys
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "NA") for key in columns})


def write_md(path: Path, content: str) -> None:
    path.write_text(content.strip() + "\n", encoding="utf-8")


def file_type(path: Path) -> str:
    suffix = path.suffix.lower().lstrip(".")
    return suffix or "unknown"


def bool_from_patterns(text: str, patterns: list[str]) -> bool:
    haystack = text.lower()
    return any(re.search(pattern, haystack, flags=re.IGNORECASE) for pattern in patterns)


def load_asset_report() -> pd.DataFrame:
    for path in [ISSUE25C / "locked_asset_report.csv", ISSUE23 / "locked_validation_asset_report.csv"]:
        if path.exists():
            return pd.read_csv(path)
    return pd.DataFrame()


def asset_lookup() -> dict[str, dict[str, Any]]:
    df = load_asset_report()
    out: dict[str, dict[str, Any]] = {}
    if not df.empty and "holdout_name" in df.columns:
        for row in df.to_dict(orient="records"):
            out[str(row["holdout_name"])] = row
    return out


def get_asset(name: str) -> dict[str, Any]:
    return asset_lookup().get(name, {})


def str_field(value: Any) -> str:
    if pd.isna(value):
        return "NA"
    return str(value)


def inspect_parquet_schema(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        df = pd.read_parquet(path)
        return ",".join(map(str, df.columns))
    except Exception as exc:
        return f"PARQUET_SCHEMA_READ_ERROR: {type(exc).__name__}: {exc}"


def build_metadata_source_inventory() -> list[dict[str, Any]]:
    roots = [ROOT / "runs", ROOT / "repo"]
    suffixes = {".csv", ".json", ".md", ".py", ".txt", ".parquet"}
    name_terms = re.compile(
        r"(manifest|config|run_spec|protocol|split|provenance|support|threshold|metadata|parquet|row|bin|timestamp|packet|capture|flow|asset|locked)",
        re.IGNORECASE,
    )
    priority_dirs = {
        ISSUE26A,
        ISSUE25C,
        ISSUE23,
        ISSUE22,
        ISSUE22B,
        ISSUE18,
        ROOT / "runs" / "issue19_lowguard_plus_representation_margin_repair_pilot_2026-05-18",
        ROOT / "runs" / "issue24b_adapter_bottleneck_diagnosis_for_enhanced_v2_top64_2026-05-18",
        ROOT / "runs" / "issue24c_v1_v2_residual_fusion_adapter_retry_2026-05-18",
    }

    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for base in roots:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            if any(part in {".git", "__pycache__"} for part in path.parts):
                continue
            is_priority = any(str(path).startswith(str(d)) for d in priority_dirs)
            if not is_priority and not name_terms.search(path.name):
                continue
            if path in seen:
                continue
            seen.add(path)
            text = inspect_parquet_schema(path) if path.suffix.lower() == ".parquet" else read_text_head(path)
            detection = {key: bool_from_patterns(text + "\n" + path.name, pats) for key, pats in FIELD_PATTERNS.items()}
            source_kind = "code" if path.suffix.lower() == ".py" else "artifact"
            temporal_usable = "yes" if (detection["contains_timestamp"] or detection["contains_packet_order"]) and source_kind == "artifact" else "partial" if detection["contains_bin_id"] and source_kind == "artifact" else "no"
            leakage_usable = "yes" if any(detection[k] for k in ["contains_row_id", "contains_split_label", "contains_support_id", "contains_eval_id", "contains_bin_id"]) and source_kind == "artifact" else "partial" if source_kind == "code" and any(detection.values()) else "no"
            notes = []
            if path.suffix.lower() == ".parquet":
                notes.append("parquet schema inspected; no full temporal split constructed")
            if source_kind == "code":
                notes.append("code-level evidence only")
            if temporal_usable == "partial":
                notes.append("bin/split metadata only; raw timestamp or packet-order missing")
            if not any(detection.values()):
                notes.append("no target metadata fields detected in header/head")
            rows.append(
                {
                    "source_path": rel(path),
                    "file_type": file_type(path),
                    **{key: yes_no(value) for key, value in detection.items()},
                    "usable_for_temporal_split": temporal_usable,
                    "usable_for_leakage_audit": leakage_usable,
                    "notes": "; ".join(notes) if notes else "metadata fields detected",
                }
            )
    rows.sort(key=lambda r: (0 if "issue26a" in r["source_path"] or "issue25c" in r["source_path"] or "issue23" in r["source_path"] else 1, r["source_path"]))
    return rows


def build_setting_provenance() -> list[dict[str, Any]]:
    assets = asset_lookup()

    def row(
        setting: str,
        bin_or_window: str,
        asset_name: str | None,
        used22: str,
        used22b: str,
        used23: str,
        used25c: str,
        clean: str,
        notes: str,
        used_feature: str = "yes, frozen top64 was selected before issue23/25c",
        used_support: str = "yes, kcenter32 support selected from setting-specific attack train pool",
        used_threshold: str = "yes, ID calibration + OOD validation only",
        adapter_choice: str = "no new adapter choice in issue26b; prior fixed LR adapter choice already frozen",
        timestamp: str = "no",
        packet_order: str = "partial, row_id/order and bin order only",
        bin_id: str = "yes",
    ) -> dict[str, Any]:
        asset = assets.get(asset_name or setting, {})
        train_bins = str_field(asset.get("train_bins", "NA"))
        eval_bins = str_field(asset.get("eval_bins", "NA"))
        train_count = str_field(asset.get("train_pool_count", "NA"))
        eval_count = str_field(asset.get("attack_eval_count", "NA"))
        return {
            "setting": setting,
            "bin_or_window": bin_or_window,
            "id_train_source": "issue22/23/25c script constants: x_id[:8000]",
            "id_calibration_source": "issue22/23/25c script constants: x_id[8000:13000]",
            "ood_train_source": "issue22/23/25c script constants: x_ood[:8000]",
            "ood_validation_source": "issue22/23/25c script constants: x_ood[8000:10000]",
            "ood_eval_source": "issue22/23/25c script constants: x_ood[10000:] report-only; row ids not fully persisted in issue25c",
            "attack_train_pool_source": f"asset report train_bins={train_bins}; train_pool_count={train_count}",
            "attack_support_source": "support_id_provenance/support_provenance selected_attack_row_id; no final eval selection",
            "attack_eval_source": f"asset report eval_bins={eval_bins}; attack_eval_count={eval_count}",
            "timestamp_available": timestamp,
            "packet_order_available": packet_order,
            "bin_id_available": bin_id,
            "used_for_feature_selection": used_feature,
            "used_for_support_selection": used_support,
            "used_for_threshold_calibration": used_threshold,
            "used_for_adapter_choice": adapter_choice,
            "used_for_issue22": used22,
            "used_for_issue22b": used22b,
            "used_for_issue23": used23,
            "used_for_issue25c": used25c,
            "clean_for_future_temporal_validation": clean,
            "notes": notes,
        }

    rows = [
        row(
            "primary_lowood",
            "primary same-protocol split",
            None,
            "yes, primary safety/non-regression evidence",
            "yes, primary non-regression",
            "yes, consistency context",
            "yes, consistency context",
            "no",
            "Primary evidence is already part of method discovery/confirmation; not a future temporal object.",
            bin_id="unknown/NA for attack temporal bins",
        ),
        row(
            "holdout_bin_2",
            "eval bin 2; train bins 3,4,5,6,7,8",
            "holdout_bin_2",
            "yes, direct issue22 top64 discovery eval",
            "no",
            "excluded, only consistency context",
            "yes, consistency context",
            "no",
            "Hard-shift discovery evidence only; cannot become clean temporal proof.",
        ),
        row(
            "chrono_late",
            "train bins 6,7,8; eval bins 2,3,4",
            "chrono_late_train_early_eval",
            "yes, issue22 chrono consistency/discovery confirmation",
            "no",
            "excluded, consistency only",
            "yes, consistency context",
            "no",
            "Temporal-looking but already used in candidate confirmation; consistency-only.",
        ),
        row(
            "locked_bin_5",
            "eval bin 5; train bins 2,3,4,6,7,8",
            "holdout_bin_5",
            "no direct issue22 discovery eval",
            "no",
            "yes, locked validation",
            "yes, strong-baseline locked evidence",
            "no",
            "Valid locked object already consumed by issue23/25c; future reuse is repeated locked-bin analysis.",
        ),
        row(
            "locked_bin_6",
            "eval bin 6; train bins 2,3,4,5,7,8",
            "holdout_bin_6",
            "no direct issue22 discovery eval",
            "no",
            "yes, locked validation",
            "yes, strong-baseline locked evidence",
            "no",
            "Valid locked object already consumed by issue23/25c; future reuse is repeated locked-bin analysis.",
        ),
        row(
            "locked_bin_7",
            "eval bin 7; train bins 2,3,4,5,6,8",
            "holdout_bin_7",
            "no direct issue22 discovery eval",
            "no",
            "yes, locked validation",
            "yes, strong-baseline locked evidence",
            "no",
            "Valid locked object already consumed by issue23/25c; future reuse is repeated locked-bin analysis.",
        ),
        row(
            "locked_bin_8",
            "eval bin 8; train bins 2,3,4,5,6,7",
            "holdout_bin_8",
            "no direct issue22 discovery eval",
            "no",
            "yes, locked validation",
            "yes, strong-baseline locked evidence",
            "no",
            "Valid locked object already consumed by issue23/25c; eval count is small and should carry a row-count caveat.",
        ),
        row(
            "chrono_early_train_late_eval candidate",
            "train bins 2,3,4; eval bins 6,7,8",
            "chrono_early_train_late_eval",
            "no direct issue22 discovery eval",
            "no",
            "overlaps eval bins 6,7,8 already locked",
            "overlaps issue25c locked evidence",
            "no",
            "Best partial temporal direction, but late eval bins overlap existing locked evidence; raw timestamp/purge metadata still missing.",
        ),
        row(
            "purged_future_window_holdout",
            "unknown future window",
            None,
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "Desired clean object, but no unused raw timestamp/packet-order/window manifest was recovered.",
            used_feature="unknown until raw asset is recovered",
            used_support="unknown until raw asset is recovered",
            used_threshold="no if constructed before final eval; currently not constructible",
            timestamp="no",
            packet_order="no",
            bin_id="unknown",
        ),
    ]
    return rows


def build_candidate_rebuild() -> list[dict[str, Any]]:
    assets = asset_lookup()
    hb5 = assets.get("holdout_bin_5", {})
    hb6 = assets.get("holdout_bin_6", {})
    hb7 = assets.get("holdout_bin_7", {})
    hb8 = assets.get("holdout_bin_8", {})
    late = assets.get("chrono_early_train_late_eval", {})

    def candidate(
        name: str,
        ctype: str,
        available: str,
        req_meta: str,
        train: str,
        cal: str,
        val: str,
        eval_: str,
        o22: str,
        o22b: str,
        o23: str,
        o25c: str,
        risk: str,
        purge: str,
        embargo: str,
        gap: str,
        sample: str,
        attack_eval: str,
        ood_eval: str,
        cost: str,
        slurm: str,
        priority: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "candidate_name": name,
            "candidate_type": ctype,
            "available": available,
            "required_metadata_available": req_meta,
            "train_bins_or_time": train,
            "cal_bins_or_time": cal,
            "val_bins_or_time": val,
            "eval_bins_or_time": eval_,
            "overlaps_issue22": o22,
            "overlaps_issue22b": o22b,
            "overlaps_issue23": o23,
            "overlaps_issue25c": o25c,
            "leakage_risk": risk,
            "purge_required": purge,
            "embargo_required": embargo,
            "recommended_gap": gap,
            "expected_sample_size": sample,
            "expected_attack_eval_size": attack_eval,
            "expected_ood_eval_size": ood_eval,
            "estimated_cost": cost,
            "requires_slurm": slurm,
            "priority": priority,
            "reason": reason,
        }

    return [
        candidate(
            "future-window holdout",
            "future_window_holdout",
            "no",
            "no, raw timestamp/window manifest not recovered",
            "NA",
            "ID/OOD calibration from existing benign slices only if pre-registered",
            "OOD validation only",
            "NA",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "yes",
            "yes",
            "unknown until raw timestamps/capture boundaries recovered",
            "NA",
            "NA",
            "NA",
            "medium for metadata scan; high for formal validation",
            "unknown for raw scan; yes for large formal matrix",
            "P2",
            "Scientifically preferred, but no unused future timestamp/window asset was recovered in issue26b.",
        ),
        candidate(
            "earlier-to-later",
            "chronological_cross_window",
            "partial",
            "partial, bin-level only",
            "bins 2,3,4",
            "existing ID/OOD calibration slices",
            "OOD validation",
            "bins 6,7,8",
            "no direct issue22 eval overlap",
            "no",
            "yes, eval bins already locked",
            "yes, eval bins already in issue25c locked evidence",
            "medium",
            "yes",
            "yes",
            "at least one bin or raw timestamp gap; exact gap unavailable",
            f"attack train pool {str_field(late.get('train_pool_count', '3426'))}; ID/OOD as 8000/5000/8000/2000",
            str_field(late.get("attack_eval_count", "2568")),
            "10000 if reusing final OOD eval report-only",
            "low for smoke; medium for formal",
            "no for metadata; unknown for formal",
            "P2",
            "Best partial temporal direction, but it is not clean because late eval bins were already used as locked evidence.",
        ),
        candidate(
            "later-to-earlier",
            "reverse_chronological_consistency",
            "yes",
            "partial, bin-level only",
            "bins 6,7,8",
            "existing ID/OOD calibration slices",
            "OOD validation",
            "bins 2,3,4",
            "yes",
            "no",
            "consistency only",
            "yes, consistency context",
            "high",
            "unknown",
            "unknown",
            "not applicable",
            "attack train pool 2568",
            "3426",
            "10000",
            "low",
            "no",
            "not_recommended",
            "Already used in issue22/25c discovery/consistency; cannot be formal temporal proof.",
        ),
        candidate(
            "rolling-origin validation",
            "rolling_origin",
            "partial",
            "no, raw timestamp/order and unused windows missing",
            "multiple origins unknown",
            "existing benign calibration possible only if pre-registered",
            "OOD validation",
            "future windows unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "yes",
            "yes",
            "must be pre-registered from raw time/capture boundaries",
            "NA",
            "NA",
            "NA",
            "medium_to_high",
            "yes if formal multi-origin",
            "P2",
            "Design is good, but current assets do not persist enough clean temporal metadata.",
        ),
        candidate(
            "leave-one-bin-out excluding used bins",
            "leave_one_bin_out",
            "no",
            "yes for bins 2-8 only; no unused bin remains",
            "NA",
            "existing ID/OOD calibration slices",
            "OOD validation",
            "no unused bin",
            "yes for bins 2/3/4",
            "no",
            "yes for bins 5/6/7/8",
            "yes",
            "high",
            "unknown",
            "unknown",
            "not applicable",
            "NA",
            "NA",
            "10000 if reused",
            "low",
            "no",
            "not_recommended",
            "All persisted bins are already discovery or locked evidence; no clean unused bin was found.",
        ),
        candidate(
            "adjacent-bin holdout with embargo",
            "adjacent_window_holdout",
            "partial",
            "partial, bin adjacency but not raw timestamp/session boundaries",
            "candidate-specific adjacent bins",
            "existing ID/OOD calibration slices",
            "OOD validation",
            "adjacent held-out bin",
            "unknown",
            "unknown",
            "likely if using bins 5-8",
            "likely",
            "medium_to_high",
            "yes",
            "yes",
            "one-bin coarse embargo recommended until timestamps recover",
            "varies by bin",
            "426 to 1348 depending bin; bin8 small",
            "10000 if reused",
            "medium",
            "unknown",
            "P3",
            "Adjacent-window contamination cannot be bounded with current metadata.",
        ),
        candidate(
            "purged temporal split",
            "purged_temporal_split",
            "no",
            "no, raw timestamp/packet-order/capture metadata not recovered",
            "NA",
            "NA",
            "NA",
            "NA",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "yes",
            "yes",
            "must be based on recovered raw time/capture boundary",
            "NA",
            "NA",
            "NA",
            "medium for metadata; high for formal",
            "unknown",
            "P2",
            "Cannot build without row-level time/order manifest.",
        ),
        candidate(
            "larger attack eval window",
            "data_scale_stress",
            "partial",
            "partial, existing bins can be pooled but already inspected",
            "existing train bins",
            "existing ID/OOD calibration slices",
            "OOD validation",
            "pooled known bins",
            "yes",
            "unknown",
            "yes",
            "yes",
            "high",
            "yes",
            "yes",
            "requires purge if time-adjacent",
            "could pool known bins but not clean",
            "up to 6871 across bins 2-8, not clean",
            "10000 if reused",
            "low_to_medium",
            "no for inventory",
            "not_recommended",
            "A pooled stress check may be appendix-only after clean validation; not a clean temporal candidate.",
        ),
        candidate(
            "new clean bin if metadata shows unused bin exists",
            "new_clean_bin",
            "no",
            "no new bin discovered",
            "NA",
            "NA",
            "NA",
            "NA",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "unknown",
            "NA",
            "NA",
            "NA",
            "NA",
            "unknown",
            "unknown",
            "not_recommended",
            "No unused attack bin beyond 2-8 was found in current persisted assets.",
        ),
    ]


def build_data_scale() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    assets = asset_lookup()

    def add(setting: str, asset_name: str | None, time_span: str, completeness: str, risk: str, notes: str) -> None:
        asset = assets.get(asset_name or "", {})
        rows.append(
            {
                "setting": setting,
                "id_train_rows": 8000,
                "id_calibration_rows": 5000,
                "ood_train_rows": 8000,
                "ood_validation_rows": 2000,
                "ood_eval_rows": 10000,
                "attack_train_pool_rows": str_field(asset.get("train_pool_count", "NA")),
                "attack_support_count": 32 if asset_name else "32/NA depending setting",
                "attack_eval_rows": str_field(asset.get("attack_eval_count", "NA")),
                "time_span": time_span,
                "bin_definition": f"train_bins={str_field(asset.get('train_bins', 'NA'))}; eval_bins={str_field(asset.get('eval_bins', 'NA'))}",
                "metadata_completeness": completeness,
                "sample_size_risk": risk,
                "notes": notes,
            }
        )

    add("primary_lowood", None, "NA; not a clean temporal object", "partial: split sizes known, raw time/bin not fully persisted", "medium", "Primary setting already used for method confirmation; exact attack train/eval row ids not fully persisted here.")
    add("holdout_bin_2", "holdout_bin_2", "bin-level only", "partial: bin and counts known, no raw timestamp", "medium", "Discovery hard holdout; not future-clean.")
    add("chrono_late_train_early_eval", "chrono_late_train_early_eval", "bin-level early/late order only", "partial: bin and counts known, no raw timestamp", "medium", "Consistency/discovery evidence only.")
    for b in [5, 6, 7, 8]:
        risk = "high" if b == 8 else "medium"
        add(f"locked_bin_{b}", f"holdout_bin_{b}", "bin-level only", "partial: bin and counts known, no raw timestamp", risk, "Already consumed by issue23/25c locked validation.")
    add("chrono_early_train_late_eval candidate", "chrono_early_train_late_eval", "bin-level early-to-late order only", "partial: bin and counts known, no raw timestamp/purge metadata", "medium", "Best partial candidate, but eval bins overlap issue23/25c locked bins.")
    return rows


def markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    if not rows:
        return ""
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join(["---"] * len(columns)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(col, "NA")).replace("|", "/") for col in columns) + " |")
    return "\n".join(lines)


def create_outputs() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    metadata_rows = build_metadata_source_inventory()
    provenance_rows = build_setting_provenance()
    candidate_rows = build_candidate_rebuild()
    data_rows = build_data_scale()

    write_csv(
        OUT / "metadata_source_inventory.csv",
        metadata_rows,
        [
            "source_path",
            "file_type",
            "contains_timestamp",
            "contains_packet_order",
            "contains_bin_id",
            "contains_row_id",
            "contains_split_label",
            "contains_support_id",
            "contains_eval_id",
            "contains_attack_family",
            "contains_capture_id",
            "usable_for_temporal_split",
            "usable_for_leakage_audit",
            "notes",
        ],
    )
    write_csv(OUT / "setting_provenance_reconstruction.csv", provenance_rows)
    write_csv(OUT / "temporal_asset_candidate_rebuild.csv", candidate_rows)
    write_csv(OUT / "recovered_data_scale_inventory.csv", data_rows)

    required_inputs = [
        ISSUE26A / "summary.md",
        ISSUE26A / "temporal_candidate_matrix.csv",
        ISSUE26A / "data_scale_temporal_inventory.csv",
        ISSUE26A / "leakage_audit_report.md",
        ISSUE26A / "issue26b_execution_plan.md",
        ROOT / "runs" / "mainline_docs" / "mainline_handoff.md",
        ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md",
    ]
    missing = [rel(p) for p in required_inputs if not p.exists()]
    if missing:
        write_md(OUT / "missing_input_report.md", "# Missing Input Report\n\nMissing mandatory inputs:\n\n" + "\n".join(f"- `{m}`" for m in missing))
    else:
        write_md(
            OUT / "missing_input_report.md",
            "# Missing Input Report\n\nNone for mandatory issue26b inputs. Raw timestamp / packet-order / capture-level temporal assets were not recovered; this is recorded as a metadata asset gap rather than a missing required handoff file.",
        )

    issue26a_summary = (ISSUE26A / "summary.md").read_text(encoding="utf-8", errors="replace") if (ISSUE26A / "summary.md").exists() else ""
    found_no_clean = "Clean new temporal candidate found: no" in issue26a_summary or "No clean P0/P1 temporal candidate" in issue26a_summary
    data_dirs_found = [str(p.name) for p in [ROOT / "runs", ROOT / "repo"] if p.exists()]
    timestamp_sources = [r for r in metadata_rows if r["contains_timestamp"] == "yes" and r["usable_for_temporal_split"] != "no"]
    packet_sources = [r for r in metadata_rows if r["contains_packet_order"] == "yes" and r["usable_for_temporal_split"] != "no"]
    bin_sources = [r for r in metadata_rows if r["contains_bin_id"] == "yes" and r["usable_for_temporal_split"] in {"yes", "partial"}]
    row_sources = [r for r in metadata_rows if r["contains_row_id"] == "yes"]

    preflight_rows = [
        ("1", "Read issue26a summary", yes_no((ISSUE26A / "summary.md").exists()), "issue26a summary was loaded."),
        ("2", "Confirm issue26a found no clean temporal candidate", yes_no(found_no_clean), "issue26a reports no clean P0/P1 low-leakage candidate."),
        ("3", "Confirm frozen main method", "yes", "Enhanced LOW-GUARD+ top64 remains frozen."),
        ("4", "Confirm no formal temporal validation this round", "yes", "issue26b is metadata recovery + asset build only."),
        ("5", "Find data directories", "partial", f"Found {', '.join(data_dirs_found)}; no standalone data/ directory in worktree root."),
        ("6", "Find split/bin/timestamp/row_id/support_id/eval_id files", "partial", f"bin_sources={len(bin_sources)}, row_sources={len(row_sources)}, timestamp_artifacts={len(timestamp_sources)}, packet_order_artifacts={len(packet_sources)}."),
        ("7", "Recover each setting time or bin provenance", "partial", "Recovered bin-level provenance and row/support/threshold provenance; raw timestamps not recovered."),
        ("8", "Judge method-discovery participation", "partial", "Can judge at setting/bin level from issue22/23/25c reports; not at full sample timestamp level."),
        ("9", "Need large parquet scan", "no for issue26b", "Only light schema/header inspection was performed; no large recomputation."),
        ("10", "Need Slurm", "no for issue26b", "Formal validation or large raw scans may need Slurm later."),
        ("11", "This round is metadata recovery + temporal asset build only", "yes", "No model training, no threshold tuning, no formal temporal validation."),
    ]
    write_md(
        OUT / "preflight_issue26b_check.md",
        "# Preflight Issue26b Check\n\n"
        + markdown_table(
            [{"id": a, "check": b, "status": c, "notes": d} for a, b, c, d in preflight_rows],
            ["id", "check", "status", "notes"],
        ),
    )

    smoke_candidates = [r for r in candidate_rows if r["candidate_name"] in {"earlier-to-later", "later-to-earlier"}]
    smoke_ok = all("bins" in str(r["train_bins_or_time"]) and "bins" in str(r["eval_bins_or_time"]) for r in smoke_candidates)
    write_md(
        OUT / "metadata_split_smoke_check.md",
        f"""# Metadata Split Smoke Check

Status: `metadata_only_smoke_completed`

- Candidate checked: `earlier-to-later` and existing reverse `later-to-earlier` bin definitions.
- What was checked: asset-report train/eval bin definitions load, attack train/eval counts are present, and known split labels can be reconstructed at bin level.
- Smoke pass: `{yes_no(smoke_ok)}`.
- Model training: no.
- Threshold selection: no.
- Final OOD/attack eval used for selection: no.
- Can enter formal validation directly: no.

Why not formal: this smoke only confirms bin-level metadata wiring. It did not recover raw timestamp, packet order, capture/session boundaries, or purge/embargo gap metadata, so it cannot support a clean formal temporal validation claim.
""",
    )

    write_md(
        OUT / "purge_embargo_plan.md",
        """# Purge / Embargo Plan

## Candidates Requiring Purge Or Embargo

- `earlier-to-later`: requires purge/embargo because train bins `2,3,4` and eval bins `6,7,8` are temporally ordered but raw boundary gaps are unknown.
- `future-window holdout`: requires purge/embargo if constructed from raw time or packet order.
- `adjacent-bin holdout with embargo`: requires both purge and embargo; adjacent-window contamination is the central risk.
- `rolling-origin validation`: requires pre-registered gaps around each origin.
- `larger attack eval window`: requires purge if it pools adjacent windows; not clean in current assets.

## Basis

Current artifacts recover bin-level ordering and support/threshold provenance, but they do not recover raw timestamp, packet order, flow/session/capture boundaries, or window_start/window_end. Therefore any numeric embargo gap would be speculative if set now.

## Recommended Gap

- If only bin metadata is available: use a conservative one-bin coarse embargo and report the resulting sample-size loss before running formal validation.
- If raw timestamps are recovered later: define the gap from capture/session adjacency before any final eval is touched.

## Feasibility

With currently persisted bins, a one-bin embargo may leave no unused clean late-window proof because bins `5/6/7/8` have already been consumed by issue23/25c locked evidence. That makes issue26c formal validation blocked until either raw unused windows are recovered or the protocol explicitly changes to a metadata follow-up / second-environment feasibility step.
""",
    )

    write_md(
        OUT / "slurm_need_assessment.md",
        """# Slurm Need Assessment

| field | value |
|---|---|
| task_name | issue26b_split_metadata_recovery_and_temporal_asset_build |
| local_feasible | yes |
| estimated_cost | low |
| requires_large_parquet_scan | no for this issue26b inventory |
| requires_multi_seed | no |
| requires_model_training | no |
| requires_slurm | no |
| recommended_partition_if_known | NA |
| recommended_time | NA |
| recommended_mem | NA |
| recommended_cpus | NA |
| recommended_log_paths | NA |
| reason | This round only scans existing manifests/provenance and writes planning artifacts. Slurm is only appropriate for large raw data scans or formal multi-seed issue26c validation after metadata is recovered. |
""",
    )
    write_md(
        OUT / "issue26c_slurm_plan_not_needed.md",
        """# Issue26c Slurm Plan Not Needed Yet

No formal Slurm task is recommended from issue26b because no clean formal temporal validation candidate is ready.

If a later metadata recovery step finds raw timestamps / packet-order / unused future windows, prepare a date-stamped `sbatch` script under the future issue26c run directory, with stdout/stderr named by job id and with `squeue` / `sacct` checks recorded. Do not run formal validation on a login node.
""",
    )

    write_md(
        OUT / "claim_update_after_issue26b.md",
        """# Claim Update After Issue26b

## Allowed after issue26b

- issue26b recovered and consolidated bin-level split provenance for primary, discovery, locked, and partial temporal candidates.
- issue26b confirmed support and threshold provenance: kcenter support does not use attack eval, and threshold selection uses ID calibration + OOD validation rather than final eval.
- issue26b identified that raw timestamp / packet-order / capture-level temporal metadata is still insufficient for a clean purged formal temporal split.

## Still not allowed

- Formal temporal validation succeeded.
- Temporal generalization is proven.
- External generalization is proven.
- All future drift is solved.
- Repeated locked-bin analysis is new temporal proof.

## Ready for issue26c

- No clean formal candidate is ready.
- A metadata follow-up can target raw timestamp / packet-order / capture/session manifest recovery, or the project can open a carefully scoped second-environment feasibility step.

## Needs issue27

- Second environment / external dataset validation remains necessary for external-validity claims.
""",
    )

    write_md(
        OUT / "reviewer_defense_metadata_temporal_split.md",
        """# Reviewer Defense: Metadata And Temporal Split

## Q1: Why did issue26a not run new temporal validation?

Because no P0/P1 low-leakage candidate existed. Running a reused locked bin would create the appearance of new evidence while actually being a consistency check.

## Q2: Why recover timestamp / packet-order / bin provenance?

Temporal validation needs a defensible chronology. Bin names alone show coarse ordering but cannot rule out adjacent-window contamination, near-duplicate flows, or session leakage.

## Q3: How do you avoid repeated locked-bin analysis being written as new evidence?

Bins `5/6/7/8` are marked as already consumed by issue23 and issue25c. Future reuse is consistency or robustness checking, not clean proof.

## Q4: How do you avoid adjacent-window contamination?

By requiring purge/embargo before formal validation. Since raw timestamps and capture boundaries are missing, issue26b does not choose a numeric gap.

## Q5: If a clean candidate does not exist, what happens to the paper?

The within-dataset temporal claim remains pending. The paper can still use issue23/25c as same-dataset locked evidence, but must state the temporal/external-validity limitation and run a metadata follow-up or second-environment feasibility step.

## Q6: How does metadata recovery lead to formal temporal validation?

It defines which windows are train/cal/val/eval, whether they were previously used, and how purge/embargo will be set before final metrics are touched.

## Q7: Why is second environment still needed?

Within-dataset temporal evidence cannot establish external generalization. A second environment is still needed for issue27-level external-validity claims.

## Q8: Is more data needed?

Likely yes for a clean temporal claim. The weakest existing locked bin has only 426 attack eval rows, and no unused future window was recovered.

## Q9: Is Slurm needed?

Not for issue26b. Slurm becomes relevant for large raw scans or formal multi-seed validation after the split protocol is frozen.
""",
    )

    write_md(
        OUT / "issue26c_execution_plan.md",
        """# Issue26c Execution Plan

## Recommended Issue26c Action

`issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`

## Why

Issue26b recovered bin-level provenance and support/threshold provenance, but not enough raw timestamp / packet-order / capture metadata to construct a low-leakage clean temporal validation object.

## Candidate Status

- `earlier-to-later`: partial, not clean; eval bins overlap issue23/25c locked evidence.
- `future-window holdout`: scientifically preferred, but unavailable until raw temporal metadata is recovered.
- `purged temporal split`: blocked by missing timestamp/order/capture metadata.

## Inputs Needed

- Raw stage2 manifest with row-level timestamp or packet order.
- Bin-to-time or capture-window mapping.
- Full attack eval row list per bin.
- ID/OOD benign split manifests with train/cal/val/eval labels.
- Pre-registered purge/embargo rule.

## Purge / Embargo

Required for any adjacent or future-window temporal split. Do not tune gap size on final eval metrics.

## Slurm

Not needed until a clean formal candidate is available. If raw manifests are large, do only a small local schema smoke and prepare Slurm for the full scan.

## Proposed Seeds For Future Formal Validation

- Smoke: `42`.
- Formal: `42,43,44,45,46`.
- Heldout robustness after smoke: `47,48,49,50,51`.

## Output File Plan

Future issue26c should write: `temporal_split_manifest.csv`, `support_provenance.csv`, `threshold_provenance.csv`, `method_comparison_by_seed.csv`, `method_comparison_summary.csv`, `leakage_audit_report.md`, `command.txt`, `config.json`, `run_spec.json`, and `manifest.csv`.
""",
    )

    write_md(
        OUT / "claim_boundary.md",
        """# Claim Boundary

## Can Say

- issue26b inventories and consolidates split metadata needed for within-dataset temporal validation.
- issue26b recovers bin-level provenance for known primary, discovery, locked, and partial temporal settings.
- issue26b audits support and threshold provenance and confirms final eval is not used for threshold/support selection in the inspected assets.
- issue26b prepares the next issue26c decision point.

## Cannot Say

- issue26b proves temporal generalization.
- issue26b proves external generalization.
- issue26b completes formal temporal validation.
- issue26b replaces second-environment evidence.
- issue26b permits topK/support/adapter/threshold tuning.
- Reusing issue23/25c locked bins is a clean new temporal proof.
""",
    )

    risk_rows = [
        ("repeated locked-bin analysis risk", "high", "Bins 5/6/7/8 already support issue23/25c.", "Label reuse as consistency-only."),
        ("temporal leakage risk", "medium", "Raw timestamp/order not recovered.", "Block formal validation until raw metadata exists."),
        ("adjacent-window contamination risk", "medium", "Coarse bins may contain near-adjacent traffic.", "Require purge/embargo."),
        ("insufficient metadata risk", "high", "No raw timestamp/packet-order/capture manifest recovered.", "Run metadata follow-up or second-environment feasibility."),
        ("small attack eval risk", "medium", "holdout_bin_8 has 426 attack eval rows.", "Report row-count caveats."),
        ("small OOD eval risk", "low", "Existing OOD eval has about 10000 rows.", "Keep report-only and preserve protocol."),
        ("single-domain risk", "high", "issue26b is within-dataset only.", "Keep issue27 second environment as needed."),
        ("no second environment risk", "high", "Within-dataset temporal asset does not prove external validity.", "Do not remove issue27."),
        ("final eval leakage risk", "medium", "Future metadata work might be tempted to inspect final eval.", "Pre-register splits and use final eval report-only."),
        ("Slurm misuse risk", "medium", "Large scans/formal multi-seed could be too heavy locally.", "Use local smoke then sbatch."),
    ]
    write_csv(OUT / "risk_register.csv", [{"risk_name": a, "severity": b, "reason": c, "mitigation": d} for a, b, c, d in risk_rows])

    write_md(
        OUT / "recommended_next_action.md",
        """# Recommended Next Action

Unique next action:

`issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`

Reason: issue26b did not recover enough raw timestamp / packet-order / capture-level metadata to build a clean formal temporal validation object. The best partial candidate remains `earlier-to-later`, but it overlaps issue23/25c locked evidence and needs purge/embargo metadata before it can be considered formal.

Do not recommend model changes, topK search, adapter tuning, support-budget tuning, routing, promotion, or frontend-f2 reopening.
""",
    )

    write_md(
        OUT / "summary.md",
        """# Issue26b Split Metadata Recovery And Temporal Asset Build Summary

## Outcome

- Task type: split metadata recovery + clean temporal asset build.
- Formal temporal validation executed: no.
- Model training executed: no.
- TopK/support/adapter/threshold changed: no.
- Final OOD/attack eval used for selection: no.
- Slurm used: no.

## 1. Was timestamp / packet-order / bin provenance recovered?

- Bin provenance: yes, at coarse attack-bin level from issue23/25c asset reports.
- Row/support provenance: partial, through support provenance and issue18 row-level score artifacts.
- Threshold provenance: yes, inspected assets record ID calibration + OOD validation and no final eval use.
- Raw timestamp / packet-order / capture/session provenance: no. Source code supports timestamp extraction, but current run assets do not persist a row-level timestamp or packet-order manifest for formal temporal splitting.

## 2. Available Metadata

- `locked_asset_report.csv` / `locked_validation_asset_report.csv`: train/eval bins, attack train-pool counts, attack eval counts.
- `support_provenance.csv` / `support_id_provenance.csv`: selected attack row IDs and no attack-eval/final-OOD selection flags.
- `threshold_provenance.csv`: threshold source and no final-eval threshold selection.
- issue18 `row_level_scores.parquet`: row-level score IDs for older holdout_bin_2 and chrono_late diagnostics only.

## 3. Missing Metadata

- Raw packet timestamp.
- Packet order or packet index for all current candidate rows.
- window_start / window_end.
- capture_id / flow_id / session boundary.
- Full final attack/OOD eval row manifests for new unused temporal windows.
- Bin-to-clock-time mapping.

## 4. Clean Temporal Candidate

No clean candidate was found. `earlier-to-later` remains partial, but its eval bins `6/7/8` overlap issue23/25c locked evidence. With current metadata, it is a consistency/planning object, not a clean formal temporal proof.

## 5. Recommended Issue26c Candidate

No formal candidate is ready. The recommended next action is `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.

## 6. Purge / Embargo

Required for any future chronological or adjacent-window validation. A numeric gap cannot be responsibly fixed until raw timestamp/order/capture metadata is recovered.

## 7. Sample Size

Existing split sizes are recoverable at coarse level: ID train 8000, ID calibration 5000, OOD train 8000, OOD validation 2000, OOD eval about 10000. Attack eval size varies; locked bin 8 remains small at 426 rows.

## 8. Slurm

Not needed for issue26b. Slurm may be needed only for a large raw metadata scan or future formal multi-seed temporal validation.

## 9. Claim Change

The temporal claim does not become stronger. issue26b strengthens provenance hygiene and defines the blocker: current assets are good enough for bin-level audit, but not enough for clean purged temporal proof.

## 10. Next Step

Unique next step: `issue26c_temporal_metadata_recovery_followup_or_second_environment_feasibility`.
""",
    )

    config = {
        "run": "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "task_type": "metadata_recovery_and_temporal_asset_build",
        "formal_temporal_validation": False,
        "model_training": False,
        "main_method_frozen": "Enhanced LOW-GUARD+ top64",
        "topk_changed": False,
        "support_budget_changed": False,
        "adapter_changed": False,
        "threshold_protocol_changed": False,
        "final_eval_used_for_selection": False,
        "second_environment_opened": False,
        "outputs": [
            "summary.md",
            "preflight_issue26b_check.md",
            "missing_input_report.md",
            "metadata_source_inventory.csv",
            "setting_provenance_reconstruction.csv",
            "temporal_asset_candidate_rebuild.csv",
            "purge_embargo_plan.md",
            "recovered_data_scale_inventory.csv",
            "metadata_split_smoke_check.md",
            "slurm_need_assessment.md",
            "issue26c_slurm_plan_not_needed.md",
            "claim_update_after_issue26b.md",
            "reviewer_defense_metadata_temporal_split.md",
            "issue26c_execution_plan.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "claim_boundary.md",
            "risk_register.csv",
            "recommended_next_action.md",
            "manifest.csv",
        ],
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

    run_spec = {
        "issue": "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22",
        "question": "Can existing assets recover enough temporal metadata to build a clean formal temporal validation candidate?",
        "serves_claim": "Prepares, but does not prove, within-dataset temporal validation for Enhanced LOW-GUARD+ top64.",
        "reviewer_attack_defended": [
            "one-dataset repeated tuning",
            "repeated locked-bin evidence presented as new proof",
            "temporal leakage",
            "final eval leakage",
        ],
        "success_interpretation": "Clean raw timestamp/order provenance found and an unused candidate can be pre-registered.",
        "failure_interpretation": "Temporal validation remains blocked; use metadata follow-up or second-environment feasibility.",
        "paper_destination": "appendix/provenance and experiment planning; not main result",
        "leakage_controls": [
            "no final eval selection",
            "no topK/support/adapter/threshold tuning",
            "no model training",
            "formal validation blocked unless clean metadata exists",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")

    write_md(
        OUT / "command.txt",
        """git branch --show-current
git status --short
Get-Content issue26a required files
Get-Content mainline docs
rg / Get-ChildItem metadata and provenance scans under runs/repo
Get-Content key issue22/23/25c support, threshold, asset, config, manifest files
python schema check for issue18 row_level_scores.parquet
python runs/issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22/generate_issue26b_outputs.py
apply_patch runs/mainline_docs/mainline_handoff.md issue26b append
apply_patch runs/mainline_docs/mainline_experiment_map.md issue26b append
""",
    )

    # Build manifest after all files except manifest itself are written.
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"file": path.name, "size_bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows, ["file", "size_bytes"])


if __name__ == "__main__":
    create_outputs()
