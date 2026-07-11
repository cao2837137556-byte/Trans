"""issue27ckam: ToN-IoT Bro/GroundTruth schema and alignment audit v1.

This script is an A0/A1 precondition audit.  It does not train, tune, select a
model, or score a detector.

It checks whether the downloaded ToN-IoT Route-A minimum package is usable:

* Bro/Zeek conn.log schema and timestamp integrity;
* SecurityEvents_Network groundtruth schema and label/type counts;
* coarse time-window overlap between groundtruth files and Bro conn logs.

All outputs are evidence for loader/frontend readiness only.  They must not be
used as model performance evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ISSUE = "issue27ckam_toniot_bro_groundtruth_schema_audit_v1_2026-07-09"
WORKTREE = Path(__file__).resolve().parents[2]
PAPER04 = WORKTREE.parent.parent
DEFAULT_EXTRACTED = PAPER04 / "datasets" / "external" / "ton_iot_raw_network" / "extracted"
DEFAULT_OUT = WORKTREE / "runs" / ISSUE

REQUIRED_CONN_FIELDS = [
    "ts",
    "uid",
    "id.orig_h",
    "id.orig_p",
    "id.resp_h",
    "id.resp_p",
    "proto",
    "service",
    "duration",
    "orig_bytes",
    "resp_bytes",
    "conn_state",
    "orig_pkts",
    "orig_ip_bytes",
    "resp_pkts",
    "resp_ip_bytes",
]

REQUIRED_GT_FIELDS = ["ts", "src_ip", "src_port", "dst_ip", "dst_port", "proto", "type"]


@dataclass
class ConnAudit:
    relative_path: str
    parent_group: str
    scenario_family: str
    scenario_name: str
    row_count: int
    min_ts: float | None
    max_ts: float | None
    first_ts: float | None
    last_ts: float | None
    ts_parse_failures: int
    monotonic_violations: int
    fields: list[str]
    types: list[str]
    missing_required_fields: list[str]


@dataclass
class GroundTruthAudit:
    relative_path: str
    file_id: int | None
    row_count: int
    min_ts: float | None
    max_ts: float | None
    first_ts: float | None
    last_ts: float | None
    ts_parse_failures: int
    monotonic_violations: int
    header: list[str]
    missing_required_fields: list[str]
    type_counts: dict[str, int]


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    ensure_dir(path.parent)
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
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


def parse_float(text: str) -> float | None:
    try:
        value = float(str(text).strip())
        if math.isfinite(value):
            return value
    except Exception:
        return None
    return None


def infer_scenario(path: Path) -> tuple[str, str, str]:
    parts = list(path.parts)
    if "normal_Bro" in parts:
        idx = parts.index("normal_Bro")
        scenario = parts[idx + 1] if idx + 1 < len(parts) else "normal_unknown"
        return "normal_Bro", "normal", scenario
    if "normal_attack_Bro" in parts:
        idx = parts.index("normal_attack_Bro")
        family = parts[idx + 1] if idx + 1 < len(parts) else "attack_unknown"
        scenario = parts[idx + 2] if idx + 2 < len(parts) else family
        return "normal_attack_Bro", family.replace("normal_", ""), scenario
    return "unknown", "unknown", path.parent.name


def parse_zeek_header(path: Path) -> tuple[list[str], list[str]]:
    fields: list[str] = []
    types: list[str] = []
    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            if not line.startswith("#"):
                break
            line = line.rstrip("\r\n")
            if line.startswith("#fields\t"):
                fields = line.split("\t")[1:]
            elif line.startswith("#types\t"):
                types = line.split("\t")[1:]
    return fields, types


def audit_conn_log(path: Path, root: Path) -> ConnAudit:
    fields, types = parse_zeek_header(path)
    ts_idx = fields.index("ts") if "ts" in fields else 0
    row_count = 0
    parse_fail = 0
    mono = 0
    prev_ts: float | None = None
    first_ts: float | None = None
    last_ts: float | None = None
    min_ts: float | None = None
    max_ts: float | None = None

    with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        for line in f:
            if not line or line.startswith("#"):
                continue
            parts = line.rstrip("\r\n").split("\t")
            if ts_idx >= len(parts):
                parse_fail += 1
                continue
            ts = parse_float(parts[ts_idx])
            if ts is None:
                parse_fail += 1
                continue
            row_count += 1
            if first_ts is None:
                first_ts = ts
            if prev_ts is not None and ts < prev_ts:
                mono += 1
            prev_ts = ts
            last_ts = ts
            min_ts = ts if min_ts is None else min(min_ts, ts)
            max_ts = ts if max_ts is None else max(max_ts, ts)

    parent_group, family, scenario = infer_scenario(path)
    return ConnAudit(
        relative_path=str(path.relative_to(root)).replace("\\", "/"),
        parent_group=parent_group,
        scenario_family=family,
        scenario_name=scenario,
        row_count=row_count,
        min_ts=min_ts,
        max_ts=max_ts,
        first_ts=first_ts,
        last_ts=last_ts,
        ts_parse_failures=parse_fail,
        monotonic_violations=mono,
        fields=fields,
        types=types,
        missing_required_fields=[f for f in REQUIRED_CONN_FIELDS if f not in fields],
    )


def file_id_from_name(path: Path) -> int | None:
    stem = path.stem
    suffix = stem.split("_")[-1]
    try:
        return int(suffix)
    except Exception:
        return None


def audit_groundtruth(path: Path, root: Path) -> GroundTruthAudit:
    row_count = 0
    parse_fail = 0
    mono = 0
    prev_ts: float | None = None
    first_ts: float | None = None
    last_ts: float | None = None
    min_ts: float | None = None
    max_ts: float | None = None
    type_counts: Counter[str] = Counter()

    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        for row in reader:
            ts = parse_float(row.get("ts", ""))
            if ts is None:
                parse_fail += 1
            else:
                if first_ts is None:
                    first_ts = ts
                if prev_ts is not None and ts < prev_ts:
                    mono += 1
                prev_ts = ts
                last_ts = ts
                min_ts = ts if min_ts is None else min(min_ts, ts)
                max_ts = ts if max_ts is None else max(max_ts, ts)
            typ = str(row.get("type", "")).strip() or "missing"
            type_counts[typ] += 1
            row_count += 1

    return GroundTruthAudit(
        relative_path=str(path.relative_to(root)).replace("\\", "/"),
        file_id=file_id_from_name(path),
        row_count=row_count,
        min_ts=min_ts,
        max_ts=max_ts,
        first_ts=first_ts,
        last_ts=last_ts,
        ts_parse_failures=parse_fail,
        monotonic_violations=mono,
        header=header,
        missing_required_fields=[f for f in REQUIRED_GT_FIELDS if f not in header],
        type_counts=dict(sorted(type_counts.items())),
    )


def overlap_seconds(a0: float | None, a1: float | None, b0: float | None, b1: float | None) -> float:
    if a0 is None or a1 is None or b0 is None or b1 is None:
        return 0.0
    return max(0.0, min(a1, b1) - max(a0, b0))


def dict_conn(a: ConnAudit) -> dict[str, Any]:
    return {
        "relative_path": a.relative_path,
        "parent_group": a.parent_group,
        "scenario_family": a.scenario_family,
        "scenario_name": a.scenario_name,
        "row_count": a.row_count,
        "min_ts": a.min_ts,
        "max_ts": a.max_ts,
        "first_ts": a.first_ts,
        "last_ts": a.last_ts,
        "ts_parse_failures": a.ts_parse_failures,
        "monotonic_violations": a.monotonic_violations,
        "field_count": len(a.fields),
        "fields": "|".join(a.fields),
        "types": "|".join(a.types),
        "missing_required_fields": "|".join(a.missing_required_fields),
    }


def dict_gt(a: GroundTruthAudit) -> dict[str, Any]:
    return {
        "relative_path": a.relative_path,
        "file_id": a.file_id,
        "row_count": a.row_count,
        "min_ts": a.min_ts,
        "max_ts": a.max_ts,
        "first_ts": a.first_ts,
        "last_ts": a.last_ts,
        "ts_parse_failures": a.ts_parse_failures,
        "monotonic_violations": a.monotonic_violations,
        "field_count": len(a.header),
        "header": "|".join(a.header),
        "missing_required_fields": "|".join(a.missing_required_fields),
        "type_counts_json": json.dumps(a.type_counts, ensure_ascii=False, sort_keys=True),
    }


def build_overlap_rows(conn_rows: list[ConnAudit], gt_rows: list[GroundTruthAudit], top_k: int = 8) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for gt in gt_rows:
        scored: list[tuple[float, ConnAudit]] = []
        for conn in conn_rows:
            ov = overlap_seconds(gt.min_ts, gt.max_ts, conn.min_ts, conn.max_ts)
            if ov > 0:
                scored.append((ov, conn))
        scored.sort(key=lambda item: item[0], reverse=True)
        for rank, (ov, conn) in enumerate(scored[:top_k], start=1):
            rows.append(
                {
                    "groundtruth_file": gt.relative_path,
                    "groundtruth_file_id": gt.file_id,
                    "gt_rows": gt.row_count,
                    "gt_min_ts": gt.min_ts,
                    "gt_max_ts": gt.max_ts,
                    "gt_types": json.dumps(gt.type_counts, ensure_ascii=False, sort_keys=True),
                    "rank": rank,
                    "overlap_seconds": ov,
                    "conn_file": conn.relative_path,
                    "conn_parent_group": conn.parent_group,
                    "conn_family": conn.scenario_family,
                    "conn_scenario": conn.scenario_name,
                    "conn_rows": conn.row_count,
                    "conn_min_ts": conn.min_ts,
                    "conn_max_ts": conn.max_ts,
                }
            )
    return rows


def summarize(conn_rows: list[ConnAudit], gt_rows: list[GroundTruthAudit], runtime_sec: float) -> dict[str, Any]:
    conn_family_rows: Counter[str] = Counter()
    conn_family_files: Counter[str] = Counter()
    conn_missing: Counter[str] = Counter()
    for row in conn_rows:
        conn_family_rows[row.scenario_family] += row.row_count
        conn_family_files[row.scenario_family] += 1
        for field in row.missing_required_fields:
            conn_missing[field] += 1

    gt_type_rows: Counter[str] = Counter()
    gt_missing: Counter[str] = Counter()
    for row in gt_rows:
        gt_type_rows.update(row.type_counts)
        for field in row.missing_required_fields:
            gt_missing[field] += 1

    conn_ts_min = min([r.min_ts for r in conn_rows if r.min_ts is not None], default=None)
    conn_ts_max = max([r.max_ts for r in conn_rows if r.max_ts is not None], default=None)
    gt_ts_min = min([r.min_ts for r in gt_rows if r.min_ts is not None], default=None)
    gt_ts_max = max([r.max_ts for r in gt_rows if r.max_ts is not None], default=None)

    critical_pass = (
        bool(conn_rows)
        and bool(gt_rows)
        and not conn_missing
        and not gt_missing
        and conn_ts_min is not None
        and conn_ts_max is not None
        and gt_ts_min is not None
        and gt_ts_max is not None
    )
    return {
        "issue": ISSUE,
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "conn_log_files": len(conn_rows),
        "conn_total_rows": sum(r.row_count for r in conn_rows),
        "conn_family_files": dict(sorted(conn_family_files.items())),
        "conn_family_rows": dict(sorted(conn_family_rows.items())),
        "conn_missing_required_fields": dict(sorted(conn_missing.items())),
        "conn_ts_min": conn_ts_min,
        "conn_ts_max": conn_ts_max,
        "conn_monotonic_violations_total": sum(r.monotonic_violations for r in conn_rows),
        "conn_ts_parse_failures_total": sum(r.ts_parse_failures for r in conn_rows),
        "groundtruth_files": len(gt_rows),
        "groundtruth_total_rows": sum(r.row_count for r in gt_rows),
        "groundtruth_type_rows": dict(sorted(gt_type_rows.items())),
        "groundtruth_missing_required_fields": dict(sorted(gt_missing.items())),
        "groundtruth_ts_min": gt_ts_min,
        "groundtruth_ts_max": gt_ts_max,
        "groundtruth_monotonic_violations_total": sum(r.monotonic_violations for r in gt_rows),
        "groundtruth_ts_parse_failures_total": sum(r.ts_parse_failures for r in gt_rows),
        "critical_schema_pass": critical_pass,
        "runtime_sec": round(runtime_sec, 3),
        "next_gate": "A1_frontend_parity_smoke" if critical_pass else "BLOCKED_SCHEMA_OR_TIME_AUDIT",
    }


def build_report(summary: dict[str, Any]) -> str:
    return f"""# issue27ckam ToN-IoT Bro/GroundTruth schema audit

Generated: `{summary['generated_at_utc']}`

## Gate

```text
{summary['next_gate']}
```

Critical schema pass:

```text
{summary['critical_schema_pass']}
```

## Main counts

```json
{json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True)}
```

## Interpretation boundary

This is not a detector result.  It only says whether the Route-A external
dataset can proceed into frontend parity and label/time alignment work.

No ToN-IoT rows are used for model fitting, thresholding, or feature selection
by this script.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extracted", type=Path, default=DEFAULT_EXTRACTED)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    t0 = time.time()
    root = args.extracted
    out = args.out
    ensure_dir(out)

    conn_paths = sorted((root / "Network_dataset_Bro").rglob("conn.log"))
    gt_paths = sorted((root / "SecurityEvents_Network_datasets").glob("GroundTruth_Network_*.csv"))

    conn_rows = [audit_conn_log(path, root) for path in conn_paths]
    gt_rows = [audit_groundtruth(path, root) for path in gt_paths]
    overlap_rows = build_overlap_rows(conn_rows, gt_rows)
    summary = summarize(conn_rows, gt_rows, time.time() - t0)

    write_csv(out / "conn_log_schema_time_audit.csv", [dict_conn(r) for r in conn_rows])
    write_csv(out / "groundtruth_schema_time_label_audit.csv", [dict_gt(r) for r in gt_rows])
    write_csv(out / "groundtruth_to_conn_time_overlap_top8.csv", overlap_rows)
    write_json(out / "summary.json", summary)
    write_text(out / "summary.md", build_report(summary))

    print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
