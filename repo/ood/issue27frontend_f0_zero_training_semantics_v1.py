#!/usr/bin/env python3
"""Deterministic H1-H4 semantic-context prototype for Frontend-F0.

This module is deliberately limited to the synthetic ZT-1 contract surface.
It contains no real-PCAP entry point and cannot train, score, or open model
artifacts.  A separately authorized runner may later import this engine.
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


CONTRACT_PATH = "runs/mainline_docs/frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md"
CONTRACT_SHA256 = "532bb52e4d03c0321f1e874cc4bd7a49fca3391943c0dd23a1968fd69ac3c0ee"
SEMANTICS_VERSION = "frontend-f0-zt-v1"

MAX_EVENTS = 256
MAX_SPAN_SECONDS = 300.0
IDLE_GAP_SECONDS = 60.0

MISSING_REASONS = (
    "DECODER_CORRUPT_EVENT",
    "NONFINITE_EVENT_TIMESTAMP",
    "REQUIRED_PACKET_ORDINAL_ABSENT",
    "TARGET_NOT_REACHED_AT_EXACT_CUTOFF",
    "CONTEXT_CONSTRUCTION_INVARIANT_FAILURE",
)

FORBIDDEN_CONSTRUCTION_ROLES = frozenset(
    {"label", "report", "final", "model", "score", "representation", "weights"}
)

ALLOWED_DECODER_FIELDS = frozenset(
    {
        "source_id",
        "member_id",
        "packet_ordinal",
        "timestamp",
        "link_type",
        "ethertype",
        "ip_version",
        "ip_protocol",
        "src_endpoint",
        "dst_endpoint",
        "src_port",
        "dst_port",
        "decoder_corrupt",
        "field_presence_mask",
        "target_uid",
    }
)


class SemanticContractFailure(RuntimeError):
    """A frozen identity, conservation, or semantic invariant failed."""


class ForbiddenRoleAccess(SemanticContractFailure):
    """A role forbidden during semantic construction was requested."""


@dataclass(frozen=True)
class Event:
    source_id: str
    member_id: str
    packet_ordinal: Optional[int]
    timestamp: float
    link_type: str = "ETHERNET"
    ethertype: Optional[int] = 0x0800
    ip_version: Optional[int] = 4
    ip_protocol: Optional[int] = 6
    src_endpoint: Optional[str] = "a"
    dst_endpoint: Optional[str] = "b"
    src_port: Optional[int] = 1000
    dst_port: Optional[int] = 2000
    decoder_corrupt: bool = False
    field_presence_mask: str = "default"
    target_uid: Optional[str] = None


@dataclass(frozen=True)
class TargetSpec:
    uid: str
    source_id: str
    member_id: str
    packet_ordinal: int


@dataclass
class AccessAudit:
    label_columns_read_during_construction: int = 0
    report_opened: int = 0
    final_opened: int = 0
    model_opened: int = 0
    score_opened: int = 0
    representation_opened: int = 0

    def request(self, role: str) -> None:
        normalized = str(role).strip().lower()
        if normalized in FORBIDDEN_CONSTRUCTION_ROLES:
            field = {
                "label": "label_columns_read_during_construction",
                "report": "report_opened",
                "final": "final_opened",
                "model": "model_opened",
                "weights": "model_opened",
                "score": "score_opened",
                "representation": "representation_opened",
            }[normalized]
            setattr(self, field, getattr(self, field) + 1)
            raise ForbiddenRoleAccess("forbidden construction role requested: %s" % normalized)
        raise SemanticContractFailure("unregistered construction role: %s" % normalized)

    def assert_clean(self) -> None:
        if any(asdict(self).values()):
            raise SemanticContractFailure("construction boundary audit is nonzero")


@dataclass(frozen=True)
class Route:
    tier: str
    base_key: Tuple[object, ...]
    orientation: Tuple[object, ...]
    direction: str
    protocol_class: Tuple[object, ...]
    ports_present: bool


@dataclass
class ContextState:
    tier: str
    base_key: Tuple[object, ...]
    orientation: Tuple[object, ...]
    protocol_class: Tuple[object, ...]
    epoch: int
    first_surrogate: float
    last_surrogate: float
    event_count: int
    regression_count: int


@dataclass(frozen=True)
class SemanticRow:
    uid: str
    source_id: str
    member_id: str
    target_packet_ordinal: int
    semantic_finite: bool
    semantic_missing_reason: str
    context_tier: str
    causal_context_id: str
    context_epoch: Optional[int]
    context_event_count: Optional[int]
    context_surrogate_span_seconds: Optional[float]
    direction_code: str
    link_type: str
    ip_version_or_none: Optional[int]
    ip_protocol_or_none: Optional[int]
    transport_ports_present: bool
    timestamp_regression_count_in_context: Optional[int]
    raw_endpoint_values_emitted: bool
    label_columns_read_during_construction: int


def sha256_file(path: Path, block_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            block = stream.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def verify_contract(repo_root: Path) -> str:
    path = repo_root / CONTRACT_PATH
    actual = sha256_file(path)
    if actual != CONTRACT_SHA256:
        raise SemanticContractFailure("frozen zero-training contract SHA drift")
    return actual


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def event_from_mapping(row: Mapping[str, object]) -> Event:
    """Construct an event without ever requesting payload bytes.

    Extra decoder fields are tolerated because mature decoders commonly expose
    more audit fields.  Only the declared allowlist is requested here.
    """
    values: Dict[str, object] = {}
    for field in ALLOWED_DECODER_FIELDS:
        if field in row:
            values[field] = row[field]
    required = {"source_id", "member_id", "timestamp"}
    if not required.issubset(values):
        raise SemanticContractFailure("decoder row lacks required semantic fields")
    return Event(**values)  # type: ignore[arg-type]


class EndpointTokens:
    """Past-only, per-member first-seen endpoint tokens."""

    def __init__(self) -> None:
        self._tokens: Dict[str, int] = {}

    def token(self, endpoint: str) -> int:
        value = str(endpoint)
        if value not in self._tokens:
            self._tokens[value] = len(self._tokens)
        return self._tokens[value]


def _optional_int(value: object) -> Optional[int]:
    if value is None or value == "":
        return None
    return int(value)


def _endpoint_pair(event: Event, tokens: EndpointTokens) -> Optional[Tuple[int, int]]:
    if event.src_endpoint in {None, ""} or event.dst_endpoint in {None, ""}:
        return None
    return tokens.token(str(event.src_endpoint)), tokens.token(str(event.dst_endpoint))


def _ordered_pair(left: Tuple[object, ...], right: Tuple[object, ...]) -> Tuple[Tuple[object, ...], Tuple[object, ...]]:
    return (left, right) if left <= right else (right, left)


def classify_route(event: Event, tokens: EndpointTokens) -> Route:
    pair = _endpoint_pair(event, tokens)
    version = _optional_int(event.ip_version)
    protocol = _optional_int(event.ip_protocol)
    is_ip = version in {4, 6} and protocol is not None
    ports_present = event.src_port is not None and event.dst_port is not None

    if is_ip and protocol in {6, 17} and pair is not None and ports_present:
        left = (pair[0], int(event.src_port))
        right = (pair[1], int(event.dst_port))
        canonical = _ordered_pair(left, right)
        return Route(
            tier="H1",
            base_key=(version, protocol, canonical),
            orientation=(left, right),
            direction="A_TO_B",
            protocol_class=(version, protocol),
            ports_present=True,
        )

    if is_ip and pair is not None:
        left = (pair[0],)
        right = (pair[1],)
        canonical = _ordered_pair(left, right)
        return Route(
            tier="H2",
            base_key=(version, protocol, canonical),
            orientation=(left, right),
            direction="A_TO_B",
            protocol_class=(version, protocol),
            ports_present=ports_present,
        )

    if not is_ip and pair is not None:
        left = (pair[0],)
        right = (pair[1],)
        canonical = _ordered_pair(left, right)
        ethertype = _optional_int(event.ethertype)
        return Route(
            tier="H3",
            base_key=(str(event.link_type), ethertype, canonical),
            orientation=(left, right),
            direction="A_TO_B",
            protocol_class=(str(event.link_type), ethertype),
            ports_present=ports_present,
        )

    ethertype = _optional_int(event.ethertype)
    base_class = (
        str(event.link_type),
        ethertype,
        version,
        protocol,
        str(event.field_presence_mask),
    )
    return Route(
        tier="H4",
        base_key=base_class,
        orientation=(),
        direction="UNKNOWN",
        protocol_class=base_class,
        ports_present=ports_present,
    )


def _direction(route: Route, state: ContextState) -> str:
    if route.tier == "H4":
        return "UNKNOWN"
    if route.orientation == state.orientation:
        return "A_TO_B"
    if route.orientation == tuple(reversed(state.orientation)):
        return "B_TO_A"
    raise SemanticContractFailure("endpoint orientation drift within base context")


def _context_id(source_id: str, member_id: str, state: ContextState) -> str:
    identity = {
        "version": SEMANTICS_VERSION,
        "source_id": str(source_id),
        "member_id": str(member_id),
        "tier": state.tier,
        "orientation_tokens": state.orientation,
        "protocol_class": state.protocol_class,
        "epoch": state.epoch,
    }
    return hashlib.sha256(canonical_json_bytes(identity)).hexdigest()


def _event_missing_reason(event: Event) -> str:
    if event.decoder_corrupt:
        return "DECODER_CORRUPT_EVENT"
    if event.packet_ordinal is None:
        return "REQUIRED_PACKET_ORDINAL_ABSENT"
    if not math.isfinite(float(event.timestamp)):
        return "NONFINITE_EVENT_TIMESTAMP"
    return ""


def _missing_row(target: TargetSpec, event: Optional[Event], reason: str, audit: AccessAudit) -> SemanticRow:
    if reason not in MISSING_REASONS:
        raise SemanticContractFailure("unregistered missing reason: %s" % reason)
    return SemanticRow(
        uid=target.uid,
        source_id=target.source_id,
        member_id=target.member_id,
        target_packet_ordinal=target.packet_ordinal,
        semantic_finite=False,
        semantic_missing_reason=reason,
        context_tier="",
        causal_context_id="",
        context_epoch=None,
        context_event_count=None,
        context_surrogate_span_seconds=None,
        direction_code="UNKNOWN",
        link_type="" if event is None else str(event.link_type),
        ip_version_or_none=None if event is None else _optional_int(event.ip_version),
        ip_protocol_or_none=None if event is None else _optional_int(event.ip_protocol),
        transport_ports_present=False if event is None else event.src_port is not None and event.dst_port is not None,
        timestamp_regression_count_in_context=None,
        raw_endpoint_values_emitted=False,
        label_columns_read_during_construction=audit.label_columns_read_during_construction,
    )


def _finite_row(target: TargetSpec, event: Event, route: Route, state: ContextState, audit: AccessAudit) -> SemanticRow:
    span = state.last_surrogate - state.first_surrogate
    if state.event_count > MAX_EVENTS or span > MAX_SPAN_SECONDS:
        raise SemanticContractFailure("context bounds violated at materialization")
    return SemanticRow(
        uid=target.uid,
        source_id=target.source_id,
        member_id=target.member_id,
        target_packet_ordinal=target.packet_ordinal,
        semantic_finite=True,
        semantic_missing_reason="",
        context_tier=state.tier,
        causal_context_id=_context_id(target.source_id, target.member_id, state),
        context_epoch=state.epoch,
        context_event_count=state.event_count,
        context_surrogate_span_seconds=float(span),
        direction_code=_direction(route, state),
        link_type=str(event.link_type),
        ip_version_or_none=_optional_int(event.ip_version),
        ip_protocol_or_none=_optional_int(event.ip_protocol),
        transport_ports_present=route.ports_present,
        timestamp_regression_count_in_context=state.regression_count,
        raw_endpoint_values_emitted=False,
        label_columns_read_during_construction=audit.label_columns_read_during_construction,
    )


class SemanticPrototype:
    """Two-pass, member-isolated synthetic semantic materializer."""

    def __init__(self, audit: Optional[AccessAudit] = None) -> None:
        self.audit = audit if audit is not None else AccessAudit()
        self.last_state_count = 0

    @staticmethod
    def _validate_member(events: Sequence[Event], targets: Sequence[TargetSpec]) -> Tuple[str, str]:
        if not targets:
            raise SemanticContractFailure("member has no frozen targets")
        source = targets[0].source_id
        member = targets[0].member_id
        if any(target.source_id != source or target.member_id != member for target in targets):
            raise SemanticContractFailure("target member/source isolation failure")
        seen_uids: Set[str] = set()
        seen_positions: Set[int] = set()
        for target in targets:
            if target.uid in seen_uids or target.packet_ordinal in seen_positions:
                raise SemanticContractFailure("duplicate UID or target ordinal")
            seen_uids.add(target.uid)
            seen_positions.add(target.packet_ordinal)
        expected_at_position = {target.packet_ordinal: target.uid for target in targets}
        for event in events:
            if event.source_id != source or event.member_id != member:
                raise SemanticContractFailure("event crossed source/member boundary")
            if event.target_uid is not None:
                if event.target_uid not in seen_uids:
                    raise SemanticContractFailure("unregistered target UID in event stream")
                if event.packet_ordinal is None or expected_at_position.get(int(event.packet_ordinal)) != event.target_uid:
                    raise SemanticContractFailure("target UID marker is not at its frozen ordinal")
        return source, member

    @staticmethod
    def _discover(events: Sequence[Event], targets_by_position: Mapping[int, TargetSpec]) -> Dict[Tuple[object, ...], int]:
        tokens = EndpointTokens()
        last_target: Dict[Tuple[object, ...], int] = {}
        for index, event in enumerate(events):
            if event.packet_ordinal is not None and int(event.packet_ordinal) != index:
                raise SemanticContractFailure("packet ordinal is absent or non-causal")
            route = classify_route(event, tokens)
            target = targets_by_position.get(index)
            if target is not None and not _event_missing_reason(event):
                identity = (route.tier, route.base_key)
                last_target[identity] = max(index, last_target.get(identity, -1))
        return last_target

    @staticmethod
    def _start_state(route: Route, epoch: int, timestamp: float) -> ContextState:
        return ContextState(
            tier=route.tier,
            base_key=route.base_key,
            orientation=route.orientation,
            protocol_class=route.protocol_class,
            epoch=epoch,
            first_surrogate=timestamp,
            last_surrogate=timestamp,
            event_count=1,
            regression_count=0,
        )

    @staticmethod
    def _append_or_split(route: Route, state: Optional[ContextState], next_epoch: int, timestamp: float) -> Tuple[ContextState, int]:
        if state is None:
            return SemanticPrototype._start_state(route, next_epoch, timestamp), next_epoch + 1
        surrogate = max(state.last_surrogate, timestamp)
        idle = surrogate - state.last_surrogate
        span = surrogate - state.first_surrogate
        split = idle > IDLE_GAP_SECONDS or span > MAX_SPAN_SECONDS or state.event_count + 1 > MAX_EVENTS
        if split:
            return SemanticPrototype._start_state(route, next_epoch, timestamp), next_epoch + 1
        if timestamp < state.last_surrogate:
            state.regression_count += 1
        state.last_surrogate = surrogate
        state.event_count += 1
        return state, next_epoch

    def process_member(self, events: Sequence[Event], targets: Sequence[TargetSpec]) -> List[SemanticRow]:
        source, member = self._validate_member(events, targets)
        targets_by_position = {target.packet_ordinal: target for target in targets}
        target_uids = {target.uid for target in targets}
        last_target = self._discover(events, targets_by_position)

        tokens = EndpointTokens()
        active: MutableMapping[Tuple[object, ...], ContextState] = {}
        next_epoch: Dict[Tuple[object, ...], int] = {}
        closed: Set[Tuple[object, ...]] = set()
        h4_current: Optional[Tuple[object, ...]] = None
        rows: Dict[str, SemanticRow] = {}

        for index, event in enumerate(events):
            route = classify_route(event, tokens)
            identity = (route.tier, route.base_key)
            target = targets_by_position.get(index)
            missing_reason = _event_missing_reason(event)

            if route.tier == "H4" and h4_current is not None and h4_current != identity:
                active.pop(h4_current, None)
            if route.tier == "H4":
                h4_current = identity

            is_active = identity in last_target and index <= last_target[identity] and identity not in closed
            state: Optional[ContextState] = active.get(identity)
            if is_active and not missing_reason:
                state, epoch_value = self._append_or_split(
                    route,
                    state,
                    next_epoch.get(identity, 0),
                    float(event.timestamp),
                )
                next_epoch[identity] = epoch_value
                active[identity] = state

            if target is not None:
                if event.target_uid is not None and event.target_uid != target.uid:
                    raise SemanticContractFailure("target UID/ordinal identity drift")
                if target.uid in rows:
                    raise SemanticContractFailure("duplicate target row materialization")
                if missing_reason:
                    rows[target.uid] = _missing_row(target, event, missing_reason, self.audit)
                elif not is_active or state is None:
                    rows[target.uid] = _missing_row(
                        target, event, "CONTEXT_CONSTRUCTION_INVARIANT_FAILURE", self.audit
                    )
                else:
                    rows[target.uid] = _finite_row(target, event, route, state, self.audit)

            if identity in last_target and index == last_target[identity]:
                active.pop(identity, None)
                closed.add(identity)
                if h4_current == identity:
                    h4_current = None

        for target in targets:
            if target.uid not in rows:
                rows[target.uid] = _missing_row(
                    target, None, "TARGET_NOT_REACHED_AT_EXACT_CUTOFF", self.audit
                )
        if set(rows) != target_uids:
            raise SemanticContractFailure("target UID conservation failure")
        if active:
            raise SemanticContractFailure("semantic state not empty after exact target cutoffs")
        self.last_state_count = len(active)
        self.audit.assert_clean()
        return [rows[target.uid] for target in sorted(targets, key=lambda value: (value.packet_ordinal, value.uid))]

    def materialize(
        self,
        events_by_member: Mapping[Tuple[str, str], Sequence[Event]],
        targets: Sequence[TargetSpec],
    ) -> List[SemanticRow]:
        grouped: Dict[Tuple[str, str], List[TargetSpec]] = {}
        for target in targets:
            grouped.setdefault((target.source_id, target.member_id), []).append(target)
        if set(grouped) - set(events_by_member):
            missing = set(grouped) - set(events_by_member)
            raise SemanticContractFailure("target members absent from event map: %s" % sorted(missing))
        output: List[SemanticRow] = []
        for identity in sorted(grouped):
            output.extend(self.process_member(list(events_by_member[identity]), grouped[identity]))
        uids = [row.uid for row in output]
        if len(uids) != len(set(uids)) or len(uids) != len(targets):
            raise SemanticContractFailure("global target conservation failure")
        return sorted(output, key=lambda row: row.uid)


def rows_as_dicts(rows: Iterable[SemanticRow]) -> List[Dict[str, object]]:
    return [asdict(row) for row in rows]


def canonical_rows_bytes(rows: Iterable[SemanticRow]) -> bytes:
    ordered = sorted(rows_as_dicts(rows), key=lambda row: str(row["uid"]))
    return b"".join(canonical_json_bytes(row) + b"\n" for row in ordered)


def atomic_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    temp = Path(raw)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temp), str(path))
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def write_synthetic_bundle(
    out_dir: Path,
    rows: Sequence[SemanticRow],
    terminal_state: str,
    engineering_failure: Optional[str] = None,
) -> Dict[str, str]:
    """Write only synthetic ZT-1 evidence and cover it with SHA256SUMS."""
    out_dir.mkdir(parents=True, exist_ok=True)
    verdict_path = out_dir / "zt_synthetic_verdict.json"
    if engineering_failure is not None:
        try:
            verdict_path.unlink()
        except FileNotFoundError:
            pass
        atomic_bytes(
            out_dir / "engineering_failure.json",
            canonical_json_bytes({"status": "ZT_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT", "detail": engineering_failure}) + b"\n",
        )
        return {}
    if terminal_state not in {
        "ZT_SEMANTICS_CONTRACT_FAILURE",
        "ZT_CAUSALITY_NO_GO",
        "ZT_CONTEXT_DEGENERACY_NO_GO",
        "ZT_SEMANTIC_COVERAGE_PASS",
    }:
        raise SemanticContractFailure("unregistered synthetic terminal state")
    status_path = out_dir / "zt_synthetic_status.jsonl"
    atomic_bytes(status_path, canonical_rows_bytes(rows))
    atomic_bytes(verdict_path, canonical_json_bytes({"status": terminal_state, "rows": len(rows)}) + b"\n")
    names = [status_path.name, verdict_path.name]
    sums = "".join("%s  %s\n" % (sha256_file(out_dir / name), name) for name in names)
    atomic_bytes(out_dir / "SHA256SUMS", sums.encode("utf-8"))
    return {name: sha256_file(out_dir / name) for name in names}


def assert_zero_training_source(source_path: Path) -> None:
    source = source_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(source_path), feature_version=(3, 9))
    forbidden_imports = ("torch", "sklearn", "xgboost", "lightgbm")
    forbidden_calls = {"fit", "partial_fit", "backward", "gradient_descent", "KMeans"}
    present: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            present.extend(name.name for name in node.names if name.name.startswith(forbidden_imports))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module.startswith(forbidden_imports):
                present.append(module)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                present.append(node.func.id)
            if isinstance(node.func, ast.Attribute) and node.func.attr in forbidden_calls:
                present.append(node.func.attr)
    if present:
        raise SemanticContractFailure("learning/tuning surface detected: %s" % present)
