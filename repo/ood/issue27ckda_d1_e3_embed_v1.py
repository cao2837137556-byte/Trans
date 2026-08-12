#!/usr/bin/env python3
"""Generate frozen E3 target-prefix embeddings with member checkpoints.

Each PCAP member is decoded once in capture order.  A target is embedded from
its current-inclusive canonical bidirectional session prefix.  Completed
member artifacts are identity-checked and reused on restart; the final union
is accepted only after exact UID coverage and atomic NPZ readback.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

import numpy as np
import pandas as pd

import issue27ckda_d1_representation_probe_v1 as core


NETFOUND_CHECKPOINT_SHA256 = "e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105"
CHECKPOINT_FIELDS = {
    "uid", "representation", "missing", "session_id", "timestamp_epoch",
    "event_position", "member_identity_sha256", "plan_sha256", "contract_sha256",
}


class BoundedNetfoundPrefix:
    """Exact netFound prefix state with a fixed 144-packet memory bound."""

    __slots__ = (
        "first_src", "first_timestamp", "latest_timestamp",
        "last_event_timestamp", "last_direction_timestamp", "bursts",
    )

    def __init__(self) -> None:
        self.first_src = ""
        self.first_timestamp = math.nan
        self.latest_timestamp = math.nan
        self.last_event_timestamp = None
        self.last_direction_timestamp = {True: None, False: None}
        self.bursts = {True: [], False: []}

    def append(self, row: Dict[str, str], timestamp: float) -> None:
        if not math.isfinite(timestamp):
            raise RuntimeError("non-finite timestamp in encodable session")
        if self.last_event_timestamp is not None and timestamp < float(self.last_event_timestamp):
            raise RuntimeError("session timestamp regressed; frozen causal order is not representable")
        self.last_event_timestamp = timestamp
        src = (row.get("ip.src") or row.get("ipv6.src") or "").strip()
        if not self.first_src:
            self.first_src = src
            self.first_timestamp = timestamp
        self.latest_timestamp = timestamp
        direction = src == self.first_src
        previous = self.last_direction_timestamp[direction]
        new_burst = previous is None or timestamp - float(previous) > 0.010
        self.last_direction_timestamp[direction] = timestamp
        bursts = self.bursts[direction]
        if new_burst:
            if len(bursts) >= 12:
                return
            bursts.append([])
        if len(bursts[-1]) < 6:
            bursts[-1].append(dict(row))

    def flow(self, d0: Any) -> Dict[str, Any]:
        retained = []
        for bursts in self.bursts.values():
            for burst in bursts:
                retained.extend(burst)
        retained.sort(key=lambda row: int(float(str(row.get("frame.number", "0") or "0"))))
        if not retained:
            raise RuntimeError("empty bounded netFound state")
        value = d0.netfound_flow(retained)
        value["flow_duration"] = max(
            0, int(round((float(self.latest_timestamp) - float(self.first_timestamp)) * 1e6))
        )
        return value


def import_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, str(Path(path)))
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def member_identity(part: pd.DataFrame) -> str:
    values = {
        "contract_sha256": core.CONTRACT_SHA256,
        "dataset_kind": str(part.iloc[0]["dataset_kind"]),
        "container_path": str(part.iloc[0]["container_path"]),
        "raw_source_path": str(part.iloc[0]["raw_source_path"]),
        "targets": sorted(
            (str(row.uid), int(row.target_event_position_within_capture))
            for row in part.itertuples(index=False)
        ),
    }
    return core.sha256_json(values)


def open_member(ckbu: Any, kind: str, container: Path, member: str, tshark: str, limit: int):
    import zipfile

    if kind == "gotham_zip":
        archive = zipfile.ZipFile(container)
        if member not in set(archive.namelist()):
            archive.close()
            raise RuntimeError("planned Gotham member absent: %s" % member)
        return archive, ckbu.iter_tshark_rows(tshark, archive=archive, member=member, packet_limit=limit)
    if kind == "direct_pcap":
        if not container.is_file():
            raise RuntimeError("planned ToN PCAP absent: %s" % container)
        return None, ckbu.iter_tshark_rows(tshark, pcap_path=container, packet_limit=limit)
    raise RuntimeError("unknown dataset kind: %s" % kind)


def build_e3_runtime(d0: Any, source_root: Path, checkpoint_dir: Path, device: str):
    import torch

    model_path = Path(checkpoint_dir) / "model.safetensors"
    if core.sha256_file(model_path) != NETFOUND_CHECKPOINT_SHA256:
        raise RuntimeError("netFound checkpoint SHA drift")
    config_type, collator_type, model_type, tokenizer_type = d0.import_netfound(source_root)
    config = config_type.from_pretrained(str(checkpoint_dir), local_files_only=True)
    config.pretraining = False
    config.compile = False
    model = model_type.from_pretrained(str(checkpoint_dir), config=config, local_files_only=True)
    model.to(device=device, dtype=torch.float32)
    model.eval()
    tokenizer = tokenizer_type(config=config)
    tokenizer.pretraining = True
    tokenizer.raw_labels = False
    collator = collator_type(pad_token_id=tokenizer.pad_token_id)
    return model, tokenizer, collator


def embed_flows(
    d0: Any,
    model: Any,
    tokenizer: Any,
    collator: Any,
    flows: Sequence[Dict[str, Any]],
    device: str,
    batch_size: int,
) -> np.ndarray:
    dataset = {key: [flow[key] for flow in flows] for key in flows[0]}
    encoded = tokenizer(dataset)
    examples = [{key: value[index] for key, value in encoded.items()} for index in range(len(flows))]
    batches = [collator(examples[start:start + batch_size]) for start in range(0, len(examples), batch_size)]
    return core.e3_forward_batches(model, batches, device=device)


def validate_member_checkpoint(path: Path, identity: str, plan_sha: str, expected_uids: Sequence[str]) -> None:
    with np.load(path, allow_pickle=False) as values:
        if set(values.files) != CHECKPOINT_FIELDS:
            raise RuntimeError("member checkpoint schema drift")
        if values["member_identity_sha256"].astype(str).tolist() != [identity]:
            raise RuntimeError("member checkpoint identity drift")
        if values["plan_sha256"].astype(str).tolist() != [plan_sha]:
            raise RuntimeError("member checkpoint plan drift")
        if values["contract_sha256"].astype(str).tolist() != [core.CONTRACT_SHA256]:
            raise RuntimeError("member checkpoint contract drift")
        if sorted(values["uid"].astype(str).tolist()) != sorted(str(value) for value in expected_uids):
            raise RuntimeError("member checkpoint UID coverage drift")
        if len(values["representation"]) != len(expected_uids):
            raise RuntimeError("member checkpoint representation count drift")


def process_member(
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
    identity = member_identity(part)
    expected_uids = part["uid"].astype(str).tolist()
    if checkpoint.is_file():
        validate_member_checkpoint(checkpoint, identity, plan_sha, expected_uids)
        return {"status": "REUSED", "checkpoint": str(checkpoint), "rows": len(part), "sha256": core.sha256_file(checkpoint)}

    kind = str(part.iloc[0]["dataset_kind"])
    container = Path(str(part.iloc[0]["container_path"]))
    member = str(part.iloc[0]["raw_source_path"])
    if part["target_event_position_within_capture"].duplicated().any():
        raise RuntimeError("member has duplicate target event position")
    by_position = {
        int(row.target_event_position_within_capture): row
        for row in part.itertuples(index=False)
    }
    maximum = max(by_position)
    owner, iterator = open_member(ckbu, kind, container, member, tshark, maximum + 1)
    sessions: Dict[Tuple[Any, ...], BoundedNetfoundPrefix] = {}
    pending_rows = []
    pending_flows: List[List[Dict[str, str]]] = []
    output: Dict[str, Tuple[np.ndarray, bool, str, float, int]] = {}

    def flush() -> None:
        if not pending_rows:
            return
        embedded = embed_flows(d0, model, tokenizer, collator, pending_flows, device, batch_size)
        if len(embedded) != len(pending_rows):
            raise RuntimeError("E3 batch output count drift")
        for index, details in enumerate(pending_rows):
            uid, session_id, timestamp, position = details
            output[uid] = (embedded[index], False, session_id, timestamp, position)
        pending_rows.clear()
        pending_flows.clear()

    decoded = 0
    try:
        for position, raw in enumerate(iterator):
            if position > maximum:
                raise RuntimeError("decoder crossed target cutoff")
            decoded += 1
            if decoded % 50_000 == 0:
                print(
                    "CKDA_D1_E3_DECODE_PROGRESS member=%s packets=%d/%d targets=%d/%d" %
                    (member, decoded, maximum + 1, len(output), len(expected_uids)),
                    flush=True,
                )
            event = ckbu.event_from_tshark(raw)
            session = None
            if int(event.ip_version) in {4, 6}:
                left = (str(event.src), int(event.src_port))
                right = (str(event.dst), int(event.dst_port))
                session = (int(event.ip_proto),) + tuple(sorted((left, right)))
                if session not in sessions:
                    sessions[session] = BoundedNetfoundPrefix()
                sessions[session].append(dict(raw), float(event.timestamp))
            target = by_position.get(position)
            if target is None:
                continue
            uid = str(target.uid)
            timestamp = float(event.timestamp)
            if session is None or int(event.ip_proto) not in {6, 17} or not math.isfinite(timestamp):
                missing_session_id = hashlib.sha256(
                    repr((str(target.source_group), member, "UNENCODABLE", position, uid)).encode("utf-8")
                ).hexdigest()
                output[uid] = (
                    np.empty(0, dtype=np.float32), True, missing_session_id, timestamp, position
                )
                continue
            session_id = hashlib.sha256(repr((str(target.source_group), member, session)).encode("utf-8")).hexdigest()
            pending_rows.append((uid, session_id, timestamp, position))
            pending_flows.append(sessions[session].flow(d0))
            if len(pending_rows) >= batch_size:
                flush()
        flush()
    finally:
        if owner is not None:
            owner.close()
    if decoded != maximum + 1:
        raise RuntimeError("member prefix incomplete: %d/%d" % (decoded, maximum + 1))
    if set(output) != set(expected_uids):
        raise RuntimeError("member target output coverage drift")
    widths = {len(value[0]) for value in output.values() if not value[1]}
    if len(widths) != 1:
        raise RuntimeError("E3 representation width drift")
    expected_width = int(getattr(model.config, "hidden_size", 0))
    if widths and widths != {expected_width}:
        raise RuntimeError("E3 representation/config width mismatch")
    if expected_width <= 0:
        raise RuntimeError("E3 config lacks positive hidden width")
    width = expected_width
    ordered = [output[uid] for uid in expected_uids]
    representation = np.zeros((len(ordered), width), dtype=np.float32)
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
    validate_member_checkpoint(checkpoint, identity, plan_sha, expected_uids)
    return {"status": "COMPUTED", "checkpoint": str(checkpoint), "rows": len(part), "sha256": core.sha256_file(checkpoint)}


def combine(checkpoints: Sequence[Path], target_plan: pd.DataFrame, plan_sha: str, out: Path) -> Dict[str, object]:
    parts = []
    for path in checkpoints:
        with np.load(path, allow_pickle=False) as values:
            parts.append({name: np.asarray(values[name]) for name in (
                "uid", "representation", "missing", "session_id", "timestamp_epoch", "event_position"
            )})
    uids = np.concatenate([value["uid"].astype(str) for value in parts])
    representations = np.concatenate([value["representation"].astype(np.float32) for value in parts])
    missing = np.concatenate([value["missing"].astype(np.bool_) for value in parts])
    session_ids = np.concatenate([value["session_id"].astype(str) for value in parts])
    timestamps = np.concatenate([value["timestamp_epoch"].astype(np.float64) for value in parts])
    event_positions = np.concatenate([value["event_position"].astype(np.int64) for value in parts])
    if len(uids) != len(target_plan) or len(set(uids.tolist())) != len(uids):
        raise RuntimeError("combined embedding cardinality/UID drift")
    positions = pd.Series(np.arange(len(uids), dtype=np.int64), index=uids)
    take = positions.reindex(target_plan["uid"].astype(str)).to_numpy()
    if pd.isna(take).any():
        raise RuntimeError("combined embedding misses target")
    take = take.astype(np.int64)
    from issue27ckda_d1_probe_runner_v1 import atomic_npz

    atomic_npz(
        out,
        uid=target_plan["uid"].astype(str).to_numpy(dtype=np.str_),
        representation=representations[take],
        missing=missing[take],
        candidate_id=np.asarray(["E3"], dtype=np.str_),
        plan_sha256=np.asarray([plan_sha], dtype=np.str_),
        contract_sha256=np.asarray([core.CONTRACT_SHA256], dtype=np.str_),
    )
    metadata_path = out.with_suffix(out.suffix + ".metadata.csv.gz")
    metadata_rows = (
        {
            "uid": str(target_plan.iloc[index]["uid"]),
            "session_id": str(session_ids[take[index]]),
            "timestamp_epoch": float(timestamps[take[index]]),
            "event_position": int(event_positions[take[index]]),
        }
        for index in range(len(target_plan))
    )
    core.atomic_csv_stream(
        metadata_path, metadata_rows,
        ["uid", "session_id", "timestamp_epoch", "event_position"], compress=True,
    )
    audit = {
        "status": "CKDA_D1_E3_EMBEDDINGS_COMPLETE",
        "contract_sha256": core.CONTRACT_SHA256,
        "plan_sha256": plan_sha,
        "target_rows": len(target_plan),
        "embedded_rows": int((~missing).sum()),
        "missing_rows": int(missing.sum()),
        "duplicate_rows": 0,
        "member_checkpoints": len(checkpoints),
        "output_sha256": core.sha256_file(out),
        "metadata_sha256": core.sha256_file(metadata_path),
        "final_files_opened": 0,
    }
    core.atomic_json(out.with_suffix(out.suffix + ".audit.json"), audit)
    return audit


def run(args: argparse.Namespace) -> None:
    core.verify_contract(args.contract)
    plan = pd.read_csv(args.target_metadata, keep_default_na=False)
    plan_sha = str(args.plan_sha256)
    if len(plan_sha) != 64 or len(plan) not in {25_467, 262_050} or plan["uid"].duplicated().any():
        raise RuntimeError("target metadata/plan identity drift")
    if set(plan["dataset_kind"]) - {"gotham_zip", "direct_pcap"}:
        raise RuntimeError("target metadata dataset kind drift")
    ckbu = import_file("ckda_d1_ckbu_embed", args.ckbu_decoder)
    d0 = import_file("ckda_d1_d0_e3", args.d0_pilot)
    model, tokenizer, collator = build_e3_runtime(d0, args.netfound_source, args.netfound_checkpoint, args.device)
    checkpoint_root = Path(args.checkpoint_dir)
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    checkpoint_paths = []
    audits = []
    groups = list(plan.groupby(["dataset_kind", "container_path", "raw_source_path"], sort=True))
    for index, (_key, part) in enumerate(groups, start=1):
        identity = member_identity(part)
        checkpoint = checkpoint_root / (identity[:24] + ".npz")
        audit = process_member(
            part.reset_index(drop=True), plan_sha, ckbu, d0, model, tokenizer, collator,
            args.tshark, args.device, args.batch_size, checkpoint,
        )
        checkpoint_paths.append(checkpoint)
        audits.append(audit)
        print("CKDA_D1_E3_MEMBER_COMPLETE index=%d/%d rows=%d status=%s" % (index, len(groups), len(part), audit["status"]), flush=True)
    audit = combine(checkpoint_paths, plan, plan_sha, args.out)
    audit["member_manifest_sha256"] = core.sha256_json(sorted((value["checkpoint"], value["sha256"]) for value in audits))
    core.atomic_json(Path(args.out).with_suffix(Path(args.out).suffix + ".audit.json"), audit)
    print(json.dumps(audit, indent=2, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    root = Path(__file__).resolve().parents[2]
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--contract", type=Path, required=True)
    result.add_argument("--target-metadata", type=Path, required=True)
    result.add_argument("--plan-sha256", required=True)
    result.add_argument("--netfound-source", type=Path, required=True)
    result.add_argument("--netfound-checkpoint", type=Path, required=True)
    result.add_argument("--ckbu-decoder", type=Path, default=root / "repo/ood/issue27ckbu_unified_tshark_causal_frontend_v1.py")
    result.add_argument("--d0-pilot", type=Path, default=root / "repo/ood/issue27ckda_d0_resource_pilot_v1.py")
    result.add_argument("--tshark", default="tshark")
    result.add_argument("--device", default="cpu")
    result.add_argument("--batch-size", type=int, default=16)
    result.add_argument("--checkpoint-dir", type=Path, required=True)
    result.add_argument("--out", type=Path, required=True)
    return result


if __name__ == "__main__":
    run(parser().parse_args())
