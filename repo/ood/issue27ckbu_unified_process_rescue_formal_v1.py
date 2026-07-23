"""CKBU: unified causal process evidence for attack rescue.

This experiment does not claim that CKBQ already solved open-world IDS.  It
keeps the frozen CKBQ normal-consensus output as a measured (NO_GO) baseline
and asks one result-producing question: can a *single*, dataset-neutral causal
process representation recover attacks without destroying the multi-held OOD
signal?

The 51-dimensional input is decoded by TShark for every dataset and contains
only current-packet fields and source-local past state.  It contains no source
identity, dataset identity, labels, or connection-final fields unavailable at
the scoring instant.  One shared process head is trained from every legal
Gotham support_train row, legal Gotham/auxiliary benign fit rows, and a frozen
ToN-IoT Scan/Password process-support pilot.  There is no per-family expert.

The registered decision is asymmetric and uses no score addition:

    hard = frozen_CKBQ_hard OR strong_process_attack_evidence

Thus the process head can rescue both CKBQ suppressions and C1 false negatives.
Its threshold is selected only from support_val attacks plus source-disjoint
benign select data.  Report rows are scored with fixed weights/thresholds,
review remains zero, and every strict held family is excluded from every fit
and select scope.
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
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.preprocessing import QuantileTransformer


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbm_tabm_causal_source_calibration_v1 as ckbm  # noqa: E402
import issue27ckbo_mature_afterimage_transfer_v1 as ckbo  # noqa: E402
import issue27ckbq_causal_minirocket_consensus_v1 as ckbq  # noqa: E402
import issue27ckbu_unified_tshark_causal_frontend_v1 as frontend  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD  # noqa: E402


ISSUE = "issue27ckbu_unified_process_rescue_formal_v1_2026-07-23"
ROOT = ckbo.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
SEED = 27
BASELINE = "M1-FrozenCKBQ"
EXTRA_HEAD = "H1-ExtraTreesProcessHead"
TABM_HEAD = "H2-TabMProcessHead"
EXTRA_C1OR = "A1-C1ORExtraTreesProcess"
EXTRA_RESCUE = "A2-CKBQ-ExtraTreesRescue"
TABM_C1OR = "A3-C1ORTabMProcess"
PRIMARY = "M4-CKBQ-TabMProcessRescue"
PROCESS_HEADS = (EXTRA_HEAD, TABM_HEAD)
ALL_CANDIDATES = (
    "M0-C1",
    BASELINE,
    EXTRA_C1OR,
    EXTRA_RESCUE,
    TABM_C1OR,
    PRIMARY,
)


@dataclass(frozen=True)
class Gate:
    candidate: str
    threshold: float
    support_process_recall: float
    support_c1_recall: float
    benign_select_process_hard_rate: float
    constraint_pass: bool


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def dump_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(ckbm.json_ready(value), indent=2, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for row in rows:
        for name in row:
            if name not in fields:
                fields.append(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unique(records: Iterable[ckbj.Record]) -> list[ckbj.Record]:
    result: list[ckbj.Record] = []
    seen: set[str] = set()
    for record in records:
        if record.uid in seen:
            continue
        seen.add(record.uid)
        result.append(record)
    return result


def stack(records: list[ckbj.Record], features: dict[str, np.ndarray]) -> np.ndarray:
    if not records:
        return np.zeros((0, len(frontend.FEATURE_NAMES)), dtype=np.float32)
    missing = [record.uid for record in records if record.uid not in features]
    if missing:
        raise RuntimeError(f"unified feature coverage missing: {missing[:5]}")
    value = np.vstack([features[record.uid] for record in records]).astype(np.float32)
    if value.shape != (len(records), len(frontend.FEATURE_NAMES)):
        raise RuntimeError(f"unified feature shape drift: {value.shape}")
    if not np.isfinite(value).all():
        raise RuntimeError("nonfinite unified causal feature")
    return value


class UnifiedFeatureStore:
    def __init__(
        self,
        gotham_manifest: Path,
        gotham_cache: Path,
        auxiliary_manifest: Path,
        auxiliary_cache: Path,
    ) -> None:
        self.gotham_cache = Path(gotham_cache)
        self.auxiliary_cache = Path(auxiliary_cache)
        self.gotham = self._manifest(Path(gotham_manifest), "source_group")
        self.auxiliary = self._manifest(Path(auxiliary_manifest), "source_group")
        self.loaded: dict[tuple[str, str], dict[int, np.ndarray]] = {}

    @staticmethod
    def _manifest(path: Path, key: str) -> dict[str, dict[str, str]]:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if frame[key].duplicated().any():
            raise RuntimeError(f"duplicate unified cache source: {path}")
        if "raw_label_column_read" in frame:
            value = frame["raw_label_column_read"].astype(str).str.lower()
            if value.isin({"true", "1", "yes"}).any():
                raise RuntimeError(f"unified cache manifest read labels: {path}")
        return {str(row[key]): row.to_dict() for _, row in frame.iterrows()}

    def _source(self, source: str, auxiliary: bool) -> dict[int, np.ndarray]:
        kind = "aux" if auxiliary else "gotham"
        cache_key = (kind, source)
        if cache_key in self.loaded:
            return self.loaded[cache_key]
        table = self.auxiliary if auxiliary else self.gotham
        root = self.auxiliary_cache if auxiliary else self.gotham_cache
        if source not in table:
            raise RuntimeError(f"source absent from unified cache manifest: {kind}: {source}")
        key = str(table[source]["source_cache_key"])
        path = root / f"{key}.npz"
        if not path.is_file():
            raise FileNotFoundError(path)
        with np.load(path, allow_pickle=False) as values:
            names = values["feature_names"].astype(str).tolist()
            matrix = np.asarray(values["causal_features"], dtype=np.float32)
            indices = np.asarray(
                values["target_row" if auxiliary else "recorded_index"], dtype=np.int64
            )
        if names != frontend.FEATURE_NAMES or matrix.shape != (
            len(indices),
            len(frontend.FEATURE_NAMES),
        ):
            raise RuntimeError(f"unified cache schema drift: {path}: {matrix.shape}")
        if len(set(indices.tolist())) != len(indices):
            raise RuntimeError(f"duplicate target index in unified cache: {path}")
        result = {int(index): row for index, row in zip(indices, matrix)}
        self.loaded[cache_key] = result
        return result

    def add(self, records: Iterable[ckbj.Record], target: dict[str, np.ndarray]) -> None:
        for record in records:
            source = self._source(record.source, record.role.startswith("aux_"))
            if int(record.recorded_index) not in source:
                raise RuntimeError(
                    f"unified target absent: {record.source}:{record.recorded_index}:{record.uid}"
                )
            target[record.uid] = source[int(record.recorded_index)]


def auxiliary_records(plan_path: Path) -> dict[str, list[ckbj.Record]]:
    plan = pd.read_csv(Path(plan_path), dtype=str, keep_default_na=False)
    result: dict[str, list[ckbj.Record]] = defaultdict(list)
    for row in plan.itertuples(index=False):
        count = int(row.target_rows)
        records = ckbo.make_aux_records(
            str(row.source_group), str(row.role), count, str(row.device_family)
        )
        result[str(row.role)].extend(records)
    counts = {key: len(value) for key, value in result.items()}
    if counts != {"aux_fit": 6_600, "aux_select": 3_000, "aux_report": 9_000}:
        raise RuntimeError(f"auxiliary role count drift: {counts}")
    return dict(result)


def ton_records(path: Path) -> tuple[dict[str, list[ckbj.Record]], dict[str, np.ndarray], dict[str, Any]]:
    with np.load(Path(path), allow_pickle=False) as values:
        names = values["feature_names"].astype(str).tolist()
        matrix = np.asarray(values["causal_features"], dtype=np.float32)
        columns = {
            name: values[name].astype(str)
            for name in ("record_id", "role", "source_file", "mechanism_family")
        }
        labels = np.asarray(values["label"], dtype=np.int64)
        positions = np.asarray(values["target_event_position_within_capture"], dtype=np.int64)
    if names != frontend.FEATURE_NAMES or matrix.shape[1] != len(frontend.FEATURE_NAMES):
        raise RuntimeError("ToN unified feature schema differs from Gotham")
    records: dict[str, list[ckbj.Record]] = defaultdict(list)
    feature_map: dict[str, np.ndarray] = {}
    for index in range(len(matrix)):
        role = str(columns["role"][index])
        label = int(labels[index])
        source = str(columns["source_file"][index])
        uid = f"ton:{columns['record_id'][index]}"
        record = ckbj.Record(
            uid=uid,
            role=role,
            m1_phase="fit" if role.endswith("fit") else "select",
            source=source,
            recorded_index=int(positions[index]),
            event_position=int(positions[index]),
            label=label,
            attack_family=(
                f"ToN-{columns['mechanism_family'][index]}" if label else "benign"
            ),
            device_family="ton-iot-external",
            source_family="ton-iot-external",
            # No frozen C1 cache exists for ToN normal select.  Treating every
            # row as process-gate eligible is the conservative false-positive
            # accounting choice.
            c1_score=1.0,
            episode_id=source,
        )
        records[role].append(record)
        feature_map[uid] = matrix[index]
    counts = {key: len(value) for key, value in records.items()}
    expected = {"aux_normal_fit": 4_000, "aux_normal_select": 4_000, "aux_process_fit": 4_000}
    if counts != expected:
        raise RuntimeError(f"ToN materialized role count drift: {counts}")
    return dict(records), feature_map, {
        "cache_sha256": sha256_file(Path(path)),
        "rows": len(matrix),
        "roles": counts,
        "fit_select_sources_disjoint": not (
            {record.source for record in records["aux_normal_fit"]}
            & {record.source for record in records["aux_normal_select"]}
        ),
        "reserved_injection_mitm_model_rows": 0,
    }


def row_weights(records: list[ckbj.Record]) -> tuple[np.ndarray, list[dict[str, Any]]]:
    groups: dict[tuple[int, str], list[int]] = defaultdict(list)
    for index, record in enumerate(records):
        key = record.attack_family if record.label else record.source
        groups[(record.label, key)].append(index)
    labels = {label for label, _ in groups}
    if labels != {0, 1}:
        raise RuntimeError("process training requires both attack and benign groups")
    weights = np.zeros(len(records), dtype=np.float64)
    audit: list[dict[str, Any]] = []
    for label in (0, 1):
        label_groups = {key: value for (y, key), value in groups.items() if y == label}
        for key, indices in sorted(label_groups.items()):
            mass = 0.5 / len(label_groups)
            weights[np.asarray(indices, dtype=np.int64)] = mass / len(indices)
            audit.append(
                {
                    "label": label,
                    "balance_unit": "attack_family" if label else "benign_source",
                    "group": key,
                    "unique_rows": len(indices),
                    "rows_visited_per_epoch": len(indices),
                    "all_unique_rows_covered": True,
                    "normalized_group_mass": mass,
                }
            )
    weights *= len(weights) / weights.sum()
    if not np.isfinite(weights).all() or np.any(weights <= 0):
        raise RuntimeError("invalid process training weights")
    return weights.astype(np.float32), audit


def fit_preprocessor(
    records: list[ckbj.Record], features: dict[str, np.ndarray], seed: int
) -> tuple[QuantileTransformer, dict[str, Any]]:
    x = stack(records, features)
    rng = np.random.default_rng(int(seed))
    # Deterministic tiny jitter only breaks ties in discrete counters.  It is
    # fit-only and never touches select/report rows.
    jitter = rng.normal(0.0, 1e-6, x.shape).astype(np.float32)
    transformer = QuantileTransformer(
        n_quantiles=max(10, min(500, len(x) // 30)),
        output_distribution="normal",
        subsample=1_000_000_000,
        random_state=int(seed),
    ).fit(x + jitter)
    return transformer, {
        "fit_rows": len(records),
        "fit_sources": len({record.source for record in records}),
        "fit_attack_rows": sum(record.label == 1 for record in records),
        "fit_benign_rows": sum(record.label == 0 for record in records),
        "select_rows_used": 0,
        "report_rows_used": 0,
        "feature_dim": x.shape[1],
        "identity_features": 0,
        "fit_only": True,
        "quantiles_sha256": ckbm.sha256_array(transformer.quantiles_),
    }


def transformed(
    transformer: QuantileTransformer,
    records: list[ckbj.Record],
    features: dict[str, np.ndarray],
) -> np.ndarray:
    value = transformer.transform(stack(records, features))
    return np.clip(np.nan_to_num(value, nan=0.0, posinf=8.0, neginf=-8.0), -8.0, 8.0).astype(
        np.float32
    )


def choose_process_gate(
    candidate: str,
    support_val: list[ckbj.Record],
    benign_select: list[ckbj.Record],
    scores: dict[str, float],
    c1_threshold: float,
) -> tuple[Gate, list[dict[str, Any]]]:
    if not support_val or not benign_select:
        raise RuntimeError("process gate requires legal attack and benign select rows")
    attack = np.asarray([scores[record.uid] for record in support_val], dtype=np.float64)
    benign = np.asarray([scores[record.uid] for record in benign_select], dtype=np.float64)
    c1 = np.asarray([record.c1_score >= c1_threshold for record in support_val], dtype=bool)
    if not np.isfinite(attack).all() or not np.isfinite(benign).all():
        raise RuntimeError("nonfinite process gate scores")
    lower = float(np.nextafter(min(float(attack.min()), float(benign.min())), -np.inf))
    thresholds = sorted({lower, *(float(value) for value in attack.tolist())})
    rows: list[dict[str, Any]] = []
    c1_recall = float(np.mean(c1))
    for threshold in thresholds:
        hard = attack >= threshold
        family_ok = True
        for family in sorted({record.attack_family for record in support_val}):
            mask = np.asarray([record.attack_family == family for record in support_val])
            if int(mask.sum()) >= 3:
                reference = float(np.mean(c1[mask]))
                family_ok &= float(np.mean(hard[mask])) >= reference - 0.02
        rows.append(
            {
                "candidate": candidate,
                "process_threshold": threshold,
                "support_val_process_recall": float(np.mean(hard)),
                "support_val_c1_recall": c1_recall,
                "benign_select_process_hard_rate": float(np.mean(benign >= threshold)),
                "eligible": bool(float(np.mean(hard)) >= c1_recall - 0.005 and family_ok),
                "support_val_rows_used": len(support_val),
                "benign_select_rows_used": len(benign_select),
                "report_rows_used": 0,
                "selection_order": "attack_preservation_then_minimum_benign_process_hard",
            }
        )
    eligible = [row for row in rows if row["eligible"]]
    if eligible:
        selected = min(
            eligible,
            key=lambda row: (
                row["benign_select_process_hard_rate"],
                -row["process_threshold"],
            ),
        )
        passed = True
    else:
        selected = max(
            rows,
            key=lambda row: (
                row["support_val_process_recall"],
                -row["benign_select_process_hard_rate"],
            ),
        )
        passed = False
    selected["selected"] = True
    selected["gate_constraint_pass"] = passed
    gate = Gate(
        candidate,
        float(selected["process_threshold"]),
        float(selected["support_val_process_recall"]),
        c1_recall,
        float(selected["benign_select_process_hard_rate"]),
        passed,
    )
    return gate, rows


def bool_values(series: pd.Series) -> np.ndarray:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).to_numpy(dtype=bool)
    mapped = series.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    if mapped.isna().any():
        raise RuntimeError(f"invalid frozen boolean values: {sorted(series[mapped.isna()].unique())}")
    return mapped.to_numpy(dtype=bool)


def frozen_prediction_maps(path: Path) -> tuple[dict[tuple[str, str], bool], dict[tuple[str, str], bool]]:
    frame = pd.read_csv(Path(path), compression="infer")
    required = {"held_value", "uid", "hard__M0-C1", f"hard__{ckbq.PRIMARY}"}
    if not required.issubset(frame):
        raise RuntimeError(f"frozen CKBQ prediction schema missing: {sorted(required-set(frame))}")
    keys = list(zip(frame["held_value"].astype(str), frame["uid"].astype(str)))
    if len(set(keys)) != len(keys):
        raise RuntimeError("duplicate frozen CKBQ prediction key")
    c1 = bool_values(frame["hard__M0-C1"])
    base = bool_values(frame[f"hard__{ckbq.PRIMARY}"])
    return dict(zip(keys, c1)), dict(zip(keys, base))


def base_decisions(
    protocol: str,
    records: list[ckbj.Record],
    c1_map: dict[tuple[str, str], bool],
    base_map: dict[tuple[str, str], bool],
    c1_threshold: float,
) -> tuple[np.ndarray, np.ndarray]:
    keys = [(protocol, record.uid) for record in records]
    missing = [key for key in keys if key not in base_map]
    if missing:
        raise RuntimeError(f"frozen CKBQ prediction coverage missing: {missing[:5]}")
    c1 = np.asarray([record.c1_score >= c1_threshold for record in records], dtype=bool)
    frozen_c1 = np.asarray([c1_map[key] for key in keys], dtype=bool)
    if not np.array_equal(c1, frozen_c1):
        raise RuntimeError(f"fresh C1 decisions differ from frozen CKBQ: {protocol}")
    return c1, np.asarray([base_map[key] for key in keys], dtype=bool)


def run_protocol(
    held: str | None,
    args: argparse.Namespace,
    x_by_role: dict[str, np.ndarray],
    report_frames: dict[str, pd.DataFrame],
    model_frames: dict[str, pd.DataFrame],
    t0: Any,
    position_cache: dict[str, dict[int, int]],
    store: UnifiedFeatureStore,
    aux: dict[str, list[ckbj.Record]],
    ton: dict[str, list[ckbj.Record]],
    ton_features: dict[str, np.ndarray],
    frozen_c1: dict[tuple[str, str], bool],
    frozen_base: dict[tuple[str, str], bool],
) -> dict[str, list[dict[str, Any]]]:
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
    if held is None and (len(sets["fit_attack"]) != 385 or len(sets["select_attack"]) != 69):
        raise RuntimeError("global support cardinality drift")
    if held == ckbo.AUX_HELD_FAMILY:
        sets["report"] = list(aux["aux_report"])
    aux_fit = [record for record in aux["aux_fit"] if held is None or record.device_family != held]
    aux_select = [
        record for record in aux["aux_select"] if held is None or record.device_family != held
    ]
    fit_attack = list(sets["fit_attack"]) + list(ton["aux_process_fit"])
    fit_benign = list(sets["fit_benign"]) + aux_fit + list(ton["aux_normal_fit"])
    fit_records = unique([*fit_attack, *fit_benign])
    select_attack = list(sets["select_attack"])
    select_benign = (
        list(sets["select_benign"]) + aux_select + list(ton["aux_normal_select"])
    )
    report_records = list(sets["report"])
    scored = unique([*select_attack, *select_benign, *report_records])
    feature_map = dict(ton_features)
    store.add([record for record in unique([*fit_records, *scored]) if not record.uid.startswith("ton:")], feature_map)
    transformer, prep_audit = fit_preprocessor(fit_records, feature_map, int(args.seed))
    fit_x = transformed(transformer, fit_records, feature_map)
    all_x = transformed(transformer, scored, feature_map)
    labels = np.asarray([record.label for record in fit_records], dtype=np.int64)
    weights, balance_audit = row_weights(fit_records)

    model_specs = (
        ckbm.BackendSpec(EXTRA_HEAD, "extratrees", "unified_causal51", False),
        ckbm.BackendSpec(TABM_HEAD, "tabm", "unified_causal51", True),
    )
    scores: dict[str, dict[str, float]] = {}
    gates: dict[str, Gate] = {}
    selection_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    for spec in model_specs:
        model, history, model_hash = ckbm.fit_backend(
            spec, fit_x, labels, weights, args, int(args.seed)
        )
        probability = ckbm.backend_scores(model, all_x)
        score_map = {record.uid: float(value) for record, value in zip(scored, probability)}
        gate, frontier = choose_process_gate(
            spec.name,
            select_attack,
            select_benign,
            score_map,
            c1_threshold,
        )
        scores[spec.name] = score_map
        gates[spec.name] = gate
        selection_rows.extend(
            {
                **row,
                "held_value": protocol,
                "selected": bool(row.get("selected", False)),
                "gate_constraint_pass": gate.constraint_pass if row.get("selected") else math.nan,
            }
            for row in frontier
        )
        loss_rows.extend({**row, "candidate": spec.name, "held_value": protocol} for row in history)
        model_rows.append(
            {
                "candidate": spec.name,
                "held_value": protocol,
                "backend": "ExtraTrees" if spec.kind == "extratrees" else "official_TabM_v0.0.3",
                "shared_process_head": True,
                "per_family_experts": 0,
                "input_dim": fit_x.shape[1],
                "fit_rows": len(fit_records),
                "fit_attack_rows": len(fit_attack),
                "fit_benign_rows": len(fit_benign),
                "gotham_support_rows": len(sets["fit_attack"]),
                "ton_process_support_rows": len(ton["aux_process_fit"]),
                "report_rows_used": 0,
                "select_rows_used_for_fit": 0,
                "model_sha256": model_hash,
                "review_rate": 0.0,
            }
        )

    strict = (
        select_attack + [record for record in report_records if record.label == 1]
        if held is None
        else report_records
    )
    c1_hard, frozen_hard = base_decisions(
        protocol, strict, frozen_c1, frozen_base, c1_threshold
    )
    strict_index = {record.uid: index for index, record in enumerate(scored)}
    process_extra = np.asarray(
        [scores[EXTRA_HEAD][record.uid] >= gates[EXTRA_HEAD].threshold for record in strict]
    )
    process_tabm = np.asarray(
        [scores[TABM_HEAD][record.uid] >= gates[TABM_HEAD].threshold for record in strict]
    )
    decisions = {
        "M0-C1": c1_hard,
        BASELINE: frozen_hard,
        EXTRA_C1OR: c1_hard | process_extra,
        EXTRA_RESCUE: frozen_hard | process_extra,
        TABM_C1OR: c1_hard | process_tabm,
        PRIMARY: frozen_hard | process_tabm,
    }
    metrics: list[dict[str, Any]] = []
    families: list[dict[str, Any]] = []
    attack: list[dict[str, Any]] = []
    strict_rows: list[dict[str, Any]] = []
    for candidate in ALL_CANDIDATES:
        values, per_family = ckbj.metric_rows(
            candidate,
            "strict_leave" if held else "attack_preservation",
            protocol,
            strict,
            decisions[candidate],
            int(args.bootstrap_reps),
            int(args.seed),
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
                    int(args.bootstrap_reps),
                    int(args.seed),
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
                    int(args.bootstrap_reps),
                    int(args.seed),
                )
            )

    prediction_rows: list[dict[str, Any]] = []
    c1_all, base_all = base_decisions(
        protocol,
        [record for record in scored if not record.uid.startswith("ton:")],
        frozen_c1,
        frozen_base,
        c1_threshold,
    )
    base_by_uid = {
        record.uid: (bool(c1), bool(base))
        for record, c1, base in zip(
            [record for record in scored if not record.uid.startswith("ton:")], c1_all, base_all
        )
    }
    for record in scored:
        c1_value, base_value = base_by_uid.get(record.uid, (True, False))
        ex = scores[EXTRA_HEAD][record.uid] >= gates[EXTRA_HEAD].threshold
        ta = scores[TABM_HEAD][record.uid] >= gates[TABM_HEAD].threshold
        prediction_rows.append(
            {
                "held_value": protocol,
                "uid": record.uid,
                "role": record.role,
                "phase": record.m1_phase,
                "source_group": record.source,
                "device_family": record.device_family,
                "attack_family": record.attack_family,
                "label_metric_only": record.label,
                "c1_hard": c1_value,
                "frozen_ckbq_hard": base_value,
                "extra_process_score": scores[EXTRA_HEAD][record.uid],
                "extra_process_threshold": gates[EXTRA_HEAD].threshold,
                "tabm_process_score": scores[TABM_HEAD][record.uid],
                "tabm_process_threshold": gates[TABM_HEAD].threshold,
                "hard__M0-C1": c1_value,
                f"hard__{BASELINE}": base_value,
                f"hard__{EXTRA_C1OR}": c1_value or ex,
                f"hard__{EXTRA_RESCUE}": base_value or ex,
                f"hard__{TABM_C1OR}": c1_value or ta,
                f"hard__{PRIMARY}": base_value or ta,
                "review": False,
            }
        )

    support_usage = []
    if held is None:
        for candidate in PROCESS_HEADS:
            epochs = 1 if candidate == EXTRA_HEAD else int(args.epochs)
            support_usage.extend(
                {
                    "candidate": candidate,
                    "uid": record.uid,
                    "source_group": record.source,
                    "attack_family": record.attack_family,
                    "epochs": epochs,
                    "times_used": epochs,
                    "used_at_least_once_each_epoch": True,
                }
                for record in sets["fit_attack"]
            )
    held_removed = {
        "held_value": protocol,
        "held_family": held or "NONE",
        "core_fit_attack_rows": len(sets["fit_attack"]),
        "core_fit_benign_rows": len(sets["fit_benign"]),
        "core_select_attack_rows": len(sets["select_attack"]),
        "core_select_benign_rows": len(sets["select_benign"]),
        "aux_fit_rows": len(aux_fit),
        "aux_select_rows": len(aux_select),
        "ton_fit_rows": len(ton["aux_process_fit"]) + len(ton["aux_normal_fit"]),
        "ton_select_rows": len(ton["aux_normal_select"]),
        "report_fit_use_count": 0,
        "report_select_use_count": 0,
        "review_rate": 0.0,
    }
    for row in data_audit + c1_audit:
        row["protocol_run"] = protocol
    return {
        "metrics": metrics,
        "family_metrics": families,
        "attack_summary": attack,
        "strict_summary": strict_rows,
        "selection": selection_rows,
        "models": model_rows,
        "loss": loss_rows,
        "support_usage": support_usage,
        "balance": [{**row, "held_value": protocol} for row in balance_audit],
        "preprocess": [{**prep_audit, "held_value": protocol}],
        "scope": [held_removed],
        "data_audit": data_audit,
        "c1_audit": c1_audit,
        "predictions": prediction_rows,
    }


def one(frame: pd.DataFrame, column: str, **where: Any) -> float | None:
    part = frame
    for key, value in where.items():
        part = part.loc[part[key].eq(value)] if key in part else part.iloc[0:0]
    return None if part.empty else float(part.iloc[0][column])


def scientific_decision(
    attack: pd.DataFrame,
    strict: pd.DataFrame,
    selection: pd.DataFrame,
    support: pd.DataFrame,
    scope: pd.DataFrame,
) -> dict[str, Any]:
    overall = one(
        attack, "delta_vs_c1_pp", candidate=PRIMARY, metric="overall_attack_hard_recall"
    )
    major = attack.loc[
        attack.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)
        & attack.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")
        & pd.to_numeric(attack.get("rows", 0), errors="coerce").fillna(0).ge(15)
    ]
    required = [
        "iotsim-ip-camera-street",
        "iotsim-predictive-maintenance",
        "iotsim-stream-consumer",
        "iotsim-hydraulic-system",
    ]
    rates: dict[str, float] = {}
    c1_rates: dict[str, float] = {}
    base_rates: dict[str, float] = {}
    for held in required:
        for target, candidate in (
            (rates, PRIMARY),
            (c1_rates, "M0-C1"),
            (base_rates, BASELINE),
        ):
            value = one(strict, "hard_rate", candidate=candidate, held_value=held)
            if value is not None:
                target[held] = value
    held_signal = bool(
        len(rates) == len(c1_rates) == len(base_rates) == len(required)
        and all(rates[value] <= 0.90 and rates[value] <= c1_rates[value] - 0.05 for value in required)
    )
    selected = selection.loc[
        selection.get("candidate", pd.Series(dtype=str)).eq(TABM_HEAD)
        & selection.get("held_value", pd.Series(dtype=str)).eq("GLOBAL_ATTACK_PRESERVATION")
        & selection.get("selected", pd.Series(False, index=selection.index)).astype(bool)
    ]
    checks = {
        "required_metrics_missing": overall is None or len(rates) != len(required),
        "overall_attack_drop_over_0_5pp": overall is not None and overall < -0.5,
        "major_attack_family_drop_over_2pp": bool(
            not major.empty
            and (pd.to_numeric(major["delta_vs_c1_pp"], errors="coerce") < -2.0).any()
        ),
        "multiheld_signal_missing": not held_signal,
        "process_gate_constraint_failed": bool(
            selected.empty
            or not selected.get("gate_constraint_pass", pd.Series(False)).fillna(False).astype(bool).all()
        ),
        "support_usage_incomplete": bool(
            len(support.loc[support["candidate"].eq(TABM_HEAD)]) != 385
            or not support.loc[support["candidate"].eq(TABM_HEAD)][
                "used_at_least_once_each_epoch"
            ].astype(bool).all()
        ),
        "report_or_held_used_in_fit_select": bool(
            scope.empty
            or pd.to_numeric(scope["report_fit_use_count"], errors="coerce").fillna(1).sum()
            or pd.to_numeric(scope["report_select_use_count"], errors="coerce").fillna(1).sum()
        ),
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
        "held_frozen_ckbq_hard_rates": base_rates,
        "all_required_held_improve_5pp_and_at_most_90pct": held_signal,
        "review_rate": 0.0,
        "single_seed_scope": "route signal only; multi-seed and final held data remain required",
    }


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    if int(args.seed) != SEED:
        raise RuntimeError("first CKBU formal run is preregistered for seed 27 only")
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.use_deterministic_algorithms(True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    allowed = {
        "resource_usage.txt",
        "slurm_identity.txt",
        "slurm_job_at_start.txt",
        "gotham_causal_cache",
        "auxiliary_causal_cache",
        "source_runtime",
        "ckbu_gotham_source_plan.csv",
        "ckbu_gotham_plan.json",
        "ckbu_gotham_unified_causal_manifest.csv",
        "ckbu_gotham_unified_causal_ready.json",
        "ckbu_auxiliary_source_plan.csv",
        "ckbu_auxiliary_plan.json",
        "ckbu_auxiliary_unified_causal_manifest.csv",
        "ckbu_auxiliary_unified_causal_ready.json",
        "ckbu_ton_raw_pcap_pilot_manifest.csv",
        "ckbu_ton_raw_pcap_pilot_ready.json",
        "ckbu_ton_raw_pcap_materialization_audit.csv",
        "ckbu_ton_raw_pcap_pilot_causal_samples.npz",
        "ckbu_ton_raw_pcap_pilot_causal_ready.json",
    }
    unexpected = [path.name for path in out.iterdir() if path.name not in allowed]
    if unexpected:
        raise RuntimeError(f"refusing mixed CKBU output directory: {unexpected[:5]}")
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
    if protocols != [
        None,
        "iotsim-ip-camera-street",
        "iotsim-predictive-maintenance",
        "iotsim-stream-consumer",
        "iotsim-hydraulic-system",
    ]:
        raise RuntimeError(f"CKBU protocol boundary drift: {protocols}")
    store = UnifiedFeatureStore(
        Path(args.gotham_manifest),
        Path(args.gotham_cache),
        Path(args.auxiliary_manifest),
        Path(args.auxiliary_cache),
    )
    aux = auxiliary_records(Path(args.auxiliary_plan))
    ton, ton_features, ton_audit = ton_records(Path(args.ton_cache))
    frozen_c1, frozen_base = frozen_prediction_maps(Path(args.ckbq_predictions))
    position_cache: dict[str, dict[int, int]] = {}
    results = [
        run_protocol(
            held,
            args,
            x_by_role,
            report_frames,
            model_frames,
            t0,
            position_cache,
            store,
            aux,
            ton,
            ton_features,
            frozen_c1,
            frozen_base,
        )
        for held in protocols
    ]

    def table(key: str) -> pd.DataFrame:
        return pd.DataFrame([{**row, "seed": SEED} for result in results for row in result[key]])

    outputs = {
        "ckbu_all_metrics.csv": table("metrics"),
        "ckbu_per_attack_family_metrics.csv": table("family_metrics"),
        "attack_preservation_summary.csv": table("attack_summary"),
        "strict_level2_summary.csv": table("strict_summary"),
        "ckbu_candidate_selection.csv": table("selection"),
        "ckbu_model_audit.csv": table("models"),
        "ckbu_loss_curves.csv": table("loss"),
        "ckbu_support_training_usage.csv": table("support_usage"),
        "ckbu_group_balance_audit.csv": table("balance"),
        "ckbu_preprocessing_audit.csv": table("preprocess"),
        "ckbu_protocol_scope_audit.csv": table("scope"),
        "ckbu_role_usage_audit.csv": table("data_audit"),
        "ckbu_c1_fit_select_audit.csv": table("c1_audit"),
        "ckbu_permanent_report_only_audit.csv": pd.DataFrame(permanent),
        "ckbu_frozen_model_scope_audit.csv": pd.DataFrame(frozen_scope),
        "ckbu_review_audit.csv": pd.DataFrame(
            [{"seed": SEED, "review_count": 0, "review_rate": 0.0, "review_enabled": False}]
        ),
        "ckbu_negative_sampling_audit.csv": pd.DataFrame(
            [{"seed": SEED, "negative_sampling_used": False, "negative_samples": 0}]
        ),
    }
    for filename, frame in outputs.items():
        frame.to_csv(out / filename, index=False)
    predictions = table("predictions")
    predictions.to_csv(
        out / "ckbu_record_predictions.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 6, "mtime": 0},
    )
    outcome = scientific_decision(
        outputs["attack_preservation_summary.csv"],
        outputs["strict_level2_summary.csv"],
        outputs["ckbu_candidate_selection.csv"],
        outputs["ckbu_support_training_usage.csv"],
        outputs["ckbu_protocol_scope_audit.csv"],
    )
    dump_json(out / "ckbu_single_seed_go_no_go.json", outcome)
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "torch": torch.__version__,
        "tshark": os.environ.get("CKBU_TSHARK_VERSION", "recorded_by_launcher"),
        "seed": SEED,
        "commit_sha": os.environ.get("CKBU_COMMIT_SHA", ckbm.git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "wall_seconds": time.time() - started,
        "review_rate": 0.0,
        "gotham_manifest_sha256": sha256_file(Path(args.gotham_manifest)),
        "auxiliary_manifest_sha256": sha256_file(Path(args.auxiliary_manifest)),
        "ton_cache_sha256": ton_audit["cache_sha256"],
        "frozen_ckbq_predictions_sha256": sha256_file(Path(args.ckbq_predictions)),
        "base_t0_manifest_sha256": ckbo.sha256_file(
            Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
        ),
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
    }
    dump_json(out / "ckbu_environment.json", environment)
    dump_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "decision": outcome,
            "primary_candidate": PRIMARY,
            "candidates": ALL_CANDIDATES,
            "original_1m_split_modified": False,
            "frozen_ckbq_baseline_retrained": False,
            "review_rate": 0.0,
            "score_addition_used": False,
            "per_family_experts": 0,
            "unified_frontend": {
                "decoder": "TShark 4.6.6",
                "feature_dim": len(frontend.FEATURE_NAMES),
                "score_before_update": True,
                "source_local_past_only": True,
                "feature_available_time_recorded": True,
                "raw_label_column_read": False,
            },
            "fusion": "frozen CKBQ hard OR shared process attack evidence",
            "selection": "support_val attack preservation first; source-disjoint benign process hard second; report use zero",
            "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
            "final_held_unopened": ["iotsim-cooler-motor"],
            "ton_pilot": ton_audit,
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_extension_audit": c1_extension_audit,
            "environment": environment,
        },
    )
    write_text(
        out / "codex_readout.md",
        f"# CKBU seed 27\n\nScientific decision: `{outcome['decision']}`.  "
        "This is a route signal only.  The earlier CKBQ result was a NO_GO baseline, "
        "not adequate detection performance.  CKBU uses one shared causal process head, "
        "no family-specific experts, no report tuning, no score addition, and review=0.\n",
    )
    print(json.dumps({"status": "CKBU_FORMAL_COMPLETE", "decision": outcome["decision"], "out": str(out)}, indent=2))


def contract_unit() -> None:
    support = [
        ckbj.Record(f"a:{i}", "support_val", "select", "s", i, i, 1, "f", "d", "d", 1.0, "e")
        for i in range(4)
    ]
    benign = [
        ckbj.Record(f"b:{i}", "aux_select", "select", "n", i, i, 0, "benign", "n", "n", 1.0, "e")
        for i in range(4)
    ]
    values = {**{record.uid: 0.8 + i * 0.01 for i, record in enumerate(support)}, **{record.uid: 0.1 + i * 0.01 for i, record in enumerate(benign)}}
    gate, frontier = choose_process_gate("unit", support, benign, values, 0.5)
    if not gate.constraint_pass or gate.support_process_recall != 1.0 or gate.benign_select_process_hard_rate != 0.0:
        raise RuntimeError("exact process gate unit failed")
    c1 = np.asarray([True, False, True])
    base = np.asarray([False, False, True])
    process = np.asarray([False, True, False])
    if not np.array_equal(base | process, np.asarray([False, True, True])):
        raise RuntimeError("asymmetric OR rescue unit failed")
    print(
        json.dumps(
            {
                "status": "CKBU_FORMAL_CONTRACT_UNIT_PASS",
                "feature_dim": len(frontend.FEATURE_NAMES),
                "exact_gate_points": len(frontier),
                "score_addition_used": False,
                "shared_process_head": True,
                "per_family_experts": 0,
                "review_rate": 0.0,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["contract-unit", "dry-run", "formal"], default="dry-run")
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
    parser.add_argument("--gotham-manifest", type=Path, required=False)
    parser.add_argument("--gotham-cache", type=Path, required=False)
    parser.add_argument("--auxiliary-manifest", type=Path, required=False)
    parser.add_argument("--auxiliary-plan", type=Path, required=False)
    parser.add_argument("--auxiliary-cache", type=Path, required=False)
    parser.add_argument("--ton-cache", type=Path, required=False)
    parser.add_argument("--ckbq-predictions", type=Path, required=False)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=24)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--tabm-k", type=int, default=16)
    parser.add_argument("--tabm-width", type=int, default=192)
    parser.add_argument("--tabm-blocks", type=int, default=3)
    parser.add_argument("--extra-trees", type=int, default=500)
    parser.add_argument("--aux-rows-per-source", type=int, default=600)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "contract-unit":
        contract_unit()
    elif args.mode == "formal":
        required = (
            args.gotham_manifest,
            args.gotham_cache,
            args.auxiliary_manifest,
            args.auxiliary_plan,
            args.auxiliary_cache,
            args.ton_cache,
            args.ckbq_predictions,
        )
        if any(value is None for value in required):
            raise RuntimeError("formal mode requires all unified cache and frozen CKBQ paths")
        run_formal(args)
    else:
        print(
            json.dumps(
                {
                    "status": "CKBU_DRY_RUN",
                    "primary": PRIMARY,
                    "feature_dim": len(frontend.FEATURE_NAMES),
                    "fusion": "frozen CKBQ hard OR shared process attack evidence",
                    "formal_seed": SEED,
                    "review_rate": 0.0,
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
