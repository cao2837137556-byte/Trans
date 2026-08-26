#!/usr/bin/env python3
"""Synthetic contract tests for CKDE-S D0 Lane G."""

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
TARGET = HERE / "issue27ckde_s_d0_lane_g_geometry_audit_v1.py"
SPEC = importlib.util.spec_from_file_location("lane_g", TARGET)
lane_g = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(lane_g)


def metadata(devices: int, sessions: int) -> pd.DataFrame:
    rows = []
    for device in range(devices):
        for session in range(sessions):
            for event in (1, 2):
                rows.append({
                    "uid": "d%d:s%d:%d" % (device, session, event),
                    "role": "aux_fit", "source_group": "d%d" % device,
                    "attack_family": "benign", "label_metric_only": 0,
                    "recorded_index": event, "session_id": "s%d" % session,
                    "timestamp_epoch": float(event), "event_position": event,
                })
    return pd.DataFrame(rows)


class LaneGContractTests(unittest.TestCase):
    def test_01_literal_identity_and_numeric_conventions(self):
        self.assertEqual(lane_g.CONTRACT_SHA256, "e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6")
        self.assertEqual(lane_g.ERRATUM_SHA256, "156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d")
        self.assertEqual(lane_g.SVD_RELATIVE_TOLERANCE, 1e-10)
        self.assertEqual(lane_g.ORTHOGONALITY_TOLERANCE, 1e-10)
        self.assertEqual(lane_g.GRADIENT_NORM_FLOOR, 1e-12)
        self.assertEqual(lane_g.WIDTH, 768)
        expected = {
            "embeddings": "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099",
            "metadata": "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd",
            "plan": "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac",
            "probe_state": "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38",
        }
        self.assertEqual({name: value[1] for name, value in lane_g.PINS.items()}, expected)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "x"
            path.write_bytes(b"drift")
            with self.assertRaises(RuntimeError):
                lane_g.require_sha(path, "0" * 64)

    def test_02_count_gate_precedes_npz_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            rows = metadata(8, 64)
            with mock.patch.object(lane_g, "pin_inputs", return_value={}), mock.patch.object(
                lane_g, "load_metadata_only", return_value=rows
            ), mock.patch.object(lane_g, "load_arrays", side_effect=AssertionError("NPZ opened")):
                verdict = lane_g.materialize(root, out)
            self.assertEqual(verdict["scientific_state"], "G0")
            role = json.loads((out / "ckde_s_d0_role_open_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(role["embedding_arrays_opened"], 0)
            self.assertEqual(role["probe_state_arrays_opened"], 0)

    def test_03_rank_formula_is_exact_and_no_retry(self):
        _, result = lane_g.count_rank_gate(metadata(15, 64))
        self.assertEqual(result["rank"], 4)
        self.assertFalse(result["rank_retry_permitted"])
        source = TARGET.read_text(encoding="utf-8")
        self.assertNotIn("rank - 1", source)
        self.assertNotIn("rank -=", source)

    def test_04_complete_session_uses_terminal_target(self):
        rows = metadata(1, 3)
        terminal = lane_g.terminal_session_rows(rows)
        self.assertEqual(len(terminal), 3)
        self.assertEqual(set(terminal["event_position"]), {2})

    def test_05_svd_relative_boundary_is_strict(self):
        self.assertEqual(lane_g.retained_rank([1.0, 1e-10, 1.0000001e-10]), 2)

    def test_06_svd_zero_and_nonfinite_fail_closed(self):
        for values in ([0.0, 0.0], [1.0, float("nan")], [float("inf")]):
            with self.assertRaises(RuntimeError):
                lane_g.retained_rank(values)

    def test_07_basis_rejects_requested_rank_above_retained(self):
        matrix = np.diag([1.0, 1e-12])
        with self.assertRaises(RuntimeError):
            lane_g.basis_from_rows(matrix, 2)

    def test_08_orthogonality_boundary_is_inclusive(self):
        self.assertTrue(lane_g.orthogonality_pass(1e-10))
        self.assertFalse(lane_g.orthogonality_pass(np.nextafter(1e-10, np.inf)))

    def test_09_principal_angle_clip_is_finite(self):
        basis = np.eye(4)[:, :2]
        self.assertAlmostEqual(lane_g.principal_angle_degrees(basis, basis), 0.0)

    def test_10_lodo_identical_plane_passes(self):
        centers = {}
        for index in range(9):
            centers[str(index)] = np.asarray([float(index), float(index % 3), 0.0, 0.0])
        global_center = np.median(np.stack(list(centers.values())), axis=0)
        _, frame, summary = lane_g.lodo_stability(centers, global_center, 2)
        self.assertEqual(len(frame), 9)
        self.assertTrue(summary["pass"])

    def test_11_between_within_stable_shift_passes(self):
        records = []
        vectors = []
        for device in range(9):
            for session in range(64):
                records.append({"source_group": str(device), "session_id": str(session), "timestamp_epoch": float(session), "event_position": session, "uid": "%d:%d" % (device, session), "embedding_index": len(vectors)})
                vectors.append([float(device), 0.001 * session])
        frame, summary = lane_g.between_within(pd.DataFrame(records), np.asarray(vectors), np.eye(2)[:, :1], np.asarray([4.0, 0.0]))
        self.assertEqual(len(frame), 9)
        self.assertTrue(summary["pass"])

    def test_11b_between_within_uses_causal_timestamp_not_session_length(self):
        records = [
            {"source_group": "device", "session_id": "s1", "timestamp_epoch": 1.0, "event_position": 1, "uid": "u1", "embedding_index": 0},
            {"source_group": "device", "session_id": "s2", "timestamp_epoch": 2.0, "event_position": 4, "uid": "u2", "embedding_index": 1},
            {"source_group": "device", "session_id": "s3", "timestamp_epoch": 3.0, "event_position": 2, "uid": "u3", "embedding_index": 2},
            {"source_group": "device", "session_id": "s4", "timestamp_epoch": 4.0, "event_position": 3, "uid": "u4", "embedding_index": 3},
        ]
        vectors = np.asarray([[0.0], [0.0], [10.0], [10.0]])
        frame, _ = lane_g.between_within(
            pd.DataFrame(records), vectors, np.eye(1), np.zeros(1)
        )
        self.assertAlmostEqual(float(frame.iloc[0]["within_early_late_norm"]), 10.0)

    def _state(self):
        state = {
            "normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
            "p2__0.weight": np.zeros((128, 769)), "p2__0.bias": np.full(128, -1.0),
            "p2__3.weight": np.zeros((1, 128)), "p2__3.bias": np.zeros(1),
        }
        state["p2__0.weight"][0, 0] = 2.0
        state["p2__0.bias"][0] = 1.0
        state["p2__3.weight"][0, 0] = 3.0
        return state

    def test_12_p2_gradient_matches_finite_difference(self):
        state = self._state()
        z = np.ones((1, 768))
        gradient = lane_g.p2_gradients(z, np.asarray([False]), state)[0]
        self.assertAlmostEqual(gradient[0], 1.0)
        self.assertAlmostEqual(float(np.linalg.norm(gradient)), 1.0)

    def test_13_p2_zero_gradient_fails_closed(self):
        state = self._state()
        state["p2__3.weight"][:] = 0.0
        with self.assertRaises(RuntimeError):
            lane_g.p2_gradients(np.ones((1, 768)), np.asarray([False]), state)

    def test_14_p2_nonfinite_gradient_fails_closed(self):
        state = self._state()
        state["p2__0.weight"][0, 0] = float("nan")
        with self.assertRaises(RuntimeError):
            lane_g.p2_gradients(np.ones((1, 768)), np.asarray([False]), state)

    def test_14b_p2_floor_equal_gradient_fails_closed(self):
        state = self._state()
        state["p2__0.weight"][0, 0] = 1.0
        state["p2__3.weight"][0, 0] = lane_g.GRADIENT_NORM_FLOOR
        with self.assertRaises(RuntimeError):
            lane_g.p2_gradients(np.ones((1, 768)), np.asarray([False]), state)

    def test_15_robust_direction_is_session_equal_weight(self):
        direction = lane_g.robust_direction(np.asarray([[10.0, 0.0], [1.0, 0.0], [1.0, 0.0]]))
        np.testing.assert_allclose(direction, [1.0, 0.0])

    def test_16_projection_is_invariant_to_basis_sign(self):
        basis = np.eye(3)[:, :2]
        np.testing.assert_allclose(lane_g.projection(basis), lane_g.projection(-basis))

    def test_17_engineering_failure_has_no_scientific_verdict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            with mock.patch.object(lane_g, "pin_inputs", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    lane_g.materialize(root, out)
            self.assertFalse(out.exists())
            failure = out.with_name(out.name + "_control") / "engineering_failure.json"
            self.assertTrue(failure.exists())
            self.assertNotIn("scientific_state", json.loads(failure.read_text(encoding="utf-8")))

    def test_18_no_forbidden_role_constants_overlap(self):
        self.assertFalse(lane_g.FIT_BENIGN_ROLES & lane_g.FORBIDDEN_ROLES)
        self.assertFalse(lane_g.FIT_ATTACK_ROLES & lane_g.FORBIDDEN_ROLES)

    def test_19_state_names_are_literal(self):
        source = TARGET.read_text(encoding="utf-8")
        for state in ("NO_IDENTIFIABLE_DEVICE_SUBSPACE_BY_COUNT", "UNSTABLE_OR_TEMPORAL_DEVICE_SUBSPACE", "ATTACK_DIRECTION_NOT_IDENTIFIABLE", "NO_ATTACK_ORTHOGONAL_DEVICE_NUISANCE", "ATTACK_PROTECTED_DEVICE_SUBSPACE_FEASIBLE"):
            self.assertIn(state, source)

    def test_20_python39_grammar(self):
        ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET), feature_version=(3, 9))

    def test_21_attack_protection_preserves_orthogonal_device_shift(self):
        state = self._state()
        state["p2__0.weight"][:] = 0.0
        state["p2__0.weight"][0, 1] = 2.0
        representations = np.zeros((30, 768), dtype=np.float64)
        representations[:, 1] = 1.0
        sessions = pd.DataFrame({
            "embedding_index": np.arange(30),
            "attack_family": ["f1"] * 15 + ["f2"] * 15,
        })
        gradients, contrasts, summary = lane_g.attack_protection(
            sessions,
            representations,
            np.zeros(30, dtype=bool),
            state,
            np.zeros(768),
            np.eye(768)[:, :1],
            np.asarray([np.eye(768)[0], -np.eye(768)[0]]),
        )
        self.assertEqual(len(gradients), 2)
        self.assertEqual(len(contrasts), 2)
        self.assertTrue(summary["pass"])
        self.assertLessEqual(summary["orthogonality_spectral_norm"], 1e-10)
        self.assertAlmostEqual(summary["median_retained_between_device_energy"], 1.0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LaneGContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
