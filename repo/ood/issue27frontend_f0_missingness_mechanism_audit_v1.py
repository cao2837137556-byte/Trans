#!/usr/bin/env python3
"""Frozen Frontend-F0 Step-0 missingness mechanism audit.

This program is deliberately unable to read representation/probe arrays or PCAPs.
It inventories only the frozen fit/select availability and legal metadata, then
fails closed when the four primitive causes cannot be reconstructed per target.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import os
import tempfile
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np
import pandas as pd


CONTRACT = "runs/mainline_docs/frontend_f0_missingness_mechanism_audit_frozen_20260828.md"
CONTRACT_SHA256 = "f188afc0f9a0564a9f193b2e13637efdb660077f6ce74ba5c1d9cfc638fb1e8e"
FORMAL = "repo/ood/issue27ckda_d1_e3_embed_v1.py"
FORMAL_SHA256 = "360cbaa72f818e6fc423b16f3b4989333bfba002a1423085ff15b2cb1569de14"
LOCAL = "repo/ood/issue27ckda_d1_e3_embed_local_twopass_v1.py"
LOCAL_SHA256 = "9f11d03b31e640de28f11fd7570b1495c7b9452b124b8b99b248689031b24ca2"
STAGE = "runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage"
AVAILABILITY = STAGE + "/ckda_d1_fit_select_embeddings.npz"
AVAILABILITY_SHA256 = "b1b4f2fde168a69e0cf7a53aaede2ddef9bd6d92b0ce58e56a9d6fcde37b6099"
METADATA = STAGE + "/ckda_d1_fit_select_embeddings.npz.metadata.csv.gz"
METADATA_SHA256 = "120ed5ccc752c1210a655dbcb972e08b6263bdeb1e08093d76b3e2f9c1b3d8dd"
PLAN = STAGE + "/ckda_d1_fit_select_plan.csv"
PLAN_SHA256 = "eed3d431ab8d71117db7a02b5ee0022eefe7932888001e7d9bcccfd54199aeac"
TERMINAL_REVIEW = "runs/mainline_docs/ckde_s_d0_lane_g_r2_result_kimi_terminal_review_20260827.md"
TERMINAL_REVIEW_SHA256 = "fddd32a9758743b0627ca64e1265b984a24fec74b3c0cab860fe2ca20939b61f"

PRIMITIVES = (
    "NO_IP_SESSION_KEY",
    "UNSUPPORTED_IP_PROTOCOL_NOT_TCP_UDP",
    "NONFINITE_TARGET_TIMESTAMP",
    "SESSION_TIMESTAMP_REGRESSION",
)
TERMINAL = "NO_IDENTIFIABLE_MISSINGNESS_MECHANISM_WITHOUT_REDECODE"
ALLOWED_NPZ_ARRAYS = ("uid", "missing")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def atomic_json(path: Path, value: Mapping[str, object]) -> None:
    atomic_bytes(path, (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]], gzip_output: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".%s." % path.name, dir=str(path.parent))
    os.close(fd)
    try:
        opener = gzip.open if gzip_output else open
        kwargs = {"mode": "wt", "encoding": "utf-8", "newline": ""}
        with opener(name, **kwargs) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
            writer.writeheader()
            writer.writerows(rows)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def verify_inputs(root: Path) -> Dict[str, str]:
    expected = {
        CONTRACT: CONTRACT_SHA256,
        FORMAL: FORMAL_SHA256,
        LOCAL: LOCAL_SHA256,
        AVAILABILITY: AVAILABILITY_SHA256,
        METADATA: METADATA_SHA256,
        PLAN: PLAN_SHA256,
        TERMINAL_REVIEW: TERMINAL_REVIEW_SHA256,
    }
    actual = {}
    for rel, digest in expected.items():
        path = root / rel
        if not path.is_file():
            raise RuntimeError("missing pinned input: %s" % rel)
        got = sha256_file(path)
        if got != digest:
            raise RuntimeError("pinned input drift: %s got=%s expected=%s" % (rel, got, digest))
        actual[rel] = got
    return actual


def static_branch_audit(root: Path) -> Dict[str, object]:
    formal = (root / FORMAL).read_text(encoding="utf-8")
    local = (root / LOCAL).read_text(encoding="utf-8")
    checks = {
        "no_ip_session_key": "session is None" in formal,
        "unsupported_protocol": "int(event.ip_proto) not in {6, 17}" in formal,
        "nonfinite_timestamp": "not math.isfinite(timestamp)" in formal,
        "timestamp_regression": "session in unencodable_sessions" in formal,
        "generic_reason": 'else "UNENCODABLE"' in formal,
        "regression_reason": '"UNENCODABLE_TIMESTAMP_REGRESSION"' in formal,
        "local_canonical_tcp_udp": "int(event.ip_proto) not in {6, 17}" in local,
        "reason_is_hashed": "missing_session_id = hashlib.sha256" in formal and "reason, position, uid" in formal,
    }
    if not all(checks.values()):
        raise RuntimeError("frozen missingness branch drift: %r" % checks)
    return {"checks": checks, "primitive_predicates": list(PRIMITIVES)}


def read_availability(path: Path) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    # NPZ is a ZIP container. Inspecting names first prevents a hidden schema drift.
    with zipfile.ZipFile(path) as archive:
        members = sorted(archive.namelist())
    with np.load(path, allow_pickle=False) as values:
        names = list(values.files)
        for name in ALLOWED_NPZ_ARRAYS:
            if name not in names:
                raise RuntimeError("availability NPZ missing allowed array: %s" % name)
        uid = values["uid"].astype(str)
        missing = values["missing"].astype(bool)
        # Deliberately never index values['representation'] or any other array.
    if len(uid) != len(missing) or len(set(uid.tolist())) != len(uid):
        raise RuntimeError("availability UID/missing schema drift")
    return uid, missing, members


def inventory_evidence(root: Path, missing_uids: set) -> Dict[str, object]:
    stage = root / STAGE
    target_meta = stage / "ckda_d1_fit_select_target_metadata.csv"
    inventory = []
    target_fields: List[str] = []
    target_missing_coverage = 0
    if target_meta.is_file():
        with target_meta.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            target_fields = list(reader.fieldnames or [])
            for row in reader:
                if str(row.get("uid", "")) in missing_uids:
                    target_missing_coverage += 1
        inventory.append({
            "path": str(target_meta.relative_to(root)).replace("\\", "/"),
            "sha256": sha256_file(target_meta),
            "fields": target_fields,
            "missing_uid_coverage": target_missing_coverage,
        })
    checkpoint_root = root / "runs/issue27ckda_d1_checkpoint_v1_localwin_ecb429926507d2c4/e3_fit_select"
    checkpoint_arrays: List[str] = []
    checkpoint_files = 0
    if checkpoint_root.is_dir():
        files = sorted(checkpoint_root.glob("*.npz"))
        checkpoint_files = len(files)
        if files:
            with zipfile.ZipFile(files[0]) as archive:
                checkpoint_arrays = sorted(Path(name).stem for name in archive.namelist() if name.endswith(".npy"))
        inventory.append({
            "path": str(checkpoint_root.relative_to(root)).replace("\\", "/"),
            "npz_files": checkpoint_files,
            "array_names_from_zip_directory_only": checkpoint_arrays,
            "array_values_opened": 0,
        })
    needed = {
        "ip_version_or_session_key": {"ip_version", "session_key", "ip.src", "ipv6.src", "src_ip"},
        "ip_protocol": {"ip_proto", "ip.proto", "protocol"},
        "finite_target_timestamp": {"timestamp_epoch", "feature_available_time_epoch"},
        "per_session_causal_monotonicity": {"timestamp_regression", "session_timestamps", "unencodable_reason"},
    }
    available = set(target_fields) | set(checkpoint_arrays)
    recoverable = {name: bool(fields & available) for name, fields in needed.items()}
    # A hashed session_id is not evidence for the underlying IP key or reason.
    exhaustive = all(recoverable.values()) and target_missing_coverage == len(missing_uids)
    return {
        "artifacts": inventory,
        "required_evidence_recoverable": recoverable,
        "missing_target_count": len(missing_uids),
        "target_metadata_missing_uid_coverage": target_missing_coverage,
        "all_primitive_predicates_target_identifiable": exhaustive,
        "reason_hash_is_noninvertible": True,
        "pcap_opened": 0,
        "report_opened": 0,
        "final_opened": 0,
        "representation_arrays_opened": 0,
        "probe_state_opened": 0,
        "model_weights_opened": 0,
    }


def aggregate_rows(frame: pd.DataFrame, group: str) -> List[Dict[str, object]]:
    rows = []
    for key, part in frame.groupby(group, dropna=False, sort=True):
        rows.append({
            group: str(key),
            "records": int(len(part)),
            "sessions": int(part["session_id"].nunique()),
            "missing_records": int(part["missing"].sum()),
            "finite_records": int((~part["missing"]).sum()),
            "attributed_missing_records": 0,
            "identifiability_status": TERMINAL,
        })
    return rows


def run(root: Path, output: Path) -> Dict[str, object]:
    hashes = verify_inputs(root)
    static = static_branch_audit(root)
    uid, missing, npz_members = read_availability(root / AVAILABILITY)
    plan = pd.read_csv(root / PLAN, dtype=str)
    meta = pd.read_csv(root / METADATA, dtype={"uid": str, "session_id": str})
    base = pd.DataFrame({"uid": uid, "missing": missing})
    frame = base.merge(meta, on="uid", validate="one_to_one").merge(plan, on="uid", validate="one_to_one")
    if len(frame) != len(uid):
        raise RuntimeError("fit/select join coverage drift")
    evidence = inventory_evidence(root, set(frame.loc[frame["missing"], "uid"].astype(str)))
    if evidence["all_primitive_predicates_target_identifiable"]:
        raise RuntimeError("M2 attribution is not implemented because M1 was expected to decide first")

    target_rows = []
    for row in frame.itertuples(index=False):
        target_rows.append({
            "uid": str(row.uid),
            "role": str(row.role),
            "source_group": str(row.source_group),
            "device_family": str(row.device_family),
            "attack_family": str(row.attack_family),
            "session_id": str(row.session_id),
            "missing": int(bool(row.missing)),
            "predicate_identifiable": 0,
            "primary_reason": "NOT_ATTRIBUTABLE_WITHOUT_REDECODE" if bool(row.missing) else "",
        })

    audit = {
        "status": TERMINAL,
        "contract_sha256": CONTRACT_SHA256,
        "input_sha256": hashes,
        "static_branch_audit": static,
        "availability_npz_member_names": npz_members,
        "availability_arrays_opened": list(ALLOWED_NPZ_ARRAYS),
        "rows": int(len(frame)),
        "missing_rows": int(frame["missing"].sum()),
        "finite_rows": int((~frame["missing"]).sum()),
        "devices": int(frame["device_family"].nunique()),
        "sessions": int(frame["session_id"].nunique()),
        "evidence_inventory": evidence,
    }
    verdict = {
        "status": TERMINAL,
        "scientific_stage_reached": "M1_REASON_IDENTIFIABILITY_CENSUS",
        "m2_entered": False,
        "m3_entered": False,
        "missing_rows": int(frame["missing"].sum()),
        "finite_rows": int((~frame["missing"]).sum()),
        "claim_boundary": "FROZEN_E3_MISSINGNESS_NOT_TARGET_ATTRIBUTABLE_WITHOUT_REDECODE",
        "hydraulic_false_positive_causality_claimed": False,
        "new_frontend_or_reencode_authorized": False,
        "boundary_counts": {
            "pcap_opened": 0, "report_opened": 0, "final_opened": 0,
            "representation_arrays_opened": 0, "probe_state_opened": 0,
            "model_weights_opened": 0, "training_runs": 0,
        },
    }
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / "frontend_f0_missingness_identifiability_audit.json", audit)
    atomic_json(output / "frontend_f0_missingness_mechanism_verdict.json", verdict)
    atomic_csv(output / "frontend_f0_missingness_reason_by_target.csv.gz",
               list(target_rows[0]), target_rows, gzip_output=True)
    device_rows = aggregate_rows(frame, "device_family")
    family_rows = aggregate_rows(frame, "attack_family")
    atomic_csv(output / "frontend_f0_missingness_reason_by_device.csv", list(device_rows[0]), device_rows)
    atomic_csv(output / "frontend_f0_missingness_reason_by_attack_family.csv", list(family_rows[0]), family_rows)
    names = sorted(p for p in output.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    sums = "".join("%s  %s\n" % (sha256_file(path), path.name) for path in names)
    atomic_bytes(output / "SHA256SUMS", sums.encode("ascii"))
    return verdict


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.repo_root.resolve(), args.output.resolve())
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
