"""CKBB: E/R/H attention smoke under strict leave-device-family protocol.

This is a deliberately small but *structural* next experiment after CKAW/CKAX/
CKAY.  It does not tune a C1 score.  It tests whether three separately useful
pieces of deployment-available evidence improve the Level-2 failure:

E  current flow / interaction evidence from immutable, label-free CKAW cache;
R  a source-relative, robust baseline computed only from timestamp-earlier
   unlabeled packets in the same raw source file;
H  a label-free 60-second source episode, pooled with attention rather than
   CKAY's mean/max/std summary.

Important contract
------------------
* Raw packet truth labels are never read by the R frontend.
* A target is featurized before it updates its historical state.
* `fit`, `select`, and report roles never share an episode bag.  This is a
  conservative offline safety boundary: report rows cannot influence fit or
  threshold construction through attention pooling.
* Attention is auxiliary.  Every support packet remains an independent member
  of the packet loss; 385 support rows are not reduced to the roughly 42
  positive bags seen in CKAY.
* This remains a development canary, not a fresh untouched final test: the
  held families have already informed route selection.

Candidates
----------
D0 E HistGB control; D1 E MLP control; D2 E+R packet MLP; D3 E+H joint
packet/bag attention; D4 E+R+H joint attention.  Review is disabled in this
first discrimination probe, so a lower hard rate cannot be cosmetic review
routing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
import zipfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw  # noqa: E402
import issue27ckax_episode_head_strict_l2_smoke_v1 as ckax  # noqa: E402
import issue27ckay_episode_pooling_strict_l2_smoke_v1 as ckay  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
except Exception as exc:  # pragma: no cover - explicit runtime contract
    raise RuntimeError("CKBB requires the established local/HPC torch environment") from exc


ISSUE = "issue27ckbb_erh_attention_strict_l2_smoke_v1_2026-07-11"
ROOT = cko.ROOT
DEFAULT_CKAW = ROOT / "runs" / "issue27ckaw_canonical_interaction_episode_frontend_v1_2026-07-10_local_150k"
DEFAULT_OUT = ROOT / "runs" / f"{ISSUE}_local_150k"
HELD = [
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "domotic-monitor",
    "combined-cycle",
    "iotsim-ip-camera-street",
]
EVAL = {
    "ood_val": "select",
    "ood_stress": "select",
    "future_query": "select",
    "sealed_final_ood": "all",
    "sealed_final_attack": "all",
}

BASELINE_SECONDS = 5.0
BASELINE_SNAPSHOTS = 96
BASELINE_MIN_SNAPSHOTS = 8
R_FEATURE_NAMES = [
    "r_ready",
    "r_snapshot_count_log",
    "r_src_rate_robust_z",
    "r_src_fanout_robust_z",
    "r_src_port_robust_z",
    "r_src_short_long_robust_z",
    "r_pair_reverse_balance_robust_z",
    "r_src_new_destination_robust_z",
    "r_src_new_port_robust_z",
]


def log1p(value: float) -> float:
    return float(math.log1p(max(0.0, float(value))))


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def coalesce(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def purge(events: deque[tuple[Any, ...]], now: float, window: float) -> None:
    while events and float(events[0][0]) < now - float(window):
        events.popleft()


def robust_z(value: float, snapshots: deque[np.ndarray], column: int) -> float:
    """Past-only median/MAD residual; no truth or model state is involved."""
    if len(snapshots) < BASELINE_MIN_SNAPSHOTS:
        return 0.0
    history = np.asarray(snapshots, dtype=np.float32)[:, int(column)]
    median = float(np.median(history))
    mad = float(np.median(np.abs(history - median)))
    scale = max(1e-3, 1.4826 * mad)
    return float(np.clip((float(value) - median) / scale, -12.0, 12.0))


class RelativeBaselineBuilder:
    """Build source-relative R features from raw label-free packet history.

    The builder intentionally has no `label` field in its CSV projection.  A
    snapshot is written only after an event has been appended, so a target's R
    vector cannot use itself or any timestamp-later event.
    """

    def __init__(self, raw_zip: Path):
        self.raw_zip = Path(raw_zip)

    def _read_prefix(self, member: str, nrows: int) -> pd.DataFrame:
        with zipfile.ZipFile(self.raw_zip) as archive:
            with archive.open(member) as handle:
                return pd.read_csv(
                    handle,
                    usecols=lambda name: name in ckaw.RAW_USECOLS,
                    nrows=int(nrows),
                    low_memory=False,
                )

    def build(self, member: str, target_indices: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]], dict[str, Any]]:
        targets = np.sort(np.unique(np.asarray(target_indices, dtype=np.int64)))
        if not len(targets):
            return np.zeros((0, len(R_FEATURE_NAMES)), dtype=np.float32), [], {"source_group": member, "requested_rows": 0}
        started = time.time()
        frame = self._read_prefix(member, int(targets[-1]) + 1)
        if len(frame) <= int(targets[-1]):
            raise RuntimeError(f"{member}: missing raw prefix through recorded index {int(targets[-1])}")
        seconds = ckaw.ckat._raw_time_seconds(frame.get("frame.time", pd.Series(np.nan, index=frame.index)))
        order, finite, violations = ckaw.ckat._canonical_order(seconds)
        finite_order = order[finite[order]]
        base = float(np.nanmin(seconds[finite])) if bool(finite.any()) else 0.0
        target_set = set(int(value) for value in targets.tolist())

        proto_text = frame.get("frame.protocols", pd.Series("", index=frame.index)).astype(str).to_numpy()
        ip_src = frame.get("ip.src", pd.Series("", index=frame.index)).to_numpy()
        ip_dst = frame.get("ip.dst", pd.Series("", index=frame.index)).to_numpy()
        eth_src = frame.get("eth.src", pd.Series("", index=frame.index)).to_numpy()
        eth_dst = frame.get("eth.dst", pd.Series("", index=frame.index)).to_numpy()
        ip_proto = pd.to_numeric(frame.get("ip.proto", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
        tcp_dst = pd.to_numeric(frame.get("tcp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
        udp_dst = pd.to_numeric(frame.get("udp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()

        src_short: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        src_long: dict[str, deque[tuple[Any, ...]]] = defaultdict(deque)
        pair_long: dict[tuple[str, str], deque[tuple[Any, ...]]] = defaultdict(deque)
        snapshots: dict[str, deque[np.ndarray]] = defaultdict(lambda: deque(maxlen=BASELINE_SNAPSHOTS))
        last_snapshot: dict[str, float] = {}
        features: dict[int, np.ndarray] = {}
        audits: list[dict[str, Any]] = []

        for rank, ridx in enumerate(finite_order.tolist()):
            now = float(seconds[ridx] - base)
            proto = str(proto_text[ridx]).lower()
            src = coalesce(ip_src[ridx], eth_src[ridx], f"row{ridx}:src")
            dst = coalesce(ip_dst[ridx], eth_dst[ridx], f"row{ridx}:dst")
            dport = int(tcp_dst[ridx] if tcp_dst[ridx] > 0 else udp_dst[ridx])
            pair, reverse = (src, dst), (dst, src)
            for events, window in (
                (src_short[src], ckaw.WINDOW_SHORT),
                (src_long[src], ckaw.WINDOW_LONG),
                (pair_long[pair], ckaw.WINDOW_LONG),
                (pair_long[reverse], ckaw.WINDOW_LONG),
            ):
                purge(events, now, window)

            short_events, long_events = src_short[src], src_long[src]
            pair_events, reverse_events = pair_long[pair], pair_long[reverse]
            long_dst = {event[2] for event in long_events}
            long_ports = {event[3] for event in long_events}
            current = np.asarray(
                [
                    log1p(len(long_events) / max(1.0, ckaw.WINDOW_LONG)),
                    log1p(len(long_dst)),
                    log1p(len(long_ports)),
                    float(len(short_events) / max(1.0, len(long_events))),
                    float((len(pair_events) - len(reverse_events)) / max(1.0, len(pair_events) + len(reverse_events))),
                    float(dst not in long_dst),
                    float(dport not in long_ports),
                ],
                dtype=np.float32,
            )
            prior = snapshots[src]
            if ridx in target_set:
                values = np.asarray(
                    [
                        float(len(prior) >= BASELINE_MIN_SNAPSHOTS),
                        log1p(len(prior)),
                        *[robust_z(float(current[col]), prior, col) for col in range(current.shape[0])],
                    ],
                    dtype=np.float32,
                )
                features[ridx] = values
                audits.append(
                    {
                        "recorded_index": int(ridx),
                        "source_entity": src,
                        "canonical_rank": int(rank),
                        "baseline_snapshots_before_target": int(len(prior)),
                        "baseline_ready": bool(len(prior) >= BASELINE_MIN_SNAPSHOTS),
                        "raw_label_column_read": False,
                        "chronology_status": "CANONICAL_TIMESTAMP_PAST_ONLY",
                    }
                )

            # Append after the target calculation.  This is unlabeled live
            # history; it is deliberately not a truth-cleaned normal state.
            event = (now, src, dst, dport)
            src_short[src].append(event)
            src_long[src].append(event)
            pair_long[pair].append(event)
            last = last_snapshot.get(src)
            if last is None or now - last >= BASELINE_SECONDS:
                snapshots[src].append(current)
                last_snapshot[src] = now

        for ridx in targets.tolist():
            if int(ridx) not in features:
                features[int(ridx)] = np.zeros(len(R_FEATURE_NAMES), dtype=np.float32)
                audits.append(
                    {
                        "recorded_index": int(ridx),
                        "baseline_ready": False,
                        "raw_label_column_read": False,
                        "chronology_status": "TARGET_TIMESTAMP_UNPARSEABLE",
                    }
                )
        matrix = np.vstack([features[int(index)] for index in targets]).astype(np.float32)
        summary = {
            "source_group": member,
            "requested_rows": int(len(targets)),
            "max_recorded_index": int(targets[-1]),
            "processed_prefix_rows": int(len(frame)),
            "feature_dim": len(R_FEATURE_NAMES),
            "raw_label_column_read": False,
            "timestamp_parse_failures": int((~finite).sum()),
            "recorded_order_timestamp_violations": int(violations),
            "baseline_seconds": BASELINE_SECONDS,
            "baseline_snapshots": BASELINE_SNAPSHOTS,
            "seconds": time.time() - started,
        }
        return matrix, audits, summary


class RelativeCache:
    def __init__(self, root: Path, plan_path: Path, evidence_cache_root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.evidence_cache_root = Path(evidence_cache_root)
        self.plan = pd.read_csv(plan_path)
        self.keys = {str(row.source_group): str(row.source_cache_key) for row in self.plan.itertuples()}
        self.data: dict[str, dict[int, np.ndarray]] = {}

    def ensure(self) -> list[dict[str, Any]]:
        builder = RelativeBaselineBuilder(cko.GOTHAM_ZIP)
        summary: list[dict[str, Any]] = []
        for row in self.plan.itertuples():
            source, key = str(row.source_group), str(row.source_cache_key)
            data_path, audit_path = self.root / f"{key}.npz", self.root / f"{key}.json"
            if data_path.exists() and audit_path.exists():
                summary.append(json.loads(audit_path.read_text(encoding="utf-8"))["source_audit"])
                continue
            target = np.load(self.evidence_cache_root / "canonical_episode_cache" / f"{key}.npz")["recorded_index"]
            matrix, audits, audit = builder.build(source, target)
            np.savez_compressed(data_path, recorded_index=target, features=matrix)
            audit_path.write_text(json.dumps({"source_audit": audit, "target_audit": audits}, ensure_ascii=False), encoding="utf-8")
            summary.append(audit)
        return summary

    def get(self, source: str, index: int) -> np.ndarray | None:
        source = str(source)
        if source not in self.keys:
            return None
        if source not in self.data:
            key = self.keys[source]
            payload = np.load(self.root / f"{key}.npz")
            self.data[source] = {int(idx): payload["features"][pos] for pos, idx in enumerate(payload["recorded_index"])}
        return self.data[source].get(int(index))


@dataclass
class Rows:
    e: np.ndarray
    r: np.ndarray
    y: np.ndarray
    episode: list[str]
    raw_index: np.ndarray


def collect_rows(
    e_cache: ckay.Cache,
    r_cache: RelativeCache,
    frames: dict[str, pd.DataFrame],
    role: str,
    phase: str,
    held: str,
    include_held: bool,
    cap: int,
    label: int,
) -> Rows:
    idx = ckao.role_indices_filtered(
        frames,
        role,
        phase,
        cap,
        include=("device_family", held) if include_held else None,
        exclude=None if include_held else ("device_family", held),
    )
    e_values: list[np.ndarray] = []
    r_values: list[np.ndarray] = []
    episode: list[str] = []
    kept: list[int] = []
    for row_index in idx.tolist():
        row = frames[role].iloc[int(row_index)]
        source = str(row.get("source_group", ""))
        recorded = int(row.get("recorded_index", -1))
        evidence = e_cache.get(source, recorded)
        residual = r_cache.get(source, recorded)
        if evidence is None or residual is None:
            continue
        e_vector, episode_id = evidence
        # Role namespaces prevent report or select records from contributing to
        # a fit bag.  The episode id itself is label-free frontend metadata.
        episode.append(f"{role}|{phase}|{episode_id or f'singleton:{source}:{recorded}'}")
        e_values.append(np.asarray(e_vector, dtype=np.float32))
        r_values.append(np.asarray(residual, dtype=np.float32))
        kept.append(int(row_index))
    return Rows(
        e=np.vstack(e_values).astype(np.float32) if e_values else np.zeros((0, len(ckaw.FEATURE_NAMES)), dtype=np.float32),
        r=np.vstack(r_values).astype(np.float32) if r_values else np.zeros((0, len(R_FEATURE_NAMES)), dtype=np.float32),
        y=np.full(len(kept), int(label), dtype=np.float32),
        episode=episode,
        raw_index=np.asarray(kept, dtype=np.int64),
    )


def concat_rows(parts: list[Rows]) -> Rows:
    valid = [part for part in parts if len(part.y)]
    if not valid:
        return Rows(np.zeros((0, len(ckaw.FEATURE_NAMES)), dtype=np.float32), np.zeros((0, len(R_FEATURE_NAMES)), dtype=np.float32), np.zeros(0, dtype=np.float32), [], np.zeros(0, dtype=np.int64))
    return Rows(
        e=np.vstack([part.e for part in valid]),
        r=np.vstack([part.r for part in valid]),
        y=np.concatenate([part.y for part in valid]),
        episode=sum([part.episode for part in valid], []),
        raw_index=np.concatenate([part.raw_index for part in valid]),
    )


def standardize(fit: np.ndarray, value: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = fit.mean(axis=0)
    scale = fit.std(axis=0)
    scale[scale < 1e-6] = 1.0
    return np.nan_to_num((fit - mean) / scale).astype(np.float32), np.nan_to_num((value - mean) / scale).astype(np.float32), np.column_stack([mean, scale]).astype(np.float32)


class FusionNet(nn.Module):
    def __init__(self, e_dim: int, r_dim: int, use_r: bool, use_h: bool):
        super().__init__()
        self.use_r, self.use_h = bool(use_r), bool(use_h)
        self.e_encoder = nn.Sequential(nn.Linear(e_dim, 96), nn.LayerNorm(96), nn.GELU(), nn.Dropout(0.10), nn.Linear(96, 48), nn.GELU())
        self.r_encoder = nn.Sequential(nn.Linear(r_dim, 24), nn.GELU(), nn.Linear(24, 48), nn.GELU()) if self.use_r else None
        self.instance = nn.Linear(48, 1)
        if self.use_h:
            self.attention = nn.Sequential(nn.Linear(48, 32), nn.Tanh(), nn.Linear(32, 1))
            self.bag = nn.Linear(48, 1)
        else:
            self.attention = None
            self.bag = None

    def encode(self, e: torch.Tensor, r: torch.Tensor) -> torch.Tensor:
        value = self.e_encoder(e)
        if self.use_r and self.r_encoder is not None:
            value = value + self.r_encoder(r)
        return value

    def flow_logits(self, e: torch.Tensor, r: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        embedding = self.encode(e, r)
        return self.instance(embedding).squeeze(1), embedding

    def bag_logits(self, embedding: torch.Tensor, packed: tuple[torch.Tensor, torch.Tensor]) -> tuple[torch.Tensor, torch.Tensor]:
        if not self.use_h or self.attention is None or self.bag is None:
            raise RuntimeError("bag_logits requested for an instance-only model")
        indices, mask = packed
        # A padded, masked implementation is materially faster than looping
        # bag-by-bag, while retaining exactly the same set/attention semantics.
        safe = indices.clamp_min(0)
        values = embedding.index_select(0, safe.reshape(-1)).reshape(*safe.shape, embedding.shape[1])
        weights = self.attention(values).squeeze(2).masked_fill(~mask, -1e9)
        weights = torch.softmax(weights, dim=1)
        pooled = torch.sum(weights[:, :, None] * values * mask[:, :, None], dim=1)
        bag_logits = self.bag(pooled).squeeze(1)
        member_logits = torch.zeros(embedding.shape[0], dtype=embedding.dtype, device=embedding.device)
        flat_indices = indices[mask]
        flat_scores = bag_logits[:, None].expand_as(indices)[mask]
        member_logits.index_copy_(0, flat_indices, flat_scores)
        return bag_logits, member_logits


def bag_members(episode: list[str]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    bucket: dict[str, list[int]] = defaultdict(list)
    for position, key in enumerate(episode):
        bucket[str(key)].append(position)
    names = sorted(bucket)
    max_members = max(len(bucket[name]) for name in names)
    indices = np.full((len(names), max_members), -1, dtype=np.int64)
    mask = np.zeros((len(names), max_members), dtype=bool)
    for row, name in enumerate(names):
        members = np.asarray(bucket[name], dtype=np.int64)
        indices[row, : len(members)] = members
        mask[row, : len(members)] = True
    return indices, mask, np.asarray([bucket[name][0] for name in names], dtype=np.int64), names


def fit_fusion(e: np.ndarray, r: np.ndarray, y: np.ndarray, episodes: list[str], use_r: bool, use_h: bool, epochs: int) -> FusionNet:
    torch.manual_seed(27)
    np.random.seed(27)
    model = FusionNet(e.shape[1], r.shape[1], use_r, use_h)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1.5e-3, weight_decay=2e-3)
    e_t, r_t, y_t = torch.from_numpy(e), torch.from_numpy(r), torch.from_numpy(y)
    positive_weight = torch.tensor(float(max(1.0, (y == 0).sum() / max(1, (y == 1).sum()))), dtype=torch.float32)
    group_index, group_mask, first, _ = bag_members(episodes)
    packed = (torch.from_numpy(group_index), torch.from_numpy(group_mask))
    bag_targets = y_t[torch.from_numpy(first)]
    for _epoch in range(int(epochs)):
        optimizer.zero_grad()
        instance, embedding = model.flow_logits(e_t, r_t)
        flow_loss = F.binary_cross_entropy_with_logits(instance, y_t, pos_weight=positive_weight)
        if use_h:
            bag_score, bag_per_member = model.bag_logits(embedding, packed)
            bag_loss = F.binary_cross_entropy_with_logits(bag_score, bag_targets, pos_weight=positive_weight)
            final = instance + 0.60 * bag_per_member
            final_loss = F.binary_cross_entropy_with_logits(final, y_t, pos_weight=positive_weight)
            loss = flow_loss + 0.60 * bag_loss + 0.75 * final_loss
        else:
            loss = flow_loss
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
        optimizer.step()
    model.eval()
    return model


def neural_score(model: FusionNet, e: np.ndarray, r: np.ndarray, episodes: list[str]) -> tuple[np.ndarray, int]:
    if not len(e):
        return np.zeros(0, dtype=np.float32), 0
    with torch.no_grad():
        instance, embedding = model.flow_logits(torch.from_numpy(e), torch.from_numpy(r))
        if model.use_h:
            group_index, group_mask, _first, _names = bag_members(episodes)
            _bag, per_member = model.bag_logits(embedding, (torch.from_numpy(group_index), torch.from_numpy(group_mask)))
            logits = instance + 0.60 * per_member
            count = len(_names)
        else:
            logits, count = instance, len(e)
        return torch.sigmoid(logits).cpu().numpy().astype(np.float32), int(count)


def role_rows(
    e_cache: ckay.Cache,
    r_cache: RelativeCache,
    frames: dict[str, pd.DataFrame],
    held: str,
    role: str,
    phase: str,
    cap: int,
    label: int,
    include: bool,
) -> Rows:
    return collect_rows(e_cache, r_cache, frames, role, phase, held, include, cap, label)


def train_rows(e_cache: ckay.Cache, r_cache: RelativeCache, frames: dict[str, pd.DataFrame], held: str, cap: int) -> tuple[Rows, list[dict[str, Any]]]:
    parts: list[Rows] = []
    audit: list[dict[str, Any]] = []
    for role, label in (("support_train", 1), ("id_calib", 0), ("ood_val", 0), ("ood_stress", 0)):
        part = role_rows(e_cache, r_cache, frames, held, role, "fit", cko.FULL_CAP if role == "support_train" else cap, label, False)
        parts.append(part)
        audit.append({"held_value": held, "role": role, "phase": "fit", "label": label, "rows": len(part.y), "episodes": len(set(part.episode)), "held_excluded": True})
    return concat_rows(parts), audit


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()
    e_root = Path(args.ckaw_root)
    plan_path = Path(args.plan_path) if args.plan_path else e_root / "episode_source_plan.csv"
    e_cache = ckay.Cache(e_root, str(plan_path))
    r_cache = RelativeCache(out / "relative_baseline_cache", plan_path, e_root)
    cache_audit = r_cache.ensure()
    pd.DataFrame(cache_audit).to_csv(out / "relative_baseline_cache_audit.csv", index=False)

    _, frames, _, _ = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    metrics: list[dict[str, Any]] = []
    fit_audit: list[dict[str, Any]] = []
    candidates = [value.strip() for value in args.candidates.split(",") if value.strip()]

    for held in [value.strip() for value in args.held_values.split(",") if value.strip()]:
        train, audit = train_rows(e_cache, r_cache, frames, held, args.train_cap)
        fit_audit.extend(audit)
        if not len(train.y) or len(np.unique(train.y)) < 2:
            raise RuntimeError(f"{held}: no legal two-class fit rows")
        e_fit, _unused, e_stats = standardize(train.e, train.e)
        r_fit, _unused, r_stats = standardize(train.r, train.r)
        histgb = HistGradientBoostingClassifier(max_iter=180, max_leaf_nodes=31, l2_regularization=1.0).fit(e_fit, train.y.astype(np.int64))
        models: dict[str, Any] = {"D0_e_histgb": histgb}
        for name, use_r, use_h in (("D1_e_mlp", False, False), ("D2_er_mlp", True, False), ("D3_eh_attention", False, True), ("D4_erh_attention", True, True)):
            if name in candidates:
                models[name] = fit_fusion(e_fit, r_fit, train.y, train.episode, use_r, use_h, args.epochs)

        select_scores: dict[str, list[np.ndarray]] = defaultdict(list)
        for role in ("id_calib", "ood_val", "ood_stress"):
            part = role_rows(e_cache, r_cache, frames, held, role, "select", args.eval_cap, 0, False)
            if not len(part.y):
                # A capped local cache need not cover every legal select role.
                # Skipping an empty role is safe; it cannot create threshold
                # evidence.  The resulting availability is recorded below.
                fit_audit.append({"held_value": held, "role": role, "phase": "select", "label": 0, "rows": 0, "episodes": 0, "held_excluded": True})
                continue
            e_select = np.nan_to_num((part.e - e_stats[:, 0]) / e_stats[:, 1]).astype(np.float32)
            r_select = np.nan_to_num((part.r - r_stats[:, 0]) / r_stats[:, 1]).astype(np.float32)
            for name, model in models.items():
                values = histgb.predict_proba(e_select)[:, 1] if name == "D0_e_histgb" else neural_score(model, e_select, r_select, part.episode)[0]
                if len(values):
                    select_scores[name].append(values)
        thresholds = {name: float(np.quantile(np.concatenate(values), 0.99)) for name, values in select_scores.items() if values}

        for role, phase in EVAL.items():
            label = 1 if role in {"future_query", "sealed_final_attack"} else 0
            part = role_rows(e_cache, r_cache, frames, held, role, phase, args.eval_cap, label, True)
            e_eval = np.nan_to_num((part.e - e_stats[:, 0]) / e_stats[:, 1]).astype(np.float32)
            r_eval = np.nan_to_num((part.r - r_stats[:, 0]) / r_stats[:, 1]).astype(np.float32)
            for name, model in models.items():
                if name not in thresholds:
                    continue
                if not len(part.y):
                    scores, episodes = np.zeros(0, dtype=np.float32), 0
                elif name == "D0_e_histgb":
                    scores, episodes = histgb.predict_proba(e_eval)[:, 1], len(set(part.episode))
                else:
                    scores, episodes = neural_score(model, e_eval, r_eval, part.episode)
                metrics.append({
                    "candidate": name,
                    "held_value": held,
                    "role": role,
                    "rows": int(len(scores)),
                    "episodes": int(episodes),
                    "hard_alarm_rate": float(np.mean(scores >= thresholds[name])) if len(scores) else np.nan,
                    "mean_attack_score": float(np.mean(scores)) if len(scores) else np.nan,
                    "threshold": float(thresholds[name]),
                    "review_rate": 0.0,
                    "report_only": role.startswith("sealed") or role == "future_query",
                })

    pd.DataFrame(metrics).to_csv(out / "metrics.csv", index=False)
    pd.DataFrame(fit_audit).to_csv(out / "fit_audit.csv", index=False)
    summary = [f"# {ISSUE}", "", "Strict Level-2 development canary. Review is disabled (`review=0`).", "", "| candidate | held | role | rows | episodes | hard | mean score |", "|---|---|---|---:|---:|---:|---:|"]
    for row in metrics:
        summary.append(f"| {row['candidate']} | {row['held_value']} | {row['role']} | {row['rows']} | {row['episodes']} | {row['hard_alarm_rate']:.4f} | {row['mean_attack_score']:.4f} |")
    (out / "codex_readout.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    (out / "run_spec.json").write_text(json.dumps({
        "issue": ISSUE,
        "ckaw_root": str(e_root),
        "plan_path": str(plan_path),
        "held_values": args.held_values,
        "train_cap": int(args.train_cap),
        "eval_cap": int(args.eval_cap),
        "epochs": int(args.epochs),
        "candidates": candidates,
        "frontend_label_free": True,
        "relative_state": "same-source timestamp-earlier unlabeled robust snapshots; target computed before update",
        "report_used_for_fit_or_threshold": False,
        "role_isolated_attention_bags": True,
        "packet_support_loss_preserved": True,
        "review_rate_fixed": 0.0,
        "seconds": time.time() - started,
    }, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "out": str(out), "metric_rows": len(metrics), "cache_sources": len(cache_audit)}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ckaw-root", default=str(DEFAULT_CKAW))
    parser.add_argument("--plan-path", default="")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--candidates", default="D0_e_histgb,D1_e_mlp,D2_er_mlp,D3_eh_attention,D4_erh_attention")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
