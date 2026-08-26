#!/usr/bin/env python3
"""CKDE-Q D1 Stage A: benign-prefix threshold materialization only."""

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


CONTRACT_REL = Path(
    "runs/mainline_docs/"
    "ckde_d1_development_commissioning_calibration_preregistered_v1_20260825.md"
)
CONTRACT_SHA256 = "0ec11fdfd794312f2ff592fb0f5f582aa97c1557addcbfbfc2384ec80c488fb4"
D0_REL = Path("runs/issue27ckde_d0_identifiability_audit_v1_2026-08-25_local")
CAP_REL = Path("runs/issue27ckde_d1_cap_materialization_v1_2026-08-25_local_r2")
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINS = {
    "d0_verdict": (D0_REL / "ckde_d0_verdict.json", "c1953c55d999ac151426d5d9f6fa9fdcbaddfd725fe966ebf09def1c62f47033"),
    "d0_census": (D0_REL / "ckde_d0_device_lineage_census.csv", "9ce04164ce6db9917d9fe8d1dedae612ed727f78460e1db0882afe6dc1d69f9b"),
    "cap": (CAP_REL / "ckde_d1_cap.json", "4ff7b3397417b70f12c08ec928f283b14efc915bf597c486b6f4250fa92b99c8"),
    "cap_sha256s": (CAP_REL / "SHA256SUMS", "d22eb39bd24004bd14473a4117ba75c1542bea22ecbafffa047c0c93e4420fe2"),
    "plan": (STAGE_REL / "ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "embeddings": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "session_metadata": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "probe_state": (STAGE_REL / "ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
    "threshold_marker": (STAGE_REL / "ckda_d1_threshold_freeze_marker.json", "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"),
}

EXPECTED_ROWS = 25467
WIDTH = 768
THETA_0 = 0.065159872174263
T_CAP = 0.065159883194168905
CAP = 1.1019905904463556e-08
ALPHA = 0.05
SESSION_BUDGETS = (64, 128, 256)
RECORD_BUDGETS = (100, 500, 1000)
BENIGN_ROLES = {"id_calib", "ood_val", "aux_fit", "aux_select", "aux_normal_fit", "aux_normal_select"}

COMMON_11 = tuple(
    ["iotsim-combined-cycle-%d_0-0_to_OpenvSwitch-13_%d-0" % (index, index) for index in range(2, 10)]
    + ["processed/iotsim-building-monitor-2.csv", "normal_1.pcap", "normal_2.pcap"]
)


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
    if scores.shape != (len(representations),) or not np.isfinite(scores).all():
        raise RuntimeError("non-finite prefix score")
    return scores


def quantile_threshold(scores: Sequence[float]) -> float:
    values = np.sort(np.asarray(scores, dtype=np.float64))
    if not len(values) or not np.isfinite(values).all():
        raise RuntimeError("empty or invalid calibration score set")
    rank = min(len(values), int(math.ceil((len(values) + 1) * (1.0 - ALPHA))))
    return float(np.nextafter(values[rank - 1], np.inf))


def apply_cap(q_raw: float) -> Tuple[float, float, float, str]:
    delta = max(0.0, float(q_raw) - THETA_0)
    if delta <= CAP:
        threshold = float(q_raw) if delta > 0 else THETA_0
        return threshold, delta, delta, "CALIBRATED" if delta > 0 else "NO_UPWARD_MOVEMENT_ZERO_SHOT"
    return THETA_0, delta, 0.0, "CAP_EXCEEDED_ZERO_SHOT"


def whole_session_record_budget(sessions: pd.DataFrame, budget: int) -> pd.DataFrame:
    selected = []
    total = 0
    for row in sessions.itertuples(index=False):
        records = int(row.records)
        if total + records > budget:
            break
        selected.append(row.session_id)
        total += records
    return sessions.loc[sessions["session_id"].isin(selected)].copy()


def load_prefix_sessions(root: Path) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    census = pd.read_csv(root / PINS["d0_census"][0])
    eligible = census.loc[census["causal_prefix_and_suffix_identifiable"].map(bool_value)].copy()
    if len(eligible) != 23:
        raise RuntimeError("eligible-device count drift")
    keys = sorted(eligible["device_key"].astype(str))
    counts = [int((eligible["prefix_independent_sessions"].astype(int) >= budget).sum()) for budget in SESSION_BUDGETS]
    if counts != [23, 20, 11]:
        raise RuntimeError("S64/S128/S256 eligibility drift")
    if sorted(device for device in COMMON_11) != sorted(eligible.loc[eligible["prefix_independent_sessions"].astype(int).ge(256), "device_key"].astype(str)):
        raise RuntimeError("fixed common-11 allowlist drift")

    plan = pd.read_csv(root / PINS["plan"][0])
    metadata = pd.read_csv(root / PINS["session_metadata"][0])
    if len(plan) != EXPECTED_ROWS or len(metadata) != EXPECTED_ROWS or not plan["uid"].is_unique or not metadata["uid"].is_unique:
        raise RuntimeError("plan/session denominator drift")
    joined = plan.merge(metadata, on="uid", how="left", validate="one_to_one")
    if joined["session_id"].isna().any():
        raise RuntimeError("exact session UID join failure")
    cuts = dict(zip(eligible["device_key"].astype(str), eligible["d0_count_only_cut_event_position"].astype(float)))
    benign = joined.loc[joined["source_group"].astype(str).isin(keys) & joined["role"].isin(BENIGN_ROLES)].copy()
    spans = (
        benign.groupby(["source_group", "session_id"], sort=True)
        .agg(first_event=("event_position", "min"), last_event=("event_position", "max"), records=("uid", "size"))
        .reset_index()
    )
    spans["cut"] = spans["source_group"].astype(str).map(cuts)
    prefix_sessions = spans.loc[spans["last_event"].le(spans["cut"])].copy()
    prefix_sessions.sort_values(["source_group", "first_event", "session_id"], kind="mergesort", inplace=True)
    prefix_keys = set(zip(prefix_sessions["source_group"].astype(str), prefix_sessions["session_id"].astype(str)))
    benign["is_prefix"] = [
        (str(device), str(session)) in prefix_keys
        for device, session in zip(benign["source_group"], benign["session_id"])
    ]
    prefix_rows = benign.loc[benign["is_prefix"]].copy()
    observed = prefix_sessions.groupby("source_group")["session_id"].nunique().astype(int).to_dict()
    expected = dict(zip(eligible["device_key"].astype(str), eligible["prefix_independent_sessions"].astype(int)))
    if {str(k): int(v) for k, v in observed.items()} != {str(k): int(v) for k, v in expected.items()}:
        raise RuntimeError("D0 prefix-session lineage drift")
    return prefix_rows, prefix_sessions, keys


def build_thresholds(
    prefix_rows: pd.DataFrame, prefix_sessions: pd.DataFrame, scores_by_uid: Mapping[str, float], devices: Sequence[str]
) -> pd.DataFrame:
    rows = prefix_rows.copy()
    rows["score"] = rows["uid"].astype(str).map(scores_by_uid)
    if rows["score"].isna().any() or not np.isfinite(rows["score"].to_numpy(dtype=float)).all():
        raise RuntimeError("prefix score join failure")
    session_scores = (
        rows.groupby(["source_group", "session_id"], sort=True)
        .agg(session_score=("score", "max"), records=("uid", "size"), first_event=("event_position", "min"))
        .reset_index()
    )
    session_scores.sort_values(["source_group", "first_event", "session_id"], kind="mergesort", inplace=True)
    manifest: List[Dict[str, object]] = []
    for device in devices:
        sessions = session_scores.loc[session_scores["source_group"].astype(str).eq(device)].copy()
        manifest.append({
            "device_key": device, "arm": "Z", "budget_type": "SESSION", "budget": 0,
            "calibration_sessions": 0, "calibration_records": 0, "q_raw": THETA_0,
            "requested_delta": 0.0, "accepted_delta": 0.0, "threshold": THETA_0,
            "status": "ZERO_SHOT_BASELINE",
        })
        for budget in SESSION_BUDGETS:
            if len(sessions) < budget:
                chosen = sessions.iloc[0:0]
                q_raw = THETA_0
                threshold, requested, accepted, status = THETA_0, 0.0, 0.0, "INSUFFICIENT_SESSION_BUDGET_ZERO_SHOT"
            else:
                chosen = sessions.iloc[:budget]
                q_raw = quantile_threshold(chosen["session_score"].to_numpy(dtype=float))
                threshold, requested, accepted, status = apply_cap(q_raw)
            manifest.append({
                "device_key": device, "arm": "Q-S%d" % budget, "budget_type": "SESSION", "budget": budget,
                "calibration_sessions": len(chosen), "calibration_records": int(chosen["records"].sum()) if len(chosen) else 0,
                "q_raw": q_raw, "requested_delta": requested, "accepted_delta": accepted,
                "threshold": threshold, "status": status,
            })
        for budget in RECORD_BUDGETS:
            chosen = whole_session_record_budget(sessions, budget)
            if chosen.empty:
                q_raw = THETA_0
                threshold, requested, accepted, status = THETA_0, 0.0, 0.0, "NO_COMPLETE_SESSION_FITS_ZERO_SHOT"
            else:
                q_raw = quantile_threshold(chosen["session_score"].to_numpy(dtype=float))
                threshold, requested, accepted, status = apply_cap(q_raw)
            manifest.append({
                "device_key": device, "arm": "Q-R%d" % budget, "budget_type": "RECORD", "budget": budget,
                "calibration_sessions": len(chosen), "calibration_records": int(chosen["records"].sum()) if len(chosen) else 0,
                "q_raw": q_raw, "requested_delta": requested, "accepted_delta": accepted,
                "threshold": threshold, "status": status,
            })
    return pd.DataFrame(manifest)


def write_sha256s(out: Path) -> None:
    rows = []
    for path in sorted(out.iterdir(), key=lambda value: value.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append("%s  %s" % (sha256_file(path), path.name))
    atomic_text(out / "SHA256SUMS", "\n".join(rows) + "\n")


def materialize(root: Path, out: Path) -> Dict[str, object]:
    stage = out.with_name(".%s.stage" % out.name)
    control = out.with_name("%s_control" % out.name)
    if out.exists() or stage.exists():
        raise RuntimeError("refusing to overwrite CKDE-Q Stage A output")
    if control.exists():
        shutil.rmtree(str(control))
    stage.mkdir(parents=True, exist_ok=False)
    try:
        identities = pin_inputs(root)
        cap_payload = json.loads((root / PINS["cap"][0]).read_text(encoding="utf-8"))
        if float(cap_payload["theta_0"]) != THETA_0 or float(cap_payload["T_cap"]) != T_CAP or float(cap_payload["cap_fit_attack"]) != CAP:
            raise RuntimeError("literal cap identity drift")
        prefix_rows, prefix_sessions, devices = load_prefix_sessions(root)
        uids = prefix_rows["uid"].astype(str).tolist()
        with np.load(root / PINS["embeddings"][0], allow_pickle=False) as data:
            all_uids = data["uid"].astype(str)
            positions = {uid: index for index, uid in enumerate(all_uids)}
            if len(positions) != EXPECTED_ROWS:
                raise RuntimeError("embedding UID identity drift")
            indices = np.asarray([positions[uid] for uid in uids], dtype=np.int64)
            representations = np.asarray(data["representation"][indices], dtype=np.float32)
            missing = np.asarray(data["missing"][indices], dtype=bool)
        with np.load(root / PINS["probe_state"][0], allow_pickle=False) as data:
            state = {name: np.asarray(data[name]) for name in data.files}
        scores = frozen_p2_scores(representations, missing, state)
        scores_by_uid = dict(zip(uids, [float(value) for value in scores]))
        manifest = build_thresholds(prefix_rows, prefix_sessions, scores_by_uid, devices)
        expected_rows = len(devices) * (1 + len(SESSION_BUDGETS) + len(RECORD_BUDGETS))
        if len(manifest) != expected_rows:
            raise RuntimeError("threshold manifest denominator drift")
        manifest_path = stage / "ckde_d1_stage_a_threshold_manifest.csv"
        atomic_csv(manifest_path, manifest)
        common_path = stage / "ckde_d1_stage_a_common_11_devices.txt"
        atomic_text(common_path, "\n".join(COMMON_11) + "\n")
        identity = {
            "status": "PASS", "identities": identities,
            "eligible_devices": len(devices), "prefix_rows_scored": len(prefix_rows),
            "prefix_sessions_scored": len(prefix_sessions), "embedding_width": WIDTH,
        }
        atomic_json(stage / "ckde_d1_stage_a_input_identity.json", identity)
        audit = {
            "status": "PASS", "benign_prefix_score_rows_opened": len(prefix_rows),
            "benign_suffix_score_rows_opened": 0, "fit_attack_score_rows_opened": 0,
            "support_val_score_rows_opened": 0, "report_score_rows_opened": 0,
            "final_files_opened": 0, "pcap_files_opened": 0, "training_runs": 0,
        }
        atomic_json(stage / "ckde_d1_stage_a_role_open_audit.json", audit)
        status_counts = {str(k): int(v) for k, v in manifest["status"].value_counts().sort_index().items()}
        primary = manifest.loc[manifest["arm"].eq("Q-S64")]
        summary = {
            "status": "CKDE_D1_STAGE_A_CALIBRATION_FROZEN",
            "eligible_devices": len(devices), "manifest_rows": len(manifest),
            "primary_devices": len(primary),
            "primary_cap_exceeded_fallback_devices": int(primary["status"].eq("CAP_EXCEEDED_ZERO_SHOT").sum()),
            "primary_calibrated_devices": int(primary["status"].eq("CALIBRATED").sum()),
            "primary_no_upward_movement_devices": int(primary["status"].eq("NO_UPWARD_MOVEMENT_ZERO_SHOT").sum()),
            "status_counts_all_arms": status_counts,
            "suffix_outcomes_opened": False,
            "stage_b_authorized": False,
        }
        atomic_json(stage / "ckde_d1_stage_a_summary.json", summary)
        marker = {
            "status": "CALIBRATION_FROZEN",
            "threshold_manifest_sha256": sha256_file(manifest_path),
            "common_11_allowlist_sha256": sha256_file(common_path),
            "theta_0": THETA_0, "T_cap": T_CAP, "cap_fit_attack": CAP,
            "stage_b_authorized": False,
        }
        atomic_json(stage / "ckde_d1_stage_a_calibration_frozen_marker.json", marker)
        checks = {
            "eligible_devices_23": len(devices) == 23,
            "manifest_complete": len(manifest) == 161,
            "thresholds_one_sided": bool(manifest["threshold"].ge(THETA_0).all()),
            "thresholds_at_or_below_cap": bool(manifest["threshold"].le(T_CAP).all()),
            "fallback_exact_zero_shot": bool(manifest.loc[manifest["status"].str.contains("ZERO_SHOT"), "threshold"].eq(THETA_0).all()),
            "suffix_support_report_final_zero": all(int(audit[key]) == 0 for key in ["benign_suffix_score_rows_opened", "support_val_score_rows_opened", "report_score_rows_opened", "final_files_opened"]),
        }
        validation = {"status": "PASS" if all(checks.values()) else "FAIL", "checks": checks}
        if validation["status"] != "PASS":
            raise RuntimeError("Stage A validation failed")
        atomic_json(stage / "ckde_d1_stage_a_validation_report.json", validation)
        write_sha256s(stage)
        os.replace(str(stage), str(out))
        return summary
    except Exception:
        if stage.exists():
            shutil.rmtree(str(stage))
        control.mkdir(parents=True, exist_ok=True)
        atomic_json(control / "engineering_failure.json", {"status": "CKDE_D1_ENGINEERING_FAILURE_NO_VERDICT", "traceback": traceback.format_exc()})
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.root.resolve(), args.output.resolve()), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
