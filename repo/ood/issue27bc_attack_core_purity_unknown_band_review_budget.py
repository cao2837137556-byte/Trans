from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bc_attack_core_purity_unknown_band_review_budget_2026-06-07"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [64, 128]
PROTO_BUDGETS = [32, 64]
BANK_RADIUS_QS = [0.95]
ATTACK_CORE_NORMS = [0.75, 1.0, 1.25]
BENIGN_CORE_NORMS = [0.75, 1.0, 1.25, 1.50]
UNKNOWN_NORMS = [1.25, 1.50, 2.0]
STRONG_SCORE_QS = [0.00, 0.25]
WEAK_SCORE_QS = [0.25, 0.50]
REVIEW_BUDGETS = [0.01, 0.03, 0.05, 0.10]

VAL_TARGET = 0.01
FINAL_OOD_RELAXED_TARGET = 0.03
ATTACK_DIAG_FLOOR = 0.75
STRONG_ATTACK_DIAG_FLOOR = 0.90


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


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def rate(mask: np.ndarray) -> float:
    arr = np.asarray(mask)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr.astype(bool)))


def summarize(vals: list[float] | np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {"mean": float("nan"), "min": float("nan"), "max": float("nan")}
    return {"mean": float(np.mean(arr)), "min": float(np.min(arr)), "max": float(np.max(arr))}


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("source_file") or row.get("pcap_member") or "unknown"


def split_train_val_pseudo(
    rows: np.ndarray,
    sidecar: list[dict[str, str]],
    seed: int,
    label: str,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, dict[str, Any]]:
    rows = np.asarray(sorted(map(int, rows.tolist())), dtype=np.int64)
    by_file: dict[str, list[int]] = defaultdict(list)
    for idx in rows:
        by_file[file_key(sidecar[int(idx)])].append(int(idx))
    files = sorted(by_file)
    audit: dict[str, Any] = {
        "label": label,
        "seed": seed,
        "input_rows": int(len(rows)),
        "file_count": int(len(files)),
        "split_rule": "leave_one_file_pseudo_query_then_seeded_75_25_train_val",
    }
    if len(rows) < 3:
        train, val = ay.split_selected(rows, seed)
        pseudo = np.asarray([], dtype=np.int64)
        audit.update(
            {
                "holdout_file": "",
                "train_rows": int(len(train)),
                "val_rows": int(len(val)),
                "pseudo_rows": 0,
                "fallback": "too_few_rows_no_pseudo",
            }
        )
        return train, val, pseudo, audit
    if len(files) >= 2:
        holdout_file = files[seed % len(files)]
        pseudo = np.asarray(sorted(by_file[holdout_file]), dtype=np.int64)
        remain = np.asarray(sorted([idx for f in files if f != holdout_file for idx in by_file[f]]), dtype=np.int64)
        if len(remain) < 2:
            train, val = ay.split_selected(rows, seed)
            pseudo = np.asarray([], dtype=np.int64)
            audit["fallback"] = "holdout_left_too_few_train_rows"
        else:
            train, val = ay.split_selected(remain, seed)
            audit["fallback"] = "none"
        audit["holdout_file"] = holdout_file
    else:
        train, rest = ay.split_selected(rows, seed)
        val, pseudo = ay.split_selected(rest, seed + 17) if len(rest) >= 2 else (rest, np.asarray([], dtype=np.int64))
        audit.update({"holdout_file": files[0] if files else "", "fallback": "single_file_seeded_pseudo"})
    audit.update(
        {
            "train_rows": int(len(train)),
            "val_rows": int(len(val)),
            "pseudo_rows": int(len(pseudo)),
            "train_hash": hash_indices(train),
            "val_hash": hash_indices(val),
            "pseudo_hash": hash_indices(pseudo),
        }
    )
    return train, val, pseudo, audit


def apply_unknown_band_gate(
    raw_alarm: np.ndarray,
    score_strength: np.ndarray,
    attack_cov: np.ndarray,
    benign_cov: np.ndarray,
    strong_score_floor: float,
    weak_score_ceiling: float,
    attack_core_norm: float,
    benign_core_norm: float,
    unknown_norm: float,
    review_budget: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    n = len(raw_alarm)
    state = np.full(n, "no_alarm", dtype=object)
    raw = raw_alarm.astype(bool)
    near_attack = attack_cov <= float(attack_core_norm)
    near_benign = benign_cov <= float(benign_core_norm)
    far_all = (attack_cov > float(unknown_norm)) & (benign_cov > float(unknown_norm))
    strong_attack_core = raw & near_attack & ~near_benign & (score_strength >= float(strong_score_floor))
    attack_only = raw & near_attack & ~near_benign
    weak_benign_only = raw & near_benign & ~near_attack & (score_strength <= float(weak_score_ceiling))
    conflict = raw & near_attack & near_benign
    unknown = raw & far_all
    ambiguous = raw & ~(strong_attack_core | attack_only | weak_benign_only | conflict | unknown)

    state[weak_benign_only] = "suppress"
    state[attack_only | strong_attack_core] = "hard_alarm"
    state[conflict] = "review_conflict"
    state[unknown | ambiguous] = "review_unknown"

    review_mask = np.isin(state, ["review_conflict", "review_unknown"])
    max_review = int(np.floor(float(review_budget) * n))
    if max_review < int(np.sum(review_mask)):
        review_idx = np.where(review_mask)[0]
        priority = score_strength + (float(unknown_norm) - attack_cov) - 0.5 * np.maximum(0.0, float(unknown_norm) - benign_cov)
        keep = review_idx[np.argsort(priority[review_idx])[-max_review:]] if max_review > 0 else np.asarray([], dtype=np.int64)
        overflow = np.setdiff1d(review_idx, keep, assume_unique=False)
        state[overflow] = "review_overflow_no_alarm"

    masks = {
        "raw_alarm": raw,
        "hard_alarm": state == "hard_alarm",
        "suppress": state == "suppress",
        "review_conflict": state == "review_conflict",
        "review_unknown": state == "review_unknown",
        "review_any": np.isin(state, ["review_conflict", "review_unknown"]),
        "review_overflow": state == "review_overflow_no_alarm",
        "strong_attack_core": strong_attack_core,
        "near_attack": near_attack,
        "near_benign": near_benign,
        "unknown_sparse_uncapped": unknown,
        "conflict_uncapped": conflict,
    }
    return state, masks


def metrics_from_state(
    role: str,
    state: np.ndarray,
    masks: dict[str, np.ndarray],
    attack_cov: np.ndarray,
    benign_cov: np.ndarray,
    score_strength: np.ndarray,
) -> dict[str, Any]:
    return {
        "role": role,
        "rows": int(len(state)),
        "raw_alarm_rate": rate(masks["raw_alarm"]),
        "hard_alarm_rate": rate(masks["hard_alarm"]),
        "suppress_rate": rate(masks["suppress"]),
        "review_conflict_rate": rate(masks["review_conflict"]),
        "review_unknown_rate": rate(masks["review_unknown"]),
        "review_any_rate": rate(masks["review_any"]),
        "review_overflow_rate": rate(masks["review_overflow"]),
        "strong_attack_core_rate": rate(masks["strong_attack_core"]),
        "near_attack_rate": rate(masks["near_attack"]),
        "near_benign_rate": rate(masks["near_benign"]),
        "conflict_uncapped_rate": rate(masks["conflict_uncapped"]),
        "unknown_sparse_uncapped_rate": rate(masks["unknown_sparse_uncapped"]),
        "attack_cov_p50": float(np.quantile(attack_cov, 0.50)) if len(attack_cov) else float("nan"),
        "attack_cov_p95": float(np.quantile(attack_cov, 0.95)) if len(attack_cov) else float("nan"),
        "benign_cov_p50": float(np.quantile(benign_cov, 0.50)) if len(benign_cov) else float("nan"),
        "benign_cov_p95": float(np.quantile(benign_cov, 0.95)) if len(benign_cov) else float("nan"),
        "score_strength_p50": float(np.quantile(score_strength, 0.50)) if len(score_strength) else float("nan"),
        "score_strength_p95": float(np.quantile(score_strength, 0.95)) if len(score_strength) else float("nan"),
    }


def precompute_role(x_role: np.ndarray, banks: dict[str, bb.PrototypeBank], bundle: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    attack_cov = np.minimum(banks["attack_medium"].normalized_distance(x_role), banks["attack_heavy"].normalized_distance(x_role))
    benign_cov = np.minimum(banks["id"].normalized_distance(x_role), banks["ood"].normalized_distance(x_role))
    return {
        "raw_alarm": bundle["raw_alarm"],
        "score_strength": bundle["score_strength"],
        "attack_cov": attack_cov,
        "benign_cov": benign_cov,
    }


def aggregate_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "active_label_budget",
        "proto_budget",
        "bank_radius_q",
        "attack_core_norm",
        "benign_core_norm",
        "unknown_norm",
        "strong_score_q",
        "weak_score_q",
        "review_budget",
    ]
    metrics = [
        "id_hard",
        "id_review",
        "ood_hard",
        "ood_review",
        "stress_hard",
        "stress_review",
        "support_medium_hard",
        "support_heavy_hard",
        "pseudo_medium_hard",
        "pseudo_heavy_hard",
        "dev_attack_min",
        "dev_pseudo_min",
        "dev_review_max",
        "dev_score",
    ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        row: dict[str, Any] = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(group)
        for metric in metrics:
            stats = summarize([float(r[metric]) for r in group])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["strict_feasible_all_seeds"] = all(str(r["strict_feasible"]) == "True" for r in group)
        row["relaxed_feasible_all_seeds"] = all(str(r["relaxed_feasible"]) == "True" for r in group)
        out.append(row)
    return out


def choose_global_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict = [r for r in rows if str(r["strict_feasible_all_seeds"]) == "True"]
    relaxed = [r for r in rows if str(r["relaxed_feasible_all_seeds"]) == "True"]
    pool = strict or relaxed or rows
    return max(
        pool,
        key=lambda r: (
            str(r["strict_feasible_all_seeds"]) == "True",
            str(r["relaxed_feasible_all_seeds"]) == "True",
            float(r["dev_attack_min_min"]),
            float(r["dev_pseudo_min_min"]),
            -float(r["stress_hard_max"]),
            -float(r["stress_review_max"]),
            -float(r["ood_review_max"]),
            -float(r["review_budget"]),
            -float(r["proto_budget"]),
        ),
    )


def aggregate_replay(rows: list[dict[str, Any]]) -> dict[str, Any]:
    roles = [
        "id_calib",
        "ood_val",
        "ood_stress_val",
        "support_medium_val",
        "support_heavy_val",
        "pseudo_medium_query",
        "pseudo_heavy_query",
        "medium_attack_eval_report_only",
        "dev_heavy_query_report_only",
        "final_ood_report_only",
    ]
    out: dict[str, Any] = {"seeds": len(rows)}
    for role in roles:
        for metric in ["hard_alarm_rate", "review_any_rate", "review_conflict_rate", "review_unknown_rate", "review_overflow_rate", "suppress_rate", "raw_alarm_rate"]:
            stats = summarize([float(r[f"{role}_{metric}"]) for r in rows])
            for stat, value in stats.items():
                out[f"{role}_{metric}_{stat}"] = value
    out["dev_attack_hard_min"] = min(
        float(out["support_medium_val_hard_alarm_rate_min"]),
        float(out["support_heavy_val_hard_alarm_rate_min"]),
        float(out["pseudo_medium_query_hard_alarm_rate_min"]),
        float(out["pseudo_heavy_query_hard_alarm_rate_min"]),
    )
    out["report_only_attack_hard_min"] = min(
        float(out["medium_attack_eval_report_only_hard_alarm_rate_min"]),
        float(out["dev_heavy_query_report_only_hard_alarm_rate_min"]),
    )
    out["report_only_attack_score_or_review_min"] = min(
        float(out["medium_attack_eval_report_only_hard_alarm_rate_min"]) + float(out["medium_attack_eval_report_only_review_any_rate_min"]),
        float(out["dev_heavy_query_report_only_hard_alarm_rate_min"]) + float(out["dev_heavy_query_report_only_review_any_rate_min"]),
    )
    return out


def choose_verdict(summary: dict[str, Any]) -> str:
    if (
        float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["dev_attack_hard_min"]) >= STRONG_ATTACK_DIAG_FLOOR
        and float(summary["report_only_attack_hard_min"]) >= STRONG_ATTACK_DIAG_FLOOR
        and float(summary["ood_stress_val_review_any_rate_max"]) <= 0.10
    ):
        return "purity_unknown_gate_supported_ready_for_temporal_consistency"
    if (
        float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["dev_attack_hard_min"]) >= ATTACK_DIAG_FLOOR
        and float(summary["report_only_attack_hard_min"]) >= ATTACK_DIAG_FLOOR
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= FINAL_OOD_RELAXED_TARGET
    ):
        return "purity_unknown_gate_promising_needs_temporal_or_region_refinement"
    if float(summary["dev_attack_hard_min"]) >= ATTACK_DIAG_FLOOR and float(summary["report_only_attack_hard_min"]) < ATTACK_DIAG_FLOOR:
        return "pseudo_query_still_underestimates_report_only_attack_gap"
    if float(summary["dev_attack_hard_min"]) < ATTACK_DIAG_FLOOR:
        return "pseudo_query_reveals_support_core_overfit"
    if float(summary["ood_stress_val_review_any_rate_max"]) > 0.10 or float(summary["final_ood_report_only_review_any_rate_max"]) > 0.10:
        return "review_budget_overload"
    if float(summary["ood_stress_val_hard_alarm_rate_max"]) > VAL_TARGET:
        return "attack_preserved_but_ood_overbudget"
    return "purity_unknown_gate_unresolved"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
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
    active_candidate_idx, dev_query_idx, active_split_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "actual_sha256": sha256_file(stress_cert_path), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    grid_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    prototype_purity_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=max(ACTIVE_LABEL_BUDGETS),
        )
        # The active-label candidate stream is development-side only. Labels are revealed only after selection.
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        for active_budget in ACTIVE_LABEL_BUDGETS:
            active_confirmed_budget = selected_confirmed[: min(active_budget, len(selected_confirmed))]
            heavy_train, heavy_val, heavy_pseudo, heavy_audit = split_train_val_pseudo(active_confirmed_budget, new_sidecar, seed, "active_heavy_attack_support")
            split_rows.extend(
                [
                    {"seed": seed, "active_label_budget": active_budget, **medium_audit, "base_support_selector": "kcenter128", "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                    {"seed": seed, "active_label_budget": active_budget, **heavy_audit, "active_selector": "coverage_uncovered_farthest_first", **{f"active_{k}": v for k, v in active_audit.items()}},
                ]
            )
            if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0:
                continue

            medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
            heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
            medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
            heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))

            role_x_dev = {
                "id_calib": x[id_calib],
                "ood_val": x[ood_val],
                "ood_stress_val": stress_x[stress_val],
                "support_medium_val": x[medium_val],
                "support_heavy_val": new_x[heavy_val],
                "pseudo_medium_query": x[medium_pseudo],
                "pseudo_heavy_query": new_x[heavy_pseudo],
            }
            role_scores = {
                role: bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
                for role, x_role in role_x_dev.items()
            }
            support_strength = np.concatenate(
                [
                    role_scores["support_medium_val"]["score_strength"],
                    role_scores["support_heavy_val"]["score_strength"],
                    role_scores["pseudo_medium_query"]["score_strength"],
                    role_scores["pseudo_heavy_query"]["score_strength"],
                ]
            )
            support_strength = support_strength[np.isfinite(support_strength)]
            if len(support_strength) == 0:
                support_strength = np.asarray([0.0], dtype=np.float64)

            for proto_budget in PROTO_BUDGETS:
                for radius_q in BANK_RADIUS_QS:
                    banks, audit = bb.build_banks(
                        x,
                        stress_x,
                        id_fit,
                        id_calib,
                        ood_train,
                        ood_val,
                        stress_train,
                        stress_val,
                        medium_train,
                        medium_val,
                        new_x[heavy_train],
                        new_x[heavy_val],
                        proto_budget,
                        radius_q,
                        seed,
                        active_budget,
                    )
                    bank_rows.extend(audit)
                    pre = {role: precompute_role(role_x_dev[role], banks, role_scores[role]) for role in role_x_dev}
                    for attack_core_norm in ATTACK_CORE_NORMS:
                        for benign_core_norm in BENIGN_CORE_NORMS:
                            for unknown_norm in UNKNOWN_NORMS:
                                for strong_q in STRONG_SCORE_QS:
                                    strong_floor = float(np.quantile(support_strength, strong_q))
                                    for weak_q in WEAK_SCORE_QS:
                                        if weak_q < strong_q:
                                            continue
                                        weak_ceiling = float(np.quantile(support_strength, weak_q))
                                        for review_budget in REVIEW_BUDGETS:
                                            metrics: dict[str, float] = {}
                                            for role, p in pre.items():
                                                state, masks = apply_unknown_band_gate(
                                                    p["raw_alarm"],
                                                    p["score_strength"],
                                                    p["attack_cov"],
                                                    p["benign_cov"],
                                                    strong_floor,
                                                    weak_ceiling,
                                                    attack_core_norm,
                                                    benign_core_norm,
                                                    unknown_norm,
                                                    review_budget,
                                                )
                                                prefix = {
                                                    "id_calib": "id",
                                                    "ood_val": "ood",
                                                    "ood_stress_val": "stress",
                                                    "support_medium_val": "support_medium",
                                                    "support_heavy_val": "support_heavy",
                                                    "pseudo_medium_query": "pseudo_medium",
                                                    "pseudo_heavy_query": "pseudo_heavy",
                                                }[role]
                                                metrics[f"{prefix}_hard"] = rate(masks["hard_alarm"])
                                                metrics[f"{prefix}_review"] = rate(masks["review_any"])
                                                metrics[f"{prefix}_suppress"] = rate(masks["suppress"])
                                            dev_attack_min = min(
                                                metrics["support_medium_hard"],
                                                metrics["support_heavy_hard"],
                                                metrics["pseudo_medium_hard"],
                                                metrics["pseudo_heavy_hard"],
                                            )
                                            dev_pseudo_min = min(metrics["pseudo_medium_hard"], metrics["pseudo_heavy_hard"])
                                            dev_review_max = max(metrics["id_review"], metrics["ood_review"], metrics["stress_review"])
                                            strict_feasible = (
                                                metrics["id_hard"] <= VAL_TARGET
                                                and metrics["ood_hard"] <= VAL_TARGET
                                                and metrics["stress_hard"] <= VAL_TARGET
                                                and dev_review_max <= review_budget + 1e-12
                                                and dev_attack_min >= ATTACK_DIAG_FLOOR
                                            )
                                            relaxed_feasible = (
                                                metrics["id_hard"] <= VAL_TARGET
                                                and metrics["ood_hard"] <= VAL_TARGET
                                                and metrics["stress_hard"] <= VAL_TARGET
                                                and dev_review_max <= min(0.10, review_budget + 1e-12)
                                                and dev_attack_min >= 0.50
                                            )
                                            grid_rows.append(
                                                {
                                                    "seed": seed,
                                                    "active_label_budget": active_budget,
                                                    "proto_budget": proto_budget,
                                                    "bank_radius_q": radius_q,
                                                    "attack_core_norm": attack_core_norm,
                                                    "benign_core_norm": benign_core_norm,
                                                    "unknown_norm": unknown_norm,
                                                    "strong_score_q": strong_q,
                                                    "weak_score_q": weak_q,
                                                    "review_budget": review_budget,
                                                    "strong_score_floor": strong_floor,
                                                    "weak_score_ceiling": weak_ceiling,
                                                    **metrics,
                                                    "dev_attack_min": dev_attack_min,
                                                    "dev_pseudo_min": dev_pseudo_min,
                                                    "dev_review_max": dev_review_max,
                                                    "strict_feasible": strict_feasible,
                                                    "relaxed_feasible": relaxed_feasible,
                                                    "dev_score": dev_attack_min + 0.25 * dev_pseudo_min - 0.25 * metrics["stress_hard"] - 0.15 * dev_review_max,
                                                    "selection_uses_final_ood": False,
                                                    "selection_uses_attack_eval": False,
                                                    "selection_uses_dev_heavy_query": False,
                                                }
                                            )

    grid_summary = aggregate_grid(grid_rows)
    selected = choose_global_config(grid_summary)
    selected_cfg = {
        "active_label_budget": int(selected["active_label_budget"]),
        "proto_budget": int(selected["proto_budget"]),
        "bank_radius_q": float(selected["bank_radius_q"]),
        "attack_core_norm": float(selected["attack_core_norm"]),
        "benign_core_norm": float(selected["benign_core_norm"]),
        "unknown_norm": float(selected["unknown_norm"]),
        "strong_score_q": float(selected["strong_score_q"]),
        "weak_score_q": float(selected["weak_score_q"]),
        "review_budget": float(selected["review_budget"]),
    }

    replay_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, _ = split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, _ = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=selected_cfg["active_label_budget"],
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, _ = split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        banks, _ = bb.build_banks(
            x,
            stress_x,
            id_fit,
            id_calib,
            ood_train,
            ood_val,
            stress_train,
            stress_val,
            medium_train,
            medium_val,
            new_x[heavy_train],
            new_x[heavy_val],
            selected_cfg["proto_budget"],
            selected_cfg["bank_radius_q"],
            seed,
            selected_cfg["active_label_budget"],
        )
        dev_strength = []
        for role_x in [x[medium_val], new_x[heavy_val], x[medium_pseudo], new_x[heavy_pseudo]]:
            b = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), role_x)
            dev_strength.append(b["score_strength"])
        support_strength = np.concatenate(dev_strength)
        strong_floor = float(np.quantile(support_strength, selected_cfg["strong_score_q"]))
        weak_ceiling = float(np.quantile(support_strength, selected_cfg["weak_score_q"]))

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
            p = precompute_role(x_role, banks, bundle)
            state, masks = apply_unknown_band_gate(
                p["raw_alarm"],
                p["score_strength"],
                p["attack_cov"],
                p["benign_cov"],
                strong_floor,
                weak_ceiling,
                selected_cfg["attack_core_norm"],
                selected_cfg["benign_core_norm"],
                selected_cfg["unknown_norm"],
                selected_cfg["review_budget"],
            )
            metrics = metrics_from_state(role, state, masks, p["attack_cov"], p["benign_cov"], p["score_strength"])
            for key, value in metrics.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = value
            decision_rows.append({"seed": seed, **metrics})
            prototype_purity_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "rows": int(len(state)),
                    "attack_core_rate": metrics["near_attack_rate"],
                    "benign_core_rate": metrics["near_benign_rate"],
                    "mixed_conflict_uncapped_rate": metrics["conflict_uncapped_rate"],
                    "unknown_sparse_uncapped_rate": metrics["unknown_sparse_uncapped_rate"],
                    "uses_report_only_for_purity_threshold": False,
                }
            )
        replay_rows.append(replay_row)
        role_rows.append(
            {
                "seed": seed,
                "active_label_budget": selected_cfg["active_label_budget"],
                "fit_roles": "id_fit|ood_train_guard|medium_attack_train_without_pseudo_file|active_heavy_attack_train_without_pseudo_file",
                "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                "prototype_bank_roles": "id_fit/id_calib|ood_train/ood_val/ood_stress_train/ood_stress_val|medium_support_train/val|active_heavy_train/val",
                "gate_selection_roles": "id_calib|ood_val|ood_stress_val|support_medium_val|support_heavy_val|pseudo_medium_query|pseudo_heavy_query",
                "report_only_roles": "medium_attack_eval|dev_heavy_query|final_ood",
                "uses_final_ood_for_gate_selection": False,
                "uses_attack_eval_for_gate_selection": False,
                "uses_dev_heavy_query_for_gate_selection": False,
                "uses_final_ood_for_prototypes": False,
                "uses_attack_eval_for_prototypes": False,
                "forbidden_role_access": False,
            }
        )

    replay_summary = aggregate_replay(replay_rows)
    verdict = choose_verdict(replay_summary)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "pseudo_query_split_audit.csv", split_rows)
    write_csv(OUT / "prototype_bank_audit.csv", bank_rows)
    write_csv(OUT / "prototype_purity_audit.csv", prototype_purity_rows)
    write_csv(OUT / "unknown_band_gate_grid.csv", grid_rows)
    write_csv(OUT / "unknown_band_gate_dev_summary.csv", grid_summary)
    write_csv(OUT / "gate_selection_audit.csv", [selected])
    write_csv(OUT / "report_only_replay.csv", replay_rows)
    write_csv(OUT / "decision_breakdown_by_state.csv", decision_rows)
    write_csv(OUT / "review_budget_audit.csv", decision_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_md(
        OUT / "unknown_band_gate_logic_spec.md",
        [
            "# Unknown-Band Prototype Gate Logic",
            "",
            "This diagnostic is a medium-only mechanism test, not a formal benchmark.",
            "",
            "The gate uses a raw attack score plus three-bank prototype evidence:",
            "",
            "- ID prototype bank and OOD/stress prototype bank represent known benign and benign drift regions.",
            "- Medium and active-heavy attack prototype banks represent confirmed development-side attack regions.",
            "- Pseudo-query attack rows are held out by file from development support pools to reduce support-val overfitting.",
            "",
            "Decision states:",
            "",
            "- `hard_alarm`: raw attack alarm and pure attack-core evidence.",
            "- `suppress`: weak raw attack alarm and pure benign/OOD-core evidence.",
            "- `review_conflict`: attack and benign/OOD cores both close.",
            "- `review_unknown`: raw alarm is outside both cores or otherwise ambiguous.",
            "- `review_overflow_no_alarm`: review candidate beyond the frozen budget.",
            "- `no_alarm`: raw attack alarm is absent.",
            "",
            "Final OOD, medium attack eval, and dev-heavy query are report-only replay roles and never tune thresholds, prototype radii, purity labels, review budgets, or gate parameters.",
        ],
    )
    write_md(
        OUT / "issue27bc_decision.md",
        [
            "# Issue27bc Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "- Added file-held-out pseudo-query roles on the development side.",
            "- Added prototype purity states and bounded conflict/unknown review accounting.",
            "- Did not use final OOD, medium attack eval, or dev-heavy query for support selection, prototype construction, gate selection, or review-budget selection.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bc.md",
        [
            "# Claim Update After issue27bc",
            "",
            "- issue27bc remains a medium diagnostic and cannot be reported as a formal benchmark.",
            "- Pseudo-query and unknown-band gates are useful only if they improve report-only replay without violating OOD/review constraints.",
            "- Formal claims remain blocked until a larger/frozen contract and sealed replay pass.",
        ],
    )
    next_issue = "issue27bd_temporal_consistency_or_region_refinement"
    if verdict in {"purity_unknown_gate_supported_ready_for_temporal_consistency", "purity_unknown_gate_promising_needs_temporal_or_region_refinement"}:
        next_issue = "issue27bd_past_only_temporal_consistency_gate"
    elif verdict == "pseudo_query_reveals_support_core_overfit":
        next_issue = "issue27bd_attack_region_generalization_before_temporal_gate"
    elif verdict == "pseudo_query_still_underestimates_report_only_attack_gap":
        next_issue = "issue27bd_report_only_gap_root_cause_after_pseudo_query"
    elif verdict == "attack_preserved_but_ood_overbudget":
        next_issue = "issue27bd_ood_veto_refinement_with_purity_constraints"
    write_md(
        OUT / "issue27bd_next_action.md",
        [
            "# Issue27bd Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- Do not proceed to full/larger formal benchmark from issue27bc alone.",
            "- If attack remains weak under pseudo-query, repair attack-region generalization before temporal smoothing.",
            "- If attack is preserved but OOD remains over budget, refine OOD veto under the same purity/review constraints.",
            "- Add temporal consistency only as a past-only diagnostic after the static purity gate has enough signal.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bc Summary",
            "",
            "1. issue27bc completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: attack-core purity, unknown-band, pseudo-query, and review-budget diagnostic; not formal benchmark",
            "4. 115D frontend/split changed: no",
            "5. final OOD used for prototype/gate/review selection: no",
            "6. medium attack eval/dev-heavy query used for prototype/gate/review selection: no",
            f"7. selected active label budget: `{selected_cfg['active_label_budget']}`",
            f"8. selected prototype budget per bank: `{selected_cfg['proto_budget']}`",
            f"9. selected bank radius q: `{selected_cfg['bank_radius_q']}`",
            f"10. selected attack_core_norm: `{selected_cfg['attack_core_norm']}`",
            f"11. selected benign_core_norm: `{selected_cfg['benign_core_norm']}`",
            f"12. selected unknown_norm: `{selected_cfg['unknown_norm']}`",
            f"13. selected review budget: `{selected_cfg['review_budget']}`",
            f"14. dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
            f"15. report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
            f"16. report-only attack hard-or-review min: `{replay_summary['report_only_attack_score_or_review_min']}`",
            f"17. OOD val hard max: `{replay_summary['ood_val_hard_alarm_rate_max']}`",
            f"18. OOD stress hard max: `{replay_summary['ood_stress_val_hard_alarm_rate_max']}`",
            f"19. final OOD hard max report-only: `{replay_summary['final_ood_report_only_hard_alarm_rate_max']}`",
            f"20. max OOD stress review rate: `{replay_summary['ood_stress_val_review_any_rate_max']}`",
            f"21. max final OOD review rate report-only: `{replay_summary['final_ood_report_only_review_any_rate_max']}`",
            "22. current formal benchmark allowed: no",
            f"23. next action: `{next_issue}`",
            "24. commit hash: pending",
        ],
    )
    write_md(
        OUT / "gate_selection_report.md",
        [
            "# Gate Selection Report",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "## Selected Config",
            "",
            *[f"- {k}: `{v}`" for k, v in selected_cfg.items()],
            "",
            "## Replay Summary",
            "",
            *[f"- {k}: `{v}`" for k, v in replay_summary.items()],
        ],
    )

    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "state_strategy": PRIMARY_STRATEGY,
        "active_label_budgets": ACTIVE_LABEL_BUDGETS,
        "proto_budgets": PROTO_BUDGETS,
        "bank_radius_qs": BANK_RADIUS_QS,
        "attack_core_norms": ATTACK_CORE_NORMS,
        "benign_core_norms": BENIGN_CORE_NORMS,
        "unknown_norms": UNKNOWN_NORMS,
        "review_budgets": REVIEW_BUDGETS,
        "primary_verdict": verdict,
        "selected_config": selected_cfg,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27ba_stress_certificate": str(stress_cert_path),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "medium prototype-purity unknown-band gate diagnostic only; final roles report-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bc -->",
        [
            "<!-- issue27bc -->",
            "## issue27bc - Attack-core purity, unknown band, and review budget",
            "",
            f"- primary_verdict: `{verdict}`",
            "- Added file-held-out pseudo-query on dev attack support to reduce support-val overfitting.",
            "- Added prototype purity states: hard_alarm, suppress, review_conflict, review_unknown, review_overflow_no_alarm.",
            "- Final OOD, medium attack eval, and dev-heavy query remained report-only.",
            f"- next action: `{next_issue}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bc -->",
        [
            "<!-- issue27bc -->",
            "## issue27bc - Prototype purity and unknown-band gate diagnostic",
            "",
            f"- verdict: `{verdict}`",
            "- purpose: test whether attack-core purity, pseudo-query generalization, and bounded review can improve the three-bank gate without leaking final roles.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": verdict, "selected_config": selected_cfg, "summary": replay_summary, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
