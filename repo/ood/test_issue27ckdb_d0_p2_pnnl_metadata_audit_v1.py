from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping


MODULE_PATH = Path(__file__).with_name("issue27ckdb_d0_p2_pnnl_metadata_audit_v1.py")
SPEC = importlib.util.spec_from_file_location("ckdb_d0_p2_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ckdb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckdb)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "runs/mainline_docs/ckdb_d0_p2_second_industrial_corpus_amendment_preregistered_20260818.md"
PLAN = ROOT / "runs/mainline_docs/ckdb_d0_p2_retrieval_plan_20260818.json"


def official_page() -> bytes:
    return b"""<!doctype html><html><body>
    Pacific Northwest National Laboratory PNNL Electricity and Gas IDS
    DOI 10.25584/PNNLDH/1838670. High-fidelity hardware in the loop
    experimentation on simulated models of representative electric and
    natural gas distribution systems. Multiple networks and separate network
    control enclaves were used. Normal traffic establishes baseline operation.
    Electric devices include SAGE RTU, SEL 451, and GE D30 using DNP3.
    Gas devices include ROC 800, FloBoss, and ControlWave using Modbus.
    System-fault scenarios and attack scenarios are separate classes.
    </body></html>"""


def tier_a_payloads() -> Dict[str, bytes]:
    return {
        "pnnl_datahub_page": official_page(),
        "pnnl_doi_landing": b"<!doctype html><html>PNNL Electricity and Gas IDS 10.25584/PNNLDH/1838670</html>",
        "pnnl_osti_page": b"<!doctype html><html>PNNL publication 1838670 electricity gas 2022</html>",
        "pnnl_policy": b"<!doctype html><html>PNNL DataHub research data policy and terms of use.</html>",
        "pnnl_datacite_json": json.dumps({
            "data": {"id": "10.25584/PNNLDH/1838670", "attributes": {"publisher": "PNNL"}}
        }).encode("utf-8"),
        "pnnl_osti_json": json.dumps({
            "osti_id": "1838670", "publication_date": "2022-01-01", "site": "PNNL"
        }).encode("utf-8"),
    }


class FakeFetcher:
    def __init__(self, payloads: Mapping[str, bytes]) -> None:
        self.payloads = dict(payloads)
        self.calls = []

    def fetch(self, spec: Mapping[str, Any], destination: Path) -> Dict[str, Any]:
        object_id = str(spec["object_id"])
        self.calls.append(object_id)
        payload = self.payloads[object_id]
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        ckdb.validate_object_kind(destination, str(spec["expected_kind"]))
        return {
            "candidate_id": ckdb.CANDIDATE,
            "object_id": object_id,
            "tier": "A",
            "request_url": spec["url"],
            "final_url": spec["url"],
            "retrieval_utc": "2026-08-18T00:00:00Z",
            "http_status": 200,
            "content_type": "fixture",
            "published_size_text": spec["published_size_text"],
            "local_bytes": len(payload),
            "sha256": ckdb.sha256_bytes(payload),
            "expected_kind": spec["expected_kind"],
            "safety_status": "PASS",
            "reason_code": "OK",
        }


class FakeResponse:
    def __init__(self, payload: bytes, url: str, status: int = 200) -> None:
        self.stream = io.BytesIO(payload)
        self.url = url
        self.status = status
        self.headers = {"Content-Type": "text/html"}

    def read(self, size: int = -1) -> bytes:
        return self.stream.read(size)

    def geturl(self) -> str:
        return self.url

    def getcode(self) -> int:
        return self.status


def eligible_identity() -> list:
    return [{
        "candidate_id": ckdb.CANDIDATE,
        "identity_status": "METADATA_ELIGIBLE",
        "reason_code": "OK",
    }]


class CKDBD0P2ContractTests(unittest.TestCase):
    def test_01_frozen_contract_and_plan_hashes(self):
        self.assertEqual(ckdb.sha256_file(CONTRACT), ckdb.CONTRACT_SHA256)
        self.assertEqual(ckdb.sha256_file(PLAN), ckdb.PLAN_SHA256)
        plan = ckdb.verify_identity(CONTRACT, PLAN)
        self.assertEqual(plan["candidate_order"], [ckdb.CANDIDATE])

    def test_02_single_candidate_and_exact_doi(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual(plan["candidate_order"], ["PNNL_ELECTRICITY_AND_GAS_IDS"])
        urls = "\n".join(item["url"] for item in plan["objects"])
        self.assertIn("10.25584/PNNLDH/1838670", urls)
        self.assertNotIn("UNSW", urls)
        self.assertNotIn("CICModbus", urls)

    def test_03_metadata_caps_are_literal(self):
        plan = ckdb.verify_identity(CONTRACT, PLAN)
        self.assertEqual(ckdb.TIER_A_TOTAL_CAP, 20 * 1024 * 1024)
        self.assertLessEqual(sum(int(item["max_bytes"]) for item in plan["objects"]), ckdb.TIER_A_TOTAL_CAP)
        self.assertTrue(all(int(item["max_bytes"]) <= ckdb.PER_OBJECT_CAP for item in plan["objects"]))

    def test_04_future_tar_is_not_executable(self):
        plan = ckdb.verify_identity(CONTRACT, PLAN)
        executable_ids = {item["object_id"] for item in plan["objects"]}
        future = plan["future_large_objects"][0]
        self.assertEqual(future["object_id"], "pnnl_opaque_tar")
        self.assertNotIn(future["object_id"], executable_ids)
        self.assertEqual(future["authorization_status"], "NOT_EXECUTABLE_REQUIRES_NEW_USER_AUTHORIZATION")

    def test_05_pcap_and_archive_magic_are_rejected(self):
        for prefix, message in ((b"\xd4\xc3\xb2\xa1", "PCAP"), (b"PK\x03\x04", "archive"), (b"\x1f\x8b", "archive")):
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp) / "x.html"
                path.write_bytes(prefix + b"0" * 32)
                with self.assertRaisesRegex(ckdb.SafetyError, message):
                    ckdb.validate_object_kind(path, "html")

    def test_06_login_and_html_masquerade_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            login = root / "login.html"
            login.write_bytes(b"<!doctype html><html>Authentication required</html>")
            with self.assertRaisesRegex(ckdb.SafetyError, "login"):
                ckdb.validate_object_kind(login, "html")
            disguised = root / "x.json"
            disguised.write_bytes(b"<!doctype html><html>error</html>")
            with self.assertRaisesRegex(ckdb.SafetyError, "masquerading"):
                ckdb.validate_object_kind(disguised, "json")

    def test_07_redirect_host_is_allowlisted(self):
        spec = {
            "url": "https://data.pnnl.gov/x", "allowed_final_hosts": ["data.pnnl.gov"],
            "max_bytes": 4096, "expected_kind": "html", "object_id": "x",
            "published_size_text": "unknown",
        }
        with tempfile.TemporaryDirectory() as temp:
            bad = ckdb.Fetcher(opener=lambda *args, **kwargs: FakeResponse(official_page(), "https://evil.example/x"))
            with self.assertRaisesRegex(ckdb.RetrievalError, "allowlisted"):
                bad.fetch(spec, Path(temp) / "x.html")

    def test_08_streaming_byte_cap_is_enforced(self):
        spec = {
            "url": "https://data.pnnl.gov/x", "allowed_final_hosts": ["data.pnnl.gov"],
            "max_bytes": 10, "expected_kind": "html", "object_id": "x",
            "published_size_text": "unknown",
        }
        with tempfile.TemporaryDirectory() as temp:
            fetcher = ckdb.Fetcher(opener=lambda *args, **kwargs: FakeResponse(official_page(), spec["url"]))
            with self.assertRaisesRegex(ckdb.SafetyError, "byte cap"):
                fetcher.fetch(spec, Path(temp) / "x.html")

    def test_09_atomic_write_and_exact_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ckdb.atomic_json(root / "a.json", {"b": 2, "a": 1})
            self.assertEqual(json.loads((root / "a.json").read_text()), {"a": 1, "b": 2})
            ckdb.write_csv(root / "x.csv", ("a", "reason_code"), [{"a": 1, "reason_code": "OK"}])
            with (root / "x.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["reason_code"], "OK")
            with self.assertRaises(ckdb.ContractError):
                ckdb.write_csv(root / "bad.csv", ("a", "reason_code"), [{"a": 1}])

    def test_10_sha_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ckdb.atomic_text(root / "a.txt", "x\n")
            ckdb.write_sha256sums(root)
            digest, name = (root / "SHA256SUMS").read_text().strip().split("  ")
            self.assertEqual(digest, ckdb.sha256_file(root / name))

    def test_11_all_four_conditions_are_required_for_two_domains(self):
        evidence = {"page": official_page().decode("utf-8")}
        rows = ckdb.evaluate_independence(evidence, "electric_normal.pcap gas_normal.pcap")
        self.assertEqual({row["status"] for row in rows}, {"TRUE"})
        self.assertEqual(ckdb.pnnl_domain_count(rows), 2)

    def test_12_unknown_condition_collapses_count_to_one(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        self.assertEqual(next(row["status"] for row in rows if row["condition_id"] == "C4"), "PENDING")
        self.assertEqual(ckdb.pnnl_domain_count(rows), 1)

    def test_13_device_role_day_rows_cannot_inflate_domains(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        devices = ckdb.build_device_rows(rows)
        self.assertEqual(len(devices), 2)
        self.assertEqual(sum(int(row["independent_domain_counted"]) for row in devices), 1)

    def test_14_normal_narrative_alone_is_pending(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        benign = ckdb.build_benign_rows(rows)[0]
        self.assertEqual(benign["benign_boundary"], "PENDING_ARCHIVE_INVENTORY")
        self.assertEqual(benign["eligibility_status"], "PENDING")
        self.assertFalse(benign["row_labels_required"])

    def test_15_system_fault_is_excluded_from_benign_scope(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        benign = ckdb.build_benign_rows(rows)[0]
        self.assertEqual(benign["system_fault_scope"], "EXCLUDED_ABNORMAL_PHYSICAL_STATE")

    def test_16_missing_flow_metadata_is_pending_and_descriptor_literal(self):
        plan = ckdb.verify_identity(CONTRACT, PLAN)
        row = ckdb.build_horizon_rows(plan)[0]
        self.assertEqual(row["small_flow_metadata_status"], "PENDING_NO_SMALL_FLOW_METADATA")
        self.assertEqual(row["long_tcp_definition"], "bidirectional TCP AND (packet_count > 256 OR duration_seconds >= 300)")
        self.assertEqual(row["long_tcp_flow_count"], "PENDING")

    def test_17_protocol_is_descriptive_not_domain_identity(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        coverage = ckdb.build_coverage_rows(rows)
        self.assertEqual({row["protocol_family"] for row in coverage}, {"DNP3", "MODBUS"})
        self.assertTrue(all(row["protocol_is_domain_identity"] is False for row in coverage))

    def test_18_no_third_corpus_or_candidate_search_path(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        plan = PLAN.read_text(encoding="utf-8")
        self.assertNotIn("fallback_candidate", source + plan)
        self.assertNotIn("candidate_search", source + plan)
        self.assertEqual(json.loads(plan)["candidate_order"], [ckdb.CANDIDATE])

    def test_19_no_model_label_training_or_hpc_imports(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".")[0])
        self.assertFalse(imports & {"torch", "tensorflow", "sklearn", "pandas", "scapy", "dpkt"})

    def test_20_verdict_never_authorizes_download_training_hpc_or_final(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        verdict = ckdb.build_verdict(
            eligible_identity(), ckdb.build_benign_rows(rows), rows
        )
        for key in ("large_download_authorized", "training_authorized", "hpc_authorized"):
            self.assertFalse(verdict[key])
        for key in ("final_opened", "pcap_opened", "label_tables_opened", "model_or_embedding_opened"):
            self.assertEqual(verdict[key], 0)

    def test_21_python39_syntax(self):
        for path in (MODULE_PATH, Path(__file__)):
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path), feature_version=(3, 9))

    def test_22_runtime_api_regression_scan(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotRegex(source, r"\.write_text\([^)]*newline\s*=")
        self.assertNotIn("match problem_type", source)

    def test_23_engineering_failure_has_no_scientific_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"
            payloads = tier_a_payloads()
            del payloads["pnnl_osti_json"]
            args = argparse.Namespace(contract=CONTRACT, plan=PLAN, output=output)
            with self.assertRaises(KeyError):
                ckdb.execute(args, fetcher=FakeFetcher(payloads))
            self.assertTrue((output / "engineering_failure.json").is_file())
            self.assertFalse((output / "ckdb_d0_p2_verdict.json").exists())

    def test_24_full_offline_fixture_emits_required_outputs_and_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"
            args = argparse.Namespace(contract=CONTRACT, plan=PLAN, output=output)
            fetcher = FakeFetcher(tier_a_payloads())
            ckdb.execute(args, fetcher=fetcher)
            required = {
                "ckdb_d0_p2_retrieval_manifest.csv",
                "ckdb_d0_p2_corpus_identity_and_license.csv",
                "ckdb_d0_p2_lineage_overlap_matrix.csv",
                "ckdb_d0_p2_benign_boundary.csv",
                "ckdb_d0_p2_device_process_inventory.csv",
                "ckdb_d0_p2_independence_evidence.csv",
                "ckdb_d0_p2_domain_type_coverage.csv",
                "ckdb_d0_p2_horizon_and_scale.csv",
                "ckdb_d0_p2_later_download_allowlist.csv",
                "ckdb_d0_p2_verdict.json",
                "ckdb_d0_p2_result_report.md",
                "SHA256SUMS",
            }
            self.assertTrue(required <= {path.name for path in output.iterdir()})
            for line in (output / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                self.assertEqual(digest, ckdb.sha256_file(output / name))
            self.assertEqual(fetcher.calls, [item["object_id"] for item in ckdb.verify_identity(CONTRACT, PLAN)["objects"]])

    def test_25_pending_inventory_is_propagated_to_verdict(self):
        rows = ckdb.evaluate_independence({"page": official_page().decode("utf-8")})
        verdict = ckdb.build_verdict(eligible_identity(), ckdb.build_benign_rows(rows), rows)
        self.assertEqual(verdict["status"], "CKDB_D0_P2_PENDING_METADATA")
        self.assertIn("PENDING_ARCHIVE_INVENTORY", verdict["reason_codes"])
        self.assertTrue(verdict["post_download_pre_use_boundary_verification_required"])

    def test_26_all_true_conditions_only_make_download_eligible_not_authorized(self):
        rows = ckdb.evaluate_independence(
            {"page": official_page().decode("utf-8")},
            "electric_normal/capture.pcap gas_normal/capture.pcap",
        )
        benign = ckdb.build_benign_rows(rows)
        verdict = ckdb.build_verdict(eligible_identity(), benign, rows)
        self.assertEqual(verdict["status"], "CKDB_D0_P2_LARGE_DOWNLOAD_ELIGIBLE")
        self.assertEqual(verdict["combined_industrial_domains"], 3)
        self.assertFalse(verdict["large_download_authorized"])

    def test_27_proven_independence_failure_is_no_go(self):
        rows = ckdb.evaluate_independence(
            {"page": official_page().decode("utf-8")},
            "electric_normal.pcap gas_normal.pcap",
        )
        rows[1] = dict(rows[1], status="FALSE", reason_code="SHARED_FIELD_DEVICE_FLEET")
        verdict = ckdb.build_verdict(eligible_identity(), ckdb.build_benign_rows(rows), rows)
        self.assertEqual(verdict["status"], "CKDB_D0_P2_NO_IDENTIFIABLE_SECOND_INDUSTRIAL_CORPUS")

    def test_28_no_range_header_is_constructed(self):
        seen = {}
        def opener(request, **kwargs):
            seen["range"] = request.has_header("Range")
            return FakeResponse(official_page(), request.full_url)
        spec = {
            "url": "https://data.pnnl.gov/x", "allowed_final_hosts": ["data.pnnl.gov"],
            "max_bytes": 4096, "expected_kind": "html", "object_id": "x",
            "published_size_text": "unknown",
        }
        with tempfile.TemporaryDirectory() as temp:
            ckdb.Fetcher(opener=opener).fetch(spec, Path(temp) / "x.html")
        self.assertFalse(seen["range"])

    def test_29_output_root_must_be_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "existing.txt").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(ckdb.ContractError, "empty"):
                ckdb.ensure_empty_output_root(root)

    def test_30_parser_import_and_help_path_have_no_network(self):
        parser = ckdb.build_parser()
        args = parser.parse_args([
            "execute", "--contract", str(CONTRACT), "--plan", str(PLAN),
            "--output", "out",
        ])
        self.assertEqual(args.command, "execute")

    def test_31_policy_requires_explicit_research_use_evidence(self):
        evidence = {
            "pnnl_datahub_page": official_page().decode("utf-8"),
            "pnnl_datacite_json": '{"doi":"10.25584/PNNLDH/1838670","publisher":"PNNL","title":"Electricity and Gas"}',
            "pnnl_osti_page": "PNNL electricity gas",
            "pnnl_policy": "generic legal page without a use grant",
        }
        row = ckdb.build_identity_rows(evidence)[0]
        self.assertEqual(row["identity_status"], "PENDING")
        evidence["pnnl_policy"] = "Research use prohibited."
        row = ckdb.build_identity_rows(evidence)[0]
        self.assertEqual(row["identity_status"], "INELIGIBLE")


if __name__ == "__main__":
    unittest.main()
