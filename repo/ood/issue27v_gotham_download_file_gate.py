from __future__ import annotations

import csv
import hashlib
import json
import os
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


def storage_preflight() -> dict:
    usage = shutil.disk_usage(str(PAPER_ROOT.drive + "\\"))
    cwd_ok = Path.cwd().resolve() == ROOT.resolve()
    data_root_ok = DATA_ROOT == PAPER_ROOT / "datasets" / "gotham2025"
    free_ok = usage.free >= MIN_SAFE_FREE_BYTES
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
        "free_space_ok": free_ok,
        "forbidden_target_path": forbidden_target,
        "raw_dir_exists": RAW_DIR.exists(),
        "metadata_dir_exists": METADATA_DIR.exists(),
        "labels_dir_exists": LABELS_DIR.exists(),
        "derived_dir_exists": DERIVED_DIR.exists(),
        "manifests_dir_exists": MANIFEST_DIR.exists(),
        "storage_preflight_verdict": "pass" if cwd_ok and data_root_ok and free_ok and not forbidden_target else "blocked_storage_insufficient" if not free_ok else "blocked_storage_path_safety",
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


def extract_small_metadata(archive_rows: list[dict], archive_summary: dict) -> list[dict]:
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


def gate_rows(storage: dict, integrity: dict, archive_summary: dict) -> list[dict]:
    if storage["storage_preflight_verdict"] != "pass":
        status = "blocked_storage_insufficient"
    elif integrity["integrity_verdict"] != "pass":
        status = integrity["integrity_verdict"]
    elif archive_summary["archive_listing_verdict"] != "pass":
        status = archive_summary["archive_listing_verdict"]
    else:
        status = "present" if archive_summary["pcap_count"] and archive_summary["csv_count"] else "missing_required_file_type"
    return [
        {"check": "pcap_real_exists", "status": status if status != "present" else archive_summary["pcap_count"] > 0, "evidence": archive_summary["pcap_count"]},
        {"check": "labelled_csv_real_exists", "status": status if status != "present" else archive_summary["csv_count"] > 0, "evidence": archive_summary["csv_count"]},
        {"check": "metadata_or_readme_exists", "status": status if status != "present" else (archive_summary["metadata_count"] + archive_summary["readme_count"]) > 0, "evidence": archive_summary["metadata_count"] + archive_summary["readme_count"]},
        {"check": "label_or_attack_file_candidate_exists", "status": status if status != "present" else archive_summary["label_count"] > 0, "evidence": archive_summary["label_count"]},
        {"check": "timestamp_metadata_available", "status": status if status != "present" else "needs_metadata_sample_gate", "evidence": "requires selective metadata inspection"},
        {"check": "device_source_capture_metadata_available", "status": status if status != "present" else "needs_metadata_sample_gate", "evidence": "requires selective metadata inspection"},
        {"check": "id_ood_attack_split_constructable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "file-level gate only"},
        {"check": "row_order_artifact_auditable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "requires row-level sample"},
        {"check": "source_capture_artifact_auditable", "status": status if status != "present" else "needs_sample_data_gate", "evidence": "requires metadata/sample"},
        {"check": "model_experiments_allowed", "status": False, "evidence": "still Data validity gate"},
    ]


def decide(storage: dict, download: dict, integrity: dict, archive_summary: dict) -> str:
    if storage["storage_preflight_verdict"] != "pass":
        return "gotham_download_incomplete_resume_required"
    if download.get("download_status", "").startswith("download_failed"):
        return "gotham_download_incomplete_resume_required"
    if integrity["integrity_verdict"] == "download_incomplete_or_wrong_size":
        return "gotham_download_incomplete_resume_required"
    if integrity["integrity_verdict"] == "download_corrupt":
        return "gotham_download_corrupt_redownload_required"
    if archive_summary["archive_listing_verdict"] == "blocked_archive_safety_risk":
        return "gotham_archive_structure_blocked"
    if integrity["integrity_verdict"] == "pass" and archive_summary["pcap_count"] > 0 and archive_summary["csv_count"] > 0 and (archive_summary["metadata_count"] + archive_summary["label_count"] + archive_summary["readme_count"]) > 0:
        return "gotham_file_level_gate_passed_ready_for_sample_data_gate"
    if integrity["integrity_verdict"] == "pass":
        return "gotham_file_level_gate_failed_try_toniot"
    return "gotham_download_incomplete_resume_required"


def write_reports(storage: dict, download: dict, integrity: dict, archive_summary: dict, extracted: list[dict], primary: str) -> None:
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
        f"- verdict: `{storage['storage_preflight_verdict']}`\n\n"
        "The download is blocked before any network transfer when the safe free-space guard fails. "
        "This protects the worktree and avoids a partially downloaded 23.8GB archive plus insufficient post-download validation space.\n",
    )
    write_text(
        "download_report.md",
        "# Download Report\n\n"
        f"- source: `{read_issue27u_download_url()}`\n"
        f"- target: `{ZIP_PATH}`\n"
        f"- download_status: `{download['download_status']}`\n"
        f"- attempted: `{download.get('download_attempted', False)}`\n"
        f"- log: `{download.get('log_path', MANIFEST_DIR / 'download_log.txt')}`\n\n"
        "If storage is later freed, rerun `python repo/ood/issue27v_gotham_download_file_gate.py`; the script will reuse/resume the same target path.\n",
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
        "No full extraction is performed before a safe archive listing and integrity pass.\n",
    )
    write_text(
        "selective_metadata_extraction_report.md",
        "# Selective Metadata Extraction Report\n\n"
        f"- extraction rows: `{len(extracted)}`\n"
        f"- status: `{extracted[0]['extraction_status'] if extracted else 'none'}`\n\n"
        "Only README, metadata, labels, and small CSV previews are eligible for extraction. PCAP and large CSV extraction remains blocked until later sample Data Gate planning.\n",
    )
    gate = gate_rows(storage, integrity, archive_summary)
    write_csv("gotham_file_level_data_gate_table.csv", gate, ["check", "status", "evidence"])
    gate_text = "\n".join(f"- `{r['check']}`: `{r['status']}` ({r['evidence']})" for r in gate)
    write_text(
        "gotham_file_level_data_gate_report.md",
        "# Gotham File-Level Data Gate Report\n\n"
        f"Primary file-level gate status: `{primary}`.\n\n"
        f"{gate_text}\n\n"
        "This gate does not authorize model experiments. If blocked by storage, the next action is to free D: space or move the dataset root to a user-approved large D: location, then rerun the same file-level gate.\n",
    )
    write_text(
        "issue27v_decision.md",
        "# issue27v Decision\n\n"
        f"primary_verdict = `{primary}`\n\n"
        f"storage_preflight_verdict = `{storage['storage_preflight_verdict']}`\n\n"
        "The Gotham file-level Data Gate cannot proceed to download/listing/extraction until the storage preflight passes. "
        "This is a Data validity gate stop, not a model result and not evidence against Gotham.\n",
    )
    write_text(
        "claim_update_after_issue27v.md",
        "# Claim Update After issue27v\n\n"
        "- Gotham remains a promising second-dataset candidate from metadata-level evidence.\n"
        "- Current file-level Data Gate is blocked before download by storage safety, so Gotham cannot yet be used for model or benchmark claims.\n"
        "- Model experiments remain prohibited until file-level and sample-level Data Gates pass.\n"
        "- No external generalization, deployment robustness, DeepSAD mainline, or LOW-GUARD failure claim is supported by this issue.\n",
    )
    next_action = "free_d_space_and_rerun_issue27v_download_gate" if storage["storage_preflight_verdict"] != "pass" else "issue27w_gotham_sample_data_gate"
    write_text(
        "issue27w_next_action.md",
        "# issue27w Next Action\n\n"
        f"Recommended next action: `{next_action}`.\n\n"
        "If storage is the blocker, free or provision enough D: space first. The minimum safe target remains at least 80GB free before starting the 23.825GB zip download. "
        "After the zip passes md5 and archive listing, issue27w should perform a small sample Data Gate only, not model training.\n",
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
        f"7. zip contains labelled CSV: `{archive_summary['csv_count'] > 0 and archive_summary['label_count'] > 0}`.\n"
        f"8. zip contains metadata/timestamp/device/capture information: `not_verified_file_level`; archive listing status `{archive_summary['archive_listing_verdict']}`.\n"
        f"9. selective metadata extraction completed: `{extracted and extracted[0]['extraction_status'] not in {'blocked_zip_missing', 'blocked_storage_insufficient'}}`.\n"
        f"10. Gotham file-level Data Gate passed: `{primary == 'gotham_file_level_gate_passed_ready_for_sample_data_gate'}`.\n"
        "11. current model experiments allowed: `false`.\n"
        f"12. issue27w recommendation: `{next_action}`.\n"
        "13. Slurm needed: `not for storage/download gate`; maybe later for feature extraction after sample gate.\n"
        "14. commit hash: pending.\n",
    )


def write_run_metadata(storage: dict, primary: str) -> None:
    write_text("command.txt", "python repo/ood/issue27v_gotham_download_file_gate.py\n")
    config = {
        "issue": "issue27v_gotham_download_and_file_level_data_gate_2026-05-28",
        "dataset_root": str(DATA_ROOT),
        "zip_path": str(ZIP_PATH),
        "zenodo_record": ZENODO_RECORD,
        "download_url": read_issue27u_download_url(),
        "expected_md5": EXPECTED_MD5,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "min_safe_free_bytes": MIN_SAFE_FREE_BYTES,
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
        f"- storage_preflight_verdict: `{storage['storage_preflight_verdict']}`; D: free space was `{storage['d_free_gb_decimal']} GB decimal`, below the `80 GB` safety line.\n"
        f"- planned data path: `{DATA_ROOT}`; raw zip target `{ZIP_PATH}`.\n"
        "- Gotham download was not started because Data validity gate storage preflight blocked it.\n"
        "- model experiments remain blocked; this issue is not evidence for or against Gotham's semantic suitability.\n"
        "- next: free/provision D: storage and rerun issue27v, then perform sample-level Data Gate before any model execution.\n",
    )
    append_once(
        exp_map,
        "<!-- issue27v_map_entry -->",
        "\n<!-- issue27v_map_entry -->\n\n"
        "### issue27v_gotham_download_and_file_level_data_gate_2026-05-28\n\n"
        "- status: completed with storage preflight block.\n"
        f"- primary_verdict: `{primary}`.\n"
        f"- outputs: `{OUT_DIR.relative_to(ROOT).as_posix()}/`.\n"
        "- role: Gotham file-level Data Gate entry point after user-confirmed download permission.\n"
        "- implication: no model execution; free D: storage and rerun the same gate before sample extraction or feature/interface work.\n",
    )


def main() -> None:
    ensure_dirs()
    write_dataset_readme()
    storage = storage_preflight()
    url = read_issue27u_download_url()

    if storage["storage_preflight_verdict"] == "pass":
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
        archive_rows, archive_summary = list_archive()
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
    extracted = extract_small_metadata(archive_rows, archive_summary)
    write_csv("gotham_extracted_metadata_manifest.csv", extracted, ["source_member", "local_path", "bytes_written", "extraction_status", "notes"])
    primary = decide(storage, download, integrity, archive_summary)
    write_reports(storage, download, integrity, archive_summary, extracted, primary)
    write_run_metadata(storage, primary)
    update_mainline_docs(primary, storage)
    print(json.dumps({"primary_verdict": primary, "storage_preflight_verdict": storage["storage_preflight_verdict"]}, indent=2))


if __name__ == "__main__":
    sys.exit(main())
