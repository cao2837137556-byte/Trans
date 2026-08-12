#!/usr/bin/env python3
"""Build exactly one CKDA D1 role plan per invocation.

Fit/select opens only the CKBY lineage container and never reads its label or
feature arrays.  Report is a separate invocation and remains fail-closed until
the threshold-freeze marker carries the frozen contract and fit/select plan
identities.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Mapping, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core


SNAPSHOT_SHA256 = "b2ef1f7d0244cc7abb8665c25364744f794190f411482e4e202e346cb850279c"
PREDICTIONS_SHA256 = "d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85"
GLOBAL = "GLOBAL_ATTACK_PRESERVATION"
FINAL_MARKERS = ("cooler-motor", "seed37", "seed47", "seed-37", "seed-47")
FIT_ROLE_COUNTS = {
    "aux_fit": 6_600,
    "aux_normal_fit": 4_000,
    "aux_process_fit": 4_000,
    "id_calib": 809,
    "ood_val": 2_604,
    "support_train": 385,
}
SELECT_ROLE_COUNTS = {"support_val": 69, "aux_select": 3_000, "aux_normal_select": 4_000}
REPORT_ROLE_COUNTS = {
    "support_val": 69,
    "same_file_query": 2_486,
    "future_query": 131_391,
    "sealed_final_attack": 110_104,
    "ood_val": 3_000,
    "sealed_final_ood": 3_000,
    "aux_report": 9_000,
    "ood_stress": 3_000,
}


def fail_if_final_text(value: object, context: str) -> None:
    lowered = str(value).lower().replace("_", "-")
    if any(marker in lowered for marker in FINAL_MARKERS):
        raise RuntimeError("FINAL marker in %s: %s" % (context, value))


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    mapped = series.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    if mapped.isna().any():
        raise RuntimeError("invalid boolean column: %s" % series.name)
    return mapped.astype(bool)


def load_snapshot(path: Path, include_labels: bool = False) -> pd.DataFrame:
    path = Path(path)
    if core.sha256_file(path) != SNAPSHOT_SHA256:
        raise RuntimeError("CKBY snapshot SHA drift")
    with np.load(path, allow_pickle=False) as values:
        expected = {
            "uid", "x", "role", "m1_phase", "source", "device_family",
            "attack_family", "label", "recorded_index", "raw51_observable",
            "global_pool", "feature_names",
        }
        if set(values.files) != expected:
            raise RuntimeError("CKBY snapshot schema drift")
        # x and feature_names share the container but are never read here.
        columns = {
                "uid": values["uid"].astype(str),
                "role": values["role"].astype(str),
                "phase": values["m1_phase"].astype(str),
                "source_group": values["source"].astype(str),
                "device_family": values["device_family"].astype(str),
                "attack_family": values["attack_family"].astype(str),
                "recorded_index": np.asarray(values["recorded_index"], dtype=np.int64),
                "global_pool": values["global_pool"].astype(str),
        }
        if include_labels:
            columns["label_metric_only"] = np.asarray(values["label"], dtype=np.int64)
        frame = pd.DataFrame(columns)
    if len(frame) != 287_448 or frame["uid"].duplicated().any():
        raise RuntimeError("CKBY snapshot row/UID drift")
    return frame


def load_predictions(path: Path) -> pd.DataFrame:
    path = Path(path)
    if core.sha256_file(path) != PREDICTIONS_SHA256:
        raise RuntimeError("CKBW predictions SHA drift")
    frame = pd.read_csv(path)
    required = {
        "held_value", "uid", "role", "phase", "source_group", "device_family",
        "attack_family", "label_metric_only", "c1_hard", "frozen_ckbq_hard",
        "hard__M7-TabM-TailMargin-DualControl", "review", "seed",
    }
    if not required.issubset(frame.columns):
        raise RuntimeError("CKBW prediction schema missing: %s" % sorted(required - set(frame.columns)))
    if len(frame) != 297_326 or frame.duplicated(["held_value", "uid"]).any():
        raise RuntimeError("CKBW prediction row/key drift")
    if bool_series(frame["review"]).any() or set(pd.to_numeric(frame["seed"], errors="raise")) != {27}:
        raise RuntimeError("CKBW prediction review/seed drift")
    return frame


def assert_role_counts(frame: pd.DataFrame, expected: Mapping[str, int], context: str) -> None:
    actual = frame.groupby("role", sort=True).size().astype(int).to_dict()
    if actual != dict(expected):
        raise RuntimeError("%s role counts drift: %s/%s" % (context, actual, dict(expected)))


def build_fit_select_plan(snapshot: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    fit = snapshot.loc[snapshot["global_pool"].eq("fit")].copy()
    select = snapshot.loc[snapshot["global_pool"].isin(["select_attack", "select_benign"])].copy()
    assert_role_counts(fit, FIT_ROLE_COUNTS, "fit")
    assert_role_counts(select, SELECT_ROLE_COUNTS, "select")
    fit_select = pd.concat((fit, select), ignore_index=True)
    if len(fit_select) != 25_467 or fit_select["uid"].duplicated().any():
        raise RuntimeError("fit/select frozen denominator drift")
    fit_select["plan_scope"] = np.where(
        fit_select["global_pool"].eq("fit"), "FIT_PROBE_ONLY", "SELECT_THRESHOLD_ONLY"
    )

    # Labels are mechanical from frozen roles in fit/select.  The snapshot
    # label array is intentionally unopened in this phase.
    attack_roles = {"support_train", "support_val", "aux_process_fit"}
    fit_select["label_metric_only"] = fit_select["role"].isin(attack_roles).astype(np.int64)
    for column in ("uid", "role", "source_group", "device_family"):
        for value in fit_select[column].astype(str):
            fail_if_final_text(value, column)
    fit_select.sort_values(["plan_scope", "role", "source_group", "uid"], kind="mergesort", inplace=True)
    fit_select.reset_index(drop=True, inplace=True)
    audit = {
        "status": "CKDA_D1_FIT_SELECT_ROLE_PLAN_PASS",
        "contract_sha256": core.CONTRACT_SHA256,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "fit_select_rows": len(fit_select),
        "fit_rows": len(fit),
        "select_rows": len(select),
        "report_rows_opened": 0,
        "report_labels_opened": 0,
        "final_files_opened": 0,
        "snapshot_arrays_read": [
            "uid", "role", "m1_phase", "source", "device_family", "attack_family",
            "recorded_index", "global_pool",
        ],
        "snapshot_arrays_forbidden_and_unread": ["x", "feature_names", "label", "raw51_observable"],
    }
    return fit_select, audit


def build_report_plan(snapshot: pd.DataFrame, predictions: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, object]]:
    global_attack = predictions.loc[
        predictions["held_value"].eq(GLOBAL)
        & pd.to_numeric(predictions["label_metric_only"], errors="raise").eq(1)
    ].copy()
    if len(global_attack) != core.REPORT_ATTACK_ROWS:
        raise RuntimeError("global report attack denominator drift")
    ood_held_roles = {
        "iotsim-hydraulic-system": "ood_val",
        "iotsim-ip-camera-street": "sealed_final_ood",
        "iotsim-predictive-maintenance": "aux_report",
        "iotsim-stream-consumer": "ood_stress",
    }
    parts = [global_attack]
    for held, role in ood_held_roles.items():
        part = predictions.loc[predictions["held_value"].eq(held) & predictions["role"].eq(role)].copy()
        parts.append(part)
    report = pd.concat(parts, ignore_index=True)
    assert_role_counts(report, REPORT_ROLE_COUNTS, "report")
    if len(report) != 262_050 or report["uid"].duplicated().any():
        raise RuntimeError("one-shot report denominator/UID drift")
    report["plan_scope"] = "REPORT_ONE_SHOT_ONLY"

    snapshot_keys = snapshot[["uid", "recorded_index"]].copy()
    report = report.merge(snapshot_keys, on="uid", how="left", validate="one_to_one")
    if report["recorded_index"].isna().any():
        raise RuntimeError("report UID absent from frozen lineage snapshot")

    for column in ("uid", "role", "source_group", "device_family"):
        for value in report[column].astype(str):
            fail_if_final_text(value, column)
    report.sort_values(["plan_scope", "role", "source_group", "uid"], kind="mergesort", inplace=True)
    report.reset_index(drop=True, inplace=True)

    audit = {
        "status": "CKDA_D1_REPORT_ROLE_PLAN_PASS",
        "contract_sha256": core.CONTRACT_SHA256,
        "snapshot_sha256": SNAPSHOT_SHA256,
        "predictions_sha256": PREDICTIONS_SHA256,
        "report_rows": len(report),
        "report_attack_rows": len(global_attack),
        "future_query_rows": int(report["role"].eq("future_query").sum()),
        "final_files_opened": 0,
        "review_rows": int(bool_series(report["review"]).sum()),
        "snapshot_arrays_read": [
            "uid", "role", "m1_phase", "source", "device_family", "attack_family",
            "recorded_index", "global_pool",
        ],
        "snapshot_arrays_forbidden_and_unread": ["x", "feature_names", "label", "raw51_observable"],
    }
    return report, audit


def write_plan(path: Path, frame: pd.DataFrame) -> None:
    rows = frame.to_dict(orient="records")
    core.atomic_csv(Path(path), rows, list(frame.columns))
    readback = pd.read_csv(Path(path), keep_default_na=False)
    if list(readback.columns) != list(frame.columns) or len(readback) != len(frame):
        raise RuntimeError("role plan atomic readback drift")


def require_threshold_marker(path: Path) -> Dict[str, object]:
    with Path(path).open("r", encoding="utf-8") as handle:
        marker = json.load(handle)
    if marker.get("status") != "CKDA_D1_THRESHOLDS_FROZEN":
        raise RuntimeError("report phase threshold marker status drift")
    if marker.get("contract_sha256") != core.CONTRACT_SHA256:
        raise RuntimeError("report phase threshold marker contract drift")
    plan_sha = str(marker.get("fit_select_plan_sha256", ""))
    if len(plan_sha) != 64 or any(character not in "0123456789abcdef" for character in plan_sha):
        raise RuntimeError("report phase fit/select identity missing")
    thresholds = marker.get("thresholds")
    if not isinstance(thresholds, dict) or set(thresholds) != {"G0", "P1", "P2"}:
        raise RuntimeError("report phase threshold probe set drift")
    for probe, value in thresholds.items():
        if not isinstance(value, dict) or value.get("kind") not in {"FINITE", "NO_HARD", "ALL_HARD"}:
            raise RuntimeError("report phase invalid %s threshold" % probe)
        if int(value.get("support_hard", -1)) != core.SUPPORT_SELECT_ROWS:
            raise RuntimeError("report phase %s support selection drift" % probe)
    return marker


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    snapshot = load_snapshot(args.snapshot, include_labels=False)
    if args.scope == "fit-select":
        if args.predictions is not None or args.threshold_marker is not None:
            raise RuntimeError("fit-select phase forbids predictions and threshold marker")
        fit_select, audit = build_fit_select_plan(snapshot)
        fit_path = out / "ckda_d1_fit_select_plan.csv"
        write_plan(fit_path, fit_select)
        audit["fit_select_plan_sha256"] = core.sha256_file(fit_path)
    else:
        if args.predictions is None or args.threshold_marker is None:
            raise RuntimeError("report phase requires predictions and threshold marker")
        marker = require_threshold_marker(args.threshold_marker)
        predictions = load_predictions(args.predictions)
        report, audit = build_report_plan(snapshot, predictions)
        report_path = out / "ckda_d1_report_plan.csv"
        write_plan(report_path, report)
        audit["report_plan_sha256"] = core.sha256_file(report_path)
        audit["threshold_marker_sha256"] = core.sha256_file(args.threshold_marker)
        audit["fit_select_plan_sha256"] = marker["fit_select_plan_sha256"]
    core.atomic_json(out / "ckda_d1_role_plan_audit.json", audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--scope", choices=("fit-select", "report"), required=True)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--snapshot", type=Path, required=True)
    result.add_argument("--predictions", type=Path)
    result.add_argument("--threshold-marker", type=Path)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
