#!/usr/bin/env python3
"""Real-input equivalence gate for the CKDA D1 local two-pass adapter.

The gate deterministically chooses the cheapest fit/select member, keeps its
first target prefixes, and compares the frozen one-pass implementation with
the memory-bounded two-pass implementation using the same E3 runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd

import issue27ckda_d1_e3_embed_local_twopass_v1 as local
import issue27ckda_d1_e3_embed_v1 as frozen
import issue27ckda_d1_representation_probe_v1 as core


COMPARE_FIELDS = (
    "uid", "missing", "session_id", "timestamp_epoch", "event_position",
    "member_identity_sha256", "plan_sha256", "contract_sha256",
)


def choose_part(plan: pd.DataFrame, targets: int) -> pd.DataFrame:
    groups = []
    keys = ["dataset_kind", "container_path", "raw_source_path"]
    for key, part in plan.groupby(keys, sort=True):
        ordered = part.sort_values(
            ["target_event_position_within_capture", "uid"], kind="mergesort"
        ).head(targets).copy()
        groups.append(
            (
                int(ordered["target_event_position_within_capture"].max()),
                tuple(str(value) for value in key),
                ordered,
            )
        )
    if not groups:
        raise RuntimeError("equivalence plan has no member groups")
    return min(groups, key=lambda value: (value[0], value[1]))[2].reset_index(drop=True)


def compare_npz(frozen_path: Path, local_path: Path) -> Dict[str, object]:
    with np.load(frozen_path, allow_pickle=False) as left, np.load(
        local_path, allow_pickle=False
    ) as right:
        if set(left.files) != set(right.files):
            raise RuntimeError("equivalence checkpoint schema drift")
        for field in COMPARE_FIELDS:
            equal_nan = left[field].dtype.kind in {"f", "c"}
            if not np.array_equal(left[field], right[field], equal_nan=equal_nan):
                raise RuntimeError("equivalence metadata mismatch: %s" % field)
        left_rep = left["representation"].astype(np.float32)
        right_rep = right["representation"].astype(np.float32)
        if left_rep.shape != right_rep.shape:
            raise RuntimeError("equivalence representation shape drift")
        delta = np.abs(left_rep - right_rep)
        max_abs = float(delta.max(initial=0.0))
        if not np.array_equal(left_rep, right_rep, equal_nan=True):
            raise RuntimeError("equivalence representation byte-value drift: %.9g" % max_abs)
        frozen_round6 = hashlib.sha256(
            np.round(left_rep, 6).astype("<f4").tobytes()
        ).hexdigest()
        local_round6 = hashlib.sha256(
            np.round(right_rep, 6).astype("<f4").tobytes()
        ).hexdigest()
        return {
            "rows": int(len(left_rep)),
            "width": int(left_rep.shape[1]),
            "max_abs_representation_delta": max_abs,
            "frozen_round6_sha256": frozen_round6,
            "local_round6_sha256": local_round6,
        }


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    plan = pd.read_csv(args.target_metadata, keep_default_na=False)
    if len(plan) != 25_467 or plan["uid"].duplicated().any():
        raise RuntimeError("equivalence input is not the frozen fit/select target plan")
    part = choose_part(plan, args.targets)
    plan_sha = core.sha256_file(args.fit_select_plan)
    d0 = frozen.import_file("ckda_d1_equiv_d0", args.d0_pilot)
    ckbu = local.install_union_tshark_frontend(
        frozen.import_file("ckda_d1_equiv_ckbu", args.ckbu_decoder), d0
    )
    model, tokenizer, collator = frozen.build_e3_runtime(
        d0, args.netfound_source, args.netfound_checkpoint, args.device
    )
    args.out.mkdir(parents=True, exist_ok=True)
    frozen_path = args.out / "frozen_onepass.npz"
    local_path = args.out / "local_twopass.npz"
    for path in (frozen_path, local_path):
        if path.exists():
            path.unlink()
    frozen_audit = frozen.process_member(
        part, plan_sha, ckbu, d0, model, tokenizer, collator,
        args.tshark, args.device, args.batch_size, frozen_path,
    )
    local_audit = local.process_member_twopass(
        part, plan_sha, ckbu, d0, model, tokenizer, collator,
        args.tshark, args.device, args.batch_size, local_path,
    )
    comparison = compare_npz(frozen_path, local_path)
    report = {
        "status": "CKDA_D1_LOCAL_TWOPASS_REAL_EQUIVALENCE_PASS",
        "contract_sha256": core.CONTRACT_SHA256,
        "fit_select_plan_sha256": plan_sha,
        "target_metadata_sha256": core.sha256_file(args.target_metadata),
        "frozen_embedder_sha256": core.sha256_file(Path(frozen.__file__)),
        "local_embedder_sha256": core.sha256_file(Path(local.__file__)),
        "dataset_kind": str(part.iloc[0]["dataset_kind"]),
        "raw_source_path": str(part.iloc[0]["raw_source_path"]),
        "maximum_event_position": int(part["target_event_position_within_capture"].max()),
        "batch_size": int(args.batch_size),
        "frozen_checkpoint_sha256": frozen_audit["sha256"],
        "local_checkpoint_sha256": local_audit["sha256"],
        "local_peak_retained_target_sessions": int(
            local_audit["peak_retained_target_sessions"]
        ),
        "windows_tshark_missing_sentinels_normalized": int(
            getattr(ckbu, "_ckda_local_missing_sentinels_seen", 0)
        ),
        "union_tshark_fields": list(getattr(ckbu, "_ckda_local_union_fields", ())),
        **comparison,
    }
    core.atomic_json(args.out / "ckda_d1_local_twopass_equivalence.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--fit-select-plan", type=Path, required=True)
    result.add_argument("--target-metadata", type=Path, required=True)
    result.add_argument("--netfound-source", type=Path, required=True)
    result.add_argument("--netfound-checkpoint", type=Path, required=True)
    result.add_argument("--ckbu-decoder", type=Path, required=True)
    result.add_argument("--d0-pilot", type=Path, required=True)
    result.add_argument("--tshark", required=True)
    result.add_argument("--device", default="cpu")
    result.add_argument("--batch-size", type=int, default=16)
    result.add_argument("--targets", type=int, default=32)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
