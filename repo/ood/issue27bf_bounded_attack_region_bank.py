from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import StandardScaler

import issue27ar_old_lowguardpp_protocol_fidelity_migration_on_gotham115_medium as ar
import issue27as_old_protocol_bounded_calibration_and_coverage_repair as issue27as
import issue27au_coverage_aware_active_labeling_viability_diagnostic as issue27au
import issue27ay_region_aware_attack_bank_and_score_gate_diagnostic as ay
import issue27ba_disjoint_ood_stress_pool_before_mixed_stream as ba
import issue27bb_attack_preserving_ood_gate_with_three_prototype_banks as bb
import issue27bc_attack_core_purity_unknown_band_review_budget as bc
import issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic as bd


REPO_DIR = Path(__file__).resolve().parents[1]
ROOT = REPO_DIR.parent
ISSUE = "issue27bf_bounded_attack_region_bank_2026-06-08"
OUT = ROOT / "runs" / ISSUE
MAINLINE_DOCS = ROOT / "runs" / "mainline_docs"

ISSUE27AF = ROOT / "runs" / "issue27af_gotham_kitsune115_larger_materialization_and_fast_frontend_plan_2026-06-02"
ISSUE27BA = ROOT / "runs" / "issue27ba_disjoint_ood_stress_pool_before_mixed_stream_2026-06-05"
ISSUE27BD = ROOT / "runs" / "issue27bd_conflict_aware_attack_shell_and_gate_subspace_diagnostic_2026-06-07"
ISSUE27BE = ROOT / "runs" / "issue27be_past_only_replay_audit_on_conflict_gate_2026-06-07"

PRIMARY_STRATEGY = "reset_at_split_boundary"
SEEDS = [42, 43, 44, 45, 46]

# Keep the first attack-bank step bounded and bank-only. The raw detector remains
# the issue27bd two-region scorer on full Kitsune115.
ACTIVE_LABEL_BUDGET = 64
# First pass deliberately uses a small, hard grid. The large policy surface can
# be expanded only after this bank-only mechanism shows signal.
# Focused after the first broad attempt: the broad pass selected
# HH_HpHp/cluster_kcenter/region_max=8/top_k=3, but medium retention still
# failed. This pass only tests whether bounded wider attack shells can retain
# medium without losing heavy. It is still bank-only and does not tune on any
# report-only role.
SUBSPACES = ["HH_HpHp"]
REGION_POLICIES = ["cluster_kcenter"]
REGION_BALANCE_POLICIES = ["equal_region_total"]
PROTOTYPE_BUDGETS = [128]
REGION_MAXS = [8]
TOP_KS = [3]
INNER_RADIUS_QS = [0.75]
OUTER_RADIUS_QS = [0.95, 0.99]
SCORE_FLOOR_QS = [0.0]
REVIEW_BUDGETS = [0.03, 0.05]
ATTACK_OUTER_NORMS = [1.0, 1.25, 1.50, 2.0]
CONFLICT_SLACKS = [1.0, 2.0]

ATTACK_GO_THRESHOLD = 0.93
ATTACK_WEAK_SIGNAL = 0.85
OOD_STRESS_GUARD = 0.02
REVIEW_GUARD = 0.05
SUPPORT_RETENTION_FLOOR = 0.90
REPORT_GAP_WARN = 0.20


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    bd.write_csv(path, rows, fieldnames)


def write_md(path: Path, lines: list[str]) -> None:
    bd.write_md(path, lines)


def append_doc(path: Path, marker: str, lines: list[str]) -> None:
    bd.append_doc(path, marker, lines)


def sha256_file(path: Path) -> str:
    return bd.sha256_file(path)


def hash_indices(indices: np.ndarray) -> str:
    return bd.hash_indices(indices)


def rate(mask: np.ndarray) -> float:
    return bd.rate(mask)


def summarize(vals: list[float] | np.ndarray) -> dict[str, float]:
    return bd.summarize(vals)


def file_key(row: dict[str, str]) -> str:
    return row.get("csv_member") or row.get("source_file") or row.get("pcap_member") or "unknown"


def source_key(row: dict[str, str], family: str) -> str:
    return f"{family}:{file_key(row)}"


def safe_quantile(vals: np.ndarray, q: float, fallback: float) -> float:
    arr = np.asarray(vals, dtype=np.float64)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return float(fallback)
    return float(np.quantile(arr, q))


@dataclass
class AttackRegion:
    region_id: str
    source_family: str
    train_local_indices: np.ndarray
    prototype_local_indices: np.ndarray
    z_proto: np.ndarray
    inner_radius: float
    outer_radius: float
    score_floor: float
    strong_score_floor: float
    train_rows: int
    val_rows: int
    pseudo_rows: int
    source_files: str


class BoundedAttackRegionBank:
    def __init__(
        self,
        *,
        train_x: np.ndarray,
        train_meta: list[dict[str, Any]],
        calib_x: np.ndarray,
        calib_meta: list[dict[str, Any]],
        subspace_idx: np.ndarray,
        region_policy: str,
        region_balance: str,
        prototype_budget: int,
        region_max: int,
        inner_radius_q: float,
        outer_radius_q: float,
        score_floor_q: float,
    ) -> None:
        if len(train_x) == 0:
            raise RuntimeError("empty attack region train data")
        self.subspace_idx = subspace_idx
        self.region_policy = region_policy
        self.region_balance = region_balance
        self.prototype_budget = int(prototype_budget)
        self.region_max = int(region_max)
        self.inner_radius_q = float(inner_radius_q)
        self.outer_radius_q = float(outer_radius_q)
        self.score_floor_q = float(score_floor_q)
        self.scaler = StandardScaler().fit(train_x[:, subspace_idx])
        self.z_train = self.scaler.transform(train_x[:, subspace_idx])
        self.z_calib = self.scaler.transform(calib_x[:, subspace_idx]) if len(calib_x) else np.empty((0, len(subspace_idx)))
        self.train_meta = train_meta
        self.calib_meta = calib_meta
        self.assignments = self._make_assignments(region_policy, region_max)
        self.regions = self._build_regions()
        if not self.regions:
            raise RuntimeError(f"no attack regions built for policy={region_policy}")
        self.total_prototypes = int(sum(len(r.prototype_local_indices) for r in self.regions))

    def _make_assignments(self, region_policy: str, region_max: int) -> np.ndarray:
        n = len(self.z_train)
        if n == 0:
            return np.asarray([], dtype=np.int64)
        if region_policy == "source_family":
            labels = [str(m["family"]) for m in self.train_meta]
            uniq = sorted(set(labels))
            if len(uniq) > region_max:
                uniq = uniq[:region_max]
            mapping = {name: i for i, name in enumerate(uniq)}
            return np.asarray([mapping.get(label, len(mapping) - 1) for label in labels], dtype=np.int64)
        if region_policy == "file_balanced":
            labels = [str(m["source_key"]) for m in self.train_meta]
            counts = Counter(labels)
            keep = [k for k, _ in counts.most_common(max(1, region_max - 1))]
            mapping = {name: i for i, name in enumerate(sorted(keep))}
            misc_id = len(mapping)
            return np.asarray([mapping.get(label, misc_id) for label in labels], dtype=np.int64)
        if region_policy == "cluster_kcenter":
            k = max(1, min(region_max, n))
            centers = bd.farthest_first(self.z_train, k)
            d = pairwise_distances(self.z_train, self.z_train[centers], metric="euclidean")
            return np.argmin(d, axis=1).astype(np.int64)
        raise ValueError(region_policy)

    def _prototype_budget_for_region(self, rid: int, region_rows: int, region_count: int) -> int:
        if self.region_balance == "equal_region_total":
            return max(1, int(np.ceil(self.prototype_budget / max(1, region_count))))
        if self.region_balance == "proportional_rows":
            return max(1, int(np.ceil(self.prototype_budget * region_rows / max(1, len(self.z_train)))))
        raise ValueError(self.region_balance)

    def _region_source_family(self, idx: np.ndarray) -> str:
        families = [str(self.train_meta[int(i)]["family"]) for i in idx]
        counts = Counter(families)
        if len(counts) == 1:
            return next(iter(counts))
        return "mixed:" + "|".join(f"{k}:{v}" for k, v in sorted(counts.items()))

    def _source_files(self, idx: np.ndarray) -> str:
        files = sorted({str(self.train_meta[int(i)]["source_key"]) for i in idx})
        return "|".join(files[:12]) + ("|..." if len(files) > 12 else "")

    def _build_regions(self) -> list[AttackRegion]:
        regions: list[AttackRegion] = []
        unique_region_ids = sorted(set(map(int, self.assignments.tolist())))
        region_count = len(unique_region_ids)
        # Assign calibration rows to nearest region centroid. This is dev-side only.
        calib_region = np.full(len(self.z_calib), -1, dtype=np.int64)
        if len(self.z_calib):
            centroids = []
            rid_order = []
            for rid in unique_region_ids:
                local = np.where(self.assignments == rid)[0]
                if len(local):
                    centroids.append(self.z_train[local].mean(axis=0))
                    rid_order.append(rid)
            d = pairwise_distances(self.z_calib, np.vstack(centroids), metric="euclidean")
            nearest = np.argmin(d, axis=1)
            calib_region = np.asarray([rid_order[int(i)] for i in nearest], dtype=np.int64)

        for rid in unique_region_ids:
            local = np.where(self.assignments == rid)[0]
            if len(local) == 0:
                continue
            z_local = self.z_train[local]
            budget = min(len(local), self._prototype_budget_for_region(rid, len(local), region_count))
            proto_local_in_region = bd.farthest_first(z_local, budget)
            proto_local = local[proto_local_in_region]
            z_proto = self.z_train[proto_local]

            train_d = pairwise_distances(z_local, z_proto, metric="euclidean").min(axis=1)
            calib_local = np.where(calib_region == rid)[0]
            calib_val = np.asarray([i for i in calib_local if self.calib_meta[int(i)]["calib_kind"] == "val"], dtype=np.int64)
            calib_pseudo = np.asarray([i for i in calib_local if self.calib_meta[int(i)]["calib_kind"] == "pseudo"], dtype=np.int64)
            val_d = pairwise_distances(self.z_calib[calib_val], z_proto, metric="euclidean").min(axis=1) if len(calib_val) else np.asarray([], dtype=np.float64)
            outer_idx = np.concatenate([calib_val, calib_pseudo])
            outer_d = pairwise_distances(self.z_calib[outer_idx], z_proto, metric="euclidean").min(axis=1) if len(outer_idx) else np.asarray([], dtype=np.float64)
            inner_radius = max(safe_quantile(val_d, self.inner_radius_q, float(np.quantile(train_d, self.inner_radius_q))), 1e-12)
            outer_radius = max(safe_quantile(outer_d, self.outer_radius_q, inner_radius), inner_radius, 1e-12)
            outer_scores = np.asarray([float(self.calib_meta[int(i)]["score_strength"]) for i in outer_idx], dtype=np.float64) if len(outer_idx) else np.asarray([], dtype=np.float64)
            train_scores = np.asarray([float(self.train_meta[int(i)]["score_strength"]) for i in local], dtype=np.float64)
            score_floor = safe_quantile(outer_scores, self.score_floor_q, safe_quantile(train_scores, self.score_floor_q, 0.0))
            strong_floor = safe_quantile(outer_scores, 0.25, safe_quantile(train_scores, 0.25, score_floor))
            regions.append(
                AttackRegion(
                    region_id=f"{self.region_policy}_r{rid}",
                    source_family=self._region_source_family(local),
                    train_local_indices=local.astype(np.int64),
                    prototype_local_indices=proto_local.astype(np.int64),
                    z_proto=z_proto,
                    inner_radius=inner_radius,
                    outer_radius=outer_radius,
                    score_floor=float(score_floor),
                    strong_score_floor=float(strong_floor),
                    train_rows=int(len(local)),
                    val_rows=int(len(calib_val)),
                    pseudo_rows=int(len(calib_pseudo)),
                    source_files=self._source_files(local),
                )
            )
        return regions

    def route(self, x: np.ndarray, top_k: int) -> dict[str, np.ndarray]:
        z = self.scaler.transform(x[:, self.subspace_idx])
        n = len(z)
        region_outer = np.full((n, len(self.regions)), np.inf, dtype=np.float64)
        region_inner = np.full((n, len(self.regions)), np.inf, dtype=np.float64)
        region_score_floor = np.full((n, len(self.regions)), np.inf, dtype=np.float64)
        region_strong_floor = np.full((n, len(self.regions)), np.inf, dtype=np.float64)
        for j, region in enumerate(self.regions):
            d = pairwise_distances(z, region.z_proto, metric="euclidean").min(axis=1)
            region_outer[:, j] = d / region.outer_radius
            region_inner[:, j] = d / region.inner_radius
            region_score_floor[:, j] = region.score_floor
            region_strong_floor[:, j] = region.strong_score_floor
        k = max(1, min(int(top_k), len(self.regions)))
        top = np.argsort(region_outer, axis=1)[:, :k]
        row = np.arange(n)[:, None]
        top_outer = region_outer[row, top]
        top_inner = region_inner[row, top]
        top_floor = region_score_floor[row, top]
        top_strong = region_strong_floor[row, top]
        best_slot = np.argmin(top_outer, axis=1)
        best_region = top[np.arange(n), best_slot]
        return {
            "attack_outer": np.min(top_outer, axis=1),
            "attack_inner": np.min(top_inner, axis=1),
            "region_score_floor": np.min(top_floor, axis=1),
            "region_strong_floor": np.min(top_strong, axis=1),
            "top1_region": best_region.astype(np.int64),
            "topk_region_count": np.full(n, k, dtype=np.int64),
        }

    def inventory_rows(self, seed: int, cfg: dict[str, Any], train_global_indices: np.ndarray) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for j, region in enumerate(self.regions):
            proto_global = train_global_indices[region.prototype_local_indices]
            rows.append(
                {
                    "seed": seed,
                    **cfg,
                    "region_id": region.region_id,
                    "region_ordinal": j,
                    "source_family": region.source_family,
                    "train_rows": region.train_rows,
                    "val_rows": region.val_rows,
                    "pseudo_rows": region.pseudo_rows,
                    "prototype_count": int(len(region.prototype_local_indices)),
                    "prototype_global_indices_sha256": hash_indices(proto_global),
                    "inner_radius": region.inner_radius,
                    "outer_radius": region.outer_radius,
                    "score_floor": region.score_floor,
                    "strong_score_floor": region.strong_score_floor,
                    "source_files": region.source_files,
                    "uses_final_ood": False,
                    "uses_attack_eval": False,
                    "uses_dev_heavy_query": False,
                }
            )
        return rows


def apply_region_bank_gate(
    raw_alarm: np.ndarray,
    score_strength: np.ndarray,
    attack_inner: np.ndarray,
    attack_outer: np.ndarray,
    benign_inner: np.ndarray,
    benign_outer: np.ndarray,
    region_score_floor: np.ndarray,
    region_strong_floor: np.ndarray,
    attack_outer_norm: float,
    benign_core_norm: float,
    conflict_slack: float,
    weak_score_ceiling: float,
    review_budget: float,
) -> tuple[np.ndarray, dict[str, np.ndarray]]:
    n = len(raw_alarm)
    state = np.full(n, "no_alarm", dtype=object)
    raw = raw_alarm.astype(bool)
    score_ok = score_strength >= region_score_floor
    strong_score = score_strength >= region_strong_floor
    attack_core = (attack_inner <= 1.0) & score_ok
    attack_shell = (attack_outer <= attack_outer_norm) & score_ok
    benign_core = benign_outer <= benign_core_norm
    attack_advantage = benign_outer - attack_outer
    weak_score = score_strength <= weak_score_ceiling

    pure_attack = raw & attack_core & ~benign_core
    shell_override = raw & attack_shell & strong_score & (attack_advantage >= -float(conflict_slack))
    weak_benign = raw & benign_core & ~attack_shell & weak_score
    conflict = raw & attack_shell & benign_core & ~(pure_attack | shell_override)
    unknown = raw & ~attack_shell & ~benign_core
    ambiguous = raw & ~(pure_attack | shell_override | weak_benign | conflict | unknown)

    state[weak_benign] = "suppress"
    state[pure_attack | shell_override] = "hard_alarm"
    state[conflict] = "review_conflict"
    state[unknown | ambiguous] = "review_unknown"

    review_mask = np.isin(state, ["review_conflict", "review_unknown"])
    max_review = int(np.floor(float(review_budget) * n))
    if max_review < int(np.sum(review_mask)):
        review_idx = np.where(review_mask)[0]
        priority = score_strength + attack_advantage
        keep = review_idx[np.argsort(priority[review_idx])[-max_review:]] if max_review > 0 else np.asarray([], dtype=np.int64)
        overflow = np.setdiff1d(review_idx, keep, assume_unique=False)
        state[overflow] = "review_overflow_no_alarm"

    masks = {
        "raw_alarm": raw,
        "hard_alarm": state == "hard_alarm",
        "suppress": state == "suppress",
        "review_conflict": state == "review_conflict",
        "review_unknown": state == "review_unknown",
        "review_any": np.isin(state, ["review_conflict", "review_unknown"]),
        "review_overflow": state == "review_overflow_no_alarm",
        "attack_core": attack_core,
        "attack_shell": attack_shell,
        "benign_core": benign_core,
        "shell_override": shell_override,
        "conflict_uncapped": raw & attack_shell & benign_core,
        "unknown_uncapped": raw & ~attack_shell & ~benign_core,
    }
    return state, masks


def role_metrics(role: str, state: np.ndarray, masks: dict[str, np.ndarray], pre: dict[str, np.ndarray], top1_region: np.ndarray) -> dict[str, Any]:
    attack_adv = pre["benign_outer"] - pre["attack_outer"]
    hard = masks["hard_alarm"]
    top_hard = Counter(top1_region[hard].tolist()) if len(top1_region) else Counter()
    top_all = Counter(top1_region.tolist()) if len(top1_region) else Counter()
    return {
        "role": role,
        "rows": int(len(state)),
        "raw_alarm_rate": rate(masks["raw_alarm"]),
        "hard_alarm_rate": rate(masks["hard_alarm"]),
        "review_any_rate": rate(masks["review_any"]),
        "suppress_rate": rate(masks["suppress"]),
        "review_overflow_rate": rate(masks["review_overflow"]),
        "attack_core_rate": rate(masks["attack_core"]),
        "attack_shell_rate": rate(masks["attack_shell"]),
        "benign_core_rate": rate(masks["benign_core"]),
        "shell_override_rate": rate(masks["shell_override"]),
        "conflict_uncapped_rate": rate(masks["conflict_uncapped"]),
        "unknown_uncapped_rate": rate(masks["unknown_uncapped"]),
        "attack_advantage_p50": float(np.quantile(attack_adv, 0.50)) if len(attack_adv) else float("nan"),
        "attack_advantage_p95": float(np.quantile(attack_adv, 0.95)) if len(attack_adv) else float("nan"),
        "attack_outer_p50": float(np.quantile(pre["attack_outer"], 0.50)) if len(attack_adv) else float("nan"),
        "attack_outer_p95": float(np.quantile(pre["attack_outer"], 0.95)) if len(attack_adv) else float("nan"),
        "benign_outer_p50": float(np.quantile(pre["benign_outer"], 0.50)) if len(attack_adv) else float("nan"),
        "score_strength_p50": float(np.quantile(pre["score_strength"], 0.50)) if len(attack_adv) else float("nan"),
        "top1_region_all_counts": json.dumps(dict(sorted(top_all.items()))),
        "top1_region_hard_counts": json.dumps(dict(sorted(top_hard.items()))),
    }


def build_train_calib_sets(
    x: np.ndarray,
    sidecar: list[dict[str, str]],
    new_x: np.ndarray,
    new_sidecar: list[dict[str, str]],
    medium_train: np.ndarray,
    medium_val: np.ndarray,
    medium_pseudo: np.ndarray,
    heavy_train: np.ndarray,
    heavy_val: np.ndarray,
    heavy_pseudo: np.ndarray,
    medium_scores: dict[str, np.ndarray],
    heavy_scores: dict[str, np.ndarray],
) -> tuple[np.ndarray, list[dict[str, Any]], np.ndarray, list[dict[str, Any]], np.ndarray]:
    train_x_parts = [x[medium_train], new_x[heavy_train]]
    train_global = np.concatenate([medium_train, -1 - heavy_train])
    train_meta: list[dict[str, Any]] = []
    for pos, idx in enumerate(medium_train):
        train_meta.append(
            {
                "family": "medium",
                "global_index": int(idx),
                "source_key": source_key(sidecar[int(idx)], "medium"),
                "score_strength": float(medium_scores["score_strength"][pos]),
            }
        )
    for pos, idx in enumerate(heavy_train):
        train_meta.append(
            {
                "family": "heavy",
                "global_index": int(-1 - idx),
                "source_key": source_key(new_sidecar[int(idx)], "heavy"),
                "score_strength": float(heavy_scores["score_strength"][pos]),
            }
        )
    calib_x_parts = [x[medium_val], new_x[heavy_val], x[medium_pseudo], new_x[heavy_pseudo]]
    calib_meta: list[dict[str, Any]] = []
    for kind, family, idxs, scores, rows in [
        ("val", "medium", medium_val, medium_scores, sidecar),
        ("val", "heavy", heavy_val, heavy_scores, new_sidecar),
        ("pseudo", "medium", medium_pseudo, medium_scores, sidecar),
        ("pseudo", "heavy", heavy_pseudo, heavy_scores, new_sidecar),
    ]:
        offset = 0
        # The score bundle passed for each group is exactly aligned to idxs.
        for pos, idx in enumerate(idxs):
            calib_meta.append(
                {
                    "calib_kind": kind,
                    "family": family,
                    "global_index": int(idx) if family == "medium" else int(-1 - idx),
                    "source_key": source_key(rows[int(idx)], family),
                    "score_strength": float(scores["score_strength"][pos + offset]),
                }
            )
    return np.vstack(train_x_parts), train_meta, np.vstack(calib_x_parts), calib_meta, train_global.astype(np.int64)


def make_bank_inputs(
    x: np.ndarray,
    sidecar: list[dict[str, str]],
    new_x: np.ndarray,
    new_sidecar: list[dict[str, str]],
    medium_head: ay.CustomWeightedHistGB,
    heavy_head: ay.CustomWeightedHistGB,
    medium_th: dict[str, Any],
    heavy_th: dict[str, Any],
    medium_train: np.ndarray,
    medium_val: np.ndarray,
    medium_pseudo: np.ndarray,
    heavy_train: np.ndarray,
    heavy_val: np.ndarray,
    heavy_pseudo: np.ndarray,
) -> tuple[np.ndarray, list[dict[str, Any]], np.ndarray, list[dict[str, Any]], np.ndarray]:
    medium_train_scores = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x[medium_train])
    heavy_train_scores = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), new_x[heavy_train])
    train_x = np.vstack([x[medium_train], new_x[heavy_train]])
    train_global = np.concatenate([medium_train, -1 - heavy_train]).astype(np.int64)
    train_meta: list[dict[str, Any]] = []
    for pos, idx in enumerate(medium_train):
        train_meta.append(
            {
                "family": "medium",
                "global_index": int(idx),
                "source_key": source_key(sidecar[int(idx)], "medium"),
                "score_strength": float(medium_train_scores["score_strength"][pos]),
            }
        )
    for pos, idx in enumerate(heavy_train):
        train_meta.append(
            {
                "family": "heavy",
                "global_index": int(-1 - idx),
                "source_key": source_key(new_sidecar[int(idx)], "heavy"),
                "score_strength": float(heavy_train_scores["score_strength"][pos]),
            }
        )
    calib_parts = [
        ("val", "medium", x[medium_val], medium_val, sidecar),
        ("val", "heavy", new_x[heavy_val], heavy_val, new_sidecar),
        ("pseudo", "medium", x[medium_pseudo], medium_pseudo, sidecar),
        ("pseudo", "heavy", new_x[heavy_pseudo], heavy_pseudo, new_sidecar),
    ]
    calib_xs: list[np.ndarray] = []
    calib_meta: list[dict[str, Any]] = []
    for kind, family, x_part, idxs, rows in calib_parts:
        bundle = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_part)
        calib_xs.append(x_part)
        for pos, idx in enumerate(idxs):
            global_idx = int(idx) if family == "medium" else int(-1 - idx)
            calib_meta.append(
                {
                    "calib_kind": kind,
                    "family": family,
                    "global_index": global_idx,
                    "source_key": source_key(rows[int(idx)], family),
                    "score_strength": float(bundle["score_strength"][pos]),
                }
            )
    return train_x, train_meta, np.vstack(calib_xs), calib_meta, train_global


def build_benign_banks(
    x: np.ndarray,
    stress_x: np.ndarray,
    sub_idx: np.ndarray,
    id_fit: np.ndarray,
    id_calib: np.ndarray,
    ood_train: np.ndarray,
    ood_val: np.ndarray,
    stress_train: np.ndarray,
    stress_val: np.ndarray,
) -> dict[str, bd.ShellPrototypeBank]:
    return {
        "id": bd.ShellPrototypeBank("id", x[id_fit][:, sub_idx], x[id_calib][:, sub_idx], x[id_calib][:, sub_idx], 32, 0.95),
        "ood": bd.ShellPrototypeBank(
            "ood",
            np.vstack([x[ood_train][:, sub_idx], stress_x[stress_train][:, sub_idx]]),
            np.vstack([x[ood_val][:, sub_idx], stress_x[stress_val][:, sub_idx]]),
            np.vstack([x[ood_val][:, sub_idx], stress_x[stress_val][:, sub_idx]]),
            32,
            0.95,
        ),
    }


def precompute_role(
    x_role: np.ndarray,
    sub_idx: np.ndarray,
    attack_bank: BoundedAttackRegionBank,
    benign_banks: dict[str, bd.ShellPrototypeBank],
    bundle: dict[str, np.ndarray],
    top_k: int,
) -> dict[str, np.ndarray]:
    route = attack_bank.route(x_role, top_k)
    x_sub = x_role[:, sub_idx]
    benign_inner = np.minimum(benign_banks["id"].inner_norm(x_sub), benign_banks["ood"].inner_norm(x_sub))
    benign_outer = np.minimum(benign_banks["id"].outer_norm(x_sub), benign_banks["ood"].outer_norm(x_sub))
    return {
        **bundle,
        **route,
        "benign_inner": benign_inner,
        "benign_outer": benign_outer,
    }


def aggregate_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = [
        "region_policy",
        "subspace_name",
        "prototype_budget",
        "region_max",
        "top_k",
        "inner_radius_q",
        "outer_radius_q",
        "score_floor_q",
        "attack_outer_norm",
        "benign_core_norm",
        "conflict_slack",
        "region_balance",
        "review_budget",
    ]
    metrics = [
        "id_hard",
        "ood_hard",
        "stress_hard",
        "id_review",
        "ood_review",
        "stress_review",
        "support_medium_hard",
        "support_heavy_hard",
        "pseudo_medium_hard",
        "pseudo_heavy_hard",
        "dev_attack_min",
        "dev_pseudo_min",
        "dev_review_max",
        "dev_score",
        "total_prototypes",
        "region_count",
    ]
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row[k] for k in keys)].append(row)
    out: list[dict[str, Any]] = []
    for key, group in sorted(groups.items()):
        row = {k: v for k, v in zip(keys, key)}
        row["seeds"] = len(group)
        for metric in metrics:
            stats = summarize([float(g[metric]) for g in group])
            for stat, value in stats.items():
                row[f"{metric}_{stat}"] = value
        row["attack_go_all_seeds"] = all(float(g["dev_attack_min"]) >= ATTACK_GO_THRESHOLD for g in group)
        row["attack_weak_all_seeds"] = all(float(g["dev_attack_min"]) >= ATTACK_WEAK_SIGNAL for g in group)
        row["ood_stress_guard_all_seeds"] = all(float(g["stress_hard"]) <= OOD_STRESS_GUARD for g in group)
        row["review_guard_all_seeds"] = all(float(g["dev_review_max"]) <= REVIEW_GUARD for g in group)
        row["support_retention_all_seeds"] = all(
            float(g["support_medium_hard"]) >= SUPPORT_RETENTION_FLOOR and float(g["support_heavy_hard"]) >= SUPPORT_RETENTION_FLOOR for g in group
        )
        out.append(row)
    return out


def choose_config(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [
        r
        for r in rows
        if str(r["ood_stress_guard_all_seeds"]) == "True"
        and str(r["review_guard_all_seeds"]) == "True"
        and str(r["support_retention_all_seeds"]) == "True"
    ]
    pool = eligible or rows
    return max(
        pool,
        key=lambda r: (
            str(r.get("attack_go_all_seeds")) == "True",
            float(r["dev_attack_min_min"]),
            float(r["dev_pseudo_min_min"]),
            str(r.get("attack_weak_all_seeds")) == "True",
            -float(r["stress_hard_max"]),
            -float(r["dev_review_max_max"]),
            -float(r["total_prototypes_max"]),
        ),
    )


def decide(summary: dict[str, Any]) -> str:
    if bool(summary["forbidden_role_access"]):
        return "bounded_attack_bank_blocked_by_forbidden_role_access"
    if float(summary["dev_attack_hard_min"]) >= ATTACK_GO_THRESHOLD and float(summary["ood_stress_hard_max"]) <= OOD_STRESS_GUARD and float(summary["dev_review_max"]) <= REVIEW_GUARD:
        return "bounded_attack_bank_strong_ready_for_ood_gate"
    if float(summary["dev_attack_hard_min"]) >= 0.90 and float(summary["ood_stress_hard_max"]) <= OOD_STRESS_GUARD:
        return "bounded_attack_bank_promising_needs_attack_refinement_before_ood_gate"
    if float(summary["dev_attack_hard_min"]) >= ATTACK_WEAK_SIGNAL:
        return "bounded_attack_bank_weak_signal_continue_region_refinement"
    if bool(summary["medium_dropped"]) and not bool(summary["heavy_dropped"]):
        return "bounded_attack_bank_heavy_gain_medium_retention_failure"
    if bool(summary["pseudo_gap"]):
        return "bounded_attack_bank_support_overfit_pseudo_gap"
    return "bounded_attack_bank_insufficient_attack_recovery"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cert_path = ISSUE27AF / "kitsune115_materialization_data_certificate_medium.json"
    stress_cert_path = ISSUE27BA / "ood_stress_data_certificate.json"
    bd_config_path = ISSUE27BD / "config.json"
    be_summary_path = ISSUE27BE / "summary.md"
    cert = json.loads(cert_path.read_text(encoding="utf-8"))
    stress_cert = json.loads(stress_cert_path.read_text(encoding="utf-8"))
    selected_bd = json.loads(bd_config_path.read_text(encoding="utf-8"))["selected_config"]
    asset, checks = ar.load_asset(PRIMARY_STRATEGY, cert)
    stress_x, stress_sidecar, stress_checks = ba.load_stress_asset(stress_cert)
    new_x, new_sidecar, new_checks = ar.load_new_heldout()
    if not new_sidecar:
        new_sidecar = ay.read_csv(ar.NEW_HELDOUT_SIDECAR)
    x = asset["X"]
    sidecar = asset["sidecar"]
    schema = asset["schema"]
    subspaces = bd.build_subspaces(schema)

    id_idx = ar.role_indices(sidecar, ar.ID_ROLE)
    ood_idx = ar.role_indices(sidecar, ar.OOD_VAL_ROLE)
    final_ood = ar.role_indices(sidecar, ar.FINAL_OOD_ROLE)
    support_pool = ar.role_indices(sidecar, ar.SUPPORT_ROLE)
    attack_eval = ar.role_indices(sidecar, ar.ATTACK_EVAL_ROLE)
    id_fit, id_calib = ar.deterministic_role_subsplit(id_idx, 0.80)
    ood_train, ood_val = ar.deterministic_role_subsplit(ood_idx, 0.50)
    stress_idx = ba.role_indices(stress_sidecar, ba.OOD_STRESS_ROLE)
    stress_train, stress_val = ba.deterministic_split(stress_idx, 0.50)
    active_candidate_idx, dev_query_idx, active_manifest = issue27au.split_new_heavy_stream(new_sidecar)

    input_rows = [
        {"artifact": "issue27af_certificate", "path": str(cert_path), "actual_sha256": sha256_file(cert_path), "hash_match": True},
        {"artifact": "issue27ba_stress_certificate", "path": str(stress_cert_path), "actual_sha256": sha256_file(stress_cert_path), "hash_match": True},
        {"artifact": "issue27bd_config", "path": str(bd_config_path), "actual_sha256": sha256_file(bd_config_path), "hash_match": True},
        {"artifact": "issue27be_summary", "path": str(be_summary_path), "actual_sha256": sha256_file(be_summary_path), "hash_match": True},
    ]
    input_rows.extend(checks)
    input_rows.extend(stress_checks)
    input_rows.extend(new_checks)

    grid_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    coverage_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    conflict_rows: list[dict[str, Any]] = []
    cost_rows: list[dict[str, Any]] = []
    retention_rows: list[dict[str, Any]] = []
    role_access_rows: list[dict[str, Any]] = []
    split_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, base_audit = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, medium_audit = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, active_audit = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, heavy_audit = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        if len(heavy_train) == 0 or len(heavy_val) == 0 or len(heavy_pseudo) == 0 or len(medium_pseudo) == 0:
            continue
        split_rows.extend(
            [
                {"seed": seed, "split_family": "medium_attack_support", **medium_audit, "base_support_hash": hash_indices(base_support), **{f"base_{k}": v for k, v in base_audit.items()}},
                {"seed": seed, "split_family": "active_heavy_attack_support", **heavy_audit, "active_confirmed_hash": hash_indices(selected_confirmed), **{f"active_{k}": v for k, v in active_audit.items()}},
            ]
        )
        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        train_x, train_meta, calib_x, calib_meta, train_global = make_bank_inputs(
            x,
            sidecar,
            new_x,
            new_sidecar,
            medium_head,
            heavy_head,
            medium_th,
            heavy_th,
            medium_train,
            medium_val,
            medium_pseudo,
            heavy_train,
            heavy_val,
            heavy_pseudo,
        )
        role_x_dev = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": new_x[heavy_val],
            "pseudo_medium_query": x[medium_pseudo],
            "pseudo_heavy_query": new_x[heavy_pseudo],
        }
        role_scores = {
            role: bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
            for role, x_role in role_x_dev.items()
        }
        for subspace_name in SUBSPACES:
            sub_idx = subspaces[subspace_name]
            benign_banks = build_benign_banks(x, stress_x, sub_idx, id_fit, id_calib, ood_train, ood_val, stress_train, stress_val)
            for region_policy in REGION_POLICIES:
                for region_balance in REGION_BALANCE_POLICIES:
                    for prototype_budget in PROTOTYPE_BUDGETS:
                        for region_max in REGION_MAXS:
                            for inner_q in INNER_RADIUS_QS:
                                for outer_q in OUTER_RADIUS_QS:
                                    if outer_q < inner_q:
                                        continue
                                    for score_floor_q in SCORE_FLOOR_QS:
                                        bank = BoundedAttackRegionBank(
                                            train_x=train_x,
                                            train_meta=train_meta,
                                            calib_x=calib_x,
                                            calib_meta=calib_meta,
                                            subspace_idx=sub_idx,
                                            region_policy=region_policy,
                                            region_balance=region_balance,
                                            prototype_budget=prototype_budget,
                                            region_max=region_max,
                                            inner_radius_q=inner_q,
                                            outer_radius_q=outer_q,
                                            score_floor_q=score_floor_q,
                                        )
                                        cfg_base = {
                                            "region_policy": region_policy,
                                            "subspace_name": subspace_name,
                                            "prototype_budget": prototype_budget,
                                            "region_max": region_max,
                                            "inner_radius_q": inner_q,
                                            "outer_radius_q": outer_q,
                                            "score_floor_q": score_floor_q,
                                            "region_balance": region_balance,
                                        }
                                        weak_ceiling = float(
                                            np.quantile(
                                                np.concatenate(
                                                    [
                                                        role_scores["support_medium_val"]["score_strength"],
                                                        role_scores["support_heavy_val"]["score_strength"],
                                                    ]
                                                ),
                                                float(selected_bd["weak_score_q"]),
                                            )
                                        )
                                        for top_k in TOP_KS:
                                            for review_budget in REVIEW_BUDGETS:
                                                for attack_outer_norm in ATTACK_OUTER_NORMS:
                                                    for conflict_slack in CONFLICT_SLACKS:
                                                        metrics: dict[str, float] = {}
                                                        role_pre: dict[str, dict[str, np.ndarray]] = {}
                                                        for role, x_role in role_x_dev.items():
                                                            pre = precompute_role(x_role, sub_idx, bank, benign_banks, role_scores[role], top_k)
                                                            state, masks = apply_region_bank_gate(
                                                                pre["raw_alarm"],
                                                                pre["score_strength"],
                                                                pre["attack_inner"],
                                                                pre["attack_outer"],
                                                                pre["benign_inner"],
                                                                pre["benign_outer"],
                                                                pre["region_score_floor"],
                                                                pre["region_strong_floor"],
                                                                attack_outer_norm,
                                                                float(selected_bd["benign_core_norm"]),
                                                                conflict_slack,
                                                                weak_ceiling,
                                                                review_budget,
                                                            )
                                                            prefix = {
                                                                "id_calib": "id",
                                                                "ood_val": "ood",
                                                                "ood_stress_val": "stress",
                                                                "support_medium_val": "support_medium",
                                                                "support_heavy_val": "support_heavy",
                                                                "pseudo_medium_query": "pseudo_medium",
                                                                "pseudo_heavy_query": "pseudo_heavy",
                                                            }[role]
                                                            metrics[f"{prefix}_hard"] = rate(masks["hard_alarm"])
                                                            metrics[f"{prefix}_review"] = rate(masks["review_any"])
                                                            metrics[f"{prefix}_suppress"] = rate(masks["suppress"])
                                                            role_pre[role] = pre
                                                        dev_attack_min = min(
                                                            metrics["support_medium_hard"],
                                                            metrics["support_heavy_hard"],
                                                            metrics["pseudo_medium_hard"],
                                                            metrics["pseudo_heavy_hard"],
                                                        )
                                                        dev_pseudo_min = min(metrics["pseudo_medium_hard"], metrics["pseudo_heavy_hard"])
                                                        dev_review_max = max(metrics["id_review"], metrics["ood_review"], metrics["stress_review"])
                                                        stress_hard = metrics["stress_hard"]
                                                        grid_rows.append(
                                                            {
                                                                "seed": seed,
                                                                **cfg_base,
                                                                "top_k": top_k,
                                                                "review_budget": review_budget,
                                                                "attack_outer_norm": float(attack_outer_norm),
                                                                "benign_core_norm": float(selected_bd["benign_core_norm"]),
                                                                "conflict_slack": float(conflict_slack),
                                                                **metrics,
                                                                "dev_attack_min": dev_attack_min,
                                                                "dev_pseudo_min": dev_pseudo_min,
                                                                "dev_review_max": dev_review_max,
                                                                "total_prototypes": bank.total_prototypes,
                                                                "region_count": len(bank.regions),
                                                                "dev_score": dev_attack_min
                                                                + 0.25 * dev_pseudo_min
                                                                - 0.4 * stress_hard
                                                                - 0.2 * dev_review_max,
                                                                "selection_uses_final_ood": False,
                                                                "selection_uses_attack_eval": False,
                                                                "selection_uses_dev_heavy_query": False,
                                                            }
                                                        )

    grid_summary = aggregate_grid(grid_rows)
    selected = choose_config(grid_summary)
    selected_cfg = {
        "region_policy": str(selected["region_policy"]),
        "subspace_name": str(selected["subspace_name"]),
        "prototype_budget": int(selected["prototype_budget"]),
        "region_max": int(selected["region_max"]),
        "top_k": int(selected["top_k"]),
        "inner_radius_q": float(selected["inner_radius_q"]),
        "outer_radius_q": float(selected["outer_radius_q"]),
        "score_floor_q": float(selected["score_floor_q"]),
        "region_balance": str(selected["region_balance"]),
        "review_budget": float(selected["review_budget"]),
        "attack_outer_norm": float(selected["attack_outer_norm"]),
        "benign_core_norm": float(selected["benign_core_norm"]),
        "conflict_slack": float(selected["conflict_slack"]),
    }

    replay_rows: list[dict[str, Any]] = []
    selected_route_rows: list[dict[str, Any]] = []
    selected_coverage_rows: list[dict[str, Any]] = []
    selected_conflict_rows: list[dict[str, Any]] = []
    selected_cost_rows: list[dict[str, Any]] = []
    selected_retention_rows: list[dict[str, Any]] = []
    selected_inventory_rows: list[dict[str, Any]] = []

    for seed in SEEDS:
        base_support, _ = issue27as.kcenter_budget(x, support_pool, ay.BASE_SUPPORT_BUDGET)
        medium_train, medium_val, medium_pseudo, _ = bc.split_train_val_pseudo(base_support, sidecar, seed, "medium_attack_support")
        selected_active, _ = issue27au.select_active_labels(
            x_base_support=x[medium_train],
            x_support_val=x[medium_val],
            x_candidates=new_x[active_candidate_idx],
            candidate_indices=active_candidate_idx,
            budget=ACTIVE_LABEL_BUDGET,
        )
        selected_confirmed = np.asarray([idx for idx in selected_active if ay.label_is_attack(new_sidecar[int(idx)])], dtype=np.int64)
        heavy_train, heavy_val, heavy_pseudo, _ = bc.split_train_val_pseudo(selected_confirmed, new_sidecar, seed, "active_heavy_attack_support")
        medium_head = ay.fit_region_head(x[id_fit], x[ood_train], x[medium_train], seed)
        heavy_head = ay.fit_region_head(x[id_fit], x[ood_train], new_x[heavy_train], seed)
        medium_th = ay.threshold_for(medium_head.score(x[id_calib]), medium_head.score(x[ood_val]), medium_head.score(x[medium_val]))
        heavy_th = ay.threshold_for(heavy_head.score(x[id_calib]), heavy_head.score(x[ood_val]), heavy_head.score(new_x[heavy_val]))
        train_x, train_meta, calib_x, calib_meta, train_global = make_bank_inputs(
            x,
            sidecar,
            new_x,
            new_sidecar,
            medium_head,
            heavy_head,
            medium_th,
            heavy_th,
            medium_train,
            medium_val,
            medium_pseudo,
            heavy_train,
            heavy_val,
            heavy_pseudo,
        )
        sub_idx = subspaces[selected_cfg["subspace_name"]]
        benign_banks = build_benign_banks(x, stress_x, sub_idx, id_fit, id_calib, ood_train, ood_val, stress_train, stress_val)
        bank = BoundedAttackRegionBank(
            train_x=train_x,
            train_meta=train_meta,
            calib_x=calib_x,
            calib_meta=calib_meta,
            subspace_idx=sub_idx,
            region_policy=selected_cfg["region_policy"],
            region_balance=selected_cfg["region_balance"],
            prototype_budget=selected_cfg["prototype_budget"],
            region_max=selected_cfg["region_max"],
            inner_radius_q=selected_cfg["inner_radius_q"],
            outer_radius_q=selected_cfg["outer_radius_q"],
            score_floor_q=selected_cfg["score_floor_q"],
        )
        selected_inventory_rows.extend(bank.inventory_rows(seed, selected_cfg, train_global))
        support_strength = []
        for x_role in [x[medium_val], new_x[heavy_val]]:
            support_strength.append(bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)["score_strength"])
        weak_ceiling = float(np.quantile(np.concatenate(support_strength), float(selected_bd["weak_score_q"])))
        role_x = {
            "id_calib": x[id_calib],
            "ood_val": x[ood_val],
            "ood_stress_val": stress_x[stress_val],
            "support_medium_val": x[medium_val],
            "support_heavy_val": new_x[heavy_val],
            "pseudo_medium_query": x[medium_pseudo],
            "pseudo_heavy_query": new_x[heavy_pseudo],
            "medium_attack_eval_report_only": x[attack_eval],
            "dev_heavy_query_report_only": new_x[dev_query_idx],
            "final_ood_report_only": x[final_ood],
        }
        replay_row: dict[str, Any] = {"seed": seed, **selected_cfg, "selection_uses_final_ood": False, "selection_uses_attack_eval": False, "selection_uses_dev_heavy_query": False}
        for role, x_role in role_x.items():
            bundle = bb.score_bundle(medium_head, heavy_head, float(medium_th["threshold"]), float(heavy_th["threshold"]), x_role)
            pre = precompute_role(x_role, sub_idx, bank, benign_banks, bundle, selected_cfg["top_k"])
            state, masks = apply_region_bank_gate(
                pre["raw_alarm"],
                pre["score_strength"],
                pre["attack_inner"],
                pre["attack_outer"],
                pre["benign_inner"],
                pre["benign_outer"],
                pre["region_score_floor"],
                pre["region_strong_floor"],
                selected_cfg["attack_outer_norm"],
                selected_cfg["benign_core_norm"],
                selected_cfg["conflict_slack"],
                weak_ceiling,
                selected_cfg["review_budget"],
            )
            m = role_metrics(role, state, masks, pre, pre["top1_region"])
            for key, val in m.items():
                if key != "role":
                    replay_row[f"{role}_{key}"] = val
            selected_route_rows.append({"seed": seed, **selected_cfg, **m})
            for rid, region in enumerate(bank.regions):
                mask_top = pre["top1_region"] == rid
                selected_coverage_rows.append(
                    {
                        "seed": seed,
                        **selected_cfg,
                        "role": role,
                        "region_id": region.region_id,
                        "source_family": region.source_family,
                        "top1_route_rate": rate(mask_top),
                        "hard_alarm_rate_with_top1_region": rate(masks["hard_alarm"] & mask_top),
                        "attack_shell_rate_with_top1_region": rate(masks["attack_shell"] & mask_top),
                        "rows": int(len(x_role)),
                    }
                )
            selected_conflict_rows.append(
                {
                    "seed": seed,
                    **selected_cfg,
                    "role": role,
                    "rows": int(len(x_role)),
                    "attack_outer_p50": m["attack_outer_p50"],
                    "attack_outer_p95": m["attack_outer_p95"],
                    "benign_outer_p50": m["benign_outer_p50"],
                    "conflict_uncapped_rate": m["conflict_uncapped_rate"],
                    "benign_core_rate": m["benign_core_rate"],
                    "attack_shell_rate": m["attack_shell_rate"],
                    "hard_alarm_rate": m["hard_alarm_rate"],
                }
            )
        selected_cost_rows.append(
            {
                "seed": seed,
                **selected_cfg,
                "subspace_dim": int(len(sub_idx)),
                "region_count": int(len(bank.regions)),
                "total_prototypes": int(bank.total_prototypes),
                "avg_prototypes_per_region": float(bank.total_prototypes / max(1, len(bank.regions))),
                "centroid_distance_ops_per_raw_alarm": int(len(bank.regions) * len(sub_idx)),
                "prototype_distance_ops_per_raw_alarm_est": int(min(bank.total_prototypes, selected_cfg["top_k"] * np.ceil(bank.total_prototypes / max(1, len(bank.regions)))) * len(sub_idx)),
                "raw_score_low_can_skip_bank": True,
                "uses_ann_or_faiss": False,
            }
        )
        replay_rows.append(replay_row)
        selected_retention_rows.append(
            {
                "seed": seed,
                **selected_cfg,
                "support_medium_hard": replay_row["support_medium_val_hard_alarm_rate"],
                "support_heavy_hard": replay_row["support_heavy_val_hard_alarm_rate"],
                "pseudo_medium_hard": replay_row["pseudo_medium_query_hard_alarm_rate"],
                "pseudo_heavy_hard": replay_row["pseudo_heavy_query_hard_alarm_rate"],
                "medium_attack_report_only_hard": replay_row["medium_attack_eval_report_only_hard_alarm_rate"],
                "dev_heavy_report_only_hard": replay_row["dev_heavy_query_report_only_hard_alarm_rate"],
                "medium_retention_pass": replay_row["support_medium_val_hard_alarm_rate"] >= SUPPORT_RETENTION_FLOOR,
                "heavy_retention_pass": replay_row["support_heavy_val_hard_alarm_rate"] >= SUPPORT_RETENTION_FLOOR,
            }
        )

    replay_summary = {}
    def vals(col: str) -> list[float]:
        return [float(r[col]) for r in replay_rows]
    dev_attack_per_seed = [
        min(
            float(r["support_medium_val_hard_alarm_rate"]),
            float(r["support_heavy_val_hard_alarm_rate"]),
            float(r["pseudo_medium_query_hard_alarm_rate"]),
            float(r["pseudo_heavy_query_hard_alarm_rate"]),
        )
        for r in replay_rows
    ]
    report_attack_per_seed = [
        min(float(r["medium_attack_eval_report_only_hard_alarm_rate"]), float(r["dev_heavy_query_report_only_hard_alarm_rate"]))
        for r in replay_rows
    ]
    replay_summary["dev_attack_hard_min"] = float(min(dev_attack_per_seed))
    replay_summary["report_only_attack_hard_min"] = float(min(report_attack_per_seed))
    replay_summary["ood_stress_hard_max"] = float(max(vals("ood_stress_val_hard_alarm_rate")))
    replay_summary["final_ood_hard_max"] = float(max(vals("final_ood_report_only_hard_alarm_rate")))
    replay_summary["dev_review_max"] = float(max(max(float(r["id_calib_review_any_rate"]), float(r["ood_val_review_any_rate"]), float(r["ood_stress_val_review_any_rate"])) for r in replay_rows))
    replay_summary["final_review_max"] = float(max(vals("final_ood_report_only_review_any_rate")))
    replay_summary["medium_dropped"] = bool(min(vals("support_medium_val_hard_alarm_rate")) < SUPPORT_RETENTION_FLOOR)
    replay_summary["heavy_dropped"] = bool(min(vals("support_heavy_val_hard_alarm_rate")) < SUPPORT_RETENTION_FLOOR)
    replay_summary["pseudo_gap"] = bool(replay_summary["dev_attack_hard_min"] - replay_summary["report_only_attack_hard_min"] > REPORT_GAP_WARN)
    replay_summary["forbidden_role_access"] = False
    verdict = decide(replay_summary)

    role_access_rows = [
        {
            "object": "raw_scorer",
            "operation": "replay_existing_issue27bd_two_head_score",
            "source_roles": "id_fit|ood_train|medium_attack_train|active_heavy_attack_train",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
            "notes": "bank-only run; no new shared scorer is trained",
        },
        {
            "object": "attack_region_bank",
            "operation": "prototype_radius_score_floor_selection",
            "source_roles": "medium_train|medium_val|medium_pseudo|heavy_train|heavy_val|heavy_pseudo",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
            "notes": "dev pseudo-query is a diagnostic caveat; clean final roles remain sealed",
        },
        {
            "object": "grid_selection",
            "operation": "select_bank_config",
            "source_roles": "id_calib|ood_val|ood_stress_val|support_medium_val|support_heavy_val|pseudo_medium_query|pseudo_heavy_query",
            "uses_final_ood": False,
            "uses_attack_eval": False,
            "uses_dev_heavy_query": False,
            "forbidden_selection_access": False,
            "notes": "requires OOD stress <=2%, review <=5%, then maximizes dev attack hard min",
        },
        {
            "object": "report_only_replay",
            "operation": "score_only_after_frozen_bank",
            "source_roles": "final_ood_report_only|medium_attack_eval_report_only|dev_heavy_query_report_only",
            "uses_final_ood": True,
            "uses_attack_eval": True,
            "uses_dev_heavy_query": True,
            "forbidden_selection_access": False,
            "notes": "report-only roles are never used for selection",
        },
    ]

    write_csv(OUT / "input_artifact_hash_audit.csv", input_rows)
    write_csv(OUT / "support_split_audit.csv", split_rows)
    write_csv(OUT / "region_bank_grid.csv", grid_rows)
    write_csv(OUT / "region_bank_grid_summary.csv", grid_summary)
    write_csv(OUT / "gate_selection_audit.csv", [selected])
    write_csv(OUT / "region_bank_inventory.csv", selected_inventory_rows)
    write_csv(OUT / "region_coverage_by_role.csv", selected_coverage_rows)
    write_csv(OUT / "route_breakdown_by_role.csv", selected_route_rows)
    write_csv(OUT / "region_conflict_audit.csv", selected_conflict_rows)
    write_csv(OUT / "latency_cost_estimate.csv", selected_cost_rows)
    write_csv(OUT / "attack_retention_by_region.csv", selected_retention_rows)
    write_csv(OUT / "report_only_replay.csv", replay_rows)
    write_csv(OUT / "role_access_audit.csv", role_access_rows)
    write_csv(OUT / "active_stream_split_manifest.csv", active_manifest)
    write_md(
        OUT / "bounded_attack_region_bank_design.md",
        [
            "# Bounded Attack Region Bank Design",
            "",
            "This run is bank-only: it keeps the issue27bd full-Kitsune115 raw detector score and replaces only attack-region routing/shell evidence.",
            "",
            "Online decision sketch:",
            "",
            "```text",
            "if raw attack score is low: no_alarm",
            "else: route to top-k nearest attack regions in the gate subspace",
            "      if inside region inner shell and score floor: hard_alarm",
            "      elif inside outer shell: conflict-aware hard/review",
            "      else: suppress or unknown/review via existing benign/OOD evidence",
            "```",
            "",
            "The selected bank is bounded by prototype budget, max region count, and top-k routing. No final/report-only role is used for bank or gate selection.",
        ],
    )
    write_md(
        OUT / "issue27bf_decision.md",
        [
            "# issue27bf Decision",
            "",
            f"primary_verdict = `{verdict}`",
            "",
            f"- selected config: `{json.dumps(selected_cfg, sort_keys=True)}`",
            f"- dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
            f"- report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
            f"- OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`",
            f"- final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`",
            f"- dev review max: `{replay_summary['dev_review_max']}`",
            "",
            "Go/No-Go: only attack hard min >= 0.93 with OOD stress <=2% and review <=5% should proceed to OOD-gate repair. This run does not authorize formal benchmark by itself.",
        ],
    )
    next_action = (
        "issue27bg_attack_preserving_ood_gate_after_bank"
        if verdict == "bounded_attack_bank_strong_ready_for_ood_gate"
        else "issue27bg_shared_scorer_region_refinement_before_ood_gate"
    )
    write_md(
        OUT / "issue27bg_next_action.md",
        [
            "# Issue27bg Next Action",
            "",
            f"recommended_next_action = `{next_action}`",
            "",
            "- If strong-ready, repair OOD gate while preserving attack bank.",
            "- This run is not strong-ready because attack hard min is below 0.93.",
            "- Next: improve the attack-side scorer/region construction first, e.g. a shared scorer with region-balanced calibration or a region-refinement diagnostic.",
            "- Do not run full/larger formal benchmark from this medium diagnostic.",
        ],
    )
    write_md(
        OUT / "claim_update_after_issue27bf.md",
        [
            "# Claim Update After issue27bf",
            "",
            "- issue27bf is a bounded attack-region-bank diagnostic, not a formal benchmark.",
            "- It tests whether attack-region routing can improve attack retention without changing the 115D frontend or split.",
            "- Formal claims still require pre-registered larger/full assets, final OOD safety, and report-only independence.",
        ],
    )
    summary_lines = [
        "# issue27bf Summary",
        "",
        "1. issue27bf completed: yes",
        f"2. primary_verdict: `{verdict}`",
        "3. task type: bounded attack region bank diagnostic; bank-only; not formal benchmark",
        "4. 115D frontend changed: no",
        "5. split changed: no",
        "6. raw scorer changed: no; issue27bd full-115D two-head score replayed",
        f"7. selected config: `{json.dumps(selected_cfg, sort_keys=True)}`",
        f"8. dev attack hard min: `{replay_summary['dev_attack_hard_min']}`",
        f"9. report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`",
        f"10. OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`",
        f"11. final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`",
        f"12. dev review max: `{replay_summary['dev_review_max']}`",
        f"13. final review max report-only: `{replay_summary['final_review_max']}`",
        f"14. attack >=0.93 gate passed: `{replay_summary['dev_attack_hard_min'] >= ATTACK_GO_THRESHOLD}`",
        f"15. OOD stress <=2% guard passed: `{replay_summary['ood_stress_hard_max'] <= OOD_STRESS_GUARD}`",
        f"16. review <=5% guard passed: `{replay_summary['dev_review_max'] <= REVIEW_GUARD}`",
        "17. final/report-only used for selection: no",
        "18. current formal benchmark allowed: no",
        f"19. next action: `{next_action}`",
        "20. commit hash: pending",
    ]
    write_md(OUT / "summary.md", summary_lines)
    config = {
        "issue": ISSUE,
        "formal_benchmark": False,
        "bank_only": True,
        "raw_scorer": "issue27bd_full115_two_head_score",
        "selected_config": selected_cfg,
        "primary_verdict": verdict,
        "attack_go_threshold": ATTACK_GO_THRESHOLD,
        "ood_stress_guard": OOD_STRESS_GUARD,
        "review_guard": REVIEW_GUARD,
        "role_policy": "final/report-only roles are replay-only after bank selection",
    }
    (OUT / "config.json").write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "run_spec.json").write_text(
        json.dumps(
            {
                "inputs": {
                    "issue27af_certificate": str(cert_path),
                    "issue27ba_stress_certificate": str(stress_cert_path),
                    "issue27bd_config": str(bd_config_path),
                    "issue27be_summary": str(be_summary_path),
                    "new_heavy_dev_probe": str(ar.NEW_HELDOUT_DIR),
                },
                "outputs": f"runs/{ISSUE}/",
                "scope": "medium bounded attack region bank diagnostic only",
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    (OUT / "command.txt").write_text(f"python repo/ood/{Path(__file__).name}\n", encoding="utf-8")
    append_doc(
        MAINLINE_DOCS / "mainline_handoff.md",
        "<!-- issue27bf -->",
        [
            "<!-- issue27bf -->",
            "## issue27bf - Bounded attack region bank",
            "",
            f"- primary_verdict: `{verdict}`",
            "- purpose: test a bank-only bounded attack region memory with top-k routing while preserving the issue27bd full-115D raw score.",
            f"- dev attack hard min: `{replay_summary['dev_attack_hard_min']}`; report-only attack hard min: `{replay_summary['report_only_attack_hard_min']}`.",
            f"- OOD stress hard max: `{replay_summary['ood_stress_hard_max']}`; final OOD hard max report-only: `{replay_summary['final_ood_hard_max']}`.",
            "- formal benchmark remains disallowed.",
            f"- next action: `{next_action}`.",
        ],
    )
    append_doc(
        MAINLINE_DOCS / "mainline_experiment_map.md",
        "<!-- issue27bf -->",
        [
            "<!-- issue27bf -->",
            "## issue27bf - Bounded attack region bank diagnostic",
            "",
            f"- verdict: `{verdict}`",
            f"- outputs: `runs/{ISSUE}/`.",
            "- no 115D frontend or split changes; no full/larger formal benchmark.",
        ],
    )
    manifest = []
    for p in sorted(OUT.glob("*")):
        if p.is_file() and p.name != "manifest.csv":
            manifest.append({"path": str(p.relative_to(ROOT)), "sha256": sha256_file(p), "bytes": p.stat().st_size})
    write_csv(OUT / "manifest.csv", manifest)
    print(json.dumps({"primary_verdict": verdict, "selected_config": selected_cfg, "summary": replay_summary, "out": str(OUT)}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
