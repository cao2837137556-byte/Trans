#!/usr/bin/env python3
"""CKDE-R D0 representation-commissioning identifiability audit.

The program is deliberately fail-closed.  Audit-0 consumes metadata only and
must finish before the embedding NPZ is opened.  A failed Audit-0 therefore
produces state A and no embedding-derived artifact.
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
from itertools import combinations
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path(
    "runs/mainline_docs/"
    "ckde_r_d0_representation_commissioning_identifiability_preregistered_20260826.md"
)
CONTRACT_SHA256 = "53efc5b13ef64a07e3b4e7e5a5e4e2095e0da92611286c5ff586302c96899d01"
D0_REL = Path("runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local")
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINS = {
    "parent_verdict": (D0_REL / "ckde_d0_verdict.json", "c1953c55d999ac151426d5d9f6fa9fdcbaddfd725fe966ebf09def1c62f47033"),
    "parent_census": (D0_REL / "ckde_d0_device_lineage_census.csv", "9ce04164ce6db9917d9fe8d1dedae612ed727f78460e1db0882afe6dc1d69f9b"),
    "parent_pairing": (D0_REL / "ckde_d0_same_device_pairing.csv", "6f904325c712fcbe081eb8250780d32479862dc468e5fbcaf3d88e3f9667d9ee"),
    "embeddings": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "session_metadata": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "plan": (STAGE_REL / "ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "probe_state": (STAGE_REL / "ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
}

FIT_BENIGN_ROLES = {"id_calib", "aux_fit", "aux_normal_fit"}
FIT_ATTACK_ROLES = {"support_train", "aux_process_fit"}
FORBIDDEN_ROLES = {"support_val", "report", "final"}
EXPECTED_ROWS = 25467
WIDTH = 768
MIN_BENIGN_SESSIONS = 64
MIN_ATTACK_SESSIONS = 15
BOOTSTRAPS = 1000
LAMBDA_CENTER = 0.50
LAMBDA_SCALE = 0.25
CENTER_MACRO_GATE = 0.15
CENTER_WORST_GATE = 0.35
SCALE_MACRO_GATE = 0.10
SCALE_WORST_GATE = 0.25
ENTANGLEMENT_GATE = 0.25
THETA_0 = 0.065159872174263

EMBEDDING_OUTPUTS = {
    "ckde_r_d0_session_denominators.csv",
    "ckde_r_d0_global_reference_audit.json",
    "ckde_r_d0_bootstrap_stability_by_device.csv",
    "ckde_r_d0_stability_summary.json",
    "ckde_r_d0_entanglement_pairs.csv",
    "ckde_r_d0_entanglement_bootstrap.json",
    "ckde_r_d0_synthetic_shift_attack_metrics.csv",
    "ckde_r_d0_non_degeneracy_diagnostic.csv",
}


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


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    frame.to_csv(temp, index=False, lineterminator="\n")
    os.replace(str(temp), str(path))


def pin_inputs(root: Path) -> Dict[str, object]:
    identities: Dict[str, object] = {
        "contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256)
    }
    for key, (relative, digest) in PINS.items():
        identities[key] = require_sha(root / relative, digest)
    return identities


def bool_value(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def load_metadata_only(root: Path) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    plan = pd.read_csv(root / PINS["plan"][0])
    metadata = pd.read_csv(root / PINS["session_metadata"][0])
    census = pd.read_csv(root / PINS["parent_census"][0])
    required_plan = {
        "uid", "role", "source_group", "attack_family", "recorded_index",
        "label_metric_only",
    }
    required_meta = {"uid", "session_id", "timestamp_epoch", "event_position"}
    required_census = {"device_key", "lineage_stable", "causal_prefix_and_suffix_identifiable"}
    if not required_plan.issubset(plan.columns):
        raise RuntimeError("plan schema drift")
    if not required_meta.issubset(metadata.columns):
        raise RuntimeError("session metadata schema drift")
    if not required_census.issubset(census.columns):
        raise RuntimeError("parent census schema drift")
    if len(plan) != EXPECTED_ROWS or len(metadata) != EXPECTED_ROWS:
        raise RuntimeError("fit/select denominator drift")
    if not plan["uid"].is_unique or not metadata["uid"].is_unique:
        raise RuntimeError("UID duplication")
    joined = plan.merge(metadata, on="uid", how="left", validate="one_to_one")
    if len(joined) != EXPECTED_ROWS or joined["session_id"].isna().any():
        raise RuntimeError("exact metadata UID join failure")
    return joined, plan, census


def session_table(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame(columns=["source_group", "session_id", "first_event", "last_event", "records"])
    return (
        rows.groupby(["source_group", "session_id"], sort=True)["event_position"]
        .agg(first_event="min", last_event="max", records="size")
        .reset_index()
    )


def audit0(
    joined: pd.DataFrame, census: pd.DataFrame
) -> Tuple[pd.DataFrame, Dict[str, object], Dict[str, object]]:
    census_map = {
        str(row.device_key): {
            "lineage_stable": bool_value(row.lineage_stable),
            "causal_benign": bool_value(row.causal_prefix_and_suffix_identifiable),
        }
        for row in census.itertuples(index=False)
    }
    attack_rows = joined.loc[joined["role"].isin(FIT_ATTACK_ROLES)].copy()
    benign_rows = joined.loc[joined["role"].isin(FIT_BENIGN_ROLES)].copy()
    attack_devices = sorted(set(attack_rows["source_group"].astype(str)))
    reasons: Set[str] = set()
    incidence: List[Dict[str, object]] = []
    eligible_cells: Set[Tuple[str, str]] = set()
    device_benign_counts: Dict[str, int] = {}

    benign_sessions = session_table(benign_rows)
    for device in attack_devices:
        device_attack = attack_rows.loc[attack_rows["source_group"].astype(str).eq(device)].copy()
        mapped = device in census_map and census_map[device]["lineage_stable"]
        if not mapped:
            reasons.add("ATTACK_DEVICE_UNMAPPED")
        first_attack = float(device_attack["event_position"].min())
        prior = benign_sessions.loc[
            benign_sessions["source_group"].astype(str).eq(device)
            & benign_sessions["last_event"].lt(first_attack)
        ]
        prior_count = int(len(prior))
        device_benign_counts[device] = prior_count
        center_ok = mapped and prior_count >= MIN_BENIGN_SESSIONS
        if not center_ok:
            reasons.add("NO_SAME_DEVICE_FIT_BENIGN_CENTER")
        for family, part in device_attack.groupby("attack_family", sort=True):
            sessions = int(part["session_id"].nunique())
            cell_ok = bool(center_ok and sessions >= MIN_ATTACK_SESSIONS)
            if sessions < MIN_ATTACK_SESSIONS:
                reasons.add("INSUFFICIENT_ATTACK_SESSIONS_PER_CELL")
            if cell_ok:
                eligible_cells.add((device, str(family)))
            incidence.append(
                {
                    "device_key": device,
                    "attack_family": str(family),
                    "attack_records": int(len(part)),
                    "attack_independent_sessions": sessions,
                    "prior_fit_benign_sessions": prior_count,
                    "lineage_stable": mapped,
                    "eligible_cell": cell_ok,
                }
            )

    cycles: List[Dict[str, object]] = []
    families_by_device: Dict[str, Set[str]] = {}
    for device, family in eligible_cells:
        families_by_device.setdefault(device, set()).add(family)
    for d1, d2 in combinations(sorted(families_by_device), 2):
        shared = sorted(families_by_device[d1] & families_by_device[d2])
        for f1, f2 in combinations(shared, 2):
            cycles.append({"device_1": d1, "device_2": d2, "family_1": f1, "family_2": f2})
    if not cycles:
        reasons.add("NO_TWO_BY_TWO_DEVICE_FAMILY_CYCLE")
        if eligible_cells:
            reasons.add("DEVICE_FAMILY_CONFOUNDED")

    passed = bool(attack_devices and not reasons and cycles)
    graph = {
        "status": "PASS" if passed else "FAIL",
        "attack_devices": len(attack_devices),
        "eligible_device_family_cells": len(eligible_cells),
        "two_by_two_cycles": len(cycles),
        "cycles": cycles,
        "reason_codes": sorted(reasons),
        "minimum_prior_fit_benign_sessions": MIN_BENIGN_SESSIONS,
        "minimum_attack_sessions_per_cell": MIN_ATTACK_SESSIONS,
    }
    audit = {
        "audit0_pass": passed,
        "attack_records": int(len(attack_rows)),
        "attack_devices": len(attack_devices),
        "fit_benign_records": int(len(benign_rows)),
        "fit_benign_devices": int(benign_rows["source_group"].nunique()),
        "device_prior_benign_session_counts": dict(sorted(device_benign_counts.items())),
    }
    frame = pd.DataFrame(incidence)
    if frame.empty:
        frame = pd.DataFrame(
            columns=[
                "device_key", "attack_family", "attack_records",
                "attack_independent_sessions", "prior_fit_benign_sessions",
                "lineage_stable", "eligible_cell",
            ]
        )
    return frame, graph, audit


def higher_percentile(values: Sequence[float], q: float = 0.95) -> float:
    ordered = np.sort(np.asarray(values, dtype=np.float64))
    if not len(ordered):
        raise RuntimeError("empty percentile input")
    index = int(math.ceil(len(ordered) * q) - 1)
    return float(ordered[index])


def seed64(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def robust_reference(vectors: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(vectors, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != WIDTH or not np.isfinite(values).all():
        raise RuntimeError("invalid session representation matrix")
    center = np.median(values, axis=0)
    scale = np.maximum(1.4826 * np.median(np.abs(values - center), axis=0), 1e-6)
    return center, scale


def device_estimate(vectors: np.ndarray, mu_g: np.ndarray, sigma_g: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(vectors, dtype=np.float64)
    raw_center = np.median(values, axis=0)
    raw_scale = np.maximum(
        1.4826 * np.median(np.abs(values - raw_center), axis=0), 0.10 * sigma_g
    )
    center = mu_g + LAMBDA_CENTER * (raw_center - mu_g)
    log_scale = np.log(sigma_g) + LAMBDA_SCALE * (np.log(raw_scale) - np.log(sigma_g))
    return center, log_scale


def bootstrap_stability(
    device: str, vectors: np.ndarray, mu_g: np.ndarray, sigma_g: np.ndarray
) -> Dict[str, object]:
    values = np.asarray(vectors, dtype=np.float64)
    if values.shape != (MIN_BENIGN_SESSIONS, WIDTH):
        raise RuntimeError("device bootstrap requires exactly 64x768")
    full_center, full_log_scale = device_estimate(values, mu_g, sigma_g)
    center_errors: List[float] = []
    scale_errors: List[float] = []
    for replicate in range(BOOTSTRAPS):
        rng = np.random.default_rng(seed64("CKDE-R-D0|%s|%d" % (device, replicate)))
        sample = values[rng.integers(0, len(values), size=len(values))]
        center, log_scale = device_estimate(sample, mu_g, sigma_g)
        center_errors.append(float(np.sqrt(np.mean(((center - full_center) / sigma_g) ** 2))))
        scale_errors.append(float(np.sqrt(np.mean((log_scale - full_log_scale) ** 2))))
    return {
        "device_key": device,
        "sessions": len(values),
        "q95_center": higher_percentile(center_errors),
        "q95_scale": higher_percentile(scale_errors),
    }


def choose_stability(rows: pd.DataFrame) -> Tuple[str, Dict[str, object]]:
    if rows.empty:
        raise RuntimeError("no stability rows")
    required = int(math.ceil(0.80 * len(rows)))
    center_count = int(rows["q95_center"].le(CENTER_MACRO_GATE).sum())
    center_worst = float(rows["q95_center"].max())
    center_pass = center_count >= required and center_worst <= CENTER_WORST_GATE
    scale_count = int(rows["q95_scale"].le(SCALE_MACRO_GATE).sum())
    scale_worst = float(rows["q95_scale"].max())
    scale_pass = center_pass and scale_count >= required and scale_worst <= SCALE_WORST_GATE
    candidate = "DIAGONAL_AFFINE" if scale_pass else ("CENTER_ONLY" if center_pass else "NONE")
    return candidate, {
        "eligible_devices": len(rows),
        "required_80_percent_devices": required,
        "center_devices_at_or_below_0_15": center_count,
        "center_worst": center_worst,
        "center_pass": center_pass,
        "scale_devices_at_or_below_0_10": scale_count,
        "scale_worst": scale_worst,
        "scale_pass": scale_pass,
        "provisional_class": candidate,
    }


def cosine_projection(delta_a: np.ndarray, delta_b: np.ndarray) -> Tuple[float, float]:
    a = np.asarray(delta_a, dtype=np.float64)
    b = np.asarray(delta_b, dtype=np.float64)
    norm_a = float(np.linalg.norm(a))
    norm_b = float(np.linalg.norm(b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise RuntimeError("zero-norm entanglement pair")
    dot = float(np.dot(a, b))
    return dot / (norm_a * norm_b), max(0.0, dot / (norm_b * norm_b))


def frozen_p2_scores(representations: np.ndarray, missing: np.ndarray, state: Mapping[str, np.ndarray]) -> np.ndarray:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    if mean.shape != (WIDTH,) or scale.shape != (WIDTH,) or np.any(scale <= 0):
        raise RuntimeError("frozen normalizer shape drift")
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
    if not np.isfinite(scores).all():
        raise RuntimeError("non-finite P2 score")
    return scores


def write_sha256s(out: Path) -> None:
    rows = []
    for path in sorted(out.iterdir(), key=lambda value: value.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append("%s  %s" % (sha256_file(path), path.name))
    atomic_text(out / "SHA256SUMS", "\n".join(rows) + "\n")


def validation_for_state_a(out: Path, graph: Mapping[str, object], role_audit: Mapping[str, object]) -> Dict[str, object]:
    absent = sorted(name for name in EMBEDDING_OUTPUTS if (out / name).exists())
    checks = {
        "audit0_failed": graph["status"] == "FAIL",
        "embedding_arrays_opened_zero": int(role_audit["embedding_arrays_opened"]) == 0,
        "probe_state_arrays_opened_zero": int(role_audit["probe_state_arrays_opened"]) == 0,
        "embedding_outputs_absent": not absent,
        "report_final_pcap_training_zero": all(
            int(role_audit[key]) == 0
            for key in ["support_val_rows_opened", "report_files_opened", "final_files_opened", "pcap_files_opened", "training_runs"]
        ),
    }
    return {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks, "unexpected_embedding_outputs": absent}


def materialize(root: Path, out: Path) -> Dict[str, object]:
    stage = out.with_name(".%s.stage" % out.name)
    control = out.with_name("%s_control" % out.name)
    if out.exists() or stage.exists():
        raise RuntimeError("refusing to overwrite CKDE-R D0 output")
    if control.exists():
        shutil.rmtree(str(control))
    stage.mkdir(parents=True, exist_ok=False)
    role_audit: Dict[str, object] = {
        "status": "PRE_OPEN",
        "plan_metadata_opened": 0,
        "session_metadata_opened": 0,
        "parent_census_opened": 0,
        "embedding_arrays_opened": 0,
        "probe_state_arrays_opened": 0,
        "support_val_rows_opened": 0,
        "report_files_opened": 0,
        "final_files_opened": 0,
        "pcap_files_opened": 0,
        "training_runs": 0,
    }
    try:
        identities = pin_inputs(root)
        atomic_json(stage / "ckde_r_d0_input_identity.json", {"status": "PASS", "identities": identities})
        joined, _, census = load_metadata_only(root)
        role_audit.update({"plan_metadata_opened": 1, "session_metadata_opened": 1, "parent_census_opened": 1})
        incidence, graph, metadata_audit = audit0(joined, census)
        atomic_csv(stage / "ckde_r_d0_pairing_incidence.csv", incidence)
        atomic_json(stage / "ckde_r_d0_pairing_graph_audit.json", graph)

        if graph["status"] != "PASS":
            role_audit["status"] = "AUDIT0_FAIL_CLOSED_BEFORE_EMBEDDINGS"
            atomic_json(stage / "ckde_r_d0_role_open_audit.json", role_audit)
            verdict = {
                "status": "A_NO_IDENTIFIABLE_PAIRED_DEVICE_SUPPORT",
                "scientific_state": "A",
                "reason_codes": graph["reason_codes"],
                "audit0": metadata_audit,
                "embedding_arrays_opened": 0,
                "d1_drafting_authorized": False,
                "claim_ceiling": "NO_REPRESENTATION_COMMISSIONING_EXPERIMENT_JUSTIFIED_FROM_CURRENT_EVIDENCE",
            }
            atomic_json(stage / "ckde_r_d0_verdict.json", verdict)
            validation = validation_for_state_a(stage, graph, role_audit)
            if validation["status"] != "PASS":
                raise RuntimeError("state-A validation failed")
            atomic_json(stage / "ckde_r_d0_validation_report.json", validation)
            write_sha256s(stage)
            os.replace(str(stage), str(out))
            return verdict

        # No current live input reaches this block.  It remains fail-closed so
        # a future graph cannot silently claim an unvalidated implementation.
        raise RuntimeError(
            "Audit-0 passed but post-Audit representation stages require a new implementation review"
        )
    except Exception:
        if stage.exists():
            shutil.rmtree(str(stage))
        control.mkdir(parents=True, exist_ok=True)
        atomic_json(
            control / "engineering_failure.json",
            {
                "status": "CKDE_R_D0_ENGINEERING_FAILURE_NO_VERDICT",
                "traceback": traceback.format_exc(),
            },
        )
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verdict = materialize(args.root.resolve(), args.output.resolve())
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
