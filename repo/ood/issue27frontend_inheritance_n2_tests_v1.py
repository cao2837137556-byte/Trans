"""Generated fixtures only; historical experiment reads are denied during tests."""
from __future__ import annotations

import ast
import copy
import csv
import gzip
import io
import json
import os
import struct
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

import numpy as np
import torch
import issue27frontend_inheritance_n2_support_v1 as s
import issue27frontend_inheritance_n2_runner_v1 as r
import issue27frontend_inheritance_n2_control_v1 as c

GUARD = {"active": False, "blocked": 0}


def audit_guard(event, args):
    if GUARD["active"] and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        if os.fsdecode(args[0]).lower() == os.devnull.lower():
            return
        path = Path(os.fsdecode(args[0])).resolve()
        if path.is_relative_to((s.ROOT / "runs").resolve()):
            GUARD["blocked"] += 1
            raise PermissionError("SYNTHETIC_HISTORICAL_ARTIFACT_READ_DENIED")


sys.addaudithook(audit_guard)


def budget(**kwargs):
    return s.Budget(memory=lambda: 0, **kwargs)


def row(uid, category, context, event=0, source="dev", device="key"):
    owner, label, teacher = next(k for k, v in s.CATEGORIES.items() if v == category)
    return {"uid": uid, "context_key": context, "event_index": str(event), "source_group": source,
            "nested_split": "internal_val", "owner": owner, "label": label, "teacher_kind": teacher,
            "device_family": device, "attack_family": "synthetic" if label == "1" else "benign",
            "feature_prefix_sha256": "0" * 64, "prefix_events": str(event + 1),
            "finite": "true", "roundtrip_exact": "true", "feature_width": "131",
            "category": category, "protected": category in s.PROTECTED, "event": event}


def context(key, rows, length=None, offset=0):
    n = length or max(x["event"] + 1 for x in rows)
    return {"key": key, "targets": rows, "length": n, "count": n, "offset": offset,
            "byte_offset": offset * 524, "byte_length": n * 524, "source": rows[0]["source_group"],
            "split": "internal_val"}


def tiny():
    return [context("a", [row("a1", "A1C", "a"), row("a0", "A0C", "a", 1)], 3),
            context("b", [row("b1", "B1N", "b"), row("b0", "B0N", "b", 1),
                          row("b00", "B0N", "b", 2)]),
            context("c", [row("a0w", "A0W", "c")])]


def predictions(contexts, values=None):
    values = values or {}
    result = {}
    for ctx in contexts:
        for x in ctx["targets"]:
            label = int(x["label"])
            value = float(values.get(x["uid"], 1 if label else -1))
            result[x["uid"]] = {"uid": x["uid"], "context": ctx["key"], "category": x["category"],
                "source": ctx["source"], "device_family": x["device_family"], "attack_family": x["attack_family"],
                "protected": x["protected"], "label": label, "logit": value,
                "hard": value >= 0, "signed_margin": value if label else -value}
    return result


def reference(contexts, wrong=()):
    p = predictions(contexts)
    gates = {}
    for cat, key in (("A1C", "val:A1:protected"), ("A0C", "val:A0:protected"), ("B1N", "val:B1:protected")):
        selected = [v for v in p.values() if v["category"] == cat]
        gates[key] = {"targets": len(selected), "hard": sum(not bool(x["label"]) if x["uid"] in wrong
                    else bool(x["label"]) for x in selected), "flips": sum(x["uid"] in wrong for x in selected)}
    return {"epoch": 20, "val_violations": list(wrong), "gate_counts": gates}


def full_metadata_fixture():
    contexts, counter = [], 0
    def add(source, cat, targets, nc, device, attack="benign"):
        nonlocal counter
        for i in range(nc):
            key = "%05d" % counter
            counter += 1
            count = targets // nc + int(i < targets % nc)
            rows = [row(key + ":" + str(j), cat, key, j, source, device) for j in range(count)]
            for x in rows:
                x["attack_family"] = attack
            contexts.append(context(key, rows))
    a, b, normal, attack = s.SOURCES
    add(a, "A0C", 267, 182, "iotsim-combined-cycle")
    add(a, "B0N", 333, 282, "iotsim-combined-cycle")
    add(b, "A0C", 368, 137, "iotsim-domotic-monitor")
    add(b, "A0W", 2, 2, "iotsim-domotic-monitor")
    add(b, "B0N", 230, 50, "iotsim-domotic-monitor")
    add(normal, "A0C", 843, 672, "ton-iot-external")
    add(normal, "B0N", 3157, 2995, "ton-iot-external")
    add(attack, "A1C", 3, 1, "combined-cycle", "Ingress Tool Transfer")
    add(attack, "B1N", 3, 2, "combined-cycle", "File Download")
    return contexts


def metadata_fixture():
    index = {"t": dict(zip(s.INDEX_COLUMNS, ("t", "train-source", "train", "0", "2"))),
             "a": dict(zip(s.INDEX_COLUMNS, ("a", "dev", "internal_val", "2", "3")))}
    x = row("a1", "A1C", "a", 1)
    ts = {"t1": {"uid": "t1", "context_key": "t", "nested_split": "train"},
          "a1": {k: x[k] for k in s.SELECTORS["target"]}}
    ss = {u: {"uid": u, "context": t["context_key"], "split": t["nested_split"]} for u, t in ts.items()}
    scope = {"a1": {**ss["a1"], "source": "dev", "owner": "A"}}
    return [index, ts, {"a1": x}, ss, scope, {"train": {"train-source"}, "internal_val": {"dev"}}]


def validate_fixture(args):
    return s.validate_metadata(*args, expected={"A1C": 1}, context_count=1, all_contexts=2,
                               all_targets=2, all_events=5, train_sources=1)


def csv_blob(kind, rows):
    columns = {"target": s.TARGET_COLUMNS, "scope": s.SCOPE_COLUMNS, "index": s.INDEX_COLUMNS}[kind]
    stream = io.StringIO(newline="")
    writer = csv.writer(stream)
    writer.writerow(columns)
    writer.writerows([[r.get(k, "SENTINEL") for k in columns] for r in rows])
    raw = stream.getvalue().encode()
    return gzip.compress(raw) if kind == "target" else raw


class ProjectionTests(unittest.TestCase):
    def test_train_payload_never_accessed(self):
        values = {"uid": "t", "nested_split": "train", "context_key": "ctx"}
        selectors, payload = s.project_dev(values.__getitem__, "target")
        self.assertIsNone(payload)
        self.assertEqual(selectors, values)

    def test_dev_excluded_columns_never_accessed(self):
        x = row("u", "A1C", "c")
        x.pop("category")
        _, selected = s.project_dev(x.__getitem__, "target")
        self.assertNotIn("l1_prefix_sha256", selected)
        self.assertNotIn("old_all_unk", selected)

    def test_mixed_csv_access_accounting(self):
        train = {"uid": "t", "nested_split": "train", "context_key": "t"}
        audit = {}
        selectors, selected = s.scan_csv(csv_blob("target", [train, row("v", "A0C", "v")]), "target", audit)
        self.assertEqual(set(selectors), {"t", "v"})
        self.assertEqual(set(selected), {"v"})
        self.assertEqual(audit["column_accesses"]["label"], 1)
        self.assertEqual(audit["column_accesses"]["l1_prefix_sha256"], 0)
        self.assertEqual(audit["cells_tokenized"], 34)
        self.assertEqual(audit["excluded_payload_cells_transiently_tokenized"], 16)

    def test_scope_selective_payload(self):
        rows = [{"uid": "t", "split": "train", "context": "t"},
                {"uid": "v", "split": "internal_val", "context": "v", "source": "dev", "owner": "A"}]
        audit = {}
        _, selected = s.scan_csv(csv_blob("scope", rows), "scope", audit)
        self.assertEqual(selected["v"]["source"], "dev")
        self.assertEqual(audit["column_accesses"]["source"], 1)

    def test_duplicate_and_header_rejected(self):
        with self.assertRaises(s.Stop):
            s.scan_csv(csv_blob("target", [row("v", "A0C", "v")] * 2), "target", {})
        with self.assertRaises(s.Stop):
            s.scan_csv(b"bad,header\n", "scope", {})

    def test_metadata_join_and_prefix_selection(self):
        contexts, counts, events = validate_fixture(metadata_fixture())
        self.assertEqual((counts, events), ({"A1C": 1}, 2))
        self.assertEqual((contexts[0]["byte_offset"], contexts[0]["byte_length"]), (1048, 1048))

    def test_selector_join_drift(self):
        args = metadata_fixture()
        args[3]["a1"]["context"] = "t"
        with self.assertRaises(s.Stop):
            validate_fixture(args)

    def test_payload_source_drift(self):
        args = metadata_fixture()
        args[4]["a1"]["source"] = "train-source"
        with self.assertRaises(s.Stop):
            validate_fixture(args)

    def test_noncontiguous_ranges(self):
        args = metadata_fixture()
        args[0]["a"]["event_offset"] = "1"
        with self.assertRaises(s.Stop):
            validate_fixture(args)

    def test_target_outside_context(self):
        args = metadata_fixture()
        args[2]["a1"]["event_index"] = "3"
        with self.assertRaises(s.Stop):
            validate_fixture(args)

    def test_real_group_denominators_generated(self):
        contexts = full_metadata_fixture()
        s.validate_groups(contexts)
        self.assertEqual(len(contexts), 4323)
        self.assertEqual(sum(len(x["targets"]) for x in contexts), 5206)

    def test_group_family_drift(self):
        contexts = full_metadata_fixture()
        contexts[-1]["targets"][0]["attack_family"] = "renamed"
        with self.assertRaises(s.Stop):
            s.validate_groups(contexts)

    def test_hash_and_authorized_path(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            (folder / "data").write_bytes(b"good")
            inputs = s.Inputs(folder, {"data": s.digest(b"bad")}, budget(), {})
            with self.assertRaises(s.Stop):
                inputs.verify("data")
            with self.assertRaises(s.Stop):
                inputs.path("../escape")

    def test_audit_guard_denies_historical_numeric(self):
        with self.assertRaises(PermissionError):
            (s.ROOT / s.FEATURES).open("rb")


class NumericTests(unittest.TestCase):
    def test_exact_head_assembly_and_nonhead_identity(self):
        state = r.f5.Student().state_dict()
        theta = np.linspace(-1, 1, 65, dtype=np.float32)
        theta[5] = np.float32(-0.0)
        head = theta.astype("<f4").tobytes()
        pins = {"terminal_state_tensor_sha256": r.f5.tensor_hash(state),
                "non_head_state_tensor_sha256": r.non_head_hash(state), "head_float32_le_sha256": s.digest(head)}
        b = budget()
        model, hashes = r.assemble(state, head, pins, b)
        self.assertEqual(model.head_output.weight.detach().numpy().tobytes()
                         + model.head_output.bias.detach().numpy().tobytes(), head)
        self.assertEqual(r.non_head_hash(model.state_dict()), pins["non_head_state_tensor_sha256"])
        self.assertNotEqual(hashes["assembled_state"], hashes["terminal_state"])
        with self.assertRaises(s.Stop):
            r.assemble(state, head, pins, b)

    def test_state_and_head_hash_drift(self):
        state = r.f5.Student().state_dict()
        head = np.zeros(65, dtype="<f4").tobytes()
        pins = {"terminal_state_tensor_sha256": r.f5.tensor_hash(state),
                "non_head_state_tensor_sha256": r.non_head_hash(state), "head_float32_le_sha256": s.digest(head)}
        for field in pins:
            bad = {**pins, field: "0" * 64}
            with self.assertRaises(s.Stop):
                r.assemble(state, head, bad, budget())

    def test_final_epoch_only_projection(self):
        class Forbidden(dict):
            def __getitem__(self, key):
                raise AssertionError("EXCLUDED_FIELD")
        final = {"epoch": 20, "val_violations": ["u"],
                 "gate_counts": {"val:A1:protected": {"targets": 1}, "train:excluded": Forbidden()},
                 "train_violations": Forbidden()}
        container = {"model": {"x": torch.zeros(1)}, "identities": {"pin": "fixture"},
            "optimizer": Forbidden(), "rng": Forbidden(), "progress": {"epoch": 21, "cursor": 0,
            "order": [], "steps": 3120, "stop_reached": True,
            "selection": {"best_epoch": None, "last_epoch": 20}, "epoch_ledger": [Forbidden(), final]}}
        audit = {}
        _, ref = r.project_checkpoint(container, {"pin": "fixture"}, audit)
        self.assertEqual(set(ref["gate_counts"]), {"val:A1:protected"})
        self.assertFalse(audit["checkpoint_projection"]["incidental_values_used"])

    def test_restricted_loader_globals_and_restore(self):
        previous = torch.serialization.get_safe_globals()
        torch.serialization.add_safe_globals([set])
        wanted = {np._core.multiarray._reconstruct, np.ndarray, np.dtype, np.dtypes.UInt32DType}
        def load(*args, **kwargs):
            self.assertEqual(set(torch.serialization.get_safe_globals()), wanted)
            self.assertEqual(kwargs, {"map_location": "cpu", "weights_only": True})
            raise pickle_error()
        terminal = {"status": "F5_NO_ELIGIBLE_CHECKPOINT", "complete": True,
                    "selected_epoch": None, "epochs": 20, "steps": 3120}
        try:
            with patch.object(torch, "load", side_effect=load) as loader:
                with self.assertRaisesRegex(s.Stop, "N2_NEEDS_GOVERNED_MODEL_EXPORT"):
                    r.restricted_checkpoint(b"fixture", s.digest(b"fixture"), {}, terminal, {}, budget())
                self.assertEqual(loader.call_count, 1)
            self.assertIn(set, torch.serialization.get_safe_globals())
        finally:
            torch.serialization.clear_safe_globals()
            torch.serialization.add_safe_globals(previous)

    def test_generated_checkpoint_success(self):
        terminal = {"status": "F5_NO_ELIGIBLE_CHECKPOINT", "complete": True,
                    "selected_epoch": None, "epochs": 20, "steps": 3120}
        fixture = {"model": r.f5.Student().state_dict(), "identities": {"fixture": True},
            "progress": {"epoch": 21, "cursor": 0, "order": [], "steps": 3120, "stop_reached": True,
                "selection": {"best_epoch": None, "last_epoch": 20}, "epoch_ledger": [reference(tiny())]},
            "rng": np.random.get_state(), "optimizer": {"fixture": torch.zeros(2)}}
        stream = io.BytesIO()
        torch.save(fixture, stream)
        raw = stream.getvalue()
        state, ref = r.restricted_checkpoint(raw, s.digest(raw), fixture["identities"], terminal, {}, budget())
        self.assertEqual(r.f5.tensor_hash(state), r.f5.tensor_hash(fixture["model"]))
        self.assertEqual(ref, reference(tiny()))

    def test_selective_seek_prefix_hash_and_train_exclusion(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "features"
            values = np.zeros((5, 131), dtype="<f4")
            values[:2] = np.nan
            raw = values.tobytes()
            path.write_bytes(raw)
            contexts, _, _ = validate_fixture(metadata_fixture())
            ctx = contexts[0]
            ctx["split"] = "internal_val"
            ctx["targets"][0]["feature_prefix_sha256"] = s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", 2, 131) + raw[1048:2096])
            audit = {}
            loaded = r.feature_contexts(path, contexts, budget(), audit, len(raw))
            self.assertEqual(loaded[0]["x"].shape, (2, 131))
            self.assertEqual(audit["feature_decode"]["train_events"], 0)
            ctx["split"] = "train"
            with self.assertRaises(s.Stop):
                r.feature_contexts(path, contexts, budget(), {}, len(raw))

    def test_feature_nonfinite_hash_and_range(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "features"
            raw = np.full((1, 131), np.nan, dtype="<f4").tobytes()
            path.write_bytes(raw)
            ctx = context("x", [row("x", "A0C", "x")])
            with self.assertRaisesRegex(s.Stop, "FEATURE_PREFIX_IDENTITY"):
                r.feature_contexts(path, [ctx], budget(), {}, len(raw))
            ctx["targets"][0]["feature_prefix_sha256"] = s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", 1, 131) + raw)
            with self.assertRaisesRegex(s.Stop, "FEATURE_NONFINITE"):
                r.feature_contexts(path, [ctx], budget(), {}, len(raw))
            ctx["byte_offset"] = -1
            with self.assertRaisesRegex(s.Stop, "FEATURE_SEEK_RANGE"):
                r.feature_contexts(path, [ctx], budget(), {}, len(raw))

    def test_canonical_sort_full_context_zero_state_no_grad(self):
        contexts = tiny()
        contexts[1]["length"] = contexts[1]["count"] = 5
        for ctx in contexts:
            ctx["x"] = torch.randn(ctx["length"], 131)
        model = r.f5.Student()
        before = r.f5.tensor_hash(model.state_dict())
        shapes, gru_calls = [], []
        def head_hook(module, args):
            self.assertFalse(torch.is_grad_enabled())
            self.assertFalse(model.training)
            shapes.append(tuple(args[0].shape))
        def gru_hook(module, args):
            self.assertEqual(len(args), 1)
            gru_calls.append(True)
        h = model.head_output.register_forward_pre_hook(head_hook)
        g = model.encoder.register_forward_pre_hook(gru_hook)
        try:
            first = r.canonical_pass(model, contexts, budget())
        finally:
            h.remove()
            g.remove()
        self.assertEqual(shapes, [(5, 64), (3, 64), (1, 64)])
        self.assertEqual(len(gru_calls), 1)
        self.assertEqual(r.f5.tensor_hash(model.state_dict()), before)
        self.assertEqual(set(first), {x["uid"] for ctx in contexts for x in ctx["targets"]})
        self.assertTrue(all(p.grad is None for p in model.parameters()))

    def test_no_second_pass_or_train_forward(self):
        ctx = tiny()[0]
        ctx["x"] = torch.zeros(ctx["length"], 131)
        b = budget()
        r.canonical_pass(r.f5.Student(), [ctx], b)
        with self.assertRaisesRegex(s.Stop, "ACTION_CAP_PASSES"):
            r.canonical_pass(r.f5.Student(), [ctx], b)
        ctx["split"] = "train"
        with self.assertRaisesRegex(s.Stop, "TRAIN_FORWARD_FORBIDDEN"):
            r.canonical_pass(r.f5.Student(), [ctx], budget())

    def test_generated_assembly_decode_forward_measurement_pipeline(self):
        with tempfile.TemporaryDirectory() as temp:
            folder, contexts = Path(temp), tiny()
            state = r.f5.Student().state_dict()
            head = np.zeros(65, dtype="<f4").tobytes()
            pins = {"terminal_state_tensor_sha256": r.f5.tensor_hash(state),
                    "non_head_state_tensor_sha256": r.non_head_hash(state),
                    "head_float32_le_sha256": s.digest(head)}
            b = budget()
            writer = s.Writer(folder, b)
            model, hashes = r.assemble(state, head, pins, b)
            writer.json("assembled_state_before_decode.json", hashes)
            chunks, cursor = [], 0
            for ctx in contexts:
                raw = np.zeros((ctx["length"], 131), dtype="<f4").tobytes()
                ctx.update(offset=cursor, byte_offset=cursor * 524)
                cursor += ctx["length"]
                chunks.append(raw)
                for x in ctx["targets"]:
                    n = x["event"] + 1
                    x["feature_prefix_sha256"] = s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", n, 131) + raw[:n * 524])
            (folder / "features").write_bytes(b"".join(chunks))
            writer.json("ranges.json", contexts)
            loaded = r.feature_contexts(folder / "features", contexts, b, {}, cursor * 524)
            p = r.canonical_pass(model, loaded, b)
            baseline = r.protected_reference(contexts, reference(contexts), False)
            result = r.measurements(p, contexts, baseline, False)
            self.assertEqual(result["status"], s.SCIENTIFIC[1])
            self.assertEqual(r.f5.tensor_hash(model.state_dict()), hashes["assembled_state"])
            self.assertEqual(b.counts["decoded_events"], b.counts["events"])
            self.assertEqual((b.counts["assemblies"], b.counts["passes"]), (1, 1))


def pickle_error():
    import pickle
    return pickle.UnpicklingError("fixture rejection")


class GateTests(unittest.TestCase):
    def measure(self, values=None):
        contexts = tiny()
        baseline = r.protected_reference(contexts, reference(contexts, ["a1"]), False)
        return r.measurements(predictions(contexts, values), contexts, baseline, False)

    def test_attack_zero_tie_passes_benign_zero_fails(self):
        self.assertEqual(self.measure({"a1": 0})["status"], s.SCIENTIFIC[3])
        self.assertEqual(self.measure({"a0": -0.0})["status"], s.SCIENTIFIC[1])

    def test_all_verdict_priorities_and_complete_metrics(self):
        for values, wanted in (({"a1": -1, "a0": 1, "b0": 1}, 0),
                               ({"a0": 1, "b0": 1}, 1), ({"b0": 1}, 2), ({}, 3)):
            result = self.measure(values)
            self.assertEqual(result["status"], s.SCIENTIFIC[wanted])
            self.assertIn("key", result["B_utility"])
            self.assertEqual(result["usable_joint_utility"], wanted == 3)

    def test_context_criterion_only_b_benign(self):
        result = self.measure()
        self.assertEqual(result["B_utility"]["key"]["all_B_benign_normal_contexts"], 1)
        self.assertTrue(result["B_utility_pass"])
        result = self.measure({"b00": 0})
        self.assertEqual(result["B_utility"]["key"]["all_B_benign_normal_contexts"], 0)

    def test_ceil_boundary_and_context_union(self):
        contexts = [context("%02d" % i, [row(str(i), "B0N", "%02d" % i)]) for i in range(11)]
        contexts[0]["targets"].append(row("protected", "A1C", "00"))
        baseline = {"protected": True}
        for n, passed in ((1, False), (2, True)):
            values = {str(i): -1 if i < n else 1 for i in range(11)}
            result = r.measurements(predictions(contexts, values), contexts, baseline, False)
            utility = result["B_utility"]["key"]
            self.assertEqual((utility["target_floor"], utility["context_floor"]), (2, 2))
            self.assertEqual(utility["pass"], passed)
            self.assertEqual(result["groups"]["source"]["dev"]["contexts"], 11)

    def test_incomplete_nonfinite_attachment_rejected(self):
        contexts = tiny()
        baseline = r.protected_reference(contexts, reference(contexts), False)
        for mutation in (lambda p: p.pop("a0w"), lambda p: p["a1"].update(logit=float("nan")),
                         lambda p: p["a1"].update(device_family="changed")):
            p = predictions(contexts)
            mutation(p)
            with self.assertRaises(s.Stop):
                r.measurements(p, contexts, baseline, False)

    def test_protected_baseline_no_unprotected_invention(self):
        contexts = tiny()
        baseline = r.protected_reference(contexts, reference(contexts, ["a1"]), False)
        self.assertEqual(set(baseline), {"a1", "a0", "b1"})
        result = self.measure()
        self.assertEqual(result["protected_comparison"]["newly_correct"], ["a1"])
        self.assertEqual(result["protected_comparison"]["newly_wrong"], [])

    def test_reference_duplicate_wrong_category_and_gates(self):
        contexts = tiny()
        for wrong in (["a1", "a1"], ["a0w"], ["absent"]):
            with self.assertRaises(s.Stop):
                r.protected_reference(contexts, reference(contexts, wrong), False)
        ref = reference(contexts)
        ref["gate_counts"]["val:A1:protected"]["hard"] = 0
        with self.assertRaises(s.Stop):
            r.protected_reference(contexts, ref, False)

    def test_full_denominators_reference_and_utility_floors(self):
        contexts = full_metadata_fixture()
        wrong = [x["uid"] for ctx in contexts for x in ctx["targets"]
                 if x["category"] == "A1C" or (x["category"] == "A0C" and x["source_group"] == "normal_1.pcap")]
        baseline = r.protected_reference(contexts, reference(contexts, wrong))
        result = r.measurements(predictions(contexts), contexts, baseline)
        self.assertEqual(result["status"], s.SCIENTIFIC[3])
        self.assertEqual(len(result["protected_comparison"]["newly_correct"]), 846)
        self.assertEqual(sum(g["target_floor"] for g in result["B_utility"].values()), 373)
        self.assertEqual(sum(g["context_floor"] for g in result["B_utility"].values()), 334)
        for key in s.B_KEYS:
            vals = {x["uid"]: 1 for ctx in contexts for x in ctx["targets"]
                    if x["category"] == "B0N" and x["device_family"] == key}
            failed = r.measurements(predictions(contexts, vals), contexts, baseline)
            self.assertEqual(failed["status"], s.SCIENTIFIC[2])
            self.assertFalse(failed["B_utility"][key]["pass"])


class ControlTests(unittest.TestCase):
    def test_zero_action_caps(self):
        for action in ("lp_calls", "optimizer_steps", "backward_steps", "teacher_forwards",
                       "train_events", "threshold_fits", "retries", "pilots", "hpc_jobs"):
            with self.assertRaises(s.Stop):
                budget().charge(**{action: 1})

    def test_wall_memory_output_caps_and_reserved_receipts(self):
        b = budget(clock=lambda: 2, start=0, caps={**s.CAPS, "wall_seconds": 1})
        with self.assertRaisesRegex(s.Stop, "GLOBAL_WALL_STOP"):
            b.check()
        with self.assertRaisesRegex(s.Stop, "GLOBAL_MEMORY_STOP"):
            s.Budget(memory=lambda: s.CAPS["memory_bytes"] + 1).check()
        b = budget()
        b.output_bytes = s.CAPS["output_bytes"] - s.CAPS["reserve_bytes"] + 1
        with self.assertRaisesRegex(s.Stop, "GLOBAL_OUTPUT_STOP"):
            b.check()

    def test_exclusive_writer(self):
        with tempfile.TemporaryDirectory() as temp:
            writer = s.Writer(temp, budget())
            writer.write("x", b"x")
            with self.assertRaises(s.Stop):
                writer.write("x", b"y")

    def test_status_provisional_final_and_corrupt_seal(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            self.assertEqual(c.status(output)["status"], "NOT_STARTED")
            output.mkdir()
            c.atomic_status(output / "worker_terminal.json", {"verdict": {"status": "N2_ENGINEERING_STOP"}})
            self.assertFalse(c.status(output)["final"])
            c.atomic_status(output / "supervisor_terminal.json", {"verdict": {"status": "N2_ENGINEERING_STOP"}})
            self.assertFalse(c.status(output)["final"])
            sha = s.sha_file(output / "supervisor_terminal.json")
            (output / "SHA256SUMS").write_text(sha + "  supervisor_terminal.json\n", encoding="ascii")
            self.assertTrue(c.status(output)["final"])
            (output / "supervisor_terminal.json").write_text("{}", encoding="ascii")
            self.assertEqual(c.status(output)["status"], "FINAL_SEAL_INVALID_DO_NOT_RESTART")

    def test_unknown_or_incomplete_worker_cannot_pass(self):
        for verdict in ({"status": "unexpected"}, {"status": s.SCIENTIFIC[3]}):
            with self.assertRaises(s.Stop):
                c.validate_worker({"verdict": verdict}, Path("unused"), s.CAPS)

    def test_supervisor_startup_failure_sealed_and_no_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            verdict = c.supervise([], output, synthetic=True,
                                  preflight=lambda: s.require(False, "FIXTURE_PREFLIGHT_STOP"))
            self.assertEqual(verdict["reason"], "FIXTURE_PREFLIGHT_STOP")
            self.assertTrue(c.status(output)["final"])
            with self.assertRaises(FileExistsError):
                c.supervise([], output, synthetic=True)

    def child(self, body, caps=None):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            command = [sys.executable, "-B", "-c", "from pathlib import Path; import sys,time,json,os; "
                       "p=Path(sys.argv[1]); " + body, str(output)]
            verdict = c.supervise(command, output, caps=caps, synthetic=True)
            self.assertTrue(c.status(output)["final"])
            return verdict

    def test_abnormal_exit(self):
        self.assertEqual(self.child("sys.exit(7)")["reason"], "WORKER_EXIT_7")

    def test_corrupt_worker_terminal(self):
        verdict = self.child("(p/'worker_terminal.json').write_text('{broken')")
        self.assertTrue(verdict["reason"].startswith("WORKER_TERMINAL_INVALID_"))

    def test_external_wall_watchdog(self):
        self.assertEqual(self.child("time.sleep(5)", {**s.CAPS, "wall_seconds": 1})["reason"], "GLOBAL_WALL_STOP")

    def test_external_output_watchdog(self):
        verdict = self.child("(p/'large').write_bytes(b'x'*8192); time.sleep(5)",
                             {**s.CAPS, "output_bytes": 8192, "reserve_bytes": 4096})
        self.assertEqual(verdict["reason"], "GLOBAL_OUTPUT_STOP")

    def test_source_has_no_fitting_or_historical_entrypoints(self):
        tree = ast.parse(Path(r.__file__).read_text(encoding="utf-8"))
        calls = [n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                 for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))]
        forbidden = {"backward", "step", "linprog", "solve", "diagnose", "evaluate", "inference_mode",
                     "load_parent", "load_preflight", "load_checkpoint", "memmap", "fromfile", "sigmoid"}
        self.assertFalse(set(calls) & forbidden)
        self.assertEqual(calls.count("load"), 1)
        imports = [n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        self.assertFalse(any(x and ("scipy" in x or "n1_runner" in x) for x in imports))


def run_suite():
    runtime = r.configure_runtime()
    GUARD["active"] = True
    stream = io.StringIO()
    try:
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    finally:
        GUARD["active"] = False
    return {"status": "PASS" if result.wasSuccessful() else "FAIL", "tests_run": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors), "details": stream.getvalue(),
            "runtime": runtime, "historical_artifact_read_guard": "ENFORCED_DURING_TESTS",
            "expected_guard_rejections": GUARD["blocked"], "real_numeric_access": 0,
            "synthetic_processes": "generated exit/corrupt-receipt/wall/output probes only; no resource pilot"}


if __name__ == "__main__":
    report = run_suite()
    print(json.dumps(report), flush=True)
    sys.exit(0 if report["status"] == "PASS" else 1)
