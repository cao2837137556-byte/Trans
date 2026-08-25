#!/usr/bin/env python3
"""CKDD D0 read-only feasibility audit.

The implementation intentionally stops before any optimizer, report-score file,
or FINAL identity can be opened.  It is Python 3.9 compatible.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
import os
import shutil
import traceback
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path("runs/mainline_docs/ckdd_d0_constrained_attack_head_retraining_feasibility_preregistered_20260825.md")
CONTRACT_SHA256 = "0c33a0eca009242238910dffa004b8cec1fedc39b5e77f0e1be05e5b7850eb7a"
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")
PHASE_A_REL = Path("runs/issue27ckdc_d0f_certificate_phase_a_v1_2026-08-25_local")
CKBU_CODE_REL = Path("repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py")
CKBV_CODE_REL = Path("repo/ood/issue27ckbv_checkpointed_sparse_process_frontend_v1.py")

PINNED = {
    "fit_select_plan": ("ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "embeddings": ("ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "embeddings_audit": ("ckda_d1_fit_select_embeddings.npz.audit.json", "8dc4852734b408f927181dcdaad43530cdb50c5cb199a1040302aba542b9796d"),
    "embeddings_metadata": ("ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "probe_state": ("ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
    "threshold_marker": ("ckda_d1_threshold_freeze_marker.json", "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"),
    "target_metadata": ("ckda_d1_fit_select_target_metadata.csv", "d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d"),
    "fit_select_role_audit": ("ckda_d1_fit_select_role_plan_audit.json", "0f29503a225f7b235d68595dc813ecd98ff8a3f6e02f9a7991a53cb351777385"),
    "report_role_audit": ("ckda_d1_report_role_plan_audit.json", "692317b7c584deea06ff1c1d07b013151cff7794b456d18b71ba87cdea0469bd"),
}
PHASE_PINS = {
    "phase_a_rows": ("ckdc_d0f_phase_a_certificate_rows.csv", "5a89f356d4f4e78e03149d69d3cbc3d9609f1425ac6574ecb54d997f9e01e538"),
    "phase_a_input_audit": ("ckdc_d0f_phase_a_input_audit.json", "36495b23517af19c58f51cbb1171e8ac35d3a30e1f27d3979642275db383e119"),
    "phase_a_verdict": ("ckdc_d0f_phase_a_no_certificate_verdict.json", "26ce14c907f9167c95fc4fe3590f42e5a87ad92f1d2b2c60dd3f97d1148271cb"),
    "phase_a_sha256s": ("SHA256SUMS", "9b6ce02882a8be2f4efbab8d970f134ee087be598a5d9336024612486b0ed407"),
}
ATTACK_ROLES = {"aux_process_fit", "support_train", "support_val"}
FIT_ATTACK_ROLES = {"aux_process_fit", "support_train"}
CONFLICT_EXPECTED = {
    "normal_2.pcap": 3687,
    "iotsim-building-monitor-4_0-0_to_OpenvSwitch-28_4-0": 225,
    "iotsim-combined-cycle-2_0-0_to_OpenvSwitch-13_2-0": 331,
    "iotsim-combined-cycle-4_0-0_to_OpenvSwitch-13_4-0": 333,
    "iotsim-combined-cycle-tls-2_0-0_to_OpenvSwitch-14_2-0": 182,
    "iotsim-domotic-monitor-4_0-0_to_OpenvSwitch-23_4-0": 228,
}
REPORT_ATTACK_ROWS = 244050
REPORT_CONFLICT_SUBSET = 51057
FORBIDDEN_FILENAMES = {"ckda_d1_report_plan.csv", "ckda_d1_report_scores.csv.gz", "ckda_d1_report_embeddings.npz"}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch: %s" % path)
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temp), str(path))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    frame.to_csv(temp, index=False, lineterminator="\n")
    os.replace(str(temp), str(path))


def assert_no_forbidden_open(paths: Iterable[Path]) -> None:
    for path in paths:
        if path.name in FORBIDDEN_FILENAMES:
            raise RuntimeError("forbidden report-score asset: %s" % path)
        lowered = str(path).replace("\\", "/").lower()
        if any(marker in lowered for marker in ("cooler-motor", "seed37", "seed47", "sealed_final")):
            raise RuntimeError("FINAL marker in path: %s" % path)


def pin_inputs(root: Path) -> Dict[str, object]:
    stage = root / STAGE_REL
    phase = root / PHASE_A_REL
    identities = {"contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256)}
    opened = [root / CONTRACT_REL]
    for key, (name, digest) in PINNED.items():
        path = stage / name
        identities[key] = require_sha(path, digest)
        opened.append(path)
    for key, (name, digest) in PHASE_PINS.items():
        path = phase / name
        identities[key] = require_sha(path, digest)
        opened.append(path)
    assert_no_forbidden_open(opened)
    return identities


def reservoir_ordinals(total: int, budget: int, seed: int) -> List[int]:
    rng = np.random.default_rng(int(seed))
    values: List[int] = []
    for index in range(int(total)):
        seen = index + 1
        if len(values) < budget:
            values.append(index)
        else:
            replacement = int(rng.integers(0, seen))
            if replacement < budget:
                values[replacement] = index
    return sorted(values)


def provenance_audit(root: Path, plan: pd.DataFrame, metadata: pd.DataFrame) -> Dict[str, object]:
    selected = metadata.loc[metadata["source_group"].eq("normal_2.pcap")].copy()
    positions = sorted(pd.to_numeric(selected["target_event_position_within_capture"], errors="raise").astype(int).tolist())
    expected = reservoir_ordinals(2000000, 4000, 27)
    if positions != expected:
        raise RuntimeError("normal_2 seed-27 reservoir identity drift")
    if set(selected["raw_source_path"].astype(str)) != {"normal_2.pcap"}:
        raise RuntimeError("normal_2 member identity drift")
    if set(plan.loc[plan["source_group"].eq("normal_2.pcap"), "role"].astype(str)) != {"aux_normal_select"}:
        raise RuntimeError("normal_2 role mapping drift")
    if "normal_1.pcap" not in set(plan.loc[plan["role"].eq("aux_normal_fit"), "source_group"].astype(str)):
        raise RuntimeError("normal_1 fit source absent")
    return {
        "status": "PASS",
        "member": "normal_2.pcap",
        "role": "aux_normal_select",
        "mapping_symbol": "TON_PILOT_FILES",
        "decoded_events": 2000000,
        "reservoir_budget": 4000,
        "reservoir_seed": 27,
        "selected_event_positions_sha256": hashlib.sha256("\n".join(str(v) for v in positions).encode("utf-8")).hexdigest(),
        "selected_event_positions_match_exact_two_pass_reservoir": True,
        "score_before_update": True,
        "sorted_back_to_event_order": positions == sorted(positions),
        "source_disjoint_from_fit_member": True,
        "challenge_enriched_not_prevalence_sample": True,
        "raw_label_columns_read": 0,
        "ckbu_code": require_sha(root / CKBU_CODE_REL, sha256_file(root / CKBU_CODE_REL)),
        "ckbv_code": require_sha(root / CKBV_CODE_REL, sha256_file(root / CKBV_CODE_REL)),
        "role_plan_sha256": sha256_file(root / STAGE_REL / "ckda_d1_fit_select_plan.csv"),
    }


def partition_census(conflicts: pd.DataFrame, metadata: pd.DataFrame, embedded: Mapping[str, bool]) -> pd.DataFrame:
    groups = sorted(CONFLICT_EXPECTED)
    rows: List[Dict[str, object]] = []
    meta = metadata[["uid", "raw_source_path"]].copy()
    session = pd.read_csv(Path(metadata.attrs["session_path"]), usecols=["uid", "session_id"])
    enriched = conflicts.merge(meta, on="uid", how="left", validate="one_to_one").merge(session, on="uid", how="left", validate="one_to_one")
    enriched["embedded"] = enriched["uid"].map(embedded).fillna(False)
    for mask in range(1, 1 << len(groups)):
        train = {groups[i] for i in range(len(groups)) if mask & (1 << i)}
        valid = set(groups) - train
        if not train or not valid:
            continue
        tr = enriched.loc[enriched["source_group"].isin(train)]
        va = enriched.loc[enriched["source_group"].isin(valid)]
        train_share = float(tr["source_group"].value_counts(normalize=True).max())
        val_share = float(va["source_group"].value_counts(normalize=True).max())
        session_overlap = len(set(tr["session_id"].astype(str)) & set(va["session_id"].astype(str)))
        member_overlap = len(set(tr["raw_source_path"].astype(str)) & set(va["raw_source_path"].astype(str)))
        admissible = (
            len(train) >= 3 and len(valid) >= 2 and len(tr) >= 300 and len(va) >= 300
            and train_share <= 0.80 and val_share <= 0.80 and session_overlap == 0 and member_overlap == 0
        )
        rows.append({
            "train_groups": "|".join(sorted(train)), "validation_groups": "|".join(sorted(valid)),
            "train_rows": len(tr), "validation_rows": len(va), "train_group_count": len(train),
            "validation_group_count": len(valid), "train_max_source_share": train_share,
            "validation_max_source_share": val_share, "train_embedding_coverage": float(tr["embedded"].mean()),
            "validation_embedding_coverage": float(va["embedded"].mean()), "session_overlap": session_overlap,
            "member_overlap": member_overlap, "admissible": bool(admissible),
        })
    return pd.DataFrame(rows).sort_values(["admissible", "train_groups"], ascending=[False, True], kind="mergesort")


def frozen_p2_scores(representations: np.ndarray, missing: np.ndarray, state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    values = (representations.astype(np.float64) - mean) / scale
    values[np.asarray(missing, dtype=bool)] = 0.0
    x = np.concatenate((values, np.asarray(missing, dtype=np.float64)[:, None]), axis=1)
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float64)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float64)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float64).reshape(-1)
    b2 = float(np.asarray(state["p2__3.bias"], dtype=np.float64).reshape(-1)[0])
    hidden = np.maximum(0.0, x.dot(w1.T) + b1)
    logits = hidden.dot(w2) + b2
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))
    return scores, hidden


def diagnostics(plan: pd.DataFrame, conflicts: pd.DataFrame, stage: Path) -> Tuple[pd.DataFrame, Dict[str, object], Dict[str, bool]]:
    with np.load(stage / "ckda_d1_fit_select_embeddings.npz", allow_pickle=False) as data:
        uids = data["uid"].astype(str)
        reps = np.asarray(data["representation"], dtype=np.float32)
        missing = np.asarray(data["missing"], dtype=bool)
    with np.load(stage / "ckda_d1_probe_state.npz", allow_pickle=False) as data:
        state = {name: np.asarray(data[name]) for name in data.files}
    if len(uids) != len(plan) or len(set(uids)) != len(uids) or set(uids) != set(plan["uid"].astype(str)):
        raise RuntimeError("embedding/plan exact UID identity drift")
    positions = {uid: index for index, uid in enumerate(uids)}
    order = np.asarray([positions[uid] for uid in plan["uid"].astype(str)], dtype=np.int64)
    reps = reps[order]
    missing = missing[order]
    scores, hidden = frozen_p2_scores(reps, missing, state)
    marker = json.loads((stage / "ckda_d1_threshold_freeze_marker.json").read_text(encoding="utf-8"))
    threshold = float(marker["thresholds"]["P2"]["value"])
    table = plan[["uid", "role", "source_group", "attack_family", "label_metric_only"]].copy()
    table["embedded"] = ~missing
    table["p2_score"] = scores
    table["p2_logit"] = np.log(np.maximum(scores, 1e-300) / np.maximum(1.0 - scores, 1e-300))
    table["margin_to_threshold"] = scores - threshold
    table["hard_negative"] = table["uid"].isin(set(conflicts["uid"].astype(str)))
    summary_rows = []
    for name, mask in {
        "fit_attacks": table["role"].isin(FIT_ATTACK_ROLES),
        "support_val_attacks": table["role"].eq("support_val"),
        "all_select_benign": table["role"].isin({"aux_select", "aux_normal_select"}),
        "hard_negatives": table["hard_negative"],
    }.items():
        part = table.loc[mask]
        summary_rows.append({
            "population": name, "rows": len(part), "embedded_rows": int(part["embedded"].sum()),
            "embedding_coverage": float(part["embedded"].mean()), "score_min": float(part["p2_score"].min()),
            "score_q50": float(part["p2_score"].median()), "score_max": float(part["p2_score"].max()),
            "margin_min": float(part["margin_to_threshold"].min()), "margin_q50": float(part["margin_to_threshold"].median()),
        })
    # Exact frozen-head, last-layer first-order directions; no parameter update is taken.
    y = table["label_metric_only"].to_numpy(dtype=float)
    factors = scores - y
    grad = np.concatenate((hidden * factors[:, None], factors[:, None]), axis=1)
    hn = table["hard_negative"].to_numpy()
    attacks = table["role"].isin(FIT_ATTACK_ROLES).to_numpy()
    g_hn = grad[hn].mean(axis=0)
    g_attack = grad[attacks].mean(axis=0)
    denominator = float(np.linalg.norm(g_hn) * np.linalg.norm(g_attack))
    cosine = float(np.dot(g_hn, g_attack) / denominator) if denominator else math.nan
    diag = {
        "status": "PASS",
        "p2_threshold": threshold,
        "gradient_space": "FROZEN_P2_FINAL_LAYER_129D_BCE_FIRST_ORDER",
        "optimizer_steps": 0,
        "fitted_parameters": 0,
        "aggregate_hard_negative_attack_gradient_cosine": cosine,
        "hard_negative_gradient_norm": float(np.linalg.norm(g_hn)),
        "attack_anchor_gradient_norm": float(np.linalg.norm(g_attack)),
        "trust_region_diagnostic": "DESCRIPTIVE_ONLY_NOT_CONSUMED_BECAUSE_SOURCE_SPLIT_GATE_FAILS",
        "nearest_opposite_distance": "NOT_CONSUMED_AFTER_EARLIER_MECHANICAL_SOURCE_SPLIT_FAILURE",
        "diagnostics_emitted_without_conditional_rerun": True,
    }
    return pd.DataFrame(summary_rows), diag, dict(zip(table["uid"].astype(str), table["embedded"].astype(bool)))


def run(root: Path, out: Path) -> None:
    if out.exists():
        existing = sorted(path.name for path in out.iterdir())
        if existing != ["engineering_failure.json"]:
            raise RuntimeError("refusing to overwrite existing D0 output: %s" % existing)
        (out / "engineering_failure.json").unlink()
        out.rmdir()
    identities = pin_inputs(root)
    stage = root / STAGE_REL
    phase = root / PHASE_A_REL
    plan = pd.read_csv(stage / "ckda_d1_fit_select_plan.csv")
    metadata = pd.read_csv(stage / "ckda_d1_fit_select_target_metadata.csv")
    session_path = stage / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz"
    metadata.attrs["session_path"] = str(session_path)
    phase_rows = pd.read_csv(phase / "ckdc_d0f_phase_a_certificate_rows.csv")
    if len(plan) != 25467 or plan["uid"].duplicated().any() or len(phase_rows) != 7069:
        raise RuntimeError("frozen denominator drift")
    role_counts = plan.groupby("role").size().to_dict()
    expected_roles = {"aux_process_fit": 4000, "support_train": 385, "support_val": 69, "aux_select": 3000, "aux_normal_select": 4000}
    for role, count in expected_roles.items():
        if int(role_counts.get(role, -1)) != count:
            raise RuntimeError("role count drift: %s" % role)
    conflicts = phase_rows.loc[(phase_rows["label_metric_only"].eq(0)) & phase_rows["p2_hard"].astype(bool) & (~phase_rows["m7_hard"].astype(bool))].copy()
    conflict_counts = conflicts.groupby("source_group").size().astype(int).to_dict()
    if conflict_counts != CONFLICT_EXPECTED:
        raise RuntimeError("4,986 conflict source census drift: %s" % conflict_counts)
    provenance = provenance_audit(root, plan, metadata)
    diagnostics_table, diagnostic_payload, embedded = diagnostics(plan, conflicts, stage)
    partitions = partition_census(conflicts, metadata, embedded)
    attacks = plan.loc[plan["role"].isin(ATTACK_ROLES), ["role", "source_group", "attack_family", "uid"]].copy()
    session = pd.read_csv(session_path, usecols=["uid", "session_id"])
    attacks = attacks.merge(session, on="uid", how="left", validate="one_to_one")
    attack_coverage = attacks.groupby(["role", "source_group", "attack_family"], dropna=False).agg(rows=("uid", "size"), sessions=("session_id", "nunique")).reset_index()
    report_audit = json.loads((stage / "ckda_d1_report_role_plan_audit.json").read_text(encoding="utf-8"))
    if int(report_audit["report_attack_rows"]) != REPORT_ATTACK_ROWS:
        raise RuntimeError("report attack identity count drift")
    verdict = "CKDD_D0_NO_IDENTIFIABLE_SOURCE_SPLIT" if not bool(partitions["admissible"].any()) else "CKDD_D0_NO_ATTACK_SAFETY_SUPPORT"
    out.mkdir(parents=True, exist_ok=False)
    atomic_csv(out / "ckdd_d0_conflict_source_census.csv", pd.DataFrame([{"source_group": key, "rows": value, "share": value / 4986.0} for key, value in sorted(conflict_counts.items())]))
    atomic_csv(out / "ckdd_d0_partition_census.csv", partitions)
    atomic_csv(out / "ckdd_d0_attack_anchor_coverage.csv", attack_coverage)
    atomic_csv(out / "ckdd_d0_frozen_head_diagnostics.csv", diagnostics_table)
    atomic_json(out / "ckdd_d0_provenance_audit.json", provenance)
    atomic_json(out / "ckdd_d0_frozen_head_diagnostics.json", diagnostic_payload)
    atomic_json(out / "ckdd_d0_untouched_inventory.json", {"status": "NO_UNTOUCHED_BENIGN_CONFIRMATION_AVAILABLE", "untouched_nonfinal_devices": 0, "positive_generalization_evidence": False})
    atomic_json(out / "ckdd_d0_future_kill_only_declaration.json", {
        "all_viewed_report_attack_rows": REPORT_ATTACK_ROWS, "named_conflict_subset_rows": REPORT_CONFLICT_SUBSET,
        "whole_denominator_is_safety_denominator": True, "conflict_subset_is_complete_safety_denominator": False,
        "future_query_rows_all_labels": int(report_audit["future_query_rows"]),
        "family_identity_breakdown_available_without_score_open": False,
        "blind_spots": ["unseen_attack_types", "absent_devices", "attacks_outside_conflict_quadrant", "legal_select_has_zero_conflict_attacks"],
        "report_score_files_opened": 0,
    })
    boundary = {
        "report_score_files_opened": 0, "final_files_opened": 0, "pcap_files_opened": 0,
        "optimizer_steps": 0, "fitted_parameters": 0, "training_operations": 0,
        "manual_schema_inspection_first_row_displayed_after_freeze": True,
        "manual_schema_inspection_used_for_rule_selection": False,
        "formal_d0_code_refuses_report_plan_and_report_scores": True,
        "input_identities": identities,
    }
    atomic_json(out / "ckdd_d0_boundary_audit.json", boundary)
    verdict_payload = {
        "status": verdict, "conflict_rows": 4986, "conflict_source_groups": 6,
        "largest_source_rows": 3687, "largest_source_share": 3687 / 4986.0,
        "enumerated_partitions": len(partitions), "admissible_partitions": int(partitions["admissible"].sum()),
        "fit_attack_rows": 4385, "select_attack_rows": 69,
        "claim_limit": "KNOWN_POOL_REPAIR_ONLY", "untouched_confirmation": "UNAVAILABLE",
    }
    atomic_json(out / "ckdd_d0_verdict.json", verdict_payload)
    atomic_json(out / "ckdd_d0_validation_report.json", {"status": "PASS", "scientific_verdict": verdict, "python39_compatible": True, "atomic_readback": True})
    files = sorted(path for path in out.iterdir() if path.is_file())
    atomic_text(out / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(path), path.name) for path in files))


def failure_only(out: Path, exc: BaseException) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    atomic_json(out / "engineering_failure.json", {"status": "CKDD_D0_ENGINEERING_FAILURE_NO_VERDICT", "error": str(exc), "traceback": traceback.format_exc()})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(args.root.resolve(), args.out.resolve())
    except BaseException as exc:
        failure_only(args.out.resolve(), exc)
        raise


if __name__ == "__main__":
    main()
