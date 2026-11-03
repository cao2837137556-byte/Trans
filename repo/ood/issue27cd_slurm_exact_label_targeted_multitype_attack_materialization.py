from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import pickle
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dpkt
import numpy as np

import issue27ab_gotham_kitsune115_frontend_feasibility as ab


REPO = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO.parents[1] / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
ZIP_MD5 = "7ca78c0517ccb3d2854e823678e0f206"

ISSUE_ID = "issue27cd_slurm_exact_label_targeted_multitype_attack_materialization_2026-06-14"
CC_DIR = REPO / "runs" / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
PLAN_PATH = CC_DIR / "targeted_exact_label_materialization_plan.csv"

BASE_CACHE = DATA_ROOT / "derived" / "kitsune115_1m_slurm_cache_pipeline_v1"
TRAIN_STATE = BASE_CACHE / "state" / "train_state_after_id_train.pkl"
TRAIN_STATE_META = BASE_CACHE / "state" / "train_state_after_id_train_meta.json"

DERIVED = DATA_ROOT / "derived" / "kitsune115_exact_label_targeted_attack_v1"
OUT = REPO / "runs" / ISSUE_ID
CHUNK_PLAN_DIR = OUT / "chunk_plans"
CACHE_DIR = DERIVED / "chunks"
QUARANTINE_DIR = DERIVED / "quarantine"
LOG_DIR = DERIVED / "logs"

COMMAND_TEXT = "python repo/ood/issue27cd_slurm_exact_label_targeted_multitype_attack_materialization.py"
EXCLUDED_LABELS = {"", "Benign", "Unknown"}
DEFAULT_CHUNK_ROWS = 40_000
TIME_TOLERANCE_US = 2


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def append_once(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def bool_text(value: Any) -> str:
    if isinstance(value, bool):
        return str(value).lower()
    return str(value).strip().lower()


def parse_bool(value: Any) -> bool:
    return bool_text(value) in {"1", "true", "yes", "y"}


def int_text(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except Exception:
        return default


MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_frame_time_epoch(value: str) -> float | None:
    """Parse Gotham/Wireshark frame.time like 'Jan 14, 2025 18:44:53.420758000 GMT'."""
    s = str(value or "").strip().strip('"')
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        pass
    m = re.match(
        r"^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2}),\s+(?P<year>\d{4})\s+"
        r"(?P<h>\d{2}):(?P<m>\d{2}):(?P<s>\d{2})(?:\.(?P<frac>\d+))?\s+(?P<tz>[A-Z]+)$",
        s,
    )
    if not m:
        return None
    mon = MONTHS.get(m.group("mon"))
    if mon is None:
        return None
    frac = (m.group("frac") or "0")[:6].ljust(6, "0")
    tz = timezone.utc
    dt = datetime(
        int(m.group("year")),
        mon,
        int(m.group("day")),
        int(m.group("h")),
        int(m.group("m")),
        int(m.group("s")),
        int(frac),
        tzinfo=tz,
    )
    return dt.timestamp()


def timestamp_key(epoch: float) -> int:
    return int(round(float(epoch) * 1_000_000))


def timestamp_candidate_keys(epoch: float, tolerance_us: int = TIME_TOLERANCE_US) -> list[int]:
    center = timestamp_key(epoch)
    return list(range(center - tolerance_us, center + tolerance_us + 1))


def ensure_inputs() -> dict[str, Any]:
    errors: list[str] = []
    if not ZIP_PATH.exists():
        errors.append(f"missing Gotham zip: {ZIP_PATH}")
    else:
        actual = md5_file(ZIP_PATH)
        if actual != ZIP_MD5:
            errors.append(f"Gotham zip md5 mismatch: {actual}")
    if not PLAN_PATH.exists():
        errors.append(f"missing issue27cc materialization plan: {PLAN_PATH}")
    if not TRAIN_STATE.exists():
        errors.append(f"missing train-state snapshot: {TRAIN_STATE}")
    if not TRAIN_STATE_META.exists():
        errors.append(f"missing train-state meta: {TRAIN_STATE_META}")
    return {
        "ok": not errors,
        "errors": errors,
        "zip_path": str(ZIP_PATH),
        "plan_path": str(PLAN_PATH),
        "train_state": str(TRAIN_STATE),
    }


def validate_plan_rows(rows: list[dict[str, str]]) -> dict[str, Any]:
    label_counts = Counter()
    role_counts = Counter()
    bad_rows: list[dict[str, Any]] = []
    pcap_conf_counts = Counter()
    for i, row in enumerate(rows):
        label = row.get("allowed_exact_label", "")
        role = row.get("plan_role", "")
        rows_n = int_text(row.get("planned_rows"))
        label_counts[label] += rows_n
        role_counts[role] += rows_n
        pcap_conf_counts[row.get("pcap_pairing_confidence", "")] += 1
        if label in EXCLUDED_LABELS:
            bad_rows.append({"row_index": i, "reason": "forbidden_exact_label", "label": label})
        if rows_n <= 0:
            bad_rows.append({"row_index": i, "reason": "non_positive_planned_rows", "planned_rows": rows_n})
        if row.get("selection_allowed", "").lower() == "true" and parse_bool(row.get("sealed_final")):
            bad_rows.append({"row_index": i, "reason": "sealed_final_selection_allowed"})
        if parse_bool(row.get("sealed_final")) and not parse_bool(row.get("report_only")):
            bad_rows.append({"row_index": i, "reason": "sealed_final_not_report_only"})
    return {
        "plan_rows": len(rows),
        "planned_rows_total": sum(int_text(r.get("planned_rows")) for r in rows),
        "role_counts": dict(sorted(role_counts.items())),
        "label_counts": dict(sorted(label_counts.items())),
        "pcap_pairing_confidence_counts": dict(sorted(pcap_conf_counts.items())),
        "bad_rows": bad_rows[:50],
        "bad_row_count": len(bad_rows),
    }


def plan_mode() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    inputs = ensure_inputs()
    rows = read_csv(PLAN_PATH) if PLAN_PATH.exists() else []
    audit = validate_plan_rows(rows)
    primary = "exact_label_materialization_plan_ready_for_slurm" if inputs["ok"] and audit["bad_row_count"] == 0 else "blocked_by_preflight_or_contract_error"
    payload = {
        "issue": ISSUE_ID,
        "mode": "plan",
        "primary_verdict": primary,
        "inputs": inputs,
        "plan_audit": audit,
        "derived_dir": str(DERIVED),
        "run_dir": str(OUT),
        "no_model_training": True,
        "final_report_only_used_for_selection": False,
    }
    write_json(OUT / "plan_preflight.json", payload)
    write_csv(
        OUT / "role_access_audit.csv",
        [
            {
                "role": "attack_support_candidate_pool_targeted",
                "fit_allowed": "yes_for_future_support_selector_only",
                "threshold_allowed": "no",
                "model_selection_allowed": "no",
                "score_only": "no",
                "report_only": "no",
            },
            {
                "role": "dev_future_attack_query_exact",
                "fit_allowed": "no",
                "threshold_allowed": "no",
                "model_selection_allowed": "no",
                "score_only": "future_diagnostic_only",
                "report_only": "development_report_only",
            },
            {
                "role": "same_file_time_forward_dev_query_exact",
                "fit_allowed": "no",
                "threshold_allowed": "no",
                "model_selection_allowed": "no",
                "score_only": "future_diagnostic_only",
                "report_only": "development_report_only",
            },
            {
                "role": "sealed_final_attack_exact_realign",
                "fit_allowed": "no",
                "threshold_allowed": "no",
                "model_selection_allowed": "no",
                "score_only": "final_replay_only",
                "report_only": "sealed_final",
            },
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            f"# {ISSUE_ID}",
            "",
            f"- primary_verdict: {primary}",
            "- task: Slurm transfer/materialization gate for exact-label targeted multi-type attack Kitsune115 chunks.",
            "- model training: forbidden and not performed.",
            "- exact-label rule: only rows whose processed CSV label equals `allowed_exact_label` may be emitted.",
            "- forbidden old rule: post-onset binary emission based only on first attack label.",
            f"- planned rows total: {audit['planned_rows_total']}",
            f"- bad row count: {audit['bad_row_count']}",
            f"- derived output: `{DERIVED}`",
        ],
    )
    print(json.dumps(payload, indent=2))
    if primary.startswith("blocked"):
        raise SystemExit(2)
    return payload


def split_plan_row(row: dict[str, str], chunk_rows: int) -> list[dict[str, Any]]:
    start = int_text(row["planned_start_row"])
    end = int_text(row["planned_end_row"])
    out: list[dict[str, Any]] = []
    cur = start
    while cur <= end:
        sub_end = min(end, cur + chunk_rows - 1)
        sub = dict(row)
        sub["planned_start_row"] = str(cur)
        sub["planned_end_row"] = str(sub_end)
        sub["planned_rows"] = str(sub_end - cur + 1)
        out.append(sub)
        cur = sub_end + 1
    return out


def chunk_group_key(row: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("plan_role", "")),
        str(row.get("csv_member", "")),
        str(row.get("device", "")),
        str(row.get("attack_type", "")),
        str(row.get("preferred_pcap_candidate", "")),
        str(row.get("all_pcap_candidates", "")),
        str(row.get("selection_allowed", "")),
        str(row.get("report_only", "")),
        str(row.get("sealed_final", "")),
    )


def chunk_group_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (*chunk_group_key(row), int_text(row.get("planned_start_row")))


def write_chunk(chunk_id: int, segments: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> None:
    if not segments:
        return
    base = segments[0]
    planned = sum(int_text(s.get("planned_rows")) for s in segments)
    path = CHUNK_PLAN_DIR / f"chunk_{chunk_id:05d}.csv"
    for segment in segments:
        segment["chunk_id"] = chunk_id
    write_csv(path, segments)
    chunks.append(
        {
            "chunk_id": chunk_id,
            "plan_role": base["plan_role"],
            "csv_member": base["csv_member"],
            "preferred_pcap_candidate": base["preferred_pcap_candidate"],
            "all_pcap_candidates": base["all_pcap_candidates"],
            "device": base["device"],
            "attack_type": base["attack_type"],
            "phase": "mixed_phase" if len({s.get("phase", "") for s in segments}) > 1 else base["phase"],
            "planned_start_row": min(int_text(s["planned_start_row"]) for s in segments),
            "planned_end_row": max(int_text(s["planned_end_row"]) for s in segments),
            "planned_rows": planned,
            "segment_count": len(segments),
            "allowed_exact_label": base["allowed_exact_label"],
            "selection_allowed": base["selection_allowed"],
            "report_only": base["report_only"],
            "sealed_final": base["sealed_final"],
            "forbidden_for_fit": base["forbidden_for_fit"],
            "forbidden_for_threshold": base["forbidden_for_threshold"],
            "forbidden_for_model_selection": base["forbidden_for_model_selection"],
            "pcap_pairing_confidence": base["pcap_pairing_confidence"],
            "requires_pcap_pairing_verification": base["requires_pcap_pairing_verification"],
            "chunk_plan_file": str(path),
        }
    )


def build_chunks(chunk_rows: int) -> dict[str, Any]:
    plan = plan_mode()
    rows = read_csv(PLAN_PATH)
    CHUNK_PLAN_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for old in CHUNK_PLAN_DIR.glob("chunk_*.csv"):
        old.unlink()
    chunks: list[dict[str, Any]] = []
    pieces: list[dict[str, Any]] = []
    for row in rows:
        pieces.extend(split_plan_row(row, chunk_rows))
    pieces.sort(key=chunk_group_sort_key)
    chunk_id = 1
    current: list[dict[str, Any]] = []
    current_key: tuple[str, ...] | None = None
    current_rows = 0
    for piece in pieces:
        key = chunk_group_key(piece)
        piece_rows = int_text(piece["planned_rows"])
        if current and (key != current_key or current_rows + piece_rows > chunk_rows):
            write_chunk(chunk_id, current, chunks)
            chunk_id += 1
            current = []
            current_rows = 0
        current_key = key
        current.append(piece)
        current_rows += piece_rows
    if current:
        write_chunk(chunk_id, current, chunks)
    write_csv(OUT / "chunk_manifest.csv", chunks)
    summary = {
        "issue": ISSUE_ID,
        "mode": "build_chunks",
        "chunk_rows": chunk_rows,
        "chunk_count": len(chunks),
        "planned_rows_total": sum(int_text(c["planned_rows"]) for c in chunks),
        "plan_preflight": plan["primary_verdict"],
    }
    write_json(OUT / "chunk_build_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return summary


def load_train_state() -> ab.RestoredNetStat115:
    with TRAIN_STATE.open("rb") as f:
        return pickle.load(f)


def safe_state_hash(nstat: ab.RestoredNetStat115, emitted_rows: int = 0) -> tuple[str, str]:
    try:
        return ab.state_hash(nstat), "ok"
    except (RecursionError, pickle.PickleError, AttributeError, TypeError, ValueError) as exc:
        fallback = hashlib.sha256(
            f"{type(exc).__name__}:{emitted_rows}:{len(nstat.__dict__)}".encode("utf-8")
        ).hexdigest()
        return f"state_hash_unavailable:{fallback}", type(exc).__name__


def update_vec(nstat: ab.RestoredNetStat115, ts: float, buf: bytes) -> tuple[np.ndarray | None, str | None]:
    fields, error = ab.parse_packet(ts, buf)
    if error is not None:
        return None, error
    try:
        vec = nstat.update_get_stats(
            fields["ip_type"],
            fields["src_mac"],
            fields["dst_mac"],
            fields["src_ip"],
            fields["src_protocol"],
            fields["dst_ip"],
            fields["dst_protocol"],
            int(fields["datagram_size"]),
            float(fields["timestamp"]),
        )
        return np.asarray(vec, dtype=np.float32), None
    except Exception as exc:
        return None, str(exc)


def scan_csv_targets(zf: zipfile.ZipFile, segments: list[dict[str, str]]) -> tuple[dict[int, deque[dict[str, Any]]], dict[str, Any]]:
    starts_ends = [(int_text(s["planned_start_row"]), int_text(s["planned_end_row"])) for s in segments]
    min_start = min(s for s, _e in starts_ends)
    max_end = max(e for _s, e in starts_ends)
    allowed = segments[0]["allowed_exact_label"]
    csv_member = segments[0]["csv_member"]
    intervals = sorted(starts_ends)
    targets: dict[int, deque[dict[str, Any]]] = defaultdict(deque)
    label_counts = Counter()
    parse_failures = 0
    scanned = 0
    first_epoch = None
    last_epoch = None
    with zf.open(csv_member, "r") as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
        reader = csv.DictReader(text)
        interval_pos = 0
        for row_idx, row in enumerate(reader):
            if row_idx < min_start:
                continue
            if row_idx > max_end:
                break
            while interval_pos < len(intervals) and row_idx > intervals[interval_pos][1]:
                interval_pos += 1
            if interval_pos >= len(intervals):
                break
            if row_idx < intervals[interval_pos][0] or row_idx > intervals[interval_pos][1]:
                continue
            scanned += 1
            label = row.get("label", "")
            label_counts[label] += 1
            if label != allowed:
                continue
            epoch = parse_frame_time_epoch(row.get("frame.time", ""))
            if epoch is None:
                parse_failures += 1
                continue
            first_epoch = epoch if first_epoch is None else min(first_epoch, epoch)
            last_epoch = epoch if last_epoch is None else max(last_epoch, epoch)
            target = {
                "csv_row_index": row_idx,
                "csv_frame_time": row.get("frame.time", ""),
                "csv_timestamp_epoch": f"{epoch:.6f}",
                "exact_csv_label": label,
            }
            targets[timestamp_key(epoch)].append(target)
    exact_target_count = sum(len(v) for v in targets.values())
    meta = {
        "csv_member": csv_member,
        "planned_start_row": min_start,
        "planned_end_row": max_end,
        "planned_rows": sum((e - s + 1) for s, e in starts_ends),
        "segment_count": len(segments),
        "allowed_exact_label": allowed,
        "csv_rows_scanned": scanned,
        "csv_label_counts": dict(sorted(label_counts.items())),
        "csv_time_parse_failures": parse_failures,
        "exact_target_count": exact_target_count,
        "target_first_epoch": first_epoch,
        "target_last_epoch": last_epoch,
    }
    return targets, meta


def candidate_list(chunk: dict[str, str]) -> list[str]:
    values: list[str] = []
    preferred = chunk.get("preferred_pcap_candidate", "").strip()
    if preferred:
        values.append(preferred)
    for item in chunk.get("all_pcap_candidates", "").split("|"):
        item = item.strip()
        if item and item not in values:
            values.append(item)
    return values


def pcap_time_range(zf: zipfile.ZipFile, member: str, max_packets: int | None = None) -> dict[str, Any]:
    first = None
    last = None
    packets = 0
    with zf.open(member, "r") as raw:
        reader = dpkt.pcap.Reader(io.BufferedReader(raw))
        for ts, _buf in reader:
            if first is None:
                first = float(ts)
            last = float(ts)
            packets += 1
            if max_packets is not None and packets >= max_packets:
                break
    return {"pcap_member": member, "first_epoch": first, "last_epoch": last, "packets_scanned_for_range": packets}


def choose_pcap(zf: zipfile.ZipFile, chunk: dict[str, str], target_meta: dict[str, Any]) -> tuple[str | None, list[dict[str, Any]]]:
    target_first = target_meta.get("target_first_epoch")
    target_last = target_meta.get("target_last_epoch")
    ranges: list[dict[str, Any]] = []
    if target_first is None or target_last is None:
        return None, ranges
    best_member = None
    best_overlap = -1.0
    for member in candidate_list(chunk):
        if member not in zf.namelist():
            ranges.append({"pcap_member": member, "status": "missing_in_zip"})
            continue
        try:
            rng = pcap_time_range(zf, member)
        except Exception as exc:
            ranges.append({"pcap_member": member, "status": "range_error", "error": str(exc)})
            continue
        p_first = rng["first_epoch"]
        p_last = rng["last_epoch"]
        if p_first is None or p_last is None:
            rng["status"] = "empty_pcap"
            rng["overlap_seconds"] = 0
        else:
            overlap = max(0.0, min(float(p_last), float(target_last)) - max(float(p_first), float(target_first)))
            rng["overlap_seconds"] = overlap
            rng["status"] = "overlap" if overlap > 0 else "no_overlap"
            if overlap > best_overlap:
                best_overlap = overlap
                best_member = member
        ranges.append(rng)
    if best_overlap <= 0:
        return None, ranges
    return best_member, ranges


def run_chunk(chunk_id: int, force: bool = False, max_seconds: float | None = None) -> dict[str, Any]:
    chunk_path = CHUNK_PLAN_DIR / f"chunk_{chunk_id:05d}.csv"
    if not chunk_path.exists():
        raise FileNotFoundError(f"missing chunk plan: {chunk_path}")
    segments = read_csv(chunk_path)
    chunk = segments[0]
    chunk_out_prefix = CACHE_DIR / f"chunk_{chunk_id:05d}"
    meta_path = chunk_out_prefix.with_suffix(".meta.json")
    if meta_path.exists() and not force:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        print(json.dumps({"chunk_id": chunk_id, "status": "already_complete", "meta": meta}, indent=2))
        return meta
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
    start_time = time.monotonic()
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        targets, target_meta = scan_csv_targets(zf, segments)
        if target_meta["exact_target_count"] <= 0:
            meta = {
                "chunk_id": chunk_id,
                "status": "quarantined_no_exact_csv_targets",
                "target_meta": target_meta,
                "chunk": chunk,
            }
            write_json(QUARANTINE_DIR / f"chunk_{chunk_id:05d}.meta.json", meta)
            print(json.dumps(meta, indent=2))
            return meta
        pcap_member, pcap_ranges = choose_pcap(zf, chunk, target_meta)
        if pcap_member is None:
            meta = {
                "chunk_id": chunk_id,
                "status": "quarantined_no_pcap_time_overlap",
                "target_meta": target_meta,
                "pcap_ranges": pcap_ranges,
                "chunk": chunk,
            }
            write_json(QUARANTINE_DIR / f"chunk_{chunk_id:05d}.meta.json", meta)
            print(json.dumps(meta, indent=2))
            return meta
        nstat = load_train_state()
        state_before, state_hash_before_status = safe_state_hash(nstat)
        vectors: list[np.ndarray] = []
        y: list[int] = []
        sidecar: list[dict[str, Any]] = []
        parse_errors = 0
        packets_scanned = 0
        unmatched_pcap_target_hits = 0
        target_total = target_meta["exact_target_count"]
        target_first = float(target_meta["target_first_epoch"])
        target_last = float(target_meta["target_last_epoch"])
        with zf.open(pcap_member, "r") as raw:
            reader = dpkt.pcap.Reader(io.BufferedReader(raw))
            for packet_index, (ts, buf) in enumerate(reader):
                packets_scanned += 1
                if max_seconds is not None and (time.monotonic() - start_time) > max_seconds:
                    break
                vec, error = update_vec(nstat, ts, buf)
                if error is not None or vec is None:
                    parse_errors += 1
                    continue
                if float(ts) < target_first - 1.0:
                    continue
                if float(ts) > target_last + 1.0 and len(vectors) >= target_total:
                    break
                target = None
                for key in timestamp_candidate_keys(float(ts)):
                    if targets.get(key):
                        target = targets[key].popleft()
                        break
                if target is None:
                    if target_first <= float(ts) <= target_last:
                        unmatched_pcap_target_hits += 1
                    continue
                vectors.append(vec)
                y.append(1)
                role = chunk["plan_role"]
                sealed = parse_bool(chunk.get("sealed_final"))
                report_only = parse_bool(chunk.get("report_only"))
                sidecar.append(
                    {
                        "chunk_id": chunk_id,
                        "role": role,
                        "split_role": role,
                        "source_contract_role": chunk.get("source_contract_role", ""),
                        "pcap_member": pcap_member,
                        "csv_member": chunk["csv_member"],
                        "pcap_packet_index": packet_index,
                        "packet_timestamp_epoch": f"{float(ts):.6f}",
                        "csv_row_index": target["csv_row_index"],
                        "csv_frame_time": target["csv_frame_time"],
                        "csv_timestamp_epoch": target["csv_timestamp_epoch"],
                        "exact_csv_label": target["exact_csv_label"],
                        "binary_label_from_alignment": "attack",
                        "attack_type": chunk["attack_type"],
                        "phase": chunk["phase"],
                        "device": chunk["device"],
                        "selection_allowed": bool_text(chunk.get("selection_allowed")),
                        "report_only": bool_text(report_only),
                        "sealed_final": bool_text(sealed),
                        "forbidden_for_fit": bool_text(sealed or parse_bool(chunk.get("forbidden_for_fit"))),
                        "forbidden_for_threshold": bool_text(sealed or parse_bool(chunk.get("forbidden_for_threshold"))),
                        "forbidden_for_model_selection": bool_text(sealed or report_only or parse_bool(chunk.get("forbidden_for_model_selection"))),
                        "materialization_rule": "exact_csv_label_and_timestamp_match",
                        "state_strategy": "train_state_then_eval_online_past_only",
                    }
                )
                if len(vectors) >= target_total:
                    break
        remaining = sum(len(v) for v in targets.values())
        x = np.vstack(vectors).astype(np.float32) if vectors else np.empty((0, 115), dtype=np.float32)
        y_arr = np.asarray(y, dtype=np.int8)
        state_after, state_hash_after_status = safe_state_hash(nstat, emitted_rows=int(x.shape[0]))
        if x.shape[0] > 0:
            np.save(chunk_out_prefix.with_name(chunk_out_prefix.name + "_X.npy"), x)
            np.save(chunk_out_prefix.with_name(chunk_out_prefix.name + "_y.npy"), y_arr)
            write_csv(chunk_out_prefix.with_name(chunk_out_prefix.name + "_sidecar.csv"), sidecar)
        finite = bool(np.isfinite(x).all()) if x.size else True
        meta = {
            "chunk_id": chunk_id,
            "status": "complete" if remaining == 0 and x.shape[0] == target_total and finite else "partial_or_unstable",
            "pcap_member": pcap_member,
            "pcap_ranges": pcap_ranges,
            "target_meta": target_meta,
            "emitted_rows": int(x.shape[0]),
            "expected_exact_rows": int(target_total),
            "missing_exact_rows": int(max(0, target_total - x.shape[0])),
            "remaining_unmatched_targets": int(remaining),
            "packets_scanned": int(packets_scanned),
            "parse_errors": int(parse_errors),
            "unmatched_pcap_target_window_packets": int(unmatched_pcap_target_hits),
            "finite": finite,
            "feature_dim": int(x.shape[1]) if x.ndim == 2 else 0,
            "state_hash_before": state_before,
            "state_hash_after": state_after,
            "state_hash_before_status": state_hash_before_status,
            "state_hash_after_status": state_hash_after_status,
            "elapsed_seconds": round(time.monotonic() - start_time, 3),
            "outputs": {
                "x": str(chunk_out_prefix.with_name(chunk_out_prefix.name + "_X.npy")),
                "y": str(chunk_out_prefix.with_name(chunk_out_prefix.name + "_y.npy")),
                "sidecar": str(chunk_out_prefix.with_name(chunk_out_prefix.name + "_sidecar.csv")),
            },
            "chunk": chunk,
        }
        write_json(meta_path, meta)
        print(json.dumps(meta, indent=2))
        return meta


def validate_mode() -> dict[str, Any]:
    if not (OUT / "chunk_manifest.csv").exists():
        raise FileNotFoundError("missing chunk_manifest.csv; run --mode build-chunks first")
    chunks = read_csv(OUT / "chunk_manifest.csv")
    rows: list[dict[str, Any]] = []
    status_counts = Counter()
    emitted_total = 0
    expected_total = 0
    missing_total = 0
    quarantined = 0
    for chunk in chunks:
        cid = int_text(chunk["chunk_id"])
        meta_path = CACHE_DIR / f"chunk_{cid:05d}.meta.json"
        quarantine_path = QUARANTINE_DIR / f"chunk_{cid:05d}.meta.json"
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        elif quarantine_path.exists():
            meta = json.loads(quarantine_path.read_text(encoding="utf-8"))
            quarantined += 1
        else:
            meta = {"status": "missing_chunk_output", "emitted_rows": 0, "expected_exact_rows": int_text(chunk["planned_rows"]), "missing_exact_rows": int_text(chunk["planned_rows"])}
        status = meta.get("status", "unknown")
        status_counts[status] += 1
        emitted = int_text(meta.get("emitted_rows"))
        expected = int_text(meta.get("expected_exact_rows", chunk.get("planned_rows")))
        missing = int_text(meta.get("missing_exact_rows", max(0, expected - emitted)))
        emitted_total += emitted
        expected_total += expected
        missing_total += missing
        rows.append(
            {
                "chunk_id": cid,
                "status": status,
                "plan_role": chunk["plan_role"],
                "attack_type": chunk["attack_type"],
                "csv_member": chunk["csv_member"],
                "planned_rows": chunk["planned_rows"],
                "expected_exact_rows": expected,
                "emitted_rows": emitted,
                "missing_exact_rows": missing,
                "quarantined": str(quarantine_path.exists()).lower(),
            }
        )
    write_csv(OUT / "chunk_validation_table.csv", rows)
    primary = (
        "exact_label_targeted_attack_materialization_complete"
        if missing_total == 0 and quarantined == 0 and status_counts.get("missing_chunk_output", 0) == 0
        else "exact_label_targeted_attack_materialization_partial_needs_alignment_review"
    )
    payload = {
        "issue": ISSUE_ID,
        "mode": "validate",
        "primary_verdict": primary,
        "chunk_count": len(chunks),
        "status_counts": dict(sorted(status_counts.items())),
        "expected_exact_rows": expected_total,
        "emitted_rows": emitted_total,
        "missing_exact_rows": missing_total,
        "quarantine_files": quarantined,
        "no_model_training": True,
    }
    write_json(OUT / "validation_summary.json", payload)
    write_md(
        OUT / "hpc_validation_report.txt",
        [
            f"issue={ISSUE_ID}",
            f"status={'PASS' if primary.endswith('_complete') else 'PARTIAL'}",
            f"primary_verdict={primary}",
            f"chunks={len(chunks)}",
            f"expected_exact_rows={expected_total}",
            f"emitted_rows={emitted_total}",
            f"missing_exact_rows={missing_total}",
            f"quarantine_files={quarantined}",
            f"status_counts={dict(sorted(status_counts.items()))}",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            f"# {ISSUE_ID}",
            "",
            f"- primary_verdict: {primary}",
            f"- expected_exact_rows: {expected_total}",
            f"- emitted_rows: {emitted_total}",
            f"- missing_exact_rows: {missing_total}",
            f"- quarantine_files: {quarantined}",
            "- model training: not performed.",
            "- materialization rule: exact CSV attack label plus timestamp match to PCAP packet.",
            "- final/report-only rows remain forbidden for fit, threshold, and model selection.",
        ],
    )
    print(json.dumps(payload, indent=2))
    return payload


def write_run_book() -> None:
    write_csv(
        OUT / "manifest.csv",
        [
            {"artifact": "plan_preflight.json", "path": str(OUT / "plan_preflight.json")},
            {"artifact": "chunk_manifest.csv", "path": str(OUT / "chunk_manifest.csv")},
            {"artifact": "chunk_validation_table.csv", "path": str(OUT / "chunk_validation_table.csv")},
            {"artifact": "hpc_validation_report.txt", "path": str(OUT / "hpc_validation_report.txt")},
        ],
    )
    (OUT / "command.txt").write_text(COMMAND_TEXT + "\n", encoding="utf-8")
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE_ID,
            "task": "Slurm exact-label targeted multi-type attack Kitsune115 materialization",
            "frontend": "Restored Kitsune/AfterImage/netStat 115D",
            "state_strategy": "train_state_then_eval_online_past_only",
            "no_model_training": True,
            "source_contract": str(PLAN_PATH),
        },
    )
    write_json(
        OUT / "config.json",
        {
            "zip_md5": ZIP_MD5,
            "default_chunk_rows": DEFAULT_CHUNK_ROWS,
            "time_tolerance_us": TIME_TOLERANCE_US,
            "train_state": str(TRAIN_STATE),
            "derived": str(DERIVED),
        },
    )


def update_mainline_docs() -> None:
    marker = "<!-- issue27cd_slurm_exact_label_targeted_multitype_attack_materialization -->"
    lines = [
        marker,
        "### issue27cd_slurm_exact_label_targeted_multitype_attack_materialization",
        "- Status: transfer/materialization script prepared for exact-label targeted multi-type attack Kitsune115 chunks.",
        "- Purpose: repair attack-side materialization using issue27cc exact-label rows; no model training or benchmark.",
        "- Key guardrail: emit only rows whose processed CSV label equals the planned attack label and whose packet timestamp matches the PCAP stream.",
        "- Current 1M benign/OOD roles remain usable; attack query/final roles require this exact-label rematerialization before model conclusions.",
        "- Next: run the Slurm transfer kit, validate missing_exact_rows/quarantine, then decide merge policy.",
    ]
    for path in [REPO / "runs" / "mainline_docs" / "mainline_handoff.md", REPO / "runs" / "mainline_docs" / "mainline_experiment_map.md"]:
        append_once(path, marker, lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["plan", "build-chunks", "run-chunk", "validate"], required=True)
    parser.add_argument("--chunk-rows", type=int, default=DEFAULT_CHUNK_ROWS)
    parser.add_argument("--chunk-id", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--max-seconds", type=float, default=None)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.mode == "plan":
        plan_mode()
        write_run_book()
        update_mainline_docs()
    elif args.mode == "build-chunks":
        build_chunks(args.chunk_rows)
        write_run_book()
        update_mainline_docs()
    elif args.mode == "run-chunk":
        chunk_id = args.chunk_id or int(os.environ.get("SLURM_ARRAY_TASK_ID", "0"))
        if chunk_id <= 0:
            raise SystemExit("missing --chunk-id or SLURM_ARRAY_TASK_ID")
        run_chunk(chunk_id, force=args.force, max_seconds=args.max_seconds)
    elif args.mode == "validate":
        validate_mode()
        write_run_book()
        update_mainline_docs()


if __name__ == "__main__":
    main()
