#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


SOURCE = Path(__file__).with_name("issue27frontend_f0_stage1_compatibility_audit_v1.py")


def load():
    spec = importlib.util.spec_from_file_location("frontend_stage1", str(SOURCE))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base():
    return {
        "python39_syntax_compatible": True,
        "adapter_feasible": True,
        "official_code_license_clear": True,
        "known_current_role_overlap": False,
        "checkpoint": {"official_link": "x", "published_sha256": "", "published_bytes": 0},
    }


def test_python39_syntax():
    ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_checkpoint_identity_failure_is_not_engineering_failure():
    mod = load()
    assert mod.decide(base()) == "F0_NO_USABLE_OFFICIAL_CHECKPOINT"


def test_backup_only_on_engineering_failure():
    mod = load()
    value = base()
    value["python39_syntax_compatible"] = False
    assert mod.decide(value) == "F0_ENGINEERING_INCOMPATIBLE"


def test_lineage_precedes_checkpoint():
    mod = load()
    value = base()
    value["known_current_role_overlap"] = True
    assert mod.decide(value) == "F0_LINEAGE_OR_LICENSE_NO_GO"


def test_complete_identity_can_pass_stage1():
    mod = load()
    value = base()
    value["checkpoint"] = {"official_link": "x", "published_sha256": "a" * 64, "published_bytes": 1}
    assert mod.decide(value) == "STAGE_I_COMPATIBLE_PENDING_STAGE_IIA"


def test_source_has_no_network_client():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
    imported |= {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    assert not ({"requests", "urllib", "httpx"} & imported)


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print({"status": "PASS", "tests": len(tests)})
