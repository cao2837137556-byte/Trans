#!/usr/bin/env python3
"""Contract tests for CKDC D0-F Phase A."""

from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "issue27ckdc_d0f_certificate_phase_a_v1.py"
SPEC = importlib.util.spec_from_file_location("ckdc_d0f_phase_a", str(MODULE_PATH))
assert SPEC and SPEC.loader
phase_a = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(phase_a)
ROOT = HERE.parents[1]
STAGE = ROOT / phase_a.EXPECTED_STAGE_REL
D0 = ROOT / phase_a.EXPECTED_D0_REL
CKBW = phase_a.EXPECTED_CKBW


def gate_frame(covered: int = 300, groups: int = 3, support_rows: int = 69) -> pd.DataFrame:
    rows = []
    for index in range(4986):
        cert = index < covered
        rows.append({
            "uid": "b%d" % index,
            "role": "aux_select",
            "source_group": "s%d" % (index % groups),
            "label_metric_only": 0,
            "p2_hard": True,
            "m7_hard": False,
            "normality_certificate": cert,
            "candidate_hard": not cert,
            "p2_and_m7_hard": False,
            "m7_normal": True,
        })
    for index in range(support_rows):
        rows.append({
            "uid": "a%d" % index,
            "role": "support_val",
            "source_group": "attack",
            "label_metric_only": 1,
            "p2_hard": True,
            "m7_hard": True,
            "normality_certificate": False,
            "candidate_hard": True,
            "p2_and_m7_hard": True,
            "m7_normal": False,
        })
    return pd.DataFrame(rows)


class CKDCD0FPhaseAContractTests(unittest.TestCase):
    def test_01_python39_syntax_module(self) -> None:
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), filename=str(MODULE_PATH), feature_version=(3, 9))

    def test_02_python39_syntax_tests(self) -> None:
        ast.parse(Path(__file__).read_text(encoding="utf-8"), filename=__file__, feature_version=(3, 9))

    def test_03_contract_sha_literal(self) -> None:
        self.assertEqual(phase_a.sha256_file(ROOT / phase_a.CONTRACT_REL), phase_a.CONTRACT_SHA256)

    def test_04_ckda_contract_sha_literal(self) -> None:
        self.assertEqual(phase_a.sha256_file(ROOT / phase_a.CKDA_CONTRACT_REL), phase_a.CKDA_CONTRACT_SHA256)

    def test_05_frozen_input_hashes(self) -> None:
        self.assertEqual(phase_a.sha256_file(STAGE / "ckda_d1_fit_select_plan.csv"), phase_a.FIT_SELECT_PLAN_SHA256)
        self.assertEqual(phase_a.sha256_file(STAGE / "ckda_d1_threshold_freeze_marker.json"), phase_a.THRESHOLD_MARKER_SHA256)
        self.assertEqual(phase_a.sha256_file(CKBW), phase_a.CKBW_SHA256)

    def test_06_d0_select_identity(self) -> None:
        identity = phase_a.verify_d0_select_identity(D0)
        self.assertEqual(identity["select_quadrants"]["sha256"], phase_a.D0_SELECT_SHA256)

    def test_07_exact_path_identity(self) -> None:
        phase_a.assert_exact_paths(ROOT.resolve(), STAGE.resolve(), D0.resolve(), CKBW.resolve())

    def test_08_wrong_path_rejected(self) -> None:
        with self.assertRaises(RuntimeError):
            phase_a.assert_exact_paths(ROOT.resolve(), (STAGE.parent / "wrong").resolve(), D0.resolve(), CKBW.resolve())

    def test_09_every_forbidden_marker_rejected(self) -> None:
        for marker in phase_a.FORBIDDEN_PATH_MARKERS:
            with self.subTest(marker=marker), self.assertRaises(RuntimeError):
                phase_a.assert_no_forbidden_path([Path("safe") / marker / "x.csv"])

    def test_10_bool_series_exact(self) -> None:
        actual = phase_a.bool_series(pd.Series([0, 1, 0, 1])).tolist()
        self.assertEqual(actual, [False, True, False, True])

    def test_11_bool_series_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            phase_a.bool_series(pd.Series([0, 2]))

    def test_12_bool_series_rejects_missing(self) -> None:
        with self.assertRaises(ValueError):
            phase_a.bool_series(pd.Series([True, None], dtype="object"))

    def test_13_invariant_duplicate_is_accepted(self) -> None:
        frame = pd.DataFrame({"uid": ["x", "x"], "v": [1, 1]})
        dedup, disagreements = phase_a.invariant_deduplicate(frame, ["v"])
        self.assertEqual(len(dedup), 1)
        self.assertEqual(disagreements["v"], 0)

    def test_14_variant_duplicate_is_rejected(self) -> None:
        frame = pd.DataFrame({"uid": ["x", "x"], "v": [1, 2]})
        with self.assertRaises(RuntimeError):
            phase_a.invariant_deduplicate(frame, ["v"])

    def test_15_formula_truth_table(self) -> None:
        rows = []
        for p2 in (False, True):
            for tail in (False, True):
                for c1 in (False, True):
                    for ckbq in (False, True):
                        rows.append({
                            "p2_hard": p2,
                            "tail_margin_score": 0.0 if tail else 1.0,
                            "tail_margin_tau_normal": 0.5,
                            "c1_hard": not c1,
                            "frozen_ckbq_hard": not ckbq,
                            "m7_hard": False,
                        })
        result = phase_a.apply_candidate(pd.DataFrame(rows))
        expected_cert = result["tail_normal"] & result["c1_normal"] & result["ckbq_normal"]
        self.assertTrue(result["normality_certificate"].eq(expected_cert).all())
        self.assertTrue(result["candidate_hard"].eq(result["p2_hard"] & ~expected_cert).all())

    def test_16_threshold_equality_is_normal(self) -> None:
        frame = pd.DataFrame({
            "p2_hard": [True], "tail_margin_score": [0.5], "tail_margin_tau_normal": [0.5],
            "c1_hard": [False], "frozen_ckbq_hard": [False], "m7_hard": [False],
        })
        result = phase_a.apply_candidate(frame)
        self.assertTrue(bool(result.loc[0, "tail_normal"]))
        self.assertTrue(bool(result.loc[0, "normality_certificate"]))
        self.assertFalse(bool(result.loc[0, "candidate_hard"]))

    def test_17_nonfinite_candidate_evidence_fails_closed(self) -> None:
        frame = pd.DataFrame({
            "p2_hard": [True], "tail_margin_score": [np.nan], "tail_margin_tau_normal": [0.5],
            "c1_hard": [False], "frozen_ckbq_hard": [False], "m7_hard": [False],
        })
        result = phase_a.apply_candidate(frame)
        self.assertFalse(bool(result.loc[0, "normality_certificate"]))
        self.assertTrue(bool(result.loc[0, "candidate_hard"]))

    def test_18_gate_all_passes_at_300(self) -> None:
        clauses, summary = phase_a.evaluate_clauses(gate_frame(covered=300, groups=3))
        self.assertTrue(summary["all_clauses_passed"])
        self.assertTrue(all(row["passed"] for row in clauses))

    def test_19_gate_299_fails(self) -> None:
        _, summary = phase_a.evaluate_clauses(gate_frame(covered=299, groups=3))
        self.assertFalse(summary["all_clauses_passed"])

    def test_20_gate_two_groups_fails(self) -> None:
        _, summary = phase_a.evaluate_clauses(gate_frame(covered=300, groups=2))
        self.assertFalse(summary["all_clauses_passed"])

    def test_21_gate_max_share_exact_80_passes(self) -> None:
        frame = gate_frame(covered=300, groups=3)
        covered_index = frame.index[:300]
        frame.loc[covered_index, "source_group"] = ["dominant"] * 240 + ["s1"] * 30 + ["s2"] * 30
        _, summary = phase_a.evaluate_clauses(frame)
        self.assertEqual(summary["max_covered_source_share"], 0.8)
        self.assertTrue(summary["all_clauses_passed"])

    def test_22_gate_above_80_fails(self) -> None:
        frame = gate_frame(covered=300, groups=3)
        covered_index = frame.index[:300]
        frame.loc[covered_index, "source_group"] = ["dominant"] * 241 + ["s1"] * 30 + ["s2"] * 29
        _, summary = phase_a.evaluate_clauses(frame)
        self.assertFalse(summary["all_clauses_passed"])

    def test_23_support_must_be_exact_69(self) -> None:
        _, summary = phase_a.evaluate_clauses(gate_frame(covered=300, groups=3, support_rows=68))
        self.assertFalse(summary["all_clauses_passed"])

    def test_24_and_equivalence_closes(self) -> None:
        frame = gate_frame(covered=300, groups=3)
        frame["p2_and_m7_hard"] = frame["candidate_hard"]
        _, summary = phase_a.evaluate_clauses(frame)
        self.assertFalse(summary["all_clauses_passed"])

    def test_25_m7_equivalence_closes(self) -> None:
        frame = gate_frame(covered=300, groups=3)
        frame["m7_normal"] = frame["normality_certificate"]
        _, summary = phase_a.evaluate_clauses(frame)
        self.assertFalse(summary["all_clauses_passed"])

    def test_26_payload_hash_is_deterministic(self) -> None:
        self.assertEqual(
            phase_a.canonical_payload_sha256({"b": 2, "a": 1}),
            phase_a.canonical_payload_sha256({"a": 1, "b": 2}),
        )

    def test_27_atomic_text_uses_lf(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.txt"
            phase_a.atomic_text(path, "a\nb\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")

    def test_28_failure_output_has_no_scientific_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "failure"
            try:
                raise RuntimeError("synthetic")
            except RuntimeError as exc:
                phase_a.failure_only(output, exc)
            payload = json.loads((output / "engineering_failure.json").read_text(encoding="utf-8"))
            self.assertFalse(payload["scientific_verdict_written"])
            self.assertEqual(list(output.iterdir()), [output / "engineering_failure.json"])

    def test_29_cli_has_no_phase_b_or_report_argument(self) -> None:
        with mock.patch("sys.argv", ["phase-a", "--help"]):
            with self.assertRaises(SystemExit):
                phase_a.parse_args()
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn("report_scores", source)
        self.assertNotIn("phase-b", source.lower())

    def test_30_real_legal_select_load(self) -> None:
        frame, audit = phase_a.load_legal_select(STAGE, D0, CKBW)
        self.assertEqual(len(frame), 7069)
        self.assertEqual(audit["sentinel_counts"]["benign_p2_hard_m7_normal"], 4986)
        self.assertEqual(audit["sentinel_counts"]["attack_p2_hard_m7_normal"], 0)

    def test_31_real_p2_threshold_reproduces(self) -> None:
        frame, _ = phase_a.load_legal_select(STAGE, D0, CKBW)
        marker = json.loads((STAGE / "ckda_d1_threshold_freeze_marker.json").read_text(encoding="utf-8"))
        threshold = float(marker["thresholds"]["P2"]["value"])
        self.assertTrue(frame["p2_hard"].eq(frame["score"].ge(threshold)).all())

    def test_32_real_formula_preserves_support(self) -> None:
        frame, _ = phase_a.load_legal_select(STAGE, D0, CKBW)
        result = phase_a.apply_candidate(frame)
        support = result.loc[result["role"].eq("support_val")]
        self.assertEqual(len(support), 69)
        self.assertTrue(bool(support["candidate_hard"].all()))

    def test_33_formula_identity_is_literal(self) -> None:
        self.assertEqual(phase_a.FORMULA["normality_certificate"], "tail_normal AND c1_normal AND ckbq_normal")
        self.assertEqual(phase_a.FORMULA["candidate_hard"], "P2_hard AND NOT normality_certificate")

    def test_34_csv_roundtrip_tolerance_is_bounded(self) -> None:
        _, audit = phase_a.load_legal_select(STAGE, D0, CKBW)
        observed = audit["d0_ckbw_csv_roundtrip_audit"]["tail_margin_score"]
        self.assertLessEqual(observed["max_relative_difference"], observed["rtol"])
        self.assertEqual(observed["atol"], 0.0)

    def test_35_real_end_to_end_packaging_and_readback(self) -> None:
        with tempfile.TemporaryDirectory(dir=str(ROOT / "runs")) as temp:
            output = Path(temp) / "phase_a"
            validation = phase_a.execute(ROOT.resolve(), STAGE.resolve(), D0.resolve(), CKBW.resolve(), output)
            self.assertEqual(validation["status"], "PASS")
            self.assertFalse(validation["phase_b_authorized"])
            sums = {}
            for line in (output / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, name = line.split(maxsplit=1)
                sums[name.strip()] = digest
            self.assertGreaterEqual(len(sums), 7)
            for name, digest in sums.items():
                self.assertEqual(phase_a.sha256_file(output / name), digest)
            self.assertFalse((output / "engineering_failure.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
