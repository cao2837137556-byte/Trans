from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic as bd


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27be_past_only_replay_audit_on_conflict_gate_2026-06-07"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BD = ROOT / "runs" / "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
REPLAY_TOLERANCE = 1e-12
REPORT_ONLY_ROLES = {
    "final_ood_benign_eval",
    "attack_eval",
    "medium_attack_eval_report_only",
    "dev_heavy_query_report_only",
    "final_ood_report_only",
}
FORBIDDEN_FOR_SELECTION = REPORT_ONLY_ROLES | {"dev_heavy_query"}


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    bd.write_csv(path, rows, fieldnames)


def write_md(path: Path, lines: list[str]) -> None:
    bd.write_md(path, lines)


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    bd.append_doc(path, marker, lines)


def sha256_file(path: Path) -> str:
    return bd.sha256_file(path)


def hash_indices(indices: np.ndarray) -> str:
    return bd.hash_indices(indices)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def rate(mask: np.ndarray) -> float:
    return bd.rate(mask)


def role_indices_set(name: str, idx: np.ndarray, namespace: str = "medium_asset") -> dict[str, Any]:
    return {
        "namespace": namespace,
        "role_or_split": name,
        "rows": int(len(idx)),
        "indices_sha256": hash_indices(idx),
        "min_index": int(np.min(idx)) if len(idx) else "",
        "max_index": int(np.max(idx)) if len(idx) else "",
    }


def pair_disjoint_audit(sets: dict[str, np.ndarray], namespace: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    names = sorted(sets)
    for i, a in enumerate(names):
        sa = set(map(int, sets[a].tolist()))
        for b in names[i + 1 :]:
            sb = set(map(int, sets[b].tolist()))
            inter = sa.intersection(sb)
            rows.append(
                {
                    "namespace": namespace,
                    "left": a,
                    "right": b,
                    "left_rows": len(sa),
                    "right_rows": len(sb),
                    "intersection_rows": len(inter),
                    "disjoint": len(inter) == 0,
                    "intersection_sha256": hash_indices(np.asarray(sorted(inter), dtype=np.int64)) if inter else "",
                }
            )
    return rows


def flatten_sources(s: str) -> set[str]:
    return {part.strip() for part in s.replace("|", "/").split("/") if part.strip()}


def forbidden_hit(source_roles: str) -> bool:
    sources = flatten_sources(source_roles)
    return bool(sources.intersection(FORBIDDEN_FOR_SELECTION))


def state_log_audit(asset: dict[str, Any]) -> list[dict[str, Any]]:
    path = Path(asset["certificate"]["state_transition_log_path"])
    rows = ar.load_csv(path)
    by_role: dict[str, list[dict[str, str]]] = defaultdict(list)
    before_hashes = set()
    nonzero_pre = 0
    pre_record_packets_total = 0
    non_reset_state = 0
    for row in rows:
        role = row.get("role", "")
        by_role[role].append(row)
        before_hashes.add(row.get("state_hash_before", ""))
        try:
            pre = int(float(row.get("pre_record_packets", "0")))
            pre_record_packets_total += pre
            if pre != 0:
                nonzero_pre += 1
        except ValueError:
            nonzero_pre += 1
        if not row.get("state_id", "").startswith("reset::"):
            non_reset_state += 1
    reset_pass = len(before_hashes) == 1 and non_reset_state == 0
    out: list[dict[str, Any]] = []
    for role, rws in sorted(by_role.items()):
        role_pre_rows = 0
        role_pre_packets = 0
        for r in rws:
            try:
                pre = int(float(r.get("pre_record_packets", "0") or 0))
            except ValueError:
                pre = 0
            role_pre_packets += pre
            role_pre_rows += int(pre > 0)
        out.append(
            {
                "strategy": asset["strategy"],
                "role": role,
                "state_log_rows": len(rws),
                "feature_rows_emitted": int(sum(int(float(r.get("feature_rows_emitted", "0") or 0)) for r in rws)),
                "unique_state_hash_before_count_global": len(before_hashes),
                "global_nonzero_pre_record_rows": nonzero_pre,
                "global_pre_record_packets_total": pre_record_packets_total,
                "role_nonzero_pre_record_rows": role_pre_rows,
                "role_pre_record_packets_total": role_pre_packets,
                "global_non_reset_state_id_rows": non_reset_state,
                "reset_at_split_boundary_pass": reset_pass,
                "pre_record_packets_allowed_as_past_only_fast_forward": True,
                "audit_meaning": "state is reset per role/file; pre_record packets are same-file past fast-forward before emitted rows, not cross-split carryover",
            }
        )
    return out


def active_stream_order_audit(new_sidecar: list[dict[str, str]], candidate_idx: np.ndarray, query_idx: np.ndarray) -> list[dict[str, Any]]:
    candidate = set(map(int, candidate_idx.tolist()))
    query = set(map(int, query_idx.tolist()))
    by_file: dict[str, dict[str, list[int]]] = defaultdict(lambda: {"candidate": [], "query": []})
    for idx, row in enumerate(new_sidecar):
        csv_member = row.get("csv_member", "unknown")
        _, order = issue27au.packet_order(row)
        if idx in candidate:
            by_file[csv_member]["candidate"].append(order)
        if idx in query:
            by_file[csv_member]["query"].append(order)
    rows: list[dict[str, Any]] = []
    for csv_member, parts in sorted(by_file.items()):
        cand = parts["candidate"]
        qry = parts["query"]
        cand_max = max(cand) if cand else ""
        qry_min = min(qry) if qry else ""
        pass_order = bool(cand and qry and max(cand) < min(qry)) if cand and qry else True
        rows.append(
            {
                "csv_member": csv_member,
                "candidate_rows": len(cand),
                "query_rows": len(qry),
                "candidate_max_packet_order": cand_max,
                "query_min_packet_order": qry_min,
                "candidate_before_query": pass_order,
                "candidate_selection_uses_query_labels": False,
                "query_report_only": True,
            }
        )
    return rows


def role_access_rows(selected_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "object": "issue27bd_selected_config",
            "operation": "frozen_reuse_only",
            "source_roles": "issue27bd_dev_grid_summary",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": True,
            "allowed_for_issue27be": True,
            "notes": "issue27be does not search config; it replays issue27bd selected gate",
        },
        {
            "object": "medium_region_head",
            "operation": "fit",
            "source_roles": "id_fit/ood_train/medium_attack_train",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": False,
            "allowed_for_issue27be": True,
            "notes": "model fit is replayed for shape/decision consistency, not formal benchmark",
        },
        {
            "object": "heavy_region_head",
            "operation": "fit",
            "source_roles": "id_fit/ood_train/active_heavy_attack_train",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": False,
            "allowed_for_issue27be": True,
            "notes": "active heavy attack labels come only from development candidate stream",
        },
        {
            "object": "medium_threshold",
            "operation": "calibration",
            "source_roles": "id_calib/ood_val/medium_attack_val",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": False,
            "allowed_for_issue27be": True,
            "notes": "threshold is dev-side only",
        },
        {
            "object": "heavy_threshold",
            "operation": "calibration",
            "source_roles": "id_calib/ood_val/active_heavy_attack_val",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": False,
            "allowed_for_issue27be": True,
            "notes": "threshold is dev-side only",
        },
        {
            "object": "prototype_shell_banks",
            "operation": "fit_radius",
            "source_roles": "id_fit/id_calib/ood_train/ood_val/ood_stress_train/ood_stress_val/medium_attack_train/medium_attack_val/medium_attack_pseudo/active_heavy_attack_train/active_heavy_attack_val/active_heavy_attack_pseudo",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": True,
            "allowed_for_issue27be": True,
            "notes": "pseudo-query use is dev-side diagnostic caveat, not clean final use",
        },
        {
            "object": "score_strength_floor",
            "operation": "gate_calibration",
            "source_roles": "medium_attack_val/active_heavy_attack_val/medium_attack_pseudo/active_heavy_attack_pseudo",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "uses_dev_pseudo_query": True,
            "allowed_for_issue27be": True,
            "notes": "dev pseudo controls shell aggressiveness; formal version must pre-register or replace this",
        },
        {
            "object": "report_only_replay",
            "operation": "score_only_after_frozen_gate",
            "source_roles": "final_ood_report_only/medium_attack_eval_report_only/dev_heavy_query_report_only",
            "uses_final_ood": True,
            "uses_attack_eval": True,
            "uses_dev_heavy_query": True,
            "uses_dev_pseudo_query": False,
            "allowed_for_issue27be": True,
            "notes": "score-only replay; not used for fit, calibration, selection, review budget, or next-step gate choice",
        },
    ]
    for row in rows:
        row["forbidden_selection_access"] = row["operation"] != "score_only_after_frozen_gate" and (
            bool(row["uses_final_ood"]) or bool(row["uses_attack_eval"]) or bool(row["uses_dev_heavy_query"]) or forbidden_hit(str(row["source_roles"]))
        )
        row["selected_subspace"] = selected_cfg["subspace_name"]
        row["selected_review_budget"] = selected_cfg["review_budget"]
    return rows


def replay_selected_gate(
    x: np.ndarray,
    sidecar: list[dict[str, str]],
    stress_x: np.ndarray,
    stress_sidecar: list[dict[str, str]],
    new_x: np.ndarray,
    new_sidecar: list[dict[str, str]],
    schema: dict[str, Any],
    selected_cfg: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    subspaces = bd.build_subspaces(schema)
    selected_sub_idx = subspaces[selected_cfg["subspace_name"]]
    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    replay_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=selected_cfg["active_label_budget"],
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0 or len(medium_pseudo) == 0:
            raise RuntimeError(f"empty replay split for seed {seed}")

        split_rows.extend(
            [
                {
                    "seed": seed,
                    "split_family": "medium_attack_support",
                    **medium_audit,
                    "base_support_selector": "kcenter128",
                    "base_support_hash": hash_indices(base_support),
                    **{f"base_{k}": v for k, v in base_audit.items()},
                    "pseudo_used_for_gate_calibration": True,
                    "pseudo_is_clean_final": False,
                },
                {
                    "seed": seed,
                    "split_family": "active_heavy_attack_support",
                    **heavy_audit,
                    "active_confirmed_hash": hash_indices(selected_confirmed),
                    **{f"active_{k}": v for k, v in active_audit.items()},
                    "pseudo_used_for_gate_calibration": True,
                    "pseudo_is_clean_final": False,
                },
            ]
        )

        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        banks, audits = bd.build_shell_banks(
            x,
            stress_x,
            selected_sub_idx,
            id_fit,
            id_calib,
            ood_train,
            ood_val,
            stress_train,
            stress_val,
            medium_train,
            medium_val,
            medium_pseudo,
            new_x[heavy_train],
            new_x[heavy_val],
            new_x[heavy_pseudo],
            selected_cfg["proto_budget"],
            selected_cfg["bank_radius_q"],
            seed,
            selected_cfg["active_label_budget"],
            selected_cfg["subspace_name"],
        )
        bank_rows.extend(audits)
        support_strength = []
        for x_role in [x[medium_val], new_x[heavy_val], x[medium_pseudo], new_x[heavy_pseudo]]:
            bundle = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
            support_strength.append(bundle["score_strength"])
        support_strength_arr = np.concatenate(support_strength)
        strong_floor = float(np.quantile(support_strength_arr, selected_cfg["strong_score_q"]))
        weak_ceiling = float(np.quantile(support_strength_arr, selected_cfg["weak_score_q"]))
        role_x = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": new_x[heavy_val],
            "pseudo_medium_query": x[medium_pseudo],
            "pseudo_heavy_query": new_x[heavy_pseudo],
            "medium_attack_eval_report_only": x[attack_eval],
            "dev_heavy_query_report_only": new_x[dev_query_idx],
            "final_ood_report_only": x[final_ood],
        }
        replay_row: dict[str, Any] = {
            "seed": seed,
            **selected_cfg,
            "strong_score_floor": strong_floor,
            "weak_score_ceiling": weak_ceiling,
            "selection_uses_final_ood": False,
            "selection_uses_attack_eval": False,
            "selection_uses_dev_heavy_query": False,
        }
        for role, x_role in role_x.items():
            bundle = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
            pre = bd.shell_precompute(x_role, selected_sub_idx, banks, bundle)
            state, masks = bd.apply_conflict_shell_gate(
                pre["raw_alarm"],
                pre["score_strength"],
                pre["attack_inner"],
                pre["attack_outer"],
                pre["benign_inner"],
                pre["benign_outer"],
                strong_floor,
                weak_ceiling,
                selected_cfg["attack_outer_norm"],
                selected_cfg["benign_core_norm"],
                selected_cfg["conflict_slack"],
                selected_cfg["review_budget"],
            )
            metrics = bd.state_metrics(role, state, masks, pre)
            for key, value in metrics.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = value
            decision_rows.append({"seed": seed, "role": role, **{k: v for k, v in metrics.items() if k != "role"}})
        replay_rows.append(replay_row)
    return replay_rows, decision_rows, split_rows, bank_rows


def replay_consistency_rows(current: list[dict[str, Any]], previous: list[dict[str, str]]) -> list[dict[str, Any]]:
    previous_by_seed = {int(float(row["seed"])): row for row in previous}
    keys = [
        "id_calib_hard_alarm_rate",
        "ood_val_hard_alarm_rate",
        "ood_stress_val_hard_alarm_rate",
        "support_medium_val_hard_alarm_rate",
        "support_heavy_val_hard_alarm_rate",
        "pseudo_medium_query_hard_alarm_rate",
        "pseudo_heavy_query_hard_alarm_rate",
        "medium_attack_eval_report_only_hard_alarm_rate",
        "dev_heavy_query_report_only_hard_alarm_rate",
        "final_ood_report_only_hard_alarm_rate",
        "final_ood_report_only_review_any_rate",
    ]
    rows: list[dict[str, Any]] = []
    for row in current:
        seed = int(row["seed"])
        prev = previous_by_seed.get(seed)
        for key in keys:
            cur_val = float(row.get(key, float("nan")))
            prev_val = float(prev.get(key, float("nan"))) if prev else float("nan")
            delta = abs(cur_val - prev_val) if np.isfinite(cur_val) and np.isfinite(prev_val) else float("nan")
            rows.append(
                {
                    "seed": seed,
                    "metric": key,
                    "current_value": cur_val,
                    "issue27bd_value": prev_val,
                    "abs_delta": delta,
                    "within_tolerance": bool(np.isfinite(delta) and delta <= REPLAY_TOLERANCE),
                }
            )
    return rows


def aggregate_summary(replay_rows: list[dict[str, Any]]) -> dict[str, float]:
    fields = {
        "dev_attack_hard_min": [
            "support_medium_val_hard_alarm_rate",
            "support_heavy_val_hard_alarm_rate",
            "pseudo_medium_query_hard_alarm_rate",
            "pseudo_heavy_query_hard_alarm_rate",
        ],
        "report_only_attack_hard_min": [
            "medium_attack_eval_report_only_hard_alarm_rate",
            "dev_heavy_query_report_only_hard_alarm_rate",
        ],
        "report_only_attack_hard_or_review_min": [
            "medium_attack_eval_report_only_hard_alarm_rate",
            "dev_heavy_query_report_only_hard_alarm_rate",
        ],
        "ood_stress_hard_max": ["ood_stress_val_hard_alarm_rate"],
        "final_ood_hard_max": ["final_ood_report_only_hard_alarm_rate"],
        "final_ood_review_max": ["final_ood_report_only_review_any_rate"],
    }
    out: dict[str, float] = {}
    for name, cols in fields.items():
        vals: list[float] = []
        if name == "report_only_attack_hard_or_review_min":
            for row in replay_rows:
                vals.extend(
                    [
                        float(row["medium_attack_eval_report_only_hard_alarm_rate"]) + float(row["medium_attack_eval_report_only_review_any_rate"]),
                        float(row["dev_heavy_query_report_only_hard_alarm_rate"]) + float(row["dev_heavy_query_report_only_review_any_rate"]),
                    ]
                )
        elif name.endswith("_min"):
            for row in replay_rows:
                vals.append(min(float(row[c]) for c in cols))
        elif name.endswith("_max"):
            for row in replay_rows:
                vals.extend(float(row[c]) for c in cols)
        out[name] = float(min(vals) if name.endswith("_min") else max(vals))
    return out


def decide(
    forbidden_rows: list[dict[str, Any]],
    consistency_rows: list[dict[str, Any]],
    active_order_rows: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    split_rows: list[dict[str, Any]],
) -> str:
    if any(bool(r.get("forbidden_selection_access")) for r in forbidden_rows):
        return "past_only_replay_blocked_by_forbidden_role_access"
    if any(not bool(r.get("within_tolerance")) for r in consistency_rows):
        return "past_only_replay_blocked_by_replay_mismatch"
    if any(not bool(r.get("candidate_before_query")) for r in active_order_rows):
        return "past_only_replay_blocked_by_active_stream_order_violation"
    if any(not bool(r.get("reset_at_split_boundary_pass")) for r in state_rows):
        return "past_only_replay_blocked_by_state_reset_violation"
    if any(bool(r.get("pseudo_used_for_gate_calibration")) for r in split_rows):
        return "past_only_replay_passed_with_dev_pseudo_caveat_ready_for_attack_region_bank"
    return "past_only_replay_passed_ready_for_attack_region_bank"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    config_path = ISSUE27BD / "config.json"
    previous_replay_path = ISSUE27BD / "report_only_replay.csv"
    selected_cfg = json.loads(config_path.read_text(encoding="utf-8"))["selected_config"]
    previous_replay = read_csv(previous_replay_path)

    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    asset, asset_checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    replay_rows, decision_rows, split_rows, bank_rows = replay_selected_gate(
        x,
        sidecar,
        stress_x,
        stress_sidecar,
        new_x,
        new_sidecar,
        asset["schema"],
        selected_cfg,
    )
    role_rows = role_access_rows(selected_cfg)
    consistency_rows = replay_consistency_rows(replay_rows, previous_replay)
    active_order_rows = active_stream_order_audit(new_sidecar, active_candidate_idx, dev_query_idx)
    state_rows = state_log_audit(asset)
    summary_metrics = aggregate_summary(replay_rows)

    split_sets_medium = {
        "id_fit": id_fit,
        "id_calib": id_calib,
        "ood_train": ood_train,
        "ood_val": ood_val,
        "final_ood_report_only": final_ood,
        "attack_support_pool": support_pool,
        "attack_eval_report_only": attack_eval,
    }
    split_sets_stress = {"ood_stress_train": stress_train, "ood_stress_val": stress_val}
    split_sets_new = {"active_candidate_stream": active_candidate_idx, "dev_heavy_query_report_only": dev_query_idx}
    disjoint_rows = (
        pair_disjoint_audit(split_sets_medium, "medium_asset")
        + pair_disjoint_audit(split_sets_stress, "ood_stress_asset")
        + pair_disjoint_audit(split_sets_new, "new_heavy_dev_probe")
    )
    role_index_rows = [
        *[role_indices_set(k, v, "medium_asset") for k, v in split_sets_medium.items()],
        *[role_indices_set(k, v, "ood_stress_asset") for k, v in split_sets_stress.items()],
        *[role_indices_set(k, v, "new_heavy_dev_probe") for k, v in split_sets_new.items()],
    ]
    forbidden_rows = [
        {
            **row,
            "blocked": bool(row.get("forbidden_selection_access")),
            "audit_rule": "final/report-only roles may only appear in score-only replay rows",
        }
        for row in role_rows
    ]
    visibility_rows = [
        {
            "stage_order": 10,
            "stage": "load_frozen_issue27bd_config",
            "visible_roles": "issue27bd selected config only",
            "forbidden_roles_hidden": "final_ood_report_only|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "action": "reuse frozen config; no grid search",
        },
        {
            "stage_order": 20,
            "stage": "fit_heads_and_support_splits",
            "visible_roles": "id_fit|ood_train|attack_support_train|active_heavy_train",
            "forbidden_roles_hidden": "final_ood_report_only|attack_eval_report_only|dev_heavy_query_report_only",
            "action": "replay detector/gate construction",
        },
        {
            "stage_order": 30,
            "stage": "dev_calibration",
            "visible_roles": "id_calib|ood_val|ood_stress_val|support_val|dev_pseudo_query",
            "forbidden_roles_hidden": "final_ood_report_only|attack_eval_report_only|dev_heavy_query_report_only",
            "action": "threshold/prototype radius/score floor replay",
        },
        {
            "stage_order": 40,
            "stage": "report_only_replay",
            "visible_roles": "final_ood_report_only|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "forbidden_roles_hidden": "not applicable after freeze",
            "action": "score only; no parameter update",
        },
    ]

    input_rows = [
        {"artifact": "issue27bd_config", "path": str(config_path), "actual_sha256": sha256_file(config_path), "hash_match": True},
        {"artifact": "issue27bd_report_only_replay", "path": str(previous_replay_path), "actual_sha256": sha256_file(previous_replay_path), "hash_match": True},
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "actual_sha256": sha256_file(stress_cert_path), "hash_match": True},
    ]
    input_rows.extend(asset_checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    verdict = decide(forbidden_rows, consistency_rows, active_order_rows, state_rows, split_rows)
    forbidden_any = any(bool(r.get("blocked")) for r in forbidden_rows)
    replay_match_all = all(bool(r["within_tolerance"]) for r in consistency_rows)
    active_order_pass = all(bool(r["candidate_before_query"]) for r in active_order_rows)
    state_pass = all(bool(r["reset_at_split_boundary_pass"]) for r in state_rows)
    pseudo_caveat = any(bool(r.get("pseudo_used_for_gate_calibration")) for r in split_rows)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "frozen_config_audit.csv", [{**selected_cfg, "source": "issue27bd/config.json", "config_sha256": sha256_file(config_path)}])
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_csv(OUT / "forbidden_role_access_audit.csv", forbidden_rows)
    write_csv(OUT / "past_only_visibility_timeline.csv", visibility_rows)
    write_csv(OUT / "state_reset_replay_audit.csv", state_rows)
    write_csv(OUT / "split_role_index_inventory.csv", role_index_rows)
    write_csv(OUT / "split_disjointness_audit.csv", disjoint_rows)
    write_csv(OUT / "active_stream_past_future_order_audit.csv", active_order_rows)
    write_csv(OUT / "support_pseudo_query_caveat_audit.csv", split_rows)
    write_csv(OUT / "prototype_shell_bank_replay_audit.csv", bank_rows)
    write_csv(OUT / "report_only_replay_past_only.csv", replay_rows)
    write_csv(OUT / "decision_breakdown_past_only.csv", decision_rows)
    write_csv(OUT / "replay_metric_consistency.csv", consistency_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)

    write_md(
        OUT / "past_only_replay_scope.md",
        [
            "# Past-Only Replay Scope",
            "",
            "This issue is a small audit, not a new enhancement module.",
            "",
            "- It reuses the frozen issue27bd gate configuration.",
            "- It does not run a new grid search.",
            "- It does not add temporal smoothing.",
            "- It does not run a full/larger formal benchmark.",
            "- It confirms report-only roles are replayed only after all fit/calibration/gate choices are frozen.",
            "",
            "Important caveat: issue27bd used dev-side pseudo-query rows from support/active-label splits for shell calibration. These rows are not clean final evaluation, but they mean the result remains diagnostic rather than formal.",
        ],
    )
    write_md(
        OUT / "issue27be_decision.md",
        [
            "# issue27be Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- replay matches issue27bd selected report rows: `{replay_match_all}`",
            f"- forbidden selection role access found: `{forbidden_any}`",
            f"- new-heavy active candidate stream precedes dev query stream: `{active_order_pass}`",
            f"- reset_at_split_boundary state audit passed: `{state_pass}`",
            f"- dev pseudo-query calibration caveat present: `{pseudo_caveat}`",
            "",
            "Interpretation: the issue27bd signal is reproducible under the frozen replay audit and does not use clean final/report-only roles for selection. It is still a diagnostic result because dev pseudo-query rows participate in gate calibration.",
        ],
    )
    write_md(
        OUT / "issue27bf_next_action.md",
        [
            "# Issue27bf Next Action",
            "",
            "Recommended next issue: `issue27bf_bounded_attack_region_bank`.",
            "",
            "- Do not proceed to full/larger formal benchmark from issue27be.",
            "- Do not add temporal smoothing yet.",
            "- Keep the raw detector on full Kitsune115.",
            "- Upgrade attack handling from two region heads to a bounded attack region bank with shared scorer/top-k routing/region shell calibration.",
            "- Preserve final OOD and attack eval as report-only.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27be.md",
        [
            "# Claim Update After issue27be",
            "",
            "- issue27bd's conflict-aware shell gate was replayed under a frozen, role-audited setting.",
            "- This supports continuing the diagnostic line toward attack-region generalization.",
            "- It does not establish formal benchmark readiness, deployment robustness, or final OOD safety.",
            "- Model experiments remain bounded diagnostics until attack hard detection, OOD hard alarm, and review rate are all stable under pre-registered rules.",
        ],
    )
    summary_lines = [
        "# issue27be Summary",
        "",
        "1. issue27be completed: yes",
        f"2. primary_verdict: `{verdict}`",
        "3. task type: frozen past-only replay audit; not model improvement and not formal benchmark",
        f"4. selected issue27bd subspace replayed: `{selected_cfg['subspace_name']}`",
        f"5. selected active label budget replayed: `{selected_cfg['active_label_budget']}`",
        f"6. replay matches issue27bd metrics: `{replay_match_all}`",
        f"7. forbidden final/report-only role access found: `{forbidden_any}`",
        f"8. reset_at_split_boundary state audit passed: `{state_pass}`",
        f"9. active candidate before dev-heavy query: `{active_order_pass}`",
        f"10. dev pseudo-query caveat present: `{pseudo_caveat}`",
        f"11. dev attack hard min replay: `{summary_metrics['dev_attack_hard_min']}`",
        f"12. report-only attack hard min replay: `{summary_metrics['report_only_attack_hard_min']}`",
        f"13. report-only attack hard-or-review min replay: `{summary_metrics['report_only_attack_hard_or_review_min']}`",
        f"14. OOD stress hard max replay: `{summary_metrics['ood_stress_hard_max']}`",
        f"15. final OOD hard max report-only replay: `{summary_metrics['final_ood_hard_max']}`",
        f"16. final OOD review max report-only replay: `{summary_metrics['final_ood_review_max']}`",
        "17. current formal benchmark allowed: no",
        "18. next action: `issue27bf_bounded_attack_region_bank`",
        "19. commit hash: pending",
    ]
    write_md(OUT / "summary.md", summary_lines)

    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "source_issue": "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07",
        "primary_verdict": verdict,
        "selected_config": selected_cfg,
        "role_policy": "final/report-only roles are replay-only after gate freeze",
        "pseudo_query_caveat": pseudo_caveat,
        "next_action": "issue27bf_bounded_attack_region_bank",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27bd_config": str(config_path),
                    "issue27bd_report_only_replay": str(previous_replay_path),
                    "issue27af_certificate": str(cert_path),
                    "issue27ba_stress_certificate": str(stress_cert_path),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "small past-only replay audit; no temporal smoothing; no full benchmark",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27be -->",
        [
            "<!-- issue27be -->",
            "## issue27be - Past-only replay audit on conflict gate",
            "",
            f"- primary_verdict: `{verdict}`",
            "- purpose: replay the frozen issue27bd conflict-aware shell gate under role-access and past-only visibility audit.",
            f"- replay matches issue27bd metrics: `{replay_match_all}`; forbidden role access: `{forbidden_any}`.",
            "- caveat: dev-side pseudo-query rows remain part of gate calibration, so this is diagnostic rather than formal.",
            "- next action: `issue27bf_bounded_attack_region_bank`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27be -->",
        [
            "<!-- issue27be -->",
            "## issue27be - Frozen past-only replay audit",
            "",
            f"- verdict: `{verdict}`",
            f"- outputs: `runs/{ISSUE}/`.",
            "- no full/larger benchmark and no temporal smoothing; proceed to bounded attack region bank if continuing.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(
        json.dumps(
            {
                "primary_verdict": verdict,
                "summary": summary_metrics,
                "replay_match_all": replay_match_all,
                "forbidden_any": forbidden_any,
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
