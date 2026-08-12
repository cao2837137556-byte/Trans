#!/usr/bin/env python3
"""Strictly validate a complete CKDA D1 result and build its pullback allowlist."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core
import issue27ckda_d1_probe_runner_v1 as probes


MANDATORY = (
    "ckda_d1_benign_census.json",
    "ckda_d1_benign_member_census.csv",
    "ckda_d1_benign_exclusions.csv",
    "ckda_d1_fit_select_plan.csv",
    "ckda_d1_fit_select_role_plan_audit.json",
    "ckda_d1_fit_select_target_metadata.csv",
    "ckda_d1_fit_select_target_metadata.csv.audit.json",
    "ckda_d1_fit_select_embeddings.npz",
    "ckda_d1_fit_select_embeddings.npz.audit.json",
    "ckda_d1_probe_state.npz",
    "ckda_d1_threshold_freeze_marker.json",
    "ckda_d1_g0_threshold_frontier.csv",
    "ckda_d1_p1_threshold_frontier.csv",
    "ckda_d1_p2_threshold_frontier.csv",
    "ckda_d1_select_scores.csv.gz",
    "ckda_d1_report_plan.csv",
    "ckda_d1_report_role_plan_audit.json",
    "ckda_d1_report_target_metadata.csv",
    "ckda_d1_report_target_metadata.csv.audit.json",
    "ckda_d1_report_embeddings.npz",
    "ckda_d1_report_embeddings.npz.audit.json",
    "ckda_d1_report_embeddings.npz.metadata.csv.gz",
    "ckda_d1_report_scores.csv.gz",
    "ckda_d1_report_score_audit.json",
    "ckda_d1_family_ood_and_baseline_metrics.csv",
    "ckda_d1_target_coverage_by_role_source.csv",
    "ckda_d1_bootstrap_intervals.csv",
    "ckda_d1_verdict.json",
    "ckda_d1_candidate_progression.json",
)

PULLBACK = (
    "ckda_d1_benign_census.json",
    "ckda_d1_benign_member_census.csv",
    "ckda_d1_benign_exclusions.csv",
    "ckda_d1_fit_select_role_plan_audit.json",
    "ckda_d1_fit_select_target_metadata.csv.audit.json",
    "ckda_d1_fit_select_embeddings.npz.audit.json",
    "ckda_d1_threshold_freeze_marker.json",
    "ckda_d1_g0_threshold_frontier.csv",
    "ckda_d1_p1_threshold_frontier.csv",
    "ckda_d1_p2_threshold_frontier.csv",
    "ckda_d1_report_role_plan_audit.json",
    "ckda_d1_report_target_metadata.csv.audit.json",
    "ckda_d1_report_embeddings.npz.audit.json",
    "ckda_d1_report_score_audit.json",
    "ckda_d1_family_ood_and_baseline_metrics.csv",
    "ckda_d1_target_coverage_by_role_source.csv",
    "ckda_d1_bootstrap_intervals.csv",
    "ckda_d1_verdict.json",
    "ckda_d1_candidate_progression.json",
    "ckda_d1_result_report.md",
    "ckda_d1_validation_report.json",
    "SHA256SUMS",
)


def load_json(path: Path) -> Dict[str, object]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def atomic_text(path: Path, value: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix="." + path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def validate_embedding(path: Path, plan: Path, candidate: str, rows: int) -> Dict[str, object]:
    uids, values, missing, actual_candidate = probes.load_embeddings(path, core.sha256_file(plan))
    if actual_candidate != candidate or len(uids) != rows or values.shape[0] != rows:
        raise RuntimeError("embedding candidate/cardinality drift: %s" % path)
    if bool(np.any(~np.isfinite(values[~missing]))):
        raise RuntimeError("nonfinite embedded representation")
    return {"rows": rows, "width": int(values.shape[1]), "missing": int(missing.sum())}


def validate_plan_audit(root: Path, scope: str, plan_name: str, rows: int) -> None:
    audit_name = "ckda_d1_%s_role_plan_audit.json" % scope
    audit = load_json(root / audit_name)
    expected_status = "CKDA_D1_%s_ROLE_PLAN_PASS" % scope.upper()
    if audit.get("status") != expected_status or audit.get("contract_sha256") != core.CONTRACT_SHA256:
        raise RuntimeError("role-plan audit identity drift: %s" % audit_name)
    if int(audit.get("final_files_opened", -1)) != 0:
        raise RuntimeError("role-plan audit FINAL boundary failure: %s" % audit_name)
    row_field = "fit_select_rows" if scope == "fit_select" else "report_rows"
    sha_field = "fit_select_plan_sha256" if scope == "fit_select" else "report_plan_sha256"
    if int(audit.get(row_field, -1)) != rows:
        raise RuntimeError("role-plan audit denominator drift: %s" % audit_name)
    if audit.get(sha_field) != core.sha256_file(root / plan_name):
        raise RuntimeError("role-plan audit SHA drift: %s" % audit_name)


def validate_target_audit(root: Path, scope: str, plan_name: str, target_name: str, rows: int) -> None:
    audit_name = target_name + ".audit.json"
    audit = load_json(root / audit_name)
    if audit.get("status") != "CKDA_D1_TARGET_METADATA_PASS" or audit.get("scope") != scope:
        raise RuntimeError("target metadata audit identity drift: %s" % audit_name)
    if audit.get("contract_sha256") != core.CONTRACT_SHA256 or int(audit.get("final_files_opened", -1)) != 0:
        raise RuntimeError("target metadata audit contract/FINAL boundary failure: %s" % audit_name)
    if int(audit.get("rows", -1)) != rows or int(audit.get("unique_uids", -1)) != rows:
        raise RuntimeError("target metadata audit denominator drift: %s" % audit_name)
    if audit.get("plan_sha256") != core.sha256_file(root / plan_name):
        raise RuntimeError("target metadata plan lineage drift: %s" % audit_name)
    if audit.get("output_sha256") != core.sha256_file(root / target_name):
        raise RuntimeError("target metadata output SHA drift: %s" % audit_name)


def contract_test() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "x.txt"
        atomic_text(path, "one\ntwo\n")
        if path.read_bytes() != b"one\ntwo\n":
            raise RuntimeError("validator atomic LF contract failed")
    print("CKDA_D1_VALIDATOR_CONTRACT_PASS")


def run(args: argparse.Namespace) -> None:
    root = Path(args.result)
    core.verify_contract(args.contract)
    if not root.is_dir():
        raise RuntimeError("D1 result stage is absent")
    for name in MANDATORY:
        if not (root / name).is_file() or (root / name).stat().st_size <= 0:
            raise RuntimeError("mandatory D1 result absent: %s" % name)
    for marker in ("engineering_failure.json", "job_failure.txt", "slurm_failure.txt"):
        if (root / marker).exists():
            raise RuntimeError("failure marker present in result: %s" % marker)

    census = load_json(root / "ckda_d1_benign_census.json")
    gate = census.get("gate", {})
    if census.get("status") != "CKDA_D1_BENIGN_CENSUS_COMPLETE":
        raise RuntimeError("benign census is not terminal")
    if int(census.get("final_files_opened", -1)) != 0 or int(census.get("raw_label_columns_read", -1)) != 0:
        raise RuntimeError("benign census boundary failure")
    if int(census.get("visible_packet_upper_bound", -1)) >= core.BENIGN_MIN_TOKENS:
        raise RuntimeError("current frozen benign upper bound unexpectedly changed")
    if bool(gate.get("passed")) or gate.get("status") != core.PRIMARY_PRECONDITION_FAILED:
        raise RuntimeError("I1 must fail only the frozen benign precondition on this dataset")

    progression = load_json(root / "ckda_d1_candidate_progression.json")
    if progression != {
        "contract_sha256": core.CONTRACT_SHA256,
        "e3_open_reason": "I1_PRIMARY_PRECONDITION_FAILED",
        "e3_opened": True,
        "final_files_opened": 0,
        "i1_embeddings_generated": 0,
        "i1_training_started": False,
        "primary": "I1",
        "selected_candidate": "E3",
        "status": "CKDA_D1_FROZEN_PROGRESSION_PASS",
    }:
        raise RuntimeError("candidate progression identity drift")

    fit_plan = pd.read_csv(root / "ckda_d1_fit_select_plan.csv", keep_default_na=False)
    report_plan = pd.read_csv(root / "ckda_d1_report_plan.csv", keep_default_na=False)
    if len(fit_plan) != 25_467 or len(report_plan) != 262_050:
        raise RuntimeError("D1 plan denominator drift")
    if fit_plan["uid"].duplicated().any() or report_plan["uid"].duplicated().any():
        raise RuntimeError("D1 plan UID collision")
    validate_plan_audit(root, "fit_select", "ckda_d1_fit_select_plan.csv", 25_467)
    validate_plan_audit(root, "report", "ckda_d1_report_plan.csv", 262_050)
    validate_target_audit(
        root, "fit-select", "ckda_d1_fit_select_plan.csv",
        "ckda_d1_fit_select_target_metadata.csv", 25_467,
    )
    validate_target_audit(
        root, "report", "ckda_d1_report_plan.csv",
        "ckda_d1_report_target_metadata.csv", 262_050,
    )
    fit_embedding = validate_embedding(
        root / "ckda_d1_fit_select_embeddings.npz", root / "ckda_d1_fit_select_plan.csv", "E3", 25_467
    )
    report_embedding = validate_embedding(
        root / "ckda_d1_report_embeddings.npz", root / "ckda_d1_report_plan.csv", "E3", 262_050
    )

    marker = load_json(root / "ckda_d1_threshold_freeze_marker.json")
    if marker.get("status") != "CKDA_D1_THRESHOLDS_FROZEN" or marker.get("candidate_id") != "E3":
        raise RuntimeError("threshold marker identity drift")
    if marker.get("fit_select_plan_sha256") != core.sha256_file(root / "ckda_d1_fit_select_plan.csv"):
        raise RuntimeError("threshold marker fit/select lineage drift")
    if int(marker.get("report_rows_opened", -1)) != 0 or int(marker.get("report_labels_opened", -1)) != 0:
        raise RuntimeError("report opened before threshold freeze")
    for probe in ("G0", "P1", "P2"):
        frontier = root / ("ckda_d1_%s_threshold_frontier.csv" % probe.lower())
        if marker.get("frontier_sha256", {}).get(probe) != core.sha256_file(frontier):
            raise RuntimeError("threshold frontier SHA drift: %s" % probe)

    score_audit = load_json(root / "ckda_d1_report_score_audit.json")
    if score_audit.get("status") != "CKDA_D1_ONE_SHOT_REPORT_SCORED":
        raise RuntimeError("report score audit is not terminal")
    if int(score_audit.get("score_rows", -1)) != 786_150 or int(score_audit.get("report_rows", -1)) != 262_050:
        raise RuntimeError("report score denominator drift")
    if score_audit.get("report_scores_sha256") != core.sha256_file(root / "ckda_d1_report_scores.csv.gz"):
        raise RuntimeError("report score hash mismatch")

    verdict = load_json(root / "ckda_d1_verdict.json")
    allowed = {core.ACTIONABLE, core.STRONG_GEOMETRIC, core.WEAK_ONLY, core.NO_ACTIONABLE}
    if verdict.get("status") != "PASS" or verdict.get("verdict") not in allowed:
        raise RuntimeError("D1 scientific verdict invalid")
    if verdict.get("candidate_id") != "E3" or int(verdict.get("final_files_opened", -1)) != 0:
        raise RuntimeError("D1 verdict identity/FINAL boundary failure")
    if bool(verdict.get("go_d2")) != (verdict.get("verdict") == core.ACTIONABLE):
        raise RuntimeError("GO_D2 alias drift")

    coverage = pd.read_csv(root / "ckda_d1_target_coverage_by_role_source.csv")
    if int(coverage["target_rows"].sum()) != 262_050:
        raise RuntimeError("coverage table denominator drift")
    if int(coverage["duplicate_rows"].sum()) != 0 or int(coverage["nonfinite_nonmissing_rows"].sum()) != 0:
        raise RuntimeError("coverage table contract failure")
    bootstrap = pd.read_csv(root / "ckda_d1_bootstrap_intervals.csv")
    if len(bootstrap) != 6 or set(bootstrap["probe_id"]) != {"G0", "P1", "P2"}:
        raise RuntimeError("bootstrap evidence identity drift")
    if not (pd.to_numeric(bootstrap["reps_requested"], errors="raise") == 2000).all():
        raise RuntimeError("bootstrap repetition drift")

    report = "\n".join([
        "# CKDA D1 frozen representation probe result",
        "",
        "- status: `%s`" % verdict["verdict"],
        "- GO_D2: `%s`" % str(bool(verdict["go_d2"])).lower(),
        "- primary I1: `PRIMARY_PRECONDITION_FAILED` (benign-only gate)",
        "- backup/control E3: `OPENED_BY_FROZEN_PROGRESSION`",
        "- report rows: `262050`",
        "- FINAL files opened: `0`",
        "",
        "This is the one-shot D1 verdict for the frozen E3 backup after the I1 benign-only precondition failed. It does not authorize a new candidate or adaptation.",
        "",
    ])
    atomic_text(root / "ckda_d1_result_report.md", report)
    hash_names = [*MANDATORY, "ckda_d1_result_report.md"]
    atomic_text(root / "SHA256SUMS", "".join(
        "%s  %s\n" % (core.sha256_file(root / name), name) for name in hash_names
    ))
    validation = {
        "status": "PASS",
        "contract_sha256": core.CONTRACT_SHA256,
        "selected_candidate": "E3",
        "fit_select_rows": 25_467,
        "report_rows": 262_050,
        "score_rows": 786_150,
        "fit_embedding": fit_embedding,
        "report_embedding": report_embedding,
        "bootstrap_rows": 6,
        "verdict": verdict["verdict"],
        "go_d2": bool(verdict["go_d2"]),
        "final_files_opened": 0,
        "sha256sums_sha256": core.sha256_file(root / "SHA256SUMS"),
    }
    core.atomic_json(root / "ckda_d1_validation_report.json", validation)
    atomic_text(root / "PULLBACK_ALLOWLIST.txt", "\n".join(PULLBACK) + "\n")
    print(json.dumps(validation, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description=__doc__)
    value.add_argument("--result", type=Path, required=True)
    value.add_argument("--contract", type=Path, required=True)
    return value


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["contract-test"]:
        contract_test()
    else:
        run(parser().parse_args())
