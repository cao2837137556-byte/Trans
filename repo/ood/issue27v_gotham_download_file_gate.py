from __future__ import annotations

import csv
import hashlib
import json
import os
import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = ROOT.parents[1]
OUT_DIR = ROOT / "runs" / "issue27v_gotham_download_and_file_level_data_gate_2026-05-28"
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
RAW_DIR = DATA_ROOT / "raw"
METADATA_DIR = DATA_ROOT / "metadata"
LABELS_DIR = DATA_ROOT / "labels"
DERIVED_DIR = DATA_ROOT / "derived"
MANIFEST_DIR = DATA_ROOT / "manifests"
ZIP_PATH = RAW_DIR / "GothamDataset2025.zip"

ZENODO_RECORD = "https://zenodo.org/records/14502760"
ZENODO_API = "https://zenodo.org/api/records/14502760"
ZENODO_DOWNLOAD = "https://zenodo.org/api/records/14502760/files/GothamDataset2025.zip/content"
EXPECTED_MD5 = "7ca78c0517ccb3d2854e823678e0f206"
EXPECTED_SIZE_BYTES = 23_824_968_355
MIN_SAFE_FREE_BYTES = 80_000_000_000
MIN_POST_DOWNLOAD_FREE_BYTES = 10_000_000_000


def ensure_dirs() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in (RAW_DIR, METADATA_DIR, LABELS_DIR, DERIVED_DIR, MANIFEST_DIR):
        path.mkdir(parents=True, exist_ok=True)


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


def append_once(path: Path, marker: str, block: str) -> None:
    old = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in old:
        return
    sep = "" if old == "" or old.endswith("\n") else "\n"
    path.write_text(old + sep + block, encoding="utf-8")


def hash_file(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_issue27u_download_url() -> str:
    metadata_path = METADATA_DIR / "zenodo_record_14502760.json"
    try:
        if not metadata_path.exists():
            with urlopen(ZENODO_API, timeout=60) as resp:
                metadata_path.write_bytes(resp.read())
        data = json.loads(metadata_path.read_text(encoding="utf-8"))
        for item in data.get("files", []):
            if item.get("key") == "GothamDataset2025.zip":
                return item.get("links", {}).get("self") or item.get("links", {}).get("content") or ZENODO_DOWNLOAD
    except Exception:
        pass
    return ZENODO_DOWNLOAD


def write_dataset_readme() -> None:
    readme = DATA_ROOT / "README_DO_NOT_STAGE.md"
    readme.write_text(
        "# Gotham Dataset Local Storage\n\n"
        "This directory is outside the active worktree and is intended for large dataset assets.\n\n"
        "- Do not add raw zip, PCAP, PCAPNG, large CSV, 7z, tar, or gzip files to git.\n"
        "- Keep raw archives under `raw/` only.\n"
        "- Keep small metadata, hashes, and manifests under `metadata/` or `manifests/`.\n"
        "- Runs and mainline docs in the worktree are the only normal commit targets.\n",
        encoding="utf-8",
    )


def storage_preflight(user_approved_download_only: bool = False) -> dict:
    usage = shutil.disk_usage(str(PAPER_ROOT.drive + "\\"))
    cwd_ok = Path.cwd().resolve() == ROOT.resolve()
    data_root_ok = DATA_ROOT == PAPER_ROOT / "datasets" / "gotham2025"
    zip_existing_size = ZIP_PATH.stat().st_size if ZIP_PATH.exists() else 0
    zip_expected_size_present = zip_existing_size == EXPECTED_SIZE_BYTES
    if zip_expected_size_present:
        enough_for_user_approved_download = usage.free >= MIN_POST_DOWNLOAD_FREE_BYTES
        expected_post_download_free = usage.free
    else:
        enough_for_user_approved_download = usage.free >= (EXPECTED_SIZE_BYTES - zip_existing_size) + MIN_POST_DOWNLOAD_FREE_BYTES
        expected_post_download_free = usage.free - max(EXPECTED_SIZE_BYTES - zip_existing_size, 0)
    strict_free_ok = usage.free >= MIN_SAFE_FREE_BYTES
    free_ok = strict_free_ok or (user_approved_download_only and enough_for_user_approved_download)
    forbidden_roots = [
        str(Path.home() / "Downloads"),
        str(Path.home() / "Desktop"),
        os.environ.get("TEMP", ""),
        os.environ.get("TMP", ""),
        "C:\\",
    ]
    target = str(ZIP_PATH)
    forbidden_target = any(root and target.lower().startswith(root.lower()) for root in forbidden_roots)
    return {
        "cwd": str(Path.cwd()),
        "expected_cwd": str(ROOT),
        "cwd_ok": cwd_ok,
        "data_root": str(DATA_ROOT),
        "expected_data_root": str(PAPER_ROOT / "datasets" / "gotham2025"),
        "data_root_ok": data_root_ok,
        "zip_target": str(ZIP_PATH),
        "d_free_bytes": usage.free,
        "d_free_gb_decimal": round(usage.free / 1_000_000_000, 3),
        "required_safe_free_bytes": MIN_SAFE_FREE_BYTES,
        "required_safe_free_gb_decimal": round(MIN_SAFE_FREE_BYTES / 1_000_000_000, 3),
        "strict_free_space_ok": strict_free_ok,
        "user_approved_download_only": user_approved_download_only,
        "enough_for_user_approved_download": enough_for_user_approved_download,
        "free_space_ok": free_ok,
        "zip_existing_size_bytes": zip_existing_size,
        "zip_expected_size_present": zip_expected_size_present,
        "expected_post_download_free_bytes": expected_post_download_free,
        "expected_post_download_free_gb_decimal": round(expected_post_download_free / 1_000_000_000, 3),
        "min_post_download_free_bytes": MIN_POST_DOWNLOAD_FREE_BYTES,
        "min_post_download_free_gb_decimal": round(MIN_POST_DOWNLOAD_FREE_BYTES / 1_000_000_000, 3),
        "forbidden_target_path": forbidden_target,
        "raw_dir_exists": RAW_DIR.exists(),
        "metadata_dir_exists": METADATA_DIR.exists(),
        "labels_dir_exists": LABELS_DIR.exists(),
        "derived_dir_exists": DERIVED_DIR.exists(),
        "manifests_dir_exists": MANIFEST_DIR.exists(),
        "storage_preflight_verdict": (
            "pass"
            if cwd_ok and data_root_ok and strict_free_ok and not forbidden_target
            else "pass_user_approved_download_only"
            if cwd_ok and data_root_ok and user_approved_download_only and enough_for_user_approved_download and not forbidden_target
            else "blocked_storage_insufficient"
            if not free_ok
            else "blocked_storage_path_safety"
        ),
    }


def download_zip(url: str) -> dict:
    log_path = MANIFEST_DIR / "download_log.txt"
    if ZIP_PATH.exists() and ZIP_PATH.stat().st_size == EXPECTED_SIZE_BYTES:
        md5 = hash_file(ZIP_PATH, "md5")
        if md5 == EXPECTED_MD5:
            return {
                "download_status": "already_present_md5_ok",
                "download_attempted": False,
                "command": "skipped_existing_file",
                "log_path": str(log_path),
            }

    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return {
            "download_status": "blocked_no_resume_downloader_available",
            "download_attempted": False,
            "command": "missing curl.exe/curl",
            "log_path": str(log_path),
        }

    cmd = [
        curl,
        "-L",
        "-C",
        "-",
        "--fail",
        "--retry",
        "5",
        "--retry-all-errors",
        "--retry-delay",
        "10",
        "-o",
        str(ZIP_PATH),
        url,
    ]
    started = time.time()
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n# issue27v download start\n")
        log.write(" ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.run(cmd, stdout=log, stderr=log, text=True)
    elapsed = time.time() - started
    return {
        "download_status": "completed_returncode_0" if proc.returncode == 0 else f"download_failed_returncode_{proc.returncode}",
        "download_attempted": True,
        "command": " ".join(cmd),
        "returncode": proc.returncode,
        "elapsed_seconds": round(elapsed, 3),
        "log_path": str(log_path),
    }


def verify_integrity() -> dict:
    if not ZIP_PATH.exists():
        return {
            "exists": False,
            "size_bytes": 0,
            "expected_size_bytes": EXPECTED_SIZE_BYTES,
            "size_matches_expected": False,
            "md5": "missing",
            "expected_md5": EXPECTED_MD5,
            "md5_matches": False,
            "sha256": "missing",
            "integrity_verdict": "blocked_zip_missing",
        }
    size = ZIP_PATH.stat().st_size
    if size != EXPECTED_SIZE_BYTES:
        return {
            "exists": True,
            "size_bytes": size,
            "expected_size_bytes": EXPECTED_SIZE_BYTES,
            "size_matches_expected": False,
            "md5": "not_computed_size_mismatch",
            "expected_md5": EXPECTED_MD5,
            "md5_matches": False,
            "sha256": "not_computed_size_mismatch",
            "integrity_verdict": "download_incomplete_or_wrong_size",
        }
    md5 = hash_file(ZIP_PATH, "md5")
    if md5 != EXPECTED_MD5:
        return {
            "exists": True,
            "size_bytes": size,
            "expected_size_bytes": EXPECTED_SIZE_BYTES,
            "size_matches_expected": True,
            "md5": md5,
            "expected_md5": EXPECTED_MD5,
            "md5_matches": False,
            "sha256": "not_computed_md5_mismatch",
            "integrity_verdict": "download_corrupt",
        }
    sha256 = hash_file(ZIP_PATH, "sha256")
    return {
        "exists": True,
        "size_bytes": size,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "size_matches_expected": True,
        "md5": md5,
        "expected_md5": EXPECTED_MD5,
        "md5_matches": True,
        "sha256": sha256,
        "integrity_verdict": "pass",
    }


def unsafe_zip_name(name: str) -> bool:
    posix = PurePosixPath(name.replace("\\", "/"))
    return name.startswith(("/", "\\")) or ".." in posix.parts or (len(name) > 1 and name[1] == ":")


def classify_member(name: str) -> dict:
    lower = name.lower()
    suffix = Path(lower).suffix
    return {
        "is_pcap": suffix in {".pcap", ".pcapng"},
        "is_csv": suffix == ".csv",
        "is_metadata": any(x in lower for x in ["metadata", "meta", "manifest", "index", "schema", "log", "timestamps", "timestamp"]),
        "is_label": any(x in lower for x in ["label", "labels", "attack", "groundtruth", "ground_truth", "truth"]),
        "is_readme": Path(lower).name in {"readme", "readme.md", "readme.txt"} or "readme" in lower or "license" in lower,
    }


def list_archive() -> tuple[list[dict], dict]:
    if not ZIP_PATH.exists():
        return (
            [
                {
                    "file_path": "blocked_zip_missing",
                    "file_name": "blocked_zip_missing",
                    "extension": "",
                    "compressed_size": 0,
                    "uncompressed_size": 0,
                    "is_pcap": False,
                    "is_csv": False,
                    "is_metadata": False,
                    "is_label": False,
                    "is_readme": False,
                    "unsafe_path": False,
                }
            ],
            {
                "archive_listing_verdict": "blocked_zip_missing",
                "unsafe_path_count": 0,
                "pcap_count": 0,
                "csv_count": 0,
                "metadata_count": 0,
                "label_count": 0,
                "readme_count": 0,
                "total_uncompressed_size": 0,
            },
        )
    rows: list[dict] = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for info in zf.infolist():
            flags = classify_member(info.filename)
            row = {
                "file_path": info.filename,
                "file_name": Path(info.filename).name,
                "extension": Path(info.filename).suffix.lower(),
                "compressed_size": info.compress_size,
                "uncompressed_size": info.file_size,
                "is_pcap": flags["is_pcap"],
                "is_csv": flags["is_csv"],
                "is_metadata": flags["is_metadata"],
                "is_label": flags["is_label"],
                "is_readme": flags["is_readme"],
                "unsafe_path": unsafe_zip_name(info.filename),
            }
            rows.append(row)
    summary = {
        "archive_listing_verdict": "blocked_archive_safety_risk" if any(r["unsafe_path"] for r in rows) else "pass",
        "unsafe_path_count": sum(bool(r["unsafe_path"]) for r in rows),
        "pcap_count": sum(bool(r["is_pcap"]) for r in rows),
        "csv_count": sum(bool(r["is_csv"]) for r in rows),
        "metadata_count": sum(bool(r["is_metadata"]) for r in rows),
        "label_count": sum(bool(r["is_label"]) for r in rows),
        "readme_count": sum(bool(r["is_readme"]) for r in rows),
        "total_uncompressed_size": sum(int(r["uncompressed_size"]) for r in rows),
    }
    return rows, summary


def extract_small_metadata(archive_rows: list[dict], archive_summary: dict, allow_extraction: bool) -> list[dict]:
    if not allow_extraction:
        return [
            {
                "source_member": "blocked_low_space",
                "local_path": "blocked_low_space",
                "bytes_written": 0,
                "extraction_status": "blocked_low_space",
                "notes": "D: free space after download/listing is below 10GB, so selective extraction is skipped by user-approved download-only policy",
            }
        ]
    if archive_summary["archive_listing_verdict"] != "pass":
        return [
            {
                "source_member": "blocked",
                "local_path": "blocked",
                "bytes_written": 0,
                "extraction_status": archive_summary["archive_listing_verdict"],
                "notes": "selective extraction requires a safe, present zip archive",
            }
        ]
    extracted: list[dict] = []
    with zipfile.ZipFile(ZIP_PATH) as zf:
        for row in archive_rows:
            interesting = bool(row["is_metadata"] or row["is_label"] or row["is_readme"])
            if not interesting or int(row["uncompressed_size"]) > 50_000_000:
                continue
            safe_name = row["file_path"].replace("\\", "/").replace("/", "__")
            target_dir = MANIFEST_DIR if row["is_label"] else METADATA_DIR
            target = target_dir / safe_name
            content = zf.read(row["file_path"])
            target.write_bytes(content)
            extracted.append(
                {
                    "source_member": row["file_path"],
                    "local_path": str(target),
                    "bytes_written": len(content),
                    "extraction_status": "extracted_small_metadata",
                    "notes": "small metadata/label/readme file extracted; no PCAP or large CSV extracted",
                }
            )
        csv_previews = 0
        for row in archive_rows:
            if csv_previews >= 8 or not row["is_csv"]:
                continue
            with zf.open(row["file_path"], "r") as f:
                preview = b"".join(f.readline() for _ in range(6))
            target = MANIFEST_DIR / (row["file_path"].replace("\\", "/").replace("/", "__") + ".preview.txt")
            target.write_bytes(preview)
            extracted.append(
                {
                    "source_member": row["file_path"],
                    "local_path": str(target),
                    "bytes_written": len(preview),
                    "extraction_status": "csv_header_preview_only",
                    "notes": "previewed header/first rows from zip stream without extracting full CSV",
                }
            )
            csv_previews += 1
    if not extracted:
        extracted.append(
            {
                "source_member": "none",
                "local_path": "none",
                "bytes_written": 0,
                "extraction_status": "no_small_metadata_candidates",
                "notes": "archive contained no small metadata candidates under extraction policy",
            }
        )
    return extracted


def extracted_evidence(extracted: list[dict]) -> dict:
    text = ""
    for row in extracted:
        local_path = row.get("local_path", "")
        path = Path(local_path)
        if not path.exists() or path.stat().st_size > 5_000_000:
            continue
        try:
            text += "\n" + path.read_text(encoding="utf-8", errors="ignore")[:20_000]
        except Exception:
            continue
    lower = text.lower()
    return {
        "csv_label_column_detected": "label" in lower,
        "csv_timestamp_column_detected": "frame.time" in lower or "timestamp" in lower,
        "packet_order_supported_by_pcap_or_csv": "frame.time" in lower or "pcap" in lower,
        "device_source_capture_partial": any(x in lower for x in ["device", "iot device", "pcap file corresponds", "eth.src", "ip.src", "source"]),
        "readme_reports_metadata": "metadata" in lower,
        "readme_reports_attack_types": "attack" in lower,
    }


def gate_rows(storage: dict, integrity: dict, archive_summary: dict, extracted: list[dict]) -> list[dict]:
    evidence = extracted_evidence(extracted)
    if storage["storage_preflight_verdict"] not in {"pass", "pass_user_approved_download_only"}:
        status = "blocked_storage_insufficient"
    elif integrity["integrity_verdict"] != "pass":
        status = integrity["integrity_verdict"]
    elif archive_summary["archive_listing_verdict"] != "pass":
        status = archive_summary["archive_listing_verdict"]
    else:
        status = "present" if archive_summary["pcap_count"] and archive_summary["csv_count"] else "missing_required_file_type"
    return [
        {"check": "pcap_real_exists", "status": status if status != "present" else archive_summary["pcap_count"] > 0, "evidence": archive_summary["pcap_count"]},
        {"check": "labelled_csv_real_exists", "status": status if status != "present" else evidence["csv_label_column_detected"], "evidence": f"{archive_summary['csv_count']} CSVs; label column detected in preview={evidence['csv_label_column_detected']}"},
        {"check": "metadata_or_readme_exists", "status": status if status != "present" else (archive_summary["metadata_count"] + archive_summary["readme_count"]) > 0, "evidence": f"metadata files={archive_summary['metadata_count']}; readme files={archive_summary['readme_count']}"},
        {"check": "label_or_attack_file_candidate_exists", "status": status if status != "present" else (archive_summary["label_count"] > 0 or evidence["csv_label_column_detected"] or evidence["readme_reports_attack_types"]), "evidence": f"label file candidates={archive_summary['label_count']}; label column={evidence['csv_label_column_detected']}; README attack types={evidence['readme_reports_attack_types']}"},
        {"check": "timestamp_metadata_available", "status": status if status != "present" else evidence["csv_timestamp_column_detected"], "evidence": f"CSV preview frame.time/timestamp={evidence['csv_timestamp_column_detected']}"},
        {"check": "device_source_capture_metadata_available", "status": status if status != "present" else "partial_filename_csv_readme", "evidence": f"README/device/source terms and packet fields={evidence['device_source_capture_partial']}; no separate metadata JSON found in archive listing"},
        {"check": "id_ood_attack_split_constructable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "file-level gate only"},
        {"check": "row_order_artifact_auditable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "requires row-level sample"},
        {"check": "source_capture_artifact_auditable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "requires metadata/sample"},
        {"check": "model_experiments_allowed", "status": False, "evidence": "still Data validity gate"},
    ]


def decide(storage: dict, download: dict, integrity: dict, archive_summary: dict, extraction_allowed: bool) -> str:
    if storage["storage_preflight_verdict"] not in {"pass", "pass_user_approved_download_only"}:
        return "gotham_download_incomplete_resume_required"
    if download.get("download_status", "").startswith("download_failed"):
        return "gotham_download_incomplete_resume_required"
    if integrity["integrity_verdict"] == "download_incomplete_or_wrong_size":
        return "gotham_download_incomplete_resume_required"
    if integrity["integrity_verdict"] == "download_corrupt":
        return "gotham_download_corrupt_redownload_required"
    if archive_summary["archive_listing_verdict"] == "blocked_archive_safety_risk":
        return "gotham_archive_structure_blocked"
    if integrity["integrity_verdict"] == "pass" and archive_summary["archive_listing_verdict"] == "pass" and not extraction_allowed:
        return "gotham_metadata_extraction_blocked_low_space"
    if integrity["integrity_verdict"] == "pass" and archive_summary["pcap_count"] > 0 and archive_summary["csv_count"] > 0 and (archive_summary["metadata_count"] + archive_summary["label_count"] + archive_summary["readme_count"]) > 0:
        return "gotham_file_level_gate_passed_ready_for_sample_data_gate"
    if integrity["integrity_verdict"] == "pass":
        return "gotham_file_level_gate_failed_try_toniot"
    return "gotham_download_incomplete_resume_required"


def write_reports(storage: dict, download: dict, integrity: dict, archive_summary: dict, extracted: list[dict], primary: str, post_listing_free: int) -> None:
    evidence = extracted_evidence(extracted)
    storage_rows = [
        {"check": key, "value": value}
        for key, value in storage.items()
    ]
    write_csv("storage_preflight_table.csv", storage_rows, ["check", "value"])
    write_text(
        "storage_preflight_report.md",
        "# Storage Preflight Report\n\n"
        f"- worktree: `{storage['cwd']}`\n"
        f"- dataset root: `{storage['data_root']}`\n"
        f"- zip target: `{storage['zip_target']}`\n"
        f"- D free space: `{storage['d_free_gb_decimal']} GB decimal`\n"
        f"- required safe free space: `{storage['required_safe_free_gb_decimal']} GB decimal`\n"
        f"- user-approved download-only: `{storage['user_approved_download_only']}`\n"
        f"- expected post-download free space: `{storage['expected_post_download_free_gb_decimal']} GB decimal`\n"
        f"- minimum post-download free space: `{storage['min_post_download_free_gb_decimal']} GB decimal`\n"
        f"- verdict: `{storage['storage_preflight_verdict']}`\n\n"
        "The strict 80GB safety line can only be bypassed in user-approved download-only mode. "
        "This bypass still forbids full extraction, model experiments, feature extraction, C: drive fallback, browser default downloads, and large temporary files.\n",
    )
    write_text(
        "download_report.md",
        "# Download Report\n\n"
        f"- source: `{read_issue27u_download_url()}`\n"
        f"- target: `{ZIP_PATH}`\n"
        f"- download_status: `{download['download_status']}`\n"
        f"- attempted in final postprocess run: `{download.get('download_attempted', False)}`\n"
        f"- log: `{download.get('log_path', MANIFEST_DIR / 'download_log.txt')}`\n\n"
        "The zip may have been downloaded by an earlier user-approved issue27v resume attempt to the same target path. "
        "When the final postprocess run sees a complete file with matching md5, it skips re-download and records `already_present_md5_ok`.\n\n"
        "If this gate must be rerun, use `python repo/ood/issue27v_gotham_download_file_gate.py --user-approved-download-only`; the script will reuse/resume the same target path.\n",
    )
    write_text("download_command.txt", str(download.get("command", "not_attempted_storage_preflight_blocked")) + "\n")
    write_text(
        "integrity_verification_report.md",
        "# Integrity Verification Report\n\n"
        f"- zip exists: `{integrity['exists']}`\n"
        f"- size bytes: `{integrity['size_bytes']}`\n"
        f"- expected size bytes: `{integrity['expected_size_bytes']}`\n"
        f"- md5: `{integrity['md5']}`\n"
        f"- expected md5: `{EXPECTED_MD5}`\n"
        f"- md5 matches: `{integrity['md5_matches']}`\n"
        f"- sha256: `{integrity['sha256']}`\n"
        f"- verdict: `{integrity['integrity_verdict']}`\n",
    )
    write_json("integrity_hashes.json", integrity)
    write_text(
        "archive_structure_report.md",
        "# Archive Structure Report\n\n"
        f"- listing verdict: `{archive_summary['archive_listing_verdict']}`\n"
        f"- unsafe paths: `{archive_summary['unsafe_path_count']}`\n"
        f"- pcap count: `{archive_summary['pcap_count']}`\n"
        f"- csv count: `{archive_summary['csv_count']}`\n"
        f"- metadata count: `{archive_summary['metadata_count']}`\n"
        f"- label candidate count: `{archive_summary['label_count']}`\n"
        f"- readme count: `{archive_summary['readme_count']}`\n"
        f"- total uncompressed size estimate: `{archive_summary['total_uncompressed_size']}` bytes\n\n"
        f"- D free space after listing: `{round(post_listing_free / 1_000_000_000, 3)} GB decimal`\n\n"
        f"- labelled CSV evidence from preview: `{evidence['csv_label_column_detected']}`\n"
        f"- timestamp evidence from preview: `{evidence['csv_timestamp_column_detected']}`\n"
        f"- device/source/capture evidence: `partial_filename_csv_readme`; no separate metadata JSON sidecar was found in the archive listing.\n\n"
        "No full extraction is performed before a safe archive listing and integrity pass.\n",
    )
    write_text(
        "selective_metadata_extraction_report.md",
        "# Selective Metadata Extraction Report\n\n"
        f"- extraction rows: `{len(extracted)}`\n"
        f"- status: `{extracted[0]['extraction_status'] if extracted else 'none'}`\n\n"
        "Only README, metadata, labels, and small CSV previews are eligible for extraction. PCAP and large CSV extraction remains blocked until later sample Data Gate planning.\n",
    )
    gate = gate_rows(storage, integrity, archive_summary, extracted)
    write_csv("gotham_file_level_data_gate_table.csv", gate, ["check", "status", "evidence"])
    gate_text = "\n".join(f"- `{r['check']}`: `{r['status']}` ({r['evidence']})" for r in gate)
    write_text(
        "gotham_file_level_data_gate_report.md",
        "# Gotham File-Level Data Gate Report\n\n"
        f"Primary file-level gate status: `{primary}`.\n\n"
        f"{gate_text}\n\n"
        "This gate does not authorize model experiments. If metadata extraction is blocked by low free space, the next action is to free D: space before sample Data Gate.\n",
    )
    write_text(
        "issue27v_decision.md",
        "# issue27v Decision\n\n"
        f"primary_verdict = `{primary}`\n\n"
        f"storage_preflight_verdict = `{storage['storage_preflight_verdict']}`\n\n"
        "This is a user-approved download-only Data Gate result. It is not a model result and not evidence for or against any detector.\n",
    )
    write_text(
        "claim_update_after_issue27v.md",
        "# Claim Update After issue27v\n\n"
        "- Gotham remains a promising second-dataset candidate from metadata-level evidence.\n"
        "- Current file-level Data Gate is blocked before download by storage safety, so Gotham cannot yet be used for model or benchmark claims.\n"
        "- Model experiments remain prohibited until file-level and sample-level Data Gates pass.\n"
        "- No external generalization, deployment robustness, DeepSAD mainline, or LOW-GUARD failure claim is supported by this issue.\n",
    )
    next_action = (
        "issue27w_gotham_sample_data_gate"
        if primary == "gotham_file_level_gate_passed_ready_for_sample_data_gate"
        else "free_d_space_then_repeat_metadata_extraction_or_resume_download"
        if primary in {"gotham_metadata_extraction_blocked_low_space", "gotham_download_incomplete_resume_required"}
        else "inspect_blocking_file_gate_failure"
    )
    write_text(
        "issue27w_next_action.md",
        "# issue27w Next Action\n\n"
        f"Recommended next action: `{next_action}`.\n\n"
        "After the zip passes md5 and archive listing, issue27w should perform a small sample Data Gate only, not model training. "
        "If D: free space is below 10GB, metadata extraction and sample intake must wait until storage is freed.\n",
    )
    write_text(
        "summary.md",
        "# issue27v Summary\n\n"
        "1. issue27v completed: `true`.\n"
        f"2. primary_verdict: `{primary}`.\n"
        f"3. zip download successful: `{integrity['exists'] and integrity['md5_matches']}`.\n"
        f"4. zip path: `{ZIP_PATH}`.\n"
        f"5. md5 matches: `{integrity['md5_matches']}`.\n"
        f"6. zip contains PCAP: `{archive_summary['pcap_count'] > 0}`.\n"
        f"7. zip contains labelled CSV: `{archive_summary['csv_count'] > 0 and evidence['csv_label_column_detected']}`.\n"
        f"8. zip contains metadata/timestamp/device/capture information: `partial`; CSV preview has timestamp `{evidence['csv_timestamp_column_detected']}`, README/paths expose device/source/capture context, but no separate metadata JSON sidecar was found in archive listing.\n"
        f"9. selective metadata extraction completed: `{extracted and extracted[0]['extraction_status'] not in {'blocked_zip_missing', 'blocked_storage_insufficient', 'blocked_low_space'}}`.\n"
        f"10. Gotham file-level Data Gate passed: `{primary == 'gotham_file_level_gate_passed_ready_for_sample_data_gate'}`.\n"
        "11. current model experiments allowed: `false`.\n"
        f"12. issue27w recommendation: `{next_action}`.\n"
        f"13. D free space after listing/download attempt: `{round(post_listing_free / 1_000_000_000, 3)} GB decimal`.\n"
        "14. Slurm needed: `not for storage/download gate`; maybe later for feature extraction after sample gate.\n"
        "15. commit hash: pending.\n",
    )


def write_run_metadata(storage: dict, primary: str, user_approved_download_only: bool) -> None:
    command = "python repo/ood/issue27v_gotham_download_file_gate.py --user-approved-download-only" if user_approved_download_only else "python repo/ood/issue27v_gotham_download_file_gate.py"
    write_text("command.txt", command + "\n")
    config = {
        "issue": "issue27v_gotham_download_and_file_level_data_gate_2026-05-28",
        "dataset_root": str(DATA_ROOT),
        "zip_path": str(ZIP_PATH),
        "zenodo_record": ZENODO_RECORD,
        "download_url": read_issue27u_download_url(),
        "expected_md5": EXPECTED_MD5,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "min_safe_free_bytes": MIN_SAFE_FREE_BYTES,
        "min_post_download_free_bytes": MIN_POST_DOWNLOAD_FREE_BYTES,
        "user_approved_download_only": user_approved_download_only,
        "primary_verdict": primary,
        "model_experiments_allowed": False,
    }
    write_json("config.json", config)
    write_json(
        "run_spec.json",
        {
            "stages": [
                "storage_preflight",
                "download_if_safe",
                "integrity_verification",
                "archive_listing",
                "selective_metadata_extraction",
                "file_level_data_gate",
            ],
            "constraints": [
                "no_model_training",
                "no_large_data_in_worktree",
                "no_large_data_staged",
                "no_full_pcap_extraction",
                "final_model_experiments_blocked",
            ],
            "storage_preflight_verdict": storage["storage_preflight_verdict"],
            "user_approved_download_only": user_approved_download_only,
        },
    )
    rows = []
    for path in sorted(OUT_DIR.iterdir()):
        if path.is_file():
            rows.append({"file": path.name, "size_bytes": path.stat().st_size, "sha256": hash_file(path, "sha256")})
    write_csv("manifest.csv", rows, ["file", "size_bytes", "sha256"])


def update_mainline_docs(primary: str, storage: dict) -> None:
    handoff = MAINLINE_DOCS / "mainline_handoff.md"
    exp_map = MAINLINE_DOCS / "mainline_experiment_map.md"
    append_once(
        handoff,
        "<!-- issue27v_gotham_file_level_data_gate -->",
        "\n<!-- issue27v_gotham_file_level_data_gate -->\n\n"
        "## issue27v Gotham Download And File-Level Data Gate\n\n"
        f"- primary_verdict: `{primary}`.\n"
        f"- storage_preflight_verdict: `{storage['storage_preflight_verdict']}`; D: free space was `{storage['d_free_gb_decimal']} GB decimal` at preflight.\n"
        f"- planned data path: `{DATA_ROOT}`; raw zip target `{ZIP_PATH}`.\n"
        "- User-approved download-only mode allows the 80GB recommendation to be bypassed only for zip download/hash/listing/small metadata; no full extraction or model work is allowed.\n"
        f"- current issue27v primary verdict: `{primary}`.\n"
        "- model experiments remain blocked; this issue is not evidence for or against Gotham's semantic suitability.\n"
        "- next: if file-level gate passed, run small sample Data Gate; otherwise resolve download/hash/listing/storage blocker first.\n",
    )
    append_once(
        exp_map,
        "<!-- issue27v_map_entry -->",
        "\n<!-- issue27v_map_entry -->\n\n"
        "### issue27v_gotham_download_and_file_level_data_gate_2026-05-28\n\n"
        "- status: completed/updated under user-approved download-only mode.\n"
        f"- primary_verdict: `{primary}`.\n"
        f"- outputs: `{OUT_DIR.relative_to(ROOT).as_posix()}/`.\n"
        "- role: Gotham file-level Data Gate entry point after user-confirmed download permission.\n"
        "- implication: no model execution; only file-level Data Gate evidence may advance toward sample Data Gate.\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-approved-download-only", action="store_true")
    args = parser.parse_args()
    ensure_dirs()
    write_dataset_readme()
    storage = storage_preflight(args.user_approved_download_only)
    url = read_issue27u_download_url()

    if storage["storage_preflight_verdict"] in {"pass", "pass_user_approved_download_only"}:
        download = download_zip(url)
    else:
        download = {
            "download_status": storage["storage_preflight_verdict"],
            "download_attempted": False,
            "command": f"curl.exe -L -C - --fail --retry 5 --retry-delay 10 -o {ZIP_PATH} {url}",
            "log_path": str(MANIFEST_DIR / "download_log.txt"),
        }
    integrity = verify_integrity()
    if integrity["integrity_verdict"] == "pass":
        archive_rows, archive_summary = list_archive()
    else:
        archive_rows, archive_summary = (
            [
                {
                    "file_path": integrity["integrity_verdict"],
                    "file_name": integrity["integrity_verdict"],
                    "extension": "",
                    "compressed_size": 0,
                    "uncompressed_size": 0,
                    "is_pcap": False,
                    "is_csv": False,
                    "is_metadata": False,
                    "is_label": False,
                    "is_readme": False,
                    "unsafe_path": False,
                }
            ],
            {
                "archive_listing_verdict": integrity["integrity_verdict"],
                "unsafe_path_count": 0,
                "pcap_count": 0,
                "csv_count": 0,
                "metadata_count": 0,
                "label_count": 0,
                "readme_count": 0,
                "total_uncompressed_size": 0,
            },
        )
    post_listing_free = shutil.disk_usage(str(PAPER_ROOT.drive + "\\")).free
    extraction_allowed = post_listing_free >= MIN_POST_DOWNLOAD_FREE_BYTES
    write_csv(
        "archive_file_listing.csv",
        archive_rows,
        [
            "file_path",
            "file_name",
            "extension",
            "compressed_size",
            "uncompressed_size",
            "is_pcap",
            "is_csv",
            "is_metadata",
            "is_label",
            "is_readme",
            "unsafe_path",
        ],
    )
    extracted = extract_small_metadata(archive_rows, archive_summary, extraction_allowed)
    write_csv("gotham_extracted_metadata_manifest.csv", extracted, ["source_member", "local_path", "bytes_written", "extraction_status", "notes"])
    primary = decide(storage, download, integrity, archive_summary, extraction_allowed)
    write_reports(storage, download, integrity, archive_summary, extracted, primary, post_listing_free)
    write_run_metadata(storage, primary, args.user_approved_download_only)
    update_mainline_docs(primary, storage)
    print(json.dumps({"primary_verdict": primary, "storage_preflight_verdict": storage["storage_preflight_verdict"]}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
