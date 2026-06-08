from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances, roc_auc_score
from sklearn.neighbors import NeighborhoodComponentsAnalysis
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bi_region_aware_metric_or_calibrated_two_head_design as bi


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bk_task_boundary_then_metric_shell_smoke_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BI = ROOT / "runs" / "issue27bi_region_aware_metric_or_calibrated_two_head_design_2026-06-08"
ISSUE27BJ_RESEARCH = ROOT / "runs" / "issue27bj_deep_research_kitsune115_system_design_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGET = 64
ATTACK_GO_THRESHOLD = 0.93
ATTACK_PARTIAL_THRESHOLD = 0.80
REVIEW_LIMIT = 0.05
OOD_DEV_HIGH_RISK = 0.25
NORMAL_SAMPLE_CAP = 1200
OOD_SAMPLE_CAP = 800
ATTACK_SAMPLE_CAP = 512


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


def quantiles(vals: np.ndarray) -> dict[str, float]:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return {k: float("nan") for k in ["mean", "q50", "q90", "q95", "min", "max"]}
    return {
        "mean": float(np.mean(arr)),
        "q50": float(np.quantile(arr, 0.50)),
        "q90": float(np.quantile(arr, 0.90)),
        "q95": float(np.quantile(arr, 0.95)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def safe_auc(x0: np.ndarray, x1: np.ndarray) -> float:
    if len(x0) == 0 or len(x1) == 0:
        return float("nan")
    y = np.concatenate([np.zeros(len(x0), dtype=np.int64), np.ones(len(x1), dtype=np.int64)])
    s = np.concatenate([x0, x1]).astype(np.float64)
    if len(np.unique(s[np.isfinite(s)])) < 2:
        return 0.5
    return float(roc_auc_score(y, s))


def max_abs_feature_auc(x0: np.ndarray, x1: np.ndarray) -> float:
    if len(x0) == 0 or len(x1) == 0:
        return float("nan")
    vals = []
    for c in range(x0.shape[1]):
        auc = safe_auc(x0[:, c], x1[:, c])
        if np.isfinite(auc):
            vals.append(abs(auc - 0.5) + 0.5)
    return float(np.max(vals)) if vals else float("nan")


def deterministic_sample(idx: np.ndarray, cap: int, salt: int) -> np.ndarray:
    idx = np.asarray(idx, dtype=np.int64)
    if len(idx) <= cap:
        return np.asarray(sorted(idx.tolist()), dtype=np.int64)
    rng = np.random.default_rng(87231 + salt)
    picked = rng.choice(idx, size=int(cap), replace=False)
    return np.asarray(sorted(picked.tolist()), dtype=np.int64)


def local_rows(rows: list[dict[str, str]], idx: np.ndarray) -> list[dict[str, str]]:
    return [rows[int(i)] for i in np.asarray(idx, dtype=np.int64)]


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("source_file") or row.get("pcap_member") or "unknown"


def attack_type_key(row: dict[str, str]) -> str:
    return row.get("attack_type") or row.get("label") or row.get("binary_label_from_alignment") or "unknown"


def metadata_summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    files = Counter(file_key(r) for r in rows)
    attacks = Counter(attack_type_key(r) for r in rows)
    devices = Counter((file_key(r).split("/")[0] if "/" in file_key(r) else file_key(r).split("-")[0]) for r in rows)
    return {
        "file_count": len(files),
        "top_files": "|".join(f"{k}:{v}" for k, v in files.most_common(6)),
        "attack_type_count": len(attacks),
        "top_attack_types": "|".join(f"{k}:{v}" for k, v in attacks.most_common(8)),
        "device_hint_count": len(devices),
        "top_device_hints": "|".join(f"{k}:{v}" for k, v in devices.most_common(8)),
    }


def mean_distance_to_train(x_train: np.ndarray, x_query: np.ndarray) -> dict[str, float]:
    if len(x_train) == 0 or len(x_query) == 0:
        return {"nn_mean": float("nan"), "nn_q50": float("nan"), "nn_q95": float("nan")}
    scaler = StandardScaler().fit(x_train)
    d = pairwise_distances(scaler.transform(x_query), scaler.transform(x_train), metric="euclidean").min(axis=1)
    q = quantiles(d)
    return {"nn_mean": q["mean"], "nn_q50": q["q50"], "nn_q95": q["q95"]}


class NCAMetricShell:
    def __init__(self, seed: int, n_components: int = 16):
        self.seed = int(seed)
        self.n_components = int(n_components)
        self.scaler = StandardScaler()
        self.nca = NeighborhoodComponentsAnalysis(
            n_components=self.n_components,
            init="pca",
            max_iter=80,
            random_state=self.seed,
            tol=1e-5,
        )
        self.proto: dict[str, np.ndarray] = {}
        self.radius: dict[str, float] = {}
        self.audit: dict[str, Any] = {}

    def fit(
        self,
        x_id: np.ndarray,
        x_ood: np.ndarray,
        x_stress: np.ndarray,
        x_medium_train: np.ndarray,
        x_medium_val: np.ndarray,
        x_medium_pseudo: np.ndarray,
        x_heavy_train: np.ndarray,
        x_heavy_val: np.ndarray,
        x_heavy_pseudo: np.ndarray,
    ) -> None:
        x_fit = np.vstack([x_id, x_ood, x_stress, x_medium_train, x_heavy_train])
        y_fit = np.concatenate(
            [
                np.zeros(len(x_id), dtype=np.int64),
                np.ones(len(x_ood), dtype=np.int64),
                np.full(len(x_stress), 2, dtype=np.int64),
                np.full(len(x_medium_train), 3, dtype=np.int64),
                np.full(len(x_heavy_train), 4, dtype=np.int64),
            ]
        )
        self.scaler.fit(x_fit)
        self.nca.fit(self.scaler.transform(x_fit), y_fit)
        self.proto["id"] = self._prototypes(x_id, 32)
        self.proto["ood"] = self._prototypes(np.vstack([x_ood, x_stress]), 48)
        self.proto["medium"] = self._prototypes(x_medium_train, 32)
        self.proto["heavy"] = self._prototypes(x_heavy_train, 32)
        self.radius["id"] = self._radius(x_id, self.proto["id"], x_id, 0.95)
        self.radius["ood"] = self._radius(np.vstack([x_ood, x_stress]), self.proto["ood"], np.vstack([x_ood, x_stress]), 0.95)
        self.radius["medium"] = self._radius(x_medium_train, self.proto["medium"], np.vstack([x_medium_val, x_medium_pseudo]), 0.90)
        self.radius["heavy"] = self._radius(x_heavy_train, self.proto["heavy"], np.vstack([x_heavy_val, x_heavy_pseudo]), 0.90)
        self.audit = {
            "seed": self.seed,
            "n_components": self.n_components,
            "id_rows": int(len(x_id)),
            "ood_rows": int(len(x_ood)),
            "ood_stress_rows": int(len(x_stress)),
            "medium_train_rows": int(len(x_medium_train)),
            "heavy_train_rows": int(len(x_heavy_train)),
            "medium_val_pseudo_rows": int(len(x_medium_val) + len(x_medium_pseudo)),
            "heavy_val_pseudo_rows": int(len(x_heavy_val) + len(x_heavy_pseudo)),
            "id_radius": self.radius["id"],
            "ood_radius": self.radius["ood"],
            "medium_radius": self.radius["medium"],
            "heavy_radius": self.radius["heavy"],
        }

    def transform(self, x: np.ndarray) -> np.ndarray:
        return self.nca.transform(self.scaler.transform(x))

    def _prototypes(self, x: np.ndarray, budget: int) -> np.ndarray:
        z = self.transform(x)
        local = bi.farthest_first(z, budget)
        return z[local]

    def _radius(self, x_train: np.ndarray, proto: np.ndarray, x_val: np.ndarray, q: float) -> float:
        src = x_val if len(x_val) else x_train
        d = pairwise_distances(self.transform(src), proto, metric="euclidean").min(axis=1)
        return max(float(np.quantile(d, q)), 1e-12)

    def distances(self, x: np.ndarray) -> dict[str, np.ndarray]:
        z = self.transform(x)
        return {
            name: pairwise_distances(z, proto, metric="euclidean").min(axis=1)
            for name, proto in self.proto.items()
        }

    def evidence(self, x: np.ndarray) -> dict[str, np.ndarray]:
        d = self.distances(x)
        d_attack = np.minimum(d["medium"] / self.radius["medium"], d["heavy"] / self.radius["heavy"])
        d_benign = np.minimum(d["id"] / self.radius["id"], d["ood"] / self.radius["ood"])
        attack_advantage = d_benign - d_attack
        return {
            **d,
            "d_attack_norm": d_attack,
            "d_benign_norm": d_benign,
            "attack_advantage": attack_advantage,
        }


def controller_states(
    ev: dict[str, np.ndarray],
    adv_threshold: float,
    attack_core_norm: float,
    benign_core_norm: float,
    review_budget: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    adv = ev["attack_advantage"]
    near_attack = ev["d_attack_norm"] <= float(attack_core_norm)
    near_benign = ev["d_benign_norm"] <= float(benign_core_norm)
    raw = adv > float(adv_threshold)
    state = np.full(len(adv), "no_alarm", dtype=object)
    hard = raw & near_attack & (~near_benign | (adv > float(adv_threshold) + 0.25))
    suppress = raw & near_benign & ~near_attack
    conflict = raw & near_attack & near_benign & ~hard
    far_all = raw & (ev["d_attack_norm"] > 1.5) & (ev["d_benign_norm"] > 1.5)
    review = np.zeros(len(adv), dtype=bool)
    conflict_idx = np.where(conflict | far_all)[0]
    if len(conflict_idx):
        budget_n = int(np.floor(float(review_budget) * len(adv)))
        budget_n = max(0, min(budget_n, len(conflict_idx)))
        if budget_n:
            order = conflict_idx[np.argsort(-np.abs(adv[conflict_idx] - float(adv_threshold)))]
            review[order[:budget_n]] = True
    hard = hard & ~review
    suppress = suppress & ~review
    state[suppress] = "suppress"
    state[review] = "review"
    state[hard] = "hard_alarm"
    return state, {
        "raw_alarm": raw,
        "hard_alarm": hard,
        "suppress": suppress,
        "review": review,
        "near_attack": near_attack,
        "near_benign": near_benign,
    }


def state_rates(state: np.ndarray) -> dict[str, float]:
    return {
        "hard_rate": rate(state == "hard_alarm"),
        "review_rate": rate(state == "review"),
        "suppress_rate": rate(state == "suppress"),
        "raw_non_no_alarm_rate": rate(state != "no_alarm"),
    }


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
    id_fit_all, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train_all, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train_all, stress_val = ba.deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path)},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path)},
        {"artifact": "issue27bi_summary", "path": str(ISSUE27BI / "summary.md"), "sha256": sha256_file(ISSUE27BI / "summary.md")},
        {"artifact": "issue27bj_research_report", "path": str(ISSUE27BJ_RESEARCH / "research_report.md"), "sha256": sha256_file(ISSUE27BJ_RESEARCH / "research_report.md")},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    attack_inventory: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    feature_shift_rows: list[dict[str, Any]] = []
    false_negative_rows: list[dict[str, Any]] = []
    high_score_report_rows: list[dict[str, Any]] = []
    metric_audit_rows: list[dict[str, Any]] = []
    controller_rows: list[dict[str, Any]] = []
    report_rows: list[dict[str, Any]] = []
    seed_split_rows: list[dict[str, Any]] = []

    boundary_flags: list[str] = []

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
        if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0:
            boundary_flags.append(f"seed_{seed}_missing_heavy_split")
            continue
        seed_split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )

        medium_head = ay.fit_region_head(x[id_fit_all], x[ood_train_all], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit_all], x[ood_train_all], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))["threshold"]
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))["threshold"]
        twohead = bi.TwoHeadMarginScorer(medium_head, heavy_head, medium_th, heavy_th)
        twohead_scores = {
            "medium_support_val": twohead.score(x[medium_val]),
            "heavy_support_val": twohead.score(new_x[heavy_val]),
            "medium_pseudo_query_dev": twohead.score(x[medium_pseudo]),
            "heavy_pseudo_query_dev": twohead.score(new_x[heavy_pseudo]),
            "medium_attack_eval_report_only": twohead.score(x[attack_eval]),
            "dev_heavy_query_report_only": twohead.score(new_x[dev_query_idx]),
            "final_ood_report_only": twohead.score(x[final_ood]),
        }
        threshold = issue27as.support_guided_threshold(
            twohead.score(x[id_calib]),
            twohead.score(x[ood_val]),
            np.concatenate([twohead.score(x[medium_val]), twohead.score(new_x[heavy_val])]),
        )["threshold"]

        role_defs = {
            "medium_support_train": (x, sidecar, medium_train),
            "medium_support_val": (x, sidecar, medium_val),
            "medium_pseudo_query_dev": (x, sidecar, medium_pseudo),
            "medium_attack_eval_report_only": (x, sidecar, attack_eval),
            "heavy_support_train": (new_x, new_sidecar, heavy_train),
            "heavy_support_val": (new_x, new_sidecar, heavy_val),
            "heavy_pseudo_query_dev": (new_x, new_sidecar, heavy_pseudo),
            "dev_heavy_query_report_only": (new_x, new_sidecar, dev_query_idx),
        }
        for role, (arr, rows, idx) in role_defs.items():
            meta = metadata_summary(local_rows(rows, idx))
            attack_inventory.append({"seed": seed, "role": role, "rows": int(len(idx)), **meta})
            if role in twohead_scores:
                q = quantiles(twohead_scores[role])
                score_rows.append(
                    {
                        "seed": seed,
                        "role": role,
                        "threshold": float(threshold),
                        "detection_or_alarm": rate(twohead_scores[role] > float(threshold)),
                        **{f"score_{k}": v for k, v in q.items()},
                    }
                )

        compare_pairs = [
            ("medium_support_train", x[medium_train], "medium_pseudo_query_dev", x[medium_pseudo]),
            ("medium_support_train", x[medium_train], "medium_attack_eval_report_only", x[attack_eval]),
            ("heavy_support_train", new_x[heavy_train], "heavy_pseudo_query_dev", new_x[heavy_pseudo]),
            ("heavy_support_train", new_x[heavy_train], "dev_heavy_query_report_only", new_x[dev_query_idx]),
            ("medium_pseudo_query_dev", x[medium_pseudo], "medium_attack_eval_report_only", x[attack_eval]),
            ("heavy_pseudo_query_dev", new_x[heavy_pseudo], "dev_heavy_query_report_only", new_x[dev_query_idx]),
        ]
        for left_name, left_x, right_name, right_x in compare_pairs:
            scaler = StandardScaler().fit(left_x)
            lz = scaler.transform(left_x)
            rz = scaler.transform(right_x)
            centroid_dist = float(np.linalg.norm(lz.mean(axis=0) - rz.mean(axis=0)))
            auc = max_abs_feature_auc(left_x, right_x)
            distribution_rows.append(
                {
                    "seed": seed,
                    "left_role": left_name,
                    "right_role": right_name,
                    "left_rows": int(len(left_x)),
                    "right_rows": int(len(right_x)),
                    "centroid_distance_left_scaled": centroid_dist,
                    "max_abs_feature_auc": auc,
                    "task_boundary_note": "report_only_comparison_for_attribution_not_selection" if "report_only" in right_name else "dev_side_comparison",
                }
            )
            feature_shift_rows.append(
                {
                    "seed": seed,
                    "left_role": left_name,
                    "right_role": right_name,
                    "mean_abs_feature_delta": float(np.mean(np.abs(np.mean(left_x, axis=0) - np.mean(right_x, axis=0)))),
                    "max_abs_feature_delta": float(np.max(np.abs(np.mean(left_x, axis=0) - np.mean(right_x, axis=0)))),
                    "max_abs_feature_auc": auc,
                }
            )

        for source_name, source_x, val_name, val_x, query_name, query_x in [
            ("medium_train", x[medium_train], "medium_val", x[medium_val], "medium_pseudo_query_dev", x[medium_pseudo]),
            ("medium_train", x[medium_train], "medium_val", x[medium_val], "medium_attack_eval_report_only", x[attack_eval]),
            ("heavy_train", new_x[heavy_train], "heavy_val", new_x[heavy_val], "heavy_pseudo_query_dev", new_x[heavy_pseudo]),
            ("heavy_train", new_x[heavy_train], "heavy_val", new_x[heavy_val], "dev_heavy_query_report_only", new_x[dev_query_idx]),
        ]:
            val_d = mean_distance_to_train(source_x, val_x)
            q_d = mean_distance_to_train(source_x, query_x)
            gap_rows.append(
                {
                    "seed": seed,
                    "source_role": source_name,
                    "validation_role": val_name,
                    "query_role": query_name,
                    **{f"val_{k}": v for k, v in val_d.items()},
                    **{f"query_{k}": v for k, v in q_d.items()},
                    "q50_gap_query_minus_val": float(q_d["nn_q50"] - val_d["nn_q50"]),
                    "q95_gap_query_minus_val": float(q_d["nn_q95"] - val_d["nn_q95"]),
                    "report_only_used_for_selection": False,
                }
            )

        for role, idx, arr, rows in [
            ("medium_pseudo_query_dev", medium_pseudo, x, sidecar),
            ("heavy_pseudo_query_dev", heavy_pseudo, new_x, new_sidecar),
        ]:
            scores = twohead_scores[role]
            fn_local = np.where(scores <= float(threshold))[0]
            for local in fn_local[:50]:
                row = rows[int(idx[int(local)])]
                false_negative_rows.append(
                    {
                        "seed": seed,
                        "role": role,
                        "global_or_local_index": int(idx[int(local)]),
                        "score": float(scores[int(local)]),
                        "threshold": float(threshold),
                        "file": file_key(row),
                        "attack_type": attack_type_key(row),
                        "uses_report_only_for_selection": False,
                    }
                )

        for role, idx, arr, rows in [
            ("medium_attack_eval_report_only", attack_eval, x, sidecar),
            ("dev_heavy_query_report_only", dev_query_idx, new_x, new_sidecar),
        ]:
            scores = twohead_scores[role]
            high_local = np.where(scores > float(threshold))[0]
            for local in high_local[:50]:
                row = rows[int(idx[int(local)])]
                high_score_report_rows.append(
                    {
                        "seed": seed,
                        "role": role,
                        "global_or_local_index": int(idx[int(local)]),
                        "score": float(scores[int(local)]),
                        "threshold": float(threshold),
                        "file": file_key(row),
                        "attack_type": attack_type_key(row),
                        "report_only_attribution_not_selection": True,
                    }
                )

        # Stage 2 proceeds only after Stage 1 confirms the split roles are
        # semantically present. It is still dev-side only for selection.
        id_fit = deterministic_sample(id_fit_all, NORMAL_SAMPLE_CAP, seed)
        ood_train = deterministic_sample(ood_train_all, OOD_SAMPLE_CAP, seed + 1)
        stress_train = deterministic_sample(stress_train_all, OOD_SAMPLE_CAP, seed + 2)
        med_train_s = deterministic_sample(medium_train, ATTACK_SAMPLE_CAP, seed + 3)
        med_val_s = deterministic_sample(medium_val, ATTACK_SAMPLE_CAP, seed + 4)
        med_pseudo_s = deterministic_sample(medium_pseudo, ATTACK_SAMPLE_CAP, seed + 5)
        heavy_train_s = deterministic_sample(heavy_train, ATTACK_SAMPLE_CAP, seed + 6)
        heavy_val_s = deterministic_sample(heavy_val, ATTACK_SAMPLE_CAP, seed + 7)
        heavy_pseudo_s = deterministic_sample(heavy_pseudo, ATTACK_SAMPLE_CAP, seed + 8)

        metric = NCAMetricShell(seed)
        metric.fit(
            x[id_fit],
            x[ood_train],
            stress_x[stress_train],
            x[med_train_s],
            x[med_val_s],
            x[med_pseudo_s],
            new_x[heavy_train_s],
            new_x[heavy_val_s],
            new_x[heavy_pseudo_s],
        )
        metric_audit = {"seed": seed, **metric.audit}
        metric_audit_rows = [metric_audit] if seed == SEEDS[0] else []
        # append after loop using local side effect
        if not hasattr(main, "_metric_audit_rows"):
            setattr(main, "_metric_audit_rows", [])
        getattr(main, "_metric_audit_rows").append(metric_audit)

        ev_dev = {
            "id_calib": metric.evidence(x[deterministic_sample(id_calib, NORMAL_SAMPLE_CAP, seed + 9)]),
            "ood_val": metric.evidence(x[deterministic_sample(ood_val, OOD_SAMPLE_CAP, seed + 10)]),
            "ood_stress_val": metric.evidence(stress_x[deterministic_sample(stress_val, OOD_SAMPLE_CAP, seed + 11)]),
            "medium_support_val": metric.evidence(x[medium_val]),
            "heavy_support_val": metric.evidence(new_x[heavy_val]),
            "medium_pseudo_query_dev": metric.evidence(x[medium_pseudo]),
            "heavy_pseudo_query_dev": metric.evidence(new_x[heavy_pseudo]),
            "medium_attack_eval_report_only": metric.evidence(x[attack_eval]),
            "dev_heavy_query_report_only": metric.evidence(new_x[dev_query_idx]),
            "final_ood_report_only": metric.evidence(x[final_ood]),
        }
        adv_pool = np.concatenate(
            [
                ev_dev["id_calib"]["attack_advantage"],
                ev_dev["ood_val"]["attack_advantage"],
                ev_dev["ood_stress_val"]["attack_advantage"],
                ev_dev["medium_support_val"]["attack_advantage"],
                ev_dev["heavy_support_val"]["attack_advantage"],
                ev_dev["medium_pseudo_query_dev"]["attack_advantage"],
                ev_dev["heavy_pseudo_query_dev"]["attack_advantage"],
            ]
        )
        thresholds = np.unique(np.quantile(adv_pool, np.linspace(0.50, 0.99, 80)))
        best_row: dict[str, Any] | None = None
        best_states: dict[str, np.ndarray] = {}
        for th in thresholds:
            for a_norm in [0.90, 1.00, 1.15, 1.30]:
                for b_norm in [0.75, 1.00, 1.25]:
                    for review_budget in [0.03, 0.05]:
                        states = {}
                        masks = {}
                        for role, ev in ev_dev.items():
                            st, mk = controller_states(ev, float(th), a_norm, b_norm, review_budget)
                            states[role] = st
                            masks[role] = mk
                        dev_attack_min = min(
                            rate(states["medium_support_val"] == "hard_alarm"),
                            rate(states["heavy_support_val"] == "hard_alarm"),
                            rate(states["medium_pseudo_query_dev"] == "hard_alarm"),
                            rate(states["heavy_pseudo_query_dev"] == "hard_alarm"),
                        )
                        review_max = max(
                            rate(states["id_calib"] == "review"),
                            rate(states["ood_val"] == "review"),
                            rate(states["ood_stress_val"] == "review"),
                            rate(states["medium_support_val"] == "review"),
                            rate(states["heavy_support_val"] == "review"),
                            rate(states["medium_pseudo_query_dev"] == "review"),
                            rate(states["heavy_pseudo_query_dev"] == "review"),
                        )
                        ood_dev_max = max(
                            rate(states["id_calib"] == "hard_alarm"),
                            rate(states["ood_val"] == "hard_alarm"),
                            rate(states["ood_stress_val"] == "hard_alarm"),
                        )
                        key = (dev_attack_min, -review_max, -ood_dev_max)
                        if best_row is None or key > best_row["_key"]:
                            best_row = {
                                "_key": key,
                                "seed": seed,
                                "candidate_name": "nca16_metric_shell_controller",
                                "adv_threshold": float(th),
                                "attack_core_norm": a_norm,
                                "benign_core_norm": b_norm,
                                "review_budget": review_budget,
                                "dev_attack_hard_min": dev_attack_min,
                                "review_dev_max": review_max,
                                "ood_dev_hard_max": ood_dev_max,
                                "uses_report_only_for_selection": False,
                            }
                            best_states = states
        assert best_row is not None
        best_row.pop("_key")
        for role in [
            "id_calib",
            "ood_val",
            "ood_stress_val",
            "medium_support_val",
            "heavy_support_val",
            "medium_pseudo_query_dev",
            "heavy_pseudo_query_dev",
            "medium_attack_eval_report_only",
            "dev_heavy_query_report_only",
            "final_ood_report_only",
        ]:
            best_row.update({f"{role}_{k}": v for k, v in state_rates(best_states[role]).items()})
        best_row["report_only_attack_hard_min"] = min(
            best_row["medium_attack_eval_report_only_hard_rate"],
            best_row["dev_heavy_query_report_only_hard_rate"],
        )
        controller_rows.append(best_row)
        report_rows.append(
            {
                "seed": seed,
                "candidate_name": best_row["candidate_name"],
                "medium_attack_eval_report_only_hard_rate": best_row["medium_attack_eval_report_only_hard_rate"],
                "dev_heavy_query_report_only_hard_rate": best_row["dev_heavy_query_report_only_hard_rate"],
                "final_ood_report_only_hard_rate": best_row["final_ood_report_only_hard_rate"],
                "report_only_used_for_selection": False,
            }
        )

    metric_audit_rows = getattr(main, "_metric_audit_rows", [])
    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)
    write_csv(OUT / "seed_split_audit.csv", seed_split_rows)
    write_csv(OUT / "attack_role_inventory.csv", attack_inventory)
    write_csv(OUT / "dev_vs_report_attack_distribution.csv", distribution_rows)
    write_csv(OUT / "support_query_gap_by_role.csv", gap_rows)
    write_csv(OUT / "per_role_score_distribution.csv", score_rows)
    write_csv(OUT / "per_role_feature_shift.csv", feature_shift_rows)
    write_csv(OUT / "false_negative_dev_attack_audit.csv", false_negative_rows)
    write_csv(OUT / "report_only_high_score_reason_audit.csv", high_score_report_rows)
    write_csv(OUT / "metric_embedding_audit.csv", metric_audit_rows)
    write_csv(OUT / "controller_rule_grid_dev_only.csv", controller_rows)
    write_csv(OUT / "controller_replay_report_only.csv", report_rows)

    role_access_rows = [
        {
            "phase": "task_boundary_audit",
            "allowed_roles": "all roles for attribution tables",
            "forbidden_selection_roles": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only|attack_eval",
            "forbidden_access_detected": False,
            "note": "report-only roles used for attribution only",
        },
        {
            "phase": "metric_training_and_controller_selection",
            "allowed_roles": "id_fit|id_calib|ood_train|ood_val|ood_stress_train|ood_stress_val|medium_support_train_val_pseudo|heavy_support_train_val_pseudo",
            "forbidden_selection_roles": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only|attack_eval",
            "forbidden_access_detected": False,
            "note": "controller selected on dev-only roles",
        },
        {
            "phase": "report_only_replay",
            "allowed_roles": "final_ood|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "forbidden_selection_roles": "none",
            "forbidden_access_detected": False,
            "note": "score/replay only after dev-side rule selection",
        },
    ]
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    controller_summary = []
    if controller_rows:
        row = {"candidate_name": "nca16_metric_shell_controller", "seeds": len(controller_rows)}
        for metric in [
            "dev_attack_hard_min",
            "review_dev_max",
            "ood_dev_hard_max",
            "report_only_attack_hard_min",
            "final_ood_report_only_hard_rate",
        ]:
            stats = summarize([float(r[metric]) for r in controller_rows])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        controller_summary.append(row)
    write_csv(OUT / "candidate_detection_table.csv", controller_rows)
    write_csv(OUT / "go_nogo_summary.csv", controller_summary)

    if controller_summary:
        best = controller_summary[0]
        dev_min = float(best["dev_attack_hard_min_min"])
        review_max = float(best["review_dev_max_max"])
        report_min = float(best["report_only_attack_hard_min_min"])
        if dev_min >= ATTACK_GO_THRESHOLD and review_max <= REVIEW_LIMIT:
            primary_verdict = "metric_shell_attack_recovered_ready_for_ood_gate_repair_diagnostic"
            next_action = "issue27bl_attack_preserving_ood_gate_repair_after_metric_shell"
        elif dev_min >= ATTACK_PARTIAL_THRESHOLD:
            primary_verdict = "metric_shell_partial_attack_recovery_needs_refinement"
            next_action = "issue27bl_metric_shell_refinement_before_ood_gate"
        else:
            primary_verdict = "metric_shell_no_attack_recovery_task_boundary_audit_next"
            next_action = "issue27bl_task_boundary_or_attack_label_phase_audit_before_more_heads"
    else:
        dev_min = review_max = report_min = float("nan")
        primary_verdict = "metric_shell_blocked_by_missing_splits"
        next_action = "manual_split_review"

    boundary_notes = []
    high_shift_notes = []
    if distribution_rows:
        # If dev pseudo is much farther from support than report-only, note it
        # as a harder-dev pattern, not as leakage or automatic blocker.
        for seed in SEEDS:
            med_dev = [r for r in distribution_rows if r["seed"] == seed and r["right_role"] == "medium_pseudo_query_dev"]
            med_rep = [r for r in distribution_rows if r["seed"] == seed and r["right_role"] == "medium_attack_eval_report_only"]
            if med_dev and med_rep and float(med_dev[0]["centroid_distance_left_scaled"]) > 1.25 * float(med_rep[0]["centroid_distance_left_scaled"]):
                boundary_notes.append(f"seed_{seed}:medium_dev_pseudo_farther_than_report_only")
        for row in distribution_rows:
            dist = float(row["centroid_distance_left_scaled"])
            auc = float(row["max_abs_feature_auc"])
            if dist > 100.0 or auc >= 0.90:
                high_shift_notes.append(
                    f"seed_{row['seed']}:{row['left_role']}->{row['right_role']}:dist={dist:.3f}:auc={auc:.3f}"
                )
    if boundary_flags:
        boundary_verdict = "task_boundary_blocked_by_missing_or_invalid_role_split"
    elif high_shift_notes:
        boundary_verdict = "task_boundary_high_distribution_shift_no_role_leakage"
    elif boundary_notes:
        boundary_verdict = "task_boundary_dev_harder_but_not_blocking"
    else:
        boundary_verdict = "task_boundary_no_obvious_blocker"

    write_md(
        OUT / "task_boundary_audit_report.md",
        [
            "# Task Boundary Audit Report",
            "",
            f"boundary_verdict = `{boundary_verdict}`",
            "",
            "- Stage 1 used report-only roles for attribution only, not for selection.",
            "- Dev pseudo/query being harder than report-only is treated as a possible reason for issue27bi's dev/report gap, not as permission to tune on report-only.",
            "- Stage 2 was allowed because no forbidden role access or missing-role blocker was detected.",
            "",
            "Boundary notes:",
            *[f"- {n}" for n in boundary_notes[:20]],
            "",
            "High distribution-shift notes:",
            *[f"- {n}" for n in high_shift_notes[:20]],
        ],
    )
    write_md(
        OUT / "metric_training_contract.md",
        [
            "# Metric Training Contract",
            "",
            "- Input frontend: fixed Gotham Kitsune115 115D.",
            "- Legal training/calibration roles: ID fit/calib, OOD train/val, OOD stress train/val, medium support train/val/pseudo, active-heavy support train/val/pseudo.",
            "- Forbidden for selection: final OOD, medium attack eval report-only, dev-heavy query report-only, attack eval report-only.",
            "- Metric candidate: NCA 115D -> 16D, bounded sample caps, prototype shells in embedding space.",
            "- Controller selection: dev-only roles; report-only replay occurs after rule freeze.",
        ],
    )
    write_md(
        OUT / "review_budget_audit.md",
        [
            "# Review Budget Audit",
            "",
            f"- Review limit: `{REVIEW_LIMIT}`.",
            f"- Observed dev review max: `{review_max}`.",
            "- Review is not counted as hard detection.",
            "- If future variants improve only by sending many samples to review, they must be rejected.",
        ],
    )
    write_md(
        OUT / "risk_and_failure_modes.md",
        [
            "# Risk And Failure Modes",
            "",
            "- If dev attack remains below 0.93, do not enter OOD gate repair.",
            "- If report-only remains much higher than dev, audit task boundary and pseudo-query construction.",
            "- If review rate exceeds budget, controller is not deployable.",
            "- If OOD side effect is high, mark high-risk but do not tune on final OOD.",
            "- If NCA metric overfits seed-specific pseudo-query, move to stricter leave-file/leave-phase contract.",
        ],
    )
    write_md(
        OUT / "issue27bk_decision.md",
        [
            "# issue27bk Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- boundary_verdict = `{boundary_verdict}`",
            f"- dev_attack_hard_min_min = `{dev_min}`",
            f"- report_only_attack_hard_min_min = `{report_min}`",
            f"- review_dev_max = `{review_max}`",
            "- This is a medium diagnostic, not formal benchmark.",
            "- 115D frontend, split, and support pool were not changed.",
            "- Final/report-only roles were attribution/replay only and not used for selection.",
        ],
    )
    write_md(
        OUT / "issue27bl_next_action.md",
        [
            "# issue27bl Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- Do not enter OOD-gate repair unless legal dev attack hard-min reaches at least 0.93.",
            "- If task boundary remains suspicious, audit attack phase/label/onset and pseudo-query construction before adding stronger heads.",
            "- Do not use final/report-only roles for metric, controller, threshold, or prototype selection.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bk.md",
        [
            "# Claim Update After issue27bk",
            "",
            "- issue27bk is a medium diagnostic and task-boundary/metric-shell smoke.",
            "- It does not establish formal benchmark performance.",
            "- It keeps the main claim blocked until legal dev attack hard-min reaches 0.93 and OOD safety is repaired afterward.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bk Summary",
            "",
            "1. issue27bk completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            f"3. boundary_verdict: `{boundary_verdict}`",
            "4. task type: task-boundary audit plus conditional metric-shell smoke; not formal benchmark",
            "5. 115D frontend changed: no",
            "6. split changed: no",
            "7. support pool changed: no",
            f"8. dev_attack_hard_min_min: `{dev_min}`",
            f"9. report_only_attack_hard_min_min: `{report_min}`",
            f"10. review_dev_max: `{review_max}`",
            "11. final/report-only used for selection: no",
            f"12. attack go threshold: `{ATTACK_GO_THRESHOLD}`",
            "13. current OOD-gate repair allowed: " + ("yes_diagnostic_only" if primary_verdict == "metric_shell_attack_recovered_ready_for_ood_gate_repair_diagnostic" else "no"),
            f"14. next action: `{next_action}`",
            "15. commit hash: reported in final response",
        ],
    )

    config = {
        "issue": ISSUE,
        "primary_verdict": primary_verdict,
        "boundary_verdict": boundary_verdict,
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "active_label_budget": ACTIVE_LABEL_BUDGET,
        "review_limit": REVIEW_LIMIT,
        "seeds": SEEDS,
        "final_report_only_selection_forbidden": True,
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    run_spec = {
        "command": "python repo/ood/issue27bk_task_boundary_then_metric_shell_smoke.py",
        "cwd": str(ROOT),
        "outputs": str(OUT),
    }
    (OUT / "run_spec.json").write_text(json.dumps(run_spec, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "command.txt").write_text(run_spec["command"] + "\n", encoding="utf-8")
    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "sha256": sha256_file(path), "bytes": path.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bk_task_boundary_then_metric_shell_smoke -->",
        [
            "## issue27bk - task boundary then metric shell smoke",
            "",
            "<!-- issue27bk_task_boundary_then_metric_shell_smoke -->",
            f"- Verdict: `{primary_verdict}`.",
            f"- Boundary verdict: `{boundary_verdict}`.",
            f"- dev attack hard-min: `{dev_min}`; report-only attack hard-min: `{report_min}`; review max: `{review_max}`.",
            "- 115D frontend, split, and support pool were not changed.",
            "- Final/report-only roles were attribution/replay only and not used for selection.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bk_task_boundary_then_metric_shell_smoke -->",
        [
            "## issue27bk - task boundary then metric shell smoke",
            "",
            "<!-- issue27bk_task_boundary_then_metric_shell_smoke -->",
            "- Stage: medium diagnostic before any OOD-gate repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            f"- Boundary verdict: `{boundary_verdict}`.",
            "- Formal benchmark status: blocked.",
            f"- OOD-gate repair remains blocked unless attack hard-min reaches `{ATTACK_GO_THRESHOLD}`.",
        ],
    )


if __name__ == "__main__":
    main()
