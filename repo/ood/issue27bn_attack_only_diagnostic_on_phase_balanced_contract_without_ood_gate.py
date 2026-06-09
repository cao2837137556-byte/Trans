from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate_2026-06-09"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BM = ROOT / "runs" / "issue27bm_phase_balanced_attack_contract_design_without_report_only_leakage_2026-06-08"

PRIMARY_STRATEGY = "reset_at_split_boundary"
PRIMARY_CONTRACT = "phase_balanced_dev_v2"
SEEDS = [42, 43, 44, 45, 46]
ATTACK_GO_THRESHOLD = 0.93
SUPPORT_RECALL_TARGETS = [0.90, 0.93, 0.95]


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


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


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


def rate(scores: np.ndarray, threshold: float) -> float:
    return float(np.mean(np.asarray(scores) > float(threshold))) if len(scores) else float("nan")


def qstats(scores: np.ndarray) -> dict[str, float]:
    scores = np.asarray(scores, dtype=np.float64)
    if scores.size == 0:
        return {k: float("nan") for k in ["min", "p10", "p50", "p90", "p95", "p99", "max", "mean", "std"]}
    return {
        "min": float(np.min(scores)),
        "p10": float(np.quantile(scores, 0.10)),
        "p50": float(np.quantile(scores, 0.50)),
        "p90": float(np.quantile(scores, 0.90)),
        "p95": float(np.quantile(scores, 0.95)),
        "p99": float(np.quantile(scores, 0.99)),
        "max": float(np.max(scores)),
        "mean": float(np.mean(scores)),
        "std": float(np.std(scores)),
    }


def parse_global_id(global_id: str) -> tuple[str, int]:
    source, idx = global_id.rsplit(":", 1)
    return source, int(idx)


def hash_indices(indices: list[str]) -> str:
    return hashlib.sha256(",".join(indices).encode("utf-8")).hexdigest()


def load_contract_role(role_file: str) -> list[dict[str, str]]:
    rows = [r for r in read_csv(ISSUE27BM / role_file) if r.get("contract_id") == PRIMARY_CONTRACT]
    if not rows:
        raise RuntimeError(f"missing {PRIMARY_CONTRACT} rows in {role_file}")
    return rows


def contract_features(rows: list[dict[str, str]], medium_x: np.ndarray, heavy_x: np.ndarray) -> np.ndarray:
    feats = []
    for row in rows:
        source, idx = parse_global_id(row["global_id"])
        if source.startswith("medium_"):
            feats.append(medium_x[idx])
        elif source.startswith("heavy_"):
            feats.append(heavy_x[idx])
        else:
            raise RuntimeError(f"unknown contract source: {source}")
    return np.asarray(feats, dtype=np.float32)


class AttackHistGB:
    def __init__(self, seed: int, fit_mode: str, ood_weight: float, support_weight: float):
        self.seed = int(seed)
        self.fit_mode = fit_mode
        self.ood_weight = float(ood_weight)
        self.support_weight = float(support_weight)
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

    def fit(self, x_id: np.ndarray, x_ood: np.ndarray, x_support: np.ndarray) -> None:
        if self.fit_mode == "id_support_only":
            x_train = np.vstack([x_id, x_support])
            y_train = np.concatenate([np.zeros(len(x_id), dtype=np.int64), np.ones(len(x_support), dtype=np.int64)])
            sample_weight = np.concatenate(
                [
                    np.ones(len(x_id), dtype=np.float64),
                    np.full(len(x_support), self.support_weight, dtype=np.float64),
                ]
            )
            ood_rows = 0
        elif self.fit_mode == "id_ood_support":
            x_train = np.vstack([x_id, x_ood, x_support])
            y_train = np.concatenate(
                [
                    np.zeros(len(x_id), dtype=np.int64),
                    np.zeros(len(x_ood), dtype=np.int64),
                    np.ones(len(x_support), dtype=np.int64),
                ]
            )
            sample_weight = np.concatenate(
                [
                    np.ones(len(x_id), dtype=np.float64),
                    np.full(len(x_ood), self.ood_weight, dtype=np.float64),
                    np.full(len(x_support), self.support_weight, dtype=np.float64),
                ]
            )
            ood_rows = len(x_ood)
        else:
            raise ValueError(self.fit_mode)

        self.fit_shape = {
            "id_rows": int(len(x_id)),
            "ood_train_rows": int(ood_rows),
            "support_train_rows": int(len(x_support)),
            "total_rows": int(len(x_train)),
            "id_weight": 1.0,
            "ood_weight": self.ood_weight if ood_rows else 0.0,
            "support_weight": self.support_weight,
            "weighted_normal_to_attack_ratio": float(
                (len(x_id) + ood_rows * self.ood_weight) / max(1.0, len(x_support) * self.support_weight)
            ),
        }
        self.model.fit(x_train, y_train, sample_weight=sample_weight)
        self._fix_direction(x_id, x_ood if len(x_ood) else x_id[:0], x_support)

    def raw_score(self, x: np.ndarray) -> np.ndarray:
        proba = self.model.predict_proba(x)
        classes = list(self.model.classes_)
        if 1 not in classes:
            raise RuntimeError(f"missing attack class: {classes}")
        return np.asarray(proba[:, classes.index(1)], dtype=np.float64)

    def score(self, x: np.ndarray) -> np.ndarray:
        return self.score_direction * self.raw_score(x)

    def _fix_direction(self, x_id: np.ndarray, x_ood: np.ndarray, x_support: np.ndarray) -> None:
        raw_id = self.raw_score(x_id)
        raw_support = self.raw_score(x_support)
        raw_ood = self.raw_score(x_ood) if len(x_ood) else np.asarray([], dtype=np.float64)
        benign_mean = float(np.mean(raw_id)) if not len(raw_ood) else max(float(np.mean(raw_id)), float(np.mean(raw_ood)))
        if float(np.mean(raw_support)) < benign_mean:
            self.score_direction = -1.0
            self.score_direction_fixed = True
        self.direction_check = {
            "id_raw_mean": float(np.mean(raw_id)),
            "ood_raw_mean": float(np.mean(raw_ood)) if len(raw_ood) else float("nan"),
            "support_raw_mean": float(np.mean(raw_support)),
            "id_score_mean": float(np.mean(self.score(x_id))),
            "ood_score_mean": float(np.mean(self.score(x_ood))) if len(x_ood) else float("nan"),
            "support_score_mean": float(np.mean(self.score(x_support))),
            "score_direction": self.score_direction,
            "score_direction_fixed": self.score_direction_fixed,
        }


def support_recall_threshold(scores_support_val: np.ndarray, target: float) -> dict[str, Any]:
    scores = np.asarray(scores_support_val, dtype=np.float64)
    if scores.size == 0:
        return {"threshold": float("nan"), "threshold_rule": f"support_val_recall_{target:g}", "selection_feasible": False}
    q = max(0.0, min(1.0, 1.0 - float(target)))
    thr = float(np.quantile(scores, q))
    return {
        "threshold": thr,
        "threshold_rule": f"support_val_recall_{target:g}",
        "threshold_source": "support_val_attack_scores_only",
        "support_recall_target": float(target),
        "selection_feasible": True,
        "uses_ood_gate": False,
    }


def id_only_threshold(scores_id_calib: np.ndarray, target_alarm: float = 0.01) -> dict[str, Any]:
    scores = np.asarray(scores_id_calib, dtype=np.float64)
    if scores.size == 0:
        return {"threshold": float("nan"), "threshold_rule": "id_calib_1pct", "selection_feasible": False}
    thr = float(np.quantile(scores, 1.0 - target_alarm))
    return {
        "threshold": thr,
        "threshold_rule": f"id_calib_alarm_{target_alarm:g}",
        "threshold_source": "id_calib_only_no_ood_gate",
        "support_recall_target": float("nan"),
        "selection_feasible": True,
        "uses_ood_gate": False,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    x = asset["X"]
    sidecar = asset["sidecar"]

    support_train_rows = load_contract_role("phase_balanced_support_train_indices.csv")
    support_val_rows = load_contract_role("phase_balanced_support_val_indices.csv")
    pseudo_rows = load_contract_role("phase_balanced_pseudo_query_dev_indices.csv")
    x_support_train = contract_features(support_train_rows, x, new_x)
    x_support_val = contract_features(support_val_rows, x, new_x)
    x_pseudo = contract_features(pseudo_rows, x, new_x)

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood_idx = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    attack_eval_idx = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    _, dev_heavy_query_idx, _ = issue27au.split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "used_for": "asset_hash_audit"},
        {"artifact": "issue27bm_contract_json", "path": str(ISSUE27BM / "phase_balanced_contract_v2.json"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_contract_v2.json"), "used_for": "contract_definition"},
        {"artifact": "issue27bm_support_train_indices", "path": str(ISSUE27BM / "phase_balanced_support_train_indices.csv"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_support_train_indices.csv"), "used_for": "fit_attack_support"},
        {"artifact": "issue27bm_support_val_indices", "path": str(ISSUE27BM / "phase_balanced_support_val_indices.csv"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_support_val_indices.csv"), "used_for": "threshold_attack_support_val"},
        {"artifact": "issue27bm_pseudo_query_indices", "path": str(ISSUE27BM / "phase_balanced_pseudo_query_dev_indices.csv"), "sha256": sha256_file(ISSUE27BM / "phase_balanced_pseudo_query_dev_indices.csv"), "used_for": "dev_attack_diagnostic_only"},
    ]
    for check in checks + new_checks:
        input_hash_rows.append(
            {
                "artifact": check.get("artifact", "asset_check"),
                "path": check.get("path", ""),
                "sha256": check.get("actual_sha256", ""),
                "expected_sha256": check.get("expected_sha256", ""),
                "hash_match": check.get("hash_match", ""),
                "used_for": "input_asset_validation",
            }
        )

    fit_specs = [
        {"fit_mode": "id_ood_support", "ood_weight": 4.0, "support_weight": 4.0, "fit_label": "old_weighted_id_ood_support_w4"},
        {"fit_mode": "id_ood_support", "ood_weight": 4.0, "support_weight": 16.0, "fit_label": "support_emphasis_id_ood_support_w16"},
        {"fit_mode": "id_support_only", "ood_weight": 0.0, "support_weight": 4.0, "fit_label": "id_support_only_w4"},
        {"fit_mode": "id_support_only", "ood_weight": 0.0, "support_weight": 16.0, "fit_label": "id_support_only_w16"},
    ]

    result_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    score_rows: list[dict[str, Any]] = []
    fit_rows: list[dict[str, Any]] = []
    direction_rows: list[dict[str, Any]] = []

    role_arrays: dict[str, np.ndarray] = {
        "id_calib": x[id_calib],
        "ood_val_reported_not_gate": x[ood_val],
        "support_train": x_support_train,
        "support_val": x_support_val,
        "pseudo_query_dev": x_pseudo,
        "medium_attack_eval_report_only": x[attack_eval_idx],
        "dev_heavy_query_report_only": new_x[dev_heavy_query_idx],
        "final_ood_benign_eval_report_only": x[final_ood_idx],
    }

    for spec in fit_specs:
        for seed in SEEDS:
            model = AttackHistGB(seed, spec["fit_mode"], spec["ood_weight"], spec["support_weight"])
            model.fit(x[id_fit], x[ood_train], x_support_train)
            fit_row = {"seed": seed, **spec, **model.fit_shape}
            fit_rows.append(fit_row)
            direction_rows.append({"seed": seed, **spec, **model.direction_check})
            scores = {role: model.score(arr) for role, arr in role_arrays.items()}
            for role, arr in scores.items():
                row = {"seed": seed, **spec, "role": role, "n": int(len(arr))}
                row.update(qstats(arr))
                score_rows.append(row)
            threshold_specs = [support_recall_threshold(scores["support_val"], t) for t in SUPPORT_RECALL_TARGETS]
            threshold_specs.append(id_only_threshold(scores["id_calib"], 0.01))
            for th in threshold_specs:
                threshold = float(th["threshold"])
                threshold_row = {
                    "seed": seed,
                    **spec,
                    **th,
                    "id_calib_alarm_at_threshold": rate(scores["id_calib"], threshold),
                    "ood_val_alarm_at_threshold_reported_not_gate": rate(scores["ood_val_reported_not_gate"], threshold),
                    "support_val_detection_at_threshold": rate(scores["support_val"], threshold),
                    "pseudo_query_dev_detection_at_threshold": rate(scores["pseudo_query_dev"], threshold),
                }
                threshold_rows.append(threshold_row)
                for role, arr in scores.items():
                    is_report_only = role in {
                        "medium_attack_eval_report_only",
                        "dev_heavy_query_report_only",
                        "final_ood_benign_eval_report_only",
                    }
                    result_rows.append(
                        {
                            "seed": seed,
                            **spec,
                            "threshold_rule": th["threshold_rule"],
                            "threshold_source": th.get("threshold_source", ""),
                            "uses_ood_gate": False,
                            "score_role": role,
                            "n": int(len(arr)),
                            "alarm_or_detection_rate": rate(arr, threshold),
                            "is_report_only": is_report_only,
                            "used_for_selection": False,
                            "threshold": threshold,
                        }
                    )

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in result_rows:
        key = (row["fit_label"], row["threshold_rule"], row["score_role"])
        grouped.setdefault(key, []).append(row)
    summary_rows: list[dict[str, Any]] = []
    for (fit_label, threshold_rule, role), rows in sorted(grouped.items()):
        vals = np.asarray([float(r["alarm_or_detection_rate"]) for r in rows], dtype=np.float64)
        summary_rows.append(
            {
                "fit_label": fit_label,
                "threshold_rule": threshold_rule,
                "score_role": role,
                "mean_rate": float(np.mean(vals)),
                "min_rate": float(np.min(vals)),
                "max_rate": float(np.max(vals)),
                "std_rate": float(np.std(vals)),
                "n_seeds": len(vals),
                "is_report_only": rows[0]["is_report_only"],
            }
        )

    dev_candidates: list[dict[str, Any]] = []
    for fit_label in sorted(set(r["fit_label"] for r in result_rows)):
        for threshold_rule in sorted(set(r["threshold_rule"] for r in result_rows)):
            support_val = next(
                (r for r in summary_rows if r["fit_label"] == fit_label and r["threshold_rule"] == threshold_rule and r["score_role"] == "support_val"),
                None,
            )
            pseudo = next(
                (r for r in summary_rows if r["fit_label"] == fit_label and r["threshold_rule"] == threshold_rule and r["score_role"] == "pseudo_query_dev"),
                None,
            )
            if support_val and pseudo:
                dev_candidates.append(
                    {
                        "fit_label": fit_label,
                        "threshold_rule": threshold_rule,
                        "support_val_min": support_val["min_rate"],
                        "pseudo_query_dev_min": pseudo["min_rate"],
                        "dev_attack_min": min(float(support_val["min_rate"]), float(pseudo["min_rate"])),
                        "passes_attack_go_0p93_on_dev": min(float(support_val["min_rate"]), float(pseudo["min_rate"])) >= ATTACK_GO_THRESHOLD,
                    }
                )
    best_dev = max(dev_candidates, key=lambda r: (float(r["dev_attack_min"]), float(r["pseudo_query_dev_min"]))) if dev_candidates else {}
    dev_pass = bool(best_dev and best_dev["passes_attack_go_0p93_on_dev"])

    report_medium = next(
        (
            r
            for r in summary_rows
            if best_dev and r["fit_label"] == best_dev["fit_label"] and r["threshold_rule"] == best_dev["threshold_rule"] and r["score_role"] == "medium_attack_eval_report_only"
        ),
        None,
    )
    report_heavy = next(
        (
            r
            for r in summary_rows
            if best_dev and r["fit_label"] == best_dev["fit_label"] and r["threshold_rule"] == best_dev["threshold_rule"] and r["score_role"] == "dev_heavy_query_report_only"
        ),
        None,
    )
    report_attack_min = (
        min(float(report_medium["min_rate"]), float(report_heavy["min_rate"])) if report_medium and report_heavy else float("nan")
    )

    if dev_pass and report_attack_min >= ATTACK_GO_THRESHOLD:
        primary_verdict = "phase_balanced_attack_diagnostic_recovers_dev_and_report_only_attack"
        next_action = "issue27bo_ood_gate_repair_after_attack_contract_recovery"
    elif dev_pass:
        primary_verdict = "phase_balanced_attack_diagnostic_recovers_dev_but_report_only_gap_remains"
        next_action = "issue27bo_task_boundary_for_report_only_attack_or_expand_legal_dev_pool"
    else:
        primary_verdict = "phase_balanced_attack_diagnostic_still_insufficient"
        next_action = "issue27bo_task_boundary_or_model_head_rethink_before_ood_gate"

    role_access_rows = [
        {
            "stage": "fit",
            "allowed_roles": "id_fit_from_id_benign_train|ood_train_from_ood_benign_val_when_fit_mode_allows|phase_balanced_support_train",
            "forbidden_roles": "phase_balanced_pseudo_query_dev|attack_eval|dev_heavy_query|final_ood",
            "uses_attack_eval_for_fit_threshold_selection": False,
            "uses_dev_heavy_query_for_fit_threshold_selection": False,
            "uses_final_ood_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "threshold",
            "allowed_roles": "support_val|id_calib",
            "forbidden_roles": "pseudo_query_dev|attack_eval|dev_heavy_query|final_ood|ood_val_for_gate_repair",
            "uses_attack_eval_for_fit_threshold_selection": False,
            "uses_dev_heavy_query_for_fit_threshold_selection": False,
            "uses_final_ood_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "diagnostic_scoring",
            "allowed_roles": "pseudo_query_dev|report_only_roles_for_replay_only",
            "forbidden_roles": "using_report_only_to_choose_candidate_or_threshold",
            "uses_attack_eval_for_fit_threshold_selection": False,
            "uses_dev_heavy_query_for_fit_threshold_selection": False,
            "uses_final_ood_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
        {
            "stage": "dev_candidate_ranking",
            "allowed_roles": "support_val|pseudo_query_dev",
            "forbidden_roles": "attack_eval|dev_heavy_query|final_ood",
            "uses_attack_eval_for_fit_threshold_selection": False,
            "uses_dev_heavy_query_for_fit_threshold_selection": False,
            "uses_final_ood_for_fit_threshold_selection": False,
            "forbidden_role_access": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "fit_class_balance_audit.csv", fit_rows)
    write_csv(OUT / "score_direction_audit.csv", direction_rows)
    write_csv(OUT / "attack_only_threshold_audit.csv", threshold_rows)
    write_csv(OUT / "attack_only_diagnostic_by_seed.csv", result_rows)
    write_csv(OUT / "attack_only_summary_by_candidate.csv", summary_rows)
    write_csv(OUT / "dev_candidate_selection_audit.csv", dev_candidates)
    write_csv(OUT / "score_distribution_audit.csv", score_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    report_only_rows = [
        {
            "fit_label": best_dev.get("fit_label", ""),
            "threshold_rule": best_dev.get("threshold_rule", ""),
            "medium_attack_eval_report_only_min": report_medium["min_rate"] if report_medium else "",
            "dev_heavy_query_report_only_min": report_heavy["min_rate"] if report_heavy else "",
            "report_only_attack_min": report_attack_min,
            "used_for_selection": False,
        }
    ]
    write_csv(OUT / "report_only_replay_audit.csv", report_only_rows)

    write_md(
        OUT / "issue27bn_decision.md",
        [
            "# issue27bn Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- best_dev_fit_label: `{best_dev.get('fit_label', 'NA')}`",
            f"- best_dev_threshold_rule: `{best_dev.get('threshold_rule', 'NA')}`",
            f"- best_dev_attack_min: `{best_dev.get('dev_attack_min', 'NA')}`",
            f"- support_val_min: `{best_dev.get('support_val_min', 'NA')}`",
            f"- pseudo_query_dev_min: `{best_dev.get('pseudo_query_dev_min', 'NA')}`",
            f"- report_only_attack_min_under_best_dev: `{report_attack_min}`",
            "- OOD gate repair run: no",
            "- Final/report-only roles used for selection: no",
        ],
    )

    write_md(
        OUT / "issue27bo_next_action.md",
        [
            "# issue27bo Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If dev attack is recovered but report-only remains weak, do not tune on report-only; inspect task boundary or expand legal development-side attack phases.",
            "- If dev attack is not recovered, do not enter OOD-gate repair; revisit model head/representation only after confirming contract semantics.",
            "- OOD-gate repair remains blocked unless legal dev attack hard-min reaches `0.93` and the report-only replay does not show an obvious task-boundary break.",
        ],
    )

    write_md(
        OUT / "claim_update_after_issue27bn.md",
        [
            "# Claim Update After issue27bn",
            "",
            "- issue27bn is an attack-only diagnostic on a frozen phase-balanced development contract.",
            "- It does not constitute a formal benchmark or model ranking.",
            "- Report-only roles remain sealed; any report-only replay is attribution only.",
            "- OOD false-alarm repair remains a later stage and is not addressed here.",
        ],
    )

    write_md(
        OUT / "summary.md",
        [
            "# issue27bn Summary",
            "",
            "1. issue27bn completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: attack-only diagnostic on frozen phase-balanced contract",
            "4. OOD gate repair run: no",
            "5. 115D frontend changed: no",
            "6. split changed: no",
            "7. final/report-only roles used for fit/threshold/selection: no",
            "7a. pseudo_query_dev used for dev-only candidate ranking: yes",
            f"8. best dev candidate: `{best_dev.get('fit_label', 'NA')}` + `{best_dev.get('threshold_rule', 'NA')}`",
            f"9. best dev attack min: `{best_dev.get('dev_attack_min', 'NA')}`",
            f"10. support_val min / pseudo_query_dev min: `{best_dev.get('support_val_min', 'NA')}` / `{best_dev.get('pseudo_query_dev_min', 'NA')}`",
            f"11. report-only attack min under best dev candidate: `{report_attack_min}`",
            f"12. attack go threshold: `{ATTACK_GO_THRESHOLD}`",
            f"13. OOD-gate repair allowed next: `{primary_verdict == 'phase_balanced_attack_diagnostic_recovers_dev_and_report_only_attack'}`",
            f"14. next action: `{next_action}`",
            "15. commit hash: reported in final response",
        ],
    )

    write_md(OUT / "command.txt", ["python repo/ood/issue27bn_attack_only_diagnostic_on_phase_balanced_contract_without_ood_gate.py"])
    with (OUT / "config.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "issue": ISSUE,
                "primary_contract": PRIMARY_CONTRACT,
                "seeds": SEEDS,
                "support_recall_targets": SUPPORT_RECALL_TARGETS,
                "fit_specs": fit_specs,
                "no_ood_gate_repair": True,
                "report_only_selection": False,
            },
            f,
            indent=2,
        )
    with (OUT / "run_spec.json").open("w", encoding="utf-8") as f:
        json.dump(
            {
                "stage": "attack-only diagnostic",
                "formal_benchmark": False,
                "ood_gate_repair": False,
                "fit_roles": ["id_fit", "ood_train_if_fit_mode_allows", "phase_balanced_support_train"],
                "threshold_roles": ["support_val", "id_calib"],
                "dev_diagnostic_roles": ["pseudo_query_dev"],
                "report_only_roles": ["attack_eval", "dev_heavy_query", "final_ood"],
            },
            f,
            indent=2,
        )

    manifest_rows = []
    for path in sorted(OUT.iterdir()):
        if path.is_file():
            manifest_rows.append({"file": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)})
    write_csv(OUT / "manifest.csv", manifest_rows)

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bn_attack_only_diagnostic -->",
        [
            "## issue27bn - attack-only diagnostic on phase-balanced contract",
            "",
            "<!-- issue27bn_attack_only_diagnostic -->",
            f"- Verdict: `{primary_verdict}`.",
            f"- Best dev candidate: `{best_dev.get('fit_label', 'NA')}` + `{best_dev.get('threshold_rule', 'NA')}` with dev attack min `{best_dev.get('dev_attack_min', 'NA')}`.",
            f"- Report-only attack min under best dev candidate: `{report_attack_min}`.",
            "- No OOD-gate repair, no 115D/split changes, and no final/report-only selection.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bn_attack_only_diagnostic -->",
        [
            "## issue27bn - attack-only diagnostic on phase-balanced contract",
            "",
            "<!-- issue27bn_attack_only_diagnostic -->",
            "- Stage: attack-side diagnostic before any OOD-gate repair.",
            f"- Primary verdict: `{primary_verdict}`.",
            "- Formal benchmark status: blocked.",
            "- Report-only roles remained replay-only.",
        ],
    )


if __name__ == "__main__":
    main()
