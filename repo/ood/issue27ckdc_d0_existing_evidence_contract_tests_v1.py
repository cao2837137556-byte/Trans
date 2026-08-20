#!/usr/bin/env python3
"""Contract tests for CKDC D0 existing-evidence diagnosis."""

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
MODULE_PATH = HERE / "issue27ckdc_d0_existing_evidence_diagnostic_v1.py"
SPEC = importlib.util.spec_from_file_location("ckdc", str(MODULE_PATH))
assert SPEC and SPEC.loader
ckdc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckdc)
ROOT = HERE.parents[1]


def support_frame(
    benign_rows: int = 300,
    attack_rows: int = 30,
    benign_sources: int = 3,
    attack_families: int = 3,
) -> pd.DataFrame:
    rows = []
    for index in range(benign_rows):
        rows.append({
            "quadrant": "P2_HARD__M7_NORMAL",
            "label_metric_only": 0,
            "source_group": "benign_%d" % (index % benign_sources),
            "attack_family": "benign",
        })
    for index in range(attack_rows):
        rows.append({
            "quadrant": "P2_HARD__M7_NORMAL",
            "label_metric_only": 1,
            "source_group": "attack_source",
            "attack_family": "attack_%d" % (index % attack_families),
        })
    return pd.DataFrame(rows)


class CKDCD0ContractTests(unittest.TestCase):
    def test_01_python39_syntax(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        ast.parse(source, filename=str(MODULE_PATH), feature_version=(3, 9))

    def test_02_contract_sha_literal(self) -> None:
        self.assertEqual(
            ckdc.sha256_file(ROOT / ckdc.CONTRACT_REL),
            ckdc.CONTRACT_SHA256,
        )

    def test_03_four_quadrants(self) -> None:
        actual = {
            ckdc.quadrant(False, False), ckdc.quadrant(False, True),
            ckdc.quadrant(True, False), ckdc.quadrant(True, True),
        }
        self.assertEqual(actual, {
            "P2_NORMAL__M7_NORMAL", "P2_NORMAL__M7_HARD",
            "P2_HARD__M7_NORMAL", "P2_HARD__M7_HARD",
        })

    def test_04_bool_series_rejects_unknown(self) -> None:
        with self.assertRaises(ValueError):
            ckdc.bool_series(pd.Series(["yes"]))

    def test_05_ordinal_boundaries(self) -> None:
        values = [1, 2, 4, 5, 16, 17, 64, 65]
        self.assertEqual([ckdc.ordinal_bin(v) for v in values],
                         ["1", "2-4", "2-4", "5-16", "5-16", "17-64", "17-64", "65+"])

    def test_06_elapsed_boundaries(self) -> None:
        values = [0, 1, 1.01, 10, 10.01, 60, 60.01, 300, 300.01, 1800, 1800.01]
        self.assertEqual([ckdc.elapsed_bin(v) for v in values], [
            "0-1s", "0-1s", "(1,10]s", "(1,10]s", "(10,60]s", "(10,60]s",
            "(60,300]s", "(60,300]s", "(300,1800]s", "(300,1800]s", ">1800s",
        ])

    def test_07_position_boundaries(self) -> None:
        values = [0, 72, 73, 256, 257, 1024, 1025]
        self.assertEqual([ckdc.position_bin(v) for v in values],
                         ["0-72", "0-72", "73-256", "73-256", "257-1024", "257-1024", "1025+"])

    def test_08_h3_all_pass(self) -> None:
        result = ckdc.h3_decision(support_frame())
        self.assertEqual(result["verdict"], "H3_LEGAL_SUPPORT_PRESENT")
        self.assertTrue(all(result["clauses"].values()))

    def test_09_h3_attack_rows_fail(self) -> None:
        result = ckdc.h3_decision(support_frame(attack_rows=29))
        self.assertFalse(result["clauses"]["attack_rows_ge_30"])
        self.assertEqual(result["verdict"], "NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT")

    def test_10_h3_attack_families_fail(self) -> None:
        result = ckdc.h3_decision(support_frame(attack_families=2))
        self.assertFalse(result["clauses"]["attack_families_ge_3"])

    def test_11_h3_benign_sources_fail(self) -> None:
        result = ckdc.h3_decision(support_frame(benign_sources=2))
        self.assertFalse(result["clauses"]["benign_source_groups_ge_3"])

    def test_12_h3_concentration_fail(self) -> None:
        frame = support_frame()
        benign = frame["label_metric_only"].eq(0)
        frame.loc[benign, "source_group"] = "dominant"
        frame.loc[frame.index[:30], "source_group"] = ["small_%d" % (i % 2) for i in range(30)]
        result = ckdc.h3_decision(frame)
        self.assertFalse(result["clauses"]["benign_max_share_le_0_80"])

    def test_13_h1_insufficient(self) -> None:
        frame = pd.DataFrame([{"eligible": False, "delta_late_minus_early": 0.5}])
        self.assertEqual(ckdc.h1_decision(frame)["verdict"], "INSUFFICIENT_EARLY_LATE_SUPPORT")

    def test_14_h1_positive_three_sources(self) -> None:
        frame = pd.DataFrame({"eligible": [True] * 4, "delta_late_minus_early": [0.10, 0.2, 0.3, 0.01]})
        result = ckdc.h1_decision(frame)
        self.assertEqual(result["signal"], "LATE_STAGE_DEGRADATION_SIGNAL")

    def test_15_h1_negative_three_sources(self) -> None:
        frame = pd.DataFrame({"eligible": [True] * 3, "delta_late_minus_early": [-0.10, -0.2, -0.3]})
        result = ckdc.h1_decision(frame)
        self.assertEqual(result["signal"], "LATE_STAGE_IMPROVEMENT_SIGNAL")

    def test_16_h1_mixed_is_no_signal(self) -> None:
        frame = pd.DataFrame({"eligible": [True] * 4, "delta_late_minus_early": [0.2, 0.2, -0.2, -0.2]})
        self.assertEqual(ckdc.h1_decision(frame)["verdict"], "NO_CONSISTENT_TIME_COURSE_SIGNAL")

    def test_17_deterministic_tie_order(self) -> None:
        frame = pd.DataFrame({
            "session_id": ["s", "s", "s"], "timestamp_epoch": [1.0, 1.0, 1.0],
            "event_position": [2, 2, 1], "uid": ["b", "a", "z"],
        }).sort_values(["session_id", "timestamp_epoch", "event_position", "uid"], kind="mergesort")
        self.assertEqual(frame["uid"].tolist(), ["z", "a", "b"])

    def test_18_source_contrast_minimum_support(self) -> None:
        rows = []
        for ordinal in range(1, 65):
            rows.append({"source_group": "s", "target_ordinal_so_far": ordinal,
                         "session_id": "session_%d" % (ordinal % 6), "p2_hard": True})
        result = ckdc.source_contrasts(pd.DataFrame(rows))
        self.assertFalse(bool(result.loc[0, "eligible"]))

    def test_19_final_marker_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            ckdc.verify_no_final(pd.DataFrame({"uid": ["cooler-motor-final"]}), ["uid"])

    def test_20_e3_capability(self) -> None:
        result = ckdc.audit_e3_capability(
            ROOT / "repo/ood/issue27ckda_d1_e3_embed_v1.py",
            ROOT / "repo/ood/issue27ckda_d0_resource_pilot_v1.py",
        )
        self.assertEqual(result["max_packet_content_records"], 72)
        self.assertTrue(result["later_duration_visible"])
        self.assertFalse(result["later_packet_content_beyond_caps_visible"])

    def test_21_atomic_text_uses_lf(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.txt"
            ckdc.atomic_text(path, "a\nb\n")
            self.assertEqual(path.read_bytes(), b"a\nb\n")

    def test_22_atomic_json_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.json"
            ckdc.atomic_json(path, {"status": "PASS"})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["status"], "PASS")

    def test_23_failure_output_has_no_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "failure"
            try:
                raise RuntimeError("synthetic")
            except RuntimeError as exc:
                ckdc.failure_only(output, exc)
            self.assertTrue((output / "engineering_failure.json").is_file())
            self.assertFalse((output / "ckdc_d0_verdict.json").exists())

    def test_24_time_course_names_capture_position_honestly(self) -> None:
        frame = pd.DataFrame({
            "source_group": ["s"], "ordinal_bin": ["1"], "elapsed_bin": ["0-1s"],
            "capture_event_position_bin": ["0-72"], "session_id": ["x"],
            "p2_hard": [False], "m7_hard_bool": [False], "score": [0.1],
        })
        output = ckdc.time_course(frame)
        self.assertIn("capture_event_position_not_session_packet_count", set(output["dimension"]))

    def test_25_sha_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x"
            path.write_bytes(b"x")
            with self.assertRaises(RuntimeError):
                ckdc.require_sha(path, "0" * 64)


if __name__ == "__main__":
    unittest.main(verbosity=2)
