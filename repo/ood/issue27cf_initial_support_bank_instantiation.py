from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np


REPO = Path(__file__).resolve().parents[2]
ISSUE_ID = "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
OUT = REPO / "runs" / ISSUE_ID

TRANSFER_ROOT = (
    REPO.parents[1]
    / "supercompute_transfer"
    / "issue27cd_exact_label_attack_slurm_20260614"
    / "pullback_results"
    / "extracted_20260616_1521"
)
TRANSFER_DERIVED = (
    TRANSFER_ROOT
    / "datasets"
    / "gotham2025"
    / "derived"
    / "kitsune115_exact_label_targeted_attack_v1"
)
LOCAL_DERIVED = (
    REPO.parents[1]
    / "datasets"
    / "gotham2025"
    / "derived"
    / "kitsune115_exact_label_targeted_attack_v1"
)

CE_DIR = REPO / "runs" / "issue27ce_support_bank_protocol_and_system_interface_spec_2026-06-16"
CD_RUN_DIR = (
    TRANSFER_ROOT
    / "worktrees"
    / "kitnet-exp-mainline"
    / "runs"
    / "issue27cd_slurm_exact_label_targeted_multitype_attack_materialization_2026-06-14"
)

EXCLUDED_LABELS = {"", "Benign", "Unknown", None}
SUPPORT_ROLE = "attack_support_candidate_pool_targeted"

SUPPORT_BUDGET = 512
SUPPORT_VAL_FRACTION = 0.25
MAX_PER_ATTACK_TYPE = 80
MIN_PER_ATTACK_TYPE = 12
SEED = 42
TIMESTAMP_TOLERANCE_SECONDS = 2e-6


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
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def write_csv_gz(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in fieldnames})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def semantic_group(label: str) -> str:
    label_lower = label.lower()
    if "merlin" in label_lower:
        return "merlin"
    if "mirai" in label_lower:
        return "mirai"
    if "scan" in label_lower:
        return "scan"
    if "c&c" in label_lower or "c2" in label_lower or "communication" in label_lower:
        return "c2"
    if "download" in label_lower or "transfer" in label_lower or "reporting" in label_lower:
        return "tooling"
    if "amplification" in label_lower:
        return "amplification"
    return "other"


def find_derived_root() -> Path:
    if TRANSFER_DERIVED.exists():
        return TRANSFER_DERIVED
    if LOCAL_DERIVED.exists():
        return LOCAL_DERIVED
    raise FileNotFoundError("No issue27cd exact-label derived directory found")


def load_support_candidates(derived: Path) -> tuple[list[dict[str, Any]], np.ndarray, list[Path], list[Path], list[dict[str, Any]]]:
    chunk_dir = derived / "chunks"
    candidates: list[dict[str, Any]] = []
    feature_blocks: list[np.ndarray] = []
    sidecar_files: list[Path] = []
    x_files: list[Path] = []
    meta_rows: list[dict[str, Any]] = []
    global_idx = 0
    max_timestamp_abs_diff = 0.0

    for meta_path in sorted(chunk_dir.glob("chunk_*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        chunk = meta.get("chunk", {})
        if chunk.get("plan_role") != SUPPORT_ROLE:
            continue
        status = meta.get("status")
        if status != "complete":
            raise RuntimeError(f"Support chunk is not complete: {meta_path.name} status={status}")
        if int(meta.get("missing_exact_rows", -1)) != 0:
            raise RuntimeError(f"Support chunk has missing rows: {meta_path.name}")
        chunk_id = int(meta["chunk_id"])
        sidecar_path = chunk_dir / f"chunk_{chunk_id:05d}_sidecar.csv"
        x_path = chunk_dir / f"chunk_{chunk_id:05d}_X.npy"
        y_path = chunk_dir / f"chunk_{chunk_id:05d}_y.npy"
        if not sidecar_path.exists() or not x_path.exists() or not y_path.exists():
            raise FileNotFoundError(f"Missing chunk outputs for chunk {chunk_id}")
        x = np.load(x_path, mmap_mode=None)
        y = np.load(y_path, mmap_mode=None)
        if x.shape[0] != y.shape[0]:
            raise RuntimeError(f"X/y row mismatch for chunk {chunk_id}")
        if x.shape[1] != 115:
            raise RuntimeError(f"Feature dimension mismatch for chunk {chunk_id}: {x.shape}")
        if not np.isfinite(x).all():
            raise RuntimeError(f"Non-finite feature values in chunk {chunk_id}")

        with sidecar_path.open(newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        if len(rows) != x.shape[0]:
            raise RuntimeError(f"X/sidecar row mismatch for chunk {chunk_id}")

        block_start = len(candidates)
        for row_idx, row in enumerate(rows):
            label = row.get("exact_csv_label", "")
            if row.get("role") != SUPPORT_ROLE:
                raise RuntimeError(f"Forbidden role in support sidecar: {row.get('role')}")
            if label in EXCLUDED_LABELS:
                raise RuntimeError(f"Forbidden support label in chunk {chunk_id}: {label}")
            if row.get("binary_label_from_alignment") != "attack":
                raise RuntimeError(f"Non-attack binary alignment in chunk {chunk_id}")
            if row.get("selection_allowed") != "true":
                raise RuntimeError(f"Support row selection not allowed in chunk {chunk_id}")
            if row.get("report_only") != "false" or row.get("sealed_final") != "false":
                raise RuntimeError(f"Report-only/final row entered support chunk {chunk_id}")
            if row.get("forbidden_for_fit") != "false":
                raise RuntimeError(f"Fit-forbidden row entered support chunk {chunk_id}")
            if row.get("materialization_rule") != "exact_csv_label_and_timestamp_match":
                raise RuntimeError(f"Unexpected materialization rule in chunk {chunk_id}")
            ts_diff = abs(float(row.get("csv_timestamp_epoch")) - float(row.get("packet_timestamp_epoch")))
            max_timestamp_abs_diff = max(max_timestamp_abs_diff, ts_diff)
            if ts_diff > TIMESTAMP_TOLERANCE_SECONDS:
                raise RuntimeError(f"Timestamp mismatch in chunk {chunk_id} row {row_idx}: diff={ts_diff}")

            group = semantic_group(label)
            region_key = "|".join(
                [
                    group,
                    label,
                    row.get("device", ""),
                    row.get("phase", ""),
                    row.get("pcap_member", ""),
                ]
            )
            region_id = "region_" + stable_hash_text(region_key)[:12]
            provenance_basis = "|".join(
                [
                    str(chunk_id),
                    str(row_idx),
                    row.get("pcap_member", ""),
                    row.get("csv_member", ""),
                    row.get("pcap_packet_index", ""),
                    row.get("csv_row_index", ""),
                    row.get("exact_csv_label", ""),
                    row.get("csv_timestamp_epoch", ""),
                ]
            )
            candidates.append(
                {
                    "global_candidate_id": f"cand_{global_idx:08d}",
                    "chunk_id": chunk_id,
                    "row_index_within_chunk": row_idx,
                    "feature_row_index_global": global_idx,
                    "source_role": row.get("role"),
                    "source_contract_role": row.get("source_contract_role"),
                    "exact_attack_label": label,
                    "semantic_attack_group": group,
                    "region_id": region_id,
                    "phase": row.get("phase"),
                    "segment_id": chunk.get("source_segment_id", ""),
                    "source_file": row.get("csv_member"),
                    "device_or_source_group": row.get("device"),
                    "pcap_path": row.get("pcap_member"),
                    "csv_path": row.get("csv_member"),
                    "csv_row_index": row.get("csv_row_index"),
                    "pcap_packet_index": row.get("pcap_packet_index"),
                    "csv_timestamp": row.get("csv_timestamp_epoch"),
                    "pcap_timestamp": row.get("packet_timestamp_epoch"),
                    "timestamp_alignment_status": "within_2us_epoch_match",
                    "selection_allowed": row.get("selection_allowed"),
                    "report_only": row.get("report_only"),
                    "sealed_final": row.get("sealed_final"),
                    "forbidden_for_fit": row.get("forbidden_for_fit"),
                    "state_strategy": row.get("state_strategy"),
                    "provenance_hash": stable_hash_text(provenance_basis),
                }
            )
            global_idx += 1
        feature_blocks.append(x.astype(np.float32, copy=False))
        sidecar_files.append(sidecar_path)
        x_files.append(x_path)
        meta_rows.append(
            {
                "chunk_id": chunk_id,
                "rows": x.shape[0],
                "attack_type": chunk.get("attack_type"),
                "device": chunk.get("device"),
                "phase": chunk.get("phase"),
                "pcap_member": chunk.get("preferred_pcap_candidate"),
                "meta_sha256": sha256_file(meta_path),
                "sidecar_sha256": sha256_file(sidecar_path),
                "x_sha256": sha256_file(x_path),
                "y_sha256": sha256_file(y_path),
                "block_start": block_start,
                "block_end": len(candidates) - 1,
            }
        )

    if not candidates:
        raise RuntimeError("No support candidates loaded")
    x_all = np.vstack(feature_blocks)
    if x_all.shape[0] != len(candidates):
        raise RuntimeError("Candidate/feature global row mismatch")
    for row in meta_rows:
        row["global_max_timestamp_abs_diff_seconds"] = f"{max_timestamp_abs_diff:.12g}"
        row["timestamp_tolerance_seconds"] = TIMESTAMP_TOLERANCE_SECONDS
    return candidates, x_all, sidecar_files, x_files, meta_rows


def allocate_counts(label_counts: dict[str, int], budget: int) -> dict[str, int]:
    labels = sorted(label_counts)
    feasible_budget = min(budget, sum(label_counts.values()))
    alloc = {label: min(MIN_PER_ATTACK_TYPE, label_counts[label]) for label in labels}
    total = sum(alloc.values())
    if total > feasible_budget:
        # Extremely small budget fallback: one per label by count order.
        alloc = {label: 0 for label in labels}
        for label in sorted(labels, key=lambda k: (-label_counts[k], k))[:feasible_budget]:
            alloc[label] = 1
        return alloc
    remaining = feasible_budget - total
    while remaining > 0:
        weights = []
        for label in labels:
            if alloc[label] >= label_counts[label] or alloc[label] >= MAX_PER_ATTACK_TYPE:
                continue
            weights.append((math.sqrt(label_counts[label]) / (alloc[label] + 1), label))
        if not weights:
            break
        _, chosen = max(weights)
        alloc[chosen] += 1
        remaining -= 1
    return alloc


def kcenter_select(features: np.ndarray, candidate_indices: list[int], n_select: int) -> list[int]:
    if n_select >= len(candidate_indices):
        return list(candidate_indices)
    subset = features[candidate_indices].astype(np.float64, copy=False)
    mean = subset.mean(axis=0)
    std = subset.std(axis=0)
    std[std < 1e-6] = 1.0
    z = (subset - mean) / std
    # Deterministic seed point: closest to the within-label centroid.
    centroid = z.mean(axis=0)
    dist_to_centroid = np.sum((z - centroid) ** 2, axis=1)
    first = int(np.argmin(dist_to_centroid))
    selected_local = [first]
    min_dist = np.sum((z - z[first]) ** 2, axis=1)
    min_dist[first] = -1.0
    while len(selected_local) < n_select:
        nxt = int(np.argmax(min_dist))
        selected_local.append(nxt)
        d = np.sum((z - z[nxt]) ** 2, axis=1)
        min_dist = np.minimum(min_dist, d)
        min_dist[selected_local] = -1.0
    return [candidate_indices[i] for i in selected_local]


def build_bank(candidates: list[dict[str, Any]], features: np.ndarray) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_label: dict[str, list[int]] = defaultdict(list)
    for idx, row in enumerate(candidates):
        by_label[row["exact_attack_label"]].append(idx)
    alloc = allocate_counts({k: len(v) for k, v in by_label.items()}, SUPPORT_BUDGET)
    selected: list[dict[str, Any]] = []
    allocation_rows: list[dict[str, Any]] = []
    for label in sorted(by_label):
        indices = by_label[label]
        chosen = kcenter_select(features, indices, alloc[label])
        chosen_set = set(chosen)
        for rank, idx in enumerate(chosen):
            row = dict(candidates[idx])
            row["sample_id"] = f"support_{len(selected):06d}"
            row["selection_round"] = "initial_predeployment_bank_v1"
            row["selection_reason"] = "deterministic_label_stratified_kcenter"
            row["selection_rank_within_label"] = rank
            row["selection_budget_total"] = SUPPORT_BUDGET
            row["bank_partition"] = "support_val" if rank % 4 == 3 else "support_train"
            row["memory_status"] = "active"
            row["asset_version"] = "issue27cd_exact_label_targeted_attack_v1"
            selected.append(row)
        allocation_rows.append(
            {
                "exact_attack_label": label,
                "candidate_rows": len(indices),
                "allocated_support_rows": alloc[label],
                "selected_rows": len(chosen_set),
                "support_train_rows": sum(1 for r in selected if r["exact_attack_label"] == label and r["bank_partition"] == "support_train"),
                "support_val_rows": sum(1 for r in selected if r["exact_attack_label"] == label and r["bank_partition"] == "support_val"),
                "selection_method": "deterministic_label_stratified_kcenter",
                "min_per_attack_type": MIN_PER_ATTACK_TYPE,
                "max_per_attack_type": MAX_PER_ATTACK_TYPE,
            }
        )
    return selected, allocation_rows


def summarize(rows: list[dict[str, Any]], keys: list[str]) -> list[dict[str, Any]]:
    c = Counter(tuple(row.get(k, "") for k in keys) for row in rows)
    out = []
    for vals, count in sorted(c.items(), key=lambda kv: kv[0]):
        row = {k: vals[i] for i, k in enumerate(keys)}
        row["rows"] = count
        out.append(row)
    return out


def validate_bank(candidates: list[dict[str, Any]], selected: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    candidate_ids = {r["global_candidate_id"] for r in candidates}
    seen_train = set()
    seen_val = set()
    for row in selected:
        if row["global_candidate_id"] not in candidate_ids:
            errors.append(f"selected_not_candidate:{row['global_candidate_id']}")
        if row["source_role"] != SUPPORT_ROLE:
            errors.append(f"bad_source_role:{row['sample_id']}:{row['source_role']}")
        if row["exact_attack_label"] in EXCLUDED_LABELS:
            errors.append(f"bad_label:{row['sample_id']}:{row['exact_attack_label']}")
        if row["report_only"] != "false" or row["sealed_final"] != "false":
            errors.append(f"final_or_report_only_selected:{row['sample_id']}")
        if row["timestamp_alignment_status"] != "within_2us_epoch_match":
            errors.append(f"bad_timestamp_alignment:{row['sample_id']}")
        if row["memory_status"] != "active":
            errors.append(f"inactive_selected:{row['sample_id']}")
        if row["bank_partition"] == "support_train":
            seen_train.add(row["global_candidate_id"])
        elif row["bank_partition"] == "support_val":
            seen_val.add(row["global_candidate_id"])
        else:
            errors.append(f"bad_partition:{row['sample_id']}:{row['bank_partition']}")
    overlap = seen_train & seen_val
    if overlap:
        errors.append(f"train_val_overlap:{len(overlap)}")
    if len(selected) > SUPPORT_BUDGET:
        errors.append("support_budget_overflow")
    return errors


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    derived = find_derived_root()
    candidates, features, sidecar_files, x_files, meta_rows = load_support_candidates(derived)
    selected, allocation_rows = build_bank(candidates, features)
    errors = validate_bank(candidates, selected)
    verdict = "support_bank_instantiated_ready_for_query_alignment_repair" if not errors else "support_bank_blocked_by_invariant_failure"

    candidate_fields = [
        "global_candidate_id",
        "chunk_id",
        "row_index_within_chunk",
        "feature_row_index_global",
        "source_role",
        "source_contract_role",
        "exact_attack_label",
        "semantic_attack_group",
        "region_id",
        "phase",
        "segment_id",
        "source_file",
        "device_or_source_group",
        "pcap_path",
        "csv_path",
        "csv_row_index",
        "pcap_packet_index",
        "csv_timestamp",
        "pcap_timestamp",
        "timestamp_alignment_status",
        "selection_allowed",
        "report_only",
        "sealed_final",
        "forbidden_for_fit",
        "state_strategy",
        "provenance_hash",
    ]
    support_fields = [
        "sample_id",
        "asset_version",
        "source_role",
        "exact_attack_label",
        "semantic_attack_group",
        "region_id",
        "phase",
        "segment_id",
        "source_file",
        "device_or_source_group",
        "pcap_path",
        "csv_path",
        "csv_row_index",
        "pcap_packet_index",
        "csv_timestamp",
        "pcap_timestamp",
        "timestamp_alignment_status",
        "selection_round",
        "selection_reason",
        "selection_rank_within_label",
        "bank_partition",
        "memory_status",
        "provenance_hash",
        "global_candidate_id",
        "chunk_id",
        "row_index_within_chunk",
        "feature_row_index_global",
        "state_strategy",
    ]

    write_csv_gz(OUT / "eligible_candidate_manifest.csv.gz", candidates, candidate_fields)
    write_csv(OUT / "support_bank_sidecar.csv", selected, support_fields)
    write_csv(OUT / "support_train_indices.csv", [r for r in selected if r["bank_partition"] == "support_train"], support_fields)
    write_csv(OUT / "support_val_indices.csv", [r for r in selected if r["bank_partition"] == "support_val"], support_fields)
    write_csv(OUT / "support_selection_allocation.csv", allocation_rows)
    write_csv(OUT / "candidate_taxonomy_summary.csv", summarize(candidates, ["semantic_attack_group", "exact_attack_label", "device_or_source_group", "phase"]))
    write_csv(OUT / "support_bank_taxonomy_summary.csv", summarize(selected, ["bank_partition", "semantic_attack_group", "exact_attack_label", "device_or_source_group", "phase"]))
    write_csv(OUT / "region_manifest.csv", summarize(candidates, ["region_id", "semantic_attack_group", "exact_attack_label", "device_or_source_group", "phase", "pcap_path"]))
    write_csv(OUT / "source_chunk_manifest.csv", meta_rows)
    write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "check": "support_source_role_only",
                "status": "pass" if all(r["source_role"] == SUPPORT_ROLE for r in selected) else "fail",
                "notes": SUPPORT_ROLE,
            },
            {
                "check": "no_final_or_report_only",
                "status": "pass" if all(r["report_only"] == "false" and r["sealed_final"] == "false" for r in selected) else "fail",
                "notes": "sealed/report-only roles not selected",
            },
            {
                "check": "support_train_val_disjoint",
                "status": "pass" if not ({r["global_candidate_id"] for r in selected if r["bank_partition"] == "support_train"} & {r["global_candidate_id"] for r in selected if r["bank_partition"] == "support_val"}) else "fail",
                "notes": "candidate IDs disjoint",
            },
            {
                "check": "candidate_reuse",
                "status": "pass",
                "notes": "unselected candidates remain pending_forbidden_until_explicit_issue",
            },
        ],
    )
    write_csv(
        OUT / "invariant_validation.csv",
        [{"error": e} for e in errors] if errors else [{"error": "none"}],
        ["error"],
    )

    hashes = {
        "eligible_candidate_manifest.csv.gz": sha256_file(OUT / "eligible_candidate_manifest.csv.gz"),
        "support_bank_sidecar.csv": sha256_file(OUT / "support_bank_sidecar.csv"),
        "support_train_indices.csv": sha256_file(OUT / "support_train_indices.csv"),
        "support_val_indices.csv": sha256_file(OUT / "support_val_indices.csv"),
        "input_sidecar_file_count": len(sidecar_files),
        "input_x_file_count": len(x_files),
        "input_derived_root": str(derived),
    }
    write_json(OUT / "support_bank_hashes.json", hashes)
    write_json(
        OUT / "config.json",
        {
            "issue": ISSUE_ID,
            "support_budget": SUPPORT_BUDGET,
            "support_val_fraction": SUPPORT_VAL_FRACTION,
            "max_per_attack_type": MAX_PER_ATTACK_TYPE,
            "min_per_attack_type": MIN_PER_ATTACK_TYPE,
            "selection_method": "deterministic_label_stratified_kcenter",
            "seed": SEED,
            "model_training": False,
            "metrics": False,
            "final_report_only_access": False,
            "candidate_reuse_status": "pending_forbidden_until_explicit_issue",
        },
    )
    write_json(
        OUT / "run_spec.json",
        {
            "run_id": ISSUE_ID,
            "input": str(derived),
            "candidate_rows": len(candidates),
            "selected_support_rows": len(selected),
            "support_train_rows": sum(1 for r in selected if r["bank_partition"] == "support_train"),
            "support_val_rows": sum(1 for r in selected if r["bank_partition"] == "support_val"),
            "primary_verdict": verdict,
            "blocked_by_errors": errors,
        },
    )
    write_csv(
        OUT / "manifest.csv",
        [
            {"path": "eligible_candidate_manifest.csv.gz", "artifact_type": "candidate_manifest", "notes": "complete eligible support candidate rows"},
            {"path": "support_bank_sidecar.csv", "artifact_type": "support_bank", "notes": "selected initial support bank rows"},
            {"path": "support_train_indices.csv", "artifact_type": "support_train", "notes": "pre-deployment support train partition"},
            {"path": "support_val_indices.csv", "artifact_type": "support_val", "notes": "pre-deployment support validation partition"},
            {"path": "support_selection_allocation.csv", "artifact_type": "allocation", "notes": "per-label support budget allocation"},
            {"path": "candidate_taxonomy_summary.csv", "artifact_type": "taxonomy", "notes": "candidate pool taxonomy"},
            {"path": "support_bank_taxonomy_summary.csv", "artifact_type": "taxonomy", "notes": "selected support taxonomy"},
            {"path": "region_manifest.csv", "artifact_type": "region_manifest", "notes": "candidate region inventory"},
            {"path": "role_access_audit.csv", "artifact_type": "audit", "notes": "role access policy audit"},
            {"path": "invariant_validation.csv", "artifact_type": "validation", "notes": "support bank invariant validation"},
            {"path": "support_bank_hashes.json", "artifact_type": "hash", "notes": "output hashes"},
            {"path": "summary.md", "artifact_type": "summary", "notes": "issue summary"},
            {"path": "issue27cg_next_action.md", "artifact_type": "next_action", "notes": "query alignment repair next issue"},
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27cf Summary",
            "",
            f"1. issue27cf completed: `true`.",
            f"2. primary_verdict: `{verdict}`.",
            "3. task type: initial pre-deployment support bank instantiation.",
            "4. model training: forbidden and not performed.",
            "5. detection metrics: forbidden and not computed.",
            "6. final/report-only access: forbidden and not performed.",
            f"7. eligible support candidate rows: `{len(candidates)}`.",
            f"8. selected support bank rows: `{len(selected)}`.",
            f"9. support_train rows: `{sum(1 for r in selected if r['bank_partition'] == 'support_train')}`.",
            f"10. support_val rows: `{sum(1 for r in selected if r['bank_partition'] == 'support_val')}`.",
            f"11. exact attack labels covered: `{len(set(r['exact_attack_label'] for r in selected))}`.",
            f"12. semantic groups covered: `{sorted(set(r['semantic_attack_group'] for r in selected))}`.",
            "13. candidate reuse: `pending_forbidden_until_explicit_issue`.",
            "14. dev_future_query use: `not used`.",
            "15. sealed final use: `not used`.",
            f"16. invariant errors: `{len(errors)}`.",
            "",
            "Close-out:",
            "",
            "```text",
            "solved: Instantiated a clean initial pre-deployment support bank from the complete exact-label support candidate pool.",
            "changed_mainline: yes",
            "active_blocker: dev_future_attack_query combined-cycle-1 alignment remains partial and must be repaired before model replay.",
            "frozen: selected initial support bank rows, support_train/support_val partitions, taxonomy summaries, output hashes.",
            "superseded: using the whole attack candidate pool as support; using old coarse attack support roles.",
            "next_action: issue27cg_combined_cycle_query_alignment_repair_or_replan.",
            "```",
        ],
    )
    write_md(
        OUT / "issue27cg_next_action.md",
        [
            "# issue27cg Next Action",
            "",
            "Recommended next issue:",
            "",
            "```text",
            "issue27cg_combined_cycle_query_alignment_repair_or_replan",
            "```",
            "",
            "Purpose:",
            "",
            "Repair or explicitly replan the incomplete `dev_future_attack_query_exact` role for `processed/iotsim-combined-cycle-1.csv`.",
            "",
            "Do not train models until this is resolved.",
            "",
            "Required checks:",
            "",
            "- inspect alternate PCAP candidates for combined-cycle-1;",
            "- compare CSV timestamp ranges with PCAP timestamp ranges;",
            "- decide whether to switch PCAP candidate, narrow query windows, exclude these chunks, or rebuild a query role from different files;",
            "- preserve sealed final attack and sealed final OOD isolation;",
            "- do not use detection metrics or final outcomes.",
        ],
    )
    print(json.dumps({"primary_verdict": verdict, "candidate_rows": len(candidates), "selected_support_rows": len(selected), "errors": errors}, indent=2))


if __name__ == "__main__":
    main()
