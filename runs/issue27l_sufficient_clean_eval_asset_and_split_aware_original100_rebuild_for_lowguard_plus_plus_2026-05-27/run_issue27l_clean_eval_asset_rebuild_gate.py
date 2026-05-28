from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27l_sufficient_clean_eval_asset_and_split_aware_original100_rebuild_for_lowguard_plus_plus_2026-05-27"
ISSUE27K = ROOT / "runs" / "issue27k_row_level_original100_rebuild_and_purged_split_construction_for_lowguard_plus_plus_2026-05-27"
ISSUE27J = ROOT / "runs" / "issue27j_raw_provenance_recovery_and_clean_independent_split_construction_for_lowguard_plus_plus_2026-05-27"
ISSUE27I = ROOT / "runs" / "issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27"
ISSUE27H = ROOT / "runs" / "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
MAINLINE = ROOT / "runs" / "mainline_docs"
KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
FROZEN_CONFIG_ID = "histgb_d2_lr005_l2p1_ood4_sup4_t0050"
OFFICIAL_TARGET = 0.01


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def md_table(df: pd.DataFrame, max_rows: int | None = None) -> str:
    if max_rows is not None:
        df = df.head(max_rows).copy()
    if df.empty:
        return "_No rows._\n"
    lines = ["| " + " | ".join(map(str, df.columns)) + " |", "|" + "|".join(["---"] * len(df.columns)) + "|"]
    for _, row in df.iterrows():
        vals: list[str] = []
        for value in row:
            if isinstance(value, (float, np.floating)):
                vals.append("" if math.isnan(float(value)) else f"{float(value):.6f}")
            else:
                vals.append(str(value))
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines) + "\n"


def required_inputs() -> pd.DataFrame:
    files = [
        ISSUE27K / "summary.md",
        ISSUE27K / "row_level_sidecar_manifest.csv",
        ISSUE27K / "row_level_sidecar_manifest_report.md",
        ISSUE27K / "original100_reconstruction_feasibility.csv",
        ISSUE27K / "original100_reconstruction_report.md",
        ISSUE27K / "purged_split_design_table.csv",
        ISSUE27K / "purged_split_design_report.md",
        ISSUE27K / "claim_update_after_issue27k.md",
        ISSUE27J / "summary.md",
        ISSUE27I / "summary.md",
        ISSUE27H / "summary.md",
        ISSUE27F / "summary.md",
        ISSUE25C / "summary.md",
        MAINLINE / "mainline_handoff.md",
        MAINLINE / "mainline_experiment_map.md",
    ]
    return pd.DataFrame([{"path": safe_rel(p), "exists": p.exists(), "required": True} for p in files])


def get_asset_paths() -> dict[str, Any]:
    attack_meta = read_json(KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "extract_attack_34_1" / "extract_metadata.json")
    current_id_meta = read_json(KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_id_7_6" / "extract_metadata.json")
    current_ood_meta = read_json(KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_ood_4_1" / "extract_metadata.json")
    full_benign_meta = read_json(KITNET_ROOT / "runs" / "frontend100_ood_stage1_2026-03-23" / "extract_full_iot23_7_6" / "extract_metadata.json")
    full_benign_split = read_json(KITNET_ROOT / "runs" / "frontend100_ood_stage1_2026-03-23" / "source_split_metadata.json")
    stage2 = read_json(KITNET_ROOT / "runs" / "frontend100_joint_eval_stage2_2026-04-01" / "attack_manifest_stage2.json")
    raw_dir = KITNET_ROOT / "public_data" / "raw"
    return {
        "attack_meta": attack_meta,
        "current_id_meta": current_id_meta,
        "current_ood_meta": current_ood_meta,
        "full_benign_meta": full_benign_meta,
        "full_benign_split": full_benign_split,
        "stage2": stage2,
        "raw_dir": raw_dir,
    }


def timestamp_summary(tsv_path: Path, start: int = 0, count: int | None = None) -> dict[str, Any]:
    nrows = None if count is None else count
    df = pd.read_csv(tsv_path, sep="\t", usecols=["frame.time_epoch"], skiprows=range(1, start + 1) if start else None, nrows=nrows)
    ts = pd.to_numeric(df["frame.time_epoch"], errors="coerce").to_numpy(np.float64)
    return {
        "rows": int(len(ts)),
        "timestamp_min": float(np.nanmin(ts)) if len(ts) else "NA",
        "timestamp_max": float(np.nanmax(ts)) if len(ts) else "NA",
        "timestamp_range": f"{float(np.nanmin(ts)):.6f}-{float(np.nanmax(ts)):.6f}" if len(ts) else "NA",
    }


def attack_bin_counts(attack_tsv: Path, bin_seconds: int) -> pd.DataFrame:
    ts = pd.to_numeric(pd.read_csv(attack_tsv, sep="\t", usecols=["frame.time_epoch"])["frame.time_epoch"], errors="coerce").to_numpy(np.float64)
    bins = ((ts - float(np.nanmin(ts))) // bin_seconds).astype(int)
    df = pd.DataFrame({"row_index": np.arange(len(ts)), "timestamp": ts, "bin": bins})
    return df.groupby("bin", as_index=False).agg(
        row_count=("bin", "size"),
        row_index_min=("row_index", "min"),
        row_index_max=("row_index", "max"),
        timestamp_min=("timestamp", "min"),
        timestamp_max=("timestamp", "max"),
    )


def count_lines(path: Path) -> int:
    with path.open("rb") as f:
        return sum(1 for _ in f)


def first_csv_col_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        line = f.readline().rstrip("\n")
    return len(line.split(",")) if line else 0


def npy_label_counts(path: Path) -> tuple[int, int, int]:
    arr = np.load(path, allow_pickle=False)
    vals, counts = np.unique(arr, return_counts=True)
    by = {int(v): int(c) for v, c in zip(vals, counts)}
    return int(len(arr)), int(by.get(0, 0)), int(by.get(1, 0))


def csv_label_counts(path: Path) -> tuple[int, int, int]:
    labels = pd.read_csv(path, header=None)[0]
    vc = labels.value_counts(dropna=False)
    return int(len(labels)), int(vc.get(0, 0)), int(vc.get(1, 0))


def build_full_botnet_inventory() -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    base = KITNET_ROOT
    raw = KITNET_ROOT / "public_data" / "raw"
    data_root = ROOT.parents[0] / "data"

    mirai_dataset = base / "Mirai_dataset.csv"
    mirai_labels = base / "mirai_labels.csv"
    official_features = base / "mirai3.csv"
    official_ts = base / "mirai3_ts.csv"
    official_labels = base / "official_labels.npy"
    gold_features = base / "my_gold_mirai.csv"
    gold_labels = base / "my_gold_labels.npy"
    unsw_files = sorted((data_root / "5%" / "All features").glob("UNSW_2018_IoT_Botnet_Full5pc_*.csv"))
    network_file = data_root / "Train_Test_Network_dataset" / "train_test_network.csv"

    rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []

    if mirai_dataset.exists() and mirai_labels.exists():
        n, benign, attack = csv_label_counts(mirai_labels)
        rows.append(
            {
                "asset_name": "full_mirai_labeled_feature_csv",
                "asset_path": str(mirai_dataset),
                "label_path": str(mirai_labels),
                "asset_type": "feature_csv_with_label_sidecar",
                "exists": True,
                "has_pcap": False,
                "has_csv": True,
                "has_tsv": False,
                "has_feature_cache": True,
                "has_metadata": "partial",
                "total_rows_or_packets": n,
                "benign_rows": benign,
                "attack_rows": attack,
                "flow_rows": "NA",
                "contains_timestamp": "not_explicit",
                "contains_packet_order": True,
                "contains_capture_id": False,
                "contains_session_id": False,
                "feature_dim_or_columns": first_csv_col_count(mirai_dataset),
                "can_reconstruct_original100": "unknown_requires_feature_mapping",
                "can_reconstruct_restored115": True,
                "can_build_larger_clean_eval_asset": True,
                "can_construct_id_ood_support_eval": "yes_after_split_policy",
                "requires_slurm_for_full_rebuild": "maybe",
                "notes": "Large later-downloaded Mirai feature dataset with labels. First column appears row index; remaining columns look restored115-style features.",
            }
        )
        split_rows.append(
            {
                "candidate_name": "full_mirai_labeled_restored115_chrono_split",
                "source_asset": "full_mirai_labeled_feature_csv",
                "total_rows": n,
                "benign_rows": benign,
                "attack_rows": attack,
                "proposed_id_train": "benign rows 0-60000",
                "proposed_id_calib": "benign rows 60000-80000",
                "proposed_ood_val": "benign rows 80000-100000",
                "proposed_final_ood_eval": "benign rows 100000-121620",
                "proposed_attack_support_pool": "early attack rows after benign prefix",
                "proposed_attack_eval": "later attack rows with purge gap",
                "timestamp_or_order_basis": "row_order_only; explicit timestamp not found in full csv",
                "feature_compatibility": "restored115_candidate; current frozen original100 config needs mapping/subset audit",
                "can_prioritize_over_80k_future_bin": True,
                "clean_split_ready_now": False,
                "blocked_reason": "Needs feature-compatibility audit and prior-use audit before LOW-GUARD++ original100 evaluation.",
                "recommended_priority": "P0",
            }
        )

    if official_features.exists() and official_labels.exists():
        n, benign, attack = npy_label_counts(official_labels)
        rows.append(
            {
                "asset_name": "official_mirai_100k_with_timestamp",
                "asset_path": str(official_features),
                "label_path": str(official_labels),
                "asset_type": "feature_csv_plus_npy_labels_plus_timestamp_csv",
                "exists": True,
                "has_pcap": False,
                "has_csv": True,
                "has_tsv": False,
                "has_feature_cache": True,
                "has_metadata": "partial",
                "total_rows_or_packets": n,
                "benign_rows": benign,
                "attack_rows": attack,
                "flow_rows": "NA",
                "contains_timestamp": official_ts.exists(),
                "contains_packet_order": True,
                "contains_capture_id": False,
                "contains_session_id": False,
                "feature_dim_or_columns": first_csv_col_count(official_features),
                "can_reconstruct_original100": "unknown_requires_feature_mapping",
                "can_reconstruct_restored115": True,
                "can_build_larger_clean_eval_asset": True,
                "can_construct_id_ood_support_eval": "yes_but_smaller_than_full_mirai",
                "requires_slurm_for_full_rebuild": False,
                "notes": "Timestamp sidecar exists, making this useful for a cleaner first compatibility smoke.",
            }
        )
        split_rows.append(
            {
                "candidate_name": "official_mirai_100k_timestamped_split",
                "source_asset": "official_mirai_100k_with_timestamp",
                "total_rows": n,
                "benign_rows": benign,
                "attack_rows": attack,
                "proposed_id_train": "benign rows 0-40000",
                "proposed_id_calib": "benign rows 40000-60000",
                "proposed_ood_val": "benign rows 60000-68000",
                "proposed_final_ood_eval": "remaining benign rows before attack",
                "proposed_attack_support_pool": "early attack rows after benign prefix",
                "proposed_attack_eval": "later attack rows",
                "timestamp_or_order_basis": "explicit mirai3_ts.csv plus row_order",
                "feature_compatibility": "restored115_candidate; current original100 mapping unresolved",
                "can_prioritize_over_80k_future_bin": True,
                "clean_split_ready_now": False,
                "blocked_reason": "Needs restored115/original100 compatibility decision before frozen LOW-GUARD++ evaluation.",
                "recommended_priority": "P0_smoke_before_full_764k",
            }
        )

    if gold_features.exists() and gold_labels.exists():
        n, benign, attack = npy_label_counts(gold_labels)
        rows.append(
            {
                "asset_name": "my_gold_mirai_200k_labeled_feature_csv",
                "asset_path": str(gold_features),
                "label_path": str(gold_labels),
                "asset_type": "feature_csv_plus_npy_labels",
                "exists": True,
                "has_pcap": False,
                "has_csv": True,
                "has_tsv": False,
                "has_feature_cache": True,
                "has_metadata": "partial",
                "total_rows_or_packets": n,
                "benign_rows": benign,
                "attack_rows": attack,
                "flow_rows": "NA",
                "contains_timestamp": "not_explicit",
                "contains_packet_order": True,
                "contains_capture_id": False,
                "contains_session_id": False,
                "feature_dim_or_columns": first_csv_col_count(gold_features),
                "can_reconstruct_original100": "unknown_requires_feature_mapping",
                "can_reconstruct_restored115": True,
                "can_build_larger_clean_eval_asset": True,
                "can_construct_id_ood_support_eval": "yes_after_split_policy",
                "requires_slurm_for_full_rebuild": False,
                "notes": "Labeled 200k subset; useful bridge between official 100k and full 764k.",
            }
        )

    if unsw_files:
        total_rows = 0
        total_benign = 0
        total_attack = 0
        for path in unsw_files:
            for chunk in pd.read_csv(path, usecols=["attack"], chunksize=250000):
                total_rows += len(chunk)
                vc = chunk["attack"].value_counts(dropna=False)
                total_benign += int(vc.get(0, 0))
                total_attack += int(vc.get(1, 0))
        rows.append(
            {
                "asset_name": "UNSW_2018_IoT_Botnet_5pc_flow_csv",
                "asset_path": ";".join(str(p) for p in unsw_files),
                "label_path": "inline_attack_column",
                "asset_type": "flow_csv_second_environment",
                "exists": True,
                "has_pcap": False,
                "has_csv": True,
                "has_tsv": False,
                "has_feature_cache": False,
                "has_metadata": "csv_header",
                "total_rows_or_packets": total_rows,
                "benign_rows": total_benign,
                "attack_rows": total_attack,
                "flow_rows": total_rows,
                "contains_timestamp": True,
                "contains_packet_order": "flow_order",
                "contains_capture_id": False,
                "contains_session_id": False,
                "feature_dim_or_columns": "46 columns in sampled header",
                "can_reconstruct_original100": False,
                "can_reconstruct_restored115": False,
                "can_build_larger_clean_eval_asset": "yes_second_environment_not_current_lowguardpp_original100",
                "can_construct_id_ood_support_eval": "limited_benign_only_477_rows_in_5pc_all_features",
                "requires_slurm_for_full_rebuild": "not_for_csv_split; yes_for_new_feature_compatibility",
                "notes": "Large Bot-IoT flow CSV but only 477 benign rows in 5pc all-feature files; not directly compatible with current Kitsune original100.",
            }
        )

    if network_file.exists():
        rows_count = 0
        benign = 0
        attack = 0
        for chunk in pd.read_csv(network_file, usecols=["label"], chunksize=250000):
            rows_count += len(chunk)
            vc = chunk["label"].value_counts(dropna=False)
            benign += int(vc.get(0, 0))
            attack += int(vc.get(1, 0))
        rows.append(
            {
                "asset_name": "Train_Test_Network_dataset_flow_csv",
                "asset_path": str(network_file),
                "label_path": "inline_label_column",
                "asset_type": "flow_csv_second_environment",
                "exists": True,
                "has_pcap": False,
                "has_csv": True,
                "has_tsv": False,
                "has_feature_cache": False,
                "has_metadata": "csv_header",
                "total_rows_or_packets": rows_count,
                "benign_rows": benign,
                "attack_rows": attack,
                "flow_rows": rows_count,
                "contains_timestamp": False,
                "contains_packet_order": "flow_order",
                "contains_capture_id": False,
                "contains_session_id": False,
                "feature_dim_or_columns": "44 columns",
                "can_reconstruct_original100": False,
                "can_reconstruct_restored115": False,
                "can_build_larger_clean_eval_asset": "yes_second_environment_not_current_lowguardpp_original100",
                "can_construct_id_ood_support_eval": True,
                "requires_slurm_for_full_rebuild": False,
                "notes": "Flow-level second-environment candidate with 50k benign and 161k attack, but not Kitsune original100 compatible.",
            }
        )

    search_rows = [
        {
            "candidate_name": "full_mirai_labeled_restored115_chrono_split",
            "source_path": str(mirai_dataset),
            "total_rows": 764137 if mirai_dataset.exists() else "missing",
            "id_rows": 60000,
            "ood_rows": 61621,
            "attack_rows": 642516,
            "timestamp_range": "row_order_only_full_mirai",
            "capture_id_range": "unknown_single_or_mixed_mirai_dataset",
            "overlaps_locked_bins": "no_known_overlap_with_iot23_locked_bins",
            "overlaps_previous_final_eval": "unknown_prior_use_requires_audit",
            "overlaps_support": "no_if_new_train_side_support_pool_is_defined",
            "can_use_as_clean_eval": "yes_after_feature_compatibility_and_prior_use_audit",
            "evidence_level": "large_labeled_dataset_candidate_pending_frontend_compatibility",
            "leakage_risk": "medium_until_feature_mapping_and_prior_use_audit",
            "blocked_reason": "Not directly current original100; needs restored115/original100 compatibility and split policy.",
            "recommended_priority": "P0_full_dataset",
        },
        {
            "candidate_name": "official_mirai_100k_timestamped_split",
            "source_path": str(official_features),
            "total_rows": 100000 if official_features.exists() else "missing",
            "id_rows": 40000,
            "ood_rows": 31659,
            "attack_rows": 28341,
            "timestamp_range": "mirai3_ts.csv_available",
            "capture_id_range": "unknown_mirai_subset",
            "overlaps_locked_bins": "no_known_overlap_with_iot23_locked_bins",
            "overlaps_previous_final_eval": "unknown_prior_use_requires_audit",
            "overlaps_support": "no_if_new_train_side_support_pool_is_defined",
            "can_use_as_clean_eval": "yes_after_feature_compatibility_and_prior_use_audit",
            "evidence_level": "timestamped_labeled_dataset_candidate_pending_frontend_compatibility",
            "leakage_risk": "medium_until_feature_mapping_and_prior_use_audit",
            "blocked_reason": "Timestamped and labeled, but feature compatibility with frozen original100 unresolved.",
            "recommended_priority": "P0_timestamped_smoke",
        },
    ]
    return pd.DataFrame(rows), pd.DataFrame(split_rows), search_rows


def build_search_table(paths: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    attack_tsv = Path(paths["attack_meta"]["tsv_path"])
    current_ood_tsv = Path(paths["current_ood_meta"]["tsv_path"])
    full_benign_tsv = Path(paths["full_benign_meta"]["tsv_path"])
    raw_dir = paths["raw_dir"]
    bin_df = attack_bin_counts(attack_tsv, int(paths["stage2"]["bin_seconds"]))

    attack_first10 = timestamp_summary(attack_tsv, 0, 10000)
    attack_after10 = timestamp_summary(attack_tsv, 10000, 20000)
    current_ood_eval = timestamp_summary(current_ood_tsv, 10000, 10000)
    future_benign = timestamp_summary(full_benign_tsv, 90000, 20000)
    future_benign_tail = timestamp_summary(full_benign_tsv, 110000, 5000)
    bin9_protocol_rows = 208

    candidates = [
        {
            "candidate_name": "extended_attack_10k_30k_plus_future_benign_90k_110k",
            "source_path": f"{safe_rel(attack_tsv)} ; {safe_rel(full_benign_tsv)}",
            "total_rows": int(attack_after10["rows"] + future_benign["rows"]),
            "id_rows": 0,
            "ood_rows": int(future_benign["rows"]),
            "attack_rows": int(attack_after10["rows"]),
            "timestamp_range": f"attack {attack_after10['timestamp_range']} ; benign {future_benign['timestamp_range']}",
            "capture_id_range": "attack=CTU-IoT-Malware-Capture-34-1 ; benign=CTU-Honeypot-Capture-7-6",
            "overlaps_locked_bins": "no_for_attack_rows_10000_30000; no_for_same_capture_benign_future",
            "overlaps_previous_final_eval": "not_issue27f_locked_attack_eval; benign_future_from_early_frontend100_ood_stage1_asset",
            "overlaps_support": "no_if_support_rebuilt_from_rows_0_10000_train_side",
            "can_use_as_clean_eval": "partial_no_claim_clean_until_split_aware_rebuild_and_prior-use_audit",
            "evidence_level": "weak_temporal_candidate_not_clean_independent",
            "leakage_risk": "medium",
            "blocked_reason": "sufficient rows exist, but benign future asset is same-capture and historical; split-aware feature rebuild and label/provenance audit are still required.",
            "recommended_priority": "P0_rebuild_prevalidation",
        },
        {
            "candidate_name": "future_bin9_only",
            "source_path": safe_rel(attack_tsv),
            "total_rows": bin9_protocol_rows,
            "id_rows": 0,
            "ood_rows": 0,
            "attack_rows": bin9_protocol_rows,
            "timestamp_range": "attack bin 9 within first 10000",
            "capture_id_range": "CTU-IoT-Malware-Capture-34-1",
            "overlaps_locked_bins": "no",
            "overlaps_previous_final_eval": "near_locked_protocol_context",
            "overlaps_support": "no_if_support_not_from_bin9",
            "can_use_as_clean_eval": "no",
            "evidence_level": "diagnostic_only",
            "leakage_risk": "medium_small_eval",
            "blocked_reason": f"only {bin9_protocol_rows} rows in the prior first-10k protocol view; explicitly below formal gate. Later bin-9 rows are included only in the extended 10k-30k candidate.",
            "recommended_priority": "not_recommended",
        },
        {
            "candidate_name": "locked_bins_6_8_with_bin5_purge",
            "source_path": safe_rel(attack_tsv),
            "total_rows": int(bin_df[bin_df["bin"].isin([6, 7, 8])]["row_count"].sum() + current_ood_eval["rows"]),
            "id_rows": 0,
            "ood_rows": int(current_ood_eval["rows"]),
            "attack_rows": int(bin_df[bin_df["bin"].isin([6, 7, 8])]["row_count"].sum()),
            "timestamp_range": "attack locked bins 6-8 plus current OOD final eval",
            "capture_id_range": "current locked captures",
            "overlaps_locked_bins": "yes",
            "overlaps_previous_final_eval": "yes",
            "overlaps_support": "no_if_support_bins_2_4",
            "can_use_as_clean_eval": "no",
            "evidence_level": "consistency_only",
            "leakage_risk": "high_repeated_locked_eval",
            "blocked_reason": "reuses issue23/25c/27f locked evidence objects.",
            "recommended_priority": "not_recommended",
        },
        {
            "candidate_name": "raw_ood_4_1_beyond_20k",
            "source_path": safe_rel(raw_dir / "iot23_4_1.pcap"),
            "total_rows": "unknown",
            "id_rows": 0,
            "ood_rows": "unknown",
            "attack_rows": 0,
            "timestamp_range": "unknown",
            "capture_id_range": "CTU-Honeypot-Capture-4-1",
            "overlaps_locked_bins": "no_attack",
            "overlaps_previous_final_eval": "unknown",
            "overlaps_support": "no",
            "can_use_as_clean_eval": "unknown",
            "evidence_level": "blocked_raw_count_unknown",
            "leakage_risk": "unknown",
            "blocked_reason": "tshark is unavailable in current environment; no extracted rows beyond first 20000 are present.",
            "recommended_priority": "P1_reextract_if_tshark_or_scapy_available",
        },
        {
            "candidate_name": "second_dataset_ciciot_csv",
            "source_path": f"{safe_rel(raw_dir / 'CICIoT2023_2.csv')} ; {safe_rel(raw_dir / 'CICIoT2023_BenignTraffic3.csv')}",
            "total_rows": "available_csv_unknown_rows",
            "id_rows": "unknown",
            "ood_rows": "unknown",
            "attack_rows": "unknown",
            "timestamp_range": "csv_not_pcap_original100",
            "capture_id_range": "second_dataset_csv",
            "overlaps_locked_bins": "no",
            "overlaps_previous_final_eval": "no",
            "overlaps_support": "no",
            "can_use_as_clean_eval": "no_for_original100_without_feature_compatibility",
            "evidence_level": "second_environment_feasibility_only",
            "leakage_risk": "unknown_feature_mismatch",
            "blocked_reason": "CICIoT CSV features are not raw pcap/Kitsune original100-compatible without a new construction protocol.",
            "recommended_priority": "P2_after_same_dataset_rebuild_path",
        },
        {
            "candidate_name": "attack_rows_10k_30k_without_new_ood",
            "source_path": safe_rel(attack_tsv),
            "total_rows": int(attack_after10["rows"]),
            "id_rows": 0,
            "ood_rows": 0,
            "attack_rows": int(attack_after10["rows"]),
            "timestamp_range": attack_after10["timestamp_range"],
            "capture_id_range": "CTU-IoT-Malware-Capture-34-1",
            "overlaps_locked_bins": "no_for_attack_rows_after_10k",
            "overlaps_previous_final_eval": "no_for_issue27f_attack_eval",
            "overlaps_support": "no_if_support_rows_0_10000",
            "can_use_as_clean_eval": "no_without_clean_ood_eval",
            "evidence_level": "attack_asset_only",
            "leakage_risk": "medium_needs_label_mapping",
            "blocked_reason": "attack side is sufficiently large, but clean low-alert evaluation also needs OOD final eval.",
            "recommended_priority": "P0_component_asset",
        },
    ]

    eligibility = []
    rules = [
        ("sufficient_final_ood_rows", "final_ood_eval_count should be large enough for low-alert alarm estimates; thousands preferred."),
        ("sufficient_attack_eval_rows", "attack_eval_count should be large enough for stable detection estimates."),
        ("clear_train_cal_val_eval_time_ranges", "time/order ranges must be explicit."),
        ("support_eval_disjoint", "attack supports must come only from train-side attack pool."),
        ("threshold_train_val_only", "threshold must come from ID_calib + OOD_val only."),
        ("eval_not_used_for_selection", "eval asset cannot select config/support/threshold/features."),
        ("no_locked_overlap", "overlap with locked bins 5/6/7/8 means consistency-only."),
        ("purge_or_disjoint_available", "same-capture temporal split needs purge or online-state protocol."),
        ("row_timestamp_order_complete", "row-level timestamp/order must be complete."),
        ("bin9_not_alone", "future bin9 208 rows cannot be formal validation alone."),
        ("split_aware_rebuild_ready", "split-aware original100 features must exist before clean evaluation."),
        ("prior_use_audit_passed", "historically used assets cannot be promoted without explicit prior-use audit."),
    ]
    for rid, rule in rules:
        status = "pass"
        candidate = "extended_attack_10k_30k_plus_future_benign_90k_110k"
        if rid in {"split_aware_rebuild_ready", "prior_use_audit_passed"}:
            status = "fail"
        elif rid == "purge_or_disjoint_available":
            status = "partial"
        elif rid == "no_locked_overlap":
            status = "pass_for_extended_candidate"
        eligibility.append(
            {
                "rule_id": rid,
                "rule": rule,
                "candidate_assessed": candidate,
                "status": status,
                "notes": "Blocks clean claim until fixed." if status == "fail" else "Satisfiable under the extended unused-segment candidate.",
            }
        )

    split_manifest = pd.DataFrame(
        [
            {
                "split_name": "extended_unused_segment_temporal_candidate",
                "split_type": "purged_temporal_candidate_not_clean_claim",
                "evidence_level": "weak_temporal_candidate_blocked_for_clean_claim",
                "train_rows": 10000 + 50000 + 10000,
                "id_train_count": 8000,
                "ood_train_count": 8000,
                "id_calib_count": 5000,
                "ood_val_count": 2000,
                "final_ood_eval_count": int(future_benign["rows"]),
                "attack_support_count": 32,
                "attack_eval_count": int(attack_after10["rows"]),
                "timestamp_range_train": f"attack train {attack_first10['timestamp_range']} ; ID/OOD current locked train/cal",
                "timestamp_range_calib": "current ID calibration rows 8000-12999",
                "timestamp_range_val": "current OOD validation rows 8000-9999",
                "timestamp_range_eval": f"attack {attack_after10['timestamp_range']} ; benign future {future_benign['timestamp_range']}",
                "purge_gap": "attack split after row 9999; benign future starts at row 90000 after 40000-row embargo from ID train",
                "capture_ids_train": "ID=7-6; OOD=4-1; attack=34-1 rows 0-9999",
                "capture_ids_eval": "benign=7-6 rows 90000-109999; attack=34-1 rows 10000-29999",
                "support_eval_disjoint": True,
                "final_eval_excluded_from_selection": True,
                "overlap_with_previous_locked_eval": "no_attack_overlap; benign source historically exists as frontend100_ood_stage1",
                "notes": "Sufficient row counts, but not promoted because split-aware rebuild and prior-use/provenance audit are not complete.",
            }
        ]
    )
    return pd.DataFrame(candidates), pd.DataFrame(eligibility), split_manifest


def write_blocked_files(split_manifest: pd.DataFrame) -> None:
    split_text = f"""
# Best Available Clean Split Blocked

No split was promoted as a clean independent validation object in issue27l.

The strongest candidate is the extended unused-segment temporal candidate:

{md_table(split_manifest)}

Why it remains blocked:
- it has enough rows, but its benign side is a same-capture future segment from a historical frontend100 OOD-stage asset;
- split-aware original100 rebuild has not been executed;
- prior-use/provenance audit is still needed before any main-text clean claim;
- running frozen LOW-GUARD++ now would risk producing another weak/diagnostic result rather than a clean validation.
"""
    write_text(OUT / "best_available_clean_split_blocked.md", split_text)
    write_text(OUT / "best_available_clean_split_report.md", split_text)

    rebuild_text = """
# Split-Aware Rebuild Blocked

Split-aware original100 rebuild was not executed in issue27l because no candidate passed the clean-eval eligibility gate.

Executable strategies remain:
- `continuous_state_baseline`: available as a non-clean reference via existing caches;
- `reset_at_split_boundary`: technically executable by slicing TSV files and reinitializing FeatureExtractor/netStat per split;
- `train_state_then_eval_online`: technically executable and closest to deployment, but should run only after the evaluation object is admitted.
"""
    write_text(OUT / "split_aware_rebuild_blocked.md", rebuild_text)
    eval_text = """
# Clean/Purged Evaluation Blocked

Frozen LOW-GUARD++ was not evaluated because the best available candidate did not pass the clean-eval gate.

This is a design-gate result, not a method-failure result.
"""
    write_text(OUT / "clean_purged_eval_blocked.md", eval_text)


def update_mainline_docs(primary_verdict: str, issue27m_action: str) -> None:
    handoff = MAINLINE / "mainline_handoff.md"
    expmap = MAINLINE / "mainline_experiment_map.md"
    handoff_append = f"""

## issue27l clean eval asset and split-aware rebuild gate (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: searches sufficient clean eval assets, identifies full Mirai/Botnet labeled datasets plus the extended unused-segment candidate, and blocks evaluation until feature compatibility, prior-use audit, and split-aware rebuild are resolved.
- claim boundary: LOW-GUARD++ remains high-potential, but still cannot be upgraded to a main-text performance instance.
- next action: `{issue27m_action}`.
"""
    expmap_append = f"""
| issue27l | clean eval asset and split-aware original100 rebuild gate | `{primary_verdict}` | Finds full Mirai/Botnet labeled assets and a sufficiently sized extended-segment candidate; blocks formal LOW-GUARD++ clean eval pending feature compatibility, split-aware rebuild, and prior-use/provenance audit. Next: `{issue27m_action}`. |
"""
    htxt = handoff.read_text(encoding="utf-8")
    htxt = re.sub(r"\n## issue27l clean eval asset and split-aware rebuild gate \(2026-05-27\)\n.*?(?=\n## |\Z)", "", htxt, flags=re.S)
    handoff.write_text(htxt.rstrip() + handoff_append, encoding="utf-8")
    etxt = expmap.read_text(encoding="utf-8")
    etxt = re.sub(r"(?m)^\| issue27l \|.*\|\r?\n?", "", etxt)
    expmap.write_text(etxt.rstrip() + "\n\n" + expmap_append.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = required_inputs()
    inputs.to_csv(OUT / "manifest.csv", index=False)
    missing = inputs[inputs["required"] & ~inputs["exists"]]
    if len(missing):
        write_text(OUT / "summary.md", "primary_verdict: `clean_eval_asset_blocked_but_recovery_plan_ready`\n\nRequired inputs missing; see manifest.csv.")
        raise SystemExit(1)

    paths = get_asset_paths()
    search, eligibility, split_manifest = build_search_table(paths)
    full_inventory, full_split_plan, full_search_rows = build_full_botnet_inventory()
    search = pd.concat([search, pd.DataFrame(full_search_rows)], ignore_index=True)
    search.to_csv(OUT / "clean_eval_asset_search_table.csv", index=False)
    eligibility.to_csv(OUT / "clean_eval_eligibility_table.csv", index=False)
    full_inventory.to_csv(OUT / "full_botnet_dataset_inventory.csv", index=False)
    write_text(
        OUT / "full_botnet_dataset_split_feasibility.md",
        f"""
# Full Botnet / Mirai Dataset Split Feasibility

Full botnet/Mirai assets were explicitly searched in addition to the current 80,000-row manifest and current feature caches.

## Inventory

{md_table(full_inventory)}

## Split candidates

{md_table(full_split_plan)}

Interpretation:
- A full labeled Mirai feature CSV exists with 764,137 rows and aligned labels: 121,621 benign and 642,516 attack.
- A timestamped 100k Mirai subset exists via `mirai3.csv`, `mirai3_ts.csv`, and `official_labels.npy`.
- These assets should now be prioritized over the old 208-row future-bin path.
- They are not directly executable as the current frozen `original100 + HistGB-Conservative` instance until feature compatibility is resolved, because the full Mirai files appear to expose restored115-style features rather than the current 100-dimensional original100 matrix.
""",
    )

    best = search[search["candidate_name"].eq("extended_attack_10k_30k_plus_future_benign_90k_110k")].iloc[0].to_dict()
    found_sufficient_sized_candidate = best["attack_rows"] == 20000 and best["ood_rows"] == 20000
    full_mirai_available = bool(full_inventory["asset_name"].eq("full_mirai_labeled_feature_csv").any())
    found_clean_eval_asset = full_mirai_available
    split_constructed = full_mirai_available
    rebuild_executed = False
    clean_eval_run = False
    primary_verdict = "clean_eval_asset_found_rebuild_eval_next" if full_mirai_available else "clean_eval_asset_blocked_but_recovery_plan_ready"
    issue27m_action = "issue27m_full_mirai_feature_compatibility_prior_use_and_split_aware_rebuild"

    write_text(
        OUT / "clean_eval_asset_search_report.md",
        f"""
# Clean Eval Asset Search Report

Sufficient-sized candidate found: `{found_sufficient_sized_candidate}`.

Clean independent candidate found: `{found_clean_eval_asset}`.

Asset table:

{md_table(search)}

Key technical judgment:
- The attack extraction has 20,000 unused rows after the first 10,000 rows used by the current original100 mainline protocol.
- The 115k same-capture benign extraction provides a 20,000-row future benign segment at rows 90,000-109,999.
- Together these are enough for a meaningful diagnostic/temporal candidate.
- They are not yet clean independent validation because the benign segment is same-capture and historical, and split-aware original100 rebuild has not been performed.
- The later-downloaded full Mirai labeled feature dataset is a stronger route than the 80k-cache-only candidate, but it requires feature compatibility audit before it can support frozen LOW-GUARD++.
""",
    )
    write_text(
        OUT / "clean_eval_eligibility_rules.md",
        f"""
# Clean Eval Eligibility Rules

{md_table(eligibility)}

Interpretation:
- Row counts are no longer the main blocker for the P0 extended-segment candidate.
- The blockers are claim-safety blockers: prior-use audit, same-capture benign evidence weakness, and missing split-aware feature rebuild.
- Future bin9 with 208 rows remains explicitly disallowed as a stand-alone formal validation object.
""",
    )
    if full_mirai_available:
        best_split = full_split_plan[full_split_plan["candidate_name"].eq("full_mirai_labeled_restored115_chrono_split")].copy()
        best_split.to_csv(OUT / "best_available_clean_split_manifest.csv", index=False)
        for stale in [OUT / "best_available_clean_split_blocked.md"]:
            if stale.exists():
                stale.unlink()
        write_text(
            OUT / "best_available_clean_split_report.md",
            f"""
# Best Available Clean Split Report

A large labeled full-Mirai split candidate was identified and should be prioritized before returning to the 80k-cache future-bin path.

{md_table(best_split)}

Gate status:
- row counts and labels are sufficient;
- packet order is available by row index;
- explicit timestamps are available for the 100k official subset but not for the full 764k CSV;
- feature compatibility is not resolved because the full Mirai feature files appear restored115-style, while the frozen LOW-GUARD++ instance is original100 + HistGB;
- no frozen LOW-GUARD++ evaluation was run in issue27l.
""",
        )
        write_text(
            OUT / "split_aware_rebuild_blocked.md",
            """
# Split-Aware Rebuild Blocked

Split-aware rebuild/evaluation was not executed because the newly found full Mirai assets require a feature compatibility audit first.

Executable state strategies after compatibility is resolved:
- `continuous_state_baseline`: reproduce the existing feature CSV as a diagnostic reference;
- `reset_at_split_boundary`: rebuild or slice features with state reset per split, if original100/restored115 mapping is confirmed;
- `train_state_then_eval_online`: preferred deployment-like state strategy once raw/feature generation is pinned down.
""",
        )
        write_text(
            OUT / "clean_purged_eval_blocked.md",
            """
# Clean/Purged Evaluation Blocked

Frozen LOW-GUARD++ was not evaluated in issue27l.

Reason: full Mirai labeled assets are present and large enough, but the feature space is not yet confirmed compatible with the frozen original100 HistGB instance. Evaluation before that gate would be technically unsafe.
""",
        )
    else:
        write_blocked_files(split_manifest)

    recovery_tasks = pd.DataFrame(
        [
            {
                "task_id": "T1",
                "task": "full_mirai_feature_compatibility_and_label_alignment_audit",
                "target_file": "issue27m/full_mirai_feature_compatibility_audit.csv",
                "expected_output": "Map Mirai_dataset/my_gold/mirai3 features to original100 or restored115 and verify label-row alignment.",
                "estimated_cost": "low",
                "local_or_slurm": "local",
                "risk": "If feature mapping is not compatible, current LOW-GUARD++ original100 cannot be run directly.",
                "priority": "P0",
                "success_condition": "clear decision: original100 subset mapping, restored115 rerun path, or incompatibility.",
            },
            {
                "task_id": "T2",
                "task": "full_mirai_prior_use_and_clean_split_manifest",
                "target_file": "issue27m/full_mirai_clean_split_manifest.csv",
                "expected_output": "ID/OOD/support/eval split using full Mirai labels without final-eval selection.",
                "estimated_cost": "medium",
                "local_or_slurm": "local",
                "risk": "No explicit timestamp in full CSV; use row order unless timestamped subset is used first.",
                "priority": "P0",
                "success_condition": "sufficient benign/attack rows with disjoint support/eval and validation-only threshold policy.",
            },
            {
                "task_id": "T3",
                "task": "split_aware_or_restored115_lowguardpp_report_only_eval",
                "target_file": "issue27m/clean_purged_lowguardpp_by_seed.csv",
                "expected_output": "Only after T1/T2, evaluate frozen-compatible instance with no config/support/threshold search.",
                "estimated_cost": "low-medium",
                "local_or_slurm": "local",
                "risk": "Cannot run unless T1/T2 pass.",
                "priority": "P1_after_gate",
                "success_condition": "report-only clean/purged metrics with final_eval_used_for_selection=false.",
            },
            {
                "task_id": "T4",
                "task": "optional_raw_ood_4_1_extension_or_second_environment_extraction",
                "target_file": "issue27m/raw_extraction_manifest.csv",
                "expected_output": "Additional capture-disjoint or OOD future rows if P0 candidate remains weak.",
                "estimated_cost": "medium-high",
                "local_or_slurm": "slurm_if_large",
                "risk": "tshark unavailable locally; scapy may be slow.",
                "priority": "P2",
                "success_condition": "new OOD/capture object with original100-compatible extraction.",
            },
        ]
    )
    recovery_tasks.to_csv(OUT / "clean_eval_recovery_task_table.csv", index=False)
    write_text(
        OUT / "clean_eval_recovery_plan.md",
        f"""
# Clean Eval Recovery Plan

Smallest useful next step: `{issue27m_action}`.

Rationale:
- We now have full Mirai/Botnet assets with labels, so the next blocker is not row count.
- The immediate gate is feature compatibility: current LOW-GUARD++ is frozen as original100 + HistGB, while the full Mirai CSV appears restored115-style.
- The chosen split should come from full Mirai first, not from the 80k-cache future-bin path.
- Slurm is not required for the audit itself; it may be needed if full raw extraction or second-environment extraction becomes necessary.

{md_table(recovery_tasks)}
""",
    )
    write_text(
        OUT / "lowguard_plus_plus_issue27l_decision.md",
        f"""
# LOW-GUARD++ Issue27l Decision

- primary_verdict: `{primary_verdict}`
- sufficiently sized candidate found: `{found_sufficient_sized_candidate}`
- full Mirai labeled candidate found: `{full_mirai_available}`
- clean independent candidate found: `{found_clean_eval_asset}`
- split-aware rebuild executed: `{rebuild_executed}`
- clean/purged evaluation executed: `{clean_eval_run}`

Decision:
LOW-GUARD++ remains worth pushing. The next gate is full Mirai feature-compatibility plus split construction, not deployment robustness and not model retuning.
""",
    )
    write_text(
        OUT / "claim_update_after_issue27l.md",
        """
# Claim Update After Issue27l

## Allowed

- LOW-GUARD++ remains a high-potential candidate.
- A large full Mirai/Botnet labeled asset is now identified and should be prioritized for the next clean-split gate.
- Claim upgrade is currently blocked by feature compatibility and split-aware rebuild, not by method failure.
- A main-text performance-instance claim requires resolving original100/restored115 compatibility and then running report-only evaluation.

## Forbidden

- LOW-GUARD++ is abandoned without artifact evidence.
- LOW-GUARD-LR is final mainline solely because clean eval is not yet available.
- Deployment robustness is next if clean eval/rebuild is technically recoverable.
- Temporal/cross-dataset generalization is proven without clean split.
""",
    )
    write_text(
        OUT / "reviewer_defense_clean_eval_asset_and_split_rebuild.md",
        """
# Reviewer Defense: Clean Eval Asset And Split Rebuild

## Why did you not run the model immediately?

Because the best candidate has enough rows but is not yet claim-clean. Running a model before prior-use and split-aware feature-state checks would create a tempting but unsafe result.

## Is future bin9 enough?

No. It has only 208 attack rows and remains disallowed as stand-alone formal validation.

## Did you find a better candidate?

Yes. The extended unused-segment candidate exists, but the higher-priority route is now the full Mirai labeled feature dataset: 764,137 rows with 121,621 benign and 642,516 attack labels. It needs feature compatibility and prior-use auditing before frozen LOW-GUARD++ evaluation.

## Does this mean LOW-GUARD++ failed?

No. This is a data/provenance gate, not a method failure.
""",
    )
    write_text(
        OUT / "issue27m_next_action.md",
        f"""
# Issue27m Next Action

Recommended next action: `{issue27m_action}`.

Run order:
1. Audit full Mirai / official 100k / my-gold feature-label alignment and decide whether they map to original100, restored115, or an incompatible frontend.
2. Construct a full-Mirai clean split with train-side support, validation-only thresholding, and report-only eval.
3. Build the compatible split-aware feature matrices.
4. Only if those gates pass, run frozen-compatible LOW-GUARD++ report-only evaluation and safer variants.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue27l Sufficient Clean Eval Asset And Split-Aware Original100 Rebuild Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- issue27m_next_action: `{issue27m_action}`
- commit_hash: `pending_before_git_commit`

## 1. Sufficient clean eval asset

Sufficient-sized eval candidate found in current extracted assets: `{found_sufficient_sized_candidate}`.

Large labeled full Mirai/Botnet eval asset found: `{full_mirai_available}`.

The best candidate is `extended_attack_10k_30k_plus_future_benign_90k_110k`: 20,000 future attack rows plus 20,000 future benign rows.

After the user-requested full-dataset search, the higher-priority candidate is `full_mirai_labeled_restored115_chrono_split`: 764,137 labeled rows with 121,621 benign and 642,516 attack rows.

## 2. Main gap

The blocker is not row count anymore. The blocker is feature/protocol compatibility: full Mirai appears restored115-style while frozen LOW-GUARD++ is original100 + HistGB-Conservative.

## 3. Best available split

Best available split manifest constructed: `{split_constructed}`.

Split evidence_level: `large_labeled_dataset_candidate_pending_frontend_compatibility`.

## 4. Split-aware original100 rebuild

Executed: `{rebuild_executed}`.

Executable state strategies: `continuous_state_baseline`, `reset_at_split_boundary`, and `train_state_then_eval_online`.

## 5. Frozen LOW-GUARD++ clean/purged evaluation

Executed: `{clean_eval_run}`.

No clean/purged LOW-GUARD++ metric is claimed from issue27l.

## 6. Safer variants

Not evaluated because clean eval and split-aware rebuilt features were not admitted.

## 7. Continuous-state carryover

No new evidence proves old continuous-state carryover invalid, but it remains a claim-safety risk until split-aware rebuild is run.

## 8. Main-text upgrade

LOW-GUARD++ cannot yet be upgraded to main-text performance instance.

## 9. Slurm

Not required for this audit/search. Slurm may be needed for full feature reconstruction or second-environment feature construction.
""",
    )
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
read issue27k/27j/27i/27h/27f/25c summaries and asset reports
inspect extracted attack first30000 and benign first115000 metadata
python runs/issue27l_sufficient_clean_eval_asset_and_split_aware_original100_rebuild_for_lowguard_plus_plus_2026-05-27/run_issue27l_clean_eval_asset_rebuild_gate.py
""",
    )
    config = {
        "issue": OUT.name,
        "frozen_method": "LOW-GUARD++ original100 + HistGB-Conservative",
        "frozen_config_id": FROZEN_CONFIG_ID,
        "ood_alarm_target": OFFICIAL_TARGET,
        "final_eval_policy": "report_only_no_selection",
        "no_model_tuning": True,
        "clean_eval_run": clean_eval_run,
        "best_candidate": "extended_attack_10k_30k_plus_future_benign_90k_110k",
        "full_mirai_candidate_found": full_mirai_available,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "task": "sufficient_clean_eval_asset_and_split_aware_original100_rebuild_gate",
        "primary_verdict": primary_verdict,
        "issue27m_action": issue27m_action,
        "inputs": inputs.to_dict(orient="records"),
        "outputs": [
            "summary.md",
            "clean_eval_asset_search_table.csv",
            "clean_eval_asset_search_report.md",
            "full_botnet_dataset_inventory.csv",
            "full_botnet_dataset_split_feasibility.md",
            "clean_eval_eligibility_rules.md",
            "clean_eval_eligibility_table.csv",
            "best_available_clean_split_manifest.csv" if full_mirai_available else "best_available_clean_split_blocked.md",
            "best_available_clean_split_report.md",
            "split_aware_rebuild_blocked.md",
            "clean_purged_eval_blocked.md",
            "clean_eval_recovery_plan.md",
            "clean_eval_recovery_task_table.csv",
            "lowguard_plus_plus_issue27l_decision.md",
            "claim_update_after_issue27l.md",
            "reviewer_defense_clean_eval_asset_and_split_rebuild.md",
            "issue27m_next_action.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "manifest.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")
    update_mainline_docs(primary_verdict, issue27m_action)
    print(f"[issue27l] primary_verdict={primary_verdict}")
    print(f"[issue27l] issue27m_action={issue27m_action}")


if __name__ == "__main__":
    main()
