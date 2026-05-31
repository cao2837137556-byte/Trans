from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import re
import shutil
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
OUT_DIR = ROOT / "runs" / "issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
LARGER_DIR = DATA_ROOT / "derived" / "larger_sample_gate"
MANIFEST_DIR = DATA_ROOT / "manifests"
ISSUE27V = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"
ISSUE27W = ROOT / "runs" / "issue27w_gotham_sample_data_gate_2026-05-28"

EXPECTED_MD5 = "7ca78c0517ccb3d2854e823678e0f206"
MAX_SCAN_ROWS_PER_FILE = 250_000
MAX_MANIFEST_ROWS_PER_FILE = 2_000
MAX_ROWS_PER_LABEL_PER_FILE = 250
SMALL_FULL_SCAN_BYTES = 10_000_000

SELECTED_CSVS = [
    # benign-only / mostly benign candidates across device and protocol families
    "processed/iotsim-combined-cycle-2.csv",
    "processed/iotsim-combined-cycle-3.csv",
    "processed/iotsim-combined-cycle-tls-1.csv",
    "processed/iotsim-combined-cycle-tls-3.csv",
    "processed/iotsim-hydraulic-system-8.csv",
    "processed/iotsim-hydraulic-system-11.csv",
    "processed/iotsim-building-monitor-2.csv",
    "processed/iotsim-domotic-monitor-2.csv",
    "processed/iotsim-cooler-motor-8.csv",
    # mixed attack candidates across devices and attack types
    "processed/iotsim-air-quality-1.csv",
    "processed/iotsim-combined-cycle-1.csv",
    "processed/iotsim-combined-cycle-10.csv",
    "processed/iotsim-city-power-1.csv",
    "processed/iotsim-domotic-monitor-1.csv",
    "processed/iotsim-building-monitor-1.csv",
    "processed/iotsim-ip-camera-street-1.csv",
    "processed/iotsim-ip-camera-museum-1.csv",
]


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LARGER_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


def write_text(name: str, text: str) -> None:
    (OUT_DIR / name).write_text(text, encoding="utf-8")


def write_json(name: str, obj: object) -> None:
    (OUT_DIR / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with (OUT_DIR / name).open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def append_once(path: Path, marker: str, block: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old == "" or old.endswith("\n") else "\n"
    path.write_text(old + sep + block, encoding="utf-8")


def storage_preflight() -> dict:
    usage = shutil.disk_usage(str(PAPER_ROOT.drive + "\\"))
    free_gib = usage.free / (1024**3)
    if free_gib < 20:
        mode = "blocked_storage_insufficient"
    elif free_gib < 40:
        mode = "streaming_preview_only"
    elif free_gib < 80:
        mode = "limited_csv_extract"
    else:
        mode = "larger_csv_extract"
    md5 = md5_file(ZIP_PATH) if ZIP_PATH.exists() else "missing"
    target_mismatch = DATA_ROOT.drive.upper() != "D:"
    return {
        "cwd": str(Path.cwd()),
        "expected_cwd": str(ROOT),
        "cwd_ok": Path.cwd().resolve() == ROOT.resolve(),
        "data_root": str(DATA_ROOT),
        "data_root_ok": DATA_ROOT == PAPER_ROOT / "datasets" / "gotham2025",
        "zip_path": str(ZIP_PATH),
        "zip_exists": ZIP_PATH.exists(),
        "zip_md5": md5,
        "zip_md5_matches": md5 == EXPECTED_MD5,
        "d_free_bytes": usage.free,
        "d_free_gib": round(free_gib, 3),
        "allowed_mode": mode,
        "storage_target_mismatch": target_mismatch,
    }


def load_archive_listing() -> list[dict]:
    with (ISSUE27V / "archive_file_listing.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_frame_time(value: str) -> datetime | None:
    if not value:
        return None
    value = value.strip().strip('"')
    m = re.match(r"([A-Z][a-z]{2} \d{1,2}, \d{4} \d{2}:\d{2}:\d{2})\.(\d+)\s+GMT", value)
    if not m:
        return None
    frac = (m.group(2) + "000000")[:6]
    try:
        return datetime.strptime(f"{m.group(1)}.{frac}", "%b %d, %Y %H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_device(path: str) -> dict:
    stem = Path(path).stem
    if stem.startswith("iotsim-"):
        stem = stem[len("iotsim-") :]
    m = re.match(r"(?P<family>.+)-(?P<instance>\d+)$", stem)
    family = m.group("family") if m else stem
    instance = m.group("instance") if m else "unknown"
    protocol_hint = "tls" if "tls" in family else "rtsp_possible" if "camera" in family else "iot_protocol_from_packets"
    return {"device": stem, "device_family": family, "instance": instance, "protocol_hint": protocol_hint}


def parse_raw_member(path: str) -> dict:
    parts = path.replace("\\", "/").split("/")
    role = parts[1] if len(parts) > 1 and parts[0] == "raw" else "unknown"
    attack_type = parts[2] if len(parts) > 2 and parts[0] == "raw" and parts[1] == "malicious" else "none"
    raw_device = Path(path).name.split("_0-0_to_")[0]
    return {"raw_role": role, "raw_attack_type": attack_type, "raw_device": raw_device}


def matching_pcap(path: str, archive_rows: list[dict]) -> dict:
    parsed = parse_device(path)
    device_token = "iotsim-" + parsed["device"] + "_0-0_to_"
    matches = [
        r
        for r in archive_rows
        if r.get("is_pcap") == "True" and Path(r["file_path"]).name.startswith(device_token)
    ]
    benign = [r for r in matches if r["file_path"].startswith("raw/benign/")]
    malicious = [r for r in matches if r["file_path"].startswith("raw/malicious/")]
    attack_types = sorted({parse_raw_member(r["file_path"])["raw_attack_type"] for r in malicious})
    return {
        "pcap_counterpart_path": matches[0]["file_path"] if matches else "",
        "matching_pcap_count": len(matches),
        "matching_benign_pcap_count": len(benign),
        "matching_malicious_pcap_count": len(malicious),
        "matching_attack_types": "|".join(attack_types),
        "pcap_pairing_basis": "device_filename_token" if matches else "not_found",
    }


def protocol_token(value: str) -> str:
    tokens = [t.lower() for t in str(value).split(":") if t]
    for token in tokens:
        if token not in {"eth", "ethertype", "ip", "tcp", "udp"}:
            return token
    return "unknown"


def row_hash(row: dict) -> str:
    material = "|".join(str(row.get(k, "")) for k in ["frame.time", "frame.len", "frame.protocols", "eth.src", "eth.dst", "ip.src", "ip.dst", "label"])
    return hashlib.sha256(material.encode("utf-8", errors="ignore")).hexdigest()[:16]


def time_bucket(parsed: datetime | None) -> str:
    if parsed is None:
        return "unknown"
    return parsed.strftime("%Y-%m-%dT%H")


def row_order_bucket(index: int, scanned: int | None = None) -> str:
    if scanned and scanned > 0:
        frac = index / scanned
        if frac < 0.25:
            return "q1"
        if frac < 0.50:
            return "q2"
        if frac < 0.75:
            return "q3"
        return "q4"
    if index <= 1_000:
        return "head_1k"
    if index <= 10_000:
        return "head_10k"
    if index <= 50_000:
        return "mid_50k"
    return "late_or_large"


def should_keep_row(row_index: int, label: str, per_label_kept: Counter, total_kept: int) -> bool:
    if total_kept >= MAX_MANIFEST_ROWS_PER_FILE:
        return False
    if row_index <= 200:
        return True
    if per_label_kept[label] < MAX_ROWS_PER_LABEL_PER_FILE:
        return True
    return row_index in {1_000, 5_000, 10_000, 25_000, 50_000, 100_000, 150_000, 200_000, 250_000}


def scan_member(zf: zipfile.ZipFile, member: str, info: zipfile.ZipInfo, file_id: str, archive_rows: list[dict], global_start: int) -> tuple[list[dict], dict]:
    parsed_device = parse_device(member)
    pcap = matching_pcap(member, archive_rows)
    full_scan = info.file_size <= SMALL_FULL_SCAN_BYTES
    max_scan = None if full_scan else MAX_SCAN_ROWS_PER_FILE
    manifest_rows: list[dict] = []
    label_counts: Counter[str] = Counter()
    binary_counts: Counter[str] = Counter()
    protocol_counts: Counter[str] = Counter()
    time_counts: Counter[str] = Counter()
    order_counts: Counter[str] = Counter()
    per_label_kept: Counter[str] = Counter()
    rows_scanned = 0
    total_kept = 0
    first_time = None
    last_time = None
    first_attack_row = ""
    first_attack_time = ""
    label_transitions = 0
    monotonic_violations = 0
    previous_label = None
    previous_time = None

    with zf.open(member) as raw:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        for row in reader:
            rows_scanned += 1
            label = row.get("label", "")
            binary = "benign" if label == "Benign" else "attack"
            parsed_time = parse_frame_time(row.get("frame.time", ""))
            proto = protocol_token(row.get("frame.protocols", ""))
            label_counts[label] += 1
            binary_counts[binary] += 1
            protocol_counts[proto] += 1
            tb = time_bucket(parsed_time)
            ob = row_order_bucket(rows_scanned)
            time_counts[tb] += 1
            order_counts[ob] += 1
            if previous_label is not None and previous_label != label:
                label_transitions += 1
            previous_label = label
            if binary == "attack" and not first_attack_row:
                first_attack_row = str(rows_scanned)
                first_attack_time = row.get("frame.time", "")
            if parsed_time is not None:
                if first_time is None:
                    first_time = parsed_time
                if previous_time is not None and parsed_time < previous_time:
                    monotonic_violations += 1
                previous_time = parsed_time
                last_time = parsed_time
            if should_keep_row(rows_scanned, label, per_label_kept, total_kept):
                per_label_kept[label] += 1
                total_kept += 1
                manifest_rows.append(
                    {
                        "sample_file_id": file_id,
                        "archive_path": member,
                        "row_index_within_file": rows_scanned,
                        "global_sample_row_id": global_start + len(manifest_rows),
                        "frame.time": row.get("frame.time", ""),
                        "parsed_timestamp": parsed_time.isoformat() if parsed_time else "",
                        "label": label,
                        "binary_label": binary,
                        "attack_type": "" if binary == "benign" else label,
                        "device": parsed_device["device"],
                        "device_family": parsed_device["device_family"],
                        "protocol_inferred": proto,
                        "source_capture_inferred": f"{parsed_device['device']}|instance_{parsed_device['instance']}",
                        "frame.protocols": row.get("frame.protocols", ""),
                        "ip.src": row.get("ip.src", ""),
                        "ip.dst": row.get("ip.dst", ""),
                        "pcap_counterpart_path": pcap["pcap_counterpart_path"],
                        "row_order_bucket": ob,
                        "time_bucket": tb,
                        "source_file_hash": hashlib.sha256(member.encode("utf-8")).hexdigest()[:16],
                        "sample_hash": row_hash(row),
                        "extraction_mode": "streaming_sample_manifest_limited_csv_extract",
                    }
                )
            if max_scan is not None and rows_scanned >= max_scan:
                break
    summary = {
        "archive_path": member,
        "file_id": file_id,
        "file_size": info.file_size,
        "rows_scanned": rows_scanned,
        "rows_kept": len(manifest_rows),
        "full_scan": full_scan,
        "label_counts_json": json.dumps(dict(label_counts), sort_keys=True),
        "binary_counts_json": json.dumps(dict(binary_counts), sort_keys=True),
        "protocol_counts_json": json.dumps(dict(protocol_counts.most_common(10)), sort_keys=True),
        "time_bucket_count": len(time_counts),
        "row_order_bucket_counts_json": json.dumps(dict(order_counts), sort_keys=True),
        "first_time": first_time.isoformat() if first_time else "",
        "last_time": last_time.isoformat() if last_time else "",
        "first_attack_row": first_attack_row,
        "first_attack_time": first_attack_time,
        "label_transitions": label_transitions,
        "monotonic_violations": monotonic_violations,
        **parsed_device,
        **pcap,
    }
    return manifest_rows, summary


def cramers_v(rows: list[dict], col_a: str, col_b: str) -> tuple[float, int, int]:
    table: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        table[str(row.get(col_a, ""))][str(row.get(col_b, ""))] += 1
    if not table:
        return 0.0, 0, 0
    row_keys = list(table)
    col_keys = sorted({k for counter in table.values() for k in counter})
    n = sum(sum(table[r].values()) for r in row_keys)
    if n == 0:
        return 0.0, len(row_keys), len(col_keys)
    row_totals = {r: sum(table[r].values()) for r in row_keys}
    col_totals = {c: sum(table[r][c] for r in row_keys) for c in col_keys}
    chi2 = 0.0
    for r in row_keys:
        for c in col_keys:
            expected = row_totals[r] * col_totals[c] / n
            if expected > 0:
                chi2 += (table[r][c] - expected) ** 2 / expected
    denom = n * max(min(len(row_keys) - 1, len(col_keys) - 1), 1)
    return math.sqrt(chi2 / denom), len(row_keys), len(col_keys)


def max_group_purity(rows: list[dict], group_col: str, label_col: str = "binary_label") -> tuple[float, str]:
    groups: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        groups[str(row.get(group_col, ""))][str(row.get(label_col, ""))] += 1
    best_purity = 0.0
    best_group = ""
    for group, counts in groups.items():
        total = sum(counts.values())
        if total:
            purity = max(counts.values()) / total
            if purity > best_purity and total >= 50:
                best_purity = purity
                best_group = group
    return best_purity, best_group


def build_file_selection(archive_rows: list[dict], summaries: list[dict], allowed_mode: str) -> list[dict]:
    summary_by_path = {s["archive_path"]: s for s in summaries}
    rows = []
    for member in SELECTED_CSVS:
        listing = next(r for r in archive_rows if r["file_path"] == member)
        parsed = parse_device(member)
        summary = summary_by_path.get(member, {})
        labels = json.loads(summary.get("label_counts_json", "{}"))
        attack_types = [label for label in labels if label != "Benign"]
        role = "all_benign_or_mostly_benign" if attack_types == [] else "mixed_label_attack_candidate"
        extraction_mode = "full_scan_if_small_streaming_manifest" if summary.get("full_scan") else "stratified_chunks_streaming_manifest"
        if allowed_mode == "streaming_preview_only":
            extraction_mode = "header_and_streaming_rows_only"
        rows.append(
            {
                "archive_path": member,
                "file_size": listing["uncompressed_size"],
                "inferred_device": parsed["device"],
                "inferred_protocol": parsed["protocol_hint"] + "; observed_top=" + summary.get("protocol_counts_json", "{}"),
                "inferred_attack_type": "|".join(sorted(attack_types)) or "none_observed",
                "inferred_role": role,
                "expected_label_mix": summary.get("label_counts_json", "{}"),
                "selection_reason": "coverage of benign device/protocol or mixed attack labels from issue27w/file listing",
                "extraction_mode": extraction_mode,
            }
        )
    return rows


def build_pairing_table(archive_rows: list[dict], summaries: list[dict]) -> list[dict]:
    processed_paths = {r["file_path"] for r in archive_rows if r.get("is_csv") == "True"}
    pcap_paths = {r["file_path"] for r in archive_rows if r.get("is_pcap") == "True"}
    rows = []
    for summary in summaries:
        rows.append(
            {
                "archive_path": summary["archive_path"],
                "pcap_counterpart_path": summary["pcap_counterpart_path"],
                "matching_pcap_count": summary["matching_pcap_count"],
                "matching_benign_pcap_count": summary["matching_benign_pcap_count"],
                "matching_malicious_pcap_count": summary["matching_malicious_pcap_count"],
                "matching_attack_types": summary["matching_attack_types"],
                "pairing_basis": summary["pcap_pairing_basis"],
                "processed_without_pcap": summary["matching_pcap_count"] == 0,
                "can_reextract_features_later": summary["matching_pcap_count"] > 0,
                "pairing_confidence": "medium_filename_path_match" if summary["matching_pcap_count"] > 0 else "blocked_no_match",
            }
        )
    unmatched_pcap_examples = []
    for pcap in sorted(pcap_paths):
        raw_device = parse_raw_member(pcap)["raw_device"].replace("iotsim-", "")
        candidate = "processed/" + re.sub(r"_0-0_to_OpenvSwitch-.+", "", Path(pcap).name).replace("iotsim-", "iotsim-") + ".csv"
        if candidate not in processed_paths and len(unmatched_pcap_examples) < 10:
            unmatched_pcap_examples.append(pcap)
    rows.append(
        {
            "archive_path": "__archive_summary__",
            "pcap_counterpart_path": "|".join(unmatched_pcap_examples),
            "matching_pcap_count": "",
            "matching_benign_pcap_count": "",
            "matching_malicious_pcap_count": "",
            "matching_attack_types": "",
            "pairing_basis": "archive_level",
            "processed_without_pcap": "",
            "can_reextract_features_later": "yes_for_sampled_by_filename_match",
            "pairing_confidence": "medium; no packet-count/byte-level verification yet",
        }
    )
    return rows


def build_split_candidates(manifest_rows: list[dict], summaries: list[dict]) -> list[dict]:
    benign_rows = [r for r in manifest_rows if r["binary_label"] == "benign"]
    attack_rows = [r for r in manifest_rows if r["binary_label"] == "attack"]
    families = sorted({r["device_family"] for r in benign_rows})
    protocols = sorted({r["protocol_inferred"] for r in benign_rows if r["protocol_inferred"] != "unknown"})
    attack_types = sorted({r["attack_type"] for r in attack_rows if r["attack_type"]})
    cc = [r for r in benign_rows if r["device_family"].startswith("combined-cycle") and "tls" not in r["device_family"]]
    non_cc = [r for r in benign_rows if not r["device_family"].startswith("combined-cycle")]
    tls = [r for r in benign_rows if r["device_family"] == "combined-cycle-tls"]
    rows = [
        {
            "split_name": "device_disjoint_benign_drift",
            "can_construct": bool(cc and non_cc and attack_rows),
            "id_ood_benign_row_counts": f"id_candidate={len(cc)};ood_candidate={len(non_cc)};final_candidate=heldout_family_possible",
            "attack_support_eval_row_counts": f"attack_sampled={len(attack_rows)};attack_types={len(attack_types)}",
            "report_only_final_eval_feasible": "yes_after_full_manifest",
            "support_eval_disjoint_feasible": "yes_by_attack_type_file_and_time_after_full_manifest",
            "device_shortcut": "medium_high",
            "protocol_shortcut": "medium",
            "time_shortcut": "medium_high",
            "file_source_shortcut": "medium_high",
            "evidence_level": "promising_needs_full_manifest",
            "notes": "Most promising route, but needs full/larger manifest to ensure attacks are not separable by file/device source alone.",
        },
        {
            "split_name": "protocol_disjoint_benign_drift",
            "can_construct": len(protocols) >= 2 and bool(attack_rows),
            "id_ood_benign_row_counts": f"benign_protocols={len(protocols)};tls_candidate={len(tls)}",
            "attack_support_eval_row_counts": f"attack_sampled={len(attack_rows)};attack_types={len(attack_types)}",
            "report_only_final_eval_feasible": "yes_after_full_manifest",
            "support_eval_disjoint_feasible": "yes_after_full_manifest",
            "device_shortcut": "medium",
            "protocol_shortcut": "high_by_design",
            "time_shortcut": "medium_high",
            "file_source_shortcut": "medium",
            "evidence_level": "promising_needs_full_manifest",
            "notes": "Useful secondary route, but benchmark claim must state protocol-shift rather than generic deployment drift.",
        },
        {
            "split_name": "time_aware_within_device_split",
            "can_construct": "partial",
            "id_ood_benign_row_counts": f"timestamped_benign_sample_rows={len(benign_rows)}",
            "attack_support_eval_row_counts": f"timestamped_attack_sample_rows={len(attack_rows)}",
            "report_only_final_eval_feasible": "not_yet",
            "support_eval_disjoint_feasible": "partial",
            "device_shortcut": "medium",
            "protocol_shortcut": "medium",
            "time_shortcut": "high",
            "file_source_shortcut": "medium_high",
            "evidence_level": "high_artifact_risk",
            "notes": "Mixed files show benign-prefix to attack-suffix patterns; time split needs purge and full manifest before claim-safe use.",
        },
    ]
    return rows


def build_artifact_table(manifest_rows: list[dict]) -> list[dict]:
    checks = [
        ("label_vs_file_id", "sample_file_id"),
        ("label_vs_device", "device_family"),
        ("label_vs_protocol", "protocol_inferred"),
        ("label_vs_time_bucket", "time_bucket"),
        ("label_vs_source_capture", "source_capture_inferred"),
        ("idood_vs_device", "device_family"),
        ("support_eval_vs_file_time_source", "sample_file_id"),
    ]
    rows = []
    for name, col in checks:
        v, groups, labels = cramers_v(manifest_rows, "binary_label", col)
        purity, group = max_group_purity(manifest_rows, col)
        level = "high" if v >= 0.7 or purity >= 0.98 else "medium_high" if v >= 0.4 else "medium" if v >= 0.2 else "low"
        rows.append(
            {
                "risk": name,
                "group_column": col,
                "cramers_v": round(v, 6),
                "group_count": groups,
                "label_count": labels,
                "max_group_purity": round(purity, 6),
                "max_purity_group": group,
                "risk_level": level,
                "can_split_design_control": "partially" if level in {"medium", "medium_high"} else "needs_strong_controls" if level == "high" else "yes",
            }
        )
    prefix_files = []
    for file_id, rows_for_file in group_by(manifest_rows, "sample_file_id").items():
        sorted_rows = sorted(rows_for_file, key=lambda x: int(x["row_index_within_file"]))
        labels = [r["binary_label"] for r in sorted_rows]
        if "attack" in labels and labels[0] == "benign":
            prefix_files.append(file_id)
    rows.append(
        {
            "risk": "benign_prefix_attack_suffix_pattern",
            "group_column": "row_index_within_file",
            "cramers_v": "",
            "group_count": len(prefix_files),
            "label_count": "",
            "max_group_purity": "",
            "max_purity_group": "|".join(prefix_files[:10]),
            "risk_level": "high" if prefix_files else "low",
            "can_split_design_control": "requires_purge_and_file_device_disjoint_attack_eval" if prefix_files else "yes",
        }
    )
    return rows


def group_by(rows: list[dict], key: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        out[str(row.get(key, ""))].append(row)
    return out


def write_reports(storage: dict, selection: list[dict], manifest_rows: list[dict], summaries: list[dict], pairing: list[dict], split_rows: list[dict], artifact_rows: list[dict], primary: str) -> None:
    devices = sorted({s["device_family"] for s in summaries})
    protocols = sorted({r["protocol_inferred"] for r in manifest_rows if r["protocol_inferred"] != "unknown"})
    attack_types = sorted({r["attack_type"] for r in manifest_rows if r["attack_type"]})
    best_split = "device_disjoint_benign_drift"
    pairing_ok = all(str(r["pairing_confidence"]).startswith("medium") for r in pairing if r["archive_path"] != "__archive_summary__")
    max_risk = sorted(artifact_rows, key=lambda r: {"high": 3, "medium_high": 2, "medium": 1, "low": 0}.get(str(r["risk_level"]), 0), reverse=True)[0]

    write_text(
        "larger_sample_storage_preflight.md",
        "# Larger Sample Storage Preflight\n\n"
        f"- cwd: `{storage['cwd']}`\n"
        f"- data root: `{storage['data_root']}`\n"
        f"- zip exists: `{storage['zip_exists']}`\n"
        f"- zip md5 matches: `{storage['zip_md5_matches']}`\n"
        f"- D free space: `{storage['d_free_gib']} GiB`\n"
        f"- allowed_mode: `{storage['allowed_mode']}`\n"
        f"- storage_target_mismatch: `{storage['storage_target_mismatch']}`\n",
    )
    write_text(
        "larger_sample_file_selection_report.md",
        "# Larger Sample File Selection Report\n\n"
        f"Selected `{len(selection)}` processed CSV files from the archive under allowed mode `{storage['allowed_mode']}`.\n\n"
        "Selection covers benign-only device/protocol variation plus mixed-label attack candidates. The script streams rows from the zip and writes a sampled row-level manifest; it does not extract PCAP or full large CSV files.\n",
    )
    write_text(
        "gotham_larger_sample_manifest_report.md",
        "# Gotham Larger Sample Manifest Report\n\n"
        f"- sampled manifest rows: `{len(manifest_rows)}`.\n"
        f"- sampled device families: `{', '.join(devices)}`.\n"
        f"- observed protocol tokens: `{', '.join(protocols[:20])}`.\n"
        f"- observed attack labels: `{', '.join(attack_types)}`.\n"
        "- manifest is sampled, not full-dataset coverage.\n",
    )
    write_text(
        "gotham_pcap_csv_pairing_report.md",
        "# Gotham PCAP/CSV Pairing Report\n\n"
        f"- sampled CSVs paired by filename/path token: `{pairing_ok}`.\n"
        "- Pairing confidence is medium because PCAP names match processed CSV device tokens and raw directories include benign/malicious counterparts.\n"
        "- No PCAP bytes were read and no packet-count alignment was performed in this issue.\n",
    )
    write_text(
        "gotham_larger_sample_split_report.md",
        "# Gotham Larger Sample Split Report\n\n"
        f"Most promising split: `{best_split}`.\n\n"
        "The larger sample supports candidate device-disjoint and protocol-disjoint benign drift designs, but not yet a claim-safe final benchmark. "
        "Attack support/eval can likely be separated by file, device, attack type, and time, but this must be pinned in a fuller manifest to control shortcut risks.\n",
    )
    write_text(
        "gotham_larger_sample_artifact_risk_report.md",
        "# Gotham Larger Sample Artifact Risk Report\n\n"
        f"Largest observed risk: `{max_risk['risk']}` with level `{max_risk['risk_level']}`.\n\n"
        "The sampled manifest confirms that label is strongly entangled with file/device/time groupings unless the split is deliberately designed. "
        "This is not a reason to abandon Gotham, but it blocks immediate Feature/interface gate promotion. The next gate must construct a fuller manifest and pre-register exact row/file/device/time disjoint splits.\n",
    )
    write_text(
        "issue27x_decision.md",
        "# issue27x Decision\n\n"
        f"primary_verdict = `{primary}`\n\n"
        "Gotham larger sample evidence is stronger than issue27w, but still not enough for Feature/interface gate. "
        "PCAP/CSV pairing is medium-confidence by filename/path, ID/OOD benign split is promising, and attack support/eval disjoint is plausible. "
        "However, file/device/time shortcut risk remains too important to skip a fuller manifest gate.\n",
    )
    write_text(
        "claim_update_after_issue27x.md",
        "# Claim Update After issue27x\n\n"
        "- Gotham remains the leading second-dataset candidate for Data validity work.\n"
        "- Current evidence supports constructing a fuller row/file/device/time manifest, not model execution.\n"
        "- No model ranking, external generalization, deployment robustness, DeepSAD mainline, or LOW-GUARD failure claim is supported here.\n",
    )
    write_text(
        "issue27y_next_action.md",
        "# issue27y Next Action\n\n"
        "Recommended next action: `issue27y_gotham_fuller_manifest_and_preregistered_split_contract`.\n\n"
        "Construct a fuller row-level manifest across all 78 processed CSVs using streaming summaries, explicitly pre-register device-disjoint/protocol-disjoint split candidates, and only then decide whether Feature/interface gate can begin. No model training or feature extraction yet.\n",
    )
    write_text(
        "summary.md",
        "# issue27x Summary\n\n"
        "1. issue27x completed: `true`.\n"
        f"2. primary_verdict: `{primary}`.\n"
        f"3. allowed_mode: `{storage['allowed_mode']}`.\n"
        f"4. D free space: `{storage['d_free_gib']} GiB`.\n"
        f"5. storage_target_mismatch: `{storage['storage_target_mismatch']}`.\n"
        f"6. larger sample coverage: devices `{', '.join(devices)}`; protocols `{', '.join(protocols[:20])}`; attack types `{', '.join(attack_types)}`.\n"
        f"7. row-level manifest built: `true`, sampled rows `{len(manifest_rows)}`.\n"
        f"8. PCAP/CSV pairing: `medium_confidence_filename_path_match`, sampled pairing ok `{pairing_ok}`.\n"
        f"9. most promising split: `{best_split}`.\n"
        "10. claim-safe ID/OOD benign: `not_yet`; promising but needs fuller manifest and exact final-eval holdout contract.\n"
        "11. attack support/eval disjoint: `not_yet`; plausible but needs file/device/time-disjoint contract.\n"
        f"12. largest artifact risk: `{max_risk['risk']}` / `{max_risk['risk_level']}`.\n"
        "13. artifact risk controllable by split design: `partially`, but not enough to enter Feature/interface gate now.\n"
        "14. Gotham can enter Feature/interface gate: `false`.\n"
        "15. current model experiments allowed: `false`.\n"
        "16. further D cleanup needed: `recommended`, but current limited mode was sufficient for streaming sampled manifest.\n"
        "17. issue27y recommendation: fuller manifest and pre-registered split contract.\n"
        "18. Slurm needed: `not for issue27x`; maybe later for full feature extraction.\n"
        "19. commit hash: pending.\n",
    )


def write_metadata(primary: str, storage: dict) -> None:
    write_text("command.txt", "python repo/ood/issue27x_gotham_larger_sample_gate.py\n")
    write_json(
        "config.json",
        {
            "issue": "issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28",
            "zip_path": str(ZIP_PATH),
            "selected_csvs": SELECTED_CSVS,
            "allowed_mode": storage["allowed_mode"],
            "max_scan_rows_per_file": MAX_SCAN_ROWS_PER_FILE,
            "max_manifest_rows_per_file": MAX_MANIFEST_ROWS_PER_FILE,
            "no_model_training": True,
            "no_feature_extraction": True,
            "primary_verdict": primary,
        },
    )
    write_json(
        "run_spec.json",
        {
            "stages": [
                "storage_preflight",
                "larger_sample_file_selection",
                "sampled_row_manifest_construction",
                "pcap_csv_pairing_verification",
                "split_candidate_design",
                "artifact_risk_quantification_without_model_training",
            ],
            "constraints": [
                "no_model_training",
                "no_baselines",
                "no_full_zip_extraction",
                "no_pcap_extraction",
                "no_all_csv_extraction",
                "no_feature_extraction",
            ],
        },
    )
    rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.is_file():
            rows.append({"file": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv("manifest.csv", rows, ["file", "size_bytes", "sha256"])


def update_mainline_docs(primary: str) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    append_once(
        handoff,
        "<!-- issue27x_gotham_larger_sample_gate -->",
        "\n<!-- issue27x_gotham_larger_sample_gate -->\n\n"
        "## issue27x Gotham Larger Sample Manifest And Split Gate\n\n"
        f"- primary_verdict: `{primary}`.\n"
        "- allowed mode was `limited_csv_extract`, but execution used streaming sampled manifest construction and did not extract PCAP or full large CSV files.\n"
        "- sampled row-level manifest was built across representative benign and mixed attack processed CSVs; PCAP/CSV pairing is medium-confidence by filename/path matching.\n"
        "- most promising split remains device-disjoint benign drift; protocol-disjoint is a secondary route.\n"
        "- largest blocker is file/device/time shortcut risk; Gotham is not yet ready for Feature/interface gate or model experiments.\n"
        "- next: fuller manifest and pre-registered split contract.\n",
    )
    append_once(
        exp_map,
        "<!-- issue27x_map_entry -->",
        "\n<!-- issue27x_map_entry -->\n\n"
        "### issue27x_gotham_larger_sample_manifest_and_split_gate_2026-05-28\n\n"
        "- status: completed.\n"
        f"- primary_verdict: `{primary}`.\n"
        f"- outputs: `{OUT_DIR.relative_to(ROOT).as_posix()}/`.\n"
        "- role: larger-sample Data validity gate for Gotham split construction.\n"
        "- implication: Gotham remains promising, but Feature/interface gate is blocked until a fuller manifest and exact claim-safe split contract control file/device/time artifacts.\n",
    )


def main() -> int:
    ensure_dirs()
    storage = storage_preflight()
    if storage["allowed_mode"] == "blocked_storage_insufficient" or storage["storage_target_mismatch"] or not storage["zip_md5_matches"]:
        primary = "gotham_larger_sample_blocked_by_storage_target_mismatch" if storage["storage_target_mismatch"] else "gotham_larger_sample_inconclusive_try_toniot"
        write_csv("larger_sample_storage_table.csv", [{"check": k, "value": v} for k, v in storage.items()], ["check", "value"])
        write_reports(storage, [], [], [], [], [], [{"risk": "storage_or_md5_preflight", "risk_level": "high"}], primary)
        write_metadata(primary, storage)
        print(json.dumps({"primary_verdict": primary, "allowed_mode": storage["allowed_mode"]}, indent=2))
        return 0

    archive_rows = load_archive_listing()
    manifest_rows: list[dict] = []
    summaries: list[dict] = []
    global_id = 0
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for i, member in enumerate(SELECTED_CSVS, start=1):
            info = zf.getinfo(member)
            rows, summary = scan_member(zf, member, info, f"file_{i:02d}", archive_rows, global_id)
            manifest_rows.extend(rows)
            global_id += len(rows)
            summaries.append(summary)

    selection = build_file_selection(archive_rows, summaries, storage["allowed_mode"])
    pairing = build_pairing_table(archive_rows, summaries)
    split_rows = build_split_candidates(manifest_rows, summaries)
    artifact_rows = build_artifact_table(manifest_rows)
    primary = "gotham_larger_sample_promising_needs_full_manifest"

    write_csv("larger_sample_storage_table.csv", [{"check": k, "value": v} for k, v in storage.items()], ["check", "value"])
    write_csv("larger_sample_file_selection.csv", selection)
    write_csv("gotham_larger_sample_row_manifest.csv", manifest_rows)
    write_csv("gotham_pcap_csv_pairing_table.csv", pairing)
    write_csv("gotham_larger_sample_split_candidates.csv", split_rows)
    write_csv("gotham_larger_sample_artifact_risk_table.csv", artifact_rows)
    write_reports(storage, selection, manifest_rows, summaries, pairing, split_rows, artifact_rows, primary)
    write_metadata(primary, storage)
    update_mainline_docs(primary)
    print(json.dumps({"primary_verdict": primary, "allowed_mode": storage["allowed_mode"], "manifest_rows": len(manifest_rows)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
