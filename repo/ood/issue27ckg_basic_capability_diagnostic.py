from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


OOD_DIR = Path(__file__).resolve().parent
REPO_DIR = OOD_DIR.parent
ROOT = REPO_DIR.parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckc_frozen_medium_mainline_replay_on_certified_1m as ckc  # noqa: E402
import issue27ckf_hard_ood_calibrated_worst_group_veto as ckf  # noqa: E402


ISSUE = "issue27ckg_basic_capability_diagnostic_2026-06-25"
OUT = ROOT / "runs" / ISSUE

SEED = 42
JOB_INDEX = 1
TRAIN_CAP_PER_ROLE = 20000
EVAL_CAP_PER_ROLE = 120000
SUPPORT_ONLY_NEG_RATIO = 4
OOD_SAFE_Q = 0.99

EVIDENCE_COLS = [
    "attack_score",
    "attack_margin",
    "ood_risk",
    "d_attack_outer_min",
    "d_benign_core_min",
    "benign_minus_attack_distance",
]


@dataclass(frozen=True)
class DiagnosticSpec:
    regime: str
    feature_set: str
    model: str
    description: str


SPECS = [
    DiagnosticSpec("support_only", "raw115", "histgb_shallow", "few-shot support only; raw Kitsune115D"),
    DiagnosticSpec("support_only", "evidence", "histgb_shallow", "few-shot support only; current evidence features"),
    DiagnosticSpec("support_only", "raw_plus_evidence", "histgb_stronger", "few-shot support only; stronger head"),
    DiagnosticSpec("support_all_benign", "raw115", "histgb_shallow", "support positives with ID/OOD/hard-OOD negatives"),
    DiagnosticSpec("support_all_benign", "evidence", "histgb_shallow", "support positives with current evidence and all benign negatives"),
    DiagnosticSpec("support_all_benign", "raw_plus_evidence", "histgb_stronger", "support positives with stronger head and all benign negatives"),
    DiagnosticSpec("label_rich_upper", "raw115", "histgb_stronger", "diagnostic upper bound with dev attack labels"),
    DiagnosticSpec("label_rich_upper", "evidence", "histgb_stronger", "diagnostic upper bound with current evidence"),
    DiagnosticSpec("label_rich_upper", "temporal", "histgb_stronger", "diagnostic upper bound with past-only temporal features"),
    DiagnosticSpec("label_rich_upper", "raw_plus_temporal", "histgb_stronger", "diagnostic upper bound with raw+temporal"),
    DiagnosticSpec("label_rich_upper", "raw_plus_temporal", "mlp_small", "diagnostic upper bound with a small neural head"),
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


def fmt(value: Any, digits: int = 4) -> str:
    try:
        val = float(value)
    except Exception:
        return "nan"
    if not math.isfinite(val):
        return "nan"
    return f"{val:.{digits}f}"


def rate(values: Any) -> float:
    arr = np.asarray(values, dtype=bool)
    return float(np.mean(arr)) if arr.size else float("nan")


def add_source_or_time_phase(records: pd.DataFrame) -> pd.DataFrame:
    out = records.copy().reset_index(drop=True)
    groups = sorted(out["source_group"].astype(str).unique().tolist())
    if len(groups) > 1:
        cut = max(1, min(len(groups) - 1, len(groups) // 2))
        fit_groups = set(groups[:cut])
        out["phase"] = np.where(out["source_group"].astype(str).isin(fit_groups), "fit", "select")
        out["phase_rule"] = "source_group_disjoint"
        return out
    order = out.sort_values(["packet_timestamp_epoch", "recorded_index"], kind="mergesort").index
    split = max(1, len(order) // 2)
    out["phase"] = "select"
    out.loc[order[:split], "phase"] = "fit"
    out["phase_rule"] = "time_half_fallback"
    return out


def deterministic_cap(indices: np.ndarray, cap: int) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) <= cap:
        return indices
    keep = np.linspace(0, len(indices) - 1, num=cap, dtype=np.int64)
    return indices[keep]


def build_model(name: str) -> Any:
    if name == "histgb_shallow":
        return HistGradientBoostingClassifier(
            max_iter=80,
            learning_rate=0.05,
            max_leaf_nodes=8,
            l2_regularization=0.1,
            random_state=SEED,
        )
    if name == "histgb_stronger":
        return HistGradientBoostingClassifier(
            max_iter=160,
            learning_rate=0.05,
            max_leaf_nodes=31,
            l2_regularization=0.01,
            random_state=SEED,
        )
    if name == "mlp_small":
        return make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(64, 32),
                activation="relu",
                alpha=1e-4,
                learning_rate_init=1e-3,
                max_iter=80,
                early_stopping=True,
                n_iter_no_change=8,
                batch_size=512,
                random_state=SEED,
            ),
        )
    raise ValueError(f"unknown model {name}")


def positive_score(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    return np.asarray(proba[:, classes.index(1)], dtype=np.float64)


def balanced_fit(model: Any, x: np.ndarray, y: np.ndarray) -> Any:
    y = np.asarray(y, dtype=np.int8)
    if "Pipeline" in type(model).__name__:
        model.fit(np.asarray(x, dtype=np.float32), y)
        return model
    counts = {label: int(np.sum(y == label)) for label in np.unique(y)}
    weights = np.asarray([1.0 / max(1, counts[int(label)]) for label in y], dtype=np.float64)
    weights *= len(weights) / max(1e-12, float(np.sum(weights)))
    model.fit(np.asarray(x, dtype=np.float32), y, sample_weight=weights)
    return model


def safe_auc(pos: np.ndarray, neg: np.ndarray) -> tuple[float, float]:
    pos = np.asarray(pos, dtype=np.float64)
    neg = np.asarray(neg, dtype=np.float64)
    if len(pos) == 0 or len(neg) == 0:
        return float("nan"), float("nan")
    y = np.concatenate([np.ones(len(pos), dtype=np.int8), np.zeros(len(neg), dtype=np.int8)])
    s = np.concatenate([pos, neg])
    try:
        auc = float(roc_auc_score(y, s))
    except ValueError:
        auc = float("nan")
    try:
        ap = float(average_precision_score(y, s))
    except ValueError:
        ap = float("nan")
    return auc, ap


def feature_matrix(feature_set: str, role: str, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame]) -> np.ndarray:
    raw = np.asarray(x_by_role[role], dtype=np.float32)
    frame = frame_by_role[role]
    if feature_set == "raw115":
        return raw
    if feature_set == "evidence":
        return frame[EVIDENCE_COLS].to_numpy(dtype=np.float32)
    if feature_set == "temporal":
        return frame[ckc.TEMPORAL_FEATURES].to_numpy(dtype=np.float32)
    if feature_set == "raw_plus_evidence":
        return np.hstack([raw, frame[EVIDENCE_COLS].to_numpy(dtype=np.float32)]).astype(np.float32)
    if feature_set == "raw_plus_temporal":
        return np.hstack([raw, frame[ckc.TEMPORAL_FEATURES].to_numpy(dtype=np.float32)]).astype(np.float32)
    raise ValueError(f"unknown feature set {feature_set}")


def gather_rows(
    feature_set: str,
    roles: list[tuple[str, str, int | None]],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    xs = []
    ys = []
    audit = []
    for role, phase, label in roles:
        frame = frame_by_role[role]
        idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
        if len(idx) == 0:
            continue
        cap = TRAIN_CAP_PER_ROLE
        if role == "ood_stress" and label == 0:
            cap = TRAIN_CAP_PER_ROLE
        idx = deterministic_cap(idx, cap)
        x = feature_matrix(feature_set, role, x_by_role, frame_by_role)[idx]
        xs.append(x)
        ys.append(np.full(len(idx), int(label), dtype=np.int8))
        audit.append({"role": role, "phase": phase, "label": label, "rows": len(idx)})
    if not xs:
        raise RuntimeError("empty training set")
    return np.vstack(xs), np.concatenate(ys), audit


def gather_support_only(
    feature_set: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    pos = feature_matrix(feature_set, "support_train", x_by_role, frame_by_role)
    neg_all_idx = np.flatnonzero(frame_by_role["ood_stress"]["phase"].to_numpy() == "fit")
    neg_idx = deterministic_cap(neg_all_idx, min(len(neg_all_idx), len(pos) * SUPPORT_ONLY_NEG_RATIO))
    neg = feature_matrix(feature_set, "ood_stress", x_by_role, frame_by_role)[neg_idx]
    x = np.vstack([pos, neg])
    y = np.concatenate([np.ones(len(pos), dtype=np.int8), np.zeros(len(neg), dtype=np.int8)])
    audit = [
        {"role": "support_train", "phase": "all", "label": 1, "rows": len(pos)},
        {"role": "ood_stress", "phase": "fit", "label": 0, "rows": len(neg)},
    ]
    return x, y, audit


def gather_support_all_benign(
    feature_set: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    pos = feature_matrix(feature_set, "support_train", x_by_role, frame_by_role)
    neg_parts = []
    audit = [{"role": "support_train", "phase": "all", "label": 1, "rows": len(pos)}]
    per_role = max(1, (len(pos) * SUPPORT_ONLY_NEG_RATIO) // 3)
    for role in ["id_calib", "ood_val", "ood_stress"]:
        frame = frame_by_role[role]
        idx = np.flatnonzero(frame["phase"].to_numpy() == "fit")
        idx = deterministic_cap(idx, per_role)
        neg_parts.append(feature_matrix(feature_set, role, x_by_role, frame_by_role)[idx])
        audit.append({"role": role, "phase": "fit", "label": 0, "rows": len(idx)})
    neg = np.vstack(neg_parts)
    x = np.vstack([pos, neg])
    y = np.concatenate([np.ones(len(pos), dtype=np.int8), np.zeros(len(neg), dtype=np.int8)])
    return x, y, audit


def eval_role_scores(
    spec: DiagnosticSpec,
    model: Any,
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], pd.DataFrame]:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
    idx = deterministic_cap(idx, EVAL_CAP_PER_ROLE)
    x = feature_matrix(spec.feature_set, role, x_by_role, frame_by_role)[idx]
    score = positive_score(model, x)
    hard = score > threshold
    part = frame.iloc[idx].copy().reset_index(drop=True)
    part["diagnostic_score"] = score
    part["diagnostic_hard_alarm"] = hard
    row = {
        "regime": spec.regime,
        "feature_set": spec.feature_set,
        "model": spec.model,
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(part),
        "threshold": threshold,
        "hard_alarm_rate": rate(hard),
        "score_mean": float(np.mean(score)) if len(score) else float("nan"),
        "score_p50": float(np.quantile(score, 0.50)) if len(score) else float("nan"),
        "score_p95": float(np.quantile(score, 0.95)) if len(score) else float("nan"),
    }
    return row, part


def group_metrics(spec: DiagnosticSpec, role: str, phase: str, part: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    if len(part) == 0:
        return rows
    for (source, device), group in part.groupby(["source_group", "device"], sort=True):
        rows.append(
            {
                "regime": spec.regime,
                "feature_set": spec.feature_set,
                "model": spec.model,
                "role": role,
                "phase": phase,
                "source_group": source,
                "device": device,
                "rows": len(group),
                "hard_alarm_rate": rate(group["diagnostic_hard_alarm"]),
                "score_mean": float(group["diagnostic_score"].mean()),
            }
        )
    return rows


def summarize_spec(role_rows: list[dict[str, Any]], group_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    keys = sorted({(r["regime"], r["feature_set"], r["model"]) for r in role_rows})
    for regime, feature_set, model in keys:
        def get(role: str, phase: str) -> float:
            vals = [
                float(r["hard_alarm_rate"])
                for r in role_rows
                if r["regime"] == regime and r["feature_set"] == feature_set and r["model"] == model and r["role"] == role and r["phase"] == phase
            ]
            return float(np.mean(vals)) if vals else float("nan")

        def gmax(role: str, phase: str) -> float:
            vals = [
                float(r["hard_alarm_rate"])
                for r in group_rows
                if r["regime"] == regime and r["feature_set"] == feature_set and r["model"] == model and r["role"] == role and r["phase"] == phase
            ]
            return float(np.max(vals)) if vals else float("nan")

        out.append(
            {
                "regime": regime,
                "feature_set": feature_set,
                "model": model,
                "id_calib_select": get("id_calib", "select"),
                "ood_val_select": get("ood_val", "select"),
                "support_val_select": get("support_val", "select"),
                "same_file_select": get("same_file_query", "select"),
                "future_select": get("future_query", "select"),
                "ood_stress_select": get("ood_stress", "select"),
                "ood_stress_group_max": gmax("ood_stress", "select"),
                "sealed_final_attack": get("sealed_final_attack", "all"),
                "sealed_final_ood": get("sealed_final_ood", "all"),
                "sealed_final_ood_group_max": gmax("sealed_final_ood", "all"),
            }
        )
    return out


def build_readout(summary: list[dict[str, Any]], auc_rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckg basic capability diagnostic",
        "",
        "## Scope",
        "",
        "This is not a deployable repair. It asks whether the current feature/evidence space contains enough information to separate hard benign OOD from attack when the head is made stronger or given more development labels. Sealed final roles are never used for training or threshold selection.",
        "",
        "## Main summary",
        "",
        "| regime | feature set | model | ID | OOD-val | support | same-file | future | ood_stress | ood group max | sealed attack | sealed OOD | sealed OOD group max |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['regime']} | {row['feature_set']} | {row['model']} | {fmt(row['id_calib_select'])} | {fmt(row['ood_val_select'])} | {fmt(row['support_val_select'])} | {fmt(row['same_file_select'])} | {fmt(row['future_select'])} | {fmt(row['ood_stress_select'])} | {fmt(row['ood_stress_group_max'])} | {fmt(row['sealed_final_attack'])} | {fmt(row['sealed_final_ood'])} | {fmt(row['sealed_final_ood_group_max'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold-free separability",
            "",
            "| regime | feature set | model | comparison | AUC | AP |",
            "|---|---|---|---|---:|---:|",
        ]
    )
    for row in auc_rows:
        lines.append(
            f"| {row['regime']} | {row['feature_set']} | {row['model']} | {row['comparison']} | {fmt(row['auc'])} | {fmt(row['ap'])} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `support_only` tests the narrow binary question: support attacks versus hard OOD. It is not a complete detector.",
            "- `support_all_benign` is closer to a few-shot detector: support attacks versus ID/OOD/hard-OOD negatives.",
            "- `label_rich_upper` is an upper-bound diagnostic. If this also fails under source-disjoint hard OOD and sealed transfer, Kitsune115D/current evidence is likely insufficient.",
            "- A scientifically useful next model must not only reduce average OOD false alarms; it must control worst-group OOD while retaining support-covered and sealed attacks.",
            "",
            "## Training audit",
            "",
            "| regime | feature set | model | role | phase | label | rows |",
            "|---|---|---|---|---|---:|---:|",
        ]
    )
    for row in train_rows:
        lines.append(
            f"| {row['regime']} | {row['feature_set']} | {row['model']} | {row['role']} | {row['phase']} | {row['label']} | {row['rows']} |"
        )
    lines.append("")
    lines.append(f"Runtime seconds: `{fmt(seconds, 1)}`.")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
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
    hard_ood_x = np.asarray(cert_x[benign_idx["ood_benign_stress"]], dtype=np.float32)
    hard_ood_records = ckf.add_hard_ood_phase(benign_records["ood_benign_stress"])
    support_x, support_records, support_train_idx, support_val_idx = ckc.load_support(attack_root)

    job = next(spec for spec in ckc.JOB_SPECS if spec.job_index == JOB_INDEX)
    stack = ckf.build_stack(
        job,
        cert_x,
        benign_idx,
        benign_records,
        support_x,
        support_records,
        support_train_idx,
        support_val_idx,
        subspaces,
        attack_root,
        hard_ood_records,
        hard_ood_x,
        args.smoke,
        False,
    )

    same_x, same_records = ckc.load_attack_role(attack_root, "same_file_time_forward_dev_query_exact", args.smoke)
    future_x, future_records = ckc.load_attack_role(attack_root, "dev_future_attack_query_exact", args.smoke)
    sealed_attack_x, sealed_attack_records = ckc.load_attack_role(
        attack_root,
        "sealed_final_attack_exact_realign",
        args.smoke,
    )
    sealed_ood_x = np.asarray(cert_x[benign_idx["sealed_final_ood"]], dtype=np.float32)

    frame_by_role = dict(stack["frames"])
    x_by_role = {
        "id_calib": np.asarray(cert_x[benign_idx["id_benign_calib"]], dtype=np.float32),
        "ood_val": np.asarray(cert_x[benign_idx["ood_benign_val"]], dtype=np.float32),
        "support_val": support_x[support_val_idx],
        "ood_stress": hard_ood_x,
        "same_file_query": same_x,
        "future_query": future_x,
        "sealed_final_ood": sealed_ood_x,
        "sealed_final_attack": sealed_attack_x,
        "support_train": support_x[support_train_idx],
    }
    # Rebuild attack query frames with source-disjoint phases for label-rich diagnostic training.
    for role, x_role, records in [
        ("same_file_query", same_x, add_source_or_time_phase(same_records)),
        ("future_query", future_x, add_source_or_time_phase(future_records)),
        ("sealed_final_attack", sealed_attack_x, sealed_attack_records.copy()),
        ("sealed_final_ood", sealed_ood_x, benign_records["sealed_final_ood"].copy()),
    ]:
        if role in {"sealed_final_attack", "sealed_final_ood"}:
            records = records.copy()
            records["phase"] = "report_only"
        frame_by_role[role] = ckf.build_role_frame_with_temporal(role, "attack" if "attack" in role else "benign_ood", x_role, records, stack, job)

    support_train_records = support_records.iloc[support_train_idx].reset_index(drop=True).copy()
    support_train_records["phase"] = "fit"
    frame_by_role["support_train"] = ckf.build_role_frame_with_temporal(
        "support_train",
        "attack",
        x_by_role["support_train"],
        support_train_records,
        stack,
        job,
    )

    role_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    auc_rows: list[dict[str, Any]] = []

    eval_roles = [
        ("id_calib", "select", "id"),
        ("support_val", "select", "attack"),
        ("same_file_query", "select", "attack"),
        ("future_query", "select", "attack"),
        ("ood_val", "select", "ood"),
        ("ood_stress", "select", "ood"),
        ("sealed_final_attack", "all", "attack"),
        ("sealed_final_ood", "all", "ood"),
    ]

    parts_for_auc: dict[tuple[str, str, str, str, str], pd.DataFrame] = {}

    for spec in SPECS:
        if spec.regime == "support_only":
            x_train, y_train, audit = gather_support_only(spec.feature_set, x_by_role, frame_by_role)
        elif spec.regime == "support_all_benign":
            x_train, y_train, audit = gather_support_all_benign(spec.feature_set, x_by_role, frame_by_role)
        elif spec.regime == "label_rich_upper":
            x_train, y_train, audit = gather_rows(
                spec.feature_set,
                [
                    ("support_train", "fit", 1),
                    ("support_val", "fit", 1),
                    ("same_file_query", "fit", 1),
                    ("future_query", "fit", 1),
                    ("id_calib", "fit", 0),
                    ("ood_val", "fit", 0),
                    ("ood_stress", "fit", 0),
                ],
                x_by_role,
                frame_by_role,
            )
        else:
            raise ValueError(spec.regime)

        model = balanced_fit(build_model(spec.model), x_train, y_train)
        # Dev threshold is benign-safe: ID, ordinary OOD, and source-disjoint
        # hard OOD must all be protected. This avoids overestimating capability
        # by calibrating only on ood_stress.
        threshold_parts = []
        for calib_role in ["id_calib", "ood_val", "ood_stress"]:
            calib_idx = deterministic_cap(
                np.flatnonzero(frame_by_role[calib_role]["phase"].to_numpy() == "select"),
                EVAL_CAP_PER_ROLE,
            )
            calib_x = feature_matrix(spec.feature_set, calib_role, x_by_role, frame_by_role)[calib_idx]
            threshold_parts.append(float(np.quantile(positive_score(model, calib_x), OOD_SAFE_Q)))
        threshold = float(max(threshold_parts))

        for item in audit:
            train_rows.append(
                {
                    "regime": spec.regime,
                    "feature_set": spec.feature_set,
                    "model": spec.model,
                    **item,
                }
            )

        for role, phase, kind in eval_roles:
            row, part = eval_role_scores(spec, model, threshold, role, phase, kind, x_by_role, frame_by_role)
            role_rows.append(row)
            group_rows.extend(group_metrics(spec, role, phase, part))
            parts_for_auc[(spec.regime, spec.feature_set, spec.model, role, phase)] = part

        for attack_role, attack_phase, ood_role, ood_phase, name in [
            ("support_val", "select", "ood_stress", "select", "support_vs_ood_stress"),
            ("same_file_query", "select", "ood_stress", "select", "same_file_vs_ood_stress"),
            ("future_query", "select", "ood_stress", "select", "future_vs_ood_stress"),
            ("sealed_final_attack", "all", "sealed_final_ood", "all", "sealed_attack_vs_sealed_ood"),
        ]:
            pos = parts_for_auc[(spec.regime, spec.feature_set, spec.model, attack_role, attack_phase)]["diagnostic_score"].to_numpy()
            neg = parts_for_auc[(spec.regime, spec.feature_set, spec.model, ood_role, ood_phase)]["diagnostic_score"].to_numpy()
            auc, ap = safe_auc(pos, neg)
            auc_rows.append(
                {
                    "regime": spec.regime,
                    "feature_set": spec.feature_set,
                    "model": spec.model,
                    "comparison": name,
                    "positive_rows": len(pos),
                    "negative_rows": len(neg),
                    "auc": auc,
                    "ap": ap,
                }
            )

    summary = summarize_spec(role_rows, group_rows)
    seconds = time.time() - started
    write_csv(OUT / "diagnostic_specs.csv", [spec.__dict__ for spec in SPECS])
    write_csv(OUT / "train_audit.csv", train_rows)
    write_csv(OUT / "role_metrics.csv", role_rows)
    write_csv(OUT / "group_metrics_by_source_device.csv", group_rows)
    write_csv(OUT / "threshold_free_metrics.csv", auc_rows)
    write_csv(OUT / "selected_summary.csv", summary)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "basic capability diagnostic; no deployable repair claim",
            "smoke": args.smoke,
            "job_index": JOB_INDEX,
            "seed": SEED,
            "train_cap_per_role": TRAIN_CAP_PER_ROLE,
            "eval_cap_per_role": EVAL_CAP_PER_ROLE,
            "ood_safe_q": OOD_SAFE_Q,
            "sealed_final_roles_used_for_training": False,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "diagnostic_specs.csv",
                "train_audit.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "threshold_free_metrics.csv",
                "selected_summary.csv",
                "summary.md",
                "codex_readout.md",
            ],
        },
    )
    readout = build_readout(summary, auc_rows, train_rows, seconds)
    write_md(OUT / "summary.md", readout)
    write_md(OUT / "codex_readout.md", readout)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
