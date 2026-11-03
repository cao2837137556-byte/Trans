"""Synthetic source arithmetic and attack-scenario regression tests only."""
import unittest
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from lg.source import paired_scenarios, score_columns, select_source_lambda, source_ensemble
from lg import source


class SourceTests(unittest.TestCase):
    def test_source_ensemble_preserves_sequential_accumulator(self):
        values = np.array([[1e16, 1., -1e16], [3., 6., 9.]], dtype=np.float64)
        expected = np.zeros(2)
        for column in range(3):
            expected += values[:, column]
        expected /= 3
        np.testing.assert_array_equal(source_ensemble(values), expected)
        self.assertEqual(source_ensemble(values)[1], 6.)

    def test_correction_is_from_raw_and_zero_support_is_exact(self):
        raw = np.array([[1., 2., 3.], [4., 5., 6.]], dtype=np.float32)
        corrected = score_columns(raw, np.array([0., 1.]), [2., 3., 4.], .25)
        np.testing.assert_array_equal(corrected[0, :3], raw[0])
        np.testing.assert_array_equal(corrected[1, :3], [3.5, 4.25, 5.])

    def test_lambda_selects_largest_zero_withdrawal_and_ties_are_normal(self):
        raw = np.array([[.1, .1, .1]], dtype=np.float32)
        result = select_source_lambda(raw, np.array([[1.]]), np.array([[True]]), [1., 1., 1.], np.zeros(4))
        # float32 0.1 is slightly above 0.1; the original float64 conversion is
        # deliberately preserved, so lambda=.1 does not withdraw this TP.
        self.assertEqual(result["selected_lambda"], .1)
        raw = np.array([[.25, .25, .25]], dtype=np.float64)
        result = select_source_lambda(raw, np.array([[1.]]), np.array([[True]]), [1., 1., 1.], np.zeros(4))
        self.assertEqual(result["selected_lambda"], .1)
        self.assertFalse(result["candidates"][-1]["passes"])

    def test_new_one_component_attack_is_not_masked_by_d0_eligibility(self):
        matrix = {"d0": np.array([[0.]]), "local": np.array([[1.]]),
                  "eligible_d0": np.array([[False]]), "eligible_local": np.array([[True]]),
                  "branch": np.array([["ONE_COMPONENT"]])}
        result = paired_scenarios(np.array([[.1, .1, .1]]), matrix, [1., 1., 1.], .25, np.zeros(4))
        self.assertTrue(np.all(result["d0"] > 0))
        self.assertTrue(np.all(result["local"] <= 0))
        self.assertTrue(result["eligible_union"].all())
        self.assertTrue(result["exposure_branches"]["1C"].all())
        self.assertTrue(np.all(result["safety_branch_scores"]["1C"]["local"] <= 0))
        self.assertTrue(np.all(result["safety_branch_scores"]["2C_ZERO"]["local"] > 0))

    def test_union_counts_each_uid_once_with_multiple_donors(self):
        matrix = {"d0": np.array([[.2, .3]]), "local": np.array([[.8, 1.]]),
                  "eligible_d0": np.array([[True, True]]), "eligible_local": np.array([[True, True]]),
                  "branch": np.array([["TWO_COMPONENT_POSITIVE", "TWO_COMPONENT_POSITIVE"]])}
        result = paired_scenarios(np.array([[.2, .2, .2]]), matrix, [1., 1., 1.], .25, np.zeros(4))
        self.assertEqual(result["exposure"].shape, (1, 4))
        self.assertEqual(result["exposure"].sum(), 4)
        np.testing.assert_array_equal(result["safety_local"], result["local"][:, 1])

    def test_invalid_old_mask_cannot_hide_positive_support(self):
        with self.assertRaises((ValueError, RuntimeError)):
            select_source_lambda(np.ones((1, 3)), np.ones((1, 1)), np.zeros((1, 1), bool), np.ones(3), np.zeros(4))

    def test_full_source_wiring_only_uses_synthetic_assets(self):
        """Exercise stage ordering, fold FIT extraction and final PASS handoff.

        Models, geometry and metadata are small in-memory fakes.  No historical
        scientific file, real feature, saved model or network endpoint is read.
        """
        rows = []
        for i in range(8):
            rows.append(dict(uid="q" + str(i), device="first" if i < 4 else "second",
                partition="LEARN", protocol=6, label=i % 2, fit_role="FIT" if i % 4 < 2 else "CAL",
                component_id="query" + str(i), activity="normal" if i % 2 == 0 else "attack"))
        indices = {"G0_FIT": np.array([0, 1]), "G0_CAL": np.array([2, 3]), "G0_HELD": np.array([4, 5, 6, 7]),
                   "G1_FIT": np.array([4, 5]), "G1_CAL": np.array([6, 7]), "G1_HELD": np.array([0, 1, 2, 3])}
        values = np.tile(np.array([.6, .9, .6, .9], dtype=np.float32), 2)[:, None]
        p1 = {"folds": {}}
        for fold in ("G0", "G1"):
            p1["folds"][fold] = {"scores": {}, "cuts": {s: .5 for s in source.SUFFIXES}}
            for role in ("CAL", "HELD"):
                ix = indices[fold + "_" + role]
                p1["folds"][fold][role] = {"denominators": np.ones(len(ix), dtype=np.int64),
                                           "phases": np.repeat("TCP_OTHER", len(ix))}
            for seed in source.SEEDS:
                p1["folds"][fold]["scores"][str(seed)] = {
                    role: values[indices[fold + "_" + role], 0] for role in ("CAL", "HELD")}
        reference_rows = [dict(uid="r" + str(i), device="first" if i < 2 else "second",
                               partition="LEARN", protocol=6, component_id="reference" + str(i)) for i in range(4)]
        arrays = dict(uid=np.asarray([r["uid"] for r in reference_rows]),
                      e3=np.ones((4, 768), dtype=np.float32), q14=np.zeros((4, 14), dtype=np.float32))

        class FakeBank:
            def __init__(self, rr, *args, **kwargs):
                self.rows, self.has_2c_expansion, self.scale_summary = rr, True, [{"synthetic": True}]
            def scale_arrays(self):
                return dict(uid=np.asarray([row["uid"] for row in self.rows]), ready=np.ones(len(self.rows), bool),
                            rho_z=np.ones(len(self.rows)), rho_q=np.ones(len(self.rows)),
                            neighbor_uids=np.full((len(self.rows), 5), "", dtype="<U8"))
            def own(self, rr, *args, **kwargs):
                n = len(rr)
                return dict(d0=np.repeat(.2, n), local=np.repeat(.4, n), eligible_d0=np.ones(n, bool),
                            eligible_local=np.ones(n, bool), branch=np.repeat("TWO_COMPONENT_POSITIVE", n))
            def matrix(self, rr, *args, **kwargs):
                out = self.own(rr)
                out = {key: value[:, None] for key, value in out.items()}
                out["roster"] = [dict(partition="LEARN", device=self.rows[0]["device"], protocol=6)]
                return out

        class FakeTraining:
            def load_model(self, *args):
                return None
            def load_normalizer(self, *args):
                return dict(e3_mean=np.zeros(768), e3_scale=np.ones(768))
            def scores(self, model, values, q, mi, ix, normalizer, arm, progress=None):
                progress(dict(completed=len(ix)))
                return values[ix, 0].copy()

        class Runtime:
            def __init__(self, path):
                self.path, self.forwards, self.pairs = path, 0, 0
            def checkpoint(self, *args, **kwargs):
                pass
            def add_forwards(self, n):
                self.forwards += n
            def add_pairs(self, n):
                self.pairs += n
            def write_json(self, name, value):
                path = self.path / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value), encoding="utf-8")

        legacy = dict(source_training=FakeTraining(),
            core=SimpleNamespace(fit_geometry=lambda *a, **kw: {"synthetic": True},
                                 fit_scales=lambda *a, **kw: {"scales": [1., 1., 1.]}),
            source_data=SimpleNamespace(GROUPS={"G0": {"first"}, "G1": {"second"}}),
            dense_source=SimpleNamespace(validate_bank=lambda *a: None),
            indexed=SimpleNamespace(IndexedMatrix=lambda array, ix, columns=None: array[ix] if columns is None else array[ix, columns]))
        captured = []
        def evaluate(**kwargs):
            captured.append(kwargs)
            return {"name": kwargs["name"], "cal_pass": kwargs["cal_pass"]}
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            output = root / "output"
            output.mkdir()
            for relative in (source.DENSE + "/bank.npz", source.OLD_REFS + "/SOURCE_REFS.npz"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(path, **arrays)
            assets = dict(root=root, rows=rows, indices=indices, p1=p1, seals={}, values=values,
                          q=np.zeros((8, 14), np.float32), dense_rows=reference_rows,
                          old_rows=reference_rows, plan={})
            runtime = Runtime(output)
            with patch("lg.legacy.load_legacy", return_value=legacy), patch("lg.source._load_assets", return_value=assets), \
                 patch("lg.geometry.DualBank", FakeBank), patch("lg.metrics.evaluate_source_fold", side_effect=evaluate), \
                 patch("lg.metrics.source_gate", return_value={"pass": True, "status": "PASS"}):
                result = source.run_source(root, output, runtime)
            self.assertTrue(result["source_pass"])
            self.assertEqual(result["scientific_status"], "SOURCE_SIGNAL_PASS")
            self.assertEqual(runtime.forwards, 48)
            self.assertEqual(runtime.pairs, 0)
            self.assertEqual([item["name"] for item in captured], ["G0", "G1"])
            self.assertEqual([r["device"] for r in captured[0]["rows"]], ["second", "second"])
            self.assertEqual([r["device"] for r in captured[1]["rows"]], ["first", "first"])
            self.assertTrue((output / "G1/S/ATTACK_DONORS.npz").exists())


if __name__ == "__main__":
    unittest.main()
