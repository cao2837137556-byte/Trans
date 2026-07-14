"""CKBM: mature TabM verifier with causal source-relative calibration.

The experiment keeps C1 as the high-recall candidate anchor.  It compares a
mature sklearn ExtraTrees verifier, official TabM v0.0.3, and a TabM verifier
that receives a source-relative view computed strictly before the current
event updates source-local state.

No report/held row fits a model, preprocessing transform, or threshold.  All
385 legal support_train rows are used once per epoch in the global protocol.
Report inference is label-free, source-local, fresh-reset, no-gradient and
past-only.  Review is fixed to zero.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import pickle
import platform
import subprocess
import sys
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.preprocessing import QuantileTransformer


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))
VENDOR_TABM = OOD / "vendor" / "tabm_v0_0_3"
if str(VENDOR_TABM) not in sys.path:
    sys.path.insert(0, str(VENDOR_TABM))

import tabm  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbl_frontend_observability_audit_v1 as ckbl  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402


ISSUE = "issue27ckbm_tabm_causal_source_calibration_v1_2026-07-14"
ROOT = cko.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
DEFAULT_T0 = ckbj.DEFAULT_T0
DEFAULT_REPORT_EXTENSION = ckbj.DEFAULT_REPORT_EXTENSION
DEFAULT_C1_PLAN = ckbj.DEFAULT_C1_PLAN
DEFAULT_C1_TARGETS = ckbj.DEFAULT_C1_TARGETS
DEFAULT_C1_CACHE = ckbj.DEFAULT_C1_CACHE
DEFAULT_C1_REPORT_EXTENSION = ckbj.DEFAULT_C1_REPORT_EXTENSION
EXPECTED_T0_MANIFEST_SHA256 = ckbj.EXPECTED_T0_MANIFEST_SHA256
UPSTREAM_TABM_COMMIT = "a507095893d784c5702059d737ddfbd1299c41dd"
UPSTREAM_TABM_SHA256_LF = "fc654af6a16bac53d893a8265c79d7af4ebddcb95ad0d600cc6b6bc6b7317ade"
PRIMARY = "M3-TabM-CSR"
SEED = 27


@dataclass(frozen=True)
class BackendSpec:
    name: str
    kind: str
    view: str
    primary: bool = False


BACKENDS = (
    BackendSpec("M1-ExtraTrees-Global", "extratrees", "global"),
    BackendSpec("M2-TabM-Global", "tabm", "global"),
    BackendSpec(PRIMARY, "tabm", "csr", True),
    BackendSpec("A1-ExtraTrees-CSR", "extratrees", "csr"),
)


def json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return json_ready(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float):
        return None if not math.isfinite(value) else value
    return value


def write_text_lf(path: Path, text: str) -> None:
    """Write deterministic LF text on every supported Python version.

    Path.write_text only gained its ``newline`` argument in newer Python
    releases than the frozen HPC runtime.  Path.open has supported newline
    control throughout the supported runtime range, so keep the compatibility
    boundary in one tested helper.
    """
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def dump_json(path: Path, payload: Any) -> None:
    write_text_lf(path, json.dumps(json_ready(payload), indent=2, sort_keys=True) + "\n")


def sha256_file_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def sha256_array(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = hashlib.sha256()
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(np.asarray(array.shape, dtype=np.int64).tobytes())
    digest.update(array.tobytes())
    return digest.hexdigest()


def git_head() -> str:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else "UNKNOWN"


def record_row(record: ckbj.Record) -> int:
    try:
        return int(record.uid.rsplit(":", 1)[1])
    except (IndexError, ValueError) as exc:
        raise RuntimeError(f"record UID lacks role row: {record.uid}") from exc


def unique_records(parts: Iterable[Iterable[ckbj.Record]]) -> list[ckbj.Record]:
    out: list[ckbj.Record] = []
    seen: set[str] = set()
    seen_events: dict[tuple[str, int], str] = {}
    for part in parts:
        for record in part:
            if record.uid in seen:
                raise RuntimeError(f"duplicate record UID across scopes: {record.uid}")
            event_key = (record.source, int(record.event_position))
            if event_key in seen_events:
                raise RuntimeError(
                    "duplicate source-local target event across fit/select/report scopes: "
                    f"{event_key} ({seen_events[event_key]} and {record.uid})"
                )
            seen.add(record.uid)
            seen_events[event_key] = record.uid
            out.append(record)
    return out


def frontend_feature_map(
    frontend: ckai.ExternalFlowFrontend,
    records: list[ckbj.Record],
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    """Read only C1's 207 causal features; metadata is never an input."""
    candidate = ckbj.c1_candidate()
    result: dict[str, np.ndarray] = {}
    audit: list[dict[str, Any]] = []
    by_role: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in records:
        by_role[record.role].append(record)
    for role, group in sorted(by_role.items()):
        indices = np.asarray([record_row(record) for record in group], dtype=np.int64)
        matrix = frontend.matrix(candidate, role, indices)
        if matrix.shape != (len(group), 207):
            raise RuntimeError(f"C1 feature shape drift for {role}: {matrix.shape}")
        if not np.isfinite(matrix).all():
            raise RuntimeError(f"nonfinite C1 input for {role}")
        for record, row in zip(group, matrix):
            result[record.uid] = np.asarray(row, dtype=np.float32)
        audit.append(
            {
                "role": role,
                "rows": len(group),
                "sources": len({record.source for record in group}),
                "feature_dim": int(matrix.shape[1]),
                "identity_feature_count": 0,
                "raw_label_column_read": False,
                "labels_used_to_build_features": False,
            }
        )
    if len(result) != len(records):
        raise RuntimeError("frontend feature map lost records")
    return result, audit


def stack_map(records: list[ckbj.Record], values: dict[str, np.ndarray]) -> np.ndarray:
    if not records:
        width = len(next(iter(values.values()))) if values else 0
        return np.zeros((0, width), dtype=np.float32)
    return np.vstack([values[record.uid] for record in records]).astype(np.float32)


def fit_preprocessor(
    fit_records: list[ckbj.Record],
    base: dict[str, np.ndarray],
    seed: int,
) -> tuple[QuantileTransformer, dict[str, Any]]:
    x = stack_map(fit_records, base)
    if x.shape[1] != 207 or len(x) < 10:
        raise RuntimeError(f"invalid fit-only preprocessing matrix: {x.shape}")
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1e-5, x.shape).astype(np.float32)
    n_quantiles = max(min(len(x) // 30, 1000), 10)
    transformer = QuantileTransformer(
        n_quantiles=n_quantiles,
        output_distribution="normal",
        subsample=1_000_000_000,
        random_state=int(seed),
    ).fit(x + noise)
    audit = {
        "fit_rows": len(fit_records),
        "fit_sources": len({record.source for record in fit_records}),
        "fit_attack_rows": sum(record.label == 1 for record in fit_records),
        "fit_benign_rows": sum(record.label == 0 for record in fit_records),
        "n_quantiles": int(n_quantiles),
        "output_distribution": "normal",
        "jitter_std": 1e-5,
        "fit_only": True,
        "select_rows_used": 0,
        "report_rows_used": 0,
        "quantiles_sha256": sha256_array(transformer.quantiles_),
        "references_sha256": sha256_array(transformer.references_),
    }
    return transformer, audit


def transformed_map(
    transformer: QuantileTransformer,
    records: list[ckbj.Record],
    base: dict[str, np.ndarray],
) -> dict[str, np.ndarray]:
    if not records:
        return {}
    values = transformer.transform(stack_map(records, base))
    values = np.nan_to_num(values, nan=0.0, posinf=8.0, neginf=-8.0)
    values = np.clip(values, -8.0, 8.0).astype(np.float32)
    return {record.uid: row for record, row in zip(records, values)}


def causal_source_relative_map(
    records: list[ckbj.Record],
    global_values: dict[str, np.ndarray],
    phase_scope: str,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Construct current/global + prior-only source-relative residuals.

    The function deliberately never reads ``record.label`` or family metadata.
    Each source state is local to this invocation, so callers must invoke it
    separately for fit, select and report.
    """
    result: dict[str, np.ndarray] = {}
    cold = 0
    updates = 0
    by_source: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in records:
        by_source[record.source].append(record)
    for source, group in sorted(by_source.items()):
        del source
        count = 0
        mean = np.zeros(207, dtype=np.float64)
        m2 = np.zeros(207, dtype=np.float64)
        ordered = sorted(group, key=lambda item: (item.event_position, item.recorded_index, item.uid))
        for record in ordered:
            current = np.asarray(global_values[record.uid], dtype=np.float64)
            if count < 2:
                relative = np.zeros(207, dtype=np.float64)
                cold += 1
            else:
                variance = m2 / float(count - 1)
                std = np.sqrt(np.maximum(variance, 1e-4))
                relative = np.clip((current - mean) / std, -8.0, 8.0)
            history = min(math.log1p(count) / math.log(1025.0), 1.0)
            result[record.uid] = np.concatenate(
                [current, relative, np.asarray([history], dtype=np.float64)]
            ).astype(np.float32)
            # Current event updates state only after its output view is frozen.
            count += 1
            delta = current - mean
            mean += delta / float(count)
            m2 += delta * (current - mean)
            updates += 1
    if len(result) != len(records):
        raise RuntimeError("causal source-relative view lost records")
    audit = {
        "phase_scope": phase_scope,
        "records": len(records),
        "sources": len(by_source),
        "fresh_resets": len(by_source),
        "score_before_update_records": len(records),
        "label_free_updates": updates,
        "cold_start_records": cold,
        "cold_start_fraction": float(cold / len(records)) if records else 0.0,
        "source_identity_as_feature": False,
        "label_read_for_state": False,
        "gradient_updates": 0,
        "phase_state_crossing": False,
        "output_dim": 415,
        "state_event_scope": "frozen_scored_target_rows_only",
        "memory_only_events": 0,
    }
    return result, audit


def choose_verifier_gate(
    name: str,
    support_val: list[ckbj.Record],
    select_benign: list[ckbj.Record],
    verifier: dict[str, float],
    c1_threshold: float,
) -> tuple[float, list[dict[str, Any]], bool]:
    """Select the exact legal attack-preserving verifier frontier.

    A verifier decision changes only when the threshold crosses a legal
    ``support_val`` attack score.  Evaluating those scores plus a below-minimum
    sentinel therefore covers every distinct attack-retention set without
    reading any report score.  This avoids the coarse benign-quantile grid used
    by the older TGN experiment, which could miss a feasible preservation gate.
    """
    if not support_val or not select_benign:
        raise RuntimeError("gate selection needs legal support_val and benign select rows")
    attack_values = np.asarray([verifier[item.uid] for item in support_val], dtype=np.float64)
    benign_values = np.asarray([verifier[item.uid] for item in select_benign], dtype=np.float64)
    if not np.isfinite(attack_values).all() or not np.isfinite(benign_values).all():
        raise RuntimeError(f"{name}: nonfinite legal gate score")
    c1_attack = np.asarray([item.c1_score >= c1_threshold for item in support_val], dtype=bool)
    c1_benign = np.asarray([item.c1_score >= c1_threshold for item in select_benign], dtype=bool)
    lower = float(np.nextafter(min(float(attack_values.min()), float(benign_values.min())), -np.inf))
    thresholds = sorted({lower, *(float(value) for value in attack_values.tolist())})
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        verifier_attack = attack_values >= threshold
        hard_attack = c1_attack & verifier_attack
        base_recall = float(np.mean(c1_attack))
        recall = float(np.mean(hard_attack))
        family_ok = True
        for family in sorted({item.attack_family for item in support_val}):
            mask = np.asarray([item.attack_family == family for item in support_val], dtype=bool)
            if int(mask.sum()) >= 3 and float(np.mean(hard_attack[mask])) < float(np.mean(c1_attack[mask])) - 0.02:
                family_ok = False
        benign_hard = c1_benign & (benign_values >= threshold)
        rows.append(
            {
                "candidate": name,
                "verifier_threshold": threshold,
                "threshold_frontier": "exact_support_val_attack_scores",
                "support_val_c1_recall": base_recall,
                "support_val_hard_recall": recall,
                "select_benign_hard_rate": float(np.mean(benign_hard)),
                "eligible": bool(recall >= base_recall - 0.005 and family_ok),
                "support_val_rows_used": len(support_val),
                "select_benign_rows_used": len(select_benign),
                "report_rows_used": 0,
            }
        )
    eligible = [row for row in rows if bool(row["eligible"])]
    if not eligible:
        selected = max(rows, key=lambda row: (row["support_val_hard_recall"], -row["verifier_threshold"]))
        selected["selected"] = True
        selected["selected_despite_constraint_failure"] = True
        selected["gate_constraint_pass"] = False
        return float(selected["verifier_threshold"]), rows, False
    selected = min(
        eligible,
        key=lambda row: (row["select_benign_hard_rate"], -row["verifier_threshold"]),
    )
    selected["selected"] = True
    selected["selected_despite_constraint_failure"] = False
    selected["gate_constraint_pass"] = True
    return float(selected["verifier_threshold"]), rows, True


def balanced_training_sample(
    records: list[ckbj.Record], seed: int
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]], Counter[str]]:
    """Build one family-balanced epoch while covering every legal row."""
    attack_groups: defaultdict[str, list[int]] = defaultdict(list)
    benign_groups: defaultdict[str, list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        if record.label == 1:
            attack_groups[record.attack_family].append(index)
        else:
            benign_groups[record.source].append(index)
    if not attack_groups or not benign_groups:
        raise RuntimeError("training weights require attack families and benign sources")
    rng = np.random.default_rng(int(seed))
    max_attack = max(len(indices) for indices in attack_groups.values())
    sampled = list(range(len(records)))
    for _family, indices in sorted(attack_groups.items()):
        needed = max_attack - len(indices)
        while needed > 0:
            cycle = rng.permutation(np.asarray(indices, dtype=np.int64)).tolist()
            take = min(needed, len(cycle))
            sampled.extend(int(value) for value in cycle[:take])
            needed -= take
    sampled_indices = np.asarray(sampled, dtype=np.int64)
    occurrence_counts = Counter(records[index].uid for index in sampled)
    weights = np.zeros(len(sampled), dtype=np.float64)
    attack_lookup = {index: family for family, indices in attack_groups.items() for index in indices}
    benign_lookup = {index: source for source, indices in benign_groups.items() for index in indices}
    for position, original_index in enumerate(sampled):
        if original_index in attack_lookup:
            weights[position] = 0.5 / len(attack_groups) / max_attack
        else:
            source = benign_lookup[original_index]
            weights[position] = 0.5 / len(benign_groups) / len(benign_groups[source])
    audit: list[dict[str, Any]] = []
    for label, groups in ((1, attack_groups), (0, benign_groups)):
        for name, indices in sorted(groups.items()):
            sampled_occurrences = sum(occurrence_counts[records[index].uid] for index in indices)
            audit.append(
                {
                    "label": label,
                    "balance_unit": "attack_family" if label else "benign_source",
                    "group": name,
                    "unique_rows": len(indices),
                    "sampled_occurrences_per_epoch": sampled_occurrences,
                    "target_occurrences_per_attack_family": max_attack if label else math.nan,
                    "mandatory_full_coverage": True,
                    "family_balanced_sampling": bool(label),
                    "unnormalized_group_mass": 0.5 / len(groups),
                }
            )
    weights *= len(weights) / weights.sum()
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise RuntimeError("invalid family/source-balanced row weights")
    if len(occurrence_counts) != len(records) or min(occurrence_counts.values()) < 1:
        raise RuntimeError("balanced sampler omitted a legal fit row")
    attack_occurrences = {
        row["sampled_occurrences_per_epoch"] for row in audit if row["label"] == 1
    }
    if attack_occurrences != {max_attack}:
        raise RuntimeError("attack-family sampling did not balance occurrences")
    for row in audit:
        row["normalized_mean_weight"] = 1.0
    return sampled_indices, weights.astype(np.float32), audit, occurrence_counts


class TabMClassifier:
    def __init__(
        self,
        d_in: int,
        seed: int,
        epochs: int,
        batch_size: int,
        threads: int,
        k: int,
        d_block: int,
        n_blocks: int,
    ) -> None:
        torch.manual_seed(int(seed))
        torch.set_num_threads(max(1, int(threads)))
        self.model = tabm.TabM.make(
            n_num_features=int(d_in),
            d_out=2,
            num_embeddings=None,
            k=int(k),
            d_block=int(d_block),
            n_blocks=int(n_blocks),
            dropout=0.1,
        )
        self.seed = int(seed)
        self.epochs = int(epochs)
        self.batch_size = int(batch_size)
        self.history: list[dict[str, Any]] = []

    def fit(self, x: np.ndarray, y: np.ndarray, weights: np.ndarray) -> "TabMClassifier":
        if len(x) != len(y) or len(y) != len(weights):
            raise RuntimeError("TabM training arrays are not aligned")
        xt = torch.from_numpy(np.asarray(x, dtype=np.float32))
        yt = torch.from_numpy(np.asarray(y, dtype=np.int64))
        wt = torch.from_numpy(np.asarray(weights, dtype=np.float32))
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=0.002, weight_decay=0.0003)
        generator = torch.Generator().manual_seed(self.seed)
        for epoch in range(self.epochs):
            self.model.train()
            order = torch.randperm(len(xt), generator=generator)
            weighted_sum = 0.0
            weight_sum = 0.0
            batches = 0
            for index in order.split(self.batch_size):
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(xt[index])
                if logits.shape[:2] != (len(index), self.model.k):
                    raise RuntimeError(f"TabM ensemble output shape drift: {tuple(logits.shape)}")
                expanded_y = yt[index].repeat_interleave(self.model.k)
                member_loss = F.cross_entropy(
                    logits.flatten(0, 1), expanded_y, reduction="none"
                ).view(len(index), self.model.k)
                row_loss = member_loss.mean(dim=1)
                batch_weight = wt[index]
                loss = (row_loss * batch_weight).sum() / batch_weight.sum()
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError(f"nonfinite TabM loss at epoch {epoch}")
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
                weighted_sum += float((row_loss.detach() * batch_weight).sum())
                weight_sum += float(batch_weight.sum())
                batches += 1
            epoch_loss = weighted_sum / max(weight_sum, 1e-12)
            self.history.append(
                {
                    "epoch": epoch + 1,
                    "weighted_cross_entropy": epoch_loss,
                    "batches": batches,
                    "rows_visited": len(x),
                    "all_unique_rows_covered": True,
                    "sampling_contract": "coverage_first_attack_family_balanced",
                    "finite_losses": bool(math.isfinite(epoch_loss)),
                    "support_val_used_for_early_stopping": False,
                }
            )
        return self

    @torch.no_grad()
    def predict_proba(self, x: np.ndarray, batch_size: int = 4096) -> np.ndarray:
        self.model.eval()
        xt = torch.from_numpy(np.asarray(x, dtype=np.float32))
        parts: list[torch.Tensor] = []
        for index in torch.arange(len(xt)).split(int(batch_size)):
            logits = self.model(xt[index])
            # Official rule: average class probabilities, never logits.
            parts.append(torch.softmax(logits, dim=-1).mean(dim=1)[:, 1].cpu())
        return torch.cat(parts).numpy().astype(np.float32) if parts else np.zeros(0, dtype=np.float32)

    def model_hash(self) -> str:
        stream = io.BytesIO()
        torch.save(self.model.state_dict(), stream)
        return hashlib.sha256(stream.getvalue()).hexdigest()


def fit_backend(
    spec: BackendSpec,
    x: np.ndarray,
    y: np.ndarray,
    weights: np.ndarray,
    args: argparse.Namespace,
    seed: int,
) -> tuple[Any, list[dict[str, Any]], str]:
    if spec.kind == "extratrees":
        model = ExtraTreesClassifier(
            n_estimators=int(args.extra_trees),
            min_samples_leaf=2,
            max_features="sqrt",
            random_state=int(seed),
            n_jobs=max(1, int(args.threads)),
        )
        model.fit(x, y, sample_weight=weights)
        history = [
            {
                "epoch": 1,
                "weighted_cross_entropy": math.nan,
                "batches": 1,
                "rows_visited": len(x),
                "all_unique_rows_covered": True,
                "sampling_contract": "coverage_first_attack_family_balanced",
                "finite_losses": True,
                "support_val_used_for_early_stopping": False,
            }
        ]
        return model, history, hashlib.sha256(pickle.dumps(model, protocol=5)).hexdigest()
    model = TabMClassifier(
        d_in=x.shape[1],
        seed=seed,
        epochs=int(args.epochs),
        batch_size=int(args.batch_size),
        threads=int(args.threads),
        k=int(args.tabm_k),
        d_block=int(args.tabm_width),
        n_blocks=int(args.tabm_blocks),
    ).fit(x, y, weights)
    return model, model.history, model.model_hash()


def backend_scores(model: Any, x: np.ndarray) -> np.ndarray:
    if isinstance(model, TabMClassifier):
        return model.predict_proba(x)
    return np.asarray(model.predict_proba(x)[:, 1], dtype=np.float32)


def usage_rows(
    candidate: str,
    support: list[ckbj.Record],
    occurrences_per_epoch: Counter[str],
    epochs: int,
    held: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = [
        {
            "candidate": candidate,
            "held_value": held,
            "uid": record.uid,
            "source_group": record.source,
            "attack_family": record.attack_family,
            "sampled_occurrences_per_epoch": int(occurrences_per_epoch[record.uid]),
            "epochs": int(epochs),
            "times_used": int(occurrences_per_epoch[record.uid] * epochs),
            "used_at_least_once_each_epoch": bool(occurrences_per_epoch[record.uid] >= 1),
        }
        for record in support
    ]
    counts = Counter(record.attack_family for record in support)
    families = [
        {
            "candidate": candidate,
            "held_value": held,
            "attack_family": family,
            "support_rows": count,
            "sampled_occurrences_per_epoch": int(
                sum(
                    occurrences_per_epoch[record.uid]
                    for record in support
                    if record.attack_family == family
                )
            ),
            "epochs": int(epochs),
            "total_row_visits": int(
                sum(
                    occurrences_per_epoch[record.uid]
                    for record in support
                    if record.attack_family == family
                )
                * epochs
            ),
        }
        for family, count in sorted(counts.items())
    ]
    return rows, families


def build_protocol_views(
    transformer: QuantileTransformer,
    sets: dict[str, list[ckbj.Record]],
    base: dict[str, np.ndarray],
) -> tuple[dict[str, dict[str, np.ndarray]], list[dict[str, Any]]]:
    phases = {
        "fit": sets["fit_attack"] + sets["fit_benign"],
        "select": sets["select_attack"] + sets["select_benign"],
        "report": sets["report"],
    }
    global_map: dict[str, np.ndarray] = {}
    csr_map: dict[str, np.ndarray] = {}
    audits: list[dict[str, Any]] = []
    for phase, records in phases.items():
        current = transformed_map(transformer, records, base)
        global_map.update(current)
        causal, audit = causal_source_relative_map(records, current, phase)
        csr_map.update(causal)
        audits.append(audit)
    expected = sum(len(part) for part in phases.values())
    if len(global_map) != expected or len(csr_map) != expected:
        raise RuntimeError("phase view maps are incomplete")
    return {"global": global_map, "csr": csr_map}, audits


def run_protocol(
    held: str | None,
    args: argparse.Namespace,
    x_by_role: dict[str, np.ndarray],
    frames: dict[str, pd.DataFrame],
    t0: T0Cache,
    position_cache: dict[str, dict[int, int]],
    input_audit: dict[str, Any],
    source_map: dict[str, set[str]],
) -> dict[str, Any]:
    name = "GLOBAL_ATTACK_PRESERVATION" if held is None else str(held)
    c1_model, frontend, c1_threshold, c1_audit = ckbj.fit_c1(
        x_by_role,
        frames,
        held,
        Path(args.c1_cache),
        Path(args.c1_plan),
        Path(args.c1_report_extension),
        int(args.train_cap),
        int(args.eval_cap),
    )
    sets, data_audit = ckbj.collect_protocol_records(
        c1_model,
        frontend,
        frames,
        t0,
        position_cache,
        held,
        int(args.train_cap),
        int(args.eval_cap),
    )
    held_audit = ckbj.held_exclusion_counts(frames, held, int(args.train_cap), int(args.eval_cap))
    blocked_sources = ckbj.held_source_groups(frames, held, source_map)
    held_audit += ckbj.apply_temporal_source_exclusion(sets, blocked_sources, held)
    if not sets["fit_attack"] or not sets["fit_benign"]:
        raise RuntimeError(f"{name}: empty fit class after strict held exclusion")
    if not sets["select_attack"] or not sets["select_benign"]:
        raise RuntimeError(f"{name}: empty legal gate selection class")

    all_records = unique_records(
        [
            sets["fit_attack"],
            sets["fit_benign"],
            sets["select_attack"],
            sets["select_benign"],
            sets["report"],
        ]
    )
    base, feature_audit = frontend_feature_map(frontend, all_records)
    fit_records = sets["fit_attack"] + sets["fit_benign"]
    transformer, preprocessing = fit_preprocessor(fit_records, base, int(args.seed))
    views, causal_audit = build_protocol_views(transformer, sets, base)
    y_fit = np.asarray([record.label for record in fit_records], dtype=np.int64)
    sampled_indices, weights, weight_audit, occurrence_counts = balanced_training_sample(
        fit_records, int(args.seed)
    )
    sampled_y = y_fit[sampled_indices]

    selection_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    support_usage: list[dict[str, Any]] = []
    support_family_usage: list[dict[str, Any]] = []
    scores_by_candidate: dict[str, dict[str, float]] = {}
    thresholds: dict[str, float] = {}
    gate_passes: dict[str, bool] = {}

    for spec in BACKENDS:
        view = views[spec.view]
        x_fit = stack_map(fit_records, view)[sampled_indices]
        model, history, model_hash = fit_backend(
            spec,
            x_fit,
            sampled_y,
            weights,
            args,
            int(args.seed),
        )
        all_scores = backend_scores(model, stack_map(all_records, view))
        if len(all_scores) != len(all_records) or not np.isfinite(all_scores).all():
            raise RuntimeError(f"{name}/{spec.name}: invalid verifier scores")
        score_map = {record.uid: float(score) for record, score in zip(all_records, all_scores)}
        scores_by_candidate[spec.name] = score_map
        threshold, rows, gate_pass = choose_verifier_gate(
            spec.name,
            sets["select_attack"],
            sets["select_benign"],
            score_map,
            c1_threshold,
        )
        thresholds[spec.name] = float(threshold)
        gate_passes[spec.name] = bool(gate_pass)
        selection_rows.extend(
            {
                **row,
                "held_value": name,
                "c1_candidate_threshold": c1_threshold,
                "gate_constraint_pass": bool(gate_pass),
                "report_rows_used": 0,
            }
            for row in rows
        )
        loss_rows.extend({**row, "candidate": spec.name, "held_value": name} for row in history)
        epochs = int(args.epochs) if spec.kind == "tabm" else 1
        used, families = usage_rows(
            spec.name, sets["fit_attack"], occurrence_counts, epochs, name
        )
        support_usage.extend(used)
        support_family_usage.extend(families)
        model_rows.append(
            {
                "candidate": spec.name,
                "held_value": name,
                "backend": spec.kind,
                "view": spec.view,
                "primary": spec.primary,
                "input_dim": int(x_fit.shape[1]),
                "fit_rows": len(fit_records),
                "sampled_training_occurrences_per_epoch": len(sampled_indices),
                "all_unique_fit_rows_covered": len(occurrence_counts) == len(fit_records),
                "fit_attack_rows": len(sets["fit_attack"]),
                "fit_benign_rows": len(sets["fit_benign"]),
                "model_sha256": model_hash,
                "official_tabm": spec.kind == "tabm",
            }
        )

    attack_records = sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
    global_ood_records = [record for record in sets["report"] if record.label == 0]
    strict_records = sets["report"] if held is not None else attack_records + global_ood_records
    c1_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    metrics: list[dict[str, Any]] = []
    family_metrics: list[dict[str, Any]] = []
    attack_summary: list[dict[str, Any]] = []
    strict_summary: list[dict[str, Any]] = []
    rows, families = ckbj.metric_rows(
        "M0-C1",
        "strict_leave" if held else "attack_preservation",
        name,
        strict_records,
        c1_hard,
        int(args.bootstrap_reps),
        int(args.seed),
    )
    metrics += rows
    family_metrics += families
    if held is None:
        attack_summary += ckbj.attack_summary_rows(
            "M0-C1", strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
        )
    else:
        strict_summary += ckbj.strict_level2_summary(
            "M0-C1", name, strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
        )
    for spec in BACKENDS:
        hard = ckbj.hard_decisions(
            spec.name,
            strict_records,
            scores_by_candidate[spec.name],
            c1_threshold,
            thresholds[spec.name],
        )
        rows, families = ckbj.metric_rows(
            spec.name,
            "strict_leave" if held else "attack_preservation",
            name,
            strict_records,
            hard,
            int(args.bootstrap_reps),
            int(args.seed),
        )
        metrics += rows
        family_metrics += families
        if held is None:
            attack_summary += ckbj.attack_summary_rows(
                spec.name, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
            )
        else:
            strict_summary += ckbj.strict_level2_summary(
                spec.name, name, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)
            )

    extension_sources = set(getattr(t0, "report_only_sources", set()))
    event_scope = ckbj.event_scope_rows(sets, extension_sources)
    for row in event_scope:
        row["held_value"] = name
        row["protocol_run"] = name
        row["target_events"] = int(row["events"])
        row["memory_only_events"] = 0
    for rows_to_mark in (c1_audit, data_audit, held_audit):
        for row in rows_to_mark:
            row["protocol_run"] = name
    for row in feature_audit:
        row["held_value"] = name
        row["protocol_run"] = name
    for row in causal_audit:
        row["held_value"] = name
        row["protocol_run"] = name
    for row in weight_audit:
        row["held_value"] = name
        row["protocol_run"] = name
    preprocessing["held_value"] = name
    preprocessing["protocol_run"] = name
    return {
        "protocol": name,
        "held": held,
        "input_audit": input_audit,
        "c1_audit": c1_audit,
        "data_audit": data_audit,
        "held_audit": held_audit,
        "feature_audit": feature_audit,
        "causal_audit": causal_audit,
        "preprocessing": [preprocessing],
        "weight_audit": weight_audit,
        "model_audit": model_rows,
        "event_scope": event_scope,
        "support_usage": support_usage,
        "support_family_usage": support_family_usage,
        "losses": loss_rows,
        "selection": selection_rows,
        "metrics": metrics,
        "family_metrics": family_metrics,
        "attack_summary": attack_summary,
        "strict_summary": strict_summary,
        "thresholds": {"c1_candidate": c1_threshold, **thresholds},
        "gate_constraint_pass": gate_passes,
    }


def single_seed_decision(
    attack: pd.DataFrame,
    strict: pd.DataFrame,
    selection: pd.DataFrame,
    data_audit: pd.DataFrame,
    support: pd.DataFrame,
    causal: pd.DataFrame,
    extension_ok: bool,
) -> dict[str, Any]:
    def first(table: pd.DataFrame, column: str, **where: Any) -> float | None:
        part = table
        for key, value in where.items():
            if key not in part:
                return None
            part = part.loc[part[key].eq(value)]
        if part.empty or column not in part:
            return None
        return float(part.iloc[0][column])

    overall_delta = first(
        attack, "delta_vs_c1_pp", candidate=PRIMARY, metric="overall_attack_hard_recall"
    )
    stream = first(strict, "hard_rate", candidate=PRIMARY, held_value="iotsim-stream-consumer")
    stream_c1 = first(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-stream-consumer")
    hydraulic = first(strict, "hard_rate", candidate=PRIMARY, held_value="iotsim-hydraulic-system")
    hydraulic_c1 = first(strict, "hard_rate", candidate="M0-C1", held_value="iotsim-hydraulic-system")
    major = attack.loc[
        attack.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & attack.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")
        & pd.to_numeric(attack.get("rows", pd.Series(dtype=float)), errors="coerce").ge(15)
    ]
    selected = selection.loc[
        selection.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & ckbj.bool_series(
            selection.get("selected", pd.Series(False, index=selection.index))
        )
    ]
    alignment_bad = bool(
        data_audit.empty
        or "target_alignment_incomplete" not in data_audit
        or pd.to_numeric(data_audit["target_alignment_incomplete"], errors="coerce").fillna(1).gt(0).any()
    )
    support_bad = bool(
        support.empty
        or "used_at_least_once_each_epoch" not in support
        or not ckbj.bool_series(support["used_at_least_once_each_epoch"]).all()
    )
    causal_bad = bool(
        causal.empty
        or not pd.to_numeric(causal["score_before_update_records"], errors="coerce").eq(
            pd.to_numeric(causal["records"], errors="coerce")
        ).all()
        or ckbj.bool_series(causal["label_read_for_state"]).any()
        or ckbj.bool_series(causal["phase_state_crossing"]).any()
    )
    missing = any(value is None for value in (overall_delta, stream, stream_c1, hydraulic, hydraulic_c1)) or major.empty
    checks = {
        "required_metrics_missing": missing,
        "overall_attack_drop_over_0_5pp": overall_delta is None or overall_delta < -0.5,
        "major_attack_family_drop_over_2pp": major.empty or bool((pd.to_numeric(major["delta_vs_c1_pp"]) < -2.0).any()),
        "stream_signal_missing": stream is None or stream_c1 is None or stream > 0.90 or stream > stream_c1 - 0.10,
        "hydraulic_worsened_over_2pp": hydraulic is None or hydraulic_c1 is None or hydraulic > hydraulic_c1 + 0.02,
        "gate_constraint_failed": selected.empty or not selected.get(
            "gate_constraint_pass", pd.Series(False, index=selected.index)
        ).pipe(ckbj.bool_series).all(),
        "report_extension_used_in_fit_or_select": not bool(extension_ok),
        "target_alignment_incomplete": alignment_bad,
        "support_usage_incomplete": support_bad,
        "causal_order_or_reset_contract_failed": causal_bad,
        "review_not_zero": bool(
            (pd.to_numeric(attack.get("review_rate", pd.Series([1])), errors="coerce").fillna(1) != 0).any()
            or (pd.to_numeric(strict.get("review_rate", pd.Series([1])), errors="coerce").fillna(1) != 0).any()
        ),
    }
    return {
        "seed": 27,
        "candidate": PRIMARY,
        "decision": "GO_SIGNAL" if not any(checks.values()) else "NO_GO",
        "checks": checks,
        "overall_attack_delta_pp": overall_delta,
        "stream_ood_hard_rate": stream,
        "stream_c1_hard_rate": stream_c1,
        "hydraulic_ood_hard_rate": hydraulic,
        "hydraulic_c1_hard_rate": hydraulic_c1,
        "development_canaries_not_untouched_final": True,
    }


def validate_vendor() -> dict[str, Any]:
    source = VENDOR_TABM / "tabm.py"
    license_path = VENDOR_TABM / "LICENSE"
    if sha256_file_lf(source) != UPSTREAM_TABM_SHA256_LF:
        raise RuntimeError("vendored TabM differs from frozen upstream v0.0.3")
    if tabm.__version__ != "0.0.3":
        raise RuntimeError(f"unexpected TabM version: {tabm.__version__}")
    return {
        "version": tabm.__version__,
        "upstream_commit": UPSTREAM_TABM_COMMIT,
        "tabm_py_sha256_lf": sha256_file_lf(source),
        "license_sha256_lf": sha256_file_lf(license_path),
        "license": "Apache-2.0",
        "numerical_embeddings": False,
        "source_modified": False,
    }


def prepare_formal_inputs(args: argparse.Namespace, out: Path) -> tuple[Any, ...]:
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    live = ckbi.report_only_exclusion(frames)
    live.to_csv(out / "ckbm_live_report_extension_fit_select_exclusion.csv", index=False)
    required = live.loc[live["required_zero"].notna()]
    if required.empty or int(pd.to_numeric(required["extension_source_rows_used"]).sum()) != 0:
        raise RuntimeError("report-only extension source entered current fit/select sidecars")
    if not bool(ckbj.bool_series(required["pass"]).all()):
        raise RuntimeError("live report-only exclusion audit failed")
    base_t0 = T0Cache(Path(args.t0_root))
    t0_audit = ckbj.validate_t0_runtime(base_t0)
    extension_audit = ckbj.validate_report_extension(Path(args.report_t0_extension))
    c1_ready = Path(args.c1_report_extension) / "c1_report_extension_ready.json"
    if not c1_ready.is_file():
        raise RuntimeError(f"missing previously completed C1 report extension: {c1_ready}")
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
    pd.DataFrame(coverage).to_csv(out / "ckbm_required_report_source_coverage.csv", index=False)
    if any(not bool(row["full_source_coverage"]) for row in coverage):
        raise RuntimeError("formal CKBM target coverage is incomplete")
    family_contract = ckbj.source_family_contract(frames)
    pd.DataFrame(family_contract).to_csv(out / "ckbm_source_family_contract.csv", index=False)
    pd.DataFrame(ckbj.support_val_lineage(frames)).to_csv(out / "ckbm_support_val_lineage.csv", index=False)
    return x_by_role, frames, input_audit, t0, t0_audit, extension_audit, c1_audit


def finalize_formal_metadata(
    args: argparse.Namespace,
    out: Path,
    output_files: dict[str, pd.DataFrame],
    input_audit: dict[str, Any],
    t0_audit: dict[str, Any],
    extension_audit: dict[str, Any],
    c1_extension_audit: dict[str, Any],
    vendor: dict[str, Any],
    started: float,
    recovery: dict[str, Any] | None = None,
) -> dict[str, Any]:
    extension_ok = bool(
        extension_audit["report_only_fit_select_exclusion_pass"]
        and c1_extension_audit["report_only_fit_select_exclusion_pass"]
    )
    decision = single_seed_decision(
        output_files["attack_preservation_summary.csv"],
        output_files["strict_level2_summary.csv"],
        output_files["ckbm_candidate_selection.csv"],
        output_files["ckbm_role_usage_audit.csv"],
        output_files["ckbm_support_training_usage.csv"],
        output_files["ckbm_causal_source_state_audit.csv"],
        extension_ok,
    )
    dump_json(out / "ckbm_single_seed_go_no_go.json", decision)
    manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    default_seconds = time.time() - started
    seconds = float(os.environ.get("CKBM_ORIGINAL_WALL_SECONDS", default_seconds))
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "torch": torch.__version__,
        "tabm": tabm.__version__,
        "seed": int(args.seed),
        "commit_sha": os.environ.get("CKBM_COMMIT_SHA", git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "seconds": seconds,
        "review_rate": 0.0,
        "base_manifest_sha256": manifest_hash,
        "expected_base_manifest_sha256": EXPECTED_T0_MANIFEST_SHA256,
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "vendor": vendor,
        "tabm_hyperparameters": {
            "k": int(args.tabm_k),
            "width": int(args.tabm_width),
            "blocks": int(args.tabm_blocks),
            "epochs": int(args.epochs),
            "batch_size": int(args.batch_size),
            "lr": 0.002,
            "weight_decay": 0.0003,
            "probability_ensemble_at_inference": True,
            "independent_member_loss": True,
        },
    }
    if recovery is not None:
        environment["metadata_recovery"] = recovery
    dump_json(out / "ckbm_environment.json", environment)
    requested = [value.strip() for value in args.held_values.split(",") if value.strip()]
    run_spec = {
        "issue": ISSUE,
        "mode": "formal",
        "seed": int(args.seed),
        "held_values": requested,
        "primary_candidate": PRIMARY,
        "candidates": [spec.__dict__ for spec in BACKENDS],
        "input_audit": input_audit,
        "t0_audit": t0_audit,
        "extension_audit": extension_audit,
        "c1_extension_audit": c1_extension_audit,
        "report_used_for_fit_or_select": False,
        "report_inference": "label-free, no-grad for TabM, fresh source reset, score-before-update, past-only",
        "support_val_use": "threshold/gate selection only; no fitting or early stopping",
        "support_train_sampling": "coverage-first, equal attack-family occurrences, every legal row at least once per epoch",
        "review_rate": 0.0,
        "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
        "untouched_final_claim_allowed": False,
        "single_seed_scope": "go/no-go signal only",
        "environment": environment,
    }
    if recovery is not None:
        run_spec["metadata_recovery"] = recovery
    dump_json(out / "run_spec.json", run_spec)
    recovery_note = " Metadata was recovered without retraining." if recovery is not None else ""
    write_text_lf(
        out / "codex_readout.md",
        f"# {ISSUE}\n\nSeed 27 formal result completed. Primary decision: "
        f"`{decision['decision']}` for `{PRIMARY}`. Review is fixed at `0`."
        f"{recovery_note}\n",
    )
    return decision


def finalize_existing(args: argparse.Namespace) -> None:
    """Finish metadata for a run whose scientific CSVs were already written.

    This mode exists for the seed-27 AMD run that completed all protocol
    training and metric CSV writes before the legacy Python runtime rejected a
    Path.write_text(newline=...) call.  It never trains or scores a model.
    """
    started = time.time()
    out = Path(args.out)
    if int(args.seed) != 27:
        raise RuntimeError("metadata recovery is restricted to preregistered seed 27")
    if not out.is_dir():
        raise RuntimeError(f"missing existing formal output directory: {out}")
    metadata_outputs = [
        out / "ckbm_single_seed_go_no_go.json",
        out / "ckbm_environment.json",
        out / "run_spec.json",
        out / "codex_readout.md",
    ]
    existing_metadata = [path.name for path in metadata_outputs if path.exists()]
    if existing_metadata:
        raise RuntimeError(f"refusing to overwrite existing formal metadata: {existing_metadata}")
    required_tables = (
        "ckbm_c1_fit_select_audit.csv",
        "ckbm_role_usage_audit.csv",
        "ckbm_held_exclusion_audit.csv",
        "ckbm_feature_input_audit.csv",
        "ckbm_causal_source_state_audit.csv",
        "ckbm_preprocessing_audit.csv",
        "ckbm_training_weight_audit.csv",
        "ckbm_model_audit.csv",
        "ckbm_event_scope_audit.csv",
        "ckbm_support_training_usage.csv",
        "ckbm_support_family_training_usage.csv",
        "ckbm_loss_curves.csv",
        "ckbm_candidate_selection.csv",
        "ckbm_all_metrics.csv",
        "ckbm_per_attack_family_metrics.csv",
        "attack_preservation_summary.csv",
        "strict_level2_summary.csv",
        "ckbm_negative_sampling_audit.csv",
        "attack_preservation_metrics.csv",
        "strict_level2_metrics.csv",
    )
    output_files: dict[str, pd.DataFrame] = {}
    for name in required_tables:
        path = out / name
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"missing completed formal table: {path}")
        table = pd.read_csv(path)
        if table.empty:
            raise RuntimeError(f"empty completed formal table: {path}")
        if "seed" in table and not pd.to_numeric(table["seed"], errors="coerce").eq(27).all():
            raise RuntimeError(f"non-seed-27 row in completed formal table: {name}")
        output_files[name] = table
    selection = output_files["ckbm_candidate_selection.csv"]
    expected_scopes = {"GLOBAL_ATTACK_PRESERVATION", *[value.strip() for value in args.held_values.split(",") if value.strip()]}
    actual_scopes = set(selection["held_value"].astype(str))
    if actual_scopes != expected_scopes:
        raise RuntimeError(
            f"completed protocol scopes differ: expected={sorted(expected_scopes)} actual={sorted(actual_scopes)}"
        )
    live_path = out / "ckbm_live_report_extension_fit_select_exclusion.csv"
    if not live_path.is_file():
        raise RuntimeError(f"missing live report exclusion audit: {live_path}")
    live = pd.read_csv(live_path)
    required_zero = live.loc[live.get("required_zero", pd.Series(dtype=object)).notna()]
    if required_zero.empty or int(pd.to_numeric(required_zero["extension_source_rows_used"]).sum()) != 0:
        raise RuntimeError("report-only extension entered fit/select in completed compute")
    extension_audit = json.loads(
        (Path(args.report_t0_extension) / "extension_ready.json").read_text(encoding="utf-8")
    )
    c1_extension_audit = json.loads(
        (Path(args.c1_report_extension) / "c1_report_extension_ready.json").read_text(encoding="utf-8")
    )
    if not bool(extension_audit.get("report_only_fit_select_exclusion_pass")):
        raise RuntimeError("TGN report extension isolation is not certified")
    if not bool(c1_extension_audit.get("report_only_fit_select_exclusion_pass")):
        raise RuntimeError("C1 report extension isolation is not certified")
    manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    manifest_hash = hashlib.sha256(manifest.read_bytes()).hexdigest()
    if manifest_hash != EXPECTED_T0_MANIFEST_SHA256:
        raise RuntimeError("frozen CKBE manifest changed before metadata recovery")
    recovery = {
        "mode": "existing_completed_formal_tables_no_retraining",
        "reason": "Path.write_text newline keyword unsupported by frozen HPC Python after all scientific CSV writes",
        "original_compute_commit_sha": os.environ.get("CKBM_COMMIT_SHA", "unknown"),
        "recovery_commit_sha": os.environ.get("CKBM_RECOVERY_COMMIT_SHA", git_head()),
        "original_job_id": os.environ.get("SLURM_JOB_ID", "unknown"),
        "original_partition": os.environ.get("SLURM_JOB_PARTITION", "unknown"),
        "formal_tables_verified_before_metadata_write": sorted(required_tables),
    }
    input_audit = {
        "recovered_from": "ckbm_feature_input_audit.csv",
        "formal_table_sha256": hashlib.sha256((out / "ckbm_feature_input_audit.csv").read_bytes()).hexdigest(),
        "scientific_compute_reused": True,
        "models_retrained": False,
    }
    t0_audit = {
        "recovered_from_completed_formal_compute": True,
        "manifest_sha256": manifest_hash,
        "models_retrained": False,
    }
    decision = finalize_formal_metadata(
        args,
        out,
        output_files,
        input_audit,
        t0_audit,
        extension_audit,
        c1_extension_audit,
        validate_vendor(),
        started,
        recovery,
    )
    print(
        json.dumps(
            {
                "status": "CKBM_EXISTING_FORMAL_METADATA_COMPLETE",
                "out": str(out),
                "decision": decision["decision"],
                "models_retrained": False,
            },
            indent=2,
        )
    )


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    unexpected = [path.name for path in out.iterdir() if path.name not in {"resource_usage.txt"}]
    if unexpected:
        raise RuntimeError(f"refusing mixed formal output directory: {unexpected[:5]}")
    vendor = validate_vendor()
    x_by_role, frames, input_audit, t0, t0_audit, extension_audit, c1_extension_audit = prepare_formal_inputs(args, out)
    position_cache: dict[str, dict[int, int]] = {}
    source_map = ckbj.source_groups_by_family(frames)
    requested = [value.strip() for value in args.held_values.split(",") if value.strip()]
    if int(args.seed) != 27:
        raise RuntimeError("first CKBM formal run is preregistered for seed 27 only")
    results = [
        run_protocol(None, args, x_by_role, frames, t0, position_cache, input_audit, source_map)
    ]
    results.extend(
        run_protocol(held, args, x_by_role, frames, t0, position_cache, input_audit, source_map)
        for held in requested
    )
    row_keys = (
        "c1_audit",
        "data_audit",
        "held_audit",
        "feature_audit",
        "causal_audit",
        "preprocessing",
        "weight_audit",
        "model_audit",
        "event_scope",
        "support_usage",
        "support_family_usage",
        "losses",
        "selection",
        "metrics",
        "family_metrics",
        "attack_summary",
        "strict_summary",
    )
    for result in results:
        for key in row_keys:
            result[key] = [{**row, "seed": int(args.seed)} for row in result[key]]

    def frame(key: str) -> pd.DataFrame:
        return pd.DataFrame([row for result in results for row in result[key]])

    output_files = {
        "ckbm_c1_fit_select_audit.csv": frame("c1_audit"),
        "ckbm_role_usage_audit.csv": frame("data_audit"),
        "ckbm_held_exclusion_audit.csv": frame("held_audit"),
        "ckbm_feature_input_audit.csv": frame("feature_audit"),
        "ckbm_causal_source_state_audit.csv": frame("causal_audit"),
        "ckbm_preprocessing_audit.csv": frame("preprocessing"),
        "ckbm_training_weight_audit.csv": frame("weight_audit"),
        "ckbm_model_audit.csv": frame("model_audit"),
        "ckbm_event_scope_audit.csv": frame("event_scope"),
        "ckbm_support_training_usage.csv": frame("support_usage"),
        "ckbm_support_family_training_usage.csv": frame("support_family_usage"),
        "ckbm_loss_curves.csv": frame("losses"),
        "ckbm_candidate_selection.csv": frame("selection"),
        "ckbm_all_metrics.csv": frame("metrics"),
        "ckbm_per_attack_family_metrics.csv": frame("family_metrics"),
        "attack_preservation_summary.csv": frame("attack_summary"),
        "strict_level2_summary.csv": frame("strict_summary"),
    }
    output_files["ckbm_negative_sampling_audit.csv"] = pd.DataFrame(
        [
            {
                "seed": int(args.seed),
                "sampled_negatives": 0,
                "status": "not_applicable_supervised_tabular_verifier",
                "reason": "CKBM uses explicit legal attack and benign supervision; no link-prediction negative sampler",
                "report_rows_used": 0,
                "held_rows_used": 0,
            }
        ]
    )
    for filename, table in output_files.items():
        table.to_csv(out / filename, index=False)
    metrics = output_files["ckbm_all_metrics.csv"]
    metrics.loc[metrics["protocol"].eq("attack_preservation")].to_csv(
        out / "attack_preservation_metrics.csv", index=False
    )
    metrics.loc[metrics["protocol"].eq("strict_leave")].to_csv(
        out / "strict_level2_metrics.csv", index=False
    )
    decision = finalize_formal_metadata(
        args,
        out,
        output_files,
        input_audit,
        t0_audit,
        extension_audit,
        c1_extension_audit,
        vendor,
        started,
    )
    print(json.dumps({"status": "CKBM_FORMAL_COMPLETE", "out": str(out), "decision": decision["decision"]}, indent=2))


def contract_unit(args: argparse.Namespace) -> None:
    vendor = validate_vendor()
    with tempfile.TemporaryDirectory(prefix="ckbm_write_contract_") as temp_root:
        temp_path = Path(temp_root) / "compat.json"
        dump_json(temp_path, {"status": "pass", "seed": int(args.seed)})
        raw = temp_path.read_bytes()
        assert raw.endswith(b"\n") and b"\r\n" not in raw
        assert json.loads(raw.decode("utf-8"))["status"] == "pass"
    decision_tables = {
        "attack": pd.DataFrame(
            [
                {"candidate": PRIMARY, "metric": "overall_attack_hard_recall", "delta_vs_c1_pp": 0.0, "rows": 100, "review_rate": 0.0},
                {"candidate": PRIMARY, "metric": "attack_family_recall", "delta_vs_c1_pp": 0.0, "rows": 15, "review_rate": 0.0},
            ]
        ),
        "strict": pd.DataFrame(
            [
                {"candidate": PRIMARY, "held_value": "iotsim-stream-consumer", "hard_rate": 0.8, "review_rate": 0.0},
                {"candidate": "M0-C1", "held_value": "iotsim-stream-consumer", "hard_rate": 1.0, "review_rate": 0.0},
                {"candidate": PRIMARY, "held_value": "iotsim-hydraulic-system", "hard_rate": 0.5, "review_rate": 0.0},
                {"candidate": "M0-C1", "held_value": "iotsim-hydraulic-system", "hard_rate": 0.5, "review_rate": 0.0},
            ]
        ),
        "selection": pd.DataFrame(
            [{"candidate": PRIMARY, "selected": True, "gate_constraint_pass": True}]
        ),
        "data": pd.DataFrame([{"target_alignment_incomplete": 0}]),
        "support": pd.DataFrame([{"used_at_least_once_each_epoch": True}]),
        "causal": pd.DataFrame(
            [{"records": 1, "score_before_update_records": 1, "label_read_for_state": False, "phase_state_crossing": False}]
        ),
    }
    before_roundtrip = single_seed_decision(
        decision_tables["attack"], decision_tables["strict"], decision_tables["selection"],
        decision_tables["data"], decision_tables["support"], decision_tables["causal"], True,
    )
    roundtripped = {
        key: pd.read_csv(io.StringIO(table.to_csv(index=False)))
        for key, table in decision_tables.items()
    }
    after_roundtrip = single_seed_decision(
        roundtripped["attack"], roundtripped["strict"], roundtripped["selection"],
        roundtripped["data"], roundtripped["support"], roundtripped["causal"], True,
    )
    assert before_roundtrip == after_roundtrip
    assert after_roundtrip["decision"] == "GO_SIGNAL"
    torch.manual_seed(int(args.seed))
    model = tabm.TabM.make(n_num_features=7, d_out=2, k=4, n_blocks=2, d_block=16)
    logits = model(torch.randn(5, 7))
    assert logits.shape == (5, 4, 2)
    targets = torch.tensor([0, 1, 0, 1, 1]).repeat_interleave(4)
    loss = F.cross_entropy(logits.flatten(0, 1), targets)
    assert bool(torch.isfinite(loss))

    records = [
        ckbj.Record(
            uid=f"r:report:{index}",
            role="r",
            m1_phase="report",
            source=source,
            recorded_index=index,
            event_position=index,
            label=index % 2,
            attack_family="ignored",
            device_family="ignored",
            source_family="ignored",
            c1_score=0.5,
            episode_id="",
        )
        for index, source in enumerate(["a", "a", "a", "b", "b"])
    ]
    values = {record.uid: np.full(207, index, dtype=np.float32) for index, record in enumerate(records)}
    view, audit = causal_source_relative_map(records, values, "report")
    assert np.allclose(view[records[0].uid][207:414], 0.0)
    assert np.allclose(view[records[1].uid][207:414], 0.0)
    assert np.allclose(view[records[3].uid][207:414], 0.0)
    changed = dict(values)
    changed[records[2].uid] = np.full(207, 999.0, dtype=np.float32)
    changed_view, _ = causal_source_relative_map(records, changed, "report")
    assert np.array_equal(view[records[0].uid], changed_view[records[0].uid])
    assert np.array_equal(view[records[1].uid], changed_view[records[1].uid])
    relabeled = [replace(record, label=1 - record.label) for record in records]
    relabeled_view, _ = causal_source_relative_map(relabeled, values, "report")
    assert all(np.array_equal(view[key], relabeled_view[key]) for key in view)
    expected_third = (2.0 - 0.5) / math.sqrt(0.5)
    assert np.isclose(view[records[2].uid][207], expected_third)
    assert audit["fresh_resets"] == 2
    assert audit["score_before_update_records"] == len(records)
    assert audit["label_read_for_state"] is False
    duplicate_rejected = False
    try:
        unique_records([records, [replace(records[0], uid="duplicate:report:0")]])
    except RuntimeError as exc:
        duplicate_rejected = "duplicate source-local target event" in str(exc)
    assert duplicate_rejected

    gate_attack = [
        replace(
            records[index],
            uid=f"gate_attack:{index}",
            attack_family="family-a",
            c1_score=1.0,
        )
        for index in range(4)
    ]
    gate_benign = [
        replace(
            records[index % len(records)],
            uid=f"gate_benign:{index}",
            source=f"benign-{index}",
            c1_score=1.0,
        )
        for index in range(4)
    ]
    gate_scores = {
        **{record.uid: score for record, score in zip(gate_attack, [0.1, 0.2, 0.3, 0.4])},
        **{record.uid: score for record, score in zip(gate_benign, [0.8, 0.85, 0.9, 0.95])},
    }
    gate_threshold, gate_rows, gate_pass = choose_verifier_gate(
        "unit-gate", gate_attack, gate_benign, gate_scores, 0.5
    )
    assert gate_pass and np.isclose(gate_threshold, 0.1)
    assert sum(bool(row.get("selected", False)) for row in gate_rows) == 1
    assert all(int(row["report_rows_used"]) == 0 for row in gate_rows)
    print(
        json.dumps(
            {
                "status": "CKBM_CONTRACT_UNIT_PASS",
                "vendor": vendor,
                "tabm_shape": list(logits.shape),
                "finite_loss": float(loss.detach()),
                "causal_audit": audit,
                "duplicate_target_event_rejected": duplicate_rejected,
                "exact_gate_frontier_pass": gate_pass,
                "exact_gate_threshold": gate_threshold,
            },
            indent=2,
        )
    )


def fit_smoke(args: argparse.Namespace) -> None:
    """Bounded real-data fit-only smoke; never reads report canaries."""
    started = time.time()
    x_by_role, frames, _input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    table, role_audit = ckbl.legal_fit_table(frames, int(args.smoke_max_recorded_index))
    final_manifest, _manifest_hash = ckbl.load_final_holdout()
    ckbl.assert_scope(table, final_manifest)
    blocked, _blocked_audit = ckbl.known_nonfit_target_blocks(frames, table)
    matrices, row_audit, _cache = ckbl.feature_matrices(
        table,
        frames,
        x_by_role,
        "prefix",
        int(args.seed),
        state_blocked_rows=blocked,
    )
    x = matrices["C1_207_upper_bound"]
    if not np.isfinite(x).all() or len(np.unique(table["y"])) != 2:
        raise RuntimeError("real-data fit smoke lacks finite two-class data")
    pseudo_records = [
        ckbj.Record(
            uid=str(row.row_uid),
            role=str(row.role),
            m1_phase="fit",
            source=str(row.source_group),
            recorded_index=int(row.recorded_index),
            event_position=int(row.recorded_index),
            label=int(row.y),
            attack_family=str(row.attack_label),
            device_family=str(row.device_family),
            source_family=str(row.get("source_family", "NA")),
            c1_score=0.0,
            episode_id="",
        )
        for _, row in table.iterrows()
    ]
    base = {record.uid: x[index] for index, record in enumerate(pseudo_records)}
    transformer, preprocess = fit_preprocessor(pseudo_records, base, int(args.seed))
    global_map = transformed_map(transformer, pseudo_records, base)
    csr_map, causal = causal_source_relative_map(pseudo_records, global_map, "fit")
    sampled_indices, weights, weight_audit, occurrence_counts = balanced_training_sample(
        pseudo_records, int(args.seed)
    )
    unique_x = stack_map(pseudo_records, csr_map)
    unique_y = np.asarray([record.label for record in pseudo_records], dtype=np.int64)
    model = TabMClassifier(
        415,
        int(args.seed),
        int(args.smoke_epochs),
        int(args.batch_size),
        int(args.threads),
        min(4, int(args.tabm_k)),
        min(32, int(args.tabm_width)),
        2,
    ).fit(
        unique_x[sampled_indices],
        unique_y[sampled_indices],
        weights,
    )
    score = model.predict_proba(unique_x)
    if not np.isfinite(score).all():
        raise RuntimeError("real-data fit smoke produced nonfinite scores")
    payload = {
        "status": "CKBM_REAL_FIT_SMOKE_PASS",
        "formal_claim": False,
        "report_rows_used": 0,
        "development_canary_rows_used": 0,
        "rows": len(table),
        "attack_rows": int(table["y"].sum()),
        "benign_rows": int((1 - table["y"]).sum()),
        "sources": int(table["source_group"].nunique()),
        "support_families": int(table.loc[table["y"].eq(1), "attack_label"].nunique()),
        "family_balanced_training_occurrences": int(len(sampled_indices)),
        "all_unique_fit_rows_sampled": bool(len(occurrence_counts) == len(pseudo_records)),
        "sampling_audit": weight_audit,
        "frontend_alignment_pass": bool(all(row.get("alignment_ok", False) for row in row_audit)),
        "role_audit": role_audit.to_dict(orient="records"),
        "preprocessing": preprocess,
        "causal": causal,
        "loss_first": model.history[0]["weighted_cross_entropy"],
        "loss_last": model.history[-1]["weighted_cross_entropy"],
        "model_sha256": model.model_hash(),
        "scores_sha256": sha256_array(score),
        "finite_scores": True,
        "seconds": time.time() - started,
    }
    if args.out:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        dump_json(Path(args.out) / "fit_smoke.json", payload)
        pd.DataFrame(model.history).to_csv(Path(args.out) / "fit_smoke_loss.csv", index=False)
    print(json.dumps(json_ready(payload), indent=2))


def dry_run(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            {
                "status": "CKBM_DRY_RUN",
                "issue": ISSUE,
                "primary": PRIMARY,
                "seed": int(args.seed),
                "held_values": args.held_values.split(","),
                "vendor": validate_vendor(),
                "candidates": [spec.__dict__ for spec in BACKENDS],
                "paths": {
                    "t0_root": str(args.t0_root),
                    "report_t0_extension": str(args.report_t0_extension),
                    "c1_cache": str(args.c1_cache),
                    "c1_report_extension": str(args.c1_report_extension),
                },
                "formal_job": "result-producing attack preservation plus strict held-family evaluation",
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["contract-unit", "fit-smoke", "dry-run", "formal", "finalize-existing"],
        default="dry-run",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--t0-root", type=Path, default=DEFAULT_T0)
    parser.add_argument("--report-t0-extension", type=Path, default=DEFAULT_REPORT_EXTENSION)
    parser.add_argument("--c1-plan", type=Path, default=DEFAULT_C1_PLAN)
    parser.add_argument("--c1-targets", type=Path, default=DEFAULT_C1_TARGETS)
    parser.add_argument("--c1-cache", type=Path, default=DEFAULT_C1_CACHE)
    parser.add_argument("--c1-report-extension", type=Path, default=DEFAULT_C1_REPORT_EXTENSION)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument("--epochs", type=int, default=48)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--tabm-k", type=int, default=16)
    parser.add_argument("--tabm-width", type=int, default=256)
    parser.add_argument("--tabm-blocks", type=int, default=3)
    parser.add_argument("--extra-trees", type=int, default=384)
    parser.add_argument("--smoke-max-recorded-index", type=int, default=300000)
    parser.add_argument("--smoke-epochs", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "contract-unit":
        contract_unit(args)
    elif args.mode == "fit-smoke":
        fit_smoke(args)
    elif args.mode == "formal":
        run_formal(args)
    elif args.mode == "finalize-existing":
        finalize_existing(args)
    else:
        dry_run(args)


if __name__ == "__main__":
    main()
