#!/usr/bin/env python3
"""Authorized ZT-2 real-PCAP runner for the frozen zero-training semantics.

This runner is deliberately count-only.  It decodes the exact 30 reviewed
fit/select packet members, materializes one deterministic semantic-status row
per frozen terminal target, and only after exact UID conservation joins the
already-frozen role/device/family descriptors.  It never opens a model,
representation coordinate, score, report, FINAL member, or payload field.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, TextIO, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
STEP0B = ROOT / "runs/frontend_f0_step0b_implementation_preopen_20260829"
ENGINE_PATH = ROOT / "repo/ood/issue27frontend_f0_zero_training_semantics_v1.py"
ENGINE_SHA256 = "00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa"
CONTRACT_PATH = ROOT / "runs/mainline_docs/frontend_f0_controlled_zero_training_semantics_protocol_frozen_20260831.md"
CONTRACT_SHA256 = "532bb52e4d03c0321f1e874cc4bd7a49fca3391943c0dd23a1968fd69ac3c0ee"
TARGET_PATH = STAGE / "ckda_d1_fit_select_target_metadata.csv"
TARGET_SHA256 = "d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d"
AVAILABILITY_PATH = STAGE / "ckda_d1_fit_select_embeddings.npz"
AVAILABILITY_SHA256 = "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"
IDENTITY_PATH = STEP0B / "frontend_f0_step0b_packet_identity_attachment.csv"
IDENTITY_SHA256 = "5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c"
R0_PATH = STEP0B / "frontend_f0_step0b_r0_identity_audit.json"
R0_SHA256 = "41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11"
EXECUTION_TOKEN = "I_AUTHORIZE_ZT2_COUNT_ONLY_REAL_PCAP_SEMANTICS"
MIN_FREE_BYTES = 2 * 1024 * 1024 * 1024
EXPECTED_TARGETS = 25_467
EXPECTED_MEMBERS = 30
EXPECTED_OLD_MISSING = 11_640
EXPECTED_OLD_FINITE = 13_827

TSHARK_FIELDS = [
    "frame.number", "frame.time_epoch", "frame.encap_type", "frame.len",
    "eth.src", "eth.dst", "eth.type", "ip.src", "ip.dst", "ipv6.src", "ipv6.dst",
    "ip.proto", "ipv6.nxt", "tcp.srcport", "tcp.dstport", "udp.srcport", "udp.dstport",
    "sctp.srcport", "sctp.dstport", "icmp.type", "icmp.code", "icmpv6.type",
    "icmpv6.code", "gre.key",
]

STATUS_FIELDS = [
    "uid", "source_id", "member_id", "target_packet_ordinal", "semantic_finite",
    "semantic_missing_reason", "context_tier", "causal_context_id", "context_epoch",
    "context_event_count", "context_surrogate_span_seconds", "direction_code",
    "link_type", "ip_version_or_none", "ip_protocol_or_none", "transport_ports_present",
    "timestamp_regression_count_in_context", "raw_endpoint_values_emitted",
    "label_columns_read_during_construction",
]


class ZT2Failure(RuntimeError):
    pass


def sha256_file(path: Path, block_size: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            block = stream.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(raw, str(path))
    except BaseException:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass
        raise


def atomic_text(path: Path, text: str) -> None:
    atomic_bytes(path, text.encode("utf-8"))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str], compressed: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, raw = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    os.close(descriptor)
    try:
        opener = gzip.open if compressed else open
        with opener(raw, "wt", encoding="utf-8", newline="") as stream:  # type: ignore[arg-type]
            writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise", lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        os.replace(raw, str(path))
    except BaseException:
        try:
            os.unlink(raw)
        except FileNotFoundError:
            pass
        raise


def import_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise ZT2Failure("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_file(path: Path, expected: str, label: str) -> str:
    if not path.is_file():
        raise ZT2Failure("missing pinned %s: %s" % (label, path))
    actual = sha256_file(path)
    if actual != expected:
        raise ZT2Failure("%s SHA drift: %s != %s" % (label, actual, expected))
    return actual


def tshark_identity(executable: Path) -> Dict[str, object]:
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise ZT2Failure("TShark executable absent")
    result = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    value = result.stdout.strip()
    return {
        "executable_path": str(executable),
        "executable_bytes": executable.stat().st_size,
        "executable_sha256": sha256_file(executable),
        "version_output": value,
        "version_output_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def preflight(out_dir: Path, tshark: Path) -> Tuple[Any, pd.DataFrame, pd.DataFrame, Dict[str, object], Dict[str, str]]:
    pins = {
        "contract": verify_file(CONTRACT_PATH, CONTRACT_SHA256, "contract"),
        "engine": verify_file(ENGINE_PATH, ENGINE_SHA256, "engine"),
        "target_metadata": verify_file(TARGET_PATH, TARGET_SHA256, "target metadata"),
        "availability": verify_file(AVAILABILITY_PATH, AVAILABILITY_SHA256, "availability"),
        "identity_attachment": verify_file(IDENTITY_PATH, IDENTITY_SHA256, "identity attachment"),
        "r0_audit": verify_file(R0_PATH, R0_SHA256, "R0 audit"),
    }
    free = shutil.disk_usage(str(Path(out_dir).resolve().anchor or out_dir)).free
    if free < MIN_FREE_BYTES:
        raise ZT2Failure("ZT_RESOURCE_NO_GO free=%d required=%d" % (free, MIN_FREE_BYTES))
    r0 = json.loads(R0_PATH.read_text(encoding="utf-8"))
    current_tshark = tshark_identity(tshark)
    if current_tshark != r0.get("tshark_identity"):
        raise ZT2Failure("ZT_IDENTITY_FAILURE TShark identity drift")
    identities = pd.read_csv(IDENTITY_PATH, keep_default_na=False)
    if len(identities) != EXPECTED_MEMBERS or identities["is_report"].astype(str).str.lower().ne("false").any() or identities["is_final"].astype(str).str.lower().ne("false").any():
        raise ZT2Failure("ZT_IDENTITY_FAILURE identity member/boundary drift")
    # Construction receives identity columns only.  Role/device/family are not read here.
    targets = pd.read_csv(
        TARGET_PATH,
        usecols=["uid", "source_group", "raw_source_path", "target_event_position_within_capture", "dataset_kind", "container_path"],
        keep_default_na=False,
    )
    if len(targets) != EXPECTED_TARGETS or targets["uid"].nunique() != EXPECTED_TARGETS:
        raise ZT2Failure("ZT_IDENTITY_FAILURE target denominator drift")
    positions = pd.to_numeric(targets["target_event_position_within_capture"], errors="raise")
    if (positions < 0).any() or not np.equal(positions, np.floor(positions)).all():
        raise ZT2Failure("ZT_IDENTITY_FAILURE target ordinal drift")
    targets["target_event_position_within_capture"] = positions.astype(np.int64)
    keys = ["dataset_kind", "container_path", "raw_source_path"]
    if len(list(targets.groupby(keys, sort=True))) != EXPECTED_MEMBERS or targets.duplicated(keys + ["target_event_position_within_capture"]).any():
        raise ZT2Failure("ZT_IDENTITY_FAILURE member/ordinal topology drift")
    engine = import_file("zt2_semantics_engine", ENGINE_PATH)
    engine.verify_contract(ROOT)
    return engine, targets, identities, current_tshark, pins


def tshark_command(tshark: Path, read_path: str, packet_limit: int) -> List[str]:
    command = [
        str(tshark), "-n", "-r", read_path, "-T", "fields", "-E", "header=y",
        "-E", "separator=/t", "-E", "quote=d", "-E", "occurrence=f", "-c", str(packet_limit),
    ]
    for field in TSHARK_FIELDS:
        command.extend(["-e", field])
    return command


def iter_tshark_rows(tshark: Path, identity: Mapping[str, object], packet_limit: int) -> Iterator[Dict[str, str]]:
    kind = str(identity["dataset_kind"])
    container = Path(str(identity["container_path"]))
    member = str(identity["raw_source_path"])
    archive: Optional[zipfile.ZipFile] = None
    stderr = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    producer_error: List[BaseException] = []
    if kind == "direct_pcap":
        process = subprocess.Popen(
            tshark_command(tshark, str(container), packet_limit), stdout=subprocess.PIPE, stderr=stderr,
            text=True, encoding="utf-8", errors="replace",
        )
        producer = None
    elif kind == "gotham_zip":
        archive = zipfile.ZipFile(container)
        process = subprocess.Popen(tshark_command(tshark, "-", packet_limit), stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=False)

        def feed() -> None:
            assert archive is not None and process.stdin is not None
            try:
                with archive.open(member) as raw:
                    shutil.copyfileobj(raw, process.stdin, length=1024 * 1024)
            except BrokenPipeError:
                pass
            except BaseException as exc:
                producer_error.append(exc)
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass

        producer = threading.Thread(target=feed, name="zt2-zip-feed", daemon=True)
        producer.start()
    else:
        stderr.close()
        raise ZT2Failure("unregistered packet container kind")
    assert process.stdout is not None
    if kind == "direct_pcap":
        text_stream: TextIO = process.stdout  # type: ignore[assignment]
    else:
        text_stream = io.TextIOWrapper(process.stdout, encoding="utf-8", errors="replace", newline="")
    reader = csv.DictReader(text_stream, delimiter="\t", quotechar='"')
    if list(reader.fieldnames or []) != TSHARK_FIELDS:
        process.kill()
        raise ZT2Failure("ZT_SEMANTICS_CONTRACT_FAILURE TShark schema drift")
    try:
        for row in reader:
            yield {field: str(row.get(field, "")) for field in TSHARK_FIELDS}
    finally:
        text_stream.close()
        code = process.wait()
        if producer is not None:
            producer.join(timeout=30)
        stderr.seek(0)
        error_text = stderr.read().strip()
        stderr.close()
        if archive is not None:
            archive.close()
    if producer_error:
        raise ZT2Failure("ZT_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT archive feed failed")
    if code != 0:
        raise ZT2Failure("ZT_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT TShark exit %d: %s" % (code, error_text[-1000:]))


def parse_int(value: object) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        try:
            return int(text)
        except ValueError:
            return None


def parse_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return math.nan


def raw_to_event(engine: Any, raw: Mapping[str, str], source: str, member: str, position: int, target_uid: Optional[str]) -> Any:
    frame = parse_int(raw.get("frame.number"))
    if frame != position + 1:
        raise ZT2Failure("ZT_SEMANTICS_CONTRACT_FAILURE frame ordinal drift")
    src4, dst4 = raw.get("ip.src", "").strip(), raw.get("ip.dst", "").strip()
    src6, dst6 = raw.get("ipv6.src", "").strip(), raw.get("ipv6.dst", "").strip()
    eth_src, eth_dst = raw.get("eth.src", "").strip(), raw.get("eth.dst", "").strip()
    if src4 and dst4:
        src, dst, version = src4, dst4, 4
    elif src6 and dst6:
        src, dst, version = src6, dst6, 6
    elif eth_src and eth_dst:
        src, dst, version = eth_src, eth_dst, None
    else:
        src, dst, version = None, None, None
    protocol = parse_int(raw.get("ip.proto"))
    if protocol is None:
        protocol = parse_int(raw.get("ipv6.nxt"))
    port_pairs = [
        (raw.get("tcp.srcport"), raw.get("tcp.dstport")),
        (raw.get("udp.srcport"), raw.get("udp.dstport")),
        (raw.get("sctp.srcport"), raw.get("sctp.dstport")),
    ]
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    for left, right in port_pairs:
        left_value, right_value = parse_int(left), parse_int(right)
        if left_value is not None and right_value is not None:
            src_port, dst_port = left_value, right_value
            break
    mask = "|".join(sorted(field for field in TSHARK_FIELDS if field not in {"frame.number", "frame.time_epoch", "frame.len"} and raw.get(field, "").strip())) or "none"
    return engine.Event(
        source_id=source, member_id=member, packet_ordinal=position,
        timestamp=parse_float(raw.get("frame.time_epoch")),
        link_type="encap:%s" % (raw.get("frame.encap_type", "").strip() or "unknown"),
        ethertype=parse_int(raw.get("eth.type")), ip_version=version, ip_protocol=protocol,
        src_endpoint=src, dst_endpoint=dst, src_port=src_port, dst_port=dst_port,
        decoder_corrupt=False, field_presence_mask=mask, target_uid=target_uid,
    )


def discover_member(engine: Any, events: Iterable[Any], target_positions: Set[int], maximum: int) -> Tuple[Dict[Tuple[object, ...], int], int]:
    tokens = engine.EndpointTokens()
    last_target: Dict[Tuple[object, ...], int] = {}
    seen: Set[int] = set()
    decoded = 0
    for index, event in enumerate(events):
        if index > maximum:
            raise ZT2Failure("ZT_CAUSALITY_NO_GO discovery crossed exact cutoff")
        decoded += 1
        route = engine.classify_route(event, tokens)
        if index in target_positions:
            seen.add(index)
            if not engine._event_missing_reason(event):
                identity = (route.tier, route.base_key)
                last_target[identity] = max(index, last_target.get(identity, -1))
        if index == maximum:
            break
    if decoded != maximum + 1 or seen != target_positions:
        raise ZT2Failure("ZT_CAUSALITY_NO_GO target cutoff not reached")
    return last_target, decoded


def replay_member(engine: Any, events: Iterable[Any], targets: Sequence[Any], last_target: Mapping[Tuple[object, ...], int], audit: Any) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    by_position = {int(target.packet_ordinal): target for target in targets}
    tokens = engine.EndpointTokens()
    active: MutableMapping[Tuple[object, ...], Any] = {}
    next_epoch: Dict[Tuple[object, ...], int] = {}
    closed: Set[Tuple[object, ...]] = set()
    h4_current: Optional[Tuple[object, ...]] = None
    rows: Dict[str, Any] = {}
    peak_active = 0
    decoded = 0
    maximum = max(by_position)
    for index, event in enumerate(events):
        decoded += 1
        route = engine.classify_route(event, tokens)
        identity = (route.tier, route.base_key)
        target = by_position.get(index)
        missing_reason = engine._event_missing_reason(event)
        if route.tier == "H4" and h4_current is not None and h4_current != identity:
            active.pop(h4_current, None)
        if route.tier == "H4":
            h4_current = identity
        is_active = identity in last_target and index <= int(last_target[identity]) and identity not in closed
        state = active.get(identity)
        if is_active and not missing_reason:
            state, epoch_value = engine.SemanticPrototype._append_or_split(route, state, next_epoch.get(identity, 0), float(event.timestamp))
            next_epoch[identity] = epoch_value
            active[identity] = state
            peak_active = max(peak_active, len(active))
        if target is not None:
            if event.target_uid != target.uid or target.uid in rows:
                raise ZT2Failure("ZT_CAUSALITY_NO_GO target identity drift")
            if missing_reason:
                rows[target.uid] = engine._missing_row(target, event, missing_reason, audit)
            elif not is_active or state is None:
                rows[target.uid] = engine._missing_row(target, event, "CONTEXT_CONSTRUCTION_INVARIANT_FAILURE", audit)
            else:
                rows[target.uid] = engine._finite_row(target, event, route, state, audit)
        if identity in last_target and index == int(last_target[identity]):
            active.pop(identity, None)
            closed.add(identity)
            if h4_current == identity:
                h4_current = None
        if index == maximum:
            break
    for target in targets:
        if target.uid not in rows:
            rows[target.uid] = engine._missing_row(target, None, "TARGET_NOT_REACHED_AT_EXACT_CUTOFF", audit)
    if decoded != maximum + 1 or set(rows) != {target.uid for target in targets} or active:
        raise ZT2Failure("ZT_CAUSALITY_NO_GO lifecycle/conservation failure")
    ordered = [asdict(rows[target.uid]) for target in sorted(targets, key=lambda value: (value.packet_ordinal, value.uid))]
    return ordered, {"replay_packets": decoded, "peak_active_contexts": peak_active, "terminal_active_contexts": len(active)}


def checkpoint_identity(identity: Mapping[str, object], ordered_targets: Sequence[Tuple[str, int]], tshark: Mapping[str, object], runner_sha: str) -> str:
    return sha256_json({
        "contract_sha256": CONTRACT_SHA256, "engine_sha256": ENGINE_SHA256,
        "runner_sha256": runner_sha, "target_sha256": TARGET_SHA256,
        "packet_identity": dict(identity), "tshark_identity": dict(tshark),
        "ordered_targets": list(ordered_targets),
    })


def group_table(frame: pd.DataFrame, group: str, subset: str) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for value, part in frame.groupby(group, sort=True, dropna=False):
        finite = int(part["semantic_finite"].astype(bool).sum())
        rows.append({
            "subset": subset, group: str(value), "targets": len(part), "semantic_finite": finite,
            "semantic_missing": len(part) - finite, "semantic_finite_rate": finite / len(part) if len(part) else math.nan,
        })
    return rows


def quantile(values: pd.Series, probability: float) -> float:
    finite = pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)
    return float(np.quantile(finite, probability)) if len(finite) else math.nan


def context_table(frame: pd.DataFrame, group: str) -> List[Dict[str, object]]:
    finite = frame.loc[frame["semantic_finite"].astype(bool)].copy()
    rows: List[Dict[str, object]] = []
    for keys, part in finite.groupby([group, "context_tier"], sort=True, dropna=False):
        value, tier = keys
        rows.append({
            group: str(value), "context_tier": str(tier), "targets": len(part),
            "event_count_median": quantile(part["context_event_count"], 0.5),
            "event_count_q95": quantile(part["context_event_count"], 0.95),
            "event_count_max": float(pd.to_numeric(part["context_event_count"], errors="coerce").max()),
            "span_seconds_median": quantile(part["context_surrogate_span_seconds"], 0.5),
            "span_seconds_q95": quantile(part["context_surrogate_span_seconds"], 0.95),
            "span_seconds_max": float(pd.to_numeric(part["context_surrogate_span_seconds"], errors="coerce").max()),
        })
    return rows


def endpoint_remap_audit(engine: Any) -> Dict[str, object]:
    targets = [engine.TargetSpec("u", "s", "m", 1)]
    def materialize(left: str, right: str) -> bytes:
        events = [
            engine.Event("s", "m", 0, 1.0, src_endpoint=left, dst_endpoint=right),
            engine.Event("s", "m", 1, 2.0, src_endpoint=right, dst_endpoint=left, target_uid="u"),
        ]
        rows = engine.SemanticPrototype().process_member(events, targets)
        return engine.canonical_rows_bytes(rows)
    passed = materialize("10.0.0.1", "10.0.0.2") == materialize("alpha", "omega")
    return {"status": "PASS" if passed else "ZT_SEMANTICS_CONTRACT_FAILURE", "bijective_endpoint_remap_invariant": passed}


def peak_working_set_bytes() -> Optional[int]:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t),
            ]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if not ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return None
        return int(counters.PeakWorkingSetSize)
    except Exception:
        return None


def execute(args: argparse.Namespace) -> None:
    if args.authorization_token != EXECUTION_TOKEN:
        raise ZT2Failure("real ZT-2 execution not authorized")
    started = time.time()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    runner_sha = sha256_file(Path(__file__))
    engine, targets, identities, tshark_value, pins = preflight(out, Path(args.tshark))
    identity_keys = ["dataset_kind", "container_path", "raw_source_path"]
    identity_map = {
        (str(row.dataset_kind), str(row.container_path), str(row.raw_source_path)): row._asdict()
        for row in identities.itertuples(index=False)
    }
    audit = engine.AccessAudit()
    checkpoint_dir = out / "checkpoints"
    checkpoint_dir.mkdir(exist_ok=True)
    parts: List[pd.DataFrame] = []
    member_audits: List[Dict[str, object]] = []
    for member_index, (raw_key, part) in enumerate(targets.groupby(identity_keys, sort=True), start=1):
        key = tuple(str(value) for value in raw_key)
        identity = identity_map.get(key)
        if identity is None:
            raise ZT2Failure("ZT_IDENTITY_FAILURE target member absent from identity manifest")
        source = str(part["source_group"].iloc[0])
        member = key[2]
        spec_by_position = {
            int(row.target_event_position_within_capture): engine.TargetSpec(str(row.uid), source, member, int(row.target_event_position_within_capture))
            for row in part.itertuples(index=False)
        }
        ordered = sorted((target.uid, int(target.packet_ordinal)) for target in spec_by_position.values())
        digest = checkpoint_identity(identity, ordered, tshark_value, runner_sha)
        data_path = checkpoint_dir / (digest[:24] + ".csv.gz")
        marker_path = checkpoint_dir / (digest[:24] + ".complete.json")
        first_packets = second_packets = peak_active = 0
        if data_path.is_file() and marker_path.is_file():
            marker = json.loads(marker_path.read_text(encoding="utf-8"))
            if marker.get("identity") != digest or marker.get("sha256") != sha256_file(data_path):
                raise ZT2Failure("ZT_IDENTITY_FAILURE checkpoint drift")
            result = pd.read_csv(data_path, keep_default_na=False)
            status = "REUSED_EXACT_MEMBER_BOUNDARY"
        else:
            maximum = max(spec_by_position)
            def first_events() -> Iterator[Any]:
                for position, raw in enumerate(iter_tshark_rows(Path(args.tshark), identity, maximum + 1)):
                    target = spec_by_position.get(position)
                    yield raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)
            last_target, first_packets = discover_member(engine, first_events(), set(spec_by_position), maximum)
            def second_events() -> Iterator[Any]:
                for position, raw in enumerate(iter_tshark_rows(Path(args.tshark), identity, maximum + 1)):
                    target = spec_by_position.get(position)
                    yield raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)
            values, lifecycle = replay_member(engine, second_events(), list(spec_by_position.values()), last_target, audit)
            second_packets = int(lifecycle["replay_packets"])
            peak_active = int(lifecycle["peak_active_contexts"])
            atomic_csv(data_path, values, STATUS_FIELDS, compressed=True)
            atomic_json(marker_path, {"identity": digest, "sha256": sha256_file(data_path), "rows": len(values)})
            result = pd.DataFrame(values)
            status = "COMPUTED_EXACT_TWOPASS"
        if len(result) != len(part) or set(result["uid"].astype(str)) != set(part["uid"].astype(str)):
            raise ZT2Failure("ZT_CAUSALITY_NO_GO member UID conservation failure")
        parts.append(result)
        member_audits.append({
            "member_index": member_index, "dataset_kind": key[0], "container_path": key[1], "raw_source_path": key[2],
            "targets": len(result), "maximum_target_ordinal": int(part["target_event_position_within_capture"].max()),
            "status": status, "checkpoint_identity": digest, "checkpoint_sha256": sha256_file(data_path),
            "discovery_packets": first_packets, "replay_packets": second_packets,
            "peak_active_contexts": peak_active, "terminal_active_contexts": 0,
        })
        print("ZT2_MEMBER_COMPLETE index=%d/30 member=%s targets=%d status=%s" % (member_index, member, len(result), status), flush=True)
    audit.assert_clean()
    status_frame = pd.concat(parts, ignore_index=True)
    if len(status_frame) != EXPECTED_TARGETS or status_frame["uid"].nunique() != EXPECTED_TARGETS or set(status_frame["uid"].astype(str)) != set(targets["uid"].astype(str)):
        raise ZT2Failure("ZT_CAUSALITY_NO_GO global UID conservation failure")

    # Only after exact construction conservation do we open old availability and descriptive roles.
    with np.load(AVAILABILITY_PATH, allow_pickle=False) as values:
        if "uid" not in values.files or "missing" not in values.files:
            raise ZT2Failure("ZT_IDENTITY_FAILURE old availability schema drift")
        old = pd.DataFrame({"uid": values["uid"].astype(str), "old_missing": values["missing"].astype(bool)})
    if len(old) != EXPECTED_TARGETS or int(old["old_missing"].sum()) != EXPECTED_OLD_MISSING:
        raise ZT2Failure("ZT_IDENTITY_FAILURE old availability denominator drift")
    descriptive = pd.read_csv(TARGET_PATH, usecols=["uid", "role", "phase", "source_group", "device_family", "attack_family"], keep_default_na=False)
    joined = status_frame.merge(old, on="uid", how="left", validate="one_to_one").merge(descriptive, on="uid", how="left", validate="one_to_one")
    joined["semantic_finite"] = joined["semantic_finite"].astype(str).str.lower().isin({"true", "1"})
    old_finite_preserved = int(joined.loc[~joined["old_missing"], "semantic_finite"].sum())
    full_finite = int(joined["semantic_finite"].sum())
    overall_rate = full_finite / EXPECTED_TARGETS
    benign = joined.loc[joined["attack_family"].astype(str).str.lower().eq("benign")]
    attack = joined.loc[~joined["attack_family"].astype(str).str.lower().eq("benign")]
    missing_subset = joined.loc[joined["old_missing"]].copy()
    benign_device = group_table(benign, "device_family", "full")
    attack_family = group_table(attack, "attack_family", "full")
    missing_benign_device = group_table(missing_subset.loc[missing_subset["attack_family"].astype(str).str.lower().eq("benign")], "device_family", "old_missing")
    missing_attack_family = group_table(missing_subset.loc[~missing_subset["attack_family"].astype(str).str.lower().eq("benign")], "attack_family", "old_missing")
    full_gates = {
        "rows_exact": len(joined) == EXPECTED_TARGETS,
        "overall_ge_0_90": overall_rate >= 0.90,
        "every_benign_device_ge_0_80": all(float(row["semantic_finite_rate"]) >= 0.80 for row in benign_device),
        "every_attack_family_ge_0_80": all(float(row["semantic_finite_rate"]) >= 0.80 for row in attack_family),
        "incumbent_finite_13827_preserved": old_finite_preserved == EXPECTED_OLD_FINITE,
    }
    missing_rate = int(missing_subset["semantic_finite"].sum()) / EXPECTED_OLD_MISSING
    missing_gates = {
        "rows_exact": len(missing_subset) == EXPECTED_OLD_MISSING,
        "overall_ge_0_90": missing_rate >= 0.90,
        "every_benign_device_ge_0_80": all(float(row["semantic_finite_rate"]) >= 0.80 for row in missing_benign_device),
        "every_attack_family_ge_0_80": all(float(row["semantic_finite_rate"]) >= 0.80 for row in missing_attack_family),
    }
    remap = endpoint_remap_audit(engine)
    terminal = "ZT_SEMANTIC_COVERAGE_PASS" if all(full_gates.values()) and all(missing_gates.values()) and remap["status"] == "PASS" else "ZT_INSUFFICIENT_SEMANTIC_COVERAGE"

    # Durable outputs.
    shutil.copyfile(IDENTITY_PATH, out / "zt2_packet_identity_manifest.csv")
    atomic_json(out / "zt2_contract_and_implementation_identities.json", {
        "status": "PASS", "input_sha256": pins, "runner_sha256": runner_sha,
        "tshark_identity": tshark_value, "targets": EXPECTED_TARGETS, "members": EXPECTED_MEMBERS,
    })
    atomic_csv(out / "zt2_semantic_support_matrix.csv", [
        {"context_tier": "H1", "definition": "IP TCP/UDP endpoint+port context", "learned_parameters": 0},
        {"context_tier": "H2", "definition": "other IP endpoint-pair context", "learned_parameters": 0},
        {"context_tier": "H3", "definition": "non-IP link endpoint-pair context", "learned_parameters": 0},
        {"context_tier": "H4", "definition": "keyless bounded consecutive-run context", "learned_parameters": 0},
    ], ["context_tier", "definition", "learned_parameters"])
    atomic_csv(out / "zt2_semantic_status_by_target.csv.gz", joined[STATUS_FIELDS].to_dict("records"), STATUS_FIELDS, compressed=True)
    role_rows = group_table(joined, "role", "full")
    device_rows = group_table(joined, "device_family", "full")
    family_rows = group_table(joined, "attack_family", "full")
    availability_fields = ["subset", "role", "targets", "semantic_finite", "semantic_missing", "semantic_finite_rate"]
    atomic_csv(out / "zt2_availability_by_role.csv", role_rows, availability_fields)
    availability_fields[1] = "device_family"
    atomic_csv(out / "zt2_availability_by_device.csv", device_rows, availability_fields)
    availability_fields[1] = "attack_family"
    atomic_csv(out / "zt2_availability_by_family.csv", family_rows, availability_fields)
    missing_rows = group_table(missing_subset, "role", "old_missing")
    missing_rows += missing_benign_device
    missing_rows += missing_attack_family
    # Union schema keeps the three grouping dimensions explicit.
    missing_union = []
    for row in missing_rows:
        missing_union.append({
            "subset": row["subset"], "role": row.get("role", ""), "device_family": row.get("device_family", ""),
            "attack_family": row.get("attack_family", ""), "targets": row["targets"],
            "semantic_finite": row["semantic_finite"], "semantic_missing": row["semantic_missing"],
            "semantic_finite_rate": row["semantic_finite_rate"],
        })
    atomic_csv(out / "zt2_old_missing_subset_availability.csv", missing_union, ["subset", "role", "device_family", "attack_family", "targets", "semantic_finite", "semantic_missing", "semantic_finite_rate"])
    context_rows = context_table(joined, "device_family") + context_table(joined, "attack_family")
    context_union = []
    for row in context_rows:
        context_union.append({
            "device_family": row.get("device_family", ""), "attack_family": row.get("attack_family", ""),
            "context_tier": row["context_tier"], "targets": row["targets"],
            "event_count_median": row["event_count_median"], "event_count_q95": row["event_count_q95"], "event_count_max": row["event_count_max"],
            "span_seconds_median": row["span_seconds_median"], "span_seconds_q95": row["span_seconds_q95"], "span_seconds_max": row["span_seconds_max"],
        })
    atomic_csv(out / "zt2_context_size_distributions.csv", context_union, ["device_family", "attack_family", "context_tier", "targets", "event_count_median", "event_count_q95", "event_count_max", "span_seconds_median", "span_seconds_q95", "span_seconds_max"])
    regression_rows = []
    finite_joined = joined.loc[joined["semantic_finite"]].copy()
    for group in ["device_family", "attack_family"]:
        for value, part in finite_joined.groupby(group, sort=True):
            counts = pd.to_numeric(part["timestamp_regression_count_in_context"], errors="coerce").fillna(0)
            regression_rows.append({"group_kind": group, "group_value": str(value), "targets": len(part), "targets_with_regression": int((counts > 0).sum()), "regression_count_sum": int(counts.sum())})
    atomic_csv(out / "zt2_timestamp_regression_counts.csv", regression_rows, ["group_kind", "group_value", "targets", "targets_with_regression", "regression_count_sum"])
    atomic_json(out / "zt2_endpoint_remap_invariance.json", remap)
    atomic_csv(out / "zt2_member_lifecycle_and_checkpoint_audit.csv", member_audits, list(member_audits[0]))
    atomic_json(out / "zt2_role_open_audit.json", {
        "status": "PASS", "construction": asdict(audit), "packet_members_opened": EXPECTED_MEMBERS,
        "labels_joined_after_exact_conservation": True, "report_opened": 0, "final_opened": 0,
        "model_opened": 0, "score_opened": 0, "representation_opened": 0, "training_started": 0,
    })
    atomic_json(out / "zt2_resource_and_checkpoint_manifest.json", {
        "status": "PASS", "wall_seconds": time.time() - started,
        "peak_working_set_bytes": peak_working_set_bytes(), "minimum_free_bytes_gate": MIN_FREE_BYTES,
        "free_bytes_after": shutil.disk_usage(str(out.resolve().anchor or out)).free,
        "completed_member_checkpoints": len(member_audits), "checkpoint_directory": str(checkpoint_dir),
    })
    verdict = {
        "status": terminal, "targets": EXPECTED_TARGETS, "members": EXPECTED_MEMBERS,
        "semantic_finite": full_finite, "semantic_missing": EXPECTED_TARGETS - full_finite,
        "semantic_finite_rate": overall_rate, "old_missing_targets": EXPECTED_OLD_MISSING,
        "old_missing_now_finite": int(missing_subset["semantic_finite"].sum()),
        "old_missing_semantic_finite_rate": missing_rate,
        "old_finite_preserved": old_finite_preserved, "old_finite_expected": EXPECTED_OLD_FINITE,
        "full_universe_gates": full_gates, "old_missing_subset_gates": missing_gates,
        "endpoint_remap_invariance": remap["bijective_endpoint_remap_invariant"],
        "claim_boundary": "Deterministic semantic coverage only; no learned representation, detector performance, CE promotion, report, or FINAL claim.",
        "report_opened": 0, "final_opened": 0, "model_opened": 0, "score_opened": 0,
        "representation_opened": 0, "training_started": 0,
    }
    atomic_json(out / "zt2_semantic_coverage_verdict.json", verdict)
    report = (
        "# ZT-2 real-PCAP semantic coverage result\n\n"
        "- Terminal state: `%s`\n- Full semantic coverage: `%d/%d` (`%.6f`)\n"
        "- Old-missing recovery: `%d/%d` (`%.6f`)\n- Incumbent finite preserved: `%d/%d`\n"
        "- Claim boundary: %s\n"
    ) % (terminal, full_finite, EXPECTED_TARGETS, overall_rate, int(missing_subset["semantic_finite"].sum()), EXPECTED_OLD_MISSING, missing_rate, old_finite_preserved, EXPECTED_OLD_FINITE, verdict["claim_boundary"])
    atomic_text(out / "zt2_result_report.md", report)
    required = [
        "zt2_packet_identity_manifest.csv", "zt2_contract_and_implementation_identities.json",
        "zt2_semantic_support_matrix.csv", "zt2_semantic_status_by_target.csv.gz",
        "zt2_availability_by_role.csv", "zt2_availability_by_device.csv", "zt2_availability_by_family.csv",
        "zt2_old_missing_subset_availability.csv", "zt2_context_size_distributions.csv",
        "zt2_timestamp_regression_counts.csv", "zt2_endpoint_remap_invariance.json",
        "zt2_member_lifecycle_and_checkpoint_audit.csv", "zt2_role_open_audit.json",
        "zt2_resource_and_checkpoint_manifest.json", "zt2_semantic_coverage_verdict.json", "zt2_result_report.md",
    ]
    atomic_text(out / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(out / name), name) for name in required))
    print(json.dumps(verdict, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--out-dir", type=Path, required=True)
    value.add_argument("--tshark", type=Path, required=True)
    value.add_argument("--authorization-token", required=True)
    return value


if __name__ == "__main__":
    execute(parser().parse_args())
