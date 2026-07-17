"""CKBQ: attack-shielded causal MiniRocket normality consensus.

CKBQ keeps the frozen C1 attack anchor and CKBP's global raw-AfterImage115
normal conformal score.  It adds one mature temporal classifier: the
MiniRocketMultivariate transform over a fixed, causal window from CKBE/CKBI's
complete label-free nine-dimensional event stream, followed by a source- and
family-balanced RidgeClassifier.  All 385 legal support_train rows supervise
the temporal head exactly once.

The registered primary is asymmetric.  A high-confidence C1 shield is always
hard.  A remaining C1 candidate is suppressed only when both the static
normal score and the temporal process score support normality.  Disagreement,
insufficient history, or invalid temporal evidence fails closed to C1 hard.
There is no score addition and review is fixed to zero.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import platform
import sys
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import dpkt
import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.linear_model import RidgeClassifier
from sklearn.preprocessing import StandardScaler


OOD = Path(__file__).resolve().parent
VENDOR = OOD / "vendor" / "sktime_minirocket_v0_24_1"
for path in (OOD, VENDOR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import issue27ckbe_tgn_fullsupport_event_cache_v1 as ckbe  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbm_tabm_causal_source_calibration_v1 as ckbm  # noqa: E402
import issue27ckbo_mature_afterimage_transfer_v1 as ckbo  # noqa: E402
import issue27ckbp_source_local_normal_calibration_v1 as ckbp  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402
from minirocket_torch import MiniRocketMultivariateTorch  # noqa: E402


ISSUE = "issue27ckbq_causal_minirocket_consensus_v1_2026-07-17"
ROOT = ckbo.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
SEED = 27
PRIMARY = "M3-StaticTemporalConsensus"
STATIC_CONTROL = "A0-GlobalNormalConformal"
SHIELDED_STATIC = "M1-ShieldedStatic"
SHIELDED_TEMPORAL = "M2-ShieldedTemporal"
WINDOW_LENGTH = 32
MIN_RELIABLE_HISTORY = 9
MINIROCKET_FEATURES = 3360
MINIROCKET_MAX_DILATIONS = 16
RIDGE_ALPHA = 1.0
GRID_EVIDENCE_QUANTILES = 33
GRID_SHIELD_QUANTILES = 17
FIT_ROWS_PER_SOURCE = 600
EXPECTED_AUX_MANIFEST_SHA256 = "d45bb5c0359555b45d19b4b5d2c62ad83ae9dfb177654a3f36c4393fd3120c4f"


@dataclass
class AuxiliaryTemporalData:
    messages: dict[str, np.ndarray]
    offsets: dict[str, int]
    manifest: pd.DataFrame
    manifest_sha256: str


@dataclass
class TemporalModel:
    rocket: MiniRocketMultivariateTorch
    scaler: StandardScaler
    ridge: RidgeClassifier
    model_sha256: str
    audit: dict[str, Any]
    training_trace: list[dict[str, Any]]


@dataclass(frozen=True)
class Gate:
    candidate: str
    c1_shield_threshold: float
    static_threshold: float
    temporal_threshold: float
    selected_benign_hard_rate: float
    support_recall: float
    gate_constraint_pass: bool


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
    for array in arrays:
        value = np.ascontiguousarray(array)
        digest.update(str(value.dtype).encode("ascii"))
        digest.update(np.asarray(value.shape, dtype=np.int64).tobytes())
        digest.update(value.tobytes())
    return digest.hexdigest()


def portable_message(ts: float, buf: bytes) -> tuple[np.ndarray | None, str | None]:
    """Return the exact CKBE portable message without identities or labels."""
    fields, error = ckbo.ckab.parse_packet(ts, buf)
    if error is not None:
        return None, error
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        payload: Any = eth.data
        if isinstance(payload, (dpkt.ip.IP, dpkt.ip6.IP6)):
            payload = payload.data
        is_tcp = isinstance(payload, dpkt.tcp.TCP)
        is_udp = isinstance(payload, dpkt.udp.UDP)
        is_icmp = isinstance(payload, dpkt.icmp.ICMP) or (
            hasattr(dpkt, "icmp6") and isinstance(payload, dpkt.icmp6.ICMP6)
        )
        destination_port = int(payload.dport) if is_tcp or is_udp else 0
        flags = int(payload.flags) if is_tcp else 0
        message = np.asarray(
            [
                math.log1p(max(0, int(fields["datagram_size"]))),
                float(is_tcp),
                float(is_udp),
                float(is_icmp),
                ckbe.port_bucket(destination_port),
                float(bool(flags & 0x02)),
                float(bool(flags & 0x10)),
                float(bool(flags & 0x04)),
                float(bool(flags & 0x01)),
            ],
            dtype=np.float32,
        )
        return message, None
    except Exception as exc:  # pragma: no cover - corrupt-packet diagnostic
        return None, str(exc)


def materialize_auxiliary_temporal(
    args: argparse.Namespace,
    out: Path,
    aux: ckbo.AuxiliaryData,
) -> AuxiliaryTemporalData:
    cache_dir = out / "aux_temporal_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    messages: dict[str, np.ndarray] = {}
    offsets: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    required_events = ckbo.WARMUP_PACKETS + int(args.aux_rows_per_source)
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        for item in aux.manifest.sort_values("source_group", kind="mergesort").itertuples(index=False):
            source = str(item.source_group)
            member = str(item.raw_source_path)
            key = hashlib.sha256(member.encode("utf-8")).hexdigest()[:20]
            path = cache_dir / f"{key}.npz"
            parse_errors = 0
            packets_scanned = 0
            if path.is_file():
                with np.load(path, allow_pickle=False) as loaded:
                    stored_member = str(loaded["pcap_member"].item())
                    array = np.asarray(loaded["raw_msg"], dtype=np.float32)
                    offset = int(loaded["target_offset"].item())
                if stored_member != member or array.shape != (required_events, 9):
                    raise RuntimeError(f"stale auxiliary temporal cache: {source}: {array.shape}")
            else:
                collected: list[np.ndarray] = []
                with archive.open(member, "r") as raw:
                    reader = dpkt.pcap.Reader(io.BufferedReader(raw))
                    for ts, buf in reader:
                        packets_scanned += 1
                        message, error = portable_message(float(ts), buf)
                        if error is not None or message is None:
                            parse_errors += 1
                            continue
                        collected.append(message)
                        if len(collected) >= required_events:
                            break
                array = np.vstack(collected).astype(np.float32) if collected else np.empty((0, 9), dtype=np.float32)
                offset = ckbo.WARMUP_PACKETS
                if array.shape != (required_events, 9) or not np.isfinite(array).all():
                    raise RuntimeError(f"short auxiliary temporal source: {source}: {array.shape}")
                np.savez(
                    path,
                    raw_msg=array,
                    pcap_member=np.asarray(member),
                    target_offset=np.asarray(offset, dtype=np.int64),
                )
            messages[source] = array
            offsets[source] = offset
            rows.append(
                {
                    "source_group": source,
                    "device_family": str(item.device_family),
                    "role": str(item.role),
                    "raw_source_path": member,
                    "events": len(array),
                    "target_offset": offset,
                    "target_rows": int(args.aux_rows_per_source),
                    "packets_scanned_on_build": packets_scanned,
                    "parse_errors_on_build": parse_errors,
                    "raw_label_column_read": False,
                    "source_identity_as_feature": False,
                    "current_event_inclusive": True,
                    "future_event_used": False,
                    "event_schema": "CKBE portable raw_msg9",
                    "raw_msg_sha256": sha256_arrays(array),
                    "target_event_positions_sha256": sha256_arrays(
                        np.arange(offset, offset + int(args.aux_rows_per_source), dtype=np.int64)
                    ),
                    "cache_file": path.name,
                    "cache_sha256": ckbo.sha256_file(path),
                }
            )
    manifest_path = out / "ckbq_aux_temporal_manifest.csv"
    write_csv_lf(manifest_path, rows)
    manifest_sha = ckbo.sha256_file(manifest_path)
    return AuxiliaryTemporalData(messages, offsets, pd.DataFrame(rows), manifest_sha)


class TemporalWindowStore:
    def __init__(self, t0: Any, aux: AuxiliaryTemporalData):
        self.t0 = t0
        self.aux = aux
        self._messages: dict[str, np.ndarray] = {}

    def source_messages(self, source: str) -> tuple[np.ndarray, int, bool]:
        if source in self.aux.messages:
            return self.aux.messages[source], self.aux.offsets[source], True
        if source not in self._messages:
            npz, _meta = self.t0.paths(source)
            if not npz.is_file():
                raise FileNotFoundError(f"missing T0 temporal source: {source}")
            with np.load(npz, allow_pickle=False) as loaded:
                message = np.asarray(loaded["raw_msg"], dtype=np.float32)
            if message.ndim != 2 or message.shape[1] != 9 or not np.isfinite(message).all():
                raise RuntimeError(f"invalid T0 raw_msg for {source}: {message.shape}")
            self._messages[source] = message
        return self._messages[source], 0, False

    def windows(
        self,
        records: list[ckbj.Record],
        phase: str,
    ) -> tuple[np.ndarray, dict[str, int], list[dict[str, Any]]]:
        if not records:
            return np.empty((0, 9, WINDOW_LENGTH), dtype=np.float32), {}, []
        output = np.empty((len(records), 9, WINDOW_LENGTH), dtype=np.float32)
        lengths: dict[str, int] = {}
        rows: list[dict[str, Any]] = []
        by_source: defaultdict[str, list[tuple[int, ckbj.Record]]] = defaultdict(list)
        for index, record in enumerate(records):
            by_source[record.source].append((index, record))
        for source in sorted(by_source):
            message, offset, is_aux = self.source_messages(source)
            cold = 0
            positions: list[int] = []
            for output_index, record in by_source[source]:
                position = int(record.event_position) + int(offset)
                if position < 0 or position >= len(message):
                    raise RuntimeError(
                        f"temporal target outside source: {source}: {position}/{len(message)}"
                    )
                start = max(0, position - WINDOW_LENGTH + 1)
                segment = message[start : position + 1]
                valid = len(segment)
                if valid < WINDOW_LENGTH:
                    pad = np.repeat(segment[0:1], WINDOW_LENGTH - valid, axis=0)
                    segment = np.vstack([pad, segment])
                output[output_index] = segment.T
                lengths[record.uid] = valid
                positions.append(position)
                cold += int(valid < MIN_RELIABLE_HISTORY)
            rows.append(
                {
                    "phase": phase,
                    "source_group": source,
                    "records": len(by_source[source]),
                    "events_available": len(message),
                    "first_target_position": min(positions),
                    "last_target_position": max(positions),
                    "cold_records": cold,
                    "reliable_records": len(by_source[source]) - cold,
                    "window_length": WINDOW_LENGTH,
                    "current_event_inclusive": True,
                    "future_events_used": False,
                    "source_fresh_boundary": True,
                    "auxiliary_temporal_source": is_aux,
                    "raw_label_column_read": False,
                }
            )
        if not np.isfinite(output).all():
            raise RuntimeError("nonfinite causal temporal windows")
        return output, lengths, rows


def causal_phase_order_audit(records: list[ckbj.Record]) -> list[dict[str, Any]]:
    """Reject target-role inversions that could expose report rows to fit.

    Raw event windows are causal prefixes.  This audit proves that, among all
    frozen scored targets visible in a protocol, fit targets precede select
    targets and select targets precede report targets within each source.
    """
    phase_rank = {"fit": 0, "select": 1, "report": 2}
    by_source: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in records:
        if record.m1_phase not in phase_rank:
            raise RuntimeError(f"unknown M1 phase in causal audit: {record.m1_phase}")
        by_source[record.source].append(record)
    rows: list[dict[str, Any]] = []
    total_violations = 0
    for source in sorted(by_source):
        ordered = sorted(
            by_source[source],
            key=lambda record: (int(record.event_position), phase_rank[record.m1_phase], record.uid),
        )
        seen_rank = -1
        violations = 0
        duplicate_cross_phase = 0
        positions: defaultdict[int, set[str]] = defaultdict(set)
        for record in ordered:
            rank = phase_rank[record.m1_phase]
            violations += int(rank < seen_rank)
            seen_rank = max(seen_rank, rank)
            positions[int(record.event_position)].add(record.m1_phase)
        duplicate_cross_phase = sum(len(phases) > 1 for phases in positions.values())
        violations += duplicate_cross_phase
        total_violations += violations
        phase_positions = {
            phase: [int(record.event_position) for record in ordered if record.m1_phase == phase]
            for phase in phase_rank
        }
        rows.append(
            {
                "source_group": source,
                "records": len(ordered),
                "fit_targets": len(phase_positions["fit"]),
                "select_targets": len(phase_positions["select"]),
                "report_targets": len(phase_positions["report"]),
                "fit_max_event_position": max(phase_positions["fit"], default=math.nan),
                "select_min_event_position": min(phase_positions["select"], default=math.nan),
                "select_max_event_position": max(phase_positions["select"], default=math.nan),
                "report_min_event_position": min(phase_positions["report"], default=math.nan),
                "phase_order_violations": violations,
                "duplicate_position_cross_phase": duplicate_cross_phase,
                "fit_prefix_contains_select_or_report_target": violations > 0,
                "select_prefix_contains_report_target": violations > 0,
                "pass": violations == 0,
            }
        )
    if total_violations:
        offenders = [row["source_group"] for row in rows if not row["pass"]]
        raise RuntimeError(f"causal phase-order contract failed: {offenders[:5]}")
    return rows


def balanced_weights(records: list[ckbj.Record]) -> np.ndarray:
    if not records:
        return np.empty(0, dtype=np.float64)
    normal = [record for record in records if record.label == 0]
    attack = [record for record in records if record.label == 1]
    if not normal or not attack:
        raise RuntimeError("temporal classifier needs both legal normal and attack fit rows")
    source_counts = Counter(record.source for record in normal)
    family_counts = Counter(record.attack_family for record in attack)
    weights = []
    for record in records:
        if record.label == 0:
            weight = 0.5 / (len(source_counts) * source_counts[record.source])
        else:
            weight = 0.5 / (len(family_counts) * family_counts[record.attack_family])
        weights.append(weight)
    value = np.asarray(weights, dtype=np.float64)
    value *= len(value) / value.sum()
    return value


def fit_temporal_model(
    fit_normal: list[ckbj.Record],
    fit_attack: list[ckbj.Record],
    store: TemporalWindowStore,
    seed: int,
    batch_size: int,
) -> tuple[TemporalModel, list[dict[str, Any]]]:
    started = time.time()
    normal_records = ckbp.balanced_normal_records(fit_normal, FIT_ROWS_PER_SOURCE)
    train_records = normal_records + list(fit_attack)
    train_windows, _lengths, window_rows = store.windows(train_records, "fit")
    normal_windows = train_windows[: len(normal_records)]
    rocket = MiniRocketMultivariateTorch(
        num_features=MINIROCKET_FEATURES,
        max_dilations_per_kernel=MINIROCKET_MAX_DILATIONS,
        seed=seed,
        batch_size=batch_size,
    )
    fit_started = time.time()
    rocket.fit(normal_windows)
    fit_seconds = time.time() - fit_started
    transform_started = time.time()
    transformed = rocket.transform(train_windows)
    transform_seconds = time.time() - transform_started
    weights = balanced_weights(train_records)
    scaler = StandardScaler().fit(transformed, sample_weight=weights)
    standardized = scaler.transform(transformed).astype(np.float32)
    labels = np.asarray([record.label for record in train_records], dtype=np.int64)
    ridge = RidgeClassifier(alpha=RIDGE_ALPHA, fit_intercept=True)
    ridge.fit(standardized, labels, sample_weight=weights)
    decision = np.asarray(ridge.decision_function(standardized), dtype=np.float64)
    signed = np.where(labels == 1, 1.0, -1.0)
    residual = signed - decision
    weighted_mse = float(np.average(np.square(residual), weights=weights))
    penalty = float(RIDGE_ALPHA * np.square(np.asarray(ridge.coef_, dtype=np.float64)).sum() / len(labels))
    model_sha = sha256_arrays(
        np.asarray(rocket.parameters.dilations),
        np.asarray(rocket.parameters.features_per_dilation),
        np.asarray(rocket.parameters.channel_mask),
        *[np.asarray(value) for value in rocket.parameters.biases],
        np.asarray(scaler.mean_),
        np.asarray(scaler.scale_),
        np.asarray(ridge.coef_),
        np.asarray(ridge.intercept_),
    )
    family_counts = Counter(record.attack_family for record in fit_attack)
    source_counts = Counter(record.source for record in normal_records)
    audit = {
        "model": "MiniRocketMultivariate_v0.24.1_algorithm_port_plus_RidgeClassifier",
        "upstream": "sktime/sktime v0.24.1 BSD-3-Clause",
        "fit_rows": len(train_records),
        "fit_normal_rows": len(normal_records),
        "fit_attack_rows": len(fit_attack),
        "fit_report_rows": 0,
        "fit_normal_sources": len(source_counts),
        "fit_attack_families": len(family_counts),
        "all_support_train_used": len(fit_attack) > 0,
        "family_balanced_attack_weights": True,
        "source_balanced_normal_weights": True,
        "window_length": WINDOW_LENGTH,
        "input_channels": 9,
        "requested_features": MINIROCKET_FEATURES,
        "actual_features": int(rocket.parameters.actual_features),
        "parameter_sha256": rocket.parameters.parameter_sha256,
        "model_sha256": model_sha,
        "ridge_alpha": RIDGE_ALPHA,
        "weighted_training_mse": weighted_mse,
        "ridge_penalty_per_row": penalty,
        "nan_count": int(np.isnan(standardized).sum()),
        "report_gradient_updates": 0,
        "report_threshold_updates": 0,
        "select_report_transform_batch_crossing": 0,
        "wall_seconds": time.time() - started,
    }
    trace = [
        {
            "stage": "fit_minirocket_biases_normal_only",
            "rows": len(normal_records),
            "seconds": fit_seconds,
            "loss": math.nan,
            "closed_form": False,
        },
        {
            "stage": "transform_fit_windows",
            "rows": len(train_records),
            "seconds": transform_seconds,
            "loss": math.nan,
            "closed_form": False,
        },
        {
            "stage": "fit_weighted_ridge",
            "rows": len(train_records),
            "seconds": time.time() - started - fit_seconds - transform_seconds,
            "loss": weighted_mse + penalty,
            "closed_form": True,
        },
    ]
    return TemporalModel(rocket, scaler, ridge, model_sha, audit, trace), window_rows


def temporal_scores(
    model: TemporalModel,
    records: list[ckbj.Record],
    store: TemporalWindowStore,
    phase: str,
) -> tuple[dict[str, float], dict[str, bool], dict[str, int], list[dict[str, Any]]]:
    windows, lengths, rows = store.windows(records, phase)
    if not records:
        return {}, {}, lengths, rows
    transformed = model.rocket.transform(windows)
    standardized = model.scaler.transform(transformed).astype(np.float32)
    scores = np.asarray(model.ridge.decision_function(standardized), dtype=np.float64)
    if not np.isfinite(scores).all():
        raise RuntimeError("nonfinite temporal decision scores")
    mapping = {record.uid: float(score) for record, score in zip(records, scores)}
    reliable = {record.uid: lengths[record.uid] >= MIN_RELIABLE_HISTORY for record in records}
    return mapping, reliable, lengths, rows


def threshold_grid(values: np.ndarray, quantiles: int) -> np.ndarray:
    finite = np.asarray(values, dtype=np.float64)
    finite = finite[np.isfinite(finite)]
    if len(finite) == 0:
        raise RuntimeError("empty threshold grid")
    grid = np.quantile(finite, np.linspace(0.0, 1.0, int(quantiles)))
    epsilon = max(1e-12, float(np.ptp(finite)) * 1e-9)
    return np.unique(np.concatenate(([finite.min() - epsilon], grid, [finite.max() + epsilon])))


def decision_array(
    candidate: str,
    records: list[ckbj.Record],
    static_scores: dict[str, float],
    temporal: dict[str, float],
    reliable: dict[str, bool],
    c1_candidate_threshold: float,
    gate: Gate,
) -> np.ndarray:
    c1 = np.asarray([record.c1_score for record in records], dtype=np.float64)
    candidate_mask = c1 >= float(c1_candidate_threshold)
    if candidate == "M0-C1":
        return candidate_mask
    static = np.asarray([static_scores[record.uid] for record in records], dtype=np.float64)
    if candidate == STATIC_CONTROL:
        return candidate_mask & (static >= gate.static_threshold)
    shield = c1 >= gate.c1_shield_threshold
    if candidate == SHIELDED_STATIC:
        return shield | (candidate_mask & (static >= gate.static_threshold))
    temporal_score = np.asarray([temporal[record.uid] for record in records], dtype=np.float64)
    temporal_ok = np.asarray([reliable[record.uid] for record in records], dtype=bool)
    if candidate == SHIELDED_TEMPORAL:
        return shield | (candidate_mask & (~temporal_ok | (temporal_score >= gate.temporal_threshold)))
    if candidate == PRIMARY:
        return shield | (
            candidate_mask
            & (
                ~temporal_ok
                | (static >= gate.static_threshold)
                | (temporal_score >= gate.temporal_threshold)
            )
        )
    raise RuntimeError(f"unknown CKBQ candidate: {candidate}")


def gate_passes(
    records: list[ckbj.Record],
    hard: np.ndarray,
    c1_hard: np.ndarray,
) -> tuple[bool, float, int, int]:
    if len(records) != len(hard) or len(hard) != len(c1_hard):
        raise RuntimeError("gate support shape mismatch")
    baseline_hits = int(c1_hard.sum())
    hits = int(hard.sum())
    overall_pass = hits >= baseline_hits
    family_pass = True
    for family in sorted({record.attack_family for record in records}):
        mask = np.asarray([record.attack_family == family for record in records], dtype=bool)
        baseline = int(c1_hard[mask].sum())
        current = int(hard[mask].sum())
        allowed_misses = int(math.floor(0.02 * int(mask.sum()) + 1e-12))
        family_pass &= current >= baseline - allowed_misses
    recall = float(hits / len(records)) if records else math.nan
    return bool(overall_pass and family_pass), recall, hits, baseline_hits


def choose_gate(
    candidate: str,
    support: list[ckbj.Record],
    benign: list[ckbj.Record],
    static_scores: dict[str, float],
    temporal: dict[str, float],
    reliable: dict[str, bool],
    c1_threshold: float,
) -> tuple[Gate, list[dict[str, Any]]]:
    all_records = support + benign
    c1_values = np.asarray([record.c1_score for record in all_records], dtype=np.float64)
    static_values = np.asarray([static_scores[record.uid] for record in all_records], dtype=np.float64)
    temporal_values = np.asarray([temporal[record.uid] for record in all_records], dtype=np.float64)
    shield_grid = threshold_grid(c1_values[c1_values >= c1_threshold], GRID_SHIELD_QUANTILES)
    shield_grid = np.unique(np.concatenate(([float(c1_threshold)], shield_grid[shield_grid >= c1_threshold])))
    static_grid = threshold_grid(static_values, GRID_EVIDENCE_QUANTILES)
    temporal_grid = threshold_grid(temporal_values, GRID_EVIDENCE_QUANTILES)
    if candidate == SHIELDED_STATIC:
        temporal_grid = np.asarray([math.nan])
    elif candidate == SHIELDED_TEMPORAL:
        static_grid = np.asarray([math.nan])
    support_c1 = np.asarray([record.c1_score >= c1_threshold for record in support], dtype=bool)
    rows: list[dict[str, Any]] = []
    feasible: list[tuple[tuple[float, ...], Gate, dict[str, Any]]] = []
    evaluated = 0
    for shield in shield_grid.tolist():
        for static_threshold in static_grid.tolist():
            for temporal_threshold in temporal_grid.tolist():
                evaluated += 1
                gate = Gate(
                    candidate=candidate,
                    c1_shield_threshold=float(shield),
                    static_threshold=float(static_threshold),
                    temporal_threshold=float(temporal_threshold),
                    selected_benign_hard_rate=math.nan,
                    support_recall=math.nan,
                    gate_constraint_pass=False,
                )
                support_hard = decision_array(
                    candidate, support, static_scores, temporal, reliable, c1_threshold, gate
                )
                passed, recall, hits, baseline_hits = gate_passes(support, support_hard, support_c1)
                if not passed:
                    continue
                benign_hard = decision_array(
                    candidate, benign, static_scores, temporal, reliable, c1_threshold, gate
                )
                benign_rate = float(benign_hard.mean()) if benign else math.nan
                selected_gate = Gate(
                    candidate=candidate,
                    c1_shield_threshold=float(shield),
                    static_threshold=float(static_threshold),
                    temporal_threshold=float(temporal_threshold),
                    selected_benign_hard_rate=benign_rate,
                    support_recall=recall,
                    gate_constraint_pass=True,
                )
                # Conservative deterministic tie break: protect more C1 rows
                # first, then use lower evidence thresholds (more rows remain
                # hard) when scientific objectives are otherwise identical.
                key = (
                    benign_rate,
                    float(shield),
                    float(static_threshold) if math.isfinite(float(static_threshold)) else 0.0,
                    float(temporal_threshold) if math.isfinite(float(temporal_threshold)) else 0.0,
                )
                row = {
                    "candidate": candidate,
                    "c1_shield_threshold": shield,
                    "static_threshold": static_threshold,
                    "temporal_threshold": temporal_threshold,
                    "support_hard": hits,
                    "support_c1_hard": baseline_hits,
                    "support_recall": recall,
                    "benign_select_hard_rate": benign_rate,
                    "gate_constraint_pass": True,
                }
                feasible.append((key, selected_gate, row))
    if not feasible:
        raise RuntimeError(f"no attack-preserving gate found for {candidate}")
    feasible.sort(key=lambda item: item[0])
    selected = feasible[0][1]
    for rank, (_key, gate, row) in enumerate(feasible[:50], start=1):
        rows.append(
            {
                **row,
                "rank": rank,
                "selected": rank == 1,
                "grid_evaluated": evaluated,
                "grid_feasible": len(feasible),
                "report_rows_used": 0,
            }
        )
    return selected, rows


def prepare_inputs(args: argparse.Namespace, out: Path) -> tuple[Any, ...]:
    x_by_role, frames, input_audit, _labels = ckbo.cko.load_role_inputs(False)
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
    live.to_csv(out / "ckbq_live_report_extension_exclusion.csv", index=False)
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
    pd.DataFrame(coverage).to_csv(out / "ckbq_required_report_source_coverage.csv", index=False)
    if any(not bool(row["full_source_coverage"]) for row in coverage):
        raise RuntimeError("formal target coverage incomplete")
    pd.DataFrame(ckbj.support_val_lineage(frames)).to_csv(
        out / "ckbq_support_val_lineage.csv", index=False
    )
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
    window_store: TemporalWindowStore,
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
                "held_family_rows_retained": int(
                    sum(held is not None and record.device_family == held for record in after)
                ),
            }
        )

    fit_normal = sets["fit_benign"] + aux_fit
    select_normal = sets["select_benign"] + aux_select
    fit_attack = list(sets["fit_attack"])
    select_records = ckbm.unique_records([sets["select_attack"], select_normal])
    report_records = ckbm.unique_records([sets["report"]])
    scored_records = ckbm.unique_records([select_records, report_records])
    phase_order_rows = causal_phase_order_audit(fit_normal + fit_attack + scored_records)
    feature_records = ckbm.unique_records([fit_normal, scored_records])
    raw115 = ckbo.existing_feature_map(
        feature_records, x_by_role, "raw115", ckbo.afterimage_schema()[0]
    )
    add_aux = [record for record in feature_records if record.role.startswith("aux_")]
    ckbo.add_auxiliary_values(raw115, aux, "raw115", add_aux)
    if len(raw115) != len(feature_records):
        raise RuntimeError("raw AfterImage feature coverage incomplete")

    static_model = ckbp.fit_normal_model(fit_normal, raw115, int(args.seed))
    _oof_scores, fold_rows = ckbp.source_out_of_fold_scores(fit_normal, raw115, int(args.seed))
    select_reference_values = ckbp.normal_nonconformity(static_model, select_normal, raw115)
    select_reference_scores = {
        record.uid: float(value)
        for record, value in zip(select_normal, select_reference_values)
    }
    reference = ckbp.build_calibration_reference(select_normal, select_reference_scores)
    final_values = ckbp.normal_nonconformity(static_model, scored_records, raw115)
    base_nonconformity = {
        record.uid: float(value) for record, value in zip(scored_records, final_values)
    }
    static_scores = {
        record.uid: 1.0
        - ckbp.empirical_normal_p(reference.raw_reference, base_nonconformity[record.uid])
        for record in scored_records
    }

    temporal_model, fit_window_rows = fit_temporal_model(
        fit_normal,
        fit_attack,
        window_store,
        int(args.seed),
        int(args.rocket_batch_size),
    )
    select_temporal, select_reliable, select_lengths, select_window_rows = temporal_scores(
        temporal_model, select_records, window_store, "select"
    )
    report_temporal, report_reliable, report_lengths, report_window_rows = temporal_scores(
        temporal_model, report_records, window_store, "report"
    )
    temporal = {**select_temporal, **report_temporal}
    reliable = {**select_reliable, **report_reliable}
    history_lengths = {**select_lengths, **report_lengths}
    score_window_rows = select_window_rows + report_window_rows
    if len(temporal) != len(scored_records) or len(reliable) != len(scored_records):
        raise RuntimeError("select/report temporal score coverage or isolation failed")

    selection_rows: list[dict[str, Any]] = []
    gates: dict[str, Gate] = {}
    static_threshold, static_frontier, static_pass = ckbm.choose_verifier_gate(
        STATIC_CONTROL,
        sets["select_attack"],
        select_normal,
        static_scores,
        c1_threshold,
    )
    gates[STATIC_CONTROL] = Gate(
        STATIC_CONTROL,
        math.inf,
        float(static_threshold),
        math.nan,
        math.nan,
        math.nan,
        bool(static_pass),
    )
    for row in static_frontier:
        selection_rows.append(
            {
                **row,
                "candidate": STATIC_CONTROL,
                "c1_shield_threshold": math.inf,
                "static_threshold": row.get("verifier_threshold", static_threshold),
                "temporal_threshold": math.nan,
                "held_value": protocol,
                "selected": bool(row.get("selected", False)),
                "report_rows_used": 0,
            }
        )
    for candidate in (SHIELDED_STATIC, SHIELDED_TEMPORAL, PRIMARY):
        gate, frontier = choose_gate(
            candidate,
            sets["select_attack"],
            select_normal,
            static_scores,
            temporal,
            reliable,
            c1_threshold,
        )
        gates[candidate] = gate
        selection_rows.extend({**row, "held_value": protocol} for row in frontier)

    strict_records = (
        sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
        if held is None
        else sets["report"]
    )
    c1_hard = np.asarray(
        [record.c1_score >= c1_threshold for record in strict_records], dtype=bool
    )
    candidates = ["M0-C1", STATIC_CONTROL, SHIELDED_STATIC, SHIELDED_TEMPORAL, PRIMARY]
    decisions: dict[str, np.ndarray] = {"M0-C1": c1_hard}
    for candidate in candidates[1:]:
        decisions[candidate] = decision_array(
            candidate,
            strict_records,
            static_scores,
            temporal,
            reliable,
            c1_threshold,
            gates[candidate],
        )

    metrics: list[dict[str, Any]] = []
    family_metrics: list[dict[str, Any]] = []
    attack_summary: list[dict[str, Any]] = []
    strict_summary: list[dict[str, Any]] = []
    for candidate in candidates:
        hard = decisions[candidate]
        metric, family = ckbj.metric_rows(
            candidate,
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
                    candidate,
                    strict_records,
                    hard,
                    c1_hard,
                    int(args.bootstrap_reps),
                    int(args.seed),
                )
            )
        else:
            strict_summary.extend(
                ckbj.strict_level2_summary(
                    candidate,
                    protocol,
                    strict_records,
                    hard,
                    c1_hard,
                    int(args.bootstrap_reps),
                    int(args.seed),
                )
            )

    prediction_rows: list[dict[str, Any]] = []
    all_decisions: dict[str, np.ndarray] = {}
    for candidate in candidates:
        if candidate == "M0-C1":
            all_decisions[candidate] = np.asarray(
                [record.c1_score >= c1_threshold for record in scored_records], dtype=bool
            )
        else:
            all_decisions[candidate] = decision_array(
                candidate,
                scored_records,
                static_scores,
                temporal,
                reliable,
                c1_threshold,
                gates[candidate],
            )
    c1_candidates = np.asarray(
        [record.c1_score >= c1_threshold for record in scored_records], dtype=bool
    )
    temporal_reliable = np.asarray(
        [reliable[record.uid] for record in scored_records], dtype=bool
    )
    cold_c1_candidates = c1_candidates & ~temporal_reliable
    if np.any(cold_c1_candidates & ~all_decisions[PRIMARY]):
        raise RuntimeError("cold C1 candidate was suppressed by the primary gate")
    for index, record in enumerate(scored_records):
        row = {
            "held_value": protocol,
            "uid": record.uid,
            "role": record.role,
            "phase": record.m1_phase,
            "source_group": record.source,
            "device_family": record.device_family,
            "attack_family": record.attack_family,
            "label_metric_only": record.label,
            "c1_score": record.c1_score,
            "c1_candidate_threshold": c1_threshold,
            "static_attack_score": static_scores[record.uid],
            "temporal_attack_score": temporal[record.uid],
            "temporal_reliable": reliable[record.uid],
            "history_events": history_lengths[record.uid],
            "cold_fail_hard": not reliable[record.uid],
            "review": False,
        }
        for candidate in candidates:
            row[f"hard__{candidate}"] = bool(all_decisions[candidate][index])
        prediction_rows.append(row)

    support_rows: list[dict[str, Any]] = []
    support_family_rows: list[dict[str, Any]] = []
    if held is None:
        for record in fit_attack:
            support_rows.append(
                {
                    "uid": record.uid,
                    "attack_family": record.attack_family,
                    "source": record.source,
                    "candidate": PRIMARY,
                    "usage": "supervised_weighted_ridge_on_causal_minirocket",
                    "fit_count": 1,
                    "used_at_least_once": True,
                    "static_normal_fit_count": 0,
                    "temporal_supervised_fit_count": 1,
                }
            )
        for family in sorted({record.attack_family for record in fit_attack}):
            group = [record for record in fit_attack if record.attack_family == family]
            support_family_rows.append(
                {
                    "attack_family": family,
                    "unique_rows": len(group),
                    "temporal_supervised_fit_visits": len(group),
                    "static_normal_fit_visits": 0,
                }
            )

    model_rows = [
        {
            "held_value": protocol,
            "model": "global_static_normal_conformal",
            "fit_rows": static_model.fit_rows,
            "fit_sources": static_model.fit_sources,
            "fit_attack_rows": 0,
            "fit_report_rows": 0,
            "model_sha256": static_model.model_sha256,
            "report_gradient_updates": 0,
            "report_threshold_updates": 0,
            "select_report_transform_batch_crossing": 0,
        },
        {"held_value": protocol, **temporal_model.audit},
    ]
    for row in fold_rows:
        row["held_value"] = protocol
    for row in reference.source_rows:
        row["held_value"] = protocol
    for row in fit_window_rows + score_window_rows:
        row["held_value"] = protocol
    for row in temporal_model.training_trace:
        row["held_value"] = protocol

    event_scope = ckbj.event_scope_rows(
        sets, set(getattr(t0, "report_only_sources", set()))
    )
    for row in event_scope:
        row.update({"held_value": protocol, "protocol_run": protocol})
    for row in data_audit + c1_audit:
        row["protocol_run"] = protocol
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
    return {
        "c1_audit": c1_audit,
        "data_audit": data_audit,
        "candidate_selection": selection_rows,
        "model_audit": model_rows,
        "source_oof": fold_rows,
        "source_reference": reference.source_rows,
        "window_audit": fit_window_rows + score_window_rows,
        "phase_order_audit": phase_order_rows,
        "training_trace": temporal_model.training_trace,
        "support_usage": support_rows,
        "support_family_usage": support_family_rows,
        "metrics": metrics,
        "family_metrics": family_metrics,
        "attack_summary": attack_summary,
        "strict_summary": strict_summary,
        "event_scope": event_scope,
        "sealed_audit": sealed_audit,
        "predictions": prediction_rows,
    }


def one(table: pd.DataFrame, column: str, **where: Any) -> float | None:
    part = table
    for key, value in where.items():
        if key not in part:
            return None
        part = part.loc[part[key].eq(value)]
    return None if part.empty else float(part.iloc[0][column])


def scientific_decision(
    attack: pd.DataFrame,
    strict: pd.DataFrame,
    selection: pd.DataFrame,
    support: pd.DataFrame,
    data: pd.DataFrame,
    model: pd.DataFrame,
    windows: pd.DataFrame,
    permanent: pd.DataFrame,
    predictions: pd.DataFrame,
    dev_holds: list[str],
) -> dict[str, Any]:
    overall = one(
        attack,
        "delta_vs_c1_pp",
        candidate=PRIMARY,
        metric="overall_attack_hard_recall",
    )
    major = attack.loc[
        attack.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & attack.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")
        & pd.to_numeric(attack.get("rows", 0), errors="coerce").fillna(0).ge(15)
    ]
    required_holds = [
        "iotsim-stream-consumer",
        "iotsim-hydraulic-system",
        *dev_holds,
    ]
    rates: dict[str, float] = {}
    c1_rates: dict[str, float] = {}
    for held in required_holds:
        value = one(strict, "hard_rate", candidate=PRIMARY, held_value=held)
        baseline = one(strict, "hard_rate", candidate="M0-C1", held_value=held)
        if value is not None:
            rates[held] = value
        if baseline is not None:
            c1_rates[held] = baseline
    held_signal = bool(
        len(set(required_holds)) == len(rates) == len(c1_rates)
        and all(rates[value] <= 0.90 and rates[value] <= c1_rates[value] - 0.05 for value in set(required_holds))
    )
    selected = selection.loc[
        selection.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & ckbm.decision_bool_series(selection.get("selected", pd.Series(False, index=selection.index)), False)
    ]
    alignment = pd.to_numeric(
        data.get("target_alignment_incomplete", pd.Series(1, index=data.index)),
        errors="coerce",
    ).fillna(1)
    temporal_models = model.loc[model.get("model", pd.Series(dtype=str)).astype(str).str.contains("MiniRocket")]
    required_prediction_columns = {
        "c1_score",
        "c1_candidate_threshold",
        "temporal_reliable",
        f"hard__{PRIMARY}",
    }
    prediction_contract_missing = bool(
        predictions.empty or not required_prediction_columns.issubset(set(predictions.columns))
    )
    if prediction_contract_missing:
        cold_c1 = pd.DataFrame()
        cold_fail_hard_verified = False
    else:
        c1_candidate = pd.to_numeric(predictions["c1_score"], errors="coerce").ge(
            pd.to_numeric(predictions["c1_candidate_threshold"], errors="coerce")
        )
        reliable = ckbm.decision_bool_series(predictions["temporal_reliable"], False)
        primary_hard = ckbm.decision_bool_series(predictions[f"hard__{PRIMARY}"], False)
        cold_c1 = predictions.loc[c1_candidate & ~reliable]
        cold_fail_hard_verified = bool((~primary_hard[c1_candidate & ~reliable]).sum() == 0)
    checks = {
        "required_metrics_missing": bool(
            overall is None or len(rates) != len(set(required_holds)) or prediction_contract_missing
        ),
        "overall_attack_drop_over_0_5pp": bool(overall is not None and overall < -0.5),
        "major_attack_family_drop_over_2pp": bool(
            not major.empty and (pd.to_numeric(major["delta_vs_c1_pp"], errors="coerce") < -2.0).any()
        ),
        "multiheld_signal_missing": not held_signal,
        "support_usage_incomplete": bool(
            len(support) != 385
            or support.get("uid", pd.Series(dtype=str)).astype(str).nunique() != 385
            or not ckbm.decision_bool_series(
                support.get("used_at_least_once", pd.Series(False, index=support.index)), False
            ).all()
        ),
        "gate_constraint_failed": bool(
            selected.empty
            or not ckbm.decision_bool_series(
                selected.get("gate_constraint_pass", pd.Series(False, index=selected.index)), False
            ).all()
        ),
        "target_alignment_incomplete": bool(data.empty or alignment.gt(0).any()),
        "report_or_held_used_in_fit": bool(
            temporal_models.empty
            or pd.to_numeric(temporal_models.get("fit_report_rows", 1), errors="coerce").fillna(1).gt(0).any()
            or permanent.empty
            or permanent[
                ["fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count"]
            ].to_numpy().sum()
            != 0
        ),
        "cold_start_artifact": not cold_fail_hard_verified,
        "review_not_zero": False,
    }
    return {
        "seed": SEED,
        "candidate": PRIMARY,
        "decision": "GO_SIGNAL" if not any(checks.values()) else "NO_GO",
        "checks": checks,
        "overall_attack_delta_pp": overall,
        "held_hard_rates": rates,
        "held_c1_hard_rates": c1_rates,
        "all_required_held_improve_5pp_and_at_most_90pct": held_signal,
        "cold_c1_candidates": int(len(cold_c1)),
        "cold_fail_hard_verified": cold_fail_hard_verified,
        "review_rate": 0.0,
        "single_seed_scope": "route go/no-go signal only; no finite-sample 0.5pp guarantee",
    }


def assert_clean_formal_out(out: Path) -> None:
    allowed = {
        "resource_usage.txt",
        "slurm_identity.txt",
        "slurm_job_at_start.txt",
        "aux_afterimage_cache",
        "aux_temporal_cache",
        "ckbo_auxiliary_benign_manifest.csv",
        "ckbo_auxiliary_benign_ready.json",
    }
    unexpected = [path.name for path in out.iterdir() if path.name not in allowed]
    if unexpected:
        raise RuntimeError(f"refusing mixed CKBQ formal output directory: {unexpected[:5]}")


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    if int(args.seed) != SEED:
        raise RuntimeError("first CKBQ formal run is preregistered for seed 27 only")
    if int(args.aux_rows_per_source) != ckbo.MODEL_READY_PER_SOURCE:
        raise RuntimeError("formal auxiliary row contract drift")
    np.random.seed(int(args.seed))
    torch.manual_seed(int(args.seed))
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(int(args.threads))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    assert_clean_formal_out(out)
    (
        x_by_role,
        report_frames,
        input_audit,
        t0,
        t0_audit,
        extension_audit,
        c1_extension_audit,
    ) = prepare_inputs(args, out)
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    model_frames, permanent_rows = ckbo.permanently_mask_frames(report_frames)
    model_frames, frozen_scope_rows = ckbo.restrict_model_scope_to_frozen_targets(
        model_frames, Path(args.c1_targets), t0
    )
    dev_holds = ckbo.legal_development_holds(report_frames, requested)
    if set(dev_holds) != {"iotsim-ip-camera-street", ckbo.AUX_HELD_FAMILY}:
        raise RuntimeError(f"formal development held-family boundary drift: {dev_holds}")
    aux = ckbo.materialize_auxiliary(args, out)
    if aux.manifest_sha256 != EXPECTED_AUX_MANIFEST_SHA256:
        raise RuntimeError(f"frozen CKBO auxiliary manifest drift: {aux.manifest_sha256}")
    aux_temporal = materialize_auxiliary_temporal(args, out, aux)
    window_store = TemporalWindowStore(t0, aux_temporal)
    protocols = ckbo.formal_protocol_values(requested, dev_holds)
    position_cache: dict[str, dict[int, int]] = {}
    results = [
        run_protocol(
            value,
            args,
            x_by_role,
            report_frames,
            model_frames,
            t0,
            position_cache,
            aux,
            window_store,
        )
        for value in protocols
    ]

    def table(key: str) -> pd.DataFrame:
        return pd.DataFrame([{**row, "seed": SEED} for result in results for row in result[key]])

    outputs = {
        "ckbq_c1_fit_select_audit.csv": table("c1_audit"),
        "ckbq_role_usage_audit.csv": table("data_audit"),
        "ckbq_candidate_selection.csv": table("candidate_selection"),
        "ckbq_model_audit.csv": table("model_audit"),
        "ckbq_source_oof_audit.csv": table("source_oof"),
        "ckbq_source_reference_audit.csv": table("source_reference"),
        "ckbq_temporal_window_audit.csv": table("window_audit"),
        "ckbq_causal_phase_order_audit.csv": table("phase_order_audit"),
        "ckbq_training_trace.csv": table("training_trace"),
        "ckbq_support_training_usage.csv": table("support_usage"),
        "ckbq_support_family_training_usage.csv": table("support_family_usage"),
        "ckbq_all_metrics.csv": table("metrics"),
        "ckbq_per_attack_family_metrics.csv": table("family_metrics"),
        "attack_preservation_summary.csv": table("attack_summary"),
        "strict_level2_summary.csv": table("strict_summary"),
        "ckbq_event_scope_audit.csv": table("event_scope"),
        "ckbq_sealed_holdout_audit.csv": table("sealed_audit"),
        "ckbq_permanent_report_only_audit.csv": pd.DataFrame(permanent_rows),
        "ckbq_frozen_model_scope_audit.csv": pd.DataFrame(frozen_scope_rows),
        "ckbq_support_val_lineage.csv": pd.DataFrame(ckbj.support_val_lineage(report_frames)),
        "ckbq_negative_sampling_audit.csv": pd.DataFrame(
            [
                {
                    "seed": SEED,
                    "method": "MiniRocket supervised temporal classification",
                    "negative_sampling_used": False,
                    "negative_samples": 0,
                    "ghost_node_negatives": 0,
                    "reason": "not applicable; no link-prediction objective",
                }
            ]
        ),
        "ckbq_review_audit.csv": pd.DataFrame(
            [{"seed": SEED, "review_count": 0, "review_rate": 0.0, "review_enabled": False}]
        ),
    }
    for filename, frame in outputs.items():
        frame.to_csv(out / filename, index=False)
    predictions = table("predictions")
    predictions.to_csv(
        out / "ckbq_record_predictions.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    outcome = scientific_decision(
        outputs["attack_preservation_summary.csv"],
        outputs["strict_level2_summary.csv"],
        outputs["ckbq_candidate_selection.csv"],
        outputs["ckbq_support_training_usage.csv"],
        outputs["ckbq_role_usage_audit.csv"],
        outputs["ckbq_model_audit.csv"],
        outputs["ckbq_temporal_window_audit.csv"],
        outputs["ckbq_permanent_report_only_audit.csv"],
        predictions,
        dev_holds,
    )
    dump_json(out / "ckbq_single_seed_go_no_go.json", outcome)
    base_manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "torch": torch.__version__,
        "torch_deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "seed": SEED,
        "commit_sha": os.environ.get("CKBQ_COMMIT_SHA", ckbm.git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "wall_seconds": time.time() - started,
        "review_rate": 0.0,
        "base_t0_manifest_sha256": ckbo.sha256_file(base_manifest),
        "expected_base_t0_manifest_sha256": ckbj.EXPECTED_T0_MANIFEST_SHA256,
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "auxiliary_manifest_sha256": aux.manifest_sha256,
        "auxiliary_temporal_manifest_sha256": aux_temporal.manifest_sha256,
        "c1_target_manifest_sha256": ckbo.sha256_file(Path(args.c1_targets)),
    }
    dump_json(out / "ckbq_environment.json", environment)
    dump_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "mode": "formal",
            "primary_candidate": PRIMARY,
            "candidates": [
                "M0-C1",
                STATIC_CONTROL,
                SHIELDED_STATIC,
                SHIELDED_TEMPORAL,
                PRIMARY,
            ],
            "protocols": [ckbo.protocol_family_name(value) for value in protocols],
            "legal_development_holds": dev_holds,
            "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
            "sealed_unopened": ["iotsim-cooler-motor"],
            "original_1m_split_modified": False,
            "review_rate": 0.0,
            "score_addition_used": False,
            "fusion_contract": "C1 shield OR static/temporal disagreement stays hard; joint normal consensus alone suppresses",
            "temporal_contract": {
                "frontend": "sktime MiniRocketMultivariate v0.24.1 algorithm port",
                "event_channels": ckbe.RAW_MSG_NAMES,
                "window_length": WINDOW_LENGTH,
                "current_event_inclusive": True,
                "future_events_used": False,
                "cold_policy": "fail closed to C1 hard; never constant suppress",
                "support_supervision": "all legal support_train rows once; family balanced",
                "report": "fixed weights and thresholds; no gradients; label-free window",
            },
            "selection_contract": "support_val attack preservation first; legal benign select false alarm second; report rows zero",
            "statistical_claim_boundary": "69 support_val rows provide an empirical gate only, not a 0.5pp finite-sample guarantee",
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_report_extension_audit": c1_extension_audit,
            "environment": environment,
        },
    )
    write_text_lf(
        out / "codex_readout.md",
        f"# {ISSUE}\n\nSeed 27 result: `{outcome['decision']}` for `{PRIMARY}`. "
        "The primary uses no score addition: C1 shield OR static/temporal disagreement remains hard; "
        "only joint normal consensus suppresses. Review is `0`.\n",
    )
    print(
        json.dumps(
            {"status": "CKBQ_FORMAL_COMPLETE", "decision": outcome["decision"], "out": str(out)},
            indent=2,
        )
    )


def contract_unit(args: argparse.Namespace) -> None:
    rng = np.random.default_rng(SEED)
    x = rng.normal(size=(24, 9, WINDOW_LENGTH)).astype(np.float32)
    x[12:, 0] += 1.5
    first = MiniRocketMultivariateTorch(
        num_features=336,
        max_dilations_per_kernel=4,
        seed=SEED,
        batch_size=8,
    ).fit_transform(x)
    second = MiniRocketMultivariateTorch(
        num_features=336,
        max_dilations_per_kernel=4,
        seed=SEED,
        batch_size=7,
    ).fit_transform(x)
    if first.shape != (24, 336) or not np.allclose(first, second, atol=1e-7):
        raise RuntimeError("MiniRocket deterministic contract failed")
    support = [
        ckbj.Record(
            uid=f"attack:{index}",
            role="support_val",
            m1_phase="select",
            source="attack-source",
            recorded_index=index,
            event_position=index,
            label=1,
            attack_family="attack-a" if index < 4 else "attack-b",
            device_family="attack-device",
            source_family="attack-device",
            c1_score=0.8 + 0.01 * index,
            episode_id="attack-source",
        )
        for index in range(8)
    ]
    benign = [
        ckbj.Record(
            uid=f"benign:{index}",
            role="ood_val",
            m1_phase="select",
            source="benign-source",
            recorded_index=index,
            event_position=index,
            label=0,
            attack_family="benign",
            device_family="benign-device",
            source_family="benign-device",
            c1_score=0.85,
            episode_id="benign-source",
        )
        for index in range(12)
    ]
    records = support + benign
    static = {
        **{record.uid: 0.9 for record in support},
        **{record.uid: 0.1 for record in benign},
    }
    temporal = {
        **{record.uid: 2.0 for record in support},
        **{record.uid: -2.0 for record in benign},
    }
    reliable = {record.uid: True for record in records}
    gate, _rows = choose_gate(
        PRIMARY, support, benign, static, temporal, reliable, 0.5
    )
    support_hard = decision_array(PRIMARY, support, static, temporal, reliable, 0.5, gate)
    benign_hard = decision_array(PRIMARY, benign, static, temporal, reliable, 0.5, gate)
    if not support_hard.all() or benign_hard.any():
        raise RuntimeError("attack-preserving consensus contract failed")
    causal_phase_order_audit(records)
    inverted = [
        ckbj.Record(
            uid="phase:report",
            role="future_query",
            m1_phase="report",
            source="phase-source",
            recorded_index=5,
            event_position=5,
            label=0,
            attack_family="benign",
            device_family="phase-device",
            source_family="phase-device",
            c1_score=0.8,
            episode_id="phase-source",
        ),
        ckbj.Record(
            uid="phase:fit",
            role="benign_train",
            m1_phase="fit",
            source="phase-source",
            recorded_index=10,
            event_position=10,
            label=0,
            attack_family="benign",
            device_family="phase-device",
            source_family="phase-device",
            c1_score=0.8,
            episode_id="phase-source",
        ),
    ]
    phase_inversion_rejected = False
    try:
        causal_phase_order_audit(inverted)
    except RuntimeError:
        phase_inversion_rejected = True
    if not phase_inversion_rejected:
        raise RuntimeError("causal phase inversion was not rejected")
    reliable[support[0].uid] = False
    cold_hard = decision_array(PRIMARY, support, static, temporal, reliable, 0.5, gate)
    if not cold_hard[0]:
        raise RuntimeError("cold history did not fail closed")
    payload = {
        "status": "CKBQ_CONTRACT_UNIT_PASS",
        "minirocket_shape": list(first.shape),
        "deterministic_across_batch_sizes": True,
        "ppv_min": float(first.min()),
        "ppv_max": float(first.max()),
        "support_preserved": int(support_hard.sum()),
        "benign_suppressed": int((~benign_hard).sum()),
        "cold_fail_hard": True,
        "phase_order_inversion_rejected": phase_inversion_rejected,
        "score_addition_used": False,
    }
    print(json.dumps(payload, indent=2))


def dry_run(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            {
                "status": "CKBQ_DRY_RUN",
                "primary": PRIMARY,
                "window_length": WINDOW_LENGTH,
                "event_channels": ckbe.RAW_MSG_NAMES,
                "minirocket_features": MINIROCKET_FEATURES,
                "ridge_alpha": RIDGE_ALPHA,
                "review_rate": 0.0,
                "formal_only_seed": SEED,
            },
            indent=2,
        )
    )


def scope_audit(args: argparse.Namespace) -> None:
    ckbo.scope_audit(args)
    print(
        json.dumps(
            {
                "status": "CKBQ_SCOPE_AUDIT_PASS",
                "original_1m_modified": False,
                "base_t0_modified": False,
                "report_fit_select_use": 0,
                "aux_temporal_raw_label_read": False,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=["contract-unit", "scope-audit", "dry-run", "formal"], default="dry-run"
    )
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
    parser.add_argument("--rocket-batch-size", type=int, default=256)
    parser.add_argument("--aux-rows-per-source", type=int, default=ckbo.MODEL_READY_PER_SOURCE)
    # Compatibility with CKBO scope/materialization helpers.
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
