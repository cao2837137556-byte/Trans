from __future__ import annotations

import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27j_raw_provenance_recovery_and_clean_independent_split_construction_for_lowguard_plus_plus_2026-05-27"
ISSUE27I = ROOT / "runs" / "issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27"
ISSUE27H = ROOT / "runs" / "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27"
ISSUE27G = ROOT / "runs" / "issue27g_suspicious_perfect_score_audit_for_lowguard_plus_plus_2026-05-27"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
ISSUE26B = ROOT / "runs" / "issue26b_split_metadata_recovery_and_temporal_asset_build_2026-05-22"
ISSUE25C = ROOT / "runs" / "issue25c_strong_baseline_pack_execution_for_enhanced_lowguard_top64_2026-05-18"
ISSUE11 = ROOT / "runs" / "issue11_fixed_config_ood_guard_lr_ablation_2026-05-14"
MAINLINE = ROOT / "runs" / "mainline_docs"

KITNET_ROOT = ROOT.parents[1] / "KitNET-py-master" / "KitNET-py-master"
FRONTEND_ORIG = ROOT / "repo" / "kitsune_frontend_original"
FROZEN_CONFIG_ID = "histgb_d2_lr005_l2p1_ood4_sup4_t0050"
OFFICIAL_TARGET = 0.01


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


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


def safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def count_text_rows(path: Path, has_header: bool = False, comment_prefix: str | None = None) -> int | str:
    if not path.exists() or path.is_dir():
        return "NA"
    n = 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if comment_prefix and line.startswith(comment_prefix):
                continue
            if not line.strip():
                continue
            n += 1
    return max(0, n - (1 if has_header else 0))


def npy_shape(path: Path) -> str:
    if not path.exists():
        return "NA"
    arr = np.load(path, mmap_mode="r")
    return "x".join(map(str, arr.shape))


def csv_shape(path: Path, sep: str = ",", has_header: bool = True) -> str:
    if not path.exists():
        return "NA"
    try:
        sample = pd.read_csv(path, sep=sep, nrows=1, header=0 if has_header else None)
        n_cols = int(sample.shape[1])
        n_rows = count_text_rows(path, has_header=has_header)
        return f"{n_rows}x{n_cols}"
    except Exception:
        return "NA"


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def required_input_status() -> pd.DataFrame:
    required = [
        ISSUE27I / "summary.md",
        ISSUE27I / "available_independent_assets_inventory.csv",
        ISSUE27I / "available_independent_assets_diagnosis.md",
        ISSUE27I / "separator_stability_nonlocked_by_asset.csv",
        ISSUE27I / "frozen_lowguardpp_nonlocked_by_asset.csv",
        ISSUE27I / "safer_feature_variants_summary.csv",
        ISSUE27I / "data_expansion_feasibility_plan.md",
        ISSUE27I / "claim_update_after_issue27i.md",
        ISSUE27H / "summary.md",
        ISSUE27H / "feature_provenance_mapping.csv",
        ISSUE27H / "separator_distribution_by_split.csv",
        ISSUE27H / "feature_ablation_summary.csv",
        ISSUE27G / "summary.md",
        ISSUE27F / "summary.md",
        ISSUE26B / "summary.md",
        ISSUE25C / "summary.md",
        MAINLINE / "mainline_handoff.md",
        MAINLINE / "mainline_experiment_map.md",
        ISSUE11 / "config.json",
    ]
    rows = [{"path": safe_rel(p), "exists": p.exists(), "required": True} for p in required]
    return pd.DataFrame(rows)


def parse_zeek_fields(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("#fields"):
                fields_raw = line.rstrip("\n").split("\t")[1:]
                if fields_raw and "label" in fields_raw[-1] and "detailed-label" in fields_raw[-1]:
                    tail = re.split(r"\s{2,}", fields_raw[-1].strip())
                    return fields_raw[:-1] + tail
                return fields_raw
    return []


def asset_row(
    *,
    name: str,
    path: Path,
    asset_type: str,
    row_count: int | str = "NA",
    contains_original100: bool = False,
    contains_raw_timestamp: bool = False,
    contains_packet_order: bool = False,
    contains_row_id: bool = False,
    contains_capture_id: bool = False,
    contains_session_id: bool = False,
    contains_bin_id: bool = False,
    contains_window_start_end: bool = False,
    contains_label_mapping: bool = False,
    contains_feature_name_mapping: bool = False,
    can_reconstruct_original100: bool = False,
    can_build_temporal_split: bool = False,
    can_build_capture_disjoint_split: bool = False,
    can_build_purged_split: bool = False,
    limitations: str = "",
    next_action: str = "",
) -> dict[str, Any]:
    return {
        "asset_name": name,
        "asset_path": str(path),
        "exists": bool(path.exists()),
        "asset_type": asset_type,
        "row_count": row_count,
        "contains_original100": contains_original100,
        "contains_raw_timestamp": contains_raw_timestamp,
        "contains_packet_order": contains_packet_order,
        "contains_row_id": contains_row_id,
        "contains_capture_id": contains_capture_id,
        "contains_session_id": contains_session_id,
        "contains_bin_id": contains_bin_id,
        "contains_window_start_end": contains_window_start_end,
        "contains_label_mapping": contains_label_mapping,
        "contains_feature_name_mapping": contains_feature_name_mapping,
        "can_reconstruct_original100": can_reconstruct_original100,
        "can_build_temporal_split": can_build_temporal_split,
        "can_build_capture_disjoint_split": can_build_capture_disjoint_split,
        "can_build_purged_split": can_build_purged_split,
        "limitations": limitations,
        "next_action": next_action,
    }


def raw_provenance_inventory(cfg: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Path], pd.DataFrame]:
    paths = {k: Path(v) for k, v in cfg["paths"].items()}
    stage2_manifest = read_json(paths["stage2_manifest"])
    stage1_manifest = read_json(KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data_manifest.json")
    id_meta_path = KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_id_7_6" / "extract_metadata.json"
    ood_meta_path = KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_ood_4_1" / "extract_metadata.json"
    attack_meta_path = KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "extract_attack_34_1" / "extract_metadata.json"
    id_meta = read_json(id_meta_path)
    ood_meta = read_json(ood_meta_path)
    attack_meta = read_json(attack_meta_path)

    known = {
        "id_pcap": KITNET_ROOT / id_meta["source_pcap"],
        "id_tsv": Path(id_meta["tsv_path"]),
        "id_feature_npy_full": Path(id_meta["feature_path"]),
        "id_source_npy": paths["original100_id"],
        "id_source_csv": Path(stage1_manifest["outputs"]["id_csv"]),
        "id_feature_headers": id_meta_path.parent / "feature_headers.txt",
        "ood_pcap": KITNET_ROOT / ood_meta["source_pcap"],
        "ood_tsv": Path(ood_meta["tsv_path"]),
        "ood_feature_npy_full": Path(ood_meta["feature_path"]),
        "ood_source_npy": paths["original100_ood"],
        "ood_source_csv": Path(stage1_manifest["outputs"]["ood_csv"]),
        "ood_feature_headers": ood_meta_path.parent / "feature_headers.txt",
        "attack_pcap": KITNET_ROOT / attack_meta["source_pcap"],
        "attack_tsv": Path(attack_meta["tsv_path"]),
        "attack_feature_npy_full": Path(attack_meta["feature_path"]),
        "attack_source_csv": paths["original100_attack"],
        "attack_feature_headers": attack_meta_path.parent / "feature_headers.txt",
        "attack_zeek_log": Path(stage2_manifest["source_zeek_log"]),
        "stage1_manifest": KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data_manifest.json",
        "stage2_manifest": paths["stage2_manifest"],
        "frontend_netstat": FRONTEND_ORIG / "netStat.py",
        "frontend_afterimage": FRONTEND_ORIG / "AfterImage.py",
        "frontend_feature_extractor": FRONTEND_ORIG / "FeatureExtractor.py",
        "frontend_extract_script": KITNET_ROOT / "repo" / "ood" / "kitsune_frontend_original_extract.py",
        "second_env_ciciot_raw": KITNET_ROOT / "public_data" / "raw" / "CICIoT2023_2.csv",
    }

    rows: list[dict[str, Any]] = []
    for prefix in ["id", "ood", "attack"]:
        pcap = known[f"{prefix}_pcap"]
        tsv = known[f"{prefix}_tsv"]
        full = known[f"{prefix}_feature_npy_full"]
        source = known[f"{prefix}_source_npy"] if prefix != "attack" else known["attack_source_csv"]
        headers = known[f"{prefix}_feature_headers"]
        rows.append(asset_row(name=f"{prefix}_raw_pcap", path=pcap, asset_type="pcap", row_count="binary_pcap", contains_raw_timestamp=True, contains_packet_order=True, contains_capture_id=True, can_reconstruct_original100=True, can_build_temporal_split=True, limitations="No persisted packet hash manifest; mapping relies on deterministic extraction order.", next_action="Rebuild with explicit row_id/packet_id/hash manifest."))
        rows.append(asset_row(name=f"{prefix}_extracted_tsv", path=tsv, asset_type="tsv_packet_table", row_count=count_text_rows(tsv, has_header=True), contains_raw_timestamp=True, contains_packet_order=True, contains_row_id=True, contains_capture_id=True, can_reconstruct_original100=True, can_build_temporal_split=True, can_build_purged_split=True, limitations="Row_id is implicit row order, not a persisted explicit id column.", next_action="Persist explicit row_id, packet_order, timestamp, capture_id, and feature_row mapping."))
        rows.append(asset_row(name=f"{prefix}_full_feature_npy", path=full, asset_type="npy_feature_matrix", row_count=npy_shape(full), contains_original100=True, contains_row_id=False, contains_feature_name_mapping=False, can_reconstruct_original100=False, limitations="Feature matrix has no embedded timestamp or row ids.", next_action="Join to TSV by extraction row order and verify hashes."))
        rows.append(asset_row(name=f"{prefix}_source_matrix", path=source, asset_type="source_feature_matrix", row_count=(npy_shape(source) if source.suffix == ".npy" else csv_shape(source, has_header=False)), contains_original100=True, contains_row_id=False, contains_feature_name_mapping=False, can_reconstruct_original100=False, limitations="Current paper asset used by experiments; provenance is implicit via stage metadata.", next_action="Generate sidecar row-level manifest."))
        rows.append(asset_row(name=f"{prefix}_feature_headers", path=headers, asset_type="feature_name_mapping", row_count=count_text_rows(headers), contains_feature_name_mapping=True, can_reconstruct_original100=True, limitations="Feature names only; no row provenance.", next_action="Use with extractor sidecar manifest."))

    zeek_fields = parse_zeek_fields(known["attack_zeek_log"])
    rows.append(asset_row(name="attack_zeek_labeled_log", path=known["attack_zeek_log"], asset_type="zeek_labeled_log", row_count=count_text_rows(known["attack_zeek_log"], comment_prefix="#"), contains_raw_timestamp=("ts" in zeek_fields), contains_packet_order=False, contains_capture_id=True, contains_session_id=("uid" in zeek_fields), contains_label_mapping=("label" in zeek_fields), can_build_temporal_split=True, can_build_capture_disjoint_split=False, can_build_purged_split=True, limitations="Flow-level labels do not provide packet-level one-to-one labels without timestamp/window mapping.", next_action="Persist bin/window mapping between TSV packet rows and Zeek flow labels."))
    rows.append(asset_row(name="stage1_data_manifest", path=known["stage1_manifest"], asset_type="json_manifest", row_count="NA", contains_original100=True, contains_capture_id=True, contains_label_mapping=True, limitations="Capture-level and file-level provenance, not row-level split manifest.", next_action="Convert source slices into explicit row manifests."))
    rows.append(asset_row(name="stage2_attack_manifest", path=known["stage2_manifest"], asset_type="json_manifest", row_count=len(stage2_manifest.get("bin_level_stats", [])), contains_raw_timestamp=False, contains_packet_order=False, contains_bin_id=True, contains_label_mapping=True, contains_window_start_end=False, can_build_temporal_split=True, can_build_purged_split=False, limitations="Has bin IDs and counts, but no per-row timestamp ranges or support/eval row IDs.", next_action="Recompute and save row-level bin/timestamp mapping."))
    rows.append(asset_row(name="frontend_original_netstat", path=known["frontend_netstat"], asset_type="source_code", contains_feature_name_mapping=True, can_reconstruct_original100=True, limitations="Defines feature semantics but not row provenance.", next_action="Use only for lineage audit."))
    rows.append(asset_row(name="frontend_original_afterimage", path=known["frontend_afterimage"], asset_type="source_code", contains_feature_name_mapping=True, can_reconstruct_original100=True, limitations="Defines decay/stat update semantics; no data asset.", next_action="Use only for lineage audit."))
    rows.append(asset_row(name="frontend_original_extract_script", path=known["frontend_extract_script"], asset_type="source_code", contains_raw_timestamp=True, contains_packet_order=True, contains_row_id=True, can_reconstruct_original100=True, limitations="Can rebuild features but current script does not emit a row-level sidecar manifest.", next_action="Patch/re-run extraction with sidecar provenance if needed."))
    rows.append(asset_row(name="second_env_ciciot_raw", path=known["second_env_ciciot_raw"], asset_type="external_raw_csv", row_count=csv_shape(known["second_env_ciciot_raw"]) if known["second_env_ciciot_raw"].exists() else "NA", contains_raw_timestamp=False, contains_packet_order=False, contains_capture_id=False, contains_label_mapping=True, can_reconstruct_original100=False, limitations="Schema is not Kitsune original100-compatible without a dedicated feature builder.", next_action="Treat as future second-environment feasibility, not issue27j clean split."))

    inv = pd.DataFrame(rows)

    attack_tsv = pd.read_csv(known["attack_tsv"], sep="\t", nrows=int(stage2_manifest["use_first_n"]))
    ts = pd.to_numeric(attack_tsv["frame.time_epoch"], errors="coerce")
    ts0 = float(ts.min())
    bins = ((ts - ts0) // int(stage2_manifest["bin_seconds"])).astype(int)
    attack_row_map = pd.DataFrame(
        {
            "row_id": np.arange(len(attack_tsv), dtype=np.int64),
            "timestamp": ts.to_numpy(),
            "bin": bins.to_numpy(),
            "source_capture": "CTU-IoT-Malware-Capture-34-1",
        }
    )
    bin_counts = attack_row_map.groupby("bin", as_index=False).agg(
        row_count=("row_id", "size"),
        timestamp_min=("timestamp", "min"),
        timestamp_max=("timestamp", "max"),
    )
    manifest_bins = pd.DataFrame(stage2_manifest["bin_level_stats"])
    bin_counts = bin_counts.merge(manifest_bins, on="bin", how="left")
    return inv, known, bin_counts


def hh_lineage() -> pd.DataFrame:
    rows = [
        {
            "feature_name": "HH_radius_lambda_0.01",
            "original100_index": 46,
            "channel_or_grouping": "HH = host-host bandwidth stream keyed by srcIP,dstIP",
            "statistic": "radius",
            "lambda": 0.01,
            "source_code_location": "repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:88-98,390-391",
            "calculation": "update_get_1D2D_Stats returns weight/mean/std plus radius/magnitude/covariance/pcc after sequential update for the current packet.",
        },
        {
            "feature_name": "HH_magnitude_lambda_0.01",
            "original100_index": 47,
            "channel_or_grouping": "HH = host-host bandwidth stream keyed by srcIP,dstIP",
            "statistic": "magnitude",
            "lambda": 0.01,
            "source_code_location": "repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:94-98,390-391",
            "calculation": "Magnitude is sqrt(sum(mean^2)) over paired stream statistics after decay/update.",
        },
        {
            "feature_name": "HH_radius_lambda_0.1",
            "original100_index": 39,
            "channel_or_grouping": "HH = host-host bandwidth stream keyed by srcIP,dstIP",
            "statistic": "radius",
            "lambda": 0.1,
            "source_code_location": "repo/kitsune_frontend_original/netStat.py:88-92; repo/kitsune_frontend_original/AfterImage.py:88-98,390-391",
            "calculation": "Same HH radius statistic at faster decay lambda=0.1.",
        },
    ]
    out = pd.DataFrame(rows)
    out["uses_future_packets"] = False
    out["uses_current_packet"] = True
    out["online_deployable_if_state_available"] = True
    out["computed_before_split_in_current_assets"] = True
    out["temporal_leakage_risk"] = "medium_if_validation_requires_split-reset_state"
    out["capture_artifact_risk"] = "medium_low_until_session_disjoint_check"
    out["needs_splitwise_reconstruction"] = True
    out["notes"] = "No explicit label/split/bin feature, but the feature state is time-evolving and can carry capture/window conditions."
    return out


def clean_split_feasibility(raw_inv: pd.DataFrame, bin_counts: pd.DataFrame) -> pd.DataFrame:
    future_bin = bin_counts[bin_counts["bin"].eq(9)]
    future_rows = int(future_bin["row_count"].iloc[0]) if len(future_bin) else 0
    rows = [
        {
            "split_name": "chronological_forward_split",
            "required_metadata": "packet timestamp; attack row->bin mapping; ID/OOD train/cal/val/eval maps",
            "available": "partial",
            "can_construct_now": False,
            "leakage_risk": "medium",
            "expected_evidence_level": "blocked_for_formal_independent",
            "blocked_reason": "Earlier/later packet bins can be recovered, but current clean future attack window outside bins 5/6/7/8 is too small and OOD independent object is not new.",
            "construction_steps": "Persist row-level attack/ID/OOD manifests; define unused future window; keep final eval report-only.",
            "recommended_priority": "P0",
        },
        {
            "split_name": "purged_chronological_split",
            "required_metadata": "timestamp/window boundary plus embargo gap and splitwise feature reconstruction",
            "available": "partial",
            "can_construct_now": False,
            "leakage_risk": "low_after_reconstruction_high_before",
            "expected_evidence_level": "blocked_for_formal_independent",
            "blocked_reason": "Feature state was computed continuously before splits; purged validation should rebuild/reset state around split boundaries.",
            "construction_steps": "Re-extract original100 with sidecar row manifest and optional state reset/gap.",
            "recommended_priority": "P0",
        },
        {
            "split_name": "future_window_eval_bin9",
            "required_metadata": "unused bin 9 row ids and enough attack rows",
            "available": "partial",
            "can_construct_now": False,
            "leakage_risk": "medium",
            "expected_evidence_level": "small_diagnostic_only",
            "blocked_reason": f"Bin 9 is outside locked bins but has only {future_rows} packet rows and was below the previous holdout min_eval_rows=300 / min_conn_per_bin=120 gate.",
            "construction_steps": "Could run only as a labeled diagnostic after explicit approval; not sufficient for issue27j formal clean validation.",
            "recommended_priority": "P1_diagnostic",
        },
        {
            "split_name": "capture_disjoint_split",
            "required_metadata": "additional attack/benign captures with compatible original100 extraction",
            "available": "no",
            "can_construct_now": False,
            "leakage_risk": "unknown",
            "expected_evidence_level": "blocked_for_formal_independent",
            "blocked_reason": "Current roles are already capture-separated for ID/OOD/attack, but there is no unused attack capture/session with matching original100 assets for independent validation.",
            "construction_steps": "Recover or create second attack/benign capture original100 assets with row-level manifests.",
            "recommended_priority": "P1",
        },
        {
            "split_name": "second_environment_split",
            "required_metadata": "compatible raw traffic, labels, and Kitsune original100 reconstruction",
            "available": "partial",
            "can_construct_now": False,
            "leakage_risk": "medium_until_builder_compatible",
            "expected_evidence_level": "future_external_validation",
            "blocked_reason": "Potential raw external CSVs exist, but schema is not currently mapped into Kitsune original100.",
            "construction_steps": "Build/reuse original100 feature builder and pre-register split before evaluation.",
            "recommended_priority": "P2",
        },
    ]
    return pd.DataFrame(rows)


def raw_data_expansion_tasks() -> pd.DataFrame:
    rows = [
        {
            "task": "create_original100_row_sidecar_manifest",
            "target_file": "runs/<new_extraction>/row_level_original100_manifest.csv",
            "script_to_inspect_or_create": "repo/ood/kitsune_frontend_original_extract.py",
            "expected_output": "row_id, packet_order, timestamp, capture_id, source_pcap, feature_row, hash/fingerprint",
            "estimated_cost": "low_medium",
            "local_or_slurm": "local_for_current_30k; slurm_if_large",
            "risk": "low",
            "priority": "P0",
        },
        {
            "task": "rebuild_attack_original100_with_sidecar",
            "target_file": "runs/issue27k_provenance_rebuild/attack_original100_with_manifest.npy",
            "script_to_inspect_or_create": "repo/ood/kitsune_frontend_original_extract.py",
            "expected_output": "Feature matrix exactly matching current attack rows plus explicit row mapping",
            "estimated_cost": "medium",
            "local_or_slurm": "local_possible_for_30k",
            "risk": "medium_due_exact_reproducibility_check",
            "priority": "P0",
        },
        {
            "task": "construct_purged_chronological_candidate",
            "target_file": "runs/issue27k_clean_split/clean_split_manifest.csv",
            "script_to_inspect_or_create": "new issue27k split builder",
            "expected_output": "train/cal/val/eval ids, timestamp ranges, purge gap, support/eval disjointness",
            "estimated_cost": "medium",
            "local_or_slurm": "local",
            "risk": "medium_if_future_window_small",
            "priority": "P0",
        },
        {
            "task": "recover_additional_capture_or_session",
            "target_file": "runs/issue27k_capture_disjoint_assets/",
            "script_to_inspect_or_create": "repo/ood/kitsune_frontend_original_extract.py and raw public_data",
            "expected_output": "Unused attack/benign capture original100 assets",
            "estimated_cost": "medium_high",
            "local_or_slurm": "maybe_slurm",
            "risk": "medium",
            "priority": "P1",
        },
        {
            "task": "second_environment_feature_builder_check",
            "target_file": "runs/issue27k_second_environment_feasibility/",
            "script_to_inspect_or_create": "new compatibility audit",
            "expected_output": "Whether external raw traffic can be mapped to Kitsune original100",
            "estimated_cost": "high",
            "local_or_slurm": "slurm_if_large",
            "risk": "medium_schema_confounding",
            "priority": "P2",
        },
    ]
    return pd.DataFrame(rows)


def update_mainline_docs(primary_verdict: str, issue27k_action: str) -> None:
    handoff = MAINLINE / "mainline_handoff.md"
    expmap = MAINLINE / "mainline_experiment_map.md"
    handoff_append = f"""

## issue27j raw provenance and clean split audit (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: recovers raw pcap/TSV/source-code provenance for original100, audits HH separator lineage, checks clean split feasibility, and blocks formal clean validation until a row-level clean split is built.
- claim boundary: LOW-GUARD++ remains a high-potential candidate; current evidence does not justify main-text performance-instance upgrade without clean independent validation.
- next action: `{issue27k_action}`.
"""
    expmap_append = f"""
| issue27j | raw provenance and clean split audit for LOW-GUARD++ | `{primary_verdict}` | Recovered raw pcap/TSV/source-code provenance but found clean independent validation still blocked by insufficient unused future/capture split assets. Next: `{issue27k_action}`. |
"""
    htxt = handoff.read_text(encoding="utf-8")
    htxt = re.sub(r"\n## issue27j raw provenance and clean split audit \(2026-05-27\)\n.*?(?=\n## |\Z)", "", htxt, flags=re.S)
    handoff.write_text(htxt.rstrip() + handoff_append + "\n", encoding="utf-8")
    etxt = expmap.read_text(encoding="utf-8")
    etxt = re.sub(r"(?m)^\| issue27j \|.*\|\r?\n?", "", etxt)
    expmap.write_text(etxt.rstrip() + "\n\n" + expmap_append.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    input_status = required_input_status()
    input_status.to_csv(OUT / "manifest.csv", index=False)
    missing = input_status[input_status["required"] & ~input_status["exists"]]
    if len(missing):
        write_text(OUT / "summary.md", "primary_verdict: `clean_validation_blocked_by_missing_raw_assets`\n\nRequired inputs missing; see manifest.csv.")
        raise SystemExit(1)

    cfg = read_json(ISSUE11 / "config.json")
    raw_inv, known_paths, bin_counts = raw_provenance_inventory(cfg)
    raw_inv.to_csv(OUT / "raw_provenance_inventory.csv", index=False)
    lineage = hh_lineage()
    lineage.to_csv(OUT / "hh_separator_lineage_audit.csv", index=False)
    split_feas = clean_split_feasibility(raw_inv, bin_counts)
    split_feas.to_csv(OUT / "clean_split_construction_feasibility.csv", index=False)
    expansion = raw_data_expansion_tasks()
    expansion.to_csv(OUT / "raw_data_expansion_task_table.csv", index=False)

    raw_packet_found = bool(raw_inv["exists"].astype(bool).any() and raw_inv["contains_raw_timestamp"].astype(bool).any())
    row_level_recoverable = bool(raw_inv[raw_inv["asset_type"].eq("tsv_packet_table")]["exists"].all())
    can_clean_now = bool(split_feas["can_construct_now"].astype(bool).any())
    temporal_feature_leakage_found = False
    capture_artifact_found = False

    if temporal_feature_leakage_found:
        primary_verdict = "lowguard_plus_plus_blocked_by_temporal_feature_leakage"
    elif capture_artifact_found:
        primary_verdict = "lowguard_plus_plus_blocked_by_capture_artifact"
    elif raw_packet_found and row_level_recoverable and not can_clean_now:
        primary_verdict = "clean_independent_validation_blocked_but_recoverable"
    else:
        primary_verdict = "clean_validation_blocked_by_missing_raw_assets"
    issue27k_action = "issue27k_row_level_original100_rebuild_and_purged_split_construction"

    clean_block = """
# Clean Independent Split Blocked

No formal clean independent split was constructed in issue27j.

Blocking reasons:
- Raw pcap and TSV timestamp assets exist, and row-level mapping is recoverable by extraction order.
- However, the current paper matrices do not have a persisted sidecar row manifest with packet hash / packet_order / timestamp / capture_id.
- The only obvious unused future attack window is bin 9, which has too few packet rows for a stable formal validation object.
- The current OOD final object is not a new independent OOD environment.
- A purged split should rebuild/reset Kitsune state around split boundaries before it is used as formal evidence.
"""
    write_text(OUT / "clean_independent_split_blocked.md", clean_block)
    write_text(OUT / "clean_independent_split_report.md", clean_block)
    eval_block = """
# Clean Independent LOW-GUARD++ Evaluation Blocked

Frozen LOW-GUARD++ was not evaluated on a clean independent split because no clean split was constructed.

This is a provenance/split-construction blocker, not evidence that LOW-GUARD++ failed.
"""
    write_text(OUT / "clean_independent_eval_blocked.md", eval_block)

    write_text(
        OUT / "raw_provenance_recovery_report.md",
        f"""
# Raw Provenance Recovery Report

Raw packet / timestamp assets found: `{raw_packet_found}`.
Row-level mapping recoverable by extraction order: `{row_level_recoverable}`.

Key recovered assets:

{md_table(raw_inv[['asset_name','asset_type','exists','row_count','contains_raw_timestamp','contains_packet_order','contains_row_id','contains_capture_id','contains_label_mapping','can_reconstruct_original100','limitations']], 30)}

Attack bin counts recovered from TSV + stage2 manifest:

{md_table(bin_counts, 12)}

Interpretation:
- Current original100 source matrices can be traced back to pcap -> TSV -> feature extraction -> source matrix slices.
- This gives useful provenance, but it is still not a formal clean validation split because the row-level sidecar was not persisted and unused future/capture validation assets are insufficient.
""",
    )
    write_text(
        OUT / "hh_separator_lineage_report.md",
        f"""
# HH Separator Lineage Report

The three separator features are legal Kitsune/KitNET traffic-stat features, not explicit labels or split IDs.

{md_table(lineage)}

Technical interpretation:
- HH uses host-host traffic state keyed by `srcIP,dstIP`.
- `radius` and `magnitude` are derived from decayed mean/variance statistics in AfterImage.
- The extractor updates and then reports stats for the current packet; it does not use future packets.
- Because current features were generated continuously over each capture before downstream splits, a strict temporal validation should rebuild/reset feature state or use purge/embargo to avoid adjacent-window state carryover.
- The features are online-computable in deployment, but they can still encode capture/window conditions through decayed traffic history.
""",
    )
    write_text(
        OUT / "clean_split_construction_report.md",
        f"""
# Clean Split Construction Report

Clean independent split constructable now: `{can_clean_now}`.

{md_table(split_feas)}

Conclusion:
- Issue27j recovers enough raw provenance to define what a clean split should look like.
- It does not yet produce a formal clean independent validation object.
- The next step should build a row-level original100 manifest and then construct a purged chronological or capture/session-disjoint split.
""",
    )
    write_text(
        OUT / "raw_data_expansion_implementation_plan.md",
        f"""
# Raw Data Expansion Implementation Plan

Recommended next action: `{issue27k_action}`.

Minimum required fields:
- raw packet timestamp;
- packet_order / packet_id;
- capture/session id;
- row_id and feature_row;
- window_start / window_end;
- attack label mapping;
- benign OOD mapping;
- feature name mapping;
- original100 reconstruction script or reproducible extraction command.

{md_table(expansion)}

Compute note: current 30k/50k extraction is likely local-feasible. Slurm may be useful for full-capture or second-environment reconstruction.
""",
    )
    write_text(
        OUT / "lowguard_plus_plus_raw_provenance_decision.md",
        f"""
# LOW-GUARD++ Raw Provenance Decision

- primary_verdict: `{primary_verdict}`
- issue27k_next_action: `{issue27k_action}`

Decision:
- Do not abandon LOW-GUARD++.
- Do not upgrade LOW-GUARD++ to a main-text performance instance yet.
- Treat issue27f/27g as audited locked evidence, and issue27j as a provenance recovery gate.
- Move next to row-level original100 rebuild + purged clean split construction.
""",
    )
    if primary_verdict in {"clean_independent_validation_blocked_but_recoverable", "clean_validation_blocked_by_missing_raw_assets", "raw_provenance_recovered_clean_eval_next"}:
        allowed = """
- LOW-GUARD++ remains a high-potential candidate.
- Claim upgrade is blocked by raw provenance or clean split construction, not by evidence of method failure.
- Further raw provenance recovery or data expansion is required.
"""
    else:
        allowed = """
- LOW-GUARD++ cannot be upgraded under current original100 construction due to temporal/capture artifact risk.
- A leakage-safe reconstruction is required before re-evaluation.
"""
    write_text(
        OUT / "claim_update_after_issue27j.md",
        f"""
# Claim Update After Issue27j

## Allowed

{allowed}

## Forbidden

- LOW-GUARD++ is abandoned without artifact evidence.
- LOW-GUARD-LR is final mainline solely because clean split is not yet available.
- Deployment robustness is the next step if clean validation is still technically recoverable.
- Temporal/cross-dataset generalization is proven without clean split.
""",
    )
    write_text(
        OUT / "reviewer_defense_raw_provenance_and_clean_split.md",
        f"""
# Reviewer Defense: Raw Provenance And Clean Split

## Q1: Did you find raw packet / timestamp provenance?

Yes, pcap and extracted TSV assets exist for the current original100 sources. The mapping is recoverable by deterministic extraction order, but a formal row-level sidecar manifest has not yet been persisted.

## Q2: Do HH separators use future information?

No future packet use was found in the feature code. The extractor updates and reports sequential state for the current packet. The remaining risk is split-boundary state carryover and capture/window conditions, not explicit future labels.

## Q3: Why not run clean independent validation now?

Because a clean unused split with sufficient attack rows and independent OOD evidence is not currently available. Bin 9 is too small for formal validation, and current OOD eval is not a new independent object.

## Q4: Does this mean LOW-GUARD++ failed?

No. It means the clean-claim gate is blocked by provenance/split construction. The proper next step is rebuilding row-level manifests and constructing purged or capture-disjoint validation.
""",
    )
    write_text(
        OUT / "issue27k_next_action.md",
        f"""
# Issue27k Next Action

Recommended next action: `{issue27k_action}`.

Scope:
- rebuild original100 with explicit row-level sidecar provenance;
- verify feature matrix equivalence to current cached assets;
- construct purged chronological and/or capture/session-disjoint split;
- only then run frozen LOW-GUARD++ and LOW-GUARD-LR reference.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue27j Raw Provenance And Clean Split Audit Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- issue27k_next_action: `{issue27k_action}`

## 1. Raw provenance

Raw pcap / timestamp assets found: `{raw_packet_found}`.
Row-level mapping recoverable by extraction order: `{row_level_recoverable}`.

## 2. HH separator lineage

The three HH separator features were traced to legal Kitsune traffic-stat logic: HH radius/magnitude over host-host streams at lambda 0.01 / 0.1.

No explicit future-information or label/split/bin field was found. Remaining risk: continuous pre-split feature-state computation can carry temporal/capture context, so clean temporal validation should rebuild or reset state around split boundaries.

## 3. Clean independent split

Clean independent split constructable now: `{can_clean_now}`.

Blocked because:
- no persisted full sidecar row manifest;
- unused future attack window is too small for formal validation;
- no new independent OOD/capture object is ready;
- purged validation requires split-aware reconstruction or reset.

## 4. Clean LOW-GUARD++ validation

Not run. This is a split/provenance blocker, not a method-failure result.

## 5. Claim status

LOW-GUARD++ cannot yet be upgraded to main-text performance instance. It remains a high-potential audited candidate.

## 6. Slurm

Not needed for this audit. May be needed for full raw reconstruction or second-environment extraction.
""",
    )
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
read issue27i/27h/27g/27f/26b/25c assets
inspect raw pcap/tsv/manifest/source-code provenance
python runs/issue27j_raw_provenance_recovery_and_clean_independent_split_construction_for_lowguard_plus_plus_2026-05-27/run_issue27j_raw_provenance_clean_split.py
""",
    )
    config = {
        "issue": OUT.name,
        "frozen_method": "LOW-GUARD++ original100 + HistGB-Conservative",
        "frozen_config_id": FROZEN_CONFIG_ID,
        "ood_alarm_target": OFFICIAL_TARGET,
        "final_eval_policy": "report_only_no_selection",
        "no_hyperparameter_search": True,
        "no_support_search": True,
        "clean_eval_run": False,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "task": "raw_provenance_recovery_and_clean_independent_split_construction",
        "primary_verdict": primary_verdict,
        "issue27k_action": issue27k_action,
        "inputs": input_status.to_dict(orient="records"),
        "outputs": [
            "summary.md",
            "raw_provenance_inventory.csv",
            "raw_provenance_recovery_report.md",
            "hh_separator_lineage_audit.csv",
            "hh_separator_lineage_report.md",
            "clean_split_construction_feasibility.csv",
            "clean_split_construction_report.md",
            "clean_independent_split_blocked.md",
            "clean_independent_split_report.md",
            "clean_independent_eval_blocked.md",
            "raw_data_expansion_implementation_plan.md",
            "raw_data_expansion_task_table.csv",
            "lowguard_plus_plus_raw_provenance_decision.md",
            "claim_update_after_issue27j.md",
            "reviewer_defense_raw_provenance_and_clean_split.md",
            "issue27k_next_action.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "manifest.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")
    update_mainline_docs(primary_verdict, issue27k_action)
    print(f"[issue27j] primary_verdict={primary_verdict}")
    print(f"[issue27j] issue27k_action={issue27k_action}")


if __name__ == "__main__":
    main()
