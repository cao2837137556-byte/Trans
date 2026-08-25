#!/usr/bin/env python3
"""CKDC D0-F Phase A: frozen Option-A certificate audit on legal select only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path(
    "runs/mainline_docs/ckdc_d0f_m7_certificate_provenance_preregistered_20260825.md"
)
CONTRACT_SHA256 = "534e0cd4a0617dacbc37ce72e0a6ccad9b138438c7c68c48386edb48b5c93fc1"
CKDA_CONTRACT_REL = Path(
    "runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md"
)
CKDA_CONTRACT_SHA256 = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
FIT_SELECT_PLAN_SHA256 = "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"
THRESHOLD_MARKER_SHA256 = "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"
CKBW_SHA256 = "d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85"
D0_SHA256SUMS_SHA256 = "9a842341e7cea2f4379ee4a834874927f7b411a61c7c033ad0e67ecadda20161"
D0_SELECT_SHA256 = "90e817b11a7d08aa2ce09749f816aadb1c13160f46bc5a2d8c09217ff5daeb67"

EXPECTED_STAGE_REL = Path(
    "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
)
EXPECTED_D0_REL = Path(
    "runs/issue27ckdc_d0_existing_evidence_diagnostic_v1_2026-08-20_local"
)
EXPECTED_CKBW = Path(
    "D:/study/paper/anomaly_detection/paper04/supercompute_transfer/"
    "ckbw_157624_extract/issue27ckbw_tail_margin_dual_control_v1_2026-08-03_"
    "seed27_amd_157624/ckbw_record_predictions.csv.gz"
)

SELECT_ROLES = {"support_val", "aux_normal_select", "aux_select"}
ROLE_COUNTS = {"support_val": 69, "aux_normal_select": 4000, "aux_select": 3000}
FORBIDDEN_PATH_MARKERS = (
    "report", "held", "future", "sealed", "cooler", "seed37", "seed_37",
    "seed-37", "seed47", "seed_47", "seed-47",
)
FINAL_ROW_MARKERS = (
    "cooler-motor", "seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47",
)
M7_COL = "hard__M7-TabM-TailMargin-DualControl"
FORMULA = {
    "tail_normal": "tail_margin_score <= tail_margin_tau_normal",
    "c1_normal": "c1_hard == 0",
    "ckbq_normal": "frozen_ckbq_hard == 0",
    "normality_certificate": "tail_normal AND c1_normal AND ckbq_normal",
    "candidate_hard": "P2_hard AND NOT normality_certificate",
    "missing_behavior": "non-finite evidence preserves P2 hard",
}


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch for %s: %s != %s" % (path, actual, expected))
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        if bool(series.isna().any()):
            raise ValueError("missing boolean value")
        return series.astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        numeric = pd.to_numeric(series, errors="raise")
        if bool(numeric.isna().any()) or not set(numeric.unique()).issubset({0, 1}):
            raise ValueError("boolean numeric values must be exactly 0/1")
        return numeric.astype(int).astype(bool)
    lowered = series.astype("string").str.strip().str.lower()
    if bool(lowered.isna().any()):
        raise ValueError("missing boolean value")
    allowed = {"0", "1", "false", "true"}
    unexpected = sorted(set(lowered.unique()) - allowed)
    if unexpected:
        raise ValueError("unexpected boolean values: %s" % unexpected)
    return lowered.isin({"1", "true"})


def atomic_text(path: Path, content: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    os.replace(str(temp), str(path))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    frame.to_csv(temp, index=False, lineterminator="\n")
    os.replace(str(temp), str(path))


def canonical_payload_sha256(payload: Mapping[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def assert_no_forbidden_path(paths: Iterable[Path]) -> None:
    for path in paths:
        lowered = str(path).replace("\\", "/").lower()
        hits = [marker for marker in FORBIDDEN_PATH_MARKERS if marker in lowered]
        if hits:
            raise RuntimeError("forbidden Phase-A path marker %s in %s" % (hits, path))


def assert_exact_paths(root: Path, stage: Path, d0: Path, ckbw: Path) -> None:
    expected_stage = (root / EXPECTED_STAGE_REL).resolve()
    expected_d0 = (root / EXPECTED_D0_REL).resolve()
    expected_ckbw = EXPECTED_CKBW.resolve()
    actual = (stage.resolve(), d0.resolve(), ckbw.resolve())
    expected = (expected_stage, expected_d0, expected_ckbw)
    if actual != expected:
        raise RuntimeError("Phase-A path identity mismatch: %s != %s" % (actual, expected))
    assert_no_forbidden_path(actual)


def verify_row_markers(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    combined = pd.Series("", index=frame.index, dtype="object")
    for column in columns:
        if column in frame.columns:
            combined = combined + " " + frame[column].fillna("").astype(str).str.lower()
    hits = pd.Series(False, index=frame.index)
    for marker in FINAL_ROW_MARKERS:
        hits |= combined.str.contains(marker, regex=False)
    if bool(hits.any()):
        raise RuntimeError("FINAL marker found in Phase-A rows")


def verify_d0_select_identity(d0: Path) -> Dict[str, object]:
    sums = require_sha(d0 / "SHA256SUMS", D0_SHA256SUMS_SHA256)
    entries: Dict[str, str] = {}
    for line in (d0 / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            raise RuntimeError("malformed D0 SHA256SUMS line")
        entries[parts[1].strip()] = parts[0]
    if entries.get("ckdc_d0_select_quadrants.csv") != D0_SELECT_SHA256:
        raise RuntimeError("D0 select identity is absent or inconsistent in SHA256SUMS")
    select = require_sha(d0 / "ckdc_d0_select_quadrants.csv", D0_SELECT_SHA256)
    return {"sha256s": sums, "select_quadrants": select}


def invariant_deduplicate(frame: pd.DataFrame, columns: Sequence[str]) -> Tuple[pd.DataFrame, Dict[str, int]]:
    if "uid" not in frame.columns:
        raise ValueError("uid missing")
    disagreements: Dict[str, int] = {}
    for column in columns:
        disagreements[column] = int(frame.groupby("uid", sort=False)[column].nunique(dropna=False).gt(1).sum())
    if any(disagreements.values()):
        raise RuntimeError("CKBW held-view disagreement: %s" % disagreements)
    return frame.drop_duplicates("uid", keep="first").copy(), disagreements


def load_legal_select(stage: Path, d0: Path, ckbw: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    plan_columns = ["uid", "role", "source_group", "attack_family", "label_metric_only"]
    plan = pd.read_csv(stage / "ckda_d1_fit_select_plan.csv", usecols=plan_columns)
    plan = plan.loc[plan["role"].isin(SELECT_ROLES)].copy()
    if plan["uid"].duplicated().any():
        raise RuntimeError("duplicate legal plan UID")
    if len(plan) != 7069 or plan["role"].value_counts().to_dict() != ROLE_COUNTS:
        raise RuntimeError("legal plan denominator mismatch")
    verify_row_markers(plan, plan_columns)

    d0_columns = [
        "uid", "role", "source_group", "attack_family", "label_metric_only", "score",
        "p2_hard", "m7_hard", "tail_margin_score", "tail_margin_tau_normal",
        "tail_margin_tau_attack", "quadrant",
    ]
    frozen = pd.read_csv(d0 / "ckdc_d0_select_quadrants.csv", usecols=d0_columns)
    if len(frozen) != 7069 or frozen["uid"].duplicated().any():
        raise RuntimeError("D0 legal select denominator or UID mismatch")
    verify_row_markers(frozen, ["uid", "role", "source_group", "attack_family"])

    joined = plan.merge(frozen, on="uid", how="left", validate="one_to_one", suffixes=("_plan", "_d0"), indicator=True)
    if not joined["_merge"].eq("both").all():
        raise RuntimeError("D0 select exact join miss")
    for column in ("role", "source_group", "attack_family", "label_metric_only"):
        left = joined["%s_plan" % column].fillna("").astype(str)
        right = joined["%s_d0" % column].fillna("").astype(str)
        if not left.eq(right).all():
            raise RuntimeError("plan/D0 disagreement for %s" % column)
        joined[column] = joined["%s_plan" % column]

    ckbw_columns = [
        "uid", "role", "source_group", "attack_family", "label_metric_only", "c1_hard",
        "frozen_ckbq_hard", M7_COL, "tail_margin_score", "tail_margin_tau_normal",
    ]
    ckbw_frame = pd.read_csv(ckbw, usecols=ckbw_columns)
    ckbw_frame, disagreements = invariant_deduplicate(ckbw_frame, ckbw_columns[1:])
    joined = joined.merge(ckbw_frame, on="uid", how="left", validate="one_to_one", suffixes=("", "_ckbw"), indicator="_ckbw_merge")
    if not joined["_ckbw_merge"].eq("both").all():
        raise RuntimeError("CKBW exact join miss")

    for column in ("role", "source_group", "attack_family", "label_metric_only"):
        right = joined["%s_ckbw" % column].fillna("").astype(str)
        if not joined[column].fillna("").astype(str).eq(right).all():
            raise RuntimeError("CKBW disagreement for %s" % column)

    joined["p2_hard"] = bool_series(joined["p2_hard"])
    joined["m7_hard"] = bool_series(joined["m7_hard"])
    joined["c1_hard"] = bool_series(joined["c1_hard"])
    joined["frozen_ckbq_hard"] = bool_series(joined["frozen_ckbq_hard"])
    joined["m7_hard_ckbw"] = bool_series(joined[M7_COL])
    if not joined["m7_hard"].eq(joined["m7_hard_ckbw"]).all():
        raise RuntimeError("M7 decision disagreement")
    for column in ("score", "tail_margin_score", "tail_margin_tau_normal"):
        values = pd.to_numeric(joined[column], errors="coerce")
        if not np.isfinite(values.to_numpy(dtype=float)).all():
            raise RuntimeError("non-finite required score: %s" % column)
        joined[column] = values.astype(float)
    roundtrip_audit: Dict[str, Dict[str, float]] = {}
    for column in ("tail_margin_score", "tail_margin_tau_normal"):
        other = pd.to_numeric(joined["%s_ckbw" % column], errors="coerce")
        left_values = joined[column].to_numpy(dtype=float)
        right_values = other.to_numpy(dtype=float)
        absolute = np.abs(left_values - right_values)
        relative = absolute / np.maximum(np.abs(right_values), np.finfo(float).tiny)
        roundtrip_audit[column] = {
            "nonzero_rows": int(np.count_nonzero(absolute)),
            "max_absolute_difference": float(absolute.max()),
            "max_relative_difference": float(relative.max()),
            "rtol": 5e-16,
            "atol": 0.0,
        }
        if not np.allclose(left_values, right_values, rtol=5e-16, atol=0.0):
            raise RuntimeError("D0/CKBW score disagreement for %s" % column)
        joined[column] = right_values

    sentinel = joined.groupby(["label_metric_only", "p2_hard", "m7_hard"], dropna=False).size().to_dict()
    expected_sentinel = {
        (0, True, False): 4986,
        (0, False, False): 2014,
        (1, True, True): 69,
    }
    if sentinel != expected_sentinel:
        raise RuntimeError("legal select sentinel mismatch: %s" % sentinel)
    return joined, {
        "rows": int(len(joined)),
        "unique_uids": int(joined["uid"].nunique()),
        "role_counts": {str(k): int(v) for k, v in joined["role"].value_counts().to_dict().items()},
        "ckbw_duplicate_view_disagreements": disagreements,
        "d0_ckbw_csv_roundtrip_audit": roundtrip_audit,
        "sentinel_counts": {
            "benign_p2_hard_m7_normal": 4986,
            "benign_p2_normal_m7_normal": 2014,
            "attack_p2_hard_m7_hard": 69,
            "attack_p2_hard_m7_normal": 0,
        },
    }


def apply_candidate(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["tail_normal"] = result["tail_margin_score"].le(result["tail_margin_tau_normal"])
    result["c1_normal"] = ~result["c1_hard"]
    result["ckbq_normal"] = ~result["frozen_ckbq_hard"]
    result["normality_certificate"] = result["tail_normal"] & result["c1_normal"] & result["ckbq_normal"]
    result["candidate_hard"] = result["p2_hard"] & ~result["normality_certificate"]
    result["p2_and_m7_hard"] = result["p2_hard"] & result["m7_hard"]
    result["m7_normal"] = ~result["m7_hard"]
    return result


def evaluate_clauses(frame: pd.DataFrame) -> Tuple[List[Dict[str, object]], Dict[str, object]]:
    benign_conflict = frame.loc[
        frame["label_metric_only"].eq(0) & frame["p2_hard"] & ~frame["m7_hard"]
    ].copy()
    covered = benign_conflict.loc[benign_conflict["normality_certificate"]].copy()
    source_counts = covered["source_group"].value_counts(dropna=False)
    max_share = float(source_counts.max() / len(covered)) if len(covered) else None
    support = frame.loc[frame["role"].eq("support_val") & frame["label_metric_only"].eq(1)]
    changed_benign = int((benign_conflict["candidate_hard"] != benign_conflict["p2_hard"]).sum())
    differs_and = int((frame["candidate_hard"] != frame["p2_and_m7_hard"]).sum())
    differs_m7 = int((frame["normality_certificate"] != frame["m7_normal"]).sum())
    checks = [
        ("01_literal_frozen_formula", True, "exact section-4 formula"),
        ("02_covered_benign_ge_300", len(covered) >= 300, int(len(covered))),
        ("03_covered_fraction_ge_0_05", len(covered) / len(benign_conflict) >= 0.05, float(len(covered) / len(benign_conflict))),
        ("04_covered_source_groups_ge_3", covered["source_group"].nunique(dropna=False) >= 3, int(covered["source_group"].nunique(dropna=False))),
        ("05_max_source_share_le_0_80", max_share is not None and max_share <= 0.80, max_share),
        ("06_support_attacks_preserved_69_of_69", len(support) == 69 and bool(support["candidate_hard"].all()), int(support["candidate_hard"].sum())),
        ("07_changed_benign_ge_300", changed_benign >= 300, changed_benign),
        ("08_not_equivalent_to_p2_and_m7", differs_and >= 1, differs_and),
        ("09_certificate_not_equivalent_to_m7_normal", differs_m7 >= 1, differs_m7),
        ("10_zero_forbidden_operations", True, 0),
    ]
    rows = [{"clause": name, "passed": bool(passed), "observed": observed} for name, passed, observed in checks]
    summary = {
        "benign_conflict_rows": int(len(benign_conflict)),
        "covered_benign_conflicts": int(len(covered)),
        "coverage_fraction": float(len(covered) / len(benign_conflict)),
        "covered_source_groups": int(covered["source_group"].nunique(dropna=False)),
        "max_covered_source_share": max_share,
        "support_attacks_preserved": int(support["candidate_hard"].sum()),
        "changed_benign_conflicts": changed_benign,
        "rows_differing_from_p2_and_m7": differs_and,
        "rows_certificate_differing_from_m7_normal": differs_m7,
        "all_clauses_passed": all(bool(row["passed"]) for row in rows),
    }
    return rows, summary


def write_sha256s(directory: Path, names: Sequence[str]) -> None:
    lines = ["%s  %s" % (sha256_file(directory / name), name) for name in names]
    atomic_text(directory / "SHA256SUMS", "\n".join(lines) + "\n")


def execute(root: Path, stage: Path, d0: Path, ckbw: Path, output: Path) -> Dict[str, object]:
    assert_exact_paths(root, stage, d0, ckbw)
    identities = {
        "ckdc_d0f_contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256),
        "ckda_d1_contract": require_sha(root / CKDA_CONTRACT_REL, CKDA_CONTRACT_SHA256),
        "fit_select_plan": require_sha(stage / "ckda_d1_fit_select_plan.csv", FIT_SELECT_PLAN_SHA256),
        "threshold_marker": require_sha(stage / "ckda_d1_threshold_freeze_marker.json", THRESHOLD_MARKER_SHA256),
        "ckbw_predictions": require_sha(ckbw, CKBW_SHA256),
        "ckdc_d0_legal_select": verify_d0_select_identity(d0),
    }
    marker = json.loads((stage / "ckda_d1_threshold_freeze_marker.json").read_text(encoding="utf-8"))
    if marker.get("status") != "CKDA_D1_THRESHOLDS_FROZEN" or marker.get("select_rows") != 7069:
        raise RuntimeError("threshold marker status or denominator mismatch")
    p2_threshold = float(marker["thresholds"]["P2"]["value"])

    frame, select_audit = load_legal_select(stage, d0, ckbw)
    if not frame["p2_hard"].eq(frame["score"].ge(p2_threshold)).all():
        raise RuntimeError("P2 threshold disagreement")
    frame = apply_candidate(frame)
    clauses, summary = evaluate_clauses(frame)
    passed = bool(summary["all_clauses_passed"])
    verdict_label = "CKDC_D0F_CERTIFICATE_CANDIDATE_FROZEN" if passed else "CKDC_D0F_NO_CERTIFICATE"

    input_audit = {
        "status": "PASS",
        "identities": identities,
        "select": select_audit,
        "p2_threshold": p2_threshold,
        "review_count": 0,
        "final_opens": 0,
        "report_opens": 0,
        "pcap_opens": 0,
        "training_operations": 0,
        "fitted_parameters": 0,
        "phase_b_path_available": False,
    }

    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".%s.stage." % output.name, dir=str(parent)))
    try:
        row_columns = [
            "uid", "role", "source_group", "attack_family", "label_metric_only", "score",
            "p2_hard", "m7_hard", "tail_margin_score", "tail_margin_tau_normal", "c1_hard",
            "frozen_ckbq_hard", "tail_normal", "c1_normal", "ckbq_normal",
            "normality_certificate", "candidate_hard", "p2_and_m7_hard",
        ]
        atomic_json(stage_dir / "ckdc_d0f_phase_a_input_audit.json", input_audit)
        atomic_csv(stage_dir / "ckdc_d0f_phase_a_certificate_rows.csv", frame[row_columns].sort_values(["role", "source_group", "uid"]))
        atomic_csv(stage_dir / "ckdc_d0f_phase_a_clause_table.csv", pd.DataFrame(clauses))
        atomic_json(stage_dir / "ckdc_d0f_phase_a_summary.json", summary)
        evidence_names = [
            "ckdc_d0f_phase_a_input_audit.json",
            "ckdc_d0f_phase_a_certificate_rows.csv",
            "ckdc_d0f_phase_a_clause_table.csv",
            "ckdc_d0f_phase_a_summary.json",
        ]
        evidence_hashes = {name: sha256_file(stage_dir / name) for name in evidence_names}
        scientific_payload = {
            "status": verdict_label,
            "formula": FORMULA,
            "input_sha256": {
                "contract": CONTRACT_SHA256,
                "ckda_contract": CKDA_CONTRACT_SHA256,
                "fit_select_plan": FIT_SELECT_PLAN_SHA256,
                "threshold_marker": THRESHOLD_MARKER_SHA256,
                "ckbw_predictions": CKBW_SHA256,
                "d0_sha256s": D0_SHA256SUMS_SHA256,
                "d0_select": D0_SELECT_SHA256,
            },
            "denominator": 7069,
            "role_counts": ROLE_COUNTS,
            "clauses": clauses,
            "summary": summary,
            "evidence_sha256": evidence_hashes,
            "phase_b_authorized": False,
            "positive_generalization_evidence": False,
        }
        scientific_payload["canonical_payload_sha256"] = canonical_payload_sha256(scientific_payload)
        marker_name = "ckdc_d0f_phase_a_candidate_marker.json" if passed else "ckdc_d0f_phase_a_no_certificate_verdict.json"
        atomic_json(stage_dir / marker_name, scientific_payload)
        marker_sha = sha256_file(stage_dir / marker_name)
        atomic_text(stage_dir / (marker_name + ".sha256"), "%s  %s\n" % (marker_sha, marker_name))
        validation = {
            "status": "PASS",
            "scientific_status": verdict_label,
            "candidate_marker_file": marker_name if passed else None,
            "candidate_marker_sha256": marker_sha if passed else None,
            "verdict_file": marker_name,
            "verdict_sha256": marker_sha,
            "all_clauses_passed": passed,
            "rows": int(len(frame)),
            "phase_b_authorized": False,
            "engineering_failure_has_no_scientific_verdict": True,
        }
        atomic_json(stage_dir / "ckdc_d0f_phase_a_validation_report.json", validation)
        output_names = evidence_names + [marker_name, marker_name + ".sha256", "ckdc_d0f_phase_a_validation_report.json"]
        write_sha256s(stage_dir, output_names)
        if output.exists():
            raise FileExistsError(str(output))
        os.replace(str(stage_dir), str(output))
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    return validation


def failure_only(output: Path, exc: BaseException) -> None:
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "engineering_failure.json", {
        "status": "ENGINEERING_FAILURE",
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "scientific_verdict_written": False,
        "phase_b_authorized": False,
    })


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--d0", type=Path, required=True)
    parser.add_argument("--ckbw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    try:
        validation = execute(
            args.root.resolve(), args.stage.resolve(), args.d0.resolve(), args.ckbw.resolve(), output
        )
        print(json.dumps(validation, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        if not output.exists():
            failure_only(output, exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
