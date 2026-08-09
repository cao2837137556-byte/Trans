"""Local contract tests for the CKCZ endpoint-pair diagnostic core."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckcz_endpoint_pair_conflict_diagnostic_v1 as ckcz  # noqa: E402


def joined_fixture() -> pd.DataFrame:
    rows = []
    specs = [
        (ckcz.GLOBAL, "future_query", "u0", 1.0, 1, 0, "attack-a", 1),
        (ckcz.GLOBAL, "future_query", "u1", 2.0, 1, 0, "attack-a", 1),
        (ckcz.GLOBAL, "future_query", "u2", 3.0, 0, 0, "attack-a", 1),
        (ckcz.GLOBAL, "future_query", "u3", 4.0, 1, 0, "attack-a", 1),
        ("iotsim-hydraulic-system", "ood_val", "u4", 1.5, 1, 0, "benign", 0),
        ("iotsim-hydraulic-system", "ood_val", "u5", 2.5, 1, 0, "benign", 0),
    ]
    for index, (held, role, uid, stamp, c1, m7, family, label) in enumerate(specs):
        rows.append(
            {
                "_row_id": index,
                "held_value": held,
                "uid": uid,
                "role": role,
                "source_group": "source-a",
                "device_family": "device-a",
                "attack_family": family,
                "label_metric_only": label,
                "c1_hard": bool(c1),
                ckcz.M7: bool(m7),
                "review": False,
                "cache_kind": "gotham",
                "target_index": index,
                "raw_source_path": "member-a.pcap",
                "feature_available_time_epoch": stamp,
                "target_event_position_within_capture": index,
                "src_local_id": 1,
                "dst_local_id": 2,
                "metadata_matched": True,
            }
        )
    missing = dict(rows[-1])
    missing.update(
        {
            "_row_id": len(rows), "uid": "ton:missing", "cache_kind": "missing",
            "target_index": pd.NA, "raw_source_path": np.nan,
            "feature_available_time_epoch": np.nan, "metadata_matched": False,
            "c1_hard": True, ckcz.M7: False,
        }
    )
    rows.append(missing)
    return pd.DataFrame(rows)


def run() -> dict[str, bool | str]:
    result: dict[str, bool | str] = {}
    joined = joined_fixture()
    state = ckcz.build_causal_pair_state(joined)
    global_rows = state.loc[state["held_value"].eq(ckcz.GLOBAL)].sort_values("uid")
    result["current_inclusive_conflict_count"] = global_rows[
        "pair_conflict_count_so_far"
    ].tolist() == [1.0, 2.0, 2.0, 3.0]
    result["consecutive_resets_on_nonconflict"] = global_rows[
        "pair_consecutive_conflicts_so_far"
    ].tolist() == [1.0, 2.0, 0.0, 1.0]
    result["span_only_on_current_conflict"] = global_rows[
        "pair_conflict_span_seconds_so_far"
    ].tolist() == [0.0, 1.0, 0.0, 3.0]
    hydraulic = state.loc[
        state["held_value"].eq("iotsim-hydraulic-system") & state["metadata_matched"]
    ].sort_values("uid")
    result["protocol_state_isolation"] = hydraulic[
        "pair_conflict_count_so_far"
    ].tolist() == [1.0, 2.0]
    missing = state.loc[state["uid"].eq("ton:missing")].iloc[0]
    result["missing_metadata_has_no_state"] = bool(
        not missing["state_available"]
        and pd.isna(missing["pair_conflict_count_so_far"])
        and not bool(missing[ckcz.M7])
    )

    relabeled = joined.copy()
    relabeled["label_metric_only"] = 1 - relabeled["label_metric_only"]
    relabeled["role"] = "changed-after-state"
    relabeled["attack_family"] = "changed"
    relabeled_state = ckcz.build_causal_pair_state(relabeled)
    result["state_is_label_and_role_invariant"] = bool(
        np.allclose(
            state[list(ckcz.SCALARS)].to_numpy(dtype=float),
            relabeled_state[list(ckcz.SCALARS)].to_numpy(dtype=float),
            equal_nan=True,
        )
    )

    member_split = joined.iloc[:2].copy()
    member_split.loc[member_split.index[1], "raw_source_path"] = "member-b.pcap"
    split_state = ckcz.build_causal_pair_state(member_split)
    result["pcap_member_is_in_interaction_key"] = split_state[
        "pair_conflict_count_so_far"
    ].tolist() == [1.0, 1.0]

    cuts = ckcz.exact_cuts(state, "pair_conflict_count_so_far")
    result["frontier_has_explicit_no_veto"] = bool(np.isinf(cuts[0]))
    result["frontier_values_descend"] = bool(np.all(np.diff(cuts[1:]) <= 0))

    try:
        ckcz.assert_no_final_text("safe/cooler-motor/cache.npz", "test")
        result["final_marker_fails_closed"] = False
    except RuntimeError:
        result["final_marker_fails_closed"] = True

    with tempfile.TemporaryDirectory(prefix="ckcz_contract_") as tmp:
        path = Path(tmp) / "mixed.csv"
        ckcz.atomic_csv(path, [{"a": 1}, {"a": 2, "b": 3}])
        readback = pd.read_csv(path)
        result["union_schema_survives_readback"] = bool(
            readback.columns.tolist() == ["a", "b"] and len(readback) == 2
        )

    result["status"] = "PASS" if all(bool(value) for value in result.values()) else "FAIL"
    return result


def main() -> None:
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    if result["status"] != "PASS":
        raise SystemExit("CKCZ contract tests failed")


if __name__ == "__main__":
    main()
