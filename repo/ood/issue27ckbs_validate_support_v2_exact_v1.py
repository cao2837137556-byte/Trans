from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import dpkt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
CKBR = ROOT / "runs" / "issue27ckbr_support_v2_mechanism_contract_v1_2026-07-22"
OUT = ROOT / "runs" / "issue27ckbs_support_v2_exact_materialization_v1_2026-07-22"
PLAN = CKBR / "support_v2_raw_extension_plan.csv"
X_PATH = OUT / "quarantined_support_v2_candidate_X.npy"
Y_PATH = OUT / "quarantined_support_v2_candidate_y.npy"
SIDECAR = OUT / "quarantined_support_v2_candidate_sidecar.csv"
MATERIALIZATION = OUT / "support_v2_materialization_contract.json"
TARGETED_PLAN = (
    ROOT
    / "runs"
    / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
    / "targeted_exact_label_materialization_plan.csv"
)
RAW_ZIP = ROOT.parents[1] / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"
SUPPORT_TRAIN_V1 = (
    ROOT
    / "runs"
    / "issue27ckg_label_support_region_registry_and_versioned_update_protocol_2026-06-22"
    / "support_train_view_v1.csv"
)
SUPPORT_VAL_V1 = SUPPORT_TRAIN_V1.with_name("support_val_view_v1.csv")

EXPECTED_PLAN_SHA256 = "2807447b5aad1fa7c86d7246e4759d77cc61f0f57c3cf0910fa642c2493bac10"
EXPECTED_X_CONTRACT_SHA256 = "d352881c6bc86089ec07eb86dfb271547297d966b93c130b1c0bc23eaf15d586"
EXPECTED_SIDECAR_SHA256 = "01adf4e97b8205974019cddef89b25c7f61ae47d7a3757b542ba408366b7a08f"
EXPECTED_TRAIN_V1_SHA256 = "6440c9ba57412149008277c0c6ab2fb9d853a3be8d77b19812b20bed59c3ed99"
EXPECTED_VAL_V1_SHA256 = "e9ac02ff6d3393613e67c43b7612784d6088afa9dec4eca6ab297c0a1dc427d5"
SOURCE = "processed/iotsim-city-power-1.csv"
PCAP = (
    "raw/malicious/mirai-infection/"
    "iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap"
)
LABELS = {"TCP Scan", "Telnet Brute Force"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def array_digest(array: np.ndarray) -> str:
    h = hashlib.sha256()
    h.update(str(array.dtype).encode("ascii"))
    h.update(str(tuple(array.shape)).encode("ascii"))
    h.update(np.ascontiguousarray(array).tobytes())
    return h.hexdigest()


def rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_manifest(paths: list[Path]) -> None:
    with (OUT / "manifest.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["artifact", "path", "sha256", "bytes"])
        writer.writeheader()
        for path in sorted(paths, key=lambda item: item.name):
            writer.writerow(
                {
                    "artifact": path.name,
                    "path": str(path.relative_to(ROOT)),
                    "sha256": sha256(path),
                    "bytes": path.stat().st_size,
                }
            )


def frame_time_epoch(value: str) -> float:
    text = value.strip().removesuffix(" GMT")
    prefix, fraction = text.rsplit(".", 1)
    digits = "".join(char for char in fraction if char.isdigit())
    parsed = datetime.strptime(
        f"{prefix}.{(digits + '000000')[:6]}", "%b %d, %Y %H:%M:%S.%f"
    )
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def as_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"invalid boolean: {value!r}")
    return normalized == "true"


def main() -> None:
    for path in (
        PLAN,
        X_PATH,
        Y_PATH,
        SIDECAR,
        MATERIALIZATION,
        TARGETED_PLAN,
        RAW_ZIP,
        SUPPORT_TRAIN_V1,
        SUPPORT_VAL_V1,
    ):
        if not path.is_file():
            raise FileNotFoundError(path)

    checks: dict[str, bool] = {}
    checks["plan_hash_frozen"] = sha256(PLAN) == EXPECTED_PLAN_SHA256
    checks["support_train_v1_hash_frozen"] = sha256(SUPPORT_TRAIN_V1) == EXPECTED_TRAIN_V1_SHA256
    checks["support_val_v1_hash_frozen"] = sha256(SUPPORT_VAL_V1) == EXPECTED_VAL_V1_SHA256
    checks["sidecar_hash_frozen"] = sha256(SIDECAR) == EXPECTED_SIDECAR_SHA256

    plan = rows(PLAN)
    sidecar = rows(SIDECAR)
    x = np.load(X_PATH, allow_pickle=False)
    y = np.load(Y_PATH, allow_pickle=False)
    checks["matrix_shape_dtype_finite"] = (
        x.shape == (160, 115) and x.dtype == np.float32 and bool(np.isfinite(x).all())
    )
    checks["label_array_shape_value"] = y.shape == (160,) and y.dtype == np.int8 and bool(np.all(y == 1))
    checks["x_contract_hash_frozen"] = array_digest(x) == EXPECTED_X_CONTRACT_SHA256
    checks["plan_sidecar_cardinality"] = len(plan) == len(sidecar) == 160
    checks["row_order_and_identity"] = all(
        plan[index]["extension_row_id"] == row["extension_row_id"]
        and int(row["feature_row_index"]) == index
        for index, row in enumerate(sidecar)
    )
    checks["row_vector_hashes"] = all(
        hashlib.sha256(np.ascontiguousarray(x[index], dtype=np.float32).tobytes()).hexdigest()
        == row["feature_vector_sha256"]
        for index, row in enumerate(sidecar)
    )
    checks["source_and_pcap_exact"] = (
        {row["source_csv"] for row in sidecar} == {SOURCE}
        and {row["pcap_member"] for row in sidecar} == {PCAP}
    )
    checks["labels_exact"] = {row["exact_attack_label"] for row in sidecar} == LABELS
    checks["no_report_or_sealed"] = all(
        not as_bool(row["report_only"]) and not as_bool(row["sealed_final"])
        for row in sidecar
    )
    checks["all_materialized_rows_fail_closed"] = all(
        not as_bool(row["selection_allowed"])
        and as_bool(row["forbidden_for_fit"])
        and as_bool(row["forbidden_for_threshold"])
        and as_bool(row["forbidden_for_model_selection"])
        and not as_bool(row["temporal_admissibility"])
        and as_bool(row["same_capture_candidate_after_frozen_query"])
        for row in sidecar
    )
    checks["raw_labels_support_only"] = all(
        as_bool(row["raw_label_column_read"])
        and row["raw_label_use"] == "offline_exact_support_materialization_only"
        for row in sidecar
    )
    partition = Counter((row["exact_attack_label"], row["bank_partition"]) for row in sidecar)
    checks["partition_counts"] = all(
        partition[(label, "support_train")] == 60
        and partition[(label, "support_val")] == 20
        for label in LABELS
    )
    phase = Counter((row["exact_attack_label"], row["support_val_phase"]) for row in sidecar)
    checks["support_val_lineage_counts"] = all(
        phase[(label, "fit")] == 10 and phase[(label, "select")] == 10
        for label in LABELS
    )

    csv_targets = {int(row["csv_row_index"]): row for row in sidecar}
    pcap_targets = {int(row["pcap_packet_index"]): row for row in sidecar}
    raw_csv_matches = 0
    raw_pcap_matches = 0
    with zipfile.ZipFile(RAW_ZIP) as zf:
        with zf.open(SOURCE) as raw:
            reader = csv.DictReader(line.decode("utf-8", errors="replace") for line in raw)
            for csv_index, raw_row in enumerate(reader):
                if csv_index in csv_targets:
                    target = csv_targets[csv_index]
                    if raw_row.get("label", "") != target["exact_attack_label"]:
                        raise RuntimeError(f"raw CSV label mismatch at {csv_index}")
                    delta = abs(frame_time_epoch(raw_row["frame.time"]) - float(target["csv_timestamp_epoch"]))
                    if delta > 1e-9:
                        raise RuntimeError(f"raw CSV timestamp mismatch at {csv_index}: {delta}")
                    raw_csv_matches += 1
                if csv_index > max(csv_targets):
                    break
        with zf.open(PCAP) as raw:
            reader = dpkt.pcap.Reader(io.BufferedReader(raw))
            for packet_index, (timestamp, _packet) in enumerate(reader):
                if packet_index in pcap_targets:
                    target = pcap_targets[packet_index]
                    delta_us = abs(float(timestamp) - float(target["csv_timestamp_epoch"])) * 1_000_000.0
                    if delta_us > 2.000001:
                        raise RuntimeError(f"PCAP timestamp mismatch at {packet_index}: {delta_us} us")
                    if abs(float(target["timestamp_delta_us"]) - delta_us) > 1e-6:
                        raise RuntimeError(f"recorded PCAP delta mismatch at {packet_index}")
                    raw_pcap_matches += 1
                if packet_index > max(pcap_targets):
                    break
    checks["raw_csv_exact_160"] = raw_csv_matches == 160
    checks["raw_pcap_exact_160"] = raw_pcap_matches == 160

    query: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows(TARGETED_PLAN):
        if row["csv_member"] == SOURCE and row["attack_type"] in LABELS:
            query[row["attack_type"]].append(
                (int(row["planned_start_row"]), int(row["planned_end_row"]))
            )
    checks["query_zero_overlap_and_500_row_embargo"] = all(
        all(
            int(row["csv_row_index"]) < lo - 500 or int(row["csv_row_index"]) > hi + 500
            for lo, hi in query[row["exact_attack_label"]]
        )
        for row in sidecar
    )
    query_index_to_label = {
        index: label
        for label, intervals in query.items()
        for lo, hi in intervals
        for index in range(lo, hi + 1)
    }
    query_epochs: dict[str, list[float]] = defaultdict(list)
    with zipfile.ZipFile(RAW_ZIP) as zf, zf.open(SOURCE) as raw:
        reader = csv.DictReader(line.decode("utf-8", errors="replace") for line in raw)
        for csv_index, raw_row in enumerate(reader):
            if csv_index > max(query_index_to_label):
                break
            label = query_index_to_label.get(csv_index)
            if label is None:
                continue
            if raw_row.get("label", "") != label:
                raise RuntimeError(f"frozen query raw label mismatch at {csv_index}")
            query_epochs[label].append(frame_time_epoch(raw_row["frame.time"]))
    checks["same_capture_candidate_after_query_verified"] = all(
        len(query_epochs[label]) == 12_000
        and min(
            float(row["csv_timestamp_epoch"])
            for row in sidecar
            if row["exact_attack_label"] == label
        )
        > max(query_epochs[label])
        for label in LABELS
    )

    materialization = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    checks["materialization_contract_complete_but_quarantined"] = (
        materialization.get("status")
        == "SUPPORT_V2_DIAGNOSTIC_MATERIALIZATION_QUARANTINED_FUTURE_ORDER"
        and materialization.get("planned_rows") == materialization.get("emitted_rows") == 160
        and materialization.get("missing_rows") == 0
        and materialization.get("timestamp_ambiguities") == 0
        and materialization.get("report_rows") == materialization.get("sealed_rows") == 0
        and materialization.get("active_support_rows") == 0
        and materialization.get("selection_allowed_rows") == 0
        and materialization.get("forbidden_for_fit_rows") == 160
        and materialization.get("temporal_admissible_rows") == 0
        and materialization.get("plan_sha256") == EXPECTED_PLAN_SHA256
        and materialization.get("sidecar_sha256") == sha256(SIDECAR)
    )

    frontend_files = [
        ROOT / "repo" / "ood" / "issue27ab_gotham_kitsune115_frontend_feasibility.py",
        ROOT / "repo" / "kitsune_frontend_original" / "AfterImage.py",
        ROOT / "repo" / "kitsune_frontend_original" / "netStat.py",
        ROOT / "repo" / "kitsune_frontend_original" / "SOURCE.md",
    ]
    frontend_hashes = {str(path.relative_to(ROOT)): sha256(path) for path in frontend_files}
    failures = sorted(name for name, passed in checks.items() if not passed)
    result: dict[str, Any] = {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "frontend_source_hashes": frontend_hashes,
        "plan_sha256": sha256(PLAN),
        "x_contract_sha256": array_digest(x),
        "y_contract_sha256": array_digest(y),
        "sidecar_sha256": sha256(SIDECAR),
        "scientific_scope": "diagnostic_materialization_quarantine_not_model_performance",
    }
    (OUT / "independent_materialization_validation.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_manifest(
        [
            path
            for path in OUT.iterdir()
            if path.is_file() and path.name not in {"manifest.csv"}
        ]
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
