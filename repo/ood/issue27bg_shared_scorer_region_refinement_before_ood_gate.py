from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic as bd
import issue27bf_bounded_attack_region_bank as bf


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bg_shared_scorer_region_refinement_before_ood_gate_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BD = ROOT / "runs" / "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07"
ISSUE27BF = ROOT / "runs" / "issue27bf_bounded_attack_region_bank_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]

ACTIVE_LABEL_BUDGET = 64
WEIGHTING_POLICIES = [
    "uniform_sample",
    "equal_region_total",
    "medium_region_boost",
    "attack_total_parity",
    "medium_dominant_parity",
]
SUBSPACE_NAME = "HH_HpHp"
REGION_POLICY = "cluster_kcenter"
REGION_BALANCE = "equal_region_total"
PROTOTYPE_BUDGET = 128
REGION_MAX = 8
TOP_K = 3
INNER_RADIUS_Q = 0.75
OUTER_RADIUS_QS = [0.95, 0.99]
ATTACK_OUTER_NORMS = [1.0, 1.25, 1.5]
CONFLICT_SLACKS = [1.0, 2.0]
REVIEW_BUDGETS = [0.03, 0.05]
SCORE_FLOOR_Q = 0.0

ID_WEIGHT = 1.0
OOD_WEIGHT = 2.0
OOD_STRESS_WEIGHT = 2.0
BASE_ATTACK_WEIGHT = 4.0
ATTACK_GO_THRESHOLD = 0.93
ATTACK_WEAK_THRESHOLD = 0.85
OOD_STRESS_GUARD = 0.02
REVIEW_GUARD = 0.05
SUPPORT_RETENTION_FLOOR = 0.90


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    bf.write_csv(path, rows, fieldnames)


def write_md(path: Path, lines: list[str]) -> None:
    bf.write_md(path, lines)


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    bf.append_doc(path, marker, lines)


def sha256_file(path: Path) -> str:
    return bf.sha256_file(path)


def hash_indices(indices: np.ndarray) -> str:
    return bf.hash_indices(indices)


def rate(mask: np.ndarray) -> float:
    return bf.rate(mask)


def summarize(vals: list[float] | np.ndarray) -> dict[str, float]:
    return bf.summarize(vals)


def score_quantiles(scores: np.ndarray) -> dict[str, float]:
    arr = np.asarray(scores, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {k: float("nan") for k in ["mean", "q50", "q90", "q95", "q99", "min", "max"]}
    return {
        "mean": float(np.mean(arr)),
        "q50": float(np.quantile(arr, 0.50)),
        "q90": float(np.quantile(arr, 0.90)),
        "q95": float(np.quantile(arr, 0.95)),
        "q99": float(np.quantile(arr, 0.99)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


class SharedAttackHistGB:
    def __init__(self, seed: int, weighting_policy: str):
        self.seed = int(seed)
        self.weighting_policy = weighting_policy
        self.score_direction = 1.0
        self.score_direction_fixed = False
        self.model = HistGradientBoostingClassifier(
            max_depth=int(ar.FROZEN_CONFIG["max_depth"]),
            max_iter=int(ar.FROZEN_CONFIG["max_iter"]),
            learning_rate=float(ar.FROZEN_CONFIG["learning_rate"]),
            l2_regularization=float(ar.FROZEN_CONFIG["l2_regularization"]),
            random_state=self.seed,
        )
        self.fit_shape: dict[str, Any] = {}
        self.direction_check: dict[str, Any] = {}

    def _attack_weights(self, medium_rows: int, heavy_rows: int, normal_total_weight: float) -> tuple[float, float]:
        if self.weighting_policy == "uniform_sample":
            return BASE_ATTACK_WEIGHT, BASE_ATTACK_WEIGHT
        if self.weighting_policy == "equal_region_total":
            target_total = BASE_ATTACK_WEIGHT * max(1, max(medium_rows, heavy_rows))
            return target_total / max(1, medium_rows), target_total / max(1, heavy_rows)
        if self.weighting_policy == "medium_region_boost":
            target_total = BASE_ATTACK_WEIGHT * max(1, max(medium_rows, heavy_rows))
            return 1.5 * target_total / max(1, medium_rows), target_total / max(1, heavy_rows)
        if self.weighting_policy == "attack_total_parity":
            # Each attack family receives half the normal-side total weight.
            # This directly tests whether the shared scorer is still too
            # conservative because normal rows dominate the loss.
            return 0.5 * normal_total_weight / max(1, medium_rows), 0.5 * normal_total_weight / max(1, heavy_rows)
        if self.weighting_policy == "medium_dominant_parity":
            # Prior bank-only diagnostics showed medium/pseudo-medium is the
            # bottleneck, so this dev-side policy gives medium a bounded boost
            # without changing support rows or using report-only attacks.
            return 0.75 * normal_total_weight / max(1, medium_rows), 0.5 * normal_total_weight / max(1, heavy_rows)
        raise ValueError(self.weighting_policy)

    def fit(
        self,
        *,
        x_id: np.ndarray,
        x_ood: np.ndarray,
        x_ood_stress: np.ndarray,
        x_medium_attack: np.ndarray,
        x_heavy_attack: np.ndarray,
    ) -> None:
        normal_weight = len(x_id) * ID_WEIGHT + len(x_ood) * OOD_WEIGHT + len(x_ood_stress) * OOD_STRESS_WEIGHT
        medium_w, heavy_w = self._attack_weights(len(x_medium_attack), len(x_heavy_attack), normal_weight)
        xs = [x_id, x_ood, x_ood_stress, x_medium_attack, x_heavy_attack]
        ys = [
            np.zeros(len(x_id), dtype=np.int64),
            np.zeros(len(x_ood), dtype=np.int64),
            np.zeros(len(x_ood_stress), dtype=np.int64),
            np.ones(len(x_medium_attack), dtype=np.int64),
            np.ones(len(x_heavy_attack), dtype=np.int64),
        ]
        ws = [
            np.full(len(x_id), ID_WEIGHT, dtype=np.float64),
            np.full(len(x_ood), OOD_WEIGHT, dtype=np.float64),
            np.full(len(x_ood_stress), OOD_STRESS_WEIGHT, dtype=np.float64),
            np.full(len(x_medium_attack), medium_w, dtype=np.float64),
            np.full(len(x_heavy_attack), heavy_w, dtype=np.float64),
        ]
        x_train = np.vstack(xs)
        y_train = np.concatenate(ys)
        sample_weight = np.concatenate(ws)
        medium_weight = len(x_medium_attack) * medium_w
        heavy_weight = len(x_heavy_attack) * heavy_w
        self.fit_shape = {
            "seed": self.seed,
            "weighting_policy": self.weighting_policy,
            "id_rows": int(len(x_id)),
            "ood_rows": int(len(x_ood)),
            "ood_stress_rows": int(len(x_ood_stress)),
            "medium_attack_rows": int(len(x_medium_attack)),
            "heavy_attack_rows": int(len(x_heavy_attack)),
            "id_weight": ID_WEIGHT,
            "ood_weight": OOD_WEIGHT,
            "ood_stress_weight": OOD_STRESS_WEIGHT,
            "medium_attack_per_row_weight": float(medium_w),
            "heavy_attack_per_row_weight": float(heavy_w),
            "normal_total_weight": float(normal_weight),
            "medium_attack_total_weight": float(medium_weight),
            "heavy_attack_total_weight": float(heavy_weight),
            "weighted_normal_to_attack_ratio": float(normal_weight / max(1.0, medium_weight + heavy_weight)),
            "total_rows": int(len(x_train)),
        }
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        self._fix_score_direction(np.vstack([x_id, x_ood, x_ood_stress]), np.vstack([x_medium_attack, x_heavy_attack]))

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"attack class 1 missing: {classes}")
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_score_direction(self, x_benign: np.ndarray, x_attack: np.ndarray) -> None:
        raw_benign = self.raw_score(x_benign)
        raw_attack = self.raw_score(x_attack)
        if float(np.mean(raw_attack)) < float(np.mean(raw_benign)):
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "benign_raw_mean": float(np.mean(raw_benign)),
            "attack_raw_mean": float(np.mean(raw_attack)),
            "benign_score_mean": float(np.mean(self.score(x_benign))),
            "attack_score_mean": float(np.mean(self.score(x_attack))),
            "score_direction": float(self.score_direction),
            "score_direction_fixed": bool(self.score_direction_fixed),
        }


def shared_score_bundle(model: SharedAttackHistGB, threshold: float, x: np.ndarray) -> dict[str, np.ndarray]:
    s = model.score(x)
    margin = s - float(threshold)
    return {
        "shared_score": s,
        "score_strength": margin,
        "raw_alarm": margin > 0.0,
    }


def make_shared_bank_inputs(
    x: np.ndarray,
    sidecar: list[dict[str, str]],
    new_x: np.ndarray,
    new_sidecar: list[dict[str, str]],
    model: SharedAttackHistGB,
    threshold: float,
    medium_train: np.ndarray,
    medium_val: np.ndarray,
    medium_pseudo: np.ndarray,
    heavy_train: np.ndarray,
    heavy_val: np.ndarray,
    heavy_pseudo: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, Any]], np.ndarray, list[dict[str, Any]], np.ndarray]:
    train_x = np.vstack([x[medium_train], new_x[heavy_train]])
    train_global = np.concatenate([medium_train, -1 - heavy_train]).astype(np.int64)
    train_scores = [
        shared_score_bundle(model, threshold, x[medium_train]),
        shared_score_bundle(model, threshold, new_x[heavy_train]),
    ]
    train_meta: list[dict[str, Any]] = []
    for family, idxs, rows, bundle in [
        ("medium", medium_train, sidecar, train_scores[0]),
        ("heavy", heavy_train, new_sidecar, train_scores[1]),
    ]:
        for pos, idx in enumerate(idxs):
            train_meta.append(
                {
                    "family": family,
                    "global_index": int(idx) if family == "medium" else int(-1 - idx),
                    "source_key": bf.source_key(rows[int(idx)], family),
                    "score_strength": float(bundle["score_strength"][pos]),
                }
            )
    calib_parts = [
        ("val", "medium", x[medium_val], medium_val, sidecar),
        ("val", "heavy", new_x[heavy_val], heavy_val, new_sidecar),
        ("pseudo", "medium", x[medium_pseudo], medium_pseudo, sidecar),
        ("pseudo", "heavy", new_x[heavy_pseudo], heavy_pseudo, new_sidecar),
    ]
    calib_xs: list[np.ndarray] = []
    calib_meta: list[dict[str, Any]] = []
    for kind, family, x_part, idxs, rows in calib_parts:
        bundle = shared_score_bundle(model, threshold, x_part)
        calib_xs.append(x_part)
        for pos, idx in enumerate(idxs):
            calib_meta.append(
                {
                    "calib_kind": kind,
                    "family": family,
                    "global_index": int(idx) if family == "medium" else int(-1 - idx),
                    "source_key": bf.source_key(rows[int(idx)], family),
                    "score_strength": float(bundle["score_strength"][pos]),
                }
            )
    return train_x, train_meta, np.vstack(calib_xs), calib_meta, train_global


def aggregate_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "scorer_kind",
        "weighting_policy",
        "subspace_name",
        "region_policy",
        "prototype_budget",
        "region_max",
        "top_k",
        "inner_radius_q",
        "outer_radius_q",
        "attack_outer_norm",
        "benign_core_norm",
        "conflict_slack",
        "review_budget",
    ]
    metrics = [
        "id_hard",
        "ood_hard",
        "stress_hard",
        "id_review",
        "ood_review",
        "stress_review",
        "support_medium_hard",
        "support_heavy_hard",
        "pseudo_medium_hard",
        "pseudo_heavy_hard",
        "dev_attack_min",
        "dev_pseudo_min",
        "dev_review_max",
        "dev_score",
        "total_prototypes",
        "region_count",
    ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(group)
        for metric in metrics:
            stats = summarize([float(g[metric]) for g in group])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["attack_go_all_seeds"] = all(float(g["dev_attack_min"]) >= ATTACK_GO_THRESHOLD for g in group)
        row["attack_weak_all_seeds"] = all(float(g["dev_attack_min"]) >= ATTACK_WEAK_THRESHOLD for g in group)
        row["ood_stress_guard_all_seeds"] = all(float(g["stress_hard"]) <= OOD_STRESS_GUARD for g in group)
        row["review_guard_all_seeds"] = all(float(g["dev_review_max"]) <= REVIEW_GUARD for g in group)
        row["support_retention_all_seeds"] = all(
            float(g["support_medium_hard"]) >= SUPPORT_RETENTION_FLOOR and float(g["support_heavy_hard"]) >= SUPPORT_RETENTION_FLOOR for g in group
        )
        out.append(row)
    return out


def choose_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        r
        for r in rows
        if str(r["ood_stress_guard_all_seeds"]) == "True"
        and str(r["review_guard_all_seeds"]) == "True"
        and str(r["support_retention_all_seeds"]) == "True"
    ]
    pool = eligible or rows
    return max(
        pool,
        key=lambda r: (
            str(r.get("attack_go_all_seeds")) == "True",
            float(r["dev_attack_min_min"]),
            float(r["dev_pseudo_min_min"]),
            str(r.get("attack_weak_all_seeds")) == "True",
            -float(r["stress_hard_max"]),
            -float(r["dev_review_max_max"]),
        ),
    )


def verdict_from_summary(summary: dict[str, Any]) -> str:
    if bool(summary["forbidden_role_access"]):
        return "shared_scorer_blocked_by_forbidden_role_access"
    if float(summary["dev_attack_hard_min"]) >= ATTACK_GO_THRESHOLD and float(summary["ood_stress_hard_max"]) <= OOD_STRESS_GUARD and float(summary["dev_review_max"]) <= REVIEW_GUARD:
        return "shared_scorer_attack_gate_passed_ready_for_ood_repair"
    if float(summary["dev_attack_hard_min"]) >= ATTACK_WEAK_THRESHOLD:
        return "shared_scorer_attack_improved_but_below_093"
    if bool(summary["medium_dropped"]) and not bool(summary["heavy_dropped"]):
        return "shared_scorer_medium_retention_failure"
    if bool(summary["heavy_dropped"]) and not bool(summary["medium_dropped"]):
        return "shared_scorer_heavy_retention_failure"
    return "shared_scorer_no_sufficient_attack_recovery"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    bd_config_path = ISSUE27BD / "config.json"
    bf_summary_path = ISSUE27BF / "summary.md"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    selected_bd = json.loads(bd_config_path.read_text(encoding="utf-8"))["selected_config"]
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]
    subspaces = bd.build_subspaces(asset["schema"])
    sub_idx = subspaces[SUBSPACE_NAME]

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

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "actual_sha256": sha256_file(stress_cert_path), "hash_match": True},
        {"artifact": "issue27bd_config", "path": str(bd_config_path), "actual_sha256": sha256_file(bd_config_path), "hash_match": True},
        {"artifact": "issue27bf_summary", "path": str(bf_summary_path), "actual_sha256": sha256_file(bf_summary_path), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    grid_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    score_distribution_rows: list[dict[str, Any]] = []
    selected_inventory_rows: list[dict[str, Any]] = []
    selected_route_rows: list[dict[str, Any]] = []
    selected_coverage_rows: list[dict[str, Any]] = []
    selected_conflict_rows: list[dict[str, Any]] = []
    selected_cost_rows: list[dict[str, Any]] = []
    selected_retention_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0 or len(medium_pseudo) == 0:
            continue
        split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )
        role_x_dev = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": new_x[heavy_val],
            "pseudo_medium_query": x[medium_pseudo],
            "pseudo_heavy_query": new_x[heavy_pseudo],
        }
        for weighting_policy in WEIGHTING_POLICIES:
            model = SharedAttackHistGB(seed, weighting_policy)
            model.fit(
                x_id=x[id_fit],
                x_ood=x[ood_train],
                x_ood_stress=stress_x[stress_train],
                x_medium_attack=x[medium_train],
                x_heavy_attack=new_x[heavy_train],
            )
            training_rows.append({**model.fit_shape, **model.direction_check})
            score_id = model.score(x[id_calib])
            score_ood = model.score(x[ood_val])
            support_val_x = np.vstack([x[medium_val], new_x[heavy_val]])
            threshold = ay.threshold_for(score_id, score_ood, model.score(support_val_x))
            role_scores = {role: shared_score_bundle(model, float(threshold["threshold"]), x_role) for role, x_role in role_x_dev.items()}
            for role, bundle in role_scores.items():
                score_distribution_rows.append(
                    {
                        "seed": seed,
                        "weighting_policy": weighting_policy,
                        "role": role,
                        **{f"score_{k}": v for k, v in score_quantiles(bundle["score_strength"]).items()},
                        "raw_alarm_rate": rate(bundle["raw_alarm"]),
                    }
                )
            train_x, train_meta, calib_x, calib_meta, train_global = make_shared_bank_inputs(
                x,
                sidecar,
                new_x,
                new_sidecar,
                model,
                float(threshold["threshold"]),
                medium_train,
                medium_val,
                medium_pseudo,
                heavy_train,
                heavy_val,
                heavy_pseudo,
            )
            benign_banks = bf.build_benign_banks(x, stress_x, sub_idx, id_fit, id_calib, ood_train, ood_val, stress_train, stress_val)
            bank = bf.BoundedAttackRegionBank(
                train_x=train_x,
                train_meta=train_meta,
                calib_x=calib_x,
                calib_meta=calib_meta,
                subspace_idx=sub_idx,
                region_policy=REGION_POLICY,
                region_balance=REGION_BALANCE,
                prototype_budget=PROTOTYPE_BUDGET,
                region_max=REGION_MAX,
                inner_radius_q=INNER_RADIUS_Q,
                outer_radius_q=0.95,
                score_floor_q=SCORE_FLOOR_Q,
            )
            weak_ceiling = float(
                np.quantile(
                    np.concatenate([role_scores["support_medium_val"]["score_strength"], role_scores["support_heavy_val"]["score_strength"]]),
                    float(selected_bd["weak_score_q"]),
                )
            )
            for outer_q in OUTER_RADIUS_QS:
                # Rebuild only when the selected radius quantile changes; the train
                # rows/prototypes stay fixed, but radius calibration changes.
                if outer_q != bank.outer_radius_q:
                    bank = bf.BoundedAttackRegionBank(
                        train_x=train_x,
                        train_meta=train_meta,
                        calib_x=calib_x,
                        calib_meta=calib_meta,
                        subspace_idx=sub_idx,
                        region_policy=REGION_POLICY,
                        region_balance=REGION_BALANCE,
                        prototype_budget=PROTOTYPE_BUDGET,
                        region_max=REGION_MAX,
                        inner_radius_q=INNER_RADIUS_Q,
                        outer_radius_q=outer_q,
                        score_floor_q=SCORE_FLOOR_Q,
                    )
                for attack_outer_norm in ATTACK_OUTER_NORMS:
                    for conflict_slack in CONFLICT_SLACKS:
                        for review_budget in REVIEW_BUDGETS:
                            metrics: dict[str, float] = {}
                            for role, x_role in role_x_dev.items():
                                pre = bf.precompute_role(x_role, sub_idx, bank, benign_banks, role_scores[role], TOP_K)
                                state, masks = bf.apply_region_bank_gate(
                                    pre["raw_alarm"],
                                    pre["score_strength"],
                                    pre["attack_inner"],
                                    pre["attack_outer"],
                                    pre["benign_inner"],
                                    pre["benign_outer"],
                                    pre["region_score_floor"],
                                    pre["region_strong_floor"],
                                    attack_outer_norm,
                                    float(selected_bd["benign_core_norm"]),
                                    conflict_slack,
                                    weak_ceiling,
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
                            grid_rows.append(
                                {
                                    "seed": seed,
                                    "scorer_kind": "shared_histgb",
                                    "weighting_policy": weighting_policy,
                                    "subspace_name": SUBSPACE_NAME,
                                    "region_policy": REGION_POLICY,
                                    "prototype_budget": PROTOTYPE_BUDGET,
                                    "region_max": REGION_MAX,
                                    "top_k": TOP_K,
                                    "inner_radius_q": INNER_RADIUS_Q,
                                    "outer_radius_q": outer_q,
                                    "attack_outer_norm": attack_outer_norm,
                                    "benign_core_norm": float(selected_bd["benign_core_norm"]),
                                    "conflict_slack": conflict_slack,
                                    "review_budget": review_budget,
                                    **metrics,
                                    "dev_attack_min": dev_attack_min,
                                    "dev_pseudo_min": dev_pseudo_min,
                                    "dev_review_max": dev_review_max,
                                    "total_prototypes": bank.total_prototypes,
                                    "region_count": len(bank.regions),
                                    "dev_score": dev_attack_min + 0.25 * dev_pseudo_min - 0.4 * metrics["stress_hard"] - 0.2 * dev_review_max,
                                    "threshold": float(threshold["threshold"]),
                                    "threshold_source": threshold.get("threshold_source"),
                                    "selection_uses_final_ood": False,
                                    "selection_uses_attack_eval": False,
                                    "selection_uses_dev_heavy_query": False,
                                }
                            )

    grid_summary = aggregate_grid(grid_rows)
    selected = choose_config(grid_summary)
    selected_cfg = {
        "scorer_kind": str(selected["scorer_kind"]),
        "weighting_policy": str(selected["weighting_policy"]),
        "subspace_name": str(selected["subspace_name"]),
        "region_policy": str(selected["region_policy"]),
        "prototype_budget": int(selected["prototype_budget"]),
        "region_max": int(selected["region_max"]),
        "top_k": int(selected["top_k"]),
        "inner_radius_q": float(selected["inner_radius_q"]),
        "outer_radius_q": float(selected["outer_radius_q"]),
        "attack_outer_norm": float(selected["attack_outer_norm"]),
        "benign_core_norm": float(selected["benign_core_norm"]),
        "conflict_slack": float(selected["conflict_slack"]),
        "review_budget": float(selected["review_budget"]),
    }

    replay_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, _ = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, _ = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, _ = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        model = SharedAttackHistGB(seed, selected_cfg["weighting_policy"])
        model.fit(
            x_id=x[id_fit],
            x_ood=x[ood_train],
            x_ood_stress=stress_x[stress_train],
            x_medium_attack=x[medium_train],
            x_heavy_attack=new_x[heavy_train],
        )
        threshold = ay.threshold_for(model.score(x[id_calib]), model.score(x[ood_val]), model.score(np.vstack([x[medium_val], new_x[heavy_val]])))
        train_x, train_meta, calib_x, calib_meta, train_global = make_shared_bank_inputs(
            x,
            sidecar,
            new_x,
            new_sidecar,
            model,
            float(threshold["threshold"]),
            medium_train,
            medium_val,
            medium_pseudo,
            heavy_train,
            heavy_val,
            heavy_pseudo,
        )
        bank = bf.BoundedAttackRegionBank(
            train_x=train_x,
            train_meta=train_meta,
            calib_x=calib_x,
            calib_meta=calib_meta,
            subspace_idx=sub_idx,
            region_policy=selected_cfg["region_policy"],
            region_balance=REGION_BALANCE,
            prototype_budget=selected_cfg["prototype_budget"],
            region_max=selected_cfg["region_max"],
            inner_radius_q=selected_cfg["inner_radius_q"],
            outer_radius_q=selected_cfg["outer_radius_q"],
            score_floor_q=SCORE_FLOOR_Q,
        )
        selected_inventory_rows.extend(bank.inventory_rows(seed, selected_cfg, train_global))
        benign_banks = bf.build_benign_banks(x, stress_x, sub_idx, id_fit, id_calib, ood_train, ood_val, stress_train, stress_val)
        weak_ceiling = float(
            np.quantile(
                np.concatenate(
                    [
                        shared_score_bundle(model, float(threshold["threshold"]), x[medium_val])["score_strength"],
                        shared_score_bundle(model, float(threshold["threshold"]), new_x[heavy_val])["score_strength"],
                    ]
                ),
                float(selected_bd["weak_score_q"]),
            )
        )
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
            "threshold": float(threshold["threshold"]),
            "selection_uses_final_ood": False,
            "selection_uses_attack_eval": False,
            "selection_uses_dev_heavy_query": False,
        }
        for role, x_role in role_x.items():
            bundle = shared_score_bundle(model, float(threshold["threshold"]), x_role)
            pre = bf.precompute_role(x_role, sub_idx, bank, benign_banks, bundle, selected_cfg["top_k"])
            state, masks = bf.apply_region_bank_gate(
                pre["raw_alarm"],
                pre["score_strength"],
                pre["attack_inner"],
                pre["attack_outer"],
                pre["benign_inner"],
                pre["benign_outer"],
                pre["region_score_floor"],
                pre["region_strong_floor"],
                selected_cfg["attack_outer_norm"],
                selected_cfg["benign_core_norm"],
                selected_cfg["conflict_slack"],
                weak_ceiling,
                selected_cfg["review_budget"],
            )
            m = bf.role_metrics(role, state, masks, pre, pre["top1_region"])
            for key, val in m.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = val
            selected_route_rows.append({"seed": seed, **selected_cfg, **m})
            selected_conflict_rows.append(
                {
                    "seed": seed,
                    **selected_cfg,
                    "role": role,
                    "rows": int(len(x_role)),
                    "attack_outer_p50": m["attack_outer_p50"],
                    "attack_outer_p95": m["attack_outer_p95"],
                    "benign_outer_p50": m["benign_outer_p50"],
                    "benign_outer_p95": float(np.quantile(pre["benign_outer"], 0.95)) if len(pre["benign_outer"]) else float("nan"),
                    "score_strength_mean": float(np.mean(pre["score_strength"])) if len(pre["score_strength"]) else float("nan"),
                }
            )
            for rid, region in enumerate(bank.regions):
                mask_top = pre["top1_region"] == rid
                selected_coverage_rows.append(
                    {
                        "seed": seed,
                        **selected_cfg,
                        "role": role,
                        "region_id": region.region_id,
                        "source_family": region.source_family,
                        "top1_route_rate": rate(mask_top),
                        "hard_alarm_rate_with_top1_region": rate(masks["hard_alarm"] & mask_top),
                        "rows": int(len(x_role)),
                    }
                )
        replay_rows.append(replay_row)
        selected_cost_rows.append(
            {
                "seed": seed,
                **selected_cfg,
                "subspace_dim": int(len(sub_idx)),
                "region_count": int(len(bank.regions)),
                "total_prototypes": int(bank.total_prototypes),
                "centroid_distance_ops_per_raw_alarm": int(len(bank.regions) * len(sub_idx)),
                "prototype_distance_ops_per_raw_alarm_est": int(min(bank.total_prototypes, selected_cfg["top_k"] * np.ceil(bank.total_prototypes / max(1, len(bank.regions)))) * len(sub_idx)),
                "raw_score_low_can_skip_bank": True,
            }
        )
        selected_retention_rows.append(
            {
                "seed": seed,
                **selected_cfg,
                "support_medium_hard": replay_row["support_medium_val_hard_alarm_rate"],
                "support_heavy_hard": replay_row["support_heavy_val_hard_alarm_rate"],
                "pseudo_medium_hard": replay_row["pseudo_medium_query_hard_alarm_rate"],
                "pseudo_heavy_hard": replay_row["pseudo_heavy_query_hard_alarm_rate"],
            }
        )

    replay_summary = {
        "dev_attack_hard_min": float(
            min(
                min(float(r["support_medium_val_hard_alarm_rate"]) for r in replay_rows),
                min(float(r["support_heavy_val_hard_alarm_rate"]) for r in replay_rows),
                min(float(r["pseudo_medium_query_hard_alarm_rate"]) for r in replay_rows),
                min(float(r["pseudo_heavy_query_hard_alarm_rate"]) for r in replay_rows),
            )
        ),
        "report_only_attack_hard_min": float(
            min(
                min(float(r["medium_attack_eval_report_only_hard_alarm_rate"]) for r in replay_rows),
                min(float(r["dev_heavy_query_report_only_hard_alarm_rate"]) for r in replay_rows),
            )
        ),
        "ood_stress_hard_max": float(max(float(r["ood_stress_val_hard_alarm_rate"]) for r in replay_rows)),
        "final_ood_hard_max": float(max(float(r["final_ood_report_only_hard_alarm_rate"]) for r in replay_rows)),
        "dev_review_max": float(max(max(float(r["id_calib_review_any_rate"]), float(r["ood_val_review_any_rate"]), float(r["ood_stress_val_review_any_rate"])) for r in replay_rows)),
        "final_review_max": float(max(float(r["final_ood_report_only_review_any_rate"]) for r in replay_rows)),
        "forbidden_role_access": False,
        "medium_dropped": bool(min(float(r["pseudo_medium_query_hard_alarm_rate"]) for r in replay_rows) < SUPPORT_RETENTION_FLOOR),
        "heavy_dropped": bool(min(float(r["pseudo_heavy_query_hard_alarm_rate"]) for r in replay_rows) < SUPPORT_RETENTION_FLOOR),
    }
    verdict = verdict_from_summary(replay_summary)
    next_action = (
        "issue27bh_attack_preserving_ood_gate_after_shared_scorer"
        if verdict == "shared_scorer_attack_gate_passed_ready_for_ood_repair"
        else "issue27bh_attack_scorer_region_design_rethink_before_ood_gate"
    )

    role_access_rows = [
        {
            "object": "shared_attack_scorer",
            "operation": "fit_and_threshold_selection",
            "source_roles": "id_fit|ood_train|ood_stress_train|medium_attack_train|active_heavy_attack_train|id_calib|ood_val|support_medium_val|support_heavy_val",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
        },
        {
            "object": "region_bank",
            "operation": "prototype_radius_selection",
            "source_roles": "medium_train|medium_val|medium_pseudo|heavy_train|heavy_val|heavy_pseudo",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
        },
        {
            "object": "grid_selection",
            "operation": "select_shared_scorer_region_gate",
            "source_roles": "id_calib|ood_val|ood_stress_val|support_medium_val|support_heavy_val|pseudo_medium_query|pseudo_heavy_query",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
        },
        {
            "object": "report_only_replay",
            "operation": "score_only_after_frozen_selection",
            "source_roles": "final_ood_report_only|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "uses_final_ood": True,
            "uses_attack_eval": True,
            "uses_dev_heavy_query": True,
            "forbidden_selection_access": False,
        },
    ]

    baseline_rows = [
        {
            "baseline": "issue27bf_two_head_bounded_bank",
            "source_file": str(ISSUE27BF / "summary.md"),
            "primary_verdict": "bounded_attack_bank_heavy_gain_medium_retention_failure",
            "dev_attack_hard_min": 0.6428571428571429,
            "report_only_attack_hard_min": 0.6415,
            "ood_stress_hard_max": 0.002456140350877193,
            "final_ood_hard_max_report_only": 0.154,
            "notes": "previous bank-only run; raw scorer unchanged two-head replay",
        },
        {
            "baseline": "issue27bg_shared_selected",
            "source_file": str(OUT / "summary.md"),
            "primary_verdict": verdict,
            "dev_attack_hard_min": replay_summary["dev_attack_hard_min"],
            "report_only_attack_hard_min": replay_summary["report_only_attack_hard_min"],
            "ood_stress_hard_max": replay_summary["ood_stress_hard_max"],
            "final_ood_hard_max_report_only": replay_summary["final_ood_hard_max"],
            "notes": "shared scorer + bounded region bank; report-only not used for selection",
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "support_split_audit.csv", split_rows)
    write_csv(OUT / "shared_scorer_training_audit.csv", training_rows)
    write_csv(OUT / "weighting_strategy_grid.csv", grid_rows)
    write_csv(OUT / "weighting_strategy_summary.csv", grid_summary)
    write_csv(OUT / "gate_selection_audit.csv", [selected])
    write_csv(OUT / "region_bank_inventory.csv", selected_inventory_rows)
    write_csv(OUT / "route_breakdown_by_role.csv", selected_route_rows)
    write_csv(OUT / "region_coverage_by_role.csv", selected_coverage_rows)
    write_csv(OUT / "region_conflict_audit.csv", selected_conflict_rows)
    write_csv(OUT / "latency_cost_estimate.csv", selected_cost_rows)
    write_csv(OUT / "medium_retention_audit.csv", selected_retention_rows)
    write_csv(OUT / "heavy_gain_audit.csv", selected_retention_rows)
    write_csv(OUT / "ood_shell_leakage_audit.csv", selected_conflict_rows)
    write_csv(OUT / "region_score_distribution.csv", score_distribution_rows)
    write_csv(OUT / "report_only_replay.csv", replay_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(OUT / "baseline_comparison.csv", baseline_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)

    write_md(
        OUT / "shared_scorer_region_refinement_design.md",
        [
            "# Shared Scorer Region Refinement Design",
            "",
            "This run replaces the issue27bd/issue27bf two-head raw scorer with one shared HistGB attack scorer.",
            "",
            "- Fixed frontend: Gotham Kitsune115 115D.",
            "- Fixed split: issue27af/issue27ba/issue27au roles.",
            "- Positives: medium attack train + active heavy confirmed train.",
            "- Negatives: ID train + OOD train + OOD stress train.",
            "- Region bank: bounded HH_HpHp cluster-kcenter evidence layer, not the main classifier.",
            "- Selection roles exclude final OOD, medium attack eval, and dev-heavy query.",
            "- Go gate for OOD repair: attack hard min >= 0.93, OOD stress <=2%, review <=5%.",
        ],
    )
    write_md(
        OUT / "issue27bg_decision.md",
        [
            "# issue27bg Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- selected config: `{json.dumps(selected_cfg, sort_keys=True)}`",
            f"- dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
            f"- report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
            f"- OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`",
            f"- final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`",
            f"- dev review max: `{replay_summary['dev_review_max']}`",
            "",
            "Go/No-Go: OOD-gate repair is allowed only if attack hard min >= 0.93 with OOD stress <=2% and review <=5%.",
        ],
    )
    write_md(
        OUT / "issue27bh_next_action.md",
        [
            "# Issue27bh Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If attack >=0.93, proceed to attack-preserving OOD gate repair.",
            "- If attack remains below 0.93, do not tune OOD gate; rethink attack-side scorer/region design first.",
            "- Do not run full/larger formal benchmark from this medium diagnostic.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bg.md",
        [
            "# Claim Update After issue27bg",
            "",
            "- issue27bg is a medium diagnostic, not a formal benchmark.",
            "- It tests whether a shared attack scorer can improve attack retention before OOD-gate repair.",
            "- Final/report-only roles remain sealed for selection.",
            "- Formal claims still require larger/full assets, final OOD safety, and pre-registered configuration.",
        ],
    )
    summary_lines = [
        "# issue27bg Summary",
        "",
        "1. issue27bg completed: yes",
        f"2. primary_verdict: `{verdict}`",
        "3. task type: shared scorer + bounded region bank diagnostic; not formal benchmark",
        "4. 115D frontend changed: no",
        "5. split changed: no",
        "6. raw scorer changed: yes, from issue27bd two-head replay to shared HistGB attack scorer",
        f"7. selected config: `{json.dumps(selected_cfg, sort_keys=True)}`",
        f"8. dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
        f"9. report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
        f"10. OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`",
        f"11. final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`",
        f"12. dev review max: `{replay_summary['dev_review_max']}`",
        f"13. final review max report-only: `{replay_summary['final_review_max']}`",
        f"14. attack >=0.93 gate passed: `{replay_summary['dev_attack_hard_min'] >= ATTACK_GO_THRESHOLD}`",
        f"15. OOD stress <=2% guard passed: `{replay_summary['ood_stress_hard_max'] <= OOD_STRESS_GUARD}`",
        f"16. review <=5% guard passed: `{replay_summary['dev_review_max'] <= REVIEW_GUARD}`",
        "17. final/report-only used for selection: no",
        "18. current formal benchmark allowed: no",
        f"19. next action: `{next_action}`",
        "20. commit hash: reported in final response",
    ]
    write_md(OUT / "summary.md", summary_lines)

    config = {
        "issue": ISSUE,
        "primary_strategy": PRIMARY_STRATEGY,
        "seeds": SEEDS,
        "active_label_budget": ACTIVE_LABEL_BUDGET,
        "weighting_policies": WEIGHTING_POLICIES,
        "selected_config": selected_cfg,
        "primary_verdict": verdict,
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "ood_stress_guard": OOD_STRESS_GUARD,
        "review_guard": REVIEW_GUARD,
        "report_only_selection_forbidden": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "command": f"python repo/ood/{Path(__file__).name}",
                "uses_final_ood_for_selection": False,
                "uses_attack_eval_for_selection": False,
                "uses_dev_heavy_query_for_selection": False,
                "formal_benchmark": False,
                "frontend": "Gotham Kitsune115",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bg -->",
        [
            "<!-- issue27bg -->",
            "## issue27bg - Shared scorer region refinement before OOD gate",
            "",
            f"- primary_verdict: `{verdict}`",
            "- purpose: replace the issue27bd/issue27bf two-head raw scorer with one shared 115D HistGB attack scorer plus bounded region evidence.",
            f"- dev attack hard min: `{replay_summary['dev_attack_hard_min']}`; report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`.",
            f"- OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`; final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`.",
            "- formal benchmark remains disallowed.",
            f"- next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bg -->",
        [
            "<!-- issue27bg -->",
            "## issue27bg - Shared scorer region refinement diagnostic",
            "",
            f"- verdict: `{verdict}`",
            f"- outputs: `runs/{ISSUE}/`.",
            "- no 115D frontend or split changes; no full/larger formal benchmark.",
            f"- attack hard min gate 0.93 passed: `{replay_summary['dev_attack_hard_min'] >= ATTACK_GO_THRESHOLD}`.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file():
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": verdict, "selected_config": selected_cfg, "summary": replay_summary, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
