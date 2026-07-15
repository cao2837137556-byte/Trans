"""CKBO: mature AfterImage transfer with legal benign-diversity extension.

This result-producing experiment keeps the frozen C1 detector as the high-
recall candidate anchor and asks a narrower, transferable question: can a
verifier built from the maintained Kitsune/AfterImage frontend suppress unseen
normal processes without sacrificing attacks?

The original strict 1M roles and the frozen CKBE/CKBI caches are read-only.
Thirty-one previously unused benign PCAPs are materialized into a separate
source-disjoint extension manifest: 16 known-family sources provide legal
fit/select diversity and 15 predictive-maintenance sources remain report-only.
They never alter the 1M split.  Stream and hydraulic are read only after all
choices freeze; cooler-motor remains sealed and is never scored in CKBO.
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
import issue27ckai_external_flow_feature_probe_v1 as ckai  # noqa: E402
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
AUX_FAMILY = "source_disjoint_known_benign_families"
AUX_HELD_FAMILY = "iotsim-predictive-maintenance"
AUX_FIT_SELECT_DEVICE_KEYS = (
    *(f"iotsim-combined-cycle-{index}" for index in range(2, 10)),
    "iotsim-combined-cycle-tls-1",
    "iotsim-combined-cycle-tls-2",
    *(f"iotsim-domotic-monitor-{index}" for index in range(2, 6)),
    "iotsim-building-monitor-4",
    "iotsim-building-monitor-5",
)
AUX_HELD_DEVICE_KEYS = tuple(f"iotsim-predictive-maintenance-{index}" for index in range(1, 16))
AUX_SELECT_PER_FAMILY = {
    "iotsim-combined-cycle": 2,
    "iotsim-combined-cycle-tls": 1,
    "iotsim-domotic-monitor": 1,
    "iotsim-building-monitor": 1,
}
WARMUP_PACKETS = 500
MODEL_READY_PER_SOURCE = 600
FIT_SOURCE_COUNT = 11
SELECT_SOURCE_COUNT = 5
HELD_SOURCE_COUNT = 15


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
    records_report: list[ckbj.Record]
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


def device_key(member: str) -> str:
    match = re.match(r"^raw/benign/(iotsim-.+?)_0-0_to_", str(member))
    if not match:
        raise RuntimeError(f"unparsed auxiliary benign member: {member}")
    return match.group(1)


def device_family_from_key(key: str) -> str:
    family = re.sub(r"-\d+$", "", str(key))
    if family == key:
        raise RuntimeError(f"unparsed auxiliary device key: {key}")
    return family


def auxiliary_member_specs(zf: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str, str]]:
    wanted = set(AUX_FIT_SELECT_DEVICE_KEYS) | set(AUX_HELD_DEVICE_KEYS)
    by_key: dict[str, zipfile.ZipInfo] = {}
    for info in zf.infolist():
        if not info.filename.startswith("raw/benign/") or not info.filename.endswith(".pcap"):
            continue
        key = device_key(info.filename)
        if key in wanted:
            if key in by_key:
                raise RuntimeError(f"duplicate auxiliary benign source: {key}")
            by_key[key] = info
    if set(by_key) != wanted:
        raise RuntimeError(f"auxiliary benign source boundary drift: missing={sorted(wanted - set(by_key))}")

    select_keys: set[str] = set()
    fit_groups: defaultdict[str, list[str]] = defaultdict(list)
    for key in AUX_FIT_SELECT_DEVICE_KEYS:
        fit_groups[device_family_from_key(key)].append(key)
    if set(fit_groups) != set(AUX_SELECT_PER_FAMILY):
        raise RuntimeError("auxiliary fit/select family boundary drift")
    for family, keys in sorted(fit_groups.items()):
        ranked = sorted(keys, key=stable_rank)
        count = int(AUX_SELECT_PER_FAMILY[family])
        if count <= 0 or count >= len(ranked):
            raise RuntimeError(f"invalid auxiliary select source count for {family}: {count}")
        select_keys.update(ranked[-count:])
    if len(select_keys) != SELECT_SOURCE_COUNT:
        raise RuntimeError(f"auxiliary select source count drift: {len(select_keys)}")

    specs: list[tuple[zipfile.ZipInfo, str, str]] = []
    for key in sorted(wanted, key=stable_rank):
        family = device_family_from_key(key)
        role = "aux_report" if key in set(AUX_HELD_DEVICE_KEYS) else ("aux_select" if key in select_keys else "aux_fit")
        specs.append((by_key[key], family, role))
    counts = Counter(role for _info, _family, role in specs)
    expected = {"aux_fit": FIT_SOURCE_COUNT, "aux_select": SELECT_SOURCE_COUNT, "aux_report": HELD_SOURCE_COUNT}
    if dict(counts) != expected:
        raise RuntimeError(f"auxiliary role split drift: {dict(counts)} != {expected}")
    return specs


def aux_uid(source: str, role: str, row: int) -> str:
    return f"aux:{role}:{source}:{row}"


def make_aux_records(source: str, role: str, count: int, family: str = AUX_FAMILY) -> list[ckbj.Record]:
    phase = {"aux_fit": "fit", "aux_select": "select", "aux_report": "report"}[role]
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
            device_family=family,
            source_family=family,
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
    report_records: list[ckbj.Record] = []
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
        specs = auxiliary_member_specs(zf)
        family_members: defaultdict[str, list[str]] = defaultdict(list)
        for info, family, _role in specs:
            family_members[family].append(info.filename)
        family_rank = {
            member: rank
            for family, members in family_members.items()
            for rank, member in enumerate(sorted(members, key=stable_rank))
        }
        for rank, (info, family, role) in enumerate(specs):
            source = source_name(info.filename)
            key_name = device_key(info.filename)
            key = hashlib.sha256(info.filename.encode("utf-8")).hexdigest()[:20]
            npz_path = cache / f"{key}.npz"
            if npz_path.is_file():
                with np.load(npz_path, allow_pickle=False) as loaded:
                    stored_raw = np.asarray(loaded["raw115"], dtype=np.float32)
                    member = str(loaded["pcap_member"].item())
                    cached_schema = str(loaded["schema_sha256"].item())
                if member != info.filename or cached_schema != schema_sha:
                    raise RuntimeError(f"stale auxiliary cache: {npz_path}")
                if len(stored_raw) < int(args.aux_rows_per_source):
                    raise RuntimeError(f"short existing auxiliary cache: {npz_path}: {stored_raw.shape}")
                raw = stored_raw[: int(args.aux_rows_per_source)]
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
            records = make_aux_records(source, role, len(raw), family)
            for record, raw_row, contrast_row in zip(records, raw, contrast):
                raw_map[record.uid] = raw_row
                contrast_map[record.uid] = contrast_row
            {"aux_fit": fit_records, "aux_select": select_records, "aux_report": report_records}[role].extend(records)
            rows.append(
                {
                    "source_group": source,
                    "device_key": key_name,
                    "device_family": family,
                    "role": role,
                    "raw_source_path": info.filename,
                    "raw_zip_size": int(info.file_size),
                    "raw_zip_crc32": f"{int(info.CRC):08x}",
                    "stable_split_rank": rank,
                    "family_stable_split_rank": family_rank[info.filename],
                    "family_source_count": len(family_members[family]),
                    "split_rule": "sha256_rank_within_family_frozen_select_counts; predictive_all_report",
                    "warmup_packets": WARMUP_PACKETS,
                    "model_ready_rows": len(raw),
                    "training_rows": len(raw) if role == "aux_fit" else 0,
                    "selection_rows": len(raw) if role == "aux_select" else 0,
                    "report_rows": len(raw) if role == "aux_report" else 0,
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
        "report_sources": sum(row["role"] == "aux_report" for row in rows),
        "fit_rows": len(fit_records),
        "select_rows": len(select_records),
        "report_rows": len(report_records),
        "report_family": AUX_HELD_FAMILY,
        "raw_label_column_read": False,
        "original_1m_assets_modified": False,
        "permanent_report_only_use_count": 0,
        "sealed_use_count": 0,
        "feature_schema_sha256": schema_sha,
        "provenance": provenance,
    }
    dump_json(out / "ckbo_auxiliary_benign_ready.json", ready)
    return AuxiliaryData(fit_records, select_records, report_records, raw_map, contrast_map, pd.DataFrame(rows), manifest_sha, ready)


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
                    "report_only": family != "iotsim-cooler-motor",
                    "sealed_unopened": family == "iotsim-cooler-motor",
                }
            )
        masked[role] = frame
    return masked, audits


def frozen_target_keys(path: Path) -> set[tuple[str, int]]:
    table = pd.read_csv(Path(path), usecols=["source_group", "recorded_index"])
    recorded = pd.to_numeric(table["recorded_index"], errors="coerce")
    valid = recorded.notna() & recorded.ge(0)
    return set(
        zip(
            table.loc[valid, "source_group"].astype(str),
            recorded.loc[valid].astype(np.int64),
        )
    )


def t0_target_keys(t0: Any, frames: dict[str, pd.DataFrame]) -> set[tuple[str, int]]:
    sources = sorted(
        {
            str(source)
            for frame in frames.values()
            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
            if str(source)
        }
    )
    keys: set[tuple[str, int]] = set()
    for source in sources:
        keys.update((source, int(recorded)) for recorded in t0.target_positions(source))
    return keys


def restrict_model_scope_to_frozen_targets(
    frames: dict[str, pd.DataFrame],
    c1_targets: Path,
    t0: Any,
    allow_local_t0_manifest_proxy: bool = False,
) -> tuple[dict[str, pd.DataFrame], list[dict[str, Any]]]:
    """Keep fit/select membership inside both immutable cache contracts.

    The CKAT C1 cache and CKBE T0 cache contain exact row cohorts selected for
    the five frozen leave-family folds.  Permanently removing multiple canary
    families changes the length of a role and therefore changes the rows
    returned by the old linspace cap.  Re-capping the full role after that
    removal can request uncached rows.  This function makes the cache cohort an
    explicit eligibility boundary before any later held-family filter/cap.
    Missing features are never zero-filled and no new raw row is read.
    """

    c1_keys = frozen_target_keys(Path(c1_targets))
    temporal_keys = t0_target_keys(t0, frames)
    t0_scope_basis = "exact_target_positions"
    if not temporal_keys and allow_local_t0_manifest_proxy:
        plan = Path(t0.root) / "tgn_source_event_plan_frozen.csv"
        audit_path = Path(t0.root) / "t0_cache_audit.csv"
        if not plan.is_file() or not audit_path.is_file():
            raise RuntimeError("local T0 proxy requires the frozen plan and completion audit")
        plan_hash = sha256_file(plan)
        audit_table = pd.read_csv(audit_path)
        if (
            plan_hash != ckbj.EXPECTED_T0_MANIFEST_SHA256
            or len(pd.read_csv(plan)) != 26
            or len(audit_table) != 26
            or int(pd.to_numeric(audit_table["target_rows"], errors="coerce").fillna(0).sum()) != 34622
        ):
            raise RuntimeError("local T0 proxy failed frozen hash/cardinality contract")
        # The local pullback intentionally omits the 26 large NPZ files.  CKBE
        # certified the exact 34,622 CKAT target rows used to build them; the
        # formal job below never uses this proxy and re-reads every NPZ target.
        temporal_keys = set(c1_keys)
        t0_scope_basis = "local_ckbe_manifest_and_completion_audit_proxy_formal_rechecks_npz"
    if not c1_keys or not temporal_keys:
        raise RuntimeError("empty frozen C1/T0 target cohort")
    allowed = c1_keys & temporal_keys
    if not allowed:
        raise RuntimeError("frozen C1 and T0 target cohorts do not intersect")

    scoped: dict[str, pd.DataFrame] = {}
    audit: list[dict[str, Any]] = []
    extension_sources = set(getattr(t0, "report_only_sources", set()))
    for role, original in frames.items():
        frame = original.copy()
        phases = frame["phase"].astype(str)
        for phase in ("fit", "select"):
            phase_mask = phases.eq(phase).to_numpy()
            positions = np.flatnonzero(phase_mask)
            if len(positions):
                sources = frame.iloc[positions]["source_group"].astype(str).to_numpy()
                recorded = (
                    pd.to_numeric(frame.iloc[positions]["recorded_index"], errors="coerce")
                    .fillna(-1)
                    .astype(np.int64)
                    .to_numpy()
                )
                c1_ok = np.fromiter(
                    ((source, int(index)) in c1_keys for source, index in zip(sources, recorded)),
                    dtype=bool,
                    count=len(positions),
                )
                t0_ok = np.fromiter(
                    ((source, int(index)) in temporal_keys for source, index in zip(sources, recorded)),
                    dtype=bool,
                    count=len(positions),
                )
                keep = c1_ok & t0_ok
                frame.loc[positions[~keep], "phase"] = "outside_frozen_model_cohort"
                extension_use = int(np.isin(sources[keep], list(extension_sources)).sum())
            else:
                c1_ok = t0_ok = np.zeros(0, dtype=bool)
                keep = np.zeros(0, dtype=bool)
                extension_use = 0
            audit.append(
                {
                    "role": role,
                    "phase": phase,
                    "rows_before_frozen_scope": int(len(positions)),
                    "rows_in_c1_target_cohort": int(c1_ok.sum()),
                    "rows_in_t0_target_cohort": int(t0_ok.sum()),
                    "rows_after_frozen_intersection": int(keep.sum()),
                    "rows_excluded_for_cache_scope": int(len(positions) - keep.sum()),
                    "report_extension_rows_retained": extension_use,
                    "missing_feature_zero_fill": 0,
                    "raw_rows_materialized": 0,
                    "t0_scope_basis": t0_scope_basis,
                }
            )
        scoped[role] = frame

    retained = sum(row["rows_after_frozen_intersection"] for row in audit)
    if retained <= 0:
        raise RuntimeError("no legal fit/select rows remain in frozen model cohort")
    if any(row["report_extension_rows_retained"] for row in audit):
        raise RuntimeError("report-only extension entered frozen model cohort")
    return scoped, audit


def fit_c1_attack_preserving(
    x_by_role: dict[str, np.ndarray],
    frames: dict[str, pd.DataFrame],
    held: str | None,
    cache_dir: Path,
    plan: Path,
    c1_report_extension: Path,
    train_cap: int,
) -> tuple[Any, Any, float, list[dict[str, Any]]]:
    """Fit C1 legally and freeze its candidate threshold from attacks only.

    After all permanent report families are removed, the original 1M split has
    no legal benign select rows.  Using a report canary to recover that role
    would be leakage.  The C1 anchor is therefore made deliberately
    recall-first: the threshold is the value immediately below the minimum
    legal support_val attack score.  Verifier selection still uses the
    source-disjoint auxiliary benign select rows and never a report score.
    """

    cache = ckbj.CompositeCanonicalTimeC1Cache(Path(cache_dir), Path(plan), Path(c1_report_extension))
    frontend = ckai.ExternalFlowFrontend(x_by_role, frames, cache)
    sentinel = "__ckbo_global_no_hold__" if held is None else str(held)
    model, audit = ckao.fit_candidate(ckbj.c1_candidate(), frontend, frames, sentinel, int(train_cap))
    idx = ckbj.role_indices(frames, "support_val", "select", held, cko.FULL_CAP)
    if not len(idx):
        raise RuntimeError(f"{held or 'GLOBAL'} has no legal support_val rows for the C1 recall floor")
    values = ckai.score_attack(model, frontend.matrix(ckbj.c1_candidate(), "support_val", idx))
    if not len(values) or not np.isfinite(values).all():
        raise RuntimeError(f"{held or 'GLOBAL'} produced invalid C1 support_val scores")
    threshold = attack_recall_floor_threshold(values)
    retained = values >= threshold
    if not bool(retained.all()):
        raise RuntimeError("C1 attack-preserving threshold did not retain every legal support_val row")
    audit.append(
        {
            "candidate": ckbj.c1_candidate().name,
            "held_field": "device_family",
            "held_value": held or "GLOBAL",
            "role": "support_val",
            "phase": "select",
            "rows_before_exclude": int(len(idx)),
            "rows_after_exclude": int(len(idx)),
            "held_rows_removed": 0,
            "c1_candidate_threshold": threshold,
            "threshold_origin": "minimum_legal_support_val_attack_score_nextafter_negative_infinity",
            "support_val_c1_recall": float(np.mean(retained)),
            "benign_select_rows_used_for_c1_threshold": 0,
            "report_rows_used_for_c1_threshold": 0,
        }
    )
    return model, frontend, threshold, audit


def attack_recall_floor_threshold(values: np.ndarray) -> float:
    scores = np.asarray(values, dtype=np.float64)
    if scores.ndim != 1 or not len(scores) or not np.isfinite(scores).all():
        raise RuntimeError("C1 recall-floor threshold needs finite legal attack scores")
    return float(np.nextafter(float(scores.min()), -np.inf))


def choose_legal_verifier_gate(
    name: str,
    support_val: list[ckbj.Record],
    select_benign: list[ckbj.Record],
    verifier: dict[str, float],
    c1_threshold: float,
) -> tuple[float, list[dict[str, Any]], bool]:
    """Choose a legal gate even for the pre-registered no-aux ablations.

    The corrected frozen 1M scope contains no legal benign select rows after
    the permanent report families are removed.  Auxiliary-enabled candidates
    therefore use the mature CKBM exact attack-preserving/benign-minimizing
    frontier.  A no-aux ablation cannot optimize a benign objective without
    leaking report data, so it uses the most selective support-val-only point
    that satisfies the same attack-preservation constraints.  The selected
    threshold and its attack-only origin are emitted explicitly.
    """

    if select_benign:
        return ckbm.choose_verifier_gate(name, support_val, select_benign, verifier, c1_threshold)
    if not support_val:
        raise RuntimeError(f"{name}: gate selection has no legal support_val rows")
    attack_values = np.asarray([verifier[item.uid] for item in support_val], dtype=np.float64)
    if not np.isfinite(attack_values).all():
        raise RuntimeError(f"{name}: nonfinite support-val-only gate score")
    c1_attack = np.asarray([item.c1_score >= c1_threshold for item in support_val], dtype=bool)
    lower = float(np.nextafter(float(attack_values.min()), -np.inf))
    thresholds = sorted({lower, *(float(value) for value in attack_values.tolist())})
    rows: list[dict[str, Any]] = []
    for threshold in thresholds:
        hard_attack = c1_attack & (attack_values >= threshold)
        base_recall = float(np.mean(c1_attack))
        recall = float(np.mean(hard_attack))
        family_ok = True
        for family in sorted({item.attack_family for item in support_val}):
            mask = np.asarray([item.attack_family == family for item in support_val], dtype=bool)
            if int(mask.sum()) >= 3 and float(np.mean(hard_attack[mask])) < float(np.mean(c1_attack[mask])) - 0.02:
                family_ok = False
        rows.append(
            {
                "candidate": name,
                "verifier_threshold": threshold,
                "threshold_frontier": "exact_support_val_attack_scores_no_legal_benign_select",
                "selection_objective": "maximum_attack_preserving_threshold_without_benign_or_report_scores",
                "support_val_c1_recall": base_recall,
                "support_val_hard_recall": recall,
                "select_benign_hard_rate": math.nan,
                "eligible": bool(recall >= base_recall - 0.005 and family_ok),
                "support_val_rows_used": len(support_val),
                "select_benign_rows_used": 0,
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
    selected = max(eligible, key=lambda row: row["verifier_threshold"])
    selected["selected"] = True
    selected["selected_despite_constraint_failure"] = False
    selected["gate_constraint_pass"] = True
    return float(selected["verifier_threshold"]), rows, True


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
    # Global attack preservation needs attack reports only.  Pulling the
    # generic tail of REPORT_SPECS would also traverse sealed_final_ood and
    # could score the cooler-motor final holdout before a final protocol is
    # authorized.  Strict held protocols include only their named family via
    # ckbj.report_indices; cooler-motor is never a CKBO held value.
    report_specs = report_specs_for_protocol(held)
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
    sealed_scored = [record for record in sets["report"] if record.device_family == "iotsim-cooler-motor"]
    if sealed_scored:
        raise RuntimeError(f"sealed cooler-motor rows entered report scoring: {len(sealed_scored)}")
    return dict(sets), audit


def report_specs_for_protocol(held: str | None) -> tuple[tuple[str, str, int, str], ...]:
    if held is not None:
        return tuple(ckbj.REPORT_SPECS)
    return tuple(spec for spec in ckbj.REPORT_SPECS if int(spec[2]) == 1)


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


def exclude_held_auxiliary(records: Iterable[ckbj.Record], held: str | None) -> list[ckbj.Record]:
    values = list(records)
    if held is None:
        return values
    return [record for record in values if record.device_family != held]


def candidate_record_scope(
    core_records: list[ckbj.Record],
    aux_fit: list[ckbj.Record],
    aux_select: list[ckbj.Record],
    use_auxiliary_benign: bool,
) -> list[ckbj.Record]:
    """Assemble one candidate scope without duplicating protocol reports.

    ``core_records`` already contains the report records for the current
    protocol.  In particular, the predictive-maintenance strict protocol puts
    ``aux_report`` there.  Only fit/select extensions may be appended.
    """

    groups = [core_records]
    if use_auxiliary_benign:
        groups.extend([aux_fit, aux_select])
    return ckbm.unique_records(groups)


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
    c1_model, frontend, c1_threshold, c1_audit = fit_c1_attack_preserving(
        x_by_role,
        model_frames,
        held,
        Path(args.c1_cache),
        Path(args.c1_plan),
        Path(args.c1_report_extension),
        int(args.train_cap),
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
    if held == AUX_HELD_FAMILY:
        sets["report"] = list(aux.records_report)
        data_audit.append(
            {
                "role": "aux_report",
                "frame_phase": "report",
                "m1_phase": "report",
                "held_value": AUX_HELD_FAMILY,
                "eligible_role_rows": len(aux.records_report),
                "frozen_target_rows": len(aux.records_report),
                "outside_frozen_target_cohort": 0,
                "target_alignment_incomplete": 0,
                "requested_rows": len(aux.records_report),
                "cache_aligned_rows": len(aux.records_report),
                "unmapped_rows": 0,
                "label_for_metric_only": 0,
                "report": True,
                "c1_score_contract": "conservative_all_candidate_no_c1_cache",
                "fit_select_use_count": 0,
            }
        )
    headers, schema_sha = afterimage_schema()
    aux_fit = exclude_held_auxiliary(aux.records_fit, held)
    aux_select = exclude_held_auxiliary(aux.records_select, held)
    data_audit.extend(
        [
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
            for role, phase, before, after in (
                ("aux_fit", "fit", aux.records_fit, aux_fit),
                ("aux_select", "select", aux.records_select, aux_select),
            )
        ]
    )
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
        use_aux = bool(spec.use_auxiliary_benign)
        fit_records = sets["fit_attack"] + sets["fit_benign"] + (aux_fit if use_aux else [])
        select_records = sets["select_attack"] + sets["select_benign"] + (aux_select if use_aux else [])
        all_records = candidate_record_scope(core_records, aux_fit, aux_select, use_aux)
        base = existing_feature_map(core_records, x_by_role, spec.representation, headers)
        protocol_aux_report = [record for record in core_records if record.role == "aux_report"]
        add_auxiliary_values(base, aux, spec.representation, protocol_aux_report)
        if use_aux:
            add_auxiliary_values(base, aux, spec.representation, aux_fit + aux_select)
        transformer, prep = generic_preprocessor(fit_records, base, int(args.seed))
        transformed = transform_map(transformer, all_records, base)
        sampled_idx, weights, weight_audit, occurrences = ckbm.balanced_training_sample(fit_records, int(args.seed))
        y = np.asarray([record.label for record in fit_records], dtype=np.int64)[sampled_idx]
        x = ckbm.stack_map(fit_records, transformed)[sampled_idx]
        backend_spec = ckbm.BackendSpec(spec.name, "tabm", "global", spec.primary)
        model, history, model_hash = ckbm.fit_backend(backend_spec, x, y, weights, args, int(args.seed))
        probability = ckbm.backend_scores(model, ckbm.stack_map(all_records, transformed))
        score_map = {record.uid: float(value) for record, value in zip(all_records, probability)}
        threshold, frontier, gate_pass = choose_legal_verifier_gate(
            spec.name,
            sets["select_attack"],
            sets["select_benign"] + (aux_select if use_aux else []),
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
                    "auxiliary_select_rows": len(aux_select) if use_aux else 0,
                    "auxiliary_rows_conservatively_treated_as_c1_candidates": len(aux_select) if use_aux else 0,
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
                "auxiliary_fit_rows": len(aux_fit) if use_aux else 0,
                "auxiliary_held_fit_rows_used": int(
                    sum(held is not None and record.device_family == held for record in aux_fit)
                ) if use_aux else 0,
                "auxiliary_held_select_rows_used": int(
                    sum(held is not None and record.device_family == held for record in aux_select)
                ) if use_aux else 0,
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
                "fit_auxiliary_benign_rows": len(aux_fit) if use_aux else 0,
                "select_auxiliary_benign_rows": len(aux_select) if use_aux else 0,
                "auxiliary_held_fit_rows_used": int(
                    sum(held is not None and record.device_family == held for record in aux_fit)
                ) if use_aux else 0,
                "auxiliary_held_select_rows_used": int(
                    sum(held is not None and record.device_family == held for record in aux_select)
                ) if use_aux else 0,
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
    sealed_audit = [
        {
            "held_value": name,
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
        "sealed_audit": sealed_audit,
    }


def legal_development_holds(frames: dict[str, pd.DataFrame], requested: Iterable[str]) -> list[str]:
    """Return pre-registered non-canary held families with report evidence.

    The permanent canaries are reported separately and never count as the
    additional transfer check.  Cooler-motor is absent from ``HELD`` and stays
    sealed.  A family need not have benign select rows: the entire reason for
    this corrected protocol is that no such rows remain after permanent canary
    exclusion.  It must, however, have immutable report rows and is excluded
    from every model scope by the per-protocol held filter.
    """

    blocked = set(PERMANENT_REPORT_ONLY)
    report_values = {
        str(value)
        for role, frame in frames.items()
        if role in {"id_calib", "ood_val", "ood_stress", "sealed_final_ood"}
        for value in frame.get("device_family", pd.Series(dtype=str)).astype(str)
    }
    values = [
        str(value)
        for value in requested
        if str(value) not in blocked
        and str(value) not in {"", "NA", "nan"}
        and str(value) in report_values
    ]
    if AUX_HELD_FAMILY not in values:
        values.append(AUX_HELD_FAMILY)
    return values


def formal_protocol_values(requested: Iterable[str], dev_holds: list[str]) -> list[str | None]:
    report_canaries = [
        str(value)
        for value in requested
        if str(value) in {"iotsim-stream-consumer", "iotsim-hydraulic-system"}
    ]
    protocols: list[str | None] = [None]
    for value in dev_holds + report_canaries:
        if value not in protocols:
            protocols.append(value)
    expected: list[str | None] = [
        None,
        "iotsim-ip-camera-street",
        AUX_HELD_FAMILY,
        "iotsim-stream-consumer",
        "iotsim-hydraulic-system",
    ]
    if protocols != expected:
        raise RuntimeError(f"formal protocol boundary drift: {protocols} != {expected}")
    return protocols


def prepare_inputs(args: argparse.Namespace, out: Path) -> tuple[Any, ...]:
    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    auxiliary_keys = set(AUX_FIT_SELECT_DEVICE_KEYS) | set(AUX_HELD_DEVICE_KEYS)
    overlap = sorted(
        {
            Path(str(source)).stem
            for frame in frames.values()
            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
            if Path(str(source)).stem in auxiliary_keys
        }
    )
    if overlap:
        raise RuntimeError(f"auxiliary raw PCAP source overlaps the frozen 1M roles: {overlap[:3]}")
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
    dev_rates = {str(row.held_value): float(row.hard_rate) for row in dev.itertuples(index=False)}
    dev_c1_rates = {str(row.held_value): float(row.hard_rate) for row in dev_c1.itertuples(index=False)}
    dev_each_pass = bool(
        len(dev_holds) >= 2
        and all(
            value in dev_rates
            and value in dev_c1_rates
            and dev_rates[value] <= 0.90
            and dev_rates[value] <= dev_c1_rates[value] - 0.05
            for value in dev_holds
        )
    )
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
        "legal_multiheld_signal_missing": bool(
            len(dev_holds) < 2
            or dev_macro is None
            or dev_c1_macro is None
            or dev_macro > dev_c1_macro - 0.05
            or not dev_each_pass
        ),
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
        "legal_development_hard_rates": dev_rates,
        "legal_development_c1_hard_rates": dev_c1_rates,
        "legal_development_each_improves_5pp": dev_each_pass,
        "legal_development_each_at_most_90pct": bool(
            len(dev_holds) >= 2 and all(value in dev_rates and dev_rates[value] <= 0.90 for value in dev_holds)
        ),
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
    if int(args.aux_rows_per_source) != MODEL_READY_PER_SOURCE:
        raise RuntimeError(
            f"formal auxiliary row contract drift: {args.aux_rows_per_source} != {MODEL_READY_PER_SOURCE}"
        )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    assert_clean_formal_out(out)
    vendor = ckbm.validate_vendor()
    x_by_role, report_frames, input_audit, t0, t0_audit, extension_audit, c1_extension_audit = prepare_inputs(args, out)
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    model_frames, permanent_rows = permanently_mask_frames(report_frames)
    model_frames, frozen_scope_rows = restrict_model_scope_to_frozen_targets(
        model_frames,
        Path(args.c1_targets),
        t0,
    )
    dev_holds = legal_development_holds(report_frames, requested)
    if set(dev_holds) != {"iotsim-ip-camera-street", AUX_HELD_FAMILY}:
        raise RuntimeError(f"formal development held-family boundary drift: {dev_holds}")
    aux = materialize_auxiliary(args, out)
    protocols = formal_protocol_values(requested, dev_holds)
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
        "ckbo_frozen_model_scope_audit.csv": pd.DataFrame(frozen_scope_rows),
        "ckbo_sealed_holdout_audit.csv": table("sealed_audit"),
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
                "scope": "auxiliary_source_disjoint_fit_select_and_predictive_held",
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
                    "sources": SELECT_SOURCE_COUNT if spec.use_auxiliary_benign else 0,
                    "attack_events": 0,
                    "benign_events": len(aux.records_select) if spec.use_auxiliary_benign else 0,
                    "report_only_sources": 0,
                    "held_value": "GLOBAL_ATTACK_PRESERVATION",
                    "protocol_run": "GLOBAL_ATTACK_PRESERVATION",
                    "candidate": spec.name,
                },
                {
                    "record_set": "aux_report",
                    "m1_scope": "report",
                    "events": len(aux.records_report),
                    "sources": HELD_SOURCE_COUNT,
                    "attack_events": 0,
                    "benign_events": len(aux.records_report),
                    "report_only_sources": HELD_SOURCE_COUNT,
                    "held_value": AUX_HELD_FAMILY,
                    "protocol_run": AUX_HELD_FAMILY,
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
        "c1_target_manifest_sha256": sha256_file(Path(args.c1_targets)),
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
            "development_canaries": ["iotsim-stream-consumer", "iotsim-hydraulic-system"],
            "sealed_unopened": ["iotsim-cooler-motor"],
            "original_1m_split_modified": False,
            "auxiliary_extension": aux.ready,
            "input_audit": input_audit,
            "t0_audit": t0_audit,
            "report_extension_audit": extension_audit,
            "c1_report_extension_audit": c1_extension_audit,
            "support_train_contract": "all 385 legal rows in global protocol; every row at least once per epoch",
            "support_val_contract": "69 legal select rows; gate only",
            "c1_threshold_contract": "minimum legal support_val attack score; zero benign/report rows",
            "model_scope_contract": "fit/select rows are restricted to the immutable C1-target and T0-target intersection before held-family filtering/capping",
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
    floor = attack_recall_floor_threshold(np.asarray([0.4, 0.2, 0.8], dtype=np.float64))
    assert floor < 0.2 and bool((np.asarray([0.4, 0.2, 0.8]) >= floor).all())
    synthetic = make_aux_records("source-a", "aux_select", 3)
    assert all(record.c1_score == 1.0 and record.label == 0 for record in synthetic)
    support_only = [
        replace(record, label=1, attack_family="family-a", c1_score=1.0)
        for record in synthetic
    ]
    gate, frontier, gate_pass = choose_legal_verifier_gate(
        "contract-no-aux",
        support_only,
        [],
        {record.uid: score for record, score in zip(support_only, (0.2, 0.4, 0.8))},
        0.5,
    )
    selected = [row for row in frontier if row.get("selected")]
    assert gate_pass and len(selected) == 1 and gate == 0.2
    assert selected[0]["select_benign_rows_used"] == 0 and selected[0]["report_rows_used"] == 0
    global_report_specs = report_specs_for_protocol(None)
    assert global_report_specs and all(int(spec[2]) == 1 for spec in global_report_specs)
    assert not any(spec[0] == "sealed_final_ood" for spec in global_report_specs)
    report_records = make_aux_records("predictive-report", "aux_report", 2, AUX_HELD_FAMILY)
    fit_records = make_aux_records("domotic-fit", "aux_fit", 2, "iotsim-domotic-monitor")
    select_records = make_aux_records("building-select", "aux_select", 2, "iotsim-building-monitor")
    core_with_report = ckbm.unique_records([report_records])
    assembled = candidate_record_scope(core_with_report, fit_records, select_records, True)
    assert len(assembled) == 6 and len({record.uid for record in assembled}) == 6
    assert candidate_record_scope(core_with_report, fit_records, select_records, False) == core_with_report
    assert exclude_held_auxiliary(fit_records, "iotsim-domotic-monitor") == []
    assert exclude_held_auxiliary(select_records, "iotsim-domotic-monitor") == select_records
    assert formal_protocol_values(
        HELD,
        ["iotsim-ip-camera-street", AUX_HELD_FAMILY],
    ) == [
        None,
        "iotsim-ip-camera-street",
        AUX_HELD_FAMILY,
        "iotsim-stream-consumer",
        "iotsim-hydraulic-system",
    ]
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
                {"candidate": PRIMARY, "held_value": "legal-b", "hard_rate": 0.3},
                {"candidate": "M0-C1", "held_value": "legal-b", "hard_rate": 0.5},
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
        ["legal-a", "legal-b"],
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


def scope_audit(args: argparse.Namespace) -> None:
    """Run the real 1M membership audit without model fitting or raw replay."""

    x_by_role, frames, input_audit, _labels = cko.load_role_inputs(False)
    del x_by_role
    ckao.add_family_columns(frames)
    auxiliary_keys = set(AUX_FIT_SELECT_DEVICE_KEYS) | set(AUX_HELD_DEVICE_KEYS)
    overlap = sorted(
        {
            Path(str(source)).stem
            for frame in frames.values()
            for source in frame.get("source_group", pd.Series(dtype=str)).astype(str)
            if Path(str(source)).stem in auxiliary_keys
        }
    )
    if overlap:
        raise RuntimeError(f"real scope auxiliary source overlap: {overlap[:3]}")
    masked, permanent = permanently_mask_frames(frames)
    t0 = T0Cache(Path(args.t0_root))
    scoped, rows = restrict_model_scope_to_frozen_targets(
        masked,
        Path(args.c1_targets),
        t0,
        allow_local_t0_manifest_proxy=True,
    )
    requested = [value.strip() for value in str(args.held_values).split(",") if value.strip()]
    dev_holds = legal_development_holds(frames, requested)

    def count(role: str, phase: str) -> int:
        return int(scoped[role]["phase"].astype(str).eq(phase).sum())

    payload = {
        "status": "CKBO_REAL_1M_SCOPE_PASS",
        "input_audit": input_audit,
        "support_train_fit_rows": count("support_train", "fit"),
        "support_val_select_rows": count("support_val", "select"),
        "original_benign_fit_rows": sum(count(role, "fit") for role in ckbj.FIT_BENIGN),
        "original_benign_select_rows": sum(count(role, "select") for role in ckbj.SELECT_BENIGN),
        "development_held_families": dev_holds,
        "permanent_report_only": list(PERMANENT_REPORT_ONLY),
        "permanent_fit_select_rows_after_mask": int(
            sum(int(row["fit_select_rows_after_mask"]) for row in permanent)
        ),
        "frozen_scope_rows": rows,
        "c1_target_manifest_sha256": sha256_file(Path(args.c1_targets)),
        "missing_feature_zero_fill": 0,
        "raw_rows_materialized": 0,
        "auxiliary_source_overlap": overlap,
    }
    if payload["support_train_fit_rows"] != 385:
        raise RuntimeError(f"real scope lost support_train rows: {payload['support_train_fit_rows']}")
    if payload["support_val_select_rows"] != 69:
        raise RuntimeError(f"real scope support_val lineage drift: {payload['support_val_select_rows']}")
    if payload["permanent_fit_select_rows_after_mask"] != 0:
        raise RuntimeError("permanent report family survived real scope mask")
    if set(dev_holds) != {"iotsim-ip-camera-street", AUX_HELD_FAMILY}:
        raise RuntimeError(f"real scope development held-family boundary drift: {dev_holds}")
    print(json.dumps(ckbm.json_ready(payload), indent=2, sort_keys=True))


def aux_smoke(args: argparse.Namespace) -> None:
    with zipfile.ZipFile(Path(args.gotham_zip)) as zf:
        info, _family, _role = auxiliary_member_specs(zf)[0]
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
                "auxiliary_held_family": AUX_HELD_FAMILY,
                "auxiliary_sources": FIT_SOURCE_COUNT + SELECT_SOURCE_COUNT + HELD_SOURCE_COUNT,
                "auxiliary_fit_sources": FIT_SOURCE_COUNT,
                "auxiliary_select_sources": SELECT_SOURCE_COUNT,
                "auxiliary_report_sources": HELD_SOURCE_COUNT,
                "auxiliary_rows_per_source": int(args.aux_rows_per_source),
                "original_1m_split_modified": False,
                "formal_job": "result-producing attack preservation, legal multi-held development, and frozen report canaries",
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["contract-unit", "scope-audit", "aux-smoke", "dry-run", "formal"], default="dry-run")
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
    elif args.mode == "scope-audit":
        scope_audit(args)
    elif args.mode == "aux-smoke":
        aux_smoke(args)
    elif args.mode == "formal":
        run_formal(args)
    else:
        dry_run(args)


if __name__ == "__main__":
    main()
