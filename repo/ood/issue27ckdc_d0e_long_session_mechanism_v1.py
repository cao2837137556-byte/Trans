#!/usr/bin/env python3
"""CKDC D0-E longest-session composition versus transition diagnosis."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT_REL = Path(
    "runs/mainline_docs/ckdc_d0_long_session_mechanism_addendum_preregistered_20260820.md"
)
CONTRACT_SHA256 = "68a44073187bad6391affca4255998e48ed5a9a84f1292341ff556643eb3de88"
SCORES_SHA256 = "7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9"
METADATA_SHA256 = "4d44d605bd00ac5065a2cacc9ff02ebf5384b2df6bb8f68ac6e8644a3090fb10"
FINAL_MARKERS = ("cooler-motor", "seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47")
CHECKPOINTS = (1, 2, 4, 16, 65)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> None:
    if not path.is_file() or sha256_file(path) != expected:
        raise RuntimeError("immutable input mismatch: %s" % path)


def bool_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(0).astype(int).astype(bool)
    return series.fillna("").astype(str).str.lower().isin({"1", "true"})


def verify_no_final(frame: pd.DataFrame) -> None:
    text = frame[["uid", "source_group"]].fillna("").astype(str).agg(" ".join, axis=1).str.lower()
    hit = pd.Series(False, index=frame.index)
    for marker in FINAL_MARKERS:
        hit |= text.str.contains(marker, regex=False)
    if bool(hit.any()):
        raise RuntimeError("FINAL marker found")


def choose_longest_sessions(frame: pd.DataFrame) -> pd.DataFrame:
    counts = (
        frame.groupby(["source_group", "session_id"], as_index=False)
        .size().rename(columns={"size": "target_count"})
        .sort_values(["source_group", "target_count", "session_id"],
                     ascending=[True, False, True], kind="mergesort")
    )
    selected = counts.groupby("source_group", sort=False, as_index=False).head(1).reset_index(drop=True)
    if len(selected) != 5 or (selected["target_count"] < 65).any():
        raise RuntimeError("long-session support gate failed")
    return selected


def classify(first_hard: bool, late_rate: float) -> str:
    if first_hard and late_rate >= 0.90:
        return "SESSION_CLASS_CONFLICT"
    if not first_hard and late_rate >= 0.90:
        return "WITHIN_SESSION_TRANSITION"
    return "NO_PERSISTENT_LONG_SESSION_HARD_STATE"


def route_verdict(selected: pd.DataFrame) -> str:
    counts = selected["mechanism_class"].value_counts()
    if int(counts.get("SESSION_CLASS_CONFLICT", 0)) >= 3:
        return "SESSION_CLASS_SIGNAL"
    if int(counts.get("WITHIN_SESSION_TRANSITION", 0)) >= 3:
        return "WITHIN_SESSION_TRANSITION_SIGNAL"
    return "MIXED_OR_NO_LONG_SESSION_SIGNAL"


def analyze(frame: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, object]]:
    selected_ids = choose_longest_sessions(frame)
    selected_rows: List[Dict[str, object]] = []
    checkpoint_rows: List[Dict[str, object]] = []
    for item in selected_ids.itertuples(index=False):
        part = frame.loc[
            frame["source_group"].eq(item.source_group) & frame["session_id"].eq(item.session_id)
        ].sort_values(["timestamp_epoch", "event_position", "uid"], kind="mergesort").copy()
        part["ordinal"] = np.arange(1, len(part) + 1)
        first_hard_positions = part.loc[part["p2_hard"], "ordinal"]
        first_hard = int(first_hard_positions.iloc[0]) if len(first_hard_positions) else None
        persistent = bool(part.loc[part["ordinal"].ge(first_hard), "p2_hard"].all()) if first_hard else False
        late = part.loc[part["ordinal"].ge(65)]
        late_rate = float(late["p2_hard"].mean())
        first_row = part.iloc[0]
        mechanism = classify(bool(first_row["p2_hard"]), late_rate)
        selected_rows.append({
            "source_group": item.source_group,
            "session_id": item.session_id,
            "target_count": int(len(part)),
            "ordinal_1_p2_hard": bool(first_row["p2_hard"]),
            "ordinal_1_p2_score": float(first_row["score"]),
            "first_four_p2_hard_rate": float(part.loc[part["ordinal"].le(4), "p2_hard"].mean()),
            "ordinal_65_plus_p2_hard_rate": late_rate,
            "first_hard_ordinal": first_hard,
            "hard_persistent_after_first_hard": persistent,
            "m7_hard_count": int(part["m7_hard_bool"].sum()),
            "mechanism_class": mechanism,
        })
        wanted = list(CHECKPOINTS) + [len(part)]
        for ordinal in dict.fromkeys(wanted):
            match = part.loc[part["ordinal"].eq(ordinal)]
            checkpoint_rows.append({
                "source_group": item.source_group,
                "session_id": item.session_id,
                "requested_ordinal": int(ordinal),
                "is_last": bool(ordinal == len(part)),
                "present": bool(len(match) == 1),
                "p2_hard": bool(match.iloc[0]["p2_hard"]) if len(match) else None,
                "p2_score": float(match.iloc[0]["score"]) if len(match) else np.nan,
                "m7_hard": bool(match.iloc[0]["m7_hard_bool"]) if len(match) else None,
            })
    selected = pd.DataFrame(selected_rows)
    checkpoints = pd.DataFrame(checkpoint_rows)
    verdict = {
        "status": "PASS",
        "verdict": route_verdict(selected),
        "class_counts": {str(k): int(v) for k, v in selected["mechanism_class"].value_counts().items()},
        "selected_sources": int(len(selected)),
        "pcap_opened": False,
        "training_performed": False,
        "final_opened": False,
    }
    return selected, checkpoints, verdict


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


def report(selected: pd.DataFrame, verdict: Mapping[str, object]) -> str:
    lines = [
        "# CKDC D0-E longest-session mechanism result", "",
        "- verdict: `%s`" % verdict["verdict"],
        "- selected sources: %d" % len(selected), "",
        "| source | targets | first hard | late hard rate | first hard ordinal | class |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in selected.itertuples(index=False):
        lines.append("| %s | %d | %s | %.2f%% | %s | %s |" % (
            row.source_group, row.target_count, str(bool(row.ordinal_1_p2_hard)),
            100.0 * row.ordinal_65_plus_p2_hard_rate, str(row.first_hard_ordinal), row.mechanism_class,
        ))
    lines.extend([
        "", "This is a VIEWED descriptive mechanism check. It does not authorize training,",
        "a horizon choice, FINAL access, or report-based selection.", "",
    ])
    return "\n".join(lines)


def execute(root: Path, stage: Path, output: Path) -> Dict[str, object]:
    require_sha(root / CONTRACT_REL, CONTRACT_SHA256)
    require_sha(stage / "ckda_d1_report_scores.csv.gz", SCORES_SHA256)
    require_sha(stage / "ckda_d1_report_embeddings.npz.metadata.csv.gz", METADATA_SHA256)
    scores = pd.read_csv(stage / "ckda_d1_report_scores.csv.gz")
    scores = scores.loc[
        scores["probe_id"].eq("P2") & scores["device_family"].eq("iotsim-hydraulic-system")
    ].copy()
    metadata = pd.read_csv(stage / "ckda_d1_report_embeddings.npz.metadata.csv.gz")
    metadata = metadata.loc[metadata["uid"].isin(scores["uid"])].copy()
    frame = scores.merge(metadata, on="uid", how="outer", indicator=True, validate="one_to_one")
    if not frame["_merge"].eq("both").all() or len(frame) != 3000:
        raise RuntimeError("exact hydraulic join failed")
    frame = frame.drop(columns="_merge")
    verify_no_final(frame)
    frame["p2_hard"] = bool_series(frame["hard"])
    frame["m7_hard_bool"] = bool_series(frame["m7_hard"])
    selected, checkpoints, verdict = analyze(frame)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(tempfile.mkdtemp(prefix=".%s.stage." % output.name, dir=str(output.parent)))
    try:
        atomic_csv(temp_dir / "ckdc_d0e_selected_sessions.csv", selected)
        atomic_csv(temp_dir / "ckdc_d0e_checkpoints.csv", checkpoints)
        atomic_json(temp_dir / "ckdc_d0e_verdict.json", verdict)
        atomic_text(temp_dir / "ckdc_d0e_result_report.md", report(selected, verdict))
        names = ["ckdc_d0e_selected_sessions.csv", "ckdc_d0e_checkpoints.csv",
                 "ckdc_d0e_verdict.json", "ckdc_d0e_result_report.md"]
        atomic_text(temp_dir / "SHA256SUMS", "\n".join(
            "%s  %s" % (sha256_file(temp_dir / name), name) for name in names
        ) + "\n")
        if output.exists():
            raise FileExistsError(str(output))
        os.replace(str(temp_dir), str(output))
    except Exception:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise
    return verdict


def failure_only(output: Path, exc: BaseException) -> None:
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    output.mkdir(parents=True)
    atomic_json(output / "engineering_failure.json", {
        "status": "ENGINEERING_FAILURE", "message": str(exc),
        "exception_type": type(exc).__name__, "traceback": traceback.format_exc(),
        "scientific_verdict_written": False,
    })


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--stage", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("refusing to replace existing output: %s" % output)
    try:
        verdict = execute(args.root.resolve(), args.stage.resolve(), output)
        print(json.dumps(verdict, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        if not output.exists():
            failure_only(output, exc)
        raise


if __name__ == "__main__":
    raise SystemExit(main())
