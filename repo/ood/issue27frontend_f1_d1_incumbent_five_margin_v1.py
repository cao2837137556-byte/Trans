#!/usr/bin/env python3
"""Materialize incumbent E3+P2 margins for five frozen fit attack rows only."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

import numpy as np


CONTRACT_REL = Path("runs/mainline_docs/frontend_f1_d1_incumbent_five_margin_materialization_frozen_20260904.md")
CONTRACT_SHA256 = "2c35d80f63c9ea0337e33244192e5218b56e5a2287ff1d6dbbfc5bba2288a67a"
DIAGNOSTIC_REL = Path("runs/frontend_f1_d1_terminal_no_eligible_diagnostic_v1_20260904/f1_d1_terminal_flipped_attacks.csv")
D0_REL = Path("runs/frontend_f1_d0_census_v1_20260902_local_r2/f1_d0_uid_context_phase_owner_conservation.csv.gz")
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINNED = {
    "diagnostic": (DIAGNOSTIC_REL, "3adb43c349b59bc85a66024ef2533796081cca935a0f92ccd88cee008e7ca3be"),
    "d0_census": (D0_REL, "c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9"),
    "embeddings": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "probe_state": (STAGE_REL / "ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
    "threshold_marker": (STAGE_REL / "ckda_d1_threshold_freeze_marker.json", "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"),
}
FROZEN_UIDS = (
    "ton:ckbt_01dad899cff4388f69a7",
    "ton:ckbt_03cee2b1ee1f725a3cc7",
    "ton:ckbt_2430e72b8306da7ee37a",
    "ton:ckbt_2f8a4b08f3ad6eaaeeea",
    "ton:ckbt_31ba7d482a97ce8eb9d6",
)
EXPECTED_ROWS = 25467
EXPECTED_DIM = 768
THRESHOLD = 0.065159872174263


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
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}


def atomic_text(path: Path, value: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
    os.replace(str(temp), str(path))


def atomic_json(path: Path, value: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(str(temp), str(path))


def read_frozen_allowlist(path: Path) -> Tuple[str, ...]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    uids = tuple(sorted(row["uid"] for row in rows))
    if uids != FROZEN_UIDS or len(rows) != 5 or len(set(uids)) != 5:
        raise RuntimeError("F1_D1_FIVE_MARGIN_IDENTITY_OR_SCOPE_FAILURE")
    return uids


def qualify_d0(path: Path, allowlist: Set[str]) -> Dict[str, Dict[str, str]]:
    found: Dict[str, Dict[str, str]] = {}
    seen: Set[str] = set()
    with gzip.open(str(path), "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"uid", "phase", "owner", "label_kind", "legal_fit", "source_group", "attack_family"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("D0 census schema drift")
        for row in reader:
            uid = row["uid"]
            if uid in seen:
                raise RuntimeError("duplicate UID in D0 census")
            seen.add(uid)
            if uid in allowlist:
                expected = (
                    row["phase"] == "fit" and row["owner"] == "A" and
                    row["label_kind"] == "attack" and row["legal_fit"].lower() == "true" and
                    row["source_group"] == "normal_scanning1.pcap" and
                    row["attack_family"] == "ToN-reconnaissance_scan"
                )
                if not expected:
                    raise RuntimeError("F1_D1_FIVE_MARGIN_IDENTITY_OR_SCOPE_FAILURE")
                found[uid] = row
    if len(seen) != EXPECTED_ROWS or set(found) != allowlist:
        raise RuntimeError("F1_D1_FIVE_MARGIN_IDENTITY_OR_SCOPE_FAILURE")
    return found


def read_npy_header(handle: io.BufferedIOBase) -> Tuple[Tuple[int, ...], bool, np.dtype]:
    version = np.lib.format.read_magic(handle)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
    elif version in ((2, 0), (3, 0)):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
    else:
        raise RuntimeError("unsupported NPY version")
    return tuple(shape), bool(fortran), np.dtype(dtype)


def stream_rows(npz_path: Path, indices: Sequence[int], expected_rows: int = EXPECTED_ROWS,
                expected_dim: int = EXPECTED_DIM) -> Tuple[np.ndarray, Dict[str, int]]:
    wanted = sorted(int(value) for value in indices)
    if len(wanted) != 5 or len(set(wanted)) != 5 or wanted[0] < 0 or wanted[-1] >= expected_rows:
        raise RuntimeError("five-row representation index drift")
    wanted_set = set(wanted)
    retained: List[np.ndarray] = []
    with zipfile.ZipFile(str(npz_path), "r") as archive:
        if "representation.npy" not in archive.namelist():
            raise RuntimeError("representation.npy missing")
        with archive.open("representation.npy", "r") as raw:
            shape, fortran, dtype = read_npy_header(raw)
            if shape != (expected_rows, expected_dim) or fortran or dtype.kind != "f" or dtype.itemsize != 4:
                raise RuntimeError("representation layout drift")
            row_bytes = expected_dim * dtype.itemsize
            for index in range(expected_rows):
                block = raw.read(row_bytes)
                if len(block) != row_bytes:
                    raise RuntimeError("truncated representation member")
                if index in wanted_set:
                    retained.append(np.frombuffer(block, dtype=dtype, count=expected_dim).copy())
            if raw.read(1) != b"":
                raise RuntimeError("representation trailing bytes")
    if len(retained) != 5:
        raise RuntimeError("five-row extraction incomplete")
    return np.stack(retained).astype(np.float32, copy=False), {
        "representation_container_rows_streamed_as_opaque_bytes": expected_rows,
        "representation_rows_numeric_decoded": 5,
        "nonallowlisted_representation_rows_numeric_decoded": 0,
    }


def p2_logits_scores(representations: np.ndarray, state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    if mean.shape != (EXPECTED_DIM,) or scale.shape != (EXPECTED_DIM,) or np.any(scale <= 0):
        raise RuntimeError("normalizer drift")
    x = (np.asarray(representations, dtype=np.float64) - mean) / scale
    x = np.concatenate((x, np.zeros((len(x), 1), dtype=np.float64)), axis=1)
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float64)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float64)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float64).reshape(-1)
    b2 = float(np.asarray(state["p2__3.bias"], dtype=np.float64).reshape(-1)[0])
    if w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (128,):
        raise RuntimeError("P2 state drift")
    hidden = np.maximum(0.0, x.dot(w1.T) + b1)
    logits = hidden.dot(w2) + b2
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))
    if logits.shape != (5,) or not np.isfinite(logits).all() or not np.isfinite(scores).all():
        raise RuntimeError("five-row P2 output malformed")
    return logits, scores


def category(score: float, threshold: float = THRESHOLD) -> str:
    margin = score - threshold
    if score == threshold or score == float(np.nextafter(threshold, math.inf)):
        return "EXACT_OR_ULP"
    if 0.0 < margin <= 0.001:
        return "NEAR_0P1PP"
    if 0.001 < margin < 0.05:
        return "INTERMEDIATE"
    if margin >= 0.05:
        return "STRONG_5PP"
    return "NOT_HARD"


def write_sha256s(output_dir: Path) -> None:
    lines = ["%s  %s" % (sha256_file(path), path.name)
             for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
             if path.is_file() and path.name != "SHA256SUMS"]
    atomic_text(output_dir / "SHA256SUMS", "\n".join(lines) + "\n")


def materialize(repo_root: Path, output_dir: Path) -> Dict[str, object]:
    stage = output_dir.with_name(".%s.stage" % output_dir.name)
    if output_dir.exists() or stage.exists():
        raise RuntimeError("refusing to overwrite output")
    stage.mkdir(parents=True)
    try:
        identities: Dict[str, object] = {"contract": require_sha(repo_root / CONTRACT_REL, CONTRACT_SHA256)}
        for name, (relative, digest) in PINNED.items():
            identities[name] = require_sha(repo_root / relative, digest)
        uids = read_frozen_allowlist(repo_root / DIAGNOSTIC_REL)
        qualify_d0(repo_root / D0_REL, set(uids))
        embedding_path = repo_root / PINNED["embeddings"][0]
        with np.load(str(embedding_path), allow_pickle=False) as data:
            container_uids = np.asarray(data["uid"]).astype(str)
            missing = np.asarray(data["missing"], dtype=bool)
        if len(container_uids) != EXPECTED_ROWS or len(set(container_uids)) != EXPECTED_ROWS:
            raise RuntimeError("embedding UID identity drift")
        position = {uid: index for index, uid in enumerate(container_uids)}
        if not set(uids).issubset(position):
            raise RuntimeError("allowlisted UID absent")
        index_by_uid = {uid: position[uid] for uid in uids}
        selected = [index_by_uid[uid] for uid in uids]
        if bool(missing[np.asarray(selected, dtype=np.int64)].any()):
            raise RuntimeError("allowlisted row is missing")
        values_by_index, stream_audit = stream_rows(embedding_path, selected)
        # stream_rows emits numeric rows in container-index order; restore lexical UID order.
        ordered_indices = sorted(selected)
        row_by_index = {index: values_by_index[offset] for offset, index in enumerate(ordered_indices)}
        values = np.stack([row_by_index[index_by_uid[uid]] for uid in uids])
        with np.load(str(repo_root / PINNED["probe_state"][0]), allow_pickle=False) as data:
            state = {name: np.asarray(data[name]) for name in data.files}
        logits, scores = p2_logits_scores(values, state)
        marker = json.loads((repo_root / PINNED["threshold_marker"][0]).read_text(encoding="utf-8"))
        if float(marker["thresholds"]["P2"]["value"]) != THRESHOLD:
            raise RuntimeError("threshold identity drift")
        logit_threshold = math.log(THRESHOLD / (1.0 - THRESHOLD))
        rows: List[Dict[str, object]] = []
        categories: Dict[str, int] = {}
        for uid, logit, score in zip(uids, logits.tolist(), scores.tolist()):
            hard = score >= THRESHOLD
            if not hard:
                raise RuntimeError("incumbent hard identity failure")
            descriptor = category(score)
            categories[descriptor] = categories.get(descriptor, 0) + 1
            rows.append({
                "uid": uid, "incumbent_logit": format(logit, ".17g"),
                "incumbent_score": format(score, ".17g"), "threshold": format(THRESHOLD, ".15f"),
                "score_margin": format(score - THRESHOLD, ".17g"),
                "logit_threshold": format(logit_threshold, ".17g"),
                "logit_margin": format(logit - logit_threshold, ".17g"),
                "incumbent_hard": "true",
            })
        fields = ["uid", "incumbent_logit", "incumbent_score", "threshold", "score_margin",
                  "logit_threshold", "logit_margin", "incumbent_hard"]
        atomic_csv(stage / "f1_d1_incumbent_five_margins.csv", fields, rows)
        margins = np.asarray(scores) - THRESHOLD
        summary = {
            "status": "F1_D1_INCUMBENT_FIVE_MARGIN_MATERIALIZED",
            "rows": 5, "incumbent_hard_rows": 5, "categories": categories,
            "minimum_score": float(np.min(scores)), "median_score": float(np.median(scores)),
            "maximum_score": float(np.max(scores)), "minimum_score_margin": float(np.min(margins)),
            "median_score_margin": float(np.median(margins)), "maximum_score_margin": float(np.max(margins)),
            "threshold": THRESHOLD, "decision_rule": "score >= threshold; exact ties hard",
            "identities": identities,
        }
        atomic_json(stage / "f1_d1_incumbent_five_margin_summary.json", summary)
        boundary = {
            "status": "PASS", **stream_audit,
            "select_scores_opened": 0, "nonallowlisted_numeric_rows": 0,
            "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
            "pcap_opened": 0, "parameters_fitted": 0, "optimizer_steps": 0,
            "training_or_resume_started": 0, "representations_persisted": 0,
        }
        atomic_json(stage / "f1_d1_incumbent_five_margin_boundary_audit.json", boundary)
        write_sha256s(stage)
        os.replace(str(stage), str(output_dir))
        return summary
    except Exception:
        shutil.rmtree(str(stage), ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    summary = materialize(args.repo_root.resolve(), args.output_dir.resolve())
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
