"""CKCZ frozen endpoint-pair conflict-persistence diagnostic.

This program is deliberately read-only with respect to frozen CKBV/CKBW
inputs.  It exports cached endpoint metadata, constructs label-free causal
pair state independently inside each CKBW protocol slice, and enumerates the
four preregistered exact oracle frontiers.  Oracle cuts are diagnostic upper
bounds and are never legal system parameters.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


ISSUE = "issue27ckcz_endpoint_pair_conflict_diagnostic_v1_2026-08-09"
SEED = 27
GLOBAL = "GLOBAL_ATTACK_PRESERVATION"
M7 = "hard__M7-TabM-TailMargin-DualControl"
SCALARS = (
    "pair_conflict_count_so_far",
    "pair_consecutive_conflicts_so_far",
    "pair_conflict_fraction_so_far",
    "pair_conflict_span_seconds_so_far",
)
OOD_PROTOCOL_ROLE = {
    "iotsim-hydraulic-system": "ood_val",
    "iotsim-ip-camera-street": "sealed_final_ood",
    "iotsim-predictive-maintenance": "aux_report",
    "iotsim-stream-consumer": "ood_stress",
}
ATTACK_ROLES = (
    "support_val",
    "same_file_query",
    "future_query",
    "sealed_final_attack",
)
VIEWED_ATTACK_ROLES = (
    "same_file_query",
    "future_query",
    "sealed_final_attack",
)
EXPECTED_PREDICTION_SHA256 = (
    "d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85"
)
EXPECTED_GOTHAM_MANIFEST_SHA256 = (
    "aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22"
)
EXPECTED_AUXILIARY_MANIFEST_SHA256 = (
    "f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43"
)
EXPECTED_PROTOCOL_ROWS = {
    GLOBAL: 251_050,
    "iotsim-hydraulic-system": 10_069,
    "iotsim-ip-camera-street": 10_069,
    "iotsim-predictive-maintenance": 16_069,
    "iotsim-stream-consumer": 10_069,
}
GOTHAM_FIELDS = frozenset(
    {
        "recorded_index",
        "feature_available_time_epoch",
        "target_event_position_within_capture",
        "src_local_id",
        "dst_local_id",
        "causal_features",
        "feature_names",
        "raw_source_path",
    }
)
AUXILIARY_FIELDS = frozenset(
    {
        "target_row",
        "feature_available_time_epoch",
        "target_event_position_within_capture",
        "src_local_id",
        "dst_local_id",
        "causal_features",
        "feature_names",
        "raw_source_path",
    }
)
FINAL_MARKERS = (
    "cooler-motor",
    "seed37",
    "seed_37",
    "seed-37",
    "seed47",
    "seed_47",
    "seed-47",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assert_no_final_text(value: object, context: str) -> None:
    lowered = str(value).lower()
    if any(marker in lowered for marker in FINAL_MARKERS):
        raise RuntimeError(f"FINAL isolation failed in {context}")


def atomic_bytes(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(
        path,
        (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8"),
    )


def union_fields(rows: Sequence[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fields.append(key)
                seen.add(key)
    return fields


def atomic_csv(path: Path, rows: Sequence[dict[str, Any]], *, compress: bool = False) -> None:
    fields = union_fields(rows)
    if not fields:
        raise RuntimeError(f"refusing to write empty CSV: {path}")
    stream = tempfile.SpooledTemporaryFile(mode="w+", encoding="utf-8", newline="", max_size=8 << 20)
    writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    stream.seek(0)
    raw = stream.read().encode("utf-8")
    stream.close()
    atomic_bytes(path, gzip.compress(raw, mtime=0) if compress else raw)
    check = pd.read_csv(path, compression="gzip" if compress else None)
    if len(check) != len(rows) or check.columns.tolist() != fields:
        raise RuntimeError(f"CSV readback failed: {path}")


def atomic_dataframe_csv(path: Path, frame: pd.DataFrame, *, compress: bool = False) -> None:
    if frame.empty or not len(frame.columns):
        raise RuntimeError(f"refusing to write empty DataFrame CSV: {path}")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
    os.close(fd)
    try:
        if compress:
            with open(tmp_name, "wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as zipped:
                    with io.TextIOWrapper(zipped, encoding="utf-8", newline="") as text_handle:
                        frame.to_csv(text_handle, index=False, lineterminator="\n")
        else:
            frame.to_csv(tmp_name, index=False, lineterminator="\n", encoding="utf-8")
        with open(tmp_name, "r+b") as handle:
            os.fsync(handle.fileno())
        check = pd.read_csv(tmp_name, compression="gzip" if compress else None, nrows=5)
        if check.columns.tolist() != frame.columns.tolist():
            raise RuntimeError(f"DataFrame CSV schema readback failed: {path}")
        opener = gzip.open if compress else open
        with opener(tmp_name, "rt", encoding="utf-8", newline="") as handle:
            rows = sum(1 for _ in handle) - 1
        if rows != len(frame):
            raise RuntimeError(f"DataFrame CSV row readback failed: {path}: {rows}/{len(frame)}")
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


class AtomicCsvSink:
    """Streaming atomic CSV writer with deterministic fixed union schema."""

    def __init__(self, path: Path, fields: Sequence[str]) -> None:
        self.path = Path(path)
        self.fields = list(fields)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, self.tmp_name = tempfile.mkstemp(prefix=f".{self.path.name}.", dir=str(self.path.parent))
        self.handle = os.fdopen(fd, "w", encoding="utf-8", newline="")
        self.writer = csv.DictWriter(
            self.handle, fieldnames=self.fields, extrasaction="raise", lineterminator="\n"
        )
        self.writer.writeheader()
        self.rows = 0
        self.closed = False

    def write(self, rows: Iterable[dict[str, Any]]) -> None:
        for row in rows:
            self.writer.writerow(row)
            self.rows += 1

    def close(self) -> None:
        if self.closed:
            return
        try:
            if not self.rows:
                raise RuntimeError(f"refusing to finalize empty streamed CSV: {self.path}")
            self.handle.flush()
            os.fsync(self.handle.fileno())
            self.handle.close()
            with open(self.tmp_name, "r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle)
                header = next(reader)
                count = sum(1 for _ in reader)
            if header != self.fields or count != self.rows:
                raise RuntimeError(f"streamed CSV readback failed: {self.path}")
            os.replace(self.tmp_name, self.path)
            self.closed = True
        finally:
            if not self.handle.closed:
                self.handle.close()
            if os.path.exists(self.tmp_name):
                os.unlink(self.tmp_name)

    def __enter__(self) -> "AtomicCsvSink":
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if exc_type is None:
            self.close()
        else:
            self.handle.close()
            if os.path.exists(self.tmp_name):
                os.unlink(self.tmp_name)


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series.dtype):
        return series.astype(bool)
    mapped = series.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )
    if mapped.isna().any():
        raise RuntimeError(f"invalid boolean values: {sorted(series[mapped.isna()].astype(str).unique())}")
    return mapped.astype(bool)


def load_allowlist(path: Path, expected_sha256: str, kind: str) -> pd.DataFrame:
    assert_no_final_text(path, f"{kind} allowlist path")
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        raise RuntimeError(f"{kind} allowlist SHA drift: {actual}")
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    required = {"source_group"}
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"{kind} allowlist missing fields: {sorted(missing)}")
    if frame["source_group"].duplicated().any():
        raise RuntimeError(f"{kind} allowlist duplicate source")
    for value in frame.astype(str).to_numpy().ravel().tolist():
        assert_no_final_text(value, f"{kind} allowlist")
    return frame


def validate_manifest(
    manifest_path: Path,
    expected_manifest_sha256: str,
    allowlist: pd.DataFrame,
    kind: str,
    expected_sources: int,
    expected_rows: int,
) -> pd.DataFrame:
    actual = sha256_file(manifest_path)
    if actual != expected_manifest_sha256.lower():
        raise RuntimeError(f"{kind} manifest SHA drift: {actual}")
    manifest = pd.read_csv(manifest_path, dtype=str, keep_default_na=False)
    manifest_keys = ["source_group", "source_cache_key", "target_rows", "cache_sha256"]
    missing = set(manifest_keys) - set(manifest.columns)
    if missing:
        raise RuntimeError(f"{kind} manifest missing fields: {sorted(missing)}")
    optional = {"source_cache_key", "target_rows", "cache_sha256"} & set(allowlist.columns)
    if optional and optional != {"source_cache_key", "target_rows", "cache_sha256"}:
        raise RuntimeError(f"{kind} allowlist has incomplete optional manifest contract fields")
    keys = manifest_keys if optional else ["source_group"]
    selected = allowlist[keys].astype(str).merge(
        manifest[manifest_keys].astype(str),
        on=keys,
        how="left",
        indicator=True,
        validate="one_to_one",
    )
    if not selected["_merge"].eq("both").all():
        raise RuntimeError(f"{kind} allowlist is not an exact manifest subset")
    if len(allowlist) != expected_sources:
        raise RuntimeError(f"{kind} source count drift: {len(allowlist)}/{expected_sources}")
    rows = int(pd.to_numeric(selected["target_rows"], errors="raise").sum())
    if rows != expected_rows:
        raise RuntimeError(f"{kind} target count drift: {rows}/{expected_rows}")
    return selected[manifest_keys].copy()


def _expanded_string(values: np.lib.npyio.NpzFile, key: str, count: int) -> np.ndarray:
    array = np.asarray(values[key]).astype(str)
    if array.ndim == 0:
        return np.repeat(str(array.item()), count)
    if array.shape != (count,):
        raise RuntimeError(f"{key} shape drift: {array.shape}/{count}")
    return array


def export_cache_metadata(
    run_root: Path,
    allowlist: pd.DataFrame,
    kind: str,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    cache_dir = Path(run_root) / ("gotham_causal_cache" if kind == "gotham" else "auxiliary_causal_cache")
    expected_fields = GOTHAM_FIELDS if kind == "gotham" else AUXILIARY_FIELDS
    index_name = "recorded_index" if kind == "gotham" else "target_row"
    parts: list[pd.DataFrame] = []
    audits: list[dict[str, Any]] = []
    for item in allowlist.sort_values("source_group", kind="mergesort").itertuples(index=False):
        source = str(item.source_group)
        key = str(item.source_cache_key)
        path = cache_dir / f"{key}.npz"
        assert_no_final_text(path, f"{kind} cache path")
        if not path.is_file():
            raise RuntimeError(f"missing {kind} cache for allowlisted source: {source}")
        actual_sha = sha256_file(path)
        if actual_sha != str(item.cache_sha256).lower():
            raise RuntimeError(f"{kind} cache SHA drift: {source}")
        with np.load(path, allow_pickle=False) as values:
            if frozenset(values.files) != expected_fields:
                raise RuntimeError(f"{kind} NPZ fields drift: {source}: {sorted(values.files)}")
            index = np.asarray(values[index_name], dtype=np.int64)
            count = len(index)
            timestamp = np.asarray(values["feature_available_time_epoch"], dtype=np.float64)
            position = np.asarray(values["target_event_position_within_capture"], dtype=np.int64)
            src = np.asarray(values["src_local_id"], dtype=np.int64)
            dst = np.asarray(values["dst_local_id"], dtype=np.int64)
            raw_path = _expanded_string(values, "raw_source_path", count)
            features = np.asarray(values["causal_features"])
            names = np.asarray(values["feature_names"]).astype(str)
        expected_count = int(item.target_rows)
        if count != expected_count or any(len(array) != count for array in (timestamp, position, src, dst)):
            raise RuntimeError(f"{kind} NPZ row drift: {source}: {count}/{expected_count}")
        if features.shape != (count, len(names)) or not len(names):
            raise RuntimeError(f"{kind} feature schema drift: {source}: {features.shape}/{len(names)}")
        if len(np.unique(index)) != count:
            raise RuntimeError(f"{kind} target index collision: {source}")
        part = pd.DataFrame(
            {
                "cache_kind": kind,
                "source_group": source,
                "raw_source_path": raw_path,
                "target_index": index,
                "feature_available_time_epoch": timestamp,
                "target_event_position_within_capture": position,
                "src_local_id": src,
                "dst_local_id": dst,
            }
        )
        parts.append(part)
        audits.append(
            {
                "cache_kind": kind,
                "source_group": source,
                "source_cache_key": key,
                "target_rows": count,
                "cache_sha256": actual_sha,
                "nonfinite_timestamp_rows": int((~np.isfinite(timestamp)).sum()),
                "target_index_unique": True,
                "schema_pass": True,
            }
        )
    frame = pd.concat(parts, ignore_index=True)
    return frame, audits


def pair_cardinality(metadata: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    pair_sizes: list[dict[str, Any]] = []
    group_cols = ["cache_kind", "source_group"]
    for (kind, source), part in metadata.groupby(group_cols, sort=True):
        directed = part.groupby(
            ["raw_source_path", "src_local_id", "dst_local_id"], sort=False
        ).size()
        lo = np.minimum(part["src_local_id"].to_numpy(), part["dst_local_id"].to_numpy())
        hi = np.maximum(part["src_local_id"].to_numpy(), part["dst_local_id"].to_numpy())
        unordered_frame = part[["raw_source_path"]].copy()
        unordered_frame["endpoint_lo"] = lo
        unordered_frame["endpoint_hi"] = hi
        unordered = unordered_frame.groupby(
            ["raw_source_path", "endpoint_lo", "endpoint_hi"], sort=False
        ).size()
        rows.append(
            {
                "cache_kind": kind,
                "source_group": source,
                "target_rows": len(part),
                "members": int(part["raw_source_path"].nunique()),
                "directed_pairs": len(directed),
                "unordered_pairs": len(unordered),
                "directed_singleton_pairs": int(directed.eq(1).sum()),
                "directed_singleton_fraction": float(directed.eq(1).mean()),
                "unordered_singleton_pairs": int(unordered.eq(1).sum()),
                "unordered_singleton_fraction": float(unordered.eq(1).mean()),
            }
        )
        counts = Counter(directed.astype(int).tolist())
        for target_count, pairs in sorted(counts.items()):
            pair_sizes.append(
                {
                    "cache_kind": kind,
                    "source_group": source,
                    "directed_pair_target_count": target_count,
                    "directed_pairs": pairs,
                }
            )
    return rows, pair_sizes


def metadata_temporal_audit(metadata: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (kind, source, member), part in metadata.groupby(
        ["cache_kind", "source_group", "raw_source_path"], sort=True
    ):
        ordered = part.sort_values("target_event_position_within_capture", kind="mergesort")
        stamps = pd.to_numeric(
            ordered["feature_available_time_epoch"], errors="coerce"
        ).to_numpy(dtype=float)
        finite = stamps[np.isfinite(stamps)]
        rows.append(
            {
                "cache_kind": kind,
                "source_group": source,
                "raw_source_path": member,
                "target_rows": len(part),
                "nonfinite_timestamp_rows": int((~np.isfinite(stamps)).sum()),
                "duplicate_event_positions": int(
                    ordered["target_event_position_within_capture"].duplicated().sum()
                ),
                "timestamp_monotonicity_violations": int(
                    (np.diff(finite) < 0).sum() if len(finite) >= 2 else 0
                ),
                "timestamp_min": float(finite.min()) if len(finite) else math.nan,
                "timestamp_max": float(finite.max()) if len(finite) else math.nan,
                "timestamp_span_seconds": (
                    float(finite.max() - finite.min()) if len(finite) else math.nan
                ),
            }
        )
    return rows


def gini(values: np.ndarray) -> float:
    values = np.asarray(values, dtype=float)
    values = values[np.isfinite(values) & (values >= 0)]
    if not len(values) or float(values.sum()) == 0.0:
        return 0.0
    ordered = np.sort(values)
    index = np.arange(1, len(ordered) + 1, dtype=float)
    return float(
        (2.0 * np.dot(index, ordered) / (len(ordered) * ordered.sum()))
        - (len(ordered) + 1.0) / len(ordered)
    )


def conflict_descriptive_audit(
    state: pd.DataFrame,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    ecdf_rows: list[dict[str, Any]] = []
    for held, protocol in state.groupby("held_value", sort=True):
        valid = protocol.loc[protocol["state_available"].astype(bool)].copy()
        conflict = valid.loc[valid["current_conflict"].astype(bool)].copy()
        pair_counts = conflict.groupby("interaction_key", sort=False).size().to_numpy(dtype=int)
        deltas: list[float] = []
        for _key, part in conflict.groupby("interaction_key", sort=False):
            ordered = part.sort_values(
                ["feature_available_time_epoch", "target_event_position_within_capture", "uid"],
                kind="mergesort",
            )
            stamps = pd.to_numeric(
                ordered["feature_available_time_epoch"], errors="raise"
            ).to_numpy(dtype=float)
            if len(stamps) >= 2:
                deltas.extend(np.diff(stamps).astype(float).tolist())
        delta_array = np.sort(np.asarray(deltas, dtype=float))
        median = float(np.median(delta_array)) if len(delta_array) else math.nan
        mad = (
            float(np.median(np.abs(delta_array - median)))
            if len(delta_array) else math.nan
        )
        summaries.append(
            {
                "held_value": held,
                "rows": len(protocol),
                "state_available_rows": len(valid),
                "current_conflict_rows": len(conflict),
                "pairs_with_conflict": len(pair_counts),
                "conflict_concentration_gini": gini(pair_counts),
                "conflict_delta_count": len(delta_array),
                "conflict_delta_median_seconds": median,
                "conflict_delta_mad_seconds": mad,
                "max_consecutive_conflicts": int(
                    pd.to_numeric(
                        valid["pair_consecutive_conflicts_so_far"], errors="coerce"
                    ).max()
                    if len(valid) else 0
                ),
            }
        )
        for index, value in enumerate(delta_array, start=1):
            ecdf_rows.append(
                {
                    "held_value": held,
                    "rank": index,
                    "delta_seconds": float(value),
                    "ecdf": index / len(delta_array),
                }
            )
    if not ecdf_rows:
        ecdf_rows.append(
            {
                "held_value": "NO_CONFLICT_DELTAS",
                "rank": 0,
                "delta_seconds": math.nan,
                "ecdf": math.nan,
            }
        )
    return summaries, ecdf_rows


def validate_predictions(path: Path, expected_sha256: str = EXPECTED_PREDICTION_SHA256) -> pd.DataFrame:
    assert_no_final_text(path, "prediction path")
    actual = sha256_file(path)
    if actual != expected_sha256.lower():
        raise RuntimeError(f"prediction SHA drift: {actual}")
    frame = pd.read_csv(path)
    required = {
        "held_value", "uid", "role", "source_group", "device_family", "attack_family",
        "label_metric_only", "c1_hard", M7, "review",
    }
    missing = required - set(frame.columns)
    if missing:
        raise RuntimeError(f"prediction fields missing: {sorted(missing)}")
    counts = frame.groupby("held_value", sort=True).size().to_dict()
    if counts != EXPECTED_PROTOCOL_ROWS:
        raise RuntimeError(f"prediction protocol counts drift: {counts}")
    if frame.duplicated(["held_value", "uid"]).any():
        raise RuntimeError("prediction UID collision inside held protocol")
    if bool_series(frame["review"]).any():
        raise RuntimeError("review must remain false")
    return frame


def _prediction_target_index(row: pd.Series) -> tuple[str, int | None]:
    uid = str(row["uid"])
    role = str(row["role"])
    source = str(row["source_group"])
    if uid.startswith("ton:"):
        return "missing", None
    pieces = uid.split(":")
    try:
        index = int(pieces[-1])
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"UID target index parse failed: {uid}") from exc
    if uid.startswith("aux:"):
        if len(pieces) < 4 or pieces[1] != role or ":".join(pieces[2:-1]) != source:
            raise RuntimeError(f"auxiliary UID contract failed: {uid}")
        return "auxiliary", index
    if len(pieces) != 3 or pieces[0] != role:
        raise RuntimeError(f"Gotham UID contract failed: {uid}")
    return "gotham", index


def join_predictions(predictions: pd.DataFrame, metadata: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    classified = predictions.apply(_prediction_target_index, axis=1, result_type="expand")
    work = predictions.copy()
    work["cache_kind"] = classified[0]
    work["target_index"] = classified[1].astype("Int64")
    work["_row_id"] = np.arange(len(work), dtype=np.int64)
    meta_keys = ["cache_kind", "source_group", "target_index"]
    if metadata.duplicated(meta_keys).any():
        raise RuntimeError("metadata collision on cache/source/target index")
    joined = work.merge(metadata, on=meta_keys, how="left", validate="many_to_one", indicator=True)
    joined["metadata_matched"] = joined["_merge"].eq("both")
    expected_missing = joined["cache_kind"].eq("missing")
    unexpected_missing = ~joined["metadata_matched"] & ~expected_missing
    if unexpected_missing.any():
        sample = joined.loc[unexpected_missing, ["held_value", "uid", "source_group"]].head(10)
        raise RuntimeError(f"unexpected metadata join miss:\n{sample.to_string(index=False)}")
    audits: list[dict[str, Any]] = []
    for held, part in joined.groupby("held_value", sort=True):
        audits.append(
            {
                "held_value": held,
                "rows": len(part),
                "unique_uid": int(part["uid"].nunique()),
                "metadata_matched": int(part["metadata_matched"].sum()),
                "metadata_unmatched": int((~part["metadata_matched"]).sum()),
                "ton_expected_unmatched": int(part["cache_kind"].eq("missing").sum()),
                "unexpected_unmatched": int((~part["metadata_matched"] & ~part["cache_kind"].eq("missing")).sum()),
            }
        )
    return joined.drop(columns="_merge"), audits


def _interaction_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["cache_kind"].astype(str) + "\x1f" + frame["source_group"].astype(str) + "\x1f"
        + frame["raw_source_path"].astype(str) + "\x1f" + frame["src_local_id"].astype("Int64").astype(str)
        + "\x1f" + frame["dst_local_id"].astype("Int64").astype(str)
    )


def build_causal_pair_state(joined: pd.DataFrame) -> pd.DataFrame:
    forbidden = {"label_metric_only", "role", "attack_family", "device_family", "review"}
    state_input = joined.drop(columns=[column for column in forbidden if column in joined.columns]).copy()
    state_input["c1_hard"] = bool_series(state_input["c1_hard"])
    state_input[M7] = bool_series(state_input[M7])
    state_input["current_conflict"] = state_input["c1_hard"] & ~state_input[M7]
    state_input["state_available"] = (
        state_input["metadata_matched"]
        & np.isfinite(pd.to_numeric(state_input["feature_available_time_epoch"], errors="coerce"))
    )
    state_input["interaction_key"] = ""
    available = state_input["state_available"]
    state_input.loc[available, "interaction_key"] = _interaction_key(state_input.loc[available])
    outputs: list[pd.DataFrame] = []
    for held, protocol in state_input.groupby("held_value", sort=True):
        valid = protocol.loc[protocol["state_available"]].copy()
        valid = valid.sort_values(
            ["interaction_key", "feature_available_time_epoch", "target_event_position_within_capture", "uid"],
            kind="mergesort",
        )
        result_rows: list[dict[str, Any]] = []
        for key, part in valid.groupby("interaction_key", sort=False):
            conflict_count = 0
            consecutive = 0
            target_count = 0
            first_conflict_time: float | None = None
            for row in part.to_dict("records"):
                target_count += 1
                conflict = bool(row["current_conflict"])
                if conflict:
                    conflict_count += 1
                    consecutive += 1
                    if first_conflict_time is None:
                        first_conflict_time = float(row["feature_available_time_epoch"])
                    span = (
                        float(row["feature_available_time_epoch"]) - first_conflict_time
                        if conflict_count >= 2 else 0.0
                    )
                else:
                    consecutive = 0
                    span = 0.0
                result_rows.append(
                    {
                        "_row_id": int(row["_row_id"]),
                        "interaction_key": key,
                        "pair_target_count_so_far": target_count,
                        "pair_conflict_count_so_far": conflict_count,
                        "pair_consecutive_conflicts_so_far": consecutive,
                        "pair_conflict_fraction_so_far": conflict_count / target_count,
                        "pair_conflict_span_seconds_so_far": span,
                    }
                )
        state = pd.DataFrame(
            result_rows,
            columns=[
                "_row_id", "interaction_key", "pair_target_count_so_far",
                "pair_conflict_count_so_far", "pair_consecutive_conflicts_so_far",
                "pair_conflict_fraction_so_far", "pair_conflict_span_seconds_so_far",
            ],
        )
        base = protocol.merge(state, on="_row_id", how="left", suffixes=("", "_state"), validate="one_to_one")
        if "interaction_key_state" in base:
            base.loc[base["state_available"], "interaction_key"] = base.loc[
                base["state_available"], "interaction_key_state"
            ]
            base = base.drop(columns="interaction_key_state")
        for scalar in SCALARS:
            base[scalar] = pd.to_numeric(base[scalar], errors="coerce")
        outputs.append(base)
    state_only = pd.concat(outputs, ignore_index=True).sort_values("_row_id", kind="mergesort")
    metric_columns = ["_row_id", "label_metric_only", "role", "attack_family", "device_family", "review"]
    result = state_only.merge(joined[metric_columns], on="_row_id", how="left", validate="one_to_one")
    if len(result) != len(joined):
        raise RuntimeError("state row preservation failed")
    return result


@dataclass(frozen=True)
class MetricGroup:
    name: str
    kind: str
    mask: np.ndarray


def metric_groups(frame: pd.DataFrame) -> list[MetricGroup]:
    held = frame["held_value"].astype(str).to_numpy()
    role = frame["role"].astype(str).to_numpy()
    label = pd.to_numeric(frame["label_metric_only"], errors="raise").to_numpy() == 1
    attack_family = frame["attack_family"].astype(str).to_numpy()
    groups = [MetricGroup("attack_overall", "attack", (held == GLOBAL) & label)]
    for attack_role in ATTACK_ROLES:
        groups.append(
            MetricGroup(f"attack_role:{attack_role}", "attack_role", (held == GLOBAL) & label & (role == attack_role))
        )
    global_attack = (held == GLOBAL) & label
    for family in sorted(pd.unique(attack_family[global_attack])):
        groups.append(MetricGroup(f"attack_family:{family}", "attack_family", global_attack & (attack_family == family)))
    for protocol, pool_role in OOD_PROTOCOL_ROLE.items():
        groups.append(MetricGroup(f"ood_pool:{protocol}", "ood_pool", (held == protocol) & ~label & (role == pool_role)))
    return groups


def exact_cuts(frame: pd.DataFrame, scalar: str) -> np.ndarray:
    held = frame["held_value"].astype(str)
    role = frame["role"].astype(str)
    viewed = (held == GLOBAL) & role.isin(VIEWED_ATTACK_ROLES)
    for protocol, pool_role in OOD_PROTOCOL_ROLE.items():
        viewed |= (held == protocol) & role.eq(pool_role)
    eligible = frame["state_available"] & frame["current_conflict"] & viewed
    values = pd.to_numeric(frame.loc[eligible, scalar], errors="coerce").to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    unique = np.unique(values)[::-1]
    return np.concatenate(([math.inf], unique))


def _curve_for_group(
    frame: pd.DataFrame, group: MetricGroup, scalar: str, cuts: np.ndarray
) -> tuple[np.ndarray, np.ndarray, int, int]:
    mask = group.mask
    total = int(mask.sum())
    if not total:
        raise RuntimeError(f"required metric group empty: {group.name}")
    base = bool_series(frame[M7]).to_numpy()
    c1 = bool_series(frame["c1_hard"]).to_numpy()
    eligible = (
        mask & frame["state_available"].to_numpy(dtype=bool)
        & frame["current_conflict"].to_numpy(dtype=bool)
    )
    values = pd.to_numeric(frame[scalar], errors="coerce").to_numpy(dtype=float)
    increments = np.zeros(len(cuts), dtype=np.int64)
    for value in values[eligible]:
        index = int(np.searchsorted(-cuts[1:], -float(value), side="left")) + 1
        if index < len(cuts):
            increments[index] += 1
    hard = int(base[mask].sum()) + np.cumsum(increments)
    return hard / total, increments, total, int(c1[mask].sum())


def _activation_ranks(values: np.ndarray, cuts: np.ndarray) -> np.ndarray:
    """First frontier index at which value >= cut; len(cuts) means never."""
    result = np.searchsorted(-cuts[1:], -values.astype(float), side="left") + 1
    return result.astype(np.int64)


def first_trigger_audit(frame: pd.DataFrame, scalar: str, cuts: np.ndarray) -> dict[str, np.ndarray]:
    """Aggregate causal first-veto delay over VIEWED report-attack pairs.

    Delay is measured from a pair's first current conflict to its first veto.
    The implementation records pair counts, total preceding conflict misses,
    and mean delay; it does not select a cut or summarize by family.
    """
    held = frame["held_value"].astype(str)
    role = frame["role"].astype(str)
    label = pd.to_numeric(frame["label_metric_only"], errors="raise").eq(1)
    viewed_attack = held.eq(GLOBAL) & role.isin(VIEWED_ATTACK_ROLES) & label
    conflict = frame["current_conflict"].astype(bool)
    available = frame["state_available"].astype(bool)
    work = frame.loc[viewed_attack & conflict & available].copy()
    n = len(cuts)
    pair_delta = np.zeros(n, dtype=np.int64)
    miss_delta = np.zeros(n, dtype=np.int64)
    delay_delta = np.zeros(n, dtype=np.float64)
    if work.empty:
        return {
            "triggered_pairs": pair_delta,
            "preceding_conflict_misses": miss_delta,
            "mean_time_to_first_veto_seconds": np.full(n, np.nan),
        }
    work = work.sort_values(
        ["interaction_key", "feature_available_time_epoch", "target_event_position_within_capture", "uid"],
        kind="mergesort",
    )
    for _key, part in work.groupby("interaction_key", sort=False):
        values = pd.to_numeric(part[scalar], errors="raise").to_numpy(dtype=float)
        stamps = pd.to_numeric(part["feature_available_time_epoch"], errors="raise").to_numpy(dtype=float)
        ranks = _activation_ranks(values, cuts)
        best_position: int | None = None
        best_delay = 0.0
        # At each newly reached threshold, only an earlier event can improve
        # the first trigger.  Multiple events activating at the same rank are
        # collapsed before updating the global difference arrays.
        for rank in sorted(set(int(value) for value in ranks if int(value) < n)):
            positions = np.flatnonzero(ranks == rank)
            candidate = int(positions.min())
            if best_position is None:
                pair_delta[rank] += 1
                miss_delta[rank] += candidate
                delay = float(stamps[candidate] - stamps[0])
                delay_delta[rank] += delay
                best_position = candidate
                best_delay = delay
            elif candidate < best_position:
                miss_delta[rank] += candidate - best_position
                delay = float(stamps[candidate] - stamps[0])
                delay_delta[rank] += delay - best_delay
                best_position = candidate
                best_delay = delay
    triggered = np.cumsum(pair_delta)
    misses = np.cumsum(miss_delta)
    delay_sum = np.cumsum(delay_delta)
    mean_delay = np.divide(
        delay_sum,
        triggered,
        out=np.full(n, np.nan, dtype=float),
        where=triggered > 0,
    )
    return {
        "triggered_pairs": triggered,
        "preceding_conflict_misses": misses,
        "mean_time_to_first_veto_seconds": mean_delay,
    }


def rescued_viewed_curve(frame: pd.DataFrame, scalar: str, cuts: np.ndarray) -> np.ndarray:
    held = frame["held_value"].astype(str)
    role = frame["role"].astype(str)
    viewed = held.eq(GLOBAL) & role.isin(VIEWED_ATTACK_ROLES)
    for protocol, pool_role in OOD_PROTOCOL_ROLE.items():
        viewed |= held.eq(protocol) & role.eq(pool_role)
    eligible = (
        viewed.to_numpy(dtype=bool)
        & frame["state_available"].to_numpy(dtype=bool)
        & frame["current_conflict"].to_numpy(dtype=bool)
    )
    values = pd.to_numeric(frame.loc[eligible, scalar], errors="raise").to_numpy(dtype=float)
    ranks = _activation_ranks(values, cuts)
    increments = np.bincount(ranks[ranks < len(cuts)], minlength=len(cuts))
    return np.cumsum(increments).astype(np.int64)


def _cluster_labels(frame: pd.DataFrame, unit: str) -> np.ndarray:
    if unit == "source":
        return (
            frame["held_value"].astype(str) + "\x1f" + frame["source_group"].astype(str)
        ).to_numpy()
    if unit != "pair":
        raise ValueError(f"unknown bootstrap cluster unit: {unit}")
    labels = (
        frame["held_value"].astype(str) + "\x1f" + frame["interaction_key"].astype(str)
    )
    missing = ~frame["state_available"].astype(bool)
    labels.loc[missing] = (
        frame.loc[missing, "held_value"].astype(str)
        + "\x1fmissing\x1f" + frame.loc[missing, "uid"].astype(str)
    )
    return labels.to_numpy()


def bootstrap_curve_replicates(
    frame: pd.DataFrame,
    mask: np.ndarray,
    scalar: str,
    cuts: np.ndarray,
    unit: str,
    reps: int,
    seed: int,
) -> tuple[np.ndarray, int]:
    part = frame.loc[mask].copy()
    if part.empty:
        raise RuntimeError("bootstrap group is empty")
    labels = _cluster_labels(part, unit)
    codes, unique = pd.factorize(labels, sort=True)
    clusters = len(unique)
    if not clusters:
        raise RuntimeError("bootstrap cluster set is empty")
    base = bool_series(part[M7]).to_numpy(dtype=np.int8)
    eligible = (
        part["state_available"].to_numpy(dtype=bool)
        & part["current_conflict"].to_numpy(dtype=bool)
    )
    scalar_values = pd.to_numeric(part[scalar], errors="coerce").to_numpy(dtype=float)
    eligible &= np.isfinite(scalar_values)
    ranks = _activation_ranks(scalar_values[eligible], cuts)
    eligible_positions = np.flatnonzero(eligible)
    kept = ranks < len(cuts)
    ranks = ranks[kept]
    eligible_positions = eligible_positions[kept]
    rng = np.random.default_rng(int(seed))
    curves = np.empty((int(reps), len(cuts)), dtype=np.float32)
    for replicate in range(int(reps)):
        sampled = rng.integers(0, clusters, size=clusters)
        cluster_weights = np.bincount(sampled, minlength=clusters).astype(np.int64)
        weights = cluster_weights[codes]
        denominator = int(weights.sum())
        if denominator <= 0:
            raise RuntimeError("bootstrap sampled zero rows")
        base_hard = int(np.dot(weights, base))
        increments = np.bincount(
            ranks,
            weights=weights[eligible_positions],
            minlength=len(cuts),
        )
        curves[replicate] = (base_hard + np.cumsum(increments)) / denominator
    return curves, clusters


def bootstrap_interval_rows(
    frame: pd.DataFrame,
    scalar: str,
    cuts: np.ndarray,
    reps: int,
    seed: int,
) -> Iterable[dict[str, Any]]:
    groups = {group.name: group.mask for group in metric_groups(frame)}
    named_masks = {
        "attack_overall_recall": groups["attack_overall"],
        "future_attack_recall": groups["attack_role:future_query"],
        "same_file_attack_recall": groups["attack_role:same_file_query"],
        "sealed_attack_recall": groups["attack_role:sealed_final_attack"],
        "support_val_recall": groups["attack_role:support_val"],
    }
    pool_masks = [groups[f"ood_pool:{protocol}"] for protocol in OOD_PROTOCOL_ROLE]
    for unit_index, unit in enumerate(("source", "pair")):
        for metric_index, (metric, mask) in enumerate(named_masks.items()):
            curves, clusters = bootstrap_curve_replicates(
                frame, mask, scalar, cuts, unit, reps,
                int(seed) + 10_000 * unit_index + 100 * metric_index,
            )
            low, high = np.quantile(curves, [0.025, 0.975], axis=0)
            for index, cut in enumerate(cuts):
                yield {
                    "scalar": scalar,
                    "frontier_index": index,
                    "cut": float(cut),
                    "metric": metric,
                    "cluster_unit": unit,
                    "clusters": clusters,
                    "pool_cluster_counts": "",
                    "bootstrap_reps": int(reps),
                    "ci_low": float(low[index]),
                    "ci_high": float(high[index]),
                }
        macro = np.zeros((int(reps), len(cuts)), dtype=np.float32)
        pool_clusters: list[int] = []
        for pool_index, mask in enumerate(pool_masks):
            curves, clusters = bootstrap_curve_replicates(
                frame, mask, scalar, cuts, unit, reps,
                int(seed) + 10_000 * unit_index + 2_000 + 100 * pool_index,
            )
            macro += curves / len(pool_masks)
            pool_clusters.append(clusters)
        low, high = np.quantile(macro, [0.025, 0.975], axis=0)
        for index, cut in enumerate(cuts):
            yield {
                "scalar": scalar,
                "frontier_index": index,
                "cut": float(cut),
                "metric": "ood_macro_hard_rate",
                "cluster_unit": unit,
                "clusters": min(pool_clusters),
                "pool_cluster_counts": json.dumps(pool_clusters, separators=(",", ":")),
                "bootstrap_reps": int(reps),
                "ci_low": float(low[index]),
                "ci_high": float(high[index]),
            }


def oracle_frontier(
    frame: pd.DataFrame, scalar: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], bool, np.ndarray]:
    cuts = exact_cuts(frame, scalar)
    groups = metric_groups(frame)
    curves: dict[str, np.ndarray] = {}
    totals: dict[str, int] = {}
    c1_counts: dict[str, int] = {}
    for group in groups:
        curve, _increments, total, c1_count = _curve_for_group(frame, group, scalar, cuts)
        curves[group.name] = curve
        totals[group.name] = total
        c1_counts[group.name] = c1_count
    rescued = rescued_viewed_curve(frame, scalar, cuts)
    trigger = first_trigger_audit(frame, scalar, cuts)
    metadata_missing = ~frame["metadata_matched"].to_numpy(dtype=bool)
    missing_rows = int(metadata_missing.sum())
    missing_m7_hard = int(bool_series(frame[M7]).to_numpy()[metadata_missing].sum())
    family_names = [group.name for group in groups if group.kind == "attack_family"]
    pool_names = [group.name for group in groups if group.kind == "ood_pool"]
    frontier: list[dict[str, Any]] = []
    families: list[dict[str, Any]] = []
    pools: list[dict[str, Any]] = []
    feasible_any = False
    for index, cut in enumerate(cuts):
        family_delta = {
            name: 100.0 * (curves[name][index] - c1_counts[name] / totals[name])
            for name in family_names if totals[name] >= 15
        }
        ood_rates = [curves[name][index] for name in pool_names]
        future = curves["attack_role:future_query"][index]
        support = curves["attack_role:support_val"][index]
        feasible = bool(
            future >= 0.8483
            and family_delta
            and min(family_delta.values()) >= -2.0
            and support == 1.0
            and float(np.mean(ood_rates)) <= 0.3027
        )
        feasible_any |= feasible
        frontier.append(
            {
                "scalar": scalar,
                "frontier_index": index,
                "cut": float(cut),
                "cut_use": "FORBIDDEN_FOR_SELECTION",
                "attack_overall_recall": float(curves["attack_overall"][index]),
                "future_attack_recall": float(future),
                "same_file_attack_recall": float(curves["attack_role:same_file_query"][index]),
                "sealed_attack_recall": float(curves["attack_role:sealed_final_attack"][index]),
                "support_val_recall": float(support),
                "ood_macro_hard_rate": float(np.mean(ood_rates)),
                "worst_family_delta_vs_c1_pp": (
                    float(min(family_delta.values())) if family_delta else math.nan
                ),
                "rescued_viewed_rows": int(rescued[index]),
                "metadata_missing_rows_kept_at_m7": missing_rows,
                "metadata_missing_m7_hard_rows": missing_m7_hard,
                "attack_pairs_with_veto": int(trigger["triggered_pairs"][index]),
                "attack_conflict_misses_before_first_veto": int(
                    trigger["preceding_conflict_misses"][index]
                ),
                "mean_time_to_first_veto_seconds": float(
                    trigger["mean_time_to_first_veto_seconds"][index]
                ),
                "oracle_compatible": feasible,
                "review_rate": 0.0,
            }
        )
        for name in family_names:
            families.append(
                {
                    "scalar": scalar,
                    "frontier_index": index,
                    "cut": float(cut),
                    "attack_family": name.split(":", 1)[1],
                    "rows": totals[name],
                    "hard_recall": float(curves[name][index]),
                    "c1_hard_recall": c1_counts[name] / totals[name],
                    "delta_vs_c1_pp": 100.0 * (curves[name][index] - c1_counts[name] / totals[name]),
                }
            )
        for name in pool_names:
            pools.append(
                {
                    "scalar": scalar,
                    "frontier_index": index,
                    "cut": float(cut),
                    "ood_pool": name.split(":", 1)[1],
                    "rows": totals[name],
                    "hard_rate": float(curves[name][index]),
                }
            )
    return frontier, families, pools, feasible_any, cuts


def run(args: argparse.Namespace) -> dict[str, Any]:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise RuntimeError(f"CKCZ output directory must start empty: {out}")
    stage = "validate_inputs"
    try:
        run_root = Path(args.ckbv_root)
        for value, context in (
            (run_root, "CKBV root"), (args.predictions, "predictions"),
            (args.gotham_allowlist, "Gotham allowlist"),
            (args.auxiliary_allowlist, "auxiliary allowlist"),
            (args.preregistered_protocol, "preregistered protocol"),
        ):
            assert_no_final_text(value, context)
        protocol_sha = sha256_file(Path(args.preregistered_protocol))
        if protocol_sha != str(args.preregistered_protocol_sha256).lower():
            raise RuntimeError(f"preregistered protocol SHA drift: {protocol_sha}")
        gotham_allow = load_allowlist(Path(args.gotham_allowlist), args.gotham_allowlist_sha256, "gotham")
        auxiliary_allow = load_allowlist(Path(args.auxiliary_allowlist), args.auxiliary_allowlist_sha256, "auxiliary")
        gotham_allow = validate_manifest(
            run_root / "ckbu_gotham_unified_causal_manifest.csv",
            args.gotham_manifest_sha256, gotham_allow, "gotham",
            int(args.gotham_sources), int(args.gotham_rows),
        )
        auxiliary_allow = validate_manifest(
            run_root / "ckbu_auxiliary_unified_causal_manifest.csv",
            args.auxiliary_manifest_sha256, auxiliary_allow, "auxiliary",
            int(args.auxiliary_sources), int(args.auxiliary_rows),
        )
        stage = "validate_schema"
        gotham_meta, gotham_audit = export_cache_metadata(run_root, gotham_allow, "gotham")
        auxiliary_meta, auxiliary_audit = export_cache_metadata(run_root, auxiliary_allow, "auxiliary")
        metadata = pd.concat([gotham_meta, auxiliary_meta], ignore_index=True)
        stage = "export_metadata"
        atomic_dataframe_csv(out / "ckcz_target_metadata.csv.gz", metadata, compress=True)
        stage = "pair_cardinality"
        by_source, distribution = pair_cardinality(metadata)
        atomic_csv(out / "ckcz_pair_cardinality_by_source.csv", by_source)
        atomic_csv(out / "ckcz_pair_cardinality_distribution.csv", distribution)
        atomic_csv(out / "ckcz_metadata_temporal_audit.csv", metadata_temporal_audit(metadata))
        stage = "join_predictions"
        predictions = validate_predictions(Path(args.predictions), args.predictions_sha256)
        joined, join_audit = join_predictions(predictions, metadata)
        atomic_csv(out / "ckcz_prediction_join_audit.csv", join_audit)
        stage = "build_causal_state"
        state = build_causal_pair_state(joined)
        atomic_dataframe_csv(out / "ckcz_pair_state_rows.csv.gz", state, compress=True)
        conflict_summary, conflict_ecdf = conflict_descriptive_audit(state)
        atomic_csv(out / "ckcz_conflict_descriptive_audit.csv", conflict_summary)
        atomic_csv(out / "ckcz_conflict_delta_time_ecdf.csv", conflict_ecdf)
        stage = "oracle_frontiers"
        scalar_feasible: dict[str, bool] = {}
        if int(args.bootstrap_reps) < 20:
            raise RuntimeError("bootstrap_reps must be at least 20")
        bootstrap_fields = [
            "scalar", "frontier_index", "cut", "metric", "cluster_unit", "clusters",
            "pool_cluster_counts", "bootstrap_reps", "ci_low", "ci_high",
        ]
        expected_bootstrap_rows = 0
        with AtomicCsvSink(out / "ckcz_bootstrap_intervals.csv", bootstrap_fields) as bootstrap_sink:
            for scalar_index, scalar in enumerate(SCALARS):
                frontier, families, pools, feasible, cuts = oracle_frontier(state, scalar)
                scalar_feasible[scalar] = feasible
                atomic_csv(out / f"ckcz_oracle_frontier_{scalar}.csv", frontier)
                atomic_csv(out / f"ckcz_attack_family_metrics_{scalar}.csv", families)
                atomic_csv(out / f"ckcz_ood_pool_metrics_{scalar}.csv", pools)
                expected_bootstrap_rows += 12 * len(cuts)
                bootstrap_sink.write(
                    bootstrap_interval_rows(
                        state, scalar, cuts, int(args.bootstrap_reps),
                        int(args.seed) + 100_000 * scalar_index,
                    )
                )
        if bootstrap_sink.rows != expected_bootstrap_rows:
            raise RuntimeError(
                f"bootstrap frontier coverage drift: {bootstrap_sink.rows}/{expected_bootstrap_rows}"
            )
        verdict = {
            "status": (
                "CKCZ_ORACLE_INFORMATION_EXISTS_LEGAL_NOT_TESTED"
                if any(scalar_feasible.values()) else "CKCZ_ORACLE_NO_INFORMATION"
            ),
            "scalar_oracle_compatible": scalar_feasible,
            "bootstrap_complete": True,
            "bootstrap_reps": int(args.bootstrap_reps),
            "scientific_verdict_valid": True,
        }
        audit = {
            "status": "CKCZ_INPUT_CONTRACT_PASS",
            "gotham": gotham_audit,
            "auxiliary": auxiliary_audit,
            "prediction_sha256": sha256_file(Path(args.predictions)),
            "final_markers_loaded": False,
        }
        atomic_json(out / "ckcz_input_audit.json", audit)
        atomic_csv(out / "ckcz_source_allowlist_audit.csv", gotham_audit + auxiliary_audit)
        stage = "validate_outputs"
        run_spec = {
            "issue": ISSUE,
            "seed": int(args.seed),
            "frozen_preregistered_protocol": str(args.preregistered_protocol),
            "frozen_preregistered_protocol_sha256": protocol_sha,
            "hpc_submission_authorized": False,
            "bootstrap_reps": int(args.bootstrap_reps),
            "bootstrap_complete": True,
            "scientific_verdict_valid": True,
        }
        atomic_json(out / "run_spec.json", run_spec)
        required = {
            "ckcz_input_audit.json",
            "ckcz_source_allowlist_audit.csv",
            "ckcz_target_metadata.csv.gz",
            "ckcz_pair_cardinality_by_source.csv",
            "ckcz_pair_cardinality_distribution.csv",
            "ckcz_metadata_temporal_audit.csv",
            "ckcz_prediction_join_audit.csv",
            "ckcz_pair_state_rows.csv.gz",
            "ckcz_conflict_descriptive_audit.csv",
            "ckcz_conflict_delta_time_ecdf.csv",
            "ckcz_bootstrap_intervals.csv",
            "run_spec.json",
        }
        for scalar in SCALARS:
            required.update(
                {
                    f"ckcz_oracle_frontier_{scalar}.csv",
                    f"ckcz_attack_family_metrics_{scalar}.csv",
                    f"ckcz_ood_pool_metrics_{scalar}.csv",
                }
            )
        actual_names = {path.name for path in out.iterdir() if path.is_file()}
        if not required.issubset(actual_names):
            raise RuntimeError(f"required CKCZ outputs missing: {sorted(required - actual_names)}")
        if any(not (out / name).is_file() or (out / name).stat().st_size <= 0 for name in required):
            raise RuntimeError("required CKCZ output is empty")
        atomic_json(out / "ckcz_verdict.json", verdict)
        output_files = sorted(path for path in out.iterdir() if path.is_file() and path.name != "SHA256SUMS")
        sums = "".join(f"{sha256_file(path)}  {path.name}\n" for path in output_files)
        atomic_bytes(out / "SHA256SUMS", sums.encode("utf-8"))
        return verdict
    except Exception as exc:
        verdict_path = out / "ckcz_verdict.json"
        if verdict_path.exists():
            verdict_path.unlink()
        atomic_json(
            out / "job_failure.txt",
            {"status": "CKCZ_ENGINEERING_FAILURE", "stage": stage, "error_type": type(exc).__name__, "error": str(exc)},
        )
        raise


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--ckbv-root", type=Path, required=True)
    result.add_argument("--predictions", type=Path, required=True)
    result.add_argument("--gotham-allowlist", type=Path, required=True)
    result.add_argument("--auxiliary-allowlist", type=Path, required=True)
    result.add_argument("--gotham-allowlist-sha256", required=True)
    result.add_argument("--auxiliary-allowlist-sha256", required=True)
    result.add_argument("--gotham-manifest-sha256", default=EXPECTED_GOTHAM_MANIFEST_SHA256)
    result.add_argument("--auxiliary-manifest-sha256", default=EXPECTED_AUXILIARY_MANIFEST_SHA256)
    result.add_argument("--predictions-sha256", default=EXPECTED_PREDICTION_SHA256)
    result.add_argument("--gotham-sources", type=int, default=24)
    result.add_argument("--gotham-rows", type=int, default=317_523)
    result.add_argument("--auxiliary-sources", type=int, default=31)
    result.add_argument("--auxiliary-rows", type=int, default=18_600)
    result.add_argument("--seed", type=int, default=SEED)
    result.add_argument("--bootstrap-reps", type=int, default=200)
    result.add_argument("--preregistered-protocol", type=Path, required=True)
    result.add_argument("--preregistered-protocol-sha256", required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


def main() -> None:
    args = parser().parse_args()
    verdict = run(args)
    print(json.dumps(verdict, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
