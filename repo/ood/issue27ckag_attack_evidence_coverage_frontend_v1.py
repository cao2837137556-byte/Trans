"""issue27ckag: attack evidence coverage frontend v1.

CKAF failed in an important, scientifically useful way: selected attack
features were mostly near-duplicates of fanout_accel_failure, so OOD appeared
"quiet" only because the attack branch was barely firing.  This diagnostic
therefore does not tune thresholds or train a larger head.  It builds a wider
attack-mechanism frontend and audits whether the new evidence covers attack
roles while keeping OOD roles quiet.

Contract:

* New attack evidence is built from current/past-only processed CSV state via
  the CKQ aligned flow-temporal builder.
* Raw115 is not allowed into direct hard-attack evidence here.
* Legal feature scoring uses only:
    support_train/id_calib/ood_val/ood_stress fit
    support_val/id_calib/ood_val/ood_stress select
* same_file_query/future_query/sealed roles and held-family slices are
  report-only diagnostics after legal scoring.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckac_frontend_feature_utility_audit_v1 as ckac  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402


ISSUE = "issue27ckag_attack_evidence_coverage_frontend_v1_2026-07-06"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = ckac.DEFAULT_HELD_VALUES


@dataclass(frozen=True)
class DerivedFeature:
    name: str
    group: str
    hard_attack_allowed: bool
    rationale: str


def slug(text: Any, limit: int = 96) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:limit] or "empty"


def finite(value: Any, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def fmt(value: Any, digits: int = 4) -> str:
    val = finite(value)
    if math.isnan(val):
        return "nan"
    return f"{val:.{digits}f}"


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


def safe_product(*parts: np.ndarray, hi: float = 8.0) -> np.ndarray:
    if not parts:
        return np.asarray([], dtype=np.float32)
    out = clipped(parts[0], hi)
    for part in parts[1:]:
        out = out * clipped(part, hi)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0).astype(np.float32)


def safe_ratio(num: np.ndarray, den: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    return np.nan_to_num(np.asarray(num, dtype=np.float32) / (np.asarray(den, dtype=np.float32) + eps), nan=0.0, posinf=0.0, neginf=0.0)


def max_stack(*cols: np.ndarray) -> np.ndarray:
    if not cols:
        return np.asarray([], dtype=np.float32)
    return np.maximum.reduce([np.asarray(col, dtype=np.float32) for col in cols]).astype(np.float32)


def min_stack(*cols: np.ndarray) -> np.ndarray:
    if not cols:
        return np.asarray([], dtype=np.float32)
    return np.minimum.reduce([np.asarray(col, dtype=np.float32) for col in cols]).astype(np.float32)


class AttackEvidenceCoverageFrontend:
    """Derived frontend focused on wider attack-mechanism coverage.

    The class only consumes CKQ builder matrices, so row alignment is inherited
    from the already-audited role/index mapping.  Feature groups starting with
    `attack_` are allowed to support hard attack in later heads; context groups
    are diagnostics or conflict evidence only.
    """

    def __init__(self, builder: ckq.FlowTemporalBuilder):
        self.builder = builder
        self._registry: list[dict[str, Any]] | None = None
        self._cache: dict[tuple[str, str], tuple[np.ndarray, list[str], list[str], list[DerivedFeature]]] = {}

    def evidence_from_flow(self, flow: np.ndarray) -> tuple[np.ndarray, list[str], list[str], list[DerivedFeature]]:
        flow = np.asarray(flow, dtype=np.float32)
        n = len(flow)

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
        cur_dst_port = fcol(flow, "cur_dst_port_log")
        cur_tcp_window = fcol(flow, "cur_tcp_window_log")

        src_dst_frac_w8 = fcol(flow, "prior_src_w8_unique_dst_frac")
        src_dst_frac_w32 = fcol(flow, "prior_src_w32_unique_dst_frac")
        src_dst_frac_w128 = fcol(flow, "prior_src_w128_unique_dst_frac")
        src_dport_frac_w8 = fcol(flow, "prior_src_w8_unique_dport_frac")
        src_dport_frac_w32 = fcol(flow, "prior_src_w32_unique_dport_frac")
        src_dport_frac_w128 = fcol(flow, "prior_src_w128_unique_dport_frac")
        file_src_frac_w8 = fcol(flow, "prior_file_w8_unique_src_frac")
        file_dst_frac_w8 = fcol(flow, "prior_file_w8_unique_dst_frac")
        file_dport_frac_w8 = fcol(flow, "prior_file_w8_unique_dport_frac")
        file_src_frac_w32 = fcol(flow, "prior_file_w32_unique_src_frac")
        file_dst_frac_w32 = fcol(flow, "prior_file_w32_unique_dst_frac")
        file_dport_frac_w32 = fcol(flow, "prior_file_w32_unique_dport_frac")
        dst_src_frac_w8 = fcol(flow, "prior_dst_w8_unique_src_frac")
        dst_src_frac_w32 = fcol(flow, "prior_dst_w32_unique_src_frac")
        dst_src_frac_w128 = fcol(flow, "prior_dst_w128_unique_src_frac")
        dst_sport_frac_w8 = fcol(flow, "prior_dst_w8_unique_sport_frac")
        pair_sport_frac_w8 = fcol(flow, "prior_pair_w8_unique_sport_frac")
        pair_dport_frac_w8 = fcol(flow, "prior_pair_w8_unique_dport_frac")

        src_fanout_w8 = max_stack(src_dst_frac_w8, src_dport_frac_w8)
        src_fanout_w32 = max_stack(src_dst_frac_w32, src_dport_frac_w32)
        src_fanout_w128 = max_stack(src_dst_frac_w128, src_dport_frac_w128)
        src_fanout_persistent = min_stack(src_fanout_w8, src_fanout_w32, src_fanout_w128)
        src_fanout_accel = fcol(flow, "src_dport_fanout_short_long_ratio_w8_128")
        file_fanout_w8 = max_stack(file_src_frac_w8, file_dst_frac_w8, file_dport_frac_w8)
        file_fanout_w32 = max_stack(file_src_frac_w32, file_dst_frac_w32, file_dport_frac_w32)
        dst_pressure_w8 = max_stack(dst_src_frac_w8, dst_sport_frac_w8)
        dst_pressure_w32 = dst_src_frac_w32
        dst_pressure_w128 = dst_src_frac_w128
        dst_pressure_accel = fcol(flow, "dst_src_pressure_short_long_ratio_w8_128")
        pair_spread_w8 = max_stack(pair_sport_frac_w8, pair_dport_frac_w8)

        src_count_w8 = fcol(flow, "prior_src_w8_count_frac")
        src_count_w32 = fcol(flow, "prior_src_w32_count_frac")
        src_count_w128 = fcol(flow, "prior_src_w128_count_frac")
        pair_count_w8 = fcol(flow, "prior_pair_w8_count_frac")
        pair_count_w32 = fcol(flow, "prior_pair_w32_count_frac")
        flow5_count_w8 = fcol(flow, "prior_flow5_w8_count_frac")
        src_count_accel = fcol(flow, "src_count_short_long_ratio_w8_128")
        pair_count_accel = fcol(flow, "pair_count_short_long_ratio_w8_128")
        flow5_count_accel = fcol(flow, "flow5_count_short_long_ratio_w8_128")

        src_event_rate_w8 = fcol(flow, "prior_src_w8_event_rate_log")
        src_event_rate_w32 = fcol(flow, "prior_src_w32_event_rate_log")
        src_event_rate_w128 = fcol(flow, "prior_src_w128_event_rate_log")
        src_byte_rate_w8 = fcol(flow, "prior_src_w8_byte_rate_log")
        file_event_rate_w8 = fcol(flow, "prior_file_w8_event_rate_log")
        file_byte_rate_w8 = fcol(flow, "prior_file_w8_byte_rate_log")
        pair_event_rate_w8 = fcol(flow, "prior_pair_w8_event_rate_log")
        pair_event_rate_w32 = fcol(flow, "prior_pair_w32_event_rate_log")
        flow5_event_rate_w8 = fcol(flow, "prior_flow5_w8_event_rate_log")
        src_rate_w8 = max_stack(src_event_rate_w8, src_byte_rate_w8)
        file_rate_w8 = max_stack(file_event_rate_w8, file_byte_rate_w8)
        pair_rate = max_stack(pair_event_rate_w8, pair_event_rate_w32, flow5_event_rate_w8)
        burst_accel = max_stack(src_count_accel, pair_count_accel, flow5_count_accel)
        sustained_rate = max_stack(src_event_rate_w32, src_event_rate_w128, pair_event_rate_w32)
        src_gap_w8 = fcol(flow, "prior_src_w8_current_gap_log")
        pair_gap_w8 = fcol(flow, "prior_pair_w8_current_gap_log")
        recent_src = relu(1.0 - safe_ratio(src_gap_w8, src_gap_w8 + 1.0))
        recent_pair = relu(1.0 - safe_ratio(pair_gap_w8, pair_gap_w8 + 1.0))

        syn_src = max_named(flow, ["prior_src_w8_syn_rate", "prior_src_w32_syn_rate", "prior_src_w128_syn_rate"])
        ack_src = max_named(flow, ["prior_src_w8_ack_rate", "prior_src_w32_ack_rate", "prior_src_w128_ack_rate"])
        rst_src = max_named(flow, ["prior_src_w8_rst_rate", "prior_src_w32_rst_rate", "prior_src_w128_rst_rate"])
        syn_pair = max_named(flow, ["prior_pair_w8_syn_rate", "prior_pair_w32_syn_rate", "prior_pair_w128_syn_rate"])
        ack_pair = max_named(flow, ["prior_pair_w8_ack_rate", "prior_pair_w32_ack_rate", "prior_pair_w128_ack_rate"])
        rst_pair = max_named(flow, ["prior_pair_w8_rst_rate", "prior_pair_w32_rst_rate", "prior_pair_w128_rst_rate"])
        fin_pair = max_named(flow, ["prior_pair_w8_fin_rate", "prior_pair_w32_fin_rate", "prior_pair_w128_fin_rate"])
        half_open_src = relu(syn_src - ack_src)
        half_open_pair = relu(syn_pair - ack_pair)
        failed_src = max_stack(cur_syn_wo_ack, half_open_src, rst_src)
        failed_pair = max_stack(cur_syn_wo_ack, half_open_pair, rst_pair)
        failed_any = max_stack(failed_src, failed_pair)
        close_mismatch = max_stack(relu(rst_pair - fin_pair), cur_rst, cur_ack_wo_syn)

        rev_seen_w8 = fcol(flow, "prior_pair_reverse_seen_w8")
        rev_seen_w32 = fcol(flow, "prior_pair_reverse_seen_w32")
        rev_seen_w128 = fcol(flow, "prior_pair_reverse_seen_w128")
        rev_count_w8 = fcol(flow, "prior_pair_reverse_count_frac_w8")
        rev_count_w32 = fcol(flow, "prior_pair_reverse_count_frac_w32")
        rev_count_w128 = fcol(flow, "prior_pair_reverse_count_frac_w128")
        rev_byte_rate = max_named(
            flow,
            ["prior_pair_reverse_byte_rate_log_w8", "prior_pair_reverse_byte_rate_log_w32", "prior_pair_reverse_byte_rate_log_w128"],
        )
        reverse_strength = max_stack(rev_seen_w8, rev_seen_w32, rev_seen_w128, rev_count_w8, rev_count_w32, rev_count_w128)
        reverse_deficit_fast = relu(1.0 - max_stack(rev_seen_w8, rev_count_w8))
        reverse_deficit_mid = relu(1.0 - max_stack(rev_seen_w32, rev_count_w32))
        reverse_deficit_long = relu(1.0 - max_stack(rev_seen_w128, rev_count_w128))
        reverse_deficit_persistent = min_stack(reverse_deficit_fast, reverse_deficit_mid, reverse_deficit_long)
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
        forward_imbalance = relu(max_stack(fwd_rev_count_balance, fwd_rev_byte_balance))

        service_any = max_stack(cur_dns, cur_coap, cur_http, cur_tls, cur_well_known)
        nonservice_port = relu(1.0 - service_any)
        udp_service = safe_product(cur_udp, max_stack(cur_dns, cur_coap, cur_well_known))
        tcp_service = safe_product(cur_tcp, max_stack(cur_http, cur_tls, cur_well_known))

        # Residual/context-normalized signals.  These are intended to reduce
        # source/file-style shortcut reliance by asking whether the current
        # source/pair is extreme relative to the surrounding file window.
        src_fanout_residual = relu(src_fanout_w8 - file_fanout_w8)
        src_fanout_residual_mid = relu(src_fanout_w32 - file_fanout_w32)
        src_port_residual = relu(src_dport_frac_w8 - file_dport_frac_w8)
        dst_pressure_residual = relu(dst_pressure_w8 - file_fanout_w8)
        src_rate_residual = relu(src_rate_w8 - file_rate_w8)
        pair_rate_residual = relu(pair_rate - file_rate_w8)

        values_by_name: list[tuple[str, str, np.ndarray, str]] = []

        def add(name: str, group: str, value: np.ndarray, rationale: str) -> None:
            values_by_name.append((name, group, np.asarray(value, dtype=np.float32), rationale))

        # Lifecycle / protocol-state evidence.
        add("tcp_half_open_persistent", "attack_lifecycle", safe_product(cur_tcp, max_stack(half_open_src, half_open_pair), src_count_w32, recent_src), "TCP SYN pressure persists without matching ACKs.")
        add("tcp_syn_fanout_above_file", "attack_lifecycle", safe_product(cur_tcp, max_stack(cur_syn, cur_syn_wo_ack), src_fanout_residual), "SYN-like fanout exceeds file context.")
        add("tcp_rst_after_syn_spread", "attack_lifecycle", safe_product(cur_tcp, max_stack(cur_rst, rst_src, rst_pair), max_stack(src_fanout_w8, pair_spread_w8)), "RST/failed close spread across destinations/ports.")
        add("tcp_ackless_pair_pressure", "attack_lifecycle", safe_product(cur_tcp, half_open_pair, pair_rate, recent_pair), "Pair-level repeated half-open behavior.")
        add("tcp_close_state_mismatch_pressure", "attack_lifecycle", safe_product(cur_tcp, close_mismatch, max_stack(pair_count_w8, pair_rate)), "RST/ACK/FIN state mismatch under repeated pair activity.")

        # Bidirectional response evidence.
        add("oneway_persistent_pair_pressure", "attack_response", safe_product(reverse_deficit_persistent, pair_rate, forward_imbalance), "Persistent one-way pair pressure.")
        add("udp_reverse_deficit_fanout_rate", "attack_response", safe_product(cur_udp, reverse_deficit_fast, src_fanout_w8, src_rate_w8), "UDP fanout and rate without reverse response.")
        add("low_reverse_high_pair_rate", "attack_response", safe_product(relu(1.0 - reverse_strength), pair_rate), "High pair rate with weak reverse evidence.")
        add("forward_byte_imbalance_burst", "attack_response", safe_product(forward_imbalance, burst_accel, src_rate_w8), "Forward-heavy burst behavior.")
        add("response_absent_despite_service", "attack_response", safe_product(service_any, reverse_deficit_fast, max_stack(src_fanout_w8, pair_rate)), "Service-looking traffic without response.")
        add("reverse_byte_deficit_rate", "attack_response", safe_product(relu(src_rate_w8 - rev_byte_rate), reverse_deficit_fast), "Forward rate dominates reverse byte rate.")

        # Temporal persistence / burst evidence.
        add("source_burst_above_file_failure", "attack_temporal", safe_product(src_rate_residual, failed_any), "Source burst exceeds file baseline and has failure evidence.")
        add("flow5_accel_failure", "attack_temporal", safe_product(flow5_count_accel, failed_any), "5-tuple repetition accelerates with failure.")
        add("pair_accel_forward_imbalance", "attack_temporal", safe_product(pair_count_accel, forward_imbalance), "Pair acceleration with forward imbalance.")
        add("persistent_src_pressure_failure", "attack_temporal", safe_product(src_count_w128, sustained_rate, failed_any), "Long-window source pressure remains failed.")
        add("short_burst_not_filewide", "attack_temporal", safe_product(relu(src_rate_w8 - file_rate_w8), relu(src_count_w8 - src_count_w128), failed_any), "Local source burst, not merely whole-file load.")
        add("burst_fanout_response_deficit", "attack_temporal", safe_product(burst_accel, src_fanout_w8, reverse_deficit_fast), "Burst fanout with no response.")

        # Dynamic graph / interaction evidence.
        add("new_dst_scan_residual_no_response", "attack_dynamic_graph", safe_product(src_fanout_residual, reverse_deficit_fast), "New destination expansion above file context without response.")
        add("new_port_scan_residual_failure", "attack_dynamic_graph", safe_product(src_port_residual, failed_any), "New port expansion above file context with failure.")
        add("dst_src_pressure_residual_imbalance", "attack_dynamic_graph", safe_product(dst_pressure_residual, forward_imbalance), "Many sources pressure a destination beyond file baseline.")
        add("many_to_one_response_deficit", "attack_dynamic_graph", safe_product(dst_pressure_w8, reverse_deficit_fast, max_stack(src_rate_w8, file_rate_w8)), "Many-to-one pressure with response deficit.")
        add("source_to_many_service_switch_failure", "attack_dynamic_graph", safe_product(service_any, src_dport_frac_w8, failed_any), "Service/port diversity with failure.")
        add("pair_spread_state_mismatch", "attack_dynamic_graph", safe_product(pair_spread_w8, close_mismatch), "Pair sport/dport spread with state mismatch.")

        # Protocol/service-specific evidence.
        add("dns_udp_fanout_no_response", "attack_service", safe_product(cur_dns, cur_udp, src_fanout_w8, reverse_deficit_fast), "DNS-like UDP fanout without response.")
        add("coap_udp_burst_no_response", "attack_service", safe_product(cur_coap, cur_udp, burst_accel, reverse_deficit_fast), "CoAP-like burst without response.")
        add("http_rst_spread", "attack_service", safe_product(cur_http, cur_tcp, max_stack(cur_rst, rst_pair), src_fanout_w8), "HTTP-like TCP reset spread.")
        add("tls_syn_no_response", "attack_service", safe_product(cur_tls, cur_tcp, max_stack(cur_syn, cur_syn_wo_ack), reverse_deficit_fast), "TLS-like SYN/no-response.")
        add("nonservice_port_scan_failed", "attack_service", safe_product(nonservice_port, src_dport_frac_w8, failed_any), "Non-service port diversity with failure.")
        add("wellknown_mixed_pressure_failure", "attack_service", safe_product(cur_well_known, max_stack(dst_pressure_w8, src_fanout_w8), failed_any), "Well-known service pressure with failure.")

        # ICMP-like attack evidence.  The previous CKAF/CKAG probes exposed an
        # important blind spot: same_file_query can be ICMP-heavy, where TCP
        # handshake failure and UDP service response-deficit features naturally
        # stay zero.  These features therefore model ICMP rate/fanout/pressure
        # directly while still keeping pure file-wide load as context only.
        icmp_source_rate_pressure = safe_product(cur_icmp, src_rate_w8, max_stack(src_count_w8, recent_src))
        icmp_pair_rate_pressure = safe_product(cur_icmp, pair_rate, max_stack(pair_count_w8, recent_pair))
        icmp_fanout_pressure = safe_product(cur_icmp, max_stack(src_fanout_w8, dst_pressure_w8), max_stack(src_rate_w8, pair_rate))
        icmp_dst_pressure = safe_product(cur_icmp, dst_pressure_w8, max_stack(file_rate_w8, src_rate_w8))
        icmp_burst_accel = safe_product(cur_icmp, burst_accel, max_stack(src_rate_w8, pair_rate))
        icmp_localized_residual = safe_product(cur_icmp, max_stack(src_rate_residual, src_fanout_residual, dst_pressure_residual))
        icmp_consensus = max_stack(
            icmp_source_rate_pressure,
            icmp_pair_rate_pressure,
            icmp_fanout_pressure,
            icmp_dst_pressure,
            icmp_burst_accel,
            icmp_localized_residual,
        )
        add("icmp_source_rate_pressure", "attack_icmp", icmp_source_rate_pressure, "ICMP source rate pressure.")
        add("icmp_pair_rate_pressure", "attack_icmp", icmp_pair_rate_pressure, "ICMP pair-level repeated pressure.")
        add("icmp_fanout_pressure", "attack_icmp", icmp_fanout_pressure, "ICMP fanout or destination pressure.")
        add("icmp_dst_pressure", "attack_icmp", icmp_dst_pressure, "ICMP many-to-one destination pressure.")
        add("icmp_burst_accel", "attack_icmp", icmp_burst_accel, "ICMP burst acceleration.")
        add("icmp_localized_residual", "attack_icmp", icmp_localized_residual, "ICMP residual against file context.")
        add("icmp_consensus", "attack_icmp", icmp_consensus, "Max over ICMP pressure/fanout/burst evidence.")

        # Residualized attack evidence.
        add("src_fanout_residual_failure", "attack_residual", safe_product(src_fanout_residual, failed_any), "Source fanout is high relative to file context and failed.")
        add("src_fanout_mid_residual_failure", "attack_residual", safe_product(src_fanout_residual_mid, failed_any), "Mid-window fanout residual with failure.")
        add("src_rate_residual_no_response", "attack_residual", safe_product(src_rate_residual, reverse_deficit_fast), "Source rate is high relative to file context without response.")
        add("pair_rate_residual_imbalance", "attack_residual", safe_product(pair_rate_residual, forward_imbalance), "Pair rate exceeds file context with imbalance.")
        add("dst_pressure_residual_failure", "attack_residual", safe_product(dst_pressure_residual, failed_any), "Destination pressure residual with failure.")

        # Consensus features deliberately combine distinct evidence families,
        # not near-duplicates of fanout_accel_failure.
        lifecycle_consensus = max_stack(
            safe_product(cur_tcp, max_stack(half_open_src, half_open_pair), src_count_w32),
            safe_product(cur_tcp, close_mismatch, pair_rate),
            safe_product(cur_tcp, max_stack(cur_rst, rst_pair), pair_spread_w8),
        )
        response_consensus = max_stack(
            safe_product(reverse_deficit_persistent, pair_rate, forward_imbalance),
            safe_product(relu(1.0 - reverse_strength), src_rate_w8),
            safe_product(forward_imbalance, burst_accel),
        )
        graph_consensus = max_stack(
            safe_product(src_fanout_residual, reverse_deficit_fast),
            safe_product(src_port_residual, failed_any),
            safe_product(dst_pressure_residual, forward_imbalance),
        )
        service_consensus = max_stack(
            safe_product(udp_service, reverse_deficit_fast, src_fanout_w8),
            safe_product(tcp_service, failed_any, pair_spread_w8),
            safe_product(nonservice_port, src_dport_frac_w8, failed_any),
        )
        add("lifecycle_consensus", "attack_consensus", lifecycle_consensus, "Max over lifecycle/state-mismatch attacks.")
        add("response_consensus", "attack_consensus", response_consensus, "Max over bidirectional response-deficit attacks.")
        add("dynamic_graph_consensus", "attack_consensus", graph_consensus, "Max over dynamic graph residual attacks.")
        add("service_consensus", "attack_consensus", service_consensus, "Max over service/protocol attack evidence.")
        add("coverage_attack_consensus", "attack_consensus", max_stack(lifecycle_consensus, response_consensus, graph_consensus, service_consensus, icmp_consensus), "Coverage-oriented aggregate attack evidence.")

        # Conflict/context features.  These are useful for later gating/review
        # but should not directly support hard attack.
        add("ctx_cur_tcp", "conflict_context", cur_tcp, "Current TCP indicator.")
        add("ctx_cur_udp", "conflict_context", cur_udp, "Current UDP indicator.")
        add("ctx_cur_icmp", "conflict_context", cur_icmp, "Current ICMP indicator.")
        add("ctx_cur_service_any", "conflict_context", service_any, "Current well-known/protocol service indicator.")
        add("ctx_cur_len", "conflict_context", cur_len, "Current frame length log.")
        add("ctx_dst_port_log", "conflict_context", cur_dst_port, "Current destination port log.")
        add("ctx_tcp_window_log", "conflict_context", cur_tcp_window, "Current TCP window log.")
        add("ctx_src_fanout_w8", "conflict_context", src_fanout_w8, "Source fanout context.")
        add("ctx_src_fanout_w128", "conflict_context", src_fanout_w128, "Long source fanout context.")
        add("ctx_file_fanout_w8", "conflict_context", file_fanout_w8, "File-wide fanout context.")
        add("ctx_dst_pressure_w8", "conflict_context", dst_pressure_w8, "Destination pressure context.")
        add("ctx_dst_pressure_w128", "conflict_context", dst_pressure_w128, "Long destination pressure context.")
        add("ctx_pair_spread_w8", "conflict_context", pair_spread_w8, "Pair spread context.")
        add("ctx_src_rate_w8", "conflict_context", src_rate_w8, "Source rate context.")
        add("ctx_file_rate_w8", "conflict_context", file_rate_w8, "File rate context.")
        add("ctx_pair_rate", "conflict_context", pair_rate, "Pair rate context.")
        add("ctx_reverse_strength", "conflict_context", reverse_strength, "Reverse response context.")
        add("ctx_reverse_deficit_fast", "conflict_context", reverse_deficit_fast, "Short-window response deficit context.")
        add("ctx_forward_imbalance", "conflict_context", forward_imbalance, "Forward/reverse imbalance context.")
        add("ctx_failed_any", "conflict_context", failed_any, "Failure evidence context.")
        add("ctx_src_rate_residual", "conflict_context", src_rate_residual, "Residual rate context.")
        add("ctx_src_fanout_residual", "conflict_context", src_fanout_residual, "Residual fanout context.")

        names = [name for name, _group, _val, _why in values_by_name]
        groups = [group for _name, group, _val, _why in values_by_name]
        values = np.column_stack([val for _name, _group, val, _why in values_by_name]) if values_by_name else np.zeros((n, 0), dtype=np.float32)
        values = np.nan_to_num(values.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
        features = [
            DerivedFeature(
                name=name,
                group=group,
                hard_attack_allowed=group.startswith("attack_"),
                rationale=rationale,
            )
            for name, group, _value, rationale in values_by_name
        ]
        return values, names, groups, features

    def matrix(self, role: str, idx: np.ndarray) -> np.ndarray:
        idx = np.asarray(idx, dtype=np.int64)
        key = (role, "full")
        if key not in self._cache:
            flow = np.asarray(self.builder.matrix(ckq.FLOW_BLOCK, role, np.arange(len(self.builder.frame_by_role[role]), dtype=np.int64)), dtype=np.float32)
            self._cache[key] = self.evidence_from_flow(flow)
        values, names, groups, features = self._cache[key]
        if self._registry is None:
            self._registry = [
                {
                    "feature_index": i,
                    "feature_name": feature.name,
                    "feature_group": feature.group,
                    "hard_attack_allowed": bool(feature.hard_attack_allowed),
                    "rationale": feature.rationale,
                    "frontend_contract": (
                        "mechanism_evidence_can_support_hard_attack"
                        if feature.hard_attack_allowed
                        else "context_conflict_only_not_direct_hard_attack"
                    ),
                }
                for i, feature in enumerate(features)
            ]
        return values[idx]

    def registry(self) -> list[dict[str, Any]]:
        if self._registry is None:
            _ = self.matrix("support_train", np.asarray([0], dtype=np.int64))
        return list(self._registry or [])

    def feature_names(self) -> list[str]:
        return [str(row["feature_name"]) for row in self.registry()]

    def feature_groups(self) -> list[str]:
        return [str(row["feature_group"]) for row in self.registry()]


def role_indices(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, cap: int) -> np.ndarray:
    return ckac.role_indices(frame_by_role, role, phase, cap)


def contract_manifest(
    feature_rows: list[dict[str, Any]],
    max_attack_features: int,
    max_conflict_features: int,
) -> list[dict[str, Any]]:
    """Contract-aware manifest.

    CKAC's generic manifest is useful, but it does not know our hard-attack
    contract.  Here, only `attack_*` feature groups may enter the direct
    attack-evidence list.  Context features can still be recommended as
    conflict/context evidence.
    """

    if not feature_rows:
        return []
    df = pd.DataFrame(feature_rows)
    attack = df[
        df["feature_group"].astype(str).str.startswith("attack_")
        & df["recommendation"].isin(["candidate_attack_evidence", "weak_attack_evidence_needs_group_check"])
    ].copy()
    attack = attack.sort_values(
        ["legal_selection_score", "strength_attack_vs_oodish_select", "strength_attack_vs_oodish_fit"],
        ascending=False,
    ).head(int(max_attack_features))
    conflict = df[
        (~df["feature_group"].astype(str).str.startswith("attack_"))
        | (df["recommendation"] == "candidate_conflict_context")
    ].copy()
    conflict = conflict.sort_values(
        ["max_shortcut_strength_fit", "strength_id_vs_oodish_fit", "legal_selection_score"],
        ascending=False,
    ).head(int(max_conflict_features))
    rows: list[dict[str, Any]] = []
    for purpose, part in [("attack_evidence_candidate", attack), ("conflict_context_candidate", conflict)]:
        for rank, (_idx, row) in enumerate(part.iterrows(), start=1):
            rows.append(
                {
                    "rank": rank,
                    "purpose": purpose,
                    "feature_space": row["feature_space"],
                    "feature_index": int(row["feature_index"]),
                    "feature_name": row["feature_name"],
                    "feature_group": row["feature_group"],
                    "hard_attack_allowed": bool(str(row["feature_group"]).startswith("attack_") and purpose == "attack_evidence_candidate"),
                    "legal_selection_score": row["legal_selection_score"],
                    "max_shortcut_strength_fit": row["max_shortcut_strength_fit"],
                    "recommendation": row["recommendation"],
                    "selection_boundary": "legal_fit_select_only; report_only_stress_not_used; context_cannot_direct_hard_attack",
                }
            )
    return rows


def report_only_activation_rows(
    frontend: AttackEvidenceCoverageFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    selected_features: list[str],
    eval_cap: int,
    selection_note: str = "selected_by_legal_feature_scores_only; role_activation_is_report_only_diagnostic",
) -> list[dict[str, Any]]:
    if not selected_features:
        return []
    names = frontend.feature_names()
    name_to_idx = {name: i for i, name in enumerate(names)}
    rows: list[dict[str, Any]] = []
    roles = [
        ("support_val", "select", "legal_select_attack"),
        ("same_file_query", "select", "report_only_attack"),
        ("future_query", "select", "report_only_attack"),
        ("sealed_final_attack", "all", "report_only_attack"),
        ("id_calib", "select", "legal_select_id"),
        ("ood_val", "select", "legal_select_ood"),
        ("ood_stress", "select", "legal_select_hard_ood"),
        ("sealed_final_ood", "all", "report_only_ood"),
    ]
    for role, phase, role_kind in roles:
        if role not in frame_by_role:
            continue
        idx = role_indices(frame_by_role, role, phase, int(eval_cap))
        if len(idx) == 0:
            continue
        x = frontend.matrix(role, idx)
        for rank, name in enumerate(selected_features, start=1):
            j = name_to_idx.get(name)
            if j is None:
                continue
            vals = np.asarray(x[:, j], dtype=np.float32)
            rows.append(
                {
                    "selected_rank": rank,
                    "role": role,
                    "phase": phase,
                    "role_kind": role_kind,
                    "feature_name": name,
                    "rows": int(len(vals)),
                    "nonzero_rate": float(np.mean(vals > 1e-9)) if len(vals) else float("nan"),
                    "mean": float(np.mean(vals)) if len(vals) else float("nan"),
                    "p50": float(np.quantile(vals, 0.50)) if len(vals) else float("nan"),
                    "p90": float(np.quantile(vals, 0.90)) if len(vals) else float("nan"),
                    "max": float(np.max(vals)) if len(vals) else float("nan"),
                    "selection_boundary": selection_note,
                }
            )
    return rows


def report_only_all_feature_activation_rows(
    frontend: AttackEvidenceCoverageFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> list[dict[str, Any]]:
    """Activation diagnostics for all derived features on important roles.

    This is deliberately report-only.  It helps answer whether failure comes
    from feature selection or from no feature firing on attack roles at all.
    """

    names = frontend.feature_names()
    registry = {str(row["feature_name"]): row for row in frontend.registry()}
    rows: list[dict[str, Any]] = []
    roles = [
        ("support_val", "select", "legal_select_attack"),
        ("same_file_query", "select", "report_only_attack"),
        ("future_query", "select", "report_only_attack"),
        ("sealed_final_attack", "all", "report_only_attack"),
        ("ood_stress", "select", "legal_select_hard_ood"),
        ("sealed_final_ood", "all", "report_only_ood"),
    ]
    for role, phase, role_kind in roles:
        if role not in frame_by_role:
            continue
        idx = role_indices(frame_by_role, role, phase, int(eval_cap))
        if len(idx) == 0:
            continue
        x = frontend.matrix(role, idx)
        for j, name in enumerate(names):
            vals = np.asarray(x[:, j], dtype=np.float32)
            reg = registry.get(name, {})
            rows.append(
                {
                    "role": role,
                    "phase": phase,
                    "role_kind": role_kind,
                    "feature_name": name,
                    "feature_group": reg.get("feature_group", ""),
                    "hard_attack_allowed": reg.get("hard_attack_allowed", ""),
                    "rows": int(len(vals)),
                    "nonzero_rate": float(np.mean(vals > 1e-9)) if len(vals) else float("nan"),
                    "mean": float(np.mean(vals)) if len(vals) else float("nan"),
                    "p90": float(np.quantile(vals, 0.90)) if len(vals) else float("nan"),
                    "max": float(np.max(vals)) if len(vals) else float("nan"),
                    "selection_boundary": "all_features_report_only_activation_diagnostic_not_selection",
                }
            )
    return rows


def selected_attack_features(feature_rows: list[dict[str, Any]], max_features: int) -> list[str]:
    df = pd.DataFrame(feature_rows)
    if df.empty:
        return []
    part = df[
        df["feature_group"].astype(str).str.startswith("attack_")
        & df["recommendation"].isin(["candidate_attack_evidence", "weak_attack_evidence_needs_group_check"])
    ].copy()
    if part.empty:
        part = df[df["feature_group"].astype(str).str.startswith("attack_")].copy()
    part = part.sort_values(
        ["legal_selection_score", "strength_attack_vs_oodish_select", "strength_attack_vs_oodish_fit"],
        ascending=False,
    ).head(int(max_features))
    return [str(v) for v in part["feature_name"].tolist()]


def _collect_role_matrix(
    space: ckac.FeatureSpace,
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    cap: int,
) -> tuple[np.ndarray, pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, cap)
    if len(idx) == 0:
        return np.empty((0, len(space.feature_names)), dtype=np.float32), frame_by_role[role].iloc[[]].copy()
    return np.asarray(space.matrix(role, idx), dtype=np.float32), frame_by_role[role].iloc[idx].reset_index(drop=True)


def score_features_by_attack_label(
    space: ckac.FeatureSpace,
    frame_by_role: dict[str, pd.DataFrame],
    role_cap: int,
    min_label_rows: int,
    min_group_rows: int,
) -> list[dict[str, Any]]:
    """Legal-only per attack-label feature audit.

    The global CKAC score is intentionally strict: a feature must cover the
    whole attack class.  That is too harsh for family-specific mechanism
    evidence such as ICMP flooding.  This audit uses only support_train/support
    _val attack labels and legal benign roles to ask whether a feature is valid
    evidence for a particular attack family.
    """

    x_support_fit, f_support_fit = _collect_role_matrix(space, frame_by_role, "support_train", "fit", role_cap)
    x_support_sel, f_support_sel = _collect_role_matrix(space, frame_by_role, "support_val", "select", role_cap)
    x_id_fit, f_id_fit = _collect_role_matrix(space, frame_by_role, "id_calib", "fit", role_cap)
    x_ood_fit, f_ood_fit = _collect_role_matrix(space, frame_by_role, "ood_val", "fit", role_cap)
    x_hard_fit, f_hard_fit = _collect_role_matrix(space, frame_by_role, "ood_stress", "fit", role_cap)
    x_id_sel, _f_id_sel = _collect_role_matrix(space, frame_by_role, "id_calib", "select", role_cap)
    x_ood_sel, _f_ood_sel = _collect_role_matrix(space, frame_by_role, "ood_val", "select", role_cap)
    x_hard_sel, _f_hard_sel = _collect_role_matrix(space, frame_by_role, "ood_stress", "select", role_cap)

    if "attack_label" not in f_support_fit:
        return []
    labels = sorted(v for v in f_support_fit["attack_label"].astype(str).dropna().unique().tolist() if v and v != "nan")
    benign_fit = np.vstack([x for x in [x_id_fit, x_ood_fit, x_hard_fit] if len(x)]) if any(len(x) for x in [x_id_fit, x_ood_fit, x_hard_fit]) else np.empty((0, len(space.feature_names)), dtype=np.float32)
    benign_sel = np.vstack([x for x in [x_id_sel, x_ood_sel, x_hard_sel] if len(x)]) if any(len(x) for x in [x_id_sel, x_ood_sel, x_hard_sel]) else np.empty((0, len(space.feature_names)), dtype=np.float32)
    oodish_fit = np.vstack([x for x in [x_ood_fit, x_hard_fit] if len(x)]) if any(len(x) for x in [x_ood_fit, x_hard_fit]) else np.empty((0, len(space.feature_names)), dtype=np.float32)
    oodish_sel = np.vstack([x for x in [x_ood_sel, x_hard_sel] if len(x)]) if any(len(x) for x in [x_ood_sel, x_hard_sel]) else np.empty((0, len(space.feature_names)), dtype=np.float32)

    benign_fit_frame = pd.concat([f for f in [f_id_fit, f_ood_fit, f_hard_fit] if len(f)], ignore_index=True) if any(len(f) for f in [f_id_fit, f_ood_fit, f_hard_fit]) else pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for label in labels:
        fit_mask = f_support_fit["attack_label"].astype(str).to_numpy() == label
        sel_mask = f_support_sel["attack_label"].astype(str).to_numpy() == label if "attack_label" in f_support_sel else np.zeros(len(f_support_sel), dtype=bool)
        if int(np.sum(fit_mask)) < int(min_label_rows):
            continue
        x_label_fit = x_support_fit[fit_mask]
        x_label_sel = x_support_sel[sel_mask]
        label_frame = f_support_fit.iloc[np.flatnonzero(fit_mask)].reset_index(drop=True)
        shortcut_frame = pd.concat([label_frame, benign_fit_frame], ignore_index=True) if len(benign_fit_frame) else label_frame
        source_groups, device_groups = ckac.frame_groups(shortcut_frame)
        x_shortcut = np.vstack([x_label_fit, benign_fit]) if len(benign_fit) else x_label_fit
        for j, name in enumerate(space.feature_names):
            group = space.feature_groups[j] if j < len(space.feature_groups) else "unknown"
            fit_attack = x_label_fit[:, j]
            sel_attack = x_label_sel[:, j] if len(x_label_sel) else np.asarray([], dtype=np.float32)
            auc_id = ckac.auc_binary(fit_attack, x_id_fit[:, j] if len(x_id_fit) else np.asarray([], dtype=np.float32))
            auc_oodish = ckac.auc_binary(fit_attack, oodish_fit[:, j] if len(oodish_fit) else np.asarray([], dtype=np.float32))
            auc_hard = ckac.auc_binary(fit_attack, x_hard_fit[:, j] if len(x_hard_fit) else np.asarray([], dtype=np.float32))
            auc_sel_oodish = ckac.auc_binary(sel_attack, oodish_sel[:, j] if len(oodish_sel) else np.asarray([], dtype=np.float32))
            auc_sel_benign = ckac.auc_binary(sel_attack, benign_sel[:, j] if len(benign_sel) else np.asarray([], dtype=np.float32))

            s_id = ckac.strength(auc_id)
            s_oodish = ckac.strength(auc_oodish)
            s_hard = ckac.strength(auc_hard)
            s_sel_oodish = ckac.strength(auc_sel_oodish)
            s_sel_benign = ckac.strength(auc_sel_benign)
            s_id_ood = ckac.strength(ckac.auc_binary(x_id_fit[:, j] if len(x_id_fit) else np.asarray([], dtype=np.float32), oodish_fit[:, j] if len(oodish_fit) else np.asarray([], dtype=np.float32)))
            source_s, source_group, source_rows = ckac.max_one_vs_rest_strength(x_shortcut[:, j], source_groups, min_group_rows)
            device_s, device_group, device_rows = ckac.max_one_vs_rest_strength(x_shortcut[:, j], device_groups, min_group_rows)
            shortcut_s = max(source_s, device_s)
            fit_score = 0.45 * ckac.finite(s_oodish, 0.0) + 0.35 * ckac.finite(s_hard, 0.0) + 0.20 * ckac.finite(s_id, 0.0)
            select_score = 0.60 * ckac.finite(s_sel_oodish, 0.0) + 0.40 * ckac.finite(s_sel_benign, 0.0)
            legal_score = 0.65 * fit_score + 0.35 * select_score - 0.30 * shortcut_s - 0.10 * ckac.finite(s_id_ood, 0.0)
            if legal_score >= 0.30 and shortcut_s <= 0.45 and ckac.finite(s_sel_oodish, 0.0) >= 0.15:
                recommendation = "candidate_family_attack_evidence"
            elif legal_score >= 0.15 and shortcut_s <= 0.65:
                recommendation = "weak_family_attack_evidence_needs_group_check"
            elif shortcut_s >= 0.55 or ckac.finite(s_id_ood, 0.0) >= 0.45:
                recommendation = "family_conflict_or_shortcut"
            else:
                recommendation = "family_demote_or_discard"
            rows.append(
                {
                    "feature_space": space.name,
                    "attack_label": label,
                    "feature_index": j,
                    "feature_name": name,
                    "feature_group": group,
                    "hard_attack_allowed": bool(str(group).startswith("attack_")),
                    "n_fit_attack_label": int(len(fit_attack)),
                    "n_select_attack_label": int(len(sel_attack)),
                    "strength_label_vs_id_fit": s_id,
                    "strength_label_vs_oodish_fit": s_oodish,
                    "strength_label_vs_hard_ood_fit": s_hard,
                    "strength_label_vs_oodish_select": s_sel_oodish,
                    "strength_label_vs_benign_select": s_sel_benign,
                    "source_shortcut_strength_fit": source_s,
                    "source_shortcut_group": source_group,
                    "source_shortcut_rows": source_rows,
                    "device_shortcut_strength_fit": device_s,
                    "device_shortcut_group": device_group,
                    "device_shortcut_rows": device_rows,
                    "max_shortcut_strength_fit": shortcut_s,
                    "id_vs_oodish_strength_fit": s_id_ood,
                    "family_legal_selection_score": float(legal_score),
                    "recommendation": recommendation,
                    "selection_boundary": "support_train_fit_support_val_select_and_legal_benign_roles_only",
                }
            )
    return rows


def family_recommended_manifest(family_rows: list[dict[str, Any]], max_per_label: int) -> list[dict[str, Any]]:
    if not family_rows:
        return []
    df = pd.DataFrame(family_rows)
    rows: list[dict[str, Any]] = []
    for label, part0 in df.groupby("attack_label", sort=True):
        part = part0[
            part0["hard_attack_allowed"].astype(bool)
            & part0["recommendation"].isin(["candidate_family_attack_evidence", "weak_family_attack_evidence_needs_group_check"])
        ].copy()
        part = part.sort_values(
            ["family_legal_selection_score", "strength_label_vs_oodish_select", "strength_label_vs_oodish_fit"],
            ascending=False,
        ).head(int(max_per_label))
        for rank, (_idx, row) in enumerate(part.iterrows(), start=1):
            rows.append(
                {
                    "attack_label": label,
                    "rank": rank,
                    "feature_name": row["feature_name"],
                    "feature_group": row["feature_group"],
                    "family_legal_selection_score": row["family_legal_selection_score"],
                    "max_shortcut_strength_fit": row["max_shortcut_strength_fit"],
                    "n_fit_attack_label": row["n_fit_attack_label"],
                    "n_select_attack_label": row["n_select_attack_label"],
                    "recommendation": row["recommendation"],
                    "selection_boundary": "per_attack_label_legal_only_no_query_future_sealed",
                }
            )
    return rows


def build_readout(
    out: Path,
    feature_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    manifest_rows: list[dict[str, Any]],
    family_manifest_rows: list[dict[str, Any]],
    activation_rows: list[dict[str, Any]],
    stress_rows: list[dict[str, Any]],
    seconds: float,
) -> list[str]:
    df = pd.DataFrame(feature_rows)
    man = pd.DataFrame(manifest_rows)
    fam = pd.DataFrame(family_manifest_rows)
    act = pd.DataFrame(activation_rows)
    stress = pd.DataFrame(stress_rows)
    lines = [
        "# issue27ckag attack evidence coverage frontend v1",
        "",
        "## Scope",
        "",
        "Frontend evidence audit after CKAF showed attack evidence was too narrow. This is not a detector-training result.",
        "",
        "## Top legal attack-evidence candidates",
        "",
        "| rank | feature | group | score | shortcut | recommendation |",
        "|---:|---|---|---:|---:|---|",
    ]
    if not man.empty:
        attack = man[man["purpose"] == "attack_evidence_candidate"].head(16)
        for _idx, row in attack.iterrows():
            lines.append(
                f"| {int(row['rank'])} | {row['feature_name']} | {row['feature_group']} | "
                f"{fmt(row['legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    lines.extend(
        [
            "",
            "## Group summary",
            "",
            "| group | count | max score | mean score | attack candidates | weak attack | conflict | demote | max shortcut |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in group_rows[:18]:
        lines.append(
            f"| {row['feature_group']} | {row['feature_count']} | {fmt(row['max_legal_selection_score'])} | "
            f"{fmt(row['mean_legal_selection_score'])} | {row['candidate_attack_evidence_count']} | "
            f"{row['weak_attack_evidence_count']} | {row['conflict_context_count']} | "
            f"{row['demote_or_discard_count']} | {fmt(row['max_shortcut_strength_fit'])} |"
        )
    if not fam.empty:
        lines.extend(
            [
                "",
                "## Legal per-attack-label evidence",
                "",
                "| attack label | rank | feature | group | score | shortcut | recommendation |",
                "|---|---:|---|---|---:|---:|---|",
            ]
        )
        for _idx, row in fam.head(36).iterrows():
            lines.append(
                f"| {row['attack_label']} | {int(row['rank'])} | {row['feature_name']} | {row['feature_group']} | "
                f"{fmt(row['family_legal_selection_score'])} | {fmt(row['max_shortcut_strength_fit'])} | {row['recommendation']} |"
            )
    if not act.empty:
        top = act[act["role"].isin(["support_val", "same_file_query", "future_query", "sealed_final_attack", "sealed_final_ood", "ood_stress"])].head(48)
        lines.extend(
            [
                "",
                "## Report-only activation snapshot",
                "",
                "| rank | role | feature | nonzero | mean | p90 | max |",
                "|---:|---|---|---:|---:|---:|---:|",
            ]
        )
        for _idx, row in top.iterrows():
            lines.append(
                f"| {int(row['selected_rank'])} | {row['role']} | {row['feature_name']} | "
                f"{fmt(row['nonzero_rate'])} | {fmt(row['mean'])} | {fmt(row['p90'])} | {fmt(row['max'])} |"
            )
    if not stress.empty:
        stress2 = stress.sort_values("attack_affinity_positive_means_closer_to_attack", ascending=False).head(12)
        lines.extend(
            [
                "",
                "## Report-only held-family warnings",
                "",
                "| held | role | feature | affinity | rows |",
                "|---|---|---|---:|---:|",
            ]
        )
        for _idx, row in stress2.iterrows():
            lines.append(
                f"| {row['held_value']} | {row['role']} | {row['feature_name']} | "
                f"{fmt(row['attack_affinity_positive_means_closer_to_attack'])} | {int(row['rows'])} |"
            )
    counts = df["recommendation"].value_counts().to_dict() if not df.empty else {}
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- Legal feature scoring uses only fit/select development roles.",
            "- Query/future/sealed and held-family diagnostics are report-only and do not choose features.",
            "- Raw115 is not used as direct hard-attack evidence in this frontend.",
            "- Label columns in processed CSV are used only for alignment/extraction audit, not as features.",
            f"- recommendation counts: {json.dumps({str(k): int(v) for k, v in counts.items()}, ensure_ascii=False)}",
            f"- output: `{out}`",
            f"- runtime seconds: {fmt(seconds, 1)}",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(bool(args.smoke))
    ckt.add_family_columns(frame_by_role)
    role_cap_rows: list[dict[str, Any]] = []
    if int(args.source_cap) > 0:
        x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
            x_by_role,
            frame_by_role,
            int(args.role_cap),
            int(args.source_cap),
            cap_rule="ckag attack-evidence coverage capped diagnostic",
        )

    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=bool(args.smoke), local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = AttackEvidenceCoverageFrontend(builder)
    _ = frontend.matrix("support_train", np.asarray([0], dtype=np.int64))

    space = ckac.FeatureSpace(
        name="ckag_attack_evidence_coverage",
        feature_names=frontend.feature_names(),
        feature_groups=frontend.feature_groups(),
        matrix_fn=frontend.matrix,
        description="Coverage-expanded flow lifecycle/response/temporal/dynamic-graph attack evidence.",
    )
    feature_rows, role_audit = ckac.score_feature_space(
        space,
        frame_by_role,
        int(args.eval_cap),
        int(args.min_group_rows),
    )
    family_rows = score_features_by_attack_label(
        space,
        frame_by_role,
        int(args.eval_cap),
        int(args.min_label_rows),
        int(args.min_group_rows),
    )
    group_rows = ckac.group_summary(feature_rows)
    manifest_rows = contract_manifest(
        feature_rows,
        int(args.max_attack_features),
        int(args.max_conflict_features),
    )
    selected_names = selected_attack_features(feature_rows, int(args.activation_top_k))
    family_manifest_rows = family_recommended_manifest(family_rows, int(args.family_top_k))
    activation_rows = report_only_activation_rows(frontend, frame_by_role, selected_names, int(args.eval_cap))
    all_activation_rows = report_only_all_feature_activation_rows(frontend, frame_by_role, int(args.eval_cap))
    held_values = [v.strip() for v in str(args.held_values).split(",") if v.strip()]
    stress_rows = ckac.held_stress_rows(
        [space],
        frame_by_role,
        feature_rows,
        held_values,
        int(args.eval_cap),
        int(args.stress_top_k),
    )
    alignment_rows = ckq.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(out / "feature_scores.csv", feature_rows)
    cko.write_csv(out / "per_attack_label_feature_scores.csv", family_rows)
    cko.write_csv(out / "feature_group_scores.csv", group_rows)
    cko.write_csv(out / "recommended_frontend_manifest.csv", manifest_rows)
    cko.write_csv(out / "per_attack_label_recommended_manifest.csv", family_manifest_rows)
    cko.write_csv(out / "selected_attack_activation_report_only.csv", activation_rows)
    cko.write_csv(out / "all_feature_activation_report_only.csv", all_activation_rows)
    cko.write_csv(out / "held_family_feature_stress_report_only.csv", stress_rows)
    cko.write_csv(out / "frontend_registry.csv", frontend.registry())
    cko.write_csv(out / "role_usage_audit.csv", role_audit)
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(out / "alignment_audit.csv", alignment_rows)
    cko.write_md(
        out / "codex_readout.md",
        build_readout(out, feature_rows, group_rows, manifest_rows, family_manifest_rows, activation_rows, stress_rows, seconds),
    )
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "smoke": bool(args.smoke),
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "eval_cap": int(args.eval_cap),
            "min_group_rows": int(args.min_group_rows),
            "min_label_rows": int(args.min_label_rows),
            "held_values": held_values,
            "selected_activation_features": selected_names,
            "data_use_boundary": {
                "legal_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "legal_select_validation_roles": ["support_val select", "id_calib select", "ood_val select", "ood_stress select"],
                "per_attack_label_legal_roles": ["support_train fit attack_label", "support_val select attack_label", "legal benign fit/select roles"],
                "query_future_sealed_used_for_feature_selection": False,
                "held_family_stress_used_for_feature_selection": False,
                "processed_label_used_as_feature": False,
            },
            "frontend_contract": {
                "raw115_direct_attack_evidence": False,
                "attack_groups": sorted({row["feature_group"] for row in frontend.registry() if str(row["feature_group"]).startswith("attack_")}),
                "context_groups": sorted({row["feature_group"] for row in frontend.registry() if not str(row["feature_group"]).startswith("attack_")}),
                "flow_temporal_state": "current/past-only within processed source file",
                "row_alignment": "CKQ builder role/index aligned matrices",
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", default=True)
    parser.add_argument("--role-cap", type=int, default=512)
    parser.add_argument("--source-cap", type=int, default=0)
    parser.add_argument("--eval-cap", type=int, default=512)
    parser.add_argument("--min-group-rows", type=int, default=8)
    parser.add_argument("--min-label-rows", type=int, default=5)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--max-attack-features", type=int, default=32)
    parser.add_argument("--max-conflict-features", type=int, default=24)
    parser.add_argument("--activation-top-k", type=int, default=12)
    parser.add_argument("--family-top-k", type=int, default=4)
    parser.add_argument("--stress-top-k", type=int, default=24)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
