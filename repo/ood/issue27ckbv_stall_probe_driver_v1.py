#!/usr/bin/env python3
"""Bounded root-cause probe driver for the CKBV mirai-dos decode stall.

Diagnostic only (failure ledger section 10). This driver never writes any
science artifact, cache, checkpoint, model, threshold, or metric. It exists to
discriminate, on a compute node, between:

- the formal Python ZIP-producer -> TShark stdin path (``--mode producer``),
- field-group escalation subsets (``--mode fieldargs``),
- and to aggregate per-probe results into one verdict (``--mode summarize``).

The frozen production frontend module is imported read-only so field lists and
the producer pipeline are byte-identical to the formal experiment.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import zipfile
from pathlib import Path


def load_ckbu():
    """Import the frozen frontend, pinned to CKBV_FROZEN_CODE_ROOT when set.

    ``sys.path[0]`` is the driver's own directory, which in a worktree also
    holds a frontend copy; inserting the frozen root ahead of it guarantees
    the byte-audited r8 copy is the one actually executed, and the origin
    assertion turns any silent shadowing into a hard failure.
    """
    root = os.environ.get("CKBV_FROZEN_CODE_ROOT", "")
    if root:
        sys.path.insert(0, str(Path(root).resolve()))
    import issue27ckbu_unified_tshark_causal_frontend_v1 as ckbu

    if root and Path(ckbu.__file__).resolve().parent != Path(root).resolve():
        raise RuntimeError(
            f"frozen frontend import escaped CKBV_FROZEN_CODE_ROOT: {ckbu.__file__}"
        )
    return ckbu


# Field-group escalation. Order preserves the production ``-e`` order. P3 adds
# the two tcp.analysis fields and is therefore identical to the full
# production set P4; ``selftest`` asserts this so the equivalence is checked,
# not assumed.
P0_FIELDS = [
    "frame.number",
    "frame.time_epoch",
    "frame.len",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "tcp.flags.syn",
    "tcp.flags.ack",
    "tcp.flags.reset",
    "tcp.flags.fin",
]
P1_FIELDS = P0_FIELDS + [
    "tcp.stream",
    "udp.stream",
    "tcp.stream.pnum",
    "tcp.time_relative",
    "tcp.time_delta",
]
P2_FIELDS = P1_FIELDS + ["tcp.connection.syn"]
P3_FIELDS = P2_FIELDS + [
    "tcp.analysis.retransmission",
    "tcp.analysis.lost_segment",
]


def field_groups(ckbu) -> dict[str, list[str]]:
    return {
        "P0": P0_FIELDS,
        "P1": P1_FIELDS,
        "P2": P2_FIELDS,
        "P3": P3_FIELDS,
        "P4": list(ckbu.TSHARK_FIELDS),
    }


def run_selftest() -> int:
    ckbu = load_ckbu()
    groups = field_groups(ckbu)
    full = groups["P4"]
    previous: list[str] = []
    for name in ["P0", "P1", "P2", "P3"]:
        fields = groups[name]
        if len(set(fields)) != len(fields):
            print(f"SELFTEST_FAIL duplicate field in {name}", file=sys.stderr)
            return 2
        if not set(previous).issubset(set(fields)):
            print(f"SELFTEST_FAIL {name} does not extend prior group", file=sys.stderr)
            return 2
        unknown = [f for f in fields if f not in full]
        if unknown:
            print(f"SELFTEST_FAIL {name} not subset of production: {unknown}", file=sys.stderr)
            return 2
        previous = fields
    if groups["P3"] != full:
        print("SELFTEST_FAIL P3 must equal the full production field list", file=sys.stderr)
        return 2
    command = ckbu.tshark_command("tshark", "-", packet_limit=100)
    for field in full:
        if field not in command:
            print(f"SELFTEST_FAIL production command missing {field}", file=sys.stderr)
            return 2
    print("SELFTEST_OK groups=P0..P4 production_fields=%d" % len(full))
    return 0


def run_fieldargs(group: str) -> int:
    ckbu = load_ckbu()
    groups = field_groups(ckbu)
    if group not in groups:
        print(f"unknown field group: {group}", file=sys.stderr)
        return 2
    print(" ".join(f"-e {name}" for name in groups[group]))
    return 0


def run_producer(args: argparse.Namespace) -> int:
    """Exercise the exact formal ZIP-producer -> TShark stdin path.

    On deadline expiry we print a stall verdict and leave via ``os._exit`` so
    the generator's ``finally`` (which would block in ``process.wait()`` on a
    stalled TShark) cannot deadlock the probe. The Slurm wrapper reaps any
    orphaned TShark afterwards.
    """
    ckbu = load_ckbu()
    deadline = time.monotonic() + float(args.deadline_seconds)
    started = time.monotonic()
    rows = 0
    last_tick_rows = 0
    archive = zipfile.ZipFile(args.zip)
    iterator = ckbu.iter_tshark_rows(
        args.tshark,
        archive=archive,
        member=args.member,
        packet_limit=int(args.limit) if int(args.limit) > 0 else None,
    )
    try:
        for _row in iterator:
            rows += 1
            if rows % int(args.tick) == 0:
                elapsed = time.monotonic() - started
                print(
                    f"PROBE_PRODUCER_TICK rows={rows} elapsed={elapsed:.1f}s "
                    f"rate={rows / max(elapsed, 1e-9):.1f}/s",
                    flush=True,
                )
                last_tick_rows = rows
            if time.monotonic() > deadline:
                elapsed = time.monotonic() - started
                print(
                    f"PROBE_PRODUCER_STALL_OR_DEADLINE rows={rows} "
                    f"elapsed={elapsed:.1f}s last_tick_rows={last_tick_rows}",
                    flush=True,
                )
                print(f"PROBE_ROWS_TOTAL rows={rows}", flush=True)
                sys.stdout.flush()
                sys.stderr.flush()
                os._exit(124)
    except RuntimeError as exc:
        elapsed = time.monotonic() - started
        print(
            f"PROBE_PRODUCER_ERROR rows={rows} elapsed={elapsed:.1f}s error={exc}",
            flush=True,
        )
        print(f"PROBE_ROWS_TOTAL rows={rows}", flush=True)
        return 3
    elapsed = time.monotonic() - started
    print(
        f"PROBE_PRODUCER_END rows={rows} elapsed={elapsed:.1f}s "
        f"rate={rows / max(elapsed, 1e-9):.1f}/s",
        flush=True,
    )
    print(f"PROBE_ROWS_TOTAL rows={rows}", flush=True)
    return 0


STALL_WALL_ROWS = 2_375_000
# The formal run froze with its progress state at the 2,375,000 boundary and
# the production progress bucket is 25,000 rows, so the true freeze point lies
# in [2,375,000, 2,400,000). Rows beyond that window mean slow progress past
# the wall, not the deterministic freeze.
STALL_WINDOW_ROWS = 25_000
BUDGET_SKIP_RC = -9


def run_summarize(args: argparse.Namespace) -> int:
    matrix = Path(args.matrix)
    rows = list(csv.DictReader(matrix.open(encoding="utf-8")))
    if not rows:
        print("no probe rows recorded", file=sys.stderr)
        return 2

    def status(row: dict[str, str]) -> str:
        rc = int(row["rc_main"])
        count = int(row["rows"])
        limit = int(row["limit"])
        rc_up = int(row.get("rc_upstream") or 0)
        if rc == BUDGET_SKIP_RC:
            return "skipped_budget"
        if rc in (124, 137):
            # Deterministic freeze versus a slow-but-progressing decode that
            # merely exhausted its budget; only the former is "stalled".
            if limit > 0 and count < STALL_WALL_ROWS + STALL_WINDOW_ROWS:
                return "stalled"
            return "slow_timeout"
        if rc == 0:
            upstream_ok = row["mode"] != "pipe" or rc_up in (0, 141)
            if (limit == 0 or count >= limit) and upstream_ok:
                return "completed"
            return "short_read"
        return f"error_{rc}"

    by_name = {row["name"]: row for row in rows}
    verdict: dict[str, object] = {
        "status": "CKBV_STALL_PROBE_VERDICT_V1",
        "probes": {
            name: {
                "status": status(row),
                "rows": int(row["rows"]),
                "elapsed_seconds": float(row["elapsed"]),
                "rc_main": int(row["rc_main"]),
                "max_rss_kb": row.get("max_rss_kb", ""),
            }
            for name, row in by_name.items()
        },
    }

    def stalled(name: str) -> bool:
        return name in by_name and status(by_name[name]) == "stalled"

    def completed(name: str) -> bool:
        return name in by_name and status(by_name[name]) == "completed"

    paths = ["A_producer_P4", "B_stdinpipe_P4", "C_file_P4"]
    if stalled("A_producer_P4") and completed("B_stdinpipe_P4") and completed("C_file_P4"):
        verdict["input_path_verdict"] = "producer_pipeline_defect"
    elif all(stalled(p) for p in paths):
        verdict["input_path_verdict"] = "tshark_internal_stall"
    elif all(completed(p) for p in paths):
        verdict["input_path_verdict"] = "no_stall_reproduced"
    else:
        verdict["input_path_verdict"] = "mixed_review_required"

    trigger = None
    for name in ["C_file_P0", "C_file_P1", "C_file_P2", "C_file_P4"]:
        if stalled(name):
            trigger = name
            break
    verdict["first_stalling_field_group"] = trigger
    verdict["mitigation_candidates"] = [
        name
        for name in by_name
        if name.startswith("C_file_P4_no_") and completed(name)
    ]
    verdict["depth_probes"] = {
        name: status(row) for name, row in by_name.items() if name.startswith("DEPTH_")
    }
    out = Path(args.out)
    out.write_text(json.dumps(verdict, indent=1, sort_keys=True), encoding="utf-8")
    print("CKBV_STALL_PROBE_VERDICT " + json.dumps(verdict, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=["selftest", "fieldargs", "producer", "summarize"],
    )
    parser.add_argument("--group", default="P4")
    parser.add_argument("--zip", default="")
    parser.add_argument("--member", default="")
    parser.add_argument("--tshark", default="tshark")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--tick", type=int, default=100000)
    parser.add_argument("--deadline-seconds", type=float, default=1500.0)
    parser.add_argument("--matrix", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    if args.mode == "selftest":
        return run_selftest()
    if args.mode == "fieldargs":
        return run_fieldargs(args.group)
    if args.mode == "producer":
        if not args.zip or not args.member:
            parser.error("--zip and --member are required for producer mode")
        return run_producer(args)
    if args.mode == "summarize":
        if not args.matrix or not args.out:
            parser.error("--matrix and --out are required for summarize mode")
        return run_summarize(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
