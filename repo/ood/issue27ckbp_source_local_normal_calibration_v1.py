"""CKBP: source-held-out one-sided normal-evidence calibration.

CKBP keeps the frozen C1 attack-candidate anchor and the mature raw
Kitsune/AfterImage115 representation.  It does not train another symmetric
attack-versus-benign classifier.  Instead, it fits a normal-only shrinkage
model on legal benign fit sources, calibrates nonconformity on source-disjoint
legal benign select sources, and asks whether a C1 candidate is conformal with
a bounded, source-local past-only normal reference. Leave-one-fit-source-out
scores remain a diagnostic rather than the deployed conformal reference.

The report-time state is label-free, source-local, score-before-update, and
phase-isolated.  Unreliable or cold-start state fails closed to C1 hard.  A
deliberately unbounded source-adaptation control is reported but can never be
the registered primary.  The original strict 1M roles, frozen T0 manifests,
and CKBO's separate 31-source benign extension remain read-only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import tempfile
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn
from sklearn.covariance import LedoitWolf
from sklearn.preprocessing import QuantileTransformer


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbm_tabm_causal_source_calibration_v1 as ckbm  # noqa: E402
import issue27ckbo_mature_afterimage_transfer_v1 as ckbo  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402


ISSUE = "issue27ckbp_source_local_normal_calibration_v1_2026-07-15"
ROOT = cko.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
SEED = 27
PRIMARY = "M2-CappedSourceConformal"
FIT_ROWS_PER_SOURCE = 600
BURN_IN = 64
HISTORY_WINDOW = 256
UPDATE_GUARD_MAD = 3.0
SHIFT_LOWER_QUANTILE = 0.10
SHIFT_UPPER_QUANTILE = 0.90


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    mode: str
    primary: bool = False
    deployable: bool = True


CANDIDATES = (
    CandidateSpec("M1-GlobalNormalConformal", "global"),
    CandidateSpec(PRIMARY, "capped_source", primary=True),
    CandidateSpec("A1-UnboundedSourceConformal", "unbounded_source", deployable=False),
    CandidateSpec("A2-LocalRobustDeviation", "local_robust", deployable=False),
)


@dataclass
class NormalModel:
    transformer: QuantileTransformer
    location: np.ndarray
    precision: np.ndarray
    model_sha256: str
    fit_rows: int
    fit_sources: int


@dataclass
class CalibrationReference:
    raw_reference: np.ndarray
    adjusted_reference: np.ndarray
    robust_reference: np.ndarray
    source_center: float
    shift_low: float
    shift_high: float
    mad_floor: float
    mad_high: float
    source_rows: list[dict[str, Any]]


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def dump_json(path: Path, payload: Any) -> None:
    write_text_lf(path, json.dumps(ckbm.json_ready(payload), indent=2, sort_keys=True) + "\n")


def write_csv_lf(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_arrays(*arrays: np.ndarray) -> str:
    digest = hashlib.sha256()
    for value in arrays:
        array = np.ascontiguousarray(np.asarray(value))
        digest.update(str(array.dtype).encode("ascii"))
        digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
        digest.update(array.tobytes())
    return digest.hexdigest()


def ordered(records: Iterable[ckbj.Record]) -> list[ckbj.Record]:
    return sorted(
        records,
        key=lambda record: (
            str(record.m1_phase),
            str(record.source),
            int(record.event_position),
            int(record.recorded_index),
            str(record.uid),
        ),
    )


def balanced_normal_records(records: Iterable[ckbj.Record], cap: int) -> list[ckbj.Record]:
    by_source: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in records:
        if int(record.label) != 0:
            raise RuntimeError("normal-only fit received an attack-labelled record")
        by_source[str(record.source)].append(record)
    if len(by_source) < 3:
        raise RuntimeError(f"normal-only fit needs at least three sources: {len(by_source)}")
    selected: list[ckbj.Record] = []
    for source, group in sorted(by_source.items()):
        values = ordered(group)
        if len(values) > int(cap):
            indices = np.linspace(0, len(values) - 1, num=int(cap), dtype=np.int64)
            values = [values[int(index)] for index in indices]
        selected.extend(values)
        if not values:
            raise RuntimeError(f"empty normal source after cap: {source}")
    return selected


def raw_matrix(records: list[ckbj.Record], values: dict[str, np.ndarray]) -> np.ndarray:
    matrix = ckbm.stack_map(records, values).astype(np.float64)
    if matrix.ndim != 2 or matrix.shape[1] != 115 or not np.isfinite(matrix).all():
        raise RuntimeError(f"invalid raw AfterImage normal matrix: {matrix.shape}")
    return np.arcsinh(np.clip(matrix, -1e12, 1e12))


def fit_normal_model(records: list[ckbj.Record], values: dict[str, np.ndarray], seed: int) -> NormalModel:
    balanced = balanced_normal_records(records, FIT_ROWS_PER_SOURCE)
    matrix = raw_matrix(balanced, values)
    n_quantiles = max(10, min(512, len(matrix)))
    transformer = QuantileTransformer(
        n_quantiles=n_quantiles,
        output_distribution="normal",
        subsample=1_000_000_000,
        random_state=int(seed),
    ).fit(matrix)
    transformed = np.clip(transformer.transform(matrix), -8.0, 8.0)
    estimator = LedoitWolf(store_precision=True, assume_centered=False).fit(transformed)
    location = np.asarray(estimator.location_, dtype=np.float64)
    precision = np.asarray(estimator.precision_, dtype=np.float64)
    if location.shape != (115,) or precision.shape != (115, 115):
        raise RuntimeError("LedoitWolf normal model shape drift")
    model_hash = sha256_arrays(transformer.quantiles_, transformer.references_, location, precision)
    return NormalModel(
        transformer=transformer,
        location=location,
        precision=precision,
        model_sha256=model_hash,
        fit_rows=len(balanced),
        fit_sources=len({record.source for record in balanced}),
    )


def normal_nonconformity(
    model: NormalModel,
    records: list[ckbj.Record],
    values: dict[str, np.ndarray],
) -> np.ndarray:
    if not records:
        return np.zeros(0, dtype=np.float64)
    transformed = np.clip(model.transformer.transform(raw_matrix(records, values)), -8.0, 8.0)
    delta = transformed - model.location[None, :]
    squared = np.einsum("ij,jk,ik->i", delta, model.precision, delta, optimize=True)
    scores = np.log1p(np.maximum(squared, 0.0))
    if not np.isfinite(scores).all():
        raise RuntimeError("nonfinite normal nonconformity score")
    return scores.astype(np.float64)


def source_out_of_fold_scores(
    fit_normal: list[ckbj.Record],
    values: dict[str, np.ndarray],
    seed: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    balanced = balanced_normal_records(fit_normal, FIT_ROWS_PER_SOURCE)
    by_source: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in balanced:
        by_source[str(record.source)].append(record)
    score_map: dict[str, float] = {}
    rows: list[dict[str, Any]] = []
    for fold, held_source in enumerate(sorted(by_source)):
        train = [record for source, group in by_source.items() if source != held_source for record in group]
        test = ordered(by_source[held_source])
        model = fit_normal_model(train, values, seed + 1009 * (fold + 1))
        scores = normal_nonconformity(model, test, values)
        score_map.update({record.uid: float(score) for record, score in zip(test, scores)})
        rows.append(
            {
                "held_source": held_source,
                "fold": fold,
                "fit_sources": model.fit_sources,
                "fit_rows": model.fit_rows,
                "held_rows": len(test),
                "held_score_median": float(np.median(scores)),
                "held_score_mad": float(np.median(np.abs(scores - np.median(scores)))),
                "held_source_used_in_fit": 0,
                "report_rows_used": 0,
                "attack_rows_used": 0,
                "model_sha256": model.model_sha256,
            }
        )
    if len(score_map) != len(balanced):
        raise RuntimeError("source-out-of-fold normal scores lost rows")
    return score_map, rows


def build_calibration_reference(
    fit_normal: list[ckbj.Record],
    oof_scores: dict[str, float],
) -> CalibrationReference:
    by_source: defaultdict[str, list[float]] = defaultdict(list)
    for record in balanced_normal_records(fit_normal, FIT_ROWS_PER_SOURCE):
        by_source[str(record.source)].append(float(oof_scores[record.uid]))
    source_medians = {source: float(np.median(scores)) for source, scores in by_source.items()}
    source_mads = {
        source: float(np.median(np.abs(np.asarray(scores) - source_medians[source])))
        for source, scores in by_source.items()
    }
    center = float(np.median(list(source_medians.values())))
    shifts = np.asarray([value - center for value in source_medians.values()], dtype=np.float64)
    shift_low = float(np.quantile(shifts, SHIFT_LOWER_QUANTILE))
    shift_high = float(np.quantile(shifts, SHIFT_UPPER_QUANTILE))
    positive_mads = np.asarray([value for value in source_mads.values() if value > 0], dtype=np.float64)
    mad_floor = float(max(np.quantile(positive_mads, 0.10) if len(positive_mads) else 1e-6, 1e-6))
    mad_high = float(max(np.quantile(list(source_mads.values()), 0.95), mad_floor))
    raw: list[float] = []
    adjusted: list[float] = []
    robust: list[float] = []
    source_rows: list[dict[str, Any]] = []
    for source, scores in sorted(by_source.items()):
        median = source_medians[source]
        mad = max(source_mads[source], mad_floor)
        bounded_shift = float(np.clip(median - center, shift_low, shift_high))
        raw.extend(scores)
        adjusted.extend(float(value - bounded_shift) for value in scores)
        robust.extend(float(abs(value - median) / (1.4826 * mad)) for value in scores)
        source_rows.append(
            {
                "source": source,
                "rows": len(scores),
                "oof_score_median": median,
                "oof_score_mad": source_mads[source],
                "bounded_shift": bounded_shift,
                "shift_clipped": not math.isclose(bounded_shift, median - center),
                "report_rows_used": 0,
                "attack_rows_used": 0,
            }
        )
    return CalibrationReference(
        raw_reference=np.sort(np.asarray(raw, dtype=np.float64)),
        adjusted_reference=np.sort(np.asarray(adjusted, dtype=np.float64)),
        robust_reference=np.sort(np.asarray(robust, dtype=np.float64)),
        source_center=center,
        shift_low=shift_low,
        shift_high=shift_high,
        mad_floor=mad_floor,
        mad_high=mad_high,
        source_rows=source_rows,
    )


def empirical_normal_p(reference: np.ndarray, nonconformity: float) -> float:
    values = np.asarray(reference, dtype=np.float64)
    if values.ndim != 1 or not len(values) or not np.isfinite(values).all() or not math.isfinite(nonconformity):
        raise RuntimeError("empirical conformal score needs finite reference and current value")
    # Higher nonconformity is less normal.  The +1 finite-sample correction is
    # the standard inductive conformal rank; CKBP does not claim sequential
    # exchangeability for the adapted report stream.
    at_least = len(values) - int(np.searchsorted(values, nonconformity, side="left"))
    return float((1 + at_least) / (len(values) + 1))


def causal_candidate_scores(
    spec: CandidateSpec,
    records: list[ckbj.Record],
    base_scores: dict[str, float],
    reference: CalibrationReference,
    burn_in: int = BURN_IN,
    window: int = HISTORY_WINDOW,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    if spec.mode == "global":
        scores = {
            record.uid: 1.0 - empirical_normal_p(reference.raw_reference, float(base_scores[record.uid]))
            for record in records
        }
        return scores, [
            {
                "candidate": spec.name,
                "phase": "all",
                "source": "GLOBAL_NO_REPORT_ADAPTATION",
                "records": len(records),
                "fresh_resets": 0,
                "score_before_update_records": len(records),
                "history_updates": 0,
                "history_rejections": 0,
                "cold_start_records": 0,
                "unreliable_records": 0,
                "phase_state_crossing": False,
                "label_read_for_state": False,
                "future_events_used": False,
                "report_gradient_updates": 0,
                "history_scope": "not_applicable_global_score",
                "memory_only_events": 0,
            }
        ]

    by_scope: defaultdict[tuple[str, str], list[ckbj.Record]] = defaultdict(list)
    for record in records:
        by_scope[(str(record.m1_phase), str(record.source))].append(record)
    result: dict[str, float] = {}
    audits: list[dict[str, Any]] = []
    for (phase, source), group in sorted(by_scope.items()):
        group = ordered(group)
        positions = np.asarray([int(record.event_position) for record in group], dtype=np.int64)
        gaps = np.diff(positions) if len(positions) > 1 else np.zeros(0, dtype=np.int64)
        history: deque[float] = deque(maxlen=int(window))
        updates = 0
        rejected = 0
        cold = 0
        unreliable = 0
        clipped = 0
        applied_shifts: list[float] = []
        for record in group:
            current = float(base_scores[record.uid])
            # Score strictly before considering the current event for state.
            if len(history) < int(burn_in):
                attack_score = 1.0
                accept = True
                cold += 1
            else:
                past = np.asarray(history, dtype=np.float64)
                median = float(np.median(past))
                raw_mad = float(np.median(np.abs(past - median)))
                mad = max(raw_mad, reference.mad_floor)
                reliable = bool(raw_mad <= 2.0 * reference.mad_high + reference.mad_floor)
                if spec.mode == "local_robust":
                    nonconformity = abs(current - median) / (1.4826 * mad)
                    ref = reference.robust_reference
                else:
                    raw_shift = median - reference.source_center
                    if spec.mode == "capped_source":
                        shift = float(np.clip(raw_shift, reference.shift_low, reference.shift_high))
                        clipped += int(not math.isclose(shift, raw_shift))
                    elif spec.mode == "unbounded_source":
                        shift = raw_shift
                    else:
                        raise RuntimeError(f"unknown calibration candidate mode: {spec.mode}")
                    applied_shifts.append(float(shift))
                    nonconformity = current - shift
                    ref = reference.adjusted_reference
                attack_score = 1.0 - empirical_normal_p(ref, nonconformity) if reliable else 1.0
                unreliable += int(not reliable)
                # An unreliable provisional cohort never receives more state.
                # A stable attack stream can still resemble a shifted normal
                # stream, so the deployable candidate additionally caps its
                # total influence to legal source-disjoint select shifts.
                accept = bool(
                    reliable and current <= median + float(UPDATE_GUARD_MAD) * 1.4826 * mad
                )
            result[record.uid] = float(np.clip(attack_score, 0.0, 1.0))
            if accept:
                history.append(current)
                updates += 1
            else:
                rejected += 1
        audits.append(
            {
                "candidate": spec.name,
                "phase": phase,
                "source": source,
                "records": len(group),
                "fresh_resets": 1,
                "score_before_update_records": len(group),
                "history_updates": updates,
                "history_rejections": rejected,
                "provisional_burn_in_records": min(len(group), int(burn_in)),
                "cold_start_records": cold,
                "unreliable_records": unreliable,
                "bounded_shift_clips": clipped,
                "minimum_applied_shift": min(applied_shifts) if applied_shifts else math.nan,
                "maximum_applied_shift": max(applied_shifts) if applied_shifts else math.nan,
                "registered_shift_low": reference.shift_low,
                "registered_shift_high": reference.shift_high,
                "bounded_shift_contract": spec.mode == "capped_source",
                "phase_state_crossing": False,
                "label_read_for_state": False,
                "future_events_used": False,
                "report_gradient_updates": 0,
                "history_scope": "frozen_scored_target_rows_only",
                "memory_only_events": 0,
                "first_event_position": int(positions.min()) if len(positions) else -1,
                "last_event_position": int(positions.max()) if len(positions) else -1,
                "median_event_position_gap": float(np.median(gaps)) if len(gaps) else math.nan,
                "max_event_position_gap": int(gaps.max()) if len(gaps) else 0,
            }
        )
    if len(result) != len(records):
        raise RuntimeError("causal source calibration lost or duplicated records")
    return result, audits


def prepare_inputs(args: argparse.Namespace, out: Path) -> tuple[Any, ...]:
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckbo.ckao.add_family_columns(frames)
    auxiliary_keys = set(ckbo.AUX_FIT_SELECT_DEVICE_KEYS) | set(ckbo.AUX_HELD_DEVICE_KEYS)
    overlap = sorted(
        {
            Path(str(source)).stem
            for frame in frames.values()
            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
            if Path(str(source)).stem in auxiliary_keys
        }
    )
    if overlap:
        raise RuntimeError(f"auxiliary source overlaps frozen 1M roles: {overlap[:3]}")
    live = ckbi.report_only_exclusion(frames)
    live.to_csv(out / "ckbp_live_report_extension_exclusion.csv", index=False)
    required = live.loc[live["required_zero"].notna()]
    if (
        required.empty
        or int(pd.to_numeric(required["extension_source_rows_used"]).sum()) != 0
        or not bool(ckbj.bool_series(required["pass"]).all())
    ):
        raise RuntimeError("report-only extension isolation failed")
    base_t0 = T0Cache(Path(args.t0_root))
    t0_audit = ckbj.validate_t0_runtime(base_t0)
    extension_audit = ckbj.validate_report_extension(Path(args.report_t0_extension))
    c1_audit = c1ext.validate_extension(
        Path(args.c1_report_extension),
        Path(args.report_t0_extension),
        Path(args.c1_plan),
        Path(args.c1_targets),
    )
    t0 = ckbj.CompositeT0Cache(
        base_t0,
        Path(args.report_t0_extension),
        set(extension_audit["extension_sources"]),
    )
    coverage = ckbj.required_report_source_coverage(frames, t0)
    pd.DataFrame(coverage).to_csv(out / "ckbp_required_report_source_coverage.csv", index=False)
    if any(not bool(row["full_source_coverage"]) for row in coverage):
        raise RuntimeError("formal target coverage incomplete")
    pd.DataFrame(ckbj.support_val_lineage(frames)).to_csv(out / "ckbp_support_val_lineage.csv", index=False)
    return x_by_role, frames, input_audit, t0, t0_audit, extension_audit, c1_audit


def run_protocol(
    held: str | None,
    args: argparse.Namespace,
    x_by_role: dict[str, np.ndarray],
    report_frames: dict[str, pd.DataFrame],
    model_frames: dict[str, pd.DataFrame],
    t0: Any,
    position_cache: dict[str, dict[int, int]],
    aux: ckbo.AuxiliaryData,
) -> dict[str, list[dict[str, Any]]]:
    protocol = ckbo.protocol_family_name(held)
    c1_model, frontend, c1_threshold, c1_audit = ckbo.fit_c1_attack_preserving(
        x_by_role,
        model_frames,
        held,
        Path(args.c1_cache),
        Path(args.c1_plan),
        Path(args.c1_report_extension),
        int(args.train_cap),
    )
    sets, data_audit = ckbo.collect_formal_sets(
        c1_model,
        frontend,
        model_frames,
        report_frames,
        t0,
        position_cache,
        held,
        int(args.train_cap),
        int(args.eval_cap),
    )
    if held is None and (len(sets["fit_attack"]) != 385 or len(sets["select_attack"]) != 69):
        raise RuntimeError("global support_train/support_val cardinality drift")
    if held == ckbo.AUX_HELD_FAMILY:
        sets["report"] = list(aux.records_report)
        data_audit.append(
            {
                "role": "aux_report",
                "frame_phase": "report",
                "m1_phase": "report",
                "held_value": ckbo.AUX_HELD_FAMILY,
                "eligible_role_rows": len(aux.records_report),
                "frozen_target_rows": len(aux.records_report),
                "outside_frozen_target_cohort": 0,
                "target_alignment_incomplete": 0,
                "requested_rows": len(aux.records_report),
                "cache_aligned_rows": len(aux.records_report),
                "unmapped_rows": 0,
                "label_for_metric_only": 0,
                "report": True,
                "fit_select_use_count": 0,
            }
        )
    aux_fit = ckbo.exclude_held_auxiliary(aux.records_fit, held)
    aux_select = ckbo.exclude_held_auxiliary(aux.records_select, held)
    for role, phase, before, after in (
        ("aux_fit", "fit", aux.records_fit, aux_fit),
        ("aux_select", "select", aux.records_select, aux_select),
    ):
        retained_held = int(sum(held is not None and record.device_family == held for record in after))
        if retained_held:
            raise RuntimeError(f"held auxiliary family entered {role}: {held}")
        data_audit.append(
            {
                "role": role,
                "frame_phase": phase,
                "m1_phase": phase,
                "held_value": held or "GLOBAL",
                "eligible_role_rows": len(before),
                "frozen_target_rows": len(after),
                "outside_frozen_target_cohort": 0,
                "target_alignment_incomplete": 0,
                "requested_rows": len(after),
                "cache_aligned_rows": len(after),
                "unmapped_rows": 0,
                "label_for_metric_only": 0,
                "report": False,
                "held_family_rows_removed": len(before) - len(after),
                "held_family_rows_retained": retained_held,
            }
        )

    fit_normal = sets["fit_benign"] + aux_fit
    select_normal = sets["select_benign"] + aux_select
    scored_records = ckbm.unique_records([sets["select_attack"], select_normal, sets["report"]])
    feature_records = ckbm.unique_records([fit_normal, scored_records])
    base = ckbo.existing_feature_map(feature_records, x_by_role, "raw115", ckbo.afterimage_schema()[0])
    add_aux = [record for record in feature_records if record.role.startswith("aux_")]
    ckbo.add_auxiliary_values(base, aux, "raw115", add_aux)
    if len(base) != len(feature_records):
        raise RuntimeError("raw AfterImage feature map coverage incomplete")

    final_model = fit_normal_model(fit_normal, base, int(args.seed))
    _oof_scores, fold_rows = source_out_of_fold_scores(fit_normal, base, int(args.seed))
    # The deployed empirical reference is not formed from optimistic in-sample
    # fit scores or from fold-specific models. It is scored by the exact final
    # fit-only model on legal, source-disjoint benign select sources. The OOF
    # fit-source scores above are retained solely as a generalization audit.
    if len({record.source for record in select_normal}) < 3:
        raise RuntimeError("normal calibration needs at least three source-disjoint select sources")
    select_reference_values = normal_nonconformity(final_model, select_normal, base)
    select_reference_scores = {
        record.uid: float(value) for record, value in zip(select_normal, select_reference_values)
    }
    reference = build_calibration_reference(select_normal, select_reference_scores)
    final_values = normal_nonconformity(final_model, scored_records, base)
    base_scores = {record.uid: float(value) for record, value in zip(scored_records, final_values)}

    candidate_rows: list[dict[str, Any]] = []
    calibration_rows: list[dict[str, Any]] = []
    scores: dict[str, dict[str, float]] = {}
    thresholds: dict[str, float] = {}
    for spec in CANDIDATES:
        score_map, state_rows = causal_candidate_scores(spec, scored_records, base_scores, reference)
        threshold, frontier, gate_pass = ckbm.choose_verifier_gate(
            spec.name,
            sets["select_attack"],
            select_normal,
            score_map,
            c1_threshold,
        )
        scores[spec.name] = score_map
        thresholds[spec.name] = threshold
        calibration_rows.extend({**row, "held_value": protocol} for row in state_rows)
        for row in frontier:
            candidate_rows.append(
                {
                    **row,
                    "held_value": protocol,
                    "mode": spec.mode,
                    "primary": spec.primary,
                    "deployable": spec.deployable,
                    "gate_constraint_pass": gate_pass,
                    "c1_candidate_threshold": c1_threshold,
                    "burn_in": BURN_IN if spec.mode != "global" else 0,
                    "history_window": HISTORY_WINDOW if spec.mode != "global" else 0,
                    "report_rows_used": 0,
                }
            )

    strict_records = (
        sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
        if held is None
        else sets["report"]
    )
    c1_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    metrics: list[dict[str, Any]] = []
    family_metrics: list[dict[str, Any]] = []
    attack_summary: list[dict[str, Any]] = []
    strict_summary: list[dict[str, Any]] = []
    metric, family = ckbj.metric_rows(
        "M0-C1",
        "strict_leave" if held else "attack_preservation",
        protocol,
        strict_records,
        c1_hard,
        int(args.bootstrap_reps),
        int(args.seed),
    )
    metrics.extend(metric)
    family_metrics.extend(family)
    if held is None:
        attack_summary.extend(
            ckbj.attack_summary_rows(
                "M0-C1", strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
            )
        )
    else:
        strict_summary.extend(
            ckbj.strict_level2_summary(
                "M0-C1", protocol, strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
            )
        )
    for spec in CANDIDATES:
        hard = ckbj.hard_decisions(
            spec.name,
            strict_records,
            scores[spec.name],
            c1_threshold,
            thresholds[spec.name],
        )
        metric, family = ckbj.metric_rows(
            spec.name,
            "strict_leave" if held else "attack_preservation",
            protocol,
            strict_records,
            hard,
            int(args.bootstrap_reps),
            int(args.seed),
        )
        metrics.extend(metric)
        family_metrics.extend(family)
        if held is None:
            attack_summary.extend(
                ckbj.attack_summary_rows(
                    spec.name, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
                )
            )
        else:
            strict_summary.extend(
                ckbj.strict_level2_summary(
                    spec.name, protocol, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
                )
            )

    model_rows = [
        {
            "held_value": protocol,
            "model": "normal_only_quantile_ledoit_wolf",
            "frontend": "mature_raw_afterimage115",
            "fit_rows": final_model.fit_rows,
            "fit_sources": final_model.fit_sources,
            "fit_attack_rows": 0,
            "fit_report_rows": 0,
            "source_disjoint_select_reference": True,
            "source_out_of_fold_diagnostic": True,
            "source_oof_folds": len(fold_rows),
            "reference_rows": len(reference.raw_reference),
            "reference_sources": len(reference.source_rows),
            "reference_attack_rows": 0,
            "reference_report_rows": 0,
            "model_sha256": final_model.model_sha256,
            "raw_reference_rows": len(reference.raw_reference),
            "shift_low": reference.shift_low,
            "shift_high": reference.shift_high,
            "mad_floor": reference.mad_floor,
            "mad_high": reference.mad_high,
            "report_gradient_updates": 0,
            "report_threshold_updates": 0,
            "review_rate": 0.0,
        }
    ]
    for row in fold_rows:
        row["held_value"] = protocol
    for row in reference.source_rows:
        row["held_value"] = protocol

    support_rows = []
    support_family_rows = []
    if held is None:
        for record in sets["fit_attack"]:
            support_rows.append(
                {
                    "uid": record.uid,
                    "attack_family": record.attack_family,
                    "source": record.source,
                    "candidate": "M0-C1",
                    "usage": "supervised_C1_anchor_fit",
                    "fit_count": 1,
                    "used_at_least_once": True,
                    "normal_calibrator_fit_count": 0,
                }
            )
        for family in sorted({record.attack_family for record in sets["fit_attack"]}):
            group = [record for record in sets["fit_attack"] if record.attack_family == family]
            support_family_rows.append(
                {
                    "attack_family": family,
                    "unique_rows": len(group),
                    "C1_fit_visits": len(group),
                    "normal_calibrator_fit_visits": 0,
                }
            )
    event_scope = ckbj.event_scope_rows(sets, set(getattr(t0, "report_only_sources", set())))
    for row in event_scope:
        row.update({"held_value": protocol, "protocol_run": protocol})
    sealed_audit = [
        {
            "held_value": protocol,
            "sealed_family": "iotsim-cooler-motor",
            "fit_records_used": 0,
            "select_records_used": 0,
            "report_records_scored": int(
                sum(record.device_family == "iotsim-cooler-motor" for record in sets["report"])
            ),
            "metric_labels_opened": 0,
            "sealed_unopened": True,
        }
    ]
    for row in data_audit + c1_audit:
        row["protocol_run"] = protocol
    return {
        "c1_audit": c1_audit,
        "data_audit": data_audit,
        "candidate_selection": candidate_rows,
        "model_audit": model_rows,
        "source_oof": fold_rows,
        "source_reference": reference.source_rows,
        "calibration_state": calibration_rows,
        "support_usage": support_rows,
        "support_family_usage": support_family_rows,
        "metrics": metrics,
        "family_metrics": family_metrics,
        "attack_summary": attack_summary,
        "strict_summary": strict_summary,
        "event_scope": event_scope,
        "sealed_audit": sealed_audit,
    }


def decision(
    attack: pd.DataFrame,
    strict: pd.DataFrame,
    selection: pd.DataFrame,
    permanent: pd.DataFrame,
    support: pd.DataFrame,
    data: pd.DataFrame,
    model: pd.DataFrame,
    calibration: pd.DataFrame,
    dev_holds: list[str],
) -> dict[str, Any]:
    def one(table: pd.DataFrame, column: str, **where: Any) -> float | None:
        part = table
        for key, value in where.items():
            if key not in part:
                return None
            part = part.loc[part[key].eq(value)]
        return None if part.empty else float(part.iloc[0][column])

    overall = one(attack, "delta_vs_c1_pp", candidate=PRIMARY, metric="overall_attack_hard_recall")
    stream = one(strict, "hard_rate", candidate=PRIMARY, held_value="iotsim-stream-consumer")
    stream_c1 = one(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-stream-consumer")
    hydraulic = one(strict, "hard_rate", candidate=PRIMARY, held_value="iotsim-hydraulic-system")
    hydraulic_c1 = one(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-hydraulic-system")
    major = attack.loc[
        attack.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & attack.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")
        & pd.to_numeric(attack.get("rows", 0), errors="coerce").fillna(0).ge(15)
    ]
    dev = strict.loc[
        strict.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & strict.get("held_value", pd.Series(dtype=str)).isin(dev_holds)
    ]
    dev_c1 = strict.loc[
        strict.get("candidate", pd.Series(dtype=str)).eq("M0-C1")
        & strict.get("held_value", pd.Series(dtype=str)).isin(dev_holds)
    ]
    dev_rates = {str(row.held_value): float(row.hard_rate) for row in dev.itertuples(index=False)}
    dev_c1_rates = {str(row.held_value): float(row.hard_rate) for row in dev_c1.itertuples(index=False)}
    dev_macro = float(dev["hard_rate"].mean()) if len(dev) == len(dev_holds) and dev_holds else None
    dev_c1_macro = float(dev_c1["hard_rate"].mean()) if len(dev_c1) == len(dev_holds) and dev_holds else None
    dev_each = bool(
        len(dev_holds) >= 2
        and all(
            value in dev_rates
            and value in dev_c1_rates
            and dev_rates[value] <= 0.90
            and dev_rates[value] <= dev_c1_rates[value] - 0.05
            for value in dev_holds
        )
    )
    selected_mask = (
        ckbm.decision_bool_series(selection["selected"], False)
        if "selected" in selection
        else pd.Series(False, index=selection.index)
    )
    selected = selection.loc[selection.get("candidate", pd.Series(dtype=str)).eq(PRIMARY) & selected_mask]
    gate_pass = (
        ckbm.decision_bool_series(selected["gate_constraint_pass"], False)
        if "gate_constraint_pass" in selected
        else pd.Series(False, index=selected.index)
    )
    alignment = (
        pd.to_numeric(data["target_alignment_incomplete"], errors="coerce").fillna(1)
        if "target_alignment_incomplete" in data
        else pd.Series(1, index=data.index)
    )
    calibration_bool = (
        ckbm.decision_bool_series(calibration["phase_state_crossing"], False)
        if "phase_state_crossing" in calibration
        else pd.Series(True, index=calibration.index)
    )
    checks = {
        "required_metrics_missing": any(
            value is None for value in (overall, stream, stream_c1, hydraulic, hydraulic_c1, dev_macro, dev_c1_macro)
        ),
        "overall_attack_drop_over_0_5pp": bool(overall is not None and overall < -0.5),
        "major_attack_family_drop_over_2pp": bool(not major.empty and (major["delta_vs_c1_pp"] < -2.0).any()),
        "stream_signal_missing": bool(
            stream is None or stream_c1 is None or stream > 0.90 or stream > stream_c1 - 0.10
        ),
        "hydraulic_worsened_over_2pp": bool(
            hydraulic is not None and hydraulic_c1 is not None and hydraulic - hydraulic_c1 > 0.02
        ),
        "legal_multiheld_signal_missing": bool(
            len(dev_holds) < 2
            or dev_macro is None
            or dev_c1_macro is None
            or dev_macro > dev_c1_macro - 0.05
            or not dev_each
        ),
        "permanent_report_family_used": bool(
            permanent.empty
            or permanent[
                ["fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count"]
            ].to_numpy().sum()
            != 0
        ),
        "support_usage_incomplete": bool(
            len(support) != 385
            or len(set(support.get("uid", pd.Series(dtype=str)).astype(str))) != 385
            or not support.get("used_at_least_once", pd.Series(False, index=support.index)).astype(bool).all()
        ),
        "target_alignment_incomplete": bool(data.empty or alignment.gt(0).any()),
        "gate_constraint_failed": bool(selected.empty or not gate_pass.all()),
        "normal_model_used_attack_or_report": bool(
            model.empty
            or pd.to_numeric(model.get("fit_attack_rows", 1), errors="coerce").fillna(1).gt(0).any()
            or pd.to_numeric(model.get("fit_report_rows", 1), errors="coerce").fillna(1).gt(0).any()
        ),
        "causal_order_or_reset_contract_failed": bool(
            calibration.empty
            or calibration_bool.any()
            or pd.to_numeric(calibration.get("score_before_update_records", 0), errors="coerce").sum()
            != pd.to_numeric(calibration.get("records", 0), errors="coerce").sum()
        ),
        "review_not_zero": False,
    }
    return {
        "seed": SEED,
        "candidate": PRIMARY,
        "decision": "GO_SIGNAL" if not any(checks.values()) else "NO_GO",
        "checks": checks,
        "overall_attack_delta_pp": overall,
        "stream_hard_rate": stream,
        "stream_c1_hard_rate": stream_c1,
        "hydraulic_hard_rate": hydraulic,
        "hydraulic_c1_hard_rate": hydraulic_c1,
        "legal_development_held_families": dev_holds,
        "legal_development_hard_rates": dev_rates,
        "legal_development_c1_hard_rates": dev_c1_rates,
        "legal_development_macro_hard_rate": dev_macro,
        "legal_development_c1_macro_hard_rate": dev_c1_macro,
        "legal_development_each_improves_5pp": dev_each,
        "review_rate": 0.0,
        "single_seed_scope": "calibration-route go/no-go signal only",
    }


def assert_clean_formal_out(out: Path) -> None:
    allowed = {
        "resource_usage.txt",
        "slurm_identity.txt",
        "slurm_job_at_start.txt",
        "aux_afterimage_cache",
        "ckbo_auxiliary_benign_manifest.csv",
        "ckbo_auxiliary_benign_ready.json",
    }
    unexpected = [path.name for path in out.iterdir() if path.name not in allowed]
    if unexpected:
        raise RuntimeError(f"refusing mixed CKBP formal output directory: {unexpected[:5]}")


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    if int(args.seed) != SEED:
        raise RuntimeError("first CKBP formal run is preregistered for seed 27 only")
    if int(args.aux_rows_per_source) != ckbo.MODEL_READY_PER_SOURCE:
        raise RuntimeError("formal auxiliary row contract drift")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    assert_clean_formal_out(out)
    x_by_role, report_frames, input_audit, t0, t0_audit, extension_audit, c1_extension_audit = prepare_inputs(args, out)
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    model_frames, permanent_rows = ckbo.permanently_mask_frames(report_frames)
    model_frames, frozen_scope_rows = ckbo.restrict_model_scope_to_frozen_targets(
        model_frames,
        Path(args.c1_targets),
        t0,
    )
    dev_holds = ckbo.legal_development_holds(report_frames, requested)
    if set(dev_holds) != {"iotsim-ip-camera-street", ckbo.AUX_HELD_FAMILY}:
        raise RuntimeError(f"formal development held-family boundary drift: {dev_holds}")
    aux = ckbo.materialize_auxiliary(args, out)
    if aux.manifest_sha256 != "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f":
        raise RuntimeError(f"frozen CKBO auxiliary manifest drift: {aux.manifest_sha256}")
    protocols = ckbo.formal_protocol_values(requested, dev_holds)
    position_cache: dict[str, dict[int, int]] = {}
    results = [
        run_protocol(value, args, x_by_role, report_frames, model_frames, t0, position_cache, aux)
        for value in protocols
    ]

    def table(key: str) -> pd.DataFrame:
        return pd.DataFrame([{**row, "seed": SEED} for result in results for row in result[key]])

    outputs = {
        "ckbp_c1_fit_select_audit.csv": table("c1_audit"),
        "ckbp_role_usage_audit.csv": table("data_audit"),
        "ckbp_candidate_selection.csv": table("candidate_selection"),
        "ckbp_normal_model_audit.csv": table("model_audit"),
        "ckbp_source_oof_audit.csv": table("source_oof"),
        "ckbp_source_reference_audit.csv": table("source_reference"),
        "ckbp_calibration_state_audit.csv": table("calibration_state"),
        "ckbp_support_training_usage.csv": table("support_usage"),
        "ckbp_support_family_training_usage.csv": table("support_family_usage"),
        "ckbp_all_metrics.csv": table("metrics"),
        "ckbp_per_attack_family_metrics.csv": table("family_metrics"),
        "attack_preservation_summary.csv": table("attack_summary"),
        "strict_level2_summary.csv": table("strict_summary"),
        "ckbp_event_scope_audit.csv": table("event_scope"),
        "ckbp_sealed_holdout_audit.csv": table("sealed_audit"),
        "ckbp_permanent_report_only_audit.csv": pd.DataFrame(permanent_rows),
        "ckbp_frozen_model_scope_audit.csv": pd.DataFrame(frozen_scope_rows),
    }
    outputs["ckbp_negative_sampling_audit.csv"] = pd.DataFrame(
        [
            {
                "sampled_negatives": 0,
                "status": "not_applicable_normal_only_closed_form_calibration",
                "ghost_node_negatives": 0,
                "future_identity_used": False,
                "report_rows_used": 0,
                "held_rows_used": 0,
                "seed": SEED,
            }
        ]
    )
    outputs["ckbp_optimization_audit.csv"] = pd.DataFrame(
        [
            {
                "optimizer": "closed_form_quantile_transform_plus_ledoit_wolf",
                "gradient_epochs": 0,
                "loss_curve_applicable": False,
                "nan_count": 0,
                "report_gradient_updates": 0,
                "seed": SEED,
            }
        ]
    )
    for filename, frame in outputs.items():
        frame.to_csv(out / filename, index=False)

    outcome = decision(
        outputs["attack_preservation_summary.csv"],
        outputs["strict_level2_summary.csv"],
        outputs["ckbp_candidate_selection.csv"],
        outputs["ckbp_permanent_report_only_audit.csv"],
        outputs["ckbp_support_training_usage.csv"],
        outputs["ckbp_role_usage_audit.csv"],
        outputs["ckbp_normal_model_audit.csv"],
        outputs["ckbp_calibration_state_audit.csv"],
        dev_holds,
    )
    dump_json(out / "ckbp_single_seed_go_no_go.json", outcome)
    base_manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "seed": SEED,
        "commit_sha": os.environ.get("CKBP_COMMIT_SHA", ckbm.git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "wall_seconds": time.time() - started,
        "review_rate": 0.0,
        "base_t0_manifest_sha256": ckbo.sha256_file(base_manifest),
        "expected_base_t0_manifest_sha256": ckbj.EXPECTED_T0_MANIFEST_SHA256,
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "auxiliary_manifest_sha256": aux.manifest_sha256,
        "c1_target_manifest_sha256": ckbo.sha256_file(Path(args.c1_targets)),
    }
    dump_json(out / "ckbp_environment.json", environment)
    dump_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "mode": "formal",
            "primary_candidate": PRIMARY,
            "candidates": [spec.__dict__ for spec in CANDIDATES],
            "protocols": [ckbo.protocol_family_name(value) for value in protocols],
            "legal_development_holds": dev_holds,
            "permanent_report_only": list(ckbo.PERMANENT_REPORT_ONLY),
            "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
            "sealed_unopened": ["iotsim-cooler-motor"],
            "original_1m_split_modified": False,
            "auxiliary_extension_reused_without_role_change": aux.ready,
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_report_extension_audit": c1_extension_audit,
            "normal_model_contract": "legal fit benign only; source-balanced; source-disjoint benign-select calibration; fit-source OOF diagnostic; zero attacks and reports",
            "report_contract": "source-and-phase fresh state; score-before-update; label-free past-only bounded adaptation; no gradients or thresholds",
            "attack_contract": "all 385 support_train rows supervise frozen C1 anchor; 69 support_val rows select gate only",
            "review_rate": 0.0,
            "environment": environment,
        },
    )
    write_text_lf(
        out / "codex_readout.md",
        f"# {ISSUE}\n\nSeed 27 calibration result: `{outcome['decision']}` for `{PRIMARY}`. "
        "The original strict 1M split, T0 manifests, and CKBO auxiliary role split were not modified. Review is `0`.\n",
    )
    print(json.dumps({"status": "CKBP_FORMAL_COMPLETE", "decision": outcome["decision"], "out": str(out)}, indent=2))


def contract_unit(args: argparse.Namespace) -> None:
    rng = np.random.default_rng(SEED)
    synthetic_fit: list[ckbj.Record] = []
    synthetic_values: dict[str, np.ndarray] = {}
    for source_index in range(4):
        for row_index in range(24):
            uid = f"normal-fit:{source_index}:{row_index}"
            record = ckbj.Record(
                uid=uid,
                role="unit_fit",
                m1_phase="fit",
                source=f"normal-source-{source_index}",
                recorded_index=row_index,
                event_position=row_index,
                label=0,
                attack_family="benign",
                device_family=f"normal-family-{source_index // 2}",
                source_family=f"normal-family-{source_index // 2}",
                c1_score=0.0,
                episode_id=f"normal-source-{source_index}",
            )
            synthetic_fit.append(record)
            synthetic_values[uid] = np.abs(
                rng.normal(loc=0.1 * source_index, scale=0.5, size=115)
            ).astype(np.float32)
    synthetic_model = fit_normal_model(synthetic_fit, synthetic_values, SEED)
    synthetic_oof, synthetic_folds = source_out_of_fold_scores(
        synthetic_fit, synthetic_values, SEED
    )
    assert synthetic_model.fit_sources == 4 and len(synthetic_folds) == 4
    assert len(synthetic_oof) == len(synthetic_fit)
    synthetic_select: list[ckbj.Record] = []
    for source_index in range(4):
        for row_index in range(12):
            uid = f"normal-select:{source_index}:{row_index}"
            record = ckbj.Record(
                uid=uid,
                role="unit_select",
                m1_phase="select",
                source=f"normal-select-source-{source_index}",
                recorded_index=row_index,
                event_position=row_index,
                label=0,
                attack_family="benign",
                device_family=f"normal-select-family-{source_index // 2}",
                source_family=f"normal-select-family-{source_index // 2}",
                c1_score=0.0,
                episode_id=f"normal-select-source-{source_index}",
            )
            synthetic_select.append(record)
            synthetic_values[uid] = np.abs(
                rng.normal(loc=0.08 * source_index, scale=0.5, size=115)
            ).astype(np.float32)
    synthetic_select_values = normal_nonconformity(
        synthetic_model, synthetic_select, synthetic_values
    )
    synthetic_reference = build_calibration_reference(
        synthetic_select,
        {
            record.uid: float(value)
            for record, value in zip(synthetic_select, synthetic_select_values)
        },
    )
    assert len(synthetic_reference.adjusted_reference) == len(synthetic_select)
    assert len(synthetic_reference.source_rows) == 4

    reference = CalibrationReference(
        raw_reference=np.linspace(-0.4, 0.4, 401),
        adjusted_reference=np.linspace(-0.4, 0.4, 401),
        robust_reference=np.linspace(0.0, 3.0, 401),
        source_center=0.0,
        shift_low=-0.5,
        shift_high=0.5,
        mad_floor=0.05,
        mad_high=0.30,
        source_rows=[],
    )

    def records(source: str, phase: str, values: np.ndarray) -> tuple[list[ckbj.Record], dict[str, float]]:
        rows = [
            ckbj.Record(
                uid=f"{phase}:{source}:{index}",
                role="unit",
                m1_phase=phase,
                source=source,
                recorded_index=index,
                event_position=index,
                label=0,
                attack_family="benign",
                device_family="unit",
                source_family="unit",
                c1_score=1.0,
                episode_id=source,
            )
            for index in range(len(values))
        ]
        return rows, {row.uid: float(value) for row, value in zip(rows, values)}

    normal_rows, normal_values = records("offset-normal", "report", np.full(96, 0.4))
    attack_rows, attack_values = records("far-attack", "report", np.full(96, 3.0))
    primary = next(spec for spec in CANDIDATES if spec.name == PRIMARY)
    primary_scores, primary_audit = causal_candidate_scores(
        primary,
        normal_rows + attack_rows,
        {**normal_values, **attack_values},
        reference,
        burn_in=16,
        window=32,
    )
    normal_tail = np.asarray([primary_scores[row.uid] for row in normal_rows[16:]])
    attack_tail = np.asarray([primary_scores[row.uid] for row in attack_rows[16:]])
    assert float(normal_tail.mean()) < 0.60
    assert float(attack_tail.mean()) > 0.95
    unbounded = next(spec for spec in CANDIDATES if spec.mode == "unbounded_source")
    unsafe_scores, _ = causal_candidate_scores(
        unbounded,
        attack_rows,
        attack_values,
        reference,
        burn_in=16,
        window=32,
    )
    assert float(np.mean([unsafe_scores[row.uid] for row in attack_rows[16:]])) < 0.60

    prefix_rows, prefix_values = records("past-only", "report", np.linspace(0.0, 0.2, 80))
    baseline, _ = causal_candidate_scores(primary, prefix_rows, prefix_values, reference, burn_in=16, window=32)
    changed_values = dict(prefix_values)
    for row in prefix_rows[60:]:
        changed_values[row.uid] += 5.0
    changed, _ = causal_candidate_scores(primary, prefix_rows, changed_values, reference, burn_in=16, window=32)
    assert all(math.isclose(baseline[row.uid], changed[row.uid]) for row in prefix_rows[:60])
    assert len(primary_audit) == 2 and sum(row["fresh_resets"] for row in primary_audit) == 2
    assert sum(row["score_before_update_records"] for row in primary_audit) == 192
    assert all(row["phase_state_crossing"] is False for row in primary_audit)
    assert all(row["bounded_shift_contract"] is True for row in primary_audit)
    assert all(
        row["minimum_applied_shift"] >= row["registered_shift_low"] - 1e-12
        and row["maximum_applied_shift"] <= row["registered_shift_high"] + 1e-12
        for row in primary_audit
    )

    support = [
        ckbj.Record(
            uid=f"support:{index}", role="support_val", m1_phase="select", source="attack-source",
            recorded_index=index, event_position=index, label=1, attack_family="family-a",
            device_family="attack", source_family="attack", c1_score=1.0, episode_id="attack-source",
        )
        for index in range(4)
    ]
    benign = [
        ckbj.Record(
            uid=f"benign:{index}", role="aux_select", m1_phase="select", source="benign-source",
            recorded_index=index, event_position=index, label=0, attack_family="benign",
            device_family="benign", source_family="benign", c1_score=1.0, episode_id="benign-source",
        )
        for index in range(8)
    ]
    gate_scores = {**{row.uid: 1.0 for row in support}, **{row.uid: 0.1 for row in benign}}
    threshold, frontier, passed = ckbm.choose_verifier_gate(PRIMARY, support, benign, gate_scores, 0.5)
    assert passed and math.isclose(threshold, 1.0)
    assert len([row for row in frontier if row.get("selected")]) == 1

    with tempfile.TemporaryDirectory(prefix="ckbp_clean_out_") as root:
        path = Path(root)
        (path / "slurm_identity.txt").write_text("job=1\n", encoding="utf-8")
        assert_clean_formal_out(path)
        (path / "unexpected.txt").write_text("reject\n", encoding="utf-8")
        try:
            assert_clean_formal_out(path)
        except RuntimeError:
            pass
        else:
            raise AssertionError("formal output guard accepted an unexpected file")

    print(
        json.dumps(
            {
                "status": "CKBP_CONTRACT_UNIT_PASS",
                "primary": PRIMARY,
                "bounded_normal_tail_attack_score_mean": float(normal_tail.mean()),
                "bounded_far_attack_tail_attack_score_mean": float(attack_tail.mean()),
                "unbounded_far_attack_tail_attack_score_mean": float(
                    np.mean([unsafe_scores[row.uid] for row in attack_rows[16:]])
                ),
                "score_before_update": True,
                "source_reset": True,
                "future_invariance_prefix": True,
                "normal_model_finite": True,
                "source_oof_folds": len(synthetic_folds),
            },
            indent=2,
        )
    )


def scope_audit(args: argparse.Namespace) -> None:
    # Reuse the already-correct CKBO real-data membership audit.  CKBP narrows
    # model use further to benign-only normal calibration and cannot enlarge
    # the frozen target cohort.
    ckbo.scope_audit(args)


def dry_run(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            {
                "issue": ISSUE,
                "seed": SEED,
                "primary": PRIMARY,
                "candidates": [spec.__dict__ for spec in CANDIDATES],
                "normal_model": "QuantileTransformer + LedoitWolf; legal benign fit only",
                "calibration": "source-disjoint benign-select split conformal; bounded source-local past-only shift",
                "burn_in": BURN_IN,
                "history_window": HISTORY_WINDOW,
                "update_guard_mad": UPDATE_GUARD_MAD,
                "permanent_report_only": list(ckbo.PERMANENT_REPORT_ONLY),
                "sealed_unopened": ["iotsim-cooler-motor"],
                "review_rate": 0.0,
                "formal_job": "result-producing attack preservation plus legal multi-held and frozen report canaries",
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["contract-unit", "scope-audit", "dry-run", "formal"], default="dry-run")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--gotham-zip", type=Path, default=ckbo.DEFAULT_ZIP)
    parser.add_argument("--t0-root", type=Path, default=ckbo.DEFAULT_T0)
    parser.add_argument("--report-t0-extension", type=Path, default=ckbo.DEFAULT_REPORT_EXTENSION)
    parser.add_argument("--c1-plan", type=Path, default=ckbo.DEFAULT_C1_PLAN)
    parser.add_argument("--c1-targets", type=Path, default=ckbo.DEFAULT_C1_TARGETS)
    parser.add_argument("--c1-cache", type=Path, default=ckbo.DEFAULT_C1_CACHE)
    parser.add_argument("--c1-report-extension", type=Path, default=ckbo.DEFAULT_C1_REPORT_EXTENSION)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--aux-rows-per-source", type=int, default=ckbo.MODEL_READY_PER_SOURCE)
    # Compatibility with ckbo.scope_audit and materialize_auxiliary.
    parser.add_argument("--epochs", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=0)
    parser.add_argument("--tabm-k", type=int, default=0)
    parser.add_argument("--tabm-width", type=int, default=0)
    parser.add_argument("--tabm-blocks", type=int, default=0)
    parser.add_argument("--extra-trees", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "contract-unit":
        contract_unit(args)
    elif args.mode == "scope-audit":
        scope_audit(args)
    elif args.mode == "formal":
        run_formal(args)
    else:
        dry_run(args)


if __name__ == "__main__":
    main()
