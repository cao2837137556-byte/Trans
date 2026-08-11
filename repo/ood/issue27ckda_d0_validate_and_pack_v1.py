#!/usr/bin/env python3
"""Validate and finalize a CKDA D0 result directory.

This validator is intentionally strict: engineering failures have no D0
scientific verdict, the 50-column candidate schema is literal, all mandatory
outputs are read back, and FINAL/label/embedding counters must remain zero.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any


CONTRACT_SHA256 = "ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5"
ALLOWED_VERDICTS = {
    "CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN",
    "CKDA_D0_NO_COMPATIBLE_REPRESENTATION",
}
BOOLEAN_FIELDS = {
    "license_research_use_ok",
    "license_weights_redistribution_ok",
    "pretraining_iot_ics_disclosed",
    "target_fitted_tokenizer_required",
    "strict_prefix_supported",
    "full_session_then_slice_required",
    "uid_join_deterministic",
    "checkpoint_resume_supported",
    "dependency_lock_reproducible",
}
MANDATORY = (
    "ckda_d0_candidate_audit.csv",
    "ckda_d0_evidence_manifest.csv",
    "ckda_d0_data_census.json",
    "ckda_d0_resource_pilot.csv",
    "ckda_d0_resource_pilot_measurements.json",
    "ckda_d0_final_exclusion_audit.json",
    "ckda_d0_verdict.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    path = Path(path)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temp, path)


def contract_test() -> None:
    """Exercise the Python-3.9-sensitive atomic text boundary."""
    with tempfile.TemporaryDirectory() as directory:
        target = Path(directory) / "atomic.txt"
        atomic_text(target, "line-1\nline-2\n")
        if target.read_bytes() != b"line-1\nline-2\n":
            raise RuntimeError("atomic text LF/readback contract failed")
        if list(target.parent.glob(f".{target.name}.*.tmp")):
            raise RuntimeError("atomic text temporary file survived replacement")
    print("CKDA_D0_VALIDATOR_CONTRACT_PASS")


def atomic_json(path: Path, value: Any) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def load_audit_module(path: Path):
    spec = importlib.util.spec_from_file_location("ckda_validator_contract", Path(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import audit module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate(args: argparse.Namespace) -> None:
    root = Path(args.result)
    if not root.is_dir():
        raise RuntimeError(f"result directory missing: {root}")
    for name in MANDATORY:
        path = root / name
        if not path.is_file() or path.stat().st_size <= 0:
            raise RuntimeError(f"mandatory D0 output missing: {name}")
    for marker in ("job_failure.txt", "slurm_failure.txt", "engineering_failure.json"):
        if (root / marker).exists():
            raise RuntimeError(f"failure marker present: {marker}")

    contract = Path(args.contract)
    if sha256_file(contract) != CONTRACT_SHA256:
        raise RuntimeError("FROZEN contract SHA drift")
    audit_module = load_audit_module(Path(args.audit_module))
    fields, candidates = read_csv(root / "ckda_d0_candidate_audit.csv")
    if tuple(fields) != tuple(audit_module.AUDIT_FIELDS) or len(fields) != 50:
        raise RuntimeError("candidate audit schema drift")
    if [row["candidate_id"] for row in candidates] != list(audit_module.CANDIDATES):
        raise RuntimeError("candidate audit row order drift")
    for row in candidates:
        for field in BOOLEAN_FIELDS:
            if row[field] not in {"true", "false"}:
                raise RuntimeError(f"invalid boolean {field} for {row['candidate_id']}")
        if row["hard_gate_status"] not in {"PASS", "FAIL"}:
            raise RuntimeError(f"invalid hard gate status: {row['candidate_id']}")
        if int(row["final_files_opened"]) != 0:
            raise RuntimeError("candidate audit reports FINAL open")
    by_id = {row["candidate_id"]: row for row in candidates}
    if "complete_checkpoint_sha256_missing" not in by_id["E1"]["hard_gate_reasons"]:
        raise RuntimeError("E1 incomplete-checkpoint gate disappeared")
    if "license_research_use_not_granted" not in by_id["E2"]["hard_gate_reasons"]:
        raise RuntimeError("E2 license gate disappeared")

    census = json.loads((root / "ckda_d0_data_census.json").read_text(encoding="utf-8"))
    if census.get("status") != "CKDA_D0_DATA_CENSUS_COMPLETE":
        raise RuntimeError("census is not terminal")
    if census.get("contract_sha256") != CONTRACT_SHA256:
        raise RuntimeError("census contract drift")
    if int(census.get("final_files_opened", -1)) != 0 or int(census.get("raw_label_columns_read", -1)) != 0:
        raise RuntimeError("census boundary failure")
    expected_i1 = (
        "PASS"
        if int(census["i1_fit_sessions"]) >= 500_000 and int(census["i1_fit_tokens"]) >= 10_000_000
        else "FAIL"
    )
    if census.get("i1_data_gate") != expected_i1:
        raise RuntimeError("I1 conjunctive data gate drift")

    pilot_module = load_audit_module(Path(args.pilot_module))
    pilot_fields, pilots = read_csv(root / "ckda_d0_resource_pilot.csv")
    if tuple(pilot_fields) != tuple(pilot_module.PILOT_FIELDS):
        raise RuntimeError("resource pilot schema drift")
    pilot_ids = [row["candidate_id"] for row in pilots]
    expected_pilots = ["E3"] + (["I1"] if expected_i1 == "PASS" else [])
    if pilot_ids != expected_pilots:
        raise RuntimeError(f"resource pilot candidates drift: {pilot_ids} != {expected_pilots}")
    for row in pilots:
        if row["status"] != "PASS" or row["forward_finite"] != "true":
            raise RuntimeError(f"resource pilot failed: {row['candidate_id']}")
        if int(row["performance_embeddings_persisted"]) != 0:
            raise RuntimeError("resource pilot persisted embedding values")
        if int(row["labels_read"]) != 0 or int(row["final_files_opened"]) != 0:
            raise RuntimeError("resource pilot boundary failure")
        if int(row["pilot_raw_packets"]) <= 0 or int(row["pilot_raw_packets"]) > 100_000:
            raise RuntimeError("resource pilot packet bound violated")
        if float(row["pilot_median_raw_packets_per_second"]) <= 0:
            raise RuntimeError("resource pilot throughput is nonpositive")

    measurements = json.loads((root / "ckda_d0_resource_pilot_measurements.json").read_text(encoding="utf-8"))
    if measurements.get("status") != "CKDA_D0_RESOURCE_PILOT_COMPLETE":
        raise RuntimeError("resource measurements are not terminal")
    if int(measurements.get("runs_per_candidate", -1)) != 3 or int(measurements.get("warmup_runs_per_candidate", -1)) != 1:
        raise RuntimeError("resource pilot repetition contract drift")
    for candidate in expected_pilots:
        values = measurements["candidates"][candidate]
        if len(values["run_seconds"]) != 3 or not all(float(value) > 0 for value in values["run_seconds"]):
            raise RuntimeError(f"resource pilot run evidence incomplete: {candidate}")
        if int(values["session_count"]) <= 0 or int(values["session_count"]) > 100:
            raise RuntimeError(f"resource pilot session bound violated: {candidate}")

    exclusion = json.loads((root / "ckda_d0_final_exclusion_audit.json").read_text(encoding="utf-8"))
    if exclusion.get("status") != "PASS" or int(exclusion.get("final_files_opened", -1)) != 0:
        raise RuntimeError("FINAL exclusion audit failed")
    expected_reasons = {
        "processed/iotsim-cooler-motor-5.csv": "FINAL_DENYLIST",
        "processed/iotsim-hydraulic-system-1.csv": "UPSTREAM_RAW51_UNOBSERVABLE_MASK",
    }
    if exclusion.get("excluded_fit_source_reasons") != expected_reasons:
        raise RuntimeError("P0-B reason-code boundary drift")

    verdict = json.loads((root / "ckda_d0_verdict.json").read_text(encoding="utf-8"))
    if verdict.get("status") not in ALLOWED_VERDICTS:
        raise RuntimeError("invalid D0 verdict")
    if verdict.get("contract_sha256") != CONTRACT_SHA256:
        raise RuntimeError("verdict contract drift")
    if verdict.get("candidate_audit_sha256") != sha256_file(root / "ckda_d0_candidate_audit.csv"):
        raise RuntimeError("verdict candidate audit hash mismatch")
    for field in ("final_files_opened", "performance_embeddings_generated", "labels_read"):
        if int(verdict.get(field, -1)) != 0:
            raise RuntimeError(f"verdict boundary failure: {field}")
    pass_rows = [row for row in candidates if row["hard_gate_status"] == "PASS"]
    pass_rows.sort(key=__import__("functools").cmp_to_key(audit_module.compare_ranked))
    expected_ranked = [row["candidate_id"] for row in pass_rows]
    if verdict.get("ranked_candidates") != expected_ranked:
        raise RuntimeError("verdict ranking drift")
    if verdict.get("primary") != (expected_ranked[0] if expected_ranked else None):
        raise RuntimeError("verdict primary drift")
    if verdict.get("backup") != (expected_ranked[1] if len(expected_ranked) > 1 else None):
        raise RuntimeError("verdict backup drift")

    report = "\n".join(
        [
            "# CKDA D0 representation compatibility audit result",
            "",
            f"- status: `{verdict['status']}`",
            f"- primary: `{verdict.get('primary')}`",
            f"- backup: `{verdict.get('backup')}`",
            f"- I1 data gate: `{census['i1_data_gate']}` ({census['i1_fit_sessions']} sessions, {census['i1_fit_tokens']} tokens)",
            "- FINAL files opened: `0`",
            "- labels read: `0`",
            "- performance embeddings persisted: `0`",
            "",
            "This D0 verdict is a compatibility decision only. It does not claim detector-performance improvement and authorizes only a separately frozen D1 protocol.",
            "",
        ]
    )
    atomic_text(root / "ckda_d0_result_report.md", report)
    hash_names = [*MANDATORY, "ckda_d0_result_report.md"]
    sums = "".join(f"{sha256_file(root / name)}  {name}\n" for name in hash_names)
    atomic_text(root / "SHA256SUMS", sums)
    validation = {
        "status": "PASS",
        "contract_sha256": CONTRACT_SHA256,
        "candidate_schema_columns": 50,
        "candidate_rows": 4,
        "resource_pilot_candidates": expected_pilots,
        "resource_pilot_runs_per_candidate": 3,
        "ranked_candidates": expected_ranked,
        "verdict": verdict["status"],
        "final_files_opened": 0,
        "labels_read": 0,
        "performance_embeddings_persisted": 0,
        "sha256sums_sha256": sha256_file(root / "SHA256SUMS"),
    }
    atomic_json(root / "ckda_d0_validation_report.json", validation)
    print(json.dumps(validation, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--result", type=Path, required=True)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--audit-module", type=Path, required=True)
    result.add_argument("--pilot-module", type=Path, required=True)
    return result


if __name__ == "__main__":
    if sys.argv[1:] == ["contract-test"]:
        contract_test()
    else:
        validate(parser().parse_args())
