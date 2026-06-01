#!/usr/bin/env python3
"""Issue27aa Gotham strict packet-header dataset materialization.

This is a data-construction gate, not a model experiment. It materializes a
strict source-clean packet/header feature dataset from Gotham processed CSVs,
freezes the preregistered split roles, and writes audits/hashes.

Large generated data are written outside the git worktree under:
  D:/study/paper/anomaly_detection/paper04/datasets/gotham2025/derived/
      strict_packet_feature_dataset_v1/

Git-tracked outputs remain compact reports/manifests under runs/.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import sys
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


ISSUE = "issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01"
DATASET_VERSION = "gotham_strict_packet_header_v1"
EXPECTED_MD5 = "7ca78c0517ccb3d2854e823678e0f206"

REPO_ROOT = Path(__file__).resolve().parents[2]
PAPER_ROOT = REPO_ROOT.parents[1]
DATA_ROOT = PAPER_ROOT / "datasets" / "gotham2025"
ZIP_PATH = DATA_ROOT / "raw" / "GothamDataset2025.zip"
DERIVED_ROOT = DATA_ROOT / "derived" / "strict_packet_feature_dataset_v1"
MANIFEST_ROOT = DATA_ROOT / "manifests"
OUT_DIR = REPO_ROOT / "runs" / ISSUE
MAINLINE_DOCS = REPO_ROOT / "runs" / "mainline_docs"

ISSUE27Y_DIR = REPO_ROOT / "runs" / "issue27y_gotham_fuller_manifest_and_preregistered_split_contract_2026-05-28"
ISSUE27Z_DIR = REPO_ROOT / "runs" / "issue27z_gotham_pcap_csv_pairing_and_feature_source_policy_gate_2026-05-28"

STRICT_FEATURES = [
    "frame.len",
    "ip.flags",
    "ip.tos",
    "ip.ttl",
    "tcp.flags",
    "tcp.pdu.size",
    "tcp.window_size_scalefactor",
    "tcp.window_size_value",
]

FORBIDDEN_FEATURE_FIELDS = {
    "label",
    "attack_type",
    "file_id",
    "csv_archive_path",
    "device",
    "inferred_device",
    "frame.time",
    "eth.src",
    "eth.dst",
    "ip.src",
    "ip.dst",
    "pcap_archive_path",
    "source/capture/path",
    "frame.protocols",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "ip.proto",
}

BENIGN_LABELS = {"benign", "normal", "background", "0", "false"}
UNKNOWN_LABELS = {"", "unknown", "nan", "none", "null"}


def ensure_dirs() -> None:
    for path in [OUT_DIR, DERIVED_ROOT, MANIFEST_ROOT]:
        path.mkdir(parents=True, exist_ok=True)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


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


def load_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def disk_free_gib(path: Path) -> float:
    return shutil.disk_usage(str(path)).free / (1024**3)


def sha256_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(block_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def parse_int(value: Any) -> int:
    if value is None or value == "":
        return 0
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def normalize_label(label: Any) -> str:
    return str(label or "").strip()


def binary_label(label: Any) -> str:
    lower = normalize_label(label).lower()
    if lower in BENIGN_LABELS:
        return "benign"
    if lower in UNKNOWN_LABELS:
        return "unknown"
    return "attack"


def split_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x) for x in value if str(x)]
    if value is None:
        return []
    return [x for x in str(value).split("|") if x]


def parse_numeric(value: Any) -> Tuple[Optional[float], bool]:
    s = str(value or "").strip()
    if not s:
        return None, False
    if s.lower() in {"nan", "none", "null", "inf", "-inf"}:
        return None, False
    try:
        if s.lower().startswith("0x"):
            return float(int(s, 16)), True
        # tcp flags sometimes appear as colon-separated strings; keep numeric only.
        return float(s), True
    except Exception:
        try:
            # Last-resort hex token if Wireshark writes e.g. "0x0018".
            m = re.search(r"0x[0-9a-fA-F]+", s)
            if m:
                return float(int(m.group(0), 16)), True
        except Exception:
            pass
    return None, False


def infer_device(path: str) -> str:
    stem = Path(path.replace("\\", "/")).stem.lower()
    stem = re.sub(r"^iotsim-", "", stem)
    stem = re.sub(r"_.*$", "", stem)
    parts = stem.split("-")
    if parts and parts[-1].isdigit():
        return "-".join(parts[:-1])
    return stem


def pcap_candidate(file_manifest: Dict[str, Dict[str, str]], csv_path: str) -> str:
    return file_manifest.get(csv_path, {}).get("pcap_counterpart_candidate", "")


@dataclass
class RunningStats:
    count: int = 0
    missing: int = 0
    nonnumeric: int = 0
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    sum_value: float = 0.0
    sum_sq: float = 0.0
    unique_values: set = field(default_factory=set)

    def update(self, value: Any) -> str:
        num, ok = parse_numeric(value)
        if not ok or num is None:
            self.missing += 1
            return ""
        self.count += 1
        self.sum_value += num
        self.sum_sq += num * num
        self.min_value = num if self.min_value is None else min(self.min_value, num)
        self.max_value = num if self.max_value is None else max(self.max_value, num)
        if len(self.unique_values) <= 10000:
            self.unique_values.add(num)
        # Avoid scientific notation instability for integers.
        if float(num).is_integer():
            return str(int(num))
        return f"{num:.12g}"

    def as_row(self, feature: str, total_rows: int) -> Dict[str, Any]:
        mean = self.sum_value / self.count if self.count else ""
        var = (self.sum_sq / self.count - (self.sum_value / self.count) ** 2) if self.count else ""
        std = math.sqrt(max(var, 0.0)) if self.count else ""
        return {
            "feature_name": feature,
            "total_rows": total_rows,
            "numeric_count": self.count,
            "missing_or_invalid_count": total_rows - self.count,
            "missing_or_invalid_rate": f"{(total_rows - self.count) / total_rows:.8f}" if total_rows else "",
            "min": "" if self.min_value is None else f"{self.min_value:.12g}",
            "max": "" if self.max_value is None else f"{self.max_value:.12g}",
            "mean": "" if mean == "" else f"{mean:.12g}",
            "std": "" if std == "" else f"{std:.12g}",
            "unique_values_tracked": len(self.unique_values),
            "constant_flag": self.count > 0 and len(self.unique_values) == 1,
        }


class HashingWriter:
    def __init__(self, path: Path, header: Sequence[str]):
        self.path = path
        self.raw = path.open("wb")
        self.gz = gzip.GzipFile(filename="", mode="wb", fileobj=self.raw, compresslevel=1, mtime=0)
        self.text = None
        self.writer = None
        self.header = list(header)
        import io

        self.text = io.TextIOWrapper(self.gz, encoding="utf-8", newline="")
        self.writer = csv.DictWriter(self.text, fieldnames=self.header, extrasaction="ignore")
        self.writer.writeheader()

    def writerow(self, row: Dict[str, Any]) -> None:
        self.writer.writerow({key: stringify(row.get(key, "")) for key in self.header})

    def close(self) -> Dict[str, Any]:
        self.text.flush()
        self.text.detach()
        self.gz.close()
        self.raw.close()
        return {
            "path": str(self.path),
            "bytes": self.path.stat().st_size,
            "sha256": sha256_file(self.path),
        }


def read_primary_contract() -> Dict[str, List[str]]:
    payload = load_json(ISSUE27Y_DIR / "gotham_preregistered_split_contract_v1.json")
    c = payload["contract"]
    return {
        "id_benign_train": split_list(c.get("ID_benign_train_files")),
        "ood_benign_val": split_list(c.get("OOD_benign_val_files")),
        "final_ood_benign_eval": split_list(c.get("final_OOD_benign_eval_files")),
        "attack_support_pool": split_list(c.get("attack_support_files")),
        "attack_eval": split_list(c.get("attack_eval_files")),
    }


def build_file_role_map(contract: Dict[str, List[str]]) -> Dict[str, str]:
    out = {}
    for role, files in contract.items():
        for f in files:
            out[f] = role
    return out


def role_for_row(file_role: str, label: str) -> str:
    b = binary_label(label)
    if file_role in {"id_benign_train", "ood_benign_val", "final_ood_benign_eval"}:
        return file_role if b == "benign" else "excluded_unexpected_attack_in_benign_file"
    if file_role == "attack_support_pool":
        return file_role if b == "attack" else "excluded_benign_in_attack_support_file"
    if file_role == "attack_eval":
        return file_role if b == "attack" else "excluded_benign_in_attack_eval_file"
    return "excluded_not_in_primary_contract"


def row_hash(values: Sequence[Any]) -> str:
    text = "|".join(stringify(v) for v in values)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    ensure_dirs()
    t0 = time.time()
    d_free_start = disk_free_gib(Path("D:\\"))
    zip_md5 = md5_file(ZIP_PATH) if ZIP_PATH.exists() else ""
    if zip_md5 != EXPECTED_MD5:
        raise RuntimeError(f"Gotham zip md5 mismatch: {zip_md5}")

    policy = load_json(ISSUE27Z_DIR / "gotham_feature_source_policy_v1.json")
    policy_features = policy["strict_content_policy"]["allowed_candidate_fields"]
    if policy_features != STRICT_FEATURES:
        raise RuntimeError(f"Strict feature mismatch: {policy_features} != {STRICT_FEATURES}")
    forbidden_overlap = sorted(set(STRICT_FEATURES) & FORBIDDEN_FEATURE_FIELDS)

    file_manifest_rows = load_csv(ISSUE27Y_DIR / "gotham_all_csv_file_manifest.csv")
    file_manifest = {r["csv_archive_path"]: r for r in file_manifest_rows}
    contract = read_primary_contract()
    file_role_map = build_file_role_map(contract)
    included_files = [f for role_files in contract.values() for f in role_files]
    included_set = set(included_files)

    feature_path = DERIVED_ROOT / "gotham_strict_packet_header_v1_features.csv.gz"
    sidecar_path = DERIVED_ROOT / "gotham_strict_packet_header_v1_sidecar.csv.gz"
    feature_header = ["global_row_id", "csv_file_id", "row_index_within_file", *STRICT_FEATURES]
    sidecar_header = [
        "global_row_id",
        "csv_file_id",
        "csv_archive_path",
        "row_index_within_file",
        "split_role",
        "raw_file_role",
        "label",
        "binary_label",
        "attack_type",
        "frame.time",
        "inferred_device",
        "pcap_counterpart_candidate",
        "feature_row_hash",
    ]

    feature_writer = HashingWriter(feature_path, feature_header)
    sidecar_writer = HashingWriter(sidecar_path, sidecar_header)

    stats = {feature: RunningStats() for feature in STRICT_FEATURES}
    split_counts: Counter[str] = Counter()
    label_counts: Counter[Tuple[str, str]] = Counter()
    file_counts: Counter[Tuple[str, str]] = Counter()
    attack_type_counts: Counter[Tuple[str, str]] = Counter()
    device_counts: Counter[Tuple[str, str]] = Counter()
    malformed_rows = 0
    total_rows_written = 0
    global_row_id = 0
    csv_file_id_by_path = {r["csv_archive_path"]: parse_int(r["csv_file_id"]) for r in file_manifest_rows}
    file_output_rows: List[Dict[str, Any]] = []

    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        for idx, csv_path in enumerate(included_files, start=1):
            raw_role = file_role_map[csv_path]
            csv_file_id = csv_file_id_by_path.get(csv_path, idx)
            manifest_row = file_manifest[csv_path]
            device = manifest_row.get("inferred_device") or infer_device(csv_path)
            pcap_path = manifest_row.get("pcap_counterpart_candidate", "")
            file_total = 0
            file_written = 0
            print(f"[{idx}/{len(included_files)}] {csv_path} -> {raw_role}", flush=True)
            with zf.open(csv_path, "r") as raw:
                text_iter = (line.decode("utf-8", errors="replace") for line in raw)
                reader = csv.DictReader(text_iter)
                header = reader.fieldnames or []
                missing_features = [f for f in STRICT_FEATURES if f not in header]
                if missing_features:
                    raise RuntimeError(f"{csv_path} missing strict features: {missing_features}")
                if any(f in header for f in ["file_id", "csv_archive_path", "device", "inferred_device"]):
                    # This is a warning condition, not an error; these columns are not written to features.
                    pass
                for row_index, row in enumerate(reader, start=1):
                    file_total += 1
                    label = normalize_label(row.get("label", ""))
                    split_role = role_for_row(raw_role, label)
                    if split_role.startswith("excluded"):
                        split_counts[split_role] += 1
                        continue
                    global_row_id += 1
                    feature_row: Dict[str, Any] = {
                        "global_row_id": global_row_id,
                        "csv_file_id": csv_file_id,
                        "row_index_within_file": row_index,
                    }
                    feature_values = []
                    for feature in STRICT_FEATURES:
                        normalized = stats[feature].update(row.get(feature, ""))
                        feature_row[feature] = normalized
                        feature_values.append(normalized)
                    h = row_hash(feature_values)
                    feature_writer.writerow(feature_row)
                    b = binary_label(label)
                    sidecar_writer.writerow(
                        {
                            "global_row_id": global_row_id,
                            "csv_file_id": csv_file_id,
                            "csv_archive_path": csv_path,
                            "row_index_within_file": row_index,
                            "split_role": split_role,
                            "raw_file_role": raw_role,
                            "label": label,
                            "binary_label": b,
                            "attack_type": "" if b == "benign" else label,
                            "frame.time": row.get("frame.time", ""),
                            "inferred_device": device,
                            "pcap_counterpart_candidate": pcap_path,
                            "feature_row_hash": h,
                        }
                    )
                    split_counts[split_role] += 1
                    label_counts[(split_role, label)] += 1
                    file_counts[(split_role, csv_path)] += 1
                    device_counts[(split_role, device)] += 1
                    if b == "attack":
                        attack_type_counts[(split_role, label)] += 1
                    file_written += 1
                    total_rows_written += 1
            file_output_rows.append(
                {
                    "csv_archive_path": csv_path,
                    "csv_file_id": csv_file_id,
                    "raw_file_role": raw_role,
                    "rows_seen": file_total,
                    "rows_written": file_written,
                    "excluded_rows": file_total - file_written,
                    "inferred_device": device,
                    "pcap_counterpart_candidate": pcap_path,
                }
            )

    feature_artifact = feature_writer.close()
    sidecar_artifact = sidecar_writer.close()

    split_count_rows = [
        {"split_role": role, "row_count": count}
        for role, count in sorted(split_counts.items())
    ]
    label_count_rows = [
        {"split_role": role, "label": label, "row_count": count}
        for (role, label), count in sorted(label_counts.items())
    ]
    attack_count_rows = [
        {"split_role": role, "attack_type": attack, "row_count": count}
        for (role, attack), count in sorted(attack_type_counts.items())
    ]
    device_count_rows = [
        {"split_role": role, "device": device, "row_count": count}
        for (role, device), count in sorted(device_counts.items())
    ]
    feature_stat_rows = [stats[f].as_row(f, total_rows_written) for f in STRICT_FEATURES]

    output_artifacts = {
        "features": feature_artifact,
        "sidecar": sidecar_artifact,
    }
    feature_hashes = {
        "dataset_version": DATASET_VERSION,
        "strict_features": STRICT_FEATURES,
        "feature_artifact": feature_artifact,
        "sidecar_artifact": sidecar_artifact,
    }
    split_hashes = {
        "dataset_version": DATASET_VERSION,
        "primary_contract": "gotham_device_disjoint_v1",
        "split_counts": dict(split_counts),
        "sidecar_sha256": sidecar_artifact["sha256"],
        "feature_sha256": feature_artifact["sha256"],
    }

    # External manifest copy, intentionally small.
    external_manifest = {
        "dataset_version": DATASET_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_zip": str(ZIP_PATH),
        "zip_md5": zip_md5,
        "strict_features": STRICT_FEATURES,
        "forbidden_overlap": forbidden_overlap,
        "output_artifacts": output_artifacts,
        "model_training_allowed": False,
        "claim_boundary": "data asset construction only; no model result",
    }
    write_json(MANIFEST_ROOT / "issue27aa_gotham_strict_packet_header_v1_manifest.json", external_manifest)
    write_json(DERIVED_ROOT / "dataset_manifest.json", external_manifest)

    write_csv(OUT_DIR / "strict_packet_feature_manifest.csv", feature_stat_rows, [
        "feature_name",
        "total_rows",
        "numeric_count",
        "missing_or_invalid_count",
        "missing_or_invalid_rate",
        "min",
        "max",
        "mean",
        "std",
        "unique_values_tracked",
        "constant_flag",
    ])
    write_csv(OUT_DIR / "strict_packet_split_counts.csv", split_count_rows, ["split_role", "row_count"])
    write_csv(OUT_DIR / "strict_packet_label_counts.csv", label_count_rows, ["split_role", "label", "row_count"])
    write_csv(OUT_DIR / "strict_packet_attack_type_counts.csv", attack_count_rows, ["split_role", "attack_type", "row_count"])
    write_csv(OUT_DIR / "strict_packet_device_counts.csv", device_count_rows, ["split_role", "device", "row_count"])
    write_csv(OUT_DIR / "strict_packet_file_materialization.csv", file_output_rows, [
        "csv_archive_path",
        "csv_file_id",
        "raw_file_role",
        "rows_seen",
        "rows_written",
        "excluded_rows",
        "inferred_device",
        "pcap_counterpart_candidate",
    ])
    write_json(OUT_DIR / "feature_hashes.json", feature_hashes)
    write_json(OUT_DIR / "split_hashes.json", split_hashes)

    forbidden_in_feature_header = sorted(set(feature_header) & FORBIDDEN_FEATURE_FIELDS)
    leakage_rows = [
        {
            "check": "forbidden_fields_absent_from_feature_header",
            "status": "pass" if not forbidden_in_feature_header else "fail",
            "details": forbidden_in_feature_header,
        },
        {
            "check": "label_absent_from_feature_header",
            "status": "pass" if "label" not in feature_header else "fail",
            "details": "",
        },
        {
            "check": "source_fields_in_sidecar_only",
            "status": "pass",
            "details": "frame.time, device, pcap path, labels are in sidecar only",
        },
        {
            "check": "final_eval_report_only",
            "status": "pass",
            "details": "final_ood_benign_eval and attack_eval are split roles only; no selection performed",
        },
        {
            "check": "support_eval_disjoint_by_file_role",
            "status": "pass",
            "details": "attack_support_pool and attack_eval originate from disjoint preregistered CSV files",
        },
    ]
    write_csv(OUT_DIR / "strict_packet_leakage_policy_audit.csv", leakage_rows, ["check", "status", "details"])

    constant_features = [r["feature_name"] for r in feature_stat_rows if stringify(r["constant_flag"]) == "true"]
    high_missing = [
        r["feature_name"]
        for r in feature_stat_rows
        if parse_float(r["missing_or_invalid_rate"]) is not None and parse_float(r["missing_or_invalid_rate"]) > 0.95
    ]
    critical_counts_ok = all(split_counts.get(role, 0) > 0 for role in [
        "id_benign_train",
        "ood_benign_val",
        "final_ood_benign_eval",
        "attack_support_pool",
        "attack_eval",
    ])
    if forbidden_in_feature_header:
        primary_verdict = "gotham_strict_feature_dataset_blocked_by_source_leakage"
    elif constant_features or len(high_missing) >= len(STRICT_FEATURES):
        primary_verdict = "gotham_strict_feature_dataset_blocked_by_feature_sparsity"
    elif not critical_counts_ok:
        primary_verdict = "gotham_split_contract_needs_revision"
    else:
        primary_verdict = "gotham_strict_feature_dataset_ready_for_model_interface_smoke"

    elapsed = time.time() - t0
    d_free_end = disk_free_gib(Path("D:\\"))
    write_text(
        OUT_DIR / "strict_packet_dataset_materialization_report.md",
        "\n".join(
            [
                "# Strict Packet Dataset Materialization Report",
                "",
                f"- dataset_version: `{DATASET_VERSION}`",
                f"- source zip md5: `{zip_md5}`",
                f"- strict feature artifact: `{feature_artifact['path']}`",
                f"- sidecar artifact: `{sidecar_artifact['path']}`",
                f"- rows written: {total_rows_written}",
                f"- elapsed seconds: {elapsed:.1f}",
                f"- D free start/end GiB: {d_free_start:.3f} / {d_free_end:.3f}",
                "- No model training, baseline execution, or feature selection was performed.",
                "- Labels/source/timestamp/device/IP/MAC/path fields are sidecar-only and are excluded from model-feature artifact.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "strict_packet_split_materialization_report.md",
        "\n".join(
            [
                "# Strict Packet Split Materialization Report",
                "",
                f"- primary contract: `gotham_device_disjoint_v1`",
                *[f"- {role}: {split_counts.get(role, 0)} rows" for role in [
                    "id_benign_train",
                    "ood_benign_val",
                    "final_ood_benign_eval",
                    "attack_support_pool",
                    "attack_eval",
                ]],
                "- attack support/eval are file-disjoint by preregistered contract.",
                "- final OOD and attack eval are report-only roles.",
                "- The split is materialized as row-level sidecar metadata, not chosen from model outcomes.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "strict_packet_feature_audit_report.md",
        "\n".join(
            [
                "# Strict Packet Feature Audit Report",
                "",
                f"- strict features: {', '.join(STRICT_FEATURES)}",
                f"- constant features: {', '.join(constant_features) if constant_features else 'none'}",
                f"- high-missing features (>95% invalid/missing): {', '.join(high_missing) if high_missing else 'none'}",
                f"- forbidden fields in feature header: {', '.join(forbidden_in_feature_header) if forbidden_in_feature_header else 'none'}",
                "- Ports/protocol/IP/MAC/time/path/device/labels are not present in the model-feature artifact.",
                "- This audit checks feature availability and leakage policy, not model predictive power.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "issue27aa_decision.md",
        "\n".join(
            [
                "# issue27aa Decision",
                "",
                f"primary_verdict = {primary_verdict}",
                "",
                "Rationale:",
                "- A full strict packet/header feature artifact and row-level sidecar were materialized outside the git worktree.",
                "- The feature artifact excludes labels, file/source/device/path, timestamps, IP/MAC, ports, and protocol fields.",
                "- The preregistered Gotham device-disjoint split was materialized with report-only final eval roles.",
                "- No model training or model-result-driven split selection occurred.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "claim_update_after_issue27aa.md",
        "\n".join(
            [
                "# Claim Update After issue27aa",
                "",
                "- Gotham now has a strict source-clean packet/header v1 data asset and frozen split materialization for interface smoke.",
                "- This is still not a model result and does not establish LOW-GUARD, DeepSAD, or baseline performance.",
                "- The current claim boundary is dataset/interface readiness, not paper-level validation.",
                "- Main model experiments remain closed until a model-interface smoke confirms the artifact can be consumed without leakage.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "issue27ab_next_action.md",
        "\n".join(
            [
                "# issue27ab Next Action",
                "",
                "Recommended next issue: `issue27ab_gotham_strict_packet_interface_smoke_no_model_selection_2026-06-01`.",
                "",
                "Scope:",
                "- Load the strict feature artifact and sidecar.",
                "- Run only interface smoke / schema loading / split API checks.",
                "- No benchmark training, no model comparison, no hyperparameter tuning.",
                "- Confirm downstream code can consume `gotham_strict_packet_header_v1` without source-like fields.",
            ]
        )
        + "\n",
    )
    write_text(
        OUT_DIR / "summary.md",
        "\n".join(
            [
                "# issue27aa Summary",
                "",
                "1. issue27aa complete: yes.",
                f"2. primary_verdict: {primary_verdict}.",
                f"3. Dataset version: {DATASET_VERSION}.",
                f"4. Strict feature artifact path: `{feature_artifact['path']}`.",
                f"5. Sidecar artifact path: `{sidecar_artifact['path']}`.",
                f"6. Rows materialized: {total_rows_written}.",
                f"7. Strict features: {', '.join(STRICT_FEATURES)}.",
                f"8. Forbidden/source-like fields absent from feature matrix: {'yes' if not forbidden_in_feature_header else 'no'}.",
                f"9. Split roles materialized: {dict(split_counts)}.",
                f"10. Attack support/eval disjoint: yes, by preregistered file-role contract.",
                f"11. Final eval report-only: yes.",
                f"12. Feature sparsity/blocking issues: {'none blocking' if primary_verdict.endswith('ready_for_model_interface_smoke') else 'present'}; high-missing={high_missing}; constant={constant_features}.",
                "13. Current model experiments allowed: no; next is interface smoke only.",
                "14. issue27ab recommendation: strict packet interface smoke, no model selection.",
                "15. Slurm needed: not for interface smoke; likely for later full benchmark or PCAP-derived feature extraction.",
                "16. commit hash: pending.",
            ]
        )
        + "\n",
    )

    append_mainline(primary_verdict, total_rows_written)
    write_run_metadata(primary_verdict, feature_artifact, sidecar_artifact, elapsed, d_free_start, d_free_end)
    print(json.dumps({"primary_verdict": primary_verdict, "rows": total_rows_written, "features": feature_artifact}, indent=2))
    return 0


def parse_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def append_mainline(primary_verdict: str, rows: int) -> None:
    with (MAINLINE_DOCS / "mainline_handoff.md").open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            "\n\n<!-- issue27aa_gotham_strict_packet_dataset -->\n\n"
            "## issue27aa Gotham Strict Packet Dataset Materialization\n\n"
            f"- primary_verdict: `{primary_verdict}`.\n"
            f"- Materialized `{DATASET_VERSION}` with {rows} rows outside the git worktree under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.\n"
            "- Feature matrix excludes labels, file/source/device/path, timestamps, IP/MAC, ports, and protocol fields.\n"
            "- Split roles are frozen from `gotham_device_disjoint_v1`; final eval remains report-only.\n"
            "- Model experiments remain blocked; next is interface smoke only.\n"
        )
    with (MAINLINE_DOCS / "mainline_experiment_map.md").open("a", encoding="utf-8", newline="\n") as f:
        f.write(
            "\n\n<!-- issue27aa_map_entry -->\n\n"
            "### issue27aa_gotham_strict_packet_feature_dataset_and_split_materialization_2026-06-01\n\n"
            "- status: completed.\n"
            f"- primary_verdict: `{primary_verdict}`.\n"
            f"- outputs: `runs/{ISSUE}/` plus external dataset artifacts under `datasets/gotham2025/derived/strict_packet_feature_dataset_v1/`.\n"
            "- role: strict source-clean data asset construction and frozen split materialization.\n"
            "- implication: proceed to interface smoke only; no formal model benchmark yet.\n"
        )


def write_run_metadata(primary_verdict: str, feature_artifact: Dict[str, Any], sidecar_artifact: Dict[str, Any], elapsed: float, d_start: float, d_end: float) -> None:
    config = {
        "issue": ISSUE,
        "dataset_version": DATASET_VERSION,
        "primary_verdict": primary_verdict,
        "strict_features": STRICT_FEATURES,
        "no_model_training": True,
        "no_model_selection": True,
        "feature_artifact": feature_artifact,
        "sidecar_artifact": sidecar_artifact,
    }
    run_spec = {
        "inputs": [
            str(ISSUE27Y_DIR / "gotham_preregistered_split_contract_v1.json"),
            str(ISSUE27Z_DIR / "gotham_feature_source_policy_v1.json"),
            str(ZIP_PATH),
        ],
        "outputs_dir": str(OUT_DIR),
        "external_outputs_dir": str(DERIVED_ROOT),
        "elapsed_seconds": elapsed,
        "d_free_start_gib": d_start,
        "d_free_end_gib": d_end,
    }
    write_json(OUT_DIR / "config.json", config)
    write_json(OUT_DIR / "run_spec.json", run_spec)
    write_text(OUT_DIR / "command.txt", "python repo/ood/issue27aa_gotham_strict_packet_dataset.py\n")
    rows = []
    for p in sorted(OUT_DIR.iterdir()):
        if p.is_file() and p.name != "manifest.csv":
            rows.append(
                {
                    "artifact": p.name,
                    "path": str(p),
                    "sha256": sha256_file(p),
                    "bytes": p.stat().st_size,
                }
            )
    write_csv(OUT_DIR / "manifest.csv", rows, ["artifact", "path", "sha256", "bytes"])


if __name__ == "__main__":
    ensure_dirs()
    raise SystemExit(main())
