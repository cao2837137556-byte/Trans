#!/usr/bin/env python3
"""Contract tests for CKDE-Q D1 Stage A (Python 3.9 grammar)."""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE_PATH = HERE / "issue27ckde_d1_stage_a_calibration_materialization_v1.py"
SPEC = importlib.util.spec_from_file_location("ckde_q_stage_a", str(MODULE_PATH))
assert SPEC and SPEC.loader
q = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(q)


def fake_state():
    return {
        "normalizer_mean": np.zeros(q.WIDTH),
        "normalizer_scale": np.ones(q.WIDTH),
        "p2__0.weight": np.zeros((128, q.WIDTH + 1)),
        "p2__0.bias": np.zeros(128),
        "p2__3.weight": np.zeros((1, 128)),
        "p2__3.bias": np.zeros(1),
    }


def synthetic_prefix(session_count: int = 256):
    row_records = []
    session_records = []
    scores = {}
    for index in range(session_count):
        uid = "u-%04d" % index
        session = "s-%04d" % index
        row_records.append(
            {
                "uid": uid,
                "source_group": "device-a",
                "session_id": session,
                "event_position": index,
            }
        )
        session_records.append(
            {
                "source_group": "device-a",
                "session_id": session,
                "first_event": index,
                "last_event": index,
                "records": 1,
            }
        )
        scores[uid] = 0.20 + index / 100000.0
    return pd.DataFrame(row_records), pd.DataFrame(session_records), scores


class CKDEQStageATests(unittest.TestCase):
    def test_01_python39_program(self):
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_python39_tests(self):
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_03_contract_hash(self):
        self.assertEqual(q.sha256_file(ROOT / q.CONTRACT_REL), q.CONTRACT_SHA256)

    def test_04_all_input_hashes(self):
        self.assertEqual(set(q.pin_inputs(ROOT)), {"contract"} | set(q.PINS))

    def test_05_cap_literals(self):
        self.assertEqual(q.T_CAP - q.THETA_0, q.CAP)
        self.assertGreater(q.CAP, 0.0)

    def test_06_quantile_uses_higher_order_statistic(self):
        values = np.arange(64, dtype=float)
        observed = q.quantile_threshold(values)
        rank = min(64, int(np.ceil(65 * 0.95)))
        self.assertEqual(observed, np.nextafter(values[rank - 1], np.inf))

    def test_07_quantile_rejects_empty(self):
        with self.assertRaises(RuntimeError):
            q.quantile_threshold([])

    def test_08_quantile_rejects_nonfinite(self):
        with self.assertRaises(RuntimeError):
            q.quantile_threshold([0.1, np.nan])

    def test_09_cap_accepts_literal_band(self):
        threshold, requested, accepted, status = q.apply_cap(q.THETA_0 + q.CAP / 2.0)
        self.assertEqual(status, "CALIBRATED")
        self.assertEqual(threshold, q.THETA_0 + q.CAP / 2.0)
        self.assertEqual(requested, accepted)

    def test_10_cap_exceedance_is_exact_zero_shot(self):
        threshold, requested, accepted, status = q.apply_cap(q.T_CAP + q.CAP)
        self.assertEqual(status, "CAP_EXCEEDED_ZERO_SHOT")
        self.assertEqual(threshold, q.THETA_0)
        self.assertGreater(requested, q.CAP)
        self.assertEqual(accepted, 0.0)

    def test_11_no_downward_threshold(self):
        threshold, requested, accepted, status = q.apply_cap(q.THETA_0 - 0.01)
        self.assertEqual(status, "NO_UPWARD_MOVEMENT_ZERO_SHOT")
        self.assertEqual((threshold, requested, accepted), (q.THETA_0, 0.0, 0.0))

    def test_12_whole_session_record_budget(self):
        sessions = pd.DataFrame(
            [
                {"session_id": "a", "records": 60},
                {"session_id": "b", "records": 50},
                {"session_id": "c", "records": 1},
            ]
        )
        chosen = q.whole_session_record_budget(sessions, 100)
        self.assertEqual(chosen["session_id"].tolist(), ["a"])

    def test_13_p2_score_shape(self):
        scores = q.frozen_p2_scores(
            np.zeros((3, q.WIDTH)), np.asarray([False, True, False]), fake_state()
        )
        self.assertEqual(scores.shape, (3,))
        self.assertTrue(np.allclose(scores, 0.5))

    def test_14_p2_rejects_wrong_width(self):
        with self.assertRaises(ValueError):
            q.frozen_p2_scores(np.zeros((2, 132)), np.zeros(2, dtype=bool), fake_state())

    def test_15_manifest_has_seven_arms(self):
        prefix_rows, prefix_sessions, scores = synthetic_prefix()
        manifest = q.build_thresholds(prefix_rows, prefix_sessions, scores, ["device-a"])
        self.assertEqual(len(manifest), 7)
        self.assertEqual(
            manifest["arm"].tolist(),
            ["Z", "Q-S64", "Q-S128", "Q-S256", "Q-R100", "Q-R500", "Q-R1000"],
        )

    def test_16_manifest_thresholds_are_one_sided(self):
        prefix_rows, prefix_sessions, scores = synthetic_prefix()
        manifest = q.build_thresholds(prefix_rows, prefix_sessions, scores, ["device-a"])
        self.assertTrue(manifest["threshold"].ge(q.THETA_0).all())
        self.assertTrue(manifest["threshold"].le(q.T_CAP).all())
        self.assertEqual(
            manifest.loc[manifest["arm"].ne("Z"), "status"].unique().tolist(),
            ["CAP_EXCEEDED_ZERO_SHOT"],
        )

    def test_17_insufficient_session_budget_falls_back(self):
        prefix_rows, prefix_sessions, scores = synthetic_prefix(64)
        manifest = q.build_thresholds(prefix_rows, prefix_sessions, scores, ["device-a"])
        row = manifest.loc[manifest["arm"].eq("Q-S128")].iloc[0]
        self.assertEqual(row["status"], "INSUFFICIENT_SESSION_BUDGET_ZERO_SHOT")
        self.assertEqual(float(row["threshold"]), q.THETA_0)

    def test_18_live_prefix_denominators(self):
        prefix_rows, prefix_sessions, devices = q.load_prefix_sessions(ROOT)
        self.assertEqual(len(devices), 23)
        counts = prefix_sessions.groupby("source_group")["session_id"].nunique()
        self.assertEqual(int(counts.ge(64).sum()), 23)
        self.assertEqual(int(counts.ge(128).sum()), 20)
        self.assertEqual(int(counts.ge(256).sum()), 11)
        self.assertGreater(len(prefix_rows), 0)

    def test_19_common_11_is_exact(self):
        self.assertEqual(len(q.COMMON_11), 11)
        self.assertEqual(len(set(q.COMMON_11)), 11)

    def test_20_stage_a_has_no_later_stage_authorization(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('"stage_b_authorized": False', source)
        self.assertIn('"final_files_opened": 0', source)
        self.assertIn('"report_score_rows_opened": 0', source)
        self.assertNotIn("benign_suffix_scores", source)

    def test_21_sha_manifest_excludes_itself(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "a.txt").write_text("a", encoding="utf-8")
            q.write_sha256s(root)
            text = (root / "SHA256SUMS").read_text(encoding="utf-8")
            self.assertIn("a.txt", text)
            self.assertNotIn("SHA256SUMS  SHA256SUMS", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
