#!/usr/bin/env python3
"""Materialize incumbent P2 hard/normal counts for legal-fit benign owner-A.

Only allowlisted representation rows are converted from opaque NPY bytes into
numeric arrays.  No score value is persisted and no parameter is fitted.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import os
import shutil
import traceback
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

import numpy as np


CONTRACT_REL = Path(
    "runs/mainline_docs/"
    "frontend_f1_teacher_benign_count_only_materialization_frozen_20260902.md"
)
CONTRACT_SHA256 = "019c6e8864d0029c224de94b93d96edd8f3a6bf4f8c2bc92a1f52c59d028526b"
D0_ALLOWLIST_REL = Path(
    "runs/frontend_f1_d0_census_v1_20260901_local/"
    "f1_d0_uid_context_phase_owner_conservation.csv.gz"
)
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")

PINNED = {
    "d0_allowlist": (
        D0_ALLOWLIST_REL,
        "c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9",
    ),
    "embeddings": (
        STAGE_REL / "ckda_d1_fit_select_embeddings.npz",
        "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099",
    ),
    "probe_state": (
        STAGE_REL / "ckda_d1_probe_state.npz",
        "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38",
    ),
    "threshold_marker": (
        STAGE_REL / "ckda_d1_threshold_freeze_marker.json",
        "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b",
    ),
}

EXPECTED_CONTAINER_ROWS = 25467
EXPECTED_AUTHORIZED_ROWS = 7347
EXPECTED_DIM = 768
THETA_0 = 0.065159872174263


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


def atomic_text(path: Path, text: str) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with temp.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temp), str(path))


def atomic_json(path: Path, payload: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def atomic_gzip_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temp = path.with_name(".%s.tmp" % path.name)
    with gzip.open(str(temp), "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(str(temp), str(path))


def read_authorized_uids(path: Path) -> List[str]:
    selected: List[str] = []
    all_uids: Set[str] = set()
    with gzip.open(str(path), "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"uid", "legal_fit", "owner", "label_kind", "phase"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("D0 allowlist schema drift")
        for row in reader:
            uid = row["uid"]
            if uid in all_uids:
                raise RuntimeError("duplicate UID in D0 allowlist")
            all_uids.add(uid)
            legal = row["legal_fit"].strip().lower() == "true"
            if legal and row["owner"] == "A" and row["label_kind"] == "benign":
                if row["phase"] != "fit":
                    raise RuntimeError("legal-fit benign allowlist contains non-fit row")
                selected.append(uid)
    if len(all_uids) != EXPECTED_CONTAINER_ROWS or len(selected) != EXPECTED_AUTHORIZED_ROWS:
        raise RuntimeError("F1_TEACHER_BENIGN_DENOMINATOR_FAILURE")
    if len(set(selected)) != len(selected):
        raise RuntimeError("authorized UID duplication")
    return selected


def read_npy_header(handle: io.BufferedIOBase) -> Tuple[Tuple[int, ...], bool, np.dtype]:
    version = np.lib.format.read_magic(handle)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
    elif version == (2, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
    elif version == (3, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
    else:
        raise RuntimeError("unsupported NPY version: %s" % (version,))
    return tuple(shape), bool(fortran), np.dtype(dtype)


def stream_selected_representation_rows(
    npz_path: Path, selected_indices: Sequence[int]
) -> Tuple[np.ndarray, Dict[str, int]]:
    wanted = sorted(int(value) for value in selected_indices)
    if len(wanted) != EXPECTED_AUTHORIZED_ROWS or len(set(wanted)) != len(wanted):
        raise RuntimeError("authorized representation index drift")
    if wanted[0] < 0 or wanted[-1] >= EXPECTED_CONTAINER_ROWS:
        raise RuntimeError("authorized representation index out of range")
    wanted_set = set(wanted)
    retained: List[np.ndarray] = []
    with zipfile.ZipFile(str(npz_path), "r") as archive:
        names = set(archive.namelist())
        if "representation.npy" not in names:
            raise RuntimeError("representation.npy missing from frozen container")
        with archive.open("representation.npy", "r") as raw:
            shape, fortran, dtype = read_npy_header(raw)
            if shape != (EXPECTED_CONTAINER_ROWS, EXPECTED_DIM) or fortran:
                raise RuntimeError("representation shape/order drift")
            if dtype != np.dtype("<f4") and dtype != np.dtype("=f4"):
                raise RuntimeError("representation dtype drift")
            row_bytes = EXPECTED_DIM * dtype.itemsize
            for index in range(EXPECTED_CONTAINER_ROWS):
                block = raw.read(row_bytes)
                if len(block) != row_bytes:
                    raise RuntimeError("truncated representation member")
                if index in wanted_set:
                    retained.append(np.frombuffer(block, dtype=dtype, count=EXPECTED_DIM).copy())
            if raw.read(1) != b"":
                raise RuntimeError("representation member has trailing bytes")
    if len(retained) != EXPECTED_AUTHORIZED_ROWS:
        raise RuntimeError("authorized representation extraction incomplete")
    values = np.stack(retained, axis=0).astype(np.float32, copy=False)
    return values, {
        "representation_container_rows_streamed_as_opaque_bytes": EXPECTED_CONTAINER_ROWS,
        "representation_rows_numeric_decoded": len(retained),
        "nonallowlisted_representation_rows_numeric_decoded": 0,
    }


def frozen_p2_scores(representations: np.ndarray, state: Mapping[str, np.ndarray]) -> np.ndarray:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    if mean.shape != (EXPECTED_DIM,) or scale.shape != (EXPECTED_DIM,) or np.any(scale <= 0):
        raise RuntimeError("frozen normalizer shape/value drift")
    values = (np.asarray(representations, dtype=np.float64) - mean) / scale
    missing = np.zeros((len(values), 1), dtype=np.float64)
    x = np.concatenate((values, missing), axis=1)
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float64)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float64)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float64).reshape(-1)
    b2 = float(np.asarray(state["p2__3.bias"], dtype=np.float64).reshape(-1)[0])
    if w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (128,):
        raise RuntimeError("frozen P2 shape drift")
    hidden = np.maximum(0.0, x.dot(w1.T) + b1)
    logits = hidden.dot(w2) + b2
    scores = 1.0 / (1.0 + np.exp(-np.clip(logits, -700.0, 700.0)))
    if scores.shape != (EXPECTED_AUTHORIZED_ROWS,) or not np.isfinite(scores).all():
        raise RuntimeError("authorized P2 score vector malformed")
    return scores


def write_sha256s(output_dir: Path) -> None:
    rows = []
    for path in sorted(output_dir.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "SHA256SUMS":
            rows.append("%s  %s" % (sha256_file(path), path.name))
    atomic_text(output_dir / "SHA256SUMS", "\n".join(rows) + "\n")


def materialize(repo_root: Path, output_dir: Path) -> Dict[str, object]:
    stage_out = output_dir.with_name(".%s.stage" % output_dir.name)
    control = output_dir.with_name("%s_control" % output_dir.name)
    if output_dir.exists() or stage_out.exists():
        raise RuntimeError("refusing to overwrite teacher-benign output")
    if control.exists():
        shutil.rmtree(str(control))
    stage_out.mkdir(parents=True, exist_ok=False)
    try:
        identities: Dict[str, object] = {
            "contract": require_sha(repo_root / CONTRACT_REL, CONTRACT_SHA256)
        }
        for key, (relative, digest) in PINNED.items():
            identities[key] = require_sha(repo_root / relative, digest)

        authorized_uids = read_authorized_uids(repo_root / D0_ALLOWLIST_REL)
        authorized_set = set(authorized_uids)
        embedding_path = repo_root / PINNED["embeddings"][0]
        with np.load(str(embedding_path), allow_pickle=False) as data:
            if "uid" not in data.files or "missing" not in data.files:
                raise RuntimeError("frozen embedding identity arrays missing")
            container_uids = np.asarray(data["uid"]).astype(str)
            missing = np.asarray(data["missing"], dtype=bool)
        if len(container_uids) != EXPECTED_CONTAINER_ROWS or len(set(container_uids)) != len(container_uids):
            raise RuntimeError("embedding UID identity drift")
        if missing.shape != (EXPECTED_CONTAINER_ROWS,):
            raise RuntimeError("embedding missing vector drift")
        positions = {uid: index for index, uid in enumerate(container_uids)}
        if not authorized_set.issubset(set(positions)):
            raise RuntimeError("authorized UID absent from embedding container")
        selected_indices = [positions[uid] for uid in authorized_uids]
        if bool(missing[np.asarray(selected_indices, dtype=np.int64)].any()):
            raise RuntimeError("owner-A allowlist contains missing embedding")

        representations, stream_audit = stream_selected_representation_rows(
            embedding_path, selected_indices
        )
        with np.load(str(repo_root / PINNED["probe_state"][0]), allow_pickle=False) as data:
            state = {name: np.asarray(data[name]) for name in data.files}
        scores = frozen_p2_scores(representations, state)

        marker = json.loads((repo_root / PINNED["threshold_marker"][0]).read_text(encoding="utf-8"))
        theta = float(marker["thresholds"]["P2"]["value"])
        if theta != THETA_0:
            raise RuntimeError("frozen P2 threshold drift")
        hard = np.asarray(scores >= theta, dtype=bool)
        hard_rows = int(hard.sum())
        normal_rows = int(len(hard) - hard_rows)
        if hard_rows + normal_rows != EXPECTED_AUTHORIZED_ROWS:
            raise RuntimeError("teacher-benign verdict conservation failure")

        uid_rows = [
            {"uid": uid, "hard": str(bool(value)).lower()}
            for uid, value in sorted(zip(authorized_uids, hard.tolist()), key=lambda item: item[0])
        ]
        atomic_gzip_csv(
            stage_out / "f1_teacher_benign_uid_verdicts.csv.gz",
            ["uid", "hard"],
            uid_rows,
        )
        counts = {
            "status": "F1_TEACHER_BENIGN_COUNTS_MATERIALIZED",
            "authorized_rows": EXPECTED_AUTHORIZED_ROWS,
            "hard_rows": hard_rows,
            "normal_rows": normal_rows,
            "conservation_hard_plus_normal_equals_rows": hard_rows + normal_rows == EXPECTED_AUTHORIZED_ROWS,
            "threshold": THETA_0,
            "threshold_canonical": "0.065159872174263",
            "decision_rule": "score >= threshold; exact ties hard",
            "score_values_persisted": 0,
        }
        atomic_json(stage_out / "f1_teacher_benign_counts.json", counts)
        atomic_json(
            stage_out / "f1_teacher_benign_input_audit.json",
            {
                "status": "PASS",
                "identities": identities,
                "container_rows": EXPECTED_CONTAINER_ROWS,
                "authorized_uids": len(authorized_uids),
                "authorized_uids_found": len(selected_indices),
                "authorized_missing_rows": int(missing[np.asarray(selected_indices, dtype=np.int64)].sum()),
                "exact_uid_join": True,
            },
        )
        boundary = {
            "status": "PASS",
            **stream_audit,
            "authorized_fit_benign_scores_computed": len(scores),
            "select_scores_computed": 0,
            "cross_phase_fit_scores_computed": 0,
            "attack_scores_computed": 0,
            "owner_b_scores_computed": 0,
            "viewed_scores_computed": 0,
            "report_scores_computed": 0,
            "final_scores_computed": 0,
            "score_values_persisted": 0,
            "representations_persisted": 0,
            "parameters_fitted": 0,
            "optimizer_steps": 0,
            "thresholds_selected": 0,
            "pcap_files_opened": 0,
            "training_started": 0,
        }
        atomic_json(stage_out / "f1_teacher_benign_boundary_audit.json", boundary)
        atomic_json(
            stage_out / "f1_teacher_benign_validation_report.json",
            {
                "status": "PASS",
                "contract_sha256": CONTRACT_SHA256,
                "authorized_rows": EXPECTED_AUTHORIZED_ROWS,
                "hard_rows": hard_rows,
                "normal_rows": normal_rows,
                "uid_audit_rows": len(uid_rows),
                "scientific_verdict_emitted": True,
            },
        )
        write_sha256s(stage_out)
        os.replace(str(stage_out), str(output_dir))
        return counts
    except Exception as exc:
        if stage_out.exists():
            shutil.rmtree(str(stage_out))
        control.mkdir(parents=True, exist_ok=True)
        atomic_json(
            control / "engineering_failure.json",
            {
                "status": "ENGINEERING_FAILURE_NO_SCIENTIFIC_VERDICT",
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    verdict = materialize(args.repo_root.resolve(), args.output_dir.resolve())
    print(json.dumps(verdict, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
