"""issue27ckp: structured evidence frontend v1.

This experiment tests the next step after naive raw115+mechanism concatenation:

    evidence encoders -> one four-class fusion head

The final detector is still a single four-class classifier:

    ID benign / ordinary OOD / hard OOD / attack

but its input is structured evidence rather than one undifferentiated feature
blob.  Raw115 and mechanism blocks are first converted into class-probability
evidence by block encoders.  The fusion head is trained on out-of-fold evidence
from legal fit roles only, then evaluated on the same report roles as issue27cko.

No query/future/final/report-only rows are used for fitting or thresholding.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold

OOD_DIR = Path(__file__).resolve().parent
if str(OOD_DIR) not in sys.path:
    sys.path.insert(0, str(OOD_DIR))

import issue27ckg_basic_capability_diagnostic as ckg  # noqa: E402
import issue27ckh_direct_multihead_detector as ckh  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckp_structured_evidence_frontend_v1_2026-06-29"
OUT = cko.ROOT / "runs" / ISSUE

CLASS_LABELS = [ckh.CLASS_ID, ckh.CLASS_OOD, ckh.CLASS_HARD_OOD, ckh.CLASS_ATTACK]
CLASS_NAMES = {
    ckh.CLASS_ID: "id",
    ckh.CLASS_OOD: "ood",
    ckh.CLASS_HARD_OOD: "hard_ood",
    ckh.CLASS_ATTACK: "attack",
}

RAW_BLOCK = cko.FeatureSpec("raw115_block", "raw", "Raw Kitsune115D evidence encoder.")
MECH_BLOCK = cko.FeatureSpec("mechanism_block", "mechanism", "Processed CSV mechanism evidence encoder.")

CONTROL_SPECS = [
    cko.FeatureSpec("C0_raw115_control", "raw", "C4 raw115 control under this runner."),
    cko.FeatureSpec(
        "C1_raw115_plus_mechanism_naive",
        "raw_plus_mechanism",
        "Naive raw115+mechanism concat control.",
    ),
]


@dataclass(frozen=True)
class EvidenceCandidate:
    name: str
    include_margins: bool
    meta_model: str
    description: str


EVIDENCE_CANDIDATES = [
    EvidenceCandidate(
        "S1_stack_probs_oof_histgb",
        include_margins=False,
        meta_model="histgb_shallow",
        description="OOF raw/mechanism class-probability evidence -> one four-class HistGB head.",
    ),
    EvidenceCandidate(
        "S2_stack_probs_margins_oof_histgb",
        include_margins=True,
        meta_model="histgb_shallow",
        description="OOF class-probability evidence plus attack/OOD disagreement margins -> one four-class HistGB head.",
    ),
]


def fit_chunks(frame_by_role: dict[str, pd.DataFrame], train_cap: int) -> tuple[list[dict[str, Any]], np.ndarray, list[dict[str, Any]]]:
    chunks: list[dict[str, Any]] = []
    ys: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []

    def add(role: str, phase: str, label: int, cap: int) -> None:
        idx = cko.role_indices(frame_by_role, role, phase, cap)
        chunks.append({"role": role, "phase": phase, "label": label, "idx": idx})
        ys.append(np.full(len(idx), label, dtype=np.int64))
        audit.append(
            {
                "role": role,
                "phase": phase,
                "label": label,
                "label_name": CLASS_NAMES[label],
                "rows": len(idx),
            }
        )

    add("support_train", "fit", ckh.CLASS_ATTACK, cko.FULL_CAP)
    add("id_calib", "fit", ckh.CLASS_ID, train_cap)
    add("ood_val", "fit", ckh.CLASS_OOD, train_cap)
    add("ood_stress", "fit", ckh.CLASS_HARD_OOD, train_cap)
    return chunks, np.concatenate(ys), audit


def matrix_for_chunks(builder: cko.FeatureBuilder, spec: cko.FeatureSpec, chunks: list[dict[str, Any]]) -> np.ndarray:
    parts = [builder.matrix(spec, str(chunk["role"]), np.asarray(chunk["idx"], dtype=np.int64)) for chunk in chunks]
    return np.vstack(parts).astype(np.float32)


def proba4(model: Any, x: np.ndarray) -> np.ndarray:
    proba = model.predict_proba(np.asarray(x, dtype=np.float32))
    classes = list(model.classes_)
    out = np.zeros((len(x), len(CLASS_LABELS)), dtype=np.float64)
    for j, label in enumerate(CLASS_LABELS):
        if label in classes:
            out[:, j] = proba[:, classes.index(label)]
    return out


def entropy4(proba: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(proba, dtype=np.float64), 1e-12, 1.0)
    return -np.sum(p * np.log(p), axis=1)


def evidence_from_block_probas(probas: dict[str, np.ndarray], include_margins: bool) -> np.ndarray:
    raw = probas["raw"]
    mech = probas["mechanism"]
    blocks: list[np.ndarray] = [raw, mech]
    if include_margins:
        raw_attack = raw[:, ckh.CLASS_ATTACK]
        raw_conflict = np.maximum.reduce([raw[:, ckh.CLASS_ID], raw[:, ckh.CLASS_OOD], raw[:, ckh.CLASS_HARD_OOD]])
        mech_attack = mech[:, ckh.CLASS_ATTACK]
        mech_conflict = np.maximum.reduce([mech[:, ckh.CLASS_ID], mech[:, ckh.CLASS_OOD], mech[:, ckh.CLASS_HARD_OOD]])
        margin = np.column_stack(
            [
                raw_attack - raw_conflict,
                mech_attack - mech_conflict,
                raw[:, ckh.CLASS_HARD_OOD] - raw_attack,
                mech[:, ckh.CLASS_HARD_OOD] - mech_attack,
                raw[:, ckh.CLASS_OOD] - raw_attack,
                mech[:, ckh.CLASS_OOD] - mech_attack,
                raw_attack - mech_attack,
                raw_conflict - mech_conflict,
                np.abs(raw_attack - mech_attack),
                np.abs(raw_conflict - mech_conflict),
                entropy4(raw),
                entropy4(mech),
            ]
        )
        blocks.append(margin)
    return np.hstack(blocks).astype(np.float32)


def fit_block_oof_and_full(
    block_name: str,
    x: np.ndarray,
    y: np.ndarray,
    n_splits: int,
) -> tuple[np.ndarray, Any, list[dict[str, Any]]]:
    oof = np.zeros((len(y), len(CLASS_LABELS)), dtype=np.float64)
    rows: list[dict[str, Any]] = []
    splitter = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=ckh.SEED)
    for fold, (train_idx, val_idx) in enumerate(splitter.split(x, y), start=1):
        model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x[train_idx], y[train_idx])
        oof[val_idx] = proba4(model, x[val_idx])
        pred = np.argmax(oof[val_idx], axis=1)
        rows.append(
            {
                "block": block_name,
                "fold": fold,
                "train_rows": len(train_idx),
                "val_rows": len(val_idx),
                "val_accuracy": float(np.mean(pred == y[val_idx])) if len(val_idx) else float("nan"),
            }
        )
    full_model = ckh.balanced_fit(ckh.build_model("histgb_shallow", multiclass=True), x, y)
    return oof, full_model, rows


def choose_n_splits(y: np.ndarray) -> int:
    counts = [int(np.sum(y == label)) for label in np.unique(y)]
    return max(2, min(3, min(counts)))


def fit_structured_candidates(
    builder: cko.FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    train_cap: int,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    chunks, y, train_audit = fit_chunks(frame_by_role, train_cap)
    x_raw = matrix_for_chunks(builder, RAW_BLOCK, chunks)
    x_mech = matrix_for_chunks(builder, MECH_BLOCK, chunks)
    n_splits = choose_n_splits(y)

    raw_oof, raw_full, raw_rows = fit_block_oof_and_full("raw", x_raw, y, n_splits)
    mech_oof, mech_full, mech_rows = fit_block_oof_and_full("mechanism", x_mech, y, n_splits)
    oof_probas = {"raw": raw_oof, "mechanism": mech_oof}

    fitted: dict[str, dict[str, Any]] = {}
    meta_rows: list[dict[str, Any]] = []
    for candidate in EVIDENCE_CANDIDATES:
        x_meta = evidence_from_block_probas(oof_probas, candidate.include_margins)
        meta = ckh.balanced_fit(ckh.build_model(candidate.meta_model, multiclass=True), x_meta, y)
        meta_train_proba = proba4(meta, x_meta)
        meta_pred = np.argmax(meta_train_proba, axis=1)
        meta_rows.append(
            {
                "candidate": candidate.name,
                "meta_model": candidate.meta_model,
                "include_margins": candidate.include_margins,
                "meta_train_rows": len(y),
                "meta_feature_dim": x_meta.shape[1],
                "oof_meta_accuracy": float(np.mean(meta_pred == y)) if len(y) else float("nan"),
                "note": "meta head trained on out-of-fold block evidence only",
            }
        )
        fitted[candidate.name] = {
            "candidate": candidate,
            "block_models": {"raw": raw_full, "mechanism": mech_full},
            "meta": meta,
        }
    for row in train_audit:
        row["candidate"] = "structured_evidence_shared_fit_set"
    return fitted, train_audit, raw_rows + mech_rows + meta_rows


def structured_scores(fitted: dict[str, Any], builder: cko.FeatureBuilder, role: str, idx: np.ndarray) -> dict[str, np.ndarray]:
    candidate: EvidenceCandidate = fitted["candidate"]
    raw_x = builder.matrix(RAW_BLOCK, role, idx)
    mech_x = builder.matrix(MECH_BLOCK, role, idx)
    probas = {
        "raw": proba4(fitted["block_models"]["raw"], raw_x),
        "mechanism": proba4(fitted["block_models"]["mechanism"], mech_x),
    }
    x_meta = evidence_from_block_probas(probas, candidate.include_margins)
    meta_proba = proba4(fitted["meta"], x_meta)
    attack = meta_proba[:, ckh.CLASS_ATTACK]
    hard_ood = meta_proba[:, ckh.CLASS_HARD_OOD]
    ood = meta_proba[:, ckh.CLASS_OOD]
    identity = meta_proba[:, ckh.CLASS_ID]
    return {
        "attack_score": attack,
        "hard_ood_score": hard_ood,
        "conflict_score": np.maximum.reduce([identity, ood, hard_ood]),
        "id_score": identity,
        "ood_score": ood,
    }


def structured_threshold(
    fitted: dict[str, Any],
    builder: cko.FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> float:
    parts = []
    for role in ["id_calib", "ood_val", "ood_stress"]:
        idx = cko.role_indices(frame_by_role, role, "select", eval_cap)
        parts.append(structured_scores(fitted, builder, role, idx)["attack_score"])
    return float(max(np.quantile(part, cko.BENIGN_SAFE_Q) for part in parts))


def eval_structured_role(
    candidate_name: str,
    fitted: dict[str, Any],
    threshold: float,
    role: str,
    phase: str,
    role_kind: str,
    builder: cko.FeatureBuilder,
    frame_by_role: dict[str, pd.DataFrame],
    eval_cap: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    idx = cko.role_indices(frame_by_role, role, phase, eval_cap)
    score = structured_scores(fitted, builder, role, idx)
    raw = score["attack_score"] > threshold
    conflict = raw & (score["conflict_score"] > score["attack_score"])
    hard = raw & (~conflict)
    part = frame_by_role[role].iloc[idx].copy().reset_index(drop=True)
    for key, val in score.items():
        part[key] = val
    part["raw_alarm"] = raw
    part["conflict_review"] = conflict
    part["hard_alarm"] = hard
    return (
        {
            "feature_set": candidate_name,
            "role": role,
            "phase": phase,
            "role_kind": role_kind,
            "rows": len(part),
            "attack_threshold": threshold,
            "raw_alarm_rate": ckg.rate(raw),
            "conflict_review_rate": ckg.rate(conflict),
            "hard_alarm_rate": ckg.rate(hard),
            "attack_score_mean": float(np.mean(score["attack_score"])) if len(part) else float("nan"),
            "conflict_score_mean": float(np.mean(score["conflict_score"])) if len(part) else float("nan"),
        },
        part,
    )


def build_readout(matrix: list[dict[str, Any]], seconds: float, smoke: bool) -> list[str]:
    lines = [
        "# issue27ckp structured evidence frontend v1",
        "",
        "## Scope",
        "",
        "Fixed final decision form: one four-class head over structured evidence.",
        "Block encoders: raw115 and mechanism-only four-class HistGB encoders.",
        "Fusion head: four-class HistGB trained on out-of-fold block evidence.",
        f"Mode: `{'smoke' if smoke else 'full'}`.",
        "",
        "## Main matrix",
        "",
        "| candidate | future hard | same-file hard | sealed attack hard/review | sealed OOD hard/review | sealed OOD group hard max | OOD-stress hard/review |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in matrix:
        lines.append(
            f"| {row['feature_set']} | {cko.fmt(row['future_hard'])} | {cko.fmt(row['same_file_hard'])} | "
            f"{cko.fmt(row['sealed_attack_hard'])}/{cko.fmt(row['sealed_attack_review'])} | "
            f"{cko.fmt(row['sealed_ood_hard'])}/{cko.fmt(row['sealed_ood_review'])} | "
            f"{cko.fmt(row['sealed_ood_group_hard_max'])} | "
            f"{cko.fmt(row['ood_stress_hard'])}/{cko.fmt(row['ood_stress_review'])} |"
        )
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            "- The structured head only succeeds if it reduces OOD review/hard without losing future/sealed attack hard detection.",
            "- OOF evidence is used for meta training to avoid row-level leakage from block encoders into the fusion head.",
            "- Query/future/final/report-only rows remain report-only.",
            "",
            f"Runtime seconds: `{cko.fmt(seconds, 1)}`.",
        ]
    )
    return lines


def run(args: argparse.Namespace) -> None:
    started = time.time()
    OUT.mkdir(parents=True, exist_ok=True)
    x_by_role, frame_by_role, input_audit, _support_labels = cko.load_role_inputs(args.smoke)
    train_cap = cko.SMOKE_TRAIN_CAP if args.smoke else cko.TRAIN_CAP
    eval_cap = cko.SMOKE_EVAL_CAP if args.smoke else cko.FULL_CAP
    cache = cko.MechanismZipFeatureCache(cko.GOTHAM_ZIP, smoke=args.smoke)
    builder = cko.FeatureBuilder(x_by_role, frame_by_role, cache)
    builder.precompute_roles(list(frame_by_role.keys()))

    role_rows: list[dict[str, Any]] = []
    group_metrics: list[dict[str, Any]] = []
    train_rows: list[dict[str, Any]] = []
    oof_rows: list[dict[str, Any]] = []

    for spec in CONTROL_SPECS:
        model, audit = cko.fit_spec(spec, builder, frame_by_role, train_cap)
        threshold = cko.threshold_for(spec, model, builder, frame_by_role, eval_cap)
        for row in audit:
            row["candidate"] = spec.name
            row["label_name"] = CLASS_NAMES.get(int(row["label"]), "")
            train_rows.append(row)
        for role, phase, kind in cko.ROLE_EVAL:
            row, part = cko.eval_role(spec, model, threshold, role, phase, kind, builder, frame_by_role, eval_cap)
            role_rows.append(row)
            group_metrics.extend(cko.group_rows(spec, role, part))

    structured, structured_train_rows, structured_oof_rows = fit_structured_candidates(builder, frame_by_role, train_cap)
    train_rows.extend(structured_train_rows)
    oof_rows.extend(structured_oof_rows)
    for name, fitted in structured.items():
        threshold = structured_threshold(fitted, builder, frame_by_role, eval_cap)
        spec = cko.FeatureSpec(name, "structured_evidence", fitted["candidate"].description)
        for role, phase, kind in cko.ROLE_EVAL:
            row, part = eval_structured_role(name, fitted, threshold, role, phase, kind, builder, frame_by_role, eval_cap)
            role_rows.append(row)
            group_metrics.extend(cko.group_rows(spec, role, part))

    matrix = cko.aggregate(role_rows, group_metrics)
    alignment_rows = cko.build_alignment_audit(builder, x_by_role, frame_by_role)
    seconds = time.time() - started

    cko.write_csv(
        OUT / "candidate_matrix.csv",
        [
            {"name": spec.name, "kind": spec.kind, "description": spec.description, "candidate_type": "control"}
            for spec in CONTROL_SPECS
        ]
        + [
            {
                "name": c.name,
                "kind": "structured_evidence",
                "description": c.description,
                "candidate_type": "structured",
                "include_margins": c.include_margins,
                "meta_model": c.meta_model,
            }
            for c in EVIDENCE_CANDIDATES
        ],
    )
    cko.write_csv(OUT / "train_audit.csv", train_rows)
    cko.write_csv(OUT / "oof_evidence_audit.csv", oof_rows)
    cko.write_csv(OUT / "role_metrics.csv", role_rows)
    cko.write_csv(OUT / "group_metrics_by_source_device.csv", group_metrics)
    cko.write_csv(OUT / "mechanism_extraction_audit.csv", cache.audit_rows)
    cko.write_csv(OUT / "alignment_audit.csv", alignment_rows)
    cko.write_csv(OUT / "candidate_summary_matrix.csv", matrix)
    cko.write_json(
        OUT / "run_spec.json",
        {
            "issue": ISSUE,
            "scope": "structured evidence frontend v1; evidence encoders plus one four-class fusion head",
            "smoke": args.smoke,
            "train_cap": train_cap,
            "eval_cap": eval_cap,
            "control_specs": [spec.__dict__ for spec in CONTROL_SPECS],
            "evidence_candidates": [asdict(c) for c in EVIDENCE_CANDIDATES],
            "data_use_boundary": {
                "block_encoder_fit_roles": ["support_train fit", "id_calib fit", "ood_val fit", "ood_stress fit"],
                "fusion_head_fit_roles": ["OOF evidence from support_train/id_calib/ood_val/ood_stress fit only"],
                "threshold_roles": ["id_calib select", "ood_val select", "ood_stress select"],
                "report_only_roles_used_for_training": False,
                "alignment_audit_used_for_training": False,
                "processed_label_used_as_feature": False,
            },
            "input_audit": input_audit,
            "alignment_audit": {
                "sample_per_role": cko.ALIGNMENT_AUDIT_SAMPLE_PER_ROLE,
                "rows": len(alignment_rows),
                "purpose": "report-only raw115-to-mechanism row pairing evidence",
            },
            "outputs": [
                "candidate_summary_matrix.csv",
                "role_metrics.csv",
                "group_metrics_by_source_device.csv",
                "train_audit.csv",
                "oof_evidence_audit.csv",
                "mechanism_extraction_audit.csv",
                "alignment_audit.csv",
                "codex_readout.md",
            ],
            "seconds": seconds,
        },
    )
    cko.write_md(OUT / "codex_readout.md", build_readout(matrix, seconds, args.smoke))
    print(json.dumps({"status": "ok", "out": str(OUT), "seconds": seconds, "smoke": args.smoke}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
