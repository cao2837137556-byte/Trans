#!/usr/bin/env python3
"""Synthetic contract tests for five-row incumbent margin materialization."""

import importlib.util
import math
import tempfile
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("issue27frontend_f1_d1_incumbent_five_margin_v1.py")
SPEC = importlib.util.spec_from_file_location("five_margin", str(MODULE_PATH))
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ContractTests(unittest.TestCase):
    def test_01_frozen_allowlist_is_literal_and_sorted(self):
        self.assertEqual(len(m.FROZEN_UIDS), 5)
        self.assertEqual(tuple(sorted(m.FROZEN_UIDS)), m.FROZEN_UIDS)

    def test_02_contract_hash_is_literal(self):
        self.assertEqual(len(m.CONTRACT_SHA256), 64)
        self.assertEqual(m.EXPECTED_ROWS, 25467)
        self.assertEqual(m.EXPECTED_DIM, 768)

    def test_03_threshold_categories(self):
        t = m.THRESHOLD
        self.assertEqual(m.category(t), "EXACT_OR_ULP")
        self.assertEqual(m.category(float(np.nextafter(t, math.inf))), "EXACT_OR_ULP")
        self.assertEqual(m.category(t + 0.0005), "NEAR_0P1PP")
        self.assertEqual(m.category(t + 0.01), "INTERMEDIATE")
        self.assertEqual(m.category(t + 0.05), "STRONG_5PP")
        self.assertEqual(m.category(t - 0.001), "NOT_HARD")

    def test_04_stream_decodes_only_five_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.npz"
            values = np.arange(12 * 4, dtype=np.float32).reshape(12, 4)
            np.savez(path, representation=values)
            extracted, audit = m.stream_rows(path, [1, 3, 5, 7, 11], expected_rows=12, expected_dim=4)
            np.testing.assert_array_equal(extracted, values[[1, 3, 5, 7, 11]])
            self.assertEqual(audit["representation_rows_numeric_decoded"], 5)
            self.assertEqual(audit["nonallowlisted_representation_rows_numeric_decoded"], 0)

    def test_05_stream_rejects_wrong_allowlist_size(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "synthetic.npz"
            np.savez(path, representation=np.zeros((12, 4), dtype=np.float32))
            with self.assertRaises(RuntimeError):
                m.stream_rows(path, [1, 2, 3, 4], expected_rows=12, expected_dim=4)

    def test_06_p2_formula(self):
        state = {
            "normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
            "p2__0.weight": np.zeros((128, 769)), "p2__0.bias": np.ones(128),
            "p2__3.weight": np.ones((1, 128)), "p2__3.bias": np.asarray([0.0]),
        }
        logits, scores = m.p2_logits_scores(np.zeros((5, 768), dtype=np.float32), state)
        np.testing.assert_allclose(logits, 128.0)
        np.testing.assert_allclose(scores, 1.0)

    def test_07_p2_rejects_bad_normalizer(self):
        state = {
            "normalizer_mean": np.zeros(768), "normalizer_scale": np.zeros(768),
            "p2__0.weight": np.zeros((128, 769)), "p2__0.bias": np.zeros(128),
            "p2__3.weight": np.zeros((1, 128)), "p2__3.bias": np.asarray([0.0]),
        }
        with self.assertRaises(RuntimeError):
            m.p2_logits_scores(np.zeros((5, 768), dtype=np.float32), state)


if __name__ == "__main__":
    unittest.main(verbosity=2)
