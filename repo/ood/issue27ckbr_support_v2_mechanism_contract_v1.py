from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import dpkt


ROOT = Path(__file__).resolve().parents[2]
ISSUE = "issue27ckbr_support_v2_mechanism_contract_v1_2026-07-22"
OUT = ROOT / "runs" / ISSUE

SUPPORT_DIR = (
    ROOT
    / "runs"
    / "issue27ckg_label_support_region_registry_and_versioned_update_protocol_2026-06-22"
)
SUPPORT_TRAIN = SUPPORT_DIR / "support_train_view_v1.csv"
SUPPORT_VAL = SUPPORT_DIR / "support_val_view_v1.csv"

CB_DIR = ROOT / "runs" / "issue27cb_broader_attack_support_candidate_contract_2026-06-14"
SEGMENT_INVENTORY = CB_DIR / "attack_segment_inventory_support_files.csv"
CURRENT_1M_EXACT_AUDIT = CB_DIR / "current_1m_attack_exact_label_audit.csv"

CC_DIR = (
    ROOT
    / "runs"
    / "issue27cc_targeted_multitype_attack_materialization_and_onset_realign_2026-06-14"
)
PAIRING_AUDIT = CC_DIR / "pcap_pairing_requirement_audit.csv"
TARGETED_PLAN = CC_DIR / "targeted_exact_label_materialization_plan.csv"

CF_DIR = (
    ROOT
    / "runs"
    / "issue27cf_initial_support_bank_instantiation_from_complete_exact_label_pool_2026-06-16"
)
ELIGIBLE_CANDIDATES = CF_DIR / "eligible_candidate_manifest.csv.gz"

CH_DIR = ROOT / "runs" / "issue27ch_certified_attack_subset_freeze_for_protocol_replay_2026-06-17"
CERTIFIED_CHUNKS = CH_DIR / "certified_chunk_manifest.csv"

DATA_ROOT = ROOT.parents[1] / "datasets" / "gotham2025"
RAW_ZIP = DATA_ROOT / "raw" / "GothamDataset2025.zip"
ASSET_DIR = DATA_ROOT / "derived" / "kitsune115_larger_sanity_1m_certified_v1"
SIDECAR_1M = ASSET_DIR / "gotham_kitsune115_1m_certified_train_state_then_eval_online_sidecar.csv.gz"

EXPECTED_SHA256 = {
    SUPPORT_TRAIN: "6440c9ba57412149008277c0c6ab2fb9d853a3be8d77b19812b20bed59c3ed99",
    SUPPORT_VAL: "e9ac02ff6d3393613e67c43b7612784d6088afa9dec4eca6ab297c0a1dc427d5",
    ELIGIBLE_CANDIDATES: "924975a2c9e09fbea8810546a7c3197d48cb17ec964b5e76066bf3d6f5ff3132",
}

SOURCE_CSV = "processed/iotsim-city-power-1.csv"
TARGET_LABELS = ("TCP Scan", "Telnet Brute Force")
MECHANISM = {
    "TCP Scan": "reconnaissance_scan",
    "Telnet Brute Force": "credential_bruteforce",
}
HEURISTIC_LABEL_PCAP = (
    "raw/malicious/network-scanning/"
    "iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap"
)
TIMESTAMP_SELECTED_PCAP = (
    "raw/malicious/mirai-infection/"
    "iotsim-city-power-1_0-0_to_OpenvSwitch-26_1-0.pcap"
)
TRAIN_PER_LABEL = 60
VAL_PER_LABEL = 20
QUERY_EMBARGO_ROWS = 500
TRAIN_VAL_EMBARGO_ROWS = 32

PERMANENT_REPORT_FAMILIES = (
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
)


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def read_csv_gz(path: Path) -> Iterable[dict[str, str]]:
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        yield from (dict(row) for row in csv.DictReader(f))


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


def stable_uid(*parts: Any) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:20]


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


def source_group(csv_path: str) -> str:
    stem = Path(csv_path).stem
    return stem[len("iotsim-") :] if stem.startswith("iotsim-") else stem


def support_v1_audit() -> tuple[list[dict[str, Any]], Counter[str], Counter[str]]:
    rows_out: list[dict[str, Any]] = []
    label_train: Counter[str] = Counter()
    label_val: Counter[str] = Counter()
    for partition, path, expected_count, counter in (
        ("support_train", SUPPORT_TRAIN, 385, label_train),
        ("support_val", SUPPORT_VAL, 127, label_val),
    ):
        rows = read_csv(path)
        if len(rows) != expected_count:
            raise RuntimeError(f"{partition} count changed: {len(rows)} != {expected_count}")
        if any(str(row.get("immutable", "")).lower() != "true" for row in rows):
            raise RuntimeError(f"{partition} contains a non-immutable row")
        grouped: Counter[tuple[str, str]] = Counter()
        for row in rows:
            label = row["exact_attack_label"]
            counter[label] += 1
            grouped[(row["csv_path"], label)] += 1
        for (csv_path, label), count in sorted(grouped.items()):
            rows_out.append(
                {
                    "support_version": "v1_frozen",
                    "bank_partition": partition,
                    "source_csv": csv_path,
                    "source_group": source_group(csv_path),
                    "exact_attack_label": label,
                    "rows": count,
                    "immutable": True,
                    "input_sha256": file_hash(path),
                }
            )
    return rows_out, label_train, label_val


def reproduce_support_val_phase() -> tuple[int, int, list[dict[str, Any]]]:
    rows = read_csv(SUPPORT_VAL)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["csv_path"], row["exact_attack_label"])].append(row)
    audit: list[dict[str, Any]] = []
    fit = 0
    select = 0
    for (csv_path, label), group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda row: (float(row["packet_timestamp"]), int(row["csv_row_index"])))
        fit_count = max(1, len(ordered) // 2) if len(ordered) >= 2 else 0
        select_count = len(ordered) - fit_count
        fit += fit_count
        select += select_count
        audit.append(
            {
                "support_version": "v1_frozen",
                "source_csv": csv_path,
                "exact_attack_label": label,
                "support_val_rows": len(ordered),
                "derived_fit_rows": fit_count,
                "derived_select_rows": select_count,
                "rule": "per_source_label_timestamp_sort_first_floor_half_fit_remainder_select",
            }
        )
    if (fit, select) != (58, 69):
        raise RuntimeError(f"support_val lineage changed: fit={fit}, select={select}")
    return fit, select, audit


def candidate_pool_audit() -> tuple[int, Counter[str]]:
    count = 0
    labels: Counter[str] = Counter()
    for row in read_csv_gz(ELIGIBLE_CANDIDATES):
        count += 1
        labels[row["exact_attack_label"]] += 1
        if row["selection_allowed"].lower() != "true":
            raise RuntimeError("issue27cf candidate unexpectedly selection-forbidden")
        if row["report_only"].lower() == "true" or row["sealed_final"].lower() == "true":
            raise RuntimeError("issue27cf candidate unexpectedly report/sealed")
    if count != 69_492:
        raise RuntimeError(f"issue27cf candidate count changed: {count}")
    return count, labels


def all_query_intervals() -> dict[tuple[str, str], list[tuple[int, int]]]:
    intervals: dict[tuple[str, str], list[tuple[int, int]]] = defaultdict(list)
    for row in read_csv(TARGETED_PLAN):
        if row["plan_role"] != "dev_future_attack_query_exact":
            continue
        intervals[(row["csv_member"], row["attack_type"])].append(
            (int(row["planned_start_row"]), int(row["planned_end_row"]))
        )
    return intervals


def current_1m_timestamp_exact_reaudit() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Re-audit exact labels by timestamp, never by recorded_index.

    The 1M sidecar's recorded_index_within_file is a role-local ordinal.  It is
    not the row index of the processed CSV.  The old issue27cb audit used it as
    a CSV row index; this function deliberately reconstructs the only safe
    correspondence: packet timestamp to frame.time within two microseconds.
    """

    sidecars: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv_gz(SIDECAR_1M):
        if row["role"] == "attack_support_candidate_pool":
            sidecars[row["csv_member"]].append(row)
    if {source: len(rows) for source, rows in sidecars.items()} != {
        "processed/iotsim-air-quality-1.csv": 45_000,
        SOURCE_CSV: 45_000,
    }:
        raise RuntimeError("current 1M attack-support source/count contract changed")

    query = all_query_intervals()
    output: list[dict[str, Any]] = []
    source_audit: dict[str, Any] = {}
    with zipfile.ZipFile(RAW_ZIP) as zf:
        for source, source_rows in sorted(sidecars.items()):
            keys: dict[int, list[int]] = defaultdict(list)
            for index, row in enumerate(source_rows):
                keys[int(round(float(row["packet_timestamp_epoch"]) * 1_000_000.0))].append(index)
            candidates: dict[int, list[tuple[int, str, float]]] = defaultdict(list)
            ambiguous_sidecars: set[int] = set()
            with zf.open(source) as raw:
                text = (line.decode("utf-8", errors="replace") for line in raw)
                reader = csv.DictReader(text)
                for csv_row_index, raw_row in enumerate(reader):
                    epoch = frame_time_epoch(raw_row.get("frame.time", ""))
                    center = int(round(epoch * 1_000_000.0))
                    matched_sidecars: list[int] = []
                    for key in range(center - 2, center + 3):
                        for sidecar_index in keys.get(key, []):
                            delta = abs(
                                float(source_rows[sidecar_index]["packet_timestamp_epoch"]) - epoch
                            )
                            if delta <= 2.000001e-6:
                                matched_sidecars.append(sidecar_index)
                    if len(matched_sidecars) > 1:
                        ambiguous_sidecars.update(matched_sidecars)
                    for sidecar_index in matched_sidecars:
                        candidates[sidecar_index].append(
                            (csv_row_index, raw_row.get("label", ""), epoch)
                        )

            exact: list[tuple[dict[str, str], int, str, float]] = []
            multiple_csv_matches = 0
            for sidecar_index, row in enumerate(source_rows):
                values = candidates.get(sidecar_index, [])
                if sidecar_index in ambiguous_sidecars or len(values) != 1:
                    if len(values) > 1:
                        multiple_csv_matches += 1
                    continue
                csv_row_index, label, epoch = values[0]
                exact.append((row, csv_row_index, label, epoch))

            labels = Counter(label for _row, _index, label, _epoch in exact)
            for label, count in sorted(labels.items()):
                intervals = query.get((source, label), [])
                overlap = sum(
                    any(lo <= csv_row_index <= hi for lo, hi in intervals)
                    for _row, csv_row_index, value, _epoch in exact
                    if value == label
                )
                output.append(
                    {
                        "source_csv": source,
                        "source_group": source_group(source),
                        "materialized_pcap_member": source_rows[0]["pcap_member"],
                        "exact_attack_label": label,
                        "timestamp_aligned_unique_rows": count,
                        "certified_query_overlap_rows": overlap,
                        "unused_aligned_rows_outside_certified_query": count - overlap,
                        "alignment_rule": "packet_timestamp_epoch_to_frame.time_within_2us",
                        "recorded_index_used_as_csv_row": False,
                    }
                )
            source_audit[source] = {
                "sidecar_rows": len(source_rows),
                "timestamp_aligned_unique_rows": len(exact),
                "unmatched_or_nonunique_rows": len(source_rows) - len(exact),
                "ambiguous_sidecar_rows": len(ambiguous_sidecars),
                "multiple_csv_matches": multiple_csv_matches,
                "materialized_pcap_member": source_rows[0]["pcap_member"],
            }

    legacy_rows = sum(
        int(row["rows"])
        for row in read_csv(CURRENT_1M_EXACT_AUDIT)
        if row["role"] == "attack_support_candidate_pool"
    )
    if legacy_rows != 90_000:
        raise RuntimeError("legacy issue27cb audit total changed")
    audit = {
        "status": "LEGACY_INDEX_BASED_EXACT_LABEL_AUDIT_REJECTED",
        "legacy_rows": legacy_rows,
        "reason": "recorded_index_within_file_is_role_local_not_processed_csv_row_index",
        "replacement_rule": "packet_timestamp_epoch_to_frame.time_within_2us_unique_match",
        "sources": source_audit,
    }
    return output, audit


def query_intervals() -> dict[str, list[tuple[int, int]]]:
    all_intervals = all_query_intervals()
    intervals = {label: all_intervals[(SOURCE_CSV, label)] for label in TARGET_LABELS}
    for label in TARGET_LABELS:
        if sum(hi - lo + 1 for lo, hi in intervals[label]) != 12_000:
            raise RuntimeError(f"existing certified query count changed for {label}")
    return intervals


def outside_intervals(index: int, intervals: list[tuple[int, int]], margin: int) -> bool:
    return all(index < lo - margin or index > hi + margin for lo, hi in intervals)


def extract_csv_rows(indices: set[int]) -> dict[int, dict[str, str]]:
    if not indices:
        return {}
    found: dict[int, dict[str, str]] = {}
    max_index = max(indices)
    with zipfile.ZipFile(RAW_ZIP) as zf:
        if SOURCE_CSV not in zf.namelist():
            raise RuntimeError(f"raw CSV missing: {SOURCE_CSV}")
        with zf.open(SOURCE_CSV) as raw:
            text = (line.decode("utf-8", errors="replace") for line in raw)
            reader = csv.DictReader(text)
            if not reader.fieldnames or "label" not in reader.fieldnames:
                raise RuntimeError("raw CSV label column missing")
            timestamp_key = next(
                (
                    name
                    for name in ("frame.time", "timestamp", "ts", "time")
                    if name in reader.fieldnames
                ),
                None,
            )
            if timestamp_key is None:
                raise RuntimeError(f"raw CSV timestamp column missing: {reader.fieldnames}")
            for row_index, row in enumerate(reader):
                if row_index > max_index:
                    break
                if row_index in indices:
                    found[row_index] = {
                        "label": row.get("label", ""),
                        "timestamp": row.get(timestamp_key, ""),
                        "timestamp_column": timestamp_key,
                    }
    if set(found) != indices:
        missing = sorted(indices - set(found))[:10]
        raise RuntimeError(f"raw CSV selected rows missing: {missing}")
    return found


def query_timestamp_bounds() -> dict[str, dict[str, Any]]:
    """Read the frozen query intervals at their true CSV timestamps.

    A row-index embargo is not a temporal split.  These bounds are used to
    reject same-capture support candidates that occur after an already frozen
    future/query interval, even when their row indices do not overlap.
    """

    intervals = query_intervals()
    index_to_label: dict[int, str] = {}
    for label, values in intervals.items():
        for lo, hi in values:
            for index in range(lo, hi + 1):
                if index in index_to_label:
                    raise RuntimeError(f"overlapping frozen query intervals at CSV row {index}")
                index_to_label[index] = label
    max_index = max(index_to_label)
    observed: dict[str, list[tuple[int, float]]] = defaultdict(list)
    with zipfile.ZipFile(RAW_ZIP) as zf, zf.open(SOURCE_CSV) as raw:
        text = (line.decode("utf-8", errors="replace") for line in raw)
        reader = csv.DictReader(text)
        for row_index, row in enumerate(reader):
            if row_index > max_index:
                break
            label = index_to_label.get(row_index)
            if label is None:
                continue
            if row.get("label", "") != label:
                raise RuntimeError(
                    f"frozen query raw label mismatch at row {row_index}: "
                    f"{row.get('label', '')!r} != {label!r}"
                )
            observed[label].append((row_index, frame_time_epoch(row["frame.time"])))

    result: dict[str, dict[str, Any]] = {}
    for label in TARGET_LABELS:
        values = observed[label]
        if len(values) != 12_000:
            raise RuntimeError(f"frozen query timestamp count changed for {label}: {len(values)}")
        result[label] = {
            "exact_attack_label": label,
            "source_csv": SOURCE_CSV,
            "query_rows": len(values),
            "query_first_csv_row": min(index for index, _epoch in values),
            "query_last_csv_row": max(index for index, _epoch in values),
            "query_first_epoch": min(epoch for _index, epoch in values),
            "query_last_epoch": max(epoch for _index, epoch in values),
            "raw_labels_verified": len(values),
        }
    return result


def pcap_time_ranges(members: list[str]) -> list[dict[str, Any]]:
    ranges: list[dict[str, Any]] = []
    with zipfile.ZipFile(RAW_ZIP) as zf:
        names = set(zf.namelist())
        for member in members:
            if member not in names:
                ranges.append({"pcap_member": member, "status": "missing"})
                continue
            first = None
            last = None
            packets = 0
            with zf.open(member) as raw:
                reader = dpkt.pcap.Reader(io.BufferedReader(raw))
                for timestamp, _packet in reader:
                    first = float(timestamp) if first is None else first
                    last = float(timestamp)
                    packets += 1
            ranges.append(
                {
                    "pcap_member": member,
                    "status": "ok",
                    "first_epoch": first,
                    "last_epoch": last,
                    "packets": packets,
                }
            )
    return ranges


def select_extension_rows() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
]:
    intervals = query_intervals()
    pairing = {
        (row["csv_member"], row["attack_type"]): row
        for row in read_csv(PAIRING_AUDIT)
    }
    segments_by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(SEGMENT_INVENTORY):
        if row["csv_member"] == SOURCE_CSV and row["label"] in TARGET_LABELS:
            segments_by_label[row["label"]].append(row)

    preliminary: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    for label in TARGET_LABELS:
        pair = pairing.get((SOURCE_CSV, label))
        if not pair or pair["preferred_pcap_candidate"] != HEURISTIC_LABEL_PCAP:
            raise RuntimeError(f"label-name PCAP heuristic changed for {label}")
        candidate_segments: list[tuple[int, int, int, list[int]]] = []
        total_exact = 0
        query_rows = sum(hi - lo + 1 for lo, hi in intervals[label])
        available = 0
        for row in sorted(segments_by_label[label], key=lambda x: int(x["segment_start_row"])):
            segment_id = int(row["segment_id"])
            lo = int(row["segment_start_row"])
            hi = int(row["segment_end_row"])
            total_exact += hi - lo + 1
            candidates = [
                index
                for index in range(lo, hi + 1)
                if outside_intervals(index, intervals[label], QUERY_EMBARGO_ROWS)
            ]
            if candidates:
                available += len(candidates)
                candidate_segments.append((segment_id, lo, hi, candidates))
        if len(candidate_segments) < TRAIN_PER_LABEL + VAL_PER_LABEL:
            raise RuntimeError(
                f"not enough segment-diverse unused rows for {label}: {len(candidate_segments)} segments"
            )

        # Use one midpoint per exact-label segment. This avoids dense adjacent-packet
        # sampling and makes train/validation segments disjoint by construction.
        chosen_segments = candidate_segments[-(TRAIN_PER_LABEL + VAL_PER_LABEL) :]
        train_segments = chosen_segments[:TRAIN_PER_LABEL]
        val_segments = chosen_segments[TRAIN_PER_LABEL:]
        train_midpoints = [values[len(values) // 2] for _, _, _, values in train_segments]
        val_midpoints = [values[len(values) // 2] for _, _, _, values in val_segments]
        if any(
            abs(train_index - val_index) <= TRAIN_VAL_EMBARGO_ROWS
            for train_index in train_midpoints
            for val_index in val_midpoints
        ):
            raise RuntimeError(f"train/validation row embargo failed for {label}")

        inventory_rows.append(
            {
                "source_csv": SOURCE_CSV,
                "source_group": "city-power",
                "exact_attack_label": label,
                "mechanism_family": MECHANISM[label],
                "raw_exact_rows": total_exact,
                "existing_certified_query_rows": query_rows,
                "query_embargo_rows": QUERY_EMBARGO_ROWS,
                "eligible_unused_rows_after_embargo": available,
                "eligible_segments_after_embargo": len(candidate_segments),
                "planned_support_train_rows": TRAIN_PER_LABEL,
                "planned_support_val_rows": VAL_PER_LABEL,
                "heuristic_label_pcap_candidate": pair["preferred_pcap_candidate"],
                "heuristic_pcap_pairing_confidence": pair["pcap_pairing_confidence"],
                "timestamp_selected_pcap_member": "pending_row_time_range_gate",
                "timestamp_pcap_pairing_confidence": "pending",
            }
        )
        for partition, selected in (("support_train", train_segments), ("support_val", val_segments)):
            for segment_id, seg_lo, seg_hi, values in selected:
                row_index = values[len(values) // 2]
                preliminary.append(
                    {
                        "extension_row_id": "ckbr_" + stable_uid(label, partition, segment_id, row_index),
                        "support_version": "support_v2_extension_plan_v1",
                        "bank_partition": partition,
                        "support_val_phase": "pending_deterministic_lineage",
                        "source_contract_role": "quarantined_same_capture_future_order_diagnostic",
                        "source_csv": SOURCE_CSV,
                        "source_group": "city-power",
                        "exact_attack_label": label,
                        "mechanism_family": MECHANISM[label],
                        "source_segment_id": segment_id,
                        "source_segment_start_row": seg_lo,
                        "source_segment_end_row": seg_hi,
                        "csv_row_index": row_index,
                        "packet_timestamp_raw": "",
                        "packet_timestamp_epoch": "",
                        "timestamp_column": "",
                        "heuristic_label_pcap_candidate": pair["preferred_pcap_candidate"],
                        "heuristic_pcap_pairing_confidence": pair["pcap_pairing_confidence"],
                        "preferred_pcap_member": "pending_row_time_range_gate",
                        "pcap_pairing_confidence": "pending",
                        "query_embargo_rows": QUERY_EMBARGO_ROWS,
                        "train_val_embargo_rows": TRAIN_VAL_EMBARGO_ROWS,
                        "overlap_with_existing_certified_query": False,
                        "overlap_with_support_v1": False,
                        "raw_label_verified": False,
                        "feature_materialization_status": "diagnostic_materialization_only_quarantined",
                        "feature_vector_sha256": "",
                        "selection_allowed": False,
                        "report_only": False,
                        "sealed_final": False,
                        "forbidden_for_fit": True,
                        "forbidden_for_threshold": True,
                        "forbidden_for_model_selection": True,
                        "selection_rule": (
                            "diagnostic_latest_nonoverlap_segments_one_midpoint_each_"
                            "query500_trainval_segment_disjoint_then_temporal_gate"
                        ),
                    }
                )

    raw_rows = extract_csv_rows({int(row["csv_row_index"]) for row in preliminary})
    for row in preliminary:
        raw = raw_rows[int(row["csv_row_index"])]
        if raw["label"] != row["exact_attack_label"]:
            raise RuntimeError(
                f"raw label mismatch at {row['csv_row_index']}: {raw['label']} != {row['exact_attack_label']}"
            )
        row["packet_timestamp_raw"] = raw["timestamp"]
        row["packet_timestamp_epoch"] = frame_time_epoch(raw["timestamp"])
        row["timestamp_column"] = raw["timestamp_column"]
        row["raw_label_verified"] = True

    all_candidates: list[str] = []
    for label in TARGET_LABELS:
        pair = pairing[(SOURCE_CSV, label)]
        for member in [pair["preferred_pcap_candidate"], *pair["all_pcap_candidates"].split("|")]:
            if member and member not in all_candidates:
                all_candidates.append(member)
    ranges = pcap_time_ranges(all_candidates)
    target_first = min(float(row["packet_timestamp_epoch"]) for row in preliminary)
    target_last = max(float(row["packet_timestamp_epoch"]) for row in preliminary)
    covering = [
        row["pcap_member"]
        for row in ranges
        if row["status"] == "ok"
        and row["first_epoch"] is not None
        and row["last_epoch"] is not None
        and float(row["first_epoch"]) <= target_first
        and float(row["last_epoch"]) >= target_last
    ]
    if covering != [TIMESTAMP_SELECTED_PCAP]:
        raise RuntimeError(
            f"selected row timestamps do not map uniquely to frozen PCAP: covering={covering}"
        )
    for row in preliminary:
        row["preferred_pcap_member"] = TIMESTAMP_SELECTED_PCAP
        row["pcap_pairing_confidence"] = "high_unique_full_target_time_range"
        row["pcap_selection_evidence"] = (
            "row_frame.time_range_unique_cover_overrides_label_name_scenario_heuristic"
        )
        row["heuristic_candidate_overridden"] = True
    for row in inventory_rows:
        row["timestamp_selected_pcap_member"] = TIMESTAMP_SELECTED_PCAP
        row["timestamp_pcap_pairing_confidence"] = "high_unique_full_target_time_range"
        row["target_first_epoch"] = target_first
        row["target_last_epoch"] = target_last
        row["pcap_time_range_audit"] = json.dumps(ranges, sort_keys=True)

    # Preserve the frozen CKBQ rule for support_val: within each source/label,
    # timestamp sort, earliest floor-half is fit and the remainder is select.
    for label in TARGET_LABELS:
        val_rows = sorted(
            [
                row
                for row in preliminary
                if row["exact_attack_label"] == label and row["bank_partition"] == "support_val"
            ],
            key=lambda row: (float(row["packet_timestamp_epoch"]), int(row["csv_row_index"])),
        )
        half = max(1, len(val_rows) // 2)
        for index, row in enumerate(val_rows):
            row["support_val_phase"] = "fit" if index < half else "select"
    for row in preliminary:
        if row["bank_partition"] == "support_train":
            row["support_val_phase"] = "not_applicable"

    query_bounds = query_timestamp_bounds()
    temporal_audit: list[dict[str, Any]] = []
    for label in TARGET_LABELS:
        selected = [row for row in preliminary if row["exact_attack_label"] == label]
        selected_first = min(float(row["packet_timestamp_epoch"]) for row in selected)
        selected_last = max(float(row["packet_timestamp_epoch"]) for row in selected)
        bound = query_bounds[label]
        support_after_query = selected_first > float(bound["query_last_epoch"])
        if not support_after_query:
            raise RuntimeError(
                f"expected diagnosed same-capture future-order conflict for {label}; "
                f"selected_first={selected_first}, query_last={bound['query_last_epoch']}"
            )
        audit_row = {
            **bound,
            "candidate_rows": len(selected),
            "candidate_first_epoch": selected_first,
            "candidate_last_epoch": selected_last,
            "candidate_first_minus_query_last_seconds": selected_first
            - float(bound["query_last_epoch"]),
            "same_capture_candidate_after_frozen_query": True,
            "temporal_admissibility": False,
            "decision": "QUARANTINE_FORBIDDEN_FOR_FIT_SELECT",
        }
        temporal_audit.append(audit_row)
        for row in selected:
            row["frozen_query_first_epoch"] = bound["query_first_epoch"]
            row["frozen_query_last_epoch"] = bound["query_last_epoch"]
            row["same_capture_candidate_after_frozen_query"] = True
            row["temporal_admissibility"] = False
            row["quarantine_reason"] = (
                "same_capture_candidate_occurs_after_already_frozen_future_query"
            )
    for row in inventory_rows:
        audit = next(
            item for item in temporal_audit if item["exact_attack_label"] == row["exact_attack_label"]
        )
        row["temporal_admissible_rows"] = 0
        row["same_capture_candidate_after_frozen_query"] = True
        row["candidate_first_epoch"] = audit["candidate_first_epoch"]
        row["frozen_query_last_epoch"] = audit["query_last_epoch"]
        row["candidate_status"] = "QUARANTINED_SAME_CAPTURE_FUTURE_ORDER"

    return (
        sorted(
            preliminary,
            key=lambda row: (
                row["exact_attack_label"],
                row["bank_partition"],
                int(row["csv_row_index"]),
            ),
        ),
        inventory_rows,
        temporal_audit,
    )


def strict_exclusion_contract(extension_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.append(
        {
            "held_scope_type": "global_temporal_quarantine",
            "held_scope_value": "same_capture_candidate_after_frozen_future_query",
            "extension_rows_total": len(extension_rows),
            "rows_matching_held_scope": len(extension_rows),
            "required_fit_use": 0,
            "required_select_use": 0,
            "required_standardization_use": 0,
            "required_negative_sampling_use": 0,
            "required_threshold_use": 0,
            "enforcement": "permanent_zero_use_unless_a_new_forward_chronology_protocol_is_preregistered",
        }
    )
    for held_label in TARGET_LABELS:
        rows.append(
            {
                "held_scope_type": "strict_leave_attack_family",
                "held_scope_value": held_label,
                "extension_rows_total": len(extension_rows),
                "rows_matching_held_scope": sum(
                    row["exact_attack_label"] == held_label for row in extension_rows
                ),
                "required_fit_use": 0,
                "required_select_use": 0,
                "required_standardization_use": 0,
                "required_negative_sampling_use": 0,
                "required_threshold_use": 0,
                "enforcement": "exclude_entire_matching_attack_family_before_any_fit_or_select_operation",
            }
        )
    rows.append(
        {
            "held_scope_type": "strict_leave_source",
            "held_scope_value": "processed/iotsim-city-power-1.csv",
            "extension_rows_total": len(extension_rows),
            "rows_matching_held_scope": len(extension_rows),
            "required_fit_use": 0,
            "required_select_use": 0,
            "required_standardization_use": 0,
            "required_negative_sampling_use": 0,
            "required_threshold_use": 0,
            "enforcement": "exclude_entire_source_before_any_fit_or_select_operation",
        }
    )
    for family in PERMANENT_REPORT_FAMILIES:
        rows.append(
            {
                "held_scope_type": "permanent_report_family",
                "held_scope_value": family,
                "extension_rows_total": len(extension_rows),
                "rows_matching_held_scope": 0,
                "required_fit_use": 0,
                "required_select_use": 0,
                "required_standardization_use": 0,
                "required_negative_sampling_use": 0,
                "required_threshold_use": 0,
                "enforcement": "permanent_zero_use_and_no_label_driven_route_selection",
            }
        )
    return rows


def main() -> None:
    required = [
        SUPPORT_TRAIN,
        SUPPORT_VAL,
        SEGMENT_INVENTORY,
        CURRENT_1M_EXACT_AUDIT,
        PAIRING_AUDIT,
        TARGETED_PLAN,
        ELIGIBLE_CANDIDATES,
        CERTIFIED_CHUNKS,
        RAW_ZIP,
        SIDECAR_1M,
    ]
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(path)
    for path, expected in EXPECTED_SHA256.items():
        actual = file_hash(path)
        if actual != expected:
            raise RuntimeError(f"frozen input hash changed: {path}: {actual} != {expected}")

    OUT.mkdir(parents=True, exist_ok=True)
    support_audit, v1_train_labels, v1_val_labels = support_v1_audit()
    v1_val_fit, v1_val_select, val_lineage = reproduce_support_val_phase()
    candidate_count, candidate_labels = candidate_pool_audit()
    timestamp_reaudit, legacy_index_audit = current_1m_timestamp_exact_reaudit()
    extension, candidate_inventory, temporal_audit = select_extension_rows()
    strict_contract = strict_exclusion_contract(extension)

    if len(extension) != 160:
        raise RuntimeError(f"extension row count mismatch: {len(extension)}")
    extension_train = sum(row["bank_partition"] == "support_train" for row in extension)
    extension_val = sum(row["bank_partition"] == "support_val" for row in extension)
    extension_val_fit = sum(row["support_val_phase"] == "fit" for row in extension)
    extension_val_select = sum(row["support_val_phase"] == "select" for row in extension)
    if (extension_train, extension_val, extension_val_fit, extension_val_select) != (120, 40, 20, 20):
        raise RuntimeError("extension partition/phase counts changed")
    if len({row["extension_row_id"] for row in extension}) != len(extension):
        raise RuntimeError("duplicate extension row ID")
    if len({(row["source_csv"], row["csv_row_index"]) for row in extension}) != len(extension):
        raise RuntimeError("duplicate extension source row")
    if any(row["report_only"] or row["sealed_final"] for row in extension):
        raise RuntimeError("extension contains report/sealed row")
    if any(
        row["selection_allowed"]
        or not row["forbidden_for_fit"]
        or not row["forbidden_for_threshold"]
        or not row["forbidden_for_model_selection"]
        or row["temporal_admissibility"]
        for row in extension
    ):
        raise RuntimeError("temporally inadmissible candidate was not quarantined fail-closed")

    partition_summary: list[dict[str, Any]] = []
    for label in TARGET_LABELS:
        for partition in ("support_train", "support_val"):
            rows = [
                row
                for row in extension
                if row["exact_attack_label"] == label and row["bank_partition"] == partition
            ]
            partition_summary.append(
                {
                    "support_version": "v2_candidate_quarantined",
                    "source_csv": SOURCE_CSV,
                    "exact_attack_label": label,
                    "mechanism_family": MECHANISM[label],
                    "bank_partition": partition,
                    "rows": len(rows),
                    "support_val_fit_rows": sum(row["support_val_phase"] == "fit" for row in rows),
                    "support_val_select_rows": sum(row["support_val_phase"] == "select" for row in rows),
                    "active_rows": 0,
                    "quarantined_candidate_rows": len(rows),
                }
            )

    aligned_existing_target_rows = sum(
        int(row["timestamp_aligned_unique_rows"])
        for row in timestamp_reaudit
        if row["exact_attack_label"] in TARGET_LABELS
    )
    unused_existing_target_rows = sum(
        int(row["unused_aligned_rows_outside_certified_query"])
        for row in timestamp_reaudit
        if row["exact_attack_label"] in TARGET_LABELS
    )
    input_hashes = {
        str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path): file_hash(path)
        for path in required
    }

    contract = {
        "issue": ISSUE,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "SUPPORT_V2_CANDIDATE_QUARANTINED_SAME_CAPTURE_FUTURE_ORDER",
        "model_training": False,
        "hpc_submission": False,
        "frozen_v1": {
            "support_train_rows": 385,
            "support_val_rows": 127,
            "support_val_fit_rows": v1_val_fit,
            "support_val_select_rows": v1_val_select,
            "support_train_sha256": EXPECTED_SHA256[SUPPORT_TRAIN],
            "support_val_sha256": EXPECTED_SHA256[SUPPORT_VAL],
        },
        "quarantined_v2_candidate": {
            "source_csv": SOURCE_CSV,
            "labels": list(TARGET_LABELS),
            "support_train_rows": extension_train,
            "support_val_rows": extension_val,
            "support_val_fit_rows": extension_val_fit,
            "support_val_select_rows": extension_val_select,
            "active_support_train_rows": 385,
            "active_support_val_rows": 127,
            "active_support_val_fit_rows": v1_val_fit,
            "active_support_val_select_rows": v1_val_select,
            "hypothetical_illegal_train_rows_if_activated": 385 + extension_train,
            "hypothetical_illegal_val_rows_if_activated": 127 + extension_val,
            "hypothetical_illegal_val_fit_rows_if_activated": v1_val_fit + extension_val_fit,
            "hypothetical_illegal_val_select_rows_if_activated": v1_val_select + extension_val_select,
            "heuristic_label_pcap_candidate": HEURISTIC_LABEL_PCAP,
            "timestamp_selected_pcap_member": TIMESTAMP_SELECTED_PCAP,
            "feature_materialization_status": "diagnostic_only_quarantined",
            "selection_allowed_rows": 0,
            "forbidden_for_fit_rows": len(extension),
            "temporal_admissibility": False,
        },
        "data_quality_gate": {
            "legacy_issue27cb_index_exact_label_audit_rejected": True,
            "legacy_rows_affected": legacy_index_audit["legacy_rows"],
            "reason": legacy_index_audit["reason"],
            "timestamp_reaudited_existing_tcp_telnet_rows": aligned_existing_target_rows,
            "timestamp_reaudited_existing_tcp_telnet_rows_outside_certified_query": unused_existing_target_rows,
            "label_name_pcap_heuristic_overridden": True,
            "pcap_override_reason": (
                "selected row frame.time range is covered uniquely by mirai-infection PCAP; "
                "the scenario-name network-scanning candidate has no time overlap"
            ),
            "new_rows_raw_label_verified": len(extension),
            "new_rows_target_query_overlap": 0,
            "new_rows_report_or_sealed": 0,
            "same_capture_candidates_after_frozen_query": len(extension),
            "temporal_admissible_new_support_rows": 0,
        },
        "active_mechanism_coverage": sorted(set(v1_train_labels)),
        "quarantined_candidate_mechanisms": list(TARGET_LABELS),
        "candidate_pool_v1": {
            "rows": candidate_count,
            "labels": dict(sorted(candidate_labels.items())),
        },
        "strict_contract": {
            "original_1m_split_mutated": False,
            "original_385_support_mutated": False,
            "certified_query_rows_mutated": False,
            "report_rows_used": 0,
            "sealed_rows_used": 0,
            "permanent_report_families_used": 0,
            "quarantined_candidate_rows_used_in_fit_or_select": 0,
            "all_quarantined_candidate_rows_fail_closed": True,
            "strict_held_family_removes_matching_extension_before_fit_select": True,
            "strict_held_source_removes_all_city_power_extension_before_fit_select": True,
        },
        "next_gate": (
            "identify an independent training capture or external dataset training split with legal "
            "scan/bruteforce process labels and forward chronology; keep all 160 Gotham candidates quarantined"
        ),
    }

    write_csv(OUT / "support_v1_freeze_audit.csv", support_audit)
    write_csv(OUT / "support_val_v1_lineage.csv", val_lineage)
    write_csv(OUT / "current_1m_timestamp_exact_label_reaudit.csv", timestamp_reaudit)
    (OUT / "legacy_index_semantics_conflict.json").write_text(
        json.dumps(legacy_index_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_csv(OUT / "support_v2_candidate_inventory.csv", candidate_inventory)
    write_csv(OUT / "support_v2_temporal_admissibility_audit.csv", temporal_audit)
    write_csv(OUT / "support_v2_raw_extension_plan.csv", extension)
    write_csv(OUT / "support_v2_partition_summary.csv", partition_summary)
    write_csv(OUT / "support_v2_strict_exclusion_contract.csv", strict_contract)
    (OUT / "support_v2_contract.json").write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (OUT / "input_hashes.json").write_text(
        json.dumps(input_hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    summary = f"""# CKBR support-v2 mechanism contract

Status: `SUPPORT_V2_CANDIDATE_QUARANTINED_SAME_CAPTURE_FUTURE_ORDER`.

## What is frozen

- Original support v1 is unchanged: train `385`, validation `127`.
- Reproduced validation lineage: fit `58`, select `69`.
- The certified 1M split, 26-source T0 manifest, certified attack query chunks, report rows, and sealed rows are not changed.

## Blocking data-quality findings

The legacy issue27cb exact-label audit treated `recorded_index_within_file` as a processed-CSV row index. It is actually a role-local ordinal. Therefore its 90,000-row label inventory is rejected. The replacement audit uses unique PCAP-packet timestamp to CSV `frame.time` alignment within 2 microseconds. It finds `{aligned_existing_target_rows:,}` exact aligned TCP/Telnet rows, but `{unused_existing_target_rows}` remain outside the already frozen certified query intervals; they cannot supply a non-overlapping support extension.

The issue27cc `network-scanning` PCAP recommendation was a scenario-name heuristic, not row-level pairing evidence. The selected unused rows occur during the `mirai-infection` capture, whose time range uniquely covers all 160 target timestamps. The contract records this override explicitly rather than silently following the heuristic.

## Quarantined diagnostic candidate

- Source: `{SOURCE_CSV}` (already a development support source for other attack mechanisms).
- New mechanisms: `TCP Scan` and `Telnet Brute Force`.
- Diagnostic rows: proposed train `{extension_train}`, proposed validation `{extension_val}`.
- The apparent combined counts `505/167` are hypothetical and forbidden. Active support remains train `385`, validation `127` with fit/select `58/69`.
- Each row comes from a distinct exact-label segment, is at least `{QUERY_EMBARGO_ROWS}` CSV rows from every existing certified query interval, and maps uniquely by time range to `{TIMESTAMP_SELECTED_PCAP}`.
- All 160 raw CSV labels were verified and their diagnostic 115D vectors can be materialized exactly.
- However, every candidate occurs in the same capture after the already frozen TCP/Telnet future-query interval. Row non-overlap does not make a reverse-chronology split legal. All 160 rows are therefore fail-closed from fit, select, standardization, thresholding, negative sampling, and model selection.

## Scientific boundary

This audit does not broaden active attack supervision and is not a detector result. It does not use stream, hydraulic, ip-camera-street, predictive-maintenance, report, or sealed labels. The frozen support v1 remains the only active support bank.

## Next gate

Find an independent training capture or an external dataset's training split with legal scan/bruteforce process labels and forward chronology. Its test/report split must remain untouched. Do not train on any of these 160 Gotham rows.
"""
    (OUT / "summary.md").write_text(summary, encoding="utf-8")
    print(json.dumps(contract, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
