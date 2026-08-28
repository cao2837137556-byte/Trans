#!/usr/bin/env python3
"""Offline materializer for the frozen Data-F0 candidate-1 metadata audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence


CONTRACT = "runs/mainline_docs/data_f0_paired_corpus_metadata_audit_frozen_20260828.md"
CONTRACT_SHA256 = "e699008656ced7120bf6eacf71129ca416cd98e9c3d8d3e653f97e2e90ef0079"
PENDING = "PENDING_MEMBER_INVENTORY_AFTER_DOWNLOAD"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path: Path, value: Mapping[str, object]) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    os.close(fd)
    try:
        with open(name, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def decide(evidence: Mapping[str, object]) -> str:
    if not evidence["official_raw_pcap_claim"]:
        return "NO_RAW_PCAP"
    if not evidence["research_use_available"]:
        return "NO_CLEAR_LICENSE"
    if evidence["known_lineage_contamination"]:
        return "LINEAGE_CONTAMINATION_NO_GO"
    if not evidence["exact_member_inventory_published"] or not evidence["exact_victim_mapping_published"]:
        return PENDING
    paired = int(evidence["paired_device_count"])
    if paired == 0:
        return "NO_SAME_DEVICE_BENIGN_ATTACK_PAIRING"
    data_e = max(2, int(math.ceil(paired / 4.0)))
    if paired < 8 or paired - data_e < 6:
        return "NO_IDENTIFIABLE_PAIRED_DEVICE_SPLIT"
    if not evidence["task_relevance_measurable"]:
        return "NO_TASK_RELEVANCE_METADATA"
    return "DATA_F0_METADATA_ELIGIBLE"


def validate(evidence: Mapping[str, object]) -> None:
    required = {
        "candidate", "version", "official_url", "publisher", "citation",
        "research_use_available", "official_raw_pcap_claim", "directories",
        "attack_scenarios", "exact_member_inventory_published",
        "exact_victim_mapping_published", "paired_device_count",
        "known_lineage_contamination", "task_relevance_measurable",
        "resource_plan", "boundary_counts",
    }
    missing = required - set(evidence)
    if missing:
        raise RuntimeError("evidence schema missing: %s" % sorted(missing))
    if evidence["candidate"] != "CIC IoT 2022":
        raise RuntimeError("candidate-1 identity drift")
    if any(int(value) != 0 for value in evidence["boundary_counts"].values()):
        raise RuntimeError("metadata-only boundary violation")


def run(root: Path, evidence_path: Path, output: Path) -> Dict[str, object]:
    if sha256_file(root / CONTRACT) != CONTRACT_SHA256:
        raise RuntimeError("frozen contract drift")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    validate(evidence)
    status = decide(evidence)
    if status != PENDING:
        raise RuntimeError("candidate-1 observed metadata no longer matches preregistered pending branch")

    audit_fields = (
        "candidate", "version", "device_id", "device_type", "member_id", "member_role",
        "attack_family", "victim_explicit", "pairing_status", "reason_code", "official_url",
    )
    audit_rows = [{
        "candidate": evidence["candidate"], "version": evidence["version"],
        "device_id": "UNENUMERATED", "device_type": "PUBLISHED_LIST_WITHOUT_MEMBER_LINEAGE",
        "member_id": "UNPUBLISHED_PREOPEN_INVENTORY", "member_role": "UNKNOWN",
        "attack_family": "Flood|RTSP Brute Force", "victim_explicit": 0,
        "pairing_status": PENDING, "reason_code": "NO_EXACT_DEVICE_MEMBER_VICTIM_MAP",
        "official_url": evidence["official_url"],
    }]
    pairing_rows = [{
        "device_id": "UNENUMERATED_DEVICE_SET", "benign_member_proven": 0,
        "attack_member_proven": 0, "victim_identity_proven": 0,
        "commissioning_boundary_proven": 0, "status": PENDING,
    }]
    lineage = {
        "candidate": evidence["candidate"], "publisher": evidence["publisher"],
        "citation": evidence["citation"], "research_use_available": evidence["research_use_available"],
        "known_lineage_contamination": evidence["known_lineage_contamination"],
        "relationship_to_frontend_pretraining": "NOT_LISTED_IN_PCAP_ENCODER_PRETRAINING_CORPORA",
        "relationship_to_current_roles": "NO_RAW_IDENTITY_OVERLAP_ESTABLISHED_FROM_OFFICIAL_METADATA",
    }
    task = {
        "status": PENDING,
        "raw_pcap_can_later_measure_descriptors": True,
        "published_member_level_descriptor_counts": False,
        "consumer_commissioning_scope_only": True,
        "industrial_high_density_long_connection_claim_supported": False,
        "required_descriptors": [
            "packets_per_session", "duration", "bidirectional_tcp_share", "protocol_mix",
            "long_high_density_session_share", "hydraulic_failure_region_coverage",
        ],
    }
    split = {
        "status": PENDING, "paired_device_count": None,
        "data_e_count": None, "data_t_count": None,
        "reason_code": "EXACT_DEVICE_MEMBER_VICTIM_MAP_NOT_PUBLISHED_PREOPEN",
    }
    verdict = {
        "status": PENDING,
        "candidate": evidence["candidate"],
        "candidate_2_accessed": False,
        "candidate_2_authorized": False,
        "bulk_download_authorized": False,
        "reason_code": "EXACT_MEMBER_AND_VICTIM_INVENTORY_REQUIRES_LATER_BULK_AUDIT",
        "boundary_counts": evidence["boundary_counts"],
        "claim_boundary": "METADATA_DOES_NOT_YET_PROVE_SAME_DEVICE_PAIRING",
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_csv(output / "data_f0_candidate_audit.csv", audit_fields, audit_rows)
    atomic_csv(output / "data_f0_pairing_matrix.csv", tuple(pairing_rows[0]), pairing_rows)
    atomic_json(output / "data_f0_lineage_and_license.json", lineage)
    atomic_json(output / "data_f0_task_relevance.json", task)
    atomic_json(output / "data_f0_resource_plan.json", evidence["resource_plan"])
    atomic_json(output / "data_f0_data_e_t_split.json", split)
    atomic_json(output / "data_f0_verdict.json", verdict)
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "SHA256SUMS")
    atomic_bytes(output / "SHA256SUMS", "".join(
        "%s  %s\n" % (sha256_file(path), path.name) for path in files
    ).encode("ascii"))
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.repo_root.resolve(), args.evidence.resolve(), args.output.resolve()),
                     indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
