"""Synthetic production-controller contracts. Never open real experiment arrays."""
import ast
import copy
import dataclasses
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch
import numpy as np

import issue27frontend_f5_unified_student_v1 as core
import issue27frontend_f5_unified_student_runner_v1 as r


def fixture_dataset():
    train = core.synthetic_contexts(4, 2)
    val = copy.deepcopy(train)
    for c in val:
        c.key = "val-" + c.key
        c.split = "val"
        c.targets = [dataclasses.replace(t, uid="val-" + t.uid, strength=None) for t in c.targets]
    return {"train": train, "val": val}


def fixture_identities(contexts):
    core.reseed()
    initial = core.Student()
    return {"initial_tensor_sha256": core.tensor_hash(initial.state_dict()),
            "group_counts": core.group_counts(contexts["train"]), "synthetic_only": True}


class ControllerContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        core.configure_runtime()

    def setUp(self):
        core.reseed()

    def test_01_protocol_nineteen_pins_no_arrays(self):
        pins = r.protocol_pins()
        self.assertEqual(len(pins), 19)
        self.assertIn(r.P4 + "/f4_parent_features.f32le", pins)
        self.assertIn(r.PT + "/ckda_d1_probe_state.npz", pins)

    def test_02_real_cli_requires_stage_token_before_runtime(self):
        with patch("sys.argv", ["runner", "--stage", "train", "--authorization", "no"]), patch.object(core, "configure_runtime") as runtime:
            with self.assertRaises(core.ContractError):
                r.main()
            runtime.assert_not_called()

    def test_03_model_and_optimizer_no_real_path_at_import(self):
        source = Path(r.__file__).read_text()
        tree = ast.parse(source)
        calls = [node for statement in tree.body if isinstance(statement, ast.Expr)
                 for node in ast.walk(statement) if isinstance(node, ast.Call)]
        self.assertEqual(calls, [])
        self.assertNotIn("--max-epochs", source)
        self.assertNotIn("--learning-rate", source)

    def test_04_metadata_source_split_and_offset_conservation(self):
        index, targets = [], []
        expected = {"train": {}, "val": {}}
        for i, (split, owner, label, kind, cat) in enumerate([
            ("train", "A", 1, "attack_hard", "A1C"), ("internal_val", "B", 0, "none", "B0N")]):
            key = str(i)
            index.append({"context_key": key, "nested_split": split, "source_group": key, "event_offset": str(i*2), "event_count": "2"})
            targets.append({"uid": key, "context_key": key, "nested_split": split, "source_group": key,
                            "event_index": "1", "prefix_events": "2", "feature_width": "131", "finite": "true", "roundtrip_exact": "true",
                            "owner": owner, "label": str(label), "teacher_kind": kind})
            expected["train" if split == "train" else "val"][cat] = 1
        sources = {"train": {"0"}, "val": {"1"}}
        contexts, census = r.validate_metadata(index, targets, sources, expected, {"train": 1, "val": 1}, 4)
        self.assertEqual(census, expected)
        for field, value in (("context_key", "0"), ("source_group", "0"), ("nested_split", "train")):
            changed = copy.deepcopy(targets)
            changed[1][field] = value
            with self.assertRaises(core.ContractError):
                r.validate_metadata(index, changed, sources, expected, {"train": 1, "val": 1}, 4)
        index[1]["event_offset"] = "1"
        with self.assertRaises(core.ContractError):
            r.validate_metadata(index, targets, sources, expected, {"train": 1, "val": 1}, 4)

    def test_05_teacher_whitelist_before_any_npz_open(self):
        contexts = fixture_dataset()["train"]
        with tempfile.TemporaryDirectory() as temp, patch.object(r.np, "load") as loader:
            with self.assertRaises(core.ContractError):
                r.teacher_materialize(Path(temp), contexts, {}, Path(temp) / "teacher.csv", r.fresh_audit())
            loader.assert_not_called()

    def test_06_teacher_attach_exact_uid_and_split(self):
        contexts = fixture_dataset()
        strengths = {t.uid: t.strength for c in contexts["train"] for t in c.targets if t.owner == "A"}
        r.attach_teacher(contexts["train"], strengths)
        with self.assertRaises(core.ContractError):
            r.attach_teacher(contexts["train"], {**strengths, "select-uid": 1.0})
        val_strengths = {t.uid: 2.0 for c in contexts["val"] for t in c.targets if t.owner == "A"}
        with self.assertRaises(core.ContractError):
            r.attach_teacher(contexts["val"], val_strengths)

    def test_07_budget_open_batch_charged_and_caps(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            clock = [100.0]
            mono = [5.0]
            b = r.Budget(out / "time.json", 10, out, lambda: 0, lambda: clock[0], lambda: mono[0])
            b.begin()
            mono[0] += 3
            clock[0] += 3
            b.end()
            self.assertEqual(b.elapsed, 3)
            b.begin()
            clock[0] += 5
            recovered = r.Budget(out / "time.json", 10, out, lambda: 0, lambda: clock[0], lambda: mono[0])
            self.assertEqual(recovered.elapsed, 8)
            recovered.begin()
            mono[0] += 3
            clock[0] += 3
            with self.assertRaises(r.ResourceStop):
                recovered.end()

    def test_08_ram_guard_without_reading_experiments(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(r.ResourceStop):
                r.Budget(Path(temp)/"time.json", 10, Path(temp), lambda: 8*1024**3+1)

    def test_09_end_to_end_synthetic_no_eligible_no_kill(self):
        contexts = fixture_dataset()
        identities = fixture_identities(contexts)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            b = r.Budget(out/"training"/"time.json", 120, out, lambda: 0)
            with patch.object(r, "load_kill") as kill:
                result = r.train_trajectory(contexts, out, identities, b, r.fresh_audit(), max_epochs=2)
            self.assertEqual(result["status"], "F5_NO_ELIGIBLE_CHECKPOINT")
            kill.assert_not_called()
            self.assertFalse((out/"training"/"selected_seal.json").exists())
            epochs = r.read_json(out/"training"/"epoch_ledger.json")
            self.assertEqual(len(epochs), 2)
            self.assertIn("gate_counts", epochs[0])
            self.assertIn("same_checkpoint_training_losses", epochs[0])
            with self.assertRaises(core.ContractError):
                r.train_trajectory(contexts, out, identities, b, r.fresh_audit(), max_epochs=2)

    def test_10_controller_crash_recompute_same_trajectory(self):
        contexts = fixture_dataset()
        identities = fixture_identities(contexts)
        with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
            a, b = Path(t1), Path(t2)
            ba = r.Budget(a/"training"/"time.json", 120, a, lambda: 0)
            bb = r.Budget(b/"training"/"time.json", 120, b, lambda: 0)
            full = r.train_trajectory(contexts, a, identities, ba, r.fresh_audit(), max_epochs=2)
            audit = r.fresh_audit()
            partial = r.train_trajectory(contexts, b, identities, bb, audit, max_epochs=2, stop_after_steps=1)
            self.assertEqual(partial["status"], "SYNTHETIC_INTERRUPTED")
            elapsed_before = bb.elapsed
            resumed = r.train_trajectory(contexts, b, identities, bb, audit, max_epochs=2)
            self.assertEqual(full, resumed)
            self.assertGreater(bb.elapsed, elapsed_before)
            ma, mb = core.Student(), core.Student()
            oa, ob = core.optimizer_for(ma), core.optimizer_for(mb)
            pa = core.load_checkpoint(a/"training"/"resume.pt", ma, oa, identities)
            pb = core.load_checkpoint(b/"training"/"resume.pt", mb, ob, identities)
            self.assertEqual(pa, pb)
            self.assertEqual(core.tensor_hash(ma.state_dict()), core.tensor_hash(mb.state_dict()))
            self.assertEqual(audit["real_optimizer_steps"], 3)  # physical synthetic steps include one recomputation.

    def test_11_selected_checkpoint_seal_identity_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path, sealpath = Path(temp)/"best.pt", Path(temp)/"seal.json"
            core.atomic_bytes(path, b"synthetic-checkpoint")
            seal = r.seal_checkpoint(path, sealpath)
            r.require_seal(path, seal)
            with self.assertRaises(core.ContractError):
                r.seal_checkpoint(path, sealpath)
            core.atomic_bytes(path, b"different-checkpoint")
            with self.assertRaises(core.ContractError):
                r.require_seal(path, seal)

    def test_12_exact_B_device_family_denominators(self):
        good = {k: {"targets": n, "contexts": c} for k, (n, c) in r.B_COUNTS.items()}
        r.assert_b_denominators(good)
        self.assertEqual(sum((g["targets"] + 9)//10 for g in good.values()), 373)
        self.assertEqual([((n+9)//10, (c+9)//10) for n,c in r.B_COUNTS.values()], [(34,29),(23,5),(316,300)])
        wrong = copy.deepcopy(good)
        wrong["ton-iot-external"]["targets"] -= 1
        with self.assertRaises(core.ContractError):
            r.assert_b_denominators(wrong)

    def test_13_gate_counts_wrong_benign_not_protected(self):
        rows = [{"split":"val", "owner":"A", "label":0, "protected":False, "hard":True, "logit":3},
                {"split":"val", "owner":"A", "label":1, "protected":True, "hard":False, "logit":-2}]
        result = r.per_gate_counts(rows)
        self.assertEqual(result["val:A0:unprotected"]["flips"], 0)
        self.assertEqual(result["val:A1:protected"]["flips"], 1)
        self.assertEqual(result["val:A1:protected"]["min_signed_margin"], -2)

    def test_14_whole_corpus_loss_not_inflight_average(self):
        model = core.Student()
        with torch.no_grad():
            for p in model.parameters():
                p.zero_()
        contexts = fixture_dataset()["train"]
        result = r.full_training_loss(model, contexts, core.group_counts(contexts))
        for key, value in {"label":1, "teacher":.5, "attack_mean":.5, "attack_whole_corpus_worst":.5, "semantic":1, "total_diagnostic":2.6}.items():
            self.assertAlmostEqual(result[key], value, places=6)

    def test_15_no_full_parent_teacher_on_evaluation(self):
        import inspect
        source = inspect.getsource(r.run_evaluate)
        self.assertIn("with_teacher=False", source)
        self.assertLess(source.index("assert_b_denominators(gain)"), source.index("load_kill(root, audit)"))
        self.assertLess(source.index("require_seal(checkpoint, seal)"), source.index("load_kill(root, audit)"))
        self.assertIn('not marker.exists()', inspect.getsource(r.guarded_kill))

    def test_16_manifest_and_conservative_claim_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            core.atomic_json(out/"record.json", {"synthetic": True})
            r.write_manifest(out)
            line = (out/"SHA256SUMS").read_text().strip()
            self.assertEqual(line, core.sha_file(out/"record.json") + "  record.json")
        self.assertFalse(r.CLAIMS["deployment_authorized"])
        self.assertFalse(r.CLAIMS["ce_pass"])
        self.assertFalse(r.CLAIMS["positive_general_inheritance_evidence"])

    def test_17_no_gain_never_calls_kill_loader(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(r, "load_kill") as loader:
            result = r.guarded_kill(None, None, None, Path(temp), r.fresh_audit(), {"key": {"pass": False}}, loader)
            self.assertIsNone(result)
            loader.assert_not_called()
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_18_kill_failure_is_one_shot_not_epoch_selection(self):
        model = core.Student()
        with torch.no_grad():
            model.head_output.weight.zero_()
            model.head_output.bias.fill_(-1)
        kill = core.synthetic_contexts(5, 2)
        for i, c in enumerate(kill):
            c.split = "kill"
            c.targets = [core.Target("kill-%d" % i, 1, "A", 1, True)]
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            checkpoint = out/"selected.pt"
            core.atomic_bytes(checkpoint, b"synthetic-selected-identity")
            seal = r.seal_checkpoint(checkpoint, out/"seal.json")
            from unittest.mock import Mock
            loader = Mock(return_value=kill)
            audit = r.fresh_audit()
            result = r.guarded_kill(model, checkpoint, seal, out, audit, {"key": {"pass": True}}, loader)
            self.assertEqual(result, [False]*5)
            self.assertEqual(core.terminal_status(True, True, True, result), "F5_KILL_ONLY_ATTACK_FAILURE")
            self.assertEqual(audit["kill_evaluation_calls"], 1)
            with self.assertRaises(core.ContractError):
                r.guarded_kill(model, checkpoint, seal, out, audit, {"key": {"pass": True}}, loader)
            loader.assert_called_once()

    def test_19_selected_success_control_and_seal(self):
        # Fake evaluation isolates controller selection; it is not a model efficacy test.
        contexts = fixture_dataset()
        identities = fixture_identities(contexts)
        template = {"eligible": True, "violations": [], "predictions": [], "targets": 8, "contexts": 4}
        evaluations = [{**template, "label_loss": loss} for loss in (1, 1, .9, .8)]
        with tempfile.TemporaryDirectory() as temp, patch.object(core, "evaluate", side_effect=evaluations):
            out = Path(temp)
            budget = r.Budget(out/"training"/"time.json", 120, out, lambda: 0)
            result = r.train_trajectory(contexts, out, identities, budget, r.fresh_audit(), max_epochs=2)
            self.assertEqual(result["selected_epoch"], 2)
            self.assertEqual(result["status"], "F5_T_COMPLETE_CHECKPOINT_SELECTED")
            seal = r.read_json(out/"training"/"selected_seal.json")
            r.require_seal(out/"training"/"best.pt", seal)

    def test_20_full_metric_denominators_and_small_family(self):
        p = {"uid":"u", "context":"c", "split":"val", "owner":"B", "label":1,
             "hard":False, "protected":True, "logit":-2}
        meta = {"u": {"owner":"B", "label":"1", "teacher_kind":"none", "source_group":"s", "device_family":"d", "attack_family":"f"}}
        rows = r.protected_metrics([p], meta)
        self.assertEqual(len(rows), 5)
        family = next(row for row in rows if row["group_kind"] == "attack_family")
        self.assertEqual((family["targets"], family["contexts"], family["sources"], family["fn"]), (1,1,1,1))
        self.assertEqual(family["attack_evidence"], "INSUFFICIENT")

    def test_21_counts_before_feature_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            core.atomic_json(root/r.F3, {"nested_split": {"train_sources": ["s%d" % i for i in range(13)],
                                                        "internal_validation_sources": sorted(r.VAL_SOURCES)}})
            with patch.object(r, "read_csv", return_value=[]), patch.object(r.np, "fromfile") as numeric:
                with self.assertRaises(core.ContractError):
                    r.load_parent(root, r.fresh_audit())
                numeric.assert_not_called()

    def test_22_implementation_gate_blocks_unaccepted_code(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(r, "IROOT", Path(temp)):
            core.atomic_json(Path(temp)/"stage_i_acceptance.json", {"status": "PENDING"})
            with self.assertRaises(core.ContractError):
                r.check_implementation_receipt()

    def test_23_input_hash_drift_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            core.atomic_bytes(root/"input.bin", b"synthetic identity")
            pins = {"input.bin": core.sha_file(root/"input.bin")}
            with patch.object(r, "protocol_pins", return_value=pins):
                self.assertEqual(r.verify_pins(root), pins)
                core.atomic_bytes(root/"input.bin", b"changed synthetic identity")
                with self.assertRaises(core.ContractError):
                    r.verify_pins(root)

    def test_24_production_teacher_whitelist_on_synthetic_25467_rows(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/r.PT).mkdir(parents=True)
            uid = np.asarray(["synthetic-%05d" % i for i in range(25467)])
            representation = np.full((25467, 768), np.nan, dtype=np.float32)
            representation[:6870] = 0
            targets, metadata = [], {}
            for i in range(6870):
                label = int(i < 2179)
                kind = "attack_hard" if label else "benign_normal" if i < 6846 else "benign_hard"
                representation[i, 0] = 2 if kind != "benign_normal" else -2
                targets.append(core.Target(str(uid[i]), 0, "A", label, kind != "benign_hard"))
                metadata[str(uid[i])] = {"label": str(label), "teacher_kind": kind}
            np.savez_compressed(root/r.PT/"ckda_d1_fit_select_embeddings.npz", uid=uid,
                                missing=np.zeros(25467, dtype=np.bool_), representation=representation)
            state = {"normalizer_mean": np.zeros(768), "normalizer_scale": np.ones(768),
                     "p2__0.weight": np.zeros((128,769),np.float32), "p2__0.bias": np.zeros(128,np.float32),
                     "p2__3.weight": np.zeros((1,128),np.float32), "p2__3.bias": np.array([-10],np.float32)}
            state["p2__0.weight"][0,0] = 1
            state["p2__3.weight"][0,0] = 5
            np.savez_compressed(root/r.PT/"ckda_d1_probe_state.npz", **state)
            context = core.Context("synthetic-teacher-scope", torch.zeros(1,131), targets)
            audit = r.fresh_audit()
            strengths = r.teacher_materialize(root, [context], metadata, root/"teacher.csv", audit)
            self.assertEqual(len(strengths), 6870)
            self.assertEqual(sum(value is None for value in strengths.values()), 24)
            self.assertEqual(audit["teacher_representation_rows_numeric"], 6870)
            self.assertEqual(audit["teacher_state_arrays_numeric"], 6)
            self.assertEqual(audit["teacher_validation_rows_numeric"], 0)
            self.assertEqual(audit["teacher_B_rows_numeric"], 0)
            self.assertEqual(len(r.read_csv(root/"teacher.csv")), 6870)

    def test_25_crash_after_early_stop_checkpoint_cannot_add_epoch(self):
        contexts = fixture_dataset()
        identities = fixture_identities(contexts)
        with tempfile.TemporaryDirectory() as temp:
            out = Path(temp)
            budget = r.Budget(out/"training"/"time.json", 120, out, lambda: 0)
            first = r.train_trajectory(contexts, out, identities, budget, r.fresh_audit(),
                                       max_epochs=100, stop_after_epoch_checkpoint=20)
            self.assertTrue(first["progress"]["stop_reached"])
            with patch.object(core, "train_batch") as step:
                result = r.train_trajectory(contexts, out, identities, budget, r.fresh_audit())
                step.assert_not_called()
            self.assertEqual(result["epochs"], 20)
            self.assertEqual(result["status"], "F5_NO_ELIGIBLE_CHECKPOINT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
