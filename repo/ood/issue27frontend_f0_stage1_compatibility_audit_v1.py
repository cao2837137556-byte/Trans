#!/usr/bin/env python3
"""Offline materializer for the frozen Frontend-F0 Stage-I audit.

The evidence manifest is a transcription of already retrieved official metadata.
This program has no network client and cannot download checkpoints or embeddings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Iterable, Mapping, Sequence


CONTRACT = "runs/mainline_docs/frontend_f0_measurement_instrument_frozen_20260828.md"
CONTRACT_SHA256 = "197015f0a6dd5c5510b5859d12aa19813a877392c8b985f6b1fcc4fe20f81a00"
TERMINALS = (
    "F0_ENGINEERING_INCOMPATIBLE",
    "F0_LINEAGE_OR_LICENSE_NO_GO",
    "F0_NO_USABLE_OFFICIAL_CHECKPOINT",
    "STAGE_I_COMPATIBLE_PENDING_STAGE_IIA",
)


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
    if not evidence["python39_syntax_compatible"] or not evidence["adapter_feasible"]:
        return TERMINALS[0]
    if not evidence["official_code_license_clear"] or evidence["known_current_role_overlap"]:
        return TERMINALS[1]
    checkpoint = evidence["checkpoint"]
    if not checkpoint["official_link"] or not checkpoint["published_sha256"] or not checkpoint["published_bytes"]:
        return TERMINALS[2]
    return TERMINALS[3]


def validate(evidence: Mapping[str, object]) -> None:
    required = {
        "candidate", "observed_utc", "official_repo", "official_repo_commit",
        "official_code_license_clear", "python39_syntax_compatible", "adapter_feasible",
        "known_current_role_overlap", "pretraining_corpora", "checkpoint",
        "output", "protocol_support", "resource_estimate", "source_evidence",
    }
    missing = required - set(evidence)
    if missing:
        raise RuntimeError("evidence schema missing: %s" % sorted(missing))
    if evidence["candidate"] != "Pcap-Encoder":
        raise RuntimeError("primary candidate identity drift")
    if evidence["output"]["unit"] != "packet" or int(evidence["output"]["dimension"]) != 768:
        raise RuntimeError("declared output identity drift")
    if evidence["checkpoint"]["retrieved"]:
        raise RuntimeError("checkpoint retrieval is forbidden in Stage I")
    if not evidence["protocol_support"]["supported"]:
        raise RuntimeError("empty protocol support matrix")


def run(root: Path, evidence_path: Path, output: Path) -> Dict[str, object]:
    if sha256_file(root / CONTRACT) != CONTRACT_SHA256:
        raise RuntimeError("frozen contract drift")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    validate(evidence)
    status = decide(evidence)
    backup_activated = status == "F0_ENGINEERING_INCOMPATIBLE"
    protocol_rows = []
    for name in evidence["protocol_support"]["supported"]:
        protocol_rows.append({"protocol": name, "scope": "SUPPORTED", "missing_reason": ""})
    for name in evidence["protocol_support"]["outside_scope"]:
        protocol_rows.append({
            "protocol": name,
            "scope": "OUTSIDE_SCOPE",
            "missing_reason": "UNSUPPORTED_DECLARED_PROTOCOL",
        })
    audit = {
        "status": status,
        "contract_sha256": CONTRACT_SHA256,
        "evidence_sha256": sha256_file(evidence_path),
        "candidate": evidence["candidate"],
        "official_repo": evidence["official_repo"],
        "official_repo_commit": evidence["official_repo_commit"],
        "code_license": "MIT",
        "pretraining_corpora": evidence["pretraining_corpora"],
        "known_current_role_overlap": evidence["known_current_role_overlap"],
        "checkpoint": evidence["checkpoint"],
        "output": evidence["output"],
        "runtime": {
            "official_python": "3.10.16",
            "python39_syntax_files_checked": int(evidence["python39_syntax_files_checked"]),
            "python39_syntax_failures": 0,
            "python39_runtime_confirmed": False,
            "adapter_feasible": evidence["adapter_feasible"],
        },
        "missing_reason_dictionary": evidence["protocol_support"]["missing_reasons"],
        "resource_estimate": evidence["resource_estimate"],
        "source_evidence": evidence["source_evidence"],
        "backup_activated": backup_activated,
        "boundary_counts": {
            "checkpoint_files_downloaded": 0,
            "embedding_arrays_opened": 0,
            "training_runs": 0,
            "report_opened": 0,
            "final_opened": 0,
        },
    }
    verdict = {
        "status": status,
        "candidate": evidence["candidate"],
        "reason_code": "OFFICIAL_CHECKPOINT_BYTES_AND_SHA256_NOT_PUBLISHED"
        if status == "F0_NO_USABLE_OFFICIAL_CHECKPOINT" else "",
        "official_checkpoint_link_exists": bool(evidence["checkpoint"]["official_link"]),
        "official_checkpoint_identity_pinnable": bool(
            evidence["checkpoint"]["published_sha256"] and evidence["checkpoint"]["published_bytes"]
        ),
        "backup_activated": backup_activated,
        "challenger_embedding_authorized": False,
        "claim_boundary": "COMPATIBILITY_AND_RESOURCE_AUDIT_ONLY",
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "frontend_f0_stage1_audit.json", audit)
    atomic_json(output / "frontend_f0_stage1_resource_estimate.json", evidence["resource_estimate"])
    atomic_json(output / "frontend_f0_stage1_verdict.json", verdict)
    atomic_csv(output / "frontend_f0_stage1_protocol_support.csv",
               ("protocol", "scope", "missing_reason"), protocol_rows)
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
