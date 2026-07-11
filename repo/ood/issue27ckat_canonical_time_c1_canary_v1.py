"""issue27ckat: canonical-time C1 strict leave-device-family canary.

CKAI/CKAO established that CICFlow-style features are a strong Level-1
frontend, but their cache replayed raw files in recorded-index order.  CKAS
showed that this is not chronological for most relevant Gotham captures.

This is intentionally a *one-variable repair*: it retains CKAI's C1 feature
schema, HistGB backend, fit/select/report contract, and strict leave-family
protocol.  It changes only the state replay policy to:

    ascending frame.time, then recorded_index as a stable tie-breaker.

Raw packet labels are not read at all.  The unlabelled past stream may update
online state, exactly as it would at deployment, but no future row in that
canonical stream contributes to a current-row feature.

This is not the eventual mechanism-aware neural system.  It is the required
chronology-corrected representation control before that system is designed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import zipfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckat_canonical_time_c1_canary_v1_2026-07-10"
OUT_BASE = cko.ROOT / "runs" / ISSUE
EPISODE_SECONDS = 60

# Deliberately excludes the processed `label` column.  Role labels remain in
# the manifest frames and are used only by the inherited fit/evaluation code.
RAW_USECOLS = [column for column in ckai.PROCESSED_USECOLS if column != "label"]

CANONICAL_C1 = ckai.Candidate(
    "T1_cicflow_style_canonical_time_histgb",
    False,
    ("cicflow_style",),
    "histgb_shallow",
    "CKAI C1 schema under stable timestamp replay; raw labels are unread.",
)


def _raw_time_seconds(values: pd.Series) -> np.ndarray:
    parsed = pd.to_datetime(values, utc=True, errors="coerce")
    if int(parsed.notna().sum()) == 0:
        return pd.to_numeric(values, errors="coerce").to_numpy(dtype=np.float64)
    seconds = parsed.astype("int64", copy=False).to_numpy(dtype=np.float64) / 1e9
    seconds[parsed.isna().to_numpy()] = np.nan
    return seconds


def _canonical_order(seconds: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    positions = np.arange(len(seconds), dtype=np.int64)
    finite = np.isfinite(seconds)
    violations = int(np.sum(np.diff(seconds[finite]) < -1e-9)) if int(finite.sum()) >= 2 else 0
    # Missing timestamps never enter state.  They are stable-sorted last only
    # so their target rows can be explicitly marked unavailable rather than
    # silently receiving a synthetic chronology.
    order = np.lexsort((positions, np.where(finite, seconds, np.inf))).astype(np.int64)
    return order, finite, violations


def source_cache_key(source_group: str) -> str:
    return hashlib.sha256(str(source_group).encode("utf-8")).hexdigest()[:20]


class CanonicalTimeC1Cache:
    """CKAI-compatible cache with label-free canonical-time state replay."""

    def __init__(self, zip_path: Path, episode_seconds: int = EPISODE_SECONDS):
        if not zip_path.exists():
            raise FileNotFoundError(f"Missing Gotham raw zip: {zip_path}")
        self.zip_path = zip_path
        self.episode_seconds = int(episode_seconds)
        self._features: dict[str, dict[int, np.ndarray]] = {}
        self._audits: dict[str, dict[int, dict[str, Any]]] = {}
        self.audit_rows: list[dict[str, Any]] = []

    def _read_prefix(self, member: str, nrows: int) -> pd.DataFrame:
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as handle:
                return pd.read_csv(
                    handle,
                    usecols=lambda column: column in RAW_USECOLS,
                    nrows=max(0, int(nrows)),
                    low_memory=False,
                )

    def compute_member(self, member: str, row_indices: np.ndarray) -> None:
        target = sorted({int(value) for value in np.asarray(row_indices, dtype=np.int64) if int(value) >= 0})
        if not target:
            self._features.setdefault(member, {})
            self._audits.setdefault(member, {})
            return
        known = self._features.setdefault(member, {})
        if all(value in known for value in target):
            return

        max_row = max(target)
        started = time.time()
        df = self._read_prefix(member, max_row + 1)
        audits = self._audits.setdefault(member, {})
        if len(df) <= max_row:
            for ridx in target:
                known[ridx] = np.zeros(len(ckai.FEATURE_NAMES), dtype=np.float32)
                audits[ridx] = {
                    "alignment_ok": False,
                    "processed_row_exists": False,
                    "raw_label_column_read": False,
                    "chronology_status": "RECORDED_INDEX_OUT_OF_RANGE",
                }
            return

        seconds = _raw_time_seconds(df.get("frame.time", pd.Series(np.nan, index=df.index)))
        order, finite, violations = _canonical_order(seconds)
        finite_order = order[finite[order]]
        base_time = float(np.min(seconds[finite])) if bool(finite.any()) else 0.0
        normalized_time = seconds - base_time

        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        frame_len_raw = cko.safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0)
        frame_len_log = np.log1p(frame_len_raw)
        ip_proto = cko.safe_num(df.get("ip.proto", pd.Series([0] * len(df))), 0.0)
        ip_ttl = cko.safe_num(df.get("ip.ttl", pd.Series([0] * len(df))), 0.0)
        tcp_src = cko.safe_num(df.get("tcp.srcport", pd.Series([0] * len(df))), 0.0)
        tcp_dst = cko.safe_num(df.get("tcp.dstport", pd.Series([0] * len(df))), 0.0)
        udp_src = cko.safe_num(df.get("udp.srcport", pd.Series([0] * len(df))), 0.0)
        udp_dst = cko.safe_num(df.get("udp.dstport", pd.Series([0] * len(df))), 0.0)
        tcp_window = cko.safe_num(df.get("tcp.window_size_value", pd.Series([0] * len(df))), 0.0)
        tcp_pdu = cko.safe_num(df.get("tcp.pdu.size", pd.Series([0] * len(df))), 0.0)
        tcp_flags = [cko.parse_tcp_flags(value) for value in df.get("tcp.flags", pd.Series([0] * len(df))).to_numpy()]
        ip_src = df.get("ip.src", pd.Series([""] * len(df))).to_numpy()
        ip_dst = df.get("ip.dst", pd.Series([""] * len(df))).to_numpy()
        eth_src = df.get("eth.src", pd.Series([""] * len(df))).to_numpy()
        eth_dst = df.get("eth.dst", pd.Series([""] * len(df))).to_numpy()

        target_set = set(target)
        for ridx in target:
            if not bool(finite[ridx]):
                known[ridx] = np.zeros(len(ckai.FEATURE_NAMES), dtype=np.float32)
                audits[ridx] = {
                    "alignment_ok": False,
                    "processed_row_exists": True,
                    "raw_label_column_read": False,
                    "chronology_status": "TARGET_TIMESTAMP_UNPARSEABLE",
                }

        file_state = {window: deque(maxlen=window) for window in ckai.WINDOWS}
        src_state: dict[str, dict[int, deque[tuple[Any, ...]]]] = defaultdict(
            lambda: {window: deque(maxlen=window) for window in ckai.WINDOWS}
        )
        dst_state: dict[str, dict[int, deque[tuple[Any, ...]]]] = defaultdict(
            lambda: {window: deque(maxlen=window) for window in ckai.WINDOWS}
        )
        pair_state: dict[tuple[str, str], dict[int, deque[tuple[Any, ...]]]] = defaultdict(
            lambda: {window: deque(maxlen=window) for window in ckai.WINDOWS}
        )
        biflow_state: dict[tuple[Any, ...], dict[int, deque[tuple[Any, ...]]]] = defaultdict(
            lambda: {window: deque(maxlen=window) for window in ckai.WINDOWS}
        )
        flow5_state: dict[tuple[Any, ...], dict[int, deque[tuple[Any, ...]]]] = defaultdict(
            lambda: {window: deque(maxlen=window) for window in ckai.WINDOWS}
        )

        for canonical_rank, ridx in enumerate(finite_order.tolist()):
            proto = str(proto_text[ridx]).lower()
            is_tcp = int(ip_proto[ridx] == 6 or tcp_src[ridx] > 0 or tcp_dst[ridx] > 0 or "tcp" in proto)
            is_udp = int(ip_proto[ridx] == 17 or udp_src[ridx] > 0 or udp_dst[ridx] > 0 or "udp" in proto)
            is_icmp = int(ip_proto[ridx] == 1 or "icmp" in proto)
            sport = float(tcp_src[ridx] if tcp_src[ridx] > 0 else udp_src[ridx])
            dport = float(tcp_dst[ridx] if tcp_dst[ridx] > 0 else udp_dst[ridx])
            sport_i = int(sport) if np.isfinite(sport) and sport > 0 else 0
            dport_i = int(dport) if np.isfinite(dport) and dport > 0 else 0
            flags = int(tcp_flags[ridx])
            syn = int(bool(flags & 0x02))
            ack = int(bool(flags & 0x10))
            rst = int(bool(flags & 0x04))
            fin = int(bool(flags & 0x01))
            src = cko.coalesce_str(ip_src[ridx], eth_src[ridx], f"row{ridx}:src")
            dst = cko.coalesce_str(ip_dst[ridx], eth_dst[ridx], f"row{ridx}:dst")
            pair = (src, dst)
            rev_pair = (dst, src)
            proto_i = int(ip_proto[ridx]) if np.isfinite(ip_proto[ridx]) else 0
            endpoint_a, endpoint_b = sorted([(src, sport_i), (dst, dport_i)])
            biflow = (endpoint_a, endpoint_b, proto_i)
            flow5 = (src, dst, proto_i, sport_i, dport_i)
            current_ts = float(normalized_time[ridx])

            current = [
                float(frame_len_log[ridx]), float(is_tcp), float(is_udp), float(is_icmp),
                ckai.log1p(sport), ckai.log1p(dport), float(0 < dport <= 1024),
                float(dport_i == 53 or "dns" in proto), float(dport_i == 5683 or "coap" in proto),
                float(dport_i in {80, 8080} or "http" in proto), float(dport_i == 443 or "tls" in proto or "ssl" in proto),
                float(syn), float(ack), float(rst), float(fin), float(syn and not ack), float(ack and not syn),
                float(np.clip(ip_ttl[ridx] / 255.0, 0.0, 1.0)) if np.isfinite(ip_ttl[ridx]) else 0.0,
                ckai.log1p(tcp_window[ridx]), ckai.log1p(tcp_pdu[ridx]),
            ]

            if ridx in target_set:
                vals = list(current)
                for window in ckai.WINDOWS:
                    states = {
                        "file": file_state[window], "src": src_state[src][window], "dst": dst_state[dst][window],
                        "pair": pair_state[pair][window], "rev_pair": pair_state[rev_pair][window],
                        "biflow": biflow_state[biflow][window], "flow5": flow5_state[flow5][window],
                    }
                    for name in ["file", "src", "dst", "pair", "rev_pair", "biflow", "flow5"]:
                        vals.extend(ckai.state_features(states[name], window, current_ts))
                    fwd, rev = states["pair"], states["rev_pair"]
                    srcs, dsts, files, bi, flow = states["src"], states["dst"], states["file"], states["biflow"], states["flow5"]
                    vals.extend(
                        [
                            float(len(rev) > 0),
                            ckai.safe_div(len(fwd) - len(rev), len(fwd) + len(rev) + 1e-6),
                            ckai.safe_div(ckai.byte_sum(fwd) - ckai.byte_sum(rev), ckai.byte_sum(fwd) + ckai.byte_sum(rev) + 1.0),
                            ckai.safe_div(len(srcs), len(files) + 1e-6),
                            ckai.safe_div(ckai.byte_sum(srcs), ckai.byte_sum(files) + 1.0),
                            ckai.safe_div(len(dsts), len(files) + 1e-6),
                            ckai.safe_div(ckai.byte_sum(dsts), ckai.byte_sum(files) + 1.0),
                            ckai.safe_div(len(flow), len(bi) + 1e-6),
                        ]
                    )
                for short, long in [(16, 128)]:
                    vals.extend(
                        [
                            ckai.safe_div(len(src_state[src][short]), len(src_state[src][long]) + 1e-6),
                            ckai.safe_div(len({row[13] for row in src_state[src][short]}), len({row[13] for row in src_state[src][long]}) + 1e-6),
                            ckai.safe_div(len({row[10] for row in dst_state[dst][short]}), len({row[10] for row in dst_state[dst][long]}) + 1e-6),
                            ckai.safe_div(len(pair_state[pair][short]), len(pair_state[pair][long]) + 1e-6),
                            ckai.safe_div(len(flow5_state[flow5][short]), len(flow5_state[flow5][long]) + 1e-6),
                            ckai.safe_div(len(biflow_state[biflow][short]), len(biflow_state[biflow][long]) + 1e-6),
                        ]
                    )
                if len(vals) != len(ckai.FEATURE_NAMES):
                    raise RuntimeError(f"C1 schema drift: got {len(vals)}, expected {len(ckai.FEATURE_NAMES)}")
                bucket = int(np.floor(current_ts / max(1, self.episode_seconds)))
                episode_id = hashlib.sha256(f"{member}|{src}|{bucket}".encode("utf-8")).hexdigest()[:20]
                known[ridx] = np.asarray(vals, dtype=np.float32)
                audits[ridx] = {
                    "alignment_ok": True,
                    "processed_row_exists": True,
                    "raw_label_column_read": False,
                    "processed_frame_time": str(df["frame.time"].iloc[ridx]),
                    "processed_frame_protocols": proto_text[ridx],
                    "processed_frame_len": float(frame_len_raw[ridx]),
                    "processed_src": src,
                    "processed_dst": dst,
                    "processed_src_port": sport_i,
                    "processed_dst_port": dport_i,
                    "processed_ip_proto": proto_i,
                    "processed_tcp_flags": flags,
                    "canonical_rank": int(canonical_rank),
                    "episode_id": episode_id,
                    "prior_file_rows_w128": int(len(file_state[128])),
                    "chronology_status": "CANONICAL_TIMESTAMP_REPLAY",
                }

            row = (current_ts, float(frame_len_log[ridx]), float(frame_len_raw[ridx]), is_tcp, is_udp, is_icmp, syn, ack, rst, fin, src, dst, sport_i, dport_i)
            for window in ckai.WINDOWS:
                file_state[window].append(row)
                src_state[src][window].append(row)
                dst_state[dst][window].append(row)
                pair_state[pair][window].append(row)
                biflow_state[biflow][window].append(row)
                flow5_state[flow5][window].append(row)

        self.audit_rows.append(
            {
                "source_group": member,
                "requested_rows": len(target),
                "max_recorded_index": int(max_row),
                "processed_prefix_rows": int(len(df)),
                "feature_dim": len(ckai.FEATURE_NAMES),
                "timestamp_parse_failures": int((~finite).sum()),
                "recorded_order_timestamp_violations": int(violations),
                "canonical_state_rows": int(len(finite_order)),
                "canonical_sort_policy": "timestamp_ascending_then_recorded_index_stable; missing_timestamp_excluded_from_state",
                "raw_label_column_read": False,
                "seconds": time.time() - started,
            }
        )

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        self.compute_member(member, row_indices)
        return self._features.get(member, {})

    def audit_for_member(self, member: str) -> dict[int, dict[str, Any]]:
        return self._audits.get(member, {})


def attach_episode_metadata(parts: list[pd.DataFrame], cache: CanonicalTimeC1Cache) -> tuple[list[pd.DataFrame], list[dict[str, Any]]]:
    enriched: list[pd.DataFrame] = []
    for part in parts:
        if part.empty:
            continue
        work = part.copy()
        episode_ids: list[str] = []
        for _, row in work.iterrows():
            audit = cache.audit_for_member(str(row.get("source_group", ""))).get(int(row.get("recorded_index", -1)), {})
            episode_ids.append(str(audit.get("episode_id", "")))
        work["episode_id"] = episode_ids
        enriched.append(work)
    if not enriched:
        return [], []
    combined = pd.concat(enriched, ignore_index=True)
    combined = combined[combined["episode_id"].astype(str).ne("")].copy()
    rows: list[dict[str, Any]] = []
    for keys, group in combined.groupby(["held_value", "role", "role_kind", "episode_id"], sort=True):
        rows.append(
            {
                "held_value": keys[0], "role": keys[1], "role_kind": keys[2], "episode_id": keys[3],
                "flow_rows": int(len(group)), "hard_flow_rows": int(group["hard_alarm"].sum()),
                "episode_has_hard": bool(group["hard_alarm"].any()),
            }
        )
    return enriched, rows


def build_source_load_plan(
    frame_by_role: dict[str, pd.DataFrame],
    selected_groups: list[dict[str, Any]],
    train_cap: int,
    eval_cap: int,
) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    """Plan one reusable canonical cache per raw source, without raw reads.

    The union is deliberately across all five held-family folds.  A later HPC
    array can materialize every source once and reuse its cache for all folds,
    avoiding the failed 148199 pattern of repeatedly rebuilding frontends.
    """
    requested: list[pd.DataFrame] = []
    for held in selected_groups:
        value = str(held["held_value"])
        specs = [
            ("support_train", "fit", cko.FULL_CAP, ("device_family", value), "fit"),
            ("id_calib", "fit", train_cap, ("device_family", value), "fit"),
            ("ood_val", "fit", train_cap, ("device_family", value), "fit"),
            ("ood_stress", "fit", train_cap, ("device_family", value), "fit"),
            ("id_calib", "select", eval_cap, ("device_family", value), "select"),
            ("ood_val", "select", eval_cap, ("device_family", value), "select"),
            ("ood_stress", "select", eval_cap, ("device_family", value), "select"),
            ("support_val", "select", eval_cap, ("device_family", value), "select"),
        ]
        for role, phase, cap, exclude, stage in specs:
            idx = ckao.role_indices_filtered(frame_by_role, role, phase, cap, exclude=exclude)
            if len(idx):
                requested.append(frame_by_role[role].iloc[idx][["source_group", "recorded_index"]].assign(fold=value, stage=stage, role=role))
        for role, phase, _kind in cko.ROLE_EVAL:
            idx = ckao.role_indices_filtered(frame_by_role, role, phase, eval_cap, include=("device_family", value))
            if len(idx):
                requested.append(frame_by_role[role].iloc[idx][["source_group", "recorded_index"]].assign(fold=value, stage="report", role=role))
    if not requested:
        return [], {"source_count": 0, "unique_target_rows": 0, "sum_prefix_rows": 0, "max_source_prefix_rows": 0}, []
    work = pd.concat(requested, ignore_index=True)
    work["recorded_index"] = pd.to_numeric(work["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    work = work[work["recorded_index"] >= 0].copy()
    rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for source, group in work.groupby(work["source_group"].astype(str), sort=True):
        unique_rows = group[["source_group", "recorded_index"]].drop_duplicates()
        max_idx = int(group["recorded_index"].max())
        cache_key = source_cache_key(source)
        rows.append(
            {
                "source_group": source,
                "source_cache_key": cache_key,
                "requested_unique_rows": int(len(unique_rows)),
                "max_recorded_index": max_idx,
                "prefix_rows_to_read": int(max_idx + 1),
                "folds": ";".join(sorted(group["fold"].astype(str).unique().tolist())),
                "stages": ";".join(sorted(group["stage"].astype(str).unique().tolist())),
                "roles": ";".join(sorted(group["role"].astype(str).unique().tolist())),
            }
        )
        for ridx, target_part in group.groupby("recorded_index", sort=True):
            target_rows.append(
                {
                    "source_group": source,
                    "source_cache_key": cache_key,
                    "recorded_index": int(ridx),
                    "folds": ";".join(sorted(target_part["fold"].astype(str).unique().tolist())),
                    "stages": ";".join(sorted(target_part["stage"].astype(str).unique().tolist())),
                    "roles": ";".join(sorted(target_part["role"].astype(str).unique().tolist())),
                }
            )
    return rows, {
        "source_count": int(len(rows)),
        "unique_target_rows": int(len(work[["source_group", "recorded_index"]].drop_duplicates())),
        "sum_prefix_rows": int(sum(row["prefix_rows_to_read"] for row in rows)),
        "max_source_prefix_rows": int(max((row["prefix_rows_to_read"] for row in rows), default=0)),
    }, target_rows


class PersistentCanonicalTimeC1Cache:
    """Read-only, source-scoped canonical feature cache for the full L2 run."""

    def __init__(self, cache_dir: Path, source_plan_csv: Path):
        self.cache_dir = Path(cache_dir)
        plan = pd.read_csv(source_plan_csv)
        self.keys = {str(row["source_group"]): str(row["source_cache_key"]) for _, row in plan.iterrows()}
        self._features: dict[str, dict[int, np.ndarray]] = {}
        self._audits: dict[str, dict[int, dict[str, Any]]] = {}
        self.audit_rows: list[dict[str, Any]] = []

    def _load(self, member: str) -> None:
        if member in self._features:
            return
        key = self.keys.get(member)
        if not key:
            raise KeyError(f"No source-cache key recorded for {member}")
        npz_path = self.cache_dir / f"{key}.npz"
        json_path = self.cache_dir / f"{key}.json"
        if not npz_path.exists() or not json_path.exists():
            raise FileNotFoundError(f"Missing canonical source cache for {member}: {npz_path}")
        payload = np.load(npz_path, allow_pickle=False)
        indices = np.asarray(payload["recorded_index"], dtype=np.int64)
        features = np.asarray(payload["features"], dtype=np.float32)
        if len(indices) != len(features) or features.ndim != 2 or features.shape[1] != len(ckai.FEATURE_NAMES):
            raise RuntimeError(f"Malformed source cache: {npz_path}")
        with json_path.open("r", encoding="utf-8") as handle:
            audit = json.load(handle)
        self._features[member] = {int(index): features[pos] for pos, index in enumerate(indices.tolist())}
        meta = dict(audit.get("source_audit", {}))
        meta["source_group"] = member
        meta["cache_path"] = str(npz_path)
        self.audit_rows.append(meta)
        row_meta = {int(item["recorded_index"]): item for item in audit.get("target_audit", [])}
        self._audits[member] = row_meta

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        self._load(member)
        features = self._features[member]
        missing = [int(value) for value in np.asarray(row_indices, dtype=np.int64) if int(value) not in features]
        if missing:
            raise RuntimeError(f"Canonical source cache lacks {len(missing)} requested rows for {member}; first={missing[0]}")
        return features

    def audit_for_member(self, member: str) -> dict[int, dict[str, Any]]:
        self._load(member)
        return self._audits[member]


def cached_target_alignment_audit(cache: PersistentCanonicalTimeC1Cache) -> list[dict[str, Any]]:
    """Audit exactly the immutable planned targets, never arbitrary frame.head rows.

    The ordinary CKAI alignment audit samples `frame.head()`.  That is sound
    for an on-demand cache, but it is deliberately outside the source-target
    manifest in this immutable full-support cache.  Auditing the manifest is
    both stricter and avoids a false missing-cache failure after training.
    """
    rows: list[dict[str, Any]] = []
    for member in sorted(cache._audits):
        target_audit = cache._audits[member]
        values = list(target_audit.values())
        rows.append(
            {
                "source_group": member,
                "planned_target_rows": int(len(values)),
                "alignment_ok_rows": int(sum(bool(item.get("alignment_ok", False)) for item in values)),
                "all_planned_targets_aligned": bool(values) and all(bool(item.get("alignment_ok", False)) for item in values),
                "raw_label_column_read": False,
                "audit_scope": "immutable_source_target_manifest",
            }
        )
    return rows


def materialize_source_cache(args: argparse.Namespace) -> None:
    if not args.cache_dir or not args.source_plan or not args.source_targets:
        raise ValueError("source-cache mode requires --cache-dir --source-plan --source-targets")
    source_plan = pd.read_csv(Path(args.source_plan))
    source_plan = source_plan.sort_values("source_group", kind="stable").reset_index(drop=True)
    if int(args.source_index) < 0 or int(args.source_index) >= len(source_plan):
        raise IndexError(f"--source-index must be in [0, {len(source_plan) - 1}]")
    selected = source_plan.iloc[int(args.source_index)]
    member = str(selected["source_group"])
    key = str(selected["source_cache_key"])
    target_frame = pd.read_csv(Path(args.source_targets))
    target_frame = target_frame[target_frame["source_group"].astype(str).eq(member)].copy()
    indices = np.sort(pd.to_numeric(target_frame["recorded_index"], errors="coerce").dropna().astype(np.int64).unique())
    if not len(indices):
        raise RuntimeError(f"No target indices for source {member}")
    cache = CanonicalTimeC1Cache(cko.GOTHAM_ZIP, int(args.episode_seconds))
    features = cache.features_for_member(member, indices)
    matrix = np.vstack([features[int(index)] for index in indices]).astype(np.float32)
    audits = cache.audit_for_member(member)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cache_dir / f"{key}.npz", recorded_index=indices, features=matrix)
    target_audit = []
    for index in indices.tolist():
        item = dict(audits.get(int(index), {}))
        item["recorded_index"] = int(index)
        target_audit.append(item)
    cko.write_json(
        cache_dir / f"{key}.json",
        {
            "source_group": member,
            "source_cache_key": key,
            "feature_schema_hash": hashlib.sha256("\n".join(ckai.FEATURE_NAMES).encode("utf-8")).hexdigest(),
            "raw_label_column_read": False,
            "source_audit": cache.audit_rows[-1] if cache.audit_rows else {},
            "target_audit": target_audit,
        },
    )
    print(json.dumps({"status": "ok", "source_index": int(args.source_index), "source_group": member, "cache_key": key, "rows": int(len(indices))}, ensure_ascii=False, indent=2))


def build_readout(selected_groups: list[dict[str, Any]], role_rows: list[dict[str, Any]], cache_rows: list[dict[str, Any]], episode_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        f"# {ISSUE}", "", "## Verdict", "",
        "`CANONICAL_TIME_C1_STRICT_LEAVE_CANARY_COMPLETED`", "",
        "## Contract", "",
        "- Same C1 CICFlow-style feature schema and HistGB protocol as CKAO.",
        "- The only representation change is label-free canonical timestamp replay.",
        "- Raw processed labels are not read; query/future/sealed labels remain report-only.",
        "- Fit and threshold roles exclude the held device family; evaluation includes only it.", "",
        "## Held-family evaluation", "",
        "| held family | role | rows | hard rate | desired | error |", "|---|---|---:|---:|---|---:|",
    ]
    for row in role_rows:
        if row["role"] in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
            lines.append(f"| {row['held_value']} | {row['role']} | {row['rows']} | {cko.fmt(row['hard_alarm_rate'])} | {row['desired_hard_direction']} | {cko.fmt(row['error_rate_for_role'])} |")
    canonical_required = sum(int(row.get("recorded_order_timestamp_violations", 0)) > 0 for row in cache_rows)
    episode_count = len({str(row.get("episode_id", "")) for row in episode_rows if str(row.get("episode_id", ""))})
    lines.extend(
        ["", "## Extraction audit", "", f"- Sources requiring canonical replay: `{canonical_required}` / `{len(cache_rows)}`.", f"- Label-free episode records: `{episode_count}`.", f"- Runtime seconds: `{seconds:.1f}`.", "", "## Interpretation boundary", "", "- Compare this only against the matched CKAO 300k C1 canary; it is not a claim that Level-2 is solved.", "- No review gate, prototype loss, GroupDRO/REx, DANN, or report-set tuning is used here."],
    )
    return lines


def run(args: argparse.Namespace) -> None:
    if args.mode == "source-cache":
        materialize_source_cache(args)
        return
    started = time.time()
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(not bool(args.full))
    x_by_role, frame_by_role, cap_rows = ckai.filter_roles_by_recorded_index(x_by_role, frame_by_role, int(args.max_recorded_index))
    ckao.add_family_columns(frame_by_role)
    selected_groups = ckao.select_leave_groups(frame_by_role, int(args.eval_cap), int(args.max_leave_groups), int(args.min_eval_rows), str(args.held_values))
    if not selected_groups:
        raise RuntimeError("No held device-family groups selected")
    preflight_rows = ckao.build_preflight_audit(frame_by_role, selected_groups, int(args.train_cap), int(args.eval_cap))
    if not all(bool(row.get("pass_no_held_leakage", True)) and bool(row.get("pass_eval_only_held", True)) for row in preflight_rows):
        raise RuntimeError("Strict leave-family preflight failed")
    source_load_plan, source_load_summary, source_target_rows = build_source_load_plan(frame_by_role, selected_groups, int(args.train_cap), int(args.eval_cap))
    if args.mode == "preflight":
        cko.write_csv(out / "selected_leave_groups.csv", selected_groups)
        cko.write_csv(out / "strict_leave_preflight_audit.csv", preflight_rows)
        cko.write_csv(out / "role_cap_audit.csv", cap_rows)
        cko.write_csv(out / "canonical_source_load_plan.csv", source_load_plan)
        cko.write_csv(out / "canonical_source_target_index.csv", source_target_rows)
        cko.write_json(out / "source_load_summary.json", source_load_summary)
        print(json.dumps({"status": "ok", "mode": "preflight", "out": str(out)}, ensure_ascii=False, indent=2))
        return

    cache = (
        PersistentCanonicalTimeC1Cache(Path(args.cache_dir), Path(args.source_plan))
        if args.cache_dir
        else CanonicalTimeC1Cache(cko.GOTHAM_ZIP, int(args.episode_seconds))
    )
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    part_frames: list[pd.DataFrame] = []
    for held in selected_groups:
        held_value = str(held["held_value"])
        model, audit = ckao.fit_candidate(CANONICAL_C1, frontend, frame_by_role, held_value, int(args.train_cap))
        train_rows.extend(audit)
        threshold, rows = ckao.attack_threshold(CANONICAL_C1, model, frontend, frame_by_role, held_value, int(args.eval_cap))
        threshold_rows.extend(rows)
        for role, phase, kind in cko.ROLE_EVAL:
            record, part = ckao.eval_held_role(CANONICAL_C1, model, threshold, frontend, frame_by_role, held_value, role, phase, kind, int(args.eval_cap))
            role_rows.append(record)
            part_frames.append(part)
    enriched_parts, episode_rows = attach_episode_metadata(part_frames, cache)
    seconds = time.time() - started
    cko.write_csv(out / "selected_leave_groups.csv", selected_groups)
    cko.write_csv(out / "strict_leave_preflight_audit.csv", preflight_rows)
    cko.write_csv(out / "role_cap_audit.csv", cap_rows)
    cko.write_csv(out / "canonical_source_load_plan.csv", source_load_plan)
    cko.write_csv(out / "canonical_source_target_index.csv", source_target_rows)
    cko.write_csv(out / "canonical_extraction_audit.csv", cache.audit_rows)
    alignment_rows = cached_target_alignment_audit(cache) if isinstance(cache, PersistentCanonicalTimeC1Cache) else frontend.alignment_audit()
    cko.write_csv(out / "canonical_alignment_audit.csv", alignment_rows)
    cko.write_csv(out / "leave_role_metrics.csv", role_rows)
    cko.write_csv(out / "leave_train_audit.csv", train_rows)
    cko.write_csv(out / "leave_threshold_audit.csv", threshold_rows)
    cko.write_csv(out / "episode_hard_summary.csv", episode_rows)
    cko.write_csv(out / "attack_family_summary.csv", ckai.family_summary(enriched_parts))
    cko.write_csv(out / "source_group_summary.csv", ckai.grouped_performance_summary(enriched_parts, "source_group", min_rows=int(args.group_min_rows)))
    cko.write_md(out / "codex_readout.md", build_readout(selected_groups, role_rows, cache.audit_rows, episode_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE, "mode": args.mode, "full": bool(args.full), "max_recorded_index": int(args.max_recorded_index),
            "train_cap": int(args.train_cap), "eval_cap": int(args.eval_cap), "selected_leave_groups": selected_groups,
            "data_use_boundary": {
                "fit_and_threshold_exclude_held_device_family": True,
                "report_roles_used_for_fit_threshold_feature_selection": False,
                "raw_processed_label_column_read": False,
                "state_policy": "canonical timestamp ascending, stable recorded_index tie-breaker, past-only",
                "source_cache_dir": str(args.cache_dir) if args.cache_dir else "in_memory_local",
            },
            "input_audit": input_audit, "role_cap_audit": cap_rows, "source_load_summary": source_load_summary, "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "held_groups": [row["held_value"] for row in selected_groups], "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["preflight", "source-cache", "smoke"], default="preflight")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--max-recorded-index", type=int, default=300000)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--max-leave-groups", type=int, default=5)
    parser.add_argument("--min-eval-rows", type=int, default=128)
    parser.add_argument("--held-values", default="")
    parser.add_argument("--group-min-rows", type=int, default=30)
    parser.add_argument("--episode-seconds", type=int, default=60)
    parser.add_argument("--cache-dir", default="", help="Optional immutable canonical source-cache directory for smoke mode.")
    parser.add_argument("--source-plan", default="", help="CSV emitted by preflight; required for source-cache and cached smoke.")
    parser.add_argument("--source-targets", default="", help="CSV emitted by preflight; required for source-cache.")
    parser.add_argument("--source-index", type=int, default=-1, help="Zero-based source array index for source-cache mode.")
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
