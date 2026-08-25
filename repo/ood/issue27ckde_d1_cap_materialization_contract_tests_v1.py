#!/usr/bin/env python3
"""Contract tests for CKDE D1 Stage-P cap materialization (Python 3.9)."""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("issue27ckde_d1_cap_materialization_v1.py")
SPEC = importlib.util.spec_from_file_location("ckde_cap", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load cap materializer")
cap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cap)


def expect_failure(fn, text: str) -> None:
    try:
        fn()
    except Exception as exc:
        assert text in str(exc), (text, str(exc))
    else:
        raise AssertionError("expected failure containing %r" % text)


def test_ties_are_hard() -> None:
    values = np.asarray([0.1, 0.2, 0.2, 0.3], dtype=float)
    assert cap.hard_count(np.sort(values), 0.2) == 3


def test_candidates_and_largest_admissible() -> None:
    scores = np.asarray([0.9] * 20 + [0.8] * 20 + [0.7] * 20, dtype=float)
    families = ["File Download"] * 20 + ["Ingress Tool Transfer"] * 20 + ["Reporting"] * 20
    frontier, family_rows, verdict = cap.build_frontier(scores, families, theta_0=0.5)
    assert frontier[0]["threshold"] == "0.5"
    assert verdict["T_cap"] == 0.7
    assert len(family_rows) == len(frontier) * 3
    assert verdict["T_cap_global_recall_loss_pp"] == 0.0


def test_global_gate_can_bind() -> None:
    scores = np.linspace(0.5, 1.0, 1000)
    families = ["ToN-credential_bruteforce"] * 1000
    _, _, verdict = cap.build_frontier(scores, families, theta_0=0.5)
    assert verdict["T_cap_global_recall_loss_pp"] <= 0.5 + 1e-12


def test_family_gate_can_bind() -> None:
    scores = np.asarray([0.51] + [0.9] * 49 + [0.8] * 50, dtype=float)
    families = ["File Download"] * 50 + ["Ingress Tool Transfer"] * 50
    _, _, verdict = cap.build_frontier(scores, families, theta_0=0.5)
    assert verdict["T_cap"] == 0.51


def test_under_15_family_is_reported_not_gated() -> None:
    scores = np.asarray([0.51] * 14 + [0.9] * 1000, dtype=float)
    families = ["Mirai C&C Communication"] * 14 + ["ToN-reconnaissance_scan"] * 1000
    _, rows, verdict = cap.build_frontier(scores, families, theta_0=0.5)
    under = [r for r in rows if r["attack_family"] == "Mirai C&C Communication"]
    assert under and {r["gate_eligible_rows_ge_15"] for r in under} == {"false"}
    assert verdict["T_cap"] >= 0.5


def test_ton_strata_remain_exact_unmapped() -> None:
    scores = np.asarray([0.8] * 30, dtype=float)
    families = ["ToN-credential_bruteforce"] * 15 + ["ToN-reconnaissance_scan"] * 15
    _, rows, _ = cap.build_frontier(scores, families, theta_0=0.5)
    scopes = {r["family_scope"] for r in rows}
    assert scopes == {"CKBW_TON_FIT_STRATUM_EXACT_NO_MAPPING"}


def test_unknown_family_fails_closed() -> None:
    expect_failure(
        lambda: cap.build_frontier(np.asarray([0.8]), ["invented-family"], theta_0=0.5),
        "unfrozen fit family",
    )


def test_nonfinite_score_fails_closed() -> None:
    expect_failure(
        lambda: cap.build_frontier(
            np.asarray([math.nan]), ["File Download"], theta_0=0.5
        ),
        "finite scores",
    )


def test_frozen_p2_shape_and_missing_semantics() -> None:
    state = {
        "normalizer_mean": np.zeros(768),
        "normalizer_scale": np.ones(768),
        "p2__0.weight": np.zeros((128, 769)),
        "p2__0.bias": np.ones(128),
        "p2__3.weight": np.ones((1, 128)),
        "p2__3.bias": np.zeros(1),
    }
    reps = np.vstack((np.ones(768), np.full(768, 100.0))).astype(np.float32)
    scores = cap.frozen_p2_scores(reps, np.asarray([False, True]), state)
    assert scores.shape == (2,)
    assert np.isfinite(scores).all()
    assert scores[0] == scores[1]


def test_canonical_float_is_stable() -> None:
    assert cap.canonical_float(0.065159872174263) == "0.065159872174263"


def main() -> None:
    tests = [value for name, value in sorted(globals().items()) if name.startswith("test_")]
    for test in tests:
        test()
    print("CKDE_D1_CAP_CONTRACT_TESTS_PASS tests=%d python39_compatible=true" % len(tests))


if __name__ == "__main__":
    main()
