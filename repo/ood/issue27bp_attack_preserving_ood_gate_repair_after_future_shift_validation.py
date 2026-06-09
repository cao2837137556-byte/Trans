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
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bo_attack_future_shift_validation_without_new_support as bo


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bp_attack_preserving_ood_gate_repair_after_future_shift_validation_2026-06-09"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BM = ROOT / "runs" / "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"
ISSUE27BO = ROOT / "runs" / "issue27bo_attack_future_shift_validation_without_new_support_2026-06-09"

PRIMARY_STRATEGY = "reset_at_split_boundary"
PRIMARY_CONTRACT = "phase_balanced_dev_v2"
SEEDS = [42, 43, 44, 45, 46]

VAL_OOD_TARGET = 0.01
ATTACK_FLOOR = 0.93
REVIEW_BUDGET = 0.05

# Keep the raw detector on full 115D, but let gate evidence use family-aware
# subspaces. HH was useful in issue27bd; all115 remains as a control.
# Bounded grid after issue27bd/bo: focus on the family subspaces that already
# showed useful separation, plus all115 only as an OOD-risk control. This keeps
# the diagnostic small enough to audit instead of becoming another broad sweep.
ATTACK_SUBSPACES = ["HH", "HH_HpHp"]
BENIGN_SUBSPACES = ["HH", "HH_jit", "MI_H_HHjit", "all115"]
ATTACK_CORE_QS = [0.95, 0.99]
ATTACK_OUTER_QS = [0.95]
BENIGN_CORE_QS = [0.95]
ATTACK_CORE_NORMS = [1.0]
ATTACK_OUTER_NORMS = [1.0, 1.25, 1.50]
BENIGN_CORE_NORMS = [0.75, 1.0, 1.5, 2.0, 3.0]
STRONG_MARGIN_QS = [0.00, 0.10]
WEAK_MARGIN_QS = [0.25]
PROTO_BUDGETS = [32]


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


def qstats(vals: np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean"]}
    return {
        "min": float(np.min(arr)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
    }


def build_subspaces(schema: dict[str, Any]) -> dict[str, np.ndarray]:
    counts = schema["family_counts"]
    start = 0
    out: dict[str, np.ndarray] = {}
    for family in ["MI_dir", "H", "HH", "HH_jit", "HpHp"]:
        n = int(counts[family])
        out[family] = np.arange(start, start + n, dtype=np.int64)
        start += n
    if start != 115:
        raise RuntimeError(f"unexpected Kitsune115 family size: {start}")
    out["HH_HpHp"] = np.concatenate([out["HH"], out["HpHp"]])
    out["MI_H_HHjit"] = np.concatenate([out["MI_dir"], out["H"], out["HH_jit"]])
    out["all115"] = np.arange(115, dtype=np.int64)
    return out


def farthest_first(z: np.ndarray, budget: int) -> np.ndarray:
    if len(z) == 0:
        return np.asarray([], dtype=np.int64)
    if budget >= len(z):
        return np.arange(len(z), dtype=np.int64)
    centroid = z.mean(axis=0, keepdims=True)
    first = int(np.argmin(pairwise_distances(z, centroid).ravel()))
    selected = [first]
    min_dist = pairwise_distances(z, z[[first]]).ravel()
    min_dist[first] = -1.0
    while len(selected) < budget:
        nxt = int(np.argmax(min_dist))
        selected.append(nxt)
        dist = pairwise_distances(z, z[[nxt]]).ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected] = -1.0
    return np.asarray(selected, dtype=np.int64)


class ProtoBank:
    def __init__(self, name: str, x_fit: np.ndarray, budget: int, radius_sets: dict[str, tuple[np.ndarray, float]]):
        if len(x_fit) == 0:
            raise RuntimeError(f"empty prototype bank: {name}")
        self.name = name
        self.fit_rows = int(len(x_fit))
        self.budget = int(budget)
        self.scaler = StandardScaler().fit(x_fit)
        z_fit = self.scaler.transform(x_fit)
        self.proto_local = farthest_first(z_fit, budget)
        self.z_proto = z_fit[self.proto_local]
        self.radii: dict[str, float] = {}
        for label, (x_rad, q) in radius_sets.items():
            d = self.raw_distance(x_rad if len(x_rad) else x_fit)
            self.radii[label] = max(float(np.quantile(d, q)), 1e-12)

    def raw_distance(self, x: np.ndarray) -> np.ndarray:
        if len(x) == 0:
            return np.asarray([], dtype=np.float64)
        z = self.scaler.transform(x)
        return pairwise_distances(z, self.z_proto, metric="euclidean").min(axis=1)

    def norm_distance(self, x: np.ndarray, radius_label: str) -> np.ndarray:
        return self.raw_distance(x) / self.radii[radius_label]


def role_records_and_features(
    x: np.ndarray,
    sidecar: list[dict[str, str]],
    new_x: np.ndarray,
    new_sidecar: list[dict[str, str]],
    attack_eval_idx: np.ndarray,
    final_ood_idx: np.ndarray,
    dev_heavy_query_idx: np.ndarray,
    support_val_rows: list[dict[str, str]],
    pseudo_rows: list[dict[str, str]],
) -> tuple[dict[str, np.ndarray], dict[str, bool], dict[str, list[dict[str, Any]]]]:
    support_val_records = bo.make_contract_records(support_val_rows)
    pseudo_records = bo.make_contract_records(pseudo_rows)
    pseudo_buckets = bo.temporal_thirds(pseudo_records, "dev_future")
    medium_report_records = bo.make_report_records(sidecar, attack_eval_idx, "medium_attack_eval_report_only")
    heavy_report_records = bo.make_report_records(new_sidecar, dev_heavy_query_idx, "dev_heavy_query_report_only")
    report_buckets: dict[str, list[dict[str, Any]]] = {
        "sealed_medium_attack_eval_report_only": medium_report_records,
        "sealed_dev_heavy_query_report_only": heavy_report_records,
    }
    report_buckets.update(bo.temporal_thirds(heavy_report_records, "sealed_heavy_future"))

    role_x: dict[str, np.ndarray] = {
        "support_val": bo.contract_features(support_val_rows, x, new_x),
        "medium_attack_eval_report_only": x[attack_eval_idx],
        "final_ood_report_only": x[final_ood_idx],
    }
    role_report_only = {
        "support_val": False,
        "medium_attack_eval_report_only": True,
        "final_ood_report_only": True,
    }
    role_records = {
        "support_val": support_val_records,
        "medium_attack_eval_report_only": medium_report_records,
        "final_ood_report_only": [],
    }
    for name, records in pseudo_buckets.items():
        role_x[name] = bo.role_feature(records, x, new_x)
        role_report_only[name] = False
        role_records[name] = records
    for name, records in report_buckets.items():
        if name == "sealed_medium_attack_eval_report_only":
            role_x[name] = x[attack_eval_idx]
        else:
            role_x[name] = bo.role_feature(records, x, new_x)
        role_report_only[name] = True
        role_records[name] = records
    return role_x, role_report_only, role_records


def precompute_gate_evidence(
    x_role: np.ndarray,
    score: np.ndarray,
    threshold: float,
    attack_bank: ProtoBank,
    benign_bank: ProtoBank,
) -> dict[str, np.ndarray]:
    margin = np.asarray(score, dtype=np.float64) - float(threshold)
    raw_alarm = margin > 0.0
    d_attack_core = attack_bank.norm_distance(x_role, "core")
    d_attack_outer = attack_bank.norm_distance(x_role, "outer")
    d_benign = benign_bank.norm_distance(x_role, "core")
    return {
        "score": np.asarray(score, dtype=np.float64),
        "margin": margin,
        "raw_alarm": raw_alarm,
        "d_attack_core": d_attack_core,
        "d_attack_outer": d_attack_outer,
        "d_benign": d_benign,
        "attack_advantage": d_benign - d_attack_outer,
    }


def bounded_review_mask(conflict: np.ndarray, conflict_strength: np.ndarray, budget: float) -> np.ndarray:
    conflict = np.asarray(conflict, dtype=bool)
    n = conflict.size
    out = np.zeros(n, dtype=bool)
    k = int(np.floor(float(budget) * n))
    k = max(0, min(k, int(np.sum(conflict))))
    if k == 0:
        return out
    idx = np.flatnonzero(conflict)
    order = np.argsort(-np.asarray(conflict_strength, dtype=np.float64)[idx])
    out[idx[order[:k]]] = True
    return out


def apply_attack_preserving_gate(pre: dict[str, np.ndarray], params: dict[str, float]) -> dict[str, np.ndarray]:
    raw = pre["raw_alarm"]
    margin = pre["margin"]
    attack_core = pre["d_attack_core"] <= params["attack_core_norm"]
    attack_outer = pre["d_attack_outer"] <= params["attack_outer_norm"]
    benign_core = pre["d_benign"] <= params["benign_core_norm"]
    strong_attack = raw & attack_core & (margin >= params["strong_margin_floor"])
    weak_attack = raw & ((margin <= params["weak_margin_ceiling"]) | (~attack_outer))
    conflict = raw & attack_outer & benign_core & (~strong_attack)
    conflict_strength = (1.0 / np.maximum(pre["d_attack_outer"], 1e-12)) + (1.0 / np.maximum(pre["d_benign"], 1e-12))
    review = bounded_review_mask(conflict, conflict_strength, params["review_budget"])
    conflict_overflow = conflict & (~review)
    suppress = raw & (~strong_attack) & (~review) & benign_core & (weak_attack | conflict_overflow)
    hard = raw & (~suppress) & (~review)
    hard = hard | strong_attack
    no_alarm = ~(hard | review | suppress)
    return {
        "hard_alarm": hard,
        "review": review,
        "suppress": suppress,
        "no_alarm": no_alarm,
        "raw_alarm": raw,
        "strong_attack": strong_attack,
        "attack_outer": attack_outer,
        "benign_core": benign_core,
        "conflict": conflict,
        "conflict_overflow": conflict_overflow,
    }


def summarize_role(role: str, pre: dict[str, np.ndarray], masks: dict[str, np.ndarray], is_report_only: bool) -> dict[str, Any]:
    row: dict[str, Any] = {
        "role": role,
        "n": int(len(pre["score"])),
        "is_report_only": bool(is_report_only),
        "raw_alarm_rate": rate(masks["raw_alarm"]),
        "hard_alarm_rate": rate(masks["hard_alarm"]),
        "review_rate": rate(masks["review"]),
        "suppress_rate": rate(masks["suppress"]),
        "strong_attack_rate": rate(masks["strong_attack"]),
        "attack_outer_rate": rate(masks["attack_outer"]),
        "benign_core_rate": rate(masks["benign_core"]),
        "conflict_rate": rate(masks["conflict"]),
        "conflict_overflow_rate": rate(masks["conflict_overflow"]),
    }
    for k, v in qstats(pre["margin"]).items():
        row[f"margin_{k}"] = v
    for k, v in qstats(pre["d_attack_outer"]).items():
        row[f"attack_outer_norm_{k}"] = v
    for k, v in qstats(pre["d_benign"]).items():
        row[f"benign_norm_{k}"] = v
    return row


def aggregate(rows: list[dict[str, Any]], keys: list[str], metrics: list[str]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, vals in sorted(groups.items(), key=lambda x: str(x[0])):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(vals)
        for m in metrics:
            arr = np.asarray([float(v[m]) for v in vals], dtype=np.float64)
            row[f"{m}_mean"] = float(np.mean(arr))
            row[f"{m}_min"] = float(np.min(arr))
            row[f"{m}_max"] = float(np.max(arr))
        out.append(row)
    return out


def choose_candidate(summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    feasible = [
        r
        for r in summary_rows
        if str(r["dev_feasible_all_seeds"]).lower() == "true"
    ]
    pool = feasible if feasible else summary_rows
    return max(
        pool,
        key=lambda r: (
            bool(str(r["dev_feasible_all_seeds"]).lower() == "true"),
            float(r["dev_attack_min_min"]),
            -float(r["ood_stress_val_hard_alarm_rate_max"]),
            -float(r["ood_val_hard_alarm_rate_max"]),
            -float(r["dev_review_max_max"]),
        ),
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    x = asset["X"]
    sidecar = asset["sidecar"]
    schema = asset["schema"]
    subspaces = build_subspaces(schema)

    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()

    support_train_rows = bo.load_contract_role("phase_balanced_support_train_indices.csv")
    support_val_rows = bo.load_contract_role("phase_balanced_support_val_indices.csv")
    pseudo_rows = bo.load_contract_role("phase_balanced_pseudo_query_dev_indices.csv")
    x_support_train = bo.contract_features(support_train_rows, x, new_x)
    x_support_val = bo.contract_features(support_val_rows, x, new_x)
    x_pseudo = bo.contract_features(pseudo_rows, x, new_x)

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    attack_eval_idx = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    final_ood_idx = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    _, dev_heavy_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    role_x_extra, role_report_only_extra, role_records = role_records_and_features(
        x,
        sidecar,
        new_x,
        new_sidecar,
        attack_eval_idx,
        final_ood_idx,
        dev_heavy_query_idx,
        support_val_rows,
        pseudo_rows,
    )

    input_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "fixed_medium_asset"},
        {"artifact": "issue27ba_ood_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path), "used_for": "dev_ood_stress_asset"},
        {"artifact": "issue27bm_phase_balanced_contract", "path": str(ISSUE27BM / "phase_balanced_contract_v2.json"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_contract_v2.json"), "used_for": "fixed_support_contract"},
        {"artifact": "issue27bo_summary", "path": str(ISSUE27BO / "summary.md"), "sha256": sha256_file(ISSUE27BO / "summary.md"), "used_for": "fixed_support_future_shift_context"},
    ]
    for check in checks + stress_checks + new_checks:
        input_rows.append({**check, "used_for": "hash_validation"})

    dev_role_x = {
        "id_calib": x[id_calib],
        "ood_val": x[ood_val],
        "ood_stress_val": stress_x[stress_val],
        "support_val": x_support_val,
        "dev_future_near": role_x_extra["dev_future_near"],
        "dev_future_mid": role_x_extra["dev_future_mid"],
        "dev_future_far": role_x_extra["dev_future_far"],
    }
    dev_role_report = {k: False for k in dev_role_x}
    replay_role_x = {
        **dev_role_x,
        "sealed_medium_attack_eval_report_only": role_x_extra["sealed_medium_attack_eval_report_only"],
        "sealed_dev_heavy_query_report_only": role_x_extra["sealed_dev_heavy_query_report_only"],
        "sealed_heavy_future_near": role_x_extra["sealed_heavy_future_near"],
        "sealed_heavy_future_mid": role_x_extra["sealed_heavy_future_mid"],
        "sealed_heavy_future_far": role_x_extra["sealed_heavy_future_far"],
        "final_ood_report_only": x[final_ood_idx],
    }
    replay_report = {**dev_role_report}
    for k in replay_role_x:
        replay_report.setdefault(k, k.endswith("report_only") or k.startswith("sealed_") or k == "final_ood_report_only")

    grid_rows: list[dict[str, Any]] = []
    gate_rows: list[dict[str, Any]] = []
    bank_rows: list[dict[str, Any]] = []
    replay_detail_rows: list[dict[str, Any]] = []
    score_direction_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        model = bo.FrozenAttackHistGB(seed)
        model.fit(x[id_fit], x[ood_train], x_support_train)
        threshold = float(np.quantile(model.score(x[id_calib]), 0.99))
        threshold_rows.append(
            {
                "seed": seed,
                "threshold_rule": bo.FROZEN_THRESHOLD_RULE,
                "threshold": threshold,
                "id_calib_raw_alarm": bo.rate(model.score(x[id_calib]), threshold),
                "support_val_raw_detection": bo.rate(model.score(x_support_val), threshold),
                "uses_ood_for_threshold": False,
                "uses_report_only_for_threshold": False,
            }
        )
        score_direction_rows.append({"seed": seed, **model.direction_check})
        scores_dev = {role: model.score(rx) for role, rx in dev_role_x.items()}
        scores_replay = {role: model.score(rx) for role, rx in replay_role_x.items()}
        margin_source = np.concatenate(
            [
                scores_dev["support_val"] - threshold,
                scores_dev["dev_future_near"] - threshold,
                scores_dev["dev_future_mid"] - threshold,
                scores_dev["dev_future_far"] - threshold,
            ]
        )
        margin_source = margin_source[np.isfinite(margin_source)]

        for attack_subspace in ATTACK_SUBSPACES:
            attack_idx = subspaces[attack_subspace]
            attack_fit = x_support_train[:, attack_idx]
            attack_core_val = x_support_val[:, attack_idx]
            attack_outer_val = x_pseudo[:, attack_idx]
            for benign_subspace in BENIGN_SUBSPACES:
                benign_idx = subspaces[benign_subspace]
                benign_fit = np.vstack([x[id_fit][:, benign_idx], x[ood_train][:, benign_idx], stress_x[stress_train][:, benign_idx]])
                benign_core_val = np.vstack([x[id_calib][:, benign_idx], x[ood_val][:, benign_idx], stress_x[stress_val][:, benign_idx]])
                for budget in PROTO_BUDGETS:
                    for aq_core in ATTACK_CORE_QS:
                        for aq_outer in ATTACK_OUTER_QS:
                            attack_bank = ProtoBank(
                                "attack",
                                attack_fit,
                                budget,
                                {
                                    "core": (attack_core_val, aq_core),
                                    "outer": (attack_outer_val, aq_outer),
                                },
                            )
                            for bq in BENIGN_CORE_QS:
                                benign_bank = ProtoBank("benign", benign_fit, budget, {"core": (benign_core_val, bq)})
                                bank_rows.append(
                                    {
                                        "seed": seed,
                                        "attack_subspace": attack_subspace,
                                        "benign_subspace": benign_subspace,
                                        "proto_budget": budget,
                                        "attack_core_q": aq_core,
                                        "attack_outer_q": aq_outer,
                                        "benign_core_q": bq,
                                        "attack_fit_rows": attack_bank.fit_rows,
                                        "benign_fit_rows": benign_bank.fit_rows,
                                        "attack_core_radius": attack_bank.radii["core"],
                                        "attack_outer_radius": attack_bank.radii["outer"],
                                        "benign_core_radius": benign_bank.radii["core"],
                                    }
                                )
                                # Banks are fit on subspace-specific features, so
                                # precompute evidence with the same family slices.
                                pre_dev = {}
                                for role, rx in dev_role_x.items():
                                    score = scores_dev[role]
                                    margin = score - threshold
                                    pre_dev[role] = {
                                        "score": score,
                                        "margin": margin,
                                        "raw_alarm": margin > 0.0,
                                        "d_attack_core": attack_bank.norm_distance(rx[:, attack_idx], "core"),
                                        "d_attack_outer": attack_bank.norm_distance(rx[:, attack_idx], "outer"),
                                        "d_benign": benign_bank.norm_distance(rx[:, benign_idx], "core"),
                                    }
                                    pre_dev[role]["attack_advantage"] = pre_dev[role]["d_benign"] - pre_dev[role]["d_attack_outer"]
                                for core_norm in ATTACK_CORE_NORMS:
                                    for outer_norm in ATTACK_OUTER_NORMS:
                                        for benign_norm in BENIGN_CORE_NORMS:
                                            for strong_q in STRONG_MARGIN_QS:
                                                strong_floor = float(np.quantile(margin_source, strong_q))
                                                for weak_q in WEAK_MARGIN_QS:
                                                    if weak_q < strong_q:
                                                        continue
                                                    weak_ceiling = float(np.quantile(margin_source, weak_q))
                                                    params = {
                                                        "attack_core_norm": core_norm,
                                                        "attack_outer_norm": outer_norm,
                                                        "benign_core_norm": benign_norm,
                                                        "strong_margin_floor": strong_floor,
                                                        "weak_margin_ceiling": weak_ceiling,
                                                        "review_budget": REVIEW_BUDGET,
                                                    }
                                                    metric_by_role: dict[str, dict[str, Any]] = {}
                                                    for role, pre in pre_dev.items():
                                                        masks = apply_attack_preserving_gate(pre, params)
                                                        metric_by_role[role] = summarize_role(role, pre, masks, False)
                                                    dev_future_min = min(
                                                        metric_by_role["dev_future_near"]["hard_alarm_rate"],
                                                        metric_by_role["dev_future_mid"]["hard_alarm_rate"],
                                                        metric_by_role["dev_future_far"]["hard_alarm_rate"],
                                                    )
                                                    dev_attack_min = min(metric_by_role["support_val"]["hard_alarm_rate"], dev_future_min)
                                                    dev_review_max = max(
                                                        metric_by_role["id_calib"]["review_rate"],
                                                        metric_by_role["ood_val"]["review_rate"],
                                                        metric_by_role["ood_stress_val"]["review_rate"],
                                                    )
                                                    dev_feasible = (
                                                        metric_by_role["id_calib"]["hard_alarm_rate"] <= VAL_OOD_TARGET
                                                        and metric_by_role["ood_val"]["hard_alarm_rate"] <= VAL_OOD_TARGET
                                                        and metric_by_role["ood_stress_val"]["hard_alarm_rate"] <= VAL_OOD_TARGET
                                                        and metric_by_role["support_val"]["hard_alarm_rate"] >= ATTACK_FLOOR
                                                        and dev_future_min >= ATTACK_FLOOR
                                                        and dev_review_max <= REVIEW_BUDGET + 1e-12
                                                    )
                                                    grid_rows.append(
                                                        {
                                                            "seed": seed,
                                                            "attack_subspace": attack_subspace,
                                                            "benign_subspace": benign_subspace,
                                                            "proto_budget": budget,
                                                            "attack_core_q": aq_core,
                                                            "attack_outer_q": aq_outer,
                                                            "benign_core_q": bq,
                                                            **params,
                                                            "id_calib_hard_alarm_rate": metric_by_role["id_calib"]["hard_alarm_rate"],
                                                            "ood_val_hard_alarm_rate": metric_by_role["ood_val"]["hard_alarm_rate"],
                                                            "ood_stress_val_hard_alarm_rate": metric_by_role["ood_stress_val"]["hard_alarm_rate"],
                                                            "support_val_hard_alarm_rate": metric_by_role["support_val"]["hard_alarm_rate"],
                                                            "dev_future_near_hard_alarm_rate": metric_by_role["dev_future_near"]["hard_alarm_rate"],
                                                            "dev_future_mid_hard_alarm_rate": metric_by_role["dev_future_mid"]["hard_alarm_rate"],
                                                            "dev_future_far_hard_alarm_rate": metric_by_role["dev_future_far"]["hard_alarm_rate"],
                                                            "dev_future_min": dev_future_min,
                                                            "dev_attack_min": dev_attack_min,
                                                            "dev_review_max": dev_review_max,
                                                            "dev_feasible": dev_feasible,
                                                            "selection_uses_final_ood": False,
                                                            "selection_uses_report_only_attack": False,
                                                            "dev_score": dev_attack_min - 2.0 * metric_by_role["ood_stress_val"]["hard_alarm_rate"] - dev_review_max,
                                                        }
                                                    )

    grid_summary = aggregate(
        grid_rows,
        [
            "attack_subspace",
            "benign_subspace",
            "proto_budget",
            "attack_core_q",
            "attack_outer_q",
            "benign_core_q",
            "attack_core_norm",
            "attack_outer_norm",
            "benign_core_norm",
            "strong_margin_floor",
            "weak_margin_ceiling",
            "review_budget",
        ],
        [
            "id_calib_hard_alarm_rate",
            "ood_val_hard_alarm_rate",
            "ood_stress_val_hard_alarm_rate",
            "support_val_hard_alarm_rate",
            "dev_future_min",
            "dev_attack_min",
            "dev_review_max",
            "dev_score",
        ],
    )
    for row in grid_summary:
        row["dev_feasible_all_seeds"] = (
            float(row["id_calib_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
            and float(row["ood_val_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
            and float(row["ood_stress_val_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
            and float(row["support_val_hard_alarm_rate_min"]) >= ATTACK_FLOOR
            and float(row["dev_future_min_min"]) >= ATTACK_FLOOR
            and float(row["dev_review_max_max"]) <= REVIEW_BUDGET + 1e-12
        )
    selected = choose_candidate(grid_summary)
    ood_clean = [
        r
        for r in grid_summary
        if float(r["id_calib_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
        and float(r["ood_val_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
        and float(r["ood_stress_val_hard_alarm_rate_max"]) <= VAL_OOD_TARGET
        and float(r["dev_review_max_max"]) <= REVIEW_BUDGET + 1e-12
    ]
    attack_safe = [
        r
        for r in grid_summary
        if float(r["support_val_hard_alarm_rate_min"]) >= ATTACK_FLOOR
        and float(r["dev_future_min_min"]) >= ATTACK_FLOOR
        and float(r["dev_review_max_max"]) <= REVIEW_BUDGET + 1e-12
    ]
    best_ood_clean = max(ood_clean, key=lambda r: float(r["dev_attack_min_min"])) if ood_clean else {}
    best_attack_safe = min(
        attack_safe,
        key=lambda r: max(
            float(r["id_calib_hard_alarm_rate_max"]),
            float(r["ood_val_hard_alarm_rate_max"]),
            float(r["ood_stress_val_hard_alarm_rate_max"]),
        ),
    ) if attack_safe else {}
    tradeoff_frontier = []
    if best_ood_clean:
        tradeoff_frontier.append({"frontier_point": "best_ood_clean", **best_ood_clean})
    if best_attack_safe:
        tradeoff_frontier.append({"frontier_point": "best_attack_safe", **best_attack_safe})
    selected_params = {
        "attack_subspace": selected["attack_subspace"],
        "benign_subspace": selected["benign_subspace"],
        "proto_budget": int(selected["proto_budget"]),
        "attack_core_q": float(selected["attack_core_q"]),
        "attack_outer_q": float(selected["attack_outer_q"]),
        "benign_core_q": float(selected["benign_core_q"]),
        "attack_core_norm": float(selected["attack_core_norm"]),
        "attack_outer_norm": float(selected["attack_outer_norm"]),
        "benign_core_norm": float(selected["benign_core_norm"]),
        "strong_margin_floor": float(selected["strong_margin_floor"]),
        "weak_margin_ceiling": float(selected["weak_margin_ceiling"]),
        "review_budget": float(selected["review_budget"]),
    }

    replay_rows: list[dict[str, Any]] = []
    attack_preservation_rows: list[dict[str, Any]] = []
    ood_suppression_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []

    attack_idx = subspaces[str(selected_params["attack_subspace"])]
    benign_idx = subspaces[str(selected_params["benign_subspace"])]

    for seed in SEEDS:
        model = bo.FrozenAttackHistGB(seed)
        model.fit(x[id_fit], x[ood_train], x_support_train)
        threshold = float(np.quantile(model.score(x[id_calib]), 0.99))
        scores_replay = {role: model.score(rx) for role, rx in replay_role_x.items()}
        attack_bank = ProtoBank(
            "attack",
            x_support_train[:, attack_idx],
            int(selected_params["proto_budget"]),
            {
                "core": (x_support_val[:, attack_idx], float(selected_params["attack_core_q"])),
                "outer": (x_pseudo[:, attack_idx], float(selected_params["attack_outer_q"])),
            },
        )
        benign_bank = ProtoBank(
            "benign",
            np.vstack([x[id_fit][:, benign_idx], x[ood_train][:, benign_idx], stress_x[stress_train][:, benign_idx]]),
            int(selected_params["proto_budget"]),
            {"core": (np.vstack([x[id_calib][:, benign_idx], x[ood_val][:, benign_idx], stress_x[stress_val][:, benign_idx]]), float(selected_params["benign_core_q"]))},
        )
        params = {
            "attack_core_norm": float(selected_params["attack_core_norm"]),
            "attack_outer_norm": float(selected_params["attack_outer_norm"]),
            "benign_core_norm": float(selected_params["benign_core_norm"]),
            "strong_margin_floor": float(selected_params["strong_margin_floor"]),
            "weak_margin_ceiling": float(selected_params["weak_margin_ceiling"]),
            "review_budget": float(selected_params["review_budget"]),
        }
        for role, rx in replay_role_x.items():
            pre = {
                "score": scores_replay[role],
                "margin": scores_replay[role] - threshold,
                "raw_alarm": scores_replay[role] > threshold,
                "d_attack_core": attack_bank.norm_distance(rx[:, attack_idx], "core"),
                "d_attack_outer": attack_bank.norm_distance(rx[:, attack_idx], "outer"),
                "d_benign": benign_bank.norm_distance(rx[:, benign_idx], "core"),
            }
            pre["attack_advantage"] = pre["d_benign"] - pre["d_attack_outer"]
            masks = apply_attack_preserving_gate(pre, params)
            row = {
                "seed": seed,
                "role": role,
                "is_report_only": replay_report[role],
                **selected_params,
                **summarize_role(role, pre, masks, replay_report[role]),
            }
            replay_detail_rows.append(row)
            if "attack" in role or "future" in role or role == "support_val":
                attack_preservation_rows.append(row)
            if role in {"id_calib", "ood_val", "ood_stress_val", "final_ood_report_only"}:
                ood_suppression_rows.append(row)
            review_rows.append(
                {
                    "seed": seed,
                    "role": role,
                    "is_report_only": replay_report[role],
                    "review_rate": row["review_rate"],
                    "review_budget": selected_params["review_budget"],
                    "review_over_budget": row["review_rate"] > float(selected_params["review_budget"]) + 1e-12,
                    "conflict_rate": row["conflict_rate"],
                    "conflict_overflow_rate": row["conflict_overflow_rate"],
                }
            )
        compact = {"seed": seed, **selected_params}
        for row in replay_detail_rows:
            if row["seed"] == seed:
                compact[f"{row['role']}_hard_alarm_rate"] = row["hard_alarm_rate"]
                compact[f"{row['role']}_review_rate"] = row["review_rate"]
                compact[f"{row['role']}_raw_alarm_rate"] = row["raw_alarm_rate"]
        replay_rows.append(compact)

    replay_summary = aggregate(
        replay_detail_rows,
        ["role", "is_report_only"],
        ["raw_alarm_rate", "hard_alarm_rate", "review_rate", "suppress_rate", "strong_attack_rate", "conflict_rate"],
    )
    def get_summary(role: str, metric: str, stat: str) -> float:
        for row in replay_summary:
            if row["role"] == role:
                return float(row[f"{metric}_{stat}"])
        return float("nan")

    dev_attack_min = min(
        get_summary("support_val", "hard_alarm_rate", "min"),
        get_summary("dev_future_near", "hard_alarm_rate", "min"),
        get_summary("dev_future_mid", "hard_alarm_rate", "min"),
        get_summary("dev_future_far", "hard_alarm_rate", "min"),
    )
    dev_ood_max = max(
        get_summary("id_calib", "hard_alarm_rate", "max"),
        get_summary("ood_val", "hard_alarm_rate", "max"),
        get_summary("ood_stress_val", "hard_alarm_rate", "max"),
    )
    dev_review_max = max(
        get_summary("id_calib", "review_rate", "max"),
        get_summary("ood_val", "review_rate", "max"),
        get_summary("ood_stress_val", "review_rate", "max"),
    )
    report_attack_min = min(
        get_summary("sealed_medium_attack_eval_report_only", "hard_alarm_rate", "min"),
        get_summary("sealed_dev_heavy_query_report_only", "hard_alarm_rate", "min"),
        get_summary("sealed_heavy_future_near", "hard_alarm_rate", "min"),
        get_summary("sealed_heavy_future_mid", "hard_alarm_rate", "min"),
        get_summary("sealed_heavy_future_far", "hard_alarm_rate", "min"),
    )
    final_ood_max = get_summary("final_ood_report_only", "hard_alarm_rate", "max")

    best_ood_clean_attack = float(best_ood_clean.get("dev_attack_min_min", float("nan"))) if best_ood_clean else float("nan")
    best_attack_safe_ood = max(
        float(best_attack_safe.get("id_calib_hard_alarm_rate_max", float("nan"))),
        float(best_attack_safe.get("ood_val_hard_alarm_rate_max", float("nan"))),
        float(best_attack_safe.get("ood_stress_val_hard_alarm_rate_max", float("nan"))),
    ) if best_attack_safe else float("nan")

    if dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET and dev_review_max <= REVIEW_BUDGET and final_ood_max <= VAL_OOD_TARGET and report_attack_min >= ATTACK_FLOOR:
        verdict = "attack_preserving_ood_gate_dev_passed_report_only_also_clean_ready_for_larger_sanity"
    elif dev_attack_min >= ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET and dev_review_max <= REVIEW_BUDGET:
        verdict = "attack_preserving_ood_gate_dev_passed_final_report_only_gap_remains"
    elif np.isfinite(best_ood_clean_attack) and np.isfinite(best_attack_safe_ood) and best_ood_clean_attack < ATTACK_FLOOR and best_attack_safe_ood > VAL_OOD_TARGET:
        verdict = "attack_ood_tradeoff_frontier_confirmed_needs_decoupled_ood_risk"
    elif dev_attack_min < ATTACK_FLOOR and dev_ood_max <= VAL_OOD_TARGET:
        verdict = "ood_gate_still_attack_destructive_blocked"
    elif dev_attack_min >= ATTACK_FLOOR and dev_ood_max > VAL_OOD_TARGET:
        verdict = "attack_preserved_but_dev_ood_overbudget"
    else:
        verdict = "no_dev_feasible_attack_preserving_ood_gate"

    next_action = "issue27bq_larger_sanity_on_attack_preserving_ood_gate" if "dev_passed" in verdict else "issue27bq_ood_risk_scorer_or_task_boundary_repair_before_larger"

    role_access_rows = [
        {
            "stage": "attack_model_fit",
            "allowed_roles": "id_fit|ood_train|phase_balanced_support_train",
            "forbidden_roles": "support_val|dev_future_query|ood_stress_val|final_ood|attack_eval|dev_heavy_query",
            "uses_final_or_report_only": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "raw_attack_threshold",
            "allowed_roles": "id_calib",
            "forbidden_roles": "ood_val|ood_stress_val|support_val|dev_future_query|final_ood|attack_eval|dev_heavy_query",
            "uses_final_or_report_only": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "gate_selection",
            "allowed_roles": "id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "forbidden_roles": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only|sealed_heavy_future_replay",
            "uses_final_or_report_only": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "report_only_replay",
            "allowed_roles": "final_ood|sealed_attack_replay",
            "forbidden_roles": "using_replay_to_change_gate_or_support",
            "uses_final_or_report_only": True,
            "forbidden_role_access": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "gate_candidate_grid.csv", grid_rows)
    write_csv(OUT / "gate_dev_summary.csv", grid_summary)
    write_csv(OUT / "gate_selection_audit.csv", [selected])
    write_csv(OUT / "gate_tradeoff_frontier.csv", tradeoff_frontier)
    write_csv(OUT / "prototype_bank_audit.csv", bank_rows)
    write_csv(OUT / "report_only_replay_table.csv", replay_detail_rows)
    write_csv(OUT / "report_only_replay_summary.csv", replay_summary)
    write_csv(OUT / "attack_preservation_audit.csv", attack_preservation_rows)
    write_csv(OUT / "ood_suppression_audit.csv", ood_suppression_rows)
    write_csv(OUT / "conflict_review_budget_audit.csv", review_rows)
    write_csv(OUT / "frozen_threshold_audit.csv", threshold_rows)
    write_csv(OUT / "score_direction_audit.csv", score_direction_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "family_aware_gate_logic_spec.md",
        [
            "# Family-Aware Attack-Preserving OOD Gate",
            "",
            "- Raw attack score stays on full Kitsune115.",
            "- Attack-core evidence uses a selected Kitsune family subspace.",
            "- Benign/OOD-risk evidence uses a separately selected family subspace.",
            "- Strong attack-core alarms cannot be suppressed by the OOD gate.",
            "- Weak attack alarms that sit inside the benign/OOD core can be suppressed.",
            "- Attack/OOD conflicts are sent to bounded review before overflow handling.",
            "- Final/report-only roles are replay-only and never select subspaces, thresholds, prototypes, or review budgets.",
        ],
    )
    write_md(
        OUT / "issue27bp_decision.md",
        [
            "# issue27bp Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- selected attack subspace: `{selected_params['attack_subspace']}`",
            f"- selected benign/OOD subspace: `{selected_params['benign_subspace']}`",
            f"- dev attack min: `{dev_attack_min}`",
            f"- dev OOD hard max: `{dev_ood_max}`",
            f"- dev review max: `{dev_review_max}`",
            f"- report-only attack min: `{report_attack_min}`",
            f"- final OOD hard max report-only: `{final_ood_max}`",
            f"- best OOD-clean dev attack min: `{best_ood_clean_attack}`",
            f"- best attack-safe dev OOD hard max: `{best_attack_safe_ood}`",
            "- Report-only results are not used to select the gate.",
        ],
    )
    write_md(
        OUT / "issue27bq_next_action.md",
        [
            "# issue27bq Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If dev gate passes, run a larger sanity check before any full/formal benchmark.",
            "- If dev OOD remains over budget, repair OOD-risk scorer or OOD stress contract before adding more attack complexity.",
            "- If attack falls below 0.93, the gate is still attack-destructive and must not proceed.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bp.md",
        [
            "# Claim Update After issue27bp",
            "",
            "- issue27bp remains a medium diagnostic and cannot support formal benchmark claims.",
            "- A passing dev result would only support moving to larger sanity, not paper-result reporting.",
            "- Final/report-only replay is used only as an independence-preserving stress signal.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bp Summary",
            "",
            "1. issue27bp completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: attack-preserving OOD gate repair diagnostic",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. raw attack scorer changed: no",
            "7. OOD gate selection used final/report-only: no",
            f"8. selected attack subspace: `{selected_params['attack_subspace']}`",
            f"9. selected benign/OOD subspace: `{selected_params['benign_subspace']}`",
            f"10. dev attack min: `{dev_attack_min}`",
            f"11. dev OOD hard max: `{dev_ood_max}`",
            f"12. dev review max: `{dev_review_max}`",
            f"13. report-only attack min: `{report_attack_min}`",
            f"14. final OOD hard max report-only: `{final_ood_max}`",
            f"15. best OOD-clean dev attack min: `{best_ood_clean_attack}`",
            f"16. best attack-safe dev OOD hard max: `{best_attack_safe_ood}`",
            f"17. next action: `{next_action}`",
            "18. formal benchmark allowed: no",
            "19. commit hash: reported in final response",
        ],
    )

    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": verdict,
                "selected_params": selected_params,
                "seeds": SEEDS,
                "val_ood_target": VAL_OOD_TARGET,
                "attack_floor": ATTACK_FLOOR,
                "review_budget": REVIEW_BUDGET,
                "final_report_only_never_selects_gate": True,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "scope": "medium family-aware attack-preserving OOD gate diagnostic",
                "fit_roles": ["id_fit", "ood_train", "phase_balanced_support_train"],
                "raw_threshold_roles": ["id_calib"],
                "gate_selection_roles": ["id_calib", "ood_val", "ood_stress_val", "support_val", "dev_future_near", "dev_future_mid", "dev_future_far"],
                "report_only_roles": ["final_ood", "sealed_medium_attack_eval", "sealed_dev_heavy_query"],
                "formal_benchmark": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bp_attack_preserving_ood_gate -->",
        [
            "## issue27bp - attack-preserving OOD gate repair after future-shift validation",
            "",
            "<!-- issue27bp_attack_preserving_ood_gate -->",
            f"- Verdict: `{verdict}`.",
            f"- Selected attack subspace: `{selected_params['attack_subspace']}`; selected benign/OOD subspace: `{selected_params['benign_subspace']}`.",
            f"- Dev attack min: `{dev_attack_min}`; dev OOD hard max: `{dev_ood_max}`; dev review max: `{dev_review_max}`.",
            f"- Report-only attack min: `{report_attack_min}`; final OOD hard max report-only: `{final_ood_max}`.",
            "- 115D frontend, split, support, and raw attack scorer remained frozen.",
            "- Formal benchmark remains blocked.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bp_attack_preserving_ood_gate -->",
        [
            "## issue27bp - attack-preserving OOD gate repair",
            "",
            "<!-- issue27bp_attack_preserving_ood_gate -->",
            "- Stage: medium diagnostic for family-aware gate evidence.",
            f"- Primary verdict: `{verdict}`.",
            "- Full 115D raw attack scorer stayed fixed; prototype gate evidence used selected Kitsune family subspaces.",
            "- Final/report-only roles remained replay-only.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": verdict, "selected_params": selected_params, "dev_attack_min": dev_attack_min, "dev_ood_max": dev_ood_max, "final_ood_max": final_ood_max, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
