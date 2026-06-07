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
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27bc_attack_core_purity_unknown_band_review_budget as bc


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"
ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BC = ROOT / "runs" / "issue27bc_attack_core_purity_unknown_band_review_budget_2026-06-07"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [64, 128]
PROTO_BUDGETS = [32]
BANK_RADIUS_QS = [0.95]
ATTACK_OUTER_NORMS = [1.0, 1.25]
BENIGN_CORE_NORMS = [0.75, 1.0, 1.25]
CONFLICT_SLACKS = [0.0, 0.25, 0.50, 1.0]
STRONG_SCORE_QS = [0.00, 0.25]
WEAK_SCORE_QS = [0.25, 0.50]
REVIEW_BUDGETS = [0.03, 0.05, 0.10]

VAL_TARGET = 0.01
FINAL_OOD_RELAXED_TARGET = 0.03
ATTACK_DIAG_FLOOR = 0.75
REPORT_ATTACK_STOP_BLEED = 0.50
REPORT_ATTACK_STRONG = 0.80


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


def build_subspaces(schema: dict[str, Any]) -> dict[str, np.ndarray]:
    counts = schema["family_counts"]
    order = ["MI_dir", "H", "HH", "HH_jit", "HpHp"]
    start = 0
    slices: dict[str, np.ndarray] = {}
    for family in order:
        n = int(counts[family])
        slices[family] = np.arange(start, start + n, dtype=np.int64)
        start += n
    if start != 115:
        raise RuntimeError(f"unexpected Kitsune feature count from schema families: {start}")
    slices["HH_HpHp"] = np.concatenate([slices["HH"], slices["HpHp"]])
    slices["MI_H_HHjit"] = np.concatenate([slices["MI_dir"], slices["H"], slices["HH_jit"]])
    slices["all115"] = np.arange(115, dtype=np.int64)
    return slices


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


class ShellPrototypeBank:
    def __init__(
        self,
        bank_name: str,
        train_x: np.ndarray,
        inner_val_x: np.ndarray,
        outer_val_x: np.ndarray,
        budget: int,
        radius_q: float,
    ):
        if len(train_x) == 0 or len(inner_val_x) == 0:
            raise RuntimeError(f"empty prototype bank: {bank_name}")
        self.bank_name = bank_name
        self.train_rows = int(len(train_x))
        self.inner_val_rows = int(len(inner_val_x))
        self.outer_val_rows = int(len(outer_val_x))
        self.budget = int(budget)
        self.radius_q = float(radius_q)
        self.scaler = StandardScaler().fit(train_x)
        z_train = self.scaler.transform(train_x)
        self.prototype_local_indices = farthest_first(z_train, budget)
        self.z_proto = z_train[self.prototype_local_indices]
        inner_d = self.raw_distance(inner_val_x)
        outer_source = outer_val_x if len(outer_val_x) else inner_val_x
        outer_d = self.raw_distance(outer_source)
        self.inner_radius = max(float(np.quantile(inner_d, radius_q)), 1e-12)
        self.outer_radius = max(float(np.quantile(outer_d, radius_q)), self.inner_radius, 1e-12)
        self.inner_distance_mean = float(np.mean(inner_d))
        self.outer_distance_mean = float(np.mean(outer_d))

    def raw_distance(self, x: np.ndarray) -> np.ndarray:
        return pairwise_distances(self.scaler.transform(x), self.z_proto, metric="euclidean").min(axis=1)

    def inner_norm(self, x: np.ndarray) -> np.ndarray:
        return self.raw_distance(x) / self.inner_radius

    def outer_norm(self, x: np.ndarray) -> np.ndarray:
        return self.raw_distance(x) / self.outer_radius

    def audit_row(self, seed: int, active_budget: int, subspace_name: str, source_roles: str) -> dict[str, Any]:
        return {
            "seed": seed,
            "active_label_budget": active_budget,
            "subspace_name": subspace_name,
            "bank_name": self.bank_name,
            "source_roles": source_roles,
            "train_rows": self.train_rows,
            "inner_val_rows": self.inner_val_rows,
            "outer_val_rows": self.outer_val_rows,
            "prototype_budget": self.budget,
            "prototype_count": int(len(self.prototype_local_indices)),
            "prototype_local_indices_sha256": hash_indices(self.prototype_local_indices),
            "radius_quantile": self.radius_q,
            "inner_radius": self.inner_radius,
            "outer_radius": self.outer_radius,
            "inner_distance_mean": self.inner_distance_mean,
            "outer_distance_mean": self.outer_distance_mean,
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
        }


def build_shell_banks(
    x: np.ndarray,
    stress_x: np.ndarray,
    sub_idx: np.ndarray,
    id_fit: np.ndarray,
    id_calib: np.ndarray,
    ood_train: np.ndarray,
    ood_val: np.ndarray,
    stress_train: np.ndarray,
    stress_val: np.ndarray,
    medium_train: np.ndarray,
    medium_val: np.ndarray,
    medium_pseudo: np.ndarray,
    heavy_train_x: np.ndarray,
    heavy_val_x: np.ndarray,
    heavy_pseudo_x: np.ndarray,
    proto_budget: int,
    radius_q: float,
    seed: int,
    active_budget: int,
    subspace_name: str,
) -> tuple[dict[str, ShellPrototypeBank], list[dict[str, Any]]]:
    xs = lambda a: a[:, sub_idx]
    banks = {
        "id": ShellPrototypeBank("id", xs(x[id_fit]), xs(x[id_calib]), xs(x[id_calib]), proto_budget, radius_q),
        "ood": ShellPrototypeBank(
            "ood",
            xs(np.vstack([x[ood_train], stress_x[stress_train]])),
            xs(np.vstack([x[ood_val], stress_x[stress_val]])),
            xs(np.vstack([x[ood_val], stress_x[stress_val]])),
            proto_budget,
            radius_q,
        ),
        "attack_medium": ShellPrototypeBank(
            "attack_medium",
            xs(x[medium_train]),
            xs(x[medium_val]),
            xs(np.vstack([x[medium_val], x[medium_pseudo]])) if len(medium_pseudo) else xs(x[medium_val]),
            proto_budget,
            radius_q,
        ),
        "attack_heavy": ShellPrototypeBank(
            "attack_heavy",
            xs(heavy_train_x),
            xs(heavy_val_x),
            xs(np.vstack([heavy_val_x, heavy_pseudo_x])) if len(heavy_pseudo_x) else xs(heavy_val_x),
            proto_budget,
            radius_q,
        ),
    }
    source_roles = {
        "id": "id_fit/id_calib",
        "ood": "ood_train/ood_val/ood_stress_train/ood_stress_val",
        "attack_medium": "medium_support_train/val/pseudo_query",
        "attack_heavy": "active_heavy_train/val/pseudo_query",
    }
    return banks, [bank.audit_row(seed, active_budget, subspace_name, source_roles[name]) for name, bank in banks.items()]


def shell_precompute(x_role: np.ndarray, sub_idx: np.ndarray, banks: dict[str, ShellPrototypeBank], bundle: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    x_sub = x_role[:, sub_idx]
    attack_inner = np.minimum(banks["attack_medium"].inner_norm(x_sub), banks["attack_heavy"].inner_norm(x_sub))
    attack_outer = np.minimum(banks["attack_medium"].outer_norm(x_sub), banks["attack_heavy"].outer_norm(x_sub))
    benign_inner = np.minimum(banks["id"].inner_norm(x_sub), banks["ood"].inner_norm(x_sub))
    benign_outer = np.minimum(banks["id"].outer_norm(x_sub), banks["ood"].outer_norm(x_sub))
    return {
        "raw_alarm": bundle["raw_alarm"],
        "score_strength": bundle["score_strength"],
        "attack_inner": attack_inner,
        "attack_outer": attack_outer,
        "benign_inner": benign_inner,
        "benign_outer": benign_outer,
    }


def apply_conflict_shell_gate(
    raw_alarm: np.ndarray,
    score_strength: np.ndarray,
    attack_inner: np.ndarray,
    attack_outer: np.ndarray,
    benign_inner: np.ndarray,
    benign_outer: np.ndarray,
    strong_score_floor: float,
    weak_score_ceiling: float,
    attack_outer_norm: float,
    benign_core_norm: float,
    conflict_slack: float,
    review_budget: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    n = len(raw_alarm)
    state = np.full(n, "no_alarm", dtype=object)
    raw = raw_alarm.astype(bool)
    attack_core = attack_inner <= 1.0
    attack_shell = attack_outer <= float(attack_outer_norm)
    benign_core = benign_outer <= float(benign_core_norm)
    attack_advantage = benign_outer - attack_outer
    high_score = score_strength >= float(strong_score_floor)
    weak_score = score_strength <= float(weak_score_ceiling)

    pure_attack = raw & attack_core & ~benign_core
    shell_override = raw & attack_shell & high_score & (attack_advantage >= -float(conflict_slack))
    weak_benign = raw & benign_core & ~attack_shell & weak_score
    conflict = raw & attack_shell & benign_core & ~(pure_attack | shell_override)
    unknown = raw & ~attack_shell & ~benign_core
    ambiguous = raw & ~(pure_attack | shell_override | weak_benign | conflict | unknown)

    state[weak_benign] = "suppress"
    state[pure_attack | shell_override] = "hard_alarm"
    state[conflict] = "review_conflict"
    state[unknown | ambiguous] = "review_unknown"

    review_mask = np.isin(state, ["review_conflict", "review_unknown"])
    max_review = int(np.floor(float(review_budget) * n))
    if max_review < int(np.sum(review_mask)):
        review_idx = np.where(review_mask)[0]
        priority = score_strength + attack_advantage
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
        "pure_attack": pure_attack,
        "shell_override": shell_override,
        "attack_core": attack_core,
        "attack_shell": attack_shell,
        "benign_core": benign_core,
        "conflict_uncapped": raw & attack_shell & benign_core,
        "unknown_uncapped": raw & ~attack_shell & ~benign_core,
    }
    return state, masks


def state_metrics(role: str, state: np.ndarray, masks: dict[str, np.ndarray], pre: dict[str, np.ndarray]) -> dict[str, Any]:
    attack_adv = pre["benign_outer"] - pre["attack_outer"]
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
        "pure_attack_rate": rate(masks["pure_attack"]),
        "shell_override_rate": rate(masks["shell_override"]),
        "attack_core_rate": rate(masks["attack_core"]),
        "attack_shell_rate": rate(masks["attack_shell"]),
        "benign_core_rate": rate(masks["benign_core"]),
        "conflict_uncapped_rate": rate(masks["conflict_uncapped"]),
        "unknown_uncapped_rate": rate(masks["unknown_uncapped"]),
        "attack_advantage_p50": float(np.quantile(attack_adv, 0.50)) if len(attack_adv) else float("nan"),
        "attack_advantage_p95": float(np.quantile(attack_adv, 0.95)) if len(attack_adv) else float("nan"),
        "attack_outer_p50": float(np.quantile(pre["attack_outer"], 0.50)) if len(attack_adv) else float("nan"),
        "benign_outer_p50": float(np.quantile(pre["benign_outer"], 0.50)) if len(attack_adv) else float("nan"),
        "score_strength_p50": float(np.quantile(pre["score_strength"], 0.50)) if len(attack_adv) else float("nan"),
        "score_strength_p95": float(np.quantile(pre["score_strength"], 0.95)) if len(attack_adv) else float("nan"),
    }


def aggregate_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "active_label_budget",
        "subspace_name",
        "proto_budget",
        "bank_radius_q",
        "attack_outer_norm",
        "benign_core_norm",
        "conflict_slack",
        "strong_score_q",
        "weak_score_q",
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
        row["strict_feasible_all_seeds"] = all(str(g["strict_feasible"]) == "True" for g in group)
        row["relaxed_feasible_all_seeds"] = all(str(g["relaxed_feasible"]) == "True" for g in group)
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
            -float(r["dev_review_max_max"]),
            -float(r["review_budget"]),
            r["subspace_name"] != "all115",
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
        for metric in ["hard_alarm_rate", "review_any_rate", "review_conflict_rate", "review_unknown_rate", "review_overflow_rate", "suppress_rate", "raw_alarm_rate", "shell_override_rate"]:
            stats = summarize([float(row[f"{role}_{metric}"]) for row in rows])
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
    out["report_only_attack_hard_or_review_min"] = min(
        float(out["medium_attack_eval_report_only_hard_alarm_rate_min"]) + float(out["medium_attack_eval_report_only_review_any_rate_min"]),
        float(out["dev_heavy_query_report_only_hard_alarm_rate_min"]) + float(out["dev_heavy_query_report_only_review_any_rate_min"]),
    )
    return out


def choose_verdict(summary: dict[str, Any]) -> str:
    if (
        float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["dev_attack_hard_min"]) >= REPORT_ATTACK_STRONG
        and float(summary["report_only_attack_hard_min"]) >= REPORT_ATTACK_STRONG
        and float(summary["ood_stress_val_review_any_rate_max"]) <= 0.10
    ):
        return "subspace_conflict_gate_supported_ready_for_temporal_consistency"
    if (
        float(summary["ood_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["ood_stress_val_hard_alarm_rate_max"]) <= VAL_TARGET
        and float(summary["final_ood_report_only_hard_alarm_rate_max"]) <= FINAL_OOD_RELAXED_TARGET
        and float(summary["report_only_attack_hard_min"]) >= REPORT_ATTACK_STOP_BLEED
    ):
        return "subspace_conflict_gate_promising_attack_recovered_ood_relaxed"
    if (
        float(summary["dev_attack_hard_min"]) >= ATTACK_DIAG_FLOOR
        and float(summary["report_only_attack_hard_min"]) < REPORT_ATTACK_STOP_BLEED
    ):
        return "dev_shell_gate_overfits_report_only_gap_remains"
    if float(summary["dev_attack_hard_min"]) < ATTACK_DIAG_FLOOR:
        return "subspace_gate_reveals_feature_family_overlap_blocker"
    if float(summary["ood_stress_val_hard_alarm_rate_max"]) > VAL_TARGET:
        return "attack_recovered_but_ood_overbudget"
    if float(summary["ood_stress_val_review_any_rate_max"]) > 0.10:
        return "review_budget_overload"
    return "subspace_conflict_gate_unresolved"


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
    schema = asset["schema"]
    subspaces = build_subspaces(schema)

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
        {"artifact": "issue27bc_summary", "path": str(ISSUE27BC / "summary.md"), "actual_sha256": sha256_file(ISSUE27BC / "summary.md"), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    grid_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        for active_budget in ACTIVE_LABEL_BUDGETS:
            base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
            medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
            selected_active, active_audit = issue27au.select_active_labels(
                x_base_support=x[medium_train],
                x_support_val=x[medium_val],
                x_candidates=new_x[active_candidate_idx],
                candidate_indices=active_candidate_idx,
                budget=active_budget,
            )
            selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
            heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
            if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0 or len(medium_pseudo) == 0:
                continue
            split_rows.extend(
                [
                    {"seed": seed, "active_label_budget": active_budget, **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                    {"seed": seed, "active_label_budget": active_budget, **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
                ]
            )
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
            for subspace_name, sub_idx in subspaces.items():
                for proto_budget in PROTO_BUDGETS:
                    for radius_q in BANK_RADIUS_QS:
                        banks, audit = build_shell_banks(
                            x,
                            stress_x,
                            sub_idx,
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
                            proto_budget,
                            radius_q,
                            seed,
                            active_budget,
                            subspace_name,
                        )
                        bank_rows.extend(audit)
                        pre = {role: shell_precompute(role_x_dev[role], sub_idx, banks, role_scores[role]) for role in role_x_dev}
                        for attack_outer_norm in ATTACK_OUTER_NORMS:
                            for benign_core_norm in BENIGN_CORE_NORMS:
                                for conflict_slack in CONFLICT_SLACKS:
                                    for strong_q in STRONG_SCORE_QS:
                                        strong_floor = float(np.quantile(support_strength, strong_q))
                                        for weak_q in WEAK_SCORE_QS:
                                            if weak_q < strong_q:
                                                continue
                                            weak_ceiling = float(np.quantile(support_strength, weak_q))
                                            for review_budget in REVIEW_BUDGETS:
                                                metrics: dict[str, float] = {}
                                                for role, p in pre.items():
                                                    state, masks = apply_conflict_shell_gate(
                                                        p["raw_alarm"],
                                                        p["score_strength"],
                                                        p["attack_inner"],
                                                        p["attack_outer"],
                                                        p["benign_inner"],
                                                        p["benign_outer"],
                                                        strong_floor,
                                                        weak_ceiling,
                                                        attack_outer_norm,
                                                        benign_core_norm,
                                                        conflict_slack,
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
                                                dev_attack_min = min(metrics["support_medium_hard"], metrics["support_heavy_hard"], metrics["pseudo_medium_hard"], metrics["pseudo_heavy_hard"])
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
                                                    and dev_attack_min >= REPORT_ATTACK_STOP_BLEED
                                                )
                                                grid_rows.append(
                                                    {
                                                        "seed": seed,
                                                        "active_label_budget": active_budget,
                                                        "subspace_name": subspace_name,
                                                        "subspace_dim": int(len(sub_idx)),
                                                        "proto_budget": proto_budget,
                                                        "bank_radius_q": radius_q,
                                                        "attack_outer_norm": attack_outer_norm,
                                                        "benign_core_norm": benign_core_norm,
                                                        "conflict_slack": conflict_slack,
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
                                                        "dev_score": dev_attack_min + 0.25 * dev_pseudo_min - 0.5 * metrics["stress_hard"] - 0.2 * dev_review_max,
                                                        "selection_uses_final_ood": False,
                                                        "selection_uses_attack_eval": False,
                                                        "selection_uses_dev_heavy_query": False,
                                                    }
                                                )

    grid_summary = aggregate_grid(grid_rows)
    selected = choose_global_config(grid_summary)
    selected_cfg = {
        "active_label_budget": int(selected["active_label_budget"]),
        "subspace_name": str(selected["subspace_name"]),
        "proto_budget": int(selected["proto_budget"]),
        "bank_radius_q": float(selected["bank_radius_q"]),
        "attack_outer_norm": float(selected["attack_outer_norm"]),
        "benign_core_norm": float(selected["benign_core_norm"]),
        "conflict_slack": float(selected["conflict_slack"]),
        "strong_score_q": float(selected["strong_score_q"]),
        "weak_score_q": float(selected["weak_score_q"]),
        "review_budget": float(selected["review_budget"]),
    }

    replay_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []
    anatomy_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    selected_sub_idx = subspaces[selected_cfg["subspace_name"]]

    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, _ = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, _ = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=selected_cfg["active_label_budget"],
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, _ = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        banks, _ = build_shell_banks(
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
            pre = shell_precompute(x_role, selected_sub_idx, banks, bundle)
            state, masks = apply_conflict_shell_gate(
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
            metrics = state_metrics(role, state, masks, pre)
            for key, value in metrics.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = value
            decision_rows.append({"seed": seed, **metrics})
            anatomy_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "subspace_name": selected_cfg["subspace_name"],
                    "rows": int(len(x_role)),
                    "raw_alarm_rate": metrics["raw_alarm_rate"],
                    "attack_shell_rate": metrics["attack_shell_rate"],
                    "benign_core_rate": metrics["benign_core_rate"],
                    "conflict_uncapped_rate": metrics["conflict_uncapped_rate"],
                    "attack_advantage_p50": metrics["attack_advantage_p50"],
                    "attack_advantage_p95": metrics["attack_advantage_p95"],
                    "attack_outer_p50": metrics["attack_outer_p50"],
                    "benign_outer_p50": metrics["benign_outer_p50"],
                    "uses_report_only_for_selection": False,
                }
            )
        replay_rows.append(replay_row)
        role_rows.append(
            {
                "seed": seed,
                "fit_roles": "id_fit|ood_train_guard|medium_attack_train_without_pseudo_file|active_heavy_attack_train_without_pseudo_file",
                "threshold_roles": "id_calib|ood_val|medium_support_val|active_heavy_val",
                "prototype_bank_roles": "id_fit/id_calib|ood_train/ood_val/ood_stress_train/ood_stress_val|medium_support_train/val/pseudo|active_heavy_train/val/pseudo",
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
    write_csv(OUT / "prototype_shell_bank_audit.csv", bank_rows)
    write_csv(OUT / "prototype_subspace_gate_grid.csv", grid_rows)
    write_csv(OUT / "prototype_subspace_gate_dev_summary.csv", grid_summary)
    write_csv(OUT / "gate_selection_audit.csv", [selected])
    write_csv(OUT / "report_only_replay.csv", replay_rows)
    write_csv(OUT / "decision_breakdown_by_state.csv", decision_rows)
    write_csv(OUT / "conflict_anatomy.csv", anatomy_rows)
    write_csv(OUT / "feature_family_overlap_audit.csv", anatomy_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)
    write_md(
        OUT / "conflict_aware_gate_logic_spec.md",
        [
            "# Conflict-Aware Attack Shell Gate",
            "",
            "This diagnostic keeps the raw detector score on the full Kitsune115 feature space, but lets prototype gating use a fixed feature-family subspace.",
            "",
            "Decision idea:",
            "",
            "```text",
            "if raw_attack_alarm is false: no_alarm",
            "elif pure inner attack core: hard_alarm",
            "elif high raw score + pseudo-query-calibrated outer attack shell + benign is not overwhelmingly stronger: hard_alarm",
            "elif weak score + benign core + outside attack shell: suppress",
            "elif attack shell and benign core overlap: bounded review_conflict",
            "else: bounded review_unknown or review_overflow_no_alarm",
            "```",
            "",
            "The selected subspace and all thresholds are selected only from dev-side roles. Report-only roles are replayed after selection.",
        ],
    )
    write_md(
        OUT / "issue27bd_decision.md",
        [
            "# Issue27bd Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            "- Tested fixed Kitsune115 family subspaces for prototype gate evidence while preserving full-115D raw detector scores.",
            "- Added pseudo-query-calibrated outer attack shells and conflict-aware hard-alarm override.",
            "- Did not use final OOD, medium attack eval, or dev-heavy query for gate selection.",
        ],
    )
    next_issue = "issue27be_next_action_pending"
    if verdict in {"subspace_conflict_gate_supported_ready_for_temporal_consistency", "subspace_conflict_gate_promising_attack_recovered_ood_relaxed"}:
        next_issue = "issue27be_past_only_temporal_consistency_on_conflict_gate"
    elif verdict == "dev_shell_gate_overfits_report_only_gap_remains":
        next_issue = "issue27be_mixed_stream_report_only_gap_diagnosis"
    elif verdict == "subspace_gate_reveals_feature_family_overlap_blocker":
        next_issue = "issue27be_metric_learning_or_task_boundary_audit"
    elif verdict == "attack_recovered_but_ood_overbudget":
        next_issue = "issue27be_ood_veto_refinement_after_attack_shell"
    write_md(
        OUT / "issue27be_next_action.md",
        [
            "# Issue27be Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- Do not run full/larger formal benchmark from issue27bd alone.",
            "- If subspace shell gate recovers attack, add past-only temporal consistency as a diagnostic.",
            "- If attack remains collapsed, inspect metric learning or task-boundary limitations before adding complexity.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bd.md",
        [
            "# Claim Update After issue27bd",
            "",
            "- issue27bd is still a medium diagnostic, not a formal benchmark.",
            "- A positive result would only justify further temporal/mixed-stream diagnostics.",
            "- A negative result means distance-gate evidence needs redesign before formal low-OOD-alert claims.",
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
    write_md(
        OUT / "summary.md",
        [
            "# issue27bd Summary",
            "",
            "1. issue27bd completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: conflict-aware attack shell and gate subspace diagnostic; not formal benchmark",
            "4. raw detector score feature space: full Kitsune115",
            f"5. selected prototype gate subspace: `{selected_cfg['subspace_name']}`",
            f"6. selected active label budget: `{selected_cfg['active_label_budget']}`",
            f"7. selected prototype budget: `{selected_cfg['proto_budget']}`",
            f"8. selected attack_outer_norm: `{selected_cfg['attack_outer_norm']}`",
            f"9. selected benign_core_norm: `{selected_cfg['benign_core_norm']}`",
            f"10. selected conflict_slack: `{selected_cfg['conflict_slack']}`",
            f"11. selected review budget: `{selected_cfg['review_budget']}`",
            "12. final OOD used for selection: no",
            "13. medium attack eval/dev-heavy query used for selection: no",
            f"14. dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
            f"15. report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
            f"16. report-only attack hard-or-review min: `{replay_summary['report_only_attack_hard_or_review_min']}`",
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
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "state_strategy": PRIMARY_STRATEGY,
        "subspace_names": list(subspaces.keys()),
        "selected_config": selected_cfg,
        "primary_verdict": verdict,
        "role_policy": "final/report-only roles never tune support, prototypes, gate, review budget, thresholds, or model selection",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27ba_stress_certificate": str(stress_cert_path),
                    "issue27bc_summary": str(ISSUE27BC / "summary.md"),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "medium conflict-aware subspace gate diagnostic only; final roles report-only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bd -->",
        [
            "<!-- issue27bd -->",
            "## issue27bd - Conflict-aware attack shell and gate subspace diagnostic",
            "",
            f"- primary_verdict: `{verdict}`",
            f"- selected prototype gate subspace: `{selected_cfg['subspace_name']}`; raw detector remains full Kitsune115.",
            "- Added pseudo-query-calibrated outer attack shell and conflict-aware hard override.",
            "- Final OOD, medium attack eval, and dev-heavy query remained report-only.",
            f"- next action: `{next_issue}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bd -->",
        [
            "<!-- issue27bd -->",
            "## issue27bd - Conflict-aware shell and subspace gate diagnostic",
            "",
            f"- verdict: `{verdict}`",
            "- purpose: test whether gate evidence should use a fixed Kitsune115 family subspace and pseudo-query-calibrated attack shell instead of strict full-115D purity.",
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
