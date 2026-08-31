#!/usr/bin/env python3
"""Contract tests for the authorized ZT-2 count-only real runner."""

from __future__ import annotations

import ast
import importlib.util
import math
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


r = load("zt2_real_tests", RUNNER)
e = load("zt2_engine_tests", r.ENGINE_PATH)


def raw(**updates):
    value = {field: "" for field in r.TSHARK_FIELDS}
    value.update({
        "frame.number": "1", "frame.time_epoch": "1.0", "frame.encap_type": "1",
        "frame.len": "64", "eth.src": "00:00:00:00:00:01", "eth.dst": "00:00:00:00:00:02",
        "eth.type": "0x0800", "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2",
        "ip.proto": "6", "tcp.srcport": "1000", "tcp.dstport": "2000",
    })
    value.update(updates)
    return value


def test_01_py39_ast_and_compile_surface():
    tree = ast.parse(RUNNER.read_text(encoding="utf-8"), feature_version=(3, 9))
    assert tree is not None


def test_02_no_learning_imports_or_payload_fields():
    source = RUNNER.read_text(encoding="utf-8")
    for forbidden in ["import torch", "import sklearn", "partial_fit", ".fit(", "tcp.payload", "data.data"]:
        assert forbidden not in source


def test_03_exact_denominators_and_resource_gate_are_literal():
    assert (r.EXPECTED_TARGETS, r.EXPECTED_MEMBERS, r.EXPECTED_OLD_MISSING, r.EXPECTED_OLD_FINITE) == (25467, 30, 11640, 13827)
    assert r.MIN_FREE_BYTES == 2 * 1024 * 1024 * 1024


def test_04_tshark_schema_contains_semantic_fields_only():
    required = {"frame.number", "frame.time_epoch", "frame.encap_type", "eth.src", "eth.dst", "eth.type", "ip.src", "ip.dst", "ipv6.nxt", "sctp.srcport", "icmp.type", "gre.key"}
    assert required.issubset(r.TSHARK_FIELDS)
    assert not any("payload" in value or "label" in value for value in r.TSHARK_FIELDS)


def test_05_ipv4_tcp_maps_h1():
    event = r.raw_to_event(e, raw(), "s", "m", 0, "u")
    route = e.classify_route(event, e.EndpointTokens())
    assert route.tier == "H1" and route.ports_present


def test_06_ipv4_icmp_maps_h2():
    value = raw(**{"ip.proto": "1", "tcp.srcport": "", "tcp.dstport": "", "icmp.type": "8", "icmp.code": "0"})
    event = r.raw_to_event(e, value, "s", "m", 0, "u")
    route = e.classify_route(event, e.EndpointTokens())
    assert route.tier == "H2" and route.protocol_class == (4, 1)


def test_07_ipv6_next_header_maps_h2():
    value = raw(**{"ip.src": "", "ip.dst": "", "ipv6.src": "::1", "ipv6.dst": "::2", "ip.proto": "", "ipv6.nxt": "58", "tcp.srcport": "", "tcp.dstport": ""})
    event = r.raw_to_event(e, value, "s", "m", 0, "u")
    assert e.classify_route(event, e.EndpointTokens()).tier == "H2"


def test_08_non_ip_endpoint_pair_maps_h3():
    value = raw(**{"ip.src": "", "ip.dst": "", "ip.proto": "", "tcp.srcport": "", "tcp.dstport": "", "eth.type": "0x88cc"})
    event = r.raw_to_event(e, value, "s", "m", 0, "u")
    assert e.classify_route(event, e.EndpointTokens()).tier == "H3"


def test_09_keyless_event_maps_h4():
    value = raw(**{"ip.src": "", "ip.dst": "", "ip.proto": "", "tcp.srcport": "", "tcp.dstport": "", "eth.src": "", "eth.dst": ""})
    event = r.raw_to_event(e, value, "s", "m", 0, "u")
    assert e.classify_route(event, e.EndpointTokens()).tier == "H4"


def test_10_sctp_ports_are_audit_only_h2():
    value = raw(**{"ip.proto": "132", "tcp.srcport": "", "tcp.dstport": "", "sctp.srcport": "5000", "sctp.dstport": "5001"})
    event = r.raw_to_event(e, value, "s", "m", 0, "u")
    route = e.classify_route(event, e.EndpointTokens())
    assert route.tier == "H2" and route.ports_present and "5000" not in str(route.base_key)


def test_11_frame_ordinal_mismatch_fails_closed():
    value = raw(**{"frame.number": "2"})
    try:
        r.raw_to_event(e, value, "s", "m", 0, "u")
    except r.ZT2Failure as exc:
        assert "ordinal drift" in str(exc)
    else:
        raise AssertionError("frame mismatch accepted")


def test_12_two_pass_streaming_conserves_targets():
    targets = [e.TargetSpec("u1", "s", "m", 1), e.TargetSpec("u2", "s", "m", 3)]
    def events():
        for index in range(4):
            yield e.Event("s", "m", index, float(index), target_uid={1: "u1", 3: "u2"}.get(index))
    last, count = r.discover_member(e, events(), {1, 3}, 3)
    rows, audit = r.replay_member(e, events(), targets, last, e.AccessAudit())
    assert count == 4 and len(rows) == 2 and all(row["semantic_finite"] for row in rows)
    assert audit["terminal_active_contexts"] == 0


def test_13_nonfinite_target_is_explicit_missing():
    targets = [e.TargetSpec("u", "s", "m", 0)]
    def events():
        yield e.Event("s", "m", 0, math.nan, target_uid="u")
    last, _ = r.discover_member(e, events(), {0}, 0)
    rows, _ = r.replay_member(e, events(), targets, last, e.AccessAudit())
    assert not rows[0]["semantic_finite"] and rows[0]["semantic_missing_reason"] == "NONFINITE_EVENT_TIMESTAMP"


def test_14_endpoint_remap_is_exact():
    assert r.endpoint_remap_audit(e) == {"status": "PASS", "bijective_endpoint_remap_invariant": True}


def test_15_checkpoint_identity_is_deterministic_and_sensitive():
    identity = {"member": "m"}
    first = r.checkpoint_identity(identity, [("u", 1)], {"t": 1}, "a")
    assert first == r.checkpoint_identity(identity, [("u", 1)], {"t": 1}, "a")
    assert first != r.checkpoint_identity(identity, [("u", 2)], {"t": 1}, "a")


def test_16_group_table_is_group_count_not_record_bootstrap():
    frame = pd.DataFrame({"device_family": ["a", "a", "b"], "semantic_finite": [True, False, True]})
    rows = r.group_table(frame, "device_family", "full")
    assert rows[0]["targets"] == 2 and rows[0]["semantic_finite_rate"] == 0.5
    assert rows[1]["semantic_finite_rate"] == 1.0


def test_17_context_table_reports_tier_and_bounds():
    frame = pd.DataFrame({
        "device_family": ["d", "d"], "semantic_finite": [True, True], "context_tier": ["H1", "H1"],
        "context_event_count": [1, 3], "context_surrogate_span_seconds": [0.0, 2.0],
    })
    row = r.context_table(frame, "device_family")[0]
    assert row["event_count_median"] == 2.0 and row["event_count_max"] == 3.0


def test_18_authorization_token_blocks_before_writes():
    with tempfile.TemporaryDirectory() as raw_dir:
        path = Path(raw_dir) / "out"
        try:
            r.execute(SimpleNamespace(authorization_token="NO", out_dir=path, tshark=Path("missing")))
        except r.ZT2Failure as exc:
            assert "not authorized" in str(exc)
        else:
            raise AssertionError("unauthorized execution accepted")
        assert not path.exists()


def test_19_required_output_categories_are_in_runner():
    source = RUNNER.read_text(encoding="utf-8")
    for name in [
        "zt2_semantic_status_by_target.csv.gz", "zt2_availability_by_device.csv",
        "zt2_context_size_distributions.csv", "zt2_endpoint_remap_invariance.json",
        "zt2_role_open_audit.json", "zt2_semantic_coverage_verdict.json", "SHA256SUMS",
    ]:
        assert name in source


def test_20_fail_closed_terminal_names_are_present():
    source = RUNNER.read_text(encoding="utf-8")
    for name in ["ZT_IDENTITY_FAILURE", "ZT_RESOURCE_NO_GO", "ZT_CAUSALITY_NO_GO", "ZT_INSUFFICIENT_SEMANTIC_COVERAGE", "ZT_SEMANTIC_COVERAGE_PASS"]:
        assert name in source


def main():
    tests = sorted((name, value) for name, value in globals().items() if name.startswith("test_") and callable(value))
    for name, function in tests:
        function()
        print("%s: PASS" % name)
    print("ZT2_REAL_CONTRACT_TESTS_PASS tests=%d" % len(tests))


if __name__ == "__main__":
    main()
