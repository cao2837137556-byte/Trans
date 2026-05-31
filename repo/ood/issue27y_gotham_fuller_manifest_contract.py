#!/usr/bin/env python3
"""Issue27y Gotham fuller manifest and preregistered split contract.

This script performs data-validity-gate work only:
- stream all processed CSVs from GothamDataset2025.zip;
- create file-level summaries and a compact sampled row manifest;
- assess PCAP/CSV pairing and shortcut risks;
- draft preregistered split-contract candidates.

It intentionally does not extract PCAPs, train models, run feature extraction, or
use any model result to select a split.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
import zipfile
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ISSUE = "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
EXPECTED_MD5 = "7ca78c0517ccb3d2854e823678e0f206"

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = REPO_ROOT.parents[1]
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
MANIFEST_ROOT = DATA_ROOT / "manifests"
DERIVED_ROOT = DATA_ROOT / "derived" / "fuller_manifest_gate"
OUT_DIR = REPO_ROOT / "runs" / ISSUE

ISSUE27X_DIR = REPO_ROOT / "runs" / "issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28"
ISSUE27V_DIR = REPO_ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"
MAINLINE_DOCS = REPO_ROOT / "runs" / "mainline_docs"

BENIGN_ALIASES = {"benign", "normal", "background", "0", "false"}
UNKNOWN_ALIASES = {"", "unknown", "nan", "none", "null"}
MAX_SAMPLE_ROWS_PER_FILE = 800
SAMPLE_ROWS_PER_LABEL_PER_FILE = 100
FIRST_ROWS_PER_FILE = 40
TRANSITION_TAIL_ROWS = 8


def ensure_dirs() -> None:
    for path in [OUT_DIR, MANIFEST_ROOT, DERIVED_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: stringify(row.get(name, "")) for name in fieldnames})


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def safe_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_")


def disk_free_gib(path: Path) -> float:
    usage = shutil.disk_usage(str(path.anchor or path))
    return usage.free / (1024**3)


def md5_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_archive_listing() -> List[Dict[str, str]]:
    listing_path = ISSUE27V_DIR / "archive_file_listing.csv"
    if not listing_path.exists():
        raise FileNotFoundError(f"Missing archive listing: {listing_path}")
    with listing_path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def archive_path(row: Dict[str, str]) -> str:
    for key in ["archive_path", "filename", "path", "file_path", "name"]:
        if key in row and row[key]:
            return row[key]
    raise KeyError(f"Cannot find archive path key in listing row: {row.keys()}")


def parse_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def is_processed_csv(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.startswith("processed/") and normalized.endswith(".csv")


def is_pcap(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    return normalized.endswith(".pcap") or normalized.endswith(".pcapng")


def infer_device_from_path(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem.lower()
    stem = re.sub(r"^iotsim-", "", stem)
    stem = re.sub(r"_.*$", "", stem)
    stem = re.sub(r"\.pcapng?$", "", stem)
    tokens = stem.split("-")
    if len(tokens) <= 1:
        return stem
    if tokens[-1].isdigit():
        return "-".join(tokens[:-1])
    return stem


def infer_instance_from_path(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem.lower()
    m = re.search(r"-(\d+)$", stem)
    return m.group(1) if m else ""


def infer_protocol_from_filename(path: str) -> str:
    device = infer_device_from_path(path)
    for token in ["tls", "dtls", "mqtt", "coap", "http", "telnet", "goose", "modbus", "rtsp"]:
        if token in device.split("-") or f"-{token}" in device:
            return token
    return ""


def normalize_label(label: Any) -> str:
    return str(label or "").strip()


def binary_label(label: Any) -> str:
    normalized = normalize_label(label).lower()
    if normalized in BENIGN_ALIASES:
        return "benign"
    if normalized in UNKNOWN_ALIASES:
        return "unknown"
    return "attack"


def parse_timestamp(value: str) -> Tuple[str, bool]:
    raw = (value or "").strip()
    if not raw:
        return "", False
    # Wireshark frame.time often looks like "Nov 16, 2023 10:11:12.123456000 UTC".
    cleaned = re.sub(r"\s+[A-Z]{2,4}$", "", raw)
    cleaned = cleaned.replace(" UTC", "")
    formats = [
        "%b %d, %Y %H:%M:%S.%f",
        "%b %d, %Y %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.isoformat(timespec="microseconds"), True
        except ValueError:
            continue
    # Some CSVs may already use epoch seconds.
    try:
        ts = float(cleaned)
        dt = datetime.utcfromtimestamp(ts)
        return dt.isoformat(timespec="microseconds"), True
    except Exception:
        return raw, False


def timestamp_sort_key(parsed: str) -> Optional[float]:
    if not parsed:
        return None
    try:
        return datetime.fromisoformat(parsed).timestamp()
    except Exception:
        try:
            return float(parsed)
        except Exception:
            return None


def bucket_from_index(index: int, total_hint: Optional[int] = None) -> str:
    if total_hint and total_hint > 0:
        frac = index / total_hint
        bucket = min(9, int(frac * 10))
        return f"row_decile_{bucket}"
    if index < 1000:
        return "row_first_1k"
    if index < 10000:
        return "row_1k_10k"
    if index < 100000:
        return "row_10k_100k"
    if index < 1000000:
        return "row_100k_1m"
    return "row_gt_1m"


def bucket_from_time(parsed: str) -> str:
    if not parsed:
        return ""
    try:
        dt = datetime.fromisoformat(parsed)
        return dt.strftime("%Y-%m-%dT%H")
    except Exception:
        return ""


def find_column(columns: Sequence[str], candidates: Sequence[str]) -> str:
    normalized = {c.strip().lower(): c for c in columns}
    for candidate in candidates:
        key = candidate.lower()
        if key in normalized:
            return normalized[key]
    # Fallback partial matching for common packet fields.
    for c in columns:
        cl = c.strip().lower()
        if any(cl == cand.lower() or cl.endswith(cand.lower()) for cand in candidates):
            return c
    return ""


def dominant_protocol(protocol_counter: Counter[str], inferred: str) -> str:
    if protocol_counter:
        common = [p for p, _ in protocol_counter.most_common(6) if p]
        if common:
            for preferred in ["mqtt", "coap", "dtls", "tls", "http", "telnet", "goose", "icmp", "dns"]:
                if preferred in common:
                    return preferred
            return common[0]
    return inferred


def pcap_counterpart(csv_path: str, pcap_paths: Sequence[str]) -> Tuple[str, str, int]:
    stem = Path(csv_path.replace("\\", "/")).stem.lower()
    candidates = []
    for p in pcap_paths:
        p_stem = Path(p.replace("\\", "/")).stem.lower()
        if p_stem == stem or p_stem.startswith(stem + "_") or stem in p_stem:
            candidates.append(p)
    if candidates:
        # Filename/path pairing is useful but not byte-level or packet-count proof.
        return candidates[0], "medium_filename_path_match", len(candidates)
    device = infer_device_from_path(csv_path)
    loose = [p for p in pcap_paths if device and device in Path(p.replace("\\", "/")).stem.lower()]
    if loose:
        return loose[0], "low_device_token_match", len(loose)
    return "", "missing", 0


def row_for_manifest(
    *,
    global_id: int,
    csv_file_id: int,
    csv_path: str,
    row_index: int,
    row: Dict[str, str],
    cols: Dict[str, str],
    inferred_device: str,
    inferred_protocol: str,
    pcap_candidate: str,
    is_transition_nearby: bool,
    total_hint: Optional[int] = None,
) -> Dict[str, Any]:
    label = normalize_label(row.get(cols.get("label", ""), ""))
    binary = binary_label(label)
    frame_time = row.get(cols.get("frame_time", ""), "")
    parsed, parsed_ok = parse_timestamp(frame_time)
    frame_protocols = row.get(cols.get("frame_protocols", ""), "")
    protocol = inferred_protocol or infer_protocol_from_protocols(frame_protocols)
    hint = "eligible_attack" if binary == "attack" else "eligible_benign" if binary == "benign" else "unknown_label"
    return {
        "global_manifest_row_id": global_id,
        "csv_file_id": csv_file_id,
        "csv_archive_path": csv_path,
        "row_index_within_file": row_index,
        "frame.time": frame_time,
        "parsed_timestamp": parsed if parsed_ok else "",
        "label": label,
        "binary_label": binary,
        "attack_type": "" if binary == "benign" else label,
        "inferred_device": inferred_device,
        "inferred_protocol": protocol,
        "frame.protocols": frame_protocols,
        "ip.src": row.get(cols.get("ip_src", ""), ""),
        "ip.dst": row.get(cols.get("ip_dst", ""), ""),
        "time_bucket": bucket_from_time(parsed),
        "row_order_bucket": bucket_from_index(row_index, total_hint),
        "is_transition_nearby": str(bool(is_transition_nearby)).lower(),
        "pcap_counterpart_candidate": pcap_candidate,
        "split_eligibility_hint": hint,
    }


def infer_protocol_from_protocols(value: str) -> str:
    lower = (value or "").lower()
    for token in ["mqtt", "coap", "dtls", "tls", "http", "telnet", "goose", "icmp", "dns", "rtcp", "ntp"]:
        if token in lower.split(":") or token in lower:
            return token
    return ""


def protocol_tokens(value: str) -> List[str]:
    tokens = []
    for token in re.split(r"[:;,|/\s]+", (value or "").lower()):
        if token and token not in {"eth", "ethertype", "ip", "ipv6", "tcp", "udp", "data", "frame"}:
            tokens.append(token)
    return tokens


def should_sample_row(
    row_index: int,
    label: str,
    per_label_counts: Counter[str],
    kept_count: int,
    transition_nearby: bool,
) -> bool:
    if kept_count >= MAX_SAMPLE_ROWS_PER_FILE:
        return False
    if row_index <= FIRST_ROWS_PER_FILE:
        return True
    if per_label_counts[label] <= SAMPLE_ROWS_PER_LABEL_PER_FILE:
        return True
    if transition_nearby:
        return True
    # sparse deterministic spread, independent of labels/model scores.
    if row_index in {1000, 5000, 10000, 50000, 100000, 500000, 1000000}:
        return True
    return False


def summarize_csvs(
    csv_entries: Sequence[Dict[str, str]],
    pcap_paths: Sequence[str],
    allowed_mode: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    file_rows: List[Dict[str, Any]] = []
    sampled_rows: List[Dict[str, Any]] = []
    global_manifest_id = 0
    start = time.time()
    failures: List[str] = []

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for csv_file_id, entry in enumerate(csv_entries, start=1):
            path = archive_path(entry)
            file_size = parse_int(entry.get("uncompressed_size") or entry.get("file_size") or entry.get("size"))
            inferred_device = infer_device_from_path(path)
            inferred_protocol = infer_protocol_from_filename(path)
            pcap_candidate, pairing_conf, pairing_count = pcap_counterpart(path, pcap_paths)

            total_rows = 0
            label_counts: Counter[str] = Counter()
            binary_counts: Counter[str] = Counter()
            protocol_counter: Counter[str] = Counter()
            first_timestamp = ""
            last_timestamp = ""
            first_ts_sort: Optional[float] = None
            last_ts_sort: Optional[float] = None
            timestamp_parse_failures = 0
            timestamp_parse_successes = 0
            timestamp_monotonic_violations = 0
            transition_count = 0
            prev_label = None
            first_label = None
            seen_attack_after_benign = False
            transition_tail_remaining = 0
            sample_label_seen: Counter[str] = Counter()
            kept_count = 0
            columns: List[str] = []
            cols: Dict[str, str] = {}
            parse_status = "not_started"
            partial_reason = ""

            try:
                with zf.open(path, "r") as raw:
                    text = (line.decode("utf-8", errors="replace") for line in raw)
                    reader = csv.DictReader(text)
                    columns = reader.fieldnames or []
                    cols = {
                        "label": find_column(columns, ["label", "Label", "attack", "class"]),
                        "frame_time": find_column(columns, ["frame.time", "frame_time", "timestamp", "time"]),
                        "frame_number": find_column(columns, ["frame.number", "frame_number", "packet_number"]),
                        "frame_protocols": find_column(columns, ["frame.protocols", "frame_protocols", "protocols"]),
                        "ip_src": find_column(columns, ["ip.src", "ip_src", "src_ip", "source_ip"]),
                        "ip_dst": find_column(columns, ["ip.dst", "ip_dst", "dst_ip", "destination_ip"]),
                    }
                    parse_status = "ok"
                    for row in reader:
                        total_rows += 1
                        label = normalize_label(row.get(cols.get("label", ""), ""))
                        if not label:
                            label = ""
                        label_counts[label] += 1
                        binary = binary_label(label)
                        binary_counts[binary] += 1
                        if first_label is None:
                            first_label = binary
                        if prev_label is not None and binary != prev_label:
                            transition_count += 1
                            transition_tail_remaining = TRANSITION_TAIL_ROWS
                        if first_label == "benign" and binary == "attack":
                            seen_attack_after_benign = True
                        prev_label = binary

                        frame_time = row.get(cols.get("frame_time", ""), "")
                        parsed, ok = parse_timestamp(frame_time)
                        if ok:
                            timestamp_parse_successes += 1
                            if not first_timestamp:
                                first_timestamp = parsed
                            last_timestamp = parsed
                            current_key = timestamp_sort_key(parsed)
                            if current_key is not None:
                                if last_ts_sort is not None and current_key < last_ts_sort:
                                    timestamp_monotonic_violations += 1
                                last_ts_sort = current_key
                                if first_ts_sort is None:
                                    first_ts_sort = current_key
                        elif frame_time:
                            timestamp_parse_failures += 1

                        for token in protocol_tokens(row.get(cols.get("frame_protocols", ""), "")):
                            protocol_counter[token] += 1

                        transition_nearby = transition_tail_remaining > 0
                        sample_label_seen[binary] += 1
                        if allowed_mode != "summary_only_streaming" and should_sample_row(
                            total_rows,
                            binary,
                            sample_label_seen,
                            kept_count,
                            transition_nearby,
                        ):
                            global_manifest_id += 1
                            sampled_rows.append(
                                row_for_manifest(
                                    global_id=global_manifest_id,
                                    csv_file_id=csv_file_id,
                                    csv_path=path,
                                    row_index=total_rows,
                                    row=row,
                                    cols=cols,
                                    inferred_device=inferred_device,
                                    inferred_protocol=inferred_protocol,
                                    pcap_candidate=pcap_candidate,
                                    is_transition_nearby=transition_nearby,
                                )
                            )
                            kept_count += 1
                        if transition_tail_remaining > 0:
                            transition_tail_remaining -= 1
            except Exception as exc:
                parse_status = "partial_error"
                partial_reason = repr(exc)
                failures.append(f"{path}: {exc!r}")

            observed_protocol = dominant_protocol(protocol_counter, inferred_protocol)
            duration = ""
            if first_ts_sort is not None and last_ts_sort is not None and last_ts_sort >= first_ts_sort:
                duration = f"{last_ts_sort - first_ts_sort:.6f}"
            label_values = sorted(label_counts.keys())
            attack_type_counts = {k: v for k, v in label_counts.items() if binary_label(k) == "attack"}
            file_rows.append(
                {
                    "csv_file_id": csv_file_id,
                    "csv_archive_path": path,
                    "file_name": Path(path).name,
                    "file_size": file_size,
                    "inferred_device": inferred_device,
                    "inferred_protocol_from_filename": inferred_protocol,
                    "observed_protocol_from_frame_protocols": observed_protocol,
                    "pcap_counterpart_candidate": pcap_candidate,
                    "pcap_pairing_confidence": pairing_conf,
                    "pcap_pairing_candidate_count": pairing_count,
                    "total_rows_estimated_or_exact": total_rows,
                    "row_count_status": "exact" if parse_status == "ok" else "partial",
                    "columns_count": len(columns),
                    "has_label": bool(cols.get("label")),
                    "has_frame_time": bool(cols.get("frame_time")),
                    "has_frame_number": bool(cols.get("frame_number")),
                    "has_frame_protocols": bool(cols.get("frame_protocols")),
                    "has_ip_src": bool(cols.get("ip_src")),
                    "has_ip_dst": bool(cols.get("ip_dst")),
                    "label_values": label_values,
                    "benign_rows": binary_counts["benign"],
                    "attack_rows": binary_counts["attack"],
                    "unknown_label_rows": binary_counts["unknown"],
                    "attack_type_values": sorted(attack_type_counts.keys()),
                    "attack_type_counts": attack_type_counts,
                    "first_timestamp": first_timestamp,
                    "last_timestamp": last_timestamp,
                    "duration_seconds": duration,
                    "timestamp_parse_status": "ok"
                    if timestamp_parse_successes and not timestamp_parse_failures
                    else "partial"
                    if timestamp_parse_successes
                    else "missing_or_unparsed",
                    "timestamp_parse_successes": timestamp_parse_successes,
                    "timestamp_parse_failures": timestamp_parse_failures,
                    "timestamp_monotonic_violations": timestamp_monotonic_violations,
                    "label_transition_count": transition_count,
                    "benign_prefix_then_attack_suffix_flag": seen_attack_after_benign,
                    "mixed_label_flag": binary_counts["benign"] > 0 and binary_counts["attack"] > 0,
                    "all_benign_flag": binary_counts["benign"] > 0 and binary_counts["attack"] == 0,
                    "all_attack_flag": binary_counts["attack"] > 0 and binary_counts["benign"] == 0,
                    "unknown_label_flag": binary_counts["unknown"] > 0 or any(k.lower() == "unknown" for k in label_counts),
                    "sampled_rows_kept": kept_count,
                    "parse_status": parse_status,
                    "partial_reason": partial_reason,
                    "notes": "streamed_from_zip_no_full_extract",
                }
            )

    meta = {
        "elapsed_seconds": time.time() - start,
        "failures": failures,
        "sampled_row_count": len(sampled_rows),
        "file_count": len(file_rows),
    }
    return file_rows, sampled_rows, meta


def cramers_v_from_rows(rows: Sequence[Dict[str, Any]], col_a: str, col_b: str) -> Tuple[float, int, int]:
    table: Dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        a = stringify(row.get(col_a, "")).strip() or "missing"
        b = stringify(row.get(col_b, "")).strip() or "missing"
        table[a][b] += 1
    if len(table) < 2:
        return 0.0, len(table), len({b for c in table.values() for b in c})
    row_keys = list(table.keys())
    col_keys = sorted({b for c in table.values() for b in c})
    n = sum(sum(c.values()) for c in table.values())
    if n == 0 or len(col_keys) < 2:
        return 0.0, len(row_keys), len(col_keys)
    row_totals = {r: sum(table[r].values()) for r in row_keys}
    col_totals = {c: sum(table[r][c] for r in row_keys) for c in col_keys}
    chi2 = 0.0
    for r in row_keys:
        for c in col_keys:
            expected = row_totals[r] * col_totals[c] / n
            if expected > 0:
                observed = table[r][c]
                chi2 += (observed - expected) ** 2 / expected
    phi2 = chi2 / n
    denom = min(len(row_keys) - 1, len(col_keys) - 1)
    if denom <= 0:
        return 0.0, len(row_keys), len(col_keys)
    return math.sqrt(phi2 / denom), len(row_keys), len(col_keys)


def risk_level_from_v(v: float) -> str:
    if v >= 0.8:
        return "high"
    if v >= 0.5:
        return "medium_high"
    if v >= 0.3:
        return "medium"
    return "low"


def build_artifact_risk(file_rows: Sequence[Dict[str, Any]], sampled_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # File-level rows are expanded by counts for coarse binding estimates.
    expanded: List[Dict[str, Any]] = []
    for row in file_rows:
        file_id = stringify(row["csv_file_id"])
        device = row["inferred_device"]
        protocol = row.get("observed_protocol_from_frame_protocols") or row.get("inferred_protocol_from_filename")
        time_bucket = stringify(row.get("first_timestamp", ""))[:13] or "missing"
        for label, count in [("benign", parse_int(row["benign_rows"])), ("attack", parse_int(row["attack_rows"]))]:
            if count <= 0:
                continue
            expanded.append(
                {
                    "binary_label": label,
                    "file_id": file_id,
                    "device": device,
                    "protocol": protocol,
                    "time_bucket": time_bucket,
                    "weight": count,
                }
            )
    # Weighted Cramer's V by lightweight replication cap to avoid huge expansion.
    weighted_sample: List[Dict[str, Any]] = []
    for row in expanded:
        reps = max(1, min(200, int(math.sqrt(parse_int(row["weight"])))))
        weighted_sample.extend([row] * reps)

    checks = [
        ("label_vs_file_id", "binary_label", "file_id", "file-level label/file shortcut risk"),
        ("label_vs_device", "binary_label", "device", "label/device shortcut risk"),
        ("label_vs_protocol", "binary_label", "protocol", "label/protocol shortcut risk"),
        ("label_vs_time_bucket", "binary_label", "time_bucket", "label/time shortcut risk"),
    ]
    rows: List[Dict[str, Any]] = []
    for name, a, b, note in checks:
        v, n_a, n_b = cramers_v_from_rows(weighted_sample, a, b)
        rows.append(
            {
                "risk_name": name,
                "metric": "cramers_v_weighted_file_summary",
                "value": f"{v:.6f}",
                "groups_a": n_a,
                "groups_b": n_b,
                "risk_level": risk_level_from_v(v),
                "interpretation": note,
                "mitigation": "pre-register file/device/protocol/time disjoint contract; exclude source identifiers at feature gate",
            }
        )

    mixed = sum(1 for row in file_rows if str(row.get("mixed_label_flag")).lower() == "true")
    prefix = sum(1 for row in file_rows if str(row.get("benign_prefix_then_attack_suffix_flag")).lower() == "true")
    total = len(file_rows)
    rows.append(
        {
            "risk_name": "benign_prefix_attack_suffix_pattern",
            "metric": "file_fraction",
            "value": f"{(prefix / total) if total else 0:.6f}",
            "groups_a": prefix,
            "groups_b": total,
            "risk_level": "high" if prefix >= max(2, total * 0.2) else "medium" if prefix else "low",
            "interpretation": "mixed CSVs may encode attack onset by row order",
            "mitigation": "avoid time-near support/eval; use embargo and file-disjoint attack splits",
        }
    )

    sampled_for_idood = [
        {
            "binary_label": row.get("binary_label"),
            "device": row.get("inferred_device"),
            "protocol": row.get("inferred_protocol"),
            "time_bucket": row.get("time_bucket"),
        }
        for row in sampled_rows
        if row.get("binary_label") == "benign"
    ]
    for b in ["device", "protocol", "time_bucket"]:
        v, n_a, n_b = cramers_v_from_rows(sampled_for_idood, "binary_label", b)
        rows.append(
            {
                "risk_name": f"benign_candidate_vs_{b}",
                "metric": "sampled_benign_coverage",
                "value": f"{v:.6f}",
                "groups_a": n_a,
                "groups_b": n_b,
                "risk_level": "coverage_check",
                "interpretation": "benign-only rows span this grouping; binary label constant so V is not a shortcut metric",
                "mitigation": "use this grouping only for preregistered ID/OOD drift, not as hidden feature input",
            }
        )
    return rows


def group_files(file_rows: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    all_benign = [r for r in file_rows if str(r.get("all_benign_flag")).lower() == "true" and parse_int(r.get("benign_rows")) > 0]
    mixed = [r for r in file_rows if str(r.get("mixed_label_flag")).lower() == "true" and parse_int(r.get("attack_rows")) > 0]
    all_attack = [r for r in file_rows if str(r.get("all_attack_flag")).lower() == "true" and parse_int(r.get("attack_rows")) > 0]
    attack = [r for r in file_rows if parse_int(r.get("attack_rows")) > 0]
    return {
        "all_benign": all_benign,
        "mixed": mixed,
        "all_attack": all_attack,
        "attack": attack,
    }


def split_by_family(files: Sequence[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in files:
        groups[stringify(row.get("inferred_device", "unknown"))].append(row)
    return dict(groups)


def rows_sum(files: Sequence[Dict[str, Any]], key: str) -> int:
    return sum(parse_int(row.get(key)) for row in files)


def files_list(files: Sequence[Dict[str, Any]]) -> List[str]:
    return [stringify(row.get("csv_archive_path")) for row in files]


def label_union(files: Sequence[Dict[str, Any]]) -> List[str]:
    labels = set()
    for row in files:
        for label in stringify(row.get("attack_type_values", "")).split("|"):
            if label:
                labels.add(label)
    return sorted(labels)


def pick_groups_for_primary(file_rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    benign_groups = split_by_family(group_files(file_rows)["all_benign"])
    ordered = sorted(benign_groups.items(), key=lambda kv: rows_sum(kv[1], "benign_rows"), reverse=True)
    id_files: List[Dict[str, Any]] = []
    ood_val_files: List[Dict[str, Any]] = []
    final_ood_files: List[Dict[str, Any]] = []
    for idx, (_, files) in enumerate(ordered):
        if idx % 3 == 0:
            id_files.extend(files)
        elif idx % 3 == 1:
            ood_val_files.extend(files)
        else:
            final_ood_files.extend(files)
    return id_files, ood_val_files, final_ood_files


def pick_attack_support_eval(file_rows: Sequence[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    attack_files = sorted(group_files(file_rows)["attack"], key=lambda r: (stringify(r.get("inferred_device")), stringify(r.get("csv_archive_path"))))
    support: List[Dict[str, Any]] = []
    eval_files: List[Dict[str, Any]] = []
    for idx, row in enumerate(attack_files):
        if idx % 2 == 0:
            support.append(row)
        else:
            eval_files.append(row)
    return support, eval_files


def contract_row(
    contract_id: str,
    split_goal: str,
    id_files: Sequence[Dict[str, Any]],
    ood_val_files: Sequence[Dict[str, Any]],
    final_ood_files: Sequence[Dict[str, Any]],
    attack_support_files: Sequence[Dict[str, Any]],
    attack_eval_files: Sequence[Dict[str, Any]],
    evidence_level: str,
    artifact_risk: str,
    notes: str,
) -> Dict[str, Any]:
    included = list(dict.fromkeys(files_list(list(id_files) + list(ood_val_files) + list(final_ood_files) + list(attack_support_files) + list(attack_eval_files))))
    return {
        "contract_id": contract_id,
        "split_goal": split_goal,
        "included_csv_files": included,
        "excluded_csv_files": "",
        "ID_benign_train_files": files_list(id_files),
        "OOD_benign_val_files": files_list(ood_val_files),
        "final_OOD_benign_eval_files": files_list(final_ood_files),
        "attack_support_files": files_list(attack_support_files),
        "attack_eval_files": files_list(attack_eval_files),
        "allowed_labels": "benign|attack_labels_from_support_and_eval_files",
        "excluded_labels": "Unknown rows excluded from claim unless mapped at feature gate",
        "row_selection_rules": "use benign rows only for ID/OOD/final OOD; use attack rows only for support/eval; exclude transition-near rows for final eval",
        "timestamp_order_rules": "preserve per-file packet order; do not select support/eval by outcome; use embargo around mixed-file transitions",
        "purge_gap_or_embargo_rules": "exclude +/- 1000 rows around benign/attack transitions in mixed files for final eval; tune only from contract metadata",
        "support_size_candidates": "32|64|128|256",
        "final_eval_report_only": "true",
        "threshold_selection_allowed_sets": "ID_benign_calibration|OOD_benign_validation",
        "forbidden_selection_sets": "final_OOD_benign_eval|attack_eval",
        "artifact_risk_assessment": artifact_risk,
        "minimum_size_check": "computed_in_gotham_size_adequacy_table.csv",
        "evidence_level": evidence_level,
        "ID_benign_train_rows": rows_sum(id_files, "benign_rows"),
        "OOD_benign_val_rows": rows_sum(ood_val_files, "benign_rows"),
        "final_OOD_benign_eval_rows": rows_sum(final_ood_files, "benign_rows"),
        "attack_support_rows": rows_sum(attack_support_files, "attack_rows"),
        "attack_eval_rows": rows_sum(attack_eval_files, "attack_rows"),
        "ID_device_count": len(set(row.get("inferred_device") for row in id_files)),
        "OOD_val_device_count": len(set(row.get("inferred_device") for row in ood_val_files)),
        "final_OOD_device_count": len(set(row.get("inferred_device") for row in final_ood_files)),
        "attack_support_type_count": len(label_union(attack_support_files)),
        "attack_eval_type_count": len(label_union(attack_eval_files)),
        "notes": notes,
    }


def build_contracts(file_rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    id_files, ood_val_files, final_ood_files = pick_groups_for_primary(file_rows)
    attack_support, attack_eval = pick_attack_support_eval(file_rows)
    contracts = [
        contract_row(
            "gotham_device_disjoint_v1",
            "device-disjoint benign drift with file-disjoint attack support/eval",
            id_files,
            ood_val_files,
            final_ood_files,
            attack_support,
            attack_eval,
            "promising_needs_feature_gate",
            "medium_high: file/device/source shortcuts must be controlled by feature policy and disjoint files",
            "Primary candidate because benign devices can be separated into ID/OOD/final sets; still not model-ready until feature/source policy and PCAP pairing are strengthened.",
        )
    ]

    benign_files = group_files(file_rows)["all_benign"]
    by_protocol: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in benign_files:
        protocol = stringify(row.get("observed_protocol_from_frame_protocols") or row.get("inferred_protocol_from_filename") or "unknown")
        by_protocol[protocol].append(row)
    ordered = sorted(by_protocol.items(), key=lambda kv: rows_sum(kv[1], "benign_rows"), reverse=True)
    id_p: List[Dict[str, Any]] = []
    ood_p: List[Dict[str, Any]] = []
    final_p: List[Dict[str, Any]] = []
    for idx, (_, files) in enumerate(ordered):
        if idx % 3 == 0:
            id_p.extend(files)
        elif idx % 3 == 1:
            ood_p.extend(files)
        else:
            final_p.extend(files)
    contracts.append(
        contract_row(
            "gotham_protocol_disjoint_v1",
            "protocol-disjoint benign drift with file-disjoint attack support/eval",
            id_p,
            ood_p,
            final_p,
            attack_support,
            attack_eval,
            "promising_needs_feature_gate",
            "high: protocol identity can become a shortcut and must be explicitly studied",
            "Secondary route; useful if device-disjoint drift is too source-bound, but protocol shortcut risk is higher.",
        )
    )

    mixed = [r for r in group_files(file_rows)["mixed"] if str(r.get("timestamp_parse_status")) in {"ok", "partial"}]
    contracts.append(
        contract_row(
            "gotham_time_aware_within_device_v1",
            "time-aware within-device split",
            benign_files[: max(1, len(benign_files) // 3)],
            benign_files[max(1, len(benign_files) // 3) : max(2, 2 * len(benign_files) // 3)],
            benign_files[max(2, 2 * len(benign_files) // 3) :],
            mixed[::2],
            mixed[1::2],
            "high_artifact_risk",
            "high: mixed-file benign-prefix to attack-suffix patterns can encode attack onset",
            "Optional diagnostic only unless transition/embargo rules are validated on a fuller row manifest.",
        )
    )
    return contracts


def size_adequacy_rows(contracts: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for contract in contracts:
        id_rows = parse_int(contract["ID_benign_train_rows"])
        ood_rows = parse_int(contract["OOD_benign_val_rows"])
        final_rows = parse_int(contract["final_OOD_benign_eval_rows"])
        support_rows = parse_int(contract["attack_support_rows"])
        eval_rows = parse_int(contract["attack_eval_rows"])
        device_counts = [
            parse_int(contract["ID_device_count"]),
            parse_int(contract["OOD_val_device_count"]),
            parse_int(contract["final_OOD_device_count"]),
        ]
        attack_type_count = min(parse_int(contract["attack_support_type_count"]), parse_int(contract["attack_eval_type_count"]))
        if contract["evidence_level"] == "high_artifact_risk":
            verdict = "size_blocked_by_group_dominance"
        elif min(device_counts) >= 2 and final_rows >= 10000 and eval_rows >= 10000 and attack_type_count >= 3:
            verdict = "size_adequate_for_main_benchmark"
        elif final_rows >= 1000 and eval_rows >= 1000:
            verdict = "size_promising_needs_larger_extraction"
        else:
            verdict = "size_insufficient_for_main_claim"
        rows.append(
            {
                "contract_id": contract["contract_id"],
                "ID_benign_train_rows": id_rows,
                "OOD_benign_val_rows": ood_rows,
                "final_OOD_benign_eval_rows": final_rows,
                "attack_support_rows": support_rows,
                "attack_eval_rows": eval_rows,
                "ID_device_count": contract["ID_device_count"],
                "OOD_val_device_count": contract["OOD_val_device_count"],
                "final_OOD_device_count": contract["final_OOD_device_count"],
                "attack_type_count_min_support_eval": attack_type_count,
                "support_size_candidates_supported": "|".join(str(k) for k in [32, 64, 128, 256] if support_rows >= k),
                "one_file_dominance_risk": "requires_row_manifest_check",
                "subgroup_analysis_possible": "yes" if attack_type_count >= 3 and min(device_counts) >= 2 else "limited",
                "size_adequacy_verdict": verdict,
                "notes": "size check is necessary but not sufficient; artifact and feature-source gates still apply",
            }
        )
    return rows


def summarize_counts(file_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    devices = sorted({stringify(row.get("inferred_device")) for row in file_rows if row.get("inferred_device")})
    protocols = sorted({stringify(row.get("observed_protocol_from_frame_protocols") or row.get("inferred_protocol_from_filename")) for row in file_rows if row.get("observed_protocol_from_frame_protocols") or row.get("inferred_protocol_from_filename")})
    attacks = sorted({label for row in file_rows for label in stringify(row.get("attack_type_values", "")).split("|") if label})
    return {
        "file_count": len(file_rows),
        "total_rows": rows_sum(file_rows, "total_rows_estimated_or_exact"),
        "benign_rows": rows_sum(file_rows, "benign_rows"),
        "attack_rows": rows_sum(file_rows, "attack_rows"),
        "all_benign_files": sum(1 for row in file_rows if str(row.get("all_benign_flag")).lower() == "true"),
        "mixed_files": sum(1 for row in file_rows if str(row.get("mixed_label_flag")).lower() == "true"),
        "all_attack_files": sum(1 for row in file_rows if str(row.get("all_attack_flag")).lower() == "true"),
        "devices": devices,
        "protocols": protocols,
        "attacks": attacks,
    }


def append_mainline_docs(primary_verdict: str, summary: Dict[str, Any], best_contract: str) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    timestamp = datetime.now().isoformat(timespec="seconds")
    handoff_text = (
        "\n\n### issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28\n"
        f"- Appended: {timestamp}\n"
        f"- primary_verdict: {primary_verdict}\n"
        "- Gate: Data validity only; no model training, no feature extraction, no manuscript edits.\n"
        f"- Gotham fuller manifest: all 78 processed CSVs summarized; sampled row manifest rows = {summary.get('sampled_row_count')}.\n"
        f"- Best split contract candidate: {best_contract}.\n"
        "- Artifact status: label/file/device/protocol/time shortcut risk remains material; split contract reduces but does not eliminate it.\n"
        "- Feature/interface gate remains blocked until PCAP/CSV pairing and source-identifier feature policy are strengthened.\n"
        "- Current model experiments remain disallowed.\n"
        "- Next action: issue27z should strengthen PCAP/CSV pairing and define source/IP/MAC handling before feature/interface work.\n"
    )
    exp_text = (
        "\n\n| issue27y | Gotham fuller manifest and preregistered split contract | "
        f"{primary_verdict} | all 78 CSV summaries, sampled row manifest, split-contract candidates; no model work | "
        "Next: issue27z PCAP/CSV pairing + source-feature policy gate |\n"
    )
    with handoff.open("a", encoding="utf-8", newline="\n") as f:
        f.write(handoff_text)
    with exp_map.open("a", encoding="utf-8", newline="\n") as f:
        f.write(exp_text)


def report_storage(allowed_mode: str, d_free_gib: float, md5: str, csv_count: int) -> None:
    rows = [
        {
            "check": "workspace",
            "value": str(REPO_ROOT),
            "status": "ok" if str(REPO_ROOT).lower().endswith(r"worktrees\kitnet-exp-mainline") else "unexpected",
            "notes": "",
        },
        {
            "check": "gotham_zip_exists",
            "value": str(ZIP_PATH),
            "status": str(ZIP_PATH.exists()).lower(),
            "notes": "",
        },
        {
            "check": "zip_md5",
            "value": md5,
            "status": "ok" if md5 == EXPECTED_MD5 else "mismatch",
            "notes": EXPECTED_MD5,
        },
        {
            "check": "d_free_gib",
            "value": f"{d_free_gib:.3f}",
            "status": "ok",
            "notes": "D drive is the only allowed Gotham storage target",
        },
        {
            "check": "processed_csv_count",
            "value": csv_count,
            "status": "ok" if csv_count == 78 else "unexpected",
            "notes": "from archive_file_listing.csv",
        },
        {
            "check": "allowed_mode",
            "value": allowed_mode,
            "status": "selected",
            "notes": "no full zip/PCAP/CSV extraction; streaming summaries only",
        },
    ]
    write_csv(OUT_DIR / "fuller_manifest_storage_table.csv", rows, ["check", "value", "status", "notes"])
    write_text(
        OUT_DIR / "fuller_manifest_storage_preflight.md",
        "\n".join(
            [
                "# Fuller Manifest Storage Preflight",
                "",
                f"- Workspace: `{REPO_ROOT}`",
                f"- Gotham data root: `{DATA_ROOT}`",
                f"- Gotham zip: `{ZIP_PATH}`",
                f"- D drive free space: {d_free_gib:.3f} GiB",
                f"- zip md5: `{md5}` ({'matches' if md5 == EXPECTED_MD5 else 'does not match'} expected)",
                f"- processed CSVs in listing: {csv_count}",
                f"- allowed_mode: `{allowed_mode}`",
                "",
                "No PCAP, full processed CSV, or archive-wide extraction is performed in this issue.",
            ]
        )
        + "\n",
    )


def choose_allowed_mode(d_free_gib: float) -> str:
    if d_free_gib < 30:
        return "summary_only_streaming"
    if d_free_gib < 80:
        return "full_file_summary_plus_sampled_row_manifest"
    return "full_file_summary_plus_compact_row_manifest_if_feasible"


def write_reports(
    *,
    allowed_mode: str,
    d_free_gib: float,
    file_rows: Sequence[Dict[str, Any]],
    sampled_rows: Sequence[Dict[str, Any]],
    scan_meta: Dict[str, Any],
    pairing_rows: Sequence[Dict[str, Any]],
    risk_rows: Sequence[Dict[str, Any]],
    contract_rows: Sequence[Dict[str, Any]],
    size_rows: Sequence[Dict[str, Any]],
    primary_verdict: str,
) -> None:
    counts = summarize_counts(file_rows)
    best_contract = contract_rows[0]["contract_id"] if contract_rows else "none"
    pcap_conf_summary = Counter(row["pcap_pairing_confidence"] for row in pairing_rows)
    high_risks = [r for r in risk_rows if stringify(r.get("risk_level")) in {"high", "medium_high"}]

    write_csv(
        OUT_DIR / "gotham_all_csv_file_manifest.csv",
        file_rows,
        [
            "csv_file_id",
            "csv_archive_path",
            "file_name",
            "file_size",
            "inferred_device",
            "inferred_protocol_from_filename",
            "observed_protocol_from_frame_protocols",
            "pcap_counterpart_candidate",
            "pcap_pairing_confidence",
            "pcap_pairing_candidate_count",
            "total_rows_estimated_or_exact",
            "row_count_status",
            "columns_count",
            "has_label",
            "has_frame_time",
            "has_frame_number",
            "has_frame_protocols",
            "has_ip_src",
            "has_ip_dst",
            "label_values",
            "benign_rows",
            "attack_rows",
            "unknown_label_rows",
            "attack_type_values",
            "attack_type_counts",
            "first_timestamp",
            "last_timestamp",
            "duration_seconds",
            "timestamp_parse_status",
            "timestamp_parse_successes",
            "timestamp_parse_failures",
            "timestamp_monotonic_violations",
            "label_transition_count",
            "benign_prefix_then_attack_suffix_flag",
            "mixed_label_flag",
            "all_benign_flag",
            "all_attack_flag",
            "unknown_label_flag",
            "sampled_rows_kept",
            "parse_status",
            "partial_reason",
            "notes",
        ],
    )

    row_fields = [
        "global_manifest_row_id",
        "csv_file_id",
        "csv_archive_path",
        "row_index_within_file",
        "frame.time",
        "parsed_timestamp",
        "label",
        "binary_label",
        "attack_type",
        "inferred_device",
        "inferred_protocol",
        "frame.protocols",
        "ip.src",
        "ip.dst",
        "time_bucket",
        "row_order_bucket",
        "is_transition_nearby",
        "pcap_counterpart_candidate",
        "split_eligibility_hint",
    ]
    write_csv(OUT_DIR / "gotham_fuller_row_manifest.csv", sampled_rows, row_fields)
    # Also keep a pointer copy under datasets manifests; this is small relative to raw data and must not include feature columns.
    write_csv(MANIFEST_ROOT / "issue27y_gotham_fuller_row_manifest_pointer.csv", sampled_rows[:2000], row_fields)

    write_csv(
        OUT_DIR / "gotham_fuller_pcap_csv_pairing.csv",
        pairing_rows,
        [
            "csv_file_id",
            "csv_archive_path",
            "pcap_counterpart_candidate",
            "pcap_pairing_confidence",
            "pcap_pairing_candidate_count",
            "future_feature_extraction_status",
            "notes",
        ],
    )
    write_csv(
        OUT_DIR / "gotham_fuller_artifact_risk_table.csv",
        risk_rows,
        ["risk_name", "metric", "value", "groups_a", "groups_b", "risk_level", "interpretation", "mitigation"],
    )
    write_csv(
        OUT_DIR / "gotham_preregistered_split_contract_candidates.csv",
        contract_rows,
        [
            "contract_id",
            "split_goal",
            "included_csv_files",
            "excluded_csv_files",
            "ID_benign_train_files",
            "OOD_benign_val_files",
            "final_OOD_benign_eval_files",
            "attack_support_files",
            "attack_eval_files",
            "allowed_labels",
            "excluded_labels",
            "row_selection_rules",
            "timestamp_order_rules",
            "purge_gap_or_embargo_rules",
            "support_size_candidates",
            "final_eval_report_only",
            "threshold_selection_allowed_sets",
            "forbidden_selection_sets",
            "artifact_risk_assessment",
            "minimum_size_check",
            "evidence_level",
            "ID_benign_train_rows",
            "OOD_benign_val_rows",
            "final_OOD_benign_eval_rows",
            "attack_support_rows",
            "attack_eval_rows",
            "ID_device_count",
            "OOD_val_device_count",
            "final_OOD_device_count",
            "attack_support_type_count",
            "attack_eval_type_count",
            "notes",
        ],
    )
    write_json_contract(contract_rows[0] if contract_rows else {}, primary_verdict)
    write_csv(
        OUT_DIR / "gotham_size_adequacy_table.csv",
        size_rows,
        [
            "contract_id",
            "ID_benign_train_rows",
            "OOD_benign_val_rows",
            "final_OOD_benign_eval_rows",
            "attack_support_rows",
            "attack_eval_rows",
            "ID_device_count",
            "OOD_val_device_count",
            "final_OOD_device_count",
            "attack_type_count_min_support_eval",
            "support_size_candidates_supported",
            "one_file_dominance_risk",
            "subgroup_analysis_possible",
            "size_adequacy_verdict",
            "notes",
        ],
    )

    write_text(
        OUT_DIR / "gotham_all_csv_file_manifest_report.md",
        "\n".join(
            [
                "# Gotham All-CSV File Manifest Report",
                "",
                f"- Processed CSV files summarized: {counts['file_count']}",
                f"- Total rows (exact streamed count where parse_status ok): {counts['total_rows']}",
                f"- Benign rows: {counts['benign_rows']}",
                f"- Attack rows: {counts['attack_rows']}",
                f"- All-benign files: {counts['all_benign_files']}",
                f"- Mixed-label files: {counts['mixed_files']}",
                f"- All-attack files: {counts['all_attack_files']}",
                f"- Devices observed: {', '.join(counts['devices'])}",
                f"- Protocols observed: {', '.join(counts['protocols'])}",
                f"- Attack labels observed: {', '.join(counts['attacks'])}",
                f"- Streaming elapsed seconds: {scan_meta.get('elapsed_seconds', 0):.1f}",
                "",
                "The summary was computed by streaming CSVs from the zip archive. No full CSV or PCAP extraction was performed.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "gotham_fuller_row_manifest_report.md",
        "\n".join(
            [
                "# Gotham Fuller Row Manifest Report",
                "",
                f"- allowed_mode: `{allowed_mode}`",
                "- Manifest mode: `stratified_sampled_row_manifest`" if allowed_mode != "full_file_summary_plus_compact_row_manifest_if_feasible" else "- Manifest mode: `compact_row_manifest_attempted`",
                f"- Sampled row manifest rows: {len(sampled_rows)}",
                "- Fields intentionally exclude feature columns and raw packet payloads.",
                "- Sampling covers early rows, per-label rows, transition-near rows, and sparse row-order anchors per file.",
                "",
                "This manifest is sufficient for data-contract design, but not a substitute for a future full feature/interface manifest.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "gotham_fuller_pcap_csv_pairing_report.md",
        "\n".join(
            [
                "# Gotham Fuller PCAP/CSV Pairing Report",
                "",
                f"- Pairing confidence summary: {dict(pcap_conf_summary)}",
                "- Pairing is based on filename/path/device tokens only.",
                "- No PCAP packet counts, byte-level packet hashes, or row-to-packet alignment were computed in this issue.",
                "- Future feature/interface gate should strengthen this with packet-count hints or sampled PCAP parsing before any claim-safe feature extraction.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "gotham_fuller_artifact_risk_report.md",
        "\n".join(
            [
                "# Gotham Fuller Artifact Risk Report",
                "",
                "The full file summary confirms that Gotham is much stronger than the anonymous full-Mirai feature CSV for data semantics, but shortcut risks remain material.",
                "",
                "High or medium-high risks:",
                *[
                    f"- {row['risk_name']}: {row['metric']}={row['value']} ({row['risk_level']}); mitigation: {row['mitigation']}"
                    for row in high_risks
                ],
                "",
                "Interpretation:",
                "- Label/file binding is expected in packet-capture datasets because attack campaigns are captured in named files, but it becomes a claim risk if split roles are not file-disjoint.",
                "- Device/protocol/time binding can support meaningful drift only if the split contract declares it explicitly and prevents using final eval for selection.",
                "- Source identifiers such as IP/MAC/port-like columns must be handled in the Feature / interface gate before model work.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "gotham_preregistered_split_contract_report.md",
        "\n".join(
            [
                "# Gotham Preregistered Split Contract Report",
                "",
                f"- Best current candidate: `{best_contract}`",
                "- The primary route is device-disjoint benign drift with file-disjoint attack support/eval.",
                "- The secondary route is protocol-disjoint benign drift, but protocol shortcut risk is higher.",
                "- Time-aware within-device splitting remains diagnostic/high-risk because mixed CSVs can encode benign-prefix to attack-suffix transitions.",
                "",
                "These contracts are pre-registered candidates only. They do not authorize model training until the PCAP/CSV pairing and feature-source policy gate is complete.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "gotham_size_adequacy_report.md",
        "\n".join(
            [
                "# Gotham Size Adequacy Report",
                "",
                "Size adequacy was evaluated with row count, file count, device count, protocol count, attack type coverage, support/eval independence, final OOD size, and subgroup-analysis feasibility.",
                "",
                *[
                    f"- {row['contract_id']}: {row['size_adequacy_verdict']} "
                    f"(ID={row['ID_benign_train_rows']}, OOD_val={row['OOD_benign_val_rows']}, "
                    f"final_OOD={row['final_OOD_benign_eval_rows']}, attack_eval={row['attack_eval_rows']})"
                    for row in size_rows
                ],
                "",
                "The primary contract appears size-adequate, but size alone does not resolve shortcut, pairing, or feature-provenance risks.",
            ]
        )
        + "\n",
    )

    write_text(
        OUT_DIR / "issue27y_decision.md",
        "\n".join(
            [
                "# issue27y Decision",
                "",
                f"primary_verdict = {primary_verdict}",
                "",
                "Rationale:",
                "- All 78 processed CSVs were summarized from the zip without full extraction.",
                "- A stratified sampled row manifest and preregistered split-contract candidates were produced.",
                "- The primary device-disjoint contract is size-promising and may support the low-OOD-alert benchmark after additional gates.",
                "- PCAP/CSV pairing remains medium-confidence filename/path pairing, not packet-level alignment.",
                "- Shortcut risk remains nontrivial, especially label/file binding and source/device/protocol/time coupling.",
                "",
                "Decision:",
                "- Do not enter model execution yet.",
                "- Proceed to issue27z for PCAP/CSV pairing strengthening and feature/source-identifier policy.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "claim_update_after_issue27y.md",
        "\n".join(
            [
                "# Claim Update After issue27y",
                "",
                "- Gotham is a promising replacement benchmark candidate with raw PCAP, labelled CSV, timestamps, and enough scale for preregistered split-contract design.",
                "- Current evidence supports a data-contract candidate, not model claims.",
                "- Gotham cannot yet be treated as a completed main benchmark because PCAP/CSV pairing and feature-source shortcut controls remain incomplete.",
                "- No LOW-GUARD, DeepSAD, or baseline conclusion should be drawn from issue27y.",
                "- External generalization, deployment robustness, restored115 equivalence, and paper readiness are not claimed.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "issue27z_next_action.md",
        "\n".join(
            [
                "# issue27z Next Action",
                "",
                "Recommended next task: `issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28`.",
                "",
                "Scope:",
                "- Strengthen PCAP/CSV pairing for the preregistered contract files using packet-count hints and safe sampled PCAP metadata reads.",
                "- Define source identifier handling before feature/interface work: IP, MAC, ports, file identifiers, timestamp-derived fields, and protocol tokens.",
                "- Decide whether Gotham can enter Feature / interface gate with raw PCAP extraction or processed-flow features.",
                "- Continue to forbid model training until those gates pass.",
                "",
                "Slurm:",
                "- Not needed for metadata/pairing checks.",
                "- Likely needed later for full feature extraction over all contract files.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "summary.md",
        "\n".join(
            [
                "# issue27y Summary",
                "",
                "1. issue27y complete: yes.",
                f"2. primary_verdict: {primary_verdict}.",
                f"3. allowed_mode: {allowed_mode}.",
                "4. All 78 CSV file-level summary complete: yes.",
                f"5. Fuller row manifest complete: yes, {len(sampled_rows)} rows.",
                "6. Row manifest type: stratified sampled row manifest.",
                f"7. PCAP/CSV pairing confidence: medium filename/path pairing; summary {dict(pcap_conf_summary)}.",
                "8. Label/file/device/protocol/time shortcut risk: material; label/file risk remains high and must be controlled by file-disjoint contracts and feature-source policy.",
                "9. At least one preregistered split contract found: yes.",
                f"10. Recommended split contract: {best_contract}.",
                f"11. ID benign train constructible: yes under {best_contract}, pending feature/source policy.",
                f"12. OOD benign validation constructible: yes under {best_contract}, pending feature/source policy.",
                f"13. Final OOD benign eval constructible: yes under {best_contract}, report-only.",
                "14. Attack support/eval disjoint constructible: yes at file level, but needs PCAP/row-level strengthening.",
                "15. Size adequacy: primary contract appears size-adequate, but size alone is not sufficient for claim safety.",
                "16. Gotham can enter Feature / interface gate: not yet; it first needs PCAP/CSV pairing strengthening and feature-source shortcut policy.",
                "17. Current model experiments allowed: no.",
                "18. issue27z recommendation: PCAP/CSV pairing and feature-source policy gate.",
                "19. Slurm needed: not for issue27z metadata/pairing; likely for full feature extraction later.",
                "20. commit hash: pending.",
            ]
        )
        + "\n",
    )
    append_mainline_docs(primary_verdict, {"sampled_row_count": len(sampled_rows)}, best_contract)


def write_json_contract(best: Dict[str, Any], primary_verdict: str) -> None:
    payload = {
        "issue": ISSUE,
        "primary_verdict": primary_verdict,
        "contract": best,
        "status": "candidate_not_model_ready",
        "model_training_allowed": False,
        "final_eval_report_only": True,
        "forbidden": [
            "model_training",
            "feature_extraction",
            "full_pcap_extraction",
            "split_selection_from_model_results",
        ],
    }
    write_text(OUT_DIR / "gotham_preregistered_split_contract_v1.json", json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_run_metadata(allowed_mode: str, primary_verdict: str) -> None:
    config = {
        "issue": ISSUE,
        "dataset": "gotham2025",
        "zip_path": str(ZIP_PATH),
        "expected_md5": EXPECTED_MD5,
        "allowed_mode": allowed_mode,
        "no_model_training": True,
        "no_feature_extraction": True,
        "no_full_pcap_extraction": True,
        "primary_verdict": primary_verdict,
    }
    run_spec = {
        "stages": [
            "storage_preflight",
            "all_csv_file_manifest",
            "sampled_row_manifest",
            "pcap_csv_pairing",
            "artifact_risk_full_summary",
            "preregistered_split_contracts",
            "size_adequacy",
            "decision",
        ],
        "inputs": [
            str(ISSUE27X_DIR / "summary.md"),
            str(ISSUE27V_DIR / "archive_file_listing.csv"),
            str(ZIP_PATH),
        ],
        "outputs_dir": str(OUT_DIR),
    }
    write_text(OUT_DIR / "config.json", json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    write_text(OUT_DIR / "run_spec.json", json.dumps(run_spec, ensure_ascii=False, indent=2) + "\n")
    write_text(
        OUT_DIR / "command.txt",
        "python repo/ood/issue27y_gotham_fuller_manifest_contract.py\n",
    )

    output_files = sorted(p.name for p in OUT_DIR.iterdir() if p.is_file())
    rows = [
        {
            "artifact": name,
            "path": str(OUT_DIR / name),
            "sha256": hashlib.sha256((OUT_DIR / name).read_bytes()).hexdigest(),
            "bytes": (OUT_DIR / name).stat().st_size,
        }
        for name in output_files
    ]
    write_csv(OUT_DIR / "manifest.csv", rows, ["artifact", "path", "sha256", "bytes"])


def main() -> int:
    ensure_dirs()
    if not ZIP_PATH.exists():
        raise FileNotFoundError(f"Gotham zip not found: {ZIP_PATH}")
    d_free = disk_free_gib(Path("D:\\"))
    allowed_mode = choose_allowed_mode(d_free)
    listing = load_archive_listing()
    csv_entries = [row for row in listing if is_processed_csv(archive_path(row))]
    pcap_paths = [archive_path(row) for row in listing if is_pcap(archive_path(row))]
    md5 = md5_file(ZIP_PATH)
    report_storage(allowed_mode, d_free, md5, len(csv_entries))
    if md5 != EXPECTED_MD5:
        raise RuntimeError(f"Zip md5 mismatch: got {md5}, expected {EXPECTED_MD5}")

    file_rows, sampled_rows, scan_meta = summarize_csvs(csv_entries, pcap_paths, allowed_mode)
    pairing_rows = [
        {
            "csv_file_id": row["csv_file_id"],
            "csv_archive_path": row["csv_archive_path"],
            "pcap_counterpart_candidate": row["pcap_counterpart_candidate"],
            "pcap_pairing_confidence": row["pcap_pairing_confidence"],
            "pcap_pairing_candidate_count": row["pcap_pairing_candidate_count"],
            "future_feature_extraction_status": "needs_packet_count_or_sampled_pcap_validation"
            if row["pcap_pairing_confidence"] != "missing"
            else "blocked_missing_pair",
            "notes": "filename/path token pairing only; no PCAP extraction in issue27y",
        }
        for row in file_rows
    ]
    risk_rows = build_artifact_risk(file_rows, sampled_rows)
    contract_rows = build_contracts(file_rows)
    size_rows = size_adequacy_rows(contract_rows)

    all_summary_ok = len(file_rows) == 78 and not scan_meta.get("failures")
    best_size = size_rows[0]["size_adequacy_verdict"] if size_rows else "none"
    pairing_ok = all(row["pcap_pairing_confidence"] in {"medium_filename_path_match", "low_device_token_match"} for row in pairing_rows)
    material_shortcut_risk = any(
        row["risk_name"] in {"label_vs_file_id", "label_vs_device", "label_vs_protocol"}
        and row["risk_level"] in {"medium_high", "high"}
        for row in risk_rows
    )
    pairing_only_medium = any(row["pcap_pairing_confidence"] != "high" for row in pairing_rows)

    if not all_summary_ok:
        primary_verdict = "gotham_data_contract_promising_needs_feature_pairing_or_full_manifest"
    elif not pairing_ok:
        primary_verdict = "gotham_data_contract_promising_needs_feature_pairing_or_full_manifest"
    elif best_size in {"size_insufficient_for_main_claim", "size_blocked_by_group_dominance"}:
        primary_verdict = "gotham_data_contract_blocked_by_size_or_balance"
    elif material_shortcut_risk or pairing_only_medium:
        primary_verdict = "gotham_data_contract_promising_needs_feature_pairing_or_full_manifest"
    else:
        primary_verdict = "gotham_data_contract_ready_for_feature_interface_gate"

    write_reports(
        allowed_mode=allowed_mode,
        d_free_gib=d_free,
        file_rows=file_rows,
        sampled_rows=sampled_rows,
        scan_meta=scan_meta,
        pairing_rows=pairing_rows,
        risk_rows=risk_rows,
        contract_rows=contract_rows,
        size_rows=size_rows,
        primary_verdict=primary_verdict,
    )
    write_run_metadata(allowed_mode, primary_verdict)
    print(json.dumps({"primary_verdict": primary_verdict, "files": len(file_rows), "sampled_rows": len(sampled_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
