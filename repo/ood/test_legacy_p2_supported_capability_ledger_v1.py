"""Synthetic-only tests: no project data or weights are opened."""
import csv
import gzip
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import legacy_p2_supported_capability_ledger_v1 as m


def state_fixture():
    state = {key: np.zeros(shape, dtype=np.float64 if key.startswith("normalizer") else np.float32)
             for key, shape in m.STATE_SHAPES.items()}
    state["normalizer_scale"][:] = 1
    return state


def row(uid="u1", role="future_query", family="test-attack", label=1):
    return dict(uid=uid, role=role, phase="report", source_group="synthetic-source",
                device_family="synthetic-device", attack_family=family, label_metric_only=label)


class FixedLedgerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def score_file(self, rows):
        path = self.root / "synthetic_scores.csv.gz"
        fields = ["candidate_id", "probe_id", "uid", "role", "source_group", "device_family",
                  "attack_family", "label_metric_only", "score", "hard", "missing", "c1_hard", "frozen_ckbq_hard", "m7_hard"]
        with gzip.open(path, "wt", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_only_p2_numeric_fields_are_parsed(self):
        metadata = row()
        forbidden = dict(metadata, candidate_id="E3", probe_id="G0", score="NEVER_PARSE",
                         hard="NEVER_PARSE", missing="NEVER_PARSE", label_metric_only="NEVER_PARSE")
        selected = dict(metadata, candidate_id="E3", probe_id="P2", score=0.5, hard=1, missing=0,
                        c1_hard="NEVER_PARSE", frozen_ckbq_hard="NEVER_PARSE", m7_hard="NEVER_PARSE")
        path = self.score_file([forbidden, dict(forbidden, probe_id="P1"), selected])
        scores, hard, missing, skipped = m.read_p2_archive(path, [metadata])
        np.testing.assert_array_equal(scores, [0.5])
        np.testing.assert_array_equal(hard, [True])
        np.testing.assert_array_equal(missing, [False])
        self.assertEqual(skipped, {"G0": 1, "P1": 1})

    def test_score_metadata_and_uid_mismatch_fail(self):
        metadata = row()
        selected = dict(metadata, candidate_id="E3", probe_id="P2", score=0.5, hard=1, missing=0)
        for changes, message in [({"attack_family": "wrong"}, "SCORE_METADATA_JOIN"),
                                 ({"uid": "not-authorized"}, "SCORE_UNKNOWN_UID"),
                                 ({"label_metric_only": 0}, "SCORE_LABEL_JOIN"),
                                 ({"hard": 0}, "ARCHIVE_THRESHOLD_MISMATCH")]:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(m.Stop, message):
                    m.read_p2_archive(self.score_file([dict(selected, **changes)]), [metadata])

    def test_streaming_reader_skips_forbidden_nonfinite_rows(self):
        values = np.full((6, 768), np.nan, dtype=np.float32)
        values[1], values[4] = 1, 4
        path = self.root / "synthetic_embeddings.npz"
        np.savez_compressed(path, representation=values, forbidden=np.asarray([object()], dtype=object))
        audit = {}
        with mock.patch.object(m.np, "load", side_effect=AssertionError("full np.load forbidden")):
            batches = list(m.selective_batches(path, [1, 4], 6, batch_size=1, audit=audit))
        self.assertEqual([int(x[0][0]) for x in batches], [1, 4])
        self.assertEqual(audit["numeric_representation_rows"], 2)
        self.assertEqual(audit["opaque_representation_bytes"], 6 * 768 * 4)
        self.assertTrue(all(np.isfinite(x[1]).all() for x in batches))
        with self.assertRaisesRegex(m.Stop, "SELECTED_NONFINITE"):
            list(m.selective_batches(path, [0], 6))
        with self.assertRaisesRegex(m.Stop, "ROW_INDICES"):
            list(m.selective_batches(path, [4, 1], 6))

    def test_only_six_state_arrays_opened(self):
        state = state_fixture()
        path = self.root / "synthetic_state.npz"
        np.savez(path, **state, g0_reference=np.asarray([object()], dtype=object),
                 p1_coef=np.asarray([object()], dtype=object))
        actual = m.load_p2_state(path)
        self.assertEqual(set(actual), set(m.STATE_SHAPES))
        with self.assertRaisesRegex(m.Stop, "FULL_REPRESENTATION_READ_FORBIDDEN"):
            m.read_npz_arrays(path, ["representation"])

    def test_canonical_float64_normalization_then_float32_head(self):
        import torch
        state = state_fixture()
        state["normalizer_mean"][0] = 100000000.0 - 1.0
        state["p2__0.weight"][0, 0] = 1
        state["p2__3.weight"][0, 0] = 1
        # Any mistaken missing=1 would add a very large contribution.
        state["p2__0.weight"][1, -1] = 50
        state["p2__3.weight"][0, 1] = 50
        x = np.zeros((2, 768), dtype=np.float32)
        x[:, 0] = 100000000.0
        logits, probability = m.canonical_p2(x, state)
        np.testing.assert_array_equal(logits, [1.0, 1.0])
        expected = torch.sigmoid(torch.ones(2, dtype=torch.float32)).numpy().astype(np.float64)
        np.testing.assert_array_equal(probability, expected)
        self.assertEqual(probability.dtype, np.float64)
        # Early float32 normalization loses the distinguishing unit.
        self.assertEqual(float((x[0, 0] - np.float32(state["normalizer_mean"][0]))), 0.0)

    def test_npz_metadata_identity_and_join(self):
        plan = [row(), row(uid="u2")]
        path = self.root / "synthetic_metadata.npz"
        np.savez(path, uid=np.asarray(["u2", "u1"]), missing=np.asarray([True, False]),
                 candidate_id=np.asarray(["E3"]), plan_sha256=np.asarray(["plan-pin"]),
                 contract_sha256=np.asarray([m.CONTRACT]), representation=np.full((2, 768), np.nan, dtype=np.float32))
        mapping, missing = m.embedding_metadata(path, plan, "plan-pin")
        self.assertEqual(mapping, {"u2": 0, "u1": 1})
        self.assertTrue(missing[mapping["u2"]])
        with self.assertRaisesRegex(m.Stop, "EMBEDDING_PLAN_IDENTITY"):
            m.embedding_metadata(path, plan, "wrong-plan")
        with self.assertRaisesRegex(m.Stop, "EMBEDDING_UID_JOIN"):
            m.embedding_metadata(path, [row(), row(uid="not-authorized")], "plan-pin")

    def test_low_fpr_uses_worst_pool_integer_bounds_and_indivisible_ties(self):
        # Pool a permits one FP at 1%; pool b permits none. Pooling them would
        # wrongly allow the high-scoring b row (1/151 <=1%, but 1/50 >1%).
        scores = np.asarray([0.95, 0.9, 0.9] + [0.0] * 101 + [0.9] + [0.0] * 49)
        labels = np.asarray([True] * 3 + [False] * 151)
        pools = np.asarray([""] * 3 + ["a"] * 101 + ["b"] * 50)
        result = m.low_fpr_points(scores, labels, pools, labels, labels)
        for alpha in ("0.01", "0.001"):
            point = result["points"][alpha]
            self.assertEqual(point["attack"]["attack"]["detected"], 1)
            self.assertEqual(point["normal_pools"]["b"]["false_positives"], 0)
            self.assertEqual(point["diagnostic_threshold"], 0.95)
        self.assertFalse(result["deployment_threshold_selected"])

    def test_probability_saturation_and_raw_logit_both_retained(self):
        labels = np.asarray([True] + [False] * 100)
        pools = np.asarray([""] + ["normal"] * 100)
        probabilities = np.asarray([1.0, 1.0] + [0.0] * 99)
        logits = np.asarray([30.0, 20.0] + [-20.0] * 99)
        prob = m.low_fpr_points(probabilities, labels, pools, labels, labels)
        raw = m.low_fpr_points(logits, labels, pools, labels, labels)
        self.assertEqual(prob["points"]["0.001"]["threshold_kind"], "NO_HARD")
        self.assertEqual(prob["points"]["0.001"]["attack"]["attack"]["detected"], 0)
        self.assertEqual(raw["points"]["0.001"]["attack"]["attack"]["detected"], 1)

    def test_coverage_retains_missing_and_exposure_uses_original_fit(self):
        metrics = m.ledger_metric(np.asarray([True, False, True]), np.asarray([False, False, True]), np.ones(3, dtype=bool))
        self.assertEqual((metrics["all_rows"], metrics["valid_rows"], metrics["missing_rows"]), (3, 2, 1))
        self.assertEqual(metrics["hard_valid"], 1)
        self.assertEqual(metrics["archived_hard_missing"], 1)
        original = [dict(row(family="old-family"), phase="fit"), dict(row(uid="u2", family="threshold-only"), phase="select")]
        trained, calibrated = m.exposure_sets(original)
        self.assertEqual(trained, {"old-family": 1})
        self.assertEqual(calibrated, {"threshold-only": 1})


if __name__ == "__main__":
    unittest.main()
