#!/usr/bin/env python3
"""Rebind only storage paths in the SHA-pinned D0 fit-prefix manifest."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core


FORMAL_MANIFEST_SHA256 = "9184cd018efcc6547832bf04ce6d3046c687b8e48cac73234482d9fb3ba89689"
FIELDS = (
    "dataset_kind", "source_id", "container_path", "pcap_member",
    "fit_cutoff_event_position_inclusive", "fit_role_basis", "lineage_source",
)


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    if core.sha256_file(args.formal_manifest) != FORMAL_MANIFEST_SHA256:
        raise RuntimeError("formal D0 manifest SHA drift")
    formal = pd.read_csv(args.formal_manifest, keep_default_na=False)
    if tuple(formal.columns) != FIELDS or len(formal) != 27:
        raise RuntimeError("formal D0 manifest schema/cardinality drift")
    local = formal.copy()
    gotham = local["dataset_kind"].eq("gotham_zip")
    direct = local["dataset_kind"].eq("direct_pcap")
    if not (gotham | direct).all():
        raise RuntimeError("unknown D0 manifest dataset kind")
    local.loc[gotham, "container_path"] = str(args.gotham_zip)
    local.loc[direct, "container_path"] = local.loc[direct, "pcap_member"].map(
        lambda value: str(args.ton_root / str(value))
    )
    for path in sorted(set(local["container_path"].astype(str))):
        if not Path(path).is_file():
            raise RuntimeError("rebound local container is absent: %s" % path)
    immutable = [field for field in FIELDS if field != "container_path"]
    if not formal[immutable].equals(local[immutable]):
        raise RuntimeError("local manifest changed a non-path field")
    core.atomic_csv(args.out, local.to_dict(orient="records"), list(FIELDS))
    readback = pd.read_csv(args.out, keep_default_na=False)
    if not readback.equals(local):
        raise RuntimeError("local manifest atomic readback drift")
    audit = {
        "status": "CKDA_D1_LOCAL_MANIFEST_PATH_REBIND_PASS",
        "contract_sha256": core.CONTRACT_SHA256,
        "formal_manifest_sha256": FORMAL_MANIFEST_SHA256,
        "local_manifest_sha256": core.sha256_file(args.out),
        "rows": int(len(local)),
        "container_paths_changed": int(
            (formal["container_path"].astype(str) != local["container_path"].astype(str)).sum()
        ),
        "non_path_cells_changed": 0,
        "lineage_source_cells_changed": 0,
        "final_files_opened": 0,
    }
    core.atomic_json(args.out.with_suffix(args.out.suffix + ".audit.json"), audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--formal-manifest", type=Path, required=True)
    result.add_argument("--gotham-zip", type=Path, required=True)
    result.add_argument("--ton-root", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
