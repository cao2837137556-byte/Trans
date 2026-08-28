#!/usr/bin/env python3
"""Narrow regression tests for Frontend-F0 Step-0."""

from __future__ import annotations

import ast
import importlib.util
import tempfile
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
SOURCE = HERE / "issue27frontend_f0_missingness_mechanism_audit_v1.py"


def load():
    spec = importlib.util.spec_from_file_location("frontend_f0_step0", str(SOURCE))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_python39_syntax() -> None:
    ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_literal_predicates() -> None:
    mod = load()
    assert mod.PRIMITIVES == (
        "NO_IP_SESSION_KEY", "UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP",
        "NONFINITE_TARGET_TIMESTAMP", "SESSION_TIMESTAMP_REGRESSION",
    )


def test_npz_loader_does_not_require_representation() -> None:
    mod = load()
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "availability.npz"
        np.savez(path, uid=np.asarray(["a", "b"]), missing=np.asarray([False, True]),
                 representation=np.asarray([[1.0], [2.0]]))
        uid, missing, members = mod.read_availability(path)
        assert uid.tolist() == ["a", "b"]
        assert missing.tolist() == [False, True]
        assert "representation.npy" in members


def test_noninvertible_schema_stops_m1() -> None:
    mod = load()
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        stage = root / mod.STAGE
        stage.mkdir(parents=True)
        (stage / "ckda_d1_fit_select_target_metadata.csv").write_text(
            "uid,timestamp_epoch,session_id\na,1.0,hash\n", encoding="utf-8"
        )
        audit = mod.inventory_evidence(root, {"a"})
        assert audit["all_primitive_predicates_target_identifiable"] is False
        assert audit["required_evidence_recoverable"]["finite_target_timestamp"] is True
        assert audit["required_evidence_recoverable"]["ip_protocol"] is False


def test_source_has_no_forbidden_array_access() -> None:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    forbidden = {"representation", "probe_state"}
    indexed = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Constant):
            if isinstance(node.slice.value, str):
                indexed.add(node.slice.value)
    assert not (indexed & forbidden)


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print({"status": "PASS", "tests": len(tests)})


if __name__ == "__main__":
    main()
