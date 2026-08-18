#!/usr/bin/env python3
"""CKDB D0-P3 frozen transfer, boundary, and benign-census executor.

Import and ``validate`` are offline. Network access exists only in the explicit
``transfer`` subcommand, which remains fail-closed until a separately hashed
launch appendix, fresh storage evidence, and a literal authorization file all
pass. The program never reads labels, trains a model, opens FINAL, or submits
HPC work.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple


ISSUE = "issue27ckdb_d0_p3_combined_large_download_and_census_v1_2026-08-18"
CONTRACT_SHA256 = "de864fdb54a071a4db082c79071188f1445c244cd5c05376a4ad4f191fade5a1"
PLAN_SHA256 = "8d5010647134096d4494006e43b30c7752fde5ed8b103582d51b792f4e6862a1"
SCHEMA = "CKDB_D0_P3_EXECUTION_PLAN_V1"
APPENDIX_SCHEMA = "CKDB_D0_P3_LAUNCH_APPENDIX_V1"
AUTH_SCHEMA = "CKDB_D0_P3_TRANSFER_AUTHORIZATION_V1"
CANDIDATES = (
    "UNSW_IOTRAFFIC",
    "CIC_MODBUS_2023",
    "PNNL_ELECTRICITY_AND_GAS_IDS",
)
OBJECT_IDS = ("unsw_pcaps", "cic_benign_pcaps", "pnnl_opaque_tar")
HOLDOUT_SALT = "CKDB_EXTERNAL_BENIGN_REPORT_HOLDOUT_V1"
HOLDOUT_IDS = (
    "UNSW_DEVICE_001",
    "UNSW_DEVICE_027",
    "UNSW_DEVICE_018",
    "UNSW_DEVICE_009",
    "UNSW_DEVICE_024",
)
HOLDOUT_HASHES = (
    "0093f3253c7ef8410efb1dc68595a000ef7a814b2baec1c4232ba068c1704b53",
    "04abb6f50d5ff163bd55f71b754c0e3b8d982ffc178e3c6a2dd68f18cbb0f378",
    "066720e1d0171a6716afa161b63a8a506a01c14086106327a3615767f4086062",
    "10d3908880342bf5648385477b7c6209826da7936b289e2741a2a816dd8a2d2e",
    "186b4f4f87ae280a51358a96be373a9480c55384284d144f039e757e83de5728",
)
HOLDOUT_WARNING = "SMALL_N_FIVE_DEVICE_PROBE"
FINAL_MARKERS = (
    "cooler-motor", "seed37", "seed_37", "seed-37",
    "seed47", "seed_47", "seed-47",
)
PROHIBITED_PLAN_KEYS = (
    "password", "cookie", "bearer", "authorization_header", "signed_url",
    "transient_url", "form_state", "access_token", "refresh_token",
)
NESTED_ARCHIVE_SUFFIXES = (
    ".zip", ".7z", ".rar", ".tar", ".tar.gz", ".tgz", ".tar.bz2",
    ".tbz2", ".tar.xz", ".txz",
)
PCAP_SUFFIXES = (".pcap", ".pcapng", ".cap")
MIN_FIT_SESSIONS = 500000
MIN_FIT_TOKENS = 10000000
QUALITY_MIN_SESSIONS = 100
QUALITY_MIN_PACKETS = 10000
QUALITY_MIN_SOURCE_UNITS = 2
DERIVED_FLOOR_BYTES = 20 * 1024 * 1024 * 1024
MAX_INODE_USE_FRACTION = 0.85
RESULT_NAMES = (
    "ckdb_d0_p3_verdict.json",
    "ckdb_d0_p3_result_report.md",
    "SHA256SUMS",
)


class ContractError(RuntimeError):
    pass


class SafetyError(RuntimeError):
    pass


class TransferError(RuntimeError):
    pass


class BoundaryFailure(RuntimeError):
    def __init__(self, reason_code: str, details: str = "") -> None:
        super().__init__(reason_code + ((": " + details) if details else ""))
        self.reason_code = reason_code
        self.details = details


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def atomic_bytes(path: Path, value: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("wb") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: Any) -> None:
    atomic_bytes(Path(path), json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n")


def atomic_text(path: Path, value: str) -> None:
    atomic_bytes(Path(path), value.encode("utf-8"))


def union_fields(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    fields: Set[str] = set()
    for row in rows:
        fields.update(str(key) for key in row)
    return sorted(fields)


def atomic_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Optional[Sequence[str]] = None) -> None:
    names = list(fields) if fields is not None else union_fields(rows)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=names, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in names})
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def read_json(path: Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def verify_sidecar(path: Path, sidecar: Path) -> str:
    parts = Path(sidecar).read_text(encoding="utf-8").strip().split()
    if len(parts) < 2:
        raise ContractError("invalid SHA sidecar")
    expected = parts[0].lower()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ContractError("invalid SHA sidecar digest")
    if Path(parts[-1]).name != Path(path).name:
        raise ContractError("SHA sidecar filename mismatch")
    actual = sha256_file(path)
    if actual != expected:
        raise ContractError("SHA sidecar mismatch")
    return actual


def _scan_for_forbidden(value: Any, context: str) -> None:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for marker in FINAL_MARKERS:
        if marker in text:
            raise ContractError("FINAL marker in %s: %s" % (context, marker))
    for marker in PROHIBITED_PLAN_KEYS:
        if ('"%s"' % marker) in text:
            raise ContractError("secret field in %s: %s" % (context, marker))


def verify_plan(contract: Path, plan_path: Path) -> Mapping[str, Any]:
    if sha256_file(contract) != CONTRACT_SHA256:
        raise ContractError("FROZEN contract SHA drift")
    if sha256_file(plan_path) != PLAN_SHA256:
        raise ContractError("execution plan SHA drift")
    plan = read_json(plan_path)
    if plan.get("schema_version") != SCHEMA:
        raise ContractError("execution plan schema drift")
    if plan.get("contract_sha256") != CONTRACT_SHA256:
        raise ContractError("plan/contract identity mismatch")
    if tuple(plan.get("candidate_order", [])) != CANDIDATES:
        raise ContractError("candidate order/count drift")
    if bool(plan.get("corpus_search_allowed", True)):
        raise ContractError("corpus search must remain disabled")
    if bool(plan.get("large_download_authorized", True)):
        raise ContractError("base plan cannot authorize download")
    objects = list(plan.get("objects", []))
    if tuple(item.get("object_id") for item in objects) != OBJECT_IDS:
        raise ContractError("object identity/order drift")
    if len({item.get("candidate_id") for item in objects}) != 3:
        raise ContractError("candidate registry is not one-to-one")
    if any(bool(item.get("transfer_enabled", True)) for item in objects):
        raise ContractError("base-plan transfer leaked open")
    if tuple(plan.get("holdout", {}).get("source_unit_ids", [])) != HOLDOUT_IDS:
        raise ContractError("holdout identity drift")
    if plan.get("holdout", {}).get("aggregate_warning") != HOLDOUT_WARNING:
        raise ContractError("holdout warning drift")
    if bool(plan.get("industrial_policy", {}).get("replacement_corpus_allowed", True)):
        raise ContractError("replacement corpus leaked open")
    if plan.get("industrial_policy", {}).get("option") != "USE_ALL_THREE_INDUSTRIAL_DOMAINS_FOR_FIT_SELECT":
        raise ContractError("industrial option drift")
    if plan.get("industrial_policy", {}).get("claim_cap") != "FORBID_BROAD_UNSEEN_INDUSTRIAL_DOMAIN_CLAIM_BEFORE_FINAL":
        raise ContractError("industrial claim cap drift")
    if bool(plan.get("coverage_quality_gate", {}).get("route_kill_enabled", True)):
        raise ContractError("coverage route-kill leaked open")
    non_auth = plan.get("non_authorizations", {})
    if not non_auth or any(bool(value) for value in non_auth.values()):
        raise ContractError("non-authorization drift")
    _scan_for_forbidden(plan, "execution plan")
    return plan


def deterministic_holdout(source_unit_ids: Sequence[str]) -> List[Tuple[str, str]]:
    values: List[Tuple[str, str]] = []
    for source_unit_id in source_unit_ids:
        material = (HOLDOUT_SALT + "\0UNSW_IOTRAFFIC\0" + str(source_unit_id)).encode("utf-8")
        values.append((str(source_unit_id), sha256_bytes(material)))
    values.sort(key=lambda item: (item[1], item[0]))
    return values[:5]


def validate_launch_appendix(
    appendix_path: Path,
    sidecar_path: Path,
    plan: Mapping[str, Any],
) -> Mapping[str, Any]:
    appendix_sha = verify_sidecar(appendix_path, sidecar_path)
    appendix = read_json(appendix_path)
    if appendix.get("schema_version") != APPENDIX_SCHEMA:
        raise ContractError("launch appendix schema drift")
    if appendix.get("contract_sha256") != CONTRACT_SHA256 or appendix.get("execution_plan_sha256") != PLAN_SHA256:
        raise ContractError("launch appendix lineage drift")
    review = appendix.get("independent_review", {})
    if review.get("status") != "PASS" or not re.fullmatch(r"[0-9a-f]{7,40}", str(review.get("commit", ""))):
        raise ContractError("launch appendix lacks independent PASS")
    p0 = appendix.get("p0", {})
    for name in ("P0_A", "P0_B", "P0_C"):
        if p0.get(name) != "CLOSED_FROM_AUTHENTICATED_OFFICIAL_INVENTORY":
            raise ContractError("launch appendix does not close %s" % name)
    objects = list(appendix.get("objects", []))
    if tuple(item.get("object_id") for item in objects) != OBJECT_IDS:
        raise ContractError("launch appendix object identity/order drift")
    for base, item in zip(plan["objects"], objects):
        for key in ("candidate_id", "object_id", "stable_dataset_id"):
            if item.get(key) != base.get(key):
                raise ContractError("appendix stable identity drift: %s" % key)
        relative = str(item.get("publisher_relative_path", ""))
        if not relative or "P0_" in relative or urllib.parse.urlparse(relative).scheme or "?" in relative:
            raise ContractError("appendix lacks stable publisher-relative path")
        hard_cap = int(item.get("stream_hard_cap_bytes", 0))
        extracted_cap = int(item.get("extracted_size_cap_bytes", 0))
        expected_bytes = item.get("expected_bytes")
        if hard_cap <= 0 or extracted_cap <= 0:
            raise ContractError("appendix cap missing")
        if expected_bytes is not None and (int(expected_bytes) <= 0 or int(expected_bytes) > hard_cap):
            raise ContractError("appendix expected bytes invalid")
        checksum = item.get("publisher_sha256")
        if checksum not in (None, "NOT_PUBLISHED") and not re.fullmatch(r"[0-9a-f]{64}", str(checksum).lower()):
            raise ContractError("appendix publisher SHA invalid")
        hosts = list(item.get("allowed_final_hosts", []))
        if not hosts or any(not re.fullmatch(r"[a-z0-9.-]+", str(host).lower()) for host in hosts):
            raise ContractError("appendix final-host allowlist invalid")
    cic = objects[1]
    members = list(cic.get("benign_member_paths", []))
    subtree = str(cic.get("benign_subtree", ""))
    if not members and not subtree:
        raise BoundaryFailure(
            "NO_IDENTIFIABLE_THREE_INDUSTRIAL_DOMAINS_CIC_IDENTITY_UNRESOLVED",
            "P0-B has no benign-only remote identity",
        )
    for value in members + ([subtree] if subtree else []):
        lowered = normalize_member_name(value).lower()
        if any(token in lowered for token in ("attack", "malicious", "/logs/", "/log/")):
            raise ContractError("CIC benign identity contains prohibited subtree")
    _scan_for_forbidden(appendix, "launch appendix")
    appendix = dict(appendix)
    appendix["appendix_sha256"] = appendix_sha
    return appendix


def validate_authorization(path: Path, appendix_sha256: str) -> Mapping[str, Any]:
    value = read_json(path)
    if value.get("schema_version") != AUTH_SCHEMA:
        raise ContractError("authorization schema drift")
    if value.get("contract_sha256") != CONTRACT_SHA256 or value.get("execution_plan_sha256") != PLAN_SHA256:
        raise ContractError("authorization lineage drift")
    if value.get("launch_appendix_sha256") != appendix_sha256:
        raise ContractError("authorization/appendix mismatch")
    if value.get("CKDB_D0_P3_TRANSFER_AUTHORIZATION") != "YES":
        raise ContractError("explicit transfer authorization absent")
    _scan_for_forbidden(value, "authorization file")
    return value


def normalize_member_name(name: str) -> str:
    raw = str(name).replace("\\", "/")
    if not raw or raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise SafetyError("absolute/empty archive path")
    parts = PurePosixPath(raw).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        raise SafetyError("archive path traversal")
    return "/".join(parts)


def _nested_archive(name: str) -> bool:
    lowered = name.lower()
    return any(lowered.endswith(suffix) for suffix in NESTED_ARCHIVE_SUFFIXES)


def sniff_archive_kind(path: Path) -> str:
    with Path(path).open("rb") as handle:
        prefix = handle.read(600)
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"PK\x05\x06") or prefix.startswith(b"PK\x07\x08"):
        return "zip"
    if prefix.startswith(b"\x1f\x8b") or prefix.startswith(b"BZh") or prefix.startswith(b"\xfd7zXZ\x00"):
        return "tar"
    if len(prefix) >= 265 and prefix[257:262] == b"ustar":
        return "tar"
    return "unknown"


def require_archive_kind(path: Path, expected: str) -> None:
    actual = sniff_archive_kind(path)
    if actual != expected:
        raise SafetyError("archive type/magic mismatch expected=%s actual=%s" % (expected, actual))


@dataclass(frozen=True)
class ArchiveMember:
    path: str
    member_type: str
    compressed_bytes: int
    uncompressed_bytes: int


def inspect_archive(path: Path, expected_kind: str, expansion_cap: int) -> List[ArchiveMember]:
    require_archive_kind(path, expected_kind)
    rows: List[ArchiveMember] = []
    seen: Set[str] = set()
    total = 0
    if expected_kind == "zip":
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                name = normalize_member_name(info.filename.rstrip("/"))
                if name in seen:
                    raise SafetyError("duplicate normalized archive path")
                seen.add(name)
                mode = (int(info.external_attr) >> 16) & 0xFFFF
                if stat.S_ISLNK(mode):
                    raise SafetyError("archive symlink rejected")
                if int(info.flag_bits) & 0x1:
                    raise SafetyError("encrypted archive member rejected")
                member_type = "directory" if info.is_dir() else "file"
                if member_type == "file" and _nested_archive(name):
                    raise SafetyError("nested archive rejected")
                total += int(info.file_size)
                if total > int(expansion_cap):
                    raise SafetyError("archive expansion cap exceeded")
                rows.append(ArchiveMember(name, member_type, int(info.compress_size), int(info.file_size)))
    elif expected_kind == "tar":
        with tarfile.open(path, mode="r:*") as archive:
            for info in archive.getmembers():
                name = normalize_member_name(info.name.rstrip("/"))
                if name in seen:
                    raise SafetyError("duplicate normalized archive path")
                seen.add(name)
                if info.issym() or info.islnk() or info.isdev() or info.isfifo():
                    raise SafetyError("archive link/device/FIFO rejected")
                if not (info.isfile() or info.isdir()):
                    raise SafetyError("unsupported tar member type")
                member_type = "directory" if info.isdir() else "file"
                if member_type == "file" and _nested_archive(name):
                    raise SafetyError("nested archive rejected")
                total += int(info.size)
                if total > int(expansion_cap):
                    raise SafetyError("archive expansion cap exceeded")
                rows.append(ArchiveMember(name, member_type, int(info.size), int(info.size)))
    else:
        raise SafetyError("unsupported archive kind")
    return rows


def classify_pnnl_member(name: str) -> str:
    normalized = normalize_member_name(name).lower()
    tokens = set(re.split(r"[^a-z0-9]+", normalized))
    is_capture = normalized.endswith(PCAP_SUFFIXES)
    if not is_capture:
        return "metadata"
    if tokens & {"attack", "attacks", "malicious", "adversarial"}:
        return "attack"
    if ("system" in tokens and "fault" in tokens) or tokens & {"fault", "faults"}:
        return "system_fault"
    normal = bool(tokens & {"normal", "baseline", "benign"})
    electric = bool(tokens & {"electric", "electricity", "power", "microgrid"})
    gas = bool(tokens & {"gas", "naturalgas", "pipeline"}) or ("natural" in tokens and "gas" in tokens)
    if normal and electric and not gas:
        return "electric_normal"
    if normal and gas and not electric:
        return "gas_normal"
    return "ambiguous"


def pnnl_boundary(path: Path, expected_kind: str, expansion_cap: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    inventory = inspect_archive(path, expected_kind, expansion_cap)
    rows: List[Dict[str, Any]] = []
    normal: Dict[str, List[str]] = {"electric_normal": [], "gas_normal": []}
    for item in inventory:
        classification = classify_pnnl_member(item.path) if item.member_type == "file" else "directory"
        rows.append({
            "path": item.path,
            "member_type": item.member_type,
            "compressed_bytes": item.compressed_bytes,
            "uncompressed_bytes": item.uncompressed_bytes,
            "classification": classification,
            "boundary_class": (
                "BENIGN_ONLY_MEMBER_BY_PUBLISHER_SCENARIO"
                if classification in normal else "NOT_BENIGN_ALLOWLISTED"
            ),
        })
        if classification in normal:
            normal[classification].append(item.path)
    if not normal["electric_normal"] or not normal["gas_normal"]:
        raise BoundaryFailure("NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS", "both PNNL normal units are required")
    if any(row["classification"] == "ambiguous" for row in rows if str(row["path"]).lower().endswith(PCAP_SUFFIXES)):
        raise BoundaryFailure("NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS", "ambiguous PNNL capture")
    verdict = {
        "status": "PNNL_BOUNDARY_PASS",
        "postcluster_industrial_domains": 2,
        "electric_normal_members": sorted(normal["electric_normal"]),
        "gas_normal_members": sorted(normal["gas_normal"]),
        "boundary_class": "BENIGN_ONLY_MEMBER_BY_PUBLISHER_SCENARIO",
        "packet_decode_count": 0,
        "replacement_corpus_allowed": False,
    }
    return rows, verdict


def _cic_identity_members(appendix_object: Mapping[str, Any], inventory: Sequence[ArchiveMember]) -> Set[str]:
    exact = {normalize_member_name(value) for value in appendix_object.get("benign_member_paths", [])}
    subtree_raw = str(appendix_object.get("benign_subtree", ""))
    subtree = normalize_member_name(subtree_raw).rstrip("/") if subtree_raw else ""
    selected: Set[str] = set()
    for item in inventory:
        if item.member_type != "file":
            continue
        if item.path in exact or (subtree and (item.path == subtree or item.path.startswith(subtree + "/"))):
            selected.add(item.path)
    return selected


def cic_boundary(
    path: Path,
    expected_kind: str,
    expansion_cap: int,
    appendix_object: Mapping[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    inventory = inspect_archive(path, expected_kind, expansion_cap)
    selected = _cic_identity_members(appendix_object, inventory)
    expected_exact = {normalize_member_name(value) for value in appendix_object.get("benign_member_paths", [])}
    if expected_exact and not expected_exact.issubset(selected):
        raise BoundaryFailure("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE", "frozen benign member missing")
    rows: List[Dict[str, Any]] = []
    capture_count = 0
    for item in inventory:
        lowered = item.path.lower()
        if any(token in lowered for token in ("attack", "malicious", "/logs/", "/log/")):
            raise BoundaryFailure("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE", "attack/log tree present in transferred object")
        allowed = item.path in selected
        if item.member_type == "file" and not allowed:
            raise BoundaryFailure("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE", "mixed whole archive/member outside benign identity")
        if allowed:
            permitted = lowered.endswith(PCAP_SUFFIXES + (".txt", ".md", ".json", ".csv"))
            if not permitted:
                raise BoundaryFailure("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE", "unexpected benign-tree member type")
            if lowered.endswith(PCAP_SUFFIXES):
                capture_count += 1
        rows.append({
            "path": item.path,
            "member_type": item.member_type,
            "uncompressed_bytes": item.uncompressed_bytes,
            "benign_allowlisted": allowed,
        })
    if capture_count <= 0:
        raise BoundaryFailure("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE", "no benign capture")
    return rows, {
        "status": "CIC_BOUNDARY_PASS",
        "postcluster_industrial_domains": 1,
        "benign_members": sorted(selected),
        "packet_decode_count": 0,
        "replacement_corpus_allowed": False,
    }


def industrial_failure_verdict(reason_code: str) -> Dict[str, Any]:
    return {
        "status": reason_code,
        "cic_industrial_domains": 0,
        "pnnl_maximum_industrial_domains": 2,
        "combined_industrial_maximum": 2,
        "minimum_required": 3,
        "route_terminated": True,
        "replacement_corpus_allowed": False,
        "third_corpus_search_allowed": False,
    }


def required_free_bytes(compressed_bytes: int, extracted_cap_bytes: int) -> int:
    compressed = int(compressed_bytes)
    extracted = int(extracted_cap_bytes)
    if compressed <= 0 or extracted <= 0:
        raise ContractError("storage inputs must be positive")
    derived = max(int(math.ceil(0.10 * extracted)), DERIVED_FLOOR_BYTES)
    return int(math.ceil(1.20 * max(2 * compressed, compressed + extracted + derived)))


def storage_gate(
    compressed_bytes: int,
    extracted_cap_bytes: int,
    available_bytes: int,
    inode_use_fraction: Optional[float],
    measured_utc: str,
) -> Dict[str, Any]:
    if not measured_utc or measured_utc == "HISTORICAL":
        raise ContractError("fresh storage measurement required")
    required = required_free_bytes(compressed_bytes, extracted_cap_bytes)
    if inode_use_fraction is None or not math.isfinite(float(inode_use_fraction)):
        raise ContractError("inode evidence required")
    inode_ok = float(inode_use_fraction) < MAX_INODE_USE_FRACTION
    bytes_ok = int(available_bytes) >= required
    return {
        "status": "P0_D_PASS" if bytes_ok and inode_ok else "BLOCKED_STORAGE_NO_TRANSFER",
        "compressed_bytes": int(compressed_bytes),
        "extracted_cap_bytes": int(extracted_cap_bytes),
        "required_free_bytes": required,
        "available_bytes": int(available_bytes),
        "inode_use_fraction": float(inode_use_fraction),
        "maximum_inode_use_fraction": MAX_INODE_USE_FRACTION,
        "measured_utc": measured_utc,
        "fresh_measurement": True,
    }


def _header(response: Any, name: str) -> str:
    headers = getattr(response, "headers", {})
    if hasattr(headers, "get"):
        return str(headers.get(name, ""))
    return ""


def _status(response: Any) -> int:
    value = getattr(response, "status", None)
    if value is None and hasattr(response, "getcode"):
        value = response.getcode()
    return int(value)


def _final_url(response: Any) -> str:
    if hasattr(response, "geturl"):
        return str(response.geturl())
    return str(getattr(response, "url", ""))


def transfer_object(
    spec: Mapping[str, Any],
    transient_url: str,
    partial_path: Path,
    final_path: Path,
    opener: Optional[Any] = None,
) -> Dict[str, Any]:
    parsed = urllib.parse.urlparse(transient_url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise TransferError("only HTTPS transport is permitted")
    allowed_hosts = {str(host).lower() for host in spec.get("allowed_final_hosts", [])}
    if not allowed_hosts:
        raise TransferError("no final-host allowlist")
    cap = int(spec.get("stream_hard_cap_bytes", 0))
    if cap <= 0:
        raise TransferError("stream hard cap absent")
    partial_path = Path(partial_path)
    final_path = Path(final_path)
    if final_path.exists():
        raise TransferError("immutable final object already exists")
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    start = partial_path.stat().st_size if partial_path.exists() else 0
    headers = {"User-Agent": "CKDB-D0-P3/1"}
    if start:
        headers["Range"] = "bytes=%d-" % start
    request = urllib.request.Request(transient_url, headers=headers, method="GET")
    open_fn = opener if opener is not None else urllib.request.urlopen
    response = open_fn(request)
    try:
        status_code = _status(response)
        final_url = _final_url(response)
        final_host = (urllib.parse.urlparse(final_url).hostname or "").lower()
        if final_host not in allowed_hosts:
            raise TransferError("redirect/final host outside allowlist")
        if start:
            if status_code != 206:
                raise TransferError("resume response is not 206; partial retained")
            content_range = _header(response, "Content-Range")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", content_range.strip())
            if match is None or int(match.group(1)) != start:
                raise TransferError("wrong Content-Range; partial retained")
            mode = "ab"
        else:
            if status_code != 200:
                raise TransferError("initial response is not 200")
            mode = "wb"
        total = start
        with partial_path.open(mode) as handle:
            while True:
                block = response.read(4 * 1024 * 1024)
                if not block:
                    break
                total += len(block)
                if total > cap:
                    raise TransferError("stream hard cap exceeded")
                handle.write(block)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    expected_bytes = spec.get("expected_bytes")
    if expected_bytes is not None and int(expected_bytes) != int(total):
        raise TransferError("completed byte count mismatch")
    digest = sha256_file(partial_path)
    publisher_sha = spec.get("publisher_sha256")
    if publisher_sha not in (None, "NOT_PUBLISHED") and digest != str(publisher_sha).lower():
        raise TransferError("publisher checksum mismatch")
    require_archive_kind(partial_path, str(spec["expected_archive_kind"]))
    final_path.parent.mkdir(parents=True, exist_ok=True)
    os.replace(str(partial_path), str(final_path))
    return {
        "candidate_id": spec["candidate_id"],
        "object_id": spec["object_id"],
        "stable_dataset_id": spec["stable_dataset_id"],
        "publisher_relative_path": spec["publisher_relative_path"],
        "bytes": int(total),
        "sha256": digest,
        "final_host": final_host,
        "resume_start_bytes": int(start),
        "completed_utc": utc_now(),
        "transient_url_recorded": False,
        "authorization_material_recorded": False,
    }


def load_transport_secrets(path: Path, repo_root: Path) -> Mapping[str, str]:
    path = Path(path).resolve()
    repo_root = Path(repo_root).resolve()
    try:
        path.relative_to(repo_root)
    except ValueError:
        pass
    else:
        raise ContractError("runtime secret file cannot be inside Git workspace")
    if os.name != "nt" and (path.stat().st_mode & 0o077):
        raise ContractError("runtime secret file must be mode 0600")
    value = read_json(path)
    urls = value.get("transport_urls", {})
    if set(urls) != set(OBJECT_IDS):
        raise ContractError("runtime secret object set drift")
    if any(urllib.parse.urlparse(str(url)).scheme != "https" for url in urls.values()):
        raise ContractError("runtime transport URL must be HTTPS")
    return {str(key): str(url) for key, url in urls.items()}


@dataclass(frozen=True)
class PacketRecord:
    source_unit_id: str
    pcap_member: str
    coarse_domain: str
    immutable_role: str
    event_position: int
    timestamp_us: int
    src_ip: str
    src_port: int
    dst_ip: str
    dst_port: int
    protocol: int
    frame_len: int


def canonical_session_key(event: PacketRecord) -> Tuple[Any, ...]:
    if not event.src_ip or not event.dst_ip:
        raise ValueError("missing endpoint")
    ipaddress.ip_address(event.src_ip)
    ipaddress.ip_address(event.dst_ip)
    protocol = int(event.protocol)
    if protocol < 0 or protocol > 255:
        raise ValueError("missing/invalid protocol")
    left = (event.src_ip, int(event.src_port))
    right = (event.dst_ip, int(event.dst_port))
    endpoint_a, endpoint_b = sorted((left, right))
    return (
        event.source_unit_id,
        event.pcap_member,
        protocol,
        endpoint_a,
        endpoint_b,
    )


def token_fields(event: PacketRecord, previous_timestamp_us: Optional[int]) -> Tuple[int, int, int, int]:
    if int(event.timestamp_us) < 0:
        raise ValueError("missing/negative timestamp")
    key = canonical_session_key(event)
    endpoint_a = key[3]
    direction = 0 if (event.src_ip, int(event.src_port)) == endpoint_a else 1
    if int(event.frame_len) < 0:
        raise ValueError("negative frame length")
    length_bucket = min(int(event.frame_len) // 64, 31)
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
    return direction, length_bucket, int(event.protocol), iat_bucket


@dataclass
class SessionState:
    source_unit_id: str
    pcap_member: str
    coarse_domain: str
    immutable_role: str
    protocol: int
    endpoint_a: Tuple[str, int]
    first_timestamp_us: int
    last_timestamp_us: int
    last_event_position: int
    packet_count: int = 0
    token_count: int = 0
    directions: Set[int] = field(default_factory=set)
    token_histogram: Counter = field(default_factory=Counter)
    positive_iats_seconds: List[float] = field(default_factory=list)
    encodable: bool = True
    failure_reason: str = ""

    def append(self, event: PacketRecord) -> None:
        if not self.encodable:
            return
        if event.pcap_member != self.pcap_member or event.source_unit_id != self.source_unit_id:
            raise ContractError("session state crossed member/source boundary")
        if int(event.event_position) <= int(self.last_event_position) and self.packet_count:
            self.encodable = False
            self.failure_reason = "EVENT_POSITION_REGRESSION"
            return
        try:
            token = token_fields(event, self.last_timestamp_us if self.packet_count else None)
        except (ValueError, OverflowError):
            self.encodable = False
            self.failure_reason = "UNENCODABLE_FROM_FIRST_VIOLATION"
            return
        if self.packet_count:
            delta = int(event.timestamp_us) - int(self.last_timestamp_us)
            if delta < 0:
                self.encodable = False
                self.failure_reason = "NEGATIVE_TIMESTAMP_IAT"
                return
            if delta > 0:
                self.positive_iats_seconds.append(delta / 1000000.0)
        self.last_timestamp_us = int(event.timestamp_us)
        self.last_event_position = int(event.event_position)
        self.packet_count += 1
        self.token_count += 1
        self.directions.add(int(token[0]))
        self.token_histogram[(token[0], token[1], token[2])] += 1


def _packet_count_bin(value: int) -> str:
    if value <= 2:
        return "1-2"
    if value <= 8:
        return "3-8"
    if value <= 32:
        return "9-32"
    if value <= 128:
        return "33-128"
    if value <= 256:
        return "129-256"
    if value <= 1024:
        return "257-1024"
    return ">=1025"


def _duration_bin(value: float) -> str:
    if value < 1:
        return "<1"
    if value < 10:
        return "1-<10"
    if value < 60:
        return "10-<60"
    if value < 300:
        return "60-<300"
    if value < 1800:
        return "300-<1800"
    return ">=1800"


def _polling_bin(value: float) -> str:
    if value < 0.25:
        return "<0.25"
    if value < 0.50:
        return "0.25-<0.50"
    if value < 0.75:
        return "0.50-<0.75"
    return ">=0.75"


def _burstiness(values: Sequence[float]) -> Tuple[Optional[float], str]:
    if len(values) < 3:
        return None, "INSUFFICIENT_IAT"
    mean = sum(values) / len(values)
    variance = sum((item - mean) ** 2 for item in values) / len(values)
    std = math.sqrt(max(0.0, variance))
    denominator = std + mean
    value = 0.0 if denominator == 0 else (std - mean) / denominator
    if value < (-1.0 / 3.0):
        return value, "<-1/3"
    if value > (1.0 / 3.0):
        return value, ">1/3"
    return value, "-1/3..1/3"


def session_row(key: Tuple[Any, ...], state: SessionState) -> Dict[str, Any]:
    duration = max(0.0, (state.last_timestamp_us - state.first_timestamp_us) / 1000000.0)
    maximum_token = max(state.token_histogram.values()) if state.token_histogram else 0
    polling_share = (maximum_token / state.token_count) if state.token_count else 0.0
    burstiness, burstiness_bin = _burstiness(state.positive_iats_seconds)
    transport = "TCP" if state.protocol == 6 else ("UDP" if state.protocol == 17 else "OTHER")
    directionality = "BIDIRECTIONAL" if len(state.directions) >= 2 else "UNIDIRECTIONAL"
    return {
        "session_sha256": sha256_bytes(repr(key).encode("utf-8")),
        "source_unit_id": state.source_unit_id,
        "pcap_member": state.pcap_member,
        "coarse_domain": state.coarse_domain,
        "immutable_role": state.immutable_role,
        "encodable": state.encodable,
        "failure_reason": state.failure_reason,
        "packet_count": state.packet_count,
        "i1_token_count": state.token_count,
        "duration_seconds": duration,
        "packet_count_bin": _packet_count_bin(state.packet_count),
        "duration_bin": _duration_bin(duration),
        "directionality": directionality,
        "transport": transport,
        "polling_proxy": polling_share,
        "polling_proxy_bin": _polling_bin(polling_share),
        "burstiness": "" if burstiness is None else burstiness,
        "burstiness_bin": burstiness_bin,
    }


def summarize_packet_records(records: Iterable[PacketRecord]) -> List[Dict[str, Any]]:
    sessions: Dict[Tuple[Any, ...], SessionState] = {}
    seen_member_positions: Set[Tuple[str, str, int]] = set()
    current_member: Optional[Tuple[str, str]] = None
    completed_rows: List[Dict[str, Any]] = []
    for event in records:
        member_identity = (event.source_unit_id, event.pcap_member)
        if current_member is None:
            current_member = member_identity
        elif member_identity != current_member:
            completed_rows.extend(session_row(key, value) for key, value in sorted(sessions.items(), key=lambda item: repr(item[0])))
            sessions = {}
            seen_member_positions = set()
            current_member = member_identity
        member_position = (event.source_unit_id, event.pcap_member, int(event.event_position))
        if member_position in seen_member_positions:
            raise ContractError("duplicate member event position")
        seen_member_positions.add(member_position)
        try:
            key = canonical_session_key(event)
        except ValueError:
            # Missing endpoint/protocol is represented as a unique excluded causal unit.
            invalid_key = (event.source_unit_id, event.pcap_member, "invalid", int(event.event_position))
            invalid = SessionState(
                event.source_unit_id, event.pcap_member, event.coarse_domain,
                event.immutable_role, int(event.protocol), ("", 0),
                int(event.timestamp_us), int(event.timestamp_us), int(event.event_position),
                encodable=False, failure_reason="MISSING_ENDPOINT_OR_PROTOCOL",
            )
            completed_rows.append(session_row(invalid_key, invalid))
            continue
        endpoint_a = key[3]
        state_value = sessions.get(key)
        if state_value is None:
            state_value = SessionState(
                event.source_unit_id,
                event.pcap_member,
                event.coarse_domain,
                event.immutable_role,
                int(event.protocol),
                endpoint_a,
                int(event.timestamp_us),
                int(event.timestamp_us),
                -1,
            )
            sessions[key] = state_value
        state_value.append(event)
    completed_rows.extend(session_row(key, value) for key, value in sorted(sessions.items(), key=lambda item: repr(item[0])))
    return completed_rows


def coverage_regions(row: Mapping[str, Any]) -> Set[str]:
    packet_count = int(row["packet_count"])
    duration = float(row["duration_seconds"])
    result: Set[str] = set()
    if packet_count <= 8 and duration < 60:
        result.add("R1_sparse_short")
    if packet_count > 256:
        result.add("R2_packet_dense")
    if duration >= 300:
        result.add("R3_long_lived")
    if row["directionality"] == "BIDIRECTIONAL" and row["transport"] == "TCP":
        result.add("R4_bidirectional_tcp")
    if float(row["polling_proxy"]) >= 0.75:
        result.add("R5_polling_like")
    if row["burstiness_bin"] == ">1/3":
        result.add("R6_bursty")
    return result


def aggregate_census(session_rows: Iterable[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    fit_roles = {"external_benign_fit_candidate"}
    fit_sessions = 0
    fit_tokens = 0
    support: Dict[str, Dict[str, Any]] = {
        region: {"sessions": 0, "packets": 0, "source_units": set()}
        for region in (
            "R1_sparse_short", "R2_packet_dense", "R3_long_lived",
            "R4_bidirectional_tcp", "R5_polling_like", "R6_bursty",
        )
    }
    for row in session_rows:
        encodable = row["encodable"] is True or str(row["encodable"]).lower() in {"1", "true", "yes"}
        if encodable and row["immutable_role"] in fit_roles:
            fit_sessions += 1
            fit_tokens += int(row["i1_token_count"])
        if not encodable:
            continue
        for region in coverage_regions(row):
            item = support[region]
            item["sessions"] += 1
            item["packets"] += int(row["packet_count"])
            item["source_units"].add(str(row["source_unit_id"]))
    region_rows: List[Dict[str, Any]] = []
    gaps: List[str] = []
    for region in sorted(support):
        item = support[region]
        supported = (
            item["sessions"] >= QUALITY_MIN_SESSIONS
            and item["packets"] >= QUALITY_MIN_PACKETS
            and len(item["source_units"]) >= QUALITY_MIN_SOURCE_UNITS
        )
        status = "QUALITY_SUPPORTED_MASS" if supported else "THIN_OR_MISSING_" + region
        if not supported:
            gaps.append(region)
        region_rows.append({
            "region": region,
            "sessions": item["sessions"],
            "packets": item["packets"],
            "independent_source_units": len(item["source_units"]),
            "status": status,
            "route_kill": False,
        })
    verdict = {
        "status": "CKDB_D0_P3_CENSUS_COMPLETE",
        "i1_fit_sessions": fit_sessions,
        "i1_fit_tokens": fit_tokens,
        "i1_scale_status": (
            "I1_EXTERNAL_BENIGN_SCALE_GATE_PASS"
            if fit_sessions >= MIN_FIT_SESSIONS and fit_tokens >= MIN_FIT_TOKENS
            else "I1_EXTERNAL_BENIGN_SCALE_GATE_FAIL"
        ),
        "coverage_status": "COVERAGE_SPANS_PREREGISTERED_REGIONS" if not gaps else "COVERAGE_GAP_NAMED",
        "coverage_gaps": gaps,
        "coverage_gap_route_kill": False,
        "coverage_gap_adds_data": False,
        "coverage_gap_tunes_window_or_threshold": False,
        "holdout_ids": list(HOLDOUT_IDS),
        "holdout_warning": HOLDOUT_WARNING,
        "training_performed": False,
        "labels_read": 0,
        "final_opened": 0,
        "hpc_submitted": 0,
    }
    return region_rows, verdict


def packet_record_from_tshark(
    row: Mapping[str, str],
    source_unit_id: str,
    member: str,
    coarse_domain: str,
    role: str,
) -> PacketRecord:
    src = str(row.get("ip.src") or row.get("ipv6.src") or "").strip()
    dst = str(row.get("ip.dst") or row.get("ipv6.dst") or "").strip()
    tcp_src = str(row.get("tcp.srcport", "")).strip()
    tcp_dst = str(row.get("tcp.dstport", "")).strip()
    udp_src = str(row.get("udp.srcport", "")).strip()
    udp_dst = str(row.get("udp.dstport", "")).strip()
    protocol_text = str(row.get("ip.proto", "")).strip()
    timestamp = float(str(row.get("frame.time_epoch", "nan")))
    if not math.isfinite(timestamp):
        timestamp_us = -1
    else:
        timestamp_us = int(round(timestamp * 1000000.0))
    return PacketRecord(
        source_unit_id=source_unit_id,
        pcap_member=member,
        coarse_domain=coarse_domain,
        immutable_role=role,
        event_position=int(float(str(row.get("frame.number", "0") or "0"))),
        timestamp_us=timestamp_us,
        src_ip=src,
        src_port=int(tcp_src or udp_src or 0),
        dst_ip=dst,
        dst_port=int(tcp_dst or udp_dst or 0),
        protocol=int(protocol_text or -1),
        frame_len=int(float(str(row.get("frame.len", "0") or "0"))),
    )


def import_pinned_decoder(path: Path, expected_sha256: str) -> Any:
    if sha256_file(path) != expected_sha256:
        raise ContractError("decoder SHA drift")
    spec = importlib.util.spec_from_file_location("ckdb_d0_p3_pinned_decoder", str(path))
    if spec is None or spec.loader is None:
        raise ContractError("cannot import pinned decoder")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fields = list(getattr(module, "TSHARK_FIELDS", []))
    if any(str(field).lower() in {"label", "type", "attack"} for field in fields):
        raise ContractError("label field leaked into decoder")
    return module


def census_member(
    decoder: Any,
    tshark: str,
    member_spec: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    path = Path(str(member_spec["local_path"]))
    rows = decoder.iter_tshark_rows(tshark, pcap_path=path)
    records = (
        packet_record_from_tshark(
            row,
            str(member_spec["source_unit_id"]),
            str(member_spec["pcap_member"]),
            str(member_spec["coarse_domain"]),
            str(member_spec["immutable_role"]),
        )
        for row in rows
    )
    return summarize_packet_records(records)


def safe_extract_members(
    archive_path: Path,
    expected_kind: str,
    selected_members: Sequence[str],
    destination_root: Path,
    expansion_cap: int,
) -> List[Dict[str, Any]]:
    inventory = inspect_archive(archive_path, expected_kind, expansion_cap)
    available = {item.path: item for item in inventory if item.member_type == "file"}
    selected = [normalize_member_name(value) for value in selected_members]
    if len(selected) != len(set(selected)) or not selected:
        raise SafetyError("selected extraction allowlist is empty or duplicated")
    missing = sorted(set(selected) - set(available))
    if missing:
        raise SafetyError("selected archive members missing: %s" % ",".join(missing[:5]))
    destination_root = Path(destination_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    rows: List[Dict[str, Any]] = []
    if expected_kind == "zip":
        archive_context: Any = zipfile.ZipFile(archive_path)
    elif expected_kind == "tar":
        archive_context = tarfile.open(archive_path, mode="r:*")
    else:
        raise SafetyError("unsupported extraction archive kind")
    with archive_context as archive:
        for name in sorted(selected):
            destination = (destination_root / Path(*PurePosixPath(name).parts)).resolve()
            try:
                destination.relative_to(destination_root)
            except ValueError:
                raise SafetyError("extraction escaped destination root")
            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_name("." + destination.name + ".partial")
            if expected_kind == "zip":
                source = archive.open(name, "r")
            else:
                tar_info = archive.getmember(name)
                source = archive.extractfile(tar_info)
                if source is None:
                    raise SafetyError("selected tar member is not a file")
            written = 0
            digest = hashlib.sha256()
            with source:
                with temporary.open("wb") as handle:
                    while True:
                        block = source.read(4 * 1024 * 1024)
                        if not block:
                            break
                        written += len(block)
                        if written > int(available[name].uncompressed_bytes):
                            raise SafetyError("member exceeded inventoried size")
                        digest.update(block)
                        handle.write(block)
                    handle.flush()
                    os.fsync(handle.fileno())
            if written != int(available[name].uncompressed_bytes):
                raise SafetyError("member extracted-size mismatch")
            os.replace(str(temporary), str(destination))
            rows.append({
                "archive_member": name,
                "local_path": str(destination),
                "bytes": written,
                "sha256": digest.hexdigest(),
            })
    return rows


def _role_for_member(candidate_id: str, source_unit_id: str) -> str:
    if candidate_id == "UNSW_IOTRAFFIC" and source_unit_id in HOLDOUT_IDS:
        return "EXTERNAL_BENIGN_REPORT_HOLDOUT"
    if candidate_id in CANDIDATES:
        return "external_benign_fit_candidate"
    raise ContractError("unknown candidate in census member plan")


def validate_census_member_plan(
    member_plan: Mapping[str, Any],
    boundary_verdict: Mapping[str, Any],
    boundary_root: Path,
) -> List[Dict[str, Any]]:
    if member_plan.get("schema_version") != "CKDB_D0_P3_CENSUS_MEMBER_PLAN_V1":
        raise ContractError("census member-plan schema drift")
    if member_plan.get("contract_sha256") != CONTRACT_SHA256 or member_plan.get("execution_plan_sha256") != PLAN_SHA256:
        raise ContractError("census member-plan lineage drift")
    if boundary_verdict.get("status") != "CKDB_D0_P3_BOUNDARY_VERIFIED":
        raise ContractError("boundary verdict is not PASS")
    expected_boundary_sha = str(member_plan.get("boundary_verdict_sha256", ""))
    if expected_boundary_sha != str(boundary_verdict.get("self_sha256", "")):
        raise ContractError("census plan/boundary identity mismatch")
    root = Path(boundary_root).resolve()
    entries = list(member_plan.get("members", []))
    if not entries:
        raise ContractError("empty census member plan")
    rows: List[Dict[str, Any]] = []
    seen_paths: Set[str] = set()
    industrial_domains: Set[str] = set()
    for item in entries:
        candidate = str(item.get("candidate_id", ""))
        source_unit_id = str(item.get("source_unit_id", ""))
        member = normalize_member_name(str(item.get("pcap_member", "")))
        local_path = Path(str(item.get("local_path", ""))).resolve()
        try:
            local_path.relative_to(root)
        except ValueError:
            raise ContractError("census member path escaped boundary-verified root")
        if not local_path.is_file() or not str(local_path).lower().endswith(PCAP_SUFFIXES):
            raise ContractError("census member is not a materialized capture")
        digest = sha256_file(local_path)
        if digest != str(item.get("sha256", "")).lower():
            raise ContractError("census member SHA drift")
        if str(local_path) in seen_paths:
            raise ContractError("duplicate census local path")
        seen_paths.add(str(local_path))
        lowered = (member + "/" + str(local_path)).lower()
        if any(marker in lowered for marker in FINAL_MARKERS + ("attack", "malicious", "system_fault")):
            raise ContractError("prohibited member entered census plan")
        coarse = str(item.get("coarse_domain", ""))
        if candidate == "CIC_MODBUS_2023":
            if coarse != "CIC_MODBUS_SHARED_SIMULATOR":
                raise ContractError("CIC fine role inflated coarse domain")
            industrial_domains.add(coarse)
        elif candidate == "PNNL_ELECTRICITY_AND_GAS_IDS":
            if coarse not in {"PNNL_ELECTRIC_NORMAL", "PNNL_GAS_NORMAL"}:
                raise ContractError("PNNL coarse-domain drift")
            industrial_domains.add(coarse)
        elif candidate != "UNSW_IOTRAFFIC":
            raise ContractError("unknown census candidate")
        role = _role_for_member(candidate, source_unit_id)
        if str(item.get("immutable_role", role)) != role:
            raise ContractError("census role disagrees with deterministic role")
        rows.append({
            "candidate_id": candidate,
            "source_unit_id": source_unit_id,
            "pcap_member": member,
            "coarse_domain": coarse,
            "immutable_role": role,
            "local_path": str(local_path),
            "sha256": digest,
        })
    if industrial_domains != {
        "CIC_MODBUS_SHARED_SIMULATOR",
        "PNNL_ELECTRIC_NORMAL",
        "PNNL_GAS_NORMAL",
    }:
        raise ContractError("combined industrial coarse-domain count is not exactly three")
    return rows


def iter_checkpoint_rows(paths: Sequence[Path]) -> Iterator[Dict[str, Any]]:
    for path in paths:
        with Path(path).open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield dict(row)


def descriptor_tables(session_rows: Iterable[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    marginal: Counter = Counter()
    joint: Counter = Counter()
    source: MutableMapping[Tuple[str, str, str], Dict[str, int]] = defaultdict(lambda: {
        "sessions": 0, "encodable_sessions": 0, "packets": 0, "i1_tokens": 0,
    })
    descriptor_names = (
        "packet_count_bin", "duration_bin", "directionality", "transport",
        "polling_proxy_bin", "burstiness_bin",
    )
    for row in session_rows:
        key = (str(row["coarse_domain"]), str(row["source_unit_id"]), str(row["immutable_role"]))
        source[key]["sessions"] += 1
        encodable = row["encodable"] is True or str(row["encodable"]).lower() in {"1", "true", "yes"}
        if not encodable:
            continue
        packets = int(row["packet_count"])
        source[key]["encodable_sessions"] += 1
        source[key]["packets"] += packets
        source[key]["i1_tokens"] += int(row["i1_token_count"])
        for descriptor in descriptor_names:
            marginal[key + (descriptor, str(row[descriptor]))] += 1
        joint[key + (
            str(row["packet_count_bin"]), str(row["duration_bin"]),
            str(row["directionality"]), str(row["transport"]),
        )] += 1
    marginal_rows = [{
        "coarse_domain": key[0], "source_unit_id": key[1], "immutable_role": key[2],
        "descriptor": key[3], "value": key[4], "sessions": count,
    } for key, count in sorted(marginal.items())]
    joint_rows = [{
        "coarse_domain": key[0], "source_unit_id": key[1], "immutable_role": key[2],
        "packet_count_bin": key[3], "duration_bin": key[4],
        "directionality": key[5], "transport": key[6], "sessions": count,
    } for key, count in sorted(joint.items())]
    source_rows = [dict({
        "coarse_domain": key[0], "source_unit_id": key[1], "immutable_role": key[2],
    }, **value) for key, value in sorted(source.items())]
    return marginal_rows, joint_rows, source_rows


def write_sha256sums(root: Path, excluded: Sequence[str] = ("SHA256SUMS",)) -> None:
    rows = []
    for path in sorted(item for item in Path(root).rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in set(excluded):
            continue
        rows.append("%s  %s" % (sha256_file(path), relative))
    atomic_text(Path(root) / "SHA256SUMS", "\n".join(rows) + "\n")


def deterministic_package(root: Path, destination: Path) -> None:
    root = Path(root)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name("." + destination.name + ".tmp")
    with temporary.open("wb") as raw:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path in sorted(item for item in root.rglob("*") if item.is_file()):
                    relative = path.relative_to(root).as_posix()
                    info = archive.gettarinfo(str(path), arcname=relative)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with path.open("rb") as handle:
                        archive.addfile(info, handle)
    os.replace(str(temporary), str(destination))


def clean_scientific_outputs(output_root: Path) -> None:
    root = Path(output_root)
    for name in RESULT_NAMES:
        path = root / name
        if path.exists() and path.is_file():
            path.unlink()


def record_engineering_failure(output_root: Path, exc: BaseException) -> None:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    clean_scientific_outputs(root)
    atomic_json(root / "engineering_failure.json", {
        "status": "ENGINEERING_FAILURE_NO_VERDICT",
        "error_type": type(exc).__name__,
        "error": str(exc),
        "failed_utc": utc_now(),
        "scientific_verdict_emitted": False,
    })


def command_validate(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    print(json.dumps({
        "status": "CKDB_D0_P3_OFFLINE_IDENTITY_PASS",
        "contract_sha256": CONTRACT_SHA256,
        "plan_sha256": PLAN_SHA256,
        "candidates": plan["candidate_order"],
        "network_requests": 0,
    }, indent=2, sort_keys=True))


def command_preflight(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    appendix = validate_launch_appendix(args.appendix, args.appendix_sidecar, plan)
    objects = appendix["objects"]
    compressed = sum(int(item.get("expected_bytes") or item["stream_hard_cap_bytes"]) for item in objects)
    extracted = sum(int(item["extracted_size_cap_bytes"]) for item in objects)
    usage = shutil.disk_usage(args.destination)
    # NTFS has a dynamically growing MFT rather than a fixed inode pool. The
    # independently reviewed launch evidence must therefore supply the frozen
    # conservative inode-equivalent fraction explicitly.
    gate = storage_gate(compressed, extracted, usage.free, args.inode_use_fraction, utc_now())
    if gate["status"] != "P0_D_PASS":
        raise ContractError("BLOCKED_STORAGE_NO_TRANSFER")
    value = {
        "status": "CKDB_D0_P3_PREFLIGHT_PASS",
        "appendix_sha256": appendix["appendix_sha256"],
        "storage": gate,
        "network_requests": 0,
    }
    atomic_json(args.output, value)
    print(json.dumps(value, indent=2, sort_keys=True))


def command_transfer(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    appendix = validate_launch_appendix(args.appendix, args.appendix_sidecar, plan)
    validate_authorization(args.authorization, appendix["appendix_sha256"])
    preflight = read_json(args.preflight)
    if preflight.get("status") != "CKDB_D0_P3_PREFLIGHT_PASS" or preflight.get("appendix_sha256") != appendix["appendix_sha256"]:
        raise ContractError("fresh reviewed preflight missing")
    if preflight.get("storage", {}).get("status") != "P0_D_PASS":
        raise ContractError("P0-D not passed")
    secret_path = Path(args.runtime_secrets)
    urls: Mapping[str, str] = {}
    try:
        urls = load_transport_secrets(secret_path, args.repo_root)
        results = []
        by_id = {item["object_id"]: item for item in appendix["objects"]}
        for object_id in OBJECT_IDS:
            spec = by_id[object_id]
            final_path = Path(args.destination) / str(spec["destination_relative_path"])
            partial_path = Path(args.destination) / "partial" / (object_id + ".partial")
            results.append(transfer_object(spec, urls[object_id], partial_path, final_path))
        atomic_json(Path(args.destination) / "control/transfer_manifest.json", {
            "status": "IMMUTABLE_QUARANTINE_COMPLETE",
            "appendix_sha256": appendix["appendix_sha256"],
            "objects": results,
            "transient_urls_recorded": False,
            "authorization_material_recorded": False,
        })
    finally:
        if secret_path.exists():
            secret_path.unlink()


def identity_json(value: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(value)
    result.pop("self_sha256", None)
    result["self_sha256"] = sha256_bytes(canonical_json(result))
    return result


def _appendix_objects(appendix: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(item["object_id"]): item for item in appendix["objects"]}


def _object_path(destination: Path, item: Mapping[str, Any]) -> Path:
    root = Path(destination).resolve()
    path = (root / str(item["destination_relative_path"])).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        raise ContractError("appendix destination escaped execution root")
    if not path.is_file():
        raise ContractError("transferred object missing: %s" % item["object_id"])
    return path


def _inventory_rows(items: Sequence[ArchiveMember], candidate_id: str) -> List[Dict[str, Any]]:
    return [{
        "candidate_id": candidate_id,
        "path": item.path,
        "member_type": item.member_type,
        "compressed_bytes": item.compressed_bytes,
        "uncompressed_bytes": item.uncompressed_bytes,
    } for item in items]


def command_boundary(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    appendix = validate_launch_appendix(args.appendix, args.appendix_sidecar, plan)
    objects = _appendix_objects(appendix)
    destination = Path(args.destination).resolve()
    output = Path(args.output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    transfer_manifest = read_json(destination / "control/transfer_manifest.json")
    if transfer_manifest.get("status") != "IMMUTABLE_QUARANTINE_COMPLETE":
        raise ContractError("immutable quarantine transfer manifest missing")
    if transfer_manifest.get("appendix_sha256") != appendix["appendix_sha256"]:
        raise ContractError("transfer/appendix identity drift")

    unsw_spec = objects["unsw_pcaps"]
    pnnl_spec = objects["pnnl_opaque_tar"]
    cic_spec = objects["cic_benign_pcaps"]
    unsw_path = _object_path(destination, unsw_spec)
    pnnl_path = _object_path(destination, pnnl_spec)
    cic_path = _object_path(destination, cic_spec)
    unsw = inspect_archive(unsw_path, str(unsw_spec["expected_archive_kind"]), int(unsw_spec["extracted_size_cap_bytes"]))
    atomic_csv(output / "ckdb_d0_p3_unsw_inventory.csv", _inventory_rows(unsw, "UNSW_IOTRAFFIC"))
    try:
        pnnl_rows, pnnl = pnnl_boundary(
            pnnl_path, str(pnnl_spec["expected_archive_kind"]), int(pnnl_spec["extracted_size_cap_bytes"]),
        )
        atomic_csv(output / "ckdb_d0_p3_pnnl_inventory.csv", pnnl_rows)
        cic_rows, cic = cic_boundary(
            cic_path, str(cic_spec["expected_archive_kind"]), int(cic_spec["extracted_size_cap_bytes"]), cic_spec,
        )
        atomic_csv(output / "ckdb_d0_p3_cic_inventory.csv", cic_rows)
    except BoundaryFailure as exc:
        verdict = industrial_failure_verdict(exc.reason_code)
        verdict.update({
            "details": exc.details,
            "contract_sha256": CONTRACT_SHA256,
            "execution_plan_sha256": PLAN_SHA256,
            "appendix_sha256": appendix["appendix_sha256"],
            "packet_decode_count": 0,
            "labels_read": 0,
            "attack_or_fault_members_extracted": 0,
            "final_opened": 0,
            "models_loaded": 0,
            "training_performed": False,
            "hpc_submitted": 0,
        })
        verdict = identity_json(verdict)
        atomic_json(output / "ckdb_d0_p3_boundary_verdict.json", verdict)
        atomic_json(output / "ckdb_d0_p3_verdict.json", verdict)
        write_sha256sums(output)
        print(json.dumps(verdict, indent=2, sort_keys=True))
        return

    verdict = identity_json({
        "status": "CKDB_D0_P3_BOUNDARY_VERIFIED",
        "contract_sha256": CONTRACT_SHA256,
        "execution_plan_sha256": PLAN_SHA256,
        "appendix_sha256": appendix["appendix_sha256"],
        "unsw_archive_members": len(unsw),
        "pnnl": pnnl,
        "cic": cic,
        "combined_industrial_domains": 3,
        "minimum_industrial_domains": 3,
        "packet_decode_count": 0,
        "labels_read": 0,
        "attack_or_fault_members_extracted": 0,
        "final_opened": 0,
        "models_loaded": 0,
        "training_performed": False,
        "hpc_submitted": 0,
        "replacement_corpus_allowed": False,
    })
    atomic_json(output / "ckdb_d0_p3_boundary_verdict.json", verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))


def command_extract(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    appendix = validate_launch_appendix(args.appendix, args.appendix_sidecar, plan)
    boundary = read_json(args.boundary_verdict)
    if boundary.get("status") != "CKDB_D0_P3_BOUNDARY_VERIFIED":
        raise ContractError("boundary verification did not pass")
    if identity_json(boundary).get("self_sha256") != boundary.get("self_sha256"):
        raise ContractError("boundary verdict identity drift")
    if boundary.get("appendix_sha256") != appendix["appendix_sha256"]:
        raise ContractError("boundary/appendix identity drift")
    objects = _appendix_objects(appendix)
    destination = Path(args.destination).resolve()
    extraction_root = (destination / "boundary_verified").resolve()
    rows: List[Dict[str, Any]] = []
    selections = {
        "pnnl_opaque_tar": sorted(
            list(boundary["pnnl"]["electric_normal_members"]) +
            list(boundary["pnnl"]["gas_normal_members"])
        ),
        "cic_benign_pcaps": sorted(boundary["cic"]["benign_members"]),
    }
    unsw_spec = objects["unsw_pcaps"]
    unsw_inventory = inspect_archive(
        _object_path(destination, unsw_spec), str(unsw_spec["expected_archive_kind"]),
        int(unsw_spec["extracted_size_cap_bytes"]),
    )
    selections["unsw_pcaps"] = sorted(
        item.path for item in unsw_inventory
        if item.member_type == "file" and item.path.lower().endswith(PCAP_SUFFIXES)
    )
    for object_id in OBJECT_IDS:
        spec = objects[object_id]
        candidate = str(spec["candidate_id"])
        extracted = safe_extract_members(
            _object_path(destination, spec), str(spec["expected_archive_kind"]), selections[object_id],
            extraction_root / candidate, int(spec["extracted_size_cap_bytes"]),
        )
        for row in extracted:
            row.update({"object_id": object_id, "candidate_id": candidate})
            rows.append(row)
    manifest = identity_json({
        "schema_version": "CKDB_D0_P3_EXTRACTION_MANIFEST_V1",
        "status": "ALLOWLISTED_BENIGN_EXTRACTION_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "execution_plan_sha256": PLAN_SHA256,
        "boundary_verdict_sha256": boundary["self_sha256"],
        "attack_or_fault_members_extracted": 0,
        "members": rows,
    })
    atomic_json(args.output, manifest)
    atomic_csv(Path(args.output).with_suffix(".csv"), rows)
    print(json.dumps({"status": manifest["status"], "members": len(rows)}, indent=2))


def _checkpoint_identity(spec: Mapping[str, Any]) -> str:
    keys = ("candidate_id", "source_unit_id", "pcap_member", "coarse_domain", "immutable_role", "local_path", "sha256")
    return sha256_bytes(canonical_json({key: spec[key] for key in keys}))


def _census_report(verdict: Mapping[str, Any]) -> str:
    gaps = verdict.get("coverage_gaps", [])
    return "\n".join([
        "# CKDB D0-P3 census result",
        "",
        "- Status: `%s`" % verdict["status"],
        "- I1 scale: `%s` (%s sessions, %s tokens)" % (
            verdict["i1_scale_status"], verdict["i1_fit_sessions"], verdict["i1_fit_tokens"],
        ),
        "- Coverage: `%s`" % verdict["coverage_status"],
        "- Gaps: `%s`" % (", ".join(gaps) if gaps else "none"),
        "- Holdout: `%s`; per-device reporting is mandatory" % HOLDOUT_WARNING,
        "- Claim cap: `FORBID_BROAD_UNSEEN_INDUSTRIAL_DOMAIN_CLAIM_BEFORE_FINAL`",
        "- Training/embedding/threshold/HPC/FINAL: not authorized and not performed",
        "",
    ])


def command_census(args: argparse.Namespace) -> None:
    plan = verify_plan(args.contract, args.plan)
    boundary = read_json(args.boundary_verdict)
    member_plan = read_json(args.member_plan)
    members = validate_census_member_plan(member_plan, boundary, args.boundary_root)
    decoder_spec = plan["decoder_contract"]
    decoder_path = (Path(args.repo_root).resolve() / str(decoder_spec["path"])).resolve()
    decoder = import_pinned_decoder(decoder_path, str(decoder_spec["sha256"]))
    output = Path(args.output_root).resolve()
    checkpoint_root = output / "checkpoints"
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    checkpoint_paths: List[Path] = []
    checkpoint_report: List[Dict[str, Any]] = []
    for index, member in enumerate(members, 1):
        identity = _checkpoint_identity(member)
        csv_path = checkpoint_root / ("%04d_%s.csv" % (index, identity[:16]))
        json_path = checkpoint_root / ("%04d_%s.json" % (index, identity[:16]))
        reused = False
        if csv_path.is_file() and json_path.is_file():
            saved = read_json(json_path)
            reused = saved.get("member_identity_sha256") == identity and saved.get("csv_sha256") == sha256_file(csv_path)
        if not reused:
            rows = census_member(decoder, args.tshark, member)
            atomic_csv(csv_path, rows)
            atomic_json(json_path, {
                "status": "MEMBER_CENSUS_CHECKPOINT_COMPLETE",
                "member_identity_sha256": identity,
                "csv_sha256": sha256_file(csv_path),
                "session_rows": len(rows),
                "completed_utc": utc_now(),
            })
        checkpoint_paths.append(csv_path)
        checkpoint_report.append({
            "index": index, "candidate_id": member["candidate_id"],
            "source_unit_id": member["source_unit_id"], "pcap_member": member["pcap_member"],
            "checkpoint": str(csv_path), "sha256": sha256_file(csv_path), "reused": reused,
        })
        print("CKDB_D0_P3_CENSUS_PROGRESS %d/%d reused=%s member=%s" % (
            index, len(members), str(reused).lower(), member["pcap_member"],
        ), flush=True)

    region_rows, base_verdict = aggregate_census(iter_checkpoint_rows(checkpoint_paths))
    marginal_rows, joint_rows, source_rows = descriptor_tables(iter_checkpoint_rows(checkpoint_paths))
    holdout_rows = [row for row in members if row["immutable_role"] == "EXTERNAL_BENIGN_REPORT_HOLDOUT"]
    excluded_rows = [
        {"kind": "PNNL", "identity": "attack/system_fault/ambiguous", "reason": "BOUNDARY_EXCLUDED"},
        {"kind": "FINAL", "identity": "frozen denylist", "reason": "NOT_OPENED"},
    ]
    atomic_csv(output / "ckdb_d0_p3_member_manifest.csv", members)
    atomic_csv(output / "ckdb_d0_p3_holdout_manifest.csv", holdout_rows)
    atomic_csv(output / "ckdb_d0_p3_excluded_units.csv", excluded_rows)
    atomic_csv(output / "ckdb_d0_p3_source_census.csv", source_rows)
    atomic_csv(output / "ckdb_d0_p3_descriptor_marginals.csv", marginal_rows)
    atomic_csv(output / "ckdb_d0_p3_descriptor_joint.csv", joint_rows)
    atomic_csv(output / "ckdb_d0_p3_region_support.csv", region_rows)
    atomic_csv(output / "ckdb_d0_p3_checkpoint_report.csv", checkpoint_report)
    verdict = identity_json(dict(base_verdict, **{
        "status": "CKDB_D0_P3_CENSUS_COMPLETE",
        "contract_sha256": CONTRACT_SHA256,
        "execution_plan_sha256": PLAN_SHA256,
        "boundary_verdict_sha256": boundary["self_sha256"],
        "member_plan_sha256": sha256_file(args.member_plan),
        "combined_industrial_domains": 3,
        "industrial_claim_cap": "FORBID_BROAD_UNSEEN_INDUSTRIAL_DOMAIN_CLAIM_BEFORE_FINAL",
        "attack_or_fault_members_used": 0,
        "labels_read": 0,
        "final_opened": 0,
        "models_loaded": 0,
        "training_performed": False,
        "embeddings_generated": 0,
        "thresholds_selected": 0,
        "hpc_submitted": 0,
    }))
    atomic_json(output / "ckdb_d0_p3_verdict.json", verdict)
    atomic_text(output / "ckdb_d0_p3_result_report.md", _census_report(verdict))
    write_sha256sums(output)
    deterministic_package(output, args.pullback)
    atomic_text(Path(str(args.pullback) + ".sha256"), "%s  %s\n" % (sha256_file(args.pullback), Path(args.pullback).name))
    print(json.dumps(verdict, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, default=root / "runs/mainline_docs/ckdb_d0_p3_combined_large_download_and_census_preregistered_20260818.md")
    parser.add_argument("--plan", type=Path, default=root / "runs/mainline_docs/ckdb_d0_p3_execution_plan_20260818.json")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="offline identity validation only")
    validate.set_defaults(func=command_validate)
    preflight = sub.add_parser("preflight", help="offline reviewed-appendix and fresh-storage gate")
    preflight.add_argument("--appendix", type=Path, required=True)
    preflight.add_argument("--appendix-sidecar", type=Path, required=True)
    preflight.add_argument("--destination", type=Path, required=True)
    preflight.add_argument("--inode-use-fraction", type=float, required=True)
    preflight.add_argument("--output", type=Path, required=True)
    preflight.set_defaults(func=command_preflight)
    transfer = sub.add_parser("transfer", help="authorization-gated resumable transfer")
    transfer.add_argument("--appendix", type=Path, required=True)
    transfer.add_argument("--appendix-sidecar", type=Path, required=True)
    transfer.add_argument("--authorization", type=Path, required=True)
    transfer.add_argument("--preflight", type=Path, required=True)
    transfer.add_argument("--runtime-secrets", type=Path, required=True)
    transfer.add_argument("--repo-root", type=Path, default=root)
    transfer.add_argument("--destination", type=Path, required=True)
    transfer.set_defaults(func=command_transfer)
    boundary = sub.add_parser("boundary", help="inventory-only PNNL/CIC benign-boundary verification")
    boundary.add_argument("--appendix", type=Path, required=True)
    boundary.add_argument("--appendix-sidecar", type=Path, required=True)
    boundary.add_argument("--destination", type=Path, required=True)
    boundary.add_argument("--output-root", type=Path, required=True)
    boundary.set_defaults(func=command_boundary)
    extract = sub.add_parser("extract", help="extract only boundary-allowlisted benign capture members")
    extract.add_argument("--appendix", type=Path, required=True)
    extract.add_argument("--appendix-sidecar", type=Path, required=True)
    extract.add_argument("--boundary-verdict", type=Path, required=True)
    extract.add_argument("--destination", type=Path, required=True)
    extract.add_argument("--output", type=Path, required=True)
    extract.set_defaults(func=command_extract)
    census = sub.add_parser("census", help="checkpointed benign-only causal coverage census")
    census.add_argument("--boundary-verdict", type=Path, required=True)
    census.add_argument("--member-plan", type=Path, required=True)
    census.add_argument("--boundary-root", type=Path, required=True)
    census.add_argument("--repo-root", type=Path, default=root)
    census.add_argument("--tshark", required=True)
    census.add_argument("--output-root", type=Path, required=True)
    census.add_argument("--pullback", type=Path, required=True)
    census.set_defaults(func=command_census)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.func(args)
        return 0
    except BoundaryFailure as exc:
        output = getattr(args, "output_root", None)
        if output is not None:
            root = Path(output)
            root.mkdir(parents=True, exist_ok=True)
            verdict = identity_json(dict(industrial_failure_verdict(exc.reason_code), details=exc.details))
            atomic_json(root / "ckdb_d0_p3_verdict.json", verdict)
            write_sha256sums(root)
        print("CKDB_D0_P3_SCIENTIFIC_STOP %s" % exc, file=sys.stderr)
        return 2
    except (ContractError, SafetyError, TransferError) as exc:
        output = getattr(args, "output_root", None)
        if output is not None:
            record_engineering_failure(Path(output), exc)
        print("CKDB_D0_P3_FAIL %s: %s" % (type(exc).__name__, exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
