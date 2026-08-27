#!/usr/bin/env python3
"""CKDE-S D0 Lane G attack-protected device-subspace audit.

The metadata count gate precedes all NPZ access.  A second deterministic
availability recensus may read only uid/missing before representation or probe
state access.  All numerical and missingness conventions are frozen by the two
Lane G errata.  No model is trained and no threshold/report/FINAL material is
reachable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import traceback
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path("runs/mainline_docs/ckde_s_d0_attack_protected_device_shift_and_paired_corpus_preregistered_20260826.md")
CONTRACT_SHA256 = "e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6"
ERRATUM_REL = Path("runs/mainline_docs/ckde_s_d0_lane_g_preimplementation_erratum_frozen_20260826.md")
ERRATUM_SHA256 = "156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d"
MISSINGNESS_ERRATUM_REL = Path("runs/mainline_docs/ckde_s_d0_lane_g_missingness_erratum_frozen_20260827.md")
MISSINGNESS_ERRATUM_SHA256 = "c7077dbae15b4792e9b66694ebc453f61f1ad990dd7e61afd89b9a576fba0976"
MISSINGNESS_RULE_REL = Path("runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md")
MISSINGNESS_RULE_SHA256 = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
MISSINGNESS_RULE_QUOTE = (
    "For G0, an unencodable target has score `+infinity`. For P1/P2, its finite\n"
    "representation dimensions are zero and `missing_embedding=1`. No target may be\n"
    "dropped. Missing counts and hard decisions remain in every denominator."
)
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINS = {
    "embeddings": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "metadata": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "plan": (STAGE_REL / "ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "probe_state": (STAGE_REL / "ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
}

FIT_BENIGN_ROLES = {"id_calib", "aux_fit", "aux_normal_fit"}
FIT_ATTACK_ROLES = {"support_train", "aux_process_fit"}
FORBIDDEN_ROLES = {"support_val", "report", "final"}
EXPECTED_ROWS = 25_467
WIDTH = 768
EMBEDDING_PARENT_CONTRACT_SHA256 = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
EXPECTED_ROLE_COUNTS = {
    "aux_fit": 6600, "aux_normal_fit": 4000, "aux_normal_select": 4000,
    "aux_process_fit": 4000, "aux_select": 3000, "id_calib": 809,
    "ood_val": 2604, "support_train": 385, "support_val": 69,
}
MIN_DEVICE_SESSIONS = 64
MIN_DEVICE_COUNT = 9
MAX_RANK = 4
MIN_FAMILY_SESSIONS = 15
CLAIM_SCOPE = "geometry of the encodable (`missing=false`) subset of the frozen fit pool"
EXPECTED_ATTACK_FAMILIES = (
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
    "ToN-credential_bruteforce",
    "ToN-reconnaissance_scan",
)

SVD_RELATIVE_TOLERANCE = 1e-10
ORTHOGONALITY_TOLERANCE = 1e-10
GRADIENT_NORM_FLOOR = 1e-12
LODO_MEDIAN_DISTANCE_MAX = 0.20
LODO_WORST_DISTANCE_MAX = 0.35
LODO_MEDIAN_ANGLE_MAX = 20.0
LODO_WORST_ANGLE_MAX = 35.0
BETWEEN_WITHIN_MEDIAN_MIN = 2.0
BETWEEN_WITHIN_SHARE_MIN = 0.80
BETWEEN_WITHIN_DEVICE_MIN = 1.0
MAJOR_RESIDUAL_MIN = 0.50
ALL_RESIDUAL_MIN = 0.65
ALL_RESIDUAL_SHARE_MIN = 0.80
RETAINED_ENERGY_MIN = 0.25

SCIENTIFIC_OUTPUTS = {
    "ckde_s_d0_embedding_availability_recensus.json",
    "ckde_s_d0_embedding_availability_by_device.csv",
    "ckde_s_d0_embedding_availability_by_attack_family.csv",
    "ckde_s_d0_embedding_availability_session_diagnostic.csv",
    "ckde_s_d0_count_rank.json",
    "ckde_s_d0_device_subspace_stability.csv",
    "ckde_s_d0_between_within_by_device.csv",
    "ckde_s_d0_attack_gradient_by_family.csv",
    "ckde_s_d0_attack_contrast_contamination.csv",
    "ckde_s_d0_removable_subspace_audit.json",
    "ckde_s_d0_role_open_audit.json",
    "ckde_s_d0_geometry_verdict.json",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch: %s" % path)
    return {"path": str(path), "bytes": Path(path).stat().st_size, "sha256": actual}


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temporary = path.with_name(".%s.tmp" % path.name)
    frame.to_csv(temporary, index=False, lineterminator="\n")
    os.replace(str(temporary), str(path))


def pin_inputs(root: Path) -> Dict[str, object]:
    identities = {
        "contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256),
        "erratum": require_sha(root / ERRATUM_REL, ERRATUM_SHA256),
        "missingness_erratum": require_sha(
            root / MISSINGNESS_ERRATUM_REL, MISSINGNESS_ERRATUM_SHA256
        ),
        "missingness_rule": require_sha(
            root / MISSINGNESS_RULE_REL, MISSINGNESS_RULE_SHA256
        ),
    }
    source = (root / MISSINGNESS_RULE_REL).read_text(encoding="utf-8")
    if MISSINGNESS_RULE_QUOTE not in source:
        raise RuntimeError("frozen missingness quotation drift")
    for name, (relative, digest) in PINS.items():
        identities[name] = require_sha(root / relative, digest)
    return identities


def load_metadata_only(root: Path) -> pd.DataFrame:
    plan = pd.read_csv(root / PINS["plan"][0], keep_default_na=False)
    metadata = pd.read_csv(root / PINS["metadata"][0], keep_default_na=False)
    required_plan = {"uid", "role", "source_group", "attack_family", "label_metric_only", "recorded_index"}
    required_metadata = {"uid", "session_id", "timestamp_epoch", "event_position"}
    if not required_plan.issubset(plan.columns) or not required_metadata.issubset(metadata.columns):
        raise RuntimeError("metadata schema drift")
    if len(plan) != EXPECTED_ROWS or len(metadata) != EXPECTED_ROWS:
        raise RuntimeError("fit/select denominator drift")
    if not plan["uid"].is_unique or not metadata["uid"].is_unique:
        raise RuntimeError("duplicate UID")
    joined = plan.merge(metadata, on="uid", how="left", validate="one_to_one")
    if len(joined) != EXPECTED_ROWS or joined["session_id"].eq("").any():
        raise RuntimeError("exact metadata UID join failure")
    role_counts = joined.groupby("role").size().astype(int).to_dict()
    if role_counts != EXPECTED_ROLE_COUNTS:
        raise RuntimeError("fit/select role census drift")
    return joined


def terminal_session_rows(rows: pd.DataFrame) -> pd.DataFrame:
    """Choose the final frozen target in each source/session as its complete embedding."""
    if rows.empty:
        return rows.copy()
    ordered = rows.sort_values(["source_group", "session_id", "event_position", "uid"], kind="mergesort")
    return ordered.groupby(["source_group", "session_id"], sort=True, as_index=False).tail(1).reset_index(drop=True)


def count_rank_gate(joined: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    benign = terminal_session_rows(joined.loc[joined["role"].isin(FIT_BENIGN_ROLES)].copy())
    counts = benign.groupby("source_group", sort=True)["session_id"].nunique().astype(int)
    all_devices = sorted(joined.loc[joined["role"].isin(FIT_BENIGN_ROLES), "source_group"].astype(str).unique())
    rows = pd.DataFrame({
        "device_key": all_devices,
        "fit_benign_records": [int((joined["role"].isin(FIT_BENIGN_ROLES) & joined["source_group"].astype(str).eq(device)).sum()) for device in all_devices],
        "complete_fit_benign_sessions": [int(counts.get(device, 0)) for device in all_devices],
    })
    rows["eligible"] = rows["complete_fit_benign_sessions"].ge(MIN_DEVICE_SESSIONS)
    eligible = rows.loc[rows["eligible"], "device_key"].astype(str).tolist()
    rank = min(MAX_RANK, int(math.floor((len(eligible) - 1) / 3))) if eligible else 0
    passed = len(eligible) >= MIN_DEVICE_COUNT and rank >= 2
    payload = {
        "status": "PASS" if passed else "NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT",
        "D_metadata": len(eligible),
        "r_metadata": rank,
        "eligible_devices": len(eligible),
        "eligible_device_keys": eligible,
        "minimum_sessions_per_device": MIN_DEVICE_SESSIONS,
        "minimum_device_count": MIN_DEVICE_COUNT,
        "rank_formula": "min(4,floor((D-1)/3))",
        "rank": rank,
        "rank_retry_permitted": False,
    }
    return rows, payload


def retained_rank(singular_values: Sequence[float]) -> int:
    values = np.asarray(singular_values, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or values[0] <= 0.0:
        raise RuntimeError("invalid singular spectrum")
    return int(np.sum(values > SVD_RELATIVE_TOLERANCE * values[0]))


def basis_from_rows(matrix: np.ndarray, rank: int) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all() or rank < 1:
        raise RuntimeError("invalid SVD input")
    _, singular, vt = np.linalg.svd(values, full_matrices=False)
    available = retained_rank(singular)
    if available < rank:
        raise RuntimeError("SVD rank below frozen rank")
    basis = vt[:rank].T
    if np.linalg.norm(basis.T.dot(basis) - np.eye(rank), ord=2) > ORTHOGONALITY_TOLERANCE:
        raise RuntimeError("SVD basis orthogonality failure")
    return basis, singular


def projection(basis: np.ndarray) -> np.ndarray:
    return np.asarray(basis, dtype=np.float64).dot(np.asarray(basis, dtype=np.float64).T)


def orthogonality_pass(value: float) -> bool:
    return bool(np.isfinite(value) and value <= ORTHOGONALITY_TOLERANCE)


def principal_angle_degrees(left: np.ndarray, right: np.ndarray) -> float:
    singular = np.linalg.svd(np.asarray(left).T.dot(np.asarray(right)), compute_uv=False)
    if not len(singular) or not np.isfinite(singular).all():
        raise RuntimeError("invalid principal-angle spectrum")
    return float(np.degrees(np.arccos(np.clip(float(np.min(singular)), -1.0, 1.0))))


def lodo_stability(centers: Mapping[str, np.ndarray], global_center: np.ndarray, rank: int) -> Tuple[np.ndarray, pd.DataFrame, Dict[str, object]]:
    devices = sorted(centers)
    full_rows = np.stack([centers[d] - global_center for d in devices])
    full_basis, singular = basis_from_rows(full_rows, rank)
    full_projection = projection(full_basis)
    records: List[Dict[str, object]] = []
    for held in devices:
        train_devices = [d for d in devices if d != held]
        local_global = np.median(np.stack([centers[d] for d in train_devices]), axis=0)
        local_rows = np.stack([centers[d] - local_global for d in train_devices])
        local_basis, _ = basis_from_rows(local_rows, rank)
        distance = float(np.linalg.norm(full_projection - projection(local_basis), ord="fro") / math.sqrt(2.0 * rank))
        records.append({"held_out_device": held, "normalized_projection_distance": distance, "largest_principal_angle_degrees": principal_angle_degrees(full_basis, local_basis)})
    frame = pd.DataFrame(records)
    summary = {
        "median_projection_distance": float(frame["normalized_projection_distance"].median()),
        "worst_projection_distance": float(frame["normalized_projection_distance"].max()),
        "median_principal_angle_degrees": float(frame["largest_principal_angle_degrees"].median()),
        "worst_principal_angle_degrees": float(frame["largest_principal_angle_degrees"].max()),
        "svd_singular_values": singular.tolist(),
    }
    summary["pass"] = bool(
        summary["median_projection_distance"] <= LODO_MEDIAN_DISTANCE_MAX
        and summary["worst_projection_distance"] <= LODO_WORST_DISTANCE_MAX
        and summary["median_principal_angle_degrees"] <= LODO_MEDIAN_ANGLE_MAX
        and summary["worst_principal_angle_degrees"] <= LODO_WORST_ANGLE_MAX
    )
    return full_basis, frame, summary


def between_within(session_rows: pd.DataFrame, representations: np.ndarray, basis: np.ndarray, global_center: np.ndarray) -> Tuple[pd.DataFrame, Dict[str, object]]:
    records: List[Dict[str, object]] = []
    projector = projection(basis)
    for device, part in session_rows.groupby("source_group", sort=True):
        part = part.sort_values(["timestamp_epoch", "uid"], kind="mergesort")
        values = representations[part["embedding_index"].to_numpy(dtype=np.int64)]
        cut = len(values) // 2
        if cut < 1 or len(values) - cut < 1:
            raise RuntimeError("empty early/late session half")
        center = np.median(values, axis=0)
        early = np.median(values[:cut], axis=0)
        late = np.median(values[cut:], axis=0)
        between = float(np.linalg.norm(projector.dot(center - global_center)))
        within = float(np.linalg.norm(projector.dot(early - late)))
        ratio = between / max(within, 1e-12)
        records.append({"device_key": str(device), "sessions": len(values), "between_norm": between, "within_early_late_norm": within, "between_within_ratio": ratio})
    frame = pd.DataFrame(records)
    required = int(math.ceil(BETWEEN_WITHIN_SHARE_MIN * len(frame)))
    summary = {
        "median_ratio": float(frame["between_within_ratio"].median()),
        "devices_ratio_at_least_1": int(frame["between_within_ratio"].ge(BETWEEN_WITHIN_DEVICE_MIN).sum()),
        "required_devices_ratio_at_least_1": required,
    }
    summary["pass"] = bool(summary["median_ratio"] >= BETWEEN_WITHIN_MEDIAN_MIN and summary["devices_ratio_at_least_1"] >= required)
    return frame, summary


def _require_embedding_schema(data: Mapping[str, np.ndarray]) -> None:
    required = {"uid", "representation", "missing", "candidate_id", "plan_sha256", "contract_sha256"}
    if set(data.files) != required:
        raise RuntimeError("embedding schema drift")


def load_availability(
    root: Path, joined: pd.DataFrame, role_audit: Dict[str, object]
) -> pd.DataFrame:
    """Read only uid/missing and align deterministic availability to the frozen plan."""
    with np.load(root / PINS["embeddings"][0], allow_pickle=False) as data:
        _require_embedding_schema(data)
        uid_raw = np.asarray(data["uid"])
        missing_raw = np.asarray(data["missing"])
    role_audit["embedding_uid_missing_arrays_opened"] = 1
    if uid_raw.ndim != 1 or missing_raw.ndim != 1:
        raise RuntimeError("availability array rank drift")
    if missing_raw.dtype.kind != "b":
        raise RuntimeError("availability must be boolean")
    uids = uid_raw.astype(str)
    missing = missing_raw.astype(bool, copy=False)
    if len(uids) != EXPECTED_ROWS or missing.shape != (EXPECTED_ROWS,):
        raise RuntimeError("availability shape drift")
    if len(set(uids.tolist())) != EXPECTED_ROWS:
        raise RuntimeError("embedding UID drift")
    positions = pd.Series(np.arange(EXPECTED_ROWS, dtype=np.int64), index=uids)
    take = positions.reindex(joined["uid"].astype(str)).to_numpy()
    if pd.isna(take).any() or len(set(take.astype(int).tolist())) != EXPECTED_ROWS:
        raise RuntimeError("availability exact UID join failure")
    take = take.astype(np.int64)
    result = joined.copy()
    result["embedding_archive_index"] = take
    result["embedding_missing"] = missing[take]
    return result


def availability_gate_status(
    d_finite: int, r_finite: int, r_metadata: int
) -> Dict[str, object]:
    """Apply the three independent, literal recensus stop conditions."""
    stop_d = int(d_finite) < MIN_DEVICE_COUNT
    stop_rank = int(r_finite) < 2
    stop_mismatch = int(r_finite) != int(r_metadata)
    return {
        "status": (
            "NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR"
            if stop_d or stop_rank or stop_mismatch
            else "RECENSUS_PASS"
        ),
        "stop_D_finite_lt_9": stop_d,
        "stop_r_finite_lt_2": stop_rank,
        "stop_r_finite_ne_r_metadata": stop_mismatch,
        "rank_retry_permitted": False,
    }


def availability_recensus(
    joined: pd.DataFrame,
    count_gate: Mapping[str, object],
    identities: Mapping[str, object],
    role_audit: Mapping[str, object],
) -> Tuple[
    pd.DataFrame, pd.DataFrame, pd.DataFrame, Dict[str, object], pd.DataFrame, pd.DataFrame
]:
    """Materialize deterministic terminal availability and claim-bounding diagnostics."""
    benign_all = joined.loc[joined["role"].isin(FIT_BENIGN_ROLES)].copy()
    attack_all = joined.loc[joined["role"].isin(FIT_ATTACK_ROLES)].copy()
    if attack_all.groupby(["source_group", "session_id"])["attack_family"].nunique().gt(1).any():
        raise RuntimeError("attack session crosses exact-family strata")
    observed_families = tuple(sorted(attack_all["attack_family"].astype(str).unique()))
    if observed_families != EXPECTED_ATTACK_FAMILIES:
        raise RuntimeError("exact attack-family universe drift")

    benign_sessions = terminal_session_rows(benign_all)
    attack_sessions = terminal_session_rows(attack_all)
    benign_sessions["finite_terminal_embedding"] = ~benign_sessions["embedding_missing"].astype(bool)
    attack_sessions["finite_terminal_embedding"] = ~attack_sessions["embedding_missing"].astype(bool)

    benign_records = benign_all.groupby(["source_group", "session_id"], sort=True).size()
    attack_records = attack_all.groupby(["source_group", "session_id"], sort=True).size()

    device_rows: List[Dict[str, object]] = []
    for device in sorted(benign_all["source_group"].astype(str).unique()):
        part = benign_sessions.loc[benign_sessions["source_group"].astype(str).eq(device)]
        total = int(len(part))
        finite = int(part["finite_terminal_embedding"].sum())
        device_rows.append({
            "device": device,
            "total_terminal_sessions": total,
            "finite_terminal_sessions": finite,
            "missing_terminal_sessions": total - finite,
            "finite_rate": float(finite / total) if total else 0.0,
            "finite_geometry_eligible": bool(finite >= MIN_DEVICE_SESSIONS),
        })
    device_frame = pd.DataFrame(device_rows).sort_values("device", kind="mergesort").reset_index(drop=True)

    family_rows: List[Dict[str, object]] = []
    for family in EXPECTED_ATTACK_FAMILIES:
        part = attack_sessions.loc[attack_sessions["attack_family"].astype(str).eq(family)]
        total = int(len(part))
        finite = int(part["finite_terminal_embedding"].sum())
        eligible = bool(finite >= MIN_FAMILY_SESSIONS)
        family_rows.append({
            "attack_family": family,
            "total_terminal_sessions": total,
            "finite_terminal_sessions": finite,
            "missing_terminal_sessions": total - finite,
            "finite_rate": float(finite / total) if total else 0.0,
            "finite_gradient_eligible": eligible,
            "protection_status": (
                "PROTECTED_BY_REPRESENTATION_EVIDENCE"
                if eligible else "UNPROTECTED_BY_REPRESENTATION_EVIDENCE"
            ),
        })
    family_frame = pd.DataFrame(family_rows).sort_values("attack_family", kind="mergesort").reset_index(drop=True)

    diagnostic_rows: List[Dict[str, object]] = []
    for stratum, sessions, record_counts in (
        ("fit_benign", benign_sessions, benign_records),
        ("fit_attack", attack_sessions, attack_records),
    ):
        for row in sessions.itertuples(index=False):
            key = (row.source_group, row.session_id)
            diagnostic_rows.append({
                "stratum": stratum,
                "device": str(row.source_group),
                "session_id": str(row.session_id),
                "attack_family": "" if stratum == "fit_benign" else str(row.attack_family),
                "terminal_uid": str(row.uid),
                "terminal_event_position": row.event_position,
                "records_in_frozen_session": int(record_counts.loc[key]),
                "finite_terminal_embedding": bool(row.finite_terminal_embedding),
            })
    diagnostic = pd.DataFrame(diagnostic_rows).sort_values(
        ["stratum", "device", "session_id", "terminal_uid"], kind="mergesort"
    ).reset_index(drop=True)

    finite_devices = device_frame.loc[device_frame["finite_geometry_eligible"], "device"].astype(str).tolist()
    excluded_devices = device_frame.loc[~device_frame["finite_geometry_eligible"], "device"].astype(str).tolist()
    protected = family_frame.loc[family_frame["finite_gradient_eligible"], "attack_family"].astype(str).tolist()
    unprotected = family_frame.loc[~family_frame["finite_gradient_eligible"], "attack_family"].astype(str).tolist()
    d_finite = len(finite_devices)
    r_finite = min(MAX_RANK, int(math.floor((d_finite - 1) / 3))) if d_finite else 0
    r_metadata = int(count_gate["rank"])
    gate = availability_gate_status(d_finite, r_finite, r_metadata)

    missing_with_earlier_finite = 0
    for rows, terminals in ((benign_all, benign_sessions), (attack_all, attack_sessions)):
        missing_keys = set(
            zip(
                terminals.loc[~terminals["finite_terminal_embedding"], "source_group"],
                terminals.loc[~terminals["finite_terminal_embedding"], "session_id"],
            )
        )
        if missing_keys:
            finite_rows = rows.loc[~rows["embedding_missing"].astype(bool)]
            finite_keys = set(zip(finite_rows["source_group"], finite_rows["session_id"]))
            missing_with_earlier_finite += len(missing_keys & finite_keys)

    payload: Dict[str, object] = {
        "status": gate["status"],
        "claim_scope": CLAIM_SCOPE,
        "pinned_hashes": {name: value["sha256"] for name, value in identities.items()},
        "missingness_rule_source": str(MISSINGNESS_RULE_REL),
        "missingness_rule_sha256": MISSINGNESS_RULE_SHA256,
        "missingness_rule_quote": MISSINGNESS_RULE_QUOTE,
        "D_metadata": int(count_gate["eligible_devices"]),
        "r_metadata": r_metadata,
        "D_finite": d_finite,
        "r_finite": r_finite,
        "rank_formula": "min(4,floor((D-1)/3))",
        "fit_benign_terminal_sessions": int(len(benign_sessions)),
        "fit_benign_records": int(len(benign_all)),
        "fit_benign_finite_terminal_sessions": int(benign_sessions["finite_terminal_embedding"].sum()),
        "fit_benign_missing_terminal_sessions": int((~benign_sessions["finite_terminal_embedding"]).sum()),
        "fit_attack_terminal_sessions": int(len(attack_sessions)),
        "fit_attack_records": int(len(attack_all)),
        "fit_attack_finite_terminal_sessions": int(attack_sessions["finite_terminal_embedding"].sum()),
        "fit_attack_missing_terminal_sessions": int((~attack_sessions["finite_terminal_embedding"]).sum()),
        "missing_terminal_sessions_with_earlier_finite_target": int(missing_with_earlier_finite),
        "stop_D_finite_lt_9": gate["stop_D_finite_lt_9"],
        "stop_r_finite_lt_2": gate["stop_r_finite_lt_2"],
        "stop_r_finite_ne_r_metadata": gate["stop_r_finite_ne_r_metadata"],
        "eligible_devices": finite_devices,
        "excluded_devices": excluded_devices,
        "protected_attack_families": protected,
        "unprotected_attack_families": unprotected,
        "role_open_audit": dict(role_audit),
        "rank_retry_permitted": gate["rank_retry_permitted"],
    }
    return benign_sessions, attack_sessions, diagnostic, payload, device_frame, family_frame


def load_representations(
    root: Path, joined: pd.DataFrame, role_audit: Dict[str, object]
) -> Tuple[pd.DataFrame, np.ndarray]:
    with np.load(root / PINS["embeddings"][0], allow_pickle=False) as data:
        _require_embedding_schema(data)
        representations = np.asarray(data["representation"], dtype=np.float64)
        candidate = data["candidate_id"].astype(str).reshape(-1).tolist()
        plan_identity = data["plan_sha256"].astype(str).reshape(-1).tolist()
        contract_identity = data["contract_sha256"].astype(str).reshape(-1).tolist()
    role_audit["representation_arrays_opened"] = 1
    role_audit["embedding_arrays_opened"] = 1
    if representations.shape != (EXPECTED_ROWS, WIDTH):
        raise RuntimeError("embedding shape drift")
    if candidate != ["E3"] or plan_identity != [PINS["plan"][1]] or contract_identity != [EMBEDDING_PARENT_CONTRACT_SHA256]:
        raise RuntimeError("embedding internal identity drift")
    take = joined["embedding_archive_index"].to_numpy(dtype=np.int64)
    reordered = representations[take]
    finite = ~joined["embedding_missing"].to_numpy(dtype=bool)
    if not np.isfinite(reordered[finite]).all():
        raise RuntimeError("non-finite nonmissing embedding")
    result = joined.copy()
    result["embedding_index"] = np.arange(EXPECTED_ROWS, dtype=np.int64)
    return result, reordered


def load_probe_state(root: Path, role_audit: Dict[str, object]) -> Dict[str, np.ndarray]:
    with np.load(root / PINS["probe_state"][0], allow_pickle=False) as data:
        required_state = {
            "normalizer_mean", "normalizer_scale", "g0_reference", "g0_reference_uids",
            "p1_coef", "p1_intercept", "p1_classes", "p2__0.weight", "p2__0.bias",
            "p2__3.weight", "p2__3.bias",
        }
        if set(data.files) != required_state:
            raise RuntimeError("probe state schema drift")
        state = {name: np.asarray(data[name]) for name in data.files}
    role_audit["probe_state_arrays_opened"] = 1
    return state


def p2_gradients(representations: np.ndarray, missing: np.ndarray, state: Mapping[str, np.ndarray]) -> np.ndarray:
    values = np.asarray(representations, dtype=np.float64)
    missing_bool = np.asarray(missing, dtype=bool)
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float64)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float64)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float64).reshape(-1)
    if mean.shape != (WIDTH,) or scale.shape != (WIDTH,) or np.any(scale <= 0.0) or w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (128,):
        raise RuntimeError("P2 state shape drift")
    normalized = (values - mean) / scale
    normalized[missing_bool] = 0.0
    x = np.concatenate((normalized, missing_bool.astype(np.float64)[:, None]), axis=1)
    active = (x.dot(w1.T) + b1) > 0.0
    gradients = (active.astype(np.float64) * w2[None, :]).dot(w1[:, :WIDTH]) / scale[None, :]
    gradients[missing_bool] = 0.0
    norms = np.linalg.norm(gradients, axis=1)
    if not np.isfinite(gradients).all() or not np.isfinite(norms).all() or np.any(norms <= GRADIENT_NORM_FLOOR):
        raise RuntimeError("invalid P2 gradient norm")
    return gradients / norms[:, None]


def robust_direction(vectors: np.ndarray) -> np.ndarray:
    direction = np.median(np.asarray(vectors, dtype=np.float64), axis=0)
    norm = float(np.linalg.norm(direction))
    if not np.isfinite(norm) or norm <= GRADIENT_NORM_FLOOR:
        raise RuntimeError("invalid robust direction")
    return direction / norm


def orthonormal_span(rows: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    values = np.asarray(rows, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise RuntimeError("invalid span input")
    _, singular, vt = np.linalg.svd(values, full_matrices=False)
    rank = retained_rank(singular)
    basis = vt[:rank].T
    if np.linalg.norm(basis.T.dot(basis) - np.eye(rank), ord=2) > ORTHOGONALITY_TOLERANCE:
        raise RuntimeError("span orthogonality failure")
    return basis, singular


def attack_protection(
    attack_sessions: pd.DataFrame,
    representations: np.ndarray,
    missing: np.ndarray,
    state: Mapping[str, np.ndarray],
    global_center: np.ndarray,
    device_basis: np.ndarray,
    device_shifts: np.ndarray,
    all_families: Sequence[str] = EXPECTED_ATTACK_FAMILIES,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    indices = attack_sessions["embedding_index"].to_numpy(dtype=np.int64)
    values = representations[indices]
    gradients = p2_gradients(values, missing[indices], state)
    attack_sessions = attack_sessions.reset_index(drop=True).copy()
    gradient_rows: List[Dict[str, object]] = []
    contrast_rows: List[Dict[str, object]] = []
    directions: List[np.ndarray] = []
    eligible_families: List[str] = []
    for family in all_families:
        part = attack_sessions.loc[attack_sessions["attack_family"].astype(str).eq(str(family))]
        local = part.index.to_numpy(dtype=np.int64)
        count = len(local)
        if count < MIN_FAMILY_SESSIONS:
            gradient_rows.append({"attack_family": str(family), "independent_sessions": count, "gradient_norm": "", "eligible": False})
            continue
        direction = robust_direction(gradients[local])
        directions.append(direction)
        eligible_families.append(str(family))
        gradient_rows.append({"attack_family": str(family), "independent_sessions": count, "gradient_norm": float(np.linalg.norm(direction)), "eligible": True})
        contrast = np.median(values[local], axis=0) - global_center
        norm = float(np.linalg.norm(contrast))
        if not np.isfinite(norm) or norm <= GRADIENT_NORM_FLOOR:
            raise RuntimeError("invalid attack contrast")
        rho = float(np.linalg.norm(device_basis.T.dot(contrast)) / norm)
        residual = float(np.linalg.norm(contrast - device_basis.dot(device_basis.T.dot(contrast))) / norm)
        contrast_rows.append({"attack_family": str(family), "independent_sessions": count, "projection_fraction": rho, "residual_fraction": residual, "major_family": True})
    if not directions:
        raise RuntimeError("no eligible attack family direction")
    raw = np.stack(directions)
    attack_basis, _ = orthonormal_span(raw)
    contrasts = pd.DataFrame(contrast_rows)
    required = int(math.ceil(ALL_RESIDUAL_SHARE_MIN * len(contrasts)))
    residual_pass = bool(contrasts["residual_fraction"].ge(MAJOR_RESIDUAL_MIN).all() and int(contrasts["residual_fraction"].ge(ALL_RESIDUAL_MIN).sum()) >= required)
    device_projector = projection(device_basis)
    attack_projector = projection(attack_basis)
    removable_seed = (np.eye(WIDTH) - attack_projector).dot(device_basis)
    u, singular, _ = np.linalg.svd(removable_seed, full_matrices=False)
    removable_rank = retained_rank(singular)
    removable_basis = u[:, :removable_rank]
    overlap = float(np.linalg.norm(projection(removable_basis).dot(attack_projector), ord=2)) if removable_rank else math.inf
    retained = []
    # Equal-device energy retained from the original modeled device subspace.
    for shift in np.asarray(device_shifts, dtype=np.float64):
        denominator = float(np.linalg.norm(device_basis.T.dot(shift)) ** 2)
        retained.append(float(np.linalg.norm(removable_basis.T.dot(shift)) ** 2 / denominator) if denominator > 0 else 0.0)
    retained_median = float(np.median(retained))
    summary = {
        "eligible_attack_families": eligible_families,
        "residual_pass": residual_pass,
        "attack_basis_rank": int(attack_basis.shape[1]),
        "removable_rank": int(removable_rank),
        "orthogonality_spectral_norm": overlap,
        "orthogonality_pass": orthogonality_pass(overlap),
        "median_retained_between_device_energy": retained_median,
        "retained_energy_pass": bool(retained_median >= RETAINED_ENERGY_MIN),
    }
    summary["pass"] = bool(residual_pass and removable_rank >= 1 and summary["orthogonality_pass"] and summary["retained_energy_pass"])
    return pd.DataFrame(gradient_rows), contrasts, summary


def write_sha256s(out: Path) -> None:
    rows = []
    for path in sorted(out.iterdir(), key=lambda value: value.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append("%s  %s" % (sha256_file(path), path.name))
    atomic_text(out / "SHA256SUMS", "\n".join(rows) + "\n")


def validate_role_open_audit(role_audit: Mapping[str, object]) -> None:
    required = (
        "embedding_uid_missing_arrays_opened",
        "representation_arrays_opened",
        "probe_state_arrays_opened",
        "report_files_opened",
        "final_files_opened",
        "network_requests_made",
        "training_steps_run",
    )
    if any(type(role_audit.get(name)) is not int for name in required):
        raise RuntimeError("role-open audit counter type drift")
    if role_audit.get("embedding_arrays_opened") != role_audit.get("representation_arrays_opened"):
        raise RuntimeError("legacy embedding counter alias drift")
    for name in ("report_files_opened", "final_files_opened", "network_requests_made", "training_steps_run"):
        if role_audit[name] != 0:
            raise RuntimeError("sealed boundary counter is nonzero: %s" % name)


def verdict_family_claims(unprotected: Sequence[str]) -> Dict[str, object]:
    names = [str(value) for value in unprotected]
    return {
        "unprotected_attack_family_names": names,
        "unprotected_attack_families": [
            {
                "attack_family": name,
                "protection_status": "UNPROTECTED_BY_REPRESENTATION_EVIDENCE",
            }
            for name in names
        ],
    }


def verdict_counter_fields(role_audit: Mapping[str, object]) -> Dict[str, int]:
    names = (
        "embedding_uid_missing_arrays_opened",
        "representation_arrays_opened",
        "embedding_arrays_opened",
        "probe_state_arrays_opened",
        "report_files_opened",
        "final_files_opened",
        "network_requests_made",
        "training_steps_run",
    )
    return {name: int(role_audit[name]) for name in names}


def recensus_verdict_denominators(recensus: Mapping[str, object]) -> Dict[str, object]:
    return {
        "devices": {
            "metadata_eligible": int(recensus["D_metadata"]),
            "finite_eligible": int(recensus["D_finite"]),
            "metadata_rank": int(recensus["r_metadata"]),
            "finite_rank": int(recensus["r_finite"]),
        },
        "sessions": {
            "fit_benign_terminal": int(recensus["fit_benign_terminal_sessions"]),
            "fit_benign_finite_terminal": int(recensus["fit_benign_finite_terminal_sessions"]),
            "fit_benign_missing_terminal": int(recensus["fit_benign_missing_terminal_sessions"]),
            "fit_attack_terminal": int(recensus["fit_attack_terminal_sessions"]),
            "fit_attack_finite_terminal": int(recensus["fit_attack_finite_terminal_sessions"]),
            "fit_attack_missing_terminal": int(recensus["fit_attack_missing_terminal_sessions"]),
        },
        "records": {
            "fit_benign": int(recensus["fit_benign_records"]),
            "fit_attack": int(recensus["fit_attack_records"]),
        },
    }


def materialize(root: Path, out: Path) -> Dict[str, object]:
    stage = out.with_name(".%s.stage" % out.name)
    control = out.with_name("%s_control" % out.name)
    if out.exists() or stage.exists():
        raise RuntimeError("refusing to overwrite Lane G output")
    if control.exists():
        shutil.rmtree(str(control))
    stage.mkdir(parents=True, exist_ok=False)
    role_audit: Dict[str, object] = {
        "status": "PRE_OPEN", "plan_metadata_opened": 0, "session_metadata_opened": 0,
        "embedding_uid_missing_arrays_opened": 0,
        "representation_arrays_opened": 0, "embedding_arrays_opened": 0,
        "probe_state_arrays_opened": 0,
        "support_val_rows_opened": 0, "report_files_opened": 0, "final_files_opened": 0,
        "pcap_files_opened": 0, "network_requests_made": 0,
        "training_steps_run": 0, "training_runs": 0,
    }
    try:
        identities = pin_inputs(root)
        atomic_json(stage / "ckde_s_d0_input_identity.json", {"status": "PASS", "identities": identities})
        joined = load_metadata_only(root)
        role_audit["plan_metadata_opened"] = 1
        role_audit["session_metadata_opened"] = 1
        device_counts, count_gate = count_rank_gate(joined)
        atomic_json(stage / "ckde_s_d0_count_rank.json", {**count_gate, "device_counts": device_counts.to_dict(orient="records")})
        if count_gate["status"] != "PASS":
            role_audit["status"] = "COUNT_GATE_FAIL_CLOSED_BEFORE_NPZ_OPEN"
            validate_role_open_audit(role_audit)
            atomic_json(stage / "ckde_s_d0_role_open_audit.json", role_audit)
            benign_meta = joined.loc[joined["role"].isin(FIT_BENIGN_ROLES)]
            attack_meta = joined.loc[joined["role"].isin(FIT_ATTACK_ROLES)]
            verdict = {
                "status": "NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT",
                "scientific_state": "G0",
                "rank_retry_permitted": False,
                "availability_recensus_status": "NOT_OPENED_G0M",
                **verdict_counter_fields(role_audit),
                "claim_scope": "NO_GEOMETRY_CLAIM",
                "excluded_devices": [],
                "protected_attack_families": [],
                **verdict_family_claims([]),
                "denominators": {
                    "devices": {
                        "metadata_eligible": int(count_gate["eligible_devices"]),
                        "finite_eligible": "NOT_OPENED_G0M",
                        "metadata_rank": int(count_gate["rank"]),
                        "finite_rank": "NOT_OPENED_G0M",
                    },
                    "sessions": {
                        "fit_benign_terminal": int(len(terminal_session_rows(benign_meta))),
                        "fit_attack_terminal": int(len(terminal_session_rows(attack_meta))),
                    },
                    "records": {
                        "fit_benign": int(len(benign_meta)),
                        "fit_attack": int(len(attack_meta)),
                    },
                },
                "lane_m_authorized": False,
            }
            atomic_json(stage / "ckde_s_d0_geometry_verdict.json", verdict)
            write_sha256s(stage)
            os.replace(str(stage), str(out))
            return verdict

        joined = load_availability(root, joined, role_audit)
        role_audit["status"] = "AVAILABILITY_RECENSUS"
        (
            benign_terminal_all,
            attack_terminal_all,
            session_diagnostic,
            recensus,
            availability_by_device,
            availability_by_family,
        ) = availability_recensus(joined, count_gate, identities, role_audit)
        atomic_csv(stage / "ckde_s_d0_embedding_availability_by_device.csv", availability_by_device)
        atomic_csv(stage / "ckde_s_d0_embedding_availability_by_attack_family.csv", availability_by_family)
        atomic_csv(stage / "ckde_s_d0_embedding_availability_session_diagnostic.csv", session_diagnostic)
        if recensus["status"] != "RECENSUS_PASS":
            role_audit["status"] = "AVAILABILITY_RECENSUS_FAIL_CLOSED"
            validate_role_open_audit(role_audit)
            recensus["role_open_audit"] = dict(role_audit)
            atomic_json(stage / "ckde_s_d0_embedding_availability_recensus.json", recensus)
            atomic_json(stage / "ckde_s_d0_role_open_audit.json", role_audit)
            verdict = {
                "status": "NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR",
                "scientific_state": "G0",
                "rank_retry_permitted": False,
                "claim_scope": CLAIM_SCOPE,
                "excluded_devices": recensus["excluded_devices"],
                "protected_attack_families": recensus["protected_attack_families"],
                **verdict_family_claims(recensus["unprotected_attack_families"]),
                "denominators": recensus_verdict_denominators(recensus),
                **verdict_counter_fields(role_audit),
                "lane_m_authorized": False,
            }
            atomic_json(stage / "ckde_s_d0_geometry_verdict.json", verdict)
            for pre_recensus in (
                stage / "ckde_s_d0_input_identity.json",
                stage / "ckde_s_d0_count_rank.json",
            ):
                pre_recensus.unlink()
            write_sha256s(stage)
            os.replace(str(stage), str(out))
            return verdict

        role_audit["status"] = "AVAILABILITY_RECENSUS_PASS"
        recensus["role_open_audit"] = dict(role_audit)
        atomic_json(stage / "ckde_s_d0_embedding_availability_recensus.json", recensus)

        joined, reps = load_representations(root, joined, role_audit)
        state = load_probe_state(root, role_audit)
        missing = joined["embedding_missing"].to_numpy(dtype=bool)
        eligible = set(str(value) for value in recensus["eligible_devices"])
        benign_all = joined.loc[
            joined["role"].isin(FIT_BENIGN_ROLES)
            & joined["source_group"].astype(str).isin(eligible)
        ].copy()
        attack_all = joined.loc[joined["role"].isin(FIT_ATTACK_ROLES)].copy()
        benign_sessions = terminal_session_rows(benign_all)
        attack_sessions = terminal_session_rows(attack_all)
        benign_sessions = benign_sessions.loc[~benign_sessions["embedding_missing"].astype(bool)].reset_index(drop=True)
        attack_sessions = attack_sessions.loc[~attack_sessions["embedding_missing"].astype(bool)].reset_index(drop=True)
        centers = {str(device): np.median(reps[part["embedding_index"].to_numpy(dtype=np.int64)], axis=0) for device, part in benign_sessions.groupby("source_group", sort=True)}
        global_center = np.median(np.stack([centers[d] for d in sorted(centers)]), axis=0)
        basis, stability, stability_summary = lodo_stability(centers, global_center, int(recensus["r_finite"]))
        benign_denominators = benign_all.groupby("source_group", sort=True).agg(
            independent_sessions=("session_id", "nunique"), records=("uid", "size")
        ).reset_index().rename(columns={"source_group": "device_key"})
        stability = stability.merge(
            benign_denominators.rename(columns={"device_key": "held_out_device"}),
            on="held_out_device", how="left", validate="one_to_one",
        )
        atomic_csv(stage / "ckde_s_d0_device_subspace_stability.csv", stability)
        ratios, ratio_summary = between_within(benign_sessions, reps, basis, global_center)
        ratios = ratios.drop(columns=["sessions"]).merge(
            benign_denominators, on="device_key", how="left", validate="one_to_one"
        )
        atomic_csv(stage / "ckde_s_d0_between_within_by_device.csv", ratios)
        attack_denominators = attack_all.groupby("attack_family", sort=True).agg(
            records=("uid", "size"), independent_sessions_all=("session_id", "nunique")
        ).reset_index()
        if not stability_summary["pass"] or not ratio_summary["pass"]:
            status, state_name = "UNSTABLE_OR_TEMPORAL_DEVICE_SUBSPACE", "G1"
            gradient_frame = availability_by_family.rename(columns={
                "finite_terminal_sessions": "independent_sessions",
                "finite_gradient_eligible": "eligible",
            }).copy()
            gradient_frame["gradient_norm"] = ""
            gradient_frame = gradient_frame.merge(
                attack_denominators, on="attack_family", how="left", validate="one_to_one"
            )
            contrast_frame = pd.DataFrame(columns=["attack_family", "independent_sessions", "projection_fraction", "residual_fraction", "major_family", "records", "independent_sessions_all"])
            removable = {"status": "NOT_REACHED", "stability": stability_summary, "between_within": ratio_summary}
        else:
            device_shifts = np.stack([centers[device] - global_center for device in sorted(centers)])
            gradient_frame, contrast_frame, removable = attack_protection(
                attack_sessions, reps, missing, state, global_center, basis, device_shifts,
                all_families=EXPECTED_ATTACK_FAMILIES,
            )
            gradient_frame = gradient_frame.merge(
                attack_denominators, on="attack_family", how="left", validate="one_to_one"
            )
            gradient_frame = gradient_frame.merge(
                availability_by_family[[
                    "attack_family", "total_terminal_sessions", "finite_terminal_sessions",
                    "missing_terminal_sessions", "finite_rate", "protection_status",
                ]],
                on="attack_family", how="left", validate="one_to_one",
            )
            contrast_frame = contrast_frame.merge(
                attack_denominators, on="attack_family", how="left", validate="one_to_one"
            )
            if not removable["residual_pass"]:
                status, state_name = "ATTACK_DIRECTION_NOT_IDENTIFIABLE", "G2"
            elif not removable["pass"]:
                status, state_name = "NO_ATTACK_ORTHOGONAL_DEVICE_NUISANCE", "G3"
            else:
                status, state_name = "ATTACK_PROTECTED_DEVICE_SUBSPACE_FEASIBLE", "G4"
            removable["stability"] = stability_summary
            removable["between_within"] = ratio_summary
        removable["denominators"] = {
            "eligible_devices": len(eligible),
            "fit_benign_independent_sessions": int(len(benign_sessions)),
            "fit_benign_records": int(len(benign_all)),
            "fit_attack_independent_sessions": int(len(attack_sessions)),
            "fit_attack_records": int(len(attack_all)),
            "fit_benign_terminal_sessions_all": int(len(benign_terminal_all)),
            "fit_attack_terminal_sessions_all": int(len(attack_terminal_all)),
        }
        atomic_csv(stage / "ckde_s_d0_attack_gradient_by_family.csv", gradient_frame)
        atomic_csv(stage / "ckde_s_d0_attack_contrast_contamination.csv", contrast_frame)
        atomic_json(stage / "ckde_s_d0_removable_subspace_audit.json", removable)
        role_audit["status"] = "LANE_G_COMPLETE"
        validate_role_open_audit(role_audit)
        atomic_json(stage / "ckde_s_d0_role_open_audit.json", role_audit)
        verdict = {
            "status": status,
            "scientific_state": state_name,
            "rank": int(recensus["r_finite"]),
            "rank_retry_permitted": False,
            "lane_m_authorized": False,
            "claim_scope": CLAIM_SCOPE,
            "excluded_devices": recensus["excluded_devices"],
            "protected_attack_families": recensus["protected_attack_families"],
            **verdict_family_claims(recensus["unprotected_attack_families"]),
            "denominators": recensus_verdict_denominators(recensus),
            **verdict_counter_fields(role_audit),
        }
        atomic_json(stage / "ckde_s_d0_geometry_verdict.json", verdict)
        write_sha256s(stage)
        os.replace(str(stage), str(out))
        return verdict
    except Exception as exc:
        if stage.exists():
            shutil.rmtree(str(stage))
        control.mkdir(parents=True, exist_ok=True)
        failure = {"status": "ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT", "error_type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(), "scientific_outputs_removed": True}
        atomic_json(control / "engineering_failure.json", failure)
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    verdict = materialize(args.root.resolve(), args.output.resolve())
    print(json.dumps(verdict, sort_keys=True))


if __name__ == "__main__":
    main()
