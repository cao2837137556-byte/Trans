#!/usr/bin/env python3
"""Synthetic contract tests for Frontend-F2 D0."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np


MODULE = Path(__file__).with_name("issue27frontend_f2_old_function_preservation_d0_v1.py")
SPEC = importlib.util.spec_from_file_location("f2_d0", str(MODULE))
assert SPEC and SPEC.loader
m = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(m)


class ContractTests(unittest.TestCase):
    def test_01_literals(self):
        self.assertEqual((m.EXPECTED_ROWS, m.EXPECTED_ATTACK, m.EXPECTED_BENIGN), (8353, 2182, 6171))
        self.assertEqual((m.EXPECTED_CORRECT_BENIGN, m.EXPECTED_WRONG_BENIGN), (6145, 26))
        self.assertEqual(len(m.VAL_SOURCES), 5)

    def test_02_order_statistic_methods_are_distinct(self):
        values = np.asarray([0.0, 10.0, 20.0, 30.0])
        self.assertEqual(m.quantile(values, 0.4, "lower"), 10.0)
        self.assertEqual(m.quantile(values, 0.4, "higher"), 20.0)

    def test_03_one_sided_envelope_semantics(self):
        c_attack, c_benign = 4.0, -4.0
        z_old_attack, z_old_benign = 9.0, -9.0
        attack_target = min(z_old_attack, c_attack)
        benign_target = max(z_old_benign, c_benign)
        self.assertEqual(attack_target, 4.0)
        self.assertEqual(benign_target, -4.0)
        self.assertEqual(max(0.0, attack_target - 5.0), 0.0)
        self.assertEqual(max(0.0, -5.0 - benign_target), 0.0)

    def test_04_stream_selective_synthetic(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "rows.npz"
            values = np.arange(10 * 4, dtype=np.float32).reshape(10, 4)
            np.savez(path, representation=values)
            old_expected = m.EXPECTED_ROWS
            try:
                m.EXPECTED_ROWS = 3
                result, audit = m.stream_authorized_rows(path, [1, 5, 8], expected_rows=10, expected_dim=4)
            finally:
                m.EXPECTED_ROWS = old_expected
            np.testing.assert_array_equal(result, values[[1, 5, 8]])
            self.assertEqual(audit["nonauthorized_representation_rows_numeric_decoded"], 0)

    def test_05_p2_formula(self):
        state = {
            "normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
            "p2__0.weight": np.zeros((128, 769)), "p2__0.bias": np.ones(128),
            "p2__3.weight": np.ones((1, 128)), "p2__3.bias": np.asarray([0.0]),
        }
        old_expected = m.EXPECTED_ROWS
        try:
            m.EXPECTED_ROWS = 5
            logits, scores = m.canonical_p2_logits_scores(np.zeros((5, 768), dtype=np.float32), state)
        finally:
            m.EXPECTED_ROWS = old_expected
        np.testing.assert_allclose(logits, 128.0)
        np.testing.assert_allclose(scores, 1.0)

    def test_06_canonical_and_wrapper_agree_for_identity_normalizer(self):
        state = {
            "normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
            "p2__0.weight": np.zeros((128, 769)), "p2__0.bias": np.ones(128),
            "p2__3.weight": np.ones((1, 128)), "p2__3.bias": np.asarray([0.0]),
        }
        old_expected = m.EXPECTED_ROWS
        try:
            m.EXPECTED_ROWS = 5
            values = np.zeros((5, 768), dtype=np.float32)
            canonical = m.canonical_p2_logits_scores(values, state)
            wrapper = m.f1_wrapper_p2_logits_scores(values, state)
        finally:
            m.EXPECTED_ROWS = old_expected
        np.testing.assert_array_equal(canonical[0], wrapper[0])
        np.testing.assert_array_equal(canonical[1], wrapper[1])

    def test_07_threshold_identity(self):
        self.assertAlmostEqual(np.log(m.THRESHOLD / (1.0 - m.THRESHOLD)), m.Z0, places=15)
        self.assertGreater(m.Z_P99, m.Z0 + 0.5)
        self.assertLess(m.Z_P01, m.Z0 - 0.25)

    def test_08_vocabulary_is_hash_ordered_and_bijective(self):
        contexts = [{"split": "train", "signatures": ["z", "a", "m"]}]
        vocabulary, identity = m.build_vocabulary(contexts)
        expected = sorted({"z", "a", "m"}, key=lambda value: (m.hashlib.sha256(value.encode()).digest(), value.encode()))
        self.assertEqual([item for item, _ in sorted(vocabulary.items(), key=lambda pair: pair[1])], expected)
        self.assertEqual(len(identity), 64)

    def test_09_nested_split_is_source_indivisible(self):
        contexts = []
        for index in range(10):
            attack = index < 5
            contexts.append({
                "source_group": "source_%02d" % index,
                "targets": [{"label": 1 if attack else 0}, {"label": 0}],
            })
        split = m.nested_source_split(contexts)
        self.assertEqual(len(split), 10)
        self.assertEqual(sum(value == "internal_val" for value in split.values()), 2)
        self.assertEqual(sum(value == "train" for value in split.values()), 8)


if __name__ == "__main__":
    unittest.main(verbosity=2)
