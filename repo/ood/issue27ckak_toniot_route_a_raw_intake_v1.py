"""issue27ckak: ToN-IoT strict Route-A raw-network intake/audit v1.

This script intentionally does NOT train, tune, threshold, or evaluate a
detector.  It freezes the entry gate for a high-standard external-dataset
comparison:

    raw external network asset -> our own unified frontend -> Gotham-trained
    decision system -> external report-only test

Route A is stricter than using a downloaded, already-extracted flow CSV because
the feature schema must be produced by the same frontend contract.  If the
folder only contains processed feature tables, this script records them as
Route-B/back-up assets and stops the formal Route-A path.

Data-use boundary:

* zero-shot external validation: second-dataset rows are report-only;
* few-shot adaptation, if later approved: only explicit support/calibration
  roles may be used;
* report/sealed rows are never available for fitting, thresholding, feature
  selection, imputation-policy tuning, or cleaning-rule tuning.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ISSUE = "issue27ckak_toniot_route_a_raw_intake_v1_2026-07-09"

WORKTREE = Path(__file__).resolve().parents[2]
PAPER04 = WORKTREE.parent.parent

DEFAULT_RAW_DIR = PAPER04 / "datasets" / "external" / "ton_iot_raw_network" / "raw"
DEFAULT_EXTRACTED_DIR = PAPER04 / "datasets" / "external" / "ton_iot_raw_network" / "extracted"
DEFAULT_OUT = WORKTREE / "runs" / ISSUE

OFFICIAL_UNSW_PAGE = "https://research.unsw.edu.au/projects/toniot-datasets"
OFFICIAL_SHAREPOINT_URL = (
    "https://unsw-my.sharepoint.com/:f:/g/personal/"
    "z5025758_ad_unsw_edu_au/"
    "EvBTaetotpdGnW7rJQ8fCvYBh8063CNeY9W33MpRsarJaQ?e=yZlnxW"
)

PCAP_EXTS = {".pcap", ".pcapng", ".cap"}
ARCHIVE_EXTS = {".zip", ".7z", ".rar", ".tar", ".tgz", ".gz", ".bz2", ".xz"}
TEXT_EXTS = {".csv", ".tsv", ".log", ".txt", ".json", ".md"}
ZEEK_HINT_NAMES = {
    "conn.log",
    "dns.log",
    "http.log",
    "ssl.log",
    "tls.log",
    "notice.log",
    "weird.log",
    "files.log",
    "smtp.log",
    "ftp.log",
    "dhcp.log",
    "ssh.log",
    "x509.log",
}
NETWORK_HINT_RE = re.compile(
    r"(network|pcap|packet|packets|zeek|bro|conn|flow|traffic|iot|iiot)",
    re.IGNORECASE,
)
PROCESSED_HINT_RE = re.compile(
    r"(train[_-]?test|processed|features?|cicflow|netflow|nf[_-]|flowmeter)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FileRow:
    relative_path: str
    size_bytes: int
    suffix: str
    kind: str
    route_a_status: str
    sha256: str
    sha256_policy: str
    mtime_utc: str
    notes: str


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, obj: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    ensure_dir(path.parent)
    path.write_text(text, encoding="utf-8")


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


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(block_size), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_sample(path: Path, sample_bytes: int = 4 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(sample_bytes))
    return f"sample_first_{sample_bytes}_bytes:{h.hexdigest()}"


def hash_for_policy(path: Path, policy: str, limit_mb: int) -> tuple[str, str]:
    size = path.stat().st_size
    if policy == "none":
        return "not_computed", "none"
    if policy == "sample":
        return sha256_sample(path), "sample"
    if policy == "full":
        return sha256_file(path), "full"
    if policy != "skip-large":
        raise ValueError(f"unknown hash policy: {policy}")
    if size <= limit_mb * 1024 * 1024:
        return sha256_file(path), f"full_if_le_{limit_mb}MB"
    return f"skipped_large_{size}_bytes_run_with_--hash-policy_full_for_formal_freeze", "skip-large"


def safe_rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_text_head(path: Path, max_bytes: int = 64 * 1024) -> str:
    with path.open("rb") as f:
        data = f.read(max_bytes)
    return data.decode("utf-8", errors="replace")


def classify_path(path: Path) -> tuple[str, str, str]:
    name = path.name.lower()
    suffixes = [s.lower() for s in path.suffixes]
    suffix = suffixes[-1] if suffixes else ""
    joined = str(path).lower().replace("\\", "/")

    if suffix in PCAP_EXTS:
        return "pcap_raw_packets", "route_a_candidate", "raw packet capture; can support unified packet/flow frontend"
    if suffix in ARCHIVE_EXTS:
        if NETWORK_HINT_RE.search(joined):
            return "archive_network_candidate", "needs_extract_then_reaudit", "archive name suggests raw/network material"
        return "archive_unknown", "needs_manual_classification", "archive requires extraction/audit before route assignment"
    if name in ZEEK_HINT_NAMES or suffix == ".log":
        return "zeek_or_bro_log", "route_a_candidate", "Zeek/Bro log-style raw network record candidate"
    if suffix in {".csv", ".tsv"}:
        if PROCESSED_HINT_RE.search(joined):
            return "processed_feature_table", "route_b_only_until_raw_frontend_match", "processed feature table; not enough for strict Route A by itself"
        if NETWORK_HINT_RE.search(joined):
            return "network_csv_unknown_level", "needs_schema_audit", "network-looking CSV; must verify whether raw Zeek/log or processed features"
        return "csv_unknown", "needs_schema_audit", "CSV requires schema audit"
    if suffix in TEXT_EXTS:
        return "text_metadata_or_log", "metadata_candidate", "text/log metadata candidate"
    return "unknown_binary_or_misc", "needs_manual_classification", "unclassified file"


def schema_sample_for_text(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "path": str(path),
        "readable_text_head": False,
        "format_guess": "unknown",
        "columns": [],
        "zeek_fields": [],
        "zeek_types": [],
        "first_nonempty_lines": [],
    }
    try:
        head = read_text_head(path)
    except Exception as exc:
        info["error"] = repr(exc)
        return info

    info["readable_text_head"] = True
    lines = [line.rstrip("\r\n") for line in head.splitlines()]
    nonempty = [line for line in lines if line.strip()][:8]
    info["first_nonempty_lines"] = nonempty

    for line in lines[:80]:
        if line.startswith("#fields"):
            info["format_guess"] = "zeek_log"
            info["zeek_fields"] = line.split("\t")[1:]
        elif line.startswith("#types"):
            info["zeek_types"] = line.split("\t")[1:]

    if info["zeek_fields"]:
        return info

    # Lightweight delimiter guess; do not use pandas here to keep intake portable.
    first_data = next((line for line in lines if line.strip() and not line.startswith("#")), "")
    if first_data:
        comma = first_data.count(",")
        tab = first_data.count("\t")
        delim = "\t" if tab > comma else ","
        info["format_guess"] = "tsv_or_csv" if delim == "\t" else "csv_or_comma_text"
        info["columns"] = [c.strip().strip('"') for c in first_data.split(delim)]
    return info


def inventory_files(raw_dir: Path, hash_policy: str, hash_limit_mb: int, max_files: int) -> list[FileRow]:
    rows: list[FileRow] = []
    if not raw_dir.exists():
        return rows
    count = 0
    for path in sorted(raw_dir.rglob("*")):
        if not path.is_file():
            continue
        count += 1
        if count > max_files:
            break
        kind, status, notes = classify_path(path)
        sha, policy_used = hash_for_policy(path, hash_policy, hash_limit_mb)
        stat = path.stat()
        rows.append(
            FileRow(
                relative_path=safe_rel(path, raw_dir),
                size_bytes=stat.st_size,
                suffix=path.suffix.lower(),
                kind=kind,
                route_a_status=status,
                sha256=sha,
                sha256_policy=policy_used,
                mtime_utc=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                notes=notes,
            )
        )
    return rows


def summarize(rows: list[FileRow]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    by_status: dict[str, int] = {}
    total_bytes = 0
    for row in rows:
        by_kind[row.kind] = by_kind.get(row.kind, 0) + 1
        by_status[row.route_a_status] = by_status.get(row.route_a_status, 0) + 1
        total_bytes += row.size_bytes
    route_a_candidates = [
        r for r in rows if r.route_a_status in {"route_a_candidate", "needs_extract_then_reaudit", "needs_schema_audit"}
    ]
    strict_ready = any(r.kind in {"pcap_raw_packets", "zeek_or_bro_log"} for r in rows)
    needs_extract = any(r.route_a_status == "needs_extract_then_reaudit" for r in rows)
    only_processed = bool(rows) and all(r.kind in {"processed_feature_table", "csv_unknown"} for r in rows)

    if strict_ready:
        gate = "PASS_WITH_SCHEMA_AUDIT_REQUIRED"
        decision = "Raw/Zeek network assets exist. Next step is schema/label/time audit before frontend extraction."
    elif needs_extract:
        gate = "WAITING_FOR_EXTRACTION"
        decision = "Network-looking archive exists; extract into extracted/ or raw/ and rerun this audit."
    elif only_processed:
        gate = "FAIL_ROUTE_A_PROCESSED_ONLY"
        decision = "Only processed/unknown CSV-like feature tables are visible. Keep as Route B; do not claim strict Route A."
    elif rows:
        gate = "BLOCKED_NEEDS_MANUAL_ASSET_CLASSIFICATION"
        decision = "Files exist, but no clear raw PCAP/Zeek/log candidate was found."
    else:
        gate = "WAITING_FOR_RAW_DOWNLOAD"
        decision = "No files are present in the raw intake folder yet."

    return {
        "issue": ISSUE,
        "generated_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "file_count": len(rows),
        "total_bytes": total_bytes,
        "by_kind": by_kind,
        "by_route_a_status": by_status,
        "route_a_candidate_count": len(route_a_candidates),
        "strict_route_a_gate": gate,
        "decision": decision,
    }


def build_download_instructions(raw_dir: Path, extracted_dir: Path) -> str:
    return f"""# ToN-IoT strict Route-A download/intake instructions

This folder is reserved for the strict external comparison line:

```text
raw ToN-IoT network asset -> our unified frontend -> Gotham-trained model -> external report-only evaluation
```

Official source page:

```text
{OFFICIAL_UNSW_PAGE}
```

Official SharePoint folder linked by UNSW:

```text
{OFFICIAL_SHAREPOINT_URL}
```

Local target directories:

```text
raw:       {raw_dir}
extracted: {extracted_dir}
```

Manual download rule:

1. Open the official SharePoint link in browser.
2. Prefer `Raw datasets` -> `Network` assets.
3. Download PCAP/PCAPNG files first if available.
4. If PCAP is too large or not exposed, download Zeek/Bro network logs such as
   `conn.log`, `dns.log`, `http.log`, `ssl.log/tls.log`, plus the
   SecurityEvents/GroundTruth timestamp files.
5. Put archives or raw files under the `raw` directory above.
6. Do not put model outputs, previous Gotham caches, or supercomputer transfer
   bundles into this directory.

After download, rerun:

```powershell
cd "{WORKTREE}"
python repo\\ood\\issue27ckak_toniot_route_a_raw_intake_v1.py --hash-policy skip-large
```

For the formal freeze after the right files are present, rerun with full hashes:

```powershell
cd "{WORKTREE}"
python repo\\ood\\issue27ckak_toniot_route_a_raw_intake_v1.py --hash-policy full
```
"""


def build_stop_rules() -> str:
    return """# issue27ckak strict Route-A stop rules

Route A is allowed only if all of these are true:

1. External data starts from raw network PCAP/PCAPNG or Zeek/Bro raw network logs.
2. A stable row/event key can be created without relying on duplicated Flow ID.
3. Timestamp/order semantics are auditable; file order alone is not trusted.
4. Label/ground-truth mapping is auditable, but labels are not used to create
   deployment-only frontend context.
5. The exact same frontend schema can be produced for Gotham and ToN-IoT.
6. Zero-shot external test keeps all ToN-IoT rows report-only.
7. If later doing few-shot adaptation, only explicitly frozen support/calibration
   roles are fit/select allowed; sealed/report rows remain untouched.

Stop immediately if:

* only processed CICFlow/NetFlow/train-test CSV tables are available;
* cleaning/imputation/clipping policy would require looking at external sealed
  rows before report;
* the frontend needs future labels or test labels to build context;
* attack or benign coverage cannot be audited by family/source/time.
"""


def build_dataset_card(summary: dict[str, Any], raw_dir: Path, out_dir: Path) -> str:
    return f"""# issue27ckak ToN-IoT strict Route-A raw intake

Generated: `{summary['generated_at_utc']}`

## Current gate

```text
{summary['strict_route_a_gate']}
```

Decision:

```text
{summary['decision']}
```

## Paths

```text
workspace: {WORKTREE}
raw_dir:   {raw_dir}
out_dir:   {out_dir}
```

## Inventory summary

```json
{json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True)}
```

## Route meaning

This is the formal external-validation path.  Already-extracted CICFlow/NetFlow
feature CSVs may remain useful as diagnostics or baselines, but they are not
enough to claim strict Route A unless we can reproduce the same frontend schema
from raw assets on both Gotham and ToN-IoT.
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--extracted-dir", type=Path, default=DEFAULT_EXTRACTED_DIR)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--hash-policy",
        choices=["skip-large", "full", "sample", "none"],
        default="skip-large",
        help="skip-large is fast; full is required for final formal freeze.",
    )
    parser.add_argument("--hash-limit-mb", type=int, default=2048)
    parser.add_argument("--max-files", type=int, default=20000)
    parser.add_argument("--schema-sample-limit", type=int, default=200)
    args = parser.parse_args(argv)

    t0 = time.time()
    ensure_dir(args.raw_dir)
    ensure_dir(args.extracted_dir)
    ensure_dir(args.out)

    rows = inventory_files(args.raw_dir, args.hash_policy, args.hash_limit_mb, args.max_files)
    summary = summarize(rows)
    summary["raw_dir"] = str(args.raw_dir)
    summary["extracted_dir"] = str(args.extracted_dir)
    summary["out_dir"] = str(args.out)
    summary["hash_policy_requested"] = args.hash_policy
    summary["runtime_sec"] = round(time.time() - t0, 3)

    write_csv(args.out / "file_inventory.csv", [r.__dict__ for r in rows])
    write_json(args.out / "route_a_status.json", summary)
    write_text(args.out / "dataset_card.md", build_dataset_card(summary, args.raw_dir, args.out))
    write_text(args.out / "DOWNLOAD_TON_IOT_ROUTE_A.md", build_download_instructions(args.raw_dir, args.extracted_dir))
    write_text(args.out / "ROUTE_A_STOP_RULES.md", build_stop_rules())

    schema_rows: list[dict[str, Any]] = []
    for row in rows[: args.schema_sample_limit]:
        path = args.raw_dir / row.relative_path
        if path.suffix.lower() in TEXT_EXTS or row.kind in {"zeek_or_bro_log", "processed_feature_table", "network_csv_unknown_level"}:
            sample = schema_sample_for_text(path)
            sample["relative_path"] = row.relative_path
            sample["kind"] = row.kind
            sample["route_a_status"] = row.route_a_status
            schema_rows.append(sample)
    write_json(args.out / "schema_samples.json", schema_rows)

    candidate_rows = [
        r.__dict__
        for r in rows
        if r.route_a_status in {"route_a_candidate", "needs_extract_then_reaudit", "needs_schema_audit"}
    ]
    write_csv(args.out / "candidate_route_a_assets.csv", candidate_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
