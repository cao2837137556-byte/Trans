#!/usr/bin/env python3
"""CKDE D1 Stage-P fit-attack-only cap materialization.

This program is intentionally Python 3.9 compatible.  It reconstructs frozen
P2 scores only for the 4,385 legal fit attacks and emits the complete threshold
frontier plus per-family recall-loss table.  It never computes a benign,
support-val, report, or FINAL score.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import traceback
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np


CONTRACT_REL = Path(
    "runs/mainline_docs/"
    "ckde_d1_development_commissioning_calibration_preregistered_precap_20260825.md"
)
CONTRACT_SHA256 = "9e7a4904dc72c0a7f81a5510e26432128478f0a17101acbece433870804697c9"
SCOPE_REL = Path("runs/mainline_docs/ckcz_attack_family_scope_clarification_20260809.md")
SCOPE_SHA256 = "09962ec34a5a4657be9fd39fcde9adeb70ffedbbe74846df8e4f89761a2b3536"
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINNED = {
    "fit_select_plan": (
        "ckda_d1_fit_select_plan.csv",
        "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac",
    ),
    "fit_select_embeddings": (
        "ckda_d1_fit_select_embeddings.npz",
        "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099",
    ),
    "probe_state": (
        "ckda_d1_probe_state.npz",
        "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38",
    ),
    "threshold_marker": (
        "ckda_d1_threshold_freeze_marker.json",
        "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b",
    ),
}

FIT_ATTACK_ROLES = {"aux_process_fit", "support_train"}
EXPECTED_ROLE_COUNTS = {"aux_process_fit": 4000, "support_train": 385}
EXPECTED_FIT_ATTACK_ROWS = 4385
EXPECTED_PLAN_ROWS = 25467
THETA_0 = 0.065159872174263
GLOBAL_LOSS_GATE_PP = 0.5
FAMILY_LOSS_GATE_PP = 2.0
FAMILY_MIN_ROWS = 15

# CKCZ reporting taxonomy.  Exact ToN strata are kept separately and are never
# mapped into this taxonomy; both scopes were already frozen by the clarification.
CKCZ_REPORT_FAMILIES = {
    "C&C Communication",
    "CoAP Amplification",
    "File Download",
    "Ingress Tool Transfer",
    "Merlin C&C Communication",
    "Merlin ICMP Flooding",
    "Merlin TCP Flooding",
    "Merlin UDP Flooding",
    "Mirai C&C Communication",
    "Mirai GRE Flooding",
    "Mirai TCP Flooding",
    "Mirai UDP Flooding",
    "Reporting",
    "TCP Scan",
    "Telnet Brute Force",
    "UDP Scan",
}
CKBW_TON_FIT_STRATA = {"ToN-credential_bruteforce", "ToN-reconnaissance_scan"}
ALLOWED_FIT_FAMILY_LABELS = CKCZ_REPORT_FAMILIES | CKBW_TON_FIT_STRATA


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch: %s" % path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temp), str(path))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(str(temp), str(path))


def canonical_float(value: float) -> str:
    return format(float(value), ".17g")


def frozen_p2_scores(
    representations: np.ndarray, missing: np.ndarray, state: Mapping[str, np.ndarray]
) -> np.ndarray:
    """Reconstruct the already-frozen P2 head without fitting any parameter."""
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    if mean.shape != (768,) or scale.shape != (768,) or np.any(scale <= 0):
        raise RuntimeError("frozen normalizer shape/value drift")
    values = (np.asarray(representations, dtype=np.float64) - mean) / scale
    missing_bool = np.asarray(missing, dtype=bool)
    values[missing_bool] = 0.0
    x = np.concatenate((values, missing_bool.astype(np.float64)[:, None]), axis=1)
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float64)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float64)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float64).reshape(-1)
    b2 = float(np.asarray(state["p2__3.bias"], dtype=np.float64).reshape(-1)[0])
    if w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (128,):
        raise RuntimeError("frozen P2 shape drift")
    hidden = np.maximum(0.0, x.dot(w1.T) + b1)
    logits = hidden.dot(w2) + b2
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))
    if scores.shape != (len(representations),) or not np.isfinite(scores).all():
        raise RuntimeError("non-finite or malformed fit-attack score vector")
    return scores


def hard_count(sorted_scores: np.ndarray, threshold: float) -> int:
    """Count score >= threshold; left insertion preserves exact ties as hard."""
    return int(len(sorted_scores) - np.searchsorted(sorted_scores, threshold, side="left"))


def build_frontier(
    scores: np.ndarray, families: Sequence[str], theta_0: float = THETA_0
) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Dict[str, object]]:
    scores = np.asarray(scores, dtype=np.float64)
    family_values = np.asarray(list(families), dtype=str)
    if len(scores) != len(family_values) or not len(scores):
        raise RuntimeError("score/family denominator mismatch")
    if not np.isfinite(scores).all() or not math.isfinite(theta_0):
        raise RuntimeError("cap frontier requires finite scores and theta_0")
    unknown = sorted(set(family_values) - ALLOWED_FIT_FAMILY_LABELS)
    if unknown:
        raise RuntimeError("unfrozen fit family label(s): %s" % unknown)

    candidates = sorted(set([float(theta_0)] + [float(x) for x in scores if x >= theta_0]))
    global_sorted = np.sort(scores)
    baseline_global_hard = hard_count(global_sorted, theta_0)
    baseline_global_recall = baseline_global_hard / float(len(scores))
    family_counts = Counter(str(x) for x in family_values)
    family_sorted = {
        name: np.sort(scores[family_values == name]) for name in sorted(family_counts)
    }
    baseline_family_hard = {
        name: hard_count(values, theta_0) for name, values in family_sorted.items()
    }

    frontier_rows: List[Dict[str, object]] = []
    family_rows: List[Dict[str, object]] = []
    admissible_thresholds: List[float] = []
    tolerance = 1e-12
    for rank, threshold in enumerate(candidates):
        global_hard = hard_count(global_sorted, threshold)
        global_recall = global_hard / float(len(scores))
        global_loss_pp = (baseline_global_recall - global_recall) * 100.0
        maximum_eligible_family_loss = 0.0
        eligible_family_count = 0
        family_pass = True
        for name, values in family_sorted.items():
            rows = len(values)
            hard = hard_count(values, threshold)
            baseline_recall = baseline_family_hard[name] / float(rows)
            recall = hard / float(rows)
            loss_pp = (baseline_recall - recall) * 100.0
            eligible = rows >= FAMILY_MIN_ROWS
            scope = (
                "CKCZ_REPORT_FAMILY"
                if name in CKCZ_REPORT_FAMILIES
                else "CKBW_TON_FIT_STRATUM_EXACT_NO_MAPPING"
            )
            if eligible:
                eligible_family_count += 1
                maximum_eligible_family_loss = max(maximum_eligible_family_loss, loss_pp)
                if loss_pp > FAMILY_LOSS_GATE_PP + tolerance:
                    family_pass = False
            family_rows.append(
                {
                    "candidate_rank_ascending": rank,
                    "threshold": canonical_float(threshold),
                    "attack_family": name,
                    "family_scope": scope,
                    "rows": rows,
                    "gate_eligible_rows_ge_15": str(bool(eligible)).lower(),
                    "baseline_hard": baseline_family_hard[name],
                    "candidate_hard": hard,
                    "baseline_recall": canonical_float(baseline_recall),
                    "candidate_recall": canonical_float(recall),
                    "recall_loss_pp": canonical_float(loss_pp),
                    "family_gate_pass": str((not eligible) or loss_pp <= FAMILY_LOSS_GATE_PP + tolerance).lower(),
                }
            )
        global_pass = global_loss_pp <= GLOBAL_LOSS_GATE_PP + tolerance
        admissible = bool(global_pass and family_pass)
        if admissible:
            admissible_thresholds.append(float(threshold))
        frontier_rows.append(
            {
                "candidate_rank_ascending": rank,
                "threshold": canonical_float(threshold),
                "global_rows": len(scores),
                "baseline_global_hard": baseline_global_hard,
                "candidate_global_hard": global_hard,
                "baseline_global_recall": canonical_float(baseline_global_recall),
                "candidate_global_recall": canonical_float(global_recall),
                "global_recall_loss_pp": canonical_float(global_loss_pp),
                "eligible_family_count": eligible_family_count,
                "max_eligible_family_recall_loss_pp": canonical_float(maximum_eligible_family_loss),
                "global_gate_pass": str(global_pass).lower(),
                "all_family_gates_pass": str(family_pass).lower(),
                "admissible": str(admissible).lower(),
            }
        )

    if not admissible_thresholds:
        raise RuntimeError("theta_0 was not admissible; frozen cap contract is inconsistent")
    t_cap = max(admissible_thresholds)
    selected = frontier_rows[candidates.index(t_cap)]
    verdict = {
        "status": "CKDE_D1_CAP_MATERIALIZED",
        "theta_0": float(theta_0),
        "theta_0_canonical": canonical_float(theta_0),
        "T_cap": float(t_cap),
        "T_cap_canonical": canonical_float(t_cap),
        "cap_fit_attack": float(t_cap - theta_0),
        "cap_fit_attack_canonical": canonical_float(t_cap - theta_0),
        "fit_attack_rows": len(scores),
        "candidate_thresholds": len(candidates),
        "admissible_thresholds": len(admissible_thresholds),
        "baseline_global_hard": baseline_global_hard,
        "T_cap_global_hard": int(selected["candidate_global_hard"]),
        "T_cap_global_recall_loss_pp": float(selected["global_recall_loss_pp"]),
        "T_cap_max_eligible_family_recall_loss_pp": float(
            selected["max_eligible_family_recall_loss_pp"]
        ),
        "exact_ties_remain_hard": True,
        "fit_family_labels_are_exact_unmapped_values": True,
    }
    return frontier_rows, family_rows, verdict


def read_plan_fit_attacks(path: Path) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != EXPECTED_PLAN_ROWS:
        raise RuntimeError("fit/select plan row-count drift")
    uids = [row["uid"] for row in rows]
    if len(set(uids)) != len(uids):
        raise RuntimeError("fit/select plan UID duplication")
    fit = [
        row
        for row in rows
        if row["role"] in FIT_ATTACK_ROLES and int(row["label_metric_only"]) == 1
    ]
    role_counts = Counter(row["role"] for row in fit)
    if len(fit) != EXPECTED_FIT_ATTACK_ROWS or dict(role_counts) != EXPECTED_ROLE_COUNTS:
        raise RuntimeError("4,385 fit-attack denominator drift: %s" % dict(role_counts))
    unknown = sorted({row["attack_family"] for row in fit} - ALLOWED_FIT_FAMILY_LABELS)
    if unknown:
        raise RuntimeError("unfrozen fit family label(s): %s" % unknown)
    return fit, {row["uid"]: index for index, row in enumerate(rows)}


def pin_inputs(root: Path) -> Dict[str, object]:
    stage = root / STAGE_REL
    identities: Dict[str, object] = {
        "precap_contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256),
        "family_scope_clarification": require_sha(root / SCOPE_REL, SCOPE_SHA256),
    }
    for key, (name, digest) in PINNED.items():
        identities[key] = require_sha(stage / name, digest)
    return identities


def write_sha256s(out: Path) -> None:
    rows = []
    for path in sorted(out.iterdir(), key=lambda value: value.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append("%s  %s" % (sha256_file(path), path.name))
    atomic_text(out / "SHA256SUMS", "\n".join(rows) + "\n")


def materialize(root: Path, out: Path) -> Dict[str, object]:
    stage_out = out.with_name(".%s.stage" % out.name)
    control = out.with_name("%s_control" % out.name)
    if out.exists() or stage_out.exists():
        raise RuntimeError("refusing to overwrite cap artifact output")
    if control.exists():
        shutil.rmtree(str(control))
    stage_out.mkdir(parents=True, exist_ok=False)
    try:
        identities = pin_inputs(root)
        source_stage = root / STAGE_REL
        fit, plan_positions = read_plan_fit_attacks(source_stage / PINNED["fit_select_plan"][0])
        selected_indices = np.asarray([plan_positions[row["uid"]] for row in fit], dtype=np.int64)

        with np.load(source_stage / PINNED["fit_select_embeddings"][0], allow_pickle=False) as data:
            all_uids = data["uid"].astype(str)
            if len(all_uids) != EXPECTED_PLAN_ROWS or len(set(all_uids)) != len(all_uids):
                raise RuntimeError("embedding UID identity drift")
            embedding_positions = {uid: index for index, uid in enumerate(all_uids)}
            exact_indices = np.asarray([embedding_positions[row["uid"]] for row in fit], dtype=np.int64)
            representations = np.asarray(data["representation"][exact_indices], dtype=np.float32)
            missing = np.asarray(data["missing"][exact_indices], dtype=bool)
        if not np.array_equal(
            np.asarray([all_uids[index] for index in exact_indices], dtype=str),
            np.asarray([row["uid"] for row in fit], dtype=str),
        ):
            raise RuntimeError("fit attack exact UID join failed")
        # The plan order and embedding order are separately joined by UID; the
        # plan-position vector is retained only as an audit invariant.
        if len(selected_indices) != EXPECTED_FIT_ATTACK_ROWS:
            raise RuntimeError("selected plan index drift")

        with np.load(source_stage / PINNED["probe_state"][0], allow_pickle=False) as data:
            state = {name: np.asarray(data[name]) for name in data.files}
        scores = frozen_p2_scores(representations, missing, state)

        marker = json.loads(
            (source_stage / PINNED["threshold_marker"][0]).read_text(encoding="utf-8")
        )
        marker_theta = float(marker["thresholds"]["P2"]["value"])
        if marker_theta != THETA_0:
            raise RuntimeError("theta_0 marker drift")

        families = [row["attack_family"] for row in fit]
        frontier, family_table, verdict = build_frontier(scores, families, marker_theta)
        family_counts = Counter(families)
        audit = {
            "status": "PASS",
            "identities": identities,
            "fit_attack_rows": len(fit),
            "fit_attack_role_counts": dict(sorted(Counter(row["role"] for row in fit).items())),
            "fit_attack_family_counts": dict(sorted(family_counts.items())),
            "gate_eligible_family_count": sum(
                count >= FAMILY_MIN_ROWS for count in family_counts.values()
            ),
            "missing_embedding_rows": int(missing.sum()),
            "finite_fit_attack_scores": int(np.isfinite(scores).sum()),
            "embedding_container_rows": EXPECTED_PLAN_ROWS,
            "embedding_rows_selected_by_exact_uid_before_scoring": len(fit),
            "non_fit_rows_scored": 0,
            "fitted_parameters": 0,
            "optimizer_steps": 0,
            "score_rule": "FROZEN_P2_FLOAT64_RECONSTRUCTION_SCORE_GE_THRESHOLD_TIES_HARD",
        }
        boundary = {
            "status": "PASS",
            "fit_attack_identity_rows_opened": len(fit),
            "fit_attack_scores_computed": len(scores),
            "benign_scores_opened": 0,
            "support_val_scores_opened": 0,
            "report_scores_opened": 0,
            "final_scores_opened": 0,
            "final_files_opened": 0,
            "pcap_files_opened": 0,
            "model_training_performed": False,
            "training_steps": 0,
            "stage": "P_CAP_ONLY_MATERIALIZATION",
        }

        frontier_fields = list(frontier[0].keys())
        family_fields = list(family_table[0].keys())
        atomic_csv(stage_out / "ckde_d1_cap_frontier.csv", frontier_fields, frontier)
        atomic_csv(stage_out / "ckde_d1_cap_family_recall_loss.csv", family_fields, family_table)
        atomic_json(stage_out / "ckde_d1_cap.json", verdict)
        atomic_json(stage_out / "ckde_d1_cap_input_audit.json", audit)
        atomic_json(stage_out / "ckde_d1_cap_boundary_audit.json", boundary)
        validation = {
            "status": "PASS",
            "contract_sha256": CONTRACT_SHA256,
            "fit_attack_rows": len(fit),
            "frontier_rows": len(frontier),
            "family_recall_rows": len(family_table),
            "cap_status": verdict["status"],
            "scientific_verdict_emitted": True,
        }
        atomic_json(stage_out / "ckde_d1_cap_validation_report.json", validation)
        write_sha256s(stage_out)
        os.replace(str(stage_out), str(out))
        return verdict
    except Exception as exc:
        if stage_out.exists():
            shutil.rmtree(str(stage_out))
        control.mkdir(parents=True, exist_ok=True)
        atomic_json(
            control / "engineering_failure.json",
            {
                "status": "ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verdict = materialize(args.root.resolve(), args.out.resolve())
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
