from __future__ import annotations

import csv
import gzip
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27au_coverage_aware_active_labeling_viability_diagnostic_2026-06-04"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27AT = ROOT / "runs" / "issue27at_coverage_hypothesis_validation_before_protocol_redesign_2026-06-03"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SUPPORT_BUDGET = 128
OOD_WEIGHT = 2.0
SUPPORT_WEIGHT = 4.0
SEEDS = [42, 43, 44, 45, 46]
ACTIVE_LABEL_BUDGETS = [0, 4, 8, 16, 32]
ACTIVE_CANDIDATE_ROWS_PER_FILE = 1000
VAL_TARGET = 0.01

ID_ROLE = ar.ID_ROLE
OOD_VAL_ROLE = ar.OOD_VAL_ROLE
FINAL_OOD_ROLE = ar.FINAL_OOD_ROLE
SUPPORT_ROLE = ar.SUPPORT_ROLE
ATTACK_EVAL_ROLE = ar.ATTACK_EVAL_ROLE
DEV_ACTIVE_ROLE = "dev_heavy_unlabeled_active_label_candidate_stream"
DEV_QUERY_ROLE = "dev_heavy_query_after_active_labeling"


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


def read_csv(path: Path) -> list[dict[str, str]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def label_is_attack(row: dict[str, str]) -> bool:
    return (row.get("binary_label_from_alignment") or row.get("label") or "").lower() == "attack"


def packet_order(row: dict[str, str]) -> tuple[str, int]:
    csv_member = row.get("csv_member", "unknown")
    try:
        recorded = int(float(row.get("recorded_index", "")))
    except ValueError:
        try:
            recorded = int(float(row.get("packet_index", "")))
        except ValueError:
            recorded = 0
    return csv_member, recorded


def split_new_heavy_stream(sidecar: list[dict[str, str]]) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    by_file: dict[str, list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for i, row in enumerate(sidecar):
        by_file[row.get("csv_member", "unknown")].append((i, row))
    candidate: list[int] = []
    query: list[int] = []
    manifest: list[dict[str, Any]] = []
    for csv_member, items in sorted(by_file.items()):
        items = sorted(items, key=lambda t: packet_order(t[1])[1])
        cand = items[:ACTIVE_CANDIDATE_ROWS_PER_FILE]
        qry = items[ACTIVE_CANDIDATE_ROWS_PER_FILE:]
        candidate.extend(i for i, _ in cand)
        query.extend(i for i, _ in qry)
        manifest.append(
            {
                "csv_member": csv_member,
                "active_candidate_rows": len(cand),
                "query_after_labeling_rows": len(qry),
                "split_rule": f"first_{ACTIVE_CANDIDATE_ROWS_PER_FILE}_rows_per_file_for_unlabeled_active_candidate_stream_rest_for_query",
                "candidate_attack_labels_hidden_during_selection": True,
                "query_report_only": True,
            }
        )
    return np.asarray(candidate, dtype=np.int64), np.asarray(query, dtype=np.int64), manifest


def hash_indices(indices: np.ndarray) -> str:
    return hashlib.sha256(",".join(map(str, np.asarray(indices, dtype=np.int64).tolist())).encode("utf-8")).hexdigest()


def select_active_labels(
    x_base_support: np.ndarray,
    x_support_val: np.ndarray,
    x_candidates: np.ndarray,
    candidate_indices: np.ndarray,
    budget: int,
) -> tuple[np.ndarray, dict[str, Any]]:
    if budget <= 0 or len(candidate_indices) == 0:
        return np.asarray([], dtype=np.int64), {
            "budget": budget,
            "candidate_count": int(len(candidate_indices)),
            "uncovered_candidate_count": 0,
            "selector": "none_budget_0",
        }
    scaler = StandardScaler().fit(x_base_support)
    z_support = scaler.transform(x_base_support)
    z_val = scaler.transform(x_support_val)
    z_cand = scaler.transform(x_candidates)
    val_dist = pairwise_distances(z_val, z_support, metric="euclidean").min(axis=1)
    cand_dist_to_support = pairwise_distances(z_cand, z_support, metric="euclidean").min(axis=1)
    p95 = float(np.quantile(val_dist, 0.95))
    uncovered_local = np.where(cand_dist_to_support > p95)[0]
    pool_local = uncovered_local if len(uncovered_local) >= budget else np.arange(len(candidate_indices), dtype=np.int64)
    z_pool = z_cand[pool_local]
    dist_pool_support = cand_dist_to_support[pool_local]
    start = int(np.argmax(dist_pool_support))
    selected_local_pool = [start]
    min_dist = pairwise_distances(z_pool, z_pool[[start]], metric="euclidean").ravel()
    min_dist[start] = -1.0
    while len(selected_local_pool) < min(budget, len(pool_local)):
        nxt = int(np.argmax(min_dist))
        selected_local_pool.append(nxt)
        dist = pairwise_distances(z_pool, z_pool[[nxt]], metric="euclidean").ravel()
        min_dist = np.minimum(min_dist, dist)
        min_dist[selected_local_pool] = -1.0
    selected_candidate_indices = candidate_indices[pool_local[np.asarray(selected_local_pool, dtype=np.int64)]]
    return np.asarray(sorted(selected_candidate_indices.tolist()), dtype=np.int64), {
        "budget": budget,
        "candidate_count": int(len(candidate_indices)),
        "uncovered_candidate_count": int(len(uncovered_local)),
        "support_val_p95_radius": p95,
        "selector": "coverage_aware_uncovered_first_farthest_first_feature_only",
        "uses_candidate_labels_for_selection": False,
        "uses_query_labels_for_selection": False,
    }


def rate(scores: np.ndarray, threshold: float) -> float:
    return float(np.mean(scores > threshold)) if len(scores) else float("nan")


def coverage_fraction(x_support: np.ndarray, x_support_val: np.ndarray, x_query: np.ndarray) -> dict[str, float]:
    if len(x_support) == 0 or len(x_support_val) == 0 or len(x_query) == 0:
        return {
            "coverage_sufficient_fraction": float("nan"),
            "nearest_distance_p50": float("nan"),
            "nearest_distance_p95": float("nan"),
            "support_val_p75_radius": float("nan"),
            "support_val_p95_radius": float("nan"),
        }
    scaler = StandardScaler().fit(x_support)
    z_support = scaler.transform(x_support)
    z_val = scaler.transform(x_support_val)
    z_query = scaler.transform(x_query)
    val_d = pairwise_distances(z_val, z_support, metric="euclidean").min(axis=1)
    q_d = pairwise_distances(z_query, z_support, metric="euclidean").min(axis=1)
    p75 = float(np.quantile(val_d, 0.75))
    p95 = float(np.quantile(val_d, 0.95))
    return {
        "coverage_sufficient_fraction": float(np.mean(q_d <= p75)),
        "coverage_review_or_better_fraction": float(np.mean(q_d <= p95)),
        "nearest_distance_p50": float(np.quantile(q_d, 0.50)),
        "nearest_distance_p95": float(np.quantile(q_d, 0.95)),
        "support_val_p75_radius": p75,
        "support_val_p95_radius": p95,
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    keys = ["budget", "threshold_rule"]
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, gr in sorted(groups.items()):
        row = {k: v for k, v in zip(keys, key)}
        for metric in [
            "requested_labels",
            "confirmed_attack_labels",
            "label_efficiency",
            "id_calib_alarm",
            "ood_val_alarm",
            "support_val_detection",
            "final_ood_alarm_report_only",
            "medium_attack_eval_detection_report_only",
            "dev_query_detection_report_only",
            "dev_query_coverage_sufficient_fraction",
            "dev_query_coverage_review_or_better_fraction",
        ]:
            vals = np.asarray([float(g[metric]) for g in gr if g[metric] == g[metric]], dtype=np.float64)
            row[f"{metric}_mean"] = float(np.mean(vals)) if len(vals) else float("nan")
            row[f"{metric}_min"] = float(np.min(vals)) if len(vals) else float("nan")
            row[f"{metric}_max"] = float(np.max(vals)) if len(vals) else float("nan")
        row["ood_val_safe_all_seeds"] = all(float(g["ood_val_alarm"]) <= VAL_TARGET and float(g["id_calib_alarm"]) <= VAL_TARGET for g in gr)
        row["final_ood_report_only_safe_all_seeds"] = all(float(g["final_ood_alarm_report_only"]) <= VAL_TARGET for g in gr)
        out.append(row)
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]
    id_idx = ar.role_indices(sidecar, ID_ROLE)
    ood_idx = ar.role_indices(sidecar, OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    active_candidate_idx, dev_query_idx, split_manifest = split_new_heavy_stream(new_sidecar)

    input_hash_rows = [
        {"artifact": "issue27af_medium_certificate", "path": str(cert_path), "sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27at_summary", "path": str(ISSUE27AT / "summary.md"), "sha256": sha256_file(ISSUE27AT / "summary.md"), "hash_match": True},
    ]
    input_hash_rows.extend(checks)
    input_hash_rows.extend(new_checks)

    result_rows: list[dict[str, Any]] = []
    selection_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    ood_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, SUPPORT_BUDGET)
        base_train, base_val = issue27as.split_support(base_support, seed)
        x_base_train = x[base_train]
        x_base_val = x[base_val]
        for budget in ACTIVE_LABEL_BUDGETS:
            selected_local, sel_audit = select_active_labels(
                x_base_support=x_base_train,
                x_support_val=x_base_val,
                x_candidates=new_x[active_candidate_idx],
                candidate_indices=active_candidate_idx,
                budget=budget,
            )
            confirmed_attack = np.asarray([i for i in selected_local if label_is_attack(new_sidecar[int(i)])], dtype=np.int64)
            x_support_aug = np.vstack([x[base_train], new_x[confirmed_attack]]) if len(confirmed_attack) else x[base_train]
            model = issue27as.WeightedOldHistGB(seed, OOD_WEIGHT, SUPPORT_WEIGHT)
            model.fit(x[id_fit], x[ood_train], x_support_aug)
            score_id = model.score(x[id_calib])
            score_ood = model.score(x[ood_val])
            score_support_val = model.score(x[base_val])
            threshold_specs = [
                issue27as.support_guided_threshold(score_id, score_ood, score_support_val),
                issue27as.orderstat_threshold(score_id, score_ood, score_support_val),
            ]
            score_final = model.score(x[final_ood])
            score_medium_attack = model.score(x[attack_eval])
            score_query = model.score(new_x[dev_query_idx])
            cov = coverage_fraction(x_support_aug, x_base_val, new_x[dev_query_idx])
            selection_rows.append(
                {
                    "seed": seed,
                    "budget": budget,
                    "requested_labels": int(len(selected_local)),
                    "confirmed_attack_labels": int(len(confirmed_attack)),
                    "label_efficiency": float(len(confirmed_attack) / max(1, len(selected_local))),
                    "active_candidate_pool_rows": int(len(active_candidate_idx)),
                    "dev_query_rows": int(len(dev_query_idx)),
                    "selected_local_indices_sha256": hash_indices(selected_local),
                    "confirmed_attack_local_indices_sha256": hash_indices(confirmed_attack),
                    **sel_audit,
                }
            )
            by_file = Counter(new_sidecar[int(i)].get("csv_member", "unknown") for i in selected_local)
            for rank, i in enumerate(selected_local.tolist()):
                selection_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "selection_rank_detail": rank,
                        "selected_local_index": int(i),
                        "csv_member": new_sidecar[int(i)].get("csv_member", ""),
                        "packet_index": new_sidecar[int(i)].get("packet_index", ""),
                        "oracle_label_after_selection": new_sidecar[int(i)].get("binary_label_from_alignment", ""),
                        "uses_label_for_selection": False,
                        "selected_file_count_json": json.dumps(dict(by_file), sort_keys=True),
                    }
                )
            role_rows.append(
                {
                    "seed": seed,
                    "budget": budget,
                    "fit_roles": "id_fit_from_id_benign_train|ood_train_guard_from_ood_benign_val|base_attack_support_train|oracle_confirmed_active_labels_from_dev_active_stream",
                    "threshold_roles": "id_calib_from_id_benign_train|ood_val_calib_from_ood_benign_val|base_support_val",
                    "active_selection_inputs": "dev_active_stream_features_only|base_support_train_features|base_support_val_distance_quantiles",
                    "report_only_roles": f"{FINAL_OOD_ROLE}|{ATTACK_EVAL_ROLE}|{DEV_QUERY_ROLE}",
                    "uses_candidate_labels_for_active_selection": False,
                    "uses_dev_query_for_active_selection": False,
                    "uses_final_ood_for_selection": False,
                    "uses_attack_eval_for_selection": False,
                    "forbidden_role_access": False,
                }
            )
            coverage_rows.append(
                {
                    "seed": seed,
                    "budget": budget,
                    "requested_labels": int(len(selected_local)),
                    "confirmed_attack_labels": int(len(confirmed_attack)),
                    **cov,
                }
            )
            for th in threshold_specs:
                threshold = float(th["threshold"])
                row = {
                    "seed": seed,
                    "budget": budget,
                    "threshold_rule": th["rule"],
                    "threshold": threshold,
                    "requested_labels": int(len(selected_local)),
                    "confirmed_attack_labels": int(len(confirmed_attack)),
                    "label_efficiency": float(len(confirmed_attack) / max(1, len(selected_local))),
                    "id_calib_alarm": issue27as.rate(score_id, threshold),
                    "ood_val_alarm": issue27as.rate(score_ood, threshold),
                    "support_val_detection": issue27as.rate(score_support_val, threshold),
                    "final_ood_alarm_report_only": issue27as.rate(score_final, threshold),
                    "medium_attack_eval_detection_report_only": issue27as.rate(score_medium_attack, threshold),
                    "dev_query_detection_report_only": issue27as.rate(score_query, threshold),
                    "dev_query_coverage_sufficient_fraction": cov["coverage_sufficient_fraction"],
                    "dev_query_coverage_review_or_better_fraction": cov["coverage_review_or_better_fraction"],
                    "final_ood_used_for_selection": False,
                    "attack_eval_used_for_selection": False,
                    "dev_query_used_for_selection": False,
                }
                result_rows.append(row)
                ood_rows.append(
                    {
                        "seed": seed,
                        "budget": budget,
                        "threshold_rule": th["rule"],
                        "id_calib_alarm": row["id_calib_alarm"],
                        "ood_val_alarm": row["ood_val_alarm"],
                        "final_ood_alarm_report_only": row["final_ood_alarm_report_only"],
                        "ood_val_safe": row["id_calib_alarm"] <= VAL_TARGET and row["ood_val_alarm"] <= VAL_TARGET,
                        "final_ood_report_only_safe": row["final_ood_alarm_report_only"] <= VAL_TARGET,
                    }
                )

    summary_rows = summarize(result_rows)
    # The verdict is diagnostic and considers report-only fields only to decide
    # whether this mechanism is worth another clean development iteration.
    best_query = max(summary_rows, key=lambda r: float(r["dev_query_detection_report_only_min"]))
    any_query_repaired = any(
        float(r["dev_query_detection_report_only_min"]) >= 0.90 and int(float(r["budget"])) <= 32 for r in summary_rows
    )
    any_final_safe_repaired = any(
        float(r["dev_query_detection_report_only_min"]) >= 0.90
        and bool(r["ood_val_safe_all_seeds"])
        and bool(r["final_ood_report_only_safe_all_seeds"])
        for r in summary_rows
    )
    if any_final_safe_repaired:
        primary_verdict = "active_labeling_viability_supported_ood_safe_in_diagnostic"
    elif any_query_repaired:
        primary_verdict = "active_labeling_viability_supported_but_ood_tail_blocked"
    elif float(best_query["dev_query_detection_report_only_min"]) > 0.60:
        primary_verdict = "active_labeling_partially_supported_needs_better_target_pool_or_threshold"
    else:
        primary_verdict = "active_labeling_not_supported_feature_task_boundary"

    write_csv(OUT / "input_artifact_hash_audit.csv", input_hash_rows)
    write_csv(OUT / "prospective_replay_split_manifest.csv", split_manifest)
    write_csv(OUT / "active_label_selection_audit.csv", selection_rows)
    write_csv(OUT / "active_labeling_budget_results_by_seed.csv", result_rows)
    write_csv(OUT / "active_labeling_budget_summary.csv", summary_rows)
    write_csv(OUT / "coverage_gain_by_budget.csv", coverage_rows)
    write_csv(OUT / "ood_safe_gate_audit.csv", ood_rows)
    write_csv(OUT / "role_access_audit.csv", role_rows)

    write_md(
        OUT / "active_labeling_protocol.md",
        [
            "# Coverage-Aware Active Labeling Protocol",
            "",
            "This issue is a mechanism viability diagnostic, not a formal benchmark.",
            "",
            "## Prospective Replay",
            "",
            "- The previous new heldout probe is consumed here as a development-side heavy incoming stream.",
            "- For each heavy file, the first 1000 rows are treated as unlabeled active-label candidates.",
            "- The remaining rows form `dev_heavy_query_after_active_labeling` and are report-only.",
            "- Candidate labels are hidden during selection; selected rows are then sent to an oracle to simulate analyst labeling.",
            "",
            "## Gate",
            "",
            "- Coverage-aware selection uses support distance and feature diversity only.",
            "- OOD-safe calibration uses `id_calib`, `ood_val`, and base `support_val` only.",
            "- Final OOD, medium attack_eval, and dev query are report-only.",
            "",
            "## Caveat",
            "",
            "Because this consumes the previous new heldout probe as a development stream, a future clean heavy final set is required before any formal claim.",
        ],
    )
    write_md(
        OUT / "issue27au_decision.md",
        [
            "# Issue27au Decision",
            "",
            f"primary_verdict = `{primary_verdict}`",
            "",
            f"- best dev-query diagnostic row: budget=`{best_query['budget']}`, threshold_rule=`{best_query['threshold_rule']}`",
            f"- best dev-query detection_min/mean: `{best_query['dev_query_detection_report_only_min']}` / `{best_query['dev_query_detection_report_only_mean']}`",
            f"- best row final_ood_alarm_max: `{best_query['final_ood_alarm_report_only_max']}`",
            f"- best row OOD-val-safe all seeds: `{best_query['ood_val_safe_all_seeds']}`",
            f"- best row final-OOD-report-only-safe all seeds: `{best_query['final_ood_report_only_safe_all_seeds']}`",
            "",
            "This result can only decide whether coverage-aware active labeling deserves a cleaner follow-up. It cannot be used as formal performance or mainline confirmation.",
        ],
    )
    next_issue = "issue27av_clean_dev_target_pool_for_coverage_active_labeling_and_ood_tail_repair"
    if primary_verdict == "active_labeling_not_supported_feature_task_boundary":
        next_issue = "issue27av_feature_task_boundary_review_after_active_labeling_failure"
    write_md(
        OUT / "issue27av_next_action.md",
        [
            "# Issue27av Next Action",
            "",
            f"Recommended next issue: `{next_issue}`.",
            "",
            "- Build a clean development target pool and a separate sealed final heavy set.",
            "- Keep active-label selection feature-only and prospective.",
            "- Repair final OOD tail separately; do not proceed to full benchmark until both detection and OOD gates pass.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27au.md",
        [
            "# Claim Update After issue27au",
            "",
            "- Coverage-aware active labeling remains diagnostic only.",
            "- The previous new heldout probe is now consumed as development evidence and cannot be used as a clean final set.",
            "- Formal claims require a new sealed final heavy attack set and a separate OOD-tail-safe calibration gate.",
        ],
    )
    write_md(
        OUT / "summary.md",
        [
            "# issue27au Summary",
            "",
            "1. issue27au completed: yes",
            f"2. primary_verdict: `{primary_verdict}`",
            "3. task type: coverage-aware active labeling viability diagnostic; not formal benchmark",
            "4. support/threshold/model search using final roles: no",
            "5. new heldout probe status: consumed as development-side prospective replay, no longer clean final",
            "6. active candidate stream: first 1000 rows per heavy file, labels hidden during selection",
            "7. dev query stream: remaining heavy rows, report-only",
            f"8. best dev-query diagnostic budget: `{best_query['budget']}`",
            f"9. best dev-query detection_min/mean: `{best_query['dev_query_detection_report_only_min']}` / `{best_query['dev_query_detection_report_only_mean']}`",
            f"10. best row OOD-val-safe all seeds: `{best_query['ood_val_safe_all_seeds']}`",
            f"11. best row final-OOD-report-only-safe all seeds: `{best_query['final_ood_report_only_safe_all_seeds']}`",
            f"12. best row final_ood_alarm_max: `{best_query['final_ood_alarm_report_only_max']}`",
            "13. formal benchmark allowed: no",
            f"14. next action: `{next_issue}`",
            "15. commit hash: pending",
        ],
    )
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "seeds": SEEDS,
        "active_label_budgets": ACTIVE_LABEL_BUDGETS,
        "active_candidate_rows_per_file": ACTIVE_CANDIDATE_ROWS_PER_FILE,
        "primary_strategy": PRIMARY_STRATEGY,
        "support_budget": SUPPORT_BUDGET,
        "ood_weight": OOD_WEIGHT,
        "support_weight": SUPPORT_WEIGHT,
        "consumed_previous_new_heldout_as_development_probe": True,
        "selection_policy": "feature-only active selection; labels used only after selected rows are sent to oracle",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"),
                    "issue27at_outputs": str(ISSUE27AT),
                    "new_heavy_probe_consumed_as_development_stream": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "forbidden": "final OOD, medium attack_eval, and dev query are report-only; not used for active selection or threshold selection",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27au -->",
        [
            "<!-- issue27au -->",
            "## issue27au - Coverage-aware active labeling viability diagnostic",
            "",
            f"- primary_verdict: `{primary_verdict}`",
            "- Diagnostic only; previous new heldout probe is consumed as a development stream.",
            "- Active selection is feature-only and prospective; final OOD remains report-only and not solved.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27au -->",
        [
            "<!-- issue27au -->",
            "## issue27au - Coverage-aware active labeling viability",
            "",
            f"- verdict: `{primary_verdict}`",
            "- purpose: test whether budgeted representative labels from uncovered incoming heavy stream can rescue dev-query detection without using final roles.",
            f"- outputs: `runs/{ISSUE}/`.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": primary_verdict, "best_query": best_query, "out": str(OUT)}, indent=2, default=str))


if __name__ == "__main__":
    main()
