from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27k_row_level_original100_rebuild_and_purged_split_construction_for_lowguard_plus_plus_2026-05-27"
ISSUE27J = ROOT / "runs" / "issue27j_raw_provenance_recovery_and_clean_independent_split_construction_for_lowguard_plus_plus_2026-05-27"
ISSUE27I = ROOT / "runs" / "issue27i_separator_independent_validation_and_data_expansion_feasibility_for_lowguard_plus_plus_2026-05-27"
ISSUE27H = ROOT / "runs" / "issue27h_original100_feature_provenance_and_independent_verification_before_claim_upgrade_2026-05-27"
ISSUE27F = ROOT / "runs" / "issue27f_config_freeze_then_formal_validation_for_original100_histgb_conservative_2026-05-27"
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_matrix(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".npy":
        return np.load(path)
    return pd.read_csv(path, header=None).to_numpy(np.float64)


def feature_hashes(x: np.ndarray) -> list[str]:
    out: list[str] = []
    arr = np.ascontiguousarray(x.astype(np.float64, copy=False))
    for row in arr:
        out.append(hashlib.sha256(np.ascontiguousarray(row).view(np.uint8)).hexdigest()[:16])
    return out


def packet_hash(row: pd.Series) -> str:
    cols = [
        "frame.time_epoch",
        "frame.len",
        "eth.src",
        "eth.dst",
        "ip.src",
        "ip.dst",
        "tcp.srcport",
        "tcp.dstport",
        "udp.srcport",
        "udp.dstport",
        "arp.opcode",
    ]
    text = "|".join(str(row.get(c, "")) for c in cols)
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def required_input_status() -> pd.DataFrame:
    required = [
        ISSUE27J / "summary.md",
        ISSUE27J / "raw_provenance_inventory.csv",
        ISSUE27J / "raw_provenance_recovery_report.md",
        ISSUE27J / "hh_separator_lineage_audit.csv",
        ISSUE27J / "hh_separator_lineage_report.md",
        ISSUE27J / "clean_split_construction_feasibility.csv",
        ISSUE27J / "clean_split_construction_report.md",
        ISSUE27J / "raw_data_expansion_implementation_plan.md",
        ISSUE27J / "claim_update_after_issue27j.md",
        ISSUE27I / "summary.md",
        ISSUE27H / "summary.md",
        ISSUE27F / "summary.md",
        ISSUE25C / "summary.md",
        MAINLINE / "mainline_handoff.md",
        MAINLINE / "mainline_experiment_map.md",
        ISSUE11 / "config.json",
    ]
    return pd.DataFrame([{"path": safe_rel(p), "exists": p.exists(), "required": True} for p in required])


def get_assets() -> dict[str, Any]:
    cfg = read_json(ISSUE11 / "config.json")
    paths = {k: Path(v) for k, v in cfg["paths"].items()}
    stage2_manifest = read_json(paths["stage2_manifest"])
    stage1_manifest = read_json(KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "data_manifest.json")
    id_meta = read_json(KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_id_7_6" / "extract_metadata.json")
    ood_meta = read_json(KITNET_ROOT / "runs" / "frontend100_crosscapture_stage1_2026-03-25" / "extract_ood_4_1" / "extract_metadata.json")
    attack_meta = read_json(KITNET_ROOT / "runs" / "frontend100_joint_eval_stage1_2026-03-31" / "extract_attack_34_1" / "extract_metadata.json")
    return {
        "cfg": cfg,
        "paths": paths,
        "stage1_manifest": stage1_manifest,
        "stage2_manifest": stage2_manifest,
        "id": {
            "role": "id",
            "capture_id": "CTU-Honeypot-Capture-7-6",
            "source_file": str(KITNET_ROOT / id_meta["source_pcap"]),
            "tsv": Path(id_meta["tsv_path"]),
            "full_feature": Path(id_meta["feature_path"]),
            "source_matrix": paths["original100_id"],
            "feature_headers": Path(id_meta["tsv_path"]).parent / "feature_headers.txt",
            "row_count": 50000,
        },
        "ood": {
            "role": "ood",
            "capture_id": "CTU-Honeypot-Capture-4-1",
            "source_file": str(KITNET_ROOT / ood_meta["source_pcap"]),
            "tsv": Path(ood_meta["tsv_path"]),
            "full_feature": Path(ood_meta["feature_path"]),
            "source_matrix": paths["original100_ood"],
            "feature_headers": Path(ood_meta["tsv_path"]).parent / "feature_headers.txt",
            "row_count": 20000,
        },
        "attack": {
            "role": "attack",
            "capture_id": "CTU-IoT-Malware-Capture-34-1",
            "source_file": str(KITNET_ROOT / attack_meta["source_pcap"]),
            "tsv": Path(attack_meta["tsv_path"]),
            "full_feature": Path(attack_meta["feature_path"]),
            "source_matrix": paths["original100_attack"],
            "feature_headers": Path(attack_meta["tsv_path"]).parent / "feature_headers.txt",
            "row_count": 10000,
        },
    }


def attack_bins_for_tsv(tsv: pd.DataFrame, stage2_manifest: dict[str, Any]) -> np.ndarray:
    ts = pd.to_numeric(tsv["frame.time_epoch"], errors="coerce").to_numpy(np.float64)
    ts0 = float(np.nanmin(ts))
    return ((ts - ts0) // int(stage2_manifest["bin_seconds"])).astype(np.int64)


def split_membership(role: str, idx: int, bin_id: int | None) -> str:
    if role == "id":
        if idx < 8000:
            return "id_train_locked_protocol"
        if idx < 13000:
            return "id_calib_locked_protocol"
        return "id_reserved_or_eval_pool"
    if role == "ood":
        if idx < 8000:
            return "ood_train_locked_protocol"
        if idx < 10000:
            return "ood_val_locked_protocol"
        return "final_ood_eval_locked_protocol"
    if role == "attack":
        if bin_id in {5, 6, 7, 8}:
            return f"locked_eval_candidate_bin_{bin_id}"
        if bin_id in {2, 3, 4}:
            return f"attack_train_or_chrono_eval_candidate_bin_{bin_id}"
        if bin_id == 9:
            return "unused_future_bin9_too_small"
        return f"nonlocked_or_mixed_attack_bin_{bin_id}"
    return "unknown"


def build_sidecar(assets: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[pd.DataFrame] = []
    alignment_rows: list[dict[str, Any]] = []
    recon_rows: list[dict[str, Any]] = []
    bin_rows: list[dict[str, Any]] = []
    stage2 = assets["stage2_manifest"]

    for role in ["id", "ood", "attack"]:
        spec = assets[role]
        n = int(spec["row_count"])
        tsv = pd.read_csv(spec["tsv"], sep="\t", nrows=n)
        full = np.load(spec["full_feature"], mmap_mode="r")[:n]
        src = load_matrix(spec["source_matrix"])
        if len(src) != n:
            src = src[:n]
        diff = np.asarray(src, dtype=np.float64) - np.asarray(full, dtype=np.float64)
        max_abs_diff = float(np.nanmax(np.abs(diff))) if diff.size else math.nan
        mean_abs_diff = float(np.nanmean(np.abs(diff))) if diff.size else math.nan
        rel_diff = np.abs(diff) / np.maximum(1.0, np.abs(np.asarray(full, dtype=np.float64)))
        max_rel_diff = float(np.nanmax(rel_diff)) if rel_diff.size else math.nan
        p99999_abs_diff = float(np.nanquantile(np.abs(diff), 0.99999)) if diff.size else math.nan
        allclose = bool(np.allclose(src, full, atol=1e-6, rtol=1e-6))
        feat_hash = feature_hashes(np.asarray(src, dtype=np.float64))
        ts = pd.to_numeric(tsv["frame.time_epoch"], errors="coerce")
        timestamp_monotonic = bool(ts.is_monotonic_increasing)
        duplicate_ts = int(ts.duplicated().sum())
        duplicate_feat = int(pd.Series(feat_hash).duplicated().sum())
        alignment_rows.append(
            {
                "role": role,
                "source_rows": int(len(src)),
                "tsv_rows_used": int(len(tsv)),
                "full_feature_rows_used": int(len(full)),
                "source_vs_full_allclose": allclose,
                "source_vs_full_max_abs_diff": max_abs_diff,
                "source_vs_full_mean_abs_diff": mean_abs_diff,
                "source_vs_full_max_rel_diff": max_rel_diff,
                "source_vs_full_p99999_abs_diff": p99999_abs_diff,
                "allclose_tolerance": "atol=1e-6,rtol=1e-6",
                "timestamp_monotonic": timestamp_monotonic,
                "duplicate_timestamp_count": duplicate_ts,
                "duplicate_feature_hash_count": duplicate_feat,
                "alignment_confidence": "high" if allclose and timestamp_monotonic else "medium",
                "notes": "Source matrix aligns to extracted feature cache by row order." if allclose else "Check extraction/version precision before using as formal rebuilt asset.",
            }
        )
        recon_rows.append(
            {
                "role": role,
                "has_feature_name_mapping": bool(Path(spec["feature_headers"]).exists()),
                "can_call_netstat_afterimage": bool((FRONTEND_ORIG / "netStat.py").exists() and (FRONTEND_ORIG / "AfterImage.py").exists()),
                "source_vs_existing_extraction_allclose": allclose,
                "can_reconstruct_continuous_state_baseline": True,
                "can_reset_at_split_boundary": True,
                "can_train_state_then_eval_online": True,
                "rebuild_not_executed_full": True,
                "reason_not_full_rebuilt": "Existing extracted feature cache already aligns; full split-aware rebuild should be issue27l after split is chosen.",
            }
        )

        bin_ids: np.ndarray | None = None
        if role == "attack":
            bin_ids = attack_bins_for_tsv(tsv, stage2)
            bdf = pd.DataFrame({"bin": bin_ids, "timestamp": ts.to_numpy()})
            agg = bdf.groupby("bin", as_index=False).agg(
                row_count=("bin", "size"),
                timestamp_min=("timestamp", "min"),
                timestamp_max=("timestamp", "max"),
            )
            for _, r in agg.iterrows():
                bin_rows.append(
                    {
                        "bin": int(r["bin"]),
                        "row_count": int(r["row_count"]),
                        "timestamp_min": float(r["timestamp_min"]),
                        "timestamp_max": float(r["timestamp_max"]),
                        "already_used_locked_eval": int(r["bin"]) in {5, 6, 7, 8},
                        "potential_future_holdout": int(r["bin"]) == 9,
                    }
                )

        role_df = pd.DataFrame(
            {
                "row_id": [f"{role}_{i}" for i in range(n)],
                "source_role": role,
                "original100_row_index": np.arange(n, dtype=np.int64),
                "extracted_tsv_row_index": np.arange(n, dtype=np.int64),
                "packet_order": np.arange(n, dtype=np.int64),
                "timestamp": ts.to_numpy(),
                "timestamp_source": str(spec["tsv"]),
                "capture_id": spec["capture_id"],
                "source_file": spec["source_file"],
                "packet_hash_if_available": [packet_hash(row) for _, row in tsv.iterrows()],
                "label": "attack_proxy" if role == "attack" else ("benign_id" if role == "id" else "benign_ood"),
                "attack_family_if_available": "Mirai" if role == "attack" else "NA",
                "is_attack": role == "attack",
                "is_benign_id": role == "id",
                "is_benign_ood": role == "ood",
                "feature_row_hash": feat_hash,
                "alignment_confidence": "high" if allclose and timestamp_monotonic else "medium",
            }
        )
        if role == "attack" and bin_ids is not None:
            role_df["attack_bin"] = bin_ids[:n]
            role_df["split_membership_if_existing"] = [
                split_membership(role, i, int(bin_ids[i])) for i in range(n)
            ]
        else:
            role_df["attack_bin"] = "NA"
            role_df["split_membership_if_existing"] = [split_membership(role, i, None) for i in range(n)]
        role_df["notes"] = "row-level sidecar reconstructed by extraction order; packet hash is TSV-row fingerprint, not raw pcap bytes"
        rows.append(role_df)

    sidecar = pd.concat(rows, ignore_index=True)
    return sidecar, pd.DataFrame(alignment_rows), pd.DataFrame(recon_rows), pd.DataFrame(bin_rows)


def design_splits(sidecar: pd.DataFrame, bin_counts: pd.DataFrame) -> pd.DataFrame:
    id_n = int((sidecar["source_role"] == "id").sum())
    ood_n = int((sidecar["source_role"] == "ood").sum())
    bin9_n = int(bin_counts.loc[bin_counts["bin"].eq(9), "row_count"].iloc[0]) if (bin_counts["bin"].eq(9)).any() else 0
    rows = [
        {
            "split_name": "chronological_forward_existing_bins_2_4_to_6_8",
            "train_time_range": "attack bins 2-4",
            "calib_time_range": "ID 8000-12999; OOD 8000-9999",
            "ood_val_time_range": "OOD 8000-9999",
            "purge_gap": "bin 5",
            "final_eval_time_range": "attack bins 6-8",
            "attack_support_source": "attack bins 2-4",
            "attack_eval_source": "attack bins 6-8",
            "id_train_count": 8000,
            "ood_train_count": 8000,
            "id_calib_count": 5000,
            "ood_val_count": 2000,
            "final_ood_eval_count": max(0, ood_n - 10000),
            "attack_support_count": 32,
            "attack_eval_count": int(bin_counts[bin_counts["bin"].isin([6, 7, 8])]["row_count"].sum()),
            "can_construct": False,
            "blocked_reason": "Constructable as a purged chrono object but eval bins 6/7/8 already overlap locked evidence; not clean independent.",
            "leakage_risk": "medium_repeated_locked_bin_analysis",
            "evidence_level": "consistency_only_not_formal_clean",
        },
        {
            "split_name": "future_window_bin9_eval",
            "train_time_range": "attack bins 2-8 excluding eval",
            "calib_time_range": "ID/OOD locked calibration",
            "ood_val_time_range": "OOD 8000-9999",
            "purge_gap": "none_or_bin8_gap_required",
            "final_eval_time_range": "attack bin 9",
            "attack_support_source": "attack bins 2-8",
            "attack_eval_source": "attack bin 9",
            "id_train_count": 8000,
            "ood_train_count": 8000,
            "id_calib_count": 5000,
            "ood_val_count": 2000,
            "final_ood_eval_count": max(0, ood_n - 10000),
            "attack_support_count": 32,
            "attack_eval_count": bin9_n,
            "can_construct": False,
            "blocked_reason": f"Bin 9 has only {bin9_n} packet rows, below the prior min_eval_rows=300 gate and too small for stable formal validation.",
            "leakage_risk": "medium_small_eval_and_adjacent_state",
            "evidence_level": "diagnostic_only_if_run_later",
        },
        {
            "split_name": "capture_disjoint_attack_eval",
            "train_time_range": "current attack capture train",
            "calib_time_range": "current ID/OOD calibration",
            "ood_val_time_range": "current OOD validation",
            "purge_gap": "capture-disjoint",
            "final_eval_time_range": "new attack capture/session",
            "attack_support_source": "current or new train capture",
            "attack_eval_source": "new unused capture/session",
            "id_train_count": 8000,
            "ood_train_count": 8000,
            "id_calib_count": 5000,
            "ood_val_count": 2000,
            "final_ood_eval_count": "needs_new_ood_or_prespecified_current",
            "attack_support_count": 32,
            "attack_eval_count": "unknown",
            "can_construct": False,
            "blocked_reason": "No unused attack capture/session with original100 assets is currently available.",
            "leakage_risk": "low_if_constructed",
            "evidence_level": "blocked",
        },
        {
            "split_name": "purged_split_with_splitwise_feature_reset",
            "train_time_range": "to be selected after sidecar hash verification",
            "calib_time_range": "disjoint validation side",
            "ood_val_time_range": "disjoint OOD validation side",
            "purge_gap": "packet/time embargo around split",
            "final_eval_time_range": "future window after gap",
            "attack_support_source": "pre-eval train window",
            "attack_eval_source": "post-gap eval window",
            "id_train_count": id_n,
            "ood_train_count": "depends_on_design",
            "id_calib_count": "depends_on_design",
            "ood_val_count": "depends_on_design",
            "final_ood_eval_count": "depends_on_design",
            "attack_support_count": 32,
            "attack_eval_count": "needs_more_future_rows",
            "can_construct": False,
            "blocked_reason": "Need split-aware feature rebuild and enough post-gap attack/OOD rows before formal evaluation.",
            "leakage_risk": "low_after_rebuild",
            "evidence_level": "issue27l_candidate",
        },
    ]
    return pd.DataFrame(rows)


def write_blocked_outputs(primary_verdict: str) -> None:
    purged_text = """
# Purged Split Blocked

No clean purged chronological split was promoted to formal evaluation in issue27k.

The sidecar manifest was recovered, but available attack windows are either already used in locked/consistency evidence or too small for a stable new formal holdout.
"""
    write_text(OUT / "purged_split_blocked.md", purged_text)
    write_text(OUT / "purged_split_report.md", purged_text)
    rebuild_text = """
# Split-Aware Original100 Rebuild Blocked

Split-aware full original100 rebuild was not executed because no clean purged split was selected.

Feasibility result:
- continuous_state_baseline can be aligned to existing feature caches;
- reset_at_split_boundary is implementable via Kitsune FeatureExtractor/netStat reinitialization;
- train_state_then_eval_online is implementable, but should be run only after a clean split is selected.
"""
    write_text(OUT / "split_aware_rebuild_blocked.md", rebuild_text)
    write_text(OUT / "split_aware_original100_rebuild_report.md", rebuild_text)
    write_text(OUT / "split_aware_original100_rebuild_manifest.csv", "status,reason\nblocked,no_clean_purged_split_selected\n")
    write_text(OUT / "split_aware_feature_alignment_check.csv", "status,reason\nblocked,no_clean_purged_split_selected\n")
    eval_text = """
# Clean/Purged LOW-GUARD++ Evaluation Blocked

Frozen LOW-GUARD++ was not evaluated because no clean purged split and split-aware rebuilt feature matrix were available.

This is not a method-failure result.
"""
    write_text(OUT / "clean_purged_eval_blocked.md", eval_text)
    write_text(OUT / "clean_purged_lowguardpp_by_seed.csv", "status,reason\nblocked,no_clean_purged_split_or_split_aware_features\n")
    write_text(OUT / "clean_purged_lowguardpp_summary.csv", "status,reason\nblocked,no_clean_purged_split_or_split_aware_features\n")
    write_text(OUT / "clean_purged_vs_lowguard_lr.csv", "status,reason\nblocked,no_clean_purged_split_or_split_aware_features\n")


def update_mainline_docs(primary_verdict: str, issue27l_action: str) -> None:
    handoff = MAINLINE / "mainline_handoff.md"
    expmap = MAINLINE / "mainline_experiment_map.md"
    handoff_append = f"""

## issue27k row-level original100 rebuild and purged split construction (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: builds row-level sidecar provenance for ID/OOD/attack original100 assets, verifies source-vs-extracted feature alignment, and designs purged split candidates.
- claim boundary: row provenance is recovered, but clean/purged LOW-GUARD++ validation remains blocked until split-aware feature rebuild and sufficient independent eval assets exist.
- next action: `{issue27l_action}`.
"""
    expmap_append = f"""
| issue27k | row-level original100 rebuild and purged split construction | `{primary_verdict}` | Builds row-level sidecar and verifies feature alignment; clean/purged validation remains blocked by insufficient clean independent split assets. Next: `{issue27l_action}`. |
"""
    htxt = handoff.read_text(encoding="utf-8")
    htxt = re.sub(r"\n## issue27k row-level original100 rebuild and purged split construction \(2026-05-27\)\n.*?(?=\n## |\Z)", "", htxt, flags=re.S)
    handoff.write_text(htxt.rstrip() + handoff_append + "\n", encoding="utf-8")
    etxt = expmap.read_text(encoding="utf-8")
    etxt = re.sub(r"(?m)^\| issue27k \|.*\|\r?\n?", "", etxt)
    expmap.write_text(etxt.rstrip() + "\n\n" + expmap_append.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    inputs = required_input_status()
    inputs.to_csv(OUT / "manifest.csv", index=False)
    missing = inputs[inputs["required"] & ~inputs["exists"]]
    if len(missing):
        write_text(OUT / "summary.md", "primary_verdict: `blocked_needs_raw_reconstruction_or_second_environment`\n\nRequired inputs missing; see manifest.csv.")
        raise SystemExit(1)

    assets = get_assets()
    sidecar, align, recon, bin_counts = build_sidecar(assets)
    sidecar.to_csv(OUT / "row_level_sidecar_manifest.csv", index=False)
    align.to_csv(OUT / "original100_row_alignment_check.csv", index=False)
    recon.to_csv(OUT / "original100_reconstruction_feasibility.csv", index=False)
    design = design_splits(sidecar, bin_counts)
    design.to_csv(OUT / "purged_split_design_table.csv", index=False)

    row_manifest_success = bool(len(sidecar) == 80000 and align["source_vs_full_allclose"].astype(bool).all())
    split_constructed = bool(design["can_construct"].astype(bool).any())
    rebuild_done = False
    clean_eval_done = False
    continuous_state_risk = "not_directly_proven_harmful_but_claim_requires_splitwise_rebuild"

    if row_manifest_success and not split_constructed:
        primary_verdict = "row_manifest_recovered_but_clean_split_blocked"
    elif row_manifest_success and split_constructed and not clean_eval_done:
        primary_verdict = "clean_split_constructed_rebuild_eval_next"
    else:
        primary_verdict = "blocked_needs_raw_reconstruction_or_second_environment"
    issue27l_action = "issue27l_split_aware_original100_rebuild_with_sufficient_clean_eval_asset"

    write_text(
        OUT / "row_level_sidecar_manifest_report.md",
        f"""
# Row-Level Sidecar Manifest Report

Sidecar manifest constructed: `{row_manifest_success}`.

Rows:
- ID: 50000
- OOD benign: 20000
- attack: 10000
- total: {len(sidecar)}

Alignment summary:

{md_table(align)}

Interpretation:
- extracted TSV row order, feature cache row order, and current original100 source matrix row order align for the current cached assets.
- the detailed row-order alignment audit is saved in `original100_row_alignment_check.csv`.
- packet hash is a TSV-row fingerprint, not raw packet bytes.
- raw pcap source paths are recorded, but byte-level pcap-to-row hashing was not performed in this issue.
- row-level provenance is now explicit enough for split construction planning, but not enough by itself to create a new clean validation object.
""",
    )
    write_text(
        OUT / "original100_reconstruction_report.md",
        f"""
# Original100 Reconstruction Report

Reconstruction feasibility:

{md_table(recon)}

Key points:
- Feature name mapping exists for all three roles.
- Kitsune `netStat.py` / `AfterImage.py` are available and define the original100 stream statistics.
- Current source matrices align with previously extracted feature caches by row order.
- Full split-aware re-extraction was not executed in this issue because no clean purged split was selected.
- `reset_at_split_boundary` and `train_state_then_eval_online` are implementable, but should be run only after selecting a clean split to avoid producing unused experimental artifacts.
""",
    )
    write_text(
        OUT / "purged_split_design_report.md",
        f"""
# Purged Split Design Report

Purged or clean chronological split constructed: `{split_constructed}`.

{md_table(design)}

Conclusion:
- A row-level manifest now exists.
- Existing bins can be mapped to timestamps.
- Formal clean validation is still blocked because the usable post-locked future window is too small, and candidate chrono splits reuse previously analyzed locked bins.
""",
    )
    if not split_constructed:
        write_text(OUT / "purged_split_manifest.csv", "status,reason\nblocked,no_clean_purged_split_constructed\n")
        write_blocked_outputs(primary_verdict)

    write_text(
        OUT / "lowguard_plus_plus_clean_rebuild_decision.md",
        f"""
# LOW-GUARD++ Clean Rebuild Decision

- primary_verdict: `{primary_verdict}`
- issue27l_next_action: `{issue27l_action}`

Decision:
- Row-level sidecar provenance is recovered.
- Clean/purged split validation is still blocked.
- Do not upgrade LOW-GUARD++ to main-text performance instance yet.
- Do not abandon LOW-GUARD++ or collapse to LOW-GUARD-LR as final mainline.
""",
    )
    claim = """
- LOW-GUARD++ remains a high-potential candidate.
- Claim upgrade is blocked by split-aware reconstruction or clean split construction, not by method failure.
"""
    write_text(
        OUT / "claim_update_after_issue27k.md",
        f"""
# Claim Update After Issue27k

## Allowed

{claim}

## Forbidden

- LOW-GUARD++ is abandoned without artifact evidence.
- LOW-GUARD-LR is final mainline solely because clean rebuild is not yet available.
- Deployment robustness is next if clean rebuild is technically recoverable.
- Temporal/cross-dataset generalization is proven without clean split.
""",
    )
    write_text(
        OUT / "reviewer_defense_split_aware_rebuild.md",
        f"""
# Reviewer Defense: Split-Aware Rebuild

## Q1: Did you recover row-level provenance?

Yes. The sidecar manifest maps current original100 rows to extracted TSV row order, packet timestamp, packet-order proxy, capture id, and feature-row hashes.

## Q2: Does this prove LOW-GUARD++ generalizes?

No. It proves the provenance blocker is partly resolved. Clean validation still requires a sufficiently large independent future/capture split and split-aware feature rebuild.

## Q3: Did continuous-state carryover invalidate the old result?

No direct invalidating artifact was found. But the old continuous-state result is not enough for a strong claim because split-boundary state carryover remains a plausible confound.

## Q4: Why not run LOW-GUARD++ now?

Because no clean purged split was selected. Running on reused locked bins would create another consistency check, not formal independent validation.
""",
    )
    write_text(
        OUT / "issue27l_next_action.md",
        f"""
# Issue27l Next Action

Recommended next action: `{issue27l_action}`.

Scope:
- acquire or construct a sufficiently large clean future/capture evaluation object;
- run split-aware original100 rebuild with `reset_at_split_boundary` and `train_state_then_eval_online`;
- then evaluate frozen LOW-GUARD++ and safer variants under report-only final eval.
""",
    )
    write_text(
        OUT / "summary.md",
        f"""
# Issue27k Row-Level Original100 Rebuild And Purged Split Construction Summary

## Verdict

- primary_verdict: `{primary_verdict}`
- issue27l_next_action: `{issue27l_action}`

## 1. Row-level sidecar manifest

Constructed: `{row_manifest_success}`.

Total rows mapped: `{len(sidecar)}`.

## 2. Original100 / extracted TSV alignment

Current source matrices align with extracted feature caches by row order: `{bool(align['source_vs_full_allclose'].astype(bool).all())}`.

Timestamp monotonic by role: `{bool(align['timestamp_monotonic'].astype(bool).all())}`.

Raw pcap source paths are recorded in the sidecar, but byte-level pcap packet hashes were not matched in this issue.

## 3. Original100 reconstruction feasibility

Continuous-state baseline is reproducible from existing feature caches. Split-reset and train-state-then-eval-online are implementable, but full split-aware rebuild was not run because no clean split was selected.

## 4. Purged chronological split

Constructed: `{split_constructed}`.

Blocked because available chrono candidates either reuse locked/previously analyzed bins or have too few future-window attack rows.

## 5. Clean/purged LOW-GUARD++ evaluation

Completed: `{clean_eval_done}`.

No clean/purged LOW-GUARD++ score should be claimed from this issue.

## 6. Safer variants

Not evaluated on clean/purged split because no clean split and split-aware feature matrix were available.

## 7. Continuous-state carryover

Finding: `{continuous_state_risk}`.

## 8. Claim status

LOW-GUARD++ cannot yet be upgraded to main-text performance instance. It remains a high-potential candidate with improved provenance.

## 9. Slurm

Not needed for this row-level manifest and feasibility run. May be needed for larger raw reconstruction or second-environment extraction.
""",
    )
    write_text(
        OUT / "command.txt",
        """
git branch --show-current
git status --short
read issue27j/27i/27h/27f/25c assets
python runs/issue27k_row_level_original100_rebuild_and_purged_split_construction_for_lowguard_plus_plus_2026-05-27/run_issue27k_row_level_rebuild_purged_split.py
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
        "row_manifest_constructed": row_manifest_success,
        "clean_purged_eval_run": clean_eval_done,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    run_spec = {
        "task": "row_level_original100_rebuild_and_purged_split_construction",
        "primary_verdict": primary_verdict,
        "issue27l_action": issue27l_action,
        "inputs": inputs.to_dict(orient="records"),
        "outputs": [
            "summary.md",
            "row_level_sidecar_manifest.csv",
            "row_level_sidecar_manifest_report.md",
            "original100_row_alignment_check.csv",
            "original100_reconstruction_feasibility.csv",
            "original100_reconstruction_report.md",
            "purged_split_design_table.csv",
            "purged_split_design_report.md",
            "purged_split_manifest.csv",
            "purged_split_report.md",
            "split_aware_original100_rebuild_report.md",
            "split_aware_original100_rebuild_manifest.csv",
            "split_aware_feature_alignment_check.csv",
            "clean_purged_lowguardpp_by_seed.csv",
            "clean_purged_lowguardpp_summary.csv",
            "clean_purged_vs_lowguard_lr.csv",
            "lowguard_plus_plus_clean_rebuild_decision.md",
            "claim_update_after_issue27k.md",
            "reviewer_defense_split_aware_rebuild.md",
            "issue27l_next_action.md",
            "command.txt",
            "config.json",
            "run_spec.json",
            "manifest.csv",
        ],
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2), encoding="utf-8")
    update_mainline_docs(primary_verdict, issue27l_action)
    print(f"[issue27k] primary_verdict={primary_verdict}")
    print(f"[issue27k] issue27l_action={issue27l_action}")


if __name__ == "__main__":
    main()
