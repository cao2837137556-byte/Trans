"""CKBE: full-source, label-free event cache for official PyG-TGN M1.

This materializer is intentionally upstream of every classifier.  It produces
one source-local anonymous temporal event stream per raw source:

    (src_local_id, dst_local_id, canonical timestamp, portable raw message)

The raw label column is never read.  Target recorded indices from the frozen
mainline manifest are only used to write a row-to-event-position alignment
table for later supervised losses.  Each source is read in full, not merely up
to the largest recorded target: this closes the old prefix caveat where a
physically later CSV record could have an earlier timestamp.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12"
ROOT = cko.ROOT
OUT = ROOT / "runs" / ISSUE
DEFAULT_TARGETS = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_target_index.csv"
RAW_MSG_NAMES = [
    "log_packet_length", "is_tcp", "is_udp", "is_icmp", "destination_port_bucket",
    "tcp_syn", "tcp_ack", "tcp_rst", "tcp_fin",
]


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def coalesce(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def port_bucket(port: int) -> float:
    if port <= 0:
        return 0.0
    if port <= 1024:
        return 0.25
    if port <= 49151:
        return 0.5
    return 0.75


def source_key(source: str) -> str:
    return hashlib.sha256(str(source).encode("utf-8")).hexdigest()[:20]


def read_source(source: str) -> pd.DataFrame:
    with zipfile.ZipFile(cko.GOTHAM_ZIP) as archive:
        with archive.open(source) as handle:
            return pd.read_csv(handle, usecols=lambda name: name in ckaw.RAW_USECOLS, low_memory=False)


def event_arrays(frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    """Canonicalize all finite-timestamp events without exposing identities."""
    seconds = ckaw.ckat._raw_time_seconds(frame.get("frame.time", pd.Series(np.nan, index=frame.index)))
    order, finite, violations = ckaw.ckat._canonical_order(seconds)
    order = order[finite[order]]
    base = float(np.nanmin(seconds[finite])) if bool(finite.any()) else 0.0
    proto = frame.get("frame.protocols", pd.Series("", index=frame.index)).astype(str).str.lower().to_numpy()
    ip_src = frame.get("ip.src", pd.Series("", index=frame.index)).to_numpy()
    ip_dst = frame.get("ip.dst", pd.Series("", index=frame.index)).to_numpy()
    eth_src = frame.get("eth.src", pd.Series("", index=frame.index)).to_numpy()
    eth_dst = frame.get("eth.dst", pd.Series("", index=frame.index)).to_numpy()
    ip_proto = pd.to_numeric(frame.get("ip.proto", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    length = pd.to_numeric(frame.get("frame.len", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    tcp_dst = pd.to_numeric(frame.get("tcp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    udp_dst = pd.to_numeric(frame.get("udp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    flags = np.asarray([cko.parse_tcp_flags(value) for value in frame.get("tcp.flags", pd.Series(0, index=frame.index)).to_numpy()], dtype=np.int64)

    node_map: dict[str, int] = {}
    src = np.empty(len(order), dtype=np.int32)
    dst = np.empty(len(order), dtype=np.int32)
    stamp = np.empty(len(order), dtype=np.int64)
    message = np.empty((len(order), len(RAW_MSG_NAMES)), dtype=np.float32)

    def node(value: str) -> int:
        if value not in node_map:
            node_map[value] = len(node_map)
        return node_map[value]

    for position, ridx in enumerate(order.tolist()):
        source = node(coalesce(ip_src[ridx], eth_src[ridx], f"row{ridx}:src"))
        target = node(coalesce(ip_dst[ridx], eth_dst[ridx], f"row{ridx}:dst"))
        dport = int(tcp_dst[ridx] if tcp_dst[ridx] > 0 else udp_dst[ridx])
        is_tcp = float(ip_proto[ridx] == 6 or "tcp" in str(proto[ridx]))
        is_udp = float(ip_proto[ridx] == 17 or "udp" in str(proto[ridx]))
        is_icmp = float(ip_proto[ridx] == 1 or "icmp" in str(proto[ridx]))
        src[position], dst[position] = source, target
        stamp[position] = int(round((float(seconds[ridx]) - base) * 1000.0))
        message[position] = np.asarray([
            math.log1p(max(0.0, float(length[ridx]))), is_tcp, is_udp, is_icmp, port_bucket(dport),
            float(bool(flags[ridx] & 0x02)), float(bool(flags[ridx] & 0x10)),
            float(bool(flags[ridx] & 0x04)), float(bool(flags[ridx] & 0x01)),
        ], dtype=np.float32)
    summary = {
        "raw_rows": int(len(frame)), "finite_events": int(len(order)), "source_local_nodes": int(len(node_map)),
        "timestamp_parse_failures": int((~finite).sum()), "recorded_order_timestamp_violations": int(violations),
        "raw_label_column_read": False,
    }
    return order.astype(np.int64), stamp, src, dst, message, summary


def plan(targets: pd.DataFrame, out: Path) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for source, part in targets.groupby("source_group", sort=True):
        indices = pd.to_numeric(part["recorded_index"], errors="coerce").dropna().astype(np.int64).unique()
        rows.append({
            "source_group": str(source), "source_cache_key": source_key(str(source)),
            "target_rows": int(len(indices)), "max_recorded_index": int(np.max(indices)),
        })
    result = pd.DataFrame(rows)
    result.to_csv(out / "tgn_source_event_plan.csv", index=False)
    return result


def materialize_source(source: str, targets: np.ndarray, cache_dir: Path) -> dict[str, Any]:
    started = time.time()
    frame = read_source(source)  # Complete source: no recorded-prefix chronology shortcut.
    recorded, stamp, src, dst, message, summary = event_arrays(frame)
    position = {int(index): int(pos) for pos, index in enumerate(recorded.tolist())}
    targets = np.sort(np.unique(np.asarray(targets, dtype=np.int64)))
    target_positions = np.asarray([position.get(int(index), -1) for index in targets], dtype=np.int64)
    key = source_key(source)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        cache_dir / f"{key}.npz", recorded_index=recorded, time_ms=stamp, src=src, dst=dst, raw_msg=message,
        target_recorded_index=targets, target_event_position=target_positions,
    )
    summary.update({
        "source_group": source, "source_cache_key": key, "target_rows": int(len(targets)),
        "target_positions_found": int(np.sum(target_positions >= 0)), "seconds": time.time() - started,
        "event_schema": RAW_MSG_NAMES, "node_identity_policy": "source-local dynamic anonymous id; id not included in raw_msg",
        "canonical_policy": "full raw source, timestamp ascending then recorded-index stable",
    })
    (cache_dir / f"{key}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = pd.read_csv(args.targets, usecols=["source_group", "recorded_index"])
    targets["recorded_index"] = pd.to_numeric(targets["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    targets = targets[targets["recorded_index"] >= 0]
    if args.mode == "plan":
        source_plan = plan(targets, out)
        (out / "run_spec.json").write_text(json.dumps({"issue": ISSUE, "mode": "plan", "sources": int(len(source_plan)), "raw_label_column_read": False}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "plan_ok", "out": str(out), "sources": int(len(source_plan))}, indent=2))
        return
    # Array workers must receive one immutable plan. They must never rewrite a
    # shared plan file while sibling source jobs are starting.
    source_plan = pd.read_csv(args.source_plan) if args.source_plan else plan(targets, out)
    if args.source_index < 0 or args.source_index >= len(source_plan):
        raise ValueError(f"source-index {args.source_index} outside 0..{len(source_plan)-1}")
    source = str(source_plan.iloc[int(args.source_index)]["source_group"])
    rows = targets[targets["source_group"].astype(str).eq(source)]["recorded_index"].to_numpy(dtype=np.int64)
    summary = materialize_source(source, rows, Path(args.cache_dir))
    runtime = out / "source_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / f"{source_key(source)}.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "source": source, "out": str(args.cache_dir), **summary}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", default=str(DEFAULT_TARGETS))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--cache-dir", default=str(OUT / "tgn_event_cache"))
    parser.add_argument("--source-plan", default="", help="immutable plan for array workers")
    parser.add_argument("--mode", choices=["plan", "materialize"], default="plan")
    parser.add_argument("--source-index", type=int, default=-1)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
