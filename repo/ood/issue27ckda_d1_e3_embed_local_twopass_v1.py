#!/usr/bin/env python3
"""Memory-bounded local adapter for the frozen CKDA D1 E3 embedder.

The frozen one-pass implementation retains prefix state for every session seen
before the last target in a capture.  The local contingency host has 16 GiB of
RAM rather than the formal job's 64 GiB allocation.  This adapter preserves the
same target prefixes and batching order with two deterministic decoder passes:

1. discover the canonical sessions that contain frozen target positions;
2. retain state only for those sessions and release it after their last target.

The frozen tokenizer, model, checkpoint schema, member identity, combine step,
and target order are reused without modification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_e3_embed_v1 as frozen
import issue27ckda_d1_representation_probe_v1 as core


def install_union_tshark_frontend(ckbu: Any, d0: Any) -> Any:
    """Expose the union of CKBU identity fields and E3 netFound fields.

    The frozen D1 embedder decodes with CKBU but translates with the D0 E3
    frontend.  Their requested TShark field sets are not supersets of one
    another.  This local adapter requests their deterministic ordered union,
    then gives the same row to both consumers.  Windows missing-field
    sentinels are normalized to the Linux empty-string representation.
    """
    if bool(getattr(ckbu, "_ckda_local_union_frontend", False)):
        return ckbu
    union_fields = tuple(dict.fromkeys(tuple(ckbu.TSHARK_FIELDS) + tuple(d0.TSHARK_FIELDS)))
    if not set(ckbu.TSHARK_FIELDS).issubset(union_fields):
        raise RuntimeError("local union frontend lost CKBU fields")
    if not set(d0.TSHARK_FIELDS).issubset(union_fields):
        raise RuntimeError("local union frontend lost netFound fields")
    d0.TSHARK_FIELDS = union_fields
    ckbu._ckda_local_missing_sentinels_seen = 0

    def union_rows(
        tshark: str,
        pcap_path: Optional[Path] = None,
        archive: Any = None,
        member: Optional[str] = None,
        packet_limit: Optional[int] = None,
    ):
        if packet_limit is None:
            raise RuntimeError("local union frontend requires a causal packet cutoff")
        if pcap_path is not None:
            iterator = d0.iter_tshark(
                tshark, Path(pcap_path), "", "direct_pcap", int(packet_limit)
            )
        elif archive is not None and member is not None:
            iterator = d0.iter_tshark(
                tshark, Path(archive.filename), str(member), "gotham_zip", int(packet_limit)
            )
        else:
            raise ValueError("provide either pcap_path or archive+member")
        for row in iterator:
            count = sum(value is None or value == "None" for value in row.values())
            ckbu._ckda_local_missing_sentinels_seen += count
            yield {
                name: "" if value is None or value == "None" else value
                for name, value in row.items()
            }

    ckbu.iter_tshark_rows = union_rows
    ckbu._ckda_local_union_frontend = True
    ckbu._ckda_local_union_fields = union_fields
    return ckbu


def canonical_session(event: Any) -> Optional[Tuple[Any, ...]]:
    if int(event.ip_version) not in {4, 6} or int(event.ip_proto) not in {6, 17}:
        return None
    left = (str(event.src), int(event.src_port))
    right = (str(event.dst), int(event.dst_port))
    return (int(event.ip_proto),) + tuple(sorted((left, right)))


def target_session_is_active(
    session: Optional[Tuple[Any, ...]],
    position: int,
    last_target: Dict[Tuple[Any, ...], int],
) -> bool:
    """Return whether this packet can still contribute to a frozen target.

    A target session may occur again after its own last selected target while
    another session keeps the capture-level prefix open.  Such tail packets
    must not recreate state that was deliberately released at the last target.
    """
    if session is None:
        return False
    cutoff = last_target.get(session)
    return cutoff is not None and position <= cutoff


def discover_target_sessions(
    part: pd.DataFrame,
    ckbu: Any,
    tshark: str,
) -> Tuple[Dict[int, Optional[Tuple[Any, ...]]], int]:
    by_position = {
        int(row.target_event_position_within_capture): row
        for row in part.itertuples(index=False)
    }
    maximum = max(by_position)
    kind = str(part.iloc[0]["dataset_kind"])
    container = Path(str(part.iloc[0]["container_path"]))
    member = str(part.iloc[0]["raw_source_path"])
    owner, iterator = frozen.open_member(ckbu, kind, container, member, tshark, maximum + 1)
    discovered: Dict[int, Optional[Tuple[Any, ...]]] = {}
    decoded = 0
    try:
        for position, raw in enumerate(iterator):
            if position > maximum:
                raise RuntimeError("local discovery decoder crossed target cutoff")
            decoded += 1
            if position not in by_position:
                continue
            event = ckbu.event_from_tshark(raw)
            session = canonical_session(event)
            if session is None or not math.isfinite(float(event.timestamp)):
                session = None
            discovered[position] = session
            if decoded % 50_000 == 0 or len(discovered) == len(by_position):
                print(
                    "CKDA_D1_LOCAL_DISCOVERY_PROGRESS member=%s packets=%d/%d targets=%d/%d" %
                    (member, decoded, maximum + 1, len(discovered), len(by_position)),
                    flush=True,
                )
    finally:
        if owner is not None:
            owner.close()
    if decoded != maximum + 1:
        raise RuntimeError("local discovery prefix incomplete: %d/%d" % (decoded, maximum + 1))
    if set(discovered) != set(by_position):
        raise RuntimeError("local discovery target coverage drift")
    return discovered, decoded


def process_member_twopass(
    part: pd.DataFrame,
    plan_sha: str,
    ckbu: Any,
    d0: Any,
    model: Any,
    tokenizer: Any,
    collator: Any,
    tshark: str,
    device: str,
    batch_size: int,
    checkpoint: Path,
) -> Dict[str, object]:
    identity = frozen.member_identity(part)
    expected_uids = part["uid"].astype(str).tolist()
    if checkpoint.is_file():
        frozen.validate_member_checkpoint(checkpoint, identity, plan_sha, expected_uids)
        return {
            "status": "REUSED",
            "checkpoint": str(checkpoint),
            "rows": len(part),
            "sha256": core.sha256_file(checkpoint),
            "decoder_passes": 0,
            "peak_retained_target_sessions": 0,
        }
    if part["target_event_position_within_capture"].duplicated().any():
        raise RuntimeError("member has duplicate target event position")

    by_position = {
        int(row.target_event_position_within_capture): row
        for row in part.itertuples(index=False)
    }
    maximum = max(by_position)
    discovered, first_pass_packets = discover_target_sessions(part, ckbu, tshark)
    last_target: Dict[Tuple[Any, ...], int] = {}
    for position, session in discovered.items():
        if session is not None:
            last_target[session] = max(position, last_target.get(session, -1))
    wanted = set(last_target)

    kind = str(part.iloc[0]["dataset_kind"])
    container = Path(str(part.iloc[0]["container_path"]))
    member = str(part.iloc[0]["raw_source_path"])
    owner, iterator = frozen.open_member(ckbu, kind, container, member, tshark, maximum + 1)
    sessions: Dict[Tuple[Any, ...], frozen.BoundedNetfoundPrefix] = {}
    unencodable_sessions = set()
    pending_rows = []
    pending_flows: List[List[Dict[str, str]]] = []
    output: Dict[str, Tuple[np.ndarray, bool, str, float, int]] = {}
    peak_sessions = 0

    def flush() -> None:
        if not pending_rows:
            return
        embedded = frozen.embed_flows(d0, model, tokenizer, collator, pending_flows, device, batch_size)
        if len(embedded) != len(pending_rows):
            raise RuntimeError("E3 local batch output count drift")
        for index, details in enumerate(pending_rows):
            uid, session_id, timestamp, position = details
            output[uid] = (embedded[index], False, session_id, timestamp, position)
        pending_rows.clear()
        pending_flows.clear()

    decoded = 0
    try:
        for position, raw in enumerate(iterator):
            if position > maximum:
                raise RuntimeError("local embedding decoder crossed target cutoff")
            decoded += 1
            event = ckbu.event_from_tshark(raw)
            session = canonical_session(event)
            timestamp = float(event.timestamp)
            if target_session_is_active(session, position, last_target):
                frozen.append_or_mark_unencodable(
                    sessions, unencodable_sessions, session, dict(raw), timestamp
                )
                peak_sessions = max(peak_sessions, len(sessions))
            target = by_position.get(position)
            if target is None:
                continue
            uid = str(target.uid)
            target_session = discovered[position]
            if target_session is None or target_session in unencodable_sessions:
                reason = (
                    "UNENCODABLE_TIMESTAMP_REGRESSION"
                    if target_session in unencodable_sessions
                    else "UNENCODABLE"
                )
                missing_session_id = hashlib.sha256(
                    repr((str(target.source_group), member, reason, position, uid)).encode("utf-8")
                ).hexdigest()
                output[uid] = (
                    np.empty(0, dtype=np.float32), True, missing_session_id, timestamp, position
                )
            else:
                if session != target_session or target_session not in sessions:
                    raise RuntimeError("local target session discovery/replay drift")
                session_id = hashlib.sha256(
                    repr((str(target.source_group), member, target_session)).encode("utf-8")
                ).hexdigest()
                pending_rows.append((uid, session_id, timestamp, position))
                pending_flows.append(sessions[target_session].flow(d0))
                if len(pending_rows) >= batch_size:
                    flush()
            if target_session is not None and position == last_target[target_session]:
                sessions.pop(target_session, None)
            if decoded % 50_000 == 0:
                print(
                    "CKDA_D1_LOCAL_EMBED_PROGRESS member=%s packets=%d/%d targets=%d/%d active=%d peak=%d" %
                    (member, decoded, maximum + 1, len(output) + len(pending_rows), len(expected_uids),
                     len(sessions), peak_sessions),
                    flush=True,
                )
        flush()
    finally:
        if owner is not None:
            owner.close()
    if decoded != maximum + 1:
        raise RuntimeError("local embedding prefix incomplete: %d/%d" % (decoded, maximum + 1))
    if sessions:
        raise RuntimeError("local target session state not fully released")
    if set(output) != set(expected_uids):
        raise RuntimeError("local member target output coverage drift")

    widths = {len(value[0]) for value in output.values() if not value[1]}
    if len(widths) != 1:
        raise RuntimeError("E3 local representation width drift")
    expected_width = int(getattr(model.config, "hidden_size", 0))
    if widths and widths != {expected_width}:
        raise RuntimeError("E3 local representation/config width mismatch")
    if expected_width <= 0:
        raise RuntimeError("E3 local config lacks positive hidden width")
    ordered = [output[uid] for uid in expected_uids]
    representation = np.zeros((len(ordered), expected_width), dtype=np.float32)
    for index, value in enumerate(ordered):
        if not value[1]:
            representation[index] = value[0]
    from issue27ckda_d1_probe_runner_v1 import atomic_npz

    atomic_npz(
        checkpoint,
        uid=np.asarray(expected_uids, dtype=np.str_),
        representation=representation,
        missing=np.asarray([value[1] for value in ordered], dtype=np.bool_),
        session_id=np.asarray([value[2] for value in ordered], dtype=np.str_),
        timestamp_epoch=np.asarray([value[3] for value in ordered], dtype=np.float64),
        event_position=np.asarray([value[4] for value in ordered], dtype=np.int64),
        member_identity_sha256=np.asarray([identity], dtype=np.str_),
        plan_sha256=np.asarray([plan_sha], dtype=np.str_),
        contract_sha256=np.asarray([core.CONTRACT_SHA256], dtype=np.str_),
    )
    frozen.validate_member_checkpoint(checkpoint, identity, plan_sha, expected_uids)
    return {
        "status": "COMPUTED_LOCAL_EXACT_TWOPASS",
        "checkpoint": str(checkpoint),
        "rows": len(part),
        "sha256": core.sha256_file(checkpoint),
        "decoder_passes": 2,
        "first_pass_packets": first_pass_packets,
        "second_pass_packets": decoded,
        "peak_retained_target_sessions": peak_sessions,
    }


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    plan = pd.read_csv(args.target_metadata, keep_default_na=False)
    plan_sha = str(args.plan_sha256)
    if len(plan_sha) != 64 or len(plan) not in {25_467, 262_050} or plan["uid"].duplicated().any():
        raise RuntimeError("target metadata/plan identity drift")
    if set(plan["dataset_kind"]) - {"gotham_zip", "direct_pcap"}:
        raise RuntimeError("target metadata dataset kind drift")
    d0 = frozen.import_file("ckda_d1_local_d0_e3", args.d0_pilot)
    ckbu = install_union_tshark_frontend(
        frozen.import_file("ckda_d1_local_ckbu_embed", args.ckbu_decoder), d0
    )
    model, tokenizer, collator = frozen.build_e3_runtime(
        d0, args.netfound_source, args.netfound_checkpoint, args.device
    )
    checkpoint_root = Path(args.checkpoint_dir)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    checkpoint_paths = []
    audits = []
    groups = list(plan.groupby(["dataset_kind", "container_path", "raw_source_path"], sort=True))
    for index, (_key, part) in enumerate(groups, start=1):
        part = part.reset_index(drop=True)
        identity = frozen.member_identity(part)
        checkpoint = checkpoint_root / (identity[:24] + ".npz")
        audit = process_member_twopass(
            part, plan_sha, ckbu, d0, model, tokenizer, collator,
            args.tshark, args.device, args.batch_size, checkpoint,
        )
        checkpoint_paths.append(checkpoint)
        audits.append(audit)
        print(
            "CKDA_D1_E3_LOCAL_MEMBER_COMPLETE index=%d/%d rows=%d status=%s peak_sessions=%d" %
            (index, len(groups), len(part), audit["status"], audit["peak_retained_target_sessions"]),
            flush=True,
        )
    audit = frozen.combine(checkpoint_paths, plan, plan_sha, args.out)
    audit["local_adapter"] = "EXACT_TWOPASS_TARGET_SESSION_FILTER_WITH_LAST_TARGET_RELEASE"
    audit["local_adapter_sha256"] = core.sha256_file(Path(__file__))
    audit["member_manifest_sha256"] = core.sha256_json(
        sorted((value["checkpoint"], value["sha256"]) for value in audits)
    )
    audit["peak_retained_target_sessions"] = max(
        (int(value["peak_retained_target_sessions"]) for value in audits), default=0
    )
    audit["windows_tshark_missing_sentinels_normalized"] = int(
        getattr(ckbu, "_ckda_local_missing_sentinels_seen", 0)
    )
    audit["union_tshark_fields"] = list(getattr(ckbu, "_ckda_local_union_fields", ()))
    audit["union_tshark_fields_sha256"] = core.sha256_json(audit["union_tshark_fields"])
    core.atomic_json(Path(args.out).with_suffix(Path(args.out).suffix + ".audit.json"), audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    parser = frozen.parser()
    parser.description = __doc__
    return parser


if __name__ == "__main__":
    run(parser().parse_args())
