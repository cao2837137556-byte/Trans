"""issue27ckai: external-style flow feature probe v1.

This is a route reset away from hand-written Kitsune115D patches.  The goal is
to test whether a more standard IDS frontend -- Zeek/NFStream/NetFlow-style
flow semantics -- gives better attack-vs-OOD evidence.

Important boundary:

* The extractor is row-aligned to Gotham processed CSV rows through
  `source_group` + `recorded_index`.
* Features use packet fields only and past-only flow state before the current
  row.  The processed `label` column is read only for extraction/alignment
  audit, never as a feature.
* Fit: support_train/id_calib/ood_val/ood_stress fit only.
* Threshold: id_calib/ood_val/ood_stress/support_val select only.
* query/future/sealed roles are report-only.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import zipfile
from collections import defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402


ISSUE = "issue27ckai_external_flow_feature_probe_v1_2026-07-06"
OUT = cko.ROOT / "runs" / ISSUE
WINDOWS = [16, 128]
BENIGN_Q = 0.99
FULL_CAP = cko.FULL_CAP

PROCESSED_USECOLS = [
    "frame.time",
    "frame.len",
    "frame.protocols",
    "eth.src",
    "eth.dst",
    "ip.dst",
    "ip.src",
    "ip.flags",
    "ip.ttl",
    "ip.proto",
    "ip.tos",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.pdu.size",
    "udp.srcport",
    "udp.dstport",
    # Audit only; never a feature.
    "label",
]

CURRENT_FEATURES = [
    "cur_len_log",
    "cur_is_tcp",
    "cur_is_udp",
    "cur_is_icmp",
    "cur_sport_log",
    "cur_dport_log",
    "cur_well_known",
    "cur_dns",
    "cur_coap",
    "cur_http",
    "cur_tls",
    "cur_tcp_syn",
    "cur_tcp_ack",
    "cur_tcp_rst",
    "cur_tcp_fin",
    "cur_syn_without_ack",
    "cur_ack_without_syn",
    "cur_ttl_norm",
    "cur_tcp_window_log",
    "cur_tcp_pdu_log",
]

STATE_BASE = [
    "count_frac",
    "duration_log",
    "iat_last_log",
    "iat_mean_log",
    "iat_std_log",
    "pkt_rate_log",
    "byte_rate_log",
    "len_min_log",
    "len_mean_log",
    "len_max_log",
    "len_std_log",
    "tcp_rate",
    "udp_rate",
    "icmp_rate",
    "syn_rate",
    "ack_rate",
    "rst_rate",
    "fin_rate",
    "unique_src_frac",
    "unique_dst_frac",
    "unique_sport_frac",
    "unique_dport_frac",
]


def state_names(prefix: str) -> list[str]:
    return [f"{prefix}_{name}" for name in STATE_BASE]


FEATURE_NAMES = list(CURRENT_FEATURES)
for window in WINDOWS:
    for scope in ["file", "src", "dst", "pair", "rev_pair", "biflow", "flow5"]:
        FEATURE_NAMES.extend(state_names(f"{scope}_w{window}"))
    FEATURE_NAMES.extend(
        [
            f"pair_rev_seen_w{window}",
            f"pair_fwd_rev_count_balance_w{window}",
            f"pair_fwd_rev_byte_balance_w{window}",
            f"src_to_file_count_ratio_w{window}",
            f"src_to_file_byte_ratio_w{window}",
            f"dst_to_file_count_ratio_w{window}",
            f"dst_to_file_byte_ratio_w{window}",
            f"flow_to_biflow_count_ratio_w{window}",
        ]
    )
for short, long in [(16, 128)]:
    FEATURE_NAMES.extend(
        [
            f"src_count_short_long_ratio_w{short}_{long}",
            f"src_dport_fanout_short_long_ratio_w{short}_{long}",
            f"dst_src_pressure_short_long_ratio_w{short}_{long}",
            f"pair_count_short_long_ratio_w{short}_{long}",
            f"flow5_count_short_long_ratio_w{short}_{long}",
            f"biflow_count_short_long_ratio_w{short}_{long}",
        ]
    )


EXTERNAL_BLOCK_ORDER = ["graph_interaction", "zeek_semantic", "netflow_style", "cicflow_style"]


def feature_blocks_for_name(name: str) -> list[str]:
    """Assign one engineered feature to one or more interpretable frontend blocks.

    Blocks are intentionally overlapping: a SYN rate can be both Zeek-like
    protocol semantics and CICFlowMeter-like TCP flag statistics.  Smoke
    candidates select block unions, so overlap is harmless and auditable.
    """
    blocks: set[str] = set()
    if name.startswith("cur_"):
        if any(k in name for k in ["is_tcp", "is_udp", "is_icmp", "dns", "coap", "http", "tls", "well_known", "tcp_", "syn", "ack", "rst", "fin", "ttl"]):
            blocks.add("zeek_semantic")
        if any(k in name for k in ["len", "sport", "dport", "tcp_window", "tcp_pdu", "syn", "ack", "rst", "fin"]):
            blocks.add("cicflow_style")
        if any(k in name for k in ["len", "sport", "dport", "is_tcp", "is_udp", "is_icmp"]):
            blocks.add("netflow_style")
    if any(k in name for k in ["unique_", "fanout", "pressure", "to_file", "rev_seen", "count_balance", "byte_balance", "short_long"]):
        blocks.add("graph_interaction")
    if name.startswith(("pair_", "rev_pair_", "biflow_", "flow5_")) or "flow_to_biflow" in name:
        blocks.add("netflow_style")
    if any(k in name for k in ["duration", "iat_", "pkt_rate", "byte_rate", "len_", "syn_rate", "ack_rate", "rst_rate", "fin_rate"]):
        blocks.add("cicflow_style")
    if any(k in name for k in ["tcp_rate", "udp_rate", "icmp_rate", "syn_rate", "ack_rate", "rst_rate", "fin_rate"]):
        blocks.add("zeek_semantic")
    if not blocks:
        blocks.add("graph_interaction")
    return [b for b in EXTERNAL_BLOCK_ORDER if b in blocks]


FEATURE_BLOCK_MEMBERS = {name: feature_blocks_for_name(name) for name in FEATURE_NAMES}
FEATURE_BLOCK_COLUMNS = {
    block: [idx for idx, name in enumerate(FEATURE_NAMES) if block in FEATURE_BLOCK_MEMBERS[name]]
    for block in EXTERNAL_BLOCK_ORDER
}


@dataclass(frozen=True)
class Candidate:
    name: str
    include_raw: bool
    external_blocks: tuple[str, ...]
    model: str
    description: str


CANDIDATES = [
    Candidate(
        "R0_raw115_only_histgb",
        True,
        tuple(),
        "histgb_shallow",
        "Raw Kitsune115D control under the same legal smoke split.",
    ),
    Candidate(
        "G1_graph_interaction_only_histgb",
        False,
        ("graph_interaction",),
        "histgb_shallow",
        "HyperVision-inspired ego flow-interaction graph statistics only.",
    ),
    Candidate(
        "Z1_zeek_semantic_only_histgb",
        False,
        ("zeek_semantic",),
        "histgb_shallow",
        "Zeek-style protocol/service/TCP-state semantic evidence only.",
    ),
    Candidate(
        "N1_netflow_style_only_histgb",
        False,
        ("netflow_style",),
        "histgb_shallow",
        "NFStream/NetFlow-style flow aggregate evidence only.",
    ),
    Candidate(
        "C1_cicflow_style_only_histgb",
        False,
        ("cicflow_style",),
        "histgb_shallow",
        "CICFlowMeter-style duration/IAT/length/flag/rate evidence only.",
    ),
    Candidate(
        "M1_all_external_blocks_histgb",
        False,
        tuple(EXTERNAL_BLOCK_ORDER),
        "histgb_shallow",
        "Union of graph + Zeek + NetFlow + CICFlowMeter-style external blocks.",
    ),
    Candidate(
        "M2_raw115_plus_all_external_blocks_histgb",
        True,
        tuple(EXTERNAL_BLOCK_ORDER),
        "histgb_shallow",
        "Raw115 plus all external blocks; diagnostic upper-bound concat, not final route.",
    ),
]


def finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return float(default)
    return out if math.isfinite(out) else float(default)


def safe_div(num: float, den: float) -> float:
    den = float(den)
    return float(num) / den if abs(den) > 1e-12 else 0.0


def log1p(value: float) -> float:
    return float(np.log1p(max(0.0, float(value))))


def is_attack_label(label: Any) -> bool:
    text = str(label).strip().lower()
    if not text or text in {"nan", "none", "benign", "normal", "0"}:
        return False
    return True


def coarse_attack_family(label: Any) -> str:
    text = str(label).lower()
    if not is_attack_label(text):
        return "benign_or_empty"
    if "icmp" in text:
        return "icmp"
    if "tcp" in text or "scan" in text:
        return "tcp_scan_flood"
    if "udp" in text or "gre" in text:
        return "udp_gre_flood"
    if "file" in text or "download" in text or "tool transfer" in text or "ingress" in text:
        return "transfer"
    if "c&c" in text or "c2" in text or "communication" in text:
        return "c2"
    return "other_attack"


def label_context_stats(labels: deque[str], target_label: Any, prefix: str) -> dict[str, Any]:
    arr = [str(v) for v in labels]
    n = len(arr)
    if n == 0:
        return {
            f"{prefix}_context_count": 0,
            f"{prefix}_attack_seen": False,
            f"{prefix}_attack_rate": 0.0,
            f"{prefix}_same_family_seen": False,
            f"{prefix}_same_family_rate": 0.0,
            f"{prefix}_unique_attack_labels": 0,
        }
    attack_mask = [is_attack_label(v) for v in arr]
    target_family = coarse_attack_family(target_label)
    same_family_mask = [
        bool(flag and target_family != "benign_or_empty" and coarse_attack_family(v) == target_family)
        for flag, v in zip(attack_mask, arr)
    ]
    attack_labels = {v for flag, v in zip(attack_mask, arr) if flag}
    return {
        f"{prefix}_context_count": int(n),
        f"{prefix}_attack_seen": bool(any(attack_mask)),
        f"{prefix}_attack_rate": safe_div(sum(int(v) for v in attack_mask), n),
        f"{prefix}_same_family_seen": bool(any(same_family_mask)),
        f"{prefix}_same_family_rate": safe_div(sum(int(v) for v in same_family_mask), n),
        f"{prefix}_unique_attack_labels": int(len(attack_labels)),
    }


def parse_time_seconds(values: pd.Series) -> np.ndarray:
    try:
        ts = pd.to_datetime(values, utc=True, errors="coerce")
        if bool(ts.notna().all()):
            seconds = ts.astype("int64").to_numpy(dtype=np.float64) / 1e9
            base = float(seconds[0]) if len(seconds) else 0.0
            return seconds - base
    except Exception:
        pass
    return np.arange(len(values), dtype=np.float64)


FlowStateRow = tuple[float, float, float, int, int, int, int, int, int, int, str, str, int, int]


def state_features(rows: deque[FlowStateRow], window: int, current_ts: float) -> list[float]:
    n = len(rows)
    if n == 0:
        return [0.0] * len(STATE_BASE)
    arr = list(rows)
    ts = np.asarray([r[0] for r in arr], dtype=np.float64)
    len_log = np.asarray([r[1] for r in arr], dtype=np.float64)
    len_raw = np.asarray([r[2] for r in arr], dtype=np.float64)
    duration = max(0.0, float(ts[-1] - ts[0])) if n >= 2 else 0.0
    gaps = np.diff(ts) if n >= 2 else np.asarray([], dtype=np.float64)
    last_gap = max(0.0, float(current_ts - ts[-1])) if n >= 1 and np.isfinite(current_ts) and np.isfinite(ts[-1]) else 0.0
    event_rate = safe_div(n, max(duration, 1e-6)) if n >= 2 else 0.0
    byte_rate = safe_div(float(np.sum(len_raw)), max(duration, 1e-6)) if n >= 2 else 0.0
    return [
        safe_div(n, window),
        log1p(duration),
        log1p(last_gap),
        log1p(float(np.mean(gaps))) if len(gaps) else 0.0,
        log1p(float(np.std(gaps))) if len(gaps) else 0.0,
        log1p(event_rate),
        log1p(byte_rate),
        float(np.min(len_log)),
        float(np.mean(len_log)),
        float(np.max(len_log)),
        float(np.std(len_log)),
        safe_div(sum(r[3] for r in arr), n),
        safe_div(sum(r[4] for r in arr), n),
        safe_div(sum(r[5] for r in arr), n),
        safe_div(sum(r[6] for r in arr), n),
        safe_div(sum(r[7] for r in arr), n),
        safe_div(sum(r[8] for r in arr), n),
        safe_div(sum(r[9] for r in arr), n),
        safe_div(len({r[10] for r in arr}), window),
        safe_div(len({r[11] for r in arr}), window),
        safe_div(len({r[12] for r in arr}), window),
        safe_div(len({r[13] for r in arr}), window),
    ]


def byte_sum(rows: deque[tuple[Any, ...]]) -> float:
    return float(sum(float(r[2]) for r in rows))


class ExternalFlowFeatureCache:
    def __init__(self, zip_path: Path):
        if not zip_path.exists():
            raise FileNotFoundError(f"Missing Gotham raw zip: {zip_path}")
        self.zip_path = zip_path
        self._features: dict[str, dict[int, np.ndarray]] = {}
        self._audits: dict[str, dict[int, dict[str, Any]]] = {}
        self.audit_rows: list[dict[str, Any]] = []

    def read_prefix(self, member: str, nrows: int) -> pd.DataFrame:
        nrows = int(max(0, nrows))
        if nrows <= 0:
            return pd.DataFrame()
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as f:
                return pd.read_csv(f, usecols=lambda col: col in PROCESSED_USECOLS, nrows=nrows, low_memory=False)

    def compute_member(self, member: str, row_indices: np.ndarray) -> None:
        target = sorted({int(v) for v in row_indices if int(v) >= 0})
        if not target:
            self._features.setdefault(member, {})
            self._audits.setdefault(member, {})
            return
        if member in self._features and all(r in self._features[member] for r in target):
            return
        max_row = max(target)
        df = self.read_prefix(member, max_row + 1)
        feats: dict[int, np.ndarray] = self._features.setdefault(member, {})
        audits: dict[int, dict[str, Any]] = self._audits.setdefault(member, {})
        if len(df) <= max_row:
            for ridx in target:
                feats[ridx] = np.zeros(len(FEATURE_NAMES), dtype=np.float32)
                audits[ridx] = {"alignment_ok": False, "processed_row_exists": False}
            return

        ts = parse_time_seconds(df.get("frame.time", pd.Series(range(len(df)))))
        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        label_col = df.get("label", pd.Series([""] * len(df))).astype(str).to_numpy()
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
        tcp_flags = [cko.parse_tcp_flags(v) for v in df.get("tcp.flags", pd.Series([0] * len(df))).to_numpy()]
        ip_src = df.get("ip.src", pd.Series([""] * len(df))).to_numpy()
        ip_dst = df.get("ip.dst", pd.Series([""] * len(df))).to_numpy()
        eth_src = df.get("eth.src", pd.Series([""] * len(df))).to_numpy()
        eth_dst = df.get("eth.dst", pd.Series([""] * len(df))).to_numpy()

        file_state = {w: deque(maxlen=w) for w in WINDOWS}
        src_state: dict[str, dict[int, deque[tuple[Any, ...]]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        dst_state: dict[str, dict[int, deque[tuple[Any, ...]]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        pair_state: dict[tuple[str, str], dict[int, deque[tuple[Any, ...]]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        biflow_state: dict[tuple[Any, ...], dict[int, deque[tuple[Any, ...]]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        flow5_state: dict[tuple[Any, ...], dict[int, deque[tuple[Any, ...]]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        file_label_state = {w: deque(maxlen=w) for w in WINDOWS}
        src_label_state: dict[str, dict[int, deque[str]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})
        pair_label_state: dict[tuple[str, str], dict[int, deque[str]]] = defaultdict(lambda: {w: deque(maxlen=w) for w in WINDOWS})

        timestamp_monotonic_violations = int(np.sum(np.diff(ts) < -1e-9)) if len(ts) >= 2 else 0
        target_set = set(target)
        for i in range(max_row + 1):
            proto = str(proto_text[i]).lower()
            is_tcp = int(ip_proto[i] == 6 or tcp_src[i] > 0 or tcp_dst[i] > 0 or "tcp" in proto)
            is_udp = int(ip_proto[i] == 17 or udp_src[i] > 0 or udp_dst[i] > 0 or "udp" in proto)
            is_icmp = int(ip_proto[i] == 1 or "icmp" in proto)
            sport = float(tcp_src[i] if tcp_src[i] > 0 else udp_src[i])
            dport = float(tcp_dst[i] if tcp_dst[i] > 0 else udp_dst[i])
            sport_i = int(sport) if np.isfinite(sport) and sport > 0 else 0
            dport_i = int(dport) if np.isfinite(dport) and dport > 0 else 0
            flags = int(tcp_flags[i])
            syn = int(bool(flags & 0x02))
            ack = int(bool(flags & 0x10))
            rst = int(bool(flags & 0x04))
            fin = int(bool(flags & 0x01))
            src = cko.coalesce_str(ip_src[i], eth_src[i], f"row{i}:src")
            dst = cko.coalesce_str(ip_dst[i], eth_dst[i], f"row{i}:dst")
            pair = (src, dst)
            rev_pair = (dst, src)
            proto_i = int(ip_proto[i]) if np.isfinite(ip_proto[i]) else 0
            endpoint_a, endpoint_b = sorted([(src, sport_i), (dst, dport_i)])
            biflow = (endpoint_a, endpoint_b, proto_i)
            flow5 = (src, dst, proto_i, sport_i, dport_i)
            current = [
                float(frame_len_log[i]),
                float(is_tcp),
                float(is_udp),
                float(is_icmp),
                log1p(sport),
                log1p(dport),
                float(0 < dport <= 1024),
                float(dport_i == 53 or "dns" in proto),
                float(dport_i == 5683 or "coap" in proto),
                float(dport_i in {80, 8080} or "http" in proto),
                float(dport_i == 443 or "tls" in proto or "ssl" in proto),
                float(syn),
                float(ack),
                float(rst),
                float(fin),
                float(syn and not ack),
                float(ack and not syn),
                float(np.clip(ip_ttl[i] / 255.0, 0.0, 1.0)) if np.isfinite(ip_ttl[i]) else 0.0,
                log1p(tcp_window[i]),
                log1p(tcp_pdu[i]),
            ]
            if i in target_set:
                vals = list(current)
                context_audit: dict[str, Any] = {
                    "processed_label_is_attack": bool(is_attack_label(label_col[i])),
                    "processed_label_family": coarse_attack_family(label_col[i]),
                    "timestamp_monotonic_violations_before_or_at_source_prefix": int(timestamp_monotonic_violations),
                }
                for w in WINDOWS:
                    states = {
                        "file": file_state[w],
                        "src": src_state[src][w],
                        "dst": dst_state[dst][w],
                        "pair": pair_state[pair][w],
                        "rev_pair": pair_state[rev_pair][w],
                        "biflow": biflow_state[biflow][w],
                        "flow5": flow5_state[flow5][w],
                    }
                    for name in ["file", "src", "dst", "pair", "rev_pair", "biflow", "flow5"]:
                        vals.extend(state_features(states[name], w, float(ts[i])))
                    context_audit.update(label_context_stats(file_label_state[w], label_col[i], f"prior_file_w{w}"))
                    context_audit.update(label_context_stats(src_label_state[src][w], label_col[i], f"prior_src_w{w}"))
                    context_audit.update(label_context_stats(pair_label_state[pair][w], label_col[i], f"prior_pair_w{w}"))
                    fwd = states["pair"]
                    rev = states["rev_pair"]
                    srcs = states["src"]
                    dsts = states["dst"]
                    files = states["file"]
                    bi = states["biflow"]
                    flow = states["flow5"]
                    vals.extend(
                        [
                            float(len(rev) > 0),
                            safe_div(len(fwd) - len(rev), len(fwd) + len(rev) + 1e-6),
                            safe_div(byte_sum(fwd) - byte_sum(rev), byte_sum(fwd) + byte_sum(rev) + 1.0),
                            safe_div(len(srcs), len(files) + 1e-6),
                            safe_div(byte_sum(srcs), byte_sum(files) + 1.0),
                            safe_div(len(dsts), len(files) + 1e-6),
                            safe_div(byte_sum(dsts), byte_sum(files) + 1.0),
                            safe_div(len(flow), len(bi) + 1e-6),
                        ]
                    )
                for short, long in [(16, 128)]:
                    vals.extend(
                        [
                            safe_div(len(src_state[src][short]), len(src_state[src][long]) + 1e-6),
                            safe_div(len({r[13] for r in src_state[src][short]}), len({r[13] for r in src_state[src][long]}) + 1e-6),
                            safe_div(len({r[10] for r in dst_state[dst][short]}), len({r[10] for r in dst_state[dst][long]}) + 1e-6),
                            safe_div(len(pair_state[pair][short]), len(pair_state[pair][long]) + 1e-6),
                            safe_div(len(flow5_state[flow5][short]), len(flow5_state[flow5][long]) + 1e-6),
                            safe_div(len(biflow_state[biflow][short]), len(biflow_state[biflow][long]) + 1e-6),
                        ]
                    )
                feats[i] = np.asarray(vals, dtype=np.float32)
                audits[i] = {
                    "alignment_ok": True,
                    "processed_row_exists": True,
                    "processed_label": label_col[i],
                    "processed_frame_time": str(df.get("frame.time", pd.Series([""] * len(df))).iloc[i]),
                    "processed_frame_protocols": proto_text[i],
                    "processed_frame_len": float(frame_len_raw[i]),
                    "processed_src": src,
                    "processed_dst": dst,
                    "processed_src_port": sport_i,
                    "processed_dst_port": dport_i,
                    "processed_ip_proto": proto_i,
                    "processed_tcp_flags": flags,
                    **context_audit,
                }
            row = (float(ts[i]), float(frame_len_log[i]), float(frame_len_raw[i]), is_tcp, is_udp, is_icmp, syn, ack, rst, fin, src, dst, sport_i, dport_i)
            for w in WINDOWS:
                file_state[w].append(row)
                src_state[src][w].append(row)
                dst_state[dst][w].append(row)
                pair_state[pair][w].append(row)
                biflow_state[biflow][w].append(row)
                flow5_state[flow5][w].append(row)
                file_label_state[w].append(str(label_col[i]))
                src_label_state[src][w].append(str(label_col[i]))
                pair_label_state[pair][w].append(str(label_col[i]))

        self.audit_rows.append(
            {
                "source_group": member,
                "requested_rows": len(target),
                "max_recorded_index": int(max_row),
                "processed_prefix_rows": int(len(df)),
                "feature_dim": len(FEATURE_NAMES),
                "timestamp_monotonic_violations": int(timestamp_monotonic_violations),
                "timestamp_monotonic_ok": bool(timestamp_monotonic_violations == 0),
                "alignment_ok": True,
            }
        )

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        self.compute_member(member, row_indices)
        return self._features.get(member, {})

    def audit_for_member(self, member: str) -> dict[int, dict[str, Any]]:
        return self._audits.get(member, {})


class ExternalFlowFrontend:
    def __init__(self, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame], cache: ExternalFlowFeatureCache):
        self.x_by_role = x_by_role
        self.frame_by_role = frame_by_role
        self.cache = cache
        self._matrices: dict[tuple[str, tuple[int, ...], str], np.ndarray] = {}

    def external_matrix(self, role: str, idx: np.ndarray) -> np.ndarray:
        idx = np.asarray(idx, dtype=np.int64)
        out = np.zeros((len(idx), len(FEATURE_NAMES)), dtype=np.float32)
        if len(idx) == 0:
            return out
        frame = self.frame_by_role[role]
        if "source_group" not in frame or "recorded_index" not in frame:
            raise RuntimeError(f"{role} frame lacks source_group/recorded_index")
        sub = frame.iloc[idx].copy()
        sub["_out_pos"] = np.arange(len(idx), dtype=np.int64)
        for member, group in sub.groupby(sub["source_group"].astype(str), sort=True):
            row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
            feats = self.cache.features_for_member(str(member), row_idx)
            for out_pos, ridx in zip(group["_out_pos"].to_numpy(dtype=np.int64), row_idx):
                if int(ridx) in feats:
                    out[int(out_pos)] = feats[int(ridx)]
        return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)

    def matrix(self, candidate: Candidate, role: str, idx: np.ndarray) -> np.ndarray:
        block_key = "raw" if not candidate.external_blocks else "+".join(candidate.external_blocks)
        key = (role, tuple(np.asarray(idx, dtype=np.int64).tolist()), f"{int(candidate.include_raw)}:{block_key}")
        if key in self._matrices:
            return self._matrices[key]
        parts: list[np.ndarray] = []
        if candidate.include_raw:
            parts.append(np.asarray(self.x_by_role[role][idx], dtype=np.float32))
        if candidate.external_blocks:
            cols = sorted(
                {
                    col
                    for block in candidate.external_blocks
                    for col in FEATURE_BLOCK_COLUMNS.get(block, [])
                }
            )
            if not cols:
                raise ValueError(f"No external feature columns selected for {candidate.external_blocks}")
            ext = self.external_matrix(role, idx)[:, cols]
            parts.append(ext.astype(np.float32))
        if len(parts) == 1:
            mat = parts[0]
        elif len(parts) > 1:
            mat = np.hstack(parts).astype(np.float32)
        else:
            raise ValueError(f"{candidate.name} has neither raw nor external features")
        self._matrices[key] = mat
        return mat

    def alignment_audit(self, max_rows_per_role: int = 16) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for role, frame in self.frame_by_role.items():
            if "source_group" not in frame or "recorded_index" not in frame:
                continue
            sample = frame.head(int(max_rows_per_role)).copy()
            for member, group in sample.groupby(sample["source_group"].astype(str), sort=True):
                row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
                feats = self.cache.features_for_member(str(member), row_idx)
                audits = self.cache.audit_for_member(str(member))
                for pos, ridx in zip(group.index.to_numpy(dtype=np.int64), row_idx):
                    audit = audits.get(int(ridx), {})
                    feat = feats.get(int(ridx), np.zeros(len(FEATURE_NAMES), dtype=np.float32))
                    rows.append(
                        {
                            "role": role,
                            "role_row": int(pos),
                            "source_group": str(member),
                            "recorded_index": int(ridx),
                            "alignment_ok": bool(audit.get("alignment_ok", False) and len(feat) == len(FEATURE_NAMES)),
                            "feature_dim": int(len(feat)),
                            "feature_nonzero": int(np.count_nonzero(feat)),
                            "processed_label_audit_only": audit.get("processed_label", ""),
                            "processed_frame_time": audit.get("processed_frame_time", ""),
                            "processed_frame_protocols": audit.get("processed_frame_protocols", ""),
                            "processed_src": audit.get("processed_src", ""),
                            "processed_dst": audit.get("processed_dst", ""),
                            "processed_src_port": audit.get("processed_src_port", ""),
                            "processed_dst_port": audit.get("processed_dst_port", ""),
                        }
                    )
        return rows


def role_indices(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, cap: int) -> np.ndarray:
    return cko.role_indices(frame_by_role, role, phase, cap)


def fit_candidate(candidate: Candidate, frontend: ExternalFlowFrontend, frame_by_role: dict[str, pd.DataFrame], train_cap: int) -> tuple[Any, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = role_indices(frame_by_role, role, phase, cap)
        xs.append(frontend.matrix(candidate, role, idx))
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append({"candidate": candidate.name, "role": role, "phase": phase, "label": label, "rows": int(len(idx)), "feature_dim": int(xs[-1].shape[1])})

    add("support_train", "fit", ckh.CLASS_ATTACK, FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    model = ckh.balanced_fit(ckh.build_model(candidate.model, multiclass=True), np.vstack(xs), np.concatenate(ys))
    return model, audit


def score_attack(model: Any, x: np.ndarray) -> np.ndarray:
    return ckh.class_score(model, x, ckh.CLASS_ATTACK)


def score_conflict(model: Any, x: np.ndarray) -> np.ndarray:
    return np.maximum.reduce(
        [
            ckh.class_score(model, x, ckh.CLASS_ID),
            ckh.class_score(model, x, ckh.CLASS_OOD),
            ckh.class_score(model, x, ckh.CLASS_HARD_OOD),
        ]
    )


def attack_threshold(candidate: Candidate, model: Any, frontend: ExternalFlowFrontend, frame_by_role: dict[str, pd.DataFrame], eval_cap: int) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices(frame_by_role, role, "select", eval_cap)
        if len(idx):
            parts.append(score_attack(model, frontend.matrix(candidate, role, idx)))
    if not parts:
        raise RuntimeError("No benign/OOD select rows available for thresholding")
    return float(max(np.quantile(part, BENIGN_Q) for part in parts if len(part)))


def eval_role(candidate: Candidate, model: Any, threshold: float, frontend: ExternalFlowFrontend, frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, kind: str, eval_cap: int) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, eval_cap)
    if len(idx) == 0:
        row = {
            "candidate": candidate.name,
            "role": role,
            "phase": phase,
            "role_kind": kind,
            "rows": 0,
            "attack_threshold": float(threshold),
            "hard_alarm_rate": float("nan"),
            "review_rate": 0.0,
            "attack_score_mean": float("nan"),
            "conflict_score_mean": float("nan"),
        }
        return row, pd.DataFrame()
    x = frontend.matrix(candidate, role, idx)
    attack = score_attack(model, x)
    conflict = score_conflict(model, x)
    hard = attack > float(threshold)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    part["candidate"] = candidate.name
    part["role"] = role
    part["phase"] = phase
    part["role_kind"] = kind
    part["attack_score"] = attack
    part["conflict_score"] = conflict
    part["hard_alarm"] = hard
    row = {
        "candidate": candidate.name,
        "role": role,
        "phase": phase,
        "role_kind": kind,
        "rows": int(len(idx)),
        "attack_threshold": float(threshold),
        "hard_alarm_rate": ckg.rate(hard),
        "review_rate": 0.0,
        "attack_score_mean": float(np.mean(attack)) if len(idx) else float("nan"),
        "conflict_score_mean": float(np.mean(conflict)) if len(idx) else float("nan"),
    }
    return row, part


def main_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    candidates = sorted({r["candidate"] for r in rows})
    for candidate in candidates:
        def pick(role: str, metric: str) -> float:
            for row in rows:
                if row["candidate"] == candidate and row["role"] == role:
                    return float(row.get(metric, float("nan")))
            return float("nan")
        out.append(
            {
                "candidate": candidate,
                "support_hard": pick("support_val", "hard_alarm_rate"),
                "same_file_hard": pick("same_file_query", "hard_alarm_rate"),
                "future_hard": pick("future_query", "hard_alarm_rate"),
                "sealed_attack_hard": pick("sealed_final_attack", "hard_alarm_rate"),
                "sealed_ood_hard": pick("sealed_final_ood", "hard_alarm_rate"),
                "ood_stress_hard": pick("ood_stress", "hard_alarm_rate"),
                "attack_threshold": pick("support_val", "attack_threshold"),
            }
        )
    return out


def attack_family(label: Any) -> str:
    return coarse_attack_family(label)


def family_summary(parts: list[pd.DataFrame]) -> list[dict[str, Any]]:
    if not parts:
        return []
    df = pd.concat(parts, ignore_index=True)
    df = df[df["role"].isin(["support_val", "same_file_query", "future_query", "sealed_final_attack"])].copy()
    if df.empty or "attack_label" not in df:
        return []
    df["attack_family"] = df["attack_label"].map(attack_family)
    rows = []
    for (candidate, role, label, fam), part in df.groupby(["candidate", "role", "attack_label", "attack_family"], dropna=False, sort=True):
        rows.append(
            {
                "candidate": candidate,
                "role": role,
                "attack_label": label,
                "attack_family": fam,
                "rows": int(len(part)),
                "hard_alarm_rate": ckg.rate(part["hard_alarm"]),
                "attack_score_mean": float(pd.to_numeric(part["attack_score"], errors="coerce").mean()),
                "conflict_score_mean": float(pd.to_numeric(part["conflict_score"], errors="coerce").mean()),
            }
        )
    return rows


def grouped_performance_summary(parts: list[pd.DataFrame], group_col: str, min_rows: int = 20) -> list[dict[str, Any]]:
    if not parts:
        return []
    df = pd.concat([p for p in parts if p is not None and not p.empty], ignore_index=True)
    if df.empty or group_col not in df:
        return []
    rows: list[dict[str, Any]] = []
    work = df.copy()
    if "attack_label" in work:
        work["attack_family"] = work["attack_label"].map(attack_family)
    for (candidate, role, role_kind, group), part in work.groupby(["candidate", "role", "role_kind", group_col], dropna=False, sort=True):
        if len(part) < int(min_rows):
            continue
        hard_rate = ckg.rate(part["hard_alarm"])
        is_attack_role = "attack" in str(role_kind)
        rows.append(
            {
                "candidate": candidate,
                "role": role,
                "role_kind": role_kind,
                "group_col": group_col,
                "group_value": group,
                "rows": int(len(part)),
                "hard_alarm_rate": hard_rate,
                "desired_hard_direction": "high" if is_attack_role else "low",
                "error_rate_for_role": float(1.0 - hard_rate) if is_attack_role else float(hard_rate),
                "attack_score_mean": float(pd.to_numeric(part["attack_score"], errors="coerce").mean()),
                "conflict_score_mean": float(pd.to_numeric(part["conflict_score"], errors="coerce").mean()),
            }
        )
    rows.sort(key=lambda r: (str(r["candidate"]), str(r["role"]), -float(r["error_rate_for_role"]), -int(r["rows"])))
    return rows


def worst_group_overview(group_rows: list[dict[str, Any]], top_k: int = 10) -> list[dict[str, Any]]:
    if not group_rows:
        return []
    out: list[dict[str, Any]] = []
    df = pd.DataFrame(group_rows)
    if df.empty:
        return []
    for (candidate, role, group_col), part in df.groupby(["candidate", "role", "group_col"], dropna=False, sort=True):
        ranked = part.sort_values(["error_rate_for_role", "rows"], ascending=[False, False]).head(int(top_k))
        for rank, (_, row) in enumerate(ranked.iterrows(), start=1):
            item = row.to_dict()
            item["worst_group_rank"] = int(rank)
            out.append(item)
    return out


def context_role_specs(train_cap: int, eval_cap: int) -> list[tuple[str, str, str, int]]:
    specs = [
        ("support_train", "fit", "attack_fit", FULL_CAP),
        ("id_calib", "fit", "benign_id_fit", train_cap),
        ("ood_val", "fit", "benign_ood_fit", train_cap),
        ("ood_stress", "fit", "hard_ood_fit", train_cap),
    ]
    specs.extend((role, phase, kind, eval_cap) for role, phase, kind in cko.ROLE_EVAL)
    return specs


def context_audit_rows_and_summary(
    frontend: ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    row_output_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sample_rows: list[dict[str, Any]] = []
    summary: dict[tuple[str, str, str], dict[str, Any]] = {}
    bool_fields: list[str] = ["processed_label_is_attack"]
    rate_fields: list[str] = []
    for w in WINDOWS:
        for scope in ["file", "src", "pair"]:
            bool_fields.extend(
                [
                    f"prior_{scope}_w{w}_attack_seen",
                    f"prior_{scope}_w{w}_same_family_seen",
                ]
            )
            rate_fields.extend(
                [
                    f"prior_{scope}_w{w}_attack_rate",
                    f"prior_{scope}_w{w}_same_family_rate",
                ]
            )
    for role, phase, kind, cap in context_role_specs(train_cap, eval_cap):
        if role not in frame_by_role or len(frame_by_role[role]) == 0:
            continue
        idx = role_indices(frame_by_role, role, phase, cap)
        if len(idx) == 0:
            continue
        # Trigger row-aligned past-only extraction and audit cache population.
        _ = frontend.external_matrix(role, idx)
        frame = frame_by_role[role]
        sub = frame.iloc[idx].copy()
        sub["_role_row"] = idx
        for member, group in sub.groupby(sub["source_group"].astype(str), sort=True):
            audits = frontend.cache.audit_for_member(str(member))
            for _, item in group.iterrows():
                ridx = int(item.get("recorded_index", -1))
                audit = audits.get(ridx, {})
                key = (role, phase, kind)
                acc = summary.setdefault(
                    key,
                    {
                        "role": role,
                        "phase": phase,
                        "role_kind": kind,
                        "rows": 0,
                        "timestamp_monotonic_violation_rows": 0,
                    },
                )
                acc["rows"] += 1
                if int(audit.get("timestamp_monotonic_violations_before_or_at_source_prefix", 0) or 0) > 0:
                    acc["timestamp_monotonic_violation_rows"] += 1
                for field in bool_fields:
                    acc[field + "_rate"] = float(acc.get(field + "_rate", 0.0)) + float(bool(audit.get(field, False)))
                for field in rate_fields:
                    acc[field + "_mean"] = float(acc.get(field + "_mean", 0.0)) + finite(audit.get(field, 0.0))
                if row_output_cap <= 0 or len(sample_rows) < row_output_cap:
                    row = {
                        "role": role,
                        "phase": phase,
                        "role_kind": kind,
                        "role_row": int(item.get("_role_row", -1)),
                        "source_group": str(member),
                        "recorded_index": ridx,
                        "frame_attack_label": item.get("attack_label", ""),
                        "processed_label_audit_only": audit.get("processed_label", ""),
                        "processed_label_is_attack": audit.get("processed_label_is_attack", False),
                        "processed_label_family": audit.get("processed_label_family", ""),
                        "timestamp_monotonic_violations": audit.get("timestamp_monotonic_violations_before_or_at_source_prefix", 0),
                    }
                    for w in WINDOWS:
                        for scope in ["file", "src", "pair"]:
                            prefix = f"prior_{scope}_w{w}"
                            row.update(
                                {
                                    f"{prefix}_context_count": audit.get(f"{prefix}_context_count", 0),
                                    f"{prefix}_attack_seen": audit.get(f"{prefix}_attack_seen", False),
                                    f"{prefix}_attack_rate": audit.get(f"{prefix}_attack_rate", 0.0),
                                    f"{prefix}_same_family_seen": audit.get(f"{prefix}_same_family_seen", False),
                                    f"{prefix}_same_family_rate": audit.get(f"{prefix}_same_family_rate", 0.0),
                                }
                            )
                    sample_rows.append(row)
    summary_rows: list[dict[str, Any]] = []
    for acc in summary.values():
        n = max(1, int(acc["rows"]))
        out = dict(acc)
        out["timestamp_monotonic_violation_rate"] = safe_div(out.pop("timestamp_monotonic_violation_rows"), n)
        for key in list(out.keys()):
            if key.endswith("_rate") and key != "timestamp_monotonic_violation_rate":
                out[key] = safe_div(float(out[key]), n)
            if key.endswith("_mean"):
                out[key] = safe_div(float(out[key]), n)
        summary_rows.append(out)
    summary_rows.sort(key=lambda r: (str(r["role"]), str(r["phase"]), str(r["role_kind"])))
    return sample_rows, summary_rows


def build_readout(summary_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckai external flow feature probe v1",
        "",
        "## Main summary",
        "",
        "| candidate | support | same-file | future | sealed attack | sealed OOD | OOD-stress | thr |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary_rows:
        lines.append(
            f"| {row['candidate']} | {cko.fmt(row['support_hard'])} | {cko.fmt(row['same_file_hard'])} | "
            f"{cko.fmt(row['future_hard'])} | {cko.fmt(row['sealed_attack_hard'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])} | {cko.fmt(row['ood_stress_hard'])} | {cko.fmt(row['attack_threshold'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Features are row-aligned by source_group + recorded_index.",
            "- Processed label is audit-only, not a feature.",
            "- Fit uses support_train/id_calib/ood_val/ood_stress fit only.",
            "- Threshold uses id_calib/ood_val/ood_stress/support_val select only.",
            "- Query/future/sealed roles are report-only.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def filter_roles_by_recorded_index(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    max_recorded_index: int,
) -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame], list[dict[str, Any]]]:
    if int(max_recorded_index) <= 0:
        return x_by_role, frame_by_role, []
    capped_x: dict[str, np.ndarray] = {}
    capped_frame: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for role, frame in frame_by_role.items():
        frame0 = frame.reset_index(drop=True)
        if "recorded_index" not in frame0:
            positions = np.arange(len(frame0), dtype=np.int64)
        else:
            recorded = pd.to_numeric(frame0["recorded_index"], errors="coerce").fillna(10**18)
            positions = np.flatnonzero(recorded.to_numpy(dtype=np.float64) <= float(max_recorded_index)).astype(np.int64)
        capped_frame[role] = frame0.iloc[positions].reset_index(drop=True)
        capped_x[role] = np.asarray(x_by_role[role][positions], dtype=np.float32)
        rows.append(
            {
                "role": role,
                "filter": "max_recorded_index",
                "max_recorded_index": int(max_recorded_index),
                "original_rows": len(frame0),
                "kept_rows": len(positions),
                "note": "Local fast smoke guardrail; set --max-recorded-index 0 for full legal replay.",
            }
        )
    return capped_x, capped_frame, rows


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    smoke = not bool(args.full)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    role_cap_rows: list[dict[str, Any]] = []
    x_by_role, frame_by_role, filter_rows = filter_roles_by_recorded_index(
        x_by_role,
        frame_by_role,
        int(args.max_recorded_index),
    )
    role_cap_rows.extend(filter_rows)
    if int(args.source_cap) > 0:
        x_by_role, frame_by_role, cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            int(args.role_cap),
            int(args.source_cap),
            cap_rule="ckai external flow feature capped smoke",
        )
        role_cap_rows.extend(cap_rows)
    cache = ExternalFlowFeatureCache(cko.GOTHAM_ZIP)
    frontend = ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    context_sample_rows: list[dict[str, Any]] = []
    context_summary_rows: list[dict[str, Any]] = []
    if args.mode in {"context-audit", "both", "frontend"}:
        context_sample_rows, context_summary_rows = context_audit_rows_and_summary(
            frontend,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            int(args.context_row_output_cap),
        )
        cko.write_csv(out / "context_contamination_sample.csv", context_sample_rows)
        cko.write_csv(out / "context_contamination_summary.csv", context_summary_rows)
    if args.mode == "context-audit":
        seconds = time.time() - started
        cko.write_csv(out / "external_extraction_audit.csv", cache.audit_rows)
        cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
        cko.write_json(
            out / "run_spec.json",
            {
                "issue": ISSUE,
                "run_tag": args.run_tag,
                "mode": args.mode,
                "full": bool(args.full),
                "smoke": bool(smoke),
                "role_cap": int(args.role_cap),
                "source_cap": int(args.source_cap),
                "max_recorded_index": int(args.max_recorded_index),
                "train_cap": int(args.train_cap),
                "eval_cap": int(args.eval_cap),
                "context_row_output_cap": int(args.context_row_output_cap),
                "context_audit": {
                    "uses_processed_label_for_audit_only": True,
                    "processed_label_feature_use": False,
                    "query_future_sealed_used_for_training_or_thresholding": False,
                },
                "input_audit": input_audit,
                "seconds": seconds,
            },
        )
        cko.write_md(
            out / "codex_readout.md",
            [
                "# issue27ckai context contamination audit",
                "",
                "- Mode: context-audit only.",
                f"- Full input: {bool(args.full)}.",
                f"- Max recorded index: {int(args.max_recorded_index)}.",
                "- Label fields are audit-only and are not used as model features.",
                f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
            ],
        )
        print(json.dumps({"status": "ok", "mode": args.mode, "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))
        return
    candidate_names = {v.strip() for v in str(args.candidates).split(",") if v.strip()}
    candidates = [c for c in CANDIDATES if c.name in candidate_names]
    if not candidates:
        raise ValueError("No candidates selected")
    role_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    part_frames: list[pd.DataFrame] = []
    threshold_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        model, audit = fit_candidate(candidate, frontend, frame_by_role, int(args.train_cap))
        train_rows.extend(audit)
        threshold = attack_threshold(candidate, model, frontend, frame_by_role, int(args.eval_cap))
        threshold_rows.append({"candidate": candidate.name, "attack_threshold": float(threshold), "benign_q": BENIGN_Q})
        for role, phase, kind in cko.ROLE_EVAL:
            row, part = eval_role(candidate, model, threshold, frontend, frame_by_role, role, phase, kind, int(args.eval_cap))
            role_rows.append(row)
            part_frames.append(part)
    seconds = time.time() - started
    summary_rows = main_summary(role_rows)
    family_rows = family_summary(part_frames)
    source_group_rows = grouped_performance_summary(part_frames, "source_group", min_rows=int(args.group_min_rows))
    device_rows = grouped_performance_summary(part_frames, "device", min_rows=int(args.group_min_rows))
    group_overview_rows = worst_group_overview(source_group_rows + device_rows, top_k=10)
    alignment_rows = frontend.alignment_audit(max_rows_per_role=16)
    cko.write_csv(
        out / "candidate_matrix.csv",
        [
            {
                **asdict(c),
                "external_blocks": ";".join(c.external_blocks),
                "external_feature_dim": int(len(sorted({col for block in c.external_blocks for col in FEATURE_BLOCK_COLUMNS.get(block, [])}))),
            }
            for c in candidates
        ],
    )
    cko.write_csv(
        out / "feature_registry.csv",
        [
            {
                "feature_index": i,
                "feature_name": name,
                "feature_family": name.split("_w")[0],
                "feature_blocks": ";".join(FEATURE_BLOCK_MEMBERS[name]),
            }
            for i, name in enumerate(FEATURE_NAMES)
        ],
    )
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "threshold_audit.csv", threshold_rows)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "attack_family_summary.csv", family_rows)
    cko.write_csv(out / "source_group_summary.csv", source_group_rows)
    cko.write_csv(out / "device_summary.csv", device_rows)
    cko.write_csv(out / "worst_group_overview.csv", group_overview_rows)
    cko.write_csv(out / "main_summary_matrix.csv", summary_rows)
    cko.write_csv(out / "external_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_md(out / "codex_readout.md", build_readout(summary_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "mode": args.mode,
            "full": bool(args.full),
            "smoke": bool(smoke),
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "max_recorded_index": int(args.max_recorded_index),
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "context_row_output_cap": int(args.context_row_output_cap),
            "group_min_rows": int(args.group_min_rows),
            "external_feature_dim": len(FEATURE_NAMES),
            "feature_block_columns": {block: len(cols) for block, cols in FEATURE_BLOCK_COLUMNS.items()},
            "feature_style": "Zeek/NFStream/NetFlow-inspired row-aligned past-only packet/flow statistics",
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "query_future_sealed_used_for_training_or_thresholding": False,
                "processed_label_feature_use": False,
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["context-audit", "frontend", "both"], default="frontend")
    parser.add_argument("--full", action="store_true", help="Use full certified 1M roles; default keeps upstream smoke role caps.")
    parser.add_argument("--role-cap", type=int, default=256)
    parser.add_argument("--source-cap", type=int, default=0)
    parser.add_argument("--max-recorded-index", type=int, default=200000)
    parser.add_argument("--train-cap", type=int, default=256)
    parser.add_argument("--eval-cap", type=int, default=256)
    parser.add_argument("--context-row-output-cap", type=int, default=200000)
    parser.add_argument("--group-min-rows", type=int, default=20)
    parser.add_argument(
        "--candidates",
        default="R0_raw115_only_histgb,G1_graph_interaction_only_histgb,Z1_zeek_semantic_only_histgb,N1_netflow_style_only_histgb,C1_cicflow_style_only_histgb,M1_all_external_blocks_histgb,M2_raw115_plus_all_external_blocks_histgb",
    )
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
