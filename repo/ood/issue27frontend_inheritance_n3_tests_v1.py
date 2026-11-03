"""N3 generated contracts and numerical integration; real artifacts are inaccessible."""
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
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

import numpy as np
import torch
import issue27frontend_inheritance_n3_support_v1 as s
import issue27frontend_inheritance_n3_runner_v1 as r
import issue27frontend_inheritance_n3_control_v1 as c
import issue27frontend_inheritance_n1_math_v1 as m

GUARD = {"active": False, "blocked": 0}


def audit_guard(event, args):
    if GUARD["active"] and event == "open" and isinstance(args[0], (str, bytes, os.PathLike)):
        if os.fsdecode(args[0]).lower() == os.devnull.lower():
            return
        if Path(os.fsdecode(args[0])).resolve().is_relative_to((s.ROOT / "runs").resolve()):
            GUARD["blocked"] += 1
            raise PermissionError("SYNTHETIC_REAL_ARTIFACT_ACCESS_DENIED")


sys.addaudithook(audit_guard)


def budget(**kwargs):
    return s.Budget(memory=lambda: 0, **kwargs)


def context(key, split="internal_val", category="B0N", length=2, source="synthetic", device="key"):
    owner, label, teacher = next(k for k, v in s.CATEGORIES.items() if v == category)
    x = np.full((length, 131), float(len(key)) / 100, dtype=np.float32)
    raw = x.tobytes()
    row = {"uid": key + ":uid", "context_key": key, "event_index": str(length - 1),
           "prefix_events": str(length), "source_group": source, "nested_split": split,
           "owner": owner, "label": label, "teacher_kind": teacher, "device_family": device,
           "attack_family": "generated", "finite": "true", "roundtrip_exact": "true", "feature_width": "131",
           "feature_prefix_sha256": s.digest(b"F4_INPUT_V1\0" + struct.pack("<II", length, 131) + raw),
           "category": category, "protected": category in s.PROTECTED, "event": length - 1,
           "constraint_role": "original_train_retention" if split == "train" else "development_B_release_retention_fit",
           "exposure_role": "fitting"}
    return {"key": key, "split": split, "source": source, "length": length, "count": length,
            "offset": 0, "byte_offset": 0, "byte_length": len(raw), "targets": [row], "x": torch.from_numpy(x)}


def prediction(ctx, value=-1.0):
    row = ctx["targets"][0]
    return {"uid": row["uid"], "context": ctx["key"], "category": row["category"], "source": ctx["source"],
            "device_family": row["device_family"], "attack_family": row["attack_family"],
            "label": int(row["label"]), "protected": row["protected"], "hard": value >= 0, "logit": value}


def fixture():
    train = [context("train", "train", "A0W")]
    dev = [context("dev-a", category="A0C"), context("dev-b"), context("dev-c")]
    tr = {p["uid"]: p for p in map(prediction, train)}
    dr = {p["uid"]: p for p in map(prediction, dev)}
    dr[dev[-1]["targets"][0]["uid"]].update(hard=True, logit=1.0)
    splits = {"train": train, "internal_val": dev}
    roles, fit = r.freeze_roles(splits, tr, dr, False)
    return splits, tr, dr, roles, fit


def affine(conflict=False, tiny=False):
    h = np.zeros((2, 64), dtype=np.float32)
    h[:, 0] = [0, 0] if conflict else [-2**-30, 2**-30] if tiny else [-1, 1]
    return h, np.array([0, 1])


class Contracts(unittest.TestCase):
    def test_guard(self):
        with self.assertRaises(PermissionError):
            (s.ROOT / s.FEATURES).open("rb")

    def test_pin_merge_overlap(self):
        self.assertEqual(s.merge_pins({"a": "x"}, {"a": "x", "b": "y"}), {"a": "x", "b": "y"})
        with self.assertRaises(s.Stop):
            s.merge_pins({"a": "x"}, {"a": "y"})

    def test_roles_include_original_unprotected(self):
        splits, tr, dr, roles, fit = fixture()
        self.assertFalse(roles[-1]["original_protected"])
        self.assertEqual(Counter(p["constraint_role"] for p in roles),
                         {"original_train_retention": 1, "development_protection_fit": 1,
                          "development_B_release_retention_fit": 1, "exposed_report_only": 1})
        self.assertEqual([p["uid"] for p in fit], sorted(p["uid"] for p in fit))

    def test_full_frozen_population_roles(self):
        splits = {"train": [], "internal_val": []}
        refs = {"train": {}, "internal_val": {}}
        for split, counts in (("train", s.base.EXPECTED), ("internal_val", s.EXPECTED)):
            for cat, count in counts.items():
                for i in range(count):
                    ctx = context("%s-%s-%05d" % (split, cat, i), split, cat, 1)
                    p = prediction(ctx, 1.0 if cat in {"A1C", "B1N"} else -1.0)
                    if split == "internal_val" and cat == "B0N" and i >= 2567:
                        p.update(hard=True, logit=1.0)
                    splits[split].append(ctx)
                    refs[split][p["uid"]] = p
        roles, fit = r.freeze_roles(splits, refs["train"], refs["internal_val"])
        self.assertEqual(len(fit), 12711)
        self.assertEqual(sum(x["label"] for x in fit), 2253)
        self.assertEqual(len(roles) - len(fit), 1155)

    def test_train_historical_error_rejected(self):
        sp, tr, dr, _, _ = fixture()
        next(iter(tr.values()))["hard"] = True
        with self.assertRaises(s.Stop):
            r.freeze_roles(sp, tr, dr, False)

    def test_duplicate_cross_split_rejected(self):
        sp, tr, dr, _, _ = fixture()
        dr.update(tr)
        with self.assertRaises(s.Stop):
            r.freeze_roles(sp, tr, dr, False)

    def test_b_inclusion_allows_new_releases(self):
        _, _, dr, _, _ = fixture()
        candidate = copy.deepcopy(dr)
        for p in candidate.values():
            p["hard"] = False
        report = r.retention(candidate, dr, False)["key"]
        self.assertTrue(report["retention_pass"])
        self.assertEqual(len(report["new_releases"]), 1)

    def test_b_same_counts_different_members_rejected(self):
        _, _, dr, _, _ = fixture()
        candidate = copy.deepcopy(dr)
        b = [p for p in candidate.values() if p["category"] == "B0N"]
        for p in b:
            p["hard"] = not p["hard"]
        self.assertFalse(r.retention(candidate, dr, False)["key"]["retention_pass"])

    def test_b_context_only_considers_B_targets(self):
        ctx = context("mixed")
        normal = prediction(ctx)
        attack = {**normal, "uid": "attack", "category": "B1N", "label": 1, "hard": True, "logit": 1.0}
        sets = r.b_sets({normal["uid"]: normal, "attack": attack})
        self.assertEqual(sets["key"]["contexts"], {"mixed"})

    def test_b_context_requires_all_B_normal(self):
        p = prediction(context("mixed"))
        q = {**p, "uid": "second", "hard": True, "logit": 1.0}
        self.assertEqual(r.b_sets({p["uid"]: p, q["uid"]: q})["key"]["contexts"], set())

    def test_metadata_projection_both_splits_forbidden_sentinel(self):
        for kind in ("target", "scope"):
            for split in ("train", "internal_val"):
                seen = []
                def get(key):
                    self.assertNotIn(key, {"l1_prefix_sha256", "old_all_unk"})
                    seen.append(key)
                    return split if key in {"nested_split", "split"} else "x"
                sel, payload = s.project_both(get, kind)
                self.assertEqual(set(seen), set(s.SELECTORS[kind]) | set(s.PAYLOAD[kind]))

    def test_csv_both_payloads_and_excluded_cells(self):
        rows = []
        for split in ("train", "internal_val"):
            row = context(split, split)["targets"][0]
            rows.append([row.get(key, "NEVER_RETAIN") for key in s.TARGET_COLUMNS])
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(s.TARGET_COLUMNS)
        writer.writerows(rows)
        audit = {}
        _, payload = s.scan_csv(gzip.compress(buffer.getvalue().encode()), "target", audit)
        self.assertEqual(len(payload), 2)
        self.assertNotIn("old_all_unk", audit["column_accesses"])
        self.assertEqual(audit["excluded_payload_cells_transiently_tokenized"], 4)

    def test_csv_duplicate_rejected(self):
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(s.SCOPE_COLUMNS)
        writer.writerows([["u", "train", "s", "A", "c"]] * 2)
        with self.assertRaises(s.Stop):
            s.scan_csv(buffer.getvalue().encode(), "scope", {})

    def test_reference_attachment(self):
        ctx = context("c")
        p = prediction(ctx)
        self.assertEqual(r.reference_rows([p], [ctx])[p["uid"]], p)
        p["device_family"] = "changed"
        with self.assertRaises(s.Stop):
            r.reference_rows([p], [ctx])

    def test_reference_nonfinite(self):
        ctx = context("c")
        p = prediction(ctx, float("nan"))
        with self.assertRaises(s.Stop):
            r.reference_rows([p], [ctx])

    def test_baseline_float32_bits_not_counts(self):
        p = prediction(context("c"))
        q = {**p, "logit": float(np.nextafter(np.float32(-1), np.float32(-2)))}
        with self.assertRaises(s.Stop):
            r.compare_baseline({p["uid"]: q}, {p["uid"]: p})

    def test_baseline_signed_zero(self):
        p = prediction(context("c"), 0.0)
        with self.assertRaises(s.Stop):
            r.compare_baseline({p["uid"]: {**p, "logit": -0.0}}, {p["uid"]: p})

    def test_baseline_cannot_reselect_roles(self):
        sp, tr, dr, roles, _ = fixture()
        saved = copy.deepcopy(roles)
        altered = copy.deepcopy(dr)
        next(iter(altered.values()))["logit"] = -2.0
        with self.assertRaises(s.Stop):
            r.compare_baseline(altered, dr)
        self.assertEqual(roles, saved)

    def test_cache_join_once(self):
        ctx = context("train", "train", "A0W")
        raw = np.zeros((1, 64), np.float32).tobytes()
        index = {"uids": [ctx["targets"][0]["uid"]], "protected_uids": [], "shape": [1, 64],
                 "dtype": "float32_le", "sha256": s.digest(raw)}
        b = budget()
        self.assertEqual(len(r.decode_train_cache(raw, index, [ctx], s.digest(raw), b)), 1)
        with self.assertRaises(s.Stop):
            r.decode_train_cache(raw, index, [ctx], s.digest(raw), b)

    def test_cache_original_protections_not_fit(self):
        ctx = context("train", "train", "A0W")
        raw = np.zeros((1, 64), np.float32).tobytes()
        uid = ctx["targets"][0]["uid"]
        index = {"uids": [uid], "protected_uids": [uid], "shape": [1, 64],
                 "dtype": "float32_le", "sha256": s.digest(raw)}
        with self.assertRaises(s.Stop):
            r.decode_train_cache(raw, index, [ctx], s.digest(raw), budget())

    def test_cache_nonfinite(self):
        ctx = context("train", "train", "A0W")
        raw = np.full((1, 64), np.nan, np.float32).tobytes()
        index = {"uids": [ctx["targets"][0]["uid"]], "protected_uids": [], "shape": [1, 64],
                 "dtype": "float32_le", "sha256": s.digest(raw)}
        with self.assertRaises(s.Stop):
            r.decode_train_cache(raw, index, [ctx], s.digest(raw), budget())

    def test_prefix_decode_once_and_hash(self):
        ctx = context("c", "train")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "features"
            path.write_bytes(ctx["x"].numpy().tobytes())
            b = budget()
            loaded = r.feature_contexts(path, [ctx], b, {}, ctx["byte_length"])
            self.assertTrue(torch.equal(loaded[0]["x"], ctx["x"]))
            with self.assertRaises(s.Stop):
                r.feature_contexts(path, [ctx], b, {}, ctx["byte_length"])

    def test_prefix_bad_hash(self):
        ctx = context("c")
        ctx["targets"][0]["feature_prefix_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "features"
            path.write_bytes(ctx["x"].numpy().tobytes())
            with self.assertRaises(s.Stop):
                r.feature_contexts(path, [ctx], budget(), {}, ctx["byte_length"])

    def test_prefix_invalid_offset(self):
        ctx = context("c")
        ctx["byte_offset"] = 1
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "features"
            path.write_bytes(ctx["x"].numpy().tobytes())
            with self.assertRaises(s.Stop):
                r.feature_contexts(path, [ctx], budget(), {}, ctx["byte_length"])

    def test_numeric_input_classification(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / s.HEAD
            path.parent.mkdir(parents=True)
            path.write_bytes(b"generated")
            b, audit = budget(), {}
            inputs = s.Inputs(root, {s.HEAD: s.digest(b"generated")}, b, audit)
            inputs.verify(s.HEAD)
            inputs.read(s.HEAD)
            self.assertEqual(audit["metadata_containers_read"], [])
            self.assertEqual(audit["numerical_containers_read"][0]["bytes"], 9)

    def test_minimal_projection_never_indexes_ledger(self):
        class Sentinel(dict):
            def __getitem__(self, key):
                if key in {"epoch_ledger", "optimizer", "rng"}:
                    raise AssertionError(key)
                return super().__getitem__(key)
        progress = Sentinel(epoch=21, cursor=0, order=[], steps=3120, stop_reached=True,
                            selection={"best_epoch": None, "last_epoch": 20})
        container = Sentinel(model={"x": 1}, identities={"a": 1}, progress=progress)
        audit = {}
        state, projection = r.project_checkpoint(container, {"a": 1}, audit)
        self.assertEqual(state, {"x": 1})
        self.assertEqual(audit["checkpoint_projection"]["ledger_values_indexed"], 0)

    def test_restricted_load_restores_safe_globals(self):
        progress = {"epoch": 21, "cursor": 0, "order": [], "steps": 3120, "stop_reached": True,
                    "selection": {"best_epoch": None, "last_epoch": 20}, "epoch_ledger": ["incidental"]}
        data = io.BytesIO()
        torch.save({"model": {"x": torch.ones(1)}, "identities": {}, "progress": progress,
                    "optimizer": {"unused": 1}}, data)
        terminal = {"status": "F5_NO_ELIGIBLE_CHECKPOINT", "complete": True, "selected_epoch": None,
                    "epochs": 20, "steps": 3120}
        old = torch.serialization.get_safe_globals()
        torch.serialization.add_safe_globals([NS])
        try:
            expected = torch.serialization.get_safe_globals()
            original = torch.load
            def checked(*args, **kwargs):
                self.assertEqual(kwargs, {"map_location": "cpu", "weights_only": True})
                self.assertNotIn(NS, torch.serialization.get_safe_globals())
                return original(*args, **kwargs)
            with patch.object(torch, "load", checked):
                r.restricted_checkpoint(data.getvalue(), s.digest(data.getvalue()), {}, terminal, {}, budget())
            self.assertEqual(torch.serialization.get_safe_globals(), expected)
        finally:
            torch.serialization.clear_safe_globals()
            torch.serialization.add_safe_globals(old)

    def test_bad_checkpoint_no_fallback(self):
        terminal = {"status": "F5_NO_ELIGIBLE_CHECKPOINT", "complete": True, "selected_epoch": None,
                    "epochs": 20, "steps": 3120}
        before = torch.serialization.get_safe_globals()
        with self.assertRaisesRegex(s.Stop, "GOVERNED_MODEL_EXPORT"):
            r.restricted_checkpoint(b"invalid", s.digest(b"invalid"), {}, terminal, {}, budget())
        self.assertEqual(before, torch.serialization.get_safe_globals())

    def test_canonical_hook_order_and_state(self):
        model = r.f5.Student()
        contexts = [context("a", length=1), context("b", length=4), context("c", length=2)]
        before = r.f5.tensor_hash(model.state_dict())
        p, v, h = r.canonical_pass(model, contexts, budget(), "baseline_dev")
        p2, v2, h2 = r.canonical_pass(model, contexts, budget(), "candidate_dev")
        r.compare_vectors(v, v2, h, h2)
        self.assertEqual(before, r.f5.tensor_hash(model.state_dict()))
        self.assertEqual(p, p2)
        self.assertEqual({k: v["rows"] for k, v in h.items()}, {"a": 1, "b": 4, "c": 2})
        self.assertEqual(len(model.head_output._forward_pre_hooks), 0)

    def test_original_batch_boundaries(self):
        model = r.f5.Student()
        contexts = [context("%03d" % i, length=1) for i in range(33)]
        b = budget()
        r.canonical_pass(model, contexts, b, "baseline_dev")
        self.assertEqual(b.counts["batches"], 2)
        self.assertEqual(b.counts["contexts"], 33)

    def test_baseline_train_prohibited(self):
        with self.assertRaises(s.Stop):
            r.canonical_pass(r.f5.Student(), [context("t", "train")], budget(), "baseline_dev")

    def test_mixed_candidate_split_prohibited(self):
        with self.assertRaises(s.Stop):
            r.canonical_pass(r.f5.Student(), [context("a", "train"), context("b")], budget(), "candidate_train")

    def test_context_cache_corruption(self):
        v = {"u": np.zeros(64, np.float32)}
        changed = {"u": np.ones(64, np.float32)}
        with self.assertRaises(s.Stop):
            r.compare_vectors(v, changed, {"c": 1}, {"c": 1})
        with self.assertRaises(s.Stop):
            r.compare_vectors(v, v, {"c": 1}, {"c": 2})

    def test_candidate_separate_and_single_install(self):
        model = r.f5.Student()
        before = r.f5.tensor_hash(model.state_dict())
        theta = np.zeros(65, np.float32)
        theta[-1] = -1
        b = budget()
        candidate = r.install_candidate(model, theta, b)
        self.assertIsNot(candidate, model)
        self.assertEqual(before, r.f5.tensor_hash(model.state_dict()))
        self.assertEqual(r.non_head_hash(model.state_dict()), r.non_head_hash(candidate.state_dict()))
        with self.assertRaises(s.Stop):
            r.install_candidate(model, theta, b)

    def test_source_no_historical_entrypoints_or_training(self):
        tree = ast.parse(Path(r.__file__).read_text())
        calls = [n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                 for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))]
        self.assertFalse(set(calls) & {"backward", "step", "diagnose", "inference_mode", "memmap", "fromfile",
                                      "load_parent", "load_preflight", "load_checkpoint", "sigmoid"})
        self.assertEqual(calls.count("load"), 1)
        self.assertEqual(calls.count("solve_once"), 1)
        self.assertEqual(calls.count("sole_candidate"), 1)

    def test_generated_full_pipeline(self):
        model = r.f5.Student()
        with torch.no_grad():
            model.head_output.weight.zero_()
            model.head_output.bias.fill_(-1)
        splits = {"train": [context("train", "train", "A0W")],
                  "internal_val": [context("dev-a", category="A0C"), context("dev-b")]}
        tr = {p["uid"]: p for p in map(prediction, splits["train"])}
        dr = {p["uid"]: p for p in map(prediction, splits["internal_val"])}
        roles, fit = r.freeze_roles(splits, tr, dr, False)
        _, tv, th = r.canonical_pass(model, splits["train"], budget(), "candidate_train")
        with tempfile.TemporaryDirectory() as temp:
            b = budget()
            result = r.fit_once(model, splits, tv, th, tr, dr, roles, fit, s.Writer(temp, b), b, False)
            self.assertEqual(result["status"], s.SCIENTIFIC[0])
            self.assertEqual(b.counts["passes"], 3)
            self.assertEqual(b.counts["lp_calls"], 1)
            self.assertEqual(b.counts["candidate_casts"], 1)
            report = json.loads((Path(temp) / "joint_measurements.json").read_text())
            self.assertEqual(report["targets"], 3)
            self.assertEqual(result["broader_inheritance"], "NOT_PROVED")


    def pipeline_fixture(self, solver=None, mismatched_baseline=False):
        model = r.f5.Student()
        with torch.no_grad():
            model.head_output.weight.zero_()
            model.head_output.bias.fill_(-1)
        splits, tr, dr, roles, fit = fixture()
        # The last B row is a generated exposed residual, outside the fit.
        for p in dr.values():
            p.update(logit=-1.0, hard=False)
        if mismatched_baseline:
            next(iter(dr.values()))["logit"] = -2.0
        _, tv, th = r.canonical_pass(model, splits["train"], budget(), "candidate_train")
        with tempfile.TemporaryDirectory() as temp:
            b = budget()
            result = r.fit_once(model, splits, tv, th, tr, dr, roles, fit, s.Writer(temp, b), b,
                                False, solver)
            report = json.loads((Path(temp) / "joint_measurements.json").read_text())
            return result, report, b.counts

    def test_scientific_failure_finishes_both_passes_and_residual(self):
        def solver(*args, **kwargs):
            return NS(status=1, message="generated timeout candidate", nit=0,
                      x=np.r_[np.zeros(64), 1., 0.])
        result, report, counts = self.pipeline_fixture(solver)
        self.assertEqual(result["status"], s.SCIENTIFIC[2])
        self.assertFalse(report["float32_pass"])
        self.assertEqual(len(report["report_only"]), 1)
        self.assertEqual(counts["passes"], 3)
        self.assertEqual(counts["candidate_train_targets"], 1)
        self.assertEqual(counts["candidate_dev_targets"], 3)

    def test_no_candidate_has_no_install_or_replay(self):
        def solver(*args, **kwargs):
            return NS(status=1, message="generated timeout without candidate", nit=0, x=None)
        result, report, counts = self.pipeline_fixture(solver)
        self.assertEqual(result["status"], s.SCIENTIFIC[2])
        self.assertFalse(result["candidate_present"])
        self.assertEqual(counts["passes"], 1)
        self.assertEqual(counts["installations"], 0)
        self.assertEqual(counts["candidate_casts"], 0)

    def test_baseline_mismatch_prevents_any_solver_call(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("solver reached")
        with self.assertRaisesRegex(s.Stop, "BASELINE_N2_BITWISE_MISMATCH"):
            self.pipeline_fixture(forbidden, True)

    def test_residual_labels_do_not_enter_solver(self):
        seen = []
        def solver(*args, **kwargs):
            seen.append(kwargs["A_ub"].shape[0])
            return NS(status=1, message="generated", nit=0, x=None)
        _, report, _ = self.pipeline_fixture(solver)
        self.assertEqual(seen, [3])
        self.assertEqual(len(report["roles"]), 4)


class Mathematics(unittest.TestCase):
    def test_separable_and_repeatability(self):
        h, y = affine()
        results = []
        for _ in range(2):
            _, lp, _ = m.solve_once(h, y, budget())
            theta = m.sole_candidate(lp)
            self.assertTrue(m.exact_signs(h, y, theta, m.ExactBudget())["pass"])
            results.append(theta.tobytes())
        self.assertEqual(*results)

    def test_tiny_positive_is_not_gamma_gate(self):
        h, y = affine(tiny=True)
        theta = np.zeros(65, np.float32)
        theta[0] = 1
        self.assertTrue(m.exact_signs(h, y, theta, m.ExactBudget())["pass"])

    def test_attack_zero_benign_zero(self):
        h, y = affine(conflict=True)
        check = m.exact_signs(h, y, np.zeros(65, np.float32), m.ExactBudget())
        self.assertEqual(check["wrong_row_indices"], [0])
        self.assertEqual(check["zero_margin_attack_ties"], 1)

    def test_nonseparable_exact_certificate(self):
        h, y = affine(conflict=True)
        a, lp, _ = m.solve_once(h, y, budget())
        certificate = m.certificate(a, lp, False, m.ExactBudget())
        self.assertTrue(certificate["verified"])

    def test_timeout_partial_sole_candidate(self):
        lp = NS(status=1, x=np.r_[np.zeros(64), -1., np.nan])
        self.assertEqual(m.sole_candidate(lp)[-1], -1)
        self.assertIsNone(m.sole_candidate(NS(status=1, x=None)))

    def test_false_infeasible_and_unbounded(self):
        for status in (2, 3):
            with self.assertRaises(s.Stop):
                m.sole_candidate(NS(status=status))

    def test_candidate_nonfinite_and_out_of_box(self):
        self.assertIsNone(m.sole_candidate(NS(status=0, x=np.full(66, np.nan))))
        with self.assertRaises(s.Stop):
            m.sole_candidate(NS(status=0, x=np.full(66, 2.0)))

    def test_lp_no_retry(self):
        h, y = affine()
        b = budget()
        m.solve_once(h, y, b)
        with self.assertRaises(s.Stop):
            m.solve_once(h, y, b)

    def test_solver_recipe(self):
        h, y = affine()
        def solver(c, **kw):
            self.assertEqual(kw["method"], "highs-ds")
            self.assertEqual(kw["options"], m.OPTIONS)
            self.assertEqual(kw["bounds"], [(-1, 1)] * 65 + [(None, None)])
            self.assertEqual(kw["A_ub"].shape, (2, 66))
            return NS(status=1, message="timeout", nit=1, x=None)
        m.solve_once(h, y, budget(), solver)

    def test_exact_timeout_and_bits_unknown(self):
        h, y = affine()
        theta = np.ones(65, np.float32)
        time_stage = m.ExactBudget(clock=lambda: 0, seconds=-1)
        self.assertEqual(m.exact_signs(h, y, theta, time_stage)["status"], "EXACT_TIME_STOP")
        stage = m.ExactBudget(bits=2)
        with self.assertRaises(m.ExactStop):
            stage.mul(Fraction(3), Fraction(3))

    def test_certificate_corruption(self):
        h, y = affine(conflict=True)
        a = m.problem(h, y)
        self.assertTrue(m.verify_certificate(a, [0, 1], [Fraction(1, 2)] * 2, m.ExactBudget()))
        self.assertFalse(m.verify_certificate(a, [0, 1], [Fraction(1, 3)] * 2, m.ExactBudget()))
        self.assertFalse(m.verify_certificate(a, [0, 0], [Fraction(1, 2)] * 2, m.ExactBudget()))

    def test_certificate_support_bounds_no_epsilon(self):
        a = np.zeros((67, 65))
        lp = NS(status=0, ineqlin=NS(marginals=np.full(67, -1e-300)))
        self.assertEqual(m.certificate(a, lp, False, m.ExactBudget())["status"], "UNAVAILABLE_SUPPORT")
        lp.ineqlin.marginals[:] = 0
        self.assertEqual(m.certificate(a, lp, False, m.ExactBudget())["status"], "UNAVAILABLE_SUPPORT")

    def test_certificate_rank_free_variables_zero(self):
        a = np.zeros((2, 65))
        self.assertEqual(m.reconstruct(a, [0, 1], m.ExactBudget()), [Fraction(1), Fraction(0)])

    def test_certificate_inconsistent_support(self):
        h, y = affine()
        self.assertIsNone(m.reconstruct(m.problem(h, y), [0], m.ExactBudget()))

    def test_exact_witness_skips_negative(self):
        self.assertFalse(m.certificate(None, None, True, m.ExactBudget())["verified"])

    def test_actual_linear_rounding_distinct_from_exact(self):
        h = np.zeros((1, 64), np.float32)
        h[0, :3] = [1e8, 1, -1e8]
        theta = np.ones(65, np.float32)
        theta[-1] = -0.5
        layer = torch.nn.Linear(64, 1)
        with torch.no_grad():
            layer.weight.copy_(torch.from_numpy(theta[:64].reshape(1, 64)))
            layer.bias.copy_(torch.from_numpy(theta[64:]))
            q = float(layer(torch.from_numpy(h))[0, 0])
        exact = m.exact_signs(h, np.array([0]), theta, m.ExactBudget())
        self.assertFalse(exact["pass"])
        self.assertLess(q, 0)

    def test_negative_stage_time_and_bit_limits(self):
        h, y = affine(conflict=True)
        a = m.problem(h, y)
        lp = NS(status=0, ineqlin=NS(marginals=np.array([-0.5, -0.5])))
        self.assertEqual(m.certificate(a, lp, False, m.ExactBudget(seconds=-1))["status"], "EXACT_TIME_STOP")
        self.assertEqual(m.certificate(a, lp, False, m.ExactBudget(bits=1))["status"], "EXACT_BIT_STOP")

    def test_verdict_precedence(self):
        self.assertEqual(r.verdict(True, True, False)["status"], s.SCIENTIFIC[0])
        self.assertEqual(r.verdict(False, True, True)["status"], s.SCIENTIFIC[1])
        self.assertEqual(r.verdict(False, True, True)["fit_descriptor"], "FLOAT32_ONLY_FIT")
        self.assertEqual(r.verdict(True, False, False)["status"], s.SCIENTIFIC[2])
        self.assertEqual(r.verdict(True, True, False, "integrity")["status"], "N3_ENGINEERING_STOP")
        with self.assertRaises(s.Stop):
            r.verdict(True, True, True)


class Supervision(unittest.TestCase):
    def test_status_missing_provisional_and_corrupt_seal(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            self.assertEqual(c.status(output)["status"], "NOT_STARTED")
            output.mkdir()
            c.atomic_status(output / "worker_terminal.json", {"verdict": {"status": "N3_ENGINEERING_STOP"}})
            self.assertFalse(c.status(output)["final"])
            c.atomic_status(output / "supervisor_terminal.json", {"verdict": {"status": "N3_ENGINEERING_STOP"}})
            sha = s.sha_file(output / "supervisor_terminal.json")
            (output / "SHA256SUMS").write_text(sha + "  supervisor_terminal.json\n")
            self.assertTrue(c.status(output)["final"])
            (output / "supervisor_terminal.json").write_text("{}")
            self.assertEqual(c.status(output)["status"], "FINAL_SEAL_INVALID_DO_NOT_RESTART")

    def test_worker_incomplete_positive_rejected(self):
        for status in s.SCIENTIFIC:
            with self.assertRaises(s.Stop):
                c.validate_worker({"verdict": {"status": status}}, Path("unused"), s.CAPS)

    def test_startup_failure_and_no_restart(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            result = c.supervise([], output, synthetic=True,
                                 preflight=lambda: s.require(False, "GENERATED_PREFLIGHT_STOP"))
            self.assertEqual(result["reason"], "GENERATED_PREFLIGHT_STOP")
            self.assertTrue(c.status(output)["final"])
            with self.assertRaises(FileExistsError):
                c.supervise([], output, synthetic=True)

    def child(self, body, caps=None):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "attempt"
            command = [sys.executable, "-B", "-c", "from pathlib import Path; import sys,time,json,os; "
                       "p=Path(sys.argv[1]); " + body, str(output)]
            result = c.supervise(command, output, caps=caps, synthetic=True)
            self.assertTrue(c.status(output)["final"])
            return result

    def test_abnormal_exit(self):
        self.assertEqual(self.child("sys.exit(7)")["reason"], "WORKER_EXIT_7")

    def test_corrupt_terminal(self):
        self.assertTrue(self.child("(p/'worker_terminal.json').write_text('{broken')")["reason"].startswith("WORKER_TERMINAL_INVALID"))

    def test_missing_terminal(self):
        self.assertEqual(self.child("pass")["reason"], "WORKER_TERMINAL_MISSING")

    def test_external_wall(self):
        self.assertEqual(self.child("time.sleep(5)", {**s.CAPS, "wall_seconds": 1})["reason"], "GLOBAL_WALL_STOP")

    def test_external_output(self):
        result = self.child("(p/'large').write_bytes(b'x'*8192); time.sleep(5)",
                            {**s.CAPS, "output_bytes": 8192, "reserve_bytes": 4096})
        self.assertEqual(result["reason"], "GLOBAL_OUTPUT_STOP")

    def test_memory_cooperative_cap(self):
        with self.assertRaisesRegex(s.Stop, "GLOBAL_MEMORY_STOP"):
            s.Budget(memory=lambda: 100, caps={**s.CAPS, "memory_bytes": 10}).check()

    def test_external_memory_monitor(self):
        with patch.object(s, "peak_memory", return_value=s.CAPS["memory_bytes"] + 1):
            self.assertEqual(self.child("time.sleep(5)")["reason"], "GLOBAL_MEMORY_STOP")

    def test_action_caps(self):
        for key in ("lp_calls", "candidate_casts", "loads", "cache_decodes", "installations"):
            with self.assertRaises(s.Stop):
                budget().charge(**{key: 2})
        for key in ("optimizer_steps", "teacher_forwards", "baseline_train_passes", "retries"):
            with self.assertRaises(s.Stop):
                budget().charge(**{key: 1})

    def test_writer_exclusive(self):
        with tempfile.TemporaryDirectory() as temp:
            writer = s.Writer(temp, budget())
            writer.write("one", b"1")
            with self.assertRaises(s.Stop):
                writer.write("one", b"2")


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
            "synthetic_processes": "generated supervisor contract checks only; no resource pilot"}


if __name__ == "__main__":
    report = run_suite()
    print(json.dumps(report), flush=True)
    sys.exit(0 if report["status"] == "PASS" else 1)
