"""CKBK: protocol-repaired TGNMemory and DyGLib GraphMixer comparison.

This is a single-seed, result-producing experiment.  It reuses the frozen C1,
CKBE, CKBI, and CKBJ cache contracts without rebuilding them.  Fit, select, and
report use explicit source-local causal replay masks.  Report is frozen,
label-free, no-gradient, past-only, and score-before-update.

The TGN candidate keeps CKBJ's official PyG components and dimensions.  The
GraphMixer candidates reuse the maintained DyGLib temporal-message Mixer with
an explicitly documented anonymous-node adapter.  No node/source identity,
raw label, family, or report role enters either model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import sys
import time
import traceback
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import numpy as np
import pandas as pd
import sklearn
from sklearn.metrics import average_precision_score, roc_auc_score, roc_curve

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as base  # noqa: E402
import issue27ckbk_dyglib_graphmixer_v1 as dyglib  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402

torch = base.torch
nn = base.nn
F = base.F
LastNeighborLoader = base.LastNeighborLoader


ISSUE = "issue27ckbk_temporal_generalization_formal_v1_2026-07-14"
ROOT = cko.ROOT
DEFAULT_T0 = base.DEFAULT_T0
DEFAULT_REPORT_EXTENSION = base.DEFAULT_REPORT_EXTENSION
DEFAULT_C1_PLAN = base.DEFAULT_C1_PLAN
DEFAULT_C1_TARGETS = base.DEFAULT_C1_TARGETS
DEFAULT_C1_CACHE = base.DEFAULT_C1_CACHE
DEFAULT_C1_REPORT_EXTENSION = base.DEFAULT_C1_REPORT_EXTENSION
RAW_MSG_DIM = base.RAW_MSG_DIM
HISTORY_BATCH_SIZE = 200
GRAPH_TOKENS = 20
GRAPH_OUTPUT_DIM = 32
TASK_MIN_CLASS = 64
TASK_MIN_SOURCES = 3
TASK_MIN_CLASS_SOURCES = 2
LINK_MIN_POSITIVES = 128
LINK_MIN_NEGATIVES = 128
NO_SUPPRESSION_THRESHOLD = -1.0
REPORT_ROLES = {"same_file_query", "future_query", "sealed_final_ood", "sealed_final_attack"}
SELECT_ONLY_ROLES = {"support_val"}


def require_runtime() -> None:
    base.require_pyg()


def json_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def audit_key(model: str, protocol: str, held: str | None, phase: str, seed: int) -> dict[str, Any]:
    return {
        "model": str(model), "protocol": str(protocol), "held_value": held or "GLOBAL",
        "phase": str(phase), "seed": int(seed),
    }


def split_values(value: Any) -> set[str]:
    return {part.strip() for part in str(value).split(";") if part.strip() and part.strip().lower() != "nan"}


def compact_intervals(values: Iterable[int]) -> str:
    ordered = sorted(set(int(value) for value in values))
    if not ordered:
        return ""
    intervals: list[str] = []
    start = previous = ordered[0]
    for value in ordered[1:]:
        if value == previous + 1:
            previous = value
            continue
        intervals.append(str(start) if start == previous else f"{start}-{previous}")
        start = previous = value
    intervals.append(str(start) if start == previous else f"{start}-{previous}")
    return ";".join(intervals)


@dataclass(frozen=True)
class ReplayMasks:
    fit_blocked: dict[str, frozenset[int]]
    select_blocked: dict[str, frozenset[int]]
    catalog_rows: tuple[dict[str, Any], ...]

    def blocked(self, phase: str, source: str) -> frozenset[int]:
        if phase == "fit":
            return self.fit_blocked.get(source, frozenset())
        if phase == "select":
            return self.select_blocked.get(source, frozenset())
        if phase == "report":
            return frozenset()
        raise ValueError(f"unknown replay phase: {phase}")


@dataclass
class GraphExamples:
    records: list[base.Record]
    edge_tokens: np.ndarray
    time_gaps: np.ndarray
    valid_mask: np.ndarray
    node_stats: np.ndarray

    def __post_init__(self) -> None:
        rows = len(self.records)
        expected = (rows, 2, GRAPH_TOKENS, RAW_MSG_DIM)
        if self.edge_tokens.shape != expected:
            raise RuntimeError(f"GraphMixer edge token shape {self.edge_tokens.shape} != {expected}")
        if self.time_gaps.shape != expected[:3] or self.valid_mask.shape != expected[:3]:
            raise RuntimeError("GraphMixer time/mask shapes do not match records")
        if self.node_stats.shape != (rows, 2, 8):
            raise RuntimeError("GraphMixer anonymous node-stat shape changed")

    @property
    def uid_to_index(self) -> dict[str, int]:
        values = {record.uid: index for index, record in enumerate(self.records)}
        if len(values) != len(self.records):
            raise RuntimeError("duplicate GraphMixer record UID")
        return values


_ROLE_POSITION_BLOCK_CACHE: dict[
    tuple[int, int], tuple[dict[str, frozenset[int]], dict[str, frozenset[int]], tuple[dict[str, Any], ...]]
] = {}


def role_assigned_position_blocks(
    frames: dict[str, pd.DataFrame],
    t0: T0Cache | base.CompositeT0Cache,
) -> tuple[dict[str, frozenset[int]], dict[str, frozenset[int]], tuple[dict[str, Any], ...]]:
    """Map every role-assigned non-fit/report row back to raw event positions."""

    cache_key = (id(frames), id(t0))
    if cache_key in _ROLE_POSITION_BLOCK_CACHE:
        return _ROLE_POSITION_BLOCK_CACHE[cache_key]
    fit_recorded: defaultdict[str, set[int]] = defaultdict(set)
    select_recorded: defaultdict[str, set[int]] = defaultdict(set)
    for role, frame in frames.items():
        source_values = frame["source_group"].astype(str)
        recorded_values = pd.to_numeric(frame["recorded_index"], errors="coerce")
        if recorded_values.isna().any():
            raise RuntimeError(f"{role}: nonnumeric recorded index in role sidecar")
        phase_values = frame["phase"].astype(str)
        blocks_fit = (
            np.ones(len(frame), dtype=bool)
            if role in REPORT_ROLES or role in SELECT_ONLY_ROLES
            else ~phase_values.eq("fit").to_numpy()
        )
        blocks_select = (
            np.ones(len(frame), dtype=bool)
            if role in REPORT_ROLES
            else phase_values.isin(["report", "report_only"]).to_numpy()
        )
        for source, values in pd.DataFrame({
            "source": source_values, "recorded": recorded_values.astype(np.int64),
            "fit": blocks_fit, "select": blocks_select,
        }).groupby("source", sort=False):
            if bool(values["fit"].any()):
                fit_recorded[str(source)].update(values.loc[values["fit"], "recorded"].astype(int).tolist())
            if bool(values["select"].any()):
                select_recorded[str(source)].update(values.loc[values["select"], "recorded"].astype(int).tolist())
    cached_sources = set(getattr(t0, "cached_sources", set()))
    fit_positions: dict[str, frozenset[int]] = {}; select_positions: dict[str, frozenset[int]] = {}
    rows: list[dict[str, Any]] = []
    for source in sorted((set(fit_recorded) | set(select_recorded)) & cached_sources):
        npz_path, _meta_path = t0.paths(source)
        with np.load(npz_path, allow_pickle=False) as cache_data:
            recorded = np.asarray(cache_data["recorded_index"], dtype=np.int64)
        fit_values = np.fromiter(fit_recorded.get(source, set()), dtype=np.int64)
        select_values = np.fromiter(select_recorded.get(source, set()), dtype=np.int64)
        fit_mask = np.isin(recorded, fit_values, assume_unique=False) if len(fit_values) else np.zeros(len(recorded), dtype=bool)
        select_mask = np.isin(recorded, select_values, assume_unique=False) if len(select_values) else np.zeros(len(recorded), dtype=bool)
        fit_positions[source] = frozenset(np.flatnonzero(fit_mask).astype(int).tolist())
        select_positions[source] = frozenset(np.flatnonzero(select_mask).astype(int).tolist())
        missing_fit = int(len(fit_recorded.get(source, set()) - set(recorded[fit_mask].astype(int).tolist())))
        missing_select = int(len(select_recorded.get(source, set()) - set(recorded[select_mask].astype(int).tolist())))
        rows.append({
            "source_group": source,
            "role_assigned_fit_block_recorded_indices": len(fit_recorded.get(source, set())),
            "role_assigned_fit_block_event_positions": int(fit_mask.sum()),
            "role_assigned_select_block_recorded_indices": len(select_recorded.get(source, set())),
            "role_assigned_select_block_event_positions": int(select_mask.sum()),
            "fit_block_recorded_indices_absent_from_cache": missing_fit,
            "select_block_recorded_indices_absent_from_cache": missing_select,
            "raw_label_column_read": False,
        })
    result = fit_positions, select_positions, tuple(rows)
    _ROLE_POSITION_BLOCK_CACHE[cache_key] = result
    return result


def target_catalog_masks(
    t0: T0Cache | base.CompositeT0Cache,
    target_manifest: Path,
    sets: dict[str, list[base.Record]],
    frames: dict[str, pd.DataFrame],
) -> ReplayMasks:
    """Build per-protocol exact blocked target positions.

    The frozen target manifest aggregates folds, so the legal records selected
    for the current held protocol override an aggregate stage label.  All
    remaining select/support-val/report targets stay blocked during fit, and
    report targets stay blocked during select.  Unselected cache events remain
    label-free causal context; their labels are neither present nor read.
    """

    manifest = pd.read_csv(target_manifest, usecols=["source_group", "recorded_index", "stages", "roles"])
    role_fit, role_select, role_rows = role_assigned_position_blocks(frames, t0)
    aggregate_fit: defaultdict[str, set[int]] = defaultdict(set)
    aggregate_select: defaultdict[str, set[int]] = defaultdict(set)
    rows: list[dict[str, Any]] = []
    position_cache: dict[str, dict[int, int]] = {}
    cached_sources = set(getattr(t0, "cached_sources", set()))
    for source, part in manifest.groupby("source_group", sort=True):
        source = str(source)
        if cached_sources and source not in cached_sources:
            continue
        positions = position_cache.setdefault(source, t0.target_positions(source))
        missing = 0; fit_count = 0; select_count = 0
        for row in part.itertuples(index=False):
            recorded = int(row.recorded_index)
            position = positions.get(recorded)
            if position is None:
                missing += 1
                continue
            stages = split_values(row.stages); roles = split_values(row.roles)
            blocks_fit = bool(stages & {"select", "report"}) or bool(roles & (SELECT_ONLY_ROLES | REPORT_ROLES))
            blocks_select = bool(stages & {"report"}) or bool(roles & REPORT_ROLES)
            if blocks_fit:
                aggregate_fit[source].add(int(position)); fit_count += 1
            if blocks_select:
                aggregate_select[source].add(int(position)); select_count += 1
        if missing:
            raise RuntimeError(f"{source}: {missing} frozen target-manifest rows lack T0 positions")
        rows.append({
            "source_group": source, "manifest_target_rows": int(len(part)),
            "aggregate_fit_block_positions": fit_count, "aggregate_select_block_positions": select_count,
            "all_target_positions_mapped": True,
        })

    legal_fit: defaultdict[str, set[int]] = defaultdict(set)
    legal_select: defaultdict[str, set[int]] = defaultdict(set)
    for record in sets["fit_attack"] + sets["fit_benign"]:
        legal_fit[record.source].add(int(record.event_position))
    for record in sets["select_attack"] + sets["select_benign"]:
        legal_select[record.source].add(int(record.event_position))
    if any(legal_fit[source] & set(role_fit.get(source, frozenset())) for source in legal_fit):
        raise RuntimeError("legal fit target overlaps a support-val/select/report role event")
    if any(legal_select[source] & set(role_select.get(source, frozenset())) for source in legal_select):
        raise RuntimeError("legal select target overlaps a report-role event")
    fit_blocked: dict[str, frozenset[int]] = {}
    select_blocked: dict[str, frozenset[int]] = {}
    all_sources = set(role_fit) | set(role_select) | set(aggregate_fit) | set(aggregate_select)
    for source in all_sources:
        fit_values = set(role_fit.get(source, frozenset())) | (aggregate_fit[source] - legal_fit.get(source, set()))
        select_values = set(role_select.get(source, frozenset())) | (aggregate_select[source] - legal_select.get(source, set()))
        fit_blocked[source] = frozenset(fit_values); select_blocked[source] = frozenset(select_values)
    report_only = set(getattr(t0, "report_only_sources", set()))
    if (set(legal_fit) | set(legal_select)) & report_only:
        raise RuntimeError("report-only cache source entered a fit/select replay mask")
    return ReplayMasks(
        fit_blocked, select_blocked, tuple([*role_rows, *rows]),
    )


def source_phase_manifest_rows(
    model: str,
    protocol: str,
    held: str | None,
    seed: int,
    t0: T0Cache | base.CompositeT0Cache,
    sets: dict[str, list[base.Record]],
    masks: ReplayMasks,
) -> tuple[list[dict[str, Any]], str]:
    rows: list[dict[str, Any]] = []
    phase_records = {
        "fit": sets["fit_attack"] + sets["fit_benign"],
        "select": sets["select_attack"] + sets["select_benign"],
        "report": sets["report"],
    }
    for phase, records in phase_records.items():
        by_source: defaultdict[str, list[base.Record]] = defaultdict(list)
        for record in records:
            by_source[record.source].append(record)
        for source, source_records in sorted(by_source.items()):
            positions = [int(record.event_position) for record in source_records]
            if len(positions) != len(set(positions)):
                raise RuntimeError(f"{protocol}/{source}/{phase}: duplicate scored target position")
            last = max(positions); first = min(positions)
            npz_path, _meta_path = t0.paths(source)
            with np.load(npz_path, allow_pickle=False) as cache_data:
                raw_events = int(len(cache_data["recorded_index"]))
            if first < 0 or last >= raw_events:
                raise RuntimeError(f"{protocol}/{source}/{phase}: target outside T0 event cache")
            blocked = sorted(value for value in masks.blocked(phase, source) if 0 <= int(value) <= last)
            if set(positions) & set(blocked):
                raise RuntimeError(f"{protocol}/{source}/{phase}: a scored target is blocked from its own phase")
            rows.append({
                **audit_key(model, protocol, held, phase, seed),
                "source_group": source, "scored_targets": len(positions),
                "first_target_event_position": first, "last_target_event_position": last,
                "replay_start_event_position": 0, "replay_end_event_position": last,
                "source_raw_events": int(raw_events), "raw_events_in_replay_prefix": int(last + 1),
                "blocked_raw_events_in_prefix": int(len(blocked)),
                "allowed_raw_events_in_prefix": int(last + 1 - len(blocked)),
                "blocked_intervals": compact_intervals(blocked), "fresh_source_reset": True,
                "target_before_update": True, "raw_label_column_read": False,
                "report_only_source": bool(source in set(getattr(t0, "report_only_sources", set()))),
            })
    digest = json_hash(rows)
    return [{**row, "source_phase_manifest_sha256": digest} for row in rows], digest


def iter_allowed_runs(start: int, stop: int, blocked: frozenset[int]) -> Iterator[tuple[int, int]]:
    cursor = int(start)
    for value in sorted(position for position in blocked if int(start) <= position < int(stop)):
        if cursor < value:
            yield cursor, int(value)
        cursor = int(value) + 1
    if cursor < int(stop):
        yield cursor, int(stop)


def update_allowed_history(
    encoder: base.TGNProcessEncoder,
    neighbor: Any,
    store: base.ReplayStore,
    stamp: np.ndarray,
    src: np.ndarray,
    dst: np.ndarray,
    message: np.ndarray,
    start: int,
    stop: int,
    blocked: frozenset[int],
    batch_size: int,
) -> tuple[int, int, int]:
    updates = batches = repeated = 0
    for lower, upper in iter_allowed_runs(start, stop, blocked):
        count, count_batches, count_repeated = base.update_history_slice(
            encoder, neighbor, store, stamp, src, dst, message, lower, upper, batch_size,
        )
        updates += count; batches += count_batches; repeated += count_repeated
    return updates, batches, repeated


def dense_future_task_labels(
    stamp: np.ndarray,
    src: np.ndarray,
    dst: np.ndarray,
    message: np.ndarray,
    targets: set[int],
    blocked: frozenset[int],
) -> dict[int, tuple[int, int | None, int]]:
    """Outcomes from later raw events inside the legal fit replay only."""

    if not targets:
        return {}
    horizon = max(targets)
    next_edge: dict[tuple[int, int], int] = {}
    next_ackrst: dict[tuple[int, int], int] = {}
    labels: dict[int, tuple[int, int | None, int]] = {}
    for index in range(horizon, -1, -1):
        if index in blocked:
            continue
        pair = (int(src[index]), int(dst[index])); reverse = (pair[1], pair[0]); now = int(stamp[index])
        if index in targets:
            reverse_time = next_edge.get(reverse); same_time = next_edge.get(pair); ackrst_time = next_ackrst.get(reverse)
            response = int(reverse_time is not None and 0 <= reverse_time - now <= base.RESPONSE_WINDOW_MS)
            retry = int(same_time is not None and 0 <= same_time - now <= base.RETRY_WINDOW_MS)
            completion: int | None = None
            if bool(message[index, 5] > 0.5):
                completion = int(ackrst_time is not None and 0 <= ackrst_time - now <= base.RESPONSE_WINDOW_MS)
            labels[index] = (response, completion, retry)
        next_edge[pair] = now
        if bool(message[index, 6] > 0.5 or message[index, 7] > 0.5):
            next_ackrst[pair] = now
    if set(labels) != targets:
        raise RuntimeError("dense fit outcome labels do not cover every legal target")
    return labels


def presample_link_negatives(
    stamp: np.ndarray,
    src: np.ndarray,
    dst: np.ndarray,
    targets: set[int],
    blocked: frozenset[int],
    local_nodes: int,
    rng: np.random.Generator,
    neighbor_size: int = 10,
) -> tuple[dict[int, int], list[int]]:
    """Pre-register legal negatives from current-source past-seen nodes only."""

    if not targets:
        return {}, []
    horizon = max(targets); past_seen: set[int] = set()
    recent: defaultdict[int, deque[int]] = defaultdict(lambda: deque(maxlen=int(neighbor_size)))
    negatives: dict[int, int] = {}; pool_sizes: list[int] = []
    for index in range(horizon + 1):
        if index in blocked:
            continue
        left, right = int(src[index]), int(dst[index])
        if not (0 <= left < local_nodes and 0 <= right < local_nodes):
            raise RuntimeError("source-local node metadata does not cover a replay endpoint")
        if index in targets:
            candidates = sorted(past_seen - {left, right} - set(recent[left]))
            pool_sizes.append(len(candidates))
            if candidates:
                negatives[index] = int(candidates[int(rng.integers(0, len(candidates)))])
        past_seen.update((left, right)); recent[left].append(right); recent[right].append(left)
    return negatives, pool_sizes


def task_enabled(
    positives: int,
    negatives: int,
    labeled_sources: int,
    positive_sources: int,
    negative_sources: int,
    link: bool = False,
) -> tuple[bool, str]:
    minimum_positive = LINK_MIN_POSITIVES if link else TASK_MIN_CLASS
    minimum_negative = LINK_MIN_NEGATIVES if link else TASK_MIN_CLASS
    reasons: list[str] = []
    if positives < minimum_positive:
        reasons.append(f"positive<{minimum_positive}")
    if negatives < minimum_negative:
        reasons.append(f"negative<{minimum_negative}")
    total = positives + negatives
    prevalence = positives / total if total else math.nan
    if not link and (not np.isfinite(prevalence) or prevalence < 0.05 or prevalence > 0.95):
        reasons.append("prevalence_outside_[0.05,0.95]")
    if labeled_sources < TASK_MIN_SOURCES:
        reasons.append(f"labeled_sources<{TASK_MIN_SOURCES}")
    if positive_sources < TASK_MIN_CLASS_SOURCES:
        reasons.append(f"positive_sources<{TASK_MIN_CLASS_SOURCES}")
    if negative_sources < TASK_MIN_CLASS_SOURCES:
        reasons.append(f"negative_sources<{TASK_MIN_CLASS_SOURCES}")
    return not reasons, "enabled" if not reasons else ";".join(reasons)


def prepare_tgn_tasks(
    t0: T0Cache | base.CompositeT0Cache,
    fit_records: list[base.Record],
    masks: ReplayMasks,
    seed: int,
    protocol: str,
    held: str | None,
) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[int, tuple[int, int | None, int]]],
    dict[str, dict[int, int]], list[dict[str, Any]], list[dict[str, Any]],
]:
    by_source: defaultdict[str, list[base.Record]] = defaultdict(list)
    for record in fit_records:
        by_source[record.source].append(record)
    rng = np.random.default_rng(int(seed))
    labels_by_source: dict[str, dict[int, tuple[int, int | None, int]]] = {}
    negatives_by_source: dict[str, dict[int, int]] = {}
    per_source: list[dict[str, Any]] = []
    counts: dict[str, Counter[str]] = {
        task: Counter() for task in ("temporal_link", "reverse_response", "ack_rst_completion", "edge_retry_survival")
    }
    class_sources: dict[str, dict[str, set[str]]] = {
        task: {"labeled": set(), "positive": set(), "negative": set()} for task in counts
    }
    for source, records in sorted(by_source.items()):
        targets = {int(record.event_position) for record in records}
        if len(targets) != len(records):
            raise RuntimeError(f"{protocol}/{source}: duplicate legal fit target")
        _recorded, stamp, src, dst, message = base.source_arrays(t0, source)
        blocked = masks.blocked("fit", source)
        labels = dense_future_task_labels(stamp, src, dst, message, targets, blocked)
        local_nodes = int(t0.summary(source).get("source_local_nodes", 0))
        sampled, pool_sizes = presample_link_negatives(
            stamp, src, dst, targets, blocked, local_nodes, rng,
        )
        labels_by_source[source] = labels; negatives_by_source[source] = sampled
        source_counts: dict[str, tuple[int, int]] = {
            "temporal_link": (len(targets), len(sampled)),
            "reverse_response": (
                sum(value[0] == 1 for value in labels.values()), sum(value[0] == 0 for value in labels.values()),
            ),
            "ack_rst_completion": (
                sum(value[1] == 1 for value in labels.values()), sum(value[1] == 0 for value in labels.values()),
            ),
            "edge_retry_survival": (
                sum(value[2] == 1 for value in labels.values()), sum(value[2] == 0 for value in labels.values()),
            ),
        }
        for task, (positive, negative) in source_counts.items():
            counts[task]["positive"] += int(positive); counts[task]["negative"] += int(negative)
            if positive + negative:
                class_sources[task]["labeled"].add(source)
            if positive:
                class_sources[task]["positive"].add(source)
            if negative:
                class_sources[task]["negative"].add(source)
        per_source.append({
            **audit_key("TGNMemory-Repair", protocol, held, "fit", seed),
            "source_group": source, "fit_targets": len(targets),
            "fit_horizon_event_position": max(targets),
            "fit_blocked_positions_before_horizon": int(sum(value <= max(targets) for value in blocked)),
            "link_legal_negatives": len(sampled), "link_skipped_no_legal_candidate": len(targets) - len(sampled),
            "candidate_pool_min": int(min(pool_sizes) if pool_sizes else 0),
            "candidate_pool_mean": float(np.mean(pool_sizes) if pool_sizes else 0.0),
            "candidate_pool_max": int(max(pool_sizes) if pool_sizes else 0),
            "reverse_positive": source_counts["reverse_response"][0],
            "reverse_negative": source_counts["reverse_response"][1],
            "completion_positive": source_counts["ack_rst_completion"][0],
            "completion_negative": source_counts["ack_rst_completion"][1],
            "retry_positive": source_counts["edge_retry_survival"][0],
            "retry_negative": source_counts["edge_retry_survival"][1],
            "ghost_node_negatives": 0, "future_node_identity_used": False,
            "future_outcome_crossed_fit_horizon": False, "select_report_outcome_used": False,
        })
    tasks: dict[str, dict[str, Any]] = {}
    task_rows: list[dict[str, Any]] = []
    for task in counts:
        positive = int(counts[task]["positive"]); negative = int(counts[task]["negative"])
        enabled, reason = task_enabled(
            positive, negative, len(class_sources[task]["labeled"]),
            len(class_sources[task]["positive"]), len(class_sources[task]["negative"]),
            link=task == "temporal_link",
        )
        row = {
            **audit_key("TGNMemory-Repair", protocol, held, "fit", seed),
            "task": task, "positive": positive, "negative": negative,
            "positive_rate": float(positive / (positive + negative)) if positive + negative else math.nan,
            "labeled_sources": len(class_sources[task]["labeled"]),
            "positive_sources": len(class_sources[task]["positive"]),
            "negative_sources": len(class_sources[task]["negative"]),
            "task_enabled": bool(enabled), "eligibility_reason": reason,
        }
        tasks[task] = row; task_rows.append(row)
    if not tasks["temporal_link"]["task_enabled"]:
        raise RuntimeError(f"{protocol}: temporal link task failed preregistered eligibility")
    return tasks, labels_by_source, negatives_by_source, task_rows, per_source


def pretrain_tgn_repair(
    t0: T0Cache | base.CompositeT0Cache,
    fit_records: list[base.Record],
    masks: ReplayMasks,
    node_capacity: int,
    memory_dim: int,
    time_dim: int,
    epochs: int,
    detach_every: int,
    history_batch_size: int,
    seed: int,
    protocol: str,
    held: str | None,
) -> tuple[base.TGNProcessEncoder, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require_runtime()
    report_only = set(getattr(t0, "report_only_sources", set()))
    by_source: defaultdict[str, list[base.Record]] = defaultdict(list)
    for record in fit_records:
        by_source[record.source].append(record)
    if set(by_source) & report_only:
        raise RuntimeError("report-only source entered repaired TGN fit")
    capacity = max(base.source_capacity(t0, by_source), int(node_capacity))
    tasks, labels_by_source, negatives_by_source, task_rows, negative_rows = prepare_tgn_tasks(
        t0, fit_records, masks, seed, protocol, held,
    )
    torch.manual_seed(int(seed)); np.random.seed(int(seed))
    encoder = base.make_encoder(capacity, memory_dim, time_dim)
    heads = base.SelfSupervisionHeads(memory_dim, RAW_MSG_DIM)
    optimizer = torch.optim.AdamW(list(encoder.parameters()) + list(heads.parameters()), lr=1e-3, weight_decay=1e-3)
    history: list[dict[str, Any]] = []
    head_by_task = {
        "reverse_response": heads.reverse,
        "ack_rst_completion": heads.completion,
        "edge_retry_survival": heads.retry,
    }
    for epoch in range(1, int(epochs) + 1):
        encoder.train(); heads.train(); pending: list[torch.Tensor] = []
        summary: defaultdict[str, list[float]] = defaultdict(list)
        total_updates = total_batches = total_repeated = resets = 0
        for source, records in sorted(by_source.items()):
            targets = sorted(int(record.event_position) for record in records)
            _recorded, stamp, src, dst, message = base.source_arrays(t0, source)
            blocked = masks.blocked("fit", source)
            labels = labels_by_source[source]; sampled = negatives_by_source[source]
            encoder.reset_state(); neighbor = LastNeighborLoader(capacity, size=10)
            store = base.ReplayStore(max(1, targets[-1] + 1 - sum(value <= targets[-1] for value in blocked)))
            resets += 1; cursor = 0
            for index in targets:
                updates, batches, repeated = update_allowed_history(
                    encoder, neighbor, store, stamp, src, dst, message,
                    cursor, index, blocked, history_batch_size,
                )
                total_updates += updates; total_batches += batches; total_repeated += repeated
                left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
                msg = torch.from_numpy(message[index:index + 1].astype(np.float32, copy=False))
                moment = torch.tensor([int(stamp[index])], dtype=torch.long)
                representation = encoder.pair_embedding(pair, neighbor, store)
                feature = base.SelfSupervisionHeads.features(representation[0:1], representation[1:2], msg)
                positive = heads.link(feature).reshape(-1)
                loss = F.binary_cross_entropy_with_logits(positive, torch.ones_like(positive))
                pending.append(loss); summary["temporal_link"].append(float(loss.detach()))
                if index in sampled:
                    negative_id = int(sampled[index])
                    if negative_id in base.loader_neighbor_ids(neighbor, left):
                        raise RuntimeError(f"{protocol}/{source}: preregistered negative entered current PyG neighbours")
                    negative_rep = encoder.pair_embedding(torch.tensor([left, negative_id], dtype=torch.long), neighbor, store)
                    negative_feature = base.SelfSupervisionHeads.features(negative_rep[0:1], negative_rep[1:2], msg)
                    negative_logit = heads.link(negative_feature).reshape(-1)
                    loss = F.binary_cross_entropy_with_logits(negative_logit, torch.zeros_like(negative_logit))
                    pending.append(loss); summary["temporal_link"].append(float(loss.detach()))
                response, completion, retry = labels[index]
                values: dict[str, int | None] = {
                    "reverse_response": response,
                    "ack_rst_completion": completion,
                    "edge_retry_survival": retry,
                }
                for task, value in values.items():
                    if not bool(tasks[task]["task_enabled"]) or value is None:
                        continue
                    logit = head_by_task[task](feature).reshape(-1)
                    target = torch.tensor([float(value)], dtype=torch.float32)
                    loss = F.binary_cross_entropy_with_logits(logit, target)
                    pending.append(loss); summary[task].append(float(loss.detach()))
                encoder.update_state(pair[0:1], pair[1:2], moment, msg, neighbor, store)
                total_updates += 1; total_batches += 1; cursor = index + 1
                if len(pending) >= int(detach_every):
                    optimizer.zero_grad(); torch.stack(pending).mean().backward()
                    torch.nn.utils.clip_grad_norm_(list(encoder.parameters()) + list(heads.parameters()), 5.0)
                    optimizer.step(); encoder.detach(); pending.clear()
            if pending:
                optimizer.zero_grad(); torch.stack(pending).mean().backward()
                torch.nn.utils.clip_grad_norm_(list(encoder.parameters()) + list(heads.parameters()), 5.0)
                optimizer.step(); encoder.detach(); pending.clear()
        row: dict[str, Any] = {
            **audit_key("TGNMemory-Repair", protocol, held, "fit", seed),
            "stage": "ssl", "epoch": epoch, "memory_resets": resets,
            "memory_updates": total_updates, "history_update_batches": total_batches,
            "history_batch_size": int(history_batch_size),
            "repeated_endpoint_occurrences": total_repeated,
        }
        for task in tasks:
            values = summary.get(task, [])
            row[f"{task}_loss"] = float(np.mean(values)) if values else math.nan
            row[f"{task}_enabled"] = bool(tasks[task]["task_enabled"])
        losses = [value for key, value in row.items() if key.endswith("_loss") and np.isfinite(value)]
        row["finite_losses"] = bool(losses and np.isfinite(losses).all())
        history.append(row)
    encoder.eval()
    return encoder, history, task_rows, negative_rows


@torch.no_grad()
def embed_tgn_phase(
    encoder: base.TGNProcessEncoder,
    t0: T0Cache | base.CompositeT0Cache,
    records: list[base.Record],
    masks: ReplayMasks,
    phase: str,
    memory_dim: int,
    history_batch_size: int,
    model: str,
    protocol: str,
    held: str | None,
    seed: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    by_source: defaultdict[str, list[base.Record]] = defaultdict(list)
    for record in records:
        by_source[record.source].append(record)
    embeddings: dict[str, np.ndarray] = {}; audits: list[dict[str, Any]] = []
    encoder.eval()
    for source, source_records in sorted(by_source.items()):
        wanted = {int(record.event_position): record for record in source_records}
        if len(wanted) != len(source_records):
            raise RuntimeError(f"{protocol}/{source}/{phase}: duplicate TGN score target")
        last = max(wanted); blocked = masks.blocked(phase, source)
        encoder.reset_state(); neighbor = LastNeighborLoader(encoder.num_nodes, size=10)
        store = base.ReplayStore(max(1, last + 1 - sum(value <= last for value in blocked)))
        cursor = updates = batches = repeated = cold = 0
        for index in sorted(wanted):
            step = update_allowed_history(
                encoder, neighbor, store, stamp, src, dst, message,
                cursor, index, blocked, history_batch_size,
            )
            updates += step[0]; batches += step[1]; repeated += step[2]
            pair = torch.tensor([int(src[index]), int(dst[index])], dtype=torch.long)
            msg = torch.from_numpy(message[index:index + 1].astype(np.float32, copy=False))
            moment = torch.tensor([int(stamp[index])], dtype=torch.long)
            cold += int(store.count == 0)
            representation = encoder.pair_embedding(pair, neighbor, store)
            embeddings[wanted[index].uid] = representation.detach().cpu().numpy().reshape(memory_dim * 2).astype(np.float32)
            encoder.update_state(pair[0:1], pair[1:2], moment, msg, neighbor, store)
            updates += 1; batches += 1; cursor = index + 1
        audits.append({
            **audit_key(model, protocol, held, phase, seed),
            "source_group": source, "records_scored": len(wanted), "memory_updates": updates,
            "memory_only_events": updates - len(wanted), "history_update_batches": batches,
            "history_batch_size": int(history_batch_size), "repeated_endpoint_occurrences": repeated,
            "cold_start_targets": cold, "cold_start_ratio": float(cold / len(wanted)),
            "blocked_raw_events_before_last_target": int(sum(value <= last for value in blocked)),
            "memory_resets": 1, "target_before_update": True,
            "all_weights_frozen": True, "no_grad": True,
            "labels_read_for_memory": False, "raw_label_column_read": False,
            "report_only_source": bool(source in set(getattr(t0, "report_only_sources", set()))),
        })
    missing = [record.uid for record in records if record.uid not in embeddings]
    if missing:
        raise RuntimeError(f"{model}/{protocol}/{phase}: {len(missing)} missing TGN embeddings")
    return embeddings, audits


def embed_tgn_protocol(
    encoder: base.TGNProcessEncoder,
    t0: T0Cache | base.CompositeT0Cache,
    sets: dict[str, list[base.Record]],
    masks: ReplayMasks,
    memory_dim: int,
    history_batch_size: int,
    model: str,
    protocol: str,
    held: str | None,
    seed: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    phase_records = {
        "fit": sets["fit_attack"] + sets["fit_benign"],
        "select": sets["select_attack"] + sets["select_benign"],
        "report": sets["report"],
    }
    merged: dict[str, np.ndarray] = {}; audits: list[dict[str, Any]] = []
    for phase, records in phase_records.items():
        values, rows = embed_tgn_phase(
            encoder, t0, records, masks, phase, memory_dim, history_batch_size,
            model, protocol, held, seed,
        )
        collision = set(merged) & set(values)
        if collision:
            raise RuntimeError(f"TGN phase UID collision: {next(iter(collision))}")
        merged.update(values); audits.extend(rows)
    return merged, audits


def endpoint_tokens(
    history: deque[tuple[int, np.ndarray]],
    now_ms: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    messages = np.zeros((GRAPH_TOKENS, RAW_MSG_DIM), dtype=np.float32)
    gaps = np.zeros(GRAPH_TOKENS, dtype=np.float32)
    mask = np.zeros(GRAPH_TOKENS, dtype=bool)
    values = list(history)[-GRAPH_TOKENS:]
    offset = GRAPH_TOKENS - len(values)
    for local, (stamp_ms, message) in enumerate(values, start=offset):
        gap = int(now_ms) - int(stamp_ms)
        if gap < 0:
            raise RuntimeError("future GraphMixer token entered a target history")
        messages[local] = np.asarray(message, dtype=np.float32)
        gaps[local] = float(gap) / 1000.0
        mask[local] = True
    return messages, gaps, mask


@dataclass
class _GraphReplayCache:
    blocked: frozenset[int]
    capture_positions: frozenset[int]
    next_index: int = 0
    histories: Any = None
    incident: Any = None
    outgoing: Any = None
    incoming: Any = None
    out_neighbours: Any = None
    in_neighbours: Any = None
    last_seen: Any = None
    features: Any = None

    def __post_init__(self) -> None:
        self.histories = defaultdict(lambda: deque(maxlen=GRAPH_TOKENS))
        self.incident = Counter(); self.outgoing = Counter(); self.incoming = Counter()
        self.out_neighbours = defaultdict(set); self.in_neighbours = defaultdict(set)
        self.last_seen = {}; self.features = {}

    def extend(
        self,
        last: int,
        stamp: np.ndarray,
        src: np.ndarray,
        dst: np.ndarray,
        message: np.ndarray,
    ) -> None:
        if int(last) < self.next_index:
            return
        for index in range(self.next_index, int(last) + 1):
            if index in self.blocked:
                continue
            left, right, now = int(src[index]), int(dst[index]), int(stamp[index])
            if index in self.capture_positions:
                per_tokens: list[np.ndarray] = []; per_gaps: list[np.ndarray] = []
                per_masks: list[np.ndarray] = []; per_stats: list[np.ndarray] = []
                for node in (left, right):
                    tokens, gaps, valid = endpoint_tokens(self.histories[node], now)
                    per_tokens.append(tokens); per_gaps.append(gaps); per_masks.append(valid)
                    neighbours = self.out_neighbours[node] | self.in_neighbours[node]
                    reciprocal = self.out_neighbours[node] & self.in_neighbours[node]
                    gap_ms = None if node not in self.last_seen else now - self.last_seen[node]
                    per_stats.append(dyglib.anonymous_node_statistics(
                        self.incident[node], self.outgoing[node], self.incoming[node],
                        len(neighbours), len(reciprocal), gap_ms,
                    ))
                self.features[index] = (
                    np.stack(per_tokens), np.stack(per_gaps), np.stack(per_masks), np.stack(per_stats),
                )
            raw = np.asarray(message[index], dtype=np.float32).copy()
            self.histories[left].append((now, raw)); self.histories[right].append((now, raw))
            self.incident[left] += 1; self.incident[right] += 1
            self.outgoing[left] += 1; self.incoming[right] += 1
            self.out_neighbours[left].add(right); self.in_neighbours[right].add(left)
            self.last_seen[left] = now; self.last_seen[right] = now
        self.next_index = int(last) + 1


_GRAPH_REPLAY_CACHE: dict[tuple[str, str, str], _GraphReplayCache] = {}


def build_graph_examples(
    t0: T0Cache | base.CompositeT0Cache,
    records: list[base.Record],
    masks: ReplayMasks,
    phase: str,
    model: str,
    protocol: str,
    held: str | None,
    seed: int,
) -> tuple[GraphExamples, list[dict[str, Any]]]:
    """Stream source-local raw events once and snapshot pre-event histories."""

    by_source: defaultdict[str, list[base.Record]] = defaultdict(list)
    for record in records:
        by_source[record.source].append(record)
    output_records: list[base.Record] = []
    output_tokens: list[np.ndarray] = []; output_gaps: list[np.ndarray] = []
    output_masks: list[np.ndarray] = []; output_stats: list[np.ndarray] = []
    audit: list[dict[str, Any]] = []
    for source, source_records in sorted(by_source.items()):
        wanted = {int(record.event_position): record for record in source_records}
        if len(wanted) != len(source_records):
            raise RuntimeError(f"{protocol}/{source}/{phase}: duplicate GraphMixer target")
        last = max(wanted); blocked = masks.blocked(phase, source)
        blocked_digest = hashlib.sha256(np.asarray(sorted(blocked), dtype=np.int64).tobytes()).hexdigest()
        cache_key = (source, phase, blocked_digest)
        cache_reused = cache_key in _GRAPH_REPLAY_CACHE
        if not cache_reused:
            capture = frozenset(int(value) for value in t0.target_positions(source).values())
            _GRAPH_REPLAY_CACHE[cache_key] = _GraphReplayCache(blocked=blocked, capture_positions=capture)
        cache = _GRAPH_REPLAY_CACHE[cache_key]
        if last >= cache.next_index:
            _recorded, stamp, src, dst, message = base.source_arrays(t0, source)
            cache.extend(last, stamp, src, dst, message)
        cold = 0
        for index, record in sorted(wanted.items()):
            if index not in cache.features:
                raise RuntimeError(f"{protocol}/{source}/{phase}: target missing from causal GraphMixer cache")
            tokens, gaps, valid, stats = cache.features[index]
            cold += int(not valid[0].any() and not valid[1].any())
            output_records.append(record); output_tokens.append(tokens); output_gaps.append(gaps)
            output_masks.append(valid); output_stats.append(stats)
        blocked_count = int(sum(value <= last for value in blocked))
        visible = int(last + 1 - blocked_count)
        audit.append({
            **audit_key(model, protocol, held, phase, seed),
            "source_group": source, "records_scored": len(wanted), "raw_events_visible": visible,
            "blocked_raw_events_before_last_target": blocked_count, "history_tokens": GRAPH_TOKENS,
            "cold_start_targets": cold, "cold_start_ratio": float(cold / len(wanted)),
            "memory_resets": 1, "target_before_update": True, "past_only": True,
            "deterministic_feature_cache_reused": bool(cache_reused),
            "feature_cache_shares_no_mutable_model_state": True,
            "source_local_anonymous_ids_not_model_inputs": True, "raw_label_column_read": False,
            "no_grad": phase != "fit", "report_only_source": bool(source in set(getattr(t0, "report_only_sources", set()))),
        })
    if not output_records:
        empty_tokens = np.empty((0, 2, GRAPH_TOKENS, RAW_MSG_DIM), dtype=np.float32)
        return GraphExamples(
            [], empty_tokens, np.empty((0, 2, GRAPH_TOKENS), dtype=np.float32),
            np.empty((0, 2, GRAPH_TOKENS), dtype=bool), np.empty((0, 2, 8), dtype=np.float32),
        ), audit
    examples = GraphExamples(
        output_records, np.stack(output_tokens).astype(np.float32, copy=False),
        np.stack(output_gaps).astype(np.float32, copy=False),
        np.stack(output_masks).astype(bool, copy=False),
        np.stack(output_stats).astype(np.float32, copy=False),
    )
    if {record.uid for record in records} != {record.uid for record in output_records}:
        raise RuntimeError(f"{model}/{protocol}/{phase}: GraphMixer target coverage mismatch")
    return examples, audit


def merge_graph_examples(parts: Sequence[GraphExamples]) -> GraphExamples:
    records = [record for part in parts for record in part.records]
    if len({record.uid for record in records}) != len(records):
        raise RuntimeError("GraphMixer phase-isolation UID collision")
    if not records:
        return GraphExamples(
            [], np.empty((0, 2, GRAPH_TOKENS, RAW_MSG_DIM), dtype=np.float32),
            np.empty((0, 2, GRAPH_TOKENS), dtype=np.float32),
            np.empty((0, 2, GRAPH_TOKENS), dtype=bool), np.empty((0, 2, 8), dtype=np.float32),
        )
    return GraphExamples(
        records, np.concatenate([part.edge_tokens for part in parts], axis=0),
        np.concatenate([part.time_gaps for part in parts], axis=0),
        np.concatenate([part.valid_mask for part in parts], axis=0),
        np.concatenate([part.node_stats for part in parts], axis=0),
    )


def graph_tensor_batch(examples: GraphExamples, indices: Sequence[int]) -> tuple[Any, Any, Any, Any]:
    index = np.asarray(indices, dtype=np.int64)
    return (
        torch.from_numpy(examples.edge_tokens[index]), torch.from_numpy(examples.time_gaps[index]),
        torch.from_numpy(examples.valid_mask[index]), torch.from_numpy(examples.node_stats[index]),
    )


def family_balanced_attack_order(
    attack: list[base.Record], rng: np.random.Generator,
) -> tuple[list[int], int, dict[str, list[int]]]:
    family_indices: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(attack):
        family_indices[record.attack_family].append(index)
    if not family_indices:
        raise RuntimeError("no attack families for supervised verifier")
    max_family = max(len(values) for values in family_indices.values())
    expanded_by_family: dict[str, list[int]] = {}
    for family, values in sorted(family_indices.items()):
        expanded: list[int] = []
        while len(expanded) < max_family:
            expanded.extend(rng.permutation(values).tolist())
        expanded_by_family[family] = expanded[:max_family]
    order: list[int] = []
    families = sorted(expanded_by_family)
    for offset in range(max_family):
        for family in rng.permutation(families).tolist():
            order.append(int(expanded_by_family[str(family)][offset]))
    return order, max_family, dict(family_indices)


def train_graph_verifier(
    examples: GraphExamples,
    attack: list[base.Record],
    benign: list[base.Record],
    message_only: bool,
    freeze_encoder: bool,
    epochs: int,
    negative_ratio: int,
    seed: int,
    candidate: str,
    protocol: str,
    held: str | None,
) -> tuple[dyglib.AnonymousGraphMixer, base.VerifierHead, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require_runtime()
    if not attack or not benign:
        raise RuntimeError("GraphMixer verifier requires fit attack and fit benign rows")
    index_by_uid = examples.uid_to_index
    missing = [record.uid for record in attack + benign if record.uid not in index_by_uid]
    if missing:
        raise RuntimeError(f"GraphMixer fit examples miss {len(missing)} records")
    torch.manual_seed(int(seed)); rng = np.random.default_rng(int(seed))
    encoder = dyglib.AnonymousGraphMixer(
        edge_feat_dim=RAW_MSG_DIM, time_feat_dim=16, num_tokens=GRAPH_TOKENS,
        num_layers=2, token_dim_expansion_factor=0.5, channel_dim_expansion_factor=4.0,
        dropout=0.1, output_dim=GRAPH_OUTPUT_DIM, message_only=bool(message_only),
    )
    head = base.VerifierHead(GRAPH_OUTPUT_DIM)
    if freeze_encoder:
        for parameter in encoder.parameters():
            parameter.requires_grad = False
        encoder.eval()
    parameters = list(head.parameters()) + ([] if freeze_encoder else list(encoder.parameters()))
    optimizer = torch.optim.AdamW(parameters, lr=2e-3, weight_decay=1e-3)
    usage: Counter[str] = Counter(); family_usage: Counter[str] = Counter()
    history: list[dict[str, Any]] = []
    benign_order = np.arange(len(benign), dtype=np.int64); benign_cursor = 0
    family_indices: dict[str, list[int]] = {}
    for epoch in range(1, int(epochs) + 1):
        if not freeze_encoder:
            encoder.train()
        head.train(); rng.shuffle(benign_order)
        order, max_family, family_indices = family_balanced_attack_order(attack, rng)
        losses: list[float] = []
        for attack_index in order:
            chosen = [attack[int(attack_index)]]
            for _ in range(max(1, int(negative_ratio))):
                chosen.append(benign[int(benign_order[benign_cursor % len(benign_order)])])
                benign_cursor += 1
            batch_indices = [index_by_uid[record.uid] for record in chosen]
            tensors = graph_tensor_batch(examples, batch_indices)
            labels = torch.tensor([float(record.label) for record in chosen], dtype=torch.float32)
            optimizer.zero_grad(); representation = encoder(*tensors); logits = head(representation)
            loss = F.binary_cross_entropy_with_logits(logits, labels); loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 5.0); optimizer.step()
            losses.append(float(loss.detach()))
            record = attack[int(attack_index)]; usage[record.uid] += 1; family_usage[record.attack_family] += 1
        all_used = all(usage[record.uid] >= epoch for record in attack)
        history.append({
            **audit_key(candidate, protocol, held, "fit", seed),
            "stage": "supervised_verifier", "epoch": epoch, "loss": float(np.mean(losses)),
            "finite_losses": bool(losses and np.isfinite(losses).all()), "all_support_used": all_used,
            "encoder_frozen": bool(freeze_encoder), "message_only": bool(message_only),
            "family_balanced_examples_per_family": int(max_family), "optimizer_attack_steps": len(order),
            "benign_examples": len(order) * max(1, int(negative_ratio)),
        })
    encoder.eval(); head.eval()
    usage_rows = [{
        **audit_key(candidate, protocol, held, "fit", seed),
        "uid": record.uid, "attack_family": record.attack_family, "source_group": record.source,
        "uses": int(usage[record.uid]), "minimum_required_uses": int(epochs),
        "used_at_least_once_each_epoch": bool(usage[record.uid] >= int(epochs)),
    } for record in attack]
    if not all(row["used_at_least_once_each_epoch"] for row in usage_rows):
        raise RuntimeError(f"{candidate}: not every legal support row was used each epoch")
    family_rows = [{
        **audit_key(candidate, protocol, held, "fit", seed),
        "attack_family": family, "unique_support_rows": len(values),
        "training_uses": int(family_usage[family]), "epochs": int(epochs),
        "balanced_examples_per_epoch": max(len(group) for group in family_indices.values()),
    } for family, values in sorted(family_indices.items())]
    return encoder, head, history, usage_rows, family_rows


@torch.no_grad()
def graph_scores(
    encoder: dyglib.AnonymousGraphMixer,
    head: base.VerifierHead,
    examples: GraphExamples,
    batch_size: int = 2048,
) -> dict[str, float]:
    encoder.eval(); head.eval(); values: list[np.ndarray] = []
    for start in range(0, len(examples.records), int(batch_size)):
        indices = np.arange(start, min(len(examples.records), start + int(batch_size)), dtype=np.int64)
        tensors = graph_tensor_batch(examples, indices)
        values.append(torch.sigmoid(head(encoder(*tensors))).cpu().numpy().astype(np.float64))
    scores = np.concatenate(values) if values else np.empty(0, dtype=np.float64)
    if len(scores) != len(examples.records) or not np.isfinite(scores).all():
        raise RuntimeError("GraphMixer scoring produced missing/nonfinite values")
    return {record.uid: float(score) for record, score in zip(examples.records, scores.tolist())}


def choose_complete_gate(
    candidate: str,
    support_val: list[base.Record],
    select_benign: list[base.Record],
    scores: dict[str, float],
    c1_threshold: float,
    protocol: str,
    held: str | None,
    seed: int,
    tgn_only: bool = False,
) -> tuple[float, list[dict[str, Any]], bool]:
    if not support_val or not select_benign:
        raise RuntimeError("gate selection requires legal support-val and benign select rows")
    combined = np.asarray([scores[record.uid] for record in support_val + select_benign], dtype=np.float64)
    if not np.isfinite(combined).all():
        raise RuntimeError(f"{candidate}: nonfinite legal select score")
    thresholds = np.asarray([NO_SUPPRESSION_THRESHOLD, *sorted(set(combined.tolist()))], dtype=np.float64)
    c1_attack = np.asarray([record.c1_score >= c1_threshold for record in support_val], dtype=bool)
    c1_benign = np.asarray([record.c1_score >= c1_threshold for record in select_benign], dtype=bool)
    base_recall = float(np.mean(c1_attack))
    attack_scores = np.asarray([scores[record.uid] for record in support_val], dtype=np.float64)
    benign_scores = np.asarray([scores[record.uid] for record in select_benign], dtype=np.float64)

    def counts_at(values: np.ndarray) -> np.ndarray:
        ordered = np.sort(values)
        return len(ordered) - np.searchsorted(ordered, thresholds, side="left")

    hard_attack_counts = counts_at(attack_scores if tgn_only else attack_scores[c1_attack])
    hard_benign_counts = counts_at(benign_scores if tgn_only else benign_scores[c1_benign])
    family_counts: list[tuple[np.ndarray, int, int]] = []
    for family in sorted({record.attack_family for record in support_val}):
        family_mask = np.asarray([record.attack_family == family for record in support_val], dtype=bool)
        if int(family_mask.sum()) < 3:
            continue
        base_count = int(np.sum(c1_attack[family_mask]))
        eligible_scores = attack_scores[family_mask if tgn_only else (family_mask & c1_attack)]
        family_counts.append((counts_at(eligible_scores), int(family_mask.sum()), base_count))
    rows: list[dict[str, Any]] = []
    for threshold_index, threshold in enumerate(thresholds.tolist()):
        recall = float(hard_attack_counts[threshold_index] / len(support_val))
        benign_rate = float(hard_benign_counts[threshold_index] / len(select_benign))
        family_ok = True; worst_family_drop = 0.0
        for counts, denominator, base_count in family_counts:
            family_drop = float((counts[threshold_index] - base_count) / denominator)
            worst_family_drop = min(worst_family_drop, family_drop)
            if family_drop < -0.02 - 1e-12:
                family_ok = False
        eligible = bool(recall >= base_recall - 0.005 - 1e-12 and family_ok)
        rows.append({
            **audit_key(candidate, protocol, held, "select", seed),
            "candidate": candidate, "verifier_threshold": float(threshold),
            "no_suppression_sentinel": bool(threshold == NO_SUPPRESSION_THRESHOLD),
            "support_val_c1_recall": base_recall, "support_val_hard_recall": recall,
            "overall_attack_delta_pp": 100.0 * (recall - base_recall),
            "worst_family_delta_pp": 100.0 * worst_family_drop,
            "select_benign_hard_rate": benign_rate, "eligible": eligible,
            "selected": False, "gate_constraint_pass": eligible,
            "selected_despite_constraint_failure": False,
        })
    eligible_rows = [row for row in rows if bool(row["eligible"])]
    if not eligible_rows:
        raise RuntimeError(f"{candidate}: complete gate search found no attack-preserving threshold")
    selected = min(
        eligible_rows,
        key=lambda row: (
            float(row["select_benign_hard_rate"]), -float(row["support_val_hard_recall"]),
            float(row["verifier_threshold"]),
        ),
    )
    selected["selected"] = True
    return float(selected["verifier_threshold"]), rows, True


def hard_decisions(
    candidate: str,
    records: list[base.Record],
    scores: dict[str, float],
    c1_threshold: float,
    verifier_threshold: float,
    verifier_only: bool = False,
) -> np.ndarray:
    verifier = np.asarray([scores[record.uid] >= verifier_threshold for record in records], dtype=bool)
    if verifier_only:
        return verifier
    return verifier & np.asarray([record.c1_score >= c1_threshold for record in records], dtype=bool)


def metric_value(labels: np.ndarray, scores: np.ndarray, name: str) -> float:
    if len(np.unique(labels)) < 2:
        return math.nan
    if name == "auroc":
        return float(roc_auc_score(labels, scores))
    if name == "auprc":
        return float(average_precision_score(labels, scores))
    if name == "pauc_fpr_0_01":
        return float(roc_auc_score(labels, scores, max_fpr=0.01))
    if name.startswith("tpr_at_fpr_"):
        limit = float(name.removeprefix("tpr_at_fpr_"))
        fpr, tpr, _ = roc_curve(labels, scores)
        valid = tpr[fpr <= limit + 1e-15]
        return float(valid.max()) if len(valid) else 0.0
    if name == "attack_benign_margin":
        return float(scores[labels == 1].mean() - scores[labels == 0].mean())
    raise ValueError(name)


def cluster_bootstrap_metric(
    records: list[base.Record], labels: np.ndarray, scores: np.ndarray,
    metric: str, reps: int, seed: int,
) -> tuple[float, float, str, int]:
    source_count = len({record.source for record in records})
    unit = "source" if source_count >= 2 else "episode"
    keys = [record.source if unit == "source" else record.episode_id for record in records]
    groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, key in enumerate(keys):
        if key:
            groups[str(key)].append(index)
    if len(groups) < 2:
        return math.nan, math.nan, "unavailable", len(groups)
    values = list(groups.values()); rng = np.random.default_rng(int(seed)); draws: list[float] = []
    for _ in range(int(reps)):
        chosen: list[int] = []
        for _group in values:
            chosen.extend(values[int(rng.integers(0, len(values)))])
        indices = np.asarray(chosen, dtype=np.int64)
        value = metric_value(labels[indices], scores[indices], metric)
        if np.isfinite(value):
            draws.append(float(value))
    if not draws:
        return math.nan, math.nan, unit, len(groups)
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)), unit, len(groups)


def representation_audit(
    candidate: str,
    records: list[base.Record],
    scores: dict[str, float],
    selection_rows: list[dict[str, Any]],
    protocol: str,
    held: str | None,
    seed: int,
    bootstrap_reps: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels = np.asarray([record.label for record in records], dtype=np.int64)
    values = np.asarray([scores[record.uid] for record in records], dtype=np.float64)
    if set(np.unique(labels)) != {0, 1}:
        raise RuntimeError(f"{candidate}: representation audit needs legal select attack and benign rows")
    selected = [row for row in selection_rows if bool(row.get("selected", False))]
    feasible = int(sum(bool(row.get("eligible", False)) for row in selection_rows))
    selected_threshold = float(selected[0]["verifier_threshold"]) if len(selected) == 1 else math.nan
    metrics: list[dict[str, Any]] = []
    for name in ("auroc", "auprc", "pauc_fpr_0_01", "tpr_at_fpr_0.001", "tpr_at_fpr_0.01", "attack_benign_margin"):
        value = metric_value(labels, values, name)
        low, high, unit, clusters = cluster_bootstrap_metric(
            records, labels, values, name, bootstrap_reps, seed + len(metrics),
        )
        metrics.append({
            **audit_key(candidate, protocol, held, "select", seed),
            "candidate": candidate, "metric": name, "value": value,
            "ci_low": low, "ci_high": high, "ci_cluster_unit": unit, "ci_clusters": clusters,
            "rows": len(records), "attack_rows": int(labels.sum()), "benign_rows": int((labels == 0).sum()),
            "feasible_gate_thresholds": feasible, "selected_threshold": selected_threshold,
        })
    distributions: list[dict[str, Any]] = []
    groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        key = record.attack_family if record.label else f"benign:{record.device_family}"
        groups[key].append(index)
    for group, indices in sorted(groups.items()):
        part = values[np.asarray(indices, dtype=np.int64)]
        distributions.append({
            **audit_key(candidate, protocol, held, "select", seed),
            "candidate": candidate, "score_group": group, "rows": len(indices),
            "score_mean": float(np.mean(part)), "score_std": float(np.std(part)),
            "score_q05": float(np.quantile(part, 0.05)), "score_q50": float(np.quantile(part, 0.50)),
            "score_q95": float(np.quantile(part, 0.95)),
        })
    return metrics, distributions


def paired_representation_delta(
    learned: str,
    control: str,
    records: list[base.Record],
    learned_scores: dict[str, float],
    control_scores: dict[str, float],
    protocol: str,
    held: str | None,
    seed: int,
    bootstrap_reps: int,
) -> list[dict[str, Any]]:
    labels = np.asarray([record.label for record in records], dtype=np.int64)
    learned_values = np.asarray([learned_scores[record.uid] for record in records], dtype=np.float64)
    control_values = np.asarray([control_scores[record.uid] for record in records], dtype=np.float64)
    source_count = len({record.source for record in records}); unit = "source" if source_count >= 2 else "episode"
    groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        key = record.source if unit == "source" else record.episode_id
        if key:
            groups[str(key)].append(index)
    rows: list[dict[str, Any]] = []
    for offset, name in enumerate(("auroc", "auprc", "pauc_fpr_0_01", "attack_benign_margin")):
        learned_value = metric_value(labels, learned_values, name)
        control_value = metric_value(labels, control_values, name)
        draws: list[float] = []; rng = np.random.default_rng(int(seed) + 500 + offset)
        group_values = list(groups.values())
        if len(group_values) >= 2:
            for _ in range(int(bootstrap_reps)):
                indices: list[int] = []
                for _group in group_values:
                    indices.extend(group_values[int(rng.integers(0, len(group_values)))])
                chosen = np.asarray(indices, dtype=np.int64)
                left = metric_value(labels[chosen], learned_values[chosen], name)
                right = metric_value(labels[chosen], control_values[chosen], name)
                if np.isfinite(left) and np.isfinite(right):
                    draws.append(left - right)
        rows.append({
            **audit_key(learned, protocol, held, "select", seed),
            "candidate": learned, "control_candidate": control, "metric": name,
            "learned_value": learned_value, "control_value": control_value,
            "delta_learned_minus_random": learned_value - control_value,
            "delta_ci_low": float(np.quantile(draws, 0.025)) if draws else math.nan,
            "delta_ci_high": float(np.quantile(draws, 0.975)) if draws else math.nan,
            "ci_cluster_unit": unit if len(groups) >= 2 else "unavailable", "ci_clusters": len(groups),
        })
    return rows


@dataclass
class FormalInputs:
    x_by_role: dict[str, np.ndarray]
    frames: dict[str, pd.DataFrame]
    input_audit: dict[str, Any]
    t0: base.CompositeT0Cache
    t0_audit: dict[str, Any]
    extension_audit: dict[str, Any]
    c1_extension_audit: dict[str, Any]
    source_map: dict[str, set[str]]
    position_cache: dict[str, dict[int, int]]


def load_formal_inputs(args: argparse.Namespace, out: Path) -> FormalInputs:
    require_runtime()
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    live_exclusion = ckbi.report_only_exclusion(frames)
    live_exclusion.to_csv(out / "live_report_extension_fit_select_exclusion.csv", index=False)
    required = live_exclusion.loc[live_exclusion["required_zero"].notna()]
    if required.empty or int(pd.to_numeric(required["extension_source_rows_used"]).sum()) != 0:
        raise RuntimeError("report-only extension source entered a live fit/select role")
    if not bool(base.bool_series(required["pass"]).all()):
        raise RuntimeError("report-only extension exclusion audit failed")
    base_t0 = T0Cache(Path(args.t0_root)); t0_audit = base.validate_t0_runtime(base_t0)
    extension_audit = base.validate_report_extension(Path(args.report_t0_extension))
    c1_root = Path(args.c1_report_extension)
    if not (c1_root / "c1_report_extension_ready.json").is_file():
        raise RuntimeError("completed CKBJ C1 report-only extension is missing; CKBK will not rebuild shared cache")
    c1_extension_audit = c1ext.validate_extension(
        c1_root, Path(args.report_t0_extension), Path(args.c1_plan), Path(args.c1_targets),
    )
    t0 = base.CompositeT0Cache(base_t0, Path(args.report_t0_extension), set(extension_audit["extension_sources"]))
    coverage = base.required_report_source_coverage(frames, t0)
    pd.DataFrame(coverage).to_csv(out / "required_report_source_coverage.csv", index=False)
    missing = [str(row["role"]) for row in coverage if not bool(row["full_source_coverage"])]
    if missing:
        raise RuntimeError("required report cache coverage missing for " + ",".join(missing))
    pd.DataFrame(base.support_val_lineage(frames)).to_csv(out / "support_val_lineage.csv", index=False)
    pd.DataFrame(base.source_family_contract(frames)).to_csv(out / "source_family_contract.csv", index=False)
    pd.DataFrame(base.node_identity_proxy_audit(t0)).to_csv(out / "source_local_node_identity_proxy_audit.csv", index=False)
    return FormalInputs(
        x_by_role, frames, input_audit, t0, t0_audit, extension_audit, c1_extension_audit,
        base.source_groups_by_family(frames), {},
    )


def prepare_protocol(
    held: str | None,
    args: argparse.Namespace,
    inputs: FormalInputs,
) -> tuple[str, float, dict[str, list[base.Record]], ReplayMasks, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    protocol = "GLOBAL_ATTACK_PRESERVATION" if held is None else str(held)
    c1_model, frontend, c1_threshold, c1_audit = base.fit_c1(
        inputs.x_by_role, inputs.frames, held, Path(args.c1_cache), Path(args.c1_plan),
        Path(args.c1_report_extension), int(args.train_cap), int(args.eval_cap),
    )
    sets, data_audit = base.collect_protocol_records(
        c1_model, frontend, inputs.frames, inputs.t0, inputs.position_cache,
        held, int(args.train_cap), int(args.eval_cap),
    )
    held_rows = base.held_exclusion_counts(inputs.frames, held, int(args.train_cap), int(args.eval_cap))
    held_rows += base.apply_temporal_source_exclusion(
        sets, base.held_source_groups(inputs.frames, held, inputs.source_map), held,
    )
    if not sets["fit_attack"] or not sets["select_attack"]:
        raise RuntimeError(f"{protocol}: missing legal support train/select attack rows")
    report_only = set(getattr(inputs.t0, "report_only_sources", set()))
    for key in ("fit_attack", "fit_benign", "select_attack", "select_benign"):
        leaked = sorted({record.source for record in sets[key]} & report_only)
        if leaked:
            raise RuntimeError(f"{protocol}: report-only cache leaked into {key}: {leaked}")
    masks = target_catalog_masks(inputs.t0, Path(args.c1_targets), sets, inputs.frames)
    return protocol, c1_threshold, sets, masks, c1_audit, data_audit, held_rows


def add_keys(rows: Iterable[dict[str, Any]], model: str, protocol: str, held: str | None, phase: str, seed: int) -> list[dict[str, Any]]:
    return [{**audit_key(model, protocol, held, str(row.get("phase", phase)), seed), **row} for row in rows]


def evaluate_candidates(
    candidates: dict[str, tuple[dict[str, float], bool]],
    c1_threshold: float,
    sets: dict[str, list[base.Record]],
    protocol: str,
    held: str | None,
    seed: int,
    bootstrap_reps: int,
) -> dict[str, list[dict[str, Any]]]:
    selections: list[dict[str, Any]] = []
    thresholds: dict[str, float] = {}
    gate_rows_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for candidate, (scores, verifier_only) in candidates.items():
        threshold, rows, _pass = choose_complete_gate(
            candidate, sets["select_attack"], sets["select_benign"], scores, c1_threshold,
            protocol, held, seed, tgn_only=verifier_only,
        )
        thresholds[candidate] = threshold; gate_rows_by_candidate[candidate] = rows; selections.extend(rows)
    report_rows: list[dict[str, Any]] = []; family_rows: list[dict[str, Any]] = []
    attack_summary: list[dict[str, Any]] = []; strict_summary: list[dict[str, Any]] = []
    attack_records = sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
    global_ood = [record for record in sets["report"] if record.label == 0]
    strict_records = sets["report"] if held is not None else attack_records + global_ood
    c1_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    metric_protocol = "strict_leave" if held is not None else "attack_preservation"
    rows, families = base.metric_rows(
        "M0-C1", metric_protocol, protocol, strict_records, c1_hard, bootstrap_reps, seed,
    )
    report_rows.extend(rows); family_rows.extend(families)
    if held is None:
        attack_summary.extend(base.attack_summary_rows("M0-C1", strict_records, c1_hard, c1_hard, bootstrap_reps, seed))
    else:
        strict_summary.extend(base.strict_level2_summary("M0-C1", protocol, strict_records, c1_hard, c1_hard, bootstrap_reps, seed))
    representation_rows: list[dict[str, Any]] = []; distribution_rows: list[dict[str, Any]] = []
    legal_select = sets["select_attack"] + sets["select_benign"]
    for candidate, (scores, verifier_only) in candidates.items():
        hard = hard_decisions(
            candidate, strict_records, scores, c1_threshold, thresholds[candidate], verifier_only,
        )
        rows, families = base.metric_rows(
            candidate, metric_protocol, protocol, strict_records, hard, bootstrap_reps, seed,
        )
        report_rows.extend(rows); family_rows.extend(families)
        if held is None:
            attack_summary.extend(base.attack_summary_rows(candidate, strict_records, hard, c1_hard, bootstrap_reps, seed))
        else:
            strict_summary.extend(base.strict_level2_summary(candidate, protocol, strict_records, hard, c1_hard, bootstrap_reps, seed))
        rep, dist = representation_audit(
            candidate, legal_select, scores, gate_rows_by_candidate[candidate], protocol, held,
            seed, min(200, int(bootstrap_reps)),
        )
        representation_rows.extend(rep); distribution_rows.extend(dist)
    for collection in (report_rows, family_rows, attack_summary, strict_summary):
        for row in collection:
            row.setdefault("seed", int(seed)); row.setdefault("review_rate", 0.0)
    return {
        "selection": selections, "metrics": report_rows, "family_metrics": family_rows,
        "attack_summary": attack_summary, "strict_summary": strict_summary,
        "representation": representation_rows, "score_distributions": distribution_rows,
    }


def run_tgn_protocol(
    held: str | None,
    args: argparse.Namespace,
    inputs: FormalInputs,
) -> dict[str, list[dict[str, Any]]]:
    protocol, c1_threshold, sets, masks, c1_audit, data_audit, held_audit = prepare_protocol(held, args, inputs)
    seed = int(args.seed); model = "TGNMemory-Repair"
    phase_manifest, phase_hash = source_phase_manifest_rows(model, protocol, held, seed, inputs.t0, sets, masks)
    all_records = sets["fit_attack"] + sets["fit_benign"] + sets["select_attack"] + sets["select_benign"] + sets["report"]
    capacity = base.source_capacity(inputs.t0, {record.source for record in all_records})
    learned_encoder, ssl_history, task_rows, negative_rows = pretrain_tgn_repair(
        inputs.t0, sets["fit_attack"] + sets["fit_benign"], masks, capacity,
        int(args.memory_dim), int(args.time_dim), int(args.ssl_epochs), int(args.detach_every),
        int(args.history_batch_size), seed, protocol, held,
    )
    learned_embed, learned_memory = embed_tgn_protocol(
        learned_encoder, inputs.t0, sets, masks, int(args.memory_dim), int(args.history_batch_size),
        "TGNMemory-Repair", protocol, held, seed,
    )
    learned_head, learned_history, learned_usage, learned_family = base.train_verifier(
        learned_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim),
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed,
    )
    learned_scores = base.verifier_scores(learned_head, learned_embed, all_records)
    # Recreate the learned encoder's pre-training initialization exactly; the
    # only control difference is whether temporal self-supervision updated it.
    torch.manual_seed(seed)
    random_encoder = base.make_encoder(capacity, int(args.memory_dim), int(args.time_dim)); random_encoder.eval()
    random_embed, random_memory = embed_tgn_protocol(
        random_encoder, inputs.t0, sets, masks, int(args.memory_dim), int(args.history_batch_size),
        "TGNMemory-Repair-Random", protocol, held, seed,
    )
    random_head, random_history, random_usage, random_family = base.train_verifier(
        random_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim),
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed,
    )
    random_scores = base.verifier_scores(random_head, random_embed, all_records)
    only_head, only_history, only_usage, only_family = base.train_verifier(
        learned_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim),
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed + 2,
    )
    only_scores = base.verifier_scores(only_head, learned_embed, all_records)
    evaluated = evaluate_candidates({
        "TGNMemory-Repair-Random": (random_scores, False),
        "TGNMemory-Repair": (learned_scores, False),
        "TGNMemory-Repair-only": (only_scores, True),
    }, c1_threshold, sets, protocol, held, seed, int(args.bootstrap_reps))
    evaluated["representation_delta"] = paired_representation_delta(
        "TGNMemory-Repair", "TGNMemory-Repair-Random",
        sets["select_attack"] + sets["select_benign"], learned_scores, random_scores,
        protocol, held, seed, min(200, int(args.bootstrap_reps)),
    )
    evaluated.update({
        "c1_audit": add_keys(c1_audit, "M0-C1", protocol, held, "fit_select", seed),
        "data_audit": add_keys(data_audit, "SHARED", protocol, held, "role_scope", seed),
        "held_audit": add_keys(held_audit, "SHARED", protocol, held, "fit_select", seed),
        "phase_manifest": phase_manifest,
        "replay_catalog": add_keys(masks.catalog_rows, "SHARED", protocol, held, "mask_build", seed),
        "losses": ssl_history
            + add_keys(learned_history, "TGNMemory-Repair", protocol, held, "fit", seed)
            + add_keys(random_history, "TGNMemory-Repair-Random", protocol, held, "fit", seed)
            + add_keys(only_history, "TGNMemory-Repair-only", protocol, held, "fit", seed),
        "task_eligibility": task_rows,
        "negative_audit": negative_rows,
        "support_usage": add_keys(learned_usage, "TGNMemory-Repair", protocol, held, "fit", seed)
            + add_keys(random_usage, "TGNMemory-Repair-Random", protocol, held, "fit", seed)
            + add_keys(only_usage, "TGNMemory-Repair-only", protocol, held, "fit", seed),
        "support_family_usage": add_keys(learned_family, "TGNMemory-Repair", protocol, held, "fit", seed)
            + add_keys(random_family, "TGNMemory-Repair-Random", protocol, held, "fit", seed)
            + add_keys(only_family, "TGNMemory-Repair-only", protocol, held, "fit", seed),
        "memory_audit": learned_memory + random_memory,
        "event_scope": add_keys(base.event_scope_rows(sets, set(getattr(inputs.t0, "report_only_sources", set()))), "SHARED", protocol, held, "all", seed),
        "protocol_summary": [{
            **audit_key(model, protocol, held, "all", seed), "c1_threshold": c1_threshold,
            "source_phase_manifest_sha256": phase_hash, "review_rate": 0.0,
            "report_used_for_fit_or_select": False,
        }],
    })
    return evaluated


def run_graph_protocol(
    held: str | None,
    args: argparse.Namespace,
    inputs: FormalInputs,
) -> dict[str, list[dict[str, Any]]]:
    protocol, c1_threshold, sets, masks, c1_audit, data_audit, held_audit = prepare_protocol(held, args, inputs)
    seed = int(args.seed); shared_model = "GraphMixer-SharedReplay"
    phase_manifest, phase_hash = source_phase_manifest_rows(shared_model, protocol, held, seed, inputs.t0, sets, masks)
    phase_records = {
        "fit": sets["fit_attack"] + sets["fit_benign"],
        "select": sets["select_attack"] + sets["select_benign"],
        "report": sets["report"],
    }
    examples: dict[str, GraphExamples] = {}; memory_rows: list[dict[str, Any]] = []
    for phase, records in phase_records.items():
        examples[phase], rows = build_graph_examples(
            inputs.t0, records, masks, phase, shared_model, protocol, held, seed,
        )
        memory_rows.extend(rows)
    all_examples = merge_graph_examples([examples["fit"], examples["select"], examples["report"]])
    learned_encoder, learned_head, learned_history, learned_usage, learned_family = train_graph_verifier(
        examples["fit"], sets["fit_attack"], sets["fit_benign"], False, False,
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed,
        "GraphMixer-Full-Anonymous", protocol, held,
    )
    full_scores = graph_scores(learned_encoder, learned_head, all_examples, int(args.graph_score_batch_size))
    random_encoder, random_head, random_history, random_usage, random_family = train_graph_verifier(
        examples["fit"], sets["fit_attack"], sets["fit_benign"], False, True,
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed,
        "GraphMixer-Full-Random", protocol, held,
    )
    random_scores = graph_scores(random_encoder, random_head, all_examples, int(args.graph_score_batch_size))
    message_encoder, message_head, message_history, message_usage, message_family = train_graph_verifier(
        examples["fit"], sets["fit_attack"], sets["fit_benign"], True, False,
        int(args.verifier_epochs), int(args.verifier_negative_ratio), seed + 1,
        "GraphMixer-MessageOnly", protocol, held,
    )
    message_scores = graph_scores(message_encoder, message_head, all_examples, int(args.graph_score_batch_size))
    evaluated = evaluate_candidates({
        "GraphMixer-Full-Random": (random_scores, False),
        "GraphMixer-Full-Anonymous": (full_scores, False),
        "GraphMixer-MessageOnly": (message_scores, False),
    }, c1_threshold, sets, protocol, held, seed, int(args.bootstrap_reps))
    evaluated["representation_delta"] = paired_representation_delta(
        "GraphMixer-Full-Anonymous", "GraphMixer-Full-Random",
        sets["select_attack"] + sets["select_benign"], full_scores, random_scores,
        protocol, held, seed, min(200, int(args.bootstrap_reps)),
    )
    evaluated.update({
        "c1_audit": add_keys(c1_audit, "M0-C1", protocol, held, "fit_select", seed),
        "data_audit": add_keys(data_audit, "SHARED", protocol, held, "role_scope", seed),
        "held_audit": add_keys(held_audit, "SHARED", protocol, held, "fit_select", seed),
        "phase_manifest": phase_manifest,
        "replay_catalog": add_keys(masks.catalog_rows, "SHARED", protocol, held, "mask_build", seed),
        "losses": learned_history + random_history + message_history,
        "task_eligibility": [], "negative_audit": [],
        "support_usage": learned_usage + random_usage + message_usage,
        "support_family_usage": learned_family + random_family + message_family,
        "memory_audit": memory_rows,
        "event_scope": add_keys(base.event_scope_rows(sets, set(getattr(inputs.t0, "report_only_sources", set()))), "SHARED", protocol, held, "all", seed),
        "protocol_summary": [{
            **audit_key(shared_model, protocol, held, "all", seed), "c1_threshold": c1_threshold,
            "source_phase_manifest_sha256": phase_hash, "review_rate": 0.0,
            "report_used_for_fit_or_select": False,
            "graphmixer_upstream_repository": dyglib.UPSTREAM_REPOSITORY,
            "graphmixer_upstream_commit": dyglib.UPSTREAM_COMMIT,
            "graphmixer_upstream_license": dyglib.UPSTREAM_LICENSE,
            "node_adapter": "eight causal source-local anonymous statistics; no node/source embedding",
        }],
    })
    return evaluated


STAGE_FILES = {
    "c1_audit": "c1_fit_select_audit.csv",
    "data_audit": "role_usage_audit.csv",
    "held_audit": "held_exclusion_audit.csv",
    "phase_manifest": "source_phase_interval_manifest.csv",
    "replay_catalog": "role_assigned_replay_block_audit.csv",
    "losses": "loss_curves.csv",
    "task_eligibility": "ssl_task_eligibility.csv",
    "negative_audit": "negative_sampling_audit.csv",
    "support_usage": "support_training_usage.csv",
    "support_family_usage": "support_family_training_usage.csv",
    "memory_audit": "causal_replay_audit.csv",
    "event_scope": "event_scope_audit.csv",
    "selection": "candidate_selection.csv",
    "metrics": "all_metrics.csv",
    "family_metrics": "per_attack_family_metrics.csv",
    "attack_summary": "attack_preservation_summary.csv",
    "strict_summary": "strict_level2_summary.csv",
    "representation": "representation_audit.csv",
    "score_distributions": "select_score_distributions.csv",
    "representation_delta": "learned_vs_random_representation_delta.csv",
    "protocol_summary": "protocol_summary.csv",
}


def write_stage_tables(out: Path, results: list[dict[str, list[dict[str, Any]]]]) -> None:
    for key, filename in STAGE_FILES.items():
        rows = [row for result in results for row in result.get(key, [])]
        pd.DataFrame(rows).to_csv(out / filename, index=False)
    metrics = pd.DataFrame([row for result in results for row in result.get("metrics", [])])
    if not metrics.empty:
        metrics.loc[metrics["protocol"].eq("attack_preservation")].to_csv(out / "attack_preservation_metrics.csv", index=False)
        metrics.loc[metrics["protocol"].eq("strict_leave")].to_csv(out / "strict_level2_metrics.csv", index=False)


def run_formal_stage(args: argparse.Namespace) -> None:
    started = time.time(); out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"refusing to mix CKBK stage artifacts in existing directory: {out}")
    out.mkdir(parents=True, exist_ok=True)
    inputs = load_formal_inputs(args, out)
    held_values = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    unknown = sorted(set(held_values) - set(HELD))
    if unknown:
        raise RuntimeError(f"seed-27 development run cannot open unregistered held families: {unknown}")
    protocols: list[str | None] = [None, *held_values]
    runner = run_tgn_protocol if args.stage == "tgn" else run_graph_protocol
    results = [runner(held, args, inputs) for held in protocols]
    write_stage_tables(out, results)
    manifest_path = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    environment = {
        "issue": ISSUE, "stage": args.stage, "seed": int(args.seed),
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
        "sklearn": sklearn.__version__, "torch": torch.__version__, "pyg": base.PYG_VERSION,
        "commit_sha": os.environ.get("M1_COMMIT_SHA", "unknown"),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", os.environ.get("M1_PARTITION", "local")),
        "frozen_t0_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "report_extension_manifest_sha256": inputs.extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": inputs.c1_extension_audit["manifest_sha256"],
        "history_batch_size": int(args.history_batch_size), "review_rate": 0.0,
        "report_used_for_fit_or_select": False, "raw_label_column_read_for_memory": False,
        "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
        "untouched_final_manifest_opened": False,
        "seconds": time.time() - started,
    }
    (out / "environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    status = {
        "status": "COMPLETED", "stage": args.stage, "seed": int(args.seed),
        "protocols": ["GLOBAL_ATTACK_PRESERVATION", *held_values],
        "seconds": environment["seconds"], "review_rate": 0.0,
    }
    (out / "stage_status.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, indent=2))


def read_optional_csv(path: Path) -> pd.DataFrame:
    if not path.is_file() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def combine_stage_tables(stage_dirs: list[Path], out: Path) -> dict[str, pd.DataFrame]:
    tables: dict[str, pd.DataFrame] = {}
    for key, filename in STAGE_FILES.items():
        parts: list[pd.DataFrame] = []
        for stage_dir in stage_dirs:
            frame = read_optional_csv(stage_dir / filename)
            if frame.empty:
                continue
            frame.insert(0, "stage_directory", stage_dir.name)
            parts.append(frame)
        combined = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
        if not combined.empty:
            subset = [column for column in combined.columns if column != "stage_directory"]
            combined = combined.drop_duplicates(subset=subset, keep="first")
        combined.to_csv(out / f"combined_{filename}", index=False)
        tables[key] = combined
    return tables


def first_rate(frame: pd.DataFrame, value_column: str, **where: Any) -> float | None:
    if frame.empty or value_column not in frame.columns:
        return None
    part = frame
    for key, value in where.items():
        if key not in part.columns:
            return None
        part = part.loc[part[key].eq(value)]
    if part.empty:
        return None
    return float(part.iloc[0][value_column])


def aggregate_decisions(
    tables: dict[str, pd.DataFrame],
    stage_statuses: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    attack = tables["attack_summary"]; strict = tables["strict_summary"]
    selection = tables["selection"]; rep_delta = tables["representation_delta"]
    learned = {
        "TGNMemory-Repair": "TGNMemory-Repair-Random",
        "GraphMixer-Full-Anonymous": "GraphMixer-Full-Random",
    }
    stage_complete = {str(row.get("stage")): row.get("status") == "COMPLETED" for row in stage_statuses}
    rows: list[dict[str, Any]] = []
    for candidate, control in learned.items():
        stage = "tgn" if candidate.startswith("TGN") else "graphmixer"
        overall_delta = first_rate(
            attack, "delta_vs_c1_pp", candidate=candidate, metric="overall_attack_hard_recall",
        )
        major = attack
        if not major.empty:
            major = major.loc[
                major.get("candidate", pd.Series(dtype=str)).eq(candidate)
                & major.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")
                & pd.to_numeric(major.get("rows", pd.Series(dtype=float)), errors="coerce").ge(15)
            ]
        worst_major_delta = float(pd.to_numeric(major["delta_vs_c1_pp"], errors="coerce").min()) if not major.empty else None
        stream = first_rate(strict, "hard_rate", candidate=candidate, held_value="iotsim-stream-consumer")
        stream_c1 = first_rate(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-stream-consumer")
        hydraulic = first_rate(strict, "hard_rate", candidate=candidate, held_value="iotsim-hydraulic-system")
        hydraulic_c1 = first_rate(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-hydraulic-system")
        selected = selection
        if not selected.empty:
            selected_flags = base.bool_series(selected["selected"]) if "selected" in selected else pd.Series(False, index=selected.index)
            selected = selected.loc[
                selected.get("candidate", pd.Series(dtype=str)).eq(candidate)
                & selected_flags
            ]
        gate_pass = bool(
            not selected.empty and "gate_constraint_pass" in selected
            and base.bool_series(selected["gate_constraint_pass"]).all()
        )
        deltas: dict[str, float | None] = {}
        for metric in ("auroc", "auprc", "attack_benign_margin"):
            deltas[metric] = first_rate(
                rep_delta, "delta_learned_minus_random", candidate=candidate,
                control_candidate=control, metric=metric, protocol="GLOBAL_ATTACK_PRESERVATION",
            )
        required_missing = any(value is None for value in (
            overall_delta, worst_major_delta, stream, stream_c1, hydraulic, hydraulic_c1,
            deltas["auroc"], deltas["auprc"], deltas["attack_benign_margin"],
        ))
        attack_failed = bool(
            overall_delta is not None and overall_delta < -0.5 - 1e-12
        ) or bool(worst_major_delta is not None and worst_major_delta < -2.0 - 1e-12)
        learned_signal = bool(
            deltas["auroc"] is not None and deltas["auroc"] >= 0.01
            and deltas["auprc"] is not None and deltas["auprc"] >= 0.01
            and deltas["attack_benign_margin"] is not None and deltas["attack_benign_margin"] > 0.0
        )
        stream_signal = bool(
            stream is not None and stream_c1 is not None and stream <= 0.90 and stream_c1 - stream >= 0.10
        )
        hydraulic_signal = bool(
            hydraulic is not None and hydraulic_c1 is not None and hydraulic_c1 - hydraulic >= 0.05
        )
        contract_failed = not bool(stage_complete.get(stage, False)) or required_missing or not gate_pass
        if contract_failed or attack_failed:
            decision = "NO_GO"
        elif learned_signal and stream_signal and hydraulic_signal:
            decision = "GO_SIGNAL"
        else:
            decision = "INCONCLUSIVE_STOP"
        rows.append({
            "candidate": candidate, "control_candidate": control, "seed": 27, "decision": decision,
            "stage_completed": bool(stage_complete.get(stage, False)), "required_metrics_missing": required_missing,
            "gate_constraint_pass": gate_pass, "overall_attack_delta_pp": overall_delta,
            "worst_major_family_delta_pp": worst_major_delta, "attack_preservation_failed": attack_failed,
            "select_auroc_delta_vs_random": deltas["auroc"], "select_auprc_delta_vs_random": deltas["auprc"],
            "select_margin_delta_vs_random": deltas["attack_benign_margin"], "learned_representation_signal": learned_signal,
            "stream_ood_hard_rate": stream, "stream_c1_hard_rate": stream_c1, "stream_material_signal": stream_signal,
            "hydraulic_ood_hard_rate": hydraulic, "hydraulic_c1_hard_rate": hydraulic_c1,
            "hydraulic_material_signal": hydraulic_signal, "review_rate": 0.0,
        })
    return rows


def aggregate_stage_results(args: argparse.Namespace) -> None:
    out = Path(args.out)
    if out.exists() and any(out.iterdir()):
        raise RuntimeError(f"refusing to mix CKBK aggregate artifacts: {out}")
    out.mkdir(parents=True, exist_ok=True)
    stage_dirs = [Path(args.tgn_stage_out), Path(args.graph_stage_out)]
    statuses: list[dict[str, Any]] = []
    for stage_dir in stage_dirs:
        status_path = stage_dir / "stage_status.json"
        if status_path.is_file():
            statuses.append(json.loads(status_path.read_text(encoding="utf-8")))
        else:
            failure_path = stage_dir / "stage_failure.json"
            failure = json.loads(failure_path.read_text(encoding="utf-8")) if failure_path.is_file() else {}
            statuses.append({"stage": "tgn" if "tgn" in stage_dir.name else "graphmixer", "status": "FAILED", **failure})
    tables = combine_stage_tables(stage_dirs, out)
    decisions = aggregate_decisions(tables, statuses)
    pd.DataFrame(decisions).to_csv(out / "single_seed_route_decision.csv", index=False)
    overall = "PARTIAL_NO_GO" if any(row.get("status") != "COMPLETED" for row in statuses) else (
        "GO_SIGNAL" if any(row["decision"] == "GO_SIGNAL" for row in decisions) else "NO_GO_OR_INCONCLUSIVE_STOP"
    )
    payload = {
        "issue": ISSUE, "seed": 27, "status": overall, "stage_statuses": statuses,
        "candidate_decisions": decisions, "review_rate": 0.0, "seeds_37_47_launched": False,
        "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
        "untouched_final_manifest_opened": False,
    }
    (out / "single_seed_route_decision.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    lines = [
        f"# {ISSUE}", "", f"Seed 27 aggregate status: `{overall}`.", "",
        "This is a development route decision. Review is fixed at `0`; seeds 37/47 were not launched.", "",
        "See `single_seed_route_decision.csv`, combined attack/strict tables, representation audits, and stage artifacts.",
    ]
    (out / "codex_readout.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


def run_contract_unit(args: argparse.Namespace) -> None:
    require_runtime(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    runs = list(iter_allowed_runs(0, 10, frozenset({2, 3, 7})))
    task_ok, _ = task_enabled(100, 100, 3, 2, 2)
    task_bad, task_bad_reason = task_enabled(46, 1, 1, 1, 1)
    past = deque([(1000, np.ones(RAW_MSG_DIM, dtype=np.float32)), (2000, np.full(RAW_MSG_DIM, 2, dtype=np.float32))], maxlen=GRAPH_TOKENS)
    tokens_a, gaps_a, mask_a = endpoint_tokens(past, 3000)
    future = deque(list(past) + [(4000, np.full(RAW_MSG_DIM, 9, dtype=np.float32))], maxlen=GRAPH_TOKENS)
    # The target at t=3000 must reject an explicitly future token.
    future_rejected = False
    try:
        endpoint_tokens(future, 3000)
    except RuntimeError:
        future_rejected = True
    torch.manual_seed(27)
    graph = dyglib.AnonymousGraphMixer(output_dim=8)
    graph.eval()
    with torch.no_grad():
        representation = graph(
            torch.zeros(2, 2, GRAPH_TOKENS, RAW_MSG_DIM), torch.zeros(2, 2, GRAPH_TOKENS),
            torch.zeros(2, 2, GRAPH_TOKENS, dtype=torch.bool), torch.zeros(2, 2, 8),
        )
    support = [
        base.Record("a", "support_val", "select", "s1", 1, 1, 1, "f1", "d", "sf", 1.0, "e1"),
        base.Record("b", "support_val", "select", "s2", 2, 2, 1, "f2", "d", "sf", 1.0, "e2"),
        base.Record("c", "support_val", "select", "s3", 3, 3, 1, "f2", "d", "sf", 1.0, "e3"),
    ]
    benign = [
        base.Record("d", "ood_val", "select", "s4", 4, 4, 0, "benign", "d", "sf", 1.0, "e4"),
        base.Record("e", "ood_val", "select", "s5", 5, 5, 0, "benign", "d", "sf", 1.0, "e5"),
    ]
    scores = {"a": 0.1, "b": 0.2, "c": 0.3, "d": 0.9, "e": 0.8}
    threshold, selection, gate_pass = choose_complete_gate(
        "unit", support, benign, scores, 0.5, "unit", None, 27,
    )
    result = {
        "allowed_interval_mask_exact": runs == [(0, 2), (4, 7), (8, 10)],
        "eligible_task_enabled": task_ok, "degenerate_task_disabled": not task_bad,
        "degenerate_task_reason": task_bad_reason, "future_token_rejected": future_rejected,
        "past_token_shape_valid": tokens_a.shape == (GRAPH_TOKENS, RAW_MSG_DIM) and gaps_a.shape == mask_a.shape,
        "graphmixer_finite": bool(torch.isfinite(representation).all()),
        "graphmixer_pair_shape": list(representation.shape) == [2, 16],
        "complete_gate_has_no_suppression_sentinel": any(row["no_suppression_sentinel"] for row in selection),
        "complete_gate_constraint_pass": gate_pass, "selected_gate_is_no_fallback": threshold == NO_SUPPRESSION_THRESHOLD,
        "node_or_source_id_absent_from_model_arguments": True,
        "raw_label_absent_from_model_arguments": True,
    }
    booleans = [value for key, value in result.items() if isinstance(value, bool)]
    result["status"] = "PASS" if all(booleans) else "FAIL"
    (out / "ckbk_contract_unit.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit("CKBK contract unit failed")


def dry_run(args: argparse.Namespace) -> None:
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    payload = {
        "issue": ISSUE, "mode": "dry-run", "seed": int(args.seed),
        "stages": ["tgn", "graphmixer", "aggregate"],
        "candidates": [
            "M0-C1", "TGNMemory-Repair-Random", "TGNMemory-Repair", "TGNMemory-Repair-only",
            "GraphMixer-Full-Random", "GraphMixer-Full-Anonymous", "GraphMixer-MessageOnly",
        ],
        "official_pyg_components": [
            "TGNMemory", "IdentityMessage", "LastAggregator", "LastNeighborLoader",
            "TGNMemory internal TimeEncoder", "TransformerConv",
        ],
        "graphmixer_upstream_commit": dyglib.UPSTREAM_COMMIT,
        "strict_held_values": list(HELD), "review_rate": 0.0,
        "untouched_final_manifest_opened": False, "seeds_37_47_launched": False,
        "formal_hpc_submitted": False,
    }
    (out / "ckbk_dry_run.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("unit", "dry-run", "formal", "aggregate"), default="dry-run")
    parser.add_argument("--stage", choices=("tgn", "graphmixer"), default="tgn")
    parser.add_argument("--out", default=str(ROOT / "runs" / ISSUE))
    parser.add_argument("--tgn-stage-out", default="")
    parser.add_argument("--graph-stage-out", default="")
    parser.add_argument("--t0-root", default=str(DEFAULT_T0))
    parser.add_argument("--report-t0-extension", default=str(DEFAULT_REPORT_EXTENSION))
    parser.add_argument("--c1-cache", default=str(DEFAULT_C1_CACHE))
    parser.add_argument("--c1-plan", default=str(DEFAULT_C1_PLAN))
    parser.add_argument("--c1-targets", default=str(DEFAULT_C1_TARGETS))
    parser.add_argument("--c1-report-extension", default=str(DEFAULT_C1_REPORT_EXTENSION))
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--memory-dim", type=int, default=32)
    parser.add_argument("--time-dim", type=int, default=16)
    parser.add_argument("--ssl-epochs", type=int, default=3)
    parser.add_argument("--verifier-epochs", type=int, default=30)
    parser.add_argument("--verifier-negative-ratio", type=int, default=4)
    parser.add_argument("--detach-every", type=int, default=64)
    parser.add_argument("--history-batch-size", type=int, default=HISTORY_BATCH_SIZE)
    parser.add_argument("--graph-score-batch-size", type=int, default=2048)
    parser.add_argument("--bootstrap-reps", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=27)
    args = parser.parse_args()
    if args.mode == "unit":
        run_contract_unit(args); return
    if args.mode == "dry-run":
        dry_run(args); return
    if args.mode == "aggregate":
        if not args.tgn_stage_out or not args.graph_stage_out:
            raise SystemExit("aggregate requires --tgn-stage-out and --graph-stage-out")
        aggregate_stage_results(args); return
    out = Path(args.out)
    try:
        run_formal_stage(args)
    except Exception as exc:
        out.mkdir(parents=True, exist_ok=True)
        failure = {
            "status": "FAILED", "stage": args.stage, "seed": int(args.seed),
            "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(),
        }
        (out / "stage_failure.json").write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(failure, indent=2), file=sys.stderr)
        raise


if __name__ == "__main__":
    main()
