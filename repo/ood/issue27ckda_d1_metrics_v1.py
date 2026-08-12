#!/usr/bin/env python3
"""Compile CKDA D1 one-shot metrics, fixed gates, and bootstrap evidence."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core


FROZEN_OOD_RATES = {
    "iotsim-hydraulic-system": 0.4570,
    "iotsim-ip-camera-street": 0.0810,
    "iotsim-predictive-maintenance": 0.575889,
    "iotsim-stream-consumer": 0.2970,
}
REPORT_FAMILIES = {
    "C&C Communication": 179,
    "CoAP Amplification": 320,
    "File Download": 2569,
    "Ingress Tool Transfer": 10069,
    "Merlin C&C Communication": 9926,
    "Merlin ICMP Flooding": 19730,
    "Merlin TCP Flooding": 27722,
    "Merlin UDP Flooding": 10298,
    "Mirai C&C Communication": 369,
    "Mirai GRE Flooding": 27722,
    "Mirai TCP Flooding": 27721,
    "Mirai UDP Flooding": 27722,
    "Reporting": 167,
    "TCP Scan": 39711,
    "Telnet Brute Force": 39712,
    "UDP Scan": 113,
}
OOD_ROLE_TO_POOL = {
    "ood_val": "iotsim-hydraulic-system",
    "sealed_final_ood": "iotsim-ip-camera-street",
    "aux_report": "iotsim-predictive-maintenance",
    "ood_stress": "iotsim-stream-consumer",
}
PROBES = ("G0", "P1", "P2")


def binary_auc(labels: np.ndarray, scores: np.ndarray) -> Tuple[float, float]:
    from sklearn.metrics import average_precision_score, roc_auc_score

    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    if bool(np.any(np.isnan(scores))) or bool(np.any(np.isneginf(scores))):
        raise RuntimeError("AUC scores contain NaN or negative infinity")
    if bool(np.any(np.isposinf(scores))):
        finite = scores[np.isfinite(scores)]
        ceiling = float(finite.max()) if len(finite) else 0.0
        scores = scores.copy()
        scores[np.isposinf(scores)] = np.nextafter(ceiling, math.inf)
    if sorted(np.unique(labels).tolist()) != [0, 1]:
        raise RuntimeError("AUC sample lacks both classes")
    return float(roc_auc_score(labels, scores)), float(average_precision_score(labels, scores))


def percentile_interval(values: Sequence[float]) -> Tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    return float(np.quantile(array, 0.025)), float(np.quantile(array, 0.975))


def cluster_auc_bootstrap(
    frame: pd.DataFrame,
    cluster_column: str,
    reps: int = 2000,
    seed: int = core.BOOTSTRAP_SEED,
) -> Dict[str, object]:
    if int(reps) != 2000 or int(seed) != core.BOOTSTRAP_SEED:
        raise RuntimeError("bootstrap identity drift")
    cluster_codes, cluster_values = pd.factorize(frame[cluster_column].astype(str), sort=True)
    cluster_count = len(cluster_values)
    if cluster_count < 1:
        raise RuntimeError("empty bootstrap cluster set")
    labels = frame["binary_auc_label"].to_numpy(dtype=np.int64)
    scores = frame["score"].to_numpy(dtype=np.float64)
    rng = np.random.default_rng(seed)
    roc_values = []
    pr_values = []
    unavailable = 0
    normalized_scores = scores.copy()
    if bool(np.any(np.isposinf(normalized_scores))):
        finite = normalized_scores[np.isfinite(normalized_scores)]
        ceiling = float(finite.max()) if len(finite) else 0.0
        normalized_scores[np.isposinf(normalized_scores)] = np.nextafter(ceiling, math.inf)
    order = np.argsort(-normalized_scores, kind="mergesort")
    ordered_scores = normalized_scores[order]
    ordered_labels = labels[order]
    ordered_clusters = cluster_codes[order]
    starts = np.r_[0, np.flatnonzero(ordered_scores[1:] != ordered_scores[:-1]) + 1]

    for _rep in range(reps):
        chosen = rng.integers(0, cluster_count, size=cluster_count)
        multiplicity = np.bincount(chosen, minlength=cluster_count).astype(np.float64)
        row_weight = multiplicity[ordered_clusters]
        positive = np.add.reduceat(row_weight * ordered_labels, starts)
        negative = np.add.reduceat(row_weight * (1 - ordered_labels), starts)
        positive_total = float(positive.sum())
        negative_total = float(negative.sum())
        if positive_total <= 0.0 or negative_total <= 0.0:
            unavailable += 1
            continue
        true_positive = np.cumsum(positive)
        false_positive = np.cumsum(negative)
        tpr = np.r_[0.0, true_positive / positive_total]
        fpr = np.r_[0.0, false_positive / negative_total]
        roc = float(np.sum((tpr[1:] + tpr[:-1]) * (fpr[1:] - fpr[:-1]) * 0.5))
        precision = true_positive / np.maximum(true_positive + false_positive, 1e-300)
        pr = float(np.sum(precision * positive / positive_total))
        roc_values.append(roc)
        pr_values.append(pr)
    if len(roc_values) < int(0.95 * reps):
        return {
            "status": "UNAVAILABLE_INSUFFICIENT_TWO_CLASS_REPLICATES",
            "cluster_column": cluster_column,
            "reps_requested": reps,
            "reps_available": len(roc_values),
            "reps_unavailable": unavailable,
        }
    roc_low, roc_high = percentile_interval(roc_values)
    pr_low, pr_high = percentile_interval(pr_values)
    return {
        "status": "PASS",
        "cluster_column": cluster_column,
        "reps_requested": reps,
        "reps_available": len(roc_values),
        "reps_unavailable": unavailable,
        "roc_auc_low": roc_low,
        "roc_auc_high": roc_high,
        "pr_auc_low": pr_low,
        "pr_auc_high": pr_high,
    }


def bool_column(values: pd.Series) -> np.ndarray:
    mapped = values.astype(str).str.strip().str.lower().map({"true": True, "false": False, "0": False, "1": True})
    if mapped.isna().any():
        raise RuntimeError("invalid boolean values")
    return mapped.to_numpy(dtype=np.bool_)


def probe_metrics(frame: pd.DataFrame, probe: str) -> Tuple[Dict[str, object], List[Dict[str, object]]]:
    part = frame.loc[frame["probe_id"].eq(probe)].copy().reset_index(drop=True)
    if len(part) != 262_050 or part["uid"].duplicated().any():
        raise RuntimeError("probe report denominator/UID drift")
    if bool_column(part["review"]).any():
        raise RuntimeError("review count is nonzero")
    hard = pd.to_numeric(part["hard"], errors="raise").to_numpy(dtype=np.int64)
    labels = pd.to_numeric(part["label_metric_only"], errors="raise").to_numpy(dtype=np.int64)
    attack = labels == 1
    if int(attack.sum()) != core.REPORT_ATTACK_ROWS:
        raise RuntimeError("attack report denominator drift")
    future = part["role"].eq("future_query").to_numpy()
    if int(future.sum()) != core.FUTURE_QUERY_ROWS:
        raise RuntimeError("future report denominator drift")
    overall_recall = float(hard[attack].mean())
    c1 = pd.to_numeric(part["c1_hard"], errors="raise").to_numpy(dtype=np.int64)
    c1_recall = float(c1[attack].mean())
    family_rows = []
    family_deltas: Dict[str, float] = {}
    attack_part = part.loc[attack].copy()
    actual_counts = attack_part.groupby("attack_family", sort=True).size().astype(int).to_dict()
    if actual_counts != REPORT_FAMILIES:
        raise RuntimeError("16-family dictionary/count drift")
    for family, expected in REPORT_FAMILIES.items():
        mask = attack_part["attack_family"].eq(family).to_numpy()
        probe_recall = float(pd.to_numeric(attack_part.loc[mask, "hard"]).mean())
        c1_family = float(pd.to_numeric(attack_part.loc[mask, "c1_hard"]).mean())
        delta = 100.0 * (probe_recall - c1_family)
        family_deltas[family] = delta
        family_rows.append({
            "probe_id": probe, "attack_family": family, "rows": expected,
            "probe_recall": probe_recall, "c1_recall": c1_family, "delta_pp": delta,
        })
    ood_rates: Dict[str, float] = {}
    ood_rows = []
    for role, pool in OOD_ROLE_TO_POOL.items():
        mask = part["role"].eq(role).to_numpy()
        if int(mask.sum()) not in {3000, 9000}:
            raise RuntimeError("OOD pool denominator drift: %s" % pool)
        rate = float(hard[mask].mean())
        ood_rates[pool] = rate
        ood_rows.append({
            "probe_id": probe, "ood_pool": pool, "rows": int(mask.sum()),
            "probe_hard_rate": rate, "frozen_ckbq_hard_rate": FROZEN_OOD_RATES[pool],
            "delta_pp": 100.0 * (rate - FROZEN_OOD_RATES[pool]),
        })
    evidence = core.GateEvidence(
        support_hard=int(hard[part["role"].eq("support_val").to_numpy()].sum()),
        overall_attack_rows=int(attack.sum()),
        overall_recall=overall_recall,
        c1_overall_recall=c1_recall,
        future_rows=int(future.sum()),
        future_recall=float(hard[future].mean()),
        family_deltas_pp=family_deltas,
        ood_rates=ood_rates,
        frozen_ood_rates=FROZEN_OOD_RATES,
        review_count=0,
        contract_gates_pass=True,
    )
    actionable, checks = core.actionable_gate(evidence)
    auc_mask = future.copy()
    auc_mask |= part["role"].isin(OOD_ROLE_TO_POOL).to_numpy()
    auc_frame = part.loc[auc_mask, ["uid", "role", "source_group", "score"]].copy().reset_index(drop=True)
    auc_frame["binary_auc_label"] = auc_frame["role"].eq("future_query").astype(np.int64)
    roc_auc, pr_auc = binary_auc(auc_frame["binary_auc_label"].to_numpy(), auc_frame["score"].to_numpy())
    source_bootstrap = cluster_auc_bootstrap(auc_frame, "source_group")
    baseline_rows = []
    for name, column in (
        ("C1", "c1_hard"),
        ("FrozenCKBQ", "frozen_ckbq_hard"),
        ("M7", "m7_hard"),
    ):
        baseline_hard = pd.to_numeric(part[column], errors="raise").to_numpy(dtype=np.int64)
        baseline_rows.append({
            "row_kind": "same_denominator_baseline",
            "probe_id": probe,
            "baseline_id": name,
            "overall_attack_rows": int(attack.sum()),
            "overall_attack_recall": float(baseline_hard[attack].mean()),
            "future_rows": int(future.sum()),
            "future_recall": float(baseline_hard[future].mean()),
            "ood_macro": float(np.mean([
                baseline_hard[part["role"].eq(role).to_numpy()].mean()
                for role in OOD_ROLE_TO_POOL
            ])),
        })
    attack_sessions = part.loc[attack].groupby("session_id", sort=False)["hard"].max()
    benign_sessions = part.loc[~attack].groupby(["source_group", "session_id"], sort=False)["hard"].max()
    first_alert_rows = []
    for session_id, session in part.loc[attack].groupby("session_id", sort=False):
        ordered = session.sort_values(["timestamp_epoch", "event_position", "uid"], kind="mergesort")
        alerted = ordered.loc[pd.to_numeric(ordered["hard"], errors="raise").eq(1)]
        if len(alerted):
            first_alert_rows.append(float(alerted.iloc[0]["timestamp_epoch"] - ordered.iloc[0]["timestamp_epoch"]))
    metrics = {
        "probe_id": probe,
        "support_hard": evidence.support_hard,
        "overall_attack_rows": evidence.overall_attack_rows,
        "overall_attack_recall": overall_recall,
        "c1_overall_attack_recall": c1_recall,
        "future_rows": evidence.future_rows,
        "future_recall": evidence.future_recall,
        "ood_macro": float(np.mean(list(ood_rates.values()))),
        "roc_auc": roc_auc,
        "pr_auc": pr_auc,
        "actionable": actionable,
        "gate_checks": checks,
        "source_bootstrap": source_bootstrap,
        "weak_source_bootstrap": (
            source_bootstrap.get("status") == "PASS" and float(source_bootstrap["roc_auc_low"]) > 0.5
        ),
        "session_detection_rate": float(attack_sessions.mean()),
        "false_alert_sessions_per_source_mean": float(
            benign_sessions.groupby(level=0).sum().mean() if len(benign_sessions) else 0.0
        ),
        "time_to_first_alert_seconds_median": (
            float(np.median(first_alert_rows)) if first_alert_rows else None
        ),
    }
    return metrics, family_rows + ood_rows + baseline_rows


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    score_path = Path(args.scores)
    frame = pd.read_csv(score_path)
    expected_rows = 3 * 262_050
    if len(frame) != expected_rows or set(frame["probe_id"]) != set(PROBES):
        raise RuntimeError("report score table identity drift")
    metadata = pd.read_csv(args.metadata)
    if len(metadata) != 262_050 or metadata["uid"].duplicated().any():
        raise RuntimeError("session metadata denominator/UID drift")
    frame = frame.merge(metadata[["uid", "session_id", "timestamp_epoch", "event_position"]], on="uid", validate="many_to_one")
    if frame[["session_id", "timestamp_epoch", "event_position"]].isna().any().any():
        raise RuntimeError("report session metadata join produced missing values")
    finite_or_declared_missing = np.isfinite(pd.to_numeric(frame["score"], errors="raise").to_numpy())
    finite_or_declared_missing |= (
        frame["probe_id"].eq("G0").to_numpy()
        & pd.to_numeric(frame["missing"], errors="raise").eq(1).to_numpy()
        & np.isposinf(pd.to_numeric(frame["score"], errors="raise").to_numpy())
    )
    if not bool(finite_or_declared_missing.all()):
        raise RuntimeError("report score table has invalid nonfinite values")
    metrics = {}
    tables = []
    for probe in PROBES:
        metrics[probe], rows = probe_metrics(frame, probe)
        auc_mask = frame["probe_id"].eq(probe) & (
            frame["role"].eq("future_query") | frame["role"].isin(OOD_ROLE_TO_POOL)
        )
        session_frame = frame.loc[auc_mask, ["session_id", "role", "score"]].copy().reset_index(drop=True)
        session_frame["binary_auc_label"] = session_frame["role"].eq("future_query").astype(np.int64)
        metrics[probe]["session_bootstrap"] = cluster_auc_bootstrap(session_frame, "session_id")
        tables.extend(rows)
    state = core.final_state(
        bool(metrics["P1"]["actionable"]),
        bool(metrics["P2"]["actionable"]),
        bool(metrics["G0"]["actionable"]),
        [
            float(value["source_bootstrap"].get("roc_auc_low", -1.0))
            for value in metrics.values()
        ],
        completed=True,
        engineering_failure=False,
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    core.atomic_csv(out / "ckda_d1_family_ood_and_baseline_metrics.csv", tables)
    first_probe = frame.loc[frame["probe_id"].eq("G0")].copy()
    coverage = []
    for (role, source), part in first_probe.groupby(["role", "source_group"], sort=True):
        missing = pd.to_numeric(part["missing"], errors="raise").to_numpy(dtype=np.int64)
        coverage.append({
            "role": str(role),
            "source_group": str(source),
            "target_rows": len(part),
            "embedded_rows": int((missing == 0).sum()),
            "missing_rows": int((missing == 1).sum()),
            "duplicate_rows": 0,
            "nonfinite_nonmissing_rows": 0,
        })
    core.atomic_csv(out / "ckda_d1_target_coverage_by_role_source.csv", coverage)
    bootstrap_rows = []
    for probe in PROBES:
        for kind in ("source_bootstrap", "session_bootstrap"):
            value = metrics[probe][kind]
            bootstrap_rows.append({
                "probe_id": probe,
                "bootstrap_kind": kind,
                **value,
            })
    core.atomic_csv(out / "ckda_d1_bootstrap_intervals.csv", bootstrap_rows)
    verdict = {
        "status": "PASS",
        "verdict": state,
        "go_d2": state == core.ACTIONABLE,
        "contract_sha256": core.CONTRACT_SHA256,
        "candidate_id": str(args.candidate),
        "report_scores_sha256": core.sha256_file(score_path),
        "session_metadata_sha256": core.sha256_file(args.metadata),
        "coverage_sha256": core.sha256_file(out / "ckda_d1_target_coverage_by_role_source.csv"),
        "bootstrap_intervals_sha256": core.sha256_file(out / "ckda_d1_bootstrap_intervals.csv"),
        "metrics": metrics,
        "bootstrap_reps": 2000,
        "bootstrap_seed": core.BOOTSTRAP_SEED,
        "final_files_opened": 0,
    }
    core.atomic_json(out / "ckda_d1_verdict.json", verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--candidate", choices=("I1", "E3"), required=True)
    result.add_argument("--scores", type=Path, required=True)
    result.add_argument("--metadata", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
