from __future__ import annotations

import csv
import hashlib
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "runs" / "issue27ckbr_support_v2_mechanism_contract_v1_2026-07-22"
PLAN = OUT / "support_v2_raw_extension_plan.csv"
CONTRACT = OUT / "support_v2_contract.json"
TARGETED_PLAN = (
    ROOT
    / "runs"
    / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
    / "targeted_exact_label_materialization_plan.csv"
)
SUPPORT_TRAIN = (
    ROOT
    / "runs"
    / "issue27ckg_label_support_region_registry_and_versioned_update_protocol_2026-06-22"
    / "support_train_view_v1.csv"
)
SUPPORT_VAL = SUPPORT_TRAIN.with_name("support_val_view_v1.csv")
RAW_ZIP = ROOT.parents[1] / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"

EXPECTED_TRAIN_HASH = "6440c9ba57412149008277c0c6ab2fb9d853a3be8d77b19812b20bed59c3ed99"
EXPECTED_VAL_HASH = "e9ac02ff6d3393613e67c43b7612784d6088afa9dec4eca6ab297c0a1dc427d5"
SOURCE = "processed/iotsim-city-power-1.csv"
LABELS = ("TCP Scan", "Telnet Brute Force")
EXPECTED_PCAP = (
    "raw/malicious/mirai-infection/"
    "iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap"
)
QUERY_MARGIN = 500
TRAIN_VAL_MARGIN = 32


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
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


def as_bool(value: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized not in {"true", "false"}:
        raise RuntimeError(f"invalid boolean value: {value!r}")
    return normalized == "true"


def frame_time_epoch(value: str) -> float:
    text = value.strip()
    if text.endswith(" GMT"):
        text = text[:-4]
    if "." in text:
        prefix, fraction = text.rsplit(".", 1)
        digits = "".join(char for char in fraction if char.isdigit())
        text = f"{prefix}.{(digits + '000000')[:6]}"
        parsed = datetime.strptime(text, "%b %d, %Y %H:%M:%S.%f")
    else:
        parsed = datetime.strptime(text, "%b %d, %Y %H:%M:%S")
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def main() -> None:
    for path in (PLAN, CONTRACT, TARGETED_PLAN, SUPPORT_TRAIN, SUPPORT_VAL, RAW_ZIP):
        if not path.is_file():
            raise FileNotFoundError(path)
    checks: dict[str, Any] = {}
    checks["support_train_v1_hash_frozen"] = sha256(SUPPORT_TRAIN) == EXPECTED_TRAIN_HASH
    checks["support_val_v1_hash_frozen"] = sha256(SUPPORT_VAL) == EXPECTED_VAL_HASH

    extension = rows(PLAN)
    checks["extension_rows_160"] = len(extension) == 160
    checks["unique_extension_ids"] = len({row["extension_row_id"] for row in extension}) == 160
    checks["unique_source_rows"] = len({(row["source_csv"], row["csv_row_index"]) for row in extension}) == 160
    checks["single_legal_source"] = {row["source_csv"] for row in extension} == {SOURCE}
    checks["target_labels_only"] = {row["exact_attack_label"] for row in extension} == set(LABELS)
    checks["preferred_pcap_only"] = {row["preferred_pcap_member"] for row in extension} == {EXPECTED_PCAP}
    checks["label_name_pcap_heuristic_explicitly_overridden"] = all(
        as_bool(row["heuristic_candidate_overridden"])
        and row["pcap_selection_evidence"]
        == "row_frame.time_range_unique_cover_overrides_label_name_scenario_heuristic"
        for row in extension
    )
    checks["no_report_or_sealed"] = all(
        not as_bool(row["report_only"]) and not as_bool(row["sealed_final"])
        for row in extension
    )
    checks["all_raw_labels_marked_verified"] = all(
        as_bool(row["raw_label_verified"]) for row in extension
    )
    checks["diagnostic_materialization_only"] = {
        row["feature_materialization_status"] for row in extension
    } == {"diagnostic_materialization_only_quarantined"}
    checks["all_rows_fail_closed"] = all(
        not as_bool(row["selection_allowed"])
        and as_bool(row["forbidden_for_fit"])
        and as_bool(row["forbidden_for_threshold"])
        and as_bool(row["forbidden_for_model_selection"])
        and not as_bool(row["temporal_admissibility"])
        and as_bool(row["same_capture_candidate_after_frozen_query"])
        for row in extension
    )

    counts = Counter((row["exact_attack_label"], row["bank_partition"]) for row in extension)
    checks["partition_counts"] = all(
        counts[(label, "support_train")] == 60 and counts[(label, "support_val")] == 20
        for label in LABELS
    )
    phases = Counter((row["exact_attack_label"], row["support_val_phase"]) for row in extension)
    checks["support_val_phase_counts"] = all(
        phases[(label, "fit")] == 10 and phases[(label, "select")] == 10
        for label in LABELS
    )

    query: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for row in rows(TARGETED_PLAN):
        if row["csv_member"] == SOURCE and row["attack_type"] in LABELS:
            query[row["attack_type"]].append(
                (int(row["planned_start_row"]), int(row["planned_end_row"]))
            )
    checks["frozen_query_counts_12000_each"] = all(
        sum(hi - lo + 1 for lo, hi in query[label]) == 12_000 for label in LABELS
    )
    checks["query_overlap_zero_and_500_row_embargo"] = all(
        all(
            int(row["csv_row_index"]) < lo - QUERY_MARGIN
            or int(row["csv_row_index"]) > hi + QUERY_MARGIN
            for lo, hi in query[row["exact_attack_label"]]
        )
        for row in extension
    )
    query_index_to_label = {
        index: label
        for label, intervals in query.items()
        for lo, hi in intervals
        for index in range(lo, hi + 1)
    }
    query_epochs: dict[str, list[float]] = defaultdict(list)
    with zipfile.ZipFile(RAW_ZIP) as zf, zf.open(SOURCE) as raw:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        for index, raw_row in enumerate(reader):
            if index > max(query_index_to_label):
                break
            label = query_index_to_label.get(index)
            if label is None:
                continue
            if raw_row.get("label", "") != label:
                raise RuntimeError(f"frozen query raw label mismatch at row {index}")
            query_epochs[label].append(frame_time_epoch(raw_row["frame.time"]))
    checks["frozen_query_raw_labels_and_timestamps_24000"] = all(
        len(query_epochs[label]) == 12_000 for label in LABELS
    )
    checks["same_capture_candidates_all_after_frozen_query"] = all(
        min(
            float(row["packet_timestamp_epoch"])
            for row in extension
            if row["exact_attack_label"] == label
        )
        > max(query_epochs[label])
        for label in LABELS
    )

    checks["train_val_segments_disjoint"] = True
    checks["train_val_rows_32_embargo"] = True
    for label in LABELS:
        train = [row for row in extension if row["exact_attack_label"] == label and row["bank_partition"] == "support_train"]
        val = [row for row in extension if row["exact_attack_label"] == label and row["bank_partition"] == "support_val"]
        if {row["source_segment_id"] for row in train} & {row["source_segment_id"] for row in val}:
            checks["train_val_segments_disjoint"] = False
        if any(
            abs(int(a["csv_row_index"]) - int(b["csv_row_index"])) <= TRAIN_VAL_MARGIN
            for a in train
            for b in val
        ):
            checks["train_val_rows_32_embargo"] = False

    indices = {int(row["csv_row_index"]): row["exact_attack_label"] for row in extension}
    raw_verified = 0
    with zipfile.ZipFile(RAW_ZIP) as zf, zf.open(SOURCE) as raw:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        for index, row in enumerate(reader):
            if index in indices:
                if row.get("label", "") != indices[index]:
                    raise RuntimeError(f"raw label mismatch at row {index}")
                raw_verified += 1
            if index > max(indices):
                break
    checks["raw_zip_exact_labels_160"] = raw_verified == 160

    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    checks["contract_status_is_quarantine_not_result"] = (
        contract.get("status")
        == "SUPPORT_V2_CANDIDATE_QUARANTINED_SAME_CAPTURE_FUTURE_ORDER"
        and contract.get("model_training") is False
        and contract.get("hpc_submission") is False
    )
    checks["active_support_counts_unchanged"] = (
        contract["frozen_v1"]["support_train_rows"] == 385
        and contract["frozen_v1"]["support_val_rows"] == 127
        and contract["quarantined_v2_candidate"]["active_support_train_rows"] == 385
        and contract["quarantined_v2_candidate"]["active_support_val_rows"] == 127
        and contract["data_quality_gate"]["temporal_admissible_new_support_rows"] == 0
    )
    checks["frozen_assets_not_mutated"] = (
        contract["strict_contract"]["original_1m_split_mutated"] is False
        and contract["strict_contract"]["original_385_support_mutated"] is False
        and contract["strict_contract"]["certified_query_rows_mutated"] is False
    )
    checks["report_zero_use_declared"] = (
        contract["strict_contract"]["report_rows_used"] == 0
        and contract["strict_contract"]["sealed_rows_used"] == 0
        and contract["strict_contract"]["permanent_report_families_used"] == 0
    )

    failures = sorted(name for name, passed in checks.items() if not passed)
    result = {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "plan_sha256": sha256(PLAN),
        "contract_sha256": sha256(CONTRACT),
        "scientific_scope": "temporal_admissibility_quarantine_not_model_performance",
    }
    (OUT / "independent_contract_validation.json").write_text(
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
