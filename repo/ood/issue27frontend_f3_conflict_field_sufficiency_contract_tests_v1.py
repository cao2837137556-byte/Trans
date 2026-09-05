#!/usr/bin/env python3
"""Synthetic contract tests for the Frontend-F3 field-sufficiency audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent
SUBJECT = HERE / "issue27frontend_f3_conflict_field_sufficiency_v1.py"


def load_subject():
    spec = importlib.util.spec_from_file_location("frontend_f3_subject", str(SUBJECT))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def base_raw(**updates):
    row = {
        "frame.len": "84", "ip.len": "68", "ipv6.plen": "", "ip.ttl": "64", "ipv6.hlim": "",
        "tcp.flags": "", "tcp.len": "", "udp.length": "48",
    }
    row.update(updates)
    return row


def make_row(uid, label, teacher, hashes):
    return {
        "uid": uid, "label": label, "teacher_kind": teacher,
        "source_group": "s", "attack_family": "attack" if label else "benign",
        "prefix_sha256": hashes,
    }


def main() -> int:
    subject = load_subject()
    tests = []

    tests.append(("delta_zero", subject.delta_log2_us(0.0) == "ZERO"))
    tests.append(("delta_log2", subject.delta_log2_us(3e-6) == "1" and subject.delta_log2_us(37e-6) == "5"))
    tests.append(("port_classes", [subject.port_class(x) for x in (None, 53, 1024, 49151, 49152)] == ["NONE", "SYSTEM", "REGISTERED", "REGISTERED", "DYNAMIC"]))
    tests.append(("high_port_masked", subject.port_semantic(37103) == "REGISTERED" and "37103" not in subject.port_semantic(37103)))
    tests.append(("system_port_kept", subject.port_semantic(53) == "SYSTEM:53"))
    tests.append(("ttl_bins", [subject.ttl_bucket(x) for x in (None, 31, 32, 64, 128, 192)] == ["NONE", "0_31", "32_63", "64_127", "128_191", "192_255"]))
    tests.append(("empty_cell_normalization", subject.normalize_tshark_cell(None) == "" and subject.normalize_tshark_cell("None") == "" and subject.normalize_tshark_cell("0") == "0"))
    tests.append(("autoreset_frame_normalization", subject.normalize_reset_frame_number("1", 0) == "1" and subject.normalize_reset_frame_number("100000", 99999) == "100000" and subject.normalize_reset_frame_number("1", 100000) == "100001"))

    udp = SimpleNamespace(ip_protocol=17, src_port=37103, dst_port=53)
    sig = subject.extended_signatures("BASE", base_raw(), udp, 3e-6)
    tests.append(("ladder_cumulative", all(sig[level].startswith(sig["L0"]) for level in subject.LEVELS) and len(sig["L0"]) < len(sig["L1"]) < len(sig["L2"]) < len(sig["L3"])))
    tests.append(("signature_masks_high_port", "37103" not in sig["L2"] and "SYSTEM:53" in sig["L2"]))

    rows = [
        make_row("a", 0, "benign_normal", {"L0": "x", "L1": "u", "L2": "u", "L3": "u"}),
        make_row("b", 1, "attack_hard", {"L0": "x", "L1": "v", "L2": "v", "L3": "v"}),
    ]
    summary, memberships, selected = subject.analyze(rows)
    tests.append(("first_passing_level", selected == "L1" and summary[0]["hard_protected_mixed_buckets"] == 1 and summary[1]["hard_protected_mixed_buckets"] == 0))
    tests.append(("conflict_membership_complete", len([row for row in memberships if row["level"] == "L0"]) == 2))

    failures = [name for name, passed in tests if not passed]
    for name, passed in tests:
        print("%s %s" % ("PASS" if passed else "FAIL", name))
    print("SUMMARY %d/%d PASS" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
