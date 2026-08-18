#!/usr/bin/env python3
"""CKDB D0-P2 frozen PNNL metadata-only audit.

Importing this module has no network side effect. The explicit execute command
retrieves only six allowlisted Tier-A metadata objects. The PNNL tar, packet
data, labels, models, reports, HPC, and FINAL assets are outside this program's
executable graph.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import ssl
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


ISSUE = "issue27ckdb_d0_p2_pnnl_metadata_audit_v1_2026-08-18"
CONTRACT_SHA256 = "16926b7eb860322dc380a45c98bcb9d116d78dabcee32e8743d0639fef41c4b6"
PLAN_SHA256 = "5d1a313ca73acb8f42342bc8a58057ccb830c80a1d930eafef30f06a57e80072"
CANDIDATE = "PNNL_ELECTRICITY_AND_GAS_IDS"
DOI = "10.25584/PNNLDH/1838670"
TIER_A_TOTAL_CAP = 20 * 1024 * 1024
PER_OBJECT_CAP = 8 * 1024 * 1024
LONG_TCP_PACKET_CUT = 256
LONG_TCP_DURATION_CUT = 300.0
FINAL_MARKERS = (
    "cooler-motor", "seed37", "seed_37", "seed-37",
    "seed47", "seed_47", "seed-47",
)
PROHIBITED_TEXT_MARKERS = FINAL_MARKERS + ("ckda_d1_report", "ckcz_report")
PCAP_MAGICS = {
    b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1",
    b"\xa1\xb2\x3c\x4d", b"\x0a\x0d\x0d\x0a",
}
LOGIN_MARKERS = (
    "access denied", "captcha", "cloudflare challenge",
    "please sign in", "authentication required",
)

RETRIEVAL_FIELDS = (
    "candidate_id", "object_id", "tier", "request_url", "final_url",
    "retrieval_utc", "http_status", "content_type", "published_size_text",
    "local_bytes", "sha256", "expected_kind", "safety_status", "reason_code",
)
IDENTITY_FIELDS = (
    "candidate_id", "official_owner", "dataset_title", "dataset_doi",
    "official_landing_url", "license_or_policy_status", "research_use_status",
    "access_requirement", "identity_status", "reason_code",
    "evidence_object_ids",
)
LINEAGE_FIELDS = (
    "candidate_id", "comparison_source", "collection_relation",
    "positive_evidence", "claim_ceiling", "reason_code",
)
BENIGN_FIELDS = (
    "candidate_id", "source_boundary_id", "benign_boundary", "normal_claim",
    "system_fault_scope", "row_labels_required", "eligibility_status",
    "reason_code", "evidence_object_ids",
)
DEVICE_FIELDS = (
    "candidate_id", "process_domain", "process_model", "field_device_fleet",
    "protocol_family", "control_enclave", "cluster_id",
    "independent_domain_counted", "reason_code",
)
INDEPENDENCE_FIELDS = (
    "candidate_id", "condition_id", "condition_name", "status",
    "primary_evidence", "reason_code",
)
COVERAGE_FIELDS = (
    "candidate_id", "process_domain", "usage_domain", "embodiment",
    "postcluster_independent_domains", "protocol_family",
    "protocol_is_domain_identity", "reason_code",
)
HORIZON_FIELDS = (
    "candidate_id", "small_flow_metadata_status", "long_tcp_definition",
    "long_tcp_flow_count", "long_tcp_flow_fraction", "archive_inventory_status",
    "published_size_or_ceiling", "i1_scale_status", "reason_code",
)
ALLOWLIST_FIELDS = (
    "candidate_id", "object_id", "official_url", "expected_size_or_ceiling",
    "expected_sha256", "destination_identity", "intended_use",
    "authorization_status",
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


def ensure_empty_output_root(path: Path) -> None:
    path = Path(path)
    if path.exists() and any(path.iterdir()):
        raise ContractError("output root must be new and empty")
    path.mkdir(parents=True, exist_ok=True)


def fail_if_prohibited_text(value: Any, context: str) -> None:
    lowered = str(value).replace("\\", "/").lower()
    marker = next((item for item in PROHIBITED_TEXT_MARKERS if item in lowered), None)
    if marker is not None:
        raise ContractError("prohibited identity context=%s marker=%s" % (context, marker))


def verify_identity(contract: Path, plan_path: Path) -> Mapping[str, Any]:
    if sha256_file(contract) != CONTRACT_SHA256:
        raise ContractError("FROZEN contract SHA drift")
    if sha256_file(plan_path) != PLAN_SHA256:
        raise ContractError("retrieval plan SHA drift")
    with Path(plan_path).open("r", encoding="utf-8") as handle:
        plan = json.load(handle)
    if plan.get("schema_version") != "CKDB_D0_P2_RETRIEVAL_PLAN_V1":
        raise ContractError("retrieval schema drift")
    if plan.get("candidate_order") != [CANDIDATE]:
        raise ContractError("candidate count/order drift")
    if plan.get("contract_sha256") != CONTRACT_SHA256:
        raise ContractError("plan/contract identity mismatch")
    if int(plan.get("tier_a_total_cap_bytes", -1)) != TIER_A_TOTAL_CAP:
        raise ContractError("Tier-A total cap drift")
    objects = list(plan.get("objects", []))
    object_ids = [str(item.get("object_id", "")) for item in objects]
    if len(objects) != 6 or len(object_ids) != len(set(object_ids)):
        raise ContractError("metadata object count/identity drift")
    total_planned = 0
    for item in objects:
        if item.get("candidate_id") != CANDIDATE or item.get("tier") != "A":
            raise ContractError("unexpected candidate or tier")
        parsed = urllib.parse.urlparse(str(item.get("url", "")))
        if parsed.scheme != "https" or not parsed.hostname:
            raise ContractError("only explicit HTTPS metadata objects are permitted")
        if "range" in {str(key).lower() for key in item}:
            raise ContractError("range requests are prohibited")
        cap = int(item.get("max_bytes", -1))
        if cap <= 0 or cap > PER_OBJECT_CAP:
            raise ContractError("per-object cap drift")
        total_planned += cap
        hosts = list(item.get("allowed_final_hosts", []))
        if not hosts or any("/" in str(host) for host in hosts):
            raise ContractError("invalid final-host allowlist")
        fail_if_prohibited_text(item, "retrieval_plan")
    if total_planned > TIER_A_TOTAL_CAP:
        raise ContractError("planned metadata cap exceeds total")
    future = list(plan.get("future_large_objects", []))
    if len(future) != 1 or future[0].get("object_id") != "pnnl_opaque_tar":
        raise ContractError("future tar identity drift")
    if future[0].get("authorization_status") != "NOT_EXECUTABLE_REQUIRES_NEW_USER_AUTHORIZATION":
        raise ContractError("future tar authorization drift")
    if future[0].get("object_id") in set(object_ids):
        raise ContractError("future tar leaked into executable objects")
    return plan


def sniff_kind(prefix: bytes) -> str:
    lowered = prefix[:8192].lstrip().lower()
    if prefix[:4] in PCAP_MAGICS:
        return "pcap"
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"\x1f\x8b"):
        return "archive"
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html"):
        return "html"
    return "text"


def validate_object_kind(path: Path, expected_kind: str) -> None:
    path = Path(path)
    with path.open("rb") as handle:
        prefix = handle.read(8192)
    observed = sniff_kind(prefix)
    if observed == "pcap":
        raise SafetyError("PCAP magic prohibited")
    if observed == "archive":
        raise SafetyError("archive body prohibited")
    if expected_kind == "html":
        if observed != "html":
            raise SafetyError("expected HTML metadata")
        text = path.read_bytes()[:256 * 1024].decode("utf-8", errors="ignore").lower()
        marker = next((item for item in LOGIN_MARKERS if item in text), None)
        if marker is not None:
            raise SafetyError("login/error/challenge HTML rejected: " + marker)
    elif expected_kind == "json":
        if observed == "html":
            raise SafetyError("HTML masquerading as JSON")
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                value = json.load(handle)
        except (ValueError, UnicodeError) as error:
            raise SafetyError("invalid JSON metadata") from error
        if not isinstance(value, (dict, list)):
            raise SafetyError("JSON metadata must be structured")
    else:
        raise ContractError("unexpected metadata kind")


def build_verified_ssl_context() -> ssl.SSLContext:
    return ssl.create_default_context()


class Fetcher:
    def __init__(self, opener: Optional[Any] = None) -> None:
        self.opener = opener or urllib.request.urlopen
        self.ssl_context = build_verified_ssl_context()

    def fetch(self, spec: Mapping[str, Any], destination: Path) -> Dict[str, Any]:
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name("." + destination.name + ".part")
        if temporary.exists():
            temporary.unlink()
        request = urllib.request.Request(
            str(spec["url"]),
            headers={"User-Agent": "CKDB-D0-P2-metadata-audit/1.0", "Accept": "*/*"},
            method="GET",
        )
        if request.has_header("Range"):
            raise ContractError("range request prohibited")
        try:
            try:
                response = self.opener(request, timeout=60, context=self.ssl_context)
            except TypeError:
                response = self.opener(request, timeout=60)
            final_url = str(response.geturl())
            parsed = urllib.parse.urlparse(final_url)
            allowed = {str(host).lower() for host in spec["allowed_final_hosts"]}
            if parsed.scheme != "https" or str(parsed.hostname).lower() not in allowed:
                raise RetrievalError("final redirect host not allowlisted")
            status = int(getattr(response, "status", response.getcode()))
            if status < 200 or status >= 300:
                raise RetrievalError("HTTP status %d" % status)
            cap = int(spec["max_bytes"])
            total = 0
            digest = hashlib.sha256()
            with temporary.open("wb") as handle:
                while True:
                    block = response.read(64 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > cap or total > PER_OBJECT_CAP:
                        raise SafetyError("metadata byte cap exceeded")
                    digest.update(block)
                    handle.write(block)
            validate_object_kind(temporary, str(spec["expected_kind"]))
            os.replace(str(temporary), str(destination))
            headers = getattr(response, "headers", {})
            content_type = str(headers.get("Content-Type", "")) if hasattr(headers, "get") else ""
            return {
                "candidate_id": CANDIDATE, "object_id": spec["object_id"], "tier": "A",
                "request_url": spec["url"], "final_url": final_url,
                "retrieval_utc": utc_now(), "http_status": status,
                "content_type": content_type or "UNKNOWN",
                "published_size_text": spec["published_size_text"],
                "local_bytes": total, "sha256": digest.hexdigest(),
                "expected_kind": spec["expected_kind"], "safety_status": "PASS",
                "reason_code": "OK",
            }
        finally:
            if temporary.exists():
                temporary.unlink()


def strip_html(value: str) -> str:
    no_script = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", value)
    no_tags = re.sub(r"(?s)<[^>]+>", " ", no_script)
    return re.sub(r"\s+", " ", html.unescape(no_tags)).strip()


def object_path(root: Path, object_id: str, expected_kind: str) -> Path:
    extension = ".html" if expected_kind == "html" else ".json"
    return Path(root) / "downloads" / (object_id + extension)


def load_evidence_text(root: Path, plan: Mapping[str, Any]) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for spec in plan["objects"]:
        path = object_path(root, str(spec["object_id"]), str(spec["expected_kind"]))
        if spec["expected_kind"] == "html":
            result[str(spec["object_id"])] = strip_html(
                path.read_bytes().decode("utf-8", errors="replace")
            )
        else:
            with path.open("r", encoding="utf-8-sig") as handle:
                result[str(spec["object_id"])] = json.dumps(
                    json.load(handle), sort_keys=True, ensure_ascii=False
                )
    return result


def contains_all(text: str, phrases: Sequence[str]) -> bool:
    lowered = text.lower()
    return all(phrase.lower() in lowered for phrase in phrases)


def build_identity_rows(evidence: Mapping[str, str]) -> List[Dict[str, Any]]:
    combined = " ".join(evidence.values())
    identity_ok = DOI.lower() in combined.lower() and contains_all(
        combined, ("electricity", "gas", "pnnl")
    )
    policy = evidence.get("pnnl_policy", "")
    policy_lower = policy.lower()
    prohibited = any(
        phrase in policy_lower
        for phrase in ("research use prohibited", "may not be used for research")
    )
    explicit_research_use = (
        "research" in policy_lower
        and ("use" in policy_lower or "data" in policy_lower)
    )
    if prohibited:
        policy_status = "PROHIBITED_RESEARCH_USE"
        status = "INELIGIBLE"
    elif explicit_research_use:
        policy_status = "RESEARCH_USE_EVIDENCE_PRESENT"
        status = "METADATA_ELIGIBLE" if identity_ok else "PENDING"
    else:
        policy_status = "PENDING_EXPLICIT_RESEARCH_USE_EVIDENCE"
        status = "PENDING"
    return [{
        "candidate_id": CANDIDATE,
        "official_owner": "Pacific Northwest National Laboratory",
        "dataset_title": "Electricity and Gas IDS",
        "dataset_doi": DOI,
        "official_landing_url": "https://data.pnnl.gov/group/nodes/dataset/13470",
        "license_or_policy_status": policy_status,
        "research_use_status": "OFFICIAL_RESEARCH_DATASET_POLICY_RECORDED",
        "access_requirement": "MANUAL_USER_REGISTRATION_FOR_FUTURE_LARGE_OBJECT",
        "identity_status": status,
        "reason_code": (
            "OK" if status == "METADATA_ELIGIBLE"
            else "PROHIBITED_RESEARCH_USE" if status == "INELIGIBLE"
            else "PENDING_PRIMARY_IDENTITY_OR_POLICY"
        ),
        "evidence_object_ids": "pnnl_datahub_page;pnnl_datacite_json;pnnl_osti_page;pnnl_policy",
    }]


def build_lineage_rows(evidence: Mapping[str, str]) -> List[Dict[str, Any]]:
    timeline = (
        "OSTI_DATACITE_TIMELINE_RECORDED"
        if evidence.get("pnnl_datacite_json") and evidence.get("pnnl_osti_json")
        else "PENDING_TIMELINE"
    )
    rows = []
    for source, ceiling in (
        ("TON_IOT_AND_IOTSIM_ROUTE", "NO_KNOWN_OVERLAP"),
        ("UNSW_IOTRAFFIC", "NO_KNOWN_OVERLAP"),
        ("CIC_MODBUS_2023", "NO_KNOWN_OVERLAP"),
        ("NETFOUND_PRETRAINING", "POSSIBLE_OVERLAP"),
        ("COOLER_MOTOR_FINAL", "FINAL_IDENTITY_ONLY_NOT_OPENED"),
    ):
        rows.append({
            "candidate_id": CANDIDATE,
            "comparison_source": source,
            "collection_relation": "SEPARATE_PNNL_CAMPAIGN_PENDING_FULL_INVENTORY",
            "positive_evidence": timeline,
            "claim_ceiling": ceiling,
            "reason_code": "FINAL_NOT_OPENED" if source == "COOLER_MOTOR_FINAL" else timeline,
        })
    return rows


def evaluate_independence(
    evidence: Mapping[str, str], inventory_text: str = ""
) -> List[Dict[str, Any]]:
    primary = " ".join(evidence.values())
    lower = primary.lower()
    conditions = [
        (
            "C1", "DISTINCT_PROCESS_MODEL",
            "electric" in lower and "natural gas" in lower
            and ("simulat" in lower or "process model" in lower),
            "official description names electric and natural-gas process models",
        ),
        (
            "C2", "DISTINCT_FIELD_DEVICE_FLEET",
            any(name in lower for name in ("sage", "sel 451", "sel451", "ge d30"))
            and any(name in lower for name in ("roc 800", "roc800", "floboss", "controlwave")),
            "sector-specific electrical and gas field-device names",
        ),
        (
            "C3", "DISTINCT_CONTROL_ENCLAVE",
            ("multiple network" in lower or "separate network" in lower or "control enclave" in lower)
            and "electric" in lower and "gas" in lower,
            "official description distinguishes sector control networks",
        ),
    ]
    rows = []
    for condition_id, name, passed, description in conditions:
        rows.append({
            "candidate_id": CANDIDATE, "condition_id": condition_id,
            "condition_name": name, "status": "TRUE" if passed else "PENDING",
            "primary_evidence": description if passed else "PRIMARY_METADATA_NOT_YET_SUFFICIENT",
            "reason_code": "OK" if passed else "PENDING_" + name,
        })
    inv = inventory_text.lower()
    separable = (
        ("electric_normal" in inv or "electric/normal" in inv)
        and ("gas_normal" in inv or "gas/normal" in inv)
    )
    rows.append({
        "candidate_id": CANDIDATE, "condition_id": "C4",
        "condition_name": "SEPARABLE_NORMAL_UNIT",
        "status": "TRUE" if separable else "PENDING",
        "primary_evidence": (
            "pre-open sector-specific normal members"
            if separable else "OPAQUE_TAR_NO_PREOPEN_MEMBER_INVENTORY"
        ),
        "reason_code": "OK" if separable else "PENDING_ARCHIVE_INVENTORY",
    })
    return rows


def pnnl_domain_count(independence_rows: Sequence[Mapping[str, Any]]) -> int:
    required = {"C1", "C2", "C3", "C4"}
    statuses = {str(row["condition_id"]): str(row["status"]) for row in independence_rows}
    return 2 if set(statuses) == required and all(statuses[key] == "TRUE" for key in required) else 1


def build_benign_rows(independence_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    c4 = next(row for row in independence_rows if row["condition_id"] == "C4")
    if c4["status"] == "TRUE":
        boundary, eligibility, reason = "BENIGN_ONLY_FILE_OR_FOLDER_PER_SECTOR", "ELIGIBLE", "OK"
    else:
        boundary, eligibility, reason = "PENDING_ARCHIVE_INVENTORY", "PENDING", "PENDING_ARCHIVE_INVENTORY"
    return [{
        "candidate_id": CANDIDATE,
        "source_boundary_id": "PNNL_NORMAL_TRAFFIC_BASELINE",
        "benign_boundary": boundary,
        "normal_claim": "OFFICIAL_NARRATIVE_NAMES_NORMAL_TRAFFIC_BASELINE",
        "system_fault_scope": "EXCLUDED_ABNORMAL_PHYSICAL_STATE",
        "row_labels_required": False,
        "eligibility_status": eligibility,
        "reason_code": reason,
        "evidence_object_ids": "pnnl_datahub_page",
    }]


def build_device_rows(independence_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    count = pnnl_domain_count(independence_rows)
    return [
        {
            "candidate_id": CANDIDATE, "process_domain": "ELECTRIC_DISTRIBUTION",
            "process_model": "OPAL_RT_ELECTRIC_DISTRIBUTION",
            "field_device_fleet": "SAGE_RTU;SEL_451;GE_D30",
            "protocol_family": "DNP3",
            "control_enclave": "PNNL_ELECTRIC_CONTROL_ENCLAVE",
            "cluster_id": "PNNL_ELECTRIC_DISTRIBUTION",
            "independent_domain_counted": 1, "reason_code": "OK_BASE_DOMAIN",
        },
        {
            "candidate_id": CANDIDATE, "process_domain": "NATURAL_GAS_DISTRIBUTION",
            "process_model": "PNNL_NATURAL_GAS_DISTRIBUTION",
            "field_device_fleet": "ROC_800;FLOBOSS;CONTROLWAVE",
            "protocol_family": "MODBUS",
            "control_enclave": "PNNL_GAS_CONTROL_ENCLAVE",
            "cluster_id": "PNNL_NATURAL_GAS_DISTRIBUTION",
            "independent_domain_counted": 1 if count == 2 else 0,
            "reason_code": "OK_INDEPENDENT" if count == 2 else "PENDING_FOUR_CONDITION_CONJUNCTION",
        },
    ]


def build_coverage_rows(independence_rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    count = pnnl_domain_count(independence_rows)
    rows = []
    for domain, protocol in (("ELECTRIC_DISTRIBUTION", "DNP3"), ("NATURAL_GAS_DISTRIBUTION", "MODBUS")):
        rows.append({
            "candidate_id": CANDIDATE, "process_domain": domain,
            "usage_domain": "INDUSTRIAL_PROCESS",
            "embodiment": "HARDWARE_IN_THE_LOOP_SIMULATED_PROCESS",
            "postcluster_independent_domains": count,
            "protocol_family": protocol, "protocol_is_domain_identity": False,
            "reason_code": "DESCRIPTIVE_PROTOCOL_ONLY",
        })
    return rows


def build_horizon_rows(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    future = plan["future_large_objects"][0]
    return [{
        "candidate_id": CANDIDATE,
        "small_flow_metadata_status": "PENDING_NO_SMALL_FLOW_METADATA",
        "long_tcp_definition": "bidirectional TCP AND (packet_count > 256 OR duration_seconds >= 300)",
        "long_tcp_flow_count": "PENDING", "long_tcp_flow_fraction": "PENDING",
        "archive_inventory_status": "PENDING_ARCHIVE_INVENTORY",
        "published_size_or_ceiling": future["expected_size_or_ceiling"],
        "i1_scale_status": "PENDING_POST_DOWNLOAD_CENSUS",
        "reason_code": "PENDING_NO_SMALL_FLOW_METADATA",
    }]


def build_allowlist(plan: Mapping[str, Any]) -> List[Dict[str, Any]]:
    return [{
        "candidate_id": item["candidate_id"], "object_id": item["object_id"],
        "official_url": item["official_url"],
        "expected_size_or_ceiling": item["expected_size_or_ceiling"],
        "expected_sha256": item["expected_sha256"],
        "destination_identity": item["destination_identity"],
        "intended_use": item["intended_use"],
        "authorization_status": item["authorization_status"],
    } for item in plan["future_large_objects"]]


def build_verdict(
    identity_rows: Sequence[Mapping[str, Any]],
    benign_rows: Sequence[Mapping[str, Any]],
    independence_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    identity = str(identity_rows[0]["identity_status"])
    statuses = {str(row["condition_id"]): str(row["status"]) for row in independence_rows}
    reasons = sorted({
        str(row["reason_code"])
        for row in list(identity_rows) + list(benign_rows) + list(independence_rows)
        if str(row["reason_code"]) != "OK"
    })
    proven_false = any(value == "FALSE" for value in statuses.values())
    pending = identity != "METADATA_ELIGIBLE" or any(value != "TRUE" for value in statuses.values())
    if proven_false or identity == "INELIGIBLE":
        candidate_status = "PNNL_CORPUS_METADATA_INELIGIBLE"
        status = "CKDB_D0_P2_NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS"
    elif pending:
        candidate_status = "PNNL_CORPUS_METADATA_PENDING"
        status = "CKDB_D0_P2_PENDING_METADATA"
    else:
        candidate_status = "PNNL_CORPUS_METADATA_ELIGIBLE"
        status = "CKDB_D0_P2_LARGE_DOWNLOAD_ELIGIBLE"
    pnnl_domains = pnnl_domain_count(independence_rows)
    return {
        "issue": ISSUE, "candidate_id": CANDIDATE,
        "candidate_status": candidate_status, "status": status,
        "reason_codes": reasons or ["OK"],
        "cic_modbus_postcluster_domains": 1,
        "pnnl_postcluster_independent_domains": pnnl_domains,
        "combined_industrial_domains": 1 + pnnl_domains,
        "post_download_pre_use_boundary_verification_required": (
            "PENDING_ARCHIVE_INVENTORY" in reasons
        ),
        "large_download_authorized": False, "training_authorized": False,
        "hpc_authorized": False, "final_opened": 0, "pcap_opened": 0,
        "label_tables_opened": 0, "model_or_embedding_opened": 0,
        "manual_registration_automated": 0,
    }


def write_sha256sums(root: Path, excluded: Iterable[str] = ("SHA256SUMS",)) -> None:
    root = Path(root)
    excluded_set = set(excluded)
    lines = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded_set or relative.endswith(".tmp") or "/." in relative:
            continue
        lines.append("%s  %s" % (sha256_file(path), relative))
    atomic_text(root / "SHA256SUMS", "\n".join(lines) + "\n")


def package_result(root: Path) -> Tuple[Path, Path]:
    root = Path(root)
    archive = root.with_name(root.name + "_pullback.tar.gz")
    sidecar = archive.with_name(archive.name + ".sha256")
    temporary = archive.with_name("." + archive.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        with tarfile.open(str(temporary), "w:gz") as handle:
            for path in sorted(item for item in root.rglob("*") if item.is_file()):
                handle.add(str(path), arcname=path.relative_to(root).as_posix(), recursive=False)
        os.replace(str(temporary), str(archive))
        atomic_text(sidecar, "%s  %s\n" % (sha256_file(archive), archive.name))
    finally:
        if temporary.exists():
            temporary.unlink()
    return archive, sidecar


def write_report(path: Path, verdict: Mapping[str, Any]) -> None:
    lines = [
        "# CKDB D0-P2 metadata audit result", "",
        "- Status: %s" % verdict["status"],
        "- Candidate status: %s" % verdict["candidate_status"],
        "- PNNL post-cluster domains: %s" % verdict["pnnl_postcluster_independent_domains"],
        "- Combined industrial domains: %s" % verdict["combined_industrial_domains"],
        "- Pending reasons: %s" % ";".join(verdict["reason_codes"]),
        "- Large download authorized: false",
        "- Training/HPC authorized: false",
        "- FINAL/PCAP/labels/models opened: 0/0/0/0", "",
        "This result is metadata evidence only. Registration and large-object access",
        "remain manual and separately authorization-gated.", "",
    ]
    atomic_text(path, "\n".join(lines))


def execute(args: argparse.Namespace, fetcher: Optional[Any] = None) -> None:
    output = Path(args.output)
    ensure_empty_output_root(output)
    try:
        plan = verify_identity(Path(args.contract), Path(args.plan))
        active_fetcher = fetcher or Fetcher()
        retrieval_rows = []
        total_bytes = 0
        for spec in plan["objects"]:
            destination = object_path(output, str(spec["object_id"]), str(spec["expected_kind"]))
            row = active_fetcher.fetch(spec, destination)
            total_bytes += int(row["local_bytes"])
            if total_bytes > TIER_A_TOTAL_CAP:
                raise SafetyError("Tier-A total byte cap exceeded")
            retrieval_rows.append(row)
        evidence = load_evidence_text(output, plan)
        identity_rows = build_identity_rows(evidence)
        lineage_rows = build_lineage_rows(evidence)
        independence_rows = evaluate_independence(evidence)
        benign_rows = build_benign_rows(independence_rows)
        device_rows = build_device_rows(independence_rows)
        coverage_rows = build_coverage_rows(independence_rows)
        horizon_rows = build_horizon_rows(plan)
        allowlist_rows = build_allowlist(plan)
        verdict = build_verdict(identity_rows, benign_rows, independence_rows)

        write_csv(output / "ckdb_d0_p2_retrieval_manifest.csv", RETRIEVAL_FIELDS, retrieval_rows)
        write_csv(output / "ckdb_d0_p2_corpus_identity_and_license.csv", IDENTITY_FIELDS, identity_rows)
        write_csv(output / "ckdb_d0_p2_lineage_overlap_matrix.csv", LINEAGE_FIELDS, lineage_rows)
        write_csv(output / "ckdb_d0_p2_benign_boundary.csv", BENIGN_FIELDS, benign_rows)
        write_csv(output / "ckdb_d0_p2_device_process_inventory.csv", DEVICE_FIELDS, device_rows)
        write_csv(output / "ckdb_d0_p2_independence_evidence.csv", INDEPENDENCE_FIELDS, independence_rows)
        write_csv(output / "ckdb_d0_p2_domain_type_coverage.csv", COVERAGE_FIELDS, coverage_rows)
        write_csv(output / "ckdb_d0_p2_horizon_and_scale.csv", HORIZON_FIELDS, horizon_rows)
        write_csv(output / "ckdb_d0_p2_later_download_allowlist.csv", ALLOWLIST_FIELDS, allowlist_rows)
        atomic_json(output / "ckdb_d0_p2_verdict.json", verdict)
        write_report(output / "ckdb_d0_p2_result_report.md", verdict)
        write_sha256sums(output)
        package_result(output)
    except Exception as error:
        for name in ("ckdb_d0_p2_verdict.json", "ckdb_d0_p2_result_report.md", "SHA256SUMS"):
            path = output / name
            if path.exists():
                path.unlink()
        archive = output.with_name(output.name + "_pullback.tar.gz")
        sidecar = archive.with_name(archive.name + ".sha256")
        for path in (archive, sidecar):
            if path.exists():
                path.unlink()
        atomic_json(output / "engineering_failure.json", {
            "issue": ISSUE,
            "status": "CKDB_D0_P2_ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT",
            "error_type": type(error).__name__, "error": str(error),
        })
        raise


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    execute_parser = subparsers.add_parser("execute", help="retrieve allowlisted Tier-A metadata")
    execute_parser.add_argument("--contract", required=True)
    execute_parser.add_argument("--plan", required=True)
    execute_parser.add_argument("--output", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "execute":
        execute(args)
        return 0
    raise ContractError("unknown command")


if __name__ == "__main__":
    sys.exit(main())
