#!/usr/bin/env python3
"""CKDA D1 exact benign-only I1 census with validated D0 checkpoint reuse."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import issue27ckda_d1_representation_probe_v1 as core


ALLOWED_GOTHAM_ROLES = {"aux_fit", "id_calib", "ood_val", "ood_stress"}
EXCLUDED_ROLES = {"support_train", "aux_process_fit"}
REQUIRED_FIELDS = (
    "dataset_kind",
    "source_id",
    "container_path",
    "pcap_member",
    "fit_cutoff_event_position_inclusive",
    "fit_role_basis",
    "lineage_source",
)


def import_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(Path(path)))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s from %s" % (name, path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def fail_if_final(value: object, context: str) -> None:
    lowered = str(value).lower().replace("_", "-")
    markers = ("cooler-motor", "seed37", "seed47", "seed-37", "seed-47")
    if any(marker in lowered for marker in markers):
        raise RuntimeError("FINAL marker in %s: %s" % (context, value))


def load_manifest(path: Path) -> Tuple[List[Dict[str, str]], str]:
    rows = core.read_csv(Path(path))
    if not rows or tuple(rows[0].keys()) != REQUIRED_FIELDS:
        raise RuntimeError("D0 fit-prefix manifest schema drift")
    return rows, core.sha256_file(Path(path))


def benign_row(row: Mapping[str, str]) -> bool:
    role = str(row["fit_role_basis"])
    member = str(row["pcap_member"]).replace("\\", "/")
    if role in ALLOWED_GOTHAM_ROLES:
        return str(row["dataset_kind"]) == "gotham_zip" and member.startswith("raw/benign/")
    if role == "aux_normal_fit":
        return str(row["dataset_kind"]) == "direct_pcap"
    return False


def filter_benign(rows: Sequence[Mapping[str, str]]) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    allowed = []
    excluded = []
    for raw in rows:
        row = dict(raw)
        for field in ("source_id", "container_path", "pcap_member", "lineage_source"):
            fail_if_final(row[field], field)
        if benign_row(row):
            allowed.append(row)
        else:
            row["exclusion_reason"] = (
                "FROZEN_EXCLUDED_ROLE" if row["fit_role_basis"] in EXCLUDED_ROLES
                else "NOT_EXPLICITLY_BENIGN_UNDER_D1_SECTION_4_1"
            )
            excluded.append(row)
    counts: Dict[str, int] = {}
    for row in allowed:
        counts[row["fit_role_basis"]] = counts.get(row["fit_role_basis"], 0) + 1
    expected = {"aux_fit": 11, "aux_normal_fit": 1, "id_calib": 3, "ood_stress": 1, "ood_val": 4}
    if counts != expected or len(allowed) != 20:
        raise RuntimeError("CKDA D1 benign member scope drift: %s" % counts)
    return allowed, excluded


def checkpoint_key(row: Mapping[str, str]) -> Tuple[str, str]:
    identity = str(row["source_id"]) + "\x1f" + str(row["pcap_member"])
    key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
    return identity, key


def reuse_d0_checkpoint(
    row: Mapping[str, str],
    d0_checkpoint_dir: Optional[Path],
    d0_manifest_sha256: str,
) -> Optional[Dict[str, object]]:
    if d0_checkpoint_dir is None:
        return None
    identity, key = checkpoint_key(row)
    path = Path(d0_checkpoint_dir) / (key + ".json")
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if value.get("manifest_sha256") != d0_manifest_sha256:
        raise RuntimeError("D0 census checkpoint manifest SHA drift: %s" % path)
    if value.get("identity") != identity or value.get("status") != "CKDA_D0_SOURCE_CENSUS_COMPLETE":
        raise RuntimeError("D0 census checkpoint identity/status drift: %s" % path)
    expected = int(row["fit_cutoff_event_position_inclusive"]) + 1
    if int(value.get("fit_visible_unique_packets", -1)) != expected:
        raise RuntimeError("D0 census checkpoint cutoff coverage drift: %s" % path)
    encodable = value.get("fit_encodable_unique_packets", {})
    if "I1" not in encodable:
        raise RuntimeError("D0 census checkpoint lacks I1 count: %s" % path)
    return {
        "identity": identity,
        "source_id": row["source_id"],
        "pcap_member": row["pcap_member"],
        "fit_role_basis": row["fit_role_basis"],
        "cutoff_inclusive": int(row["fit_cutoff_event_position_inclusive"]),
        "visible_packets": expected,
        "i1_tokens": int(encodable["I1"]),
        "i1_sessions": int(value["i1_sessions"]),
        "lineage": "REUSED_D0_VALIDATED_SOURCE_CHECKPOINT",
        "checkpoint_path": str(path),
        "checkpoint_sha256": core.sha256_file(path),
        "raw_label_columns_read": 0,
        "final_files_opened": 0,
    }


def exact_decode(
    row: Mapping[str, str],
    ckbu: Any,
    d0: Any,
    tshark: str,
) -> Dict[str, object]:
    identity, _key = checkpoint_key(row)
    owner, iterator = d0.open_rows(ckbu, dict(row), tshark)
    sessions = set()
    visible = 0
    tokens = 0
    started = time.monotonic()
    try:
        for position, tshark_row in enumerate(iterator):
            cutoff = int(row["fit_cutoff_event_position_inclusive"])
            if position > cutoff:
                break
            event = ckbu.event_from_tshark(tshark_row)
            visible += 1
            key = d0.session_key(event)
            if key is not None:
                tokens += 1
                sessions.add(hashlib.sha256(repr((identity, key)).encode("utf-8")).digest())
            if visible % 100_000 == 0:
                print(
                    "CKDA_D1_BENIGN_CENSUS_PROGRESS member=%s packets=%d" %
                    (row["pcap_member"], visible),
                    flush=True,
                )
    finally:
        if owner is not None:
            owner.close()
    expected = int(row["fit_cutoff_event_position_inclusive"]) + 1
    if visible != expected:
        raise RuntimeError("benign census prefix incomplete: %s %d/%d" % (identity, visible, expected))
    return {
        "identity": identity,
        "source_id": row["source_id"],
        "pcap_member": row["pcap_member"],
        "fit_role_basis": row["fit_role_basis"],
        "cutoff_inclusive": int(row["fit_cutoff_event_position_inclusive"]),
        "visible_packets": visible,
        "i1_tokens": tokens,
        "i1_sessions": len(sessions),
        "lineage": "EXACT_D1_BENIGN_REDECODE",
        "checkpoint_path": "",
        "checkpoint_sha256": "",
        "seconds": time.monotonic() - started,
        "raw_label_columns_read": 0,
        "final_files_opened": 0,
    }


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    rows, manifest_sha = load_manifest(args.fit_prefix_manifest)
    allowed, excluded = filter_benign(rows)
    visible_upper_bound = sum(int(row["fit_cutoff_event_position_inclusive"]) + 1 for row in allowed)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    ckbu = import_file("ckda_d1_ckbu", args.ckbu_decoder)
    d0 = import_file("ckda_d1_d0", args.d0_audit)
    results = []
    checkpoint_dir = out / "benign_member_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    for index, row in enumerate(allowed):
        identity, key = checkpoint_key(row)
        checkpoint = checkpoint_dir / (key + ".json")
        if checkpoint.is_file():
            with checkpoint.open("r", encoding="utf-8") as handle:
                result = json.load(handle)
            if result.get("identity") != identity or result.get("contract_sha256") != core.CONTRACT_SHA256:
                raise RuntimeError("D1 benign census checkpoint identity drift")
        else:
            result = reuse_d0_checkpoint(row, args.d0_checkpoint_dir, manifest_sha)
            if result is None:
                result = exact_decode(row, ckbu, d0, args.tshark)
            result["status"] = "CKDA_D1_BENIGN_MEMBER_CENSUS_COMPLETE"
            result["contract_sha256"] = core.CONTRACT_SHA256
            result["fit_prefix_manifest_sha256"] = manifest_sha
            core.atomic_json(checkpoint, result)
            with checkpoint.open("r", encoding="utf-8") as handle:
                verified = json.load(handle)
            if verified != result:
                raise RuntimeError("D1 benign census checkpoint readback failed")
        results.append(result)
        print(
            "CKDA_D1_BENIGN_MEMBER_COMPLETE index=%d/%d member=%s tokens=%d sessions=%d" %
            (index + 1, len(allowed), row["pcap_member"], result["i1_tokens"], result["i1_sessions"]),
            flush=True,
        )
    sessions = sum(int(value["i1_sessions"]) for value in results)
    tokens = sum(int(value["i1_tokens"]) for value in results)
    gate = core.benign_census_gate(sessions, tokens)
    report = {
        "status": "CKDA_D1_BENIGN_CENSUS_COMPLETE",
        "contract_sha256": core.CONTRACT_SHA256,
        "fit_prefix_manifest_sha256": manifest_sha,
        "allowed_members": len(allowed),
        "excluded_members": len(excluded),
        "visible_packet_upper_bound": visible_upper_bound,
        "benign_fit_sessions": sessions,
        "benign_fit_tokens": tokens,
        "gate": gate,
        "reused_d0_checkpoints": sum(value["lineage"].startswith("REUSED") for value in results),
        "exact_redecoded_members": sum(value["lineage"].startswith("EXACT") for value in results),
        "raw_label_columns_read": 0,
        "performance_embeddings_generated": 0,
        "final_files_opened": 0,
        "member_manifest_sha256": core.sha256_json(
            sorted((value["identity"], core.sha256_json(value)) for value in results)
        ),
    }
    core.atomic_csv(out / "ckda_d1_benign_member_census.csv", results)
    core.atomic_csv(out / "ckda_d1_benign_exclusions.csv", excluded)
    core.atomic_json(out / "ckda_d1_benign_census.json", report)
    print(json.dumps(report, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--fit-prefix-manifest", type=Path, required=True)
    result.add_argument("--d0-checkpoint-dir", type=Path)
    result.add_argument(
        "--d0-audit",
        type=Path,
        default=root / "repo/ood/issue27ckda_d0_representation_compatibility_audit_v1.py",
    )
    result.add_argument(
        "--ckbu-decoder",
        type=Path,
        default=root / "repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py",
    )
    result.add_argument("--tshark", default="tshark")
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
