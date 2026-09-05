#!/usr/bin/env python3
"""Full original-fit L1 input-identifiability audit for Frontend-F3."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
import sys
import traceback
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_REL = Path("runs/mainline_docs/frontend_f3_full_fit_l1_identifiability_frozen_20260905.md")
CONTRACT_SHA = "f8eb764839c6514b385851d5e693ecb14ae485c3fc4dfd51cc86aa309bc3be2f"
ATTACHMENT_REL = Path("runs/mainline_docs/frontend_f3_full_fit_construction_attachment_20260905.csv.gz")
ATTACHMENT_SHA = "3ae2d143651c0a507ebabfd4adedcf83a26d7b16f615450d37606d0288dcb113"
F1_CORPUS_REL = Path("runs/frontend_f1_d1_fit_corpus_v1_20260902_local/f1_d1_fit_contexts.jsonl.gz")
F1_CORPUS_SHA = "623d4e0bbec6ddfad4e98c08a9fc90df137e51e7692ff3453ac7f38c5e84097e"
KILL_REL = Path("runs/frontend_f1_d1_terminal_no_eligible_diagnostic_v1_20260904/f1_d1_terminal_flipped_attacks.csv")
KILL_SHA = "3adb43c349b59bc85a66024ef2533796081cca935a0f92ccd88cee008e7ca3be"
IDENTITY_REL = Path("runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_packet_identity_attachment.csv")
IDENTITY_SHA = "5deddd66248d036250da7b82d97437c4dfff343ed4ac25ac3fe157b8669a849c"
R0_REL = Path("runs/frontend_f0_step0b_implementation_preopen_20260829/frontend_f0_step0b_r0_identity_audit.json")
R0_SHA = "41b524918af9fd07d65460bc2e7c86367b1ba1bc6c1522bc0a9683adc2c68e11"
ENGINE_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_v1.py")
ENGINE_SHA = "00366fdef9d644c2ac60fab68047938e6bcc4425aab68e1f6c1ae552db40affa"
ZT_REL = Path("repo/ood/issue27frontend_f0_zero_training_semantics_real_v1.py")
ZT_SHA = "ca34ff39bfe7289fee1048d74e04de53dd4d4f096228fa837104cb65388b6f60"
F1_REL = Path("repo/ood/issue27frontend_f1_d1_train_v1.py")
F1_SHA = "6e2df7059b9bb0aba9be80adb11e7e918c3f1ddfef3ecc690b571b0f0af18634"
F3_REL = Path("repo/ood/issue27frontend_f3_conflict_field_sufficiency_v1.py")
F3_SHA = "187048a4b42c2aab6a8381144e3927ad74843a2a08595ba9c3463d130ebd00ff"
TARGETED_VERDICT_REL = Path("runs/frontend_f3_conflict_field_sufficiency_v1_20260905/f3_verdict.json")
TARGETED_VERDICT_SHA = "eab4d7dca26a37f488b94822220cab871d6f04fe6991311299eb5ae099268230"

EXECUTION_TOKEN = "I_AUTHORIZE_FRONTEND_F3_FULL_FIT_L1_AUDIT"
EXPECTED_PARENT_ROWS = 13_866
EXPECTED_PARENT_CONTEXTS = 9_307
EXPECTED_KILL_ROWS = 5
EXPECTED_TOTAL_ROWS = 13_871
EXPECTED_MEMBERS = 20
MAX_EVENTS = 256
VOCABULARY_CAP = 4094
NESTED_SALT = "frontend-f2-d1-internal-val-v1"
# The first attempt completed 18 exact member checkpoints before encountering
# a TShark empty-field spelling of ``None``.  The normalization repair changes
# no nonempty value, so those checkpoints retain their original semantic ID.
CHECKPOINT_SEMANTIC_IMPLEMENTATION_SHA = "9a0dce6afd0dd94a0cecbbb82e3ea85295b140930e575e92bbf9a3fa3f1c3fb0"


class F3BFailure(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def sha256_value(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def require_sha(path: Path, expected: str) -> Dict[str, object]:
    if not path.is_file():
        raise F3BFailure("missing pinned input: %s" % path)
    actual = sha256_file(path)
    if actual != expected:
        raise F3BFailure("SHA drift for %s: %s != %s" % (path, actual, expected))
    return {"path": str(path.resolve()), "bytes": path.stat().st_size, "sha256": actual}


def import_file(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:
        raise F3BFailure("cannot import %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def atomic_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(str(temporary), str(path))


def atomic_json(path: Path, value: object) -> None:
    atomic_text(path, json.dumps(value, indent=2, sort_keys=True) + "\n")


def atomic_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n", extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(str(temporary), str(path))


def atomic_gzip_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as binary:
        with gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=list(fields), lineterminator="\n", extrasaction="raise")
                writer.writeheader()
                writer.writerows(rows)
    os.replace(str(temporary), str(path))


def atomic_gzip_jsonl(path: Path, rows: Iterable[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(".%s.tmp" % path.name)
    with temporary.open("wb") as binary:
        with gzip.GzipFile(filename="", fileobj=binary, mode="wb", mtime=0) as compressed:
            with io.TextIOWrapper(compressed, encoding="utf-8", newline="\n") as text:
                for row in rows:
                    text.write(json.dumps(dict(row), sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
    os.replace(str(temporary), str(path))


def read_gzip_jsonl(path: Path) -> List[Dict[str, object]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def write_sha256s(output: Path) -> None:
    members = [item for item in sorted(output.iterdir(), key=lambda p: p.name) if item.is_file() and item.name != "SHA256SUMS"]
    atomic_text(output / "SHA256SUMS", "".join("%s  %s\n" % (sha256_file(item), item.name) for item in members))


@dataclass
class LiveContext:
    context_key: str
    count: int
    l0: List[str]
    l1: List[str]


def l1_signature(f3: Any, base: str, raw: Mapping[str, str], event: Any, delta_seconds: float) -> str:
    frame_length = f3.parse_int(raw.get("frame.len"))
    if frame_length is None:
        raise F3BFailure("frame length absent")
    tcp_flags = f3.parse_int(raw.get("tcp.flags")) if event.ip_protocol == 6 else None
    return base + "\x1f" + "\x1f".join([
        "FRAME_LEN=%d" % frame_length,
        "DELTA_LOG2_US=%s" % f3.delta_log2_us(delta_seconds),
        "TRANSPORT_LEN=%s" % f3.transport_length(raw, event.ip_protocol),
        "TCP_FLAGS=%s" % ("NONE" if tcp_flags is None else str(tcp_flags)),
    ])


def replay_member_once(
    engine: Any, zt: Any, f1: Any, f3: Any, decoded: Iterable[Tuple[Mapping[str, str], Any]],
    targets: Mapping[int, Mapping[str, object]], maximum: int,
) -> Tuple[List[Dict[str, object]], Dict[str, int]]:
    endpoint_tokens = engine.EndpointTokens()
    states: MutableMapping[Tuple[object, ...], Any] = {}
    contexts: MutableMapping[Tuple[object, ...], LiveContext] = {}
    next_epoch: Dict[Tuple[object, ...], int] = {}
    h4_current: Optional[Tuple[object, ...]] = None
    rows: List[Dict[str, object]] = []
    seen: Set[str] = set()
    decoded_rows = 0
    peak_states = 0
    for index, (raw, event) in enumerate(decoded):
        decoded_rows += 1
        if index > maximum:
            raise F3BFailure("replay crossed exact cutoff")
        route = engine.classify_route(event, endpoint_tokens)
        identity = (route.tier, route.base_key)
        if route.tier == "H4" and h4_current is not None and h4_current != identity:
            states.pop(h4_current, None)
            contexts.pop(h4_current, None)
        if route.tier == "H4":
            h4_current = identity
        state = states.get(identity)
        context = contexts.get(identity)
        missing_reason = engine._event_missing_reason(event)
        if not missing_reason:
            previous_state = state
            previous_last = None if previous_state is None else float(previous_state.last_surrogate)
            state, epoch_value = engine.SemanticPrototype._append_or_split(
                route, state, next_epoch.get(identity, 0), float(event.timestamp)
            )
            next_epoch[identity] = epoch_value
            states[identity] = state
            new_epoch = previous_state is None or state is not previous_state
            if new_epoch:
                context_id = engine._context_id(str(event.source_id), str(event.member_id), state)
                key = "%s\x1f%s\x1f%d" % (event.member_id, context_id, int(state.epoch))
                context = LiveContext(key, 0, [], [])
                contexts[identity] = context
                delta_seconds = 0.0
                regression = False
            else:
                if context is None or previous_last is None:
                    raise F3BFailure("live context absent")
                delta_seconds = max(previous_last, float(event.timestamp)) - previous_last
                regression = float(event.timestamp) < previous_last
            assert context is not None
            direction = engine._direction(route, state)
            base = f1.canonical_signature(raw, event, route, direction, delta_seconds, regression)
            l1 = l1_signature(f3, base, raw, event, delta_seconds)
            context.count += 1
            if context.count <= MAX_EVENTS:
                context.l0.append(base)
                context.l1.append(l1)
        target = targets.get(index)
        if target is not None:
            uid = str(target["uid"])
            if uid in seen or event.target_uid != uid:
                raise F3BFailure("target identity drift")
            if missing_reason or state is None or context is None:
                raise F3BFailure("target semantic context absent")
            if context.context_key != str(target["expected_context_key"]):
                raise F3BFailure("context key drift for %s" % uid)
            if context.count - 1 != int(target["expected_event_index"]):
                raise F3BFailure("event index drift for %s" % uid)
            if context.count > MAX_EVENTS:
                raise F3BFailure("target context exceeds 256 events")
            rows.append({
                "uid": uid, "scope": str(target["scope"]), "source_group": str(target["source_group"]),
                "context_key": context.context_key, "event_index": context.count - 1,
                "l0_signatures": list(context.l0), "l1_signatures": list(context.l1),
            })
            seen.add(uid)
        peak_states = max(peak_states, len(states))
        if index == maximum:
            break
    expected = {str(value["uid"]) for value in targets.values()}
    if decoded_rows != maximum + 1 or seen != expected:
        raise F3BFailure("member target conservation failure")
    return rows, {"packets": decoded_rows, "targets": len(seen), "peak_states": peak_states}


def source_split(contexts: Sequence[Mapping[str, object]]) -> Dict[str, str]:
    labels_by_source: Dict[str, Set[int]] = defaultdict(set)
    for context in contexts:
        source = str(context["source_group"])
        for target in context["targets"]:  # type: ignore[index]
            labels_by_source[source].add(int(target["label"]))
    strata: Dict[str, List[Tuple[bytes, str]]] = defaultdict(list)
    for source, labels in labels_by_source.items():
        stratum = "attack_present" if 1 in labels else "benign_only"
        payload = ("%s\0%s\0%s" % (NESTED_SALT, stratum, source)).encode("utf-8")
        strata[stratum].append((hashlib.sha256(payload).digest(), source))
    result: Dict[str, str] = {}
    for stratum in sorted(strata):
        ordered = sorted(strata[stratum], key=lambda item: (item[0], item[1]))
        held = {source for _, source in ordered[:max(1, int(math.ceil(len(ordered) / 5.0)))]}
        for _, source in ordered:
            result[source] = "internal_val" if source in held else "train"
    return result


def build_vocabulary(contexts: Sequence[Mapping[str, object]], split: Mapping[str, str]) -> Tuple[Dict[str, int], List[str]]:
    observed: Set[str] = set()
    for context in contexts:
        if split[str(context["source_group"])] == "train":
            observed.update(str(item) for item in context["signatures"])  # type: ignore[arg-type]
    ordered = sorted(observed, key=lambda value: (hashlib.sha256(value.encode("utf-8")).digest(), value.encode("utf-8")))
    return {signature: index + 2 for index, signature in enumerate(ordered)}, ordered


def collision_rows(rows: Sequence[Mapping[str, object]], field: str) -> Tuple[int, List[Dict[str, object]]]:
    groups: Dict[str, List[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        groups[str(row[field])].append(row)
    conflicts: List[Dict[str, object]] = []
    count = 0
    for digest, members in sorted(groups.items()):
        labels = {int(row["label"]) for row in members}
        if labels != {0, 1}:
            continue
        count += 1
        for row in members:
            conflicts.append({
                "identity_type": field, "prefix_sha256": digest, "bucket_rows": len(members),
                "uid": row["uid"], "nested_split": row["nested_split"], "source_group": row["source_group"],
                "owner": row["owner"], "label": row["label"], "teacher_kind": row["teacher_kind"],
                "attack_family": row["attack_family"],
            })
    return count, conflicts


def corpus_descriptors() -> Tuple[List[Dict[str, object]], Dict[str, Dict[str, object]]]:
    contexts = read_gzip_jsonl(ROOT / F1_CORPUS_REL)
    kill = pd.read_csv(ROOT / KILL_REL, keep_default_na=False)
    kill_uids = set(kill["uid"].astype(str))
    target_lookup: Dict[str, Dict[str, object]] = {}
    parent: List[Dict[str, object]] = []
    kill_found: Set[str] = set()
    for context in contexts:
        is_parent = str(context["split"]) == "train"
        if is_parent:
            parent.append(context)
        for target in context["targets"]:  # type: ignore[index]
            uid = str(target["uid"])
            if is_parent or uid in kill_uids:
                if uid in target_lookup:
                    raise F3BFailure("corpus UID duplication")
                target_lookup[uid] = {
                    **dict(target), "context_key": str(context["context_key"]),
                    "expected_l0_prefix_sha": sha256_value(context["signatures"][:int(target["event_index"]) + 1]),  # type: ignore[index]
                    "scope": "parent_train" if is_parent else "kill_only",
                }
                if uid in kill_uids:
                    kill_found.add(uid)
    if len(parent) != EXPECTED_PARENT_CONTEXTS or len(target_lookup) != EXPECTED_TOTAL_ROWS or kill_found != kill_uids:
        raise F3BFailure("corpus descriptor denominator drift")
    return parent, target_lookup


def execute(output: Path, tshark: Path) -> Dict[str, object]:
    output = output.resolve()
    try:
        output.relative_to((ROOT / "runs").resolve())
    except ValueError as exc:
        raise F3BFailure("output must be under runs") from exc
    output.mkdir(parents=True, exist_ok=True)
    prior_failure = output / "engineering_failure.json"
    archived_failure = output / "engineering_failure_attempt1.json"
    if prior_failure.is_file() and not archived_failure.exists():
        os.replace(str(prior_failure), str(archived_failure))
    checkpoint_dir = output / "checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    pins = {
        "contract": require_sha(ROOT / CONTRACT_REL, CONTRACT_SHA),
        "construction_attachment": require_sha(ROOT / ATTACHMENT_REL, ATTACHMENT_SHA),
        "f1_corpus": require_sha(ROOT / F1_CORPUS_REL, F1_CORPUS_SHA),
        "kill_only": require_sha(ROOT / KILL_REL, KILL_SHA),
        "packet_identity": require_sha(ROOT / IDENTITY_REL, IDENTITY_SHA),
        "r0": require_sha(ROOT / R0_REL, R0_SHA),
        "engine": require_sha(ROOT / ENGINE_REL, ENGINE_SHA),
        "zt_runner": require_sha(ROOT / ZT_REL, ZT_SHA),
        "f1_runner": require_sha(ROOT / F1_REL, F1_SHA),
        "f3_runner": require_sha(ROOT / F3_REL, F3_SHA),
        "targeted_verdict": require_sha(ROOT / TARGETED_VERDICT_REL, TARGETED_VERDICT_SHA),
    }
    engine = import_file("f3b_engine", ROOT / ENGINE_REL)
    zt = import_file("f3b_zt", ROOT / ZT_REL)
    f1 = import_file("f3b_f1", ROOT / F1_REL)
    f3 = import_file("f3b_f3", ROOT / F3_REL)
    current_tshark = f3.tshark_identity(tshark)
    r0 = json.loads((ROOT / R0_REL).read_text(encoding="utf-8"))
    if current_tshark != r0.get("tshark_identity"):
        raise F3BFailure("TShark identity drift")
    targeted = json.loads((ROOT / TARGETED_VERDICT_REL).read_text(encoding="utf-8"))
    if targeted.get("status") != "F3_CONFLICT_FIELDS_CANDIDATE_PASS" or targeted.get("selected_candidate_level") != "L1":
        raise F3BFailure("targeted F3 did not select L1")
    fields = list(zt.TSHARK_FIELDS) + [field for field in ("tcp.flags", "tcp.len", "udp.length") if field not in zt.TSHARK_FIELDS]

    construction = pd.read_csv(ROOT / ATTACHMENT_REL, keep_default_na=False)
    expected_columns = {
        "uid", "source_group", "dataset_kind", "container_path", "raw_source_path",
        "target_event_position_within_capture", "expected_context_key", "expected_event_index", "scope",
    }
    if set(construction.columns) != expected_columns or len(construction) != EXPECTED_TOTAL_ROWS:
        raise F3BFailure("construction attachment schema/denominator drift")
    if set(construction["scope"]) != {"parent_train", "kill_only"}:
        raise F3BFailure("construction scope drift")
    if int(construction["scope"].eq("parent_train").sum()) != EXPECTED_PARENT_ROWS or int(construction["scope"].eq("kill_only").sum()) != EXPECTED_KILL_ROWS:
        raise F3BFailure("construction scope counts drift")
    identities = pd.read_csv(ROOT / IDENTITY_REL, keep_default_na=False)
    identity_keys = ["dataset_kind", "container_path", "raw_source_path"]
    identity_map = {
        tuple(str(getattr(row, key)) for key in identity_keys): row._asdict()
        for row in identities.itertuples(index=False)
    }
    groups = list(construction.groupby(identity_keys, sort=True))
    if len(groups) != EXPECTED_MEMBERS:
        raise F3BFailure("construction member count drift")

    semantic_rows: List[Dict[str, object]] = []
    member_rows: List[Dict[str, object]] = []
    implementation_sha = sha256_file(Path(__file__))
    for member_index, (raw_key, part) in enumerate(groups, start=1):
        key = tuple(str(item) for item in raw_key)
        packet_identity = identity_map.get(key)
        if packet_identity is None:
            raise F3BFailure("member absent from identity attachment")
        if str(packet_identity.get("is_report", "")).lower() != "false" or str(packet_identity.get("is_final", "")).lower() != "false":
            raise F3BFailure("forbidden member role")
        f3.verify_packet_identity(packet_identity)
        member = key[2]
        targets: Dict[int, Dict[str, object]] = {}
        for row in part.itertuples(index=False):
            position = int(row.target_event_position_within_capture)
            if position in targets:
                raise F3BFailure("duplicate target ordinal in member")
            targets[position] = {
                "uid": str(row.uid), "source_group": str(row.source_group),
                "expected_context_key": str(row.expected_context_key),
                "expected_event_index": int(row.expected_event_index), "scope": str(row.scope),
            }
        source_values = {str(value["source_group"]) for value in targets.values()}
        if len(source_values) != 1:
            raise F3BFailure("member spans source groups")
        source = next(iter(source_values))
        maximum = max(targets)
        checkpoint_identity = sha256_value({
            "contract": CONTRACT_SHA, "attachment": ATTACHMENT_SHA,
            "implementation": CHECKPOINT_SEMANTIC_IMPLEMENTATION_SHA,
            "packet": packet_identity, "targets": sorted((position, value["uid"], value["expected_context_key"], value["expected_event_index"]) for position, value in targets.items()),
            "fields": fields,
        })
        checkpoint = checkpoint_dir / (checkpoint_identity[:24] + ".jsonl.gz")
        marker = checkpoint_dir / (checkpoint_identity[:24] + ".json")
        if checkpoint.is_file() and marker.is_file():
            mark = json.loads(marker.read_text(encoding="utf-8"))
            if mark.get("identity") != checkpoint_identity or mark.get("sha256") != sha256_file(checkpoint):
                raise F3BFailure("checkpoint identity drift")
            decoded_rows = read_gzip_jsonl(checkpoint)
            lifecycle = {"packets": 0, "targets": len(decoded_rows), "peak_states": 0}
            status = "REUSED_EXACT_MEMBER_CHECKPOINT"
        else:
            def decoded() -> Iterator[Tuple[Mapping[str, str], Any]]:
                for position, raw in enumerate(f3.iter_tshark_rows(tshark, packet_identity, maximum + 1, fields)):
                    target = targets.get(position)
                    uid = None if target is None else str(target["uid"])
                    event = zt.raw_to_event(engine, raw, source, member, position, uid)
                    yield raw, event
            decoded_rows, lifecycle = replay_member_once(engine, zt, f1, f3, decoded(), targets, maximum)
            atomic_gzip_jsonl(checkpoint, decoded_rows)
            atomic_json(marker, {"identity": checkpoint_identity, "sha256": sha256_file(checkpoint), "targets": len(decoded_rows)})
            status = "COMPUTED_CAUSAL_ONE_PASS"
        semantic_rows.extend(decoded_rows)
        member_rows.append({
            "member_index": member_index, "member_id": member, "targets": len(part),
            "maximum_target_position": maximum, "status": status,
            "decoded_packets": lifecycle["packets"], "peak_states": lifecycle["peak_states"],
            "checkpoint_identity": checkpoint_identity, "checkpoint_sha256": sha256_file(checkpoint),
        })
        print("F3B_MEMBER_COMPLETE index=%d/%d member=%s targets=%d status=%s" % (member_index, len(groups), member, len(part), status), flush=True)

    if len(semantic_rows) != EXPECTED_TOTAL_ROWS or len({str(row["uid"]) for row in semantic_rows}) != EXPECTED_TOTAL_ROWS:
        raise F3BFailure("semantic target conservation failure")

    # Labels and teacher outcomes become available only after semantic conservation.
    parent_descriptors, descriptors = corpus_descriptors()
    joined: List[Dict[str, object]] = []
    l0_mismatch = 0
    for semantic in semantic_rows:
        uid = str(semantic["uid"])
        descriptor = descriptors.get(uid)
        if descriptor is None:
            raise F3BFailure("descriptor absent after semantic construction")
        if semantic["scope"] != descriptor["scope"] or semantic["context_key"] != descriptor["context_key"] or int(semantic["event_index"]) != int(descriptor["event_index"]):
            raise F3BFailure("semantic/descriptor identity drift")
        observed_l0 = sha256_value(semantic["l0_signatures"])
        l0_mismatch += int(observed_l0 != descriptor["expected_l0_prefix_sha"])
        joined.append({
            **semantic,
            "owner": str(descriptor["owner"]), "label": int(descriptor["label"]),
            "teacher_kind": str(descriptor["teacher_kind"]),
            "device_family": str(descriptor["device_family"]),
            "attack_family": str(descriptor["attack_family"]),
            "expected_l0_prefix_sha": str(descriptor["expected_l0_prefix_sha"]),
            "observed_l0_prefix_sha": observed_l0,
        })

    parent_rows = [row for row in joined if row["scope"] == "parent_train"]
    kill_rows = [row for row in joined if row["scope"] == "kill_only"]
    context_groups: Dict[str, List[Dict[str, object]]] = defaultdict(list)
    for row in parent_rows:
        context_groups[str(row["context_key"])].append(row)
    enriched_contexts: List[Dict[str, object]] = []
    for key, members in sorted(context_groups.items()):
        longest = max(members, key=lambda row: int(row["event_index"]))
        if len(longest["l1_signatures"]) != int(longest["event_index"]) + 1:  # type: ignore[arg-type]
            raise F3BFailure("longest context prefix drift")
        enriched_contexts.append({
            "context_key": key, "source_group": str(longest["source_group"]),
            "signatures": list(longest["l1_signatures"]),
            "targets": [{
                "uid": row["uid"], "event_index": row["event_index"], "owner": row["owner"],
                "label": row["label"], "teacher_kind": row["teacher_kind"],
                "source_group": row["source_group"], "device_family": row["device_family"],
                "attack_family": row["attack_family"],
            } for row in sorted(members, key=lambda row: (int(row["event_index"]), str(row["uid"])))],
        })
    if len(enriched_contexts) != EXPECTED_PARENT_CONTEXTS:
        raise F3BFailure("enriched context denominator drift")

    split = source_split(enriched_contexts)
    vocabulary, ordered_vocabulary = build_vocabulary(enriched_contexts, split)
    target_audit: List[Dict[str, object]] = []
    for row in parent_rows:
        signatures = [str(item) for item in row["l1_signatures"]]  # type: ignore[arg-type]
        tokens = [int(vocabulary.get(signature, 1)) for signature in signatures]
        target_audit.append({
            "uid": row["uid"], "context_key": row["context_key"], "event_index": row["event_index"],
            "nested_split": split[str(row["source_group"])], "source_group": row["source_group"],
            "owner": row["owner"], "label": row["label"], "teacher_kind": row["teacher_kind"],
            "device_family": row["device_family"], "attack_family": row["attack_family"],
            "l1_prefix_sha": sha256_value(signatures), "token_prefix_sha": sha256_value(tokens),
            "prefix_events": len(tokens), "known_events": sum(token != 1 for token in tokens),
            "unk_events": sum(token == 1 for token in tokens),
        })
    canonical_conflicts, canonical_rows = collision_rows(target_audit, "l1_prefix_sha")
    token_conflicts, token_rows = collision_rows(target_audit, "token_prefix_sha")
    conflict_output = canonical_rows + token_rows

    eligibility: Dict[Tuple[str, str], Set[str]] = defaultdict(set)
    for row in target_audit:
        nested = str(row["nested_split"])
        category = ""
        if row["owner"] == "A" and row["teacher_kind"] == "attack_hard":
            category = "a_protected_attack"
        elif row["owner"] == "A" and row["teacher_kind"] == "benign_normal":
            category = "a_protected_benign"
        elif row["owner"] == "B" and int(row["label"]) == 0:
            category = "b_benign"
        elif row["owner"] == "B" and int(row["label"]) == 1:
            category = "b_attack"
        if category:
            eligibility[(nested, category)].add(str(row["context_key"]))
    required_categories = [(side, category) for side in ("train", "internal_val") for category in ("a_protected_attack", "a_protected_benign", "b_benign")]
    split_feasible = all(len(eligibility[key]) > 0 for key in required_categories) and len(eligibility[("train", "b_attack")]) > 0

    train_benign_prefixes = {
        str(row["token_prefix_sha"]) for row in target_audit
        if row["nested_split"] == "train" and int(row["label"]) == 0
    }
    kill_output: List[Dict[str, object]] = []
    for row in sorted(kill_rows, key=lambda item: str(item["uid"])):
        signatures = [str(item) for item in row["l1_signatures"]]  # type: ignore[arg-type]
        tokens = [int(vocabulary.get(signature, 1)) for signature in signatures]
        digest = sha256_value(tokens)
        kill_output.append({
            "uid": row["uid"], "source_group": row["source_group"], "attack_family": row["attack_family"],
            "prefix_events": len(tokens), "known_events": sum(token != 1 for token in tokens),
            "unk_events": sum(token == 1 for token in tokens), "token_prefix_sha": digest,
            "collides_with_nested_train_benign": str(digest in train_benign_prefixes).lower(),
        })

    unk_rows: List[Dict[str, object]] = []
    for source, members in sorted(defaultdict(list, {
        source: [row for row in target_audit if row["source_group"] == source]
        for source in sorted({str(row["source_group"]) for row in target_audit})
    }).items()):
        total = sum(int(row["prefix_events"]) for row in members)
        unknown = sum(int(row["unk_events"]) for row in members)
        unk_rows.append({
            "nested_split": split[source], "source_group": source, "targets": len(members),
            "prefix_events": total, "unk_events": unknown, "unk_rate": unknown / max(total, 1),
        })

    all_non_unk = all(int(row["known_events"]) > 0 for row in target_audit)
    kill_non_unk = all(int(row["known_events"]) > 0 for row in kill_output)
    kill_collision = any(str(row["collides_with_nested_train_benign"]) == "true" for row in kill_output)
    vocabulary_ok = len(ordered_vocabulary) <= VOCABULARY_CAP
    static_emission_ok = all(
        "SRC_PORT_" not in signature and "DST_PORT_" not in signature and "TTL_BUCKET=" not in signature
        for context in enriched_contexts for signature in context["signatures"]  # type: ignore[index]
    )
    gates = {
        "denominator_conservation": len(parent_rows) == EXPECTED_PARENT_ROWS and len(enriched_contexts) == EXPECTED_PARENT_CONTEXTS and len(kill_rows) == EXPECTED_KILL_ROWS,
        "l0_prefix_reproduction": l0_mismatch == 0,
        "canonical_mixed_label_zero": canonical_conflicts == 0,
        "token_mixed_label_zero": token_conflicts == 0,
        "vocabulary_capacity_and_non_unk": vocabulary_ok and all_non_unk,
        "nested_split_feasible": split_feasible,
        "kill_only_not_structurally_blocked": kill_non_unk and not kill_collision,
        "static_emission_scope": static_emission_ok,
    }
    status = "F3_FULL_FIT_L1_IDENTIFIABILITY_PASS" if all(gates.values()) else "F3_FULL_FIT_L1_NO_GO"

    atomic_gzip_jsonl(output / "f3b_l1_contexts.jsonl.gz", ({**context, "nested_split": split[str(context["source_group"])]} for context in enriched_contexts))
    atomic_gzip_csv(
        output / "f3b_target_prefix_audit.csv.gz",
        ["uid", "context_key", "event_index", "nested_split", "source_group", "owner", "label", "teacher_kind", "device_family", "attack_family", "l1_prefix_sha", "token_prefix_sha", "prefix_events", "known_events", "unk_events"],
        sorted(target_audit, key=lambda row: str(row["uid"])),
    )
    atomic_csv(
        output / "f3b_collision_rows.csv",
        ["identity_type", "prefix_sha256", "bucket_rows", "uid", "nested_split", "source_group", "owner", "label", "teacher_kind", "attack_family"],
        conflict_output,
    )
    atomic_csv(
        output / "f3b_nested_split_census.csv",
        ["nested_split", "category", "contexts"],
        [{"nested_split": key[0], "category": key[1], "contexts": len(value)} for key, value in sorted(eligibility.items())],
    )
    atomic_csv(output / "f3b_unk_by_source.csv", ["nested_split", "source_group", "targets", "prefix_events", "unk_events", "unk_rate"], unk_rows)
    atomic_csv(
        output / "f3b_kill_only_audit.csv",
        ["uid", "source_group", "attack_family", "prefix_events", "known_events", "unk_events", "token_prefix_sha", "collides_with_nested_train_benign"],
        kill_output,
    )
    atomic_csv(
        output / "f3b_member_replay_audit.csv",
        ["member_index", "member_id", "targets", "maximum_target_position", "status", "decoded_packets", "peak_states", "checkpoint_identity", "checkpoint_sha256"],
        member_rows,
    )
    atomic_gzip_jsonl(output / "f3b_vocabulary.jsonl.gz", ({"token": index + 2, "signature": value} for index, value in enumerate(ordered_vocabulary)))
    boundary = {
        "select_opened": 0, "viewed_opened": 0, "report_opened": 0, "final_opened": 0,
        "model_opened": 0, "score_opened": 0, "representation_opened": 0,
        "payload_bytes_opened": 0, "optimizer_steps": 0,
        "kill_only_rows_opened_after_l1_freeze": len(kill_rows),
    }
    identities = {
        "status": status, "pins": pins, "implementation_sha256": implementation_sha,
        "checkpoint_semantic_implementation_sha256": CHECKPOINT_SEMANTIC_IMPLEMENTATION_SHA,
        "tshark_identity": current_tshark, "fields": fields,
        "tshark_resource_profile": f3.TSHARK_RESOURCE_PROFILE,
        "vocabulary_sha256": sha256_value({"PAD": 0, "UNK": 1, "items": ordered_vocabulary}),
        "nested_split": {
            "salt": NESTED_SALT,
            "train_sources": sorted(source for source, value in split.items() if value == "train"),
            "internal_validation_sources": sorted(source for source, value in split.items() if value == "internal_val"),
        },
    }
    atomic_json(output / "f3b_identities.json", identities)
    verdict = {
        "status": status, "gates": gates, "parent_train_targets": len(parent_rows),
        "parent_train_contexts": len(enriched_contexts), "kill_only_targets": len(kill_rows),
        "l0_prefix_mismatches": l0_mismatch, "canonical_mixed_label_buckets": canonical_conflicts,
        "token_mixed_label_buckets": token_conflicts, "vocabulary_size": len(ordered_vocabulary),
        "vocabulary_cap": VOCABULARY_CAP, "all_target_prefixes_have_known_event": all_non_unk,
        "kill_only_collision_count": sum(str(row["collides_with_nested_train_benign"]) == "true" for row in kill_output),
        "boundary": boundary,
        "claim_boundary": "Input identifiability only; no ability inheritance, detector, or OOD claim.",
        "next_authorized_by_pass": "draft_one_shot_f2_training_addendum_only" if status.endswith("PASS") else "close_unified_encoder_frozen_p2_route",
    }
    atomic_json(output / "f3b_verdict.json", verdict)
    write_sha256s(output)
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--tshark", default=r"C:\Program Files\Wireshark\tshark.exe")
    parser.add_argument("--authorization-token", required=True)
    args = parser.parse_args()
    if args.authorization_token != EXECUTION_TOKEN:
        raise F3BFailure("execution not authorized")
    output = Path(args.output_dir)
    try:
        verdict = execute(output, Path(args.tshark))
    except BaseException as exc:
        output.mkdir(parents=True, exist_ok=True)
        for name in ("f3b_verdict.json", "SHA256SUMS"):
            path = output / name
            if path.is_file():
                path.unlink()
        atomic_json(output / "engineering_failure.json", {
            "status": "F3_FULL_FIT_L1_ENGINEERING_FAILURE", "scientific_verdict_emitted": False,
            "error_type": type(exc).__name__, "error": str(exc), "traceback": traceback.format_exc(),
        })
        raise
    print(json.dumps({"status": verdict["status"], "vocabulary_size": verdict["vocabulary_size"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
