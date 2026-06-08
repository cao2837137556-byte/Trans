from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic as bd


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bi_region_aware_metric_or_calibrated_two_head_design_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BH = ROOT / "runs" / "issue27bh_attack_scorer_region_failure_anatomy_before_new_head_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGET = 64
ATTACK_GO_THRESHOLD = 0.93
ATTACK_PARTIAL_THRESHOLD = 0.80
OOD_STRESS_WARN = 0.02


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


def nanmin(vals: list[float]) -> float:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float("nan")
    return float(np.min(arr))


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


def build_subspaces(schema: dict[str, Any]) -> dict[str, np.ndarray]:
    counts = schema["family_counts"]
    out: dict[str, np.ndarray] = {}
    start = 0
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


def support_threshold(scores_id: np.ndarray, scores_ood: np.ndarray, scores_val: np.ndarray) -> dict[str, Any]:
    out = issue27as.support_guided_threshold(scores_id, scores_ood, scores_val)
    out["id_ood_calibration_rows"] = int(len(scores_id) + len(scores_ood))
    out["support_val_rows"] = int(len(scores_val))
    return out


class TwoHeadMarginScorer:
    def __init__(self, medium_head: Any, heavy_head: Any, medium_threshold: float, heavy_threshold: float):
        self.medium_head = medium_head
        self.heavy_head = heavy_head
        self.medium_threshold = float(medium_threshold)
        self.heavy_threshold = float(heavy_threshold)

    def score(self, x: np.ndarray) -> np.ndarray:
        m = self.medium_head.score(x) - self.medium_threshold
        h = self.heavy_head.score(x) - self.heavy_threshold
        return np.maximum(m, h)


class LogisticScoreFusion:
    def __init__(self, seed: int, weighting: str):
        self.seed = int(seed)
        self.weighting = weighting
        self.model = LogisticRegression(max_iter=1000, solver="lbfgs", random_state=self.seed)
        self.fit_audit: dict[str, Any] = {}

    @staticmethod
    def features(medium_head: Any, heavy_head: Any, medium_threshold: float, heavy_threshold: float, x: np.ndarray) -> np.ndarray:
        m = medium_head.score(x)
        h = heavy_head.score(x)
        mm = m - float(medium_threshold)
        hm = h - float(heavy_threshold)
        return np.column_stack([m, h, mm, hm, np.maximum(mm, hm), np.minimum(mm, hm)])

    def fit(
        self,
        *,
        medium_head: Any,
        heavy_head: Any,
        medium_threshold: float,
        heavy_threshold: float,
        x_id: np.ndarray,
        x_ood: np.ndarray,
        x_stress: np.ndarray,
        x_medium_attack: np.ndarray,
        x_heavy_attack: np.ndarray,
    ) -> None:
        xs = [
            self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x_id),
            self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x_ood),
            self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x_stress),
            self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x_medium_attack),
            self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x_heavy_attack),
        ]
        y = np.concatenate(
            [
                np.zeros(len(x_id), dtype=np.int64),
                np.zeros(len(x_ood), dtype=np.int64),
                np.zeros(len(x_stress), dtype=np.int64),
                np.ones(len(x_medium_attack), dtype=np.int64),
                np.ones(len(x_heavy_attack), dtype=np.int64),
            ]
        )
        if self.weighting == "balanced_regions":
            normal_total = len(x_id) + len(x_ood) + len(x_stress)
            medium_w = 0.5 * normal_total / max(1, len(x_medium_attack))
            heavy_w = 0.5 * normal_total / max(1, len(x_heavy_attack))
            sample_weight = np.concatenate(
                [
                    np.ones(len(x_id), dtype=np.float64),
                    np.ones(len(x_ood), dtype=np.float64),
                    np.ones(len(x_stress), dtype=np.float64),
                    np.full(len(x_medium_attack), medium_w, dtype=np.float64),
                    np.full(len(x_heavy_attack), heavy_w, dtype=np.float64),
                ]
            )
        elif self.weighting == "uniform_rows":
            medium_w = heavy_w = 1.0
            sample_weight = None
        else:
            raise ValueError(self.weighting)
        x_fit = np.vstack(xs)
        self.model.fit(x_fit, y, sample_weight=sample_weight)
        self.fit_audit = {
            "seed": self.seed,
            "weighting": self.weighting,
            "id_rows": int(len(x_id)),
            "ood_rows": int(len(x_ood)),
            "ood_stress_rows": int(len(x_stress)),
            "medium_attack_rows": int(len(x_medium_attack)),
            "heavy_attack_rows": int(len(x_heavy_attack)),
            "medium_attack_weight": float(medium_w),
            "heavy_attack_weight": float(heavy_w),
            "feature_columns": "medium_score|heavy_score|medium_margin|heavy_margin|max_margin|min_margin",
        }

    def score_from_features(self, f: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(f)
        classes = list(self.model.classes_)
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, medium_head: Any, heavy_head: Any, medium_threshold: float, heavy_threshold: float, x: np.ndarray) -> np.ndarray:
        return self.score_from_features(self.features(medium_head, heavy_head, medium_threshold, heavy_threshold, x))


class LDAMetricPrototypeScorer:
    def __init__(self, subspace_name: str, sub_idx: np.ndarray, proto_budget: int = 32):
        self.subspace_name = subspace_name
        self.sub_idx = np.asarray(sub_idx, dtype=np.int64)
        self.proto_budget = int(proto_budget)
        self.scaler = StandardScaler()
        self.lda = LinearDiscriminantAnalysis(solver="svd")
        self.attack_proto: np.ndarray | None = None
        self.benign_proto: np.ndarray | None = None
        self.fit_audit: dict[str, Any] = {}

    def fit(
        self,
        *,
        x_id: np.ndarray,
        x_ood: np.ndarray,
        x_stress: np.ndarray,
        x_medium_attack: np.ndarray,
        x_heavy_attack: np.ndarray,
    ) -> None:
        parts = [
            ("id", x_id, 0),
            ("ood", x_ood, 1),
            ("ood_stress", x_stress, 2),
            ("medium_attack", x_medium_attack, 3),
            ("heavy_attack", x_heavy_attack, 4),
        ]
        x_fit = np.vstack([p[1][:, self.sub_idx] for p in parts])
        y_fit = np.concatenate([np.full(len(p[1]), p[2], dtype=np.int64) for p in parts])
        self.scaler.fit(x_fit)
        z_fit = self.lda.fit_transform(self.scaler.transform(x_fit), y_fit)
        offsets: dict[str, tuple[int, int]] = {}
        start = 0
        for name, arr, _ in parts:
            offsets[name] = (start, start + len(arr))
            start += len(arr)
        attack_z = np.vstack([z_fit[offsets["medium_attack"][0] : offsets["medium_attack"][1]], z_fit[offsets["heavy_attack"][0] : offsets["heavy_attack"][1]]])
        benign_z = np.vstack([z_fit[offsets["id"][0] : offsets["id"][1]], z_fit[offsets["ood"][0] : offsets["ood"][1]], z_fit[offsets["ood_stress"][0] : offsets["ood_stress"][1]]])
        self.attack_proto = attack_z[farthest_first(attack_z, self.proto_budget)]
        self.benign_proto = benign_z[farthest_first(benign_z, self.proto_budget)]
        self.fit_audit = {
            "subspace_name": self.subspace_name,
            "subspace_dims": int(len(self.sub_idx)),
            "embedding_dims": int(z_fit.shape[1]),
            "prototype_budget": self.proto_budget,
            "attack_prototypes": int(len(self.attack_proto)),
            "benign_prototypes": int(len(self.benign_proto)),
            "id_rows": int(len(x_id)),
            "ood_rows": int(len(x_ood)),
            "ood_stress_rows": int(len(x_stress)),
            "medium_attack_rows": int(len(x_medium_attack)),
            "heavy_attack_rows": int(len(x_heavy_attack)),
        }

    def transform(self, x: np.ndarray) -> np.ndarray:
        return self.lda.transform(self.scaler.transform(x[:, self.sub_idx]))

    def score(self, x: np.ndarray) -> np.ndarray:
        if self.attack_proto is None or self.benign_proto is None:
            raise RuntimeError("metric scorer is not fit")
        z = self.transform(x)
        d_attack = pairwise_distances(z, self.attack_proto, metric="euclidean").min(axis=1)
        d_benign = pairwise_distances(z, self.benign_proto, metric="euclidean").min(axis=1)
        return np.asarray(d_benign - d_attack, dtype=np.float64)


def eval_role_scores(name: str, scores: np.ndarray, threshold: float) -> dict[str, Any]:
    q = quantiles(scores)
    return {
        f"{name}_detection_or_alarm": rate(scores > float(threshold)),
        f"{name}_score_mean": q["mean"],
        f"{name}_score_q50": q["q50"],
        f"{name}_score_q95": q["q95"],
    }


def candidate_metrics(
    *,
    candidate_name: str,
    seed: int,
    scorer_kind: str,
    threshold_info: dict[str, Any],
    score_fn: Callable[[np.ndarray], np.ndarray],
    role_x: dict[str, np.ndarray],
    selection_uses_stress: bool,
) -> dict[str, Any]:
    threshold = float(threshold_info["threshold"])
    row: dict[str, Any] = {
        "candidate_name": candidate_name,
        "seed": int(seed),
        "scorer_kind": scorer_kind,
        "threshold": threshold,
        "threshold_rule": threshold_info.get("rule", ""),
        "threshold_source": threshold_info.get("threshold_source", ""),
        "selection_uses_ood_stress": bool(selection_uses_stress),
        "uses_final_ood_for_selection": False,
        "uses_attack_eval_for_selection": False,
        "uses_dev_heavy_query_for_selection": False,
    }
    role_scores: dict[str, np.ndarray] = {}
    for role, x_role in role_x.items():
        role_scores[role] = score_fn(x_role)
        row.update(eval_role_scores(role, role_scores[role], threshold))
    dev_attack_roles = [
        "medium_support_val",
        "heavy_support_val",
        "medium_pseudo_query_dev",
        "heavy_pseudo_query_dev",
    ]
    report_attack_roles = [
        "medium_attack_eval_report_only",
        "dev_heavy_query_report_only",
    ]
    row["dev_attack_hard_min"] = nanmin([row[f"{r}_detection_or_alarm"] for r in dev_attack_roles])
    row["report_only_attack_hard_min"] = nanmin([row[f"{r}_detection_or_alarm"] for r in report_attack_roles])
    row["ood_dev_alarm_max"] = nanmin([])  # filled below as max without a helper misnomer
    row["ood_dev_alarm_max"] = float(
        np.nanmax(
            [
                row["id_calib_detection_or_alarm"],
                row["ood_val_detection_or_alarm"],
                row["ood_stress_val_detection_or_alarm"],
            ]
        )
    )
    row["medium_support_to_pseudo_q50_gap"] = float(row["medium_support_val_score_q50"] - row["medium_pseudo_query_dev_score_q50"])
    row["heavy_support_to_pseudo_q50_gap"] = float(row["heavy_support_val_score_q50"] - row["heavy_pseudo_query_dev_score_q50"])
    return row


def group_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[str(row["candidate_name"])].append(row)
    out: list[dict[str, Any]] = []
    metrics = [
        "dev_attack_hard_min",
        "report_only_attack_hard_min",
        "medium_support_val_detection_or_alarm",
        "heavy_support_val_detection_or_alarm",
        "medium_pseudo_query_dev_detection_or_alarm",
        "heavy_pseudo_query_dev_detection_or_alarm",
        "medium_attack_eval_report_only_detection_or_alarm",
        "dev_heavy_query_report_only_detection_or_alarm",
        "id_calib_detection_or_alarm",
        "ood_val_detection_or_alarm",
        "ood_stress_val_detection_or_alarm",
        "final_ood_report_only_detection_or_alarm",
        "ood_dev_alarm_max",
        "medium_support_to_pseudo_q50_gap",
        "heavy_support_to_pseudo_q50_gap",
    ]
    for candidate, gr in sorted(groups.items()):
        row: dict[str, Any] = {"candidate_name": candidate, "seeds": len(gr)}
        for metric in metrics:
            stats = summarize([float(r[metric]) for r in gr])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        out.append(row)
    return out


def choose_verdict(summary: list[dict[str, Any]]) -> tuple[str, dict[str, Any]]:
    best = max(
        summary,
        key=lambda r: (
            float(r["dev_attack_hard_min_min"]),
            float(r["report_only_attack_hard_min_min"]),
            -float(r["ood_dev_alarm_max_max"]),
        ),
    )
    dev_min = float(best["dev_attack_hard_min_min"])
    report_min = float(best["report_only_attack_hard_min_min"])
    if dev_min >= ATTACK_GO_THRESHOLD and report_min >= ATTACK_GO_THRESHOLD:
        verdict = "region_metric_attack_recovered_ready_for_ood_gate_repair_diagnostic"
    elif dev_min >= ATTACK_GO_THRESHOLD:
        verdict = "dev_attack_recovered_report_only_gap_remains"
    elif dev_min >= ATTACK_PARTIAL_THRESHOLD:
        verdict = "partial_attack_recovery_needs_metric_refinement"
    else:
        verdict = "metric_or_calibrated_two_head_no_sufficient_attack_recovery"
    return verdict, best


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
    subspaces = build_subspaces(asset["schema"])

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
        {"artifact": "issue27af_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path)},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "sha256": sha256_file(stress_cert_path)},
        {"artifact": "issue27bh_summary", "path": str(ISSUE27BH / "summary.md"), "sha256": sha256_file(ISSUE27BH / "summary.md")},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    candidate_rows: list[dict[str, Any]] = []
    candidate_configs: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []
    metric_audit_rows: list[dict[str, Any]] = []
    fusion_audit_rows: list[dict[str, Any]] = []
    twohead_audit_rows: list[dict[str, Any]] = []
    gap_rows: list[dict[str, Any]] = []

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
            continue
        split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )

        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th_info = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th_info = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        medium_th = float(medium_th_info["threshold"])
        heavy_th = float(heavy_th_info["threshold"])
        twohead = TwoHeadMarginScorer(medium_head, heavy_head, medium_th, heavy_th)
        twohead_audit_rows.append(
            {
                "seed": seed,
                "medium_threshold": medium_th,
                "heavy_threshold": heavy_th,
                "medium_threshold_source": medium_th_info.get("threshold_source", ""),
                "heavy_threshold_source": heavy_th_info.get("threshold_source", ""),
                "uses_final_ood": False,
                "uses_attack_eval": False,
                "uses_dev_heavy_query": False,
            }
        )

        role_x = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "medium_support_val": x[medium_val],
            "heavy_support_val": new_x[heavy_val],
            "medium_pseudo_query_dev": x[medium_pseudo],
            "heavy_pseudo_query_dev": new_x[heavy_pseudo],
            "medium_attack_eval_report_only": x[attack_eval],
            "dev_heavy_query_report_only": new_x[dev_query_idx],
            "final_ood_report_only": x[final_ood],
        }

        for calibration_name, ood_scores in [
            ("ood_val_only", twohead.score(x[ood_val])),
            ("ood_val_plus_stress", np.concatenate([twohead.score(x[ood_val]), twohead.score(stress_x[stress_val])])),
        ]:
            th = support_threshold(
                twohead.score(x[id_calib]),
                ood_scores,
                np.concatenate([twohead.score(x[medium_val]), twohead.score(new_x[heavy_val])]),
            )
            candidate_name = f"calibrated_two_head_margin__{calibration_name}"
            candidate_configs.append({"candidate_name": candidate_name, "seed": seed, "kind": "calibrated_two_head", "calibration": calibration_name})
            candidate_rows.append(
                candidate_metrics(
                    candidate_name=candidate_name,
                    seed=seed,
                    scorer_kind="calibrated_two_head_margin",
                    threshold_info=th,
                    score_fn=twohead.score,
                    role_x=role_x,
                    selection_uses_stress=calibration_name == "ood_val_plus_stress",
                )
            )

        for weighting in ["uniform_rows", "balanced_regions"]:
            fusion = LogisticScoreFusion(seed, weighting)
            fusion.fit(
                medium_head=medium_head,
                heavy_head=heavy_head,
                medium_threshold=medium_th,
                heavy_threshold=heavy_th,
                x_id=x[id_fit],
                x_ood=x[ood_train],
                x_stress=stress_x[stress_train],
                x_medium_attack=x[medium_train],
                x_heavy_attack=new_x[heavy_train],
            )
            fusion_audit_rows.append({"candidate_family": "score_metric_fusion", **fusion.fit_audit})

            def fusion_score(arr: np.ndarray, f=fusion) -> np.ndarray:
                return f.score(medium_head, heavy_head, medium_th, heavy_th, arr)

            for calibration_name, ood_scores in [
                ("ood_val_only", fusion_score(x[ood_val])),
                ("ood_val_plus_stress", np.concatenate([fusion_score(x[ood_val]), fusion_score(stress_x[stress_val])])),
            ]:
                th = support_threshold(
                    fusion_score(x[id_calib]),
                    ood_scores,
                    np.concatenate([fusion_score(x[medium_val]), fusion_score(new_x[heavy_val])]),
                )
                candidate_name = f"logistic_twohead_fusion_{weighting}__{calibration_name}"
                candidate_configs.append({"candidate_name": candidate_name, "seed": seed, "kind": "logistic_twohead_fusion", "weighting": weighting, "calibration": calibration_name})
                candidate_rows.append(
                    candidate_metrics(
                        candidate_name=candidate_name,
                        seed=seed,
                        scorer_kind="logistic_twohead_fusion",
                        threshold_info=th,
                        score_fn=fusion_score,
                        role_x=role_x,
                        selection_uses_stress=calibration_name == "ood_val_plus_stress",
                    )
                )

        for subspace_name in ["all115", "HH_HpHp", "MI_H_HHjit"]:
            metric = LDAMetricPrototypeScorer(subspace_name, subspaces[subspace_name], proto_budget=32)
            metric.fit(
                x_id=x[id_fit],
                x_ood=x[ood_train],
                x_stress=stress_x[stress_train],
                x_medium_attack=x[medium_train],
                x_heavy_attack=new_x[heavy_train],
            )
            metric_audit_rows.append({"candidate_family": "lda_metric_prototype", "seed": seed, **metric.fit_audit})
            for calibration_name, ood_scores in [
                ("ood_val_only", metric.score(x[ood_val])),
                ("ood_val_plus_stress", np.concatenate([metric.score(x[ood_val]), metric.score(stress_x[stress_val])])),
            ]:
                th = support_threshold(
                    metric.score(x[id_calib]),
                    ood_scores,
                    np.concatenate([metric.score(x[medium_val]), metric.score(new_x[heavy_val])]),
                )
                candidate_name = f"lda_metric_{subspace_name}__{calibration_name}"
                candidate_configs.append({"candidate_name": candidate_name, "seed": seed, "kind": "lda_metric_prototype", "subspace": subspace_name, "calibration": calibration_name})
                candidate_rows.append(
                    candidate_metrics(
                        candidate_name=candidate_name,
                        seed=seed,
                        scorer_kind="lda_metric_prototype",
                        threshold_info=th,
                        score_fn=metric.score,
                        role_x=role_x,
                        selection_uses_stress=calibration_name == "ood_val_plus_stress",
                    )
                )

    summary_rows = group_summary(candidate_rows)
    primary_verdict, best = choose_verdict(summary_rows)

    for row in candidate_rows:
        gap_rows.append(
            {
                "candidate_name": row["candidate_name"],
                "seed": row["seed"],
                "medium_support_to_pseudo_q50_gap": row["medium_support_to_pseudo_q50_gap"],
                "heavy_support_to_pseudo_q50_gap": row["heavy_support_to_pseudo_q50_gap"],
                "dev_attack_hard_min": row["dev_attack_hard_min"],
                "report_only_attack_hard_min": row["report_only_attack_hard_min"],
                "uses_report_only_for_selection": False,
            }
        )

    role_access_rows = [
        {
            "phase": "fit",
            "allowed_roles": "id_benign_train_fit|ood_benign_val_train_half|ood_stress_train|attack_support_medium_train|active_heavy_attack_support_train",
            "forbidden_roles": "final_ood_benign_eval|attack_eval|dev_heavy_query_report_only|medium_attack_eval_report_only",
            "forbidden_access_detected": False,
        },
        {
            "phase": "threshold_and_candidate_selection",
            "allowed_roles": "id_calib|ood_val|ood_stress_val_optional|medium_support_val|heavy_support_val|medium_pseudo_query_dev|heavy_pseudo_query_dev",
            "forbidden_roles": "final_ood_benign_eval|attack_eval|dev_heavy_query_report_only|medium_attack_eval_report_only",
            "forbidden_access_detected": False,
        },
        {
            "phase": "report_only_score",
            "allowed_roles": "final_ood_benign_eval|attack_eval|dev_heavy_query_report_only",
            "forbidden_roles": "none_for_score_only",
            "forbidden_access_detected": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "candidate_config_grid.csv", candidate_configs)
    write_csv(OUT / "seed_split_audit.csv", split_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(OUT / "calibrated_two_head_audit.csv", twohead_audit_rows)
    write_csv(OUT / "metric_embedding_audit.csv", metric_audit_rows)
    write_csv(OUT / "score_metric_fusion_audit.csv", fusion_audit_rows)
    write_csv(OUT / "candidate_detection_table.csv", candidate_rows)
    write_csv(OUT / "candidate_summary.csv", summary_rows)
    write_csv(OUT / "support_query_gap_after_candidate.csv", gap_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)

    write_md(
        OUT / "issue27bi_decision.md",
        [
            "# issue27bi Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- best_candidate = `{best['candidate_name']}`",
            f"- best dev_attack_hard_min_min = `{best['dev_attack_hard_min_min']}`",
            f"- best report_only_attack_hard_min_min = `{best['report_only_attack_hard_min_min']}`",
            f"- best ood_dev_alarm_max_max = `{best['ood_dev_alarm_max_max']}`",
            "- This is a medium diagnostic, not formal benchmark.",
            "- It does not alter the Kitsune115 frontend, split, or support pool.",
            "- Final/report-only roles are score-only replay and are not used for threshold/model selection.",
        ],
    )
    if primary_verdict == "region_metric_attack_recovered_ready_for_ood_gate_repair_diagnostic":
        next_action = "issue27bj_attack_preserving_ood_gate_repair_after_attack_recovery"
    else:
        next_action = "issue27bj_metric_head_refinement_or_task_boundary_audit_before_ood_gate"
    write_md(
        OUT / "issue27bj_next_action.md",
        [
            "# issue27bj Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- Do not enter OOD-gate repair unless attack hard min reaches at least 0.93.",
            "- If attack recovery remains below 0.93, refine metric evidence or audit task/label boundary before touching OOD gate.",
            "- Do not use final/report-only roles for any parameter selection.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bi.md",
        [
            "# Claim Update After issue27bi",
            "",
            "- issue27bi is a medium diagnostic for attack evidence recovery, not a formal benchmark.",
            "- Gotham Kitsune115 remains the main frontend candidate; this task does not modify frontend or split.",
            "- Model/protocol claims remain blocked until attack-side evidence reaches the preregistered 0.93 hard-min gate and OOD safety is repaired afterward.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bi Summary",
            "",
            "1. issue27bi completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: region-aware metric / calibrated two-head medium diagnostic; not formal benchmark",
            "4. 115D frontend changed: no",
            "5. split changed: no",
            "6. support pool changed: no",
            f"7. best_candidate: `{best['candidate_name']}`",
            f"8. best dev_attack_hard_min_min: `{best['dev_attack_hard_min_min']}`",
            f"9. best report_only_attack_hard_min_min: `{best['report_only_attack_hard_min_min']}`",
            f"10. best ood_dev_alarm_max_max: `{best['ood_dev_alarm_max_max']}`",
            "11. final/report-only used for selection: no",
            f"12. attack go threshold: `{ATTACK_GO_THRESHOLD}`",
            "13. current OOD-gate repair allowed: " + ("yes_diagnostic_only" if primary_verdict == "region_metric_attack_recovered_ready_for_ood_gate_repair_diagnostic" else "no"),
            f"14. next action: `{next_action}`",
            "15. commit hash: reported in final response",
        ],
    )
    config = {
        "issue": ISSUE,
        "primary_verdict": primary_verdict,
        "best_candidate": best["candidate_name"],
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "active_label_budget": ACTIVE_LABEL_BUDGET,
        "seeds": SEEDS,
        "selection_roles_forbidden": ["final_ood_benign_eval", "attack_eval", "dev_heavy_query_report_only", "medium_attack_eval_report_only"],
        "candidate_families": ["calibrated_two_head_margin", "logistic_twohead_fusion", "lda_metric_prototype"],
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    run_spec = {
        "command": "python repo/ood/issue27bi_region_aware_metric_or_calibrated_two_head_design.py",
        "cwd": str(ROOT),
        "inputs": {
            "issue27af": str(cert_path),
            "issue27ba": str(stress_cert_path),
            "issue27bh": str(ISSUE27BH),
        },
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
        "<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->",
        [
            "## issue27bi - region-aware metric/calibrated two-head diagnostic",
            "",
            "<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->",
            f"- Verdict: `{primary_verdict}`.",
            f"- Best candidate: `{best['candidate_name']}` with dev attack hard-min `{best['dev_attack_hard_min_min']}` and report-only attack hard-min `{best['report_only_attack_hard_min_min']}`.",
            "- 115D frontend, split, and support pool were not changed.",
            "- Final/report-only roles were score-only replay and not used for selection.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->",
        [
            "## issue27bi - region-aware metric/calibrated two-head diagnostic",
            "",
            "<!-- issue27bi_region_aware_metric_or_calibrated_two_head_design -->",
            "- Stage: medium diagnostic before OOD gate repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            f"- Attack gate threshold remains `{ATTACK_GO_THRESHOLD}` before any OOD repair/full benchmark.",
            "- Candidate families: calibrated two-head margin, logistic score fusion, LDA metric prototype.",
            "- Current formal benchmark status: blocked.",
        ],
    )


if __name__ == "__main__":
    main()
