"""Bounded bridge from decoded rows to the unchanged legacy causal prefix.

This module has no decoder, model, raw-file opener, asset loader or retry loop.
The upstream caller owns source/recipe pinning and real-execution authorization.
Only synthetic callback factories are exercised by this implementation's tests.
"""

import copy
import hashlib
import json

import legacy_commissioning_attack_v1 as audit
import legacy_reference_sample_prepare_v1 as prep


SOURCE_KEYS = frozenset(("capture_id", "source_sha256", "source_read_receipt_sha256",
                         "owner", "device", "role", "activity", "provenance"))
E3_KEYS = frozenset(("flow_duration", "burst_tokens", "directions", "bytes", "iats", "counts", "protocol"))
CONSUMED_CONFIRMATION_DEVICES = frozenset(("borun camera", "netatmo camera", "ring basestation"))


def _device_name(value):
    return " ".join(value.casefold().split())


def _stream(row, protocol):
    name = "tcp.stream" if protocol == 6 else "udp.stream"
    value = str(row.get(name, "")).strip()
    if not value:
        return None
    audit._require(value.isdigit(), "INVALID_DECODED_STREAM_ID")
    return ("tcp:" if protocol == 6 else "udp:") + str(int(value))


def _validate_inputs(targets, source, known_owners):
    audit._exact_keys(source, SOURCE_KEYS, "TRACE_SOURCE")
    for key in ("capture_id", "owner", "device", "activity"):
        audit._text(source[key], "SOURCE_" + key.upper())
    for key in ("source_sha256", "source_read_receipt_sha256"):
        audit._sha(source[key], key.upper())
    audit._require(source["role"] in ("LEARN", "DEV"), "SOURCE_ROLE_FORBIDDEN")
    audit._require(source["provenance"] == "attack", "SOURCE_MUST_BE_DECLARED_ATTACK")
    audit._require(_device_name(source["device"]) not in CONSUMED_CONFIRMATION_DEVICES,
                   "CONSUMED_CONFIRMATION_SOURCE_FORBIDDEN")
    audit._require(type(known_owners) in (list, tuple) and bool(known_owners), "KNOWN_OWNERS_SCHEMA")
    for owner in known_owners:
        audit._text(owner, "KNOWN_OWNER")
        audit._require(owner == owner.lower(), "OWNER_MUST_BE_NORMALIZED")
    audit._require(len(set(known_owners)) == len(known_owners), "DUPLICATE_KNOWN_OWNER")
    audit._require(source["owner"] in known_owners, "SOURCE_OWNER_NOT_REGISTERED")
    audit._require(type(targets) in (list, tuple) and bool(targets), "NONEMPTY_SELECTED_TARGETS_REQUIRED")
    by_frame = {}
    seen_uids = set()
    for target in targets:
        audit._row(target)
        audit._require(_device_name(target["device"]) not in CONSUMED_CONFIRMATION_DEVICES,
                       "CONSUMED_CONFIRMATION_TARGET_FORBIDDEN")
        for key in ("capture_id", "source_sha256", "owner", "device", "role", "activity"):
            audit._require(target[key] == source[key], "TARGET_SOURCE_" + key.upper() + "_MISMATCH")
        audit._require(target["frame"] not in by_frame, "DUPLICATE_SELECTED_FRAME")
        audit._require(target["uid"] not in seen_uids, "DUPLICATE_SELECTED_UID")
        audit._require(target["uid"] == prep.digest([source["source_sha256"], target["frame"], target["owner"]]),
                       "SELECTED_UID_IDENTITY_MISMATCH")
        by_frame[target["frame"]] = copy.deepcopy(target)
        seen_uids.add(target["uid"])
    return by_frame


def _retained_provenance(contexts, namespace, target, source, known_owners, event_api):
    prefix = contexts.states[namespace]
    audit._require(set(prefix.bursts) == {True, False}, "FROZEN_PREFIX_DIRECTION_SCHEMA")
    packets = []
    for direction in (True, False):
        bursts = prefix.bursts[direction]
        audit._require(type(bursts) is list and len(bursts) <= audit.BURSTS_PER_DIRECTION,
                       "FROZEN_PREFIX_BURST_SCHEMA")
        for burst_id, burst in enumerate(bursts):
            audit._require(type(burst) is list and len(burst) <= audit.PACKETS_PER_BURST,
                           "FROZEN_PREFIX_PACKET_SCHEMA")
            for retained in burst:
                event = event_api.event_from_tshark(retained)
                key = prep.old.old_key(event)
                accepted, _ = prep.guard.context_decision(
                    retained, event, owner_mac=target["owner"], known_device_macs=known_owners,
                    capture_id=source["capture_id"], query_capture_id=source["capture_id"],
                    query_frame=target["frame"], query_timestamp=target["timestamp"], query_key=namespace[2])
                audit._require(accepted and key == namespace[2], "RETAINED_PACKET_NAMESPACE_OR_CAUSALITY_DRIFT")
                row_src = (retained.get("ip.src") or retained.get("ipv6.src") or "").strip()
                audit._require((row_src == prefix.first_src) is direction, "RETAINED_DIRECTION_DRIFT")
                packets.append(dict(
                    owner=target["owner"], capture_id=source["capture_id"],
                    source_sha256=source["source_sha256"], component_id=prep.digest([target["owner"], key]),
                    protocol=event.ip_proto, timestamp=event.timestamp, frame=int(retained["frame.number"]),
                    stream_id=_stream(retained, event.ip_proto), direction=int(direction), burst_id=burst_id))
    packets.sort(key=lambda p: p["frame"])
    return packets


def _flow_summary(flow, retained_packets, target):
    # Existing code boundary, not a new failure claim: BoundedNetfoundPrefix
    # (issue27ckda_d1_e3_embed_v1.py) stores12 bursts/direction; netfound_flow
    # (issue27ckda_d0_resource_pilot_v1.py) re-groups retained rows and keeps
    # first12 bursts total. Neither flow length nor prefix membership establishes
    # that a particular target survives this translation or the tokenizer.
    audit._require(type(flow) is dict and set(flow) == E3_KEYS, "FROZEN_FLOW_SCHEMA")
    audit._require(type(flow["protocol"]) is int and flow["protocol"] == target["protocol"], "FLOW_PROTOCOL_DRIFT")
    fields = ("burst_tokens", "directions", "bytes", "iats", "counts")
    audit._require(all(type(flow[k]) is list for k in fields), "FLOW_LIST_SCHEMA")
    lengths = {len(flow[k]) for k in fields}
    audit._require(len(lengths) == 1 and 0 < len(flow["counts"]) <= 12, "FLOW_BURST_COUNT_DRIFT")
    audit._require(all(type(n) is int and 0 < n <= 6 for n in flow["counts"]), "FLOW_PACKET_COUNT_DRIFT")
    audit._require(sum(flow["counts"]) <= len(retained_packets), "FLOW_HAS_MORE_PACKETS_THAN_PREFIX")
    audit._require(type(flow["flow_duration"]) is int and flow["flow_duration"] >= 0, "FLOW_DURATION_DRIFT")
    encoded = json.dumps(flow, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()
    return {
        "flow_sha256": hashlib.sha256(encoded).hexdigest(), "flow_duration": flow["flow_duration"],
        "protocol": flow["protocol"], "burst_count": len(flow["counts"]),
        "packet_counts": list(flow["counts"]), "translated_packets": sum(flow["counts"]),
        "retained_prefix_packets": len(retained_packets),
        "translation_may_further_truncate_prefix": True,
        "target_in_translated_flow_without_callback": "INCONCLUSIVE",
        "translation_frame_mapping_available": False,
        "static_boundary": "BoundedNetfoundPrefix:12/direction; netfound_flow:first12 total; unchanged",
    }


def audit_selected_source(decoded_rows_factory, targets, source, known_owners,
                          event_api, prefix_api, translator,
                          tokenizer_callback=None, label_callback=None):
    """One source pass through the largest preselected frame, then close.

    ``decoded_rows_factory(max_frame=<int>)`` must return a closeable iterator
    starting at source frame1. It must also pass this bound to any external
    decoder, and own source-byte verification plus execution authority. This
    function never requests frame max_frame+1, including for end-of-file tests.
    It cannot control prefetch inside an external decoder. The real factory must
    honor max_frame with the decoder's own packet limit, not merely stop yielding.

    Targets are exact attack-selector ROW_KEYS records for this source. Source
    is exact SOURCE_KEYS metadata, without a raw-file path. Its receipt SHA is
    declared upstream evidence, not independently verified here.

    The actual frozen ScopedPrefixes handles every row, including unselected
    past rows. Namespace remains owner/capture/canonical-five-tuple. A changed
    transport stream is recorded and NEVER resets the old prefix.

    tokenizer_callback(flow_snapshot, retained_provenance) may return the pure
    audit module's provenance schema. It receives neither correctness nor labels
    and must trace both translation and tokenizer truncation. Missing callback
    leaves target-survives-tokenizer INCONCLUSIVE. No encoder is passed or used.
    label_callback(decoded_target_row, target_event, source_metadata) may return
    the pure module's label-evidence schema; omission remains INCONCLUSIVE.
    Callbacks receive copies so they cannot mutate causal state or stored traces.

    Caller must discard all results on any exception. There is no partial-success
    return, automatic retry, source reopening, or prefix rule modification.
    """
    source = copy.deepcopy(source)
    known_owners = copy.deepcopy(known_owners)
    by_frame = _validate_inputs(targets, source, known_owners)
    audit._require(callable(decoded_rows_factory), "DECODER_FACTORY_REQUIRED")
    for callback in (tokenizer_callback, label_callback):
        audit._require(callback is None or callable(callback), "INVALID_AUDIT_CALLBACK")
    max_frame = max(by_frame)
    contexts = prep.ScopedPrefixes(source["capture_id"], known_owners, prefix_api, retain_full_rows=True)
    iterator = decoded_rows_factory(max_frame=max_frame)
    close = getattr(iterator, "close", None)
    audit._require(callable(close), "CLOSEABLE_SOURCE_ITERATOR_REQUIRED")
    results = []
    completed = set()
    try:
        audit._require(iter(iterator) is iterator, "SOURCE_MUST_BE_SINGLE_ITERATOR")
        for expected_frame in range(1, max_frame + 1):
            try:
                decoded = next(iterator)
            except StopIteration:
                raise audit.AuditError("INCOMPLETE_SOURCE_TARGET_COVERAGE") from None
            audit._require(type(decoded) is dict and decoded.get("frame.number") == str(expected_frame),
                           "NONCONTIGUOUS_SOURCE_FRAME")
            # Copy the decoder's potentially reused buffer before the old append.
            decoded = copy.deepcopy(decoded)
            event = event_api.event_from_tshark(decoded)
            owner, namespace, valid = contexts.append(decoded, event)
            target = by_frame.get(expected_frame)
            if target is None:
                continue
            literal = (target["owner"].lower(), source["capture_id"], prep.old.old_key(event))
            audit._require(valid and owner == target["owner"] and namespace == literal,
                           "SELECTED_TARGET_NAMESPACE_OR_VALIDITY_DRIFT")
            audit._require(event.timestamp == target["timestamp"] and event.ip_proto == target["protocol"],
                           "SELECTED_TARGET_TIME_OR_PROTOCOL_DRIFT")
            audit._require(prep.digest([owner, namespace[2]]) == target["component_id"],
                           "SELECTED_TARGET_COMPONENT_DRIFT")
            audit._require(prep.digest([source["source_sha256"], expected_frame, owner]) == target["uid"],
                           "SELECTED_TARGET_UID_DRIFT")
            retained = _retained_provenance(contexts, namespace, target, source, known_owners, event_api)
            # snapshot already copies; keep this bridge's ownership explicit.
            flow = copy.deepcopy(contexts.snapshot(namespace, translator))
            summary = _flow_summary(flow, retained, target)
            tokenizer = None if tokenizer_callback is None else tokenizer_callback(copy.deepcopy(flow), copy.deepcopy(retained))
            label = None if label_callback is None else label_callback(copy.deepcopy(decoded), copy.deepcopy(event), copy.deepcopy(source))
            query = dict(target, stream_id=_stream(decoded, event.ip_proto))
            trace = audit.trace_attack_sample(query, retained, tokenizer, label)
            trace["frozen_namespace_sha256"] = prep.digest(namespace)
            trace["flow_summary"] = summary
            results.append(trace)
            completed.add(target["uid"])
    finally:
        close()
    audit._require(completed == {target["uid"] for target in by_frame.values()}, "INCOMPLETE_SELECTED_UID_COVERAGE")
    return {
        "schema": "legacy-commissioning-source-trace-bridge-v1",
        "status": "SOURCE_AUDIT_COMPLETE_WITH_INCONCLUSIVE_FIELDS" if any(
            trace["status"] == "INCONCLUSIVE" for trace in results) else
            "SOURCE_AUDIT_OBSERVATIONS_COMPLETE_NOT_CAUSAL_ATTRIBUTION",
        "capture_id": source["capture_id"], "source_sha256": source["source_sha256"],
        "declared_source_read_receipt_sha256": source["source_read_receipt_sha256"],
        "source_bytes_verified_by_bridge": False, "source_iterator_factory_invocations": 1,
        "consumed_frames": max_frame, "largest_selected_frame": max_frame,
        "requested_frame_after_last_target": False, "source_iterator_closed": True,
        "upstream_decoder_prefetch_verified": False,
        "upstream_decoder_packet_limit_required": max_frame,
        "selected_uid_count": len(completed), "selected_uids": sorted(completed),
        "traces": results, "context_reasons": dict(sorted(contexts.reasons.items())),
        "transport_streams_change_prefix_namespace": False,
        "encoder_calls": 0, "retries": 0, "causal_attribution": "NOT_ESTABLISHED",
    }
