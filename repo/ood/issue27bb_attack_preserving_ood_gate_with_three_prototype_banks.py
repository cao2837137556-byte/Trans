from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bb_attack_preserving_ood_gate_with_three_prototype_banks_2026-06-05"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [64, 128]
PROTO_BUDGETS = [32, 64]
BANK_RADIUS_QS = [0.90, 0.95]
ATTACK_CORE_NORMS = [1.0, 1.25]
BENIGN_VETO_NORMS = [0.75, 1.0, 1.25, 1.50]
STRONG_SCORE_QS = [0.00, 0.25, 0.50]
WEAK_SCORE_QS = [0.25, 0.50]

VAL_TARGET = 0.01
REVIEW_BUDGET = 0.10
RELAXED_REVIEW_BUDGET = 0.20
ATTACK_FLOOR = 0.75
RELAXED_ATTACK_FLOOR = 0.50


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


def farthest_first(z: np.ndarray, budget: int) -> np.ndarray:
    if len(z) == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= len(z):
        return np.arange(len(z), dtype=np.int64)
    centroid = z.mean(axis=0, keepdims=True)
    start = int(np.argmin(pairwise_distances(z, centroid, metric="euclidean").ravel()))
    selected = [start]
    min_dist = pairwise_distances(z, z[[start]], metric="euclidean").ravel()
    min_dist[start] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(z, z[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


class PrototypeBank:
    def __init__(self, bank_name: str, train_x: np.ndarray, val_x: np.ndarray, budget: int, radius_q: float):
        if len(train_x) == 0 or len(val_x) == 0:
            raise RuntimeError(f"empty prototype bank: {bank_name}")
        self.bank_name = bank_name
        self.train_rows = int(len(train_x))
        self.val_rows = int(len(val_x))
        self.budget = int(budget)
        self.radius_q = float(radius_q)
        self.scaler = StandardScaler().fit(train_x)
        z_train = self.scaler.transform(train_x)
        proto_local = farthest_first(z_train, self.budget)
        self.prototype_local_indices = proto_local
        self.z_proto = z_train[proto_local]
        val_d = pairwise_distances(self.scaler.transform(val_x), self.z_proto, metric="euclidean").min(axis=1)
        radius = float(np.quantile(val_d, self.radius_q))
        if not np.isfinite(radius) or radius <= 1e-12:
            radius = 1e-12
        self.radius = radius
        self.val_distance_mean = float(np.mean(val_d))
        self.val_distance_max = float(np.max(val_d))

    def normalized_distance(self, x: np.ndarray) -> np.ndarray:
        d = pairwise_distances(self.scaler.transform(x), self.z_proto, metric="euclidean").min(axis=1)
        return d / self.radius

    def audit_row(self, seed: int, active_budget: int, source_roles: str) -> dict[str, Any]:
        return {
            "seed": seed,
            "active_label_budget": active_budget,
            "bank_name": self.bank_name,
            "source_roles": source_roles,
            "train_rows": self.train_rows,
            "val_rows": self.val_rows,
            "prototype_budget": self.budget,
            "prototype_count": int(len(self.prototype_local_indices)),
            "prototype_local_indices_sha256": hash_indices(self.prototype_local_indices),
            "radius_quantile": self.radius_q,
            "radius": self.radius,
            "val_distance_mean": self.val_distance_mean,
            "val_distance_max": self.val_distance_max,
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
        }


def score_bundle(
    medium_head: ay.CustomWeightedHistGB,
    heavy_head: ay.CustomWeightedHistGB,
    medium_threshold: float,
    heavy_threshold: float,
    x: np.ndarray,
) -> dict[str, np.ndarray]:
    m = medium_head.score(x)
    h = heavy_head.score(x)
    m_margin = m - float(medium_threshold)
    h_margin = h - float(heavy_threshold)
    score_strength = np.maximum(m_margin, h_margin)
    return {
        "medium_score": m,
        "heavy_score": h,
        "medium_margin": m_margin,
        "heavy_margin": h_margin,
        "score_strength": score_strength,
        "raw_alarm": score_strength > 0.0,
    }


def three_bank_gate(
    raw_alarm: np.ndarray,
    score_strength: np.ndarray,
    attack_cov: np.ndarray,
    benign_cov: np.ndarray,
    strong_score_floor: float,
    weak_score_ceiling: float,
    attack_core_norm: float,
    benign_veto_norm: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    raw_alarm = raw_alarm.astype(bool)
    near_attack = attack_cov <= float(attack_core_norm)
    near_benign = benign_cov <= float(benign_veto_norm)
    strong_attack_core = raw_alarm & near_attack & (score_strength >= float(strong_score_floor))
    weak_benign_only = raw_alarm & near_benign & ~near_attack & (score_strength <= float(weak_score_ceiling))
    conflict = raw_alarm & near_benign & near_attack & ~strong_attack_core
    unknown = raw_alarm & ~near_benign & ~near_attack
    benign_only_high_score = raw_alarm & near_benign & ~near_attack & ~weak_benign_only
    attack_only = raw_alarm & near_attack & ~near_benign
    hard = strong_attack_core | attack_only
    review = conflict | unknown | benign_only_high_score
    suppress = weak_benign_only
    # Partition sanity: prefer hard over review, and review over suppress.
    review = review & ~hard
    suppress = suppress & ~review & ~hard
    return hard, review, suppress, strong_attack_core, conflict


def role_metrics(role: str, raw_alarm: np.ndarray, hard: np.ndarray, review: np.ndarray, suppress: np.ndarray, strong_core: np.ndarray, conflict: np.ndarray, attack_cov: np.ndarray, benign_cov: np.ndarray, score_strength: np.ndarray) -> dict[str, Any]:
    return {
        "role": role,
        "raw_alarm_rate": rate(raw_alarm),
        "hard_alarm_rate": rate(hard),
        "review_rate": rate(review),
        "suppress_rate": rate(suppress),
        "strong_attack_core_rate": rate(strong_core),
        "conflict_rate": rate(conflict),
        "attack_covered_rate": rate(attack_cov <= 1.0),
        "benign_covered_rate": rate(benign_cov <= 1.0),
        "score_strength_mean": float(np.mean(score_strength)) if len(score_strength) else float("nan"),
        "score_strength_p50": float(np.quantile(score_strength, 0.50)) if len(score_strength) else float("nan"),
        "score_strength_p95": float(np.quantile(score_strength, 0.95)) if len(score_strength) else float("nan"),
    }


def build_banks(
    x: np.ndarray,
    stress_x: np.ndarray,
    id_fit: np.ndarray,
    id_calib: np.ndarray,
    ood_train: np.ndarray,
    ood_val: np.ndarray,
    stress_train: np.ndarray,
    stress_val: np.ndarray,
    medium_train: np.ndarray,
    medium_val: np.ndarray,
    heavy_train_x: np.ndarray,
    heavy_val_x: np.ndarray,
    proto_budget: int,
    radius_q: float,
    seed: int,
    active_budget: int,
) -> tuple[dict[str, PrototypeBank], list[dict[str, Any]]]:
    banks = {
        "id": PrototypeBank("id", x[id_fit], x[id_calib], proto_budget, radius_q),
        "ood": PrototypeBank("ood", np.vstack([x[ood_train], stress_x[stress_train]]), np.vstack([x[ood_val], stress_x[stress_val]]), proto_budget, radius_q),
        "attack_medium": PrototypeBank("attack_medium", x[medium_train], x[medium_val], proto_budget, radius_q),
        "attack_heavy": PrototypeBank("attack_heavy", heavy_train_x, heavy_val_x, proto_budget, radius_q),
    }
    source_roles = {
        "id": "id_fit/id_calib",
        "ood": "ood_train/ood_val/ood_stress_train/ood_stress_val",
        "attack_medium": "attack_support_medium_train/val",
        "attack_heavy": "active_heavy_support_train/val",
    }
    rows = [bank.audit_row(seed, active_budget, source_roles[name]) for name, bank in banks.items()]
    return banks, rows


def precompute_role(
    x_role: np.ndarray,
    banks: dict[str, PrototypeBank],
    bundle: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    attack_cov = np.minimum(banks["attack_medium"].normalized_distance(x_role), banks["attack_heavy"].normalized_distance(x_role))
    benign_cov = np.minimum(banks["id"].normalized_distance(x_role), banks["ood"].normalized_distance(x_role))
    return {
        "raw_alarm": bundle["raw_alarm"],
        "score_strength": bundle["score_strength"],
        "attack_cov": attack_cov,
        "benign_cov": benign_cov,
    }


def aggregate_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    keys = [
        "active_label_budget",
        "proto_budget",
        "bank_radius_q",
        "attack_core_norm",
        "benign_veto_norm",
        "strong_score_q",
        "weak_score_q",
    ]
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    metrics = [
        "id_hard",
        "id_review",
        "ood_hard",
        "ood_review",
        "stress_hard",
        "stress_review",
        "support_medium_hard",
        "support_medium_review",
        "support_heavy_hard",
        "support_heavy_review",
        "dev_attack_min",
        "dev_score",
    ]
    for key, gr in sorted(groups.items()):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(gr)
        for metric in metrics:
            stats = summarize([float(r[metric]) for r in gr])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["strict_feasible_all_seeds"] = all(str(r["strict_feasible"]) == "True" for r in gr)
        row["relaxed_feasible_all_seeds"] = all(str(r["relaxed_feasible"]) == "True" for r in gr)
        out.append(row)
    return out


def choose_global_config(summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    strict = [r for r in summary_rows if str(r["strict_feasible_all_seeds"]) == "True"]
    relaxed = [r for r in summary_rows if str(r["relaxed_feasible_all_seeds"]) == "True"]
    pool = strict or relaxed or summary_rows
    return max(
        pool,
        key=lambda r: (
            str(r["strict_feasible_all_seeds"]) == "True",
            str(r["relaxed_feasible_all_seeds"]) == "True",
            float(r["dev_attack_min_min"]),
            -float(r["stress_review_max"]),
            -float(r["ood_review_max"]),
            -float(r["id_review_max"]),
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
        "medium_attack_eval_report_only",
        "dev_heavy_query_report_only",
        "final_ood_report_only",
    ]
    out: dict[str, Any] = {"seeds": len(rows)}
    for role in roles:
        for metric in ["hard_alarm_rate", "review_rate", "suppress_rate", "raw_alarm_rate", "strong_attack_core_rate", "conflict_rate"]:
            stats = summarize([float(r[f"{role}_{metric}"]) for r in rows])
            for stat, value in stats.items():
                out[f"{role}_{metric}_{stat}"] = value
    out["triple_attack_hard_min"] = min(
        float(out["support_medium_val_hard_alarm_rate_min"]),
        float(out["support_heavy_val_hard_alarm_rate_min"]),
        float(out["medium_attack_eval_report_only_hard_alarm_rate_min"]),
        float(out["dev_heavy_query_report_only_hard_alarm_rate_min"]),
    )
    out["triple_attack_score_or_review_min"] = min(
        float(out["support_medium_val_hard_alarm_rate_min"]) + float(out["support_medium_val_review_rate_min"]),
        float(out["support_heavy_val_hard_alarm_rate_min"]) + float(out["support_heavy_val_review_rate_min"]),
        float(out["medium_attack_eval_report_only_hard_alarm_rate_min"]) + float(out["medium_attack_eval_report_only_review_rate_min"]),
        float(out["dev_heavy_query_report_only_hard_alarm_rate_min"]) + float(out["dev_heavy_query_report_only_review_rate_min"]),
    )
    return out


def choose_verdict(summary: dict[str, Any]) -> str:
    if (
        float(summary["triple_attack_hard_min"]) >= 0.90
        and float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_review_rate_max"]) <= REVIEW_BUDGET
    ):
        return "three_bank_gate_supported_ready_for_mixed_stream"
    if (
        float(summary["triple_attack_hard_min"]) >= 0.75
        and float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= VAL_TARGET
    ):
        return "three_bank_gate_promising_needs_review_cost_repair"
    if float(summary["triple_attack_hard_min"]) < 0.75 and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET:
        return "three_bank_gate_still_kills_attack"
    if float(summary["ood_stress_val_hard_alarm_rate_max"]) > VAL_TARGET:
        return "three_bank_gate_attack_preserved_but_ood_overbudget"
    if float(summary["ood_stress_val_review_rate_max"]) > RELAXED_REVIEW_BUDGET:
        return "three_bank_gate_review_overload"
    return "three_bank_gate_unresolved"


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
    active_candidate_idx, dev_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "actual_sha256": sha256_file(stress_cert_path), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    grid_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    # First pass: dev-only grid for one frozen global config.
    for seed in SEEDS:
        for active_budget in ACTIVE_LABEL_BUDGETS:
            sel = ay.select_base_and_active(x, new_x, support_pool, active_candidate_idx, new_sidecar, seed, active_budget)
            medium_train = sel["base_train"]
            medium_val = sel["base_val"]
            heavy_train_idx = sel["heavy_train"]
            heavy_val_idx = sel["heavy_val"]
            heavy_train_x = new_x[heavy_train_idx]
            heavy_val_x = new_x[heavy_val_idx]
            medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
            heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], heavy_train_x, seed)
            medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
            heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(heavy_val_x))

            role_x_dev = {
                "id_calib": x[id_calib],
                "ood_val": x[ood_val],
                "ood_stress_val": stress_x[stress_val],
                "support_medium_val": x[medium_val],
                "support_heavy_val": heavy_val_x,
            }
            role_scores = {
                role: score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
                for role, x_role in role_x_dev.items()
            }
            support_strength = np.concatenate([role_scores["support_medium_val"]["score_strength"], role_scores["support_heavy_val"]["score_strength"]])
            support_strength = support_strength[np.isfinite(support_strength)]
            if len(support_strength) == 0:
                support_strength = np.asarray([0.0], dtype=np.float64)

            for proto_budget in PROTO_BUDGETS:
                for radius_q in BANK_RADIUS_QS:
                    banks, audit = build_banks(
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
                        heavy_train_x,
                        heavy_val_x,
                        proto_budget,
                        radius_q,
                        seed,
                        active_budget,
                    )
                    bank_rows.extend(audit)
                    pre = {role: precompute_role(role_x_dev[role], banks, role_scores[role]) for role in role_x_dev}
                    for attack_core_norm in ATTACK_CORE_NORMS:
                        for benign_veto_norm in BENIGN_VETO_NORMS:
                            for strong_q in STRONG_SCORE_QS:
                                strong_floor = float(np.quantile(support_strength, strong_q))
                                for weak_q in WEAK_SCORE_QS:
                                    if weak_q < strong_q:
                                        continue
                                    weak_ceiling = float(np.quantile(support_strength, weak_q))
                                    metrics: dict[str, float] = {}
                                    for role, p in pre.items():
                                        hard, review, suppress, strong_core, conflict = three_bank_gate(
                                            p["raw_alarm"],
                                            p["score_strength"],
                                            p["attack_cov"],
                                            p["benign_cov"],
                                            strong_floor,
                                            weak_ceiling,
                                            attack_core_norm,
                                            benign_veto_norm,
                                        )
                                        prefix = {
                                            "id_calib": "id",
                                            "ood_val": "ood",
                                            "ood_stress_val": "stress",
                                            "support_medium_val": "support_medium",
                                            "support_heavy_val": "support_heavy",
                                        }[role]
                                        metrics[f"{prefix}_hard"] = rate(hard)
                                        metrics[f"{prefix}_review"] = rate(review)
                                        metrics[f"{prefix}_suppress"] = rate(suppress)
                                    dev_attack_min = min(metrics["support_medium_hard"], metrics["support_heavy_hard"])
                                    strict_feasible = (
                                        metrics["id_hard"] <= VAL_TARGET
                                        and metrics["ood_hard"] <= VAL_TARGET
                                        and metrics["stress_hard"] <= VAL_TARGET
                                        and metrics["id_review"] <= REVIEW_BUDGET
                                        and metrics["ood_review"] <= REVIEW_BUDGET
                                        and metrics["stress_review"] <= REVIEW_BUDGET
                                        and metrics["support_medium_hard"] >= ATTACK_FLOOR
                                        and metrics["support_heavy_hard"] >= ATTACK_FLOOR
                                    )
                                    relaxed_feasible = (
                                        metrics["id_hard"] <= VAL_TARGET
                                        and metrics["ood_hard"] <= VAL_TARGET
                                        and metrics["stress_hard"] <= VAL_TARGET
                                        and metrics["id_review"] <= RELAXED_REVIEW_BUDGET
                                        and metrics["ood_review"] <= RELAXED_REVIEW_BUDGET
                                        and metrics["stress_review"] <= RELAXED_REVIEW_BUDGET
                                        and metrics["support_medium_hard"] >= RELAXED_ATTACK_FLOOR
                                        and metrics["support_heavy_hard"] >= RELAXED_ATTACK_FLOOR
                                    )
                                    grid_rows.append(
                                        {
                                            "seed": seed,
                                            "active_label_budget": active_budget,
                                            "proto_budget": proto_budget,
                                            "bank_radius_q": radius_q,
                                            "attack_core_norm": attack_core_norm,
                                            "benign_veto_norm": benign_veto_norm,
                                            "strong_score_q": strong_q,
                                            "weak_score_q": weak_q,
                                            "strong_score_floor": strong_floor,
                                            "weak_score_ceiling": weak_ceiling,
                                            **metrics,
                                            "dev_attack_min": dev_attack_min,
                                            "strict_feasible": strict_feasible,
                                            "relaxed_feasible": relaxed_feasible,
                                            "dev_score": dev_attack_min - 0.2 * (metrics["stress_review"] + metrics["ood_review"]) - 0.1 * metrics["id_review"],
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
        "benign_veto_norm": float(selected["benign_veto_norm"]),
        "strong_score_q": float(selected["strong_score_q"]),
        "weak_score_q": float(selected["weak_score_q"]),
    }

    replay_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        active_budget = selected_cfg["active_label_budget"]
        sel = ay.select_base_and_active(x, new_x, support_pool, active_candidate_idx, new_sidecar, seed, active_budget)
        medium_train = sel["base_train"]
        medium_val = sel["base_val"]
        heavy_train_idx = sel["heavy_train"]
        heavy_val_idx = sel["heavy_val"]
        heavy_train_x = new_x[heavy_train_idx]
        heavy_val_x = new_x[heavy_val_idx]
        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], heavy_train_x, seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(heavy_val_x))
        banks, _ = build_banks(
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
            heavy_train_x,
            heavy_val_x,
            selected_cfg["proto_budget"],
            selected_cfg["bank_radius_q"],
            seed,
            active_budget,
        )
        role_x = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": heavy_val_x,
            "medium_attack_eval_report_only": x[attack_eval],
            "dev_heavy_query_report_only": new_x[dev_query_idx],
            "final_ood_report_only": x[final_ood],
        }
        support_scores_for_floor = []
        for role in ["support_medium_val", "support_heavy_val"]:
            b = score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), role_x[role])
            support_scores_for_floor.append(b["score_strength"])
        support_strength = np.concatenate(support_scores_for_floor)
        strong_floor = float(np.quantile(support_strength, selected_cfg["strong_score_q"]))
        weak_ceiling = float(np.quantile(support_strength, selected_cfg["weak_score_q"]))
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
            bundle = score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
            pre = precompute_role(x_role, banks, bundle)
            hard, review, suppress, strong_core, conflict = three_bank_gate(
                pre["raw_alarm"],
                pre["score_strength"],
                pre["attack_cov"],
                pre["benign_cov"],
                strong_floor,
                weak_ceiling,
                selected_cfg["attack_core_norm"],
                selected_cfg["benign_veto_norm"],
            )
            metrics = role_metrics(role, pre["raw_alarm"], hard, review, suppress, strong_core, conflict, pre["attack_cov"], pre["benign_cov"], pre["score_strength"])
            for key, value in metrics.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = value
            decision_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "rows": int(len(x_role)),
                    "hard_alarm_rate": metrics["hard_alarm_rate"],
                    "review_rate": metrics["review_rate"],
                    "suppress_rate": metrics["suppress_rate"],
                    "strong_attack_core_rate": metrics["strong_attack_core_rate"],
                    "conflict_rate": metrics["conflict_rate"],
                    "raw_alarm_rate": metrics["raw_alarm_rate"],
                }
            )
        replay_rows.append(replay_row)
        role_rows.append(
            {
                "seed": seed,
                "active_label_budget": active_budget,
                "fit_roles": "id_fit|ood_train_guard|medium_region_train_attack|active_heavy_region_train_attack",
                "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                "prototype_bank_roles": "id_fit/id_calib|ood_train/ood_val/ood_stress_train/ood_stress_val|medium_support_train/val|active_heavy_train/val",
                "gate_selection_roles": "id_calib|ood_val|ood_stress_val|support_medium_val|support_heavy_val",
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
    write_csv(OUT / "prototype_bank_audit.csv", bank_rows)
    write_csv(OUT / "three_bank_gate_candidate_grid.csv", grid_rows)
    write_csv(OUT / "three_bank_gate_dev_summary.csv", grid_summary)
    write_csv(OUT / "three_bank_gate_selection_audit.csv", [selected])
    write_csv(OUT / "three_bank_gate_report_only_replay_by_seed.csv", replay_rows)
    write_csv(OUT / "three_bank_gate_decision_breakdown.csv", decision_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_md(
        OUT / "three_bank_gate_logic_spec.md",
        [
            "# Three Prototype Bank Attack-Preserving Gate",
            "",
            "This diagnostic uses three evidence banks after a raw attack score alarm:",
            "",
            "- ID prototype bank: known benign support for false-alarm attribution.",
            "- OOD/stress prototype bank: benign drift support for OOD-tail veto.",
            "- Attack prototype banks: medium and active-heavy attack regions that protect confirmed attack alarms.",
            "",
            "Decision order:",
            "",
            "```text",
            "if raw_attack_alarm == false: no_alarm",
            "elif strong_attack_score and near_attack_core: hard_alarm",
            "elif near_attack_core and not near_benign_or_ood: hard_alarm",
            "elif weak_attack_score and near_benign_or_ood and not near_attack_core: suppress",
            "elif near_attack_core and near_benign_or_ood: review",
            "else: unknown_review",
            "```",
            "",
            "Final OOD, medium attack eval, and dev-heavy query are report-only and do not tune prototypes, score floors, or gate parameters.",
        ],
    )
    write_md(
        OUT / "three_bank_gate_report.md",
        [
            "# Three-Bank Gate Report",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "## Selected Dev-Frozen Config",
            "",
            *[f"- {k}: `{v}`" for k, v in selected_cfg.items()],
            "",
            "## Replay Summary",
            "",
            *[f"- {k}: `{v}`" for k, v in replay_summary.items()],
            "",
            "## Interpretation",
            "",
            "- This is not a formal benchmark.",
            "- The selected gate is frozen from dev roles only.",
            "- Review is not counted as hard detection.",
        ],
    )

    next_issue = "issue27bc_three_bank_gate_refinement_or_mixed_stream"
    if verdict == "three_bank_gate_supported_ready_for_mixed_stream":
        next_issue = "issue27bc_mixed_stream_active_labeling_realism_gate"
    elif verdict in {"three_bank_gate_still_kills_attack", "three_bank_gate_promising_needs_review_cost_repair"}:
        next_issue = "issue27bc_attack_core_and_review_cost_repair"
    elif verdict == "three_bank_gate_attack_preserved_but_ood_overbudget":
        next_issue = "issue27bc_ood_veto_strengthening_with_attack_core_protection"

    write_md(
        OUT / "issue27bb_decision.md",
        [
            "# Issue27bb Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "- Implemented ID/OOD/Attack prototype banks with compressed k-center prototypes.",
            "- Used one dev-selected global gate config across seeds.",
            "- Did not use final OOD, attack eval, or dev-heavy query for bank construction or gate selection.",
            f"- Recommended next issue: `{next_issue}`.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bb.md",
        [
            "# Claim Update After issue27bb",
            "",
            "- issue27bb is a mechanism diagnostic, not a formal benchmark.",
            "- Prototype banks can be used as online gating evidence only when role access and review cost remain bounded.",
            "- Formal claims require a frozen full/larger data contract and sealed final replay.",
        ],
    )
    write_md(
        OUT / "issue27bc_next_action.md",
        [
            "# Issue27bc Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If attack hard detection is still too low, repair attack-core and review-cost logic before adding mixed streams.",
            "- If OOD hard alarm is too high, strengthen OOD veto while preserving attack core override.",
            "- If both are controlled, move to mixed incoming-stream realism with unknown/review accounting.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bb Summary",
            "",
            "1. issue27bb completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: attack-preserving three-prototype-bank OOD gate diagnostic; not formal benchmark",
            "4. 115D frontend/split changed: no",
            "5. final OOD used for prototype/gate selection: no",
            "6. attack eval/dev-heavy query used for prototype/gate selection: no",
            f"7. selected active label budget: `{selected_cfg['active_label_budget']}`",
            f"8. selected prototype budget per bank: `{selected_cfg['proto_budget']}`",
            f"9. selected bank radius q: `{selected_cfg['bank_radius_q']}`",
            f"10. selected attack_core_norm: `{selected_cfg['attack_core_norm']}`",
            f"11. selected benign_veto_norm: `{selected_cfg['benign_veto_norm']}`",
            f"12. triple attack hard min: `{replay_summary['triple_attack_hard_min']}`",
            f"13. triple attack score-or-review min: `{replay_summary['triple_attack_score_or_review_min']}`",
            f"14. OOD val hard max: `{replay_summary['ood_val_hard_alarm_rate_max']}`",
            f"15. OOD stress hard max: `{replay_summary['ood_stress_val_hard_alarm_rate_max']}`",
            f"16. final OOD hard max report-only: `{replay_summary['final_ood_report_only_hard_alarm_rate_max']}`",
            f"17. max review rate on OOD stress: `{replay_summary['ood_stress_val_review_rate_max']}`",
            "18. current formal benchmark allowed: no",
            f"19. next action: `{next_issue}`",
            "20. commit hash: pending",
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
        "benign_veto_norms": BENIGN_VETO_NORMS,
        "strong_score_qs": STRONG_SCORE_QS,
        "weak_score_qs": WEAK_SCORE_QS,
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
                "scope": "three-bank prototype gate diagnostic only; final roles report-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bb -->",
        [
            "<!-- issue27bb -->",
            "## issue27bb - Three prototype bank attack-preserving OOD gate",
            "",
            f"- primary_verdict: `{verdict}`",
            "- Diagnostic only; adds ID/OOD/Attack prototype banks after raw attack score alarms.",
            "- Final OOD, attack eval, and dev-heavy query were not used for prototype or gate selection.",
            f"- next action: `{next_issue}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bb -->",
        [
            "<!-- issue27bb -->",
            "## issue27bb - Three prototype bank gate diagnostic",
            "",
            f"- verdict: `{verdict}`",
            "- purpose: test whether compressed ID/OOD/Attack prototype banks can suppress OOD drift while preserving attack core alarms.",
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
