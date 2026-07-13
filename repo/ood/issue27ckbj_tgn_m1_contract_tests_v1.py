"""Repeatable local contract tests for the corrected formal M1 implementation."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckbj_c1_report_only_cache_extension_v1 as c1ext  # noqa: E402
import issue27ckbj_tgn_m1_strict_formal_v2 as formal  # noqa: E402


def record(uid: str, label: int, family: str, c1_score: float) -> formal.Record:
    return formal.Record(
        uid=uid, role="support_val" if label else "ood_val", m1_phase="select",
        source="synthetic-source", recorded_index=0, event_position=0,
        label=label, attack_family=family, device_family="synthetic-family",
        source_family="synthetic-family", c1_score=c1_score, episode_id="episode-0",
    )


def run(seed: int) -> dict[str, object]:
    results: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="ckbj_contract_") as tmp:
        formal.run_unit(argparse.Namespace(seed=int(seed), out=tmp))
        unit = json.loads((Path(tmp) / "m1_unit_smoke.json").read_text(encoding="utf-8"))
    results["pyg_causal_unit"] = unit["status"] == "PASS"

    stamp = np.arange(5, dtype=np.int64) * 1000
    src = np.asarray([0, 9, 1, 9, 0], dtype=np.int64)
    dst = np.asarray([1, 9, 0, 9, 1], dtype=np.int64)
    message = np.zeros((5, formal.RAW_MSG_DIM), dtype=np.float32)
    fit_positions = {0, 2, 4}
    baseline = formal.future_task_labels(stamp, src, dst, message, fit_positions)
    changed_src = src.copy(); changed_dst = dst.copy()
    changed_src[1], changed_dst[1] = 1, 0  # non-fit event only
    changed = formal.future_task_labels(stamp, changed_src, changed_dst, message, fit_positions)
    results["fit_future_label_ignores_nonfit_event"] = baseline == changed

    negative, pool = formal.sample_negative(0, 1, {0, 1, 2}, set(), np.random.default_rng(seed))
    no_negative, empty_pool = formal.sample_negative(0, 1, {0, 1}, set(), np.random.default_rng(seed))
    results["negative_from_past_seen_source_only"] = negative == 2 and pool == 1
    results["negative_skips_empty_legal_pool"] = no_negative is None and empty_pool == 0

    attack = [record(f"attack-{index}", 1, "family-a", 0.99) for index in range(4)]
    benign = [record(f"benign-{index}", 0, "benign", 0.99) for index in range(4)]
    scores = {item.uid: (0.1 if item.label else 0.9) for item in attack + benign}
    _threshold, rows, gate_pass = formal.choose_gate("M1-SSL", attack, benign, scores, 0.5)
    results["gate_constraint_failure_is_fail_closed"] = bool(
        not gate_pass and any(row.get("selected_despite_constraint_failure") for row in rows)
    )

    false_column = pd.Series([False, False])
    true_column = pd.Series([True, True])
    results["raw_label_false_parses_as_false"] = bool(not formal.bool_series(false_column).any())
    results["positive_contract_field_parses_as_true"] = bool(formal.bool_series(true_column).all())

    base = formal.DEFAULT_C1_PLAN.parent
    base_audit = c1ext.validate_base_contract(
        base / "canonical_source_load_plan.csv", base / "canonical_source_target_index.csv",
    )
    results["frozen_c1_26_sources"] = base_audit["base_c1_sources"] == 26
    results["frozen_c1_34622_targets"] = base_audit["base_c1_targets"] == 34622
    results["status"] = "PASS" if all(bool(value) for value in results.values()) else "FAIL"
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=27)
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = run(int(args.seed))
    if args.out:
        out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if result["status"] != "PASS":
        raise SystemExit("CKBJ contract tests failed")


if __name__ == "__main__":
    main()
