"""Synthetic-only PREPARE checks, including the actual old tokenizer adapter.

No real feature arrays, checkpoint bytes or real PCAP are opened by this suite.
"""
import copy
import csv
import hashlib
import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import dpkt
import numpy as np
import torch

import legacy_cic2022_enhancement_prepare_v1 as m
import legacy_cic2022_two_camera_semantic_probe_v1 as probe
import legacy_p2_supported_capability_ledger_v1 as reader
import issue27ckda_d0_resource_pilot_v1 as translator
import issue27ckda_d1_e3_embed_v1 as embed


VENDOR = Path("D:/study/paper/anomaly_detection/paper04/supercompute_transfer/issue27ckda_d0_representation_compatibility_20260811_r2/payload/vendor/netFound")
TSHARK = Path("C:/Program Files/Wireshark/tshark.exe")
CAM_MAC = "00:00:00:00:00:02"


class StubModel:
    """Deterministic token-sensitive transformer stand-in; never loads weights."""
    def __init__(self):
        self.calls = []
        self.training = False

    def eval(self):
        self.training = False
        return self

    def base_transformer(self, **kwargs):
        self.calls.append({k: v.detach().clone() if torch.is_tensor(v) else copy.deepcopy(v) for k, v in kwargs.items()})
        token = kwargs["input_ids"].float()
        # Variation in a retained packet's tokens or context changes pooling.
        return SimpleNamespace(last_hidden_state=token.unsqueeze(-1).expand(-1, -1, 768))


def dump_plan(path, rows):
    path.write_bytes("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode("utf-8"))


def synthetic_plan_set():
    old = [dict(uid=uid, label=label, owner="A", planned_role="OLD_REPLAY", class_balanced_weight_numerator=1,
                class_balanced_weight_denominator=2) for uid, label in (("a", 0), ("b", 1))]
    recipe = dict(old_replay=dict(rows=2, benign=1, attack=1,
                                 sorted_uid_lines_sha256=hashlib.sha256(b"a\nb\n").hexdigest()),
                  new_data=dict(train_file_ids=[1, 2, 3, 4], check_file_ids=[5, 6, 7, 8], unassigned_nmap_ids=[9],
                                train_rows=4, check_rows=4, train_labels=dict(benign=2, attack=2), check_labels=dict(benign=2, attack=2)))
    captures, candidates, train, check = [], [], [], []
    for fid in range(1, 10):
        role = "TRAIN" if fid <= 4 else ("CHECK" if fid <= 8 else "UNASSIGNED")
        spec = dict(file_id=fid, planned_role=role, archive_path="synthetic.tar.gz", member_path="member%d.pcap" % fid,
                    member_sha256=str(fid) * 64)
        captures.append(spec)
        if fid == 9:
            continue
        device, label = ("amcrest" if (fid - 1) % 4 < 2 else "simcam"), (fid - 1) % 2
        original = dict(candidate_uid="u%d" % fid, file_id=fid, member_path=spec["member_path"], member_sha256=spec["member_sha256"],
                        frame_number_1based=1, timestamp=1.0, stream="tcp:0", evidence_basis="synthetic", candidate_label=label)
        target = {k: v for k, v in original.items() if k not in {"candidate_uid", "candidate_label"}}
        target.update(uid=original["candidate_uid"], label=label, device=device, planned_role=role,
                      candidate_ordinal_0based=0, candidates_in_stream=1, selected_in_stream=1,
                      streams_in_capture=1, captures_in_device_label_cell=1)
        for prefix, denominator in (("conditional", 1), ("balanced_bce", 4), ("evaluation_label", 2)):
            target[prefix + "_weight_numerator"] = 1
            target[prefix + "_weight_denominator"] = denominator
        candidates.append(original)
        (train if role == "TRAIN" else check).append(target)
    return recipe, old, train, check, captures, candidates


class PrepareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        torch.set_num_threads(1)
        m.runtime_dependencies()
        cls.event, _, cls.fields = probe.legacy_runtime()
        # Import the real pinned implementation but prohibit pretrained APIs.
        config_type, cls.collator_type, model_type, cls.tokenizer_type = translator.import_netfound(VENDOR)
        cls.model_loader_guard = mock.patch.object(model_type, "from_pretrained", side_effect=AssertionError("real checkpoint prohibited"))
        cls.config_loader_guard = mock.patch.object(config_type, "from_pretrained", side_effect=AssertionError("real config prohibited"))
        cls.model_loader_guard.start()
        cls.config_loader_guard.start()
        cls.config_type = config_type

    @classmethod
    def tearDownClass(cls):
        cls.model_loader_guard.stop()
        cls.config_loader_guard.stop()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="legacy_enhancement_synthetic_")
        self.root = Path(self.temporary.name)
        self.runtime_guard = mock.patch.object(m, "build_runtime", side_effect=AssertionError("real runtime prohibited"))
        self.runtime_guard.start()

    def tearDown(self):
        self.runtime_guard.stop()
        self.temporary.cleanup()

    def runtime(self, trans=translator):
        config = self.config_type(pretraining=False, compile=False, strip_payload=True,
                                  max_burst_length=73, model_max_length=876, max_position_embeddings=73)
        tokenizer = self.tokenizer_type(config=config)
        tokenizer.pretraining, tokenizer.raw_labels = True, False
        return dict(embed=embed, translator=trans, event=self.event, fields=self.fields, probe=probe,
                    tokenizer=tokenizer, collator=self.collator_type(pad_token_id=tokenizer.pad_token_id), model=StubModel())

    def capture(self, name="fixture.pcap", first_ttl=64, future_window=8192, first_time=1.0, reverse_time=False):
        path = self.root / name
        request = b"DESCRIBE rtsp://10.0.0.2/live RTSP/1.0\r\nCSeq: 1\r\nAuthorization: Basic YWJj\r\n\r\n"
        packets = [(False, dpkt.tcp.TH_SYN, 100, 0, b""),
                   (True, dpkt.tcp.TH_SYN | dpkt.tcp.TH_ACK, 500, 101, b""),
                   (False, dpkt.tcp.TH_ACK, 101, 501, b""),
                   (False, dpkt.tcp.TH_ACK | dpkt.tcp.TH_PUSH, 101, 501, request)]
        with path.open("wb") as f:
            writer = dpkt.pcap.Writer(f)
            for i, (reverse, flags, seq, ack, payload) in enumerate(packets):
                tcp = dpkt.tcp.TCP(sport=554 if reverse else 1234, dport=1234 if reverse else 554,
                                    seq=seq, ack=ack, flags=flags, off=5, win=future_window if i == 3 else 8192, data=payload)
                ip = dpkt.ip.IP(src=bytes([10, 0, 0, 2 if reverse else 1]), dst=bytes([10, 0, 0, 1 if reverse else 2]),
                                p=6, ttl=first_ttl if i == 0 else 64, data=tcp)
                ip.len = len(ip)
                packet = dpkt.ethernet.Ethernet(src=bytes.fromhex("000000000002" if reverse else "000000000001"),
                                                dst=bytes.fromhex("000000000001" if reverse else "000000000002"),
                                                type=dpkt.ethernet.ETH_TYPE_IP, data=ip)
                writer.writepkt(bytes(packet), ts=(0.5 if reverse_time and i == 3 else first_time + i * 0.01))
        return path

    def decoded(self, path):
        return list(m.decode_rows(path, self.fields, TSHARK, path.with_suffix(".stderr")))

    def targets(self, path, rows, frames=(1, 4), label=0, role="TRAIN"):
        spec = dict(planned_role=role, member_path="synthetic/Hydra/input.pcap" if label else "synthetic/normal/input.pcap",
                    member_sha256=m.sha256(path), provenance_kind="attack_experiment_candidate" if label else "normal_interaction_candidate")
        targets = [dict(uid="synthetic:%d" % i, device="amcrest", label=label, planned_role=role,
                        frame_number_1based=i, timestamp=float(rows[i - 1]["frame.time_epoch"]),
                        stream="tcp:" + rows[i - 1]["tcp.stream"], member_path=spec["member_path"], member_sha256=spec["member_sha256"]) for i in frames]
        return targets, spec

    def materialize(self, path, frames=(1, 4), label=0, runtime=None):
        rows = self.decoded(path)
        targets, spec = self.targets(path, rows, frames, label)
        runtime = runtime or self.runtime()
        result, audit = m.materialize_capture(iter(rows), targets, spec, runtime, {"amcrest": CAM_MAC}, batch_size=16)
        return result, audit, runtime

    def test_real_decoder_tokenizer_collator_adapter_and_future_invariance(self):
        base, a1, runtime1 = self.materialize(self.capture())
        changed, a2, runtime2 = self.materialize(self.capture("future.pcap", future_window=16))
        self.assertEqual(a1["packets"], 4)
        self.assertEqual(a1["E3_forward_rows"], 2)
        self.assertEqual(a1["target_snapshot_deep_copies"], 2)
        # Both targets are embedded after all four packets in ONE deferred batch.
        self.assertEqual(len(runtime1["model"].calls), 1)
        self.assertEqual(runtime1["model"].calls[0]["input_ids"].shape[0], 2)
        np.testing.assert_array_equal(base["synthetic:1"], changed["synthetic:1"])
        self.assertFalse(np.array_equal(base["synthetic:4"], changed["synthetic:4"]))
        self.assertEqual(base["synthetic:1"].shape, (768,))
        self.assertEqual(base["synthetic:1"].dtype, np.float32)
        self.assertEqual(a1, a2)

    def test_prior_context_affects_current_target(self):
        baseline, _, _ = self.materialize(self.capture(), frames=(4,))
        changed, _, _ = self.materialize(self.capture("prior.pcap", first_ttl=8), frames=(4,))
        self.assertFalse(np.array_equal(baseline["synthetic:4"], changed["synthetic:4"]))

    def test_deepcopy_protects_pending_target_from_reused_nested_translator_buffers(self):
        path = self.capture()
        baseline, _, _ = self.materialize(path)
        shared = {}

        def reusable(rows):
            current = translator.netfound_flow(rows)
            for key, value in current.items():
                if isinstance(value, list) and key in shared:
                    shared[key][:] = value
                else:
                    shared[key] = value
            return shared

        result, _, _ = self.materialize(path, runtime=self.runtime(SimpleNamespace(netfound_flow=reusable)))
        for uid in result:
            np.testing.assert_array_equal(result[uid], baseline[uid])

    def test_contexts_reset_between_captures(self):
        runtime = self.runtime()
        self.materialize(self.capture("first.pcap", first_ttl=5), runtime=runtime)
        shared_runtime, _, _ = self.materialize(self.capture("second.pcap"), runtime=runtime)
        fresh_runtime, _, _ = self.materialize(self.root / "second.pcap")
        for uid in shared_runtime:
            np.testing.assert_array_equal(shared_runtime[uid], fresh_runtime[uid])

    def test_attack_evidence_only_current_request_not_previous_handshake(self):
        path = self.capture()
        result, _, _ = self.materialize(path, frames=(4,), label=1)
        self.assertEqual(len(result), 1)
        with self.assertRaisesRegex(m.Stop, "ATTACK_CURRENT_PACKET_EVIDENCE"):
            self.materialize(path, frames=(1,), label=1)
        benign, _, _ = self.materialize(path, frames=(4,), label=0)
        np.testing.assert_array_equal(result["synthetic:4"], benign["synthetic:4"])

    def test_midstream_capture_does_not_require_syn(self):
        path = self.capture()
        rows = self.decoded(path)[2:]
        for i, row in enumerate(rows, 1):
            row["frame.number"] = str(i)
        targets, spec = self.targets(path, rows, frames=(2,))
        values, _ = m.materialize_capture(iter(rows), targets, spec, self.runtime(), {"amcrest": CAM_MAC})
        self.assertEqual(len(values), 1)

    def test_nonfinite_output_timestamp_regression_and_missing_target_stop(self):
        path = self.capture()
        runtime = self.runtime()
        rows = self.decoded(path)
        targets, spec = self.targets(path, rows)
        with mock.patch.object(embed, "embed_flows", return_value=np.full((2, 768), np.nan, dtype=np.float32)):
            with self.assertRaisesRegex(m.Stop, "E3_OUTPUT"):
                m.materialize_capture(iter(rows), targets, spec, runtime, {"amcrest": CAM_MAC})
        with self.assertRaisesRegex(m.Stop, "TARGET_UNENCODABLE"):
            self.materialize(self.capture("regression.pcap", reverse_time=True))
        with self.assertRaisesRegex(m.Stop, "CAPTURE_TARGET_COVERAGE"):
            m.materialize_capture(iter(rows[:3]), targets, spec, runtime, {"amcrest": CAM_MAC})

    def test_headers_role_and_metadata_fields_never_silently_pass(self):
        path = self.capture()
        rows = self.decoded(path)
        targets, spec = self.targets(path, rows)
        bad = copy.deepcopy(rows)
        bad[0]["tcp.window_size_value"] = ""
        with self.assertRaisesRegex(m.Stop, "TARGET_UNENCODABLE_OR_INCOMPLETE"):
            m.materialize_capture(iter(bad), targets, spec, self.runtime(), {"amcrest": CAM_MAC})
        targets[0]["planned_role"] = "CHECK"
        with self.assertRaisesRegex(m.Stop, "TARGET_CAPTURE_ROLE"):
            m.materialize_capture(iter(rows), targets, spec, self.runtime(), {"amcrest": CAM_MAC})

    def test_synthetic_plans_sampling_weights_roles_and_unknown_uid(self):
        args = synthetic_plan_set()
        self.assertEqual(len(m.validate_plans(*args)), 8)
        bad = copy.deepcopy(args)
        bad[0]["new_data"]["check_file_ids"].append(1)
        with self.assertRaisesRegex(m.Stop, "CAPTURE_ROLE_OVERLAP"):
            m.validate_plans(*bad)
        bad = copy.deepcopy(args)
        bad[2][0]["uid"] = "u0-unknown"
        with self.assertRaisesRegex(m.Stop, "REPRESENTATIVE_TARGET_IDENTITY"):
            m.validate_plans(*bad)
        bad = copy.deepcopy(args)
        bad[2][0]["conditional_weight_denominator"] = 2
        with self.assertRaisesRegex(m.Stop, "NEW_WEIGHT"):
            m.validate_plans(*bad)

    def test_selective_old_rows_and_state_do_not_decode_forbidden_members(self):
        plan = self.root / "fit.csv"
        rows = [dict(uid="a", phase="fit", role="support_train", source_group="s", device_family="d", attack_family="a", label_metric_only=0),
                dict(uid="b", phase="select", role="support_val", source_group="s", device_family="d", attack_family="a", label_metric_only=1)]
        with plan.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.META)
            writer.writeheader()
            writer.writerows(rows)
        path = self.root / "features.npz"
        x = np.full((2, 768), np.nan, dtype=np.float32)
        x[1] = 7
        np.savez_compressed(path, uid=np.asarray(["b", "a"]), missing=np.asarray([True, False]), candidate_id=np.asarray(["E3"]),
                            plan_sha256=np.asarray([m.sha256(plan)]), contract_sha256=np.asarray([reader.CONTRACT]),
                            representation=x, G0=np.asarray([object()], dtype=object))
        target = dict(uid="a", owner="A", planned_role="OLD_REPLAY", historical_role="support_train", label=0)
        audit = {}
        with mock.patch.object(np, "load", side_effect=AssertionError("broad np.load prohibited")):
            out = m.select_old_features(path, plan, m.sha256(plan), [target], audit)
        np.testing.assert_array_equal(out, np.full((1, 768), 7, dtype=np.float32))
        self.assertEqual(audit["numeric_representation_rows"], 1)
        with self.assertRaisesRegex(m.Stop, "OLD_UNKNOWN_UID"):
            m.select_old_features(path, plan, m.sha256(plan), [dict(target, uid="unauthorized")], {})
        state = {key: np.zeros(shape, dtype=np.float64 if key.startswith("normalizer") else np.float32) for key, shape in reader.STATE_SHAPES.items()}
        state["normalizer_scale"][:] = 1
        state_path = self.root / "state.npz"
        np.savez(state_path, **state, g0_reference=np.asarray([object()], dtype=object), p1_coef=np.asarray([object()], dtype=object))
        self.assertEqual(set(reader.load_p2_state(state_path)), set(m.STATE_NAMES))

    def test_cache_physical_split_and_byte_identical_metadata(self):
        targets = [dict(uid="a", label=0, planned_role="TRAIN")]
        source = self.root / "source.jsonl"
        dump_plan(source, targets)
        output = self.root / "out"
        artifact = m.write_cache(output, "train/old_cache.npz", np.zeros((1, 768), dtype=np.float32), targets, source)
        check = m.write_cache(output, "check/new_check_cache.npz", np.ones((1, 768), dtype=np.float32), targets, source)
        self.assertNotEqual(Path(artifact["path"]).parent, Path(check["path"]).parent)
        self.assertEqual((output / artifact["metadata_path"]).read_bytes(), source.read_bytes())
        with np.load(output / artifact["path"], allow_pickle=False) as cache:
            self.assertEqual(set(cache.files), {"uid", "x", "y"})

    def test_exact_archive_extraction_cannot_traverse_or_open_other_members(self):
        archive = self.root / "synthetic.tar.gz"
        payload = b"synthetic pcap placeholder"
        with tarfile.open(archive, "w:gz") as tar:
            for name, raw in (("../../escape.pcap", payload), ("never-selected.pcap", b"unselected")):
                member = tarfile.TarInfo(name)
                member.size = len(raw)
                tar.addfile(member, io.BytesIO(raw))
        spec = dict(file_id=1, planned_role="TRAIN", archive_path=archive.name, archive_sha256=m.sha256(archive),
                    member_path="../../escape.pcap", member_sha256=hashlib.sha256(payload).hexdigest(), member_bytes=len(payload))
        paths = m.extract_captures([spec], self.root / "out", root=self.root)
        self.assertEqual(paths[1], self.root / "out/train/raw/01.pcap")
        self.assertEqual(paths[1].read_bytes(), payload)
        self.assertEqual([p.name for p in (self.root / "out").rglob("*.pcap")], ["01.pcap"])

    def test_id_extension_uses_exact_frame_timestamp_session_and_full_prefix(self):
        path = self.capture()
        rows = self.decoded(path)
        base, spec = self.targets(path, rows, frames=(4,), role="ID_TEST")
        target = base[0]
        key = probe.old_key(self.event.event_from_tshark(rows[3]))
        target.update(position_zero_based=3, session_key_sha256=hashlib.sha256(repr(key).encode()).hexdigest(),
                      source_cutoff_frame_1based=0, source_cutoff_time=0., session_first_frame=1)
        out, audit = m.materialize_capture(iter(rows), [target], spec, self.runtime(), {})
        self.assertEqual(audit["packets"], 4)
        self.assertEqual(len(out), 1)
        target["session_key_sha256"] = "bad"
        with self.assertRaisesRegex(m.Stop, "ID_CANONICAL_SESSION_JOIN"):
            m.materialize_capture(iter(rows), [target], spec, self.runtime(), {})

    def test_id_raw_packet_pin_includes_current_target_bytes(self):
        path = self.capture()
        with path.open("rb") as f:
            packets = list(dpkt.pcap.Reader(f))
        ts, packet = packets[-1]
        target = dict(frame_number_1based=4, timestamp=float(ts), packet_sha256=hashlib.sha256(packet).hexdigest())
        m.verify_id_raw_targets(path, [target], 4)
        with self.assertRaisesRegex(m.Stop, "ID_RAW_PACKET_JOIN"):
            m.verify_id_raw_targets(path, [dict(target, packet_sha256="wrong")], 4)

    def test_id_metadata_seal_counts_and_train_exclusion(self):
        boundary = {"source_local_later_than_old_fit_select": True, "predecessor_development_untouched": False}
        target = dict(uid="id", member_path="normal.pcap", raw_member="normal.pcap", member_sha256="m", planned_role="ID_TEST", role="ID_TEST",
                      label=0, device_family="synthetic", independence_boundary=boundary, frame_number_1based=2, position_zero_based=1, session_key_sha256="s")
        plan = self.root / "id.jsonl"
        dump_plan(plan, [target])
        report = self.root / "qualification.json"
        m.atomic_json(report, dict(status="PASS_WITH_DECLARED_LIMITS", target_plan_sha256=m.sha256(plan), independence_boundary=boundary,
                                   qualified_targets=1, qualified_canonical_sessions=1))
        manifest = self.root / "identity.json"
        m.atomic_json(manifest, {"synthetic": True})
        extension = dict(schema="legacy-id-test-extension-v2", qualified=True, status="QUALIFIED_WITH_DECLARED_LIMITS", planned_role="ID_TEST", label=0,
                         device_family="synthetic", model_features_materialized=False, scored=False, rows=1, canonical_sessions=1,
                         target_plan_path=str(plan), target_plan_sha256=m.sha256(plan),
                         qualification=dict(path=str(report), sha256=m.sha256(report), independence_boundary=boundary),
                         metadata_identity=dict(qualification_manifest_path=str(manifest), qualification_manifest_sha256=m.sha256(manifest)),
                         member_pins={"normal.pcap": dict(sha256="m", packets=2)})
        actual, _, _ = m.validate_id_metadata(extension, root=self.root)
        self.assertEqual(actual, [target])
        with self.assertRaisesRegex(m.Stop, "ID_CROSS_ROLE_UID"):
            m.validate_id_metadata(extension, [dict(uid="id", member_sha256="different")], root=self.root)
        with self.assertRaisesRegex(m.Stop, "ID_CROSS_ROLE_MEMBER"):
            m.validate_id_metadata(extension, [dict(uid="train", member_sha256="m")], root=self.root)
        with self.assertRaisesRegex(m.Stop, "ID_TARGET_COUNT"):
            m.validate_id_metadata(dict(extension, rows=2), root=self.root)

    def test_prepare_manifest_training_confinement_and_fail_stop_status(self):
        """Exercise orchestration using only tiny synthetic assets and stub E3."""
        capture = self.capture()
        decoded = self.decoded(capture)
        train, train_spec = self.targets(capture, decoded, frames=(1,), role="TRAIN")
        check, check_spec = self.targets(capture, decoded, frames=(4,), role="CHECK")
        train[0]["uid"], train[0]["file_id"] = "new-train", 1
        check[0]["uid"], check[0]["file_id"] = "new-check", 2
        train_spec["file_id"], check_spec["file_id"] = 1, 2
        old = [dict(uid="old", owner="A", planned_role="OLD_REPLAY", historical_role="support_train", label=0)]
        paths = {role: self.root / (role + ".jsonl") for role in ("old", "train", "check")}
        for role, targets in (("old", old), ("train", train), ("check", check)):
            dump_plan(paths[role], targets)
        state = {key: np.zeros(shape, dtype=np.float64 if key.startswith("normalizer") else np.float32) for key, shape in reader.STATE_SHAPES.items()}
        state["normalizer_scale"][:] = 1
        state_path = self.root / "ckda_d1_probe_state.npz"
        np.savez(state_path, **state)
        fit_path = self.root / "ckda_d1_fit_select_plan.csv"
        with fit_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=reader.META)
            writer.writeheader()
            writer.writerow(dict(uid="old", phase="fit", role="support_train", source_group="s", device_family="d", attack_family="normal", label_metric_only=0))
        fit_x = self.root / "ckda_d1_fit_select_embeddings.npz"
        np.savez(fit_x, uid=np.asarray(["old"]), missing=np.asarray([False]), candidate_id=np.asarray(["E3"]),
                 plan_sha256=np.asarray([m.sha256(fit_path)]), contract_sha256=np.asarray([reader.CONTRACT]), representation=np.zeros((1, 768), dtype=np.float32))
        marker = self.root / "ckda_d1_threshold_freeze_marker.json"
        m.atomic_json(marker, dict(probe_state_sha256=m.sha256(state_path)))
        recipe = dict(legacy_asset_pins=dict(files={p.name: m.sha256(p) for p in (state_path, fit_path, fit_x, marker)}),
                      model=dict(state_array_allowlist=list(m.STATE_NAMES), e3_batch_size=16, new_e3_targets=2))
        metadata = dict(old=old, train=train, check=check, captures=[train_spec, check_spec], plan_paths=paths,
                        review=dict(identity=dict(devices={"amcrest": CAM_MAC}),
                                    file_results=[dict(file_id=i, packets=4, legacy_prefix_eligible_packets=4) for i in (1, 2)]))
        runtime = self.runtime()
        runtime["dependency_identity"] = dict(synthetic=True)
        id_targets = [dict(uid="new-id", label=0, planned_role="ID_TEST")]
        id_plan = self.root / "id-test.jsonl"
        dump_plan(id_plan, id_targets)
        id_extension = dict(status="QUALIFIED_WITH_DECLARED_LIMITS", canonical_sessions=1,
                            qualification=dict(independence_boundary={"synthetic": True}))
        id_report = dict(qualified_sources={"synthetic": 1}, qualified_protocol_targets={"17": 1})
        out = self.root / "prepared"
        with mock.patch.object(m, "ROOT", self.root), mock.patch.object(m, "load_recipe", return_value=recipe), \
             mock.patch.object(m, "load_frozen_metadata", return_value=metadata), \
             mock.patch.object(m, "build_runtime", return_value=runtime), \
             mock.patch.object(m, "extract_captures", return_value={1: capture, 2: capture}), \
             mock.patch.object(m, "load_id_extension", return_value=(id_extension, id_targets, id_plan, id_report)), \
             mock.patch.object(m, "materialize_id", return_value=(np.zeros((1, 768), dtype=np.float32), [])):
            manifest = m.prepare(recipe, out, id_extension="synthetic")
        self.assertEqual(manifest["status"], "PREPARE_COMPLETE")
        train_manifest_path = out / manifest["training_manifest"]
        descriptor = json.loads(train_manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(set(descriptor["artifacts"]), {"old_cache", "new_train_cache", "reference_state"})
        for artifact in descriptor["artifacts"].values():
            self.assertTrue((train_manifest_path.parent / artifact["path"]).resolve().is_relative_to(train_manifest_path.parent))
            self.assertNotIn("..", artifact["path"])
        self.assertEqual(manifest["training_manifest_sha256"], m.sha256(train_manifest_path))
        completed = json.loads((out / "status.json").read_text())
        self.assertEqual(completed["status"], "PREPARE_COMPLETE")
        self.assertEqual((completed["done"], completed["total"]), (3, 3))
        self.assertEqual(completed["total"], sum(manifest["artifacts"][key]["rows"] for key in ("new_train_cache", "new_check_cache", "id_cache")))
        failed = self.root / "failed"
        with mock.patch.object(m, "load_recipe", return_value=recipe), \
             mock.patch.object(m, "load_frozen_metadata", side_effect=m.Stop("synthetic failure")):
            with self.assertRaisesRegex(m.Stop, "synthetic failure"):
                m.prepare(recipe, failed)
        failure = json.loads((failed / "prepare_failure.json").read_text())
        self.assertEqual(failure["retries"], 0)
        self.assertIsNone(failure["scientific_verdict"])
        self.assertEqual(json.loads((failed / "status.json").read_text())["status"], "PREPARE_FAILED")


if __name__ == "__main__":
    unittest.main()
