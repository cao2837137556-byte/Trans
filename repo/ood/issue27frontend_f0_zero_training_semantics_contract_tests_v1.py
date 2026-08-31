#!/usr/bin/env python3
"""Synthetic ZT-1 contract battery for the controlled semantic prototype."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "issue27frontend_f0_zero_training_semantics_v1.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("zt_semantics_tested", str(RUNNER))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load zero-training semantics module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


M = load_runner()


def ev(
    ordinal=0,
    timestamp=0.0,
    source="s",
    member="m",
    version=4,
    protocol=6,
    src="a",
    dst="b",
    sport=1000,
    dport=2000,
    link="ETHERNET",
    ethertype=0x0800,
    mask="default",
    corrupt=False,
    target_uid=None,
):
    return M.Event(
        source_id=source,
        member_id=member,
        packet_ordinal=ordinal,
        timestamp=float(timestamp),
        link_type=link,
        ethertype=ethertype,
        ip_version=version,
        ip_protocol=protocol,
        src_endpoint=src,
        dst_endpoint=dst,
        src_port=sport,
        dst_port=dport,
        decoder_corrupt=corrupt,
        field_presence_mask=mask,
        target_uid=target_uid,
    )


def target(uid="u", ordinal=0, source="s", member="m"):
    return M.TargetSpec(uid=uid, source_id=source, member_id=member, packet_ordinal=ordinal)


def run(events, targets):
    return M.SemanticPrototype().process_member(events, targets)


def reverse(event, ordinal, timestamp):
    return M.Event(
        source_id=event.source_id,
        member_id=event.member_id,
        packet_ordinal=ordinal,
        timestamp=float(timestamp),
        link_type=event.link_type,
        ethertype=event.ethertype,
        ip_version=event.ip_version,
        ip_protocol=event.ip_protocol,
        src_endpoint=event.dst_endpoint,
        dst_endpoint=event.src_endpoint,
        src_port=event.dst_port,
        dst_port=event.src_port,
        field_presence_mask=event.field_presence_mask,
    )


def test_01_ipv4_tcp_bidirectional_h1():
    first = ev(0, 1)
    rows = run([first, reverse(first, 1, 2)], [target("a", 0), target("b", 1)])
    assert [row.context_tier for row in rows] == ["H1", "H1"]
    assert rows[0].causal_context_id == rows[1].causal_context_id
    assert [row.direction_code for row in rows] == ["A_TO_B", "B_TO_A"]


def test_02_ipv6_udp_bidirectional_h1():
    first = ev(0, 1, version=6, protocol=17)
    rows = run([first, reverse(first, 1, 2)], [target("a", 0), target("b", 1)])
    assert rows[0].context_tier == "H1" and rows[0].causal_context_id == rows[1].causal_context_id


def test_03_icmp_h2_without_invented_ports():
    events = [ev(0, 1, protocol=1, sport=None, dport=None), ev(1, 2, protocol=1, sport=None, dport=None)]
    rows = run(events, [target("u", 1)])
    assert rows[0].context_tier == "H2" and not rows[0].transport_ports_present


def test_04_gre_h2_without_invented_ports():
    row = run([ev(0, 1, protocol=47, sport=None, dport=None)], [target()])[0]
    assert row.context_tier == "H2" and row.ip_protocol_or_none == 47


def test_05_other_portless_ip_h2():
    row = run([ev(0, 1, protocol=50, sport=None, dport=None)], [target()])[0]
    assert row.semantic_finite and row.context_tier == "H2"


def test_06_port_bearing_non_tcp_udp_still_h2():
    first = ev(0, 1, protocol=132, sport=7, dport=9)
    second = ev(1, 2, protocol=132, sport=700, dport=900)
    rows = run([first, second], [target("a", 0), target("b", 1)])
    assert rows[0].context_tier == "H2" and rows[0].transport_ports_present
    assert rows[0].causal_context_id == rows[1].causal_context_id


def test_07_non_ip_paired_h3():
    row = run([ev(0, 1, version=None, protocol=None, sport=None, dport=None, ethertype=0x0806)], [target()])[0]
    assert row.semantic_finite and row.context_tier == "H3"


def test_08_keyless_repeated_h4_is_not_singleton():
    events = [ev(i, i, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="x") for i in range(3)]
    row = run(events, [target("u", 2)])[0]
    assert row.context_tier == "H4" and row.context_event_count == 3


def test_09_h4_not_member_wide_pseudo_session():
    events = [
        ev(0, 0, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="x"),
        ev(1, 1, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="x"),
        ev(2, 2, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="y"),
    ]
    rows = run(events, [target("a", 1), target("b", 2)])
    assert rows[0].context_event_count == 2 and rows[1].context_event_count == 1
    assert rows[0].causal_context_id != rows[1].causal_context_id


def test_10_member_boundary_resets_state():
    engine = M.SemanticPrototype()
    events = {
        ("s", "m1"): [ev(0, 1, member="m1")],
        ("s", "m2"): [ev(0, 1, member="m2")],
    }
    rows = engine.materialize(events, [target("a", 0, member="m1"), target("b", 0, member="m2")])
    assert rows[0].context_event_count == rows[1].context_event_count == 1
    assert rows[0].causal_context_id != rows[1].causal_context_id


def test_11_source_boundary_resets_state():
    engine = M.SemanticPrototype()
    events = {
        ("s1", "m"): [ev(0, 1, source="s1")],
        ("s2", "m"): [ev(0, 1, source="s2")],
    }
    rows = engine.materialize(events, [target("a", 0, source="s1"), target("b", 0, source="s2")])
    assert rows[0].causal_context_id != rows[1].causal_context_id


def test_12_idle_gap_equality_and_strict_split():
    events = [ev(0, 0), ev(1, 60), ev(2, 120.0001)]
    rows = run(events, [target("a", 1), target("b", 2)])
    assert rows[0].context_epoch == 0 and rows[0].context_event_count == 2
    assert rows[1].context_epoch == 1 and rows[1].context_event_count == 1


def test_13_span_equality_and_strict_split():
    events = [ev(0, 0), ev(1, 50), ev(2, 100), ev(3, 150), ev(4, 200), ev(5, 250), ev(6, 300), ev(7, 300.0001)]
    rows = run(events, [target("a", 6), target("b", 7)])
    assert rows[0].context_epoch == 0 and rows[0].context_surrogate_span_seconds == 300.0
    assert rows[1].context_epoch == 1 and rows[1].context_event_count == 1


def test_14_event_256_and_257_boundary():
    events = [ev(index, index / 10.0) for index in range(257)]
    rows = run(events, [target("a", 255), target("b", 256)])
    assert rows[0].context_event_count == 256 and rows[0].context_epoch == 0
    assert rows[1].context_event_count == 1 and rows[1].context_epoch == 1


def test_15_current_target_is_inclusive():
    row = run([ev(0, 1), ev(1, 2)], [target("u", 1)])[0]
    assert row.context_event_count == 2 and row.context_surrogate_span_seconds == 1.0


def test_16_future_mutation_cannot_change_prior_row():
    base = [ev(0, 1), ev(1, 2)]
    mutated = [ev(0, 1), ev(1, 999, src="future", dst="packet")]
    first = run(base, [target("u", 0)])[0]
    second = run(mutated, [target("u", 0)])[0]
    assert M.canonical_json_bytes(M.asdict(first)) == M.canonical_json_bytes(M.asdict(second))


def test_17_timestamp_regression_clamps_without_reorder():
    rows = run([ev(0, 10), ev(1, 5), ev(2, 12)], [target("a", 0), target("b", 1), target("c", 2)])
    assert [row.timestamp_regression_count_in_context for row in rows] == [0, 1, 1]
    assert [row.context_surrogate_span_seconds for row in rows] == [0.0, 0.0, 2.0]


def test_18_nonfinite_exact_missing_reason():
    row = run([ev(0, math.nan)], [target()])[0]
    assert not row.semantic_finite and row.semantic_missing_reason == "NONFINITE_EVENT_TIMESTAMP"


def test_19_endpoint_bijection_preserves_partition():
    original = [ev(0, 1, src="a", dst="b"), ev(1, 2, src="b", dst="a", sport=2000, dport=1000)]
    renamed = [ev(0, 1, src="x", dst="y"), ev(1, 2, src="y", dst="x", sport=2000, dport=1000)]
    targets = [target("a", 0), target("b", 1)]
    left, right = run(original, targets), run(renamed, targets)
    assert M.canonical_rows_bytes(left) == M.canonical_rows_bytes(right)


def test_20_raw_endpoints_absent_from_outputs():
    row = run([ev(0, 1, src="secret-a", dst="secret-b")], [target()])[0]
    rendered = M.canonical_json_bytes(M.asdict(row)).decode("utf-8")
    assert "secret-a" not in rendered and "secret-b" not in rendered
    assert not row.raw_endpoint_values_emitted


class TrackingMapping(Mapping):
    def __init__(self, values):
        self.values = values
        self.accessed = []

    def __getitem__(self, key):
        self.accessed.append(key)
        return self.values[key]

    def __iter__(self):
        return iter(self.values)

    def __len__(self):
        return len(self.values)


def test_21_payload_bytes_never_requested():
    values = M.asdict(ev(0, 1))
    values["payload"] = b"do-not-open"
    mapping = TrackingMapping(values)
    event = M.event_from_mapping(mapping)
    assert event.packet_ordinal == 0 and "payload" not in mapping.accessed


def test_22_every_target_exactly_one_row_including_unreached():
    rows = run([ev(0, 1)], [target("a", 0), target("b", 5)])
    assert len(rows) == 2 and len({row.uid for row in rows}) == 2
    assert rows[1].semantic_missing_reason == "TARGET_NOT_REACHED_AT_EXACT_CUTOFF"


def test_23_duplicate_and_unregistered_uid_fail_closed():
    try:
        run([ev(0, 1)], [target("same", 0), target("same", 1)])
    except M.SemanticContractFailure:
        pass
    else:
        raise AssertionError("duplicate UID accepted")
    try:
        run([ev(0, 1, target_uid="unregistered")], [target("registered", 0)])
    except M.SemanticContractFailure:
        pass
    else:
        raise AssertionError("unregistered event UID accepted")


def test_24_label_join_before_conservation_fails_closed():
    audit = M.AccessAudit()
    try:
        audit.request("label")
    except M.ForbiddenRoleAccess:
        pass
    else:
        raise AssertionError("label access accepted")
    assert audit.label_columns_read_during_construction == 1


def test_25_representation_model_score_access_fails_closed():
    for role in ("representation", "model", "weights", "score"):
        try:
            M.AccessAudit().request(role)
        except M.ForbiddenRoleAccess:
            pass
        else:
            raise AssertionError("forbidden role accepted: %s" % role)


def test_26_report_and_final_access_fail_closed():
    for role in ("report", "final"):
        try:
            M.AccessAudit().request(role)
        except M.ForbiddenRoleAccess:
            pass
        else:
            raise AssertionError("forbidden role accepted: %s" % role)


def test_27_state_empty_after_last_targets():
    engine = M.SemanticPrototype()
    engine.process_member([ev(0, 1), ev(1, 2)], [target("u", 1)])
    assert engine.last_state_count == 0


def test_28_irrelevant_tail_does_not_rebuild_released_state():
    first = run([ev(0, 1)], [target("u", 0)])[0]
    second = run([ev(0, 1), ev(1, 2), ev(2, 3)], [target("u", 0)])[0]
    assert M.canonical_json_bytes(M.asdict(first)) == M.canonical_json_bytes(M.asdict(second))


def test_29_clean_and_member_resumed_bytes_identical():
    engine = M.SemanticPrototype()
    events = {
        ("s", "m1"): [ev(0, 1, member="m1")],
        ("s", "m2"): [ev(0, 1, member="m2")],
    }
    targets = [target("a", 0, member="m1"), target("b", 0, member="m2")]
    clean = engine.materialize(events, targets)
    resumed = []
    resumed.extend(M.SemanticPrototype().process_member(events[("s", "m1")], [targets[0]]))
    resumed.extend(M.SemanticPrototype().process_member(events[("s", "m2")], [targets[1]]))
    assert M.canonical_rows_bytes(clean) == M.canonical_rows_bytes(resumed)


def test_30_python39_syntax_runtime_and_no_learning_surface():
    source = RUNNER.read_text(encoding="utf-8")
    ast.parse(source, filename=str(RUNNER), feature_version=(3, 9))
    assert "match " not in source and "Path.write_text" not in source and "Path.write_bytes" not in source
    M.assert_zero_training_source(RUNNER)
    assert M.MAX_EVENTS == 256 and M.MAX_SPAN_SECONDS == 300.0 and M.IDLE_GAP_SECONDS == 60.0


def test_31_engineering_failure_removes_scientific_verdict():
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        (out / "zt_synthetic_verdict.json").write_text("stale", encoding="utf-8")
        M.write_synthetic_bundle(out, [], "ZT_SEMANTIC_COVERAGE_PASS", engineering_failure="synthetic failure")
        assert not (out / "zt_synthetic_verdict.json").exists()
        assert (out / "engineering_failure.json").is_file()


def test_32_sha256sums_covers_every_scientific_output():
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        rows = run([ev(0, 1)], [target()])
        identities = M.write_synthetic_bundle(out, rows, "ZT_SEMANTIC_COVERAGE_PASS")
        lines = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        parsed = {line.split("  ", 1)[1]: line.split("  ", 1)[0] for line in lines}
        assert parsed == identities
        for name, digest in parsed.items():
            assert hashlib.sha256((out / name).read_bytes()).hexdigest() == digest


def test_33_corrupt_decode_exact_missing_reason():
    row = run([ev(0, 1, corrupt=True)], [target()])[0]
    assert row.semantic_missing_reason == "DECODER_CORRUPT_EVENT"


def test_34_absent_packet_ordinal_exact_missing_reason():
    event = ev(0, 1)
    event = M.Event(**dict(M.asdict(event), packet_ordinal=None))
    row = run([event], [target()])[0]
    assert row.semantic_missing_reason == "REQUIRED_PACKET_ORDINAL_ABSENT"


def test_35_h4_base_class_return_opens_new_epoch():
    events = [
        ev(0, 0, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="x"),
        ev(1, 1, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="y"),
        ev(2, 2, version=None, protocol=None, src=None, dst=None, sport=None, dport=None, mask="x"),
    ]
    rows = run(events, [target("a", 0), target("b", 2)])
    assert rows[0].context_epoch == 0 and rows[1].context_epoch == 1
    assert rows[0].causal_context_id != rows[1].causal_context_id


def test_36_contract_identity_is_exact():
    repo_root = HERE.parent.parent
    assert M.verify_contract(repo_root) == M.CONTRACT_SHA256
    assert set(M.MISSING_REASONS) == {
        "DECODER_CORRUPT_EVENT",
        "NONFINITE_EVENT_TIMESTAMP",
        "REQUIRED_PACKET_ORDINAL_ABSENT",
        "TARGET_NOT_REACHED_AT_EXACT_CUTOFF",
        "CONTEXT_CONSTRUCTION_INVARIANT_FAILURE",
    }


def main():
    tests = sorted((name, value) for name, value in globals().items() if name.startswith("test_") and callable(value))
    if len(tests) != 36:
        raise AssertionError("expected 36 tests, got %d" % len(tests))
    for name, function in tests:
        function()
        print("%s: PASS" % name)
    print(json.dumps({"status": "PASS", "tests": len(tests)}, sort_keys=True))


if __name__ == "__main__":
    main()
