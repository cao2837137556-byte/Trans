"""Only generated targets, arrays and weights; never opens experiment data."""
import copy
import hashlib
import json
import tempfile
import unittest
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

import legacy_cic2022_enhancement_train_v1 as m


def generated_targets():
    old = [{"uid": "old_%02d" % i, "label": int(i >= 3), "owner": "A", "planned_role": "OLD_REPLAY"}
           for i in range(5)]
    counts = Counter(r["label"] for r in old)
    for row in old:
        row.update(class_balanced_weight_numerator=1, class_balanced_weight_denominator=2 * counts[row["label"]])
    new = []
    # Unequal capture/stream/target counts expose accidental per-batch means.
    specifications = [("amcrest", 0, 1, [1, 3]), ("amcrest", 0, 2, [2]),
                      ("amcrest", 1, 3, [1, 3]), ("simcam", 0, 4, [1]),
                      ("simcam", 1, 5, [2, 1])]
    cell_captures = Counter((d, label) for d, label, _cap, _sizes in specifications)
    for device, label, cap, sizes in specifications:
        member = hashlib.sha256(("synthetic_%d" % cap).encode()).hexdigest()
        for stream, size in enumerate(sizes):
            for ordinal in range(size):
                denominator = cell_captures[(device, label)] * len(sizes) * size
                new.append({"uid": "new_%02d_%02d_%02d" % (cap, stream, ordinal),
                            "device": device, "label": label, "file_id": cap, "member_sha256": member,
                            "capture_dependency_group": member, "stream": "tcp:%d" % stream,
                            "planned_role": "TRAIN", "candidates_in_stream": size,
                            "candidate_ordinal_0based": ordinal, "frame_number_1based": stream * 10 + ordinal + 1,
                            "captures_in_device_label_cell": cell_captures[(device, label)],
                            "streams_in_capture": len(sizes), "selected_in_stream": size,
                            "conditional_weight_numerator": 1, "conditional_weight_denominator": denominator,
                            "balanced_bce_weight_numerator": 1, "balanced_bce_weight_denominator": 4 * denominator,
                            "evaluation_label_weight_numerator": 1, "evaluation_label_weight_denominator": 2 * denominator})
    return old, sorted(new, key=lambda r: r["uid"])


def generated_state(d=3, h=4):
    rng = np.random.default_rng(93)
    return {"normalizer_mean": rng.normal(0, 0.1, d).astype(np.float64),
            "normalizer_scale": rng.uniform(0.5, 2, d).astype(np.float64),
            "p2__0.weight": rng.normal(0, 0.2, (h, d + 1)).astype(np.float32),
            "p2__0.bias": rng.normal(0.3, 0.1, h).astype(np.float32),
            "p2__3.weight": rng.normal(0, 0.2, (1, h)).astype(np.float32),
            "p2__3.bias": rng.normal(0, 0.1, 1).astype(np.float32)}


class MatchedTrainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m.configure_runtime()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.old, self.new = generated_targets()
        self.state = generated_state()
        rng = np.random.default_rng(77)
        self.old_z = rng.normal(size=(len(self.old), 3)).astype(np.float32)
        self.new_z = rng.normal(size=(len(self.new), 3)).astype(np.float32)
        self.recipe = m.make_synthetic_recipe(self.old, self.new)

    def tearDown(self):
        self.directory.cleanup()

    def test_normalization_uses_float64_before_complete_float32_cast(self):
        state = generated_state(d=1, h=1)
        state["normalizer_mean"][:] = 1e8 - 1
        state["normalizer_scale"][:] = 1
        x = np.asarray([[1e8]], dtype=np.float32)
        normalized = m.normalize_features(x, state, synthetic=True)
        np.testing.assert_array_equal(normalized, np.asarray([[1, 0]], dtype=np.float32))
        self.assertEqual(float(x[0, 0] - np.float32(state["normalizer_mean"][0])), 0.0)

    def test_accumulation_matches_single_full_objective_gradient(self):
        recipe = m.make_synthetic_recipe(self.old, self.new, dropout=0.0)
        plan = m.validate_targets(self.old, self.new, recipe, synthetic=True)
        old_x = torch.from_numpy(m.normalize_features(self.old_z, self.state, synthetic=True))
        new_x = torch.from_numpy(m.normalize_features(self.new_z, self.state, synthetic=True))
        for arm in ("B", "C"):
            with self.subTest(arm=arm):
                accumulated = m.build_model(self.state, 0.0, synthetic=True)
                reference = m.build_model(self.state, 0.0, synthetic=True).train()
                actual = m.accumulate_gradients(accumulated, old_x, new_x, plan, recipe["optimization"], arm)
                zo, zn = reference(old_x).flatten(), reference(new_x).flatten()
                old = (F.binary_cross_entropy_with_logits(zo, torch.from_numpy(plan["old_labels"]), reduction="none") * torch.from_numpy(plan["old_weights"])).sum()
                new = (F.binary_cross_entropy_with_logits(zn, torch.from_numpy(plan["new_labels"]), reduction="none") * torch.from_numpy(plan["new_weights"])).sum()
                ranking = m.rank_loss(zn, plan)
                objective = 0.8 * old + 0.2 * new + recipe["optimization"]["rank_coefficient"][arm] * ranking
                objective.backward()
                self.assertAlmostEqual(actual["total_objective"], float(objective.detach()), places=6)
                for first, second in zip(accumulated.parameters(), reference.parameters()):
                    torch.testing.assert_close(first.grad, second.grad, rtol=3e-5, atol=2e-7)

    def test_rank_matches_independent_scalar_weighted_pairs(self):
        plan = m.validate_targets(self.old, self.new, self.recipe, synthetic=True)
        logits = torch.linspace(-1.2, 1.5, len(self.new), requires_grad=True)
        actual = m.rank_loss(logits, plan)
        expected, count = logits.new_zeros(()), 0
        for i, attack in enumerate(self.new):
            for j, benign in enumerate(self.new):
                if attack["device"] == benign["device"] and attack["label"] == 1 and benign["label"] == 0:
                    qa = 1 / attack["conditional_weight_denominator"]
                    qb = 1 / benign["conditional_weight_denominator"]
                    expected = expected + 0.5 * qa * qb * F.softplus(-(logits[i] - logits[j]))
                    count += 1
        self.assertEqual(count, plan["pair_count"])
        torch.testing.assert_close(actual, expected, rtol=1e-6, atol=1e-7)
        for device in {r["device"] for r in self.new}:
            for label in (0, 1):
                self.assertAlmostEqual(sum(float(plan["conditional_weights"][i]) for i, r in enumerate(self.new) if r["device"] == device and r["label"] == label), 1.0, places=7)

    def test_full_matched_arms_rng_exposure_and_endpoint_isolation(self):
        initial_digest = m.state_digest(self.state)
        original_old, original_new = self.old_z.copy(), self.new_z.copy()
        notifications = []
        def callback(value):
            # Monitoring code consuming RNG must not perturb dropout.
            torch.rand(7)
            notifications.append(value)
        b = m.train_arm(self.state, self.old_z, self.old, self.new_z, self.new, self.recipe,
                        self.root / "B", "B", progress=callback, synthetic=True)
        c = m.train_arm(self.state, self.old_z, self.old, self.new_z, self.new, self.recipe,
                        self.root / "C", "C", synthetic=True)
        self.assertEqual(b["initial_state_digest"], c["initial_state_digest"])
        self.assertEqual(b["initial_state_digest"], initial_digest)
        self.assertEqual(b["first_update_forward_digests"], c["first_update_forward_digests"])
        self.assertEqual(b["initial_dropout_rng_sha256"], c["initial_dropout_rng_sha256"])
        self.assertEqual(b["final_dropout_rng_sha256"], c["final_dropout_rng_sha256"])
        self.assertEqual(b["row_exposures"], 2 * (len(self.old) + len(self.new)))
        self.assertEqual(b["forward_batches"], 2 * (3 + 7))
        self.assertEqual(b["optimizer_updates"], 2)
        self.assertEqual(b["rank_extra_forward_calls"], 0)
        self.assertEqual(m.state_digest(self.state), initial_digest)
        np.testing.assert_array_equal(self.old_z, original_old)
        np.testing.assert_array_equal(self.new_z, original_new)
        self.assertNotEqual(b["final_state_digest"], c["final_state_digest"])
        for arm, record in (("B", b), ("C", c)):
            with np.load(record["checkpoint_path"], allow_pickle=False) as checkpoint:
                self.assertEqual(set(checkpoint.files), set(m.STATE_KEYS))
                for key in ("normalizer_mean", "normalizer_scale"):
                    np.testing.assert_array_equal(checkpoint[key], self.state[key])
            status = json.loads((self.root / arm / "status.json").read_text(encoding="utf-8"))
            self.assertEqual(status["status"], "COMPLETE")
            trace = [json.loads(line) for line in (self.root / arm / "loss_trace.jsonl").read_text().splitlines()]
            self.assertEqual([r["update"] for r in trace], [1, 2])
            self.assertTrue(all(r["measured_at"] == "before_this_update" for r in trace))
        self.assertEqual(notifications[-1]["status"], "COMPLETE")

    def test_fixed_scoring_matches_endpoint_functional_reference(self):
        result = m.score_fixed(self.state, self.new_z, batch_size=3, synthetic=True)
        x = torch.from_numpy(m.normalize_features(self.new_z, self.state, synthetic=True))
        with torch.no_grad():
            hidden = F.relu(F.linear(x, torch.from_numpy(self.state["p2__0.weight"]), torch.from_numpy(self.state["p2__0.bias"])))
            logit = F.linear(hidden, torch.from_numpy(self.state["p2__3.weight"]), torch.from_numpy(self.state["p2__3.bias"])).flatten()
        np.testing.assert_allclose(result["logits"], logit.numpy().astype(np.float64), rtol=1e-6, atol=1e-7)
        np.testing.assert_allclose(result["probabilities"], logit.sigmoid().numpy().astype(np.float64), rtol=1e-6, atol=1e-7)
        np.testing.assert_array_equal(result["hard"], result["probabilities"] >= m.THETA)

    def test_role_weight_uid_and_recipe_changes_fail(self):
        cases = []
        wrong_role = copy.deepcopy(self.new)
        wrong_role[0]["planned_role"] = "CHECK"
        cases.append((self.old, wrong_role, self.recipe, "NEW_ROLE"))
        wrong_weight = copy.deepcopy(self.new)
        wrong_weight[0]["balanced_bce_weight_denominator"] += 4
        cases.append((self.old, wrong_weight, self.recipe, "NEW_EXACT_WEIGHT"))
        wrong_old = copy.deepcopy(self.old)
        wrong_old[0]["class_balanced_weight_denominator"] = 2
        cases.append((wrong_old, self.new, self.recipe, "OLD_CLASS_WEIGHT"))
        cases.append((list(reversed(self.old)), self.new, self.recipe, "TARGET_UID_SORT_OR_DUPLICATE"))
        for old, new, recipe, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(m.Stop, message):
                    m.validate_targets(old, new, recipe, synthetic=True)
        changed = copy.deepcopy(self.recipe)
        changed["optimization"]["lr"] = 1e-3
        with self.assertRaisesRegex(m.Stop, "FROZEN_OPTIMIZATION:lr"):
            m.validate_recipe(changed, self.state, synthetic=True)
        with self.assertRaisesRegex(m.Stop, "REAL_STATE_DIMENSIONS"):
            m.validate_recipe(self.recipe, self.state, synthetic=False)

    def test_nonfinite_stops_and_output_cannot_be_retried(self):
        broken = self.new_z.copy()
        broken[0, 0] = np.nan
        out = self.root / "bad"
        with self.assertRaisesRegex(m.Stop, "FEATURE_SHAPE_FINITE"):
            m.train_arm(self.state, self.old_z, self.old, broken, self.new, self.recipe, out, "B", synthetic=True)
        status = json.loads((out / "status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["status"], "STOP")
        self.assertFalse((out / "checkpoint.npz").exists())
        with self.assertRaisesRegex(m.Stop, "OUTPUT_NOT_EMPTY_ZERO_RETRY"):
            m.train_arm(self.state, self.old_z, self.old, self.new_z, self.new, self.recipe, out, "B", synthetic=True)

    def test_build_model_does_not_mutate_input_or_global_rng(self):
        digest = m.state_digest(self.state)
        before = torch.get_rng_state().clone()
        first = m.build_model(self.state, synthetic=True)
        second = m.build_model(self.state, synthetic=True)
        self.assertTrue(torch.equal(before, torch.get_rng_state()))
        with torch.no_grad():
            first[0].weight.add_(1)
        self.assertFalse(torch.equal(first[0].weight, second[0].weight))
        self.assertEqual(m.state_digest(self.state), digest)

    def test_generated_full_width_fixture_uses_production_head_shape(self):
        state = generated_state(d=768, h=128)
        rng = np.random.default_rng(942)
        old = rng.normal(size=(len(self.old), 768)).astype(np.float32)
        new = rng.normal(size=(len(self.new), 768)).astype(np.float32)
        recipe = m.make_synthetic_recipe(self.old, self.new, input_width=768, hidden_width=128)
        result = m.train_arm(state, old, self.old, new, self.new, recipe, self.root / "full_width", "B", synthetic=True)
        self.assertEqual(result["optimizer_updates"], 2)
        with np.load(result["checkpoint_path"], allow_pickle=False) as saved:
            self.assertEqual(saved["p2__0.weight"].shape, (128, 769))
            self.assertEqual(saved["p2__3.weight"].shape, (1, 128))
        changed = copy.deepcopy(recipe)
        changed["optimization"]["full_batch_updates_per_arm"] = 200
        with self.assertRaisesRegex(m.Stop, "SYNTHETIC_BUDGET"):
            m.validate_recipe(changed, state, synthetic=True)


if __name__ == "__main__":
    unittest.main()
