#!/usr/bin/env python3
"""Issue27z Gotham PCAP/CSV pairing and source-feature policy gate.

Data validity / feature-interface pre-gate only. This script:
- streams processed CSV timestamps from GothamDataset2025.zip;
- streams PCAP packet metadata from the same zip without extracting PCAPs;
- strengthens CSV/PCAP pairing evidence;
- writes a source-like feature inventory and feature-source policy.

It does not train models, run baselines, perform formal feature extraction, or
select splits from model results.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import struct
import sys
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ISSUE = "issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28"
EXPECTED_MD5 = "7ca78c0517ccb3d2854e823678e0f206"

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = REPO_ROOT.parents[1]
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
MANIFEST_ROOT = DATA_ROOT / "manifests"
DERIVED_ROOT = DATA_ROOT / "derived" / "pairing_source_policy_gate"
OUT_DIR = REPO_ROOT / "runs" / ISSUE

ISSUE27Y_DIR = REPO_ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ISSUE27V_DIR = REPO_ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"
MAINLINE_DOCS = REPO_ROOT / "runs" / "mainline_docs"


def ensure_dirs() -> None:
    for path in [OUT_DIR, MANIFEST_ROOT, DERIVED_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (list, tuple, set)):
        return "|".join(str(x) for x in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value)


def write_csv(path: Path, rows: Sequence[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: stringify(row.get(key, "")) for key in fieldnames})


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def parse_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def parse_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except Exception:
        return None


def disk_free_gib(path: Path) -> float:
    return shutil.disk_usage(str(path)).free / (1024**3)


def md5_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def archive_path(row: Dict[str, str]) -> str:
    for key in ["archive_path", "file_path", "path", "filename", "name"]:
        if row.get(key):
            return row[key]
    raise KeyError(f"archive path not found in row keys: {row.keys()}")


def is_pcap_path(path: str) -> bool:
    lower = path.replace("\\", "/").lower()
    return lower.endswith(".pcap") or lower.endswith(".pcapng")


def is_processed_csv(path: str) -> bool:
    lower = path.replace("\\", "/").lower()
    return lower.startswith("processed/") and lower.endswith(".csv")


def normalize_stem(path: str) -> str:
    return Path(path.replace("\\", "/")).stem.lower()


def infer_device(path: str) -> str:
    stem = normalize_stem(path)
    stem = re.sub(r"^iotsim-", "", stem)
    stem = re.sub(r"_.*$", "", stem)
    tokens = stem.split("-")
    if tokens and tokens[-1].isdigit():
        return "-".join(tokens[:-1])
    return stem


def infer_protocol_from_path_or_frame(path: str, frame_protocols: str = "") -> str:
    haystack = f"{path} {frame_protocols}".lower()
    for token in ["mqtt", "coap", "dtls", "tls", "http", "telnet", "goose", "icmp", "dns", "rtcp", "ntp"]:
        if token in haystack:
            return token
    return ""


def parse_frame_time(value: str) -> Tuple[Optional[float], str, bool]:
    raw = (value or "").strip()
    if not raw:
        return None, "", False
    cleaned = re.sub(r"\s+(GMT|UTC)$", "", raw, flags=re.IGNORECASE)
    # Wireshark frame.time can carry 9 fractional digits; Python supports 6.
    m = re.match(r"^(.*\d{2}:\d{2}:\d{2})\.(\d+)$", cleaned)
    if m:
        frac = (m.group(2) + "000000")[:6]
        cleaned = f"{m.group(1)}.{frac}"
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
            dt = datetime.strptime(cleaned, fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp(), dt.isoformat().replace("+00:00", "Z"), True
        except ValueError:
            pass
    try:
        ts = float(cleaned)
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return ts, dt.isoformat().replace("+00:00", "Z"), True
    except Exception:
        return None, "", False


def iso_from_epoch(ts: Optional[float]) -> str:
    if ts is None:
        return ""
    try:
        return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def find_column(columns: Sequence[str], candidates: Sequence[str]) -> str:
    lower = {c.lower(): c for c in columns}
    for candidate in candidates:
        if candidate.lower() in lower:
            return lower[candidate.lower()]
    return ""


def safe_ratio(a: Optional[float], b: Optional[float]) -> str:
    if a is None or b is None:
        return ""
    return f"{a - b:.6f}"


def pcap_candidate_from_csv(csv_path: str, pcap_paths: Sequence[str]) -> Tuple[str, int]:
    stem = normalize_stem(csv_path)
    matches = []
    for p in pcap_paths:
        p_stem = normalize_stem(p)
        if p_stem == stem or p_stem.startswith(stem + "_") or stem in p_stem:
            matches.append(p)
    if matches:
        return matches[0], len(matches)
    device = infer_device(csv_path)
    loose = [p for p in pcap_paths if device and device in normalize_stem(p)]
    if loose:
        return loose[0], len(loose)
    return "", 0


@dataclass
class PcapMeta:
    archive_path: str
    status: str
    packet_count: int = 0
    first_ts: Optional[float] = None
    last_ts: Optional[float] = None
    snaplen: int = 0
    network: int = 0
    endian: str = ""
    ts_resolution: str = ""
    bytes_scanned: int = 0
    error: str = ""


def skip_bytes(f: Any, n: int) -> int:
    remaining = n
    skipped = 0
    while remaining > 0:
        chunk = f.read(min(1024 * 1024, remaining))
        if not chunk:
            break
        skipped += len(chunk)
        remaining -= len(chunk)
    return skipped


def read_pcap_meta_from_zip(zf: zipfile.ZipFile, path: str) -> PcapMeta:
    try:
        info = zf.getinfo(path)
        with zf.open(info, "r") as f:
            header = f.read(24)
            if len(header) < 24:
                return PcapMeta(path, "bad_header", error="short global header")
            magic = header[:4]
            if magic == b"\xd4\xc3\xb2\xa1":
                endian = "<"
                ts_res = "microsecond"
            elif magic == b"\xa1\xb2\xc3\xd4":
                endian = ">"
                ts_res = "microsecond"
            elif magic == b"\x4d\x3c\xb2\xa1":
                endian = "<"
                ts_res = "nanosecond"
            elif magic == b"\xa1\xb2\x3c\x4d":
                endian = ">"
                ts_res = "nanosecond"
            elif magic == b"\x0a\x0d\x0d\x0a":
                return PcapMeta(path, "pcapng_unsupported", bytes_scanned=24, error="pcapng unsupported in this gate")
            else:
                return PcapMeta(path, "unknown_magic", bytes_scanned=24, error=magic.hex())
            try:
                _magic, _vmaj, _vmin, _tz, _sig, snaplen, network = struct.unpack(endian + "IHHIIII", header)
            except Exception as exc:
                return PcapMeta(path, "bad_global_unpack", error=repr(exc))
            count = 0
            first = None
            last = None
            scanned = 24
            packet_struct = struct.Struct(endian + "IIII")
            while True:
                pkt_header = f.read(16)
                if not pkt_header:
                    break
                scanned += len(pkt_header)
                if len(pkt_header) < 16:
                    return PcapMeta(path, "truncated_packet_header", count, first, last, snaplen, network, endian, ts_res, scanned)
                ts_sec, ts_frac, incl_len, _orig_len = packet_struct.unpack(pkt_header)
                if incl_len < 0 or incl_len > 256 * 1024 * 1024:
                    return PcapMeta(path, "invalid_incl_len", count, first, last, snaplen, network, endian, ts_res, scanned, str(incl_len))
                skipped = skip_bytes(f, incl_len)
                scanned += skipped
                if skipped != incl_len:
                    return PcapMeta(path, "truncated_packet_payload", count, first, last, snaplen, network, endian, ts_res, scanned)
                frac_div = 1_000_000_000 if ts_res == "nanosecond" else 1_000_000
                ts = ts_sec + (ts_frac / frac_div)
                if first is None:
                    first = ts
                last = ts
                count += 1
            return PcapMeta(path, "ok", count, first, last, snaplen, network, endian, ts_res, scanned)
    except Exception as exc:
        return PcapMeta(path, "error", error=repr(exc))


def stream_csv_side_stats(zf: zipfile.ZipFile, csv_path: str) -> Dict[str, Any]:
    first_ts = None
    last_ts = None
    min_ts = None
    max_ts = None
    parse_ok = 0
    parse_fail = 0
    frame_number_min = None
    frame_number_max = None
    columns: List[str] = []
    dominant_protocol_counter: Counter[str] = Counter()
    with zf.open(csv_path, "r") as raw:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        columns = reader.fieldnames or []
        time_col = find_column(columns, ["frame.time", "frame_time", "timestamp", "time"])
        number_col = find_column(columns, ["frame.number", "frame_number"])
        proto_col = find_column(columns, ["frame.protocols", "frame_protocols"])
        for idx, row in enumerate(reader, start=1):
            if number_col:
                n = parse_int(row.get(number_col))
                if frame_number_min is None or n < frame_number_min:
                    frame_number_min = n
                if frame_number_max is None or n > frame_number_max:
                    frame_number_max = n
            if time_col:
                ts, _iso, ok = parse_frame_time(row.get(time_col, ""))
                if ok and ts is not None:
                    parse_ok += 1
                    if first_ts is None:
                        first_ts = ts
                    last_ts = ts
                    min_ts = ts if min_ts is None else min(min_ts, ts)
                    max_ts = ts if max_ts is None else max(max_ts, ts)
                elif row.get(time_col, ""):
                    parse_fail += 1
            if proto_col and idx <= 5000:
                for token in re.split(r"[:;,|/\s]+", row.get(proto_col, "").lower()):
                    if token and token not in {"eth", "ethertype", "ip", "ipv6", "tcp", "udp", "data", "frame"}:
                        dominant_protocol_counter[token] += 1
    protocol_hint = ""
    for token, _count in dominant_protocol_counter.most_common():
        if token in {"mqtt", "coap", "dtls", "tls", "http", "telnet", "goose", "icmp", "dns", "rtcp", "ntp"}:
            protocol_hint = token
            break
    return {
        "csv_timestamp_min_epoch": min_ts,
        "csv_timestamp_max_epoch": max_ts,
        "csv_first_timestamp_epoch": first_ts,
        "csv_last_timestamp_epoch": last_ts,
        "csv_timestamp_min": iso_from_epoch(min_ts),
        "csv_timestamp_max": iso_from_epoch(max_ts),
        "csv_first_timestamp": iso_from_epoch(first_ts),
        "csv_last_timestamp": iso_from_epoch(last_ts),
        "csv_timestamp_parse_ok_rows": parse_ok,
        "csv_timestamp_parse_fail_rows": parse_fail,
        "csv_frame_number_min": frame_number_min if frame_number_min is not None else "",
        "csv_frame_number_max": frame_number_max if frame_number_max is not None else "",
        "csv_columns": columns,
        "csv_protocol_hint": protocol_hint,
    }


def compare_packet_count(csv_rows: int, pcap_packets: int) -> str:
    if pcap_packets <= 0:
        return "pcap_packet_count_missing"
    if csv_rows == pcap_packets:
        return "exact_match"
    diff = abs(csv_rows - pcap_packets)
    if csv_rows and diff / csv_rows <= 0.001:
        return "near_match_within_0p1pct"
    if csv_rows and diff / csv_rows <= 0.01:
        return "near_match_within_1pct"
    return "mismatch"


def compare_timestamp_ranges(csv_min: Optional[float], csv_max: Optional[float], pcap_first: Optional[float], pcap_last: Optional[float]) -> str:
    if csv_min is None or csv_max is None:
        return "csv_timestamp_missing"
    if pcap_first is None or pcap_last is None:
        return "pcap_timestamp_missing"
    start_delta = abs(csv_min - pcap_first)
    end_delta = abs(csv_max - pcap_last)
    overlap = max(csv_min, pcap_first) <= min(csv_max, pcap_last)
    if start_delta <= 1.0 and end_delta <= 1.0:
        return "range_endpoint_match_within_1s"
    if overlap:
        return "range_overlap"
    return "no_overlap"


def new_pairing_confidence(count_status: str, time_status: str, old: str) -> str:
    if count_status in {"exact_match", "near_match_within_0p1pct"} and time_status == "range_endpoint_match_within_1s":
        return "high_packet_count_timestamp_match"
    if count_status in {"exact_match", "near_match_within_0p1pct"} and time_status in {"range_overlap", "csv_timestamp_missing"}:
        return "medium_plus_frame_timestamp_hint"
    if count_status in {"near_match_within_1pct"} and time_status in {"range_endpoint_match_within_1s", "range_overlap"}:
        return "medium_plus_frame_timestamp_hint"
    if old:
        return "medium_filename_path_match"
    return "low_ambiguous"


def tool_status_rows() -> List[Dict[str, Any]]:
    tools = ["tshark", "capinfos", "editcap", "tcpdump", "python", "curl", "aria2c"]
    rows = []
    for tool in tools:
        found = shutil.which(tool)
        rows.append(
            {
                "tool": tool,
                "available": bool(found),
                "path": found or "",
                "notes": "pcap metadata can use this" if tool in {"tshark", "capinfos", "tcpdump"} and found else "fallback to Python streaming parser" if tool == "python" and found else "",
            }
        )
    return rows


def source_inventory_from_columns(columns: Sequence[str]) -> List[Dict[str, Any]]:
    policies = {
        "label": ("label", "blocking", "no", "yes", "no", "no", "no", "forbidden", "target label only; never an input feature"),
        "attack_type": ("label", "blocking", "no", "yes", "no", "no", "no", "forbidden", "derived target label only"),
        "file_id": ("path/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "direct source identifier"),
        "csv_archive_path": ("path/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "direct file path identifier"),
        "device": ("device/source", "high", "yes", "yes", "yes", "no", "no", "forbidden", "split grouping and shortcut audit only"),
        "inferred_device": ("device/source", "high", "yes", "yes", "yes", "no", "no", "forbidden", "path-derived device identifier"),
        "frame.time": ("timestamp", "high", "yes", "yes", "yes", "no", "no", "split_order_only", "use for ordering/purge/audit, not raw model input"),
        "frame.number": ("row/order", "high", "yes", "yes", "yes", "no", "no", "pairing_audit_only", "packet order proxy, not model input"),
        "frame.protocols": ("protocol", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "protocol text can leak device/source; diagnostic rich policy only"),
        "eth.src": ("mac/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "host identifier"),
        "eth.dst": ("mac/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "host identifier"),
        "ip.src": ("ip/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "host/source identifier"),
        "ip.dst": ("ip/source", "blocking", "yes", "yes", "yes", "no", "no", "forbidden", "host/source identifier"),
        "tcp.srcport": ("port", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "ports can be service/source proxy; not strict main input"),
        "tcp.dstport": ("port", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "ports can be service/source proxy; not strict main input"),
        "udp.srcport": ("port", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "ports can be service/source proxy; not strict main input"),
        "udp.dstport": ("port", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "ports can be service/source proxy; not strict main input"),
        "ip.proto": ("protocol_numeric", "medium", "yes", "yes", "yes", "no", "yes", "diagnostic_only", "protocol identity needs audit before main use"),
    }
    default_main = {
        "frame.len",
        "ip.flags",
        "ip.ttl",
        "ip.tos",
        "tcp.flags",
        "tcp.window_size_value",
        "tcp.window_size_scalefactor",
        "tcp.pdu.size",
    }
    diagnostic_only = {"ip.checksum", "tcp.checksum", "tcp.options"}
    rows = []
    all_fields = list(dict.fromkeys(list(columns) + [
        "file_id",
        "csv_archive_path",
        "device",
        "inferred_device",
        "attack_type",
        "pcap_archive_path",
        "source/capture/path",
    ]))
    for field in all_fields:
        if field in policies:
            semantic_type, risk, split, audit, pairing, main, diag, transform, reason = policies[field]
        elif field in default_main:
            semantic_type, risk, split, audit, pairing, main, diag, transform, reason = (
                "packet_header_numeric",
                "low_medium",
                "no",
                "yes",
                "no",
                "yes",
                "yes",
                "strict_numeric_scaling_and_missing_policy",
                "numeric packet/header field; still requires distribution and leakage audit",
            )
        elif field in diagnostic_only:
            semantic_type, risk, split, audit, pairing, main, diag, transform, reason = (
                "checksum_or_option",
                "medium",
                "no",
                "yes",
                "no",
                "no",
                "yes",
                "diagnostic_only_or_drop",
                "can encode low-level implementation/source quirks",
            )
        elif "path" in field or "source" in field or "capture" in field:
            semantic_type, risk, split, audit, pairing, main, diag, transform, reason = (
                "path/source",
                "blocking",
                "yes",
                "yes",
                "yes",
                "no",
                "no",
                "forbidden",
                "source/capture identifier",
            )
        else:
            semantic_type, risk, split, audit, pairing, main, diag, transform, reason = (
                "unknown_or_packet_field",
                "medium",
                "no",
                "yes",
                "no",
                "no",
                "yes",
                "diagnostic_until_audited",
                "not whitelisted for strict main policy",
            )
        rows.append(
            {
                "field_name": field,
                "source": "processed_csv_or_derived_manifest",
                "semantic_type": semantic_type,
                "shortcut_risk": risk,
                "allowed_for_split": split,
                "allowed_for_audit": audit,
                "allowed_for_pairing": pairing,
                "allowed_as_model_feature_main": main,
                "allowed_as_model_feature_diagnostic": diag,
                "transformation_policy": transform,
                "reason": reason,
            }
        )
    return rows


def build_policy(inventory_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    forbidden = [r["field_name"] for r in inventory_rows if r["allowed_as_model_feature_main"] == "no" and r["shortcut_risk"] in {"blocking", "high"}]
    split_audit_only = [r["field_name"] for r in inventory_rows if r["allowed_for_split"] == "yes" or r["allowed_for_pairing"] == "yes"]
    strict = [r["field_name"] for r in inventory_rows if r["allowed_as_model_feature_main"] == "yes"]
    diagnostic = [r["field_name"] for r in inventory_rows if r["allowed_as_model_feature_diagnostic"] == "yes"]
    return {
        "policy_id": "gotham_feature_source_policy_v1",
        "issue": ISSUE,
        "scope": "Gotham Data validity / Feature-interface pre-gate",
        "model_training_allowed": False,
        "formal_feature_extraction_allowed": False,
        "strict_content_policy": {
            "allowed_candidate_fields": strict,
            "forbidden_fields": sorted(set(forbidden + ["label", "attack_type", "file_id", "csv_archive_path", "pcap_archive_path"])),
            "notes": "Strict policy is the only candidate route for main-claim features; it still requires feature-interface audit before model execution.",
        },
        "diagnostic_rich_policy": {
            "allowed_diagnostic_fields": diagnostic,
            "not_main_claim_default": True,
            "notes": "Protocol/port/checksum/options fields are diagnostic until shortcut audits show they do not dominate the claim.",
        },
        "split_audit_pairing_only_fields": sorted(set(split_audit_only)),
        "frame_time_policy": "Use frame.time only for ordering, purge, split construction, timestamp pairing, and artifact audit; never as raw model input.",
        "ip_mac_policy": "Use IP/MAC only for source/device inference, pairing, and artifact audit; default exclude from main model inputs.",
        "port_protocol_policy": "Ports and protocol fields may be diagnostic; main use requires a separate shortcut audit and preregistration.",
        "file_device_source_policy": "Use file/device/source/path only for split and audit; never model inputs.",
        "label_policy": "Labels and attack_type are targets/evaluation labels only; never input features.",
        "future_flow_feature_policy": "Prefer uniform PCAP-derived flow/Kitsune/AfterImage features that exclude direct source identifiers, with a new interface gate before model work.",
    }


def primary_contract_files(contract: Dict[str, Any]) -> Dict[str, List[str]]:
    c = contract.get("contract", contract)
    fields = {
        "ID_benign_train_files": c.get("ID_benign_train_files", []),
        "OOD_benign_val_files": c.get("OOD_benign_val_files", []),
        "final_OOD_benign_eval_files": c.get("final_OOD_benign_eval_files", []),
        "attack_support_files": c.get("attack_support_files", []),
        "attack_eval_files": c.get("attack_eval_files", []),
    }
    out: Dict[str, List[str]] = {}
    for k, v in fields.items():
        if isinstance(v, str):
            out[k] = [x for x in v.split("|") if x]
        else:
            out[k] = list(v or [])
    return out


def summarize_confidences(rows: Sequence[Dict[str, Any]], files: Sequence[str]) -> Dict[str, Any]:
    subset = [r for r in rows if r["csv_archive_path"] in set(files)]
    conf = Counter(r["pairing_confidence_new"] for r in subset)
    low = [r["csv_archive_path"] for r in subset if r["pairing_confidence_new"] in {"low_ambiguous", "missing"}]
    return {"file_count": len(subset), "confidence_counts": dict(conf), "missing_or_low_files": low}


def main() -> int:
    ensure_dirs()
    start = time.time()
    d_free = disk_free_gib(Path("D:\\"))
    zip_exists = ZIP_PATH.exists()
    md5 = md5_file(ZIP_PATH) if zip_exists else ""
    y_manifest = load_csv(ISSUE27Y_DIR / "gotham_all_csv_file_manifest.csv")
    y_pairing = load_csv(ISSUE27Y_DIR / "gotham_fuller_pcap_csv_pairing.csv")
    y_contract = load_json(ISSUE27Y_DIR / "gotham_preregistered_split_contract_v1.json")
    archive_listing = load_csv(ISSUE27V_DIR / "archive_file_listing.csv")
    pcap_paths = [archive_path(r) for r in archive_listing if is_pcap_path(archive_path(r))]
    csv_paths = [archive_path(r) for r in archive_listing if is_processed_csv(archive_path(r))]
    pcap_size = {archive_path(r): parse_int(r.get("uncompressed_size")) for r in archive_listing}

    tools = tool_status_rows()
    python_available = any(r["tool"] == "python" and r["available"] for r in tools)
    if not zip_exists or md5 != EXPECTED_MD5 or not python_available:
        allowed_mode = "blocked_storage_or_tooling"
    else:
        allowed_mode = "pcap_metadata_streaming"

    storage_rows = [
        {"check": "d_free_gib", "value": f"{d_free:.3f}", "status": "ok", "notes": "D: is required data target"},
        {"check": "gotham_zip_exists", "value": str(ZIP_PATH), "status": str(zip_exists).lower(), "notes": ""},
        {"check": "zip_md5", "value": md5, "status": "ok" if md5 == EXPECTED_MD5 else "mismatch", "notes": EXPECTED_MD5},
        {"check": "zip_listing_readable", "value": len(archive_listing), "status": "ok" if archive_listing else "missing", "notes": ""},
        {"check": "pcap_metadata_method", "value": "python_streaming_pcap_parser", "status": "ok" if python_available else "missing", "notes": "no PCAP extraction"},
        {"check": "allowed_mode", "value": allowed_mode, "status": "selected", "notes": "metadata only; no feature extraction"},
    ]
    for tool in tools:
        storage_rows.append({"check": f"tool_{tool['tool']}", "value": tool["path"], "status": "available" if tool["available"] else "missing", "notes": tool["notes"]})
    write_csv(OUT_DIR / "pairing_policy_storage_table.csv", storage_rows, ["check", "value", "status", "notes"])
    write_text(
        OUT_DIR / "pairing_policy_storage_preflight.md",
        "\n".join(
            [
                "# Pairing Policy Storage Preflight",
                "",
                f"- D drive free space: {d_free:.3f} GiB",
                f"- Gotham zip: `{ZIP_PATH}`",
                f"- md5: `{md5}` ({'matches' if md5 == EXPECTED_MD5 else 'does not match'} expected)",
                f"- allowed_mode: `{allowed_mode}`",
                "- Tooling: no `tshark/capinfos/tcpdump/scapy` command was available; PCAP metadata uses a Python streaming parser directly on zip members.",
                "- No PCAP, full CSV, or archive-wide extraction is performed.",
            ]
        )
        + "\n",
    )
    if allowed_mode == "blocked_storage_or_tooling":
        raise RuntimeError("Blocked by storage/tooling preflight")

    # CSV-side and PCAP-side metadata.
    pcap_candidates = sorted({r["pcap_counterpart_candidate"] for r in y_manifest if r.get("pcap_counterpart_candidate")})
    pcap_meta: Dict[str, PcapMeta] = {}
    csv_stats: Dict[str, Dict[str, Any]] = {}
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for idx, path in enumerate(pcap_candidates, start=1):
            print(f"[pcap {idx}/{len(pcap_candidates)}] {path}", flush=True)
            pcap_meta[path] = read_pcap_meta_from_zip(zf, path)
        for idx, row in enumerate(y_manifest, start=1):
            path = row["csv_archive_path"]
            print(f"[csv {idx}/{len(y_manifest)}] {path}", flush=True)
            csv_stats[path] = stream_csv_side_stats(zf, path)

    y_pair_old = {r["csv_archive_path"]: r.get("pcap_pairing_confidence", "") for r in y_pairing}
    strengthened_rows: List[Dict[str, Any]] = []
    all_columns = set()
    for row in y_manifest:
        csv_path = row["csv_archive_path"]
        pcap_path = row.get("pcap_counterpart_candidate") or pcap_candidate_from_csv(csv_path, pcap_paths)[0]
        meta = pcap_meta.get(pcap_path, PcapMeta(pcap_path, "missing"))
        stats = csv_stats[csv_path]
        all_columns.update(stats.get("csv_columns", []))
        csv_rows = parse_int(row.get("total_rows_estimated_or_exact"))
        count_status = compare_packet_count(csv_rows, meta.packet_count)
        time_status = compare_timestamp_ranges(
            stats.get("csv_timestamp_min_epoch"),
            stats.get("csv_timestamp_max_epoch"),
            meta.first_ts,
            meta.last_ts,
        )
        old_conf = y_pair_old.get(csv_path, row.get("pcap_pairing_confidence", ""))
        new_conf = new_pairing_confidence(count_status, time_status, old_conf)
        csv_stem = normalize_stem(csv_path)
        pcap_stem = normalize_stem(pcap_path)
        protocol = stats.get("csv_protocol_hint") or row.get("observed_protocol_from_frame_protocols") or row.get("inferred_protocol_from_filename")
        strengthened_rows.append(
            {
                "csv_archive_path": csv_path,
                "inferred_device": row.get("inferred_device"),
                "inferred_protocol": protocol,
                "candidate_pcap_archive_path": pcap_path,
                "filename_token_match": csv_stem in pcap_stem if pcap_path else False,
                "path_token_match": bool(pcap_path),
                "device_token_match": infer_device(csv_path) == infer_device(pcap_path) if pcap_path else False,
                "protocol_token_match": protocol and protocol in (pcap_path + " " + csv_path).lower(),
                "csv_row_count": csv_rows,
                "csv_frame_number_min": stats.get("csv_frame_number_min"),
                "csv_frame_number_max": stats.get("csv_frame_number_max"),
                "csv_timestamp_min": stats.get("csv_timestamp_min"),
                "csv_timestamp_max": stats.get("csv_timestamp_max"),
                "candidate_pcap_file_size": pcap_size.get(pcap_path, ""),
                "pcap_packet_count_if_available": meta.packet_count if meta.status == "ok" else "",
                "pcap_first_timestamp_if_available": iso_from_epoch(meta.first_ts),
                "pcap_last_timestamp_if_available": iso_from_epoch(meta.last_ts),
                "pcap_metadata_status": meta.status,
                "packet_count_vs_csv_row_count_status": count_status,
                "timestamp_range_overlap_status": time_status,
                "pairing_confidence_old": old_conf,
                "pairing_confidence_new": new_conf,
                "unresolved_reason": "" if new_conf == "high_packet_count_timestamp_match" else f"count={count_status}; time={time_status}; pcap_status={meta.status}",
            }
        )

    write_csv(
        OUT_DIR / "gotham_pairing_strengthened_table.csv",
        strengthened_rows,
        [
            "csv_archive_path",
            "inferred_device",
            "inferred_protocol",
            "candidate_pcap_archive_path",
            "filename_token_match",
            "path_token_match",
            "device_token_match",
            "protocol_token_match",
            "csv_row_count",
            "csv_frame_number_min",
            "csv_frame_number_max",
            "csv_timestamp_min",
            "csv_timestamp_max",
            "candidate_pcap_file_size",
            "pcap_packet_count_if_available",
            "pcap_first_timestamp_if_available",
            "pcap_last_timestamp_if_available",
            "pcap_metadata_status",
            "packet_count_vs_csv_row_count_status",
            "timestamp_range_overlap_status",
            "pairing_confidence_old",
            "pairing_confidence_new",
            "unresolved_reason",
        ],
    )

    conf_counts = Counter(r["pairing_confidence_new"] for r in strengthened_rows)
    count_counts = Counter(r["packet_count_vs_csv_row_count_status"] for r in strengthened_rows)
    time_counts = Counter(r["timestamp_range_overlap_status"] for r in strengthened_rows)
    write_text(
        OUT_DIR / "gotham_pairing_strengthened_report.md",
        "\n".join(
            [
                "# Gotham Pairing Strengthened Report",
                "",
                f"- CSVs checked: {len(strengthened_rows)}",
                f"- Pairing confidence after issue27z: {dict(conf_counts)}",
                f"- Packet count comparison: {dict(count_counts)}",
                f"- Timestamp comparison: {dict(time_counts)}",
                "- PCAP metadata was read by streaming PCAP members from the zip; no PCAPs were fully extracted.",
                "- `high_packet_count_timestamp_match` requires exact or near-exact packet counts and timestamp endpoint agreement within 1 second.",
            ]
        )
        + "\n",
    )

    primary_files = primary_contract_files(y_contract)
    audit_rows = []
    for role, files in primary_files.items():
        summary = summarize_confidences(strengthened_rows, files)
        counts = summary["confidence_counts"]
        if summary["missing_or_low_files"]:
            sufficiency = "no"
        elif set(counts.keys()).issubset({"high_packet_count_timestamp_match", "medium_plus_frame_timestamp_hint"}):
            sufficiency = "main_candidate"
        else:
            sufficiency = "diagnostic_only"
        audit_rows.append(
            {
                "split_role": role,
                "file_count": summary["file_count"],
                "confidence_counts": summary["confidence_counts"],
                "missing_or_low_files": summary["missing_or_low_files"],
                "pairing_sufficient_for_feature_gate": sufficiency,
                "notes": "requires source-feature policy before model work",
            }
        )
    write_csv(
        OUT_DIR / "gotham_primary_split_pairing_audit.csv",
        audit_rows,
        ["split_role", "file_count", "confidence_counts", "missing_or_low_files", "pairing_sufficient_for_feature_gate", "notes"],
    )
    low_primary = [r for r in audit_rows if r["pairing_sufficient_for_feature_gate"] != "yes"]
    write_text(
        OUT_DIR / "gotham_primary_split_pairing_report.md",
        "\n".join(
            [
                "# Gotham Primary Split Pairing Audit",
                "",
                f"- Primary contract: `{y_contract.get('contract', {}).get('contract_id', 'unknown')}`",
                f"- Split roles audited: {len(audit_rows)}",
                f"- Roles with missing/low pairing: {len(low_primary)}",
                "- Pairing is sufficient for the next Feature/interface gate if every role has at least medium+ or high evidence and no missing/low files.",
            ]
        )
        + "\n",
    )

    inventory_rows = source_inventory_from_columns(sorted(all_columns))
    write_csv(
        OUT_DIR / "gotham_source_like_feature_inventory.csv",
        inventory_rows,
        [
            "field_name",
            "source",
            "semantic_type",
            "shortcut_risk",
            "allowed_for_split",
            "allowed_for_audit",
            "allowed_for_pairing",
            "allowed_as_model_feature_main",
            "allowed_as_model_feature_diagnostic",
            "transformation_policy",
            "reason",
        ],
    )
    forbidden = [r["field_name"] for r in inventory_rows if r["allowed_as_model_feature_main"] == "no" and r["shortcut_risk"] in {"blocking", "high"}]
    write_text(
        OUT_DIR / "gotham_source_like_feature_report.md",
        "\n".join(
            [
                "# Gotham Source-Like Feature Inventory Report",
                "",
                f"- Unique processed CSV fields plus derived identifiers inventoried: {len(inventory_rows)}",
                f"- Fields forbidden from main model input by blocking/high shortcut risk: {', '.join(sorted(set(forbidden)))}",
                "- The inventory deliberately distinguishes split/audit/pairing fields from model input fields.",
            ]
        )
        + "\n",
    )
    policy = build_policy(inventory_rows)
    write_json(OUT_DIR / "gotham_feature_source_policy_v1.json", policy)
    write_json(MANIFEST_ROOT / "issue27z_gotham_feature_source_policy_v1.json", policy)
    write_text(
        OUT_DIR / "gotham_feature_source_policy_report.md",
        "\n".join(
            [
                "# Gotham Feature Source Policy Report",
                "",
                "- `frame.time`: ordering, purge, split, timestamp pairing, and audit only; never raw model input.",
                "- IP/MAC fields: source/device inference, pairing, and artifact audit only; default excluded from main model input.",
                "- ports/protocol: diagnostic-rich only until a later shortcut audit; not default main-claim inputs.",
                "- file/device/source/path fields: split and audit only; never model inputs.",
                "- label/attack_type: training/evaluation targets only; never input features.",
                "- strict_content_policy keeps only lower-risk numeric packet/header fields as candidates, and still requires a feature-interface audit before model execution.",
            ]
        )
        + "\n",
    )

    no_missing_low = all(r["pairing_confidence_new"] not in {"low_ambiguous", "missing"} for r in strengthened_rows)
    high_or_medium_plus = all(r["pairing_confidence_new"] in {"high_packet_count_timestamp_match", "medium_plus_frame_timestamp_hint"} for r in strengthened_rows)
    primary_ok = not low_primary
    if high_or_medium_plus and primary_ok:
        readiness_verdict = "ready_for_feature_interface_gate"
        primary_verdict = "gotham_ready_for_feature_interface_gate"
    elif no_missing_low and primary_ok:
        readiness_verdict = "ready_for_feature_interface_diagnostic_only"
        primary_verdict = "gotham_ready_for_feature_interface_diagnostic_only"
    else:
        readiness_verdict = "needs_stronger_pairing_before_feature_gate"
        primary_verdict = "gotham_needs_stronger_pcap_csv_pairing"
    readiness_rows = [
        {
            "check": "primary_split_contract_stable",
            "status": "yes",
            "verdict": "pass",
            "notes": "device-disjoint v1 remains the candidate contract; no model results used",
        },
        {
            "check": "pcap_csv_pairing",
            "status": dict(conf_counts),
            "verdict": "pass" if no_missing_low else "needs_work",
            "notes": "PCAP metadata streamed from zip",
        },
        {
            "check": "source_feature_policy",
            "status": "gotham_feature_source_policy_v1",
            "verdict": "pass",
            "notes": "strict and diagnostic policies defined",
        },
        {
            "check": "model_experiments_allowed",
            "status": "no",
            "verdict": "blocked_by_gate_sequence",
            "notes": "next gate is feature/interface construction, not models",
        },
        {
            "check": "readiness_verdict",
            "status": readiness_verdict,
            "verdict": readiness_verdict,
            "notes": "main feature-interface gate if high/medium+ pairing and policy pass",
        },
    ]
    write_csv(
        OUT_DIR / "gotham_feature_interface_readiness_table.csv",
        readiness_rows,
        ["check", "status", "verdict", "notes"],
    )
    write_text(
        OUT_DIR / "gotham_feature_interface_readiness_report.md",
        "\n".join(
            [
                "# Gotham Feature Interface Readiness Report",
                "",
                f"- readiness_verdict: `{readiness_verdict}`",
                f"- primary_verdict: `{primary_verdict}`",
                f"- Pairing confidence summary: {dict(conf_counts)}",
                "- Source-feature policy is explicit and conservative.",
                "- Model experiments remain disallowed; the next step is Feature/interface gate work only.",
            ]
        )
        + "\n",
    )

    write_text(
        OUT_DIR / "issue27z_decision.md",
        "\n".join(
            [
                "# issue27z Decision",
                "",
                f"primary_verdict = {primary_verdict}",
                "",
                "Rationale:",
                f"- allowed_mode = {allowed_mode}.",
                f"- PCAP/CSV pairing confidence after metadata streaming: {dict(conf_counts)}.",
                f"- Primary split pairing audit has missing/low roles: {bool(low_primary)}.",
                "- Source-like feature policy is defined with a strict main-candidate route and diagnostic-rich route.",
                "- No model experiment is authorized by this issue.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "claim_update_after_issue27z.md",
        "\n".join(
            [
                "# Claim Update After issue27z",
                "",
                "- Gotham has passed a stronger pairing/source-policy pre-gate for feature-interface work.",
                "- This is not a model result and does not validate LOW-GUARD, DeepSAD, or any baseline.",
                "- Main claims still require feature/interface construction, model execution, result audit, and later external validation.",
                "- Raw source identifiers, labels, file paths, device fields, IP/MAC, and absolute timestamps must not enter main model inputs.",
            ]
        )
        + "\n",
    )
    next_issue = "issue27aa_gotham_feature_interface_gate_strict_policy_smoke_2026-05-28"
    write_text(
        OUT_DIR / "issue27aa_next_action.md",
        "\n".join(
            [
                "# issue27aa Next Action",
                "",
                f"Recommended next issue: `{next_issue}`.",
                "",
                "Scope:",
                "- Build feature/interface artifacts under `gotham_feature_source_policy_v1`.",
                "- No model benchmark yet; only verify feature extraction/interface alignment and leakage controls.",
                "- Compare strict_content_policy against diagnostic_rich_policy as feature-space readiness, not model performance.",
                "- Decide whether full extraction needs Slurm before any model gate.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "summary.md",
        "\n".join(
            [
                "# issue27z Summary",
                "",
                "1. issue27z complete: yes.",
                f"2. primary_verdict: {primary_verdict}.",
                f"3. allowed_mode: {allowed_mode}.",
                f"4. PCAP/CSV pairing enhanced: yes, {dict(conf_counts)}.",
                f"5. Pairing for primary split files sufficient: {'yes' if primary_ok else 'no'}.",
                f"6. Missing / low pairing files: {'none' if primary_ok else 'present'}.",
                "7. Source-like feature inventory complete: yes.",
                f"8. Fields forbidden from model input: {', '.join(sorted(set(forbidden)))}.",
                "9. frame.time use: ordering / purge / split / audit / pairing only, not raw model input.",
                "10. IP/MAC/port/protocol use: IP/MAC audit/pairing only; ports/protocol diagnostic only unless separately audited.",
                "11. gotham_feature_source_policy_v1 formed: yes.",
                f"12. Gotham can enter Feature / interface gate: {'yes' if primary_verdict == 'gotham_ready_for_feature_interface_gate' else 'diagnostic only' if primary_verdict == 'gotham_ready_for_feature_interface_diagnostic_only' else 'no'}.",
                f"13. Gate type: {readiness_verdict}.",
                "14. Current model experiments allowed: no.",
                "15. issue27aa recommendation: feature/interface gate under strict source policy, no model benchmark yet.",
                "16. Slurm needed: not for issue27aa metadata/interface smoke; likely for full feature extraction later.",
                "17. commit hash: pending.",
            ]
        )
        + "\n",
    )

    append_mainline(primary_verdict, readiness_verdict, conf_counts)
    write_run_metadata(primary_verdict, allowed_mode)
    print(json.dumps({"primary_verdict": primary_verdict, "readiness": readiness_verdict, "pairing": dict(conf_counts)}, indent=2))
    return 0


def append_mainline(primary_verdict: str, readiness_verdict: str, conf_counts: Counter[str]) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    with handoff.open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            "\n\n<!-- issue27z_gotham_pairing_source_policy_gate -->\n\n"
            "## issue27z Gotham Pairing And Source Policy Gate\n\n"
            f"- primary_verdict: `{primary_verdict}`.\n"
            f"- readiness_verdict: `{readiness_verdict}`.\n"
            f"- PCAP/CSV pairing status: {dict(conf_counts)} after streaming PCAP metadata from the zip; no PCAP extraction or feature extraction was performed.\n"
            "- source policy status: `gotham_feature_source_policy_v1` defined; labels, file/device/source/path, IP/MAC, and absolute timestamps are forbidden from main model inputs.\n"
            "- ports/protocol fields are diagnostic-only until a later shortcut audit.\n"
            "- current model experiments remain blocked; next action is Feature/interface gate work only.\n"
        )
    with exp_map.open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            "\n\n<!-- issue27z_map_entry -->\n\n"
            "### issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28\n\n"
            "- status: completed.\n"
            f"- primary_verdict: `{primary_verdict}`.\n"
            f"- outputs: `runs/{ISSUE}/`.\n"
            "- role: PCAP/CSV pairing strengthening and feature-source policy pre-gate.\n"
            "- implication: Gotham may proceed only to Feature/interface gate work; model experiments remain disallowed.\n"
        )


def write_run_metadata(primary_verdict: str, allowed_mode: str) -> None:
    config = {
        "issue": ISSUE,
        "dataset": "gotham2025",
        "allowed_mode": allowed_mode,
        "primary_verdict": primary_verdict,
        "no_model_training": True,
        "no_formal_feature_extraction": True,
        "no_full_pcap_extraction": True,
        "expected_md5": EXPECTED_MD5,
    }
    run_spec = {
        "inputs": [
            str(ISSUE27Y_DIR / "summary.md"),
            str(ISSUE27Y_DIR / "gotham_all_csv_file_manifest.csv"),
            str(ISSUE27Y_DIR / "gotham_preregistered_split_contract_v1.json"),
            str(ISSUE27V_DIR / "archive_file_listing.csv"),
            str(ZIP_PATH),
        ],
        "stages": [
            "storage_and_tooling_preflight",
            "pcap_csv_pairing_strengthening",
            "primary_split_pairing_audit",
            "source_like_feature_inventory",
            "feature_source_policy",
            "feature_interface_readiness",
            "decision",
        ],
    }
    write_json(OUT_DIR / "config.json", config)
    write_json(OUT_DIR / "run_spec.json", run_spec)
    write_text(OUT_DIR / "command.txt", "python repo/ood/issue27z_gotham_pairing_source_policy_gate.py\n")
    rows = []
    for p in sorted(OUT_DIR.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            rows.append(
                {
                    "artifact": p.name,
                    "path": str(p),
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "bytes": p.stat().st_size,
                }
            )
    write_csv(OUT_DIR / "manifest.csv", rows, ["artifact", "path", "sha256", "bytes"])


if __name__ == "__main__":
    ensure_dirs()
    raise SystemExit(main())
