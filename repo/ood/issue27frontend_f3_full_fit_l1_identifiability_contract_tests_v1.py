#!/usr/bin/env python3
"""Synthetic contract tests for the Frontend-F3 full-fit L1 audit."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace


HERE = Path(__file__).resolve().parent


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def main() -> int:
    subject = load("f3b_subject", HERE / "issue27frontend_f3_full_fit_l1_identifiability_v1.py")
    f3 = load("f3_subject_for_tests", HERE / "issue27frontend_f3_conflict_field_sufficiency_v1.py")
    tests = []

    raw = {"frame.len": "70", "tcp.flags": "0x0018", "tcp.len": "4", "udp.length": ""}
    event = SimpleNamespace(ip_protocol=6)
    signature = subject.l1_signature(f3, "BASE", raw, event, 40e-6)
    tests.append(("l1_exact_shape", "FRAME_LEN=70" in signature and "TRANSPORT_LEN=4" in signature and "TCP_FLAGS=24" in signature))
    tests.append(("l1_no_port_or_ttl", "SRC_PORT" not in signature and "DST_PORT" not in signature and "TTL_BUCKET" not in signature))

    contexts = [
        {"source_group": "attack_a", "signatures": ["a"], "targets": [{"label": 1}]},
        {"source_group": "attack_b", "signatures": ["b"], "targets": [{"label": 1}]},
        {"source_group": "benign_a", "signatures": ["c"], "targets": [{"label": 0}]},
        {"source_group": "benign_b", "signatures": ["d"], "targets": [{"label": 0}]},
    ]
    split1 = subject.source_split(contexts)
    split2 = subject.source_split(list(reversed(contexts)))
    tests.append(("split_deterministic", split1 == split2 and set(split1) == {"attack_a", "attack_b", "benign_a", "benign_b"}))
    tests.append(("split_holds_each_stratum", any(split1[x] == "internal_val" for x in ("attack_a", "attack_b")) and any(split1[x] == "internal_val" for x in ("benign_a", "benign_b"))))

    vocab_contexts = [
        {"source_group": "train", "signatures": ["known"], "targets": []},
        {"source_group": "val", "signatures": ["forbidden_val_only"], "targets": []},
    ]
    vocabulary, ordered = subject.build_vocabulary(vocab_contexts, {"train": "train", "val": "internal_val"})
    tests.append(("vocabulary_train_only", ordered == ["known"] and "forbidden_val_only" not in vocabulary))

    rows = [
        {"uid": "n", "label": 0, "l1_prefix_sha": "x", "token_prefix_sha": "u", "nested_split": "train", "source_group": "s1", "owner": "A", "teacher_kind": "benign_normal", "attack_family": "benign"},
        {"uid": "a", "label": 1, "l1_prefix_sha": "x", "token_prefix_sha": "v", "nested_split": "train", "source_group": "s2", "owner": "A", "teacher_kind": "attack_hard", "attack_family": "attack"},
    ]
    canonical_count, canonical_members = subject.collision_rows(rows, "l1_prefix_sha")
    token_count, _ = subject.collision_rows(rows, "token_prefix_sha")
    tests.append(("canonical_conflict_detected", canonical_count == 1 and len(canonical_members) == 2))
    tests.append(("token_separation_detected", token_count == 0))

    failures = [name for name, passed in tests if not passed]
    for name, passed in tests:
        print("%s %s" % ("PASS" if passed else "FAIL", name))
    print("SUMMARY %d/%d PASS" % (len(tests) - len(failures), len(tests)))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
