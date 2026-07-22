from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import pickle
import sys
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any

import dpkt
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OOD_DIR = ROOT / "repo" / "ood"
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ab_gotham_kitsune115_frontend_feasibility as ab  # noqa: E402


ISSUE = "issue27ckbs_support_v2_exact_materialization_v1_2026-07-22"
OUT = ROOT / "runs" / ISSUE
CKBR = ROOT / "runs" / "issue27ckbr_support_v2_mechanism_contract_v1_2026-07-22"
PLAN = CKBR / "support_v2_raw_extension_plan.csv"
PLAN_VALIDATION = CKBR / "independent_contract_validation.json"
RAW_ZIP = ROOT.parents[1] / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"
STATE_DIR = (
    ROOT.parents[1]
    / "datasets"
    / "gotham2025"
    / "derived"
    / "kitsune115_1m_slurm_cache_pipeline_v1"
    / "state"
)
TRAIN_STATE = STATE_DIR / "train_state_after_id_train.pkl"
TRAIN_STATE_META = STATE_DIR / "train_state_after_id_train_meta.json"

EXPECTED_PLAN_SHA256 = "2807447b5aad1fa7c86d7246e4759d77cc61f0f57c3cf0910fa642c2493bac10"
EXPECTED_PCAP = (
    "raw/malicious/mirai-infection/"
    "iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap"
)
SOURCE_CSV = "processed/iotsim-city-power-1.csv"
TIME_TOLERANCE_US = 2


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


def row_digest(vector: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(vector, dtype=np.float32).tobytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def timestamp_key(epoch: float) -> int:
    return int(round(float(epoch) * 1_000_000.0))


def as_bool(value: Any) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"invalid boolean value: {value!r}")
    return normalized == "true"


def validate_quarantined_plan(plan: list[dict[str, str]]) -> None:
    if len(plan) != 160:
        raise RuntimeError(f"expected 160 diagnostic rows, got {len(plan)}")
    if {row["source_csv"] for row in plan} != {SOURCE_CSV}:
        raise RuntimeError("diagnostic candidate source drift")
    if {row["preferred_pcap_member"] for row in plan} != {EXPECTED_PCAP}:
        raise RuntimeError("diagnostic candidate PCAP drift")
    if any(
        as_bool(row["selection_allowed"])
        or not as_bool(row["forbidden_for_fit"])
        or not as_bool(row["forbidden_for_threshold"])
        or not as_bool(row["forbidden_for_model_selection"])
        or as_bool(row["temporal_admissibility"])
        or not as_bool(row["same_capture_candidate_after_frozen_query"])
        for row in plan
    ):
        raise RuntimeError("CKBR diagnostic candidate is not fail-closed")


def finalized_sidecar(
    plan: list[dict[str, str]], sidecar: list[dict[str, str]], x: np.ndarray
) -> list[dict[str, Any]]:
    plan_by_id = {row["extension_row_id"]: row for row in plan}
    if len(plan_by_id) != 160 or len(sidecar) != 160:
        raise RuntimeError("plan/sidecar row-count contract changed")
    output: list[dict[str, Any]] = []
    for row_index, old in enumerate(sidecar):
        plan_row = plan_by_id.get(old["extension_row_id"])
        if plan_row is None:
            raise RuntimeError(f"sidecar row not present in plan: {old['extension_row_id']}")
        if int(old["feature_row_index"]) != row_index:
            raise RuntimeError("sidecar feature order changed")
        if old["feature_vector_sha256"] != row_digest(x[row_index]):
            raise RuntimeError(f"feature vector hash changed at row {row_index}")
        updated: dict[str, Any] = dict(old)
        updated.update(
            {
                "support_version": "support_v2_candidate_quarantined_materialized_v1",
                "source_contract_role": plan_row["source_contract_role"],
                "selection_allowed": False,
                "report_only": False,
                "sealed_final": False,
                "forbidden_for_fit": True,
                "forbidden_for_threshold": True,
                "forbidden_for_model_selection": True,
                "temporal_admissibility": False,
                "same_capture_candidate_after_frozen_query": True,
                "frozen_query_first_epoch": plan_row["frozen_query_first_epoch"],
                "frozen_query_last_epoch": plan_row["frozen_query_last_epoch"],
                "quarantine_reason": plan_row["quarantine_reason"],
            }
        )
        output.append(updated)
    return output


def write_quarantine_outputs(
    plan: list[dict[str, str]],
    sidecar: list[dict[str, Any]],
    x: np.ndarray,
    y: np.ndarray,
    materialization: dict[str, Any],
) -> dict[str, Any]:
    write_csv(OUT / "quarantined_support_v2_candidate_sidecar.csv", sidecar)
    write_csv(
        OUT / "quarantined_support_train_candidate_v2.csv",
        [row for row in sidecar if row["bank_partition"] == "support_train"],
    )
    write_csv(
        OUT / "quarantined_support_val_candidate_v2.csv",
        [row for row in sidecar if row["bank_partition"] == "support_val"],
    )
    materialization.update(
        {
            "status": "SUPPORT_V2_DIAGNOSTIC_MATERIALIZATION_QUARANTINED_FUTURE_ORDER",
            "model_training": False,
            "hpc_submission": False,
            "plan_sha256": sha256(PLAN),
            "candidate_rows": len(sidecar),
            "active_support_rows": 0,
            "selection_allowed_rows": 0,
            "forbidden_for_fit_rows": len(sidecar),
            "temporal_admissible_rows": 0,
            "same_capture_candidate_after_frozen_query_rows": len(sidecar),
            "x_contract_sha256": array_digest(x),
            "y_contract_sha256": array_digest(y),
            "sidecar_sha256": sha256(OUT / "quarantined_support_v2_candidate_sidecar.csv"),
        }
    )
    (OUT / "support_v2_materialization_contract.json").write_text(
        json.dumps(materialization, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "summary.md").write_text(
        "\n".join(
            [
                "# CKBS exact diagnostic materialization",
                "",
                "Status: `SUPPORT_V2_DIAGNOSTIC_MATERIALIZATION_QUARANTINED_FUTURE_ORDER`.",
                "",
                "- Reused the vendored mature Kitsune/AfterImage `RestoredNetStat115` frontend and frozen ID-train state.",
                "- Exactly materialized 160 labeled diagnostic rows; matrix shape is `[160, 115]`, with zero missing targets and zero timestamp ambiguity.",
                "- Every candidate is from the same capture after the already frozen TCP/Telnet future-query interval.",
                "- All 160 rows are forbidden for fit, select, standardization, thresholding, negative sampling, and model selection.",
                "- Active support remains train `385`, validation `127` (fit/select `58/69`). This is not a model-performance result.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return materialization


def finalize_existing_quarantine() -> None:
    required = [
        PLAN,
        PLAN_VALIDATION,
        OUT / "quarantined_support_v2_candidate_X.npy",
        OUT / "quarantined_support_v2_candidate_y.npy",
        OUT / "quarantined_support_v2_candidate_sidecar.csv",
        OUT / "support_v2_materialization_contract.json",
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    if sha256(PLAN) != EXPECTED_PLAN_SHA256:
        raise RuntimeError("CKBR quarantined plan hash changed")
    validation = json.loads(PLAN_VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or validation.get("plan_sha256") != EXPECTED_PLAN_SHA256:
        raise RuntimeError("CKBR quarantine validation is not a PASS for the frozen plan")
    plan = read_csv(PLAN)
    validate_quarantined_plan(plan)
    x = np.load(OUT / "quarantined_support_v2_candidate_X.npy", allow_pickle=False)
    y = np.load(OUT / "quarantined_support_v2_candidate_y.npy", allow_pickle=False)
    if x.shape != (160, 115) or y.shape != (160,) or not np.isfinite(x).all():
        raise RuntimeError("existing diagnostic arrays changed")
    sidecar = finalized_sidecar(
        plan, read_csv(OUT / "quarantined_support_v2_candidate_sidecar.csv"), x
    )
    materialization = json.loads(
        (OUT / "support_v2_materialization_contract.json").read_text(encoding="utf-8")
    )
    materialization.setdefault(
        "original_feature_materialization_status", materialization.get("status")
    )
    materialization["metadata_finalized_without_feature_recompute"] = True
    result = write_quarantine_outputs(plan, sidecar, x, y, materialization)
    print(json.dumps(result, indent=2, sort_keys=True))


def packet_fields(nstat: ab.RestoredNetStat115, ts: float, buf: bytes) -> tuple[np.ndarray | None, str | None]:
    fields, error = ab.parse_packet(ts, buf)
    if error is not None:
        return None, error
    try:
        vector = nstat.update_get_stats(
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
        return np.asarray(vector, dtype=np.float32), None
    except Exception as exc:  # fail-closed metadata is more useful than a partial cache
        return None, f"{type(exc).__name__}: {exc}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--finalize-existing-quarantine", action="store_true")
    args = parser.parse_args()
    if args.finalize_existing_quarantine:
        finalize_existing_quarantine()
        return

    started = time.monotonic()
    for path in (PLAN, PLAN_VALIDATION, RAW_ZIP, TRAIN_STATE, TRAIN_STATE_META):
        if not path.is_file():
            raise FileNotFoundError(path)
    if sha256(PLAN) != EXPECTED_PLAN_SHA256:
        raise RuntimeError("CKBR extension plan hash changed")
    validation = json.loads(PLAN_VALIDATION.read_text(encoding="utf-8"))
    if validation.get("status") != "PASS" or validation.get("plan_sha256") != EXPECTED_PLAN_SHA256:
        raise RuntimeError("CKBR independent validation is not a PASS for the frozen plan")

    plan = read_csv(PLAN)
    validate_quarantined_plan(plan)

    targets_by_key: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for order, row in enumerate(plan):
        target = dict(row)
        target["plan_order"] = order
        target["target_epoch"] = float(row["packet_timestamp_epoch"])
        target["matched"] = False
        targets_by_key[timestamp_key(target["target_epoch"])].append(target)

    with TRAIN_STATE.open("rb") as f:
        nstat: ab.RestoredNetStat115 = pickle.load(f)
    state_hash_before = ab.state_hash(nstat)
    state_meta = json.loads(TRAIN_STATE_META.read_text(encoding="utf-8"))

    matches: dict[str, tuple[np.ndarray, dict[str, Any]]] = {}
    parse_errors = 0
    packets_scanned = 0
    ambiguity_count = 0
    with zipfile.ZipFile(RAW_ZIP) as zf:
        if EXPECTED_PCAP not in zf.namelist():
            raise RuntimeError(f"PCAP missing from raw archive: {EXPECTED_PCAP}")
        pcap_info = zf.getinfo(EXPECTED_PCAP)
        with zf.open(EXPECTED_PCAP) as raw:
            reader = dpkt.pcap.Reader(io.BufferedReader(raw))
            for packet_index, (ts, buf) in enumerate(reader):
                packets_scanned += 1
                vector, error = packet_fields(nstat, float(ts), buf)
                if error is not None or vector is None:
                    parse_errors += 1
                    continue
                center = timestamp_key(float(ts))
                candidates: list[tuple[float, dict[str, Any]]] = []
                for key in range(center - TIME_TOLERANCE_US, center + TIME_TOLERANCE_US + 1):
                    for target in targets_by_key.get(key, []):
                        if target["matched"]:
                            continue
                        delta = abs(float(ts) - target["target_epoch"])
                        if delta <= TIME_TOLERANCE_US / 1_000_000.0 + 1e-12:
                            candidates.append((delta, target))
                if candidates:
                    candidates.sort(key=lambda pair: (pair[0], int(pair[1]["csv_row_index"])))
                    if len(candidates) > 1 and abs(candidates[0][0] - candidates[1][0]) < 1e-12:
                        ambiguity_count += 1
                    _, target = candidates[0]
                    target["matched"] = True
                    matches[target["extension_row_id"]] = (
                        vector,
                        {
                            "pcap_packet_index": packet_index,
                            "packet_timestamp_epoch": f"{float(ts):.6f}",
                            "timestamp_delta_us": abs(float(ts) - target["target_epoch"]) * 1_000_000.0,
                        },
                    )
                    if len(matches) == len(plan):
                        break

    missing = [row["extension_row_id"] for row in plan if row["extension_row_id"] not in matches]
    if missing:
        raise RuntimeError(f"exact PCAP timestamp alignment incomplete: {len(missing)} missing; first={missing[:5]}")
    if ambiguity_count:
        raise RuntimeError(f"ambiguous exact PCAP timestamp matches: {ambiguity_count}")

    ordered_vectors = [matches[row["extension_row_id"]][0] for row in plan]
    x = np.vstack(ordered_vectors).astype(np.float32)
    y = np.ones(len(plan), dtype=np.int8)
    if x.shape != (160, 115) or not np.isfinite(x).all():
        raise RuntimeError(f"invalid extension matrix: shape={x.shape}, finite={np.isfinite(x).all()}")

    sidecar: list[dict[str, Any]] = []
    for row_index, row in enumerate(plan):
        match = matches[row["extension_row_id"]][1]
        sidecar.append(
            {
                "feature_row_index": row_index,
                "extension_row_id": row["extension_row_id"],
                "support_version": "support_v2_candidate_quarantined_materialized_v1",
                "bank_partition": row["bank_partition"],
                "support_val_phase": row["support_val_phase"],
                "source_contract_role": row["source_contract_role"],
                "source_csv": row["source_csv"],
                "source_group": row["source_group"],
                "exact_attack_label": row["exact_attack_label"],
                "mechanism_family": row["mechanism_family"],
                "source_segment_id": row["source_segment_id"],
                "csv_row_index": row["csv_row_index"],
                "csv_timestamp_epoch": row["packet_timestamp_epoch"],
                "pcap_member": EXPECTED_PCAP,
                "pcap_packet_index": match["pcap_packet_index"],
                "packet_timestamp_epoch": match["packet_timestamp_epoch"],
                "timestamp_delta_us": f"{match['timestamp_delta_us']:.9f}",
                "timestamp_alignment_status": "within_2us_epoch_match",
                "feature_dim": 115,
                "feature_vector_sha256": row_digest(x[row_index]),
                "frontend": "vendored_mature_Kitsune_AfterImage_RestoredNetStat115",
                "state_strategy": "frozen_id_train_state_then_source_local_online_current_packet_inclusive",
                "raw_label_column_read": True,
                "raw_label_use": "offline_exact_support_materialization_only",
                "selection_allowed": False,
                "report_only": False,
                "sealed_final": False,
                "forbidden_for_fit": True,
                "forbidden_for_threshold": True,
                "forbidden_for_model_selection": True,
                "temporal_admissibility": False,
                "same_capture_candidate_after_frozen_query": True,
                "frozen_query_first_epoch": row["frozen_query_first_epoch"],
                "frozen_query_last_epoch": row["frozen_query_last_epoch"],
                "quarantine_reason": row["quarantine_reason"],
            }
        )

    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "quarantined_support_v2_candidate_X.npy", x)
    np.save(OUT / "quarantined_support_v2_candidate_y.npy", y)
    write_csv(OUT / "quarantined_support_v2_candidate_sidecar.csv", sidecar)
    write_csv(
        OUT / "quarantined_support_train_candidate_v2.csv",
        [row for row in sidecar if row["bank_partition"] == "support_train"],
    )
    write_csv(
        OUT / "quarantined_support_val_candidate_v2.csv",
        [row for row in sidecar if row["bank_partition"] == "support_val"],
    )

    materialization = {
        "issue": ISSUE,
        "status": "SUPPORT_V2_DIAGNOSTIC_MATERIALIZATION_QUARANTINED_FUTURE_ORDER",
        "model_training": False,
        "hpc_submission": False,
        "source_csv": SOURCE_CSV,
        "pcap_member": EXPECTED_PCAP,
        "pcap_zip_crc32": f"{pcap_info.CRC:08x}",
        "pcap_uncompressed_bytes": pcap_info.file_size,
        "plan_sha256": sha256(PLAN),
        "train_state_sha256": sha256(TRAIN_STATE),
        "train_state_meta_sha256": sha256(TRAIN_STATE_META),
        "train_state_declared_meta": state_meta,
        "state_hash_before": state_hash_before,
        "state_hash_after": ab.state_hash(nstat),
        "packets_scanned": packets_scanned,
        "packet_parse_errors": parse_errors,
        "timestamp_tolerance_us": TIME_TOLERANCE_US,
        "timestamp_ambiguities": ambiguity_count,
        "planned_rows": len(plan),
        "emitted_rows": len(sidecar),
        "missing_rows": 0,
        "support_train_rows": sum(row["bank_partition"] == "support_train" for row in sidecar),
        "support_val_rows": sum(row["bank_partition"] == "support_val" for row in sidecar),
        "support_val_fit_rows": sum(row["support_val_phase"] == "fit" for row in sidecar),
        "support_val_select_rows": sum(row["support_val_phase"] == "select" for row in sidecar),
        "report_rows": 0,
        "sealed_rows": 0,
        "raw_label_column_read": True,
        "raw_label_use": "offline_exact_support_materialization_only",
        "feature_schema": "Kitsune/AfterImage RestoredNetStat115 float32",
        "x_shape": list(x.shape),
        "x_dtype": str(x.dtype),
        "x_contract_sha256": array_digest(x),
        "y_contract_sha256": array_digest(y),
        "sidecar_sha256": sha256(OUT / "quarantined_support_v2_candidate_sidecar.csv"),
        "elapsed_seconds": round(time.monotonic() - started, 3),
    }
    result = write_quarantine_outputs(plan, sidecar, x, y, materialization)
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
