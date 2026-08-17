#!/usr/bin/env python3
"""CKDB D0-P1 frozen external benign-corpus metadata audit.

The module is intentionally split into pure validation/audit helpers and an
explicit ``execute`` command. Importing it performs no network request.  It
never opens PCAP, model, label, CKDA report, HPC, or FINAL assets.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import json
import math
import os
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.error
import urllib.request
import http.cookiejar
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple


ISSUE = "issue27ckdb_d0_p1_external_metadata_audit_v1_2026-08-17"
CONTRACT_SHA256 = "9e96ad2860f812595d51376bc7b0bc1c3ae30e264e1918c946750689d363a3ba"
PLAN_SHA256 = "ca28462274bd0fe2256e8eefaead9bfc6e768b74f2dbc99a89479e34a3d46bfe"
CANDIDATES = ("UNSW_IOTRAFFIC", "CIC_MODBUS_2023")
TIER_A_CAP = 20 * 1024 * 1024
TIER_B_CAP = 128 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200.0
FINAL_MARKERS = (
    "cooler-motor",
    "seed37",
    "seed_37",
    "seed-37",
    "seed47",
    "seed_47",
    "seed-47",
)
PROHIBITED_ARCHIVE_SUFFIXES = (
    ".pcap",
    ".pcapng",
    ".exe",
    ".dll",
    ".so",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".jar",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
)
PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1",
    b"\xa1\xb2\xc3\xd4",
    b"\x4d\x3c\xb2\xa1",
    b"\xa1\xb2\x3c\x4d",
    b"\x0a\x0d\x0d\x0a",
}
LONG_TCP_PACKET_CUT = 256
LONG_TCP_DURATION_CUT = 300.0
DRYAD_HOST = "datadryad.org"
DRYAD_FILE_PREFIX = "/downloads/file_stream/"
DRYAD_CHALLENGE_PATH = "/.within.website/x/cmd/anubis/api/pass-challenge"
DRYAD_ASSET_HOST = "dryad-assetstore-merritt-west.s3.us-west-2.amazonaws.com"
DRYAD_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)

RETRIEVAL_FIELDS = (
    "candidate_id",
    "object_id",
    "tier",
    "request_url",
    "final_url",
    "retrieval_utc",
    "http_status",
    "content_type",
    "published_size_text",
    "local_bytes",
    "sha256",
    "expected_kind",
    "safety_status",
    "reason_code",
)
IDENTITY_FIELDS = (
    "candidate_id",
    "official_owner",
    "official_landing_url",
    "dataset_doi",
    "paper_doi",
    "license_terms",
    "research_use_status",
    "redistribution_status",
    "access_requirement",
    "identity_status",
    "reason_code",
    "evidence_object_ids",
)
LINEAGE_FIELDS = (
    "candidate_id",
    "route_id",
    "comparison_source",
    "collection_relation",
    "positive_evidence",
    "claim_ceiling",
    "reason_code",
)
BENIGN_FIELDS = (
    "candidate_id",
    "source_boundary_id",
    "benign_boundary",
    "normal_claim",
    "attack_material_separate",
    "row_labels_required",
    "eligibility_status",
    "reason_code",
    "evidence_object_ids",
)
DEVICE_FIELDS = (
    "candidate_id",
    "source_unit_id",
    "published_name",
    "usage_domain",
    "embodiment",
    "source_unit",
    "cluster_id",
    "independent_domain_counted",
    "first_seen",
    "last_seen",
    "published_packets",
    "published_flows",
    "reason_code",
)
COVERAGE_FIELDS = (
    "candidate_id",
    "usage_domain",
    "embodiment",
    "raw_source_units",
    "post_cluster_independent_domains",
    "transport_evidence",
    "long_bidirectional_tcp_evidence",
    "long_tcp_definition",
    "long_tcp_flow_count",
    "long_tcp_flow_fraction",
    "reason_code",
)
HORIZON_FIELDS = (
    "candidate_id",
    "flow_rows",
    "packet_count_q50",
    "packet_count_q90",
    "packet_count_q99",
    "duration_seconds_q50",
    "duration_seconds_q90",
    "duration_seconds_q99",
    "fraction_packet_count_gt_256",
    "fraction_long_bidirectional_tcp",
    "horizon_status",
    "published_packets",
    "published_flows",
    "i1_scale_status",
    "reason_code",
)
ALLOWLIST_FIELDS = (
    "candidate_id",
    "object_id",
    "official_url",
    "expected_size_or_ceiling",
    "expected_sha256",
    "destination_identity",
    "intended_use",
    "authorization_status",
)
MEMBER_FIELDS = (
    "candidate_id",
    "object_id",
    "member_name",
    "compressed_bytes",
    "uncompressed_bytes",
    "sha256",
    "safety_status",
)


class ContractError(RuntimeError):
    pass


class RetrievalError(RuntimeError):
    pass


class SafetyError(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    os.replace(str(temporary), str(path))


def atomic_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
    os.replace(str(temporary), str(path))


def write_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("." + path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        for row in rows:
            missing = set(fields) - set(row)
            if missing:
                raise ContractError("missing CSV fields: " + ",".join(sorted(missing)))
            writer.writerow({field: row[field] for field in fields})
    os.replace(str(temporary), str(path))


def read_csv(path: Path) -> List[Dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def verify_identity(contract: Path, plan_path: Path) -> Mapping[str, Any]:
    if sha256_file(contract) != CONTRACT_SHA256:
        raise ContractError("FROZEN contract SHA drift")
    if sha256_file(plan_path) != PLAN_SHA256:
        raise ContractError("retrieval plan SHA drift")
    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    if tuple(plan.get("candidate_order", [])) != CANDIDATES:
        raise ContractError("candidate set/order drift")
    if plan.get("contract_sha256") != CONTRACT_SHA256:
        raise ContractError("plan/contract identity mismatch")
    if int(plan.get("tier_a_candidate_cap_bytes", -1)) != TIER_A_CAP:
        raise ContractError("Tier A cap drift")
    if int(plan.get("tier_b_candidate_cap_bytes", -1)) != TIER_B_CAP:
        raise ContractError("Tier B cap drift")
    objects = list(plan.get("objects", []))
    object_ids = [str(item.get("object_id", "")) for item in objects]
    if len(object_ids) != len(set(object_ids)) or not object_ids:
        raise ContractError("object identity missing or duplicated")
    for item in objects:
        candidate = str(item.get("candidate_id", ""))
        if candidate not in CANDIDATES:
            raise ContractError("unexpected candidate in plan")
        tier = str(item.get("tier", ""))
        if tier not in {"A", "B"}:
            raise ContractError("invalid tier")
        url = str(item.get("url", ""))
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ContractError("only explicit HTTPS objects are permitted")
        fail_if_prohibited_text(url, "retrieval_plan")
    future = list(plan.get("future_large_objects", []))
    if {str(item.get("candidate_id", "")) for item in future} != set(CANDIDATES):
        raise ContractError("future large-object allowlist must cover both candidates")
    if any(str(item.get("object_id", "")) in set(object_ids) for item in future):
        raise ContractError("future large object leaked into retrieval objects")
    return plan


def fail_if_prohibited_text(value: Any, context: str) -> None:
    lowered = str(value).replace("\\", "/").lower()
    marker = next((item for item in FINAL_MARKERS if item in lowered), None)
    if marker is not None:
        raise ContractError("FINAL exclusion failure context=%s marker=%s" % (context, marker))


def ensure_empty_output_root(path: Path) -> None:
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ContractError("output root must be new and empty")
    path.mkdir(parents=True, exist_ok=True)


def sniff_kind(prefix: bytes) -> str:
    lowered = prefix[:8192].lstrip().lower()
    if prefix[:4] in PCAP_MAGICS:
        return "pcap"
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"PK\x05\x06"):
        return "zip"
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html"):
        return "html"
    return "text"


def validate_object_kind(path: Path, expected_kind: str) -> None:
    with Path(path).open("rb") as handle:
        prefix = handle.read(8192)
    observed = sniff_kind(prefix)
    if observed == "pcap":
        raise SafetyError("PCAP magic prohibited")
    if expected_kind == "html" and observed != "html":
        raise SafetyError("expected HTML")
    if expected_kind in {"csv", "markdown"} and observed == "html":
        raise SafetyError("HTML masquerading as data")
    if expected_kind == "zip_flow_metadata" and observed != "zip":
        raise SafetyError("expected ZIP flow metadata")
    if expected_kind in {"csv", "markdown"} and observed == "zip":
        raise SafetyError("unexpected archive")


def _response_status(response: Any) -> int:
    value = getattr(response, "status", None)
    if value is None:
        value = response.getcode()
    return int(value)


def _response_header(response: Any, name: str) -> str:
    headers = getattr(response, "headers", {})
    if hasattr(headers, "get"):
        return str(headers.get(name, ""))
    return ""


def _is_dryad_file_stream(url: str) -> bool:
    parsed = urllib.parse.urlparse(str(url))
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() == DRYAD_HOST
        and parsed.path.startswith(DRYAD_FILE_PREFIX)
    )


def _parse_anubis_challenge(payload: bytes) -> Mapping[str, Any]:
    if len(payload) > 2 * 1024 * 1024:
        raise RetrievalError("Dryad challenge document exceeds safety ceiling")
    text = payload.decode("utf-8", errors="strict")
    match = re.search(
        r'<script[^>]+id=["\']anubis_challenge["\'][^>]*>(.*?)</script>',
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match is None:
        raise RetrievalError("Dryad response is neither data nor a recognized Anubis challenge")
    try:
        value = json.loads(html.unescape(match.group(1)).strip())
    except (ValueError, TypeError) as error:
        raise RetrievalError("invalid Dryad Anubis challenge JSON") from error
    if not isinstance(value, dict):
        raise RetrievalError("incomplete Dryad Anubis challenge")
    if {"challenge", "rules"}.issubset(value):
        challenge = value.get("challenge")
        rules = value.get("rules")
        if not isinstance(challenge, dict) or not isinstance(rules, dict):
            raise RetrievalError("incomplete Dryad Anubis challenge")
        value = dict(challenge)
        value["algorithm"] = rules.get("algorithm")
        if int(value.get("difficulty", -1)) != int(rules.get("difficulty", -2)):
            raise RetrievalError("Dryad Anubis challenge/rules difficulty mismatch")
    required = {"algorithm", "difficulty", "id", "randomData"}
    if not required.issubset(value):
        raise RetrievalError("incomplete Dryad Anubis challenge")
    if str(value["algorithm"]) != "fast":
        raise RetrievalError("unsupported Dryad Anubis algorithm")
    difficulty = int(value["difficulty"])
    if difficulty < 1 or difficulty > 6:
        raise RetrievalError("Dryad Anubis difficulty outside frozen engineering bound")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,256}", str(value["id"])):
        raise RetrievalError("invalid Dryad Anubis challenge id")
    if not re.fullmatch(r"[A-Za-z0-9+/=_-]{8,4096}", str(value["randomData"])):
        raise RetrievalError("invalid Dryad Anubis random data")
    return value


def _solve_anubis_pow(random_data: str, difficulty: int) -> Tuple[int, str, int]:
    prefix = "0" * int(difficulty)
    started = time.monotonic()
    nonce = 0
    while True:
        digest = hashlib.sha256((str(random_data) + str(nonce)).encode("utf-8")).hexdigest()
        if digest.startswith(prefix):
            elapsed_ms = max(1, int((time.monotonic() - started) * 1000))
            return nonce, digest, elapsed_ms
        nonce += 1


def _browser_headers(referer: str = "") -> Dict[str, str]:
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin" if referer else "none",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": DRYAD_BROWSER_USER_AGENT,
    }
    if referer:
        headers["Referer"] = referer
    return headers


class Fetcher:
    def __init__(self, opener: Any = None, allow_dryad_anubis: bool = False) -> None:
        self.opener = opener or urllib.request.urlopen
        self.allow_dryad_anubis = bool(allow_dryad_anubis)
        self._dryad_cookie_jar = http.cookiejar.CookieJar()
        self._dryad_opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self._dryad_cookie_jar)
        )

    def _open_dryad_file(
        self, url: str, offset: int, allowed_final_hosts: Sequence[str]
    ) -> Any:
        if not self.allow_dryad_anubis:
            raise RetrievalError("Dryad Anubis access requires explicit user authorization flag")
        if not _is_dryad_file_stream(url):
            raise RetrievalError("Dryad Anubis adapter refused non-file-stream URL")
        initial = urllib.request.Request(url, headers=_browser_headers())
        try:
            response = self._dryad_opener.open(initial, timeout=120)
        except urllib.error.HTTPError as error:
            payload = error.read(2 * 1024 * 1024 + 1)
            error.close()
            challenge = _parse_anubis_challenge(payload)
        else:
            content_type = _response_header(response, "Content-Type").lower()
            final_url = str(response.geturl())
            if "text/html" not in content_type and _is_dryad_file_stream(final_url):
                return response
            payload = response.read(2 * 1024 * 1024 + 1)
            response.close()
            challenge = _parse_anubis_challenge(payload)

        nonce, digest, elapsed_ms = _solve_anubis_pow(
            str(challenge["randomData"]), int(challenge["difficulty"])
        )
        pass_url = urllib.parse.urlunparse(
            (
                "https",
                DRYAD_HOST,
                DRYAD_CHALLENGE_PATH,
                "",
                urllib.parse.urlencode(
                    {
                        "id": str(challenge["id"]),
                        "response": digest,
                        "nonce": nonce,
                        "redir": url,
                        "elapsedTime": elapsed_ms,
                    }
                ),
                "",
            )
        )
        headers = _browser_headers(referer=url)
        if offset:
            headers["Range"] = "bytes=%d-" % offset
        passed = urllib.request.Request(pass_url, headers=headers)
        response = self._dryad_opener.open(passed, timeout=120)
        final_url = str(response.geturl())
        final_parsed = urllib.parse.urlparse(final_url)
        allowed = {str(item).lower() for item in allowed_final_hosts}
        final_host = (final_parsed.hostname or "").lower()
        final_is_official_payload = (
            final_parsed.scheme == "https"
            and final_host in allowed
            and (
                (
                    final_host == DRYAD_HOST
                    and (
                        final_parsed.path.startswith(DRYAD_FILE_PREFIX)
                        or final_parsed.path == DRYAD_CHALLENGE_PATH
                    )
                )
                or (final_host == DRYAD_ASSET_HOST and final_parsed.path.startswith("/v3/"))
            )
        )
        if not final_is_official_payload:
            response.close()
            raise RetrievalError("Dryad challenge did not return the authorized file stream")
        if "text/html" in _response_header(response, "Content-Type").lower():
            response.close()
            raise RetrievalError("Dryad challenge remained unresolved")
        return response

    def fetch(self, spec: Mapping[str, Any], destination: Path) -> Dict[str, Any]:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        part = destination.with_name("." + destination.name + ".part")
        resume_meta = destination.with_name("." + destination.name + ".part.json")
        identity = {
            "object_id": spec["object_id"],
            "url": spec["url"],
            "expected_kind": spec["expected_kind"],
            "max_bytes": int(spec["max_bytes"]),
        }
        offset = 0
        if part.exists() or resume_meta.exists():
            if not (part.exists() and resume_meta.exists()):
                raise RetrievalError("incomplete resume identity pair")
            observed = json.loads(resume_meta.read_text(encoding="utf-8"))
            if observed != identity:
                raise RetrievalError("resume identity mismatch")
            offset = part.stat().st_size
        else:
            atomic_json(resume_meta, identity)

        url = str(spec["url"])
        if _is_dryad_file_stream(url):
            response = self._open_dryad_file(url, offset, spec["allowed_final_hosts"])
        else:
            headers = {"User-Agent": "CKDB-D0-P1-metadata-audit/1"}
            if offset:
                headers["Range"] = "bytes=%d-" % offset
            request = urllib.request.Request(url, headers=headers)
            response = self.opener(request, timeout=120)
        try:
            status = _response_status(response)
            content_type = _response_header(response, "Content-Type")
            if status not in {200, 206}:
                raise RetrievalError("HTTP status %d" % status)
            append = bool(offset and status == 206)
            if offset and status == 206:
                content_range = _response_header(response, "Content-Range")
                if not content_range.startswith("bytes %d-" % offset):
                    raise RetrievalError("resume Content-Range mismatch")
            if offset and status == 200:
                offset = 0
                append = False
            response_url = str(response.geturl())
            final_host = (urllib.parse.urlparse(response_url).hostname or "").lower()
            allowed = {str(item).lower() for item in spec["allowed_final_hosts"]}
            if final_host not in allowed:
                raise RetrievalError("unapproved redirect host: " + final_host)
            final_url = url if _is_dryad_file_stream(url) else response_url
            mode = "ab" if append else "wb"
            written = offset
            with part.open(mode) as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    written += len(block)
                    if written > int(spec["max_bytes"]):
                        raise RetrievalError("object byte ceiling exceeded")
                    handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            response.close()

        if not part.is_file() or part.stat().st_size == 0:
            raise RetrievalError("empty download")
        try:
            validate_object_kind(part, str(spec["expected_kind"]))
        except SafetyError as error:
            quarantine = destination.parent / "_quarantine"
            quarantine.mkdir(parents=True, exist_ok=True)
            quarantined = quarantine / (destination.name + ".rejected")
            os.replace(str(part), str(quarantined))
            atomic_json(
                quarantine / (destination.name + ".rejected.json"),
                {
                    "bytes": quarantined.stat().st_size,
                    "object_id": spec["object_id"],
                    "reason": str(error),
                    "sha256": sha256_file(quarantined),
                    "status": "QUARANTINED_SAFETY_FAILURE",
                },
            )
            resume_meta.unlink()
            raise
        os.replace(str(part), str(destination))
        resume_meta.unlink()
        return {
            "candidate_id": spec["candidate_id"],
            "object_id": spec["object_id"],
            "tier": spec["tier"],
            "request_url": spec["url"],
            "final_url": final_url,
            "retrieval_utc": utc_now(),
            "http_status": status,
            "content_type": content_type,
            "published_size_text": spec["published_size_text"],
            "local_bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "expected_kind": spec["expected_kind"],
            "safety_status": "PASS",
            "reason_code": "OK",
        }


def enforce_candidate_tier_cap(rows: Sequence[Mapping[str, Any]], candidate: str, tier: str) -> None:
    total = sum(
        int(row["local_bytes"])
        for row in rows
        if row["candidate_id"] == candidate and row["tier"] == tier
    )
    cap = TIER_A_CAP if tier == "A" else TIER_B_CAP
    if total > cap:
        raise SafetyError("candidate tier byte cap exceeded")


def _safe_member_name(name: str) -> str:
    normalized = name.replace("\\", "/")
    parts = normalized.split("/")
    if not normalized or normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized):
        raise SafetyError("absolute archive member")
    if any(part in {"", ".", ".."} for part in parts):
        raise SafetyError("archive traversal/empty segment")
    lowered = normalized.lower()
    if lowered.endswith(PROHIBITED_ARCHIVE_SUFFIXES):
        raise SafetyError("prohibited or nested archive member: " + normalized)
    return normalized


def inspect_flow_zip(path: Path) -> Tuple[List[Dict[str, Any]], List[zipfile.ZipInfo]]:
    manifest: List[Dict[str, Any]] = []
    with zipfile.ZipFile(path) as archive:
        infos = [info for info in archive.infolist() if not info.is_dir()]
        if not infos:
            raise SafetyError("empty flow archive")
        total_uncompressed = 0
        csv_infos: List[zipfile.ZipInfo] = []
        for info in infos:
            name = _safe_member_name(info.filename)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise SafetyError("archive link member")
            if info.flag_bits & 0x1:
                raise SafetyError("encrypted archive member")
            if not name.lower().endswith(".csv"):
                raise SafetyError("non-CSV member in flow archive")
            total_uncompressed += int(info.file_size)
            if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED:
                raise SafetyError("archive uncompressed ceiling exceeded")
            if info.compress_size == 0 and info.file_size > 0:
                raise SafetyError("invalid compression size")
            if info.compress_size and info.file_size / float(info.compress_size) > MAX_COMPRESSION_RATIO:
                raise SafetyError("archive compression ratio exceeded")
            digest = hashlib.sha256()
            with archive.open(info) as handle:
                prefix = handle.read(4)
                if prefix in PCAP_MAGICS:
                    raise SafetyError("PCAP magic in archive")
                digest.update(prefix)
                for block in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(block)
            manifest.append(
                {
                    "candidate_id": "UNSW_IOTRAFFIC",
                    "object_id": "unsw_flows",
                    "member_name": name,
                    "compressed_bytes": int(info.compress_size),
                    "uncompressed_bytes": int(info.file_size),
                    "sha256": digest.hexdigest(),
                    "safety_status": "PASS",
                }
            )
            csv_infos.append(info)
    if len(csv_infos) != 27:
        raise SafetyError("UNSW flow archive must contain exactly 27 CSV members")
    return manifest, csv_infos


def _normalized_field(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.strip().lower())


def _field_lookup(fields: Sequence[str]) -> Dict[str, str]:
    return {_normalized_field(field): field for field in fields}


def validate_flow_header(fields: Sequence[str]) -> Dict[str, str]:
    lookup = _field_lookup(fields)
    required = {
        "ipproto",
        "srcnumpackets",
        "dstnumpackets",
        "flowduration",
        "flowseqnum",
    }
    missing = required - set(lookup)
    if missing:
        raise SafetyError("flow aggregate schema missing: " + ",".join(sorted(missing)))
    forbidden = {
        "rawpayload",
        "payloadhex",
        "payloadbytes",
        "packetbytes",
        "frameraw",
        "packetnumber",
        "packetid",
        "frameno",
    }
    hit = forbidden & set(lookup)
    if hit:
        raise SafetyError("payload/per-packet fields detected: " + ",".join(sorted(hit)))
    return lookup


def _as_float(value: Any) -> float:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return float("nan")
    return result if math.isfinite(result) else float("nan")


def _quantile(values: Sequence[float], probability: float) -> Any:
    clean = sorted(value for value in values if math.isfinite(value))
    if not clean:
        return "UNKNOWN_NO_VALUES"
    position = (len(clean) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return clean[lower]
    weight = position - lower
    return clean[lower] * (1.0 - weight) + clean[upper] * weight


def analyze_unsw_flow_zip(path: Path) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    member_rows, infos = inspect_flow_zip(path)
    packet_counts: List[float] = []
    durations: List[float] = []
    flow_rows = 0
    packet_gt_256 = 0
    long_tcp = 0
    with zipfile.ZipFile(path) as archive:
        for info in infos:
            with archive.open(info) as raw:
                wrapper = io.TextIOWrapper(raw, encoding="utf-8-sig", newline="")
                reader = csv.DictReader(wrapper)
                if reader.fieldnames is None:
                    raise SafetyError("flow CSV has no header")
                lookup = validate_flow_header(reader.fieldnames)
                for row in reader:
                    src = _as_float(row.get(lookup["srcnumpackets"]))
                    dst = _as_float(row.get(lookup["dstnumpackets"]))
                    duration = _as_float(row.get(lookup["flowduration"]))
                    proto = str(row.get(lookup["ipproto"], "")).strip().lower()
                    if not (math.isfinite(src) and math.isfinite(dst) and math.isfinite(duration)):
                        continue
                    packets = src + dst
                    flow_rows += 1
                    packet_counts.append(packets)
                    durations.append(duration)
                    if packets > LONG_TCP_PACKET_CUT:
                        packet_gt_256 += 1
                    is_tcp = proto in {"6", "tcp", "0x06"}
                    if is_tcp and src > 0 and dst > 0 and (
                        packets > LONG_TCP_PACKET_CUT or duration >= LONG_TCP_DURATION_CUT
                    ):
                        long_tcp += 1
    if flow_rows == 0:
        raise SafetyError("no valid aggregate flow rows")
    return (
        {
            "flow_rows": flow_rows,
            "packet_count_q50": _quantile(packet_counts, 0.50),
            "packet_count_q90": _quantile(packet_counts, 0.90),
            "packet_count_q99": _quantile(packet_counts, 0.99),
            "duration_seconds_q50": _quantile(durations, 0.50),
            "duration_seconds_q90": _quantile(durations, 0.90),
            "duration_seconds_q99": _quantile(durations, 0.99),
            "fraction_packet_count_gt_256": packet_gt_256 / float(flow_rows),
            "fraction_long_bidirectional_tcp": long_tcp / float(flow_rows),
            "long_tcp_flow_count": long_tcp,
        },
        member_rows,
    )


def quarantine_download(path: Path, reason: str) -> Path:
    path = Path(path)
    quarantine = path.parent / "_quarantine"
    quarantine.mkdir(parents=True, exist_ok=True)
    destination = quarantine / (path.name + ".rejected")
    os.replace(str(path), str(destination))
    atomic_json(
        quarantine / (path.name + ".rejected.json"),
        {
            "bytes": destination.stat().st_size,
            "reason": reason,
            "sha256": sha256_file(destination),
            "status": "QUARANTINED_SAFETY_FAILURE",
        },
    )
    return destination


def strip_html(value: str) -> str:
    value = re.sub(r"<script\b[^>]*>.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b[^>]*>.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def object_path(root: Path, object_id: str) -> Path:
    matches = list(Path(root).glob("*/" + object_id + ".*"))
    if len(matches) != 1:
        raise ContractError("expected one retrieved object: " + object_id)
    return matches[0]


def load_text_object(root: Path, object_id: str) -> str:
    return object_path(root, object_id).read_text(encoding="utf-8-sig", errors="replace")


def _require_phrases(text: str, phrases: Sequence[str], context: str) -> None:
    lowered = text.lower()
    missing = [phrase for phrase in phrases if phrase.lower() not in lowered]
    if missing:
        raise ContractError("primary evidence phrase missing %s: %s" % (context, missing))


def parse_unsw_devices(path: Path) -> List[Dict[str, Any]]:
    rows = read_csv(path)
    if len(rows) != 27:
        raise ContractError("UNSW device census must contain 27 rows")
    if not rows:
        raise ContractError("empty UNSW device census")
    lookup = _field_lookup(list(rows[0]))
    required = {"devicename", "firstseen", "lastseen", "numberofpackets", "numberofflows"}
    if required - set(lookup):
        raise ContractError("UNSW device summary schema drift")
    result: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, 1):
        name = str(row[lookup["devicename"]]).strip()
        if not name:
            raise ContractError("blank UNSW device name")
        result.append(
            {
                "candidate_id": "UNSW_IOTRAFFIC",
                "source_unit_id": "UNSW_DEVICE_%03d" % index,
                "published_name": name,
                "usage_domain": "CONSUMER_HOME",
                "embodiment": "PHYSICAL",
                "source_unit": "DEVICE",
                "cluster_id": "UNSW_DEVICE_%03d" % index,
                "independent_domain_counted": 1,
                "first_seen": str(row[lookup["firstseen"]]).strip(),
                "last_seen": str(row[lookup["lastseen"]]).strip(),
                "published_packets": str(row[lookup["numberofpackets"]]).strip(),
                "published_flows": str(row[lookup["numberofflows"]]).strip(),
                "reason_code": "OK",
            }
        )
    return result


def parse_cic_roles(page_text: str) -> List[Dict[str, Any]]:
    text = strip_html(page_text)
    phrases = (
        "simulated substation network",
        "IED1A",
        "IED4C",
        "IED1B",
        "Secure SCADA HMI",
        "Normal SCADA HMI",
        "Central Agent",
    )
    _require_phrases(text, phrases, "CIC roles")
    roles = ("IED1A", "IED4C", "IED1B", "Secure SCADA HMI", "Normal SCADA HMI", "Central Agent")
    result: List[Dict[str, Any]] = []
    for index, name in enumerate(roles, 1):
        result.append(
            {
                "candidate_id": "CIC_MODBUS_2023",
                "source_unit_id": "CIC_ROLE_%03d" % index,
                "published_name": name,
                "usage_domain": "INDUSTRIAL_PROCESS",
                "embodiment": "SIMULATED",
                "source_unit": "ROLE",
                "cluster_id": "CIC_SIMULATED_SUBSTATION_1",
                "independent_domain_counted": 1 if index == 1 else 0,
                "first_seen": "UNKNOWN_NOT_PUBLISHED",
                "last_seen": "UNKNOWN_NOT_PUBLISHED",
                "published_packets": "UNKNOWN_NOT_PUBLISHED",
                "published_flows": "UNKNOWN_NOT_PUBLISHED",
                "reason_code": "SHARED_SIMULATOR_CLUSTER",
            }
        )
    return result


def cluster_count(rows: Sequence[Mapping[str, Any]], candidate: str) -> int:
    return len({str(row["cluster_id"]) for row in rows if row["candidate_id"] == candidate})


def build_identity_rows(evidence_root: Path) -> List[Dict[str, Any]]:
    unsw_page = strip_html(load_text_object(evidence_root, "unsw_official_page"))
    dryad = strip_html(load_text_object(evidence_root, "unsw_dryad_inventory"))
    cic = strip_html(load_text_object(evidence_root, "cic_official_page"))
    cic_inventory = strip_html(load_text_object(evidence_root, "cic_download_inventory"))
    unsw_ok = all(
        phrase.lower() in (unsw_page + " " + dryad).lower()
        for phrase in (
            "UNSW IoT traffic data",
            "10.5061/dryad.w0vt4b94b",
            "27 devices",
            "flows.zip",
            "pcaps.zip",
            "README.md",
            "device_pcap_summary.csv",
        )
    )
    unsw_license_ok = any(
        phrase in dryad.lower()
        for phrase in ("cc0", "licensed for reuse", "creative commons zero")
    )
    unsw_ok = unsw_ok and unsw_license_ok
    cic_ok = all(
        phrase.lower() in cic.lower()
        for phrase in (
            "CIC Modbus dataset 2023",
            "benign dataset",
            "simulated substation network",
            "You may redistribute",
        )
    )
    access = "FORM_REQUIRED" if "first name" in cic_inventory.lower() and "email" in cic_inventory.lower() else "UNKNOWN_ACCESS_PATH"
    return [
        {
            "candidate_id": "UNSW_IOTRAFFIC",
            "official_owner": "UNSW Sydney / Dryad",
            "official_landing_url": "https://datadryad.org/dataset/doi%3A10.5061/dryad.w0vt4b94b",
            "dataset_doi": "10.5061/dryad.w0vt4b94b",
            "paper_doi": "10.1109/IEEEDATA.2025.3602010",
            "license_terms": (
                "DRYAD_PRIMARY_PAGE_LICENSED_FOR_REUSE"
                if unsw_license_ok
                else "AMBIGUOUS_NOT_FOUND_IN_PRIMARY_METADATA"
            ),
            "research_use_status": "PERMITTED" if unsw_license_ok else "AMBIGUOUS",
            "redistribution_status": "PRIMARY_TERMS_APPLY" if unsw_license_ok else "AMBIGUOUS",
            "access_requirement": "DIRECT_HTTPS",
            "identity_status": "PASS" if unsw_ok else "FAIL",
            "reason_code": "OK" if unsw_ok else "PRIMARY_IDENTITY_OR_INVENTORY_INCOMPLETE",
            "evidence_object_ids": "unsw_official_page;unsw_dryad_inventory;unsw_readme",
        },
        {
            "candidate_id": "CIC_MODBUS_2023",
            "official_owner": "Canadian Institute for Cybersecurity, UNB",
            "official_landing_url": "https://www.unb.ca/cic/datasets/modbus-2023.html",
            "dataset_doi": "NO_DATASET_DOI_ON_PRIMARY_PAGE",
            "paper_doi": "PRIMARY_PAGE_CITATION_NO_DOI_ASSERTED",
            "license_terms": "REDISTRIBUTE_REPUBLISH_MIRROR_WITH_CITATION",
            "research_use_status": "PERMITTED_WITH_CITATION",
            "redistribution_status": "PERMITTED_WITH_CITATION",
            "access_requirement": access,
            "identity_status": "PASS" if cic_ok else "FAIL",
            "reason_code": (
                "DOWNLOAD_INVENTORY_FORM_ONLY"
                if cic_ok and access == "FORM_REQUIRED"
                else "PRIMARY_IDENTITY_LICENSE_OR_BOUNDARY_INCOMPLETE"
            ),
            "evidence_object_ids": "cic_official_page;cic_download_inventory",
        },
    ]


def build_lineage_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for candidate in CANDIDATES:
        rows.extend(
            [
                {
                    "candidate_id": candidate,
                    "route_id": "I1_EXTERNAL_SELF_SUPERVISION",
                    "comparison_source": "CKDA_FIT_SELECT_REPORT_AND_TON_IOT",
                    "collection_relation": "NO_KNOWN_OVERLAP",
                    "positive_evidence": "distinct named corpus, owner, testbed, and collection description",
                    "claim_ceiling": "NO_KNOWN_OVERLAP",
                    "reason_code": "NO_POSITIVE_MANIFEST_DISJOINTNESS",
                },
                {
                    "candidate_id": candidate,
                    "route_id": "E3_NETFOUND_CONTROL",
                    "comparison_source": "NETFOUND_PRETRAINING_CORPORA",
                    "collection_relation": "POSSIBLE_OVERLAP",
                    "positive_evidence": "netFound public-pretraining disclosure is not a complete file manifest",
                    "claim_ceiling": "POSSIBLE_OVERLAP",
                    "reason_code": "PRETRAINING_LINEAGE_INCOMPLETE",
                },
                {
                    "candidate_id": candidate,
                    "route_id": "FUTURE_FINAL",
                    "comparison_source": "COOLER_MOTOR_FINAL",
                    "collection_relation": "NO_KNOWN_OVERLAP",
                    "positive_evidence": "distinct corpus owner and device/testbed identity; FINAL not opened",
                    "claim_ceiling": "NO_KNOWN_OVERLAP",
                    "reason_code": "FINAL_MANIFEST_NOT_OPENED",
                },
            ]
        )
    return rows


def build_benign_rows(evidence_root: Path) -> List[Dict[str, Any]]:
    unsw = strip_html(load_text_object(evidence_root, "unsw_readme"))
    cic = strip_html(load_text_object(evidence_root, "cic_official_page"))
    unsw_ok = all(
        phrase.lower() in unsw.lower()
        for phrase in ("interactions", "background", "No ground-truth annotations")
    )
    cic_ok = all(
        phrase.lower() in cic.lower()
        for phrase in ("attack dataset", "benign dataset", "normal network traffic")
    )
    return [
        {
            "candidate_id": "UNSW_IOTRAFFIC",
            "source_boundary_id": "UNSW_WHOLE_CORPUS_ACTIVITY",
            "benign_boundary": "UNLABELED_NORMAL_CLAIM",
            "normal_claim": "interactions and autonomous background activity; no event annotations",
            "attack_material_separate": "NO_ATTACK_TREE_DESCRIBED",
            "row_labels_required": 0,
            "eligibility_status": "PASS_WITH_CLAIM_CEILING" if unsw_ok else "FAIL",
            "reason_code": (
                "UNLABELED_NORMAL_CLAIM_NOT_ATTACK_GROUND_TRUTH"
                if unsw_ok
                else "NORMAL_CLAIM_NOT_FOUND_IN_PRIMARY_METADATA"
            ),
            "evidence_object_ids": "unsw_readme;unsw_dryad_inventory",
        },
        {
            "candidate_id": "CIC_MODBUS_2023",
            "source_boundary_id": "CIC_BENIGN_FOLDER_ONLY",
            "benign_boundary": "BENIGN_ONLY_FOLDER",
            "normal_claim": "legitimate Modbus communication in simulated substation",
            "attack_material_separate": "YES_FOLDER_LEVEL",
            "row_labels_required": 0,
            "eligibility_status": "PASS" if cic_ok else "FAIL",
            "reason_code": "ATTACK_TREE_PROHIBITED" if cic_ok else "BENIGN_ATTACK_BOUNDARY_UNRESOLVED",
            "evidence_object_ids": "cic_official_page",
        },
    ]


def build_allowlist(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for spec in plan["future_large_objects"]:
        rows.append(
            {
                "candidate_id": spec["candidate_id"],
                "object_id": spec["object_id"],
                "official_url": spec["official_url"],
                "expected_size_or_ceiling": spec["expected_size_or_ceiling"],
                "expected_sha256": spec["expected_sha256"],
                "destination_identity": spec["destination_identity"],
                "intended_use": spec["intended_use"],
                "authorization_status": "FUTURE_USER_AUTHORIZATION_REQUIRED_NOT_EXECUTABLE",
            }
        )
    return rows


def eligible_tier_b_specs(
    plan: Mapping[str, Any], tier_a_pass: Mapping[str, bool]
) -> List[Mapping[str, Any]]:
    return [
        spec
        for spec in plan["objects"]
        if spec["tier"] == "B" and bool(tier_a_pass.get(str(spec["candidate_id"]), False))
    ]


def build_coverage_and_horizon(
    devices: Sequence[Mapping[str, Any]],
    flow_summary: Optional[Mapping[str, Any]],
    metadata_eligible: Optional[Mapping[str, bool]] = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any]]:
    eligible = dict(metadata_eligible or {candidate: True for candidate in CANDIDATES})
    unsw_clusters = cluster_count(devices, "UNSW_IOTRAFFIC")
    cic_clusters = cluster_count(devices, "CIC_MODBUS_2023")
    unsw_long_state = "PRESENT" if flow_summary and int(flow_summary["long_tcp_flow_count"]) > 0 else (
        "ABSENT" if flow_summary else "PENDING"
    )
    coverage = [
        {
            "candidate_id": "UNSW_IOTRAFFIC",
            "usage_domain": "CONSUMER_HOME",
            "embodiment": "PHYSICAL",
            "raw_source_units": sum(1 for row in devices if row["candidate_id"] == "UNSW_IOTRAFFIC"),
            "post_cluster_independent_domains": unsw_clusters,
            "transport_evidence": "MIXED",
            "long_bidirectional_tcp_evidence": unsw_long_state,
            "long_tcp_definition": "bidirectional TCP AND (packet_count > 256 OR duration_seconds >= 300)",
            "long_tcp_flow_count": flow_summary["long_tcp_flow_count"] if flow_summary else "UNKNOWN_NOT_MEASURED",
            "long_tcp_flow_fraction": flow_summary["fraction_long_bidirectional_tcp"] if flow_summary else "UNKNOWN_NOT_MEASURED",
            "reason_code": "OK" if flow_summary else "PENDING_TIER_B_FLOW_METADATA",
        },
        {
            "candidate_id": "CIC_MODBUS_2023",
            "usage_domain": "INDUSTRIAL_PROCESS",
            "embodiment": "SIMULATED",
            "raw_source_units": sum(1 for row in devices if row["candidate_id"] == "CIC_MODBUS_2023"),
            "post_cluster_independent_domains": cic_clusters,
            "transport_evidence": "TCP_MODBUS",
            "long_bidirectional_tcp_evidence": "PENDING",
            "long_tcp_definition": "bidirectional TCP AND (packet_count > 256 OR duration_seconds >= 300)",
            "long_tcp_flow_count": "UNKNOWN_NOT_MEASURED",
            "long_tcp_flow_fraction": "UNKNOWN_NOT_MEASURED",
            "reason_code": "PENDING_NO_SMALL_FLOW_METADATA",
        },
    ]
    if flow_summary:
        unsw_horizon = dict(flow_summary)
        unsw_horizon.update(
            {
                "candidate_id": "UNSW_IOTRAFFIC",
                "horizon_status": (
                    "PREFIX_256_TRUNCATES_MATERIAL_LONG_HORIZON"
                    if float(flow_summary["fraction_packet_count_gt_256"]) >= 0.05
                    else "PREFIX_256_COVERS_MOST_OBSERVED_FLOWS"
                ),
                "published_packets": 95543405,
                "published_flows": 4944041,
                "i1_scale_status": "SCALE_PLAUSIBLE_PENDING_EXACT_CENSUS",
                "reason_code": "FLOW_METADATA_MEASURED",
            }
        )
    else:
        unsw_horizon = {
            "candidate_id": "UNSW_IOTRAFFIC",
            "flow_rows": "UNKNOWN_NOT_MEASURED",
            "packet_count_q50": "UNKNOWN_NOT_MEASURED",
            "packet_count_q90": "UNKNOWN_NOT_MEASURED",
            "packet_count_q99": "UNKNOWN_NOT_MEASURED",
            "duration_seconds_q50": "UNKNOWN_NOT_MEASURED",
            "duration_seconds_q90": "UNKNOWN_NOT_MEASURED",
            "duration_seconds_q99": "UNKNOWN_NOT_MEASURED",
            "fraction_packet_count_gt_256": "UNKNOWN_NOT_MEASURED",
            "fraction_long_bidirectional_tcp": "UNKNOWN_NOT_MEASURED",
            "horizon_status": "PENDING_NO_SMALL_FLOW_METADATA",
            "published_packets": 95543405,
            "published_flows": 4944041,
            "i1_scale_status": "SCALE_PLAUSIBLE_PENDING_EXACT_CENSUS",
            "reason_code": "TIER_B_NOT_OPENED",
        }
    cic_horizon = {
        "candidate_id": "CIC_MODBUS_2023",
        "flow_rows": "UNKNOWN_NOT_PUBLISHED",
        "packet_count_q50": "UNKNOWN_NOT_PUBLISHED",
        "packet_count_q90": "UNKNOWN_NOT_PUBLISHED",
        "packet_count_q99": "UNKNOWN_NOT_PUBLISHED",
        "duration_seconds_q50": "UNKNOWN_NOT_PUBLISHED",
        "duration_seconds_q90": "UNKNOWN_NOT_PUBLISHED",
        "duration_seconds_q99": "UNKNOWN_NOT_PUBLISHED",
        "fraction_packet_count_gt_256": "UNKNOWN_NOT_PUBLISHED",
        "fraction_long_bidirectional_tcp": "UNKNOWN_NOT_PUBLISHED",
        "horizon_status": "PENDING_NO_SMALL_FLOW_METADATA",
        "published_packets": "UNKNOWN_NOT_PUBLISHED",
        "published_flows": "UNKNOWN_NOT_PUBLISHED",
        "i1_scale_status": "SCALE_UNKNOWN",
        "reason_code": "PENDING_NO_SMALL_FLOW_METADATA",
    }
    if not eligible.get("UNSW_IOTRAFFIC", False) or not eligible.get("CIC_MODBUS_2023", False):
        verdict = "CKDB_D0_P1_NO_IDENTIFIABLE_CORPUS_MIX"
        missing = "METADATA_ELIGIBLE_CONSUMER_AND_INDUSTRIAL_CORPUS"
    elif unsw_clusters < 3:
        verdict = "CKDB_D0_P1_NO_IDENTIFIABLE_CORPUS_MIX"
        missing = "CONSUMER_POST_CLUSTER_DOMAINS"
    elif cic_clusters < 3:
        verdict = "CKDB_D0_P1_PENDING_METADATA"
        missing = "SECOND_INDUSTRIAL_PROCESS_CORPUS"
    else:
        verdict = "CKDB_D0_P1_LARGE_DOWNLOAD_ELIGIBLE"
        missing = "NONE"
    decision = {
        "consumer_post_cluster_domains": unsw_clusters,
        "industrial_post_cluster_domains": cic_clusters,
        "large_download_authorized": False,
        "missing_evidence": missing,
        "status": verdict,
    }
    return coverage, [unsw_horizon, cic_horizon], decision


def write_sha256sums(root: Path, excluded: Sequence[str] = ("SHA256SUMS",)) -> None:
    root = Path(root)
    rows: List[str] = []
    excluded_set = set(excluded)
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded_set:
            continue
        rows.append("%s  %s" % (sha256_file(path), relative))
    atomic_text(root / "SHA256SUMS", "\n".join(rows) + "\n")


def package_result(root: Path) -> Tuple[Path, Path]:
    root = Path(root)
    archive = root.parent / (root.name + "_pullback.tar.gz")
    sidecar = archive.with_name(archive.name + ".sha256")
    if archive.exists() or sidecar.exists():
        raise ContractError("result package destination already exists")
    temporary = archive.with_name("." + archive.name + ".tmp")
    with tarfile.open(temporary, "w:gz") as handle:
        handle.add(root, arcname=root.name, recursive=True)
    os.replace(str(temporary), str(archive))
    atomic_text(sidecar, "%s  %s\n" % (sha256_file(archive), archive.name))
    return archive, sidecar


def write_report(path: Path, verdict: Mapping[str, Any], retrieval_rows: Sequence[Mapping[str, Any]]) -> None:
    lines = [
        "# CKDB D0-P1 metadata audit result",
        "",
        "Status: `%s`" % verdict["status"],
        "",
        "- consumer post-clustering domains: `%s`" % verdict["consumer_post_cluster_domains"],
        "- industrial post-clustering domains: `%s`" % verdict["industrial_post_cluster_domains"],
        "- missing evidence: `%s`" % verdict["missing_evidence"],
        "- large download authorized: `false`",
        "- downloaded metadata objects: `%d`" % len(retrieval_rows),
        "- PCAP opened: `0`",
        "- FINAL opened: `0`",
        "- labels read: `0`",
        "- training/embedding/threshold operations: `0`",
        "",
        "This result is an evidence gate only; it cannot authorize a large download.",
        "",
    ]
    atomic_text(path, "\n".join(lines))


def _extension_for_kind(kind: str) -> str:
    return {
        "html": ".html",
        "csv": ".csv",
        "markdown": ".md",
        "zip_flow_metadata": ".zip",
    }[kind]


def execute(args: argparse.Namespace, fetcher: Optional[Fetcher] = None) -> None:
    plan = verify_identity(Path(args.contract), Path(args.plan))
    output = Path(args.output)
    ensure_empty_output_root(output)
    downloads = output / "downloads"
    retrieval_rows: List[Dict[str, Any]] = []
    fetcher = fetcher or Fetcher(
        allow_dryad_anubis=bool(getattr(args, "allow_dryad_anubis", False))
    )
    try:
        tier_a_specs = [spec for spec in plan["objects"] if spec["tier"] == "A"]
        for spec in tier_a_specs:
            destination = downloads / spec["candidate_id"] / (
                spec["object_id"] + _extension_for_kind(spec["expected_kind"])
            )
            retrieval_rows.append(fetcher.fetch(spec, destination))
            enforce_candidate_tier_cap(retrieval_rows, spec["candidate_id"], "A")

        identity_rows = build_identity_rows(downloads)
        benign_rows = build_benign_rows(downloads)
        unsw_devices = parse_unsw_devices(object_path(downloads, "unsw_device_summary"))
        cic_devices = parse_cic_roles(load_text_object(downloads, "cic_official_page"))
        device_rows = unsw_devices + cic_devices
        tier_a_pass = {
            candidate: any(row["candidate_id"] == candidate and row["identity_status"] == "PASS" for row in identity_rows)
            and any(row["candidate_id"] == candidate and str(row["eligibility_status"]).startswith("PASS") for row in benign_rows)
            for candidate in CANDIDATES
        }

        flow_summary: Optional[Dict[str, Any]] = None
        member_rows: List[Dict[str, Any]] = []
        if not args.tier_a_only:
            for spec in eligible_tier_b_specs(plan, tier_a_pass):
                destination = downloads / spec["candidate_id"] / (
                    spec["object_id"] + _extension_for_kind(spec["expected_kind"])
                )
                retrieval_rows.append(fetcher.fetch(spec, destination))
                enforce_candidate_tier_cap(retrieval_rows, spec["candidate_id"], "B")
                if spec["object_id"] == "unsw_flows":
                    try:
                        flow_summary, member_rows = analyze_unsw_flow_zip(destination)
                    except SafetyError as error:
                        quarantine_download(destination, str(error))
                        raise

        lineage_rows = build_lineage_rows()
        coverage_rows, horizon_rows, verdict = build_coverage_and_horizon(
            device_rows, flow_summary, tier_a_pass
        )
        allowlist_rows = build_allowlist(plan)

        write_csv(output / "ckdb_d0_p1_retrieval_manifest.csv", RETRIEVAL_FIELDS, retrieval_rows)
        write_csv(output / "ckdb_d0_p1_corpus_identity_and_license.csv", IDENTITY_FIELDS, identity_rows)
        write_csv(output / "ckdb_d0_p1_lineage_overlap_matrix.csv", LINEAGE_FIELDS, lineage_rows)
        write_csv(output / "ckdb_d0_p1_benign_boundary.csv", BENIGN_FIELDS, benign_rows)
        write_csv(output / "ckdb_d0_p1_device_domain_inventory.csv", DEVICE_FIELDS, device_rows)
        write_csv(output / "ckdb_d0_p1_domain_type_coverage.csv", COVERAGE_FIELDS, coverage_rows)
        write_csv(output / "ckdb_d0_p1_horizon_and_scale.csv", HORIZON_FIELDS, horizon_rows)
        write_csv(output / "ckdb_d0_p1_later_download_allowlist.csv", ALLOWLIST_FIELDS, allowlist_rows)
        if member_rows:
            write_csv(output / "ckdb_d0_p1_unsw_flows_member_manifest.csv", MEMBER_FIELDS, member_rows)
        verdict.update(
            {
                "candidate_order": list(CANDIDATES),
                "contract_sha256": CONTRACT_SHA256,
                "final_files_opened": 0,
                "hpc_submissions": 0,
                "label_columns_read": 0,
                "models_opened": 0,
                "pcap_files_opened": 0,
                "plan_sha256": PLAN_SHA256,
                "report_assets_opened": 0,
                "training_embedding_threshold_operations": 0,
            }
        )
        atomic_json(output / "ckdb_d0_p1_verdict.json", verdict)
        write_report(output / "ckdb_d0_p1_result_report.md", verdict, retrieval_rows)
        write_sha256sums(output)
        package_result(output)
    except Exception as error:
        atomic_json(
            output / "engineering_failure.json",
            {
                "error_type": type(error).__name__,
                "message": str(error),
                "scientific_verdict": "NOT_EMITTED",
                "status": "CKDB_D0_P1_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT",
            },
        )
        verdict_path = output / "ckdb_d0_p1_verdict.json"
        if verdict_path.exists():
            verdict_path.unlink()
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute_parser = sub.add_parser("execute")
    execute_parser.add_argument("--contract", type=Path, required=True)
    execute_parser.add_argument("--plan", type=Path, required=True)
    execute_parser.add_argument("--output", type=Path, required=True)
    execute_parser.add_argument("--tier-a-only", action="store_true")
    execute_parser.add_argument(
        "--allow-dryad-anubis",
        action="store_true",
        help="Use the user-authorized official Dryad Anubis proof-of-work flow for exact file_stream URLs",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "execute":
        execute(args)
        return 0
    raise ContractError("unknown command")


if __name__ == "__main__":
    sys.exit(main())
