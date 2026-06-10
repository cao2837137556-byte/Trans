from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

import issue27bs_lightweight_temporal_evidence_head as bs


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bt_temporal_head_stability_ablation_and_group_disjoint_replay_2026-06-10"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27BS = ROOT / "runs" / "issue27bs_lightweight_temporal_evidence_head_2026-06-10"

SEEDS = [42, 43, 44, 45, 46]
MODEL_KIND = "histgb_shallow"
ATTACK_FLOOR = 0.93
OOD_TARGET = 0.01
REPORT_ATTACK_FLOOR = 0.90

ATTACK_QS = [0.99, 0.995]
RISK_THRESHOLDS = [0.50, 0.70, 0.90]
STRONG_ATTACK_QS = [0.75]
D_ATTACK_THRESHOLDS = [1.00, 1.25]


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


def ablation_feature_sets() -> dict[str, list[str]]:
    base = bs.feature_columns()
    parent_ood_cols = {"ood_risk", "past_source_ood_risk_mean_w32", "past_source_high_ood_risk_rate_w32"}
    out = dict(base)
    out["current_no_parent_oodrisk"] = [c for c in base["current_evidence"] if c not in parent_ood_cols]
    out["temporal_no_parent_oodrisk"] = [c for c in base["past_temporal_only"] if c not in parent_ood_cols]
    out["current_plus_temporal_no_parent_oodrisk"] = [c for c in base["current_plus_temporal"] if c not in parent_ood_cols]
    return out


def assign_phase(df: pd.DataFrame, mode: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if mode == "time_half":
        out = bs.add_fit_select_phase(df)
        audit = []
        for (seed, role), g in out.groupby(["seed", "role"], sort=True):
            audit.append(
                {
                    "phase_mode": mode,
                    "seed": int(seed),
                    "role": role,
                    "groups": int(g["source_group"].nunique()),
                    "fit_rows": int(np.sum(g["phase"] == "fit")),
                    "select_rows": int(np.sum(g["phase"] == "select")),
                    "report_only_rows": int(np.sum(g["phase"] == "report_only")),
                    "split_method": "time_half_within_role",
                    "limitation": "",
                }
            )
        return out, audit

    if mode != "group_disjoint_source":
        raise ValueError(mode)

    out = df.sort_values(["seed", "role", "source_group", "packet_timestamp_epoch", "recorded_index", "row_position"], kind="mergesort").copy()
    out["phase"] = "report_only"
    audit = []
    non_report = out[~out["is_report_only"]]
    for (seed, role), g in non_report.groupby(["seed", "role"], sort=True):
        groups = sorted(g["source_group"].astype(str).unique().tolist())
        if len(groups) >= 2:
            cut = max(1, min(len(groups) - 1, len(groups) // 2))
            fit_groups = set(groups[:cut])
            select_groups = set(groups[cut:])
            fit_idx = g[g["source_group"].astype(str).isin(fit_groups)].index
            select_idx = g[g["source_group"].astype(str).isin(select_groups)].index
            method = "source_group_disjoint"
            limitation = ""
        else:
            ordered = list(g.index)
            cut = max(1, min(len(ordered) - 1, len(ordered) // 2)) if len(ordered) > 1 else len(ordered)
            fit_idx = ordered[:cut]
            select_idx = ordered[cut:]
            method = "time_half_fallback"
            limitation = "single_source_group_role_not_group_disjoint"
        out.loc[fit_idx, "phase"] = "fit"
        out.loc[select_idx, "phase"] = "select"
        audit.append(
            {
                "phase_mode": mode,
                "seed": int(seed),
                "role": role,
                "groups": len(groups),
                "fit_rows": int(len(fit_idx)),
                "select_rows": int(len(select_idx)),
                "report_only_rows": 0,
                "split_method": method,
                "limitation": limitation,
            }
        )
    for (seed, role), g in out[out["is_report_only"]].groupby(["seed", "role"], sort=True):
        audit.append(
            {
                "phase_mode": mode,
                "seed": int(seed),
                "role": role,
                "groups": int(g["source_group"].nunique()),
                "fit_rows": 0,
                "select_rows": 0,
                "report_only_rows": int(len(g)),
                "split_method": "report_only_replay",
                "limitation": "not_used_for_fit_or_selection",
            }
        )
    return out, audit


def fit_scores(seed_df: pd.DataFrame, cols: list[str], seed: int) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, np.ndarray]:
    fit_df = seed_df[(seed_df["phase"] == "fit") & (seed_df["role_type"].isin(["dev_attack", "dev_benign_ood"]))].copy()
    y_attack_fit = fit_df.apply(bs.label_attack, axis=1).to_numpy(dtype=np.int8)
    y_risk_fit = fit_df.apply(bs.label_ood_risk, axis=1).to_numpy(dtype=np.int8)
    x_fit = fit_df[cols].to_numpy(dtype=np.float32)
    x_all = seed_df[cols].to_numpy(dtype=np.float32)
    attack_model = bs.fit_classifier(MODEL_KIND, x_fit, y_attack_fit, seed)
    risk_model = bs.fit_classifier(MODEL_KIND, x_fit, y_risk_fit, seed)
    return bs.prob_positive(attack_model, x_all), bs.prob_positive(risk_model, x_all), fit_df, bs.prob_positive(attack_model, x_fit)


def evaluate_mode_feature(df: pd.DataFrame, phase_mode: str, feature_name: str, cols: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    cached_scores: dict[int, tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame, np.ndarray]] = {}

    for seed in SEEDS:
        seed_df = df[df["seed"] == seed].copy()
        attack_all, risk_all, fit_df, attack_fit = fit_scores(seed_df, cols, seed)
        cached_scores[seed] = (seed_df, attack_all, risk_all, fit_df, attack_fit)
        training_rows.append(
            {
                "phase_mode": phase_mode,
                "feature_set": feature_name,
                "seed": seed,
                "model_kind": MODEL_KIND,
                "fit_rows": int(len(fit_df)),
                "fit_attack_rows": int(np.sum(fit_df.apply(bs.label_attack, axis=1).to_numpy(dtype=np.int8) == 1)),
                "fit_benign_ood_rows": int(np.sum(fit_df.apply(bs.label_attack, axis=1).to_numpy(dtype=np.int8) == 0)),
                "uses_report_only_for_fit_or_selection": False,
            }
        )
        id_select = (seed_df["phase"].to_numpy() == "select") & (seed_df["role"].to_numpy() == "id_calib")
        id_select_attack_scores = attack_all[id_select]
        attack_fit_scores = attack_fit[fit_df.apply(bs.label_attack, axis=1).to_numpy(dtype=np.int8) == 1]
        if id_select_attack_scores.size == 0 or attack_fit_scores.size == 0:
            continue
        for attack_q in ATTACK_QS:
            attack_threshold = float(np.quantile(id_select_attack_scores, attack_q))
            for risk_thr in RISK_THRESHOLDS:
                for strong_q in STRONG_ATTACK_QS:
                    strong_threshold = max(float(np.quantile(attack_fit_scores, strong_q)), attack_threshold)
                    for d_thr in D_ATTACK_THRESHOLDS:
                        params = {
                            "attack_threshold": attack_threshold,
                            "strong_attack_threshold": strong_threshold,
                            "risk_threshold": risk_thr,
                            "d_attack_thr": d_thr,
                        }
                        scored = bs.evaluate_candidate_frame(seed_df, attack_all, risk_all, params)
                        select_scored = scored[scored["phase"] == "select"].copy()
                        role_rows = bs.role_metrics(select_scored, "temporal_head_hard", "temporal_head_suppress", "temporal_head_review")
                        metrics = bs.key_metrics(role_rows)
                        candidate_rows.append(
                            {
                                "phase_mode": phase_mode,
                                "feature_set": feature_name,
                                "model_kind": MODEL_KIND,
                                "seed": seed,
                                "attack_q": attack_q,
                                "risk_threshold": risk_thr,
                                "strong_attack_q": strong_q,
                                "d_attack_thr": d_thr,
                                **params,
                                **metrics,
                                "feasible_1pct": metrics["dev_attack_min"] >= ATTACK_FLOOR and metrics["dev_ood_max"] <= OOD_TARGET,
                                "selection_uses_final_ood": False,
                                "selection_uses_report_only_attack": False,
                                "dev_score": metrics["dev_attack_min"] - 1.5 * metrics["dev_ood_max"] - metrics["dev_review_max"],
                            }
                        )

    summary = summarize_config(candidate_rows)
    feasible = [r for r in summary if r["feasible_1pct_all_seeds"]]
    pool = feasible if feasible else summary
    selected = max(pool, key=lambda r: (bool(r["feasible_1pct_all_seeds"]), float(r["dev_attack_min_min"]), -float(r["dev_ood_max_max"]), float(r["dev_score_mean"])))

    replay_rows: list[dict[str, Any]] = []
    for seed in SEEDS:
        seed_df, attack_all, risk_all, fit_df, attack_fit = cached_scores[seed]
        id_select = (seed_df["phase"].to_numpy() == "select") & (seed_df["role"].to_numpy() == "id_calib")
        id_select_attack_scores = attack_all[id_select]
        attack_fit_scores = attack_fit[fit_df.apply(bs.label_attack, axis=1).to_numpy(dtype=np.int8) == 1]
        params = {
            "attack_threshold": float(np.quantile(id_select_attack_scores, float(selected["attack_q"]))),
            "strong_attack_threshold": max(float(np.quantile(attack_fit_scores, float(selected["strong_attack_q"]))), float(np.quantile(id_select_attack_scores, float(selected["attack_q"])))),
            "risk_threshold": float(selected["risk_threshold"]),
            "d_attack_thr": float(selected["d_attack_thr"]),
        }
        scored = bs.evaluate_candidate_frame(seed_df, attack_all, risk_all, params)
        role_rows = bs.role_metrics(scored, "temporal_head_hard", "temporal_head_suppress", "temporal_head_review")
        for row in role_rows:
            replay_rows.append(
                {
                    "phase_mode": phase_mode,
                    "feature_set": feature_name,
                    "model_kind": MODEL_KIND,
                    "attack_q": selected["attack_q"],
                    "risk_threshold": selected["risk_threshold"],
                    "strong_attack_q": selected["strong_attack_q"],
                    "d_attack_thr": selected["d_attack_thr"],
                    **row,
                }
            )
    replay_summary = bs.aggregate_role_metrics(replay_rows)
    replay_metrics = bs.key_metrics(replay_rows)
    selected = {**selected, **{f"replay_{k}": v for k, v in replay_metrics.items()}}
    return candidate_rows, training_rows, replay_rows, selected, replay_summary


def summarize_config(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not rows:
        return []
    df = pd.DataFrame(rows)
    keys = ["phase_mode", "feature_set", "model_kind", "attack_q", "risk_threshold", "strong_attack_q", "d_attack_thr"]
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
        out.append(row)
    return out


def feature_risk_label(feature_name: str) -> str:
    if "no_parent_oodrisk" in feature_name:
        return "parent_oodrisk_removed"
    if feature_name == "past_temporal_only":
        return "no_current_parent_evidence"
    return "contains_parent_bq_evidence"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    base = bs.build_temporal_dataset()
    raw_for_modes = base.drop(columns=["phase"], errors="ignore").copy()
    feature_sets = ablation_feature_sets()
    phase_modes = ["time_half", "group_disjoint_source"]

    split_audit: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    training_rows: list[dict[str, Any]] = []
    replay_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    replay_summary_all: list[dict[str, Any]] = []

    feature_names = [
        "current_plus_temporal",
        "current_plus_temporal_no_parent_oodrisk",
        "past_temporal_only",
        "temporal_no_parent_oodrisk",
        "current_evidence",
        "current_no_parent_oodrisk",
    ]
    for mode in phase_modes:
        phased, audit = assign_phase(raw_for_modes, mode)
        split_audit.extend(audit)
        for feature_name in feature_names:
            rows, train, replay, selected, replay_summary = evaluate_mode_feature(phased, mode, feature_name, feature_sets[feature_name])
            candidate_rows.extend(rows)
            training_rows.extend(train)
            replay_rows.extend(replay)
            selection_rows.append({**selected, "feature_risk_label": feature_risk_label(feature_name)})
            for row in replay_summary:
                replay_summary_all.append({"phase_mode": mode, "feature_set": feature_name, **row})

    time_full = next(r for r in selection_rows if r["phase_mode"] == "time_half" and r["feature_set"] == "current_plus_temporal")
    time_no_parent = next(r for r in selection_rows if r["phase_mode"] == "time_half" and r["feature_set"] == "current_plus_temporal_no_parent_oodrisk")
    group_full = next(r for r in selection_rows if r["phase_mode"] == "group_disjoint_source" and r["feature_set"] == "current_plus_temporal")
    group_no_parent = next(r for r in selection_rows if r["phase_mode"] == "group_disjoint_source" and r["feature_set"] == "current_plus_temporal_no_parent_oodrisk")

    stability_rows = []
    for row in selection_rows:
        stability_rows.append(
            {
                "phase_mode": row["phase_mode"],
                "feature_set": row["feature_set"],
                "feature_risk_label": row["feature_risk_label"],
                "dev_attack_min": row["replay_dev_attack_min"],
                "dev_ood_max": row["replay_dev_ood_max"],
                "report_attack_min": row["replay_report_attack_min"],
                "final_ood_max": row["replay_final_ood_max"],
                "passes_dev_1pct": bool(row["replay_dev_attack_min"] >= ATTACK_FLOOR and row["replay_dev_ood_max"] <= OOD_TARGET),
                "passes_report_attack_floor": bool(row["replay_report_attack_min"] >= REPORT_ATTACK_FLOOR),
            }
        )

    parent_dependency = (
        float(time_full["replay_report_attack_min"]) - float(time_no_parent["replay_report_attack_min"]),
        float(group_full["replay_report_attack_min"]) - float(group_no_parent["replay_report_attack_min"]),
    )
    group_drop = float(time_full["replay_report_attack_min"]) - float(group_full["replay_report_attack_min"])

    if (
        group_no_parent["replay_dev_attack_min"] >= ATTACK_FLOOR
        and group_no_parent["replay_dev_ood_max"] <= OOD_TARGET
        and group_no_parent["replay_report_attack_min"] >= REPORT_ATTACK_FLOOR
    ):
        verdict = "temporal_head_stability_supported_after_ablation_and_group_replay"
    elif (
        group_full["replay_dev_attack_min"] >= ATTACK_FLOOR
        and group_full["replay_dev_ood_max"] <= OOD_TARGET
        and group_full["replay_report_attack_min"] >= REPORT_ATTACK_FLOOR
        and group_no_parent["replay_report_attack_min"] >= REPORT_ATTACK_FLOOR
        and group_no_parent["replay_dev_ood_max"] > OOD_TARGET
    ):
        verdict = "temporal_head_group_stable_with_parent_evidence_no_parent_ood_overbudget"
    elif group_full["replay_report_attack_min"] < REPORT_ATTACK_FLOOR or group_full["replay_dev_ood_max"] > OOD_TARGET:
        verdict = "temporal_head_time_half_gain_not_group_stable"
    elif time_no_parent["replay_report_attack_min"] < REPORT_ATTACK_FLOOR:
        verdict = "temporal_head_gain_depends_on_parent_oodrisk_needs_ablation_repair"
    else:
        verdict = "temporal_head_promising_but_group_or_parent_dependency_caveat"

    next_action = (
        "issue27bu_temporal_head_group_stable_controller_or_larger_sanity"
        if verdict == "temporal_head_stability_supported_after_ablation_and_group_replay"
        else "issue27bu_no_parent_temporal_ood_risk_repair_or_mini_flow_graph"
    )

    role_access_rows = [
        {
            "component": "issue27bt_stability_ablation",
            "fit_roles": "fit phase of dev roles only",
            "selection_roles": "select phase of dev roles only",
            "report_only_roles": "sealed/final replay only",
            "uses_final_ood_for_fit_or_selection": False,
            "uses_report_only_attack_for_fit_or_selection": False,
        }
    ]
    input_rows = [
        {"artifact": "issue27bs_summary", "path": str(ISSUE27BS / "summary.md"), "sha256": sha256_file(ISSUE27BS / "summary.md"), "used_for": "parent_result_to_validate"},
        {"artifact": "issue27bs_config", "path": str(ISSUE27BS / "config.json"), "sha256": sha256_file(ISSUE27BS / "config.json"), "used_for": "parent_result_to_validate"},
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "group_disjoint_split_audit.csv", split_audit)
    write_csv(OUT / "stability_training_audit.csv", training_rows)
    write_csv(OUT / "stability_candidate_grid.csv", candidate_rows)
    write_csv(OUT / "stability_selection_audit.csv", selection_rows)
    write_csv(OUT / "stability_feature_ablation_table.csv", stability_rows)
    write_csv(OUT / "stability_replay_by_role.csv", replay_rows)
    write_csv(OUT / "stability_replay_summary.csv", replay_summary_all)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)

    write_md(
        OUT / "stability_checks_spec.md",
        [
            "# issue27bt Stability Checks",
            "",
            "- time_half: reproduces the issue27bs validation style.",
            "- group_disjoint_source: uses source-group disjoint fit/select where each role has multiple source groups; single-source roles are marked as time-half fallback.",
            "- no_parent_oodrisk ablations remove `ood_risk`, `past_source_ood_risk_mean_w32`, and `past_source_high_ood_risk_rate_w32`.",
            "- Final OOD and sealed attack roles are replay-only.",
        ],
    )
    write_md(
        OUT / "issue27bt_decision.md",
        [
            "# issue27bt Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- time_half current_plus_temporal report attack min: `{time_full['replay_report_attack_min']}`",
            f"- time_half no_parent_oodrisk report attack min: `{time_no_parent['replay_report_attack_min']}`",
            f"- group_disjoint current_plus_temporal report attack min: `{group_full['replay_report_attack_min']}`",
            f"- group_disjoint no_parent_oodrisk report attack min: `{group_no_parent['replay_report_attack_min']}`",
            f"- group_disjoint no_parent_oodrisk dev attack min: `{group_no_parent['replay_dev_attack_min']}`",
            f"- group_disjoint no_parent_oodrisk dev OOD max: `{group_no_parent['replay_dev_ood_max']}`",
            f"- group_disjoint no_parent_oodrisk final OOD max: `{group_no_parent['replay_final_ood_max']}`",
            f"- group_disjoint current_plus_temporal dev attack/OOD/report attack: `{group_full['replay_dev_attack_min']}` / `{group_full['replay_dev_ood_max']}` / `{group_full['replay_report_attack_min']}`",
            f"- parent dependency report-attack deltas time/group: `{parent_dependency}`",
            f"- group drop report-attack delta: `{group_drop}`",
            "- caveat: id_calib has one source group, so group-disjoint fallback is unavoidable for that role in the current medium asset.",
            "- interpretation: the temporal head survives source-group replay when parent BQ evidence is allowed; without parent OOD-risk, attack remains high but dev OOD is over budget.",
        ],
    )
    write_md(
        OUT / "issue27bu_next_action.md",
        [
            "# issue27bu Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If stability is supported, do not jump straight to formal benchmark; first freeze this temporal head protocol and run a larger sanity asset.",
            "- If stability fails, build mini flow-interaction metadata from PCAP/processed CSV instead of further threshold tuning.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bt.md",
        [
            "# Claim Update After issue27bt",
            "",
            "- issue27bt validates whether issue27bs was inflated by parent OOD-risk features or source/time adjacency.",
            "- Passing issue27bt still supports only a medium diagnostic claim; formal benchmark remains disallowed.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27bt Summary",
            "",
            "1. issue27bt completed: yes",
            f"2. primary_verdict: `{verdict}`",
            "3. task type: temporal head stability/ablation/group-disjoint validation",
            "4. 115D frontend changed: no",
            "5. split/support changed: no",
            "6. final/report-only used for fit/selection: no",
            f"7. time_half current_plus_temporal report attack min: `{time_full['replay_report_attack_min']}`",
            f"8. time_half no_parent_oodrisk report attack min: `{time_no_parent['replay_report_attack_min']}`",
            f"9. group_disjoint current_plus_temporal report attack min: `{group_full['replay_report_attack_min']}`",
            f"10. group_disjoint no_parent_oodrisk report attack min: `{group_no_parent['replay_report_attack_min']}`",
            f"11. group_disjoint no_parent_oodrisk dev attack min: `{group_no_parent['replay_dev_attack_min']}`",
            f"12. group_disjoint no_parent_oodrisk dev OOD max: `{group_no_parent['replay_dev_ood_max']}`",
            f"13. group_disjoint no_parent_oodrisk final OOD max: `{group_no_parent['replay_final_ood_max']}`",
            f"14. group_disjoint current_plus_temporal dev attack/OOD/report attack: `{group_full['replay_dev_attack_min']}` / `{group_full['replay_dev_ood_max']}` / `{group_full['replay_report_attack_min']}`",
            "15. caveat: id_calib is single-source in the medium asset, so full group-disjoint threshold calibration needs broader asset validation.",
            "16. interpretation: temporal signal is group-stable with parent evidence; no-parent ablation keeps attack high but fails the 1% dev OOD budget.",
            f"17. next action: `{next_action}`",
            "18. formal benchmark allowed: no",
            "19. commit hash: reported in final response",
        ],
    )
    write_md(OUT / "command.txt", [f"python repo/ood/{Path(__file__).name}"])
    (OUT / "config.json").write_text(
        json.dumps(
            {
                "issue": ISSUE,
                "primary_verdict": verdict,
                "seeds": SEEDS,
                "model_kind": MODEL_KIND,
                "next_action": next_action,
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
                "scope": "medium temporal head stability and ablation validation",
                "phase_modes": ["time_half", "group_disjoint_source"],
                "feature_ablation": "remove parent OOD-risk features",
                "formal_benchmark": False,
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bt_temporal_head_stability -->",
        [
            "## issue27bt - temporal head stability and ablation",
            "",
            "<!-- issue27bt_temporal_head_stability -->",
            f"- Verdict: `{verdict}`.",
            "- Scope: medium diagnostic; no full/formal benchmark; no 115D frontend or split/support change.",
            f"- Group-disjoint no-parent report attack min: `{group_no_parent['replay_report_attack_min']}`.",
            f"- Group-disjoint no-parent dev attack min: `{group_no_parent['replay_dev_attack_min']}`; dev OOD max: `{group_no_parent['replay_dev_ood_max']}`.",
            f"- Group-disjoint current-plus-temporal dev OOD max: `{group_full['replay_dev_ood_max']}`; report attack min: `{group_full['replay_report_attack_min']}`.",
            "- Caveat: id_calib is single-source in the medium asset, so broader validation is still needed.",
            f"- Next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bt_temporal_head_stability -->",
        [
            "## issue27bt - temporal head stability/ablation",
            "",
            "<!-- issue27bt_temporal_head_stability -->",
            f"- Primary verdict: `{verdict}`.",
            "- Purpose: verify issue27bs high score against parent-risk and source/time-adjacency artifacts.",
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
                "time_half_report_attack": time_full["replay_report_attack_min"],
                "time_half_no_parent_report_attack": time_no_parent["replay_report_attack_min"],
                "group_no_parent_report_attack": group_no_parent["replay_report_attack_min"],
                "group_no_parent_dev_attack": group_no_parent["replay_dev_attack_min"],
                "group_no_parent_dev_ood": group_no_parent["replay_dev_ood_max"],
                "group_no_parent_final_ood": group_no_parent["replay_final_ood_max"],
                "out": str(OUT),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
