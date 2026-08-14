#!/usr/bin/env python3
"""Materialize the frozen I1-to-E3 progression after benign census."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import issue27ckda_d1_representation_probe_v1 as core


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    with args.census.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if value.get("status") != "CKDA_D1_BENIGN_CENSUS_COMPLETE":
        raise RuntimeError("benign census status drift")
    if value.get("contract_sha256") != core.CONTRACT_SHA256:
        raise RuntimeError("benign census contract drift")
    gate = value.get("gate", {})
    if bool(gate.get("passed")):
        raise RuntimeError("I1 benign gate unexpectedly passed")
    report = {
        "contract_sha256": core.CONTRACT_SHA256,
        "e3_open_reason": "I1_PRIMARY_PRECONDITION_FAILED",
        "e3_opened": True,
        "final_files_opened": 0,
        "i1_embeddings_generated": 0,
        "i1_training_started": False,
        "primary": "I1",
        "selected_candidate": "E3",
        "status": "CKDA_D1_FROZEN_PROGRESSION_PASS",
    }
    core.atomic_json(args.out, report)
    print(json.dumps(report, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--census", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
