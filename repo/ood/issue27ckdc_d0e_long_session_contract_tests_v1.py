#!/usr/bin/env python3
"""Contract tests for CKDC D0-E."""

from __future__ import annotations

import ast
import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "issue27ckdc_d0e_long_session_mechanism_v1.py"
SPEC = importlib.util.spec_from_file_location("ckdce", str(MODULE_PATH))
assert SPEC and SPEC.loader
ckdce = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckdce)
ROOT = HERE.parents[1]


def synthetic(first_hard: bool = False, sources: int = 5) -> pd.DataFrame:
    rows = []
    for source in range(sources):
        for session, count in (("long", 70), ("short", 2)):
            for index in range(count):
                hard = first_hard if index == 0 else (index >= 1)
                rows.append({
                    "source_group": "source_%d" % source,
                    "session_id": "%s_%d" % (session, source),
                    "uid": "%d_%s_%d" % (source, session, index),
                    "timestamp_epoch": float(index), "event_position": index,
                    "p2_hard": hard, "m7_hard_bool": False, "score": float(hard),
                })
    return pd.DataFrame(rows)


class CKDCEContractTests(unittest.TestCase):
    def test_01_python39_syntax(self) -> None:
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_contract_sha(self) -> None:
        self.assertEqual(ckdce.sha256_file(ROOT / ckdce.CONTRACT_REL), ckdce.CONTRACT_SHA256)

    def test_03_longest_selected_without_scores(self) -> None:
        frame = synthetic()
        selected = ckdce.choose_longest_sessions(frame)
        self.assertEqual(selected["target_count"].tolist(), [70] * 5)
        self.assertTrue(selected["session_id"].str.startswith("long_").all())

    def test_04_tie_breaks_by_session_id(self) -> None:
        frame = synthetic()
        extra = frame.loc[frame["session_id"].eq("long_0")].copy()
        extra["session_id"] = "aaa"
        extra["uid"] = "x_" + extra["uid"]
        selected = ckdce.choose_longest_sessions(pd.concat([frame, extra], ignore_index=True))
        self.assertEqual(selected.loc[selected["source_group"].eq("source_0"), "session_id"].iloc[0], "aaa")

    def test_05_minimum_65_targets(self) -> None:
        frame = synthetic()
        frame = frame.groupby(["source_group", "session_id"], group_keys=False).head(64)
        with self.assertRaises(RuntimeError):
            ckdce.choose_longest_sessions(frame)

    def test_06_session_class(self) -> None:
        self.assertEqual(ckdce.classify(True, 0.90), "SESSION_CLASS_CONFLICT")

    def test_07_transition_class(self) -> None:
        self.assertEqual(ckdce.classify(False, 0.90), "WITHIN_SESSION_TRANSITION")

    def test_08_no_persistent_class(self) -> None:
        self.assertEqual(ckdce.classify(True, 0.89), "NO_PERSISTENT_LONG_SESSION_HARD_STATE")

    def test_09_route_session_class(self) -> None:
        frame = pd.DataFrame({"mechanism_class": ["SESSION_CLASS_CONFLICT"] * 3 + ["x"] * 2})
        self.assertEqual(ckdce.route_verdict(frame), "SESSION_CLASS_SIGNAL")

    def test_10_route_transition(self) -> None:
        frame = pd.DataFrame({"mechanism_class": ["WITHIN_SESSION_TRANSITION"] * 3 + ["x"] * 2})
        self.assertEqual(ckdce.route_verdict(frame), "WITHIN_SESSION_TRANSITION_SIGNAL")

    def test_11_analyze_transition(self) -> None:
        selected, checkpoints, verdict = ckdce.analyze(synthetic(first_hard=False))
        self.assertEqual(verdict["verdict"], "WITHIN_SESSION_TRANSITION_SIGNAL")
        self.assertEqual(len(selected), 5)
        self.assertTrue(checkpoints["present"].all())

    def test_12_analyze_session_class(self) -> None:
        selected, _, verdict = ckdce.analyze(synthetic(first_hard=True))
        self.assertEqual(verdict["verdict"], "SESSION_CLASS_SIGNAL")
        self.assertTrue(selected["hard_persistent_after_first_hard"].all())

    def test_13_final_fails_closed(self) -> None:
        with self.assertRaises(RuntimeError):
            ckdce.verify_no_final(pd.DataFrame({"uid": ["cooler-motor"], "source_group": ["x"]}))

    def test_14_existing_output_not_replaced(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                ckdce.failure_only(output, RuntimeError("x"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
