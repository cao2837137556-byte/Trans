#!/usr/bin/env python3
"""CKDA D1 frozen representation/probe implementation primitives.

This module contains the executable pieces whose identities are fixed by
``ckda_d1_frozen_representation_probe_preregistered_20260812.md``.  The formal
runner imports these functions; the module can also execute a small real-model
contract path with ``--contract-unit`` before any expensive real-input work.

The formal HPC runtime is Python 3.9.  Keep this file parseable and executable
there: no structural pattern matching and no newer pathlib write helpers.
"""

from __future__ import annotations

import argparse
import ast
import csv
import gzip
import hashlib
import inspect
import io
import json
import math
import os
import random
import re
import tempfile
import time
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

import numpy as np


SEED = 27
BOOTSTRAP_SEED = 2701
CONTRACT_SHA256 = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
MAX_PREFIX = 256
HIDDEN_WIDTH = 128
BLOCKS = 4
HEADS = 4
FF_WIDTH = 512
DROPOUT = 0.10
REPRESENTATION_WIDTH = 132
GLOBAL_TOKEN_BUDGET = 32_768

BENIGN_MIN_SESSIONS = 500_000
BENIGN_MIN_TOKENS = 10_000_000
SUPPORT_SELECT_ROWS = 69
AUX_SELECT_ROWS = 3_000
TON_SELECT_ROWS = 4_000
REPORT_ATTACK_ROWS = 244_050
FUTURE_QUERY_ROWS = 131_391
ATTACK_FAMILIES = 16
OOD_POOLS = 4

ACTIONABLE = "CKDA_D1_ACTIONABLE_PROBE_SIGNAL"
STRONG_GEOMETRIC = "CKDA_D1_STRONG_GEOMETRIC_SIGNAL"
WEAK_ONLY = "CKDA_D1_WEAK_ONLY"
NO_ACTIONABLE = "CKDA_D1_NO_ACTIONABLE_SIGNAL_UNDER_FROZEN_PROBES"
ENGINEERING_FAILURE = "CKDA_D1_ENGINEERING_FAILURE"
PRIMARY_PRECONDITION_FAILED = "CKDA_D1_PRIMARY_PRECONDITION_FAILED"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_trusted_training_checkpoint(path: Path, map_location):
    """Load an internally generated full-state checkpoint across Torch 2.5+.

    Torch 2.6 changed ``weights_only``'s default.  CKDA checkpoints contain
    optimizer and RNG state, so they require the trusted full-state loader.
    Older supported builds that do not expose the keyword retain their legacy
    full-state behavior.
    """
    import torch

    parameters = inspect.signature(torch.load).parameters
    if "weights_only" in parameters:
        return torch.load(path, map_location=map_location, weights_only=False)
    return torch.load(path, map_location=map_location)


def sha256_json(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(payload)


def _atomic_replace(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def atomic_text(path: Path, text: str) -> None:
    _atomic_replace(Path(path), text.replace("\r\n", "\n").encode("utf-8"))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(Path(path), json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def union_fieldnames(rows: Sequence[Mapping[str, object]]) -> List[str]:
    fields = set()
    for row in rows:
        fields.update(str(key) for key in row.keys())
    return sorted(fields)


def atomic_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Optional[Sequence[str]] = None) -> None:
    fieldnames = list(fields) if fields is not None else union_fieldnames(rows)
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fieldnames})
    _atomic_replace(Path(path), stream.getvalue().encode("utf-8"))


def atomic_csv_stream(
    path: Path,
    rows: Iterable[Mapping[str, object]],
    fields: Sequence[str],
    compress: bool = False,
) -> int:
    """Write a large fixed-schema table without materializing it in memory."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    os.close(descriptor)
    count = 0
    try:
        if compress:
            raw = open(temporary, "wb", buffering=1024 * 1024)
            zipped = gzip.GzipFile(fileobj=raw, mode="wb", filename="", mtime=0)
            handle = io.TextIOWrapper(zipped, encoding="utf-8", newline="")
        else:
            raw = None
            zipped = None
            handle = open(temporary, "w", encoding="utf-8", newline="", buffering=1024 * 1024)
        try:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise", lineterminator="\n")
            writer.writeheader()
            for count, row in enumerate(rows, start=1):
                writer.writerow({field: row.get(field, "") for field in fields})
                if count % 100_000 == 0:
                    handle.flush()
            handle.flush()
        finally:
            handle.close()
            if zipped is not None and not zipped.closed:
                zipped.close()
            if raw is not None and not raw.closed:
                raw.close()
        opener = gzip.open if compress else open
        with opener(temporary, "rt", encoding="utf-8", newline="") as check:
            reader = csv.reader(check)
            header = next(reader)
            readback = sum(1 for _ in reader)
        if header != list(fields) or readback != count:
            raise RuntimeError("streamed CSV readback drift: %s/%s" % (readback, count))
        os.replace(temporary, path)
        return count
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_contract(path: Path) -> None:
    actual = sha256_file(Path(path))
    if actual != CONTRACT_SHA256:
        raise RuntimeError("CKDA D1 frozen contract SHA mismatch: " + actual)


def assert_python39_source(path: Path) -> None:
    """Parse under 3.9 grammar and reject observed runtime incompatibilities."""
    source = Path(path).read_bytes().decode("utf-8")
    try:
        try:
            tree = ast.parse(source, filename=str(path), feature_version=(3, 9))
        except TypeError:
            # CPython 3.9 accepts the feature minor as an integer; newer
            # runtimes accept the explicit major/minor tuple.
            tree = ast.parse(source, filename=str(path), feature_version=9)
    except SyntaxError as error:
        raise RuntimeError("Python 3.9 grammar gate failed for %s: %s" % (path, error))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "write_text" and any(key.arg == "newline" for key in node.keywords):
                raise RuntimeError("Python 3.9 Path.write_text(newline=) gate failed: %s" % path)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == "zip" and any(key.arg == "strict" for key in node.keywords):
                raise RuntimeError("Python 3.9 zip(strict=) gate failed: %s" % path)
    # The AST gate catches real match/case syntax.  This explicit scan protects
    # vendored files before import and makes the historical failure visible.
    if re.search(r"(?m)^\s*match\s+.+:\s*(?:#.*)?$", source):
        raise RuntimeError("Python 3.9 match/case gate failed: %s" % path)


def assert_python39_tree(paths: Iterable[Path]) -> Dict[str, object]:
    checked = []
    for root in paths:
        root = Path(root)
        members = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for member in members:
            assert_python39_source(member)
            checked.append({"path": str(member), "sha256": sha256_file(member)})
    if not checked:
        raise RuntimeError("Python 3.9 gate received no Python files")
    return {"status": "PASS", "files": len(checked), "members": checked}


def runtime_io_contract(root: Path) -> Dict[str, object]:
    """Exercise real atomic text/JSON/mixed-schema CSV write and readback."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    text_path = root / "atomic.txt"
    json_path = root / "atomic.json"
    csv_path = root / "mixed.csv"
    atomic_text(text_path, "alpha\nbeta\n")
    atomic_json(json_path, {"status": "PASS", "value": 27})
    mixed = [{"uid": "a", "fit_only": 1}, {"uid": "b", "report_only": "x"}]
    atomic_csv(csv_path, mixed)
    text_value = text_path.read_bytes().decode("utf-8")
    with json_path.open("r", encoding="utf-8") as handle:
        json_value = json.load(handle)
    csv_value = read_csv(csv_path)
    if text_value != "alpha\nbeta\n":
        raise RuntimeError("atomic text roundtrip failed")
    if json_value != {"status": "PASS", "value": 27}:
        raise RuntimeError("atomic JSON roundtrip failed")
    if list(csv_value[0]) != ["fit_only", "report_only", "uid"]:
        raise RuntimeError("mixed-schema CSV union field order failed")
    if csv_value[0]["fit_only"] != "1" or csv_value[1]["report_only"] != "x":
        raise RuntimeError("mixed-schema CSV value roundtrip failed")
    return {
        "status": "PASS",
        "text_sha256": sha256_file(text_path),
        "json_sha256": sha256_file(json_path),
        "csv_sha256": sha256_file(csv_path),
    }


@dataclass(frozen=True)
class PacketEvent:
    source_id: str
    pcap_member: str
    event_position: int
    timestamp_us: int
    src_ip: bytes
    src_port: int
    dst_ip: bytes
    dst_port: int
    protocol: int
    frame_len: int


def canonical_session_key(event: PacketEvent) -> Tuple[object, ...]:
    left = (bytes(event.src_ip), int(event.src_port))
    right = (bytes(event.dst_ip), int(event.dst_port))
    endpoint_a, endpoint_b = sorted((left, right))
    protocol = int(event.protocol)
    if protocol < 0 or protocol > 255:
        raise ValueError("protocol outside [0,255]")
    return (str(event.source_id), str(event.pcap_member), protocol, endpoint_a, endpoint_b)


def packet_fields(event: PacketEvent, previous_timestamp_us: Optional[int]) -> Tuple[int, int, int, int]:
    key = canonical_session_key(event)
    endpoint_a = key[3]
    direction = 0 if (bytes(event.src_ip), int(event.src_port)) == endpoint_a else 1
    frame_len = int(event.frame_len)
    if frame_len < 0:
        raise ValueError("negative frame length")
    length_bucket = min(frame_len // 64, 31)
    protocol = int(event.protocol)
    if previous_timestamp_us is None:
        iat_bucket = 0
    else:
        delta = int(event.timestamp_us) - int(previous_timestamp_us)
        if delta < 0:
            raise ValueError("negative causal IAT")
        if delta == 0:
            iat_bucket = 1
        else:
            iat_bucket = 2 + min(int(math.floor(math.log2(delta))), 30)
    return int(direction), int(length_bucket), int(protocol), int(iat_bucket)


def materialize_sessions(events: Iterable[PacketEvent]) -> Dict[Tuple[object, ...], np.ndarray]:
    """Materialize each packet once, with stable timestamp/event-position order."""
    ordered = sorted(
        events,
        key=lambda value: (
            str(value.source_id),
            str(value.pcap_member),
            canonical_session_key(value),
            int(value.timestamp_us),
            int(value.event_position),
        ),
    )
    sessions: Dict[Tuple[object, ...], List[Tuple[int, int, int, int]]] = {}
    previous: Dict[Tuple[object, ...], int] = {}
    seen_positions = set()
    for event in ordered:
        member_position = (str(event.source_id), str(event.pcap_member), int(event.event_position))
        if member_position in seen_positions:
            raise RuntimeError("duplicate source/member event position")
        seen_positions.add(member_position)
        key = canonical_session_key(event)
        token = packet_fields(event, previous.get(key))
        sessions.setdefault(key, []).append(token)
        previous[key] = int(event.timestamp_us)
    return {key: np.asarray(value, dtype=np.int64) for key, value in sessions.items()}


def split_once(sequences: Mapping[object, np.ndarray], width: int = MAX_PREFIX) -> List[Tuple[str, np.ndarray]]:
    """Split long sessions without overlapping or duplicating a packet."""
    if int(width) != MAX_PREFIX:
        raise RuntimeError("I1 prefix width drift")
    chunks = []
    for key in sorted(sequences, key=lambda value: repr(value)):
        tokens = np.asarray(sequences[key], dtype=np.int64)
        if tokens.ndim != 2 or tokens.shape[1] != 4 or len(tokens) == 0:
            raise RuntimeError("invalid I1 session token shape")
        for start in range(0, len(tokens), width):
            chunk = np.ascontiguousarray(tokens[start : start + width])
            chunks.append((sha256_bytes((repr(key) + ":" + str(start)).encode("utf-8")), chunk))
    if sum(len(chunk) for _, chunk in chunks) != sum(len(value) for value in sequences.values()):
        raise RuntimeError("I1 split duplicated or removed packets")
    return chunks


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            np.savez_compressed(handle, **arrays)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_session_shard(path: Path, sequences: Mapping[object, np.ndarray]) -> Dict[str, object]:
    """Persist deterministic non-overlapping session chunks for resumable training."""
    chunks = split_once(sequences)
    offsets = [0]
    digests = []
    token_parts = []
    for digest, tokens in chunks:
        validate_token_array(tokens)
        token_parts.append(np.asarray(tokens, dtype=np.int16))
        offsets.append(offsets[-1] + len(tokens))
        digests.append(digest.encode("ascii"))
    if not token_parts:
        raise RuntimeError("cannot write empty I1 session shard")
    packed = np.concatenate(token_parts, axis=0)
    atomic_npz(
        Path(path),
        tokens=packed,
        offsets=np.asarray(offsets, dtype=np.int64),
        chunk_sha256=np.asarray(digests, dtype="S64"),
    )
    report = validate_session_shard(Path(path))
    return report


def validate_session_shard(path: Path) -> Dict[str, object]:
    with np.load(Path(path), allow_pickle=False) as archive:
        if set(archive.files) != {"tokens", "offsets", "chunk_sha256"}:
            raise RuntimeError("I1 shard schema drift")
        tokens = np.asarray(archive["tokens"])
        offsets = np.asarray(archive["offsets"])
        digests = np.asarray(archive["chunk_sha256"])
    validate_token_array(tokens)
    if offsets.ndim != 1 or len(offsets) < 2 or int(offsets[0]) != 0:
        raise RuntimeError("I1 shard offset schema drift")
    if bool(np.any(np.diff(offsets) <= 0)) or int(offsets[-1]) != len(tokens):
        raise RuntimeError("I1 shard offset coverage drift")
    if bool(np.any(np.diff(offsets) > MAX_PREFIX)):
        raise RuntimeError("I1 shard contains over-width chunk")
    if len(digests) != len(offsets) - 1 or len(set(digests.tolist())) != len(digests):
        raise RuntimeError("I1 shard chunk identity drift")
    return {
        "path": str(Path(path)),
        "sha256": sha256_file(Path(path)),
        "chunks": int(len(digests)),
        "tokens": int(len(tokens)),
        "status": "PASS",
    }


def iter_shard_chunks(path: Path) -> Iterator[np.ndarray]:
    # mmap is unavailable for compressed NPZ; one source/member shard is the
    # bounded resume unit and is released before the next shard is opened.
    with np.load(Path(path), allow_pickle=False) as archive:
        tokens = np.asarray(archive["tokens"], dtype=np.int64)
        offsets = np.asarray(archive["offsets"], dtype=np.int64)
        for index in range(len(offsets) - 1):
            yield np.ascontiguousarray(tokens[int(offsets[index]) : int(offsets[index + 1])])


def epoch_shard_order(paths: Sequence[Path], epoch: int) -> List[Path]:
    return sorted(
        (Path(value) for value in paths),
        key=lambda path: sha256_bytes((str(int(epoch)) + ":" + sha256_file(path)).encode("ascii")),
    )


def iter_token_budget_batches(paths: Sequence[Path], epoch: int) -> Iterator[List[np.ndarray]]:
    # Fixed powers-of-two length bins bound padded width to less than 2x the
    # longest nonpadding width in a bin.  The rule is data-independent and
    # preserves the frozen 32,768 nonpadding-token budget exactly.
    pending: Dict[int, List[np.ndarray]] = {}
    token_counts: Dict[int, int] = {}

    def bin_id(length: int) -> int:
        return 0 if int(length) <= 1 else int(math.ceil(math.log2(int(length))))

    for path in epoch_shard_order(paths, epoch):
        for chunk in iter_shard_chunks(path):
            key = bin_id(len(chunk))
            batch = pending.setdefault(key, [])
            count = token_counts.setdefault(key, 0)
            if batch and count + len(chunk) > GLOBAL_TOKEN_BUDGET:
                yield batch
                batch = []
                count = 0
                pending[key] = batch
            batch.append(chunk)
            token_counts[key] = count + len(chunk)
    for key in sorted(pending):
        if pending[key]:
            yield pending[key]


def validate_batch_padding(chunks: Sequence[np.ndarray]) -> Dict[str, int]:
    if not chunks:
        raise RuntimeError("empty I1 token batch")
    nonpadding = sum(len(value) for value in chunks)
    padded = len(chunks) * max(len(value) for value in chunks)
    if nonpadding > GLOBAL_TOKEN_BUDGET:
        raise RuntimeError("I1 nonpadding token budget exceeded")
    if padded > 2 * nonpadding:
        raise RuntimeError("I1 padding amplification exceeded fixed bound")
    return {"sequences": len(chunks), "nonpadding_tokens": nonpadding, "padded_tokens": padded}


def count_optimizer_steps(paths: Sequence[Path], epochs: int = 3) -> int:
    return sum(1 for epoch in range(int(epochs)) for _batch in iter_token_budget_batches(paths, epoch))


def atomic_torch_save(path: Path, value: object) -> None:
    torch = _torch()
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as handle:
            torch.save(value, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def i1_training_identity(shards: Sequence[Path], total_steps: int) -> Dict[str, object]:
    return {
        "contract_sha256": CONTRACT_SHA256,
        "seed": SEED,
        "epochs": 3,
        "optimizer": "AdamW",
        "learning_rate": 3e-4,
        "weight_decay": 1e-2,
        "global_nonpadding_token_budget": GLOBAL_TOKEN_BUDGET,
        "gradient_clip": 1.0,
        "warmup_fraction": 0.05,
        "precision": "float32",
        "total_steps": int(total_steps),
        "shards": [
            {"path": str(Path(path)), "sha256": sha256_file(Path(path))}
            for path in sorted((Path(value) for value in shards), key=lambda value: str(value))
        ],
    }


def learning_rate_at_step(step: int, total_steps: int) -> float:
    if int(step) < 1 or int(step) > int(total_steps):
        raise RuntimeError("learning-rate step outside frozen schedule")
    warmup = max(1, int(math.ceil(0.05 * int(total_steps))))
    if int(step) <= warmup:
        factor = float(step) / float(warmup)
    elif total_steps == warmup:
        factor = 0.0
    else:
        progress = float(step - warmup) / float(total_steps - warmup)
        factor = 0.5 * (1.0 + math.cos(math.pi * progress))
    return 3e-4 * factor


def train_i1_from_shards(
    shards: Sequence[Path],
    checkpoint_dir: Path,
    device: str = "cpu",
    stop_after_epoch: Optional[int] = None,
) -> Dict[str, object]:
    """Train exactly the frozen I1 identity with epoch-level exact resume."""
    torch = _torch()
    if not shards:
        raise RuntimeError("I1 training has no shards")
    shard_reports = [validate_session_shard(Path(path)) for path in shards]
    total_steps = count_optimizer_steps(shards, epochs=3)
    if total_steps < 1:
        raise RuntimeError("I1 training has zero optimizer steps")
    identity = i1_training_identity(shards, total_steps)
    identity_sha = sha256_json(identity)
    checkpoint_dir = Path(checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / "i1_epoch_checkpoint.pt"
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
    model = build_i1_model().to(device=device, dtype=torch.float32)
    optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-2)
    torch.use_deterministic_algorithms(True)
    completed_epoch = 0
    global_step = 0
    history = []
    if checkpoint_path.is_file():
        checkpoint = load_trusted_training_checkpoint(checkpoint_path, device)
        if checkpoint.get("identity_sha256") != identity_sha:
            raise RuntimeError("I1 checkpoint identity mismatch")
        model.load_state_dict(checkpoint["model"])
        optimizer.load_state_dict(checkpoint["optimizer"])
        completed_epoch = int(checkpoint["completed_epoch"])
        global_step = int(checkpoint["global_step"])
        history = list(checkpoint["history"])
        random.setstate(checkpoint["python_rng_state"])
        np.random.set_state(checkpoint["numpy_rng_state"])
        torch.set_rng_state(checkpoint["torch_rng_state"])
        if torch.cuda.is_available() and checkpoint.get("cuda_rng_state") is not None:
            torch.cuda.set_rng_state_all(checkpoint["cuda_rng_state"])
        if completed_epoch < 0 or completed_epoch > 3:
            raise RuntimeError("I1 checkpoint epoch outside frozen range")
    target_epoch = 3 if stop_after_epoch is None else int(stop_after_epoch)
    if target_epoch < completed_epoch or target_epoch > 3:
        raise RuntimeError("invalid I1 stop-after epoch")
    started = time.time()
    for epoch in range(completed_epoch, target_epoch):
        model.train()
        loss_sum = 0.0
        token_sum = 0
        batch_count = 0
        for chunks in iter_token_budget_batches(shards, epoch):
            validate_batch_padding(chunks)
            tokens, valid = collate_chunks(chunks)
            tokens = tokens.to(device)
            valid = valid.to(device)
            global_step += 1
            learning_rate = learning_rate_at_step(global_step, total_steps)
            for group in optimizer.param_groups:
                group["lr"] = learning_rate
            optimizer.zero_grad(set_to_none=True)
            loss, _components = model.loss(tokens, valid)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            current_tokens = int(valid.sum().item())
            loss_sum += float(loss.item()) * current_tokens
            token_sum += current_tokens
            batch_count += 1
        if token_sum != sum(int(value["tokens"]) for value in shard_reports):
            raise RuntimeError("I1 epoch packet coverage drift")
        history.append(
            {
                "epoch": epoch + 1,
                "optimizer_steps": batch_count,
                "tokens": token_sum,
                "mean_loss": loss_sum / float(token_sum),
                "last_learning_rate": learning_rate_at_step(global_step, total_steps),
            }
        )
        atomic_torch_save(
            checkpoint_path,
            {
                "identity": identity,
                "identity_sha256": identity_sha,
                "completed_epoch": epoch + 1,
                "global_step": global_step,
                "model": model.state_dict(),
                "optimizer": optimizer.state_dict(),
                "history": history,
                "python_rng_state": random.getstate(),
                "numpy_rng_state": np.random.get_state(),
                "torch_rng_state": torch.get_rng_state(),
                "cuda_rng_state": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else None,
            },
        )
        # A checkpoint is reusable only after immediate readback and identity validation.
        verified = load_trusted_training_checkpoint(checkpoint_path, "cpu")
        if verified.get("identity_sha256") != identity_sha or int(verified["completed_epoch"]) != epoch + 1:
            raise RuntimeError("I1 epoch checkpoint readback failed")
    model.eval()
    state_hash = sha256_json(
        {
            key: sha256_bytes(value.detach().cpu().numpy().astype("<f4").tobytes())
            for key, value in sorted(model.state_dict().items())
        }
    )
    report = {
        "status": "PASS" if target_epoch == 3 else "CHECKPOINTED",
        "identity_sha256": identity_sha,
        "completed_epoch": target_epoch,
        "global_step": global_step,
        "total_steps": total_steps,
        "model_state_sha256": state_hash,
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "history": history,
        "elapsed_seconds_this_invocation": time.time() - started,
    }
    atomic_json(checkpoint_dir / "i1_training_report.json", report)
    return report


def validate_token_array(tokens: np.ndarray) -> None:
    tokens = np.asarray(tokens)
    if tokens.ndim != 2 or tokens.shape[1] != 4:
        raise RuntimeError("token array must be [packets,4]")
    limits = ((0, 1), (0, 31), (0, 255), (0, 32))
    for index, (lower, upper) in enumerate(limits):
        if np.any(tokens[:, index] < lower) or np.any(tokens[:, index] > upper):
            raise RuntimeError("token field %d outside frozen vocabulary" % index)


def benign_census_gate(session_count: int, token_count: int) -> Dict[str, object]:
    passed = int(session_count) >= BENIGN_MIN_SESSIONS and int(token_count) >= BENIGN_MIN_TOKENS
    return {
        "status": "PASS" if passed else PRIMARY_PRECONDITION_FAILED,
        "benign_fit_sessions": int(session_count),
        "benign_fit_tokens": int(token_count),
        "minimum_sessions": BENIGN_MIN_SESSIONS,
        "minimum_tokens": BENIGN_MIN_TOKENS,
        "passed": bool(passed),
    }


def _torch():
    import torch
    return torch


def build_i1_model():
    torch = _torch()
    nn = torch.nn

    class I1CausalTransformer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.direction = nn.Embedding(2, HIDDEN_WIDTH)
            self.length = nn.Embedding(32, HIDDEN_WIDTH)
            self.protocol = nn.Embedding(256, HIDDEN_WIDTH)
            self.iat = nn.Embedding(33, HIDDEN_WIDTH)
            self.position = nn.Embedding(MAX_PREFIX, HIDDEN_WIDTH)
            self.bos = nn.Parameter(torch.zeros(1, 1, HIDDEN_WIDTH))
            layer = nn.TransformerEncoderLayer(
                d_model=HIDDEN_WIDTH,
                nhead=HEADS,
                dim_feedforward=FF_WIDTH,
                dropout=DROPOUT,
                activation="relu",
                batch_first=True,
                norm_first=True,
            )
            self.encoder = nn.TransformerEncoder(layer, num_layers=BLOCKS)
            self.final_norm = nn.LayerNorm(HIDDEN_WIDTH)
            self.heads = nn.ModuleList(
                [nn.Linear(HIDDEN_WIDTH, size) for size in (2, 32, 256, 33)]
            )
            nn.init.normal_(self.bos, mean=0.0, std=0.02)

        def packet_embedding(self, tokens):
            length = int(tokens.shape[1])
            if length < 1 or length > MAX_PREFIX:
                raise RuntimeError("I1 sequence length outside [1,256]")
            positions = torch.arange(length, device=tokens.device).unsqueeze(0)
            return (
                self.direction(tokens[:, :, 0])
                + self.length(tokens[:, :, 1])
                + self.protocol(tokens[:, :, 2])
                + self.iat(tokens[:, :, 3])
                + self.position(positions)
            )

        def encode(self, tokens, valid_mask):
            embedded = self.packet_embedding(tokens)
            batch = int(tokens.shape[0])
            bos = self.bos.expand(batch, -1, -1)
            sequence = torch.cat((bos, embedded), dim=1)
            total = int(sequence.shape[1])
            causal = torch.triu(
                torch.ones(total, total, device=tokens.device, dtype=torch.bool), diagonal=1
            )
            padding = torch.cat(
                (torch.ones(batch, 1, device=tokens.device, dtype=torch.bool), valid_mask), dim=1
            )
            hidden = self.encoder(sequence, mask=causal, src_key_padding_mask=~padding)
            return hidden

        def loss(self, tokens, valid_mask):
            hidden = self.encode(tokens, valid_mask)
            predictors = hidden[:, :-1, :]
            losses = []
            for field, head in enumerate(self.heads):
                logits = head(predictors)
                per_token = torch.nn.functional.cross_entropy(
                    logits.reshape(-1, logits.shape[-1]),
                    tokens[:, :, field].reshape(-1),
                    reduction="none",
                ).reshape(tokens.shape[0], tokens.shape[1])
                losses.append(per_token[valid_mask].mean())
            return torch.stack(losses).mean(), torch.stack(losses)

        def representation(self, tokens, valid_mask):
            hidden = self.encode(tokens, valid_mask)
            batch = int(tokens.shape[0])
            lengths = valid_mask.sum(dim=1).to(torch.long)
            row = torch.arange(batch, device=tokens.device)
            consumed = self.final_norm(hidden[row, lengths, :])
            previous = hidden[row, lengths - 1, :]
            current = tokens[row, lengths - 1, :]
            nlls = []
            for field, head in enumerate(self.heads):
                logits = head(previous)
                nll = torch.nn.functional.cross_entropy(logits, current[:, field], reduction="none")
                nlls.append(nll)
            return torch.cat((consumed, torch.stack(nlls, dim=1)), dim=1)

    torch.manual_seed(SEED)
    return I1CausalTransformer()


def collate_chunks(chunks: Sequence[np.ndarray]):
    torch = _torch()
    if not chunks:
        raise RuntimeError("cannot collate empty I1 batch")
    maximum = max(len(value) for value in chunks)
    tokens = np.zeros((len(chunks), maximum, 4), dtype=np.int64)
    valid = np.zeros((len(chunks), maximum), dtype=np.bool_)
    for row, value in enumerate(chunks):
        validate_token_array(value)
        tokens[row, : len(value), :] = value
        valid[row, : len(value)] = True
    return torch.from_numpy(tokens), torch.from_numpy(valid)


def i1_forward_contract() -> Dict[str, object]:
    torch = _torch()
    model = build_i1_model().to(device="cpu", dtype=torch.float32)
    model.eval()
    chunks = [
        np.asarray([[0, 1, 6, 0], [1, 2, 6, 2], [0, 3, 6, 12]], dtype=np.int64),
        np.asarray([[1, 4, 17, 0]], dtype=np.int64),
    ]
    tokens, valid = collate_chunks(chunks)
    with torch.inference_mode():
        loss, components = model.loss(tokens, valid)
        representation = model.representation(tokens, valid)
    if tuple(representation.shape) != (2, REPRESENTATION_WIDTH):
        raise RuntimeError("I1 representation width drift")
    if not bool(torch.isfinite(loss).item()) or not bool(torch.isfinite(representation).all().item()):
        raise RuntimeError("I1 real forward produced nonfinite values")
    return {
        "status": "PASS",
        "loss": float(loss.item()),
        "component_losses": [float(value) for value in components.tolist()],
        "representation_shape": list(representation.shape),
        "quantized_sha256": sha256_bytes(
            np.round(representation.detach().cpu().numpy(), 6).astype("<f4").tobytes()
        ),
    }


def masked_mean_last_hidden(last_hidden: Any, attention_mask: Any):
    """Frozen E3 final-layer attention-mask-weighted arithmetic mean."""
    torch = _torch()
    hidden = last_hidden.to(dtype=torch.float32)
    mask = attention_mask.to(device=hidden.device, dtype=torch.float32)
    if hidden.ndim != 3 or mask.ndim != 2 or hidden.shape[:2] != mask.shape:
        raise RuntimeError("E3 hidden/mask shape drift")
    denominator = mask.sum(dim=1, keepdim=True)
    if bool((denominator <= 0).any().item()):
        raise RuntimeError("E3 attention mask has empty row")
    pooled = (hidden * mask.unsqueeze(-1)).sum(dim=1) / denominator
    if not bool(torch.isfinite(pooled).all().item()):
        raise RuntimeError("E3 masked mean produced nonfinite values")
    return pooled


def e3_forward_batches(model: Any, batches: Iterable[Mapping[str, Any]], device: str = "cpu") -> np.ndarray:
    """Run the already-pinned official E3 base transformer and fixed pooling."""
    torch = _torch()
    representations = []
    model.eval()
    with torch.inference_mode():
        for raw in batches:
            batch = {
                key: value.to(device) if hasattr(value, "to") else value
                for key, value in raw.items()
            }
            sequence_length = int(batch["input_ids"].shape[1])
            position_ids = torch.arange(sequence_length, device=device).unsqueeze(0).expand(
                batch["input_ids"].shape[0], -1
            )
            hidden = model.base_transformer(
                input_ids=batch["input_ids"],
                attention_mask=batch["attention_mask"],
                position_ids=position_ids,
                direction=batch["direction"].to(torch.float32),
                iats=batch["iats"].to(torch.float32),
                bytes=batch["bytes"].to(torch.float32),
                pkt_count=batch["pkt_count"].to(torch.float32),
                protocol=batch["protocol"],
                dataset_burst_sizes=batch["dataset_burst_sizes"],
                return_dict=True,
            ).last_hidden_state
            pooled = masked_mean_last_hidden(hidden, batch["attention_mask"])
            representations.append(pooled.cpu().numpy().astype(np.float32))
    if not representations:
        raise RuntimeError("E3 received no forward batches")
    result = np.concatenate(representations, axis=0)
    if not bool(np.all(np.isfinite(result))):
        raise RuntimeError("E3 representations are nonfinite")
    return result


@dataclass(frozen=True)
class SharedNormalizer:
    mean: np.ndarray
    scale: np.ndarray

    @classmethod
    def fit(cls, representations: np.ndarray, missing: np.ndarray) -> "SharedNormalizer":
        values = np.asarray(representations, dtype=np.float64)
        mask = ~np.asarray(missing, dtype=np.bool_)
        if values.ndim != 2 or len(values) != len(mask) or not np.any(mask):
            raise RuntimeError("invalid normalizer fit inputs")
        finite = np.isfinite(values[mask])
        if not bool(np.all(finite)):
            raise RuntimeError("nonfinite legal fit representation")
        mean = values[mask].mean(axis=0)
        standard = values[mask].std(axis=0, ddof=0)
        scale = np.where(standard > 0.0, standard, 1.0)
        return cls(mean=mean, scale=scale)

    def transform(self, representations: np.ndarray, missing: np.ndarray) -> np.ndarray:
        values = np.asarray(representations, dtype=np.float64)
        miss = np.asarray(missing, dtype=np.bool_)
        if values.ndim != 2 or values.shape[1] != len(self.mean) or len(values) != len(miss):
            raise RuntimeError("normalizer transform shape drift")
        result = (values - self.mean) / self.scale
        result[miss, :] = 0.0
        if not bool(np.all(np.isfinite(result))):
            raise RuntimeError("normalizer produced nonfinite values")
        return result


def append_missing(values: np.ndarray, missing: np.ndarray) -> np.ndarray:
    return np.column_stack((np.asarray(values, dtype=np.float64), np.asarray(missing, dtype=np.float64)))


class GeometryProbe:
    def __init__(self, cap: int = 200_000, neighbors: int = 5) -> None:
        self.cap = int(cap)
        self.neighbors = int(neighbors)
        self.reference = None
        self.reference_uids: List[str] = []

    def fit(self, normalized: np.ndarray, missing: np.ndarray, labels: np.ndarray, uids: Sequence[str]) -> "GeometryProbe":
        values = np.asarray(normalized, dtype=np.float64)
        miss = np.asarray(missing, dtype=np.bool_)
        labels = np.asarray(labels, dtype=np.int64)
        eligible = [
            index for index in range(len(values)) if not miss[index] and int(labels[index]) == 0
        ]
        eligible.sort(key=lambda index: (sha256_bytes(str(uids[index]).encode("utf-8")), str(uids[index])))
        eligible = eligible[: self.cap]
        if len(eligible) < self.neighbors:
            raise RuntimeError("G0 benign reference has fewer than five rows")
        reference = values[eligible]
        norms = np.linalg.norm(reference, axis=1, keepdims=True)
        reference = reference / np.where(norms > 0.0, norms, 1.0)
        self.reference = reference
        self.reference_uids = [str(uids[index]) for index in eligible]
        return self

    def score(
        self,
        normalized: np.ndarray,
        missing: np.ndarray,
        uids: Sequence[str],
        query_batch: int = 1024,
    ) -> np.ndarray:
        from sklearn.neighbors import NearestNeighbors

        if self.reference is None:
            raise RuntimeError("G0 not fitted")
        values = np.asarray(normalized, dtype=np.float64)
        miss = np.asarray(missing, dtype=np.bool_)
        norms = np.linalg.norm(values, axis=1, keepdims=True)
        values = values / np.where(norms > 0.0, norms, 1.0)
        request = min(len(self.reference), self.neighbors + 1)
        model = NearestNeighbors(n_neighbors=request, metric="cosine", algorithm="brute")
        model.fit(self.reference)
        result = np.empty(len(values), dtype=np.float64)
        reference_uid_to_index = {uid: index for index, uid in enumerate(self.reference_uids)}
        if int(query_batch) < 1:
            raise RuntimeError("G0 query batch must be positive")
        for start in range(0, len(values), int(query_batch)):
            stop = min(len(values), start + int(query_batch))
            distances, indices = model.kneighbors(values[start:stop], return_distance=True)
            for offset in range(stop - start):
                row = start + offset
                if miss[row]:
                    result[row] = math.inf
                    continue
                own = reference_uid_to_index.get(str(uids[row]))
                kept = [
                    float(distance)
                    for distance, index in zip(distances[offset], indices[offset])
                    if own is None or int(index) != int(own)
                ]
                if len(kept) < self.neighbors:
                    raise RuntimeError("G0 self-exclusion left fewer than five neighbors")
                result[row] = float(np.mean(kept[: self.neighbors]))
            if stop == len(values) or stop % (32 * int(query_batch)) == 0:
                print(
                    "CKDA_D1_G0_QUERY_PROGRESS rows=%d/%d" % (stop, len(values)),
                    flush=True,
                )
        return result


class LinearProbe:
    def __init__(self) -> None:
        self.model = None

    def fit(self, features: np.ndarray, labels: np.ndarray) -> "LinearProbe":
        from sklearn.linear_model import LogisticRegression

        labels = np.asarray(labels, dtype=np.int64)
        if sorted(np.unique(labels).tolist()) != [0, 1]:
            raise RuntimeError("P1 fit requires both binary classes")
        model = LogisticRegression(
            C=1.0,
            class_weight="balanced",
            solver="lbfgs",
            max_iter=300,
            tol=1e-8,
            random_state=SEED,
        )
        model.fit(np.asarray(features, dtype=np.float64), labels)
        self.model = model
        return self

    def score(self, features: np.ndarray) -> np.ndarray:
        if self.model is None:
            raise RuntimeError("P1 not fitted")
        return np.asarray(self.model.predict_proba(features)[:, 1], dtype=np.float64)


class MLPProbe:
    def __init__(self, input_width: int) -> None:
        torch = _torch()
        torch.manual_seed(SEED)
        self.model = torch.nn.Sequential(
            torch.nn.Linear(int(input_width), 128),
            torch.nn.ReLU(),
            torch.nn.Dropout(0.10),
            torch.nn.Linear(128, 1),
        )

    def fit(self, features: np.ndarray, labels: np.ndarray, epochs: int = 50) -> "MLPProbe":
        torch = _torch()
        if int(epochs) != 50:
            raise RuntimeError("P2 epoch identity drift")
        x = torch.as_tensor(np.asarray(features, dtype=np.float32))
        y = torch.as_tensor(np.asarray(labels, dtype=np.float32)).reshape(-1, 1)
        if sorted(np.unique(labels).tolist()) != [0, 1]:
            raise RuntimeError("P2 fit requires both binary classes")
        counts = np.bincount(np.asarray(labels, dtype=np.int64), minlength=2).astype(np.float64)
        class_weights = len(labels) / (2.0 * counts)
        row_weights = torch.as_tensor(class_weights[np.asarray(labels, dtype=np.int64)], dtype=torch.float32).reshape(-1, 1)
        optimizer = torch.optim.AdamW(self.model.parameters(), lr=1e-3, weight_decay=1e-4)
        generator = torch.Generator().manual_seed(SEED)
        for _epoch in range(50):
            order = torch.randperm(len(x), generator=generator)
            self.model.train()
            for start in range(0, len(x), 256):
                index = order[start : start + 256]
                optimizer.zero_grad(set_to_none=True)
                logits = self.model(x[index])
                loss = torch.nn.functional.binary_cross_entropy_with_logits(
                    logits, y[index], weight=row_weights[index], reduction="mean"
                )
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()
        return self

    def score(self, features: np.ndarray) -> np.ndarray:
        torch = _torch()
        self.model.eval()
        with torch.inference_mode():
            logits = self.model(torch.as_tensor(np.asarray(features, dtype=np.float32))).reshape(-1)
            scores = torch.sigmoid(logits).cpu().numpy()
        if not bool(np.all(np.isfinite(scores))):
            raise RuntimeError("P2 produced nonfinite score")
        return scores.astype(np.float64)


@dataclass(frozen=True)
class ThresholdSpec:
    kind: str
    value: Optional[float]
    canonical: str
    support_hard: int
    auxiliary_hard: int
    ton_hard: int


def canonical_score(value: float) -> str:
    if not math.isfinite(float(value)):
        raise RuntimeError("canonical_score requires finite value")
    return format(Decimal(str(float(value))), "f")


def apply_threshold(scores: np.ndarray, threshold: ThresholdSpec) -> np.ndarray:
    values = np.asarray(scores, dtype=np.float64)
    if bool(np.any(np.isnan(values))):
        raise RuntimeError("NaN score")
    if threshold.kind == "NO_HARD":
        return np.zeros(len(values), dtype=np.bool_)
    if threshold.kind == "ALL_HARD":
        return np.ones(len(values), dtype=np.bool_)
    if threshold.kind != "FINITE" or threshold.value is None:
        raise RuntimeError("unknown threshold kind")
    return values >= float(threshold.value)


def choose_threshold(support: np.ndarray, auxiliary: np.ndarray, ton: np.ndarray) -> Tuple[ThresholdSpec, List[Dict[str, object]]]:
    support = np.asarray(support, dtype=np.float64)
    auxiliary = np.asarray(auxiliary, dtype=np.float64)
    ton = np.asarray(ton, dtype=np.float64)
    if (len(support), len(auxiliary), len(ton)) != (
        SUPPORT_SELECT_ROWS,
        AUX_SELECT_ROWS,
        TON_SELECT_ROWS,
    ):
        raise RuntimeError("CKDA D1 select denominator drift")
    all_values = np.concatenate((support, auxiliary, ton))
    if bool(np.any(np.isnan(all_values))):
        raise RuntimeError("CKDA D1 select score contains NaN")
    finite = sorted(set(float(value) for value in all_values if math.isfinite(float(value))))
    if not finite:
        raise RuntimeError("no valid finite threshold frontier")
    candidates = [ThresholdSpec("NO_HARD", None, "NO_HARD", 0, 0, 0)]
    candidates.extend(ThresholdSpec("FINITE", value, canonical_score(value), 0, 0, 0) for value in finite)
    candidates.append(ThresholdSpec("ALL_HARD", None, "ALL_HARD", 0, 0, 0))
    evaluated = []
    valid = []
    for candidate in candidates:
        support_hard = int(apply_threshold(support, candidate).sum())
        auxiliary_hard = int(apply_threshold(auxiliary, candidate).sum())
        ton_hard = int(apply_threshold(ton, candidate).sum())
        current = ThresholdSpec(
            candidate.kind,
            candidate.value,
            candidate.canonical,
            support_hard,
            auxiliary_hard,
            ton_hard,
        )
        evaluated.append(asdict(current))
        if support_hard == SUPPORT_SELECT_ROWS:
            valid.append(current)
    if not valid:
        raise RuntimeError("no threshold achieves 69/69 support")

    def rank(value: ThresholdSpec) -> Tuple[object, ...]:
        numeric = float(value.value) if value.value is not None else (
            math.inf if value.kind == "NO_HARD" else -math.inf
        )
        return (
            value.auxiliary_hard + value.ton_hard,
            value.auxiliary_hard,
            value.ton_hard,
            -numeric,
            value.canonical,
        )

    return min(valid, key=rank), evaluated


@dataclass(frozen=True)
class GateEvidence:
    support_hard: int
    overall_attack_rows: int
    overall_recall: float
    c1_overall_recall: float
    future_rows: int
    future_recall: float
    family_deltas_pp: Mapping[str, float]
    ood_rates: Mapping[str, float]
    frozen_ood_rates: Mapping[str, float]
    review_count: int
    contract_gates_pass: bool


def actionable_gate(evidence: GateEvidence) -> Tuple[bool, Dict[str, bool]]:
    if len(evidence.family_deltas_pp) != ATTACK_FAMILIES:
        raise RuntimeError("attack family denominator/scope drift")
    if len(evidence.ood_rates) != OOD_POOLS or set(evidence.ood_rates) != set(evidence.frozen_ood_rates):
        raise RuntimeError("OOD pool denominator/scope drift")
    macro = float(np.mean(list(evidence.ood_rates.values())))
    checks = {
        "support_69_of_69": int(evidence.support_hard) == SUPPORT_SELECT_ROWS,
        "overall_rows": int(evidence.overall_attack_rows) == REPORT_ATTACK_ROWS,
        "overall_delta_ge_minus_0_5pp": 100.0 * (float(evidence.overall_recall) - float(evidence.c1_overall_recall)) >= -0.5,
        "all_16_family_delta_ge_minus_2pp": all(float(value) >= -2.0 for value in evidence.family_deltas_pp.values()),
        "future_rows": int(evidence.future_rows) == FUTURE_QUERY_ROWS,
        "future_recall_ge_84_83pct": float(evidence.future_recall) >= 0.8483,
        "ood_macro_le_30_2722pct": macro <= 0.302722,
        "each_ood_delta_le_2pp": all(
            100.0 * (float(evidence.ood_rates[key]) - float(evidence.frozen_ood_rates[key])) <= 2.0
            for key in evidence.ood_rates
        ),
        "each_ood_le_90pct": all(float(value) <= 0.90 for value in evidence.ood_rates.values()),
        "review_zero": int(evidence.review_count) == 0,
        "contracts_pass": bool(evidence.contract_gates_pass),
    }
    return all(checks.values()), checks


def final_state(
    p1_actionable: bool,
    p2_actionable: bool,
    g0_strong: bool,
    weak_lower_bounds: Sequence[float],
    completed: bool,
    engineering_failure: bool,
) -> str:
    if engineering_failure or not completed:
        return ENGINEERING_FAILURE
    if bool(p1_actionable) or bool(p2_actionable):
        return ACTIONABLE
    if bool(g0_strong):
        return STRONG_GEOMETRIC
    if any(float(value) > 0.5 for value in weak_lower_bounds):
        return WEAK_ONLY
    return NO_ACTIONABLE


def contract_unit(out: Path) -> Dict[str, object]:
    random.seed(SEED)
    np.random.seed(SEED)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    io_report = runtime_io_contract(out / "io")
    forward = i1_forward_contract()

    events = [
        PacketEvent("s", "m", 2, 20, b"\x0a\x00\x00\x02", 443, b"\x0a\x00\x00\x01", 10, 6, 128),
        PacketEvent("s", "m", 1, 10, b"\x0a\x00\x00\x01", 10, b"\x0a\x00\x00\x02", 443, 6, 64),
    ]
    sessions = materialize_sessions(events)
    tokens = next(iter(sessions.values()))
    if tokens.tolist() != [[0, 1, 6, 0], [1, 2, 6, 5]]:
        raise RuntimeError("causal token contract failed: %r" % tokens.tolist())

    rng = np.random.default_rng(SEED)
    fit = rng.normal(size=(40, 8))
    missing = np.zeros(40, dtype=np.bool_)
    labels = np.asarray([0] * 20 + [1] * 20, dtype=np.int64)
    uids = ["fit:%d" % index for index in range(40)]
    normalizer = SharedNormalizer.fit(fit, missing)
    normalized = normalizer.transform(fit, missing)
    geometry = GeometryProbe().fit(normalized, missing, labels, uids)
    geometry_scores = geometry.score(normalized, missing, uids)
    features = append_missing(normalized, missing)
    linear = LinearProbe().fit(features, labels)
    linear_scores = linear.score(features)
    mlp = MLPProbe(features.shape[1]).fit(features, labels)
    mlp_scores = mlp.score(features)
    for name, values in (("G0", geometry_scores), ("P1", linear_scores), ("P2", mlp_scores)):
        if len(values) != 40 or bool(np.any(np.isnan(values))):
            raise RuntimeError(name + " probe contract failed")

    support = np.linspace(0.80, 0.90, SUPPORT_SELECT_ROWS)
    auxiliary = np.linspace(0.0, 0.79, AUX_SELECT_ROWS)
    ton = np.linspace(0.0, 0.78, TON_SELECT_ROWS)
    threshold, frontier = choose_threshold(support, auxiliary, ton)
    if threshold.kind != "FINITE" or threshold.support_hard != SUPPORT_SELECT_ROWS:
        raise RuntimeError("threshold contract failed")
    report = {
        "status": "PASS",
        "contract_sha256": CONTRACT_SHA256,
        "io": io_report,
        "i1_forward": forward,
        "session_token_sha256": sha256_bytes(tokens.astype("<i8").tobytes()),
        "probe_score_sha256": sha256_json(
            {
                "G0": np.round(geometry_scores, 12).tolist(),
                "P1": np.round(linear_scores, 12).tolist(),
                "P2": np.round(mlp_scores, 12).tolist(),
            }
        ),
        "threshold": asdict(threshold),
        "frontier_rows": len(frontier),
    }
    atomic_json(out / "ckda_d1_contract_unit.json", report)
    return report


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract-unit", action="store_true")
    result.add_argument("--python39-gate", nargs="*", type=Path)
    result.add_argument("--contract", type=Path)
    result.add_argument("--out", type=Path, default=Path("tmp/ckda_d1_contract_unit"))
    return result


def main() -> None:
    args = parser().parse_args()
    if args.contract is not None:
        verify_contract(args.contract)
    if args.python39_gate is not None:
        report = assert_python39_tree(args.python39_gate)
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    if args.contract_unit:
        report = contract_unit(args.out)
        print(json.dumps(report, indent=2, sort_keys=True))
        return
    raise SystemExit("choose --contract-unit or --python39-gate")


if __name__ == "__main__":
    main()
