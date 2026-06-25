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
import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402


ISSUE = "issue27ckh_direct_multihead_detector_2026-06-25"
OUT = ROOT / "runs" / ISSUE

SEED = 42
JOB_INDEX = 1
BENIGN_CAP_PER_ROLE = 1600
DEV_ATTACK_CAP_PER_ROLE = 20000
EVAL_CAP_PER_ROLE = 120000
BENIGN_SAFE_Q = 0.99
SUPPORT_HARD_OOD_GATE_Q = 0.95


@dataclass(frozen=True)
class Candidate:
    name: str
    regime: str
    feature_set: str
    architecture: str
    model: str
    description: str


CANDIDATES = [
    Candidate(
        "C1_fewshot_binary_raw115",
        "fewshot_direct",
        "raw115",
        "binary_attack_vs_all_benign",
        "histgb_shallow",
        "Direct attack-vs-ID/OOD/hard-OOD head using support attacks only.",
    ),
    Candidate(
        "C2_fewshot_binary_evidence",
        "fewshot_direct",
        "evidence",
        "binary_attack_vs_all_benign",
        "histgb_shallow",
        "Direct attack-vs-ID/OOD/hard-OOD head using evidence features.",
    ),
    Candidate(
        "C3_fewshot_binary_raw_plus_evidence",
        "fewshot_direct",
        "raw_plus_evidence",
        "binary_attack_vs_all_benign",
        "histgb_stronger",
        "Direct head using raw115 plus current evidence features.",
    ),
    Candidate(
        "C4_fewshot_multiclass_raw115",
        "fewshot_direct",
        "raw115",
        "multiclass_id_ood_hardood_attack",
        "histgb_shallow",
        "Four-class head; high-priority attack is class-attack probability after benign-safe calibration.",
    ),
    Candidate(
        "C5_fewshot_multihead_raw_plus_evidence",
        "fewshot_direct",
        "raw_plus_evidence",
        "multihead_attack_hardood_conflict",
        "histgb_stronger",
        "Attack head plus hard-OOD head; high attack requires low conflict, otherwise review.",
    ),
    Candidate(
        "U1_devlabel_binary_raw_plus_temporal_mlp",
        "dev_label_upper",
        "raw_plus_temporal",
        "binary_attack_vs_all_benign",
        "mlp_small",
        "Upper-bound direct head with legal dev attack labels and temporal features; not deployable few-shot.",
    ),
    Candidate(
        "U2_devlabel_multihead_raw_plus_temporal",
        "dev_label_upper",
        "raw_plus_temporal",
        "multihead_attack_hardood_conflict",
        "histgb_stronger",
        "Upper-bound conflict-aware head with legal dev attack labels.",
    ),
]


ROLE_EVAL = [
    ("id_calib", "select", "benign_id"),
    ("ood_val", "select", "benign_ood"),
    ("ood_stress", "select", "hard_ood"),
    ("support_val", "select", "attack"),
    ("same_file_query", "select", "attack"),
    ("future_query", "select", "attack"),
    ("sealed_final_ood", "all", "benign_ood_report"),
    ("sealed_final_attack", "all", "attack_report"),
]


CLASS_ID = 0
CLASS_OOD = 1
CLASS_HARD_OOD = 2
CLASS_ATTACK = 3


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


def deterministic_cap(indices: np.ndarray, cap: int) -> np.ndarray:
    indices = np.asarray(indices, dtype=np.int64)
    if len(indices) <= cap:
        return indices
    keep = np.linspace(0, len(indices) - 1, num=cap, dtype=np.int64)
    return indices[keep]


def build_model(name: str, multiclass: bool = False) -> Any:
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
                max_iter=100,
                early_stopping=True,
                n_iter_no_change=8,
                batch_size=512,
                random_state=SEED,
            ),
        )
    raise ValueError(f"unknown model {name}")


def positive_score(model: Any, x: np.ndarray, positive_label: int = 1) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    return np.asarray(proba[:, classes.index(positive_label)], dtype=np.float64)


def class_score(model: Any, x: np.ndarray, label: int) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    if label not in classes:
        return np.zeros(len(x), dtype=np.float64)
    return np.asarray(proba[:, classes.index(label)], dtype=np.float64)


def balanced_fit(model: Any, x: np.ndarray, y: np.ndarray) -> Any:
    y = np.asarray(y)
    if "Pipeline" in type(model).__name__:
        model.fit(np.asarray(x, dtype=np.float32), y)
        return model
    counts = {label: int(np.sum(y == label)) for label in np.unique(y)}
    weights = np.asarray([1.0 / max(1, counts[label]) for label in y], dtype=np.float64)
    weights *= len(weights) / max(1e-12, float(np.sum(weights)))
    model.fit(np.asarray(x, dtype=np.float32), y, sample_weight=weights)
    return model


def safe_auc(pos: np.ndarray, neg: np.ndarray) -> tuple[float, float]:
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
    return ckg.feature_matrix(feature_set, role, x_by_role, frame_by_role)


def role_indices(frame_by_role: dict[str, pd.DataFrame], role: str, phase: str, cap: int) -> np.ndarray:
    frame = frame_by_role[role]
    idx = np.arange(len(frame), dtype=np.int64) if phase == "all" else np.flatnonzero(frame["phase"].to_numpy() == phase)
    return deterministic_cap(idx, cap)


def train_rows_for_candidate(
    candidate: Candidate,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    xs: list[np.ndarray] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = role_indices(frame_by_role, role, phase, cap)
        xs.append(feature_matrix(candidate.feature_set, role, x_by_role, frame_by_role)[idx])
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append({"role": role, "phase": phase, "label": label, "rows": len(idx)})

    if candidate.regime == "fewshot_direct":
        pos_label = CLASS_ATTACK if candidate.architecture == "multiclass_id_ood_hardood_attack" else 1
        add("support_train", "fit", pos_label, 1000000)
    elif candidate.regime == "dev_label_upper":
        pos_label = CLASS_ATTACK if candidate.architecture == "multiclass_id_ood_hardood_attack" else 1
        add("support_train", "fit", pos_label, 1000000)
        add("support_val", "fit", pos_label, 1000000)
        add("same_file_query", "fit", pos_label, DEV_ATTACK_CAP_PER_ROLE)
        add("future_query", "fit", pos_label, DEV_ATTACK_CAP_PER_ROLE)
    else:
        raise ValueError(candidate.regime)

    if candidate.architecture == "multiclass_id_ood_hardood_attack":
        add("id_calib", "fit", CLASS_ID, BENIGN_CAP_PER_ROLE)
        add("ood_val", "fit", CLASS_OOD, BENIGN_CAP_PER_ROLE)
        add("ood_stress", "fit", CLASS_HARD_OOD, BENIGN_CAP_PER_ROLE)
    else:
        add("id_calib", "fit", 0, BENIGN_CAP_PER_ROLE)
        add("ood_val", "fit", 0, BENIGN_CAP_PER_ROLE)
        add("ood_stress", "fit", 0, BENIGN_CAP_PER_ROLE)

    return np.vstack(xs), np.concatenate(ys), audit


def fit_candidate(candidate: Candidate, x_by_role: dict[str, np.ndarray], frame_by_role: dict[str, pd.DataFrame]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    x_train, y_train, audit = train_rows_for_candidate(candidate, x_by_role, frame_by_role)
    if candidate.architecture == "binary_attack_vs_all_benign":
        model = balanced_fit(build_model(candidate.model), x_train, y_train)
        return {"attack_model": model}, audit
    if candidate.architecture == "multiclass_id_ood_hardood_attack":
        model = balanced_fit(build_model(candidate.model, multiclass=True), x_train, y_train)
        return {"multiclass_model": model}, audit
    if candidate.architecture == "multihead_attack_hardood_conflict":
        attack_model = balanced_fit(build_model(candidate.model), x_train, (y_train > 0).astype(np.int8))
        # Hard-OOD head sees hard OOD as positive and attack/id/ordinary OOD as negative.
        xs: list[np.ndarray] = []
        ys: list[np.ndarray] = []
        hard_audit: list[dict[str, Any]] = []

        def add_hard(role: str, phase: str, label: int, cap: int) -> None:
            idx = role_indices(frame_by_role, role, phase, cap)
            xs.append(feature_matrix(candidate.feature_set, role, x_by_role, frame_by_role)[idx])
            ys.append(np.full(len(idx), label, dtype=np.int8))
            hard_audit.append({"role": role, "phase": phase, "label": label, "rows": len(idx), "head": "hard_ood"})

        add_hard("ood_stress", "fit", 1, BENIGN_CAP_PER_ROLE)
        add_hard("support_train", "fit", 0, 1000000)
        add_hard("id_calib", "fit", 0, BENIGN_CAP_PER_ROLE)
        add_hard("ood_val", "fit", 0, BENIGN_CAP_PER_ROLE)
        if candidate.regime == "dev_label_upper":
            add_hard("same_file_query", "fit", 0, DEV_ATTACK_CAP_PER_ROLE)
            add_hard("future_query", "fit", 0, DEV_ATTACK_CAP_PER_ROLE)
        hard_model = balanced_fit(build_model(candidate.model), np.vstack(xs), np.concatenate(ys))
        return {"attack_model": attack_model, "hard_ood_model": hard_model}, audit + hard_audit
    raise ValueError(candidate.architecture)


def benign_safe_threshold(
    candidate: Candidate,
    fitted: dict[str, Any],
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> dict[str, float]:
    scores = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = role_indices(frame_by_role, role, "select", EVAL_CAP_PER_ROLE)
        x = feature_matrix(candidate.feature_set, role, x_by_role, frame_by_role)[idx]
        scores.append(decision_scores(candidate, fitted, x)["attack_score"])
    threshold = float(max(np.quantile(score, BENIGN_SAFE_Q) for score in scores))
    out = {"attack_threshold": threshold}
    if candidate.architecture == "multihead_attack_hardood_conflict":
        x_support = feature_matrix(candidate.feature_set, "support_train", x_by_role, frame_by_role)
        hard_support = positive_score(fitted["hard_ood_model"], x_support)
        out["hard_ood_gate"] = float(np.quantile(hard_support, SUPPORT_HARD_OOD_GATE_Q))
    else:
        out["hard_ood_gate"] = float("nan")
    return out


def decision_scores(candidate: Candidate, fitted: dict[str, Any], x: np.ndarray) -> dict[str, np.ndarray]:
    if candidate.architecture == "binary_attack_vs_all_benign":
        attack = positive_score(fitted["attack_model"], x, 1)
        return {
            "attack_score": attack,
            "hard_ood_score": np.zeros(len(x), dtype=np.float64),
            "conflict_score": np.zeros(len(x), dtype=np.float64),
        }
    if candidate.architecture == "multiclass_id_ood_hardood_attack":
        model = fitted["multiclass_model"]
        attack = class_score(model, x, CLASS_ATTACK)
        hard_ood = class_score(model, x, CLASS_HARD_OOD)
        ood = class_score(model, x, CLASS_OOD)
        identity = class_score(model, x, CLASS_ID)
        return {
            "attack_score": attack,
            "hard_ood_score": hard_ood,
            "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
        }
    if candidate.architecture == "multihead_attack_hardood_conflict":
        attack = positive_score(fitted["attack_model"], x, 1)
        hard_ood = positive_score(fitted["hard_ood_model"], x, 1)
        return {
            "attack_score": attack,
            "hard_ood_score": hard_ood,
            "conflict_score": np.minimum(attack, hard_ood),
        }
    raise ValueError(candidate.architecture)


def eval_candidate_role(
    candidate: Candidate,
    fitted: dict[str, Any],
    thresholds: dict[str, float],
    role: str,
    phase: str,
    role_kind: str,
    x_by_role: dict[str, np.ndarray],
    frame_by_role: dict[str, pd.DataFrame],
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = role_indices(frame_by_role, role, phase, EVAL_CAP_PER_ROLE)
    x = feature_matrix(candidate.feature_set, role, x_by_role, frame_by_role)[idx]
    score = decision_scores(candidate, fitted, x)
    raw = score["attack_score"] > thresholds["attack_threshold"]
    if candidate.architecture == "multihead_attack_hardood_conflict":
        conflict = raw & (score["hard_ood_score"] > thresholds["hard_ood_gate"])
    elif candidate.architecture == "multiclass_id_ood_hardood_attack":
        conflict = raw & (score["conflict_score"] > score["attack_score"])
    else:
        conflict = np.zeros(len(raw), dtype=bool)
    hard = raw & (~conflict)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    part["attack_score"] = score["attack_score"]
    part["hard_ood_score"] = score["hard_ood_score"]
    part["conflict_score"] = score["conflict_score"]
    part["raw_alarm"] = raw
    part["conflict_review"] = conflict
    part["hard_alarm"] = hard
    row = {
        "candidate": candidate.name,
        "regime": candidate.regime,
        "feature_set": candidate.feature_set,
        "architecture": candidate.architecture,
        "model": candidate.model,
        "role": role,
        "phase": phase,
        "role_kind": role_kind,
        "rows": len(part),
        "attack_threshold": thresholds["attack_threshold"],
        "hard_ood_gate": thresholds["hard_ood_gate"],
        "raw_alarm_rate": rate(raw),
        "conflict_review_rate": rate(conflict),
        "hard_alarm_rate": rate(hard),
        "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
        "hard_ood_score_mean": float(np.mean(score["hard_ood_score"])) if len(part) else float("nan"),
        "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
    }
    return row, part


def group_rows(candidate: Candidate, role: str, phase: str, part: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    if len(part) == 0:
        return rows
    for (source, device), group in part.groupby(["source_group", "device"], sort=True):
        rows.append(
            {
                "candidate": candidate.name,
                "regime": candidate.regime,
                "feature_set": candidate.feature_set,
                "architecture": candidate.architecture,
                "role": role,
                "phase": phase,
                "source_group": source,
                "device": device,
                "rows": len(group),
                "hard_alarm_rate": rate(group["hard_alarm"]),
                "conflict_review_rate": rate(group["conflict_review"]),
                "attack_score_mean": float(group["attack_score"].mean()),
                "hard_ood_score_mean": float(group["hard_ood_score"].mean()),
            }
        )
    return rows


def support_coverage_rows(candidate: Candidate, role: str, part: pd.DataFrame, support_labels: set[str]) -> list[dict[str, Any]]:
    if "attack_label" not in part.columns:
        return []
    out = []
    tmp = part.assign(
        support_coverage=np.where(part["attack_label"].astype(str).isin(support_labels), "seen_in_support", "unseen_in_support")
    )
    for (coverage, label), group in tmp.groupby(["support_coverage", "attack_label"], sort=True):
        out.append(
            {
                "candidate": candidate.name,
                "regime": candidate.regime,
                "feature_set": candidate.feature_set,
                "architecture": candidate.architecture,
                "role": role,
                "support_coverage": coverage,
                "attack_label": label,
                "rows": len(group),
                "hard_alarm_rate": rate(group["hard_alarm"]),
                "conflict_review_rate": rate(group["conflict_review"]),
            }
        )
    return out


def make_summary(role_metrics: list[dict[str, Any]], group_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for candidate in sorted({row["candidate"] for row in role_metrics}):
        def get(role: str) -> float:
            vals = [float(row["hard_alarm_rate"]) for row in role_metrics if row["candidate"] == candidate and row["role"] == role]
            return float(np.mean(vals)) if vals else float("nan")

        def review(role: str) -> float:
            vals = [float(row["conflict_review_rate"]) for row in role_metrics if row["candidate"] == candidate and row["role"] == role]
            return float(np.mean(vals)) if vals else float("nan")

        def gmax(role: str) -> float:
            vals = [float(row["hard_alarm_rate"]) for row in group_metrics if row["candidate"] == candidate and row["role"] == role]
            return float(np.max(vals)) if vals else float("nan")

        sample = next(row for row in role_metrics if row["candidate"] == candidate)
        out.append(
            {
                "candidate": candidate,
                "regime": sample["regime"],
                "feature_set": sample["feature_set"],
                "architecture": sample["architecture"],
                "model": sample["model"],
                "id_calib": get("id_calib"),
                "ood_val": get("ood_val"),
                "ood_stress": get("ood_stress"),
                "ood_stress_group_max": gmax("ood_stress"),
                "support_val": get("support_val"),
                "same_file_query": get("same_file_query"),
                "future_query": get("future_query"),
                "sealed_final_attack": get("sealed_final_attack"),
                "sealed_final_ood": get("sealed_final_ood"),
                "sealed_final_ood_group_max": gmax("sealed_final_ood"),
                "sealed_attack_review": review("sealed_final_attack"),
                "sealed_ood_review": review("sealed_final_ood"),
            }
        )
    return out


def build_readout(summary: list[dict[str, Any]], auc_rows: list[dict[str, Any]], train_rows: list[dict[str, Any]], seconds: float) -> list[str]:
    lines = [
        "# issue27ckh direct multihead detector",
        "",
        "## Scope",
        "",
        "This is the first trial of the new structure. It stops tuning the old attack-scorer plus OOD-veto pipeline and instead trains direct attack-vs-ID/OOD/hard-OOD discriminative heads. Sealed final roles are report-only.",
        "",
        "## Candidate summary",
        "",
        "| candidate | regime | feature | architecture | ID | OOD-val | hard-OOD | hard-OOD group max | support | same-file | future | sealed attack | sealed OOD | sealed OOD group max | sealed attack review |",
        "|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary:
        lines.append(
            f"| {row['candidate']} | {row['regime']} | {row['feature_set']} | {row['architecture']} | {fmt(row['id_calib'])} | {fmt(row['ood_val'])} | {fmt(row['ood_stress'])} | {fmt(row['ood_stress_group_max'])} | {fmt(row['support_val'])} | {fmt(row['same_file_query'])} | {fmt(row['future_query'])} | {fmt(row['sealed_final_attack'])} | {fmt(row['sealed_final_ood'])} | {fmt(row['sealed_final_ood_group_max'])} | {fmt(row['sealed_attack_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Threshold-free separability",
            "",
            "| candidate | comparison | AUC | AP |",
            "|---|---|---:|---:|",
        ]
    )
    for row in auc_rows:
        lines.append(f"| {row['candidate']} | {row['comparison']} | {fmt(row['auc'])} | {fmt(row['ap'])} |")
    lines.extend(
        [
            "",
            "## Interpretation guardrails",
            "",
            "- A good candidate must control ID/OOD/hard-OOD and sealed-final OOD while retaining support-covered and sealed attacks.",
            "- `dev_label_upper` candidates are not deployable few-shot systems; they only show whether stronger heads and more labels can use the existing representation.",
            "- If a multihead candidate mainly sends attacks to review, it is not a detection fix yet; it is only safer than false high-priority alarms.",
            "",
            "## Training audit",
            "",
            "| candidate | role | phase | label | rows |",
            "|---|---|---|---:|---:|",
        ]
    )
    for row in train_rows:
        lines.append(f"| {row['candidate']} | {row['role']} | {row['phase']} | {row['label']} | {row['rows']} |")
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
    support_labels = set(support_records.loc[support_train_idx, "attack_label"].astype(str))

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
    for role, x_role, records in [
        ("same_file_query", same_x, ckg.add_source_or_time_phase(same_records)),
        ("future_query", future_x, ckg.add_source_or_time_phase(future_records)),
        ("sealed_final_attack", sealed_attack_x, sealed_attack_records.copy()),
        ("sealed_final_ood", sealed_ood_x, benign_records["sealed_final_ood"].copy()),
    ]:
        if role in {"sealed_final_attack", "sealed_final_ood"}:
            records = records.copy()
            records["phase"] = "report_only"
        frame_by_role[role] = ckf.build_role_frame_with_temporal(
            role,
            "attack" if "attack" in role else "benign_ood",
            x_role,
            records,
            stack,
            job,
        )
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

    role_metrics: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    coverage_metrics: list[dict[str, Any]] = []
    train_audit: list[dict[str, Any]] = []
    auc_rows: list[dict[str, Any]] = []

    parts_by_candidate_role: dict[tuple[str, str], pd.DataFrame] = {}

    for candidate in CANDIDATES:
        fitted, audit = fit_candidate(candidate, x_by_role, frame_by_role)
        thresholds = benign_safe_threshold(candidate, fitted, x_by_role, frame_by_role)
        for item in audit:
            train_audit.append({"candidate": candidate.name, **item})
        for role, phase, role_kind in ROLE_EVAL:
            row, part = eval_candidate_role(candidate, fitted, thresholds, role, phase, role_kind, x_by_role, frame_by_role)
            role_metrics.append(row)
            group_metrics.extend(group_rows(candidate, role, phase, part))
            if role in {"support_val", "same_file_query", "future_query", "sealed_final_attack"}:
                coverage_metrics.extend(support_coverage_rows(candidate, role, part, support_labels))
            parts_by_candidate_role[(candidate.name, role)] = part
        for attack_role, ood_role, name in [
            ("support_val", "ood_stress", "support_vs_hard_ood"),
            ("same_file_query", "ood_stress", "same_file_vs_hard_ood"),
            ("future_query", "ood_stress", "future_vs_hard_ood"),
            ("sealed_final_attack", "sealed_final_ood", "sealed_attack_vs_sealed_ood"),
        ]:
            pos = parts_by_candidate_role[(candidate.name, attack_role)]["attack_score"].to_numpy()
            neg = parts_by_candidate_role[(candidate.name, ood_role)]["attack_score"].to_numpy()
            auc, ap = safe_auc(pos, neg)
            auc_rows.append(
                {
                    "candidate": candidate.name,
                    "comparison": name,
                    "positive_rows": len(pos),
                    "negative_rows": len(neg),
                    "auc": auc,
                    "ap": ap,
                }
            )

    summary = make_summary(role_metrics, group_metrics)
    seconds = time.time() - started
    write_csv(OUT / "candidate_matrix.csv", [candidate.__dict__ for candidate in CANDIDATES])
    write_csv(OUT / "train_audit.csv", train_audit)
    write_csv(OUT / "role_metrics.csv", role_metrics)
    write_csv(OUT / "group_metrics_by_source_device.csv", group_metrics)
    write_csv(OUT / "support_coverage_metrics.csv", coverage_metrics)
    write_csv(OUT / "threshold_free_metrics.csv", auc_rows)
    write_csv(OUT / "selected_summary.csv", summary)
    write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "first direct multihead detector trial; seed42 diagnostic",
            "smoke": args.smoke,
            "job_index": JOB_INDEX,
            "seed": SEED,
            "benign_cap_per_role": BENIGN_CAP_PER_ROLE,
            "dev_attack_cap_per_role": DEV_ATTACK_CAP_PER_ROLE,
            "eval_cap_per_role": EVAL_CAP_PER_ROLE,
            "benign_safe_q": BENIGN_SAFE_Q,
            "support_hard_ood_gate_q": SUPPORT_HARD_OOD_GATE_Q,
            "sealed_final_roles_used_for_training": False,
            "input_audit": input_audit,
            "seconds": seconds,
            "outputs": [
                "candidate_matrix.csv",
                "train_audit.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "support_coverage_metrics.csv",
                "threshold_free_metrics.csv",
                "selected_summary.csv",
                "summary.md",
                "codex_readout.md",
            ],
        },
    )
    readout = build_readout(summary, auc_rows, train_audit, seconds)
    write_md(OUT / "summary.md", readout)
    write_md(OUT / "codex_readout.md", readout)
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds}, indent=2))


if __name__ == "__main__":
    main()
