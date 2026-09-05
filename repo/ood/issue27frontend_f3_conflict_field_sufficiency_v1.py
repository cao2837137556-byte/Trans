#!/usr/bin/env python3
"""Targeted, no-training input-sufficiency audit for Frontend-F3.

Only the 28 already identified Frontend-F2 hard-conflict targets and their
causal prefixes are decoded.  The incumbent H1-H4 context router is unchanged;
the audit compares a frozen, endpoint-free event-field ladder.
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
import traceback
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, TextIO, Tuple

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_REL = Path("runs/mainline_docs/frontend_f3_conflict_field_sufficiency_frozen_20260905.md")
CONTRACT_SHA = "1b5c222d6a72050d27e0ed957cc101e1e46e827174d519a9790d9ca617570553"
CONFLICT_REL = Path("runs/frontend_f2_old_function_preservation_d0_v1_20260904/f2_d0_conflicting_prefix_buckets.csv")
CONFLICT_SHA = "b044270974ff281b0a6ad4d32741e19e011d497fdfa613990e1433ed5d2a1535"
TARGET_ATTACHMENT_REL = Path("runs/mainline_docs/frontend_f3_conflict_target_identity_attachment_20260905.csv")
TARGET_ATTACHMENT_SHA = "83270314a539332ca40c047b4f6e1626876b18b70dc85bd47e01146176858d82"
TARGET_ATTACHMENT_SOURCE_SHA = "d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d"
IDENTITY_REL = Path("runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv")
IDENTITY_SHA = "5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c"
R0_REL = Path("runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json")
R0_SHA = "41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11"
ENGINE_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_v1.py")
ENGINE_SHA = "00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa"
ZT_RUNNER_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py")
ZT_RUNNER_SHA = "ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60"
F1_REL = Path("repo/ood/issue27frontend_f1_d1_train_v1.py")
F1_SHA = "6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634"

EXECUTION_TOKEN = "I_AUTHORIZE_FRONTEND_F3_CONFLICT_FIELD_AUDIT"
EXPECTED_TARGETS = 28
EXPECTED_MEMBERS = 8
EXPECTED_L0_CONFLICT_BUCKETS = 2
LEVELS = ("L0", "L1", "L2", "L3")

EXTRA_FIELDS = [
    "ip.len", "ipv6.plen", "ip.ttl", "ipv6.hlim",
    "tcp.flags", "tcp.len", "udp.length",
]


class F3Failure(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_value(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    if not path.is_file():
        raise F3Failure("missing pinned input: %s" % path)
    actual = sha256_file(path)
    if actual != expected:
        raise F3Failure("SHA drift for %s: %s != %s" % (path, actual, expected))
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}


def import_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise F3Failure("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(str(temporary), str(path))


def atomic_gzip_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as binary:
        with gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
    os.replace(str(temporary), str(path))


def write_sha256s(output: Path) -> None:
    files = [item for item in sorted(output.iterdir(), key=lambda p: p.name) if item.is_file() and item.name != "SHA256SUMS"]
    atomic_text(output / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(item), item.name) for item in files))


def tshark_identity(executable: Path) -> Dict[str, object]:
    result = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    value = result.stdout.strip()
    return {
        "executable_path": str(executable.resolve()),
        "executable_bytes": executable.stat().st_size,
        "executable_sha256": sha256_file(executable),
        "version_output": value,
        "version_output_sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
    }


def verify_packet_identity(identity: Mapping[str, object]) -> None:
    container = Path(str(identity["container_path"]))
    if not container.is_file():
        raise F3Failure("packet container absent: %s" % container)
    if container.stat().st_size != int(identity["container_bytes"]):
        raise F3Failure("packet container size drift: %s" % container)
    kind = str(identity["dataset_kind"])
    if kind == "direct_pcap":
        if sha256_file(container) != str(identity["container_sha256"]):
            raise F3Failure("direct PCAP SHA drift: %s" % container)
        return
    if kind != "gotham_zip":
        raise F3Failure("unregistered packet container kind")
    member = str(identity["raw_source_path"])
    with zipfile.ZipFile(container) as archive:
        try:
            info = archive.getinfo(member)
        except KeyError as exc:
            raise F3Failure("archive member absent: %s" % member) from exc
    expected_size = int(identity["member_uncompressed_bytes_if_archive"])
    expected_crc = str(identity["member_crc32_if_archive"]).strip().lower()
    if info.file_size != expected_size or ("%08x" % info.CRC) != expected_crc:
        raise F3Failure("archive member identity drift: %s" % member)


def tshark_command(tshark: Path, read_path: str, packet_limit: int, fields: Sequence[str]) -> List[str]:
    command = [
        str(tshark), "-n", "-r", read_path, "-T", "fields", "-E", "header=y",
        "-E", "separator=/t", "-E", "quote=d", "-E", "occurrence=f", "-c", str(packet_limit),
    ]
    for field in fields:
        command.extend(["-e", field])
    return command


def normalize_tshark_cell(value: object) -> str:
    if value is None or str(value).strip() == "None":
        return ""
    return str(value)


def iter_tshark_rows(
    tshark: Path, identity: Mapping[str, object], packet_limit: int, fields: Sequence[str],
) -> Iterator[Dict[str, str]]:
    kind = str(identity["dataset_kind"])
    container = Path(str(identity["container_path"]))
    member = str(identity["raw_source_path"])
    archive: Optional[zipfile.ZipFile] = None
    stderr = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
    producer_error: List[BaseException] = []
    if kind == "direct_pcap":
        process = subprocess.Popen(
            tshark_command(tshark, str(container), packet_limit, fields),
            stdout=subprocess.PIPE, stderr=stderr, text=True, encoding="utf-8", errors="replace",
        )
        producer = None
    elif kind == "gotham_zip":
        archive = zipfile.ZipFile(container)
        process = subprocess.Popen(
            tshark_command(tshark, "-", packet_limit, fields), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=stderr, text=False,
        )

        def feed() -> None:
            assert archive is not None and process.stdin is not None
            try:
                with archive.open(member) as raw:
                    shutil.copyfileobj(raw, process.stdin, length=1024 * 1024)
            except BrokenPipeError:
                pass
            except BaseException as exc:  # pragma: no cover - engineering boundary
                producer_error.append(exc)
            finally:
                try:
                    process.stdin.close()
                except BrokenPipeError:
                    pass

        producer = threading.Thread(target=feed, name="f3-zip-feed", daemon=True)
        producer.start()
    else:
        stderr.close()
        raise F3Failure("unregistered packet container kind")
    assert process.stdout is not None
    text_stream: TextIO
    if kind == "direct_pcap":
        text_stream = process.stdout  # type: ignore[assignment]
    else:
        text_stream = io.TextIOWrapper(process.stdout, encoding="utf-8", errors="replace", newline="")
    reader = csv.DictReader(text_stream, delimiter="\t", quotechar='"')
    if list(reader.fieldnames or []) != list(fields):
        process.kill()
        raise F3Failure("TShark schema drift")
    try:
        for row in reader:
            yield {field: normalize_tshark_cell(row.get(field)) for field in fields}
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
        raise F3Failure("archive feed failed")
    if code != 0:
        raise F3Failure("TShark exit %d: %s" % (code, error_text[-1000:]))


def parse_int(value: object) -> Optional[int]:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text, 0)
    except ValueError:
        return int(text)


def delta_log2_us(delta_seconds: float) -> str:
    if float(delta_seconds) == 0.0:
        return "ZERO"
    micros = max(1, int(round(float(delta_seconds) * 1_000_000.0)))
    return str(int(math.floor(math.log2(micros))))


def port_class(value: Optional[int]) -> str:
    if value is None:
        return "NONE"
    if value <= 1023:
        return "SYSTEM"
    if value <= 49151:
        return "REGISTERED"
    return "DYNAMIC"


def port_semantic(value: Optional[int]) -> str:
    category = port_class(value)
    return "%s:%d" % (category, value) if category == "SYSTEM" else category


def ttl_bucket(value: Optional[int]) -> str:
    if value is None:
        return "NONE"
    if value <= 31:
        return "0_31"
    if value <= 63:
        return "32_63"
    if value <= 127:
        return "64_127"
    if value <= 191:
        return "128_191"
    return "192_255"


def transport_length(raw: Mapping[str, str], protocol: Optional[int]) -> str:
    field = "tcp.len" if protocol == 6 else "udp.length" if protocol == 17 else ""
    value = parse_int(raw.get(field)) if field else None
    return "NONE" if value is None else str(value)


def extended_signatures(
    base: str, raw: Mapping[str, str], event: Any, delta_seconds: float,
) -> Dict[str, str]:
    frame_length = parse_int(raw.get("frame.len"))
    if frame_length is None:
        raise F3Failure("frame length absent")
    tcp_flags = parse_int(raw.get("tcp.flags")) if event.ip_protocol == 6 else None
    l1 = base + "\x1f" + "\x1f".join([
        "FRAME_LEN=%d" % frame_length,
        "DELTA_LOG2_US=%s" % delta_log2_us(delta_seconds),
        "TRANSPORT_LEN=%s" % transport_length(raw, event.ip_protocol),
        "TCP_FLAGS=%s" % ("NONE" if tcp_flags is None else str(tcp_flags)),
    ])
    l2 = l1 + "\x1f" + "\x1f".join([
        "SRC_PORT_CLASS=%s" % port_class(event.src_port),
        "DST_PORT_CLASS=%s" % port_class(event.dst_port),
        "SRC_PORT_SEMANTIC=%s" % port_semantic(event.src_port),
        "DST_PORT_SEMANTIC=%s" % port_semantic(event.dst_port),
    ])
    ip_length = parse_int(raw.get("ip.len"))
    if ip_length is None:
        payload = parse_int(raw.get("ipv6.plen"))
        ip_length = None if payload is None else payload + 40
    ttl = parse_int(raw.get("ip.ttl"))
    if ttl is None:
        ttl = parse_int(raw.get("ipv6.hlim"))
    l3 = l2 + "\x1f" + "\x1f".join([
        "IP_LEN=%s" % ("NONE" if ip_length is None else str(ip_length)),
        "TTL_BUCKET=%s" % ttl_bucket(ttl),
    ])
    return {"L0": base, "L1": l1, "L2": l2, "L3": l3}


@dataclass
class AuditBucket:
    context_key: str
    signatures: Dict[str, List[str]]
    targets: List[Dict[str, object]]


def replay_member(
    engine: Any, f1: Any, zt: Any, decoded: Iterable[Tuple[Mapping[str, str], Any]],
    targets: Sequence[Any], last_target: Mapping[Tuple[object, ...], int],
) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    by_position = {int(target.packet_ordinal): target for target in targets}
    endpoint_tokens = engine.EndpointTokens()
    active: MutableMapping[Tuple[object, ...], Any] = {}
    buckets: MutableMapping[Tuple[object, ...], AuditBucket] = {}
    next_epoch: Dict[Tuple[object, ...], int] = {}
    closed: Set[Tuple[object, ...]] = set()
    h4_current: Optional[Tuple[object, ...]] = None
    result: List[Dict[str, object]] = []
    seen: Set[str] = set()
    decoded_rows = 0
    maximum = max(by_position)
    for index, (raw, event) in enumerate(decoded):
        decoded_rows += 1
        if index > maximum:
            raise F3Failure("replay crossed exact cutoff")
        route = engine.classify_route(event, endpoint_tokens)
        identity = (route.tier, route.base_key)
        target = by_position.get(index)
        missing_reason = engine._event_missing_reason(event)
        if route.tier == "H4" and h4_current is not None and h4_current != identity:
            active.pop(h4_current, None)
            buckets.pop(h4_current, None)
        if route.tier == "H4":
            h4_current = identity
        is_active = identity in last_target and index <= int(last_target[identity]) and identity not in closed
        state = active.get(identity)
        bucket = buckets.get(identity)
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
                bucket = AuditBucket(context_key, {level: [] for level in LEVELS}, [])
                buckets[identity] = bucket
                delta_seconds = 0.0
                regression = False
            else:
                if bucket is None or previous_last is None:
                    raise F3Failure("active bucket absent")
                delta_seconds = max(previous_last, float(event.timestamp)) - previous_last
                regression = float(event.timestamp) < previous_last
            assert bucket is not None
            direction = engine._direction(route, state)
            base = f1.canonical_signature(raw, event, route, direction, delta_seconds, regression)
            signatures = extended_signatures(base, raw, event, delta_seconds)
            for level in LEVELS:
                bucket.signatures[level].append(signatures[level])
        if target is not None:
            if target.uid in seen or event.target_uid != target.uid:
                raise F3Failure("target identity drift")
            if missing_reason or not is_active or state is None or bucket is None:
                raise F3Failure("protected target became unavailable")
            prefix_rows = {level: list(bucket.signatures[level]) for level in LEVELS}
            result.append({
                "uid": str(target.uid), "context_key": bucket.context_key,
                "prefix_signatures": prefix_rows,
                "prefix_sha256": {level: sha256_value(prefix_rows[level]) for level in LEVELS},
            })
            seen.add(str(target.uid))
        if identity in last_target and index == int(last_target[identity]):
            active.pop(identity, None)
            buckets.pop(identity, None)
            closed.add(identity)
            if h4_current == identity:
                h4_current = None
        if index == maximum:
            break
    expected = {str(target.uid) for target in targets}
    if decoded_rows != maximum + 1 or seen != expected or active:
        raise F3Failure("member lifecycle/conservation failure")
    return result, {"packets": decoded_rows, "targets": len(seen)}


def analyze(rows: Sequence[Mapping[str, object]]) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], Optional[str]]:
    summaries: List[Dict[str, object]] = []
    memberships: List[Dict[str, object]] = []
    selected: Optional[str] = None
    for level in LEVELS:
        buckets: Dict[str, List[Mapping[str, object]]] = defaultdict(list)
        for row in rows:
            buckets[str(row["prefix_sha256"][level])].append(row)  # type: ignore[index]
        mixed = 0
        hard = 0
        for digest, part in sorted(buckets.items()):
            labels = {int(row["label"]) for row in part}
            teachers = {str(row["teacher_kind"]) for row in part}
            is_mixed = labels == {0, 1}
            is_hard = "attack_hard" in teachers and "benign_normal" in teachers
            mixed += int(is_mixed)
            hard += int(is_hard)
            if is_mixed or is_hard:
                for row in part:
                    memberships.append({
                        "level": level, "prefix_sha256": digest, "bucket_rows": len(part),
                        "mixed_label": str(is_mixed).lower(), "hard_protected": str(is_hard).lower(),
                        "uid": row["uid"], "label": row["label"], "teacher_kind": row["teacher_kind"],
                        "source_group": row["source_group"], "attack_family": row["attack_family"],
                    })
        summaries.append({
            "level": level, "unique_prefixes": len(buckets),
            "mixed_label_buckets": mixed, "hard_protected_mixed_buckets": hard,
        })
        if level != "L0" and selected is None and hard == 0:
            selected = level
    return summaries, memberships, selected


def execute(output: Path, tshark: Path) -> Dict[str, object]:
    output = output.resolve()
    runs = (ROOT / "runs").resolve()
    try:
        output.relative_to(runs)
    except ValueError as exc:
        raise F3Failure("output must be under runs") from exc
    output.mkdir(parents=True, exist_ok=True)
    pins = {
        "contract": require_sha(ROOT / CONTRACT_REL, CONTRACT_SHA),
        "conflicts": require_sha(ROOT / CONFLICT_REL, CONFLICT_SHA),
        "target_identity_attachment": require_sha(ROOT / TARGET_ATTACHMENT_REL, TARGET_ATTACHMENT_SHA),
        "identity_attachment": require_sha(ROOT / IDENTITY_REL, IDENTITY_SHA),
        "r0": require_sha(ROOT / R0_REL, R0_SHA),
        "engine": require_sha(ROOT / ENGINE_REL, ENGINE_SHA),
        "zt_runner": require_sha(ROOT / ZT_RUNNER_REL, ZT_RUNNER_SHA),
        "f1_runner": require_sha(ROOT / F1_REL, F1_SHA),
    }
    engine = import_file("f3_zt_engine", ROOT / ENGINE_REL)
    zt = import_file("f3_zt_runner", ROOT / ZT_RUNNER_REL)
    f1 = import_file("f3_f1_runner", ROOT / F1_REL)
    current_tshark = tshark_identity(tshark)
    r0 = json.loads((ROOT / R0_REL).read_text(encoding="utf-8"))
    if current_tshark != r0.get("tshark_identity"):
        raise F3Failure("TShark identity drift")
    fields = list(zt.TSHARK_FIELDS) + [field for field in EXTRA_FIELDS if field not in zt.TSHARK_FIELDS]

    conflicts = pd.read_csv(ROOT / CONFLICT_REL, keep_default_na=False)
    conflicts = conflicts.loc[conflicts["identity_type"].eq("token_prefix_sha")].copy()
    if len(conflicts) != EXPECTED_TARGETS or conflicts["uid"].nunique() != EXPECTED_TARGETS:
        raise F3Failure("conflict target denominator drift")
    conflict_by_uid = conflicts.set_index("uid", drop=False)
    metadata = pd.read_csv(ROOT / TARGET_ATTACHMENT_REL, keep_default_na=False)
    if len(metadata) != EXPECTED_TARGETS or metadata["uid"].nunique() != EXPECTED_TARGETS:
        raise F3Failure("target metadata join drift")
    if set(metadata["uid"].astype(str)) != set(conflicts["uid"].astype(str)):
        raise F3Failure("target attachment UID drift")
    identities = pd.read_csv(ROOT / IDENTITY_REL, keep_default_na=False)
    identity_keys = ["dataset_kind", "container_path", "raw_source_path"]
    identity_map = {
        tuple(str(getattr(row, key)) for key in identity_keys): row._asdict()
        for row in identities.itertuples(index=False)
    }
    groups = list(metadata.groupby(identity_keys, sort=True))
    if len(groups) != EXPECTED_MEMBERS:
        raise F3Failure("member denominator drift")

    target_results: List[Dict[str, object]] = []
    member_audit: List[Dict[str, object]] = []
    for member_index, (raw_key, part) in enumerate(groups, start=1):
        key = tuple(str(item) for item in raw_key)
        packet_identity = identity_map.get(key)
        if packet_identity is None:
            raise F3Failure("member absent from identity attachment")
        verify_packet_identity(packet_identity)
        if str(packet_identity.get("is_report", "")).lower() != "false" or str(packet_identity.get("is_final", "")).lower() != "false":
            raise F3Failure("forbidden member role")
        source = str(part["source_group"].iloc[0])
        member = key[2]
        spec_by_position = {
            int(row.target_event_position_within_capture): engine.TargetSpec(
                str(row.uid), source, member, int(row.target_event_position_within_capture)
            ) for row in part.itertuples(index=False)
        }
        maximum = max(spec_by_position)

        def first_events() -> Iterator[Any]:
            for position, raw in enumerate(iter_tshark_rows(tshark, packet_identity, maximum + 1, fields)):
                target = spec_by_position.get(position)
                yield zt.raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)

        last_target, discovery_packets = zt.discover_member(engine, first_events(), set(spec_by_position), maximum)

        def second_events() -> Iterator[Tuple[Mapping[str, str], Any]]:
            for position, raw in enumerate(iter_tshark_rows(tshark, packet_identity, maximum + 1, fields)):
                target = spec_by_position.get(position)
                event = zt.raw_to_event(engine, raw, source, member, position, None if target is None else target.uid)
                yield raw, event

        decoded, lifecycle = replay_member(engine, f1, zt, second_events(), list(spec_by_position.values()), last_target)
        for row in decoded:
            uid = str(row["uid"])
            expected_context = str(conflict_by_uid.loc[uid, "context_key"])
            if str(row["context_key"]) != expected_context:
                raise F3Failure("context identity drift for %s" % uid)
            source_row = conflict_by_uid.loc[uid]
            row.update({
                "source_group": str(source_row["source_group"]),
                "attack_family": str(source_row["attack_family"]),
                "label": int(source_row["label"]),
                "teacher_kind": str(source_row["teacher_kind"]),
            })
            target_results.append(row)
        member_audit.append({
            "member_index": member_index, "member_id": member, "targets": len(part),
            "maximum_target_position": maximum, "discovery_packets": discovery_packets,
            "replay_packets": lifecycle["packets"],
            "dataset_kind": key[0], "container_bytes": packet_identity.get("container_bytes", ""),
            "container_sha256": packet_identity.get("container_sha256", ""),
            "member_uncompressed_bytes": packet_identity.get("member_uncompressed_bytes_if_archive", ""),
            "member_crc32": packet_identity.get("member_crc32_if_archive", ""),
        })
        print("F3_MEMBER_COMPLETE index=%d/%d member=%s targets=%d" % (member_index, len(groups), member, len(part)), flush=True)

    if len(target_results) != EXPECTED_TARGETS or len({str(row["uid"]) for row in target_results}) != EXPECTED_TARGETS:
        raise F3Failure("global target conservation failure")
    summaries, memberships, selected = analyze(target_results)
    if summaries[0]["hard_protected_mixed_buckets"] != EXPECTED_L0_CONFLICT_BUCKETS:
        raise F3Failure("L0 conflict reproduction failed")
    status = "F3_CONFLICT_FIELDS_CANDIDATE_PASS" if selected is not None else "F3_CONFLICT_FIELDS_NO_GO"
    boundary = {
        "select_opened": 0, "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
        "model_opened": 0, "score_opened": 0, "representation_opened": 0,
        "payload_bytes_opened": 0, "optimizer_steps": 0,
    }
    identity = {
        "status": status, "selected_candidate_level": selected,
        "targets": len(target_results), "members": len(groups), "pins": pins,
        "tshark_identity": current_tshark, "fields": fields,
        "target_attachment_source_sha256": TARGET_ATTACHMENT_SOURCE_SHA,
        "prior_observation_disclosure": "UDP bucket exact lengths/port 53 were viewed before freeze and are non-positive evidence.",
    }
    atomic_json(output / "f3_identities.json", identity)
    atomic_csv(output / "f3_level_summary.csv", ["level", "unique_prefixes", "mixed_label_buckets", "hard_protected_mixed_buckets"], summaries)
    atomic_csv(
        output / "f3_conflict_memberships.csv",
        ["level", "prefix_sha256", "bucket_rows", "mixed_label", "hard_protected", "uid", "label", "teacher_kind", "source_group", "attack_family"],
        memberships,
    )
    atomic_csv(
        output / "f3_member_decode_audit.csv",
        ["member_index", "member_id", "targets", "maximum_target_position", "discovery_packets", "replay_packets", "dataset_kind", "container_bytes", "container_sha256", "member_uncompressed_bytes", "member_crc32"],
        member_audit,
    )
    atomic_gzip_jsonl(output / "f3_target_prefix_signatures.jsonl.gz", sorted(target_results, key=lambda row: str(row["uid"])))
    verdict = {
        "status": status, "selected_candidate_level": selected,
        "targets_conserved": len(target_results), "members_decoded_two_pass": len(groups),
        "level_summary": summaries, "boundary": boundary,
        "claim_boundary": "Necessary input identifiability only; no inheritance, detection, or OOD claim.",
        "next_authorized_by_pass": "full_fit_collision_and_shortcut_audit_only" if selected else "architectural_inheritance_route_only",
    }
    atomic_json(output / "f3_verdict.json", verdict)
    write_sha256s(output)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tshark", default=r"C:\Program Files\Wireshark\tshark.exe")
    parser.add_argument("--authorization-token", required=True)
    args = parser.parse_args()
    output = Path(args.output_dir)
    if args.authorization_token != EXECUTION_TOKEN:
        raise F3Failure("execution not authorized")
    try:
        verdict = execute(output, Path(args.tshark))
    except BaseException as exc:
        output.mkdir(parents=True, exist_ok=True)
        for name in ("f3_verdict.json", "SHA256SUMS"):
            path = output / name
            if path.is_file():
                path.unlink()
        atomic_json(output / "engineering_failure.json", {
            "status": "F3_CONFLICT_FIELDS_ENGINEERING_FAILURE",
            "scientific_verdict_emitted": False, "error_type": type(exc).__name__,
            "error": str(exc), "traceback": traceback.format_exc(),
        })
        raise
    print(json.dumps({"status": verdict["status"], "selected": verdict["selected_candidate_level"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
