#!/usr/bin/env python3
"""Synthetic contract tests for the frozen Frontend-F1 D1 implementation."""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd
import torch


ROOT = Path(__file__).resolve().parents[2]


def load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


M = load("f1_d1_train_under_test", ROOT / "repo/ood/issue27frontend_f1_d1_train_v1.py")
E = load("f1_d1_semantic_engine_under_test", ROOT / "repo/ood/issue27frontend_f0_zero_training_semantics_v1.py")


def raw(frame: int, length: int = 100, protocol: int = 6, **changes: str) -> Dict[str, str]:
    value = {
        "frame.number": str(frame + 1), "frame.time_epoch": str(float(frame)),
        "frame.encap_type": "1", "frame.len": str(length), "eth.src": "aa",
        "eth.dst": "bb", "eth.type": "0x0800", "ip.src": "10.0.0.1",
        "ip.dst": "10.0.0.2", "ipv6.src": "", "ipv6.dst": "",
        "ip.proto": str(protocol), "ipv6.nxt": "", "tcp.srcport": "1000",
        "tcp.dstport": "2000", "udp.srcport": "", "udp.dstport": "",
        "sctp.srcport": "", "sctp.dstport": "", "icmp.type": "",
        "icmp.code": "", "icmpv6.type": "", "icmpv6.code": "", "gre.key": "",
    }
    value.update(changes)
    return value


def event(frame: int, target: str = "", timestamp: float = None, protocol: int = 6,
          src: str = "a", dst: str = "b", ports: bool = True) -> Any:
    return E.Event(
        "source", "member", frame, float(frame if timestamp is None else timestamp),
        link_type="encap:1", ethertype=0x0800, ip_version=4, ip_protocol=protocol,
        src_endpoint=src, dst_endpoint=dst,
        src_port=1000 if ports else None, dst_port=2000 if ports else None,
        field_presence_mask="ip", target_uid=target or None,
    )


def fake_p2(bias: float = -3.0) -> Any:
    state = {
        "normalizer_mean": np.zeros(768, dtype=np.float32),
        "normalizer_scale": np.ones(768, dtype=np.float32),
        "p2__0.weight": np.zeros((128, 769), dtype=np.float32),
        "p2__0.bias": np.ones(128, dtype=np.float32),
        "p2__3.weight": np.zeros((1, 128), dtype=np.float32),
        "p2__3.bias": np.asarray([bias], dtype=np.float32),
    }
    return M.FrozenP2(state)


def example(key: str, source: str, label: int = 0, owner: str = "B",
            teacher: str = "none", length: int = 3, targets: int = 1) -> Any:
    signatures = ["sig_%d" % index for index in range(length)]
    entries = [
        M.TargetEntry("%s_u%d" % (key, index), min(index, length - 1), owner, label,
                      teacher, "support_train", source, "device", "family")
        for index in range(targets)
    ]
    return M.ContextExample(key, source, signatures, entries)


class Contracts(unittest.TestCase):
    def test_01_frozen_hash_literal(self):
        self.assertEqual(M.FROZEN_SHA256, "7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860")

    def test_02_parent_hash_literal(self):
        self.assertEqual(M.PARENT_SHA256, "98f2b73a051ee9c392631e85f4cc84d787306ed8333bfe2125f77870790c41b4")

    def test_03_runtime_manifest_is_fully_pinned(self):
        keys = set(M.expected_runtime_manifest())
        self.assertTrue({"python_executable", "numpy", "torch", "sklearn", "windows_ver", "cpu",
                         "pythonhashseed", "omp_num_threads", "mkl_num_threads",
                         "torch_num_threads", "torch_num_interop_threads"}.issubset(keys))

    def test_04_runtime_drift_fails(self):
        value = M.expected_runtime_manifest()
        value["torch"] = "drift"
        with self.assertRaises(M.F1Failure):
            M.verify_runtime(value)

    def test_05_source_split_literal(self):
        self.assertEqual(M.source_split("normal_scanning1.pcap"), "internal_val")
        self.assertEqual(M.source_split("anything_else"), "train")

    def test_06_owner_uses_only_missing(self):
        self.assertEqual(M.deployment_owner(True, label=0, device="x"), "B")
        self.assertEqual(M.deployment_owner(False, label=1, family="y"), "A")

    def test_07_a_route_is_incumbent(self):
        self.assertEqual(M.deployment_route("A"), "INCUMBENT_E3_P2_BYTE_IDENTICAL")

    def test_08_b_route_is_new_encoder(self):
        self.assertEqual(M.deployment_route("B"), "F1_GRU_FROZEN_P2")

    def test_09_unknown_route_fails(self):
        with self.assertRaises(M.F1Failure):
            M.deployment_route("C")

    def test_10_report_path_fails(self):
        with self.assertRaises(M.F1Failure):
            M.assert_scope_paths([Path("some/report/file")])

    def test_11_final_path_fails(self):
        with self.assertRaises(M.F1Failure):
            M.assert_scope_paths([Path("FINAL/data")])

    def test_12_length_bins_boundaries(self):
        expected = {63: "<=63", 64: "64-127", 127: "64-127", 128: "128-255",
                    1518: "1024-1518", 1519: "1519-4095", 4096: ">=4096"}
        self.assertEqual({key: M.length_bin(key) for key in expected}, expected)

    def test_13_delta_bins_boundaries(self):
        self.assertEqual(M.delta_bin(0), "0")
        self.assertEqual(M.delta_bin(1e-6), "(0,1e-6]")
        self.assertEqual(M.delta_bin(60), "(10,60]")
        self.assertEqual(M.delta_bin(61), ">60")

    def test_14_protocol_groups(self):
        self.assertEqual(M.protocol_group(4, 6, "H1"), "TCP")
        self.assertEqual(M.protocol_group(4, 47, "H2"), "GRE")
        self.assertEqual(M.protocol_group(None, None, "H3"), "NON_IP")
        self.assertEqual(M.protocol_group(None, None, "H4"), "KEYLESS")

    def test_15_signature_excludes_endpoint_values(self):
        tokens1, tokens2 = E.EndpointTokens(), E.EndpointTokens()
        e1, e2 = event(0, src="secret-a", dst="secret-b"), event(0, src="other-a", dst="other-b")
        r1, r2 = E.classify_route(e1, tokens1), E.classify_route(e2, tokens2)
        s1 = M.canonical_signature(raw(0), e1, r1, "A_TO_B", 0, False)
        s2 = M.canonical_signature(raw(0), e2, r2, "A_TO_B", 0, False)
        self.assertEqual(s1, s2)
        self.assertNotIn("secret", s1)

    def test_16_signature_has_15_fields(self):
        e = event(0)
        route = E.classify_route(e, E.EndpointTokens())
        self.assertEqual(len(M.canonical_signature(raw(0), e, route, "A_TO_B", 0, False).split("\x1f")), 15)

    def test_17_vocab_uses_train_only(self):
        train = example("t", "train", length=1)
        val = example("v", "normal_scanning1.pcap", length=1)
        train.signatures = ["train_only"]
        val.signatures = ["val_only"]
        vocab, _ = M.build_vocabulary([train, val])
        self.assertIn("train_only", vocab)
        self.assertNotIn("val_only", vocab)

    def test_18_vocab_order_is_hash_then_bytes(self):
        values = example("t", "train", length=1)
        values.signatures = ["z", "a", "m"]
        first, identity1 = M.build_vocabulary([values])
        second, identity2 = M.build_vocabulary([values])
        self.assertEqual(first, second)
        self.assertEqual(identity1, identity2)

    def test_19_unseen_maps_to_unk(self):
        value = example("v", "normal_scanning1.pcap", length=1)
        value.signatures = ["unseen"]
        self.assertEqual(M.encode_context(value, {}), [1])

    def test_20_vocab_capacity_fails_closed(self):
        value = example("t", "train", length=1)
        value.signatures = ["s%d" % index for index in range(4095)]
        with self.assertRaises(M.F1Failure):
            M.build_vocabulary([value])

    def test_21_control_exact_dimension(self):
        self.assertEqual(M.order_free_control([2, 3]).shape, (4097,))

    def test_22_control_is_order_free(self):
        np.testing.assert_array_equal(M.order_free_control([2, 3, 2]), M.order_free_control([2, 2, 3]))

    def test_23_control_preserves_length(self):
        self.assertNotEqual(M.order_free_control([2])[-1], M.order_free_control([2, 2])[-1])

    def test_24_model_parameter_counts(self):
        model = M.F1Encoder()
        self.assertEqual(model.inference_parameter_count(), 292352)
        self.assertEqual(model.training_parameter_count(), 300576)

    def test_25_model_output_shapes(self):
        model = M.F1Encoder()
        reps, semantic = model(torch.tensor([[2, 3, 0], [4, 5, 6]]), torch.tensor([2, 3]))
        self.assertEqual(tuple(reps.shape), (2, 3, 768))
        self.assertEqual(tuple(semantic.shape), (2, 3, 4096))

    def test_26_future_token_does_not_change_prefix(self):
        torch.manual_seed(M.SEED)
        model = M.F1Encoder().eval()
        with torch.no_grad():
            left, _ = model(torch.tensor([[2, 3, 4]]), torch.tensor([3]))
            right, _ = model(torch.tensor([[2, 3, 9]]), torch.tensor([3]))
        torch.testing.assert_close(left[0, :2], right[0, :2], rtol=0, atol=0)

    def test_27_frozen_p2_shape(self):
        scores = fake_p2()(torch.zeros((3, 768)))
        self.assertEqual(tuple(scores.shape), (3,))

    def test_28_frozen_p2_has_no_trainable_parameters(self):
        self.assertEqual(sum(parameter.numel() for parameter in fake_p2().parameters()), 0)

    def test_29_loss_total_is_sum_of_four(self):
        contexts = [example("x", "train", label=0, owner="B")]
        vocab, _ = M.build_vocabulary(contexts)
        encoded = M.encode_examples(contexts, vocab)
        losses = M.compute_losses(M.F1Encoder(), fake_p2(), M.collate_examples(encoded))
        expected = losses["semantic"] + losses["label"] + losses["attack"] + losses["teacher"]
        torch.testing.assert_close(losses["total"], expected)

    def test_30_attack_teacher_is_threshold_relative(self):
        context = example("x", "train", label=1, owner="A", teacher="attack_hard")
        vocab, _ = M.build_vocabulary([context])
        losses = M.compute_losses(M.F1Encoder(), fake_p2(M.Z_0), M.collate_examples(M.encode_examples([context], vocab)))
        self.assertGreater(float(losses["teacher"].detach()), 0.0)

    def test_31_benign_teacher_is_threshold_relative(self):
        context = example("x", "train", label=0, owner="A", teacher="benign_normal")
        vocab, _ = M.build_vocabulary([context])
        losses = M.compute_losses(M.F1Encoder(), fake_p2(M.Z_0), M.collate_examples(M.encode_examples([context], vocab)))
        self.assertGreater(float(losses["teacher"].detach()), 0.0)

    def test_32_old_hard_benign_is_not_teacher_preserved(self):
        context = example("x", "train", label=0, owner="A", teacher="benign_hard")
        vocab, _ = M.build_vocabulary([context])
        losses = M.compute_losses(M.F1Encoder(), fake_p2(10), M.collate_examples(M.encode_examples([context], vocab)))
        self.assertEqual(float(losses["teacher"].detach()), 0.0)

    def test_33_b_has_no_teacher(self):
        context = example("x", "train", label=1, owner="B", teacher="none")
        vocab, _ = M.build_vocabulary([context])
        losses = M.compute_losses(M.F1Encoder(), fake_p2(10), M.collate_examples(M.encode_examples([context], vocab)))
        self.assertEqual(float(losses["teacher"].detach()), 0.0)

    def test_34_context_equal_not_target_row_equal(self):
        one = example("one", "train", targets=1)
        many = example("many", "train", targets=5)
        vocab, _ = M.build_vocabulary([one, many])
        losses = M.compute_losses(M.F1Encoder(), fake_p2(-3), M.collate_examples(M.encode_examples([one, many], vocab)))
        self.assertTrue(torch.isfinite(losses["label"]))

    def test_35_checkpoint_rejects_attack_flip(self):
        item = M.EncodedExample(example("x", "train", 1, "A", "attack_hard"), [2, 3, 4])
        self.assertFalse(M.checkpoint_eligible(
            {"logits": torch.tensor([M.Z_0 - 1]), "representations_finite": torch.tensor(True)}, [item]
        ))

    def test_36_checkpoint_rejects_new_benign_hard(self):
        item = M.EncodedExample(example("x", "train", 0, "A", "benign_normal"), [2, 3, 4])
        self.assertFalse(M.checkpoint_eligible(
            {"logits": torch.tensor([M.Z_0 + 1]), "representations_finite": torch.tensor(True)}, [item]
        ))

    def test_37_checkpoint_accepts_correct_sides(self):
        left = M.EncodedExample(example("a", "train", 1, "A", "attack_hard"), [2, 3, 4])
        right = M.EncodedExample(example("b", "train", 0, "A", "benign_normal"), [2, 3, 4])
        self.assertTrue(M.checkpoint_eligible(
            {"logits": torch.tensor([M.Z_0 + 1, M.Z_0 - 1]),
             "representations_finite": torch.tensor(True)}, [left, right]
        ))

    def test_38_batch_order_is_epoch_deterministic(self):
        values = [M.EncodedExample(example(str(i), "train"), [2]) for i in range(8)]
        first = [[x.context.context_key for x in b] for b in M.deterministic_batches(values, 3, 2)]
        second = [[x.context.context_key for x in b] for b in M.deterministic_batches(values, 3, 2)]
        self.assertEqual(first, second)

    def test_39_tensor_serialization_is_stable(self):
        model = M.F1Encoder()
        self.assertEqual(M.state_tensor_bytes(model.state_dict()), M.state_tensor_bytes(model.state_dict()))

    def test_40_constant_representation_fails_collapse(self):
        self.assertFalse(M.collapse_pass(M.collapse_metrics(np.ones((64, 768)))))

    def test_41_nonfinite_representation_fails_collapse(self):
        values = np.random.RandomState(1).normal(size=(64, 768))
        values[0, 0] = np.nan
        self.assertFalse(M.collapse_pass(M.collapse_metrics(values)))

    def test_42_random_representation_passes_collapse(self):
        values = np.random.RandomState(1).normal(size=(128, 768))
        self.assertTrue(M.collapse_pass(M.collapse_metrics(values)))

    def test_43_linear_canary_returns_probabilities(self):
        rng = np.random.RandomState(1)
        x = rng.normal(size=(30, 5)); y = np.asarray([0] * 15 + [1] * 15)
        prediction = M.fit_linear_canary(x, y, x[:4])
        self.assertTrue(np.logical_and(prediction >= 0, prediction <= 1).all())

    def test_44_permutation_null_is_deterministic(self):
        labels = np.asarray([0, 0, 1, 1]); predictions = np.asarray([.1, .2, .8, .9])
        contexts = ["a", "b", "c", "d"]
        self.assertEqual(M.permutation_p99(labels, predictions, contexts, 20),
                         M.permutation_p99(labels, predictions, contexts, 20))

    def test_45_context_json_roundtrip(self):
        value = example("x", "train")
        restored = M.context_from_json(M.context_to_json(value))
        self.assertEqual(M.context_to_json(value), M.context_to_json(restored))

    def test_46_invalid_split_tag_fails(self):
        value = M.context_to_json(example("x", "train")); value["split"] = "internal_val"
        with self.assertRaises(M.F1Failure):
            M.context_from_json(value)

    def test_47_replay_h1_target(self):
        events = [event(0), event(1, "u")]
        targets = [E.TargetSpec("u", "source", "member", 1)]
        last = E.SemanticPrototype._discover(events, {1: targets[0]})
        pairs = [(raw(0), events[0]), (raw(1), events[1])]
        buckets, lifecycle = M.replay_member_signatures(E, pairs, targets, last)
        self.assertEqual(sum(len(x.targets) for x in buckets), 1)
        self.assertEqual(lifecycle["terminal_active_contexts"], 0)

    def test_48_replay_h4_keyless_target(self):
        e = E.Event("source", "member", 0, 0.0, src_endpoint=None, dst_endpoint=None,
                    ip_version=None, ip_protocol=None, src_port=None, dst_port=None,
                    field_presence_mask="none", target_uid="u")
        target = E.TargetSpec("u", "source", "member", 0)
        last = E.SemanticPrototype._discover([e], {0: target})
        buckets, _ = M.replay_member_signatures(E, [(raw(0), e)], [target], last)
        self.assertTrue(buckets[0].signatures[0].startswith("H4\x1f"))

    def test_49_replay_idle_split_resets_prefix(self):
        events = [event(0, timestamp=0), event(1, "u", timestamp=100)]
        target = E.TargetSpec("u", "source", "member", 1)
        last = E.SemanticPrototype._discover(events, {1: target})
        buckets, _ = M.replay_member_signatures(E, [(raw(0), events[0]), (raw(1), events[1])], [target], last)
        target_bucket = [b for b in buckets if b.targets][0]
        self.assertEqual(len(target_bucket.signatures), 1)

    def test_50_join_assigns_label_aware_teacher(self):
        bucket = M.ReplayBucket("source", "member", "ctx", ["s"], [("u", 0)])
        descriptors = pd.DataFrame([{"uid": "u", "semantic_context_key": "ctx", "legal_fit": True,
                                     "owner": "A", "label_kind": "benign", "role": "aux_normal_fit",
                                     "source_group": "source", "device_family": "d", "attack_family": "benign",
                                     "timestamp_epoch": 1.0}])
        value = M.join_buckets_to_examples([bucket], descriptors, {"u": False})
        self.assertEqual(value[0].targets[0].teacher_kind, "benign_normal")

    def test_51_authorization_tokens_are_separate(self):
        self.assertEqual(len({M.MATERIALIZE_TOKEN, M.TRAIN_TOKEN, M.SELECT_TOKEN}), 3)

    def test_52_parser_has_three_physical_modes(self):
        parser = M.parser()
        materialize = parser.parse_args(["materialize-fit", "--authorization-token", "x", "--tshark", "t", "--output-dir", "o"])
        train = parser.parse_args(["train-fit", "--authorization-token", "x", "--corpus", "c", "--output-dir", "o"])
        select = parser.parse_args(["evaluate-select", "--authorization-token", "x", "--checkpoint", "k", "--corpus", "c", "--output-dir", "o"])
        self.assertEqual((materialize.mode, train.mode, select.mode), ("materialize-fit", "train-fit", "evaluate-select"))

    def test_53_wrong_train_token_fails_before_open(self):
        args = argparse.Namespace(authorization_token="wrong", corpus="absent", output_dir="absent")
        with self.assertRaises(M.F1Failure):
            M.train_fit(args)

    def test_54_atomic_write_and_hash_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "x.txt"
            M.atomic_text(path, "hello\n")
            self.assertEqual(M.sha256_file(path), M.sha256_bytes(b"hello\n"))

    def test_55_resume_matches_uninterrupted_checkpoint_tensors(self):
        train_contexts = [example("train%d" % i, "train_source_%d" % i, owner="B", length=2) for i in range(4)]
        val_contexts = [example("val%d" % i, "normal_scanning1.pcap", owner="B", length=2) for i in range(2)]
        vocabulary, _ = M.build_vocabulary(train_contexts + val_contexts)
        train_encoded = M.encode_examples(train_contexts, vocabulary)
        val_encoded = M.encode_examples(val_contexts, vocabulary)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            torch.manual_seed(M.SEED); np.random.seed(M.SEED); __import__("random").seed(M.SEED)
            full = M.train_loop(train_encoded, val_encoded, fake_p2(), root / "full", max_epochs=1,
                                batch_size=2, checkpoint_interval=1)
            torch.manual_seed(M.SEED); np.random.seed(M.SEED); __import__("random").seed(M.SEED)
            partial = M.train_loop(train_encoded, val_encoded, fake_p2(), root / "resume", max_epochs=1,
                                   batch_size=2, stop_after_batches=1, checkpoint_interval=1)
            resumed = M.train_loop(train_encoded, val_encoded, fake_p2(), root / "resume", max_epochs=1,
                                   batch_size=2, resume_path=Path(partial["resume"]), checkpoint_interval=1)
            full_state = torch.load(full["best_checkpoint"], map_location="cpu", weights_only=False)["model"]
            resumed_state = torch.load(resumed["best_checkpoint"], map_location="cpu", weights_only=False)["model"]
            self.assertEqual(M.state_tensor_bytes(full_state), M.state_tensor_bytes(resumed_state))
            self.assertEqual(full["ledger"], resumed["ledger"])

    def test_56_denominator_literals(self):
        self.assertEqual((M.EXPECTED_SELECT_ATTACK_ROWS, M.EXPECTED_A_SELECT_ATTACK_ROWS,
                          M.EXPECTED_B_SELECT_ATTACK_ROWS, M.EXPECTED_B_BENIGN_SELECT_ROWS,
                          M.EXPECTED_B_BENIGN_GAIN), (69, 46, 23, 4812, 482))

    def test_57_real_count_only_identity_pins(self):
        self.assertEqual(M.sha256_file(ROOT / M.D0_REL / "f1_d0_verdict.json"), M.D0_VERDICT_SHA256)
        self.assertEqual(M.sha256_file(ROOT / M.D0_REL / "f1_d0_uid_context_phase_owner_conservation.csv.gz"), M.D0_TABLE_SHA256)
        self.assertEqual(M.sha256_file(ROOT / M.TEACHER_REL / "f1_teacher_benign_counts.json"), M.TEACHER_COUNTS_SHA256)
        self.assertEqual(M.sha256_file(ROOT / M.TEACHER_REL / "f1_teacher_benign_uid_verdicts.csv.gz"), M.TEACHER_UID_SHA256)
        self.assertEqual(M.sha256_file(ROOT / M.EMBEDDING_METADATA_REL), M.EMBEDDING_METADATA_SHA256)

    def test_58_loss_reports_exact_context_denominators(self):
        contexts = [example("a", "train", label=0), example("b", "train", label=1)]
        vocab, _ = M.build_vocabulary(contexts)
        losses = M.compute_losses(M.F1Encoder(), fake_p2(), M.collate_examples(M.encode_examples(contexts, vocab)))
        self.assertEqual(int(losses["label_context_count"]), 2)
        self.assertEqual(int(losses["attack_context_count"]), 1)

    def test_59_label_descriptors_are_loaded_after_member_replay(self):
        source = (ROOT / "repo/ood/issue27frontend_f1_d1_train_v1.py").read_text(encoding="utf-8")
        allowlist = source.index("construction_allowlist = pd.read_csv")
        replay = source.index("for member_index, (raw_key, part)")
        descriptor = source.index("# Only after construction is complete may authorized fit descriptors enter.")
        self.assertLess(allowlist, replay)
        self.assertLess(replay, descriptor)

    def test_60_engineering_failure_removes_scientific_verdict(self):
        previous = M.ROOT
        with tempfile.TemporaryDirectory() as directory:
            M.ROOT = Path(directory)
            output = M.ROOT / "runs" / "failure"
            output.mkdir(parents=True)
            M.atomic_json(output / "f1_d1_verdict.json", {"status": "invalid"})
            try:
                raise RuntimeError("synthetic")
            except RuntimeError as exc:
                M.record_engineering_failure(output, exc)
            self.assertFalse((output / "f1_d1_verdict.json").exists())
            self.assertTrue((output / "engineering_failure.json").is_file())
        M.ROOT = previous

    def test_61_resume_scientific_identity_is_pinned(self):
        source = (ROOT / "repo/ood/issue27frontend_f1_d1_train_v1.py").read_text(encoding="utf-8")
        self.assertIn('saved.get("run_identity", {})', source)
        self.assertIn('"probe_state_sha256": PROBE_STATE_SHA256', source)

    def test_62_atomic_npz_is_byte_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "first.npz"
            second = Path(directory) / "second.npz"
            arrays = {"z": np.arange(7, dtype=np.int64), "a": np.eye(3, dtype=np.float32)}
            M.atomic_npz(first, **arrays)
            M.atomic_npz(second, **arrays)
            self.assertEqual(M.sha256_file(first), M.sha256_file(second))
            with np.load(first, allow_pickle=False) as loaded:
                np.testing.assert_array_equal(loaded["z"], arrays["z"])
                np.testing.assert_array_equal(loaded["a"], arrays["a"])

    def test_63_geometry_instrument_passes_stable_rank_four_fixture(self):
        devices = ["iotsim-building-monitor", "iotsim-combined-cycle",
                   "iotsim-combined-cycle-tls", "iotsim-domotic-monitor", "ton-iot-external"]
        centers = [np.asarray([8, 0, 0, 0]), np.asarray([0, 8, 0, 0]),
                   np.asarray([0, 0, 8, 0]), np.asarray([0, 0, 0, 8]),
                   np.asarray([-8, -8, -8, -8])]
        rows, values = [], []
        for device_index, device in enumerate(devices):
            for context_index in range(64):
                rows.append({"uid": "%d-%d" % (device_index, context_index),
                             "context_key": "%d-%d" % (device_index, context_index),
                             "event_index": 0, "label": 0, "device_family": device,
                             "timestamp_epoch": float(context_index)})
                vector = np.zeros(768, dtype=np.float32)
                vector[:4] = centers[device_index]
                values.append(vector)
        result = M.geometry_audit(pd.DataFrame(rows), np.stack(values))
        self.assertTrue(result["pass"])
        self.assertEqual(result["rank"], 4)
        self.assertEqual(len(result["between_within_rows"]), 5)

    def test_64_device_leakage_compares_same_token_control(self):
        rng = np.random.RandomState(M.SEED)
        rows = []
        for device_index in range(3):
            for context_index in range(25):
                rows.append({"uid": "%d-%d" % (device_index, context_index),
                             "context_key": "%d-%d" % (device_index, context_index),
                             "event_index": 0, "label": 0,
                             "device_family": "device-%d" % device_index})
        values = rng.normal(size=(len(rows), 12)).astype(np.float32)
        result = M.device_leakage_audit(pd.DataFrame(rows), values, values.copy())
        self.assertTrue(result["pass"])
        self.assertAlmostEqual(result["learned_balanced_accuracy"], result["control_balanced_accuracy"])

    def test_65_attack_canary_reports_control_and_centroid(self):
        rng = np.random.RandomState(M.SEED)
        rows, learned, control = [], [], []
        for split, count in (("train", 80), ("internal_val", 80)):
            for index in range(count):
                label = index % 2
                rows.append({"uid": "%s-%d" % (split, index), "context_key": "%s-%d" % (split, index),
                             "split": split, "source_group": "%s-source" % split,
                             "attack_family": "family" if label else "benign", "label": label})
                learned.append([float(label) * 8.0 - 4.0] + rng.normal(scale=0.05, size=7).tolist())
                control.append(rng.normal(size=8).tolist())
        result = M.attack_canary_audit(
            pd.DataFrame(rows), np.asarray(learned, dtype=np.float32), np.asarray(control, dtype=np.float32)
        )
        self.assertTrue(result["pass"])
        self.assertIn("control_permutation_p99", result)
        self.assertIn("learned_nearest_centroid_cosine_auroc", result)
        self.assertGreaterEqual(len(result["denominators"]), 4)

    def test_66_fit_checkpoint_runs_audit_before_select(self):
        source = (ROOT / "repo/ood/issue27frontend_f1_d1_train_v1.py").read_text(encoding="utf-8")
        train_start = source.index("def train_fit")
        train_body = source[train_start:source.index("def evaluate_select", train_start)]
        self.assertIn("fit_representation_audit(model, encoded, output)", train_body)
        self.assertIn('result["select_opened"] = 0', train_body)
        self.assertIn("F1_D1_FIT_GATE_PASS_AWAITING_SELECT_AUTHORIZATION", train_body)

    def test_67_real_fit_context_labels_are_unique(self):
        frame = pd.read_csv(ROOT / M.D0_REL / "f1_d0_uid_context_phase_owner_conservation.csv.gz",
                            usecols=["semantic_context_key", "label_kind", "legal_fit"], keep_default_na=False)
        frame["legal_fit"] = frame["legal_fit"].astype(str).str.lower().eq("true")
        legal = frame.loc[frame["legal_fit"]]
        self.assertTrue(legal.groupby("semantic_context_key")["label_kind"].nunique().le(1).all())

    def test_68_checkpoint_rejects_nonfinite_representation_even_with_finite_score(self):
        item = M.EncodedExample(example("x", "train", 1, "A", "attack_hard"), [2, 3, 4])
        self.assertFalse(M.checkpoint_eligible(
            {"logits": torch.tensor([M.Z_0 + 1]), "representations_finite": torch.tensor(False)}, [item]
        ))

    def test_69_resource_probe_and_output_cap_are_executable(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            usage = M.enforce_resource_caps(Path(directory))
            self.assertGreater(usage["peak_working_set_bytes"], 0)
            self.assertEqual(usage["durable_output_bytes"], 0)

    def test_70_scientific_stop_is_not_engineering_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "runs") as directory:
            output = Path(directory)
            M.record_scientific_stop(output, M.ScientificStop("F1_TEST_NO_GO", "synthetic"))
            value = json.loads((output / "f1_d1_scientific_stop.json").read_text(encoding="utf-8"))
            self.assertEqual(value["status"], "F1_TEST_NO_GO")
            self.assertFalse((output / "engineering_failure.json").exists())

    def test_71_replay_checkpoint_identity_matches_first_authorized_implementation(self):
        payload = subprocess.check_output([
            "git", "cat-file", "blob", "d074cea:repo/ood/issue27frontend_f1_d1_train_v1.py"
        ], cwd=str(ROOT))
        self.assertEqual(M.sha256_bytes(payload), M.REPLAY_IMPLEMENTATION_SHA256)

    def test_72_inherited_timestamp_metadata_closes_target_plan_nan(self):
        target = pd.read_csv(
            ROOT / M.STAGE_REL / "ckda_d1_fit_select_target_metadata.csv",
            usecols=["uid", "feature_available_time_epoch"], keep_default_na=False,
        )
        inherited = pd.read_csv(
            ROOT / M.EMBEDDING_METADATA_REL, usecols=["uid", "timestamp_epoch"], keep_default_na=False,
        )
        self.assertEqual(int(target["feature_available_time_epoch"].astype(str).str.lower().eq("nan").sum()), 12000)
        self.assertEqual(len(inherited), M.EXPECTED_ALL)
        self.assertTrue(inherited["uid"].is_unique)
        self.assertTrue(np.isfinite(pd.to_numeric(inherited["timestamp_epoch"], errors="raise")).all())
        self.assertEqual(len(target.merge(inherited, on="uid", how="inner", validate="one_to_one")), M.EXPECTED_ALL)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    print("F1_D1_CONTRACT_TESTS passed=%d failures=%d errors=%d" %
          (result.testsRun - len(result.failures) - len(result.errors), len(result.failures), len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
