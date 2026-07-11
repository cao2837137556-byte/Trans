"""issue27ckau: full-support mechanism observability diagnostic.

This is the data-first gate after CKAT formally showed that a global C1 attack
score fails strict leave-device-family OOD safety.  It does NOT train a neural
head or select a deployment threshold.  Instead it asks a narrower question:

    In label-free canonical-time C1 evidence, do known attack mechanisms form
    support manifolds that are distinguishable from held OOD families?

Protocol
--------
* attack mechanism names come only from ``support_train`` fit labels;
* prototypes and feature scaling use legal non-held fit rows only;
* manifold radii use only non-held ``support_val`` select rows;
* future/query/sealed rows are report-only diagnostics;
* raw packet labels are never read: CKAT's immutable canonical source cache is
  the only frontend input.

The diagnostic purposefully keeps only mechanisms with support in at least two
legal source families.  It must not claim cross-environment generalization for
single-environment C2 or transfer support.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckau_c1_mechanism_observability_diagnostic_v1_2026-07-10"
OUT_BASE = cko.ROOT / "runs" / ISSUE
CKAT_PLAN_DIR = cko.ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
DEFAULT_PLAN = CKAT_PLAN_DIR / "canonical_source_load_plan.csv"
DEFAULT_CACHE = CKAT_PLAN_DIR / "hpc_canonical_c1_cache"
HELD_VALUES = [
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "domotic-monitor",
    "combined-cycle",
    "iotsim-ip-camera-street",
]
FIT_BENIGN_ROLES = ["id_calib", "ood_val", "ood_stress"]


def c1_candidate() -> ckai.Candidate:
    for candidate in ckai.CANDIDATES:
        if candidate.name == "C1_cicflow_style_only_histgb":
            return candidate
    raise RuntimeError("C1 candidate not found")


def finite_matrix(x: np.ndarray) -> np.ndarray:
    return np.nan_to_num(np.asarray(x, dtype=np.float32), nan=0.0, posinf=0.0, neginf=0.0)


def fit_scaler(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mu = np.mean(x, axis=0, keepdims=True)
    sigma = np.std(x, axis=0, keepdims=True)
    sigma = np.where(sigma < 1e-6, 1.0, sigma)
    return mu.astype(np.float32), sigma.astype(np.float32)


def transform(x: np.ndarray, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
    return finite_matrix((finite_matrix(x) - mu) / sigma)


def source_family(frame: pd.DataFrame) -> np.ndarray:
    if "source_family" not in frame:
        return np.asarray(["unknown"] * len(frame), dtype=object)
    return frame["source_family"].astype(str).fillna("unknown").to_numpy(dtype=object)


def role_idx(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, cap: int, held: str, *, include: bool = False) -> np.ndarray:
    selector = ("device_family", held)
    return ckao.role_indices_filtered(
        frame_by_role,
        role,
        phase,
        cap,
        include=selector if include else None,
        exclude=None if include else selector,
    )


def mechanism_frame(frame_by_role: dict[str, pd.DataFrame], held: str) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    frame = frame_by_role["support_train"]
    idx = role_idx(frame_by_role, "support_train", "fit", cko.FULL_CAP, held)
    part = frame.iloc[idx].copy().reset_index(drop=True)
    part["mechanism"] = part.get("attack_label", pd.Series("", index=part.index)).map(ckai.coarse_attack_family)
    coverage: list[dict[str, Any]] = []
    for mechanism, group in part.groupby("mechanism", sort=True):
        if mechanism in {"", "benign_or_empty"}:
            continue
        environments = sorted(set(source_family(group).tolist()))
        coverage.append(
            {
                "held_value": held,
                "mechanism": str(mechanism),
                "fit_support_rows": int(len(group)),
                "fit_source_family_count": int(len(environments)),
                "fit_source_families": ";".join(environments),
                "eligible_cross_environment": bool(len(environments) >= 2),
            }
        )
    return part, coverage


def build_fit_reference(
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held: str,
    train_cap: int,
) -> tuple[np.ndarray, list[dict[str, Any]]]:
    candidate = c1_candidate()
    matrices: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []
    attack_idx = role_idx(frame_by_role, "support_train", "fit", cko.FULL_CAP, held)
    matrices.append(frontend.matrix(candidate, "support_train", attack_idx))
    audit.append({"held_value": held, "role": "support_train", "phase": "fit", "rows": int(len(attack_idx)), "use": "fit_scale"})
    for role in FIT_BENIGN_ROLES:
        idx = role_idx(frame_by_role, role, "fit", train_cap, held)
        matrices.append(frontend.matrix(candidate, role, idx))
        audit.append({"held_value": held, "role": role, "phase": "fit", "rows": int(len(idx)), "use": "fit_scale"})
    return np.vstack(matrices).astype(np.float32), audit


def nearest_metrics(x: np.ndarray, prototypes: dict[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    names = sorted(prototypes)
    if not names:
        n = len(x)
        return np.asarray(["no_eligible_mechanism"] * n, dtype=object), np.full(n, np.nan), np.full(n, np.nan)
    stacked = np.vstack([prototypes[name] for name in names]).astype(np.float32)
    distances = np.sqrt(np.maximum(0.0, ((x[:, None, :] - stacked[None, :, :]) ** 2).mean(axis=2)))
    order = np.argsort(distances, axis=1)
    best = order[:, 0]
    nearest = np.asarray([names[index] for index in best], dtype=object)
    best_dist = distances[np.arange(len(x)), best]
    if len(names) == 1:
        margin = np.full(len(x), np.nan)
    else:
        second = distances[np.arange(len(x)), order[:, 1]]
        margin = second - best_dist
    return nearest, best_dist, margin


def support_val_radii(
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held: str,
    prototypes: dict[str, np.ndarray],
    mu: np.ndarray,
    sigma: np.ndarray,
    q: float,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    frame = frame_by_role["support_val"]
    idx = role_idx(frame_by_role, "support_val", "select", cko.FULL_CAP, held)
    part = frame.iloc[idx].copy().reset_index(drop=True)
    part["mechanism"] = part.get("attack_label", pd.Series("", index=part.index)).map(ckai.coarse_attack_family)
    x = transform(frontend.matrix(c1_candidate(), "support_val", idx), mu, sigma)
    radii: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for mechanism in sorted(prototypes):
        mask = part["mechanism"].astype(str).to_numpy() == mechanism
        if int(mask.sum()) < 3:
            rows.append({"held_value": held, "mechanism": mechanism, "support_val_rows": int(mask.sum()), "radius_q": q, "radius": np.nan, "status": "insufficient_support_val"})
            continue
        dist = np.sqrt(np.maximum(0.0, ((x[mask] - prototypes[mechanism][None, :]) ** 2).mean(axis=1)))
        radii[mechanism] = float(np.quantile(dist, q))
        rows.append({"held_value": held, "mechanism": mechanism, "support_val_rows": int(mask.sum()), "radius_q": q, "radius": radii[mechanism], "status": "calibrated_select_only"})
    return radii, rows


def summarise_role(
    frontend: ckai.ExternalFlowFrontend,
    frame_by_role: dict[str, pd.DataFrame],
    held: str,
    role: str,
    phase: str,
    role_kind: str,
    cap: int,
    prototypes: dict[str, np.ndarray],
    radii: dict[str, float],
    mu: np.ndarray,
    sigma: np.ndarray,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_idx(frame_by_role, role, phase, cap, held, include=True)
    if len(idx) == 0:
        return {"held_value": held, "role": role, "phase": phase, "role_kind": role_kind, "rows": 0}, pd.DataFrame()
    x = transform(frontend.matrix(c1_candidate(), role, idx), mu, sigma)
    nearest, dist, margin = nearest_metrics(x, prototypes)
    radii_vec = np.asarray([radii.get(str(name), np.nan) for name in nearest], dtype=np.float64)
    matched = np.isfinite(radii_vec) & (dist <= radii_vec)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    part["held_value"] = held
    part["role"] = role
    part["role_kind"] = role_kind
    part["nearest_mechanism"] = nearest
    part["nearest_distance"] = dist
    part["nearest_margin"] = margin
    part["mechanism_radius"] = radii_vec
    part["mechanism_manifold_match"] = matched
    counts = pd.Series(nearest).value_counts(dropna=False).to_dict()
    return (
        {
            "held_value": held,
            "role": role,
            "phase": phase,
            "role_kind": role_kind,
            "rows": int(len(part)),
            "nearest_distance_mean": float(np.nanmean(dist)),
            "nearest_distance_p50": float(np.nanquantile(dist, 0.50)),
            "nearest_distance_p95": float(np.nanquantile(dist, 0.95)),
            "nearest_margin_mean": float(np.nanmean(margin)) if np.isfinite(margin).any() else np.nan,
            "mechanism_manifold_match_rate": float(np.mean(matched)),
            "nearest_mechanism_counts": json.dumps({str(key): int(value) for key, value in counts.items()}, ensure_ascii=False, sort_keys=True),
            "report_only": bool(role in {"future_query", "same_file_query", "sealed_final_ood", "sealed_final_attack"}),
        },
        part,
    )


def build_readout(coverage: list[dict[str, Any]], role_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    eligible = sorted({row["mechanism"] for row in coverage if bool(row["eligible_cross_environment"])})
    lines = [
        f"# {ISSUE}", "", "## Scope", "",
        "- Frozen full-support C1 cache; no raw packet label read and no neural head trained.",
        "- Prototypes: support_train fit only. Mechanism radii: support_val select only.",
        "- Held report roles never influence scaling, prototypes, radii, or mechanism eligibility.", "",
        "## Eligible cross-environment mechanisms", "",
        f"`{', '.join(eligible) if eligible else 'none'}`", "",
        "## Held-family manifold diagnostic", "",
        "| held family | role | rows | match rate | distance p50 | distance p95 | nearest mechanisms |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in role_rows:
        if row.get("rows", 0):
            lines.append(
                f"| {row['held_value']} | {row['role']} | {row['rows']} | {cko.fmt(row.get('mechanism_manifold_match_rate'))} | "
                f"{cko.fmt(row.get('nearest_distance_p50'))} | {cko.fmt(row.get('nearest_distance_p95'))} | {row.get('nearest_mechanism_counts', '')} |"
            )
    lines.extend([
        "", "## Boundary", "",
        "- A low held-OOD manifold-match rate is necessary but not sufficient evidence for a mechanism verifier.",
        "- A high held-OOD manifold-match rate means C1 itself lacks the needed mechanism separation; do not train a more complex head on it.",
        "- Runtime seconds: %.1f." % seconds,
    ])
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    out = OUT_BASE if not args.run_tag else cko.ROOT / "runs" / f"{ISSUE}_{args.run_tag}"
    out.mkdir(parents=True, exist_ok=True)
    plan_path = Path(args.source_plan)
    cache_dir = Path(args.cache_dir)
    if not plan_path.exists() or not cache_dir.exists():
        raise FileNotFoundError("CKAT source plan/cache missing; run this only after CKAT array completion")

    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frame_by_role)
    cache = ckat.PersistentCanonicalTimeC1Cache(cache_dir, plan_path)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frame_by_role, cache)
    held_values = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    coverage_rows: list[dict[str, Any]] = []
    scale_audit: list[dict[str, Any]] = []
    radius_rows: list[dict[str, Any]] = []
    role_rows: list[dict[str, Any]] = []
    sample_frames: list[pd.DataFrame] = []

    for held in held_values:
        support, coverage = mechanism_frame(frame_by_role, held)
        coverage_rows.extend(coverage)
        eligible = {row["mechanism"] for row in coverage if bool(row["eligible_cross_environment"])}
        support = support[support["mechanism"].astype(str).isin(eligible)].copy().reset_index(drop=True)
        support_idx_all = role_idx(frame_by_role, "support_train", "fit", cko.FULL_CAP, held)
        support_mech_all = frame_by_role["support_train"].iloc[support_idx_all].copy().reset_index(drop=True)
        support_mech_all["mechanism"] = support_mech_all.get("attack_label", pd.Series("", index=support_mech_all.index)).map(ckai.coarse_attack_family)
        eligible_mask = support_mech_all["mechanism"].astype(str).isin(eligible).to_numpy()
        x_support = frontend.matrix(c1_candidate(), "support_train", support_idx_all)[eligible_mask]
        fit_x, audit = build_fit_reference(frontend, frame_by_role, held, int(args.train_cap))
        scale_audit.extend(audit)
        mu, sigma = fit_scaler(fit_x)
        z_support = transform(x_support, mu, sigma)
        prototypes: dict[str, np.ndarray] = {}
        for mechanism in sorted(eligible):
            mask = support_mech_all.loc[eligible_mask, "mechanism"].astype(str).to_numpy() == mechanism
            if int(mask.sum()) >= 2:
                prototypes[mechanism] = np.mean(z_support[mask], axis=0).astype(np.float32)
        radii, radii_audit = support_val_radii(frontend, frame_by_role, held, prototypes, mu, sigma, float(args.radius_q))
        radius_rows.extend(radii_audit)
        for role, phase, role_kind in cko.ROLE_EVAL:
            row, part = summarise_role(frontend, frame_by_role, held, role, phase, role_kind, int(args.eval_cap), prototypes, radii, mu, sigma)
            role_rows.append(row)
            if not part.empty:
                sample_frames.append(part)

    seconds = time.time() - started
    cko.write_csv(out / "mechanism_support_coverage.csv", coverage_rows)
    cko.write_csv(out / "fit_scaling_audit.csv", scale_audit)
    cko.write_csv(out / "mechanism_radius_select_audit.csv", radius_rows)
    cko.write_csv(out / "held_role_manifold_metrics.csv", role_rows)
    # ``cko.write_csv`` deliberately accepts a list of record dictionaries.
    # Passing a DataFrame iterates column names and stops the run after the
    # metrics have been written, leaving an incomplete diagnostic directory.
    sample_rows = pd.concat(sample_frames, ignore_index=True).to_dict("records") if sample_frames else []
    cko.write_csv(out / "held_role_manifold_samples.csv", sample_rows)
    cko.write_csv(out / "canonical_cache_audit.csv", cache.audit_rows)
    cko.write_md(out / "codex_readout.md", build_readout(coverage_rows, role_rows, seconds))
    cko.write_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "full_support": True,
            "train_cap": int(args.train_cap),
            "eval_cap": int(args.eval_cap),
            "radius_q": float(args.radius_q),
            "held_values": held_values,
            "data_use_boundary": {
                "mechanism_labels": "support_train fit only",
                "prototype_fit": "support_train fit only, held excluded",
                "radius_calibration": "support_val select only, held excluded",
                "query_future_sealed_used_for_fit_or_radius": False,
                "raw_processed_label_column_read": False,
            },
            "input_audit": input_audit,
            "seconds": seconds,
        },
    )
    print(json.dumps({"status": "ok", "out": str(out), "seconds": seconds}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--radius-q", type=float, default=0.95)
    parser.add_argument("--held-values", default=",".join(HELD_VALUES))
    parser.add_argument("--source-plan", default=str(DEFAULT_PLAN))
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE))
    parser.add_argument("--run-tag", default="")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
