#!/usr/bin/env python3
"""Join CKDA D1 frozen role plans to immutable raw-PCAP target metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core
import issue27ckcz_endpoint_pair_conflict_diagnostic_v1 as ckcz


GOTHAM_MANIFEST_SHA256 = "aaef2a0c0e4cc28d3815dbff4152db2fbe8c7d953dc35cf05cd817c4135d4c22"
AUXILIARY_MANIFEST_SHA256 = "f2a674235cb929ed4b7ebb8723c53a4f314f4e4563e727e3f4a2e0a4ab201e43"
GOTHAM_ALLOWLIST_SHA256 = "65b4804109914d50c3efb6b9ae40d2b7d7befc903be571a92ebee90624ab6de7"
AUXILIARY_ALLOWLIST_SHA256 = "be4ad12a9b0807b15b120d91ec2f9519a1743120ef0e9f04e0d8bab573252c49"
FINAL_MARKERS = ("cooler-motor", "seed37", "seed47", "seed-37", "seed-47")


def fail_if_final(value: object, context: str) -> None:
    lowered = str(value).lower().replace("_", "-")
    if any(marker in lowered for marker in FINAL_MARKERS):
        raise RuntimeError("FINAL marker in %s: %s" % (context, value))


def require_report_marker(path: Optional[Path], fit_select_plan_sha256: str) -> Dict[str, object]:
    if path is None or not Path(path).is_file():
        raise RuntimeError("sealed report metadata requires threshold-freeze marker")
    with Path(path).open("r", encoding="utf-8") as handle:
        marker = json.load(handle)
    if marker.get("status") != "CKDA_D1_THRESHOLDS_FROZEN":
        raise RuntimeError("threshold-freeze marker status drift")
    if marker.get("contract_sha256") != core.CONTRACT_SHA256:
        raise RuntimeError("threshold-freeze marker contract drift")
    if marker.get("fit_select_plan_sha256") != fit_select_plan_sha256:
        raise RuntimeError("threshold-freeze marker fit/select identity drift")
    thresholds = marker.get("thresholds", {})
    if set(thresholds) != {"G0", "P1", "P2"}:
        raise RuntimeError("threshold-freeze marker probe set drift")
    for probe, value in thresholds.items():
        if int(value.get("support_hard", -1)) != core.SUPPORT_SELECT_ROWS:
            raise RuntimeError("%s threshold does not preserve all support_val attacks" % probe)
    if int(marker.get("fit_rows", -1)) != 18_398 or int(marker.get("select_rows", -1)) != 7_069:
        raise RuntimeError("threshold-freeze marker denominator drift")
    if int(marker.get("report_rows_opened", -1)) != 0 or int(marker.get("report_labels_opened", -1)) != 0:
        raise RuntimeError("threshold-freeze marker reports premature report access")
    return marker


def load_cache_metadata(args: argparse.Namespace) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    gotham_allowlist = ckcz.load_allowlist(
        args.gotham_allowlist, GOTHAM_ALLOWLIST_SHA256, "gotham"
    )
    auxiliary_allowlist = ckcz.load_allowlist(
        args.auxiliary_allowlist, AUXILIARY_ALLOWLIST_SHA256, "auxiliary"
    )
    gotham = ckcz.validate_manifest(
        args.gotham_manifest,
        GOTHAM_MANIFEST_SHA256,
        gotham_allowlist,
        "gotham",
        24,
        317_523,
    )
    auxiliary = ckcz.validate_manifest(
        args.auxiliary_manifest,
        AUXILIARY_MANIFEST_SHA256,
        auxiliary_allowlist,
        "auxiliary",
        31,
        18_600,
    )
    gotham_meta, gotham_audit = ckcz.export_cache_metadata(args.ckbv_root, gotham, "gotham")
    auxiliary_meta, auxiliary_audit = ckcz.export_cache_metadata(
        args.ckbv_root, auxiliary, "auxiliary"
    )
    metadata = pd.concat((gotham_meta, auxiliary_meta), ignore_index=True)
    return metadata, gotham_audit + auxiliary_audit


def classify_uid(uid: str) -> str:
    if str(uid).startswith("ton:"):
        return "ton"
    if str(uid).startswith("aux:"):
        return "auxiliary"
    return "gotham"


def join_plan(
    plan: pd.DataFrame, metadata: pd.DataFrame, ton_pcap_root: Path, gotham_zip: Path
) -> pd.DataFrame:
    work = plan.copy()
    work["cache_kind"] = work["uid"].astype(str).map(classify_uid)
    work["target_index"] = pd.to_numeric(work["recorded_index"], errors="raise").astype("Int64")
    keys = ["cache_kind", "source_group", "target_index"]
    if metadata.duplicated(keys).any():
        raise RuntimeError("raw target metadata key collision")
    joined = work.merge(metadata, on=keys, how="left", validate="many_to_one", indicator=True)
    ton = joined["cache_kind"].eq("ton")
    unexpected = ~joined["_merge"].eq("both") & ~ton
    if unexpected.any():
        raise RuntimeError(
            "non-ToN target metadata join miss:\n%s" %
            joined.loc[unexpected, ["uid", "role", "source_group"]].head(10).to_string(index=False)
        )
    if joined.loc[~ton, "raw_source_path"].isna().any():
        raise RuntimeError("joined non-ToN metadata lacks raw member")
    joined.loc[ton, "raw_source_path"] = joined.loc[ton, "source_group"].astype(str)
    joined.loc[ton, "feature_available_time_epoch"] = np.nan
    joined.loc[ton, "target_event_position_within_capture"] = joined.loc[ton, "target_index"].astype(float)
    joined.loc[ton, "src_local_id"] = -1
    joined.loc[ton, "dst_local_id"] = -1
    joined["dataset_kind"] = np.where(ton, "direct_pcap", "gotham_zip")
    joined["container_path"] = np.where(
        ton,
        joined["raw_source_path"].map(lambda value: str(Path(ton_pcap_root) / str(value))),
        str(Path(gotham_zip)),
    )
    joined["metadata_matched"] = joined["_merge"].eq("both") | ton
    joined.drop(columns=["_merge"], inplace=True)
    if joined["uid"].duplicated().any() or not joined["metadata_matched"].all():
        raise RuntimeError("target metadata UID preservation failed")
    for column in ("source_group", "raw_source_path", "container_path"):
        for value in joined[column].astype(str):
            fail_if_final(value, column)
    joined.sort_values(
        ["dataset_kind", "raw_source_path", "target_event_position_within_capture", "uid"],
        kind="mergesort",
        inplace=True,
    )
    joined.reset_index(drop=True, inplace=True)
    return joined


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    plan_path = Path(args.plan)
    plan_sha = core.sha256_file(plan_path)
    plan = pd.read_csv(plan_path, keep_default_na=False)
    expected_scope = "FIT_PROBE_ONLY" if args.scope == "fit-select" else "REPORT_ONE_SHOT_ONLY"
    if args.scope == "fit-select":
        allowed_scopes = {"FIT_PROBE_ONLY", "SELECT_THRESHOLD_ONLY"}
        if set(plan["plan_scope"]) != allowed_scopes or len(plan) != 25_467:
            raise RuntimeError("fit/select plan scope/cardinality drift")
        marker = None
    else:
        if set(plan["plan_scope"]) != {expected_scope} or len(plan) != 262_050:
            raise RuntimeError("sealed report plan scope/cardinality drift")
        marker = require_report_marker(args.threshold_marker, args.fit_select_plan_sha256)
    metadata, cache_audit = load_cache_metadata(args)
    if not Path(args.gotham_zip).is_file():
        raise RuntimeError("Gotham archive is absent")
    fail_if_final(args.gotham_zip, "gotham_zip")
    joined = join_plan(plan, metadata, args.ton_pcap_root, args.gotham_zip)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    core.atomic_csv(out, joined.to_dict(orient="records"), list(joined.columns))
    readback = pd.read_csv(out, keep_default_na=False)
    if len(readback) != len(joined) or list(readback.columns) != list(joined.columns):
        raise RuntimeError("target metadata atomic readback failed")
    audit = {
        "status": "CKDA_D1_TARGET_METADATA_PASS",
        "scope": args.scope,
        "contract_sha256": core.CONTRACT_SHA256,
        "plan_sha256": plan_sha,
        "threshold_marker_sha256": core.sha256_file(args.threshold_marker) if marker is not None else "NOT_OPENED",
        "rows": len(joined),
        "unique_uids": int(joined["uid"].nunique()),
        "gotham_rows": int(joined["cache_kind"].eq("gotham").sum()),
        "auxiliary_rows": int(joined["cache_kind"].eq("auxiliary").sum()),
        "ton_rows": int(joined["cache_kind"].eq("ton").sum()),
        "cache_sources_audited": len(cache_audit),
        "output_sha256": core.sha256_file(out),
        "final_files_opened": 0,
    }
    core.atomic_json(out.with_suffix(out.suffix + ".audit.json"), audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--scope", choices=("fit-select", "report"), required=True)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--plan", type=Path, required=True)
    result.add_argument("--threshold-marker", type=Path)
    result.add_argument("--fit-select-plan-sha256", default="")
    result.add_argument("--ckbv-root", type=Path, required=True)
    result.add_argument("--gotham-manifest", type=Path, required=True)
    result.add_argument("--auxiliary-manifest", type=Path, required=True)
    result.add_argument("--gotham-allowlist", type=Path, required=True)
    result.add_argument("--auxiliary-allowlist", type=Path, required=True)
    result.add_argument("--ton-pcap-root", type=Path, required=True)
    result.add_argument("--gotham-zip", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
