"""Synthetic numerical-core regressions; not the full real-run acceptance suite."""
import copy
import io
import math
import tempfile
import unittest
import zipfile
from pathlib import Path

import numpy as np
import torch

import issue27frontend_f5_unified_student_v1 as m


class CoreContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m.configure_runtime()

    def setUp(self):
        m.reseed()

    def test_01_model_identity_seed_and_aux_removal(self):
        a = m.Student()
        self.assertEqual(sum(p.numel() for p in a.parameters()), 94748)
        self.assertEqual(sum(v.numel() for v in a.inference_state().values()), 91265)
        h = m.tensor_hash(a.state_dict())
        m.reseed()
        self.assertEqual(h, m.tensor_hash(m.Student().state_dict()))

    def test_02_packed_individual_restore_order(self):
        model = m.Student().eval()
        seqs = [torch.rand(n, 131) for n in (3, 8, 8, 1)]
        keys = ["z", "y", "a", "k"]
        with torch.no_grad():
            batched, _, _ = model(seqs, keys)
            for i, seq in enumerate(seqs):
                individual, _, _ = model([seq], [keys[i]])
                torch.testing.assert_close(batched[i], individual[0], atol=1e-6, rtol=1e-6)
                self.assertTrue(torch.equal(batched[i] >= 0, individual[0] >= 0))

    def test_03_causality_future_and_context_reset(self):
        model = m.Student().eval()
        x = torch.rand(9, 131)
        changed = x.clone()
        changed[4:] = torch.rand(5, 131)
        with torch.no_grad():
            a = model([x], ["a"])[0][0]
            b = model([changed], ["a"])[0][0]
            prefix = model([x[:4]], ["a"])[0][0]
            model([torch.ones(8, 131)], ["unrelated"])
            again = model([x], ["a"])[0][0]
        torch.testing.assert_close(a[:4], b[:4], atol=1e-6, rtol=1e-6)
        torch.testing.assert_close(a[:4], prefix, atol=1e-6, rtol=1e-6)
        self.assertTrue(torch.equal(a, again))

    def test_04_invalid_feature_shape_and_nonfinite(self):
        model = m.Student()
        for x in (torch.zeros(2, 130), torch.zeros(257, 131), torch.zeros(0, 131),
                  torch.full((2, 131), float("nan")), torch.zeros(2, 131, dtype=torch.float64)):
            with self.assertRaises(m.ContractError):
                model([x], ["a"])

    def test_05_metadata_not_an_input(self):
        model = m.Student().eval()
        c = m.synthetic_contexts(4, 3)
        with torch.no_grad():
            a = model([x.x for x in c], [x.key for x in c])[0]
            for x in c:
                x.device = "changed-device-IP-MAC"
            b = model([x.x for x in c], [x.key for x in c])[0]
        self.assertTrue(all(torch.equal(x, y) for x, y in zip(a, b)))

    def test_06_synthetic_fixture_f4_roundtrip(self):
        # The F4 module has no model/runtime side effects; only its pure codec is used.
        import issue27frontend_f4_fieldwise_input_v1 as f4
        for c in m.synthetic_contexts(4, 3):
            signature = f4.decode_event(c.x[0].numpy())
            np.testing.assert_array_equal(f4.encode_event(f4.parse_l1(signature)), c.x[0].numpy())

    def test_07_group_counts_context_weighting(self):
        contexts = m.synthetic_contexts(4, 3)
        counts = m.group_counts(contexts)
        self.assertEqual(counts, {"A1": 1, "A0": 1, "B1": 1, "B0": 1, "T1": 1, "T0": 1, "semantic": 4})
        c = contexts[0]
        c.targets.append(m.Target("mixed", 0, "B", 1))
        self.assertEqual(m.group_counts(contexts)["B1"], 2)
        c.targets.append(c.targets[0])
        with self.assertRaises(m.ContractError):
            m.group_counts(contexts)

    def test_08_hand_computed_zero_logits(self):
        contexts = m.synthetic_contexts(4, 2)
        q = [torch.zeros(2, requires_grad=True) for _ in contexts]
        sem = [torch.zeros(2, 27, requires_grad=True) for _ in contexts]
        total, p = m.batch_loss(contexts, q, sem, 4, m.group_counts(contexts))
        for key, expected in (("label", 1), ("teacher", .5), ("attack_mean", .5),
                              ("attack_batch_worst", .5), ("semantic", 1)):
            self.assertAlmostEqual(float(p[key].detach()), expected, places=6)
        self.assertAlmostEqual(float(total.detach()), 2.6, places=6)

    def test_09_global_ng_not_batch_rebalance(self):
        contexts = m.synthetic_contexts(4, 2)
        q = [torch.zeros(2, requires_grad=True)]
        sem = [torch.zeros(2, 27, requires_grad=True)]
        _, p = m.batch_loss(contexts[:1], q, sem, 4, m.group_counts(contexts))
        self.assertAlmostEqual(float(p["label"].detach()), 1, places=6)  # 4/(1*1) divided by 4
        self.assertAlmostEqual(float(p["teacher"].detach()), 1, places=6)
        self.assertEqual(float(p["attack_mean"].detach()), 0)
        self.assertEqual(float(p["attack_batch_worst"].detach()), 0)
        counts = m.group_counts(contexts)
        counts["B1"] = 0
        with self.assertRaises(m.ContractError):
            m.batch_loss(contexts[:1], q, sem, 4, counts)

    def test_10_attack_tied_max_gradient(self):
        q = torch.zeros(2, requires_grad=True)
        v = m.huber_nonnegative(torch.relu(1 - q)).amax()
        v.backward()
        torch.testing.assert_close(q.grad, torch.tensor([-.5, -.5]), rtol=0, atol=0)

    def test_11_teacher_wrong_and_B_no_strength(self):
        c = m.synthetic_contexts(4, 2)[0]
        c.targets = [m.Target("wrong", 0, "A", 0, False, None)]
        terms, _ = m.context_terms(c, torch.zeros(2), torch.zeros(2, 27))
        self.assertIn("A0", terms)
        self.assertNotIn("T0", terms)
        c.targets = [m.Target("illegal", 0, "B", 0, True, 2)]
        with self.assertRaises(m.ContractError):
            c.validate()

    def test_12_semantic_terminal_prefix_and_singleton(self):
        c = m.synthetic_contexts(4, 5)[0]
        c.targets = [m.Target("p", 1, "A", 0, True, 2)]
        q = torch.zeros(5)
        sem = torch.zeros(5, 27, requires_grad=True)
        terms, _ = m.context_terms(c, q, sem)
        terms["semantic"].backward()
        self.assertTrue(bool((sem.grad[1:] == 0).all()))
        c.targets = [m.Target("s", 0, "A", 0, True, 2)]
        terms, _ = m.context_terms(c, q, sem)
        self.assertNotIn("semantic", terms)

    def test_13_validation_and_kill_gradient_guard(self):
        model = m.Student()
        optimizer = m.optimizer_for(model)
        contexts = m.synthetic_contexts(4, 2)
        counts = m.group_counts(contexts)
        for split in ("val", "kill"):
            contexts[0].split = split
            with self.assertRaises(m.ContractError):
                m.train_batch(model, optimizer, contexts, 4, counts)

    def test_14_teacher_boundary_and_saturation(self):
        state = {"normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
                 "p2__0.weight": np.zeros((128, 769), np.float32), "p2__0.bias": np.zeros(128, np.float32),
                 "p2__3.weight": np.zeros((1, 128), np.float32), "p2__3.bias": np.array([100], np.float32)}
        raw, scores, strengths = m.canonical_teacher(np.zeros((2, 768), np.float32), state, [1, 0], [True, False])
        self.assertEqual(raw.tolist(), [100, 100])
        self.assertEqual(scores.tolist(), [1, 1])
        self.assertEqual(strengths, [6, None])
        state["p2__3.bias"][0] = np.float32(m.Z0_OLD)
        raw32 = torch.tensor([np.float32(m.Z0_OLD)])
        boundary_hard = bool(raw32.sigmoid().numpy().astype(np.float64)[0] >= m.THETA_OLD)
        m.canonical_teacher(np.zeros((1, 768), np.float32), state, [int(boundary_hard)], [True])
        with self.assertRaises(m.ContractError):
            m.canonical_teacher(np.zeros((1, 768), np.float32), state, [int(boundary_hard)], [False])

    def test_15_selective_npz_opaque_forbidden_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fixture.npz"
            data = np.full((7, 768), np.nan, np.float32)
            data[2], data[5] = 2, 5
            np.savez_compressed(path, representation=data)
            audit = {}
            out = m.selective_npy_rows(path, "representation.npy", [2, 5], (7, 768), audit)
            self.assertEqual(out[:, 0].tolist(), [2, 5])
            self.assertEqual(audit["numeric_rows_opened"], 2)
            self.assertEqual(audit["opaque_bytes_streamed"], 7 * 768 * 4)
            with self.assertRaises(m.ContractError):
                m.selective_npy_rows(path, "representation.npy", [1], (7, 768), {})
            with self.assertRaises(m.ContractError):
                m.selective_npy_rows(path, "representation.npy", [5, 2], (7, 768), {})

    def test_16_hard_threshold_zero(self):
        model = m.Student()
        with torch.no_grad():
            for p in model.parameters():
                p.zero_()
        contexts = m.synthetic_contexts(4, 2)
        result = m.evaluate(model, contexts)
        self.assertTrue(all(row["hard"] for row in result["predictions"]))
        self.assertEqual(len(result["violations"]), 2)  # A benign only; B benign not protected.
        self.assertFalse(result["eligible"])

    def test_17_selection_patience_and_no_eligible(self):
        selection = m.Selection()
        for epoch in range(1, 21):
            improved, stop = selection.update(epoch, False, 1)
            self.assertFalse(improved)
            self.assertEqual(stop, epoch == 20)
        self.assertIsNone(selection.best_epoch)
        selection = m.Selection()
        self.assertEqual(selection.update(1, True, 0.0001), (True, False))
        self.assertEqual(selection.update(2, True, 0.0), (True, False))
        self.assertEqual(selection.update(3, True, 0.0), (False, False))
        self.assertEqual(selection.best_epoch, 2)
        with self.assertRaises(m.ContractError):
            selection.update(5, True, 0)

    def test_18_gain_context_all_targets_and_ceil(self):
        rows = []
        for i in range(11):
            rows.append({"split": "val", "owner": "B", "label": 0, "device": "small",
                         "context": str(i), "hard": i >= 2})
        result = m.benign_gain(rows)["small"]
        self.assertEqual((result["target_min"], result["context_min"]), (2, 2))
        self.assertTrue(result["pass"])
        rows.append({**rows[0], "hard": True})
        self.assertFalse(m.benign_gain(rows)["small"]["pass"])

    def test_19_terminal_precedence_and_no_kill_early(self):
        self.assertEqual(m.terminal_status(True, False, False, None), "F5_NO_ELIGIBLE_CHECKPOINT")
        self.assertEqual(m.terminal_status(True, True, False, None), "F5_NO_MATERIAL_BENIGN_GAIN")
        self.assertEqual(m.terminal_status(True, True, True, [True] * 4 + [False]), "F5_KILL_ONLY_ATTACK_FAILURE")
        with self.assertRaises(m.ContractError):
            m.terminal_status(False, True, True, [True] * 5)
        with self.assertRaises(m.ContractError):
            m.terminal_status(True, False, False, [True] * 5)

    def test_20_resume_exact_tensor_optimizer_rng_ledger(self):
        contexts = m.synthetic_contexts(4, 3)
        counts = m.group_counts(contexts)
        model = m.Student()
        optimizer = m.optimizer_for(model)
        ledger = [m.train_batch(model, optimizer, contexts, 4, counts)]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "resume.pt"
            m.save_checkpoint(path, model, optimizer, {"cursor": 1, "ledger": ledger}, {"protocol": m.PROTOCOL_SHA})
            expected_row = m.train_batch(model, optimizer, contexts, 4, counts)
            expected_model = m.tensor_hash(model.state_dict())
            expected_optimizer = copy.deepcopy(optimizer.state_dict())
            expected_rng = torch.get_rng_state().clone()
            other = m.Student()
            other_optimizer = m.optimizer_for(other)
            progress = m.load_checkpoint(path, other, other_optimizer, {"protocol": m.PROTOCOL_SHA})
            actual_row = m.train_batch(other, other_optimizer, contexts, 4, counts)
            self.assertEqual(progress, {"cursor": 1, "ledger": ledger})
            self.assertEqual(expected_row, actual_row)
            self.assertEqual(expected_model, m.tensor_hash(other.state_dict()))
            self.assertTrue(torch.equal(expected_rng, torch.get_rng_state()))
            for key, state in expected_optimizer["state"].items():
                for name, value in state.items():
                    actual = other_optimizer.state_dict()["state"][key][name]
                    self.assertTrue(torch.equal(value, actual) if torch.is_tensor(value) else value == actual)
            path.write_bytes(b"corrupt synthetic fixture")
            with self.assertRaises(m.ContractError):
                m.load_checkpoint(path, other, other_optimizer, {"protocol": m.PROTOCOL_SHA})

    def test_21_time_recovery_and_resource_formula(self):
        self.assertEqual(m.recover_elapsed({"elapsed": 5, "last_utc": 100, "open_batch_utc": 100}, 125), 30)
        self.assertEqual(m.recover_elapsed({"elapsed": 5, "last_utc": 100}, 125), 5)
        with self.assertRaises(m.ContractError):
            m.recover_elapsed({"elapsed": 5, "last_utc": 100}, 99)
        expected = 100 * (156 * .1 + 292 * .02)
        self.assertAlmostEqual(m.resource_projection(.1, .02)["projected_seconds"], expected)
        self.assertFalse(m.resource_projection(10, 10)["pass"])
        self.assertTrue(m.resource_projection(0, 0)["pass"])

    def test_22_epoch_order_partial_and_atomic(self):
        keys = ["k%d" % i for i in range(35)]
        first = m.epoch_order(keys, 1)
        self.assertEqual(first, m.epoch_order(keys[::-1], 1))
        self.assertEqual(set(first), set(keys))
        self.assertEqual(len(first[32:]), 3)
        self.assertNotEqual(first, m.epoch_order(keys, 2))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "receipt.json"
            m.atomic_json(path, {"phase": "synthetic"})
            self.assertEqual(list(Path(temp).iterdir()), [path])
            with self.assertRaises(ValueError):
                m.atomic_json(path, {"bad": float("nan")})
            self.assertIn("synthetic", path.read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
