from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional


MODULE_PATH = Path(__file__).with_name("issue27ckdb_d0_p3_combined_large_download_and_census_v1.py")
SPEC = importlib.util.spec_from_file_location("ckdb_d0_p3_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ckdb = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = ckdb
SPEC.loader.exec_module(ckdb)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "runs/mainline_docs/ckdb_d0_p3_combined_large_download_and_census_preregistered_20260818.md"
CONTRACT_SIDECAR = Path(str(CONTRACT) + ".sha256")
PLAN = ROOT / "runs/mainline_docs/ckdb_d0_p3_execution_plan_20260818.json"
PLAN_SIDECAR = Path(str(PLAN) + ".sha256")


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_sidecar(path: Path) -> Path:
    sidecar = Path(str(path) + ".sha256")
    sidecar.write_text("%s  %s\n" % (ckdb.sha256_file(path), path.name), encoding="utf-8")
    return sidecar


def base_appendix() -> Dict[str, Any]:
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    values = []
    for item in plan["objects"]:
        object_id = item["object_id"]
        values.append({
            "candidate_id": item["candidate_id"],
            "object_id": object_id,
            "stable_dataset_id": item["stable_dataset_id"],
            "publisher_relative_path": {
                "unsw_pcaps": "pcaps.zip",
                "cic_benign_pcaps": "benign/normal.zip",
                "pnnl_opaque_tar": "PNNL_IDS.tar",
            }[object_id],
            "destination_relative_path": {
                "unsw_pcaps": "quarantine/UNSW_IOTRAFFIC/pcaps.zip",
                "cic_benign_pcaps": "quarantine/CIC_MODBUS_2023/normal.zip",
                "pnnl_opaque_tar": "quarantine/PNNL_ELECTRICITY_AND_GAS_IDS/PNNL_IDS.tar",
            }[object_id],
            "expected_archive_kind": "tar" if object_id == "pnnl_opaque_tar" else "zip",
            "expected_bytes": None,
            "publisher_sha256": "NOT_PUBLISHED",
            "stream_hard_cap_bytes": 1024 * 1024,
            "extracted_size_cap_bytes": 4 * 1024 * 1024,
            "allowed_final_hosts": ["official.example"],
            "benign_member_paths": ["benign/normal.pcap"] if object_id == "cic_benign_pcaps" else [],
            "benign_subtree": "",
        })
    return {
        "schema_version": ckdb.APPENDIX_SCHEMA,
        "contract_sha256": ckdb.CONTRACT_SHA256,
        "execution_plan_sha256": ckdb.PLAN_SHA256,
        "independent_review": {"status": "PASS", "commit": "0123456"},
        "p0": {
            "P0_A": "CLOSED_FROM_AUTHENTICATED_OFFICIAL_INVENTORY",
            "P0_B": "CLOSED_FROM_AUTHENTICATED_OFFICIAL_INVENTORY",
            "P0_C": "CLOSED_FROM_AUTHENTICATED_OFFICIAL_INVENTORY",
        },
        "objects": values,
    }


def validate_appendix(value: Mapping[str, Any]) -> Mapping[str, Any]:
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "appendix.json"
        write_json(path, value)
        sidecar = write_sidecar(path)
        return ckdb.validate_launch_appendix(path, sidecar, ckdb.verify_plan(CONTRACT, PLAN))


def zip_bytes(files: Mapping[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in files.items():
            archive.writestr(name, payload)
    return stream.getvalue()


def make_zip(path: Path, files: Mapping[str, bytes]) -> None:
    path.write_bytes(zip_bytes(files))


def make_tar(path: Path, files: Mapping[str, bytes]) -> None:
    with tarfile.open(path, "w") as archive:
        for name, payload in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(payload))


class FakeResponse:
    def __init__(
        self,
        payload: bytes,
        url: str = "https://official.example/object",
        status: int = 200,
        headers: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._stream = io.BytesIO(payload)
        self._url = url
        self.status = status
        self.headers = dict(headers or {})

    def read(self, size: int = -1) -> bytes:
        return self._stream.read(size)

    def geturl(self) -> str:
        return self._url

    def getcode(self) -> int:
        return self.status

    def close(self) -> None:
        self._stream.close()


def transfer_spec(payload: bytes) -> Dict[str, Any]:
    return {
        "candidate_id": "UNSW_IOTRAFFIC",
        "object_id": "unsw_pcaps",
        "stable_dataset_id": "10.5061/dryad.w0vt4b94b",
        "publisher_relative_path": "pcaps.zip",
        "allowed_final_hosts": ["official.example"],
        "stream_hard_cap_bytes": len(payload) + 100,
        "expected_bytes": len(payload),
        "publisher_sha256": hashlib.sha256(payload).hexdigest(),
        "expected_archive_kind": "zip",
    }


def packet(
    position: int,
    timestamp_us: int,
    src: str = "10.0.0.1",
    dst: str = "10.0.0.2",
    src_port: int = 1000,
    dst_port: int = 80,
    protocol: int = 6,
    frame_len: int = 128,
    source: str = "FIT_A",
    member: str = "a.pcap",
    role: str = "external_benign_fit_candidate",
) -> Any:
    return ckdb.PacketRecord(
        source, member, "industrial", role, position, timestamp_us,
        src, src_port, dst, dst_port, protocol, frame_len,
    )


class CKDBD0P3ContractTests(unittest.TestCase):
    def test_01_frozen_protocol_and_plan_hash_match(self):
        self.assertEqual(ckdb.verify_sidecar(CONTRACT, CONTRACT_SIDECAR), ckdb.CONTRACT_SHA256)
        self.assertEqual(ckdb.verify_sidecar(PLAN, PLAN_SIDECAR), ckdb.PLAN_SHA256)
        self.assertEqual(ckdb.verify_plan(CONTRACT, PLAN)["schema_version"], ckdb.SCHEMA)

    def test_02_exact_three_candidates_and_no_corpus_search(self):
        plan = ckdb.verify_plan(CONTRACT, PLAN)
        self.assertEqual(tuple(plan["candidate_order"]), ckdb.CANDIDATES)
        self.assertFalse(plan["corpus_search_allowed"])
        self.assertFalse(plan["industrial_policy"]["replacement_corpus_allowed"])

    def test_03_all_p0_cells_must_close_before_launch(self):
        value = base_appendix()
        value["p0"]["P0_A"] = "PENDING"
        with self.assertRaisesRegex(ckdb.ContractError, "P0_A"):
            validate_appendix(value)

    def test_04_transient_secrets_absent_from_plan_appendix_and_authorization(self):
        text = PLAN.read_text(encoding="utf-8").lower()
        for marker in ckdb.PROHIBITED_PLAN_KEYS:
            self.assertNotIn('"%s"' % marker, text)
        value = base_appendix()
        value["access_token"] = "secret"
        with self.assertRaisesRegex(ckdb.ContractError, "secret field"):
            validate_appendix(value)

    def test_05_exact_host_and_object_cap_enforcement(self):
        payload = zip_bytes({"a.txt": b"a"})
        spec = transfer_spec(payload)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad_host = lambda _request: FakeResponse(payload, url="https://evil.example/x")
            with self.assertRaisesRegex(ckdb.TransferError, "host"):
                ckdb.transfer_object(spec, "https://official.example/x", root / "x.partial", root / "x.zip", bad_host)
            spec["stream_hard_cap_bytes"] = 2
            with self.assertRaisesRegex(ckdb.TransferError, "cap"):
                ckdb.transfer_object(spec, "https://official.example/x", root / "y.partial", root / "y.zip", lambda _r: FakeResponse(payload))

    def test_06_partial_is_not_promoted_before_hash_completion(self):
        payload = zip_bytes({"a.txt": b"a"})
        spec = transfer_spec(payload)
        spec["publisher_sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial, final = root / "x.partial", root / "x.zip"
            with self.assertRaisesRegex(ckdb.TransferError, "checksum"):
                ckdb.transfer_object(spec, "https://official.example/x", partial, final, lambda _r: FakeResponse(payload))
            self.assertTrue(partial.is_file())
            self.assertFalse(final.exists())

    def test_07_wrong_content_range_cannot_append(self):
        payload = zip_bytes({"a.txt": b"abc"})
        spec = transfer_spec(payload)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial = root / "x.partial"
            partial.write_bytes(payload[:10])
            before = partial.read_bytes()
            response = lambda _r: FakeResponse(payload[10:], status=206, headers={"Content-Range": "bytes 9-%d/%d" % (len(payload) - 1, len(payload))})
            with self.assertRaisesRegex(ckdb.TransferError, "Content-Range"):
                ckdb.transfer_object(spec, "https://official.example/x", partial, root / "x.zip", response)
            self.assertEqual(partial.read_bytes(), before)

    def test_08_published_checksum_mismatch_fails_closed(self):
        payload = zip_bytes({"a.txt": b"a"})
        spec = transfer_spec(payload)
        spec["publisher_sha256"] = "f" * 64
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ckdb.TransferError, "checksum"):
                ckdb.transfer_object(spec, "https://official.example/x", Path(temp) / "x.partial", Path(temp) / "x.zip", lambda _r: FakeResponse(payload))

    def test_09_archive_type_magic_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.zip"
            path.write_bytes(b"not an archive")
            with self.assertRaisesRegex(ckdb.SafetyError, "magic"):
                ckdb.require_archive_kind(path, "zip")

    def test_10_archive_path_link_device_and_encryption_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.zip"
            make_zip(path, {"../escape.pcap": b"x"})
            with self.assertRaisesRegex(ckdb.SafetyError, "traversal"):
                ckdb.inspect_archive(path, "zip", 1000)
            tar_path = Path(temp) / "bad.tar"
            with tarfile.open(tar_path, "w") as archive:
                info = tarfile.TarInfo("link")
                info.type = tarfile.SYMTYPE
                info.linkname = "target"
                archive.addfile(info)
            with self.assertRaisesRegex(ckdb.SafetyError, "link"):
                ckdb.inspect_archive(tar_path, "tar", 1000)

    def test_11_archive_expansion_cap_is_enforced(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "big.zip"
            make_zip(path, {"normal.pcap": b"x" * 100})
            with self.assertRaisesRegex(ckdb.SafetyError, "expansion"):
                ckdb.inspect_archive(path, "zip", 99)

    def test_12_pnnl_inventory_precedes_packet_decode(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pnnl.tar"
            make_tar(path, {"electric/normal/a.pcap": b"e", "gas/baseline/b.pcap": b"g"})
            rows, verdict = ckdb.pnnl_boundary(path, "tar", 10000)
            self.assertEqual(verdict["packet_decode_count"], 0)
            self.assertEqual(len(rows), 2)

    def test_13_both_pnnl_normal_units_are_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pnnl.tar"
            make_tar(path, {"electric/normal/a.pcap": b"e"})
            with self.assertRaisesRegex(ckdb.BoundaryFailure, "both PNNL"):
                ckdb.pnnl_boundary(path, "tar", 10000)

    def test_14_attack_fault_and_ambiguous_never_enter_pnnl_normal_allowlist(self):
        cases = {
            "electric/attack/a.pcap": "attack",
            "gas/system_fault/a.pcap": "system_fault",
            "misc/normal/a.pcap": "ambiguous",
        }
        for name, expected in cases.items():
            self.assertEqual(ckdb.classify_pnnl_member(name), expected)
            self.assertNotIn(expected, {"electric_normal", "gas_normal"})

    def test_15_pnnl_ambiguity_isolated_without_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "pnnl.tar"
            make_tar(path, {
                "electric/normal/a.pcap": b"e",
                "gas/normal/b.pcap": b"g",
                "misc/normal/c.pcap": b"x",
            })
            with self.assertRaisesRegex(ckdb.BoundaryFailure, "ambiguous"):
                ckdb.pnnl_boundary(path, "tar", 10000)

    def test_16_cic_attack_tree_cannot_enter_allowlist(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cic.zip"
            make_zip(path, {"benign/normal.pcap": b"b", "attack/a.pcap": b"a"})
            appendix = base_appendix()["objects"][1]
            with self.assertRaisesRegex(ckdb.BoundaryFailure, "attack/log"):
                ckdb.cic_boundary(path, "zip", 10000, appendix)

    def test_17_cic_mixed_whole_archive_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "cic.zip"
            make_zip(path, {"benign/normal.pcap": b"b", "other/unknown.pcap": b"x"})
            appendix = base_appendix()["objects"][1]
            with self.assertRaisesRegex(ckdb.BoundaryFailure, "mixed whole"):
                ckdb.cic_boundary(path, "zip", 10000, appendix)

    def test_18_uncloseable_p0b_yields_named_two_domain_termination(self):
        value = base_appendix()
        cic = value["objects"][1]
        cic["benign_member_paths"] = []
        cic["benign_subtree"] = ""
        with self.assertRaises(ckdb.BoundaryFailure) as caught:
            validate_appendix(value)
        verdict = ckdb.industrial_failure_verdict(caught.exception.reason_code)
        self.assertEqual(verdict["combined_industrial_maximum"], 2)
        self.assertFalse(verdict["replacement_corpus_allowed"])

    def test_19_post_transfer_cic_failure_has_same_no_replacement_consequence(self):
        verdict = ckdb.industrial_failure_verdict("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE")
        self.assertEqual(verdict["cic_industrial_domains"], 0)
        self.assertTrue(verdict["route_terminated"])
        self.assertFalse(verdict["third_corpus_search_allowed"])

    def test_20_exact_five_device_holdout_and_hash_order(self):
        selected = ckdb.deterministic_holdout(["UNSW_DEVICE_%03d" % value for value in range(1, 28)])
        self.assertEqual(tuple(item[0] for item in selected), ckdb.HOLDOUT_IDS)
        self.assertEqual(tuple(item[1] for item in selected), ckdb.HOLDOUT_HASHES)

    def test_21_holdout_excluded_from_fit_scale_roles(self):
        fit = ckdb.summarize_packet_records([packet(1, 0, source="FIT_A")])[0]
        holdout = ckdb.summarize_packet_records([packet(1, 0, source="UNSW_DEVICE_001", role="EXTERNAL_BENIGN_REPORT_HOLDOUT")])[0]
        _regions, verdict = ckdb.aggregate_census([fit, holdout])
        self.assertEqual(verdict["i1_fit_sessions"], 1)
        self.assertEqual(verdict["i1_fit_tokens"], 1)

    def test_22_per_device_holdout_warning_is_mandatory(self):
        plan = ckdb.verify_plan(CONTRACT, PLAN)
        self.assertEqual(plan["holdout"]["aggregate_warning"], ckdb.HOLDOUT_WARNING)
        self.assertEqual(len(plan["holdout"]["source_unit_ids"]), 5)

    def test_23_industrial_option_two_and_claim_cap_are_literal(self):
        policy = ckdb.verify_plan(CONTRACT, PLAN)["industrial_policy"]
        self.assertEqual(policy["option"], "USE_ALL_THREE_INDUSTRIAL_DOMAINS_FOR_FIT_SELECT")
        self.assertEqual(policy["claim_cap"], "FORBID_BROAD_UNSEEN_INDUSTRIAL_DOMAIN_CLAIM_BEFORE_FINAL")

    def test_24_fine_units_cannot_inflate_coarse_domain_count(self):
        verdict = ckdb.industrial_failure_verdict("CIC_BENIGN_BOUNDARY_FAILURE_NO_USE")
        self.assertEqual(verdict["combined_industrial_maximum"], 2)
        self.assertEqual(verdict["minimum_required"], 3)

    def test_25_causal_session_member_reset_and_timestamp_regression(self):
        rows = ckdb.summarize_packet_records([
            packet(1, 2000000), packet(2, 1000000),
            packet(1, 500000, member="b.pcap"),
        ])
        first = [row for row in rows if row["pcap_member"] == "a.pcap"][0]
        second = [row for row in rows if row["pcap_member"] == "b.pcap"][0]
        self.assertFalse(first["encodable"])
        self.assertEqual(first["i1_token_count"], 1)
        self.assertTrue(second["encodable"])
        self.assertEqual(second["i1_token_count"], 1)

    def test_26_exact_i1_token_buckets_and_count_once(self):
        event = packet(1, 0, frame_len=64)
        self.assertEqual(ckdb.token_fields(event, None), (0, 1, 6, 0))
        reverse = packet(2, 1024, src="10.0.0.2", dst="10.0.0.1", src_port=80, dst_port=1000, frame_len=2048)
        self.assertEqual(ckdb.token_fields(reverse, 0), (1, 31, 6, 12))
        row = ckdb.summarize_packet_records([event, reverse])[0]
        self.assertEqual(row["i1_token_count"], 2)

    def test_27_i1_scale_excludes_holdout_prohibited_and_ambiguous(self):
        rows = []
        for role in (
            "external_benign_fit_candidate",
            "EXTERNAL_BENIGN_REPORT_HOLDOUT",
            "PROHIBITED_ATTACK_MATERIAL",
            "EXCLUDED_UNRESOLVED_IDENTITY",
        ):
            rows.append(ckdb.summarize_packet_records([packet(1, 0, source=role, member=role + ".pcap", role=role)])[0])
        _regions, verdict = ckdb.aggregate_census(rows)
        self.assertEqual(verdict["i1_fit_sessions"], 1)
        self.assertEqual(verdict["labels_read"], 0)

    def test_28_descriptor_edges_and_low_iat_state(self):
        self.assertEqual(ckdb._packet_count_bin(2), "1-2")
        self.assertEqual(ckdb._packet_count_bin(3), "3-8")
        self.assertEqual(ckdb._packet_count_bin(257), "257-1024")
        self.assertEqual(ckdb._duration_bin(300), "300-<1800")
        self.assertEqual(ckdb._polling_bin(0.75), ">=0.75")
        self.assertEqual(ckdb._burstiness([1.0, 1.0])[1], "INSUFFICIENT_IAT")

    def test_29_exact_six_regions_and_quality_thresholds(self):
        row = {
            "packet_count": 300,
            "duration_seconds": 301.0,
            "directionality": "BIDIRECTIONAL",
            "transport": "TCP",
            "polling_proxy": 0.8,
            "burstiness_bin": ">1/3",
        }
        self.assertEqual(ckdb.coverage_regions(row), {
            "R2_packet_dense", "R3_long_lived", "R4_bidirectional_tcp",
            "R5_polling_like", "R6_bursty",
        })
        self.assertEqual((ckdb.QUALITY_MIN_SESSIONS, ckdb.QUALITY_MIN_PACKETS, ckdb.QUALITY_MIN_SOURCE_UNITS), (100, 10000, 2))

    def test_30_coverage_gap_caps_claim_without_route_kill_or_tuning(self):
        row = ckdb.summarize_packet_records([packet(1, 0)])[0]
        regions, verdict = ckdb.aggregate_census([row])
        self.assertEqual(verdict["coverage_status"], "COVERAGE_GAP_NAMED")
        self.assertFalse(verdict["coverage_gap_route_kill"])
        self.assertFalse(verdict["coverage_gap_adds_data"])
        self.assertFalse(verdict["coverage_gap_tunes_window_or_threshold"])
        self.assertEqual(len(regions), 6)

    def test_31_storage_formula_inode_gate_and_fresh_measurement(self):
        required = ckdb.required_free_bytes(100, 1000)
        self.assertGreater(required, 20 * 1024 * 1024 * 1024)
        passed = ckdb.storage_gate(100, 1000, required, 0.1, "2026-08-18T00:00:00Z")
        self.assertEqual(passed["status"], "P0_D_PASS")
        blocked = ckdb.storage_gate(100, 1000, required - 1, 0.1, "2026-08-18T00:00:00Z")
        self.assertEqual(blocked["status"], "BLOCKED_STORAGE_NO_TRANSFER")
        with self.assertRaisesRegex(ckdb.ContractError, "fresh"):
            ckdb.storage_gate(100, 1000, required, 0.1, "HISTORICAL")

    def test_32_engineering_failure_emits_no_scientific_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ckdb.RESULT_NAMES:
                (root / name).write_text("bad", encoding="utf-8")
            ckdb.record_engineering_failure(root, RuntimeError("boom"))
            self.assertTrue((root / "engineering_failure.json").is_file())
            self.assertTrue(all(not (root / name).exists() for name in ckdb.RESULT_NAMES))
            value = json.loads((root / "engineering_failure.json").read_text(encoding="utf-8"))
            self.assertFalse(value["scientific_verdict_emitted"])

    def test_33_python39_runtime_hash_and_deterministic_package_roundtrip(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        ast.parse(source, filename=str(MODULE_PATH), feature_version=(3, 9))
        self.assertNotIn("write_text(text, encoding=\"utf-8\", newline=", source)
        subprocess.run([sys.executable, "-m", "py_compile", str(MODULE_PATH)], check=True)
        help_result = subprocess.run([sys.executable, str(MODULE_PATH), "--help"], check=True, capture_output=True, text=True)
        self.assertIn("offline", help_result.stdout.lower())
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "result"
            root.mkdir()
            (root / "a.txt").write_bytes(b"alpha")
            ckdb.write_sha256sums(root)
            one, two = Path(temp) / "one.tar.gz", Path(temp) / "two.tar.gz"
            ckdb.deterministic_package(root, one)
            ckdb.deterministic_package(root, two)
            self.assertEqual(ckdb.sha256_file(one), ckdb.sha256_file(two))
            with tarfile.open(one, "r:gz") as archive:
                self.assertEqual(sorted(archive.getnames()), ["SHA256SUMS", "a.txt"])


if __name__ == "__main__":
    unittest.main()
