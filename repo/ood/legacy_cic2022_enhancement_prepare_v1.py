"""Bounded PREPARE for the frozen legacy P2 enhancement experiment.

Importing this module opens no real cache, capture or checkpoint. ``prepare``
is the separately authorized execution entry point. It never scores a head,
normalizes features, trains, or calls an old all-array experiment driver.
"""
from __future__ import annotations

import copy
import csv
import gzip
import hashlib
import inspect
import json
import math
import os
import subprocess
import sys
import tarfile
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RECIPE_REL = "runs/mainline_docs/legacy_cic2022_p2_enhancement_small_recipe_v1_20260915.json"
RECIPE_SHA = "e90fe1f434d3f5b6aaf69bdf0b4b0a74a55fb83cd0dfac55214a74f56006b0c8"
DESIGN_REL = "runs/mainline_docs/legacy_cic2022_p2_enhancement_small_design_v1_20260915.md"
DESIGN_SHA = "d245b5394a5e67ddc2405f7ae9a50d7cc08cdfdf64973c2485217aed78bc0259"
DESIGN_RUN = "runs/legacy_cic2022_p2_enhancement_design_v1_20260915"
PROBE_RUN = "runs/legacy_cic2022_two_camera_semantic_probe_v1_20260915"
ID_EXTENSION_REL = "runs/legacy_id_temporal_qualification_v1_20260916/id_test_extension_v2.json"
ID_EXTENSION_SHA = "51aa383f858207edbf6e0b52359ca53f22548a6fa186b939eda8ea631875687e"
E3_KEYS = {"flow_duration", "burst_tokens", "directions", "bytes", "iats", "counts", "protocol"}
STATE_NAMES = ("normalizer_mean", "normalizer_scale", "p2__0.weight", "p2__0.bias", "p2__3.weight", "p2__3.bias")


class Stop(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def atomic_json(path, obj):
    path = Path(path)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def scoped_path(root, relative):
    root = Path(root).resolve()
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "PATH_OUTSIDE_ROOT")
    return path


def verify_file(path, expected, expected_bytes=None):
    path = Path(path)
    require(path.is_file(), "MISSING_PINNED_FILE:" + path.name)
    require(expected_bytes is None or path.stat().st_size == expected_bytes, "PINNED_SIZE:" + path.name)
    require(sha256(path) == expected, "PINNED_SHA:" + path.name)
    return path


def load_recipe(recipe):
    """Only the exact frozen recipe is executable; a dict is not a bypass."""
    source = ROOT / RECIPE_REL if isinstance(recipe, dict) else Path(recipe)
    verify_file(source, RECIPE_SHA)
    frozen = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(recipe, dict):
        require(recipe == frozen, "RECIPE_DICT_DRIFT")
    verify_file(ROOT / DESIGN_REL, DESIGN_SHA)
    return frozen


def read_jsonl(path):
    with Path(path).open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def validate_plans(recipe, old, train, check, captures, candidates):
    """Metadata-only identity, role, sampling and rational-weight audit."""
    all_uids = [row["uid"] for rows in (old, train, check) for row in rows]
    require(len(set(all_uids)) == len(all_uids), "CROSS_PLAN_UID_COLLISION")
    for rows in (old, train, check):
        require([r["uid"] for r in rows] == sorted(r["uid"] for r in rows), "PLAN_UID_ORDER")
    require(len(old) == recipe["old_replay"]["rows"], "OLD_REPLAY_COUNT")
    require(Counter(r["label"] for r in old) == {0: recipe["old_replay"]["benign"], 1: recipe["old_replay"]["attack"]}, "OLD_REPLAY_LABEL_COUNTS")
    digest = hashlib.sha256("".join(r["uid"] + "\n" for r in old).encode("utf-8")).hexdigest()
    require(digest == recipe["old_replay"]["sorted_uid_lines_sha256"], "OLD_REPLAY_UID_SHA")
    for row in old:
        require(row["owner"] == "A" and row["planned_role"] == "OLD_REPLAY", "OLD_REPLAY_ROLE")
        require(row["class_balanced_weight_numerator"] == 1 and row["class_balanced_weight_denominator"] == 2 * recipe["old_replay"]["benign" if row["label"] == 0 else "attack"], "OLD_WEIGHT")
    by_file = {c["file_id"]: c for c in captures}
    require(len(by_file) == len(captures), "CAPTURE_DUPLICATE_ID")
    train_ids, check_ids = set(recipe["new_data"]["train_file_ids"]), set(recipe["new_data"]["check_file_ids"])
    excluded = set(recipe["new_data"]["unassigned_nmap_ids"])
    require(not train_ids & check_ids and not (train_ids | check_ids) & excluded, "CAPTURE_ROLE_OVERLAP")
    require(set(by_file) == train_ids | check_ids | excluded, "CAPTURE_SCOPE")
    selected_captures = [c for c in captures if c["file_id"] in train_ids | check_ids]
    require(len({c["member_sha256"] for c in selected_captures}) == len(selected_captures), "CAPTURE_BYTE_IDENTITY_OVERLAP")
    require(len({(c["archive_path"], c["member_path"]) for c in captures}) == len(captures), "CAPTURE_MEMBER_DUPLICATE")
    groups = defaultdict(list)
    candidate_uids = set()
    for row in candidates:
        require(row["candidate_uid"] not in candidate_uids, "ANNOTATION_UID_DUPLICATE")
        candidate_uids.add(row["candidate_uid"])
        require(row["file_id"] in train_ids | check_ids, "ANNOTATION_SCOPE")
        spec = by_file[row["file_id"]]
        require(row["member_sha256"] == spec["member_sha256"] and row["member_path"] == spec["member_path"], "ANNOTATION_MEMBER")
        require(row["candidate_label"] in (0, 1), "ANNOTATION_LABEL")
        groups[(row["file_id"], row["stream"])].append(row)
    streams = Counter(fid for fid, _ in groups)
    expected = {}
    for (fid, stream), rows in groups.items():
        rows.sort(key=lambda r: r["frame_number_1based"])
        require(len({r["frame_number_1based"] for r in rows}) == len(rows), "ANNOTATION_FRAME_DUPLICATE")
        indices = sorted({0, (len(rows) - 1) // 2, len(rows) - 1})
        for ordinal in indices:
            row = rows[ordinal]
            expected[row["candidate_uid"]] = (row, ordinal, len(rows), len(indices))
    require(set(expected) == {r["uid"] for r in train + check}, "REPRESENTATIVE_TARGET_IDENTITY")
    for role, rows, ids, expected_n in (("TRAIN", train, train_ids, recipe["new_data"]["train_rows"]), ("CHECK", check, check_ids, recipe["new_data"]["check_rows"])):
        require(len(rows) == expected_n and {r["file_id"] for r in rows} == ids, "NEW_ROLE_COUNT:" + role)
        counts = recipe["new_data"][role.lower() + "_labels"]
        require(Counter(r["label"] for r in rows) == {0: counts["benign"], 1: counts["attack"]}, "NEW_LABEL_COUNTS")
        cells = defaultdict(Fraction)
        for target in rows:
            spec = by_file[target["file_id"]]
            require(target["planned_role"] == role == spec["planned_role"], "NEW_TARGET_ROLE")
            require("nmap" not in spec["member_path"].lower(), "NMAP_FORBIDDEN")
            original, ordinal, n, k = expected[target["uid"]]
            for key in ("file_id", "member_path", "member_sha256", "frame_number_1based", "timestamp", "stream", "evidence_basis"):
                require(target[key] == original[key], "ANNOTATION_TARGET_JOIN:" + key)
            require(target["label"] == original["candidate_label"], "ANNOTATION_TARGET_LABEL")
            require(target["candidate_ordinal_0based"] == ordinal and target["candidates_in_stream"] == n and target["selected_in_stream"] == k, "TARGET_SAMPLING")
            require(target["streams_in_capture"] == streams[target["file_id"]], "STREAM_DENOMINATOR")
            fcount = len({r["file_id"] for r in rows if r["device"] == target["device"] and r["label"] == target["label"]})
            require(target["captures_in_device_label_cell"] == fcount, "CAPTURE_DENOMINATOR")
            den = fcount * streams[target["file_id"]] * k
            for prefix, multiplier in (("conditional", 1), ("balanced_bce", 4), ("evaluation_label", 2)):
                require(target[prefix + "_weight_numerator"] == 1 and target[prefix + "_weight_denominator"] == multiplier * den, "NEW_WEIGHT:" + prefix)
            cells[(target["device"], target["label"])] += Fraction(1, den)
        require(set(cells) == {(d, y) for d in ("amcrest", "simcam") for y in (0, 1)} and all(v == 1 for v in cells.values()), "NEW_CELL_MASS")
    return selected_captures


def load_frozen_metadata(recipe, root=ROOT):
    """This helper reads only source code and already-authorized metadata."""
    root = Path(root)
    for category in ("design_artifact_pins", "code_source_pins"):
        for rel, digest in recipe[category].items():
            verify_file(scoped_path(root, rel), digest)
    design = scoped_path(root, DESIGN_RUN)
    source_pins = json.loads((design / "metadata_source_pins.json").read_text(encoding="utf-8"))
    for pin in source_pins:
        verify_file(scoped_path(root, pin["path"]), pin["sha256"])
    old = read_jsonl(design / "old_replay_target_plan.jsonl")
    train = read_jsonl(design / "new_train_target_plan.jsonl")
    check = read_jsonl(design / "new_check_target_plan.jsonl")
    captures = json.loads((design / "capture_role_plan.json").read_text(encoding="utf-8"))
    probe = scoped_path(root, PROBE_RUN)
    with gzip.open(probe / "annotation_candidates.jsonl.gz", "rt", encoding="utf-8") as f:
        candidates = [json.loads(line) for line in f]
    selected = validate_plans(recipe, old, train, check, captures, candidates)
    with gzip.open(scoped_path(root, recipe["old_replay"]["source"]), "rt", encoding="utf-8-sig", newline="") as f:
        lawful = {r["uid"]: r for r in csv.DictReader(f) if r["owner"] == "A"}
    require(set(lawful) == {r["uid"] for r in old}, "LAWFUL_OLD_UIDS")
    for row in old:
        source = lawful[row["uid"]]
        for key in ("context_key", "historical_role", "member"):
            require(row[key] == source[key], "LAWFUL_OLD_METADATA")
        require(row["label"] == int(source["label"]), "LAWFUL_OLD_LABEL")
    review = json.loads((probe / "evidence_review.json").read_text(encoding="utf-8"))
    rule = json.loads((probe / "annotation_rule.json").read_text(encoding="utf-8"))
    require(rule["normal"]["candidate_label"] == 0 and rule["attack"]["candidate_label"] == 1, "ANNOTATION_RULE_LABELS")
    return dict(old=old, train=train, check=check, captures=selected, review=review,
                plan_paths={"old": design / "old_replay_target_plan.jsonl", "train": design / "new_train_target_plan.jsonl", "check": design / "new_check_target_plan.jsonl"})


def verify_vendor(recipe, root=ROOT, verify_checkpoint=True):
    manifest = json.loads(scoped_path(root, recipe["model"]["vendor_source_manifest"]).read_text(encoding="utf-8"))
    source = Path(recipe["model"]["source_root"]).resolve() / "src"
    require(Path(manifest["source_root"]).resolve() == source.resolve(), "VENDOR_ROOT")
    names = {p["relative_path"] for p in manifest["files"]}
    require(len(names) == len(manifest["files"]) == 17, "VENDOR_PIN_COUNT")
    actual = {p.relative_to(source).as_posix() for p in source.rglob("*.py")}
    require(actual == names, "VENDOR_SOURCE_FILE_SET")
    for pin in manifest["files"]:
        verify_file(scoped_path(source, pin["relative_path"]), pin["sha256"], pin["bytes"])
    if verify_checkpoint:
        checkpoint = Path(recipe["model"]["checkpoint_dir"])
        verify_file(checkpoint / "model.safetensors", recipe["model"]["checkpoint_sha256"])
        verify_file(checkpoint / "config.json", recipe["model"]["config_sha256"])
    return source, manifest


def runtime_dependencies():
    """Verify the existing D1 Windows runtime; do not install or mix bundles."""
    from importlib.metadata import version
    import torch

    require(sys.version_info[:3] == (3, 9, 13), "E3_PYTHON_VERSION")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    expected = {"numpy": "2.0.2", "torch": "2.8.0+cpu", "transformers": "4.57.3", "tokenizers": "0.22.2", "safetensors": "0.6.2", "huggingface-hub": "0.36.2"}
    actual = {name: version(name) for name in expected}
    actual["torch"] = str(torch.__version__)
    require(actual == expected, "EXISTING_LOCAL_DEPENDENCY_VERSION_DRIFT")
    return dict(python=sys.executable, versions=actual, network="offline")


def build_runtime(recipe):
    dependencies = runtime_dependencies()
    import torch
    import issue27ckda_d1_e3_embed_v1 as embed
    import issue27ckda_d0_resource_pilot_v1 as translator
    import legacy_cic2022_two_camera_semantic_probe_v1 as probe

    for module in (embed, translator, embed.core):
        actual = Path(inspect.getfile(module)).resolve()
        relative = actual.relative_to(ROOT).as_posix() if actual.is_relative_to(ROOT) else ""
        require(relative in recipe["code_source_pins"], "IMPORTED_LEGACY_MODULE_UNPINNED")
        verify_file(actual, recipe["code_source_pins"][relative])
    torch.set_num_threads(recipe["runtime"]["intraop_threads"])
    if torch.get_num_interop_threads() != recipe["runtime"]["interop_threads"]:
        torch.set_num_interop_threads(recipe["runtime"]["interop_threads"])
    torch.use_deterministic_algorithms(recipe["runtime"]["deterministic_algorithms"])
    torch.manual_seed(recipe["optimization"]["seed"])
    source, manifest = verify_vendor(recipe, verify_checkpoint=False)
    # The unchanged old builder hashes model.safetensors before loading it.
    require(recipe["model"]["checkpoint_sha256"] == embed.NETFOUND_CHECKPOINT_SHA256, "E3_BUILDER_CHECKPOINT_PIN")
    verify_file(Path(recipe["model"]["checkpoint_dir"]) / "config.json", recipe["model"]["config_sha256"])
    model, tokenizer, collator = embed.build_e3_runtime(translator, Path(recipe["model"]["source_root"]), Path(recipe["model"]["checkpoint_dir"]), "cpu")
    allowed = {(source / p["relative_path"]).resolve(): p["sha256"] for p in manifest["files"]}
    for obj in (type(model), type(model.config), type(tokenizer), type(collator)):
        actual = Path(inspect.getfile(obj)).resolve()
        require(actual in allowed, "IMPORTED_VENDOR_OUTSIDE_PINNED_ROOT")
        verify_file(actual, allowed[actual])
    for name, module in list(sys.modules.items()):
        if name.startswith("modules.netFound") and getattr(module, "__file__", None):
            actual = Path(module.__file__).resolve()
            require(actual in allowed, "IMPORTED_VENDOR_MODULE_DRIFT")
            verify_file(actual, allowed[actual])
    require(not model.training and tokenizer.pretraining and not tokenizer.raw_labels, "E3_RUNTIME_MODE")
    require(model.config.pretraining is False and model.config.compile is False, "E3_CONFIG_MODE")
    event_api, _prefix_api, fields = probe.legacy_runtime()
    return dict(embed=embed, translator=translator, event=event_api, probe=probe,
                fields=fields, model=model, tokenizer=tokenizer, collator=collator, dependency_identity=dependencies)


def extract_captures(captures, out, root=ROOT):
    """Read exact named tar members only; never extract by archive paths."""
    grouped = defaultdict(list)
    for spec in captures:
        require(spec["planned_role"] in {"TRAIN", "CHECK"}, "RAW_ROLE_FORBIDDEN")
        grouped[spec["archive_path"]].append(spec)
    paths = {}
    for relative, specs in sorted(grouped.items()):
        archive = scoped_path(root, relative)
        digests = {s["archive_sha256"] for s in specs}
        require(len(digests) == 1, "ARCHIVE_PIN_CONFLICT")
        verify_file(archive, next(iter(digests)))
        wanted = {s["member_path"]: s for s in specs}
        require(len(wanted) == len(specs), "DUPLICATE_MEMBER_REQUEST")
        found = set()
        with tarfile.open(archive, "r|gz") as tar:
            for member in tar:
                if member.name not in wanted:
                    tar.members.clear()
                    continue
                require(member.name not in found and member.isfile(), "TAR_DUPLICATE_OR_NONREGULAR")
                spec = wanted[member.name]
                require(member.size == spec["member_bytes"], "TAR_MEMBER_SIZE")
                directory = Path(out) / spec["planned_role"].lower() / "raw"
                directory.mkdir(parents=True, exist_ok=True)
                destination = directory / ("%02d.pcap" % spec["file_id"])
                h, total = hashlib.sha256(), 0
                with tar.extractfile(member) as source, destination.open("xb") as sink:
                    for block in iter(lambda: source.read(1024 * 1024), b""):
                        total += len(block)
                        require(total <= spec["member_bytes"], "TAR_MEMBER_OVERRUN")
                        h.update(block)
                        sink.write(block)
                require(total == spec["member_bytes"] and h.hexdigest() == spec["member_sha256"], "TAR_MEMBER_SHA")
                paths[spec["file_id"]] = destination
                found.add(member.name)
                tar.members.clear()
        require(found == set(wanted), "TAR_MISSING_MEMBER")
    return paths


def decode_rows(path, fields, tshark, stderr):
    command = [str(tshark), "-n", "-r", str(path), "-T", "fields", "-E", "header=y", "-E", "separator=/t", "-E", "quote=d", "-E", "occurrence=f"]
    for field in fields:
        command.extend(["-e", field])
    with Path(stderr).open("w", encoding="utf-8") as err:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err, text=True, encoding="utf-8", errors="strict")
        try:
            reader = csv.DictReader(process.stdout, delimiter="\t", quotechar='"')
            require(tuple(reader.fieldnames or ()) == tuple(fields), "TSHARK_SCHEMA")
            for raw in reader:
                require(None not in raw, "TSHARK_EXTRA_COLUMN")
                yield {k: "" if v in (None, "None") else v for k, v in raw.items()}
            require(process.wait(timeout=30) == 0, "TSHARK_EXIT")
        finally:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=30)
            process.stdout.close()


def headers_complete(row, event):
    keys = ["ip.src", "ip.dst", "ip.hdr_len", "ip.dsfield", "ip.len", "ip.flags", "ip.ttl"] if event.ip_version == 4 else ["ipv6.src", "ipv6.dst", "ipv6.tclass", "ipv6.plen", "ipv6.hlim"]
    keys += ["tcp.srcport", "tcp.dstport", "tcp.flags", "tcp.window_size_value", "tcp.seq_raw", "tcp.ack_raw", "tcp.urgent_pointer", "tcp.hdr_len"] if event.ip_proto == 6 else ["udp.srcport", "udp.dstport", "udp.length"]
    return all(row.get(k, "") != "" for k in keys)


def verify_target(target, spec, row, event, eligible, expected_mac, probe):
    require(eligible and headers_complete(row, event), "TARGET_UNENCODABLE_OR_INCOMPLETE")
    require(target["member_sha256"] == spec["member_sha256"] and target["member_path"] == spec["member_path"], "TARGET_MEMBER_JOIN")
    require(int(row["frame.number"]) == target["frame_number_1based"], "TARGET_FRAME_JOIN")
    require(float(event.timestamp) == target["timestamp"], "TARGET_TIMESTAMP_JOIN")
    if spec["planned_role"] == "ID_TEST":
        require(target["planned_role"] == "ID_TEST" and target["label"] == 0, "ID_TARGET_ROLE_LABEL")
        key = (int(event.ip_proto),) + tuple(sorted(((str(event.src), int(event.src_port)), (str(event.dst), int(event.dst_port)))))
        require(hashlib.sha256(repr(key).encode("utf-8")).hexdigest() == target["session_key_sha256"], "ID_CANONICAL_SESSION_JOIN")
        require(target["frame_number_1based"] - 1 == target["position_zero_based"], "ID_FRAME_POSITION_JOIN")
        require(target["frame_number_1based"] > target["source_cutoff_frame_1based"] and target["timestamp"] > target["source_cutoff_time"], "ID_SOURCE_LOCAL_TIME")
        require(target["session_first_frame"] > target["source_cutoff_frame_1based"], "ID_NEW_SESSION")
        return
    stream = "tcp:" + row["tcp.stream"] if row.get("tcp.stream") else ("udp:" + row["udp.stream"] if row.get("udp.stream") else "")
    require(stream == target["stream"], "TARGET_STREAM_JOIN")
    smac, dmac = row.get("eth.src", "").lower(), row.get("eth.dst", "").lower()
    if target["label"] == 0:
        require(spec["provenance_kind"] == "normal_interaction_candidate" and expected_mac in {smac, dmac}, "NORMAL_EVIDENCE")
    elif target["label"] == 1:
        require(spec["provenance_kind"] == "attack_experiment_candidate" and "/Hydra/" in spec["member_path"], "ATTACK_PROVENANCE")
        markers = probe.rtsp_markers(row)
        require(dmac == expected_mac and event.dst_port == 554 and markers["method"] == "DESCRIBE" and markers["authorization_line_count"] > 0, "ATTACK_CURRENT_PACKET_EVIDENCE")
    else:
        raise Stop("TARGET_LABEL")


def materialize_capture(rows, targets, spec, runtime, device_macs, batch_size=16):
    """Actual prefix -> tokenizer -> collator -> base-forward -> fixed pooling.

    ``rows`` is a decoder iterator; tests use the real decoder on synthetic
    PCAP and the real tokenizer/collator/forward adapter with a stub model.
    Metadata and application markers never enter the E3 flow dictionary.
    """
    by_frame = {t["frame_number_1based"]: t for t in targets}
    require(len(by_frame) == len(targets) and targets, "TARGET_DUPLICATE_FRAME_OR_EMPTY")
    require(all(t["planned_role"] == spec["planned_role"] for t in targets), "TARGET_CAPTURE_ROLE")
    sessions, poisoned, pending, pending_flows, result = {}, set(), [], [], {}
    audit = dict(packets=0, legacy_scope=0, targets=0, E3_forward_rows=0, target_snapshot_deep_copies=0)
    embed, translator, event_api = runtime["embed"], runtime["translator"], runtime["event"]

    def flush():
        if not pending:
            return
        values = embed.embed_flows(translator, runtime["model"], runtime["tokenizer"], runtime["collator"], pending_flows, "cpu", batch_size)
        require(values.dtype == np.float32 and values.shape == (len(pending), 768) and np.isfinite(values).all(), "E3_OUTPUT")
        for uid, value in zip(pending, values):
            result[uid] = value.copy()
        audit["E3_forward_rows"] += len(pending)
        pending.clear()
        pending_flows.clear()

    for n, raw in enumerate(rows, 1):
        require(int(raw["frame.number"]) == n, "NONCONTIGUOUS_CAPTURE_FRAME")
        audit["packets"] += 1
        event = event_api.event_from_tshark(raw)
        key = None
        if event.ip_version in {4, 6}:
            key = (int(event.ip_proto),) + tuple(sorted(((str(event.src), int(event.src_port)), (str(event.dst), int(event.dst_port)))))
            embed.append_or_mark_unencodable(sessions, poisoned, key, dict(raw), float(event.timestamp))
        eligible = key is not None and event.ip_proto in {6, 17} and math.isfinite(event.timestamp) and key not in poisoned
        audit["legacy_scope"] += int(eligible)
        target = by_frame.get(n)
        if target is None:
            continue
        expected_mac = None if spec["planned_role"] == "ID_TEST" else device_macs[target["device"]]
        verify_target(target, spec, raw, event, eligible, expected_mac, runtime["probe"])
        flow = sessions[key].flow(translator)
        require(set(flow) == E3_KEYS, "E3_FLOW_METADATA_LEAK")
        # A pending example owns every nested list. Later same-flow packets,
        # mutable translator buffers and tokenizer mutations cannot change it.
        snapshot = copy.deepcopy(flow)
        pending.append(target["uid"])
        pending_flows.append(snapshot)
        audit["target_snapshot_deep_copies"] += 1
        audit["targets"] += 1
        if len(pending) >= batch_size:
            flush()
    flush()
    require(set(result) == {r["uid"] for r in targets}, "CAPTURE_TARGET_COVERAGE")
    return result, audit


def select_old_features(path, fit_plan_path, plan_sha, targets, audit):
    import legacy_p2_supported_capability_ledger_v1 as reader

    plan = reader.read_plan(fit_plan_path)
    by_uid = {r["uid"]: r for r in plan}
    mapping, missing = reader.embedding_metadata(path, plan, plan_sha)
    require(len({r["uid"] for r in targets}) == len(targets), "OLD_TARGET_DUPLICATE")
    for row in targets:
        require(row["uid"] in by_uid, "OLD_UNKNOWN_UID")
        old = by_uid[row["uid"]]
        require(row["owner"] == "A" and row["planned_role"] == "OLD_REPLAY", "OLD_TARGET_ACCESS_ROLE")
        require(old["phase"] == "fit" and old["role"] == row["historical_role"] and old["label_metric_only"] == row["label"], "OLD_PLAN_JOIN")
        require(not missing[mapping[row["uid"]]], "OLD_SELECTED_MISSING")
    indices = sorted(mapping[r["uid"]] for r in targets)
    output = np.empty((len(targets), 768), dtype=np.float32)
    destination = {mapping[r["uid"]]: i for i, r in enumerate(targets)}
    for physical, values in reader.selective_batches(path, indices, len(plan), audit=audit):
        for source_i, value in zip(physical.tolist(), values):
            output[destination[source_i]] = value
    require(audit.get("numeric_representation_rows") == len(targets), "OLD_NUMERIC_ACCESS_COUNT")
    return output


def write_cache(out, relative, features, targets, plan_path):
    path = Path(out) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    require(features.dtype == np.float32 and features.shape == (len(targets), 768) and np.isfinite(features).all(), "CACHE_FEATURE_SCHEMA")
    require(len({r["uid"] for r in targets}) == len(targets), "CACHE_UID_DUPLICATE")
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("xb") as f:
        np.savez(f, uid=np.asarray([r["uid"] for r in targets], dtype=np.str_), x=features, y=np.asarray([r["label"] for r in targets], dtype=np.int64))
    os.replace(str(temporary), str(path))
    with np.load(path, allow_pickle=False) as restored:
        require(set(restored.files) == {"uid", "x", "y"}, "CACHE_READBACK_FIELDS")
        require(restored["uid"].tolist() == [r["uid"] for r in targets], "CACHE_READBACK_UID")
        require(np.array_equal(restored["x"], features) and restored["x"].dtype == np.float32, "CACHE_READBACK_X")
        require(restored["y"].tolist() == [r["label"] for r in targets], "CACHE_READBACK_Y")
    metadata = path.with_suffix(".targets.jsonl")
    metadata.write_bytes(Path(plan_path).read_bytes())
    require(read_jsonl(metadata) == targets, "COPIED_PLAN_DRIFT")
    return dict(path=path.relative_to(out).as_posix(), sha256=sha256(path), rows=len(targets),
                metadata_path=metadata.relative_to(out).as_posix(), metadata_sha256=sha256(metadata))


def validate_id_metadata(extension, forbidden_targets=(), root=ROOT):
    """Read sealed qualification metadata only; never open raw/feature inputs."""
    require(extension.get("schema") == "legacy-id-test-extension-v2" and extension.get("qualified") is True
            and extension.get("status") == "QUALIFIED_WITH_DECLARED_LIMITS", "ID_NOT_QUALIFIED")
    require(extension.get("planned_role") == "ID_TEST" and extension.get("label") == 0, "ID_EXTENSION_ROLE")
    require(not extension.get("model_features_materialized") and not extension.get("scored"), "ID_ALREADY_SCORED")
    plan_path = scoped_path(root, extension["target_plan_path"])
    verify_file(plan_path, extension["target_plan_sha256"])
    qualification = extension["qualification"]
    report_path = scoped_path(root, qualification["path"])
    verify_file(report_path, qualification["sha256"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    require(report["status"] == "PASS_WITH_DECLARED_LIMITS" and report["target_plan_sha256"] == extension["target_plan_sha256"], "ID_QUALIFICATION_REPORT")
    require(report["independence_boundary"] == qualification["independence_boundary"], "ID_BOUNDARY_DRIFT")
    identity = extension["metadata_identity"]
    verify_file(scoped_path(root, identity["qualification_manifest_path"]), identity["qualification_manifest_sha256"])
    targets = read_jsonl(plan_path)
    require(len(targets) == extension["rows"] == report["qualified_targets"] and targets, "ID_TARGET_COUNT")
    require(len({r["uid"] for r in targets}) == len(targets), "ID_UID_DUPLICATE")
    require(not {r["uid"] for r in targets} & {r["uid"] for r in forbidden_targets}, "ID_CROSS_ROLE_UID")
    require(not {r["member_sha256"] for r in targets} & {r.get("member_sha256") for r in forbidden_targets}, "ID_CROSS_ROLE_MEMBER")
    require(len({r["session_key_sha256"] for r in targets}) == extension["canonical_sessions"] == report["qualified_canonical_sessions"], "ID_SESSION_DENOMINATOR")
    identities = set()
    for row in targets:
        require(row["planned_role"] == "ID_TEST" and row["role"] == "ID_TEST" and row["label"] == 0, "ID_TARGET_ROLE_LABEL")
        require(row["device_family"] == extension["device_family"] and row["member_path"] == row["raw_member"], "ID_TARGET_MEMBER_METADATA")
        pin = extension["member_pins"].get(row["member_path"])
        require(pin is not None and row["member_sha256"] == pin["sha256"], "ID_MEMBER_PIN")
        require(row["independence_boundary"] == qualification["independence_boundary"], "ID_ROW_BOUNDARY")
        require(1 <= row["frame_number_1based"] <= pin["packets"] and row["position_zero_based"] == row["frame_number_1based"] - 1, "ID_FRAME_IDENTITY")
        identity = (row["member_sha256"], row["frame_number_1based"])
        require(identity not in identities, "ID_PACKET_DUPLICATE")
        identities.add(identity)
    return targets, plan_path, report


def load_id_extension(extension, forbidden_targets=()):
    source = ROOT / ID_EXTENSION_REL if isinstance(extension, dict) else Path(extension)
    verify_file(source, ID_EXTENSION_SHA)
    frozen = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(extension, dict):
        require(extension == frozen, "ID_EXTENSION_DICT_DRIFT")
    targets, plan, report = validate_id_metadata(frozen, forbidden_targets)
    return frozen, targets, plan, report


def verify_id_raw_targets(path, targets, expected_packets):
    """Verify the qualified packet byte hashes without interpreting features."""
    import dpkt

    by_frame = {r["frame_number_1based"]: r for r in targets}
    seen = set()
    with Path(path).open("rb") as f:
        magic = f.read(4)
        f.seek(0)
        packets = dpkt.pcapng.Reader(f) if magic == b"\x0a\x0d\x0d\x0a" else dpkt.pcap.Reader(f)
        n = 0
        for n, (timestamp, raw) in enumerate(packets, 1):
            target = by_frame.get(n)
            if target is not None:
                require(float(timestamp) == target["timestamp"] and hashlib.sha256(raw).hexdigest() == target["packet_sha256"], "ID_RAW_PACKET_JOIN")
                seen.add(n)
        require(n == expected_packets and seen == set(by_frame), "ID_RAW_PACKET_DENOMINATOR")


def materialize_id(extension, targets, runtime, out, tshark, batch_size, progress=None):
    values, audits = {}, []
    for member in sorted({r["member_path"] for r in targets}):
        pin = extension["member_pins"][member]
        path = verify_file(scoped_path(ROOT, pin["local_path"]), pin["sha256"], pin["bytes"])
        selected = [r for r in targets if r["member_path"] == member]
        verify_id_raw_targets(path, selected, pin["packets"])
        spec = dict(planned_role="ID_TEST", member_path=member, member_sha256=pin["sha256"])
        log_dir = Path(out) / "check/id_decode_logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        rows = decode_rows(path, runtime["fields"], tshark, log_dir / ("%02d.stderr.log" % (len(audits) + 1)))
        try:
            current, audit = materialize_capture(rows, selected, spec, runtime, {}, batch_size)
        finally:
            rows.close()
        require(audit["packets"] == pin["packets"], "ID_DECODE_PACKET_DENOMINATOR")
        require(not set(values) & set(current), "ID_OUTPUT_UID_COLLISION")
        values.update(current)
        audits.append(dict(member_path=member, **audit))
        if progress:
            progress("ID_E3_FEATURES", len(values), len(targets))
    require(set(values) == {r["uid"] for r in targets}, "ID_OUTPUT_COVERAGE")
    return np.stack([values[r["uid"]] for r in targets]), audits


def prepare(recipe, output_dir, progress=None, id_extension=None):
    """Execute the authorized PREPARE once; exceptions never trigger retries."""
    recipe = load_recipe(recipe)
    out = Path(output_dir).resolve()
    require(not out.exists() or not any(out.iterdir()), "PREPARE_OUTPUT_NOT_EMPTY")
    out.mkdir(parents=True, exist_ok=True)

    def emit(stage, done=0, total=0, **extra):
        message = dict(stage="PREPARE", substage=stage, status="PREPARE_COMPLETE" if stage == "COMPLETE" else ("PREPARE_FAILED" if stage == "FAILED" else "PREPARE_RUNNING"), done=done, total=total, **extra)
        atomic_json(out / "prepare_status.json", message)
        atomic_json(out / "status.json", message)
        (out / "status.md").write_text("PREPARE: %s (%s/%s)\n\nThis status covers feature preparation only; it is not a scientific result.\n" % (stage, done, total), encoding="utf-8")
        if progress:
            progress(message)

    try:
        emit("VERIFY_METADATA")
        metadata = load_frozen_metadata(recipe)
        id_info = load_id_extension(id_extension, metadata["old"] + metadata["train"] + metadata["check"]) if id_extension is not None else None
        import legacy_p2_supported_capability_ledger_v1 as reader

        pins = recipe["legacy_asset_pins"]["files"]
        def asset(name):
            matches = [(rel, value) for rel, value in pins.items() if Path(rel).name == name]
            require(len(matches) == 1, "LEGACY_ASSET_ALIAS:" + name)
            rel, digest = matches[0]
            return verify_file(scoped_path(ROOT, rel), digest), digest

        state_path, _ = asset("ckda_d1_probe_state.npz")
        fit_path, fit_sha = asset("ckda_d1_fit_select_plan.csv")
        embeddings, _ = asset("ckda_d1_fit_select_embeddings.npz")
        marker_path, _ = asset("ckda_d1_threshold_freeze_marker.json")
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
        require(marker["probe_state_sha256"] == sha256(state_path), "REFERENCE_STATE_MARKER")
        state = reader.load_p2_state(state_path)
        require(set(state) == set(STATE_NAMES) == set(recipe["model"]["state_array_allowlist"]), "STATE_ALLOWLIST")
        (out / "train").mkdir()
        reference = out / "train/reference_state.npz"
        with reference.open("xb") as f:
            np.savez(f, **state)
        audit = dict(optimizer_steps=0, head_forward_rows=0, old_numeric={}, state_arrays_read=list(STATE_NAMES), new_capture_audits=[], report_numeric_rows_read=0, G0_P1_arrays_read=0)
        emit("COPY_OLD_FEATURES", 0, len(metadata["old"]))
        old_x = select_old_features(embeddings, fit_path, fit_sha, metadata["old"], audit["old_numeric"])
        artifacts = {"reference_state": dict(path="train/reference_state.npz", sha256=sha256(reference), arrays=list(STATE_NAMES))}
        artifacts["old_cache"] = write_cache(out, "train/old_cache.npz", old_x, metadata["old"], metadata["plan_paths"]["old"])
        del old_x
        emit("EXTRACT_PINNED_CAPTURES", 0, len(metadata["captures"]))
        raw_paths = extract_captures(metadata["captures"], out)
        tshark = Path("C:/Program Files/Wireshark/tshark.exe")
        version = subprocess.run([str(tshark), "--version"], capture_output=True, text=True, encoding="utf-8", check=True).stdout.splitlines()[0]
        require("4.6.6" in version, "TSHARK_VERSION")
        runtime = build_runtime(recipe)
        audit["runtime_dependency_identity"] = runtime["dependency_identity"]
        all_new = metadata["train"] + metadata["check"]
        values = {}
        for index, spec in enumerate(metadata["captures"], 1):
            targets = [r for r in all_new if r["file_id"] == spec["file_id"]]
            stderr = raw_paths[spec["file_id"]].with_suffix(".stderr.log")
            rows = decode_rows(raw_paths[spec["file_id"]], runtime["fields"], tshark, stderr)
            try:
                current, capture_audit = materialize_capture(rows, targets, spec, runtime, metadata["review"]["identity"]["devices"], recipe["model"]["e3_batch_size"])
            finally:
                rows.close()
            expected = next(r for r in metadata["review"]["file_results"] if r["file_id"] == spec["file_id"])
            require(capture_audit["packets"] == expected["packets"] and capture_audit["legacy_scope"] == expected["legacy_prefix_eligible_packets"], "CAPTURE_ACCOUNTING_DRIFT")
            require(not set(values) & set(current), "CAPTURE_OUTPUT_UID_COLLISION")
            values.update(current)
            audit["new_capture_audits"].append(dict(file_id=spec["file_id"], role=spec["planned_role"], **capture_audit))
            emit("NEW_E3_FEATURES", len(values), recipe["model"]["new_e3_targets"], capture_done=index, capture_total=len(metadata["captures"]))
        require(len(values) == recipe["model"]["new_e3_targets"], "NEW_E3_TARGET_COUNT")
        for role in ("train", "check"):
            targets = metadata[role]
            x = np.stack([values[r["uid"]] for r in targets])
            artifacts["new_" + role + "_cache"] = write_cache(out, role + "/new_" + role + "_cache.npz", x, targets, metadata["plan_paths"][role])
        id_qualification = dict(qualified=False, status="NOT_SUPPLIED")
        if id_info is not None:
            extension, id_targets, id_plan, id_report = id_info
            emit("ID_E3_FEATURES", 0, len(id_targets))
            id_x, id_audits = materialize_id(extension, id_targets, runtime, out, tshark, recipe["model"]["e3_batch_size"], emit)
            artifacts["id_cache"] = write_cache(out, "check/id_cache.npz", id_x, id_targets, id_plan)
            audit["id_capture_audits"] = id_audits
            id_qualification = dict(qualified=True, status=extension["status"], extension_sha256=ID_EXTENSION_SHA,
                                    rows=len(id_targets), canonical_sessions=extension["canonical_sessions"],
                                    sessions=extension["canonical_sessions"], per_source=id_report["qualified_sources"],
                                    protocol_coverage="UDP only; not TLS/TCP business coverage",
                                    protocol_targets=id_report["qualified_protocol_targets"],
                                    independence_boundary=extension["qualification"]["independence_boundary"],
                                    qualification=extension["qualification"], numerical_failure_policy="STOP without removing any target")
        training = dict(schema="legacy-cic2022-prepared-training-v1", recipe_sha256=RECIPE_SHA,
                        artifacts={k: {**v, "path": Path(v["path"]).relative_to("train").as_posix(), **({"metadata_path": Path(v["metadata_path"]).relative_to("train").as_posix()} if "metadata_path" in v else {})} for k, v in artifacts.items() if k in {"old_cache", "new_train_cache", "reference_state"}},
                        feature_semantics="Raw E3 float32; no new normalization; use frozen reference state")
        atomic_json(out / "train/train_manifest.json", training)
        manifest = dict(schema="legacy-cic2022-prepared-v1", status="PREPARE_COMPLETE", recipe_sha256=RECIPE_SHA,
                        artifacts=artifacts, training_manifest="train/train_manifest.json",
                        training_manifest_sha256=sha256(out / "train/train_manifest.json"),
                        id_extension_status=id_qualification["status"], id_qualification=id_qualification, audit=audit)
        atomic_json(out / "prepare_manifest.json", manifest)
        completed = recipe["model"]["new_e3_targets"] + artifacts.get("id_cache", {}).get("rows", 0)
        emit("COMPLETE", completed, completed)
        return manifest
    except Exception as exc:
        atomic_json(out / "prepare_failure.json", dict(status="PREPARE_FAILED", error_type=type(exc).__name__, error=str(exc), scientific_verdict=None, retries=0))
        emit("FAILED", error=str(exc), error_type=type(exc).__name__)
        raise
