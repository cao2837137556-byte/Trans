#!/usr/bin/env python3
"""Training-only incumbent-logit audit for Frontend-F2 feasibility."""

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
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Set, Tuple

import numpy as np
import torch


CONTRACT_REL = Path("runs/mainline_docs/frontend_f2_old_function_preservation_d0_frozen_20260904.md")
CONTRACT_SHA = "2a2b323a383de391c272bdc01dff1716819f25615dd6c0545a91723c38011a54"
ERRATUM_REL = Path("runs/mainline_docs/frontend_f2_old_function_preservation_d0_numeric_semantics_erratum_frozen_20260904.md")
ERRATUM_SHA = "c573ef26df6bf559b5c4006d0a0aa284c760a600294f059d1a0b102c1e997e49"
STRUCTURAL_REL = Path("runs/mainline_docs/frontend_f2_old_function_preservation_d0_structural_addendum_frozen_20260904.md")
STRUCTURAL_SHA = "06103319735b996d02ec799876d0b4930aa6fcb4a2716b40f05b4afcebdbdc49"
D0_REL = Path("runs/frontend_f1_d0_census_v1_20260902_local_r2/f1_d0_uid_context_phase_owner_conservation.csv.gz")
FIT_CONTEXT_REL = Path("runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_contexts.jsonl.gz")
TEACHER_REL = Path("runs/frontend_f1_teacher_benign_count_only_v1_20260902_local/f1_teacher_benign_uid_verdicts.csv.gz")
STAGE_REL = Path("runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage")
NUMERICAL_REL = Path("runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md")

PINNED = {
    "numerical_contract": (NUMERICAL_REL, "7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860"),
    "d0_census": (D0_REL, "c02937de7c5660688c60578adb2801f5a12b709745652fa8303b6c8e0d0b0ae9"),
    "fit_context_corpus": (FIT_CONTEXT_REL, "623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e"),
    "teacher_benign": (TEACHER_REL, "f7deceac0ac76fb25e577714f7a94da047e15ed77cb9bee19a9ea9c2954c493b"),
    "embeddings": (STAGE_REL / "ckda_d1_fit_select_embeddings.npz", "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"),
    "probe_state": (STAGE_REL / "ckda_d1_probe_state.npz", "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38"),
    "threshold_marker": (STAGE_REL / "ckda_d1_threshold_freeze_marker.json", "84576a5008259f4381c46eecbc3ee3bda9d06b9dc7068cd52d7c2232e884dd5b"),
    "formal_ckda_implementation": (Path("repo/ood/issue27ckda_d1_representation_probe_v1.py"), "f8f477ca78d8ed1fa490880d24a01f65111e3f910eaa8ab72af154d8a143de4e"),
    "f1_wrapper_implementation": (Path("repo/ood/issue27frontend_f1_d1_train_v1.py"), "6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634"),
}
VAL_SOURCES = {
    "normal_scanning1.pcap",
    "iotsim-combined-cycle-3_0-0_to_OpenvSwitch-13_3-0",
    "iotsim-combined-cycle-7_0-0_to_OpenvSwitch-13_7-0",
    "iotsim-combined-cycle-8_0-0_to_OpenvSwitch-13_8-0",
    "iotsim-domotic-monitor-2_0-0_to_OpenvSwitch-23_2-0",
}
EXPECTED_CONTAINER_ROWS = 25467
EXPECTED_ROWS = 8353
EXPECTED_CONTEXTS = 4994
EXPECTED_ATTACK = 2182
EXPECTED_BENIGN = 6171
EXPECTED_CORRECT_BENIGN = 6145
EXPECTED_WRONG_BENIGN = 26
EXPECTED_DIM = 768
THRESHOLD = 0.065159872174263
Z0 = -2.6635317063752599
Z_P99 = 4.595119850134589
Z_P01 = -4.59511985013459
EXPECTED_PARENT_TRAIN_ROWS = 13866
EXPECTED_PARENT_TRAIN_CONTEXTS = 9307
VOCABULARY_SHA = "e5ca926798949ca0da1c87795d38aec9fc10c17ae52ecc844a489a98781efd4c"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError("SHA256 mismatch: %s" % path)
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}


def atomic_text(path: Path, value: str) -> None:
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: Mapping[str, object]) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(str(temporary), str(path))


def atomic_gzip_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as binary:
        with gzip.GzipFile(filename="", mode="wb", fileobj=binary, mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
    os.replace(str(temporary), str(path))


def canonical_json_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def build_vocabulary(contexts: Sequence[Mapping[str, object]]) -> Tuple[Dict[str, int], str]:
    observed: Set[str] = set()
    for context in contexts:
        if str(context["split"]) == "train":
            observed.update(str(value) for value in context["signatures"])  # type: ignore[arg-type]
    if len(observed) > 4094:
        raise RuntimeError("vocabulary capacity drift")
    ordered = sorted(observed, key=lambda value: (hashlib.sha256(value.encode("utf-8")).digest(), value.encode("utf-8")))
    vocabulary = {signature: index + 2 for index, signature in enumerate(ordered)}
    identity = sha256_value({"PAD": 0, "UNK": 1, "items": ordered})
    return vocabulary, identity


def read_context_corpus(path: Path) -> List[Dict[str, object]]:
    contexts: List[Dict[str, object]] = []
    keys: Set[str] = set()
    with gzip.open(str(path), "rt", encoding="utf-8") as handle:
        for line in handle:
            value = json.loads(line)
            key = str(value["context_key"])
            if key in keys:
                raise RuntimeError("context corpus duplication")
            keys.add(key)
            expected_split = "internal_val" if str(value["source_group"]) in VAL_SOURCES else "train"
            if str(value["split"]) != expected_split:
                raise RuntimeError("context split drift")
            contexts.append(value)
    return contexts


def nested_source_split(parent_train: Sequence[Mapping[str, object]]) -> Dict[str, str]:
    labels_by_source: Dict[str, Set[int]] = defaultdict(set)
    for context in parent_train:
        source = str(context["source_group"])
        for target in context["targets"]:  # type: ignore[assignment]
            labels_by_source[source].add(int(target["label"]))
    by_stratum: Dict[str, List[Tuple[bytes, str]]] = defaultdict(list)
    for source, labels in labels_by_source.items():
        stratum = "attack_present" if 1 in labels else "benign_only"
        payload = ("frontend-f2-d1-internal-val-v1\0%s\0%s" % (stratum, source)).encode("utf-8")
        by_stratum[stratum].append((hashlib.sha256(payload).digest(), source))
    result: Dict[str, str] = {}
    for stratum in sorted(by_stratum):
        ordered = sorted(by_stratum[stratum], key=lambda item: (item[0], item[1]))
        validation_count = max(1, int(math.ceil(len(ordered) / 5.0)))
        validation = {source for _, source in ordered[:validation_count]}
        for _, source in ordered:
            result[source] = "internal_val" if source in validation else "train"
    return result


def structural_audit(contexts: Sequence[Mapping[str, object]]) -> Dict[str, object]:
    vocabulary, vocabulary_sha = build_vocabulary(contexts)
    if vocabulary_sha != VOCABULARY_SHA:
        raise RuntimeError("F2 D0 vocabulary identity drift")
    parent_train = [context for context in contexts if str(context["split"]) == "train"]
    target_rows: List[Dict[str, object]] = []
    for context in parent_train:
        signatures = [str(value) for value in context["signatures"]]  # type: ignore[arg-type]
        tokens = [int(vocabulary.get(signature, 1)) for signature in signatures]
        for target in context["targets"]:  # type: ignore[assignment]
            event_index = int(target["event_index"])
            if event_index < 0 or event_index >= len(signatures):
                raise RuntimeError("target event index drift")
            target_rows.append({
                "uid": str(target["uid"]), "context_key": str(context["context_key"]),
                "source_group": str(target["source_group"]), "device_family": str(target["device_family"]),
                "attack_family": str(target["attack_family"]), "owner": str(target["owner"]),
                "label": int(target["label"]), "teacher_kind": str(target["teacher_kind"]),
                "canonical_prefix_sha": sha256_value(signatures[:event_index + 1]),
                "token_prefix_sha": sha256_value(tokens[:event_index + 1]),
            })
    if len(parent_train) != EXPECTED_PARENT_TRAIN_CONTEXTS or len(target_rows) != EXPECTED_PARENT_TRAIN_ROWS:
        raise RuntimeError("parent train corpus conservation drift")

    conflict_rows: List[Dict[str, object]] = []
    conflict_counts: Dict[str, int] = {}
    hard_token_buckets: Set[str] = set()
    for identity_field in ("canonical_prefix_sha", "token_prefix_sha"):
        buckets: Dict[str, List[Dict[str, object]]] = defaultdict(list)
        for row in target_rows:
            buckets[str(row[identity_field])].append(row)
        conflict_buckets = 0
        for digest, members in sorted(buckets.items()):
            labels = {int(row["label"]) for row in members}
            if len(labels) < 2:
                continue
            conflict_buckets += 1
            hard = (
                any(row["owner"] == "A" and row["teacher_kind"] == "attack_hard" for row in members) and
                any(row["owner"] == "A" and row["teacher_kind"] == "benign_normal" for row in members)
            )
            if identity_field == "token_prefix_sha" and hard:
                hard_token_buckets.add(digest)
            for row in members:
                conflict_rows.append({
                    "identity_type": identity_field, "prefix_sha256": digest,
                    "bucket_rows": len(members), "bucket_attack_rows": sum(int(x["label"]) == 1 for x in members),
                    "bucket_benign_rows": sum(int(x["label"]) == 0 for x in members),
                    "hard_protected_conflict": str(hard).lower(),
                    "uid": row["uid"], "context_key": row["context_key"], "source_group": row["source_group"],
                    "device_family": row["device_family"], "attack_family": row["attack_family"],
                    "owner": row["owner"], "label": row["label"], "teacher_kind": row["teacher_kind"],
                })
        conflict_counts[identity_field] = conflict_buckets

    split_by_source = nested_source_split(parent_train)
    nested_rows: List[Dict[str, object]] = []
    nested_counts: Dict[Tuple[str, str, int, str, str, str], Set[str]] = defaultdict(set)
    nested_row_counts: Dict[Tuple[str, str, int, str, str, str], int] = defaultdict(int)
    eligibility = defaultdict(int)
    for context in parent_train:
        nested = split_by_source[str(context["source_group"])]
        for target in context["targets"]:  # type: ignore[assignment]
            key = (nested, str(target["owner"]), int(target["label"]), str(target["teacher_kind"]),
                   str(target["source_group"]), str(target["attack_family"]))
            nested_row_counts[key] += 1
            nested_counts[key].add(str(context["context_key"]))
            if str(target["owner"]) == "A" and str(target["teacher_kind"]) == "attack_hard":
                eligibility[(nested, "a_correct_attack")] += 1
            if str(target["owner"]) == "A" and str(target["teacher_kind"]) == "benign_normal":
                eligibility[(nested, "a_correct_benign")] += 1
            if str(target["owner"]) == "B" and int(target["label"]) == 0:
                eligibility[(nested, "b_benign")] += 1
            if str(target["owner"]) == "B" and int(target["label"]) == 1:
                eligibility[(nested, "b_attack")] += 1
    for key in sorted(nested_row_counts):
        nested_rows.append({
            "nested_split": key[0], "owner": key[1], "label": key[2], "teacher_kind": key[3],
            "source_group": key[4], "attack_family": key[5], "rows": nested_row_counts[key],
            "contexts": len(nested_counts[key]),
        })
    split_feasible = all(eligibility[(split, kind)] > 0 for split in ("train", "internal_val")
                         for kind in ("a_correct_attack", "a_correct_benign"))
    split_feasible = split_feasible and eligibility[("train", "b_benign")] > 0 and eligibility[("train", "b_attack")] > 0
    return {
        "vocabulary_sha256": vocabulary_sha, "parent_train_rows": len(target_rows),
        "parent_train_contexts": len(parent_train), "conflict_counts": conflict_counts,
        "hard_protected_token_conflict_buckets": len(hard_token_buckets),
        "input_identifiable": len(hard_token_buckets) == 0,
        "conflict_rows": conflict_rows, "nested_rows": nested_rows,
        "nested_split": {
            "train_sources": sorted(source for source, split in split_by_source.items() if split == "train"),
            "internal_validation_sources": sorted(source for source, split in split_by_source.items() if split == "internal_val"),
            "eligibility_row_counts": {"%s|%s" % key: value for key, value in sorted(eligibility.items())},
            "split_feasible": bool(split_feasible),
        },
        "parent_train_a_uids": sorted(str(row["uid"]) for row in target_rows if row["owner"] == "A"),
    }


def read_authorized_rows(path: Path) -> List[Dict[str, str]]:
    selected: List[Dict[str, str]] = []
    all_uids: Set[str] = set()
    all_rows = 0
    with gzip.open(str(path), "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "uid", "semantic_context_key", "phase", "owner", "label_kind", "role",
            "source_group", "device_family", "attack_family", "legal_fit",
        }
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise RuntimeError("D0 schema drift")
        for row in reader:
            all_rows += 1
            uid = row["uid"]
            if uid in all_uids:
                raise RuntimeError("D0 UID duplication")
            all_uids.add(uid)
            legal = row["legal_fit"].strip().lower() == "true"
            if legal and row["owner"] == "A" and row["source_group"] not in VAL_SOURCES:
                if row["phase"] != "fit":
                    raise RuntimeError("authorized row is not fit")
                selected.append(dict(row))
    labels = {name: sum(row["label_kind"] == name for row in selected) for name in ("attack", "benign")}
    contexts = len({row["semantic_context_key"] for row in selected})
    if (all_rows != EXPECTED_CONTAINER_ROWS or len(selected) != EXPECTED_ROWS or
            labels != {"attack": EXPECTED_ATTACK, "benign": EXPECTED_BENIGN} or
            contexts != EXPECTED_CONTEXTS):
        raise RuntimeError("F2_D0_TEACHER_IDENTITY_OR_SCOPE_FAILURE")
    return sorted(selected, key=lambda row: row["uid"])


def read_teacher_benign(path: Path) -> Dict[str, bool]:
    result: Dict[str, bool] = {}
    with gzip.open(str(path), "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None or set(reader.fieldnames) != {"uid", "hard"}:
            raise RuntimeError("teacher benign schema drift")
        for row in reader:
            if row["uid"] in result:
                raise RuntimeError("teacher benign UID duplication")
            result[row["uid"]] = row["hard"].strip().lower() == "true"
    if len(result) != 7347:
        raise RuntimeError("teacher benign denominator drift")
    return result


def read_npy_header(handle: io.BufferedIOBase) -> Tuple[Tuple[int, ...], bool, np.dtype]:
    version = np.lib.format.read_magic(handle)
    if version == (1, 0):
        shape, fortran, dtype = np.lib.format.read_array_header_1_0(handle)
    elif version in ((2, 0), (3, 0)):
        shape, fortran, dtype = np.lib.format.read_array_header_2_0(handle)
    else:
        raise RuntimeError("unsupported NPY version")
    return tuple(shape), bool(fortran), np.dtype(dtype)


def stream_authorized_rows(npz_path: Path, indices: Sequence[int], expected_rows: int = EXPECTED_CONTAINER_ROWS,
                           expected_dim: int = EXPECTED_DIM) -> Tuple[np.ndarray, Dict[str, int]]:
    wanted = sorted(int(value) for value in indices)
    if len(wanted) != EXPECTED_ROWS or len(set(wanted)) != EXPECTED_ROWS:
        raise RuntimeError("authorized index denominator drift")
    if wanted[0] < 0 or wanted[-1] >= expected_rows:
        raise RuntimeError("authorized index out of range")
    wanted_set = set(wanted)
    retained: List[np.ndarray] = []
    with zipfile.ZipFile(str(npz_path), "r") as archive:
        if "representation.npy" not in archive.namelist():
            raise RuntimeError("representation.npy absent")
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
                raise RuntimeError("representation member trailing bytes")
    if len(retained) != EXPECTED_ROWS:
        raise RuntimeError("authorized extraction incomplete")
    return np.stack(retained).astype(np.float32, copy=False), {
        "representation_container_rows_streamed_as_opaque_bytes": expected_rows,
        "representation_rows_numeric_decoded": EXPECTED_ROWS,
        "nonauthorized_representation_rows_numeric_decoded": 0,
    }


def _p2_state(state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    w1 = np.asarray(state["p2__0.weight"], dtype=np.float32)
    b1 = np.asarray(state["p2__0.bias"], dtype=np.float32)
    w2 = np.asarray(state["p2__3.weight"], dtype=np.float32)
    b2 = np.asarray(state["p2__3.bias"], dtype=np.float32)
    if w1.shape != (128, 769) or b1.shape != (128,) or w2.shape != (1, 128) or b2.shape != (1,):
        raise RuntimeError("P2 state drift")
    return w1, b1, w2, b2


def _torch_p2(features: np.ndarray, state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    w1, b1, w2, b2 = _p2_state(state)
    with torch.inference_mode():
        x = torch.from_numpy(np.ascontiguousarray(features, dtype=np.float32))
        hidden = torch.relu(torch.nn.functional.linear(x, torch.from_numpy(w1), torch.from_numpy(b1)))
        logits_t = torch.nn.functional.linear(hidden, torch.from_numpy(w2), torch.from_numpy(b2)).reshape(-1)
        scores_t = torch.sigmoid(logits_t)
    logits = logits_t.cpu().numpy().astype(np.float64)
    scores = scores_t.cpu().numpy().astype(np.float64)
    if logits.shape != (EXPECTED_ROWS,) or not np.isfinite(logits).all() or not np.isfinite(scores).all():
        raise RuntimeError("P2 outputs malformed")
    return logits, scores


def canonical_p2_logits_scores(representations: np.ndarray, state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float64)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float64)
    if mean.shape != (EXPECTED_DIM,) or scale.shape != (EXPECTED_DIM,) or np.any(scale <= 0):
        raise RuntimeError("normalizer drift")
    normalized64 = (np.asarray(representations, dtype=np.float64) - mean) / scale
    features32 = np.column_stack((normalized64, np.zeros(len(normalized64), dtype=np.float64))).astype(np.float32)
    return _torch_p2(features32, state)


def f1_wrapper_p2_logits_scores(representations: np.ndarray, state: Mapping[str, np.ndarray]) -> Tuple[np.ndarray, np.ndarray]:
    mean = np.asarray(state["normalizer_mean"], dtype=np.float32)
    scale = np.asarray(state["normalizer_scale"], dtype=np.float32)
    if mean.shape != (EXPECTED_DIM,) or scale.shape != (EXPECTED_DIM,) or np.any(scale <= 0):
        raise RuntimeError("F1 normalizer drift")
    normalized32 = (np.asarray(representations, dtype=np.float32) - mean) / scale
    features32 = np.column_stack((normalized32, np.zeros(len(normalized32), dtype=np.float32)))
    return _torch_p2(features32, state)


def quantile(values: np.ndarray, probability: float, method: str) -> float:
    return float(np.quantile(np.asarray(values, dtype=np.float64), probability, method=method))


def summary_stats(values: np.ndarray) -> Dict[str, object]:
    values = np.asarray(values, dtype=np.float64)
    return {
        "count": int(len(values)), "minimum": float(np.min(values)),
        "q01": quantile(values, 0.01, "linear"), "q05": quantile(values, 0.05, "linear"),
        "q25": quantile(values, 0.25, "linear"), "q50": quantile(values, 0.50, "linear"),
        "q75": quantile(values, 0.75, "linear"), "q95": quantile(values, 0.95, "linear"),
        "q99": quantile(values, 0.99, "linear"), "maximum": float(np.max(values)),
    }


def write_sha256s(output_dir: Path) -> None:
    lines = ["%s  %s" % (sha256_file(path), path.name)
             for path in sorted(output_dir.iterdir(), key=lambda item: item.name)
             if path.is_file() and path.name != "SHA256SUMS"]
    atomic_text(output_dir / "SHA256SUMS", "\n".join(lines) + "\n")


def materialize(root: Path, output_dir: Path) -> Dict[str, object]:
    stage = output_dir.with_name(".%s.stage" % output_dir.name)
    if output_dir.exists() or stage.exists():
        raise RuntimeError("refusing to overwrite F2 D0 output")
    stage.mkdir(parents=True)
    try:
        identities: Dict[str, object] = {
            "contract": require_sha(root / CONTRACT_REL, CONTRACT_SHA),
            "numeric_semantics_erratum": require_sha(root / ERRATUM_REL, ERRATUM_SHA),
            "structural_addendum": require_sha(root / STRUCTURAL_REL, STRUCTURAL_SHA),
        }
        for name, (relative, digest) in PINNED.items():
            identities[name] = require_sha(root / relative, digest)
        rows = read_authorized_rows(root / D0_REL)
        teacher_benign = read_teacher_benign(root / TEACHER_REL)
        structure = structural_audit(read_context_corpus(root / FIT_CONTEXT_REL))
        parent_train_a_uids = structure.pop("parent_train_a_uids")
        if parent_train_a_uids != [row["uid"] for row in rows]:
            raise RuntimeError("D0 census / fit corpus A-train UID drift")
        conflict_rows = structure.pop("conflict_rows")
        nested_rows = structure.pop("nested_rows")
        nested_split = structure.pop("nested_split")
        atomic_json(stage / "f2_d0_input_identifiability.json", structure)
        conflict_fields = [
            "identity_type", "prefix_sha256", "bucket_rows", "bucket_attack_rows", "bucket_benign_rows",
            "hard_protected_conflict", "uid", "context_key", "source_group", "device_family",
            "attack_family", "owner", "label", "teacher_kind",
        ]
        atomic_csv(stage / "f2_d0_conflicting_prefix_buckets.csv", conflict_fields, conflict_rows)
        atomic_json(stage / "f2_d0_nested_split.json", nested_split)
        nested_fields = ["nested_split", "owner", "label", "teacher_kind", "source_group", "attack_family", "rows", "contexts"]
        atomic_csv(stage / "f2_d0_nested_split_census.csv", nested_fields, nested_rows)
        structural_status = "PASS"
        if not bool(structure["input_identifiable"]):
            structural_status = "F2_D0_NO_IDENTIFIABLE_PROTECTED_INPUT_FUNCTION"
        elif not bool(nested_split["split_feasible"]):
            structural_status = "F2_D0_NO_IDENTIFIABLE_FRESH_CHECKPOINT_SPLIT"
        if structural_status != "PASS":
            boundary = {
                "status": "PASS", "representation_container_rows_streamed_as_opaque_bytes": 0,
                "representation_rows_numeric_decoded": 0, "nonauthorized_representation_rows_numeric_decoded": 0,
                "authorized_train_a_rows": EXPECTED_ROWS, "authorized_train_a_contexts": EXPECTED_CONTEXTS,
                "internal_validation_representation_rows_decoded": 0, "internal_validation_scores_computed": 0,
                "select_scores_opened": 0, "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
                "pcap_opened": 0, "new_model_opened": 0, "parameters_fitted": 0, "optimizer_steps": 0,
                "training_or_resume_started": 0,
            }
            atomic_json(stage / "f2_d0_scope_and_boundary_audit.json", boundary)
            verdict = {
                "status": structural_status, "scientific_pass": False, "rows": EXPECTED_ROWS,
                "contexts": EXPECTED_CONTEXTS, "identities": identities,
                "training_authorized": False, "internal_validation_authorized": False,
            }
            atomic_json(stage / "f2_d0_verdict.json", verdict)
            write_sha256s(stage)
            os.replace(str(stage), str(output_dir))
            return verdict
        embedding_path = root / PINNED["embeddings"][0]
        with np.load(str(embedding_path), allow_pickle=False) as data:
            if "uid" not in data.files or "missing" not in data.files:
                raise RuntimeError("embedding identity arrays absent")
            container_uids = np.asarray(data["uid"]).astype(str)
            missing = np.asarray(data["missing"], dtype=bool)
        if len(container_uids) != EXPECTED_CONTAINER_ROWS or len(set(container_uids)) != EXPECTED_CONTAINER_ROWS:
            raise RuntimeError("embedding UID identity drift")
        positions = {uid: index for index, uid in enumerate(container_uids)}
        lexical_uids = [row["uid"] for row in rows]
        if not set(lexical_uids).issubset(positions):
            raise RuntimeError("authorized UID absent from embeddings")
        selected_indices = [positions[uid] for uid in lexical_uids]
        if bool(missing[np.asarray(selected_indices, dtype=np.int64)].any()):
            raise RuntimeError("authorized A row is missing")
        streamed, stream_audit = stream_authorized_rows(embedding_path, selected_indices)
        index_order = sorted(selected_indices)
        values_by_index = {index: streamed[offset] for offset, index in enumerate(index_order)}
        representations = np.stack([values_by_index[positions[uid]] for uid in lexical_uids])
        with np.load(str(root / PINNED["probe_state"][0]), allow_pickle=False) as data:
            state = {name: np.asarray(data[name]) for name in data.files}
        logits, scores = canonical_p2_logits_scores(representations, state)
        f1_logits, f1_scores = f1_wrapper_p2_logits_scores(representations, state)
        marker = json.loads((root / PINNED["threshold_marker"][0]).read_text(encoding="utf-8"))
        if float(marker["thresholds"]["P2"]["value"]) != THRESHOLD:
            raise RuntimeError("threshold drift")

        labels = np.asarray([row["label_kind"] for row in rows])
        canonical_hard = scores >= THRESHOLD
        f1_hard = f1_scores >= THRESHOLD
        hard_disagreements = int(np.count_nonzero(canonical_hard != f1_hard))
        differences = np.abs(logits - f1_logits)
        interface_comparison = {
            "status": "PASS" if hard_disagreements == 0 else "F2_D0_P2_INTERFACE_NUMERICAL_DRIFT",
            "canonical_vs_f1_wrapper_hard_disagreements": hard_disagreements,
            "maximum_absolute_logit_difference": float(np.max(differences)),
            "median_absolute_logit_difference": quantile(differences, 0.50, "linear"),
            "q95_absolute_logit_difference": quantile(differences, 0.95, "linear"),
            "q99_absolute_logit_difference": quantile(differences, 0.99, "linear"),
            "maximum_absolute_score_difference": float(np.max(np.abs(scores - f1_scores))),
            "canonical_attack_hard": int(np.count_nonzero(canonical_hard & (labels == "attack"))),
            "f1_wrapper_attack_hard": int(np.count_nonzero(f1_hard & (labels == "attack"))),
            "canonical_benign_hard": int(np.count_nonzero(canonical_hard & (labels == "benign"))),
            "f1_wrapper_benign_hard": int(np.count_nonzero(f1_hard & (labels == "benign"))),
            "rows": EXPECTED_ROWS,
        }
        atomic_json(stage / "f2_d0_p2_interface_comparison.json", interface_comparison)
        if hard_disagreements != 0:
            raise RuntimeError("F2_D0_P2_INTERFACE_NUMERICAL_DRIFT")

        output_rows: List[Dict[str, object]] = []
        classes: List[str] = []
        for row, logit, score in zip(rows, logits.tolist(), scores.tolist()):
            hard = score >= THRESHOLD
            if row["label_kind"] == "attack":
                teacher_class = "correct_attack" if hard else "teacher_wrong_attack"
            else:
                teacher_class = "teacher_wrong_benign" if hard else "correct_benign"
                if row["uid"] not in teacher_benign or teacher_benign[row["uid"]] != hard:
                    raise RuntimeError("teacher benign row mismatch")
            classes.append(teacher_class)
            output_rows.append({
                "uid": row["uid"], "semantic_context_key": row["semantic_context_key"],
                "source_group": row["source_group"], "device_family": row["device_family"],
                "attack_family": row["attack_family"], "label_kind": row["label_kind"],
                "old_logit": format(logit, ".17g"), "old_score": format(score, ".17g"),
                "threshold_margin": format(score - THRESHOLD, ".17g"), "teacher_class": teacher_class,
            })
        class_counts = {name: classes.count(name) for name in sorted(set(classes))}
        required_counts = {
            "correct_attack": EXPECTED_ATTACK,
            "correct_benign": EXPECTED_CORRECT_BENIGN,
            "teacher_wrong_benign": EXPECTED_WRONG_BENIGN,
        }
        if class_counts != required_counts or "teacher_wrong_attack" in class_counts:
            raise RuntimeError("F2_D0_TEACHER_IDENTITY_OR_SCOPE_FAILURE")

        class_array = np.asarray(classes)
        distribution_rows: List[Dict[str, object]] = []
        for teacher_class in sorted(required_counts):
            stats = summary_stats(logits[class_array == teacher_class])
            distribution_rows.append({"teacher_class": teacher_class, **stats})

        group_indices: Dict[Tuple[str, str, str, str], List[int]] = defaultdict(list)
        for index, row in enumerate(rows):
            key = (row["source_group"], row["attack_family"], row["label_kind"], classes[index])
            group_indices[key].append(index)
        group_rows: List[Dict[str, object]] = []
        for key in sorted(group_indices):
            values = logits[np.asarray(group_indices[key], dtype=np.int64)]
            group_rows.append({
                "source_group": key[0], "attack_family": key[1], "label_kind": key[2],
                "teacher_class": key[3], "rows": len(values), "minimum_logit": float(np.min(values)),
                "q05_logit": quantile(values, 0.05, "linear"), "median_logit": quantile(values, 0.5, "linear"),
                "q95_logit": quantile(values, 0.95, "linear"), "maximum_logit": float(np.max(values)),
            })

        attack_logits = logits[class_array == "correct_attack"]
        benign_logits = logits[class_array == "correct_benign"]
        q_attack_05 = quantile(attack_logits, 0.05, "lower")
        q_benign_95 = quantile(benign_logits, 0.95, "higher")
        c_attack = min(Z_P99, q_attack_05)
        c_benign = max(Z_P01, q_benign_95)
        attack_normalizer = c_attack - Z0
        benign_normalizer = Z0 - c_benign
        predicates = {
            "attack_envelope_stronger_than_old_margin": bool(c_attack > Z0 + 0.5),
            "benign_envelope_stronger_than_old_tolerance": bool(c_benign < Z0 - 0.25),
            "normalizers_finite_and_positive": bool(
                np.isfinite([attack_normalizer, benign_normalizer]).all() and
                attack_normalizer > 0 and benign_normalizer > 0
            ),
        }
        feasible = all(predicates.values())
        envelope_status = "F2_D0_CONTINUOUS_TEACHER_ENVELOPE_PASS" if feasible else "F2_D0_NO_IDENTIFIABLE_CONTINUOUS_TEACHER_ENVELOPE"
        constants = {
            "status": envelope_status, "theta_0": THRESHOLD, "z_0": Z0,
            "z_p99": Z_P99, "z_p01": Z_P01,
            "q_attack_05_method_lower": q_attack_05,
            "q_benign_95_method_higher": q_benign_95,
            "c_attack": c_attack, "c_benign": c_benign,
            "attack_normalizer": attack_normalizer, "benign_normalizer": benign_normalizer,
            "predicates": predicates,
            "future_aggregation": {
                "mean": "mean_context(mean_eligible_target(v_i))",
                "attack_worst": "max_context(max_correct_attack_target(v_i))",
            },
        }
        fields = ["uid", "semantic_context_key", "source_group", "device_family", "attack_family",
                  "label_kind", "old_logit", "old_score", "threshold_margin", "teacher_class"]
        atomic_gzip_csv(stage / "f2_d0_train_a_incumbent_logits.csv.gz", fields, output_rows)
        atomic_csv(stage / "f2_d0_teacher_distribution.csv",
                   ["teacher_class", "count", "minimum", "q01", "q05", "q25", "q50", "q75", "q95", "q99", "maximum"],
                   distribution_rows)
        atomic_csv(stage / "f2_d0_source_family_distribution.csv",
                   ["source_group", "attack_family", "label_kind", "teacher_class", "rows", "minimum_logit",
                    "q05_logit", "median_logit", "q95_logit", "maximum_logit"], group_rows)
        atomic_json(stage / "f2_d0_envelope_constants.json", constants)
        boundary = {
            "status": "PASS", **stream_audit, "authorized_train_a_rows": EXPECTED_ROWS,
            "authorized_train_a_contexts": EXPECTED_CONTEXTS,
            "internal_validation_representation_rows_decoded": 0,
            "internal_validation_scores_computed": 0, "select_scores_opened": 0,
            "viewed_opened": 0, "report_opened": 0, "final_opened": 0, "pcap_opened": 0,
            "new_model_opened": 0, "parameters_fitted": 0, "optimizer_steps": 0,
            "training_or_resume_started": 0,
        }
        atomic_json(stage / "f2_d0_scope_and_boundary_audit.json", boundary)
        status = "F2_D0_OLD_FUNCTION_PRESERVATION_FEASIBLE" if feasible else envelope_status
        verdict = {
            "status": status, "scientific_pass": feasible, "rows": EXPECTED_ROWS,
            "contexts": EXPECTED_CONTEXTS, "teacher_class_counts": class_counts,
            "constants": constants, "identities": identities,
            "training_authorized": False, "internal_validation_authorized": False,
        }
        atomic_json(stage / "f2_d0_verdict.json", verdict)
        write_sha256s(stage)
        os.replace(str(stage), str(output_dir))
        return verdict
    except Exception:
        shutil.rmtree(str(stage), ignore_errors=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = materialize(args.repo_root.resolve(), args.output_dir.resolve())
    print(json.dumps({"status": result["status"], "rows": result["rows"], "contexts": result["contexts"]}, sort_keys=True))


if __name__ == "__main__":
    main()
