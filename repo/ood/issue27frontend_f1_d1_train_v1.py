#!/usr/bin/env python3
"""Frozen Frontend-F1 D1 corpus, training, and gated evaluation implementation.

The module has three physically separated entry points:

``materialize-fit`` replays only the legal fit targets and writes declarative
H1-H4 token sequences. ``train-fit`` consumes only that corpus and can never
open select/report/FINAL. ``evaluate-select`` requires a different explicit
authorization token and a frozen checkpoint.

Importing this module performs no filesystem reads and starts no training.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd
import sklearn
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score, roc_auc_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence


ROOT = Path(__file__).resolve().parents[2]
FROZEN_REL = Path("runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md")
FROZEN_SHA256 = "7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860"
PARENT_REL = Path("runs/mainline_docs/frontend_f1_teacher_constrained_unified_encoder_d0_d1_frozen_20260901.md")
PARENT_SHA256 = "98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4"
ZT_ENGINE_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_v1.py")
ZT_ENGINE_SHA256 = "00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa"
ZT_RUNNER_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py")
ZT_RUNNER_SHA256 = "ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60"
D0_REL = Path("runs/frontend_f1_d0_census_v1_20260902_local_r2")
D0_VERDICT_SHA256 = "5109826a86d5e109cc7d51c57cbecf0dcb7bbd214b0f22483904cf5b08b66ec4"
D0_TABLE_SHA256 = "c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9"
TEACHER_REL = Path("runs/frontend_f1_teacher_benign_count_only_v1_20260902_local")
TEACHER_COUNTS_SHA256 = "922a7a4faacdbaf370adfdf72e44e88b990ba54ac07c85286be40a6e7a86063e"
TEACHER_UID_SHA256 = "f7deceac0ac76fb25e577714f7a94da047e15ed77cb9bee19a9ea9c2954c493b"
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")
PROBE_STATE_SHA256 = "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"
THRESHOLD_SHA256 = "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"
EMBEDDING_METADATA_REL = STAGE_REL / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz"
EMBEDDING_METADATA_SHA256 = "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"
# The first authorized materialization decoded every member with this exact
# semantic-replay implementation. Post-replay metadata repair must not force a
# scientifically identical 24-member re-decode.
REPLAY_IMPLEMENTATION_SHA256 = "f5b38023244485415570a6235be8160706b8ace0aad449d30481e7a9b3efc7e9"

MATERIALIZE_TOKEN = "I_AUTHORIZE_F1_D1_FIT_CORPUS_MATERIALIZATION"
TRAIN_TOKEN = "I_AUTHORIZE_F1_D1_ONE_SHOT_LOCAL_TRAINING"
SELECT_TOKEN = "I_AUTHORIZE_F1_D1_ONE_SHOT_SELECT_EVALUATION"

EXPECTED_ALL = 25_467
EXPECTED_LEGAL_FIT_ROWS = 18_266
EXPECTED_LEGAL_FIT_CONTEXTS = 12_889
EXPECTED_TRAIN_ROWS = 13_866
EXPECTED_TRAIN_CONTEXTS = 9_307
EXPECTED_VAL_ROWS = 4_400
EXPECTED_VAL_CONTEXTS = 3_582
EXPECTED_SELECT_ROWS = 7_069
EXPECTED_SELECT_CONTEXTS = 5_298
EXPECTED_A_SELECT_ATTACK_ROWS = 46
EXPECTED_B_SELECT_ATTACK_ROWS = 23
EXPECTED_SELECT_ATTACK_ROWS = 69
EXPECTED_B_BENIGN_SELECT_ROWS = 4_812
EXPECTED_B_BENIGN_GAIN = 482
MAX_EVENTS = 256
VOCABULARY_SIZE = 4096
THETA_0 = 0.065159872174263
Z_0 = -2.6635317063752599
ATTACK_MARGIN = 0.5
TEACHER_TOLERANCE = 0.25
SEMANTIC_NORMALIZER = 8.317766166719343
LABEL_NORMALIZER = 0.69314718055994529
SEED = 2701

VAL_SOURCES = frozenset(
    {
        "normal_scanning1.pcap",
        "iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0",
        "iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0",
        "iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0",
        "iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0",
    }
)

FORBIDDEN_NAMES = ("viewed", "report", "final", "cooler-motor")


class F1Failure(RuntimeError):
    pass


class ScientificStop(F1Failure):
    def __init__(self, status: str, reason: str):
        super().__init__(reason)
        self.status = str(status)
        self.reason = str(reason)


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def atomic_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_gzip_frame(path: Path, frame: pd.DataFrame) -> None:
    """Write a deterministic gzip CSV and publish it atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text_handle:
                frame.to_csv(text_handle, index=False, lineterminator="\n")
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(str(temporary), str(path))


def atomic_npz(path: Path, **arrays: np.ndarray) -> None:
    """Write an NPZ with stable member order/timestamps and publish atomically."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as raw:
        with zipfile.ZipFile(raw, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name in sorted(arrays):
                member = io.BytesIO()
                np.lib.format.write_array(member, np.asarray(arrays[name]), allow_pickle=False)
                info = zipfile.ZipInfo("%s.npy" % name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                archive.writestr(info, member.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(str(temporary), str(path))


def atomic_gzip_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as handle:
                for row in rows:
                    handle.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":")) + "\n")
        raw.flush()
        os.fsync(raw.fileno())
    os.replace(str(temporary), str(path))


def atomic_csv(path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    os.replace(str(temporary), str(path))


def atomic_torch(path: Path, value: object) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as handle:
        torch.save(value, handle)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def import_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise F1Failure("cannot import pinned module: %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def require_sha(root: Path, relative: Path, expected: str) -> Dict[str, object]:
    path = Path(root) / relative
    if not path.is_file():
        raise F1Failure("required input absent: %s" % path)
    actual = sha256_file(path)
    if actual != expected:
        raise F1Failure("identity drift: %s" % path)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}


def assert_scope_paths(paths: Iterable[Path], allow_select: bool = False) -> None:
    for path in paths:
        resolved = Path(path).resolve()
        try:
            resolved.relative_to(ROOT.resolve())
        except ValueError as exc:
            raise F1Failure("workspace-scope path requested: %s" % resolved) from exc
        lowered = str(resolved).replace("\\", "/").lower()
        forbidden = [name for name in FORBIDDEN_NAMES if name in lowered]
        if allow_select:
            forbidden = [name for name in forbidden if name != "select"]
        if forbidden:
            raise F1Failure("forbidden scope path requested: %s" % resolved)


def assert_output_under_runs(path: Path) -> None:
    resolved = Path(path).resolve()
    try:
        resolved.relative_to((ROOT / "runs").resolve())
    except ValueError as exc:
        raise F1Failure("output must remain under repository runs/: %s" % resolved) from exc


def directory_bytes(path: Path) -> int:
    if not Path(path).exists():
        return 0
    return sum(item.stat().st_size for item in Path(path).rglob("*") if item.is_file())


def peak_working_set_bytes() -> int:
    """Return Windows PeakWorkingSetSize using only the frozen stdlib runtime."""
    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    get_current_process = ctypes.windll.kernel32.GetCurrentProcess
    get_current_process.restype = ctypes.c_void_p
    get_process_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_process_memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(ProcessMemoryCounters), ctypes.c_ulong]
    get_process_memory.restype = ctypes.c_int
    process = get_current_process()
    if not get_process_memory(process, ctypes.byref(counters), counters.cb):
        raise F1Failure("cannot read Windows process memory counters")
    return int(counters.PeakWorkingSetSize)


def enforce_resource_caps(output_dir: Path) -> Dict[str, int]:
    peak = peak_working_set_bytes()
    durable = directory_bytes(output_dir)
    if peak > 8 * 1024 ** 3:
        raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "peak RAM exceeded 8 GiB")
    if durable > 5 * 1024 ** 3:
        raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "durable output exceeded 5 GiB")
    return {"peak_working_set_bytes": peak, "durable_output_bytes": durable}


def runtime_manifest() -> Dict[str, object]:
    try:
        windows_ver = subprocess.check_output(
            ["cmd", "/c", "ver"], text=True, encoding="utf-8", errors="replace"
        ).strip()
    except (OSError, subprocess.SubprocessError):
        windows_ver = platform.platform()
    return {
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "python_compiler": platform.python_compiler(),
        "machine": platform.machine(),
        "numpy": str(np.__version__),
        "torch": str(torch.__version__),
        "sklearn": str(sklearn.__version__),
        "windows_ver": windows_ver,
        "cpu": platform.processor(),
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", ""),
        "omp_num_threads": os.environ.get("OMP_NUM_THREADS", ""),
        "mkl_num_threads": os.environ.get("MKL_NUM_THREADS", ""),
        "torch_num_threads": int(torch.get_num_threads()),
        "torch_num_interop_threads": int(torch.get_num_interop_threads()),
    }


def expected_runtime_manifest() -> Dict[str, object]:
    return {
        "python_executable": r"C:\Users\28371\AppData\Local\Programs\Python\Python39\python.exe",
        "python_version": "3.9.13",
        "python_compiler": "MSC v.1929 64 bit (AMD64)",
        "machine": "AMD64",
        "numpy": "2.0.2",
        "torch": "2.8.0+cpu",
        "sklearn": "1.6.1",
        "windows_ver": "Microsoft Windows [Version 10.0.26200.9168]",
        "cpu": "Intel64 Family 6 Model 154 Stepping 3, GenuineIntel",
        "pythonhashseed": "2701",
        "omp_num_threads": "4",
        "mkl_num_threads": "4",
        "torch_num_threads": 4,
        "torch_num_interop_threads": 1,
    }


def seed_runtime() -> Dict[str, object]:
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    return runtime_manifest()


def verify_runtime(manifest: Optional[Mapping[str, object]] = None) -> Dict[str, object]:
    current = dict(runtime_manifest() if manifest is None else manifest)
    expected = expected_runtime_manifest()
    if current != expected:
        differences = {
            key: {"expected": expected.get(key), "actual": current.get(key)}
            for key in sorted(set(expected) | set(current))
            if expected.get(key) != current.get(key)
        }
        raise F1Failure("runtime manifest drift: %s" % json.dumps(differences, sort_keys=True))
    return current


def length_bin(value: int) -> str:
    limits = ((63, "<=63"), (127, "64-127"), (255, "128-255"), (511, "256-511"),
              (1023, "512-1023"), (1518, "1024-1518"), (4095, "1519-4095"))
    for maximum, label in limits:
        if int(value) <= maximum:
            return label
    return ">=4096"


def delta_bin(value: float) -> str:
    x = float(value)
    if x == 0.0:
        return "0"
    limits = ((1e-6, "(0,1e-6]"), (1e-3, "(1e-6,1e-3]"), (1e-2, "(1e-3,1e-2]"),
              (1e-1, "(1e-2,1e-1]"), (1.0, "(1e-1,1]"), (10.0, "(1,10]"),
              (60.0, "(10,60]"))
    for maximum, label in limits:
        if x <= maximum:
            return label
    return ">60"


def protocol_group(version: Optional[int], protocol: Optional[int], tier: str) -> str:
    if tier == "H4":
        return "KEYLESS"
    if version not in {4, 6} or protocol is None:
        return "NON_IP"
    return {6: "TCP", 17: "UDP", 1: "ICMP", 58: "ICMP", 47: "GRE"}.get(int(protocol), "OTHER_IP")


def optional_decimal(value: object) -> str:
    if value is None or str(value).strip() == "":
        return "NONE"
    return str(int(value))


def canonical_signature(
    raw: Mapping[str, str], event: Any, route: Any, direction: str,
    surrogate_delta: float, regression: bool,
) -> str:
    icmp_type = raw.get("icmp.type", "").strip() or raw.get("icmpv6.type", "").strip()
    icmp_code = raw.get("icmp.code", "").strip() or raw.get("icmpv6.code", "").strip()
    frame_length = int(str(raw.get("frame.len", "0") or "0"))
    values = [
        str(route.tier), str(direction), str(event.link_type), optional_decimal(event.ethertype),
        optional_decimal(event.ip_version), optional_decimal(event.ip_protocol),
        protocol_group(event.ip_version, event.ip_protocol, str(route.tier)),
        "true" if route.ports_present else "false", str(event.field_presence_mask),
        length_bin(frame_length), delta_bin(surrogate_delta), "true" if regression else "false",
        optional_decimal(icmp_type), optional_decimal(icmp_code),
        "true" if raw.get("gre.key", "").strip() else "false",
    ]
    return "\x1f".join(values)


def source_split(source_group: str) -> str:
    return "internal_val" if str(source_group) in VAL_SOURCES else "train"


def deployment_owner(old_missing: object, **unused: object) -> str:
    del unused
    return "B" if bool(old_missing) else "A"


def deployment_route(owner: str) -> str:
    if owner == "A":
        return "INCUMBENT_E3_P2_BYTE_IDENTICAL"
    if owner == "B":
        return "F1_GRU_FROZEN_P2"
    raise F1Failure("unregistered CE owner")


@dataclass
class TargetEntry:
    uid: str
    event_index: int
    owner: str
    label: int
    teacher_kind: str
    role: str
    source_group: str
    device_family: str
    attack_family: str
    timestamp_epoch: float = 0.0


@dataclass
class ContextExample:
    context_key: str
    source_group: str
    signatures: List[str]
    targets: List[TargetEntry]

    def split(self) -> str:
        return source_split(self.source_group)


def context_to_json(example: ContextExample) -> Dict[str, object]:
    return {
        "context_key": example.context_key,
        "source_group": example.source_group,
        "split": example.split(),
        "signatures": list(example.signatures),
        "targets": [entry.__dict__.copy() for entry in example.targets],
    }


def context_from_json(value: Mapping[str, object]) -> ContextExample:
    signatures = [str(item) for item in value["signatures"]]  # type: ignore[index]
    targets = [TargetEntry(**dict(item)) for item in value["targets"]]  # type: ignore[arg-type,index]
    example = ContextExample(str(value["context_key"]), str(value["source_group"]), signatures, targets)
    if str(value.get("split")) != example.split():
        raise F1Failure("context split identity drift")
    return example


def read_contexts(path: Path) -> List[ContextExample]:
    result: List[ContextExample] = []
    with gzip.open(str(path), "rt", encoding="utf-8") as handle:
        for line in handle:
            result.append(context_from_json(json.loads(line)))
    keys = [item.context_key for item in result]
    if len(keys) != len(set(keys)):
        raise F1Failure("duplicate semantic context")
    return result


def build_vocabulary(contexts: Sequence[ContextExample]) -> Tuple[Dict[str, int], str]:
    observed: Set[str] = set()
    for context in contexts:
        if context.split() != "train":
            continue
        observed.update(context.signatures)
    if len(observed) > 4094:
        raise ScientificStop("F1_D1_VOCABULARY_CAPACITY_NO_GO", "train vocabulary exceeds 4,094 signatures")
    ordered = sorted(observed, key=lambda value: (hashlib.sha256(value.encode("utf-8")).digest(), value.encode("utf-8")))
    vocabulary = {signature: index + 2 for index, signature in enumerate(ordered)}
    identity = sha256_bytes(canonical_json_bytes({"PAD": 0, "UNK": 1, "items": ordered}))
    return vocabulary, identity


def encode_context(example: ContextExample, vocabulary: Mapping[str, int]) -> List[int]:
    return [int(vocabulary.get(signature, 1)) for signature in example.signatures]


def order_free_control(token_ids: Sequence[int]) -> np.ndarray:
    if not token_ids or len(token_ids) > MAX_EVENTS:
        raise F1Failure("invalid control prefix length")
    result = np.zeros(VOCABULARY_SIZE + 1, dtype=np.float64)
    for token in token_ids:
        if int(token) < 0 or int(token) >= VOCABULARY_SIZE:
            raise F1Failure("token outside frozen vocabulary")
        result[int(token)] += 1.0
    result[:VOCABULARY_SIZE] /= float(len(token_ids))
    result[VOCABULARY_SIZE] = math.log1p(len(token_ids)) / math.log(257.0)
    return result


class FrozenP2(nn.Module):
    def __init__(self, state: Mapping[str, np.ndarray]):
        super().__init__()
        mean = np.asarray(state["normalizer_mean"], dtype=np.float32)
        scale = np.asarray(state["normalizer_scale"], dtype=np.float32)
        w1 = np.asarray(state["p2__0.weight"], dtype=np.float32)
        b1 = np.asarray(state["p2__0.bias"], dtype=np.float32)
        w2 = np.asarray(state["p2__3.weight"], dtype=np.float32)
        b2 = np.asarray(state["p2__3.bias"], dtype=np.float32)
        if mean.shape != (768,) or scale.shape != (768,) or np.any(scale <= 0):
            raise F1Failure("normalizer identity drift")
        if w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (1, 128) or b2.shape != (1,):
            raise F1Failure("P2 identity drift")
        self.register_buffer("mean", torch.from_numpy(mean))
        self.register_buffer("scale", torch.from_numpy(scale))
        self.register_buffer("w1", torch.from_numpy(w1))
        self.register_buffer("b1", torch.from_numpy(b1))
        self.register_buffer("w2", torch.from_numpy(w2))
        self.register_buffer("b2", torch.from_numpy(b2))

    def forward(self, representations: torch.Tensor) -> torch.Tensor:
        normalized = (representations - self.mean) / self.scale
        missing = torch.zeros((len(normalized), 1), dtype=normalized.dtype, device=normalized.device)
        features = torch.cat((normalized, missing), dim=1)
        hidden = torch.relu(torch.nn.functional.linear(features, self.w1, self.b1))
        return torch.nn.functional.linear(hidden, self.w2, self.b2).reshape(-1)


class F1Encoder(nn.Module):
    def __init__(self, vocab_size: int = VOCABULARY_SIZE, embedding_dim: int = 32,
                 hidden_size: int = 128, output_dim: int = 768):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
        self.gru = nn.GRU(embedding_dim, hidden_size, num_layers=1, bias=True,
                          batch_first=True, bidirectional=False, dropout=0.0)
        self.adapter = nn.Linear(hidden_size, output_dim, bias=True)
        self.semantic_projection = nn.Linear(hidden_size, embedding_dim, bias=True)
        self.semantic_bias = nn.Parameter(torch.zeros(vocab_size))

    def forward(self, token_ids: torch.Tensor, lengths: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        embedded = self.embedding(token_ids)
        packed = pack_padded_sequence(embedded, lengths.cpu(), batch_first=True, enforce_sorted=False)
        packed_hidden, _ = self.gru(packed)
        hidden, _ = pad_packed_sequence(packed_hidden, batch_first=True, total_length=token_ids.shape[1])
        representations = self.adapter(hidden)
        semantic_base = self.semantic_projection(hidden)
        semantic_logits = torch.matmul(semantic_base, self.embedding.weight.transpose(0, 1)) + self.semantic_bias
        return representations, semantic_logits

    def inference_parameter_count(self) -> int:
        names = ("embedding", "gru", "adapter")
        return sum(parameter.numel() for name in names for parameter in getattr(self, name).parameters())

    def training_parameter_count(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters())


@dataclass
class EncodedExample:
    context: ContextExample
    tokens: List[int]


def encode_examples(contexts: Sequence[ContextExample], vocabulary: Mapping[str, int]) -> List[EncodedExample]:
    return [EncodedExample(context, encode_context(context, vocabulary)) for context in contexts]


def collate_examples(examples: Sequence[EncodedExample]) -> Dict[str, object]:
    if not examples:
        raise F1Failure("empty context batch")
    lengths = torch.tensor([len(item.tokens) for item in examples], dtype=torch.int64)
    if int(lengths.min()) < 1 or int(lengths.max()) > MAX_EVENTS:
        raise F1Failure("context length outside frozen bounds")
    token_ids = torch.zeros((len(examples), int(lengths.max())), dtype=torch.int64)
    for index, item in enumerate(examples):
        token_ids[index, :len(item.tokens)] = torch.tensor(item.tokens, dtype=torch.int64)
        for target in item.context.targets:
            if target.event_index < 0 or target.event_index >= len(item.tokens):
                raise F1Failure("target event index outside causal prefix")
    return {"examples": list(examples), "token_ids": token_ids, "lengths": lengths}


def mean_or_zero(values: List[torch.Tensor], reference: torch.Tensor) -> torch.Tensor:
    if not values:
        return reference.sum() * 0.0
    return torch.stack(values).mean()


def compute_losses(model: F1Encoder, p2: FrozenP2, batch: Mapping[str, object]) -> Dict[str, torch.Tensor]:
    examples = batch["examples"]  # type: ignore[assignment]
    token_ids = batch["token_ids"]  # type: ignore[assignment]
    lengths = batch["lengths"]  # type: ignore[assignment]
    representations, semantic_logits = model(token_ids, lengths)
    semantic_by_context: List[torch.Tensor] = []
    label_by_context: List[torch.Tensor] = []
    attack_by_context: List[torch.Tensor] = []
    teacher_by_context: List[torch.Tensor] = []
    all_logits: List[torch.Tensor] = []
    all_labels: List[int] = []
    all_uids: List[str] = []
    all_target_representations: List[torch.Tensor] = []
    for row_index, encoded in enumerate(examples):
        length = len(encoded.tokens)
        if length > 1:
            semantic_by_context.append(
                torch.nn.functional.cross_entropy(
                    semantic_logits[row_index, :length - 1], token_ids[row_index, 1:length], reduction="mean"
                ) / SEMANTIC_NORMALIZER
            )
        target_reps = torch.stack(
            [representations[row_index, target.event_index] for target in encoded.context.targets]
        )
        logits = p2(target_reps)
        labels = torch.tensor([target.label for target in encoded.context.targets], dtype=logits.dtype)
        label_by_context.append(torch.nn.functional.binary_cross_entropy_with_logits(logits, labels) / LABEL_NORMALIZER)
        attack_mask = labels.eq(1.0)
        if bool(attack_mask.any()):
            attack_by_context.append(torch.relu((Z_0 + ATTACK_MARGIN) - logits[attack_mask]).mean() / ATTACK_MARGIN)
        teacher_terms: List[torch.Tensor] = []
        for target_index, target in enumerate(encoded.context.targets):
            if target.teacher_kind == "attack_hard":
                teacher_terms.append(torch.relu((Z_0 + TEACHER_TOLERANCE) - logits[target_index]) / TEACHER_TOLERANCE)
            elif target.teacher_kind == "benign_normal":
                teacher_terms.append(torch.relu(logits[target_index] - (Z_0 - TEACHER_TOLERANCE)) / TEACHER_TOLERANCE)
            elif target.teacher_kind not in {"benign_hard", "none"}:
                raise F1Failure("unregistered teacher kind")
        if teacher_terms:
            teacher_by_context.append(torch.stack(teacher_terms).mean())
        all_logits.extend(list(logits))
        all_target_representations.extend(list(target_reps))
        all_labels.extend(int(value) for value in labels.tolist())
        all_uids.extend(target.uid for target in encoded.context.targets)
    reference = representations
    semantic = mean_or_zero(semantic_by_context, reference)
    label = mean_or_zero(label_by_context, reference)
    attack = mean_or_zero(attack_by_context, reference)
    teacher = mean_or_zero(teacher_by_context, reference)
    return {
        "semantic": semantic,
        "label": label,
        "attack": attack,
        "teacher": teacher,
        "total": semantic + label + attack + teacher,
        "semantic_context_count": torch.tensor(len(semantic_by_context), dtype=torch.int64),
        "label_context_count": torch.tensor(len(label_by_context), dtype=torch.int64),
        "attack_context_count": torch.tensor(len(attack_by_context), dtype=torch.int64),
        "teacher_context_count": torch.tensor(len(teacher_by_context), dtype=torch.int64),
        "logits": torch.stack(all_logits),
        "representations_finite": torch.isfinite(torch.stack(all_target_representations)).all(),
        "labels": torch.tensor(all_labels, dtype=torch.int64),
        "uids": all_uids,  # type: ignore[dict-item]
    }


def checkpoint_eligible(losses: Mapping[str, object], examples: Sequence[EncodedExample]) -> bool:
    logits = torch.as_tensor(losses["logits"]).detach().cpu().numpy()
    if not bool(torch.as_tensor(losses["representations_finite"]).item()) or not np.isfinite(logits).all():
        return False
    targets = [target for example in examples for target in example.context.targets]
    if len(targets) != len(logits):
        raise F1Failure("checkpoint target/logit conservation failure")
    for target, logit in zip(targets, logits):
        hard = float(logit) >= Z_0
        if target.owner == "A" and target.label == 1 and target.teacher_kind == "attack_hard" and not hard:
            return False
        if target.owner == "A" and target.label == 0 and target.teacher_kind == "benign_normal" and hard:
            return False
    return True


def deterministic_batches(examples: Sequence[EncodedExample], epoch: int, batch_size: int = 32) -> List[List[EncodedExample]]:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(SEED + int(epoch))
    order = torch.randperm(len(examples), generator=generator).tolist()
    return [[examples[index] for index in order[start:start + batch_size]] for start in range(0, len(order), batch_size)]


def state_tensor_bytes(state: Mapping[str, torch.Tensor]) -> bytes:
    chunks: List[bytes] = []
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        chunks.append(name.encode("utf-8") + b"\0")
        chunks.append(str(tensor.dtype).encode("ascii") + b"\0")
        chunks.append(canonical_json_bytes(list(tensor.shape)) + b"\0")
        chunks.append(tensor.numpy().tobytes(order="C"))
    return b"".join(chunks)


def load_probe_state(path: Path) -> FrozenP2:
    with np.load(str(path), allow_pickle=False) as values:
        state = {name: np.asarray(values[name]) for name in values.files}
    model = FrozenP2(state)
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()
    return model


def validate_split(examples: Sequence[ContextExample]) -> Dict[str, int]:
    rows = {"train_rows": 0, "train_contexts": 0, "val_rows": 0, "val_contexts": 0}
    for example in examples:
        key = "val" if example.split() == "internal_val" else "train"
        rows[key + "_rows"] += len(example.targets)
        rows[key + "_contexts"] += 1
    expected = {
        "train_rows": EXPECTED_TRAIN_ROWS, "train_contexts": EXPECTED_TRAIN_CONTEXTS,
        "val_rows": EXPECTED_VAL_ROWS, "val_contexts": EXPECTED_VAL_CONTEXTS,
    }
    if rows != expected:
        raise F1Failure("frozen internal split drift: %s" % rows)
    return rows


def train_loop(
    train_examples: Sequence[EncodedExample], val_examples: Sequence[EncodedExample], p2: FrozenP2,
    output_dir: Path, max_epochs: int = 100, batch_size: int = 32,
    resume_path: Optional[Path] = None, stop_after_batches: Optional[int] = None,
    checkpoint_interval: int = 50, run_identity: Optional[Mapping[str, object]] = None,
) -> Dict[str, object]:
    frozen_identity = dict(run_identity or {})
    model = F1Encoder()
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, betas=(0.9, 0.999), eps=1e-8,
                                  weight_decay=1e-4, amsgrad=False)
    epoch_start, batch_start = 0, 0
    best_loss, best_epoch, patience = math.inf, -1, 0
    cumulative_seconds, processed_batches = 0.0, 0
    ledger: List[Dict[str, object]] = []
    if resume_path is not None:
        saved = torch.load(str(resume_path), map_location="cpu", weights_only=False)
        if saved["runtime_manifest"] != expected_runtime_manifest():
            raise F1Failure("resume runtime identity drift")
        if dict(saved.get("run_identity", {})) != frozen_identity:
            raise F1Failure("resume scientific identity drift")
        model.load_state_dict(saved["model"], strict=True)
        optimizer.load_state_dict(saved["optimizer"])
        epoch_start, batch_start = int(saved["epoch"]), int(saved["next_batch"])
        best_loss, best_epoch = float(saved["best_loss"]), int(saved["best_epoch"])
        patience = int(saved["patience"])
        cumulative_seconds = float(saved["cumulative_seconds"])
        processed_batches = int(saved["processed_batches"])
        ledger = [dict(row) for row in saved.get("ledger", [])]
        random.setstate(saved["python_rng"])
        np.random.set_state(saved["numpy_rng"])
        torch.set_rng_state(saved["torch_rng"])
    output_dir.mkdir(parents=True, exist_ok=True)
    resume_out = output_dir / "f1_d1_resume.pt"
    best_out = output_dir / "f1_d1_best.pt"
    run_started = time.perf_counter()
    for epoch in range(epoch_start, max_epochs):
        batches = deterministic_batches(train_examples, epoch, batch_size)
        begin = batch_start if epoch == epoch_start else 0
        model.train()
        for batch_index in range(begin, len(batches)):
            optimizer.zero_grad(set_to_none=True)
            losses = compute_losses(model, p2, collate_examples(batches[batch_index]))
            losses["total"].backward()  # type: ignore[union-attr]
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            processed_batches += 1
            elapsed = cumulative_seconds + (time.perf_counter() - run_started)
            if elapsed > 47_494.34391:
                raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "training wall cap exceeded")
            if processed_batches % 50 == 0:
                enforce_resource_caps(output_dir)
            next_epoch, next_batch = epoch, batch_index + 1
            if next_batch == len(batches):
                next_epoch, next_batch = epoch + 1, 0
            if processed_batches % checkpoint_interval == 0 or (stop_after_batches is not None and processed_batches >= stop_after_batches):
                payload = {
                    "runtime_manifest": expected_runtime_manifest(), "model": model.state_dict(),
                    "run_identity": frozen_identity,
                    "optimizer": optimizer.state_dict(), "epoch": next_epoch, "next_batch": next_batch,
                    "best_loss": best_loss, "best_epoch": best_epoch, "patience": patience,
                    "cumulative_seconds": elapsed, "processed_batches": processed_batches,
                    "ledger": ledger,
                    "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
                    "torch_rng": torch.get_rng_state(),
                }
                atomic_torch(resume_out, payload)
            if stop_after_batches is not None and processed_batches >= stop_after_batches:
                return {"status": "INTERRUPTED", "resume": str(resume_out), "processed_batches": processed_batches}
        batch_start = 0
        model.eval()
        term_sums = {"semantic": 0.0, "label": 0.0, "attack": 0.0, "teacher": 0.0}
        term_counts = {"semantic": 0, "label": 0, "attack": 0, "teacher": 0}
        eligible = True
        with torch.no_grad():
            for start in range(0, len(val_examples), batch_size):
                part = list(val_examples[start:start + batch_size])
                losses = compute_losses(model, p2, collate_examples(part))
                for term in term_sums:
                    count = int(torch.as_tensor(losses[term + "_context_count"]).item())
                    term_sums[term] += float(torch.as_tensor(losses[term]).item()) * count
                    term_counts[term] += count
                eligible = eligible and checkpoint_eligible(losses, part)
        if term_counts["label"] == 0:
            raise F1Failure("internal-validation label context denominator is zero")
        scalar = float(sum(
            0.0 if term_counts[term] == 0 else term_sums[term] / term_counts[term]
            for term in term_sums
        ))
        improved = bool(eligible and scalar < best_loss - 1e-4)
        if improved:
            best_loss, best_epoch, patience = scalar, epoch, 0
            atomic_torch(best_out, {
                "runtime_manifest": expected_runtime_manifest(), "model": model.state_dict(),
                "run_identity": frozen_identity,
                "epoch": epoch, "selection_loss": scalar,
                "model_tensor_sha256": sha256_bytes(state_tensor_bytes(model.state_dict())),
            })
        elif epoch + 1 >= 20:
            patience += 1
        ledger.append({"epoch": epoch, "eligible": eligible, "selection_loss": scalar,
                       "improved": improved, "best_epoch": best_epoch, "patience": patience})
        elapsed = cumulative_seconds + (time.perf_counter() - run_started)
        atomic_torch(resume_out, {
            "runtime_manifest": expected_runtime_manifest(), "model": model.state_dict(),
            "run_identity": frozen_identity,
            "optimizer": optimizer.state_dict(), "epoch": epoch + 1, "next_batch": 0,
            "best_loss": best_loss, "best_epoch": best_epoch, "patience": patience,
            "cumulative_seconds": elapsed, "processed_batches": processed_batches,
            "ledger": ledger,
            "python_rng": random.getstate(), "numpy_rng": np.random.get_state(),
            "torch_rng": torch.get_rng_state(),
        })
        if epoch + 1 >= 20 and patience >= 12:
            break
    if best_epoch < 0 or not best_out.is_file():
        return {"status": "F1_D1_NO_ELIGIBLE_CHECKPOINT", "ledger": ledger,
                "cumulative_seconds": cumulative_seconds + (time.perf_counter() - run_started)}
    return {"status": "CHECKPOINT_FROZEN", "best_epoch": best_epoch, "best_loss": best_loss,
            "best_checkpoint": str(best_out), "resume": str(resume_out), "ledger": ledger,
            "processed_batches": processed_batches,
            "cumulative_seconds": cumulative_seconds + (time.perf_counter() - run_started)}


def collapse_metrics(representations: np.ndarray) -> Dict[str, float]:
    values = np.asarray(representations, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != 768:
        raise F1Failure("representation dimension drift")
    finite = np.isfinite(values).all(axis=1)
    nonfinite_fraction = 1.0 - float(finite.mean())
    safe = values[finite]
    if len(safe) == 0:
        return {"nonfinite_fraction": nonfinite_fraction, "all_zero_fraction": 1.0,
                "duplicate_excess_fraction": 1.0, "stable_rank_count": 0.0,
                "effective_rank": 0.0, "median_norm": 0.0, "q99_over_median": math.inf}
    norms = np.linalg.norm(safe, axis=1)
    all_zero = float(np.mean(np.all(safe == 0.0, axis=1)))
    unique = len(np.unique(safe, axis=0))
    duplicate_excess = float((len(safe) - unique) / len(safe))
    centered = safe - safe.mean(axis=0, keepdims=True)
    singular = np.linalg.svd(centered, compute_uv=False, full_matrices=False)
    stable = 0 if len(singular) == 0 or singular[0] == 0 else int(np.sum(singular / singular[0] >= 1e-3))
    energy = singular ** 2
    probabilities = energy / energy.sum() if energy.sum() > 0 else np.asarray([])
    effective = 0.0 if not len(probabilities) else float(np.exp(-np.sum(probabilities * np.log(np.maximum(probabilities, 1e-300)))))
    median = float(np.median(norms))
    ratio = math.inf if median == 0 else float(np.quantile(norms, 0.99) / median)
    return {"nonfinite_fraction": nonfinite_fraction, "all_zero_fraction": all_zero,
            "duplicate_excess_fraction": duplicate_excess, "stable_rank_count": float(stable),
            "effective_rank": effective, "median_norm": median, "q99_over_median": ratio}


def collapse_pass(metrics: Mapping[str, float]) -> bool:
    return bool(
        metrics["nonfinite_fraction"] == 0.0 and metrics["all_zero_fraction"] <= 0.001
        and metrics["duplicate_excess_fraction"] <= 0.10 and metrics["stable_rank_count"] >= 32
        and metrics["effective_rank"] >= 16 and metrics["median_norm"] >= 1e-3
        and metrics["q99_over_median"] <= 100
    )


def fit_linear_canary(x_train: np.ndarray, y_train: np.ndarray, x_val: np.ndarray) -> np.ndarray:
    scaler = StandardScaler().fit(x_train)
    model = LogisticRegression(C=1.0, solver="liblinear", max_iter=2000, random_state=SEED)
    model.fit(scaler.transform(x_train), y_train)
    return model.predict_proba(scaler.transform(x_val))[:, 1]


def represent_examples(
    model: F1Encoder, examples: Sequence[EncodedExample], batch_size: int = 32,
) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rows: List[Dict[str, object]] = []
    representations: List[np.ndarray] = []
    controls: List[np.ndarray] = []
    model.eval()
    with torch.no_grad():
        for start in range(0, len(examples), batch_size):
            part = list(examples[start:start + batch_size])
            batch = collate_examples(part)
            reps, _ = model(batch["token_ids"], batch["lengths"])  # type: ignore[arg-type]
            for row_index, encoded in enumerate(part):
                for target in encoded.context.targets:
                    rows.append({
                        "uid": target.uid, "context_key": encoded.context.context_key,
                        "event_index": target.event_index, "source_group": target.source_group,
                        "device_family": target.device_family, "attack_family": target.attack_family,
                        "owner": target.owner, "label": target.label, "role": target.role,
                        "split": encoded.context.split(), "teacher_kind": target.teacher_kind,
                        "timestamp_epoch": float(target.timestamp_epoch),
                    })
                    representations.append(reps[row_index, target.event_index].cpu().numpy().astype(np.float32, copy=True))
                    controls.append(order_free_control(encoded.tokens[:target.event_index + 1]))
    frame = pd.DataFrame(rows)
    if frame["uid"].duplicated().any() or len(frame) != len(representations):
        raise F1Failure("fit representation UID conservation failure")
    return frame, np.stack(representations), np.stack(controls)


def context_terminal_indices(frame: pd.DataFrame, require_benign: bool = False) -> np.ndarray:
    subset = frame.loc[frame["label"].eq(0)].copy() if require_benign else frame.copy()
    ordered = subset.sort_values(["context_key", "event_index", "uid"], kind="mergesort")
    return ordered.groupby("context_key", sort=True).tail(1).index.to_numpy(dtype=np.int64)


def device_leakage_audit(frame: pd.DataFrame, representations: np.ndarray, controls: np.ndarray) -> Dict[str, object]:
    benign = frame.loc[frame["label"].eq(0)].copy()
    terminal = benign.loc[context_terminal_indices(benign)].copy()
    counts = terminal.groupby("device_family", sort=True)["context_key"].nunique()
    eligible = sorted(counts.loc[counts.ge(20)].index.astype(str))
    terminal = terminal.loc[terminal["device_family"].astype(str).isin(eligible)].copy()
    if len(eligible) < 2:
        raise F1Failure("device leakage audit has fewer than two eligible devices")
    train_indices: List[int] = []
    val_indices: List[int] = []
    for device, part in terminal.groupby("device_family", sort=True):
        ordered = sorted(
            part.index.to_list(),
            key=lambda index: (
                hashlib.sha256(("frontend-f1-d1-device-audit-v1\0" + str(frame.loc[index, "context_key"])).encode("utf-8")).digest(),
                str(frame.loc[index, "context_key"]),
            ),
        )
        n_val = max(4, int(math.ceil(len(ordered) / 5.0)))
        val_indices.extend(ordered[:n_val]); train_indices.extend(ordered[n_val:])
    y_train = frame.loc[train_indices, "device_family"].astype(str).to_numpy()
    y_val = frame.loc[val_indices, "device_family"].astype(str).to_numpy()
    def score(values: np.ndarray) -> Tuple[float, np.ndarray]:
        scaler = StandardScaler().fit(values[train_indices])
        classifier = OneVsRestClassifier(
            LogisticRegression(C=1.0, solver="liblinear", max_iter=2000, random_state=SEED)
        )
        classifier.fit(scaler.transform(values[train_indices]), y_train)
        prediction = classifier.predict(scaler.transform(values[val_indices]))
        return float(balanced_accuracy_score(y_val, prediction)), prediction
    learned, learned_prediction = score(representations)
    control, control_prediction = score(controls)
    rng = np.random.RandomState(SEED)
    null_values = [float(balanced_accuracy_score(y_val[rng.permutation(len(y_val))], learned_prediction)) for _ in range(1000)]
    return {
        "eligible_devices": eligible, "train_contexts": len(train_indices), "validation_contexts": len(val_indices),
        "learned_balanced_accuracy": learned, "control_balanced_accuracy": control,
        "learned_permutation_p99": float(np.quantile(null_values, 0.99)),
        "pass": bool(learned <= control + 0.05),
        "endpoint_masked_identical": True,
        "control_prediction_sha256": sha256_bytes(np.asarray(control_prediction).astype(str).tobytes()),
    }


def orthonormal_basis(matrix: np.ndarray, rank: int) -> Tuple[np.ndarray, np.ndarray]:
    _, singular, vt = np.linalg.svd(np.asarray(matrix, dtype=np.float64), full_matrices=False)
    if len(singular) < rank or singular[0] <= 0 or int(np.sum(singular > 1e-10 * singular[0])) < rank:
        raise F1Failure("geometry rank below frozen rank")
    basis = vt[:rank].T
    if np.linalg.norm(basis.T.dot(basis) - np.eye(rank), ord=2) > 1e-10:
        raise F1Failure("geometry basis orthogonality failure")
    return basis, singular


def principal_angle_degrees(left: np.ndarray, right: np.ndarray) -> float:
    singular = np.linalg.svd(left.T.dot(right), compute_uv=False)
    return float(np.degrees(np.arccos(np.clip(float(np.min(singular)), -1.0, 1.0))))


def geometry_audit(frame: pd.DataFrame, representations: np.ndarray) -> Dict[str, object]:
    devices = ["iotsim-building-monitor", "iotsim-combined-cycle", "iotsim-combined-cycle-tls",
               "iotsim-domotic-monitor", "ton-iot-external"]
    benign = frame.loc[frame["label"].eq(0) & frame["device_family"].isin(devices)].copy()
    terminal = benign.loc[context_terminal_indices(benign)].copy()
    counts = {
        str(key): int(value)
        for key, value in terminal.groupby("device_family")["context_key"].nunique().to_dict().items()
    }
    if set(counts) != set(devices) or any(int(counts[device]) < 64 for device in devices):
        raise F1Failure("frozen geometry device denominator drift")
    centers = {
        device: np.median(representations[terminal.loc[terminal["device_family"].eq(device)].index], axis=0)
        for device in devices
    }
    global_center = np.median(np.stack([centers[device] for device in devices]), axis=0)
    rank = 4
    try:
        full_basis, singular = orthonormal_basis(np.stack([centers[d] - global_center for d in devices]), rank)
    except F1Failure as exc:
        return {
            "rank": rank, "devices": devices, "contexts_by_device": counts,
            "pass": False, "failure": "GEOMETRY_RANK_BELOW_FROZEN_RANK",
            "detail": str(exc), "lodo_rows": [], "between_within_rows": [],
        }
    full_projection = full_basis.dot(full_basis.T)
    lodo_rows: List[Dict[str, object]] = []
    for held in devices:
        remaining = [device for device in devices if device != held]
        local_global = np.median(np.stack([centers[device] for device in remaining]), axis=0)
        try:
            local_basis, _ = orthonormal_basis(np.stack([centers[d] - local_global for d in remaining]), rank)
        except F1Failure as exc:
            return {
                "rank": rank, "devices": devices, "contexts_by_device": counts,
                "pass": False, "failure": "GEOMETRY_LODO_RANK_BELOW_FROZEN_RANK",
                "held_out_device": held, "detail": str(exc),
                "lodo_rows": lodo_rows, "between_within_rows": [],
            }
        distance = float(np.linalg.norm(full_projection - local_basis.dot(local_basis.T), ord="fro") / math.sqrt(2.0 * rank))
        lodo_rows.append({"held_out_device": held, "projection_distance": distance,
                          "principal_angle_degrees": principal_angle_degrees(full_basis, local_basis)})
    lodo = pd.DataFrame(lodo_rows)
    projector = full_projection
    ratio_rows: List[Dict[str, object]] = []
    for device in devices:
        part = terminal.loc[terminal["device_family"].eq(device)].sort_values(
            ["timestamp_epoch", "uid"], kind="mergesort"
        )
        values = representations[part.index.to_numpy(dtype=np.int64)]
        cut = len(values) // 2
        center = np.median(values, axis=0)
        early, late = np.median(values[:cut], axis=0), np.median(values[cut:], axis=0)
        between = float(np.linalg.norm(projector.dot(center - global_center)))
        within = float(np.linalg.norm(projector.dot(early - late)))
        ratio_rows.append({"device": device, "contexts": len(values), "ratio": between / max(within, 1e-12)})
    ratios = pd.DataFrame(ratio_rows)
    summary = {
        "rank": rank, "devices": devices, "contexts_by_device": counts,
        "median_projection_distance": float(lodo["projection_distance"].median()),
        "worst_projection_distance": float(lodo["projection_distance"].max()),
        "median_principal_angle_degrees": float(lodo["principal_angle_degrees"].median()),
        "worst_principal_angle_degrees": float(lodo["principal_angle_degrees"].max()),
        "median_between_within_ratio": float(ratios["ratio"].median()),
        "devices_ratio_at_least_1": int(ratios["ratio"].ge(1.0).sum()),
        "singular_values": singular.tolist(), "lodo_rows": lodo_rows, "between_within_rows": ratio_rows,
    }
    summary["pass"] = bool(
        summary["median_projection_distance"] <= 0.20 and summary["worst_projection_distance"] <= 0.35
        and summary["median_principal_angle_degrees"] <= 20.0
        and summary["worst_principal_angle_degrees"] <= 35.0
        and summary["median_between_within_ratio"] >= 2.0
        and summary["devices_ratio_at_least_1"] >= 4
    )
    return summary


def nearest_centroid_cosine_scores(
    train_values: np.ndarray, train_labels: np.ndarray, validation_values: np.ndarray,
) -> np.ndarray:
    scaler = StandardScaler().fit(train_values)
    train_scaled = scaler.transform(train_values)
    validation_scaled = scaler.transform(validation_values)
    if set(np.unique(train_labels).tolist()) != {0, 1}:
        raise F1Failure("nearest-centroid training requires both labels")
    centers = []
    for label in (0, 1):
        center = np.mean(train_scaled[train_labels == label], axis=0)
        centers.append(center / max(float(np.linalg.norm(center)), 1e-12))
    norms = np.maximum(np.linalg.norm(validation_scaled, axis=1, keepdims=True), 1e-12)
    normalized = validation_scaled / norms
    return normalized.dot(centers[1]) - normalized.dot(centers[0])


def diagnostic_denominators(frame: pd.DataFrame) -> List[Dict[str, object]]:
    result: List[Dict[str, object]] = []
    for keys, part in frame.groupby(["split", "source_group", "attack_family", "label"], sort=True):
        split, source, family, label = keys
        result.append({
            "split": str(split), "source_group": str(source),
            "attack_family": str(family) if str(family) else "<BENIGN>",
            "label": int(label), "rows": int(len(part)),
            "contexts": int(part["context_key"].nunique()),
        })
    return result


def attack_canary_audit(frame: pd.DataFrame, representations: np.ndarray, controls: np.ndarray) -> Dict[str, object]:
    train = frame["split"].eq("train").to_numpy()
    val = frame["split"].eq("internal_val").to_numpy()
    y_train = frame.loc[train, "label"].to_numpy(dtype=np.int64)
    y_val = frame.loc[val, "label"].to_numpy(dtype=np.int64)
    learned_prediction = fit_linear_canary(representations[train], y_train, representations[val])
    control_prediction = fit_linear_canary(controls[train], y_train, controls[val])
    weights = 1.0 / frame.loc[val].groupby("context_key")["context_key"].transform("count").to_numpy(dtype=np.float64)
    learned_auc = float(roc_auc_score(y_val, learned_prediction, sample_weight=weights))
    control_auc = float(roc_auc_score(y_val, control_prediction, sample_weight=weights))
    learned_null_p99 = permutation_p99(
        y_val, learned_prediction, frame.loc[val, "context_key"].astype(str).tolist(), 1000
    )
    control_null_p99 = permutation_p99(
        y_val, control_prediction, frame.loc[val, "context_key"].astype(str).tolist(), 1000
    )
    learned_centroid = nearest_centroid_cosine_scores(
        representations[train], y_train, representations[val]
    )
    control_centroid = nearest_centroid_cosine_scores(controls[train], y_train, controls[val])
    return {
        "train_rows": int(train.sum()), "validation_rows": int(val.sum()),
        "learned_auroc": learned_auc, "control_auroc": control_auc,
        "learned_permutation_p99": learned_null_p99,
        "control_permutation_p99": control_null_p99,
        "learned_nearest_centroid_cosine_auroc": float(
            roc_auc_score(y_val, learned_centroid, sample_weight=weights)
        ),
        "control_nearest_centroid_cosine_auroc": float(
            roc_auc_score(y_val, control_centroid, sample_weight=weights)
        ),
        "denominators": diagnostic_denominators(frame),
        "pass": bool(
            learned_auc >= 0.80
            and learned_auc >= control_auc + 0.02
            and learned_auc > learned_null_p99
        ),
        "endpoint_masked_identical": True,
        "claim_boundary": "Unified/A-dominated attack-information diagnostic; zero B attack contexts in internal validation.",
    }


def fit_availability_precheck(frame: pd.DataFrame, representations: np.ndarray) -> Dict[str, object]:
    """Apply the frozen availability rates on fit only; select remains unopened."""
    finite = np.isfinite(representations).all(axis=1)
    working = frame.copy()
    working["finite"] = finite

    def grouped(column: str, mask: pd.Series, minimum: float) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for key, part in working.loc[mask].groupby(column, sort=True):
            rate = float(part["finite"].mean())
            rows.append({"group": str(key), "rows": int(len(part)), "finite_rate": rate,
                         "minimum": minimum, "pass": bool(rate >= minimum)})
        return rows

    overall_rate = float(working["finite"].mean())
    old_missing = working["owner"].eq("B")
    old_missing_rate = float(working.loc[old_missing, "finite"].mean())
    benign_devices = grouped("device_family", working["label"].eq(0), 0.80)
    attack_families = grouped("attack_family", working["label"].eq(1), 0.80)
    missing_benign_devices = grouped(
        "device_family", old_missing & working["label"].eq(0), 0.80
    )
    missing_attack_families = grouped(
        "attack_family", old_missing & working["label"].eq(1), 0.80
    )
    group_rows = benign_devices + attack_families + missing_benign_devices + missing_attack_families
    return {
        "scope": "LEGAL_FIT_PRECHECK_ONLY_SELECT_UNOPENED",
        "rows": int(len(working)), "unique_uids": int(working["uid"].nunique()),
        "overall_finite_rate": overall_rate, "overall_minimum": 0.90,
        "old_missing_rows": int(old_missing.sum()), "old_missing_finite_rate": old_missing_rate,
        "old_missing_minimum": 0.90,
        "benign_device_rows": benign_devices, "attack_family_rows": attack_families,
        "old_missing_benign_device_rows": missing_benign_devices,
        "old_missing_attack_family_rows": missing_attack_families,
        "pass": bool(
            len(working) == EXPECTED_LEGAL_FIT_ROWS
            and working["uid"].nunique() == EXPECTED_LEGAL_FIT_ROWS
            and overall_rate >= 0.90 and old_missing_rate >= 0.90
            and all(bool(row["pass"]) for row in group_rows)
        ),
        "claim_boundary": "This is not the frozen 25,467-row availability verdict; select is still unopened.",
    }


def fit_representation_audit(model: F1Encoder, examples: Sequence[EncodedExample], output_dir: Path) -> Dict[str, object]:
    started = time.perf_counter()
    frame, representations, controls = represent_examples(model, examples)
    terminal = context_terminal_indices(frame)
    collapse = collapse_metrics(representations[terminal])
    availability = fit_availability_precheck(frame, representations)
    collapse_result = {**collapse, "pass": collapse_pass(collapse)}
    enforce_resource_caps(output_dir)
    if not availability["pass"] or not collapse_result["pass"]:
        leakage = {"status": "NOT_EVALUATED_AFTER_AVAILABILITY_OR_COLLAPSE_FAILURE", "pass": False}
        geometry = {"status": "NOT_EVALUATED_AFTER_AVAILABILITY_OR_COLLAPSE_FAILURE", "pass": False}
        attack = {"status": "NOT_EVALUATED_AFTER_AVAILABILITY_OR_COLLAPSE_FAILURE", "pass": False}
    else:
        leakage = device_leakage_audit(frame, representations, controls)
        enforce_resource_caps(output_dir)
        geometry = geometry_audit(frame, representations)
        enforce_resource_caps(output_dir)
        attack = attack_canary_audit(frame, representations, controls)
        enforce_resource_caps(output_dir)
    elapsed = time.perf_counter() - started
    if elapsed > 4 * 3600:
        raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "post-checkpoint evaluation wall cap exceeded")
    result = {
        "fit_availability_precheck": availability,
        "collapse": collapse_result,
        "device_leakage": leakage, "geometry": geometry, "attack_information": attack,
        "endpoint_masked_identical": True, "post_checkpoint_seconds": elapsed,
    }
    result["pass"] = bool(
        availability["pass"] and result["collapse"]["pass"] and leakage["pass"]
        and geometry["pass"] and attack["pass"]
    )
    atomic_npz(
        output_dir / "f1_d1_fit_representations.npz", uid=frame["uid"].astype(str).to_numpy(),
        representation=representations.astype(np.float32), control=controls.astype(np.float32),
    )
    atomic_gzip_frame(output_dir / "f1_d1_fit_representation_rows.csv.gz", frame)
    atomic_json(output_dir / "f1_d1_fit_representation_audit.json", result)
    return result


def permutation_p99(labels: np.ndarray, predictions: np.ndarray, context_ids: Sequence[str], repeats: int = 1000) -> float:
    frame = pd.DataFrame({"label": labels.astype(int), "prediction": predictions, "context": list(context_ids)})
    context_labels = frame.groupby("context", sort=True)["label"].first()
    if not frame.groupby("context")["label"].nunique().le(1).all():
        raise F1Failure("context label is not unique for permutation")
    rng = np.random.RandomState(SEED)
    values: List[float] = []
    contexts = context_labels.index.to_numpy()
    base = context_labels.to_numpy()
    for _ in range(repeats):
        shuffled = base[rng.permutation(len(base))]
        mapping = dict(zip(contexts, shuffled))
        y = frame["context"].map(mapping).to_numpy(dtype=int)
        values.append(0.5 if len(np.unique(y)) < 2 else float(roc_auc_score(y, predictions)))
    return float(np.quantile(values, 0.99))


def write_sha256s(output_dir: Path) -> None:
    members = [path for path in sorted(Path(output_dir).iterdir(), key=lambda item: item.name)
               if path.is_file() and path.name != "SHA256SUMS"]
    atomic_text(Path(output_dir) / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(path), path.name) for path in members))


def record_engineering_failure(output_dir: Path, exc: BaseException) -> None:
    output = Path(output_dir).resolve()
    runs_root = (ROOT / "runs").resolve()
    try:
        output.relative_to(runs_root)
    except ValueError:
        return
    output.mkdir(parents=True, exist_ok=True)
    verdict = output / "f1_d1_verdict.json"
    if verdict.is_file():
        verdict.unlink()
    atomic_json(output / "engineering_failure.json", {
        "status": "F1_ENGINEERING_OR_PROTOCOL_FAILURE",
        "scientific_verdict_emitted": False,
        "error_type": type(exc).__name__, "error": str(exc),
        "traceback": traceback.format_exc(),
    })


def record_scientific_stop(output_dir: Path, exc: ScientificStop) -> None:
    output = Path(output_dir).resolve()
    try:
        output.relative_to((ROOT / "runs").resolve())
    except ValueError:
        return
    output.mkdir(parents=True, exist_ok=True)
    engineering = output / "engineering_failure.json"
    if engineering.is_file():
        engineering.unlink()
    atomic_json(output / "f1_d1_scientific_stop.json", {
        "status": exc.status, "reason": exc.reason,
        "contract_sha256": FROZEN_SHA256,
        "select_opened": 0, "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
    })
    write_sha256s(output)


def synthetic_contexts() -> List[ContextExample]:
    result: List[ContextExample] = []
    for index in range(12):
        source = "normal_scanning1.pcap" if index >= 8 else "train_source_%02d" % index
        label = 1 if index % 3 == 0 else 0
        owner = "B" if index % 4 == 0 else "A"
        teacher = "none" if owner == "B" else ("attack_hard" if label else "benign_normal")
        signatures = ["H1\x1fA_TO_B\x1f%d" % value for value in range(1 + index % 4)]
        result.append(ContextExample(
            "context_%02d" % index, source, signatures,
            [TargetEntry("uid_%02d" % index, len(signatures) - 1, owner, label, teacher,
                         "support_train", source, "device_%d" % (index % 3), "family_%d" % (index % 2))]
        ))
    return result


@dataclass
class ReplayBucket:
    source_group: str
    member_id: str
    context_key: str
    signatures: List[str]
    targets: List[Tuple[str, int]]


def replay_member_signatures(
    engine: Any, decoded: Iterable[Tuple[Mapping[str, str], Any]], targets: Sequence[Any],
    last_target: Mapping[Tuple[object, ...], int],
) -> Tuple[List[ReplayBucket], Dict[str, int]]:
    by_position = {int(target.packet_ordinal): target for target in targets}
    endpoint_tokens = engine.EndpointTokens()
    active: MutableMapping[Tuple[object, ...], Any] = {}
    active_bucket: MutableMapping[Tuple[object, ...], ReplayBucket] = {}
    next_epoch: Dict[Tuple[object, ...], int] = {}
    closed: Set[Tuple[object, ...]] = set()
    h4_current: Optional[Tuple[object, ...]] = None
    buckets: Dict[str, ReplayBucket] = {}
    seen_uids: Set[str] = set()
    maximum = max(by_position)
    decoded_rows = 0
    peak_active = 0
    for index, pair in enumerate(decoded):
        raw, event = pair
        decoded_rows += 1
        if index > maximum:
            raise F1Failure("fit replay crossed exact target cutoff")
        route = engine.classify_route(event, endpoint_tokens)
        identity = (route.tier, route.base_key)
        target = by_position.get(index)
        missing_reason = engine._event_missing_reason(event)
        if route.tier == "H4" and h4_current is not None and h4_current != identity:
            active.pop(h4_current, None)
            active_bucket.pop(h4_current, None)
        if route.tier == "H4":
            h4_current = identity
        is_active = identity in last_target and index <= int(last_target[identity]) and identity not in closed
        state = active.get(identity)
        bucket = active_bucket.get(identity)
        if is_active and not missing_reason:
            previous_state = state
            previous_last = None if previous_state is None else float(previous_state.last_surrogate)
            state, epoch_value = engine.SemanticPrototype._append_or_split(
                route, state, next_epoch.get(identity, 0), float(event.timestamp)
            )
            next_epoch[identity] = epoch_value
            active[identity] = state
            new_epoch = previous_state is None or state is not previous_state
            if new_epoch:
                context_id = engine._context_id(str(event.source_id), str(event.member_id), state)
                context_key = "%s\x1f%s\x1f%d" % (event.member_id, context_id, int(state.epoch))
                bucket = ReplayBucket(str(event.source_id), str(event.member_id), context_key, [], [])
                if context_key in buckets:
                    raise F1Failure("semantic context identity reused")
                buckets[context_key] = bucket
                active_bucket[identity] = bucket
                surrogate_delta = 0.0
                regression = False
            else:
                if bucket is None or previous_last is None:
                    raise F1Failure("active context bucket missing")
                surrogate_delta = max(previous_last, float(event.timestamp)) - previous_last
                regression = float(event.timestamp) < previous_last
            assert bucket is not None
            direction = engine._direction(route, state)
            bucket.signatures.append(
                canonical_signature(raw, event, route, direction, surrogate_delta, regression)
            )
            peak_active = max(peak_active, len(active))
        if target is not None:
            if event.target_uid != target.uid or target.uid in seen_uids:
                raise F1Failure("fit target identity drift")
            if missing_reason or not is_active or state is None or bucket is None:
                raise F1Failure("frozen semantic-finite target became missing")
            bucket.targets.append((str(target.uid), len(bucket.signatures) - 1))
            seen_uids.add(str(target.uid))
        if identity in last_target and index == int(last_target[identity]):
            active.pop(identity, None)
            active_bucket.pop(identity, None)
            closed.add(identity)
            if h4_current == identity:
                h4_current = None
        if index == maximum:
            break
    expected = {str(target.uid) for target in targets}
    if decoded_rows != maximum + 1 or seen_uids != expected or active:
        raise F1Failure("fit replay lifecycle/conservation failure")
    retained = [bucket for bucket in buckets.values() if bucket.targets]
    if sum(len(bucket.targets) for bucket in retained) != len(targets):
        raise F1Failure("fit replay target conservation failure")
    return sorted(retained, key=lambda value: value.context_key), {
        "replay_packets": decoded_rows, "peak_active_contexts": peak_active,
        "terminal_active_contexts": len(active),
    }


def bucket_to_json(bucket: ReplayBucket) -> Dict[str, object]:
    return {
        "source_group": bucket.source_group,
        "member_id": bucket.member_id,
        "context_key": bucket.context_key,
        "signatures": list(bucket.signatures),
        "targets": [{"uid": uid, "event_index": index} for uid, index in bucket.targets],
    }


def bucket_from_json(value: Mapping[str, object]) -> ReplayBucket:
    targets = [(str(row["uid"]), int(row["event_index"])) for row in value["targets"]]  # type: ignore[index]
    return ReplayBucket(str(value["source_group"]), str(value["member_id"]), str(value["context_key"]),
                        [str(item) for item in value["signatures"]], targets)  # type: ignore[index]


def read_gzip_jsonl(path: Path) -> List[Dict[str, object]]:
    with gzip.open(str(path), "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def join_buckets_to_examples(
    buckets: Sequence[ReplayBucket], descriptors: pd.DataFrame,
    teacher_benign: Mapping[str, bool],
) -> List[ContextExample]:
    if descriptors["uid"].duplicated().any():
        raise F1Failure("descriptor UID duplication")
    lookup = descriptors.set_index("uid", drop=False)
    examples: List[ContextExample] = []
    seen: Set[str] = set()
    for bucket in buckets:
        targets: List[TargetEntry] = []
        for uid, event_index in bucket.targets:
            if uid in seen or uid not in lookup.index:
                raise F1Failure("bucket/descriptor UID mismatch")
            row = lookup.loc[uid]
            if str(row["semantic_context_key"]) != bucket.context_key or not bool(row["legal_fit"]):
                raise F1Failure("bucket context or legal-fit identity drift")
            owner = str(row["owner"])
            label = 1 if str(row["label_kind"]) == "attack" else 0
            if owner == "A" and label == 1:
                teacher_kind = "attack_hard"
            elif owner == "A" and label == 0:
                if uid not in teacher_benign:
                    raise F1Failure("A benign teacher verdict absent")
                teacher_kind = "benign_hard" if teacher_benign[uid] else "benign_normal"
            else:
                teacher_kind = "none"
            targets.append(TargetEntry(
                uid, int(event_index), owner, label, teacher_kind, str(row["role"]),
                str(row["source_group"]), str(row["device_family"]), str(row["attack_family"]),
                float(row["timestamp_epoch"]),
            ))
            seen.add(uid)
        sources = {target.source_group for target in targets}
        if sources != {bucket.source_group}:
            raise F1Failure("context source-group drift")
        examples.append(ContextExample(bucket.context_key, bucket.source_group, list(bucket.signatures), targets))
    if seen != set(descriptors.loc[descriptors["legal_fit"].astype(bool), "uid"].astype(str)):
        raise F1Failure("legal-fit UID conservation failure")
    return sorted(examples, key=lambda value: value.context_key)


def materialize_fit(args: argparse.Namespace) -> None:
    if args.authorization_token != MATERIALIZE_TOKEN:
        raise F1Failure("fit corpus materialization is not authorized")
    out = Path(args.output_dir).resolve()
    assert_scope_paths([out])
    assert_output_under_runs(out)
    stage = out.with_name(".%s.stage" % out.name)
    if out.exists():
        raise F1Failure("refusing to overwrite fit corpus")
    stage.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = stage / "member_checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)
    identities = {
        "frozen": require_sha(ROOT, FROZEN_REL, FROZEN_SHA256),
        "parent": require_sha(ROOT, PARENT_REL, PARENT_SHA256),
        "zt_engine": require_sha(ROOT, ZT_ENGINE_REL, ZT_ENGINE_SHA256),
        "zt_runner": require_sha(ROOT, ZT_RUNNER_REL, ZT_RUNNER_SHA256),
        "d0_verdict": require_sha(ROOT, D0_REL / "f1_d0_verdict.json", D0_VERDICT_SHA256),
        "d0_table": require_sha(ROOT, D0_REL / "f1_d0_uid_context_phase_owner_conservation.csv.gz", D0_TABLE_SHA256),
        "teacher_benign_counts": require_sha(ROOT, TEACHER_REL / "f1_teacher_benign_counts.json", TEACHER_COUNTS_SHA256),
        "teacher_benign_uids": require_sha(ROOT, TEACHER_REL / "f1_teacher_benign_uid_verdicts.csv.gz", TEACHER_UID_SHA256),
        "embedding_metadata": require_sha(ROOT, EMBEDDING_METADATA_REL, EMBEDDING_METADATA_SHA256),
    }
    if shutil.disk_usage(str(out.anchor)).free < 12 * 1024 ** 3:
        raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "free space below 12 GiB")
    zt_runner = import_file("f1_d1_pinned_zt_runner", ROOT / ZT_RUNNER_REL)
    engine, target_identity, packet_identities, tshark_identity, zt_pins = zt_runner.preflight(stage, Path(args.tshark))
    # Construction opens only UID plus the already-frozen legal-fit Boolean.
    # Label/owner/device/family columns remain unopened until all member replay
    # has completed and exact semantic-context conservation has passed.
    construction_allowlist = pd.read_csv(
        ROOT / D0_REL / "f1_d0_uid_context_phase_owner_conservation.csv.gz",
        usecols=["uid", "legal_fit"], keep_default_na=False,
    )
    construction_allowlist["legal_fit"] = construction_allowlist["legal_fit"].astype(str).str.lower().eq("true")
    legal_uids = set(construction_allowlist.loc[construction_allowlist["legal_fit"], "uid"].astype(str))
    if len(legal_uids) != EXPECTED_LEGAL_FIT_ROWS:
        raise F1Failure("legal-fit denominator drift")
    construction_targets = target_identity.loc[target_identity["uid"].astype(str).isin(legal_uids)].copy()
    if len(construction_targets) != EXPECTED_LEGAL_FIT_ROWS:
        raise F1Failure("construction target UID join drift")
    identity_keys = ["dataset_kind", "container_path", "raw_source_path"]
    identity_map = {
        tuple(str(getattr(row, key)) for key in identity_keys): row._asdict()
        for row in packet_identities.itertuples(index=False)
    }
    previous_ledger = stage / "f1_d1_materialization_progress.json"
    previous_seconds = 0.0
    if previous_ledger.is_file():
        previous_seconds = float(json.loads(previous_ledger.read_text(encoding="utf-8"))["cumulative_seconds"])
    session_started = time.perf_counter()
    all_buckets: List[ReplayBucket] = []
    member_rows: List[Dict[str, object]] = []
    implementation_sha = sha256_file(Path(__file__))
    runner_sha = REPLAY_IMPLEMENTATION_SHA256
    groups = list(construction_targets.groupby(identity_keys, sort=True))
    for member_index, (raw_key, part) in enumerate(groups, start=1):
        key = tuple(str(item) for item in raw_key)
        packet_identity = identity_map.get(key)
        if packet_identity is None:
            raise F1Failure("packet member absent from identity attachment")
        source = str(part["source_group"].iloc[0])
        member = key[2]
        spec_by_position = {
            int(row.target_event_position_within_capture): engine.TargetSpec(
                str(row.uid), source, member, int(row.target_event_position_within_capture)
            ) for row in part.itertuples(index=False)
        }
        ordered = sorted((target.uid, int(target.packet_ordinal)) for target in spec_by_position.values())
        checkpoint_identity = sha256_bytes(canonical_json_bytes({
            "frozen": FROZEN_SHA256, "runner": runner_sha, "packet": packet_identity,
            "tshark": tshark_identity, "targets": ordered,
        }))
        data_path = checkpoint_dir / (checkpoint_identity[:24] + ".jsonl.gz")
        marker_path = checkpoint_dir / (checkpoint_identity[:24] + ".complete.json")
        if data_path.is_file() and marker_path.is_file():
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("identity") != checkpoint_identity or marker.get("sha256") != sha256_file(data_path):
                raise F1Failure("member checkpoint identity drift")
            buckets = [bucket_from_json(value) for value in read_gzip_jsonl(data_path)]
            status = "REUSED_EXACT_MEMBER_BOUNDARY"
            lifecycle = {"replay_packets": 0, "peak_active_contexts": 0, "terminal_active_contexts": 0}
            discovery_packets = 0
        else:
            maximum = max(spec_by_position)
            def first_events() -> Iterator[Any]:
                for position, raw in enumerate(zt_runner.iter_tshark_rows(Path(args.tshark), packet_identity, maximum + 1)):
                    target = spec_by_position.get(position)
                    yield zt_runner.raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)
            last_target, discovery_packets = zt_runner.discover_member(
                engine, first_events(), set(spec_by_position), maximum
            )
            def second_events() -> Iterator[Tuple[Mapping[str, str], Any]]:
                for position, raw in enumerate(zt_runner.iter_tshark_rows(Path(args.tshark), packet_identity, maximum + 1)):
                    target = spec_by_position.get(position)
                    event = zt_runner.raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)
                    yield raw, event
            buckets, lifecycle = replay_member_signatures(
                engine, second_events(), list(spec_by_position.values()), last_target
            )
            atomic_gzip_jsonl(data_path, (bucket_to_json(bucket) for bucket in buckets))
            atomic_json(marker_path, {"identity": checkpoint_identity, "sha256": sha256_file(data_path),
                                      "targets": len(part), "contexts": len(buckets)})
            status = "COMPUTED_EXACT_TWOPASS"
        all_buckets.extend(buckets)
        member_rows.append({
            "member_index": member_index, "members_total": len(groups), "member_id": member,
            "targets": len(part), "contexts": len(buckets), "status": status,
            "checkpoint_identity": checkpoint_identity, "checkpoint_sha256": sha256_file(data_path),
            "discovery_packets": discovery_packets, "replay_packets": lifecycle["replay_packets"],
            "peak_active_contexts": lifecycle["peak_active_contexts"],
        })
        cumulative = previous_seconds + (time.perf_counter() - session_started)
        atomic_json(previous_ledger, {"cumulative_seconds": cumulative, "members_complete": member_index,
                                      "members_total": len(groups)})
        if cumulative > 4 * 3600:
            raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "corpus wall cap exceeded")
        enforce_resource_caps(stage)
        print("F1_D1_CORPUS_MEMBER_COMPLETE index=%d/%d member=%s targets=%d" %
              (member_index, len(groups), member, len(part)), flush=True)
    # Only after construction is complete may authorized fit descriptors enter.
    descriptors = pd.read_csv(
        ROOT / D0_REL / "f1_d0_uid_context_phase_owner_conservation.csv.gz", keep_default_na=False
    )
    descriptors["legal_fit"] = descriptors["legal_fit"].astype(str).str.lower().eq("true")
    # The target plan legitimately stores `nan` for 12,000 ToN rows. The
    # inherited Lane-G timestamp ordering is defined by the already-pinned
    # embedding metadata, which has one finite causal timestamp per frozen UID.
    timestamp_frame = pd.read_csv(
        ROOT / EMBEDDING_METADATA_REL, usecols=["uid", "timestamp_epoch"], keep_default_na=False
    )
    timestamp_frame["timestamp_epoch"] = pd.to_numeric(timestamp_frame["timestamp_epoch"], errors="raise")
    if timestamp_frame["uid"].duplicated().any() or not np.isfinite(timestamp_frame["timestamp_epoch"]).all():
        raise F1Failure("inherited timestamp metadata identity/conservation drift")
    descriptors = descriptors.merge(timestamp_frame, on="uid", how="left", validate="one_to_one")
    if descriptors["timestamp_epoch"].isna().any():
        raise F1Failure("target timestamp join drift")
    teacher_frame = pd.read_csv(ROOT / TEACHER_REL / "f1_teacher_benign_uid_verdicts.csv.gz", keep_default_na=False)
    if teacher_frame["uid"].duplicated().any():
        raise F1Failure("teacher-benign UID duplication")
    teacher_map = {
        str(row.uid): str(row.hard).strip().lower() == "true"
        for row in teacher_frame.itertuples(index=False)
    }
    examples = join_buckets_to_examples(all_buckets, descriptors, teacher_map)
    validate_split(examples)
    if len(examples) != EXPECTED_LEGAL_FIT_CONTEXTS or sum(len(item.targets) for item in examples) != EXPECTED_LEGAL_FIT_ROWS:
        raise F1Failure("fit corpus conservation failure")
    corpus_path = stage / "f1_d1_fit_contexts.jsonl.gz"
    atomic_gzip_jsonl(corpus_path, (context_to_json(item) for item in examples))
    atomic_csv(stage / "f1_d1_member_materialization_audit.csv", member_rows, list(member_rows[0]))
    atomic_json(stage / "f1_d1_fit_corpus_manifest.json", {
        "status": "F1_D1_FIT_CORPUS_MATERIALIZED", "contract_sha256": FROZEN_SHA256,
        "rows": EXPECTED_LEGAL_FIT_ROWS, "contexts": EXPECTED_LEGAL_FIT_CONTEXTS,
        "train_rows": EXPECTED_TRAIN_ROWS, "train_contexts": EXPECTED_TRAIN_CONTEXTS,
        "internal_val_rows": EXPECTED_VAL_ROWS, "internal_val_contexts": EXPECTED_VAL_CONTEXTS,
        "corpus_sha256": sha256_file(corpus_path), "input_identities": identities,
        "zt_pins": zt_pins, "tshark_identity": tshark_identity,
        "implementation_sha256": implementation_sha,
        "replay_implementation_sha256": REPLAY_IMPLEMENTATION_SHA256,
        "materialization_cumulative_seconds": previous_seconds + (time.perf_counter() - session_started),
        "resource_usage": enforce_resource_caps(stage),
        "labels_read_during_semantic_construction": 0, "select_targets_materialized": 0,
        "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
    })
    write_sha256s(stage)
    os.replace(str(stage), str(out))
    print(json.dumps({"status": "F1_D1_FIT_CORPUS_MATERIALIZED", "output": str(out)}, indent=2))


def train_fit(args: argparse.Namespace) -> None:
    if args.authorization_token != TRAIN_TOKEN:
        raise F1Failure("one-shot local training is not authorized")
    paths = [Path(args.corpus), Path(args.output_dir), ROOT / STAGE_REL / "ckda_d1_probe_state.npz"]
    assert_scope_paths(paths)
    seed_runtime()
    verify_runtime()
    require_sha(ROOT, FROZEN_REL, FROZEN_SHA256)
    require_sha(ROOT, PARENT_REL, PARENT_SHA256)
    require_sha(ROOT, STAGE_REL / "ckda_d1_probe_state.npz", PROBE_STATE_SHA256)
    corpus_path = Path(args.corpus).resolve()
    manifest_path = corpus_path.parent / "f1_d1_fit_corpus_manifest.json"
    if not manifest_path.is_file():
        raise F1Failure("fit corpus manifest absent")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("status") != "F1_D1_FIT_CORPUS_MATERIALIZED"
            or manifest.get("contract_sha256") != FROZEN_SHA256
            or manifest.get("corpus_sha256") != sha256_file(corpus_path)
            or int(manifest.get("rows", -1)) != EXPECTED_LEGAL_FIT_ROWS
            or int(manifest.get("contexts", -1)) != EXPECTED_LEGAL_FIT_CONTEXTS):
        raise F1Failure("fit corpus identity/conservation drift")
    contexts = read_contexts(corpus_path)
    validate_split(contexts)
    vocabulary, vocabulary_sha = build_vocabulary(contexts)
    encoded = encode_examples(contexts, vocabulary)
    train = [item for item in encoded if item.context.split() == "train"]
    val = [item for item in encoded if item.context.split() == "internal_val"]
    p2 = load_probe_state(ROOT / STAGE_REL / "ckda_d1_probe_state.npz")
    output = Path(args.output_dir).resolve()
    assert_output_under_runs(output)
    resume = None if args.resume is None else Path(args.resume).resolve()
    if resume is None and output.exists():
        raise F1Failure("refusing to overwrite one-shot training output")
    if resume is not None and not resume.is_file():
        raise F1Failure("resume checkpoint absent")
    if shutil.disk_usage(str(output.anchor)).free < 12 * 1024 ** 3:
        raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "free space below 12 GiB")
    output.mkdir(parents=True, exist_ok=True)
    vocabulary_path = output / "f1_d1_vocabulary.json"
    split_path = output / "f1_d1_internal_split.json"
    if resume is None:
        ordered_vocabulary = [
            {"token_id": token_id, "signature": signature}
            for signature, token_id in sorted(vocabulary.items(), key=lambda item: item[1])
        ]
        atomic_json(vocabulary_path, {"PAD": 0, "UNK": 1, "items": ordered_vocabulary,
                                      "identity_sha256": vocabulary_sha})
        atomic_json(split_path, {
            "validation_sources": sorted(VAL_SOURCES), "counts": validate_split(contexts),
            "context_keys_sha256": sha256_bytes(canonical_json_bytes(sorted(item.context_key for item in contexts))),
        })
    elif not vocabulary_path.is_file() or not split_path.is_file():
        raise F1Failure("resume vocabulary/split identity absent")
    run_identity = {
        "contract_sha256": FROZEN_SHA256, "parent_sha256": PARENT_SHA256,
        "corpus_sha256": sha256_file(corpus_path), "vocabulary_sha256": vocabulary_sha,
        "vocabulary_file_sha256": sha256_file(vocabulary_path),
        "split_file_sha256": sha256_file(split_path),
        "probe_state_sha256": PROBE_STATE_SHA256, "threshold_marker_sha256": THRESHOLD_SHA256,
    }
    result = train_loop(train, val, p2, output, max_epochs=100, batch_size=32,
                        resume_path=resume, run_identity=run_identity)
    if sha256_file(ROOT / STAGE_REL / "ckda_d1_probe_state.npz") != PROBE_STATE_SHA256:
        raise F1Failure("frozen P2 changed during training")
    if sha256_file(ROOT / STAGE_REL / "ckda_d1_threshold_freeze_marker.json") != THRESHOLD_SHA256:
        raise F1Failure("frozen threshold changed during training")
    if result.get("status") == "CHECKPOINT_FROZEN":
        checkpoint_path = Path(str(result["best_checkpoint"]))
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        if checkpoint.get("runtime_manifest") != expected_runtime_manifest():
            raise F1Failure("best checkpoint runtime identity drift")
        if dict(checkpoint.get("run_identity", {})) != run_identity:
            raise F1Failure("best checkpoint scientific identity drift")
        model = F1Encoder()
        model.load_state_dict(checkpoint["model"], strict=True)
        model.eval()
        audit = fit_representation_audit(model, encoded, output)
        materialization_seconds = float(manifest.get("materialization_cumulative_seconds", 0.0))
        process_chain_seconds = materialization_seconds + float(result["cumulative_seconds"]) + float(
            audit["post_checkpoint_seconds"]
        )
        if process_chain_seconds > 24 * 3600:
            raise ScientificStop("F1_D0_RESOURCE_OR_CANDIDATE_NO_GO", "overall process-chain cap exceeded")
        result["best_checkpoint_sha256"] = sha256_file(checkpoint_path)
        result["fit_representation_audit"] = audit
        result["process_chain_seconds"] = process_chain_seconds
        result["resource_usage"] = enforce_resource_caps(output)
        if audit["pass"]:
            result["status"] = "F1_D1_FIT_GATE_PASS_AWAITING_SELECT_AUTHORIZATION"
            result["scientific_verdict"] = None
        else:
            result["status"] = "F1_REPRESENTATION_NO_GO"
            result["scientific_verdict"] = "F1_REPRESENTATION_NO_GO"
        result["select_opened"] = 0
        result["viewed_opened"] = 0
        result["report_opened"] = 0
        result["final_opened"] = 0
    result["vocabulary_sha256"] = vocabulary_sha
    result["contract_sha256"] = FROZEN_SHA256
    atomic_json(output / "f1_d1_training_status.json", result)
    write_sha256s(output)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))


def evaluate_select(args: argparse.Namespace) -> None:
    if args.authorization_token != SELECT_TOKEN:
        raise F1Failure("one-shot select evaluation is not authorized")
    raise F1Failure("SELECT_EVALUATION_REQUIRES_SEPARATELY_REVIEWED_FROZEN_CHECKPOINT")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser()
    sub = value.add_subparsers(dest="mode", required=True)
    materialize = sub.add_parser("materialize-fit")
    materialize.add_argument("--authorization-token", required=True)
    materialize.add_argument("--tshark", type=Path, required=True)
    materialize.add_argument("--output-dir", type=Path, required=True)
    materialize.set_defaults(function=materialize_fit)
    train = sub.add_parser("train-fit")
    train.add_argument("--authorization-token", required=True)
    train.add_argument("--corpus", type=Path, required=True)
    train.add_argument("--output-dir", type=Path, required=True)
    train.add_argument("--resume", type=Path)
    train.set_defaults(function=train_fit)
    select = sub.add_parser("evaluate-select")
    select.add_argument("--authorization-token", required=True)
    select.add_argument("--checkpoint", type=Path, required=True)
    select.add_argument("--corpus", type=Path, required=True)
    select.add_argument("--output-dir", type=Path, required=True)
    select.set_defaults(function=evaluate_select)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        args.function(args)
        return 0
    except ScientificStop as exc:
        output = getattr(args, "output_dir", None)
        if output is not None:
            record_scientific_stop(Path(output), exc)
        print("%s: %s" % (exc.status, exc.reason), file=sys.stderr)
        return 2
    except BaseException as exc:
        output = getattr(args, "output_dir", None)
        if output is not None:
            record_engineering_failure(Path(output), exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
