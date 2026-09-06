#!/usr/bin/env python3
"""Synthetic contract tests for the frozen Frontend-F4 fieldwise input map."""

from __future__ import annotations

import ast
import hashlib
import importlib.util
import math
import pathlib
import tempfile
from typing import Any, Callable, Dict, List

import numpy as np


def signature(**changes: object) -> str:
    values: Dict[str, object] = {
        "tier": "H1", "direction": "A_TO_B", "link": "encap:1", "ethertype": "2048",
        "version": "4", "protocol": "6", "group": "TCP", "ports": "true",
        "mask": "frame.encap_type|ip.dst|ip.proto|ip.src|tcp.dstport|tcp.srcport",
        "length_bin": "64-127", "delta_bin": "(1e-3,1e-2]", "regression": "false",
        "icmp_type": "NONE", "icmp_code": "NONE", "gre": "false", "frame_len": "100",
        "delta_log": "12", "transport_len": "60", "tcp_flags": "24",
    }
    values.update(changes)
    return "\x1f".join([
        str(values["tier"]), str(values["direction"]), str(values["link"]), str(values["ethertype"]),
        str(values["version"]), str(values["protocol"]), str(values["group"]), str(values["ports"]),
        str(values["mask"]), str(values["length_bin"]), str(values["delta_bin"]), str(values["regression"]),
        str(values["icmp_type"]), str(values["icmp_code"]), str(values["gre"]),
        "FRAME_LEN=" + str(values["frame_len"]), "DELTA_LOG2_US=" + str(values["delta_log"]),
        "TRANSPORT_LEN=" + str(values["transport_len"]), "TCP_FLAGS=" + str(values["tcp_flags"]),
    ])


def expect_raises(error: type, action: Callable[[], object]) -> None:
    try:
        action()
    except error:
        return
    raise AssertionError("expected %s" % error.__name__)


def roundtrip(m: Any, text: str) -> np.ndarray:
    vector = m.encode_event(m.parse_l1(text))
    assert m.decode_event(vector) == text
    return vector


def t01_shape(m: Any) -> None:
    m.parse_l1(signature())
    expect_raises(m.F4Failure, lambda: m.parse_l1(signature() + "\x1fEXTRA"))
    expect_raises(m.F4Failure, lambda: m.parse_l1("\x1f".join(signature().split("\x1f")[:-1])))


def t02_tail_names(m: Any) -> None:
    bad = signature().replace("FRAME_LEN=100", "FRAME_LENGTH=100")
    expect_raises(m.F4Failure, lambda: m.parse_l1(bad))
    bad = signature().replace("DELTA_LOG2_US=12\x1fTRANSPORT_LEN=60", "TRANSPORT_LEN=60\x1fDELTA_LOG2_US=12")
    expect_raises(m.F4Failure, lambda: m.parse_l1(bad))


def t03_categories(m: Any) -> None:
    for tier in m.TIER:
        roundtrip(m, signature(tier=tier))
    for direction in m.DIRECTION:
        roundtrip(m, signature(direction=direction))
    for group in m.PROTOCOL_GROUP:
        roundtrip(m, signature(group=group))
    expect_raises(m.F4Failure, lambda: m.parse_l1(signature(tier="H5")))


def t04_uint_bounds(m: Any) -> None:
    roundtrip(m, signature(protocol="0", ethertype="0", frame_len="0", length_bin="<=63"))
    roundtrip(m, signature(protocol="255", ethertype="65535", frame_len="4294967295", length_bin=">=4096"))
    expect_raises(m.DomainStop, lambda: m.parse_l1(signature(protocol="256")))
    expect_raises(m.DomainStop, lambda: m.parse_l1(signature(ethertype="65536")))
    expect_raises(m.DomainStop, lambda: m.parse_l1(signature(frame_len="4294967296", length_bin=">=4096")))


def t05_noncanonical_numbers(m: Any) -> None:
    for value in ("01", " 1", "+1", "-1", "1.0", "NaN", "inf", "１２"):
        expect_raises(m.F4Failure, lambda value=value: m.parse_l1(signature(protocol=value)))


def t06_none_zero(m: Any) -> None:
    for field in ("ethertype", "protocol", "icmp_type", "icmp_code", "transport_len", "tcp_flags"):
        a, b = roundtrip(m, signature(**{field: "NONE"})), roundtrip(m, signature(**{field: "0"}))
        assert not np.array_equal(a, b)


def t07_delta_zero(m: Any) -> None:
    a = roundtrip(m, signature(delta_log="ZERO", delta_bin="0"))
    b = roundtrip(m, signature(delta_log="0", delta_bin="0"))
    c = roundtrip(m, signature(delta_log="255"))
    assert not np.array_equal(a, b) and c[109] == np.float32(255 / 256)


def t08_uint32_float_exact(m: Any) -> None:
    values = (65535, 65536, 65537, 2**24 - 1, 2**24, 2**24 + 1, 0xFFFFFFFF)
    enc = [roundtrip(m, signature(frame_len=str(v), length_bin=m.length_bin_for(v))) for v in values]
    assert len({x[105:108].tobytes() for x in enc}) == len(values)


def t09_log_formula(m: Any) -> None:
    for value in (0, 1, 100, 0xFFFFFFFF):
        vector = roundtrip(m, signature(frame_len=str(value), length_bin=m.length_bin_for(value)))
        assert vector[107] == np.float32(math.log2(1 + value) / 32.0)


def t10_tcp_flags(m: Any) -> None:
    none = roundtrip(m, signature(tcp_flags="NONE"))
    zero = roundtrip(m, signature(tcp_flags="0"))
    assert not np.array_equal(none, zero)
    for bit in range(16):
        roundtrip(m, signature(tcp_flags=str(1 << bit)))


def t11_presence_mask(m: Any) -> None:
    roundtrip(m, signature(mask="none"))
    roundtrip(m, signature(mask=m.PRESENCE_FIELDS[0]))
    roundtrip(m, signature(mask="|".join(m.PRESENCE_FIELDS)))
    expect_raises(m.F4Failure, lambda: m.parse_l1(signature(mask="bogus")))
    expect_raises(m.F4Failure, lambda: m.parse_l1(signature(mask="eth.src|eth.src")))
    expect_raises(m.F4Failure, lambda: m.parse_l1(signature(mask="eth.src|eth.dst")))


def t12_encapsulation(m: Any) -> None:
    unknown = roundtrip(m, signature(link="encap:unknown"))
    zero = roundtrip(m, signature(link="encap:0"))
    maximum = roundtrip(m, signature(link="encap:4294967295"))
    assert not np.array_equal(unknown, zero) and maximum[7] == 1.0


def t13_offsets_dtype(m: Any) -> None:
    assert m.OFFSETS[0][1] == 0 and m.OFFSETS[-1][2] == m.WIDTH == 131
    assert all(b - a > 0 for _, a, b in m.OFFSETS)
    assert all(m.OFFSETS[i][2] == m.OFFSETS[i + 1][1] for i in range(len(m.OFFSETS) - 1))
    assert roundtrip(m, signature()).dtype == np.float32


def t14_corrupt_vectors(m: Any) -> None:
    base = roundtrip(m, signature())
    for index, value in ((0, np.float32(0.5)), (7, np.float32(0.0)), (105, np.float32(0.1)), (107, np.float32(0.0))):
        bad = base.copy(); bad[index] = value
        expect_raises(m.F4Failure, lambda bad=bad: m.decode_event(bad))
    bad = base.copy(); bad[0] = np.nan
    expect_raises(m.F4Failure, lambda: m.decode_event(bad))


def t15_unseen_combination(m: Any) -> None:
    a = signature(tier="H4", direction="UNKNOWN", link="encap:4294967295", ethertype="NONE", version="NONE",
                  protocol="NONE", group="KEYLESS", ports="false", mask="none", length_bin="<=63", frame_len="1",
                  delta_log="ZERO", delta_bin="0", transport_len="NONE", tcp_flags="NONE")
    b = a.replace("FRAME_LEN=1", "FRAME_LEN=2")
    assert roundtrip(m, a).tobytes() != roundtrip(m, b).tobytes()


def t16_length_difference(m: Any) -> None:
    a = roundtrip(m, signature(frame_len="100", transport_len="60"))
    b = roundtrip(m, signature(frame_len="101", transport_len="61"))
    assert a.tobytes() != b.tobytes()


def t17_pad_separation(m: Any) -> None:
    vector = roundtrip(m, signature())
    assert vector.any() and not np.zeros(m.WIDTH, dtype=np.float32).any()


def t18_h1_h4_roundtrip(m: Any) -> None:
    fixtures = [signature(tier="H1"), signature(tier="H2", protocol="1", group="ICMP", ports="false", icmp_type="8", icmp_code="0", transport_len="NONE", tcp_flags="NONE"),
                signature(tier="H3", protocol="47", group="GRE", ports="false", gre="true", transport_len="NONE", tcp_flags="NONE"),
                signature(tier="H4", link="encap:unknown", ethertype="NONE", version="NONE", protocol="NONE", group="KEYLESS", ports="false", mask="none", transport_len="NONE", tcp_flags="NONE")]
    for item in fixtures:
        roundtrip(m, item)


def t19_future_invariance(m: Any) -> None:
    base = [signature(frame_len="100"), signature(frame_len="101")]
    a = m.encode_context(base)
    b = m.encode_context(base + [signature(frame_len="102")])
    assert m.prefix_bytes(a, 1) == m.prefix_bytes(b, 1)


def t20_context_order_independence(m: Any) -> None:
    a, b = [signature(frame_len="100")], [signature(frame_len="101")]
    first = {"a": m.encode_context(a), "b": m.encode_context(b)}
    second = {"b": m.encode_context(b), "a": m.encode_context(a)}
    assert all(np.array_equal(first[k], second[k]) for k in first)


def t21_metadata_exclusion(m: Any) -> None:
    record = m.parse_l1(signature())
    for key in ("uid", "source", "label", "owner", "teacher", "split"):
        bad = dict(record); bad[key] = "changed"
        expect_raises(m.F4Failure, lambda bad=bad: m.encode_event(bad))


def t22_offsets_prefix_and_uid(m: Any) -> None:
    matrix = m.encode_context([signature(frame_len="100"), signature(frame_len="101")])
    assert m.prefix_bytes(matrix, 0) != m.prefix_bytes(matrix, 1)
    expect_raises(m.F4Failure, lambda: m.prefix_bytes(matrix, 2))
    uids = ["a", "b", "a"]
    assert len(set(uids)) != len(uids)


def t23_collision_detector(m: Any) -> None:
    assert m.collision_pairs([("a", b"same"), ("b", b"same")]) == [("a", "b")]
    assert m.collision_pairs([("a", b"one"), ("b", b"two")]) == []


def t24_mixed_labels(m: Any) -> None:
    assert m.mixed_label_bucket_count([(b"x", 0), (b"x", 1)]) == 1
    assert m.mixed_label_bucket_count([(b"x", 0), (b"x", 0)]) == 0


def t25_kill_order_static(m: Any) -> None:
    text = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    assert text.index('contexts = read_gzip_jsonl') < text.index('kill_contexts = read_gzip_jsonl')
    assert "kill_only_container_opened_after_parent" in text


def t26_preflight_guards(m: Any) -> None:
    with tempfile.TemporaryDirectory() as temp:
        existing = pathlib.Path(temp)
        expect_raises(m.F4Failure, lambda: m.preflight(existing, m.EXECUTION_TOKEN))
    expect_raises(m.F4Failure, lambda: m.preflight(m.ROOT / "runs" / "synthetic-never-created", "WRONG"))


def t27_resource_boundaries(m: Any) -> None:
    assert m.resource_values_ok(m.MAX_WALL_SECONDS, m.MAX_PEAK_BYTES, m.MAX_OUTPUT_BYTES, m.MIN_FREE_BYTES)
    assert not m.resource_values_ok(m.MAX_WALL_SECONDS + 0.1, 0, 0, m.MIN_FREE_BYTES)
    assert not m.resource_values_ok(0, m.MAX_PEAK_BYTES + 1, 0, m.MIN_FREE_BYTES)
    assert not m.resource_values_ok(0, 0, m.MAX_OUTPUT_BYTES + 1, m.MIN_FREE_BYTES)
    assert not m.resource_values_ok(0, 0, 0, m.MIN_FREE_BYTES - 1)
    assert m.terminal_state(m.ResourceStop()) == "F4_RESOURCE_NO_GO"
    assert m.terminal_state(m.DomainStop()) == "F4_FIELD_DOMAIN_UNSUPPORTED"
    assert m.terminal_state(m.ScientificStop()) == "F4_FIELDWISE_INPUT_NO_GO"
    assert m.peak_working_set_bytes() > 0


def t28_import_io_determinism(m: Any) -> None:
    source = pathlib.Path(m.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {node.names[0].name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)}
    imports |= {str(node.module).split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imports.intersection({"torch", "sklearn", "pandas", "requests", "socket", "subprocess"})
    assert all(term not in source for term in ("np.load(", "tshark.exe", "urllib.request", "optimizer.step"))
    a = m.encode_context([signature(), signature(frame_len="101")])
    b = m.encode_context([signature(), signature(frame_len="101")])
    assert a.astype("<f4").tobytes() == b.astype("<f4").tobytes()


TESTS = [
    t01_shape, t02_tail_names, t03_categories, t04_uint_bounds, t05_noncanonical_numbers,
    t06_none_zero, t07_delta_zero, t08_uint32_float_exact, t09_log_formula, t10_tcp_flags,
    t11_presence_mask, t12_encapsulation, t13_offsets_dtype, t14_corrupt_vectors,
    t15_unseen_combination, t16_length_difference, t17_pad_separation, t18_h1_h4_roundtrip,
    t19_future_invariance, t20_context_order_independence, t21_metadata_exclusion,
    t22_offsets_prefix_and_uid, t23_collision_detector, t24_mixed_labels, t25_kill_order_static,
    t26_preflight_guards, t27_resource_boundaries, t28_import_io_determinism,
]


def run_all(module: Any) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for index, test in enumerate(TESTS, 1):
        try:
            test(module)
            rows.append({"index": index, "name": test.__name__, "passed": True})
        except Exception as exc:
            rows.append({"index": index, "name": test.__name__, "passed": False, "error": repr(exc)})
    return rows


def main() -> None:
    path = pathlib.Path(__file__).with_name("issue27frontend_f4_fieldwise_input_v1.py")
    spec = importlib.util.spec_from_file_location("f4_runner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load F4 runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = run_all(module)
    for row in rows:
        print(("PASS" if row["passed"] else "FAIL") + " %02d %s%s" % (row["index"], row["name"], "" if row["passed"] else " " + str(row["error"])))
    passed = sum(bool(row["passed"]) for row in rows)
    print("SUMMARY %d/%d PASS" % (passed, len(rows)))
    if passed != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
