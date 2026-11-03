"""Synthetic N1 acceptance tests. No historical numeric artifact is opened."""
from __future__ import annotations

import ast
import builtins
import csv
import gzip
import io
import json
import os
import struct
import sys
import tempfile
import textwrap
import time
import unittest
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
import torch

import issue27frontend_inheritance_n1_support_v1 as s
import issue27frontend_inheritance_n1_math_v1 as m
import issue27frontend_inheritance_n1_runner_v1 as r
import issue27frontend_inheritance_n1_control_v1 as control

RUNTIME = None
DENIED_REAL_OPENS = []


def install_access_guard():
    runs = os.path.normcase(str((s.ROOT / "runs").resolve())) + os.sep
    allowed = {os.path.normcase(str((s.ROOT / name).resolve())) for name in
               (s.DESIGN, s.PINS_FILE, str(Path(s.DESIGN).with_suffix(".sha256")),
                str(Path(s.PINS_FILE).with_suffix(".sha256")))}
    implementation = os.path.normcase(str((s.ROOT / s.IMPLEMENTATION).resolve())) + os.sep
    def guard(event, args):
        if event != "open" or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
        if path.startswith(runs) and path not in allowed and not path.startswith(implementation):
            DENIED_REAL_OPENS.append(path)
            raise AssertionError("SYNTHETIC_TEST_ATTEMPTED_REAL_ARTIFACT_OPEN")
    sys.addaudithook(guard)


def setUpModule():
    global RUNTIME
    install_access_guard()
    RUNTIME = r.configure_runtime()


def budget(**changes):
    caps = dict(s.CAPS, **changes)
    return s.Budget(memory=lambda: 0, caps=caps)


def encoded(columns, rows):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(columns)
    writer.writerows([[row[k] for k in columns] if isinstance(row, dict) else row for row in rows])
    return stream.getvalue().encode("utf-8")


def row_fixture(uid="syn", category="A1C", context="ctx", **changes):
    owner, label, teacher = next(key for key, value in s.CATEGORIES.items() if value == category)
    row = dict.fromkeys(s.TARGET_COLUMNS, "synthetic")
    row.update(uid=uid, context_key=context, event_index="0", source_group="source", nested_split="train",
               owner=owner, label=label, teacher_kind=teacher, prefix_events="1", finite="true",
               roundtrip_exact="true", feature_width="131", feature_prefix_sha256="a" * 64)
    row.update(changes)
    return row


def small_contexts():
    contexts, raw, cursor = [], bytearray(), 0
    generator = np.random.RandomState(7)
    for i, category in enumerate(s.EXPECTED):
        length = [2, 5, 1, 4, 3][i]
        values = generator.standard_normal((length, 131)).astype("<f4") * np.float32(0.1)
        part = values.tobytes()
        target = row_fixture("syn-%d" % i, category, "ctx-%d" % i,
                             event_index=str(length - 1), prefix_events=str(length),
                             feature_prefix_sha256=s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", length, 131) + part))
        target.update(event=length - 1, category=category, protected=category in s.PROTECTED)
        contexts.append({"key": "ctx-%d" % i, "source": "source", "offset": cursor,
                         "count": length, "length": length, "targets": [target],
                         "byte_offset": cursor * 524, "byte_length": len(part), "x": torch.from_numpy(values.copy())})
        raw.extend(part)
        cursor += length
        # The prohibited interval is a deliberate nonfinite sentinel.
        raw.extend(b"\xff" * 524)
        cursor += 1
    return contexts, bytes(raw)


def checkpoint_blob(extra=None):
    identities = json.loads(json.dumps({"runtime": RUNTIME, "synthetic": True}))
    model = r.f5.Student()
    progress = {"epoch": 21, "cursor": 0, "order": [], "steps": 3120, "stop_reached": True,
                "selection": {"best_epoch": None, "last_epoch": 20},
                "epoch_ledger": [{"epoch": 20, "train_violations": ["synthetic-five"],
                                  "val_violations": ["PRIVATE_VALIDATION_SENTINEL"],
                                  "gate_counts": {"train:A1:protected": {"targets": 1},
                                                  "val:A0:protected": {"secret": "PRIVATE_SENTINEL"}}}]}
    container = {"model": model.state_dict(), "optimizer": {"state": {0: {"exp_avg": torch.zeros(2)}}},
                 "progress": progress, "identities": identities, "torch_rng": torch.get_rng_state(),
                 "numpy_rng": np.random.RandomState(2705).get_state(), "python_rng": (3, (1, 2, 3), None)}
    if extra:
        container.update(extra)
    stream = io.BytesIO()
    torch.save(container, stream)
    terminal = {"status": "F5_NO_ELIGIBLE_CHECKPOINT", "complete": True,
                "selected_epoch": None, "epochs": 20, "steps": 3120}
    return stream.getvalue(), identities, terminal


def forbidden_global():
    raise AssertionError("FORBIDDEN_REDUCER_EXECUTED")


class Forbidden:
    def __reduce__(self):
        return forbidden_global, ()


def result(status=0, theta=None, marginals=None):
    return SimpleNamespace(status=status, x=theta, ineqlin=SimpleNamespace(marginals=marginals),
                           nit=0, message="synthetic")


class InputTests(unittest.TestCase):
    def test_excluded_target_and_scope_access_only_selectors(self):
        for kind in ("target", "scope"):
            row = {key: "syn" for key in s.SELECTORS[kind]}
            row["nested_split" if kind == "target" else "split"] = "internal_val"
            accessed = []
            def get(key):
                self.assertIn(key, s.SELECTORS[kind])
                accessed.append(key)
                return row[key]
            select, payload = s.project_train(get, kind)
            self.assertIsNone(payload)
            self.assertEqual(set(accessed), set(s.SELECTORS[kind]))

    def test_mixed_csv_sentinels_and_quoting(self):
        rows = [row_fixture(source_group='source, "quoted"\nline'),
                row_fixture("excluded", nested_split="internal_val", source_group="PRIVATE_SENTINEL")]
        audit = {}
        select, payload = s.scan_csv(gzip.compress(encoded(s.TARGET_COLUMNS, rows)), "target", audit)
        self.assertEqual(len(select), 2)
        self.assertEqual(len(payload), 1)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps([select, payload, audit]))
        self.assertEqual(audit["column_accesses"]["source_group"], 1)
        self.assertEqual(audit["column_accesses"].get("old_all_unk", 0), 0)
        self.assertEqual(audit["excluded_payload_cells_transiently_tokenized"], 14)

    def test_bad_csv_header_rows_duplicates_and_split(self):
        good = row_fixture()
        cases = [encoded(s.TARGET_COLUMNS[::-1], [good]), encoded(s.TARGET_COLUMNS, [good, good]),
                 encoded(s.TARGET_COLUMNS, [["x"]]),
                 encoded(s.TARGET_COLUMNS, [row_fixture(nested_split="select")]),
                 encoded(s.TARGET_COLUMNS, []) + b'"unterminated\n']
        for data in cases:
            with self.assertRaises(s.Stop):
                s.scan_csv(gzip.compress(data), "target", {})

    def test_manifest_path_and_duplicate_guards(self):
        self.assertEqual(s.manifest(b"a" * 64 + b"  fixture.json\n"), {"fixture.json": "a" * 64})
        for name in ("../escape", "/escape", "C:/escape", "a//b", "a/./b"):
            with self.assertRaises(s.Stop):
                s.manifest(("a" * 64 + "  " + name + "\n").encode())
        with self.assertRaises(s.Stop):
            s.manifest(("a" * 64 + "  duplicate\n").encode() * 2)

    def test_input_hash_membership_repeated_reads_and_numeric_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "fixture").write_bytes(b"synthetic")
            inputs = s.Inputs(root, {"fixture": s.digest(b"synthetic"), s.FEATURES: "a" * 64}, budget(), {})
            with self.assertRaises(s.Stop):
                inputs.read("fixture")
            with self.assertRaises(s.Stop):
                inputs.verify("unauthorized")
            inputs.verify("fixture")
            self.assertEqual(inputs.read("fixture"), b"synthetic")
            with self.assertRaises(s.Stop):
                inputs.read("fixture")
            with self.assertRaises(s.Stop):
                inputs.verify("fixture")
            inputs.verified[s.FEATURES] = "a" * 64
            with self.assertRaisesRegex(s.Stop, "RESTRICTED_READER"):
                inputs.read(s.FEATURES)
            bad = s.Inputs(root, {"fixture": "0" * 64}, budget(), {})
            with self.assertRaisesRegex(s.Stop, "HASH_DRIFT"):
                bad.verify("fixture")

    def test_all_five_real_denominators_using_generated_metadata(self):
        index, selectors, targets, scope_select, scope = {}, {}, {}, {}, {}
        sources = {"train": {"s%d" % i for i in range(13)}, "internal_val": {"v"}}
        for i in range(9307):
            key, train = "c%05d" % i, i < 4984
            index[key] = {"context_key": key, "source_group": "s%d" % (i % 13) if train else "v",
                          "nested_split": "train" if train else "internal_val", "event_offset": str(i), "event_count": "1"}
        j = 0
        for category, count in s.EXPECTED.items():
            for _ in range(count):
                uid, key = "u%05d" % j, "c%05d" % (j % 4984)
                row = row_fixture(uid, category, key, source_group=index[key]["source_group"])
                targets[uid] = row
                selectors[uid] = {k: row[k] for k in s.SELECTORS["target"]}
                scope[uid] = {"uid": uid, "split": "train", "context": key,
                              "source": row["source_group"], "owner": row["owner"]}
                scope_select[uid] = {k: scope[uid][k] for k in s.SELECTORS["scope"]}
                j += 1
        for i in range(5206):
            uid, key = "v%05d" % i, "c%05d" % (4984 + i % 4323)
            selectors[uid] = {"uid": uid, "nested_split": "internal_val", "context_key": key}
            scope_select[uid] = {"uid": uid, "split": "internal_val", "context": key}
        args = (index, selectors, targets, scope_select, scope, sources)
        contexts, counts, events = s.validate_metadata(*args, all_events=9307)
        self.assertEqual((len(contexts), counts, events), (4984, s.EXPECTED, 4984))
        targets["u00000"]["prefix_events"] = "2"
        with self.assertRaisesRegex(s.Stop, "PREFIX_RANGE"):
            s.validate_metadata(*args, all_events=9307)
        targets["u00000"]["prefix_events"] = "1"
        scope_select["u00000"]["context"] = "wrong"
        with self.assertRaisesRegex(s.Stop, "SELECTOR_CONTEXT_JOIN"):
            s.validate_metadata(*args, all_events=9307)
        scope_select["u00000"]["context"] = "c00000"
        targets["u00000"]["teacher_kind"] = "none"
        with self.assertRaisesRegex(s.Stop, "CATEGORY_DRIFT"):
            s.validate_metadata(*args, all_events=9307)

    def test_train_seek_read_skips_nonfinite_excluded_intervals(self):
        contexts, blob = small_contexts()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.f32le"
            path.write_bytes(blob)
            audit = {}
            loaded = r.feature_contexts(path, contexts, budget(), audit, len(blob))
            self.assertEqual(audit["feature_decode"]["validation_events"], 0)
            for original, actual in zip(contexts, loaded):
                self.assertTrue(torch.equal(original["x"], actual["x"]))
            contexts[0]["byte_offset"] = -1
            with self.assertRaisesRegex(s.Stop, "SEEK_RANGE"):
                r.feature_contexts(path, contexts, budget(), {}, len(blob))

    def test_prefix_identity_and_size_fail_closed(self):
        contexts, blob = small_contexts()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "synthetic.f32le"
            path.write_bytes(blob)
            with self.assertRaisesRegex(s.Stop, "BYTE_SIZE"):
                r.feature_contexts(path, contexts, budget(), {}, len(blob) + 1)
            contexts[0]["targets"][0]["feature_prefix_sha256"] = "0" * 64
            with self.assertRaisesRegex(s.Stop, "PREFIX_IDENTITY"):
                r.feature_contexts(path, contexts, budget(), {}, len(blob))


class ModelTests(unittest.TestCase):
    def test_restricted_full_checkpoint_json_roundtrip_and_projection(self):
        blob, identities, terminal = checkpoint_blob()
        audit = {}
        with mock.patch.object(torch.optim.AdamW, "__init__", side_effect=AssertionError("optimizer")):
            state, reference = r.restricted_checkpoint(blob, s.digest(blob), identities, terminal, audit)
        self.assertEqual(len(state), len(r.f5.Student().state_dict()))
        self.assertNotIn("PRIVATE", json.dumps(reference))
        self.assertTrue(audit["checkpoint_container"]["incidental_optimizer_rng_and_old_validation_ledger_materialized"])
        self.assertFalse(audit["checkpoint_container"]["incidental_values_used"])

    def test_forbidden_globals_and_ambient_allowlist_do_not_leak(self):
        blob, identities, terminal = checkpoint_blob({"forbidden": Forbidden()})
        previous = torch.serialization.get_safe_globals()
        torch.serialization.add_safe_globals([forbidden_global])
        try:
            with self.assertRaisesRegex(s.Stop, "NEEDS_GOVERNED_MODEL_EXPORT"):
                r.restricted_checkpoint(blob, s.digest(blob), identities, terminal, {})
            self.assertIn(forbidden_global, torch.serialization.get_safe_globals())
        finally:
            torch.serialization.clear_safe_globals()
            torch.serialization.add_safe_globals(previous)

    def test_checkpoint_hash_identity_and_terminal_stops(self):
        blob, identities, terminal = checkpoint_blob()
        with self.assertRaisesRegex(s.Stop, "CHANGED_AFTER_HASH"):
            r.restricted_checkpoint(blob, "0" * 64, identities, terminal, {})
        with self.assertRaisesRegex(s.Stop, "EMBEDDED_IDENTITY"):
            r.restricted_checkpoint(blob, s.digest(blob), {}, terminal, {})
        terminal["epochs"] = 19
        with self.assertRaisesRegex(s.Stop, "TERMINAL_REFERENCE"):
            r.restricted_checkpoint(blob, s.digest(blob), identities, terminal, {})

    def test_canonical_full_context_hook_and_replay_identity(self):
        contexts, _ = small_contexts()
        model = r.f5.Student()
        calls = []
        original = model.head_output.forward
        def forward(x):
            calls.append((len(x), torch.is_grad_enabled()))
            return original(x)
        with mock.patch.object(model.head_output, "forward", side_effect=forward):
            baseline, features, hashes = r.canonical_pass(model, contexts, budget())
        self.assertEqual(calls, [(5, False), (4, False), (3, False), (2, False), (1, False)])
        self.assertEqual(set(features), set(baseline))
        theta = np.zeros(65, dtype=np.float32)
        replay, actual_hashes, _ = r.replay_candidate(model, contexts, theta, hashes, budget())
        self.assertEqual(hashes, actual_hashes)
        self.assertTrue(all(p["hard"] for p in replay.values()))
        self.assertEqual(len(model.head_output._forward_pre_hooks), 0)
        bad = dict(hashes)
        bad[contexts[0]["key"]] = {"rows": 2, "sha256": "0" * 64}
        with self.assertRaisesRegex(s.Stop, "FIXED_FEATURE_IDENTITY"):
            r.replay_candidate(model, contexts, theta, bad, budget())

    def test_wrong_context_order_and_forward_action_caps(self):
        contexts, _ = small_contexts()
        with self.assertRaisesRegex(s.Stop, "CONTEXT_ORDER"):
            r.canonical_pass(r.f5.Student(), contexts[::-1], budget())
        with self.assertRaisesRegex(s.Stop, "ACTION_CAP_BATCHES"):
            r.canonical_pass(r.f5.Student(), contexts, budget(batches=0))

    def test_exact_baseline_five_uid_gate(self):
        predictions = {}
        gates = {}
        for category in s.EXPECTED:
            for i in range(s.EXPECTED[category]):
                uid, attack = category + str(i), category in {"A1C", "B1N"}
                hard = False if category == "A1C" and i < 5 else attack
                predictions[uid] = {"hard": hard, "label": int(attack), "protected": category in s.PROTECTED,
                                    "category": category}
        for category, key in (("A1C", "train:A1:protected"), ("A0C", "train:A0:protected"), ("B1N", "train:B1:protected")):
            values = [p for p in predictions.values() if p["category"] == category]
            gates[key] = {"targets": len(values), "hard": sum(p["hard"] for p in values),
                          "flips": sum(p["hard"] != bool(p["label"]) for p in values)}
        reference = {"train_violations": ["A1C%d" % i for i in range(5)], "gate_counts": gates}
        r.validate_baseline(predictions, reference, predictions)
        reference["train_violations"][-1] = "A1C5"
        with self.assertRaisesRegex(s.Stop, "FIVE_ERROR_SET"):
            r.validate_baseline(predictions, reference, predictions)

    def test_all_category_change_accounting(self):
        old = {cat: {"category": cat, "label": 0, "hard": False} for cat in s.EXPECTED}
        new = {cat: {**value, "hard": True} for cat, value in old.items()}
        report = r.outcomes(old, new)
        for category in s.EXPECTED:
            self.assertEqual(report[category]["newly_wrong"], [category])
            self.assertIsNone(r.outcomes(old, None)[category]["candidate_errors"])

    def test_synthetic_end_to_end_single_lp_two_forwards(self):
        contexts, _ = small_contexts()
        with tempfile.TemporaryDirectory() as folder:
            b = budget()
            writer = s.Writer(folder, b)
            verdict = r.diagnose(r.f5.Student(), contexts, {}, writer, b, enforce_real_baseline=False)
            self.assertIn(verdict["status"], {"N1_JOINT_HEAD_WITNESS", "N1_EXACT_AFFINE_NONSEPARABLE", "N1_NUMERICAL_UNKNOWN"})
            self.assertEqual((b.counts["lp_calls"], b.counts["passes"], b.counts["targets"]), (1, 2, 10))
            for name, sha in writer.members.items():
                self.assertEqual(s.sha_file(Path(folder) / name), sha)
            self.assertFalse(any("resume" in name or "checkpoint" in name for name in writer.members))


class MathTests(unittest.TestCase):
    def fixture(self, values=(1, -1), labels=(1, 0)):
        h = np.zeros((len(values), 64), dtype=np.float32)
        h[:, 0] = values
        return h, np.asarray(labels, dtype=np.int64)

    def test_separable_and_repeatability_exact_runtime(self):
        h, labels = self.fixture()
        results = []
        for _ in range(2):
            a, solved, receipt = m.solve_once(h, labels, budget())
            theta = m.sole_candidate(solved)
            self.assertTrue(m.exact_signs(h, labels, theta, m.ExactBudget())["pass"])
            self.assertEqual(receipt["warnings"], [])
            results.append((solved.x.tobytes(), solved.ineqlin.marginals.tobytes(), solved.nit))
        self.assertEqual(results[0], results[1])

    def test_known_nonseparable_exact_certificate(self):
        h, labels = self.fixture((0, 0))
        a, solved, _ = m.solve_once(h, labels, budget())
        checked = m.certificate(a, solved, False, m.ExactBudget())
        self.assertTrue(checked["verified"])
        values = [Fraction(int(v["numerator"]), int(v["denominator"])) for v in checked["lambda"]]
        self.assertTrue(m.verify_certificate(a, checked["support"], values, m.ExactBudget()))
        values[0] += Fraction(1, 10**20)
        self.assertFalse(m.verify_certificate(a, checked["support"], values, m.ExactBudget()))

    def test_tiny_positive_margin_is_not_negative_evidence(self):
        h, labels = self.fixture((1e-12, -1e-12))
        theta = np.zeros(65, dtype=np.float32)
        theta[0] = 1
        self.assertTrue(m.exact_signs(h, labels, theta, m.ExactBudget())["pass"])
        a, solved, _ = m.solve_once(h, labels, budget())
        self.assertFalse(m.certificate(a, solved, False, m.ExactBudget())["verified"])

    def test_attack_zero_allowed_benign_zero_rejected(self):
        h, labels = self.fixture((0, -1))
        theta = np.zeros(65, dtype=np.float32)
        theta[0] = 1
        checked = m.exact_signs(h, labels, theta, m.ExactBudget())
        self.assertTrue(checked["pass"])
        self.assertEqual(checked["zero_margin_attack_ties"], 1)
        h[1, 0] = 0
        self.assertFalse(m.exact_signs(h, labels, theta, m.ExactBudget())["pass"])

    def test_status_partial_candidate_and_no_fallback(self):
        h, labels = self.fixture()
        for status in (0, 1, 2, 3, 4):
            fake = mock.Mock(return_value=result(status, np.zeros(66)))
            b = budget()
            _, solved, _ = m.solve_once(h, labels, b, fake)
            self.assertEqual(fake.call_count, 1)
            self.assertEqual(fake.call_args.kwargs["method"], "highs-ds")
            if status in (2, 3):
                with self.assertRaisesRegex(s.Stop, "INFEASIBLE_OR_UNBOUNDED"):
                    m.sole_candidate(solved)
            else:
                self.assertEqual(m.sole_candidate(solved) is not None, status in (0, 1))
            with self.assertRaisesRegex(s.Stop, "ACTION_CAP_LP_CALLS"):
                m.solve_once(h, labels, b, fake)
            self.assertEqual(fake.call_count, 1)

    def test_missing_nonfinite_and_out_of_range_candidate(self):
        self.assertIsNone(m.sole_candidate(result(1)))
        self.assertIsNone(m.sole_candidate(result(0, np.full(66, np.nan))))
        with self.assertRaisesRegex(s.Stop, "CAST_RANGE"):
            m.sole_candidate(result(0, np.full(66, 2.0)))

    def test_certificate_support_rank_and_negative_reconstruction(self):
        h, labels = self.fixture((0, 0))
        a = m.problem(h, labels)
        for status, margins in ((1, [-0.5, -0.5]), (0, [0, 0]), (0, [None, None])):
            if margins == [None, None]:
                margins = [np.nan, np.nan]
            self.assertFalse(m.certificate(a, result(status, marginals=margins), False, m.ExactBudget())["verified"])
        many = np.zeros((67, 65), dtype=np.float64)
        checked = m.certificate(many, result(marginals=-np.ones(67)), False, m.ExactBudget())
        self.assertEqual(checked["status"], "UNAVAILABLE_SUPPORT")
        # Rank-deficient support is reconstructed deterministically with free variables zero.
        duplicate = np.vstack([a, a[:1]])
        values = m.reconstruct(duplicate, [0, 1, 2], m.ExactBudget())
        self.assertEqual(values, [Fraction(1, 2), Fraction(1, 2), Fraction(0)])
        self.assertFalse(m.verify_certificate(a, [0, 1], [Fraction(-1), Fraction(2)], m.ExactBudget()))
        self.assertIsNone(m.reconstruct(m.problem(*self.fixture()), [0, 1], m.ExactBudget()))

    def test_exact_bit_and_time_budget_stops_are_unknown(self):
        with self.assertRaises(m.ExactStop):
            m.ExactBudget(bits=4).mul(Fraction(15), Fraction(15))
        clock = iter([0, 121])
        stage = m.ExactBudget(clock=lambda: next(clock))
        h, labels = self.fixture()
        checked = m.exact_signs(h, labels, np.zeros(65, dtype=np.float32), stage)
        self.assertEqual(checked["status"], "EXACT_TIME_STOP")
        h, labels = self.fixture((0, 0))
        clock = iter([0, 121])
        checked = m.certificate(m.problem(h, labels), result(marginals=[-0.5, -0.5]), False,
                                m.ExactBudget(clock=lambda: next(clock)))
        self.assertFalse(checked["verified"])
        self.assertEqual(checked["status"], "EXACT_TIME_STOP")

    def test_verdict_precedence_and_float32_only_coexistence(self):
        self.assertEqual(m.verdict(True, True, False)["status"], "N1_JOINT_HEAD_WITNESS")
        exact_only = m.verdict(True, False, False)
        self.assertEqual(exact_only["fit_descriptor"], "EXACT_AFFINE_WITNESS_FLOAT32_REPLAY_MISMATCH")
        self.assertEqual(exact_only["status"], "N1_NUMERICAL_UNKNOWN")
        float_only = m.verdict(False, True, True)
        self.assertEqual(float_only["status"], "N1_EXACT_AFFINE_NONSEPARABLE")
        self.assertEqual(float_only["fit_descriptor"], "FLOAT32_ONLY_FIT")
        self.assertEqual(m.verdict(False, True, False)["status"], "N1_NUMERICAL_UNKNOWN")
        with self.assertRaisesRegex(s.Stop, "INTEGRITY"):
            m.verdict(True, True, True)
        self.assertEqual(m.verdict(True, True, True, "GLOBAL_WALL_STOP")["status"], "N1_ENGINEERING_STOP")
        with mock.patch.object(m, "reconstruct", side_effect=AssertionError("certificate attempted")):
            self.assertEqual(m.certificate(np.zeros((2, 65)), result(), True, m.ExactBudget())["status"],
                             "SKIPPED_EXACT_THRESHOLD_WITNESS")

    def test_actual_float32_cancellation_disagrees_with_exact_signs(self):
        matrix = np.zeros((5, 64), dtype=np.float32)
        matrix[:, :3] = [2**24, 1, -(2**24)]
        theta = np.zeros(65, dtype=np.float32)
        theta[:3], theta[-1] = 1, -0.5
        layer = torch.nn.Linear(64, 1)
        with torch.no_grad():
            layer.weight.copy_(torch.from_numpy(theta[:64].reshape(1, 64)))
            layer.bias.copy_(torch.from_numpy(theta[64:]))
            actual = layer(torch.from_numpy(matrix)).flatten().numpy()
        self.assertTrue((actual < 0).all())
        self.assertTrue(m.exact_signs(matrix, np.ones(5, dtype=np.int64), theta, m.ExactBudget())["pass"])
        self.assertFalse(m.exact_signs(matrix, np.zeros(5, dtype=np.int64), theta, m.ExactBudget())["pass"])


class ResourceTests(unittest.TestCase):
    def test_cooperative_wall_memory_output_and_single_writer(self):
        clock = iter([0, 1801])
        with self.assertRaisesRegex(s.Stop, "GLOBAL_WALL"):
            s.Budget(memory=lambda: 0, clock=lambda: next(clock)).check()
        with self.assertRaisesRegex(s.Stop, "GLOBAL_MEMORY"):
            s.Budget(memory=lambda: s.CAPS["memory_bytes"] + 1).check()
        with tempfile.TemporaryDirectory() as folder:
            writer = s.Writer(folder, budget(output_bytes=100, reserve_bytes=20))
            writer.write("first", b"x")
            with self.assertRaisesRegex(s.Stop, "ALREADY_EXISTS"):
                writer.write("first", b"x")
            with self.assertRaisesRegex(s.Stop, "GLOBAL_OUTPUT"):
                writer.write("oversize", b"x" * 80)
            self.assertFalse((Path(folder) / "oversize").exists())

    def synthetic_worker(self, folder, body, **caps):
        script = Path(folder) / "worker.py"
        output = Path(folder) / "result"
        script.write_text("import sys, time, json, os\nfrom pathlib import Path\n"
                          "sys.path.insert(0, " + repr(str(s.ROOT / "repo/ood")) + ")\n"
                          "import issue27frontend_inheritance_n1_control_v1 as c\n"
                          "output = Path(sys.argv[1])\nc.wait_gate(output)\n" + textwrap.dedent(body), encoding="utf-8")
        verdict = control.supervise([sys.executable, "-B", str(script), str(output)], output,
                                    caps=dict(s.CAPS, **caps), synthetic=True)
        return verdict, output

    def test_external_watchdog_stops_native_style_hang_no_retry(self):
        with tempfile.TemporaryDirectory() as folder:
            verdict, output = self.synthetic_worker(folder, "time.sleep(100)\n", wall_seconds=2)
            self.assertEqual(verdict["reason"], "GLOBAL_WALL_STOP")
            receipt = json.loads((output / "supervisor_terminal.json").read_text())
            self.assertEqual((receipt["worker_count"], receipt["restarts"]), (1, 0))
            self.assertLess(receipt["elapsed_seconds"], 5)
            with self.assertRaises(FileExistsError):
                control.supervise([], output, synthetic=True)

    def test_windows_job_rejects_large_allocation(self):
        with tempfile.TemporaryDirectory() as folder:
            verdict, _ = self.synthetic_worker(folder, '''
                try:
                    block = bytearray(256 * 1024**2)
                    code = "ALLOCATION_UNEXPECTEDLY_ALLOWED"
                except MemoryError:
                    code = "SYNTHETIC_MEMORY_LIMIT_ENFORCED"
                c.atomic_status(output / "worker_terminal.json", {"verdict": {"status": code}})
                ''', memory_bytes=128 * 1024**2, wall_seconds=10)
            self.assertEqual(verdict["status"], "SYNTHETIC_MEMORY_LIMIT_ENFORCED")

    def test_windows_job_rejects_second_worker(self):
        with tempfile.TemporaryDirectory() as folder:
            verdict, _ = self.synthetic_worker(folder, '''
                import subprocess
                try:
                    child = subprocess.Popen([sys.executable, "-c", "pass"], creationflags=subprocess.CREATE_NO_WINDOW)
                    child.wait()
                    code = "CHILD_UNEXPECTEDLY_ALLOWED"
                except OSError:
                    code = "SYNTHETIC_SECOND_WORKER_BLOCKED"
                c.atomic_status(output / "worker_terminal.json", {"verdict": {"status": code}})
                ''', wall_seconds=10)
            self.assertEqual(verdict["status"], "SYNTHETIC_SECOND_WORKER_BLOCKED")

    def test_external_output_overflow_and_status_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            verdict, output = self.synthetic_worker(folder, '''
                (output / "oversize").write_bytes(b"x" * 20000)
                time.sleep(100)
                ''', output_bytes=30000, reserve_bytes=15000, wall_seconds=10)
            self.assertEqual(verdict["reason"], "GLOBAL_OUTPUT_STOP")
            self.assertEqual(control.status(output)["source"], "supervisor_terminal.json")

    def test_real_cli_requires_authorization_before_artifact_access(self):
        with mock.patch.object(sys, "argv", ["control", "run-real"]), \
                mock.patch.object(s, "frozen_design", side_effect=AssertionError("premature I/O")):
            with self.assertRaisesRegex(s.Stop, "AUTHORIZATION_REQUIRED"):
                control.main()

    def test_preflight_failure_seals_without_spawning(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "attempt"
            def fail():
                raise s.Stop("SYNTHETIC_IDENTITY_DRIFT")
            with mock.patch.object(control.subprocess, "Popen", side_effect=AssertionError("worker spawned")):
                verdict = control.supervise([], output, synthetic=True, preflight=fail)
            self.assertEqual(verdict["reason"], "SYNTHETIC_IDENTITY_DRIFT")
            self.assertEqual(json.loads((output / "supervisor_terminal.json").read_text())["worker_count"], 0)
            self.assertTrue(control.status(output)["final"])

    def test_corrupt_terminal_and_abnormal_exit_are_sealed(self):
        for body, reason in (("(output / 'worker_terminal.json').write_text('{broken')\n", "WORKER_TERMINAL_INVALID_JSONDecodeError"),
                             ("sys.exit(7)\n", "WORKER_EXIT_7")):
            with tempfile.TemporaryDirectory() as folder:
                verdict, output = self.synthetic_worker(folder, body, wall_seconds=10)
                self.assertEqual(verdict["reason"], reason)
                self.assertTrue(control.status(output)["final"])
                for name, sha in s.manifest((output / "SHA256SUMS").read_bytes()).items():
                    self.assertEqual(s.sha_file(output / name), sha)

    def test_provisional_and_corrupt_status_are_not_final(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder)
            control.atomic_status(output / "worker_terminal.json", {"verdict": {"status": "SYNTHETIC_PENDING"}})
            self.assertFalse(control.status(output)["final"])
            (output / "worker_terminal.json").write_text("{broken")
            self.assertEqual(control.status(output)["status"], "STATUS_RECEIPT_UNREADABLE_DO_NOT_RESTART")

    def test_no_forbidden_historical_calls_in_implementation(self):
        forbidden = {"load_parent", "load_preflight", "load_checkpoint", "backward", "optimizer_for",
                     "train_batch", "synthetic_pilot", "fromfile", "memmap", "restore_rng_state"}
        for name in ("support", "math", "runner", "control"):
            path = Path(__file__).with_name("issue27frontend_inheritance_n1_" + name + "_v1.py")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    function = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                    self.assertNotIn(function, forbidden)
                    if function == "load" and isinstance(node.func, ast.Attribute) and getattr(node.func.value, "id", "") == "torch":
                        self.assertTrue(any(k.arg == "weights_only" and isinstance(k.value, ast.Constant)
                                            and k.value.value is True for k in node.keywords))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.passed = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.passed.append(test.id())


def run_suite():
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result1 = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(suite)
    return {"status": "PASS" if result1.wasSuccessful() and not DENIED_REAL_OPENS else "FAIL",
            "tests_run": result1.testsRun, "passed": result1.passed,
            "failures": [{"test": test.id(), "traceback": trace} for test, trace in result1.failures],
            "errors": [{"test": test.id(), "traceback": trace} for test, trace in result1.errors],
            "denied_real_artifact_opens": DENIED_REAL_OPENS, "real_numeric_access": 0,
            "runtime": RUNTIME, "resource_tests": "SYNTHETIC_LIMIT_ENFORCEMENT_NOT_RESOURCE_PILOT"}


if __name__ == "__main__":
    report = run_suite()
    print(json.dumps(report, indent=2), flush=True)
    sys.exit(0 if report["status"] == "PASS" else 1)
