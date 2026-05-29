from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from itertools import islice
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None


REPO = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
KITNET = Path(r"D:\study\paper\anomaly_detection\paper04\KitNET-py-master\KitNET-py-master")
OUT = REPO / "runs" / "issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27"

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
ORIG100_HEADERS = (
    KITNET
    / "runs"
    / "frontend100_crosscapture_stage1_2026-03-25"
    / "extract_id_7_6"
    / "feature_headers.txt"
)
MAINLINE_DOCS = REPO / "runs" / "mainline_docs"


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "NA") for k in fieldnames})


def first_row(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        return next(csv.reader(f), [])


def line_count(path: Path) -> int:
    count = 0
    with path.open("rb") as f:
        for _ in f:
            count += 1
    return count


def csv_labels(path: Path) -> np.ndarray:
    vals: list[int] = []
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            s = line.strip()
            if s:
                vals.append(int(float(s.split(",")[0])))
    return np.asarray(vals, dtype=np.int8)


def index_like_audit(path: Path, labels: np.ndarray) -> dict[str, Any]:
    n = len(labels)
    sample_values: list[float] = []
    last_value = None
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            if i < 5000:
                sample_values.append(float(row[0]))
            last_value = float(row[0])
    strict_prefix = all(abs(v - i) < 1e-9 for i, v in enumerate(sample_values))
    corr = float(np.corrcoef(np.arange(n, dtype=np.float64), labels.astype(np.float64))[0, 1])
    return {
        "row_count": n,
        "first_value": sample_values[0] if sample_values else "NA",
        "last_value": last_value,
        "strict_0_based_prefix_first_5000": strict_prefix,
        "last_matches_row_count_minus_one": abs(float(last_value) - (n - 1)) < 1e-9 if last_value is not None else False,
        "pearson_corr_col0_with_label": corr,
        "label_transition_count": int(np.sum(labels[1:] != labels[:-1])),
        "first_attack_row": int(np.argmax(labels == 1)) if np.any(labels == 1) else -1,
        "decision": "drop_col0_required",
        "reason": "col0 is a row index; high label correlation is a row-order artifact, not semantic traffic behavior",
    }


def scan_clean115_numeric(path: Path, label_count: int) -> dict[str, Any]:
    if pd is None:
        row = first_row(path)
        return {
            "scan_mode": "fallback_headerless_first_row_only",
            "rows": label_count,
            "raw_dim": len(row),
            "clean_dim": max(0, len(row) - 1),
            "nan_count": "not_scanned",
            "inf_count": "not_scanned",
            "constant_column_count": "not_scanned",
            "all_numeric": "unknown",
        }
    rows = 0
    clean_dim = None
    nan_count = 0
    inf_count = 0
    col_min = None
    col_max = None
    col_sum = None
    col_sumsq = None
    first_hash = None
    for chunk in pd.read_csv(path, header=None, chunksize=50000):
        arr = chunk.iloc[:, 1:].to_numpy(dtype=np.float64, copy=True)
        if clean_dim is None:
            clean_dim = arr.shape[1]
            col_min = np.full(clean_dim, np.inf)
            col_max = np.full(clean_dim, -np.inf)
            col_sum = np.zeros(clean_dim, dtype=np.float64)
            col_sumsq = np.zeros(clean_dim, dtype=np.float64)
            first_hash = hashlib.sha256(arr[0].tobytes()).hexdigest()
        rows += arr.shape[0]
        finite = np.isfinite(arr)
        nan_count += int(np.isnan(arr).sum())
        inf_count += int(np.isinf(arr).sum())
        safe = np.where(finite, arr, np.nan)
        col_min = np.fmin(col_min, np.nanmin(safe, axis=0))
        col_max = np.fmax(col_max, np.nanmax(safe, axis=0))
        col_sum += np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0).sum(axis=0)
        col_sumsq += np.nan_to_num(arr * arr, nan=0.0, posinf=0.0, neginf=0.0).sum(axis=0)
    const_count = int(np.sum(col_min == col_max)) if col_min is not None else "NA"
    return {
        "scan_mode": "pandas_chunk_full_scan",
        "rows": rows,
        "label_count": label_count,
        "raw_dim": len(first_row(path)),
        "clean_dim": int(clean_dim or 0),
        "nan_count": nan_count,
        "inf_count": inf_count,
        "constant_column_count": const_count,
        "all_numeric": nan_count == 0 and inf_count == 0,
        "first_clean_row_hash": first_hash,
        "materialized_clean115_cache": False,
        "materialization_reason": "not written to avoid duplicating a >1GB matrix before mapping gate passes",
    }


def read_original100_headers() -> list[str]:
    return [line.strip() for line in ORIG100_HEADERS.read_text(encoding="utf-8").splitlines() if line.strip()]


def expected_hstat_headers() -> list[str]:
    lambdas = ["5", "3", "1", "0.1", "0.01"]
    headers = []
    for lam in lambdas:
        headers += [f"H_{lam}_weight", f"H_{lam}_mean", f"H_{lam}_std"]
    return headers


def expected_restored115_headers() -> list[str]:
    orig = read_original100_headers()
    # Current original100 order is MI(15) + HH(35) + HH_jit(15) + HpHp(35).
    return orig[:15] + expected_hstat_headers() + orig[15:]


def sample_lines(path: Path, wanted: set[int]) -> dict[int, str]:
    out: dict[int, str] = {}
    max_wanted = max(wanted)
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for i, line in enumerate(f):
            if i in wanted:
                out[i] = line.rstrip("\n\r")
            if i >= max_wanted:
                break
    return out


def sample_numeric_rows(path: Path, wanted: set[int]) -> dict[int, np.ndarray]:
    rows = {}
    for idx, line in sample_lines(path, wanted).items():
        rows[idx] = np.fromstring(line, sep=",")
    return rows


def prior_use_audit(labels: np.ndarray) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    my_labels = np.load(MY_GOLD_LABELS).astype(np.int8)
    prefix_label_match = bool(np.array_equal(labels[: len(my_labels)], my_labels))
    sample_idx = {0, 1, 1000, 121620, 121621, 199999}
    full_samples = sample_numeric_rows(FULL_MIRAI, sample_idx)
    gold_samples = sample_numeric_rows(MY_GOLD, sample_idx)
    feature_sample_match = all(
        i in full_samples
        and i in gold_samples
        and full_samples[i].shape == gold_samples[i].shape
        and np.allclose(full_samples[i], gold_samples[i], rtol=1e-10, atol=1e-12)
        for i in sample_idx
    )
    prefix = len(my_labels)
    remaining = labels[prefix:]
    rem_counts = Counter(remaining.tolist())
    full_counts = Counter(labels.tolist())
    rows = [
        {
            "prior_asset": "my_gold_mirai_200k",
            "overlap_with_full_mirai": "prefix_0_199999_sample_and_label_confirmed" if prefix_label_match and feature_sample_match else "likely_but_not_fully_confirmed",
            "label_prefix_match": prefix_label_match,
            "feature_sample_match": feature_sample_match,
            "rows_to_exclude_for_strict_prior_use": prefix,
            "benign_remaining_after_exclusion": int(rem_counts.get(0, 0)),
            "attack_remaining_after_exclusion": int(rem_counts.get(1, 0)),
            "impact": "strict exclusion removes all benign rows" if rem_counts.get(0, 0) == 0 else "benign remains",
            "verdict": "overlap_known_and_isolated_but_clean_split_loses_benign",
        },
        {
            "prior_asset": "official_mirai_100k_with_timestamp",
            "overlap_with_full_mirai": "insufficient_metadata_to_determine",
            "label_prefix_match": False,
            "feature_sample_match": "not_checked_schema_differs_or_order_unknown",
            "rows_to_exclude_for_strict_prior_use": "unknown",
            "benign_remaining_after_exclusion": "unknown",
            "attack_remaining_after_exclusion": "unknown",
            "impact": "timestamped asset may be useful but row mapping to full asset is unresolved",
            "verdict": "insufficient_metadata_to_determine",
        },
        {
            "prior_asset": "issue27f_to_issue27m_lowguardpp_chain",
            "overlap_with_full_mirai": "no_direct_use_detected_for_config_support_threshold_final_eval",
            "label_prefix_match": "NA",
            "feature_sample_match": "NA",
            "rows_to_exclude_for_strict_prior_use": 0,
            "benign_remaining_after_exclusion": int(full_counts.get(0, 0)),
            "attack_remaining_after_exclusion": int(full_counts.get(1, 0)),
            "impact": "full Mirai not used to tune current original100 LOW-GUARD++",
            "verdict": "no_prior_use_detected_for_lowguardpp_selection",
        },
    ]
    summary = {
        "prefix_label_match": prefix_label_match,
        "feature_sample_match": feature_sample_match,
        "benign_remaining_after_excluding_my_gold_prefix": int(rem_counts.get(0, 0)),
        "attack_remaining_after_excluding_my_gold_prefix": int(rem_counts.get(1, 0)),
    }
    return rows, summary


def split_proposal(labels: np.ndarray, prior: dict[str, Any]) -> list[dict[str, Any]]:
    counts = Counter(labels.tolist())
    rows = [
        {
            "split_name": "clean115_full_mirai_relaxed_development_split",
            "evidence_level": "consistency_only_due_to_historical_my_gold_benign_overlap",
            "id_train_count": 60000,
            "ood_train_count": 20000,
            "id_calib_count": 20000,
            "ood_val_count": 10000,
            "final_ood_eval_count": 11621,
            "attack_support_pool_count": 60000,
            "attack_support_count": 32,
            "attack_eval_count": 582516,
            "support_eval_disjoint": True,
            "final_eval_report_only": True,
            "timestamp_available": False,
            "capture_session_available": False,
            "prior_use_rows_excluded": False,
            "blocked_for_clean_claim": True,
            "blocked_reason": "uses benign rows from historical my_gold prefix; suitable only as interface/development split after mapping",
        },
        {
            "split_name": "clean115_full_mirai_strict_prior_use_excluded_split",
            "evidence_level": "blocked",
            "id_train_count": 0,
            "ood_train_count": 0,
            "id_calib_count": 0,
            "ood_val_count": 0,
            "final_ood_eval_count": 0,
            "attack_support_pool_count": 60000 if prior["attack_remaining_after_excluding_my_gold_prefix"] >= 60000 else prior["attack_remaining_after_excluding_my_gold_prefix"],
            "attack_support_count": 32 if prior["attack_remaining_after_excluding_my_gold_prefix"] >= 32 else 0,
            "attack_eval_count": max(0, prior["attack_remaining_after_excluding_my_gold_prefix"] - 60000),
            "support_eval_disjoint": True,
            "final_eval_report_only": True,
            "timestamp_available": False,
            "capture_session_available": False,
            "prior_use_rows_excluded": True,
            "blocked_for_clean_claim": True,
            "blocked_reason": "after excluding historical my_gold prefix, benign_remaining=0; cannot build ID/OOD/final benign eval",
        },
        {
            "split_name": "official_mirai_100k_timestamp_mapping_candidate",
            "evidence_level": "blocked_pending_feature_mapping_and_prior_overlap",
            "id_train_count": 40000,
            "ood_train_count": 10000,
            "id_calib_count": 10000,
            "ood_val_count": 6000,
            "final_ood_eval_count": 5659,
            "attack_support_pool_count": 8000,
            "attack_support_count": 32,
            "attack_eval_count": 20341,
            "support_eval_disjoint": True,
            "final_eval_report_only": True,
            "timestamp_available": True,
            "capture_session_available": False,
            "prior_use_rows_excluded": "unknown",
            "blocked_for_clean_claim": True,
            "blocked_reason": "feature mapping and row overlap with full/my_gold unresolved",
        },
    ]
    return rows


def update_docs(primary_verdict: str) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    expmap = MAINLINE_DOCS / "mainline_experiment_map.md"
    handoff_entry = f"""

## issue27n full Mirai restored115 mapping gate (2026-05-27)

- primary_verdict: `{primary_verdict}`
- scope: audits dirty116-to-clean115 construction, restored115 feature mapping, historical prior-use isolation, clean115 split proposal, and LOW-GUARD interface-smoke gates.
- key result: clean115 can be defined by dropping the index-like col0, but restored115 feature names/order remain unverified and historical `my_gold` overlap contains all benign rows.
- claim boundary: no restored115 LOW-GUARD++ smoke or formal full Mirai validation was run; clean115/restored115 remains a separate candidate input track, not the frozen original100 claim.
- next action: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`.
"""
    exp_entry = f"""

| issue27n | full Mirai restored115 mapping and interface-smoke gate | `{primary_verdict}` | Defines clean115 from dirty116 but blocks smoke because feature mapping is unverified and strict prior-use exclusion removes all benign rows. Next: `issue27o_restored115_mapping_recovery_or_original100_reextraction_for_full_mirai`. |
"""
    text = handoff.read_text(encoding="utf-8", errors="ignore")
    if "issue27n full Mirai restored115 mapping gate" not in text:
        handoff.write_text(text.rstrip() + handoff_entry + "\n", encoding="utf-8")
    text = expmap.read_text(encoding="utf-8", errors="ignore")
    if "| issue27n |" not in text:
        expmap.write_text(text.rstrip() + "\n" + exp_entry.strip() + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    primary_verdict = "restored115_feature_mapping_blocked"
    labels = csv_labels(FULL_LABELS)
    full_audit = index_like_audit(FULL_MIRAI, labels)
    numeric = scan_clean115_numeric(FULL_MIRAI, len(labels))
    headers100 = read_original100_headers()
    restored_headers = expected_restored115_headers()
    prior_rows, prior_summary = prior_use_audit(labels)
    split_rows = split_proposal(labels, prior_summary)

    write_csv(
        OUT / "dirty116_index_column_audit.csv",
        [
            {
                "asset": str(FULL_MIRAI),
                "raw_dim": len(first_row(FULL_MIRAI)),
                **full_audit,
            },
            {
                "asset": str(MY_GOLD),
                "raw_dim": len(first_row(MY_GOLD)),
                "row_count": len(np.load(MY_GOLD_LABELS)),
                "decision": "drop_col0_required_by_historical_stage",
                "reason": "historical csv_input_clean_stage1 confirmed col0 index-like",
            },
        ],
    )

    write_csv(
        OUT / "clean115_matrix_manifest.csv",
        [
            {
                "matrix_name": "full_mirai_clean115_virtual",
                "source_csv": str(FULL_MIRAI),
                "label_path": str(FULL_LABELS),
                "construction": "drop index-like col0 from dirty116",
                "materialized": False,
                "proposed_cache_path": str(KITNET / "runs" / "issue27n_full_mirai_clean115_cache" / "Mirai_dataset_clean115.npy"),
                **numeric,
            },
            {
                "matrix_name": "my_gold_clean115_existing",
                "source_csv": str(CLEAN115),
                "label_path": str(CLEAN115_LABELS),
                "construction": "historical clean115 subset",
                "materialized": CLEAN115.exists(),
                "rows": line_count(CLEAN115) if CLEAN115.exists() else "missing",
                "clean_dim": len(first_row(CLEAN115)) if CLEAN115.exists() else "missing",
                "prior_use_role": "historical development subset; not clean eval without disclosure/exclusion",
            },
            {
                "matrix_name": "official_mirai3_115_existing",
                "source_csv": str(OFFICIAL_100K),
                "label_path": str(OFFICIAL_LABELS),
                "timestamp_path": str(OFFICIAL_TS),
                "construction": "existing 115D matrix with timestamp sidecar",
                "materialized": OFFICIAL_100K.exists(),
                "rows": line_count(OFFICIAL_100K),
                "clean_dim": len(first_row(OFFICIAL_100K)),
                "prior_use_role": "candidate timestamped asset; overlap unresolved",
            },
        ],
    )

    map_rows = [
        {
            "mapping_object": "expected_restored115_schema",
            "expected_dim": 115,
            "observed_clean115_dim": numeric["clean_dim"],
            "feature_header_available": False,
            "can_identify_mi_hh_hhjit_hphp_by_name": False,
            "can_identify_lambda_scales_by_name": False,
            "can_identify_statistic_types_by_name": False,
            "current_hstat_extra15_expected": ";".join(expected_hstat_headers()),
            "common100_tentative_indices": "0:15 and 30:115 if classic Hstat insertion is correct",
            "extra15_tentative_indices": "15:30 if classic Hstat insertion is correct",
            "mapping_confidence": "low",
            "decision": "blocked",
            "reason": "dimension matches restored115, but no feature header/source generation script proves clean115 column order",
        },
        {
            "mapping_object": "original100_common_feature_projection",
            "expected_dim": 100,
            "observed_clean115_dim": numeric["clean_dim"],
            "feature_header_available": False,
            "can_identify_mi_hh_hhjit_hphp_by_name": "tentative_from_current_original100_headers_only",
            "can_identify_lambda_scales_by_name": "tentative",
            "can_identify_statistic_types_by_name": "tentative",
            "current_hstat_extra15_expected": "NA",
            "common100_tentative_indices": "0:15 and 30:115",
            "extra15_tentative_indices": "15:30",
            "mapping_confidence": "low",
            "decision": "blocked",
            "reason": "cannot safely create restored115_common100 without verified column order",
        },
        {
            "mapping_object": "restored115_extra15_diagnostic",
            "expected_dim": 15,
            "observed_clean115_dim": numeric["clean_dim"],
            "feature_header_available": False,
            "can_identify_mi_hh_hhjit_hphp_by_name": "expected_Hstat_only",
            "can_identify_lambda_scales_by_name": "tentative",
            "can_identify_statistic_types_by_name": "tentative_weight_mean_std",
            "current_hstat_extra15_expected": ";".join(expected_hstat_headers()),
            "common100_tentative_indices": "NA",
            "extra15_tentative_indices": "15:30",
            "mapping_confidence": "low",
            "decision": "blocked",
            "reason": "extra15 likely Host BW stats, but not verified for this CSV",
        },
    ]
    write_csv(OUT / "restored115_feature_mapping_table.csv", map_rows)
    write_csv(OUT / "clean115_prior_use_isolation_table.csv", prior_rows)
    write_csv(OUT / "clean115_split_proposal_manifest.csv", split_rows)
    write_csv(
        OUT / "restored115_common100_matrix_manifest.csv",
        [
            {
                "matrix_name": "restored115_common100",
                "source": "full_mirai_clean115_virtual",
                "construction_status": "blocked",
                "would_drop_indices_if_mapping_verified": "15:30",
                "would_keep_indices_if_mapping_verified": "0:15,30:115",
                "output_dim": 100,
                "materialized": False,
                "blocked_reason": "feature names/order are not verified; dropping 15 columns would fabricate original100",
            }
        ],
    )
    write_csv(
        OUT / "restored115_all_vs_common100_comparison.csv",
        [
            {
                "schema": "restored115_all",
                "input_dim": 115,
                "mapping_status": "shape_available_semantics_unverified",
                "contains_common100": "tentative_only",
                "contains_extra15": "tentative_only",
                "eligible_for_smoke": False,
                "reason": "no feature-name/order mapping",
            },
            {
                "schema": "restored115_common100",
                "input_dim": 100,
                "mapping_status": "blocked",
                "contains_common100": "unverified",
                "contains_extra15": False,
                "eligible_for_smoke": False,
                "reason": "cannot safely remove tentative Hstat columns without provenance",
            },
            {
                "schema": "restored115_extra15_only",
                "input_dim": 15,
                "mapping_status": "blocked",
                "contains_common100": False,
                "contains_extra15": "unverified",
                "eligible_for_smoke": False,
                "reason": "extra15 likely Hstat but not verified against source column order",
            },
        ],
    )
    write_csv(
        OUT / "restored115_extra15_only_diagnostic.csv",
        [
            {
                "diagnostic_name": "restored115_extra15_only",
                "status": "blocked",
                "tentative_indices": "15:30",
                "tentative_feature_family": "Hstat / Host BW",
                "expected_feature_names": ";".join(expected_hstat_headers()),
                "can_run_lowguard_smoke": False,
                "reason": "feature order mapping is not confirmed; cannot test whether extra15 carries strong signal",
            }
        ],
    )

    write_text(
        OUT / "clean115_construction_report.md",
        f"""
# clean115 Construction Report

clean115 can be defined mechanically by dropping the index-like first column from `Mirai_dataset.csv`.

- raw rows: `{numeric['rows']}`
- raw columns: `{numeric['raw_dim']}`
- clean columns after dropping col0: `{numeric['clean_dim']}`
- label rows: `{len(labels)}`
- NaN count in full scan: `{numeric['nan_count']}`
- Inf count in full scan: `{numeric['inf_count']}`
- constant column count: `{numeric['constant_column_count']}`
- materialized cache: `{numeric['materialized_clean115_cache']}`

The cache was not materialized because the mapping gate has not passed. Creating another >1GB derived matrix before verifying column semantics would add storage churn without improving claim safety.
""",
    )

    write_text(
        OUT / "restored115_feature_mapping_report.md",
        f"""
# restored115 Feature Mapping Report

Mapping confidence: `low`

The 115D dimension is consistent with a classic Kitsune-style restored115 vector. A tentative schema would be:

- current original100 = MI(15) + HH(35) + HH_jit(15) + HpHp(35)
- possible restored115 = MI(15) + Hstat(15) + HH(35) + HH_jit(15) + HpHp(35)

However, the full Mirai clean115 CSV has no feature header, no generation script, and no direct column-order provenance. Therefore:

- MI / HH / HH_jit / HpHp family membership cannot be verified by column name.
- lambda scales cannot be verified by column name.
- the extra15 cannot be safely named beyond a tentative Host-BW/Hstat hypothesis.
- `restored115_common100` cannot be safely constructed.

Decision: block interface smoke until feature-name/order mapping is recovered.
""",
    )

    write_text(
        OUT / "common100_mapping_blocked.md",
        """
# restored115_common100 Mapping Blocked

`restored115_common100` was not materialized and was not used for smoke.

The tempting construction is to assume clean115 is ordered as:

`MI(15) + Hstat(15) + HH(35) + HH_jit(15) + HpHp(35)`

and then remove indices `15:30` to recover the same 100 columns as current `original100`.

That assumption is not claim-safe here because the full Mirai clean115 CSV has no feature names, no column-order manifest, and no generator script proving this order. Deleting 15 anonymous columns would create a pseudo-original100 representation and could manufacture a misleading comparison.

Required next evidence:

- feature-name/order mapping for the 115 columns, or
- a source extractor script that emits the 115 columns in documented order, or
- re-extraction into current original100 with known headers.
""",
    )

    write_text(
        OUT / "restored115_extra15_only_diagnostic.md",
        """
# restored115_extra15_only Diagnostic

The extra15-only diagnostic was not run.

Rationale: extra15 is only a tentative Hstat / Host-BW block inferred from classic Kitsune dimensionality. The current clean115 matrix has no header or column-order proof. Testing anonymous columns 15:30 would be a debugging experiment at best and could not support a paper claim.

The diagnostic should be enabled only after restored115 feature mapping is recovered.
""",
    )

    write_text(
        OUT / "clean115_prior_use_isolation_report.md",
        f"""
# clean115 Prior-Use Isolation Report

The historical `my_gold_mirai_200k` subset appears to be the first 200,000 rows of full Mirai:

- label prefix match: `{prior_summary['prefix_label_match']}`
- sampled feature-row match: `{prior_summary['feature_sample_match']}`

This matters because the prefix contains all available benign rows in the full Mirai label order. After excluding that historical prefix:

- benign remaining: `{prior_summary['benign_remaining_after_excluding_my_gold_prefix']}`
- attack remaining: `{prior_summary['attack_remaining_after_excluding_my_gold_prefix']}`

So strict prior-use isolation makes a clean ID/OOD/final benign split impossible from full Mirai alone. A relaxed split can be used for interface debugging, but not for a clean claim.
""",
    )

    write_text(
        OUT / "clean115_split_proposal_report.md",
        """
# clean115 Split Proposal Report

A relaxed development split is count-feasible, but not clean-claim safe because it uses benign rows from the historical `my_gold` prefix.

A strict prior-use-excluded split is blocked because excluding `my_gold` removes all benign rows.

The timestamped official 100k asset is a useful candidate, but its feature mapping and overlap against full/my_gold remain unresolved. It should be considered in issue27o.
""",
    )

    write_text(
        OUT / "clean115_interface_smoke_blocked.md",
        """
# LOW-GUARD Interface Smoke Blocked

Smoke was not executed.

Gate failures:

1. restored115 feature mapping confidence is low because clean115 lacks verified feature names and column order.
2. restored115_common100 mapping is blocked; deleting the tentative extra15 would fabricate a pseudo-original100.
3. restored115_extra15_only diagnostic is blocked for the same mapping reason.
4. strict prior-use isolation against historical `my_gold` removes all benign rows, blocking a clean ID/OOD/final benign split.

Running HistGB/LR now would produce a representation-development score, not a claim-safe interface result. This is a deliberate technical stop, not a LOW-GUARD++ failure.
""",
    )

    write_text(
        OUT / "issue27n_decision.md",
        f"""
# issue27n Decision

primary_verdict = `{primary_verdict}`

clean115 construction is technically clear, but restored115 feature mapping is not safe enough to run LOW-GUARD interface smoke. The prior-use audit also finds that `my_gold_mirai_200k` likely covers the full Mirai prefix containing all benign rows, so strict isolation leaves no benign rows for clean ID/OOD/final benign evaluation.

The right next step is mapping/provenance recovery, not deployment robustness and not demotion.
""",
    )

    write_text(
        OUT / "claim_update_after_issue27n.md",
        """
# Claim Update After issue27n

## Allowed

- Full Mirai dirty116 can be converted conceptually to clean115 by dropping the index-like first column.
- restored115/clean115 remains a separate candidate input track from frozen original100.
- Full Mirai restored115/clean115 pipeline is not yet ready for formal clean validation.
- Further feature mapping and prior-use isolation are required.

## Still Not Allowed

- LOW-GUARD++ is validated on full Mirai.
- issue27n smoke proves anything, because smoke was blocked.
- Full Mirai proves temporal or cross-dataset generalization.
- clean115/restored115 results are interchangeable with original100.
- LOW-GUARD-LR is final mainline solely because restored115 mapping is unresolved.
""",
    )

    write_text(
        OUT / "reviewer_defense_restored115_mapping.md",
        """
# Reviewer Defense: restored115 Mapping

**Q1: Why not run on the 115D matrix directly?**
Because a 115D shape match is not enough. Without feature names/order, we cannot know whether common100 and extra15 are correctly identified.

**Q2: Why drop col0?**
The first column is a strict row index and is strongly correlated with labels only because the file is ordered benign-first/attack-later.

**Q3: Is this a method failure?**
No. It is an input-schema and prior-use gate. The method has not been evaluated under clean restored115 yet.

**Q4: What blocks a clean split?**
The historical my_gold prefix appears to contain all benign rows. Strictly excluding prior-use rows leaves no benign data.

**Q5: What should happen next?**
Recover feature-name/order mapping or use the timestamped official 100k asset if its mapping and overlap can be resolved.
""",
    )

    write_text(
        OUT / "issue27o_next_action.md",
        """
# issue27o Next Action

Recommended next action:

`issue27o_restored115_mapping_recovery_and_official100k_overlap_audit_2026-05-27`

Goals:

- Recover the exact clean115/restored115 feature-name/order mapping.
- Decide whether `restored115_common100` and `extra15` are safe to construct.
- Audit whether `official_mirai_100k_with_timestamp` overlaps with full Mirai / my_gold.
- If mapping and overlap pass, run a small LOW-GUARD interface smoke on the timestamped 100k asset.

Alternative:

`issue27o_full_mirai_original100_reextraction_from_raw_or_extractor_inputs`

Use this only if packet-level or extractor-compatible raw fields can be recovered.
""",
    )

    summary = f"""
# issue27n Full Mirai restored115 Mapping and Interface Smoke Gate

## Verdict

- primary_verdict = `{primary_verdict}`
- clean115 construction: yes, by dropping dirty116 col0.
- interface smoke: not run.

## Answers

1. clean115 was successfully defined but not materialized as a large duplicate cache.
2. dirty116 col0 should be removed: it is a strict row index and label-correlated only through row order.
3. clean115 cannot yet be safely mapped to restored115 because feature names/order are missing.
4. mapping confidence = `low`.
5. common100 and extra15 are only tentative; `common100_mapping_blocked.md` records why they were not materialized.
6. prior-use/my_gold overlap is severe: sampled features and labels indicate my_gold is the full Mirai prefix, and strict exclusion removes all benign rows.
7. A split proposal was written, but clean-claim evidence is blocked.
8. split evidence_level = `consistency_only_due_to_historical_my_gold_benign_overlap` for relaxed split; strict split is `blocked`.
9. LOW-GUARD interface smoke was not executed.
10. restored115 + HistGB-Conservative remains a candidate, but potential cannot be judged until mapping and split gates pass.
11. restored115_common100 vs restored115_all was not evaluated.
12. It cannot enter formal clean validation yet.
13. Minimal blockers: feature mapping/order and prior-use isolation.
14. issue27o should recover restored115 mapping and audit the timestamped official 100k overlap.
15. Slurm: not needed for this audit; may be needed for full re-extraction or large smoke later.
"""
    write_text(OUT / "summary.md", summary)

    config = {
        "issue": "issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27",
        "primary_verdict": primary_verdict,
        "clean115_construction": "drop_col0_virtual",
        "mapping_confidence": "low",
        "interface_smoke_executed": False,
        "ood_alarm_target": 0.01,
        "final_eval_report_only": True,
    }
    write_text(OUT / "config.json", json.dumps(config, indent=2))
    run_spec = {
        "stages": [
            "dirty116_to_clean115_construction_audit",
            "restored115_feature_mapping_gate",
            "prior_use_isolation",
            "split_proposal",
            "interface_smoke_gate",
        ],
        "smoke_blocked_reason": "low feature mapping confidence and strict prior-use exclusion removes benign rows",
        "no_formal_claim": True,
    }
    write_text(OUT / "run_spec.json", json.dumps(run_spec, indent=2))
    write_text(
        OUT / "command.txt",
        "\n".join(
            [
                "git branch --show-current; git status --short",
                "Get-Content issue27m/summary.md and compatibility tables",
                "rg restored115/clean115/headers/Hstat in repo and runs",
                "python runs/issue27n_full_mirai_restored115_feature_mapping_and_lowguardpp_interface_smoke_2026-05-27/run_issue27n_restored115_mapping_gate.py",
            ]
        ),
    )

    # Manifest last, before docs update.
    manifest_rows = []
    for p in sorted(OUT.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            manifest_rows.append({"path": str(p), "file_name": p.name, "size_bytes": p.stat().st_size, "role": "issue27n_output"})
    write_csv(OUT / "manifest.csv", manifest_rows)
    update_docs(primary_verdict)


if __name__ == "__main__":
    main()
