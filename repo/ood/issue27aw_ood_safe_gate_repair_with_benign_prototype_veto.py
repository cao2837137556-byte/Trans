from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27av_prototype_aware_triage_and_ood_tail_attribution as issue27av


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27aw_ood_safe_gate_repair_with_benign_prototype_veto_2026-06-04"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AU = ROOT / "runs" / "issue27au_coverage_aware_active_labeling_viability_diagnostic_2026-06-04"
ISSUE27AV = ROOT / "runs" / "issue27av_prototype_aware_triage_and_ood_tail_attribution_2026-06-04"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_BUDGET = 16
SUPPORT_BUDGET = 128
OOD_WEIGHT = 2.0
SUPPORT_WEIGHT = 4.0
VAL_TARGET = 0.01

ID_PROTOTYPES = 64
OOD_PROTOTYPES = 64
ATTACK_PROTOTYPES = 64

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
DEV_QUERY_ROLE = issue27au.DEV_QUERY_ROLE


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if marker in text:
        return
    path.write_text(text.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def label_is_attack(row: dict[str, str]) -> bool:
    return (row.get("binary_label_from_alignment") or row.get("label") or "").lower() == "attack"


def rate_bool(x: np.ndarray) -> float:
    return float(np.mean(x.astype(bool))) if x.size else float("nan")


def summarize_values(vals: np.ndarray) -> dict[str, float]:
    vals = np.asarray(vals, dtype=np.float64)
    if vals.size == 0:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan")}
    return {"mean": float(np.mean(vals)), "min": float(np.min(vals)), "max": float(np.max(vals))}


def candidate_margins(*arrays: np.ndarray) -> list[float]:
    vals = np.concatenate([np.asarray(a, dtype=np.float64) for a in arrays if len(a)])
    if vals.size == 0:
        return [0.0]
    qs = np.linspace(0.0, 1.0, 101)
    margins = np.unique(np.concatenate([[0.0], np.quantile(vals, qs)]))
    return sorted(float(x) for x in margins)


def build_features_for_rows(
    x_rows: np.ndarray,
    scores: np.ndarray,
    threshold: float,
    scaler: StandardScaler,
    id_proto_z: np.ndarray,
    ood_proto_z: np.ndarray,
    attack_proto_z: np.ndarray,
    r_id: float,
    r_ood: float,
    r_attack: float,
) -> dict[str, np.ndarray]:
    z = scaler.transform(x_rows)
    d_id = issue27av.nearest_dist(z, id_proto_z)
    d_ood = issue27av.nearest_dist(z, ood_proto_z)
    d_attack = issue27av.nearest_dist(z, attack_proto_z)
    min_benign = np.minimum(d_id, d_ood)
    id_cov = d_id <= r_id
    ood_cov = d_ood <= r_ood
    benign_cov = id_cov | ood_cov
    attack_cov = d_attack <= r_attack
    attack_distance_advantage = min_benign - d_attack
    return {
        "score": np.asarray(scores, dtype=np.float64),
        "base_alarm": np.asarray(scores, dtype=np.float64) > float(threshold),
        "d_id": d_id,
        "d_ood": d_ood,
        "d_attack": d_attack,
        "id_covered": id_cov,
        "ood_covered": ood_cov,
        "benign_covered": benign_cov,
        "attack_covered": attack_cov,
        "attack_distance_advantage": attack_distance_advantage,
        "benign_advantage": d_attack - min_benign,
    }


def apply_gate(feat: dict[str, np.ndarray], gate_name: str, margin: float = 0.0) -> dict[str, np.ndarray]:
    base = feat["base_alarm"].astype(bool)
    benign = feat["benign_covered"].astype(bool)
    attack = feat["attack_covered"].astype(bool)
    adv = feat["attack_distance_advantage"]
    if gate_name == "baseline_no_veto":
        hard_alarm = base.copy()
        needs_review = np.zeros_like(base, dtype=bool)
        suppressed = np.zeros_like(base, dtype=bool)
    elif gate_name == "benign_prototype_veto_v1":
        suppress = base & benign & (~attack)
        hard_alarm = base & (~suppress)
        needs_review = np.zeros_like(base, dtype=bool)
        suppressed = suppress
    elif gate_name == "conflict_review_v1":
        conflict = base & benign & attack
        suppress = base & benign & (~attack)
        hard_alarm = base & (~suppress) & (~conflict)
        needs_review = conflict
        suppressed = suppress
    elif gate_name == "attack_advantage_zero_v1":
        suppress = base & benign & (adv <= 0.0)
        hard_alarm = base & (~suppress)
        needs_review = np.zeros_like(base, dtype=bool)
        suppressed = suppress
    elif gate_name == "attack_advantage_margin_dev_v1":
        suppress = base & benign & (adv < float(margin))
        hard_alarm = base & (~suppress)
        needs_review = np.zeros_like(base, dtype=bool)
        suppressed = suppress
    else:
        raise ValueError(f"unknown gate: {gate_name}")
    return {
        "hard_alarm": hard_alarm,
        "needs_review": needs_review,
        "suppressed_by_gate": suppressed,
        "attention": hard_alarm | needs_review,
    }


def gate_metrics(action: dict[str, np.ndarray]) -> dict[str, float]:
    return {
        "hard_alarm_rate": rate_bool(action["hard_alarm"]),
        "needs_review_rate": rate_bool(action["needs_review"]),
        "suppressed_rate": rate_bool(action["suppressed_by_gate"]),
        "operational_attention_rate": rate_bool(action["attention"]),
    }


def evaluate_candidate(
    gate_name: str,
    margin: float,
    features_by_role: dict[str, dict[str, np.ndarray]],
    seed: int,
) -> dict[str, Any]:
    row: dict[str, Any] = {"seed": seed, "gate_name": gate_name, "margin": float(margin)}
    for role, feat in features_by_role.items():
        action = apply_gate(feat, gate_name, margin)
        metrics = gate_metrics(action)
        row[f"{role}_hard_alarm_rate"] = metrics["hard_alarm_rate"]
        row[f"{role}_needs_review_rate"] = metrics["needs_review_rate"]
        row[f"{role}_suppressed_rate"] = metrics["suppressed_rate"]
        row[f"{role}_operational_attention_rate"] = metrics["operational_attention_rate"]
    row["dev_ood_safe"] = (
        row["id_calib_hard_alarm_rate"] <= VAL_TARGET
        and row["ood_val_hard_alarm_rate"] <= VAL_TARGET
        and row["id_calib_operational_attention_rate"] <= VAL_TARGET
        and row["ood_val_operational_attention_rate"] <= VAL_TARGET
    )
    row["support_preservation"] = row["support_val_hard_alarm_rate"]
    return row


def select_gate_for_seed(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    feasible = [r for r in candidates if bool(r["dev_ood_safe"])]
    pool = feasible if feasible else candidates
    # Choose only from development roles: preserve support_val attack while keeping
    # ID/OOD attention low. Final/query roles are absent from this table.
    def key(r: dict[str, Any]) -> tuple[float, float, float, float, float]:
        return (
            float(r["support_val_hard_alarm_rate"]),
            -float(r["ood_val_operational_attention_rate"]),
            -float(r["id_calib_operational_attention_rate"]),
            float(r["support_val_suppressed_rate"]) * -1.0,
            -float(r["margin"]),
        )

    best = max(pool, key=key).copy()
    best["selected_by"] = "dev_only_max_support_val_detection_subject_to_id_ood_attention_1pct"
    best["selected_from_feasible_pool"] = bool(feasible)
    return best


def aggregate_selected(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["role"]].append(row)
    out: list[dict[str, Any]] = []
    for role, gr in sorted(groups.items()):
        out_row: dict[str, Any] = {"role": role, "seeds": len(gr)}
        for metric in [
            "before_hard_alarm_rate",
            "after_hard_alarm_rate",
            "after_needs_review_rate",
            "after_operational_attention_rate",
            "after_suppressed_rate",
        ]:
            stats = summarize_values(np.asarray([float(r[metric]) for r in gr], dtype=np.float64))
            for stat_name, value in stats.items():
                out_row[f"{metric}_{stat_name}"] = value
        out.append(out_row)
    return out


def aggregate_named_replay(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["gate_label"], row["role"])].append(row)
    out: list[dict[str, Any]] = []
    for (gate_label, role), gr in sorted(groups.items()):
        out_row: dict[str, Any] = {"gate_label": gate_label, "role": role, "seeds": len(gr)}
        for metric in [
            "hard_alarm_rate",
            "needs_review_rate",
            "operational_attention_rate",
            "suppressed_rate",
        ]:
            stats = summarize_values(np.asarray([float(r[metric]) for r in gr], dtype=np.float64))
            for stat_name, value in stats.items():
                out_row[f"{metric}_{stat_name}"] = value
        out.append(out_row)
    return out


def find_named(summary_rows: list[dict[str, Any]], gate_label: str, role: str) -> dict[str, Any]:
    return next((r for r in summary_rows if r["gate_label"] == gate_label and r["role"] == role), {})


def pick_verdict(summary_rows: list[dict[str, Any]], named_summary_rows: list[dict[str, Any]]) -> tuple[str, dict[str, float]]:
    by_role = {r["role"]: r for r in summary_rows}
    final = by_role.get("final_ood_benign_eval_report_only", {})
    dev = by_role.get("dev_heavy_query_report_only", {})
    medium = by_role.get("medium_attack_eval_report_only", {})
    final_attention = float(final.get("after_operational_attention_rate_max", float("nan")))
    final_hard = float(final.get("after_hard_alarm_rate_max", float("nan")))
    dev_det_min = float(dev.get("after_hard_alarm_rate_min", float("nan")))
    medium_det_min = float(medium.get("after_hard_alarm_rate_min", float("nan")))
    stats = {
        "final_ood_after_hard_alarm_max": final_hard,
        "final_ood_after_attention_max": final_attention,
        "dev_heavy_after_detection_min": dev_det_min,
        "medium_attack_after_detection_min": medium_det_min,
    }
    fixed_final = find_named(named_summary_rows, "fixed_benign_prototype_veto_v1", "final_ood_benign_eval_report_only")
    fixed_dev = find_named(named_summary_rows, "fixed_benign_prototype_veto_v1", "dev_heavy_query_report_only")
    fixed_medium = find_named(named_summary_rows, "fixed_benign_prototype_veto_v1", "medium_attack_eval_report_only")
    fixed_final_hard = float(fixed_final.get("hard_alarm_rate_max", float("nan")))
    fixed_dev_det = float(fixed_dev.get("hard_alarm_rate_min", float("nan")))
    fixed_medium_det = float(fixed_medium.get("hard_alarm_rate_min", float("nan")))
    stats.update(
        {
            "fixed_veto_final_ood_hard_alarm_max": fixed_final_hard,
            "fixed_veto_dev_heavy_detection_min": fixed_dev_det,
            "fixed_veto_medium_attack_detection_min": fixed_medium_det,
        }
    )
    if final_hard > VAL_TARGET and fixed_final_hard <= VAL_TARGET and min(fixed_dev_det, fixed_medium_det) < 0.75:
        return "benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged", stats
    if final_hard > VAL_TARGET:
        return "benign_prototype_veto_insufficient_final_ood_tail_persists", stats
    if final_attention > VAL_TARGET:
        return "benign_prototype_veto_reduces_hard_alarm_but_review_cost_high", stats
    if min(dev_det_min, medium_det_min) < 0.75:
        return "benign_prototype_veto_ood_safe_but_attack_signal_too_damaged", stats
    return "benign_prototype_veto_candidate_supported_needs_clean_final_replay", stats


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = read_csv(ar.NEW_HELDOUT_SIDECAR)

    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ID_ROLE)
    ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    active_candidate_idx, dev_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27av_summary", "path": str(ISSUE27AV / "summary.md"), "sha256": sha256_file(ISSUE27AV / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(checks)
    input_hash_rows.extend(new_checks)

    gate_candidate_rows: list[dict[str, Any]] = []
    selected_gate_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    named_replay_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    prototype_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, SUPPORT_BUDGET)
        base_train, base_val = issue27as.split_support(base_support, seed)
        selected_local, sel_audit = issue27au.select_active_labels(
            x_base_support=x[base_train],
            x_support_val=x[base_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_BUDGET,
        )
        confirmed_attack = np.asarray([i for i in selected_local if label_is_attack(new_sidecar[int(i)])], dtype=np.int64)
        x_support_aug = np.vstack([x[base_train], new_x[confirmed_attack]]) if len(confirmed_attack) else x[base_train]

        model = issue27as.WeightedOldHistGB(seed, OOD_WEIGHT, SUPPORT_WEIGHT)
        model.fit(x[id_fit], x[ood_train], x_support_aug)
        score_id = model.score(x[id_calib])
        score_ood = model.score(x[ood_val])
        score_support_val = model.score(x[base_val])
        threshold_info = issue27as.orderstat_threshold(score_id, score_ood, score_support_val)
        threshold = float(threshold_info["threshold"])

        scaler_source = np.concatenate([id_fit, ood_train, base_train])
        scaler = StandardScaler().fit(x[scaler_source])
        z_all = scaler.transform(x)
        z_new = scaler.transform(new_x)
        id_proto = issue27av.kcenter_from_global_z(z_all, id_fit, ID_PROTOTYPES)
        ood_proto = issue27av.kcenter_from_global_z(z_all, ood_train, OOD_PROTOTYPES)
        z_attack_source = np.vstack([z_all[base_train], z_new[confirmed_attack]])
        if len(z_attack_source) <= ATTACK_PROTOTYPES:
            attack_proto_z = z_attack_source
            attack_proto_desc = "all_base_support_train_plus_confirmed_active_labels"
        else:
            centroid = z_attack_source.mean(axis=0, keepdims=True)
            start = int(np.argmin(pairwise_distances(z_attack_source, centroid).ravel()))
            local = ar.farthest_first(z_attack_source, ATTACK_PROTOTYPES, start)
            attack_proto_z = z_attack_source[local]
            attack_proto_desc = "kcenter64_from_base_support_train_plus_confirmed_active_labels"
        id_proto_z = z_all[id_proto]
        ood_proto_z = z_all[ood_proto]
        r_id = issue27av.p95_radius(z_all[id_calib], id_proto_z)
        r_ood = issue27av.p95_radius(z_all[ood_val], ood_proto_z)
        r_attack = issue27av.p95_radius(z_all[base_val], attack_proto_z)

        prototype_rows.extend(
            [
                {
                    "seed": seed,
                    "prototype_set": "id_prototypes",
                    "source_roles": "id_fit",
                    "count": len(id_proto),
                    "radius_source": "id_calib",
                    "radius_p95": r_id,
                    "hash_or_descriptor": hash_indices(id_proto),
                    "uses_final_ood": False,
                    "uses_attack_eval": False,
                    "uses_dev_query": False,
                },
                {
                    "seed": seed,
                    "prototype_set": "ood_prototypes",
                    "source_roles": "ood_train_guard",
                    "count": len(ood_proto),
                    "radius_source": "ood_val",
                    "radius_p95": r_ood,
                    "hash_or_descriptor": hash_indices(ood_proto),
                    "uses_final_ood": False,
                    "uses_attack_eval": False,
                    "uses_dev_query": False,
                },
                {
                    "seed": seed,
                    "prototype_set": "attack_prototypes",
                    "source_roles": "base_attack_support_train|dev_active_confirmed_attack",
                    "count": len(attack_proto_z),
                    "radius_source": "base_support_val",
                    "radius_p95": r_attack,
                    "hash_or_descriptor": attack_proto_desc,
                    "uses_final_ood": False,
                    "uses_attack_eval": False,
                    "uses_dev_query": False,
                },
            ]
        )

        dev_features = {
            "id_calib": build_features_for_rows(x[id_calib], score_id, threshold, scaler, id_proto_z, ood_proto_z, attack_proto_z, r_id, r_ood, r_attack),
            "ood_val": build_features_for_rows(x[ood_val], score_ood, threshold, scaler, id_proto_z, ood_proto_z, attack_proto_z, r_id, r_ood, r_attack),
            "support_val": build_features_for_rows(x[base_val], score_support_val, threshold, scaler, id_proto_z, ood_proto_z, attack_proto_z, r_id, r_ood, r_attack),
        }
        margins = candidate_margins(
            dev_features["id_calib"]["attack_distance_advantage"],
            dev_features["ood_val"]["attack_distance_advantage"],
            dev_features["support_val"]["attack_distance_advantage"],
        )
        candidates: list[dict[str, Any]] = []
        for gate_name in [
            "baseline_no_veto",
            "benign_prototype_veto_v1",
            "conflict_review_v1",
            "attack_advantage_zero_v1",
        ]:
            candidates.append(evaluate_candidate(gate_name, 0.0, dev_features, seed))
        for margin in margins:
            candidates.append(evaluate_candidate("attack_advantage_margin_dev_v1", margin, dev_features, seed))
        gate_candidate_rows.extend(candidates)
        selected = select_gate_for_seed(candidates)
        selected_gate_rows.append(selected)

        report_features = {
            "id_calib_dev": dev_features["id_calib"],
            "ood_val_dev": dev_features["ood_val"],
            "support_val_dev": dev_features["support_val"],
            "final_ood_benign_eval_report_only": build_features_for_rows(
                x[final_ood],
                model.score(x[final_ood]),
                threshold,
                scaler,
                id_proto_z,
                ood_proto_z,
                attack_proto_z,
                r_id,
                r_ood,
                r_attack,
            ),
            "medium_attack_eval_report_only": build_features_for_rows(
                x[attack_eval],
                model.score(x[attack_eval]),
                threshold,
                scaler,
                id_proto_z,
                ood_proto_z,
                attack_proto_z,
                r_id,
                r_ood,
                r_attack,
            ),
            "dev_heavy_query_report_only": build_features_for_rows(
                new_x[dev_query_idx],
                model.score(new_x[dev_query_idx]),
                threshold,
                scaler,
                id_proto_z,
                ood_proto_z,
                attack_proto_z,
                r_id,
                r_ood,
                r_attack,
            ),
        }
        for role, feat in report_features.items():
            before = apply_gate(feat, "baseline_no_veto", 0.0)
            after = apply_gate(feat, str(selected["gate_name"]), float(selected["margin"]))
            before_metrics = gate_metrics(before)
            after_metrics = gate_metrics(after)
            replay_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "selected_gate_name": selected["gate_name"],
                    "selected_margin": selected["margin"],
                    "rows": len(feat["score"]),
                    "before_hard_alarm_rate": before_metrics["hard_alarm_rate"],
                    "after_hard_alarm_rate": after_metrics["hard_alarm_rate"],
                    "after_needs_review_rate": after_metrics["needs_review_rate"],
                    "after_suppressed_rate": after_metrics["suppressed_rate"],
                    "after_operational_attention_rate": after_metrics["operational_attention_rate"],
                    "score_mean": float(np.mean(feat["score"])) if len(feat["score"]) else float("nan"),
                    "benign_covered_fraction": rate_bool(feat["benign_covered"]),
                    "attack_covered_fraction": rate_bool(feat["attack_covered"]),
                    "base_alarm_benign_covered_fraction": rate_bool(feat["base_alarm"] & feat["benign_covered"]),
                    "base_alarm_attack_covered_fraction": rate_bool(feat["base_alarm"] & feat["attack_covered"]),
                }
            )
            named_specs = [
                ("baseline_no_veto", "baseline_no_veto", 0.0),
                ("fixed_benign_prototype_veto_v1", "benign_prototype_veto_v1", 0.0),
                ("fixed_conflict_review_v1", "conflict_review_v1", 0.0),
                ("fixed_attack_advantage_zero_v1", "attack_advantage_zero_v1", 0.0),
                ("selected_dev_gate", str(selected["gate_name"]), float(selected["margin"])),
            ]
            for gate_label, gate_name, gate_margin in named_specs:
                action = apply_gate(feat, gate_name, gate_margin)
                metrics = gate_metrics(action)
                named_replay_rows.append(
                    {
                        "seed": seed,
                        "role": role,
                        "gate_label": gate_label,
                        "gate_name": gate_name,
                        "margin": gate_margin,
                        "hard_alarm_rate": metrics["hard_alarm_rate"],
                        "needs_review_rate": metrics["needs_review_rate"],
                        "suppressed_rate": metrics["suppressed_rate"],
                        "operational_attention_rate": metrics["operational_attention_rate"],
                        "report_only_if_final_or_attack": role.endswith("_report_only"),
                        "used_for_gate_selection": False,
                    }
                )

        role_rows.append(
            {
                "seed": seed,
                "active_budget": ACTIVE_BUDGET,
                "fit_roles": "id_fit|ood_train_guard|base_support_train|dev_active_confirmed_attack",
                "threshold_roles": "id_calib|ood_val|base_support_val",
                "gate_calibration_roles": "id_calib|ood_val|base_support_val",
                "prototype_roles": "id_fit|ood_train_guard|base_support_train|dev_active_confirmed_attack",
                "report_only_roles": "final_ood_benign_eval|medium_attack_eval|dev_heavy_query",
                "uses_final_ood_for_gate_selection": False,
                "uses_attack_eval_for_gate_selection": False,
                "uses_dev_query_for_gate_selection": False,
                "uses_final_ood_for_threshold_or_prototypes": False,
                "uses_candidate_labels_for_selection": False,
                "confirmed_active_labels_after_feature_only_selection": int(len(confirmed_attack)),
                "selected_gate_name": selected["gate_name"],
                "selected_margin": selected["margin"],
                "forbidden_role_access": False,
                "notes": "current final OOD is diagnostic only and cannot support formal claim after tail attribution",
            }
        )

    aggregate_rows = aggregate_selected(replay_rows)
    named_summary_rows = aggregate_named_replay(named_replay_rows)
    primary_verdict, verdict_stats = pick_verdict(aggregate_rows, named_summary_rows)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "prototype_registry.csv", prototype_rows)
    write_csv(OUT / "dev_gate_candidate_table.csv", gate_candidate_rows)
    write_csv(OUT / "selected_gate_by_seed.csv", selected_gate_rows)
    write_csv(OUT / "gate_replay_by_role_seed.csv", replay_rows)
    write_csv(OUT / "gate_replay_summary.csv", aggregate_rows)
    write_csv(OUT / "report_only_named_gate_replay.csv", named_replay_rows)
    write_csv(OUT / "report_only_named_gate_replay_summary.csv", named_summary_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)

    selected_names = Counter(str(r["gate_name"]) for r in selected_gate_rows)
    final_row = next((r for r in aggregate_rows if r["role"] == "final_ood_benign_eval_report_only"), {})
    dev_row = next((r for r in aggregate_rows if r["role"] == "dev_heavy_query_report_only"), {})
    medium_row = next((r for r in aggregate_rows if r["role"] == "medium_attack_eval_report_only"), {})

    write_md(
        OUT / "ood_safe_gate_repair_report.md",
        [
            "# OOD-Safe Gate Repair Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "This is a diagnostic gate repair on the medium Gotham Kitsune115 asset. It is not a formal benchmark.",
            "",
            "Gate selection used only ID calibration, OOD validation, and base support validation. Final OOD, medium attack eval, and dev-heavy query were replay-only.",
            "",
            "## Selected Gate Counts",
            "",
            *[f"- {name}: `{count}` seeds" for name, count in sorted(selected_names.items())],
            "",
            "## Report-Only Replay Summary",
            "",
            f"- final OOD after hard alarm max: `{verdict_stats.get('final_ood_after_hard_alarm_max')}`",
            f"- final OOD after attention max: `{verdict_stats.get('final_ood_after_attention_max')}`",
            f"- dev-heavy after detection min: `{verdict_stats.get('dev_heavy_after_detection_min')}`",
            f"- medium attack after detection min: `{verdict_stats.get('medium_attack_after_detection_min')}`",
            f"- fixed benign veto final OOD hard alarm max: `{verdict_stats.get('fixed_veto_final_ood_hard_alarm_max')}`",
            f"- fixed benign veto dev-heavy detection min: `{verdict_stats.get('fixed_veto_dev_heavy_detection_min')}`",
            f"- fixed benign veto medium attack detection min: `{verdict_stats.get('fixed_veto_medium_attack_detection_min')}`",
            "",
            "If the candidate is supported, the next step still requires a clean sealed-final replay because the current final OOD has already been used diagnostically in issue27av.",
        ],
    )
    write_md(
        OUT / "gate_policy_v1.md",
        [
            "# Gate Policy v1",
            "",
            "Draft diagnostic policy, frozen per seed from development roles only.",
            "",
            "- Base alarm comes from the existing old-protocol HistGB score and NP/order-stat threshold.",
            "- ID/OOD/attack prototype coverage is computed in a common StandardScaler space fitted on ID fit, OOD train, and base support train.",
            "- `benign_prototype_veto_v1`: suppress base alarms that are benign-covered but not attack-covered.",
            "- `conflict_review_v1`: suppress benign-only alarms and route benign+attack conflicts to review.",
            "- `attack_advantage_*`: allow benign-covered alarms only when attack distance is closer than benign distance by the dev-calibrated margin.",
            "- Final OOD cannot be used to pick the gate or margin.",
        ],
    )
    next_issue = "issue27ax_clean_sealed_final_replay_for_ood_safe_active_labeling"
    if primary_verdict == "benign_veto_tradeoff_unresolved_ood_safe_but_attack_damaged":
        next_issue = "issue27ax_attack_preserving_ood_veto_margin_repair"
    elif primary_verdict == "benign_prototype_veto_reduces_hard_alarm_but_review_cost_high":
        next_issue = "issue27ax_reduce_review_cost_or_build_ood_stress_pool"
    elif primary_verdict == "benign_prototype_veto_ood_safe_but_attack_signal_too_damaged":
        next_issue = "issue27ax_conflict_margin_repair_before_clean_final"
    elif primary_verdict == "benign_prototype_veto_insufficient_final_ood_tail_persists":
        next_issue = "issue27ax_build_dev_ood_stress_pool_before_more_gate_repair"
    write_md(
        OUT / "issue27aw_decision.md",
        [
            "# Issue27aw Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- This result is diagnostic only.",
            "- Gate selection did not use final OOD, medium attack eval, or dev-heavy query.",
            "- Current final OOD is no longer clean for formal claims because it has been used for attribution in issue27av.",
            f"- Recommended next issue: `{next_issue}`.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27aw.md",
        [
            "# Claim Update After issue27aw",
            "",
            "- issue27aw does not establish a formal model result.",
            "- It tests whether a benign/OOD prototype veto can repair the OOD tail observed in the active-labeling diagnostic.",
            "- Any paper-facing claim still requires clean sealed-final replay after gate freezing.",
        ],
    )
    write_md(
        OUT / "issue27ax_next_action.md",
        [
            "# Issue27ax Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If supported, construct a clean sealed-final OOD/attack replay set that was not used for gate design.",
            "- Keep final roles report-only.",
            "- Do not run full/larger formal benchmark yet.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27aw Summary",
            "",
            "1. issue27aw completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: OOD-safe gate repair diagnostic; not formal benchmark",
            "4. final OOD used for gate selection: no",
            "5. attack eval / dev query used for gate selection: no",
            f"6. selected gate counts: `{json.dumps(dict(selected_names), sort_keys=True)}`",
            f"7. final OOD after hard alarm max: `{verdict_stats.get('final_ood_after_hard_alarm_max')}`",
            f"8. final OOD after attention max: `{verdict_stats.get('final_ood_after_attention_max')}`",
            f"9. dev-heavy after detection min: `{verdict_stats.get('dev_heavy_after_detection_min')}`",
            f"10. medium attack after detection min: `{verdict_stats.get('medium_attack_after_detection_min')}`",
            f"11. fixed benign veto final OOD hard alarm max: `{verdict_stats.get('fixed_veto_final_ood_hard_alarm_max')}`",
            f"12. fixed benign veto dev-heavy detection min: `{verdict_stats.get('fixed_veto_dev_heavy_detection_min')}`",
            f"13. fixed benign veto medium attack detection min: `{verdict_stats.get('fixed_veto_medium_attack_detection_min')}`",
            "14. formal benchmark allowed: no",
            "15. current final OOD clean for formal claim: no, diagnostic only after issue27av",
            f"16. next action: `{next_issue}`",
            "17. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "primary_strategy": PRIMARY_STRATEGY,
        "active_budget": ACTIVE_BUDGET,
        "support_budget": SUPPORT_BUDGET,
        "val_target": VAL_TARGET,
        "gate_selection_roles": ["id_calib", "ood_val", "support_val"],
        "report_only_roles": ["final_ood_benign_eval", "medium_attack_eval", "dev_heavy_query"],
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27av_outputs": str(ISSUE27AV),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "role_policy": "gate from dev/calib roles only; final OOD and attacks replay-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27aw -->",
        [
            "<!-- issue27aw -->",
            "## issue27aw - OOD-safe gate repair diagnostic",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; benign/OOD prototype veto selected from dev roles and replayed on report-only roles.",
            "- Current final OOD remains diagnostic-only; clean sealed-final replay is required before formal claims.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27aw -->",
        [
            "<!-- issue27aw -->",
            "## issue27aw - OOD-safe gate repair",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether benign/OOD prototype veto can reduce OOD tail without using final roles for gate selection.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "stats": verdict_stats, "selected_gate_counts": dict(selected_names), "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
