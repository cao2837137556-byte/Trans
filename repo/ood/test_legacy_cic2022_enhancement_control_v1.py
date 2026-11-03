"""Generated-only worker integration, access guards, metrics and supervisor tests."""
import copy
import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

import legacy_cic2022_enhancement_control_v1 as control
import legacy_cic2022_enhancement_evaluate_v1 as evaluation
import legacy_cic2022_enhancement_train_v1 as train
import legacy_p2_supported_capability_ledger_v1 as ledger
from test_legacy_cic2022_enhancement_train_v1 import generated_state, generated_targets


def metadata(uid, label, family="attack", role="future_query"):
    return dict(uid=uid, role=role, phase="report", source_group="synthetic-source", device_family="synthetic-device",
                attack_family=family if label else "benign", label_metric_only=label)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def cache(self, name, x, targets):
        p = self.root / (name + ".npz")
        np.savez(p, uid=np.asarray([r["uid"] for r in targets]), x=x,
                 y=np.asarray([int(r["label"]) for r in targets], dtype=np.int64))
        meta = self.root / (name + ".jsonl")
        meta.write_text("".join(json.dumps(r, separators=(",", ":")) + "\n" for r in targets), encoding="utf-8")
        return dict(path=p.name, sha256=control.sha(p), rows=len(targets), metadata_path=meta.name, metadata_sha256=control.sha(meta))

    def test_real_scope_requires_authorization_before_any_read(self):
        with mock.patch.object(control, "read_json", side_effect=AssertionError("must not open scope")):
            with self.assertRaisesRegex(RuntimeError, "AUTHORIZATION"):
                control.verify_scope("nonexistent", False)

    def test_training_descriptor_rejects_check_artifact_before_cache_access(self):
        p = self.root / "manifest.json"
        p.write_text(json.dumps({"artifacts": {"old_cache": {}, "new_train_cache": {}, "reference_state": {}, "new_check_cache": {}}}), encoding="utf-8")
        with mock.patch.object(evaluation, "load_cache", side_effect=AssertionError("must not open caches")):
            with self.assertRaisesRegex(RuntimeError, "ALLOWLIST"):
                control.training_worker("not-opened", p, self.root / "out", "B", synthetic=True)

    def test_two_full_width_workers_and_fixed_endpoint_scores(self):
        old, new = generated_targets()
        state = generated_state(768, 128)
        rng = np.random.default_rng(100)
        ox = rng.normal(size=(len(old), 768)).astype(np.float32)
        nx = rng.normal(size=(len(new), 768)).astype(np.float32)
        recipe = train.make_synthetic_recipe(old, new, input_width=768, hidden_width=128)
        recipe_path = self.root / "recipe.json"
        recipe_path.write_text(json.dumps(recipe), encoding="utf-8")
        state_path = self.root / "reference.npz"
        np.savez(state_path, **state)
        descriptor = dict(recipe_sha256=control.sha(recipe_path), artifacts={
            "old_cache": self.cache("old", ox, old), "new_train_cache": self.cache("new", nx, new),
            "reference_state": dict(path=state_path.name, sha256=control.sha(state_path))})
        manifest_path = self.root / "train_manifest.json"
        manifest_path.write_text(json.dumps(descriptor), encoding="utf-8")
        endpoints = {}
        for arm in ("B", "C"):
            endpoints[arm] = control.training_worker(recipe_path, manifest_path, self.root / arm, arm, synthetic=True)
        control.check_endpoints(endpoints["B"], endpoints["C"])
        states = {"R": state, **{arm: ledger.load_p2_state(self.root / arm / "checkpoint.npz") for arm in ("B", "C")}}
        check = [dict(r, uid="held_" + r["uid"], planned_role="CHECK") for r in new]
        cache = self.cache("check", nx, check)
        targets, probabilities, logits = evaluation._prepared_scores(self.root, cache, states, "CHECK")
        self.assertEqual(len(targets), len(check))
        reference = train.score_fixed(state, nx, synthetic=True)
        np.testing.assert_array_equal(probabilities["R"], reference["probabilities"])
        np.testing.assert_array_equal(logits["R"], reference["logits"])
        self.assertEqual(endpoints["B"]["row_exposures"], 2 * (len(old) + len(new)))
        with self.assertRaisesRegex(RuntimeError, "OUTPUT_NOT_EMPTY"):
            control.training_worker(recipe_path, manifest_path, self.root / "B", "B", synthetic=True)

    def test_cache_roles_order_and_path_escape_are_rejected(self):
        targets = [dict(uid="normal", label=0, planned_role="CHECK")]
        item = self.cache("check", np.zeros((1, 768), np.float32), targets)
        with self.assertRaisesRegex(ledger.Stop, "ROLE_ACCESS"):
            evaluation.load_cache(self.root, item, "TRAIN")
        with self.assertRaisesRegex(ledger.Stop, "OUTSIDE_ROOT"):
            evaluation.pinned(self.root, dict(path="../forbidden.npz", sha256="unused"))
        metadata_path = self.root / item["metadata_path"]
        metadata_path.write_text(json.dumps(dict(targets[0], uid="wrong")) + "\n", encoding="utf-8")
        item["metadata_sha256"] = control.sha(metadata_path)
        with self.assertRaisesRegex(ledger.Stop, "UID_ORDER"):
            evaluation.load_cache(self.root, item, "CHECK")

    def test_reference_identity_and_missing_are_preserved(self):
        plan = [metadata("valid", 1), metadata("missing", 1)]
        p = self.root / "reference.csv.gz"
        fields = ["subset", "uid", "role", "source_group", "device_family", "attack_family", "label", "missing", "raw_logit", "immutable_archived_probability", "fixed_rescore_probability", "canonical_hard"]
        def write(wrong=False):
            with gzip.open(p, "wt", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader()
                for i, target in enumerate(plan):
                    row = {k: target[k] for k in ("uid", "role", "source_group", "device_family", "attack_family")}
                    row.update(subset="expanded", label=1, missing=i, raw_logit="" if i else 0,
                               immutable_archived_probability=0.5, fixed_rescore_probability="" if i else 0.5, canonical_hard=1)
                    if wrong and not i: row["attack_family"] = "identity-drift"
                    writer.writerow(row)
        write()
        value = evaluation.load_reference(p, {"expanded": plan})["expanded"]
        np.testing.assert_array_equal(value["missing"], [False, True])
        self.assertTrue(np.isnan(value["probability"][1]))
        write(True)
        with self.assertRaisesRegex(ledger.Stop, "REFERENCE_METADATA"):
            evaluation.load_reference(p, {"expanded": plan})

    def test_primary_metrics_do_not_count_missing_as_learned_detection(self):
        rows = [metadata("a", 1), metadata("missing", 1), metadata("normal", 0)]
        probs = {"R": np.asarray([0.9, np.nan, 0.01]), "B": np.asarray([0.01, np.nan, 0.01]), "C": np.asarray([0.9, np.nan, 0.9])}
        summary = evaluation.pool_summary(rows, np.asarray([False, True, False]), probs, {"attack"})
        self.assertEqual(summary["attack"]["total_rows"], 2)
        self.assertEqual(summary["attack"]["valid_rows"], 1)
        self.assertEqual(summary["attack"]["missing_rows"], 1)
        self.assertEqual(summary["attack"]["flips"]["R_to_B"]["alarm_to_accept"], 1)
        verdict = evaluation.assess_contrasts(summary)
        self.assertEqual(verdict["R_to_C"]["status"], "REGRESSION")

    def test_weighted_regression_is_detected_even_with_equal_raw_errors(self):
        # Same raw alarm count; moving an error to the larger stream weight is worse.
        targets = [dict(label=0, evaluation_label_weight_numerator=1, evaluation_label_weight_denominator=4),
                   dict(label=0, evaluation_label_weight_numerator=3, evaluation_label_weight_denominator=4),
                   dict(label=1, evaluation_label_weight_numerator=1, evaluation_label_weight_denominator=1)]
        p = {"R": np.asarray([0.9, 0.01, 0.9]), "B": np.asarray([0.01, 0.9, 0.9]), "C": np.asarray([0.9, 0.01, 0.9])}
        metrics = evaluation.weighted_cic_summaries(targets, p)
        self.assertEqual(metrics["0"]["arms"]["R"]["alarms"], metrics["0"]["arms"]["B"]["alarms"])
        self.assertEqual(evaluation.assess_contrasts(metrics)["R_to_B"]["status"], "REGRESSION")

    def test_curves_keep_attack_pool_blank_and_same_normal_denominators(self):
        rows = [metadata("a", 1)] + [dict(metadata("n" + str(i), 0), device_family="iotsim-stream-consumer") for i in range(100)]
        p = np.asarray([0.9] + [0.01] * 100)
        report = dict(rows=rows, missing=np.zeros(len(rows), bool), p={a: p.copy() for a in evaluation.ARMS}, z={a: p.copy() for a in evaluation.ARMS})
        familiar = dict(rows=[metadata("f", 0)], missing=np.zeros(1, bool), p={a: np.asarray([0.01]) for a in evaluation.ARMS}, z={a: np.asarray([0.01]) for a in evaluation.ARMS})
        curves = evaluation.comparison_curves(report, familiar, {"attack"})
        for arm in evaluation.ARMS:
            point = curves[arm]["native_probability"]["points"]["0.01"]
            self.assertEqual(point["attack"]["attack"]["detected"], 1)
            self.assertEqual(curves[arm]["native_probability"]["normal_pool_rows"], {"familiar_normal": 1, "stream": 100})

    def test_supervisor_failure_is_terminal_and_does_not_advance_or_retry(self):
        out = self.root / "stopped"
        preservation = dict(files=[])
        def fake_json(path):
            return preservation
        with mock.patch.object(control, "verify_scope", return_value=({"desktop_notification": False}, self.root / "id.json", out)), \
             mock.patch.object(control, "read_json", side_effect=fake_json), \
             mock.patch.object(control, "run_child", side_effect=RuntimeError("synthetic prepare failure")) as child:
            with self.assertRaisesRegex(RuntimeError, "synthetic prepare failure"):
                control.run_chain("synthetic_scope", True)
        status = json.loads((out / "finalstatus.json").read_text(encoding="utf-8"))
        self.assertEqual(status["status"], "STOP")
        self.assertEqual(status["retries"], 0)
        self.assertEqual(child.call_count, 1)
        self.assertFalse((out / "train_B").exists())

    def test_ID_session_diagnostic_keeps_dependent_target_counts(self):
        targets = [dict(session_id="session-a"), dict(session_id="session-a"), dict(session_id="session-b")]
        p = {a: np.asarray([0.9, 0.01, 0.01]) for a in evaluation.ARMS}
        result = evaluation.id_session_summary(targets, p)
        self.assertEqual(result["session_count"], 2)
        self.assertEqual(result["packet_targets"], 3)
        self.assertEqual(result["per_session"]["session-a"]["arms"]["R"]["false_positive_packets"], 1)

    def test_supervisor_routes_PREPARE_to_existing_E3_runtime(self):
        out = self.root / "routing"
        with mock.patch.object(control, "verify_scope", return_value=({"desktop_notification": False}, self.root / "id.json", out)), \
             mock.patch.object(control, "read_json", return_value={"files": []}), \
             mock.patch.object(control, "run_child", side_effect=RuntimeError("synthetic routing stop")) as child:
            with self.assertRaisesRegex(RuntimeError, "synthetic routing stop"):
                control.run_chain("synthetic_scope", True)
        self.assertEqual(child.call_args.kwargs["python"], control.PREPARE_PYTHON)

    def test_supervisor_interrupt_records_STOP(self):
        out = self.root / "interrupted"
        with mock.patch.object(control, "verify_scope", return_value=({"desktop_notification": False}, self.root / "id.json", out)), \
             mock.patch.object(control, "read_json", return_value={"files": []}), \
             mock.patch.object(control, "run_child", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                control.run_chain("synthetic_scope", True)
        self.assertEqual(json.loads((out / "finalstatus.json").read_text(encoding="utf-8"))["status"], "STOP")


if __name__ == "__main__":
    unittest.main()
