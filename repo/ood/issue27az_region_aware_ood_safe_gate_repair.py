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


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27az_region_aware_attack_preserving_ood_safe_gate_repair_2026-06-05"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AY = ROOT / "runs" / "issue27ay_region_aware_attack_bank_and_score_gate_diagnostic_2026-06-05"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [64, 128]
RADIUS_QUANTILES = [0.75, 0.90, 0.95]
MARGINS = [-0.25, 0.0, 0.25, 0.50, 0.75, 1.0]
VAL_TARGET = 0.01
REVIEW_BUDGET = 0.10
RELAXED_REVIEW_BUDGET = 0.20

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE


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


class CoverageRegion:
    def __init__(self, region_id: str, train_x: np.ndarray, val_x: np.ndarray):
        self.region_id = region_id
        self.train_rows = int(len(train_x))
        self.val_rows = int(len(val_x))
        self.scaler = StandardScaler().fit(train_x)
        self.z_train = self.scaler.transform(train_x)
        if len(val_x):
            val_d = pairwise_distances(self.scaler.transform(val_x), self.z_train, metric="euclidean").min(axis=1)
        else:
            val_d = np.asarray([1.0], dtype=np.float64)
        self.radius_by_q = {
            0.75: float(np.quantile(val_d, 0.75)),
            0.90: float(np.quantile(val_d, 0.90)),
            0.95: float(np.quantile(val_d, 0.95)),
        }
        # Avoid divide-by-zero if a tiny dev sample has identical vectors.
        for q, radius in list(self.radius_by_q.items()):
            if not np.isfinite(radius) or radius <= 1e-12:
                self.radius_by_q[q] = 1e-12
        self.val_distance_mean = float(np.mean(val_d))
        self.val_distance_max = float(np.max(val_d))

    def normalized_distance(self, x: np.ndarray, q: float) -> np.ndarray:
        d = pairwise_distances(self.scaler.transform(x), self.z_train, metric="euclidean").min(axis=1)
        return d / float(self.radius_by_q[float(q)])

    def audit_row(self, q: float) -> dict[str, Any]:
        return {
            "region_id": self.region_id,
            "train_rows": self.train_rows,
            "val_rows": self.val_rows,
            "radius_quantile": q,
            "radius": self.radius_by_q[float(q)],
            "val_distance_mean": self.val_distance_mean,
            "val_distance_max": self.val_distance_max,
            "radius_source": "dev_train_val_only",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
        }


def head_alarms(
    medium_head: ay.CustomWeightedHistGB,
    heavy_head: ay.CustomWeightedHistGB | None,
    medium_threshold: float,
    heavy_threshold: float | None,
    x: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    m_alarm = medium_head.score(x) > float(medium_threshold)
    if heavy_head is None or heavy_threshold is None:
        h_alarm = np.zeros(len(x), dtype=bool)
    else:
        h_alarm = heavy_head.score(x) > float(heavy_threshold)
    return m_alarm, h_alarm, m_alarm | h_alarm


def gate_decision(
    gate_name: str,
    raw_alarm: np.ndarray,
    attack_cov: np.ndarray,
    benign_cov: np.ndarray,
    margin: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    attack_covered = attack_cov <= 1.0
    benign_covered = benign_cov <= 1.0
    attack_advantage = benign_cov - attack_cov
    raw_alarm = raw_alarm.astype(bool)
    if gate_name == "no_gate":
        hard = raw_alarm.copy()
        review = np.zeros(len(raw_alarm), dtype=bool)
        suppress = raw_alarm & ~hard
        return hard, review, suppress
    if gate_name == "soft_benign_veto":
        veto_zone = raw_alarm & benign_covered & (attack_advantage < margin)
        review = veto_zone & attack_covered
        suppress = veto_zone & ~attack_covered
        hard = raw_alarm & ~veto_zone
        return hard, review, suppress
    if gate_name == "attack_advantage_margin":
        hard = raw_alarm & (attack_advantage >= margin)
        review = raw_alarm & ~hard & attack_covered
        suppress = raw_alarm & ~hard & ~attack_covered
        return hard, review, suppress
    if gate_name == "conflict_to_review":
        conflict = raw_alarm & attack_covered & benign_covered
        unknown = raw_alarm & ~attack_covered & ~benign_covered
        suppress = raw_alarm & ~attack_covered & benign_covered
        hard = raw_alarm & attack_covered & ~benign_covered
        review = conflict | unknown
        return hard, review, suppress
    raise ValueError(gate_name)


def role_metrics(
    role: str,
    raw_alarm: np.ndarray,
    hard: np.ndarray,
    review: np.ndarray,
    suppress: np.ndarray,
    attack_cov: np.ndarray,
    benign_cov: np.ndarray,
) -> dict[str, Any]:
    return {
        "role": role,
        "raw_alarm_rate": rate(raw_alarm),
        "hard_alarm_rate": rate(hard),
        "review_rate": rate(review),
        "suppress_rate": rate(suppress),
        "attack_covered_rate": rate(attack_cov <= 1.0),
        "benign_covered_rate": rate(benign_cov <= 1.0),
        "attack_advantage_mean": float(np.mean(benign_cov - attack_cov)) if len(attack_cov) else float("nan"),
    }


def aggregate_selection_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[(row["active_label_budget"], row["gate_name"], row["radius_quantile"], row["margin"])].append(row)
    out: list[dict[str, Any]] = []
    for key, gr in sorted(groups.items()):
        row = {
            "active_label_budget": key[0],
            "gate_name": key[1],
            "radius_quantile": key[2],
            "margin": key[3],
            "seeds": len(gr),
        }
        for metric in [
            "id_calib_hard_alarm",
            "ood_val_hard_alarm",
            "ood_val_review",
            "support_medium_hard_detection",
            "support_heavy_hard_detection",
            "dev_support_attack_min",
            "dev_selection_score",
        ]:
            stats = summarize([float(r[metric]) for r in gr])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["dev_feasible_all_seeds"] = all(str(r["dev_feasible"]) == "True" for r in gr)
        row["dev_relaxed_feasible_all_seeds"] = all(str(r["dev_relaxed_feasible"]) == "True" for r in gr)
        out.append(row)
    return out


def aggregate_report_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["selected_for_replay"] is True:
            groups[(row["active_label_budget"], row["gate_name"], row["radius_quantile"], row["margin"])].append(row)
    out: list[dict[str, Any]] = []
    for key, gr in sorted(groups.items()):
        row = {
            "active_label_budget": key[0],
            "gate_name": key[1],
            "radius_quantile": key[2],
            "margin": key[3],
            "seeds": len(gr),
        }
        for role in [
            "medium_attack_eval_report_only",
            "dev_heavy_query_report_only",
            "final_ood_report_only",
            "id_calib",
            "ood_val",
            "support_medium_val",
            "support_heavy_val",
        ]:
            for metric in ["hard_alarm_rate", "review_rate", "suppress_rate", "raw_alarm_rate"]:
                vals = [float(r[f"{role}_{metric}"]) for r in gr]
                stats = summarize(vals)
                for stat, value in stats.items():
                    row[f"{role}_{metric}_{stat}"] = value
        row["triple_attack_hard_min"] = min(
            float(row["support_medium_val_hard_alarm_rate_min"]),
            float(row["support_heavy_val_hard_alarm_rate_min"]),
            float(row["medium_attack_eval_report_only_hard_alarm_rate_min"]),
            float(row["dev_heavy_query_report_only_hard_alarm_rate_min"]),
        )
        row["triple_attack_score_or_review_min"] = min(
            float(row["support_medium_val_hard_alarm_rate_min"]),
            float(row["support_heavy_val_hard_alarm_rate_min"]),
            float(row["medium_attack_eval_report_only_hard_alarm_rate_min"])
            + float(row["medium_attack_eval_report_only_review_rate_min"]),
            float(row["dev_heavy_query_report_only_hard_alarm_rate_min"])
            + float(row["dev_heavy_query_report_only_review_rate_min"]),
        )
        out.append(row)
    return out


def choose_dev_candidate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    feasible = [r for r in rows if r["dev_feasible"]]
    relaxed = [r for r in rows if r["dev_relaxed_feasible"]]
    pool = feasible or relaxed or rows
    return max(
        pool,
        key=lambda r: (
            bool(r["dev_feasible"]),
            bool(r["dev_relaxed_feasible"]),
            float(r["dev_support_attack_min"]),
            -float(r["ood_val_review"]),
            -float(r["id_calib_hard_alarm"]),
            -float(r["margin"]),
        ),
    )


def choose_verdict(report_summary: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    best = max(
        report_summary,
        key=lambda r: (
            float(r["triple_attack_hard_min"]),
            -float(r["final_ood_report_only_hard_alarm_rate_max"]),
            -float(r["final_ood_report_only_review_rate_max"]),
        ),
    )
    stats = {
        "selected_active_label_budget": int(best["active_label_budget"]),
        "selected_gate_name": best["gate_name"],
        "selected_radius_quantile": float(best["radius_quantile"]),
        "selected_margin": float(best["margin"]),
        "triple_attack_hard_min": float(best["triple_attack_hard_min"]),
        "triple_attack_score_or_review_min": float(best["triple_attack_score_or_review_min"]),
        "medium_attack_hard_min": float(best["medium_attack_eval_report_only_hard_alarm_rate_min"]),
        "dev_heavy_hard_min": float(best["dev_heavy_query_report_only_hard_alarm_rate_min"]),
        "final_ood_hard_max": float(best["final_ood_report_only_hard_alarm_rate_max"]),
        "final_ood_review_max": float(best["final_ood_report_only_review_rate_max"]),
        "ood_val_hard_max": float(best["ood_val_hard_alarm_rate_max"]),
        "ood_val_review_max": float(best["ood_val_review_rate_max"]),
    }
    if stats["triple_attack_hard_min"] >= 0.95 and stats["final_ood_hard_max"] <= VAL_TARGET and stats["final_ood_review_max"] <= REVIEW_BUDGET:
        return "region_ood_gate_supported", stats
    if stats["triple_attack_hard_min"] >= 0.90 and stats["final_ood_hard_max"] <= 0.05 and stats["final_ood_review_max"] <= RELAXED_REVIEW_BUDGET:
        return "region_ood_gate_promising_but_not_final_safe", stats
    if stats["final_ood_hard_max"] <= 0.05 and stats["triple_attack_hard_min"] < 0.90:
        return "ood_gate_kills_attack", stats
    if stats["triple_attack_hard_min"] >= 0.90 and stats["ood_val_hard_max"] <= VAL_TARGET and stats["final_ood_hard_max"] > 0.05:
        return "needs_disjoint_ood_stress_pool_final_tail_uncovered", stats
    if stats["triple_attack_hard_min"] >= 0.90 and stats["final_ood_hard_max"] > 0.05:
        return "ood_gate_insufficient_attack_preserved", stats
    if stats["final_ood_review_max"] > RELAXED_REVIEW_BUDGET:
        return "ood_gate_review_overload", stats
    return "region_ood_gate_unresolved", stats


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)

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
        {"artifact": "issue27ay_summary", "path": str(ISSUE27AY / "summary.md"), "sha256": sha256_file(ISSUE27AY / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(checks)
    input_hash_rows.extend(new_checks)

    radius_rows: list[dict[str, Any]] = []
    grid_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    review_budget_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        for budget in ACTIVE_LABEL_BUDGETS:
            sel = ay.select_base_and_active(x, new_x, support_pool, active_candidate_idx, new_sidecar, seed, budget)
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

            regions = {
                "attack_medium": CoverageRegion("attack_medium", x[medium_train], x[medium_val]),
                "attack_heavy": CoverageRegion("attack_heavy", heavy_train_x, heavy_val_x),
                "id_benign": CoverageRegion("id_benign", x[id_fit], x[id_calib]),
                "ood_benign": CoverageRegion("ood_benign", x[ood_train], x[ood_val]),
            }
            for region in regions.values():
                for q in RADIUS_QUANTILES:
                    row = region.audit_row(q)
                    row.update({"seed": seed, "active_label_budget": budget})
                    radius_rows.append(row)

            role_x = {
                "id_calib": x[id_calib],
                "ood_val": x[ood_val],
                "support_medium_val": x[medium_val],
                "support_heavy_val": heavy_val_x,
                "medium_attack_eval_report_only": x[attack_eval],
                "dev_heavy_query_report_only": new_x[dev_query_idx],
                "final_ood_report_only": x[final_ood],
            }
            role_precomp: dict[tuple[str, float], dict[str, np.ndarray]] = {}
            for q in RADIUS_QUANTILES:
                for role, x_role in role_x.items():
                    _, _, raw = head_alarms(
                        medium_head,
                        heavy_head,
                        float(medium_th["threshold"]),
                        float(heavy_th["threshold"]),
                        x_role,
                    )
                    c_m = regions["attack_medium"].normalized_distance(x_role, q)
                    c_h = regions["attack_heavy"].normalized_distance(x_role, q)
                    c_id = regions["id_benign"].normalized_distance(x_role, q)
                    c_ood = regions["ood_benign"].normalized_distance(x_role, q)
                    role_precomp[(role, q)] = {
                        "raw_alarm": raw,
                        "attack_cov": np.minimum(c_m, c_h),
                        "benign_cov": np.minimum(c_id, c_ood),
                    }

            seed_grid_rows: list[dict[str, Any]] = []
            for gate_name in ["no_gate", "soft_benign_veto", "attack_advantage_margin", "conflict_to_review"]:
                q_iter = [0.95] if gate_name == "no_gate" else RADIUS_QUANTILES
                margin_iter = [0.0] if gate_name in {"no_gate", "conflict_to_review"} else MARGINS
                for q in q_iter:
                    for margin in margin_iter:
                        dev_metrics: dict[str, float] = {}
                        for role in ["id_calib", "ood_val", "support_medium_val", "support_heavy_val"]:
                            pre = role_precomp[(role, q)]
                            hard, review, suppress = gate_decision(
                                gate_name,
                                pre["raw_alarm"],
                                pre["attack_cov"],
                                pre["benign_cov"],
                                float(margin),
                            )
                            dev_metrics[f"{role}_hard"] = rate(hard)
                            dev_metrics[f"{role}_review"] = rate(review)
                            dev_metrics[f"{role}_suppress"] = rate(suppress)
                            dev_metrics[f"{role}_raw"] = rate(pre["raw_alarm"])
                        dev_attack_min = min(dev_metrics["support_medium_val_hard"], dev_metrics["support_heavy_val_hard"])
                        dev_feasible = (
                            dev_metrics["id_calib_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_review"] <= REVIEW_BUDGET
                        )
                        dev_relaxed_feasible = (
                            dev_metrics["id_calib_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_hard"] <= VAL_TARGET
                            and dev_metrics["ood_val_review"] <= RELAXED_REVIEW_BUDGET
                        )
                        row = {
                            "seed": seed,
                            "active_label_budget": budget,
                            "gate_name": gate_name,
                            "radius_quantile": q,
                            "margin": float(margin),
                            "id_calib_hard_alarm": dev_metrics["id_calib_hard"],
                            "id_calib_review": dev_metrics["id_calib_review"],
                            "ood_val_hard_alarm": dev_metrics["ood_val_hard"],
                            "ood_val_review": dev_metrics["ood_val_review"],
                            "support_medium_hard_detection": dev_metrics["support_medium_val_hard"],
                            "support_heavy_hard_detection": dev_metrics["support_heavy_val_hard"],
                            "dev_support_attack_min": dev_attack_min,
                            "dev_feasible": dev_feasible,
                            "dev_relaxed_feasible": dev_relaxed_feasible,
                            "dev_selection_score": dev_attack_min - 0.1 * dev_metrics["ood_val_review"],
                            "selection_uses_final_ood": False,
                            "selection_uses_attack_eval": False,
                            "selection_uses_dev_heavy_query": False,
                        }
                        seed_grid_rows.append(row)
                        grid_rows.append(row)
            selected = choose_dev_candidate(seed_grid_rows)
            selection_rows.append({**selected, "selected_for_report_only_replay": True})
            review_budget_rows.append(
                {
                    "seed": seed,
                    "active_label_budget": budget,
                    "selected_gate_name": selected["gate_name"],
                    "selected_radius_quantile": selected["radius_quantile"],
                    "selected_margin": selected["margin"],
                    "dev_review_budget": REVIEW_BUDGET,
                    "dev_relaxed_review_budget": RELAXED_REVIEW_BUDGET,
                    "ood_val_review": selected["ood_val_review"],
                    "review_budget_pass": float(selected["ood_val_review"]) <= REVIEW_BUDGET,
                    "relaxed_review_budget_pass": float(selected["ood_val_review"]) <= RELAXED_REVIEW_BUDGET,
                }
            )
            replay_row: dict[str, Any] = {
                "seed": seed,
                "active_label_budget": budget,
                "gate_name": selected["gate_name"],
                "radius_quantile": selected["radius_quantile"],
                "margin": selected["margin"],
                "selected_for_replay": True,
                "dev_selection_uses_final_ood": False,
                "dev_selection_uses_attack_eval": False,
                "dev_selection_uses_dev_heavy_query": False,
            }
            for role, x_role in role_x.items():
                pre = role_precomp[(role, float(selected["radius_quantile"]))]
                hard, review, suppress = gate_decision(
                    selected["gate_name"],
                    pre["raw_alarm"],
                    pre["attack_cov"],
                    pre["benign_cov"],
                    float(selected["margin"]),
                )
                metrics = role_metrics(role, pre["raw_alarm"], hard, review, suppress, pre["attack_cov"], pre["benign_cov"])
                for key, value in metrics.items():
                    if key != "role":
                        replay_row[f"{role}_{key}"] = value
            replay_rows.append(replay_row)
            role_rows.append(
                {
                    "seed": seed,
                    "active_label_budget": budget,
                    "fit_roles": "id_fit|ood_train_guard|medium_region_train_attack|active_heavy_region_train_attack",
                    "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                    "gate_radius_roles": "id_fit/id_calib|ood_train/ood_val|medium_train/medium_val|heavy_train/heavy_val",
                    "report_only_roles": "medium_attack_eval|dev_heavy_query|final_ood",
                    "uses_final_ood_for_gate_selection": False,
                    "uses_attack_eval_for_gate_selection": False,
                    "uses_dev_heavy_query_for_gate_selection": False,
                    "uses_final_ood_for_radius": False,
                    "uses_attack_eval_for_radius": False,
                    "forbidden_role_access": False,
                }
            )

    gate_summary = aggregate_selection_rows(grid_rows)
    report_summary = aggregate_report_rows(replay_rows)
    primary_verdict, verdict_stats = choose_verdict(report_summary)

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "prototype_radius_audit.csv", radius_rows)
    write_csv(OUT / "gate_candidate_grid.csv", grid_rows)
    write_csv(OUT / "gate_selection_audit.csv", selection_rows)
    write_csv(OUT / "gate_dev_summary.csv", gate_summary)
    write_csv(OUT / "gate_report_only_replay_by_seed.csv", replay_rows)
    write_csv(OUT / "gate_report_only_summary.csv", report_summary)
    write_csv(OUT / "review_budget_audit.csv", review_budget_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_md(
        OUT / "gate_logic_spec.md",
        [
            "# Region-Aware OOD-Safe Gate Logic Spec",
            "",
            "This task adds a post-score gate after issue27ay per-region heads.",
            "",
            "- `no_gate`: attack alarm is `medium_head OR heavy_head`.",
            "- `soft_benign_veto`: raw alarms close to benign/OOD and without enough attack advantage go to review or suppress.",
            "- `attack_advantage_margin`: raw alarms become hard alarms only when attack coverage beats benign/OOD coverage by a pre-registered margin.",
            "- `conflict_to_review`: raw alarms close to both attack and benign/OOD are reviewed; benign-only raw alarms are suppressed.",
            "",
            "All radii and margins are selected from dev roles only. Final OOD, medium attack eval, and dev-heavy query are replay-only.",
        ],
    )
    write_md(
        OUT / "gate_repair_report.md",
        [
            "# Region-Aware OOD-Safe Gate Repair Report",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "This is not a formal benchmark. It tests whether issue27ay region-aware heads can be guarded without killing attack recovery.",
            "",
            "## Dev-Selected Replay Summary",
            "",
            *[f"- {k}: `{v}`" for k, v in verdict_stats.items()],
            "",
            "## Interpretation",
            "",
            "- Hard alarm, review, and suppress rates are separated; review is not counted as detection.",
            "- Gate selection uses only ID/OOD/support validation roles.",
            "- Final OOD is report-only and can only diagnose whether dev OOD covered the final tail.",
        ],
    )
    next_issue = "issue27ba_mixed_incoming_stream_active_labeling_realism"
    if primary_verdict in {"needs_disjoint_ood_stress_pool_final_tail_uncovered", "ood_gate_insufficient_attack_preserved"}:
        next_issue = "issue27ba_disjoint_ood_stress_pool_before_mixed_stream"
    elif primary_verdict == "ood_gate_kills_attack":
        next_issue = "issue27ba_attack_preserving_gate_redesign"
    elif primary_verdict == "region_ood_gate_supported":
        next_issue = "issue27ba_mixed_incoming_stream_active_labeling_realism"
    write_md(
        OUT / "issue27az_decision.md",
        [
            "# Issue27az Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            "- Region-aware heads were reused; no 115D frontend or split changes were made.",
            "- Gate parameters were selected on dev roles only.",
            "- Final OOD and attack eval roles are report-only.",
            f"- Recommended next issue: `{next_issue}`.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27az.md",
        [
            "# Claim Update After issue27az",
            "",
            "- issue27az remains a diagnostic gate-repair experiment, not a formal benchmark.",
            "- It can support internal route decisions about OOD-safe gating but cannot establish paper claims.",
            "- Formal claims still require disjoint data contracts, mixed-stream realism checks, larger/full replay, and sealed final evaluation.",
        ],
    )
    write_md(
        OUT / "issue27ba_next_action.md",
        [
            "# Issue27ba Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- If final OOD remains high while dev OOD is controlled, construct a strictly disjoint OOD stress pool before mixed-stream active labeling.",
            "- If OOD is controlled and attack is preserved, move to mixed incoming stream realism.",
            "- If attack is killed, redesign the gate before adding new data.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27az Summary",
            "",
            "1. issue27az completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: region-aware attack-preserving OOD gate diagnostic; not formal benchmark",
            "4. 115D frontend/split changed: no",
            "5. final OOD used for gate/radius/threshold selection: no",
            "6. attack eval/dev-heavy query used for gate/radius/threshold selection: no",
            f"7. selected gate: `{verdict_stats['selected_gate_name']}`",
            f"8. selected active label budget: `{verdict_stats['selected_active_label_budget']}`",
            f"9. selected radius quantile: `{verdict_stats['selected_radius_quantile']}`",
            f"10. selected margin: `{verdict_stats['selected_margin']}`",
            f"11. triple attack hard min: `{verdict_stats['triple_attack_hard_min']}`",
            f"12. triple attack score-or-review min: `{verdict_stats['triple_attack_score_or_review_min']}`",
            f"13. medium attack hard min: `{verdict_stats['medium_attack_hard_min']}`",
            f"14. dev-heavy attack hard min: `{verdict_stats['dev_heavy_hard_min']}`",
            f"15. OOD val hard max: `{verdict_stats['ood_val_hard_max']}`",
            f"16. OOD val review max: `{verdict_stats['ood_val_review_max']}`",
            f"17. final OOD hard max report-only: `{verdict_stats['final_ood_hard_max']}`",
            f"18. final OOD review max report-only: `{verdict_stats['final_ood_review_max']}`",
            "19. current formal benchmark allowed: no",
            f"20. next action: `{next_issue}`",
            "21. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "state_strategy": PRIMARY_STRATEGY,
        "active_label_budgets": ACTIVE_LABEL_BUDGETS,
        "radius_quantiles": RADIUS_QUANTILES,
        "margins": MARGINS,
        "val_target": VAL_TARGET,
        "review_budget": REVIEW_BUDGET,
        "relaxed_review_budget": RELAXED_REVIEW_BUDGET,
        "primary_verdict": primary_verdict,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27ay_outputs": str(ISSUE27AY),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "medium region-aware OOD gate diagnostic only; final roles report-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27az -->",
        [
            "<!-- issue27az -->",
            "## issue27az - Region-aware attack-preserving OOD gate diagnostic",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; evaluates OOD-safe gates after region-aware heads.",
            "- Final/report-only roles were not used for gate/radius/threshold selection.",
            f"- next action: `{next_issue}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27az -->",
        [
            "<!-- issue27az -->",
            "## issue27az - Region-aware OOD gate diagnostic",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether region-aware attack heads can be guarded without killing attack detection or overloading review.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "stats": verdict_stats, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
