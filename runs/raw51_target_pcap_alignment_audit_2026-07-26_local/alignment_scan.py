#!/usr/bin/env python3
"""Read-only full-scope target-to-PCAP alignment audit (Codex mandate 2026-07-26).

For every frozen Gotham target (base T0 34,622 + report extension 290,445 =
325,067), reproduce the formal matching rule (timestamp +/-2 us, exact frame
length, compatible 5-tuple via the frozen ``TargetMatcher.compatible``)
against ALL 110 pcap members in the frozen ZIP, in a single pass with a
hash-indexed fingerprint table. Each target is classified into exactly one of:

  exact_member_unique / exact_member_ambiguous / non_exact_member_unique /
  non_exact_member_multiple / absent_from_all_pcaps / unsupported_or_malformed

Matching never reads label/family/role; roles are joined only afterwards for
the concentration summaries. Nothing frozen is modified.

Known local deviation (documented): packets are parsed from pcap record
headers instead of TShark, so timestamps come from sec+usec fields; the
+/-2 us tolerance absorbs the <=1 us float-rounding difference vs
frame.time_epoch string parsing. frame.len equals the on-wire length
(orig_len). IPv6 textual form uses RFC 5952 compression like TShark.
"""

from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import struct
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace

BASE = Path(r"D:\study\paper\anomaly_detection\paper04\worktrees\kitnet-exp-mainline")
sys.path.insert(0, str(BASE / "repo" / "ood"))
import issue27ckbu_unified_tshark_causal_frontend_v1 as ckbu  # noqa: E402

ZIP_PATH = Path(r"D:\study\paper\anomaly_detection\paper04\datasets\gotham2025\raw\GothamDataset2025.zip")
BASE_TARGETS = BASE / "runs/issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1/canonical_source_target_index.csv"
REPORT_TARGETS = BASE / "runs/issue27ckbu_unified_tshark_causal_frontend_v1_2026-07-23_local_plan/report_extension_recorded_targets.csv"
SOURCE_PLAN = BASE / "runs/issue27ckbu_unified_tshark_causal_frontend_v1_2026-07-23_local_plan/ckbu_gotham_source_plan.csv"
OUT = BASE / "runs/raw51_target_pcap_alignment_audit_2026-07-26_local"
TOLERANCE_US = 2
EXPECTED_TOTAL = 325_067
EXPECTED_MEMBERS = 110

STATUSES = [
    "exact_member_unique",
    "exact_member_ambiguous",
    "non_exact_member_unique",
    "non_exact_member_multiple",
    "absent_from_all_pcaps",
    "unsupported_or_malformed",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


# ---------------------------------------------------------------- targets ---
log("loading frozen target lists")
targets_meta: dict[tuple[str, int], dict] = {}
for path, origin in ((BASE_TARGETS, "base_t0"), (REPORT_TARGETS, "report_extension")):
    for row in csv.DictReader(path.open(encoding="utf-8")):
        key = (row["source_group"], int(row["recorded_index"]))
        if key in targets_meta:
            raise RuntimeError(f"duplicate frozen target: {key}")
        targets_meta[key] = {
            "origin": origin,
            "roles": row.get("roles", "") or row.get("report_role", ""),
            "folds": row.get("folds", ""),
            "stages": row.get("stages", "") or row.get("report_phase_policy", ""),
        }
if len(targets_meta) != EXPECTED_TOTAL:
    raise RuntimeError(f"target reconciliation failed: {len(targets_meta)} != {EXPECTED_TOTAL}")
wanted_by_source: dict[str, set[int]] = defaultdict(set)
for source, index in targets_meta:
    wanted_by_source[source].add(index)
log(f"targets: {len(targets_meta)} across {len(wanted_by_source)} sources")

zf = zipfile.ZipFile(ZIP_PATH)
all_members = sorted(n for n in zf.namelist() if n.endswith(".pcap"))
if len(all_members) != EXPECTED_MEMBERS:
    raise RuntimeError(f"member count {len(all_members)} != {EXPECTED_MEMBERS}")
member_id = {name: i for i, name in enumerate(all_members)}

# Exact-stem pairing via the FROZEN planner function for every source; the
# (older, 26-source) local plan CSV is used only as a cross-check.
plan_members: dict[str, list[str]] = {}
for row in csv.DictReader(SOURCE_PLAN.open(encoding="utf-8")):
    plan_members[row["source_group"]] = json.loads(row["pcap_members_json"])
exact_members_by_source: dict[str, set[int]] = {}
for source in wanted_by_source:
    members = ckbu.exact_pcap_members(all_members, source)
    if source in plan_members and sorted(plan_members[source]) != sorted(members):
        raise RuntimeError(
            f"frozen pairing disagrees with local plan for {source}: "
            f"{plan_members[source]} vs {members}"
        )
    exact_members_by_source[source] = {member_id[m] for m in members}

# ----------------------------------------------------------- fingerprints ---
log("building fingerprints from processed CSVs (matching fields only)")
fingerprints: list = []          # tid -> TargetFingerprint or None
tid_by_key: dict[tuple[str, int], int] = {}
status: list[str | None] = []
for source in sorted(wanted_by_source):
    wanted = wanted_by_source[source]
    found: dict[int, object] = {}
    bad: dict[int, str] = {}
    started = time.monotonic()
    with zf.open(source) as fh:
        text = io.TextIOWrapper(fh, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.reader(text)
        header = next(reader)
        col = {name: pos for pos, name in enumerate(header)}
        needed = [(name, col.get(name)) for name in ckbu.GOTHAM_ALIGNMENT_FIELDS]
        remaining = set(wanted)
        for index, row in enumerate(reader):
            if index not in remaining:
                continue
            remaining.discard(index)
            safe = {
                name: (row[pos] if pos is not None and pos < len(row) else "")
                for name, pos in needed
            }
            try:
                fp = ckbu.target_from_processed_row(source, index, safe)
                if not (fp.timestamp == fp.timestamp) or fp.timestamp <= 0:
                    raise ValueError("nonfinite or nonpositive timestamp")
                found[index] = fp
            except Exception as exc:  # noqa: BLE001 - audit must not crash
                bad[index] = f"{type(exc).__name__}: {exc}"
            if not remaining:
                break
        for index in remaining:
            bad[index] = "row_absent_from_processed_csv"
    for index in sorted(wanted):
        tid = len(fingerprints)
        tid_by_key[(source, index)] = tid
        if index in found:
            fingerprints.append(found[index])
            status.append(None)
        else:
            fingerprints.append(None)
            status.append("unsupported_or_malformed")
            targets_meta[(source, index)]["error"] = bad.get(index, "unknown")
    log(f"  {source}: ok={len(found)} malformed={len(bad)} "
        f"({time.monotonic() - started:.0f}s)")

# ------------------------------------------------------------- time index ---
log("indexing fingerprints by microsecond key")
by_time: dict[int, list[int]] = defaultdict(list)
for tid, fp in enumerate(fingerprints):
    if fp is None:
        continue
    for key in range(fp.time_us - TOLERANCE_US, fp.time_us + TOLERANCE_US + 1):
        by_time[key].append(tid)
by_time = dict(by_time)
log(f"index keys: {len(by_time)}")

# ------------------------------------------------------------- pcap sweep ---
matches: dict[int, dict[int, int]] = defaultdict(dict)  # tid -> {member: count}
member_rows = []
compatible = ckbu.TargetMatcher.compatible

for member_name in all_members:
    mid = member_id[member_name]
    info = zf.getinfo(member_name)
    packets = 0
    hits = 0
    started = time.monotonic()
    with zf.open(member_name) as raw:
        stream = io.BufferedReader(raw, buffer_size=4 << 20)
        gh = stream.read(24)
        if len(gh) < 24:
            member_rows.append((member_name, 0, 0, info.file_size, info.CRC, "empty"))
            continue
        magic = gh[:4]
        endian = "<" if magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1") else ">"
        nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        rec = struct.Struct(endian + "IIII")
        read = stream.read
        unpack = rec.unpack
        get_bucket = by_time.get
        while True:
            hdr = read(16)
            if len(hdr) < 16:
                break
            ts_sec, ts_frac, incl, orig = unpack(hdr)
            data = read(incl)
            if len(data) < incl:
                break
            packets += 1
            timestamp = ts_sec + ts_frac / (1e9 if nano else 1e6)
            bucket = get_bucket(int(round(timestamp * 1_000_000.0)))
            if bucket is None:
                continue
            # decode only when a target is nearby (sparse by construction)
            src = dst = ""
            proto = sport = dport = 0
            offset = 12
            ethertype = data[offset:offset + 2]
            if ethertype == b"\x81\x00" and len(data) >= 18:
                offset += 4
                ethertype = data[offset:offset + 2]
            payload = data[offset + 2:]
            if ethertype == b"\x08\x00" and len(payload) >= 20:
                ihl = (payload[0] & 0x0F) * 4
                proto = payload[9]
                src = ".".join(map(str, payload[12:16]))
                dst = ".".join(map(str, payload[16:20]))
                l4 = payload[ihl:]
                if proto in (6, 17) and len(l4) >= 4:
                    sport, dport = struct.unpack(">HH", l4[:4])
            elif ethertype == b"\x86\xdd" and len(payload) >= 40:
                proto = 0  # TShark ip.proto is empty for IPv6
                src = str(ipaddress.IPv6Address(payload[8:24]))
                dst = str(ipaddress.IPv6Address(payload[24:40]))
                next_header = payload[6]
                l4 = payload[40:]
                if next_header in (6, 17) and len(l4) >= 4:
                    sport, dport = struct.unpack(">HH", l4[:4])
            else:
                src, dst = "missing-src", "missing-dst"
            event = SimpleNamespace(
                frame_len=orig, src=src or "missing-src", dst=dst or "missing-dst",
                ip_proto=proto, src_port=sport, dst_port=dport,
            )
            for tid in bucket:
                fp = fingerprints[tid]
                if compatible(fp, event):
                    counts = matches[tid]
                    counts[mid] = counts.get(mid, 0) + 1
                    hits += 1
    member_rows.append((member_name, packets, hits, info.file_size, info.CRC, "ok"))
    log(f"  member {mid:3d}/110 {member_name.split('/')[-1]}: packets={packets} "
        f"target_hits={hits} ({time.monotonic() - started:.0f}s)")

# ---------------------------------------------------------- classification ---
log("classifying targets")
audit_rows = []
source_counter: dict[str, Counter] = defaultdict(Counter)
role_counter: dict[str, Counter] = defaultdict(Counter)
member_exact_hits = Counter()
member_foreign_hits = Counter()
for (source, index), meta in sorted(targets_meta.items()):
    tid = tid_by_key[(source, index)]
    exact_set = exact_members_by_source[source]
    if status[tid] == "unsupported_or_malformed":
        verdict = "unsupported_or_malformed"
        exact_n = other_n = 0
        candidate_members = ""
    else:
        counts = matches.get(tid, {})
        exact_n = sum(c for m, c in counts.items() if m in exact_set)
        other_n = sum(c for m, c in counts.items() if m not in exact_set)
        for m, c in counts.items():
            (member_exact_hits if m in exact_set else member_foreign_hits)[m] += c
        if exact_n == 1:
            verdict = "exact_member_unique"
        elif exact_n >= 2:
            verdict = "exact_member_ambiguous"
        elif other_n == 1:
            verdict = "non_exact_member_unique"
        elif other_n >= 2:
            verdict = "non_exact_member_multiple"
        else:
            verdict = "absent_from_all_pcaps"
        candidate_members = ";".join(
            f"{all_members[m]}:{c}" for m, c in sorted(counts.items())
        )[:400]
    audit_rows.append({
        "source_group": source,
        "recorded_index": index,
        "origin": meta["origin"],
        "status": verdict,
        "exact_candidates": exact_n,
        "other_candidates": other_n,
        "candidate_members_truncated": candidate_members,
        "error": meta.get("error", ""),
    })
    source_counter[source][verdict] += 1
    role_counter[meta["roles"] or "(none)"][verdict] += 1

totals = Counter(row["status"] for row in audit_rows)
if sum(totals.values()) != EXPECTED_TOTAL:
    raise RuntimeError("classification reconciliation failed")

# ---------------------------------------------------------------- outputs ---
log("writing outputs")
OUT.mkdir(parents=True, exist_ok=True)
with (OUT / "alignment_target_audit.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()))
    writer.writeheader()
    writer.writerows(audit_rows)
with (OUT / "alignment_source_summary.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["source_group", "targets", *STATUSES, "unaligned_pct"])
    for source in sorted(source_counter):
        row = source_counter[source]
        total = sum(row.values())
        unaligned = total - row["exact_member_unique"]
        writer.writerow([source, total, *[row[s] for s in STATUSES],
                         round(100 * unaligned / total, 3)])
with (OUT / "alignment_role_family_summary.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["roles", "targets", *STATUSES])
    for role_name in sorted(role_counter):
        row = role_counter[role_name]
        writer.writerow([role_name, sum(row.values()), *[row[s] for s in STATUSES]])
with (OUT / "alignment_member_summary.csv").open("w", encoding="utf-8", newline="") as fh:
    writer = csv.writer(fh)
    writer.writerow(["member", "packets", "target_hits", "compressed_size",
                     "zip_crc32", "parse_status", "exact_home_hits", "foreign_hits"])
    for name, packets, hits, size, crc, ok in member_rows:
        mid = member_id[name]
        writer.writerow([name, packets, hits, size, f"{crc:08x}", ok,
                         member_exact_hits.get(mid, 0), member_foreign_hits.get(mid, 0)])

overall_unaligned = EXPECTED_TOTAL - totals["exact_member_unique"]
per_source_pct = {
    source: 100 * (sum(c.values()) - c["exact_member_unique"]) / sum(c.values())
    for source, c in source_counter.items()
}
decision = {
    "status": "RAW51_ALIGNMENT_AUDIT_V1",
    "expected_targets": EXPECTED_TOTAL,
    "classified_targets": sum(totals.values()),
    "totals_by_status": dict(totals),
    "overall_non_exact_unique_pct": round(100 * overall_unaligned / EXPECTED_TOTAL, 4),
    "codex_gate_overall_le_0.5pct": 100 * overall_unaligned / EXPECTED_TOTAL <= 0.5,
    "codex_gate_worst_source_le_2pct": max(per_source_pct.values()) <= 2.0,
    "worst_sources_pct": dict(sorted(per_source_pct.items(), key=lambda kv: -kv[1])[:8]),
    "tolerance_us": TOLERANCE_US,
    "matching_rule": "frozen TargetMatcher.compatible + time key int(round(ts*1e6)) in [t-2, t+2]",
    "matching_reads_labels_or_roles": False,
    "inputs": {
        "zip": {"path": str(ZIP_PATH), "bytes": ZIP_PATH.stat().st_size},
        "base_targets_sha256": sha256_file(BASE_TARGETS),
        "report_targets_sha256": sha256_file(REPORT_TARGETS),
        "source_plan_sha256": sha256_file(SOURCE_PLAN),
        "pcap_members": len(all_members),
    },
    "local_deviation": "packet timestamps re-parsed from pcap headers, not TShark; "
                       "+/-2us window absorbs <=1us float rounding; frame.len=orig_len",
}
(OUT / "alignment_decision_inputs.json").write_text(
    json.dumps(decision, indent=1, sort_keys=True), encoding="utf-8"
)
log("=== SUMMARY ===")
for status_name in STATUSES:
    log(f"  {status_name}: {totals[status_name]}")
log(f"overall non-exact-unique: {overall_unaligned} "
    f"({100 * overall_unaligned / EXPECTED_TOTAL:.4f}%)")
log(f"codex gates: overall<=0.5% {decision['codex_gate_overall_le_0.5pct']}, "
    f"worst-source<=2% {decision['codex_gate_worst_source_le_2pct']}")
log("ALIGNMENT_AUDIT_DONE")
