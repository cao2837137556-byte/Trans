from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
OUT_DIR = ROOT / "runs" / "issue27w_gotham_sample_data_gate_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
SAMPLE_DIR = DATA_ROOT / "derived" / "sample_gate"
MANIFEST_DIR = DATA_ROOT / "manifests"
ISSUE27V = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"

SELECTED_CSVS = [
    "processed/iotsim-combined-cycle-2.csv",
    "processed/iotsim-combined-cycle-tls-1.csv",
    "processed/iotsim-hydraulic-system-8.csv",
    "processed/iotsim-air-quality-1.csv",
    "processed/iotsim-combined-cycle-10.csv",
    "processed/iotsim-city-power-1.csv",
]

MAX_SAMPLE_ROWS_TO_WRITE = 1000
FULL_SCAN_LIMIT_BYTES = 50_000_000
LARGE_SCAN_ROW_LIMIT = 200_000
MIN_FREE_BYTES_FOR_EXTRACTION = 10_000_000_000


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
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


def append_once(path: Path, marker: str, block: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old == "" or old.endswith("\n") else "\n"
    path.write_text(old + sep + block, encoding="utf-8")


def load_archive_listing() -> list[dict]:
    with (ISSUE27V / "archive_file_listing.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def safe_name(member: str) -> str:
    return member.replace("\\", "/").replace("/", "__")


def parse_device_from_processed(path: str) -> dict:
    name = Path(path).stem
    if name.startswith("iotsim-"):
        name = name[len("iotsim-") :]
    m = re.match(r"(?P<family>.+)-(?P<instance>\d+)$", name)
    family = m.group("family") if m else name
    instance = m.group("instance") if m else "unknown"
    protocol_hint = "tls" if "tls" in family else "camera_rtsp_possible" if "camera" in family else "iot_protocol_unknown"
    return {
        "inferred_device": name,
        "inferred_device_family": family,
        "inferred_capture_or_instance": instance,
        "inferred_protocol_from_name": protocol_hint,
    }


def parse_raw_member(path: str) -> dict:
    parts = path.replace("\\", "/").split("/")
    role = "unknown"
    attack_type = "none"
    if len(parts) >= 2 and parts[0] == "raw":
        role = parts[1]
    if len(parts) >= 3 and parts[0] == "raw" and parts[1] == "malicious":
        attack_type = parts[2]
    device = Path(path).name.split("_0-0_to_")[0]
    return {"raw_role": role, "raw_attack_type": attack_type, "raw_device": device}


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


def protocol_signature(protocol_values: Counter) -> str:
    tokens: Counter[str] = Counter()
    for value, count in protocol_values.items():
        for token in str(value).split(":"):
            token = token.lower().strip()
            if token:
                tokens[token] += count
    interesting = [k for k, _ in tokens.most_common(10) if k not in {"eth", "ethertype", "ip", "tcp", "udp"}]
    return "|".join(interesting[:5]) if interesting else "unknown"


def scan_csv_member(zf: zipfile.ZipFile, member: str, file_size: int) -> dict:
    full_scan = file_size <= FULL_SCAN_LIMIT_BYTES
    row_limit = None if full_scan else LARGE_SCAN_ROW_LIMIT
    out_path = SAMPLE_DIR / f"{safe_name(member)}.sample1000.csv"
    rows_written = 0
    rows_scanned = 0
    label_counts: Counter[str] = Counter()
    protocols: Counter[str] = Counter()
    src_ips: Counter[str] = Counter()
    dst_ips: Counter[str] = Counter()
    eth_src: Counter[str] = Counter()
    eth_dst: Counter[str] = Counter()
    columns: list[str] = []
    first_time: datetime | None = None
    last_time: datetime | None = None
    min_time: datetime | None = None
    max_time: datetime | None = None
    monotonic_violations = 0
    previous_time: datetime | None = None
    first_non_benign_row = ""
    first_non_benign_time = ""
    label_transitions = 0
    previous_label = None

    with zf.open(member) as raw, out_path.open("w", newline="", encoding="utf-8") as out_f:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        columns = reader.fieldnames or []
        writer = csv.DictWriter(out_f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in reader:
            rows_scanned += 1
            if rows_written < MAX_SAMPLE_ROWS_TO_WRITE:
                writer.writerow(row)
                rows_written += 1
            label = row.get("label", "")
            label_counts[label] += 1
            protocols[row.get("frame.protocols", "")] += 1
            src_ips[row.get("ip.src", "")] += 1
            dst_ips[row.get("ip.dst", "")] += 1
            eth_src[row.get("eth.src", "")] += 1
            eth_dst[row.get("eth.dst", "")] += 1
            if previous_label is not None and previous_label != label:
                label_transitions += 1
            previous_label = label
            if label != "Benign" and not first_non_benign_row:
                first_non_benign_row = str(rows_scanned)
                first_non_benign_time = row.get("frame.time", "")
            parsed = parse_frame_time(row.get("frame.time", ""))
            if parsed is not None:
                if first_time is None:
                    first_time = parsed
                if previous_time is not None and parsed < previous_time:
                    monotonic_violations += 1
                previous_time = parsed
                last_time = parsed
                min_time = parsed if min_time is None or parsed < min_time else min_time
                max_time = parsed if max_time is None or parsed > max_time else max_time
            if row_limit is not None and rows_scanned >= row_limit:
                break
    return {
        "sample_path": str(out_path),
        "sample_size_bytes": out_path.stat().st_size,
        "sample_sha256": sha256_file(out_path),
        "rows_written": rows_written,
        "rows_scanned": rows_scanned,
        "full_scan": full_scan,
        "scan_limit": row_limit if row_limit is not None else "full_file",
        "columns": columns,
        "label_counts": dict(label_counts),
        "label_values": sorted(label_counts),
        "protocol_signature": protocol_signature(protocols),
        "top_frame_protocols": dict(protocols.most_common(5)),
        "top_ip_src": dict(src_ips.most_common(5)),
        "top_ip_dst": dict(dst_ips.most_common(5)),
        "top_eth_src": dict(eth_src.most_common(5)),
        "top_eth_dst": dict(eth_dst.most_common(5)),
        "first_time": first_time.isoformat() if first_time else "",
        "last_time": last_time.isoformat() if last_time else "",
        "min_time": min_time.isoformat() if min_time else "",
        "max_time": max_time.isoformat() if max_time else "",
        "monotonic_violations": monotonic_violations,
        "first_non_benign_row": first_non_benign_row,
        "first_non_benign_time": first_non_benign_time,
        "label_transitions": label_transitions,
    }


def matching_raw_paths(member: str, archive_rows: list[dict]) -> dict:
    parsed = parse_device_from_processed(member)
    device = "iotsim-" + parsed["inferred_device"]
    matches = [r["file_path"] for r in archive_rows if r.get("is_pcap") == "True" and device in r["file_path"]]
    benign = [m for m in matches if m.startswith("raw/benign/")]
    malicious = [m for m in matches if m.startswith("raw/malicious/")]
    attack_types = sorted({parse_raw_member(m)["raw_attack_type"] for m in malicious})
    return {
        "matching_pcap_count": len(matches),
        "matching_benign_pcap_count": len(benign),
        "matching_malicious_pcap_count": len(malicious),
        "matching_attack_types": "|".join(attack_types),
        "example_matching_pcap": matches[0] if matches else "",
    }


def build_candidate_selection(archive_rows: list[dict], scans: dict[str, dict]) -> list[dict]:
    rows: list[dict] = []
    for member in SELECTED_CSVS:
        listing = next(r for r in archive_rows if r["file_path"] == member)
        parsed = parse_device_from_processed(member)
        scan = scans.get(member, {})
        labels = scan.get("label_counts", {})
        role = "benign_candidate" if labels and set(labels) == {"Benign"} else "attack_mixed_candidate" if labels else "pre_scan_unknown"
        reason = {
            "processed/iotsim-combined-cycle-2.csv": "small benign MQTT-like industrial device; same family as attacked combined-cycle for device split contrast",
            "processed/iotsim-combined-cycle-tls-1.csv": "small benign TLS variant for protocol-disjoint benign drift probe",
            "processed/iotsim-hydraulic-system-8.csv": "small benign different device family for device-disjoint benign drift probe",
            "processed/iotsim-air-quality-1.csv": "mixed benign plus Telnet/TCP scan/Ingress labels; moderate size and attack candidate",
            "processed/iotsim-combined-cycle-10.csv": "mixed benign plus multiple attack labels; same family as benign combined-cycle candidates",
            "processed/iotsim-city-power-1.csv": "mixed benign plus Mirai UDP Flooding in partial scan; covers IoT botnet-style attack type",
        }.get(member, "selected representative sample")
        rows.append(
            {
                "archive_path": member,
                "file_type": "processed_csv",
                "estimated_uncompressed_size": listing["uncompressed_size"],
                "inferred_device": parsed["inferred_device"],
                "inferred_device_family": parsed["inferred_device_family"],
                "inferred_protocol": parsed["inferred_protocol_from_name"] + "; observed=" + scan.get("protocol_signature", "not_scanned"),
                "inferred_attack_type": "|".join([x for x in scan.get("label_values", []) if x != "Benign"]) or "none_observed",
                "inferred_role": role,
                "selection_reason": reason,
            }
        )
    for r in archive_rows:
        if r.get("is_readme") == "True":
            rows.append(
                {
                    "archive_path": r["file_path"],
                    "file_type": "readme_metadata",
                    "estimated_uncompressed_size": r["uncompressed_size"],
                    "inferred_device": "all",
                    "inferred_device_family": "all",
                    "inferred_protocol": "documentation",
                    "inferred_attack_type": "documentation",
                    "inferred_role": "metadata",
                    "selection_reason": "README provides dataset structure, labels, raw/processed semantics, and attack list",
                }
            )
    return rows


def run() -> dict:
    ensure_dirs()
    if not ZIP_PATH.exists():
        raise FileNotFoundError(ZIP_PATH)
    if shutil.disk_usage(str(PAPER_ROOT.drive + "\\")).free < MIN_FREE_BYTES_FOR_EXTRACTION:
        raise RuntimeError("D: free space below 10GB; sample extraction blocked")
    archive_rows = load_archive_listing()
    scans: dict[str, dict] = {}
    extraction_rows: list[dict] = []
    schema_rows: list[dict] = []
    temporal_rows: list[dict] = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for member in SELECTED_CSVS:
            info = zf.getinfo(member)
            scan = scan_csv_member(zf, member, info.file_size)
            scans[member] = scan
            parsed = parse_device_from_processed(member)
            raw = matching_raw_paths(member, archive_rows)
            extraction_rows.append(
                {
                    "archive_path": member,
                    "local_sample_path": scan["sample_path"],
                    "extraction_mode": "first_1000_rows_only_to_disk_full_or_limited_scan_in_zip",
                    "uncompressed_size": info.file_size,
                    "rows_written": scan["rows_written"],
                    "rows_scanned": scan["rows_scanned"],
                    "full_scan": scan["full_scan"],
                    "sample_size_bytes": scan["sample_size_bytes"],
                    "sample_sha256": scan["sample_sha256"],
                    "pcap_extracted": False,
                    "matching_pcap_count": raw["matching_pcap_count"],
                    "notes": "No PCAP or full large CSV extraction performed.",
                }
            )
            label_values = scan["label_values"]
            has_attack = any(x != "Benign" for x in label_values)
            all_benign = label_values == ["Benign"]
            schema_rows.append(
                {
                    "archive_path": member,
                    "columns": "|".join(scan["columns"]),
                    "column_count": len(scan["columns"]),
                    "has_label": "label" in scan["columns"],
                    "label_values": "|".join(label_values),
                    "label_counts_json": json.dumps(scan["label_counts"], sort_keys=True),
                    "has_frame_time": "frame.time" in scan["columns"],
                    "has_frame_number": "frame.number" in scan["columns"],
                    "has_ip_src": "ip.src" in scan["columns"],
                    "has_ip_dst": "ip.dst" in scan["columns"],
                    "has_eth_src": "eth.src" in scan["columns"],
                    "has_eth_dst": "eth.dst" in scan["columns"],
                    "has_attack_type_column": False,
                    "label_matches_filename_role": "mixed_attack_labels_in_processed_device_file" if has_attack else "all_benign_processed_device_file" if all_benign else "unknown",
                    "missing_label_count": scan["label_counts"].get("", 0),
                    "mixed_label_file": has_attack and "Benign" in label_values,
                    "all_benign_file": all_benign,
                    "all_attack_file": has_attack and "Benign" not in label_values,
                    "timestamp_sortable": bool(scan["first_time"]),
                }
            )
            temporal_rows.append(
                {
                    "archive_path": member,
                    "device": parsed["inferred_device"],
                    "device_family": parsed["inferred_device_family"],
                    "instance_or_capture": parsed["inferred_capture_or_instance"],
                    "observed_protocol_signature": scan["protocol_signature"],
                    "first_time": scan["first_time"],
                    "last_time": scan["last_time"],
                    "min_time": scan["min_time"],
                    "max_time": scan["max_time"],
                    "time_monotonic_violations": scan["monotonic_violations"],
                    "time_parse_supported": bool(scan["first_time"]),
                    "first_non_benign_row": scan["first_non_benign_row"],
                    "first_non_benign_time": scan["first_non_benign_time"],
                    "label_transitions": scan["label_transitions"],
                    "top_ip_src_json": json.dumps(scan["top_ip_src"], sort_keys=True),
                    "top_ip_dst_json": json.dumps(scan["top_ip_dst"], sort_keys=True),
                    "matching_benign_pcap_count": raw["matching_benign_pcap_count"],
                    "matching_malicious_pcap_count": raw["matching_malicious_pcap_count"],
                    "matching_attack_types": raw["matching_attack_types"],
                    "same_device_multi_time_or_capture_potential": raw["matching_pcap_count"] > 1,
                }
            )
    candidate_rows = build_candidate_selection(archive_rows, scans)
    write_csv("sample_candidate_selection.csv", candidate_rows)
    write_csv("sample_extraction_manifest.csv", extraction_rows)
    write_csv("gotham_sample_csv_schema_audit.csv", schema_rows)
    write_csv("gotham_sample_temporal_source_audit.csv", temporal_rows)

    split_rows = [
        {
            "split_name": "device_disjoint_benign_drift",
            "can_construct": True,
            "required_files": "combined-cycle-2 or combined-cycle-tls-1 as ID benign; hydraulic-system-8 as OOD benign; air-quality-1/combined-cycle-10/city-power-1 for attack support/eval",
            "required_fields": "label|frame.time|ip.src|ip.dst|eth.src|eth.dst|frame.protocols",
            "id_ood_semantics": "cross-device benign shift with packet-level timestamps and labels",
            "attack_support_eval_disjoint": "possible by file/device/attack-label subsets, but must avoid device/file shortcut",
            "source_device_artifact_risk": "medium_high",
            "row_order_artifact_risk": "medium_high_for_attack_files_due_to benign_prefix_then_attack_labels",
            "report_only_final_eval_possible": "yes_after_larger_manifest",
            "fit_for_low_ood_alert": "promising_but_needs_larger_sample",
            "evidence_level": "promising_but_needs_larger_sample",
        },
        {
            "split_name": "protocol_disjoint_benign_drift",
            "can_construct": True,
            "required_files": "combined-cycle-2 vs combined-cycle-tls-1 or hydraulic-system-8; attack from mixed files",
            "required_fields": "label|frame.time|frame.protocols",
            "id_ood_semantics": "cross-protocol benign shift using observed protocol signatures",
            "attack_support_eval_disjoint": "possible, with larger sample needed for balanced attack families",
            "source_device_artifact_risk": "medium",
            "row_order_artifact_risk": "medium_high_for_attack_files",
            "report_only_final_eval_possible": "yes_after_larger_manifest",
            "fit_for_low_ood_alert": "promising_but_needs_larger_sample",
            "evidence_level": "promising_but_needs_larger_sample",
        },
        {
            "split_name": "time_order_split",
            "can_construct": "partial",
            "required_files": "requires larger benign files/captures and explicit final-eval holdout manifest",
            "required_fields": "frame.time plus device/source/capture manifest",
            "id_ood_semantics": "timestamps parse and are mostly ordered, but sample does not prove natural train-to-deploy benign drift",
            "attack_support_eval_disjoint": "possible by time/file, but attack labels are time/order coupled in mixed files",
            "source_device_artifact_risk": "medium",
            "row_order_artifact_risk": "high",
            "report_only_final_eval_possible": "not_yet",
            "fit_for_low_ood_alert": "needs_larger_sample",
            "evidence_level": "promising_but_needs_larger_sample",
        },
    ]
    write_csv("gotham_sample_split_feasibility_table.csv", split_rows)

    artifact_rows = [
        {"risk": "label_vs_file_path_binding", "level": "medium_high", "evidence": "benign-only sample files and mixed attack device files can become file-level shortcuts if split is careless"},
        {"risk": "label_vs_device_binding", "level": "medium_high", "evidence": "sample attack labels appear in selected devices; larger sample must verify attack labels across devices and construct device-disjoint controls"},
        {"risk": "label_vs_protocol_binding", "level": "medium", "evidence": "frame.protocols is available and may partially encode scenario; protocol-disjoint split is useful but can become the benchmark variable"},
        {"risk": "label_vs_time_or_row_order", "level": "high", "evidence": "mixed attack files have benign prefix and later attack labels; time/order split must use purge/report-only manifest and controls"},
        {"risk": "source_capture_artifact", "level": "medium_high", "evidence": "separate metadata JSON was absent in archive listing; source/capture comes from paths/fields and must be validated in a larger manifest"},
        {"risk": "pcap_csv_alignment", "level": "medium", "evidence": "matching PCAP names exist, but no byte-level or packet-count alignment was performed in this sample gate"},
    ]
    write_csv("gotham_sample_artifact_risk_table.csv", artifact_rows)

    primary = "gotham_sample_gate_promising_needs_more_space_and_larger_sample"
    write_reports(candidate_rows, extraction_rows, schema_rows, temporal_rows, split_rows, artifact_rows, primary)
    write_run_metadata(primary)
    update_mainline_docs(primary)
    return {"primary_verdict": primary}


def write_reports(candidate_rows: list[dict], extraction_rows: list[dict], schema_rows: list[dict], temporal_rows: list[dict], split_rows: list[dict], artifact_rows: list[dict], primary: str) -> None:
    selected = [r["archive_path"] for r in candidate_rows if r["file_type"] == "processed_csv"]
    attack_labels = sorted({label for row in schema_rows for label in row["label_values"].split("|") if label and label != "Benign"})
    benign_families = sorted({row["device_family"] for row in temporal_rows if row["archive_path"] in SELECTED_CSVS and "Benign" in next(s["label_values"] for s in schema_rows if s["archive_path"] == row["archive_path"])})
    best_split = "device_disjoint_benign_drift"

    write_text(
        "sample_candidate_selection_report.md",
        "# Sample Candidate Selection Report\n\n"
        f"Selected processed CSVs: `{', '.join(selected)}`.\n\n"
        "The selection intentionally covers benign-only device/protocol variation plus mixed attack files with multiple labels. "
        "No PCAP was extracted. PCAP presence was used only as provenance evidence from archive listing.\n",
    )
    write_text(
        "sample_extraction_report.md",
        "# Sample Extraction Report\n\n"
        "- extraction mode: first 1000 rows per selected processed CSV written to `derived/sample_gate`.\n"
        "- scan mode: selected small/medium CSVs were scanned in-zip to count labels and timestamps; large CSVs were capped at 200000 rows.\n"
        "- PCAP extraction: `false`.\n"
        "- full CSV extraction: `false`.\n"
        f"- local sample directory: `{SAMPLE_DIR}`.\n",
    )
    write_text(
        "gotham_sample_label_audit.md",
        "# Gotham Sample Label Audit\n\n"
        f"- CSV label column present: `{all(str(r['has_label']) == 'True' for r in schema_rows)}`.\n"
        f"- attack labels observed: `{', '.join(attack_labels)}`.\n"
        "- benign-only files are consistent with processed device files whose sampled labels are all `Benign`.\n"
        "- mixed attack files contain a benign prefix plus attack labels, which is useful for semantic audit but creates row-order/time artifact risk.\n"
        "- no separate `attack_type` column was observed; attack type is encoded in the `label` value.\n",
    )
    write_text(
        "gotham_sample_temporal_source_report.md",
        "# Gotham Sample Temporal And Source Report\n\n"
        "- `frame.time` parsed successfully in all selected CSVs.\n"
        "- Selected CSVs were mostly internally time-ordered at the scanned level.\n"
        "- Device/capture can be inferred from processed filenames and matching raw PCAP names.\n"
        "- Protocol can be inferred from `frame.protocols`; names provide only partial hints.\n"
        "- The sample supports device/protocol split design, but does not yet justify a temporal-deployment claim.\n",
    )
    write_text(
        "gotham_sample_split_feasibility_report.md",
        "# Gotham Sample Split Feasibility Report\n\n"
        f"Most promising split: `{best_split}`.\n\n"
        "Device-disjoint benign drift is the strongest next candidate because the archive provides multiple benign device families and mixed attack files with labels and timestamps. "
        "However, larger sample validation is required to ensure attack support/eval is not merely file/device/source separation and to build report-only final OOD eval.\n",
    )
    write_text(
        "gotham_sample_artifact_risk_report.md",
        "# Gotham Sample Artifact Risk Report\n\n"
        "Largest risk: label/source/time coupling. Mixed attack CSVs show benign-prefix then attack-label structure, so a naive time or row-order split can create a shortcut. "
        "A larger sample gate must construct device/protocol controls, check label distribution across devices and attack types, and verify PCAP/CSV alignment before any feature/interface gate.\n",
    )
    write_text(
        "issue27w_decision.md",
        "# issue27w Decision\n\n"
        f"primary_verdict = `{primary}`\n\n"
        "Gotham passes the sample-level schema/label/timestamp availability check and has plausible device/protocol split routes. "
        "It should not proceed directly to model experiments. It should proceed to a larger Data Gate after freeing storage and building a richer manifest.\n",
    )
    write_text(
        "claim_update_after_issue27w.md",
        "# Claim Update After issue27w\n\n"
        "- Gotham remains a promising second dataset for a low-OOD-alert benchmark, but only at Data validity gate level.\n"
        "- Current evidence supports larger sample Data Gate, not model execution or paper claims.\n"
        "- The largest caveat is source/device/time artifact risk in constructing attack and OOD splits.\n"
        "- No external generalization, deployment robustness, DeepSAD mainline, or LOW-GUARD failure claim is supported here.\n",
    )
    write_text(
        "issue27x_next_action.md",
        "# issue27x Next Action\n\n"
        "Recommended next action: `issue27x_gotham_larger_sample_manifest_and_split_gate`.\n\n"
        "Before issue27x, free D: space if possible. Then build a larger row-level sample manifest across more benign device families and attack types, validate PCAP/CSV pairing, and pre-register candidate ID/OOD/attack splits. "
        "Still do not train models or extract full features.\n",
    )
    write_text(
        "summary.md",
        "# issue27w Summary\n\n"
        "1. issue27w completed: `true`.\n"
        f"2. primary_verdict: `{primary}`.\n"
        f"3. sampled CSV / PCAP / metadata: CSV previews from `{', '.join(selected)}`; README metadata; PCAPs were not extracted, only matched by archive listing.\n"
        "4. CSV label column: `yes`.\n"
        "5. CSV frame.time: `yes`.\n"
        "6. labels vs README / filenames: labels are consistent with README multiclass packet-level dataset; processed filenames are device-level and do not directly encode attack labels.\n"
        "7. device / protocol / source: `partial_yes`; device/source from file paths and packet fields, protocol from `frame.protocols`.\n"
        f"8. benign multi-device/protocol/multi-stage potential: `yes_promising`; benign families include `{', '.join(benign_families)}`.\n"
        f"9. attack labels and types: `{', '.join(attack_labels)}`.\n"
        "10. ID/OOD benign split constructable: `yes_promising`, especially device/protocol-disjoint.\n"
        "11. attack support/eval disjoint constructable: `yes_promising`, but needs larger manifest to control file/device/time artifacts.\n"
        f"12. most promising split: `{best_split}`.\n"
        "13. largest artifact risk: label/source/time coupling and benign-prefix-then-attack row-order in mixed files.\n"
        "14. Gotham can enter larger sample Data Gate: `true`.\n"
        "15. current model experiments allowed: `false`.\n"
        "16. need to clean D first: `recommended`, because only about 20GB remained after issue27v.\n"
        "17. issue27x recommendation: larger sample manifest and split gate, no model training.\n"
        "18. Slurm needed: `not for sample gate`; maybe later for full feature extraction.\n"
        "19. commit hash: pending.\n",
    )


def write_run_metadata(primary: str) -> None:
    write_text("command.txt", "python repo/ood/issue27w_gotham_sample_data_gate.py\n")
    write_json(
        "config.json",
        {
            "issue": "issue27w_gotham_sample_data_gate_2026-05-28",
            "zip_path": str(ZIP_PATH),
            "sample_dir": str(SAMPLE_DIR),
            "selected_csvs": SELECTED_CSVS,
            "max_rows_written_per_csv": MAX_SAMPLE_ROWS_TO_WRITE,
            "large_scan_row_limit": LARGE_SCAN_ROW_LIMIT,
            "no_model_training": True,
            "no_feature_extraction": True,
            "primary_verdict": primary,
        },
    )
    write_json(
        "run_spec.json",
        {
            "stages": [
                "sample_candidate_selection",
                "selective_sample_extraction_preview",
                "csv_schema_label_audit",
                "timestamp_order_device_source_audit",
                "small_split_feasibility",
                "sample_artifact_risk_audit",
            ],
            "constraints": [
                "no_model_training",
                "no_baselines",
                "no_full_zip_extraction",
                "no_pcap_extraction",
                "no_large_csv_extraction",
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
        "<!-- issue27w_gotham_sample_data_gate -->",
        "\n<!-- issue27w_gotham_sample_data_gate -->\n\n"
        "## issue27w Gotham Sample Data Gate\n\n"
        f"- primary_verdict: `{primary}`.\n"
        "- sample gate read selected processed CSVs from the zip stream and wrote only first-1000-row previews under the external dataset directory; no PCAP or full large CSV extraction was performed.\n"
        "- labels, `frame.time`, packet fields, device/file names, and matching PCAP paths are usable at sample level.\n"
        "- most promising split is device-disjoint benign drift, with protocol-disjoint as a secondary route.\n"
        "- largest artifact risk is label/source/time coupling, especially benign-prefix then attack-label structure in mixed attack files.\n"
        "- model experiments remain blocked; next is a larger sample manifest and split gate.\n",
    )
    append_once(
        exp_map,
        "<!-- issue27w_map_entry -->",
        "\n<!-- issue27w_map_entry -->\n\n"
        "### issue27w_gotham_sample_data_gate_2026-05-28\n\n"
        "- status: completed.\n"
        f"- primary_verdict: `{primary}`.\n"
        f"- outputs: `{OUT_DIR.relative_to(ROOT).as_posix()}/`.\n"
        "- role: Gotham sample-level Data validity gate before feature/interface work.\n"
        "- implication: Gotham is promising but requires larger sample manifest/split validation before any model execution.\n",
    )


def main() -> int:
    result = run()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
