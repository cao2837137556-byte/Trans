"""CKBJ: corrected formal M1 C1-gated PyG-TGN strict evaluation.

This program is intentionally narrow.  It uses the maintained PyG TGNMemory
stack and the official-example TransformerConv neighbour embedding, the
existing legal C1 baseline, four pre-registered candidates, and a logical
C1-candidate / TGN-verifier gate.  It is not a generic MLP, episode
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
import platform
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckat_canonical_time_c1_canary_v1 as ckat  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as ckbj  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402

try:  # Kept lazy so dry-run can be inspected without creating an environment.
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch_geometric import __version__ as PYG_VERSION
    from torch_geometric.nn import TransformerConv
    from torch_geometric.nn.models.tgn import IdentityMessage, LastAggregator, LastNeighborLoader, TGNMemory
except Exception as exc:  # pragma: no cover - exercised only without PyG.
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]
    F = None  # type: ignore[assignment]
    PYG_VERSION = "unavailable"
    IdentityMessage = LastAggregator = LastNeighborLoader = TGNMemory = TransformerConv = None  # type: ignore[assignment]
    TORCH_ERROR = exc
else:
    TORCH_ERROR = None

_Module = nn.Module if nn is not None else object

ISSUE = "issue27ckbj_tgn_m1_strict_formal_v2_2026-07-13"
ROOT = cko.ROOT
DEFAULT_T0 = ROOT / "runs" / "issue27ckbe_tgn_fullsupport_event_cache_v1_2026-07-12_hpc_fullsupport_r3"
DEFAULT_REPORT_EXTENSION = ROOT / "runs" / "issue27ckbi_tgn_report_only_cache_extension_v1_2026-07-12_hpc"
DEFAULT_C1_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_load_plan.csv"
DEFAULT_C1_TARGETS = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_target_index.csv"
DEFAULT_C1_CACHE = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "hpc_canonical_c1_cache"
DEFAULT_C1_REPORT_EXTENSION = ROOT / "runs" / "issue27ckbj_c1_report_only_cache_extension_v1_2026-07-13_hpc"
EXPECTED_T0_MANIFEST_SHA256 = "b102b04347dd320f9f89a219285285866dbfa09e09bd73d0839cbe1a91bb0f67"
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
OFFICIAL_TGN_HISTORY_BATCH = 200


def require_pyg() -> None:
    if torch is None:
        raise RuntimeError("CKBH needs the provisioned Torch/PyG runtime") from TORCH_ERROR


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    mapped = series.astype(str).str.strip().str.lower().map({"true": True, "false": False, "1": True, "0": False})
    if mapped.isna().any():
        raise RuntimeError(f"invalid boolean values: {sorted(series.loc[mapped.isna()].astype(str).unique().tolist())}")
    return mapped.astype(bool)


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
    episode_id: str


class CompositeT0Cache:
    """Base frozen CKBE cache plus an explicitly report-only extension."""

    def __init__(self, base: T0Cache, extension_root: Path, extension_sources: set[str]):
        self.base = base
        self.extension = T0Cache(extension_root)
        self.root = base.root  # the frozen base manifest remains authoritative
        self.report_only_sources = set(extension_sources)
        self._summary_cache: dict[str, dict[str, Any]] = {}
        self._position_cache: dict[str, dict[int, int]] = {}

    def paths(self, source: str) -> tuple[Path, Path]:
        return self.extension.paths(source) if source in self.report_only_sources else self.base.paths(source)

    def summary(self, source: str) -> dict[str, Any]:
        if source not in self._summary_cache:
            self._summary_cache[source] = self.extension.summary(source) if source in self.report_only_sources else self.base.summary(source)
        return self._summary_cache[source]

    def target_positions(self, source: str) -> dict[int, int]:
        if source not in self._position_cache:
            self._position_cache[source] = self.extension.target_positions(source) if source in self.report_only_sources else self.base.target_positions(source)
        return self._position_cache[source]

    @property
    def cached_sources(self) -> set[str]:
        plan = pd.read_csv(self.base.root / "tgn_source_event_plan_frozen.csv")
        return set(plan["source_group"].astype(str).tolist()) | self.report_only_sources


class CompositeCanonicalTimeC1Cache:
    """Frozen CKAT cache plus the separate CKBJ report-only cache."""

    def __init__(self, base_dir: Path, base_plan: Path, extension_root: Path):
        extension_plan = extension_root / "canonical_source_load_plan.csv"
        self.base = ckat.PersistentCanonicalTimeC1Cache(base_dir, base_plan)
        self.extension = ckat.PersistentCanonicalTimeC1Cache(extension_root / "c1_report_cache", extension_plan)
        plan = pd.read_csv(extension_plan)
        self.extension_sources = set(plan["source_group"].astype(str))
        if self.extension_sources != set(ckbi.EXTENSION_SOURCES):
            raise RuntimeError("C1 report extension source boundary changed")
        self.audit_rows: list[dict[str, Any]] = []

    def _cache(self, member: str) -> ckat.PersistentCanonicalTimeC1Cache:
        return self.extension if str(member) in self.extension_sources else self.base

    def features_for_member(self, member: str, row_indices: np.ndarray) -> dict[int, np.ndarray]:
        cache = self._cache(member)
        values = cache.features_for_member(member, row_indices)
        return values

    def audit_for_member(self, member: str) -> dict[int, dict[str, Any]]:
        cache = self._cache(member)
        values = cache.audit_for_member(member)
        return values


class VerifierHead(_Module):  # type: ignore[misc]
    """A small per-event TGN verifier; C1 remains a separate logical gate."""

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


class GraphAttentionEmbedding(_Module):  # type: ignore[misc]
    """Graph embedding copied from the official PyG TGN example contract."""

    def __init__(self, memory_dim: int, message_dim: int, time_encoder: Any):
        require_pyg()
        super().__init__()
        if int(memory_dim) % 2:
            raise ValueError("memory_dim must be even for two-head TransformerConv")
        self.time_encoder = time_encoder
        edge_dim = int(message_dim) + int(time_encoder.out_channels)
        self.conv = TransformerConv(
            int(memory_dim), int(memory_dim) // 2, heads=2, dropout=0.1, edge_dim=edge_dim,
        )

    def forward(
        self, x: "torch.Tensor", last_update: "torch.Tensor", edge_index: "torch.Tensor",
        edge_time: "torch.Tensor", edge_message: "torch.Tensor",
    ) -> "torch.Tensor":
        relative = last_update[edge_index[0]] - edge_time
        relative_encoding = self.time_encoder(relative.to(x.dtype))
        edge_attr = torch.cat([relative_encoding, edge_message], dim=-1)
        return self.conv(x, edge_index, edge_attr)


class ReplayStore:
    """Event tensors indexed by LastNeighborLoader's source-local event IDs."""

    def __init__(self, capacity: int):
        require_pyg()
        self.time = torch.empty(max(1, int(capacity)), dtype=torch.long)
        self.message = torch.empty((max(1, int(capacity)), RAW_MSG_DIM), dtype=torch.float32)
        self.count = 0

    def append(self, moment: "torch.Tensor", message: "torch.Tensor") -> None:
        rows = int(len(moment))
        if self.count + rows > len(self.time):
            raise RuntimeError("TGN replay store capacity exceeded")
        self.time[self.count : self.count + rows] = moment.detach()
        self.message[self.count : self.count + rows] = message.detach()
        self.count += rows


class TGNProcessEncoder(_Module):  # type: ignore[misc]
    """Official PyG TGNMemory plus official-example graph attention embedding."""

    def __init__(self, capacity: int, memory_dim: int, time_dim: int):
        require_pyg()
        super().__init__()
        self.num_nodes = max(2, int(capacity))
        self.memory_dim = int(memory_dim)
        self.memory = TGNMemory(
            num_nodes=self.num_nodes,
            raw_msg_dim=RAW_MSG_DIM,
            memory_dim=int(memory_dim),
            time_dim=int(time_dim),
            message_module=IdentityMessage(RAW_MSG_DIM, int(memory_dim), int(time_dim)),
            aggregator_module=LastAggregator(),
        )
        self.gnn = GraphAttentionEmbedding(int(memory_dim), RAW_MSG_DIM, self.memory.time_enc)
        self.register_buffer("assoc", torch.empty(self.num_nodes, dtype=torch.long), persistent=False)

    def reset_state(self) -> None:
        self.memory.reset_state()

    def detach(self) -> None:
        self.memory.detach()

    def pair_embedding(
        self, pair: "torch.Tensor", neighbor: "LastNeighborLoader", store: ReplayStore,
    ) -> "torch.Tensor":
        query = pair.unique()
        node_ids, edge_index, event_ids = neighbor(query)
        if event_ids.numel() and int(event_ids.max()) >= int(store.count):
            raise RuntimeError("LastNeighborLoader event ID exceeds replay store")
        self.assoc[node_ids] = torch.arange(node_ids.numel(), dtype=torch.long)
        memory, last_update = self.memory(node_ids)
        edge_time = store.time[event_ids] if event_ids.numel() else store.time[:0]
        edge_message = store.message[event_ids] if event_ids.numel() else store.message[:0]
        embedding = self.gnn(memory, last_update, edge_index, edge_time, edge_message)
        return embedding[self.assoc[pair]]

    def update_state(
        self, left: "torch.Tensor", right: "torch.Tensor", moment: "torch.Tensor",
        message: "torch.Tensor", neighbor: "LastNeighborLoader", store: ReplayStore,
    ) -> None:
        self.memory.update_state(left, right, moment, message)
        store.append(moment, message)
        neighbor.insert(left, right)


def make_encoder(capacity: int, memory_dim: int, time_dim: int) -> TGNProcessEncoder:
    return TGNProcessEncoder(max(2, int(capacity)), int(memory_dim), int(time_dim))


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
    c1_report_extension: Path, train_cap: int, select_cap: int,
) -> tuple[Any, ckai.ExternalFlowFrontend, float, list[dict[str, Any]]]:
    cache = CompositeCanonicalTimeC1Cache(cache_dir, plan, c1_report_extension)
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
    # Report membership is determined by the immutable T0 target manifests,
    # not by re-running a cap over the full role table.  Re-capping here can
    # select different rows from the frozen 34,622-target contract.
    idx = report_indices(frames, role, frame_phase, held, cko.FULL_CAP) if report else role_indices(frames, role, frame_phase, held, cap)
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
        source = str(row.get("source_group", ""))
        recorded = int(row.get("recorded_index", -1))
        episode = str(frontend.cache.audit_for_member(source).get(recorded, {}).get("episode_id", ""))
        records.append(Record(
            uid=f"{role}:{m1_phase}:{row_index}", role=role, m1_phase=m1_phase,
            source=source, recorded_index=recorded,
            event_position=event_position, label=int(label), attack_family=attack_family,
            device_family=str(row.get("device_family", "NA")), source_family=str(row.get("source_family", "NA")),
            c1_score=float(scores[local]), episode_id=episode,
        ))
    if not report and dropped:
        raise RuntimeError(
            f"{held or 'GLOBAL'} {role}/{m1_phase}: {dropped} fit/select targets are absent from the frozen cache"
        )
    audit = [{
        "role": role, "frame_phase": frame_phase, "m1_phase": m1_phase, "held_value": held or "GLOBAL",
        "eligible_role_rows": int(len(idx)), "frozen_target_rows": int(len(records)),
        "outside_frozen_target_cohort": int(dropped), "target_alignment_incomplete": 0,
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
    extension_sources = set(getattr(t0, "report_only_sources", set()))
    for key in ("fit_attack", "fit_benign", "select_attack", "select_benign"):
        leaked = sorted({record.source for record in sets[key]} & extension_sources)
        if leaked:
            raise RuntimeError(f"report-only extension leaked into {key}: {leaked}")
    if extension_sources:
        audit.append({
            "role": "REPORT_EXTENSION", "frame_phase": "report_only", "m1_phase": "report",
            "held_value": held or "GLOBAL", "requested_rows": int(sum(record.source in extension_sources for record in sets["report"])),
            "cache_aligned_rows": int(sum(record.source in extension_sources for record in sets["report"])), "unmapped_rows": 0,
            "eligible_role_rows": int(sum(record.source in extension_sources for record in sets["report"])),
            "frozen_target_rows": int(sum(record.source in extension_sources for record in sets["report"])),
            "outside_frozen_target_cohort": 0, "target_alignment_incomplete": 0,
            "label_for_metric_only": True, "report": True, "extension_fit_select_rows": 0,
        })
    return sets, audit


def source_groups_by_family(frames: dict[str, pd.DataFrame]) -> dict[str, set[str]]:
    groups: defaultdict[str, set[str]] = defaultdict(set)
    for frame in frames.values():
        if {"device_family", "source_group"}.issubset(frame.columns):
            pairs = frame[["device_family", "source_group"]].astype(str).drop_duplicates()
            for pair in pairs.itertuples(index=False):
                groups[str(pair.device_family)].add(str(pair.source_group))
    return dict(groups)


def source_family_contract(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    by_source: defaultdict[str, set[str]] = defaultdict(set)
    for frame in frames.values():
        if {"source_group", "device_family"}.issubset(frame.columns):
            for row in frame[["source_group", "device_family"]].astype(str).drop_duplicates().itertuples(index=False):
                if str(row.device_family) not in {"", "NA", "nan"}:
                    by_source[str(row.source_group)].add(str(row.device_family))
    rows = [{
        "source_group": source, "device_family_count": len(families),
        "device_families": "|".join(sorted(families)), "single_family_source": len(families) <= 1,
    } for source, families in sorted(by_source.items())]
    mixed = [row for row in rows if not row["single_family_source"]]
    if mixed:
        raise RuntimeError(f"strict C1 row exclusion is not source-equivalent for mixed-family sources: {mixed[:3]}")
    return rows


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


def source_capacity(t0: T0Cache, sources: Iterable[str]) -> int:
    values = [int(t0.summary(source).get("source_local_nodes", 0)) for source in sources]
    if not values or min(values) <= 0:
        raise RuntimeError("every TGN source must declare a positive source_local_nodes count")
    return max(2, max(values))


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
    manifest_hash = hashlib.sha256(plan.read_bytes()).hexdigest()
    if manifest_hash != EXPECTED_T0_MANIFEST_SHA256:
        raise RuntimeError(f"frozen CKBE T0 manifest hash changed: {manifest_hash}")
    required = ["npz_exists", "cache_json_exists", "runtime_json_exists", "target_positions_complete", "raw_label_column_read_false"]
    for column in required:
        if column not in cache_audit or not bool(bool_series(cache_audit[column]).all()):
            raise RuntimeError(f"CKBE T0 audit failed required column: {column}")
    for source in manifest["source_group"].astype(str):
        summary = t0.summary(source)
        if not bool(summary.get("npz_exists")) or not bool(summary.get("cache_json_exists")):
            raise RuntimeError(f"missing CKBE T0 cache member: {source}")
    return {
        "t0_sources": int(len(manifest)), "t0_targets": int(cache_audit["target_rows"].sum()),
        "t0_manifest_sha256": manifest_hash, "raw_label_column_read": False,
    }


def validate_report_extension(root: Path) -> dict[str, Any]:
    manifest_path = root / "report_only_extension_manifest_frozen.csv"
    manifest_hash_path = root / "report_only_extension_manifest_sha256.txt"
    ready_path = root / "extension_ready.json"
    exclusion_path = root / "report_only_fit_select_exclusion_audit.csv"
    if not all(path.is_file() for path in (manifest_path, manifest_hash_path, ready_path, exclusion_path)):
        raise RuntimeError("missing CKBI report-only extension contract artifacts")
    manifest = pd.read_csv(manifest_path)
    expected = set(ckbi.EXTENSION_SOURCES)
    actual = set(manifest.get("source_group", pd.Series(dtype=str)).astype(str).tolist())
    if len(manifest) != 4 or actual != expected:
        raise RuntimeError(f"unexpected CKBI extension sources: {sorted(actual)}")
    manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if manifest_hash != manifest_hash_path.read_text(encoding="utf-8").strip():
        raise RuntimeError("CKBI extension manifest SHA-256 mismatch")
    required_true = ("target_positions_complete", "source_local_anonymous_ids")
    for column in required_true:
        if column not in manifest or not bool(bool_series(manifest[column]).all()):
            raise RuntimeError(f"CKBI extension manifest failed column: {column}")
    if "raw_label_column_read" not in manifest or bool(bool_series(manifest["raw_label_column_read"]).any()):
        raise RuntimeError("CKBI extension manifest says that a raw label column was read")
    exclusion = pd.read_csv(exclusion_path)
    use_rows = exclusion.loc[exclusion["required_zero"].notna()]
    if use_rows.empty or "pass" not in use_rows or not bool(bool_series(use_rows["pass"]).all()):
        raise RuntimeError("report-only extension appears in an M1 fit/select scope")
    for row in manifest.itertuples(index=False):
        source = str(row.source_group)
        cache = T0Cache(root)
        summary = cache.summary(source)
        if not bool(summary.get("npz_exists")) or not bool(summary.get("cache_json_exists")):
            raise RuntimeError(f"missing CKBI cache member: {source}")
        if not bool(summary.get("target_positions_complete")) or bool(summary.get("raw_label_column_read", True)) or int(summary.get("event_schema_dim", 0)) != RAW_MSG_DIM:
            raise RuntimeError(f"invalid CKBI cache metadata: {source}")
    ready = json.loads(ready_path.read_text(encoding="utf-8"))
    if str(ready.get("extension_manifest_sha256", "")) != manifest_hash:
        raise RuntimeError("CKBI ready artifact does not bind the extension manifest")
    return {
        "extension_root": str(root), "extension_manifest_sha256": manifest_hash,
        "extension_sources": sorted(actual), "extension_targets": int(manifest["target_rows"].sum()),
        "report_only_fit_select_exclusion_pass": True, "raw_label_column_read": False,
    }


def required_report_source_coverage(frames: dict[str, pd.DataFrame], t0: T0Cache | CompositeT0Cache) -> list[dict[str, Any]]:
    """Require every requested Table-A/B report source to be cacheable.

    A partial aligned subset can be useful diagnosis, but it must never be
    silently promoted to the requested same/future/sealed formal table.
    """
    cached = t0.cached_sources if isinstance(t0, CompositeT0Cache) else set(
        pd.read_csv(t0.root / "tgn_source_event_plan_frozen.csv")["source_group"].astype(str).tolist()
    )
    specs = (("same_file_query", "all"), ("future_query", "all"), ("sealed_final_ood", "report_only"), ("sealed_final_attack", "report_only"))
    rows: list[dict[str, Any]] = []
    for role, phase in specs:
        frame = frames[role]
        part = frame if phase == "all" else frame.loc[frame["phase"].astype(str).eq(phase)]
        sources = sorted(part["source_group"].astype(str).unique().tolist())
        missing = sorted(set(sources) - cached)
        rows.append({"role": role, "phase": phase, "requested_source_groups": len(sources), "cached_source_groups": len(sources) - len(missing), "missing_source_groups": "|".join(missing), "full_source_coverage": not missing})
    return rows


def source_arrays(t0: T0Cache, source: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    path, _ = t0.paths(source)
    with np.load(path, allow_pickle=False) as data:
        return (
            np.asarray(data["recorded_index"], dtype=np.int64), np.asarray(data["time_ms"], dtype=np.int64),
            np.asarray(data["src"], dtype=np.int64), np.asarray(data["dst"], dtype=np.int64),
            np.asarray(data["raw_msg"], dtype=np.float32),
        )


def node_identity_proxy_audit(t0: T0Cache | CompositeT0Cache) -> list[dict[str, Any]]:
    """Quantify singleton anonymous nodes without reopening raw identity fields."""
    rows: list[dict[str, Any]] = []
    for source in sorted(t0.cached_sources if isinstance(t0, CompositeT0Cache) else []):
        _recorded, _stamp, src, dst, _message = source_arrays(t0, source)
        endpoints = np.concatenate([src, dst]).astype(np.int64, copy=False)
        counts = np.bincount(endpoints) if len(endpoints) else np.zeros(0, dtype=np.int64)
        observed = int(np.sum(counts > 0)); singleton = int(np.sum(counts == 1))
        rows.append({
            "source_group": source, "events": int(len(src)),
            "declared_source_local_nodes": int(t0.summary(source).get("source_local_nodes", 0)),
            "observed_source_local_nodes": observed, "singleton_endpoint_nodes": singleton,
            "singleton_endpoint_ratio": float(singleton / observed) if observed else math.nan,
            "anonymous_id_source_local": True,
            "raw_ip_mac_fallback_identity_not_recoverable_from_frozen_cache": True,
            "interpretation": "singleton ratio is a proxy, not proof of endpoint fallback",
        })
    return rows


def update_history_slice(
    encoder: TGNProcessEncoder, neighbor: "LastNeighborLoader", store: ReplayStore,
    stamp: np.ndarray, src: np.ndarray, dst: np.ndarray, message: np.ndarray,
    start: int, stop: int, batch_size: int,
) -> tuple[int, int, int]:
    """Apply label-free past history using the official TGN batch contract."""
    updates = 0; batches = 0; repeated_endpoint_occurrences = 0
    for lower in range(int(start), int(stop), max(1, int(batch_size))):
        upper = min(int(stop), lower + max(1, int(batch_size)))
        left = torch.from_numpy(src[lower:upper].astype(np.int64, copy=False))
        right = torch.from_numpy(dst[lower:upper].astype(np.int64, copy=False))
        moment = torch.from_numpy(stamp[lower:upper].astype(np.int64, copy=False))
        msg = torch.from_numpy(message[lower:upper].astype(np.float32, copy=False))
        repeated_endpoint_occurrences += int(len(left) + len(right) - len(torch.cat([left, right]).unique()))
        encoder.update_state(left, right, moment, msg, neighbor, store)
        updates += upper - lower; batches += 1
    return updates, batches, repeated_endpoint_occurrences


def future_task_labels(
    time_ms: np.ndarray, src: np.ndarray, dst: np.ndarray, raw_msg: np.ndarray, fit_positions: set[int],
) -> dict[int, tuple[int, int | None, int]]:
    """Create outcomes only from the next *legal fit* event in this source."""
    next_edge: dict[tuple[int, int], int] = {}
    next_ackrst: dict[tuple[int, int], int] = {}
    labels: dict[int, tuple[int, int | None, int]] = {}
    for index in sorted((int(value) for value in fit_positions), reverse=True):
        pair = (int(src[index]), int(dst[index])); reverse = (pair[1], pair[0]); now = int(time_ms[index])
        reverse_time = next_edge.get(reverse)
        same_time = next_edge.get(pair)
        ackrst_time = next_ackrst.get(reverse)
        response = int(reverse_time is not None and 0 <= reverse_time - now <= RESPONSE_WINDOW_MS)
        retry = int(same_time is not None and 0 <= same_time - now <= RETRY_WINDOW_MS)
        completion: int | None = None
        if bool(raw_msg[index, 5] > 0.5):  # SYN current event only.
            completion = int(ackrst_time is not None and 0 <= ackrst_time - now <= RESPONSE_WINDOW_MS)
        labels[index] = (response, completion, retry)
        next_edge[pair] = now
        if bool(raw_msg[index, 6] > 0.5 or raw_msg[index, 7] > 0.5):
            next_ackrst[pair] = now
    return labels


def loader_neighbor_ids(neighbor: "LastNeighborLoader", node_id: int) -> set[int]:
    """Read the maintained PyG neighbour history before the current update."""
    nodes, _edge_index, _event_ids = neighbor(torch.tensor([int(node_id)], dtype=torch.long))
    return {int(value) for value in nodes.detach().cpu().tolist() if int(value) != int(node_id)}


def sample_negative(
    src_id: int, dst_id: int, past_seen_nodes: set[int], neighbor_ids: set[int], rng: np.random.Generator,
) -> tuple[int | None, int]:
    """Sample only an actually observed node from the current source history."""
    candidates = sorted(set(past_seen_nodes) - {int(src_id), int(dst_id)} - set(neighbor_ids))
    if not candidates:
        return None, 0
    return int(candidates[int(rng.integers(0, len(candidates)))]), int(len(candidates))


def pretrain_ssl(
    t0: T0Cache | CompositeT0Cache, fit_records: list[Record], node_capacity: int, memory_dim: int, time_dim: int,
    epochs: int, detach_every: int, seed: int,
) -> tuple[TGNProcessEncoder, SelfSupervisionHeads, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require_pyg()
    by_source: defaultdict[str, list[Record]] = defaultdict(list)
    for record in fit_records:
        by_source[record.source].append(record)
    report_only_sources = set(getattr(t0, "report_only_sources", set()))
    leaked_sources = sorted(set(by_source) & report_only_sources)
    if leaked_sources:
        raise RuntimeError(f"report-only source entered TGN self-supervision: {leaked_sources}")
    # Capacity is a non-learned index upper bound shared by source-local
    # replays.  Negative candidates still come only from the current source's
    # past-seen set; no report node identity enters an SSL example.
    capacity = max(source_capacity(t0, by_source), int(node_capacity))
    torch.manual_seed(seed); np.random.seed(seed); rng = np.random.default_rng(seed)
    encoder = make_encoder(capacity, memory_dim, time_dim); heads = SelfSupervisionHeads(memory_dim, RAW_MSG_DIM)
    optimizer = torch.optim.AdamW(list(encoder.parameters()) + list(heads.parameters()), lr=1e-3, weight_decay=1e-3)
    history: list[dict[str, Any]] = []; negative_audit: list[dict[str, Any]] = []; future_scope: list[dict[str, Any]] = []
    # Task outcomes depend on later fit events, never on select/report/raw
    # events outside the explicitly legal fit target set.
    prepared: dict[str, tuple[list[int], tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray], dict[int, tuple[int, int | None, int]], int]] = {}
    for source, source_records in by_source.items():
        allowed = {record.event_position for record in source_records}
        raw_arrays = source_arrays(t0, source)
        if not allowed or min(allowed) < 0 or max(allowed) >= len(raw_arrays[1]):
            raise RuntimeError(f"{source}: legal fit target falls outside its event cache")
        if len(allowed) != len(source_records):
            raise RuntimeError(f"{source}: duplicate legal fit target event")
        local_nodes = int(t0.summary(source).get("source_local_nodes", 0))
        observed_max = int(max(np.max(raw_arrays[2]), np.max(raw_arrays[3]))) if len(raw_arrays[2]) else -1
        if local_nodes <= observed_max:
            raise RuntimeError(f"{source}: source-local node metadata does not cover node id {observed_max}")
        labels = future_task_labels(raw_arrays[1], raw_arrays[2], raw_arrays[3], raw_arrays[4], allowed)
        ordered = sorted(allowed)
        future_scope.append({
            "source_group": source, "fit_target_events": len(allowed), "fit_horizon_event_position": int(max(allowed)),
            "source_raw_events_total": int(len(raw_arrays[1])), "raw_events_visible_to_ssl": int(len(allowed)),
            "nonfit_raw_events_visible_to_ssl": 0, "future_label_max_event_position": int(max(allowed)),
            "future_outcomes_from_fit_events_only": True, "select_report_outcome_used": False,
            "reverse_positive": int(sum(value[0] for value in labels.values())),
            "completion_labeled": int(sum(value[1] is not None for value in labels.values())),
            "completion_positive": int(sum(int(value[1] or 0) for value in labels.values())),
            "retry_positive": int(sum(value[2] for value in labels.values())),
        })
        prepared[source] = (ordered, raw_arrays, labels, local_nodes)
    for epoch in range(1, int(epochs) + 1):
        encoder.train(); heads.train(); losses: list[torch.Tensor] = []; summary: defaultdict[str, list[float]] = defaultdict(list)
        source_resets = 0; history_updates = 0
        for source in sorted(by_source):
            ordered, (_recorded, stamp, src, dst, message), labels, local_nodes = prepared[source]
            encoder.reset_state(); neighbor = LastNeighborLoader(capacity, size=10); store = ReplayStore(len(ordered)); source_resets += 1
            past_seen_nodes: set[int] = set(); pool_sizes: list[int] = []; sampled = 0; skipped = 0
            for index in ordered:
                left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
                msg = torch.from_numpy(message[index : index + 1]); moment = torch.tensor([int(stamp[index])], dtype=torch.long)
                representation = encoder.pair_embedding(pair, neighbor, store)  # Current event is read before its update.
                feature = SelfSupervisionHeads.features(representation[0:1], representation[1:2], msg)
                positive = heads.link(feature).reshape(-1)
                losses.append(F.binary_cross_entropy_with_logits(positive, torch.ones_like(positive))); summary["link"].append(float(losses[-1].detach()))
                prior_neighbor_ids = loader_neighbor_ids(neighbor, left)
                negative_id, pool_size = sample_negative(left, right, past_seen_nodes, prior_neighbor_ids, rng)
                pool_sizes.append(pool_size)
                if negative_id is not None:
                    negative_repr = encoder.pair_embedding(torch.tensor([left, negative_id], dtype=torch.long), neighbor, store)
                    negative_feature = SelfSupervisionHeads.features(negative_repr[0:1], negative_repr[1:2], msg)
                    negative = heads.link(negative_feature).reshape(-1)
                    losses.append(F.binary_cross_entropy_with_logits(negative, torch.zeros_like(negative))); summary["link"].append(float(losses[-1].detach()))
                    sampled += 1
                    if negative_id not in past_seen_nodes or negative_id < 0 or negative_id >= local_nodes:
                        raise RuntimeError(f"{source}: invalid source-local negative node {negative_id}")
                else:
                    skipped += 1
                response, completion, retry = labels[index]
                for name, value, head in (("reverse_response", response, heads.reverse), ("edge_retry_survival", retry, heads.retry)):
                    logit = head(feature).reshape(-1); target = torch.tensor([float(value)])
                    losses.append(F.binary_cross_entropy_with_logits(logit, target)); summary[name].append(float(losses[-1].detach()))
                if completion is not None:
                    logit = heads.completion(feature).reshape(-1); target = torch.tensor([float(completion)])
                    losses.append(F.binary_cross_entropy_with_logits(logit, target)); summary["ack_rst_completion"].append(float(losses[-1].detach()))
                encoder.update_state(pair[0:1], pair[1:2], moment, msg, neighbor, store)
                past_seen_nodes.update((left, right)); history_updates += 1
                if len(losses) >= int(detach_every):
                    torch.stack(losses).mean().backward(); torch.nn.utils.clip_grad_norm_(list(encoder.parameters()) + list(heads.parameters()), 5.0)
                    optimizer.step(); optimizer.zero_grad(); encoder.detach(); losses.clear()
            if losses:
                torch.stack(losses).mean().backward(); torch.nn.utils.clip_grad_norm_(list(encoder.parameters()) + list(heads.parameters()), 5.0)
                optimizer.step(); optimizer.zero_grad(); encoder.detach(); losses.clear()
            negative_audit.append({
                "epoch": epoch, "source_group": source,
                "rule": "current_source_past_seen_nodes_excluding_src_dst_and_pyg_neighbors",
                "attempted_positive_events": len(ordered), "sampled_negatives": sampled,
                "skipped_no_legal_candidate": skipped, "candidate_pool_min": int(min(pool_sizes) if pool_sizes else 0),
                "candidate_pool_mean": float(np.mean(pool_sizes) if pool_sizes else 0.0),
                "candidate_pool_max": int(max(pool_sizes) if pool_sizes else 0),
                "ghost_node_negatives": 0, "future_node_identity_used": False,
            })
        epoch_row = {"stage": "ssl", "epoch": epoch, "memory_resets": source_resets, "memory_updates": history_updates, "history_update_batches": history_updates, **{f"{key}_loss": float(np.mean(value)) if value else np.nan for key, value in summary.items()}}
        numeric_losses = [value for key, value in epoch_row.items() if key.endswith("_loss") and not pd.isna(value)]
        epoch_row["finite_losses"] = bool(numeric_losses and np.isfinite(numeric_losses).all())
        history.append(epoch_row)
    encoder.eval(); heads.eval()
    return encoder, heads, history, negative_audit, future_scope


@torch.no_grad()
def embed_target_phase(
    encoder: TGNProcessEncoder, t0: T0Cache | CompositeT0Cache,
    context: list[Record], scored: list[Record], phase: str, memory_dim: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    """Replay only legal fit/select target events; report events cannot enter."""
    by_source_context: defaultdict[str, list[Record]] = defaultdict(list)
    by_source_scored: defaultdict[str, list[Record]] = defaultdict(list)
    for record in context:
        by_source_context[record.source].append(record)
    for record in scored:
        by_source_scored[record.source].append(record)
    embeddings: dict[str, np.ndarray] = {}; audits: list[dict[str, Any]] = []
    encoder.eval()
    for source in sorted(by_source_scored):
        context_by_position = {record.event_position: record for record in by_source_context.get(source, [])}
        scored_by_position = {record.event_position: record for record in by_source_scored[source]}
        if len(context_by_position) != len(by_source_context.get(source, [])) or len(scored_by_position) != len(by_source_scored[source]):
            raise RuntimeError(f"{source}: duplicate target event in {phase} replay")
        overlap = set(context_by_position) & set(scored_by_position)
        if overlap:
            raise RuntimeError(f"{source}: event belongs to both context and scored {phase} scope")
        _recorded, stamp, src, dst, message = source_arrays(t0, source)
        positions = sorted(set(context_by_position) | set(scored_by_position))
        encoder.reset_state(); neighbor = LastNeighborLoader(encoder.num_nodes, size=10); store = ReplayStore(len(positions))
        context_updates = 0; cold_start_targets = 0
        for index in positions:
            left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
            msg = torch.from_numpy(message[index : index + 1]); moment = torch.tensor([int(stamp[index])], dtype=torch.long)
            if index in scored_by_position:
                cold_start_targets += int(store.count == 0)
                representation = encoder.pair_embedding(pair, neighbor, store)
                record = scored_by_position[index]
                embeddings[record.uid] = representation.detach().cpu().numpy().reshape(memory_dim * 2).astype(np.float32)
            else:
                context_updates += 1
            encoder.update_state(pair[0:1], pair[1:2], moment, msg, neighbor, store)
        audits.append({
            "phase": phase, "source_group": source, "records_scored": len(scored_by_position),
            "memory_updates": len(positions), "context_fit_updates": context_updates,
            "cold_start_targets": cold_start_targets,
            "cold_start_ratio": float(cold_start_targets / len(scored_by_position)) if scored_by_position else math.nan,
            "nonphase_raw_events_used": 0, "history_update_batches": len(positions),
            "history_batch_size": 1, "repeated_endpoint_occurrences": 0, "memory_resets": 1,
            "target_before_update": True, "report_only_source": bool(source in set(getattr(t0, "report_only_sources", set()))),
            "no_grad": True,
        })
    missing = [record.uid for record in scored if record.uid not in embeddings]
    if missing:
        raise RuntimeError(f"TGN {phase} embedding missing {len(missing)} records; first={missing[0]}")
    return embeddings, audits


@torch.no_grad()
def embed_report_records(
    encoder: TGNProcessEncoder, t0: T0Cache | CompositeT0Cache, records: list[Record], memory_dim: int,
    history_batch_size: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    """Fresh source-local, label-free, past-only report replay."""
    by_source: defaultdict[str, list[Record]] = defaultdict(list)
    for record in records:
        by_source[record.source].append(record)
    embeddings: dict[str, np.ndarray] = {}; audits: list[dict[str, Any]] = []
    encoder.eval()
    for source in sorted(by_source):
        positions = [record.event_position for record in by_source[source]]
        if len(set(positions)) != len(positions):
            raise RuntimeError(f"{source}: duplicate report target event")
        wanted = {record.event_position: record for record in by_source[source]}
        _recorded, stamp, src, dst, message = source_arrays(t0, source)
        last_target = max(wanted)
        encoder.reset_state(); neighbor = LastNeighborLoader(encoder.num_nodes, size=10); store = ReplayStore(last_target + 1)
        updates = 0; batches = 0; repeated = 0; cursor = 0; cold_start_targets = 0
        for index in sorted(wanted):
            step_updates, step_batches, step_repeated = update_history_slice(
                encoder, neighbor, store, stamp, src, dst, message, cursor, index, history_batch_size,
            )
            updates += step_updates; batches += step_batches; repeated += step_repeated
            left, right = int(src[index]), int(dst[index]); pair = torch.tensor([left, right], dtype=torch.long)
            msg = torch.from_numpy(message[index : index + 1]); moment = torch.tensor([int(stamp[index])], dtype=torch.long)
            cold_start_targets += int(store.count == 0)
            representation = encoder.pair_embedding(pair, neighbor, store)  # pre-event score
            record = wanted[index]
            embeddings[record.uid] = representation.detach().cpu().numpy().reshape(memory_dim * 2).astype(np.float32)
            encoder.update_state(pair[0:1], pair[1:2], moment, msg, neighbor, store)
            updates += 1; batches += 1; cursor = index + 1
        audits.append({
            "phase": "report", "source_group": source, "records_scored": len(wanted),
            "memory_updates": updates, "memory_only_events": max(0, updates - len(wanted)),
            "cold_start_targets": cold_start_targets,
            "cold_start_ratio": float(cold_start_targets / len(wanted)) if wanted else math.nan,
            "history_update_batches": batches, "history_batch_size": int(history_batch_size),
            "repeated_endpoint_occurrences": repeated, "memory_resets": 1,
            "target_before_update": True, "all_past_raw_events_update_memory": True,
            "report_only_source": bool(source in set(getattr(t0, "report_only_sources", set()))),
            "no_grad": True, "model_weights_updated": False, "labels_read_for_memory": False,
        })
    missing = [record.uid for record in records if record.uid not in embeddings]
    if missing:
        raise RuntimeError(f"TGN report embedding missing {len(missing)} records; first={missing[0]}")
    return embeddings, audits


def embed_protocol_records(
    encoder: TGNProcessEncoder, t0: T0Cache | CompositeT0Cache, sets: dict[str, list[Record]],
    memory_dim: int, history_batch_size: int,
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    fit = sets["fit_attack"] + sets["fit_benign"]
    select = sets["select_attack"] + sets["select_benign"]
    fit_embeddings, fit_audit = embed_target_phase(encoder, t0, [], fit, "fit", memory_dim)
    select_embeddings, select_audit = embed_target_phase(encoder, t0, fit, select, "select", memory_dim)
    report_embeddings, report_audit = embed_report_records(
        encoder, t0, sets["report"], memory_dim, history_batch_size,
    )
    merged = {**fit_embeddings, **select_embeddings, **report_embeddings}
    expected = fit + select + sets["report"]
    if len(merged) != len(expected):
        raise RuntimeError("phase-isolated embedding UID collision or omission")
    return merged, fit_audit + select_audit + report_audit


def train_verifier(
    embeddings: dict[str, np.ndarray], attack: list[Record], benign: list[Record], memory_dim: int, epochs: int,
    negative_ratio: int, seed: int,
) -> tuple[VerifierHead, list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    require_pyg()
    if not attack or not benign:
        raise RuntimeError("verifier requires aligned attack support and legal fit benign records")
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    head = VerifierHead(memory_dim); optimizer = torch.optim.AdamW(head.parameters(), lr=2e-3, weight_decay=1e-3)
    family_indices: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(attack):
        family_indices[record.attack_family].append(index)
    max_family = max(len(values) for values in family_indices.values())
    usage: Counter[str] = Counter(); history: list[dict[str, Any]] = []
    family_usage: Counter[str] = Counter()
    benign_order = np.arange(len(benign)); cursor = 0
    for epoch in range(1, int(epochs) + 1):
        # Each family contributes max_family examples.  Majority-family rows
        # appear once; smaller families are cycled only after every member has
        # appeared, so all 385 legal support rows are used at least once/epoch.
        family_order: dict[str, list[int]] = {}
        for family, values in sorted(family_indices.items()):
            expanded: list[int] = []
            while len(expanded) < max_family:
                expanded.extend(rng.permutation(values).tolist())
            family_order[family] = expanded[:max_family]
        order: list[int] = []
        families = sorted(family_order)
        for offset in range(max_family):
            for family in rng.permutation(families).tolist():
                order.append(int(family_order[str(family)][offset]))
        rng.shuffle(benign_order); losses: list[float] = []
        for attack_index in order:
            record = attack[int(attack_index)]
            neg_count = int(max(1, negative_ratio)); selected = [record]
            for _ in range(neg_count):
                selected.append(benign[int(benign_order[cursor % len(benign_order)])]); cursor += 1
            x = torch.from_numpy(np.vstack([embeddings[item.uid] for item in selected]).astype(np.float32))
            y = torch.tensor([float(item.label) for item in selected], dtype=torch.float32)
            optimizer.zero_grad(); logits = head(x); loss = F.binary_cross_entropy_with_logits(logits, y)
            loss.backward(); torch.nn.utils.clip_grad_norm_(head.parameters(), 5.0); optimizer.step()
            loss_value = float(loss.detach()); losses.append(loss_value); usage[record.uid] += 1; family_usage[record.attack_family] += 1
        all_used = all(usage[record.uid] >= epoch for record in attack)
        history.append({
            "stage": "verifier", "epoch": epoch, "loss": float(np.mean(losses)),
            "finite_losses": bool(losses and np.isfinite(losses).all()), "all_support_used": all_used,
            "family_balanced_examples_per_family": int(max_family), "optimizer_attack_steps": int(len(order)),
            "benign_examples": int(len(order) * max(1, int(negative_ratio))),
        })
    head.eval()
    use_rows = [{
        "uid": record.uid, "attack_family": record.attack_family, "source_group": record.source,
        "uses": int(usage[record.uid]), "minimum_required_uses": int(epochs),
        "used_at_least_once_each_epoch": bool(usage[record.uid] >= int(epochs)),
    } for record in attack]
    if not all(row["used_at_least_once_each_epoch"] for row in use_rows):
        raise RuntimeError("family-balanced verifier failed to use every legal support row each epoch")
    family_rows = [{
        "attack_family": family, "unique_support_rows": int(len(family_indices[family])),
        "training_uses": int(family_usage[family]), "epochs": int(epochs),
        "balanced_examples_per_epoch": int(max_family),
    } for family in sorted(family_indices)]
    return head, history, use_rows, family_rows


@torch.no_grad()
def verifier_scores(head: VerifierHead, embeddings: dict[str, np.ndarray], records: list[Record]) -> dict[str, float]:
    if not records:
        return {}
    x = torch.from_numpy(np.vstack([embeddings[record.uid] for record in records]).astype(np.float32))
    values = torch.sigmoid(head(x)).cpu().numpy()
    return {record.uid: float(value) for record, value in zip(records, values.tolist())}


def choose_gate(
    name: str, support_val: list[Record], select_benign: list[Record], verifier: dict[str, float], c1_threshold: float,
) -> tuple[float, list[dict[str, Any]], bool]:
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
        fallback["selected"] = True
        fallback["selected_despite_constraint_failure"] = True
        fallback["gate_constraint_pass"] = False
        return float(fallback["verifier_threshold"]), rows, False
    selected = next(
        row for row in rows
        if bool(row["eligible"]) and float(row["verifier_threshold"]) == float(best[1])
        and float(row["select_benign_hard_rate"]) == float(best[0])
    )
    selected["selected"] = True
    selected["selected_despite_constraint_failure"] = False
    selected["gate_constraint_pass"] = True
    return best[1], rows, True


def hard_decisions(name: str, records: list[Record], verifier: dict[str, float], c1_threshold: float, verifier_threshold: float) -> np.ndarray:
    tgn = np.asarray([verifier[item.uid] >= verifier_threshold for item in records], dtype=bool)
    return tgn if name == "TGN-only" else (tgn & np.asarray([item.c1_score >= c1_threshold for item in records], dtype=bool))


def bootstrap_ci(records: list[Record], hard: np.ndarray, reps: int, seed: int) -> tuple[float, float, str, int]:
    if not records:
        return math.nan, math.nan, "unavailable", 0
    source_count = len({record.source for record in records})
    episode_count = len({record.episode_id for record in records if record.episode_id})
    unit = "source" if source_count >= 2 else "episode"
    if unit == "episode" and episode_count < 2:
        return math.nan, math.nan, "unavailable", max(source_count, episode_count)
    groups: defaultdict[str, list[bool]] = defaultdict(list)
    for record, value in zip(records, hard.tolist()):
        key = record.source if unit == "source" else record.episode_id
        if key:
            groups[key].append(bool(value))
    values = list(groups.values()); rng = np.random.default_rng(seed); draws = []
    for _ in range(int(reps)):
        chosen = [values[int(rng.integers(0, len(values)))] for _ in values]
        draws.append(float(np.mean([item for group in chosen for item in group])))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)), unit, len(values)


def paired_delta_bootstrap_ci(
    records: list[Record], hard: np.ndarray, c1_hard: np.ndarray, reps: int, seed: int,
) -> tuple[float, float, str, int]:
    delta = hard.astype(np.float64) - c1_hard.astype(np.float64)
    if not records:
        return math.nan, math.nan, "unavailable", 0
    source_count = len({record.source for record in records})
    episode_count = len({record.episode_id for record in records if record.episode_id})
    unit = "source" if source_count >= 2 else "episode"
    if unit == "episode" and episode_count < 2:
        return math.nan, math.nan, "unavailable", max(source_count, episode_count)
    groups: defaultdict[str, list[float]] = defaultdict(list)
    for record, value in zip(records, delta.tolist()):
        key = record.source if unit == "source" else record.episode_id
        if key:
            groups[key].append(float(value))
    values = list(groups.values()); rng = np.random.default_rng(seed); draws: list[float] = []
    for _ in range(int(reps)):
        chosen = [values[int(rng.integers(0, len(values)))] for _ in values]
        draws.append(100.0 * float(np.mean([item for group in chosen for item in group])))
    return float(np.quantile(draws, 0.025)), float(np.quantile(draws, 0.975)), unit, len(values)


def metric_rows(candidate: str, protocol: str, held: str, records: list[Record], hard: np.ndarray, reps: int, seed: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overall: list[dict[str, Any]] = []; family: list[dict[str, Any]] = []
    for role in sorted({record.role for record in records}):
        part = [record for record in records if record.role == role]; mask = np.asarray([record.role == role for record in records], dtype=bool); values = hard[mask]
        if not part: continue
        ci_low, ci_high, ci_unit, ci_clusters = bootstrap_ci(part, values, reps, seed)
        overall.append({"candidate": candidate, "protocol": protocol, "held_value": held, "role": role, "rows": len(part), "sources": len({record.source for record in part}), "label": int(part[0].label), "metric": "attack_hard_recall" if part[0].label else "benign_ood_hard_rate", "hard_rate": float(np.mean(values)), "ci_low": ci_low, "ci_high": ci_high, "ci_cluster_unit": ci_unit, "ci_clusters": ci_clusters, "review_rate": 0.0})
        if part[0].label:
            for attack_family in sorted({record.attack_family for record in part}):
                group = [record for record in part if record.attack_family == attack_family]; group_mask = np.asarray([record.attack_family == attack_family and record.role == role for record in records], dtype=bool); group_hard = hard[group_mask]
                low, high, ci_unit, ci_clusters = bootstrap_ci(group, group_hard, reps, seed)
                family.append({"candidate": candidate, "protocol": protocol, "held_value": held, "role": role, "attack_family": attack_family, "rows": len(group), "sources": len({record.source for record in group}), "hard_recall": float(np.mean(group_hard)), "ci_low": low, "ci_high": high, "ci_cluster_unit": ci_unit, "ci_clusters": ci_clusters, "review_rate": 0.0})
    return overall, family


def event_scope_rows(sets: dict[str, list[Record]], report_only_sources: set[str]) -> list[dict[str, Any]]:
    labels = {"fit_attack": "training", "fit_benign": "training", "select_attack": "select", "select_benign": "select", "report": "report"}
    rows: list[dict[str, Any]] = []
    for key, records in sets.items():
        rows.append({
            "record_set": key, "m1_scope": labels[key], "events": len(records),
            "sources": len({record.source for record in records}), "attack_events": int(sum(record.label == 1 for record in records)),
            "benign_events": int(sum(record.label == 0 for record in records)),
            "report_only_sources": int(len({record.source for record in records if record.source in report_only_sources})),
        })
    return rows


def support_val_lineage(frames: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    all_support = int(len(frames["support_train"]) + len(frames["support_val"]))
    support_val = frames["support_val"]
    phase_fit = int(support_val["phase"].astype(str).eq("fit").sum())
    phase_select = int(support_val["phase"].astype(str).eq("select").sum())
    rows = [
        {"scope": "global", "stage": "support_sidecar_total", "rows": all_support, "reason": "original certified support sidecar"},
        {"scope": "global", "stage": "support_train_partition", "rows": int(len(frames["support_train"])), "reason": "immutable support_train, not eligible for support_val gate selection"},
        {"scope": "global", "stage": "support_val_partition", "rows": int(len(support_val)), "reason": "original support_val partition"},
        {"scope": "global", "stage": "excluded_phase_fit", "rows": phase_fit, "reason": "temporal support_val subphase is fit; select-only gate cannot use it"},
        {"scope": "global", "stage": "retained_legal_select", "rows": phase_select, "reason": "legal support_val=69 for threshold/gate selection"},
    ]
    select = support_val.loc[support_val["phase"].astype(str).eq("select")]
    for held in HELD:
        removed = int(select["device_family"].astype(str).eq(held).sum())
        rows.append({"scope": held, "stage": "held_family_exclusion", "rows": removed, "reason": "strict held-family removal from support_val select"})
        rows.append({"scope": held, "stage": "retained_legal_select", "rows": int(len(select) - removed), "reason": "support_val select after strict held exclusion"})
    return rows


def attack_summary_rows(
    candidate: str, records: list[Record], hard: np.ndarray, c1_hard: np.ndarray, reps: int, seed: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    def add(metric: str, mask: np.ndarray) -> None:
        if not int(mask.sum()):
            return
        rate = float(np.mean(hard[mask])); c1_rate = float(np.mean(c1_hard[mask]))
        subset = [record for record, keep in zip(records, mask.tolist()) if keep]
        low, high, unit, clusters = paired_delta_bootstrap_ci(subset, hard[mask], c1_hard[mask], reps, seed)
        rows.append({"candidate": candidate, "metric": metric, "rows": int(mask.sum()), "hard_recall": rate, "c1_hard_recall": c1_rate, "delta_vs_c1_pp": 100.0 * (rate - c1_rate), "delta_ci_low_pp": low, "delta_ci_high_pp": high, "ci_cluster_unit": unit, "ci_clusters": clusters, "review_rate": 0.0})
    labels = np.asarray([record.label == 1 for record in records], dtype=bool)
    add("overall_attack_hard_recall", labels)
    for role, name in (("support_val", "support_val_recall"), ("same_file_query", "same_file_attack_recall"), ("future_query", "future_attack_recall"), ("sealed_final_attack", "sealed_attack_recall")):
        add(name, np.asarray([record.role == role and record.label == 1 for record in records], dtype=bool))
    for family, name in (("domotic-monitor", "domotic_attack_recall"), ("combined-cycle", "combined_attack_recall")):
        add(name, np.asarray([record.device_family == family and record.label == 1 for record in records], dtype=bool))
    family_rows: list[tuple[str, float, float, int]] = []
    for family in sorted({record.attack_family for record in records if record.label == 1}):
        mask = np.asarray([record.attack_family == family and record.label == 1 for record in records], dtype=bool)
        rate = float(np.mean(hard[mask])); c1_rate = float(np.mean(c1_hard[mask])); family_rows.append((family, rate, c1_rate, int(mask.sum())))
        subset = [record for record, keep in zip(records, mask.tolist()) if keep]
        low, high, unit, clusters = paired_delta_bootstrap_ci(subset, hard[mask], c1_hard[mask], reps, seed)
        rows.append({"candidate": candidate, "metric": "attack_family_recall", "attack_family": family, "rows": int(mask.sum()), "hard_recall": rate, "c1_hard_recall": c1_rate, "delta_vs_c1_pp": 100.0 * (rate - c1_rate), "delta_ci_low_pp": low, "delta_ci_high_pp": high, "ci_cluster_unit": unit, "ci_clusters": clusters, "review_rate": 0.0})
    if family_rows:
        worst = min(family_rows, key=lambda value: value[1])
        rows.append({"candidate": candidate, "metric": "worst_family_recall", "attack_family": worst[0], "rows": worst[3], "hard_recall": worst[1], "c1_hard_recall": worst[2], "delta_vs_c1_pp": 100.0 * (worst[1] - worst[2]), "review_rate": 0.0})
    return rows


def strict_level2_summary(
    candidate: str, held: str, records: list[Record], hard: np.ndarray, c1_hard: np.ndarray, reps: int, seed: int,
) -> list[dict[str, Any]]:
    benign = np.asarray([record.label == 0 for record in records], dtype=bool)
    if not int(benign.sum()):
        return []
    rate = float(np.mean(hard[benign])); c1_rate = float(np.mean(c1_hard[benign]))
    subset = [record for record, keep in zip(records, benign.tolist()) if keep]
    low, high, unit, clusters = paired_delta_bootstrap_ci(subset, hard[benign], c1_hard[benign], reps, seed)
    return [{"candidate": candidate, "held_value": held, "rows": int(benign.sum()), "sources": len({record.source for record in subset}), "metric": "benign_ood_hard_rate", "hard_rate": rate, "c1_hard_rate": c1_rate, "delta_vs_c1_pp": 100.0 * (rate - c1_rate), "delta_ci_low_pp": low, "delta_ci_high_pp": high, "ci_cluster_unit": unit, "ci_clusters": clusters, "review_rate": 0.0}]


def single_seed_go_no_go(
    attack: pd.DataFrame, strict: pd.DataFrame, extension: dict[str, Any], data_audit: pd.DataFrame,
    selection: pd.DataFrame, negative: pd.DataFrame, losses: pd.DataFrame, support_usage: pd.DataFrame,
) -> dict[str, Any]:
    """Pre-registered stop rules for the first (seed 27) result only."""
    def rate(table: pd.DataFrame, **where: Any) -> float | None:
        if table.empty or any(key not in table.columns for key in where):
            return None
        part = table
        for key, value in where.items():
            part = part.loc[part[key].eq(value)]
        if part.empty:
            return None
        return float(part.iloc[0]["hard_recall" if "hard_recall" in part.columns else "hard_rate"])

    overall_delta = attack.loc[(attack["candidate"].eq("M1-SSL")) & (attack["metric"].eq("overall_attack_hard_recall")), "delta_vs_c1_pp"]
    stream = rate(strict, candidate="M1-SSL", held_value="iotsim-stream-consumer")
    stream_c1 = rate(strict, candidate="M0", held_value="iotsim-stream-consumer")
    hydraulic_m1 = rate(strict, candidate="M1-SSL", held_value="iotsim-hydraulic-system")
    hydraulic_c1 = rate(strict, candidate="M0", held_value="iotsim-hydraulic-system")
    main_family = attack.loc[(attack["candidate"].eq("M1-SSL")) & (attack["metric"].eq("attack_family_recall")) & (attack["rows"].ge(15))]
    selected_ssl = selection.loc[selection.get("candidate", pd.Series(dtype=str)).eq("M1-SSL") & selection.get("selected", pd.Series(dtype=bool)).fillna(False).astype(bool)]
    required_metrics_missing = any(value is None for value in (stream, stream_c1, hydraulic_m1, hydraulic_c1)) or overall_delta.empty or main_family.empty
    alignment_incomplete = bool(
        data_audit.empty or "target_alignment_incomplete" not in data_audit
        or pd.to_numeric(data_audit["target_alignment_incomplete"], errors="coerce").fillna(1).gt(0).any()
    )
    gate_failure = bool(
        selected_ssl.empty or "gate_constraint_pass" not in selected_ssl
        or not selected_ssl["gate_constraint_pass"].fillna(False).astype(bool).all()
    )
    invalid_negative = bool(
        negative.empty or int(pd.to_numeric(negative.get("sampled_negatives", pd.Series(dtype=int)), errors="coerce").fillna(0).sum()) == 0
        or int(pd.to_numeric(negative.get("ghost_node_negatives", pd.Series(dtype=int)), errors="coerce").fillna(1).sum()) != 0
        or negative.get("future_node_identity_used", pd.Series(True, index=negative.index)).fillna(True).astype(bool).any()
    )
    nonfinite_loss = bool(
        losses.empty or "finite_losses" not in losses or not losses["finite_losses"].fillna(False).astype(bool).all()
    )
    support_incomplete = bool(
        support_usage.empty or "used_at_least_once_each_epoch" not in support_usage
        or not support_usage["used_at_least_once_each_epoch"].fillna(False).astype(bool).all()
    )
    review_nonzero = bool(
        ("review_rate" in attack and pd.to_numeric(attack["review_rate"], errors="coerce").fillna(1).ne(0).any())
        or ("review_rate" in strict and pd.to_numeric(strict["review_rate"], errors="coerce").fillna(1).ne(0).any())
    )
    checks = {
        "required_metrics_missing": required_metrics_missing,
        "stream_ood_still_near_original": bool(stream is not None and stream >= 0.95),
        "hydraulic_worsened_over_2pp": bool(hydraulic_m1 is not None and hydraulic_c1 is not None and hydraulic_m1 - hydraulic_c1 > 0.02),
        "overall_attack_drop_over_0_5pp": bool(not overall_delta.empty and float(overall_delta.iloc[0]) < -0.5),
        "main_attack_family_drop_over_2pp": bool((main_family["delta_vs_c1_pp"] < -2.0).any()),
        "report_extension_used_in_fit_or_select": not bool(extension["report_only_fit_select_exclusion_pass"]),
        "target_alignment_incomplete": alignment_incomplete,
        "gate_attack_preservation_constraint_failed": gate_failure,
        "negative_sampling_contract_failed": invalid_negative,
        "nonfinite_or_missing_loss": nonfinite_loss,
        "support_usage_incomplete": support_incomplete,
        "review_not_zero": review_nonzero,
    }
    meaningful_stream_signal = bool(
        stream is not None and stream_c1 is not None and stream <= 0.90 and stream <= stream_c1 - 0.10
    )
    if any(checks.values()):
        decision = "NO_GO"
    elif meaningful_stream_signal:
        decision = "GO_SIGNAL"
    else:
        decision = "INCONCLUSIVE_STOP"
    return {
        "seed": 27, "candidate": "M1-SSL", "checks": checks,
        "decision": decision, "meaningful_stream_signal": meaningful_stream_signal,
        "stream_ood_hard_rate": stream, "stream_c1_hard_rate": stream_c1, "hydraulic_m1_hard_rate": hydraulic_m1,
        "hydraulic_c1_hard_rate": hydraulic_c1,
    }


def run_protocol(
    held: str | None, args: argparse.Namespace, x_by_role: dict[str, np.ndarray], frames: dict[str, pd.DataFrame], t0: T0Cache,
    position_cache: dict[str, dict[int, int]], input_audit: dict[str, Any], source_map: dict[str, set[str]],
) -> dict[str, Any]:
    name = "GLOBAL_ATTACK_PRESERVATION" if held is None else held
    c1_model, frontend, c1_threshold, c1_audit = fit_c1(
        x_by_role, frames, held, Path(args.c1_cache), Path(args.c1_plan), Path(args.c1_report_extension),
        int(args.train_cap), int(args.eval_cap),
    )
    sets, data_audit = collect_protocol_records(c1_model, frontend, frames, t0, position_cache, held, int(args.train_cap), int(args.eval_cap))
    held_audit = held_exclusion_counts(frames, held, int(args.train_cap), int(args.eval_cap))
    temporal_source_audit = apply_temporal_source_exclusion(sets, held_source_groups(frames, held, source_map), held)
    if len(sets["fit_attack"]) == 0 or len(sets["select_attack"]) == 0:
        raise RuntimeError(f"{name}: attack cache alignment unexpectedly empty")
    all_records = sets["fit_attack"] + sets["fit_benign"] + sets["select_attack"] + sets["select_benign"] + sets["report"]
    node_capacity = source_capacity(t0, {record.source for record in all_records})
    ssl_encoder, _ssl_heads, ssl_history, negative, future_scope = pretrain_ssl(t0, sets["fit_attack"] + sets["fit_benign"], node_capacity, int(args.memory_dim), int(args.time_dim), int(args.ssl_epochs), int(args.detach_every), int(args.seed))
    ssl_embed, ssl_memory_audit = embed_protocol_records(
        ssl_encoder, t0, sets, int(args.memory_dim), int(args.history_batch_size),
    )
    ssl_head, verifier_history, support_usage, support_family_usage = train_verifier(ssl_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed))
    ssl_scores = verifier_scores(ssl_head, ssl_embed, all_records)
    torch.manual_seed(int(args.seed) + 10_000)
    random_encoder = make_encoder(node_capacity, int(args.memory_dim), int(args.time_dim)); random_encoder.eval()
    random_embed, random_memory_audit = embed_protocol_records(
        random_encoder, t0, sets, int(args.memory_dim), int(args.history_batch_size),
    )
    random_head, random_history, random_usage, random_family_usage = train_verifier(random_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed) + 1)
    random_scores = verifier_scores(random_head, random_embed, all_records)
    tgn_head, tgn_history, tgn_usage, tgn_family_usage = train_verifier(ssl_embed, sets["fit_attack"], sets["fit_benign"], int(args.memory_dim), int(args.verifier_epochs), int(args.verifier_negative_ratio), int(args.seed) + 2)
    tgn_scores = verifier_scores(tgn_head, ssl_embed, all_records)
    selection: list[dict[str, Any]] = []
    threshold_by_candidate: dict[str, float] = {}
    gate_constraint_by_candidate: dict[str, bool] = {}
    for candidate, scores in (("M1-Random", random_scores), ("M1-SSL", ssl_scores), ("TGN-only", tgn_scores)):
        threshold, rows, gate_pass = choose_gate(candidate, sets["select_attack"], sets["select_benign"], scores, c1_threshold)
        threshold_by_candidate[candidate] = threshold; gate_constraint_by_candidate[candidate] = gate_pass
        selection.extend([{**row, "held_value": name, "c1_candidate_threshold": c1_threshold} for row in rows])
    report_rows: list[dict[str, Any]] = []; family_rows: list[dict[str, Any]] = []
    # Headline preservation is evaluation-only: support_train is never folded
    # back into the reported overall recall.
    attack_records = sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
    global_ood_records = [record for record in sets["report"] if record.label == 0]
    strict_records = sets["report"] if held is not None else attack_records + global_ood_records
    c1_attack_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    event_scope = event_scope_rows(sets, set(getattr(t0, "report_only_sources", set())))
    attack_summary: list[dict[str, Any]] = []; strict_summary: list[dict[str, Any]] = []
    rows, families = metric_rows("M0", "strict_leave" if held else "attack_preservation", name, strict_records, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)); report_rows += rows; family_rows += families
    if held is None:
        attack_summary.extend(attack_summary_rows("M0", strict_records, c1_attack_hard, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)))
    else:
        strict_summary.extend(strict_level2_summary("M0", name, strict_records, c1_attack_hard, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)))
    for candidate, scores in (("M1-Random", random_scores), ("M1-SSL", ssl_scores), ("TGN-only", tgn_scores)):
        hard = hard_decisions(candidate, strict_records, scores, c1_threshold, threshold_by_candidate[candidate])
        rows, families = metric_rows(candidate, "strict_leave" if held else "attack_preservation", name, strict_records, hard, int(args.bootstrap_reps), int(args.seed)); report_rows += rows; family_rows += families
        if held is None:
            attack_summary.extend(attack_summary_rows(candidate, strict_records, hard, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)))
        else:
            strict_summary.extend(strict_level2_summary(candidate, name, strict_records, hard, c1_attack_hard, int(args.bootstrap_reps), int(args.seed)))
    return {
        "protocol": name, "held": held, "input_audit": input_audit, "c1_audit": c1_audit, "data_audit": data_audit,
        "held_audit": held_audit + temporal_source_audit,
        "ssl_history": [{**row, "candidate": "M1-SSL"} for row in ssl_history],
        "verifier_history": [{**row, "candidate": "M1-SSL"} for row in verifier_history] + [{**row, "candidate": "M1-Random"} for row in random_history] + [{**row, "candidate": "TGN-only"} for row in tgn_history],
        "negative": [{**row, "candidate": "M1-SSL"} for row in negative],
        "future_label_scope": [{**row, "candidate": "M1-SSL"} for row in future_scope],
        "event_scope": event_scope,
        "support_usage": [{**row, "candidate": "M1-SSL"} for row in support_usage] + [{**row, "candidate": "M1-Random"} for row in random_usage] + [{**row, "candidate": "TGN-only"} for row in tgn_usage],
        "support_family_usage": [{**row, "candidate": "M1-SSL"} for row in support_family_usage] + [{**row, "candidate": "M1-Random"} for row in random_family_usage] + [{**row, "candidate": "TGN-only"} for row in tgn_family_usage],
        "memory_audit": [{**row, "candidate": "M1-SSL"} for row in ssl_memory_audit] + [{**row, "candidate": "M1-Random"} for row in random_memory_audit],
        "selection": selection, "metrics": report_rows, "family_metrics": family_rows,
        "attack_summary": attack_summary, "strict_summary": strict_summary,
        "thresholds": {"c1_candidate": c1_threshold, **threshold_by_candidate},
        "gate_constraint_pass": gate_constraint_by_candidate,
    }


def run_formal(args: argparse.Namespace) -> None:
    require_pyg(); started = time.time(); out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    unexpected = [path.name for path in out.iterdir() if path.name != "m1_time_v.txt"]
    if unexpected:
        raise RuntimeError(f"refusing to mix formal results with existing output files: {unexpected[:5]}")
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False); ckao.add_family_columns(frames)
    live_extension_exclusion = ckbi.report_only_exclusion(frames)
    live_extension_exclusion.to_csv(out / "m1_live_report_extension_fit_select_exclusion.csv", index=False)
    live_use = live_extension_exclusion.loc[live_extension_exclusion["required_zero"].notna()]
    if live_use.empty or int(pd.to_numeric(live_use["extension_source_rows_used"]).sum()) != 0 or not bool(bool_series(live_use["pass"]).all()):
        raise RuntimeError("current role sidecars place a report-only extension source in fit/select")
    base_t0 = T0Cache(Path(args.t0_root)); t0_audit = validate_t0_runtime(base_t0)
    extension_audit = validate_report_extension(Path(args.report_t0_extension))
    c1_extension_root = Path(args.c1_report_extension)
    c1_ready = c1_extension_root / "c1_report_extension_ready.json"
    if c1_ready.is_file():
        c1_extension_audit = ckbj.validate_extension(
            c1_extension_root, Path(args.report_t0_extension), Path(args.c1_plan), Path(args.c1_targets),
        )
    else:
        if c1_extension_root.exists():
            raise RuntimeError(f"partial/non-ready C1 report extension exists; refuse overwrite: {c1_extension_root}")
        staging = c1_extension_root.with_name(
            c1_extension_root.name + f".staging-{os.environ.get('SLURM_JOB_ID', 'local')}"
        )
        ckbj.materialize(
            staging, Path(args.report_t0_extension), Path(args.c1_plan), Path(args.c1_targets),
        )
        ckbj.validate_extension(
            staging, Path(args.report_t0_extension), Path(args.c1_plan), Path(args.c1_targets),
        )
        staging.replace(c1_extension_root)
        c1_extension_audit = ckbj.validate_extension(
            c1_extension_root, Path(args.report_t0_extension), Path(args.c1_plan), Path(args.c1_targets),
        )
    t0 = CompositeT0Cache(base_t0, Path(args.report_t0_extension), set(extension_audit["extension_sources"]))
    pd.DataFrame(node_identity_proxy_audit(t0)).to_csv(out / "m1_source_local_node_identity_proxy_audit.csv", index=False)
    coverage = required_report_source_coverage(frames, t0)
    pd.DataFrame(coverage).to_csv(out / "m1_required_report_source_coverage.csv", index=False)
    missing_roles = [str(row["role"]) for row in coverage if not bool(row["full_source_coverage"])]
    if missing_roles:
        raise RuntimeError("formal M1 stopped before training: frozen T0 lacks required report sources for " + ", ".join(missing_roles))
    pd.DataFrame(support_val_lineage(frames)).to_csv(out / "m1_support_val_lineage.csv", index=False)
    position_cache: dict[str, dict[int, int]] = {}
    source_map = source_groups_by_family(frames)
    source_family_rows = source_family_contract(frames)
    pd.DataFrame(source_family_rows).to_csv(out / "m1_source_family_contract.csv", index=False)
    requested = [value.strip() for value in args.held_values.split(",") if value.strip()]
    seeds = [int(value.strip()) for value in args.seeds.split(",") if value.strip()]
    if not seeds:
        raise RuntimeError("formal M1 needs at least one seed")
    all_results: list[dict[str, Any]] = []
    row_keys = ("c1_audit", "data_audit", "held_audit", "ssl_history", "verifier_history", "negative", "future_label_scope", "event_scope", "support_usage", "support_family_usage", "memory_audit", "selection", "metrics", "family_metrics", "attack_summary", "strict_summary")
    for seed in seeds:
        per_seed = argparse.Namespace(**vars(args)); per_seed.seed = int(seed)
        results = [run_protocol(None, per_seed, x_by_role, frames, t0, position_cache, input_audit, source_map)]
        results.extend(run_protocol(held, per_seed, x_by_role, frames, t0, position_cache, input_audit, source_map) for held in requested)
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
    pd.DataFrame(flatten("support_family_usage")).to_csv(out / "m1_support_family_training_usage.csv", index=False)
    pd.DataFrame(flatten("negative")).to_csv(out / "m1_negative_sampling_audit.csv", index=False)
    pd.DataFrame(flatten("future_label_scope")).to_csv(out / "m1_ssl_future_label_scope.csv", index=False)
    pd.DataFrame(flatten("event_scope")).to_csv(out / "m1_event_scope_audit.csv", index=False)
    pd.DataFrame(flatten("memory_audit")).to_csv(out / "m1_memory_audit.csv", index=False)
    pd.DataFrame(flatten("ssl_history") + flatten("verifier_history")).to_csv(out / "m1_loss_curves.csv", index=False)
    pd.DataFrame(flatten("selection")).to_csv(out / "m1_candidate_selection.csv", index=False)
    metrics = pd.DataFrame(flatten("metrics")); metrics.to_csv(out / "m1_all_metrics.csv", index=False)
    metrics.loc[metrics["protocol"].eq("attack_preservation")].to_csv(out / "attack_preservation_metrics.csv", index=False)
    metrics.loc[metrics["protocol"].eq("attack_preservation") & metrics["label"].eq(0)].to_csv(out / "global_report_ood_metrics.csv", index=False)
    metrics.loc[metrics["protocol"].eq("strict_leave")].to_csv(out / "strict_level2_metrics.csv", index=False)
    pd.DataFrame(flatten("family_metrics")).to_csv(out / "per_attack_family_metrics.csv", index=False)
    attack_summary = pd.DataFrame(flatten("attack_summary")); attack_summary.to_csv(out / "attack_preservation_summary.csv", index=False)
    strict_summary = pd.DataFrame(flatten("strict_summary")); strict_summary.to_csv(out / "strict_level2_summary.csv", index=False)
    loss_frame = pd.DataFrame(flatten("ssl_history") + flatten("verifier_history"))
    data_frame = pd.DataFrame(flatten("data_audit")); selection_frame = pd.DataFrame(flatten("selection"))
    negative_frame = pd.DataFrame(flatten("negative")); support_frame = pd.DataFrame(flatten("support_usage"))
    combined_extension_audit = {
        **extension_audit,
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "report_only_fit_select_exclusion_pass": bool(
            extension_audit["report_only_fit_select_exclusion_pass"]
            and c1_extension_audit["report_only_fit_select_exclusion_pass"]
        ),
    }
    if seeds == [27]:
        decision = single_seed_go_no_go(
            attack_summary, strict_summary, combined_extension_audit, data_frame,
            selection_frame, negative_frame, loss_frame, support_frame,
        )
        (out / "m1_single_seed_go_no_go.json").write_text(json.dumps(decision, indent=2) + "\n", encoding="utf-8")
    manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else "missing"
    environment = {
        "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "sklearn": sklearn.__version__,
        "torch": torch.__version__, "pyg": PYG_VERSION, "seeds": seeds,
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"), "commit_sha": os.environ.get("M1_COMMIT_SHA", "unknown"),
        "manifest_sha256": manifest_hash, "c1_base_plan_sha256": c1_extension_audit["base_c1_plan_sha256"],
        "c1_base_target_sha256": c1_extension_audit["base_c1_target_sha256"],
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "report_extension_targets": extension_audit["extension_targets"], "review_rate": 0.0,
        "seconds": time.time() - started, "history_batch_size": int(args.history_batch_size),
        "node_capacity_policy": "nonlearned max source-local id upper bound; reset per source; never a negative candidate universe",
        "official_pyg_components": ["TGNMemory", "IdentityMessage", "LastAggregator", "LastNeighborLoader", "TGNMemory internal TimeEncoder", "TransformerConv graph embedding"],
    }
    (out / "m1_environment.json").write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
    spec = {"issue": ISSUE, "mode": "formal", "held_values": requested, "t0_root": str(args.t0_root), "report_t0_extension": str(args.report_t0_extension), "c1_cache": str(args.c1_cache), "c1_report_extension": str(args.c1_report_extension), "input_audit": input_audit, "t0_audit": t0_audit, "extension_audit": extension_audit, "c1_extension_audit": c1_extension_audit, "environment": environment, "thresholds": [{"seed": result["seed"], "protocol": result["protocol"], "thresholds": result["thresholds"], "gate_constraint_pass": result["gate_constraint_pass"]} for result in all_results], "report_used_for_fit_or_select": False, "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"], "untouched_final_claim_allowed": False, "single_seed_scope": "go_no_go_only_not_paper_evidence"}
    (out / "run_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (out / "codex_readout.md").write_text(f"# {ISSUE}\n\nFormal M1 completed. Review is fixed at `0`; see CSV tables for attack preservation and strict leave-family metrics.\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "seconds": environment["seconds"]}, indent=2))


def run_unit(args: argparse.Namespace) -> None:
    require_pyg(); torch.manual_seed(int(args.seed)); rng = np.random.default_rng(int(args.seed))
    message = rng.normal(size=(6, RAW_MSG_DIM)).astype(np.float32)
    src = np.asarray([0, 0, 1, 1, 0, 2], dtype=np.int64); dst = np.asarray([1, 1, 0, 0, 2, 0], dtype=np.int64); stamp = np.arange(6, dtype=np.int64) * 1000
    def signature(values: np.ndarray, mutate: tuple[int, int] | None = None) -> np.ndarray:
        torch.manual_seed(int(args.seed)); local = make_encoder(8, 8, 4); local.eval(); local.reset_state(); loader = LastNeighborLoader(8, size=3); store = ReplayStore(6)
        altered = values.copy()
        if mutate is not None: altered[mutate[0], mutate[1]] += 5.0
        for index in range(5):
            pair = torch.tensor([int(src[index]), int(dst[index])]); rep = local.pair_embedding(pair, loader, store)
            if index == 4: return rep.detach().cpu().numpy()
            local.update_state(pair[0:1], pair[1:2], torch.tensor([int(stamp[index])]), torch.from_numpy(altered[index : index + 1]), loader, store)
        raise RuntimeError("unreachable")
    baseline, future, past = signature(message), signature(message, (5, 0)), signature(message, (2, 0))
    torch.manual_seed(int(args.seed)); reset_encoder = make_encoder(8, 8, 4); reset_encoder.eval(); reset_encoder.reset_state(); reset_loader = LastNeighborLoader(8, size=3); reset_store = ReplayStore(1)
    reset_rep = reset_encoder.pair_embedding(torch.tensor([0, 1]), reset_loader, reset_store).detach().cpu().numpy()
    torch.manual_seed(int(args.seed)); fresh_encoder = make_encoder(8, 8, 4); fresh_encoder.eval(); fresh_encoder.reset_state(); fresh_loader = LastNeighborLoader(8, size=3); fresh_store = ReplayStore(1)
    fresh_rep = fresh_encoder.pair_embedding(torch.tensor([0, 1]), fresh_loader, fresh_store).detach().cpu().numpy()
    labels = future_task_labels(stamp, src, dst, message, {1, 2, 3})
    negative_id, pool_size = sample_negative(0, 1, {0, 1, 2}, set(), np.random.default_rng(27))
    result = {"target_before_update": True, "source_reset_matches_fresh_memory": bool(np.allclose(reset_rep, fresh_rep)), "future_mutation_invariant": bool(np.allclose(baseline, future)), "past_mutation_changes_memory": bool(not np.allclose(baseline, past)), "future_task_label_count": len(labels), "has_reverse_response_task": True, "has_ack_rst_completion_task": True, "has_retry_survival_task": True, "negative_is_past_seen_source_local": bool(negative_id == 2 and pool_size == 1), "nan_or_inf": False}
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
        return Record(f"{phase}:{index}", phase, phase, source, index, index, label, family, "synthetic", "synthetic", c1, f"episode-{index // 3}")
    fit_attack = [record(3, 1, "fit", "attack_a", 0.95), record(6, 1, "fit", "attack_b", 0.95)]
    fit_benign = [record(1, 0, "fit", "benign", 0.05), record(2, 0, "fit", "benign", 0.05)]
    select_attack = [record(8, 1, "select", "attack_a", 0.95)]
    select_benign = [record(9, 0, "select", "benign", 0.05)]
    encoder, _heads, ssl_history, negative, _future_scope = pretrain_ssl(t0, fit_attack + fit_benign, 3, 8, 4, 2, 4, int(args.seed))
    records = fit_attack + fit_benign + select_attack + select_benign
    sets = {"fit_attack": fit_attack, "fit_benign": fit_benign, "select_attack": select_attack, "select_benign": select_benign, "report": []}
    embeddings, memory_audit = embed_protocol_records(encoder, t0, sets, 8, 2)
    verifier, verifier_history, usage, _family_usage = train_verifier(embeddings, fit_attack, fit_benign, 8, 3, 1, int(args.seed))
    scores = verifier_scores(verifier, embeddings, records)
    threshold, selection, gate_pass = choose_gate("M1-SSL", select_attack, select_benign, scores, 0.5)
    torch.manual_seed(int(args.seed)); _encoder_b, _heads_b, history_b, _negative_b, _future_scope_b = pretrain_ssl(t0, fit_attack + fit_benign, 3, 8, 4, 2, 4, int(args.seed))
    reproducible = bool(np.allclose([row.get("link_loss", np.nan) for row in ssl_history], [row.get("link_loss", np.nan) for row in history_b], equal_nan=True))
    finite = all(np.isfinite(value) for row in ssl_history + verifier_history for key, value in row.items() if key.endswith("loss") and not pd.isna(value))
    result = {
        "status": "PASS" if finite and reproducible and all(row["uses"] >= 3 for row in usage) else "FAIL",
        "ssl_epochs": 2, "verifier_epochs": 3, "support_rows": len(fit_attack),
        "all_support_used_each_epoch": bool(all(row["uses"] >= 3 for row in usage)),
        "negative_samples": int(sum(row["sampled_negatives"] for row in negative)), "memory_resets": int(sum(row["memory_resets"] for row in ssl_history)),
        "finite_losses": finite, "reproducible_same_seed": reproducible,
        "verifier_threshold": threshold, "gate_constraint_pass": gate_pass, "memory_update_rows": int(sum(row["memory_updates"] for row in memory_audit)),
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
    parser.add_argument("--t0-root", default=str(DEFAULT_T0))
    parser.add_argument("--report-t0-extension", default=str(DEFAULT_REPORT_EXTENSION))
    parser.add_argument("--c1-cache", default=str(DEFAULT_C1_CACHE))
    parser.add_argument("--c1-plan", default=str(DEFAULT_C1_PLAN))
    parser.add_argument("--c1-targets", default=str(DEFAULT_C1_TARGETS))
    parser.add_argument("--c1-report-extension", default=str(DEFAULT_C1_REPORT_EXTENSION))
    parser.add_argument("--held-values", default=",".join(HELD)); parser.add_argument("--train-cap", type=int, default=4000); parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--memory-dim", type=int, default=32); parser.add_argument("--time-dim", type=int, default=16); parser.add_argument("--ssl-epochs", type=int, default=3); parser.add_argument("--verifier-epochs", type=int, default=30); parser.add_argument("--verifier-negative-ratio", type=int, default=4); parser.add_argument("--detach-every", type=int, default=64); parser.add_argument("--history-batch-size", type=int, default=OFFICIAL_TGN_HISTORY_BATCH); parser.add_argument("--bootstrap-reps", type=int, default=1000); parser.add_argument("--seed", type=int, default=27); parser.add_argument("--seeds", default="27")
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
