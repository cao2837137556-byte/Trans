#!/usr/bin/env python3
"""ToN-IoT Route-A loader policy repair audit.

This script is deliberately *not* a detector and deliberately performs no
training, thresholding, feature selection, or model selection.

It consumes the previous CKAM schema/time audit and answers one narrow
question:

    Can the Route-A external ToN-IoT Bro/Zeek assets proceed into frontend
    parity work if the loader uses explicit, reproducible policies?

The two policies audited here are:

1. Headerless Bro conn.log files may be interpreted only when their first data
   row exactly matches the standard 21-column conn schema used by sibling logs.
2. File row order is not trusted for temporal/context features; all external
   flow context must be sorted by timestamp, then by stable row provenance.

No raw file is modified.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ISSUE = "issue27ckan_toniot_route_a_loader_policy_repair_v1_2026-07-09"

STANDARD_CONN_FIELDS = [
    "ts",
    "uid",
    "id.orig_h",
    "id.orig_p",
    "id.resp_h",
    "id.resp_p",
    "proto",
    "service",
    "duration",
    "orig_bytes",
    "resp_bytes",
    "conn_state",
    "local_orig",
    "local_resp",
    "missed_bytes",
    "history",
    "orig_pkts",
    "orig_ip_bytes",
    "resp_pkts",
    "resp_ip_bytes",
    "tunnel_parents",
]

REQUIRED_CONN_FIELDS = [
    "ts",
    "uid",
    "id.orig_h",
    "id.orig_p",
    "id.resp_h",
    "id.resp_p",
    "proto",
    "service",
    "duration",
    "orig_bytes",
    "resp_bytes",
    "conn_state",
    "orig_pkts",
    "orig_ip_bytes",
    "resp_pkts",
    "resp_ip_bytes",
]

FAMILY_NORMALIZE = {
    "ddos": "ddos",
    "dos": "dos",
    "xss": "xss",
    "mitm": "mitm",
    "backdoor": "backdoor",
    "injection": "injection",
    "normal": "benign",
    "password": "password",
    "runsomware": "ransomware",
    "ransomware": "ransomware",
    "scanning": "scanning",
}


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_external_dir() -> Path:
    return repo_root().parents[1] / "datasets" / "external" / "ton_iot_raw_network" / "extracted"


def default_ckam_out() -> Path:
    return repo_root() / "runs" / "issue27ckam_toniot_bro_groundtruth_schema_audit_v1_2026-07-09"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def as_int(value: str) -> int:
    if value is None or value == "":
        return 0
    return int(float(value))


def as_float(value: str) -> float:
    if value is None or value == "":
        return 0.0
    return float(value)


def normalize_family(value: str) -> str:
    return FAMILY_NORMALIZE.get((value or "").strip().lower(), (value or "").strip().lower())


def first_data_columns(path: Path) -> Tuple[int, str, bool]:
    """Return (column_count, first_line_preview, ts_parse_ok)."""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n\r")
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            ts_parse_ok = False
            try:
                float(parts[0])
                ts_parse_ok = True
            except Exception:
                ts_parse_ok = False
            return len(parts), line[:240], ts_parse_ok
    return 0, "", False


def split_type_counts(raw: str) -> Dict[str, int]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        return {}
    return {normalize_family(str(k)): int(v) for k, v in parsed.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--extracted-dir", type=Path, default=default_external_dir())
    ap.add_argument("--ckam-out", type=Path, default=default_ckam_out())
    ap.add_argument(
        "--out",
        type=Path,
        default=repo_root() / "runs" / ISSUE,
    )
    args = ap.parse_args()

    extracted_dir = args.extracted_dir
    ckam_out = args.ckam_out
    out = args.out
    out.mkdir(parents=True, exist_ok=True)

    conn_audit_path = ckam_out / "conn_log_schema_time_audit.csv"
    gt_audit_path = ckam_out / "groundtruth_schema_time_label_audit.csv"
    overlap_path = ckam_out / "groundtruth_to_conn_time_overlap_top8.csv"

    conn_rows = read_csv(conn_audit_path)
    gt_rows = read_csv(gt_audit_path)
    overlap_rows = read_csv(overlap_path)

    loader_rows: List[Dict[str, object]] = []
    unrepaired_blockers: List[Dict[str, object]] = []
    inferred_header_count = 0
    explicit_header_count = 0
    timestamp_sort_required_count = 0

    for row in conn_rows:
        rel = row["relative_path"]
        raw_family = row["scenario_family"]
        normalized_family = normalize_family(raw_family)
        missing = row.get("missing_required_fields", "")
        field_count = as_int(row.get("field_count", "0"))
        monotonic = as_int(row.get("monotonic_violations", "0"))
        full_path = extracted_dir / rel

        header_policy = "explicit_zeek_header"
        inferred_fields = row.get("fields", "")
        inference_reason = ""
        first_col_count = ""
        first_ts_parse_ok = ""
        loader_blocker = ""

        if missing:
            if field_count == 0 and full_path.exists():
                first_count, preview, ts_ok = first_data_columns(full_path)
                first_col_count = first_count
                first_ts_parse_ok = ts_ok
                if first_count == len(STANDARD_CONN_FIELDS) and ts_ok:
                    header_policy = "infer_standard_conn_21_fields_from_data_rows"
                    inferred_fields = "|".join(STANDARD_CONN_FIELDS)
                    inference_reason = (
                        "headerless_conn_log_with_21_tab_fields_and_numeric_ts;"
                        "raw_file_left_unchanged"
                    )
                    inferred_header_count += 1
                    missing_after_policy = ""
                else:
                    missing_after_policy = missing
                    loader_blocker = (
                        f"cannot_infer_header:first_col_count={first_count},"
                        f"ts_parse_ok={ts_ok},preview={preview[:80]}"
                    )
            else:
                missing_after_policy = missing
                loader_blocker = "missing_required_fields_not_repairable_by_declared_policy"
        else:
            explicit_header_count += 1
            missing_after_policy = ""

        if monotonic > 0:
            timestamp_sort_required_count += 1

        if loader_blocker:
            unrepaired_blockers.append(
                {
                    "relative_path": rel,
                    "raw_family": raw_family,
                    "missing_required_fields": missing,
                    "loader_blocker": loader_blocker,
                }
            )

        loader_rows.append(
            {
                "relative_path": rel,
                "parent_group": row.get("parent_group", ""),
                "raw_family": raw_family,
                "normalized_family": normalized_family,
                "scenario_name": row.get("scenario_name", ""),
                "row_count": row.get("row_count", ""),
                "min_ts": row.get("min_ts", ""),
                "max_ts": row.get("max_ts", ""),
                "monotonic_violations": monotonic,
                "timestamp_sort_required": monotonic > 0,
                "header_policy": header_policy,
                "field_count_after_policy": len(inferred_fields.split("|")) if inferred_fields else 0,
                "fields_after_policy": inferred_fields,
                "missing_required_fields_before_policy": missing,
                "missing_required_fields_after_policy": missing_after_policy,
                "first_data_col_count": first_col_count,
                "first_data_ts_parse_ok": first_ts_parse_ok,
                "inference_reason": inference_reason,
                "loader_blocker": loader_blocker,
            }
        )

    gt_policy_rows: List[Dict[str, object]] = []
    for row in gt_rows:
        type_counts = split_type_counts(row.get("type_counts_json", ""))
        sorted_types = sorted(type_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        gt_policy_rows.append(
            {
                "relative_path": row["relative_path"],
                "file_id": row["file_id"],
                "row_count": row["row_count"],
                "min_ts": row["min_ts"],
                "max_ts": row["max_ts"],
                "monotonic_violations": row["monotonic_violations"],
                "timestamp_sort_required": as_int(row["monotonic_violations"]) > 0,
                "required_fields_pass": row.get("missing_required_fields", "") == "",
                "normalized_type_counts_json": json.dumps(dict(sorted_types), sort_keys=True),
                "primary_normalized_type": sorted_types[0][0] if sorted_types else "",
                "policy": "labels_for_audit_and_reporting_only_not_for_context_feature_extraction",
            }
        )

    alignment_rows: List[Dict[str, object]] = []
    for row in overlap_rows:
        type_counts = split_type_counts(row.get("gt_types", ""))
        gt_types = sorted(type_counts.keys())
        conn_family_norm = normalize_family(row.get("conn_family", ""))
        family_match = conn_family_norm in gt_types
        rank = as_int(row.get("rank", "0"))
        overlap_seconds = as_float(row.get("overlap_seconds", "0"))
        alignment_rows.append(
            {
                "groundtruth_file": row.get("groundtruth_file", ""),
                "groundtruth_file_id": row.get("groundtruth_file_id", ""),
                "gt_rows": row.get("gt_rows", ""),
                "gt_types_normalized": "|".join(gt_types),
                "conn_file": row.get("conn_file", ""),
                "conn_family_raw": row.get("conn_family", ""),
                "conn_family_normalized": conn_family_norm,
                "conn_rows": row.get("conn_rows", ""),
                "rank": rank,
                "overlap_seconds": overlap_seconds,
                "family_match": family_match,
                "candidate_strength": (
                    "primary_family_time_match"
                    if rank == 1 and family_match and overlap_seconds > 0
                    else "secondary_family_time_match"
                    if family_match and overlap_seconds > 0
                    else "time_overlap_family_mismatch"
                    if overlap_seconds > 0
                    else "no_overlap"
                ),
                "use_policy": "alignment_audit_only;not_a_training_split",
            }
        )

    write_csv(
        out / "conn_loader_policy.csv",
        loader_rows,
        [
            "relative_path",
            "parent_group",
            "raw_family",
            "normalized_family",
            "scenario_name",
            "row_count",
            "min_ts",
            "max_ts",
            "monotonic_violations",
            "timestamp_sort_required",
            "header_policy",
            "field_count_after_policy",
            "fields_after_policy",
            "missing_required_fields_before_policy",
            "missing_required_fields_after_policy",
            "first_data_col_count",
            "first_data_ts_parse_ok",
            "inference_reason",
            "loader_blocker",
        ],
    )
    write_csv(
        out / "groundtruth_loader_policy.csv",
        gt_policy_rows,
        [
            "relative_path",
            "file_id",
            "row_count",
            "min_ts",
            "max_ts",
            "monotonic_violations",
            "timestamp_sort_required",
            "required_fields_pass",
            "normalized_type_counts_json",
            "primary_normalized_type",
            "policy",
        ],
    )
    write_csv(
        out / "scenario_label_alignment_candidates.csv",
        alignment_rows,
        [
            "groundtruth_file",
            "groundtruth_file_id",
            "gt_rows",
            "gt_types_normalized",
            "conn_file",
            "conn_family_raw",
            "conn_family_normalized",
            "conn_rows",
            "rank",
            "overlap_seconds",
            "family_match",
            "candidate_strength",
            "use_policy",
        ],
    )
    write_csv(
        out / "unrepaired_loader_blockers.csv",
        unrepaired_blockers,
        ["relative_path", "raw_family", "missing_required_fields", "loader_blocker"],
    )

    next_gate = (
        "PASS_A1_READY_WITH_TIMESTAMP_SORT_AND_HEADER_INFERENCE_POLICY"
        if not unrepaired_blockers
        else "BLOCKED_UNREPAIRED_LOADER_SCHEMA"
    )
    summary = {
        "issue": ISSUE,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "next_gate": next_gate,
        "conn_log_files": len(conn_rows),
        "conn_total_rows": sum(as_int(r.get("row_count", "0")) for r in conn_rows),
        "explicit_header_count": explicit_header_count,
        "inferred_header_count": inferred_header_count,
        "unrepaired_loader_blockers": len(unrepaired_blockers),
        "timestamp_sort_required_files": timestamp_sort_required_count,
        "groundtruth_files": len(gt_rows),
        "groundtruth_total_rows": sum(as_int(r.get("row_count", "0")) for r in gt_rows),
        "alignment_candidates": len(alignment_rows),
        "family_time_match_candidates": sum(
            1 for r in alignment_rows if r["family_match"] and as_float(str(r["overlap_seconds"])) > 0
        ),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    (out / "timestamp_sort_policy.md").write_text(
        "\n".join(
            [
                f"# {ISSUE} timestamp/context policy",
                "",
                "This policy freezes the Route-A external-loader behavior before any external",
                "model evaluation.",
                "",
                "## Rules",
                "",
                "1. Do not trust file row order for ToN-IoT Bro/Zeek logs.",
                "2. Sort flow rows by `ts`, then by stable provenance key",
                "   `(relative_path, row_index)` for deterministic ties.",
                "3. Context/temporal features must be past-only after timestamp sorting.",
                "4. Ground-truth labels may be used for audit/report roles only.",
                "5. Ground-truth labels must not be used to clean deployment context windows,",
                "   select features, choose frontend blocks, tune thresholds, calibrate review,",
                "   or choose the best model.",
                "6. Headerless conn.log files are accepted only under the explicit",
                "   `infer_standard_conn_21_fields_from_data_rows` policy recorded in",
                "   `conn_loader_policy.csv`; raw files remain unmodified.",
                "7. `runsomware` is normalized to `ransomware` only as a label spelling",
                "   normalization, not as a data-filtering rule.",
                "",
                "## Gate",
                "",
                f"`{next_gate}`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    (out / "summary.md").write_text(
        "\n".join(
            [
                f"# {ISSUE}",
                "",
                f"Gate: `{next_gate}`",
                "",
                "## Summary",
                "",
                "```json",
                json.dumps(summary, indent=2, ensure_ascii=False),
                "```",
                "",
                "## Interpretation",
                "",
                "This is a loader-policy audit only.  It does not evaluate detector",
                "performance.  If the gate passes, the external ToN-IoT Route-A data can",
                "move to frontend parity and strict zero-shot/few-shot protocol design.",
                "",
            ]
        ),
        encoding="utf-8",
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if not unrepaired_blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
