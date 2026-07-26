"""CKBU: unified, causal TShark event frontend for Gotham and ToN-IoT.

This module does not define a detector and does not change the frozen Gotham
1M split.  It provides one packet decoder and one past-only feature state for
both datasets.  Dataset adapters may select different rows, but they may not
change the event schema or the feature computation.

The important temporal contract is:

    decode current packet -> emit current+past feature row -> update state

Every PCAP/PCAPNG capture starts with a fresh ``CausalFeatureBuilder``.  Raw
labels are never requested from TShark and are never accepted by the builder.
Gotham processed CSV files are read only for immutable target alignment; the
``label`` column is deliberately absent from ``GOTHAM_ALIGNMENT_FIELDS``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence, TextIO

import numpy as np
import pandas as pd


OOD = Path(__file__).resolve().parent
ROOT = OOD.parent.parent
PROJECT = ROOT.parents[1]

ISSUE = "issue27ckbu_unified_tshark_causal_frontend_v1_2026-07-23"
OUT = ROOT / "runs" / ISSUE
GOTHAM_ZIP = PROJECT / "datasets" / "gotham2025" / "raw" / "GothamDataset2025.zip"
DEFAULT_TARGETS = (
    ROOT
    / "runs"
    / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1"
    / "canonical_source_target_index.csv"
)

TSHARK_FIELDS = [
    "frame.number",
    "frame.time_epoch",
    "frame.len",
    "ip.src",
    "ip.dst",
    "ipv6.src",
    "ipv6.dst",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
    "tcp.flags.syn",
    "tcp.flags.ack",
    "tcp.flags.reset",
    "tcp.flags.fin",
    "tcp.stream",
    "udp.stream",
    "tcp.stream.pnum",
    "tcp.time_relative",
    "tcp.time_delta",
    "tcp.connection.syn",
    "tcp.analysis.retransmission",
    "tcp.analysis.lost_segment",
]

# No label/type/attack field is permitted here.  These columns are used only to
# locate already-frozen Gotham target rows in independently decoded PCAPs.
GOTHAM_ALIGNMENT_FIELDS = [
    "frame.time",
    "frame.len",
    "ip.src",
    "ip.dst",
    "ip.proto",
    "tcp.srcport",
    "tcp.dstport",
    "udp.srcport",
    "udp.dstport",
]

WINDOWS_SECONDS = (1.0, 10.0, 60.0)

FEATURE_NAMES = [
    # Current packet fields, available at packet arrival.
    "cur_log_frame_len",
    "cur_is_ipv4",
    "cur_is_ipv6",
    "cur_is_tcp",
    "cur_is_udp",
    "cur_is_icmp",
    "cur_src_port_class",
    "cur_dst_port_class",
    "cur_dst_well_known",
    "cur_tcp_syn",
    "cur_tcp_ack",
    "cur_tcp_rst",
    "cur_tcp_fin",
    "cur_tshark_retransmission",
    "cur_tshark_lost_segment",
    "cur_log_tcp_stream_pnum",
    "cur_log_tcp_time_relative_ms",
    "cur_log_tcp_time_delta_ms",
    # Source/capture history strictly before the current packet.
    "hist_log_source_events",
    "hist_log_source_iat_ms",
    "hist_source_rate_1s",
    "hist_source_rate_10s",
    "hist_source_rate_60s",
    # Source endpoint history strictly before the current packet.
    "hist_log_src_events",
    "hist_log_src_iat_ms",
    "hist_src_unique_peer_1s",
    "hist_src_unique_peer_10s",
    "hist_src_unique_peer_60s",
    "hist_src_unique_dport_1s",
    "hist_src_unique_dport_10s",
    "hist_src_unique_dport_60s",
    "hist_src_syn_rate_60s",
    "hist_src_rst_rate_60s",
    # Directed and reverse-pair history strictly before the current packet.
    "hist_log_pair_forward_events",
    "hist_log_pair_reverse_events",
    "hist_log_pair_forward_iat_ms",
    "hist_log_reverse_response_ms",
    "hist_pair_bidirectional_seen",
    "hist_log_pair_forward_bytes",
    "hist_log_pair_reverse_bytes",
    # Connection-prefix state strictly before the current packet.
    "hist_log_flow_packets",
    "hist_log_flow_elapsed_ms",
    "hist_log_flow_forward_packets",
    "hist_log_flow_reverse_packets",
    "hist_flow_bidirectional_seen",
    "hist_flow_syn_seen",
    "hist_flow_ack_seen",
    "hist_flow_rst_seen",
    "hist_flow_fin_seen",
    "hist_log_flow_retransmissions",
    "hist_log_flow_lost_segments",
]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_key(value: str) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:20]


RAW51_MASK_SOURCE = "processed/iotsim-hydraulic-system-1.csv"
RAW51_MASK_ROWS = 1353


def load_raw51_mask(path: Any, expected_sha256: Any) -> dict[str, set[int]]:
    """Versioned ``raw51_observable_v1`` eligibility mask (ledger section 11).

    Lists frozen targets that have no legal same-observation-unit raw-51D
    input. Generated only from raw-packet alignment results; loading reads no
    label, score, or experiment outcome. Version-1 gates are hard: exact
    SHA-256, exactly one benign source, exactly 1,353 unique rows.
    """
    data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    digest = hashlib.sha256(data).hexdigest()
    if digest != str(expected_sha256).strip().lower():
        raise RuntimeError(f"raw51 mask sha256 mismatch: {digest}")
    masked: defaultdict[str, set[int]] = defaultdict(set)
    total = 0
    for row in csv.DictReader(io.StringIO(data.decode("utf-8"))):
        masked[str(row["source_group"])].add(int(row["recorded_index"]))
        total += 1
    if sorted(masked) != [RAW51_MASK_SOURCE]:
        raise RuntimeError(f"raw51 mask source set unexpected: {sorted(masked)}")
    if total != RAW51_MASK_ROWS or len(masked[RAW51_MASK_SOURCE]) != RAW51_MASK_ROWS:
        raise RuntimeError(f"raw51 mask row count unexpected: {total}")
    return dict(masked)


def dump_json(path: Path, value: Any) -> None:
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"refuse to write empty CSV: {path}")
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(str(value).strip())
        return result if math.isfinite(result) else default
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return default


def as_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    return text not in {"", "0", "0.0", "false", "none", "nan"}


def normalize_port(value: Any) -> int:
    port = as_int(value, 0)
    return port if 0 <= port <= 65535 else 0


def port_class(port: int) -> float:
    if port <= 0:
        return 0.0
    if port <= 1023:
        return 0.25
    if port <= 49151:
        return 0.50
    return 0.75


def log_ms(seconds: float | None) -> float:
    if seconds is None or not math.isfinite(seconds) or seconds < 0:
        return 0.0
    return math.log1p(seconds * 1000.0)


def source_stem(source_group: str) -> str:
    return Path(str(source_group)).stem


def exact_pcap_members(names: Iterable[str], source_group: str) -> list[str]:
    """Match a complete source stem, never the ambiguous prefix ``foo-1``."""
    stem = source_stem(source_group)
    pattern = re.compile(
        rf"(?:^|/){re.escape(stem)}_[^/]+\.(?:pcap|pcapng)$",
        flags=re.IGNORECASE,
    )
    matches = sorted(name for name in names if pattern.search(str(name)))
    if not matches:
        raise RuntimeError(f"no exact PCAP member for source: {source_group}")
    for member in matches:
        filename = Path(member).name
        if not filename.startswith(stem + "_"):
            raise RuntimeError(f"ambiguous PCAP prefix match: {source_group}: {member}")
    return matches


def parse_gotham_time(value: Any) -> float:
    text = str(value).strip()
    if not text:
        return math.nan
    if text.endswith(" GMT"):
        text = text[:-4]
    match = re.match(r"^(.*?\.)(\d+)$", text)
    if match:
        text = match.group(1) + (match.group(2) + "000000")[:6]
        fmt = "%b %d, %Y %H:%M:%S.%f"
    else:
        fmt = "%b %d, %Y %H:%M:%S"
    try:
        return datetime.strptime(text, fmt).replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return math.nan


@dataclass(frozen=True)
class PacketEvent:
    frame_number: int
    timestamp: float
    frame_len: int
    src: str
    dst: str
    ip_version: int
    ip_proto: int
    src_port: int
    dst_port: int
    tcp_syn: bool
    tcp_ack: bool
    tcp_rst: bool
    tcp_fin: bool
    tcp_stream: int
    udp_stream: int
    tcp_stream_pnum: int
    tcp_time_relative: float
    tcp_time_delta: float
    tcp_connection_syn: bool
    retransmission: bool
    lost_segment: bool

    @property
    def is_tcp(self) -> bool:
        return self.ip_proto == 6 or self.tcp_stream >= 0

    @property
    def is_udp(self) -> bool:
        return self.ip_proto == 17 or self.udp_stream >= 0

    @property
    def is_icmp(self) -> bool:
        return self.ip_proto in {1, 58}

    @property
    def directed_pair(self) -> tuple[str, str]:
        return self.src, self.dst

    @property
    def reverse_pair(self) -> tuple[str, str]:
        return self.dst, self.src

    @property
    def flow_key(self) -> tuple[Any, ...]:
        # TShark stream IDs are source-local and never enter the feature vector.
        if self.is_tcp and self.tcp_stream >= 0:
            return ("tcp_stream", self.tcp_stream)
        if self.is_udp and self.udp_stream >= 0:
            return ("udp_stream", self.udp_stream)
        left = (self.src, self.src_port)
        right = (self.dst, self.dst_port)
        return ("five_tuple", self.ip_proto, *sorted((left, right)))


def event_from_tshark(row: dict[str, str]) -> PacketEvent:
    src4, dst4 = str(row.get("ip.src", "")).strip(), str(row.get("ip.dst", "")).strip()
    src6, dst6 = str(row.get("ipv6.src", "")).strip(), str(row.get("ipv6.dst", "")).strip()
    src, dst = (src4, dst4) if src4 or dst4 else (src6, dst6)
    tcp_src = normalize_port(row.get("tcp.srcport", ""))
    tcp_dst = normalize_port(row.get("tcp.dstport", ""))
    udp_src = normalize_port(row.get("udp.srcport", ""))
    udp_dst = normalize_port(row.get("udp.dstport", ""))
    tcp_stream_text = str(row.get("tcp.stream", "")).strip()
    udp_stream_text = str(row.get("udp.stream", "")).strip()
    return PacketEvent(
        frame_number=as_int(row.get("frame.number"), 0),
        timestamp=as_float(row.get("frame.time_epoch"), math.nan),
        frame_len=max(0, as_int(row.get("frame.len"), 0)),
        src=src or "missing-src",
        dst=dst or "missing-dst",
        ip_version=4 if src4 or dst4 else (6 if src6 or dst6 else 0),
        ip_proto=as_int(row.get("ip.proto"), 0),
        src_port=tcp_src or udp_src,
        dst_port=tcp_dst or udp_dst,
        tcp_syn=as_bool(row.get("tcp.flags.syn")),
        tcp_ack=as_bool(row.get("tcp.flags.ack")),
        tcp_rst=as_bool(row.get("tcp.flags.reset")),
        tcp_fin=as_bool(row.get("tcp.flags.fin")),
        tcp_stream=as_int(tcp_stream_text, -1) if tcp_stream_text else -1,
        udp_stream=as_int(udp_stream_text, -1) if udp_stream_text else -1,
        tcp_stream_pnum=max(0, as_int(row.get("tcp.stream.pnum"), 0)),
        tcp_time_relative=max(0.0, as_float(row.get("tcp.time_relative"), 0.0)),
        tcp_time_delta=max(0.0, as_float(row.get("tcp.time_delta"), 0.0)),
        tcp_connection_syn=as_bool(row.get("tcp.connection.syn")),
        retransmission=as_bool(row.get("tcp.analysis.retransmission")),
        lost_segment=as_bool(row.get("tcp.analysis.lost_segment")),
    )


@dataclass
class PairState:
    count: int = 0
    bytes: int = 0
    last_time: float | None = None


@dataclass
class FlowState:
    first_time: float
    last_time: float
    first_direction: tuple[str, str]
    packets: int = 0
    forward: int = 0
    reverse: int = 0
    syn: int = 0
    ack: int = 0
    rst: int = 0
    fin: int = 0
    retransmission: int = 0
    lost_segment: int = 0


@dataclass
class EndpointState:
    count: int = 0
    last_time: float | None = None
    recent: deque[tuple[float, str, int, bool, bool]] = field(default_factory=deque)


class CausalFeatureBuilder:
    """Stateful source-local causal feature transform.

    ``emit`` never mutates state.  ``update`` is the only mutating operation,
    which makes score-before-update testable rather than merely documented.
    """

    def __init__(self) -> None:
        self.source_times: deque[float] = deque()
        self.source_count = 0
        self.source_last: float | None = None
        self.endpoints: dict[str, EndpointState] = {}
        self.pairs: dict[tuple[str, str], PairState] = {}
        self.flows: dict[tuple[Any, ...], FlowState] = {}
        self.nodes: dict[str, int] = {}

    def node(self, value: str) -> int:
        if value not in self.nodes:
            self.nodes[value] = len(self.nodes)
        return self.nodes[value]

    @staticmethod
    def _prune_times(values: deque[float], now: float) -> None:
        while values and now - values[0] > WINDOWS_SECONDS[-1]:
            values.popleft()

    @staticmethod
    def _prune_endpoint(values: deque[tuple[float, str, int, bool, bool]], now: float) -> None:
        while values and now - values[0][0] > WINDOWS_SECONDS[-1]:
            values.popleft()

    def emit(self, event: PacketEvent) -> np.ndarray:
        if not math.isfinite(event.timestamp):
            raise RuntimeError("nonfinite current event timestamp")
        # Pruning expired past records does not expose the current event.
        self._prune_times(self.source_times, event.timestamp)
        endpoint = self.endpoints.setdefault(event.src, EndpointState())
        self._prune_endpoint(endpoint.recent, event.timestamp)
        pair = self.pairs.get(event.directed_pair, PairState())
        reverse = self.pairs.get(event.reverse_pair, PairState())
        flow = self.flows.get(event.flow_key)

        source_rates = [
            sum(event.timestamp - stamp <= window for stamp in self.source_times) / window
            for window in WINDOWS_SECONDS
        ]
        unique_peers = []
        unique_ports = []
        for window in WINDOWS_SECONDS:
            recent = [item for item in endpoint.recent if event.timestamp - item[0] <= window]
            unique_peers.append(float(len({item[1] for item in recent})))
            unique_ports.append(float(len({item[2] for item in recent if item[2] > 0})))
        recent60 = list(endpoint.recent)
        syn_rate = float(sum(item[3] for item in recent60) / len(recent60)) if recent60 else 0.0
        rst_rate = float(sum(item[4] for item in recent60) / len(recent60)) if recent60 else 0.0

        flow_packets = flow.packets if flow else 0
        flow_elapsed = event.timestamp - flow.first_time if flow else 0.0
        vector = np.asarray(
            [
                math.log1p(event.frame_len),
                float(event.ip_version == 4),
                float(event.ip_version == 6),
                float(event.is_tcp),
                float(event.is_udp),
                float(event.is_icmp),
                port_class(event.src_port),
                port_class(event.dst_port),
                float(0 < event.dst_port <= 1023),
                float(event.tcp_syn),
                float(event.tcp_ack),
                float(event.tcp_rst),
                float(event.tcp_fin),
                float(event.retransmission),
                float(event.lost_segment),
                math.log1p(event.tcp_stream_pnum),
                log_ms(event.tcp_time_relative),
                log_ms(event.tcp_time_delta),
                math.log1p(self.source_count),
                log_ms(None if self.source_last is None else event.timestamp - self.source_last),
                *source_rates,
                math.log1p(endpoint.count),
                log_ms(None if endpoint.last_time is None else event.timestamp - endpoint.last_time),
                *unique_peers,
                *unique_ports,
                syn_rate,
                rst_rate,
                math.log1p(pair.count),
                math.log1p(reverse.count),
                log_ms(None if pair.last_time is None else event.timestamp - pair.last_time),
                log_ms(None if reverse.last_time is None else event.timestamp - reverse.last_time),
                float(reverse.count > 0),
                math.log1p(pair.bytes),
                math.log1p(reverse.bytes),
                math.log1p(flow_packets),
                log_ms(flow_elapsed),
                math.log1p(flow.forward if flow else 0),
                math.log1p(flow.reverse if flow else 0),
                float(bool(flow and flow.forward and flow.reverse)),
                float(bool(flow and flow.syn)),
                float(bool(flow and flow.ack)),
                float(bool(flow and flow.rst)),
                float(bool(flow and flow.fin)),
                math.log1p(flow.retransmission if flow else 0),
                math.log1p(flow.lost_segment if flow else 0),
            ],
            dtype=np.float32,
        )
        if vector.shape != (len(FEATURE_NAMES),) or not np.isfinite(vector).all():
            raise RuntimeError(f"invalid causal feature vector: {vector.shape}")
        return vector

    def update(self, event: PacketEvent) -> tuple[int, int]:
        src_id, dst_id = self.node(event.src), self.node(event.dst)
        self.source_count += 1
        self.source_last = event.timestamp
        self.source_times.append(event.timestamp)

        endpoint = self.endpoints.setdefault(event.src, EndpointState())
        endpoint.count += 1
        endpoint.last_time = event.timestamp
        endpoint.recent.append(
            (event.timestamp, event.dst, event.dst_port, event.tcp_syn, event.tcp_rst)
        )

        pair = self.pairs.setdefault(event.directed_pair, PairState())
        pair.count += 1
        pair.bytes += event.frame_len
        pair.last_time = event.timestamp

        flow = self.flows.get(event.flow_key)
        if flow is None:
            flow = FlowState(event.timestamp, event.timestamp, event.directed_pair)
            self.flows[event.flow_key] = flow
        flow.last_time = event.timestamp
        flow.packets += 1
        if event.directed_pair == flow.first_direction:
            flow.forward += 1
        else:
            flow.reverse += 1
        flow.syn += int(event.tcp_syn)
        flow.ack += int(event.tcp_ack)
        flow.rst += int(event.tcp_rst)
        flow.fin += int(event.tcp_fin)
        flow.retransmission += int(event.retransmission)
        flow.lost_segment += int(event.lost_segment)
        return src_id, dst_id

    def transform(self, events: Iterable[PacketEvent]) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        features: list[np.ndarray] = []
        times: list[float] = []
        src: list[int] = []
        dst: list[int] = []
        for event in events:
            features.append(self.emit(event))
            times.append(event.timestamp)
            left, right = self.update(event)
            src.append(left)
            dst.append(right)
        return (
            np.vstack(features).astype(np.float32) if features else np.empty((0, len(FEATURE_NAMES)), dtype=np.float32),
            np.asarray(times, dtype=np.float64),
            np.asarray(src, dtype=np.int32),
            np.asarray(dst, dtype=np.int32),
        )


@dataclass(frozen=True)
class TargetFingerprint:
    source_group: str
    recorded_index: int
    timestamp: float
    frame_len: int
    src: str
    dst: str
    ip_proto: int
    src_port: int
    dst_port: int

    @property
    def time_us(self) -> int:
        return int(round(self.timestamp * 1_000_000.0))


def target_from_processed_row(source: str, index: int, row: dict[str, str]) -> TargetFingerprint:
    tcp_src = normalize_port(row.get("tcp.srcport"))
    tcp_dst = normalize_port(row.get("tcp.dstport"))
    udp_src = normalize_port(row.get("udp.srcport"))
    udp_dst = normalize_port(row.get("udp.dstport"))
    return TargetFingerprint(
        source_group=source,
        recorded_index=int(index),
        timestamp=parse_gotham_time(row.get("frame.time")),
        frame_len=max(0, as_int(row.get("frame.len"), 0)),
        src=str(row.get("ip.src", "")).strip(),
        dst=str(row.get("ip.dst", "")).strip(),
        ip_proto=as_int(row.get("ip.proto"), 0),
        src_port=tcp_src or udp_src,
        dst_port=tcp_dst or udp_dst,
    )


def load_target_indices(paths: Sequence[Path]) -> dict[str, set[int]]:
    result: defaultdict[str, set[int]] = defaultdict(set)
    for path in paths:
        frame = pd.read_csv(Path(path), usecols=["source_group", "recorded_index"])
        for row in frame.itertuples(index=False):
            index = as_int(row.recorded_index, -1)
            if index >= 0:
                result[str(row.source_group)].add(index)
    if not result:
        raise RuntimeError("empty unified target plan")
    return dict(result)


def read_gotham_target_fingerprints(
    archive: zipfile.ZipFile, source: str, target_indices: set[int]
) -> list[TargetFingerprint]:
    if not target_indices:
        return []
    wanted = set(int(value) for value in target_indices)
    found: list[TargetFingerprint] = []
    with archive.open(source) as raw:
        text = io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace", newline="")
        reader = csv.DictReader(text)
        missing_fields = sorted(set(GOTHAM_ALIGNMENT_FIELDS) - set(reader.fieldnames or []))
        if missing_fields:
            raise RuntimeError(f"Gotham alignment fields missing for {source}: {missing_fields}")
        if "label" not in (reader.fieldnames or []):
            raise RuntimeError(f"unexpected Gotham processed schema without label audit column: {source}")
        for index, row in enumerate(reader):
            if index in wanted:
                safe = {name: row.get(name, "") for name in GOTHAM_ALIGNMENT_FIELDS}
                found.append(target_from_processed_row(source, index, safe))
                if len(found) == len(wanted):
                    break
    actual = {item.recorded_index for item in found}
    if actual != wanted:
        raise RuntimeError(f"missing processed target rows for {source}: {sorted(wanted - actual)[:8]}")
    if any(not math.isfinite(item.timestamp) for item in found):
        raise RuntimeError(f"nonfinite processed target timestamps for {source}")
    return found


class TargetMatcher:
    def __init__(self, targets: Sequence[TargetFingerprint], tolerance_us: int = 2):
        self.targets = list(targets)
        self.tolerance_us = int(tolerance_us)
        self.by_time: defaultdict[int, list[int]] = defaultdict(list)
        for index, target in enumerate(self.targets):
            for key in range(target.time_us - self.tolerance_us, target.time_us + self.tolerance_us + 1):
                self.by_time[key].append(index)
        self.matches: dict[int, tuple[str, int, np.ndarray, float, int, int]] = {}
        self.ambiguous: set[int] = set()

    @staticmethod
    def compatible(target: TargetFingerprint, event: PacketEvent) -> bool:
        return (
            target.frame_len == event.frame_len
            and (not target.src or target.src == event.src)
            and (not target.dst or target.dst == event.dst)
            and (not target.ip_proto or target.ip_proto == event.ip_proto)
            and (not target.src_port or target.src_port == event.src_port)
            and (not target.dst_port or target.dst_port == event.dst_port)
        )

    def observe(
        self,
        member: str,
        event_position: int,
        event: PacketEvent,
        feature: np.ndarray,
        src_id: int,
        dst_id: int,
    ) -> None:
        key = int(round(event.timestamp * 1_000_000.0))
        candidates = {
            index
            for index in self.by_time.get(key, [])
            if self.compatible(self.targets[index], event)
        }
        for index in candidates:
            if index in self.matches:
                self.ambiguous.add(index)
            else:
                self.matches[index] = (
                    member,
                    int(event_position),
                    np.asarray(feature, dtype=np.float32).copy(),
                    float(event.timestamp),
                    int(src_id),
                    int(dst_id),
                )

    def finalize(self) -> list[dict[str, Any]]:
        if self.ambiguous:
            rows = [self.targets[index].recorded_index for index in sorted(self.ambiguous)]
            raise RuntimeError(f"ambiguous PCAP target alignment: {rows[:8]}")
        missing = [
            target.recorded_index
            for index, target in enumerate(self.targets)
            if index not in self.matches
        ]
        if missing:
            raise RuntimeError(f"incomplete PCAP target alignment: {missing[:8]}")
        rows: list[dict[str, Any]] = []
        for index, target in enumerate(self.targets):
            member, position, feature, available, src_id, dst_id = self.matches[index]
            rows.append(
                {
                    "source_group": target.source_group,
                    "recorded_index": target.recorded_index,
                    "raw_source_path": member,
                    "target_event_position_within_capture": position,
                    "feature_available_time_epoch": available,
                    "src_local_id": src_id,
                    "dst_local_id": dst_id,
                    "feature": feature,
                }
            )
        return rows


def tshark_command(
    tshark: str, read_path: str, packet_limit: int | None = None
) -> list[str]:
    command = [
        str(tshark),
        "-n",
        "-r",
        read_path,
        "-T",
        "fields",
        "-E",
        "header=y",
        "-E",
        "separator=/t",
        "-E",
        "quote=d",
        "-E",
        "occurrence=f",
    ]
    if packet_limit is not None:
        if int(packet_limit) <= 0:
            raise ValueError(f"invalid TShark packet limit: {packet_limit}")
        command.extend(["-c", str(int(packet_limit))])
    for name in TSHARK_FIELDS:
        command.extend(["-e", name])
    return command


def iter_tshark_rows(
    tshark: str,
    pcap_path: Path | None = None,
    archive: zipfile.ZipFile | None = None,
    member: str | None = None,
    packet_limit: int | None = None,
) -> Iterator[dict[str, str]]:
    if (pcap_path is None) == (archive is None or member is None):
        raise ValueError("provide either pcap_path or archive+member")
    stderr = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    producer_error: list[BaseException] = []
    if pcap_path is not None:
        command = tshark_command(tshark, str(Path(pcap_path)), packet_limit)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        producer = None
    else:
        command = tshark_command(tshark, "-", packet_limit)
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr,
            text=False,
        )

        def feed() -> None:
            assert archive is not None and member is not None and process.stdin is not None
            try:
                with archive.open(member) as raw:
                    shutil.copyfileobj(raw, process.stdin, length=1024 * 1024)
            except BrokenPipeError as exc:
                # Expected when ``-c`` intentionally stops before the end of
                # a ZIP member; it is not an extraction failure.
                if packet_limit is None:
                    producer_error.append(exc)
            except BaseException as exc:  # propagated after the process closes
                producer_error.append(exc)
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass

        producer = threading.Thread(target=feed, name="ckbu-zip-pcap-feed", daemon=True)
        producer.start()

    assert process.stdout is not None
    if pcap_path is not None:
        text_stream: TextIO = process.stdout  # type: ignore[assignment]
    else:
        text_stream = io.TextIOWrapper(process.stdout, encoding="utf-8", errors="replace", newline="")
    reader = csv.DictReader(text_stream, delimiter="\t", quotechar='"')
    if list(reader.fieldnames or []) != TSHARK_FIELDS:
        process.kill()
        raise RuntimeError(f"TShark field header drift: {reader.fieldnames}")
    try:
        for row in reader:
            yield {name: row.get(name, "") for name in TSHARK_FIELDS}
    finally:
        text_stream.close()
        code = process.wait()
        if producer is not None:
            producer.join(timeout=30)
        stderr.seek(0)
        error_text = stderr.read().strip()
        stderr.close()
    if producer_error:
        raise RuntimeError(f"failed to stream PCAP member: {producer_error[0]}")
    if code != 0:
        raise RuntimeError(f"TShark exited {code}: {error_text[-2000:]}")


def process_capture(
    rows: Iterable[dict[str, str]],
    member: str,
    matcher: TargetMatcher | None = None,
    keep_positions: set[int] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    builder = CausalFeatureBuilder()
    selected: list[dict[str, Any]] = []
    parsed = 0
    timestamp_violations = 0
    previous = -math.inf
    for position, row in enumerate(rows):
        event = event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        timestamp_violations += int(event.timestamp < previous)
        previous = max(previous, event.timestamp)
        feature = builder.emit(event)
        src_id, dst_id = builder.update(event)
        if matcher is not None:
            matcher.observe(member, position, event, feature, src_id, dst_id)
        if keep_positions is not None and position in keep_positions:
            selected.append(
                {
                    "raw_source_path": member,
                    "target_event_position_within_capture": position,
                    "feature_available_time_epoch": event.timestamp,
                    "src_local_id": src_id,
                    "dst_local_id": dst_id,
                    "feature": feature.copy(),
                }
            )
        parsed += 1
    audit = {
        "raw_source_path": member,
        "decoded_events": parsed,
        "source_local_nodes": len(builder.nodes),
        "recorded_order_timestamp_violations": timestamp_violations,
        "fresh_source_reset": True,
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "raw_label_column_read": False,
        "event_schema": "TShark 4.6.6 packet fields",
        "feature_schema_dim": len(FEATURE_NAMES),
    }
    return selected, audit


def plan_gotham(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    targets = load_target_indices([Path(path) for path in args.targets])
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        names = archive.namelist()
        rows = []
        for source, indices in sorted(targets.items()):
            members = exact_pcap_members(names, source)
            rows.append(
                {
                    "source_group": source,
                    "source_cache_key": stable_key(source),
                    "target_rows": len(indices),
                    "min_recorded_index": min(indices),
                    "max_recorded_index": max(indices),
                    "candidate_pcap_members": len(members),
                    "pcap_members_json": json.dumps(members, separators=(",", ":")),
                    "pairing_rule": "exact_complete_source_stem_then_target_timestamp_and_packet_fingerprint_unique",
                    "raw_label_column_read": False,
                }
            )
    plan_path = out / "ckbu_gotham_source_plan.csv"
    write_csv(plan_path, rows)
    dump_json(
        out / "ckbu_gotham_plan.json",
        {
            "status": "CKBU_GOTHAM_PLAN_READY",
            "sources": len(rows),
            "targets": sum(row["target_rows"] for row in rows),
            "source_plan_sha256": sha256_file(plan_path),
            "original_split_modified": False,
            "raw_label_column_read": False,
            "feature_schema": FEATURE_NAMES,
        },
    )


def materialize_gotham_source(args: argparse.Namespace) -> None:
    out = Path(args.out)
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    plan = pd.read_csv(Path(args.source_plan))
    if args.source_index < 0 or args.source_index >= len(plan):
        raise RuntimeError(f"source index outside plan: {args.source_index}/{len(plan)}")
    source = str(plan.iloc[int(args.source_index)]["source_group"])
    targets = load_target_indices([Path(path) for path in args.targets])
    if source not in targets:
        raise RuntimeError(f"planned source has no targets: {source}")
    started = time.time()
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        fingerprints = read_gotham_target_fingerprints(archive, source, targets[source])
        matcher = TargetMatcher(fingerprints, int(args.alignment_tolerance_us))
        members = json.loads(str(plan.iloc[int(args.source_index)]["pcap_members_json"]))
        audits = []
        for member in members:
            rows = iter_tshark_rows(args.tshark, archive=archive, member=str(member))
            _selected, audit = process_capture(rows, str(member), matcher=matcher)
            audits.append(audit)
    aligned = sorted(matcher.finalize(), key=lambda row: int(row["recorded_index"]))
    features = np.vstack([row.pop("feature") for row in aligned]).astype(np.float32)
    key = stable_key(source)
    npz = cache / f"{key}.npz"
    np.savez_compressed(
        npz,
        recorded_index=np.asarray([row["recorded_index"] for row in aligned], dtype=np.int64),
        feature_available_time_epoch=np.asarray(
            [row["feature_available_time_epoch"] for row in aligned], dtype=np.float64
        ),
        target_event_position_within_capture=np.asarray(
            [row["target_event_position_within_capture"] for row in aligned], dtype=np.int64
        ),
        src_local_id=np.asarray([row["src_local_id"] for row in aligned], dtype=np.int32),
        dst_local_id=np.asarray([row["dst_local_id"] for row in aligned], dtype=np.int32),
        causal_features=features,
        feature_names=np.asarray(FEATURE_NAMES),
        raw_source_path=np.asarray([row["raw_source_path"] for row in aligned]),
    )
    summary = {
        "status": "CKBU_GOTHAM_SOURCE_COMPLETE",
        "source_group": source,
        "source_cache_key": key,
        "target_rows": len(aligned),
        "target_positions_complete": len(aligned) == len(targets[source]),
        "candidate_captures_processed": len(audits),
        "capture_audit": audits,
        "cache_npz": str(npz),
        "cache_sha256": sha256_file(npz),
        "feature_schema": FEATURE_NAMES,
        "feature_schema_dim": len(FEATURE_NAMES),
        "feature_available_time_recorded": True,
        "score_before_update": True,
        "source_fresh_reset_per_capture": True,
        "raw_label_column_read": False,
        "original_split_modified": False,
        "seconds": time.time() - started,
    }
    dump_json(cache / f"{key}.json", summary)
    runtime = out / "source_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    dump_json(runtime / f"{key}.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def aggregate_gotham(args: argparse.Namespace) -> None:
    out = Path(args.out)
    plan = pd.read_csv(Path(args.source_plan))
    cache = Path(args.cache_dir)
    raw51_mask = (
        load_raw51_mask(args.raw51_mask, args.raw51_mask_sha256)
        if getattr(args, "raw51_mask", None)
        else {}
    )
    rows = []
    masked_source_total = 0
    for item in plan.itertuples(index=False):
        source = str(item.source_group)
        key = str(item.source_cache_key)
        masked_rows = len(raw51_mask.get(source, ()))
        if masked_rows and masked_rows != int(item.target_rows):
            raise RuntimeError(
                f"raw51 mask v1 supports only fully-masked sources: {source} "
                f"{masked_rows}/{item.target_rows}"
            )
        if masked_rows:
            # A fully-masked source has no legal same-observation-unit raw-51D
            # input; it is absent from the raw-51D materialization by design.
            masked_source_total += masked_rows
            continue
        npz = cache / f"{key}.npz"
        meta = cache / f"{key}.json"
        if not npz.is_file() or not meta.is_file():
            raise RuntimeError(f"missing CKBU source cache: {source}")
        summary = json.loads(meta.read_text(encoding="utf-8"))
        with np.load(npz, allow_pickle=False) as values:
            shape = tuple(values["causal_features"].shape)
            target_rows = len(values["recorded_index"])
            names = values["feature_names"].astype(str).tolist()
        if shape != (int(item.target_rows), len(FEATURE_NAMES)) or names != FEATURE_NAMES:
            raise RuntimeError(f"CKBU cache schema/coverage drift: {source}: {shape}")
        if not bool(summary.get("target_positions_complete")) or bool(
            summary.get("raw_label_column_read", True)
        ):
            raise RuntimeError(f"CKBU cache contract failed: {source}")
        rows.append(
            {
                "source_group": source,
                "source_cache_key": key,
                "target_rows": target_rows,
                "feature_schema_dim": shape[1],
                "candidate_captures_processed": summary["candidate_captures_processed"],
                "cache_npz": str(npz),
                "cache_sha256": sha256_file(npz),
                "target_positions_complete": True,
                "feature_available_time_recorded": True,
                "score_before_update": True,
                "source_fresh_reset_per_capture": True,
                "raw_label_column_read": False,
                "fit_select_report_roles_changed": False,
            }
        )
    manifest = out / "ckbu_gotham_unified_causal_manifest.csv"
    write_csv(manifest, rows)
    dump_json(
        out / "ckbu_gotham_unified_causal_ready.json",
        {
            "status": "CKBU_GOTHAM_UNIFIED_CAUSAL_READY",
            "sources": len(rows),
            "targets": sum(row["target_rows"] for row in rows),
            "raw51_masked_targets_total": masked_source_total,
            "raw51_fully_masked_sources": sorted(raw51_mask),
            "raw51_observable_mask_sha256": (
                str(args.raw51_mask_sha256).strip().lower() if raw51_mask else None
            ),
            "manifest_sha256": sha256_file(manifest),
            "feature_schema": FEATURE_NAMES,
            "raw_label_column_read": False,
            "original_split_modified": False,
        },
    )


def plan_auxiliary(args: argparse.Namespace) -> None:
    """Freeze the already-legal CKBO/CKBQ benign source roles for re-decoding."""
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    frame = pd.read_csv(Path(args.aux_manifest))
    required = {
        "source_group",
        "device_family",
        "role",
        "raw_source_path",
        "warmup_packets",
        "model_ready_rows",
        "raw_label_column_read",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"auxiliary manifest fields missing: {missing}")
    if frame["source_group"].astype(str).duplicated().any():
        raise RuntimeError("duplicate auxiliary source")
    truth = frame["raw_label_column_read"].astype(str).str.lower()
    if truth.isin({"true", "1", "yes"}).any():
        raise RuntimeError("auxiliary manifest says raw label was read")
    rows = []
    for item in frame.sort_values("source_group", kind="mergesort").itertuples(index=False):
        warmup = int(item.warmup_packets)
        count = int(item.model_ready_rows)
        rows.append(
            {
                "source_group": str(item.source_group),
                "source_cache_key": stable_key(str(item.source_group)),
                "device_family": str(item.device_family),
                "role": str(item.role),
                "raw_source_path": str(item.raw_source_path),
                "warmup_packets": warmup,
                "target_rows": count,
                "first_target_event_position": warmup,
                "last_target_event_position": warmup + count - 1,
                "raw_label_column_read": False,
                "role_source_reused_without_resplit": True,
            }
        )
    plan_path = out / "ckbu_auxiliary_source_plan.csv"
    write_csv(plan_path, rows)
    dump_json(
        out / "ckbu_auxiliary_plan.json",
        {
            "status": "CKBU_AUXILIARY_PLAN_READY",
            "sources": len(rows),
            "targets": sum(row["target_rows"] for row in rows),
            "roles": {
                role: sum(row["role"] == role for row in rows)
                for role in sorted({row["role"] for row in rows})
            },
            "source_plan_sha256": sha256_file(plan_path),
            "roles_modified": False,
            "raw_label_column_read": False,
        },
    )


def materialize_auxiliary_source(args: argparse.Namespace) -> None:
    out = Path(args.out)
    cache = Path(args.cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    plan = pd.read_csv(Path(args.source_plan))
    if args.source_index < 0 or args.source_index >= len(plan):
        raise RuntimeError(f"source index outside auxiliary plan: {args.source_index}/{len(plan)}")
    item = plan.iloc[int(args.source_index)]
    source = str(item["source_group"])
    member = str(item["raw_source_path"])
    first = int(item["first_target_event_position"])
    last = int(item["last_target_event_position"])
    keep = set(range(first, last + 1))
    started = time.time()
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        if member not in set(archive.namelist()):
            raise RuntimeError(f"auxiliary PCAP member missing: {member}")
        selected, audit = process_capture(
            iter_tshark_rows(
                args.tshark,
                archive=archive,
                member=member,
                packet_limit=last + 1,
            ),
            member,
            keep_positions=keep,
        )
    if len(selected) != int(item["target_rows"]):
        raise RuntimeError(
            f"auxiliary target coverage incomplete: {source}: {len(selected)}/{item['target_rows']}"
        )
    selected.sort(key=lambda row: int(row["target_event_position_within_capture"]))
    features = np.vstack([row.pop("feature") for row in selected]).astype(np.float32)
    key = stable_key(source)
    npz = cache / f"{key}.npz"
    np.savez_compressed(
        npz,
        target_row=np.arange(len(selected), dtype=np.int64),
        feature_available_time_epoch=np.asarray(
            [row["feature_available_time_epoch"] for row in selected], dtype=np.float64
        ),
        target_event_position_within_capture=np.asarray(
            [row["target_event_position_within_capture"] for row in selected], dtype=np.int64
        ),
        src_local_id=np.asarray([row["src_local_id"] for row in selected], dtype=np.int32),
        dst_local_id=np.asarray([row["dst_local_id"] for row in selected], dtype=np.int32),
        causal_features=features,
        feature_names=np.asarray(FEATURE_NAMES),
        raw_source_path=np.asarray(member),
    )
    summary = {
        "status": "CKBU_AUXILIARY_SOURCE_COMPLETE",
        "source_group": source,
        "source_cache_key": key,
        "device_family": str(item["device_family"]),
        "role": str(item["role"]),
        "target_rows": len(selected),
        "target_positions_complete": len(selected) == int(item["target_rows"]),
        "capture_audit": audit,
        "cache_npz": str(npz),
        "cache_sha256": sha256_file(npz),
        "feature_schema": FEATURE_NAMES,
        "feature_schema_dim": len(FEATURE_NAMES),
        "feature_available_time_recorded": True,
        "score_before_update": True,
        "source_fresh_reset": True,
        "raw_label_column_read": False,
        "roles_modified": False,
        "seconds": time.time() - started,
    }
    dump_json(cache / f"{key}.json", summary)
    runtime = out / "source_runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    dump_json(runtime / f"{key}.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


def aggregate_auxiliary(args: argparse.Namespace) -> None:
    out = Path(args.out)
    plan = pd.read_csv(Path(args.source_plan))
    cache = Path(args.cache_dir)
    rows = []
    for item in plan.itertuples(index=False):
        source = str(item.source_group)
        key = str(item.source_cache_key)
        npz = cache / f"{key}.npz"
        meta = cache / f"{key}.json"
        if not npz.is_file() or not meta.is_file():
            raise RuntimeError(f"missing CKBU auxiliary cache: {source}")
        summary = json.loads(meta.read_text(encoding="utf-8"))
        with np.load(npz, allow_pickle=False) as values:
            shape = tuple(values["causal_features"].shape)
            names = values["feature_names"].astype(str).tolist()
        if shape != (int(item.target_rows), len(FEATURE_NAMES)) or names != FEATURE_NAMES:
            raise RuntimeError(f"CKBU auxiliary cache schema/coverage drift: {source}: {shape}")
        if not bool(summary.get("target_positions_complete")) or bool(
            summary.get("raw_label_column_read", True)
        ):
            raise RuntimeError(f"CKBU auxiliary cache contract failed: {source}")
        rows.append(
            {
                "source_group": source,
                "source_cache_key": key,
                "device_family": str(item.device_family),
                "role": str(item.role),
                "target_rows": int(item.target_rows),
                "feature_schema_dim": shape[1],
                "cache_npz": str(npz),
                "cache_sha256": sha256_file(npz),
                "target_positions_complete": True,
                "feature_available_time_recorded": True,
                "score_before_update": True,
                "source_fresh_reset": True,
                "raw_label_column_read": False,
                "roles_modified": False,
            }
        )
    manifest = out / "ckbu_auxiliary_unified_causal_manifest.csv"
    write_csv(manifest, rows)
    dump_json(
        out / "ckbu_auxiliary_unified_causal_ready.json",
        {
            "status": "CKBU_AUXILIARY_UNIFIED_CAUSAL_READY",
            "sources": len(rows),
            "targets": sum(row["target_rows"] for row in rows),
            "manifest_sha256": sha256_file(manifest),
            "feature_schema": FEATURE_NAMES,
            "raw_label_column_read": False,
            "roles_modified": False,
        },
    )


TON_PILOT_FILES = {
    "normal_1.pcap": "aux_normal_fit",
    "normal_2.pcap": "aux_normal_select",
    "normal_scanning1.pcap": "aux_process_fit",
    "password_normal1.pcap": "aux_process_fit",
    "injection_normal1.pcap": "reserved_internal_report_no_model_use",
    "MITM_normal1.pcap": "reserved_internal_report_no_model_use",
}
TON_PAIR_TO_PCAP = {
    "scanning_fit_capture_1": "normal_scanning1.pcap",
    "password_fit_capture_1": "password_normal1.pcap",
}


def pcap_container(path: Path) -> str:
    # Some pilot captures are larger than 1 GiB.  Reading the whole file merely
    # to inspect its container signature can exhaust a login node before the
    # real extraction starts.
    with Path(path).open("rb") as handle:
        magic = handle.read(4)
    if magic == bytes.fromhex("0a0d0d0a"):
        return "pcapng"
    if magic in {
        bytes.fromhex("d4c3b2a1"),
        bytes.fromhex("a1b2c3d4"),
        bytes.fromhex("4d3cb2a1"),
        bytes.fromhex("a1b23c4d"),
    }:
        return "pcap"
    return "unknown"


def plan_ton_pilot(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pilot = Path(args.ton_pilot_dir)
    rows = []
    for name, role in TON_PILOT_FILES.items():
        path = pilot / name
        if not path.is_file():
            raise FileNotFoundError(path)
        container = pcap_container(path)
        if container == "unknown":
            raise RuntimeError(f"unknown PCAP container signature: {path}")
        rows.append(
            {
                "dataset": "ToN-IoT",
                "source_file": name,
                "absolute_path": str(path),
                "role": role,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "container_from_magic": container,
                "extension_used_to_infer_container": False,
                "model_use": role != "reserved_internal_report_no_model_use",
                "raw_label_column_read": False,
            }
        )
    manifest = out / "ckbu_ton_raw_pcap_pilot_manifest.csv"
    write_csv(manifest, rows)
    dump_json(
        out / "ckbu_ton_raw_pcap_pilot_ready.json",
        {
            "status": "CKBU_TON_RAW_PCAP_PILOT_READY",
            "files": len(rows),
            "bytes": sum(row["bytes"] for row in rows),
            "manifest_sha256": sha256_file(manifest),
            "fit_files": [row["source_file"] for row in rows if row["role"].endswith("fit")],
            "select_files": [
                row["source_file"] for row in rows if row["role"].endswith("select")
            ],
            "reserved_files": [
                row["source_file"]
                for row in rows
                if row["role"] == "reserved_internal_report_no_model_use"
            ],
            "raw_label_column_read": False,
            "same_feature_schema_as_gotham": True,
            "feature_schema": FEATURE_NAMES,
        },
    )


def zeek_selected_rows(path: Path, indices: set[int]) -> dict[int, dict[str, str]]:
    fields: list[str] | None = None
    result: dict[int, dict[str, str]] = {}
    data_index = 0
    with Path(path).open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for line in handle:
            if line.startswith("#fields"):
                fields = line.rstrip("\r\n").split("\t")[1:]
                continue
            if not line or line.startswith("#"):
                continue
            if fields is None:
                raise RuntimeError(f"Zeek #fields header missing: {path}")
            if data_index in indices:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) != len(fields):
                    raise RuntimeError(f"Zeek row width drift: {path}:{data_index}")
                result[data_index] = dict(zip(fields, parts))
                if len(result) == len(indices):
                    break
            data_index += 1
    if set(result) != indices:
        raise RuntimeError(f"missing selected Zeek rows: {path}: {sorted(indices-set(result))[:8]}")
    return result


def ckbt_key_hash(
    ts: Any, src: Any, src_port: Any, dst: Any, dst_port: Any, proto: Any
) -> str:
    parts = (
        math.floor(float(ts)),
        str(src).strip(),
        str(normalize_port(src_port)),
        str(dst).strip(),
        str(normalize_port(dst_port)),
        str(proto).strip().lower(),
    )
    return hashlib.sha256("\x1f".join(str(part) for part in parts).encode("utf-8")).hexdigest()


@dataclass
class TonConnectionTarget:
    record_id: str
    role: str
    pair_id: str
    mechanism_family: str
    start: float
    stop: float
    src: str
    dst: str
    src_port: int
    dst_port: int
    proto: str
    matched_feature: np.ndarray | None = None
    matched_time: float = math.nan
    matched_position: int = -1
    src_local_id: int = -1
    dst_local_id: int = -1

    @property
    def direct_key(self) -> tuple[str, str, int, str, int]:
        return self.proto, self.src, self.src_port, self.dst, self.dst_port

    @property
    def reverse_key(self) -> tuple[str, str, int, str, int]:
        return self.proto, self.dst, self.dst_port, self.src, self.src_port


def load_ton_connection_targets(
    candidate_manifest: Path, extracted_root: Path
) -> dict[str, list[TonConnectionTarget]]:
    frame = pd.read_csv(Path(candidate_manifest), dtype=str, keep_default_na=False)
    frame = frame.loc[frame["pair_id"].isin(TON_PAIR_TO_PCAP)].copy()
    if len(frame) != 4_000 or set(frame["role"]) != {"aux_process_fit"}:
        raise RuntimeError(f"unexpected ToN raw-fit candidate scope: {len(frame)} {set(frame['role'])}")
    result: dict[str, list[TonConnectionTarget]] = {}
    for pair_id, part in frame.groupby("pair_id", sort=True):
        conn_rel = set(part["conn_relative_path"].astype(str))
        if len(conn_rel) != 1:
            raise RuntimeError(f"multiple conn sources in ToN pair: {pair_id}")
        conn_path = Path(extracted_root) / next(iter(conn_rel))
        indices = set(pd.to_numeric(part["conn_line_index"], errors="raise").astype(int))
        rows = zeek_selected_rows(conn_path, indices)
        targets = []
        for item in part.itertuples(index=False):
            line_index = int(item.conn_line_index)
            raw = rows[line_index]
            digest = ckbt_key_hash(
                raw["ts"],
                raw["id.orig_h"],
                raw["id.orig_p"],
                raw["id.resp_h"],
                raw["id.resp_p"],
                raw["proto"],
            )
            if digest != str(item.key_sha256):
                raise RuntimeError(f"CKBT selected Zeek row hash drift: {item.record_id}")
            start = float(raw["ts"])
            duration_text = str(raw.get("duration", ""))
            duration = 0.05 if duration_text in {"", "-"} else max(0.0, float(duration_text))
            targets.append(
                TonConnectionTarget(
                    record_id=str(item.record_id),
                    role=str(item.role),
                    pair_id=str(pair_id),
                    mechanism_family=str(item.mechanism_family),
                    start=start,
                    stop=start + duration,
                    src=str(raw["id.orig_h"]),
                    dst=str(raw["id.resp_h"]),
                    src_port=normalize_port(raw["id.orig_p"]),
                    dst_port=normalize_port(raw["id.resp_p"]),
                    proto=str(raw["proto"]).lower(),
                )
            )
        result[TON_PAIR_TO_PCAP[str(pair_id)]] = targets
    if set(result) != set(TON_PAIR_TO_PCAP.values()):
        raise RuntimeError(f"ToN raw-fit PCAP mapping incomplete: {sorted(result)}")
    return result


def event_connection_keys(event: PacketEvent) -> tuple[tuple[str, str, int, str, int], ...]:
    proto = "tcp" if event.is_tcp else ("udp" if event.is_udp else str(event.ip_proto))
    direct = (proto, event.src, event.src_port, event.dst, event.dst_port)
    reverse = (proto, event.dst, event.dst_port, event.src, event.src_port)
    return direct, reverse


def process_ton_attack_capture(
    rows: Iterable[dict[str, str]], member: str, targets: list[TonConnectionTarget]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key: defaultdict[tuple[str, str, int, str, int], list[TonConnectionTarget]] = defaultdict(list)
    for target in targets:
        by_key[target.direct_key].append(target)
        by_key[target.reverse_key].append(target)
    builder = CausalFeatureBuilder()
    events = 0
    for position, row in enumerate(rows):
        event = event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        feature = builder.emit(event)
        src_id, dst_id = builder.update(event)
        candidates: dict[str, TonConnectionTarget] = {}
        for key in event_connection_keys(event):
            for target in by_key.get(key, []):
                candidates[target.record_id] = target
        for target in candidates.values():
            if target.start - 0.01 <= event.timestamp <= target.stop + 0.01:
                # The last observed prefix at/before the legal completion lower
                # bound is retained.  Its feature availability is this packet's
                # timestamp, never the later Zeek log-emission time.
                if not math.isfinite(target.matched_time) or event.timestamp >= target.matched_time:
                    target.matched_feature = feature.copy()
                    target.matched_time = event.timestamp
                    target.matched_position = position
                    target.src_local_id = src_id
                    target.dst_local_id = dst_id
        events += 1
    missing = [target.record_id for target in targets if target.matched_feature is None]
    if missing:
        raise RuntimeError(f"ToN selected connection PCAP alignment incomplete: {missing[:8]}")
    positions = [int(target.matched_position) for target in targets]
    if len(set(positions)) != len(positions):
        duplicates = [value for value, count in Counter(positions).items() if count > 1]
        raise RuntimeError(
            "multiple ToN connection targets collapsed onto one packet event: "
            f"{duplicates[:8]}"
        )
    selected = [
        {
            "record_id": target.record_id,
            "role": target.role,
            "source_file": member,
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
        "raw_source_path": member,
        "decoded_events": events,
        "selected_attack_connections": len(selected),
        "target_alignment_complete": True,
        "target_event_positions_unique": True,
        "source_local_nodes": len(builder.nodes),
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "explicit_zeek_log_emission_time_used": False,
        "raw_label_column_read": False,
    }


def process_ton_normal_capture(
    rows: Iterable[dict[str, str]], member: str, role: str, budget: int, seed: int
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    builder = CausalFeatureBuilder()
    rng = np.random.default_rng(int(seed))
    reservoir: list[dict[str, Any]] = []
    events = 0
    for position, row in enumerate(rows):
        event = event_from_tshark(row)
        if not math.isfinite(event.timestamp):
            continue
        feature = builder.emit(event)
        src_id, dst_id = builder.update(event)
        item = {
            "record_id": f"ton_normal:{Path(member).stem}:{position}",
            "role": role,
            "source_file": member,
            "mechanism_family": "benign",
            "label": 0,
            "feature_available_time_epoch": event.timestamp,
            "target_event_position_within_capture": position,
            "src_local_id": src_id,
            "dst_local_id": dst_id,
            "feature": feature.copy(),
        }
        events += 1
        if len(reservoir) < budget:
            reservoir.append(item)
        else:
            replacement = int(rng.integers(0, events))
            if replacement < budget:
                reservoir[replacement] = item
    if len(reservoir) != budget:
        raise RuntimeError(f"short ToN normal capture: {member}: {len(reservoir)}/{budget}")
    reservoir.sort(key=lambda item: int(item["target_event_position_within_capture"]))
    return reservoir, {
        "raw_source_path": member,
        "decoded_events": events,
        "reservoir_rows": len(reservoir),
        "reservoir_seed": int(seed),
        "source_local_nodes": len(builder.nodes),
        "score_before_update": True,
        "feature_available_time_recorded": True,
        "raw_label_column_read": False,
    }


def materialize_ton_pilot(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    pilot = Path(args.ton_pilot_dir)
    connection_targets = load_ton_connection_targets(
        Path(args.ckbt_candidate_manifest), Path(args.ton_extracted_root)
    )
    selected: list[dict[str, Any]] = []
    audits = []
    for name, role in TON_PILOT_FILES.items():
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
        path = pilot / name
        rows = iter_tshark_rows(args.tshark, pcap_path=path)
        if name in connection_targets:
            values, audit = process_ton_attack_capture(rows, name, connection_targets[name])
        elif role in {"aux_normal_fit", "aux_normal_select"}:
            values, audit = process_ton_normal_capture(
                rows, name, role, int(args.ton_normal_budget), int(args.seed)
            )
        else:
            raise RuntimeError(f"unhandled ToN pilot role: {name}: {role}")
        selected.extend(values)
        audits.append({**audit, "role": role, "model_rows": len(values)})
    features = np.vstack([row.pop("feature") for row in selected]).astype(np.float32)
    npz = out / "ckbu_ton_raw_pcap_pilot_causal_samples.npz"
    np.savez_compressed(
        npz,
        record_id=np.asarray([row["record_id"] for row in selected]),
        role=np.asarray([row["role"] for row in selected]),
        source_file=np.asarray([row["source_file"] for row in selected]),
        mechanism_family=np.asarray([row["mechanism_family"] for row in selected]),
        label=np.asarray([row["label"] for row in selected], dtype=np.int8),
        feature_available_time_epoch=np.asarray(
            [row["feature_available_time_epoch"] for row in selected], dtype=np.float64
        ),
        target_event_position_within_capture=np.asarray(
            [row["target_event_position_within_capture"] for row in selected], dtype=np.int64
        ),
        src_local_id=np.asarray([row["src_local_id"] for row in selected], dtype=np.int32),
        dst_local_id=np.asarray([row["dst_local_id"] for row in selected], dtype=np.int32),
        causal_features=features,
        feature_names=np.asarray(FEATURE_NAMES),
    )
    write_csv(out / "ckbu_ton_raw_pcap_materialization_audit.csv", audits)
    roles = defaultdict(int)
    for row in selected:
        roles[str(row["role"])] += 1
    dump_json(
        out / "ckbu_ton_raw_pcap_pilot_causal_ready.json",
        {
            "status": "CKBU_TON_RAW_PCAP_CAUSAL_READY",
            "rows": len(selected),
            "roles": dict(sorted(roles.items())),
            "feature_schema": FEATURE_NAMES,
            "cache_npz": str(npz),
            "cache_sha256": sha256_file(npz),
            "same_feature_schema_as_gotham": True,
            "score_before_update": True,
            "feature_available_time_recorded": True,
            "fit_select_source_files_disjoint": True,
            "reserved_injection_mitm_model_rows": 0,
            "raw_label_column_read": False,
        },
    )


def synthetic_event(
    timestamp: float,
    src: str,
    dst: str,
    *,
    stream: int = 1,
    syn: bool = False,
    ack: bool = False,
    rst: bool = False,
) -> PacketEvent:
    return PacketEvent(
        frame_number=int(timestamp * 1000),
        timestamp=timestamp,
        frame_len=60,
        src=src,
        dst=dst,
        ip_version=4,
        ip_proto=6,
        src_port=50000,
        dst_port=23,
        tcp_syn=syn,
        tcp_ack=ack,
        tcp_rst=rst,
        tcp_fin=False,
        tcp_stream=stream,
        udp_stream=-1,
        tcp_stream_pnum=1,
        tcp_time_relative=0.0,
        tcp_time_delta=0.0,
        tcp_connection_syn=syn,
        retransmission=False,
        lost_segment=False,
    )


def unit_tests() -> dict[str, Any]:
    if "label" in TSHARK_FIELDS or "type" in TSHARK_FIELDS:
        raise RuntimeError("label entered TShark schema")
    if set(GOTHAM_ALIGNMENT_FIELDS) & {"label", "type", "attack"}:
        raise RuntimeError("label entered Gotham alignment schema")
    if len(FEATURE_NAMES) != len(set(FEATURE_NAMES)):
        raise RuntimeError("duplicate causal feature names")

    past = [
        synthetic_event(1.0, "a", "b", syn=True),
        synthetic_event(1.1, "b", "a", ack=True),
        synthetic_event(2.0, "a", "c", syn=True, stream=2),
    ]
    future_a = synthetic_event(3.0, "c", "a", rst=True, stream=2)
    future_b = synthetic_event(30.0, "x", "y", rst=True, stream=9)
    first = CausalFeatureBuilder()
    xa, _, _, _ = first.transform(past + [future_a])
    second = CausalFeatureBuilder()
    xb, _, _, _ = second.transform(past + [future_b])
    if not np.array_equal(xa[: len(past)], xb[: len(past)]):
        raise RuntimeError("future event changed a past feature row")

    fresh = CausalFeatureBuilder()
    cold = fresh.emit(past[0])
    fresh.update(past[0])
    warm = fresh.emit(past[0])
    reset = CausalFeatureBuilder().emit(past[0])
    if not np.array_equal(cold, reset) or np.array_equal(cold, warm):
        raise RuntimeError("source reset or score-before-update contract failed")

    names = [
        "raw/benign/iotsim-combined-cycle-1_0-0_to_x.pcap",
        "raw/benign/iotsim-combined-cycle-10_0-0_to_x.pcap",
        "raw/malicious/a/iotsim-combined-cycle-1_0-0_to_x.pcap",
    ]
    matches = exact_pcap_members(names, "processed/iotsim-combined-cycle-1.csv")
    if len(matches) != 2 or any("cycle-10_" in value for value in matches):
        raise RuntimeError("exact source-stem boundary test failed")

    target = TargetFingerprint(
        "processed/a.csv", 7, 10.0, 60, "a", "b", 6, 50000, 23
    )
    matcher = TargetMatcher([target])
    event = synthetic_event(10.000001, "a", "b", syn=True)
    feature = CausalFeatureBuilder().emit(event)
    matcher.observe("a.pcap", 3, event, feature, 0, 1)
    if matcher.finalize()[0]["recorded_index"] != 7:
        raise RuntimeError("target fingerprint alignment test failed")

    command = tshark_command("tshark", "input.pcap")
    if command.count("-e") != len(TSHARK_FIELDS) or "label" in command:
        raise RuntimeError("TShark command schema test failed")

    # raw51_observable_v1 mask loader gates (ledger section 11).
    with tempfile.TemporaryDirectory() as raw51_temp:
        mask_path = Path(raw51_temp) / "mask.csv"
        body = "source_group,recorded_index\n" + "".join(
            f"{RAW51_MASK_SOURCE},{index}\n" for index in range(RAW51_MASK_ROWS)
        )
        mask_path.write_bytes(body.encode("utf-8"))
        good_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
        loaded = load_raw51_mask(mask_path, good_sha)
        if len(loaded[RAW51_MASK_SOURCE]) != RAW51_MASK_ROWS:
            raise RuntimeError("raw51 mask loader row count failed")
        for corrupted, expected_error in (
            (body, "0" * 64),
            (body + f"other.csv,1\n", good_sha),
            (body.replace(f"{RAW51_MASK_SOURCE},0\n", ""), good_sha),
        ):
            mask_path.write_bytes(corrupted.encode("utf-8"))
            digest = (
                expected_error
                if expected_error != good_sha
                else hashlib.sha256(corrupted.encode("utf-8")).hexdigest()
            )
            try:
                load_raw51_mask(mask_path, digest)
            except RuntimeError:
                pass
            else:
                raise RuntimeError("raw51 mask loader accepted invalid input")
    return {
        "status": "CKBU_UNIT_PASS",
        "feature_schema_dim": len(FEATURE_NAMES),
        "raw51_mask_loader_gates_tested": True,
        "future_invariance": True,
        "score_before_update": True,
        "fresh_source_reset": True,
        "exact_source_stem_boundary": True,
        "target_fingerprint_tolerance_us": 2,
        "raw_label_column_read": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=(
            "unit",
            "plan-gotham",
            "materialize-gotham-source",
            "aggregate-gotham",
            "plan-auxiliary",
            "materialize-auxiliary-source",
            "aggregate-auxiliary",
            "plan-ton-pilot",
            "materialize-ton-pilot",
        ),
        default="unit",
    )
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--gotham-zip", type=Path, default=GOTHAM_ZIP)
    parser.add_argument("--targets", action="append", default=[])
    parser.add_argument("--source-plan", type=Path, default=OUT / "ckbu_gotham_source_plan.csv")
    parser.add_argument("--source-index", type=int, default=-1)
    parser.add_argument("--cache-dir", type=Path, default=OUT / "gotham_causal_cache")
    parser.add_argument("--tshark", default="tshark")
    parser.add_argument("--raw51-mask", default=None)
    parser.add_argument("--raw51-mask-sha256", default=None)
    parser.add_argument("--alignment-tolerance-us", type=int, default=2)
    parser.add_argument("--aux-manifest", type=Path)
    parser.add_argument("--ton-pilot-dir", type=Path)
    parser.add_argument("--ton-extracted-root", type=Path)
    parser.add_argument("--ckbt-candidate-manifest", type=Path)
    parser.add_argument("--ton-normal-budget", type=int, default=4_000)
    parser.add_argument("--seed", type=int, default=27)
    args = parser.parse_args()
    if not args.targets:
        args.targets = [str(DEFAULT_TARGETS)]
    if args.mode == "unit":
        print(json.dumps(unit_tests(), indent=2, sort_keys=True))
    elif args.mode == "plan-gotham":
        plan_gotham(args)
    elif args.mode == "materialize-gotham-source":
        materialize_gotham_source(args)
    elif args.mode == "aggregate-gotham":
        aggregate_gotham(args)
    elif args.mode == "plan-auxiliary":
        if args.aux_manifest is None:
            raise RuntimeError("--aux-manifest is required")
        plan_auxiliary(args)
    elif args.mode == "materialize-auxiliary-source":
        materialize_auxiliary_source(args)
    elif args.mode == "aggregate-auxiliary":
        aggregate_auxiliary(args)
    elif args.mode == "plan-ton-pilot":
        if args.ton_pilot_dir is None:
            raise RuntimeError("--ton-pilot-dir is required")
        plan_ton_pilot(args)
    elif args.mode == "materialize-ton-pilot":
        required = (args.ton_pilot_dir, args.ton_extracted_root, args.ckbt_candidate_manifest)
        if any(value is None for value in required):
            raise RuntimeError(
                "--ton-pilot-dir, --ton-extracted-root and --ckbt-candidate-manifest are required"
            )
        materialize_ton_pilot(args)
    else:  # pragma: no cover
        raise AssertionError(args.mode)


if __name__ == "__main__":
    main()
