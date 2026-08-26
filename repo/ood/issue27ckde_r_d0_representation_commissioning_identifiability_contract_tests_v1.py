#!/usr/bin/env python3
"""Contract tests for CKDE-R D0 (Python 3.9 grammar)."""

from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE_PATH = HERE / "issue27ckde_r_d0_representation_commissioning_identifiability_v1.py"
SPEC = importlib.util.spec_from_file_location("ckde_r", str(MODULE_PATH))
assert SPEC and SPEC.loader
r = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(r)


def synthetic_graph(pass_cycle: bool = True):
    rows = []
    meta = []
    devices = ["d1", "d2"]
    families = ["f1", "f2"] if pass_cycle else ["f1"]
    for device in devices:
        for index in range(64):
            uid = "%s-b-%d" % (device, index)
            rows.append({"uid": uid, "role": "aux_fit", "source_group": device, "attack_family": "benign", "recorded_index": index, "label_metric_only": 0})
            meta.append({"uid": uid, "session_id": "%s-bs-%d" % (device, index), "timestamp_epoch": index, "event_position": index})
        position = 1000
        for family in families:
            for index in range(15):
                uid = "%s-%s-a-%d" % (device, family, index)
                rows.append({"uid": uid, "role": "support_train", "source_group": device, "attack_family": family, "recorded_index": position, "label_metric_only": 1})
                meta.append({"uid": uid, "session_id": "%s-%s-as-%d" % (device, family, index), "timestamp_epoch": position, "event_position": position})
                position += 1
    joined = pd.DataFrame(rows).merge(pd.DataFrame(meta), on="uid", validate="one_to_one")
    census = pd.DataFrame([
        {"device_key": device, "lineage_stable": True, "causal_prefix_and_suffix_identifiable": True}
        for device in devices
    ])
    return joined, census


def fake_state():
    return {
        "normalizer_mean": np.zeros(768),
        "normalizer_scale": np.ones(768),
        "p2__0.weight": np.zeros((128, 769)),
        "p2__0.bias": np.ones(128),
        "p2__3.weight": np.ones((1, 128)),
        "p2__3.bias": np.zeros(1),
    }


class CKDERD0Tests(unittest.TestCase):
    def test_01_python39_program(self):
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_python39_tests(self):
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_03_contract_hash(self):
        self.assertEqual(r.sha256_file(ROOT / r.CONTRACT_REL), r.CONTRACT_SHA256)

    def test_04_all_input_hashes(self):
        self.assertEqual(set(r.pin_inputs(ROOT)), {"contract"} | set(r.PINS))

    def test_05_two_by_two_cycle_passes(self):
        incidence, graph, _ = r.audit0(*synthetic_graph(True))
        self.assertEqual(graph["status"], "PASS")
        self.assertEqual(len(incidence), 4)
        self.assertEqual(graph["two_by_two_cycles"], 1)

    def test_06_no_cycle_fails(self):
        _, graph, _ = r.audit0(*synthetic_graph(False))
        self.assertEqual(graph["status"], "FAIL")
        self.assertIn("NO_TWO_BY_TWO_DEVICE_FAMILY_CYCLE", graph["reason_codes"])

    def test_07_missing_center_fails(self):
        joined, census = synthetic_graph(True)
        suffixes = tuple(str(x) for x in range(4, 10))
        joined = joined.loc[
            ~(
                (joined["role"] == "aux_fit")
                & joined["session_id"].str.endswith(suffixes)
            )
        ]
        _, graph, _ = r.audit0(joined, census)
        self.assertIn("NO_SAME_DEVICE_FIT_BENIGN_CENTER", graph["reason_codes"])

    def test_08_unmapped_attack_device_fails(self):
        joined, census = synthetic_graph(True)
        census = census.iloc[:1]
        _, graph, _ = r.audit0(joined, census)
        self.assertIn("ATTACK_DEVICE_UNMAPPED", graph["reason_codes"])

    def test_09_session_equal_weighting(self):
        rows = pd.DataFrame([
            {"source_group": "d", "session_id": "a", "event_position": 1},
            {"source_group": "d", "session_id": "a", "event_position": 2},
            {"source_group": "d", "session_id": "b", "event_position": 3},
        ])
        table = r.session_table(rows)
        self.assertEqual(len(table), 2)
        self.assertEqual(int(table.loc[table["session_id"] == "a", "records"].iloc[0]), 2)

    def test_10_higher_percentile(self):
        values = list(range(1000))
        self.assertEqual(r.higher_percentile(values), 949.0)

    def test_11_seed_is_deterministic(self):
        self.assertEqual(r.seed64("x"), r.seed64("x"))
        self.assertNotEqual(r.seed64("x"), r.seed64("y"))

    def test_12_robust_reference_floor(self):
        center, scale = r.robust_reference(np.zeros((3, 768)))
        self.assertTrue(np.all(center == 0))
        self.assertTrue(np.all(scale == 1e-6))

    def test_13_shrinkage_literals(self):
        values = np.ones((64, 768))
        center, log_scale = r.device_estimate(values, np.zeros(768), np.ones(768))
        self.assertTrue(np.allclose(center, 0.5))
        self.assertEqual(center.shape, log_scale.shape)

    def test_14_bootstrap_deterministic(self):
        old = r.BOOTSTRAPS
        r.BOOTSTRAPS = 10
        try:
            values = np.arange(64 * 768, dtype=float).reshape(64, 768) / 1000.0
            one = r.bootstrap_stability("d", values, np.zeros(768), np.ones(768))
            two = r.bootstrap_stability("d", values, np.zeros(768), np.ones(768))
            self.assertEqual(one, two)
        finally:
            r.BOOTSTRAPS = old

    def test_15_stability_diagonal(self):
        frame = pd.DataFrame([{"q95_center": 0.01, "q95_scale": 0.01}] * 5)
        candidate, summary = r.choose_stability(frame)
        self.assertEqual(candidate, "DIAGONAL_AFFINE")
        self.assertTrue(summary["scale_pass"])

    def test_16_worst_device_guard(self):
        frame = pd.DataFrame([{"q95_center": 0.01, "q95_scale": 0.01}] * 4 + [{"q95_center": 0.36, "q95_scale": 0.01}])
        candidate, _ = r.choose_stability(frame)
        self.assertEqual(candidate, "NONE")

    def test_17_cosine_projection(self):
        cosine, projection = r.cosine_projection(np.ones(768), np.ones(768))
        self.assertAlmostEqual(cosine, 1.0)
        self.assertAlmostEqual(projection, 1.0)

    def test_18_zero_norm_fails(self):
        with self.assertRaisesRegex(RuntimeError, "zero-norm"):
            r.cosine_projection(np.zeros(768), np.ones(768))

    def test_19_p2_width_and_missing(self):
        reps = np.vstack((np.ones(768), np.full(768, 100.0)))
        scores = r.frozen_p2_scores(reps, np.asarray([False, True]), fake_state())
        self.assertEqual(scores.shape, (2,))
        self.assertEqual(scores[0], scores[1])

    def test_20_p2_132d_rejected(self):
        with self.assertRaises(ValueError):
            r.frozen_p2_scores(np.ones((1, 132)), np.asarray([False]), fake_state())

    def test_21_state_a_output_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            graph = {"status": "FAIL"}
            audit = {
                "embedding_arrays_opened": 0, "probe_state_arrays_opened": 0,
                "support_val_rows_opened": 0, "report_files_opened": 0,
                "final_files_opened": 0, "pcap_files_opened": 0, "training_runs": 0,
            }
            self.assertEqual(r.validation_for_state_a(out, graph, audit)["status"], "PASS")

    def test_22_live_audit0_stops_before_embedding(self):
        joined, _, census = r.load_metadata_only(ROOT)
        _, graph, _ = r.audit0(joined, census)
        self.assertEqual(graph["status"], "FAIL")

    def test_23_forbidden_roles_excluded_from_audit0(self):
        joined, census = synthetic_graph(True)
        extra = joined.iloc[[0]].copy()
        extra["uid"] = "forbidden"
        extra["role"] = "support_val"
        joined = pd.concat([joined, extra], ignore_index=True)
        _, graph, audit = r.audit0(joined, census)
        self.assertEqual(graph["status"], "PASS")
        self.assertEqual(audit["attack_records"], 60)

    def test_24_state_a_embedding_outputs_are_named(self):
        self.assertIn("ckde_r_d0_entanglement_pairs.csv", r.EMBEDDING_OUTPUTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
