from __future__ import annotations

import csv
import hashlib
import json
import re
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
OUT_DIR = ROOT / "runs" / "issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28"
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
METADATA_DIR = DATA_ROOT / "metadata"
MANIFEST_DIR = DATA_ROOT / "manifests"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ZENODO_API = "https://zenodo.org/api/records/14502760"
ZENODO_RECORD = "https://zenodo.org/records/14502760"


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST_DIR.mkdir(parents=True, exist_ok=True)


def write_text(name: str, text: str) -> None:
    (OUT_DIR / name).write_text(text, encoding="utf-8")


def write_json(name: str, obj: object) -> None:
    (OUT_DIR / name).write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    keys: list[str] = []
    if fieldnames is None:
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
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


def strip_html(value: str) -> str:
    text = re.sub("<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip()


def load_zenodo_metadata() -> dict:
    path = METADATA_DIR / "zenodo_record_14502760.json"
    if not path.exists():
        with urllib.request.urlopen(ZENODO_API, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def contains(text: str, *needles: str) -> bool:
    low = text.lower()
    return all(n.lower() in low for n in needles)


def make_manifest() -> None:
    rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.name == "manifest.csv" or not path.is_file():
            continue
        rows.append({"file": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv("manifest.csv", rows)


def main() -> None:
    ensure_dirs()
    record = load_zenodo_metadata()
    metadata = record.get("metadata", {})
    description = strip_html(metadata.get("description", ""))
    files = record.get("files", [])
    total_size = sum(int(f.get("size", 0) or 0) for f in files)
    file_keys = [f.get("key", "") for f in files]
    single_large_zip = len(files) == 1 and file_keys[0].lower().endswith(".zip")
    size_decimal_gb = total_size / 1_000_000_000
    size_gib = total_size / (1024 ** 3)

    # Small local metadata manifest outside git workspace.
    local_meta_manifest = MANIFEST_DIR / "metadata_intake_manifest.csv"
    with local_meta_manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["asset", "path", "size_bytes", "sha256", "notes"])
        writer.writeheader()
        zp = METADATA_DIR / "zenodo_record_14502760.json"
        writer.writerow(
            {
                "asset": "zenodo_record_14502760_json",
                "path": str(zp),
                "size_bytes": zp.stat().st_size,
                "sha256": sha256_file(zp),
                "notes": "Small metadata only; not raw dataset.",
            }
        )

    raw_pcap = contains(description, "pcap", "raw network traffic")
    labelled_csv = contains(description, "csv", "processed packet-level")
    metadata_available = contains(description, "metadata files")
    timestamp_available = contains(description, "timestamps")
    device_info = contains(description, "78 heterogeneous iot devices") or contains(description, "device-level")
    attack_labels = contains(description, "attack types") and contains(description, "deterministic labelling")
    protocol_info = contains(description, "http/3") or contains(description, "quic") or contains(description, "coap")
    benign_possible = contains(description, "traffic collected") and contains(description, "iot devices")

    inventory_rows = []
    for f in files:
        inventory_rows.append(
            {
                "dataset_name": "Gotham Dataset 2025",
                "official_page": ZENODO_RECORD,
                "api_record": ZENODO_API,
                "paper_or_citation_info": metadata.get("doi", record.get("doi", "")),
                "title": metadata.get("title", record.get("title", "")),
                "publication_date": metadata.get("publication_date", ""),
                "total_size_bytes": total_size,
                "total_size_gb_decimal": round(size_decimal_gb, 3),
                "total_size_gib": round(size_gib, 3),
                "file_name": f.get("key", ""),
                "file_size_bytes": f.get("size", ""),
                "file_type": Path(f.get("key", "")).suffix.lower().lstrip("."),
                "file_checksum": f.get("checksum", ""),
                "raw_pcap_available": raw_pcap,
                "labelled_csv_available": labelled_csv,
                "metadata_available": metadata_available,
                "timestamp_available": timestamp_available,
                "device_source_capture_available": device_info,
                "protocol_information": protocol_info,
                "attack_label_available": attack_labels,
                "benign_traffic_available": benign_possible,
                "multiple_device_environment_information": device_info,
                "license_access": metadata.get("license", {}).get("id", "") if isinstance(metadata.get("license"), dict) else metadata.get("license", ""),
                "access_right": metadata.get("access_right", record.get("access_right", "open")),
                "download_mode": "single_large_zip_no_per_file_granularity" if single_large_zip else "per_file_available",
                "local_planned_metadata_path": str(METADATA_DIR),
                "local_planned_manifest_path": str(MANIFEST_DIR),
                "local_planned_raw_path": str(DATA_ROOT / "raw"),
                "local_metadata_file": str(METADATA_DIR / "zenodo_record_14502760.json"),
            }
        )
    write_csv("gotham_metadata_inventory.csv", inventory_rows)

    precheck_rows = [
        {
            "gate_check": "construct_id_benign_train",
            "status": "likely_yes_after_download",
            "evidence": "Device-level traffic collected at interface level of 78 heterogeneous IoT devices.",
            "risk": "medium",
            "next_check": "Inspect CSV labels/metadata for normal traffic segments per device.",
        },
        {
            "gate_check": "construct_ood_benign_validation",
            "status": "likely_yes_but_not_proven",
            "evidence": "Non-IID traffic across devices suggests device/capture split potential.",
            "risk": "medium",
            "next_check": "Verify benign-only phases or devices not contaminated by attack windows.",
        },
        {
            "gate_check": "construct_final_ood_benign_eval",
            "status": "likely_yes_but_requires_metadata",
            "evidence": "Device-organized files may allow report-only held-out devices or time windows.",
            "risk": "medium",
            "next_check": "Check file/device/time labels after download.",
        },
        {
            "gate_check": "construct_attack_support",
            "status": "yes_after_download",
            "evidence": "Attack types listed include Mirai, Merlin C2, reconnaissance, amplification, DoS.",
            "risk": "low_medium",
            "next_check": "Confirm per-packet attack labels and attack family names.",
        },
        {
            "gate_check": "construct_attack_eval",
            "status": "yes_after_download",
            "evidence": "Ground-truth deterministic labels based on orchestration logs.",
            "risk": "low_medium",
            "next_check": "Split by attack family/device/time without support/eval overlap.",
        },
        {
            "gate_check": "support_eval_disjoint",
            "status": "likely_yes",
            "evidence": "Raw/CSV files organized by device identifier.",
            "risk": "medium",
            "next_check": "Use row/file/device IDs to enforce disjointness.",
        },
        {
            "gate_check": "timestamp_or_order_for_deployment_split",
            "status": "yes_metadata_claimed",
            "evidence": "Metadata files provide timestamps according to Zenodo description.",
            "risk": "low_medium",
            "next_check": "Verify timestamp fields in metadata/CSV after download.",
        },
        {
            "gate_check": "device_capture_source_split",
            "status": "yes_device_level_claimed",
            "evidence": "78 heterogeneous IoT devices and device-level traces.",
            "risk": "low_medium",
            "next_check": "Inspect device identifiers and gateway/capture metadata.",
        },
        {
            "gate_check": "row_order_artifact_audit",
            "status": "yes_with_raw_and_metadata",
            "evidence": "PCAP/CSV/metadata triad should permit row and source audits.",
            "risk": "medium",
            "next_check": "Hash row alignment across PCAP/CSV/labels.",
        },
        {
            "gate_check": "source_capture_artifact_audit",
            "status": "yes_with_device_metadata",
            "evidence": "Device-organized files and contextual metadata.",
            "risk": "medium",
            "next_check": "Ensure attack labels are not equivalent to device/source ID.",
        },
        {
            "gate_check": "report_only_final_eval",
            "status": "yes_protocol_can_define",
            "evidence": "Dataset has enough file-level/device-level units if labels are as described.",
            "risk": "medium",
            "next_check": "Define held-out device/time windows after metadata inspection.",
        },
        {
            "gate_check": "feature_extraction_path",
            "status": "yes",
            "evidence": "Raw PCAP enables Kitsune/AfterImage or flow extraction; CSV enables packet-level feature path.",
            "risk": "medium",
            "next_check": "Choose feature path after file inspection.",
        },
        {
            "gate_check": "kitsune_afterimage_online_fe",
            "status": "yes_if_pcap_downloaded",
            "evidence": "Raw PCAP is included in zip according to metadata.",
            "risk": "medium_high",
            "next_check": "Run small extraction smoke after user-confirmed download.",
        },
        {
            "gate_check": "flow_feature_extraction",
            "status": "yes",
            "evidence": "Processed packet-level CSV exists; flow aggregation can be derived.",
            "risk": "medium",
            "next_check": "Inspect CSV schema.",
        },
        {
            "gate_check": "low_ood_alert_operating_point",
            "status": "promising_not_proven",
            "evidence": "Multiple devices/non-IID setting suggests possible benign OOD splits.",
            "risk": "medium",
            "next_check": "Run Data Gate sample after download; no model claim yet.",
        },
    ]
    write_csv("gotham_data_gate_precheck_table.csv", precheck_rows)

    risk_rows = [
        {
            "risk": "single large archive",
            "severity": "high",
            "evidence": f"Zenodo exposes {file_keys[0]} at {round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB.",
            "mitigation": "Require user confirmation before download; no big file in git.",
        },
        {
            "risk": "benign phase not yet verified",
            "severity": "medium",
            "evidence": "Metadata says device-level non-IID traffic, but file contents not inspected.",
            "mitigation": "After download, inspect labels/timestamps per device before split.",
        },
        {
            "risk": "attack/source coupling",
            "severity": "medium",
            "evidence": "Attack orchestration labels may align with devices/time windows.",
            "mitigation": "Check whether attack label is separable from source/device/capture.",
        },
        {
            "risk": "storage and extraction cost",
            "severity": "high",
            "evidence": "23.8GB zip; decompressed size unknown.",
            "mitigation": "Download to D: datasets only; inspect zip listing before extraction if possible.",
        },
        {
            "risk": "feature path decision",
            "severity": "medium",
            "evidence": "Dataset has PCAP and CSV; exact CSV schema unseen.",
            "mitigation": "Issue27v should inspect file listing/schema before model pipeline.",
        },
    ]
    write_csv("gotham_risk_table.csv", risk_rows)

    primary_verdict = "gotham_ready_for_full_download_with_user_confirmation"

    write_text(
        "gotham_metadata_report.md",
        f"""# Gotham Metadata Report

Official record: `{ZENODO_RECORD}`

Title: `{metadata.get('title', record.get('title', ''))}`

DOI: `{metadata.get('doi', record.get('doi', ''))}`

Publication date: `{metadata.get('publication_date', '')}`

License/access: `{metadata.get('license', {}).get('id', '') if isinstance(metadata.get('license'), dict) else metadata.get('license', '')}`, access `{metadata.get('access_right', record.get('access_right', 'open'))}`.

Metadata intake result:

- raw PCAP availability: `{raw_pcap}`.
- labelled/processed CSV availability: `{labelled_csv}`.
- metadata availability: `{metadata_available}`.
- timestamp information: `{timestamp_available}`.
- device/source/capture information: `{device_info}`.
- attack labels: `{attack_labels}`.
- total downloadable data: `{round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB`.
- file granularity: `single_large_zip_no_per_file_granularity`.

Interpretation:

Gotham is a strong candidate for the low-OOD-alert benchmark because the record describes raw PCAP, processed CSV, metadata with timestamps/attacker IPs/attack types, device-level traces from 78 heterogeneous IoT devices, and deterministic labels from orchestration logs.

The metadata is strong enough to justify a user-confirmed full download or a user-confirmed method for inspecting the zip listing. It is not enough to start model experiments. The next gate must inspect the actual files and labels after download.
""",
    )

    write_text(
        "gotham_data_gate_precheck_report.md",
        """# Gotham Data Gate Precheck Report

Gotham passes the metadata-level precheck as a promising candidate, not as a validated benchmark.

Why it is promising:

- raw PCAP and processed CSV are advertised.
- metadata includes timestamps, attacker IPs, and attack types.
- files are organized by device identifier.
- 78 heterogeneous IoT devices create a plausible basis for ID/OOD benign splits.
- deterministic labeling from orchestration logs is reported.

What remains blocked:

- actual benign phase counts per device are unknown.
- actual CSV schema is unknown.
- actual label fields and attack windows are unknown.
- decompressed file structure is unknown because Zenodo exposes a single large zip.
- no model execution is allowed until sample/file-level Data Gate passes.
""",
    )

    write_text(
        "gotham_download_decision.md",
        f"""# Gotham Download Decision

Decision: `{primary_verdict}`.

Do not download automatically in this issue.

Recommended next download, only with user confirmation:

1. `GothamDataset2025.zip` from Zenodo record `{ZENODO_RECORD}`.
2. Save only under `D:\\study\\paper\\anomaly_detection\\paper04\\datasets\\gotham2025\\raw`.
3. Preserve Zenodo metadata under `D:\\study\\paper\\anomaly_detection\\paper04\\datasets\\gotham2025\\metadata`.
4. Write file hashes and extraction manifest under `D:\\study\\paper\\anomaly_detection\\paper04\\datasets\\gotham2025\\manifests`.

Expected download size: `{round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB`.

Expected decompressed size: unknown; plan for significantly more than the zip size.

Recommended immediate follow-up after user confirmation:

- download the zip to the D: dataset root.
- inspect zip file listing before extraction.
- extract only metadata/README/CSV schema first if possible.
- do not run models.
""",
    )

    write_text(
        "issue27u_decision.md",
        f"""# issue27u Decision

primary_verdict = `{primary_verdict}`

Gotham metadata is strong enough to justify the next intake step. It has raw PCAP, processed CSV, metadata, timestamps, device-level structure, and deterministic attack labels according to the official Zenodo record.

However, Zenodo exposes the dataset as a single `{round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB` zip. Because there is no small per-file download path visible from the API, issue27v must require user confirmation before downloading. After download, the next gate must inspect file structure, label schema, benign phases, and source/capture coupling before any feature/interface or model execution.
""",
    )

    write_text(
        "claim_update_after_issue27u.md",
        """# Claim Update After issue27u

Gotham is a promising second-dataset candidate for the Data validity gate, but it is not yet a validated benchmark.

No model claims are allowed. Full Mirai remains diagnostic only. DeepSADStyle_Lite is not a main method, LOW-GUARD++ is not declared failed, and external generalization is not proven.

The next claim-safe step is user-confirmed Gotham download followed by file-level metadata, label, timestamp, and benign/attack split audit.
""",
    )

    write_text(
        "issue27v_next_action.md",
        """# issue27v Next Action

Recommended issue:

`issue27v_gotham_user_confirmed_download_and_file_level_data_gate_2026-05-28`

Before starting:

- ask user to confirm the 23.8GB Gotham download.
- use only `D:\\study\\paper\\anomaly_detection\\paper04\\datasets\\gotham2025\\raw`.
- do not stage raw data.

After download:

1. compute zip hash and compare with Zenodo md5.
2. inspect zip listing before extraction.
3. extract metadata/README/CSV schema first.
4. audit device IDs, timestamps, attack labels, benign phases, and source/capture coupling.
5. decide whether Gotham can construct ID benign, OOD benign, final OOD, attack support, and attack eval.
6. only after Data Gate passes should Feature/interface gate begin.

Fallback: if user does not want the large download or Gotham file-level audit fails, run ToN-IoT metadata intake.
""",
    )

    summary = f"""# issue27u Gotham Metadata Intake Summary

1. issue27u completed: `true`.
2. primary_verdict: `{primary_verdict}`.
3. Gotham raw PCAP: `yes`, according to official Zenodo metadata.
4. labelled CSV: `yes`, processed packet-level CSV is reported.
5. timestamp/order: `yes`, metadata files reportedly include timestamps.
6. device/source/capture metadata: `yes/promising`, device-level files from 78 heterogeneous IoT devices are reported.
7. benign multi-stage/environment: `promising_not_yet_verified`; non-IID device traffic suggests possible ID/OOD benign split, but file-level labels must be inspected.
8. attack labels: `yes`, deterministic labels from orchestration logs and metadata attack types are reported.
9. support for low-OOD-alert benchmark: `promising`, but not validated until file-level Data Gate.
10. largest risk: Zenodo exposes a single `{round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB` zip; no small per-device download path was visible in API metadata.
11. user confirmation needed: `yes` before any raw/full download.
12. recommended download: `GothamDataset2025.zip` only after confirmation; inspect zip listing/metadata before extraction.
13. planned path: `D:\\study\\paper\\anomaly_detection\\paper04\\datasets\\gotham2025\\raw|metadata|labels|derived|manifests`.
14. model experiments allowed: `false`.
15. if Gotham not suitable: fallback to ToN-IoT metadata intake.
16. Slurm needed: not for metadata; possibly for feature extraction after large download.
17. commit hash: pending.
"""
    write_text("summary.md", summary)

    write_text("command.txt", "python repo/ood/issue27u_gotham_metadata_intake.py\n")
    write_json(
        "config.json",
        {
            "issue": "issue27u",
            "no_model_training": True,
            "no_large_download": True,
            "zenodo_record": ZENODO_RECORD,
            "metadata_saved_to": str(METADATA_DIR / "zenodo_record_14502760.json"),
            "primary_verdict": primary_verdict,
        },
    )
    write_json(
        "run_spec.json",
        {
            "task": "gotham_metadata_intake_and_data_gate_precheck",
            "input_issue": "issue27t_second_dataset_intake_with_full_mirai_raw_missing_confirmed_2026-05-28",
            "external_sources": [ZENODO_RECORD, ZENODO_API],
            "large_download_performed": False,
            "metadata_only_saved_outside_repo": str(METADATA_DIR / "zenodo_record_14502760.json"),
            "primary_verdict": primary_verdict,
        },
    )

    marker = "<!-- issue27u_gotham_metadata_intake -->"
    append_once(
        MAINLINE_DOCS / "mainline_handoff.md",
        marker,
        f"""
{marker}

## issue27u Gotham Metadata Intake

- primary_verdict: `{primary_verdict}`.
- Gotham metadata reports raw PCAP, processed CSV, metadata with timestamps/attacker IPs/attack types, device-level traces from 78 heterogeneous IoT devices, and deterministic labels.
- Zenodo exposes a single `{round(size_decimal_gb, 3)}GB decimal / {round(size_gib, 3)}GiB` zip; no large download was performed.
- model experiments remain blocked by Data validity gate.
- next: user-confirmed Gotham download and file-level Data Gate, or ToN-IoT metadata intake if Gotham is blocked.
""",
    )

    map_marker = "<!-- issue27u_map_entry -->"
    append_once(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        map_marker,
        f"""
{map_marker}

### issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28

- status: completed.
- primary_verdict: `{primary_verdict}`.
- outputs: `runs/issue27u_gotham_metadata_intake_and_data_gate_precheck_2026-05-28/`.
- role: Gotham metadata-level Data Gate precheck.
- implication: Gotham is promising but requires user-confirmed 23.825GB decimal / 22.189GiB download and file-level split/label audit before any model execution.
""",
    )

    make_manifest()
    print(
        json.dumps(
            {
                "primary_verdict": primary_verdict,
                "size_gb_decimal": round(size_decimal_gb, 3),
                "size_gib": round(size_gib, 3),
                "files": file_keys,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
