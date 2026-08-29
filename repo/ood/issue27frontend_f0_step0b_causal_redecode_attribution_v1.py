#!/usr/bin/env python3
"""Causal re-decode attribution for frozen E3 missing terminal targets.

The ``identity`` command performs R0 only and never opens packet bodies.  The
``execute`` command is intentionally separate and requires a reviewed R0
attachment plus an explicit execution token.  This split makes the current
implementation-review authorization mechanically narrower than real decode.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "runs/mainline_docs/frontend_f0_step0b_causal_redecode_attribution_preregistered_20260829.md"
PROTOCOL_SHA256 = "ace6a37fa1ad84fb1660426d4e6c6876fdd3bc407577e3b0709908465b910794"
EXPECTED_GOTHAM_MD5 = "7ca78c0517ccb3d2854e823678e0f206"
EXECUTION_TOKEN = "I_UNDERSTAND_STEP0B_OPENS_FIT_SELECT_PACKET_PREFIXES"

STAGE = ROOT / "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
PINNED = {
    "protocol": (PROTOCOL, PROTOCOL_SHA256),
    "ckda_contract": (ROOT / "runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md", "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"),
    "step0_contract": (ROOT / "runs/mainline_docs/frontend_f0_missingness_mechanism_audit_frozen_20260828.md", "f188afc0f9a0564a9f193b2e13637efdb660077f6ce74ba5c1d9cfc638fb1e8e"),
    "step0_verdict": (ROOT / "runs/frontend_f0_missingness_mechanism_audit_20260828/frontend_f0_missingness_mechanism_verdict.json", "a4611c854a139bb663ea64e1599beffa10d4bfbf9f82f86f433408153feee9dc"),
    "ckbu": (ROOT / "repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py", "127efd212932d9330af790f17a069a84b3ee48205d68bed7e2e9f00778bb2820"),
    "formal_embedder": (ROOT / "repo/ood/issue27ckda_d1_e3_embed_v1.py", "360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14"),
    "local_twopass": (ROOT / "repo/ood/issue27ckda_d1_e3_embed_local_twopass_v1.py", "9f11d03b31e640de28f11fd7570b1495c7b9452b124b8b99b248689031b24ca2"),
    "availability": (STAGE / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "metadata": (STAGE / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "plan": (STAGE / "ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "target_metadata": (STAGE / "ckda_d1_fit_select_target_metadata.csv", "d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d"),
    "target_audit": (STAGE / "ckda_d1_fit_select_target_metadata.csv.audit.json", "fec780565a8c2f706316c90d76ee5af83136522c20e688b1b6d94f439f7fc906"),
    "local_manifest": (STAGE / "ckda_d1_local_fit_prefix_manifest.csv", "afd8f700e64d799d15c2375c3a887b388423a982c7af72d1cb45b85de2ac8e01"),
    "rebind_audit": (STAGE / "ckda_d1_local_fit_prefix_manifest.csv.audit.json", "78bdbc0a5d3b38127ef1a06fb6bfd4af5a4be47735b9bc723ada1d2374afafe3"),
}

CAUSAL_COLUMNS = [
    "uid", "role", "phase", "source_group", "device_family", "recorded_index",
    "global_pool", "plan_scope", "label_metric_only", "cache_kind", "target_index",
    "raw_source_path", "feature_available_time_epoch",
    "target_event_position_within_capture", "src_local_id", "dst_local_id",
    "dataset_kind", "container_path", "metadata_matched",
]
PLAN_JOIN_COLUMNS = ["uid", "role", "phase", "source_group", "recorded_index", "global_pool", "plan_scope", "label_metric_only"]
PREDICATES = (
    "SESSION_TIMESTAMP_REGRESSION",
    "NO_IP_SESSION_KEY",
    "UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP",
    "NONFINITE_TARGET_TIMESTAMP",
)
MECHANISM_BY_PREDICATE = {
    "NO_IP_SESSION_KEY": "INPUT_SESSION_KEY",
    "UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP": "PROTOCOL_COVERAGE",
    "NONFINITE_TARGET_TIMESTAMP": "TIMESTAMP_VALIDITY",
    "SESSION_TIMESTAMP_REGRESSION": "CAUSAL_TIMESTAMP_ORDER",
}
IDENTITY_FIELDS = [
    "dataset_kind", "container_path", "container_bytes", "container_sha256",
    "published_identity_if_archive", "raw_source_path",
    "member_uncompressed_bytes_if_archive", "member_crc32_if_archive",
    "source_group", "role_set", "target_count",
    "maximum_target_event_position_inclusive", "is_report", "is_final",
]


class PreopenFailure(RuntimeError):
    pass


class DecodeSchemaFailure(RuntimeError):
    pass


class EquivalenceFailure(RuntimeError):
    pass


def sha256_file(path: Path, block: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(block)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def md5_file(path: Path, block: int = 16 * 1024 * 1024) -> str:
    digest = hashlib.md5()
    with Path(path).open("rb") as stream:
        while True:
            chunk = stream.read(block)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: object) -> str:
    data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path: Path, payload: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def atomic_text(path: Path, text: str) -> None:
    atomic_bytes(path, text.encode("utf-8"))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: Iterable[Mapping[str, object]], fields: Sequence[str], gzip_output: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(prefix=".%s." % path.name, suffix=".tmp", dir=str(path.parent))
    os.close(handle)
    try:
        opener = gzip.open if gzip_output else open
        with opener(name, "wt", encoding="utf-8", newline="") as stream:  # type: ignore[arg-type]
            writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise", lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow(dict(row))
        os.replace(name, path)
    except BaseException:
        try:
            os.unlink(name)
        except FileNotFoundError:
            pass
        raise


def import_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_pins() -> Dict[str, str]:
    actual: Dict[str, str] = {}
    for name, (path, expected) in PINNED.items():
        if not path.is_file():
            raise PreopenFailure("missing pinned input: %s: %s" % (name, path))
        digest = sha256_file(path)
        actual[name] = digest
        if digest != expected:
            raise PreopenFailure("pinned SHA drift: %s: %s != %s" % (name, digest, expected))
    return actual


def load_availability(path: Path) -> Tuple[np.ndarray, np.ndarray, Set[str]]:
    opened: Set[str] = set()
    with np.load(path, allow_pickle=False) as values:
        if "uid" not in values.files or "missing" not in values.files:
            raise PreopenFailure("availability lacks uid/missing")
        uid = values["uid"].astype(str)
        opened.add("uid")
        missing = values["missing"].astype(np.bool_)
        opened.add("missing")
    if opened != {"uid", "missing"}:
        raise PreopenFailure("forbidden availability array opened")
    return uid, missing, opened


def load_scope() -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, pd.DataFrame]:
    targets = pd.read_csv(PINNED["target_metadata"][0], usecols=CAUSAL_COLUMNS, keep_default_na=False)
    plan = pd.read_csv(PINNED["plan"][0], usecols=PLAN_JOIN_COLUMNS, keep_default_na=False)
    uid, missing, _ = load_availability(PINNED["availability"][0])
    if len(targets) != 25_467 or targets["uid"].nunique() != 25_467:
        raise PreopenFailure("target metadata UID denominator drift")
    if len(plan) != 25_467 or plan["uid"].nunique() != 25_467:
        raise PreopenFailure("plan UID denominator drift")
    if len(uid) != 25_467 or len(set(uid.tolist())) != 25_467:
        raise PreopenFailure("availability UID denominator drift")
    if set(targets["uid"].astype(str)) != set(plan["uid"].astype(str)) or set(uid) != set(targets["uid"].astype(str)):
        raise PreopenFailure("UID exact join drift")
    if int(missing.sum()) != 11_640 or int((~missing).sum()) != 13_827:
        raise PreopenFailure("availability finite/missing denominator drift")
    joined = targets.merge(plan, on="uid", how="left", validate="one_to_one", suffixes=("", "_plan"))
    for column in PLAN_JOIN_COLUMNS[1:]:
        other = column + "_plan"
        if not (joined[column].astype(str) == joined[other].astype(str)).all():
            raise PreopenFailure("plan/target role identity drift: %s" % column)
    if set(targets["dataset_kind"].astype(str)) - {"direct_pcap", "gotham_zip"}:
        raise PreopenFailure("unknown packet dataset kind")
    positions = pd.to_numeric(targets["target_event_position_within_capture"], errors="raise")
    if (positions < 0).any() or not np.equal(positions, np.floor(positions)).all():
        raise PreopenFailure("target positions must be non-negative integers")
    targets = targets.copy()
    targets["target_event_position_within_capture"] = positions.astype(np.int64)
    key = ["dataset_kind", "container_path", "raw_source_path"]
    if targets.duplicated(key + ["target_event_position_within_capture"]).any():
        raise PreopenFailure("duplicate target position within packet member")
    groups = list(targets.groupby(key, sort=True))
    if len(groups) != 30:
        raise PreopenFailure("packet member denominator drift: %d" % len(groups))
    manifest = pd.read_csv(PINNED["local_manifest"][0], keep_default_na=False)
    required_manifest_columns = {
        "dataset_kind",
        "container_path",
        "pcap_member",
        "fit_cutoff_event_position_inclusive",
    }
    if not required_manifest_columns.issubset(manifest.columns):
        raise PreopenFailure("local packet manifest schema drift")
    # This pinned manifest contains the 27 fit-prefix lineage rows.  The exact
    # target metadata is the normative 30-member fit/select universe; select
    # members intentionally need not occur in the fit-only manifest.
    if len(manifest) != 27:
        raise PreopenFailure("local fit-prefix manifest denominator drift")
    return targets, uid, missing, manifest


def tshark_identity(executable: Path) -> Dict[str, object]:
    executable = Path(executable).resolve()
    if not executable.is_file():
        raise PreopenFailure("TShark executable missing: %s" % executable)
    result = subprocess.run([str(executable), "--version"], check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")
    version = result.stdout.strip()
    if not version:
        raise PreopenFailure("TShark version output empty")
    return {
        "executable_path": str(executable),
        "executable_bytes": executable.stat().st_size,
        "executable_sha256": sha256_file(executable),
        "version_output": version,
        "version_output_sha256": hashlib.sha256(version.encode("utf-8")).hexdigest(),
    }


def manifest_lookup(manifest: pd.DataFrame) -> Dict[Tuple[str, str, str], pd.Series]:
    result: Dict[Tuple[str, str, str], pd.Series] = {}
    for row in manifest.itertuples(index=False):
        key = (str(row.dataset_kind), str(row.container_path), str(row.pcap_member))
        if key in result:
            raise PreopenFailure("duplicate member in local manifest")
        result[key] = pd.Series(row._asdict())
    return result


def build_identity_attachment(targets: pd.DataFrame, manifest: pd.DataFrame) -> List[Dict[str, object]]:
    lookup = manifest_lookup(manifest)
    container_cache: Dict[str, Tuple[int, str, Optional[str], Optional[zipfile.ZipFile]]] = {}
    rows: List[Dict[str, object]] = []
    key_columns = ["dataset_kind", "container_path", "raw_source_path"]
    try:
        for (kind, container_text, member), part in targets.groupby(key_columns, sort=True):
            kind, container_text, member = str(kind), str(container_text), str(member)
            key = (kind, container_text, member)
            maximum = int(part["target_event_position_within_capture"].max())
            # The pinned target metadata is itself the exact fit/select target
            # contract.  Where a member also occurs in the pinned fit-prefix
            # manifest, that independent lineage cutoff must cover every
            # selected target.  Select-only members are not fabricated into
            # that fit-only manifest: their declared cutoff is the exact
            # maximum target position from the pinned target metadata.
            if key in lookup:
                frozen_cutoff = int(lookup[key]["fit_cutoff_event_position_inclusive"])
                if maximum > frozen_cutoff:
                    raise PreopenFailure("target exceeds frozen fit-prefix member cutoff")
            container = Path(container_text)
            if not container.is_file():
                raise PreopenFailure("packet container missing: %s" % container)
            if container_text not in container_cache:
                size = container.stat().st_size
                digest = sha256_file(container)
                published = None
                archive = None
                if kind == "gotham_zip":
                    actual_md5 = md5_file(container)
                    if actual_md5 != EXPECTED_GOTHAM_MD5:
                        raise PreopenFailure("Gotham published MD5 mismatch")
                    published = "zenodo-md5:%s" % actual_md5
                    archive = zipfile.ZipFile(container)
                container_cache[container_text] = (size, digest, published, archive)
            size, digest, published, archive = container_cache[container_text]
            member_size: object = ""
            member_crc: object = ""
            if kind == "gotham_zip":
                assert archive is not None
                try:
                    info = archive.getinfo(member)
                except KeyError as exc:
                    raise PreopenFailure("Gotham allowlisted member absent: %s" % member) from exc
                member_size = int(info.file_size)
                member_crc = "%08x" % int(info.CRC)
            elif kind != "direct_pcap":
                raise PreopenFailure("unknown packet kind")
            roles = sorted(set(part["role"].astype(str)))
            phases = sorted(set(part["phase"].astype(str)))
            sources = sorted(set(part["source_group"].astype(str)))
            if len(sources) != 1 or not roles or not phases:
                raise PreopenFailure("member role/source identity is not exact")
            is_report = any(value.lower() == "report" or "report" in value.lower() for value in roles + phases)
            is_final = any("final" in value.lower() for value in roles + phases)
            if is_report or is_final:
                raise PreopenFailure("report/FINAL packet member in fit/select scope")
            rows.append({
                "dataset_kind": kind,
                "container_path": container_text,
                "container_bytes": int(size),
                "container_sha256": digest,
                "published_identity_if_archive": published or "",
                "raw_source_path": member,
                "member_uncompressed_bytes_if_archive": member_size,
                "member_crc32_if_archive": member_crc,
                "source_group": sources[0],
                "role_set": "|".join(roles),
                "target_count": len(part),
                "maximum_target_event_position_inclusive": maximum,
                "is_report": "false",
                "is_final": "false",
            })
    finally:
        for _size, _digest, _published, archive in container_cache.values():
            if archive is not None:
                archive.close()
    if len(rows) != 30:
        raise PreopenFailure("identity attachment must have 30 members")
    return rows


def materialize_identity(out_dir: Path, tshark: Path) -> Dict[str, object]:
    pins = verify_pins()
    targets, uid, missing, manifest = load_scope()
    tshark_value = tshark_identity(tshark)
    rows = build_identity_attachment(targets, manifest)
    out_dir = Path(out_dir)
    attachment = out_dir / "frontend_f0_step0b_packet_identity_attachment.csv"
    atomic_csv(attachment, rows, IDENTITY_FIELDS)
    digest = sha256_file(attachment)
    atomic_text(Path(str(attachment) + ".sha256"), "%s  %s\n" % (digest, attachment.name))
    audit = {
        "status": "STEP0B_R0_IDENTITY_ATTACHMENT_READY",
        "contract_sha256": PROTOCOL_SHA256,
        "input_sha256": pins,
        "availability_arrays_opened": ["missing", "uid"],
        "forbidden_arrays_opened": [],
        "targets": len(targets),
        "finite": int((~missing).sum()),
        "missing": int(missing.sum()),
        "members": len(rows),
        "packet_bodies_opened": 0,
        "report_opened": 0,
        "final_opened": 0,
        "model_opened": 0,
        "score_opened": 0,
        "training_started": 0,
        "attachment": str(attachment),
        "attachment_sha256": digest,
        "tshark_identity": tshark_value,
    }
    atomic_json(out_dir / "frontend_f0_step0b_r0_identity_audit.json", audit)
    return audit


@dataclass(frozen=True)
class SimpleEvent:
    timestamp: float
    src: str
    dst: str
    ip_version: int
    ip_proto: int
    src_port: int = 0
    dst_port: int = 0


def formal_ip_session(event: Any) -> Optional[Tuple[Any, ...]]:
    if int(event.ip_version) not in {4, 6}:
        return None
    left = (str(event.src), int(event.src_port))
    right = (str(event.dst), int(event.dst_port))
    return (int(event.ip_proto),) + tuple(sorted((left, right)))


def reversible_session_candidate(target: Mapping[str, object], session: Optional[Tuple[Any, ...]]) -> str:
    """Serialize a capture-scoped formal session without an irreversible hash."""
    if session is None:
        return ""
    return json.dumps({
        "source_group": str(target["source_group"]),
        "member": str(target["member"]),
        "ip_proto": int(session[0]),
        "endpoints": [
            {"address": str(endpoint[0]), "port": int(endpoint[1])}
            for endpoint in session[1:]
        ],
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def primitive_predicates(event: Any, regression: bool) -> Dict[str, bool]:
    return {
        "SESSION_TIMESTAMP_REGRESSION": bool(regression),
        "NO_IP_SESSION_KEY": int(event.ip_version) not in {4, 6},
        "UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP": int(event.ip_proto) not in {6, 17},
        "NONFINITE_TARGET_TIMESTAMP": not math.isfinite(float(event.timestamp)),
    }


def primary_reason(values: Mapping[str, bool]) -> str:
    unexpected = set(values) - set(PREDICATES)
    if unexpected:
        raise DecodeSchemaFailure("fifth primitive cause rejected: %s" % sorted(unexpected))
    for name in PREDICATES:
        if bool(values.get(name, False)):
            return name
    return "FINITE"


def mechanism_counts(rows: Iterable[Mapping[str, object]]) -> Dict[str, int]:
    counts = {name: 0 for name in MECHANISM_BY_PREDICATE.values()}
    for row in rows:
        for predicate, mechanism in MECHANISM_BY_PREDICATE.items():
            if bool(row[predicate]):
                counts[mechanism] += 1
    return counts


def classify_mechanisms(counts: Mapping[str, int]) -> str:
    present = {name for name, value in counts.items() if int(value) > 0}
    if not present:
        raise DecodeSchemaFailure("missing mechanism classification has empty cause set")
    # None of the four observed primitive mechanisms is repairable by changing
    # a literal existing resource/configuration value while preserving all
    # seven parent-M3 invariants.  In particular, changing timestamp-order or
    # timestamp-validity semantics is explicitly NEW_FRONTEND_SEMANTICS.
    if len(present) == 1:
        return "NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS"
    return "MIXED_MISSINGNESS_MECHANISMS"


def replay_member(
    events: Iterable[Any],
    targets_by_position: Mapping[int, Mapping[str, object]],
    discovered_sessions: Mapping[int, Optional[Tuple[Any, ...]]],
) -> List[Dict[str, object]]:
    maximum = max(targets_by_position)
    last_target: Dict[Tuple[Any, ...], int] = {}
    for position, session in discovered_sessions.items():
        if session is not None:
            last_target[session] = max(position, last_target.get(session, -1))
    last_timestamp: Dict[Tuple[Any, ...], float] = {}
    poisoned: Set[Tuple[Any, ...]] = set()
    output: List[Dict[str, object]] = []
    decoded = 0
    for position, event in enumerate(events):
        if position > maximum:
            raise DecodeSchemaFailure("decoder crossed inclusive member cutoff")
        decoded += 1
        session = formal_ip_session(event)
        active = session is not None and session in last_target and position <= last_target[session]
        if active:
            timestamp = float(event.timestamp)
            if not math.isfinite(timestamp):
                raise DecodeSchemaFailure("non-finite timestamp reached pinned active-IP append order")
            assert session is not None
            previous = last_timestamp.get(session)
            if previous is not None and timestamp < previous:
                poisoned.add(session)
            last_timestamp[session] = timestamp
        target = targets_by_position.get(position)
        if target is not None:
            expected = discovered_sessions[position]
            if expected != session:
                raise DecodeSchemaFailure("discovery/replay session drift")
            values = primitive_predicates(event, session in poisoned if session is not None else False)
            row = dict(target)
            row.update(values)
            row["primary_reason"] = primary_reason(values)
            row["session_id"] = reversible_session_candidate(target, session)
            output.append(row)
            if session is not None and position == last_target.get(session):
                last_timestamp.pop(session, None)
                poisoned.discard(session)
        if position == maximum:
            break
    if decoded != maximum + 1:
        raise DecodeSchemaFailure("member prefix incomplete")
    if last_timestamp or poisoned:
        raise DecodeSchemaFailure("target-session state not fully released")
    return output


def discovery_pass(events: Iterable[Any], positions: Set[int], maximum: int) -> Tuple[Dict[int, Optional[Tuple[Any, ...]]], int]:
    result: Dict[int, Optional[Tuple[Any, ...]]] = {}
    decoded = 0
    for position, event in enumerate(events):
        if position > maximum:
            raise DecodeSchemaFailure("discovery crossed inclusive member cutoff")
        decoded += 1
        if position in positions:
            result[position] = formal_ip_session(event)
        if position == maximum:
            break
    if decoded != maximum + 1 or set(result) != positions:
        raise DecodeSchemaFailure("discovery prefix/target coverage incomplete")
    return result, decoded


def member_checkpoint_identity(
    contract_sha: str,
    target_sha: str,
    packet_identity: Mapping[str, object],
    tshark: Mapping[str, object],
    ordered_uid_positions: Sequence[Tuple[str, int]],
) -> str:
    return sha256_json({
        "contract_sha256": contract_sha,
        "target_metadata_sha256": target_sha,
        "packet_member_identity": dict(packet_identity),
        "tshark_identity": dict(tshark),
        "ordered_targets": list(ordered_uid_positions),
    })


def open_member_rows(ckbu: Any, identity: Mapping[str, object], tshark: str) -> Tuple[Optional[zipfile.ZipFile], Iterator[Mapping[str, str]]]:
    kind = str(identity["dataset_kind"])
    container = Path(str(identity["container_path"]))
    member = str(identity["raw_source_path"])
    cutoff = int(identity["maximum_target_event_position_inclusive"])
    if kind == "direct_pcap":
        return None, ckbu.iter_tshark_rows(tshark, pcap_path=container, packet_limit=cutoff + 1)
    if kind == "gotham_zip":
        archive = zipfile.ZipFile(container)
        return archive, ckbu.iter_tshark_rows(tshark, archive=archive, member=member, packet_limit=cutoff + 1)
    raise DecodeSchemaFailure("unknown member kind")


def verify_reviewed_identity(out_dir: Path, tshark: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    attachment = out_dir / "frontend_f0_step0b_packet_identity_attachment.csv"
    sidecar = Path(str(attachment) + ".sha256")
    audit_path = out_dir / "frontend_f0_step0b_r0_identity_audit.json"
    if not attachment.is_file() or not sidecar.is_file() or not audit_path.is_file():
        raise PreopenFailure("reviewed R0 identity artifacts absent")
    expected = sidecar.read_text(encoding="utf-8").split()[0]
    if sha256_file(attachment) != expected:
        raise PreopenFailure("R0 identity attachment SHA drift")
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    if audit.get("attachment_sha256") != expected or audit.get("contract_sha256") != PROTOCOL_SHA256:
        raise PreopenFailure("R0 identity audit drift")
    current_tshark = tshark_identity(tshark)
    if current_tshark != audit.get("tshark_identity"):
        raise PreopenFailure("TShark identity drift after review")
    frame = pd.read_csv(attachment, keep_default_na=False)
    if list(frame.columns) != IDENTITY_FIELDS or len(frame) != 30:
        raise PreopenFailure("R0 attachment schema/member drift")
    return frame, audit


def execute_real(args: argparse.Namespace) -> None:
    if args.authorization_token != EXECUTION_TOKEN:
        raise PreopenFailure("real packet execution is not explicitly authorized")
    verify_pins()
    identities, r0_audit = verify_reviewed_identity(Path(args.out_dir), Path(args.tshark))
    targets, frozen_uid, frozen_missing, _manifest = load_scope()
    ckbu = import_file("step0b_ckbu", PINNED["ckbu"][0])
    checkpoint_dir = Path(args.out_dir) / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    reason_parts: List[pd.DataFrame] = []
    member_audits: List[Dict[str, object]] = []
    key_columns = ["dataset_kind", "container_path", "raw_source_path"]
    identity_map = {
        (str(row.dataset_kind), str(row.container_path), str(row.raw_source_path)): row._asdict()
        for row in identities.itertuples(index=False)
    }
    for index, (key, part) in enumerate(targets.groupby(key_columns, sort=True), start=1):
        key = tuple(str(value) for value in key)
        identity = identity_map[key]
        ordered = sorted((str(row.uid), int(row.target_event_position_within_capture)) for row in part.itertuples(index=False))
        checkpoint_identity = member_checkpoint_identity(
            PROTOCOL_SHA256, PINNED["target_metadata"][1], identity,
            r0_audit["tshark_identity"], ordered,
        )
        checkpoint = checkpoint_dir / (checkpoint_identity[:24] + ".csv.gz")
        completed = checkpoint_dir / (checkpoint_identity[:24] + ".complete.json")
        if checkpoint.is_file() and completed.is_file():
            marker = json.loads(completed.read_text(encoding="utf-8"))
            if marker.get("identity") != checkpoint_identity or marker.get("sha256") != sha256_file(checkpoint):
                raise DecodeSchemaFailure("completed member checkpoint drift")
            result = pd.read_csv(checkpoint, keep_default_na=False)
            status = "REUSED_EXACT_MEMBER_BOUNDARY"
            first_packets = second_packets = 0
        else:
            by_position = {
                int(row.target_event_position_within_capture): {"uid": str(row.uid), "source_group": str(row.source_group), "device_family": str(row.device_family), "role": str(row.role), "phase": str(row.phase), "member": str(row.raw_source_path), "event_position": int(row.target_event_position_within_capture)}
                for row in part.itertuples(index=False)
            }
            maximum = max(by_position)
            owner, iterator = open_member_rows(ckbu, identity, args.tshark)
            try:
                discovery, first_packets = discovery_pass((ckbu.event_from_tshark(raw) for raw in iterator), set(by_position), maximum)
            finally:
                if owner is not None:
                    owner.close()
            owner, iterator = open_member_rows(ckbu, identity, args.tshark)
            try:
                values = replay_member((ckbu.event_from_tshark(raw) for raw in iterator), by_position, discovery)
            finally:
                if owner is not None:
                    owner.close()
            second_packets = maximum + 1
            result = pd.DataFrame(values)
            atomic_csv(checkpoint, result.to_dict("records"), list(result.columns), gzip_output=True)
            atomic_json(completed, {"identity": checkpoint_identity, "sha256": sha256_file(checkpoint), "rows": len(result)})
            status = "COMPUTED_EXACT_TWOPASS"
        if set(result["uid"].astype(str)) != set(part["uid"].astype(str)):
            raise DecodeSchemaFailure("member checkpoint UID coverage drift")
        reason_parts.append(result)
        member_audits.append({
            "member_index": index, "dataset_kind": key[0], "container_path": key[1],
            "raw_source_path": key[2], "target_count": len(part), "status": status,
            "checkpoint_identity": checkpoint_identity, "checkpoint_sha256": sha256_file(checkpoint),
            "discovery_packets": first_packets, "replay_packets": second_packets,
        })
        print("STEP0B_MEMBER_COMPLETE index=%d/30 member=%s targets=%d status=%s" % (index, key[2], len(part), status), flush=True)
    reasons = pd.concat(reason_parts, ignore_index=True)
    if len(reasons) != 25_467 or reasons["uid"].nunique() != 25_467:
        raise EquivalenceFailure("reason target denominator drift")
    frozen = pd.DataFrame({"uid": frozen_uid.astype(str), "frozen_missing": frozen_missing.astype(bool)})
    joined = frozen.merge(reasons, on="uid", how="left", validate="one_to_one")
    joined["redecoded_missing"] = joined[list(PREDICATES)].astype(bool).any(axis=1)
    matches = joined["redecoded_missing"].astype(bool) == joined["frozen_missing"].astype(bool)
    equivalence = {
        "uid_coverage": len(joined), "uid_expected": 25_467,
        "equivalence_matches": int(matches.sum()), "equivalence_expected": 25_467,
        "missing": int(joined["redecoded_missing"].sum()), "missing_expected": 11_640,
        "finite": int((~joined["redecoded_missing"]).sum()), "finite_expected": 13_827,
    }
    verdict_path = Path(args.out_dir) / "frontend_f0_step0b_mechanism_verdict.json"
    if not matches.all() or equivalence["missing"] != 11_640:
        try:
            verdict_path.unlink()
        except FileNotFoundError:
            pass
        atomic_json(Path(args.out_dir) / "frontend_f0_step0b_equivalence_audit.json", dict(equivalence, status="REDECODE_MISSINGNESS_EQUIVALENCE_FAILURE"))
        raise EquivalenceFailure("exact frozen missingness equivalence failed")
    # Labels are joined only now, after R3 passed.
    labels = pd.read_csv(PINNED["target_metadata"][0], usecols=["uid", "attack_family"], keep_default_na=False)
    joined = joined.merge(labels, on="uid", how="left", validate="one_to_one")
    missing_rows = joined.loc[joined["redecoded_missing"]].copy()
    counts = mechanism_counts(missing_rows.to_dict("records"))
    terminal = classify_mechanisms(counts)
    primary = Counter(missing_rows["primary_reason"].astype(str))
    excluded_devices = sorted(set(missing_rows["device_family"].astype(str)) - {""})
    excluded_attack_families = sorted(set(missing_rows["attack_family"].astype(str)) - {""})
    out = Path(args.out_dir)
    reason_fields = ["uid", "source_group", "device_family", "role", "phase", "member", "event_position", *PREDICATES, "primary_reason", "session_id", "frozen_missing", "redecoded_missing", "attack_family"]
    atomic_csv(out / "frontend_f0_step0b_reason_by_target.csv.gz", joined[reason_fields].to_dict("records"), reason_fields, gzip_output=True)
    for group, filename in [
        ("source_group", "frontend_f0_step0b_reason_by_source.csv"),
        ("device_family", "frontend_f0_step0b_reason_by_device.csv"),
        ("role", "frontend_f0_step0b_reason_by_role.csv"),
        ("attack_family", "frontend_f0_step0b_reason_by_attack_family.csv"),
    ]:
        universe = sorted(set(joined[group].astype(str)))
        rows = []
        for value in universe:
            subset = missing_rows.loc[missing_rows[group].astype(str) == value]
            row: Dict[str, object] = {group: value, "missing_targets": len(subset)}
            for predicate in PREDICATES:
                row[predicate] = int(subset[predicate].astype(bool).sum())
            rows.append(row)
        atomic_csv(out / filename, rows, [group, "missing_targets", *PREDICATES])
    atomic_csv(out / "frontend_f0_step0b_member_decode_audit.csv", member_audits, list(member_audits[0]))
    atomic_json(out / "frontend_f0_step0b_equivalence_audit.json", dict(equivalence, status="PASS"))
    verdict = {
        "status": terminal,
        "contract_sha256": PROTOCOL_SHA256,
        "primitive_any_true_missing_target_counts": {name: int(missing_rows[name].astype(bool).sum()) for name in PREDICATES},
        "mechanism_any_true_missing_target_counts": counts,
        "primary_reason_distribution": dict(sorted(primary.items())),
        "new_frontend_mechanism_classes": sorted(name for name, value in counts.items() if value),
        "excluded_devices_from_frontend_claim": excluded_devices,
        "excluded_attack_families_from_frontend_claim": [
            {"attack_family": value, "status": "UNPROTECTED_BY_REPRESENTATION_EVIDENCE"}
            for value in excluded_attack_families
        ],
        "all_targets": 25_467, "missing_targets": 11_640, "finite_targets": 13_827,
        "equivalence_matches": 25_467,
        "devices": int(joined["device_family"].nunique()),
        "sessions": int(joined.loc[joined["session_id"].astype(str) != "", "session_id"].nunique()),
        "records": len(joined),
        "packet_members_opened": 30, "report_opened": 0, "final_opened": 0,
        "model_opened": 0, "score_opened": 0, "training_started": 0,
        "tshark_identity": r0_audit["tshark_identity"], "input_sha256": r0_audit["input_sha256"],
        "claim_boundary": "Pinned frozen-E3 fit/select terminal-target missingness-cause topology only; no performance or deployment claim.",
    }
    atomic_json(verdict_path, verdict)
    report = "# Frontend-F0 Step-0b result\n\n- Terminal state: `%s`\n- Exact equivalence: `25,467/25,467`\n- Missing / finite: `11,640 / 13,827`\n- Claim boundary: %s\n" % (terminal, verdict["claim_boundary"])
    atomic_text(out / "frontend_f0_step0b_result_report.md", report)
    required = [
        "frontend_f0_step0b_packet_identity_attachment.csv",
        "frontend_f0_step0b_packet_identity_attachment.csv.sha256",
        "frontend_f0_step0b_reason_by_target.csv.gz",
        "frontend_f0_step0b_reason_by_source.csv",
        "frontend_f0_step0b_reason_by_device.csv",
        "frontend_f0_step0b_reason_by_role.csv",
        "frontend_f0_step0b_reason_by_attack_family.csv",
        "frontend_f0_step0b_member_decode_audit.csv",
        "frontend_f0_step0b_equivalence_audit.json",
        "frontend_f0_step0b_mechanism_verdict.json",
        "frontend_f0_step0b_result_report.md",
    ]
    atomic_text(out / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(out / name), name) for name in required))
    print(json.dumps(verdict, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    sub = value.add_subparsers(dest="command", required=True)
    identity = sub.add_parser("identity", help="R0 only; never opens packet bodies")
    identity.add_argument("--out-dir", type=Path, required=True)
    identity.add_argument("--tshark", type=Path, required=True)
    execute = sub.add_parser("execute", help="R1-R4; requires separately authorized token")
    execute.add_argument("--out-dir", type=Path, required=True)
    execute.add_argument("--tshark", type=Path, required=True)
    execute.add_argument("--authorization-token", required=True)
    return value


def main() -> None:
    args = parser().parse_args()
    if args.command == "identity":
        print(json.dumps(materialize_identity(args.out_dir, args.tshark), indent=2, sort_keys=True))
    elif args.command == "execute":
        execute_real(args)
    else:
        raise RuntimeError("unknown command")


if __name__ == "__main__":
    main()
