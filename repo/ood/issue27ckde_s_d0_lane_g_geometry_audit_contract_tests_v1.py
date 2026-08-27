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


def recensus_metadata(
    devices: int = 9,
    sessions: int = 64,
    missing_devices: int = 0,
    attack_sessions_per_family: int = 1,
) -> pd.DataFrame:
    rows = []
    for device in range(devices):
        for session in range(sessions):
            rows.append({
                "uid": "b%d:%d" % (device, session),
                "role": "aux_fit",
                "source_group": "d%d" % device,
                "attack_family": "benign",
                "label_metric_only": 0,
                "recorded_index": session,
                "session_id": "s%d" % session,
                "timestamp_epoch": float(session),
                "event_position": 1,
                "embedding_archive_index": len(rows),
                "embedding_missing": bool(device < missing_devices),
            })
    for family_index, family in enumerate(lane_g.EXPECTED_ATTACK_FAMILIES):
        for session in range(attack_sessions_per_family):
            rows.append({
                "uid": "a%d:%d" % (family_index, session),
                "role": "support_train",
                "source_group": "attack-device-%d" % family_index,
                "attack_family": family,
                "label_metric_only": 1,
                "recorded_index": session,
                "session_id": "as%d" % session,
                "timestamp_epoch": float(session),
                "event_position": 1,
                "embedding_archive_index": len(rows),
                "embedding_missing": False,
            })
    return pd.DataFrame(rows)


class LaneGContractTests(unittest.TestCase):
    def test_01_literal_identity_and_numeric_conventions(self):
        self.assertEqual(lane_g.CONTRACT_SHA256, "e2de3bd75ac0f4e9a1d90180bcc9db938418e44719f08bac5a89d07b29cf29e6")
        self.assertEqual(lane_g.ERRATUM_SHA256, "156932108d48495c4b6c7156ef2af8e3f10ca74494c75451cb0a30f5222a149d")
        self.assertEqual(lane_g.MISSINGNESS_ERRATUM_SHA256, "c7077dbae15b4792e9b66694ebc453f61f1ad990dd7e61afd89b9a576fba0976")
        self.assertEqual(lane_g.MISSINGNESS_RULE_SHA256, "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9")
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
            ), mock.patch.object(lane_g, "load_availability", side_effect=AssertionError("NPZ opened")):
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
            all_families=("f1", "f2"),
        )
        self.assertEqual(len(gradients), 2)
        self.assertEqual(len(contrasts), 2)
        self.assertTrue(summary["pass"])
        self.assertLessEqual(summary["orthogonality_spectral_norm"], 1e-10)
        self.assertAlmostEqual(summary["median_retained_between_device_energy"], 1.0)

    def test_22_missingness_rule_quote_and_claim_are_literal(self):
        self.assertIn("No target may be\ndropped.", lane_g.MISSINGNESS_RULE_QUOTE)
        self.assertEqual(
            lane_g.CLAIM_SCOPE,
            "geometry of the encodable (`missing=false`) subset of the frozen fit pool",
        )
        root = HERE.parents[1]
        lane_g.require_sha(root / lane_g.MISSINGNESS_RULE_REL, lane_g.MISSINGNESS_RULE_SHA256)
        source = (root / lane_g.MISSINGNESS_RULE_REL).read_text(encoding="utf-8")
        self.assertIn(lane_g.MISSINGNESS_RULE_QUOTE, source)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "recensus.json"
            lane_g.atomic_json(path, {
                "source": str(lane_g.MISSINGNESS_RULE_REL),
                "sha256": lane_g.MISSINGNESS_RULE_SHA256,
                "quote": lane_g.MISSINGNESS_RULE_QUOTE,
            })
            readback = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(readback["quote"], lane_g.MISSINGNESS_RULE_QUOTE)
        self.assertEqual(readback["sha256"], lane_g.MISSINGNESS_RULE_SHA256)

    def test_23_load_availability_reads_boolean_uid_missing_only(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "availability.npz"
            np.savez(
                archive,
                uid=np.asarray(["u2", "u1"]),
                representation=np.asarray([[np.nan], [np.nan]]),
                missing=np.asarray([True, False], dtype=bool),
                candidate_id=np.asarray(["unused"]),
                plan_sha256=np.asarray(["unused"]),
                contract_sha256=np.asarray(["unused"]),
            )
            joined = pd.DataFrame({"uid": ["u1", "u2"]})
            role = {"embedding_uid_missing_arrays_opened": 0}
            with mock.patch.object(lane_g, "EXPECTED_ROWS", 2), mock.patch.dict(
                lane_g.PINS, {"embeddings": (Path("availability.npz"), "unused")}
            ):
                result = lane_g.load_availability(root, joined, role)
            self.assertEqual(role["embedding_uid_missing_arrays_opened"], 1)
            self.assertEqual(result["embedding_archive_index"].tolist(), [1, 0])
            self.assertEqual(result["embedding_missing"].tolist(), [False, True])

    def test_24_load_availability_rejects_nonboolean_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            np.savez(
                root / "availability.npz",
                uid=np.asarray(["u1"]),
                representation=np.asarray([[0.0]]),
                missing=np.asarray([0], dtype=np.int8),
                candidate_id=np.asarray(["unused"]),
                plan_sha256=np.asarray(["unused"]),
                contract_sha256=np.asarray(["unused"]),
            )
            with mock.patch.object(lane_g, "EXPECTED_ROWS", 1), mock.patch.dict(
                lane_g.PINS, {"embeddings": (Path("availability.npz"), "unused")}
            ):
                with self.assertRaisesRegex(RuntimeError, "boolean"):
                    lane_g.load_availability(
                        root,
                        pd.DataFrame({"uid": ["u1"]}),
                        {"embedding_uid_missing_arrays_opened": 0},
                    )

    def test_25_three_recensus_stop_conditions_are_independent_and_no_retry(self):
        cases = (
            (8, 2, 2, "stop_D_finite_lt_9"),
            (9, 1, 1, "stop_r_finite_lt_2"),
            (9, 2, 3, "stop_r_finite_ne_r_metadata"),
        )
        for d_finite, r_finite, r_metadata, field in cases:
            with self.subTest(field=field):
                result = lane_g.availability_gate_status(d_finite, r_finite, r_metadata)
                self.assertEqual(result["status"], "NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR")
                self.assertTrue(result[field])
                self.assertFalse(result["rank_retry_permitted"])
        self.assertEqual(lane_g.availability_gate_status(9, 2, 2)["status"], "RECENSUS_PASS")

    def test_26_terminal_missing_never_substitutes_earlier_finite_target(self):
        joined = recensus_metadata()
        terminal_uid = "b0:0"
        joined.loc[joined["uid"].eq(terminal_uid), "embedding_missing"] = True
        earlier = joined.loc[joined["uid"].eq(terminal_uid)].iloc[0].copy()
        earlier["uid"] = "b0:0:earlier"
        earlier["event_position"] = 0
        earlier["timestamp_epoch"] = -1.0
        earlier["embedding_missing"] = False
        joined = pd.concat([joined, pd.DataFrame([earlier])], ignore_index=True)
        _, count_gate = lane_g.count_rank_gate(joined)
        benign, _, diagnostic, payload, _, _ = lane_g.availability_recensus(
            joined, count_gate, {}, {}
        )
        chosen = benign.loc[benign["source_group"].eq("d0") & benign["session_id"].eq("s0")]
        self.assertEqual(chosen["terminal_uid"].tolist() if "terminal_uid" in chosen else chosen["uid"].tolist(), [terminal_uid])
        self.assertFalse(bool(chosen.iloc[0]["finite_terminal_embedding"]))
        self.assertEqual(payload["missing_terminal_sessions_with_earlier_finite_target"], 1)
        row = diagnostic.loc[diagnostic["terminal_uid"].eq(terminal_uid)].iloc[0]
        self.assertFalse(bool(row["finite_terminal_embedding"]))
        self.assertEqual(int(row["terminal_event_position"]), 1)
        self.assertEqual(int(row["records_in_frozen_session"]), 2)

    def test_27_recensus_emits_exact_device_family_and_session_schemas(self):
        joined = recensus_metadata(attack_sessions_per_family=15)
        _, count_gate = lane_g.count_rank_gate(joined)
        benign, attack, diagnostic, payload, devices, families = lane_g.availability_recensus(
            joined, count_gate, {}, {"embedding_uid_missing_arrays_opened": 1}
        )
        self.assertEqual(payload["status"], "RECENSUS_PASS")
        self.assertEqual(len(benign), 9 * 64)
        self.assertEqual(len(attack), 12 * 15)
        self.assertEqual(families["attack_family"].tolist(), list(lane_g.EXPECTED_ATTACK_FAMILIES))
        self.assertEqual(set(families["protection_status"]), {"PROTECTED_BY_REPRESENTATION_EVIDENCE"})
        self.assertEqual(
            list(devices.columns),
            ["device", "total_terminal_sessions", "finite_terminal_sessions", "missing_terminal_sessions", "finite_rate", "finite_geometry_eligible"],
        )
        self.assertEqual(
            list(diagnostic.columns),
            ["stratum", "device", "session_id", "attack_family", "terminal_uid", "terminal_event_position", "records_in_frozen_session", "finite_terminal_embedding"],
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "families.csv"
            lane_g.atomic_csv(path, families)
            readback = pd.read_csv(path, keep_default_na=False)
        self.assertEqual(readback["attack_family"].tolist(), list(lane_g.EXPECTED_ATTACK_FAMILIES))
        self.assertEqual(len(readback), 12)

    def test_28_recensus_is_deterministic_under_row_permutation(self):
        joined = recensus_metadata(attack_sessions_per_family=2)
        _, count_gate = lane_g.count_rank_gate(joined)
        left = lane_g.availability_recensus(joined, count_gate, {}, {})
        shuffled = joined.sample(frac=1.0, random_state=7).reset_index(drop=True)
        right = lane_g.availability_recensus(shuffled, count_gate, {}, {})
        pd.testing.assert_frame_equal(left[2], right[2])
        pd.testing.assert_frame_equal(left[4], right[4])
        pd.testing.assert_frame_equal(left[5], right[5])
        self.assertEqual(left[3]["status"], right[3]["status"])

    def test_29_recensus_failure_blocks_representation_and_probe_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            rows = metadata(9, 64)
            rows["embedding_archive_index"] = np.arange(len(rows))
            rows["embedding_missing"] = False
            benign = lane_g.terminal_session_rows(rows)
            empty = pd.DataFrame()
            recensus = {
                "status": "NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR",
                "D_metadata": 9,
                "r_metadata": 2,
                "D_finite": 8,
                "r_finite": 2,
                "fit_benign_terminal_sessions": 576,
                "fit_benign_finite_terminal_sessions": 512,
                "fit_benign_missing_terminal_sessions": 64,
                "fit_benign_records": 1152,
                "fit_attack_terminal_sessions": 0,
                "fit_attack_finite_terminal_sessions": 0,
                "fit_attack_missing_terminal_sessions": 0,
                "fit_attack_records": 0,
                "excluded_devices": [
                    "normal_1.pcap",
                    "iotsim-combined-cycle-tls-1_0-0_to_OpenvSwitch-14_1-0",
                ],
                "protected_attack_families": [],
                "unprotected_attack_families": [
                    "File Download",
                    "Ingress Tool Transfer",
                    "Merlin C&C Communication",
                    "Merlin ICMP Flooding",
                    "Mirai C&C Communication",
                    "Mirai GRE Flooding",
                    "Mirai UDP Flooding",
                ],
            }

            def availability(_root, frame, audit):
                audit["embedding_uid_missing_arrays_opened"] = 1
                return frame

            with mock.patch.object(lane_g, "pin_inputs", return_value={}), mock.patch.object(
                lane_g, "load_metadata_only", return_value=rows
            ), mock.patch.object(lane_g, "load_availability", side_effect=availability), mock.patch.object(
                lane_g,
                "availability_recensus",
                return_value=(benign, empty, empty, recensus, empty, empty),
            ), mock.patch.object(
                lane_g, "load_representations", side_effect=AssertionError("representation opened")
            ), mock.patch.object(
                lane_g, "load_probe_state", side_effect=AssertionError("probe opened")
            ):
                verdict = lane_g.materialize(root, out)
            self.assertEqual(verdict["status"], "NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR")
            self.assertEqual(verdict["representation_arrays_opened"], 0)
            self.assertEqual(verdict["embedding_arrays_opened"], 0)
            self.assertEqual(verdict["probe_state_arrays_opened"], 0)
            for name in ("report_files_opened", "final_files_opened", "network_requests_made", "training_steps_run"):
                self.assertEqual(verdict[name], 0)
            self.assertEqual(set(verdict["denominators"]), {"devices", "sessions", "records"})
            self.assertEqual(
                verdict["excluded_devices"],
                ["normal_1.pcap", "iotsim-combined-cycle-tls-1_0-0_to_OpenvSwitch-14_1-0"],
            )
            self.assertEqual(len(verdict["unprotected_attack_families"]), 7)
            self.assertTrue(all(
                row["protection_status"] == "UNPROTECTED_BY_REPRESENTATION_EVIDENCE"
                for row in verdict["unprotected_attack_families"]
            ))
            allowed = {
                "ckde_s_d0_embedding_availability_recensus.json",
                "ckde_s_d0_embedding_availability_by_device.csv",
                "ckde_s_d0_embedding_availability_by_attack_family.csv",
                "ckde_s_d0_embedding_availability_session_diagnostic.csv",
                "ckde_s_d0_role_open_audit.json",
                "ckde_s_d0_geometry_verdict.json",
                "SHA256SUMS",
            }
            self.assertEqual({path.name for path in out.iterdir()}, allowed)
            joined_json = "\n".join(
                path.read_text(encoding="utf-8")
                for path in out.iterdir()
                if path.suffix == ".json"
            ).lower()
            for forbidden in ("principal_angle", "singular_value", "device_center", "gradient_norm", "projection_fraction"):
                self.assertNotIn(forbidden, joined_json)

    def test_30_legacy_embedding_counter_is_exact_representation_alias(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertEqual(source.count('role_audit["representation_arrays_opened"] = 1'), 1)
        self.assertEqual(source.count('role_audit["embedding_arrays_opened"] = 1'), 1)
        self.assertLess(
            source.index('role_audit["representation_arrays_opened"] = 1'),
            source.index('role_audit["embedding_arrays_opened"] = 1'),
        )

    def test_31_new_scientific_state_and_no_retry_are_literal(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertIn("NO_IDENTIFIABLE_COMPLETE_SESSION_EMBEDDING_DENOMINATOR", source)
        self.assertNotIn("r_finite -", source)
        self.assertNotIn("r_finite -=", source)

    def test_32_protected_and_unprotected_family_lists_follow_finite_counts(self):
        joined = recensus_metadata(attack_sessions_per_family=15)
        missing_family = lane_g.EXPECTED_ATTACK_FAMILIES[0]
        joined.loc[joined["attack_family"].eq(missing_family), "embedding_missing"] = True
        _, count_gate = lane_g.count_rank_gate(joined)
        result = lane_g.availability_recensus(joined, count_gate, {}, {})
        payload, families = result[3], result[5]
        self.assertEqual(payload["unprotected_attack_families"], [missing_family])
        self.assertNotIn(missing_family, payload["protected_attack_families"])
        status = families.set_index("attack_family").loc[missing_family, "protection_status"]
        self.assertEqual(status, "UNPROTECTED_BY_REPRESENTATION_EVIDENCE")

    def test_33_attack_span_uses_one_direction_per_family(self):
        state = self._state()
        device_basis = np.eye(768)[:, 1:2]
        shifts = np.asarray([np.eye(768)[1], -np.eye(768)[1]])

        def run(count_f2):
            count = 15 + count_f2
            representations = np.ones((count, 768), dtype=np.float64)
            sessions = pd.DataFrame({
                "embedding_index": np.arange(count),
                "attack_family": ["f1"] * 15 + ["f2"] * count_f2,
            })
            return lane_g.attack_protection(
                sessions,
                representations,
                np.zeros(count, dtype=bool),
                state,
                np.zeros(768),
                device_basis,
                shifts,
                all_families=("f1", "f2"),
            )

        baseline = run(15)
        duplicated = run(30)
        self.assertEqual(baseline[0]["attack_family"].tolist(), ["f1", "f2"])
        self.assertEqual(baseline[2]["eligible_attack_families"], ["f1", "f2"])
        self.assertEqual(baseline[2]["attack_basis_rank"], duplicated[2]["attack_basis_rank"])
        self.assertAlmostEqual(
            baseline[2]["orthogonality_spectral_norm"],
            duplicated[2]["orthogonality_spectral_norm"],
        )

    def test_34_missing_channel_immunity_is_not_promoted_to_geometry_claim(self):
        source = TARGET.read_text(encoding="utf-8")
        self.assertNotIn("missing channel is attack-safe", source.lower())
        self.assertNotIn("missing rows are protected", source.lower())
        self.assertIn("encodable (`missing=false`) subset", lane_g.CLAIM_SCOPE)

    def test_35_all_four_missingness_diagnostics_are_scientific_outputs(self):
        expected = {
            "ckde_s_d0_embedding_availability_recensus.json",
            "ckde_s_d0_embedding_availability_by_device.csv",
            "ckde_s_d0_embedding_availability_by_attack_family.csv",
            "ckde_s_d0_embedding_availability_session_diagnostic.csv",
        }
        self.assertTrue(expected.issubset(lane_g.SCIENTIFIC_OUTPUTS))

    def test_36_viewed_recensus_values_are_not_encoded_as_success_expectations(self):
        source = TARGET.read_text(encoding="utf-8")
        for viewed in ("13827", "11640", "8372", "2087", "4262", "4123", "6424"):
            self.assertNotIn(viewed, source)

    def test_37_duplicate_and_missing_uid_availability_fail_engineering(self):
        cases = (
            (np.asarray(["u1", "u1"]), pd.DataFrame({"uid": ["u1", "u2"]}), "UID drift"),
            (np.asarray(["u1", "u3"]), pd.DataFrame({"uid": ["u1", "u2"]}), "exact UID join"),
        )
        for uids, joined, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                np.savez(
                    root / "availability.npz",
                    uid=uids,
                    representation=np.zeros((2, 1)),
                    missing=np.zeros(2, dtype=bool),
                    candidate_id=np.asarray(["unused"]),
                    plan_sha256=np.asarray(["unused"]),
                    contract_sha256=np.asarray(["unused"]),
                )
                with mock.patch.object(lane_g, "EXPECTED_ROWS", 2), mock.patch.dict(
                    lane_g.PINS, {"embeddings": (Path("availability.npz"), "unused")}
                ):
                    with self.assertRaisesRegex(RuntimeError, message):
                        lane_g.load_availability(
                            root, joined, {"embedding_uid_missing_arrays_opened": 0}
                        )

    def test_38_role_open_alias_disagreement_fails_engineering(self):
        audit = {
            "embedding_uid_missing_arrays_opened": 1,
            "representation_arrays_opened": 1,
            "embedding_arrays_opened": 0,
            "probe_state_arrays_opened": 1,
            "report_files_opened": 0,
            "final_files_opened": 0,
            "network_requests_made": 0,
            "training_steps_run": 0,
        }
        with self.assertRaisesRegex(RuntimeError, "alias drift"):
            lane_g.validate_role_open_audit(audit)

    def test_39_recensus_pass_opens_representation_then_probe_and_publishes_alias(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            out = root / "out"
            rows = recensus_metadata(attack_sessions_per_family=1)

            def availability(_root, frame, audit):
                audit["embedding_uid_missing_arrays_opened"] = 1
                return frame.copy()

            def representations(_root, frame, audit):
                audit["representation_arrays_opened"] = 1
                audit["embedding_arrays_opened"] = 1
                result = frame.copy().reset_index(drop=True)
                result["embedding_index"] = np.arange(len(result))
                values = np.zeros((len(result), lane_g.WIDTH), dtype=np.float64)
                for index, row in result.iterrows():
                    if row["role"] in lane_g.FIT_BENIGN_ROLES:
                        device = int(str(row["source_group"])[1:])
                        session = int(str(row["session_id"])[1:])
                        values[index, 0] = float(device) + (10.0 if session >= 32 else 0.0)
                        values[index, 1] = float(device % 3)
                return result, values

            def probe(_root, audit):
                audit["probe_state_arrays_opened"] = 1
                return {}

            with mock.patch.object(lane_g, "pin_inputs", return_value={}), mock.patch.object(
                lane_g, "load_metadata_only", return_value=rows
            ), mock.patch.object(lane_g, "load_availability", side_effect=availability), mock.patch.object(
                lane_g, "load_representations", side_effect=representations
            ), mock.patch.object(lane_g, "load_probe_state", side_effect=probe):
                verdict = lane_g.materialize(root, out)
            self.assertEqual(verdict["scientific_state"], "G1")
            self.assertEqual(verdict["embedding_uid_missing_arrays_opened"], 1)
            self.assertEqual(verdict["representation_arrays_opened"], 1)
            self.assertEqual(verdict["embedding_arrays_opened"], 1)
            self.assertEqual(verdict["probe_state_arrays_opened"], 1)
            role = json.loads((out / "ckde_s_d0_role_open_audit.json").read_text(encoding="utf-8"))
            self.assertEqual(role["representation_arrays_opened"], role["embedding_arrays_opened"])
            self.assertEqual(role["report_files_opened"], 0)
            self.assertEqual(role["final_files_opened"], 0)
            self.assertEqual(role["network_requests_made"], 0)
            self.assertEqual(role["training_steps_run"], 0)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LaneGContractTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print(json.dumps({"status": "PASS" if result.wasSuccessful() else "FAIL", "tests": result.testsRun}, sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
