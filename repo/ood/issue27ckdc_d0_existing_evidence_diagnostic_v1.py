#!/usr/bin/env python3
"""CKDC D0 read-only diagnosis over frozen CKDA/CKBW artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path(
    "runs/mainline_docs/ckdc_d0_existing_evidence_diagnostic_preregistered_20260820.md"
)
CONTRACT_SHA256 = "2088de963f70c3b783a9c4f9c2a6e6a3f2f6053e2117c68067592c8f2d742d18"
CKDA_CONTRACT_SHA256 = "ecb429926507d2c4f8f666edc2d7e50f3e94fc2ec74bc1e26e78ca4813950aa9"
FIT_SELECT_PLAN_SHA256 = "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"
SELECT_SCORES_SHA256 = "bc34268eea2c4545a425cba8adf641a214f75dae5435858a86ee0bb3aabe3419"
THRESHOLD_MARKER_SHA256 = "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"
REPORT_SCORES_SHA256 = "7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9"
REPORT_TARGET_METADATA_SHA256 = "628c542108b4b582e74cd6ed0e5474a5f69225bd6a7c054200998d7448bfe65e"
REPORT_EMBED_METADATA_SHA256 = "4d44d605bd00ac5065a2cacc9ff02ebf5384b2df6bb8f68ac6e8644a3090fb10"
CKBW_SHA256 = "d1e905924e74bf390aaaae79ee68f10312dc0bc1cdebff88848d4d3ee64adf85"
E3_EMBEDDER_SHA256 = "360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14"
E3_ADAPTER_SHA256 = "ec1cb7be1f47e2ef7862905f3e89c75c0295fb1565fa0820d174a6e11409856a"

SELECT_ROLES = {"support_val", "aux_normal_select", "aux_select"}
FINAL_MARKERS = ("cooler-motor", "seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47")
M7_COL = "hard__M7-TabM-TailMargin-DualControl"

ORDINAL_ORDER = ["1", "2-4", "5-16", "17-64", "65+"]
ELAPSED_ORDER = ["0-1s", "(1,10]s", "(10,60]s", "(60,300]s", "(300,1800]s", ">1800s"]
POSITION_ORDER = ["0-72", "73-256", "257-1024", "1025+"]


def sha256_file(path: Path, block_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(block_size)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    if not path.is_file():
        raise FileNotFoundError(str(path))
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch for %s: %s != %s" % (path, actual, expected))
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual}


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(False).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(int).astype(bool)
    lowered = series.fillna("").astype(str).str.strip().str.lower()
    allowed = {"", "0", "1", "false", "true"}
    unexpected = sorted(set(lowered.unique()) - allowed)
    if unexpected:
        raise ValueError("unexpected boolean values: %s" % unexpected)
    return lowered.isin({"1", "true"})


def quadrant(p2_hard: bool, m7_hard: bool) -> str:
    if p2_hard and m7_hard:
        return "P2_HARD__M7_HARD"
    if p2_hard and not m7_hard:
        return "P2_HARD__M7_NORMAL"
    if not p2_hard and m7_hard:
        return "P2_NORMAL__M7_HARD"
    return "P2_NORMAL__M7_NORMAL"


def ordinal_bin(value: int) -> str:
    if value <= 1:
        return "1"
    if value <= 4:
        return "2-4"
    if value <= 16:
        return "5-16"
    if value <= 64:
        return "17-64"
    return "65+"


def elapsed_bin(value: float) -> str:
    if value <= 1:
        return "0-1s"
    if value <= 10:
        return "(1,10]s"
    if value <= 60:
        return "(10,60]s"
    if value <= 300:
        return "(60,300]s"
    if value <= 1800:
        return "(300,1800]s"
    return ">1800s"


def position_bin(value: int) -> str:
    if value <= 72:
        return "0-72"
    if value <= 256:
        return "73-256"
    if value <= 1024:
        return "257-1024"
    return "1025+"


def h3_decision(frame: pd.DataFrame) -> Dict[str, object]:
    conflict = frame.loc[frame["quadrant"].eq("P2_HARD__M7_NORMAL")].copy()
    benign = conflict.loc[conflict["label_metric_only"].eq(0)]
    attack = conflict.loc[conflict["label_metric_only"].eq(1)]

    benign_source_counts = benign.groupby("source_group", dropna=False).size()
    attack_family_counts = attack.groupby("attack_family", dropna=False).size()

    benign_max_share = float(benign_source_counts.max() / len(benign)) if len(benign) else None
    attack_max_share = float(attack_family_counts.max() / len(attack)) if len(attack) else None
    clauses = {
        "benign_rows_ge_300": len(benign) >= 300,
        "benign_source_groups_ge_3": benign["source_group"].nunique(dropna=False) >= 3,
        "attack_rows_ge_30": len(attack) >= 30,
        "attack_families_ge_3": attack["attack_family"].nunique(dropna=False) >= 3,
        "benign_max_share_le_0_80": benign_max_share is not None and benign_max_share <= 0.80,
        "attack_max_share_le_0_80": attack_max_share is not None and attack_max_share <= 0.80,
    }
    passed = all(clauses.values())
    return {
        "verdict": "H3_LEGAL_SUPPORT_PRESENT" if passed else "NO_IDENTIFIABLE_LEGAL_CONFLICT_SUPPORT",
        "clauses": clauses,
        "benign_conflict_rows": int(len(benign)),
        "benign_conflict_source_groups": int(benign["source_group"].nunique(dropna=False)),
        "benign_max_source_share": benign_max_share,
        "attack_conflict_rows": int(len(attack)),
        "attack_conflict_families": int(attack["attack_family"].nunique(dropna=False)),
        "attack_max_family_share": attack_max_share,
    }


def h1_decision(contrasts: pd.DataFrame) -> Dict[str, object]:
    eligible = contrasts.loc[contrasts["eligible"]].copy()
    if eligible.empty:
        return {
            "verdict": "INSUFFICIENT_EARLY_LATE_SUPPORT",
            "signal": "INSUFFICIENT_EARLY_LATE_SUPPORT",
            "eligible_sources": 0,
            "positive_signal_sources": 0,
            "negative_signal_sources": 0,
        }
    positive = eligible["delta_late_minus_early"].ge(0.10)
    negative = eligible["delta_late_minus_early"].le(-0.10)
    positive_n = int(positive.sum())
    negative_n = int(negative.sum())
    if positive_n >= 3:
        verdict = "H1_TIME_COURSE_SUPPORT_PRESENT"
        signal = "LATE_STAGE_DEGRADATION_SIGNAL"
    elif negative_n >= 3:
        verdict = "H1_TIME_COURSE_SUPPORT_PRESENT"
        signal = "LATE_STAGE_IMPROVEMENT_SIGNAL"
    else:
        verdict = "NO_CONSISTENT_TIME_COURSE_SIGNAL"
        signal = "NO_CONSISTENT_TIME_COURSE_SIGNAL"
    return {
        "verdict": verdict,
        "signal": signal,
        "eligible_sources": int(len(eligible)),
        "positive_signal_sources": positive_n,
        "negative_signal_sources": negative_n,
    }


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    temp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temp), str(path))


def atomic_csv(path: Path, frame: pd.DataFrame) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    frame.to_csv(temp, index=False, lineterminator="\n")
    os.replace(str(temp), str(path))


def atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temp), str(path))


def verify_no_final(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    combined = pd.Series("", index=frame.index, dtype="object")
    for column in columns:
        if column in frame.columns:
            combined = combined + " " + frame[column].fillna("").astype(str).str.lower()
    hit = pd.Series(False, index=frame.index)
    for marker in FINAL_MARKERS:
        hit |= combined.str.contains(marker, regex=False)
    if bool(hit.any()):
        raise RuntimeError("FINAL marker found in diagnostic input")


def audit_e3_capability(embedder: Path, adapter: Path) -> Dict[str, object]:
    embed_text = embedder.read_text(encoding="utf-8")
    adapter_text = adapter.read_text(encoding="utf-8")

    checks = {
        "embedder_max_bursts_per_direction_12": "if len(bursts) >= 12:" in embed_text,
        "embedder_max_packets_per_burst_6": "if len(bursts[-1]) < 6:" in embed_text,
        "embedder_burst_gap_0_010": "> 0.010" in embed_text,
        "adapter_max_merged_bursts_12": ")[:12]" in adapter_text,
        "adapter_max_packets_per_burst_6": "values[:6]" in adapter_text,
        "adapter_earliest_first_sort": "sorted(by_direction" in adapter_text,
        "duration_uses_latest_timestamp": "latest_timestamp" in embed_text and "flow_duration" in embed_text,
    }
    if not all(checks.values()):
        raise RuntimeError("E3 capability audit failed: %s" % checks)
    return {
        "status": "PASS",
        "checks": checks,
        "burst_gap_seconds": 0.010,
        "max_merged_bursts": 12,
        "max_packets_per_burst": 6,
        "max_packet_content_records": 72,
        "later_duration_visible": True,
        "later_packet_content_beyond_caps_visible": False,
        "verdict": "EARLY_BURST_CONTENT_CAPPED_DURATION_VISIBLE",
    }


def load_select(stage: Path, ckbw_path: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    scores = pd.read_csv(stage / "ckda_d1_select_scores.csv.gz")
    scores = scores.loc[scores["probe_id"].eq("P2")].copy()
    if scores["uid"].duplicated().any():
        raise RuntimeError("duplicate P2 select UID")
    if set(scores["role"].unique()) - SELECT_ROLES:
        raise RuntimeError("unexpected select role")

    plan_columns = ["uid", "role", "source_group", "attack_family", "label_metric_only"]
    plan = pd.read_csv(stage / "ckda_d1_fit_select_plan.csv", usecols=plan_columns)
    plan = plan.loc[plan["role"].isin(SELECT_ROLES)].copy()
    if plan["uid"].duplicated().any():
        raise RuntimeError("duplicate select plan UID")

    ckbw_columns = [
        "uid", M7_COL, "tail_margin_score", "tail_margin_tau_normal", "tail_margin_tau_attack"
    ]
    ckbw = pd.read_csv(ckbw_path, usecols=ckbw_columns)
    duplicate_invariance: Dict[str, int] = {}
    for column in ckbw_columns[1:]:
        disagreement = int(ckbw.groupby("uid", dropna=False)[column].nunique(dropna=False).gt(1).sum())
        duplicate_invariance[column] = disagreement
        if disagreement:
            raise RuntimeError("CKBW held-view disagreement in %s" % column)
    ckbw = ckbw.drop_duplicates("uid", keep="first")

    merged = scores.merge(plan, on=["uid", "role"], how="outer", indicator=True, validate="one_to_one")
    if not merged["_merge"].eq("both").all():
        raise RuntimeError("select score/plan join is not exact")
    merged = merged.drop(columns="_merge")
    merged = merged.merge(ckbw, on="uid", how="left", validate="one_to_one")
    if merged[M7_COL].isna().any():
        raise RuntimeError("select UID missing frozen M7 state")
    merged["p2_hard"] = bool_series(merged["hard"])
    merged["m7_hard"] = bool_series(merged[M7_COL])
    merged["quadrant"] = [quadrant(p2, m7) for p2, m7 in zip(merged["p2_hard"], merged["m7_hard"])]
    verify_no_final(merged, ["uid", "source_group", "attack_family"])
    audit = {
        "select_rows": int(len(merged)),
        "select_unique_uids": int(merged["uid"].nunique()),
        "duplicate_view_disagreements": duplicate_invariance,
        "roles": {str(k): int(v) for k, v in merged["role"].value_counts().sort_index().items()},
    }
    return merged, audit


def select_summary(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ["role", "label_metric_only", "attack_family", "source_group", "quadrant"]
    return frame.groupby(keys, dropna=False).size().rename("rows").reset_index()


def load_hydraulic(stage: Path) -> Tuple[pd.DataFrame, Dict[str, object]]:
    scores = pd.read_csv(stage / "ckda_d1_report_scores.csv.gz")
    scores = scores.loc[
        scores["probe_id"].eq("P2") & scores["device_family"].eq("iotsim-hydraulic-system")
    ].copy()
    if scores["uid"].duplicated().any():
        raise RuntimeError("duplicate hydraulic P2 report UID")

    target_columns = [
        "uid", "source_group", "device_family", "attack_family", "label_metric_only",
        "target_event_position_within_capture", "raw_source_path", "metadata_matched",
    ]
    target = pd.read_csv(stage / "ckda_d1_report_target_metadata.csv", usecols=target_columns)
    target = target.loc[target["uid"].isin(scores["uid"])].copy()
    embedding = pd.read_csv(stage / "ckda_d1_report_embeddings.npz.metadata.csv.gz")
    embedding = embedding.loc[embedding["uid"].isin(scores["uid"])].copy()

    merged = scores.merge(target, on=["uid", "source_group", "device_family", "attack_family", "label_metric_only"],
                          how="outer", indicator=True, validate="one_to_one")
    if not merged["_merge"].eq("both").all():
        raise RuntimeError("hydraulic report score/target join is not exact")
    merged = merged.drop(columns="_merge")
    merged = merged.merge(embedding, on="uid", how="left", validate="one_to_one")
    if merged[["session_id", "timestamp_epoch", "event_position"]].isna().any().any():
        raise RuntimeError("missing hydraulic session metadata")
    if not bool_series(merged["metadata_matched"]).all():
        raise RuntimeError("unmatched hydraulic target metadata")
    verify_no_final(merged, ["uid", "source_group", "raw_source_path"])

    merged["p2_hard"] = bool_series(merged["hard"])
    merged["m7_hard_bool"] = bool_series(merged["m7_hard"])
    merged = merged.sort_values(
        ["session_id", "timestamp_epoch", "event_position", "uid"], kind="mergesort"
    ).reset_index(drop=True)
    merged["target_ordinal_so_far"] = merged.groupby("session_id", sort=False).cumcount() + 1
    first_time = merged.groupby("session_id", sort=False)["timestamp_epoch"].transform("min")
    merged["elapsed_seconds_so_far"] = (merged["timestamp_epoch"] - first_time).clip(lower=0)
    merged["ordinal_bin"] = merged["target_ordinal_so_far"].map(ordinal_bin)
    merged["elapsed_bin"] = merged["elapsed_seconds_so_far"].map(elapsed_bin)
    merged["capture_event_position_bin"] = merged["event_position"].astype(int).map(position_bin)
    audit = {
        "hydraulic_rows": int(len(merged)),
        "hydraulic_sessions": int(merged["session_id"].nunique()),
        "hydraulic_sources": int(merged["source_group"].nunique()),
        "p2_hard_rows": int(merged["p2_hard"].sum()),
        "m7_hard_rows": int(merged["m7_hard_bool"].sum()),
        "capture_position_is_session_packet_count": False,
    }
    return merged, audit


def time_course(frame: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    dimensions = [
        ("target_ordinal_so_far", "ordinal_bin", ORDINAL_ORDER),
        ("elapsed_seconds_so_far", "elapsed_bin", ELAPSED_ORDER),
        ("capture_event_position_not_session_packet_count", "capture_event_position_bin", POSITION_ORDER),
    ]
    for dimension, column, order in dimensions:
        for source in sorted(frame["source_group"].unique()):
            source_part = frame.loc[frame["source_group"].eq(source)]
            for bin_value in order:
                part = source_part.loc[source_part[column].eq(bin_value)]
                rows.append({
                    "dimension": dimension,
                    "bin": bin_value,
                    "source_group": source,
                    "rows": int(len(part)),
                    "sessions": int(part["session_id"].nunique()),
                    "p2_hard_rate": float(part["p2_hard"].mean()) if len(part) else np.nan,
                    "m7_hard_rate": float(part["m7_hard_bool"].mean()) if len(part) else np.nan,
                    "p2_score_q25": float(part["score"].quantile(0.25)) if len(part) else np.nan,
                    "p2_score_median": float(part["score"].median()) if len(part) else np.nan,
                    "p2_score_q75": float(part["score"].quantile(0.75)) if len(part) else np.nan,
                })
    return pd.DataFrame(rows)


def source_contrasts(frame: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, object]] = []
    for source in sorted(frame["source_group"].unique()):
        part = frame.loc[frame["source_group"].eq(source)]
        early = part.loc[part["target_ordinal_so_far"].le(4)]
        late = part.loc[part["target_ordinal_so_far"].ge(65)]
        eligible = (
            len(early) >= 30 and early["session_id"].nunique() >= 5
            and len(late) >= 30 and late["session_id"].nunique() >= 5
        )
        early_rate = float(early["p2_hard"].mean()) if len(early) else np.nan
        late_rate = float(late["p2_hard"].mean()) if len(late) else np.nan
        rows.append({
            "source_group": source,
            "early_rows": int(len(early)),
            "early_sessions": int(early["session_id"].nunique()),
            "early_p2_hard_rate": early_rate,
            "late_rows": int(len(late)),
            "late_sessions": int(late["session_id"].nunique()),
            "late_p2_hard_rate": late_rate,
            "delta_late_minus_early": late_rate - early_rate if len(early) and len(late) else np.nan,
            "eligible": bool(eligible),
        })
    return pd.DataFrame(rows)


def render_report(verdict: Mapping[str, object], select_audit: Mapping[str, object],
                  hydraulic_audit: Mapping[str, object]) -> str:
    h3 = verdict["h3"]
    h1 = verdict["h1"]
    return """# CKDC D0 existing-evidence diagnostic result

## Mechanical verdict

- H3: `{h3_verdict}`
- H1: `{h1_verdict}` (`{h1_signal}`)
- E3 capability: `{e3_verdict}`

## Exact facts

- legal select rows: {select_rows}
- `P2 hard / M7 normal` benign select rows: {benign_rows}
- `P2 hard / M7 normal` attack select rows: {attack_rows}
- hydraulic report rows (VIEWED, descriptive only): {hydraulic_rows}
- hydraulic P2 hard rows: {hydraulic_p2}
- hydraulic M7 hard rows: {hydraulic_m7}

## Interpretation boundary

This diagnosis does not train or select a model.  H3 may proceed only when its legal-support
conjunction passes.  H1 uses already-viewed report rows only to decide whether a separate,
label-free retention audit is worth preregistering.  No FINAL material was opened.
""".format(
        h3_verdict=h3["verdict"], h1_verdict=h1["verdict"], h1_signal=h1["signal"],
        e3_verdict=verdict["e3_capability_verdict"], select_rows=select_audit["select_rows"],
        benign_rows=h3["benign_conflict_rows"], attack_rows=h3["attack_conflict_rows"],
        hydraulic_rows=hydraulic_audit["hydraulic_rows"],
        hydraulic_p2=hydraulic_audit["p2_hard_rows"], hydraulic_m7=hydraulic_audit["m7_hard_rows"],
    )


def write_sha256s(directory: Path, names: Sequence[str]) -> None:
    lines = ["%s  %s" % (sha256_file(directory / name), name) for name in names]
    atomic_text(directory / "SHA256SUMS", "\n".join(lines) + "\n")


def execute(root: Path, stage: Path, ckbw: Path, output: Path) -> Dict[str, object]:
    identities = {
        "ckdc_contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA256),
        "ckda_contract": require_sha(
            root / "runs/mainline_docs/ckda_d1_frozen_representation_probe_preregistered_20260812.md",
            CKDA_CONTRACT_SHA256,
        ),
        "fit_select_plan": require_sha(stage / "ckda_d1_fit_select_plan.csv", FIT_SELECT_PLAN_SHA256),
        "select_scores": require_sha(stage / "ckda_d1_select_scores.csv.gz", SELECT_SCORES_SHA256),
        "threshold_marker": require_sha(stage / "ckda_d1_threshold_freeze_marker.json", THRESHOLD_MARKER_SHA256),
        "report_scores": require_sha(stage / "ckda_d1_report_scores.csv.gz", REPORT_SCORES_SHA256),
        "report_target_metadata": require_sha(
            stage / "ckda_d1_report_target_metadata.csv", REPORT_TARGET_METADATA_SHA256
        ),
        "report_embedding_metadata": require_sha(
            stage / "ckda_d1_report_embeddings.npz.metadata.csv.gz", REPORT_EMBED_METADATA_SHA256
        ),
        "ckbw_predictions": require_sha(ckbw, CKBW_SHA256),
        "e3_embedder": require_sha(root / "repo/ood/issue27ckda_d1_e3_embed_v1.py", E3_EMBEDDER_SHA256),
        "e3_adapter": require_sha(root / "repo/ood/issue27ckda_d0_resource_pilot_v1.py", E3_ADAPTER_SHA256),
    }

    select, select_audit = load_select(stage, ckbw)
    h3 = h3_decision(select)
    capability = audit_e3_capability(
        root / "repo/ood/issue27ckda_d1_e3_embed_v1.py",
        root / "repo/ood/issue27ckda_d0_resource_pilot_v1.py",
    )
    hydraulic, hydraulic_audit = load_hydraulic(stage)
    course = time_course(hydraulic)
    contrasts = source_contrasts(hydraulic)
    h1 = h1_decision(contrasts)

    verdict = {
        "status": "PASS",
        "h3": h3,
        "h1": h1,
        "e3_capability_verdict": capability["verdict"],
        "training_performed": False,
        "pcap_opened": False,
        "final_opened": False,
        "report_used_for_selection": False,
    }
    input_audit = {
        "status": "PASS",
        "identities": identities,
        "select": select_audit,
        "hydraulic_report": hydraulic_audit,
        "final_opened": 0,
        "pcap_opened": 0,
    }

    parent = output.parent
    parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=".%s.stage." % output.name, dir=str(parent)))
    try:
        atomic_json(stage_dir / "ckdc_d0_input_audit.json", input_audit)
        atomic_csv(
            stage_dir / "ckdc_d0_select_quadrants.csv",
            select[[
                "uid", "role", "source_group", "attack_family", "label_metric_only", "score",
                "p2_hard", "m7_hard", "tail_margin_score", "tail_margin_tau_normal",
                "tail_margin_tau_attack", "quadrant",
            ]].sort_values(["role", "source_group", "uid"]),
        )
        atomic_csv(stage_dir / "ckdc_d0_select_support_summary.csv", select_summary(select))
        atomic_json(stage_dir / "ckdc_d0_e3_capability_audit.json", capability)
        atomic_csv(stage_dir / "ckdc_d0_hydraulic_time_course.csv", course)
        atomic_csv(stage_dir / "ckdc_d0_hydraulic_source_contrasts.csv", contrasts)
        atomic_json(stage_dir / "ckdc_d0_verdict.json", verdict)
        atomic_text(stage_dir / "ckdc_d0_result_report.md", render_report(verdict, select_audit, hydraulic_audit))
        names = [
            "ckdc_d0_input_audit.json", "ckdc_d0_select_quadrants.csv",
            "ckdc_d0_select_support_summary.csv", "ckdc_d0_e3_capability_audit.json",
            "ckdc_d0_hydraulic_time_course.csv", "ckdc_d0_hydraulic_source_contrasts.csv",
            "ckdc_d0_verdict.json", "ckdc_d0_result_report.md",
        ]
        write_sha256s(stage_dir, names)
        if output.exists():
            raise FileExistsError(str(output))
        os.replace(str(stage_dir), str(output))
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise
    return verdict


def failure_only(output: Path, exc: BaseException) -> None:
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    output.mkdir(parents=True, exist_ok=False)
    atomic_json(output / "engineering_failure.json", {
        "status": "ENGINEERING_FAILURE",
        "exception_type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
        "scientific_verdict_written": False,
    })


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--ckbw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    try:
        verdict = execute(args.root.resolve(), args.stage.resolve(), args.ckbw.resolve(), output)
        print(json.dumps(verdict, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        if not output.exists():
            failure_only(output, exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
