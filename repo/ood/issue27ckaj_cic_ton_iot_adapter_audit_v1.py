"""issue27ckaj: CIC-ToN-IoT external dataset adapter/audit v1.

This script does *not* train a detector.  It constructs the first clean,
auditable intake layer for the second dataset:

* verify the downloaded UQ CIC-ToN-IoT artifact;
* audit labels, columns, timestamp/order, feature null/non-finite values;
* freeze deterministic role splits for later experiments.

Data-use boundary:

* zero-shot external validation may use all rows as report-only rows;
* few-shot/adaptation may use only the explicit fit/select roles below;
* report/sealed roles are never available for fitting, thresholding,
  feature selection, or cleanup-rule tuning.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import heapq
import json
import math
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import numpy as np


ISSUE = "issue27ckaj_cic_ton_iot_adapter_audit_v1_2026-07-09"
DATASET_UUID = "127784c0-ef9d-11ed-a964-b70596e96ad5"

WORKTREE = Path(__file__).resolve().parents[2]
PAPER04 = WORKTREE.parent.parent
DEFAULT_DATA_DIR = (
    PAPER04
    / "datasets"
    / "external"
    / "cic_ton_iot"
    / "extracted"
    / "a40a412453292fe6_MOHANAD_A4706"
)
DEFAULT_CSV = DEFAULT_DATA_DIR / "data" / "CIC-ToN-IoT.csv"
DEFAULT_FEATURE_DOC = DEFAULT_DATA_DIR / "data" / "CICFLowMeter_Features.csv"
DEFAULT_RAW_ZIP = (
    PAPER04
    / "datasets"
    / "external"
    / "cic_ton_iot"
    / "raw"
    / f"CIC-ToN-IoT_UQ_{DATASET_UUID}.zip"
)
OUT = WORKTREE / "runs" / ISSUE

ID_COLUMNS = {
    "Flow ID",
    "Src IP",
    "Dst IP",
    "Timestamp",
    "Label",
    "Attack",
}

TIMESTAMP_FORMAT = "%d/%m/%Y %I:%M:%S %p"
SEED = "issue27ckaj_cic_ton_iot_split_v1"


@dataclass(frozen=True)
class RoleSpec:
    role: str
    phase: str
    role_kind: str
    protocol: str
    fit_allowed: bool
    threshold_allowed: bool
    report_only: bool


ROLE_SPECS: dict[str, RoleSpec] = {
    "id_benign_fit": RoleSpec(
        "id_benign_fit",
        "fit",
        "benign_id_fit",
        "fewshot_adaptation_v1",
        True,
        False,
        False,
    ),
    "id_benign_select": RoleSpec(
        "id_benign_select",
        "select",
        "benign_id_select",
        "fewshot_adaptation_v1",
        False,
        True,
        False,
    ),
    "support_attack_train": RoleSpec(
        "support_attack_train",
        "fit",
        "attack_support_fit",
        "fewshot_adaptation_v1",
        True,
        False,
        False,
    ),
    "support_attack_val": RoleSpec(
        "support_attack_val",
        "select",
        "attack_support_select",
        "fewshot_adaptation_v1",
        False,
        True,
        False,
    ),
    "attack_query_report": RoleSpec(
        "attack_query_report",
        "report",
        "attack_query_report_only",
        "fewshot_adaptation_v1",
        False,
        False,
        True,
    ),
    "sealed_benign_report": RoleSpec(
        "sealed_benign_report",
        "report",
        "benign_external_report_only",
        "fewshot_adaptation_v1",
        False,
        False,
        True,
    ),
    "sealed_attack_report": RoleSpec(
        "sealed_attack_report",
        "report",
        "attack_external_report_only",
        "fewshot_adaptation_v1",
        False,
        False,
        True,
    ),
}


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    ensure_dir(path.parent)
    rows = list(rows)
    if fieldnames is None:
        keys: list[str] = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    keys.append(key)
                    seen.add(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def sha1_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_u64(*parts: Any) -> int:
    joined = "\x1f".join(str(p) for p in parts)
    digest = hashlib.blake2b(joined.encode("utf-8"), digest_size=8, person=b"ckajv001").digest()
    return int.from_bytes(digest, "big", signed=False)


def stable_hex(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def parse_timestamp(value: str) -> float | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), TIMESTAMP_FORMAT).timestamp()
    except Exception:
        return None


def parse_label(value: str) -> int | None:
    text = str(value).strip()
    if text in {"0", "0.0"}:
        return 0
    if text in {"1", "1.0"}:
        return 1
    return None


def is_missing(value: str) -> bool:
    return str(value).strip() == ""


def numeric_value(value: str) -> float | None:
    if is_missing(value):
        return None
    try:
        return float(value)
    except Exception:
        return None


def push_smallest(heap: list[tuple[int, int]], limit: int, key: int, row_id: int) -> None:
    """Keep the `limit` rows with smallest key in a max-heap via negative key."""
    if limit <= 0:
        return
    item = (-int(key), int(row_id))
    if len(heap) < limit:
        heapq.heappush(heap, item)
        return
    if item > heap[0]:
        heapq.heapreplace(heap, item)


def selected_order_from_heap(heap: list[tuple[int, int]]) -> list[int]:
    pairs = [(-neg_key, row_id) for neg_key, row_id in heap]
    pairs.sort()
    return [row_id for _, row_id in pairs]


def attack_train_cap(n: int) -> int:
    if n <= 0:
        return 0
    return int(min(256, max(8, math.ceil(0.02 * n))))


def attack_val_cap(n: int, train_n: int) -> int:
    remain = max(0, n - train_n)
    if remain <= 0:
        return 0
    return int(min(128, max(4, math.ceil(0.01 * n), min(8, remain))))


def attack_query_cap(n: int, train_n: int, val_n: int) -> int:
    remain = max(0, n - train_n - val_n)
    if remain <= 0:
        return 0
    return int(min(512, max(16, math.ceil(0.02 * n), min(32, remain))))


def benign_fit_cap(n: int) -> int:
    return int(min(20000, max(0, n // 20)))


def benign_select_cap(n: int, fit_n: int) -> int:
    return int(min(20000, max(0, n - fit_n, min(20000, n - fit_n))))


def read_header(csv_path: Path) -> list[str]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def audit_first_pass(csv_path: Path, *, chunk_log: int) -> dict[str, Any]:
    started = time.time()
    fieldnames = read_header(csv_path)
    numeric_cols = [c for c in fieldnames if c not in ID_COLUMNS]
    label_counts: Counter[str] = Counter()
    attack_counts: Counter[str] = Counter()
    protocol_counts: Counter[str] = Counter()
    src_counts: Counter[str] = Counter()
    dst_counts: Counter[str] = Counter()
    date_counts: Counter[str] = Counter()
    label_attack_counts: Counter[tuple[str, str]] = Counter()
    null_counts: Counter[str] = Counter()
    invalid_numeric_counts: Counter[str] = Counter()
    nonfinite_counts: Counter[str] = Counter()
    numeric_min: dict[str, float] = {c: math.inf for c in numeric_cols}
    numeric_max: dict[str, float] = {c: -math.inf for c in numeric_cols}
    numeric_seen: Counter[str] = Counter()
    row_count = 0
    parse_label_fail = 0
    parse_timestamp_fail = 0
    timestamp_monotonic_violations = 0
    prior_ts: float | None = None
    first_timestamp: str | None = None
    last_timestamp: str | None = None
    min_ts: float | None = None
    max_ts: float | None = None
    flow_hashes: set[int] = set()
    duplicate_flow_hashes = 0
    source_ips: set[str] = set()
    dest_ips: set[str] = set()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            row_count += 1
            raw_label = str(row.get("Label", "")).strip()
            raw_attack = str(row.get("Attack", "")).strip()
            raw_protocol = str(row.get("Protocol", "")).strip()
            label_counts[raw_label] += 1
            attack_counts[raw_attack] += 1
            protocol_counts[raw_protocol] += 1
            label_attack_counts[(raw_label, raw_attack)] += 1
            src = str(row.get("Src IP", "")).strip()
            dst = str(row.get("Dst IP", "")).strip()
            if src:
                source_ips.add(src)
                src_counts[src] += 1
            if dst:
                dest_ips.add(dst)
                dst_counts[dst] += 1
            label = parse_label(raw_label)
            if label is None:
                parse_label_fail += 1
            ts_text = str(row.get("Timestamp", "")).strip()
            if first_timestamp is None:
                first_timestamp = ts_text
            last_timestamp = ts_text
            ts = parse_timestamp(ts_text)
            if ts is None:
                parse_timestamp_fail += 1
            else:
                date_counts[datetime.fromtimestamp(ts).strftime("%Y-%m-%d")] += 1
                min_ts = ts if min_ts is None else min(min_ts, ts)
                max_ts = ts if max_ts is None else max(max_ts, ts)
                if prior_ts is not None and ts < prior_ts:
                    timestamp_monotonic_violations += 1
                prior_ts = ts
            flow_id = str(row.get("Flow ID", "")).strip()
            if flow_id:
                fh = stable_u64("flow_id", flow_id)
                if fh in flow_hashes:
                    duplicate_flow_hashes += 1
                else:
                    flow_hashes.add(fh)
            for col in numeric_cols:
                value = str(row.get(col, ""))
                if is_missing(value):
                    null_counts[col] += 1
                    continue
                parsed = numeric_value(value)
                if parsed is None:
                    invalid_numeric_counts[col] += 1
                    continue
                if not math.isfinite(parsed):
                    nonfinite_counts[col] += 1
                    continue
                numeric_seen[col] += 1
                if parsed < numeric_min[col]:
                    numeric_min[col] = parsed
                if parsed > numeric_max[col]:
                    numeric_max[col] = parsed
            if chunk_log and row_count % chunk_log == 0:
                print(f"[audit] rows={row_count}", file=sys.stderr, flush=True)

    numeric_rows = []
    for col in numeric_cols:
        seen = int(numeric_seen[col])
        numeric_rows.append(
            {
                "column": col,
                "seen_numeric": seen,
                "null_count": int(null_counts[col]),
                "invalid_numeric_count": int(invalid_numeric_counts[col]),
                "nonfinite_count": int(nonfinite_counts[col]),
                "min": "" if seen == 0 else numeric_min[col],
                "max": "" if seen == 0 else numeric_max[col],
            }
        )

    seconds = time.time() - started
    return {
        "fieldnames": fieldnames,
        "numeric_cols": numeric_cols,
        "row_count": row_count,
        "label_counts": label_counts,
        "attack_counts": attack_counts,
        "protocol_counts": protocol_counts,
        "src_counts": src_counts,
        "dst_counts": dst_counts,
        "date_counts": date_counts,
        "label_attack_counts": label_attack_counts,
        "numeric_rows": numeric_rows,
        "source_ip_count": len(source_ips),
        "dest_ip_count": len(dest_ips),
        "duplicate_flow_hashes": duplicate_flow_hashes,
        "unique_flow_hashes": len(flow_hashes),
        "parse_label_fail": parse_label_fail,
        "parse_timestamp_fail": parse_timestamp_fail,
        "timestamp_monotonic_violations": timestamp_monotonic_violations,
        "timestamp_monotonic_violation_rate": timestamp_monotonic_violations / max(1, row_count - 1),
        "first_timestamp_in_file": first_timestamp or "",
        "last_timestamp_in_file": last_timestamp or "",
        "min_timestamp_epoch": "" if min_ts is None else min_ts,
        "max_timestamp_epoch": "" if max_ts is None else max_ts,
        "seconds": seconds,
    }


def build_split_plan(label_counts: Counter[str], attack_counts: Counter[str]) -> dict[str, Any]:
    benign_n = int(label_counts.get("0", 0))
    benign_fit = benign_fit_cap(benign_n)
    benign_select = benign_select_cap(benign_n, benign_fit)
    attack_caps: dict[str, dict[str, int]] = {}
    for attack, n in sorted(attack_counts.items()):
        if attack.lower() == "benign":
            continue
        train = attack_train_cap(int(n))
        val = attack_val_cap(int(n), train)
        query = attack_query_cap(int(n), train, val)
        attack_caps[attack] = {
            "rows": int(n),
            "support_train_cap": train,
            "support_val_cap": val,
            "query_report_cap": query,
            "selected_cap_total": train + val + query,
        }
    return {
        "seed": SEED,
        "benign": {
            "rows": benign_n,
            "id_fit_cap": benign_fit,
            "id_select_cap": benign_select,
            "selected_cap_total": benign_fit + benign_select,
        },
        "attack_by_family": attack_caps,
        "rules": [
            "zero_shot_external_protocol: all CIC-ToN-IoT rows are report-only when no CIC rows are used for fit/threshold.",
            "fewshot_adaptation_v1: only id_benign_fit and support_attack_train are fit-allowed.",
            "fewshot_adaptation_v1: only id_benign_select and support_attack_val are threshold/select-allowed.",
            "attack_query_report, sealed_benign_report, and sealed_attack_report are report-only.",
            "row assignment is deterministic by blake2b hash over seed, row_id, Flow ID, Timestamp, Label, and Attack.",
            "labels are used only to construct explicitly allowed fit/select roles and final evaluation roles.",
        ],
    }


def support_coverage_rows(split_counts: list[dict[str, Any]], split_plan: dict[str, Any]) -> list[dict[str, Any]]:
    by_family_role: Counter[tuple[str, str]] = Counter()
    for row in split_counts:
        family = str(row["attack_family"])
        role = str(row["role"])
        if family.lower() == "benign":
            continue
        by_family_role[(family, role)] += int(row["rows"])
    rows: list[dict[str, Any]] = []
    for family, spec in sorted(split_plan["attack_by_family"].items()):
        total = int(spec["rows"])
        support_train = int(by_family_role[(family, "support_attack_train")])
        support_val = int(by_family_role[(family, "support_attack_val")])
        query = int(by_family_role[(family, "attack_query_report")])
        sealed = int(by_family_role[(family, "sealed_attack_report")])
        support_total = support_train + support_val
        selected_total = support_total + query
        if support_train >= 32 and support_val >= 16 and sealed >= 100:
            grade = "good_for_first_smoke"
        elif support_train >= 8 and support_val >= 8 and sealed >= 50:
            grade = "rare_family_minimal_but_present"
        else:
            grade = "too_sparse_for_stable_family_claim"
        rows.append(
            {
                "attack_family": family,
                "total_rows": total,
                "support_train_rows": support_train,
                "support_val_rows": support_val,
                "attack_query_report_rows": query,
                "sealed_attack_report_rows": sealed,
                "support_total_rows": support_total,
                "selected_nonsealed_rows": selected_total,
                "support_train_fraction": support_train / max(1, total),
                "support_val_fraction": support_val / max(1, total),
                "sealed_fraction": sealed / max(1, total),
                "coverage_grade": grade,
                "note": (
                    "Few-shot cap by design; coverage means every attack family has nonzero train/val/query/sealed rows, "
                    "not that support exhausts the family distribution."
                ),
            }
        )
    return rows


def protocol_role_map_rows() -> list[dict[str, Any]]:
    return [
        {
            "experiment_protocol": "gotham_to_cic_zero_shot_external",
            "current_manifest_role": "ALL Label=0 rows",
            "semantic_role": "external_ood_benign_report",
            "fit_allowed": 0,
            "threshold_allowed": 0,
            "report_only": 1,
            "reason": "When the detector is trained only on Gotham, all CIC-ToN-IoT benign traffic is external benign/OOD relative to the training environment.",
        },
        {
            "experiment_protocol": "gotham_to_cic_zero_shot_external",
            "current_manifest_role": "ALL Label=1 rows",
            "semantic_role": "external_attack_report",
            "fit_allowed": 0,
            "threshold_allowed": 0,
            "report_only": 1,
            "reason": "Zero-shot external validation must not use CIC attack labels for support, thresholds, feature selection, or cleanup.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "id_benign_fit",
            "semantic_role": "cic_id_benign_fit",
            "fit_allowed": 1,
            "threshold_allowed": 0,
            "report_only": 0,
            "reason": "This is a CIC-internal adaptation role, not external OOD evidence.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "id_benign_select",
            "semantic_role": "cic_id_benign_select",
            "fit_allowed": 0,
            "threshold_allowed": 1,
            "report_only": 0,
            "reason": "Selection/calibration only; not fit.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "support_attack_train",
            "semantic_role": "cic_attack_support_fit",
            "fit_allowed": 1,
            "threshold_allowed": 0,
            "report_only": 0,
            "reason": "Few-shot support; kept family-capped and disjoint from query/sealed.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "support_attack_val",
            "semantic_role": "cic_attack_support_select",
            "fit_allowed": 0,
            "threshold_allowed": 1,
            "report_only": 0,
            "reason": "Support threshold/select only; not fit.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "sealed_benign_report",
            "semantic_role": "cic_heldout_benign_report",
            "fit_allowed": 0,
            "threshold_allowed": 0,
            "report_only": 1,
            "reason": "Held-out benign within CIC. It is not automatically internal OOD unless a separate domain-holdout split is defined.",
        },
        {
            "experiment_protocol": "cic_fewshot_adaptation",
            "current_manifest_role": "sealed_attack_report",
            "semantic_role": "cic_heldout_attack_report",
            "fit_allowed": 0,
            "threshold_allowed": 0,
            "report_only": 1,
            "reason": "Final CIC attack report-only rows.",
        },
    ]


def sanitizer_policy_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "issue": "nonfinite_numeric_values",
            "affected_columns": ";".join(
                str(r["column"]) for r in audit["numeric_rows"] if int(r["nonfinite_count"]) > 0
            ),
            "observed": sum(int(r["nonfinite_count"]) for r in audit["numeric_rows"]),
            "required_loader_action": "replace +inf/-inf with NaN, then impute using fit-only column statistics; persist imputer parameters.",
            "forbidden_action": "using report/sealed rows to choose imputation values or clipping quantiles.",
        },
        {
            "issue": "negative_rate_like_values",
            "affected_columns": ";".join(
                str(r["column"])
                for r in audit["numeric_rows"]
                if r["min"] != "" and float(r["min"]) < 0 and ("/s" in str(r["column"]) or "Rate" in str(r["column"]))
            ),
            "observed": "min<0",
            "required_loader_action": "do not silently trust rate signs; keep raw value for audit and create sanitized model value by fit-only clipping/winsorization.",
            "forbidden_action": "dropping rows based on report/sealed labels or manually editing labels.",
        },
        {
            "issue": "timestamp_file_order_not_monotonic",
            "affected_columns": "Timestamp",
            "observed": audit["timestamp_monotonic_violations"],
            "required_loader_action": "do not treat CSV row order as chronological order; if temporal experiments are needed, sort within allowed split only and never use future/report labels.",
            "forbidden_action": "creating temporal context across fit/select/report boundaries.",
        },
        {
            "issue": "flow_id_not_unique",
            "affected_columns": "Flow ID",
            "observed": audit["duplicate_flow_hashes"],
            "required_loader_action": "use row_id plus role_manifest as stable primary key; Flow ID is an audit field only.",
            "forbidden_action": "joining predictions/labels by Flow ID alone.",
        },
    ]
    return rows


def collect_selected_rows(csv_path: Path, split_plan: dict[str, Any], *, chunk_log: int) -> dict[str, set[int]]:
    started = time.time()
    benign_total = int(split_plan["benign"]["selected_cap_total"])
    benign_heap: list[tuple[int, int]] = []
    attack_heaps: dict[str, list[tuple[int, int]]] = defaultdict(list)
    attack_limits = {
        attack: int(spec["selected_cap_total"])
        for attack, spec in split_plan["attack_by_family"].items()
    }
    row_count = 0
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row_id, row in enumerate(reader):
            row_count += 1
            raw_label = str(row.get("Label", "")).strip()
            attack = str(row.get("Attack", "")).strip()
            key = stable_u64(
                SEED,
                row_id,
                row.get("Flow ID", ""),
                row.get("Timestamp", ""),
                raw_label,
                attack,
            )
            if raw_label == "0":
                push_smallest(benign_heap, benign_total, key, row_id)
            elif raw_label == "1" and attack in attack_limits:
                push_smallest(attack_heaps[attack], attack_limits[attack], key, row_id)
            if chunk_log and row_count % chunk_log == 0:
                print(f"[select] rows={row_count}", file=sys.stderr, flush=True)

    selected: dict[str, set[int]] = {
        "id_benign_fit": set(),
        "id_benign_select": set(),
        "support_attack_train": set(),
        "support_attack_val": set(),
        "attack_query_report": set(),
    }
    benign_order = selected_order_from_heap(benign_heap)
    benign_fit = int(split_plan["benign"]["id_fit_cap"])
    benign_select = int(split_plan["benign"]["id_select_cap"])
    selected["id_benign_fit"].update(benign_order[:benign_fit])
    selected["id_benign_select"].update(benign_order[benign_fit : benign_fit + benign_select])
    for attack, heap in attack_heaps.items():
        order = selected_order_from_heap(heap)
        spec = split_plan["attack_by_family"][attack]
        train = int(spec["support_train_cap"])
        val = int(spec["support_val_cap"])
        query = int(spec["query_report_cap"])
        selected["support_attack_train"].update(order[:train])
        selected["support_attack_val"].update(order[train : train + val])
        selected["attack_query_report"].update(order[train + val : train + val + query])
    print(f"[select] seconds={time.time() - started:.1f}", file=sys.stderr, flush=True)
    return selected


def role_for_row(row_id: int, label: str, selected: dict[str, set[int]]) -> str:
    if row_id in selected["id_benign_fit"]:
        return "id_benign_fit"
    if row_id in selected["id_benign_select"]:
        return "id_benign_select"
    if row_id in selected["support_attack_train"]:
        return "support_attack_train"
    if row_id in selected["support_attack_val"]:
        return "support_attack_val"
    if row_id in selected["attack_query_report"]:
        return "attack_query_report"
    if str(label).strip() == "0":
        return "sealed_benign_report"
    return "sealed_attack_report"


def write_manifest_and_indices(
    csv_path: Path,
    selected: dict[str, set[int]],
    out: Path,
    *,
    chunk_log: int,
    preview_cap: int,
) -> tuple[list[dict[str, Any]], dict[str, list[int]]]:
    started = time.time()
    manifest_path = out / "role_manifest.csv.gz"
    split_counts: Counter[tuple[str, str, str, str]] = Counter()
    role_indices: dict[str, list[int]] = defaultdict(list)
    preview_rows: list[dict[str, Any]] = []
    row_count = 0
    with gzip.open(manifest_path, "wt", newline="", encoding="utf-8") as f:
        fieldnames = [
            "row_id",
            "role",
            "phase",
            "role_kind",
            "protocol",
            "fit_allowed",
            "threshold_allowed",
            "report_only",
            "label_binary",
            "attack_family",
            "timestamp",
            "protocol_number",
            "src_ip_sha16",
            "dst_ip_sha16",
            "flow_id_sha16",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        with csv_path.open("r", encoding="utf-8-sig", newline="") as src:
            reader = csv.DictReader(src)
            for row_id, row in enumerate(reader):
                row_count += 1
                label = str(row.get("Label", "")).strip()
                attack = str(row.get("Attack", "")).strip()
                role = role_for_row(row_id, label, selected)
                spec = ROLE_SPECS[role]
                out_row = {
                    "row_id": row_id,
                    "role": role,
                    "phase": spec.phase,
                    "role_kind": spec.role_kind,
                    "protocol": spec.protocol,
                    "fit_allowed": int(spec.fit_allowed),
                    "threshold_allowed": int(spec.threshold_allowed),
                    "report_only": int(spec.report_only),
                    "label_binary": label,
                    "attack_family": attack,
                    "timestamp": str(row.get("Timestamp", "")).strip(),
                    "protocol_number": str(row.get("Protocol", "")).strip(),
                    "src_ip_sha16": stable_hex(str(row.get("Src IP", "")).strip()),
                    "dst_ip_sha16": stable_hex(str(row.get("Dst IP", "")).strip()),
                    "flow_id_sha16": stable_hex(str(row.get("Flow ID", "")).strip()),
                }
                writer.writerow(out_row)
                role_indices[role].append(row_id)
                split_counts[(role, spec.phase, spec.role_kind, attack)] += 1
                if len(preview_rows) < preview_cap:
                    preview_rows.append(out_row)
                if chunk_log and row_count % chunk_log == 0:
                    print(f"[manifest] rows={row_count}", file=sys.stderr, flush=True)

    npz_payload = {role: np.asarray(indices, dtype=np.int64) for role, indices in role_indices.items()}
    np.savez_compressed(out / "role_indices.npz", **npz_payload)
    write_csv(out / "role_manifest_preview.csv", preview_rows)
    rows = [
        {
            "role": role,
            "phase": phase,
            "role_kind": kind,
            "attack_family": attack,
            "rows": count,
        }
        for (role, phase, kind, attack), count in sorted(split_counts.items())
    ]
    print(f"[manifest] seconds={time.time() - started:.1f}", file=sys.stderr, flush=True)
    return rows, role_indices


def write_dataset_card(
    out: Path,
    csv_path: Path,
    raw_zip: Path,
    audit: dict[str, Any],
    split_counts: list[dict[str, Any]],
    split_plan: dict[str, Any],
    seconds: float,
) -> None:
    lines = [
        "# issue27ckaj CIC-ToN-IoT external dataset intake v1",
        "",
        "## Purpose",
        "",
        "Freeze a clean, independent second-dataset intake layer before any model training.",
        "",
        "## Source",
        "",
        f"- Dataset: CIC-ToN-IoT, University of Queensland RDM `{DATASET_UUID}`.",
        "- Format: CICFlowMeter-style CSV with 83 network features plus label fields.",
        f"- Local CSV: `{csv_path}`.",
        f"- Local raw zip: `{raw_zip}`.",
        "",
        "## Basic audit",
        "",
        f"- Rows: `{audit['row_count']}`.",
        f"- Columns: `{len(audit['fieldnames'])}`.",
        f"- Numeric feature columns audited: `{len(audit['numeric_cols'])}`.",
        f"- Label parse failures: `{audit['parse_label_fail']}`.",
        f"- Timestamp parse failures: `{audit['parse_timestamp_fail']}`.",
        f"- Timestamp monotonic violation rate in file order: `{audit['timestamp_monotonic_violation_rate']:.6f}`.",
        f"- Source IP count: `{audit['source_ip_count']}`.",
        f"- Destination IP count: `{audit['dest_ip_count']}`.",
        f"- Duplicate Flow ID hash count: `{audit['duplicate_flow_hashes']}`.",
        "",
        "## Data-use contract",
        "",
        "- There is no native OOD label in CIC-ToN-IoT. OOD is protocol-relative:",
        "  - Gotham-to-CIC zero-shot: CIC benign rows are external OOD benign report rows.",
        "  - CIC few-shot/adaptation: held-out benign rows are held-out benign, not automatically OOD.",
        "- Zero-shot external protocol: all rows are report-only when the model is trained only on Gotham.",
        "- Few-shot/adaptation protocol: only `id_benign_fit` and `support_attack_train` are fit-allowed.",
        "- Threshold/selection may only use `id_benign_select` and `support_attack_val`.",
        "- `attack_query_report`, `sealed_benign_report`, and `sealed_attack_report` are report-only.",
        "- Report/sealed rows must not be used for training, thresholding, feature selection, cleaning-rule tuning, or hyperparameter search.",
        "",
        "## Split summary",
        "",
        "| role | phase | role_kind | rows |",
        "|---|---|---|---:|",
    ]
    by_role: Counter[tuple[str, str, str]] = Counter()
    for row in split_counts:
        by_role[(row["role"], row["phase"], row["role_kind"])] += int(row["rows"])
    for (role, phase, kind), count in sorted(by_role.items()):
        lines.append(f"| {role} | {phase} | {kind} | {count} |")
    lines.extend(
        [
            "",
            "## Files produced",
            "",
            "- `dataset_audit.json`",
            "- `label_counts.csv`",
            "- `attack_counts.csv`",
            "- `protocol_counts.csv`",
            "- `numeric_column_audit.csv`",
            "- `split_policy.json`",
            "- `split_counts.csv`",
            "- `role_manifest.csv.gz`",
        "- `role_indices.npz`",
        "- `role_manifest_preview.csv`",
        "- `support_coverage_audit.csv`",
        "- `protocol_role_map.csv`",
        "- `loader_sanitizer_policy.csv`",
        "",
        f"Runtime seconds: `{seconds:.1f}`.",
        ]
    )
    (out / "dataset_card.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = Path(args.out)
    ensure_dir(out)
    csv_path = Path(args.csv)
    raw_zip = Path(args.raw_zip)
    feature_doc = Path(args.feature_doc)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)
    if not raw_zip.exists():
        raise FileNotFoundError(raw_zip)
    if not feature_doc.exists():
        raise FileNotFoundError(feature_doc)

    print(f"[ckaj] csv={csv_path}", file=sys.stderr)
    print(f"[ckaj] out={out}", file=sys.stderr)
    csv_sha1 = sha1_file(csv_path)
    zip_sha256 = sha256_file(raw_zip)
    audit = audit_first_pass(csv_path, chunk_log=int(args.chunk_log))
    split_plan = build_split_plan(audit["label_counts"], audit["attack_counts"])
    selected = collect_selected_rows(csv_path, split_plan, chunk_log=int(args.chunk_log))
    split_counts, role_indices = write_manifest_and_indices(
        csv_path,
        selected,
        out,
        chunk_log=int(args.chunk_log),
        preview_cap=int(args.preview_cap),
    )
    label_rows = [
        {"label": k, "rows": v}
        for k, v in sorted(audit["label_counts"].items(), key=lambda kv: str(kv[0]))
    ]
    attack_rows = [
        {"attack_family": k, "rows": v}
        for k, v in sorted(audit["attack_counts"].items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]
    protocol_rows = [
        {"protocol": k, "rows": v}
        for k, v in sorted(audit["protocol_counts"].items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]
    date_rows = [
        {"date": k, "rows": v}
        for k, v in sorted(audit["date_counts"].items(), key=lambda kv: str(kv[0]))
    ]
    label_attack_rows = [
        {"label": label, "attack_family": attack, "rows": rows}
        for (label, attack), rows in sorted(audit["label_attack_counts"].items(), key=lambda kv: (-kv[1], str(kv[0])))
    ]
    top_src_rows = [
        {"src_ip_sha16": stable_hex(k), "rows": v}
        for k, v in audit["src_counts"].most_common(50)
    ]
    top_dst_rows = [
        {"dst_ip_sha16": stable_hex(k), "rows": v}
        for k, v in audit["dst_counts"].most_common(50)
    ]
    support_rows = support_coverage_rows(split_counts, split_plan)
    protocol_rows_for_roles = protocol_role_map_rows()
    sanitizer_rows = sanitizer_policy_rows(audit)

    write_csv(out / "label_counts.csv", label_rows)
    write_csv(out / "attack_counts.csv", attack_rows)
    write_csv(out / "protocol_counts.csv", protocol_rows)
    write_csv(out / "date_counts.csv", date_rows)
    write_csv(out / "label_attack_counts.csv", label_attack_rows)
    write_csv(out / "top_src_ip_hash_counts.csv", top_src_rows)
    write_csv(out / "top_dst_ip_hash_counts.csv", top_dst_rows)
    write_csv(out / "numeric_column_audit.csv", audit["numeric_rows"])
    write_csv(out / "split_counts.csv", split_counts)
    write_csv(out / "support_coverage_audit.csv", support_rows)
    write_csv(out / "protocol_role_map.csv", protocol_rows_for_roles)
    write_csv(out / "loader_sanitizer_policy.csv", sanitizer_rows)
    write_json(out / "split_policy.json", split_plan)
    seconds = time.time() - started
    dataset_audit = {
        "issue": ISSUE,
        "dataset": "CIC-ToN-IoT",
        "dataset_uuid": DATASET_UUID,
        "source": {
            "uq_rdm": f"https://rdm.uq.edu.au/files/{DATASET_UUID}",
            "uq_espace": "https://espace.library.uq.edu.au/view/UQ%3Af6884ce",
        },
        "local_paths": {
            "csv": str(csv_path),
            "raw_zip": str(raw_zip),
            "feature_doc": str(feature_doc),
            "out": str(out),
        },
        "hashes": {
            "csv_sha1": csv_sha1,
            "raw_zip_sha256": zip_sha256,
        },
        "row_count": audit["row_count"],
        "column_count": len(audit["fieldnames"]),
        "fieldnames": audit["fieldnames"],
        "numeric_feature_columns": audit["numeric_cols"],
        "label_counts": dict(audit["label_counts"]),
        "attack_counts": dict(audit["attack_counts"]),
        "protocol_counts": dict(audit["protocol_counts"]),
        "source_ip_count": audit["source_ip_count"],
        "dest_ip_count": audit["dest_ip_count"],
        "unique_flow_hashes": audit["unique_flow_hashes"],
        "duplicate_flow_hashes": audit["duplicate_flow_hashes"],
        "parse_label_fail": audit["parse_label_fail"],
        "parse_timestamp_fail": audit["parse_timestamp_fail"],
        "timestamp_monotonic_violations": audit["timestamp_monotonic_violations"],
        "timestamp_monotonic_violation_rate": audit["timestamp_monotonic_violation_rate"],
        "first_timestamp_in_file": audit["first_timestamp_in_file"],
        "last_timestamp_in_file": audit["last_timestamp_in_file"],
        "min_timestamp_epoch": audit["min_timestamp_epoch"],
        "max_timestamp_epoch": audit["max_timestamp_epoch"],
        "role_index_counts": {role: len(indices) for role, indices in sorted(role_indices.items())},
        "support_coverage_audit": support_rows,
        "protocol_role_map": protocol_rows_for_roles,
        "loader_sanitizer_policy": sanitizer_rows,
        "data_use_contract": {
            "native_ood_label_available": False,
            "zero_shot_cic_benign_semantic_role": "external_ood_benign_report",
            "fewshot_cic_heldout_benign_semantic_role": "cic_heldout_benign_report",
            "zero_shot_external_all_rows_report_only": True,
            "fewshot_fit_roles": ["id_benign_fit", "support_attack_train"],
            "fewshot_threshold_roles": ["id_benign_select", "support_attack_val"],
            "report_only_roles": ["attack_query_report", "sealed_benign_report", "sealed_attack_report"],
            "report_or_sealed_used_for_training_threshold_feature_selection": False,
        },
        "seconds": seconds,
    }
    write_json(out / "dataset_audit.json", dataset_audit)
    write_dataset_card(out, csv_path, raw_zip, audit, split_counts, split_plan, seconds)
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--raw-zip", default=str(DEFAULT_RAW_ZIP))
    parser.add_argument("--feature-doc", default=str(DEFAULT_FEATURE_DOC))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--chunk-log", type=int, default=500000)
    parser.add_argument("--preview-cap", type=int, default=200)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
