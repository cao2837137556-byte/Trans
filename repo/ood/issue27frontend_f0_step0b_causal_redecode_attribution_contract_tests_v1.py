#!/usr/bin/env python3
"""Synthetic contract tests for Frontend-F0 Step-0b."""

from __future__ import annotations

import ast
import csv
import gzip
import hashlib
import importlib.util
import json
import math
import sys
import tempfile
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "issue27frontend_f0_step0b_causal_redecode_attribution_v1.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("step0b_runner_tested", str(RUNNER))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load runner")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


M = load_runner()


def ev(ts=1.0, version=4, proto=6, src="a", dst="b", sport=1, dport=2):
    return M.SimpleEvent(float(ts), src, dst, int(version), int(proto), int(sport), int(dport))


def target(uid="u"):
    return {"uid": uid, "source_group": "s", "device_family": "d", "role": "fit", "phase": "fit", "member": "m", "event_position": 0}


def test_01_pinned_hashes_are_exact():
    values = M.verify_pins()
    assert values["protocol"] == M.PROTOCOL_SHA256
    assert len(values) == len(M.PINNED)


def test_02_identity_is_preopen_and_gotham_sha_is_not_md5_substitute():
    source = RUNNER.read_text(encoding="utf-8")
    execute = source[source.index("def execute_real"):source.index("def parser")]
    assert execute.index("verify_reviewed_identity") < execute.index("open_member_rows(ckbu")
    assert "container_sha256" in M.IDENTITY_FIELDS
    assert "published_identity_if_archive" in M.IDENTITY_FIELDS
    assert "Gotham published MD5 mismatch" in source
    assert "R0 identity attachment SHA drift" in source


def test_03_unallowlisted_member_fails_before_open():
    manifest = pd.DataFrame([{"dataset_kind": "gotham_zip", "container_path": "z", "pcap_member": "allowed", "fit_cutoff_event_position_inclusive": 3}])
    lookup = M.manifest_lookup(manifest)
    assert ("gotham_zip", "z", "missing") not in lookup


def test_04_report_and_final_fail_preopen():
    source = RUNNER.read_text(encoding="utf-8")
    assert "report/FINAL packet member in fit/select scope" in source
    assert '"is_report": "false"' in source and '"is_final": "false"' in source


def test_05_uid_denominator_literal_and_scope_loader():
    source = RUNNER.read_text(encoding="utf-8")
    assert source.count("25_467") >= 5
    assert "target metadata UID denominator drift" in source


def test_06_duplicate_positions_rejected():
    source = RUNNER.read_text(encoding="utf-8")
    assert "duplicate target position within packet member" in source
    assert "duplicated(key + [\"target_event_position_within_capture\"])" in source


def test_07_current_inclusive_exact_cutoff():
    discovered, decoded = M.discovery_pass(iter([ev(1), ev(2), ev(3)]), {0, 2}, 2)
    assert decoded == 3 and set(discovered) == {0, 2}
    try:
        M.discovery_pass(iter([ev(1), ev(2)]), {0, 2}, 2)
    except M.DecodeSchemaFailure:
        pass
    else:
        raise AssertionError("incomplete prefix accepted")


def test_08_future_packet_cannot_change_earlier_target():
    by = {0: target("u")}
    first = M.formal_ip_session(ev(2))
    out_a = M.replay_member(iter([ev(2)]), by, {0: first})
    out_b = M.replay_member(iter([ev(2), ev(1)]), by, {0: first})
    assert out_a == out_b


def test_09_ipv4_tcp_key_supported():
    value = ev(version=4, proto=6)
    assert M.formal_ip_session(value) is not None
    p = M.primitive_predicates(value, False)
    assert not p["NO_IP_SESSION_KEY"] and not p["UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP"]


def test_10_ipv6_udp_key_supported():
    value = ev(version=6, proto=17)
    assert M.formal_ip_session(value) is not None
    p = M.primitive_predicates(value, False)
    assert not p["NO_IP_SESSION_KEY"] and not p["UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP"]


def test_11_ipv4_icmp_key_but_unsupported():
    value = ev(version=4, proto=1)
    assert M.formal_ip_session(value) is not None
    p = M.primitive_predicates(value, False)
    assert not p["NO_IP_SESSION_KEY"] and p["UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP"]


def test_12_gre_key_but_unsupported():
    value = ev(version=4, proto=47)
    assert M.formal_ip_session(value) is not None
    assert M.primitive_predicates(value, False)["UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP"]


def test_13_non_ip_has_no_key():
    value = ev(version=0, proto=0)
    assert M.formal_ip_session(value) is None
    assert M.primitive_predicates(value, False)["NO_IP_SESSION_KEY"]


def test_14_nonfinite_is_independent_and_active_append_fails_closed():
    value = ev(ts=math.nan, version=0, proto=1)
    p = M.primitive_predicates(value, False)
    assert p["NONFINITE_TARGET_TIMESTAMP"] and p["NO_IP_SESSION_KEY"] and p["UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP"]
    active = ev(ts=math.nan, version=4, proto=6)
    session = M.formal_ip_session(active)
    try:
        M.replay_member(iter([active]), {0: target()}, {0: session})
    except M.DecodeSchemaFailure as exc:
        assert "active-IP append" in str(exc)
    else:
        raise AssertionError("nonfinite active IP was reordered into attribution")


def test_15_equal_timestamps_do_not_poison():
    events = [ev(1), ev(1)]
    session = M.formal_ip_session(events[0])
    rows = M.replay_member(iter(events), {1: dict(target(), event_position=1)}, {1: session})
    assert not rows[0]["SESSION_TIMESTAMP_REGRESSION"]


def test_16_decrease_poisons_current_and_later_only():
    events = [ev(2), ev(1), ev(3)]
    session = M.formal_ip_session(events[0])
    by = {0: target("a"), 1: dict(target("b"), event_position=1), 2: dict(target("c"), event_position=2)}
    rows = M.replay_member(iter(events), by, {0: session, 1: session, 2: session})
    assert [r["SESSION_TIMESTAMP_REGRESSION"] for r in rows] == [False, True, True]


def test_17_poison_is_session_local():
    a1, a2 = ev(2, src="a", dst="b"), ev(1, src="a", dst="b")
    c = ev(3, src="c", dst="d")
    sa, sc = M.formal_ip_session(a1), M.formal_ip_session(c)
    by = {1: dict(target("a"), event_position=1), 2: dict(target("c"), event_position=2)}
    rows = M.replay_member(iter([a1, a2, c]), by, {1: sa, 2: sc})
    assert rows[0]["SESSION_TIMESTAMP_REGRESSION"] and not rows[1]["SESSION_TIMESTAMP_REGRESSION"]


def test_18_post_last_target_does_not_recreate_state():
    first, tail, other = ev(1, src="a", dst="b"), ev(2, src="a", dst="b"), ev(3, src="c", dst="d")
    s1, s2 = M.formal_ip_session(first), M.formal_ip_session(other)
    by = {0: target("a"), 2: dict(target("b"), event_position=2)}
    rows = M.replay_member(iter([first, tail, other]), by, {0: s1, 2: s2})
    assert len(rows) == 2


def test_19_multiple_predicates_primary_and_any_true_counts():
    values = M.primitive_predicates(ev(math.nan, version=0, proto=1), True)
    assert sum(values.values()) == 4
    assert M.primary_reason(values) == "SESSION_TIMESTAMP_REGRESSION"
    counts = M.mechanism_counts([values])
    assert all(value == 1 for value in counts.values())
    assert M.classify_mechanisms({"PROTOCOL_COVERAGE": 1}) == "NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS"
    assert M.classify_mechanisms({"CAUSAL_TIMESTAMP_ORDER": 1}) == "NEW_FRONTEND_REQUIRED_BY_INPUT_SEMANTICS"
    assert M.classify_mechanisms(counts) == "MIXED_MISSINGNESS_MECHANISMS"


def test_20_fifth_cause_rejected():
    try:
        M.primary_reason({"FIFTH": True})
    except M.DecodeSchemaFailure:
        pass
    else:
        raise AssertionError("fifth cause accepted")


def test_21_exact_equivalence_literals_are_mandatory():
    source = RUNNER.read_text(encoding="utf-8")
    assert '"equivalence_matches": int(matches.sum())' in source
    assert '"equivalence_expected": 25_467' in source
    assert 'equivalence["missing"] != 11_640' in source


def test_22_equivalence_failure_withholds_verdict():
    source = RUNNER.read_text(encoding="utf-8")
    unlink = source.index("verdict_path.unlink()")
    failure = source.index("raise EquivalenceFailure", unlink)
    label_join = source.index("# Labels are joined only now")
    assert unlink < failure < label_join


def test_23_only_uid_missing_opened_from_npz():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "a.npz"
        np.savez(path, uid=np.asarray(["u"]), missing=np.asarray([True]), representation=np.ones((1, 2)))
        uid, missing, opened = M.load_availability(path)
        assert uid.tolist() == ["u"] and missing.tolist() == [True]
        assert opened == {"uid", "missing"}


def test_24_forbidden_model_score_objects_absent_from_r0():
    source = RUNNER.read_text(encoding="utf-8")
    section = source[source.index("def materialize_identity"):source.index("@dataclass(frozen=True)")]
    for token in ["representation", "probe_state", "weights", "threshold"]:
        assert token not in section
    assert '"model_opened": 0' in section and '"score_opened": 0' in section


def test_25_labels_join_only_after_r3():
    source = RUNNER.read_text(encoding="utf-8")
    gate = source.index("if not matches.all()")
    label = source.index("# Labels are joined only now")
    assert gate < label
    causal = source[source.index("CAUSAL_COLUMNS"):source.index("PLAN_JOIN_COLUMNS")]
    assert "attack_family" not in causal


def test_26_checkpoint_identity_covers_all_drift_axes():
    identity = M.member_checkpoint_identity("c", "t", {"m": 1}, {"x": 2}, [("u", 0)])
    variants = [
        M.member_checkpoint_identity("C", "t", {"m": 1}, {"x": 2}, [("u", 0)]),
        M.member_checkpoint_identity("c", "T", {"m": 1}, {"x": 2}, [("u", 0)]),
        M.member_checkpoint_identity("c", "t", {"m": 2}, {"x": 2}, [("u", 0)]),
        M.member_checkpoint_identity("c", "t", {"m": 1}, {"x": 3}, [("u", 0)]),
        M.member_checkpoint_identity("c", "t", {"m": 1}, {"x": 2}, [("v", 0)]),
    ]
    assert all(value != identity for value in variants)


def test_27_resume_only_from_complete_member_boundary():
    source = RUNNER.read_text(encoding="utf-8")
    assert "checkpoint.is_file() and completed.is_file()" in source
    assert "completed member checkpoint drift" in source
    assert "REUSED_EXACT_MEMBER_BOUNDARY" in source


def test_28_device_session_record_denominators_separate():
    source = RUNNER.read_text(encoding="utf-8")
    assert '"devices": int(' in source
    assert '"sessions": int(' in source
    assert '"records": len(joined)' in source
    first = M.reversible_session_candidate(target("u"), M.formal_ip_session(ev()))
    second_target = dict(target("v"), member="other")
    second = M.reversible_session_candidate(second_target, M.formal_ip_session(ev()))
    assert json.loads(first)["endpoints"] and first != second


def test_29_zero_count_universe_rows_are_serialized():
    source = RUNNER.read_text(encoding="utf-8")
    assert "universe = sorted(set(joined[group].astype(str)))" in source
    assert '"missing_targets": len(subset)' in source
    assert '"excluded_devices_from_frontend_claim"' in source
    assert '"excluded_attack_families_from_frontend_claim"' in source


def test_30_python39_syntax_and_api_contract():
    ast.parse(RUNNER.read_text(encoding="utf-8"), filename=str(RUNNER), feature_version=(3, 9))
    source = RUNNER.read_text(encoding="utf-8")
    assert "match " not in source
    assert ".write_text(" not in source
    assert ".write_bytes(" not in source


def test_31_large_outputs_stream_and_atomic_finalize():
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "large.csv.gz"
        M.atomic_csv(path, ({"x": index} for index in range(10_000)), ["x"], gzip_output=True)
        assert path.is_file() and not list(path.parent.glob(".*.tmp"))
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            assert sum(1 for _ in stream) == 10_001


def test_32_engineering_failure_never_creates_scientific_verdict():
    with tempfile.TemporaryDirectory() as folder:
        out = Path(folder)
        try:
            M.verify_reviewed_identity(out, Path("missing-tshark"))
        except M.PreopenFailure:
            pass
        else:
            raise AssertionError("missing identity accepted")
        assert not (out / "frontend_f0_step0b_mechanism_verdict.json").exists()


def main() -> None:
    tests = [(name, value) for name, value in globals().items() if name.startswith("test_") and callable(value)]
    tests.sort()
    if len(tests) != 32:
        raise AssertionError("expected 32 tests, got %d" % len(tests))
    for name, value in tests:
        value()
        print("%s: PASS" % name)
    print(json.dumps({"status": "PASS", "tests": len(tests)}, sort_keys=True))


if __name__ == "__main__":
    main()
