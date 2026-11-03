#!/usr/bin/env python3
"""Audit issue27cd partial combined-cycle attack-query alignment.

This is a data-contract audit only. It does not train models, does not emit
new model-ready attack rows, and does not use sealed final or report-only data
for parameter selection.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import dpkt


ROOT = Path(__file__).resolve().parents[2]
ISSUE_ID = "issue27cg_combined_cycle_query_alignment_repair_or_replan_2026-06-17"
OUT = ROOT / "runs" / ISSUE_ID

PAPER04_ROOT = ROOT.parents[1]
GOTHAM_ZIP = PAPER04_ROOT / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"
ISSUE27CD_RUN = ROOT / "runs" / "issue27cd_slurm_exact_label_targeted_multitype_attack_materialization_2026-06-14"
ISSUE27CC_RUN = ROOT / "runs" / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
PULLBACK_ROOT = (
    PAPER04_ROOT
    / "supercompute_transfer"
    / "issue27cd_exact_label_attack_slurm_20260614"
    / "pullback_results"
    / "extracted_20260616_1521"
)
PULLBACK_CHUNKS = (
    PULLBACK_ROOT
    / "datasets"
    / "gotham2025"
    / "derived"
    / "kitsune115_exact_label_targeted_attack_v1"
    / "chunks"
)

PARTIAL_CHUNKS = [37, 39, 40, 49, 50, 51]
TOLERANCE_US_LEVELS = [2, 10, 50, 100, 500, 1000, 5000, 10000]
CSV_MEMBER = "processed/iotsim-combined-cycle-1.csv"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({k for row in rows for k in row})
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def parse_frame_time_epoch(value: str) -> float | None:
    # Import the prior parser to preserve issue27cd semantics.
    import issue27cd_slurm_exact_label_targeted_multitype_attack_materialization as cd

    return cd.parse_frame_time_epoch(value)


def timestamp_key(epoch: float) -> int:
    return int(round(float(epoch) * 1_000_000))


def quantile(sorted_values: list[float], q: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = (len(sorted_values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    frac = pos - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def nearest_abs_diff_us(target_key: int, pcap_keys: list[int]) -> int | None:
    if not pcap_keys:
        return None
    idx = bisect.bisect_left(pcap_keys, target_key)
    best: int | None = None
    for pos in (idx - 1, idx):
        if 0 <= pos < len(pcap_keys):
            diff = abs(pcap_keys[pos] - target_key)
            if best is None or diff < best:
                best = diff
    return best


def greedy_one_to_one_count(target_keys: list[int], pcap_keys: list[int], tolerance_us: int) -> int:
    """Count one-to-one nearest timestamp matches under monotonic ordering."""
    targets = sorted(target_keys)
    pcaps = sorted(pcap_keys)
    i = 0
    j = 0
    matched = 0
    while i < len(targets) and j < len(pcaps):
        diff = pcaps[j] - targets[i]
        if abs(diff) <= tolerance_us:
            matched += 1
            i += 1
            j += 1
        elif pcaps[j] < targets[i] - tolerance_us:
            j += 1
        else:
            i += 1
    return matched


def load_chunk_plan(chunk_id: int) -> list[dict[str, str]]:
    path = ISSUE27CD_RUN / "chunk_plans" / f"chunk_{chunk_id:05d}.csv"
    return read_csv(path)


def load_meta(chunk_id: int) -> dict[str, Any]:
    path = PULLBACK_CHUNKS / f"chunk_{chunk_id:05d}.meta.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_sidecar_rows(chunk_id: int) -> list[dict[str, str]]:
    path = PULLBACK_CHUNKS / f"chunk_{chunk_id:05d}_sidecar.csv"
    return read_csv(path) if path.exists() else []


def row_in_intervals(row_idx: int, intervals: list[tuple[int, int]]) -> bool:
    # Intervals are short enough here; clarity beats cleverness.
    return any(start <= row_idx <= end for start, end in intervals)


def load_csv_targets_by_chunk() -> dict[int, list[dict[str, Any]]]:
    specs: dict[int, dict[str, Any]] = {}
    for chunk_id in PARTIAL_CHUNKS:
        plan = load_chunk_plan(chunk_id)
        specs[chunk_id] = {
            "label": plan[0]["allowed_exact_label"],
            "intervals": [(int(r["planned_start_row"]), int(r["planned_end_row"])) for r in plan],
        }

    targets: dict[int, list[dict[str, Any]]] = {cid: [] for cid in PARTIAL_CHUNKS}
    max_needed = max(end for spec in specs.values() for _start, end in spec["intervals"])
    with zipfile.ZipFile(GOTHAM_ZIP, "r") as zf:
        with zf.open(CSV_MEMBER, "r") as raw:
            reader = csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", newline=""))
            for row_idx, row in enumerate(reader):
                if row_idx > max_needed:
                    break
                label = (row.get("label") or "").strip()
                for chunk_id, spec in specs.items():
                    if label != spec["label"]:
                        continue
                    if not row_in_intervals(row_idx, spec["intervals"]):
                        continue
                    epoch = parse_frame_time_epoch(row.get("frame.time", ""))
                    targets[chunk_id].append(
                        {
                            "chunk_id": chunk_id,
                            "csv_row_index": row_idx,
                            "label": label,
                            "frame_time": row.get("frame.time", ""),
                            "timestamp_epoch": epoch,
                            "timestamp_key": timestamp_key(epoch) if epoch is not None else None,
                        }
                    )
    return targets


def candidate_members() -> list[str]:
    members: list[str] = []
    for chunk_id in PARTIAL_CHUNKS:
        meta = load_meta(chunk_id)
        chunk = meta["chunk"]
        for key in ["preferred_pcap_candidate", "all_pcap_candidates"]:
            for item in str(chunk.get(key, "")).split("|"):
                item = item.strip()
                if item and item not in members:
                    members.append(item)
    return members


def load_pcap_keys(members: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    with zipfile.ZipFile(GOTHAM_ZIP, "r") as zf:
        names = set(zf.namelist())
        for member in members:
            if member not in names:
                out[member] = []
                continue
            keys: list[int] = []
            with zf.open(member, "r") as raw:
                reader = dpkt.pcap.Reader(io.BufferedReader(raw))
                for ts, _buf in reader:
                    keys.append(timestamp_key(float(ts)))
            out[member] = sorted(keys)
    return out


def summarize_chunk(
    chunk_id: int,
    targets: list[dict[str, Any]],
    pcap_keys_by_member: dict[str, list[int]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    meta = load_meta(chunk_id)
    sidecar = load_sidecar_rows(chunk_id)
    chunk = meta["chunk"]
    members = []
    for item in str(chunk.get("all_pcap_candidates", "")).split("|"):
        item = item.strip()
        if item:
            members.append(item)

    target_keys = [int(t["timestamp_key"]) for t in targets if t["timestamp_key"] is not None]
    matched_rows = {int(r["csv_row_index"]) for r in sidecar if str(r.get("csv_row_index", "")).isdigit()}
    missing_targets = [t for t in targets if int(t["csv_row_index"]) not in matched_rows]
    missing_keys = [int(t["timestamp_key"]) for t in missing_targets if t["timestamp_key"] is not None]
    chosen = str(meta.get("pcap_member", ""))
    chosen_keys = pcap_keys_by_member.get(chosen, [])
    nearest_missing = [
        d for key in missing_keys if (d := nearest_abs_diff_us(key, chosen_keys)) is not None
    ]
    nearest_missing.sort()
    duplicate_count = len(target_keys) - len(set(target_keys))

    candidate_rows: list[dict[str, Any]] = []
    best_member = ""
    best_2us = -1
    best_1000us = -1
    for member in members:
        keys = pcap_keys_by_member.get(member, [])
        row: dict[str, Any] = {
            "chunk_id": chunk_id,
            "candidate_pcap_member": member,
            "pcap_packet_count": len(keys),
            "is_chosen_by_issue27cd": str(member == chosen).lower(),
        }
        for tol in TOLERANCE_US_LEVELS:
            row[f"match_count_tol_{tol}us"] = greedy_one_to_one_count(target_keys, keys, tol)
        candidate_rows.append(row)
        if row["match_count_tol_2us"] > best_2us:
            best_2us = int(row["match_count_tol_2us"])
            best_member = member
        best_1000us = max(best_1000us, int(row["match_count_tol_1000us"]))

    p50 = quantile(nearest_missing, 0.50)
    p95 = quantile(nearest_missing, 0.95)
    p99 = quantile(nearest_missing, 0.99)
    chosen_tol_counts = {
        f"chosen_match_count_tol_{tol}us": greedy_one_to_one_count(target_keys, chosen_keys, tol)
        for tol in TOLERANCE_US_LEVELS
    }

    if best_2us == len(target_keys):
        diagnosis = "recoverable_by_candidate_pcap_switch"
    elif best_1000us >= max(int(len(target_keys) * 0.95), best_2us + 100):
        diagnosis = "possibly_recoverable_by_bounded_timestamp_tolerance"
    elif len(sidecar) >= len(target_keys) * 0.95:
        diagnosis = "effectively_complete_low_missing"
    elif duplicate_count > len(target_keys) * 0.10:
        diagnosis = "csv_duplicate_or_aggregate_timestamp_risk"
    else:
        diagnosis = "not_repairable_under_exact_packet_timestamp_contract"

    summary = {
        "chunk_id": chunk_id,
        "role": chunk.get("plan_role", ""),
        "csv_member": chunk.get("csv_member", ""),
        "allowed_exact_label": chunk.get("allowed_exact_label", ""),
        "attack_family_hint": chunk.get("attack_family_hint", ""),
        "chosen_pcap_member": chosen,
        "expected_exact_rows": int(meta.get("expected_exact_rows", 0)),
        "csv_targets_rescanned": len(targets),
        "emitted_rows": int(meta.get("emitted_rows", 0)),
        "sidecar_rows": len(sidecar),
        "missing_exact_rows": int(meta.get("missing_exact_rows", 0)),
        "target_unique_timestamp_keys": len(set(target_keys)),
        "target_duplicate_timestamp_keys": duplicate_count,
        "issue27cd_segment_count": meta.get("target_meta", {}).get("segment_count", ""),
        "pcap_packets_scanned_issue27cd": meta.get("packets_scanned", ""),
        "unmatched_pcap_target_window_packets": meta.get("unmatched_pcap_target_window_packets", ""),
        "best_pcap_by_2us": best_member,
        "best_pcap_match_count_tol_2us": best_2us,
        "best_pcap_match_count_tol_1000us": best_1000us,
        "missing_nearest_diff_us_p50": p50,
        "missing_nearest_diff_us_p95": p95,
        "missing_nearest_diff_us_p99": p99,
        "diagnosis": diagnosis,
        **chosen_tol_counts,
    }
    return summary, candidate_rows


def build_replan_candidates(chunk_summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in chunk_summaries:
        missing = int(row["missing_exact_rows"])
        if missing <= 0:
            continue
        if row["diagnosis"] == "not_repairable_under_exact_packet_timestamp_contract":
            action = "replace_this_combined_cycle_1_chunk_from_other_legal_development_query_exact_sources"
        elif row["diagnosis"] == "possibly_recoverable_by_bounded_timestamp_tolerance":
            action = "run_small_repair_probe_with_monotonic_one_to_one_tolerance_before_replacing"
        else:
            action = "manual_review_before_replan"
        rows.append(
            {
                "blocked_chunk_id": row["chunk_id"],
                "blocked_label": row["allowed_exact_label"],
                "missing_rows": missing,
                "current_csv_member": row["csv_member"],
                "current_pcap_member": row["chosen_pcap_member"],
                "required_replacement_role": "dev_future_attack_query_exact",
                "candidate_policy": action,
                "must_not_use": "attack_support_candidate_pool_targeted|same_file_time_forward_dev_query_exact|sealed_final_attack_exact_realign|sealed_final_ood|final_report_only",
                "selection_basis_allowed": "development_side_exact_label_plan_rows_with_successful_packet_timestamp_alignment_only",
            }
        )
    return rows


def update_mainline_docs(primary_verdict: str, missing_rows: int) -> None:
    marker = "<!-- issue27cg_combined_cycle_query_alignment_repair_or_replan -->"
    handoff = ROOT / "runs" / "mainline_docs" / "mainline_handoff.md"
    experiment_map = ROOT / "runs" / "mainline_docs" / "mainline_experiment_map.md"
    block = [
        "",
        marker,
        "### issue27cg combined-cycle query alignment audit",
        f"- solved: diagnosed issue27cd partial dev/query exact-label materialization gap ({missing_rows} rows).",
        "- changed_mainline: no; support bank remains frozen and model replay remains blocked.",
        "- active_blocker: dev_future_attack_query exact packet-label alignment for combined-cycle-1 partial chunks.",
        "- frozen: issue27cf initial support bank, issue27bz benign/OOD 1M asset, sealed final attack/OOD non-selection rules.",
        "- superseded: none; this audit narrows issue27cd partial status.",
        f"- next_action: {primary_verdict}.",
    ]
    for path in [handoff, experiment_map]:
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        if marker not in text:
            path.write_text(text.rstrip() + "\n" + "\n".join(block) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["audit"], default="audit")
    args = parser.parse_args()
    if args.mode != "audit":
        raise ValueError(args.mode)

    OUT.mkdir(parents=True, exist_ok=True)
    csv_targets = load_csv_targets_by_chunk()
    pcap_members = candidate_members()
    pcap_keys = load_pcap_keys(pcap_members)

    chunk_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for chunk_id in PARTIAL_CHUNKS:
        summary, candidates = summarize_chunk(chunk_id, csv_targets[chunk_id], pcap_keys)
        chunk_rows.append(summary)
        candidate_rows.extend(candidates)

    missing_total = sum(int(r["missing_exact_rows"]) for r in chunk_rows)
    non_repairable = [r for r in chunk_rows if r["diagnosis"] == "not_repairable_under_exact_packet_timestamp_contract"]
    tolerance_probe = [r for r in chunk_rows if r["diagnosis"] == "possibly_recoverable_by_bounded_timestamp_tolerance"]
    if non_repairable:
        primary_verdict = "query_alignment_requires_replan_for_combined_cycle_1"
    elif tolerance_probe:
        primary_verdict = "query_alignment_needs_bounded_tolerance_probe_before_replan"
    else:
        primary_verdict = "query_alignment_repairable_without_replan"

    replan_rows = build_replan_candidates(chunk_rows)
    write_csv(OUT / "combined_cycle_partial_chunk_audit.csv", chunk_rows)
    write_csv(OUT / "pcap_candidate_timestamp_match_audit.csv", candidate_rows)
    write_csv(OUT / "legal_query_replan_candidates.csv", replan_rows)
    write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "artifact_or_role": "attack_support_candidate_pool_targeted",
                "used_for_issue27cg": "no",
                "reason": "support bank remains frozen; not used to repair query",
            },
            {
                "artifact_or_role": "sealed_final_attack_exact_realign",
                "used_for_issue27cg": "no",
                "reason": "sealed final remains report-only and forbidden for repair/replan",
            },
            {
                "artifact_or_role": "dev_future_attack_query_exact",
                "used_for_issue27cg": "audit_only",
                "reason": "current blocker being diagnosed",
            },
        ],
    )

    write_md(
        OUT / "combined_cycle_alignment_diagnosis.md",
        [
            "# Combined-Cycle-1 Alignment Diagnosis",
            "",
            f"primary_verdict: `{primary_verdict}`",
            "",
            "This audit is data-only. It does not train models, does not emit new model-ready rows, and does not use sealed final or support rows to choose replacements.",
            "",
            "Key diagnosis:",
            f"- Partial chunk count audited: {len(PARTIAL_CHUNKS)}.",
            f"- Missing exact rows audited: {missing_total}.",
            f"- Non-repairable under strict exact packet timestamp contract: {len(non_repairable)} chunks.",
            f"- Bounded timestamp tolerance probe candidates: {len(tolerance_probe)} chunks.",
            "",
            "Interpretation:",
            "- The incomplete chunks are localized to `processed/iotsim-combined-cycle-1.csv` and `dev_future_attack_query_exact`.",
            "- issue27cd already confirmed the support pool and sealed final attack rows are complete; this audit keeps those frozen.",
            "- A simple quota fill is not allowed. Any replacement must come from legal development-side exact-label rows with packet timestamp alignment.",
        ],
    )
    write_md(
        OUT / "repair_vs_replan_decision.md",
        [
            "# Repair vs Replan Decision",
            "",
            f"Decision: `{primary_verdict}`",
            "",
            "Rules applied:",
            "1. Do not loosen timestamp matching unless a bounded monotonic one-to-one probe shows it recovers rows without ambiguous packet reuse.",
            "2. Do not borrow rows from support bank, selected support, unselected support candidates, sealed final attack, or final OOD.",
            "3. If strict matching remains poor across all candidate PCAPs, replace the dev/query segment from legal development-side exact-label sources.",
            "",
            "Recommended next action:",
            "- If `legal_query_replan_candidates.csv` marks a chunk as `replace_this_combined_cycle_1_chunk_from_other_legal_development_query_exact_sources`, create issue27ch/next data task to replan those dev/query rows from non-final, non-support exact-label sources.",
            "- If a chunk is marked as bounded tolerance probe, run only a small probe first; do not materialize model-ready rows until the probe passes one-to-one monotonic constraints.",
        ],
    )
    write_md(
        OUT / "issue27ch_next_action.md",
        [
            "# issue27ch Next Action",
            "",
            "Recommended next issue:",
            "`issue27ch_dev_query_exact_label_replan_or_bounded_alignment_probe`",
            "",
            "Scope:",
            "- Repair or replace only the missing `dev_future_attack_query_exact` rows identified by issue27cg.",
            "- Keep issue27cf support bank frozen.",
            "- Keep sealed final attack/OOD untouched.",
            "- No model training or detection metrics.",
        ],
    )

    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE_ID,
            "mode": "audit",
            "partial_chunks": PARTIAL_CHUNKS,
            "gotham_zip": str(GOTHAM_ZIP),
            "gotham_zip_sha256": sha256_file(GOTHAM_ZIP),
            "issue27cd_run": str(ISSUE27CD_RUN),
            "pullback_chunks": str(PULLBACK_CHUNKS),
            "primary_verdict": primary_verdict,
        },
    )
    write_json(
        OUT / "config.json",
        {
            "tolerance_us_levels": TOLERANCE_US_LEVELS,
            "csv_member": CSV_MEMBER,
            "forbidden_inputs": [
                "attack_support_candidate_pool_targeted",
                "selected_support_bank",
                "sealed_final_attack_exact_realign",
                "sealed_final_ood",
                "final_report_only",
            ],
        },
    )
    (OUT / "command.txt").write_text(
        "python repo/ood/issue27cg_combined_cycle_query_alignment_repair_or_replan.py --mode audit\n",
        encoding="utf-8",
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27cg Summary",
            "",
            f"issue27cg complete: yes",
            f"primary_verdict: `{primary_verdict}`",
            f"missing_exact_rows_audited: {missing_total}",
            f"support_bank_changed: no",
            f"sealed_final_used: no",
            f"model_training: no",
            "",
            "What this means:",
            "- The data alignment blocker is isolated to combined-cycle-1 dev/query chunks from issue27cd.",
            "- The existing 1M benign/OOD asset and issue27cf support bank remain usable as frozen inputs.",
            "- Model replay remains blocked until the dev/query exact-label alignment gap is repaired or legally replanned.",
        ],
    )
    write_csv(
        OUT / "manifest.csv",
        [
            {"artifact": p.name, "path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size}
            for p in sorted(OUT.iterdir())
            if p.is_file()
        ],
    )
    update_mainline_docs(primary_verdict, missing_total)
    print(json.dumps({"issue": ISSUE_ID, "primary_verdict": primary_verdict, "run_dir": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
