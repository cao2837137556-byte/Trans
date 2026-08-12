#!/usr/bin/env python3
"""Fit/freeze or apply the CKDA D1 three-probe canary.

The two scopes are intentionally disjoint. ``fit-select`` never accepts a
report plan. ``report`` requires the immutable threshold marker and only
reconstructs frozen numerical state; no fitting or threshold selection code is
reachable in that scope.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core


EMBEDDING_FIELDS = {
    "uid", "representation", "missing", "candidate_id", "plan_sha256", "contract_sha256"
}
PROBES = ("G0", "P1", "P2")


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp.npz")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
        handle.flush()
    temporary.replace(path)
    with np.load(path, allow_pickle=False) as values:
        if set(values.files) != set(arrays):
            raise RuntimeError("NPZ atomic readback schema drift")


def load_embeddings(path: Path, plan_sha256: str) -> Tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    with np.load(Path(path), allow_pickle=False) as values:
        if set(values.files) != EMBEDDING_FIELDS:
            raise RuntimeError("embedding artifact schema drift")
        uids = values["uid"].astype(str)
        representation = np.asarray(values["representation"], dtype=np.float64)
        missing = np.asarray(values["missing"], dtype=np.bool_)
        candidate_values = values["candidate_id"].astype(str).reshape(-1)
        plan_values = values["plan_sha256"].astype(str).reshape(-1)
        contract_values = values["contract_sha256"].astype(str).reshape(-1)
    if representation.ndim != 2 or len(uids) != len(representation) or len(missing) != len(uids):
        raise RuntimeError("embedding artifact shape drift")
    if len(set(uids.tolist())) != len(uids):
        raise RuntimeError("embedding artifact duplicate UID")
    if len(candidate_values) != 1 or candidate_values[0] not in {"I1", "E3"}:
        raise RuntimeError("embedding candidate identity drift")
    if plan_values.tolist() != [str(plan_sha256)]:
        raise RuntimeError("embedding plan identity drift")
    if contract_values.tolist() != [core.CONTRACT_SHA256]:
        raise RuntimeError("embedding contract identity drift")
    if bool(np.any(np.isnan(representation[~missing]))):
        raise RuntimeError("embedded target contains NaN")
    return uids, representation, missing, candidate_values[0]


def exact_join(plan: pd.DataFrame, uids: np.ndarray, values: np.ndarray, missing: np.ndarray) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    if plan["uid"].duplicated().any() or len(plan) != len(uids):
        raise RuntimeError("plan/embedding cardinality drift")
    positions = pd.Series(np.arange(len(uids), dtype=np.int64), index=uids)
    if positions.index.has_duplicates:
        raise RuntimeError("embedding duplicate UID")
    take = positions.reindex(plan["uid"].astype(str)).to_numpy()
    if pd.isna(take).any():
        raise RuntimeError("plan UID missing from embeddings")
    take = take.astype(np.int64)
    if len(set(take.tolist())) != len(take):
        raise RuntimeError("embedding UID reused")
    return plan.reset_index(drop=True), values[take], missing[take]


def sigmoid(value: np.ndarray) -> np.ndarray:
    value = np.asarray(value, dtype=np.float64)
    positive = value >= 0.0
    result = np.empty_like(value)
    result[positive] = 1.0 / (1.0 + np.exp(-value[positive]))
    exponential = np.exp(value[~positive])
    result[~positive] = exponential / (1.0 + exponential)
    return result


def serialize_state(
    path: Path,
    normalizer: core.SharedNormalizer,
    geometry: core.GeometryProbe,
    linear: core.LinearProbe,
    mlp: core.MLPProbe,
) -> None:
    torch = core._torch()
    arrays: Dict[str, np.ndarray] = {
        "normalizer_mean": np.asarray(normalizer.mean, dtype=np.float64),
        "normalizer_scale": np.asarray(normalizer.scale, dtype=np.float64),
        "g0_reference": np.asarray(geometry.reference, dtype=np.float64),
        "g0_reference_uids": np.asarray(geometry.reference_uids, dtype=np.str_),
        "p1_coef": np.asarray(linear.model.coef_, dtype=np.float64),
        "p1_intercept": np.asarray(linear.model.intercept_, dtype=np.float64),
        "p1_classes": np.asarray(linear.model.classes_, dtype=np.int64),
    }
    for name, tensor in mlp.model.state_dict().items():
        arrays["p2__" + name] = tensor.detach().cpu().numpy()
    atomic_npz(path, **arrays)
    # Exercise a real reconstruct-and-forward path before accepting the file.
    loaded = load_state(path)
    if loaded[0].mean.shape != normalizer.mean.shape:
        raise RuntimeError("probe state readback shape drift")
    del torch


def load_state(path: Path):
    with np.load(Path(path), allow_pickle=False) as values:
        required = {
            "normalizer_mean", "normalizer_scale", "g0_reference", "g0_reference_uids",
            "p1_coef", "p1_intercept", "p1_classes",
            "p2__0.weight", "p2__0.bias", "p2__3.weight", "p2__3.bias",
        }
        if set(values.files) != required:
            raise RuntimeError("probe state schema drift")
        normalizer = core.SharedNormalizer(values["normalizer_mean"], values["normalizer_scale"])
        geometry = core.GeometryProbe()
        geometry.reference = np.asarray(values["g0_reference"], dtype=np.float64)
        geometry.reference_uids = values["g0_reference_uids"].astype(str).tolist()
        p1_coef = np.asarray(values["p1_coef"], dtype=np.float64)
        p1_intercept = np.asarray(values["p1_intercept"], dtype=np.float64)
        p1_classes = np.asarray(values["p1_classes"], dtype=np.int64)
        if p1_classes.tolist() != [0, 1] or p1_coef.shape[0] != 1 or p1_intercept.shape != (1,):
            raise RuntimeError("P1 state identity drift")
        mlp = core.MLPProbe(int(p1_coef.shape[1]))
        torch = core._torch()
        state = {
            name[len("p2__"):]: torch.as_tensor(np.asarray(values[name])).clone()
            for name in values.files if name.startswith("p2__")
        }
        mlp.model.load_state_dict(state, strict=True)
    return normalizer, geometry, (p1_coef, p1_intercept), mlp


def score_frozen(state, representations: np.ndarray, missing: np.ndarray, uids: Sequence[str]) -> Dict[str, np.ndarray]:
    normalizer, geometry, p1_state, mlp = state
    normalized = normalizer.transform(representations, missing)
    features = core.append_missing(normalized, missing)
    p1_coef, p1_intercept = p1_state
    scores = {
        "G0": geometry.score(normalized, missing, uids),
        "P1": sigmoid(features @ p1_coef.reshape(-1) + float(p1_intercept[0])),
        "P2": mlp.score(features),
    }
    for probe, values in scores.items():
        if len(values) != len(uids) or bool(np.any(np.isnan(values))):
            raise RuntimeError("%s frozen score drift" % probe)
    return scores


def threshold_dict(value: core.ThresholdSpec) -> Dict[str, object]:
    return {
        "kind": value.kind,
        "value": value.value,
        "canonical": value.canonical,
        "support_hard": value.support_hard,
        "auxiliary_hard": value.auxiliary_hard,
        "ton_hard": value.ton_hard,
    }


def run_fit_select(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    plan_sha = core.sha256_file(plan_path)
    plan = pd.read_csv(plan_path, keep_default_na=False)
    if set(plan["plan_scope"]) != {"FIT_PROBE_ONLY", "SELECT_THRESHOLD_ONLY"} or len(plan) != 25_467:
        raise RuntimeError("fit/select plan identity drift")
    uids, representations, missing, candidate = load_embeddings(args.embeddings, plan_sha)
    plan, representations, missing = exact_join(plan, uids, representations, missing)
    if candidate != args.candidate:
        raise RuntimeError("requested candidate identity drift")
    fit_mask = plan["plan_scope"].eq("FIT_PROBE_ONLY").to_numpy()
    select_mask = ~fit_mask
    if (int(fit_mask.sum()), int(select_mask.sum())) != (18_398, 7_069):
        raise RuntimeError("fit/select denominator drift")
    labels = pd.to_numeric(plan["label_metric_only"], errors="raise").to_numpy(dtype=np.int64)
    normalizer = core.SharedNormalizer.fit(representations[fit_mask], missing[fit_mask])
    normalized_fit = normalizer.transform(representations[fit_mask], missing[fit_mask])
    fit_uids = plan.loc[fit_mask, "uid"].astype(str).tolist()
    geometry = core.GeometryProbe().fit(normalized_fit, missing[fit_mask], labels[fit_mask], fit_uids)
    fit_features = core.append_missing(normalized_fit, missing[fit_mask])
    linear = core.LinearProbe().fit(fit_features, labels[fit_mask])
    mlp = core.MLPProbe(fit_features.shape[1]).fit(fit_features, labels[fit_mask])

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "ckda_d1_probe_state.npz"
    serialize_state(state_path, normalizer, geometry, linear, mlp)
    state = load_state(state_path)
    select_plan = plan.loc[select_mask].reset_index(drop=True)
    select_scores = score_frozen(
        state, representations[select_mask], missing[select_mask], select_plan["uid"].astype(str).tolist()
    )
    thresholds: Dict[str, Dict[str, object]] = {}
    frontier_hashes: Dict[str, str] = {}
    score_rows = []
    for probe in PROBES:
        values = select_scores[probe]
        support = values[select_plan["role"].eq("support_val").to_numpy()]
        auxiliary = values[select_plan["role"].eq("aux_select").to_numpy()]
        ton = values[select_plan["role"].eq("aux_normal_select").to_numpy()]
        threshold, frontier = core.choose_threshold(support, auxiliary, ton)
        thresholds[probe] = threshold_dict(threshold)
        frontier_path = out / ("ckda_d1_%s_threshold_frontier.csv" % probe.lower())
        core.atomic_csv(frontier_path, frontier, list(frontier[0]))
        frontier_hashes[probe] = core.sha256_file(frontier_path)
        for index, row in select_plan.iterrows():
            score_rows.append({
                "candidate_id": candidate,
                "probe_id": probe,
                "uid": str(row["uid"]),
                "role": str(row["role"]),
                "score": float(values[index]),
                "hard": int(core.apply_threshold(np.asarray([values[index]]), threshold)[0]),
            })
    score_path = out / "ckda_d1_select_scores.csv.gz"
    core.atomic_csv_stream(
        score_path,
        iter(score_rows),
        ["candidate_id", "probe_id", "uid", "role", "score", "hard"],
        compress=True,
    )
    marker = {
        "status": "CKDA_D1_THRESHOLDS_FROZEN",
        "contract_sha256": core.CONTRACT_SHA256,
        "candidate_id": candidate,
        "fit_select_plan_sha256": plan_sha,
        "fit_select_embeddings_sha256": core.sha256_file(args.embeddings),
        "probe_state_sha256": core.sha256_file(state_path),
        "select_scores_sha256": core.sha256_file(score_path),
        "thresholds": thresholds,
        "frontier_sha256": frontier_hashes,
        "fit_rows": int(fit_mask.sum()),
        "select_rows": int(select_mask.sum()),
        "report_rows_opened": 0,
        "report_labels_opened": 0,
        "final_files_opened": 0,
    }
    marker_path = out / "ckda_d1_threshold_freeze_marker.json"
    core.atomic_json(marker_path, marker)
    print(json.dumps(marker, indent=2, sort_keys=True))


def parse_threshold(value: Mapping[str, object]) -> core.ThresholdSpec:
    return core.ThresholdSpec(
        str(value["kind"]),
        None if value.get("value") is None else float(value["value"]),
        str(value["canonical"]),
        int(value["support_hard"]),
        int(value["auxiliary_hard"]),
        int(value["ton_hard"]),
    )


def run_report(args: argparse.Namespace) -> None:
    plan_path = Path(args.plan)
    plan_sha = core.sha256_file(plan_path)
    plan = pd.read_csv(plan_path, keep_default_na=False)
    if set(plan["plan_scope"]) != {"REPORT_ONE_SHOT_ONLY"} or len(plan) != 262_050:
        raise RuntimeError("report plan identity drift")
    with Path(args.marker).open("r", encoding="utf-8") as handle:
        marker = json.load(handle)
    if marker.get("status") != "CKDA_D1_THRESHOLDS_FROZEN" or marker.get("contract_sha256") != core.CONTRACT_SHA256:
        raise RuntimeError("threshold marker identity drift")
    if marker.get("candidate_id") != args.candidate or set(marker.get("thresholds", {})) != set(PROBES):
        raise RuntimeError("threshold marker candidate/probe drift")
    if core.sha256_file(args.state) != marker.get("probe_state_sha256"):
        raise RuntimeError("frozen probe state SHA drift")
    uids, representations, missing, candidate = load_embeddings(args.embeddings, plan_sha)
    plan, representations, missing = exact_join(plan, uids, representations, missing)
    if candidate != args.candidate:
        raise RuntimeError("report candidate identity drift")
    scores = score_frozen(load_state(args.state), representations, missing, plan["uid"].astype(str).tolist())
    hard_by_probe = {
        probe: core.apply_threshold(scores[probe], parse_threshold(marker["thresholds"][probe]))
        for probe in PROBES
    }

    def score_rows():
        for probe in PROBES:
            hard = hard_by_probe[probe]
            for index, row in plan.iterrows():
                yield {
                    "candidate_id": candidate,
                    "probe_id": probe,
                    "uid": str(row["uid"]),
                    "role": str(row["role"]),
                    "source_group": str(row["source_group"]),
                    "device_family": str(row["device_family"]),
                    "attack_family": str(row["attack_family"]),
                    "label_metric_only": int(row["label_metric_only"]),
                    "score": float(scores[probe][index]),
                    "hard": int(hard[index]),
                    "missing": int(missing[index]),
                    "c1_hard": int(row["c1_hard"]),
                    "frozen_ckbq_hard": int(row["frozen_ckbq_hard"]),
                    "m7_hard": int(row["hard__M7-TabM-TailMargin-DualControl"]),
                    "review": str(row["review"]),
                }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    score_path = out / "ckda_d1_report_scores.csv.gz"
    fields = [
        "candidate_id", "probe_id", "uid", "role", "source_group", "device_family",
        "attack_family", "label_metric_only", "score", "hard", "missing", "c1_hard",
        "frozen_ckbq_hard", "m7_hard", "review",
    ]
    score_rows_written = core.atomic_csv_stream(score_path, score_rows(), fields, compress=True)
    audit = {
        "status": "CKDA_D1_ONE_SHOT_REPORT_SCORED",
        "contract_sha256": core.CONTRACT_SHA256,
        "candidate_id": candidate,
        "report_plan_sha256": plan_sha,
        "threshold_marker_sha256": core.sha256_file(args.marker),
        "probe_state_sha256": core.sha256_file(args.state),
        "report_embeddings_sha256": core.sha256_file(args.embeddings),
        "report_scores_sha256": core.sha256_file(score_path),
        "report_rows": len(plan),
        "score_rows": score_rows_written,
        "missing_targets": int(missing.sum()),
        "duplicate_targets": 0,
        "nonfinite_nonmissing": 0,
        "final_files_opened": 0,
    }
    core.atomic_json(out / "ckda_d1_report_score_audit.json", audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--scope", choices=("fit-select", "report"), required=True)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--candidate", choices=("I1", "E3"), required=True)
    result.add_argument("--plan", type=Path, required=True)
    result.add_argument("--embeddings", type=Path, required=True)
    result.add_argument("--state", type=Path)
    result.add_argument("--marker", type=Path)
    result.add_argument("--out", type=Path, required=True)
    return result


def main() -> None:
    args = parser().parse_args()
    core.verify_contract(args.contract)
    if args.scope == "fit-select":
        if args.state is not None or args.marker is not None:
            raise RuntimeError("fit/select scope forbids external state/marker")
        run_fit_select(args)
    else:
        if args.state is None or args.marker is None:
            raise RuntimeError("report scope requires frozen state and marker")
        run_report(args)


if __name__ == "__main__":
    main()
