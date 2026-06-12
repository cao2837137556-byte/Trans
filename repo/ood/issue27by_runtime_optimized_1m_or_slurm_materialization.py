from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import pickle
import sys
import time
import zipfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dpkt
import numpy as np

REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
OOD_DIR = REPO_DIR / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402
import issue27bx3_500k_cache_aware_materialization_retry as bx3  # noqa: E402

ISSUE = "issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

BX4_RUN = ROOT / "runs" / "issue27bx4_1m_materialization_runtime_profile_2026-06-12"
PLAN_PATH = BX4_RUN / "materialization_1m_runtime_profile_plan.csv"
BX3_CACHE_DIR = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_500k_v1" / "per_file_cache"
BX4_CACHE_DIR = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_runtime_profile_v1" / "per_file_cache"
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_1m_slurm_cache_pipeline_v1"
CACHE_DIR = DERIVED / "per_file_cache"
QUARANTINE_DIR = DERIVED / "quarantine"
STATE_DIR = DERIVED / "state"
LOG_DIR = DERIVED / "logs"

PRIMARY_STRATEGY = bx3.PRIMARY_STRATEGY
WARMUP_PACKETS = bx3.WARMUP_PACKETS
SCAN_SLACK_PACKETS = bx3.SCAN_SLACK_PACKETS
ATTACK_ROLES = bx3.ATTACK_ROLES
SEALED_FINAL_ROLES = bx3.SEALED_FINAL_ROLES
REPORT_ONLY_ROLES = bx3.REPORT_ONLY_ROLES
CACHE_READ_DIRS = [CACHE_DIR, BX4_CACHE_DIR, BX3_CACHE_DIR]
TARGET_TOTAL_ROWS = 1_000_000


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_once(path: Path, marker: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def log(path: Path, message: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def configure_bx3_plan() -> None:
    bx3.PLAN_PATH = PLAN_PATH


def build_plans() -> list[bx3.FilePlan]:
    configure_bx3_plan()
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        plans = bx3.build_plans(zf)
    if sum(plan.target_rows for plan in plans) != TARGET_TOTAL_ROWS:
        raise RuntimeError("issue27by expects the strict issue27bx4 1M plan.")
    return plans


def cache_paths_in_dir(cache_dir: Path, plan: bx3.FilePlan) -> dict[str, Path]:
    return bx3.cache_paths_in_dir(cache_dir, plan)


def cache_status(plan: bx3.FilePlan) -> tuple[str, str]:
    if plan.role == "id_benign_train":
        return "stateful_train_chain_required", ""
    for cache_dir in CACHE_READ_DIRS:
        paths = cache_paths_in_dir(cache_dir, plan)
        if bx3.cache_valid_for_paths(plan, paths):
            return "existing_valid", str(cache_dir)
    return "missing_needs_job", ""


def plan_rows(plans: list[bx3.FilePlan]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    job_index = 0
    for plan in plans:
        status, source_cache_dir = cache_status(plan)
        if plan.role == "id_benign_train":
            job_kind = "train_state_chain"
        else:
            job_kind = "feature_cache_job"
            job_index += 1
        rows.append(
            {
                "job_index": "" if plan.role == "id_benign_train" else job_index,
                "job_kind": job_kind,
                "role": plan.role,
                "csv_member": plan.csv_member,
                "pcap_member": plan.pcap_member,
                "target_rows": plan.target_rows,
                "expected_binary_label": plan.expected_binary_label,
                "report_only": str(plan.report_only).lower(),
                "sealed_final": str(plan.role in SEALED_FINAL_ROLES).lower(),
                "selection_allowed": str(plan.selection_allowed).lower(),
                "record_start_ts": "" if plan.record_start_ts is None else f"{plan.record_start_ts:.6f}",
                "planned_pre_onset_packets": plan.planned_pre_onset_packets,
                "cache_key": plan.cache_key,
                "cache_status": status,
                "source_cache_dir": source_cache_dir,
                "local_cache_dir": str(CACHE_DIR),
                "quarantine_dir": str(QUARANTINE_DIR),
                "can_run_in_slurm_array": str(plan.role != "id_benign_train").lower(),
            }
        )
    return rows


def file_plan_by_job_index(plans: list[bx3.FilePlan], job_index: int) -> bx3.FilePlan:
    jobs = [plan for plan in plans if plan.role != "id_benign_train"]
    if job_index < 1 or job_index > len(jobs):
        raise IndexError(f"job_index {job_index} outside 1..{len(jobs)}")
    return jobs[job_index - 1]


def state_snapshot_paths() -> dict[str, Path]:
    return {
        "pickle": STATE_DIR / "train_state_after_id_train.pkl",
        "meta": STATE_DIR / "train_state_after_id_train_meta.json",
    }


def cache_train_state(plans: list[bx3.FilePlan], max_rows: int | None = None) -> dict[str, Any]:
    """Build the serial ID train frontend state. This is the dependency for array jobs."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    train_plans = [plan for plan in plans if plan.role == "id_benign_train"]
    state_log = LOG_DIR / "train_state_chain.log"
    if state_log.exists():
        state_log.unlink()
    nstat = ab.RestoredNetStat115()
    total_rows = 0
    role_meta: list[dict[str, Any]] = []
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        for plan in train_plans:
            effective_target = plan.target_rows
            if max_rows is not None:
                remaining = max(0, max_rows - total_rows)
                if remaining <= 0:
                    break
                effective_target = min(effective_target, remaining)
            smoke_plan = plan if effective_target == plan.target_rows else replace_plan_target(plan, effective_target)
            log(state_log, f"[train-file-start] csv={smoke_plan.csv_member} rows={smoke_plan.target_rows}")
            start = time.time()
            x, y, sidecar, meta = emit_with_budget(zf, smoke_plan, nstat, max_wall_seconds=None, progress_log=state_log)
            elapsed = time.time() - start
            total_rows += int(meta["emitted_rows"])
            meta["elapsed_seconds"] = round(elapsed, 3)
            role_meta.append(meta)
            if int(meta["emitted_rows"]) != smoke_plan.target_rows:
                raise RuntimeError(f"ID train state shortfall for {smoke_plan.csv_member}: {meta['emitted_rows']}/{smoke_plan.target_rows}")
            log(state_log, f"[train-file-done] emitted={meta['emitted_rows']} total={total_rows} elapsed={elapsed:.1f}s")
            del x, y, sidecar
    paths = state_snapshot_paths()
    with paths["pickle"].open("wb") as f:
        pickle.dump(nstat, f, protocol=4)
    meta = {
        "snapshot_kind": "train_state_after_id_train",
        "strategy": PRIMARY_STRATEGY,
        "rows_used": total_rows,
        "full_train_state": max_rows is None,
        "state_sha256": ab.file_hash(paths["pickle"]),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "role_meta": role_meta,
    }
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def replace_plan_target(plan: bx3.FilePlan, target_rows: int) -> bx3.FilePlan:
    return bx3.FilePlan(
        role=plan.role,
        csv_member=plan.csv_member,
        pcap_member=plan.pcap_member,
        target_rows=target_rows,
        expected_binary_label=plan.expected_binary_label,
        report_only=plan.report_only,
        selection_allowed=plan.selection_allowed,
        record_start_ts=plan.record_start_ts,
        first_attack_label=plan.first_attack_label,
        planned_pre_onset_packets=plan.planned_pre_onset_packets,
        cache_key=plan.cache_key,
        cacheable=plan.cacheable,
    )


def load_train_state() -> ab.RestoredNetStat115:
    paths = state_snapshot_paths()
    if not paths["pickle"].exists():
        raise FileNotFoundError(f"Missing train state snapshot: {paths['pickle']}")
    with paths["pickle"].open("rb") as f:
        return pickle.load(f)


def emit_with_budget(
    zf: zipfile.ZipFile,
    plan: bx3.FilePlan,
    nstat: ab.RestoredNetStat115,
    max_wall_seconds: float | None,
    progress_log: Path,
    progress_interval_packets: int = 25_000,
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    parse_errors = 0
    scanned = 0
    pre_record = 0
    emitted = 0
    first_ts = None
    last_ts = None
    timeout = False
    start = time.monotonic()
    x = np.empty((plan.target_rows, 115), dtype=np.float32)
    y = np.empty((plan.target_rows,), dtype=np.int8)
    sidecar_rows: list[dict[str, Any]] = []
    max_scan_packets = plan.planned_pre_onset_packets + plan.target_rows + WARMUP_PACKETS + SCAN_SLACK_PACKETS
    state_before = ab.state_hash(nstat)
    with zf.open(plan.pcap_member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        for packet_index, (ts, buf) in enumerate(reader):
            if max_wall_seconds is not None and (time.monotonic() - start) > max_wall_seconds:
                timeout = True
                log(progress_log, f"[timeout] role={plan.role} csv={plan.csv_member} scanned={scanned} emitted={emitted}")
                break
            if scanned >= max_scan_packets:
                break
            scanned += 1
            if scanned % progress_interval_packets == 0:
                log(progress_log, f"[progress] role={plan.role} csv={plan.csv_member} scanned={scanned} emitted={emitted}")
            vec, error = bx3.bx.update_vec(nstat, ts, buf)
            if error is not None or vec is None:
                parse_errors += 1
                continue
            if plan.record_start_ts is not None and float(ts) < plan.record_start_ts:
                pre_record += 1
                continue
            if emitted >= plan.target_rows:
                break
            x[emitted, :] = vec
            y[emitted] = 1 if plan.expected_binary_label == "attack" else 0
            first_ts = float(ts) if first_ts is None else first_ts
            last_ts = float(ts)
            warmup = emitted < WARMUP_PACKETS
            sealed = plan.role in SEALED_FINAL_ROLES
            sidecar_rows.append(
                {
                    "global_row_id": emitted,
                    "strategy": PRIMARY_STRATEGY,
                    "state_id": f"{PRIMARY_STRATEGY}::{plan.role}::{Path(plan.csv_member).stem}",
                    "role": plan.role,
                    "split_role": plan.role,
                    "pcap_member": plan.pcap_member,
                    "csv_member": plan.csv_member,
                    "pcap_packet_index": packet_index,
                    "recorded_index_within_file": emitted,
                    "packet_timestamp_epoch": f"{float(ts):.6f}",
                    "binary_label_from_alignment": plan.expected_binary_label,
                    "label_source": "post_onset_binary_from_csv_first_attack" if plan.expected_binary_label == "attack" else "all_benign_file_contract",
                    "first_attack_label": plan.first_attack_label,
                    "warmup_only": str(warmup).lower(),
                    "model_ready_hint": str(not warmup).lower(),
                    "report_only": str(plan.report_only).lower(),
                    "selection_allowed": str(plan.selection_allowed).lower(),
                    "sealed_final": str(sealed).lower(),
                    "forbidden_for_fit": str(sealed or plan.report_only).lower(),
                    "forbidden_for_threshold": str(sealed).lower(),
                    "forbidden_for_model_selection": str(sealed or plan.report_only).lower(),
                }
            )
            emitted += 1
    x = x[:emitted, :]
    y = y[:emitted]
    state_after = ab.state_hash(nstat)
    meta = {
        "role": plan.role,
        "csv_member": plan.csv_member,
        "pcap_member": plan.pcap_member,
        "target_rows": plan.target_rows,
        "emitted_rows": int(emitted),
        "packets_scanned": int(scanned),
        "pre_record_packets": int(pre_record),
        "parse_errors": int(parse_errors),
        "first_timestamp_epoch": first_ts,
        "last_timestamp_epoch": last_ts,
        "state_hash_before": state_before,
        "state_hash_after": state_after,
        "max_scan_packets": int(max_scan_packets),
        "completed_target": bool(emitted == plan.target_rows),
        "timeout": bool(timeout),
        "report_only": bool(plan.report_only),
        "selection_allowed": bool(plan.selection_allowed),
        "elapsed_seconds": round(time.monotonic() - start, 3),
    }
    return x, y, sidecar_rows, meta


def write_cache(plan: bx3.FilePlan, x: np.ndarray, y: np.ndarray, sidecar_rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    bx3.CACHE_DIR = CACHE_DIR
    bx3.write_cache(plan, x, y, sidecar_rows, meta)


def write_quarantine(plan: bx3.FilePlan, x: np.ndarray, y: np.ndarray, sidecar_rows: list[dict[str, Any]], meta: dict[str, Any], reason: str) -> dict[str, str]:
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    stem = f"INCOMPLETE_{Path(plan.csv_member).stem}_{plan.role}_{plan.cache_key[:12]}"
    paths = {
        "x": QUARANTINE_DIR / f"{stem}_X.npy",
        "y": QUARANTINE_DIR / f"{stem}_y.npy",
        "sidecar": QUARANTINE_DIR / f"{stem}_sidecar.csv.gz",
        "meta": QUARANTINE_DIR / f"{stem}_meta.json",
    }
    np.save(paths["x"], x.astype(np.float32, copy=False))
    np.save(paths["y"], y.astype(np.int8, copy=False))
    with gzip.open(paths["sidecar"], "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=bx3.sidecar_fieldnames())
        writer.writeheader()
        writer.writerows(sidecar_rows)
    meta = dict(meta)
    meta.update(
        {
            "cache_key": plan.cache_key,
            "quarantine_reason": reason,
            "usable_for_merge": False,
            "x_sha256": ab.file_hash(paths["x"]),
            "y_sha256": ab.file_hash(paths["y"]),
            "sidecar_sha256": ab.file_hash(paths["sidecar"]),
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}


def run_file_job(job_index: int, max_wall_seconds: float | None) -> dict[str, Any]:
    plans = build_plans()
    plan = file_plan_by_job_index(plans, job_index)
    job_log = LOG_DIR / f"job_{job_index:03d}_{Path(plan.csv_member).stem}_{plan.role}.log"
    status, source_cache = cache_status(plan)
    if status == "existing_valid":
        result = {
            "job_index": job_index,
            "status": "cache_already_valid",
            "role": plan.role,
            "csv_member": plan.csv_member,
            "source_cache_dir": source_cache,
        }
        log(job_log, json.dumps(result, sort_keys=True))
        return result
    nstat = deepcopy(load_train_state())
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        x, y, sidecar_rows, meta = emit_with_budget(zf, plan, nstat, max_wall_seconds=max_wall_seconds, progress_log=job_log)
    if meta["completed_target"]:
        write_cache(plan, x, y, sidecar_rows, meta)
        status = "cache_written"
        quarantine_paths: dict[str, str] = {}
    else:
        quarantine_paths = write_quarantine(plan, x, y, sidecar_rows, meta, "timeout_or_shortfall")
        status = "quarantined_incomplete"
    result = {
        "job_index": job_index,
        "status": status,
        "role": plan.role,
        "csv_member": plan.csv_member,
        "target_rows": plan.target_rows,
        "emitted_rows": meta["emitted_rows"],
        "packets_scanned": meta["packets_scanned"],
        "elapsed_seconds": meta["elapsed_seconds"],
        "quarantine_meta": quarantine_paths.get("meta", ""),
    }
    log(job_log, json.dumps(result, sort_keys=True))
    return result


def write_slurm_artifacts(rows: list[dict[str, Any]]) -> None:
    array_jobs = [row for row in rows if row["job_kind"] == "feature_cache_job"]
    array_count = len(array_jobs)
    slurm = f"""#!/bin/bash
#SBATCH --job-name=gotham115-by
#SBATCH --output=slurm-%A_%a.out
#SBATCH --error=slurm-%A_%a.err
#SBATCH --array=1-{array_count}
#SBATCH --cpus-per-task=1
#SBATCH --mem=8G
#SBATCH --time=04:00:00

set -euo pipefail
cd "$SLURM_SUBMIT_DIR"

# Prerequisite: run build-train-state once before this array:
# python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode build-train-state

python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py \\
  --mode run-job \\
  --job-index "${{SLURM_ARRAY_TASK_ID}}" \\
  --max-wall-seconds "${{MAX_WALL_SECONDS:-10800}}"
"""
    (OUT / "slurm_job_plan.sh").write_text(slurm, encoding="utf-8")
    write_md(
        OUT / "slurm_submission_notes.md",
        [
            "# Slurm Submission Notes",
            "",
            "This is a data materialization pipeline, not a model experiment.",
            "",
            "1. Copy the worktree and Gotham dataset paths to the compute environment.",
            "2. Build the ID train frontend state once:",
            "   `python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode build-train-state`",
            "3. Submit the array job from the worktree root:",
            "   `sbatch runs/issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12/slurm_job_plan.sh`",
            "4. Do not merge until every required cache is valid and no quarantine item is required.",
            "5. Sealed final roles remain report-only; this pipeline does not train models.",
        ],
    )


def write_reports(smoke_rows: list[dict[str, Any]] | None = None) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    plans = build_plans()
    rows = plan_rows(plans)
    write_csv(OUT / "slurm_array_config.csv", rows)
    write_slurm_artifacts(rows)

    cache_manifest = []
    for plan in plans:
        status, source_cache = cache_status(plan)
        local_paths = cache_paths_in_dir(CACHE_DIR, plan)
        cache_manifest.append(
            {
                "role": plan.role,
                "csv_member": plan.csv_member,
                "target_rows": plan.target_rows,
                "cache_status": status,
                "source_cache_dir": source_cache,
                "local_x_path": str(local_paths["x"]),
                "cache_key": plan.cache_key,
                "merge_allowed_now": str(status == "existing_valid").lower(),
            }
        )
    write_csv(OUT / "per_file_cache_manifest.csv", cache_manifest)

    bx4_progress_path = BX4_RUN / "materialization_progress.csv"
    runtime_rows: list[dict[str, Any]] = []
    if bx4_progress_path.exists():
        runtime_rows = read_csv(bx4_progress_path)
    write_csv(OUT / "runtime_profile_table.csv", runtime_rows)

    role_status: dict[str, dict[str, int]] = {}
    for row in rows:
        role = row["role"]
        role_status.setdefault(role, {"target": 0, "existing": 0, "missing": 0, "stateful": 0})
        role_status[role]["target"] += int(row["target_rows"])
        if row["cache_status"] == "existing_valid":
            role_status[role]["existing"] += int(row["target_rows"])
        elif row["cache_status"] == "missing_needs_job":
            role_status[role]["missing"] += int(row["target_rows"])
        else:
            role_status[role]["stateful"] += int(row["target_rows"])
    role_rows = [{"role": role, **vals} for role, vals in sorted(role_status.items())]
    write_csv(OUT / "role_cache_readiness.csv", role_rows)
    if smoke_rows is None:
        smoke_rows = []
    write_csv(OUT / "local_smoke_report.csv", smoke_rows)

    missing_rows = sum(int(row["target_rows"]) for row in rows if row["cache_status"] == "missing_needs_job")
    existing_rows = sum(int(row["target_rows"]) for row in rows if row["cache_status"] == "existing_valid")
    stateful_rows = sum(int(row["target_rows"]) for row in rows if row["cache_status"] == "stateful_train_chain_required")
    primary_verdict = (
        "slurm_ready_per_file_pipeline_smoke_passed"
        if smoke_rows and all(row.get("status") in {"cache_already_valid", "expected_quarantine_timeout"} for row in smoke_rows)
        else "slurm_ready_pipeline_plan_created_needs_smoke"
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27by Summary",
            "",
            f"- issue: `{ISSUE}`",
            f"- primary_verdict: `{primary_verdict}`",
            f"- target rows in strict 1M contract: `{TARGET_TOTAL_ROWS}`",
            f"- rows already covered by valid cache: `{existing_rows}`",
            f"- rows in stateful ID train chain: `{stateful_rows}`",
            f"- rows still requiring Slurm/local jobs: `{missing_rows}`",
            "- model training: no",
            "- formal benchmark: no",
            "- key correction: non-ID jobs require a frozen ID train frontend state snapshot; they are not independent empty-state jobs.",
            "- final/report-only roles remain sealed and forbidden for fit/threshold/support selection/model selection.",
        ],
    )
    write_md(
        OUT / "merge_asset_report.md",
        [
            "# Merge Asset Report",
            "",
            "Merge was not executed in issue27by.",
            "",
            "Required before merge:",
            "1. Full ID train state snapshot exists and matches the strict issue27bx4 ID train chain.",
            "2. Every non-ID file has a valid completed per-file cache.",
            "3. No quarantine cache is used.",
            "4. Sealed final role metadata remains report-only.",
            "5. The final X/y/sidecar merge writes fresh hashes and a finite audit.",
        ],
    )
    write_md(
        OUT / "issue27by_decision.md",
        [
            "# issue27by Decision",
            "",
            f"primary_verdict: `{primary_verdict}`",
            "",
            "The next production step should move high-cost file extraction to Slurm using a state-snapshot-dependent per-file cache array. The 1M asset is still not certified until all caches are complete and merged.",
        ],
    )
    write_md(
        OUT / "issue27bz_next_action.md",
        [
            "# issue27bz Next Action",
            "",
            "Recommended next task: `issue27bz_slurm_1m_cache_execution_and_certified_merge`.",
            "",
            "Boundary:",
            "- run the Slurm cache array or equivalent local optimized jobs;",
            "- merge only completed valid caches;",
            "- keep final/report-only data sealed;",
            "- still no formal model benchmark until certified 1M asset exists.",
        ],
    )
    write_md(
        OUT / "command.txt",
        [
            "python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode smoke",
            "python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode build-train-state",
            "python repo/ood/issue27by_runtime_optimized_1m_or_slurm_materialization.py --mode run-job --job-index <N> --max-wall-seconds 10800",
        ],
    )
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "created_utc": datetime.now(timezone.utc).isoformat(),
                "plan_path": str(PLAN_PATH),
                "derived": str(DERIVED),
                "cache_dirs": [str(p) for p in CACHE_READ_DIRS],
                "target_total_rows": TARGET_TOTAL_ROWS,
                "primary_verdict": primary_verdict,
                "model_training": False,
                "formal_benchmark": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "runtime_optimized_slurm_ready_materialization_pipeline",
                "inputs": [str(PLAN_PATH), str(BX3_CACHE_DIR), str(BX4_CACHE_DIR)],
                "outputs": [
                    "slurm_array_config.csv",
                    "slurm_job_plan.sh",
                    "per_file_cache_manifest.csv",
                    "runtime_profile_table.csv",
                    "local_smoke_report.csv",
                ],
                "forbidden": ["model_training", "threshold_tuning", "formal_benchmark", "using_quarantine_in_merge"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file() and path.name != "manifest.csv":
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": ab.file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        ISSUE,
        [
            "## issue27by Runtime-optimized 1M/Slurm Materialization Pipeline",
            "",
            f"marker: `{ISSUE}`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Created a state-snapshot-dependent per-file cache pipeline and Slurm array plan.",
            "- No certified 1M asset yet; merge remains blocked until all non-ID caches are complete and quarantine-free.",
            "- No model training or formal benchmark was run.",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE,
        [
            "## issue27by Runtime-optimized 1M/Slurm Materialization Pipeline",
            "",
            f"marker: `{ISSUE}`",
            "",
            "- Role: data production line hardening before certified 1M/larger asset.",
            "- Key constraint: non-ID extraction jobs depend on the frozen ID train frontend state snapshot.",
        ],
    )


def smoke() -> None:
    plans = build_plans()
    smoke_rows: list[dict[str, Any]] = []
    # Smoke 1: validate that cache resolution can find existing certified cache.
    cached = next(plan for plan in plans if plan.role == "sealed_final_attack")
    status, source_cache = cache_status(cached)
    smoke_rows.append(
        {
            "smoke_id": "existing_cache_resolution",
            "role": cached.role,
            "csv_member": cached.csv_member,
            "status": "cache_already_valid" if status == "existing_valid" else "failed",
            "details": source_cache,
        }
    )
    # Smoke 2: validate timeout/quarantine path on the known slow file.
    slow = next(plan for plan in plans if plan.csv_member == "processed/iotsim-building-monitor-1.csv" and plan.role == "dev_future_attack_query")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    smoke_log = LOG_DIR / "smoke_timeout_building_monitor.log"
    if smoke_log.exists():
        smoke_log.unlink()
    nstat = ab.RestoredNetStat115()
    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        x, y, sidecar_rows, meta = emit_with_budget(zf, slow, nstat, max_wall_seconds=2.0, progress_log=smoke_log, progress_interval_packets=5000)
    quarantine = write_quarantine(slow, x, y, sidecar_rows, meta, "local_smoke_expected_timeout")
    smoke_rows.append(
        {
            "smoke_id": "timeout_quarantine_building_monitor",
            "role": slow.role,
            "csv_member": slow.csv_member,
            "status": "expected_quarantine_timeout" if meta["timeout"] and not meta["completed_target"] else "failed",
            "emitted_rows": meta["emitted_rows"],
            "packets_scanned": meta["packets_scanned"],
            "elapsed_seconds": meta["elapsed_seconds"],
            "quarantine_meta": quarantine["meta"],
        }
    )
    write_reports(smoke_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan", "smoke", "build-train-state", "run-job"], default="plan")
    parser.add_argument("--job-index", type=int, default=0)
    parser.add_argument("--max-wall-seconds", type=float, default=None)
    parser.add_argument("--smoke-train-rows", type=int, default=None)
    args = parser.parse_args()

    if args.mode == "plan":
        write_reports([])
        print(json.dumps({"issue": ISSUE, "mode": "plan", "run_dir": str(OUT)}, indent=2))
    elif args.mode == "smoke":
        smoke()
        print(json.dumps({"issue": ISSUE, "mode": "smoke", "run_dir": str(OUT)}, indent=2))
    elif args.mode == "build-train-state":
        meta = cache_train_state(build_plans(), max_rows=args.smoke_train_rows)
        print(json.dumps(meta, indent=2))
    elif args.mode == "run-job":
        if args.job_index <= 0:
            raise SystemExit("--job-index is required for --mode run-job")
        result = run_file_job(args.job_index, max_wall_seconds=args.max_wall_seconds)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
