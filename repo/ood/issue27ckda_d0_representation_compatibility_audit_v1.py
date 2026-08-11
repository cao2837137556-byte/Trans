#!/usr/bin/env python3
"""CKDA D0 frozen representation compatibility audit.

This module implements the data-boundary and mechanical-decision parts of
``ckda_d0_representation_compatibility_audit_preregistered_20260811.md``.
It never reads labels or scores and never emits a representation vector.

The raw census deliberately reuses the validated CKBU TShark decoder.  It
scans only the union of past-and-current prefixes made visible by frozen fit
targets, checkpoints after every source/member, and fails closed before a raw
file is opened when a FINAL marker appears.
"""

from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import importlib.util
import ipaddress
import json
import math
import os
import sys
import tempfile
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


ISSUE = "issue27ckda_d0_representation_compatibility_audit_v1_2026-08-11"
CONTRACT_SHA256 = "ac4e2c2093811929e0fd20b65bb0c727ef3f872f6f7586b3049cf5758fc9c8b5"
FINAL_MARKERS = ("cooler-motor", "seed37", "seed_37", "seed-37", "seed47", "seed_47", "seed-47")
I1_MIN_SESSIONS = 500_000
I1_MIN_TOKENS = 10_000_000
CANDIDATES = ("E1", "E2", "E3", "I1")
EXPECTED_NONALLOWLIST_FIT_SOURCES = {
    "processed/iotsim-cooler-motor-5.csv": "FINAL_DENYLIST",
    "processed/iotsim-hydraulic-system-1.csv": "UPSTREAM_RAW51_UNOBSERVABLE_MASK",
}

AUDIT_FIELDS = (
    "candidate_id",
    "official_paper_url",
    "official_repo_url",
    "official_repo_commit",
    "official_release",
    "checkpoint_url",
    "checkpoint_sha256",
    "license_id",
    "license_research_use_ok",
    "license_weights_redistribution_ok",
    "identity_status",
    "pretraining_corpora",
    "pretraining_collection_dates",
    "pretraining_iot_ics_disclosed",
    "iotsim_overlap_evidence",
    "ton_iot_overlap_evidence",
    "overlap_risk",
    "native_input_unit",
    "required_payload",
    "required_fields",
    "target_fitted_tokenizer_required",
    "strict_prefix_supported",
    "full_session_then_slice_required",
    "uid_join_deterministic",
    "fit_visible_unique_packets",
    "fit_encodable_unique_packets",
    "fit_encodable_fraction",
    "select_static_target_fraction",
    "report_static_target_fraction",
    "ton_metadata_gap_status",
    "final_files_opened",
    "pilot_raw_packets",
    "pilot_candidate_tokens",
    "pilot_peak_rss_bytes",
    "pilot_peak_vram_bytes",
    "pilot_median_raw_packets_per_second",
    "pilot_median_candidate_tokens_per_second",
    "projected_nonfinal_wall_seconds",
    "checkpoint_resume_supported",
    "dependency_lock_reproducible",
    "maturity_grade",
    "custom_adapter_files",
    "custom_adapter_loc",
    "i1_fit_sessions",
    "i1_fit_tokens",
    "i1_data_gate",
    "hard_gate_status",
    "hard_gate_reasons",
    "ranking_tuple",
    "evidence_manifest_path",
)

CUTOFF_FIELDS = (
    "dataset_kind",
    "source_id",
    "container_path",
    "pcap_member",
    "fit_cutoff_event_position_inclusive",
    "fit_role_basis",
    "lineage_source",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temp.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temp, path)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(temp, path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def fail_if_final(value: Any, context: str) -> None:
    text = str(value).replace("\\", "/").lower()
    hit = next((marker for marker in FINAL_MARKERS if marker in text), None)
    if hit is not None:
        raise RuntimeError(
            "CKDA_D0_ENGINEERING_FAILURE_FINAL_EXCLUSION "
            f"context={context} marker={hit}"
        )


def verify_contract(contract: Path) -> None:
    observed = sha256_file(Path(contract))
    if observed != CONTRACT_SHA256:
        raise RuntimeError(f"FROZEN contract SHA drift: {observed} != {CONTRACT_SHA256}")


def stage_contains_fit(value: Any) -> bool:
    return "fit" in {part.strip() for part in str(value).split(";") if part.strip()}


def prepare_cutoffs(args: argparse.Namespace) -> None:
    """Materialize the exact fit-visible raw-prefix manifest without raw opens."""

    verify_contract(args.contract)
    rows: list[dict[str, Any]] = []

    gotham_allow = pd.read_csv(Path(args.gotham_allowlist))
    if list(gotham_allow.columns) != ["source_group"]:
        raise RuntimeError(f"Gotham allowlist schema drift: {list(gotham_allow.columns)}")
    gotham_allowed = set(gotham_allow["source_group"].astype(str))
    if not gotham_allowed:
        raise RuntimeError("empty Gotham allowlist")
    for source in gotham_allowed:
        fail_if_final(source, "gotham_allowlist")

    auxiliary_allow = pd.read_csv(Path(args.aux_allowlist))
    if list(auxiliary_allow.columns) != ["source_group"]:
        raise RuntimeError(f"auxiliary allowlist schema drift: {list(auxiliary_allow.columns)}")
    auxiliary_allowed = set(auxiliary_allow["source_group"].astype(str))
    if not auxiliary_allowed:
        raise RuntimeError("empty auxiliary allowlist")
    for source in auxiliary_allowed:
        fail_if_final(source, "auxiliary_allowlist")

    targets = pd.read_csv(Path(args.base_targets))
    required_targets = {"source_group", "source_cache_key", "recorded_index", "stages", "roles"}
    if required_targets - set(targets.columns):
        raise RuntimeError(f"base targets missing fields: {sorted(required_targets - set(targets.columns))}")
    all_fit = targets[targets["stages"].map(stage_contains_fit)].copy()
    excluded_fit = sorted(set(all_fit["source_group"].astype(str)) - gotham_allowed)
    if set(excluded_fit) != set(EXPECTED_NONALLOWLIST_FIT_SOURCES):
        raise RuntimeError(
            "fit allowlist exclusion drift: "
            f"{excluded_fit} != {sorted(EXPECTED_NONALLOWLIST_FIT_SOURCES)}"
        )
    fit = all_fit[all_fit["source_group"].astype(str).isin(gotham_allowed)].copy()
    if fit.empty:
        raise RuntimeError("no frozen fit targets")
    if fit[["source_group", "recorded_index"]].duplicated().any():
        raise RuntimeError("duplicate frozen fit target identity")

    source_plan = pd.read_csv(Path(args.gotham_source_plan))
    source_by_name = {str(item.source_group): item for item in source_plan.itertuples(index=False)}
    for source, frame in fit.groupby("source_group", sort=True):
        source = str(source)
        fail_if_final(source, "gotham_fit_source")
        if source not in source_by_name:
            raise RuntimeError(f"fit source absent from Gotham plan: {source}")
        item = source_by_name[source]
        cache = Path(args.gotham_cache_dir) / f"{item.source_cache_key}.npz"
        if not cache.is_file():
            raise RuntimeError(f"fit lineage cache missing: {cache}")
        with np.load(cache, allow_pickle=False) as values:
            recorded = values["recorded_index"].astype(np.int64)
            positions = values["target_event_position_within_capture"].astype(np.int64)
            members = values["raw_source_path"].astype(str)
        if len(recorded) != len(set(recorded.tolist())):
            raise RuntimeError(f"nonunique recorded_index lineage: {source}")
        lookup = {
            int(index): (str(member), int(position))
            for index, member, position in zip(recorded, members, positions)
        }
        missing = sorted(set(frame["recorded_index"].astype(int)) - set(lookup))
        if missing:
            raise RuntimeError(f"fit lineage miss: {source}: {len(missing)}")
        cutoffs: dict[str, int] = {}
        for index in frame["recorded_index"].astype(int):
            member, position = lookup[int(index)]
            fail_if_final(member, "gotham_fit_member")
            cutoffs[member] = max(cutoffs.get(member, -1), position)
        for member, cutoff in sorted(cutoffs.items()):
            rows.append(
                {
                    "dataset_kind": "gotham_zip",
                    "source_id": source,
                    "container_path": str(Path(args.gotham_zip)),
                    "pcap_member": member,
                    "fit_cutoff_event_position_inclusive": cutoff,
                    "fit_role_basis": ";".join(sorted(set(frame["roles"].astype(str)))),
                    "lineage_source": str(cache),
                }
            )

    auxiliary = pd.read_csv(Path(args.aux_source_plan))
    needed_aux = {
        "source_group",
        "role",
        "raw_source_path",
        "last_target_event_position",
    }
    if needed_aux - set(auxiliary.columns):
        raise RuntimeError(f"auxiliary plan missing fields: {sorted(needed_aux - set(auxiliary.columns))}")
    unexpected_aux = sorted(
        set(auxiliary.loc[auxiliary["role"].astype(str) == "aux_fit", "source_group"].astype(str))
        - auxiliary_allowed
    )
    aux_fit = auxiliary[
        (auxiliary["role"].astype(str) == "aux_fit")
        & auxiliary["source_group"].astype(str).isin(auxiliary_allowed)
    ].copy()
    for item in aux_fit.sort_values("source_group", kind="mergesort").itertuples(index=False):
        fail_if_final(item.source_group, "aux_fit_source")
        fail_if_final(item.raw_source_path, "aux_fit_member")
        rows.append(
            {
                "dataset_kind": "gotham_zip",
                "source_id": f"aux:{item.source_group}",
                "container_path": str(Path(args.gotham_zip)),
                "pcap_member": str(item.raw_source_path),
                "fit_cutoff_event_position_inclusive": int(item.last_target_event_position),
                "fit_role_basis": "aux_fit",
                "lineage_source": str(Path(args.aux_source_plan)),
            }
        )

    ton_manifest = pd.read_csv(Path(args.ton_manifest))
    ton_audit = pd.read_csv(Path(args.ton_audit))
    ton_paths = {
        str(item.source_file): (str(item.absolute_path), str(item.role))
        for item in ton_manifest.itertuples(index=False)
    }
    for item in ton_audit.itertuples(index=False):
        role = str(item.role)
        if not role.endswith("_fit"):
            continue
        name = str(item.raw_source_path)
        if name not in ton_paths:
            raise RuntimeError(f"fit ToN source absent from manifest: {name}")
        path, manifest_role = ton_paths[name]
        if manifest_role != role:
            raise RuntimeError(f"ToN role drift: {name}: {manifest_role} != {role}")
        fail_if_final(name, "ton_fit_source")
        decoded = int(item.decoded_events)
        if decoded <= 0:
            raise RuntimeError(f"nonpositive ToN fit prefix: {name}")
        rows.append(
            {
                "dataset_kind": "direct_pcap",
                "source_id": f"ton:{name}",
                "container_path": path,
                "pcap_member": name,
                "fit_cutoff_event_position_inclusive": decoded - 1,
                "fit_role_basis": role,
                "lineage_source": str(Path(args.ton_audit)),
            }
        )

    identities = [(row["source_id"], row["pcap_member"]) for row in rows]
    if len(identities) != len(set(identities)):
        raise RuntimeError("duplicate fit prefix identity")
    if not rows:
        raise RuntimeError("empty fit prefix manifest")
    rows.sort(key=lambda row: (str(row["source_id"]), str(row["pcap_member"])))
    out = Path(args.out)
    write_csv(out, rows, CUTOFF_FIELDS)
    audit = {
        "status": "CKDA_D0_FIT_PREFIX_MANIFEST_READY",
        "contract_sha256": CONTRACT_SHA256,
        "rows": len(rows),
        "sources": len({row["source_id"] for row in rows}),
        "manifest_sha256": sha256_file(out),
        "base_targets_sha256": sha256_file(Path(args.base_targets)),
        "gotham_source_plan_sha256": sha256_file(Path(args.gotham_source_plan)),
        "aux_source_plan_sha256": sha256_file(Path(args.aux_source_plan)),
        "ton_manifest_sha256": sha256_file(Path(args.ton_manifest)),
        "ton_audit_sha256": sha256_file(Path(args.ton_audit)),
        "gotham_allowlist_sha256": sha256_file(Path(args.gotham_allowlist)),
        "auxiliary_allowlist_sha256": sha256_file(Path(args.aux_allowlist)),
        "excluded_frozen_fit_sources_not_in_allowlist": excluded_fit,
        "excluded_frozen_fit_source_reasons": {
            source: EXPECTED_NONALLOWLIST_FIT_SOURCES[source] for source in excluded_fit
        },
        "excluded_aux_fit_sources_not_in_allowlist": unexpected_aux,
        "final_files_opened": 0,
        "label_columns_read": 0,
    }
    atomic_json(out.with_suffix(".json"), audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def load_ckbu(path: Path):
    spec = importlib.util.spec_from_file_location("ckda_ckbu", Path(path))
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import CKBU decoder: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def packed_endpoint(address: str, port: int) -> tuple[bytes, int]:
    try:
        packed = ipaddress.ip_address(address).packed
    except ValueError:
        packed = b"\xff" + str(address).encode("utf-8", errors="replace")
    return packed, int(port)


def session_key(event: Any) -> tuple[Any, ...] | None:
    if int(event.ip_version) not in {4, 6}:
        return None
    left = packed_endpoint(str(event.src), int(event.src_port))
    right = packed_endpoint(str(event.dst), int(event.dst_port))
    ordered = tuple(sorted((left, right)))
    return int(event.ip_proto), ordered[0], ordered[1]


def encodable(event: Any) -> dict[str, bool]:
    ip = int(event.ip_version) in {4, 6}
    return {
        "E1": ip,
        "E2": int(event.ip_version) == 4,
        "E3": ip and int(event.ip_proto) in {6, 17},
        "I1": ip,
    }


def open_rows(ckbu: Any, row: dict[str, str], tshark: str):
    cutoff = int(row["fit_cutoff_event_position_inclusive"])
    limit = cutoff + 1
    if row["dataset_kind"] == "gotham_zip":
        archive = zipfile.ZipFile(Path(row["container_path"]))
        names = set(archive.namelist())
        member = str(row["pcap_member"])
        if member not in names:
            archive.close()
            raise RuntimeError(f"planned archive member missing: {member}")
        return archive, ckbu.iter_tshark_rows(tshark, archive=archive, member=member, packet_limit=limit)
    if row["dataset_kind"] == "direct_pcap":
        path = Path(row["container_path"])
        if not path.is_file():
            raise RuntimeError(f"planned fit PCAP missing: {path}")
        return None, ckbu.iter_tshark_rows(tshark, pcap_path=path, packet_limit=limit)
    raise RuntimeError(f"unknown dataset_kind: {row['dataset_kind']}")


def run_census(args: argparse.Namespace) -> None:
    verify_contract(args.contract)
    cutoff_path = Path(args.cutoffs)
    rows = read_csv(cutoff_path)
    if tuple(rows[0]) != CUTOFF_FIELDS:
        raise RuntimeError(f"cutoff schema drift: {tuple(rows[0])}")
    for row in rows:
        fail_if_final(row["source_id"], "census_source")
        fail_if_final(row["pcap_member"], "census_member")
        fail_if_final(row["container_path"], "census_container")

    manifest_sha = sha256_file(cutoff_path)
    ckbu = load_ckbu(Path(args.ckbu_decoder))
    out = Path(args.out)
    checkpoint_dir = out / "source_checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    aggregate: list[dict[str, Any]] = []
    all_session_count = 0
    encodable_totals = Counter()
    visible_total = 0
    pilot_sessions: dict[str, dict[str, Any]] = {}
    pilot_packets = 0

    def merge_pilot(records: list[dict[str, Any]]) -> None:
        nonlocal pilot_packets
        for record in records:
            session_hash = str(record["session_sha256"])
            if session_hash not in pilot_sessions and len(pilot_sessions) >= 100:
                break
            if session_hash not in pilot_sessions:
                pilot_sessions[session_hash] = {
                    "session_sha256": session_hash,
                    "source_id": record["source_id"],
                    "pcap_member": record["pcap_member"],
                    "packets": 0,
                }
            remaining = max(0, 100_000 - pilot_packets)
            accepted = min(remaining, int(record["packets"]))
            pilot_sessions[session_hash]["packets"] += accepted
            pilot_packets += accepted
            if pilot_packets >= 100_000:
                break

    for source_index, row in enumerate(rows):
        identity = f"{row['source_id']}\x1f{row['pcap_member']}"
        key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        checkpoint = checkpoint_dir / f"{key}.json"
        if checkpoint.is_file():
            value = json.loads(checkpoint.read_text(encoding="utf-8"))
            if value.get("manifest_sha256") != manifest_sha or value.get("identity") != identity:
                raise RuntimeError(f"checkpoint identity drift: {checkpoint}")
            if value.get("status") != "CKDA_D0_SOURCE_CENSUS_COMPLETE":
                raise RuntimeError(f"invalid checkpoint status: {checkpoint}")
            aggregate.append(value)
            visible_total += int(value["fit_visible_unique_packets"])
            encodable_totals.update({k: int(v) for k, v in value["fit_encodable_unique_packets"].items()})
            all_session_count += int(value["i1_sessions"])
            merge_pilot(list(value["pilot_sessions"]))
            continue

        started = time.monotonic()
        owner, iterator = open_rows(ckbu, row, args.tshark)
        visible = 0
        per_candidate = Counter()
        sessions: set[str] = set()
        local_pilot_sessions: dict[str, dict[str, Any]] = {}
        local_pilot_packets = 0
        try:
            for position, tshark_row in enumerate(iterator):
                if position > int(row["fit_cutoff_event_position_inclusive"]):
                    break
                event = ckbu.event_from_tshark(tshark_row)
                visible += 1
                flags = encodable(event)
                for candidate, ok in flags.items():
                    per_candidate[candidate] += int(ok)
                key_value = session_key(event)
                if key_value is not None:
                    session_digest = hashlib.sha256(repr((identity, key_value)).encode("utf-8")).hexdigest()
                    sessions.add(session_digest)
                    if len(local_pilot_sessions) < 100 or session_digest in local_pilot_sessions:
                        record = local_pilot_sessions.setdefault(
                            session_digest,
                            {
                                "session_sha256": session_digest,
                                "source_id": row["source_id"],
                                "pcap_member": row["pcap_member"],
                                "packets": 0,
                            },
                        )
                        if local_pilot_packets < 100_000:
                            record["packets"] += 1
                            local_pilot_packets += 1
                if visible % 100_000 == 0:
                    print(
                        "CKDA_D0_CENSUS_PROGRESS "
                        f"source_index={source_index} member={row['pcap_member']} packets={visible}",
                        flush=True,
                    )
        finally:
            if owner is not None:
                owner.close()
        expected = int(row["fit_cutoff_event_position_inclusive"]) + 1
        if visible != expected:
            raise RuntimeError(
                f"fit prefix incomplete: {identity}: decoded={visible} expected={expected}"
            )
        value = {
            "status": "CKDA_D0_SOURCE_CENSUS_COMPLETE",
            "manifest_sha256": manifest_sha,
            "identity": identity,
            "source_id": row["source_id"],
            "pcap_member": row["pcap_member"],
            "fit_cutoff_event_position_inclusive": int(row["fit_cutoff_event_position_inclusive"]),
            "fit_visible_unique_packets": visible,
            "fit_encodable_unique_packets": {candidate: int(per_candidate[candidate]) for candidate in CANDIDATES},
            "i1_sessions": len(sessions),
            "pilot_sessions": list(local_pilot_sessions.values()),
            "seconds": time.monotonic() - started,
            "raw_label_columns_read": 0,
            "final_files_opened": 0,
        }
        atomic_json(checkpoint, value)
        aggregate.append(value)
        visible_total += visible
        encodable_totals.update(per_candidate)
        all_session_count += len(sessions)
        merge_pilot(list(local_pilot_sessions.values()))
        print(
            "CKDA_D0_SOURCE_CENSUS_COMPLETE "
            f"source_index={source_index} member={row['pcap_member']} packets={visible} sessions={len(sessions)}",
            flush=True,
        )

    i1_tokens = int(encodable_totals["I1"])
    i1_sessions = all_session_count
    result = {
        "status": "CKDA_D0_DATA_CENSUS_COMPLETE",
        "issue": ISSUE,
        "contract_sha256": CONTRACT_SHA256,
        "fit_prefix_manifest": str(cutoff_path),
        "fit_prefix_manifest_sha256": manifest_sha,
        "fit_prefix_rows": len(rows),
        "fit_sources": len({row["source_id"] for row in rows}),
        "fit_visible_unique_packets": visible_total,
        "fit_encodable_unique_packets": {candidate: int(encodable_totals[candidate]) for candidate in CANDIDATES},
        "fit_encodable_fraction": {
            candidate: (float(encodable_totals[candidate]) / visible_total if visible_total else None)
            for candidate in CANDIDATES
        },
        "i1_fit_sessions": i1_sessions,
        "i1_fit_tokens": i1_tokens,
        "i1_data_gate": "PASS" if i1_sessions >= I1_MIN_SESSIONS and i1_tokens >= I1_MIN_TOKENS else "FAIL",
        "i1_min_sessions": I1_MIN_SESSIONS,
        "i1_min_tokens": I1_MIN_TOKENS,
        "pilot_sessions": len(pilot_sessions),
        "pilot_raw_packets": pilot_packets,
        "raw_label_columns_read": 0,
        "final_files_opened": 0,
        "source_checkpoint_count": len(aggregate),
        "source_checkpoint_manifest_sha256": sha256_json(
            sorted((value["identity"], sha256_json(value)) for value in aggregate)
        ),
    }
    atomic_json(out / "ckda_d0_data_census.json", result)
    write_csv(
        out / "ckda_d0_pilot_session_manifest.csv",
        sorted(pilot_sessions.values(), key=lambda value: value["session_sha256"]),
        ("session_sha256", "source_id", "pcap_member", "packets"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))


def bool_text(value: Any) -> str:
    return "true" if bool(value) else "false"


def hard_reasons(candidate: str, evidence: dict[str, Any], census: dict[str, Any], pilot: dict[str, Any] | None) -> list[str]:
    reasons = []
    if not evidence.get("license_research_use_ok", False):
        reasons.append("license_research_use_not_granted")
    checkpoint = str(evidence.get("checkpoint_sha256", ""))
    if candidate != "I1" and len(checkpoint) != 64:
        reasons.append("complete_checkpoint_sha256_missing")
    if evidence.get("overlap_risk") in {"POSSIBLE_OVERLAP", "CONFIRMED_OVERLAP"}:
        reasons.append(f"overlap_risk={evidence.get('overlap_risk')}")
    if evidence.get("target_fitted_tokenizer_required", False):
        reasons.append("target_fitted_tokenizer_required")
    if not evidence.get("strict_prefix_supported", False):
        reasons.append("strict_prefix_not_supported")
    if evidence.get("full_session_then_slice_required", True):
        reasons.append("full_session_then_slice_required")
    if not evidence.get("uid_join_deterministic", False):
        reasons.append("uid_join_not_deterministic")
    if evidence.get("maturity_grade") == "C":
        reasons.append("maturity_grade_C")
    if not evidence.get("dependency_lock_reproducible", False):
        reasons.append("dependency_lock_not_reproducible")
    if candidate == "I1" and census.get("i1_data_gate") != "PASS":
        reasons.append("i1_data_gate_FAIL")
    if not reasons and pilot is None:
        reasons.append("resource_pilot_missing")
    if not reasons and int(evidence.get("prefix_native_rank", 0)) == 1:
        if not str((pilot or {}).get("custom_adapter_files", "")).strip():
            reasons.append("custom_adapter_files_missing")
        try:
            adapter_loc = int((pilot or {}).get("custom_adapter_loc", ""))
        except (TypeError, ValueError):
            adapter_loc = -1
        if adapter_loc < 0:
            reasons.append("custom_adapter_loc_missing")
    return reasons


def compare_ranked(left: dict[str, Any], right: dict[str, Any]) -> int:
    overlap_rank = {"KNOWN_DISJOINT": 0, "NO_KNOWN_OVERLAP": 1}
    maturity_rank = {"A": 0, "B": 1, "I": 2}
    candidate_rank = {candidate: index for index, candidate in enumerate(CANDIDATES)}

    def ordinary(a: Any, b: Any) -> int:
        return (a > b) - (a < b)

    comparisons = (
        ordinary(overlap_rank[left["overlap_risk"]], overlap_rank[right["overlap_risk"]]),
        (
            0
            if abs(float(left["fit_encodable_fraction"]) - float(right["fit_encodable_fraction"])) < 1e-6
            else ordinary(-float(left["fit_encodable_fraction"]), -float(right["fit_encodable_fraction"]))
        ),
        (
            0
            if abs(float(left["select_static_target_fraction"]) - float(right["select_static_target_fraction"])) < 1e-6
            else ordinary(-float(left["select_static_target_fraction"]), -float(right["select_static_target_fraction"]))
        ),
        (
            0
            if abs(float(left["report_static_target_fraction"]) - float(right["report_static_target_fraction"])) < 1e-6
            else ordinary(-float(left["report_static_target_fraction"]), -float(right["report_static_target_fraction"]))
        ),
        ordinary(0 if left["candidate_id"] == "I1" else 1, 0 if right["candidate_id"] == "I1" else 1),
        ordinary(maturity_rank[left["maturity_grade"]], maturity_rank[right["maturity_grade"]]),
        ordinary(int(left["custom_adapter_loc"]), int(right["custom_adapter_loc"])),
    )
    for result in comparisons:
        if result:
            return result
    left_cost = float(left["projected_nonfinal_wall_seconds"])
    right_cost = float(right["projected_nonfinal_wall_seconds"])
    if abs(left_cost - right_cost) > 0.10 * min(left_cost, right_cost):
        result = ordinary(left_cost, right_cost)
        if result:
            return result
    return ordinary(candidate_rank[left["candidate_id"]], candidate_rank[right["candidate_id"]])


def compile_audit(args: argparse.Namespace) -> None:
    verify_contract(args.contract)
    evidence_document = json.loads(Path(args.evidence).read_text(encoding="utf-8"))
    if evidence_document.get("contract_sha256") != CONTRACT_SHA256:
        raise RuntimeError("official evidence contract SHA drift")
    census = json.loads(Path(args.census).read_text(encoding="utf-8"))
    if census.get("status") != "CKDA_D0_DATA_CENSUS_COMPLETE":
        raise RuntimeError("data census is not terminal")
    if int(census.get("final_files_opened", -1)) != 0 or int(census.get("raw_label_columns_read", -1)) != 0:
        raise RuntimeError("data boundary failure in census")
    pilot_rows = read_csv(Path(args.resource_pilot)) if args.resource_pilot else []
    pilots = {row["candidate_id"]: row for row in pilot_rows if row.get("status") == "PASS"}

    rows: list[dict[str, Any]] = []
    for candidate in CANDIDATES:
        evidence = evidence_document["candidates"][candidate]
        pilot = pilots.get(candidate)
        reasons = hard_reasons(candidate, evidence, census, pilot)
        visible = int(census["fit_visible_unique_packets"])
        candidate_encodable = int(census["fit_encodable_unique_packets"][candidate])
        audit: dict[str, Any] = {field: "" for field in AUDIT_FIELDS}
        for field in AUDIT_FIELDS:
            if field in evidence:
                audit[field] = evidence[field]
        audit.update(
            {
                "candidate_id": candidate,
                "license_research_use_ok": bool_text(evidence["license_research_use_ok"]),
                "license_weights_redistribution_ok": bool_text(evidence["license_weights_redistribution_ok"]),
                "pretraining_iot_ics_disclosed": bool_text(evidence["pretraining_iot_ics_disclosed"]),
                "target_fitted_tokenizer_required": bool_text(evidence["target_fitted_tokenizer_required"]),
                "strict_prefix_supported": bool_text(evidence["strict_prefix_supported"]),
                "full_session_then_slice_required": bool_text(evidence["full_session_then_slice_required"]),
                "uid_join_deterministic": bool_text(evidence["uid_join_deterministic"]),
                "fit_visible_unique_packets": visible,
                "fit_encodable_unique_packets": candidate_encodable,
                "fit_encodable_fraction": f"{candidate_encodable / visible:.12f}" if visible else "",
                "select_static_target_fraction": "1.000000000000",
                "report_static_target_fraction": "1.000000000000",
                "ton_metadata_gap_status": "UNIFIED_MISSING_STATE_REQUIRED",
                "final_files_opened": 0,
                "checkpoint_resume_supported": bool_text(evidence["checkpoint_resume_supported"]),
                "dependency_lock_reproducible": bool_text(evidence["dependency_lock_reproducible"]),
                "custom_adapter_files": "",
                "custom_adapter_loc": "",
                "i1_fit_sessions": census["i1_fit_sessions"] if candidate == "I1" else "",
                "i1_fit_tokens": census["i1_fit_tokens"] if candidate == "I1" else "",
                "i1_data_gate": census["i1_data_gate"] if candidate == "I1" else "NOT_APPLICABLE",
                "hard_gate_status": "FAIL" if reasons else "PASS",
                "hard_gate_reasons": ";".join(reasons),
                "evidence_manifest_path": str(Path(args.evidence_manifest)),
            }
        )
        if pilot is not None:
            for field in (
                "pilot_raw_packets",
                "pilot_candidate_tokens",
                "pilot_peak_rss_bytes",
                "pilot_peak_vram_bytes",
                "pilot_median_raw_packets_per_second",
                "pilot_median_candidate_tokens_per_second",
                "projected_nonfinal_wall_seconds",
            ):
                audit[field] = pilot[field]
            audit["custom_adapter_files"] = pilot.get("custom_adapter_files", "")
            audit["custom_adapter_loc"] = pilot.get("custom_adapter_loc", "")
        elif candidate == "I1":
            audit["custom_adapter_files"] = "0"
            audit["custom_adapter_loc"] = "0"
        rows.append(audit)

    pass_rows = [row for row in rows if row["hard_gate_status"] == "PASS"]
    overlap_rank = {"KNOWN_DISJOINT": 0, "NO_KNOWN_OVERLAP": 1}
    maturity_rank = {"A": 0, "B": 1, "I": 2}
    candidate_rank = {candidate: index for index, candidate in enumerate(CANDIDATES)}
    for row in pass_rows:
        candidate = row["candidate_id"]
        evidence = evidence_document["candidates"][candidate]
        ranking = (
            overlap_rank[row["overlap_risk"]],
            -float(row["fit_encodable_fraction"]),
            -float(row["select_static_target_fraction"]),
            -float(row["report_static_target_fraction"]),
            int(evidence["prefix_native_rank"]),
            maturity_rank[row["maturity_grade"]],
            int(row["custom_adapter_loc"] or 0),
            float(row["projected_nonfinal_wall_seconds"]),
            candidate_rank[candidate],
        )
        row["ranking_tuple"] = json.dumps(ranking, separators=(",", ":"))
    pass_rows.sort(key=functools.cmp_to_key(compare_ranked))
    for row in rows:
        if not row["ranking_tuple"]:
            row["ranking_tuple"] = "NOT_RANKED_HARD_GATE_FAIL"

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    write_csv(out / "ckda_d0_candidate_audit.csv", rows, AUDIT_FIELDS)
    verdict = {
        "status": (
            "CKDA_D0_PRIMARY_AND_OPTIONAL_BACKUP_FROZEN"
            if pass_rows
            else "CKDA_D0_NO_COMPATIBLE_REPRESENTATION"
        ),
        "primary": pass_rows[0]["candidate_id"] if pass_rows else None,
        "backup": pass_rows[1]["candidate_id"] if len(pass_rows) > 1 else None,
        "ranked_candidates": [row["candidate_id"] for row in pass_rows],
        "contract_sha256": CONTRACT_SHA256,
        "candidate_audit_sha256": sha256_file(out / "ckda_d0_candidate_audit.csv"),
        "final_files_opened": 0,
        "performance_embeddings_generated": 0,
        "labels_read": 0,
    }
    atomic_json(out / "ckda_d0_verdict.json", verdict)
    print(json.dumps(verdict, indent=2, sort_keys=True))


def contract_test(_: argparse.Namespace) -> None:
    assert len(AUDIT_FIELDS) == 50, len(AUDIT_FIELDS)
    assert len(CUTOFF_FIELDS) == 7
    assert stage_contains_fit("report;fit")
    assert not stage_contains_fit("select;report")
    try:
        fail_if_final("processed/iotsim-cooler-motor-5.csv", "synthetic")
    except RuntimeError as exc:
        assert "FINAL_EXCLUSION" in str(exc)
    else:
        raise AssertionError("FINAL marker did not fail closed")
    class Event:
        ip_version = 4
        ip_proto = 6
        src = "10.0.0.2"
        dst = "10.0.0.1"
        src_port = 443
        dst_port = 50000
    forward = session_key(Event())
    Event.src, Event.dst, Event.src_port, Event.dst_port = "10.0.0.1", "10.0.0.2", 50000, 443
    reverse = session_key(Event())
    assert forward == reverse
    assert encodable(Event()) == {"E1": True, "E2": True, "E3": True, "I1": True}
    print(json.dumps({"status": "PASS", "tests": 8, "audit_fields": len(AUDIT_FIELDS)}, indent=2))


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    default_contract = root / "runs/mainline_docs/ckda_d0_representation_compatibility_audit_preregistered_20260811.md"
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)

    test = sub.add_parser("contract-test")
    test.set_defaults(func=contract_test)

    cutoffs = sub.add_parser("prepare-cutoffs")
    cutoffs.add_argument("--contract", type=Path, default=default_contract)
    cutoffs.add_argument("--base-targets", type=Path, required=True)
    cutoffs.add_argument("--gotham-allowlist", type=Path, required=True)
    cutoffs.add_argument("--aux-allowlist", type=Path, required=True)
    cutoffs.add_argument("--gotham-source-plan", type=Path, required=True)
    cutoffs.add_argument("--gotham-cache-dir", type=Path, required=True)
    cutoffs.add_argument("--aux-source-plan", type=Path, required=True)
    cutoffs.add_argument("--ton-manifest", type=Path, required=True)
    cutoffs.add_argument("--ton-audit", type=Path, required=True)
    cutoffs.add_argument("--gotham-zip", type=Path, required=True)
    cutoffs.add_argument("--out", type=Path, required=True)
    cutoffs.set_defaults(func=prepare_cutoffs)

    census = sub.add_parser("census")
    census.add_argument("--contract", type=Path, default=default_contract)
    census.add_argument("--cutoffs", type=Path, required=True)
    census.add_argument("--ckbu-decoder", type=Path, default=root / "repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py")
    census.add_argument("--tshark", default="tshark")
    census.add_argument("--out", type=Path, required=True)
    census.set_defaults(func=run_census)

    compile_cmd = sub.add_parser("compile")
    compile_cmd.add_argument("--contract", type=Path, default=default_contract)
    compile_cmd.add_argument("--evidence", type=Path, required=True)
    compile_cmd.add_argument("--evidence-manifest", type=Path, required=True)
    compile_cmd.add_argument("--census", type=Path, required=True)
    compile_cmd.add_argument("--resource-pilot", type=Path)
    compile_cmd.add_argument("--out", type=Path, required=True)
    compile_cmd.set_defaults(func=compile_audit)
    return result


def main() -> None:
    args = parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
