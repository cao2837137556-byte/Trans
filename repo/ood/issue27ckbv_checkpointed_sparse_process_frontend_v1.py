"""CKBV execution repair for the frozen CKBU unified process experiment.

This module does not change the CKBU feature schema, target rows, data roles,
model, seed, or decision rule.  It fixes two execution defects:

1. Gotham PCAPs are checkpointed per archive member and can be resumed exactly.
2. Full 51-D features are emitted only for frozen target candidates.  Every
   other packet still performs the same causal state pruning and update.

The sparse path is therefore an execution optimization, not a new scientific
feature.  Unit tests compare it bit-for-bit with the original dense path at
selected events.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import signal
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbu_parallel_cache_resume_v1 as resume  # noqa: E402
import issue27ckbu_unified_tshark_causal_frontend_v1 as ckbu  # noqa: E402


ISSUE = "issue27ckbv_checkpointed_sparse_process_frontend_v1_2026-07-25"
MEMBER_STATUS = "CKBV_GOTHAM_MEMBER_COMPLETE"
TON_FILE_STATUS = "CKBV_TON_FILE_COMPLETE"
PROGRESS_EVERY_DEFAULT = 250_000


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    ckbu.dump_json(temporary, value)
    os.replace(temporary, path)


def atomic_npz(path: Path, **arrays: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("wb") as handle:
        np.savez_compressed(handle, **arrays)
    os.replace(temporary, path)


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def prune_before_update(
    builder: ckbu.CausalFeatureBuilder, event: ckbu.PacketEvent
) -> None:
    """Apply only the non-observational maintenance performed by ``emit``."""
    builder._prune_times(builder.source_times, event.timestamp)
    endpoint = builder.endpoints.setdefault(event.src, ckbu.EndpointState())
    builder._prune_endpoint(endpoint.recent, event.timestamp)


def matcher_candidates(
    matcher: ckbu.TargetMatcher, event: ckbu.PacketEvent
) -> set[int]:
    key = int(round(event.timestamp * 1_000_000.0))
    return {
        index
        for index in matcher.by_time.get(key, [])
        if matcher.compatible(matcher.targets[index], event)
    }


def sparse_selected_transform(
    events: Sequence[ckbu.PacketEvent], selected_positions: set[int]
) -> dict[int, np.ndarray]:
    """Reference helper used by the bit-exact sparse/dense regression test."""
    builder = ckbu.CausalFeatureBuilder()
    selected: dict[int, np.ndarray] = {}
    for position, event in enumerate(events):
        if position in selected_positions:
            selected[position] = builder.emit(event).copy()
        else:
            prune_before_update(builder, event)
        builder.update(event)
    return selected


def process_gotham_member_sparse(
    rows: Iterable[dict[str, str]],
    member: str,
    matcher: ckbu.TargetMatcher,
    progress_every: int,
) -> dict[str, Any]:
    builder = ckbu.CausalFeatureBuilder()
    decoded = 0
    emitted = 0
    timestamp_violations = 0
    previous = -math.inf
    started = time.monotonic()
    print(f"CKBV_MEMBER_START member={member}", flush=True)
    for position, row in enumerate(rows):
        event = ckbu.event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        timestamp_violations += int(event.timestamp < previous)
        previous = max(previous, event.timestamp)
        candidates = matcher_candidates(matcher, event)
        if candidates:
            feature = builder.emit(event)
            emitted += 1
        else:
            prune_before_update(builder, event)
            feature = None
        src_id, dst_id = builder.update(event)
        if feature is not None:
            matcher.observe(member, position, event, feature, src_id, dst_id)
        decoded += 1
        if progress_every > 0 and decoded % progress_every == 0:
            elapsed = max(time.monotonic() - started, 1e-9)
            print(
                "CKBV_MEMBER_PROGRESS "
                f"member={member} decoded={decoded} sparse_emits={emitted} "
                f"events_per_second={decoded / elapsed:.3f}",
                flush=True,
            )
    elapsed = time.monotonic() - started
    print(
        "CKBV_MEMBER_SCAN_COMPLETE "
        f"member={member} decoded={decoded} sparse_emits={emitted} "
        f"seconds={elapsed:.3f}",
        flush=True,
    )
    return {
        "raw_source_path": member,
        "decoded_events": decoded,
        "sparse_feature_emits": emitted,
        "source_local_nodes": len(builder.nodes),
        "recorded_order_timestamp_violations": timestamp_violations,
        "fresh_source_reset": True,
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "raw_label_column_read": False,
        "event_schema": "TShark 4.6.6 packet fields",
        "feature_schema_dim": len(ckbu.FEATURE_NAMES),
        "execution_only_sparse_emit": True,
        "seconds": elapsed,
    }


def member_key(source: str, member: str, crc: int, size: int) -> str:
    return ckbu.stable_key(f"{source}\x1f{member}\x1f{int(crc)}\x1f{int(size)}")


def plan_gotham_members(args: argparse.Namespace) -> None:
    source_plan = read_csv_rows(Path(args.source_plan))
    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        info = {item.filename: item for item in archive.infolist()}
        for source_index, source_row in enumerate(source_plan):
            source = str(source_row["source_group"])
            members = json.loads(source_row["pcap_members_json"])
            for within_source, member in enumerate(members):
                if member not in info:
                    raise RuntimeError(f"planned Gotham member missing: {member}")
                item = info[member]
                rows.append(
                    {
                        "member_index": len(rows),
                        "source_index": source_index,
                        "source_group": source,
                        "source_cache_key": source_row["source_cache_key"],
                        "source_target_rows": int(source_row["target_rows"]),
                        "member_within_source": within_source,
                        "archive_member": member,
                        "member_cache_key": member_key(
                            source, member, item.CRC, item.file_size
                        ),
                        "archive_crc32": int(item.CRC),
                        "uncompressed_bytes": int(item.file_size),
                        "compressed_bytes": int(item.compress_size),
                        "raw_label_column_read": False,
                    }
                )
    if not rows:
        raise RuntimeError("empty Gotham member plan")
    out = Path(args.member_plan)
    ckbu.write_csv(out, rows)
    atomic_json(
        out.with_suffix(".json"),
        {
            "status": "CKBV_GOTHAM_MEMBER_PLAN_READY",
            "members": len(rows),
            "sources": len(source_plan),
            "uncompressed_bytes": sum(int(row["uncompressed_bytes"]) for row in rows),
            "compressed_bytes": sum(int(row["compressed_bytes"]) for row in rows),
            "member_plan_sha256": ckbu.sha256_file(out),
            "source_plan_sha256": ckbu.sha256_file(Path(args.source_plan)),
            "checkpoint_granularity": "archive_member",
            "raw_label_column_read": False,
            "scientific_protocol_changed": False,
        },
    )
    print(
        json.dumps(
            {
                "status": "CKBV_GOTHAM_MEMBER_PLAN_READY",
                "members": len(rows),
                "sources": len(source_plan),
                "member_plan": str(out),
            },
            indent=2,
        ),
        flush=True,
    )


def member_paths(cache: Path, key: str) -> tuple[Path, Path]:
    return Path(cache) / f"{key}.npz", Path(cache) / f"{key}.json"


def validate_member_pair(
    row: dict[str, Any], cache: Path, member_plan_sha256: str
) -> tuple[bool, str]:
    npz, meta = member_paths(Path(cache), str(row["member_cache_key"]))
    if not npz.is_file() or not meta.is_file():
        return False, "missing_pair"
    try:
        summary = json.loads(meta.read_text(encoding="utf-8"))
        if summary.get("status") != MEMBER_STATUS:
            return False, "status"
        exact = {
            "source_group": str(row["source_group"]),
            "source_cache_key": str(row["source_cache_key"]),
            "archive_member": str(row["archive_member"]),
            "member_cache_key": str(row["member_cache_key"]),
            "archive_crc32": int(row["archive_crc32"]),
            "uncompressed_bytes": int(row["uncompressed_bytes"]),
            "member_plan_sha256": str(member_plan_sha256),
        }
        for name, expected in exact.items():
            if summary.get(name) != expected:
                return False, f"{name}_drift"
        if bool(summary.get("raw_label_column_read", True)):
            return False, "raw_label"
        if summary.get("cache_sha256") != ckbu.sha256_file(npz):
            return False, "sha256"
        with np.load(npz, allow_pickle=False) as values:
            features = values["causal_features"]
            names = values["feature_names"].astype(str).tolist()
            recorded = values["recorded_index"]
            raw = values["raw_source_path"].astype(str)
            required = (
                "feature_available_time_epoch",
                "target_event_position_within_capture",
                "src_local_id",
                "dst_local_id",
            )
            if any(name not in values for name in required):
                return False, "schema"
        if features.shape != (len(recorded), len(ckbu.FEATURE_NAMES)):
            return False, "shape"
        if names != ckbu.FEATURE_NAMES:
            return False, "feature_names"
        if len(raw) != len(recorded) or any(
            value != str(row["archive_member"]) for value in raw
        ):
            return False, "member_path"
        if len(set(recorded.astype(int).tolist())) != len(recorded):
            return False, "duplicate_within_member"
    except Exception as exc:
        return False, f"exception:{type(exc).__name__}"
    return True, "ok"


def materialize_gotham_member(args: argparse.Namespace) -> None:
    plan = read_csv_rows(Path(args.member_plan))
    index = int(args.member_index)
    if index < 0 or index >= len(plan):
        raise RuntimeError(f"member index outside plan: {index}/{len(plan)}")
    row = plan[index]
    if int(row["member_index"]) != index:
        raise RuntimeError("member plan index drift")
    member_plan_sha256 = ckbu.sha256_file(Path(args.member_plan))
    valid, reason = validate_member_pair(row, Path(args.member_cache), member_plan_sha256)
    if valid:
        print(
            f"CKBV_MEMBER_REUSED index={index} member={row['archive_member']}",
            flush=True,
        )
        return
    if reason != "missing_pair":
        raise RuntimeError(f"invalid existing member checkpoint: {index}: {reason}")

    targets = ckbu.load_target_indices([Path(path) for path in args.targets])
    source = str(row["source_group"])
    if source not in targets:
        raise RuntimeError(f"member source has no frozen targets: {source}")
    started = time.time()
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        member = str(row["archive_member"])
        info = archive.getinfo(member)
        if (
            int(info.CRC) != int(row["archive_crc32"])
            or int(info.file_size) != int(row["uncompressed_bytes"])
        ):
            raise RuntimeError(f"archive member identity drift: {member}")
        fingerprints = ckbu.read_gotham_target_fingerprints(
            archive, source, targets[source]
        )
        matcher = ckbu.TargetMatcher(
            fingerprints, int(args.alignment_tolerance_us)
        )
        audit = process_gotham_member_sparse(
            ckbu.iter_tshark_rows(
                args.tshark, archive=archive, member=member
            ),
            member,
            matcher,
            int(args.progress_every),
        )
    if matcher.ambiguous:
        recorded = [
            fingerprints[item].recorded_index for item in sorted(matcher.ambiguous)
        ]
        raise RuntimeError(
            f"ambiguous target alignment within member {member}: {recorded[:8]}"
        )
    selected: list[dict[str, Any]] = []
    for target_index, values in matcher.matches.items():
        raw, position, feature, available, src_id, dst_id = values
        target = fingerprints[target_index]
        selected.append(
            {
                "recorded_index": int(target.recorded_index),
                "feature_available_time_epoch": float(available),
                "target_event_position_within_capture": int(position),
                "src_local_id": int(src_id),
                "dst_local_id": int(dst_id),
                "feature": np.asarray(feature, dtype=np.float32),
                "raw_source_path": str(raw),
            }
        )
    selected.sort(key=lambda item: int(item["recorded_index"]))
    if selected:
        features = np.vstack([item["feature"] for item in selected]).astype(
            np.float32
        )
    else:
        features = np.empty((0, len(ckbu.FEATURE_NAMES)), dtype=np.float32)
    npz, meta = member_paths(Path(args.member_cache), str(row["member_cache_key"]))
    atomic_npz(
        npz,
        recorded_index=np.asarray(
            [item["recorded_index"] for item in selected], dtype=np.int64
        ),
        feature_available_time_epoch=np.asarray(
            [item["feature_available_time_epoch"] for item in selected],
            dtype=np.float64,
        ),
        target_event_position_within_capture=np.asarray(
            [item["target_event_position_within_capture"] for item in selected],
            dtype=np.int64,
        ),
        src_local_id=np.asarray(
            [item["src_local_id"] for item in selected], dtype=np.int32
        ),
        dst_local_id=np.asarray(
            [item["dst_local_id"] for item in selected], dtype=np.int32
        ),
        causal_features=features,
        feature_names=np.asarray(ckbu.FEATURE_NAMES),
        raw_source_path=np.asarray(
            [item["raw_source_path"] for item in selected]
        ),
    )
    summary = {
        "status": MEMBER_STATUS,
        "source_group": source,
        "source_cache_key": str(row["source_cache_key"]),
        "archive_member": str(row["archive_member"]),
        "member_cache_key": str(row["member_cache_key"]),
        "archive_crc32": int(row["archive_crc32"]),
        "uncompressed_bytes": int(row["uncompressed_bytes"]),
        "compressed_bytes": int(row["compressed_bytes"]),
        "member_plan_sha256": member_plan_sha256,
        "matched_target_rows": len(selected),
        "matched_recorded_indices": [
            int(item["recorded_index"]) for item in selected
        ],
        "capture_audit": audit,
        "cache_npz": str(npz),
        "cache_sha256": ckbu.sha256_file(npz),
        "feature_schema": ckbu.FEATURE_NAMES,
        "feature_schema_dim": len(ckbu.FEATURE_NAMES),
        "feature_available_time_recorded": True,
        "score_before_update": True,
        "fresh_source_reset": True,
        "raw_label_column_read": False,
        "execution_only_sparse_emit": True,
        "scientific_protocol_changed": False,
        "seconds": time.time() - started,
    }
    atomic_json(meta, summary)
    valid, reason = validate_member_pair(row, Path(args.member_cache), member_plan_sha256)
    if not valid:
        raise RuntimeError(f"new member checkpoint failed validation: {reason}")
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def validate_source_pair(row: dict[str, Any], cache: Path) -> tuple[bool, str]:
    return resume.validate_pair("gotham", row, Path(cache))


def aggregate_one_source(
    source_row: dict[str, Any],
    member_rows: list[dict[str, Any]],
    member_cache: Path,
    source_cache: Path,
    targets: dict[str, set[int]],
    member_plan_sha256: str,
    runtime_dir: Path,
) -> dict[str, Any]:
    source = str(source_row["source_group"])
    key = str(source_row["source_cache_key"])
    existing, _reason = validate_source_pair(source_row, source_cache)
    if existing:
        return {
            "source_group": source,
            "source_cache_key": key,
            "reused_source_cache": True,
            "member_checkpoints": 0,
        }
    parts: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for row in member_rows:
        valid, reason = validate_member_pair(
            row, member_cache, member_plan_sha256
        )
        if not valid:
            raise RuntimeError(
                f"missing/invalid member checkpoint for {source}: "
                f"{row['archive_member']}: {reason}"
            )
        npz, meta = member_paths(member_cache, str(row["member_cache_key"]))
        summary = json.loads(meta.read_text(encoding="utf-8"))
        audits.append(summary["capture_audit"])
        with np.load(npz, allow_pickle=False) as values:
            for index in range(len(values["recorded_index"])):
                parts.append(
                    {
                        "recorded_index": int(values["recorded_index"][index]),
                        "feature_available_time_epoch": float(
                            values["feature_available_time_epoch"][index]
                        ),
                        "target_event_position_within_capture": int(
                            values["target_event_position_within_capture"][index]
                        ),
                        "src_local_id": int(values["src_local_id"][index]),
                        "dst_local_id": int(values["dst_local_id"][index]),
                        "feature": values["causal_features"][index].astype(
                            np.float32, copy=True
                        ),
                        "raw_source_path": str(
                            values["raw_source_path"].astype(str)[index]
                        ),
                    }
                )
    counts = Counter(item["recorded_index"] for item in parts)
    duplicated = sorted(index for index, count in counts.items() if count > 1)
    if duplicated:
        raise RuntimeError(
            f"ambiguous target alignment across members for {source}: "
            f"{duplicated[:8]}"
        )
    expected = set(int(value) for value in targets[source])
    actual = set(counts)
    if actual != expected:
        raise RuntimeError(
            f"incomplete member target coverage for {source}: "
            f"missing={sorted(expected-actual)[:8]} extra={sorted(actual-expected)[:8]}"
        )
    parts.sort(key=lambda item: int(item["recorded_index"]))
    features = np.vstack([item["feature"] for item in parts]).astype(np.float32)
    npz = source_cache / f"{key}.npz"
    meta = source_cache / f"{key}.json"
    atomic_npz(
        npz,
        recorded_index=np.asarray(
            [item["recorded_index"] for item in parts], dtype=np.int64
        ),
        feature_available_time_epoch=np.asarray(
            [item["feature_available_time_epoch"] for item in parts],
            dtype=np.float64,
        ),
        target_event_position_within_capture=np.asarray(
            [item["target_event_position_within_capture"] for item in parts],
            dtype=np.int64,
        ),
        src_local_id=np.asarray(
            [item["src_local_id"] for item in parts], dtype=np.int32
        ),
        dst_local_id=np.asarray(
            [item["dst_local_id"] for item in parts], dtype=np.int32
        ),
        causal_features=features,
        feature_names=np.asarray(ckbu.FEATURE_NAMES),
        raw_source_path=np.asarray(
            [item["raw_source_path"] for item in parts]
        ),
    )
    summary = {
        "status": resume.STATUS_BY_KIND["gotham"],
        "source_group": source,
        "source_cache_key": key,
        "target_rows": len(parts),
        "target_positions_complete": len(parts) == len(expected),
        "candidate_captures_processed": len(member_rows),
        "capture_audit": audits,
        "cache_npz": str(npz),
        "cache_sha256": ckbu.sha256_file(npz),
        "feature_schema": ckbu.FEATURE_NAMES,
        "feature_schema_dim": len(ckbu.FEATURE_NAMES),
        "feature_available_time_recorded": True,
        "score_before_update": True,
        "source_fresh_reset_per_capture": True,
        "raw_label_column_read": False,
        "original_split_modified": False,
        "member_checkpointed": True,
        "execution_only_sparse_emit": True,
        "scientific_protocol_changed": False,
    }
    atomic_json(meta, summary)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    atomic_json(runtime_dir / f"{key}.json", summary)
    valid, reason = validate_source_pair(source_row, source_cache)
    if not valid:
        raise RuntimeError(f"aggregated source cache invalid: {source}: {reason}")
    return {
        "source_group": source,
        "source_cache_key": key,
        "reused_source_cache": False,
        "member_checkpoints": len(member_rows),
    }


def terminate_process_group(process: subprocess.Popen[Any]) -> None:
    if process.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=20)
            return
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    else:
        process.terminate()


def run_member_subprocess(
    args: argparse.Namespace, row: dict[str, Any]
) -> dict[str, Any]:
    index = int(row["member_index"])
    log_dir = Path(args.out) / "member_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{index:04d}_{row['member_cache_key']}.log"
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--mode",
        "materialize-gotham-member",
        "--gotham-zip",
        str(args.gotham_zip),
        "--member-plan",
        str(args.member_plan),
        "--member-index",
        str(index),
        "--member-cache",
        str(args.member_cache),
        "--tshark",
        str(args.tshark),
        "--alignment-tolerance-us",
        str(args.alignment_tolerance_us),
        "--progress-every",
        str(args.progress_every),
    ]
    for target in args.targets:
        command.extend(["--targets", str(target)])
    started = time.monotonic()
    with log.open("w", encoding="utf-8", newline="\n") as handle:
        process = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
        last_size = 0
        last_progress = time.monotonic()
        while process.poll() is None:
            time.sleep(5)
            size = log.stat().st_size if log.exists() else 0
            if size != last_size:
                last_size = size
                last_progress = time.monotonic()
            elapsed = time.monotonic() - started
            if elapsed > float(args.member_timeout_seconds):
                terminate_process_group(process)
                raise RuntimeError(
                    f"member timeout after {elapsed:.1f}s: "
                    f"{row['archive_member']} log={log}"
                )
            if time.monotonic() - last_progress > float(args.stale_seconds):
                terminate_process_group(process)
                raise RuntimeError(
                    f"member progress stale for {args.stale_seconds}s: "
                    f"{row['archive_member']} log={log}"
                )
        code = int(process.returncode or 0)
    if code:
        tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            f"member subprocess failed code={code}: {row['archive_member']}\n{tail}"
        )
    valid, reason = validate_member_pair(
        row, Path(args.member_cache), ckbu.sha256_file(Path(args.member_plan))
    )
    if not valid:
        raise RuntimeError(
            f"member subprocess returned without valid checkpoint: "
            f"{row['archive_member']}: {reason}"
        )
    meta = member_paths(
        Path(args.member_cache), str(row["member_cache_key"])
    )[1]
    summary = json.loads(meta.read_text(encoding="utf-8"))
    return {
        "member_index": index,
        "source_group": str(row["source_group"]),
        "archive_member": str(row["archive_member"]),
        "uncompressed_bytes": int(row["uncompressed_bytes"]),
        "decoded_events": int(summary["capture_audit"]["decoded_events"]),
        "sparse_feature_emits": int(
            summary["capture_audit"]["sparse_feature_emits"]
        ),
        "seconds": float(summary["seconds"]),
        "log_path": str(log),
    }


def run_batch(
    args: argparse.Namespace, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=min(int(args.max_workers), len(rows))) as pool:
        futures = {pool.submit(run_member_subprocess, args, row): row for row in rows}
        for future in as_completed(futures):
            row = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(
                    "CKBV_MEMBER_COMPLETE "
                    f"index={result['member_index']} "
                    f"source={result['source_group']} "
                    f"decoded={result['decoded_events']} "
                    f"seconds={result['seconds']:.3f}",
                    flush=True,
                )
            except Exception as exc:
                failures.append(str(exc))
                print(f"CKBV_MEMBER_FAILED {exc}", file=sys.stderr, flush=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    return results


def copy_valid_member_reuse(
    rows: list[dict[str, Any]],
    destination: Path,
    reuse_dirs: list[Path],
    member_plan_sha256: str,
) -> int:
    destination.mkdir(parents=True, exist_ok=True)
    reused = 0
    for row in rows:
        valid, _ = validate_member_pair(row, destination, member_plan_sha256)
        if valid:
            continue
        for source in reuse_dirs:
            valid, _ = validate_member_pair(row, source, member_plan_sha256)
            if not valid:
                continue
            src_npz, src_meta = member_paths(source, str(row["member_cache_key"]))
            dst_npz, dst_meta = member_paths(
                destination, str(row["member_cache_key"])
            )
            resume.atomic_copy(src_npz, dst_npz)
            resume.atomic_copy(src_meta, dst_meta)
            valid, reason = validate_member_pair(
                row, destination, member_plan_sha256
            )
            if not valid:
                raise RuntimeError(f"copied member reuse invalid: {reason}")
            reused += 1
            break
    return reused


def size_range_calibration(
    sorted_rows: list[dict[str, Any]], requested_count: int
) -> list[dict[str, Any]]:
    if not sorted_rows:
        return []
    count = min(
        len(sorted_rows),
        max(2 if len(sorted_rows) > 1 else 1, int(requested_count)),
    )
    indices = sorted(
        {
            round(index * (len(sorted_rows) - 1) / max(count - 1, 1))
            for index in range(count)
        }
    )
    return [sorted_rows[index] for index in indices]


def run_gotham_members(args: argparse.Namespace) -> None:
    started = time.monotonic()
    source_rows = read_csv_rows(Path(args.source_plan))
    member_rows = read_csv_rows(Path(args.member_plan))
    source_cache = Path(args.source_cache)
    member_cache = Path(args.member_cache)
    source_cache.mkdir(parents=True, exist_ok=True)
    member_cache.mkdir(parents=True, exist_ok=True)
    source_reuse_dirs = [
        Path(value)
        for value in args.reuse_source_cache
        if Path(value).is_dir()
    ]
    member_reuse_dirs = [
        Path(value)
        for value in args.reuse_member_cache
        if Path(value).is_dir()
    ]
    source_audit = resume.reuse_valid_pairs(
        "gotham", source_rows, source_cache, source_reuse_dirs
    )
    member_plan_sha256 = ckbu.sha256_file(Path(args.member_plan))
    reused_members = copy_valid_member_reuse(
        member_rows, member_cache, member_reuse_dirs, member_plan_sha256
    )
    missing_sources = {
        str(row["source_cache_key"])
        for row in source_rows
        if not validate_source_pair(row, source_cache)[0]
    }
    pending = [
        row
        for row in member_rows
        if str(row["source_cache_key"]) in missing_sources
        and not validate_member_pair(row, member_cache, member_plan_sha256)[0]
    ]
    pending.sort(
        key=lambda row: (
            int(row["uncompressed_bytes"]),
            int(row["member_index"]),
        )
    )
    print(
        "CKBV_CHECKPOINT_START "
        f"sources={len(source_rows)} missing_sources={len(missing_sources)} "
        f"members={len(member_rows)} pending_members={len(pending)} "
        f"reused_members={reused_members} workers={args.max_workers}",
        flush=True,
    )
    runtimes: list[dict[str, Any]] = []
    calibration = size_range_calibration(pending, int(args.max_workers))
    calibration_count = len(calibration)
    if calibration:
        # Calibrate on the size range, not only on the easiest members.  The
        # predecessor launched the largest sources first and then ran for
        # 17 hours without one checkpoint.  A smallest-only calibration would
        # repeat the same optimism defect.
        runtimes.extend(run_batch(args, calibration))
        elapsed = time.monotonic() - started
        completed_indices = {int(item["member_index"]) for item in runtimes}
        remaining = [
            row
            for row in pending
            if int(row["member_index"]) not in completed_indices
        ]
        total_bytes = sum(int(item["uncompressed_bytes"]) for item in runtimes)
        cpu_seconds = sum(max(float(item["seconds"]), 1e-6) for item in runtimes)
        bytes_per_cpu_second = total_bytes / cpu_seconds
        remaining_bytes = sum(int(row["uncompressed_bytes"]) for row in remaining)
        projected_wall = (
            remaining_bytes
            / max(bytes_per_cpu_second, 1e-9)
            / max(int(args.max_workers), 1)
            * float(args.projection_safety_factor)
        )
        available = max(float(args.available_seconds) - elapsed, 0.0)
        projection = {
            "status": "CKBV_THROUGHPUT_PROJECTION",
            "calibration_members": calibration_count,
            "calibration_member_indices": [
                int(row["member_index"]) for row in calibration
            ],
            "calibration_uncompressed_bytes": total_bytes,
            "calibration_cpu_seconds": cpu_seconds,
            "bytes_per_cpu_second": bytes_per_cpu_second,
            "remaining_members": len(remaining),
            "remaining_uncompressed_bytes": remaining_bytes,
            "projection_safety_factor": float(args.projection_safety_factor),
            "projected_remaining_wall_seconds": projected_wall,
            "available_remaining_seconds": available,
            "projection_pass": projected_wall <= available * 0.75,
        }
        atomic_json(Path(args.out) / "ckbv_throughput_projection.json", projection)
        print(json.dumps(projection, indent=2, sort_keys=True), flush=True)
        if not projection["projection_pass"]:
            raise RuntimeError(
                "projected Gotham member runtime exceeds 75% of remaining "
                "allocation; refusing another non-finishing run"
            )
        remaining.sort(
            key=lambda row: (-int(row["uncompressed_bytes"]), int(row["member_index"]))
        )
        for start in range(0, len(remaining), int(args.max_workers)):
            runtimes.extend(
                run_batch(args, remaining[start : start + int(args.max_workers)])
            )

    targets = ckbu.load_target_indices([Path(path) for path in args.targets])
    by_source: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in member_rows:
        by_source[str(row["source_cache_key"])].append(row)
    aggregation: list[dict[str, Any]] = []
    for row in source_rows:
        aggregation.append(
            aggregate_one_source(
                row,
                by_source[str(row["source_cache_key"])],
                member_cache,
                source_cache,
                targets,
                member_plan_sha256,
                Path(args.out) / "source_runtime",
            )
        )
        print(
            "CKBV_SOURCE_CACHE_READY "
            f"source={row['source_group']} "
            f"reused={aggregation[-1]['reused_source_cache']}",
            flush=True,
        )
    invalid = [
        f"{row['source_group']}:{validate_source_pair(row, source_cache)[1]}"
        for row in source_rows
        if not validate_source_pair(row, source_cache)[0]
    ]
    if invalid:
        raise RuntimeError(f"incomplete Gotham source cache: {invalid}")
    if runtimes:
        ckbu.write_csv(
            Path(args.out) / "ckbv_member_runtime.csv",
            sorted(runtimes, key=lambda item: int(item["member_index"])),
        )
    ckbu.write_csv(Path(args.out) / "ckbv_source_reuse_audit.csv", source_audit)
    ckbu.write_csv(Path(args.out) / "ckbv_source_aggregation_audit.csv", aggregation)
    summary = {
        "status": "CKBV_GOTHAM_CHECKPOINT_COMPLETE",
        "sources": len(source_rows),
        "members": len(member_rows),
        "reused_source_caches": sum(
            bool(item["reused_source_cache"]) for item in aggregation
        ),
        "reused_member_caches": reused_members,
        "materialized_member_caches": len(runtimes),
        "checkpoint_granularity": "archive_member",
        "execution_only_sparse_emit": True,
        "sparse_dense_equivalence_unit_tested": True,
        "raw_label_column_read": False,
        "scientific_protocol_changed": False,
        "seconds": time.monotonic() - started,
    }
    atomic_json(Path(args.out) / "ckbv_gotham_checkpoint_ready.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def reservoir_event_ordinals(total: int, budget: int, seed: int) -> list[int]:
    if total < budget:
        raise RuntimeError(f"capture shorter than budget: {total}/{budget}")
    rng = np.random.default_rng(int(seed))
    reservoir: list[int] = []
    for event_index in range(int(total)):
        events = event_index + 1
        if len(reservoir) < budget:
            reservoir.append(event_index)
        else:
            replacement = int(rng.integers(0, events))
            if replacement < budget:
                reservoir[replacement] = event_index
    return sorted(reservoir)


def count_finite_timestamps(
    tshark: str, pcap: Path, progress_every: int
) -> int:
    command = [
        str(tshark),
        "-n",
        "-r",
        str(pcap),
        "-T",
        "fields",
        "-e",
        "frame.time_epoch",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert process.stdout is not None
    count = 0
    for line in process.stdout:
        value = ckbu.as_float(line.strip(), math.nan)
        if math.isfinite(value):
            count += 1
            if progress_every > 0 and count % progress_every == 0:
                print(
                    f"CKBV_TON_COUNT_PROGRESS file={pcap.name} events={count}",
                    flush=True,
                )
    stderr = process.stderr.read() if process.stderr is not None else ""
    code = process.wait()
    if code:
        raise RuntimeError(f"TShark count pass exited {code}: {stderr[-2000:]}")
    return count


def process_ton_normal_sparse(
    args: argparse.Namespace, name: str, role: str
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    path = Path(args.ton_pilot_dir) / name
    total = count_finite_timestamps(
        args.tshark, path, int(args.progress_every)
    )
    selected_ordinals = set(
        reservoir_event_ordinals(total, int(args.ton_normal_budget), int(args.seed))
    )
    builder = ckbu.CausalFeatureBuilder()
    selected: list[dict[str, Any]] = []
    event_ordinal = 0
    started = time.monotonic()
    for position, row in enumerate(
        ckbu.iter_tshark_rows(args.tshark, pcap_path=path)
    ):
        event = ckbu.event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        choose = event_ordinal in selected_ordinals
        if choose:
            feature = builder.emit(event)
        else:
            prune_before_update(builder, event)
            feature = None
        src_id, dst_id = builder.update(event)
        if feature is not None:
            selected.append(
                {
                    "record_id": f"ton_normal:{Path(name).stem}:{position}",
                    "role": role,
                    "source_file": name,
                    "mechanism_family": "benign",
                    "label": 0,
                    "feature_available_time_epoch": event.timestamp,
                    "target_event_position_within_capture": position,
                    "src_local_id": src_id,
                    "dst_local_id": dst_id,
                    "feature": feature.copy(),
                }
            )
        event_ordinal += 1
        if (
            int(args.progress_every) > 0
            and event_ordinal % int(args.progress_every) == 0
        ):
            print(
                "CKBV_TON_FEATURE_PROGRESS "
                f"file={name} events={event_ordinal} selected={len(selected)}",
                flush=True,
            )
    if event_ordinal != total or len(selected) != int(args.ton_normal_budget):
        raise RuntimeError(
            f"ToN normal two-pass drift: {name}: "
            f"events={event_ordinal}/{total} selected={len(selected)}"
        )
    return selected, {
        "raw_source_path": name,
        "decoded_events": event_ordinal,
        "reservoir_rows": len(selected),
        "reservoir_seed": int(args.seed),
        "source_local_nodes": len(builder.nodes),
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "raw_label_column_read": False,
        "execution_only_sparse_emit": True,
        "two_pass_exact_reservoir": True,
        "seconds": time.monotonic() - started,
    }


def process_ton_attack_sparse(
    args: argparse.Namespace,
    name: str,
    targets: list[ckbu.TonConnectionTarget],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key: defaultdict[
        tuple[str, str, int, str, int], list[ckbu.TonConnectionTarget]
    ] = defaultdict(list)
    for target in targets:
        by_key[target.direct_key].append(target)
        by_key[target.reverse_key].append(target)
    builder = ckbu.CausalFeatureBuilder()
    events = 0
    emitted = 0
    path = Path(args.ton_pilot_dir) / name
    started = time.monotonic()
    for position, row in enumerate(
        ckbu.iter_tshark_rows(args.tshark, pcap_path=path)
    ):
        event = ckbu.event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        candidates: dict[str, ckbu.TonConnectionTarget] = {}
        for key in ckbu.event_connection_keys(event):
            for target in by_key.get(key, []):
                if target.start - 0.01 <= event.timestamp <= target.stop + 0.01:
                    candidates[target.record_id] = target
        if candidates:
            feature = builder.emit(event)
            emitted += 1
        else:
            prune_before_update(builder, event)
            feature = None
        src_id, dst_id = builder.update(event)
        if feature is not None:
            for target in candidates.values():
                if (
                    not math.isfinite(target.matched_time)
                    or event.timestamp >= target.matched_time
                ):
                    target.matched_feature = feature.copy()
                    target.matched_time = event.timestamp
                    target.matched_position = position
                    target.src_local_id = src_id
                    target.dst_local_id = dst_id
        events += 1
        if (
            int(args.progress_every) > 0
            and events % int(args.progress_every) == 0
        ):
            print(
                "CKBV_TON_ATTACK_PROGRESS "
                f"file={name} events={events} sparse_emits={emitted}",
                flush=True,
            )
    missing = [
        target.record_id for target in targets if target.matched_feature is None
    ]
    if missing:
        raise RuntimeError(
            f"ToN attack PCAP alignment incomplete: {name}: {missing[:8]}"
        )
    positions = [int(target.matched_position) for target in targets]
    duplicates = [
        value for value, count in Counter(positions).items() if count > 1
    ]
    if duplicates:
        raise RuntimeError(
            f"ToN targets collapsed onto a packet: {name}: {duplicates[:8]}"
        )
    selected = [
        {
            "record_id": target.record_id,
            "role": target.role,
            "source_file": name,
            "mechanism_family": target.mechanism_family,
            "label": 1,
            "feature_available_time_epoch": target.matched_time,
            "target_event_position_within_capture": target.matched_position,
            "src_local_id": target.src_local_id,
            "dst_local_id": target.dst_local_id,
            "feature": target.matched_feature,
        }
        for target in targets
    ]
    return selected, {
        "raw_source_path": name,
        "decoded_events": events,
        "selected_attack_connections": len(selected),
        "target_alignment_complete": True,
        "target_event_positions_unique": True,
        "source_local_nodes": len(builder.nodes),
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "explicit_zeek_log_emission_time_used": False,
        "raw_label_column_read": False,
        "execution_only_sparse_emit": True,
        "sparse_feature_emits": emitted,
        "seconds": time.monotonic() - started,
    }


def ton_file_key(name: str, path: Path) -> str:
    return ckbu.stable_key(f"{name}\x1f{path.stat().st_size}")


def ton_file_paths(cache: Path, name: str, path: Path) -> tuple[Path, Path]:
    key = ton_file_key(name, path)
    return Path(cache) / f"{key}.npz", Path(cache) / f"{key}.json"


def validate_ton_file_pair(
    cache: Path, name: str, path: Path, role: str, expected_rows: int
) -> tuple[bool, str]:
    npz, meta = ton_file_paths(cache, name, path)
    if not npz.is_file() or not meta.is_file():
        return False, "missing_pair"
    try:
        summary = json.loads(meta.read_text(encoding="utf-8"))
        if (
            summary.get("status") != TON_FILE_STATUS
            or summary.get("source_file") != name
            or summary.get("role") != role
            or int(summary.get("input_bytes", -1)) != path.stat().st_size
            or int(summary.get("rows", -1)) != expected_rows
            or bool(summary.get("raw_label_column_read", True))
            or summary.get("cache_sha256") != ckbu.sha256_file(npz)
        ):
            return False, "metadata"
        with np.load(npz, allow_pickle=False) as values:
            shape = tuple(values["causal_features"].shape)
            names = values["feature_names"].astype(str).tolist()
            if shape != (expected_rows, len(ckbu.FEATURE_NAMES)):
                return False, "shape"
            if names != ckbu.FEATURE_NAMES:
                return False, "feature_names"
    except Exception as exc:
        return False, f"exception:{type(exc).__name__}"
    return True, "ok"


def save_ton_file(
    cache: Path,
    name: str,
    role: str,
    path: Path,
    rows: list[dict[str, Any]],
    audit: dict[str, Any],
) -> None:
    npz, meta = ton_file_paths(cache, name, path)
    features = np.vstack([row["feature"] for row in rows]).astype(np.float32)
    atomic_npz(
        npz,
        record_id=np.asarray([row["record_id"] for row in rows]),
        role=np.asarray([row["role"] for row in rows]),
        source_file=np.asarray([row["source_file"] for row in rows]),
        mechanism_family=np.asarray(
            [row["mechanism_family"] for row in rows]
        ),
        label=np.asarray([row["label"] for row in rows], dtype=np.int8),
        feature_available_time_epoch=np.asarray(
            [row["feature_available_time_epoch"] for row in rows],
            dtype=np.float64,
        ),
        target_event_position_within_capture=np.asarray(
            [row["target_event_position_within_capture"] for row in rows],
            dtype=np.int64,
        ),
        src_local_id=np.asarray(
            [row["src_local_id"] for row in rows], dtype=np.int32
        ),
        dst_local_id=np.asarray(
            [row["dst_local_id"] for row in rows], dtype=np.int32
        ),
        causal_features=features,
        feature_names=np.asarray(ckbu.FEATURE_NAMES),
    )
    atomic_json(
        meta,
        {
            "status": TON_FILE_STATUS,
            "source_file": name,
            "role": role,
            "input_bytes": path.stat().st_size,
            "rows": len(rows),
            "cache_npz": str(npz),
            "cache_sha256": ckbu.sha256_file(npz),
            "capture_audit": audit,
            "feature_schema": ckbu.FEATURE_NAMES,
            "raw_label_column_read": False,
            "execution_only_sparse_emit": True,
            "scientific_protocol_changed": False,
        },
    )


def materialize_ton_file(args: argparse.Namespace) -> None:
    name = str(args.ton_file)
    if name not in ckbu.TON_PILOT_FILES:
        raise RuntimeError(f"unknown ToN pilot file: {name}")
    role = ckbu.TON_PILOT_FILES[name]
    if role == "reserved_internal_report_no_model_use":
        raise RuntimeError(f"reserved ToN file cannot be materialized: {name}")
    path = Path(args.ton_pilot_dir) / name
    connection_targets = ckbu.load_ton_connection_targets(
        Path(args.ckbt_candidate_manifest), Path(args.ton_extracted_root)
    )
    expected = (
        len(connection_targets[name])
        if name in connection_targets
        else int(args.ton_normal_budget)
    )
    valid, reason = validate_ton_file_pair(
        Path(args.ton_file_cache), name, path, role, expected
    )
    if valid:
        print(f"CKBV_TON_FILE_REUSED file={name}", flush=True)
        return
    if reason != "missing_pair":
        raise RuntimeError(f"invalid existing ToN file cache: {name}: {reason}")
    print(f"CKBV_TON_FILE_START file={name} role={role}", flush=True)
    if name in connection_targets:
        rows, audit = process_ton_attack_sparse(
            args, name, connection_targets[name]
        )
    else:
        rows, audit = process_ton_normal_sparse(args, name, role)
    save_ton_file(Path(args.ton_file_cache), name, role, path, rows, audit)
    valid, reason = validate_ton_file_pair(
        Path(args.ton_file_cache), name, path, role, expected
    )
    if not valid:
        raise RuntimeError(f"new ToN file cache invalid: {name}: {reason}")
    print(
        f"CKBV_TON_FILE_COMPLETE file={name} rows={len(rows)} "
        f"seconds={audit['seconds']:.3f}",
        flush=True,
    )


def run_ton_file_subprocess(
    args: argparse.Namespace, name: str
) -> dict[str, Any]:
    log_dir = Path(args.out) / "ton_file_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log = log_dir / f"{name}.log"
    command = [
        sys.executable,
        "-u",
        str(Path(__file__).resolve()),
        "--mode",
        "materialize-ton-file",
        "--ton-file",
        name,
        "--ton-pilot-dir",
        str(args.ton_pilot_dir),
        "--ton-extracted-root",
        str(args.ton_extracted_root),
        "--ckbt-candidate-manifest",
        str(args.ckbt_candidate_manifest),
        "--ton-file-cache",
        str(args.ton_file_cache),
        "--ton-normal-budget",
        str(args.ton_normal_budget),
        "--seed",
        str(args.seed),
        "--tshark",
        str(args.tshark),
        "--progress-every",
        str(args.progress_every),
    ]
    started = time.monotonic()
    with log.open("w", encoding="utf-8", newline="\n") as handle:
        process = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=(os.name == "posix"),
        )
        last_size = 0
        last_progress = time.monotonic()
        while process.poll() is None:
            time.sleep(5)
            size = log.stat().st_size if log.exists() else 0
            if size != last_size:
                last_size = size
                last_progress = time.monotonic()
            elapsed = time.monotonic() - started
            if elapsed > float(args.ton_file_timeout_seconds):
                terminate_process_group(process)
                raise RuntimeError(f"ToN file timeout: {name}: {elapsed:.1f}s")
            if time.monotonic() - last_progress > float(args.stale_seconds):
                terminate_process_group(process)
                raise RuntimeError(f"ToN file progress stale: {name}")
        code = int(process.returncode or 0)
    if code:
        tail = log.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"ToN file subprocess failed {name}: {code}\n{tail}")
    return {"source_file": name, "seconds": time.monotonic() - started, "log_path": str(log)}


def copy_valid_ton_reuse(
    args: argparse.Namespace, names: list[str]
) -> int:
    destination = Path(args.ton_file_cache)
    destination.mkdir(parents=True, exist_ok=True)
    connection_targets = ckbu.load_ton_connection_targets(
        Path(args.ckbt_candidate_manifest), Path(args.ton_extracted_root)
    )
    reused = 0
    for name in names:
        role = ckbu.TON_PILOT_FILES[name]
        path = Path(args.ton_pilot_dir) / name
        expected = (
            len(connection_targets[name])
            if name in connection_targets
            else int(args.ton_normal_budget)
        )
        if validate_ton_file_pair(destination, name, path, role, expected)[0]:
            continue
        for raw in args.reuse_ton_file_cache:
            source = Path(raw)
            if not validate_ton_file_pair(
                source, name, path, role, expected
            )[0]:
                continue
            src_npz, src_meta = ton_file_paths(source, name, path)
            dst_npz, dst_meta = ton_file_paths(destination, name, path)
            resume.atomic_copy(src_npz, dst_npz)
            resume.atomic_copy(src_meta, dst_meta)
            if not validate_ton_file_pair(
                destination, name, path, role, expected
            )[0]:
                raise RuntimeError(f"copied ToN reuse invalid: {name}")
            reused += 1
            break
    return reused


def run_ton_files(args: argparse.Namespace) -> None:
    names = [
        name
        for name, role in ckbu.TON_PILOT_FILES.items()
        if role != "reserved_internal_report_no_model_use"
    ]
    reused = copy_valid_ton_reuse(args, names)
    connection_targets = ckbu.load_ton_connection_targets(
        Path(args.ckbt_candidate_manifest), Path(args.ton_extracted_root)
    )
    pending: list[str] = []
    for name in names:
        role = ckbu.TON_PILOT_FILES[name]
        path = Path(args.ton_pilot_dir) / name
        expected = (
            len(connection_targets[name])
            if name in connection_targets
            else int(args.ton_normal_budget)
        )
        if not validate_ton_file_pair(
            Path(args.ton_file_cache), name, path, role, expected
        )[0]:
            pending.append(name)
    runtimes: list[dict[str, Any]] = []
    failures: list[str] = []
    if pending:
        with ThreadPoolExecutor(
            max_workers=min(int(args.ton_workers), len(pending))
        ) as pool:
            futures = {
                pool.submit(run_ton_file_subprocess, args, name): name
                for name in pending
            }
            for future in as_completed(futures):
                name = futures[future]
                try:
                    result = future.result()
                    runtimes.append(result)
                    print(
                        f"CKBV_TON_CHECKPOINT_READY file={name} "
                        f"seconds={result['seconds']:.3f}",
                        flush=True,
                    )
                except Exception as exc:
                    failures.append(str(exc))
                    print(
                        f"CKBV_TON_FILE_FAILED {exc}",
                        file=sys.stderr,
                        flush=True,
                    )
    if failures:
        raise RuntimeError("; ".join(failures))

    selected: list[dict[str, Any]] = []
    audits: list[dict[str, Any]] = []
    for name, role in ckbu.TON_PILOT_FILES.items():
        if role == "reserved_internal_report_no_model_use":
            audits.append(
                {
                    "raw_source_path": name,
                    "role": role,
                    "decoded_events": 0,
                    "model_rows": 0,
                    "reserved_no_model_use": True,
                    "raw_label_column_read": False,
                }
            )
            continue
        path = Path(args.ton_pilot_dir) / name
        npz, meta = ton_file_paths(Path(args.ton_file_cache), name, path)
        summary = json.loads(meta.read_text(encoding="utf-8"))
        audits.append(
            {
                **summary["capture_audit"],
                "role": role,
                "model_rows": int(summary["rows"]),
            }
        )
        with np.load(npz, allow_pickle=False) as values:
            for index in range(len(values["record_id"])):
                selected.append(
                    {
                        "record_id": str(values["record_id"].astype(str)[index]),
                        "role": str(values["role"].astype(str)[index]),
                        "source_file": str(values["source_file"].astype(str)[index]),
                        "mechanism_family": str(
                            values["mechanism_family"].astype(str)[index]
                        ),
                        "label": int(values["label"][index]),
                        "feature_available_time_epoch": float(
                            values["feature_available_time_epoch"][index]
                        ),
                        "target_event_position_within_capture": int(
                            values["target_event_position_within_capture"][index]
                        ),
                        "src_local_id": int(values["src_local_id"][index]),
                        "dst_local_id": int(values["dst_local_id"][index]),
                        "feature": values["causal_features"][index].astype(
                            np.float32, copy=True
                        ),
                    }
                )
    if len(selected) != 12_000:
        raise RuntimeError(f"ToN aggregate row drift: {len(selected)}/12000")
    features = np.vstack([row["feature"] for row in selected]).astype(np.float32)
    out = Path(args.out)
    npz = out / "ckbu_ton_raw_pcap_pilot_causal_samples.npz"
    atomic_npz(
        npz,
        record_id=np.asarray([row["record_id"] for row in selected]),
        role=np.asarray([row["role"] for row in selected]),
        source_file=np.asarray([row["source_file"] for row in selected]),
        mechanism_family=np.asarray(
            [row["mechanism_family"] for row in selected]
        ),
        label=np.asarray([row["label"] for row in selected], dtype=np.int8),
        feature_available_time_epoch=np.asarray(
            [row["feature_available_time_epoch"] for row in selected],
            dtype=np.float64,
        ),
        target_event_position_within_capture=np.asarray(
            [row["target_event_position_within_capture"] for row in selected],
            dtype=np.int64,
        ),
        src_local_id=np.asarray(
            [row["src_local_id"] for row in selected], dtype=np.int32
        ),
        dst_local_id=np.asarray(
            [row["dst_local_id"] for row in selected], dtype=np.int32
        ),
        causal_features=features,
        feature_names=np.asarray(ckbu.FEATURE_NAMES),
    )
    ckbu.write_csv(out / "ckbu_ton_raw_pcap_materialization_audit.csv", audits)
    roles = Counter(str(row["role"]) for row in selected)
    ready = {
        "status": "CKBU_TON_RAW_PCAP_CAUSAL_READY",
        "rows": len(selected),
        "roles": dict(sorted(roles.items())),
        "feature_schema": ckbu.FEATURE_NAMES,
        "cache_npz": str(npz),
        "cache_sha256": ckbu.sha256_file(npz),
        "same_feature_schema_as_gotham": True,
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "fit_select_source_files_disjoint": True,
        "reserved_injection_mitm_model_rows": 0,
        "raw_label_column_read": False,
        "file_checkpointed": True,
        "execution_only_sparse_emit": True,
        "scientific_protocol_changed": False,
        "reused_file_caches": reused,
    }
    atomic_json(out / "ckbu_ton_raw_pcap_pilot_causal_ready.json", ready)
    if runtimes:
        ckbu.write_csv(out / "ckbv_ton_file_runtime.csv", runtimes)
    print(json.dumps(ready, indent=2, sort_keys=True), flush=True)


def unit_tests() -> dict[str, Any]:
    base = 1_000.0
    events = [
        ckbu.synthetic_event(base + index * 0.017, f"n{index % 4}", f"n{(index + 1) % 5}", stream=index % 7)
        for index in range(500)
    ]
    selected_positions = {0, 1, 17, 80, 129, 255, 499}
    dense = ckbu.CausalFeatureBuilder()
    dense_features, _times, _src, _dst = dense.transform(events)
    sparse = sparse_selected_transform(events, selected_positions)
    for position in selected_positions:
        if not np.array_equal(dense_features[position], sparse[position]):
            raise RuntimeError(f"sparse/dense feature drift at {position}")

    expected_reservoir = []
    rng = np.random.default_rng(27)
    for index in range(100):
        events_seen = index + 1
        if len(expected_reservoir) < 13:
            expected_reservoir.append(index)
        else:
            replacement = int(rng.integers(0, events_seen))
            if replacement < 13:
                expected_reservoir[replacement] = index
    if reservoir_event_ordinals(100, 13, 27) != sorted(expected_reservoir):
        raise RuntimeError("two-pass reservoir selection drift")

    calibration_fixture = [
        {"member_index": index, "uncompressed_bytes": (index + 1) * 100}
        for index in range(10)
    ]
    calibration = size_range_calibration(calibration_fixture, 4)
    if (
        len(calibration) != 4
        or calibration[0] != calibration_fixture[0]
        or calibration[-1] != calibration_fixture[-1]
    ):
        raise RuntimeError("size-range calibration omitted an endpoint")
    single_worker_calibration = size_range_calibration(calibration_fixture, 1)
    if (
        len(single_worker_calibration) != 2
        or single_worker_calibration[0] != calibration_fixture[0]
        or single_worker_calibration[-1] != calibration_fixture[-1]
    ):
        raise RuntimeError("single-worker calibration omitted the largest member")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        archive_path = root / "tiny.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("capture-a.pcap", b"a" * 100)
            archive.writestr("capture-b.pcap", b"b" * 200)
        source_plan = root / "source.csv"
        ckbu.write_csv(
            source_plan,
            [
                {
                    "source_group": "processed/test.csv",
                    "source_cache_key": "source-key",
                    "target_rows": 2,
                    "pcap_members_json": json.dumps(
                        ["capture-a.pcap", "capture-b.pcap"]
                    ),
                }
            ],
        )
        member_plan = root / "member.csv"
        plan_gotham_members(
            SimpleNamespace(
                source_plan=source_plan,
                gotham_zip=archive_path,
                member_plan=member_plan,
            )
        )
        rows = read_csv_rows(member_plan)
        if len(rows) != 2 or [int(row["member_index"]) for row in rows] != [0, 1]:
            raise RuntimeError("member planning drift")

        cache = root / "cache"
        row = rows[0]
        npz, meta = member_paths(cache, row["member_cache_key"])
        atomic_npz(
            npz,
            recorded_index=np.asarray([], dtype=np.int64),
            feature_available_time_epoch=np.asarray([], dtype=np.float64),
            target_event_position_within_capture=np.asarray([], dtype=np.int64),
            src_local_id=np.asarray([], dtype=np.int32),
            dst_local_id=np.asarray([], dtype=np.int32),
            causal_features=np.empty(
                (0, len(ckbu.FEATURE_NAMES)), dtype=np.float32
            ),
            feature_names=np.asarray(ckbu.FEATURE_NAMES),
            raw_source_path=np.asarray([], dtype=str),
        )
        atomic_json(
            meta,
            {
                "status": MEMBER_STATUS,
                "source_group": row["source_group"],
                "source_cache_key": row["source_cache_key"],
                "archive_member": row["archive_member"],
                "member_cache_key": row["member_cache_key"],
                "archive_crc32": int(row["archive_crc32"]),
                "uncompressed_bytes": int(row["uncompressed_bytes"]),
                "member_plan_sha256": ckbu.sha256_file(member_plan),
                "raw_label_column_read": False,
                "cache_sha256": ckbu.sha256_file(npz),
            },
        )
        valid, reason = validate_member_pair(
            row, cache, ckbu.sha256_file(member_plan)
        )
        if not valid:
            raise RuntimeError(f"valid empty member checkpoint rejected: {reason}")
        summary = json.loads(meta.read_text(encoding="utf-8"))
        summary["raw_label_column_read"] = True
        atomic_json(meta, summary)
        if validate_member_pair(row, cache, ckbu.sha256_file(member_plan))[0]:
            raise RuntimeError("raw-label member checkpoint accepted")
        summary["raw_label_column_read"] = False
        atomic_json(meta, summary)
        reuse = root / "reuse"
        copied = copy_valid_member_reuse(
            [row],
            reuse,
            [cache],
            ckbu.sha256_file(member_plan),
        )
        if copied != 1:
            raise RuntimeError("valid member checkpoint was not reused")
        if not validate_member_pair(
            row, reuse, ckbu.sha256_file(member_plan)
        )[0]:
            raise RuntimeError("copied member checkpoint rejected")
        reused_npz, _reused_meta = member_paths(
            reuse, str(row["member_cache_key"])
        )
        with reused_npz.open("ab") as handle:
            handle.write(b"corruption")
        if validate_member_pair(
            row, reuse, ckbu.sha256_file(member_plan)
        )[0]:
            raise RuntimeError("corrupted reused checkpoint accepted")

    return {
        "status": "CKBV_CHECKPOINT_SPARSE_UNIT_PASS",
        "feature_dim": len(ckbu.FEATURE_NAMES),
        "sparse_dense_selected_rows_bit_exact": True,
        "score_before_update": True,
        "past_only_state_update_preserved": True,
        "member_checkpoint_atomic": True,
        "invalid_checkpoint_rejected": True,
        "valid_checkpoint_resume_tested": True,
        "corrupted_reuse_rejected": True,
        "two_pass_reservoir_exact": True,
        "size_range_calibration_includes_largest": True,
        "raw_label_column_read": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "unit",
            "plan-gotham-members",
            "materialize-gotham-member",
            "run-gotham-members",
            "materialize-ton-file",
            "run-ton-files",
        ),
        default="unit",
    )
    parser.add_argument("--out", type=Path)
    parser.add_argument("--gotham-zip", type=Path)
    parser.add_argument("--source-plan", type=Path)
    parser.add_argument("--member-plan", type=Path)
    parser.add_argument("--member-index", type=int, default=-1)
    parser.add_argument("--member-cache", type=Path)
    parser.add_argument("--source-cache", type=Path)
    parser.add_argument("--reuse-source-cache", action="append", default=[])
    parser.add_argument("--reuse-member-cache", action="append", default=[])
    parser.add_argument("--targets", action="append", default=[])
    parser.add_argument("--tshark", default="tshark")
    parser.add_argument("--alignment-tolerance-us", type=int, default=2)
    parser.add_argument("--progress-every", type=int, default=PROGRESS_EVERY_DEFAULT)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--member-timeout-seconds", type=int, default=14_400)
    parser.add_argument("--ton-file-timeout-seconds", type=int, default=21_600)
    parser.add_argument("--stale-seconds", type=int, default=1_800)
    parser.add_argument("--available-seconds", type=int, default=108_000)
    parser.add_argument("--projection-safety-factor", type=float, default=2.0)
    parser.add_argument("--ton-pilot-dir", type=Path)
    parser.add_argument("--ton-extracted-root", type=Path)
    parser.add_argument("--ckbt-candidate-manifest", type=Path)
    parser.add_argument("--ton-file-cache", type=Path)
    parser.add_argument("--reuse-ton-file-cache", action="append", default=[])
    parser.add_argument("--ton-file")
    parser.add_argument("--ton-normal-budget", type=int, default=4_000)
    parser.add_argument("--ton-workers", type=int, default=2)
    parser.add_argument("--seed", type=int, default=27)
    args = parser.parse_args()

    if args.mode == "unit":
        print(json.dumps(unit_tests(), indent=2, sort_keys=True))
    elif args.mode == "plan-gotham-members":
        plan_gotham_members(args)
    elif args.mode == "materialize-gotham-member":
        materialize_gotham_member(args)
    elif args.mode == "run-gotham-members":
        run_gotham_members(args)
    elif args.mode == "materialize-ton-file":
        materialize_ton_file(args)
    elif args.mode == "run-ton-files":
        run_ton_files(args)


if __name__ == "__main__":
    main()
