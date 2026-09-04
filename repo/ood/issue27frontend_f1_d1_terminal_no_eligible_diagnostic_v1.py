"""Read-only fit/internal-val diagnostic for the terminal Frontend-F1 D1 state.

This script explains the terminal checkpoint's zero-regression failure.  It
never opens select, viewed, report, FINAL, PCAP, or any network resource and it
does not train, resume, or mutate a model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

import numpy as np
import torch


ROOT = Path(__file__).resolve().parents[2]
TRAINER = ROOT / "repo/ood/issue27frontend_f1_d1_train_v1.py"
CORPUS = ROOT / "runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_contexts.jsonl.gz"
RUN = ROOT / "runs/frontend_f1_d1_one_shot_training_v1_20260902_local"
RESUME = RUN / "f1_d1_resume.pt"
STATUS = RUN / "f1_d1_training_status.json"
PROBE = ROOT / "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/ckda_d1_probe_state.npz"
FROZEN = ROOT / "runs/mainline_docs/frontend_f1_d1_numerical_addendum_frozen_20260902.md"

PINS = {
    TRAINER: "6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634",
    CORPUS: "623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e",
    RESUME: "12fccfa359c5d909f13cd1a821a88ec53dc6c9fd0e01cf8b1a1c5bffc1ecfefa",
    STATUS: "9dc4735c34df1202a123d3c140ab445d35a7f826f0ba62b194f77acde0046e62",
    PROBE: "50a9bcfc18287d51bf8afda7367b57decdf3179dd41fc3aa61399d4098360c38",
    FROZEN: "7cf06c5885e21b813f9f5933360bc18308f41038bdb60809e2343a612fafd860",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, rows: Sequence[Mapping[str, object]], fields: Sequence[str]) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(str(temporary), str(path))


def load_trainer():
    specification = importlib.util.spec_from_file_location("frontend_f1_d1_trainer_diag", TRAINER)
    if specification is None or specification.loader is None:
        raise RuntimeError("cannot load pinned trainer")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


def quantiles(values: Sequence[float]) -> Dict[str, float]:
    array = np.asarray(values, dtype=np.float64)
    return {
        "min": float(np.min(array)),
        "q01": float(np.quantile(array, 0.01)),
        "q05": float(np.quantile(array, 0.05)),
        "median": float(np.median(array)),
        "q95": float(np.quantile(array, 0.95)),
        "max": float(np.max(array)),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    output = arguments.output_dir.resolve()
    output.relative_to((ROOT / "runs").resolve())
    allowed_outputs = {
        "SHA256SUMS",
        "f1_d1_terminal_attack_group_summary.csv",
        "f1_d1_terminal_diagnostic.json",
        "f1_d1_terminal_flipped_attacks.csv",
    }
    if output.exists():
        unexpected = sorted(path.name for path in output.iterdir() if path.name not in allowed_outputs)
        if unexpected:
            raise RuntimeError("refusing unexpected diagnostic output: %s" % unexpected)
    for path, expected in PINS.items():
        if not path.is_file() or sha256(path) != expected:
            raise RuntimeError("input identity drift: %s" % path)

    trainer = load_trainer()
    trainer.seed_runtime()
    trainer.verify_runtime()
    status = json.loads(STATUS.read_text(encoding="utf-8"))
    if status.get("status") != "F1_D1_NO_ELIGIBLE_CHECKPOINT" or len(status.get("ledger", [])) != 31:
        raise RuntimeError("terminal training state drift")

    contexts = trainer.read_contexts(CORPUS)
    vocabulary, vocabulary_sha = trainer.build_vocabulary(contexts)
    encoded = trainer.encode_examples(contexts, vocabulary)
    validation = [item for item in encoded if item.context.split() == "internal_val"]
    if len(validation) != 3582 or sum(len(item.context.targets) for item in validation) != 4400:
        raise RuntimeError("internal-validation denominator drift")
    checkpoint = torch.load(RESUME, map_location="cpu", weights_only=False)
    if int(checkpoint["epoch"]) != 31 or len(checkpoint["ledger"]) != 31:
        raise RuntimeError("terminal checkpoint cursor drift")
    model = trainer.F1Encoder()
    model.load_state_dict(checkpoint["model"], strict=True)
    model.eval()
    p2 = trainer.load_probe_state(PROBE)

    target_rows: List[Dict[str, object]] = []
    representations_finite = True
    with torch.no_grad():
        for start in range(0, len(validation), 32):
            part = validation[start:start + 32]
            batch = trainer.collate_examples(part)
            representations, _ = model(batch["token_ids"], batch["lengths"])
            for row_index, example in enumerate(part):
                tokens = example.tokens
                for target in example.context.targets:
                    representation = representations[row_index, target.event_index]
                    representations_finite = representations_finite and bool(torch.isfinite(representation).all())
                    logit = float(p2(representation.reshape(1, -1)).item())
                    prefix = tokens[:target.event_index + 1]
                    target_signature = example.context.signatures[target.event_index].split("\x1f")
                    if len(target_signature) != 15:
                        raise RuntimeError("canonical signature width drift")
                    target_rows.append({
                        "uid": target.uid,
                        "context_key": example.context.context_key,
                        "source_group": target.source_group,
                        "device_family": target.device_family,
                        "attack_family": target.attack_family,
                        "owner": target.owner,
                        "label": target.label,
                        "teacher_kind": target.teacher_kind,
                        "event_index": target.event_index,
                        "prefix_events": len(prefix),
                        "context_events": len(tokens),
                        "context_targets": len(example.context.targets),
                        "unknown_prefix_events": int(sum(token == 1 for token in prefix)),
                        "unknown_prefix_fraction": float(sum(token == 1 for token in prefix) / len(prefix)),
                        "target_tier": target_signature[0],
                        "target_direction": target_signature[1],
                        "target_protocol_group": target_signature[6],
                        "target_length_bin": target_signature[9],
                        "target_delta_bin": target_signature[10],
                        "new_logit": logit,
                        "new_probability": float(1.0 / (1.0 + math.exp(-logit))),
                        "margin_from_threshold": float(logit - trainer.Z_0),
                        "new_hard": bool(logit >= trainer.Z_0),
                    })

    protected_attack = [
        row for row in target_rows
        if row["owner"] == "A" and row["label"] == 1 and row["teacher_kind"] == "attack_hard"
    ]
    protected_benign = [
        row for row in target_rows
        if row["owner"] == "A" and row["label"] == 0 and row["teacher_kind"] == "benign_normal"
    ]
    failed = [row for row in protected_attack if not row["new_hard"]]
    new_benign_hard = [row for row in protected_benign if row["new_hard"]]
    if len(protected_attack) != 2000 or len(protected_benign) != 1174:
        raise RuntimeError("protected denominator drift")
    if len(failed) != 5 or new_benign_hard or not representations_finite:
        raise RuntimeError("terminal diagnostic reproduction drift")

    group_rows: List[Dict[str, object]] = []
    for kind, key in (("source_group", "source_group"), ("attack_family", "attack_family")):
        buckets: Dict[str, List[Mapping[str, object]]] = defaultdict(list)
        for row in protected_attack:
            buckets[str(row[key])].append(row)
        for group in sorted(buckets):
            rows = buckets[group]
            margins = [float(row["margin_from_threshold"]) for row in rows]
            group_rows.append({
                "group_kind": kind,
                "group": group,
                "protected_attack_rows": len(rows),
                "flipped_rows": sum(not bool(row["new_hard"]) for row in rows),
                "flip_fraction": sum(not bool(row["new_hard"]) for row in rows) / len(rows),
                "minimum_margin": min(margins),
                "median_margin": float(np.median(margins)),
            })

    failed_fields = [
        "uid", "context_key", "source_group", "device_family", "attack_family", "event_index",
        "prefix_events", "context_events", "context_targets", "unknown_prefix_events",
        "unknown_prefix_fraction", "target_tier", "target_direction", "target_protocol_group",
        "target_length_bin", "target_delta_bin", "new_logit", "new_probability",
        "margin_from_threshold", "new_hard",
    ]
    output.mkdir(parents=True, exist_ok=True)
    atomic_csv(output / "f1_d1_terminal_flipped_attacks.csv", failed, failed_fields)
    atomic_csv(
        output / "f1_d1_terminal_attack_group_summary.csv",
        group_rows,
        ["group_kind", "group", "protected_attack_rows", "flipped_rows", "flip_fraction",
         "minimum_margin", "median_margin"],
    )
    result = {
        "status": "F1_D1_TERMINAL_NO_ELIGIBLE_DIAGNOSTIC_COMPLETE",
        "scope": "FIT_INTERNAL_VAL_TERMINAL_STATE_ONLY",
        "input_sha256": {str(path.relative_to(ROOT)).replace("\\", "/"): digest for path, digest in PINS.items()},
        "vocabulary_sha256": vocabulary_sha,
        "epochs_in_ledger": len(status["ledger"]),
        "all_epochs_eligible_false": all(not bool(row["eligible"]) for row in status["ledger"]),
        "terminal_epoch": int(checkpoint["epoch"]),
        "threshold_logit": float(trainer.Z_0),
        "threshold_probability": float(1.0 / (1.0 + math.exp(-trainer.Z_0))),
        "representations_finite": representations_finite,
        "protected_attack_rows": len(protected_attack),
        "terminal_attack_flips": len(failed),
        "terminal_attack_retention": 1.0 - len(failed) / len(protected_attack),
        "protected_benign_rows": len(protected_benign),
        "terminal_new_benign_hard": len(new_benign_hard),
        "failed_unique_contexts": len(set(str(row["context_key"]) for row in failed)),
        "failed_sources": dict(sorted((key, sum(row["source_group"] == key for row in failed))
                                       for key in set(str(row["source_group"]) for row in failed))),
        "failed_families": dict(sorted((key, sum(row["attack_family"] == key for row in failed))
                                        for key in set(str(row["attack_family"]) for row in failed))),
        "failed_target_protocol_groups": dict(sorted(
            (key, sum(row["target_protocol_group"] == key for row in failed))
            for key in set(str(row["target_protocol_group"]) for row in failed)
        )),
        "failed_prefix_event_counts": sorted(int(row["prefix_events"]) for row in failed),
        "failed_rows_with_unknown_prefix_event": sum(int(row["unknown_prefix_events"]) > 0 for row in failed),
        "protected_attack_margin_quantiles": quantiles(
            [float(row["margin_from_threshold"]) for row in protected_attack]
        ),
        "failed_margin_quantiles": quantiles([float(row["margin_from_threshold"]) for row in failed]),
        "claim_boundary": {
            "old_continuous_teacher_score_available": False,
            "reason": "The authorized fit corpus carries only label-aware teacher_kind bits, not incumbent continuous scores.",
            "does_not_identify_every_epoch_failure": True,
            "select_opened": 0,
            "viewed_opened": 0,
            "report_opened": 0,
            "final_opened": 0,
            "training_or_resume_started": 0,
        },
    }
    atomic_json(output / "f1_d1_terminal_diagnostic.json", result)
    generated = [
        output / "f1_d1_terminal_attack_group_summary.csv",
        output / "f1_d1_terminal_diagnostic.json",
        output / "f1_d1_terminal_flipped_attacks.csv",
    ]
    atomic_text(output / "SHA256SUMS", "".join("%s  %s\n" % (sha256(path), path.name) for path in generated))
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
