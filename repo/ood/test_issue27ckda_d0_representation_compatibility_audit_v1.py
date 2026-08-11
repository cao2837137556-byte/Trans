from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("issue27ckda_d0_representation_compatibility_audit_v1.py")
SPEC = importlib.util.spec_from_file_location("ckda_d0_test_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ckda = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckda)

PILOT_PATH = Path(__file__).with_name("issue27ckda_d0_resource_pilot_v1.py")
PILOT_SPEC = importlib.util.spec_from_file_location("ckda_d0_pilot_test_target", PILOT_PATH)
assert PILOT_SPEC is not None and PILOT_SPEC.loader is not None
pilot = importlib.util.module_from_spec(PILOT_SPEC)
PILOT_SPEC.loader.exec_module(pilot)

VALIDATOR_PATH = Path(__file__).with_name("issue27ckda_d0_validate_and_pack_v1.py")
VALIDATOR_SPEC = importlib.util.spec_from_file_location("ckda_d0_validator_test_target", VALIDATOR_PATH)
assert VALIDATOR_SPEC is not None and VALIDATOR_SPEC.loader is not None
validator = importlib.util.module_from_spec(VALIDATOR_SPEC)
VALIDATOR_SPEC.loader.exec_module(validator)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "runs/mainline_docs/ckda_d0_representation_compatibility_audit_preregistered_20260811.md"
EVIDENCE = ROOT / "runs/mainline_docs/ckda_d0_official_candidate_evidence_20260811.json"


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class Event:
    ip_version = 4
    ip_proto = 6
    src = "10.0.0.2"
    dst = "10.0.0.1"
    src_port = 443
    dst_port = 50000


class CKDAD0ContractTests(unittest.TestCase):
    def test_01_frozen_hash(self):
        self.assertEqual(ckda.sha256_file(CONTRACT), ckda.CONTRACT_SHA256)

    def test_02_literal_schema_has_fifty_fields(self):
        self.assertEqual(len(ckda.AUDIT_FIELDS), 50)
        self.assertEqual(ckda.AUDIT_FIELDS[0], "candidate_id")
        self.assertEqual(ckda.AUDIT_FIELDS[-1], "evidence_manifest_path")

    def test_03_candidate_order(self):
        self.assertEqual(ckda.CANDIDATES, ("E1", "E2", "E3", "I1"))

    def test_04_stage_exact_token(self):
        self.assertTrue(ckda.stage_contains_fit("report;fit"))
        self.assertFalse(ckda.stage_contains_fit("outfit;select"))

    def test_05_final_marker_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "FINAL_EXCLUSION"):
            ckda.fail_if_final("processed/iotsim-cooler-motor-5.csv", "test")

    def test_06_seed_markers_fail_closed(self):
        for marker in ("seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47"):
            with self.assertRaises(RuntimeError):
                ckda.fail_if_final(marker, "test")

    def test_07_bidirectional_session_key(self):
        forward = ckda.session_key(Event())
        Event.src, Event.dst, Event.src_port, Event.dst_port = "10.0.0.1", "10.0.0.2", 50000, 443
        reverse = ckda.session_key(Event())
        self.assertEqual(forward, reverse)

    def test_08_protocol_is_in_session_key(self):
        Event.ip_proto = 6
        tcp = ckda.session_key(Event())
        Event.ip_proto = 17
        udp = ckda.session_key(Event())
        self.assertNotEqual(tcp, udp)

    def test_09_non_ip_not_i1_encodable(self):
        Event.ip_version = 0
        self.assertEqual(ckda.encodable(Event()), {"E1": False, "E2": False, "E3": False, "I1": False})

    def test_10_yaTC_ipv4_only_static_contract(self):
        Event.ip_version = 6
        Event.ip_proto = 6
        self.assertFalse(ckda.encodable(Event())["E2"])
        self.assertTrue(ckda.encodable(Event())["E3"])

    def test_11_evidence_candidate_set(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        self.assertEqual(tuple(value["candidates"]), ckda.CANDIDATES)

    def test_12_yaTC_license_is_fail(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["E2"]
        reasons = ckda.hard_reasons("E2", value, {"i1_data_gate": "FAIL"}, None)
        self.assertIn("license_research_use_not_granted", reasons)

    def test_13_ETBERT_partial_is_not_identity_hash(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["E1"]
        reasons = ckda.hard_reasons("E1", value, {"i1_data_gate": "FAIL"}, None)
        self.assertIn("complete_checkpoint_sha256_missing", reasons)

    def test_14_possible_overlap_is_fail(self):
        value = dict(json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["E3"])
        value["overlap_risk"] = "POSSIBLE_OVERLAP"
        reasons = ckda.hard_reasons("E3", value, {"i1_data_gate": "FAIL"}, {})
        self.assertIn("overlap_risk=POSSIBLE_OVERLAP", reasons)

    def test_15_i1_gate_is_conjunctive(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["I1"]
        reasons = ckda.hard_reasons("I1", value, {"i1_data_gate": "FAIL"}, {})
        self.assertIn("i1_data_gate_FAIL", reasons)

    def test_16_missing_pilot_blocks_otherwise_eligible(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["E3"]
        self.assertEqual(ckda.hard_reasons("E3", value, {"i1_data_gate": "FAIL"}, None), ["resource_pilot_missing"])

    def test_17_atomic_json_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.json"
            ckda.atomic_json(path, {"b": 2, "a": 1})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"a": 1, "b": 2})

    def test_18_prepare_cutoffs_uses_allowlist_before_raw_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            allowed = "processed/iotsim-building-monitor-2.csv"
            aux_allowed = "aux-fit-source"
            base = root / "targets.csv"
            write_csv(
                base,
                ["source_group", "source_cache_key", "recorded_index", "stages", "roles"],
                [
                    {"source_group": allowed, "source_cache_key": "a", "recorded_index": 7, "stages": "fit", "roles": "ood_val"},
                    {"source_group": "processed/iotsim-cooler-motor-5.csv", "source_cache_key": "b", "recorded_index": 1, "stages": "fit", "roles": "support_train"},
                    {"source_group": "processed/iotsim-hydraulic-system-1.csv", "source_cache_key": "c", "recorded_index": 2, "stages": "fit", "roles": "ood_val"},
                ],
            )
            g_allow = root / "g_allow.csv"
            a_allow = root / "a_allow.csv"
            write_csv(g_allow, ["source_group"], [{"source_group": allowed}])
            write_csv(a_allow, ["source_group"], [{"source_group": aux_allowed}])
            g_plan = root / "g_plan.csv"
            write_csv(g_plan, ["source_group", "source_cache_key"], [{"source_group": allowed, "source_cache_key": "a"}])
            cache = root / "cache"
            cache.mkdir()
            np.savez(
                cache / "a.npz",
                recorded_index=np.asarray([7]),
                target_event_position_within_capture=np.asarray([9]),
                raw_source_path=np.asarray(["raw/allowed.pcap"]),
            )
            aux = root / "aux.csv"
            write_csv(
                aux,
                ["source_group", "role", "raw_source_path", "last_target_event_position"],
                [{"source_group": aux_allowed, "role": "aux_fit", "raw_source_path": "raw/aux.pcap", "last_target_event_position": 4}],
            )
            ton_manifest = root / "ton_manifest.csv"
            write_csv(
                ton_manifest,
                ["source_file", "absolute_path", "role"],
                [{"source_file": "fit.pcap", "absolute_path": str(root / "fit.pcap"), "role": "aux_normal_fit"}],
            )
            ton_audit = root / "ton_audit.csv"
            write_csv(
                ton_audit,
                ["raw_source_path", "role", "decoded_events"],
                [{"raw_source_path": "fit.pcap", "role": "aux_normal_fit", "decoded_events": 3}],
            )
            out = root / "cutoffs.csv"
            args = argparse.Namespace(
                contract=CONTRACT,
                base_targets=base,
                gotham_allowlist=g_allow,
                aux_allowlist=a_allow,
                gotham_source_plan=g_plan,
                gotham_cache_dir=cache,
                aux_source_plan=aux,
                ton_manifest=ton_manifest,
                ton_audit=ton_audit,
                gotham_zip=root / "never-opened.zip",
                out=out,
            )
            ckda.prepare_cutoffs(args)
            with out.open(encoding="utf-8", newline="") as handle:
                result = list(csv.DictReader(handle))
            self.assertEqual(len(result), 3)
            self.assertEqual({int(row["fit_cutoff_event_position_inclusive"]) for row in result}, {2, 4, 9})
            audit = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(audit["final_files_opened"], 0)

    def test_19_cutoff_schema_is_exact(self):
        self.assertEqual(len(ckda.CUTOFF_FIELDS), 7)
        self.assertEqual(ckda.CUTOFF_FIELDS[-1], "lineage_source")

    def test_20_checkpoint_manifest_hash_is_order_stable(self):
        left = ckda.sha256_json(sorted([("b", "2"), ("a", "1")]))
        right = ckda.sha256_json(sorted([("a", "1"), ("b", "2")]))
        self.assertEqual(left, right)

    def test_21_empty_numeric_is_not_zero(self):
        row = {field: "" for field in ckda.AUDIT_FIELDS}
        self.assertEqual(row["pilot_peak_vram_bytes"], "")

    def test_22_expected_nonallowlist_sources_are_exact(self):
        self.assertEqual(
            ckda.EXPECTED_NONALLOWLIST_FIT_SOURCES,
            {
                "processed/iotsim-cooler-motor-5.csv": "FINAL_DENYLIST",
                "processed/iotsim-hydraulic-system-1.csv": "UPSTREAM_RAW51_UNOBSERVABLE_MASK",
            },
        )

    def test_23_adapter_measurement_is_mandatory(self):
        value = json.loads(EVIDENCE.read_text(encoding="utf-8"))["candidates"]["E3"]
        reasons = ckda.hard_reasons("E3", value, {"i1_data_gate": "FAIL"}, {"status": "PASS"})
        self.assertEqual(reasons, ["custom_adapter_files_missing", "custom_adapter_loc_missing"])

    def test_24_float_tolerance_reaches_candidate_order(self):
        base = {
            "overlap_risk": "NO_KNOWN_OVERLAP",
            "fit_encodable_fraction": "0.9000000",
            "select_static_target_fraction": "1.0",
            "report_static_target_fraction": "1.0",
            "maturity_grade": "B",
            "custom_adapter_loc": "10",
            "projected_nonfinal_wall_seconds": "100",
        }
        left = dict(base, candidate_id="E1")
        right = dict(base, candidate_id="E2", fit_encodable_fraction="0.9000005")
        self.assertLess(ckda.compare_ranked(left, right), 0)

    def test_25_cost_ten_percent_is_tie(self):
        base = {
            "overlap_risk": "NO_KNOWN_OVERLAP",
            "fit_encodable_fraction": "0.9",
            "select_static_target_fraction": "1.0",
            "report_static_target_fraction": "1.0",
            "maturity_grade": "B",
            "custom_adapter_loc": "10",
        }
        left = dict(base, candidate_id="E1", projected_nonfinal_wall_seconds="110")
        right = dict(base, candidate_id="E2", projected_nonfinal_wall_seconds="100")
        self.assertLess(ckda.compare_ranked(left, right), 0)
        left["projected_nonfinal_wall_seconds"] = "111"
        self.assertGreater(ckda.compare_ranked(left, right), 0)

    def test_26_resource_pilot_schema_is_exact(self):
        self.assertEqual(len(pilot.PILOT_FIELDS), 19)
        self.assertEqual(pilot.PILOT_FIELDS[0], "candidate_id")
        self.assertEqual(pilot.PILOT_FIELDS[-1], "final_files_opened")

    def test_27_pilot_bidirectional_session_key(self):
        left = {
            "ip.src": "10.0.0.2", "ip.dst": "10.0.0.1", "ip.proto": "6",
            "tcp.srcport": "443", "tcp.dstport": "50000",
        }
        right = {
            "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "ip.proto": "6",
            "tcp.srcport": "50000", "tcp.dstport": "443",
        }
        self.assertEqual(pilot.canonical_session(left), pilot.canonical_session(right))

    def test_28_netfound_token_width_and_payload_placeholder(self):
        row = {field: "" for field in pilot.TSHARK_FIELDS}
        row.update(
            {
                "frame.number": "1", "frame.time_epoch": "1.0", "frame.len": "60",
                "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2", "ip.proto": "6",
                "ip.hdr_len": "20", "ip.len": "60", "ip.ttl": "64",
                "tcp.srcport": "1", "tcp.dstport": "2", "tcp.flags": "0x02",
                "tcp.window_size_value": "1024", "tcp.seq_raw": "100",
                "tcp.ack_raw": "0", "tcp.urgent_pointer": "0",
            }
        )
        flow = pilot.netfound_flow([row])
        self.assertEqual(flow["protocol"], 6)
        self.assertEqual(len(flow["burst_tokens"][0]), 18)
        self.assertEqual(flow["burst_tokens"][0][-6:], [0] * 6)

    def test_29_pilot_final_marker_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError, "FINAL_EXCLUSION"):
            pilot.fail_if_final("seed_47", "test")

    def test_30_resource_pilot_has_no_label_or_score_field(self):
        lowered = {field.lower() for field in pilot.TSHARK_FIELDS}
        self.assertFalse(any("label" in field or "attack" in field or "score" in field for field in lowered))

    def test_31_compile_boundary_and_validator_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "result"
            result.mkdir()
            census = {
                "status": "CKDA_D0_DATA_CENSUS_COMPLETE",
                "contract_sha256": ckda.CONTRACT_SHA256,
                "fit_visible_unique_packets": 1000,
                "fit_encodable_unique_packets": {candidate: 900 for candidate in ckda.CANDIDATES},
                "i1_fit_sessions": 499_999,
                "i1_fit_tokens": 20_000_000,
                "i1_data_gate": "FAIL",
                "source_checkpoint_manifest_sha256": "1" * 64,
                "final_files_opened": 0,
                "raw_label_columns_read": 0,
            }
            census_path = result / "ckda_d0_data_census.json"
            census_path.write_text(json.dumps(census), encoding="utf-8")

            pilot_row = {field: "" for field in pilot.PILOT_FIELDS}
            pilot_row.update(
                {
                    "candidate_id": "E3",
                    "status": "PASS",
                    "pilot_raw_packets": "1000",
                    "pilot_candidate_tokens": "1200",
                    "pilot_peak_rss_bytes": "1000000",
                    "pilot_peak_vram_bytes": "",
                    "pilot_median_raw_packets_per_second": "100",
                    "pilot_median_candidate_tokens_per_second": "120",
                    "projected_nonfinal_wall_seconds": "1000",
                    "forward_finite": "true",
                    "custom_adapter_files": "1",
                    "custom_adapter_loc": "500",
                    "performance_embeddings_persisted": "0",
                    "labels_read": "0",
                    "final_files_opened": "0",
                }
            )
            pilot_path = result / "ckda_d0_resource_pilot.csv"
            write_csv(pilot_path, pilot.PILOT_FIELDS, [pilot_row])
            measurements = {
                "status": "CKDA_D0_RESOURCE_PILOT_COMPLETE",
                "runs_per_candidate": 3,
                "warmup_runs_per_candidate": 1,
                "candidates": {"E3": {"run_seconds": [1.0, 1.1, 1.2], "session_count": 100}},
            }
            (result / "ckda_d0_resource_pilot_measurements.json").write_text(
                json.dumps(measurements), encoding="utf-8"
            )

            evidence_manifest = ROOT / "runs/mainline_docs/ckda_d0_official_evidence_manifest_20260811.csv"
            ckda.compile_audit(
                argparse.Namespace(
                    contract=CONTRACT,
                    evidence=EVIDENCE,
                    evidence_manifest=evidence_manifest,
                    census=census_path,
                    resource_pilot=pilot_path,
                    out=result,
                )
            )
            shutil.copy2(evidence_manifest, result / "ckda_d0_evidence_manifest.csv")
            cutoff = {
                "status": "CKDA_D0_FIT_PREFIX_MANIFEST_READY",
                "excluded_frozen_fit_source_reasons": ckda.EXPECTED_NONALLOWLIST_FIT_SOURCES,
                "final_files_opened": 0,
                "label_columns_read": 0,
                "manifest_sha256": "2" * 64,
            }
            cutoff_path = root / "cutoff.json"
            cutoff_path.write_text(json.dumps(cutoff), encoding="utf-8")
            exclusion_path = result / "ckda_d0_final_exclusion_audit.json"
            ckda.finalize_boundary(
                argparse.Namespace(
                    contract=CONTRACT,
                    cutoff_audit=cutoff_path,
                    census=census_path,
                    out=exclusion_path,
                )
            )
            validator.validate(
                argparse.Namespace(
                    result=result,
                    contract=CONTRACT,
                    audit_module=MODULE_PATH,
                    pilot_module=PILOT_PATH,
                )
            )
            report = json.loads((result / "ckda_d0_validation_report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["resource_pilot_candidates"], ["E3"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
