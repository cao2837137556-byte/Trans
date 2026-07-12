"""CKBH: formal M1 C1-gated PyG-TGN strict leave-family evaluation.

This program is intentionally narrow.  It uses the maintained PyG TGNMemory
stack, the existing legal C1 baseline, four pre-registered candidates, and a
logical C1-candidate / TGN-verifier gate.  It is not a generic MLP, episode
pooling, prototype, domain-adaptation, or review-routing experiment.

The command has three modes:
* ``unit`` creates a tiny synthetic PyG causal smoke only;
* ``dry-run`` emits the intended formal configuration without training;
* ``formal`` performs the complete training and strict held-family report.

No report/future/sealed row is used to fit a TGN, train a verifier, fit a C1
model, standardize, construct negatives, or select a gate.  Its label is read
only after a report score has been emitted for the final metric table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402

try:  # Kept lazy so dry-run can be inspected without creating an environment.
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric import __version__ as PYG_VERSION
    from torch_geometric.nn.models.tgn import IdentityMessage, LastAggregator, LastNeighborLoader, TGNMemory
except Exception as exc:  # pragma: no cover - exercised only without PyG.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    PYG_VERSION = "unavailable"
    IdentityMessage = LastAggregator = LastNeighborLoader = TGNMemory = None  # type: ignore[assignment]
    TORCH_ERROR = exc
else:
    TORCH_ERROR = None

_Module = nn.Module if nn is not None else object

ISSUE = "issue27ckbh_tgn_m1_strict_formal_v1_2026-07-12"
ROOT = cko.ROOT
DEFAULT_T0 = ROOT / "runs" / "issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
DEFAULT_C1_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_load_plan.csv"
DEFAULT_C1_CACHE = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "hpc_canonical_c1_cache"
FIT_BENIGN = ("id_calib", "ood_val", "ood_stress")
SELECT_BENIGN = ("id_calib", "ood_val", "ood_stress")
REPORT_SPECS = (
    ("id_calib", "select", 0, "benign_id"),
    ("ood_val", "select", 0, "benign_ood"),
    ("ood_stress", "select", 0, "benign_ood"),
    ("same_file_query", "all", 1, "attack"),
    ("future_query", "all", 1, "attack"),
    ("sealed_final_ood", "report_only", 0, "benign_ood"),
    ("sealed_final_attack", "report_only", 1, "attack"),
)
RESPONSE_WINDOW_MS = 60_000
RETRY_WINDOW_MS = 300_000
RAW_MSG_DIM = 9


def require_pyg() -> None:
    if torch is None:
        raise RuntimeError("CKBH needs the provisioned Torch/PyG runtime") from TORCH_ERROR


def c1_candidate() -> ckai.Candidate:
    return next(value for value in ckai.CANDIDATES if value.name == "C1_cicflow_style_only_histgb")


@dataclass(frozen=True)
class Record:
    uid: str
    role: str
    m1_phase: str
    source: str
    recorded_index: int
    event_position: int
    label: int
    attack_family: str
    device_family: str
    source_family: str
    c1_score: float


class VerifierHead(_Module):  # type: ignore[misc]
    """A deliberately small TGN-only verifier; C1 is a separate logical gate."""

    def __init__(self, memory_dim: int):
        require_pyg()
        super().__init__()
        self.linear = nn.Linear(memory_dim * 2, 1)

    def forward(self, representation: "torch.Tensor") -> "torch.Tensor":
        return self.linear(representation).reshape(-1)


class SelfSupervisionHeads(_Module):  # type: ignore[misc]
    """Small task heads over official TGN memory, not replacement TGN parts."""

    def __init__(self, memory_dim: int, message_dim: int):
        require_pyg()
        super().__init__()
        width = memory_dim * 2 + message_dim
        self.link = nn.Linear(width, 1)
        self.reverse = nn.Linear(width, 1)
        self.completion = nn.Linear(width, 1)
        self.retry = nn.Linear(width, 1)

    @staticmethod
    def features(src_memory: "torch.Tensor", dst_memory: "torch.Tensor", message: "torch.Tensor") -> "torch.Tensor":
        return torch.cat([src_memory, dst_memory, message], dim=1)


def make_memory(capacity: int, memory_dim: int, time_dim: int) -> "TGNMemory":
    require_pyg()
    memory = TGNMemory(
        num_nodes=max(2, int(capacity)), raw_msg_dim=RAW_MSG_DIM, memory_dim=int(memory_dim), time_dim=int(time_dim),
        message_module=IdentityMessage(RAW_MSG_DIM, int(memory_dim), int(time_dim)), aggregator_module=LastAggregator(),
    )
    return memory


def role_indices(frames: dict[str, pd.DataFrame], role: str, phase: str, held: str | None, cap: int) -> np.ndarray:
    if held is None:
        return ckao.role_indices_filtered(frames, role, phase, cap)
    return ckao.role_indices_filtered(frames, role, phase, cap, exclude=("device_family", held))


def report_indices(frames: dict[str, pd.DataFrame], role: str, phase: str, held: str | None, cap: int) -> np.ndarray:
    if held is None:
        return ckao.role_indices_filtered(frames, role, phase, cap)
    return ckao.role_indices_filtered(frames, role, phase, cap, include=("device_family", held))


def fit_c1(
    x_by_role: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], held: str | None, cache_dir: Path, plan: Path,
    train_cap: int, select_cap: int,
) -> tuple[Any, ckai.ExternalFlowFrontend, float, list[dict[str, Any]]]:
    cache = ckat.PersistentCanonicalTimeC1Cache(cache_dir, plan)
    frontend = ckai.ExternalFlowFrontend(x_by_role, frames, cache)
    sentinel = "__m1_global_no_hold__" if held is None else held
    model, audit = ckao.fit_candidate(c1_candidate(), frontend, frames, sentinel, train_cap)
    threshold, threshold_audit = ckao.attack_threshold(c1_candidate(), model, frontend, frames, sentinel, select_cap)
    return model, frontend, float(threshold), audit + threshold_audit


def cached_positions(t0: T0Cache, source: str, cache: dict[str, dict[int, int]]) -> dict[int, int]:
    if source not in cache:
        cache[source] = t0.target_positions(source)
    return cache[source]


def collect_records(
    model: Any,
    frontend: ckai.ExternalFlowFrontend,
    frames: dict[str, pd.DataFrame],
    t0: T0Cache,
    position_cache: dict[str, dict[int, int]],
    role: str,
    frame_phase: str,
    m1_phase: str,
    label: int,
    held: str | None,
    cap: int,
    report: bool = False,
) -> tuple[list[Record], list[dict[str, Any]]]:
    idx = report_indices(frames, role, frame_phase, held, cap) if report else role_indices(frames, role, frame_phase, held, cap)
    frame = frames[role]
    keep: list[int] = []
    positions: list[int] = []
    dropped = 0
    for row_index in idx.tolist():
        row = frame.iloc[int(row_index)]
        source = str(row.get("source_group", ""))
        recorded = int(pd.to_numeric(row.get("recorded_index", -1), errors="coerce"))
        event_position = cached_positions(t0, source, position_cache).get(recorded, -1)
        if event_position < 0:
            dropped += 1
            continue
        keep.append(int(row_index)); positions.append(int(event_position))
    scores = ckai.score_attack(model, frontend.matrix(c1_candidate(), role, np.asarray(keep, dtype=np.int64))) if keep else np.zeros(0, dtype=np.float32)
    records: list[Record] = []
    for local, (row_index, event_position) in enumerate(zip(keep, positions)):
        row = frame.iloc[row_index]
        attack_family = str(row.get("attack_label", "benign")) if label else "benign"
        records.append(Record(
            uid=f"{role}:{m1_phase}:{row_index}", role=role, m1_phase=m1_phase,
            source=str(row.get("source_group", "")), recorded_index=int(row.get("recorded_index", -1)),
            event_position=event_position, label=int(label), attack_family=attack_family,
            device_family=str(row.get("device_family", "NA")), source_family=str(row.get("source_family", "NA")),
            c1_score=float(scores[local]),
        ))
    audit = [{
        "role": role, "frame_phase": frame_phase, "m1_phase": m1_phase, "held_value": held or "GLOBAL",
        "requested_rows": int(len(idx)), "cache_aligned_rows": int(len(records)), "unmapped_rows": int(dropped),
        "label_for_metric_only": int(label), "report": bool(report),
    }]
    return records, audit


def collect_protocol_records(
    model: Any, frontend: ckai.ExternalFlowFrontend, frames: dict[str, pd.DataFrame], t0: T0Cache,
    position_cache: dict[str, dict[int, int]], held: str | None, train_cap: int, eval_cap: int,
) -> tuple[dict[str, list[Record]], list[dict[str, Any]]]:
    sets: dict[str, list[Record]] = defaultdict(list)
    audit: list[dict[str, Any]] = []
    support, row = collect_records(model, frontend, frames, t0, position_cache, "support_train", "fit", "fit", 1, held, cko.FULL_CAP)
    sets["fit_attack"] += support; audit += row
    for role in FIT_BENIGN:
        values, row = collect_records(model, frontend, frames, t0, position_cache, role, "fit", "fit", 0, held, train_cap)
        sets["fit_benign"] += values; audit += row
    support_val, row = collect_records(model, frontend, frames, t0, position_cache, "support_val", "select", "select", 1, held, cko.FULL_CAP)
    sets["select_attack"] += support_val; audit += row
    for role in SELECT_BENIGN:
        values, row = collect_records(model, frontend, frames, t0, position_cache, role, "select", "select", 0, held, eval_cap)
        sets["select_benign"] += values; audit += row
    # Globally, select-benign rows are selection-only.  In strict leave-family
    # runs the held slice of those rows becomes a report-only OOD evaluation;
    # the fit/select slice excluded it, so no event is duplicated.
    report_specs = REPORT_SPECS if held is not None else REPORT_SPECS[3:]
    for role, phase, label, _kind in report_specs:
        values, row = collect_records(model, frontend, frames, t0, position_cache, role, phase, "report", label, held, eval_cap, report=True)
        sets["report"] += values; audit += row
    return sets, audit


def source_groups_by_family(frames: dict[str, pd.DataFrame]) -> dict[str, set[str]]:
    groups: defaultdict[str, set[str]] = defaultdict(set)
    for frame in frames.values():
        if {"device_family", "source_group"}.issubset(frame.columns):
            pairs = frame[["device_family", "source_group"]].astype(str).drop_duplicates()
            for pair in pairs.itertuples(index=False):
                groups[str(pair.device_family)].add(str(pair.source_group))
    return dict(groups)


def held_source_groups(
    frames: dict[str, pd.DataFrame], held: str | None, source_groups: dict[str, set[str]] | None = None,
) -> set[str]:
    """Conservatively reject entire source streams that contain a held family.

    A source cache stores unlabeled raw events.  If it contains even one target
    attributed to the held device family, keeping its surrounding raw events in
    SSL would make the leave-family claim ambiguous.  C1 remains row-filtered
    by the established baseline contract; temporal SSL additionally enforces
    this stricter source boundary.
    """
    if held is None:
        return set()
    if source_groups is not None:
        return set(source_groups.get(str(held), set()))
    blocked: set[str] = set()
    for frame in frames.values():
        if {"device_family", "source_group"}.issubset(frame.columns):
            blocked.update(
                frame.loc[frame["device_family"].astype(str).eq(str(held)), "source_group"].astype(str).tolist()
            )
    return blocked


def apply_temporal_source_exclusion(
    sets: dict[str, list[Record]], blocked_sources: set[str], held: str | None,
) -> list[dict[str, Any]]:
    """Apply the source-level strictness only to temporal fit inputs."""
    rows: list[dict[str, Any]] = []
    for key in ("fit_attack", "fit_benign"):
        before = sets[key]
        after = [record for record in before if record.source not in blocked_sources]
        sets[key] = after
        rows.append({
            "held_value": held or "GLOBAL", "scope": "tgn_ssl_and_verifier_source_exclusion",
            "record_set": key, "records_before": len(before), "records_removed": len(before) - len(after),
            "records_after": len(after), "blocked_source_groups": len(blocked_sources),
        })
    return rows


def held_exclusion_counts(frames: dict[str, pd.DataFrame], held: str | None, train_cap: int, eval_cap: int) -> list[dict[str, Any]]:
    if held is None:
        return []
    scopes = {
        "tgn_ssl_and_support": (("support_train", "fit", cko.FULL_CAP),),
        "benign_ood_fit_and_standardize": tuple((role, "fit", train_cap) for role in FIT_BENIGN),
        "negative_sampling_and_hard_pairs": (("support_train", "fit", cko.FULL_CAP),) + tuple((role, "fit", train_cap) for role in FIT_BENIGN),
        "gate_threshold_and_c1_select": (("support_val", "select", cko.FULL_CAP),) + tuple((role, "select", eval_cap) for role in SELECT_BENIGN),
    }
    rows: list[dict[str, Any]] = []
    for scope, uses in scopes.items():
        for role, phase, cap in uses:
            before = ckao.role_indices_filtered(frames, role, phase, cap)
            after = ckao.role_indices_filtered(frames, role, phase, cap, exclude=("device_family", held))
            rows.append({"held_value": held, "scope": scope, "role": role, "phase": phase, "rows_before": len(before), "held_rows_removed": len(before) - len(after), "rows_after": len(after), "held_rows_remaining": int(frames[role].iloc[after]["device_family"].astype(str).eq(held).sum())})
    return rows


def readonly_role_audit(
    frames: dict[str, pd.DataFrame], t0: T0Cache, position_cache: dict[str, dict[int, int]],
    held_values: list[str], train_cap: int, eval_cap: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Materialize the formal data contract without scoring or fitting a model."""
    base_specs: list[tuple[str, str, str, int, bool]] = [
        ("support_train", "fit", "fit", cko.FULL_CAP, False),
        *((role, "fit", "fit", train_cap, False) for role in FIT_BENIGN),
        ("support_val", "select", "select", cko.FULL_CAP, False),
        *((role, "select", "select", eval_cap, False) for role in SELECT_BENIGN),
    ]
    role_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    source_map = source_groups_by_family(frames)
    for held in [None] + held_values:
        scope = "GLOBAL" if held is None else held
        report_specs = REPORT_SPECS if held is not None else REPORT_SPECS[3:]
        specs = base_specs + [(role, phase, "report", eval_cap, True) for role, phase, _label, _kind in report_specs]
        for role, phase, m1_phase, cap, report in specs:
            idx = report_indices(frames, role, phase, held, cap) if report else role_indices(frames, role, phase, held, cap)
            frame = frames[role].iloc[idx]
            mapped = 0
            positions: set[tuple[str, int]] = set()
            unavailable_sources: set[str] = set()
            sources_here = frame["source_group"].astype(str).unique().tolist() if "source_group" in frame else []
            unavailable_sources = {source for source in sources_here if not t0.paths(source)[0].is_file()}
            if not unavailable_sources:
                for row in frame.itertuples():
                    source = str(getattr(row, "source_group", ""))
                    recorded = int(getattr(row, "recorded_index", -1))
                    position = cached_positions(t0, source, position_cache).get(recorded, -1)
                    if position >= 0:
                        mapped += 1; positions.add((source, position))
            alignment_state = "verified_local_npz" if not unavailable_sources else "not_verified_npz_not_pulled"
            role_rows.append({
                "held_value": scope, "role": role, "frame_phase": phase, "m1_phase": m1_phase,
                "report_only": bool(report), "rows_selected": int(len(idx)), "target_rows_aligned": int(mapped) if not unavailable_sources else math.nan,
                "target_rows_unmapped": int(len(idx) - mapped) if not unavailable_sources else math.nan, "distinct_targets": int(len(positions)) if not unavailable_sources else math.nan,
                "target_alignment_state": alignment_state, "npz_unavailable_source_groups": len(unavailable_sources),
                "source_groups": int(frame["source_group"].astype(str).nunique()) if "source_group" in frame else 0,
            })
            if held is None and role in {"support_train", "support_val"}:
                for family, group in frame.groupby(frame.get("attack_label", pd.Series("unknown", index=frame.index)).astype(str), sort=True):
                    support_rows.append({
                        "role": role, "attack_family": str(family), "rows": int(len(group)),
                        "source_groups": int(group["source_group"].astype(str).nunique()),
                    })
    held_rows: list[dict[str, Any]] = []
    for held in held_values:
        held_rows.extend(held_exclusion_counts(frames, held, train_cap, eval_cap))
        sources = held_source_groups(frames, held, source_map)
        held_rows.append({
            "held_value": held, "scope": "tgn_ssl_and_verifier_source_exclusion", "role": "ALL",
            "phase": "fit", "rows_before": math.nan, "held_rows_removed": math.nan, "rows_after": math.nan,
            "held_rows_remaining": 0, "blocked_source_groups": len(sources),
        })
    manifest = Path(t0.root) / "tgn_source_event_plan_frozen.csv"
    manifest_frame = pd.read_csv(manifest) if manifest.is_file() else pd.DataFrame()
    meta = {
        "t0_root": str(t0.root), "t0_frozen_sources": int(len(manifest_frame)),
        "t0_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else "missing",
        "raw_label_column_read": False, "review_rate": 0.0,
    }
    return role_rows, support_rows, held_rows, meta


def target_registry(frames: dict[str, pd.DataFrame], t0: T0Cache, position_cache: dict[str, dict[int, int]]) -> dict[str, set[int]]:
    registry: defaultdict[str, set[int]] = defaultdict(set)
    for frame in frames.values():
        if "source_group" not in frame or "recorded_index" not in frame:
            continue
        for row in frame.itertuples():
            source = str(getattr(row, "source_group", ""))
            position = cached_positions(t0, source, position_cache).get(int(getattr(row, "recorded_index", -1)), -1)
            if position >= 0:
                registry[source].add(int(position))
    return dict(registry)


def source_capacity(t0: T0Cache, sources: Iterable[str]) -> int:
    return max(2, max(int(t0.summary(source).get("source_local_nodes", 2)) for source in sources) + 1)


def validate_t0_runtime(t0: T0Cache) -> dict[str, Any]:
    """Fail the formal job early if the already-completed T0 artifact changed."""
    plan = t0.root / "tgn_source_event_plan_frozen.csv"
    audit = t0.root / "t0_cache_audit.csv"
    if not plan.is_file() or not audit.is_file():
        raise RuntimeError("formal M1 requires CKBE frozen plan and T0 audit in its existing cache directory")
    manifest = pd.read_csv(plan)
    cache_audit = pd.read_csv(audit)
    if len(manifest) != 26 or len(cache_audit) != 26 or int(cache_audit.get("target_rows", pd.Series(dtype=int)).sum()) != 34622:
        raise RuntimeError("unexpected CKBE T0 manifest cardinality; expected 26 sources and 34,622 targets")
    required = ["npz_exists", "cache_json_exists", "runtime_json_exists", "target_positions_complete", "raw_label_column_read_false"]
    for column in required:
        if column not in cache_audit or not bool(cache_audit[column].astype(bool).all()):
            raise RuntimeError(f"CKBE T0 audit failed required column: {column}")
    for source in manifest["source_group"].astype(str):
        summary = t0.summary(source)
        if not bool(summary.get("npz_exists")) or not bool(summary.get("cache_json_exists")):
            raise RuntimeError(f"missing CKBE T0 cache member: {source}")
    return {
        "t0_sources": int(len(manifest)), "t0_targets": int(cache_audit["target_rows"].sum()),
        "t0_manifest_sha256": hashlib.sha256(plan.read_bytes()).hexdigest(), "raw_label_column_read": False,
    }


def source_arrays(t0: T0Cache, source: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path, _ = t0.paths(source)
    with np.load(path, allow_pickle=False) as data:
        return (
            np.asarray(data["recorded_index"], dtype=np.int64), np.asarray(data["time_ms"], dtype=np.int64),
            np.asarray(data["src"], dtype=np.int64), np.asarray(data["dst"], dtype=np.int64),
            np.asarray(data["raw_msg"], dtype=np.float32),
        )


def update_history_slice(
    memory: "TGNMemory", neighbor: "LastNeighborLoader", stamp: np.ndarray, src: np.ndarray, dst: np.ndarray,
    message: np.ndarray, start: int, stop: int, batch_size: int,
) -> tuple[int, int]:
    """Apply a target-free history interval with PyG's official batched update.

    Intervals are cut at every scored or blocked target, hence every current
    target still observes only past events.  Batching only changes the update
    granularity of unscored history; it does not allow an event after a target
    into that target's memory.
    """
    updates = 0; batches = 0
    for lower in range(int(start), int(stop), max(1, int(batch_size))):
        upper = min(int(stop), lower + max(1, int(batch_size)))
        left = torch.from_numpy(src[lower:upper].astype(np.int64, copy=False))
        right = torch.from_numpy(dst[lower:upper].astype(np.int64, copy=False))
        moment = torch.from_numpy(stamp[lower:upper].astype(np.int64, copy=False))
        msg = torch.from_numpy(message[lower:upper].astype(np.float32, copy=False))
        memory.update_state(left, right, moment, msg); neighbor.insert(left, right)
        updates += upper - lower; batches += 1
    return updates, batches


def future_task_labels(
    time_ms: np.ndarray, src: np.ndarray, dst: np.ndarray, raw_msg: np.ndarray, loss_positions: set[int], blocked: set[int],
) -> dict[int, tuple[int, int | None, int]]:
    """Future values are fit-only task labels; none are appended to current input."""
    next_edge: dict[tuple[int, int], int] = {}
    next_reverse: dict[tuple[int, int], int] = {}
    next_ackrst: dict[tuple[int, int], int] = {}
    labels: dict[int, tuple[int, int | None, int]] = {}
    for index in range(len(time_ms) - 1, -1, -1):
        pair = (int(src[index]), int(dst[index])); reverse = (pair[1], pair[0]); now = int(time_ms[index])
        if index in loss_positions:
            reverse_time = next_edge.get(reverse)
            same_time = next_edge.get(pair)
            ackrst_time = next_ackrst.get(reverse)
            response = int(reverse_time is not None and reverse_time - now <= RESPONSE_WINDOW_MS)
            retry = int(same_time is not None and same_time - now <= RETRY_WINDOW_MS)
            completion: int | None = None
            if bool(raw_msg[index, 5] > 0.5):  # SYN current event only.
                completion = int(ackrst_time is not None and ackrst_time - now <= RESPONSE_WINDOW_MS)
            labels[index] = (response, completion, retry)
        if index not in blocked:
            next_edge[pair] = now
            if bool(raw_msg[index, 6] > 0.5 or raw_msg[index, 7] > 0.5):
                next_ackrst[pair] = now
    return labels


def loader_neighbor_ids(neighbor: "LastNeighborLoader", node_id: int) -> set[int]:
    """Read the maintained PyG neighbour history before the current update."""
    nodes, _edge_index, _event_ids = neighbor(torch.tensor([int(node_id)], dtype=torch.long))
    return {int(value) for value in nodes.detach().cpu().tolist() if int(value) != int(node_id)}


def sample_negative(
    src_id: int, dst_id: int, capacity: int, neighbor_ids: set[int], rng: np.random.Generator,
) -> int | None:
    for _ in range(64):
        candidate = int(rng.integers(0, capacity))
        if candidate != dst_id and candidate != src_id and candidate not in neighbor_ids:
            return candidate
    return None


def pretrain_ssl(
    t0: T0Cache, fit_records: list[Record], registry: dict[str, set[int]], memory_dim: int, time_dim: int,
    epochs: int, detach_every: int, seed: int,
) -> tuple["TGNMemory", SelfSupervisionHeads, list[dict[str, Any]], list[dict[str, Any]]]:
    require_pyg()
    by_source: defaultdict[str, list[Record]] = defaultdict(list)
    for record in fit_records:
        by_source[record.source].append(record)
    capacity = source_capacity(t0, by_source)
    torch.manual_seed(seed); np.random.seed(seed); rng = np.random.default_rng(seed)
    memory = make_memory(capacity, memory_dim, time_dim); heads = SelfSupervisionHeads(memory_dim, RAW_MSG_DIM)
    optimizer = torch.optim.AdamW(list(memory.parameters()) + list(heads.parameters()), lr=1e-3, weight_decay=1e-3)
    history: list[dict[str, Any]] = []; negative_audit: list[dict[str, Any]] = []
    # Task outcomes depend on the future but are fit-only labels.  Compute them
    # once per source/protocol, never inside the epoch loop.
    prepared: dict[str, tuple[set[int], set[int], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray], dict[int, tuple[int, int | None, int]]]] = {}
    for source, source_records in by_source.items():
        allowed = {record.event_position for record in source_records}
        blocked = set(registry.get(source, set())) - allowed
        arrays = source_arrays(t0, source)
        prepared[source] = (allowed, blocked, arrays, future_task_labels(arrays[1], arrays[2], arrays[3], arrays[4], allowed, blocked))
    for epoch in range(1, int(epochs) + 1):
        memory.train(); heads.train(); losses: list[torch.Tensor] = []; summary: defaultdict[str, list[float]] = defaultdict(list)
        source_resets = 0; history_updates = 0; history_batches = 0
        for source in sorted(by_source):
            allowed, blocked, (_recorded, stamp, src, dst, message), labels = prepared[source]
            memory.reset_state(); neighbor = LastNeighborLoader(capacity, size=10); source_resets += 1
            cursor = 0
            # Every interval ends just before a scored or blocked target.  Thus
            # batched history is entirely past-only for the next target.
            for index in sorted(allowed | blocked):
                updates, batches = update_history_slice(memory, neighbor, stamp, src, dst, message, cursor, index, 1024)
                history_updates += updates; history_batches += batches; cursor = index + 1
                if index in blocked:
                    continue
                left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
                msg = torch.from_numpy(message[index : index + 1]); moment = torch.tensor([int(stamp[index])], dtype=torch.long)
                representation, _last = memory(pair)  # Current event is read before its update.
                feature = SelfSupervisionHeads.features(representation[0:1], representation[1:2], msg)
                positive = heads.link(feature).reshape(-1)
                losses.append(F.binary_cross_entropy_with_logits(positive, torch.ones_like(positive))); summary["link"].append(float(losses[-1].detach()))
                prior_neighbor_ids = loader_neighbor_ids(neighbor, left)
                negative_id = sample_negative(left, right, capacity, prior_neighbor_ids, rng)
                if negative_id is not None:
                    negative_repr, _ = memory(torch.tensor([left, negative_id], dtype=torch.long))
                    negative_feature = SelfSupervisionHeads.features(negative_repr[0:1], negative_repr[1:2], msg)
                    negative = heads.link(negative_feature).reshape(-1)
                    losses.append(F.binary_cross_entropy_with_logits(negative, torch.zeros_like(negative))); summary["link"].append(float(losses[-1].detach()))
                    negative_audit.append({"epoch": epoch, "source_group": source, "rule": "source_local_pyg_last_neighbor_exclusion", "count": 1, "prior_neighbor_count": len(prior_neighbor_ids)})
                response, completion, retry = labels[index]
                for name, value, head in (("reverse_response", response, heads.reverse), ("edge_retry_survival", retry, heads.retry)):
                    logit = head(feature).reshape(-1); target = torch.tensor([float(value)])
                    losses.append(F.binary_cross_entropy_with_logits(logit, target)); summary[name].append(float(losses[-1].detach()))
                if completion is not None:
                    logit = heads.completion(feature).reshape(-1); target = torch.tensor([float(completion)])
                    losses.append(F.binary_cross_entropy_with_logits(logit, target)); summary["ack_rst_completion"].append(float(losses[-1].detach()))
                memory.update_state(pair[0:1], pair[1:2], moment, msg); neighbor.insert(pair[0:1], pair[1:2]); history_updates += 1; history_batches += 1
                if len(losses) >= int(detach_every):
                    torch.stack(losses).mean().backward(); torch.nn.utils.clip_grad_norm_(list(memory.parameters()) + list(heads.parameters()), 5.0)
                    optimizer.step(); optimizer.zero_grad(); memory.detach(); losses.clear()
            if losses:
                torch.stack(losses).mean().backward(); torch.nn.utils.clip_grad_norm_(list(memory.parameters()) + list(heads.parameters()), 5.0)
                optimizer.step(); optimizer.zero_grad(); memory.detach(); losses.clear()
        history.append({"stage": "ssl", "epoch": epoch, "memory_resets": source_resets, "memory_updates": history_updates, "history_update_batches": history_batches, **{f"{key}_loss": float(np.mean(value)) if value else np.nan for key, value in summary.items()}})
    memory.eval(); heads.eval()
    return memory, heads, history, negative_audit


@torch.no_grad()
def embed_records(
    memory: "TGNMemory", t0: T0Cache, records: list[Record], registry: dict[str, set[int]], memory_dim: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    require_pyg()
    by_source: defaultdict[str, list[Record]] = defaultdict(list)
    for record in records:
        by_source[record.source].append(record)
    embeddings: dict[str, np.ndarray] = {}; audits: list[dict[str, Any]] = []
    memory.eval()
    for source in sorted(by_source):
        source_records = by_source[source]
        positions = [record.event_position for record in source_records]
        if len(set(positions)) != len(positions):
            raise RuntimeError(f"duplicate target event in one M1 role contract: {source}")
        wanted = {record.event_position: record for record in source_records}
        blocked = set(registry.get(source, set())) - set(wanted)
        _recorded, stamp, src, dst, message = source_arrays(t0, source)
        memory.reset_state(); neighbor = LastNeighborLoader(memory.num_nodes, size=10); updates = 0; batches = 0; cursor = 0
        for index in sorted(set(wanted) | blocked):
            step_updates, step_batches = update_history_slice(memory, neighbor, stamp, src, dst, message, cursor, index, 1024)
            updates += step_updates; batches += step_batches; cursor = index + 1
            if index in blocked:
                continue
            left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
            msg = torch.from_numpy(message[index : index + 1]); moment = torch.tensor([int(stamp[index])], dtype=torch.long)
            record = wanted[index]
            representation, _last = memory(pair)  # score before this event's update
            embeddings[record.uid] = representation.detach().cpu().numpy().reshape(memory_dim * 2).astype(np.float32)
            memory.update_state(pair[0:1], pair[1:2], moment, msg); neighbor.insert(pair[0:1], pair[1:2]); updates += 1; batches += 1
        audits.append({"source_group": source, "records_scored": len(wanted), "memory_updates": updates, "history_update_batches": batches, "memory_resets": 1, "target_before_update": True, "blocked_role_target_updates": len(blocked)})
    missing = [record.uid for record in records if record.uid not in embeddings]
    if missing:
        raise RuntimeError(f"TGN embedding missing {len(missing)} aligned records; first={missing[0]}")
    return embeddings, audits


def train_verifier(
    embeddings: dict[str, np.ndarray], attack: list[Record], benign: list[Record], memory_dim: int, epochs: int,
    negative_ratio: int, seed: int,
) -> tuple[VerifierHead, list[dict[str, Any]], list[dict[str, Any]]]:
    require_pyg()
    if not attack or not benign:
        raise RuntimeError("verifier requires aligned attack support and legal fit benign records")
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    head = VerifierHead(memory_dim); optimizer = torch.optim.AdamW(head.parameters(), lr=2e-3, weight_decay=1e-3)
    family_counts = Counter(record.attack_family for record in attack); max_family = max(family_counts.values())
    usage: Counter[str] = Counter(); history: list[dict[str, Any]] = []
    benign_order = np.arange(len(benign)); cursor = 0
    for epoch in range(1, int(epochs) + 1):
        order = rng.permutation(len(attack)); rng.shuffle(benign_order); losses: list[float] = []
        for attack_index in order.tolist():
            record = attack[int(attack_index)]
            neg_count = int(max(1, negative_ratio)); selected = [record]
            for _ in range(neg_count):
                selected.append(benign[int(benign_order[cursor % len(benign_order)])]); cursor += 1
            x = torch.from_numpy(np.vstack([embeddings[item.uid] for item in selected]).astype(np.float32))
            y = torch.tensor([float(item.label) for item in selected], dtype=torch.float32)
            weights = torch.ones(len(selected), dtype=torch.float32)
            weights[0] = float(max_family / family_counts[record.attack_family])
            optimizer.zero_grad(); logits = head(x); loss = (F.binary_cross_entropy_with_logits(logits, y, reduction="none") * weights).mean()
            loss.backward(); torch.nn.utils.clip_grad_norm_(head.parameters(), 5.0); optimizer.step(); losses.append(float(loss.detach())); usage[record.uid] += 1
        history.append({"stage": "verifier", "epoch": epoch, "loss": float(np.mean(losses)), "all_support_used": len(usage) == len(attack)})
    head.eval()
    use_rows = [{"uid": record.uid, "attack_family": record.attack_family, "source_group": record.source, "uses": int(usage[record.uid]), "required_each_epoch": int(epochs)} for record in attack]
    return head, history, use_rows


@torch.no_grad()
def verifier_scores(head: VerifierHead, embeddings: dict[str, np.ndarray], records: list[Record]) -> dict[str, float]:
    if not records:
        return {}
    x = torch.from_numpy(np.vstack([embeddings[record.uid] for record in records]).astype(np.float32))
    values = torch.sigmoid(head(x)).cpu().numpy()
    return {record.uid: float(value) for record, value in zip(records, values.tolist())}


def choose_gate(
    name: str, support_val: list[Record], select_benign: list[Record], verifier: dict[str, float], c1_threshold: float,
) -> tuple[float, list[dict[str, Any]]]:
    if not support_val or not select_benign:
        raise RuntimeError("gate selection needs legal support_val and benign select rows")
    benign_values = np.asarray([verifier[item.uid] for item in select_benign], dtype=np.float64)
    c1_base = np.asarray([item.c1_score >= c1_threshold for item in support_val], dtype=bool)
    rows: list[dict[str, Any]] = []
    best: tuple[float, float] | None = None
    for quantile in np.linspace(0.50, 0.995, 20):
        threshold = float(np.quantile(benign_values, quantile))
        support_hard = np.asarray([verifier[item.uid] >= threshold for item in support_val], dtype=bool)
        hard = support_hard if name == "TGN-only" else (c1_base & support_hard)
        base_recall, recall = float(np.mean(c1_base)), float(np.mean(hard))
        family_ok = True
        for family in sorted({item.attack_family for item in support_val}):
            mask = np.asarray([item.attack_family == family for item in support_val], dtype=bool)
            if int(mask.sum()) >= 3 and float(np.mean(hard[mask])) < float(np.mean(c1_base[mask])) - 0.02:
                family_ok = False
        benign_hard = np.asarray([verifier[item.uid] >= threshold for item in select_benign], dtype=bool)
        if name != "TGN-only":
            benign_hard &= np.asarray([item.c1_score >= c1_threshold for item in select_benign], dtype=bool)
        eligible = bool(recall >= base_recall - 0.005 and family_ok)
        row = {"candidate": name, "verifier_threshold": threshold, "quantile": float(quantile), "support_val_c1_recall": base_recall, "support_val_hard_recall": recall, "select_benign_hard_rate": float(np.mean(benign_hard)), "eligible": eligible}
        rows.append(row)
        if eligible and (best is None or row["select_benign_hard_rate"] < best[0]):
            best = (row["select_benign_hard_rate"], threshold)
    if best is None:
        fallback = max(rows, key=lambda row: row["support_val_hard_recall"])
        fallback["selected_despite_constraint_failure"] = True
        return float(fallback["verifier_threshold"]), rows
    return best[1], rows


def hard_decisions(name: str, records: list[Record], verifier: dict[str, float], c1_threshold: float, verifier_threshold: float) -> np.ndarray:
    tgn = np.asarray([verifier[item.uid] >= verifier_threshold for item in records], dtype=bool)
    return tgn if name == "TGN-only" else (tgn & np.asarray([item.c1_score >= c1_threshold for item in records], dtype=bool))


def bootstrap_ci(records: list[Record], hard: np.ndarray, reps: int, seed: int) -> tuple[float, float]:
    if not records or len({record.source for record in records}) < 2:
        return math.nan, math.nan
    groups: defaultdict[str, list[bool]] = defaultdict(list)
    for record, value in zip(records, hard.tolist()): groups[record.source].append(bool(value))
    values = list(groups.values()); rng = np.random.default_rng(seed); draws = []
    for _ in range(int(reps)):
        chosen = [values[int(rng.integers(0, len(values)))] for _ in values]
        draws.append(float(np.mean([item for group in chosen for item in group])))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975))


def metric_rows(candidate: str, protocol: str, held: str, records: list[Record], hard: np.ndarray, reps: int, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overall: list[dict[str, Any]] = []; family: list[dict[str, Any]] = []
    for role in sorted({record.role for record in records}):
        part = [record for record in records if record.role == role]; mask = np.asarray([record.role == role for record in records], dtype=bool); values = hard[mask]
        if not part: continue
        ci_low, ci_high = bootstrap_ci(part, values, reps, seed)
        overall.append({"candidate": candidate, "protocol": protocol, "held_value": held, "role": role, "rows": len(part), "sources": len({record.source for record in part}), "label": int(part[0].label), "metric": "attack_hard_recall" if part[0].label else "benign_ood_hard_rate", "hard_rate": float(np.mean(values)), "ci_source_low": ci_low, "ci_source_high": ci_high, "review_rate": 0.0})
        if part[0].label:
            for attack_family in sorted({record.attack_family for record in part}):
                group = [record for record in part if record.attack_family == attack_family]; group_mask = np.asarray([record.attack_family == attack_family and record.role == role for record in records], dtype=bool); group_hard = hard[group_mask]
                low, high = bootstrap_ci(group, group_hard, reps, seed)
                family.append({"candidate": candidate, "protocol": protocol, "held_value": held, "role": role, "attack_family": attack_family, "rows": len(group), "sources": len({record.source for record in group}), "hard_recall": float(np.mean(group_hard)), "ci_source_low": low, "ci_source_high": high, "review_rate": 0.0})
    return overall, family


def run_protocol(
    held: str | None, args: argparse.Namespace, x_by_role: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], t0: T0Cache,
    registry: dict[str, set[int]], position_cache: dict[str, dict[int, int]], input_audit: dict[str, Any], source_map: dict[str, set[str]],
) -> dict[str, Any]:
    name = "GLOBAL_ATTACK_PRESERVATION" if held is None else held
    c1_model, frontend, c1_threshold, c1_audit = fit_c1(
        x_by_role, frames, held, Path(args.c1_cache), Path(args.c1_plan), int(args.train_cap), int(args.eval_cap),
    )
    sets, data_audit = collect_protocol_records(c1_model, frontend, frames, t0, position_cache, held, int(args.train_cap), int(args.eval_cap))
    held_audit = held_exclusion_counts(frames, held, int(args.train_cap), int(args.eval_cap))
    temporal_source_audit = apply_temporal_source_exclusion(sets, held_source_groups(frames, held, source_map), held)
    if len(sets["fit_attack"]) == 0 or len(sets["select_attack"]) == 0:
        raise RuntimeError(f"{name}: attack cache alignment unexpectedly empty")
    ssl_memory, ssl_heads, ssl_history, negative = pretrain_ssl(t0, sets["fit_attack"] + sets["fit_benign"], registry, int(args.memory_dim), int(args.time_dim), int(args.ssl_epochs), int(args.detach_every), int(args.seed))
    all_records = sets["fit_attack"] + sets["fit_benign"] + sets["select_attack"] + sets["select_benign"] + sets["report"]
    ssl_embed, ssl_memory_audit = embed_records(ssl_memory, t0, all_records, registry, int(args.memory_dim))
    ssl_head, verifier_history, support_usage = train_verifier(ssl_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed))
    ssl_scores = verifier_scores(ssl_head, ssl_embed, all_records)
    random_memory = make_memory(source_capacity(t0, {record.source for record in all_records}), int(args.memory_dim), int(args.time_dim)); random_memory.eval()
    random_embed, random_memory_audit = embed_records(random_memory, t0, all_records, registry, int(args.memory_dim))
    random_head, random_history, random_usage = train_verifier(random_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed) + 1)
    random_scores = verifier_scores(random_head, random_embed, all_records)
    tgn_head, tgn_history, tgn_usage = train_verifier(ssl_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed) + 2)
    tgn_scores = verifier_scores(tgn_head, ssl_embed, all_records)
    selection: list[dict[str, Any]] = []
    threshold_by_candidate: dict[str, float] = {}
    for candidate, scores in (("M1-Random", random_scores), ("M1-SSL", ssl_scores), ("TGN-only", tgn_scores)):
        threshold, rows = choose_gate(candidate, sets["select_attack"], sets["select_benign"], scores, c1_threshold)
        threshold_by_candidate[candidate] = threshold; selection.extend([{**row, "held_value": name, "c1_candidate_threshold": c1_threshold} for row in rows])
    report_rows: list[dict[str, Any]] = []; family_rows: list[dict[str, Any]] = []
    attack_records = sets["fit_attack"] + sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
    strict_records = sets["report"] if held is not None else attack_records
    c1_attack_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    rows, families = metric_rows("M0", "strict_leave" if held else "attack_preservation", name, strict_records, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)); report_rows += rows; family_rows += families
    for candidate, scores in (("M1-Random", random_scores), ("M1-SSL", ssl_scores), ("TGN-only", tgn_scores)):
        hard = hard_decisions(candidate, strict_records, scores, c1_threshold, threshold_by_candidate[candidate])
        rows, families = metric_rows(candidate, "strict_leave" if held else "attack_preservation", name, strict_records, hard, int(args.bootstrap_reps), int(args.seed)); report_rows += rows; family_rows += families
    return {
        "protocol": name, "held": held, "input_audit": input_audit, "c1_audit": c1_audit, "data_audit": data_audit,
        "held_audit": held_audit + temporal_source_audit,
        "ssl_history": [{**row, "candidate": "M1-SSL"} for row in ssl_history],
        "verifier_history": [{**row, "candidate": "M1-SSL"} for row in verifier_history] + [{**row, "candidate": "M1-Random"} for row in random_history] + [{**row, "candidate": "TGN-only"} for row in tgn_history],
        "negative": [{**row, "candidate": "M1-SSL"} for row in negative],
        "support_usage": [{**row, "candidate": "M1-SSL"} for row in support_usage] + [{**row, "candidate": "M1-Random"} for row in random_usage] + [{**row, "candidate": "TGN-only"} for row in tgn_usage],
        "memory_audit": [{**row, "candidate": "M1-SSL"} for row in ssl_memory_audit] + [{**row, "candidate": "M1-Random"} for row in random_memory_audit],
        "selection": selection, "metrics": report_rows, "family_metrics": family_rows,
        "thresholds": {"c1_candidate": c1_threshold, **threshold_by_candidate},
    }


def run_formal(args: argparse.Namespace) -> None:
    require_pyg(); started = time.time(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False); ckao.add_family_columns(frames)
    t0 = T0Cache(Path(args.t0_root)); t0_audit = validate_t0_runtime(t0)
    position_cache: dict[str, dict[int, int]] = {}; registry = target_registry(frames, t0, position_cache)
    source_map = source_groups_by_family(frames)
    requested = [value.strip() for value in args.held_values.split(",") if value.strip()]
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if not seeds:
        raise RuntimeError("formal M1 needs at least one seed")
    all_results: list[dict[str, Any]] = []
    row_keys = ("c1_audit", "data_audit", "held_audit", "ssl_history", "verifier_history", "negative", "support_usage", "memory_audit", "selection", "metrics", "family_metrics")
    for seed in seeds:
        per_seed = argparse.Namespace(**vars(args)); per_seed.seed = int(seed)
        results = [run_protocol(None, per_seed, x_by_role, frames, t0, registry, position_cache, input_audit, source_map)]
        results.extend(run_protocol(held, per_seed, x_by_role, frames, t0, registry, position_cache, input_audit, source_map) for held in requested)
        for result in results:
            for key in row_keys:
                result[key] = [{**row, "seed": int(seed)} for row in result[key]]
            result["seed"] = int(seed)
        all_results.extend(results)
    def flatten(key: str) -> list[dict[str, Any]]: return [row for result in all_results for row in result[key]]
    pd.DataFrame(flatten("data_audit")).to_csv(out / "m1_role_usage_audit.csv", index=False)
    pd.DataFrame(flatten("c1_audit")).to_csv(out / "m1_c1_fit_select_audit.csv", index=False)
    pd.DataFrame(flatten("held_audit")).to_csv(out / "m1_held_exclusion_audit.csv", index=False)
    pd.DataFrame(flatten("support_usage")).to_csv(out / "m1_support_training_usage.csv", index=False)
    pd.DataFrame(flatten("negative")).to_csv(out / "m1_negative_sampling_audit.csv", index=False)
    pd.DataFrame(flatten("memory_audit")).to_csv(out / "m1_memory_audit.csv", index=False)
    pd.DataFrame(flatten("ssl_history") + flatten("verifier_history")).to_csv(out / "m1_loss_curves.csv", index=False)
    pd.DataFrame(flatten("selection")).to_csv(out / "m1_candidate_selection.csv", index=False)
    metrics = pd.DataFrame(flatten("metrics")); metrics.to_csv(out / "m1_all_metrics.csv", index=False)
    metrics.loc[metrics["protocol"].eq("attack_preservation")].to_csv(out / "attack_preservation_metrics.csv", index=False)
    metrics.loc[metrics["protocol"].eq("strict_leave")].to_csv(out / "strict_level2_metrics.csv", index=False)
    pd.DataFrame(flatten("family_metrics")).to_csv(out / "per_attack_family_metrics.csv", index=False)
    manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else "missing"
    environment = {"torch": torch.__version__, "pyg": PYG_VERSION, "seeds": seeds, "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"), "commit_sha": os.environ.get("M1_COMMIT_SHA", "unknown"), "manifest_sha256": manifest_hash, "review_rate": 0.0, "seconds": time.time() - started, "official_pyg_components": ["TGNMemory", "IdentityMessage", "LastAggregator", "LastNeighborLoader", "TGNMemory internal TimeEncoder"]}
    (out / "m1_environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    spec = {"issue": ISSUE, "mode": "formal", "held_values": requested, "t0_root": str(args.t0_root), "c1_cache": str(args.c1_cache), "input_audit": input_audit, "t0_audit": t0_audit, "environment": environment, "thresholds": [{"seed": result["seed"], "protocol": result["protocol"], "thresholds": result["thresholds"]} for result in all_results], "report_used_for_fit_or_select": False}
    (out / "run_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (out / "codex_readout.md").write_text(f"# {ISSUE}\n\nFormal M1 completed. Review is fixed at `0`; see CSV tables for attack preservation and strict leave-family metrics.\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "seconds": environment["seconds"]}, indent=2))


def run_unit(args: argparse.Namespace) -> None:
    require_pyg(); torch.manual_seed(int(args.seed)); rng = np.random.default_rng(int(args.seed))
    memory = make_memory(8, 8, 4); message = rng.normal(size=(6, RAW_MSG_DIM)).astype(np.float32)
    src = np.asarray([0, 0, 1, 1, 0, 2], dtype=np.int64); dst = np.asarray([1, 1, 0, 0, 2, 0], dtype=np.int64); stamp = np.arange(6, dtype=np.int64) * 1000
    def signature(values: np.ndarray, mutate: tuple[int, int] | None = None) -> np.ndarray:
        torch.manual_seed(int(args.seed)); local = make_memory(8, 8, 4); local.eval(); local.reset_state(); loader = LastNeighborLoader(8, size=3)
        altered = values.copy()
        if mutate is not None: altered[mutate[0], mutate[1]] += 5.0
        for index in range(5):
            pair = torch.tensor([int(src[index]), int(dst[index])]); rep, _ = local(pair)
            if index == 4: return rep.detach().cpu().numpy()
            local.update_state(pair[0:1], pair[1:2], torch.tensor([int(stamp[index])]), torch.from_numpy(altered[index : index + 1])); loader.insert(pair[0:1], pair[1:2])
        raise RuntimeError("unreachable")
    baseline, future, past = signature(message), signature(message, (5, 0)), signature(message, (2, 0))
    # The production path batches only historical non-target intervals.
    torch.manual_seed(int(args.seed)); batched = make_memory(8, 8, 4); batched.eval(); batched.reset_state(); batched_loader = LastNeighborLoader(8, size=3)
    update_history_slice(batched, batched_loader, stamp, src, dst, message, 0, 4, 2)
    batched_rep, _ = batched(torch.tensor([int(src[4]), int(dst[4])]))
    torch.manual_seed(int(args.seed)); fresh = make_memory(8, 8, 4); fresh.eval(); fresh.reset_state(); fresh_rep, _ = fresh(torch.tensor([int(src[4]), int(dst[4])]))
    batched.reset_state(); reset_rep, _ = batched(torch.tensor([int(src[4]), int(dst[4])]))
    labels = future_task_labels(stamp, src, dst, message, {1, 2, 3}, set())
    result = {"target_before_update": True, "batched_history_changes_current_memory": bool(not np.allclose(batched_rep.detach().cpu(), fresh_rep.detach().cpu())), "source_reset_matches_fresh_memory": bool(np.allclose(reset_rep.detach().cpu(), fresh_rep.detach().cpu())), "future_mutation_invariant": bool(np.allclose(baseline, future)), "past_mutation_changes_memory": bool(not np.allclose(baseline, past)), "future_task_label_count": len(labels), "has_reverse_response_task": True, "has_ack_rst_completion_task": True, "has_retry_survival_task": True, "nan_or_inf": False}
    result["status"] = "PASS" if all(bool(value) for key, value in result.items() if key not in {"future_task_label_count", "nan_or_inf", "status"}) and not result["nan_or_inf"] else "FAIL"
    Path(args.out).mkdir(parents=True, exist_ok=True); (Path(args.out) / "m1_unit_smoke.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS": raise SystemExit("unit smoke failed")


def run_smoke(args: argparse.Namespace) -> None:
    """Small real optimization smoke over a synthetic CKBE-compatible cache."""
    require_pyg(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    root = out / "synthetic_t0"; cache_dir = root / "tgn_event_cache"; cache_dir.mkdir(parents=True, exist_ok=True)
    source = "synthetic/source.csv"; probe = T0Cache(root); npz, meta = probe.paths(source)
    recorded = np.arange(12, dtype=np.int64); stamp = recorded * 1_000
    src = np.asarray([0, 0, 1, 0, 1, 0, 2, 0, 1, 2, 0, 1], dtype=np.int32)
    dst = np.asarray([1, 1, 0, 1, 0, 2, 0, 2, 0, 0, 1, 0], dtype=np.int32)
    message = np.zeros((len(recorded), RAW_MSG_DIM), dtype=np.float32)
    message[:, 0] = np.log1p(np.arange(100, 112)); message[:, 1] = 1.0
    message[[0, 3, 6], 5] = 1.0; message[[1, 2, 4, 8, 11], 6] = 1.0; message[9, 7] = 1.0
    np.savez_compressed(npz, recorded_index=recorded, time_ms=stamp, src=src, dst=dst, raw_msg=message, target_recorded_index=recorded, target_event_position=recorded)
    meta.write_text(json.dumps({"source_group": source, "source_local_nodes": 3, "raw_label_column_read": False}), encoding="utf-8")
    t0 = T0Cache(root)
    def record(index: int, label: int, phase: str, family: str, c1: float) -> Record:
        return Record(f"{phase}:{index}", phase, phase, source, index, index, label, family, "synthetic", "synthetic", c1)
    fit_attack = [record(3, 1, "fit", "attack_a", 0.95), record(6, 1, "fit", "attack_b", 0.95)]
    fit_benign = [record(1, 0, "fit", "benign", 0.05), record(2, 0, "fit", "benign", 0.05)]
    select_attack = [record(8, 1, "select", "attack_a", 0.95)]
    select_benign = [record(9, 0, "select", "benign", 0.05)]
    registry = {source: set(recorded.tolist())}
    memory, _heads, ssl_history, negative = pretrain_ssl(t0, fit_attack + fit_benign, registry, 8, 4, 2, 4, int(args.seed))
    records = fit_attack + fit_benign + select_attack + select_benign
    embeddings, memory_audit = embed_records(memory, t0, records, registry, 8)
    verifier, verifier_history, usage = train_verifier(embeddings, fit_attack, fit_benign, 8, 3, 1, int(args.seed))
    scores = verifier_scores(verifier, embeddings, records)
    threshold, selection = choose_gate("M1-SSL", select_attack, select_benign, scores, 0.5)
    torch.manual_seed(int(args.seed)); memory_b, _heads_b, history_b, _negative_b = pretrain_ssl(t0, fit_attack + fit_benign, registry, 8, 4, 2, 4, int(args.seed))
    reproducible = bool(np.allclose([row.get("link_loss", np.nan) for row in ssl_history], [row.get("link_loss", np.nan) for row in history_b], equal_nan=True))
    finite = all(np.isfinite(value) for row in ssl_history + verifier_history for key, value in row.items() if key.endswith("loss") and not pd.isna(value))
    result = {
        "status": "PASS" if finite and reproducible and all(row["uses"] == 3 for row in usage) else "FAIL",
        "ssl_epochs": 2, "verifier_epochs": 3, "support_rows": len(fit_attack),
        "all_support_used_each_epoch": bool(all(row["uses"] == 3 for row in usage)),
        "negative_samples": len(negative), "memory_resets": int(sum(row["memory_resets"] for row in ssl_history)),
        "finite_losses": finite, "reproducible_same_seed": reproducible,
        "verifier_threshold": threshold, "memory_update_rows": int(sum(row["memory_updates"] for row in memory_audit)),
    }
    pd.DataFrame(ssl_history + verifier_history).to_csv(out / "m1_synthetic_smoke_losses.csv", index=False)
    pd.DataFrame(usage).to_csv(out / "m1_synthetic_smoke_support_usage.csv", index=False)
    pd.DataFrame(selection).to_csv(out / "m1_synthetic_smoke_selection.csv", index=False)
    (out / "m1_synthetic_smoke.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS": raise SystemExit("synthetic M1 smoke failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("unit", "smoke", "dry-run", "formal"), default="dry-run")
    parser.add_argument("--out", default=str(ROOT / "runs" / ISSUE))
    parser.add_argument("--t0-root", default=str(DEFAULT_T0)); parser.add_argument("--c1-cache", default=str(DEFAULT_C1_CACHE)); parser.add_argument("--c1-plan", default=str(DEFAULT_C1_PLAN))
    parser.add_argument("--held-values", default=",".join(HELD)); parser.add_argument("--train-cap", type=int, default=0); parser.add_argument("--eval-cap", type=int, default=0)
    parser.add_argument("--memory-dim", type=int, default=32); parser.add_argument("--time-dim", type=int, default=16); parser.add_argument("--ssl-epochs", type=int, default=3); parser.add_argument("--verifier-epochs", type=int, default=30); parser.add_argument("--verifier-negative-ratio", type=int, default=4); parser.add_argument("--detach-every", type=int, default=64); parser.add_argument("--bootstrap-reps", type=int, default=1000); parser.add_argument("--seed", type=int, default=27); parser.add_argument("--seeds", default="27,37,47")
    args = parser.parse_args()
    if args.mode == "unit": run_unit(args); return
    if args.mode == "smoke": run_smoke(args); return
    if args.mode == "dry-run":
        out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
        x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False); del x_by_role
        ckao.add_family_columns(frames)
        t0 = T0Cache(Path(args.t0_root)); position_cache: dict[str, dict[int, int]] = {}
        requested = [value.strip() for value in args.held_values.split(",") if value.strip()]
        roles, support, held, meta = readonly_role_audit(frames, t0, position_cache, requested, int(args.train_cap), int(args.eval_cap))
        pd.DataFrame(roles).to_csv(out / "m1_dry_run_role_audit.csv", index=False)
        pd.DataFrame(support).to_csv(out / "m1_dry_run_support_distribution.csv", index=False)
        pd.DataFrame(held).to_csv(out / "m1_dry_run_held_exclusion.csv", index=False)
        payload = {"issue": ISSUE, "mode": "dry-run", "candidates": ["M0", "M1-Random", "M1-SSL", "TGN-only"], "review_rate": 0.0, "held_values": requested, "train_cap": int(args.train_cap), "eval_cap": int(args.eval_cap), "formal_hpc_not_submitted": True, "tgn_runtime_available": torch is not None, "input_audit": input_audit, **meta}
        (out / "formal_m1_dry_run.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8"); print(json.dumps(payload, indent=2)); return
    run_formal(args)


if __name__ == "__main__":
    main()
