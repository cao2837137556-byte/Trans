from __future__ import annotations

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

import numpy as np


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
KITNET = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
OUT = REPO / "runs" / "issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27"

FULL_MIRAI = KITNET / "Mirai_dataset.csv"
FULL_LABELS = KITNET / "mirai_labels.csv"
MY_GOLD = KITNET / "my_gold_mirai.csv"
MY_GOLD_LABELS = KITNET / "my_gold_labels.npy"
OFFICIAL_100K = KITNET / "mirai3.csv"
OFFICIAL_TS = KITNET / "mirai3_ts.csv"
OFFICIAL_LABELS = KITNET / "official_labels.npy"
CLEAN_STAGE = KITNET / "runs" / "csv_input_clean_stage1_2026-03-23"
CLEAN115 = CLEAN_STAGE / "data" / "my_gold_mirai_clean115.csv"
CLEAN115_LABELS = CLEAN_STAGE / "data" / "my_gold_labels_copy.npy"
ORIGINAL100_HEADERS = (
    KITNET
    / "runs"
    / "frontend100_crosscapture_stage1_2026-03-25"
    / "extract_id_7_6"
    / "feature_headers.txt"
)
ISSUE27L = REPO / "runs" / "issue27l_sufficient_clean_eval_asset_and_split_aware_original100_rebuild_for_lowguard_plus_plus_2026-05-27"
ISSUE27K = REPO / "runs" / "issue27k_row_level_original100_rebuild_and_purged_split_construction_for_lowguard_plus_plus_2026-05-27"
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"


def ensure_out() -> None:
    OUT.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "NA") for k in fieldnames})


def write_text(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def file_hash(path: Path, max_bytes: int = 4 * 1024 * 1024) -> str:
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max_bytes
        while remaining > 0:
            chunk = f.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)
    return f"sha256_first_{max_bytes}_bytes:{h.hexdigest()}"


def count_lines(path: Path) -> int | str:
    if not path.exists():
        return "missing"
    count = 0
    with path.open("rb") as f:
        for _ in f:
            count += 1
    return count


def first_csv_row(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        return next(reader, [])


def sample_first_column(path: Path, n: int = 1000) -> list[float]:
    values: list[float] = []
    if not path.exists():
        return values
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i >= n:
                break
            if not row:
                continue
            try:
                values.append(float(row[0]))
            except ValueError:
                pass
    return values


def is_index_like(vals: list[float]) -> bool:
    if len(vals) < 10:
        return False
    return all(abs(v - i) < 1e-9 for i, v in enumerate(vals[: min(len(vals), 1000)]))


def np_label_counts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"rows": "missing", "benign": "missing", "attack": "missing"}
    arr = np.load(path)
    c = Counter(arr.astype(int).tolist())
    return {"rows": int(arr.shape[0]), "benign": int(c.get(0, 0)), "attack": int(c.get(1, 0))}


def csv_label_counts(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"rows": "missing", "benign": "missing", "attack": "missing"}
    vals = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                vals.append(int(float(s.split(",")[0])))
            except ValueError:
                continue
    c = Counter(vals)
    return {"rows": len(vals), "benign": c.get(0, 0), "attack": c.get(1, 0)}


def label_transition_summary(path: Path, npy: bool = False) -> dict[str, Any]:
    if not path.exists():
        return {"transition_summary": "missing"}
    if npy:
        labels = np.load(path).astype(int)
    else:
        labels = np.array([int(float(line.strip().split(",")[0])) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])
    changes = np.where(labels[1:] != labels[:-1])[0] + 1
    first_attack = int(np.argmax(labels == 1)) if np.any(labels == 1) else -1
    first_benign_after_attack = -1
    if first_attack >= 0:
        later = np.where(labels[first_attack:] == 0)[0]
        if later.size:
            first_benign_after_attack = int(first_attack + later[0])
    chunks = []
    for start in range(0, len(labels), max(1, len(labels) // 10)):
        end = min(len(labels), start + max(1, len(labels) // 10))
        c = Counter(labels[start:end].tolist())
        chunks.append(f"{start}:{end}:b{c.get(0,0)}_a{c.get(1,0)}")
    return {
        "first_attack_row": first_attack,
        "first_benign_after_attack_row": first_benign_after_attack,
        "num_label_transitions": int(changes.size),
        "first_transitions": ";".join(map(str, changes[:10])),
        "decile_counts": "|".join(chunks[:10]),
    }


def read_headers(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]


def path_rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def asset_identity_rows() -> list[dict[str, Any]]:
    assets = [
        {
            "asset_name": "full_mirai_labeled_feature_csv",
            "asset_path": FULL_MIRAI,
            "label_path": FULL_LABELS,
            "label_type": "csv_0_benign_1_attack",
            "asset_role": "largest labeled Mirai/Botnet feature matrix",
        },
        {
            "asset_name": "my_gold_mirai_200k_labeled_feature_csv",
            "asset_path": MY_GOLD,
            "label_path": MY_GOLD_LABELS,
            "label_type": "npy_0_benign_1_attack",
            "asset_role": "historical clean115 source subset after dropping index-like col0",
        },
        {
            "asset_name": "official_mirai_100k_with_timestamp",
            "asset_path": OFFICIAL_100K,
            "label_path": OFFICIAL_LABELS,
            "timestamp_path": OFFICIAL_TS,
            "label_type": "npy_0_benign_1_attack",
            "asset_role": "timestamp-sidecar 100k labeled feature matrix",
        },
        {
            "asset_name": "clean115_my_gold_stage1",
            "asset_path": CLEAN115,
            "label_path": CLEAN115_LABELS,
            "label_type": "npy_0_benign_1_attack",
            "asset_role": "clean115 historical cleaned subset",
        },
    ]
    rows = []
    for a in assets:
        p = Path(a["asset_path"])
        first = first_csv_row(p)
        dim = len(first) if first else "missing"
        fc = sample_first_column(p, 1000)
        if str(a["label_path"]).endswith(".npy"):
            counts = np_label_counts(Path(a["label_path"]))
            trans = label_transition_summary(Path(a["label_path"]), npy=True) if Path(a["label_path"]).exists() else {}
        else:
            counts = csv_label_counts(Path(a["label_path"]))
            trans = label_transition_summary(Path(a["label_path"]), npy=False) if Path(a["label_path"]).exists() else {}
        timestamp_path = Path(a.get("timestamp_path", ""))
        timestamp_exists = bool(a.get("timestamp_path")) and timestamp_path.exists()
        rows.append(
            {
                "asset_name": a["asset_name"],
                "asset_path": str(p),
                "file_type": p.suffix.lower().lstrip(".") or "unknown",
                "exists": p.exists(),
                "file_size_bytes": p.stat().st_size if p.exists() else "missing",
                "row_count": counts.get("rows", count_lines(p)),
                "column_count": dim,
                "benign_count": counts.get("benign", "NA"),
                "attack_count": counts.get("attack", "NA"),
                "label_column_name": "sidecar_label",
                "label_path": str(a["label_path"]),
                "timestamp_column_or_sidecar": str(timestamp_path) if timestamp_exists else "not_explicit",
                "timestamp_present": timestamp_exists,
                "packet_order_or_row_id_present": "implicit_row_order",
                "capture_or_session_id_present": False,
                "feature_names_present": False,
                "is_original100": dim == 100,
                "is_possible_restored115": dim == 115,
                "is_dirty116_with_index_col": dim == 116 and is_index_like(fc),
                "is_other_feature_schema": dim not in (100, 115, 116),
                "raw_pcap_traceable": False,
                "feature_cache_present": True,
                "label_mapping_present": Path(a["label_path"]).exists(),
                "metadata_sidecar_present": a["asset_name"] == "clean115_my_gold_stage1",
                "checksum_or_file_hash": file_hash(p),
                **trans,
                "notes": a["asset_role"],
            }
        )
    return rows


def compatibility_rows(headers100: list[str]) -> list[dict[str, Any]]:
    top3 = ["HH_0.01_radius_0_1", "HH_0.01_magnitude_0_1", "HH_0.1_radius_0_1"]
    common = {
        "current_lowguardpp_expected_representation": "original100",
        "expected_dim": 100,
        "frozen_config_id": "histgb_d2_lr005_l2p1_ood4_sup4_t0050",
        "ood_target": 0.01,
    }
    rows = [
        {
            **common,
            "asset_name": "full_mirai_labeled_feature_csv",
            "observed_dim": len(first_csv_row(FULL_MIRAI)),
            "feature_names_available": False,
            "has_index_like_col0": is_index_like(sample_first_column(FULL_MIRAI)),
            "matches_original100_dim": False,
            "matches_restored115_dim_after_drop": True,
            "hh_radius_lambda_0_01_name_confirmed": False,
            "hh_magnitude_lambda_0_01_name_confirmed": False,
            "hh_radius_lambda_0_1_name_confirmed": False,
            "mi_hh_hhjit_hphp_family_recognizable": "unknown_without_header",
            "lambda_scales_consistent": "unknown_without_header",
            "feature_order_consistent": "unknown_without_mapping",
            "label_like_split_like_index_like_feature": "col0 index-like if not dropped",
            "missing_constant_nan_inf_risk": "not fully scanned; needs numeric audit before eval",
            "needs_netstat_afterimage_reextract": "yes_for_original100; no_or_unknown_for_clean115",
            "restored115_possible": True,
            "compatibility_verdict": "incompatible_needs_reextraction",
            "minimum_fix": "drop index-like col0 for clean115/restored115 path, or re-run Kitsune frontend to produce current original100-compatible features with explicit mapping",
        },
        {
            **common,
            "asset_name": "official_mirai_100k_with_timestamp",
            "observed_dim": len(first_csv_row(OFFICIAL_100K)),
            "feature_names_available": False,
            "has_index_like_col0": is_index_like(sample_first_column(OFFICIAL_100K)),
            "matches_original100_dim": False,
            "matches_restored115_dim_after_drop": True,
            "hh_radius_lambda_0_01_name_confirmed": False,
            "hh_magnitude_lambda_0_01_name_confirmed": False,
            "hh_radius_lambda_0_1_name_confirmed": False,
            "mi_hh_hhjit_hphp_family_recognizable": "unknown_without_header",
            "lambda_scales_consistent": "unknown_without_header",
            "feature_order_consistent": "unknown_without_mapping",
            "label_like_split_like_index_like_feature": "no index-like col0 detected in sample",
            "missing_constant_nan_inf_risk": "not fully scanned; needs numeric audit before eval",
            "needs_netstat_afterimage_reextract": "yes_for_original100; existing matrix may support restored115 if mapping is recovered",
            "restored115_possible": True,
            "compatibility_verdict": "compatible_restored115",
            "minimum_fix": "recover feature-name/order mapping and define restored115 LOW-GUARD++ input; do not mix with frozen original100 claim",
        },
        {
            **common,
            "asset_name": "clean115_my_gold_stage1",
            "observed_dim": len(first_csv_row(CLEAN115)),
            "feature_names_available": False,
            "has_index_like_col0": is_index_like(sample_first_column(CLEAN115)),
            "matches_original100_dim": False,
            "matches_restored115_dim_after_drop": True,
            "hh_radius_lambda_0_01_name_confirmed": False,
            "hh_magnitude_lambda_0_01_name_confirmed": False,
            "hh_radius_lambda_0_1_name_confirmed": False,
            "mi_hh_hhjit_hphp_family_recognizable": "historically_clean115_not_original100",
            "lambda_scales_consistent": "unknown_without_header",
            "feature_order_consistent": "unknown_without_mapping",
            "label_like_split_like_index_like_feature": "index col removed in prior stage",
            "missing_constant_nan_inf_risk": "historical clean stage did ID-only checks; needs full numeric audit before eval",
            "needs_netstat_afterimage_reextract": "yes_for_original100",
            "restored115_possible": True,
            "compatibility_verdict": "compatible_restored115",
            "minimum_fix": "treat as separate clean115/restored115 representation line, not frozen original100 LOW-GUARD++",
        },
        {
            **common,
            "asset_name": "current_original100_header_reference",
            "observed_dim": len(headers100),
            "feature_names_available": True,
            "has_index_like_col0": False,
            "matches_original100_dim": len(headers100) == 100,
            "matches_restored115_dim_after_drop": False,
            "hh_radius_lambda_0_01_name_confirmed": top3[0] in headers100,
            "hh_magnitude_lambda_0_01_name_confirmed": top3[1] in headers100,
            "hh_radius_lambda_0_1_name_confirmed": top3[2] in headers100,
            "mi_hh_hhjit_hphp_family_recognizable": True,
            "lambda_scales_consistent": True,
            "feature_order_consistent": "reference_only",
            "label_like_split_like_index_like_feature": False,
            "missing_constant_nan_inf_risk": "NA",
            "needs_netstat_afterimage_reextract": False,
            "restored115_possible": False,
            "compatibility_verdict": "compatible_original100_reference_only",
            "minimum_fix": "use this header/order target when re-extracting full Mirai to original100",
        },
    ]
    return rows


def prior_use_rows() -> list[dict[str, Any]]:
    checks = [
        ("issue27f_formal_lowguardpp", "runs/issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27", "no full Mirai path found in required summaries; used current original100 locked assets"),
        ("issue27g_anomaly_audit", "runs/issue27g_suspicious_perfect_score_audit_for_lowguard_plus_plus_2026-05-27", "audited current original100 result; no full Mirai clean115 path used for config/support/threshold"),
        ("issue27h_separator_audit", "runs/issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27", "separator provenance/ablation on current original100; no full Mirai use for LOW-GUARD++ selection"),
        ("issue27i_nonlocked_consistency", "runs/issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27", "included full asset inventory only after issue27l request; consistency assets were not full Mirai clean eval"),
        ("issue27k_row_manifest_80k", "runs/issue27k_row_level_original100_rebuild_and_purged_split_construction_for_lowguard_plus_plus_2026-05-27", "80k manifest is separate ID/OOD/attack cache; no row-level overlap established with full Mirai"),
        ("issue27l_asset_inventory", "runs/issue27l_sufficient_clean_eval_asset_and_split_aware_original100_rebuild_for_lowguard_plus_plus_2026-05-27", "inventory and split feasibility only; no score-based selection or eval"),
        ("historical_csv_input_clean_stage1", str(CLEAN_STAGE), "prior historical clean115/dirty116 cleaning and ID-only checks used my_gold subset; not current LOW-GUARD++ selection"),
    ]
    rows = []
    for name, path, notes in checks:
        rows.append(
            {
                "audit_target": name,
                "path": path,
                "full_mirai_row_overlap_detected": "unknown_without_global_row_id" if "historical" in name or "80k" in name else "not_detected_from_docs",
                "used_for_issue27f_locked_eval": name == "issue27f_formal_lowguardpp",
                "used_for_issue27g_anomaly_audit": name == "issue27g_anomaly_audit",
                "used_for_issue27h_separator_audit": name == "issue27h_separator_audit",
                "used_for_issue27i_nonlocked_consistency": name == "issue27i_nonlocked_consistency",
                "used_for_issue27k_80k_manifest": name == "issue27k_row_manifest_80k",
                "used_for_kcenter32_support": False,
                "used_for_ood_val_threshold": False,
                "used_for_final_ood_eval": False,
                "used_for_config_freeze": False,
                "used_for_feature_selection_separator_discovery": False,
                "can_be_clean_report_eval_after_removing_overlap": "yes_if_restored115/original100 path is defined and historical my_gold rows are excluded",
                "contamination_verdict": "historical_clean115_use_present_not_lowguardpp_selection" if "historical" in name else "no_prior_use_detected_for_lowguardpp_selection",
                "notes": notes,
            }
        )
    return rows


def split_rows() -> list[dict[str, Any]]:
    full_counts = csv_label_counts(FULL_LABELS)
    official_counts = np_label_counts(OFFICIAL_LABELS)
    my_counts = np_label_counts(MY_GOLD_LABELS)
    return [
        {
            "candidate_name": "full_mirai_row_order_clean115_or_restored115_split",
            "asset": str(FULL_MIRAI),
            "total_rows": full_counts["rows"],
            "benign_rows": full_counts["benign"],
            "attack_rows": full_counts["attack"],
            "can_construct_id_benign_train": True,
            "can_construct_ood_benign_train": True,
            "can_construct_id_calib": True,
            "can_construct_ood_val": True,
            "can_construct_final_ood_eval": True,
            "can_construct_attack_support_pool": True,
            "can_construct_kcenter32_candidate": "yes after compatible feature matrix is defined",
            "can_construct_attack_eval": True,
            "support_eval_disjoint_possible": True,
            "timestamp_available": False,
            "capture_session_available": False,
            "purge_gap_possible": "row_order_only_not_timestamp",
            "low_alert_threshold_possible": True,
            "protocol_reproducible": "blocked_for_current_original100; feasible for clean115/restored115 after representation decision",
            "evidence_level": "large_labeled_dataset_candidate_pending_frontend_compatibility",
            "notes": "Enough benign/attack rows for ID/OOD/support/eval; no explicit timestamp/capture id in full asset.",
        },
        {
            "candidate_name": "official_mirai_100k_timestamp_split",
            "asset": str(OFFICIAL_100K),
            "total_rows": official_counts["rows"],
            "benign_rows": official_counts["benign"],
            "attack_rows": official_counts["attack"],
            "can_construct_id_benign_train": True,
            "can_construct_ood_benign_train": True,
            "can_construct_id_calib": True,
            "can_construct_ood_val": True,
            "can_construct_final_ood_eval": True,
            "can_construct_attack_support_pool": True,
            "can_construct_kcenter32_candidate": "yes after compatible feature matrix is defined",
            "can_construct_attack_eval": True,
            "support_eval_disjoint_possible": True,
            "timestamp_available": True,
            "capture_session_available": False,
            "purge_gap_possible": True,
            "low_alert_threshold_possible": True,
            "protocol_reproducible": "blocked_for_current_original100; good timestamp candidate for restored115 path",
            "evidence_level": "timestamped_large_candidate_pending_feature_mapping",
            "notes": "Smaller but timestamped; useful for split-aware prototype once feature mapping is recovered.",
        },
        {
            "candidate_name": "my_gold_clean115_200k_split",
            "asset": str(MY_GOLD),
            "total_rows": my_counts["rows"],
            "benign_rows": my_counts["benign"],
            "attack_rows": my_counts["attack"],
            "can_construct_id_benign_train": True,
            "can_construct_ood_benign_train": True,
            "can_construct_id_calib": True,
            "can_construct_ood_val": True,
            "can_construct_final_ood_eval": True,
            "can_construct_attack_support_pool": True,
            "can_construct_kcenter32_candidate": "yes after compatible feature matrix is defined",
            "can_construct_attack_eval": True,
            "support_eval_disjoint_possible": True,
            "timestamp_available": False,
            "capture_session_available": False,
            "purge_gap_possible": "row_order_only_not_timestamp",
            "low_alert_threshold_possible": True,
            "protocol_reproducible": "historical clean115 subset, not independent from old clean115 work",
            "evidence_level": "consistency_or_development_asset",
            "notes": "Useful for restored115 debugging; less clean because historically used.",
        },
    ]


def proposal_rows() -> list[dict[str, Any]]:
    return [
        {
            "split_name": "full_mirai_clean115_restored115_row_order_proposal_v0",
            "split_type": "row_order_labeled_split_pending_frontend_compatibility",
            "evidence_level": "proposal_only_not_clean_validation",
            "id_train_count": 60000,
            "ood_train_count": 20000,
            "id_calib_count": 20000,
            "ood_val_count": 10000,
            "final_ood_eval_count": 11621,
            "attack_support_pool_count": 60000,
            "attack_support_count": 32,
            "attack_eval_count": 582516,
            "timestamp_range_train": "not_explicit",
            "timestamp_range_val": "not_explicit",
            "timestamp_range_eval": "not_explicit",
            "capture_ids_train": "not_available",
            "capture_ids_eval": "not_available",
            "support_eval_disjoint": True,
            "prior_use_overlap_removed": "must exclude historical my_gold rows if clean eval claim is desired",
            "final_eval_used_for_selection": False,
            "notes": "Counts are feasible for a clean115/restored115 proposal. This is blocked for current frozen original100 LOW-GUARD++ until feature compatibility/rebuild is resolved.",
        },
        {
            "split_name": "official_mirai_100k_timestamp_proposal_v0",
            "split_type": "timestamped_row_order_split_pending_feature_mapping",
            "evidence_level": "proposal_only_not_clean_validation",
            "id_train_count": 40000,
            "ood_train_count": 10000,
            "id_calib_count": 10000,
            "ood_val_count": 6000,
            "final_ood_eval_count": 5659,
            "attack_support_pool_count": 8000,
            "attack_support_count": 32,
            "attack_eval_count": 20341,
            "timestamp_range_train": "available_in_mirai3_ts_pending_range_extraction",
            "timestamp_range_val": "available_in_mirai3_ts_pending_range_extraction",
            "timestamp_range_eval": "available_in_mirai3_ts_pending_range_extraction",
            "capture_ids_train": "not_available",
            "capture_ids_eval": "not_available",
            "support_eval_disjoint": True,
            "prior_use_overlap_removed": "likely clean for current LOW-GUARD++ but needs row-overlap mapping",
            "final_eval_used_for_selection": False,
            "notes": "Good small timestamped route for restored115/feature-mapping smoke; still not current original100.",
        },
    ]


def rebuild_rows() -> list[dict[str, Any]]:
    return [
        {
            "state_strategy": "continuous_state_baseline",
            "can_run_netstat_afterimage": "not_from_feature_csv_only",
            "can_reset_at_split": False,
            "can_train_state_then_eval_online": False,
            "can_output_original100": "requires raw packet/TSV extractor input and original100 header order",
            "can_output_restored115": "existing matrices available, but frontend state not reconstructable from features alone",
            "needs_restore_15_dims": "yes if choosing restored115 path",
            "requires_slurm": "possibly_for_full_reextraction",
            "estimated_cost": "medium_high_if_raw_reextraction; low_for_matrix_split_only",
            "technical_risk": "feature CSV lacks packet-level fields needed to rerun stateful Kitsune frontend",
            "notes": "Can split existing feature matrix, but cannot make split-aware state claims.",
        },
        {
            "state_strategy": "reset_at_split_boundary",
            "can_run_netstat_afterimage": "blocked_without_raw_packet_or_extracted_packet_fields",
            "can_reset_at_split": "only after raw/TSV frontend input is available",
            "can_train_state_then_eval_online": False,
            "can_output_original100": "blocked_currently",
            "can_output_restored115": "blocked_currently",
            "needs_restore_15_dims": "depends_on_frontend_version",
            "requires_slurm": "yes_likely_for_full_764k_rebuild",
            "estimated_cost": "medium_high",
            "technical_risk": "timestamp alone is insufficient for HH/MI/HpHp feature generation",
            "notes": "Cleanest conservative split-aware state, but not executable from current full Mirai feature CSV.",
        },
        {
            "state_strategy": "train_state_then_eval_online",
            "can_run_netstat_afterimage": "blocked_without_raw_packet_or_extracted_packet_fields",
            "can_reset_at_split": False,
            "can_train_state_then_eval_online": "only after raw/TSV frontend input is available",
            "can_output_original100": "blocked_currently",
            "can_output_restored115": "blocked_currently",
            "needs_restore_15_dims": "depends_on_frontend_version",
            "requires_slurm": "yes_likely_for_full_764k_rebuild",
            "estimated_cost": "medium_high",
            "technical_risk": "requires exact packet order and frontend implementation match",
            "notes": "Most deployment-like state strategy; next issue should build this after raw feature input is recovered.",
        },
    ]


def write_reports(primary_verdict: str) -> None:
    summary = f"""
# issue27m Full Mirai Compatibility / Prior-Use / Split-Aware Rebuild Audit

## Verdict

- primary_verdict = `{primary_verdict}`
- Full Mirai/Botnet is a large, useful asset, but it is **not directly compatible with the frozen `original100 + HistGB-Conservative` LOW-GUARD++ input**.
- The largest file is a 116-column CSV with an index-like first column; the clean historical path is `clean115/restored115`, which the mainline docs already warn must not be mixed with original frontend 100D.
- No evidence was found that full Mirai was used for issue27f LOW-GUARD++ config freeze, kcenter32 support, thresholding, or locked final eval. Historical clean115 use exists and must be separated from any future clean-eval claim.

## Answers

1. full Mirai/Botnet asset format: feature CSV plus label sidecar. `Mirai_dataset.csv` has 116 columns; `mirai_labels.csv` has 764,137 labels.
2. It is not current `original100`. It is best treated as `dirty116` unless col0 is dropped, after which it becomes a `clean115/restored115`-style input. `mirai3.csv` is 115D with timestamp sidecar.
3. Compatibility with current LOW-GUARD++: blocked for frozen `original100`; feasible only through a new `restored115/clean115` path or by re-extracting original100 from raw/packet-level input.
4. original100 recovery/rebuild: not from the current feature CSV alone. It requires raw packet or extracted packet fields compatible with `netStat.py` / `AfterImage.py`.
5. restored115 recovery/rebuild: feature matrices already exist or are recoverable by dropping the index column, but the feature-name/order mapping must be recovered before formal LOW-GUARD++ evaluation.
6. Prior-use/contamination: no current LOW-GUARD++ selection contamination detected; historical clean115 experiments exist, so future clean eval should exclude or explicitly account for those rows.
7. ID/OOD/support/eval construction: row counts are sufficient for full Mirai and official 100k candidates, but evidence is pending frontend compatibility.
8. Split proposal: constructed as proposal-only, not a clean validation split.
9. Split-aware rebuild: blocked from feature CSV alone because state-reset / train-state-then-eval-online needs packet-level frontend input, not only 115D/116D features.
10. Micro-smoke: not executed. Running it now would test a different representation and risk mixing claims.
11. LOW-GUARD++ can enter full Mirai clean eval only after either (a) restored115 is declared as a new bounded LOW-GUARD++ input path with mapping, or (b) full Mirai is re-extracted to current original100.
12. Minimal blocker: feature schema/front-end path incompatibility with frozen original100.
13. Next: `issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke` or an equivalent re-extraction issue if we choose original100 reconstruction instead.
14. Slurm: not needed for this audit; likely needed for full raw/front-end re-extraction over 764k rows.

## Claim Boundary

Allowed: full Mirai is a large labeled candidate asset; it strengthens the data-expansion route and can support future split-aware LOW-GUARD++ evaluation after feature compatibility is resolved.

Not allowed: LOW-GUARD++ is validated on full Mirai; full Mirai proves temporal/cross-dataset generalization; clean115/restored115 results are interchangeable with frozen original100 results; deployment robustness is proven.
"""
    write_text(OUT / "summary.md", summary)

    write_text(
        OUT / "full_mirai_asset_identity_report.md",
        """
# Full Mirai Asset Identity Report

The full Mirai asset exists as a large feature CSV plus label sidecar, not as a packet-level feature-reconstruction-ready object in the current audit.

Key finding: `Mirai_dataset.csv` has 116 columns and an index-like first column. This matches the historical `dirty116` diagnosis. Dropping col0 gives a 115D track, but the current LOW-GUARD++ candidate is frozen on the original frontend `original100`, not on clean115/restored115.

The timestamped `mirai3.csv` asset is 115D with `mirai3_ts.csv`, making it useful for future timestamp-aware split proposals. It still lacks feature names/order mapping against current `original100`.

Recursive local search found separate IoT23 raw pcaps under `public_data/raw`, but did not find a full Mirai/Botnet pcap paired with `Mirai_dataset.csv`. Therefore the current full Mirai object should be treated as a downstream feature matrix, not as a packet-level reconstruction asset.
""",
    )

    write_text(
        OUT / "full_mirai_feature_compatibility_report.md",
        """
# Full Mirai Feature Compatibility Report

The compatibility gate does not pass for the current frozen LOW-GUARD++ instance.

Reason: the formal candidate is `original100 + HistGB-Conservative`, while the full Mirai assets are either dirty 116D or clean/restored 115D feature matrices. The repository's own historical documentation states that clean115 and original-frontend 100 are parallel input tracks and should not be mixed as the same result.

The full Mirai asset is therefore valuable, but the next experiment must choose one of two explicit routes:

1. Re-extract full Mirai into the current 100D frontend feature order, preserving row/timestamp provenance.
2. Define a new bounded `LOW-GUARD++-restored115` instance, recover feature mapping, and validate it as a separate representation-control path.

Micro-smoke was blocked because either route changes the representation relative to the frozen `original100` claim.
""",
    )

    write_text(
        OUT / "full_mirai_prior_use_report.md",
        """
# Full Mirai Prior-Use Report

No evidence was found that the full Mirai asset participated in issue27f LOW-GUARD++ config freeze, support selection, thresholding, or locked final evaluation.

Important boundary: historical clean115/dirty116 experiments exist in `csv_input_clean_stage1_2026-03-23`. They are not part of the current LOW-GUARD++ selection chain, but they mean a future 'clean independent' claim should either use rows outside that historical subset or explicitly disclose that the asset had prior historical development use.

Current contamination verdict: partial historical use exists for clean115, but not for LOW-GUARD++ config/support/threshold/final selection.
""",
    )

    write_text(
        OUT / "full_mirai_split_feasibility_report.md",
        """
# Full Mirai Split Feasibility Report

Full Mirai has enough benign and attack rows to define ID train, OOD train, ID calibration, OOD validation, final OOD eval, attack support pool, kcenter32 support, and attack eval.

However, split feasibility is not the same as LOW-GUARD++ validation readiness. The largest full asset lacks explicit timestamp/capture/session metadata, and its feature schema is not the frozen original100 schema. The official 100k asset has timestamp sidecar and is promising for a small restored115 route, but still needs feature-name/order mapping before evaluation.
""",
    )

    write_text(
        OUT / "full_mirai_split_proposal_report.md",
        """
# Full Mirai Split Proposal Report

Two proposal-only splits were written:

- `full_mirai_clean115_restored115_row_order_proposal_v0`
- `official_mirai_100k_timestamp_proposal_v0`

Both are intentionally marked proposal-only. They must not be described as clean LOW-GUARD++ validation splits until feature compatibility is resolved and final-eval report-only rules are implemented in a runnable pipeline.
""",
    )

    write_text(
        OUT / "full_mirai_split_aware_rebuild_report.md",
        """
# Full Mirai Split-Aware Rebuild Feasibility

Split-aware rebuild is blocked from the current feature CSV alone.

`reset_at_split_boundary` and `train_state_then_eval_online` require packet-level or extractor-level inputs such as packet order, addresses/ports/channels, timestamps, and the exact Kitsune frontend implementation. A 115D/116D feature matrix is already downstream of the stateful frontend and cannot prove reset/online-state behavior by itself.

Slurm is not needed for this audit. It is likely needed if we run full front-end re-extraction over the 764k-row asset or over raw pcap.
""",
    )

    write_text(
        OUT / "full_mirai_micro_smoke_blocked.md",
        """
# Full Mirai Micro-Smoke Blocked

Micro-smoke was not run.

Gate reason: feature compatibility did not pass for the frozen `original100 + HistGB-Conservative` LOW-GUARD++ instance. Running on clean115/restored115 would test a different representation, and running on dirty116 would reintroduce the known index-like column risk.

This is a scientific guardrail, not a method failure.
""",
    )
    write_text(
        OUT / "full_mirai_micro_smoke_report.md",
        """
# Full Mirai Micro-Smoke Report

Not executed. See `full_mirai_micro_smoke_blocked.md`.
""",
    )

    write_text(
        OUT / "full_mirai_issue27m_decision.md",
        f"""
# issue27m Decision

primary_verdict = `{primary_verdict}`

Full Mirai is a strong data-expansion asset, but it cannot yet serve as a clean validation asset for the frozen original100 LOW-GUARD++ candidate. The technically correct next step is not deployment robustness and not demotion. It is feature-path resolution:

1. recover/make feature mapping for restored115/clean115 and define a bounded LOW-GUARD++ restored115 smoke, or
2. re-extract full Mirai into the current original100 frontend with explicit row/timestamp provenance.

Until then, any score on full Mirai would be a representation-compatibility result, not a formal validation of the existing LOW-GUARD++ claim.
""",
    )

    write_text(
        OUT / "claim_update_after_issue27m.md",
        """
# Claim Update After issue27m

## Allowed

- Full Mirai/Botnet is now identified as a large labeled candidate asset for future LOW-GUARD++ validation.
- The asset appears suitable for split proposal construction at the label/count level.
- Full Mirai is currently a clean115/restored115 or dirty116 feature-schema route, not the frozen original100 route.
- Claim upgrade still requires feature compatibility and full clean evaluation.

## Still Not Allowed

- LOW-GUARD++ is validated on full Mirai.
- Full Mirai proves temporal or cross-dataset generalization.
- clean115/restored115 and original100 results are interchangeable.
- Deployment robustness is proven.
- LOW-GUARD-LR is the final mainline solely because full Mirai compatibility is unresolved.
""",
    )

    write_text(
        OUT / "reviewer_defense_full_mirai_data_grounding.md",
        """
# Reviewer Defense: Full Mirai Data Grounding

**Q1: Why not immediately report LOW-GUARD++ on full Mirai?**
Because the full asset is not the frozen original100 input. Reporting it directly would mix representation tracks.

**Q2: Is full Mirai useless then?**
No. It is a valuable large labeled asset. It needs either original100 re-extraction or a clearly bounded restored115 LOW-GUARD++ route.

**Q3: Was full Mirai used to tune the current LOW-GUARD++ result?**
No evidence was found for use in issue27f config freeze, support selection, thresholding, or locked final eval. Historical clean115 work exists and should be disclosed or separated.

**Q4: Can it support ID/OOD/support/eval construction?**
At the label/count level, yes. The blocker is frontend feature compatibility and split-aware reconstruction, not sample volume.

**Q5: Why block micro-smoke?**
A smoke score on a non-equivalent representation could look useful but would not answer the frozen LOW-GUARD++ claim. The safe next step is interface/mapping first.
""",
    )

    write_text(
        OUT / "issue27n_next_action.md",
        """
# issue27n Next Action

Unique next action:

`issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27`

Purpose:

- Recover/define full Mirai clean115/restored115 feature names and order.
- Explicitly decide whether restored115 is a separate LOW-GUARD++ representation-control path.
- Build a fixed split proposal with final-eval report-only rules.
- Run only a micro-smoke after compatibility, prior-use, and split gates pass.

Alternative if the paper insists on the existing frozen original100 instance:

`issue27n_full_mirai_original100_frontend_reextraction_plan_2026-05-27`

This would require packet-level/extractor-compatible inputs and likely Slurm for full re-extraction.
""",
    )


def update_mainline_docs(primary_verdict: str) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    expmap = MAINLINE_DOCS / "mainline_experiment_map.md"
    handoff_entry = f"""

## issue27m full Mirai compatibility audit (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: audited full Mirai/Botnet asset identity, feature schema compatibility, prior-use risk, split feasibility, and split-aware rebuild feasibility before any LOW-GUARD++ score run.
- key result: full Mirai is a large labeled asset (`764137` rows; benign `121621`, attack `642516`), but it is `dirty116`/`clean115-restored115` style rather than the current frozen `original100` LOW-GUARD++ input.
- claim boundary: no full Mirai LOW-GUARD++ validation was run; clean115/restored115 must not be mixed with the frozen original100 claim.
- next action: `issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke` or, if original100 must be preserved, full Mirai original100 frontend re-extraction.
"""
    exp_entry = f"""

### issue27m full Mirai compatibility audit (2026-05-27)

| Run | Verdict | Role | Boundary | Next |
|---|---|---|---|---|
| `runs/issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27/` | `{primary_verdict}` | Large-data compatibility and prior-use gate for LOW-GUARD++ | Full Mirai is not yet a clean validation result for frozen original100; it is a clean115/restored115 or re-extraction path | Recover restored115 mapping or re-extract original100 before evaluation |
"""
    for path, entry in [(handoff, handoff_entry), (expmap, exp_entry)]:
        text = path.read_text(encoding="utf-8", errors="ignore")
        marker = "issue27m full Mirai compatibility audit"
        if marker not in text:
            path.write_text(text.rstrip() + entry + "\n", encoding="utf-8")


def main() -> None:
    ensure_out()
    primary_verdict = "full_mirai_incompatible_needs_new_frontend_path"
    headers100 = read_headers(ORIGINAL100_HEADERS)
    identity = asset_identity_rows()
    compatibility = compatibility_rows(headers100)
    prior = prior_use_rows()
    split = split_rows()
    proposal = proposal_rows()
    rebuild = rebuild_rows()

    write_csv(OUT / "full_mirai_asset_identity_audit.csv", identity)
    write_csv(OUT / "full_mirai_feature_compatibility_table.csv", compatibility)
    write_csv(OUT / "full_mirai_prior_use_audit.csv", prior)
    write_csv(OUT / "full_mirai_split_feasibility_table.csv", split)
    write_csv(OUT / "full_mirai_split_proposal_manifest.csv", proposal)
    write_csv(OUT / "full_mirai_split_aware_rebuild_feasibility.csv", rebuild)

    write_reports(primary_verdict)

    config = {
        "issue": "issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27",
        "method_frozen": "LOW-GUARD++ original100 + HistGB-Conservative",
        "frozen_config_id": "histgb_d2_lr005_l2p1_ood4_sup4_t0050",
        "ood_alarm_target": 0.01,
        "final_eval_report_only": True,
        "micro_smoke_executed": False,
        "primary_verdict": primary_verdict,
    }
    write_text(OUT / "config.json", json.dumps(config, indent=2))

    run_spec = {
        "read_inputs": [
            str(ISSUE27L / "summary.md"),
            str(ISSUE27L / "full_botnet_dataset_inventory.csv"),
            str(ISSUE27K / "summary.md"),
            str(CLEAN_STAGE / "summary.md"),
            str(ORIGINAL100_HEADERS),
        ],
        "stages": [
            "asset_identity_audit",
            "feature_compatibility_audit",
            "prior_use_audit",
            "split_feasibility",
            "split_proposal",
            "split_aware_rebuild_feasibility",
            "micro_smoke_gate",
        ],
        "blocked_micro_smoke_reason": "full Mirai feature schema is clean115/restored115/dirty116, not frozen original100",
    }
    write_text(OUT / "run_spec.json", json.dumps(run_spec, indent=2))

    commands = [
        "git branch --show-current",
        "git status --short",
        "Get-Content runs/issue27l.../summary.md",
        "Get-Content runs/issue27l.../full_botnet_dataset_inventory.csv",
        "Get-Content runs/issue27k.../summary.md",
        "Get-Content runs/mainline_docs/mainline_experiment_map.md/mainline_handoff.md selected patterns",
        "Get-ChildItem -Recurse for Mirai/Botnet csv/npy/tsv/pcap assets",
        "python runs/issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild_2026-05-27/run_issue27m_full_mirai_compatibility_audit.py",
    ]
    write_text(OUT / "command.txt", "\n".join(commands))

    manifest_rows = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            manifest_rows.append(
                {
                    "path": str(p),
                    "file_name": p.name,
                    "size_bytes": p.stat().st_size,
                    "role": "issue27m_output",
                }
            )
    write_csv(OUT / "manifest.csv", manifest_rows)
    update_mainline_docs(primary_verdict)


if __name__ == "__main__":
    main()
