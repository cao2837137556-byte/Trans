"""issue27cky: interaction/causal frontend v1.

This route is a deeper frontend redesign after issue27ckx showed the right
evidence-routing idea but too-weak attack-mechanism evidence.

The core contract is deliberately stricter than naive feature concatenation:

* hard attack evidence must come from interaction/causal mechanism features:
  fanout WITH failed handshakes, weak reverse response, sustained pressure, or
  protocol-state mismatch.
* raw115 summaries, pure rate/burst, pure fanout, and size/style features are
  conflict/context evidence only.  They may suppress or trigger review, but may
  not directly produce hard attack.

This is a local medium smoke.  It tests whether a more goal-aligned frontend
reduces OOD/attack entanglement without hiding failure in review.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
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
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402


ISSUE = "issue27cky_interaction_causal_frontend_v1_2026-07-03"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = "iotsim-stream-consumer,iotsim-hydraulic-system"
BENIGN_SAFE_Q = 0.99


@dataclass(frozen=True)
class DecisionPolicy:
    name: str
    support_review_budget: float
    description: str


@dataclass(frozen=True)
class Candidate:
    name: str
    architecture: str
    attack_model: str
    conflict_model: str
    description: str


POLICIES = [
    DecisionPolicy(
        name="P0_no_review_margin0",
        support_review_budget=0.0,
        description="No budgeted review: hard only when attack score beats conflict score.",
    ),
    DecisionPolicy(
        name="P1_support_review_1pp",
        support_review_budget=0.01,
        description="Allow at most about 1pp support attack low-margin review.",
    ),
    DecisionPolicy(
        name="P2_support_review_2pp",
        support_review_budget=0.02,
        description="Allow at most about 2pp support attack low-margin review.",
    ),
]


CANDIDATES = [
    Candidate(
        name="Y1_interaction_causal_router",
        architecture="routed_binary_interaction_causal",
        attack_model="histgb_shallow",
        conflict_model="histgb_shallow",
        description="Mechanism-only attack head plus OOD-vs-attack conflict head.",
    ),
    Candidate(
        name="Y2_interaction_causal_router_stronger",
        architecture="routed_binary_interaction_causal",
        attack_model="histgb_stronger",
        conflict_model="histgb_stronger",
        description="Same evidence contract as Y1, but stronger tree capacity.",
    ),
    Candidate(
        name="Y0_full_interaction_multiclass_control",
        architecture="full_interaction_multiclass_control",
        attack_model="histgb_stronger",
        conflict_model="",
        description="Full evidence direct four-class control; not the preferred deployment route.",
    ),
]


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def fcol(flow: np.ndarray, name: str) -> np.ndarray:
    try:
        idx = ckq.FLOW_TEMPORAL_FEATURES.index(name)
    except ValueError:
        return np.zeros(len(flow), dtype=np.float32)
    return flow[:, idx].astype(np.float32)


def max_named(flow: np.ndarray, names: list[str]) -> np.ndarray:
    cols = [fcol(flow, name) for name in names]
    if not cols:
        return np.zeros(len(flow), dtype=np.float32)
    return np.maximum.reduce(cols).astype(np.float32)


def mean_named(flow: np.ndarray, names: list[str]) -> np.ndarray:
    cols = [fcol(flow, name) for name in names]
    if not cols:
        return np.zeros(len(flow), dtype=np.float32)
    return np.mean(np.vstack(cols), axis=0).astype(np.float32)


def relu(x: np.ndarray) -> np.ndarray:
    return np.maximum(np.asarray(x, dtype=np.float32), 0.0)


def clipped(x: np.ndarray, hi: float = 8.0) -> np.ndarray:
    return np.clip(np.asarray(x, dtype=np.float32), 0.0, hi).astype(np.float32)


def safe_product(*parts: np.ndarray) -> np.ndarray:
    if not parts:
        return np.asarray([], dtype=np.float32)
    out = clipped(parts[0])
    for part in parts[1:]:
        out = out * clipped(part)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


class InteractionCausalFrontend:
    """Strictly aligned interaction/causal evidence frontend.

    The builder supplies raw115 and ckq flow-temporal rows by the same
    role/index positions.  This class only derives deterministic summaries from
    those aligned arrays; it never reindexes rows independently.
    """

    def __init__(self, builder: ckq.FlowTemporalBuilder):
        self.builder = builder
        self._registry: list[dict[str, Any]] | None = None

    def raw_summary(self, raw: np.ndarray) -> tuple[np.ndarray, list[str], list[str]]:
        raw = np.asarray(raw, dtype=np.float32)
        if len(raw) == 0:
            values = np.zeros((0, 10), dtype=np.float32)
        else:
            values = np.column_stack(
                [
                    np.mean(raw, axis=1),
                    np.std(raw, axis=1),
                    np.max(raw, axis=1),
                    np.min(raw, axis=1),
                    np.linalg.norm(raw, axis=1) / math.sqrt(max(1, raw.shape[1])),
                    np.quantile(raw, 0.50, axis=1),
                    np.quantile(raw, 0.75, axis=1),
                    np.quantile(raw, 0.90, axis=1),
                    np.quantile(raw, 0.99, axis=1),
                    np.mean(np.abs(raw), axis=1),
                ]
            ).astype(np.float32)
        names = [
            "raw_mean",
            "raw_std",
            "raw_max",
            "raw_min",
            "raw_norm",
            "raw_q50",
            "raw_q75",
            "raw_q90",
            "raw_q99",
            "raw_abs_mean",
        ]
        groups = ["conflict_context"] * len(names)
        return values, names, groups

    def evidence_from_arrays(self, raw: np.ndarray, flow: np.ndarray) -> tuple[np.ndarray, list[str], list[str]]:
        flow = np.asarray(flow, dtype=np.float32)

        # Current packet/protocol state.  These are useful, but only become
        # direct attack evidence when paired with interaction/temporal context.
        cur_tcp = fcol(flow, "cur_is_tcp")
        cur_udp = fcol(flow, "cur_is_udp")
        cur_icmp = fcol(flow, "cur_is_icmp")
        cur_dns = fcol(flow, "cur_is_dns")
        cur_coap = fcol(flow, "cur_is_coap")
        cur_http = fcol(flow, "cur_is_http")
        cur_tls = fcol(flow, "cur_is_tls")
        cur_well_known = fcol(flow, "cur_dst_well_known")
        cur_syn = fcol(flow, "cur_tcp_syn")
        cur_ack = fcol(flow, "cur_tcp_ack")
        cur_rst = fcol(flow, "cur_tcp_rst")
        cur_fin = fcol(flow, "cur_tcp_fin")
        cur_syn_wo_ack = fcol(flow, "cur_syn_without_ack")
        cur_ack_wo_syn = fcol(flow, "cur_ack_without_syn")
        cur_len = fcol(flow, "cur_log_frame_len")
        cur_ttl = fcol(flow, "cur_ttl_norm")
        cur_window = fcol(flow, "cur_tcp_window_log")

        # Interaction topology, separated by scale so the model can distinguish
        # one-off fanout from sustained fanout.
        src_fanout_w8 = max_named(flow, ["prior_src_w8_unique_dst_frac", "prior_src_w8_unique_dport_frac"])
        src_fanout_w32 = max_named(flow, ["prior_src_w32_unique_dst_frac", "prior_src_w32_unique_dport_frac"])
        src_fanout_w128 = max_named(flow, ["prior_src_w128_unique_dst_frac", "prior_src_w128_unique_dport_frac"])
        file_fanout_w8 = max_named(
            flow,
            ["prior_file_w8_unique_src_frac", "prior_file_w8_unique_dst_frac", "prior_file_w8_unique_dport_frac"],
        )
        file_fanout_w32 = max_named(
            flow,
            ["prior_file_w32_unique_src_frac", "prior_file_w32_unique_dst_frac", "prior_file_w32_unique_dport_frac"],
        )
        file_fanout_w128 = max_named(
            flow,
            ["prior_file_w128_unique_src_frac", "prior_file_w128_unique_dst_frac", "prior_file_w128_unique_dport_frac"],
        )
        dst_pressure_w8 = max_named(flow, ["prior_dst_w8_unique_src_frac", "prior_dst_w8_unique_sport_frac"])
        dst_pressure_w32 = max_named(flow, ["prior_dst_w32_unique_src_frac", "prior_dst_w32_unique_sport_frac"])
        dst_pressure_w128 = max_named(flow, ["prior_dst_w128_unique_src_frac", "prior_dst_w128_unique_sport_frac"])
        pair_spread = max_named(
            flow,
            [
                "prior_pair_w8_unique_sport_frac",
                "prior_pair_w8_unique_dport_frac",
                "prior_pair_w32_unique_sport_frac",
                "prior_pair_w32_unique_dport_frac",
                "prior_pair_w128_unique_sport_frac",
                "prior_pair_w128_unique_dport_frac",
            ],
        )
        src_fanout_accel = fcol(flow, "src_dport_fanout_short_long_ratio_w8_128")
        dst_pressure_accel = fcol(flow, "dst_src_pressure_short_long_ratio_w8_128")
        src_count_accel = fcol(flow, "src_count_short_long_ratio_w8_128")
        pair_count_accel = fcol(flow, "pair_count_short_long_ratio_w8_128")
        flow5_count_accel = fcol(flow, "flow5_count_short_long_ratio_w8_128")

        # Temporal pressure and response/reciprocity.
        src_rate_short = max_named(flow, ["prior_src_w8_event_rate_log", "prior_src_w8_byte_rate_log"])
        src_rate_mid = max_named(flow, ["prior_src_w32_event_rate_log", "prior_src_w32_byte_rate_log"])
        src_rate_long = max_named(flow, ["prior_src_w128_event_rate_log", "prior_src_w128_byte_rate_log"])
        file_rate_short = max_named(flow, ["prior_file_w8_event_rate_log", "prior_file_w8_byte_rate_log"])
        file_rate_mid = max_named(flow, ["prior_file_w32_event_rate_log", "prior_file_w32_byte_rate_log"])
        file_rate_long = max_named(flow, ["prior_file_w128_event_rate_log", "prior_file_w128_byte_rate_log"])
        pair_rate = max_named(flow, ["prior_pair_w8_event_rate_log", "prior_pair_w32_event_rate_log", "prior_pair_w128_event_rate_log"])
        burst_accel = max_named(flow, ["src_count_short_long_ratio_w8_128", "pair_count_short_long_ratio_w8_128", "flow5_count_short_long_ratio_w8_128"])
        rate_pressure = np.maximum.reduce([src_rate_short, src_rate_mid, file_rate_short, burst_accel]).astype(np.float32)
        sustained_rate = np.maximum.reduce([src_rate_long, file_rate_long, pair_rate]).astype(np.float32)

        syn_rate_src = max_named(flow, ["prior_src_w8_syn_rate", "prior_src_w32_syn_rate", "prior_src_w128_syn_rate"])
        ack_rate_src = max_named(flow, ["prior_src_w8_ack_rate", "prior_src_w32_ack_rate", "prior_src_w128_ack_rate"])
        rst_rate_src = max_named(flow, ["prior_src_w8_rst_rate", "prior_src_w32_rst_rate", "prior_src_w128_rst_rate"])
        syn_rate_pair = max_named(flow, ["prior_pair_w8_syn_rate", "prior_pair_w32_syn_rate", "prior_pair_w128_syn_rate"])
        ack_rate_pair = max_named(flow, ["prior_pair_w8_ack_rate", "prior_pair_w32_ack_rate", "prior_pair_w128_ack_rate"])
        rst_rate_pair = max_named(flow, ["prior_pair_w8_rst_rate", "prior_pair_w32_rst_rate", "prior_pair_w128_rst_rate"])
        failed_src = np.maximum.reduce([cur_syn_wo_ack, relu(syn_rate_src - ack_rate_src), rst_rate_src]).astype(np.float32)
        failed_pair = np.maximum.reduce([cur_syn_wo_ack, relu(syn_rate_pair - ack_rate_pair), rst_rate_pair]).astype(np.float32)
        failed_any = np.maximum(failed_src, failed_pair).astype(np.float32)

        reverse_seen = max_named(flow, ["prior_pair_reverse_seen_w8", "prior_pair_reverse_seen_w32", "prior_pair_reverse_seen_w128"])
        reverse_count = max_named(
            flow,
            ["prior_pair_reverse_count_frac_w8", "prior_pair_reverse_count_frac_w32", "prior_pair_reverse_count_frac_w128"],
        )
        reverse_byte_rate = max_named(
            flow,
            [
                "prior_pair_reverse_byte_rate_log_w8",
                "prior_pair_reverse_byte_rate_log_w32",
                "prior_pair_reverse_byte_rate_log_w128",
            ],
        )
        reverse_deficit = relu(1.0 - np.maximum(reverse_seen, reverse_count))
        fwd_rev_count_balance = mean_named(
            flow,
            [
                "prior_pair_forward_reverse_count_balance_w8",
                "prior_pair_forward_reverse_count_balance_w32",
                "prior_pair_forward_reverse_count_balance_w128",
            ],
        )
        fwd_rev_byte_balance = mean_named(
            flow,
            [
                "prior_pair_forward_reverse_byte_balance_w8",
                "prior_pair_forward_reverse_byte_balance_w32",
                "prior_pair_forward_reverse_byte_balance_w128",
            ],
        )
        positive_forward_imbalance = relu(np.maximum(fwd_rev_count_balance, fwd_rev_byte_balance))
        reverse_imbalance_abs = np.abs(np.maximum(fwd_rev_count_balance, fwd_rev_byte_balance)).astype(np.float32)

        # Pure mechanisms are conjunctive.  These are the only channels fed to
        # the direct attack head.
        fast_scan_no_response = safe_product(src_fanout_w8, reverse_deficit)
        mid_scan_no_response = safe_product(src_fanout_w32, reverse_deficit)
        sustained_scan_no_response = safe_product(src_fanout_w128, reverse_deficit)
        fast_scan_failed = safe_product(src_fanout_w8, failed_any)
        sustained_scan_failed = safe_product(src_fanout_w128, failed_any)
        dst_pressure_failed = safe_product(dst_pressure_w8, failed_any)
        pair_spread_failed = safe_product(pair_spread, failed_pair)
        flood_no_response = safe_product(rate_pressure, reverse_deficit)
        flood_failed = safe_product(rate_pressure, failed_any)
        sustained_flood_imbalance = safe_product(sustained_rate, positive_forward_imbalance)
        fanout_accel_failure = safe_product(src_fanout_accel, failed_any)
        dst_pressure_accel_failure = safe_product(dst_pressure_accel, failed_any)
        burst_fanout = safe_product(burst_accel, np.maximum(src_fanout_w8, file_fanout_w8))
        burst_fanout_no_response = safe_product(burst_fanout, reverse_deficit)
        tcp_syn_scan = safe_product(cur_tcp, np.maximum(cur_syn_wo_ack, cur_syn), np.maximum(src_fanout_w8, src_fanout_accel))
        tcp_rst_spread = safe_product(cur_tcp, np.maximum(cur_rst, rst_rate_src), np.maximum(src_fanout_w8, pair_spread))
        udp_fanout_burst = safe_product(cur_udp, np.maximum(cur_dns, cur_coap), np.maximum(src_fanout_w8, src_fanout_accel), rate_pressure)
        service_spread_failure = safe_product(np.maximum(cur_well_known, np.maximum(cur_dns, np.maximum(cur_coap, cur_http))), src_fanout_w8, failed_any)
        many_to_one_pressure = safe_product(dst_pressure_w8, rate_pressure, positive_forward_imbalance)
        protocol_state_mismatch = np.maximum.reduce([cur_syn_wo_ack, cur_ack_wo_syn, cur_rst, relu(syn_rate_src - ack_rate_src)]).astype(np.float32)
        mechanism_consensus = np.maximum.reduce(
            [
                fast_scan_no_response,
                fast_scan_failed,
                flood_no_response,
                flood_failed,
                sustained_flood_imbalance,
                burst_fanout_no_response,
            ]
        ).astype(np.float32)

        attack_values = np.column_stack(
            [
                fast_scan_no_response,
                mid_scan_no_response,
                sustained_scan_no_response,
                fast_scan_failed,
                sustained_scan_failed,
                dst_pressure_failed,
                pair_spread_failed,
                flood_no_response,
                flood_failed,
                sustained_flood_imbalance,
                fanout_accel_failure,
                dst_pressure_accel_failure,
                burst_fanout,
                burst_fanout_no_response,
                tcp_syn_scan,
                tcp_rst_spread,
                udp_fanout_burst,
                service_spread_failure,
                many_to_one_pressure,
                protocol_state_mismatch,
                mechanism_consensus,
            ]
        ).astype(np.float32)
        attack_names = [
            "fast_scan_no_response",
            "mid_scan_no_response",
            "sustained_scan_no_response",
            "fast_scan_failed",
            "sustained_scan_failed",
            "dst_pressure_failed",
            "pair_spread_failed",
            "flood_no_response",
            "flood_failed",
            "sustained_flood_imbalance",
            "fanout_accel_failure",
            "dst_pressure_accel_failure",
            "burst_fanout",
            "burst_fanout_no_response",
            "tcp_syn_scan",
            "tcp_rst_spread",
            "udp_fanout_burst",
            "service_spread_failure",
            "many_to_one_pressure",
            "protocol_state_mismatch",
            "mechanism_consensus",
        ]
        attack_groups = ["attack_mechanism"] * len(attack_names)

        context_values = np.column_stack(
            [
                cur_tcp,
                cur_udp,
                cur_icmp,
                cur_dns,
                cur_coap,
                cur_http,
                cur_tls,
                cur_well_known,
                cur_syn,
                cur_ack,
                cur_rst,
                cur_fin,
                cur_syn_wo_ack,
                cur_ack_wo_syn,
                cur_len,
                cur_ttl,
                cur_window,
                src_fanout_w8,
                src_fanout_w32,
                src_fanout_w128,
                file_fanout_w8,
                file_fanout_w32,
                file_fanout_w128,
                dst_pressure_w8,
                dst_pressure_w32,
                dst_pressure_w128,
                pair_spread,
                src_fanout_accel,
                dst_pressure_accel,
                src_count_accel,
                pair_count_accel,
                flow5_count_accel,
                src_rate_short,
                src_rate_mid,
                src_rate_long,
                file_rate_short,
                file_rate_mid,
                file_rate_long,
                pair_rate,
                burst_accel,
                rate_pressure,
                sustained_rate,
                syn_rate_src,
                ack_rate_src,
                rst_rate_src,
                syn_rate_pair,
                ack_rate_pair,
                rst_rate_pair,
                failed_src,
                failed_pair,
                reverse_seen,
                reverse_count,
                reverse_byte_rate,
                reverse_deficit,
                positive_forward_imbalance,
                reverse_imbalance_abs,
            ]
        ).astype(np.float32)
        context_names = [
            "ctx_cur_tcp",
            "ctx_cur_udp",
            "ctx_cur_icmp",
            "ctx_cur_dns",
            "ctx_cur_coap",
            "ctx_cur_http",
            "ctx_cur_tls",
            "ctx_cur_well_known",
            "ctx_cur_syn",
            "ctx_cur_ack",
            "ctx_cur_rst",
            "ctx_cur_fin",
            "ctx_cur_syn_without_ack",
            "ctx_cur_ack_without_syn",
            "ctx_cur_len",
            "ctx_cur_ttl",
            "ctx_cur_tcp_window",
            "ctx_src_fanout_w8",
            "ctx_src_fanout_w32",
            "ctx_src_fanout_w128",
            "ctx_file_fanout_w8",
            "ctx_file_fanout_w32",
            "ctx_file_fanout_w128",
            "ctx_dst_pressure_w8",
            "ctx_dst_pressure_w32",
            "ctx_dst_pressure_w128",
            "ctx_pair_spread",
            "ctx_src_fanout_accel",
            "ctx_dst_pressure_accel",
            "ctx_src_count_accel",
            "ctx_pair_count_accel",
            "ctx_flow5_count_accel",
            "ctx_src_rate_short",
            "ctx_src_rate_mid",
            "ctx_src_rate_long",
            "ctx_file_rate_short",
            "ctx_file_rate_mid",
            "ctx_file_rate_long",
            "ctx_pair_rate",
            "ctx_burst_accel",
            "ctx_rate_pressure",
            "ctx_sustained_rate",
            "ctx_syn_rate_src",
            "ctx_ack_rate_src",
            "ctx_rst_rate_src",
            "ctx_syn_rate_pair",
            "ctx_ack_rate_pair",
            "ctx_rst_rate_pair",
            "ctx_failed_src",
            "ctx_failed_pair",
            "ctx_reverse_seen",
            "ctx_reverse_count",
            "ctx_reverse_byte_rate",
            "ctx_reverse_deficit",
            "ctx_positive_forward_imbalance",
            "ctx_reverse_imbalance_abs",
        ]
        context_groups = ["conflict_context"] * len(context_names)

        raw_values, raw_names, raw_groups = self.raw_summary(raw)
        values = np.hstack([attack_values, context_values, raw_values]).astype(np.float32)
        names = attack_names + context_names + raw_names
        groups = attack_groups + context_groups + raw_groups
        values = np.nan_to_num(values, nan=0.0, posinf=0.0, neginf=0.0)
        return values, names, groups

    def matrix(self, role: str, idx: np.ndarray, block: str = "full") -> np.ndarray:
        raw = np.asarray(self.builder.matrix(ckq.RAW_BLOCK, role, idx), dtype=np.float32)
        flow = np.asarray(self.builder.matrix(ckq.FLOW_BLOCK, role, idx), dtype=np.float32)
        values, names, groups = self.evidence_from_arrays(raw, flow)
        if self._registry is None:
            self._registry = [
                {
                    "feature_index": i,
                    "feature_name": name,
                    "evidence_group": group,
                    "hard_attack_allowed": group == "attack_mechanism",
                    "frontend_contract": (
                        "conjunctive_interaction_or_causal_mechanism_can_support_hard_attack"
                        if group == "attack_mechanism"
                        else "context_conflict_only_not_direct_hard_attack"
                    ),
                }
                for i, (name, group) in enumerate(zip(names, groups))
            ]
        if block == "full":
            return values
        mask = np.asarray([group == block for group in groups], dtype=bool)
        return values[:, mask]

    def registry(self) -> list[dict[str, Any]]:
        if self._registry is None:
            _ = self.matrix("support_train", np.asarray([0], dtype=np.int64), "full")
        return list(self._registry or [])


def role_indices(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> np.ndarray:
    return ckt.cks.role_indices_filtered(frame_by_role, role, phase, cap, include=include, exclude=exclude)


def candidate_by_name(name: str) -> Candidate:
    for candidate in CANDIDATES:
        if candidate.name == name:
            return candidate
    raise ValueError(name)


def fit_router(
    candidate: Candidate,
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attack_xs: list[np.ndarray] = []
    attack_ys: list[np.ndarray] = []
    conflict_xs: list[np.ndarray] = []
    conflict_ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add_attack(role: str, phase: str, is_attack: int, cap: int) -> np.ndarray:
        idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
        attack_xs.append(frontend.matrix(role, idx, "attack_mechanism"))
        attack_ys.append(np.full(len(idx), is_attack, dtype=np.int8))
        audit.append(
            {
                "candidate": candidate.name,
                "role": role,
                "phase": phase,
                "rows": len(idx),
                "is_attack": is_attack,
                "head": "attack_mechanism",
                "model": candidate.attack_model,
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
            }
        )
        return idx

    support_idx = add_attack("support_train", "fit", 1, cko.FULL_CAP)
    add_attack("id_calib", "fit", 0, train_cap)
    ood_idx = add_attack("ood_val", "fit", 0, train_cap)
    hard_ood_idx = add_attack("ood_stress", "fit", 0, train_cap)

    conflict_xs.append(frontend.matrix("support_train", support_idx, "conflict_context"))
    conflict_ys.append(np.zeros(len(support_idx), dtype=np.int8))
    conflict_xs.append(frontend.matrix("ood_val", ood_idx, "conflict_context"))
    conflict_ys.append(np.ones(len(ood_idx), dtype=np.int8))
    conflict_xs.append(frontend.matrix("ood_stress", hard_ood_idx, "conflict_context"))
    conflict_ys.append(np.ones(len(hard_ood_idx), dtype=np.int8))
    audit.append(
        {
            "candidate": candidate.name,
            "role": "support_train+ood_val+ood_stress",
            "phase": "fit",
            "rows": int(len(support_idx) + len(ood_idx) + len(hard_ood_idx)),
            "is_attack": "",
            "head": "ood_vs_attack_conflict_context",
            "model": candidate.conflict_model,
            "exclude_field": exclude[0] if exclude else "",
            "exclude_value": exclude[1] if exclude else "",
        }
    )
    attack_model = ckh.balanced_fit(ckh.build_model(candidate.attack_model), np.vstack(attack_xs), np.concatenate(attack_ys))
    conflict_model = ckh.balanced_fit(ckh.build_model(candidate.conflict_model), np.vstack(conflict_xs), np.concatenate(conflict_ys))
    return {
        "candidate_name": candidate.name,
        "architecture": candidate.architecture,
        "attack_model": attack_model,
        "conflict_model": conflict_model,
    }, audit


def fit_multiclass_control(
    candidate: Candidate,
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = role_indices(frame_by_role, role, phase, cap, exclude=exclude)
        xs.append(frontend.matrix(role, idx, "full"))
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "candidate": candidate.name,
                "role": role,
                "phase": phase,
                "rows": len(idx),
                "label": label,
                "label_name": ckq.CLASS_NAMES.get(label, str(label)),
                "head": "full_interaction_multiclass_control",
                "model": candidate.attack_model,
                "exclude_field": exclude[0] if exclude else "",
                "exclude_value": exclude[1] if exclude else "",
            }
        )

    add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    model = ckh.balanced_fit(ckh.build_model(candidate.attack_model, multiclass=True), np.vstack(xs), np.concatenate(ys))
    return {"candidate_name": candidate.name, "architecture": candidate.architecture, "model": model}, audit


def fit_candidate(
    name: str,
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidate = candidate_by_name(name)
    if candidate.architecture == "routed_binary_interaction_causal":
        return fit_router(candidate, frontend, frame_by_role, train_cap, exclude=exclude)
    if candidate.architecture == "full_interaction_multiclass_control":
        return fit_multiclass_control(candidate, frontend, frame_by_role, train_cap, exclude=exclude)
    raise ValueError(candidate.architecture)


def scores(fitted: dict[str, Any], frontend: InteractionCausalFrontend, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    if len(idx) == 0:
        empty = np.asarray([], dtype=np.float64)
        return {
            "attack_score": empty,
            "conflict_score": empty,
            "hard_ood_score": empty,
            "margin_score": empty,
        }
    arch = fitted["architecture"]
    if arch == "routed_binary_interaction_causal":
        attack_x = frontend.matrix(role, idx, "attack_mechanism")
        conflict_x = frontend.matrix(role, idx, "conflict_context")
        attack = ckh.positive_score(fitted["attack_model"], attack_x, 1)
        conflict = ckh.positive_score(fitted["conflict_model"], conflict_x, 1)
        return {
            "attack_score": attack,
            "conflict_score": conflict,
            "hard_ood_score": np.zeros(len(idx), dtype=np.float64),
            "margin_score": attack - conflict,
        }
    if arch == "full_interaction_multiclass_control":
        x = frontend.matrix(role, idx, "full")
        model = fitted["model"]
        attack = ckh.class_score(model, x, ckh.CLASS_ATTACK)
        hard_ood = ckh.class_score(model, x, ckh.CLASS_HARD_OOD)
        ood = ckh.class_score(model, x, ckh.CLASS_OOD)
        identity = ckh.class_score(model, x, ckh.CLASS_ID)
        conflict = np.maximum.reduce([identity, ood, hard_ood])
        return {
            "attack_score": attack,
            "conflict_score": conflict,
            "hard_ood_score": hard_ood,
            "margin_score": attack - conflict,
        }
    raise ValueError(arch)


def attack_threshold(
    fitted: dict[str, Any],
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    benign_q: float,
    exclude: tuple[str, str] | None = None,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices(frame_by_role, role, "select", eval_cap, exclude=exclude)
        if len(idx):
            parts.append(scores(fitted, frontend, role, idx)["attack_score"])
    if not parts:
        return 1.0
    return float(max(np.quantile(part, benign_q) for part in parts if len(part)))


def policy_thresholds(
    fitted: dict[str, Any],
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
    attack_thr: float,
    policy: DecisionPolicy,
    exclude: tuple[str, str] | None = None,
) -> dict[str, Any]:
    idx = role_indices(frame_by_role, "support_val", "select", eval_cap, exclude=exclude)
    score = scores(fitted, frontend, "support_val", idx)
    raw = score["attack_score"] > attack_thr
    margins = score["margin_score"][raw]
    if policy.support_review_budget <= 0.0 or len(margins) == 0:
        margin_thr = 0.0
    else:
        margin_thr = max(0.0, float(np.quantile(margins, policy.support_review_budget)))
    suppress = raw & (score["margin_score"] <= 0.0)
    review = raw & (score["margin_score"] > 0.0) & (score["margin_score"] <= margin_thr)
    hard = raw & (~suppress) & (~review)
    return {
        "policy": policy.name,
        "support_review_budget": policy.support_review_budget,
        "attack_threshold": attack_thr,
        "margin_review_threshold": margin_thr,
        "support_rows": len(idx),
        "support_raw_alarm_rate": ckg.rate(raw),
        "support_hard_rate": ckg.rate(hard),
        "support_review_rate": ckg.rate(review),
        "support_suppress_rate": ckg.rate(suppress),
        "exclude_field": exclude[0] if exclude else "",
        "exclude_value": exclude[1] if exclude else "",
    }


def decide(score: dict[str, np.ndarray], threshold_row: dict[str, Any]) -> dict[str, np.ndarray]:
    raw = score["attack_score"] > float(threshold_row["attack_threshold"])
    margin = score["margin_score"]
    suppress = raw & (margin <= 0.0)
    review = raw & (margin > 0.0) & (margin <= float(threshold_row["margin_review_threshold"]))
    hard = raw & (~suppress) & (~review)
    return {"raw_alarm": raw, "hard_alarm": hard, "review": review, "suppress": suppress}


def eval_role(
    fitted: dict[str, Any],
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    role_kind: str,
    eval_cap: int,
    threshold_row: dict[str, Any],
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, eval_cap, include=include, exclude=exclude)
    score = scores(fitted, frontend, role, idx)
    decision = decide(score, threshold_row)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    for key, value in score.items():
        part[key] = value
    for key, value in decision.items():
        part[key] = value
    row = {
        "candidate": fitted.get("candidate_name", fitted["architecture"]),
        "policy": threshold_row["policy"],
        "split": split,
        "held_field": include[0] if include else "",
        "held_value": include[1] if include else "",
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(idx),
        "attack_threshold": threshold_row["attack_threshold"],
        "margin_review_threshold": threshold_row["margin_review_threshold"],
        "raw_alarm_rate": ckg.rate(decision["raw_alarm"]),
        "hard_alarm_rate": ckg.rate(decision["hard_alarm"]),
        "review_rate": ckg.rate(decision["review"]),
        "suppress_rate": ckg.rate(decision["suppress"]),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(idx) else float("nan"),
        "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(idx) else float("nan"),
        "margin_score_mean": float(np.mean(score["margin_score"])) if len(idx) else float("nan"),
    }
    return row, part


def eval_candidate(
    name: str,
    frontend: InteractionCausalFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
    eval_cap: int,
    benign_q: float,
    split: str,
    include: tuple[str, str] | None = None,
    exclude: tuple[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    fitted, train_rows = fit_candidate(name, frontend, frame_by_role, train_cap, exclude=exclude)
    attack_thr = attack_threshold(fitted, frontend, frame_by_role, eval_cap, benign_q, exclude=exclude)
    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    for policy in POLICIES:
        thr = policy_thresholds(fitted, frontend, frame_by_role, eval_cap, attack_thr, policy, exclude=exclude)
        thr["candidate"] = name
        thr["split"] = split
        thr["held_field"] = include[0] if include else ""
        thr["held_value"] = include[1] if include else ""
        threshold_rows.append(thr)
        for role, phase, kind in cko.ROLE_EVAL:
            # Leave-family stress means: fit/threshold exclude the held family,
            # while evaluation includes only that held family wherever the role
            # has such rows.  Query/future/sealed remain report-only; including
            # them here does not feed them back into fitting.
            role_include = include if split == "leave_device_family" else None
            role_exclude = None
            row, _part = eval_role(
                fitted,
                frontend,
                frame_by_role,
                role,
                phase,
                kind,
                eval_cap,
                thr,
                split=split,
                include=role_include,
                exclude=role_exclude,
            )
            row["candidate"] = name
            role_rows.append(row)
    return role_rows, threshold_rows, train_rows


def pick(rows: list[dict[str, Any]], split: str, candidate: str, policy: str, role: str, metric: str, held_value: str = "") -> float:
    for row in rows:
        if (
            row["split"] == split
            and row["candidate"] == candidate
            and row["policy"] == policy
            and row["role"] == role
            and str(row.get("held_value", "")) == held_value
        ):
            return float(row.get(metric, float("nan")))
    return float("nan")


def main_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = sorted({(r["candidate"], r["policy"]) for r in role_rows if r["split"] == "main"})
    out = []
    for candidate, policy in keys:
        out.append(
            {
                "candidate": candidate,
                "policy": policy,
                "future_hard": pick(role_rows, "main", candidate, policy, "future_query", "hard_alarm_rate"),
                "future_review": pick(role_rows, "main", candidate, policy, "future_query", "review_rate"),
                "future_suppress": pick(role_rows, "main", candidate, policy, "future_query", "suppress_rate"),
                "sealed_attack_hard": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "hard_alarm_rate"),
                "sealed_attack_review": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "review_rate"),
                "sealed_attack_suppress": pick(role_rows, "main", candidate, policy, "sealed_final_attack", "suppress_rate"),
                "sealed_ood_hard": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "hard_alarm_rate"),
                "sealed_ood_review": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "review_rate"),
                "sealed_ood_suppress": pick(role_rows, "main", candidate, policy, "sealed_final_ood", "suppress_rate"),
                "ood_stress_hard": pick(role_rows, "main", candidate, policy, "ood_stress", "hard_alarm_rate"),
                "ood_stress_review": pick(role_rows, "main", candidate, policy, "ood_stress", "review_rate"),
                "ood_stress_suppress": pick(role_rows, "main", candidate, policy, "ood_stress", "suppress_rate"),
            }
        )
    return out


def leave_summary(role_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for row in role_rows:
        if row["split"] != "leave_device_family" or row["role"] not in {"ood_val", "ood_stress", "sealed_final_ood", "future_query", "sealed_final_attack"}:
            continue
        out.append(
            {
                "candidate": row["candidate"],
                "policy": row["policy"],
                "held_value": row.get("held_value", ""),
                "role": row["role"],
                "rows": row["rows"],
                "raw_alarm_rate": row["raw_alarm_rate"],
                "hard_alarm_rate": row["hard_alarm_rate"],
                "review_rate": row["review_rate"],
                "suppress_rate": row["suppress_rate"],
                "attack_score_mean": row["attack_score_mean"],
                "conflict_score_mean": row["conflict_score_mean"],
                "margin_score_mean": row["margin_score_mean"],
            }
        )
    return out


def build_readout(main_rows: list[dict[str, Any]], leave_rows: list[dict[str, Any]], threshold_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27cky interaction/causal frontend v1",
        "",
        "## Scope",
        "",
        "Local medium-smoke for a stronger problem-aligned frontend.",
        "Hard attack can only come from conjunctive interaction/causal mechanism evidence; raw115 and pure context remain conflict-only.",
        "",
        "## Main roles",
        "",
        "| candidate | policy | future h/r/s | sealed attack h/r/s | sealed OOD h/r/s | OOD-stress h/r/s |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in main_rows:
        lines.append(
            f"| {row['candidate']} | {row['policy']} | "
            f"{cko.fmt(row['future_hard'])}/{cko.fmt(row['future_review'])}/{cko.fmt(row['future_suppress'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])}/{cko.fmt(row['sealed_attack_suppress'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])}/{cko.fmt(row['sealed_ood_suppress'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])}/{cko.fmt(row['ood_stress_suppress'])} |"
        )
    lines.extend(
        [
            "",
            "## Leave-device-family stress",
            "",
            "| candidate | policy | held family | role | rows | raw | hard | review | suppress | attack/conflict/margin mean |",
            "|---|---|---|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in leave_rows:
        if int(row["rows"]) == 0:
            continue
        lines.append(
            f"| {row['candidate']} | {row['policy']} | {row['held_value']} | {row['role']} | {row['rows']} | "
            f"{cko.fmt(row['raw_alarm_rate'])} | {cko.fmt(row['hard_alarm_rate'])} | "
            f"{cko.fmt(row['review_rate'])} | {cko.fmt(row['suppress_rate'])} | "
            f"{cko.fmt(row['attack_score_mean'])}/{cko.fmt(row['conflict_score_mean'])}/{cko.fmt(row['margin_score_mean'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold audit",
            "",
            "| candidate | split | held | policy | attack thr | margin review thr | support hard/review/suppress |",
            "|---|---|---|---|---:|---:|---:|",
        ]
    )
    for row in threshold_rows:
        lines.append(
            f"| {row['candidate']} | {row['split']} | {row.get('held_value','')} | {row['policy']} | "
            f"{cko.fmt(row['attack_threshold'])} | {cko.fmt(row['margin_review_threshold'])} | "
            f"{cko.fmt(row['support_hard_rate'])}/{cko.fmt(row['support_review_rate'])}/{cko.fmt(row['support_suppress_rate'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Fit uses only support_train/id_calib/ood_val/ood_stress fit phases.",
            "- Thresholds use only id_calib/ood_val/ood_stress/support_val select phases.",
            "- Leave-family stress excludes the held device_family from fit and thresholds.",
            "- Query/future/sealed rows are report-only.",
            "- h/r/s = hard/review/suppress.",
            "- This is still Gotham-internal smoke, not cross-dataset proof.",
            f"- Runtime seconds: {cko.fmt(seconds, 1)}.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(True)
    x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
        x_by_role,
        frame_by_role,
        int(args.role_cap),
        int(args.source_cap),
        cap_rule="interaction-causal frontend capped local smoke",
    )
    ckt.add_family_columns(frame_by_role)
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=True, local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = InteractionCausalFrontend(builder)

    candidates = [item.strip() for item in str(args.candidates).split(",") if item.strip()]
    held_values = [item.strip() for item in str(args.held_values).split(",") if item.strip()]

    role_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    selected_rows: list[dict[str, Any]] = []

    for candidate in candidates:
        rows, thrs, trains = eval_candidate(
            candidate,
            frontend,
            frame_by_role,
            int(args.train_cap),
            int(args.eval_cap),
            float(args.benign_q),
            split="main",
        )
        role_rows.extend(rows)
        threshold_rows.extend(thrs)
        train_rows.extend(trains)

    for held_value in held_values:
        counts = {
            "ood_val": ckt.rows_for(frame_by_role, "ood_val", "select", "device_family", held_value, int(args.eval_cap)),
            "ood_stress": ckt.rows_for(frame_by_role, "ood_stress", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_ood": ckt.rows_for(frame_by_role, "sealed_final_ood", "all", "device_family", held_value, int(args.eval_cap)),
            "future_query": ckt.rows_for(frame_by_role, "future_query", "select", "device_family", held_value, int(args.eval_cap)),
            "sealed_final_attack": ckt.rows_for(frame_by_role, "sealed_final_attack", "all", "device_family", held_value, int(args.eval_cap)),
        }
        selected_rows.append({"held_field": "device_family", "held_value": held_value, "total_eval_rows": sum(counts.values()), **counts})
        exclude = ("device_family", held_value)
        include = ("device_family", held_value)
        for candidate in candidates:
            rows, thrs, trains = eval_candidate(
                candidate,
                frontend,
                frame_by_role,
                int(args.train_cap),
                int(args.eval_cap),
                float(args.benign_q),
                split="leave_device_family",
                include=include,
                exclude=exclude,
            )
            role_rows.extend(rows)
            threshold_rows.extend(thrs)
            train_rows.extend({"held_value": held_value, **row} for row in trains)

    main_rows = main_summary(role_rows)
    leave_rows = leave_summary(role_rows)
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started
    cko.write_csv(out / "main_summary_matrix.csv", main_rows)
    cko.write_csv(out / "leave_device_family_summary_matrix.csv", leave_rows)
    cko.write_csv(out / "role_metrics.csv", role_rows)
    cko.write_csv(out / "threshold_policy_audit.csv", threshold_rows)
    cko.write_csv(out / "train_audit.csv", train_rows)
    cko.write_csv(out / "evidence_feature_registry.csv", frontend.registry())
    cko.write_csv(out / "selected_leave_groups.csv", selected_rows)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_md(out / "codex_readout.md", build_readout(main_rows, leave_rows, threshold_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "scope": "interaction/causal frontend smoke with evidence routing",
            "role_cap": args.role_cap,
            "source_cap": args.source_cap,
            "train_cap": args.train_cap,
            "eval_cap": args.eval_cap,
            "benign_q": args.benign_q,
            "candidates": [asdict(candidate_by_name(name)) for name in candidates],
            "policies": [asdict(policy) for policy in POLICIES],
            "held_values": held_values,
            "data_use_boundary": {
                "fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select", "support_val select"],
                "leave_family_exclusion": "held device_family excluded from fit and thresholds",
                "report_only_roles_used_for_training_or_thresholding": False,
            },
            "frontend_contract": {
                "attack_mechanism": "conjunctive interaction/causal features only",
                "conflict_context": "raw115 summaries, pure rate/fanout/volume/style context; cannot directly produce hard attack",
                "processed_label_used_as_feature": False,
                "source_or_device_used_as_inference_feature": False,
            },
            "input_audit": input_audit,
            "selected_leave_groups": selected_rows,
            "alignment_audit_rows": len(alignment_rows),
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-cap", type=int, default=1536)
    parser.add_argument("--source-cap", type=int, default=48)
    parser.add_argument("--train-cap", type=int, default=768)
    parser.add_argument("--eval-cap", type=int, default=1536)
    parser.add_argument("--benign-q", type=float, default=BENIGN_SAFE_Q)
    parser.add_argument(
        "--candidates",
        default="Y1_interaction_causal_router,Y2_interaction_causal_router_stronger,Y0_full_interaction_multiclass_control",
    )
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
