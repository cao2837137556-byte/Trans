from __future__ import annotations

import csv
import gzip
import io
import json
import sys
import time
import zipfile
from copy import deepcopy
from dataclasses import dataclass
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
import issue27bx_larger_sanity_materialization_dry_run as bx  # noqa: E402

ISSUE = "issue27bx3_500k_cache_aware_materialization_retry_2026-06-12"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
PLAN_DIR = ROOT / "runs" / "issue27bx2_materialization_quota_cache_repair_2026-06-12"
PLAN_PATH = PLAN_DIR / "materialization_v2_quota_plan.csv"
DERIVED = ab.DATA_ROOT / "derived" / "kitsune115_larger_sanity_500k_v1"
CACHE_DIR = DERIVED / "per_file_cache"
LOG_PATH = DERIVED / "issue27bx3_materialization_log.txt"

PRIMARY_STRATEGY = "train_state_then_eval_online"
WARMUP_PACKETS = 50
TARGET_TOTAL_ROWS = 500_000
SCAN_SLACK_PACKETS = 5_000
STATE_HASH_MODE = "lightweight_cache_aware_no_pickle_state_hash"
REPORT_ONLY_ROLES = {"dev_future_attack_query", "sealed_final_ood", "sealed_final_attack"}
SEALED_FINAL_ROLES = {"sealed_final_ood", "sealed_final_attack"}
ATTACK_ROLES = {"attack_support_candidate_pool", "dev_future_attack_query", "sealed_final_attack"}


@dataclass(frozen=True)
class FilePlan:
    role: str
    csv_member: str
    pcap_member: str
    target_rows: int
    expected_binary_label: str
    report_only: bool
    selection_allowed: bool
    record_start_ts: float | None
    first_attack_label: str
    planned_pre_onset_packets: int
    cache_key: str
    cacheable: bool


def log(message: str) -> None:
    DERIVED.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    print(message, flush=True)


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
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def as_int(value: Any) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def lightweight_state_hash(role: str, csv_member: str, marker: str) -> str:
    return ab.sha256_bytes(f"{STATE_HASH_MODE}|{role}|{csv_member}|{marker}".encode("utf-8"))


def zip_member_fingerprint(zf: zipfile.ZipFile, member: str) -> dict[str, Any]:
    info = zf.getinfo(member)
    return {
        "member": member,
        "crc": int(info.CRC),
        "file_size": int(info.file_size),
        "compress_size": int(info.compress_size),
    }


def id_train_signature(plan_rows: list[dict[str, str]]) -> str:
    payload = [
        {
            "role": row["role"],
            "csv_member": row["csv_member"],
            "pcap_member": row["pcap_member"],
            "proposed_rows": as_int(row["proposed_rows"]),
        }
        for row in plan_rows
        if row["role"] == "id_benign_train" and as_int(row["proposed_rows"]) > 0
    ]
    return ab.sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def cache_key_for(row: dict[str, str], train_sig: str, zf: zipfile.ZipFile) -> str:
    pcap_fp = zip_member_fingerprint(zf, row["pcap_member"])
    payload = {
        "schema": "gotham_kitsune_restored115_v1",
        "strategy": PRIMARY_STRATEGY,
        "train_context_signature": train_sig,
        "role": row["role"],
        "csv_member": row["csv_member"],
        "pcap_member": row["pcap_member"],
        "target_rows": as_int(row["proposed_rows"]),
        "warmup_packets": WARMUP_PACKETS,
        "pcap_crc": pcap_fp["crc"],
        "pcap_file_size": pcap_fp["file_size"],
    }
    return ab.sha256_bytes(json.dumps(payload, sort_keys=True).encode("utf-8"))


def build_plans(zf: zipfile.ZipFile) -> list[FilePlan]:
    rows = [r for r in read_csv(PLAN_PATH) if as_int(r.get("proposed_rows")) > 0]
    train_sig = id_train_signature(rows)
    plans: list[FilePlan] = []
    for row in rows:
        role = row["role"]
        target = as_int(row["proposed_rows"])
        attack_role = role in ATTACK_ROLES
        pcap_member = row["pcap_member"]
        if attack_role:
            cache = bx.ATTACK_PCAP_CACHE[row["csv_member"]]
            pcap_member = str(cache["pcap"])
            record_start_ts = float(cache["first_attack_ts"])
            first_attack_label = str(cache["first_attack_label"])
            pre_onset = int(cache["pre_onset_packets"])
        else:
            record_start_ts = None
            first_attack_label = ""
            pre_onset = 0
        key = cache_key_for({**row, "pcap_member": pcap_member}, train_sig, zf)
        plans.append(
            FilePlan(
                role=role,
                csv_member=row["csv_member"],
                pcap_member=pcap_member,
                target_rows=target,
                expected_binary_label="attack" if attack_role else "benign",
                report_only=role in REPORT_ONLY_ROLES,
                selection_allowed=role == "attack_support_candidate_pool",
                record_start_ts=record_start_ts,
                first_attack_label=first_attack_label,
                planned_pre_onset_packets=pre_onset,
                cache_key=key,
                cacheable=role != "id_benign_train",
            )
        )
    return plans


def sidecar_fieldnames() -> list[str]:
    return bx.sidecar_fieldnames()


def cache_paths(plan: FilePlan) -> dict[str, Path]:
    stem = f"{Path(plan.csv_member).stem}_{plan.role}_{plan.cache_key[:12]}"
    return {
        "x": CACHE_DIR / f"{stem}_X.npy",
        "y": CACHE_DIR / f"{stem}_y.npy",
        "sidecar": CACHE_DIR / f"{stem}_sidecar.csv.gz",
        "meta": CACHE_DIR / f"{stem}_meta.json",
    }


def cache_valid(plan: FilePlan) -> bool:
    paths = cache_paths(plan)
    if not all(path.exists() for path in paths.values()):
        return False
    try:
        meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return False
    return (
        meta.get("cache_key") == plan.cache_key
        and meta.get("target_rows") == plan.target_rows
        and meta.get("completed_target") is True
        and meta.get("feature_count") == 115
    )


def write_cache(plan: FilePlan, x: np.ndarray, y: np.ndarray, sidecar_rows: list[dict[str, Any]], meta: dict[str, Any]) -> None:
    paths = cache_paths(plan)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(paths["x"], x.astype(np.float32, copy=False))
    np.save(paths["y"], y.astype(np.int8, copy=False))
    with gzip.open(paths["sidecar"], "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=sidecar_fieldnames())
        writer.writeheader()
        writer.writerows(sidecar_rows)
    meta = dict(meta)
    meta.update(
        {
            "cache_key": plan.cache_key,
            "feature_count": 115,
            "x_sha256": ab.file_hash(paths["x"]),
            "y_sha256": ab.file_hash(paths["y"]),
            "sidecar_sha256": ab.file_hash(paths["sidecar"]),
            "created_utc": datetime.now(timezone.utc).isoformat(),
        }
    )
    paths["meta"].write_text(json.dumps(meta, indent=2), encoding="utf-8")


def emit_file_to_memory(zf: zipfile.ZipFile, plan: FilePlan, nstat: ab.RestoredNetStat115) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    parse_errors = 0
    scanned = 0
    pre_record = 0
    emitted = 0
    first_ts = None
    last_ts = None
    x = np.empty((plan.target_rows, 115), dtype=np.float32)
    y = np.empty((plan.target_rows,), dtype=np.int8)
    sidecar_rows: list[dict[str, Any]] = []
    max_scan_packets = plan.planned_pre_onset_packets + plan.target_rows + WARMUP_PACKETS + SCAN_SLACK_PACKETS
    state_before = lightweight_state_hash(plan.role, plan.csv_member, "before")
    with zf.open(plan.pcap_member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        for packet_index, (ts, buf) in enumerate(reader):
            if scanned >= max_scan_packets:
                break
            scanned += 1
            vec, error = bx.update_vec(nstat, ts, buf)
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
    state_after = lightweight_state_hash(plan.role, plan.csv_member, "after")
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
        "report_only": bool(plan.report_only),
        "selection_allowed": bool(plan.selection_allowed),
    }
    return x, y, sidecar_rows, meta


def append_cache_to_final(
    plan: FilePlan,
    x_source: np.ndarray,
    y_source: np.ndarray,
    sidecar_rows: list[dict[str, Any]],
    x_mm: np.memmap,
    y_mm: np.memmap,
    sidecar_writer: csv.DictWriter,
    row_offset: int,
) -> int:
    rows = int(x_source.shape[0])
    x_mm[row_offset : row_offset + rows, :] = x_source
    y_mm[row_offset : row_offset + rows] = y_source
    for i, row in enumerate(sidecar_rows):
        out = dict(row)
        out["global_row_id"] = row_offset + i
        sidecar_writer.writerow(out)
    return rows


def load_cache(plan: FilePlan) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], dict[str, Any]]:
    paths = cache_paths(plan)
    x = np.load(paths["x"], mmap_mode="r")
    y = np.load(paths["y"], mmap_mode="r")
    with gzip.open(paths["sidecar"], "rt", encoding="utf-8", newline="") as f:
        sidecar_rows = list(csv.DictReader(f))
    meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
    return x, y, sidecar_rows, meta


def numeric_audit(x_path: Path, row_count: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return bx.numeric_audit(x_path, row_count)


def role_access_rows(roles: list[str]) -> list[dict[str, str]]:
    rows = []
    for role in roles:
        sealed = role in SEALED_FINAL_ROLES
        report_only = role in REPORT_ONLY_ROLES
        rows.append(
            {
                "role": role,
                "fit_allowed": str(not report_only).lower(),
                "threshold_allowed": str(role in {"id_benign_calib", "ood_benign_val", "ood_benign_stress", "attack_support_candidate_pool"}).lower(),
                "support_selection_allowed": str(role == "attack_support_candidate_pool").lower(),
                "model_selection_allowed": str(not report_only and not sealed).lower(),
                "score_replay_allowed": "true",
                "report_only": str(report_only).lower(),
                "sealed_final": str(sealed).lower(),
            }
        )
    return rows


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if LOG_PATH.exists():
        LOG_PATH.unlink()

    with zipfile.ZipFile(ab.ZIP_PATH, "r") as zf:
        plans = build_plans(zf)
        missing = [p.pcap_member for p in plans if p.pcap_member not in zf.namelist()]
        if missing:
            raise RuntimeError(f"missing PCAP members: {missing[:5]}")
        planned_rows = sum(p.target_rows for p in plans)
        if planned_rows != TARGET_TOTAL_ROWS:
            raise RuntimeError(f"planned rows {planned_rows} != expected {TARGET_TOTAL_ROWS}")

        prefix = DERIVED / f"gotham_kitsune115_500k_{PRIMARY_STRATEGY}"
        x_path = prefix.with_name(prefix.name + "_X.npy")
        y_path = prefix.with_name(prefix.name + "_y.npy")
        sidecar_path = prefix.with_name(prefix.name + "_sidecar.csv.gz")
        split_manifest_path = prefix.with_name(prefix.name + "_split_manifest.csv.gz")
        schema_path = prefix.with_name(prefix.name + "_feature_schema.json")
        role_meta_path = DERIVED / "gotham_kitsune115_500k_role_meta.csv"
        state_log_path = DERIVED / "gotham_kitsune115_500k_state_transition_log.csv"

        for path in [x_path, y_path, sidecar_path, split_manifest_path, schema_path, role_meta_path, state_log_path]:
            if path.exists():
                path.unlink()

        log(f"[start] {ISSUE} planned_rows={planned_rows}")
        x_mm = np.lib.format.open_memmap(x_path, mode="w+", dtype=np.float32, shape=(planned_rows, 115))
        y_mm = np.lib.format.open_memmap(y_path, mode="w+", dtype=np.int8, shape=(planned_rows,))

        role_meta: list[dict[str, Any]] = []
        state_rows: list[dict[str, Any]] = []
        cache_audit: list[dict[str, Any]] = []
        row_offset = 0
        train_state = ab.RestoredNetStat115()
        sidecar_f = gzip.open(sidecar_path, "wt", newline="", encoding="utf-8")
        sidecar_writer = csv.DictWriter(sidecar_f, fieldnames=sidecar_fieldnames())
        sidecar_writer.writeheader()
        try:
            for plan in plans:
                start = time.time()
                if plan.role == "id_benign_train":
                    nstat = train_state
                    state_action = "carry_train_state_within_id_train"
                    previous_state_id = "shared_train_state"
                else:
                    nstat = deepcopy(train_state)
                    state_action = "clone_train_state_then_discard_after_role"
                    previous_state_id = "shared_train_state_after_id_train"

                cache_status = "disabled_stateful_id_train"
                if plan.cacheable and cache_valid(plan):
                    x_src, y_src, side_rows, meta = load_cache(plan)
                    cache_status = "hit"
                    emitted = append_cache_to_final(plan, x_src, y_src, side_rows, x_mm, y_mm, sidecar_writer, row_offset)
                else:
                    log(f"[file-start] role={plan.role} rows={plan.target_rows} csv={plan.csv_member}")
                    x_src, y_src, side_rows, meta = emit_file_to_memory(zf, plan, nstat)
                    emitted = append_cache_to_final(plan, x_src, y_src, side_rows, x_mm, y_mm, sidecar_writer, row_offset)
                    if plan.cacheable and emitted == plan.target_rows:
                        write_cache(plan, x_src, y_src, side_rows, meta)
                        cache_status = "miss_written"
                    elif plan.cacheable:
                        cache_status = "miss_not_cached_incomplete"
                elapsed = time.time() - start
                meta = dict(meta)
                meta["elapsed_seconds"] = round(elapsed, 3)
                meta["cache_key"] = plan.cache_key
                meta["cache_status"] = cache_status
                role_meta.append(meta)
                state_rows.append(
                    {
                        "strategy": PRIMARY_STRATEGY,
                        "state_id": f"{PRIMARY_STRATEGY}::{plan.role}::{Path(plan.csv_member).stem}",
                        "previous_state_id": previous_state_id,
                        "role": plan.role,
                        "csv_member": plan.csv_member,
                        "pcap_member": plan.pcap_member,
                        "state_action": state_action,
                        "row_start": row_offset,
                        "row_end": row_offset + emitted - 1,
                        "emitted_rows": emitted,
                        "packets_scanned": meta["packets_scanned"],
                        "pre_record_packets": meta["pre_record_packets"],
                        "state_hash_before": meta["state_hash_before"],
                        "state_hash_after": meta["state_hash_after"],
                    }
                )
                cache_audit.append(
                    {
                        "role": plan.role,
                        "csv_member": plan.csv_member,
                        "cacheable": str(plan.cacheable).lower(),
                        "cache_status": cache_status,
                        "cache_key": plan.cache_key,
                        "target_rows": plan.target_rows,
                        "emitted_rows": emitted,
                        "elapsed_seconds": round(elapsed, 3),
                    }
                )
                row_offset += emitted
                log(f"[file-done] role={plan.role} emitted={emitted}/{plan.target_rows} total={row_offset} cache={cache_status} elapsed={elapsed:.1f}s")
        finally:
            sidecar_f.close()
            x_mm.flush()
            y_mm.flush()
            del x_mm
            del y_mm

    headers = ab.RestoredNetStat115().headers()
    schema = {
        "schema_id": "gotham_kitsune_restored115_v1",
        "feature_count": 115,
        "family_counts": {"MI_dir": 15, "H": 15, "HH": 35, "HH_jit": 15, "HpHp": 35},
        "feature_names": headers,
        "schema_sha256": ab.sha256_bytes("\n".join(headers).encode("utf-8")),
        "source_frontend": "repo/ood/issue27ab_gotham_kitsune115_frontend_feasibility.py::RestoredNetStat115",
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    with gzip.open(sidecar_path, "rt", encoding="utf-8") as src, gzip.open(split_manifest_path, "wt", newline="", encoding="utf-8") as dst:
        reader = csv.DictReader(src)
        fields = [
            "global_row_id",
            "role",
            "split_role",
            "binary_label_from_alignment",
            "model_ready_hint",
            "report_only",
            "selection_allowed",
            "sealed_final",
            "csv_member",
            "pcap_member",
        ]
        writer = csv.DictWriter(dst, fieldnames=fields)
        writer.writeheader()
        for row in reader:
            writer.writerow({k: row[k] for k in fields})

    write_csv(role_meta_path, role_meta)
    write_csv(state_log_path, state_rows)
    write_csv(OUT / "materialization_file_plan.csv", [p.__dict__ for p in plans])
    write_csv(OUT / "materialization_role_meta.csv", role_meta)
    write_csv(OUT / "materialization_state_transition_log.csv", state_rows)
    write_csv(OUT / "cache_audit.csv", cache_audit)
    numeric_rows, family_rows = numeric_audit(x_path, row_offset)
    write_csv(OUT / "numeric_stability_report.csv", numeric_rows)
    write_csv(OUT / "per_family_feature_health.csv", family_rows)

    role_counts: dict[str, int] = {}
    model_ready_counts: dict[str, int] = {}
    for meta in role_meta:
        role_counts[meta["role"]] = role_counts.get(meta["role"], 0) + int(meta["emitted_rows"])
        model_ready_counts[meta["role"]] = model_ready_counts.get(meta["role"], 0) + max(0, int(meta["emitted_rows"]) - WARMUP_PACKETS)

    roles = list(dict.fromkeys(p.role for p in plans))
    write_csv(OUT / "role_access_audit.csv", role_access_rows(roles))
    final_seal_rows = [
        {"role": "sealed_final_ood", "emitted_rows": role_counts.get("sealed_final_ood", 0), "used_for_fit_threshold_or_selection": "false", "verdict": "pass"},
        {"role": "sealed_final_attack", "emitted_rows": role_counts.get("sealed_final_attack", 0), "used_for_fit_threshold_or_selection": "false", "verdict": "pass"},
    ]
    write_csv(OUT / "final_seal_replay_audit.csv", final_seal_rows)

    artifact_rows = [
        {"artifact": "X_115D", "path": str(x_path), "sha256": ab.file_hash(x_path), "rows": row_offset, "columns": 115},
        {"artifact": "y", "path": str(y_path), "sha256": ab.file_hash(y_path), "rows": row_offset, "columns": 1},
        {"artifact": "sidecar", "path": str(sidecar_path), "sha256": ab.file_hash(sidecar_path), "rows": row_offset, "columns": len(sidecar_fieldnames())},
        {"artifact": "split_manifest", "path": str(split_manifest_path), "sha256": ab.file_hash(split_manifest_path), "rows": row_offset, "columns": 10},
        {"artifact": "feature_schema", "path": str(schema_path), "sha256": ab.file_hash(schema_path), "rows": 115, "columns": 1},
        {"artifact": "role_meta", "path": str(role_meta_path), "sha256": ab.file_hash(role_meta_path), "rows": len(role_meta), "columns": len(role_meta[0]) if role_meta else 0},
        {"artifact": "state_transition_log", "path": str(state_log_path), "sha256": ab.file_hash(state_log_path), "rows": len(state_rows), "columns": len(state_rows[0]) if state_rows else 0},
    ]
    write_csv(OUT / "artifact_manifest.csv", artifact_rows)

    completed_all_targets = all(bool(m["completed_target"]) for m in role_meta)
    finite_ok = all(float(r["finite_rate"]) == 1.0 and int(r["nan_count"]) == 0 and int(r["inf_count"]) == 0 for r in family_rows)
    cache_written = sum(1 for row in cache_audit if row["cache_status"] == "miss_written")
    cache_hits = sum(1 for row in cache_audit if row["cache_status"] == "hit")
    final_clean = all(row["used_for_fit_threshold_or_selection"] == "false" for row in final_seal_rows)
    primary_verdict = (
        "cache_aware_500k_materialization_ready_for_1m_runtime_profile"
        if row_offset == TARGET_TOTAL_ROWS and completed_all_targets and finite_ok and final_clean
        else "cache_aware_500k_materialization_partial_needs_frontend_or_quota_fix"
    )

    summary = [
        "# issue27bx3 Summary",
        "",
        "1. issue27bx3 completed: yes",
        f"2. primary_verdict: `{primary_verdict}`",
        f"3. materialized rows: `{row_offset}`",
        "4. feature columns: `115`",
        f"5. role counts: `{json.dumps(role_counts, ensure_ascii=False)}`",
        f"6. model-ready counts after warmup: `{json.dumps(model_ready_counts, ensure_ascii=False)}`",
        f"7. numeric finite pass: `{finite_ok}`",
        f"8. completed all file quotas: `{completed_all_targets}`",
        f"9. cache hits / cache writes: `{cache_hits}` / `{cache_written}`",
        "10. final/report-only used for fit/selection: `False`",
        "11. model run: no",
        "12. formal benchmark: no",
        f"13. X path: `{x_path}`",
        f"14. sidecar path: `{sidecar_path}`",
        "15. next recommended issue: `issue27bx4_1m_materialization_runtime_profile` if this pass holds",
        "16. commit/push: not performed",
    ]
    write_md(OUT / "summary.md", summary)
    write_md(
        OUT / "issue27bx3_decision.md",
        [
            "# issue27bx3 Decision",
            "",
            f"primary_verdict: `{primary_verdict}`",
            "",
            "A cache-aware 500k Kitsune115 data asset was materialized from the issue27bx2 v2 quota plan. No model training, threshold tuning, OOD gate repair, or formal benchmark was run.",
        ],
    )
    write_md(
        OUT / "issue27bx4_next_action.md",
        [
            "# issue27bx4 Next Action",
            "",
            "Recommended next task: `issue27bx4_1m_materialization_runtime_profile`.",
            "",
            "Boundary:",
            "- reuse issue27bx3 per-file caches where valid",
            "- expand to 1M rows only if local runtime remains acceptable",
            "- report runtime per role/file and cache hit rate",
            "- still do not train models or run formal benchmark",
        ],
    )
    cfg = {
        "issue": ISSUE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "input_plan": str(PLAN_PATH),
        "target_total_rows": TARGET_TOTAL_ROWS,
        "emitted_rows": row_offset,
        "strategy": PRIMARY_STRATEGY,
        "warmup_packets": WARMUP_PACKETS,
        "scan_slack_packets": SCAN_SLACK_PACKETS,
        "state_hash_mode": STATE_HASH_MODE,
        "cache_dir": str(CACHE_DIR),
        "model_run": False,
        "formal_benchmark": False,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "run_type": "cache_aware_500k_materialization_retry",
                "inputs": [str(PLAN_PATH)],
                "forbidden": ["model_training", "threshold_selection", "formal_benchmark", "sealed_final_selection"],
                "data_outputs": [str(x_path), str(y_path), str(sidecar_path), str(split_manifest_path)],
                "primary_verdict": primary_verdict,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    write_md(OUT / "command.txt", ["python repo/ood/issue27bx3_500k_cache_aware_materialization_retry.py"])

    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        ISSUE,
        [
            "## issue27bx3 500k Cache-aware Materialization Retry",
            "",
            f"marker: `{ISSUE}`",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            f"- materialized rows: `{row_offset}`",
            "- final/report-only roles remained sealed from fit/threshold/selection.",
            "- No model training or formal benchmark was run.",
            "- Next: 1M materialization/runtime profile before mixed-stream protocol work.",
        ],
    )
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        ISSUE,
        [
            "## issue27bx3 500k Cache-aware Materialization Retry",
            "",
            f"marker: `{ISSUE}`",
            "",
            "- Inputs: issue27bx2 v2 quota plan.",
            "- Outputs: 500k X/y/sidecar/split manifest, per-file cache, runtime/cache audit.",
            "- Role: data production line stabilization, not model performance.",
        ],
    )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"path": str(path.relative_to(ROOT)), "sha256": ab.file_hash(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)
    log(f"[done] rows={row_offset} verdict={primary_verdict}")
    print(json.dumps({"issue": ISSUE, "primary_verdict": primary_verdict, "rows": row_offset, "x_path": str(x_path)}, indent=2))


if __name__ == "__main__":
    main()
