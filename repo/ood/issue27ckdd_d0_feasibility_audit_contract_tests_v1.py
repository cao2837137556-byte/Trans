#!/usr/bin/env python3
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
MODULE_PATH = HERE / "issue27ckdd_d0_feasibility_audit_v1.py"
SPEC = importlib.util.spec_from_file_location("ckdd", str(MODULE_PATH))
assert SPEC and SPEC.loader
ckdd = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckdd)
ROOT = HERE.parents[1]


class CKDDD0Tests(unittest.TestCase):
    def test_01_python39_module(self):
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_02_python39_tests(self):
        ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 9))

    def test_03_contract_hash(self):
        self.assertEqual(ckdd.sha256_file(ROOT / ckdd.CONTRACT_REL), ckdd.CONTRACT_SHA256)

    def test_04_pin_inputs(self):
        self.assertIn("phase_a_rows", ckdd.pin_inputs(ROOT))

    def test_05_forbidden_report_plan(self):
        with self.assertRaises(RuntimeError):
            ckdd.assert_no_forbidden_open([Path("ckda_d1_report_plan.csv")])

    def test_06_forbidden_final_marker(self):
        with self.assertRaises(RuntimeError):
            ckdd.assert_no_forbidden_open([Path("x/cooler-motor/y")])

    def test_07_reservoir_deterministic(self):
        self.assertEqual(ckdd.reservoir_ordinals(100, 13, 27), ckdd.reservoir_ordinals(100, 13, 27))

    def test_08_reservoir_exact_size_sorted(self):
        values = ckdd.reservoir_ordinals(100, 13, 27)
        self.assertEqual(len(values), 13)
        self.assertEqual(values, sorted(values))

    def test_09_live_provenance(self):
        stage = ROOT / ckdd.STAGE_REL
        plan = pd.read_csv(stage / "ckda_d1_fit_select_plan.csv")
        meta = pd.read_csv(stage / "ckda_d1_fit_select_target_metadata.csv")
        audit = ckdd.provenance_audit(ROOT, plan, meta)
        self.assertTrue(audit["selected_event_positions_match_exact_two_pass_reservoir"])

    def test_10_conflict_counts_literal(self):
        rows = pd.read_csv(ROOT / ckdd.PHASE_A_REL / "ckdc_d0f_phase_a_certificate_rows.csv")
        c = rows.loc[rows["label_metric_only"].eq(0) & rows["p2_hard"].astype(bool) & ~rows["m7_hard"].astype(bool)]
        self.assertEqual(c.groupby("source_group").size().to_dict(), ckdd.CONFLICT_EXPECTED)

    def test_11_partition_gate_has_zero_live(self):
        out = ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/ckdd_d0_partition_census.csv"
        frame = pd.read_csv(out)
        self.assertEqual(int(frame["admissible"].sum()), 0)

    def test_12_partition_count(self):
        frame = pd.read_csv(ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/ckdd_d0_partition_census.csv")
        self.assertEqual(len(frame), 62)

    def test_13_p2_forward_shape_and_bounds(self):
        state = {
            "normalizer_mean": np.zeros(2), "normalizer_scale": np.ones(2),
            "p2__0.weight": np.ones((1, 3)), "p2__0.bias": np.zeros(1),
            "p2__3.weight": np.ones((1, 1)), "p2__3.bias": np.zeros(1),
        }
        score, hidden = ckdd.frozen_p2_scores(np.asarray([[1.0, 2.0]], dtype=np.float32), np.asarray([False]), state)
        self.assertEqual(hidden.shape, (1, 1))
        self.assertTrue(0.0 < score[0] < 1.0)

    def test_14_missing_zeroes_representation_and_sets_indicator(self):
        state = {
            "normalizer_mean": np.zeros(2), "normalizer_scale": np.ones(2),
            "p2__0.weight": np.asarray([[0.0, 0.0, 1.0]]), "p2__0.bias": np.zeros(1),
            "p2__3.weight": np.ones((1, 1)), "p2__3.bias": np.zeros(1),
        }
        score, _ = ckdd.frozen_p2_scores(np.asarray([[9.0, 9.0]], dtype=np.float32), np.asarray([True]), state)
        self.assertGreater(score[0], 0.5)

    def test_15_verdict_live(self):
        payload = json.loads((ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/ckdd_d0_verdict.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["status"], "CKDD_D0_NO_IDENTIFIABLE_SOURCE_SPLIT")

    def test_16_boundary_zero_forbidden(self):
        payload = json.loads((ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/ckdd_d0_boundary_audit.json").read_text(encoding="utf-8"))
        self.assertEqual(payload["report_score_files_opened"], 0)
        self.assertEqual(payload["final_files_opened"], 0)
        self.assertEqual(payload["optimizer_steps"], 0)

    def test_17_manual_incident_transparent_and_unused(self):
        payload = json.loads((ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local/ckdd_d0_boundary_audit.json").read_text(encoding="utf-8"))
        self.assertTrue(payload["manual_schema_inspection_first_row_displayed_after_freeze"])
        self.assertFalse(payload["manual_schema_inspection_used_for_rule_selection"])

    def test_18_sha256s_validate(self):
        base = ROOT / "runs/issue27ckdd_d0_feasibility_audit_v1_2026-08-25_local"
        for line in (base / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, name = line.split(maxsplit=1)
            self.assertEqual(ckdd.sha256_file(base / name.strip()), digest)

    def test_19_failure_has_no_scientific_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp) / "out"
            try:
                raise RuntimeError("synthetic")
            except RuntimeError as exc:
                ckdd.failure_only(out, exc)
            self.assertFalse((out / "ckdd_d0_verdict.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
