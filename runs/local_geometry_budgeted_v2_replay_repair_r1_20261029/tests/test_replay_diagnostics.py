"""Small synthetic arrays only; no model, historical data or remote execution."""
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import numpy as np

from lg.common import array_sha, require, sha, write_json
from lg.source import _record_raw_replay


class RecordingRuntime:
    def __init__(self, output):
        self.output, self.checkpoints = output, []

    def checkpoint(self, *args, **fields):
        self.checkpoints.append((args, fields))

    def write_json(self, name, value):
        write_json(self.output / name, value)
        self.checkpoint()


class ReplayDiagnosticsTests(unittest.TestCase):
    def record(self, directory, expected, reproduced, cut=.5):
        output = Path(directory)
        runtime = RecordingRuntime(output)
        indices = np.array([2, 0, 3][:len(expected)], dtype=np.int64)
        rows = [{"uid": "uid" + str(i)} for i in range(4)]
        summary = _record_raw_replay(output, runtime, SimpleNamespace(),
            fold="G0", seed=27, role="CAL", expected=expected, reproduced=reproduced,
            indices=indices, rows=rows, cut=cut)
        saved = json.loads((output / "RAW_REPLAY/G0/27/CAL/SUMMARY.json").read_text(encoding="utf-8"))
        self.assertEqual(saved, summary)
        self.assertGreaterEqual(len(runtime.checkpoints), 3)
        return summary

    def test_exact_replay_saves_only_json_and_does_not_mutate_scores(self):
        expected = np.array([.25, .5, 1.], dtype=np.float32)
        reproduced = expected.copy()
        before = expected.tobytes(), reproduced.tobytes()
        with tempfile.TemporaryDirectory() as directory:
            summary = self.record(directory, expected, reproduced)
            self.assertTrue(summary["strict_gate_pass"])
            self.assertTrue(summary["values_equal"])
            self.assertTrue(summary["bytes_equal"])
            self.assertEqual(summary["byte_mismatch_count"], 0)
            self.assertEqual(summary["value_mismatch_count"], 0)
            self.assertEqual(summary["decision_mismatch_count"], 0)
            self.assertEqual(summary["expected"]["bytes_sha256"], array_sha(expected))
            self.assertEqual(summary["expected"]["dtype"], "float32")
            self.assertEqual(summary["expected"]["shape"], [3])
            self.assertIn("python", summary["environment"])
            self.assertIn("numpy", summary["environment"])
            self.assertIn("platform", summary["environment"])
            self.assertEqual(list(Path(directory).rglob("*.npz")), [])
            self.assertEqual(before, (expected.tobytes(), reproduced.tobytes()))

    def test_signed_zero_is_numeric_equal_but_strict_failure_keeps_all_scores(self):
        expected = np.array([0., 1., 2.], dtype=np.float32)
        reproduced = np.array([-0., 1., 2.], dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            summary = self.record(directory, expected, reproduced)
            self.assertTrue(summary["values_equal"])
            self.assertFalse(summary["bytes_equal"])
            self.assertFalse(summary["strict_gate_pass"])
            self.assertEqual(summary["value_mismatch_count"], 0)
            self.assertEqual(summary["element_bytes_mismatch_count"], 1)
            self.assertEqual(summary["byte_mismatch_count"], 1)
            self.assertEqual(summary["max_absolute_difference"], 0.)
            self.assertEqual(summary["decision_mismatch_count"], 0)
            mismatch = summary["first_mismatches"][0]
            self.assertEqual((mismatch["role_index"], mismatch["source_index"], mismatch["uid"]), (0, 2, "uid2"))
            self.assertNotEqual(mismatch["expected_bytes_hex"], mismatch["reproduced_bytes_hex"])
            path = Path(directory) / summary["failure_scores"]["path"]
            self.assertEqual(sha(path), summary["failure_scores"]["sha256"])
            with np.load(path, allow_pickle=False) as saved:
                self.assertEqual(saved["expected"].tobytes(), expected.tobytes())
                self.assertEqual(saved["reproduced"].tobytes(), reproduced.tobytes())
                np.testing.assert_array_equal(saved["uid"], ["uid2", "uid0", "uid3"])
                np.testing.assert_array_equal(saved["source_index"], [2, 0, 3])
            # The original strict assertion still rejects a harmless sign-bit change.
            with self.assertRaisesRegex(ValueError, "SOURCE_RAW_REPLAY_MISMATCH"):
                require(reproduced.dtype == expected.dtype and reproduced.shape == expected.shape
                        and reproduced.tobytes() == expected.tobytes(), "SOURCE_RAW_REPLAY_MISMATCH:G027CAL")

    def test_numeric_changes_report_both_threshold_flip_directions_and_ties(self):
        expected = np.array([1., 0., .5], dtype=np.float32)
        reproduced = np.array([.5, .75, .5], dtype=np.float32)
        with tempfile.TemporaryDirectory() as directory:
            summary = self.record(directory, expected, reproduced)
            self.assertEqual(summary["value_mismatch_count"], 2)
            self.assertEqual(summary["max_absolute_difference"], .75)
            self.assertEqual(summary["decision_mismatch_count"], 2)
            self.assertEqual(summary["expected_positive_to_reproduced_negative"], 1)
            self.assertEqual(summary["expected_negative_to_reproduced_positive"], 1)
            self.assertEqual([row["uid"] for row in summary["first_mismatches"]], ["uid2", "uid0"])
            self.assertFalse(summary["strict_gate_pass"])

    def test_dtype_and_shape_failures_are_distinguished_without_broadcasting(self):
        expected = np.array([0., 1., 2.], dtype=np.float32)
        for reproduced, field in ((expected.astype(np.float64), "dtype_equal"),
                                  (expected.reshape(3, 1), "shape_equal")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                summary = self.record(directory, expected, reproduced)
                self.assertFalse(summary[field])
                self.assertFalse(summary["strict_gate_pass"])
                self.assertIsNotNone(summary["failure_scores"])
                if field == "dtype_equal":
                    self.assertTrue(summary["values_equal"])
                    self.assertEqual(summary["value_mismatch_count"], 0)
                else:
                    self.assertTrue(summary["bytes_equal"])
                    self.assertIsNone(summary["value_mismatch_count"])
                    self.assertIsNone(summary["decision_mismatch_count"])
                    self.assertIn("row_comparison_unavailable", summary)


if __name__ == "__main__":
    unittest.main()
