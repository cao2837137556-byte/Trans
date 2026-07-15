"""CKBO: mature AfterImage transfer with legal benign-diversity extension.

This result-producing experiment keeps the frozen C1 detector as the high-
recall candidate anchor and asks a narrower, transferable question: can a
verifier built from the maintained Kitsune/AfterImage frontend suppress unseen
normal processes without sacrificing attacks?

The original strict 1M roles and the frozen CKBE/CKBI caches are read-only.
Fifteen previously unused predictive-maintenance benign PCAPs are materialized
into a separate source-disjoint extension manifest.  They never alter the 1M
split.  Stream, hydraulic and cooler-motor are permanently excluded from every
fit/select/preprocessing/gate scope and are read only after all choices freeze.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import re
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
import sklearn
from sklearn.preprocessing import QuantileTransformer


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ab_gotham_kitsune115_frontend_feasibility as ckab  # noqa: E402
import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckbi_tgn_report_only_cache_extension_v1 as ckbi  # noqa: E402
import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as ckbj  # noqa: E402
import issue27ckbm_tabm_causal_source_calibration_v1 as ckbm  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402
from issue27ckbf_tgn_m1_preflight_v1 import HELD, T0Cache  # noqa: E402


ISSUE = "issue27ckbo_mature_afterimage_transfer_v1_2026-07-15"
ROOT = cko.ROOT
DEFAULT_OUT = ROOT / "runs" / ISSUE
DEFAULT_T0 = ckbj.DEFAULT_T0
DEFAULT_REPORT_EXTENSION = ckbj.DEFAULT_REPORT_EXTENSION
DEFAULT_C1_PLAN = ckbj.DEFAULT_C1_PLAN
DEFAULT_C1_TARGETS = ckbj.DEFAULT_C1_TARGETS
DEFAULT_C1_CACHE = ckbj.DEFAULT_C1_CACHE
DEFAULT_C1_REPORT_EXTENSION = ckbj.DEFAULT_C1_REPORT_EXTENSION
DEFAULT_ZIP = cko.GOTHAM_ZIP
SEED = 27
PRIMARY = "M3-AfterImageContrast-Aux"
PERMANENT_REPORT_ONLY = (
    "iotsim-stream-consumer",
    "iotsim-hydraulic-system",
    "iotsim-cooler-motor",
)
AUX_FAMILY = "iotsim-predictive-maintenance"
AUX_PREFIX = "raw/benign/iotsim-predictive-maintenance-"
WARMUP_PACKETS = 500
MODEL_READY_PER_SOURCE = 2000
FIT_SOURCE_COUNT = 10


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    representation: str
    use_auxiliary_benign: bool
    primary: bool = False


CANDIDATES = (
    CandidateSpec("M1-AfterImage115-NoAux", "raw115", False),
    CandidateSpec("M2-AfterImage115-Aux", "raw115", True),
    CandidateSpec(PRIMARY, "multiscale_contrast115", True, True),
    CandidateSpec("A1-AfterImageContrast-NoAux", "multiscale_contrast115", False),
)


@dataclass
class AuxiliaryData:
    records_fit: list[ckbj.Record]
    records_select: list[ckbj.Record]
    raw: dict[str, np.ndarray]
    contrast: dict[str, np.ndarray]
    manifest: pd.DataFrame
    manifest_sha256: str
    ready: dict[str, Any]


def write_text_lf(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def dump_json(path: Path, payload: Any) -> None:
    write_text_lf(path, json.dumps(ckbm.json_ready(payload), indent=2, sort_keys=True) + "\n")


def write_csv_lf(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_rank(text: str) -> str:
    return hashlib.sha256(f"ckbo|{SEED}|{text}".encode("utf-8")).hexdigest()


def source_name(member: str) -> str:
    return Path(member).stem


def afterimage_schema() -> tuple[list[str], str]:
    headers = ckab.RestoredNetStat115().headers()
    if len(headers) != 115 or len(set(headers)) != 115:
        raise RuntimeError("AfterImage115 schema drift")
    digest = hashlib.sha256(("\n".join(headers) + "\n").encode("utf-8")).hexdigest()
    return headers, digest


def contrast_plan(headers: list[str]) -> tuple[list[tuple[int, int | None, str]], list[str]]:
    pattern = re.compile(r"^(MI_dir|HH_jit|HpHp|HH|H)_(5|3|1|0\.1|0\.01)_(.+)$")
    by_stat: defaultdict[tuple[str, str], dict[str, int]] = defaultdict(dict)
    for index, header in enumerate(headers):
        match = pattern.match(header)
        if not match:
            raise RuntimeError(f"unparsed AfterImage header: {header}")
        family, scale, stat = match.groups()
        by_stat[(family, stat)][scale] = index
    expected = {"5", "3", "1", "0.1", "0.01"}
    if len(by_stat) != 23 or any(set(values) != expected for values in by_stat.values()):
        raise RuntimeError("AfterImage multiscale groups drifted from 23 x 5")
    plan: list[tuple[int, int | None, str]] = []
    names: list[str] = []
    for (family, stat), values in sorted(by_stat.items()):
        plan.append((values["0.01"], None, f"{family}_{stat}_slow_0.01"))
        names.append(plan[-1][2])
        for fast, slow in (("5", "3"), ("3", "1"), ("1", "0.1"), ("0.1", "0.01")):
            plan.append((values[fast], values[slow], f"{family}_{stat}_asinh_delta_{fast}_minus_{slow}"))
            names.append(plan[-1][2])
    if len(plan) != 115 or len(set(names)) != 115:
        raise RuntimeError("contrast schema is not 115D")
    return plan, names


def multiscale_contrast(x: np.ndarray, headers: list[str]) -> np.ndarray:
    values = np.asarray(x, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 115:
        raise RuntimeError(f"invalid AfterImage matrix: {values.shape}")
    transformed = np.arcsinh(np.nan_to_num(values, nan=0.0, posinf=1e12, neginf=-1e12))
    plan, _names = contrast_plan(headers)
    out = np.empty((len(values), 115), dtype=np.float32)
    for column, (left, right, _name) in enumerate(plan):
        out[:, column] = transformed[:, left] if right is None else transformed[:, left] - transformed[:, right]
    if not np.isfinite(out).all():
        raise RuntimeError("nonfinite multiscale contrast")
    return out


def predictive_members(zf: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    members = [
        info
        for info in zf.infolist()
        if info.filename.startswith(AUX_PREFIX) and info.filename.endswith(".pcap")
    ]
    members.sort(key=lambda info: stable_rank(info.filename))
    if len(members) != 15:
        raise RuntimeError(f"expected 15 predictive-maintenance PCAPs, found {len(members)}")
    return members


def aux_uid(source: str, role: str, row: int) -> str:
    return f"aux:{role}:{source}:{row}"


def make_aux_records(source: str, role: str, count: int) -> list[ckbj.Record]:
    phase = "fit" if role == "aux_fit" else "select"
    return [
        ckbj.Record(
            uid=aux_uid(source, role, index),
            role=role,
            m1_phase=phase,
            source=source,
            recorded_index=index,
            event_position=index,
            label=0,
            attack_family="benign",
            device_family=AUX_FAMILY,
            source_family=AUX_FAMILY,
            # The auxiliary source has no C1 cache.  Treating every select row
            # as a C1 candidate is conservative: its verifier false positives
            # count in gate selection instead of being hidden by C1.
            c1_score=1.0,
            episode_id=source,
        )
        for index in range(count)
    ]


def materialize_auxiliary(args: argparse.Namespace, out: Path) -> AuxiliaryData:
    cache = out / "aux_afterimage_cache"
    cache.mkdir(parents=True, exist_ok=True)
    headers, schema_sha = afterimage_schema()
    frontend_source = OOD / "issue27ab_gotham_kitsune115_frontend_feasibility.py"
    afterimage_source = OOD.parent / "kitsune_frontend_original" / "AfterImage.py"
    source_md = OOD.parent / "kitsune_frontend_original" / "SOURCE.md"
    provenance = {
        "issue27ab_sha256_lf": ckbm.sha256_file_lf(frontend_source),
        "afterimage_py_sha256_lf": ckbm.sha256_file_lf(afterimage_source),
        "source_md_sha256_lf": ckbm.sha256_file_lf(source_md),
        "feature_schema_sha256": schema_sha,
    }
    rows: list[dict[str, Any]] = []
    raw_map: dict[str, np.ndarray] = {}
    contrast_map: dict[str, np.ndarray] = {}
    fit_records: list[ckbj.Record] = []
    select_records: list[ckbj.Record] = []
    with zipfile.ZipFile(Path(args.gotham_zip)) as zf:
        malicious_predictive = [
            name
            for name in zf.namelist()
            if name.startswith("raw/malicious/") and "predictive-maintenance" in name
        ]
        if malicious_predictive:
            raise RuntimeError(
                "predictive-maintenance is not a benign-only auxiliary family: "
                f"{malicious_predictive[:3]}"
            )
        for rank, info in enumerate(predictive_members(zf)):
            role = "aux_fit" if rank < FIT_SOURCE_COUNT else "aux_select"
            source = source_name(info.filename)
            key = hashlib.sha256(info.filename.encode("utf-8")).hexdigest()[:20]
            npz_path = cache / f"{key}.npz"
            if npz_path.is_file():
                with np.load(npz_path, allow_pickle=False) as loaded:
                    raw = np.asarray(loaded["raw115"], dtype=np.float32)
                    member = str(loaded["pcap_member"].item())
                    cached_schema = str(loaded["schema_sha256"].item())
                if member != info.filename or cached_schema != schema_sha:
                    raise RuntimeError(f"stale auxiliary cache: {npz_path}")
            else:
                smoke = ckab.SmokeFile(
                    role=role,
                    split_role=role,
                    pcap_member=info.filename,
                    csv_member="",
                    expected_binary_label="benign",
                    expected_attack_type="",
                    selection_reason="separate source-disjoint benign diversity extension",
                )
                full, _sidecar, meta = ckab.read_pcap_vectors(
                    zf,
                    smoke,
                    ckab.RestoredNetStat115(),
                    WARMUP_PACKETS + int(args.aux_rows_per_source),
                    WARMUP_PACKETS,
                    "fresh_source_afterimage115",
                    source,
                    max_scan_packets=max(200_000, WARMUP_PACKETS + int(args.aux_rows_per_source) + 1),
                )
                raw = np.asarray(full[WARMUP_PACKETS:], dtype=np.float32)
                if len(raw) != int(args.aux_rows_per_source):
                    raise RuntimeError(f"short auxiliary source {source}: {len(raw)} model-ready rows; meta={meta}")
                # These arrays are below 1 MiB per source.  Uncompressed NPZ
                # avoids zlib's transient output buffer, which can fail under
                # a memory-constrained login/local process for negligible disk
                # savings at this scale.
                np.savez(
                    npz_path,
                    raw115=raw,
                    pcap_member=np.asarray(info.filename),
                    schema_sha256=np.asarray(schema_sha),
                )
            if raw.shape != (int(args.aux_rows_per_source), 115) or not np.isfinite(raw).all():
                raise RuntimeError(f"invalid auxiliary cache shape for {source}: {raw.shape}")
            contrast = multiscale_contrast(raw, headers)
            records = make_aux_records(source, role, len(raw))
            for record, raw_row, contrast_row in zip(records, raw, contrast):
                raw_map[record.uid] = raw_row
                contrast_map[record.uid] = contrast_row
            (fit_records if role == "aux_fit" else select_records).extend(records)
            rows.append(
                {
                    "source_group": source,
                    "device_family": AUX_FAMILY,
                    "role": role,
                    "raw_source_path": info.filename,
                    "raw_zip_size": int(info.file_size),
                    "raw_zip_crc32": f"{int(info.CRC):08x}",
                    "stable_split_rank": rank,
                    "warmup_packets": WARMUP_PACKETS,
                    "model_ready_rows": len(raw),
                    "source_fresh_reset": True,
                    "current_packet_inclusive": True,
                    "future_events_used": False,
                    "raw_label_column_read": False,
                    "labels_used_to_build_features": False,
                    "source_identity_as_feature": False,
                    "event_schema": "Kitsune/AfterImage RestoredNetStat115",
                    "feature_schema_sha256": schema_sha,
                    "cache_npz": npz_path.name,
                    "cache_sha256": sha256_file(npz_path),
                    **provenance,
                }
            )
    manifest_path = out / "ckbo_auxiliary_benign_manifest.csv"
    write_csv_lf(manifest_path, rows)
    manifest_sha = sha256_file(manifest_path)
    ready = {
        "status": "CKBO_AUXILIARY_AFTERIMAGE_READY",
        "manifest_sha256": manifest_sha,
        "source_count": len(rows),
        "fit_sources": sum(row["role"] == "aux_fit" for row in rows),
        "select_sources": sum(row["role"] == "aux_select" for row in rows),
        "fit_rows": len(fit_records),
        "select_rows": len(select_records),
        "raw_label_column_read": False,
        "original_1m_assets_modified": False,
        "permanent_report_only_use_count": 0,
        "sealed_use_count": 0,
        "feature_schema_sha256": schema_sha,
        "provenance": provenance,
    }
    dump_json(out / "ckbo_auxiliary_benign_ready.json", ready)
    return AuxiliaryData(fit_records, select_records, raw_map, contrast_map, pd.DataFrame(rows), manifest_sha, ready)


def permanently_mask_frames(frames: dict[str, pd.DataFrame]) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    masked: dict[str, pd.DataFrame] = {}
    audits: list[dict[str, Any]] = []
    blocked = set(PERMANENT_REPORT_ONLY)
    for role, original in frames.items():
        frame = original.copy()
        families = frame["device_family"].astype(str)
        mask = families.isin(blocked) & frame["phase"].astype(str).isin({"fit", "select"})
        before = {
            family: int((families.eq(family) & frame["phase"].astype(str).isin({"fit", "select"})).sum())
            for family in PERMANENT_REPORT_ONLY
        }
        frame.loc[mask, "phase"] = "permanent_report_only_forbidden"
        for family in PERMANENT_REPORT_ONLY:
            after = int(
                (
                    frame["device_family"].astype(str).eq(family)
                    & frame["phase"].astype(str).isin({"fit", "select"})
                ).sum()
            )
            audits.append(
                {
                    "role": role,
                    "family": family,
                    "fit_select_rows_in_original": before[family],
                    "fit_select_rows_after_mask": after,
                    "model_use_count": 0,
                    "preprocessing_use_count": 0,
                    "gate_use_count": 0,
                    "report_only": True,
                }
            )
        masked[role] = frame
    return masked, audits


def collect_formal_sets(
    model: Any,
    frontend: Any,
    model_frames: dict[str, pd.DataFrame],
    report_frames: dict[str, pd.DataFrame],
    t0: Any,
    position_cache: dict[str, dict[int, int]],
    held: str | None,
    train_cap: int,
    eval_cap: int,
) -> tuple[dict[str, list[ckbj.Record]], list[dict[str, Any]]]:
    sets: dict[str, list[ckbj.Record]] = defaultdict(list)
    audit: list[dict[str, Any]] = []

    def take(role: str, phase: str, scope: str, label: int, cap: int, report: bool, frames: dict[str, pd.DataFrame]) -> None:
        values, rows = ckbj.collect_records(
            model,
            frontend,
            frames,
            t0,
            position_cache,
            role,
            phase,
            scope,
            label,
            held,
            cap,
            report=report,
        )
        sets[{"fit": "fit_attack" if label else "fit_benign", "select": "select_attack" if label else "select_benign", "report": "report"}[scope]].extend(values)
        audit.extend(rows)

    take("support_train", "fit", "fit", 1, cko.FULL_CAP, False, model_frames)
    for role in ckbj.FIT_BENIGN:
        take(role, "fit", "fit", 0, train_cap, False, model_frames)
    take("support_val", "select", "select", 1, cko.FULL_CAP, False, model_frames)
    for role in ckbj.SELECT_BENIGN:
        take(role, "select", "select", 0, eval_cap, False, model_frames)
    report_specs = ckbj.REPORT_SPECS if held is not None else ckbj.REPORT_SPECS[3:]
    for role, phase, label, _kind in report_specs:
        take(role, phase, "report", label, eval_cap, True, report_frames)
    blocked = set(PERMANENT_REPORT_ONLY)
    extension_sources = set(getattr(t0, "report_only_sources", set()))
    for key in ("fit_attack", "fit_benign", "select_attack", "select_benign"):
        leaked = [record for record in sets[key] if record.device_family in blocked]
        if leaked:
            raise RuntimeError(f"permanent report-only family leaked into {key}: {leaked[0].device_family}")
        extension_leaked = sorted({record.source for record in sets[key]} & extension_sources)
        if extension_leaked:
            raise RuntimeError(f"report-cache extension source leaked into {key}: {extension_leaked}")
    return dict(sets), audit


def existing_feature_map(records: list[ckbj.Record], x_by_role: dict[str, np.ndarray], representation: str, headers: list[str]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    by_role: defaultdict[str, list[ckbj.Record]] = defaultdict(list)
    for record in records:
        if not record.role.startswith("aux_"):
            by_role[record.role].append(record)
    for role, group in by_role.items():
        matrix = np.vstack([np.asarray(x_by_role[role][ckbm.record_row(record)], dtype=np.float32) for record in group])
        if matrix.shape[1] != 115:
            raise RuntimeError(f"certified AfterImage feature width drift for {role}: {matrix.shape}")
        if representation == "multiscale_contrast115":
            matrix = multiscale_contrast(matrix, headers)
        for record, row in zip(group, matrix):
            result[record.uid] = row
    return result


def generic_preprocessor(records: list[ckbj.Record], values: dict[str, np.ndarray], seed: int) -> tuple[QuantileTransformer, dict[str, Any]]:
    x = ckbm.stack_map(records, values)
    if x.ndim != 2 or x.shape[1] != 115 or len(x) < 10:
        raise RuntimeError(f"invalid fit-only AfterImage preprocessing matrix: {x.shape}")
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.0, 1e-5, x.shape).astype(np.float32)
    n_quantiles = max(min(len(x) // 30, 1000), 10)
    transformer = QuantileTransformer(
        n_quantiles=n_quantiles,
        output_distribution="normal",
        subsample=1_000_000_000,
        random_state=int(seed),
    ).fit(x + noise)
    return transformer, {
        "fit_rows": len(records),
        "fit_sources": len({record.source for record in records}),
        "fit_attack_rows": sum(record.label == 1 for record in records),
        "fit_benign_rows": sum(record.label == 0 for record in records),
        "n_quantiles": n_quantiles,
        "fit_only": True,
        "select_rows_used": 0,
        "report_rows_used": 0,
        "quantiles_sha256": ckbm.sha256_array(transformer.quantiles_),
        "references_sha256": ckbm.sha256_array(transformer.references_),
    }


def transform_map(transformer: QuantileTransformer, records: list[ckbj.Record], values: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    if not records:
        return {}
    matrix = transformer.transform(ckbm.stack_map(records, values))
    matrix = np.clip(np.nan_to_num(matrix, nan=0.0, posinf=8.0, neginf=-8.0), -8.0, 8.0).astype(np.float32)
    return {record.uid: row for record, row in zip(records, matrix)}


def add_auxiliary_values(values: dict[str, np.ndarray], aux: AuxiliaryData, representation: str, records: Iterable[ckbj.Record]) -> None:
    source = aux.raw if representation == "raw115" else aux.contrast
    for record in records:
        values[record.uid] = source[record.uid]


def protocol_family_name(held: str | None) -> str:
    return "GLOBAL_ATTACK_PRESERVATION" if held is None else held


def run_protocol(
    held: str | None,
    args: argparse.Namespace,
    x_by_role: dict[str, np.ndarray],
    report_frames: dict[str, pd.DataFrame],
    model_frames: dict[str, pd.DataFrame],
    t0: Any,
    position_cache: dict[str, dict[int, int]],
    aux: AuxiliaryData,
) -> dict[str, list[dict[str, Any]]]:
    name = protocol_family_name(held)
    c1_model, frontend, c1_threshold, c1_audit = ckbj.fit_c1(
        x_by_role,
        model_frames,
        held,
        Path(args.c1_cache),
        Path(args.c1_plan),
        Path(args.c1_report_extension),
        int(args.train_cap),
        int(args.eval_cap),
    )
    sets, data_audit = collect_formal_sets(
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
    if len(sets["fit_attack"]) != 385 and held is None:
        raise RuntimeError(f"global protocol lost legal support_train rows: {len(sets['fit_attack'])}")
    if len(sets["select_attack"]) != 69 and held is None:
        raise RuntimeError(f"global protocol lost legal support_val rows: {len(sets['select_attack'])}")
    headers, schema_sha = afterimage_schema()
    core_records = ckbm.unique_records(
        [sets["fit_attack"], sets["fit_benign"], sets["select_attack"], sets["select_benign"], sets["report"]]
    )
    candidate_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    loss_rows: list[dict[str, Any]] = []
    support_rows: list[dict[str, Any]] = []
    support_family_rows: list[dict[str, Any]] = []
    preprocessing_rows: list[dict[str, Any]] = []
    scores: dict[str, dict[str, float]] = {}
    thresholds: dict[str, float] = {}

    for spec in CANDIDATES:
        use_aux = bool(spec.use_auxiliary_benign and held != AUX_FAMILY)
        fit_records = sets["fit_attack"] + sets["fit_benign"] + (aux.records_fit if use_aux else [])
        select_records = sets["select_attack"] + sets["select_benign"] + (aux.records_select if use_aux else [])
        all_records = core_records + ((aux.records_fit + aux.records_select) if use_aux else [])
        base = existing_feature_map(core_records, x_by_role, spec.representation, headers)
        if use_aux:
            add_auxiliary_values(base, aux, spec.representation, aux.records_fit + aux.records_select)
        transformer, prep = generic_preprocessor(fit_records, base, int(args.seed))
        transformed = transform_map(transformer, all_records, base)
        sampled_idx, weights, weight_audit, occurrences = ckbm.balanced_training_sample(fit_records, int(args.seed))
        y = np.asarray([record.label for record in fit_records], dtype=np.int64)[sampled_idx]
        x = ckbm.stack_map(fit_records, transformed)[sampled_idx]
        backend_spec = ckbm.BackendSpec(spec.name, "tabm", "global", spec.primary)
        model, history, model_hash = ckbm.fit_backend(backend_spec, x, y, weights, args, int(args.seed))
        probability = ckbm.backend_scores(model, ckbm.stack_map(all_records, transformed))
        score_map = {record.uid: float(value) for record, value in zip(all_records, probability)}
        threshold, frontier, gate_pass = ckbm.choose_verifier_gate(
            spec.name,
            sets["select_attack"],
            sets["select_benign"] + (aux.records_select if use_aux else []),
            score_map,
            c1_threshold,
        )
        scores[spec.name] = score_map
        thresholds[spec.name] = threshold
        for row in frontier:
            candidate_rows.append(
                {
                    **row,
                    "held_value": name,
                    "representation": spec.representation,
                    "auxiliary_benign_enabled": use_aux,
                    "auxiliary_select_rows": len(aux.records_select) if use_aux else 0,
                    "auxiliary_rows_conservatively_treated_as_c1_candidates": len(aux.records_select) if use_aux else 0,
                    "c1_candidate_threshold": c1_threshold,
                    "gate_constraint_pass": gate_pass,
                    "feature_schema_sha256": schema_sha,
                }
            )
        loss_rows.extend({**row, "candidate": spec.name, "held_value": name} for row in history)
        used, families = ckbm.usage_rows(spec.name, sets["fit_attack"], occurrences, int(args.epochs), name)
        support_rows.extend(used)
        support_family_rows.extend(families)
        prep.update(
            {
                "candidate": spec.name,
                "held_value": name,
                "representation": spec.representation,
                "auxiliary_benign_enabled": use_aux,
                "auxiliary_fit_rows": len(aux.records_fit) if use_aux else 0,
            }
        )
        preprocessing_rows.append(prep)
        model_rows.append(
            {
                "candidate": spec.name,
                "held_value": name,
                "backend": "official_tabm_v0.0.3",
                "representation": spec.representation,
                "mature_afterimage_frontend": True,
                "auxiliary_benign_enabled": use_aux,
                "primary": spec.primary,
                "input_dim": x.shape[1],
                "fit_rows": len(fit_records),
                "fit_attack_rows": len(sets["fit_attack"]),
                "fit_original_benign_rows": len(sets["fit_benign"]),
                "fit_auxiliary_benign_rows": len(aux.records_fit) if use_aux else 0,
                "all_unique_fit_rows_covered": len(occurrences) == len(fit_records),
                "model_sha256": model_hash,
                "report_gradient_updates": 0,
                "report_threshold_updates": 0,
                "review_rate": 0.0,
            }
        )
        for row in weight_audit:
            row.update({"candidate": spec.name, "held_value": name})

    attack_records = sets["select_attack"] + [record for record in sets["report"] if record.label == 1]
    strict_records = sets["report"] if held is not None else attack_records + [record for record in sets["report"] if record.label == 0]
    c1_hard = np.asarray([record.c1_score >= c1_threshold for record in strict_records], dtype=bool)
    metrics: list[dict[str, Any]] = []
    family_metrics: list[dict[str, Any]] = []
    attack_summary: list[dict[str, Any]] = []
    strict_summary: list[dict[str, Any]] = []
    rows, families = ckbj.metric_rows("M0-C1", "strict_leave" if held else "attack_preservation", name, strict_records, c1_hard, int(args.bootstrap_reps), int(args.seed))
    metrics.extend(rows)
    family_metrics.extend(families)
    if held is None:
        attack_summary.extend(ckbj.attack_summary_rows("M0-C1", strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)))
    else:
        strict_summary.extend(ckbj.strict_level2_summary("M0-C1", name, strict_records, c1_hard, c1_hard, int(args.bootstrap_reps), int(args.seed)))
    for spec in CANDIDATES:
        hard = ckbj.hard_decisions(spec.name, strict_records, scores[spec.name], c1_threshold, thresholds[spec.name])
        rows, families = ckbj.metric_rows(spec.name, "strict_leave" if held else "attack_preservation", name, strict_records, hard, int(args.bootstrap_reps), int(args.seed))
        metrics.extend(rows)
        family_metrics.extend(families)
        if held is None:
            attack_summary.extend(ckbj.attack_summary_rows(spec.name, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)))
        else:
            strict_summary.extend(ckbj.strict_level2_summary(spec.name, name, strict_records, hard, c1_hard, int(args.bootstrap_reps), int(args.seed)))
    event_scope = ckbj.event_scope_rows(sets, set(getattr(t0, "report_only_sources", set())))
    for row in event_scope:
        row.update({"held_value": name, "protocol_run": name})
    for row in data_audit + c1_audit:
        row["protocol_run"] = name
    return {
        "c1_audit": c1_audit,
        "data_audit": data_audit,
        "candidate_selection": candidate_rows,
        "model_audit": model_rows,
        "preprocessing_audit": preprocessing_rows,
        "loss_curves": loss_rows,
        "support_usage": support_rows,
        "support_family_usage": support_family_rows,
        "metrics": metrics,
        "family_metrics": family_metrics,
        "attack_summary": attack_summary,
        "strict_summary": strict_summary,
        "event_scope": event_scope,
    }


def legal_development_holds(frames: dict[str, pd.DataFrame]) -> list[str]:
    values: list[str] = []
    blocked = set(PERMANENT_REPORT_ONLY)
    for family in sorted(
        set(frames["id_calib"]["device_family"].astype(str))
        | set(frames["ood_val"]["device_family"].astype(str))
    ):
        if family in blocked or family in {"", "NA", "nan"}:
            continue
        fit_rows = 0
        select_rows = 0
        for role in ("id_calib", "ood_val"):
            part = frames[role]
            fit_rows += int((part["device_family"].astype(str).eq(family) & part["phase"].astype(str).eq("fit")).sum())
            select_rows += int((part["device_family"].astype(str).eq(family) & part["phase"].astype(str).eq("select")).sum())
        if fit_rows and select_rows:
            values.append(family)
    return values


def prepare_inputs(args: argparse.Namespace, out: Path) -> tuple[Any, ...]:
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    overlap = sorted(
        {
            str(source)
            for frame in frames.values()
            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
            if "predictive-maintenance" in str(source)
        }
    )
    if overlap:
        raise RuntimeError(f"auxiliary predictive-maintenance source overlaps the frozen 1M roles: {overlap[:3]}")
    live = ckbi.report_only_exclusion(frames)
    live.to_csv(out / "ckbo_live_report_extension_exclusion.csv", index=False)
    required = live.loc[live["required_zero"].notna()]
    if required.empty or int(pd.to_numeric(required["extension_source_rows_used"]).sum()) != 0 or not bool(ckbj.bool_series(required["pass"]).all()):
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
    t0 = ckbj.CompositeT0Cache(base_t0, Path(args.report_t0_extension), set(extension_audit["extension_sources"]))
    coverage = ckbj.required_report_source_coverage(frames, t0)
    pd.DataFrame(coverage).to_csv(out / "ckbo_required_report_source_coverage.csv", index=False)
    if any(not bool(row["full_source_coverage"]) for row in coverage):
        raise RuntimeError("formal target coverage incomplete")
    pd.DataFrame(ckbj.support_val_lineage(frames)).to_csv(out / "ckbo_support_val_lineage.csv", index=False)
    return x_by_role, frames, input_audit, t0, t0_audit, extension_audit, c1_audit


def decision(attack: pd.DataFrame, strict: pd.DataFrame, selection: pd.DataFrame, permanent: pd.DataFrame, support: pd.DataFrame, data: pd.DataFrame, dev_holds: list[str]) -> dict[str, Any]:
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
    major = attack.loc[(attack.get("candidate", pd.Series(dtype=str)).eq(PRIMARY)) & (attack.get("metric", pd.Series(dtype=str)).eq("attack_family_recall")) & (pd.to_numeric(attack.get("rows", 0), errors="coerce").fillna(0).ge(15))]
    dev = strict.loc[strict.get("candidate", pd.Series(dtype=str)).eq(PRIMARY) & strict.get("held_value", pd.Series(dtype=str)).isin(dev_holds)]
    dev_c1 = strict.loc[strict.get("candidate", pd.Series(dtype=str)).eq("M0-C1") & strict.get("held_value", pd.Series(dtype=str)).isin(dev_holds)]
    dev_macro = float(dev["hard_rate"].mean()) if len(dev) == len(dev_holds) and dev_holds else None
    dev_c1_macro = float(dev_c1["hard_rate"].mean()) if len(dev_c1) == len(dev_holds) and dev_holds else None
    selected_flag = (
        ckbm.decision_bool_series(selection["selected"], False)
        if "selected" in selection
        else pd.Series(False, index=selection.index)
    )
    selected = selection.loc[selection.get("candidate", pd.Series(dtype=str)).eq(PRIMARY) & selected_flag]
    selected_gate_pass = (
        ckbm.decision_bool_series(selected["gate_constraint_pass"], False)
        if "gate_constraint_pass" in selected
        else pd.Series(False, index=selected.index)
    )
    alignment = (
        pd.to_numeric(data["target_alignment_incomplete"], errors="coerce").fillna(1)
        if "target_alignment_incomplete" in data
        else pd.Series(1, index=data.index)
    )
    checks = {
        "required_metrics_missing": any(value is None for value in (overall, stream, stream_c1, hydraulic, hydraulic_c1, dev_macro, dev_c1_macro)),
        "overall_attack_drop_over_0_5pp": bool(overall is not None and overall < -0.5),
        "major_attack_family_drop_over_2pp": bool(not major.empty and (major["delta_vs_c1_pp"] < -2.0).any()),
        "stream_signal_missing": bool(stream is None or stream_c1 is None or stream > 0.90 or stream > stream_c1 - 0.10),
        "hydraulic_worsened_over_2pp": bool(hydraulic is not None and hydraulic_c1 is not None and hydraulic - hydraulic_c1 > 0.02),
        "legal_multiheld_signal_missing": bool(dev_macro is None or dev_c1_macro is None or dev_macro > dev_c1_macro - 0.05),
        "permanent_report_family_used": bool(
            permanent.empty
            or permanent[
                ["fit_select_rows_after_mask", "model_use_count", "preprocessing_use_count", "gate_use_count"]
            ].to_numpy().sum()
            != 0
        ),
        "support_usage_incomplete": bool(support.empty or not support["used_at_least_once_each_epoch"].fillna(False).astype(bool).all()),
        "target_alignment_incomplete": bool(data.empty or alignment.gt(0).any()),
        "gate_constraint_failed": bool(selected.empty or not selected_gate_pass.all()),
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
        "legal_development_macro_hard_rate": dev_macro,
        "legal_development_c1_macro_hard_rate": dev_c1_macro,
        "review_rate": 0.0,
        "single_seed_scope": "go/no-go signal only",
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
        raise RuntimeError(f"refusing mixed formal output directory: {unexpected[:5]}")


def run_formal(args: argparse.Namespace) -> None:
    started = time.time()
    if int(args.seed) != SEED:
        raise RuntimeError("first CKBO formal run is preregistered for seed 27 only")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    assert_clean_formal_out(out)
    vendor = ckbm.validate_vendor()
    aux = materialize_auxiliary(args, out)
    x_by_role, report_frames, input_audit, t0, t0_audit, extension_audit, c1_extension_audit = prepare_inputs(args, out)
    model_frames, permanent_rows = permanently_mask_frames(report_frames)
    dev_holds = legal_development_holds(model_frames)
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    protocols: list[str | None] = [None]
    for value in dev_holds + requested:
        if value not in protocols:
            protocols.append(value)
    position_cache: dict[str, dict[int, int]] = {}
    results = [run_protocol(value, args, x_by_role, report_frames, model_frames, t0, position_cache, aux) for value in protocols]

    def table(key: str) -> pd.DataFrame:
        return pd.DataFrame([{**row, "seed": SEED} for result in results for row in result[key]])

    outputs = {
        "ckbo_c1_fit_select_audit.csv": table("c1_audit"),
        "ckbo_role_usage_audit.csv": table("data_audit"),
        "ckbo_candidate_selection.csv": table("candidate_selection"),
        "ckbo_model_audit.csv": table("model_audit"),
        "ckbo_preprocessing_audit.csv": table("preprocessing_audit"),
        "ckbo_loss_curves.csv": table("loss_curves"),
        "ckbo_support_training_usage.csv": table("support_usage"),
        "ckbo_support_family_training_usage.csv": table("support_family_usage"),
        "ckbo_all_metrics.csv": table("metrics"),
        "ckbo_per_attack_family_metrics.csv": table("family_metrics"),
        "attack_preservation_summary.csv": table("attack_summary"),
        "strict_level2_summary.csv": table("strict_summary"),
        "ckbo_event_scope_audit.csv": table("event_scope"),
        "ckbo_permanent_report_only_audit.csv": pd.DataFrame(permanent_rows),
    }
    outputs["ckbo_negative_sampling_audit.csv"] = pd.DataFrame(
        [
            {
                "seed": SEED,
                "sampled_negatives": 0,
                "status": "not_applicable_explicit_supervised_attack_and_benign_rows",
                "ghost_node_negatives": 0,
                "future_node_identity_used": False,
                "report_rows_used": 0,
                "held_rows_used": 0,
            }
        ]
    )
    outputs["ckbo_frontend_state_audit.csv"] = pd.DataFrame(
        [
            {
                "scope": "auxiliary_predictive_maintenance",
                "sources": len(aux.manifest),
                "fresh_source_resets": len(aux.manifest),
                "warmup_packets_per_source": WARMUP_PACKETS,
                "model_ready_cold_start_fraction": 0.0,
                "current_packet_inclusive": True,
                "future_events_used": False,
                "label_read_for_state": False,
                "gradient_updates_during_report": 0,
            },
            {
                "scope": "frozen_certified_1m_afterimage_features",
                "sources": int(
                    len(
                        {
                            str(source)
                            for frame in report_frames.values()
                            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
                        }
                    )
                ),
                "fresh_source_resets": "certified_input_materialization_contract",
                "warmup_packets_per_source": "frozen_input_contract",
                "model_ready_cold_start_fraction": "not_recomputed_by_ckbo",
                "current_packet_inclusive": True,
                "future_events_used": False,
                "label_read_for_state": False,
                "gradient_updates_during_report": 0,
            },
        ]
    )
    aux_scope_rows = []
    for spec in CANDIDATES:
        aux_scope_rows.extend(
            [
                {
                    "record_set": "aux_fit",
                    "m1_scope": "training" if spec.use_auxiliary_benign else "unused_ablation",
                    "events": len(aux.records_fit) if spec.use_auxiliary_benign else 0,
                    "sources": FIT_SOURCE_COUNT if spec.use_auxiliary_benign else 0,
                    "attack_events": 0,
                    "benign_events": len(aux.records_fit) if spec.use_auxiliary_benign else 0,
                    "report_only_sources": 0,
                    "held_value": "GLOBAL_ATTACK_PRESERVATION",
                    "protocol_run": "GLOBAL_ATTACK_PRESERVATION",
                    "candidate": spec.name,
                },
                {
                    "record_set": "aux_select",
                    "m1_scope": "select" if spec.use_auxiliary_benign else "unused_ablation",
                    "events": len(aux.records_select) if spec.use_auxiliary_benign else 0,
                    "sources": 15 - FIT_SOURCE_COUNT if spec.use_auxiliary_benign else 0,
                    "attack_events": 0,
                    "benign_events": len(aux.records_select) if spec.use_auxiliary_benign else 0,
                    "report_only_sources": 0,
                    "held_value": "GLOBAL_ATTACK_PRESERVATION",
                    "protocol_run": "GLOBAL_ATTACK_PRESERVATION",
                    "candidate": spec.name,
                },
            ]
        )
    outputs["ckbo_event_scope_audit.csv"] = pd.concat(
        [outputs["ckbo_event_scope_audit.csv"], pd.DataFrame(aux_scope_rows)], ignore_index=True
    )
    for filename, frame in outputs.items():
        frame.to_csv(out / filename, index=False)
    outcome = decision(
        outputs["attack_preservation_summary.csv"],
        outputs["strict_level2_summary.csv"],
        outputs["ckbo_candidate_selection.csv"],
        outputs["ckbo_permanent_report_only_audit.csv"],
        outputs["ckbo_support_training_usage.csv"],
        outputs["ckbo_role_usage_audit.csv"],
        dev_holds,
    )
    dump_json(out / "ckbo_single_seed_go_no_go.json", outcome)
    base_manifest = Path(args.t0_root) / "tgn_source_event_plan_frozen.csv"
    environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "pandas": pd.__version__,
        "sklearn": sklearn.__version__,
        "dpkt": getattr(ckab.dpkt, "__version__", "unknown"),
        "torch": ckbm.torch.__version__,
        "tabm": ckbm.tabm.__version__,
        "seed": SEED,
        "commit_sha": os.environ.get("CKBO_COMMIT_SHA", ckbm.git_head()),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "local"),
        "slurm_partition": os.environ.get("SLURM_JOB_PARTITION", "local"),
        "wall_seconds": time.time() - started,
        "review_rate": 0.0,
        "base_t0_manifest_sha256": sha256_file(base_manifest),
        "expected_base_t0_manifest_sha256": ckbj.EXPECTED_T0_MANIFEST_SHA256,
        "report_extension_manifest_sha256": extension_audit["extension_manifest_sha256"],
        "c1_report_extension_manifest_sha256": c1_extension_audit["manifest_sha256"],
        "auxiliary_manifest_sha256": aux.manifest_sha256,
        "vendor": vendor,
    }
    dump_json(out / "ckbo_environment.json", environment)
    dump_json(
        out / "run_spec.json",
        {
            "issue": ISSUE,
            "mode": "formal",
            "primary_candidate": PRIMARY,
            "candidates": [spec.__dict__ for spec in CANDIDATES],
            "protocols": [protocol_family_name(value) for value in protocols],
            "legal_development_holds": dev_holds,
            "permanent_report_only": list(PERMANENT_REPORT_ONLY),
            "original_1m_split_modified": False,
            "auxiliary_extension": aux.ready,
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_report_extension_audit": c1_extension_audit,
            "support_train_contract": "all 385 legal rows in global protocol; every row at least once per epoch",
            "support_val_contract": "69 legal select rows; gate only",
            "report_contract": "frozen model and preprocessing, no gradients, no thresholds, no label-derived features",
            "frontend_event_semantics": "standard AfterImage current-packet-inclusive statistics; no future packet and no label input; TabM has no mutable report state",
            "review_rate": 0.0,
            "environment": environment,
        },
    )
    write_text_lf(
        out / "codex_readout.md",
        f"# {ISSUE}\n\nSeed 27 formal result: `{outcome['decision']}` for `{PRIMARY}`. "
        "The original strict 1M split and frozen T0 manifest were not modified. Review is `0`.\n",
    )
    print(json.dumps({"status": "CKBO_FORMAL_COMPLETE", "decision": outcome["decision"], "out": str(out)}, indent=2))


def contract_unit(args: argparse.Namespace) -> None:
    headers, schema_sha = afterimage_schema()
    rng = np.random.default_rng(SEED)
    raw = np.abs(rng.normal(size=(7, 115))).astype(np.float32)
    contrast = multiscale_contrast(raw, headers)
    assert contrast.shape == raw.shape and np.isfinite(contrast).all()
    frames = {
        "x": pd.DataFrame(
            {
                "device_family": ["ok", *PERMANENT_REPORT_ONLY],
                "phase": ["fit", "fit", "select", "fit"],
            }
        )
    }
    masked, audit = permanently_mask_frames(frames)
    assert masked["x"].loc[0, "phase"] == "fit"
    assert all(masked["x"].loc[index, "phase"] == "permanent_report_only_forbidden" for index in (1, 2, 3))
    synthetic = make_aux_records("source-a", "aux_select", 3)
    assert all(record.c1_score == 1.0 and record.label == 0 for record in synthetic)
    assert sum(row["model_use_count"] for row in audit) == 0
    outcome = decision(
        pd.DataFrame(
            [
                {"candidate": PRIMARY, "metric": "overall_attack_hard_recall", "delta_vs_c1_pp": 0.0, "rows": 100},
                {"candidate": PRIMARY, "metric": "attack_family_recall", "delta_vs_c1_pp": 0.0, "rows": 20},
            ]
        ),
        pd.DataFrame(
            [
                {"candidate": PRIMARY, "held_value": "iotsim-stream-consumer", "hard_rate": 0.8},
                {"candidate": "M0-C1", "held_value": "iotsim-stream-consumer", "hard_rate": 1.0},
                {"candidate": PRIMARY, "held_value": "iotsim-hydraulic-system", "hard_rate": 0.4},
                {"candidate": "M0-C1", "held_value": "iotsim-hydraulic-system", "hard_rate": 0.4},
                {"candidate": PRIMARY, "held_value": "legal-a", "hard_rate": 0.4},
                {"candidate": "M0-C1", "held_value": "legal-a", "hard_rate": 0.5},
            ]
        ),
        pd.DataFrame(
            [
                {"candidate": PRIMARY, "selected": True, "gate_constraint_pass": True},
                {"candidate": PRIMARY, "selected": np.nan, "gate_constraint_pass": np.nan},
            ]
        ),
        pd.DataFrame(audit),
        pd.DataFrame([{"used_at_least_once_each_epoch": True}]),
        pd.DataFrame([{"target_alignment_incomplete": 0}]),
        ["legal-a"],
    )
    assert outcome["decision"] == "GO_SIGNAL", outcome
    with tempfile.TemporaryDirectory(prefix="ckbo_formal_out_contract_") as temp_root:
        temp_out = Path(temp_root)
        (temp_out / "slurm_identity.txt").write_text("job=1\n", encoding="utf-8")
        (temp_out / "slurm_job_at_start.txt").write_text("job\n", encoding="utf-8")
        assert_clean_formal_out(temp_out)
        (temp_out / "unexpected.txt").write_text("reject\n", encoding="utf-8")
        try:
            assert_clean_formal_out(temp_out)
        except RuntimeError:
            pass
        else:
            raise AssertionError("formal output guard accepted an unexpected file")
    vendor = ckbm.validate_vendor()
    print(
        json.dumps(
            {
                "status": "CKBO_CONTRACT_UNIT_PASS",
                "feature_schema_sha256": schema_sha,
                "contrast_shape": list(contrast.shape),
                "permanent_report_only": list(PERMANENT_REPORT_ONLY),
                "vendor": vendor,
            },
            indent=2,
        )
    )


def aux_smoke(args: argparse.Namespace) -> None:
    with zipfile.ZipFile(Path(args.gotham_zip)) as zf:
        info = predictive_members(zf)[0]
        smoke = ckab.SmokeFile("smoke", "smoke", info.filename, "", "benign", "", "bounded local parser check")
        raw, sidecar, meta = ckab.read_pcap_vectors(
            zf,
            smoke,
            ckab.RestoredNetStat115(),
            32,
            8,
            "fresh_source_afterimage115",
            source_name(info.filename),
            max_scan_packets=256,
        )
    contrast = multiscale_contrast(raw[8:], afterimage_schema()[0])
    if raw.shape != (32, 115) or contrast.shape != (24, 115):
        raise RuntimeError(f"bounded auxiliary smoke failed: raw={raw.shape}, contrast={contrast.shape}")
    print(json.dumps({"status": "CKBO_AUX_SMOKE_PASS", "pcap_member": info.filename, "raw_shape": list(raw.shape), "contrast_shape": list(contrast.shape), "meta": meta, "raw_label_column_read": False, "sidecar_rows": len(sidecar)}, indent=2))


def dry_run(args: argparse.Namespace) -> None:
    print(
        json.dumps(
            {
                "issue": ISSUE,
                "seed": SEED,
                "primary": PRIMARY,
                "candidates": [spec.__dict__ for spec in CANDIDATES],
                "permanent_report_only": list(PERMANENT_REPORT_ONLY),
                "auxiliary_family": AUX_FAMILY,
                "auxiliary_sources": 15,
                "auxiliary_fit_sources": FIT_SOURCE_COUNT,
                "auxiliary_select_sources": 15 - FIT_SOURCE_COUNT,
                "auxiliary_rows_per_source": int(args.aux_rows_per_source),
                "original_1m_split_modified": False,
                "formal_job": "result-producing attack preservation, legal multi-held development, and frozen report canaries",
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["contract-unit", "aux-smoke", "dry-run", "formal"], default="dry-run")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--held-values", default=",".join(HELD))
    parser.add_argument("--gotham-zip", type=Path, default=DEFAULT_ZIP)
    parser.add_argument("--t0-root", type=Path, default=DEFAULT_T0)
    parser.add_argument("--report-t0-extension", type=Path, default=DEFAULT_REPORT_EXTENSION)
    parser.add_argument("--c1-plan", type=Path, default=DEFAULT_C1_PLAN)
    parser.add_argument("--c1-targets", type=Path, default=DEFAULT_C1_TARGETS)
    parser.add_argument("--c1-cache", type=Path, default=DEFAULT_C1_CACHE)
    parser.add_argument("--c1-report-extension", type=Path, default=DEFAULT_C1_REPORT_EXTENSION)
    parser.add_argument("--train-cap", type=int, default=4000)
    parser.add_argument("--eval-cap", type=int, default=3000)
    parser.add_argument("--bootstrap-reps", type=int, default=500)
    parser.add_argument("--epochs", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=512)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--tabm-k", type=int, default=16)
    parser.add_argument("--tabm-width", type=int, default=256)
    parser.add_argument("--tabm-blocks", type=int, default=3)
    parser.add_argument("--extra-trees", type=int, default=0)
    parser.add_argument("--aux-rows-per-source", type=int, default=MODEL_READY_PER_SOURCE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode == "contract-unit":
        contract_unit(args)
    elif args.mode == "aux-smoke":
        aux_smoke(args)
    elif args.mode == "formal":
        run_formal(args)
    else:
        dry_run(args)


if __name__ == "__main__":
    main()
