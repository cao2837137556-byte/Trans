#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path


SOURCE = Path(__file__).with_name("issue27data_f0_candidate1_metadata_audit_v1.py")


def load():
    spec = importlib.util.spec_from_file_location("data_f0", str(SOURCE))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def base():
    return {
        "official_raw_pcap_claim": True, "research_use_available": True,
        "known_lineage_contamination": False, "exact_member_inventory_published": False,
        "exact_victim_mapping_published": False, "paired_device_count": 0,
        "task_relevance_measurable": False,
    }


def test_python39_syntax():
    ast.parse(SOURCE.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_unknown_member_lineage_is_pending():
    mod = load()
    assert mod.decide(base()) == mod.PENDING


def test_pending_is_not_positive_pairing():
    mod = load()
    value = base()
    value["exact_member_inventory_published"] = True
    value["exact_victim_mapping_published"] = True
    assert mod.decide(value) == "NO_SAME_DEVICE_BENIGN_ATTACK_PAIRING"


def test_split_formula():
    mod = load()
    value = base()
    value.update({"exact_member_inventory_published": True, "exact_victim_mapping_published": True,
                  "paired_device_count": 8, "task_relevance_measurable": True})
    assert mod.decide(value) == "DATA_F0_METADATA_ELIGIBLE"


def test_candidate2_not_mentioned_by_network_code():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    imported = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
    imported |= {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    assert not ({"requests", "urllib", "httpx"} & imported)


if __name__ == "__main__":
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print({"status": "PASS", "tests": len(tests)})
