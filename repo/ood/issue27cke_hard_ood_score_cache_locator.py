from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import pairwise_distances_argmin_min
from sklearn.preprocessing import StandardScaler


OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckc_frozen_medium_mainline_replay_on_certified_1m as ckc  # noqa: E402


ISSUE = "issue27cke_hard_ood_score_cache_locator_2026-06-24"
OUT = ROOT / "runs" / ISSUE

KEY_SCORE_COLS = [
    "attack_score",
    "attack_margin",
    "ood_risk",
    "d_attack_outer_min",
    "d_benign_core_min",
    "benign_minus_attack_distance",
    "temporal_attack_score",
    "temporal_ood_risk",
]

BOOL_COLS = [
    "raw_alarm",
    "hard_alarm",
    "suppress",
    "high_ood_risk",
    "strong_attack",
    "temporal_raw_alarm",
    "temporal_hard_alarm",
    "temporal_suppress",
    "temporal_high_ood_risk",
    "temporal_strong_attack",
    "temporal_unknown",
]

KEEP_RECORD_COLS = [
    "job_index",
    "job_label",
    "weighting",
    "seed",
    "role",
    "role_kind",
    "row_index_in_role",
    "global_id",
    "source_group",
    "packet_timestamp_epoch",
    "recorded_index",
    "attack_label",
    "device",
    "phase",
]


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
        writer.writerows({key: clean(row.get(key, "")) for key in fields} for row in rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(payload), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_md(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def qstats(values: Any) -> dict[str, float]:
    arr = np.asarray(values, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {k: float("nan") for k in ["min", "p50", "p90", "p95", "p99", "max", "mean"]}
    return {
        "min": float(np.min(arr)),
        "p50": float(np.quantile(arr, 0.50)),
        "p90": float(np.quantile(arr, 0.90)),
        "p95": float(np.quantile(arr, 0.95)),
        "p99": float(np.quantile(arr, 0.99)),
        "max": float(np.max(arr)),
        "mean": float(np.mean(arr)),
    }


def rate(values: Any) -> float:
    arr = np.asarray(values, dtype=bool)
    return float(np.mean(arr)) if arr.size else float("nan")


def fmt(value: Any, digits: int = 4) -> str:
    try:
        f = float(value)
    except Exception:
        return "nan"
    if not math.isfinite(f):
        return "nan"
    return f"{f:.{digits}f}"


def parse_job_indices(raw: str) -> list[int]:
    out: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        out.append(int(part))
    if not out:
        raise ValueError("no jobs selected")
    return out


def support_weight_for(job: ckc.JobSpec, n_id: int, n_ood_fit: int, n_support_train: int) -> float:
    if job.weighting == "strict_frozen_weight4":
        return ckc.STRICT_SUPPORT_WEIGHT
    return float(
        (n_id + ckc.OOD_WEIGHT * n_ood_fit)
        / (ckc.MEDIUM_WEIGHTED_NORMAL_TO_ATTACK_RATIO * max(1, n_support_train))
    )


def fit_frozen_stack(
    job: ckc.JobSpec,
    cert_x: np.ndarray,
    benign_idx: dict[str, np.ndarray],
    benign_records: dict[str, pd.DataFrame],
    support_x: np.ndarray,
    support_records: pd.DataFrame,
    support_train_idx: np.ndarray,
    support_val_idx: np.ndarray,
    subspaces: dict[str, np.ndarray],
    smoke: bool,
) -> dict[str, Any]:
    support_val_records = support_records.iloc[support_val_idx].reset_index(drop=True)
    support_val_phase = support_val_records["phase"].to_numpy()

    id_train_idx = ckc.limited_indices(benign_idx["id_benign_train"], smoke, 4000)
    id_calib_x = np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32)
    id_calib_phase = benign_records["id_benign_calib"]["phase"].to_numpy()
    ood_val_x = np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32)
    ood_val_phase = benign_records["ood_benign_val"]["phase"].to_numpy()
    x_id_train = np.asarray(cert_x[id_train_idx], dtype=np.float32)
    x_ood_fit = ood_val_x[ood_val_phase == "fit"]
    x_ood_select = ood_val_x[ood_val_phase == "select"]
    x_support_train = support_x[support_train_idx]
    x_support_val = support_x[support_val_idx]
    x_support_val_fit = x_support_val[support_val_phase == "fit"]

    support_weight = support_weight_for(job, len(x_id_train), len(x_ood_fit), len(x_support_train))
    attack_model = ckc.FrozenAttackHistGB(job.seed)
    attack_model.fit(x_id_train, x_ood_fit, x_support_train, support_weight)
    id_select_scores = attack_model.score(id_calib_x[id_calib_phase == "select"])
    parent_attack_threshold = float(np.quantile(id_select_scores, 0.99))

    banks, bank_audit = ckc.build_evidence_banks(
        subspaces,
        x_id_train,
        id_calib_x[id_calib_phase == "fit"],
        x_ood_fit,
        x_ood_select,
        x_support_train,
        x_support_val_fit,
    )

    pre_roles = {
        "id_calib": (id_calib_x, benign_records["id_benign_calib"].copy(), "benign_id"),
        "ood_val": (ood_val_x, benign_records["ood_benign_val"].copy(), "benign_ood"),
        "support_val": (x_support_val, support_val_records.copy(), "attack"),
    }
    role_evidence: dict[str, np.ndarray] = {}
    role_aux: dict[str, dict[str, np.ndarray]] = {}
    for role, (x_role, records, _kind) in pre_roles.items():
        score = attack_model.score(x_role)
        evidence, aux = ckc.evidence_features(x_role, score, parent_attack_threshold, banks, subspaces)
        role_evidence[role] = evidence
        role_evidence[f"{role}_phase"] = records["phase"].to_numpy()
        role_aux[role] = aux

    parent_model, parent_params, parent_fit_audit = ckc.fit_parent_risk(job.seed, role_evidence, role_aux)
    pre_frames: dict[str, pd.DataFrame] = {}
    for role, (x_role, records, kind) in pre_roles.items():
        frame = ckc.build_role_frame(
            role,
            kind,
            x_role,
            records,
            attack_model,
            parent_attack_threshold,
            banks,
            subspaces,
            parent_model,
            parent_params,
        )
        pre_frames[role] = frame

    temporal_attack_head, temporal_risk_head, temporal_params, temporal_fit_audit = ckc.fit_temporal_heads(
        job.seed, pre_frames
    )
    scored_pre = {
        role: add_job_cols(
            ckc.apply_temporal_controller(frame, temporal_attack_head, temporal_risk_head, temporal_params),
            job,
        )
        for role, frame in pre_frames.items()
    }

    return {
        "job": job,
        "support_weight": support_weight,
        "attack_model": attack_model,
        "parent_attack_threshold": parent_attack_threshold,
        "banks": banks,
        "bank_audit": bank_audit,
        "parent_model": parent_model,
        "parent_params": parent_params,
        "parent_fit_audit": parent_fit_audit,
        "temporal_attack_head": temporal_attack_head,
        "temporal_risk_head": temporal_risk_head,
        "temporal_params": temporal_params,
        "temporal_fit_audit": temporal_fit_audit,
        "scored_pre": scored_pre,
        "x_support_train": x_support_train,
        "support_train_records": support_records.iloc[support_train_idx].reset_index(drop=True),
    }


def add_job_cols(frame: pd.DataFrame, job: ckc.JobSpec) -> pd.DataFrame:
    out = frame.copy()
    out.insert(0, "seed", job.seed)
    out.insert(0, "weighting", job.weighting)
    out.insert(0, "job_label", job.label)
    out.insert(0, "job_index", job.job_index)
    out["row_index_in_role"] = np.arange(len(out), dtype=np.int64)
    return out


def score_post_role(
    stack: dict[str, Any],
    role: str,
    role_kind: str,
    x: np.ndarray,
    records: pd.DataFrame,
) -> pd.DataFrame:
    job = stack["job"]
    frame = ckc.build_role_frame(
        role,
        role_kind,
        x,
        records,
        stack["attack_model"],
        stack["parent_attack_threshold"],
        stack["banks"],
        stack["banks_subspaces"],
        stack["parent_model"],
        stack["parent_params"],
    )
    return add_job_cols(
        ckc.apply_temporal_controller(frame, stack["temporal_attack_head"], stack["temporal_risk_head"], stack["temporal_params"]),
        job,
    )


def summarize_frame(frame: pd.DataFrame, stage: str) -> dict[str, Any]:
    row: dict[str, Any] = {
        "job_index": int(frame["job_index"].iloc[0]),
        "job_label": str(frame["job_label"].iloc[0]),
        "weighting": str(frame["weighting"].iloc[0]),
        "seed": int(frame["seed"].iloc[0]),
        "stage": stage,
        "role": str(frame["role"].iloc[0]),
        "role_kind": str(frame["role_kind"].iloc[0]),
        "rows": len(frame),
    }
    for col in BOOL_COLS:
        if col in frame:
            row[f"{col}_rate"] = rate(frame[col])
    for col in KEY_SCORE_COLS:
        if col in frame:
            stats = qstats(frame[col])
            for k, v in stats.items():
                row[f"{col}_{k}"] = v
    return row


def selected_rows_for_hard_ood(frame: pd.DataFrame, top_k: int) -> pd.DataFrame:
    hard = frame[frame["temporal_hard_alarm"].astype(bool)].copy()
    if hard.empty:
        hard = frame.copy()
    selectors: list[tuple[str, pd.DataFrame]] = [
        ("top_temporal_attack", hard.sort_values("temporal_attack_score", ascending=False).head(top_k)),
        ("top_parent_attack", hard.sort_values("attack_score", ascending=False).head(top_k)),
        ("lowest_temporal_ood_risk", hard.sort_values("temporal_ood_risk", ascending=True).head(top_k)),
        ("nearest_attack_region", hard.sort_values("d_attack_outer_min", ascending=True).head(top_k)),
        ("highest_benign_minus_attack", hard.sort_values("benign_minus_attack_distance", ascending=False).head(top_k)),
    ]
    parts = []
    for selector, part in selectors:
        if part.empty:
            continue
        part = part.copy()
        part["selector"] = selector
        parts.append(part)
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    return out.drop_duplicates(["job_index", "role", "row_index_in_role", "selector"]).reset_index(drop=True)


def selected_rows_for_attack_misses(frame: pd.DataFrame, top_k: int) -> pd.DataFrame:
    misses = frame[~frame["temporal_hard_alarm"].astype(bool)].copy()
    if misses.empty:
        return pd.DataFrame()
    selectors: list[tuple[str, pd.DataFrame]] = [
        ("lowest_temporal_attack", misses.sort_values("temporal_attack_score", ascending=True).head(top_k)),
        ("highest_temporal_ood_risk", misses.sort_values("temporal_ood_risk", ascending=False).head(top_k)),
        ("farthest_attack_region", misses.sort_values("d_attack_outer_min", ascending=False).head(top_k)),
        ("lowest_parent_attack", misses.sort_values("attack_score", ascending=True).head(top_k)),
    ]
    parts = []
    for selector, part in selectors:
        if part.empty:
            continue
        part = part.copy()
        part["selector"] = selector
        parts.append(part)
    out = pd.concat(parts, ignore_index=True)
    return out.drop_duplicates(["job_index", "role", "row_index_in_role", "selector"]).reset_index(drop=True)


def nearest_support_annotations(
    selected: pd.DataFrame,
    x_by_role: dict[str, np.ndarray],
    x_support_train: np.ndarray,
    support_train_records: pd.DataFrame,
    subspaces: dict[str, np.ndarray],
) -> list[dict[str, Any]]:
    if selected.empty:
        return []
    out: list[dict[str, Any]] = []
    scalers: dict[str, StandardScaler] = {}
    support_z: dict[str, np.ndarray] = {}
    names = ["HH", "HH_HpHp", "all115"]
    for name in names:
        idx = subspaces[name]
        scaler = StandardScaler().fit(x_support_train[:, idx])
        scalers[name] = scaler
        support_z[name] = scaler.transform(x_support_train[:, idx])

    for _, row in selected.iterrows():
        role = str(row["role"])
        local_idx = int(row["row_index_in_role"])
        x_one = x_by_role[role][[local_idx]]
        annot: dict[str, Any] = {
            "job_index": int(row["job_index"]),
            "job_label": row["job_label"],
            "weighting": row["weighting"],
            "role": role,
            "selector": row.get("selector", ""),
            "row_index_in_role": local_idx,
            "global_id": row.get("global_id", ""),
            "source_group": row.get("source_group", ""),
            "attack_label": row.get("attack_label", ""),
            "device": row.get("device", ""),
            "temporal_hard_alarm": bool(row.get("temporal_hard_alarm", False)),
            "temporal_attack_score": float(row.get("temporal_attack_score", float("nan"))),
            "temporal_ood_risk": float(row.get("temporal_ood_risk", float("nan"))),
            "attack_score": float(row.get("attack_score", float("nan"))),
            "ood_risk": float(row.get("ood_risk", float("nan"))),
            "d_attack_outer_min": float(row.get("d_attack_outer_min", float("nan"))),
            "d_benign_core_min": float(row.get("d_benign_core_min", float("nan"))),
            "benign_minus_attack_distance": float(row.get("benign_minus_attack_distance", float("nan"))),
        }
        for name in names:
            idx = subspaces[name]
            q = scalers[name].transform(x_one[:, idx])
            nearest, dist = pairwise_distances_argmin_min(q, support_z[name], metric="euclidean")
            support_row = support_train_records.iloc[int(nearest[0])]
            prefix = f"nearest_support_{name}"
            annot[f"{prefix}_distance"] = float(dist[0])
            annot[f"{prefix}_global_id"] = support_row.get("global_id", "")
            annot[f"{prefix}_label"] = support_row.get("attack_label", "")
            annot[f"{prefix}_device"] = support_row.get("device", "")
            annot[f"{prefix}_source_group"] = support_row.get("source_group", "")
        out.append(annot)
    return out


def compact_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    fields = [c for c in KEEP_RECORD_COLS + KEY_SCORE_COLS + BOOL_COLS + ["selector"] if c in frame.columns]
    return frame[fields].to_dict(orient="records")


def group_hard_ood_sources(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    hard = frame[frame["temporal_hard_alarm"].astype(bool)]
    if hard.empty:
        return rows
    for (source_group, device), group in hard.groupby(["source_group", "device"], sort=True):
        rows.append(
            {
                "job_index": int(group["job_index"].iloc[0]),
                "job_label": str(group["job_label"].iloc[0]),
                "weighting": str(group["weighting"].iloc[0]),
                "role": str(group["role"].iloc[0]),
                "source_group": source_group,
                "device": device,
                "hard_rows": len(group),
                "role_rows": len(frame),
                "hard_share_within_role": len(group) / max(1, len(frame)),
                "temporal_attack_score_mean": float(group["temporal_attack_score"].mean()),
                "temporal_ood_risk_mean": float(group["temporal_ood_risk"].mean()),
                "attack_score_mean": float(group["attack_score"].mean()),
                "ood_risk_mean": float(group["ood_risk"].mean()),
                "d_attack_outer_min_mean": float(group["d_attack_outer_min"].mean()),
                "d_benign_core_min_mean": float(group["d_benign_core_min"].mean()),
            }
        )
    rows.sort(key=lambda r: (-r["hard_rows"], r["role"], r["source_group"]))
    return rows


def label_count_rows(nearest_rows: list[dict[str, Any]], role_filter: set[str]) -> list[dict[str, Any]]:
    buckets: dict[tuple[Any, ...], Counter[str]] = defaultdict(Counter)
    for row in nearest_rows:
        if row["role"] not in role_filter:
            continue
        key = (row["job_index"], row["job_label"], row["weighting"], row["role"], row["selector"])
        label = str(row.get("nearest_support_HH_HpHp_label", ""))
        buckets[key][label] += 1
    out: list[dict[str, Any]] = []
    for key, counter in sorted(buckets.items()):
        total = sum(counter.values())
        for label, count in counter.most_common():
            out.append(
                {
                    "job_index": key[0],
                    "job_label": key[1],
                    "weighting": key[2],
                    "role": key[3],
                    "selector": key[4],
                    "nearest_support_HH_HpHp_label": label,
                    "selected_rows": count,
                    "selected_share": count / max(1, total),
                }
            )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", default="1,6", help="comma-separated issue27ckc job indices; default medium seed42 and strict seed42")
    parser.add_argument("--top-k", type=int, default=80, help="top rows per selector")
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()

    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)

    input_audit = ckc.validate_inputs()
    attack_root = Path(input_audit["attack_root"])
    cert_x = np.load(ckc.CERT_X, mmap_mode="r")
    schema = json.loads(ckc.FEATURE_SCHEMA.read_text(encoding="utf-8"))
    subspaces = ckc.bp.build_subspaces(schema)

    benign_idx, benign_records = ckc.load_benign_roles(args.smoke)
    benign_records["id_benign_calib"] = ckc.add_source_disjoint_phase(benign_records["id_benign_calib"])
    benign_records["ood_benign_val"] = ckc.add_source_disjoint_phase(benign_records["ood_benign_val"])
    support_x, support_records, support_train_idx, support_val_idx = ckc.load_support(attack_root)

    stress_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)
    future_x, future_records = ckc.load_attack_role(attack_root, "dev_future_attack_query_exact", args.smoke)
    sealed_attack_x, sealed_attack_records = ckc.load_attack_role(
        attack_root,
        "sealed_final_attack_exact_realign",
        args.smoke,
    )

    x_by_role_base = {
        "ood_stress": stress_x,
        "sealed_final_ood": sealed_ood_x,
        "future_query": future_x,
        "sealed_final_attack": sealed_attack_x,
    }

    job_indices = parse_job_indices(args.jobs)
    jobs = []
    for job_index in job_indices:
        job = next((spec for spec in ckc.JOB_SPECS if spec.job_index == job_index), None)
        if job is None:
            raise SystemExit(f"unknown job index {job_index}")
        jobs.append(job)

    role_summary_rows: list[dict[str, Any]] = []
    parent_fit_rows: list[dict[str, Any]] = []
    temporal_fit_rows: list[dict[str, Any]] = []
    hard_ood_rows: list[dict[str, Any]] = []
    attack_miss_rows: list[dict[str, Any]] = []
    nearest_rows: list[dict[str, Any]] = []
    hard_source_rows: list[dict[str, Any]] = []
    run_rows: list[dict[str, Any]] = []

    for job in jobs:
        job_started = time.time()
        stack = fit_frozen_stack(
            job,
            cert_x,
            benign_idx,
            benign_records,
            support_x,
            support_records,
            support_train_idx,
            support_val_idx,
            subspaces,
            args.smoke,
        )
        stack["banks_subspaces"] = subspaces
        scored_pre = stack["scored_pre"]
        for role, frame in scored_pre.items():
            selected = frame[frame["phase"] == "select"] if "phase" in frame else frame
            role_summary_rows.append(summarize_frame(selected, "calibration_select"))

        post_roles = {
            "ood_stress": (stress_x, benign_records["ood_benign_stress"], "benign_ood", "read_only"),
            "sealed_final_ood": (sealed_ood_x, benign_records["sealed_final_ood"], "benign_ood", "report_only"),
            "future_query": (future_x, future_records, "attack", "read_only"),
            "sealed_final_attack": (sealed_attack_x, sealed_attack_records, "attack", "report_only"),
        }
        scored_post: dict[str, pd.DataFrame] = {}
        for role, (x_role, records, kind, stage) in post_roles.items():
            frame = score_post_role(stack, role, kind, x_role, records)
            scored_post[role] = frame
            role_summary_rows.append(summarize_frame(frame, stage))
            if kind.startswith("benign"):
                hard_source_rows.extend(group_hard_ood_sources(frame))

        x_by_role = {
            **x_by_role_base,
            "id_calib": np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32),
            "ood_val": np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32),
            "support_val": support_x[support_val_idx],
        }

        hard_selected_parts = [
            selected_rows_for_hard_ood(scored_post["ood_stress"], args.top_k),
            selected_rows_for_hard_ood(scored_post["sealed_final_ood"], args.top_k),
        ]
        hard_selected = pd.concat([p for p in hard_selected_parts if not p.empty], ignore_index=True)
        if not hard_selected.empty:
            hard_ood_rows.extend(compact_rows(hard_selected))
            nearest_rows.extend(
                nearest_support_annotations(
                    hard_selected,
                    x_by_role,
                    stack["x_support_train"],
                    stack["support_train_records"],
                    subspaces,
                )
            )

        miss_selected_parts = [
            selected_rows_for_attack_misses(scored_post["future_query"], args.top_k),
            selected_rows_for_attack_misses(scored_post["sealed_final_attack"], args.top_k),
        ]
        miss_selected = pd.concat([p for p in miss_selected_parts if not p.empty], ignore_index=True)
        if not miss_selected.empty:
            attack_miss_rows.extend(compact_rows(miss_selected))
            nearest_rows.extend(
                nearest_support_annotations(
                    miss_selected,
                    x_by_role,
                    stack["x_support_train"],
                    stack["support_train_records"],
                    subspaces,
                )
            )

        for row in stack["parent_fit_audit"]:
            parent_fit_rows.append({"job_index": job.job_index, "job_label": job.label, "weighting": job.weighting, **row})
        for row in stack["temporal_fit_audit"]:
            temporal_fit_rows.append({"job_index": job.job_index, "job_label": job.label, "weighting": job.weighting, **row})

        run_rows.append(
            {
                "job_index": job.job_index,
                "job_label": job.label,
                "weighting": job.weighting,
                "seed": job.seed,
                "support_weight": stack["support_weight"],
                "parent_attack_threshold": stack["parent_attack_threshold"],
                "parent_risk_threshold": stack["parent_params"]["risk_threshold"],
                "temporal_attack_threshold": stack["temporal_params"]["attack_threshold"],
                "temporal_risk_threshold": stack["temporal_params"]["risk_threshold"],
                "seconds": time.time() - job_started,
            }
        )

    nearest_label_counts = label_count_rows(nearest_rows, {"ood_stress", "sealed_final_ood"})

    write_csv(OUT / "role_score_distribution.csv", role_summary_rows)
    write_csv(OUT / "parent_risk_fit_audit.csv", parent_fit_rows)
    write_csv(OUT / "temporal_fit_audit.csv", temporal_fit_rows)
    write_csv(OUT / "hard_ood_selected_rows.csv", hard_ood_rows)
    write_csv(OUT / "attack_miss_selected_rows.csv", attack_miss_rows)
    write_csv(OUT / "selected_rows_nearest_support.csv", nearest_rows)
    write_csv(OUT / "hard_ood_by_source_group.csv", hard_source_rows)
    write_csv(OUT / "hard_ood_nearest_support_label_counts.csv", nearest_label_counts)
    write_csv(OUT / "run_jobs.csv", run_rows)

    diagnosis = build_diagnosis(role_summary_rows, parent_fit_rows, nearest_label_counts, hard_source_rows, run_rows)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "source_protocol": "issue27ckc exact frozen scoring stack, local score-cache locator",
            "jobs": [clean(job.__dict__) for job in jobs],
            "smoke": args.smoke,
            "top_k": args.top_k,
            "input_audit": input_audit,
            "seconds": time.time() - started,
            "outputs": [
                "role_score_distribution.csv",
                "parent_risk_fit_audit.csv",
                "temporal_fit_audit.csv",
                "hard_ood_selected_rows.csv",
                "attack_miss_selected_rows.csv",
                "selected_rows_nearest_support.csv",
                "hard_ood_by_source_group.csv",
                "hard_ood_nearest_support_label_counts.csv",
                "run_jobs.csv",
                "summary.md",
            ],
        },
    )
    write_md(OUT / "summary.md", diagnosis)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": time.time() - started}, indent=2))


def find_row(rows: list[dict[str, Any]], weighting: str, role: str) -> dict[str, Any] | None:
    for row in rows:
        if row.get("weighting") == weighting and row.get("role") == role:
            return row
    return None


def build_diagnosis(
    role_rows: list[dict[str, Any]],
    parent_fit_rows: list[dict[str, Any]],
    nearest_label_counts: list[dict[str, Any]],
    hard_source_rows: list[dict[str, Any]],
    run_rows: list[dict[str, Any]],
) -> list[str]:
    lines: list[str] = [
        "# issue27cke hard-OOD score-cache locator",
        "",
        "## Purpose",
        "",
        "This is a localization run, not a new model result. It reuses the frozen issue27ckc scoring stack and inspects why hard benign OOD is accepted as attack.",
        "",
        "## Key role-level evidence",
        "",
    ]
    for weighting in sorted({str(row["weighting"]) for row in role_rows}):
        ood_val = find_row(role_rows, weighting, "ood_val")
        stress = find_row(role_rows, weighting, "ood_stress")
        sealed = find_row(role_rows, weighting, "sealed_final_ood")
        future = find_row(role_rows, weighting, "future_query")
        sealed_attack = find_row(role_rows, weighting, "sealed_final_attack")
        lines.append(f"### {weighting}")
        lines.append("")
        lines.append("| role | rows | temporal hard | parent hard | temporal attack mean | temporal risk mean | attack distance mean | benign distance mean |")
        lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
        for row in [ood_val, stress, sealed, future, sealed_attack]:
            if row is None:
                continue
            lines.append(
                "| "
                + str(row["role"])
                + " | "
                + str(row["rows"])
                + " | "
                + fmt(row.get("temporal_hard_alarm_rate"))
                + " | "
                + fmt(row.get("hard_alarm_rate"))
                + " | "
                + fmt(row.get("temporal_attack_score_mean"))
                + " | "
                + fmt(row.get("temporal_ood_risk_mean"))
                + " | "
                + fmt(row.get("d_attack_outer_min_mean"))
                + " | "
                + fmt(row.get("d_benign_core_min_mean"))
                + " |"
            )
        lines.append("")

    lines.extend(
        [
            "## Parent OOD-risk fit audit",
            "",
            "| job | weighting | role | risk label | rows used | row source |",
            "|---:|---|---|---:|---:|---|",
        ]
    )
    for row in parent_fit_rows:
        lines.append(
            f"| {row['job_index']} | {row['weighting']} | {row['role']} | {row['risk_label']} | {row['fit_rows_used']} | {row['row_source']} |"
        )
    lines.append("")

    lines.extend(
        [
            "## What the selected hard OOD rows are nearest to",
            "",
            "Counts below use only selected diagnostic rows, not the full OOD corpus. They locate the failure mode without turning this into another full experiment.",
            "",
            "| weighting | role | selector | nearest support label | selected rows | share |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for row in nearest_label_counts[:80]:
        lines.append(
            f"| {row['weighting']} | {row['role']} | {row['selector']} | {row['nearest_support_HH_HpHp_label']} | {row['selected_rows']} | {fmt(row['selected_share'])} |"
        )
    lines.append("")

    lines.extend(
        [
            "## Largest hard-OOD source groups",
            "",
            "| weighting | role | source group | hard rows | share | temporal attack mean | temporal risk mean |",
            "|---|---|---|---:|---:|---:|---:|",
        ]
    )
    for row in sorted(hard_source_rows, key=lambda r: (-r["hard_rows"], r["weighting"], r["role"]))[:30]:
        lines.append(
            f"| {row['weighting']} | {row['role']} | {row['source_group']} | {row['hard_rows']} | {fmt(row['hard_share_within_role'])} | {fmt(row['temporal_attack_score_mean'])} | {fmt(row['temporal_ood_risk_mean'])} |"
        )
    lines.append("")

    lines.extend(
        [
            "## Current localization conclusion",
            "",
            "1. If `ood_val` remains clean while `ood_stress` and `sealed_final_ood` are near-one hard alarms, the validation OOD slice is not representative of the hard benign OOD that appears after freeze.",
            "2. If hard OOD has high temporal attack score but low temporal OOD-risk, the failure is not merely a threshold bug. The OOD-risk evidence is anti-calibrated for hard OOD.",
            "3. If hard OOD is also close to attack regions (`d_attack_outer_min` around or below 1), the 115D/evidence geometry itself is confounding benign OOD with support-covered attack modes.",
            "4. The next fix should therefore target OOD evidence/calibration before controller wiring: add hard-OOD calibration or a conservative OOD veto, then rerun the same frozen-role replay.",
            "",
            "## Run metadata",
            "",
            "| job | weighting | support weight | parent threshold | temporal threshold | seconds |",
            "|---:|---|---:|---:|---:|---:|",
        ]
    )
    for row in run_rows:
        lines.append(
            f"| {row['job_index']} | {row['weighting']} | {fmt(row['support_weight'])} | {fmt(row['parent_attack_threshold'])} | {fmt(row['temporal_attack_threshold'])} | {fmt(row['seconds'], 1)} |"
        )
    return lines


if __name__ == "__main__":
    main()
