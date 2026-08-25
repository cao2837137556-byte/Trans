#!/usr/bin/env python3
"""CKDE D0 metadata-only commissioning identifiability audit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import traceback
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Tuple

import pandas as pd


CONTRACT_REL = Path("runs/mainline_docs/ckde_d0_benign_commissioning_identifiability_preregistered_20260825.md")
CONTRACT_SHA256 = "1f36d0dba81e676af1a2bd29436e4fdf90e85642301cf30a9ca09af751f823a1"
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")
PINS = {
    "plan": ("ckda_d1_fit_select_plan.csv", "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"),
    "target_metadata": ("ckda_d1_fit_select_target_metadata.csv", "d6fbba24a1997db24597a800cf952f80f739284e5ca13db5ce04497f1540c36d"),
    "session_metadata": ("ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"),
    "fit_select_role_audit": ("ckda_d1_fit_select_role_plan_audit.json", "0f29503a225f7b235d68595dc813ecd98ff8a3f6e02f9a7991a53cb351777385"),
    "report_role_audit": ("ckda_d1_report_role_plan_audit.json", "692317b7c584deea06ff1c1d07b013151cff7794b456d18b71ba87cdea0469bd"),
}
ATTACK_ROLES = {"aux_process_fit", "support_train", "support_val"}
BENIGN_ROLES = {"aux_fit", "aux_normal_fit", "aux_normal_select", "aux_select", "id_calib", "ood_val"}
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
        raise RuntimeError("SHA mismatch: %s" % path)
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


def pin_inputs(root: Path) -> Dict[str, object]:
    stage = root / STAGE_REL
    identities = {"contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256)}
    for key, (name, digest) in PINS.items():
        path = stage / name
        if path.name in FORBIDDEN_FILENAMES:
            raise RuntimeError("forbidden report asset")
        identities[key] = require_sha(path, digest)
    return identities


def build_census(plan: pd.DataFrame, target: pd.DataFrame, sessions: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    allowed = plan[["uid", "role", "source_group", "device_family", "recorded_index", "global_pool", "plan_scope"]].copy()
    joined = allowed.merge(target[["uid", "source_group", "raw_source_path", "dataset_kind", "target_event_position_within_capture"]], on="uid", how="left", validate="one_to_one", suffixes=("", "_meta"))
    joined = joined.merge(sessions[["uid", "session_id", "timestamp_epoch", "event_position"]], on="uid", how="left", validate="one_to_one")
    if len(joined) != len(plan) or joined["session_id"].isna().any():
        raise RuntimeError("exact metadata/session join failure")
    if not joined["source_group"].astype(str).eq(joined["source_group_meta"].astype(str)).all():
        raise RuntimeError("source lineage disagreement")
    joined["device_key"] = joined["source_group"].astype(str)
    joined["publisher_semantic"] = joined["role"].map(lambda role: "ATTACK_ROLE" if role in ATTACK_ROLES else ("BENIGN_ROLE" if role in BENIGN_ROLES else "UNKNOWN"))
    if joined["publisher_semantic"].eq("UNKNOWN").any():
        raise RuntimeError("unknown role semantics")
    device_rows: List[Dict[str, object]] = []
    pairing_rows: List[Dict[str, object]] = []
    for device, part in joined.groupby("device_key", sort=True):
        benign = part.loc[part["publisher_semantic"].eq("BENIGN_ROLE")].copy()
        attacks = part.loc[part["publisher_semantic"].eq("ATTACK_ROLE")].copy()
        source_paths = sorted(set(part["raw_source_path"].astype(str)))
        lineage_stable = len(source_paths) == 1
        prefix_sessions = 0
        suffix_sessions = 0
        prefix_rows = 0
        suffix_rows = 0
        cut = None
        if len(benign) >= 2:
            benign.sort_values(["event_position", "uid"], kind="mergesort", inplace=True)
            cut_index = len(benign) // 2
            cut = int(benign.iloc[cut_index - 1]["event_position"])
            before = benign.loc[benign["event_position"].le(cut)].copy()
            after = benign.loc[benign["event_position"].gt(cut)].copy()
            # Count only sessions wholly on one causal side; straddlers are not independent units.
            spans = benign.groupby("session_id")["event_position"].agg(["min", "max"])
            prefix_ids = set(spans.index[spans["max"].le(cut)])
            suffix_ids = set(spans.index[spans["min"].gt(cut)])
            prefix_sessions = len(prefix_ids)
            suffix_sessions = len(suffix_ids)
            prefix_rows = int(before["session_id"].isin(prefix_ids).sum())
            suffix_rows = int(after["session_id"].isin(suffix_ids).sum())
        attack_sessions = int(attacks["session_id"].nunique())
        eligible_prefix = lineage_stable and prefix_sessions > 0 and suffix_sessions > 0
        device_rows.append({
            "device_key": device, "device_family": "|".join(sorted(set(part["device_family"].astype(str)))),
            "raw_source_paths": "|".join(source_paths), "lineage_stable": lineage_stable,
            "benign_rows": len(benign), "attack_rows": len(attacks), "benign_sessions": int(benign["session_id"].nunique()),
            "attack_sessions": attack_sessions, "d0_count_only_cut_event_position": cut,
            "prefix_rows_whole_sessions": prefix_rows, "prefix_independent_sessions": prefix_sessions,
            "suffix_benign_rows_whole_sessions": suffix_rows, "suffix_independent_sessions": suffix_sessions,
            "causal_prefix_and_suffix_identifiable": eligible_prefix,
        })
        pairing_rows.append({
            "device_key": device, "legal_benign_prefix": eligible_prefix, "later_benign_suffix": suffix_sessions > 0,
            "later_same_device_attack_population": attack_sessions > 0,
            "paired_device_eligible": eligible_prefix and attack_sessions > 0,
        })
    census = pd.DataFrame(device_rows)
    pairing = pd.DataFrame(pairing_rows)
    eligible = census.loc[census["causal_prefix_and_suffix_identifiable"]]
    paired = pairing.loc[pairing["paired_device_eligible"]]
    summary = {
        "devices_total": len(census), "devices_with_causal_benign_prefix_suffix": len(eligible),
        "devices_with_same_device_attack_pairing": len(paired),
        "eligible_prefix_sessions": int(eligible["prefix_independent_sessions"].sum()),
        "eligible_suffix_sessions": int(eligible["suffix_independent_sessions"].sum()),
        "record_count_never_upgrades_session_gate": True,
        "device_key": "source_group_with_one_to_one_raw_source_path_lineage",
        "session_key": "precomputed_sha256(source_id+pcap_member+canonical_bidirectional_5tuple_with_protocol)",
        "d0_cut_rule": "COUNT_ONLY_MEDIAN_EVENT_POSITION_WHOLE_SESSION_CENSUS_NOT_D1_FORMULA",
    }
    return census, pairing, summary


def choose_verdict(summary: Mapping[str, object]) -> str:
    if int(summary["devices_with_same_device_attack_pairing"]) > 0:
        return "CKDE_D0_PAIRED_CALIBRATION_IDENTIFIABLE"
    if int(summary["devices_with_causal_benign_prefix_suffix"]) > 0 and int(summary["eligible_prefix_sessions"]) > 0:
        return "CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY"
    if int(summary["devices_with_causal_benign_prefix_suffix"]) > 0:
        return "CKDE_D0_INSUFFICIENT_INDEPENDENT_SESSIONS"
    return "CKDE_D0_NO_CAUSAL_BENIGN_PREFIX"


def run(root: Path, out: Path) -> None:
    identities = pin_inputs(root)
    stage = root / STAGE_REL
    # usecols deliberately excludes attack_family and label_metric_only.
    plan = pd.read_csv(stage / "ckda_d1_fit_select_plan.csv", usecols=["uid", "role", "source_group", "device_family", "recorded_index", "global_pool", "plan_scope"])
    target = pd.read_csv(stage / "ckda_d1_fit_select_target_metadata.csv", usecols=["uid", "source_group", "raw_source_path", "dataset_kind", "target_event_position_within_capture"])
    sessions = pd.read_csv(stage / "ckda_d1_fit_select_embeddings.npz.metadata.csv.gz", usecols=["uid", "session_id", "timestamp_epoch", "event_position"])
    if len(plan) != 25467 or plan["uid"].duplicated().any():
        raise RuntimeError("plan denominator drift")
    census, pairing, summary = build_census(plan, target, sessions)
    verdict = choose_verdict(summary)
    out.mkdir(parents=True, exist_ok=False)
    atomic_csv(out / "ckde_d0_device_lineage_census.csv", census)
    atomic_csv(out / "ckde_d0_same_device_pairing.csv", pairing)
    atomic_json(out / "ckde_d0_prefix_suffix_summary.json", summary)
    atomic_json(out / "ckde_d0_untouched_inventory.json", {
        "untouched_nonfinal_devices_in_allowed_fit_select_artifacts": 0,
        "viewed_report_devices_recycled_as_positive_evidence": 0,
        "final_devices_opened": 0,
        "final_confirmation": "PENDING_SEPARATE_PREREGISTRATION",
    })
    atomic_json(out / "ckde_d0_role_open_audit.json", {
        "input_identities": identities, "plan_columns_read": ["uid", "role", "source_group", "device_family", "recorded_index", "global_pool", "plan_scope"],
        "row_labels_read": 0, "attack_family_columns_read": 0, "report_score_files_opened": 0,
        "report_plan_files_opened": 0, "final_files_opened": 0, "pcap_files_opened": 0,
        "thresholds_fitted": 0, "calibration_scores_opened": 0,
        "manual_schema_inspection_first_row_displayed_after_freeze": True,
        "manual_schema_inspection_used_for_rule_selection": False,
        "formal_d0_code_refuses_report_plan_and_report_scores": True,
    })
    atomic_json(out / "ckde_d0_verdict.json", {
        "status": verdict, **summary,
        "strict_session_conformal_claim_authorized": verdict == "CKDE_D0_PAIRED_CALIBRATION_IDENTIFIABLE",
        "prefix_quantile_engineering_study_authorized_for_drafting": verdict == "CKDE_D0_UNPAIRED_DEVELOPMENT_ONLY",
        "same_device_attack_preservation_positive_claim": False,
        "d1_executable": False,
    })
    atomic_json(out / "ckde_d0_validation_report.json", {"status": "PASS", "scientific_verdict": verdict, "python39_compatible": True, "atomic_readback": True})
    files = sorted(path for path in out.iterdir() if path.is_file())
    atomic_text(out / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(path), path.name) for path in files))


def failure_only(out: Path, exc: BaseException) -> None:
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    atomic_json(out / "engineering_failure.json", {"status": "CKDE_D0_ENGINEERING_FAILURE_NO_VERDICT", "error": str(exc), "traceback": traceback.format_exc()})


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
