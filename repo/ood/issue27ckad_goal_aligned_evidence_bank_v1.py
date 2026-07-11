"""issue27ckad: goal-aligned mechanism evidence bank v1.

This constructs a new frontend candidate after CKAC's feature audit.

Design goals:

1. Separate OOD from attack: hard-attack evidence must come from mechanism-like
   interactions, not raw source/device style.
2. Keep review bounded: context/conflict evidence is retained to suppress or
   question OOD-looking rows, not to turn everything into review.
3. Improve basic generalization: favor cross-window, source-normalized and
   bidirectional interaction evidence; demote raw115 to context only.

This file is still a diagnostic frontend audit, not a final detector.  It builds
the CKAD evidence bank and immediately scores its individual features with the
CKAC legal feature-utility audit.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckac_frontend_feature_utility_audit_v1 as ckac  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
import issue27ckq_flow_temporal_evidence_frontend_v1 as ckq  # noqa: E402
import issue27ckt_neural_leave_device_family_stress_v1 as ckt  # noqa: E402
import issue27cky_interaction_causal_frontend_v1 as cky  # noqa: E402


ISSUE = "issue27ckad_goal_aligned_evidence_bank_v1_2026-07-05"
OUT = cko.ROOT / "runs" / ISSUE
DEFAULT_HELD_VALUES = ckac.DEFAULT_HELD_VALUES


RAW_CONTEXT_NAMES = [
    # From CKAC legal-fit/select audit: strong but shortcut-heavy raw115
    # dimensions.  They are context/conflict only, not hard-attack evidence.
    "HpHp_0.01_mean_0",
    "HpHp_0.01_magnitude_0_1",
    "HpHp_0.1_mean_0",
    "HpHp_0.1_magnitude_0_1",
    "HH_0.1_mean_0",
    "HH_0.1_magnitude_0_1",
    "MI_dir_0.1_mean",
    "MI_dir_0.01_mean",
    "H_0.1_mean",
    "H_0.01_mean",
    # Lower-shortcut stability hints; still context only at this stage.
    "HH_jit_1_std",
    "HH_jit_3_std",
    "HH_jit_5_std",
    "HpHp_0.1_covariance_0_1",
    "HpHp_0.1_pcc_0_1",
]


def slug(text: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_")[:80] or "empty"


def _ratio_gap(short: np.ndarray, long: np.ndarray) -> np.ndarray:
    return cky.clipped(cky.relu(short - long), 6.0)


def _persistent(short: np.ndarray, mid: np.ndarray, long: np.ndarray) -> np.ndarray:
    return np.minimum(np.minimum(short, mid), long).astype(np.float32)


def _escalating(short: np.ndarray, mid: np.ndarray, long: np.ndarray) -> np.ndarray:
    return cky.safe_product(cky.relu(short - mid), cky.relu(mid - long))


def _max3(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return np.maximum.reduce([a, b, c]).astype(np.float32)


class GoalAlignedEvidenceBank:
    """CKAD evidence bank.

    Rows are aligned by CKQ's builder, exactly like CKY.  No label/source/device
    value is used as an inference feature.
    """

    def __init__(self, builder: ckq.FlowTemporalBuilder):
        self.builder = builder
        self.raw_names = ckac.raw_feature_names()
        self.raw_index = {name: i for i, name in enumerate(self.raw_names)}
        self._registry: list[dict[str, Any]] | None = None

    def selected_raw_context(self, raw: np.ndarray) -> tuple[np.ndarray, list[str], list[str]]:
        cols = [self.raw_index[name] for name in RAW_CONTEXT_NAMES if name in self.raw_index]
        names = [f"rawctx_{self.raw_names[i]}" for i in cols]
        if len(raw) == 0 or not cols:
            values = np.zeros((len(raw), len(cols)), dtype=np.float32)
        else:
            values = np.asarray(raw[:, cols], dtype=np.float32)
        groups = ["raw_context_conflict"] * len(names)
        return values, names, groups

    def evidence_from_arrays(self, raw: np.ndarray, flow: np.ndarray) -> tuple[np.ndarray, list[str], list[str]]:
        raw = np.asarray(raw, dtype=np.float32)
        flow = np.asarray(flow, dtype=np.float32)

        # Reuse CKY as the base, then add stricter mechanism channels.  CKY's
        # own attack channels remain auditable; CKAD adds more targeted
        # cross-window and protocol-specific evidence.
        base = cky.InteractionCausalFrontend(self.builder)
        base_values, base_names, base_groups = base.evidence_from_arrays(raw, flow)

        cur_tcp = cky.fcol(flow, "cur_is_tcp")
        cur_udp = cky.fcol(flow, "cur_is_udp")
        cur_icmp = cky.fcol(flow, "cur_is_icmp")
        cur_dns = cky.fcol(flow, "cur_is_dns")
        cur_coap = cky.fcol(flow, "cur_is_coap")
        cur_well_known = cky.fcol(flow, "cur_dst_well_known")
        cur_syn = cky.fcol(flow, "cur_tcp_syn")
        cur_rst = cky.fcol(flow, "cur_tcp_rst")
        cur_syn_wo_ack = cky.fcol(flow, "cur_syn_without_ack")
        cur_ack_wo_syn = cky.fcol(flow, "cur_ack_without_syn")
        cur_len = cky.fcol(flow, "cur_log_frame_len")
        cur_ttl = cky.fcol(flow, "cur_ttl_norm")

        src_fan8 = cky.max_named(flow, ["prior_src_w8_unique_dst_frac", "prior_src_w8_unique_dport_frac"])
        src_fan32 = cky.max_named(flow, ["prior_src_w32_unique_dst_frac", "prior_src_w32_unique_dport_frac"])
        src_fan128 = cky.max_named(flow, ["prior_src_w128_unique_dst_frac", "prior_src_w128_unique_dport_frac"])
        dst_press8 = cky.max_named(flow, ["prior_dst_w8_unique_src_frac", "prior_dst_w8_unique_sport_frac"])
        dst_press32 = cky.max_named(flow, ["prior_dst_w32_unique_src_frac", "prior_dst_w32_unique_sport_frac"])
        dst_press128 = cky.max_named(flow, ["prior_dst_w128_unique_src_frac", "prior_dst_w128_unique_sport_frac"])
        pair_spread8 = cky.max_named(flow, ["prior_pair_w8_unique_sport_frac", "prior_pair_w8_unique_dport_frac"])
        pair_spread32 = cky.max_named(flow, ["prior_pair_w32_unique_sport_frac", "prior_pair_w32_unique_dport_frac"])
        pair_spread128 = cky.max_named(flow, ["prior_pair_w128_unique_sport_frac", "prior_pair_w128_unique_dport_frac"])

        src_rate8 = cky.max_named(flow, ["prior_src_w8_event_rate_log", "prior_src_w8_byte_rate_log"])
        src_rate32 = cky.max_named(flow, ["prior_src_w32_event_rate_log", "prior_src_w32_byte_rate_log"])
        src_rate128 = cky.max_named(flow, ["prior_src_w128_event_rate_log", "prior_src_w128_byte_rate_log"])
        dst_rate8 = cky.max_named(flow, ["prior_dst_w8_event_rate_log", "prior_dst_w8_byte_rate_log"])
        dst_rate32 = cky.max_named(flow, ["prior_dst_w32_event_rate_log", "prior_dst_w32_byte_rate_log"])
        dst_rate128 = cky.max_named(flow, ["prior_dst_w128_event_rate_log", "prior_dst_w128_byte_rate_log"])
        pair_rate8 = cky.max_named(flow, ["prior_pair_w8_event_rate_log", "prior_pair_w8_byte_rate_log"])
        pair_rate32 = cky.max_named(flow, ["prior_pair_w32_event_rate_log", "prior_pair_w32_byte_rate_log"])
        pair_rate128 = cky.max_named(flow, ["prior_pair_w128_event_rate_log", "prior_pair_w128_byte_rate_log"])

        src_syn = _max3(cky.fcol(flow, "prior_src_w8_syn_rate"), cky.fcol(flow, "prior_src_w32_syn_rate"), cky.fcol(flow, "prior_src_w128_syn_rate"))
        src_ack = _max3(cky.fcol(flow, "prior_src_w8_ack_rate"), cky.fcol(flow, "prior_src_w32_ack_rate"), cky.fcol(flow, "prior_src_w128_ack_rate"))
        src_rst = _max3(cky.fcol(flow, "prior_src_w8_rst_rate"), cky.fcol(flow, "prior_src_w32_rst_rate"), cky.fcol(flow, "prior_src_w128_rst_rate"))
        pair_syn = _max3(cky.fcol(flow, "prior_pair_w8_syn_rate"), cky.fcol(flow, "prior_pair_w32_syn_rate"), cky.fcol(flow, "prior_pair_w128_syn_rate"))
        pair_ack = _max3(cky.fcol(flow, "prior_pair_w8_ack_rate"), cky.fcol(flow, "prior_pair_w32_ack_rate"), cky.fcol(flow, "prior_pair_w128_ack_rate"))
        pair_rst = _max3(cky.fcol(flow, "prior_pair_w8_rst_rate"), cky.fcol(flow, "prior_pair_w32_rst_rate"), cky.fcol(flow, "prior_pair_w128_rst_rate"))

        reverse_seen = _max3(
            cky.fcol(flow, "prior_pair_reverse_seen_w8"),
            cky.fcol(flow, "prior_pair_reverse_seen_w32"),
            cky.fcol(flow, "prior_pair_reverse_seen_w128"),
        )
        reverse_count = _max3(
            cky.fcol(flow, "prior_pair_reverse_count_frac_w8"),
            cky.fcol(flow, "prior_pair_reverse_count_frac_w32"),
            cky.fcol(flow, "prior_pair_reverse_count_frac_w128"),
        )
        reverse_byte = _max3(
            cky.fcol(flow, "prior_pair_reverse_byte_rate_log_w8"),
            cky.fcol(flow, "prior_pair_reverse_byte_rate_log_w32"),
            cky.fcol(flow, "prior_pair_reverse_byte_rate_log_w128"),
        )
        fwd_rev_count = cky.mean_named(
            flow,
            [
                "prior_pair_forward_reverse_count_balance_w8",
                "prior_pair_forward_reverse_count_balance_w32",
                "prior_pair_forward_reverse_count_balance_w128",
            ],
        )
        fwd_rev_byte = cky.mean_named(
            flow,
            [
                "prior_pair_forward_reverse_byte_balance_w8",
                "prior_pair_forward_reverse_byte_balance_w32",
                "prior_pair_forward_reverse_byte_balance_w128",
            ],
        )
        reverse_deficit = cky.relu(1.0 - np.maximum(reverse_seen, reverse_count))
        forward_imbalance = cky.relu(np.maximum(fwd_rev_count, fwd_rev_byte))

        fanout_escalation = _escalating(src_fan8, src_fan32, src_fan128)
        fanout_persistent = _persistent(src_fan8, src_fan32, src_fan128)
        dst_pressure_escalation = _escalating(dst_press8, dst_press32, dst_press128)
        dst_pressure_persistent = _persistent(dst_press8, dst_press32, dst_press128)
        pair_spread_escalation = _escalating(pair_spread8, pair_spread32, pair_spread128)
        src_rate_escalation = _escalating(src_rate8, src_rate32, src_rate128)
        dst_rate_escalation = _escalating(dst_rate8, dst_rate32, dst_rate128)
        pair_rate_escalation = _escalating(pair_rate8, pair_rate32, pair_rate128)
        src_rate_residual = _ratio_gap(src_rate8, src_rate128)
        dst_rate_residual = _ratio_gap(dst_rate8, dst_rate128)
        pair_rate_residual = _ratio_gap(pair_rate8, pair_rate128)
        syn_ack_gap = cky.relu(np.maximum(src_syn, pair_syn) - np.maximum(src_ack, pair_ack))
        rst_pressure = np.maximum(src_rst, pair_rst).astype(np.float32)
        failed_state = np.maximum.reduce([cur_syn_wo_ack, cur_ack_wo_syn, syn_ack_gap, rst_pressure]).astype(np.float32)
        low_response = np.maximum(reverse_deficit, cky.relu(0.2 - reverse_byte)).astype(np.float32)

        # Mechanism evidence: deliberately conjunctive and protocol-aware.
        new_attack_values = np.column_stack(
            [
                cky.safe_product(cur_tcp, cur_syn, fanout_escalation, low_response),
                cky.safe_product(cur_tcp, fanout_persistent, failed_state),
                cky.safe_product(cur_tcp, pair_spread_escalation, failed_state),
                cky.safe_product(cur_tcp, rst_pressure, pair_spread8),
                cky.safe_product(cur_udp, np.maximum(cur_dns, cur_coap), fanout_escalation, src_rate_residual),
                cky.safe_product(cur_udp, fanout_persistent, low_response, src_rate_residual),
                cky.safe_product(cur_icmp, fanout_escalation, low_response),
                cky.safe_product(dst_pressure_escalation, failed_state),
                cky.safe_product(dst_pressure_persistent, dst_rate_residual, forward_imbalance),
                cky.safe_product(src_rate_escalation, low_response, np.maximum(src_fan8, fanout_escalation)),
                cky.safe_product(dst_rate_escalation, forward_imbalance, dst_pressure_persistent),
                cky.safe_product(pair_rate_escalation, failed_state, pair_spread8),
                cky.safe_product(np.maximum(cur_well_known, np.maximum(cur_dns, cur_coap)), fanout_persistent, failed_state),
                cky.safe_product(fanout_escalation, failed_state, low_response),
                cky.safe_product(dst_pressure_escalation, dst_rate_residual, low_response),
                cky.safe_product(src_rate_residual, pair_rate_residual, low_response),
                cky.safe_product(fanout_persistent, failed_state, src_rate_residual),
                cky.safe_product(dst_pressure_persistent, forward_imbalance, low_response),
            ]
        ).astype(np.float32)
        new_attack_names = [
            "tcp_syn_fanout_escalation_low_response",
            "tcp_persistent_fanout_failed_state",
            "tcp_pair_spread_escalation_failed_state",
            "tcp_rst_pair_spread",
            "udp_service_fanout_escalation_rate_residual",
            "udp_persistent_fanout_low_response_rate_residual",
            "icmp_fanout_escalation_low_response",
            "dst_pressure_escalation_failed_state",
            "dst_persistent_pressure_rate_forward_imbalance",
            "src_rate_escalation_fanout_low_response",
            "dst_rate_escalation_forward_imbalance_pressure",
            "pair_rate_escalation_failed_spread",
            "well_known_service_spread_failed",
            "fanout_failed_low_response_consensus",
            "dst_pressure_rate_low_response_consensus",
            "source_pair_rate_residual_low_response",
            "persistent_fanout_failed_rate_residual",
            "persistent_dst_pressure_forward_low_response",
        ]
        new_attack_groups = ["ckad_attack_mechanism"] * len(new_attack_names)

        # Context/conflict channels: useful for suppressing OOD-like traffic,
        # but not sufficient for hard attack by themselves.
        raw_ctx_values, raw_ctx_names, raw_ctx_groups = self.selected_raw_context(raw)
        new_context_values = np.column_stack(
            [
                fanout_escalation,
                fanout_persistent,
                dst_pressure_escalation,
                dst_pressure_persistent,
                pair_spread_escalation,
                src_rate_escalation,
                dst_rate_escalation,
                pair_rate_escalation,
                src_rate_residual,
                dst_rate_residual,
                pair_rate_residual,
                syn_ack_gap,
                rst_pressure,
                failed_state,
                low_response,
                reverse_seen,
                reverse_count,
                reverse_byte,
                forward_imbalance,
                cur_len,
                cur_ttl,
            ]
        ).astype(np.float32)
        new_context_names = [
            "ctx_fanout_escalation",
            "ctx_fanout_persistent",
            "ctx_dst_pressure_escalation",
            "ctx_dst_pressure_persistent",
            "ctx_pair_spread_escalation",
            "ctx_src_rate_escalation",
            "ctx_dst_rate_escalation",
            "ctx_pair_rate_escalation",
            "ctx_src_rate_residual",
            "ctx_dst_rate_residual",
            "ctx_pair_rate_residual",
            "ctx_syn_ack_gap",
            "ctx_rst_pressure",
            "ctx_failed_state",
            "ctx_low_response",
            "ctx_reverse_seen",
            "ctx_reverse_count",
            "ctx_reverse_byte",
            "ctx_forward_imbalance",
            "ctx_cur_len",
            "ctx_cur_ttl",
        ]
        new_context_groups = ["ckad_conflict_context"] * len(new_context_names)

        values = np.hstack([base_values, new_attack_values, new_context_values, raw_ctx_values]).astype(np.float32)
        names = base_names + new_attack_names + new_context_names + raw_ctx_names
        groups = base_groups + new_attack_groups + new_context_groups + raw_ctx_groups
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
                    "hard_attack_allowed": group in {"attack_mechanism", "ckad_attack_mechanism"},
                    "frontend_contract": (
                        "mechanism_or_cross_window_interaction_can_support_hard_attack"
                        if group in {"attack_mechanism", "ckad_attack_mechanism"}
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


def build_spaces(frontend: GoalAlignedEvidenceBank) -> list[ckac.FeatureSpace]:
    _ = frontend.matrix("support_train", np.asarray([0], dtype=np.int64), "full")
    reg = frontend.registry()
    groups = []
    for row in reg:
        group = str(row["evidence_group"])
        if group not in groups:
            groups.append(group)
    spaces = []
    for group in groups:
        names = [str(r["feature_name"]) for r in reg if str(r["evidence_group"]) == group]
        spaces.append(
            ckac.FeatureSpace(
                name=f"ckad_{group}",
                feature_names=names,
                feature_groups=[group] * len(names),
                matrix_fn=lambda role, idx, b=group: frontend.matrix(role, idx, b),
                description=f"CKAD evidence group {group}",
            )
        )
    return spaces


def build_readout(out: Path, feature_rows: list[dict[str, Any]], group_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = ckac.build_readout(out, feature_rows, group_rows, manifest_rows, [], seconds)
    if lines:
        lines[0] = "# issue27ckad goal-aligned evidence bank v1"
    insert_at = 2 if len(lines) > 2 else len(lines)
    lines[insert_at:insert_at] = [
        "",
        "## CKAD design",
        "",
        "- Adds protocol-aware scan/flood/failure/low-response mechanism features.",
        "- Adds cross-window escalation/persistence and source/pair residual features.",
        "- Demotes selected raw115 dimensions to raw_context_conflict only.",
        "- This is a frontend audit, not a final detector.",
    ]
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{slug(args.run_tag)}"
    out.mkdir(parents=True, exist_ok=True)

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(bool(args.smoke))
    ckt.add_family_columns(frame_by_role)
    x_by_role, frame_by_role, role_cap_rows = ckq.cap_loaded_roles(
        x_by_role,
        frame_by_role,
        int(args.role_cap),
        int(args.source_cap),
        cap_rule="goal-aligned evidence-bank capped diagnostic",
    )
    cache = ckq.FlowTemporalZipFeatureCache(cko.GOTHAM_ZIP, smoke=bool(args.smoke), local_context_only=False)
    builder = ckq.FlowTemporalBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))
    frontend = GoalAlignedEvidenceBank(builder)
    spaces = build_spaces(frontend)

    feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for space in spaces:
        rows, audit = ckac.score_feature_space(space, frame_by_role, int(args.eval_cap), int(args.min_group_rows))
        feature_rows.extend(rows)
        audit_rows.extend(audit)
    group_rows = ckac.group_summary(feature_rows)
    manifest_rows = ckac.recommended_manifest(feature_rows, int(args.max_attack_features), int(args.max_conflict_features))
    held_values = [v.strip() for v in str(args.held_values).split(",") if v.strip()]
    stress_rows = ckac.held_stress_rows(spaces, frame_by_role, feature_rows, held_values, int(args.eval_cap), int(args.stress_top_k))
    seconds = time.time() - started

    cko.write_csv(out / "feature_scores.csv", feature_rows)
    cko.write_csv(out / "feature_group_scores.csv", group_rows)
    cko.write_csv(out / "recommended_frontend_manifest.csv", manifest_rows)
    cko.write_csv(out / "held_family_feature_stress_report_only.csv", stress_rows)
    cko.write_csv(out / "role_usage_audit.csv", audit_rows)
    cko.write_csv(out / "frontend_registry.csv", frontend.registry())
    cko.write_csv(out / "role_cap_audit.csv", role_cap_rows)
    cko.write_csv(out / "flow_temporal_extraction_audit.csv", cache.audit_rows)
    cko.write_md(out / "codex_readout.md", build_readout(out, feature_rows, group_rows, manifest_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "run_tag": args.run_tag,
            "smoke": bool(args.smoke),
            "role_cap": int(args.role_cap),
            "source_cap": int(args.source_cap),
            "eval_cap": int(args.eval_cap),
            "held_values": held_values,
            "raw_context_names": RAW_CONTEXT_NAMES,
            "data_use_boundary": {
                "legal_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "legal_select_validation_roles": ["support_val select", "id_calib select", "ood_val select", "ood_stress select"],
                "report_only_stress_used_for_selection": False,
            },
            "frontend_contract": {
                "hard_attack_allowed_groups": ["attack_mechanism", "ckad_attack_mechanism"],
                "raw115_direct_hard_attack": False,
                "source_or_device_used_as_inference_feature": False,
                "flow_temporal_state": "current/past-only within processed source file",
            },
            "sources_used_for_design": [
                "Zeek conn.log connection-level monitoring semantics",
                "IPFIX flow information model",
                "NetFlow temporal feature literature",
                "cross-network IIoT generalization warnings",
            ],
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true", default=True)
    parser.add_argument("--role-cap", type=int, default=256)
    parser.add_argument("--source-cap", type=int, default=24)
    parser.add_argument("--eval-cap", type=int, default=256)
    parser.add_argument("--min-group-rows", type=int, default=8)
    parser.add_argument("--held-values", default=DEFAULT_HELD_VALUES)
    parser.add_argument("--max-attack-features", type=int, default=40)
    parser.add_argument("--max-conflict-features", type=int, default=40)
    parser.add_argument("--stress-top-k", type=int, default=16)
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
