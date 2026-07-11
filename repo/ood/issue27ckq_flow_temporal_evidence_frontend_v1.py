"""issue27ckq: deep flow-temporal evidence frontend v1.

This experiment is intentionally deeper than issue27cko's shallow mechanism
features.  It builds past-only flow interaction evidence from processed Gotham
CSV rows and tests whether those signals help separate attack mechanism from
OOD/domain shift without sacrificing the strong raw115 attack baseline.

Decision form:

    controls:
      F0 raw115
      F1 flow-temporal only
      F2 raw115 + flow-temporal naive concat

    structured candidates:
      raw115 encoder + flow-temporal encoder -> one four-class fusion head

The final classifier is still a single four-class decision over:

    ID benign / ordinary OOD / hard OOD / attack

No query/future/final/report-only rows are used for fitting or thresholding.
All flow-temporal state is current/past-only within the processed source file.
"""

from __future__ import annotations

import argparse
import bisect
import json
import math
import sys
import time
import zipfile
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckq_flow_temporal_evidence_frontend_v1_2026-06-30"
OUT = cko.ROOT / "runs" / ISSUE

WINDOWS = [8, 32, 128]
SHORT_LONG_PAIRS = [(8, 128)]
MICRO_TRAIN_CAP = 256
MICRO_EVAL_CAP = 768
CLASS_LABELS = [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD, ckh.CLASS_ATTACK]
CLASS_NAMES = {
    ckh.CLASS_ID: "id",
    ckh.CLASS_OOD: "ood",
    ckh.CLASS_HARD_OOD: "hard_ood",
    ckh.CLASS_ATTACK: "attack",
}

PROCESSED_USECOLS = [
    "frame.len",
    "frame.protocols",
    "eth.src",
    "eth.dst",
    "ip.src",
    "ip.dst",
    "ip.ttl",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.pdu.size",
    "udp.srcport",
    "udp.dstport",
    # Audit only, never converted into a feature.
    "label",
]

CURRENT_FEATURES = [
    "cur_log_frame_len",
    "cur_is_tcp",
    "cur_is_udp",
    "cur_is_icmp",
    "cur_src_port_log",
    "cur_dst_port_log",
    "cur_dst_well_known",
    "cur_is_dns",
    "cur_is_coap",
    "cur_is_http",
    "cur_is_tls",
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
    "len_mean_log",
    "len_std_log",
    "tcp_rate",
    "udp_rate",
    "syn_rate",
    "ack_rate",
    "rst_rate",
    "fin_rate",
    "duration_log",
    "event_rate_log",
    "byte_rate_log",
    "current_gap_log",
]


def state_feature_names(prefix: str, unique_names: list[str]) -> list[str]:
    return [f"{prefix}_{name}" for name in STATE_BASE + unique_names]


FLOW_TEMPORAL_FEATURES = list(CURRENT_FEATURES)
for window in WINDOWS:
    FLOW_TEMPORAL_FEATURES.extend(
        state_feature_names(
            f"prior_file_w{window}",
            ["unique_src_frac", "unique_dst_frac", "unique_dport_frac"],
        )
    )
    FLOW_TEMPORAL_FEATURES.extend(
        state_feature_names(
            f"prior_src_w{window}",
            ["unique_dst_frac", "unique_dport_frac"],
        )
    )
    FLOW_TEMPORAL_FEATURES.extend(
        state_feature_names(
            f"prior_dst_w{window}",
            ["unique_src_frac", "unique_sport_frac"],
        )
    )
    FLOW_TEMPORAL_FEATURES.extend(
        state_feature_names(
            f"prior_pair_w{window}",
            ["unique_sport_frac", "unique_dport_frac"],
        )
    )
    FLOW_TEMPORAL_FEATURES.extend(state_feature_names(f"prior_flow5_w{window}", []))
    FLOW_TEMPORAL_FEATURES.extend(
        [
            f"prior_pair_reverse_count_frac_w{window}",
            f"prior_pair_reverse_byte_rate_log_w{window}",
            f"prior_pair_forward_reverse_count_balance_w{window}",
            f"prior_pair_forward_reverse_byte_balance_w{window}",
            f"prior_pair_reverse_seen_w{window}",
        ]
    )
for short, long in SHORT_LONG_PAIRS:
    FLOW_TEMPORAL_FEATURES.extend(
        [
            f"src_count_short_long_ratio_w{short}_{long}",
            f"src_dport_fanout_short_long_ratio_w{short}_{long}",
            f"dst_src_pressure_short_long_ratio_w{short}_{long}",
            f"pair_count_short_long_ratio_w{short}_{long}",
            f"flow5_count_short_long_ratio_w{short}_{long}",
        ]
    )


RAW_BLOCK = cko.FeatureSpec("raw115_block", "raw", "Raw Kitsune115D evidence encoder.")
FLOW_BLOCK = cko.FeatureSpec("flow_temporal_block", "flow_temporal", "Past-only flow-temporal evidence encoder.")


CONTROL_SPECS = [
    cko.FeatureSpec("F0_raw115_control", "raw", "Raw Kitsune115D control."),
    cko.FeatureSpec("F1_flow_temporal_only", "flow_temporal", "Deep past-only flow/temporal evidence only."),
    cko.FeatureSpec("F2_raw115_plus_flow_temporal_naive", "raw_plus_flow_temporal", "Naive raw115 + flow-temporal concat."),
]


@dataclass(frozen=True)
class EvidenceCandidate:
    name: str
    include_margins: bool
    meta_model: str
    description: str


EVIDENCE_CANDIDATES = [
    EvidenceCandidate(
        "Q1_raw_flow_stack_probs_oof_histgb",
        include_margins=False,
        meta_model="histgb_shallow",
        description="Raw115 and flow-temporal class-probability evidence -> one four-class fusion head.",
    ),
    EvidenceCandidate(
        "Q2_raw_flow_stack_margins_oof_histgb",
        include_margins=True,
        meta_model="histgb_shallow",
        description="Class-probability evidence plus attack/OOD disagreement margins -> one four-class fusion head.",
    ),
]


def safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else 0.0


def event_time(max_needed: int) -> np.ndarray:
    """Past-only event time for rolling flow evidence.

    Wall-clock parsing from `frame.time` is deliberately not used in this v1
    smokeable runner because it made local validation prohibitively heavy.
    The evidence still captures multi-scale event-window burst/fanout/direction
    dynamics.  A later Zeek/IPFIX-style frontend can add true duration/rate.
    """

    return np.arange(max_needed + 1, dtype=np.float64)


class DeepRollingState:
    def __init__(self, window: int):
        self.window = int(window)
        self.rows: deque[tuple[float, float, float, float, float, float, float, float, float, str, str, int, int]] = deque()
        self.sum_len_log = 0.0
        self.sum_len_log2 = 0.0
        self.sum_len_raw = 0.0
        self.sum_tcp = 0.0
        self.sum_udp = 0.0
        self.sum_syn = 0.0
        self.sum_ack = 0.0
        self.sum_rst = 0.0
        self.sum_fin = 0.0
        self.src_counter: Counter[str] = Counter()
        self.dst_counter: Counter[str] = Counter()
        self.sport_counter: Counter[int] = Counter()
        self.dport_counter: Counter[int] = Counter()

    def _remove_counter(self, counter: Counter[Any], key: Any) -> None:
        counter[key] -= 1
        if counter[key] <= 0:
            del counter[key]

    def _pop_oldest(self) -> None:
        ts, len_log, len_raw, is_tcp, is_udp, syn, ack, rst, fin, src, dst, sport, dport = self.rows.popleft()
        self.sum_len_log -= len_log
        self.sum_len_log2 -= len_log * len_log
        self.sum_len_raw -= len_raw
        self.sum_tcp -= is_tcp
        self.sum_udp -= is_udp
        self.sum_syn -= syn
        self.sum_ack -= ack
        self.sum_rst -= rst
        self.sum_fin -= fin
        self._remove_counter(self.src_counter, src)
        self._remove_counter(self.dst_counter, dst)
        self._remove_counter(self.sport_counter, sport)
        self._remove_counter(self.dport_counter, dport)

    def update(
        self,
        ts: float,
        len_log: float,
        len_raw: float,
        is_tcp: float,
        is_udp: float,
        syn: float,
        ack: float,
        rst: float,
        fin: float,
        src: str,
        dst: str,
        sport: int,
        dport: int,
    ) -> None:
        if len(self.rows) >= self.window:
            self._pop_oldest()
        row = (
            float(ts),
            float(len_log),
            float(len_raw),
            float(is_tcp),
            float(is_udp),
            float(syn),
            float(ack),
            float(rst),
            float(fin),
            str(src),
            str(dst),
            int(sport),
            int(dport),
        )
        self.rows.append(row)
        self.sum_len_log += row[1]
        self.sum_len_log2 += row[1] * row[1]
        self.sum_len_raw += row[2]
        self.sum_tcp += row[3]
        self.sum_udp += row[4]
        self.sum_syn += row[5]
        self.sum_ack += row[6]
        self.sum_rst += row[7]
        self.sum_fin += row[8]
        self.src_counter[row[9]] += 1
        self.dst_counter[row[10]] += 1
        self.sport_counter[row[11]] += 1
        self.dport_counter[row[12]] += 1

    @property
    def count(self) -> int:
        return len(self.rows)

    @property
    def byte_sum(self) -> float:
        return float(self.sum_len_raw)

    def count_frac(self) -> float:
        return safe_div(self.count, self.window)

    def byte_rate_log(self, current_ts: float) -> float:
        if self.count < 2:
            return 0.0
        duration = max(1e-6, float(self.rows[-1][0]) - float(self.rows[0][0]))
        return float(np.log1p(max(0.0, self.sum_len_raw) / duration))

    def features(self, current_ts: float, unique_names: list[str]) -> list[float]:
        n = self.count
        if n == 0:
            return [0.0] * (len(STATE_BASE) + len(unique_names))
        mean = self.sum_len_log / n
        var = max(0.0, self.sum_len_log2 / n - mean * mean)
        duration = max(0.0, float(self.rows[-1][0]) - float(self.rows[0][0])) if n >= 2 else 0.0
        event_rate = safe_div(n, max(duration, 1e-6)) if n >= 2 else 0.0
        byte_rate = safe_div(self.sum_len_raw, max(duration, 1e-6)) if n >= 2 else 0.0
        gap = max(0.0, float(current_ts) - float(self.rows[-1][0]))
        out = [
            safe_div(n, self.window),
            float(mean),
            float(math.sqrt(var)),
            safe_div(self.sum_tcp, n),
            safe_div(self.sum_udp, n),
            safe_div(self.sum_syn, n),
            safe_div(self.sum_ack, n),
            safe_div(self.sum_rst, n),
            safe_div(self.sum_fin, n),
            float(np.log1p(duration)),
            float(np.log1p(max(0.0, event_rate))),
            float(np.log1p(max(0.0, byte_rate))),
            float(np.log1p(gap)),
        ]
        for name in unique_names:
            if name == "unique_src_frac":
                out.append(safe_div(len(self.src_counter), self.window))
            elif name == "unique_dst_frac":
                out.append(safe_div(len(self.dst_counter), self.window))
            elif name == "unique_sport_frac":
                out.append(safe_div(len(self.sport_counter), self.window))
            elif name == "unique_dport_frac":
                out.append(safe_div(len(self.dport_counter), self.window))
            else:
                raise ValueError(name)
        return out


class FlowTemporalZipFeatureCache:
    def __init__(self, zip_path: Path, smoke: bool = False, local_context_only: bool = False):
        if not zip_path.exists():
            raise FileNotFoundError(f"Missing Gotham raw zip: {zip_path}")
        self.zip_path = zip_path
        self.smoke = bool(smoke)
        self.local_context_only = bool(local_context_only)
        self._features: dict[str, dict[int, np.ndarray]] = {}
        self._row_audits: dict[str, dict[int, dict[str, Any]]] = {}
        self.audit_rows: list[dict[str, Any]] = []

    def read_processed(self, member: str) -> pd.DataFrame:
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as f:
                return pd.read_csv(f, usecols=lambda col: col in PROCESSED_USECOLS, low_memory=False)

    def read_processed_prefix(self, member: str, nrows: int) -> pd.DataFrame:
        nrows = max(0, int(nrows))
        if nrows <= 0:
            return pd.DataFrame()
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as f:
                return pd.read_csv(
                    f,
                    usecols=lambda col: col in PROCESSED_USECOLS,
                    nrows=nrows,
                    low_memory=False,
                )

    def read_processed_range(self, member: str, start: int, end: int) -> pd.DataFrame:
        nrows = max(0, int(end) - int(start) + 1)
        if nrows <= 0:
            return pd.DataFrame()
        with zipfile.ZipFile(self.zip_path) as zf:
            if member not in zf.namelist():
                raise FileNotFoundError(f"{member} not found inside {self.zip_path}")
            with zf.open(member) as f:
                return pd.read_csv(
                    f,
                    usecols=lambda col: col in PROCESSED_USECOLS,
                    skiprows=range(1, int(start) + 1),
                    nrows=nrows,
                    low_memory=False,
                )

    def compute_window(
        self,
        df: pd.DataFrame,
        base_row: int,
        target: set[int],
        features: dict[int, np.ndarray],
        row_audits: dict[int, dict[str, Any]],
    ) -> int:
        if len(df) == 0:
            return 0
        ts = event_time(len(df) - 1) + float(base_row)
        label_col = df.get("label", pd.Series([""] * len(df))).astype(str).to_numpy()
        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        ip_proto = cko.safe_num(df.get("ip.proto", pd.Series([0] * len(df))), 0.0)
        ip_ttl = cko.safe_num(df.get("ip.ttl", pd.Series([0] * len(df))), 0.0)
        frame_len_raw = cko.safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0)
        frame_len_log = np.log1p(frame_len_raw)
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

        file_state = {w: DeepRollingState(w) for w in WINDOWS}
        src_state: dict[str, dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
        dst_state: dict[str, dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
        pair_state: dict[tuple[str, str], dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
        flow_state: dict[tuple[str, str, int, int, int], dict[int, DeepRollingState]] = defaultdict(
            lambda: {w: DeepRollingState(w) for w in WINDOWS}
        )

        for j in range(len(df)):
            i = int(base_row) + j
            proto = str(proto_text[j]).lower()
            is_tcp = float(ip_proto[j] == 6 or tcp_src[j] > 0 or tcp_dst[j] > 0 or "tcp" in proto)
            is_udp = float(ip_proto[j] == 17 or udp_src[j] > 0 or udp_dst[j] > 0 or "udp" in proto)
            is_icmp = float(ip_proto[j] == 1 or "icmp" in proto)
            src_port = float(tcp_src[j] if tcp_src[j] > 0 else udp_src[j])
            dst_port = float(tcp_dst[j] if tcp_dst[j] > 0 else udp_dst[j])
            sport_i = int(src_port) if np.isfinite(src_port) and src_port > 0 else 0
            dport_i = int(dst_port) if np.isfinite(dst_port) and dst_port > 0 else 0
            flags = int(tcp_flags[j])
            syn = float(bool(flags & 0x02))
            ack = float(bool(flags & 0x10))
            rst = float(bool(flags & 0x04))
            fin = float(bool(flags & 0x01))
            src = cko.coalesce_str(ip_src[j], eth_src[j], f"row{i}:src")
            dst = cko.coalesce_str(ip_dst[j], eth_dst[j], f"row{i}:dst")
            pair_key = (src, dst)
            reverse_key = (dst, src)
            flow_key = (src, dst, int(ip_proto[j]) if np.isfinite(ip_proto[j]) else 0, sport_i, dport_i)
            current_ts = float(ts[j])

            cur = [
                float(frame_len_log[j]),
                is_tcp,
                is_udp,
                is_icmp,
                float(np.log1p(max(src_port, 0.0))),
                float(np.log1p(max(dst_port, 0.0))),
                float(0 < dst_port <= 1024),
                float(dport_i == 53 or "dns" in proto),
                float(dport_i == 5683 or "coap" in proto),
                float(dport_i in {80, 8080} or "http" in proto),
                float(dport_i == 443 or "tls" in proto or "ssl" in proto),
                syn,
                ack,
                rst,
                fin,
                float(syn > 0 and ack == 0),
                float(ack > 0 and syn == 0),
                float(np.clip(ip_ttl[j] / 255.0, 0.0, 1.0)) if np.isfinite(ip_ttl[j]) else 0.0,
                float(np.log1p(max(tcp_window[j], 0.0))),
                float(np.log1p(max(tcp_pdu[j], 0.0))),
            ]

            if i in target:
                vals = list(cur)
                for w in WINDOWS:
                    vals.extend(file_state[w].features(current_ts, ["unique_src_frac", "unique_dst_frac", "unique_dport_frac"]))
                    vals.extend(src_state[src][w].features(current_ts, ["unique_dst_frac", "unique_dport_frac"]))
                    vals.extend(dst_state[dst][w].features(current_ts, ["unique_src_frac", "unique_sport_frac"]))
                    vals.extend(pair_state[pair_key][w].features(current_ts, ["unique_sport_frac", "unique_dport_frac"]))
                    vals.extend(flow_state[flow_key][w].features(current_ts, []))
                    fwd = pair_state[pair_key][w]
                    rev = pair_state[reverse_key][w]
                    fwd_count = fwd.count_frac()
                    rev_count = rev.count_frac()
                    fwd_bytes = fwd.byte_sum
                    rev_bytes = rev.byte_sum
                    vals.extend(
                        [
                            rev_count,
                            rev.byte_rate_log(current_ts),
                            safe_div(fwd_count - rev_count, fwd_count + rev_count + 1e-6),
                            safe_div(fwd_bytes - rev_bytes, fwd_bytes + rev_bytes + 1.0),
                            float(rev.count > 0),
                        ]
                    )
                for short, long in SHORT_LONG_PAIRS:
                    vals.extend(
                        [
                            safe_div(src_state[src][short].count_frac(), src_state[src][long].count_frac() + 1e-6),
                            safe_div(
                                len(src_state[src][short].dport_counter) / short,
                                len(src_state[src][long].dport_counter) / long + 1e-6,
                            ),
                            safe_div(
                                len(dst_state[dst][short].src_counter) / short,
                                len(dst_state[dst][long].src_counter) / long + 1e-6,
                            ),
                            safe_div(pair_state[pair_key][short].count_frac(), pair_state[pair_key][long].count_frac() + 1e-6),
                            safe_div(flow_state[flow_key][short].count_frac(), flow_state[flow_key][long].count_frac() + 1e-6),
                        ]
                    )
                features[i] = np.asarray(vals, dtype=np.float32)
                row_audits[i] = {
                    "processed_row_exists": True,
                    "processed_label": label_col[j],
                    "processed_frame_protocols": proto_text[j],
                    "processed_frame_len": float(frame_len_raw[j]),
                    "processed_ip_proto": float(ip_proto[j]),
                    "processed_src": src,
                    "processed_dst": dst,
                    "processed_src_port": float(src_port),
                    "processed_dst_port": float(dst_port),
                    "processed_tcp_flags": int(flags),
                    "processed_time_seconds": current_ts,
                }

            for w in WINDOWS:
                for state in [file_state[w], src_state[src][w], dst_state[dst][w], pair_state[pair_key][w], flow_state[flow_key][w]]:
                    state.update(current_ts, float(frame_len_log[j]), float(frame_len_raw[j]), is_tcp, is_udp, syn, ack, rst, fin, src, dst, sport_i, dport_i)
        return len(df)

    def _tail_before(self, idx_list: list[int], row_pos: int, window: int) -> list[int]:
        pos = bisect.bisect_left(idx_list, int(row_pos))
        return idx_list[max(0, pos - int(window)) : pos]

    def _state_features_from_indices(
        self,
        idx: list[int],
        window: int,
        current_ts: float,
        unique_names: list[str],
        data: dict[str, np.ndarray],
    ) -> list[float]:
        n = len(idx)
        if n == 0:
            return [0.0] * (len(STATE_BASE) + len(unique_names))
        arr_idx = np.asarray(idx, dtype=np.int64)
        len_log = data["frame_len_log"][arr_idx]
        len_raw = data["frame_len_raw"][arr_idx]
        duration = max(0.0, float(data["ts"][arr_idx[-1]]) - float(data["ts"][arr_idx[0]])) if n >= 2 else 0.0
        event_rate = safe_div(n, max(duration, 1e-6)) if n >= 2 else 0.0
        byte_rate = safe_div(float(np.sum(len_raw)), max(duration, 1e-6)) if n >= 2 else 0.0
        gap = max(0.0, float(current_ts) - float(data["ts"][arr_idx[-1]]))
        mean = float(np.mean(len_log))
        var = max(0.0, float(np.mean(len_log * len_log)) - mean * mean)
        out = [
            safe_div(n, window),
            mean,
            float(math.sqrt(var)),
            safe_div(float(np.sum(data["is_tcp"][arr_idx])), n),
            safe_div(float(np.sum(data["is_udp"][arr_idx])), n),
            safe_div(float(np.sum(data["syn"][arr_idx])), n),
            safe_div(float(np.sum(data["ack"][arr_idx])), n),
            safe_div(float(np.sum(data["rst"][arr_idx])), n),
            safe_div(float(np.sum(data["fin"][arr_idx])), n),
            float(np.log1p(duration)),
            float(np.log1p(event_rate)),
            float(np.log1p(byte_rate)),
            float(np.log1p(gap)),
        ]
        for name in unique_names:
            if name == "unique_src_frac":
                out.append(safe_div(len(set(data["src"][arr_idx])), window))
            elif name == "unique_dst_frac":
                out.append(safe_div(len(set(data["dst"][arr_idx])), window))
            elif name == "unique_sport_frac":
                out.append(safe_div(len(set(data["sport"][arr_idx])), window))
            elif name == "unique_dport_frac":
                out.append(safe_div(len(set(data["dport"][arr_idx])), window))
            else:
                raise ValueError(name)
        return out

    def _count_frac_from_indices(self, idx: list[int], window: int) -> float:
        return safe_div(len(idx), window)

    def _byte_sum_from_indices(self, idx: list[int], data: dict[str, np.ndarray]) -> float:
        if not idx:
            return 0.0
        return float(np.sum(data["frame_len_raw"][np.asarray(idx, dtype=np.int64)]))

    def _byte_rate_log_from_indices(self, idx: list[int], data: dict[str, np.ndarray]) -> float:
        if len(idx) < 2:
            return 0.0
        arr_idx = np.asarray(idx, dtype=np.int64)
        duration = max(1e-6, float(data["ts"][arr_idx[-1]]) - float(data["ts"][arr_idx[0]]))
        return float(np.log1p(max(0.0, float(np.sum(data["frame_len_raw"][arr_idx]))) / duration))

    def compute_targeted_prefix(
        self,
        df: pd.DataFrame,
        base_row: int,
        target: set[int],
        features: dict[int, np.ndarray],
        row_audits: dict[int, dict[str, Any]],
    ) -> int:
        """Exact complete-past event-window features for sparse target rows."""

        if len(df) == 0:
            return 0
        target_pos = sorted(int(i) - int(base_row) for i in target if int(base_row) <= int(i) < int(base_row) + len(df))
        if not target_pos:
            return len(df)

        ts = event_time(len(df) - 1) + float(base_row)
        label_col = df.get("label", pd.Series([""] * len(df))).astype(str).to_numpy()
        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        proto_lower = np.asarray([str(v).lower() for v in proto_text], dtype=object)
        ip_proto = cko.safe_num(df.get("ip.proto", pd.Series([0] * len(df))), 0.0)
        ip_ttl = cko.safe_num(df.get("ip.ttl", pd.Series([0] * len(df))), 0.0)
        frame_len_raw = cko.safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0)
        frame_len_log = np.log1p(frame_len_raw)
        tcp_src = cko.safe_num(df.get("tcp.srcport", pd.Series([0] * len(df))), 0.0)
        tcp_dst = cko.safe_num(df.get("tcp.dstport", pd.Series([0] * len(df))), 0.0)
        udp_src = cko.safe_num(df.get("udp.srcport", pd.Series([0] * len(df))), 0.0)
        udp_dst = cko.safe_num(df.get("udp.dstport", pd.Series([0] * len(df))), 0.0)
        tcp_window = cko.safe_num(df.get("tcp.window_size_value", pd.Series([0] * len(df))), 0.0)
        tcp_pdu = cko.safe_num(df.get("tcp.pdu.size", pd.Series([0] * len(df))), 0.0)
        tcp_flags = np.asarray([cko.parse_tcp_flags(v) for v in df.get("tcp.flags", pd.Series([0] * len(df))).to_numpy()], dtype=np.int64)
        ip_src = df.get("ip.src", pd.Series([""] * len(df))).to_numpy()
        ip_dst = df.get("ip.dst", pd.Series([""] * len(df))).to_numpy()
        eth_src = df.get("eth.src", pd.Series([""] * len(df))).to_numpy()
        eth_dst = df.get("eth.dst", pd.Series([""] * len(df))).to_numpy()

        src_arr = np.asarray([cko.coalesce_str(ip_src[j], eth_src[j], f"row{base_row + j}:src") for j in range(len(df))], dtype=object)
        dst_arr = np.asarray([cko.coalesce_str(ip_dst[j], eth_dst[j], f"row{base_row + j}:dst") for j in range(len(df))], dtype=object)
        src_port = np.where(tcp_src > 0, tcp_src, udp_src)
        dst_port = np.where(tcp_dst > 0, tcp_dst, udp_dst)
        sport = np.asarray([int(v) if np.isfinite(v) and v > 0 else 0 for v in src_port], dtype=np.int64)
        dport = np.asarray([int(v) if np.isfinite(v) and v > 0 else 0 for v in dst_port], dtype=np.int64)
        proto_int = np.asarray([int(v) if np.isfinite(v) else 0 for v in ip_proto], dtype=np.int64)
        proto_as_str = proto_lower.astype(str)
        is_tcp = ((ip_proto == 6) | (tcp_src > 0) | (tcp_dst > 0) | (np.char.find(proto_as_str, "tcp") >= 0)).astype(float)
        is_udp = ((ip_proto == 17) | (udp_src > 0) | (udp_dst > 0) | (np.char.find(proto_as_str, "udp") >= 0)).astype(float)
        is_icmp = ((ip_proto == 1) | (np.char.find(proto_as_str, "icmp") >= 0)).astype(float)
        syn = ((tcp_flags & 0x02) > 0).astype(float)
        ack = ((tcp_flags & 0x10) > 0).astype(float)
        rst = ((tcp_flags & 0x04) > 0).astype(float)
        fin = ((tcp_flags & 0x01) > 0).astype(float)

        data = {
            "ts": ts,
            "frame_len_raw": frame_len_raw,
            "frame_len_log": frame_len_log,
            "is_tcp": is_tcp,
            "is_udp": is_udp,
            "syn": syn,
            "ack": ack,
            "rst": rst,
            "fin": fin,
            "src": src_arr,
            "dst": dst_arr,
            "sport": sport,
            "dport": dport,
        }

        needed_src = {str(src_arr[j]) for j in target_pos}
        needed_dst = {str(dst_arr[j]) for j in target_pos}
        needed_pairs: set[tuple[str, str]] = set()
        needed_flows: set[tuple[str, str, int, int, int]] = set()
        for j in target_pos:
            pair = (str(src_arr[j]), str(dst_arr[j]))
            needed_pairs.add(pair)
            needed_pairs.add((pair[1], pair[0]))
            needed_flows.add((pair[0], pair[1], int(proto_int[j]), int(sport[j]), int(dport[j])))

        src_index: dict[str, list[int]] = defaultdict(list)
        dst_index: dict[str, list[int]] = defaultdict(list)
        pair_index: dict[tuple[str, str], list[int]] = defaultdict(list)
        flow_index: dict[tuple[str, str, int, int, int], list[int]] = defaultdict(list)
        for j in range(len(df)):
            src = str(src_arr[j])
            dst = str(dst_arr[j])
            if src in needed_src:
                src_index[src].append(j)
            if dst in needed_dst:
                dst_index[dst].append(j)
            pair = (src, dst)
            if pair in needed_pairs:
                pair_index[pair].append(j)
            flow = (src, dst, int(proto_int[j]), int(sport[j]), int(dport[j]))
            if flow in needed_flows:
                flow_index[flow].append(j)

        for j in target_pos:
            i = int(base_row) + j
            proto = str(proto_lower[j])
            pair_key = (str(src_arr[j]), str(dst_arr[j]))
            reverse_key = (pair_key[1], pair_key[0])
            flow_key = (pair_key[0], pair_key[1], int(proto_int[j]), int(sport[j]), int(dport[j]))
            current_ts = float(ts[j])
            vals = [
                float(frame_len_log[j]),
                float(is_tcp[j]),
                float(is_udp[j]),
                float(is_icmp[j]),
                float(np.log1p(max(float(src_port[j]), 0.0))),
                float(np.log1p(max(float(dst_port[j]), 0.0))),
                float(0 < float(dst_port[j]) <= 1024),
                float(int(dport[j]) == 53 or "dns" in proto),
                float(int(dport[j]) == 5683 or "coap" in proto),
                float(int(dport[j]) in {80, 8080} or "http" in proto),
                float(int(dport[j]) == 443 or "tls" in proto or "ssl" in proto),
                float(syn[j]),
                float(ack[j]),
                float(rst[j]),
                float(fin[j]),
                float(syn[j] > 0 and ack[j] == 0),
                float(ack[j] > 0 and syn[j] == 0),
                float(np.clip(ip_ttl[j] / 255.0, 0.0, 1.0)) if np.isfinite(ip_ttl[j]) else 0.0,
                float(np.log1p(max(float(tcp_window[j]), 0.0))),
                float(np.log1p(max(float(tcp_pdu[j]), 0.0))),
            ]
            for w in WINDOWS:
                file_tail = list(range(max(0, j - w), j))
                src_tail = self._tail_before(src_index.get(pair_key[0], []), j, w)
                dst_tail = self._tail_before(dst_index.get(pair_key[1], []), j, w)
                pair_tail = self._tail_before(pair_index.get(pair_key, []), j, w)
                flow_tail = self._tail_before(flow_index.get(flow_key, []), j, w)
                rev_tail = self._tail_before(pair_index.get(reverse_key, []), j, w)
                vals.extend(self._state_features_from_indices(file_tail, w, current_ts, ["unique_src_frac", "unique_dst_frac", "unique_dport_frac"], data))
                vals.extend(self._state_features_from_indices(src_tail, w, current_ts, ["unique_dst_frac", "unique_dport_frac"], data))
                vals.extend(self._state_features_from_indices(dst_tail, w, current_ts, ["unique_src_frac", "unique_sport_frac"], data))
                vals.extend(self._state_features_from_indices(pair_tail, w, current_ts, ["unique_sport_frac", "unique_dport_frac"], data))
                vals.extend(self._state_features_from_indices(flow_tail, w, current_ts, [], data))
                fwd_count = self._count_frac_from_indices(pair_tail, w)
                rev_count = self._count_frac_from_indices(rev_tail, w)
                fwd_bytes = self._byte_sum_from_indices(pair_tail, data)
                rev_bytes = self._byte_sum_from_indices(rev_tail, data)
                vals.extend(
                    [
                        rev_count,
                        self._byte_rate_log_from_indices(rev_tail, data),
                        safe_div(fwd_count - rev_count, fwd_count + rev_count + 1e-6),
                        safe_div(fwd_bytes - rev_bytes, fwd_bytes + rev_bytes + 1.0),
                        float(len(rev_tail) > 0),
                    ]
                )
            for short, long in SHORT_LONG_PAIRS:
                src_short = self._tail_before(src_index.get(pair_key[0], []), j, short)
                src_long = self._tail_before(src_index.get(pair_key[0], []), j, long)
                dst_short = self._tail_before(dst_index.get(pair_key[1], []), j, short)
                dst_long = self._tail_before(dst_index.get(pair_key[1], []), j, long)
                pair_short = self._tail_before(pair_index.get(pair_key, []), j, short)
                pair_long = self._tail_before(pair_index.get(pair_key, []), j, long)
                flow_short = self._tail_before(flow_index.get(flow_key, []), j, short)
                flow_long = self._tail_before(flow_index.get(flow_key, []), j, long)
                vals.extend(
                    [
                        safe_div(self._count_frac_from_indices(src_short, short), self._count_frac_from_indices(src_long, long) + 1e-6),
                        safe_div(safe_div(len(set(dport[src_short])), short), safe_div(len(set(dport[src_long])), long) + 1e-6),
                        safe_div(safe_div(len(set(src_arr[dst_short])), short), safe_div(len(set(src_arr[dst_long])), long) + 1e-6),
                        safe_div(self._count_frac_from_indices(pair_short, short), self._count_frac_from_indices(pair_long, long) + 1e-6),
                        safe_div(self._count_frac_from_indices(flow_short, short), self._count_frac_from_indices(flow_long, long) + 1e-6),
                    ]
                )
            features[i] = np.asarray(vals, dtype=np.float32)
            row_audits[i] = {
                "processed_row_exists": True,
                "processed_label": label_col[j],
                "processed_frame_protocols": proto_text[j],
                "processed_frame_len": float(frame_len_raw[j]),
                "processed_ip_proto": float(ip_proto[j]),
                "processed_src": pair_key[0],
                "processed_dst": pair_key[1],
                "processed_src_port": float(src_port[j]),
                "processed_dst_port": float(dst_port[j]),
                "processed_tcp_flags": int(tcp_flags[j]),
                "processed_time_seconds": current_ts,
            }
        return len(df)

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        requested = sorted({int(v) for v in np.asarray(row_indices, dtype=np.int64) if int(v) >= 0})
        if not requested:
            return {}
        known = self._features.get(member, {})
        missing = [idx for idx in requested if idx not in known]
        if not missing:
            return {idx: known[idx] for idx in requested}

        started = time.time()
        if self.local_context_only:
            target = set(missing)
            scan_ranges: list[tuple[int, int]] = []
            for idx in sorted(target):
                start = max(0, int(idx) - max(WINDOWS))
                end = int(idx)
                if scan_ranges and start <= scan_ranges[-1][1] + 1:
                    scan_ranges[-1] = (scan_ranges[-1][0], max(scan_ranges[-1][1], end))
                else:
                    scan_ranges.append((start, end))
            features: dict[int, np.ndarray] = dict(known)
            row_audits: dict[int, dict[str, Any]] = dict(self._row_audits.get(member, {}))
            scanned_rows = 0
            for start, end in scan_ranges:
                df_range = self.read_processed_range(member, start, end)
                scanned_rows += self.compute_window(df_range, start, target, features, row_audits)
            computed_new = sum(1 for idx in target if idx in features)
            missing_oob = len(target) - computed_new
            self._features[member] = features
            self._row_audits[member] = row_audits
            self.audit_rows.append(
                {
                    "csv_member": member,
                    "requested_rows": len(requested),
                    "computed_new_rows": computed_new,
                    "out_of_bounds_rows": missing_oob,
                    "processed_rows_read": "",
                    "scanned_rows_for_features": scanned_rows,
                    "max_requested_row": max(requested),
                    "scan_ranges": len(scan_ranges),
                    "first_start_row_scanned": scan_ranges[0][0] if scan_ranges else "",
                    "feature_dim": len(FLOW_TEMPORAL_FEATURES),
                    "local_context_only": self.local_context_only,
                    "seconds": time.time() - started,
                    "label_column_read_for_audit_not_feature": True,
                }
            )
            return {idx: features[idx] for idx in requested if idx in features}

        # Complete-past semantics only require rows [0, max(requested)].
        # Reading the whole processed member made local smoke unreasonably slow
        # for multi-million-row files while adding no extra feature information.
        df = self.read_processed_prefix(member, max(missing) + 1)
        max_needed = min(max(missing), len(df) - 1)
        target = set(idx for idx in missing if idx < len(df))
        missing_oob = len(missing) - len(target)
        features: dict[int, np.ndarray] = dict(known)
        row_audits: dict[int, dict[str, Any]] = dict(self._row_audits.get(member, {}))
        scanned_rows = self.compute_targeted_prefix(df, 0, target, features, row_audits)
        computed_new = sum(1 for idx in target if idx in features)
        self._features[member] = features
        self._row_audits[member] = row_audits
        self.audit_rows.append(
            {
                "csv_member": member,
                "requested_rows": len(requested),
                "computed_new_rows": computed_new,
                "out_of_bounds_rows": missing_oob + (len(target) - computed_new),
                "processed_rows_read": len(df),
                "scanned_rows_for_features": scanned_rows,
                "max_requested_row": max(requested),
                "scan_ranges": 1 if target else 0,
                "first_start_row_scanned": 0 if target else "",
                "feature_dim": len(FLOW_TEMPORAL_FEATURES),
                "local_context_only": self.local_context_only,
                "targeted_complete_past_prefix": True,
                "seconds": time.time() - started,
                "label_column_read_for_audit_not_feature": "label" in df.columns,
            }
        )
        return {idx: features[idx] for idx in requested if idx in features}
        if self.local_context_only and target:
            scan_ranges: list[tuple[int, int]] = []
            for idx in sorted(target):
                start = max(0, int(idx) - max(WINDOWS))
                end = int(idx)
                if scan_ranges and start <= scan_ranges[-1][1] + 1:
                    scan_ranges[-1] = (scan_ranges[-1][0], max(scan_ranges[-1][1], end))
                else:
                    scan_ranges.append((start, end))
        else:
            scan_ranges = [(0, max_needed)] if target else []
        features: dict[int, np.ndarray] = dict(known)
        row_audits: dict[int, dict[str, Any]] = dict(self._row_audits.get(member, {}))

        ts = event_time(max_needed)
        label_col = df.get("label", pd.Series([""] * len(df))).astype(str).to_numpy()
        proto_text = df.get("frame.protocols", pd.Series([""] * len(df))).astype(str).to_numpy()
        ip_proto = cko.safe_num(df.get("ip.proto", pd.Series([0] * len(df))), 0.0)
        ip_ttl = cko.safe_num(df.get("ip.ttl", pd.Series([0] * len(df))), 0.0)
        frame_len_raw = cko.safe_num(df.get("frame.len", pd.Series([0] * len(df))), 0.0)
        frame_len_log = np.log1p(frame_len_raw)
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

        scanned_rows = 0
        for range_start, range_end in scan_ranges:
            file_state = {w: DeepRollingState(w) for w in WINDOWS}
            src_state: dict[str, dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
            dst_state: dict[str, dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
            pair_state: dict[tuple[str, str], dict[int, DeepRollingState]] = defaultdict(lambda: {w: DeepRollingState(w) for w in WINDOWS})
            flow_state: dict[tuple[str, str, int, int, int], dict[int, DeepRollingState]] = defaultdict(
                lambda: {w: DeepRollingState(w) for w in WINDOWS}
            )

            for i in range(range_start, range_end + 1):
                scanned_rows += 1
                proto = str(proto_text[i]).lower()
                is_tcp = float(ip_proto[i] == 6 or tcp_src[i] > 0 or tcp_dst[i] > 0 or "tcp" in proto)
                is_udp = float(ip_proto[i] == 17 or udp_src[i] > 0 or udp_dst[i] > 0 or "udp" in proto)
                is_icmp = float(ip_proto[i] == 1 or "icmp" in proto)
                src_port = float(tcp_src[i] if tcp_src[i] > 0 else udp_src[i])
                dst_port = float(tcp_dst[i] if tcp_dst[i] > 0 else udp_dst[i])
                sport_i = int(src_port) if np.isfinite(src_port) and src_port > 0 else 0
                dport_i = int(dst_port) if np.isfinite(dst_port) and dst_port > 0 else 0
                flags = int(tcp_flags[i])
                syn = float(bool(flags & 0x02))
                ack = float(bool(flags & 0x10))
                rst = float(bool(flags & 0x04))
                fin = float(bool(flags & 0x01))
                src = cko.coalesce_str(ip_src[i], eth_src[i], f"row{i}:src")
                dst = cko.coalesce_str(ip_dst[i], eth_dst[i], f"row{i}:dst")
                pair_key = (src, dst)
                reverse_key = (dst, src)
                flow_key = (src, dst, int(ip_proto[i]) if np.isfinite(ip_proto[i]) else 0, sport_i, dport_i)
                current_ts = float(ts[i])

                cur = [
                    float(frame_len_log[i]),
                    is_tcp,
                    is_udp,
                    is_icmp,
                    float(np.log1p(max(src_port, 0.0))),
                    float(np.log1p(max(dst_port, 0.0))),
                    float(0 < dst_port <= 1024),
                    float(dport_i == 53 or "dns" in proto),
                    float(dport_i == 5683 or "coap" in proto),
                    float(dport_i in {80, 8080} or "http" in proto),
                    float(dport_i == 443 or "tls" in proto or "ssl" in proto),
                    syn,
                    ack,
                    rst,
                    fin,
                    float(syn > 0 and ack == 0),
                    float(ack > 0 and syn == 0),
                    float(np.clip(ip_ttl[i] / 255.0, 0.0, 1.0)) if np.isfinite(ip_ttl[i]) else 0.0,
                    float(np.log1p(max(tcp_window[i], 0.0))),
                    float(np.log1p(max(tcp_pdu[i], 0.0))),
                ]

                if i in target:
                    vals = list(cur)
                    for w in WINDOWS:
                        vals.extend(file_state[w].features(current_ts, ["unique_src_frac", "unique_dst_frac", "unique_dport_frac"]))
                        vals.extend(src_state[src][w].features(current_ts, ["unique_dst_frac", "unique_dport_frac"]))
                        vals.extend(dst_state[dst][w].features(current_ts, ["unique_src_frac", "unique_sport_frac"]))
                        vals.extend(pair_state[pair_key][w].features(current_ts, ["unique_sport_frac", "unique_dport_frac"]))
                        vals.extend(flow_state[flow_key][w].features(current_ts, []))
                        fwd = pair_state[pair_key][w]
                        rev = pair_state[reverse_key][w]
                        fwd_count = fwd.count_frac()
                        rev_count = rev.count_frac()
                        fwd_bytes = fwd.byte_sum
                        rev_bytes = rev.byte_sum
                        vals.extend(
                            [
                                rev_count,
                                rev.byte_rate_log(current_ts),
                                safe_div(fwd_count - rev_count, fwd_count + rev_count + 1e-6),
                                safe_div(fwd_bytes - rev_bytes, fwd_bytes + rev_bytes + 1.0),
                                float(rev.count > 0),
                            ]
                        )
                    for short, long in SHORT_LONG_PAIRS:
                        vals.extend(
                            [
                                safe_div(src_state[src][short].count_frac(), src_state[src][long].count_frac() + 1e-6),
                                safe_div(
                                    len(src_state[src][short].dport_counter) / short,
                                    len(src_state[src][long].dport_counter) / long + 1e-6,
                                ),
                                safe_div(
                                    len(dst_state[dst][short].src_counter) / short,
                                    len(dst_state[dst][long].src_counter) / long + 1e-6,
                                ),
                                safe_div(pair_state[pair_key][short].count_frac(), pair_state[pair_key][long].count_frac() + 1e-6),
                                safe_div(flow_state[flow_key][short].count_frac(), flow_state[flow_key][long].count_frac() + 1e-6),
                            ]
                        )
                    features[i] = np.asarray(vals, dtype=np.float32)
                    row_audits[i] = {
                        "processed_row_exists": True,
                        "processed_label": label_col[i],
                        "processed_frame_protocols": proto_text[i],
                        "processed_frame_len": float(frame_len_raw[i]),
                        "processed_ip_proto": float(ip_proto[i]),
                        "processed_src": src,
                        "processed_dst": dst,
                        "processed_src_port": float(src_port),
                        "processed_dst_port": float(dst_port),
                        "processed_tcp_flags": int(flags),
                        "processed_time_seconds": current_ts,
                    }

                for w in WINDOWS:
                    for state in [
                        file_state[w],
                        src_state[src][w],
                        dst_state[dst][w],
                        pair_state[pair_key][w],
                        flow_state[flow_key][w],
                    ]:
                        state.update(
                            current_ts,
                            float(frame_len_log[i]),
                            float(frame_len_raw[i]),
                            is_tcp,
                            is_udp,
                            syn,
                            ack,
                            rst,
                            fin,
                            src,
                            dst,
                            sport_i,
                            dport_i,
                        )

        self._features[member] = features
        self._row_audits[member] = row_audits
        self.audit_rows.append(
            {
                "csv_member": member,
                "requested_rows": len(requested),
                "computed_new_rows": len(target),
                "out_of_bounds_rows": missing_oob,
                "processed_rows_read": len(df),
                "scanned_rows_for_features": scanned_rows,
                "max_requested_row": max(requested),
                "scan_ranges": len(scan_ranges),
                "first_start_row_scanned": scan_ranges[0][0] if scan_ranges else "",
                "feature_dim": len(FLOW_TEMPORAL_FEATURES),
                "local_context_only": self.local_context_only,
                "seconds": time.time() - started,
                "label_column_read_for_audit_not_feature": "label" in df.columns,
            }
        )
        return {idx: features[idx] for idx in requested if idx in features}

    def row_audits_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, dict[str, Any]]:
        requested = sorted({int(v) for v in np.asarray(row_indices, dtype=np.int64) if int(v) >= 0})
        if not requested:
            return {}
        self.features_for_member(member, np.asarray(requested, dtype=np.int64))
        known = self._row_audits.get(member, {})
        return {idx: known.get(idx, {"processed_row_exists": False}) for idx in requested}


def cap_loaded_roles(
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    per_phase_cap: int,
    per_source_cap: int = 64,
    cap_rule: str = "earliest recorded_index rows per phase/source for capped smoke",
) -> tuple[dict[str, np.ndarray], dict[str, pd.DataFrame], list[dict[str, Any]]]:
    capped_x: dict[str, np.ndarray] = {}
    capped_frame: dict[str, pd.DataFrame] = {}
    rows: list[dict[str, Any]] = []
    for role, frame in frame_by_role.items():
        frame0 = frame.reset_index(drop=True)
        if len(frame0) == 0 or "phase" not in frame0:
            positions = np.arange(min(len(frame0), per_phase_cap), dtype=np.int64)
        else:
            parts = []
            for _, group in frame0.groupby(frame0["phase"].astype(str), sort=True):
                phase_parts: list[int] = []
                if "source_group" in group and "recorded_index" in group:
                    for _, source_group in group.groupby(group["source_group"].astype(str), sort=True):
                        ordered = source_group.sort_values(["recorded_index"], kind="mergesort")
                        phase_parts.extend(ordered.index.to_numpy(dtype=np.int64)[:per_source_cap].tolist())
                        if len(phase_parts) >= per_phase_cap:
                            break
                else:
                    phase_parts.extend(group.index.to_numpy(dtype=np.int64)[:per_source_cap].tolist())
                parts.extend(phase_parts[:per_phase_cap])
            positions = np.asarray(sorted(set(parts)), dtype=np.int64)
        capped_frame[role] = frame0.iloc[positions].reset_index(drop=True)
        capped_x[role] = np.asarray(x_by_role[role][positions], dtype=np.float32)
        rows.append(
            {
                "role": role,
                "original_rows": len(frame0),
                "capped_rows": len(positions),
                "per_phase_cap": per_phase_cap,
                "per_source_cap": per_source_cap,
                "cap_rule": cap_rule,
            }
        )
    return capped_x, capped_frame, rows


class FlowTemporalBuilder:
    def __init__(self, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame], cache: FlowTemporalZipFeatureCache):
        self.x_by_role = x_by_role
        self.frame_by_role = frame_by_role
        self.cache = cache
        self.role_flow_cache: dict[str, np.ndarray] = {}

    def precompute_roles(self, roles: list[str]) -> None:
        need_by_member: dict[str, set[int]] = defaultdict(set)
        for role in roles:
            frame = self.frame_by_role[role].reset_index(drop=True)
            if len(frame) == 0:
                continue
            if "source_group" not in frame or "recorded_index" not in frame:
                raise RuntimeError(f"{role} frame lacks source_group/recorded_index")
            for member, group in frame.groupby(frame["source_group"].astype(str), sort=True):
                row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
                need_by_member[member].update(int(v) for v in row_idx if int(v) >= 0)
        for member, rows in sorted(need_by_member.items()):
            sorted_rows = sorted(rows)
            self.cache.features_for_member(member, np.asarray(sorted_rows, dtype=np.int64))

    def flow_for_role(self, role: str) -> np.ndarray:
        if role in self.role_flow_cache:
            return self.role_flow_cache[role]
        frame = self.frame_by_role[role].reset_index(drop=True)
        out = np.zeros((len(frame), len(FLOW_TEMPORAL_FEATURES)), dtype=np.float32)
        if len(frame) == 0:
            self.role_flow_cache[role] = out
            return out
        if "source_group" not in frame or "recorded_index" not in frame:
            raise RuntimeError(f"{role} frame lacks source_group/recorded_index")
        for member, group in frame.groupby(frame["source_group"].astype(str), sort=True):
            row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
            mapping = self.cache.features_for_member(member, row_idx)
            for pos, ridx in zip(group.index.to_numpy(dtype=np.int64), row_idx):
                feat = mapping.get(int(ridx))
                if feat is not None:
                    out[pos] = feat
        self.role_flow_cache[role] = np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)
        return self.role_flow_cache[role]

    def matrix(self, spec: cko.FeatureSpec, role: str, idx: np.ndarray) -> np.ndarray:
        raw = np.asarray(self.x_by_role[role][idx], dtype=np.float32)
        if spec.kind == "raw":
            return raw
        flow = self.flow_for_role(role)[idx]
        if spec.kind == "flow_temporal":
            return flow
        if spec.kind == "raw_plus_flow_temporal":
            return np.hstack([raw, flow]).astype(np.float32)
        raise ValueError(spec.kind)


def build_alignment_audit(
    builder: FlowTemporalBuilder,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
    sample_per_role: int = cko.ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in sorted(frame_by_role):
        frame = frame_by_role[role].reset_index(drop=True)
        x_role = x_by_role.get(role)
        x_rows = int(len(x_role)) if x_role is not None else -1
        x_dim = int(x_role.shape[1]) if x_role is not None and getattr(x_role, "ndim", 0) == 2 else -1
        length_match = x_rows == len(frame)
        if len(frame) == 0:
            rows.append({"role": role, "sampled": False, "alignment_ok": length_match})
            continue
        positions = cko.deterministic_cap(np.arange(len(frame), dtype=np.int64), sample_per_role)
        sample = frame.iloc[positions].copy()
        flow = builder.flow_for_role(role)
        for member, group in sample.groupby(sample["source_group"].astype(str), sort=True):
            row_idx = pd.to_numeric(group["recorded_index"], errors="coerce").fillna(-1).astype(int).to_numpy()
            audits = builder.cache.row_audits_for_member(member, row_idx)
            for pos, ridx in zip(group.index.to_numpy(dtype=np.int64), row_idx):
                record = frame.iloc[int(pos)]
                audit = audits.get(int(ridx), {})
                feat = flow[int(pos)] if 0 <= int(pos) < len(flow) else np.asarray([], dtype=np.float32)
                processed_exists = bool(audit.get("processed_row_exists", False))
                rows.append(
                    {
                        "role": role,
                        "sampled": True,
                        "row_index_in_role": int(pos),
                        "x_rows": x_rows,
                        "frame_rows": len(frame),
                        "x_dim": x_dim,
                        "x_frame_length_match": length_match,
                        "source_group": member,
                        "recorded_index": int(ridx),
                        "global_id": record.get("global_id", ""),
                        "phase": record.get("phase", ""),
                        "role_attack_label": record.get("attack_label", ""),
                        "processed_row_exists": processed_exists,
                        "processed_label": audit.get("processed_label", ""),
                        "processed_frame_protocols": audit.get("processed_frame_protocols", ""),
                        "processed_frame_len": audit.get("processed_frame_len", ""),
                        "processed_src": audit.get("processed_src", ""),
                        "processed_dst": audit.get("processed_dst", ""),
                        "processed_src_port": audit.get("processed_src_port", ""),
                        "processed_dst_port": audit.get("processed_dst_port", ""),
                        "flow_temporal_dim": int(len(feat)),
                        "flow_temporal_nonzero": int(np.count_nonzero(feat)) if len(feat) else 0,
                        "alignment_ok": bool(length_match and processed_exists and int(ridx) >= 0),
                    }
                )
    return rows


def fit_chunks(frame_by_role: dict[str, pd.DataFrame], train_cap: int) -> tuple[list[dict[str, Any]], np.ndarray, list[dict[str, Any]]]:
    chunks: list[dict[str, Any]] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = cko.role_indices(frame_by_role, role, phase, cap)
        chunks.append({"role": role, "phase": phase, "label": label, "idx": idx})
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append({"role": role, "phase": phase, "label": label, "label_name": CLASS_NAMES[label], "rows": len(idx)})

    add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    return chunks, np.concatenate(ys), audit


def matrix_for_chunks(builder: FlowTemporalBuilder, spec: cko.FeatureSpec, chunks: list[dict[str, Any]]) -> np.ndarray:
    return np.vstack([builder.matrix(spec, str(chunk["role"]), np.asarray(chunk["idx"], dtype=np.int64)) for chunk in chunks])


def proba4(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    out = np.zeros((len(x), len(CLASS_LABELS)), dtype=np.float64)
    for j, label in enumerate(CLASS_LABELS):
        if label in classes:
            out[:, j] = proba[:, classes.index(label)]
    return out


def entropy4(proba: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(proba, dtype=np.float64), 1e-12, 1.0)
    return -np.sum(p * np.log(p), axis=1)


def evidence_from_block_probas(probas: dict[str, np.ndarray], include_margins: bool) -> np.ndarray:
    raw = probas["raw"]
    flow = probas["flow"]
    blocks: list[np.ndarray] = [raw, flow]
    if include_margins:
        raw_attack = raw[:, ckh.CLASS_ATTACK]
        raw_conflict = np.maximum.reduce([raw[:, ckh.CLASS_ID], raw[:, ckh.CLASS_OOD], raw[:, ckh.CLASS_HARD_OOD]])
        flow_attack = flow[:, ckh.CLASS_ATTACK]
        flow_conflict = np.maximum.reduce([flow[:, ckh.CLASS_ID], flow[:, ckh.CLASS_OOD], flow[:, ckh.CLASS_HARD_OOD]])
        blocks.append(
            np.column_stack(
                [
                    raw_attack - raw_conflict,
                    flow_attack - flow_conflict,
                    raw[:, ckh.CLASS_HARD_OOD] - raw_attack,
                    flow[:, ckh.CLASS_HARD_OOD] - flow_attack,
                    raw[:, ckh.CLASS_OOD] - raw_attack,
                    flow[:, ckh.CLASS_OOD] - flow_attack,
                    raw_attack - flow_attack,
                    raw_conflict - flow_conflict,
                    np.abs(raw_attack - flow_attack),
                    np.abs(raw_conflict - flow_conflict),
                    entropy4(raw),
                    entropy4(flow),
                ]
            )
        )
    return np.hstack(blocks).astype(np.float32)


def choose_n_splits(y: np.ndarray) -> int:
    counts = [int(np.sum(y == label)) for label in np.unique(y)]
    return max(2, min(3, min(counts)))


def fit_block_oof_and_full(block_name: str, x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, Any, list[dict[str, Any]]]:
    n_splits = choose_n_splits(y)
    oof = np.zeros((len(y), len(CLASS_LABELS)), dtype=np.float64)
    rows: list[dict[str, Any]] = []
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=ckh.SEED)
    for fold, (train_idx, val_idx) in enumerate(splitter.split(x, y), start=1):
        model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x[train_idx], y[train_idx])
        oof[val_idx] = proba4(model, x[val_idx])
        pred = np.argmax(oof[val_idx], axis=1)
        rows.append(
            {
                "block": block_name,
                "fold": fold,
                "train_rows": len(train_idx),
                "val_rows": len(val_idx),
                "val_accuracy": float(np.mean(pred == y[val_idx])) if len(val_idx) else float("nan"),
            }
        )
    full_model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x, y)
    return oof, full_model, rows


def fit_control(
    spec: cko.FeatureSpec,
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
) -> tuple[Any, list[dict[str, Any]]]:
    chunks, y, audit = fit_chunks(frame_by_role, train_cap)
    x = matrix_for_chunks(builder, spec, chunks)
    model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x, y)
    for row in audit:
        row["candidate"] = spec.name
    return model, audit


def control_scores(model: Any, x: np.ndarray) -> dict[str, np.ndarray]:
    attack = ckh.class_score(model, x, ckh.CLASS_ATTACK)
    hard_ood = ckh.class_score(model, x, ckh.CLASS_HARD_OOD)
    ood = ckh.class_score(model, x, ckh.CLASS_OOD)
    identity = ckh.class_score(model, x, ckh.CLASS_ID)
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "ood_score": ood,
        "id_score": identity,
        "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
    }


def control_threshold(
    spec: cko.FeatureSpec,
    model: Any,
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = cko.role_indices(frame_by_role, role, "select", eval_cap)
        parts.append(control_scores(model, builder.matrix(spec, role, idx))["attack_score"])
    return float(max(np.quantile(part, cko.BENIGN_SAFE_Q) for part in parts))


def eval_control_role(
    spec: cko.FeatureSpec,
    model: Any,
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = cko.role_indices(frame_by_role, role, phase, eval_cap)
    score = control_scores(model, builder.matrix(spec, role, idx))
    return scored_part(spec.name, threshold, role, phase, role_kind, frame_by_role[role].iloc[idx], score)


def fit_structured_candidates(
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chunks, y, train_audit = fit_chunks(frame_by_role, train_cap)
    x_raw = matrix_for_chunks(builder, RAW_BLOCK, chunks)
    x_flow = matrix_for_chunks(builder, FLOW_BLOCK, chunks)
    raw_oof, raw_full, raw_rows = fit_block_oof_and_full("raw", x_raw, y)
    flow_oof, flow_full, flow_rows = fit_block_oof_and_full("flow_temporal", x_flow, y)
    oof_probas = {"raw": raw_oof, "flow": flow_oof}
    fitted: dict[str, dict[str, Any]] = {}
    meta_rows: list[dict[str, Any]] = []
    for candidate in EVIDENCE_CANDIDATES:
        x_meta = evidence_from_block_probas(oof_probas, candidate.include_margins)
        meta = ckh.balanced_fit(ckh.build_model(candidate.meta_model, multiclass=True), x_meta, y)
        meta_proba = proba4(meta, x_meta)
        pred = np.argmax(meta_proba, axis=1)
        meta_rows.append(
            {
                "candidate": candidate.name,
                "meta_model": candidate.meta_model,
                "include_margins": candidate.include_margins,
                "meta_train_rows": len(y),
                "meta_feature_dim": x_meta.shape[1],
                "oof_meta_accuracy": float(np.mean(pred == y)) if len(y) else float("nan"),
                "note": "meta head trained on out-of-fold block evidence only",
            }
        )
        fitted[candidate.name] = {
            "candidate": candidate,
            "block_models": {"raw": raw_full, "flow": flow_full},
            "meta": meta,
        }
    for row in train_audit:
        row["candidate"] = "structured_evidence_shared_fit_set"
    return fitted, train_audit, raw_rows + flow_rows + meta_rows


def structured_scores(fitted: dict[str, Any], builder: FlowTemporalBuilder, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    candidate: EvidenceCandidate = fitted["candidate"]
    raw_x = builder.matrix(RAW_BLOCK, role, idx)
    flow_x = builder.matrix(FLOW_BLOCK, role, idx)
    probas = {
        "raw": proba4(fitted["block_models"]["raw"], raw_x),
        "flow": proba4(fitted["block_models"]["flow"], flow_x),
    }
    x_meta = evidence_from_block_probas(probas, candidate.include_margins)
    meta_proba = proba4(fitted["meta"], x_meta)
    attack = meta_proba[:, ckh.CLASS_ATTACK]
    hard_ood = meta_proba[:, ckh.CLASS_HARD_OOD]
    ood = meta_proba[:, ckh.CLASS_OOD]
    identity = meta_proba[:, ckh.CLASS_ID]
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "ood_score": ood,
        "id_score": identity,
        "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
    }


def structured_threshold(
    fitted: dict[str, Any],
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = cko.role_indices(frame_by_role, role, "select", eval_cap)
        parts.append(structured_scores(fitted, builder, role, idx)["attack_score"])
    return float(max(np.quantile(part, cko.BENIGN_SAFE_Q) for part in parts))


def eval_structured_role(
    candidate_name: str,
    fitted: dict[str, Any],
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    builder: FlowTemporalBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = cko.role_indices(frame_by_role, role, phase, eval_cap)
    score = structured_scores(fitted, builder, role, idx)
    return scored_part(candidate_name, threshold, role, phase, role_kind, frame_by_role[role].iloc[idx], score)


def scored_part(
    name: str,
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    frame_part: pd.DataFrame,
    score: dict[str, np.ndarray],
) -> tuple[dict[str, Any], pd.DataFrame]:
    raw = score["attack_score"] > threshold
    conflict = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & (~conflict)
    part = frame_part.copy().reset_index(drop=True)
    for key, val in score.items():
        part[key] = val
    part["raw_alarm"] = raw
    part["conflict_review"] = conflict
    part["hard_alarm"] = hard
    return (
        {
            "feature_set": name,
            "role": role,
            "phase": phase,
            "role_kind": role_kind,
            "rows": len(part),
            "attack_threshold": threshold,
            "raw_alarm_rate": ckg.rate(raw),
            "conflict_review_rate": ckg.rate(conflict),
            "hard_alarm_rate": ckg.rate(hard),
            "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
            "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
        },
        part,
    )


def build_readout(matrix: list[dict[str, Any]], audit: list[dict[str, Any]], seconds: float, smoke: bool) -> list[str]:
    requested = sum(int(row.get("requested_rows", 0)) for row in audit)
    computed = sum(int(row.get("computed_new_rows", 0)) for row in audit)
    oob = sum(int(row.get("out_of_bounds_rows", 0)) for row in audit)
    lines = [
        "# issue27ckq flow-temporal evidence frontend v1",
        "",
        "## Scope",
        "",
        "Deep past-only flow interaction and temporal evidence from processed Gotham CSV rows.",
        "Controls include raw115, flow-temporal only, and naive concat.",
        "Structured candidates use raw115/flow-temporal evidence encoders plus one four-class fusion head.",
        f"Mode: `{'smoke' if smoke else 'full'}`.",
        "",
        "## Main matrix",
        "",
        "| candidate | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | sealed OOD group hard max | OOD-stress hard/review |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {cko.fmt(row['future_hard'])} | {cko.fmt(row['same_file_hard'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])} | "
            f"{cko.fmt(row['sealed_ood_group_hard_max'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Flow-temporal extraction audit",
            "",
            "| files read | requested rows | computed rows | out-of-bounds rows |",
            "|---:|---:|---:|---:|",
            f"| {len(audit)} | {requested} | {computed} | {oob} |",
            "",
            "## Guardrail",
            "",
            "- Success requires OOD hard/review not worse than raw115 while keeping future/sealed attack hard detection.",
            "- All flow-temporal features are current/past-only within the processed source file.",
            "- Query/future/final/report-only rows remain report-only.",
            "",
            f"Runtime seconds: `{cko.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    role_cap_requested = args.role_cap is not None
    smoke = bool(args.smoke or args.micro_smoke or role_cap_requested)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(smoke)
    role_cap_rows: list[dict[str, Any]] = []
    if args.micro_smoke or role_cap_requested:
        per_phase_cap = args.micro_role_cap if args.micro_smoke else int(args.role_cap)
        per_source_cap = args.micro_source_cap if args.micro_smoke else int(args.source_cap)
        cap_rule = (
            "earliest recorded_index rows per phase/source for local-context micro-smoke only"
            if args.micro_smoke
            else "earliest recorded_index rows per phase/source for complete-past capped smoke"
        )
        x_by_role, frame_by_role, role_cap_rows = cap_loaded_roles(
            x_by_role,
            frame_by_role,
            per_phase_cap,
            per_source_cap,
            cap_rule=cap_rule,
        )
    train_cap = MICRO_TRAIN_CAP if args.micro_smoke else (cko.SMOKE_TRAIN_CAP if args.smoke else cko.TRAIN_CAP)
    eval_cap = MICRO_EVAL_CAP if args.micro_smoke else (cko.SMOKE_EVAL_CAP if args.smoke else cko.FULL_CAP)
    cache = FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=smoke, local_context_only=args.micro_smoke)
    builder = FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    role_rows: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    oof_rows: list[dict[str, Any]] = []

    for spec in CONTROL_SPECS:
        model, audit = fit_control(spec, builder, frame_by_role, train_cap)
        threshold = control_threshold(spec, model, builder, frame_by_role, eval_cap)
        train_rows.extend(audit)
        for role, phase, kind in cko.ROLE_EVAL:
            row, part = eval_control_role(spec, model, threshold, role, phase, kind, builder, frame_by_role, eval_cap)
            role_rows.append(row)
            group_metrics.extend(cko.group_rows(spec, role, part))

    structured, structured_train_rows, structured_oof_rows = fit_structured_candidates(builder, frame_by_role, train_cap)
    train_rows.extend(structured_train_rows)
    oof_rows.extend(structured_oof_rows)
    for name, fitted in structured.items():
        threshold = structured_threshold(fitted, builder, frame_by_role, eval_cap)
        spec = cko.FeatureSpec(name, "structured_flow_temporal_evidence", fitted["candidate"].description)
        for role, phase, kind in cko.ROLE_EVAL:
            row, part = eval_structured_role(name, fitted, threshold, role, phase, kind, builder, frame_by_role, eval_cap)
            role_rows.append(row)
            group_metrics.extend(cko.group_rows(spec, role, part))

    matrix = cko.aggregate(role_rows, group_metrics)
    alignment_rows = build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(
        OUT / "candidate_matrix.csv",
        [
            {"name": spec.name, "kind": spec.kind, "description": spec.description, "candidate_type": "control"}
            for spec in CONTROL_SPECS
        ]
        + [
            {
                "name": c.name,
                "kind": "structured_flow_temporal_evidence",
                "description": c.description,
                "candidate_type": "structured",
                "include_margins": c.include_margins,
                "meta_model": c.meta_model,
            }
            for c in EVIDENCE_CANDIDATES
        ],
    )
    cko.write_csv(OUT / "train_audit.csv", train_rows)
    cko.write_csv(OUT / "oof_evidence_audit.csv", oof_rows)
    cko.write_csv(OUT / "role_metrics.csv", role_rows)
    cko.write_csv(OUT / "group_metrics_by_source_device.csv", group_metrics)
    cko.write_csv(OUT / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(OUT / "alignment_audit.csv", alignment_rows)
    cko.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    cko.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "deep flow-temporal evidence frontend; controls plus structured fusion",
            "smoke": smoke,
            "micro_smoke": args.micro_smoke,
            "train_cap": train_cap,
            "eval_cap": eval_cap,
            "feature_dim": len(FLOW_TEMPORAL_FEATURES),
            "windows": WINDOWS,
            "short_long_pairs": SHORT_LONG_PAIRS,
            "control_specs": [spec.__dict__ for spec in CONTROL_SPECS],
            "evidence_candidates": [asdict(c) for c in EVIDENCE_CANDIDATES],
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "report_only_roles_used_for_training": False,
                "alignment_audit_used_for_training": False,
                "processed_label_used_as_feature": False,
                "flow_temporal_state": "current/past-only within processed source file",
                "micro_smoke_local_context_only": bool(args.micro_smoke),
                "role_capped_complete_past_smoke": bool(role_cap_requested and not args.micro_smoke),
            },
            "input_audit": input_audit,
            "role_cap_audit": role_cap_rows,
            "alignment_audit": {
                "sample_per_role": cko.ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
                "rows": len(alignment_rows),
                "purpose": "report-only raw115-to-flow-temporal row pairing evidence",
            },
            "outputs": [
                "candidate_summary_matrix.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "train_audit.csv",
                "oof_evidence_audit.csv",
                "flow_temporal_extraction_audit.csv",
                "alignment_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    cko.write_csv(OUT / "role_cap_audit.csv", role_cap_rows)
    cko.write_md(OUT / "codex_readout.md", build_readout(matrix, cache.audit_rows, seconds, smoke))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds, "smoke": smoke, "micro_smoke": args.micro_smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--micro-smoke", action="store_true", help="local code-path check with capped role rows")
    parser.add_argument("--micro-role-cap", type=int, default=512)
    parser.add_argument("--micro-source-cap", type=int, default=48)
    parser.add_argument("--role-cap", type=int, default=None, help="cap rows per role phase while preserving complete-past flow state")
    parser.add_argument("--source-cap", type=int, default=24, help="cap rows per source within each role phase when --role-cap is used")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
