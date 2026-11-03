"""Synthetic counterexamples for metric and protection errors."""
import unittest
import json

import numpy as np

from lg import metrics as m


def fixture(name="G0", attacks=100, device=None):
    device = device or f"device-{name}"
    rows = [dict(label=0, device=device, activity="normal", phase="TCP_OTHER", annotation="normal")
            for _ in range(4)]
    rows += [dict(label=1, device=device, activity="attack", phase="TCP_OTHER", annotation="attack")
             for _ in range(attacks)]
    raw = np.full((len(rows), 4), .2)
    raw[2:4] = -.2
    d0, local = raw.copy(), raw.copy()
    local[:2] = -.2
    exposure = np.zeros_like(raw, dtype=bool)
    exposure[4] = True
    normal_cap = np.zeros_like(raw, dtype=bool)
    normal_cap[:2] = True
    return dict(name=name, rows=rows, weights=np.ones(len(rows)), raw=raw, d0=d0,
                local=local, cuts=np.zeros(4), branches=["1C", "2C_ZERO"] + ["OTHER"] * (len(rows)-2),
                exposure=exposure, normal_cap=normal_cap, lambda_value=.25, cal_pass=True)


def report(**kwargs):
    return m.evaluate_source_fold(**kwargs)


class ArithmeticTests(unittest.TestCase):
    def test_exact_historical_ensemble_paths(self):
        logits = np.array([[1e16, 1., -1e16], [-1e16, 1e16, 1.],
                           [.1, .2, .3], [-0., -0., -0.]], dtype=np.float64)
        expected_source = np.zeros(len(logits), dtype=np.float64)
        for column in logits.T:
            expected_source += column
        expected_source /= 3
        expected_target = np.stack([logits[:, j] for j in range(3)]).mean(0, dtype=np.float64)
        self.assertEqual(m.ensemble(logits, "source").tobytes(), expected_source.tobytes())
        self.assertEqual(m.ensemble(logits, "target").tobytes(), expected_target.tobytes())
        # The cutoff is strict, including an exact ensemble tie.
        self.assertFalse(m.ensemble(logits, "source")[0] > 0)

    def test_correction_from_raw_not_incremental_d0(self):
        raw = np.array([[1., .3, -.2], [0., 2., 3.]])
        support = np.array([.7, 0.])
        scales = np.array([2., 3., 4.])
        expected = raw.copy()
        for j in range(3):
            expected[0, j] = raw[0, j] - .25 * scales[j] * support[0]
        for mode in ("source", "target"):
            actual = m.apply_correction(raw, support, scales, .25, mode)
            np.testing.assert_array_equal(actual[:, :3], expected)
            np.testing.assert_array_equal(actual[:, 3], m.ensemble(expected, mode))

    def test_new_1c_eligible_attack_cannot_disappear_under_old_mask(self):
        raw = np.full((1, 3), .1)
        old = m.scenario_scores(raw, [[0.]], [[False]], [1., 1., 1.], .25)
        new = m.scenario_scores(raw, [[1.]], [[True]], [1., 1., 1.], .25)
        incorrect = m.scenario_scores(raw, [[1.]], [[False]], [1., 1., 1.], .25)
        self.assertTrue(m.calibration_check(raw, incorrect["safety"], np.zeros(4))["pass"])
        self.assertFalse(m.calibration_check(raw, new["safety"], np.zeros(4))["pass"])
        risk = m.paired_donor_risk(raw, old["donor"], new["donor"], old["eligible"], new["eligible"], np.zeros(4))
        self.assertTrue(risk["raw_to_local"].all())
        self.assertTrue(risk["new_uid_withdrawals"].all())
        np.testing.assert_array_equal(old["safety"], m.score_columns(raw))

    def test_donor_union_count_once_and_scenarios_do_not_cancel(self):
        raw = np.full((1, 4), .1)
        d0 = np.array([[[-.1]*4, [.1]*4]])
        local = np.array([[[-.1]*4, [-.1]*4]])
        mask = np.ones((1, 2), dtype=bool)
        risk = m.paired_donor_risk(raw, d0, local, mask, mask, np.zeros(4))
        self.assertTrue(risk["new_scenarios"].all())
        self.assertFalse(risk["new_uid_withdrawals"].any())
        self.assertEqual(risk["raw_to_local"].shape, (1, 4))

    def test_lambda_grid_uses_every_seed_and_strict_cut(self):
        raw = np.array([[.1, 10., 10.]])
        selected = m.calibrate_lambda(raw, [[1.]], [[True]], [1., 1., 1.], np.zeros(4))
        self.assertEqual(selected["selected_lambda"], .05)
        self.assertFalse(selected["grid"][2]["pass"])
        self.assertEqual(selected["grid"][2]["withdrawals"]["27"], 1)
        with self.assertRaises(ValueError):
            m.calibrate_lambda(np.empty((0, 3)), np.empty((0, 1)), np.empty((0, 1), bool), [1]*3, np.zeros(4))


class AccountingTests(unittest.TestCase):
    def test_subsets_condition_parent_weights_not_equal_device_reweighting(self):
        rows = [dict(label=0, device="a", activity="n", phase="p"),
                dict(label=0, device="b", activity="n", phase="p"),
                dict(label=1, device="a", activity="x", phase="p")]
        raw = np.array([[1.]*4, [-1.]*4, [1.]*4])
        out = m.evaluate_population(name="subset", rows=rows, weights=[.01, .1, .03],
                                    raw=raw, d0=raw, local=raw, cuts=np.zeros(4))
        self.assertAlmostEqual(out["metrics"]["RAW"]["ensemble"]["fpr"], 1/11)
        self.assertAlmostEqual(out["metrics"]["RAW"]["ensemble"]["normal_weight"], .11)
        self.assertEqual(out["group_metrics"]["RAW"]["device"]["a"]["ensemble"]["fpr"], 1.)
        self.assertIsNone(out["group_metrics"]["RAW"]["device"]["b"]["ensemble"]["recall"])

    def test_original_fn_cannot_offset_new_withdrawals(self):
        data = fixture(attacks=1000)
        data["raw"][4:24] = -.2
        data["d0"][4:24] = -.2
        data["local"][4:24] = -.2
        data["local"][4] = .2  # illicit recovery of one old FN
        data["local"][24] = -.2  # one new withdrawal; net recall unchanged
        data["exposure"][:] = False
        data["exposure"][25] = True
        out = report(**data)
        ledger = out["protection"]["own"]["ensemble"]["ledger"]
        self.assertEqual(ledger["raw_fn"]["count"], 20)
        self.assertEqual(ledger["raw_to_local"]["count"], 1)
        self.assertEqual(ledger["recovered_raw_fn"]["count"], 1)
        self.assertEqual(out["metrics"]["RAW"]["ensemble"]["recall"], out["metrics"]["L"]["ensemble"]["recall"])
        gate = m.source_gate([out, report(**fixture("G1"))])
        self.assertEqual(gate["status"], "TECHNICAL_SCORE_ORDER_FAIL")

    def test_cumulative_ledger_does_not_issue_another_one_pp(self):
        data = fixture(attacks=250)
        data["d0"][4:6] = -.2
        data["local"][4:7] = -.2
        data["exposure"][:] = False
        data["exposure"][7] = True
        out = report(**data)
        ledger = out["protection"]["safety"]["ensemble"]["ledger"]
        self.assertAlmostEqual(ledger["raw_to_d0"]["pp"], .8)
        self.assertAlmostEqual(ledger["d0_to_local"]["pp"], .4)
        self.assertAlmostEqual(ledger["raw_to_local"]["pp"], 1.2)
        gate = m.source_gate([out, report(**fixture("G1"))])
        self.assertEqual(gate["status"], "SAFETY_FAIL")

    def test_new_1c_donor_loss_is_reported_despite_other_own_branch(self):
        data = fixture(attacks=1000)
        base, changed = data["raw"].copy(), data["raw"].copy()
        changed[4] = -.2
        data["safety_d0"] = data["d0"].copy()
        data["safety_local"] = data["local"].copy()
        data["safety_local"][4] = -.2
        data["safety_branch_scores"] = {"1C": {"d0": base, "local": changed}}
        out = report(**data)
        self.assertEqual(out["protection"]["own"]["27"]["branches"]["1C"]["raw_to_local"]["count"], 0)
        self.assertEqual(out["protection"]["safety"]["27"]["branches"]["1C"]["raw_to_local"]["count"], 1)
        self.assertAlmostEqual(out["protection"]["safety"]["27"]["branches"]["1C"]["raw_to_local"]["pp"], .1)


class GateTests(unittest.TestCase):
    def test_valid_source_pass_and_large_cap_is_not_actual_failure(self):
        data = fixture()
        data["exposure"][4:] = True  # 100pp envelope is not observed withdrawal
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertTrue(gate["pass"], gate)
        self.assertFalse(gate["independent_confirmation"])

    def test_low_raw_recall_may_not_decline_even_within_device_budget(self):
        data = fixture(attacks=1000)
        for key in ("raw", "d0", "local"):
            data[key][4:24] = -.2
        data["local"][24] = -.2  # 0.1pp, within 1pp device budget
        data["exposure"][:] = False
        data["exposure"][25] = True
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "SAFETY_FAIL")
        self.assertTrue(any("RAW recall below 99%" in reason for reason in gate["reasons"]))

    def test_d0_transfer_failure_has_baseline_status(self):
        data = fixture(attacks=1000)
        for key in ("raw", "d0", "local"):
            data[key][4:24] = -.2
        data["d0"][24] = data["local"][24] = -.2
        data["exposure"][:] = False
        data["exposure"][25] = True
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "BASELINE_TRANSFER_GUARD_FAIL")

    def test_phase_device_guard_and_all_four_suffixes(self):
        data = fixture(attacks=400)
        for i, row in enumerate(data["rows"][4:]):
            row["phase"] = "small" if i < 100 else "large"
        data["local"][4:6, 1] = -.2  # seed127: pool0.5pp, phase-device2pp
        out = report(**data)
        gate = m.source_gate([out, report(**fixture("G1"))])
        self.assertEqual(gate["status"], "SAFETY_FAIL")
        self.assertTrue(any("127/phase_device" in reason for reason in gate["reasons"]))

    def test_phase_activity_has_its_own_denominator_and_five_pp_guard(self):
        data = fixture(attacks=1000)
        for i, row in enumerate(data["rows"][4:]):
            row["phase"] = "p" if i < 100 else "q"
            row["activity"] = "small" if i < 10 or 100 <= i < 290 else "other"
        data["local"][4, 2] = -.2
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "SAFETY_FAIL")
        self.assertTrue(any("227/phase_activity" in reason for reason in gate["reasons"]))
        self.assertFalse(any("227/phase_device" in reason for reason in gate["reasons"]))

    def test_missing_pressure_or_branches_never_passes_zero_denominator(self):
        data = fixture()
        data["exposure"][:] = False
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "DIAGNOSTIC_COVERAGE_INSUFFICIENT")
        a, b = fixture(), fixture("G1")
        a["branches"] = ["OTHER"] * len(a["rows"])
        b["branches"] = ["OTHER"] * len(b["rows"])
        self.assertEqual(m.source_gate([report(**a), report(**b)])["status"], "DIAGNOSTIC_COVERAGE_INSUFFICIENT")

    def test_gain_gate_and_zero_lambda(self):
        data = fixture()
        data["local"][:2] = data["d0"][:2]
        self.assertEqual(m.source_gate([report(**data), report(**fixture("G1"))])["status"], "PRACTICAL_GAIN_GATE_NOT_MET")
        data["lambda_value"] = 0
        self.assertEqual(m.source_gate([report(**data), report(**fixture("G1"))])["status"], "NO_CORRECTION_BUDGET")

    def test_legal_cap_without_enough_crossing_space_is_coverage_stop(self):
        data = fixture()
        data["local"][:2] = data["d0"][:2]
        data["normal_cap"][:] = False
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "DIAGNOSTIC_COVERAGE_INSUFFICIENT")
        self.assertTrue(any("20%" in reason for reason in gate["reasons"]))

    def test_source_donor_safety_overrides_safe_own_scores(self):
        data = fixture(attacks=100)
        data["safety_d0"] = data["d0"].copy()
        data["safety_local"] = data["local"].copy()
        data["safety_local"][4:6] = -.2
        gate = m.source_gate([report(**data), report(**fixture("G1"))])
        self.assertEqual(gate["status"], "SAFETY_FAIL")
        self.assertTrue(any("safety/" in reason for reason in gate["reasons"]))

    def test_target_ensemble_endpoints_and_single_seed_guards(self):
        a, b = fixture("A", attacks=1000), fixture("B", attacks=1000)
        self.assertTrue(m.target_gate([report(**a), report(**b)])["pass"])
        b["local"][4:15, 0] = -.2  # ensemble good, seed27 1.1pp device loss
        gate = m.target_gate([report(**a), report(**b)])
        self.assertEqual(gate["status"], "TARGET_CONTRACT_NOT_MET")
        self.assertTrue(any("27/device" in reason for reason in gate["reasons"]))

    def test_target_does_not_inherit_source_phase_guard(self):
        a, b = fixture("A", attacks=400), fixture("B", attacks=400)
        for i, row in enumerate(b["rows"][4:]):
            row["phase"] = "small" if i < 100 else "large"
        b["local"][4:6, 1] = -.2
        self.assertTrue(m.target_gate([report(**a), report(**b)])["pass"])

    def test_target_missing_required_annotation_is_not_fabricated_pass(self):
        a, b = fixture("A"), fixture("B")
        for row in b["rows"]:
            row.pop("annotation")
        gate = m.target_gate([report(**a), report(**b)])
        self.assertEqual(gate["status"], "TARGET_COVERAGE_INSUFFICIENT")

    def test_target_annotation_guard_is_not_hidden_by_pool_recall(self):
        a, b = fixture("A", attacks=1000), fixture("B", attacks=1000)
        for i, row in enumerate(b["rows"][4:]):
            row["annotation"] = "rare" if i < 5 else "common"
        b["local"][4, 2] = -.2
        gate = m.target_gate([report(**a), report(**b)])
        self.assertEqual(gate["status"], "TARGET_CONTRACT_NOT_MET")
        self.assertTrue(any("227/annotation/rare" in reason for reason in gate["reasons"]))

    def test_target_device_fpr_must_pass_even_when_pool_fpr_passes(self):
        rows = [dict(label=0, device="small" if i < 10 else "large", activity="n", phase="p")
                for i in range(100)]
        rows += [dict(label=1, device="large", activity="a", phase="p") for _ in range(100)]
        scores = np.full((200, 4), -.2)
        scores[0] = scores[100:] = .2
        a = m.evaluate_target_pool(name="A", rows=rows, weights=np.ones(200),
                                   raw=scores, d0=scores, local=scores, cuts=np.zeros(4))
        self.assertEqual(a["metrics"]["L"]["ensemble"]["fpr"], .01)
        gate = m.target_gate([a, report(**fixture("B"))])
        self.assertEqual(gate["status"], "TARGET_CONTRACT_NOT_MET")
        self.assertTrue(any("small: ensemble device FPR" in reason for reason in gate["reasons"]))


class ExactBoundaryTests(unittest.TestCase):
    def test_target_two_percent_one_pp_and_99_percent_exact_boundaries(self):
        def make(name, pair):
            rows = [dict(label=0, device="d", activity="normal", annotation="normal", phase="p") for _ in range(100)]
            rows += [dict(label=1, device="d", activity="attack", annotation="attack", phase="p") for _ in range(200)]
            den = np.array(list(pair) * 150, dtype=np.int64)
            raw = np.full((300, 4), .2)
            raw[2:100] = -.2
            local = raw.copy()
            local[100:102] = -.2
            return m.evaluate_target_pool(name=name, rows=rows, weights=1./den, denominators=den,
                                          raw=raw, d0=raw, local=local, cuts=np.zeros(4))
        a, b = make("A", (2, 9)), make("B", (2, 6))
        # The unchanged display arithmetic lies just on the wrong side.
        self.assertGreater(a["metrics"]["L"]["ensemble"]["fpr"], .02)
        self.assertGreater(a["protection"]["own"]["ensemble"]["ledger"]["raw_to_local"]["pp"], 1.)
        self.assertLess(b["metrics"]["L"]["ensemble"]["recall"], .99)
        self.assertTrue(m.target_gate([a, b])["pass"])
        self.assertEqual(a["metrics"]["L"]["ensemble"]["exact"]["fpr"], {"numerator": 1, "denominator": 50})
        # Exact fields are ordinary JSON data, never Fraction objects.
        json.dumps(a, allow_nan=False)

    def test_source_twenty_percent_relative_repair_exact_boundary(self):
        reports = []
        for name, branch in (("G0", "1C"), ("G1", "2C_ZERO")):
            rows = [dict(label=0, device=name, activity="normal", phase="p") for _ in range(5)]
            rows += [dict(label=1, device=name, activity="attack", phase="p") for _ in range(100)]
            den = np.full(105, 9, dtype=np.int64)
            raw = np.full((105, 4), .2)
            local = raw.copy()
            local[0] = -.2
            cap = np.zeros_like(raw, bool)
            cap[:5] = True
            exposure = np.zeros_like(raw, bool)
            exposure[5] = True
            reports.append(m.evaluate_source_fold(name=name, rows=rows, weights=1./den, denominators=den,
                raw=raw, d0=raw, local=local, cuts=np.zeros(4), branches=[branch]+["OTHER"]*104,
                normal_cap=cap, exposure=exposure, lambda_value=.25, cal_pass=True))
        self.assertLess(reports[0]["repairs"]["ensemble"]["relative_repair"], .2)
        self.assertTrue(m.source_gate(reports)["pass"])

    def test_five_pp_activity_boundary_and_half_pp_gain_boundary(self):
        data = fixture(attacks=200)
        den = np.full(len(data["rows"]), 15, dtype=np.int64)
        data.update(denominators=den, weights=1./den)
        for i, row in enumerate(data["rows"][4:]):
            row["activity"] = "rare" if i < 20 else "common"
        data["local"][4] = -.2
        out = report(**data)
        event = out["protection"]["own"]["ensemble"]["groups"]["activity"]["rare"]["raw_to_local"]
        self.assertGreater(event["pp"], 5.)
        self.assertEqual(m._comparison(event, "pp", 5.), 0)
        self.assertTrue(m.source_gate([out, report(**fixture("G1"))])["pass"])
        rows = [dict(label=0, device="d", activity="n", phase="p") for _ in range(400)]
        den = np.array([2, 6]*200, dtype=np.int64)
        raw = np.full((400, 4), -.2)
        raw[:2] = .2
        local = np.full_like(raw, -.2)
        out = m.evaluate_population(name="gain", rows=rows, weights=1./den, denominators=den,
                                    raw=raw, d0=raw, local=local, cuts=np.zeros(4))
        gain = out["repairs"]["ensemble"]
        self.assertLess(gain["absolute_gain_pp"], .5)
        self.assertEqual(m._comparison(gain, "absolute_gain_pp", .5), 0)

    def test_exact_denominators_must_match_supplied_original_weights(self):
        data = fixture()
        data["denominators"] = np.full(len(data["rows"]), 2, dtype=np.int64)
        with self.assertRaisesRegex(ValueError, "disagree"):
            report(**data)

    def test_exact_failure_just_above_two_percent_is_not_tolerated(self):
        rows = [dict(label=0, device="d", activity="n", phase="p") for _ in range(51)]
        rows += [dict(label=1, device="d", activity="a", phase="p")]
        den = np.array([50]*50 + [2**62, 1], dtype=np.int64)
        raw = np.full((52, 4), -.2)
        raw[[0, 50, 51]] = .2
        a = m.evaluate_target_pool(name="A", rows=rows, weights=1./den, denominators=den,
                                   raw=raw, d0=raw, local=raw, cuts=np.zeros(4))
        self.assertEqual(a["metrics"]["L"]["ensemble"]["fpr"], .02)
        gate = m.target_gate([a, report(**fixture("B"))])
        self.assertFalse(gate["pass"])
        self.assertTrue(any("pool FPR exceeds 2%" in reason for reason in gate["reasons"]))


if __name__ == "__main__":
    unittest.main()
