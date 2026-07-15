"""CKBN: frozen-fit separability diagnosis for the persistent stream canary.

This is a diagnostic, not a detector candidate.  It reuses CKBL's causal
frontend bundles and group-balanced HistGB information probe.  The probe and
its threshold see legal fit data only.  The already-used stream and hydraulic
development canaries are scored only after the model is frozen, alongside a
family-stratified future-attack report cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import sklearn


OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckbl_frontend_observability_audit_v1 as ckbl  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbn_stream_separability_diagnostic_v1_2026-07-15"
DEFAULT_OUT = cko.ROOT / "runs" / f"{ISSUE}_local_seed27"
SEED = 27
STREAM = "iotsim-stream-consumer"
HYDRAULIC = "iotsim-hydraulic-system"
COOLER = "iotsim-cooler-motor"
FORBIDDEN = {STREAM, HYDRAULIC, COOLER}
REPORT_BUNDLES = ("TGN9_exact", "Current20", "CompactProcess69", "C1_207_upper_bound")


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def dump_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_rank(source: str, recorded_index: int, seed: int, stratum: str) -> str:
    payload = f"{seed}|{stratum}|{source}|{int(recorded_index)}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def make_report_part(
    frame_by_role: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    class_name: str,
    label: int,
    cap: int,
    seed: int,
    device_family: str | None = None,
    per_attack_family: bool = False,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frame = frame_by_role[role]
    if phase == "all":
        work = frame.copy()
    else:
        work = frame.loc[frame["phase"].astype(str).eq(str(phase))].copy()
    if device_family is not None:
        work = work.loc[work["device_family"].astype(str).eq(device_family)].copy()
    work["recorded_index"] = pd.to_numeric(work["recorded_index"], errors="coerce").fillna(-1).astype(np.int64)
    work = work.loc[work["recorded_index"].ge(0)].copy()
    work["role_row"] = work.index.to_numpy(dtype=np.int64)
    work["role"] = role
    work["class_name"] = class_name
    work["y"] = int(label)
    if int(label) == 0:
        work["attack_label"] = "benign"
    else:
        work["attack_label"] = work["attack_label"].astype(str)
    work["report_stratum"] = work["attack_label"] if per_attack_family else (device_family or class_name)
    before = work.groupby("report_stratum", sort=True).size().to_dict()
    selected: list[pd.DataFrame] = []
    audit: list[dict[str, Any]] = []
    for stratum, part in work.groupby("report_stratum", sort=True):
        part = part.copy()
        part["stable_rank"] = [
            stable_rank(str(source), int(recorded), int(seed), str(stratum))
            for source, recorded in zip(part["source_group"], part["recorded_index"])
        ]
        part = part.sort_values(["stable_rank", "source_group", "recorded_index"], kind="stable").head(int(cap))
        selected.append(part)
        audit.append(
            {
                "scope": class_name,
                "role": role,
                "phase": phase,
                "stratum": str(stratum),
                "eligible_rows": int(before[stratum]),
                "selected_rows": int(len(part)),
                "cap": int(cap),
                "selection": "stable_sha256_source_recorded_index",
                "labels_used_for_fit_threshold_or_features": 0,
            }
        )
    if not selected:
        raise RuntimeError(f"empty report cohort: {class_name}")
    out = pd.concat(selected, ignore_index=True)
    out["row_uid"] = [f"{role}:{int(row)}" for row in out["role_row"]]
    if out["row_uid"].duplicated().any():
        raise RuntimeError(f"duplicate report role-row UID: {class_name}")
    return out.reset_index(drop=True), audit


def assert_zero_use(fit: pd.DataFrame, reports: dict[str, pd.DataFrame]) -> pd.DataFrame:
    fit_families = set(fit["device_family"].astype(str))
    collision = sorted(fit_families & FORBIDDEN)
    if collision:
        raise RuntimeError(f"forbidden report family entered fit: {collision}")
    fit_uids = set(fit["row_uid"].astype(str))
    rows: list[dict[str, Any]] = []
    for family in sorted(FORBIDDEN):
        rows.append(
            {
                "family": family,
                "fit_rows_used": int(fit["device_family"].astype(str).eq(family).sum()),
                "threshold_rows_used": int(fit["device_family"].astype(str).eq(family).sum()),
                "normalization_rows_used": 0,
                "feature_selection_rows_used": 0,
                "pass": family not in fit_families,
            }
        )
    for scope, table in reports.items():
        overlap = sorted(fit_uids & set(table["row_uid"].astype(str)))
        if overlap:
            raise RuntimeError(f"report rows overlap fit rows in {scope}: {overlap[:8]}")
    return pd.DataFrame(rows)


def quantiles(scores: np.ndarray) -> dict[str, float]:
    return {
        "score_min": float(np.min(scores)),
        "score_q01": float(np.quantile(scores, 0.01)),
        "score_q05": float(np.quantile(scores, 0.05)),
        "score_q50": float(np.quantile(scores, 0.50)),
        "score_q95": float(np.quantile(scores, 0.95)),
        "score_q99": float(np.quantile(scores, 0.99)),
        "score_max": float(np.max(scores)),
        "score_mean": float(np.mean(scores)),
    }


def distribution_row(
    scope: str,
    bundle: str,
    meta: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "scope": scope,
        "bundle": bundle,
        "rows": int(len(meta)),
        "sources": int(meta["source_group"].nunique()),
        "attack_families": int(meta.loc[meta["y"].eq(1), "attack_label"].nunique()),
        "threshold": float(threshold),
        "hard_rate": float(np.mean(scores >= threshold)) if np.isfinite(threshold) else float("nan"),
    }
    row.update(quantiles(scores))
    return row


def pairwise_rows(
    canary_name: str,
    canary_meta: pd.DataFrame,
    canary_scores: np.ndarray,
    attack_meta: pd.DataFrame,
    attack_scores: np.ndarray,
    bundle: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, positions in attack_meta.groupby("attack_label", sort=True).indices.items():
        pos = np.asarray(positions, dtype=np.int64)
        y = np.concatenate([np.zeros(len(canary_scores), dtype=np.int64), np.ones(len(pos), dtype=np.int64)])
        scores = np.concatenate([canary_scores, attack_scores[pos]])
        auc, ap = ckbl.safe_auc(y, scores)
        part = attack_meta.iloc[pos]
        rows.append(
            {
                "canary": canary_name,
                "bundle": bundle,
                "attack_family": str(family),
                "canary_rows": int(len(canary_meta)),
                "canary_sources": int(canary_meta["source_group"].nunique()),
                "attack_rows": int(len(part)),
                "attack_sources": int(part["source_group"].nunique()),
                "auroc": auc,
                "average_precision": ap,
                "attack_minus_canary_score_mean": float(np.mean(attack_scores[pos]) - np.mean(canary_scores)),
                "packet_independence_claim": False,
            }
        )
    return rows


def hard_attack_rows(
    attack_meta: pd.DataFrame,
    scores: np.ndarray,
    threshold: float,
    support_counts: dict[str, int],
    bundle: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for family, positions in attack_meta.groupby("attack_label", sort=True).indices.items():
        pos = np.asarray(positions, dtype=np.int64)
        rows.append(
            {
                "bundle": bundle,
                "attack_family": str(family),
                "rows": int(len(pos)),
                "sources": int(attack_meta.iloc[pos]["source_group"].nunique()),
                "threshold": float(threshold),
                "hard_recall": float(np.mean(scores[pos] >= threshold)) if np.isfinite(threshold) else float("nan"),
                "support_train_rows": int(support_counts.get(str(family), 0)),
                "seen_in_support_train": bool(support_counts.get(str(family), 0) > 0),
            }
        )
    return rows


def lookup(frame: pd.DataFrame, canary: str, bundle: str, family: str) -> float:
    row = frame.loc[
        frame["canary"].eq(canary)
        & frame["bundle"].eq(bundle)
        & frame["attack_family"].eq(family)
    ]
    return float(row.iloc[0]["auroc"]) if len(row) else float("nan")


def macro_auc(frame: pd.DataFrame, canary: str, bundle: str) -> float:
    part = frame.loc[frame["canary"].eq(canary) & frame["bundle"].eq(bundle), "auroc"]
    return float(part.mean()) if len(part) else float("nan")


def hard_rate(distributions: pd.DataFrame, scope: str, bundle: str) -> float:
    row = distributions.loc[distributions["scope"].eq(scope) & distributions["bundle"].eq(bundle)]
    return float(row.iloc[0]["hard_rate"]) if len(row) else float("nan")


def diagnose(pairwise: pd.DataFrame, distributions: pd.DataFrame) -> dict[str, Any]:
    c1_macro = macro_auc(pairwise, "stream", "C1_207_upper_bound")
    c1_udp = lookup(pairwise, "stream", "C1_207_upper_bound", "UDP Scan")
    compact_macro = macro_auc(pairwise, "stream", "CompactProcess69")
    compact_udp = lookup(pairwise, "stream", "CompactProcess69", "UDP Scan")
    stream_hard = hard_rate(distributions, "stream", "C1_207_upper_bound")
    if c1_macro >= 0.75 and c1_udp >= 0.70 and stream_hard >= 0.90:
        primary = "TRANSFERABLE_RANK_SIGNAL_WITH_GATE_FAILURE"
    elif c1_macro < 0.60 or c1_udp < 0.55:
        primary = "CURRENT_FRONTEND_ENTANGLED_OR_INSUFFICIENT"
    else:
        primary = "MIXED_FAMILY_DEPENDENT_SIGNAL"
    secondary = (
        "COMPACT_PROCESS_ADAPTER_INSUFFICIENT"
        if c1_macro >= 0.75 and c1_udp >= 0.70 and (compact_macro < 0.70 or compact_udp < 0.65)
        else "NO_COMPACT_ADAPTER_DEFICIT_PROVEN"
    )
    return {
        "status": "CKBN_DIAGNOSTIC_COMPLETE",
        "primary_diagnosis": primary,
        "secondary_diagnosis": secondary,
        "metrics": {
            "c1_stream_family_macro_auroc": c1_macro,
            "c1_stream_udp_scan_auroc": c1_udp,
            "c1_stream_hard_rate_at_legal_threshold": stream_hard,
            "compact_stream_family_macro_auroc": compact_macro,
            "compact_stream_udp_scan_auroc": compact_udp,
        },
        "candidate_promoted": False,
        "report_used_for_fit_threshold_normalization_or_feature_selection": False,
        "review": 0,
        "claim_boundary": "Known-canary failure diagnosis only; not final held-family evidence and not a detector go signal.",
    }


def markdown_summary(
    decision: dict[str, Any],
    pairwise: pd.DataFrame,
    distributions: pd.DataFrame,
    elapsed: float,
) -> str:
    lines = [
        "# CKBN stream separability diagnostic",
        "",
        f"- Primary diagnosis: `{decision['primary_diagnosis']}`",
        f"- Secondary diagnosis: `{decision['secondary_diagnosis']}`",
        f"- Runtime seconds: `{elapsed:.3f}`",
        "- stream/hydraulic/cooler fit and threshold rows: `0`",
        "- Candidate promoted: `false`",
        "- Review: `0`",
        "",
        "## Primary C1 evidence",
        "",
        f"- Stream vs future-family macro AUROC: `{decision['metrics']['c1_stream_family_macro_auroc']:.6f}`",
        f"- Stream vs UDP Scan AUROC: `{decision['metrics']['c1_stream_udp_scan_auroc']:.6f}`",
        f"- Stream hard rate at the legal source-OOF threshold: `{decision['metrics']['c1_stream_hard_rate_at_legal_threshold']:.6f}`",
        "",
        "## Pairwise AUROC by future attack family",
        "",
        "| canary | bundle | attack family | AUROC | attack-canary score margin |",
        "|---|---|---|---:|---:|",
    ]
    for row in pairwise.to_dict(orient="records"):
        lines.append(
            f"| {row['canary']} | {row['bundle']} | {row['attack_family']} | "
            f"{row['auroc']:.6f} | {row['attack_minus_canary_score_mean']:.6f} |"
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            str(decision["claim_boundary"]),
            "Packet rows are not claimed as independent samples; source counts are retained in the CSVs.",
            "",
        ]
    )
    return "\n".join(lines)


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"CKBN_START out={out} mode={args.mode}", flush=True)
    final_manifest, final_hash = ckbl.load_final_holdout()
    x_by_role, frame_by_role, input_audit, _ = cko.load_role_inputs(False)
    ckao.add_family_columns(frame_by_role)
    fit, fit_scope = ckbl.legal_fit_table(frame_by_role, 0)
    ckbl.assert_scope(fit, final_manifest)
    blocked, memory_scope = ckbl.known_nonfit_target_blocks(frame_by_role, fit)

    stream, stream_audit = make_report_part(
        frame_by_role, "ood_stress", "select", "stream", 0, int(args.canary_cap), int(args.seed), device_family=STREAM
    )
    hydraulic, hydraulic_audit = make_report_part(
        frame_by_role, "ood_val", "select", "hydraulic", 0, int(args.canary_cap), int(args.seed), device_family=HYDRAULIC
    )
    attacks, attack_audit = make_report_part(
        frame_by_role,
        "future_query",
        "all",
        "future_attack",
        1,
        int(args.attack_family_cap),
        int(args.seed),
        per_attack_family=True,
    )
    reports = {"stream": stream, "hydraulic": hydraulic, "future_attack": attacks}
    zero_use = assert_zero_use(fit, reports)
    if not bool(zero_use["pass"].all()):
        raise RuntimeError("report-family zero-use contract failed")

    fit_scope.to_csv(out / "fit_scope_audit.csv", index=False)
    memory_scope.to_csv(out / "fit_memory_scope_audit.csv", index=False)
    pd.DataFrame(stream_audit + hydraulic_audit + attack_audit).to_csv(out / "report_cohort_audit.csv", index=False)
    zero_use.to_csv(out / "report_family_zero_use_audit.csv", index=False)
    fit[["row_uid", "role", "phase", "source_group", "device_family", "recorded_index", "attack_label", "y"]].to_csv(
        out / "fit_rows.csv", index=False
    )
    for name, table in reports.items():
        table[["row_uid", "role", "phase", "source_group", "device_family", "recorded_index", "attack_label", "y"]].to_csv(
            out / f"{name}_report_rows.csv", index=False
        )

    run_spec = {
        "issue": ISSUE,
        "mode": args.mode,
        "seed": int(args.seed),
        "canary_cap": int(args.canary_cap),
        "attack_family_cap": int(args.attack_family_cap),
        "max_iter": int(args.max_iter),
        "fit_rows": int(len(fit)),
        "support_train_rows": int(fit["role"].eq("support_train").sum()),
        "fit_sources": int(fit["source_group"].nunique()),
        "report_rows": {name: int(len(table)) for name, table in reports.items()},
        "report_sources": {name: int(table["source_group"].nunique()) for name, table in reports.items()},
        "report_attack_families": int(attacks["attack_label"].nunique()),
        "forbidden_family_model_use": {family: 0 for family in sorted(FORBIDDEN)},
        "report_used_for_fit_threshold_normalization_or_feature_selection": False,
        "raw_label_column_read_by_frontend": False,
        "identity_feature_use": False,
        "review": 0,
        "sealed_final_holdout_manifest_sha256": final_hash,
        "git_head_at_run": ckbl.git_head(),
        "declared_commit_sha": os.environ.get("CKBN_COMMIT_SHA", ckbl.git_head()),
        "script_sha256": ckbl.sha256_file(Path(__file__).resolve()),
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
        },
        "input_audit_hash": hashlib.sha256(json.dumps(json_ready(input_audit), sort_keys=True).encode()).hexdigest(),
    }
    dump_json(out / "run_spec.json", run_spec)
    print(
        f"CKBN_SCOPE fit={len(fit)} support={fit['role'].eq('support_train').sum()} "
        f"stream={len(stream)} hydraulic={len(hydraulic)} future={len(attacks)}",
        flush=True,
    )
    if args.mode == "plan":
        print(json.dumps({"status": "CKBN_REAL_DATA_PLAN_OK", **run_spec}, indent=2))
        return

    matrices: dict[str, dict[str, np.ndarray]] = {}
    alignment_rows: list[pd.DataFrame] = []
    source_runtime_rows: list[pd.DataFrame] = []
    for scope, table in {"fit": fit, **reports}.items():
        print(f"CKBN_FEATURE_SCOPE_START scope={scope} rows={len(table)}", flush=True)
        mats, row_audit, source_audit = ckbl.feature_matrices(
            table,
            frame_by_role,
            x_by_role,
            "prefix",
            int(args.seed),
            state_blocked_rows=blocked if scope == "fit" else None,
            progress_path=out / f"{scope}_source_progress.jsonl",
        )
        matrices[scope] = mats
        row_frame = pd.DataFrame(row_audit)
        row_frame.insert(0, "scope", scope)
        alignment_rows.append(row_frame)
        source_frame = pd.DataFrame(source_audit)
        source_frame.insert(0, "scope", scope)
        source_runtime_rows.append(source_frame)
        print(f"CKBN_FEATURE_SCOPE_DONE scope={scope}", flush=True)
    pd.concat(alignment_rows, ignore_index=True).to_csv(out / "frontend_alignment_audit.csv", index=False)
    pd.concat(source_runtime_rows, ignore_index=True).to_csv(out / "frontend_source_runtime_audit.csv", index=False)

    support_counts = fit.loc[fit["y"].eq(1)].groupby("attack_label").size().astype(int).to_dict()
    threshold_rows: list[dict[str, Any]] = []
    distribution_rows: list[dict[str, Any]] = []
    pairwise: list[dict[str, Any]] = []
    hard_rows: list[dict[str, Any]] = []
    per_source_rows: list[dict[str, Any]] = []
    for bundle in REPORT_BUNDLES:
        model_seed = ckbl.stable_seed(int(args.seed), ISSUE, bundle)
        fit_oof, oof_status = ckbl.inner_oof_scores(matrices["fit"][bundle], fit, model_seed, int(args.max_iter))
        threshold, threshold_audit = ckbl.select_threshold(fit, fit_oof)
        threshold_rows.append({"bundle": bundle, "oof_status": oof_status, **threshold_audit})
        if not np.isfinite(threshold):
            raise RuntimeError(f"legal source-OOF threshold unavailable for {bundle}: {threshold_audit}")
        model = ckbl.fit_probe(matrices["fit"][bundle], fit, model_seed, int(args.max_iter))
        scores = {
            "fit_oof": fit_oof,
            "stream": ckbl.score_probe(model, matrices["stream"][bundle]),
            "hydraulic": ckbl.score_probe(model, matrices["hydraulic"][bundle]),
            "future_attack": ckbl.score_probe(model, matrices["future_attack"][bundle]),
        }
        distribution_rows.append(distribution_row("fit_oof", bundle, fit, scores["fit_oof"], threshold))
        for scope in ("stream", "hydraulic", "future_attack"):
            distribution_rows.append(distribution_row(scope, bundle, reports[scope], scores[scope], threshold))
        for source, positions in fit.groupby("source_group", sort=True).indices.items():
            pos = np.asarray(positions, dtype=np.int64)
            row = distribution_row(f"fit_oof_source:{source}", bundle, fit.iloc[pos], fit_oof[pos], threshold)
            row["source_group"] = str(source)
            per_source_rows.append(row)
        for scope in ("stream", "hydraulic"):
            for source, positions in reports[scope].groupby("source_group", sort=True).indices.items():
                pos = np.asarray(positions, dtype=np.int64)
                row = distribution_row(f"{scope}_source:{source}", bundle, reports[scope].iloc[pos], scores[scope][pos], threshold)
                row["source_group"] = str(source)
                per_source_rows.append(row)
            pairwise.extend(pairwise_rows(scope, reports[scope], scores[scope], attacks, scores["future_attack"], bundle))
        hard_rows.extend(hard_attack_rows(attacks, scores["future_attack"], threshold, support_counts, bundle))
        print(f"CKBN_PROBE_DONE bundle={bundle} threshold={threshold:.8g}", flush=True)

    threshold_frame = pd.DataFrame(threshold_rows)
    distribution_frame = pd.DataFrame(distribution_rows)
    pairwise_frame = pd.DataFrame(pairwise)
    hard_frame = pd.DataFrame(hard_rows)
    threshold_frame.to_csv(out / "legal_oof_threshold_audit.csv", index=False)
    distribution_frame.to_csv(out / "score_distribution_summary.csv", index=False)
    pd.DataFrame(per_source_rows).to_csv(out / "per_source_score_summary.csv", index=False)
    pairwise_frame.to_csv(out / "canary_vs_attack_family_pairwise_metrics.csv", index=False)
    hard_frame.to_csv(out / "future_attack_family_hard_recall.csv", index=False)
    decision = diagnose(pairwise_frame, distribution_frame)
    elapsed = time.time() - started
    decision["elapsed_seconds"] = elapsed
    dump_json(out / "decision.json", decision)
    (out / "summary.md").write_text(markdown_summary(decision, pairwise_frame, distribution_frame, elapsed), encoding="utf-8")
    print(json.dumps(json_ready({"out": out, **decision}), indent=2), flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["plan", "run"], default="plan")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--canary-cap", type=int, default=3000)
    parser.add_argument("--attack-family-cap", type=int, default=2000)
    parser.add_argument("--max-iter", type=int, default=80)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
