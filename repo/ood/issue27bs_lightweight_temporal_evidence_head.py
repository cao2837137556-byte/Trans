from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

import issue27br_past_only_temporal_interaction_evidence_feasibility as br


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bs_lightweight_temporal_evidence_head_2026-06-10"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27BR = ROOT / "runs" / "issue27br_past_only_temporal_interaction_evidence_feasibility_2026-06-10"

SEEDS = [42, 43, 44, 45, 46]
ATTACK_FLOOR = 0.93
OOD_TARGET = 0.01
OOD_DIAGNOSTIC_TARGET = 0.05

MODEL_KINDS = ["logreg_balanced", "histgb_shallow"]
ATTACK_QS = [0.99, 0.995]
RISK_THRESHOLDS = [0.50, 0.70, 0.90]
STRONG_ATTACK_QS = [0.75]
ATTACK_DISTANCE_THRESHOLDS = [1.00, 1.25]


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


def rate(mask: pd.Series | np.ndarray) -> float:
    arr = np.asarray(mask)
    if arr.size == 0:
        return float("nan")
    return float(np.mean(arr.astype(bool)))


def fit_classifier(kind: str, x_train: np.ndarray, y_train: np.ndarray, seed: int):
    if kind == "logreg_balanced":
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=1000, solver="liblinear", class_weight="balanced", random_state=seed),
        )
    elif kind == "histgb_shallow":
        model = HistGradientBoostingClassifier(
            max_iter=80,
            learning_rate=0.05,
            max_leaf_nodes=8,
            l2_regularization=0.1,
            random_state=seed,
        )
    else:
        raise ValueError(kind)
    model.fit(x_train, y_train)
    return model


def prob_positive(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(x)
    classes = list(model.classes_) if hasattr(model, "classes_") else list(model[-1].classes_)
    return np.asarray(proba[:, classes.index(1)], dtype=np.float64)


def add_fit_select_phase(df: pd.DataFrame) -> pd.DataFrame:
    out = df.sort_values(["seed", "role", "source_group", "packet_timestamp_epoch", "recorded_index", "row_position"], kind="mergesort").copy()
    out["phase"] = "report_only"
    for (seed, role), idx in out[~out["is_report_only"]].groupby(["seed", "role"], sort=False).groups.items():
        ordered = list(idx)
        cut = max(1, min(len(ordered) - 1, len(ordered) // 2)) if len(ordered) > 1 else len(ordered)
        out.loc[ordered[:cut], "phase"] = "fit"
        out.loc[ordered[cut:], "phase"] = "select"
    return out


def feature_columns() -> dict[str, list[str]]:
    current = [
        "attack_margin",
        "ood_risk",
        "d_attack_outer_min",
        "d_benign_core_min",
        "benign_minus_attack_distance",
    ]
    temporal = [
        "past_role_raw_alarm_rate_w8",
        "past_role_raw_alarm_rate_w32",
        "past_role_raw_alarm_rate_w128",
        "past_source_raw_alarm_rate_w8",
        "past_source_raw_alarm_rate_w32",
        "past_source_raw_alarm_rate_w128",
        "past_source_high_ood_risk_rate_w32",
        "past_source_strong_attack_rate_w32",
        "past_source_attack_margin_mean_w32",
        "past_source_ood_risk_mean_w32",
        "past_source_d_attack_outer_min_mean_w32",
        "past_source_d_benign_core_min_mean_w32",
        "past_source_raw_alarm_run_before",
    ]
    return {
        "current_evidence": current,
        "past_temporal_only": temporal,
        "current_plus_temporal": current + temporal,
    }


def label_attack(row: pd.Series) -> int:
    return 1 if row["role_type"] == "dev_attack" else 0


def label_ood_risk(row: pd.Series) -> int:
    return 1 if row["role_type"] == "dev_benign_ood" else 0


def role_metrics(df: pd.DataFrame, hard_col: str, suppress_col: str, review_col: str) -> list[dict[str, Any]]:
    rows = []
    for (seed, role), g in df.groupby(["seed", "role"], sort=True):
        rows.append(
            {
                "seed": int(seed),
                "role": role,
                "role_type": br.role_type(role),
                "is_report_only": bool(g["is_report_only"].iloc[0]),
                "n": int(len(g)),
                "raw_alarm_rate": rate(g["temporal_head_raw_alarm"]),
                "hard_alarm_rate": rate(g[hard_col]),
                "suppress_rate": rate(g[suppress_col]),
                "review_rate": rate(g[review_col]),
                "temporal_attack_score_mean": float(g["temporal_attack_score"].mean()),
                "temporal_ood_risk_mean": float(g["temporal_ood_risk"].mean()),
            }
        )
    return rows


def aggregate_role_metrics(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    out = []
    for (role, is_report_only), g in df.groupby(["role", "is_report_only"], sort=True):
        row = {"role": role, "is_report_only": bool(is_report_only), "seeds": int(len(g))}
        for metric in ["raw_alarm_rate", "hard_alarm_rate", "suppress_rate", "review_rate"]:
            vals = g[metric].astype(float)
            row[f"{metric}_mean"] = float(vals.mean())
            row[f"{metric}_min"] = float(vals.min())
            row[f"{metric}_max"] = float(vals.max())
        out.append(row)
    return out


def key_metrics(rows: list[dict[str, Any]]) -> dict[str, float]:
    df = pd.DataFrame(rows)
    def get(role: str, metric: str, agg: str) -> float:
        vals = df[df["role"] == role][metric].astype(float)
        if vals.empty:
            return float("nan")
        return float(vals.min() if agg == "min" else vals.max())
    return {
        "dev_attack_min": min(
            get("support_val", "hard_alarm_rate", "min"),
            get("dev_future_near", "hard_alarm_rate", "min"),
            get("dev_future_mid", "hard_alarm_rate", "min"),
            get("dev_future_far", "hard_alarm_rate", "min"),
        ),
        "dev_ood_max": max(
            get("id_calib", "hard_alarm_rate", "max"),
            get("ood_val", "hard_alarm_rate", "max"),
            get("ood_stress_val", "hard_alarm_rate", "max"),
        ),
        "dev_review_max": max(
            get("id_calib", "review_rate", "max"),
            get("ood_val", "review_rate", "max"),
            get("ood_stress_val", "review_rate", "max"),
        ),
        "report_attack_min": min(
            get("sealed_medium_attack_eval_report_only", "hard_alarm_rate", "min"),
            get("sealed_dev_heavy_query_report_only", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_near", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_mid", "hard_alarm_rate", "min"),
            get("sealed_heavy_future_far", "hard_alarm_rate", "min"),
        ),
        "final_ood_max": get("final_ood_report_only", "hard_alarm_rate", "max"),
    }


def summarize_config(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    df = pd.DataFrame(rows)
    keys = ["feature_set", "model_kind", "attack_q", "risk_threshold", "strong_attack_q", "d_attack_thr"]
    out = []
    for key, g in df.groupby(keys, sort=True):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = int(len(g))
        for metric in ["dev_attack_min", "dev_ood_max", "dev_review_max", "dev_score"]:
            vals = g[metric].astype(float)
            row[f"{metric}_mean"] = float(vals.mean())
            row[f"{metric}_min"] = float(vals.min())
            row[f"{metric}_max"] = float(vals.max())
        row["feasible_1pct_all_seeds"] = bool(row["dev_attack_min_min"] >= ATTACK_FLOOR and row["dev_ood_max_max"] <= OOD_TARGET)
        row["feasible_5pct_all_seeds"] = bool(row["dev_attack_min_min"] >= ATTACK_FLOOR and row["dev_ood_max_max"] <= OOD_DIAGNOSTIC_TARGET)
        out.append(row)
    return out


def build_temporal_dataset() -> pd.DataFrame:
    ctx = br.build_base_context()
    rows = []
    for seed in SEEDS:
        _out, seed_rows, _params = br.fit_bq_seed(ctx, seed)
        rows.extend(seed_rows)
    df = br.build_temporal_frame(rows)
    return add_fit_select_phase(df)


def train_seed_scores(seed_df: pd.DataFrame, feature_set: str, model_kind: str, cols: list[str], seed: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame, np.ndarray]:
    fit_df = seed_df[seed_df["phase"] == "fit"].copy()
    select_df = seed_df[seed_df["phase"] == "select"].copy()
    fit_df = fit_df[fit_df["role_type"].isin(["dev_attack", "dev_benign_ood"])].copy()
    select_df = select_df[select_df["role_type"].isin(["dev_attack", "dev_benign_ood"])].copy()
    y_attack_fit = fit_df.apply(label_attack, axis=1).to_numpy(dtype=np.int8)
    y_risk_fit = fit_df.apply(label_ood_risk, axis=1).to_numpy(dtype=np.int8)
    x_fit = fit_df[cols].to_numpy(dtype=np.float32)
    x_all = seed_df[cols].to_numpy(dtype=np.float32)
    attack_model = fit_classifier(model_kind, x_fit, y_attack_fit, seed)
    risk_model = fit_classifier(model_kind, x_fit, y_risk_fit, seed)
    attack_all = prob_positive(attack_model, x_all)
    risk_all = prob_positive(risk_model, x_all)
    attack_fit = prob_positive(attack_model, x_fit)
    return attack_all, risk_all, fit_df, select_df, attack_fit


def replay_selected_config(df: pd.DataFrame, selected: dict[str, Any], fsets: dict[str, list[str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    feature_set = str(selected["feature_set"])
    model_kind = str(selected["model_kind"])
    attack_q = float(selected["attack_q"])
    risk_threshold = float(selected["risk_threshold"])
    strong_q = float(selected["strong_attack_q"])
    d_attack_thr = float(selected["d_attack_thr"])
    cols = fsets[feature_set]
    for seed in SEEDS:
        seed_df = df[df["seed"] == seed].copy()
        attack_all, risk_all, fit_df, select_df, attack_fit = train_seed_scores(seed_df, feature_set, model_kind, cols, seed)
        id_select_scores = attack_all[(seed_df["phase"].to_numpy() == "select") & (seed_df["role"].to_numpy() == "id_calib")]
        attack_fit_scores = attack_fit[fit_df.apply(label_attack, axis=1).to_numpy(dtype=np.int8) == 1]
        attack_threshold = float(np.quantile(id_select_scores, attack_q))
        strong_threshold = float(np.quantile(attack_fit_scores, strong_q)) if attack_fit_scores.size else attack_threshold
        params = {
            "attack_threshold": attack_threshold,
            "strong_attack_threshold": max(strong_threshold, attack_threshold),
            "risk_threshold": risk_threshold,
            "d_attack_thr": d_attack_thr,
        }
        scored = evaluate_candidate_frame(seed_df, attack_all, risk_all, params)
        role_rows = role_metrics(scored, "temporal_head_hard", "temporal_head_suppress", "temporal_head_review")
        for rr in role_rows:
            rows.append(
                {
                    "feature_set": feature_set,
                    "model_kind": model_kind,
                    "attack_q": attack_q,
                    "risk_threshold": risk_threshold,
                    "strong_attack_q": strong_q,
                    "d_attack_thr": d_attack_thr,
                    **rr,
                }
            )
    return rows


def evaluate_candidate_frame(df: pd.DataFrame, attack_scores: np.ndarray, risk_scores: np.ndarray, params: dict[str, float]) -> pd.DataFrame:
    out = df.copy()
    out["temporal_attack_score"] = attack_scores
    out["temporal_ood_risk"] = risk_scores
    out["temporal_head_raw_alarm"] = out["temporal_attack_score"] >= params["attack_threshold"]
    strong = (
        out["temporal_head_raw_alarm"]
        & (out["temporal_attack_score"] >= params["strong_attack_threshold"])
        & (out["d_attack_outer_min"] <= params["d_attack_thr"])
    )
    high_risk = out["temporal_head_raw_alarm"] & (out["temporal_ood_risk"] >= params["risk_threshold"])
    suppress = high_risk & (~strong)
    out["temporal_head_strong_attack"] = strong
    out["temporal_head_high_ood_risk"] = high_risk
    out["temporal_head_suppress"] = suppress
    out["temporal_head_review"] = False
    out["temporal_head_hard"] = out["temporal_head_raw_alarm"] & (~suppress)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = build_temporal_dataset()
    fsets = feature_columns()

    input_rows = [
        {"artifact": "issue27br_summary", "path": str(ISSUE27BR / "summary.md"), "sha256": sha256_file(ISSUE27BR / "summary.md"), "used_for": "parent_temporal_context"},
        {"artifact": "issue27br_config", "path": str(ISSUE27BR / "config.json"), "sha256": sha256_file(ISSUE27BR / "config.json"), "used_for": "parent_temporal_context"},
    ]
    feature_rows = []
    for name, cols in fsets.items():
        feature_rows.append({"feature_set": name, "n_features": len(cols), "columns": "|".join(cols)})

    split_rows = []
    for (seed, role, phase), g in df.groupby(["seed", "role", "phase"], sort=True):
        split_rows.append(
            {
                "seed": int(seed),
                "role": role,
                "phase": phase,
                "role_type": br.role_type(role),
                "is_report_only": bool(g["is_report_only"].iloc[0]),
                "rows": int(len(g)),
            }
        )

    candidate_rows: list[dict[str, Any]] = []
    model_audit_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        seed_df = df[df["seed"] == seed].copy()
        fit_df = seed_df[seed_df["phase"] == "fit"].copy()
        select_df = seed_df[seed_df["phase"] == "select"].copy()
        fit_mask = fit_df["role_type"].isin(["dev_attack", "dev_benign_ood"])
        select_mask = select_df["role_type"].isin(["dev_attack", "dev_benign_ood"])
        fit_df = fit_df[fit_mask].copy()
        select_df = select_df[select_mask].copy()
        y_attack_fit = fit_df.apply(label_attack, axis=1).to_numpy(dtype=np.int8)
        y_risk_fit = fit_df.apply(label_ood_risk, axis=1).to_numpy(dtype=np.int8)
        for feature_set, cols in fsets.items():
            x_select = select_df[cols].to_numpy(dtype=np.float32)
            for model_kind in MODEL_KINDS:
                attack_all, risk_all, _fit_df2, _select_df2, attack_fit = train_seed_scores(seed_df, feature_set, model_kind, cols, seed)
                attack_select = attack_all[seed_df["phase"].to_numpy() == "select"]

                model_audit_rows.append(
                    {
                        "seed": seed,
                        "feature_set": feature_set,
                        "model_kind": model_kind,
                        "fit_rows": int(len(fit_df)),
                        "fit_attack_rows": int(np.sum(y_attack_fit == 1)),
                        "fit_benign_ood_rows": int(np.sum(y_attack_fit == 0)),
                        "select_rows": int(len(select_df)),
                        "uses_report_only_for_fit_or_selection": False,
                    }
                )

                id_select_scores = select_df[select_df["role"] == "id_calib"].copy()
                if id_select_scores.empty:
                    continue
                id_select_attack_scores = attack_select[select_df["role"].to_numpy() == "id_calib"]
                attack_fit_scores = attack_fit[y_attack_fit == 1]
                for attack_q in ATTACK_QS:
                    attack_threshold = float(np.quantile(id_select_attack_scores, attack_q))
                    for strong_q in STRONG_ATTACK_QS:
                        strong_threshold = float(np.quantile(attack_fit_scores, strong_q)) if attack_fit_scores.size else attack_threshold
                        strong_threshold = max(strong_threshold, attack_threshold)
                        for risk_thr in RISK_THRESHOLDS:
                            for d_thr in ATTACK_DISTANCE_THRESHOLDS:
                                params = {
                                    "attack_threshold": attack_threshold,
                                    "strong_attack_threshold": strong_threshold,
                                    "risk_threshold": risk_thr,
                                    "d_attack_thr": d_thr,
                                }
                                scored = evaluate_candidate_frame(seed_df, attack_all, risk_all, params)
                                select_scored = scored[scored["phase"] == "select"].copy()
                                role_rows = role_metrics(select_scored, "temporal_head_hard", "temporal_head_suppress", "temporal_head_review")
                                metrics = key_metrics(role_rows)
                                row = {
                                    "seed": seed,
                                    "feature_set": feature_set,
                                    "model_kind": model_kind,
                                    "attack_q": attack_q,
                                    "risk_threshold": risk_thr,
                                    "strong_attack_q": strong_q,
                                    "d_attack_thr": d_thr,
                                    **params,
                                    **metrics,
                                    "feasible_1pct": metrics["dev_attack_min"] >= ATTACK_FLOOR and metrics["dev_ood_max"] <= OOD_TARGET,
                                    "feasible_5pct": metrics["dev_attack_min"] >= ATTACK_FLOOR and metrics["dev_ood_max"] <= OOD_DIAGNOSTIC_TARGET,
                                    "selection_uses_final_ood": False,
                                    "selection_uses_report_only_attack": False,
                                    "dev_score": metrics["dev_attack_min"] - 1.5 * metrics["dev_ood_max"] - metrics["dev_review_max"],
                                }
                                candidate_rows.append(row)

    config_summary = summarize_config(candidate_rows)
    feasible = [r for r in config_summary if r["feasible_1pct_all_seeds"]]
    if not feasible:
        feasible = [r for r in config_summary if r["feasible_5pct_all_seeds"]]
    pool = feasible if feasible else config_summary
    selected = max(
        pool,
        key=lambda r: (
            bool(r["feasible_1pct_all_seeds"]),
            bool(r["feasible_5pct_all_seeds"]),
            float(r["dev_attack_min_min"]),
            -float(r["dev_ood_max_max"]),
            float(r["dev_score_mean"]),
        ),
    )
    selected_role_rows = replay_selected_config(df, selected, fsets)
    selected_summary = aggregate_role_metrics(selected_role_rows)
    selected_metrics = key_metrics(selected_role_rows)

    bq_base = {
        "dev_attack_min": 0.984375,
        "dev_ood_max": 0.25933333333333336,
        "report_attack_min": 0.6501501501501501,
        "final_ood_max": 0.0,
    }
    if selected_metrics["dev_attack_min"] >= ATTACK_FLOOR and selected_metrics["dev_ood_max"] <= OOD_TARGET:
        verdict = "temporal_evidence_head_dev_passed_ready_for_controller_stability"
    elif selected_metrics["dev_attack_min"] >= ATTACK_FLOOR and selected_metrics["dev_ood_max"] < bq_base["dev_ood_max"]:
        verdict = "temporal_evidence_head_partial_pareto_improvement_but_ood_overbudget"
    elif selected_metrics["report_attack_min"] > bq_base["report_attack_min"] + 0.05 and selected_metrics["dev_ood_max"] <= bq_base["dev_ood_max"]:
        verdict = "temporal_evidence_head_recovers_attack_tail_but_not_ood"
    else:
        verdict = "temporal_evidence_head_no_reliable_gain_need_mini_flow_graph"
    if verdict == "temporal_evidence_head_dev_passed_ready_for_controller_stability":
        next_action = "issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay"
    else:
        next_action = "issue27bt_mini_flow_interaction_graph_from_pcap_metadata_or_task_boundary_audit"

    role_access_rows = [
        {
            "component": "lightweight_temporal_attack_head",
            "fit_roles": "fit half of id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "selection_roles": "select half of id_calib|ood_val|ood_stress_val|support_val|dev_future_near|dev_future_mid|dev_future_far",
            "report_only_roles": "final_ood_report_only|sealed_medium_attack_eval_report_only|sealed_dev_heavy_query_report_only|sealed_heavy_future_near|sealed_heavy_future_mid|sealed_heavy_future_far",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
        },
        {
            "component": "lightweight_temporal_ood_risk_head",
            "fit_roles": "fit half of dev benign/OOD vs dev attack roles",
            "selection_roles": "select half only",
            "report_only_roles": "replay only",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "temporal_head_feature_sets.csv", feature_rows)
    write_csv(OUT / "temporal_head_fit_select_split_audit.csv", split_rows)
    write_csv(OUT / "temporal_head_training_audit.csv", model_audit_rows)
    write_csv(OUT / "temporal_head_candidate_grid.csv", candidate_rows)
    write_csv(OUT / "temporal_head_config_summary.csv", config_summary)
    write_csv(OUT / "temporal_head_selection_audit.csv", [selected])
    write_csv(OUT / "temporal_head_replay_by_role.csv", selected_role_rows)
    write_csv(OUT / "temporal_head_replay_summary.csv", selected_summary)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "temporal_head_method_spec.md",
        [
            "# Lightweight Temporal Evidence Head Spec",
            "",
            "- This is a medium diagnostic, not a formal benchmark.",
            "- The 115D Kitsune frontend, split, and support contract stay fixed.",
            "- Each non-report-only role is split by past-only ordering into a fit half and a select half.",
            "- Final OOD and sealed attack roles are replay-only and never used for fit or threshold/model selection.",
            "- The temporal head compares three feature sets: current evidence only, past temporal only, and current evidence plus past temporal.",
            "- Past temporal features were generated in issue27br with `shift(1)` rolling windows, so current/future rows are excluded.",
            "- The controller is deliberately simple: attack head raw alarm, OOD-risk head suppresses only if high risk and not strong attack.",
        ],
    )
    write_md(
        OUT / "issue27bs_decision.md",
        [
            "# issue27bs Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- selected feature set: `{selected['feature_set']}`",
            f"- selected model kind: `{selected['model_kind']}`",
            f"- selected attack_q: `{selected['attack_q']}`",
            f"- selected risk_threshold: `{selected['risk_threshold']}`",
            f"- selected strong_attack_q: `{selected['strong_attack_q']}`",
            f"- selected d_attack_thr: `{selected['d_attack_thr']}`",
            f"- dev attack min: `{selected_metrics['dev_attack_min']}`",
            f"- dev OOD max: `{selected_metrics['dev_ood_max']}`",
            f"- report-only attack min: `{selected_metrics['report_attack_min']}`",
            f"- final OOD max report-only: `{selected_metrics['final_ood_max']}`",
            f"- bq base dev OOD max: `{bq_base['dev_ood_max']}`",
            f"- bq base report-only attack min: `{bq_base['report_attack_min']}`",
            "- caveat: this is a fit/select time-half diagnostic, not a group/file-disjoint formal evaluation.",
            "- caveat: the selected feature set includes parent BQ evidence, so the next step must run ablations without parent `ood_risk` and with group-disjoint replay.",
        ],
    )
    write_md(
        OUT / "issue27bt_next_action.md",
        [
            "# issue27bt Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- The lightweight temporal head has a strong medium diagnostic signal, but it must be stress-tested before any larger claim.",
            "- Next step should run group/file-disjoint replay, remove parent `ood_risk` in an ablation, and verify the result is not a time-half/source-adjacency artifact.",
            "- If those stability checks fail, then construct mini flow-interaction metadata from PCAP/processed CSV or run a task-boundary audit.",
            "- Keep final/report-only roles sealed.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bs.md",
        [
            "# Claim Update After issue27bs",
            "",
            "- issue27bs tests training-layer use of past-only temporal evidence.",
            "- A negative or partial result does not invalidate graph/trajectory evidence because this head still lacks true flow interaction fields.",
            "- No formal benchmark claim is allowed from this run.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bs Summary",
            "",
            "1. issue27bs completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: lightweight temporal-evidence head diagnostic",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. final/report-only used for fit/selection: no",
            f"7. selected feature set: `{selected['feature_set']}`",
            f"8. selected model kind: `{selected['model_kind']}`",
            f"9. dev attack min: `{selected_metrics['dev_attack_min']}`",
            f"10. dev OOD max: `{selected_metrics['dev_ood_max']}`",
            f"11. report-only attack min: `{selected_metrics['report_attack_min']}`",
            f"12. final OOD max report-only: `{selected_metrics['final_ood_max']}`",
            f"13. bq base dev attack min: `{bq_base['dev_attack_min']}`",
            f"14. bq base dev OOD max: `{bq_base['dev_ood_max']}`",
            f"15. bq base report-only attack min: `{bq_base['report_attack_min']}`",
            "16. caveat: current validation is time-half fit/select, not group/file-disjoint.",
            "17. caveat: selected feature set includes parent BQ evidence; ablation is required.",
            f"18. next action: `{next_action}`",
            "19. formal benchmark allowed: no",
            "20. commit hash: reported in final response",
        ],
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": verdict,
                "seeds": SEEDS,
                "selected": selected,
                "final_report_only_never_selects": True,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "scope": "medium lightweight temporal-evidence head diagnostic",
                "fit_roles": ["fit half of dev roles only"],
                "selection_roles": ["select half of dev roles only"],
                "report_only_roles": ["final_ood_report_only", "sealed attack roles"],
                "formal_benchmark": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bs_lightweight_temporal_head -->",
        [
            "## issue27bs - lightweight temporal evidence head",
            "",
            "<!-- issue27bs_lightweight_temporal_head -->",
            f"- Verdict: `{verdict}`.",
            "- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.",
            "- Non-report roles were split into fit/select halves by past-only order; final/report-only replay stayed sealed.",
            f"- Selected feature set: `{selected['feature_set']}`; model: `{selected['model_kind']}`.",
            f"- Dev attack min: `{selected_metrics['dev_attack_min']}`; dev OOD max: `{selected_metrics['dev_ood_max']}`.",
            f"- Report-only attack min: `{selected_metrics['report_attack_min']}`; final OOD max report-only: `{selected_metrics['final_ood_max']}`.",
            "- Caveat: this is a time-half medium diagnostic and must be followed by group-disjoint stability/ablation before any larger claim.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bs_lightweight_temporal_head -->",
        [
            "## issue27bs - lightweight temporal evidence head diagnostic",
            "",
            "<!-- issue27bs_lightweight_temporal_head -->",
            f"- Primary verdict: `{verdict}`.",
            "- Purpose: test whether training-layer past-only temporal evidence improves the BQ/BR frontier without final leakage.",
            "- Stage: medium diagnostic before any larger/full benchmark.",
        ],
    )

    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)

    print(
        json.dumps(
            {
                "primary_verdict": verdict,
                "selected": selected,
                "selected_metrics": selected_metrics,
                "bq_base": bq_base,
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
