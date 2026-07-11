"""CKBD T0: PyG-TGN event adapter and causal-data contract audit.

This file deliberately reuses :class:`torch_geometric.nn.models.TGNMemory`.
It does not implement a custom temporal graph network and it does not fit an
attack classifier.  Its sole job is to prove that the eventual M1 adapter can
construct a deployment-feasible event stream correctly:

* source-local anonymous node allocation;
* canonical timestamp order with a stable recorded-index tie break;
* target embedding read before ``TGNMemory.update_state``;
* no raw truth-label column read;
* explicit TGN memory reset between source files;
* strict held-family absence from fit/select manifest rows.

The compact actual-source replay is a contract audit, not a performance smoke.
No report metrics, thresholds, model selection, or representation selection are
performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch
from torch_geometric import __version__ as PYG_VERSION
from torch_geometric.nn.models.tgn import IdentityMessage, LastAggregator, TGNMemory


OOD = Path(__file__).resolve().parent
if str(OOD) not in sys.path:
    sys.path.insert(0, str(OOD))

import issue27ckao_c1_strict_leave_device_family_canary_v1 as ckao  # noqa: E402
import issue27ckaw_canonical_interaction_episode_frontend_v1 as ckaw  # noqa: E402
import issue27cko_mechanism_frontend_v1 as cko  # noqa: E402


ISSUE = "issue27ckbd_tgn_event_contract_audit_v1_2026-07-11"
ROOT = cko.ROOT
OUT = ROOT / "runs" / ISSUE
DEFAULT_PLAN = ROOT / "runs" / "issue27ckat_canonical_time_c1_canary_v1_2026-07-10_fullsupport_cacheplan_v1" / "canonical_source_target_index.csv"
AUDIT_SOURCES = [
    "processed/iotsim-stream-consumer-1.csv",
    "processed/iotsim-hydraulic-system-1.csv",
    "processed/iotsim-combined-cycle-10.csv",
]
RAW_MSG_NAMES = [
    "log_packet_length", "is_tcp", "is_udp", "is_icmp", "destination_port_bucket",
    "tcp_syn", "tcp_ack", "tcp_rst", "tcp_fin",
]


def safe_text(value: Any) -> str:
    if pd.isna(value):
        return ""
    text = str(value)
    return "" if text.lower() == "nan" else text


def coalesce(*values: Any) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def port_bucket(port: int) -> float:
    if port <= 0:
        return 0.0
    if port <= 1024:
        return 0.25
    if port <= 49151:
        return 0.5
    return 0.75


def raw_message(frame: pd.DataFrame) -> tuple[np.ndarray, list[str], list[str]]:
    """Return portable raw messages; label/IP/file identifiers are excluded."""
    proto = frame.get("frame.protocols", pd.Series("", index=frame.index)).astype(str).str.lower().to_numpy()
    ip_proto = pd.to_numeric(frame.get("ip.proto", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    length = pd.to_numeric(frame.get("frame.len", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    tcp_dst = pd.to_numeric(frame.get("tcp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    udp_dst = pd.to_numeric(frame.get("udp.dstport", pd.Series(0, index=frame.index)), errors="coerce").fillna(0).to_numpy()
    flags = np.asarray([cko.parse_tcp_flags(value) for value in frame.get("tcp.flags", pd.Series(0, index=frame.index)).to_numpy()], dtype=np.int64)
    source = [coalesce(a, b, f"row{index}:src") for index, (a, b) in enumerate(zip(frame.get("ip.src", pd.Series("", index=frame.index)), frame.get("eth.src", pd.Series("", index=frame.index))))]
    target = [coalesce(a, b, f"row{index}:dst") for index, (a, b) in enumerate(zip(frame.get("ip.dst", pd.Series("", index=frame.index)), frame.get("eth.dst", pd.Series("", index=frame.index))))]
    out = np.zeros((len(frame), len(RAW_MSG_NAMES)), dtype=np.float32)
    for index in range(len(frame)):
        is_tcp = float(ip_proto[index] == 6 or "tcp" in str(proto[index]))
        is_udp = float(ip_proto[index] == 17 or "udp" in str(proto[index]))
        is_icmp = float(ip_proto[index] == 1 or "icmp" in str(proto[index]))
        dport = int(tcp_dst[index] if tcp_dst[index] > 0 else udp_dst[index])
        out[index] = np.asarray([
            math.log1p(max(0.0, float(length[index]))), is_tcp, is_udp, is_icmp, port_bucket(dport),
            float(bool(flags[index] & 0x02)), float(bool(flags[index] & 0x10)),
            float(bool(flags[index] & 0x04)), float(bool(flags[index] & 0x01)),
        ], dtype=np.float32)
    return out, source, target


class SourceLocalNodeMap:
    """Sequential per-source allocation; node identity is never a message feature."""

    def __init__(self, capacity: int):
        self.capacity = int(capacity)
        self.mapping: dict[str, int] = {}

    def node(self, value: str) -> int:
        value = str(value)
        if value not in self.mapping:
            if len(self.mapping) >= self.capacity:
                raise RuntimeError("source-local TGN node capacity exceeded")
            self.mapping[value] = len(self.mapping)
        return self.mapping[value]


def make_memory(capacity: int) -> TGNMemory:
    memory_dim, time_dim = 32, 16
    memory = TGNMemory(
        num_nodes=max(2, int(capacity)), raw_msg_dim=len(RAW_MSG_NAMES), memory_dim=memory_dim, time_dim=time_dim,
        message_module=IdentityMessage(len(RAW_MSG_NAMES), memory_dim, time_dim), aggregator_module=LastAggregator(),
    )
    memory.eval()
    return memory


def fingerprint(value: torch.Tensor) -> str:
    return hashlib.sha256(value.detach().cpu().numpy().astype(np.float32).tobytes()).hexdigest()[:20]


@dataclass
class ReplayResult:
    target_fingerprints: dict[int, str]
    targets_seen: int
    events_replayed: int
    nodes_allocated: int
    timestamp_violations: int


def replay(
    frame: pd.DataFrame,
    targets: set[int],
    memory: TGNMemory | None = None,
    node_map: SourceLocalNodeMap | None = None,
    reset_before: bool = True,
) -> ReplayResult:
    """Read each target before its event updates official PyG TGN memory."""
    seconds = ckaw.ckat._raw_time_seconds(frame.get("frame.time", pd.Series(np.nan, index=frame.index)))
    order, finite, violations = ckaw.ckat._canonical_order(seconds)
    message, source, target = raw_message(frame)
    # Dynamic allocation avoids using a future entity's appearance even as a
    # node-map side effect.  Capacity is only an upper bound, not an identity.
    node_map = node_map or SourceLocalNodeMap(capacity=2 * max(1, len(frame)))
    memory = memory or make_memory(node_map.capacity)
    if reset_before:
        memory.reset_state()
    base = float(np.nanmin(seconds[finite])) if bool(finite.any()) else 0.0
    fingerprints: dict[int, str] = {}
    events = 0
    for ridx in order.tolist():
        if not bool(finite[ridx]):
            continue
        src = node_map.node(source[ridx])
        dst = node_map.node(target[ridx])
        timestamp = int(round((float(seconds[ridx]) - base) * 1000.0))
        source_t = torch.tensor([src], dtype=torch.long)
        target_t = torch.tensor([dst], dtype=torch.long)
        time_t = torch.tensor([timestamp], dtype=torch.long)
        msg_t = torch.from_numpy(message[ridx : ridx + 1])
        if ridx in targets:
            representation, last_update = memory(torch.tensor([src, dst], dtype=torch.long))
            fingerprints[int(ridx)] = fingerprint(torch.cat([representation.flatten(), last_update.to(torch.float32)]))
        memory.update_state(source_t, target_t, time_t, msg_t)
        events += 1
    return ReplayResult(fingerprints, len(fingerprints), events, len(node_map.mapping), int(violations))


def synthetic_frame() -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for moment in range(12):
        rows.append({
            "frame.time": f"2025-01-01T00:00:{moment:02d}Z", "frame.len": 100 + moment,
            "frame.protocols": "eth:ip:tcp", "ip.src": "10.0.0.1", "ip.dst": "10.0.0.2",
            "eth.src": "aa:01", "eth.dst": "aa:02", "ip.proto": 6, "tcp.srcport": 50000,
            "tcp.dstport": 443, "udp.srcport": 0, "udp.dstport": 0, "tcp.flags": "0x00000012",
            "label": "Benign" if moment < 10 else "Attack",
        })
    return pd.DataFrame(rows)


def synthetic_audit() -> dict[str, bool]:
    target = {8}
    torch.manual_seed(27)
    baseline = replay(synthetic_frame(), target).target_fingerprints[8]
    labels = synthetic_frame()
    labels["label"] = "arbitrary_label_change"
    torch.manual_seed(27)
    label_mutation = replay(labels, target).target_fingerprints[8]
    future = synthetic_frame()
    future.loc[11, "ip.dst"] = "203.0.113.9"
    torch.manual_seed(27)
    future_mutation = replay(future, target).target_fingerprints[8]
    past = synthetic_frame()
    past.loc[6, "ip.dst"] = "10.0.0.77"
    torch.manual_seed(27)
    past_mutation = replay(past, target).target_fingerprints[8]
    # Each source must begin with zeroed memory.  A source B representation is
    # identical when replayed alone or after source A in the *same* official
    # TGN instance followed by an explicit reset.
    source_b = synthetic_frame()
    torch.manual_seed(31)
    alone = replay(source_b, target).target_fingerprints[8]
    torch.manual_seed(31)
    shared = make_memory(2 * len(source_b))
    _unused = replay(synthetic_frame(), set(), memory=shared, node_map=SourceLocalNodeMap(2 * len(source_b)), reset_before=True)
    shared.reset_state()
    after_reset = replay(source_b, target, memory=shared, node_map=SourceLocalNodeMap(2 * len(source_b)), reset_before=False).target_fingerprints[8]
    return {
        "label_mutation_invariant": baseline == label_mutation,
        "future_event_mutation_invariant": baseline == future_mutation,
        "past_event_changes_representation": baseline != past_mutation,
        "source_reset_invariant": alone == after_reset,
    }


def read_source_prefix(member: str, nrows: int) -> pd.DataFrame:
    with zipfile.ZipFile(cko.GOTHAM_ZIP) as archive:
        with archive.open(member) as handle:
            return pd.read_csv(handle, usecols=lambda name: name in ckaw.RAW_USECOLS, nrows=int(nrows), low_memory=False)


def actual_audit(plan: pd.DataFrame, max_recorded_index: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in AUDIT_SOURCES:
        part = plan[plan["source_group"].astype(str).eq(source)]
        targets = sorted({int(value) for value in part["recorded_index"].tolist() if int(value) <= int(max_recorded_index)})
        if not targets:
            rows.append({"source_group": source, "status": "NO_TARGET_UNDER_CAP"})
            continue
        frame = read_source_prefix(source, int(max(targets)) + 1)
        # First/middle/last selected target exercise event-before-update across
        # the source without turning this contract audit into a classifier run.
        chosen = {targets[0], targets[len(targets) // 2], targets[-1]}
        result = replay(frame, chosen)
        rows.append({
            "source_group": source,
            "status": "OK",
            "raw_rows": int(len(frame)),
            "target_records_requested": int(len(chosen)),
            "target_records_seen": int(result.targets_seen),
            "events_replayed": int(result.events_replayed),
            "source_local_nodes": int(result.nodes_allocated),
            "recorded_order_timestamp_violations": int(result.timestamp_violations),
            "raw_label_column_read": False,
            "source_memory_reset": True,
            "target_before_update": True,
        })
    return rows


def held_contract() -> dict[str, bool]:
    _, frames, _, _ = cko.load_role_inputs(False)
    ckao.add_family_columns(frames)
    checks: dict[str, bool] = {}
    for held in ("iotsim-stream-consumer", "iotsim-hydraulic-system"):
        for role, phase in (("support_train", "fit"), ("id_calib", "fit"), ("ood_val", "fit"), ("ood_stress", "fit"), ("id_calib", "select"), ("ood_val", "select"), ("ood_stress", "select")):
            idx = ckao.role_indices_filtered(frames, role, phase, cko.FULL_CAP, exclude=("device_family", held))
            selected = frames[role].iloc[idx]
            checks[f"{held}:{role}:{phase}:absent"] = bool(not selected["device_family"].astype(str).eq(held).any())
    return checks


def run(args: argparse.Namespace) -> None:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = pd.read_csv(args.plan_path, usecols=["source_group", "recorded_index"])
    source_rows = actual_audit(plan, args.max_recorded_index)
    synth = synthetic_audit()
    held = held_contract()
    ok_sources = all(row.get("status") == "OK" for row in source_rows)
    checks = {
        **synth,
        "held_family_exclusion": bool(all(held.values())),
        "actual_sources_replayed": bool(ok_sources),
        "raw_label_column_absent_from_projection": "label" not in ckaw.RAW_USECOLS,
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    spec = {
        "issue": ISSUE,
        "status": status,
        "pyg_version": PYG_VERSION,
        "torch_version": torch.__version__,
        "raw_message_names": RAW_MSG_NAMES,
        "node_identity_policy": "dynamic source-local anonymous allocation; node id never enters raw_msg",
        "memory_policy": "reset per raw source; target read before TGNMemory.update_state",
        "max_recorded_index": int(args.max_recorded_index),
        "checks": checks,
    }
    pd.DataFrame(source_rows).to_csv(out / "actual_source_replay_audit.csv", index=False)
    (out / "held_family_exclusion_audit.json").write_text(json.dumps(held, indent=2) + "\n", encoding="utf-8")
    (out / "run_spec.json").write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    (out / "codex_readout.md").write_text(
        f"# {ISSUE}\n\nStatus: **{status}**\n\n"
        "This is a data-contract audit only; it has no classifier, threshold, or performance claim.\n\n"
        "```json\n" + json.dumps(spec, indent=2) + "\n```\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": status, "out": str(out), "source_rows": len(source_rows), "pyg": PYG_VERSION}, indent=2))
    if status != "PASS":
        raise SystemExit("TGN data contract failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan-path", default=str(DEFAULT_PLAN))
    parser.add_argument("--out", default=str(OUT))
    parser.add_argument("--max-recorded-index", type=int, default=5000)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
