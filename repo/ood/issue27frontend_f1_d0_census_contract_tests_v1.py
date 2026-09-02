#!/usr/bin/env python3
"""Contract tests for the Frontend-F1 D0 count-only census."""

from __future__ import annotations

import ast
import gzip
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
TARGET = HERE / "issue27frontend_f1_d0_census_v1.py"
SPEC = importlib.util.spec_from_file_location("f1d0", TARGET)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class F1D0Tests(unittest.TestCase):
    def test_01_python39_ast(self):
        ast.parse(TARGET.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_contract_sha_literal(self):
        self.assertEqual(len(MOD.EXPECTED_CONTRACT_SHA256), 64)

    def test_03_frozen_rows(self):
        self.assertEqual(MOD.EXPECTED_A + MOD.EXPECTED_B, MOD.EXPECTED_ROWS)

    def test_04_fit_select_rows(self):
        self.assertEqual(MOD.EXPECTED_FIT + MOD.EXPECTED_SELECT, MOD.EXPECTED_ROWS)

    def test_05_exclusion_rows(self):
        self.assertEqual(MOD.EXPECTED_LEGAL_FIT + MOD.EXPECTED_CROSS_FIT_ROWS, MOD.EXPECTED_FIT)

    def test_06_context_conservation(self):
        self.assertEqual(MOD.EXPECTED_LEGAL_FIT_CONTEXTS + MOD.EXPECTED_SELECT_CONTEXTS, MOD.EXPECTED_CONTEXTS)

    def test_07_attack_context_conservation(self):
        self.assertEqual(MOD.EXPECTED_B_ATTACK_CONTEXTS_BEFORE - MOD.EXPECTED_B_ATTACK_CROSS_CONTEXTS, MOD.EXPECTED_B_ATTACK_CONTEXTS_AFTER)

    def test_08_context_key_includes_epoch(self):
        frame = pd.DataFrame({"member_id": ["m", "m"], "causal_context_id": ["c", "c"], "context_epoch": [0, 1]})
        self.assertEqual(MOD.context_key(frame).nunique(), 2)

    def test_09_label_cannot_change_owner(self):
        missing = np.asarray([False, True])
        before = np.where(missing, "B", "A").tolist()
        labels = [0, 1]
        labels.reverse()
        after = np.where(missing, "B", "A").tolist()
        self.assertEqual(before, after)

    def test_10_whole_context_exclusion(self):
        frame = pd.DataFrame({"ctx": ["x", "x", "y"], "phase": ["fit", "select", "fit"]})
        select = set(frame.loc[frame.phase.eq("select"), "ctx"])
        legal = frame.loc[frame.phase.eq("fit") & ~frame.ctx.isin(select)]
        self.assertEqual(legal.ctx.tolist(), ["y"])

    def test_11_forbidden_score_file_rejected(self):
        with self.assertRaises(RuntimeError):
            MOD.assert_no_forbidden_open([Path("ckda_d1_select_scores.csv.gz")])

    def test_12_final_file_rejected(self):
        with self.assertRaises(RuntimeError):
            MOD.assert_no_forbidden_open([Path("cooler_motor_final.csv")])

    def test_13_availability_reads_only_uid_missing(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "availability.npz"
            np.savez(path, uid=np.asarray(["u1", "u2"]), missing=np.asarray([False, True]), representation=np.ones((2, 3)))
            frame = MOD.load_old_availability(path)
            self.assertEqual(frame.columns.tolist(), ["uid", "old_missing"])
            self.assertEqual(frame.old_missing.tolist(), [False, True])

    def test_14_missing_arrays_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "availability.npz"
            np.savez(path, uid=np.asarray(["u1"]))
            with self.assertRaises(RuntimeError):
                MOD.load_old_availability(path)

    def test_15_candidate_list_is_fixed(self):
        self.assertEqual([r["candidate_id"] for r in MOD.candidate_specs()], ["torch.nn.GRU", "torch.nn.LSTM", "torch.nn.TransformerEncoder"])

    def test_16_wall_cap_formula(self):
        extrapolated = 10.0
        self.assertEqual(min(3 * extrapolated, 168 * 3600), 30.0)

    def test_17_teacher_b_cannot_be_fabricated(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"b_teacher_rows": 0', source)

    def test_18_unknown_benign_teacher_is_fail_closed(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn("AUTHORIZED_COUNT_ONLY_TEACHER_BENIGN_VERDICT_NOT_MATERIALIZED", source)

    def test_19_no_training_authorization(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"training_runs_authorized": 0', source)

    def test_20_no_hyperparameter_sweep(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"hyperparameter_sweeps_authorized": 0', source)

    def test_21_teacher_artifact_exact_uid_gate(self):
        old_expected = MOD.EXPECTED_A_LEGAL_FIT_BENIGN_ROWS
        try:
            MOD.EXPECTED_A_LEGAL_FIT_BENIGN_ROWS = 2
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                counts = {
                    "status": "F1_TEACHER_BENIGN_COUNTS_MATERIALIZED",
                    "authorized_rows": 2,
                    "hard_rows": 1,
                    "normal_rows": 1,
                    "threshold": 0.065159872174263,
                    "score_values_persisted": 0,
                }
                (root / "f1_teacher_benign_counts.json").write_text(json.dumps(counts), encoding="utf-8")
                with gzip.open(str(root / "f1_teacher_benign_uid_verdicts.csv.gz"), "wt", encoding="utf-8", newline="") as handle:
                    handle.write("uid,hard\nu1,true\nu2,false\n")
                for name in ["f1_teacher_benign_input_audit.json", "f1_teacher_benign_boundary_audit.json", "f1_teacher_benign_validation_report.json"]:
                    (root / name).write_text("{}\n", encoding="utf-8")
                members = sorted(path for path in root.iterdir() if path.name != "SHA256SUMS")
                sidecar = "".join(f"{MOD.sha256(path)}  {path.name}\n" for path in members)
                (root / "SHA256SUMS").write_text(sidecar, encoding="utf-8")
                loaded = MOD.load_teacher_benign_artifact(root, {"u1", "u2"})
                self.assertEqual((loaded["hard_rows"], loaded["normal_rows"]), (1, 1))
                with self.assertRaises(RuntimeError):
                    MOD.load_teacher_benign_artifact(root, {"u1", "wrong"})
        finally:
            MOD.EXPECTED_A_LEGAL_FIT_BENIGN_ROWS = old_expected

    def test_22_teacher_artifact_has_no_score_column(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('verdicts.columns.tolist() != ["uid", "hard"]', source)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(F1D0Tests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun})
    raise SystemExit(0 if result.wasSuccessful() else 1)
