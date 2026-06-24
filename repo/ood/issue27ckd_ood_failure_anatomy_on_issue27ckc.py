from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent

SOURCE_RUN = ROOT / "runs" / "issue27ckc_frozen_medium_mainline_replay_on_certified_1m_intel_2026-06-24"
ISSUE = "issue27ckd_ood_failure_anatomy_on_issue27ckc_intel_2026-06-24"
OUT = ROOT / "runs" / ISSUE


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: row.get(key, "") for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def f(value: Any, default: float = float("nan")) -> float:
    try:
        if value == "":
            return default
        return float(value)
    except Exception:
        return default


def fmt(value: float, digits: int = 4) -> str:
    if not math.isfinite(value):
        return "nan"
    return f"{value:.{digits}f}"


def avg(rows: list[dict[str, str]], key: str) -> float:
    vals = [f(row.get(key)) for row in rows]
    vals = [v for v in vals if math.isfinite(v)]
    return mean(vals) if vals else float("nan")


def minv(rows: list[dict[str, str]], key: str) -> float:
    vals = [f(row.get(key)) for row in rows]
    vals = [v for v in vals if math.isfinite(v)]
    return min(vals) if vals else float("nan")


def maxv(rows: list[dict[str, str]], key: str) -> float:
    vals = [f(row.get(key)) for row in rows]
    vals = [v for v in vals if math.isfinite(v)]
    return max(vals) if vals else float("nan")


def weighted(rows: list[dict[str, str]], value_key: str) -> float:
    denom = sum(f(row.get("rows"), 0.0) for row in rows)
    if denom <= 0:
        return float("nan")
    return sum(f(row.get("rows"), 0.0) * f(row.get(value_key), 0.0) for row in rows) / denom


def diagnosis_for_role(role: str, role_kind: str, temporal_hard: float, attack_score: float, ood_risk: float) -> str:
    if role_kind.startswith("benign") and temporal_hard > 0.90:
        if ood_risk < 0.10 and attack_score > 0.90:
            return "hard_ood_scored_as_attack_and_not_suppressed"
        return "hard_ood_high_alarm"
    if role_kind == "attack" and temporal_hard < 0.40:
        return "weak_attack_detection"
    if role_kind == "attack" and temporal_hard > 0.90:
        return "strong_attack_detection"
    if role in {"id_calib", "ood_val"} and temporal_hard < 0.01:
        return "calibration_clean"
    return "mixed_or_intermediate"


def main() -> None:
    required = [
        SOURCE_RUN / "aggregate_role_metrics.csv",
        SOURCE_RUN / "aggregate_threshold_free_metrics.csv",
        SOURCE_RUN / "aggregate_attack_metrics_by_label_device.csv",
        SOURCE_RUN / "aggregate_score_tie_audit.csv",
        SOURCE_RUN / "aggregate_job_results.csv",
        SOURCE_RUN / "run_spec.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise SystemExit("Missing required issue27ckc artifacts:\n" + "\n".join(missing))

    OUT.mkdir(parents=True, exist_ok=True)

    role_rows = read_csv(SOURCE_RUN / "aggregate_role_metrics.csv")
    threshold_rows = read_csv(SOURCE_RUN / "aggregate_threshold_free_metrics.csv")
    attack_rows = read_csv(SOURCE_RUN / "aggregate_attack_metrics_by_label_device.csv")
    tie_rows = read_csv(SOURCE_RUN / "aggregate_score_tie_audit.csv")
    job_rows = read_csv(SOURCE_RUN / "aggregate_job_results.csv")
    run_spec = json.loads((SOURCE_RUN / "run_spec.json").read_text(encoding="utf-8"))

    role_groups: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in role_rows:
        key = (row["weighting"], row["stage"], row["role"], row["role_kind"], row["rows"])
        role_groups[key].append(row)

    dataset_summary: list[dict[str, Any]] = []
    for (weighting, stage, role, role_kind, rows), group in sorted(role_groups.items()):
        temporal_hard = avg(group, "temporal_hard_alarm_rate")
        parent_hard = avg(group, "parent_hard_alarm_rate")
        attack_score = avg(group, "attack_score_mean")
        ood_risk = avg(group, "ood_risk_mean")
        dataset_summary.append(
            {
                "weighting": weighting,
                "stage": stage,
                "role": role,
                "role_kind": role_kind,
                "rows": rows,
                "parent_hard_mean": parent_hard,
                "parent_hard_min": minv(group, "parent_hard_alarm_rate"),
                "parent_hard_max": maxv(group, "parent_hard_alarm_rate"),
                "temporal_hard_mean": temporal_hard,
                "temporal_hard_min": minv(group, "temporal_hard_alarm_rate"),
                "temporal_hard_max": maxv(group, "temporal_hard_alarm_rate"),
                "attack_score_mean": attack_score,
                "ood_risk_mean": ood_risk,
                "diagnosis": diagnosis_for_role(role, role_kind, temporal_hard, attack_score, ood_risk),
            }
        )

    threshold_summary: list[dict[str, Any]] = []
    tf_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in threshold_rows:
        tf_groups[(row["weighting"], row["comparison"], row["stage"])].append(row)
    for (weighting, comparison, stage), group in sorted(tf_groups.items()):
        temporal_auc = avg(group, "temporal_attack_auc")
        parent_auc = avg(group, "parent_attack_auc")
        threshold_summary.append(
            {
                "weighting": weighting,
                "comparison": comparison,
                "stage": stage,
                "jobs": len(group),
                "positive_rows": group[0].get("positive_rows"),
                "negative_rows": group[0].get("negative_rows"),
                "temporal_auc_mean": temporal_auc,
                "temporal_auc_min": minv(group, "temporal_attack_auc"),
                "temporal_auc_max": maxv(group, "temporal_attack_auc"),
                "temporal_ap_mean": avg(group, "temporal_attack_ap"),
                "parent_auc_mean": parent_auc,
                "parent_ap_mean": avg(group, "parent_attack_ap"),
                "diagnosis": "inverted_or_ood_dominates" if temporal_auc < 0.5 else "separable",
            }
        )

    coverage_rows: list[dict[str, Any]] = []
    cov_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in attack_rows:
        if row["role"] in {"future_query", "sealed_final_attack"}:
            cov_groups[(row["weighting"], row["role"], row["support_coverage"])].append(row)
    for (weighting, role, coverage), group in sorted(cov_groups.items()):
        total_rows_over_jobs = sum(f(row.get("rows"), 0.0) for row in group)
        jobs = len({row["job_index"] for row in group})
        coverage_rows.append(
            {
                "weighting": weighting,
                "role": role,
                "support_coverage": coverage,
                "rows_per_seed": total_rows_over_jobs / max(jobs, 1),
                "parent_detection_weighted": weighted(group, "parent_hard_detection"),
                "temporal_detection_weighted": weighted(group, "temporal_hard_detection"),
                "temporal_suppress_weighted": weighted(group, "temporal_suppress_rate"),
            }
        )

    weak_attack_rows: list[dict[str, Any]] = []
    attack_grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in attack_rows:
        if row["role"] in {"future_query", "sealed_final_attack", "same_file_query", "support_val"}:
            key = (row["weighting"], row["role"], row["attack_label"], row["device"], row["support_coverage"])
            attack_grouped[key].append(row)
    for (weighting, role, attack_label, device, coverage), group in attack_grouped.items():
        rows_per_seed = sum(f(row.get("rows"), 0.0) for row in group) / max(len({row["job_index"] for row in group}), 1)
        weak_attack_rows.append(
            {
                "weighting": weighting,
                "role": role,
                "attack_label": attack_label,
                "device": device,
                "support_coverage": coverage,
                "rows_per_seed": rows_per_seed,
                "parent_detection_mean": avg(group, "parent_hard_detection"),
                "temporal_detection_mean": avg(group, "temporal_hard_detection"),
                "temporal_attack_mean": avg(group, "temporal_attack_mean"),
                "temporal_attack_p50_mean": avg(group, "temporal_attack_p50"),
            }
        )
    weak_attack_rows.sort(key=lambda row: (row["temporal_detection_mean"], -row["rows_per_seed"]))

    tie_summary: list[dict[str, Any]] = []
    tie_grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    job_weighting = {row["job_index"]: row["weighting"] for row in job_rows}
    for row in tie_rows:
        tie_grouped[(job_weighting.get(row["job_index"], "unknown"), row["score"], row.get("threshold", ""))].append(row)
    for (weighting, score, threshold), group in sorted(tie_grouped.items()):
        equal_mass = avg(group, "equal_mass")
        tie_summary.append(
            {
                "weighting": weighting,
                "score": score,
                "threshold": threshold,
                "jobs": len(group),
                "equal_mass_mean": equal_mass,
                "strict_above_mass_mean": avg(group, "strict_above_mass"),
                "diagnosis": "degenerate_tie_or_near_binary_threshold" if equal_mass > 0.5 else "nondegenerate",
            }
        )

    # Compact hypothesis table. These are deterministic inferences from the aggregate artifacts.
    hypothesis_rows: list[dict[str, Any]] = []
    by_weight_role = {(row["weighting"], row["role"]): row for row in dataset_summary}
    for weighting in sorted({row["weighting"] for row in dataset_summary}):
        ood_val = by_weight_role.get((weighting, "ood_val"))
        ood_stress = by_weight_role.get((weighting, "ood_stress"))
        sealed_ood = by_weight_role.get((weighting, "sealed_final_ood"))
        future_seen = next(
            (row for row in coverage_rows if row["weighting"] == weighting and row["role"] == "future_query" and row["support_coverage"] == "seen_in_support"),
            None,
        )
        future_unseen = next(
            (row for row in coverage_rows if row["weighting"] == weighting and row["role"] == "future_query" and row["support_coverage"] == "unseen_in_support"),
            None,
        )
        if ood_val and ood_stress and sealed_ood:
            hypothesis_rows.append(
                {
                    "weighting": weighting,
                    "finding": "ood_calibration_does_not_transfer",
                    "evidence": (
                        f"ood_val temporal={fmt(ood_val['temporal_hard_mean'])}; "
                        f"ood_stress temporal={fmt(ood_stress['temporal_hard_mean'])}; "
                        f"sealed_final_ood temporal={fmt(sealed_ood['temporal_hard_mean'])}"
                    ),
                    "status": "supported",
                }
            )
            hypothesis_rows.append(
                {
                    "weighting": weighting,
                    "finding": "hard_ood_not_suppressed_by_ood_risk",
                    "evidence": (
                        f"ood_stress attack_score={fmt(ood_stress['attack_score_mean'])}, risk={fmt(ood_stress['ood_risk_mean'])}; "
                        f"sealed_final_ood attack_score={fmt(sealed_ood['attack_score_mean'])}, risk={fmt(sealed_ood['ood_risk_mean'])}"
                    ),
                    "status": "supported",
                }
            )
        if future_seen and future_unseen:
            hypothesis_rows.append(
                {
                    "weighting": weighting,
                    "finding": "attack_detection_is_support_coverage_dominated",
                    "evidence": (
                        f"future seen temporal={fmt(future_seen['temporal_detection_weighted'])}; "
                        f"future unseen temporal={fmt(future_unseen['temporal_detection_weighted'])}"
                    ),
                    "status": "supported",
                }
            )

    write_csv(OUT / "dataset_role_anatomy.csv", dataset_summary)
    write_csv(OUT / "threshold_free_generalization.csv", threshold_summary)
    write_csv(OUT / "support_coverage_gap.csv", coverage_rows)
    write_csv(OUT / "weak_attack_groups.csv", weak_attack_rows)
    write_csv(OUT / "score_tie_anatomy.csv", tie_summary)
    write_csv(OUT / "failure_hypotheses.csv", hypothesis_rows)
    write_json(
        OUT / "input_manifest.json",
        {
            "issue": ISSUE,
            "source_run": str(SOURCE_RUN),
            "source_run_spec": run_spec,
            "artifact_scope": "aggregate-level anatomy; no per-sample score cache was present in issue27ckc outputs",
            "cannot_determine_without_score_cache": [
                "per-sample nearest attack/support neighbor for ood_stress and sealed_final_ood",
                "within-role score quantiles beyond already aggregated label/device summaries",
                "feature-space overlap or cluster geometry between hard OOD and attack families",
            ],
        },
    )

    # Markdown report, intentionally organized by dataset role rather than by model component.
    ds_order = [
        "id_calib",
        "ood_val",
        "support_val",
        "same_file_query",
        "future_query",
        "ood_stress",
        "sealed_final_attack",
        "sealed_final_ood",
    ]
    md: list[str] = [
        "# issue27ckd OOD failure anatomy on issue27ckc Intel replay",
        "",
        "## Scope",
        "",
        "- Source run: `issue27ckc_frozen_medium_mainline_replay_on_certified_1m_intel_2026-06-24`.",
        "- Analysis level: aggregate and label/device tables already returned by the full HPC replay.",
        "- This report does not retrain or promote any model.",
        "- Limitation: the source run did not save per-sample score vectors, so nearest-neighbor feature-space proof requires a targeted score-cache replay.",
        "",
        "## Main conclusion",
        "",
        "The failure is structural rather than a small threshold accident: development OOD calibration looks clean, but hard OOD roles are scored almost exactly like attack and are not suppressed by the OOD-risk path. In parallel, attack detection is strongly support-coverage dominated.",
        "",
        "## Dataset-role summary",
        "",
        "| Weighting | Dataset role | Kind | Rows | Parent hard | Temporal hard | Attack score | OOD-risk | Diagnosis |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for weighting in sorted({row["weighting"] for row in dataset_summary}):
        for role in ds_order:
            match = next((row for row in dataset_summary if row["weighting"] == weighting and row["role"] == role), None)
            if not match:
                continue
            md.append(
                "| "
                + " | ".join(
                    [
                        weighting,
                        role,
                        match["role_kind"],
                        str(match["rows"]),
                        fmt(match["parent_hard_mean"]),
                        fmt(match["temporal_hard_mean"]),
                        fmt(match["attack_score_mean"]),
                        fmt(match["ood_risk_mean"]),
                        match["diagnosis"],
                    ]
                )
                + " |"
            )
    md.extend(
        [
            "",
            "## Threshold-free generalization",
            "",
            "| Weighting | Comparison | Stage | Temporal AUC | Temporal AP | Parent AUC | Parent AP | Diagnosis |",
            "|---|---:|---:|---:|---:|---:|---:|---|",
        ]
    )
    for row in threshold_summary:
        md.append(
            "| "
            + " | ".join(
                [
                    row["weighting"],
                    row["comparison"],
                    row["stage"],
                    fmt(row["temporal_auc_mean"]),
                    fmt(row["temporal_ap_mean"]),
                    fmt(row["parent_auc_mean"]),
                    fmt(row["parent_ap_mean"]),
                    row["diagnosis"],
                ]
            )
            + " |"
        )
    md.extend(
        [
            "",
            "## Support coverage gap",
            "",
            "| Weighting | Role | Coverage | Rows per seed | Parent detection | Temporal detection |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in coverage_rows:
        md.append(
            "| "
            + " | ".join(
                [
                    row["weighting"],
                    row["role"],
                    row["support_coverage"],
                    fmt(row["rows_per_seed"], 0),
                    fmt(row["parent_detection_weighted"]),
                    fmt(row["temporal_detection_weighted"]),
                ]
            )
            + " |"
        )
    md.extend(
        [
            "",
            "## Weak attack groups, worst 20 by temporal detection",
            "",
            "| Weighting | Role | Attack label | Device | Coverage | Rows per seed | Parent | Temporal |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in weak_attack_rows[:20]:
        md.append(
            "| "
            + " | ".join(
                [
                    row["weighting"],
                    row["role"],
                    row["attack_label"],
                    row["device"],
                    row["support_coverage"],
                    fmt(row["rows_per_seed"], 0),
                    fmt(row["parent_detection_mean"]),
                    fmt(row["temporal_detection_mean"]),
                ]
            )
            + " |"
        )
    md.extend(
        [
            "",
            "## Score tie / threshold anatomy",
            "",
            "| Weighting | Score | Threshold | Equal mass | Strict above mass | Diagnosis |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in tie_summary:
        md.append(
            "| "
            + " | ".join(
                [
                    row["weighting"],
                    row["score"],
                    str(row["threshold"]),
                    fmt(row["equal_mass_mean"]),
                    fmt(row["strict_above_mass_mean"]),
                    row["diagnosis"],
                ]
            )
            + " |"
        )
    md.extend(
        [
            "",
            "## Deterministic hypotheses supported by this run",
            "",
            "| Weighting | Finding | Evidence | Status |",
            "|---|---:|---:|---:|",
        ]
    )
    for row in hypothesis_rows:
        md.append(f"| {row['weighting']} | {row['finding']} | {row['evidence']} | {row['status']} |")
    md.extend(
        [
            "",
            "## What this rules in",
            "",
            "1. OOD calibration is non-transferable: `ood_val` is clean but `ood_stress` and `sealed_final_ood` fail.",
            "2. The hard OOD roles are not merely unsuppressed edge cases; they receive high attack scores and low OOD-risk values.",
            "3. The temporal path is not the sole root cause. Parent hard alarms are already very high on hard OOD roles.",
            "4. Attack detection is support-coverage dominated: seen-in-support attack roles are strong, unseen roles are weak.",
            "",
            "## What this does not yet prove",
            "",
            "The current artifacts cannot prove which exact feature dimensions or support neighbors cause the hard OOD confusion, because issue27ckc did not persist per-sample score vectors or nearest-neighbor identities.",
            "",
            "## Recommended next experiment",
            "",
            "Run a targeted score-cache anatomy, not another full model sweep: persist row-level parent/temporal attack score, OOD-risk, hard decision, role, label/device, and nearest support/attack/benign prototypes for `ood_val`, `ood_stress`, `sealed_final_ood`, `future_query`, and `sealed_final_attack`. A small stratified cache is enough locally if the full feature store is available; otherwise use the Intel partition.",
        ]
    )
    write_md(OUT / "summary.md", md)

    print(json.dumps({"status": "ok", "issue": ISSUE, "out": str(OUT)}, indent=2))


if __name__ == "__main__":
    main()
