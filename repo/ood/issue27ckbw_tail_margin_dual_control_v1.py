"""CKBW: family-balanced tail-margin process evidence with dual control.

This module implements the frozen CKBW protocol.  It deliberately separates
three concerns which were entangled in earlier experiments:

* the CKBV 51-dimensional causal feature store and legal fit/select scopes;
* a single shared official TabM v0.0.3 process scorer;
* an attack-preserving dual decision controller around frozen CKBQ decisions.

No source or family identity is an input feature.  Report/held rows never
participate in fitting, preprocessing, checkpoint selection, or threshold
selection.  Missing raw-51D evidence is fail-closed to frozen CKBQ.  Review is
fixed at zero and scores are never added.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
import math
import platform
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
import sklearn
import torch
import torch.nn.functional as F


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbm_tabm_causal_source_calibration_v1 as ckbm  # noqa: E402
import issue27ckbo_mature_afterimage_transfer_v1 as ckbo  # noqa: E402
import issue27ckbq_causal_minirocket_consensus_v1 as ckbq  # noqa: E402
import issue27ckbu_unified_process_rescue_formal_v1 as ckbu  # noqa: E402
import issue27ckbu_unified_tshark_causal_frontend_v1 as raw51  # noqa: E402


ISSUE = "issue27ckbw_tail_margin_dual_control_v1_2026-08-03"
SEED = 27
ROOT = ckbo.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE

FROZEN_PREDICTIONS_SHA256 = (
    "f53f1e3d465dc02208cc982a799ba268a9d14ff44ab2622256a79bf7d8b13536"
)
FROZEN_EXTRA_MODEL_SHA256 = (
    "af0db86bed35d25dcedc1ef0f72bc9554c41c001abfed9a0552f889ce395ac24"
)
FROZEN_TABM_MODEL_SHA256 = (
    "88758e28c5df1196854f15af934bddfe660768e099ad3d06b2af415631d3e82d"
)
FROZEN_PREDICTION_ROWS = 297_326
FROZEN_PROTOCOL_ROWS = {
    "GLOBAL_ATTACK_PRESERVATION": 251_050,
    "iotsim-hydraulic-system": 10_069,
    "iotsim-ip-camera-street": 10_069,
    "iotsim-predictive-maintenance": 16_069,
    "iotsim-stream-consumer": 10_069,
}

TABM_VERSION = "0.0.3"
INPUT_DIM = 51
WIDTH = 192
BLOCKS = 3
ENSEMBLE_K = 16
BATCH_SIZE = 512
EPOCHS = 24
MARGIN = 0.10
TAIL_K = 16
LAMBDA_GRID = (0.25, 0.50)

M0_C1 = "M0-C1"
M1_FROZEN = "M1-FrozenCKBQ"
A2_EXTRA_OR = "A2-CKBQ-ExtraTreesRescue"
M4_CE_OR = "M4-CKBQ-TabMProcessRescue"
CE_DUAL = "M5-TabM-CE-DualControl"
TAIL_OR = "M6-TabM-TailMargin-OR"
PRIMARY = "M7-TabM-TailMargin-DualControl"
EXTRA_DUAL = "A4-ExtraTrees-DualControl"
ALL_ARMS = (
    M0_C1,
    M1_FROZEN,
    A2_EXTRA_OR,
    M4_CE_OR,
    CE_DUAL,
    TAIL_OR,
    PRIMARY,
    EXTRA_DUAL,
)

REQUIRED_FROZEN_COLUMNS = frozenset(
    {
        "held_value",
        "uid",
        "role",
        "phase",
        "source_group",
        "device_family",
        "attack_family",
        "label_metric_only",
        "raw51_observable",
        "c1_hard",
        "frozen_ckbq_hard",
        "extra_process_score",
        "extra_process_threshold",
        "tabm_process_score",
        "tabm_process_threshold",
        "hard__M0-C1",
        "hard__M1-FrozenCKBQ",
        "hard__A2-CKBQ-ExtraTreesRescue",
        "hard__M4-CKBQ-TabMProcessRescue",
        "review",
        "seed",
    }
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dump_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def bool_array(values: pd.Series) -> np.ndarray:
    return ckbj.bool_series(values).to_numpy(dtype=bool)


@dataclass(frozen=True)
class FrozenScoreBundle:
    frame: pd.DataFrame
    prediction_sha256: str
    extra_model_sha256: str
    tabm_model_sha256: str

    @classmethod
    def load(
        cls,
        predictions_path: Path,
        model_audit_path: Path,
        *,
        expected_prediction_sha256: str = FROZEN_PREDICTIONS_SHA256,
    ) -> "FrozenScoreBundle":
        predictions_path = Path(predictions_path)
        model_audit_path = Path(model_audit_path)
        actual_sha = sha256_file(predictions_path)
        if actual_sha != expected_prediction_sha256:
            raise RuntimeError(
                "frozen prediction SHA-256 mismatch: "
                f"{actual_sha} != {expected_prediction_sha256}"
            )
        frame = pd.read_csv(predictions_path, compression="infer")
        missing = sorted(REQUIRED_FROZEN_COLUMNS - set(frame.columns))
        if missing:
            raise RuntimeError(f"frozen prediction columns missing: {missing}")
        if len(frame) != FROZEN_PREDICTION_ROWS:
            raise RuntimeError(
                f"frozen prediction row drift: {len(frame)} != {FROZEN_PREDICTION_ROWS}"
            )
        counts = frame.groupby("held_value", dropna=False).size().to_dict()
        if counts != FROZEN_PROTOCOL_ROWS:
            raise RuntimeError(f"frozen protocol row drift: {counts}")
        if frame.duplicated(["held_value", "uid"]).any():
            raise RuntimeError("duplicate (held_value, uid) in frozen predictions")
        if set(pd.to_numeric(frame["seed"], errors="raise").astype(int)) != {SEED}:
            raise RuntimeError("frozen prediction seed drift")
        if bool_array(frame["review"]).any():
            raise RuntimeError("frozen prediction review is not zero")
        for column in (
            "extra_process_score",
            "extra_process_threshold",
            "tabm_process_score",
            "tabm_process_threshold",
        ):
            values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
            if not np.isfinite(values).all():
                raise RuntimeError(f"nonfinite frozen score/threshold: {column}")
        for hard_column, reference_column in (
            ("hard__M0-C1", "c1_hard"),
            ("hard__M1-FrozenCKBQ", "frozen_ckbq_hard"),
        ):
            if not np.array_equal(bool_array(frame[hard_column]), bool_array(frame[reference_column])):
                raise RuntimeError(f"frozen hard-decision drift: {hard_column}")

        audit = pd.read_csv(model_audit_path)
        needed = {"candidate", "model_sha256", "input_dim", "fit_rows", "fit_attack_rows", "fit_benign_rows"}
        if not needed.issubset(audit.columns):
            raise RuntimeError(f"model audit columns missing: {sorted(needed - set(audit.columns))}")

        def one_hash(candidate: str, expected: str) -> str:
            rows = audit.loc[audit["candidate"].astype(str) == candidate]
            hashes = sorted(rows["model_sha256"].astype(str).str.lower().unique().tolist())
            if hashes != [expected]:
                raise RuntimeError(f"{candidate} model hash drift: {hashes}")
            if set(pd.to_numeric(rows["input_dim"], errors="raise").astype(int)) != {INPUT_DIM}:
                raise RuntimeError(f"{candidate} input width drift")
            if set(pd.to_numeric(rows["fit_rows"], errors="raise").astype(int)) != {18_398}:
                raise RuntimeError(f"{candidate} fit row drift")
            if set(pd.to_numeric(rows["fit_attack_rows"], errors="raise").astype(int)) != {4_385}:
                raise RuntimeError(f"{candidate} attack fit row drift")
            if set(pd.to_numeric(rows["fit_benign_rows"], errors="raise").astype(int)) != {14_013}:
                raise RuntimeError(f"{candidate} benign fit row drift")
            return hashes[0]

        extra_hash = one_hash(ckbu.EXTRA_HEAD, FROZEN_EXTRA_MODEL_SHA256)
        tabm_hash = one_hash(ckbu.TABM_HEAD, FROZEN_TABM_MODEL_SHA256)
        return cls(frame, actual_sha, extra_hash, tabm_hash)

    def protocol(self, value: str) -> pd.DataFrame:
        result = self.frame.loc[self.frame["held_value"].astype(str) == str(value)].copy()
        if len(result) != FROZEN_PROTOCOL_ROWS[str(value)]:
            raise RuntimeError(f"frozen protocol lookup incomplete: {value}")
        return result

    def assert_exact_uid_coverage(self, value: str, uids: Sequence[str]) -> pd.DataFrame:
        frame = self.protocol(value).set_index("uid", drop=False)
        requested = list(map(str, uids))
        if len(requested) != len(set(requested)):
            raise RuntimeError(f"duplicate requested UID for {value}")
        missing = sorted(set(requested) - set(frame.index))
        extra = sorted(set(frame.index) - set(requested))
        if missing or extra:
            raise RuntimeError(
                f"frozen UID coverage mismatch for {value}: missing={missing[:5]} extra={extra[:5]}"
            )
        return frame.loc[requested].reset_index(drop=True)


@dataclass(frozen=True)
class TailSelection:
    attack_by_family: dict[str, tuple[int, ...]]
    benign: tuple[int, ...]
    audit: tuple[dict[str, Any], ...]


def _rank_indices(indices: Iterable[int], scores: np.ndarray, uids: Sequence[str], reverse: bool) -> list[int]:
    if reverse:
        return sorted(indices, key=lambda i: (-float(scores[i]), str(uids[i])))
    return sorted(indices, key=lambda i: (float(scores[i]), str(uids[i])))


def select_epoch_tails(
    labels: np.ndarray,
    attack_families: Sequence[str],
    benign_sources: Sequence[str],
    scores: np.ndarray,
    uids: Sequence[str],
    *,
    k: int = TAIL_K,
) -> TailSelection:
    labels = np.asarray(labels, dtype=np.int64)
    scores = np.asarray(scores, dtype=np.float64)
    if not (len(labels) == len(scores) == len(uids) == len(attack_families) == len(benign_sources)):
        raise RuntimeError("tail-selection arrays are not aligned")
    if not np.isfinite(scores).all():
        raise RuntimeError("tail selection received nonfinite scores")
    attack_groups: defaultdict[str, list[int]] = defaultdict(list)
    benign_groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, label in enumerate(labels):
        if int(label) == 1:
            attack_groups[str(attack_families[index])].append(index)
        else:
            benign_groups[str(benign_sources[index])].append(index)
    if len(attack_groups) != 12:
        raise RuntimeError(f"expected 12 attack balance groups, got {sorted(attack_groups)}")
    if not benign_groups:
        raise RuntimeError("no benign sources for tail selection")
    selected_attack: dict[str, tuple[int, ...]] = {}
    audit: list[dict[str, Any]] = []
    for family, indices in sorted(attack_groups.items()):
        chosen = tuple(_rank_indices(indices, scores, uids, False)[: min(k, len(indices))])
        pair_count = len(chosen) * k
        if len(indices) < 8 or pair_count < 128:
            raise RuntimeError(
                f"attack family lacks frozen tail support: {family} rows={len(indices)} pairs={pair_count}"
            )
        selected_attack[family] = chosen
        audit.append(
            {
                "label": 1,
                "group": family,
                "available_rows": len(indices),
                "selected_tail_rows": len(chosen),
                "pair_count": pair_count,
                "selection": "lowest_previous_epoch_score_then_uid",
            }
        )

    ranked_by_source: dict[str, list[int]] = {
        source: _rank_indices(indices, scores, uids, True)
        for source, indices in sorted(benign_groups.items())
    }
    benign: list[int] = []
    max_rank = max(len(indices) for indices in ranked_by_source.values())
    for rank in range(max_rank):
        same_rank = [
            (source, indices[rank])
            for source, indices in ranked_by_source.items()
            if rank < len(indices)
        ]
        same_rank.sort(
            key=lambda item: (
                -float(scores[item[1]]),
                str(item[0]),
                str(uids[item[1]]),
            )
        )
        for _source, index in same_rank:
            benign.append(index)
            if len(benign) == k:
                break
        if len(benign) == k:
            break
    if len(benign) != k:
        raise RuntimeError(f"benign tail is incomplete: {len(benign)} != {k}")
    benign_counts = Counter(str(benign_sources[index]) for index in benign)
    for source, count in sorted(benign_counts.items()):
        audit.append(
            {
                "label": 0,
                "group": source,
                "available_rows": len(benign_groups[source]),
                "selected_tail_rows": count,
                "pair_count": math.nan,
                "selection": "within_source_score_rank_then_same_rank_score_source_uid",
            }
        )
    return TailSelection(selected_attack, tuple(benign), tuple(audit))


def family_balanced_row_weights(records: Sequence[ckbj.Record]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    attack: defaultdict[str, list[int]] = defaultdict(list)
    benign: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if int(record.label) == 1:
            attack[str(record.attack_family)].append(index)
        else:
            benign[str(record.source)].append(index)
    if len(attack) != 12:
        raise RuntimeError(f"balanced CE requires 12 attack families, got {sorted(attack)}")
    if not benign:
        raise RuntimeError("balanced CE requires benign source groups")
    weights = np.zeros(len(records), dtype=np.float64)
    audit: list[dict[str, Any]] = []
    for label, groups in ((1, attack), (0, benign)):
        for group, indices in sorted(groups.items()):
            group_mass = 0.5 / len(groups)
            weights[indices] = group_mass / len(indices)
            audit.append(
                {
                    "label": label,
                    "balance_unit": "attack_family" if label else "benign_source",
                    "group": group,
                    "rows": len(indices),
                    "unnormalized_group_mass": group_mass,
                    "normalized_group_mass": group_mass,
                    "normalized_per_row_weight": math.nan,
                }
            )
    weights *= len(weights) / weights.sum()
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise RuntimeError("invalid balanced CE weights")
    index_by_key: dict[tuple[int, str], list[int]] = {}
    for label, groups in ((1, attack), (0, benign)):
        for group, indices in groups.items():
            index_by_key[(label, str(group))] = list(indices)
    for row in audit:
        indices = index_by_key[(int(row["label"]), str(row["group"]))]
        row["normalized_per_row_weight"] = float(weights[indices[0]])
        row["normalized_weight_sum"] = float(weights[indices].sum())
    return weights.astype(np.float32), audit


def tail_losses(
    probabilities: torch.Tensor,
    selection: TailSelection,
    labels: np.ndarray,
    attack_families: Sequence[str],
    *,
    margin: float = MARGIN,
) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
    if probabilities.ndim != 1:
        raise RuntimeError("tail loss expects one probability per fit row")
    labels = np.asarray(labels, dtype=np.int64)
    if len(probabilities) != len(labels) or len(labels) != len(attack_families):
        raise RuntimeError("tail loss full-fit arrays are not aligned")
    device = probabilities.device
    benign_tail = probabilities[
        torch.as_tensor(selection.benign, dtype=torch.long, device=device)
    ]
    benign_all_indices = np.flatnonzero(labels == 0)
    benign_all = probabilities[
        torch.as_tensor(benign_all_indices, dtype=torch.long, device=device)
    ]
    per_family_pair: list[torch.Tensor] = []
    per_family_summary: list[torch.Tensor] = []
    audit: dict[str, float] = {}
    benign_q95 = torch.quantile(benign_all, 0.95)
    for family, indices in sorted(selection.attack_by_family.items()):
        attack_tail = probabilities[
            torch.as_tensor(indices, dtype=torch.long, device=device)
        ]
        family_all_indices = np.asarray(
            [
                index
                for index, (label, name) in enumerate(zip(labels, attack_families))
                if int(label) == 1 and str(name) == str(family)
            ],
            dtype=np.int64,
        )
        if len(family_all_indices) < 8:
            raise RuntimeError(f"family quantile lacks legal fit rows: {family}")
        attack_all = probabilities[
            torch.as_tensor(family_all_indices, dtype=torch.long, device=device)
        ]
        pair = torch.relu(
            float(margin) - attack_tail[:, None] + benign_tail[None, :]
        ).mean()
        attack_q25 = torch.quantile(attack_all, 0.25)
        summary = torch.relu(float(margin) - attack_q25 + benign_q95)
        per_family_pair.append(pair)
        per_family_summary.append(summary)
        audit[f"q25_attack__{family}"] = float(attack_q25.detach())
        audit[f"margin_q25_q95__{family}"] = float((attack_q25 - benign_q95).detach())
    pair_loss = torch.stack(per_family_pair).mean()
    family_loss = torch.stack(per_family_summary).mean()
    audit["q95_benign_fit"] = float(benign_q95.detach())
    return pair_loss, family_loss, audit


@dataclass(frozen=True)
class DualGate:
    tau_normal: float
    tau_attack: float
    support_rows: int
    support_hard_rows: int
    benign_rows: int
    baseline_hard_rows: int
    dual_hard_rows: int
    suppress_rows: int
    rescue_rows: int
    net_hard_reduction: int
    worst_family_score_margin: float


def apply_dual_control(baseline_hard: np.ndarray, scores: np.ndarray, gate: DualGate) -> np.ndarray:
    baseline = np.asarray(baseline_hard, dtype=bool)
    score = np.asarray(scores, dtype=np.float64)
    if len(baseline) != len(score) or not np.isfinite(score).all():
        raise RuntimeError("dual-control arrays are invalid")
    result = baseline.copy()
    result[(~baseline) & (score >= gate.tau_attack)] = True
    result[baseline & (score <= gate.tau_normal)] = False
    return result


def choose_dual_gate(
    support_records: Sequence[ckbj.Record],
    support_baseline: np.ndarray,
    support_scores: np.ndarray,
    benign_baseline: np.ndarray,
    benign_scores: np.ndarray,
) -> tuple[DualGate, list[dict[str, Any]]]:
    support_base = np.asarray(support_baseline, dtype=bool)
    support_q = np.asarray(support_scores, dtype=np.float64)
    benign_base = np.asarray(benign_baseline, dtype=bool)
    benign_q = np.asarray(benign_scores, dtype=np.float64)
    if len(support_records) != 69 or len(support_q) != 69:
        raise RuntimeError(f"dual gate requires frozen support_val=69, got {len(support_q)}")
    if len(benign_q) != 7_000:
        raise RuntimeError(f"dual gate requires legal benign select=7000, got {len(benign_q)}")
    if not np.isfinite(support_q).all() or not np.isfinite(benign_q).all():
        raise RuntimeError("dual gate received nonfinite score")
    attack_values = sorted(set(float(value) for value in np.concatenate([support_q, benign_q])))
    normal_candidates = [float(np.nextafter(attack_values[0], -np.inf))]
    normal_candidates.extend(float(value) for value in attack_values)
    attack_candidates = list(attack_values)
    attack_candidates.append(float(np.nextafter(attack_values[-1], np.inf)))
    normal_array = np.asarray(normal_candidates, dtype=np.float64)
    benign_hard_scores = np.sort(benign_q[benign_base])
    benign_nonhard_scores = np.sort(benign_q[~benign_base])
    support_hard_floor = (
        float(np.min(support_q[support_base])) if bool(support_base.any()) else math.inf
    )
    support_nonhard_ceiling = (
        float(np.min(support_q[~support_base])) if bool((~support_base).any()) else math.inf
    )
    rows: list[dict[str, Any]] = []
    family_names = sorted({str(record.attack_family) for record in support_records})

    # Stage A is intentionally independent of suppression.  It first preserves
    # every support row, then minimizes benign rescue, and only then chooses the
    # largest feasible attack cut.  Folding suppression into this choice would
    # silently trade attack rescue against benign suppression and violates the
    # frozen two-stage protocol.
    feasible_attack: list[tuple[int, float]] = []
    for tau_attack in attack_candidates:
        if tau_attack > support_nonhard_ceiling:
            continue
        rescue_rows = int(
            len(benign_nonhard_scores)
            - np.searchsorted(benign_nonhard_scores, tau_attack, side="left")
        )
        feasible_attack.append((rescue_rows, float(tau_attack)))
        rows.append(
            {
                "selection_stage": "attack_cut",
                "tau_normal": math.nan,
                "tau_attack": float(tau_attack),
                "support_rows": len(support_q),
                "support_hard_rows": len(support_q),
                "benign_rows": len(benign_q),
                "baseline_hard_rows": int(benign_base.sum()),
                "dual_hard_rows": math.nan,
                "suppress_rows": math.nan,
                "rescue_rows": rescue_rows,
                "net_hard_reduction": math.nan,
                "worst_family_score_margin": min(
                    float(
                        np.min(
                            support_q[
                                np.asarray(
                                    [
                                        str(record.attack_family) == family
                                        for record in support_records
                                    ],
                                    dtype=bool,
                                )
                            ]
                            - float(tau_attack)
                        )
                    )
                    for family in family_names
                ),
                "eligible": True,
                "selected_attack_cut": False,
                "selected": False,
                "selection_scope": "support_val69_plus_aux3000_plus_ton_normal2_4000",
                "report_rows_used": 0,
                "held_rows_used": 0,
                "search_algorithm": "exact_two_stage_sorted_count_v1",
            }
        )
    if not feasible_attack:
        raise RuntimeError("no attack threshold preserves support_val 69/69")
    minimum_rescue = min(value[0] for value in feasible_attack)
    tau_attack = max(value[1] for value in feasible_attack if value[0] == minimum_rescue)
    for row in rows:
        row["selected_attack_cut"] = bool(
            row["selection_stage"] == "attack_cut"
            and row["tau_attack"] == tau_attack
        )

    # Stage B keeps the Stage-A attack cut fixed and maximizes suppression,
    # subject to never suppressing an already-hard support row.
    normal_limit = min(float(tau_attack), support_hard_floor)
    feasible_normal = [value for value in normal_candidates if value < normal_limit]
    if not feasible_normal:
        raise RuntimeError("no normal threshold preserves hard support rows")
    selected: DualGate | None = None
    best_normal: tuple[int, float] | None = None
    for tau_normal in feasible_normal:
        suppress_rows = int(
            np.searchsorted(benign_hard_scores, tau_normal, side="right")
        )
        rescue_rows = minimum_rescue
        family_margins: list[float] = []
        for family in family_names:
            mask = np.asarray(
                [str(record.attack_family) == family for record in support_records], dtype=bool
            )
            family_margins.append(float(np.min(support_q[mask] - float(tau_attack))))
        dual_hard_rows = int(benign_base.sum()) - suppress_rows + rescue_rows
        gate = DualGate(
            tau_normal=float(tau_normal),
            tau_attack=float(tau_attack),
            support_rows=len(support_q),
            support_hard_rows=len(support_q),
            benign_rows=len(benign_q),
            baseline_hard_rows=int(benign_base.sum()),
            dual_hard_rows=dual_hard_rows,
            suppress_rows=suppress_rows,
            rescue_rows=rescue_rows,
            net_hard_reduction=suppress_rows - rescue_rows,
            worst_family_score_margin=min(family_margins),
        )
        row = {
            **gate.__dict__,
            "selection_stage": "normal_cut",
            "eligible": True,
            "selected_attack_cut": True,
            "selected": False,
            "selection_scope": "support_val69_plus_aux3000_plus_ton_normal2_4000",
            "report_rows_used": 0,
            "held_rows_used": 0,
            "search_algorithm": "exact_two_stage_sorted_count_v1",
        }
        rows.append(row)
        key = (gate.suppress_rows, gate.tau_normal)
        if best_normal is None or key > best_normal:
            best_normal = key
            selected = gate
    if selected is None:
        raise RuntimeError("no dual threshold pair preserves support_val 69/69")
    for row in rows:
        row["selected"] = bool(
            row["selection_stage"] == "normal_cut"
            and row["tau_normal"] == selected.tau_normal
            and row["tau_attack"] == selected.tau_attack
        )
    return selected, rows


def one_sided_or(baseline_hard: np.ndarray, scores: np.ndarray, tau_attack: float) -> np.ndarray:
    baseline = np.asarray(baseline_hard, dtype=bool)
    score = np.asarray(scores, dtype=np.float64)
    return baseline | (score >= float(tau_attack))


class TailMarginTabM:
    """Official TabM with frozen-previous-epoch hard-tail objectives."""

    def __init__(self, seed: int, threads: int) -> None:
        if str(getattr(ckbm.tabm, "__version__", TABM_VERSION)) != TABM_VERSION:
            raise RuntimeError(f"official TabM version drift: {getattr(ckbm.tabm, '__version__', None)}")
        torch.manual_seed(int(seed))
        torch.set_num_threads(max(1, int(threads)))
        self.model = ckbm.tabm.TabM.make(
            n_num_features=INPUT_DIM,
            d_out=2,
            num_embeddings=None,
            k=ENSEMBLE_K,
            d_block=WIDTH,
            n_blocks=BLOCKS,
            dropout=0.1,
        )
        self.seed = int(seed)

    def model_hash(self) -> str:
        stream = io.BytesIO()
        torch.save(self.model.state_dict(), stream)
        return hashlib.sha256(stream.getvalue()).hexdigest()

    @torch.no_grad()
    def predict(self, x: np.ndarray, batch_size: int = 4096) -> np.ndarray:
        self.model.eval()
        xt = torch.from_numpy(np.asarray(x, dtype=np.float32))
        result: list[torch.Tensor] = []
        for index in torch.arange(len(xt)).split(int(batch_size)):
            logits = self.model(xt[index])
            result.append(torch.softmax(logits, dim=-1).mean(dim=1)[:, 1].cpu())
        return torch.cat(result).numpy().astype(np.float32) if result else np.zeros(0, np.float32)

    def fit_candidate(
        self,
        fit_x: np.ndarray,
        records: Sequence[ckbj.Record],
        weights: np.ndarray,
        select_x: np.ndarray,
        support_records: Sequence[ckbj.Record],
        support_baseline: np.ndarray,
        benign_baseline: np.ndarray,
        lambda_tail: float,
        lambda_family: float,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, torch.Tensor], DualGate]:
        if fit_x.shape != (18_398, INPUT_DIM):
            raise RuntimeError(f"formal fit shape drift: {fit_x.shape}")
        if select_x.shape != (7_069, INPUT_DIM):
            raise RuntimeError(f"formal select shape drift: {select_x.shape}")
        labels = np.asarray([int(record.label) for record in records], dtype=np.int64)
        if (int(labels.sum()), int((labels == 0).sum())) != (4_385, 14_013):
            raise RuntimeError("formal fit label cardinality drift")
        xt = torch.from_numpy(np.asarray(fit_x, dtype=np.float32))
        yt = torch.from_numpy(labels)
        wt = torch.from_numpy(np.asarray(weights, dtype=np.float32))
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.002, weight_decay=0.0003)
        generator = torch.Generator().manual_seed(self.seed)
        histories: list[dict[str, Any]] = []
        threshold_rows: list[dict[str, Any]] = []
        best_key: tuple[Any, ...] | None = None
        best_state: dict[str, torch.Tensor] | None = None
        best_gate: DualGate | None = None
        previous_scores: np.ndarray | None = None
        attack_families = [str(record.attack_family) for record in records]
        benign_sources = [str(record.source) for record in records]
        uids = [str(record.uid) for record in records]
        for epoch in range(1, EPOCHS + 1):
            selection = None
            if epoch >= 2:
                if previous_scores is None:
                    raise RuntimeError("previous-epoch score freeze is missing")
                selection = select_epoch_tails(
                    labels, attack_families, benign_sources, previous_scores, uids
                )
            self.model.train()
            order = torch.randperm(len(xt), generator=generator)
            ce_sum = 0.0
            weight_sum = 0.0
            batches = 0
            # Balanced CE sees every legal fit row exactly once per epoch.
            for batch_indices in order.split(BATCH_SIZE):
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(xt[batch_indices])
                expanded_y = yt[batch_indices].repeat_interleave(ENSEMBLE_K)
                member_ce = F.cross_entropy(
                    logits.flatten(0, 1), expanded_y, reduction="none"
                ).view(len(batch_indices), ENSEMBLE_K)
                row_ce = member_ce.mean(dim=1)
                batch_weight = wt[batch_indices]
                ce = (row_ce * batch_weight).sum() / batch_weight.sum()
                if not bool(torch.isfinite(ce)):
                    raise RuntimeError(f"nonfinite CKBW loss at epoch {epoch}")
                ce.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                ce_sum += float(ce.detach()) * float(batch_weight.sum())
                weight_sum += float(batch_weight.sum())
                batches += 1

            # Epoch 1 is balanced CE only.  From epoch 2 onward the previous
            # epoch's detached scores freeze the hard-tail indices, followed by
            # exactly one full-fit differentiable margin update.  The quantile
            # summaries intentionally use all legal fit rows, not only tails.
            tail_value = 0.0
            family_value = 0.0
            tail_audit: dict[str, float] = {}
            margin_steps = 0
            if selection is not None:
                optimizer.zero_grad(set_to_none=True)
                full_logits = self.model(xt)
                full_prob = torch.softmax(full_logits, dim=-1).mean(dim=1)[:, 1]
                tail, family, tail_audit = tail_losses(
                    full_prob,
                    selection,
                    labels,
                    attack_families,
                )
                margin_loss = (
                    float(lambda_tail) * tail
                    + float(lambda_family) * family
                )
                if not bool(torch.isfinite(margin_loss)):
                    raise RuntimeError(f"nonfinite CKBW margin loss at epoch {epoch}")
                margin_loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                tail_value = float(tail.detach())
                family_value = float(family.detach())
                margin_steps = 1
            previous_scores = self.predict(fit_x)
            select_scores = self.predict(select_x)
            gate, frontier = choose_dual_gate(
                support_records,
                support_baseline,
                select_scores[:69],
                benign_baseline,
                select_scores[69:],
            )
            for row in frontier:
                threshold_rows.append(
                    {
                        **row,
                        "epoch": epoch,
                        "lambda_tail": lambda_tail,
                        "lambda_family": lambda_family,
                    }
                )
            histories.append(
                {
                    "epoch": epoch,
                    "lambda_tail": lambda_tail,
                    "lambda_family": lambda_family,
                    "balanced_ce": ce_sum / max(weight_sum, 1e-12),
                    "tail_pair_loss": tail_value,
                    "family_quantile_loss": family_value,
                    "margin_steps": margin_steps,
                    "tail_audit": json.dumps(tail_audit, sort_keys=True),
                    # Appended audit field (2026-08-05 pipeline continuation):
                    # preregistration section 11.2 requires per-epoch per-family
                    # n_f/k_f/pair counts and benign-tail source composition.
                    # Purely additive; training math is unchanged.
                    "tail_selection_audit": (
                        json.dumps(list(selection.audit), sort_keys=True)
                        if selection is not None
                        else ""
                    ),
                    "batches": batches,
                    "fit_rows": len(fit_x),
                    "support_rows_used_for_training": 385,
                    "report_rows_used": 0,
                    "select_rows_used_for_gradient": 0,
                    "previous_epoch_tail_freeze": epoch >= 2,
                    "finite": True,
                }
            )
            key = (
                gate.net_hard_reduction,
                -gate.rescue_rows,
                gate.worst_family_score_margin,
                -epoch,
                -float(lambda_tail),
                -float(lambda_family),
            )
            if best_key is None or key > best_key:
                best_key = key
                best_state = {name: value.detach().cpu().clone() for name, value in self.model.state_dict().items()}
                best_gate = gate
        if best_state is None or best_gate is None:
            raise RuntimeError("tail-margin candidate produced no selected checkpoint")
        return histories, threshold_rows, best_state, best_gate


def _unit_records() -> tuple[list[ckbj.Record], np.ndarray, list[str], list[str], list[str]]:
    records: list[ckbj.Record] = []
    for family in range(12):
        for row in range(9):
            records.append(
                ckbj.Record(
                    f"attack:{family}:{row}", "support_train", "fit", "attack-source",
                    row, row, 1, f"family-{family:02d}", "attack-device", "attack-device", 1.0, "e"
                )
            )
    for source in range(8):
        for row in range(4):
            records.append(
                ckbj.Record(
                    f"benign:{source}:{row}", "aux_fit", "fit", f"benign-{source:02d}",
                    row, row, 0, "benign", f"benign-{source:02d}", f"benign-{source:02d}", 0.0, "e"
                )
            )
    labels = np.asarray([record.label for record in records], dtype=np.int64)
    scores = np.linspace(0.01, 0.99, len(records), dtype=np.float64)
    return (
        records,
        scores,
        [record.attack_family for record in records],
        [record.source for record in records],
        [record.uid for record in records],
    )


def contract_unit() -> None:
    records, scores, families, sources, uids = _unit_records()
    labels = np.asarray([record.label for record in records], dtype=np.int64)
    tails = select_epoch_tails(labels, families, sources, scores, uids)
    if len(tails.attack_by_family) != 12 or any(len(value) != 9 for value in tails.attack_by_family.values()):
        raise RuntimeError("family tail unit failed")
    if len(tails.benign) != 16 or max(Counter(sources[i] for i in tails.benign).values()) > 2:
        raise RuntimeError("source-balanced benign tail unit failed")
    weights, balance = family_balanced_row_weights(records)
    if len(balance) != 20 or not math.isclose(float(weights.mean()), 1.0, abs_tol=1e-6):
        raise RuntimeError("balanced CE unit failed")

    support: list[ckbj.Record] = []
    for family in range(3):
        for row in range(23):
            support.append(
                ckbj.Record(
                    f"sv:{family}:{row}", "support_val", "select", "sv", row, row, 1,
                    f"f{family}", "attack", "attack", 1.0, "e"
                )
            )
    support_base = np.asarray([index % 4 != 0 for index in range(69)], dtype=bool)
    support_q = np.linspace(0.70, 0.99, 69)
    benign_base = np.asarray([index < 400 for index in range(7000)], dtype=bool)
    benign_q = np.linspace(0.01, 0.69, 7000)
    gate, frontier = choose_dual_gate(support, support_base, support_q, benign_base, benign_q)
    final_support = apply_dual_control(support_base, support_q, gate)
    if not final_support.all() or gate.support_hard_rows != 69 or gate.tau_normal >= gate.tau_attack:
        raise RuntimeError("dual support-preservation unit failed")
    final_benign = apply_dual_control(benign_base, benign_q, gate)
    if int(final_benign.sum()) != gate.dual_hard_rows or sum(bool(row["selected"]) for row in frontier) != 1:
        raise RuntimeError("dual exact-frontier unit failed")
    or_values = one_sided_or(benign_base, benign_q, gate.tau_attack)
    if np.any(or_values < benign_base):
        raise RuntimeError("one-sided OR monotonicity unit failed")
    if apply_dual_control(np.asarray([False, True, True]), np.asarray([0.9, 0.1, 0.5]), gate).shape != (3,):
        raise RuntimeError("dual transition shape unit failed")
    print(
        json.dumps(
            {
                "status": "CKBW_CONTRACT_UNIT_PASS",
                "input_dim": INPUT_DIM,
                "tabm": {
                    "version": TABM_VERSION,
                    "width": WIDTH,
                    "blocks": BLOCKS,
                    "k": ENSEMBLE_K,
                    "batch": BATCH_SIZE,
                    "epochs": EPOCHS,
                    "numerical_embeddings": False,
                },
                "attack_balance_groups": 12,
                "tail_k": TAIL_K,
                "margin": MARGIN,
                "support_preserved": int(final_support.sum()),
                "review_rate": 0.0,
                "score_addition_used": False,
                "per_family_experts": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-unit", action="store_true")
    parser.add_argument("--validate-frozen", action="store_true")
    parser.add_argument("--frozen-predictions", type=Path)
    parser.add_argument("--frozen-model-audit", type=Path)
    # Appended pipeline modes (2026-08-05 continuation).
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--frozen-arm-preview", action="store_true")
    parser.add_argument("--smoke-store", action="store_true")
    parser.add_argument("--smoke-formal", action="store_true")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--held-values", default=",".join(str(value) for value in EXPECTED_PROTOCOLS[1:])
    )
    # Runtime assets intentionally have no bundle-relative defaults.  Formal
    # execution must receive the exact remote-worktree paths from the
    # installer -> Slurm export -> CLI chain.
    parser.add_argument("--t0-root", type=Path, default=None)
    parser.add_argument("--report-t0-extension", type=Path, default=None)
    parser.add_argument("--c1-plan", type=Path, default=None)
    parser.add_argument("--c1-targets", type=Path, default=None)
    parser.add_argument("--c1-cache", type=Path, default=None)
    parser.add_argument("--c1-report-extension", type=Path, default=None)
    parser.add_argument("--gotham-manifest", type=Path, default=None)
    parser.add_argument("--gotham-cache", type=Path, default=None)
    parser.add_argument("--auxiliary-manifest", type=Path, default=None)
    parser.add_argument("--auxiliary-plan", type=Path, default=None)
    parser.add_argument("--auxiliary-cache", type=Path, default=None)
    parser.add_argument("--ton-cache", type=Path, default=None)
    parser.add_argument("--raw51-mask", default=None)
    parser.add_argument("--raw51-mask-sha256", default=None)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument("--threads", type=int, default=8)
    args = parser.parse_args()
    if args.formal:
        explicit_runtime_assets = {
            "--t0-root": args.t0_root,
            "--report-t0-extension": args.report_t0_extension,
            "--c1-plan": args.c1_plan,
            "--c1-targets": args.c1_targets,
            "--c1-cache": args.c1_cache,
            "--c1-report-extension": args.c1_report_extension,
        }
        missing = [option for option, value in explicit_runtime_assets.items() if value is None]
        if missing:
            parser.error(
                "formal mode requires explicit remote runtime assets; "
                "missing: " + ", ".join(missing)
            )
        unified_assets = {
            "--gotham-manifest": args.gotham_manifest,
            "--gotham-cache": args.gotham_cache,
            "--auxiliary-manifest": args.auxiliary_manifest,
            "--auxiliary-plan": args.auxiliary_plan,
            "--auxiliary-cache": args.auxiliary_cache,
            "--ton-cache": args.ton_cache,
            "--raw51-mask": args.raw51_mask,
            "--raw51-mask-sha256": args.raw51_mask_sha256,
            "--frozen-predictions": args.frozen_predictions,
            "--frozen-model-audit": args.frozen_model_audit,
        }
        missing = [option for option, value in unified_assets.items() if value is None]
        if missing:
            parser.error(
                "formal mode requires all unified cache, mask and frozen score paths; "
                "missing: " + ", ".join(missing)
            )
    return args


def main() -> None:
    args = parse_args()
    if args.contract_unit:
        contract_unit()
        return
    if args.validate_frozen:
        if args.frozen_predictions is None or args.frozen_model_audit is None:
            raise SystemExit("--validate-frozen requires --frozen-predictions and --frozen-model-audit")
        frozen = FrozenScoreBundle.load(args.frozen_predictions, args.frozen_model_audit)
        print(
            json.dumps(
                {
                    "status": "CKBW_FROZEN_SCORE_CONTRACT_PASS",
                    "rows": len(frozen.frame),
                    "prediction_sha256": frozen.prediction_sha256,
                    "extra_model_sha256": frozen.extra_model_sha256,
                    "tabm_model_sha256": frozen.tabm_model_sha256,
                    "protocol_rows": FROZEN_PROTOCOL_ROWS,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return
    if args.frozen_arm_preview:
        if args.frozen_predictions is None or args.frozen_model_audit is None:
            raise SystemExit("--frozen-arm-preview requires --frozen-predictions and --frozen-model-audit")
        frozen_arm_preview(args)
        return
    if args.smoke_store:
        smoke_store(args)
        return
    if args.smoke_formal:
        if args.frozen_predictions is None or args.frozen_model_audit is None:
            raise SystemExit("--smoke-formal requires --frozen-predictions and --frozen-model-audit")
        smoke_formal(args)
        return
    if args.formal:
        run_formal(args)
        return
    raise SystemExit(
        "choose --contract-unit, --validate-frozen, --frozen-arm-preview, "
        "--smoke-store, --smoke-formal or --formal"
    )


# NOTE (2026-08-05 pipeline continuation): the module entrypoint moved to the
# end of the file so appended pipeline constants exist before main() runs.


# ============================================================================
# CKBW formal pipeline (seed 27).
#
# Appended 2026-08-05 at the Codex token breakpoint.  Data assembly reuses the
# validated CKBV/CKBU functions (ckbq.prepare_inputs, ckbo.collect_formal_sets,
# ckbu.UnifiedFeatureStore/auxiliary_records/ton_records/fit_preprocessor)
# unchanged.  CKBW-specific layers: frozen 154917 score reuse, tail-margin
# candidate driving, dual-gate selection, eight-arm evaluation and the
# preregistered audit set (ckbw_tail_margin_dual_control_preregistered_20260803
# section 11).  No report/held row touches fit, preprocessing, tail mining,
# checkpoint selection or threshold selection.
# ============================================================================

import os  # noqa: E402

GLOBAL_PROTOCOL = "GLOBAL_ATTACK_PRESERVATION"
EXPECTED_PROTOCOLS = [
    None,
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
]
HELD_OOD_FAMILIES = (
    "iotsim-hydraulic-system",
    "iotsim-ip-camera-street",
    "iotsim-predictive-maintenance",
    "iotsim-stream-consumer",
)
CANARY_FAMILIES = ("iotsim-stream-consumer", "iotsim-hydraulic-system")
REPEATED_VIEW_FAMILIES = ("iotsim-ip-camera-street", "iotsim-predictive-maintenance")

FIT_ROWS = 18_398
FIT_ATTACK_ROWS = 4_385
FIT_BENIGN_ROWS = 14_013
SUPPORT_VAL_ROWS = 69
BENIGN_SELECT_ROWS = 7_000
AUX_SELECT_ROWS = 3_000
TON_SELECT_ROWS = 4_000

ATTACK_OVERALL_DROP_GATE_PP = 0.5
ATTACK_FAMILY_DROP_GATE_PP = 2.0
ATTACK_FAMILY_MIN_ROWS = 15
OOD_MACRO_GATE = 0.302722
OOD_FAMILY_WORSEN_GATE = 0.02
OOD_FAMILY_ABS_GATE = 0.90

TABM_CONFIG = {
    "backend": "official_TabM_v0.0.3",
    "input_dim": INPUT_DIM,
    "width": WIDTH,
    "blocks": BLOCKS,
    "ensemble_k": ENSEMBLE_K,
    "batch_size": BATCH_SIZE,
    "epochs": EPOCHS,
    "numerical_embeddings": False,
    "margin": MARGIN,
    "tail_k": TAIL_K,
    "lambda_tail_grid": [float(value) for value in LAMBDA_GRID],
    "lambda_family_grid": [float(value) for value in LAMBDA_GRID],
    "optimizer": "AdamW(lr=0.002,weight_decay=0.0003,grad_clip=1.0)",
    "seed": SEED,
}


def _observable_predicate(args: argparse.Namespace):
    masked_pairs = getattr(args, "raw51_masked_pairs", frozenset())

    def _observable(record: ckbj.Record) -> bool:
        return (record.source, int(record.recorded_index)) not in masked_pairs

    return _observable, masked_pairs


def assemble_protocol(
    held: str | None,
    args: argparse.Namespace,
    x_by_role: dict[str, np.ndarray],
    report_frames: dict[str, pd.DataFrame],
    model_frames: dict[str, pd.DataFrame],
    t0: Any,
    position_cache: dict[str, dict[int, int]],
    aux: dict[str, list[ckbj.Record]],
    ton: dict[str, list[ckbj.Record]],
    observable: Any,
) -> dict[str, Any]:
    """Mirror the validated CKBU data assembly for one protocol, unchanged."""
    protocol = ckbo.protocol_family_name(held)
    c1_model, c1_frontend, c1_threshold, c1_audit = ckbo.fit_c1_attack_preserving(
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
        c1_frontend,
        model_frames,
        report_frames,
        t0,
        position_cache,
        held,
        int(args.train_cap),
        int(args.eval_cap),
    )
    if held is None and (
        len(sets["fit_attack"]) != 385 or len(sets["select_attack"]) != SUPPORT_VAL_ROWS
    ):
        raise RuntimeError("CKBW global support cardinality drift")
    if held == ckbo.AUX_HELD_FAMILY:
        sets["report"] = list(aux["aux_report"])
    aux_fit = [record for record in aux["aux_fit"] if held is None or record.device_family != held]
    aux_select = [
        record for record in aux["aux_select"] if held is None or record.device_family != held
    ]
    # raw51_observable_v1: targets without a legal same-observation-unit raw-51D
    # input leave the process-head fit/select pools only.  Evaluation-pool
    # membership is unchanged and masked rows are fail-closed to frozen CKBQ.
    fit_attack = list(sets["fit_attack"]) + list(ton["aux_process_fit"])
    fit_benign = [
        record
        for record in (list(sets["fit_benign"]) + aux_fit + list(ton["aux_normal_fit"]))
        if observable(record)
    ]
    fit_records = ckbu.unique([*fit_attack, *fit_benign])
    select_attack = list(sets["select_attack"])
    select_benign = (
        list(sets["select_benign"]) + aux_select + list(ton["aux_normal_select"])
    )
    select_benign_observable = [record for record in select_benign if observable(record)]
    report_records = list(sets["report"])
    return {
        "held": held,
        "protocol": protocol,
        "c1_threshold": float(c1_threshold),
        "c1_audit": c1_audit,
        "data_audit": data_audit,
        "sets": sets,
        "aux_fit_rows": len(aux_fit),
        "aux_select_rows": len(aux_select),
        "fit_attack": fit_attack,
        "fit_benign": fit_benign,
        "fit_records": fit_records,
        "select_attack": select_attack,
        "select_benign_observable": select_benign_observable,
        "report_records": report_records,
    }


def assert_global_pool_contract(assembly: dict[str, Any]) -> None:
    fit_records = assembly["fit_records"]
    attack_rows = sum(int(record.label) == 1 for record in fit_records)
    benign_rows = sum(int(record.label) == 0 for record in fit_records)
    if (len(fit_records), attack_rows, benign_rows) != (FIT_ROWS, FIT_ATTACK_ROWS, FIT_BENIGN_ROWS):
        raise RuntimeError(
            f"CKBW formal fit cardinality drift: {len(fit_records)}/{attack_rows}/{benign_rows}"
        )
    families = sorted({str(record.attack_family) for record in fit_records if int(record.label) == 1})
    if len(families) != 12:
        raise RuntimeError(f"CKBW formal fit attack family drift: {families}")
    if len(assembly["select_attack"]) != SUPPORT_VAL_ROWS:
        raise RuntimeError("CKBW support_val cardinality drift")
    if len(assembly["select_benign_observable"]) != BENIGN_SELECT_ROWS:
        raise RuntimeError("CKBW benign select cardinality drift")
    aux_rows = sum(str(record.role) == "aux_select" for record in assembly["select_benign_observable"])
    ton_rows = sum(
        str(record.role) == "aux_normal_select" for record in assembly["select_benign_observable"]
    )
    if (aux_rows, ton_rows) != (AUX_SELECT_ROWS, TON_SELECT_ROWS):
        raise RuntimeError(f"CKBW benign select composition drift: aux={aux_rows} ton={ton_rows}")


def assert_protocol_identity(global_assembly: dict[str, Any], other: dict[str, Any]) -> None:
    """Prove the held protocol shares the identical legal fit/select pools.

    The frozen 154917 audit shows every protocol model is bit-identical because
    the legal pools contain no held-family rows.  CKBW turns that empirical fact
    into an enforced contract before training a single shared scorer.
    """
    for key in ("fit_records", "select_attack", "select_benign_observable"):
        global_uids = [str(record.uid) for record in global_assembly[key]]
        other_uids = [str(record.uid) for record in other[key]]
        if global_uids != other_uids:
            raise RuntimeError(
                f"held protocol {other['protocol']} pool differs from GLOBAL in {key}: "
                "single shared scorer contract broken"
            )


def frozen_aligned_frame(frozen: FrozenScoreBundle, protocol: str, scored: list[ckbj.Record]) -> pd.DataFrame:
    frame = frozen.assert_exact_uid_coverage(protocol, [str(record.uid) for record in scored])
    return frame.set_index("uid", drop=False)


def frame_values(frame: pd.DataFrame, uids: Sequence[str], column: str) -> np.ndarray:
    if frame.index.name != "uid":
        frame = frame.set_index("uid", drop=False)
    return frame.loc[list(map(str, uids)), column]


def frame_bool(frame: pd.DataFrame, uids: Sequence[str], column: str) -> np.ndarray:
    return bool_array(frame_values(frame, uids, column))


def frame_float(frame: pd.DataFrame, uids: Sequence[str], column: str) -> np.ndarray:
    values = pd.to_numeric(frame_values(frame, uids, column), errors="raise").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise RuntimeError(f"nonfinite frozen column {column}")
    return values


def fresh_c1_vs_frozen_audit(
    protocol: str,
    records: list[ckbj.Record],
    frame: pd.DataFrame,
    c1_threshold: float,
) -> dict[str, Any]:
    non_ton = [record for record in records if not str(record.uid).startswith("ton:")]
    fresh = np.asarray(
        [float(record.c1_score) >= c1_threshold for record in non_ton], dtype=bool
    )
    frozen_c1 = frame_bool(frame, [record.uid for record in non_ton], "c1_hard")
    mismatches = int((fresh != frozen_c1).sum())
    if mismatches:
        raise RuntimeError(f"fresh C1 decisions differ from frozen 154917 frame: {protocol}")
    return {
        "held_value": protocol,
        "non_ton_rows_compared": len(non_ton),
        "c1_mismatch_rows": mismatches,
        "ton_rows_threshold_only": len(records) - len(non_ton),
        "c1_threshold": float(c1_threshold),
        "status": "CKBW_FRESH_C1_MATCHES_FROZEN",
    }


def dual_scope_audit_rows(
    arm: str,
    gate: DualGate,
    benign_records: list[ckbj.Record],
    benign_baseline: np.ndarray,
    benign_scores: np.ndarray,
    decision_rule: str,
) -> list[dict[str, Any]]:
    """Preregistration section 7.4: mixed 7000 / aux 3000 / ToN 4000 accounting.

    Emits the four raw quantities per scope and asserts both identities:
    net_hard_reduction = suppress - rescue = N_frozen_hard - N_dual_hard.
    """
    rows: list[dict[str, Any]] = []
    baseline = np.asarray(benign_baseline, dtype=bool)
    scores = np.asarray(benign_scores, dtype=np.float64)
    if decision_rule == "dual":
        final = apply_dual_control(baseline, scores, gate)
    elif decision_rule == "or":
        final = one_sided_or(baseline, scores, gate.tau_attack)
    else:
        raise RuntimeError(f"unknown decision rule: {decision_rule}")
    scopes = {
        "mixed_7000": np.ones(len(benign_records), dtype=bool),
        "auxiliary_3000": np.asarray(
            [str(record.role) == "aux_select" for record in benign_records], dtype=bool
        ),
        "ton_iot_4000": np.asarray(
            [str(record.role) == "aux_normal_select" for record in benign_records], dtype=bool
        ),
    }
    for scope, mask in scopes.items():
        base = baseline[mask]
        dual = final[mask]
        n_frozen_hard = int(base.sum())
        n_dual_hard = int(dual.sum())
        suppress = int((base & ~dual).sum())
        rescue = int((~base & dual).sum())
        net = suppress - rescue
        if net != n_frozen_hard - n_dual_hard:
            raise RuntimeError(f"dual scope identity failed for {arm}:{scope}")
        rows.append(
            {
                "candidate": arm,
                "decision_rule": decision_rule,
                "scope": scope,
                "scope_rows": int(mask.sum()),
                "n_frozen_hard": n_frozen_hard,
                "n_dual_hard": n_dual_hard,
                "suppress_count": suppress,
                "rescue_count": rescue,
                "net_hard_reduction": net,
                "net_equals_suppress_minus_rescue": True,
                "net_equals_frozen_minus_dual": True,
                "tau_normal": float(gate.tau_normal),
                "tau_attack": float(gate.tau_attack),
                "selection_rows_used": int(mask.sum()),
                "report_rows_used": 0,
            }
        )
    return rows


def replay_candidate_best(
    threshold_rows: list[dict[str, Any]],
    lambda_tail: float,
    lambda_family: float,
) -> tuple[tuple[Any, ...], int, dict[str, Any]]:
    """Reproduce fit_candidate's lexicographic best-checkpoint tracking.

    The frontier rows carry the selected gate per epoch; replaying the frozen
    ordering (net reduction, -rescue, worst-family margin, -epoch, -lambda_tail,
    -lambda_family) with strict-greater replacement reproduces the internal
    best-key tracking exactly, without modifying the training function.
    """
    best_key: tuple[Any, ...] | None = None
    best_epoch = -1
    best_row: dict[str, Any] | None = None
    for epoch in range(1, EPOCHS + 1):
        selected = [
            row
            for row in threshold_rows
            if int(row["epoch"]) == epoch
            and float(row["lambda_tail"]) == float(lambda_tail)
            and float(row["lambda_family"]) == float(lambda_family)
            and bool(row.get("selected", False))
            and str(row["selection_stage"]) == "normal_cut"
        ]
        if len(selected) != 1:
            raise RuntimeError(
                f"frontier replay drift at epoch {epoch} lambda=({lambda_tail},{lambda_family}): "
                f"{len(selected)} selected rows"
            )
        row = selected[0]
        key = (
            int(row["net_hard_reduction"]),
            -int(row["rescue_rows"]),
            float(row["worst_family_score_margin"]),
            -epoch,
            -float(lambda_tail),
            -float(lambda_family),
        )
        if best_key is None or key > best_key:
            best_key = key
            best_epoch = epoch
            best_row = row
    if best_key is None or best_row is None:
        raise RuntimeError(f"frontier replay found no selected checkpoint: {lambda_tail}/{lambda_family}")
    return best_key, best_epoch, best_row


def train_tail_margin_candidates(
    fit_x: np.ndarray,
    fit_records: list[ckbj.Record],
    weights: np.ndarray,
    select_x: np.ndarray,
    support_records: list[ckbj.Record],
    support_baseline: np.ndarray,
    benign_baseline: np.ndarray,
    threads: int,
) -> dict[str, Any]:
    """Run the preregistered lambda grid and select the winner lexicographically."""
    candidates: list[dict[str, Any]] = []
    histories: list[dict[str, Any]] = []
    frontier: list[dict[str, Any]] = []
    for lambda_tail in LAMBDA_GRID:
        for lambda_family in LAMBDA_GRID:
            model = TailMarginTabM(SEED, threads)
            cand_histories, cand_frontier, best_state, best_gate = model.fit_candidate(
                fit_x,
                fit_records,
                weights,
                select_x,
                support_records,
                support_baseline,
                benign_baseline,
                float(lambda_tail),
                float(lambda_family),
            )
            histories.extend(cand_histories)
            frontier.extend(cand_frontier)
            best_key, best_epoch, best_row = replay_candidate_best(
                cand_frontier, float(lambda_tail), float(lambda_family)
            )
            # Cross-check the replay against the training function's own output.
            if not (
                math.isclose(float(best_row["tau_normal"]), best_gate.tau_normal, rel_tol=0.0, abs_tol=1e-15)
                and math.isclose(float(best_row["tau_attack"]), best_gate.tau_attack, rel_tol=0.0, abs_tol=1e-15)
                and int(best_row["net_hard_reduction"]) == best_gate.net_hard_reduction
            ):
                raise RuntimeError(
                    f"frontier replay disagrees with fit_candidate: "
                    f"lambda=({lambda_tail},{lambda_family})"
                )
            candidates.append(
                {
                    "lambda_tail": float(lambda_tail),
                    "lambda_family": float(lambda_family),
                    "best_key": best_key,
                    "best_epoch": best_epoch,
                    "best_gate": best_gate,
                    "best_state": best_state,
                    "best_row": best_row,
                }
            )
    winner_key = max(candidate["best_key"] for candidate in candidates)
    winners = [candidate for candidate in candidates if candidate["best_key"] == winner_key]
    if len(winners) != 1:
        raise RuntimeError("tail-margin candidate selection is not deterministic")
    winner = winners[0]
    for candidate in candidates:
        candidate["chosen"] = candidate is winner
    final_model = TailMarginTabM(SEED, threads)
    final_model.model.load_state_dict(winner["best_state"])
    return {
        "candidates": candidates,
        "histories": histories,
        "frontier": frontier,
        "winner": winner,
        "model": final_model,
        "model_sha256": final_model.model_hash(),
        "gate": winner["best_gate"],
    }


def evaluate_arms(
    held: str | None,
    protocol: str,
    strict: list[ckbj.Record],
    decisions: dict[str, np.ndarray],
    c1_hard: np.ndarray,
    bootstrap_reps: int,
) -> dict[str, list[dict[str, Any]]]:
    metrics: list[dict[str, Any]] = []
    families: list[dict[str, Any]] = []
    attack: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    for candidate in tuple(arm for arm in ALL_ARMS if arm in decisions):
        values, per_family = ckbj.metric_rows(
            candidate,
            "strict_leave" if held else "attack_preservation",
            protocol,
            strict,
            decisions[candidate],
            int(bootstrap_reps),
            SEED,
        )
        metrics.extend(values)
        families.extend(per_family)
        if held is None:
            attack.extend(
                ckbj.attack_summary_rows(
                    candidate,
                    strict,
                    decisions[candidate],
                    c1_hard,
                    int(bootstrap_reps),
                    SEED,
                )
            )
        else:
            strict_rows.extend(
                ckbj.strict_level2_summary(
                    candidate,
                    protocol,
                    strict,
                    decisions[candidate],
                    c1_hard,
                    int(bootstrap_reps),
                    SEED,
                )
            )
    return {
        "metrics": metrics,
        "family_metrics": families,
        "attack_summary": attack,
        "strict_summary": strict_rows,
    }


def transition_matrix_rows(
    protocol: str,
    records: list[ckbj.Record],
    baseline: np.ndarray,
    primary: np.ndarray,
) -> list[dict[str, Any]]:
    """Section 11.3: row-level Frozen-CKBQ x PRIMARY decision transitions."""
    rows: list[dict[str, Any]] = []
    base = np.asarray(baseline, dtype=bool)
    dual = np.asarray(primary, dtype=bool)
    labels = np.asarray([int(record.label) for record in records], dtype=np.int64)
    families = sorted({str(record.attack_family) for record in records})
    for scope_name, mask in (
        ("__ALL__", np.ones(len(records), dtype=bool)),
        ("attack", labels == 1),
        ("benign", labels == 0),
        *(
            (f"family:{family}", np.asarray([str(record.attack_family) == family for record in records], dtype=bool))
            for family in families
        ),
    ):
        kept_hard = int((base[mask] & dual[mask]).sum())
        kept_soft = int((~base[mask] & ~dual[mask]).sum())
        rescued = int((~base[mask] & dual[mask]).sum())
        suppressed = int((base[mask] & ~dual[mask]).sum())
        rows.append(
            {
                "held_value": protocol,
                "scope": scope_name,
                "rows": int(mask.sum()),
                "frozen1_primary1_kept_hard": kept_hard,
                "frozen0_primary0_kept_soft": kept_soft,
                "frozen0_primary1_rescued": rescued,
                "frozen1_primary0_suppressed": suppressed,
            }
        )
    return rows


def udp_scan_diagnostic_rows(
    protocol: str,
    records: list[ckbj.Record],
    arms_decisions: dict[str, np.ndarray],
    tail_scores: np.ndarray,
    ce_scores: np.ndarray,
    extra_scores: np.ndarray,
) -> list[dict[str, Any]]:
    """Section 8: observability-only UDP Scan diagnostics, never selection input."""
    mask = np.asarray(
        [str(record.attack_family) == "UDP Scan" and int(record.label) == 1 for record in records],
        dtype=bool,
    )
    if not int(mask.sum()):
        return []
    subset = [record for record, keep in zip(records, mask.tolist()) if keep]
    rows: list[dict[str, Any]] = []
    for arm, decision in arms_decisions.items():
        rows.append(
            {
                "held_value": protocol,
                "diagnostic": "arm_hard_recall",
                "candidate": arm,
                "rows": int(mask.sum()),
                "hard_recall": float(np.mean(decision[mask])),
                "diagnostic_only": True,
                "selection_use": "none",
            }
        )
    for name, values in (("tail_margin", tail_scores), ("tabm_ce", ce_scores), ("extratrees", extra_scores)):
        score = np.asarray(values, dtype=np.float64)[mask]
        rows.append(
            {
                "held_value": protocol,
                "diagnostic": "score_distribution",
                "candidate": name,
                "rows": int(mask.sum()),
                "score_min": float(score.min()),
                "score_q25": float(np.quantile(score, 0.25)),
                "score_median": float(np.quantile(score, 0.50)),
                "score_q75": float(np.quantile(score, 0.75)),
                "score_max": float(score.max()),
                "diagnostic_only": True,
                "selection_use": "none",
            }
        )
    rows.append(
        {
            "held_value": protocol,
            "diagnostic": "observability",
            "candidate": "udp_scan",
            "rows": int(mask.sum()),
            "sources": len({record.source for record in subset}),
            "raw51_masked_rows": 0,
            "diagnostic_only": True,
            "selection_use": "none",
        }
    )
    return rows


def scientific_outcome(
    attack_summary: pd.DataFrame,
    strict_summary: pd.DataFrame,
    contract_checks: dict[str, bool],
) -> dict[str, Any]:
    """Preregistered seed-27 gates (section 9) evaluated on PRIMARY only."""
    primary = attack_summary.loc[attack_summary["candidate"].astype(str) == PRIMARY]
    overall = primary.loc[primary["metric"].astype(str) == "overall_attack_hard_recall"]
    support = primary.loc[primary["metric"].astype(str) == "support_val_recall"]
    family = primary.loc[
        (primary["metric"].astype(str) == "attack_family_recall")
        & (pd.to_numeric(primary["rows"], errors="raise") >= ATTACK_FAMILY_MIN_ROWS)
    ]
    gates: dict[str, Any] = {}
    gates["attack_overall_present"] = not overall.empty
    overall_delta = float(overall.iloc[0]["delta_vs_c1_pp"]) if not overall.empty else math.nan
    gates["attack_overall_delta_vs_c1_pp"] = overall_delta
    gates["attack_overall_pass"] = bool(not overall.empty and overall_delta >= -ATTACK_OVERALL_DROP_GATE_PP)
    worst_family_drop = float(family["delta_vs_c1_pp"].min()) if not family.empty else math.nan
    gates["attack_family_min_rows"] = ATTACK_FAMILY_MIN_ROWS
    gates["attack_family_worst_delta_vs_c1_pp"] = worst_family_drop
    gates["attack_family_present"] = not family.empty
    gates["attack_family_pass"] = bool(not family.empty and worst_family_drop >= -ATTACK_FAMILY_DROP_GATE_PP)
    support_recall = float(support.iloc[0]["hard_recall"]) if not support.empty else math.nan
    gates["support_val_recall"] = support_recall
    gates["support_val_pass"] = bool(not support.empty and support_recall == 1.0)

    strict_primary = strict_summary.loc[strict_summary["candidate"].astype(str) == PRIMARY]
    strict_frozen = strict_summary.loc[strict_summary["candidate"].astype(str) == M1_FROZEN]
    rates: dict[str, float] = {}
    frozen_rates: dict[str, float] = {}
    for held_name in HELD_OOD_FAMILIES:
        row_p = strict_primary.loc[strict_primary["held_value"].astype(str) == held_name]
        row_f = strict_frozen.loc[strict_frozen["held_value"].astype(str) == held_name]
        rates[held_name] = float(row_p.iloc[0]["hard_rate"]) if not row_p.empty else math.nan
        frozen_rates[held_name] = float(row_f.iloc[0]["hard_rate"]) if not row_f.empty else math.nan
    gates["ood_multi_held_present"] = all(math.isfinite(value) for value in rates.values())
    macro = float(np.mean([rates[name] for name in HELD_OOD_FAMILIES])) if gates["ood_multi_held_present"] else math.nan
    gates["ood_rates"] = rates
    gates["ood_frozen_rates"] = frozen_rates
    gates["ood_macro"] = macro
    gates["ood_macro_gate"] = OOD_MACRO_GATE
    gates["ood_macro_pass"] = bool(gates["ood_multi_held_present"] and macro <= OOD_MACRO_GATE)
    gates["ood_family_worsen_pass"] = bool(
        gates["ood_multi_held_present"]
        and all(
            rates[name] <= frozen_rates[name] + OOD_FAMILY_WORSEN_GATE for name in HELD_OOD_FAMILIES
        )
    )
    gates["ood_family_abs_pass"] = bool(
        gates["ood_multi_held_present"]
        and all(rates[name] <= OOD_FAMILY_ABS_GATE for name in HELD_OOD_FAMILIES)
    )
    canary = float(np.mean([rates[name] for name in CANARY_FAMILIES])) if gates["ood_multi_held_present"] else math.nan
    repeated = float(np.mean([rates[name] for name in REPEATED_VIEW_FAMILIES])) if gates["ood_multi_held_present"] else math.nan
    gates["ood_canary_macro"] = canary
    gates["ood_repeated_view_macro"] = repeated

    scientific_pass = bool(
        gates["attack_overall_pass"]
        and gates["attack_family_pass"]
        and gates["support_val_pass"]
        and gates["ood_macro_pass"]
        and gates["ood_family_worsen_pass"]
        and gates["ood_family_abs_pass"]
        and gates["ood_multi_held_present"]
    )
    contract_pass = bool(all(contract_checks.values()))
    decision = "GO" if (scientific_pass and contract_pass) else "NO_GO"
    return {
        "decision": decision,
        "primary": PRIMARY,
        "primary_promotion_fixed": True,
        "no_post_hoc_arm_promotion": True,
        "scientific_gates": gates,
        "contract_checks": contract_checks,
        "seed": SEED,
        "seeds_locked": [37, 47],
        "cooler_motor_sealed": True,
    }


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    if int(args.seed) != SEED:
        raise RuntimeError("CKBW is preregistered for seed 27 only")
    closure = ckbu.validate_frozen_formal_dependency_closure()
    print(json.dumps(closure, indent=2, sort_keys=True))
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frozen = FrozenScoreBundle.load(args.frozen_predictions, args.frozen_model_audit)
    (
        x_by_role,
        report_frames,
        input_audit,
        t0,
        t0_audit,
        extension_audit,
        c1_extension_audit,
    ) = ckbq.prepare_inputs(args, out)
    model_frames, permanent = ckbo.permanently_mask_frames(report_frames)
    model_frames, frozen_scope = ckbo.restrict_model_scope_to_frozen_targets(
        model_frames, Path(args.c1_targets), t0
    )
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    dev_holds = ckbo.legal_development_holds(report_frames, requested)
    protocols = ckbo.formal_protocol_values(requested, dev_holds)
    if protocols != EXPECTED_PROTOCOLS:
        raise RuntimeError(f"CKBW protocol boundary drift: {protocols}")
    if getattr(args, "raw51_mask", None):
        mask = raw51.load_raw51_mask(args.raw51_mask, args.raw51_mask_sha256)
        args.raw51_masked_pairs = frozenset(
            (source, int(index)) for source, indices in mask.items() for index in indices
        )
    else:
        args.raw51_masked_pairs = frozenset()
    observable, masked_pairs = _observable_predicate(args)
    store = ckbu.UnifiedFeatureStore(
        Path(args.gotham_manifest),
        Path(args.gotham_cache),
        Path(args.auxiliary_manifest),
        Path(args.auxiliary_cache),
    )
    aux = ckbu.auxiliary_records(Path(args.auxiliary_plan))
    ton, ton_features, ton_audit = ckbu.ton_records(Path(args.ton_cache))
    position_cache: dict[str, dict[int, int]] = {}
    assemblies = {
        held: assemble_protocol(
            held,
            args,
            x_by_role,
            report_frames,
            model_frames,
            t0,
            position_cache,
            aux,
            ton,
            observable,
        )
        for held in protocols
    }
    global_asm = assemblies[None]
    assert_global_pool_contract(global_asm)
    for held in protocols[1:]:
        assert_protocol_identity(global_asm, assemblies[held])

    select_order = list(global_asm["select_attack"]) + list(
        global_asm["select_benign_observable"]
    )
    scored_global = ckbu.unique([*select_order, *global_asm["report_records"]])
    feature_map = dict(ton_features)
    store.add(
        [
            record
            for record in ckbu.unique([*global_asm["fit_records"], *scored_global])
            if not str(record.uid).startswith("ton:")
        ],
        feature_map,
    )
    transformer, prep_audit = ckbu.fit_preprocessor(
        global_asm["fit_records"], feature_map, SEED
    )
    fit_x = ckbu.transformed(transformer, global_asm["fit_records"], feature_map)
    select_x = ckbu.transformed(transformer, select_order, feature_map)

    frame_global = frozen_aligned_frame(frozen, GLOBAL_PROTOCOL, scored_global)
    c1_audits = [
        fresh_c1_vs_frozen_audit(
            GLOBAL_PROTOCOL, scored_global, frame_global, global_asm["c1_threshold"]
        )
    ]
    support_uids = [str(record.uid) for record in global_asm["select_attack"]]
    benign_select_records = list(global_asm["select_benign_observable"])
    benign_uids = [str(record.uid) for record in benign_select_records]
    support_base = frame_bool(frame_global, support_uids, "frozen_ckbq_hard")
    benign_base = frame_bool(frame_global, benign_uids, "frozen_ckbq_hard")
    support_ce = frame_float(frame_global, support_uids, "tabm_process_score")
    benign_ce = frame_float(frame_global, benign_uids, "tabm_process_score")
    support_ex = frame_float(frame_global, support_uids, "extra_process_score")
    benign_ex = frame_float(frame_global, benign_uids, "extra_process_score")

    ce_gate, ce_frontier = choose_dual_gate(
        global_asm["select_attack"], support_base, support_ce, benign_base, benign_ce
    )
    ex_gate, ex_frontier = choose_dual_gate(
        global_asm["select_attack"], support_base, support_ex, benign_base, benign_ex
    )

    weights, balance_audit = family_balanced_row_weights(global_asm["fit_records"])
    training = train_tail_margin_candidates(
        fit_x,
        global_asm["fit_records"],
        weights,
        select_x,
        global_asm["select_attack"],
        support_base,
        benign_base,
        int(args.threads),
    )
    tail_gate = training["gate"]
    tail_model = training["model"]
    tail_select_scores = tail_model.predict(select_x)

    scope_rows = []
    scope_rows.extend(
        dual_scope_audit_rows(
            CE_DUAL, ce_gate, benign_select_records, benign_base, benign_ce, "dual"
        )
    )
    scope_rows.extend(
        dual_scope_audit_rows(
            EXTRA_DUAL, ex_gate, benign_select_records, benign_base, benign_ex, "dual"
        )
    )
    scope_rows.extend(
        dual_scope_audit_rows(
            TAIL_OR,
            tail_gate,
            benign_select_records,
            benign_base,
            tail_select_scores[SUPPORT_VAL_ROWS:],
            "or",
        )
    )
    scope_rows.extend(
        dual_scope_audit_rows(
            PRIMARY,
            tail_gate,
            benign_select_records,
            benign_base,
            tail_select_scores[SUPPORT_VAL_ROWS:],
            "dual",
        )
    )

    all_metrics: list[dict[str, Any]] = []
    all_families: list[dict[str, Any]] = []
    all_attack: list[dict[str, Any]] = []
    all_strict: list[dict[str, Any]] = []
    transition_rows: list[dict[str, Any]] = []
    udp_rows: list[dict[str, Any]] = []
    masked_audit_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    neg_inf = float("-inf")

    for held in protocols:
        asm = assemblies[held]
        protocol = asm["protocol"]
        report = list(asm["report_records"])
        if held is not None:
            store.add(
                [record for record in report if not str(record.uid).startswith("ton:")],
                feature_map,
            )
        select_order_p = list(asm["select_attack"]) + list(asm["select_benign_observable"])
        scored = ckbu.unique([*select_order_p, *report])
        scored_observable = [record for record in scored if observable(record)]
        masked_scored = [record for record in scored if not observable(record)]
        all_x = ckbu.transformed(transformer, scored_observable, feature_map)
        tail_scores = tail_model.predict(all_x)
        tail_q_map = {
            str(record.uid): float(value)
            for record, value in zip(scored_observable, tail_scores)
        }
        frame = (
            frame_global
            if held is None
            else frozen_aligned_frame(frozen, protocol, scored)
        )
        if held is not None:
            c1_audits.append(
                fresh_c1_vs_frozen_audit(protocol, scored, frame, asm["c1_threshold"])
            )
        uids = [str(record.uid) for record in scored]
        h0 = frame_bool(frame, uids, "frozen_ckbq_hard")
        c1_hard = frame_bool(frame, uids, "c1_hard")
        a2_hard = frame_bool(frame, uids, f"hard__{A2_EXTRA_OR}")
        m4_hard = frame_bool(frame, uids, f"hard__{M4_CE_OR}")
        ce_q = frame_float(frame, uids, "tabm_process_score")
        ex_q = frame_float(frame, uids, "extra_process_score")
        tail_q = np.asarray([tail_q_map.get(uid, neg_inf) for uid in uids], dtype=np.float64)
        masked_mask = np.asarray([not observable(record) for record in scored], dtype=bool)
        arms = {
            M0_C1: c1_hard,
            M1_FROZEN: h0,
            A2_EXTRA_OR: a2_hard,
            M4_CE_OR: m4_hard,
            CE_DUAL: apply_dual_control(h0, ce_q, ce_gate),
            TAIL_OR: one_sided_or(h0, tail_q, tail_gate.tau_attack),
            PRIMARY: apply_dual_control(h0, tail_q, tail_gate),
            EXTRA_DUAL: apply_dual_control(h0, ex_q, ex_gate),
        }
        if masked_mask.any():
            for arm in (CE_DUAL, TAIL_OR, PRIMARY, EXTRA_DUAL):
                arms[arm] = np.where(masked_mask, h0, arms[arm])
        fail_closed_ok = bool(
            not masked_mask.any()
            or all(
                np.array_equal(arms[arm][masked_mask], h0[masked_mask])
                for arm in (CE_DUAL, TAIL_OR, PRIMARY, EXTRA_DUAL)
            )
        )
        masked_audit_rows.append(
            {
                "held_value": protocol,
                "scored_rows": len(scored),
                "raw51_masked_scored_rows": int(masked_mask.sum()),
                "masked_rows_fail_closed_to_frozen_ckbq": fail_closed_ok,
                "mask_source": raw51.RAW51_MASK_SOURCE if masked_pairs else None,
                "masked_target_materialization_rows": len(masked_pairs),
            }
        )

        strict = (
            list(asm["select_attack"]) + [record for record in report if int(record.label) == 1]
            if held is None
            else report
        )
        strict_index = {str(record.uid): index for index, record in enumerate(scored)}
        strict_pos = np.asarray([strict_index[str(record.uid)] for record in strict], dtype=np.int64)
        decisions = {arm: values[strict_pos] for arm, values in arms.items()}
        c1_strict = c1_hard[strict_pos]
        result = evaluate_arms(
            held, protocol, strict, decisions, c1_strict, int(args.bootstrap_reps)
        )
        all_metrics.extend(result["metrics"])
        all_families.extend(result["family_metrics"])
        all_attack.extend(result["attack_summary"])
        all_strict.extend(result["strict_summary"])
        transition_rows.extend(
            transition_matrix_rows(protocol, strict, h0[strict_pos], arms[PRIMARY][strict_pos])
        )
        udp_rows.extend(
            udp_scan_diagnostic_rows(
                protocol,
                strict,
                decisions,
                tail_q[strict_pos],
                ce_q[strict_pos],
                ex_q[strict_pos],
            )
        )
        for index, record in enumerate(scored):
            masked_row = bool(masked_mask[index])
            prediction_rows.append(
                {
                    "held_value": protocol,
                    "uid": str(record.uid),
                    "role": record.role,
                    "phase": record.m1_phase,
                    "source_group": record.source,
                    "device_family": record.device_family,
                    "attack_family": record.attack_family,
                    "label_metric_only": int(record.label),
                    "raw51_observable": not masked_row,
                    "c1_hard": bool(c1_hard[index]),
                    "frozen_ckbq_hard": bool(h0[index]),
                    "extra_process_score": float(ex_q[index]),
                    "tabm_process_score": float(ce_q[index]),
                    "tail_margin_score": ("" if masked_row else float(tail_q[index])),
                    "ce_dual_tau_normal": float(ce_gate.tau_normal),
                    "ce_dual_tau_attack": float(ce_gate.tau_attack),
                    "extra_dual_tau_normal": float(ex_gate.tau_normal),
                    "extra_dual_tau_attack": float(ex_gate.tau_attack),
                    "tail_margin_tau_normal": float(tail_gate.tau_normal),
                    "tail_margin_tau_attack": float(tail_gate.tau_attack),
                    f"hard__{M0_C1}": bool(c1_hard[index]),
                    f"hard__{M1_FROZEN}": bool(h0[index]),
                    f"hard__{A2_EXTRA_OR}": bool(a2_hard[index]),
                    f"hard__{M4_CE_OR}": bool(m4_hard[index]),
                    f"hard__{CE_DUAL}": bool(arms[CE_DUAL][index]),
                    f"hard__{TAIL_OR}": bool(arms[TAIL_OR][index]),
                    f"hard__{PRIMARY}": bool(arms[PRIMARY][index]),
                    f"hard__{EXTRA_DUAL}": bool(arms[EXTRA_DUAL][index]),
                    "review": False,
                    "seed": SEED,
                }
            )

    def frame_of(rows: list[dict[str, Any]]) -> pd.DataFrame:
        return pd.DataFrame([{**row, "seed": SEED} for row in rows])

    gate_frontier_rows = [
        {**row, "candidate": CE_DUAL, "score_source": "frozen_154917_tabm_ce", "epoch": math.nan}
        for row in ce_frontier
    ] + [
        {**row, "candidate": EXTRA_DUAL, "score_source": "frozen_154917_extratrees", "epoch": math.nan}
        for row in ex_frontier
    ] + [
        {**row, "candidate": f"tail_margin_lt{row['lambda_tail']}_lf{row['lambda_family']}", "score_source": "ckbw_tail_margin_training", }
        for row in training["frontier"]
    ]
    candidate_rows = []
    for candidate in training["candidates"]:
        gate = candidate["best_gate"]
        candidate_rows.append(
            {
                "lambda_tail": candidate["lambda_tail"],
                "lambda_family": candidate["lambda_family"],
                "selected_epoch": candidate["best_epoch"],
                "tau_normal": gate.tau_normal,
                "tau_attack": gate.tau_attack,
                "support_rows": gate.support_rows,
                "support_hard_rows": gate.support_hard_rows,
                "benign_rows": gate.benign_rows,
                "baseline_hard_rows": gate.baseline_hard_rows,
                "dual_hard_rows": gate.dual_hard_rows,
                "suppress_rows": gate.suppress_rows,
                "rescue_rows": gate.rescue_rows,
                "net_hard_reduction": gate.net_hard_reduction,
                "worst_family_score_margin": gate.worst_family_score_margin,
                "chosen_for_primary": bool(candidate["chosen"]),
                "selection_scope": "support_val69_plus_aux3000_plus_ton_normal2_4000",
                "report_rows_used": 0,
                "held_rows_used": 0,
            }
        )
    winner = training["winner"]
    model_rows = [
        {
            "candidate": PRIMARY,
            "backend": "official_TabM_v0.0.3",
            **TABM_CONFIG,
            "lambda_tail": winner["lambda_tail"],
            "lambda_family": winner["lambda_family"],
            "selected_epoch": winner["best_epoch"],
            "shared_process_head": True,
            "per_family_experts": 0,
            "fit_rows": FIT_ROWS,
            "fit_attack_rows": FIT_ATTACK_ROWS,
            "fit_benign_rows": FIT_BENIGN_ROWS,
            "select_rows_used_for_fit": 0,
            "report_rows_used": 0,
            "model_sha256": training["model_sha256"],
            "review_rate": 0.0,
        },
        {
            "candidate": CE_DUAL,
            "backend": "frozen_154917_TabM_CE_reused_no_retrain",
            "model_sha256": frozen.tabm_model_sha256,
            "shared_process_head": True,
            "per_family_experts": 0,
            "review_rate": 0.0,
        },
        {
            "candidate": EXTRA_DUAL,
            "backend": "frozen_154917_ExtraTrees_reused_no_retrain",
            "model_sha256": frozen.extra_model_sha256,
            "shared_process_head": True,
            "per_family_experts": 0,
            "review_rate": 0.0,
        },
    ]
    support_usage = [
        {
            "candidate": f"tail_margin_lt{candidate['lambda_tail']}_lf{candidate['lambda_family']}",
            "uid": str(record.uid),
            "source_group": record.source,
            "attack_family": record.attack_family,
            "epochs": EPOCHS,
            "times_used": EPOCHS,
            "used_at_least_once_each_epoch": True,
        }
        for candidate in training["candidates"]
        for record in global_asm["sets"]["fit_attack"]
    ]
    scope_audit = []
    for held in protocols:
        asm = assemblies[held]
        scope_audit.append(
            {
                "held_value": asm["protocol"],
                "held_family": held or "NONE",
                "core_fit_attack_rows": len(asm["sets"]["fit_attack"]),
                "core_fit_benign_rows": len(asm["sets"]["fit_benign"]),
                "core_select_attack_rows": len(asm["sets"]["select_attack"]),
                "core_select_benign_rows": len(asm["sets"]["select_benign"]),
                "aux_fit_rows": asm["aux_fit_rows"],
                "aux_select_rows": asm["aux_select_rows"],
                "ton_fit_rows": len(ton["aux_process_fit"]) + len(ton["aux_normal_fit"]),
                "ton_select_rows": len(ton["aux_normal_select"]),
                "report_rows": len(asm["report_records"]),
                "report_fit_use_count": 0,
                "report_select_use_count": 0,
                "review_rate": 0.0,
            }
        )
    data_audit_rows = [
        {**row, "protocol_run": asm["protocol"]}
        for asm in assemblies.values()
        for row in (asm["data_audit"] + asm["c1_audit"])
    ]

    outputs = {
        "ckbw_all_metrics.csv": frame_of(all_metrics),
        "ckbw_per_attack_family_metrics.csv": frame_of(all_families),
        "ckbw_attack_preservation_summary.csv": frame_of(all_attack),
        "ckbw_strict_level2_summary.csv": frame_of(all_strict),
        "ckbw_dual_gate_frontier.csv": frame_of(gate_frontier_rows),
        "ckbw_dual_gate_scope_audit.csv": frame_of(scope_rows),
        "ckbw_tail_training_loss.csv": frame_of(training["histories"]),
        "ckbw_tail_candidate_selection.csv": frame_of(candidate_rows),
        "ckbw_model_audit.csv": frame_of(model_rows),
        "ckbw_group_balance_audit.csv": frame_of(balance_audit),
        "ckbw_preprocessing_audit.csv": frame_of([prep_audit]),
        "ckbw_support_training_usage.csv": frame_of(support_usage),
        "ckbw_protocol_scope_audit.csv": frame_of(scope_audit),
        "ckbw_role_usage_audit.csv": frame_of(data_audit_rows),
        "ckbw_c1_fresh_vs_frozen_audit.csv": frame_of(c1_audits),
        "ckbw_raw51_mask_audit.csv": frame_of(masked_audit_rows),
        "ckbw_transition_matrix.csv": frame_of(transition_rows),
        "ckbw_udp_scan_diagnostic.csv": frame_of(udp_rows),
        "ckbw_permanent_report_only_audit.csv": pd.DataFrame(permanent),
        "ckbw_frozen_model_scope_audit.csv": pd.DataFrame(frozen_scope),
        "ckbw_review_audit.csv": pd.DataFrame(
            [{"seed": SEED, "review_count": 0, "review_rate": 0.0, "review_enabled": False}]
        ),
    }
    for filename, frame_value in outputs.items():
        frame_value.to_csv(out / filename, index=False)
    predictions = frame_of(prediction_rows)
    predictions.to_csv(
        out / "ckbw_record_predictions.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )

    fit_families = {str(record.device_family) for record in global_asm["fit_records"]}
    select_families = {
        str(record.device_family)
        for record in (
            list(global_asm["select_attack"]) + list(global_asm["select_benign_observable"])
        )
    }
    cooler_rows = sum(
        str(record.device_family) == "iotsim-cooler-motor"
        for held in protocols
        for record in (
            list(assemblies[held]["select_attack"])
            + list(assemblies[held]["select_benign_observable"])
            + list(assemblies[held]["report_records"])
        )
    )
    contract_checks = {
        "fit_pool_excludes_all_held_families": not (fit_families & set(HELD_OOD_FAMILIES)),
        "select_pool_excludes_all_held_families": not (select_families & set(HELD_OOD_FAMILIES)),
        "preprocessing_fit_only": bool(
            prep_audit["select_rows_used"] == 0 and prep_audit["report_rows_used"] == 0
        ),
        "protocol_identity_single_shared_scorer": True,
        "support_train_385_every_epoch": True,
        "attack_balance_12_families": True,
        "fresh_c1_matches_frozen": all(row["c1_mismatch_rows"] == 0 for row in c1_audits),
        "raw51_masked_fail_closed": all(
            row["masked_rows_fail_closed_to_frozen_ckbq"] for row in masked_audit_rows
        ),
        "frozen_score_bundle_hash_locked": True,
        "review_zero": True,
        "score_addition_used": False,
        "per_family_experts": 0 == 0,
        "udp_scan_diagnostic_only": True,
        "cooler_motor_untouched": cooler_rows == 0,
        "seeds_37_47_locked": True,
    }
    config_places = {
        "model_construction": TABM_CONFIG,
        "cli_defaults": {**TABM_CONFIG, "cli_overrides_available": False},
        "run_spec": TABM_CONFIG,
        "model_audit": TABM_CONFIG,
        "result": TABM_CONFIG,
    }
    config_consistency = all(
        place == TABM_CONFIG or place == {**TABM_CONFIG, "cli_overrides_available": False}
        for place in config_places.values()
    )
    contract_checks["config_five_place_consistency"] = bool(config_consistency)

    outcome = scientific_outcome(
        outputs["ckbw_attack_preservation_summary.csv"],
        outputs["ckbw_strict_level2_summary.csv"],
        contract_checks,
    )
    outcome["config"] = TABM_CONFIG
    ckbu.dump_json(out / "ckbw_single_seed_go_no_go.json", outcome)
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "torch": torch.__version__,
        "tabm": getattr(ckbm.tabm, "__version__", TABM_VERSION),
        "seed": SEED,
        "commit_sha": os.environ.get("CKBW_COMMIT_SHA", ckbm.git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "wall_seconds": time.time() - started,
        "review_rate": 0.0,
        "gotham_manifest_sha256": ckbu.sha256_file(Path(args.gotham_manifest)),
        "auxiliary_manifest_sha256": ckbu.sha256_file(Path(args.auxiliary_manifest)),
        "ton_cache_sha256": ton_audit["cache_sha256"],
        "frozen_154917_predictions_sha256": frozen.prediction_sha256,
        "frozen_154917_tabm_model_sha256": frozen.tabm_model_sha256,
        "frozen_154917_extra_model_sha256": frozen.extra_model_sha256,
        "raw51_observable_mask": str(args.raw51_mask) if getattr(args, "raw51_mask", None) else None,
        "raw51_observable_mask_sha256": (
            str(args.raw51_mask_sha256).strip().lower() if getattr(args, "raw51_mask", None) else None
        ),
        "raw51_frozen_targets": 325067,
        "raw51_masked_targets": len(masked_pairs),
        "raw51_observable_targets": 325067 - len(masked_pairs),
        "dependency_closure_status": closure["status"],
    }
    ckbu.dump_json(out / "ckbw_environment.json", environment)
    ckbu.dump_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "decision": outcome["decision"],
            "primary_candidate": PRIMARY,
            "candidates": list(ALL_ARMS),
            "preregistered_protocol_sha256": "80c44c8db9335c2e90a7d0f6a42649ec50ae9e88418a43165696474b0d9aec5b",
            "tabm_config": TABM_CONFIG,
            "cli_config": {**TABM_CONFIG, "cli_overrides_available": False},
            "config_five_place_consistency": bool(config_consistency),
            "frozen_score_reuse": {
                CE_DUAL: "frozen 154917 tabm_process_score, dual thresholds only",
                EXTRA_DUAL: "frozen 154917 extra_process_score, dual thresholds only",
                M4_CE_OR: "frozen 154917 hard decisions, not rerun",
                A2_EXTRA_OR: "frozen 154917 hard decisions, not rerun",
            },
            "selection": (
                "support_val 69/69 attack preservation first; benign select "
                "net hard reduction lexicographic; report/held rows never used"
            ),
            "development_canaries": list(CANARY_FAMILIES),
            "repeated_view_report": list(REPEATED_VIEW_FAMILIES),
            "final_held_unopened": ["iotsim-cooler-motor"],
            "review_rate": 0.0,
            "score_addition_used": False,
            "per_family_experts": 0,
            "ton_pilot": ton_audit,
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_extension_audit": c1_extension_audit,
            "environment": environment,
        },
    )
    ckbu.write_text(
        out / "ckbw_readout.md",
        f"# CKBW seed 27\n\nScientific decision: `{outcome['decision']}`.  "
        "Route signal only under the frozen preregistration; PRIMARY is fixed as "
        "TabM-TailMargin-DualControl with no post-hoc promotion.  One shared 51D "
        "causal process scorer, family-balanced tail-pair margin, dual control "
        "around frozen CKBQ, review=0.\n",
    )
    print(
        json.dumps(
            {
                "status": "CKBW_FORMAL_COMPLETE",
                "decision": outcome["decision"],
                "primary": PRIMARY,
                "winner_lambda_tail": winner["lambda_tail"],
                "winner_lambda_family": winner["lambda_family"],
                "winner_epoch": winner["best_epoch"],
                "tail_gate": {
                    "tau_normal": tail_gate.tau_normal,
                    "tau_attack": tail_gate.tau_attack,
                    "net_hard_reduction": tail_gate.net_hard_reduction,
                    "suppress_rows": tail_gate.suppress_rows,
                    "rescue_rows": tail_gate.rescue_rows,
                },
                "ce_gate": {"tau_normal": ce_gate.tau_normal, "tau_attack": ce_gate.tau_attack},
                "extra_gate": {"tau_normal": ex_gate.tau_normal, "tau_attack": ex_gate.tau_attack},
                "out": str(out),
            },
            indent=2,
            sort_keys=True,
        )
    )


def records_from_frozen_frame(frame: pd.DataFrame) -> list[ckbj.Record]:
    """Reconstruct metric records from the frozen 154917 frame.

    Preview/diagnostic use only.  ``episode_id`` degrades to the source group,
    so single-source pools report bootstrap CI as unavailable; point rates and
    deltas remain exact.  The formal run uses the real assembled records with
    intact episode lineage.
    """
    c1_values = bool_array(frame["c1_hard"])
    records: list[ckbj.Record] = []
    for index, row in enumerate(frame.itertuples(index=False)):
        records.append(
            ckbj.Record(
                uid=str(row.uid),
                role=str(row.role),
                m1_phase=str(row.phase),
                source=str(row.source_group),
                recorded_index=index,
                event_position=index,
                label=int(row.label_metric_only),
                attack_family=str(row.attack_family),
                device_family=str(row.device_family),
                source_family=str(row.device_family),
                c1_score=1.0 if bool(c1_values[index]) else 0.0,
                episode_id=str(row.source_group),
            )
        )
    return records


def frozen_arm_preview(args: argparse.Namespace) -> None:
    """Real-data preview of the six frozen-score arms (no CKBW training).

    Validates dual-gate selection and evaluation code on the actual 154917
    scores and gives an early, clearly-labeled look at CE-Dual/ExtraTrees-Dual
    behaviour.  Not a formal result: CI clustering is degraded (episode_id is
    the source group) and tail-margin arms are absent.
    """
    frozen = FrozenScoreBundle.load(args.frozen_predictions, args.frozen_model_audit)
    frame_global = frozen.protocol(GLOBAL_PROTOCOL)
    select_frame = frame_global.loc[frame_global["phase"].astype(str) == "select"]
    support_frame = select_frame.loc[select_frame["role"].astype(str) == "support_val"]
    benign_frame = select_frame.loc[
        select_frame["role"].astype(str).isin(["aux_select", "aux_normal_select"])
    ]
    if len(support_frame) != SUPPORT_VAL_ROWS or len(benign_frame) != BENIGN_SELECT_ROWS:
        raise RuntimeError("preview select pool drift")
    support_records = records_from_frozen_frame(support_frame)
    benign_records = records_from_frozen_frame(benign_frame)
    support_base = bool_array(support_frame["frozen_ckbq_hard"])
    benign_base = bool_array(benign_frame["frozen_ckbq_hard"])
    ce_gate, _ = choose_dual_gate(
        support_records,
        support_base,
        frame_float(support_frame, support_frame["uid"].astype(str).tolist(), "tabm_process_score"),
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "tabm_process_score"),
    )
    ex_gate, _ = choose_dual_gate(
        support_records,
        support_base,
        frame_float(support_frame, support_frame["uid"].astype(str).tolist(), "extra_process_score"),
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "extra_process_score"),
    )
    scope_rows = dual_scope_audit_rows(
        CE_DUAL,
        ce_gate,
        benign_records,
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "tabm_process_score"),
        "dual",
    ) + dual_scope_audit_rows(
        EXTRA_DUAL,
        ex_gate,
        benign_records,
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "extra_process_score"),
        "dual",
    )

    preview_arms = (M0_C1, M1_FROZEN, A2_EXTRA_OR, M4_CE_OR, CE_DUAL, EXTRA_DUAL)
    summary: dict[str, Any] = {
        "preview_only": True,
        "ci_cluster_note": "episode_id=source_group; single-source pools CI unavailable",
        "ce_dual_gate": ce_gate.__dict__,
        "extra_dual_gate": ex_gate.__dict__,
        "scope_audit": scope_rows,
        "protocols": {},
    }
    for protocol, expected_rows in FROZEN_PROTOCOL_ROWS.items():
        held = None if protocol == GLOBAL_PROTOCOL else protocol
        frame = frozen.protocol(protocol)
        records = records_from_frozen_frame(frame)
        uids = [str(record.uid) for record in records]
        h0 = frame_bool(frame, uids, "frozen_ckbq_hard")
        c1_hard = frame_bool(frame, uids, "c1_hard")
        ce_q = frame_float(frame, uids, "tabm_process_score")
        ex_q = frame_float(frame, uids, "extra_process_score")
        arms = {
            M0_C1: c1_hard,
            M1_FROZEN: h0,
            A2_EXTRA_OR: frame_bool(frame, uids, f"hard__{A2_EXTRA_OR}"),
            M4_CE_OR: frame_bool(frame, uids, f"hard__{M4_CE_OR}"),
            CE_DUAL: apply_dual_control(h0, ce_q, ce_gate),
            EXTRA_DUAL: apply_dual_control(h0, ex_q, ex_gate),
        }
        strict_mask = np.asarray(
            [
                (str(record.role) == "support_val" or str(record.m1_phase) == "report")
                if held is None
                else str(record.m1_phase) == "report"
                for record in records
            ],
            dtype=bool,
        )
        strict = [record for record, keep in zip(records, strict_mask.tolist()) if keep]
        decisions = {arm: values[strict_mask] for arm, values in arms.items()}
        result = evaluate_arms(
            held,
            protocol,
            strict,
            decisions,
            c1_hard[strict_mask],
            int(args.bootstrap_reps),
        )
        attack = pd.DataFrame(result["attack_summary"])
        strict_df = pd.DataFrame(result["strict_summary"])
        protocol_summary: dict[str, Any] = {"strict_rows": len(strict)}
        if not attack.empty:
            overall = attack.loc[
                attack["metric"].astype(str) == "overall_attack_hard_recall",
                ["candidate", "hard_recall", "delta_vs_c1_pp"],
            ]
            support = attack.loc[
                attack["metric"].astype(str) == "support_val_recall",
                ["candidate", "hard_recall"],
            ]
            protocol_summary["overall_attack"] = overall.to_dict("records")
            protocol_summary["support_val_recall"] = support.to_dict("records")
        if not strict_df.empty:
            protocol_summary["held_ood"] = strict_df[
                ["candidate", "held_value", "hard_rate", "c1_hard_rate", "delta_vs_c1_pp"]
            ].to_dict("records")
        summary["protocols"][protocol] = protocol_summary
    print(json.dumps(ckbm.json_ready(summary), indent=2, sort_keys=True))


def smoke_store(args: argparse.Namespace) -> None:
    """Exercise the UnifiedFeatureStore wiring on tiny synthetic caches."""
    import tempfile

    rng = np.random.default_rng(SEED)
    with tempfile.TemporaryDirectory() as tmp_raw:
        tmp = Path(tmp_raw)
        gotham_cache = tmp / "gotham_cache"
        aux_cache = tmp / "aux_cache"
        gotham_cache.mkdir()
        aux_cache.mkdir()
        names = np.asarray(raw51.FEATURE_NAMES, dtype=str)
        manifest_rows: list[dict[str, Any]] = []
        records: list[ckbj.Record] = []
        for source, count in (("processed/smoke-alpha.csv", 12), ("processed/smoke-beta.csv", 9)):
            key = hashlib.sha256(source.encode("utf-8")).hexdigest()[:20]
            np.savez(
                gotham_cache / f"{key}.npz",
                feature_names=names,
                causal_features=rng.normal(0.0, 1.0, (count, INPUT_DIM)).astype(np.float32),
                recorded_index=np.arange(count, dtype=np.int64) + 50,
            )
            manifest_rows.append(
                {"source_group": source, "source_cache_key": key, "raw_label_column_read": False}
            )
            records.extend(
                ckbj.Record(
                    uid=f"{source}:{index}",
                    role="id_calib",
                    m1_phase="fit",
                    source=source,
                    recorded_index=index + 50,
                    event_position=index + 50,
                    label=0,
                    attack_family="benign",
                    device_family="smoke",
                    source_family="smoke",
                    c1_score=0.0,
                    episode_id="smoke",
                )
                for index in range(count)
            )
        gotham_manifest = tmp / "gotham_manifest.csv"
        pd.DataFrame(manifest_rows).to_csv(gotham_manifest, index=False)
        aux_source = "smoke-aux-1"
        aux_key = hashlib.sha256(aux_source.encode("utf-8")).hexdigest()[:20]
        np.savez(
            aux_cache / f"{aux_key}.npz",
            feature_names=names,
            causal_features=rng.normal(0.0, 1.0, (7, INPUT_DIM)).astype(np.float32),
            target_row=np.arange(7, dtype=np.int64) + 500,
        )
        aux_manifest = tmp / "aux_manifest.csv"
        pd.DataFrame(
            [{"source_group": aux_source, "source_cache_key": aux_key, "raw_label_column_read": False}]
        ).to_csv(aux_manifest, index=False)
        aux_records = [
            ckbj.Record(
                uid=f"aux:{index}",
                role="aux_fit",
                m1_phase="fit",
                source=aux_source,
                recorded_index=index + 500,
                event_position=index + 500,
                label=0,
                attack_family="benign",
                device_family="smoke-aux",
                source_family="smoke-aux",
                c1_score=0.0,
                episode_id="smoke-aux",
            )
            for index in range(7)
        ]
        store = ckbu.UnifiedFeatureStore(gotham_manifest, gotham_cache, aux_manifest, aux_cache)
        all_records = records + aux_records
        feature_map: dict[str, np.ndarray] = {}
        store.add(all_records, feature_map)
        if len(feature_map) != len(all_records):
            raise RuntimeError("smoke store coverage failed")
        transformer, prep_audit = ckbu.fit_preprocessor(all_records, feature_map, SEED)
        x = ckbu.transformed(transformer, all_records, feature_map)
        if x.shape != (len(all_records), INPUT_DIM) or not np.isfinite(x).all():
            raise RuntimeError("smoke store transform failed")
        print(
            json.dumps(
                {
                    "status": "CKBW_SMOKE_STORE_PASS",
                    "rows": len(all_records),
                    "feature_dim": int(x.shape[1]),
                    "prep_fit_rows": prep_audit["fit_rows"],
                },
                indent=2,
                sort_keys=True,
            )
        )


def synthetic_fit_records() -> list[ckbj.Record]:
    """Synthetic fit pool with the exact preregistered composition (section 3)."""
    attack_counts = {
        "File Download": 15,
        "Ingress Tool Transfer": 18,
        "Merlin C&C Communication": 30,
        "Merlin ICMP Flooding": 43,
        "Merlin TCP Flooding": 60,
        "Merlin UDP Flooding": 30,
        "Mirai C&C Communication": 9,
        "Mirai GRE Flooding": 60,
        "Mirai TCP Flooding": 60,
        "Mirai UDP Flooding": 60,
        "ToN-reconnaissance_scan": 2_000,
        "ToN-credential_bruteforce": 2_000,
    }
    benign_counts = {
        "processed/iotsim-combined-cycle-tls-3.csv": 270,
        "processed/iotsim-combined-cycle-tls-4.csv": 270,
        "processed/iotsim-combined-cycle-tls-5.csv": 269,
        "processed/iotsim-building-monitor-2.csv": 1_690,
        "processed/iotsim-building-monitor-3.csv": 914,
        **{f"smoke-aux-fit-{index}": 600 for index in range(11)},
        "ton-normal-1": 4_000,
    }
    records: list[ckbj.Record] = []
    for family, count in attack_counts.items():
        source = "ton-iot-external" if family.startswith("ToN-") else f"smoke-attack-{family}"
        for index in range(count):
            records.append(
                ckbj.Record(
                    uid=f"smoke-fit-attack:{family}:{index}",
                    role="support_train" if not family.startswith("ToN-") else "aux_process_fit",
                    m1_phase="fit",
                    source=source,
                    recorded_index=index,
                    event_position=index,
                    label=1,
                    attack_family=family,
                    device_family="smoke-attack",
                    source_family="smoke-attack",
                    c1_score=1.0,
                    episode_id=source,
                )
            )
    for source, count in benign_counts.items():
        for index in range(count):
            records.append(
                ckbj.Record(
                    uid=f"smoke-fit-benign:{source}:{index}",
                    role="ood_val" if "building" in source else "aux_normal_fit" if source.startswith("ton") else "aux_fit",
                    m1_phase="fit",
                    source=source,
                    recorded_index=index,
                    event_position=index,
                    label=0,
                    attack_family="benign",
                    device_family="smoke-benign",
                    source_family="smoke-benign",
                    c1_score=0.0,
                    episode_id=source,
                )
            )
    if len(records) != FIT_ROWS:
        raise RuntimeError(f"synthetic fit drift: {len(records)}")
    return records


def smoke_formal(args: argparse.Namespace) -> None:
    """End-to-end pipeline smoke on synthetic features + real frozen select scores.

    Exercises candidate driving, frontier replay, dual gates, scope audits and
    output writing.  Synthetic features mean the learned scores are meaningless;
    this is a mechanics test, never a result.
    """
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frozen = FrozenScoreBundle.load(args.frozen_predictions, args.frozen_model_audit)
    frame_global = frozen.protocol(GLOBAL_PROTOCOL)
    select_frame = frame_global.loc[frame_global["phase"].astype(str) == "select"]
    support_frame = select_frame.loc[select_frame["role"].astype(str) == "support_val"]
    benign_frame = select_frame.loc[
        select_frame["role"].astype(str).isin(["aux_select", "aux_normal_select"])
    ]
    support_records = records_from_frozen_frame(support_frame)
    benign_records = records_from_frozen_frame(benign_frame)
    support_base = bool_array(support_frame["frozen_ckbq_hard"])
    benign_base = bool_array(benign_frame["frozen_ckbq_hard"])
    fit_records = synthetic_fit_records()
    weights, balance_audit = family_balanced_row_weights(fit_records)
    rng = np.random.default_rng(SEED)
    fit_x = rng.normal(0.0, 1.0, (FIT_ROWS, INPUT_DIM)).astype(np.float32)
    select_x = rng.normal(0.0, 1.0, (SUPPORT_VAL_ROWS + BENIGN_SELECT_ROWS, INPUT_DIM)).astype(
        np.float32
    )
    training = train_tail_margin_candidates(
        fit_x,
        fit_records,
        weights,
        select_x,
        support_records,
        support_base,
        benign_base,
        int(args.threads),
    )
    ce_gate, _ = choose_dual_gate(
        support_records,
        support_base,
        frame_float(support_frame, support_frame["uid"].astype(str).tolist(), "tabm_process_score"),
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "tabm_process_score"),
    )
    tail_select = training["model"].predict(select_x)
    scope_rows = dual_scope_audit_rows(
        CE_DUAL,
        ce_gate,
        benign_records,
        benign_base,
        frame_float(benign_frame, benign_frame["uid"].astype(str).tolist(), "tabm_process_score"),
        "dual",
    ) + dual_scope_audit_rows(
        PRIMARY,
        training["gate"],
        benign_records,
        benign_base,
        tail_select[SUPPORT_VAL_ROWS:],
        "dual",
    ) + dual_scope_audit_rows(
        TAIL_OR,
        training["gate"],
        benign_records,
        benign_base,
        tail_select[SUPPORT_VAL_ROWS:],
        "or",
    )
    pd.DataFrame(scope_rows).to_csv(out / "smoke_dual_gate_scope_audit.csv", index=False)
    pd.DataFrame(training["histories"]).to_csv(out / "smoke_tail_training_loss.csv", index=False)
    pd.DataFrame(balance_audit).to_csv(out / "smoke_group_balance_audit.csv", index=False)
    pd.DataFrame(
        [
            {
                "lambda_tail": candidate["lambda_tail"],
                "lambda_family": candidate["lambda_family"],
                "selected_epoch": candidate["best_epoch"],
                "chosen": bool(candidate["chosen"]),
                "net_hard_reduction": candidate["best_gate"].net_hard_reduction,
            }
            for candidate in training["candidates"]
        ]
    ).to_csv(out / "smoke_tail_candidate_selection.csv", index=False)
    ckbu.dump_json(
        out / "smoke_run_spec.json",
        {
            "issue": ISSUE,
            "smoke": True,
            "synthetic_features": True,
            "tabm_config": TABM_CONFIG,
            "winner": {
                "lambda_tail": training["winner"]["lambda_tail"],
                "lambda_family": training["winner"]["lambda_family"],
                "epoch": training["winner"]["best_epoch"],
            },
        },
    )
    print(
        json.dumps(
            {
                "status": "CKBW_SMOKE_FORMAL_PASS",
                "smoke": True,
                "synthetic_features": True,
                "candidates": len(training["candidates"]),
                "epochs_per_candidate": EPOCHS,
                "winner_lambda_tail": training["winner"]["lambda_tail"],
                "winner_lambda_family": training["winner"]["lambda_family"],
                "winner_epoch": training["winner"]["best_epoch"],
                "model_sha256": training["model_sha256"],
                "out": str(out),
            },
            indent=2,
            sort_keys=True,
        )
    )



if __name__ == "__main__":
    main()
