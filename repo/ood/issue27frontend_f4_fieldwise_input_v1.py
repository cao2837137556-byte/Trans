#!/usr/bin/env python3
"""Frozen Frontend-F4 fieldwise input audit (no model, score, or training)."""

from __future__ import annotations

import argparse
import ast
import csv
import ctypes
import gzip
import hashlib
import importlib.util
import json
import math
import os
import platform
import re
import shutil
import struct
import sys
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL_REL = Path("runs/mainline_docs/frontend_f4_fieldwise_input_feasibility_frozen_20260905.md")
PROTOCOL_SHA256 = "6c5408d2437cf53aafefad6b68dd7932ffefe9309004b9a4ee673cc8f3ffc8dd"
TEST_REL = Path("repo/ood/issue27frontend_f4_fieldwise_input_contract_tests_v1.py")
F3_REL = Path("runs/frontend_f3_full_fit_l1_identifiability_v1_20260905")
EXECUTION_TOKEN = "I_AUTHORIZE_FRONTEND_F4_NO_MODEL_FIELDWISE_AUDIT"
EXPECTED_TARGETS = 13_866
EXPECTED_CONTEXTS = 9_307
EXPECTED_TRAIN_TARGETS = 8_660
EXPECTED_VAL_TARGETS = 5_206
EXPECTED_TRAIN_CONTEXTS = 4_984
EXPECTED_VAL_CONTEXTS = 4_323
EXPECTED_KILL = 5
WIDTH = 131
MAX_WALL_SECONDS = 1_800.0
MAX_PEAK_BYTES = 4 * 1024**3
MAX_OUTPUT_BYTES = 2 * 1024**3
MIN_FREE_BYTES = 3 * 1024**3

INPUT_PINS = {
    "SHA256SUMS": "a294d93bfe2fdb9c221f3589e3a8da877e9ae8679ad6102e35c8f4323165e1c1",
    "f3b_l1_contexts.jsonl.gz": "87383b24ff506edfb6561b3aa24776ce5c46f8c4c6d274c301f4b6c6e3337b01",
    "f3b_target_prefix_audit.csv.gz": "fdd9eeb75170fe30affb71b5a25b5f2dcb5e5c3ac5efecad4dc72d7fc7e5d1bd",
    "f3b_identities.json": "073b28f5f3617d8c2c1ff0fd919cd02116b961d35ccc7ea5de6e7581d03f2b09",
    "f3b_verdict.json": "6975f2a56526b7cb71982039486919c8cd963ba99799806209183d28ed3a0d11",
    "f3b_kill_only_audit.csv": "e6b7bf6f5288cbf288caf9a7378adf7061afccfa48cd0a1ef223e55f4b4c98c9",
    "f3b_nested_split_census.csv": "29f03e8408cdf1c9eadc0071dc138cc6faa0232ed1dd40f145c41ced2b6e1514",
    "checkpoints/6c1c4e7926631066034dae98.jsonl.gz": "f2f88316954366070b0f4f249c2f45b7d3a749c23c522f5f76ee3b6cd7071d2c",
}
SOURCE_PINS = {
    "repo/ood/issue27frontend_f1_d1_train_v1.py": "6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634",
    "repo/ood/issue27frontend_f3_full_fit_l1_identifiability_v1.py": "69fc92fb417fe8dbca646c30aaaf7f7ea40edf81ecae3c4fe36d831434e35a67",
    "repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py": "ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60",
}

TIER = ("H1", "H2", "H3", "H4")
DIRECTION = ("A_TO_B", "B_TO_A", "UNKNOWN")
VERSION = ("NONE", "4", "6")
PROTOCOL_GROUP = ("TCP", "UDP", "ICMP", "GRE", "OTHER_IP", "NON_IP", "KEYLESS")
LENGTH_BIN = ("<=63", "64-127", "128-255", "256-511", "512-1023", "1024-1518", "1519-4095", ">=4096")
DELTA_BIN = ("0", "(0,1e-6]", "(1e-6,1e-3]", "(1e-3,1e-2]", "(1e-2,1e-1]", "(1e-1,1]", "(1,10]", "(10,60]", ">60")
PRESENCE_FIELDS = (
    "eth.dst", "eth.src", "eth.type", "frame.encap_type", "gre.key",
    "icmp.code", "icmp.type", "icmpv6.code", "icmpv6.type",
    "ip.dst", "ip.proto", "ip.src", "ipv6.dst", "ipv6.nxt", "ipv6.src",
    "sctp.dstport", "sctp.srcport", "tcp.dstport", "tcp.srcport", "udp.dstport", "udp.srcport",
)
RECORD_KEYS = (
    "tier", "direction", "link_type", "ethertype", "ip_version", "ip_protocol",
    "protocol_group", "ports_present", "presence_mask", "length_bin", "delta_bin",
    "regression", "icmp_type", "icmp_code", "gre_key_present", "frame_len",
    "delta_log2_us", "transport_len", "tcp_flags",
)
OFFSETS = (
    ("tier", 0, 4), ("direction", 4, 7), ("link_type", 7, 10),
    ("ethertype", 10, 27), ("ip_version", 27, 30), ("ip_protocol", 30, 39),
    ("protocol_group", 39, 46), ("ports_present", 46, 47),
    ("presence_mask", 47, 68), ("length_bin", 68, 76), ("delta_bin", 76, 85),
    ("regression", 85, 86), ("icmp_type", 86, 95), ("icmp_code", 95, 104),
    ("gre_key_present", 104, 105), ("frame_len", 105, 108),
    ("delta_log2_us", 108, 110), ("transport_len", 110, 114),
    ("tcp_flags", 114, 131),
)
DECIMAL = re.compile(r"(?:0|[1-9][0-9]*)\Z", re.ASCII)


class F4Failure(RuntimeError):
    pass


class DomainStop(F4Failure):
    pass


class ScientificStop(F4Failure):
    pass


class ResourceStop(F4Failure):
    pass


def sha256_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(block_size), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, str(path))
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def atomic_json(path: Path, value: object) -> None:
    atomic_bytes(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True).encode("utf-8") + b"\n")


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, str(path))
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def atomic_gzip_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as binary:
            with gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as compressed:
                import io
                with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                    writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n")
                    writer.writeheader()
                    for row in rows:
                        writer.writerow(dict(row))
            binary.flush()
            os.fsync(binary.fileno())
        os.replace(name, str(path))
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def read_gzip_jsonl(path: Path) -> List[Dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def parse_uint(text: str, bits: int, field: str) -> int:
    if not DECIMAL.fullmatch(text):
        raise F4Failure("noncanonical %s integer: %r" % (field, text))
    value = int(text)
    if value > (1 << bits) - 1:
        raise DomainStop("%s outside UInt%d: %s" % (field, bits, text))
    return value


def parse_optional(text: str, bits: int, field: str) -> Optional[int]:
    return None if text == "NONE" else parse_uint(text, bits, field)


def parse_bool(text: str, field: str) -> bool:
    if text not in {"false", "true"}:
        raise F4Failure("invalid %s boolean: %r" % (field, text))
    return text == "true"


def parse_l1(signature: str) -> Dict[str, object]:
    if not isinstance(signature, str):
        raise F4Failure("signature must be str")
    values = signature.split("\x1f")
    if len(values) != 19:
        raise F4Failure("signature must have exactly 19 components")
    if values[0] not in TIER or values[1] not in DIRECTION or values[6] not in PROTOCOL_GROUP:
        raise F4Failure("invalid fixed category")
    if values[9] not in LENGTH_BIN or values[10] not in DELTA_BIN:
        raise F4Failure("invalid fixed bin")
    link_text = values[2]
    if not link_text.startswith("encap:"):
        raise F4Failure("invalid link type literal")
    link_raw = link_text[6:]
    link_type = None if link_raw == "unknown" else parse_uint(link_raw, 32, "link_type")
    ethertype = parse_optional(values[3], 16, "ethertype")
    if values[4] not in VERSION:
        if DECIMAL.fullmatch(values[4]):
            raise DomainStop("ip_version outside {4,6}: %s" % values[4])
        raise F4Failure("invalid ip_version")
    ip_version = None if values[4] == "NONE" else int(values[4])
    ip_protocol = parse_optional(values[5], 8, "ip_protocol")
    mask_text = values[8]
    if mask_text == "none":
        mask: frozenset[str] = frozenset()
    else:
        parts = mask_text.split("|")
        if not parts or any(p not in PRESENCE_FIELDS for p in parts):
            raise F4Failure("unknown presence-mask field")
        if parts != sorted(set(parts)):
            raise F4Failure("presence mask is duplicate or noncanonical")
        mask = frozenset(parts)
    tails = ("FRAME_LEN=", "DELTA_LOG2_US=", "TRANSPORT_LEN=", "TCP_FLAGS=")
    raw_tail: List[str] = []
    for value, prefix in zip(values[15:], tails):
        if not value.startswith(prefix):
            raise F4Failure("invalid L1 tail name/order")
        raw_tail.append(value[len(prefix):])
    frame_len = parse_uint(raw_tail[0], 32, "frame_len")
    delta_log: object = "ZERO" if raw_tail[1] == "ZERO" else parse_uint(raw_tail[1], 8, "delta_log2_us")
    transport_len = parse_optional(raw_tail[2], 32, "transport_len")
    tcp_flags = parse_optional(raw_tail[3], 16, "tcp_flags")
    record: Dict[str, object] = {
        "tier": values[0], "direction": values[1], "link_type": link_type,
        "ethertype": ethertype, "ip_version": ip_version, "ip_protocol": ip_protocol,
        "protocol_group": values[6], "ports_present": parse_bool(values[7], "ports_present"),
        "presence_mask": mask, "length_bin": values[9], "delta_bin": values[10],
        "regression": parse_bool(values[11], "regression"),
        "icmp_type": parse_optional(values[12], 8, "icmp_type"),
        "icmp_code": parse_optional(values[13], 8, "icmp_code"),
        "gre_key_present": parse_bool(values[14], "gre_key_present"),
        "frame_len": frame_len, "delta_log2_us": delta_log,
        "transport_len": transport_len, "tcp_flags": tcp_flags,
    }
    if length_bin_for(frame_len) != record["length_bin"]:
        raise F4Failure("length bin does not match exact frame length")
    return record


def length_bin_for(value: int) -> str:
    for maximum, label in ((63, "<=63"), (127, "64-127"), (255, "128-255"),
                           (511, "256-511"), (1023, "512-1023"),
                           (1518, "1024-1518"), (4095, "1519-4095")):
        if value <= maximum:
            return label
    return ">=4096"


def _record_check(record: Mapping[str, object]) -> None:
    if type(record) is not dict or tuple(record.keys()) != RECORD_KEYS:
        raise F4Failure("typed record keys/order mismatch")
    for name in ("ports_present", "regression", "gre_key_present"):
        if type(record[name]) is not bool:
            raise F4Failure("%s must be bool" % name)
    for name in ("link_type", "ethertype", "ip_version", "ip_protocol", "icmp_type", "icmp_code", "transport_len", "tcp_flags"):
        if record[name] is not None and type(record[name]) is not int:
            raise F4Failure("%s must be int or None" % name)
    if type(record["frame_len"]) is not int:
        raise F4Failure("frame_len must be int")
    if record["delta_log2_us"] != "ZERO" and type(record["delta_log2_us"]) is not int:
        raise F4Failure("delta_log2_us must be ZERO or int")
    if type(record["presence_mask"]) is not frozenset:
        raise F4Failure("presence_mask must be frozenset")
    if not record["presence_mask"].issubset(PRESENCE_FIELDS):
        raise F4Failure("presence_mask contains an unknown field")
    if length_bin_for(record["frame_len"]) != record["length_bin"]:
        raise F4Failure("typed frame length/bin mismatch")
    delta = record["delta_log2_us"]
    if delta != "ZERO" and not 0 <= delta <= 255:
        raise DomainStop("delta_log2_us outside UInt8")


def _oh(value: object, order: Sequence[object]) -> np.ndarray:
    if value not in order:
        raise F4Failure("value outside one-hot order")
    result = np.zeros(len(order), dtype=np.float32)
    result[order.index(value)] = np.float32(1.0)
    return result


def _bits(value: int, width: int) -> np.ndarray:
    if type(value) is not int or not 0 <= value < (1 << width):
        raise DomainStop("integer outside %d bits" % width)
    return np.asarray([(value >> k) & 1 for k in range(width)], dtype=np.float32)


def _optional_bits(value: Optional[int], width: int) -> np.ndarray:
    return np.zeros(width + 1, dtype=np.float32) if value is None else np.concatenate((np.ones(1, dtype=np.float32), _bits(value, width)))


def _u32(value: int) -> np.ndarray:
    if type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
        raise DomainStop("integer outside UInt32")
    hi, lo = value // 65536, value % 65536
    return np.asarray([hi / 65536.0, lo / 65536.0, math.log2(1 + value) / 32.0], dtype=np.float32)


def _optional_u32(value: Optional[int]) -> np.ndarray:
    return np.zeros(4, dtype=np.float32) if value is None else np.concatenate((np.ones(1, dtype=np.float32), _u32(value)))


def encode_event(record: Mapping[str, object]) -> np.ndarray:
    _record_check(record)
    link = np.zeros(3, dtype=np.float32) if record["link_type"] is None else np.concatenate((np.ones(1, dtype=np.float32), _u32(int(record["link_type"]))[:2]))
    version_text = "NONE" if record["ip_version"] is None else str(record["ip_version"])
    if version_text not in VERSION:
        raise DomainStop("ip_version outside {4,6}")
    delta = record["delta_log2_us"]
    delta_vector = np.asarray([1.0, 0.0], dtype=np.float32) if delta == "ZERO" else np.asarray([0.0, int(delta) / 256.0], dtype=np.float32)
    mask = np.asarray([1.0 if name in record["presence_mask"] else 0.0 for name in PRESENCE_FIELDS], dtype=np.float32)
    pieces = (
        _oh(record["tier"], TIER), _oh(record["direction"], DIRECTION), link,
        _optional_bits(record["ethertype"], 16), _oh(version_text, VERSION),
        _optional_bits(record["ip_protocol"], 8), _oh(record["protocol_group"], PROTOCOL_GROUP),
        np.asarray([record["ports_present"]], dtype=np.float32), mask,
        _oh(record["length_bin"], LENGTH_BIN), _oh(record["delta_bin"], DELTA_BIN),
        np.asarray([record["regression"]], dtype=np.float32),
        _optional_bits(record["icmp_type"], 8), _optional_bits(record["icmp_code"], 8),
        np.asarray([record["gre_key_present"]], dtype=np.float32), _u32(int(record["frame_len"])),
        delta_vector, _optional_u32(record["transport_len"]), _optional_bits(record["tcp_flags"], 16),
    )
    result = np.ascontiguousarray(np.concatenate(pieces), dtype=np.float32)
    if result.shape != (WIDTH,) or not np.isfinite(result).all():
        raise F4Failure("invalid encoded event")
    if not result.any():
        raise F4Failure("observed event cannot equal PAD")
    return result


def _decode_one_hot(vector: np.ndarray, order: Sequence[object], field: str) -> object:
    if vector.shape != (len(order),) or not np.all((vector == 0.0) | (vector == 1.0)) or int(np.sum(vector)) != 1:
        raise F4Failure("invalid one-hot for %s" % field)
    return order[int(np.argmax(vector))]


def _decode_bool(value: np.float32, field: str) -> bool:
    if value not in (np.float32(0.0), np.float32(1.0)):
        raise F4Failure("invalid boolean coordinate for %s" % field)
    return bool(value)


def _decode_bits(vector: np.ndarray, width: int, field: str) -> int:
    if vector.shape != (width,) or not np.all((vector == 0.0) | (vector == 1.0)):
        raise F4Failure("invalid bits for %s" % field)
    return sum(int(vector[k]) << k for k in range(width))


def _decode_optional_bits(vector: np.ndarray, width: int, field: str) -> Optional[int]:
    present = _decode_bool(vector[0], field + "_present")
    if not present:
        if np.any(vector[1:] != 0.0):
            raise F4Failure("absent %s has nonzero bits" % field)
        return None
    return _decode_bits(vector[1:], width, field)


def _decode_limb(value: np.float32, field: str) -> int:
    if not np.isfinite(value):
        raise F4Failure("nonfinite limb")
    scaled = float(value) * 65536.0
    integer = int(round(scaled))
    if not 0 <= integer <= 65535 or np.float32(integer / 65536.0) != value:
        raise F4Failure("lossy limb for %s" % field)
    return integer


def _decode_u32(vector: np.ndarray, field: str) -> int:
    hi, lo = _decode_limb(vector[0], field + "_hi"), _decode_limb(vector[1], field + "_lo")
    value = hi * 65536 + lo
    if vector.shape != (3,) or vector[2] != np.float32(math.log2(1 + value) / 32.0):
        raise F4Failure("invalid log coordinate for %s" % field)
    return value


def _decode_optional_u32(vector: np.ndarray, field: str) -> Optional[int]:
    present = _decode_bool(vector[0], field + "_present")
    if not present:
        if np.any(vector[1:] != 0.0):
            raise F4Failure("absent %s has nonzero coordinates" % field)
        return None
    return _decode_u32(vector[1:], field)


def decode_event(vector: np.ndarray) -> str:
    value = np.asarray(vector)
    if value.dtype != np.float32 or value.shape != (WIDTH,) or not np.isfinite(value).all():
        raise F4Failure("feature must be finite float32[131]")
    tier = _decode_one_hot(value[0:4], TIER, "tier")
    direction = _decode_one_hot(value[4:7], DIRECTION, "direction")
    link_known = _decode_bool(value[7], "link_known")
    if link_known:
        link_type = _decode_limb(value[8], "link_hi") * 65536 + _decode_limb(value[9], "link_lo")
        link = "encap:%d" % link_type
    else:
        if np.any(value[8:10] != 0.0):
            raise F4Failure("unknown link has nonzero limbs")
        link = "encap:unknown"
    ethertype = _decode_optional_bits(value[10:27], 16, "ethertype")
    version = _decode_one_hot(value[27:30], VERSION, "ip_version")
    ip_protocol = _decode_optional_bits(value[30:39], 8, "ip_protocol")
    protocol_group = _decode_one_hot(value[39:46], PROTOCOL_GROUP, "protocol_group")
    ports = _decode_bool(value[46], "ports_present")
    mask_bits = [_decode_bool(v, "presence_mask") for v in value[47:68]]
    mask = "|".join(name for name, bit in zip(PRESENCE_FIELDS, mask_bits) if bit) or "none"
    length_bin = _decode_one_hot(value[68:76], LENGTH_BIN, "length_bin")
    delta_bin = _decode_one_hot(value[76:85], DELTA_BIN, "delta_bin")
    regression = _decode_bool(value[85], "regression")
    icmp_type = _decode_optional_bits(value[86:95], 8, "icmp_type")
    icmp_code = _decode_optional_bits(value[95:104], 8, "icmp_code")
    gre_key = _decode_bool(value[104], "gre_key_present")
    frame_len = _decode_u32(value[105:108], "frame_len")
    delta_zero = _decode_bool(value[108], "delta_zero")
    if delta_zero:
        if value[109] != 0.0:
            raise F4Failure("ZERO delta has nonzero exponent")
        delta_log = "ZERO"
    else:
        scaled = float(value[109]) * 256.0
        exponent = int(round(scaled))
        if not 0 <= exponent <= 255 or np.float32(exponent / 256.0) != value[109]:
            raise F4Failure("invalid delta exponent")
        delta_log = str(exponent)
    transport_len = _decode_optional_u32(value[110:114], "transport_len")
    tcp_flags = _decode_optional_bits(value[114:131], 16, "tcp_flags")
    components = [
        str(tier), str(direction), link, "NONE" if ethertype is None else str(ethertype), str(version),
        "NONE" if ip_protocol is None else str(ip_protocol), str(protocol_group), str(ports).lower(), mask,
        str(length_bin), str(delta_bin), str(regression).lower(),
        "NONE" if icmp_type is None else str(icmp_type), "NONE" if icmp_code is None else str(icmp_code),
        str(gre_key).lower(), "FRAME_LEN=%d" % frame_len, "DELTA_LOG2_US=%s" % delta_log,
        "TRANSPORT_LEN=%s" % ("NONE" if transport_len is None else transport_len),
        "TCP_FLAGS=%s" % ("NONE" if tcp_flags is None else tcp_flags),
    ]
    signature = "\x1f".join(components)
    if not np.array_equal(encode_event(parse_l1(signature)), value):
        raise F4Failure("inverse re-encoding mismatch")
    return signature


def encode_context(signatures: Sequence[str]) -> np.ndarray:
    if not 1 <= len(signatures) <= 256:
        raise F4Failure("context length outside 1..256")
    return np.ascontiguousarray(np.stack([encode_event(parse_l1(item)) for item in signatures]), dtype=np.float32)


def prefix_bytes(matrix: np.ndarray, target_event_index: int) -> bytes:
    value = np.asarray(matrix)
    if value.dtype != np.float32 or value.ndim != 2 or value.shape[1] != WIDTH:
        raise F4Failure("invalid context matrix")
    if type(target_event_index) is not int or not 0 <= target_event_index < value.shape[0]:
        raise F4Failure("target event index outside context")
    prefix = np.ascontiguousarray(value[:target_event_index + 1], dtype="<f4")
    return b"F4_INPUT_V1\0" + struct.pack("<II", prefix.shape[0], WIDTH) + prefix.tobytes(order="C")


def schema() -> Dict[str, object]:
    return {
        "version": "F4_INPUT_V1", "width": WIDTH, "dtype": "little-endian-float32",
        "record_keys": list(RECORD_KEYS), "offsets": [{"field": n, "start": a, "end": b} for n, a, b in OFFSETS],
        "orders": {"tier": list(TIER), "direction": list(DIRECTION), "ip_version": list(VERSION),
                   "protocol_group": list(PROTOCOL_GROUP), "length_bin": list(LENGTH_BIN), "delta_bin": list(DELTA_BIN),
                   "presence_fields": list(PRESENCE_FIELDS)},
        "integer_bounds": {"uint8": [0, 255], "uint16": [0, 65535], "uint32": [0, 4294967295]},
        "u32": ["hi/65536", "lo/65536", "log2(1+x)/32"],
        "optional": "leading presence bit; NONE is all zero", "bits": "least-significant-bit first",
        "padding": "all-zero event with separate valid mask; never serialized as observed input",
    }


def peak_working_set_bytes() -> int:
    if os.name != "nt":
        try:
            import resource
            scale = 1 if sys.platform == "darwin" else 1024
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * scale)
        except Exception as exc:
            raise F4Failure("peak working-set measurement unavailable: %s" % exc)
    class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
        _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
    counters = PROCESS_MEMORY_COUNTERS()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), ctypes.c_ulong]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise F4Failure("GetProcessMemoryInfo failed")
    return int(counters.PeakWorkingSetSize)


def directory_bytes(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def resource_check(start: float, attempt: Path) -> Dict[str, object]:
    wall = time.monotonic() - start
    peak = peak_working_set_bytes()
    size = directory_bytes(attempt)
    if wall > MAX_WALL_SECONDS or peak > MAX_PEAK_BYTES or size > MAX_OUTPUT_BYTES:
        raise ResourceStop("resource cap exceeded")
    return {"wall_seconds": wall, "peak_working_set_bytes": peak, "output_bytes": size}


def resource_values_ok(wall: float, peak: int, size: int, free: int) -> bool:
    return wall <= MAX_WALL_SECONDS and peak <= MAX_PEAK_BYTES and size <= MAX_OUTPUT_BYTES and free >= MIN_FREE_BYTES


def mixed_label_bucket_count(rows: Iterable[Tuple[bytes, int]]) -> int:
    groups: MutableMapping[bytes, Set[int]] = defaultdict(set)
    for key, label in rows:
        groups[key].add(int(label))
    return sum(labels == {0, 1} for labels in groups.values())


def collision_pairs(rows: Iterable[Tuple[str, bytes]]) -> List[Tuple[str, str]]:
    seen: Dict[bytes, str] = {}
    result: List[Tuple[str, str]] = []
    for canonical, feature in rows:
        if feature in seen and seen[feature] != canonical:
            result.append((seen[feature], canonical))
        else:
            seen[feature] = canonical
    return result


def terminal_state(error: BaseException) -> str:
    if isinstance(error, DomainStop):
        return "F4_FIELD_DOMAIN_UNSUPPORTED"
    if isinstance(error, ScientificStop):
        return "F4_FIELDWISE_INPUT_NO_GO"
    if isinstance(error, ResourceStop):
        return "F4_RESOURCE_NO_GO"
    return "F4_ENGINEERING_FAILURE"


def load_test_module() -> Any:
    path = ROOT / TEST_REL
    spec = importlib.util.spec_from_file_location("f4_contract_tests", path)
    if spec is None or spec.loader is None:
        raise F4Failure("cannot load contract tests")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_manifest() -> None:
    manifest = ROOT / F3_REL / "SHA256SUMS"
    for line in manifest.read_text(encoding="utf-8").splitlines():
        digest, name = line.split(None, 1)
        if sha256_file(ROOT / F3_REL / name.strip()) != digest:
            raise F4Failure("F3 package manifest mismatch: %s" % name)


def preflight(output: Path, token: str) -> Dict[str, object]:
    if token != EXECUTION_TOKEN:
        raise F4Failure("authorization token mismatch")
    runs_root = (ROOT / "runs").resolve()
    resolved = output.resolve()
    if runs_root not in resolved.parents:
        raise F4Failure("output must be a child of worktree runs")
    if output.exists():
        raise F4Failure("output already exists")
    if sha256_file(ROOT / PROTOCOL_REL) != PROTOCOL_SHA256:
        raise F4Failure("frozen protocol identity mismatch")
    for name, digest in INPUT_PINS.items():
        if sha256_file(ROOT / F3_REL / name) != digest:
            raise F4Failure("input identity mismatch: %s" % name)
    for name, digest in SOURCE_PINS.items():
        if sha256_file(ROOT / name) != digest:
            raise F4Failure("source provenance mismatch: %s" % name)
    verify_manifest()
    free = shutil.disk_usage(output.parent).free
    if free < MIN_FREE_BYTES:
        raise ResourceStop("insufficient destination free space")
    return {"free_bytes_before": free, "protocol_sha256": PROTOCOL_SHA256,
            "implementation_sha256": sha256_file(Path(__file__)), "tests_sha256": sha256_file(ROOT / TEST_REL),
            "python": sys.version, "numpy": np.__version__, "platform": platform.platform(),
            "input_pins": INPUT_PINS, "source_pins": SOURCE_PINS}


def category_for(target: Mapping[str, object]) -> str:
    owner, label, teacher = str(target["owner"]), int(target["label"]), str(target["teacher_kind"])
    key = (owner, label, teacher)
    categories = {("A", 1, "attack_hard"): "a_protected_attack",
                  ("A", 0, "benign_normal"): "a_protected_benign",
                  ("A", 0, "benign_hard"): "a_unprotected_benign",
                  ("B", 1, "none"): "b_attack", ("B", 0, "none"): "b_benign"}
    if key not in categories:
        raise F4Failure("unknown owner/label/teacher category: %r" % (key,))
    return categories[key]


def execute(output: Path, token: str) -> None:
    start = time.monotonic()
    identities = preflight(output, token)
    attempt = output.with_name(".%s.attempt-%d" % (output.name, os.getpid()))
    if attempt.exists():
        raise F4Failure("attempt directory already exists")
    attempt.mkdir(parents=True)
    try:
        schema_value = schema()
        atomic_json(attempt / "f4_schema.json", schema_value)
        identities.update({"schema_sha256": sha256_file(attempt / "f4_schema.json"),
                           "authorization_token": token, "training_authorized": False,
                           "initial_role_access": {"real_feature_vectors": 0, "models": 0, "scores": 0,
                                                   "pcap": 0, "network": 0, "optimizer_steps": 0}})
        atomic_json(attempt / "f4_inputs_and_runtime.json", identities)
        tests = load_test_module().run_all(sys.modules[__name__])
        if len(tests) != 28 or not all(row["passed"] for row in tests):
            raise F4Failure("synthetic contract battery failed")
        atomic_json(attempt / "f4_synthetic_contract_tests.json", {"passed": 28, "total": 28, "tests": tests})
        resource_check(start, attempt)

        contexts = read_gzip_jsonl(ROOT / F3_REL / "f3b_l1_contexts.jsonl.gz")
        with gzip.open(ROOT / F3_REL / "f3b_target_prefix_audit.csv.gz", "rt", encoding="utf-8", newline="") as stream:
            inherited_targets = {row["uid"]: row for row in csv.DictReader(stream)}
        if len(contexts) != EXPECTED_CONTEXTS or len(inherited_targets) != EXPECTED_TARGETS:
            raise F4Failure("parent denominator drift")
        identities_f3 = json.loads((ROOT / F3_REL / "f3b_identities.json").read_text(encoding="utf-8"))
        split_sources = {source: side for side, sources in (("train", identities_f3["nested_split"]["train_sources"]),
                                                            ("internal_val", identities_f3["nested_split"]["internal_validation_sources"])) for source in sources}
        seen_uids: Set[str] = set()
        seen_contexts: Set[str] = set()
        target_rows: List[Dict[str, object]] = []
        coverage_groups: MutableMapping[Tuple[str, str, str], Dict[str, object]] = {}
        coverage_contexts: MutableMapping[Tuple[str, str, str], Set[str]] = defaultdict(set)
        census_targets: MutableMapping[Tuple[str, str], int] = defaultdict(int)
        census_contexts: MutableMapping[Tuple[str, str], Set[str]] = defaultdict(set)
        feature_prefix_refs: MutableMapping[str, List[Tuple[bytes, str, Set[int], str]]] = defaultdict(list)
        train_benign_feature_bytes: MutableMapping[str, List[bytes]] = defaultdict(list)
        canonical_refs: MutableMapping[str, List[Tuple[bytes, Set[int]]]] = defaultdict(list)
        event_refs: MutableMapping[str, Tuple[bytes, str]] = {}
        collision_rows: List[Dict[str, object]] = []
        context_index: List[Dict[str, object]] = []
        event_offset = 0
        unique_signatures: Set[str] = set()
        unique_features: Set[str] = set()
        parent_binary = attempt / "f4_parent_features.f32le"
        with parent_binary.open("wb") as binary:
            for context_number, context in enumerate(sorted(contexts, key=lambda row: str(row["context_key"]))):
                context_key, source = str(context["context_key"]), str(context["source_group"])
                split = str(context["nested_split"])
                signatures = [str(item) for item in context["signatures"]]
                targets = list(context["targets"])
                if context_key in seen_contexts or split_sources.get(source) != split or split not in {"train", "internal_val"}:
                    raise F4Failure("context/source/split identity drift")
                seen_contexts.add(context_key)
                matrix = encode_context(signatures)
                for signature, vector in zip(signatures, matrix):
                    if decode_event(vector) != signature:
                        raise F4Failure("real event round-trip mismatch")
                    feature = np.ascontiguousarray(vector, dtype="<f4").tobytes()
                    digest = hashlib.sha256(feature).hexdigest()
                    prior = event_refs.get(digest)
                    if prior is not None and prior[0] == feature and prior[1] != signature:
                        collision_rows.append({"scope": "parent", "collision_kind": "event",
                                               "canonical_prefix_sha256": hashlib.sha256(signature.encode("utf-8")).hexdigest(),
                                               "feature_prefix_sha256": digest, "uid": "", "label": ""})
                    else:
                        event_refs[digest] = (feature, signature)
                    unique_signatures.add(signature); unique_features.add(digest)
                np.ascontiguousarray(matrix, dtype="<f4").tofile(binary)
                context_index.append({"context_key": context_key, "source_group": source, "nested_split": split,
                                      "event_offset": event_offset, "event_count": len(signatures)})
                event_offset += len(signatures)
                seen_pairs: Set[Tuple[int, str]] = set()
                for target in targets:
                    uid, index = str(target["uid"]), int(target["event_index"])
                    if uid in seen_uids or (index, uid) in seen_pairs or uid not in inherited_targets:
                        raise F4Failure("target identity duplication/drift")
                    seen_uids.add(uid); seen_pairs.add((index, uid))
                    old = inherited_targets[uid]
                    for name in ("context_key", "nested_split", "source_group", "owner", "label", "teacher_kind", "device_family", "attack_family"):
                        expected = context_key if name == "context_key" else split if name == "nested_split" else source if name == "source_group" else target[name]
                        if str(old[name]) != str(expected):
                            raise F4Failure("target metadata mismatch: %s" % name)
                    if int(old["event_index"]) != index:
                        raise F4Failure("target event-index mismatch")
                    l1_digest = hashlib.sha256(canonical_json_bytes(signatures[:index + 1])).hexdigest()
                    if l1_digest != old["l1_prefix_sha"]:
                        raise F4Failure("saved L1 prefix mismatch")
                    raw_feature = prefix_bytes(matrix, index)
                    feature_digest = hashlib.sha256(raw_feature).hexdigest()
                    label = int(target["label"])
                    canonical_raw = canonical_json_bytes(signatures[:index + 1])
                    canonical_match = next((item for item in canonical_refs[l1_digest] if item[0] == canonical_raw), None)
                    if canonical_match is None:
                        canonical_refs[l1_digest].append((canonical_raw, {label}))
                    else:
                        canonical_match[1].add(label)
                    prior = feature_prefix_refs[feature_digest]
                    feature_match = next((item for item in prior if item[0] == raw_feature), None)
                    if feature_match is not None:
                        if feature_match[1] != l1_digest:
                            collision_rows.append({"scope": "parent", "collision_kind": "prefix",
                                                   "canonical_prefix_sha256": l1_digest, "feature_prefix_sha256": feature_digest,
                                                   "uid": uid, "label": label})
                        feature_match[2].add(label)
                    else:
                        feature_prefix_refs[feature_digest].append((raw_feature, l1_digest, {label}, uid))
                    if split == "train" and label == 0 and raw_feature not in train_benign_feature_bytes[feature_digest]:
                        train_benign_feature_bytes[feature_digest].append(raw_feature)
                    category = category_for(target)
                    census_targets[(split, category)] += 1; census_contexts[(split, category)].add(context_key)
                    tier = signatures[index].split("\x1f", 1)[0]
                    group_values = {"source": source, "owner": str(target["owner"]), "label": str(label),
                                    "device_family": str(target["device_family"]), "attack_family": str(target["attack_family"]),
                                    "context_tier": tier}
                    old_all_unk = int(old["known_events"]) == 0
                    for kind, group in group_values.items():
                        key = (kind, group, split)
                        row = coverage_groups.setdefault(key, {"group_kind": kind, "group_value": group, "nested_split": split,
                                                               "targets": 0, "encoded_targets": 0, "roundtrip_targets": 0,
                                                               "old_all_unk_targets": 0})
                        row["targets"] = int(row["targets"]) + 1
                        row["encoded_targets"] = int(row["encoded_targets"]) + 1
                        row["roundtrip_targets"] = int(row["roundtrip_targets"]) + 1
                        row["old_all_unk_targets"] = int(row["old_all_unk_targets"]) + int(old_all_unk)
                        coverage_contexts[key].add(context_key)
                    target_rows.append({"uid": uid, "context_key": context_key, "event_index": index,
                                        "source_group": source, "nested_split": split, "owner": target["owner"],
                                        "label": label, "teacher_kind": target["teacher_kind"],
                                        "device_family": target["device_family"], "attack_family": target["attack_family"],
                                        "l1_prefix_sha256": l1_digest, "feature_prefix_sha256": feature_digest,
                                        "prefix_events": index + 1, "old_all_unk": str(old_all_unk).lower(),
                                        "roundtrip_exact": "true", "finite": "true", "feature_width": WIDTH})
                if context_number % 100 == 0:
                    resource_check(start, attempt)
        if seen_uids != set(inherited_targets) or len(seen_contexts) != EXPECTED_CONTEXTS:
            raise F4Failure("parent membership conservation failure")
        mixed_canonical = sum(labels == {0, 1} for groups in canonical_refs.values() for _, labels in groups)
        feature_mixed = sum(labels == {0, 1} for groups in feature_prefix_refs.values() for _, _, labels, _ in groups)
        if collision_rows or mixed_canonical or feature_mixed:
            raise ScientificStop("fieldwise mapping collision/mixed-label gate failed")

        atomic_csv(attempt / "f4_context_index.csv", ["context_key", "source_group", "nested_split", "event_offset", "event_count"], context_index)
        target_fields = ["uid", "context_key", "event_index", "source_group", "nested_split", "owner", "label", "teacher_kind",
                         "device_family", "attack_family", "l1_prefix_sha256", "feature_prefix_sha256", "prefix_events", "old_all_unk",
                         "roundtrip_exact", "finite", "feature_width"]
        atomic_gzip_csv(attempt / "f4_target_audit.csv.gz", target_fields, sorted(target_rows, key=lambda row: str(row["uid"])))
        coverage_rows = []
        for key, row in sorted(coverage_groups.items()):
            coverage_rows.append({**row, "contexts": len(coverage_contexts[key])})
        atomic_csv(attempt / "f4_coverage.csv", ["group_kind", "group_value", "nested_split", "targets", "contexts", "encoded_targets", "roundtrip_targets", "old_all_unk_targets"], coverage_rows)
        atomic_csv(attempt / "f4_collision_audit.csv", ["scope", "collision_kind", "canonical_prefix_sha256", "feature_prefix_sha256", "uid", "label"], collision_rows)
        census_rows = [{"nested_split": split, "category": category, "targets": census_targets[(split, category)],
                        "contexts": len(census_contexts[(split, category)])}
                       for split in ("internal_val", "train")
                       for category in ("a_protected_attack", "a_protected_benign", "a_unprotected_benign", "b_attack", "b_benign")]
        original_census = {(r["nested_split"], r["category"]): int(r["contexts"])
                           for r in csv.DictReader((ROOT / F3_REL / "f3b_nested_split_census.csv").open(encoding="utf-8", newline=""))}
        for row in census_rows:
            key = (str(row["nested_split"]), str(row["category"]))
            if key in original_census and int(row["contexts"]) != original_census[key]:
                raise F4Failure("nested census mismatch")
        atomic_csv(attempt / "f4_nested_split_census.csv", ["nested_split", "category", "targets", "contexts"], census_rows)

        with (ROOT / F3_REL / "f3b_kill_only_audit.csv").open(encoding="utf-8", newline="") as stream:
            kill_old = {row["uid"]: row for row in csv.DictReader(stream)}
        kill_contexts = read_gzip_jsonl(ROOT / F3_REL / "checkpoints/6c1c4e7926631066034dae98.jsonl.gz")
        if len(kill_contexts) != EXPECTED_KILL or len(kill_old) != EXPECTED_KILL:
            raise F4Failure("kill-only denominator drift")
        kill_rows: List[Dict[str, object]] = []; kill_index: List[Dict[str, object]] = []; kill_offset = 0
        seen_kill_contexts: Set[str] = set()
        with (attempt / "f4_kill_only_features.f32le").open("wb") as binary:
            for row in sorted(kill_contexts, key=lambda value: str(value["uid"])):
                uid = str(row["uid"]); signatures = [str(item) for item in row["l1_signatures"]]
                context_key = str(row["context_key"])
                if row.get("scope") != "kill_only" or uid not in kill_old or context_key in seen_kill_contexts:
                    raise F4Failure("kill-only identity/scope mismatch")
                seen_kill_contexts.add(context_key)
                if str(row["source_group"]) != kill_old[uid]["source_group"] or int(kill_old[uid]["prefix_events"]) != int(row["event_index"]) + 1:
                    raise F4Failure("kill-only source/event-count mismatch")
                index = int(row["event_index"])
                if len(signatures) != index + 1:
                    raise F4Failure("kill-only checkpoint is not an exact target prefix")
                matrix = encode_context(signatures)
                if any(decode_event(v) != s for v, s in zip(matrix, signatures)):
                    raise F4Failure("kill-only round-trip mismatch")
                matrix.astype("<f4", copy=False).tofile(binary)
                raw_feature = prefix_bytes(matrix, index)
                feature_digest = hashlib.sha256(raw_feature).hexdigest()
                collision = any(value == raw_feature for value in train_benign_feature_bytes.get(feature_digest, []))
                kill_rows.append({"uid": uid, "context_key": row["context_key"], "prefix_events": index + 1,
                                  "old_known_events": kill_old[uid]["known_events"], "old_unk_events": kill_old[uid]["unk_events"],
                                  "roundtrip_exact": "true", "finite": "true", "feature_prefix_sha256": feature_digest,
                                  "collides_with_nested_train_benign": str(collision).lower()})
                kill_index.append({"uid": uid, "context_key": row["context_key"], "event_offset": kill_offset, "event_count": len(signatures)})
                kill_offset += len(signatures)
        atomic_csv(attempt / "f4_kill_only_index.csv", ["uid", "context_key", "event_offset", "event_count"], kill_index)
        atomic_csv(attempt / "f4_kill_only_audit.csv", ["uid", "context_key", "prefix_events", "old_known_events", "old_unk_events", "roundtrip_exact", "finite", "feature_prefix_sha256", "collides_with_nested_train_benign"], kill_rows)
        if any(row["collides_with_nested_train_benign"] == "true" for row in kill_rows):
            raise ScientificStop("kill-only feature prefix collides with train benign")

        train_targets = sum(r["nested_split"] == "train" for r in target_rows)
        val_targets = len(target_rows) - train_targets
        train_contexts = sum(r["nested_split"] == "train" for r in context_index)
        val_contexts = len(context_index) - train_contexts
        if (train_targets, val_targets, train_contexts, val_contexts) != (EXPECTED_TRAIN_TARGETS, EXPECTED_VAL_TARGETS, EXPECTED_TRAIN_CONTEXTS, EXPECTED_VAL_CONTEXTS):
            raise F4Failure("nested denominator conservation failure")
        resource = resource_check(start, attempt)
        role_audit = {"parent_context_container_opened": 1, "parent_target_audit_opened": 1,
                      "kill_only_container_opened_after_parent": 1, "label_metadata_rows_parsed_for_audit": len(target_rows),
                      "feature_uses_of_label_uid_source_owner_role_teacher": 0, "pcap_opened": 0, "network_calls": 0,
                      "model_opened": 0, "score_opened": 0, "learned_representation_opened": 0,
                      "optimizer_steps": 0, "npz_opened": 0, "vocabulary_queries": 0, "learned_constants": 0}
        atomic_json(attempt / "f4_role_open_audit.json", role_audit)
        identities.update({"schema_sha256": sha256_file(attempt / "f4_schema.json"), "resource": resource,
                           "parent_contexts": len(context_index), "parent_targets": len(target_rows),
                           "parent_events": event_offset, "kill_only_targets": len(kill_rows), "kill_only_events": kill_offset})
        atomic_json(attempt / "f4_inputs_and_runtime.json", identities)
        gates = {"G1_identity_and_conservation": True, "G2_roundtrip_finite_width": True,
                 "G3_collision_and_mixed_label_zero": True, "G4_causal_prefix": True,
                 "G5_fixed_no_forbidden_io": True, "G6_kill_only_noncollision": True,
                 "G7_synthetic_tests": True, "G8_resources_and_serialization": True}
        verdict = {"status": "F4_FIELDWISE_INPUT_PASS", "gates": gates, "parent_targets": len(target_rows),
                   "parent_contexts": len(context_index), "parent_events": event_offset,
                   "train_targets": train_targets, "internal_val_targets": val_targets,
                   "train_contexts": train_contexts, "internal_val_contexts": val_contexts,
                   "roundtrip_targets": len(target_rows), "old_all_unk_targets_losslessly_encoded": sum(r["old_all_unk"] == "true" for r in target_rows),
                   "unique_canonical_events": len(unique_signatures), "unique_feature_events": len(unique_features),
                   "canonical_mixed_label_buckets": mixed_canonical, "feature_mixed_label_buckets": feature_mixed,
                   "feature_collisions": len(collision_rows), "kill_only": kill_rows, "resource": resource,
                   "claim_ceiling": "LOSSLESS_FIELD_INPUT_ON_EXPOSED_DEVELOPMENT_UNIVERSE",
                   "training_authorized": False, "positive_attack_generalization_evidence": False,
                   "next_permitted_action": "DRAFT_ONE_SHOT_TRAINING_PROTOCOL_ONLY"}
        atomic_json(attempt / "f4_verdict.json", verdict)
        resource = resource_check(start, attempt)
        identities["resource"] = resource
        verdict["resource"] = resource
        atomic_json(attempt / "f4_inputs_and_runtime.json", identities)
        atomic_json(attempt / "f4_verdict.json", verdict)
        members = sorted(item for item in attempt.iterdir() if item.is_file() and item.name != "SHA256SUMS")
        atomic_bytes(attempt / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(item), item.name) for item in members).encode("ascii"))
        resource_check(start, attempt)
        os.replace(str(attempt), str(output))
        print("F4_FIELDWISE_INPUT_PASS targets=%d contexts=%d" % (len(target_rows), len(context_index)), flush=True)
    except (DomainStop, ScientificStop, ResourceStop) as exc:
        if attempt.exists():
            status = terminal_state(exc)
            atomic_json(attempt / "f4_verdict.json", {"status": status, "error": str(exc),
                                                       "training_authorized": False,
                                                       "positive_attack_generalization_evidence": False})
            members = sorted(item for item in attempt.iterdir() if item.is_file() and item.name != "SHA256SUMS")
            atomic_bytes(attempt / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(item), item.name) for item in members).encode("ascii"))
            os.replace(str(attempt), str(output))
            print(status, flush=True)
            return
        raise
    except BaseException:
        if attempt.exists():
            failure = output.with_name(output.name + "_engineering_failure_%d" % int(time.time()))
            if not failure.exists():
                atomic_json(attempt / "engineering_failure.json", {"status": "F4_ENGINEERING_FAILURE", "error": repr(sys.exc_info()[1]),
                                                                    "training_authorized": False})
                os.replace(str(attempt), str(failure))
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--authorization-token", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    if not output.is_absolute():
        output = ROOT / output
    execute(output, args.authorization_token)


if __name__ == "__main__":
    main()
