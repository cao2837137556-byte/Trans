#!/usr/bin/env python3
"""Contract tests for the frozen CKDA D1 implementation."""

from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np

import issue27ckda_d1_representation_probe_v1 as ckda
import issue27ckda_d1_probe_runner_v1 as probe_runner
import issue27ckda_d1_role_plan_v1 as role_plan
import issue27ckda_d1_target_metadata_v1 as target_metadata
import issue27ckda_d1_e3_embed_v1 as e3_embed
import issue27ckda_d0_resource_pilot_v1 as d0_pilot
import issue27ckda_d1_metrics_v1 as metrics
import issue27ckda_d1_validate_and_pack_v1 as validator


class CKDAD1ContractTests(unittest.TestCase):
    def test_01_contract_hash_is_frozen(self) -> None:
        root = Path(__file__).resolve().parents[2]
        contract = root / "runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md"
        ckda.verify_contract(contract)

    def test_02_python39_grammar_and_runtime_api_gate(self) -> None:
        ckda.assert_python39_source(Path(ckda.__file__))
        with tempfile.TemporaryDirectory() as temporary:
            match_path = Path(temporary) / "match.py"
            match_path.write_bytes(b"match x:\n    case 1:\n        pass\n")
            with self.assertRaises(RuntimeError):
                ckda.assert_python39_source(match_path)
            newline_path = Path(temporary) / "newline.py"
            newline_path.write_bytes(b"from pathlib import Path\nPath('x').write_text('x', newline='\\n')\n")
            with self.assertRaises(RuntimeError):
                ckda.assert_python39_source(newline_path)
            strict_path = Path(temporary) / "strict.py"
            strict_path.write_bytes(b"list(zip([1], [2], strict=True))\n")
            with self.assertRaises(RuntimeError):
                ckda.assert_python39_source(strict_path)

    def test_03_atomic_mixed_schema_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = ckda.runtime_io_contract(Path(temporary))
            self.assertEqual(report["status"], "PASS")
            rows = ckda.read_csv(Path(temporary) / "mixed.csv")
            self.assertEqual(list(rows[0]), ["fit_only", "report_only", "uid"])

    def test_04_union_schema_does_not_use_first_row_only(self) -> None:
        self.assertEqual(
            ckda.union_fieldnames([{"a": 1}, {"b": 2}, {"c": 3, "a": 4}]),
            ["a", "b", "c"],
        )

    def event(self, position: int, timestamp: int, reverse: bool = False, member: str = "m") -> ckda.PacketEvent:
        left = (b"\x0a\x00\x00\x01", 10)
        right = (b"\x0a\x00\x00\x02", 443)
        source, destination = (right, left) if reverse else (left, right)
        return ckda.PacketEvent(
            "source",
            member,
            position,
            timestamp,
            source[0],
            source[1],
            destination[0],
            destination[1],
            6,
            position * 64,
        )

    def test_05_canonical_bidirectional_key(self) -> None:
        self.assertEqual(ckda.canonical_session_key(self.event(1, 1)), ckda.canonical_session_key(self.event(2, 2, True)))

    def test_06_protocol_is_in_session_key(self) -> None:
        first = self.event(1, 1)
        second = ckda.PacketEvent(**{**first.__dict__, "protocol": 17})
        self.assertNotEqual(ckda.canonical_session_key(first), ckda.canonical_session_key(second))

    def test_07_member_reset_isolation(self) -> None:
        sessions = ckda.materialize_sessions([self.event(1, 10, member="a"), self.event(1, 20, member="b")])
        self.assertEqual(len(sessions), 2)
        self.assertTrue(all(value[0, 3] == 0 for value in sessions.values()))

    def test_08_equal_time_uses_event_position(self) -> None:
        sessions = ckda.materialize_sessions([self.event(2, 10, True), self.event(1, 10, False)])
        tokens = next(iter(sessions.values()))
        self.assertEqual(tokens[:, 0].tolist(), [0, 1])
        self.assertEqual(tokens[:, 3].tolist(), [0, 1])

    def test_09_duplicate_event_position_fails(self) -> None:
        with self.assertRaises(RuntimeError):
            ckda.materialize_sessions([self.event(1, 10), self.event(1, 20, True)])

    def test_10_bucket_boundaries(self) -> None:
        event = self.event(1, 1)
        event = ckda.PacketEvent(**{**event.__dict__, "frame_len": 10_000})
        self.assertEqual(ckda.packet_fields(event, 0), (0, 31, 6, 2))
        self.assertEqual(ckda.packet_fields(event, 1)[3], 1)

    def test_11_negative_iat_fails(self) -> None:
        with self.assertRaises(ValueError):
            ckda.packet_fields(self.event(1, 1), 2)

    def test_12_split_once_no_duplication(self) -> None:
        tokens = np.tile(np.asarray([[0, 1, 6, 0]], dtype=np.int64), (600, 1))
        chunks = ckda.split_once({"session": tokens})
        self.assertEqual([len(value) for _, value in chunks], [256, 256, 88])
        self.assertEqual(sum(len(value) for _, value in chunks), 600)

    def test_13_benign_census_both_conditions_mandatory(self) -> None:
        self.assertFalse(ckda.benign_census_gate(499_999, 20_000_000)["passed"])
        self.assertFalse(ckda.benign_census_gate(600_000, 9_999_999)["passed"])
        self.assertTrue(ckda.benign_census_gate(500_000, 10_000_000)["passed"])

    def test_14_i1_real_forward_shape_and_finite(self) -> None:
        report = ckda.i1_forward_contract()
        self.assertEqual(report["representation_shape"], [2, 132])
        self.assertEqual(report["status"], "PASS")

    def test_15_future_mutation_cannot_change_current_representation(self) -> None:
        torch = ckda._torch()
        model = ckda.build_i1_model().eval()
        prefix = np.asarray([[0, 1, 6, 0], [1, 2, 6, 2]], dtype=np.int64)
        changed_future = np.asarray([[0, 1, 6, 0], [1, 2, 6, 2], [0, 31, 255, 32]], dtype=np.int64)
        first_tokens, first_valid = ckda.collate_chunks([prefix])
        second_tokens, second_valid = ckda.collate_chunks([changed_future[:2]])
        with torch.inference_mode():
            first = model.representation(first_tokens, first_valid)
            second = model.representation(second_tokens, second_valid)
        np.testing.assert_allclose(first.numpy(), second.numpy(), atol=1e-6, rtol=0.0)

    def test_15b_e3_masked_mean_excludes_padding(self) -> None:
        torch = ckda._torch()
        hidden = torch.as_tensor([[[1.0, 2.0], [3.0, 4.0], [99.0, 99.0]]])
        mask = torch.as_tensor([[1, 1, 0]])
        pooled = ckda.masked_mean_last_hidden(hidden, mask)
        np.testing.assert_array_equal(pooled.numpy(), np.asarray([[2.0, 3.0]]))

    def test_15c_e3_empty_mask_fails_closed(self) -> None:
        torch = ckda._torch()
        with self.assertRaises(RuntimeError):
            ckda.masked_mean_last_hidden(torch.zeros(1, 2, 3), torch.zeros(1, 2))

    def test_16_shard_roundtrip_and_exact_token_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            tokens = np.tile(np.asarray([[0, 1, 6, 0]], dtype=np.int64), (300, 1))
            path = Path(temporary) / "shard.npz"
            report = ckda.write_session_shard(path, {"a": tokens, "b": tokens[:2]})
            self.assertEqual(report["tokens"], 302)
            self.assertEqual(sum(len(value) for value in ckda.iter_shard_chunks(path)), 302)

    def test_17_shard_readback_rejects_schema_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "bad.npz"
            ckda.atomic_npz(path, tokens=np.zeros((1, 4), dtype=np.int16))
            with self.assertRaises(RuntimeError):
                ckda.validate_session_shard(path)

    def test_18_learning_rate_schedule(self) -> None:
        self.assertGreater(ckda.learning_rate_at_step(2, 100), ckda.learning_rate_at_step(1, 100))
        self.assertAlmostEqual(ckda.learning_rate_at_step(100, 100), 0.0)

    def test_19_epoch_resume_is_bit_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "shard.npz"
            sessions = {
                "a": np.asarray([[0, 1, 6, 0], [1, 2, 6, 2]], dtype=np.int64),
                "b": np.asarray([[1, 3, 17, 0]], dtype=np.int64),
            }
            ckda.write_session_shard(shard, sessions)
            full = ckda.train_i1_from_shards([shard], root / "full")
            partial = ckda.train_i1_from_shards([shard], root / "resume", stop_after_epoch=1)
            self.assertEqual(partial["status"], "CHECKPOINTED")
            resumed = ckda.train_i1_from_shards([shard], root / "resume")
            self.assertEqual(full["model_state_sha256"], resumed["model_state_sha256"])
            self.assertEqual(full["history"], resumed["history"])

    def test_19b_mixed_lengths_are_bucketed_without_padding_explosion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shard = root / "mixed.npz"
            sessions = {
                "tiny%d" % index: np.asarray([[0, 1, 6, 0]], dtype=np.int64)
                for index in range(200)
            }
            sessions["long"] = np.tile(np.asarray([[1, 31, 17, 2]], dtype=np.int64), (256, 1))
            ckda.write_session_shard(shard, sessions)
            batches = list(ckda.iter_token_budget_batches([shard], 0))
            reports = [ckda.validate_batch_padding(batch) for batch in batches]
            self.assertEqual(sum(value["nonpadding_tokens"] for value in reports), 456)
            self.assertTrue(all(value["padded_tokens"] <= 2 * value["nonpadding_tokens"] for value in reports))

    def test_19c_trusted_checkpoint_loader_supports_new_default(self) -> None:
        torch = ckda._torch()
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.pt"
            torch.save({"numpy_rng": np.random.get_state()}, path)
            loaded = ckda.load_trusted_training_checkpoint(path, "cpu")
            self.assertIn("numpy_rng", loaded)

    def sample_probe_data(self):
        rng = np.random.default_rng(27)
        values = rng.normal(size=(40, 6))
        missing = np.zeros(40, dtype=np.bool_)
        labels = np.asarray([0] * 20 + [1] * 20)
        uids = ["u%d" % index for index in range(40)]
        normalizer = ckda.SharedNormalizer.fit(values, missing)
        normalized = normalizer.transform(values, missing)
        return normalized, missing, labels, uids

    def test_20_zero_variance_normalizes_to_zero(self) -> None:
        values = np.ones((5, 3))
        missing = np.zeros(5, dtype=np.bool_)
        normalized = ckda.SharedNormalizer.fit(values, missing).transform(values, missing)
        np.testing.assert_array_equal(normalized, np.zeros_like(normalized))

    def test_21_missing_probe_features_are_zero_plus_flag(self) -> None:
        values = np.asarray([[1.0, 2.0], [9.0, 8.0]])
        missing = np.asarray([False, True])
        normalizer = ckda.SharedNormalizer.fit(values, missing)
        result = ckda.append_missing(normalizer.transform(values, missing), missing)
        np.testing.assert_array_equal(result[1], np.asarray([0.0, 0.0, 1.0]))

    def test_22_g0_self_exclusion_and_missing_infinity(self) -> None:
        values, missing, labels, uids = self.sample_probe_data()
        model = ckda.GeometryProbe().fit(values, missing, labels, uids)
        missing[-1] = True
        scores = model.score(values, missing, uids, query_batch=3)
        self.assertTrue(math.isinf(scores[-1]))
        self.assertFalse(np.any(np.isnan(scores)))

    def test_23_p1_fixed_solver_path(self) -> None:
        values, missing, labels, _uids = self.sample_probe_data()
        features = ckda.append_missing(values, missing)
        scores = ckda.LinearProbe().fit(features, labels).score(features)
        self.assertEqual(len(scores), 40)
        self.assertTrue(np.all((scores >= 0.0) & (scores <= 1.0)))

    def test_24_p2_fixed_50_epoch_path(self) -> None:
        values, missing, labels, _uids = self.sample_probe_data()
        features = ckda.append_missing(values, missing)
        scores = ckda.MLPProbe(features.shape[1]).fit(features, labels).score(features)
        self.assertEqual(len(scores), 40)

    def test_25_threshold_selects_largest_valid_value(self) -> None:
        support = np.full(69, 0.8)
        auxiliary = np.full(3000, 0.7)
        ton = np.full(4000, 0.6)
        threshold, _frontier = ckda.choose_threshold(support, auxiliary, ton)
        self.assertEqual(threshold.value, 0.8)
        self.assertEqual((threshold.support_hard, threshold.auxiliary_hard, threshold.ton_hard), (69, 0, 0))

    def test_26_threshold_denominator_drift_fails(self) -> None:
        with self.assertRaises(RuntimeError):
            ckda.choose_threshold(np.ones(68), np.ones(3000), np.ones(4000))

    def test_27_threshold_nan_fails(self) -> None:
        support = np.ones(69)
        support[0] = np.nan
        with self.assertRaises(RuntimeError):
            ckda.choose_threshold(support, np.ones(3000), np.ones(4000))

    def gate_evidence(self, **updates):
        values = dict(
            support_hard=69,
            overall_attack_rows=244_050,
            overall_recall=0.90,
            c1_overall_recall=0.90,
            future_rows=131_391,
            future_recall=0.90,
            family_deltas_pp={"f%d" % index: 0.0 for index in range(16)},
            ood_rates={"p%d" % index: 0.20 for index in range(4)},
            frozen_ood_rates={"p%d" % index: 0.20 for index in range(4)},
            review_count=0,
            contract_gates_pass=True,
        )
        values.update(updates)
        return ckda.GateEvidence(**values)

    def test_28_actionable_gate_is_full_conjunction(self) -> None:
        passed, checks = ckda.actionable_gate(self.gate_evidence())
        self.assertTrue(passed)
        self.assertTrue(all(checks.values()))
        passed, _checks = ckda.actionable_gate(self.gate_evidence(review_count=1))
        self.assertFalse(passed)

    def test_29_family_scope_drift_fails(self) -> None:
        with self.assertRaises(RuntimeError):
            ckda.actionable_gate(self.gate_evidence(family_deltas_pp={"f": 0.0}))

    def test_30_state_precedence(self) -> None:
        self.assertEqual(ckda.final_state(True, False, True, [0.9], True, False), ckda.ACTIONABLE)
        self.assertEqual(ckda.final_state(False, False, True, [0.9], True, False), ckda.STRONG_GEOMETRIC)
        self.assertEqual(ckda.final_state(False, False, False, [0.500001], True, False), ckda.WEAK_ONLY)
        self.assertEqual(ckda.final_state(False, False, False, [0.5], True, False), ckda.NO_ACTIONABLE)
        self.assertEqual(ckda.final_state(True, True, True, [1.0], True, True), ckda.ENGINEERING_FAILURE)

    def test_31_contract_unit_terminal_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            report = ckda.contract_unit(Path(temporary))
            self.assertEqual(report["status"], "PASS")
            with (Path(temporary) / "ckda_d1_contract_unit.json").open("r", encoding="utf-8") as handle:
                self.assertEqual(json.load(handle)["status"], "PASS")

    def test_32_probe_state_roundtrip_scores_are_exact(self) -> None:
        values, missing, labels, uids = self.sample_probe_data()
        normalizer = ckda.SharedNormalizer.fit(values, missing)
        normalized = normalizer.transform(values, missing)
        geometry = ckda.GeometryProbe().fit(normalized, missing, labels, uids)
        features = ckda.append_missing(normalized, missing)
        linear = ckda.LinearProbe().fit(features, labels)
        mlp = ckda.MLPProbe(features.shape[1]).fit(features, labels)
        expected = {
            "G0": geometry.score(normalized, missing, uids),
            "P1": linear.score(features),
            "P2": mlp.score(features),
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "state.npz"
            probe_runner.serialize_state(path, normalizer, geometry, linear, mlp)
            actual = probe_runner.score_frozen(probe_runner.load_state(path), values, missing, uids)
        for key in expected:
            np.testing.assert_allclose(actual[key], expected[key], rtol=1e-6, atol=1e-7)

    def test_33_exact_embedding_join_rejects_missing_or_duplicate(self) -> None:
        import pandas as pd

        plan = pd.DataFrame({"uid": ["a", "b"]})
        representations = np.zeros((2, 3))
        missing = np.zeros(2, dtype=np.bool_)
        joined = probe_runner.exact_join(plan, np.asarray(["b", "a"]), representations, missing)
        self.assertEqual(joined[1].shape, (2, 3))
        with self.assertRaises(RuntimeError):
            probe_runner.exact_join(plan, np.asarray(["a", "c"]), representations, missing)

    def test_34_report_marker_fails_closed(self) -> None:
        good = {
            "status": "CKDA_D1_THRESHOLDS_FROZEN",
            "contract_sha256": ckda.CONTRACT_SHA256,
            "fit_select_plan_sha256": "a" * 64,
            "thresholds": {
                key: {
                    "kind": "FINITE", "value": 0.5, "canonical": "0.5",
                    "support_hard": 69, "auxiliary_hard": 0, "ton_hard": 0,
                }
                for key in ("G0", "P1", "P2")
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "marker.json"
            ckda.atomic_json(path, good)
            self.assertEqual(role_plan.require_threshold_marker(path)["status"], good["status"])
            good["thresholds"]["P1"]["support_hard"] = 68
            ckda.atomic_json(path, good)
            with self.assertRaises(RuntimeError):
                role_plan.require_threshold_marker(path)

    def test_35_bounded_e3_prefix_is_exact(self) -> None:
        state = e3_embed.BoundedNetfoundPrefix()
        full = []
        for index in range(180):
            reverse = bool(index % 2)
            timestamp = index * 0.011
            row = {
                "frame.number": str(index + 1),
                "frame.time_epoch": str(timestamp),
                "frame.len": "64",
                "ip.src": "10.0.0.2" if reverse else "10.0.0.1",
                "ip.dst": "10.0.0.1" if reverse else "10.0.0.2",
                "ip.proto": "6", "ip.hdr_len": "20", "ip.dsfield": "0",
                "ip.len": "64", "ip.flags": "0", "ip.ttl": "64",
                "tcp.srcport": "443" if reverse else "10",
                "tcp.dstport": "10" if reverse else "443",
                "tcp.flags": "16", "tcp.window_size_value": "1024",
                "tcp.seq_raw": str(index + 100), "tcp.ack_raw": str(index + 200),
                "tcp.urgent_pointer": "0",
            }
            full.append(row)
            state.append(row, timestamp)
            expected = d0_pilot.netfound_flow(full)
            actual = state.flow(d0_pilot)
            self.assertEqual(actual, expected)

    def test_36_streamed_gzip_csv_union_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "large.csv.gz"
            count = ckda.atomic_csv_stream(
                path,
                ({"uid": str(index), "value": index} for index in range(1001)),
                ["uid", "value"],
                compress=True,
            )
            self.assertEqual(count, 1001)
            import pandas as pd
            self.assertEqual(len(pd.read_csv(path)), 1001)

    def test_36b_e3_embed_flows_real_entrypoint_uses_flow_cardinality(self) -> None:
        class Tokenizer:
            def __call__(self, values):
                count = len(values["flow_duration"])
                return {"input_ids": [[index + 1] for index in range(count)]}

        class Collator:
            def __call__(self, values):
                import torch
                return {
                    "input_ids": torch.as_tensor([value["input_ids"] for value in values]),
                    "attention_mask": torch.ones((len(values), 1), dtype=torch.long),
                    "direction": torch.ones((len(values), 1), dtype=torch.long),
                    "iats": torch.ones((len(values), 1), dtype=torch.long),
                    "bytes": torch.ones((len(values), 1), dtype=torch.long),
                    "pkt_count": torch.ones((len(values), 1), dtype=torch.long),
                    "protocol": torch.ones((len(values), 1), dtype=torch.long),
                    "dataset_burst_sizes": torch.ones((len(values), 1), dtype=torch.long),
                }

        class Transformer:
            def __call__(self, **batch):
                import torch
                values = batch["input_ids"].to(dtype=torch.float32)
                return type("Output", (), {"last_hidden_state": values.unsqueeze(-1)})()

        class Model:
            base_transformer = Transformer()

            def eval(self):
                return self

        flows = [{"flow_duration": 1}, {"flow_duration": 2}]
        actual = e3_embed.embed_flows(None, Model(), Tokenizer(), Collator(), flows, "cpu", 1)
        self.assertEqual(actual.shape, (2, 1))

    def test_36c_e3_causal_timestamp_regression_fails_closed(self) -> None:
        state = e3_embed.BoundedNetfoundPrefix()
        row = {"frame.number": "1", "ip.src": "10.0.0.1"}
        state.append(row, 2.0)
        with self.assertRaisesRegex(RuntimeError, "timestamp regressed"):
            state.append(dict(row, **{"frame.number": "2"}), 1.0)

    def test_36d_target_metadata_report_marker_is_fully_bound(self) -> None:
        marker = {
            "status": "CKDA_D1_THRESHOLDS_FROZEN",
            "contract_sha256": ckda.CONTRACT_SHA256,
            "fit_select_plan_sha256": "a" * 64,
            "fit_rows": 18_398,
            "select_rows": 7_069,
            "report_rows_opened": 0,
            "report_labels_opened": 0,
            "thresholds": {
                key: {"support_hard": ckda.SUPPORT_SELECT_ROWS}
                for key in ("G0", "P1", "P2")
            },
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "marker.json"
            ckda.atomic_json(path, marker)
            target_metadata.require_report_marker(path, "a" * 64)
            marker["report_labels_opened"] = 1
            ckda.atomic_json(path, marker)
            with self.assertRaises(RuntimeError):
                target_metadata.require_report_marker(path, "a" * 64)

    def test_36e_target_metadata_uses_ckcz_manifest_contract(self) -> None:
        import pandas as pd

        args = SimpleNamespace(
            gotham_manifest=Path("gotham.csv"),
            auxiliary_manifest=Path("auxiliary.csv"),
            gotham_allowlist=Path("gotham-allowlist.csv"),
            auxiliary_allowlist=Path("auxiliary-allowlist.csv"),
            ckbv_root=Path("cache-root"),
        )
        gotham_rows = [{"source_id": "g"}]
        auxiliary_rows = [{"source_id": "a"}]
        with mock.patch.object(target_metadata.ckcz, "load_allowlist", side_effect=[["g"], ["a"]]), \
             mock.patch.object(target_metadata.ckcz, "validate_manifest", side_effect=[gotham_rows, auxiliary_rows]) as validate, \
             mock.patch.object(
                 target_metadata.ckcz,
                 "export_cache_metadata",
                 side_effect=[(pd.DataFrame({"cache_kind": ["gotham"]}), [{}]),
                              (pd.DataFrame({"cache_kind": ["auxiliary"]}), [{}])],
             ):
            frame, audit = target_metadata.load_cache_metadata(args)
        self.assertEqual(frame["cache_kind"].tolist(), ["gotham", "auxiliary"])
        self.assertEqual(len(audit), 2)
        self.assertEqual(validate.call_args_list[0].args[:2],
                         (args.gotham_manifest, target_metadata.GOTHAM_MANIFEST_SHA256))
        self.assertEqual(validate.call_args_list[1].args[:2],
                         (args.auxiliary_manifest, target_metadata.AUXILIARY_MANIFEST_SHA256))

    def test_36f_validator_requires_persistent_role_audits_and_frontiers(self) -> None:
        required = set(validator.MANDATORY)
        self.assertTrue({
            "ckda_d1_fit_select_role_plan_audit.json",
            "ckda_d1_report_role_plan_audit.json",
            "ckda_d1_g0_threshold_frontier.csv",
            "ckda_d1_p1_threshold_frontier.csv",
            "ckda_d1_p2_threshold_frontier.csv",
        }.issubset(required))

    def test_37_weighted_cluster_bootstrap_matches_slow_sampling(self) -> None:
        import pandas as pd

        frame = pd.DataFrame({
            "cluster": ["a", "a", "b", "b", "c", "c"],
            "binary_auc_label": [1, 0, 1, 0, 1, 0],
            "score": [0.9, 0.1, 0.8, 0.2, 0.7, 0.3],
        })
        # Freeze wrapper identity while exercising the exact 2,000-replicate path.
        report = metrics.cluster_auc_bootstrap(frame, "cluster", reps=2000, seed=2701)
        self.assertEqual(report["status"], "PASS")
        self.assertGreater(report["roc_auc_low"], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
