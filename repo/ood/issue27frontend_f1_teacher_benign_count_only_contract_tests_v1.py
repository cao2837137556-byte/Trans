#!/usr/bin/env python3
"""Contract tests for Frontend-F1 teacher-benign count-only materialization."""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
TARGET = HERE / "issue27frontend_f1_teacher_benign_count_only_v1.py"
SPEC = importlib.util.spec_from_file_location("f1teacher", TARGET)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


class TeacherBenignTests(unittest.TestCase):
    def test_01_python39_ast(self):
        ast.parse(TARGET.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_contract_sha_literal(self):
        self.assertEqual(len(MOD.CONTRACT_SHA256), 64)

    def test_03_expected_denominator(self):
        self.assertEqual(MOD.EXPECTED_AUTHORIZED_ROWS, 7347)

    def test_04_threshold_literal(self):
        self.assertEqual(MOD.THETA_0, 0.065159872174263)

    def test_05_exact_tie_is_hard(self):
        scores = np.asarray([MOD.THETA_0, np.nextafter(MOD.THETA_0, 0.0)])
        self.assertEqual((scores >= MOD.THETA_0).tolist(), [True, False])

    def test_06_streaming_extracts_only_selected_rows(self):
        old_rows, old_dim, old_authorized = (
            MOD.EXPECTED_CONTAINER_ROWS,
            MOD.EXPECTED_DIM,
            MOD.EXPECTED_AUTHORIZED_ROWS,
        )
        try:
            MOD.EXPECTED_CONTAINER_ROWS = 4
            MOD.EXPECTED_DIM = 3
            MOD.EXPECTED_AUTHORIZED_ROWS = 2
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "x.npz"
                values = np.arange(12, dtype=np.float32).reshape(4, 3)
                np.savez_compressed(path, representation=values)
                selected, audit = MOD.stream_selected_representation_rows(path, [1, 3])
                np.testing.assert_array_equal(selected, values[[1, 3]])
                self.assertEqual(audit["representation_rows_numeric_decoded"], 2)
                self.assertEqual(audit["nonallowlisted_representation_rows_numeric_decoded"], 0)
        finally:
            MOD.EXPECTED_CONTAINER_ROWS = old_rows
            MOD.EXPECTED_DIM = old_dim
            MOD.EXPECTED_AUTHORIZED_ROWS = old_authorized

    def test_07_duplicate_indices_rejected(self):
        old_rows, old_dim, old_authorized = (
            MOD.EXPECTED_CONTAINER_ROWS,
            MOD.EXPECTED_DIM,
            MOD.EXPECTED_AUTHORIZED_ROWS,
        )
        try:
            MOD.EXPECTED_CONTAINER_ROWS = 2
            MOD.EXPECTED_DIM = 2
            MOD.EXPECTED_AUTHORIZED_ROWS = 2
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "x.npz"
                np.savez_compressed(path, representation=np.ones((2, 2), dtype=np.float32))
                with self.assertRaises(RuntimeError):
                    MOD.stream_selected_representation_rows(path, [0, 0])
        finally:
            MOD.EXPECTED_CONTAINER_ROWS = old_rows
            MOD.EXPECTED_DIM = old_dim
            MOD.EXPECTED_AUTHORIZED_ROWS = old_authorized

    def test_08_no_score_persistence(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"score_values_persisted": 0', source)

    def test_09_select_scores_zero(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"select_scores_computed": 0', source)

    def test_10_no_training(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"training_started": 0', source)

    def test_11_no_optimizer(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('"optimizer_steps": 0', source)

    def test_12_uid_output_has_no_score_column(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn('["uid", "hard"]', source)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TeacherBenignTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun})
    raise SystemExit(0 if result.wasSuccessful() else 1)
