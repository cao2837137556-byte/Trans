from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("issue27ckda_d0_representation_compatibility_audit_v1.py")
SPEC = importlib.util.spec_from_file_location("ckda_d0_test_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ckda = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckda)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
