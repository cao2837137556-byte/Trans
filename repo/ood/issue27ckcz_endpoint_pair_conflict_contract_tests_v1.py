"""Local contract tests for the CKCZ endpoint-pair diagnostic core."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

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
    trigger = ckcz.first_trigger_audit(state, "pair_conflict_count_so_far", cuts)
    result["first_trigger_preceding_misses_are_causal"] = (
        trigger["preceding_conflict_misses"].tolist() == [0, 2, 1, 0]
    )
    result["time_to_first_veto_updates_at_exact_cuts"] = bool(
        np.isnan(trigger["mean_time_to_first_veto_seconds"][0])
        and trigger["mean_time_to_first_veto_seconds"][1:].tolist() == [3.0, 1.0, 0.0]
    )
    future_mask = (
        state["held_value"].eq(ckcz.GLOBAL) & state["role"].eq("future_query")
    ).to_numpy()
    boot, clusters = ckcz.bootstrap_curve_replicates(
        state, future_mask, "pair_conflict_count_so_far", cuts,
        "source", 40, ckcz.SEED,
    )
    expected_base = float(state.loc[future_mask, ckcz.M7].astype(bool).mean())
    result["source_bootstrap_covers_every_frontier_point"] = bool(
        boot.shape == (40, len(cuts)) and clusters == 1
        and np.allclose(boot[:, 0], expected_base)
        and np.all((boot >= 0.0) & (boot <= 1.0))
    )
    metric_rows = []
    for role in ckcz.ATTACK_ROLES:
        metric_rows.append(
            {
                "held_value": ckcz.GLOBAL, "role": role, "label_metric_only": 1,
                "attack_family": f"family-{role}", "source_group": f"source-{role}",
                "uid": f"uid-{role}", "interaction_key": f"pair-{role}",
                "state_available": True, "current_conflict": True, ckcz.M7: False,
                "c1_hard": True, "pair_conflict_count_so_far": 1.0,
            }
        )
    for protocol, role in ckcz.OOD_PROTOCOL_ROLE.items():
        metric_rows.append(
            {
                "held_value": protocol, "role": role, "label_metric_only": 0,
                "attack_family": "benign", "source_group": f"source-{protocol}",
                "uid": f"uid-{protocol}", "interaction_key": f"pair-{protocol}",
                "state_available": True, "current_conflict": True, ckcz.M7: False,
                "c1_hard": True, "pair_conflict_count_so_far": 1.0,
            }
        )
    interval_rows = list(
        ckcz.bootstrap_interval_rows(
            pd.DataFrame(metric_rows), "pair_conflict_count_so_far",
            np.asarray([np.inf, 1.0]), 20, ckcz.SEED,
        )
    )
    result["bootstrap_interval_schema_is_complete"] = bool(
        interval_rows
        and all("pool_cluster_counts" in row for row in interval_rows)
        and {row["cluster_unit"] for row in interval_rows} == {"source", "pair"}
    )

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

        oversized_path = Path(tmp) / "oversized.bin"
        try:
            ckcz.atomic_bytes(oversized_path, b"x" * (ckcz.ATOMIC_BYTES_MAX + 1))
            oversized_failed = False
        except RuntimeError:
            oversized_failed = True
        result["oversized_atomic_bytes_fail_closed"] = bool(
            oversized_failed and not oversized_path.exists()
        )

        large_path = Path(tmp) / "large.csv"
        large_rows = [
            {"row": index, "payload": "x" * 2048, **({"late_field": index} if index else {})}
            for index in range(5_000)
        ]
        original_atomic_bytes = ckcz.atomic_bytes
        atomic_bytes_called = False

        def reject_atomic_bytes(_path: Path, _payload: bytes) -> None:
            nonlocal atomic_bytes_called
            atomic_bytes_called = True
            raise AssertionError("large CSV regressed through atomic_bytes")

        ckcz.atomic_bytes = reject_atomic_bytes
        try:
            ckcz.atomic_csv(large_path, large_rows)
        finally:
            ckcz.atomic_bytes = original_atomic_bytes
        large_readback = pd.read_csv(large_path)
        leaked_large_temps = list(Path(tmp).glob(f".{large_path.name}.*"))
        result["large_csv_streams_without_atomic_bytes"] = bool(
            not atomic_bytes_called
            and large_path.stat().st_size > (8 << 20)
            and large_readback.columns.tolist() == ["row", "payload", "late_field"]
            and len(large_readback) == len(large_rows)
            and not leaked_large_temps
        )

        root = Path(tmp) / "ckbv"
        gotham_cache = root / "gotham_causal_cache"
        auxiliary_cache = root / "auxiliary_causal_cache"
        gotham_cache.mkdir(parents=True)
        auxiliary_cache.mkdir(parents=True)
        feature_names = np.asarray(["f0", "f1"])
        np.savez_compressed(
            gotham_cache / "g-key.npz",
            recorded_index=np.asarray([10, 11], dtype=np.int64),
            feature_available_time_epoch=np.asarray([1.0, 2.0]),
            target_event_position_within_capture=np.asarray([5, 6], dtype=np.int64),
            src_local_id=np.asarray([1, 1], dtype=np.int32),
            dst_local_id=np.asarray([2, 2], dtype=np.int32),
            causal_features=np.zeros((2, 2), dtype=np.float32),
            feature_names=feature_names,
            raw_source_path=np.asarray(["g-member.pcap", "g-member.pcap"]),
        )
        np.savez_compressed(
            auxiliary_cache / "a-key.npz",
            target_row=np.asarray([0], dtype=np.int64),
            feature_available_time_epoch=np.asarray([3.0]),
            target_event_position_within_capture=np.asarray([7], dtype=np.int64),
            src_local_id=np.asarray([3], dtype=np.int32),
            dst_local_id=np.asarray([4], dtype=np.int32),
            causal_features=np.zeros((1, 2), dtype=np.float32),
            feature_names=feature_names,
            raw_source_path=np.asarray("a-member.pcap"),
        )
        lineage_path = Path(tmp) / "ckby_lineage_snapshot.npz"
        np.savez_compressed(
            lineage_path,
            uid=np.asarray(["future_query:report:0", "future_query:report:1"]),
            x=np.zeros((2, 2), dtype=np.float32),
            role=np.asarray(["future_query", "future_query"]),
            m1_phase=np.asarray(["report", "report"]),
            source=np.asarray(["g-source", "g-source"]),
            device_family=np.asarray(["device", "device"]),
            attack_family=np.asarray(["family", "family"]),
            label=np.ones(2, dtype=np.int8),
            recorded_index=np.asarray([10, 11], dtype=np.int64),
            raw51_observable=np.ones(2, dtype=bool),
            global_pool=np.asarray(["report-only", "report-only"]),
            feature_names=feature_names,
        )
        g_allow = pd.DataFrame(
            [{
                "source_group": "g-source", "source_cache_key": "g-key", "target_rows": 2,
                "cache_sha256": ckcz.sha256_file(gotham_cache / "g-key.npz"),
            }]
        )
        a_allow = pd.DataFrame(
            [{
                "source_group": "a-source", "source_cache_key": "a-key", "target_rows": 1,
                "cache_sha256": ckcz.sha256_file(auxiliary_cache / "a-key.npz"),
            }]
        )
        g_manifest = root / "ckbu_gotham_unified_causal_manifest.csv"
        a_manifest = root / "ckbu_auxiliary_unified_causal_manifest.csv"
        g_allow.to_csv(g_manifest, index=False, lineterminator="\n")
        a_allow.to_csv(a_manifest, index=False, lineterminator="\n")
        checked_g = ckcz.validate_manifest(
            g_manifest, ckcz.sha256_file(g_manifest), g_allow, "gotham", 1, 2
        )
        checked_a = ckcz.validate_manifest(
            a_manifest, ckcz.sha256_file(a_manifest), a_allow, "auxiliary", 1, 1
        )
        g_meta, _ = ckcz.export_cache_metadata(root, checked_g, "gotham")
        a_meta, _ = ckcz.export_cache_metadata(root, checked_a, "auxiliary")
        lineage, lineage_audit = ckcz.load_gotham_lineage(
            lineage_path, ckcz.sha256_file(lineage_path), 2
        )
        result["gotham_and_scalar_aux_metadata_export"] = bool(
            len(g_meta) == 2 and len(a_meta) == 1
            and a_meta.iloc[0]["raw_source_path"] == "a-member.pcap"
        )
        prediction_fixture = pd.DataFrame(
            [
                {"held_value": ckcz.GLOBAL, "uid": "future_query:report:0", "role": "future_query",
                 "phase": "report", "source_group": "g-source"},
                {"held_value": "iotsim-predictive-maintenance",
                 "uid": "aux:aux_report:a-source:0", "role": "aux_report", "phase": "report",
                 "source_group": "a-source"},
                {"held_value": ckcz.GLOBAL, "uid": "ton:ton_normal:normal_2:1",
                 "role": "aux_normal_select", "phase": "select", "source_group": "normal_2.pcap"},
            ]
        )
        joined_meta, audit = ckcz.join_predictions(
            prediction_fixture, pd.concat([g_meta, a_meta], ignore_index=True), lineage
        )
        result["exact_lineage_join_with_nonindex_uid_suffix"] = bool(
            joined_meta["metadata_matched"].tolist() == [True, True, False]
            and sum(int(row["unexpected_unmatched"]) for row in audit) == 0
            and int(joined_meta.iloc[0]["target_index"]) == 10
            and lineage_audit["forbidden_arrays_read"] == []
        )

        g_allow_path = Path(tmp) / "g_allow.csv"
        a_allow_path = Path(tmp) / "a_allow.csv"
        g_allow[["source_group"]].to_csv(g_allow_path, index=False, lineterminator="\n")
        a_allow[["source_group"]].to_csv(a_allow_path, index=False, lineterminator="\n")
        predictions = []
        families = [f"family-{index:02d}" for index in range(16)]
        attack_roles = ["support_val", "same_file_query", "sealed_final_attack"] + [
            "future_query"
        ] * 13
        for index, (family, role) in enumerate(zip(families, attack_roles)):
            predictions.append(
                {
                    "held_value": ckcz.GLOBAL,
                    "uid": f"ton:synthetic:attack:{index}",
                    "role": role,
                    "phase": "select" if role == "support_val" else "report",
                    "source_group": "normal_2.pcap",
                    "device_family": "synthetic-device",
                    "attack_family": family,
                    "label_metric_only": 1,
                    "c1_hard": True,
                    ckcz.M7: role == "support_val",
                    "review": False,
                }
            )
        for index, (protocol, role) in enumerate(ckcz.OOD_PROTOCOL_ROLE.items()):
            predictions.append(
                {
                    "held_value": protocol,
                    "uid": f"ton:synthetic:ood:{index}",
                    "role": role,
                    "phase": "report",
                    "source_group": "normal_2.pcap",
                    "device_family": protocol,
                    "attack_family": "benign",
                    "label_metric_only": 0,
                    "c1_hard": True,
                    ckcz.M7: False,
                    "review": False,
                }
            )
        prediction_path = Path(tmp) / "predictions.csv.gz"
        prediction_frame = pd.DataFrame(predictions)
        prediction_frame.to_csv(prediction_path, index=False, compression="gzip")
        protocol_path = Path(tmp) / "frozen.md"
        protocol_path.write_text("synthetic frozen protocol\n", encoding="utf-8")
        erratum_path = Path(tmp) / "erratum.md"
        erratum_path.write_text("synthetic frozen lineage erratum\n", encoding="utf-8")
        old_counts = ckcz.EXPECTED_PROTOCOL_ROWS
        ckcz.EXPECTED_PROTOCOL_ROWS = prediction_frame.groupby("held_value").size().to_dict()
        run_args = SimpleNamespace(
            ckbv_root=root,
            predictions=prediction_path,
            gotham_lineage_snapshot=lineage_path,
            gotham_lineage_snapshot_sha256=ckcz.sha256_file(lineage_path),
            gotham_lineage_rows=2,
            gotham_allowlist=g_allow_path,
            auxiliary_allowlist=a_allow_path,
            gotham_allowlist_sha256=ckcz.sha256_file(g_allow_path),
            auxiliary_allowlist_sha256=ckcz.sha256_file(a_allow_path),
            gotham_manifest_sha256=ckcz.sha256_file(g_manifest),
            auxiliary_manifest_sha256=ckcz.sha256_file(a_manifest),
            predictions_sha256=ckcz.sha256_file(prediction_path),
            gotham_sources=1,
            gotham_rows=2,
            auxiliary_sources=1,
            auxiliary_rows=1,
            seed=ckcz.SEED,
            bootstrap_reps=20,
            preregistered_protocol=protocol_path,
            preregistered_protocol_sha256=ckcz.sha256_file(protocol_path),
            preregistered_erratum=erratum_path,
            preregistered_erratum_sha256=ckcz.sha256_file(erratum_path),
            progress_file=Path(tmp) / "progress.json",
            out=Path(tmp) / "out",
        )
        try:
            verdict = ckcz.run(run_args)
        finally:
            ckcz.EXPECTED_PROTOCOL_ROWS = old_counts
        out = Path(run_args.out)
        progress = json.loads(Path(run_args.progress_file).read_text(encoding="utf-8"))
        result["full_synthetic_pipeline_is_terminal_and_hashed"] = bool(
            verdict["bootstrap_complete"]
            and verdict["scientific_verdict_valid"]
            and (out / "SHA256SUMS").is_file()
            and not (out / "job_failure.txt").exists()
            and len(pd.read_csv(out / "ckcz_bootstrap_intervals.csv")) == 48
        )
        result["node_local_progress_reaches_complete"] = bool(
            progress["stage"] == "complete"
            and progress["sequence"] > 1
            and progress["output_files"] > 1
        )
        bad_args = SimpleNamespace(**vars(run_args))
        bad_args.out = Path(tmp) / "failure-out"
        bad_args.progress_file = Path(tmp) / "failure-progress.json"
        bad_args.preregistered_protocol_sha256 = "0" * 64
        try:
            ckcz.run(bad_args)
            failed_closed = False
        except RuntimeError:
            failed_closed = True
        result["engineering_failure_has_no_scientific_verdict"] = bool(
            failed_closed
            and (Path(bad_args.out) / "job_failure.txt").is_file()
            and not (Path(bad_args.out) / "ckcz_verdict.json").exists()
            and json.loads(Path(bad_args.progress_file).read_text(encoding="utf-8"))["stage"]
            == "engineering_failure"
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
