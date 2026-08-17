from __future__ import annotations

import argparse
import ast
import csv
import importlib.util
import io
import json
import stat
import tempfile
import unittest
import zipfile
from pathlib import Path
from typing import Any, Dict, Mapping


MODULE_PATH = Path(__file__).with_name("issue27ckdb_d0_p1_external_metadata_audit_v1.py")
SPEC = importlib.util.spec_from_file_location("ckdb_d0_p1_target", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
ckdb = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ckdb)

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "runs/mainline_docs/ckdb_d0_p1_external_metadata_audit_preregistered_20260817.md"
PLAN = ROOT / "runs/mainline_docs/ckdb_d0_p1_retrieval_plan_20260817.json"


def device_summary() -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=[
            "Device Name",
            "Device MAC Address",
            "First Seen",
            "Last Seen",
            "Number of Packets",
            "Number of Flows",
        ],
    )
    writer.writeheader()
    for index in range(27):
        writer.writerow(
            {
                "Device Name": "Device%02d" % index,
                "Device MAC Address": "00:00:00:00:00:%02d" % index,
                "First Seen": "2016-09-01",
                "Last Seen": "2017-04-01",
                "Number of Packets": 1000 + index,
                "Number of Flows": 100 + index,
            }
        )
    return stream.getvalue().encode("utf-8")


def cic_page() -> bytes:
    return b"""<!doctype html><html><body>
    CIC Modbus dataset 2023. The CIC Modbus Dataset contains traffic from a
    simulated substation network. It has an attack dataset and a benign dataset.
    The benign dataset consists of normal network traffic.
    IED1A IED4C IED1B Secure SCADA HMI Normal SCADA HMI Central Agent.
    You may redistribute, republish and mirror with citation.
    </body></html>"""


def flow_zip(member_count: int = 27, extra_field: str = "") -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        fields = ["ipProto", "srcNumPackets", "dstNumPackets", "flowDuration", "flowSeqNum"]
        if extra_field:
            fields.append(extra_field)
        for index in range(member_count):
            stream = io.StringIO(newline="")
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            row: Dict[str, Any] = {
                "ipProto": 6,
                "srcNumPackets": 200,
                "dstNumPackets": 100,
                "flowDuration": 400,
                "flowSeqNum": index,
            }
            if extra_field:
                row[extra_field] = "deadbeef"
            writer.writerow(row)
            archive.writestr("flows/device_%02d.csv" % index, stream.getvalue())
    return buffer.getvalue()


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
            "candidate_id": spec["candidate_id"],
            "object_id": object_id,
            "tier": spec["tier"],
            "request_url": spec["url"],
            "final_url": spec["url"],
            "retrieval_utc": "2026-08-17T00:00:00Z",
            "http_status": 200,
            "content_type": "fixture",
            "published_size_text": spec["published_size_text"],
            "local_bytes": len(payload),
            "sha256": ckdb.sha256_bytes(payload),
            "expected_kind": spec["expected_kind"],
            "safety_status": "PASS",
            "reason_code": "OK",
        }


def tier_a_payloads() -> Dict[str, bytes]:
    return {
        "unsw_official_page": b"<!doctype html><html>UNSW IoT traffic data 10.5061/dryad.w0vt4b94b 27 devices</html>",
        "unsw_dryad_inventory": b"<!doctype html><html>flows.zip pcaps.zip README.md device_pcap_summary.csv Content on this site is licensed for reuse.</html>",
        "unsw_device_summary": device_summary(),
        "unsw_protocol_summary": b"Protocol,Number of Devices,Number of Flows\nTLS,27,100\n",
        "unsw_readme": b"Traces include interactions and autonomous background activities. No ground-truth annotations are provided.\n",
        "unsw_descriptor_landing": b"<!doctype html><html>IEEE descriptor 10.1109/IEEEDATA.2025.3602010</html>",
        "cic_official_page": cic_page(),
        "cic_download_inventory": b"<!doctype html><html>First Name Email download form</html>",
    }


def fixture_devices() -> list:
    rows = []
    for candidate, clusters in (("UNSW_IOTRAFFIC", 3), ("CIC_MODBUS_2023", 1)):
        for index in range(clusters):
            rows.append(
                {
                    "candidate_id": candidate,
                    "cluster_id": "%s_%d" % (candidate, index),
                }
            )
    return rows


class CKDBD0P1ContractTests(unittest.TestCase):
    def test_01_frozen_contract_and_plan_hashes(self):
        self.assertEqual(ckdb.sha256_file(CONTRACT), ckdb.CONTRACT_SHA256)
        self.assertEqual(ckdb.sha256_file(PLAN), ckdb.PLAN_SHA256)
        plan = ckdb.verify_identity(CONTRACT, PLAN)
        self.assertEqual(tuple(plan["candidate_order"]), ckdb.CANDIDATES)

    def test_02_tier_caps_are_literal(self):
        self.assertEqual(ckdb.TIER_A_CAP, 20 * 1024 * 1024)
        self.assertEqual(ckdb.TIER_B_CAP, 128 * 1024 * 1024)
        with self.assertRaisesRegex(ckdb.SafetyError, "byte cap"):
            ckdb.enforce_candidate_tier_cap(
                [{"candidate_id": "UNSW_IOTRAFFIC", "tier": "A", "local_bytes": ckdb.TIER_A_CAP + 1}],
                "UNSW_IOTRAFFIC",
                "A",
            )

    def test_03_pcap_magic_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.csv"
            path.write_bytes(b"\xd4\xc3\xb2\xa1" + b"0" * 20)
            with self.assertRaisesRegex(ckdb.SafetyError, "PCAP"):
                ckdb.validate_object_kind(path, "csv")

    def test_04_html_masquerading_as_data_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.csv"
            path.write_bytes(b"<!doctype html><html>login</html>")
            with self.assertRaisesRegex(ckdb.SafetyError, "HTML"):
                ckdb.validate_object_kind(path, "csv")

    def test_05_archive_traversal_link_nested_and_encryption_rejected(self):
        for name in ("../x.csv", "/x.csv", "C:/x.csv", "x.zip", "x.pcap", "run.exe"):
            with self.assertRaises(ckdb.SafetyError, msg=name):
                ckdb._safe_member_name(name)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "x.zip"
            info = zipfile.ZipInfo("flows/x.csv")
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr(info, "target")
            with self.assertRaisesRegex(ckdb.SafetyError, "link"):
                ckdb.inspect_flow_zip(path)

    def test_06_atomic_write_and_exact_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ckdb.atomic_json(root / "a.json", {"b": 2, "a": 1})
            self.assertEqual(json.loads((root / "a.json").read_text()), {"a": 1, "b": 2})
            ckdb.write_csv(root / "x.csv", ("a", "reason_code"), [{"a": 1, "reason_code": "OK"}])
            with (root / "x.csv").open(encoding="utf-8", newline="") as handle:
                self.assertEqual(list(csv.DictReader(handle))[0]["reason_code"], "OK")
            with self.assertRaises(ckdb.ContractError):
                ckdb.write_csv(root / "bad.csv", ("a", "reason_code"), [{"a": 1}])

    def test_07_resume_requires_same_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "x.csv"
            part = destination.with_name("." + destination.name + ".part")
            meta = destination.with_name("." + destination.name + ".part.json")
            part.write_bytes(b"partial")
            ckdb.atomic_json(meta, {"url": "wrong"})
            spec = {
                "object_id": "x",
                "url": "https://example.com/x",
                "expected_kind": "csv",
                "max_bytes": 100,
                "allowed_final_hosts": ["example.com"],
                "candidate_id": "UNSW_IOTRAFFIC",
                "tier": "A",
                "published_size_text": "1 B",
            }
            with self.assertRaisesRegex(ckdb.RetrievalError, "identity mismatch"):
                ckdb.Fetcher(opener=lambda *args, **kwargs: None).fetch(spec, destination)

    def test_08_sha_manifest_roundtrip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "x.txt").write_text("x", encoding="utf-8")
            (root / "downloads").mkdir()
            (root / "downloads" / "object.bin").write_bytes(b"download")
            ckdb.write_sha256sums(root)
            entries = {}
            for line in (root / "SHA256SUMS").read_text().splitlines():
                digest, name = line.split("  ", 1)
                entries[name] = digest
            self.assertEqual(entries["x.txt"], ckdb.sha256_file(root / "x.txt"))
            self.assertEqual(
                entries["downloads/object.bin"], ckdb.sha256_file(root / "downloads" / "object.bin")
            )

    def test_09_candidate_count_is_exactly_two(self):
        self.assertEqual(ckdb.CANDIDATES, ("UNSW_IOTRAFFIC", "CIC_MODBUS_2023"))
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        self.assertEqual(set(item["candidate_id"] for item in plan["objects"]), set(ckdb.CANDIDATES))

    def test_10_equal_fixed_schemas_and_explicit_unknowns(self):
        coverage, horizon, _ = ckdb.build_coverage_and_horizon(fixture_devices(), None)
        self.assertEqual(set(coverage[0]), set(coverage[1]))
        self.assertEqual(set(horizon[0]), set(horizon[1]))
        self.assertEqual(horizon[1]["horizon_status"], "PENDING_NO_SMALL_FLOW_METADATA")
        self.assertNotIn("", horizon[1].values())

    def test_11_final_and_report_paths_are_absent(self):
        source = MODULE_PATH.read_text(encoding="utf-8").lower()
        plan = PLAN.read_text(encoding="utf-8").lower()
        for marker in ckdb.FINAL_MARKERS:
            self.assertNotIn(marker, plan)
        for prohibited in ("torch", "sklearn", "pandas", "ckda_d1", "cooler-motor"):
            self.assertNotIn(prohibited, plan)
        with self.assertRaises(ckdb.ContractError):
            ckdb.fail_if_prohibited_text("seed-37", "test")
        self.assertIn("training_embedding_threshold_operations", source)

    def test_12_no_model_label_training_or_pcap_import(self):
        tree = ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertTrue({"torch", "sklearn", "pandas", "scapy", "dpkt"}.isdisjoint(imported))

    def test_13_tier_b_is_blocked_after_tier_a_fail(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        specs = ckdb.eligible_tier_b_specs(
            plan, {"UNSW_IOTRAFFIC": False, "CIC_MODBUS_2023": True}
        )
        self.assertEqual(specs, [])

    def test_14_overlap_cannot_overclaim_known_disjoint(self):
        rows = ckdb.build_lineage_rows()
        self.assertNotIn("KNOWN_DISJOINT", {row["collection_relation"] for row in rows})
        e3 = [row for row in rows if row["route_id"] == "E3_NETFOUND_CONTROL"]
        self.assertTrue(all(row["collection_relation"] == "POSSIBLE_OVERLAP" for row in e3))

    def test_15_repeated_roles_do_not_inflate_cluster_count(self):
        rows = [
            {"candidate_id": "CIC_MODBUS_2023", "cluster_id": "one"},
            {"candidate_id": "CIC_MODBUS_2023", "cluster_id": "one"},
            {"candidate_id": "CIC_MODBUS_2023", "cluster_id": "one"},
        ]
        self.assertEqual(ckdb.cluster_count(rows, "CIC_MODBUS_2023"), 1)

    def test_16_long_tcp_descriptor_is_literal_and_global(self):
        self.assertEqual(ckdb.LONG_TCP_PACKET_CUT, 256)
        self.assertEqual(ckdb.LONG_TCP_DURATION_CUT, 300.0)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "flows.zip"
            path.write_bytes(flow_zip())
            summary, members = ckdb.analyze_unsw_flow_zip(path)
            self.assertEqual(summary["flow_rows"], 27)
            self.assertEqual(summary["long_tcp_flow_count"], 27)
            self.assertEqual(len(members), 27)

    def test_17_per_packet_or_payload_disguise_fails(self):
        with self.assertRaisesRegex(ckdb.SafetyError, "payload/per-packet"):
            ckdb.validate_flow_header(
                ["ipProto", "srcNumPackets", "dstNumPackets", "flowDuration", "flowSeqNum", "rawPayload"]
            )
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "flows.zip"
            path.write_bytes(flow_zip(extra_field="packetNumber"))
            with self.assertRaisesRegex(ckdb.SafetyError, "payload/per-packet"):
                ckdb.analyze_unsw_flow_zip(path)

    def test_18_verdict_never_authorizes_large_download(self):
        _, _, verdict = ckdb.build_coverage_and_horizon(fixture_devices(), None)
        self.assertEqual(verdict["status"], "CKDB_D0_P1_PENDING_METADATA")
        self.assertEqual(verdict["missing_evidence"], "SECOND_INDUSTRIAL_PROCESS_CORPUS")
        self.assertFalse(verdict["large_download_authorized"])

    def test_19_python39_parse_and_runtime_atomic_api(self):
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"), feature_version=(3, 9))
        self.assertNotIn("write_text(", MODULE_PATH.read_text(encoding="utf-8"))

    def test_20_tier_a_only_end_to_end_is_terminal_and_hashed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"
            fetcher = FakeFetcher(tier_a_payloads())
            args = argparse.Namespace(contract=CONTRACT, plan=PLAN, output=output, tier_a_only=True)
            ckdb.execute(args, fetcher=fetcher)
            self.assertEqual(len(fetcher.calls), 8)
            self.assertNotIn("unsw_flows", fetcher.calls)
            verdict = json.loads((output / "ckdb_d0_p1_verdict.json").read_text())
            self.assertEqual(verdict["status"], "CKDB_D0_P1_PENDING_METADATA")
            self.assertEqual(verdict["industrial_post_cluster_domains"], 1)
            self.assertFalse(verdict["large_download_authorized"])
            self.assertTrue((output / "SHA256SUMS").is_file())
            with (output / "ckdb_d0_p1_device_domain_inventory.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                inventory = list(csv.DictReader(handle))
            self.assertEqual(len(inventory), 33)
            self.assertFalse(any("00:00:00" in json.dumps(row) for row in inventory))

    def test_21_engineering_failure_has_no_scientific_verdict(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "result"
            payloads = tier_a_payloads()
            payloads["unsw_official_page"] = b"not html"
            fetcher = FakeFetcher(payloads)
            args = argparse.Namespace(contract=CONTRACT, plan=PLAN, output=output, tier_a_only=True)
            with self.assertRaises(ckdb.SafetyError):
                ckdb.execute(args, fetcher=fetcher)
            self.assertFalse((output / "ckdb_d0_p1_verdict.json").exists())
            failure = json.loads((output / "engineering_failure.json").read_text())
            self.assertEqual(failure["scientific_verdict"], "NOT_EMITTED")

    def test_22_rejected_object_is_physically_quarantined(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "downloads" / "UNSW_IOTRAFFIC" / "unsw_flows.zip"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"bad-flow-object")
            quarantined = ckdb.quarantine_download(path, "payload/per-packet fields detected")
            self.assertFalse(path.exists())
            self.assertTrue(quarantined.is_file())
            audit = json.loads(
                (quarantined.parent / "unsw_flows.zip.rejected.json").read_text(encoding="utf-8")
            )
            self.assertEqual(audit["status"], "QUARANTINED_SAFETY_FAILURE")

    def test_23_later_allowlist_excludes_current_tier_b(self):
        plan = json.loads(PLAN.read_text(encoding="utf-8"))
        rows = ckdb.build_allowlist(plan)
        self.assertEqual({row["object_id"] for row in rows}, {"unsw_pcaps", "cic_benign_pcaps"})
        self.assertNotIn("unsw_flows", {row["object_id"] for row in rows})
        self.assertTrue(all(row["authorization_status"].endswith("NOT_EXECUTABLE") for row in rows))


if __name__ == "__main__":
    unittest.main(verbosity=2)
