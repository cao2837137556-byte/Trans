"""issue27ckaw: canonical-time interaction-episode frontend.

This is not another C1/CICFlow summary.  It is an independently specified,
label-free event representation inspired by connection semantics and flow
interaction graphs.  Each target packet receives current packet semantics plus
strictly past-only state for its source, destination, directed pair, reverse
pair, and source file.  State is replayed by ``frame.time`` ascending with a
stable recorded-index tie-breaker.

The script only materializes source caches.  A later paired-head experiment
will consume these immutable features; this separation prevents report labels
from steering representation construction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
import zipfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OOD_DIR = Path(__file__).resolve().parent
ROOT = OOD_DIR.parents[1]
import sys
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10"
OUT_BASE = ROOT / "runs" / ISSUE
CKAT_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
DEFAULT_TARGETS = CKAT_PLAN / "canonical_source_target_index.csv"
DEFAULT_CACHE = OUT_BASE / "canonical_episode_cache"
WINDOW_SHORT = 10.0
WINDOW_LONG = 60.0
EPISODE_SECONDS = 60.0

# ``label`` is intentionally absent.  These are fields available in a normal
# packet-derived record; they provide Zeek-like state proxies without using a
# source's truth column.
RAW_USECOLS = [
    "frame.time", "frame.len", "frame.protocols", "ip.src", "ip.dst", "eth.src", "eth.dst", "ip.proto",
    "tcp.srcport", "tcp.dstport", "udp.srcport", "udp.dstport", "tcp.flags",
]

FEATURE_NAMES = [
    "cur_log_frame_len", "cur_is_tcp", "cur_is_udp", "cur_is_icmp", "cur_dst_well_known",
    "cur_tcp_syn", "cur_tcp_ack", "cur_tcp_rst", "cur_tcp_fin",
    "src_short_count_log", "src_long_count_log", "src_short_rate_log", "src_long_rate_log",
    "src_short_unique_dst_log", "src_long_unique_dst_log", "src_short_unique_dport_log", "src_long_unique_dport_log",
    "src_dport_entropy_short", "src_dport_entropy_long", "src_new_dst_in_long", "src_new_dport_in_long",
    "dst_short_unique_src_log", "dst_long_unique_src_log", "dst_short_pressure_log", "dst_long_pressure_log",
    "pair_short_count_log", "pair_long_count_log", "reverse_short_count_log", "reverse_long_count_log",
    "pair_response_seen_short", "pair_response_seen_long", "pair_forward_reverse_balance_long",
    "pair_syn_minus_ack_long", "pair_rst_rate_long", "file_short_count_log", "file_long_count_log",
    "file_short_unique_src_log", "file_long_unique_src_log", "file_short_unique_dst_log", "file_long_unique_dst_log",
    "file_short_pair_count_log", "file_long_pair_count_log", "src_count_accel", "src_fanout_accel",
    "src_port_expansion_accel", "dst_pressure_accel", "pair_burst_accel", "global_load_accel",
]


def log1p(value: float) -> float:
    return float(math.log1p(max(0.0, float(value))))


def entropy(values: list[int]) -> float:
    if not values:
        return 0.0
    counts = Counter(values)
    total = float(sum(counts.values()))
    return float(-sum((count / total) * math.log(count / total + 1e-12) for count in counts.values()))


def rate_log(events: deque[tuple[Any, ...]], window: float) -> float:
    return log1p(len(events) / max(1.0, window))


def ratio(short: float, long: float) -> float:
    return float(short / max(1.0, long))


def purge(events: deque[tuple[Any, ...]], now: float, window: float) -> None:
    limit = now - float(window)
    while events and float(events[0][0]) < limit:
        events.popleft()


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


class CanonicalEpisodeCache:
    def __init__(self, zip_path: Path):
        self.zip_path = Path(zip_path)
        if not self.zip_path.exists():
            raise FileNotFoundError(self.zip_path)

    def read_prefix(self, member: str, nrows: int) -> pd.DataFrame:
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not inside {self.zip_path}")
            with zf.open(member) as handle:
                return pd.read_csv(handle, usecols=lambda col: col in RAW_USECOLS, nrows=int(nrows), low_memory=False)

    def compute(self, member: str, target_indices: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
        targets = np.sort(np.unique(np.asarray(target_indices, dtype=np.int64)))
        if len(targets) == 0:
            return np.zeros((0, len(FEATURE_NAMES)), dtype=np.float32), [], {"source_group": member, "requested_rows": 0}
        if int(targets[0]) < 0:
            raise ValueError("negative recorded index")
        started = time.time()
        df = self.read_prefix(member, int(targets[-1]) + 1)
        if len(df) <= int(targets[-1]):
            raise RuntimeError(f"{member}: requested index {int(targets[-1])} but prefix has {len(df)} rows")
        seconds = ckat._raw_time_seconds(df.get("frame.time", pd.Series(np.nan, index=df.index)))
        order, finite, violations = ckat._canonical_order(seconds)
        finite_order = order[finite[order]]
        base = float(np.nanmin(seconds[finite])) if bool(finite.any()) else 0.0
        target_set = set(targets.tolist())
        features: dict[int, np.ndarray] = {}
        audits: list[dict[str, Any]] = []

        src_short: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        src_long: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        dst_short: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        dst_long: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        pair_short: dict[tuple[str, str], deque[tuple[Any, ...]]] = defaultdict(deque)
        pair_long: dict[tuple[str, str], deque[tuple[Any, ...]]] = defaultdict(deque)
        file_short: deque[tuple[Any, ...]] = deque()
        file_long: deque[tuple[Any, ...]] = deque()

        proto_text = df.get("frame.protocols", pd.Series("", index=df.index)).astype(str).to_numpy()
        ip_src = df.get("ip.src", pd.Series("", index=df.index)).to_numpy()
        ip_dst = df.get("ip.dst", pd.Series("", index=df.index)).to_numpy()
        eth_src = df.get("eth.src", pd.Series("", index=df.index)).to_numpy()
        eth_dst = df.get("eth.dst", pd.Series("", index=df.index)).to_numpy()
        frame_len = pd.to_numeric(df.get("frame.len", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        ip_proto = pd.to_numeric(df.get("ip.proto", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        tcp_src = pd.to_numeric(df.get("tcp.srcport", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        tcp_dst = pd.to_numeric(df.get("tcp.dstport", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        udp_src = pd.to_numeric(df.get("udp.srcport", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        udp_dst = pd.to_numeric(df.get("udp.dstport", pd.Series(0, index=df.index)), errors="coerce").fillna(0.0).to_numpy()
        flags = np.asarray([cko.parse_tcp_flags(value) for value in df.get("tcp.flags", pd.Series(0, index=df.index)).to_numpy()], dtype=np.int64)

        for ridx in targets.tolist():
            if not bool(finite[ridx]):
                features[ridx] = np.zeros(len(FEATURE_NAMES), dtype=np.float32)
                audits.append({"recorded_index": ridx, "alignment_ok": False, "raw_label_column_read": False, "chronology_status": "TARGET_TIMESTAMP_UNPARSEABLE"})

        for rank, ridx in enumerate(finite_order.tolist()):
            now = float(seconds[ridx] - base)
            proto = str(proto_text[ridx]).lower()
            src = cko.coalesce_str(ip_src[ridx], eth_src[ridx], f"row{ridx}:src")
            dst = cko.coalesce_str(ip_dst[ridx], eth_dst[ridx], f"row{ridx}:dst")
            is_tcp = int(ip_proto[ridx] == 6 or "tcp" in proto)
            is_udp = int(ip_proto[ridx] == 17 or "udp" in proto)
            is_icmp = int(ip_proto[ridx] == 1 or "icmp" in proto)
            dport = int(tcp_dst[ridx] if tcp_dst[ridx] > 0 else udp_dst[ridx])
            sport = int(tcp_src[ridx] if tcp_src[ridx] > 0 else udp_src[ridx])
            syn, ack, rst, fin = (int(bool(flags[ridx] & bit)) for bit in (0x02, 0x10, 0x04, 0x01))
            pair, reverse = (src, dst), (dst, src)
            for events, window in ((src_short[src], WINDOW_SHORT), (dst_short[dst], WINDOW_SHORT), (pair_short[pair], WINDOW_SHORT), (pair_short[reverse], WINDOW_SHORT), (file_short, WINDOW_SHORT), (src_long[src], WINDOW_LONG), (dst_long[dst], WINDOW_LONG), (pair_long[pair], WINDOW_LONG), (pair_long[reverse], WINDOW_LONG), (file_long, WINDOW_LONG)):
                purge(events, now, window)

            if ridx in target_set:
                ss, sl = src_short[src], src_long[src]
                ds, dl = dst_short[dst], dst_long[dst]
                ps, pl = pair_short[pair], pair_long[pair]
                rs, rl = pair_short[reverse], pair_long[reverse]
                fs, fl = file_short, file_long
                src_short_dst, src_long_dst = [e[2] for e in ss], [e[2] for e in sl]
                src_short_port, src_long_port = [e[4] for e in ss], [e[4] for e in sl]
                dst_short_src, dst_long_src = [e[1] for e in ds], [e[1] for e in dl]
                file_short_src, file_long_src = [e[1] for e in fs], [e[1] for e in fl]
                file_short_dst, file_long_dst = [e[2] for e in fs], [e[2] for e in fl]
                file_short_pairs, file_long_pairs = [(e[1], e[2]) for e in fs], [(e[1], e[2]) for e in fl]
                syn_pl, ack_pl, rst_pl = sum(e[6] for e in pl), sum(e[7] for e in pl), sum(e[8] for e in pl)
                values = [
                    log1p(frame_len[ridx]), is_tcp, is_udp, is_icmp, float(0 < dport <= 1024), syn, ack, rst, fin,
                    log1p(len(ss)), log1p(len(sl)), rate_log(ss, WINDOW_SHORT), rate_log(sl, WINDOW_LONG),
                    log1p(len(set(src_short_dst))), log1p(len(set(src_long_dst))), log1p(len(set(src_short_port))), log1p(len(set(src_long_port))),
                    entropy(src_short_port), entropy(src_long_port), float(dst not in set(src_long_dst)), float(dport not in set(src_long_port)),
                    log1p(len(set(dst_short_src))), log1p(len(set(dst_long_src))), rate_log(ds, WINDOW_SHORT), rate_log(dl, WINDOW_LONG),
                    log1p(len(ps)), log1p(len(pl)), log1p(len(rs)), log1p(len(rl)), float(bool(rs)), float(bool(rl)),
                    float((len(pl) - len(rl)) / max(1.0, len(pl) + len(rl))), float((syn_pl - ack_pl) / max(1.0, len(pl))), float(rst_pl / max(1.0, len(pl))),
                    log1p(len(fs)), log1p(len(fl)), log1p(len(set(file_short_src))), log1p(len(set(file_long_src))),
                    log1p(len(set(file_short_dst))), log1p(len(set(file_long_dst))), log1p(len(set(file_short_pairs))), log1p(len(set(file_long_pairs))),
                    ratio(len(ss), len(sl)), ratio(len(set(src_short_dst)), len(set(src_long_dst))), ratio(len(set(src_short_port)), len(set(src_long_port))),
                    ratio(len(set(dst_short_src)), len(set(dst_long_src))), ratio(len(ps), len(pl)), ratio(len(fs), len(fl)),
                ]
                if len(values) != len(FEATURE_NAMES):
                    raise RuntimeError(f"episode feature schema mismatch: {len(values)} vs {len(FEATURE_NAMES)}")
                features[ridx] = np.asarray(values, dtype=np.float32)
                audits.append({
                    "recorded_index": ridx, "alignment_ok": True, "raw_label_column_read": False,
                    "chronology_status": "CANONICAL_TIMESTAMP_PAST_ONLY", "canonical_rank": rank,
                    "episode_id": hashlib.sha256(f"{member}|{src}|{int(now // EPISODE_SECONDS)}".encode()).hexdigest()[:20],
                    "source_entity": src, "destination_entity": dst, "protocol_text": proto, "destination_port": dport,
                })

            event = (now, src, dst, sport, dport, float(frame_len[ridx]), syn, ack, rst, fin)
            src_short[src].append(event); src_long[src].append(event)
            dst_short[dst].append(event); dst_long[dst].append(event)
            pair_short[pair].append(event); pair_long[pair].append(event)
            file_short.append(event); file_long.append(event)

        matrix = np.vstack([features.get(int(index), np.zeros(len(FEATURE_NAMES), dtype=np.float32)) for index in targets]).astype(np.float32)
        summary = {
            "source_group": member, "requested_rows": int(len(targets)), "max_recorded_index": int(targets[-1]),
            "processed_prefix_rows": int(len(df)), "feature_dim": len(FEATURE_NAMES),
            "timestamp_parse_failures": int((~finite).sum()), "recorded_order_timestamp_violations": int(violations),
            "canonical_sort_policy": "timestamp_ascending_then_recorded_index_stable; target state strictly past-only",
            "raw_label_column_read": False, "seconds": time.time() - started,
        }
        return matrix, audits, summary


def plan_targets(path: Path, max_recorded_index: int, source_group: str = "") -> dict[str, np.ndarray]:
    frame = pd.read_csv(path, usecols=["source_group", "recorded_index"])
    frame["recorded_index"] = pd.to_numeric(frame["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    frame = frame[frame["recorded_index"] >= 0]
    if int(max_recorded_index) > 0:
        frame = frame[frame["recorded_index"] <= int(max_recorded_index)]
    if source_group:
        frame = frame[frame["source_group"].astype(str).eq(str(source_group))]
    return {str(source): np.sort(part["recorded_index"].unique()) for source, part in frame.groupby("source_group", sort=True)}


def run(args: argparse.Namespace) -> None:
    out = OUT_BASE if not args.run_tag else ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    targets = plan_targets(Path(args.target_index), int(args.max_recorded_index), str(args.source_group))
    if args.mode == "plan":
        plan_rows = [
            {"source_group": member, "source_cache_key": ckat.source_cache_key(member), "target_rows": int(len(indices)), "max_recorded_index": int(indices[-1])}
            for member, indices in sorted(targets.items())
        ]
        pd.DataFrame(plan_rows).to_csv(out / "episode_source_plan.csv", index=False)
        (out / "run_spec.json").write_text(json.dumps({"issue": ISSUE, "mode": "plan", "max_recorded_index": int(args.max_recorded_index), "sources": len(plan_rows), "targets": int(sum(row["target_rows"] for row in plan_rows))}, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": "plan_ok", "out": str(out), "sources": len(plan_rows)}, indent=2))
        return
    cache = CanonicalEpisodeCache(cko.GOTHAM_ZIP)
    summary_rows: list[dict[str, Any]] = []
    plan_rows: list[dict[str, Any]] = []
    for member, indices in targets.items():
        key = ckat.source_cache_key(member)
        plan_rows.append({"source_group": member, "source_cache_key": key, "target_rows": int(len(indices)), "max_recorded_index": int(indices[-1])})
        matrix, audits, summary = cache.compute(member, indices)
        np.savez_compressed(cache_dir / f"{key}.npz", recorded_index=indices, features=matrix)
        (cache_dir / f"{key}.json").write_text(json.dumps({"source_audit": summary, "target_audit": audits}, ensure_ascii=False) + "\n", encoding="utf-8")
        summary_rows.append(summary)
    pd.DataFrame(plan_rows).to_csv(out / "episode_source_plan.csv", index=False)
    pd.DataFrame(summary_rows).to_csv(out / "canonical_episode_cache_audit.csv", index=False)
    (out / "feature_schema.json").write_text(json.dumps({"feature_names": FEATURE_NAMES, "feature_dim": len(FEATURE_NAMES)}, indent=2) + "\n", encoding="utf-8")
    (out / "run_spec.json").write_text(json.dumps({
        "issue": ISSUE, "mode": "materialize", "max_recorded_index": int(args.max_recorded_index),
        "target_index": str(args.target_index), "cache_dir": str(cache_dir),
        "raw_label_column_read": False, "state_policy": "canonical timestamp, past-only", "episode_seconds": EPISODE_SECONDS,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "sources": len(summary_rows), "targets": int(sum(row["requested_rows"] for row in summary_rows))}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-index", default=str(DEFAULT_TARGETS))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--max-recorded-index", type=int, default=300_000)
    parser.add_argument("--run-tag", default="")
    parser.add_argument("--source-group", default="", help="materialize exactly one planned source (HPC array use)")
    parser.add_argument("--mode", choices=["plan", "materialize"], default="materialize")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
