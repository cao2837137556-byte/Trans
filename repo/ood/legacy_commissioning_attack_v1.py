"""Metadata-only selection and pure provenance audit for commissioning policy v1.

No function opens files, decodes packets, loads a vocabulary, runs a model or
changes a frontend. Callers must supply independently pinned, authorized attack
metadata. This module validates declarations, not the truth of source bytes.
Actual source and tokenizer adapters remain a separate authorization boundary.
"""

import hashlib
import json
import math
from collections import defaultdict


AUDIT_SALT = "commissioning-attack-semantic-v1-20260924"
EXPECTED_DEV_MISSES = 11
PACKET_BUDGET = 144
BURSTS_PER_DIRECTION = 12
PACKETS_PER_BURST = 6
ROW_KEYS = frozenset((
    "uid", "role", "owner", "device", "capture_id", "source_sha256",
    "component_id", "protocol", "activity", "candidate_rank", "timestamp",
    "frame", "observed_transport_streams", "saved_q_correct",
))
IDENTITY_KEYS = frozenset((
    "owner", "capture_id", "source_sha256", "component_id", "protocol",
    "timestamp", "frame",
))
PACKET_KEYS = IDENTITY_KEYS | frozenset(("stream_id", "direction", "burst_id"))


class AuditError(ValueError):
    """A malformed or out-of-scope audit input; never silently repair it."""


def _require(condition, reason):
    if not condition:
        raise AuditError(reason)


def _text(value, name):
    _require(isinstance(value, str) and bool(value.strip()), "INVALID_" + name)
    _require("|" not in value and "\x00" not in value, "AMBIGUOUS_" + name)


def _integer(value, name, minimum=0):
    _require(type(value) is int and value >= minimum, "INVALID_" + name)


def _sha(value, name):
    _require(isinstance(value, str) and len(value) == 64 and
             all(x in "0123456789abcdef" for x in value), "INVALID_" + name)


def _time(value):
    _require(type(value) in (int, float) and math.isfinite(value), "INVALID_TIMESTAMP")


def _exact_keys(item, keys, name):
    _require(type(item) is dict and set(item) == set(keys), name + "_SCHEMA")


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def _digest(*parts):
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def rank_bucket(rank):
    """Frozen zero-based candidate-rank buckets; booleans are not ranks."""
    _integer(rank, "CANDIDATE_RANK")
    if rank == 0:
        return "0"
    if rank <= 3:
        return "1-3"
    if rank <= 15:
        return "4-15"
    return "16+"


def _identity(row):
    for field in ("owner", "capture_id", "component_id"):
        _text(row[field], field.upper())
    _sha(row["source_sha256"], "SOURCE_SHA256")
    _require(type(row["protocol"]) is int and row["protocol"] in (6, 17),
             "UNSUPPORTED_PROTOCOL")
    _integer(row["frame"], "FRAME", 1)
    _time(row["timestamp"])


def _row(row):
    # A strict allowlist prevents incidental labels, scores, token contents or
    # retention flags from becoming selection inputs through future changes.
    _exact_keys(row, ROW_KEYS, "ATTACK_ROW")
    _identity(row)
    for key in ("uid", "device", "activity"):
        _text(row[key], key.upper())
    _require(row["role"] in ("LEARN", "DEV"), "FORBIDDEN_ROLE")
    _require(type(row["saved_q_correct"]) is bool, "INVALID_SAVED_CORRECTNESS")
    rank_bucket(row["candidate_rank"])
    streams = row["observed_transport_streams"]
    if streams is not None:
        _integer(streams, "OBSERVED_TRANSPORT_STREAMS", 1)


def _endpoint(row):
    return (row["timestamp"], row["capture_id"], row["frame"], row["uid"])


def _stratum(row):
    streams = row["observed_transport_streams"]
    if streams is None:
        return None
    return (row["device"], row["activity"], row["protocol"],
            "single" if streams == 1 else "multiple", rank_bucket(row["candidate_rank"]))


def select_attack_audit(rows, expected_dev_miss_uids):
    """Select the frozen bounded audit from complete saved attack metadata.

    ``rows`` contains only the exact ROW_KEYS; saved_q_correct is the old saved
    decision correctness, never a newly inferred score. ``expected_dev_miss_uids``
    is the caller's pre-pinned list of all 11 original DEV Q misses, with no
    configurable smaller fixture setting. LEARN rows are validated but are not
    sampled by the DEV matching/structural rules. No label or token is accepted.

    Matching excludes the missed query's component. The two matched endpoints
    may share a component with each other: the frozen rule samples queries here,
    whereas structural controls explicitly sample two distinct components.
    """
    _require(type(rows) in (list, tuple), "ROWS_MUST_BE_MATERIALIZED")
    _require(type(expected_dev_miss_uids) in (list, tuple), "MISS_ROSTER_SCHEMA")
    for uid in expected_dev_miss_uids:
        _text(uid, "MISS_UID")
    _require(len(expected_dev_miss_uids) == EXPECTED_DEV_MISSES and
             len(set(expected_dev_miss_uids)) == EXPECTED_DEV_MISSES,
             "EXACTLY_11_PINNED_DEV_MISSES_REQUIRED")

    by_uid = {}
    endpoints = {}
    source_pins = {}
    component_identity = {}
    owner_identity = {}
    device_identity = {}
    session_endpoints = defaultdict(list)
    for original in rows:
        _row(original)
        row = dict(original)
        uid = row["uid"]
        _require(uid not in by_uid, "DUPLICATE_UID")
        endpoint = (row["owner"], row["capture_id"], row["frame"])
        _require(endpoint not in endpoints, "DUPLICATE_ENDPOINT")
        endpoints[endpoint] = uid
        capture = row["capture_id"]
        _require(capture not in source_pins or source_pins[capture] == row["source_sha256"],
                 "CONFLICTING_CAPTURE_SOURCE")
        source_pins[capture] = row["source_sha256"]
        component = row["component_id"]
        identity = (row["owner"], row["device"], row["role"], row["protocol"])
        _require(component not in component_identity or component_identity[component] == identity,
                 "CONFLICTING_COMPONENT_IDENTITY")
        component_identity[component] = identity
        owner = row["owner"]
        _require(owner not in owner_identity or
                 owner_identity[owner] == (row["device"], row["role"]),
                 "CONFLICTING_OWNER_IDENTITY")
        owner_identity[owner] = (row["device"], row["role"])
        device = row["device"]
        _require(device not in device_identity or device_identity[device] == owner,
                 "UNDECLARED_DEVICE_ALIAS")
        device_identity[device] = owner
        by_uid[uid] = row
        session_endpoints[(owner, capture, component)].append(row)

    # candidate_rank is the index of a labeled candidate in source frame order
    # within this causal session; conflicting metadata must not change strata.
    for session in session_endpoints.values():
        ordered = sorted(session, key=lambda r: r["frame"])
        for earlier, later in zip(ordered, ordered[1:]):
            _require(earlier["candidate_rank"] < later["candidate_rank"],
                     "CONFLICTING_CANDIDATE_RANK_ORDER")
            _require(earlier["timestamp"] <= later["timestamp"],
                     "CONFLICTING_SESSION_TIME_ORDER")

    misses = sorted(uid for uid, row in by_uid.items()
                    if row["role"] == "DEV" and not row["saved_q_correct"])
    _require(misses == sorted(expected_dev_miss_uids), "PINNED_DEV_MISS_ROSTER_MISMATCH")
    reasons = defaultdict(list)
    matched = []
    shortages = []
    dev_rows = [row for row in by_uid.values() if row["role"] == "DEV"]
    correct_index = defaultdict(list)
    structural = defaultdict(lambda: defaultdict(list))
    unknown_stream_uids = []
    for row in dev_rows:
        key = (row["capture_id"], row["protocol"], row["activity"], rank_bucket(row["candidate_rank"]))
        if row["saved_q_correct"]:
            correct_index[key].append(row)
        strata = _stratum(row)
        if strata is None:
            unknown_stream_uids.append(row["uid"])
        else:
            structural[strata][row["component_id"]].append(row)

    for uid in misses:
        miss = by_uid[uid]
        reasons[uid].append({"kind": "PRIMARY_DEV_Q_MISS"})
        key = (miss["capture_id"], miss["protocol"], miss["activity"], rank_bucket(miss["candidate_rank"]))
        candidates = [r for r in correct_index[key] if r["component_id"] != miss["component_id"]]
        candidates.sort(key=lambda r: (_digest(AUDIT_SALT, uid, r["uid"]), r["uid"]))
        chosen = candidates[:2]
        matched.append({"miss_uid": uid, "correct_uids": [r["uid"] for r in chosen],
                        "eligible_correct_queries": len(candidates)})
        for row in chosen:
            reasons[row["uid"]].append({"kind": "MATCHED_Q_CORRECT", "miss_uid": uid})
        if len(chosen) < 2:
            shortages.append({"kind": "MATCHED_Q_CORRECT", "miss_uid": uid,
                              "required_maximum": 2, "available": len(chosen),
                              "conditions_relaxed": False})

    strata_report = []
    for strata, components in sorted(structural.items()):
        ordered = sorted(components, key=lambda cid: (_digest(AUDIT_SALT, cid), cid))
        chosen_uids = []
        for cid in ordered[:2]:
            endpoint = min(components[cid], key=_endpoint)
            uid = endpoint["uid"]
            chosen_uids.append(uid)
            reasons[uid].append({"kind": "STRUCTURAL_CONTROL", "stratum": list(strata)})
        strata_report.append({"stratum": list(strata), "eligible_components": len(components),
                              "chosen_uids": chosen_uids})
        if len(ordered) < 2:
            shortages.append({"kind": "STRUCTURAL_CONTROL", "stratum": list(strata),
                              "required_maximum": 2, "available": len(ordered),
                              "conditions_relaxed": False})
    if unknown_stream_uids:
        shortages.append({"kind": "INCONCLUSIVE_TRANSPORT_STREAM_METADATA",
                          "uids": sorted(unknown_stream_uids),
                          "conditions_relaxed": False})
    selected = [{"metadata": dict(by_uid[uid]), "reasons": reasons[uid]}
                for uid in sorted(reasons)]
    return {
        "schema": "legacy-commissioning-attack-selection-v1",
        "status": "METADATA_SELECTION_ONLY_NO_SOURCE_READ",
        "audit_salt": AUDIT_SALT,
        "input_metadata_sha256": hashlib.sha256(
            _json([by_uid[uid] for uid in sorted(by_uid)]).encode("utf-8")).hexdigest(),
        "expected_dev_miss_uids": misses,
        "selected": selected, "matched_correct": matched,
        "structural_strata": strata_report, "shortages": shortages,
        "source_sha256_by_capture": dict(sorted(source_pins.items())),
        "input_rows": len(rows), "selected_rows": len(selected),
        "validated_learn_rows_not_selected": sum(r["role"] == "LEARN" for r in rows),
        "real_source_reads": 0, "model_forwards": 0,
        "source_bytes_verified": False,
        "causal_attribution": "NOT_ESTABLISHED",
    }


def _stream(value):
    if value is not None:
        _text(value, "STREAM_ID")


def trace_attack_sample(query, retained_packets, tokenizer_provenance=None,
                        label_evidence=None):
    """Audit caller-observed provenance, with missing semantics INCONCLUSIVE.

    query: exact selector row keys plus ``stream_id`` (string or None).
    retained_packets: None (not observed), or ordered exact PACKET_KEYS rows;
    stream_id/direction/burst_id may be None. Burst IDs are local to direction.
    Each packet must belong to query's owner/capture/source/component/protocol
    and precede or equal the target in both timestamp and frame order.

    tokenizer_provenance: None, or exact ``input_frame_ids``,
    ``output_source_frame_ids``, ``complete``, ``tokenizer_sha256`` and
    ``config_sha256``. The output lists source frames for retained tokens, not
    token contents; repetitions are allowed. Complete means every retained token
    carrying packet content has provenance. Supplied hashes declare identity;
    this function does not read or independently validate tokenizer artifacts.

    label_evidence: None, or exact identity fields ``owner``, ``capture_id``,
    ``source_sha256``, ``target_frame``, ``rule_sha256`` plus
    ``rule_applies_to_target`` (bool/None). This records the supplied rule's
    target applicability; it does not infer attack truth from an entire session.
    """
    _exact_keys(query, ROW_KEYS | {"stream_id"}, "TRACE_QUERY")
    _row({k: query[k] for k in ROW_KEYS})
    _stream(query["stream_id"])
    _require(retained_packets is None or type(retained_packets) in (list, tuple),
             "PREFIX_SCHEMA")
    packets = None
    frame_ids = None
    prefix_target = None
    past_stream_ids = []
    mixing = None
    saturation = {"status": "INCONCLUSIVE", "packet_budget": PACKET_BUDGET,
                  "bursts_per_direction_budget": BURSTS_PER_DIRECTION,
                  "packets_per_burst_budget": PACKETS_PER_BURST,
                  "retained_packets": None, "counts_by_direction": None,
                  "budget_reached_does_not_prove_target_omission": True}
    if retained_packets is not None:
        packets = list(retained_packets)
        _require(len(packets) <= PACKET_BUDGET, "PREFIX_PACKET_BUDGET_EXCEEDED")
        previous_frame = 0
        previous_time = -math.inf
        burst_counts = defaultdict(lambda: defaultdict(int))
        burst_metadata_complete = True
        stream_metadata_complete = query["stream_id"] is not None
        for packet in packets:
            _exact_keys(packet, PACKET_KEYS, "PREFIX_PACKET")
            _identity(packet)
            for key in ("owner", "capture_id", "source_sha256", "component_id", "protocol"):
                _require(packet[key] == query[key], "PREFIX_" + key.upper() + "_MISMATCH")
            _require(packet["frame"] <= query["frame"] and
                     packet["timestamp"] <= query["timestamp"], "FUTURE_PREFIX_PACKET")
            _require(packet["frame"] > previous_frame and packet["timestamp"] >= previous_time,
                     "PREFIX_ORDER_OR_DUPLICATE_FRAME")
            previous_frame = packet["frame"]
            previous_time = packet["timestamp"]
            if packet["frame"] == query["frame"]:
                _require(packet["timestamp"] == query["timestamp"], "TARGET_TIMESTAMP_MISMATCH")
                if packet["stream_id"] is not None and query["stream_id"] is not None:
                    _require(packet["stream_id"] == query["stream_id"], "TARGET_STREAM_MISMATCH")
            _stream(packet["stream_id"])
            if packet["stream_id"] is None:
                stream_metadata_complete = False
            else:
                past_stream_ids.append(packet["stream_id"])
            direction, burst = packet["direction"], packet["burst_id"]
            _require((direction is None) == (burst is None), "PARTIAL_BURST_IDENTITY")
            if direction is None:
                burst_metadata_complete = False
            else:
                _require(type(direction) is int and direction in (0, 1), "INVALID_DIRECTION")
                _integer(burst, "BURST_ID")
                burst_counts[direction][burst] += 1
                _require(burst_counts[direction][burst] <= PACKETS_PER_BURST,
                         "PREFIX_PACKETS_PER_BURST_EXCEEDED")
                _require(len(burst_counts[direction]) <= BURSTS_PER_DIRECTION,
                         "PREFIX_BURSTS_PER_DIRECTION_EXCEEDED")
        frame_ids = [p["frame"] for p in packets]
        prefix_target = query["frame"] in frame_ids
        past_stream_ids = sorted(set(past_stream_ids))
        # An observed foreign stream suffices for a positive finding even if
        # another packet lacks stream metadata; absence needs complete evidence.
        if query["stream_id"] is not None and any(s != query["stream_id"] for s in past_stream_ids):
            mixing = True
        elif stream_metadata_complete:
            mixing = False
        budget_reached = len(packets) == PACKET_BUDGET or any(
            len(bursts) == BURSTS_PER_DIRECTION or
            any(count == PACKETS_PER_BURST for count in bursts.values())
            for bursts in burst_counts.values())
        saturation.update({
            "status": "BUDGET_REACHED" if budget_reached else
                      "BUDGET_NOT_REACHED" if burst_metadata_complete else "INCONCLUSIVE",
            "retained_packets": len(packets),
            "counts_by_direction": {
                str(direction): {"bursts": len(bursts),
                                 "packets_per_burst": {str(k): v for k, v in sorted(bursts.items())}}
                for direction, bursts in sorted(burst_counts.items())},
            "burst_metadata_complete": burst_metadata_complete,
        })

    tokenizer_target = None
    tokenizer_identity = None
    if tokenizer_provenance is not None:
        _exact_keys(tokenizer_provenance, {"input_frame_ids", "output_source_frame_ids",
                    "complete", "tokenizer_sha256", "config_sha256"}, "TOKENIZER_PROVENANCE")
        _require(frame_ids is not None, "TOKENIZER_REQUIRES_OBSERVED_PREFIX")
        _require(type(tokenizer_provenance["complete"]) is bool, "INVALID_TOKENIZER_COMPLETENESS")
        for key in ("tokenizer_sha256", "config_sha256"):
            _sha(tokenizer_provenance[key], key.upper())
        for key in ("input_frame_ids", "output_source_frame_ids"):
            _require(type(tokenizer_provenance[key]) is list, "TOKENIZER_FRAME_LIST_REQUIRED")
            for frame in tokenizer_provenance[key]:
                _integer(frame, "TOKENIZER_FRAME", 1)
        _require(tokenizer_provenance["input_frame_ids"] == frame_ids, "TOKENIZER_PREFIX_MISMATCH")
        _require(set(tokenizer_provenance["output_source_frame_ids"]).issubset(frame_ids),
                 "TOKEN_FRAME_NOT_IN_PREFIX")
        tokenizer_identity = {k: tokenizer_provenance[k] for k in ("tokenizer_sha256", "config_sha256")}
        if query["frame"] in tokenizer_provenance["output_source_frame_ids"]:
            tokenizer_target = True
        elif tokenizer_provenance["complete"]:
            tokenizer_target = False

    label_status = "INCONCLUSIVE"
    label_rule_sha256 = None
    if label_evidence is not None:
        _exact_keys(label_evidence, {"owner", "capture_id", "source_sha256", "target_frame",
                    "rule_sha256", "rule_applies_to_target"}, "LABEL_EVIDENCE")
        for key in ("owner", "capture_id", "source_sha256"):
            _require(label_evidence[key] == query[key], "LABEL_" + key.upper() + "_MISMATCH")
        _integer(label_evidence["target_frame"], "LABEL_TARGET_FRAME", 1)
        _require(label_evidence["target_frame"] == query["frame"], "LABEL_TARGET_FRAME_MISMATCH")
        _sha(label_evidence["rule_sha256"], "LABEL_RULE_SHA256")
        applicable = label_evidence["rule_applies_to_target"]
        _require(applicable is None or type(applicable) is bool, "INVALID_LABEL_APPLICABILITY")
        label_rule_sha256 = label_evidence["rule_sha256"]
        if applicable is not None:
            label_status = "DECLARED_RULE_APPLIES" if applicable else "DECLARED_RULE_DOES_NOT_APPLY"

    missing = []
    for name, value in (("target_in_prefix", prefix_target), ("target_survives_tokenizer", tokenizer_target),
                        ("cross_stream_prefix", mixing)):
        if value is None:
            missing.append(name)
    if saturation["status"] == "INCONCLUSIVE":
        missing.append("prefix_saturation")
    if label_status == "INCONCLUSIVE":
        missing.append("label_rule_applicability")
    return {
        "schema": "legacy-commissioning-attack-trace-v1", "uid": query["uid"],
        "status": "INCONCLUSIVE" if missing else "OBSERVATIONS_COMPLETE_NOT_CAUSAL_ATTRIBUTION",
        "identity": {k: query[k] for k in sorted(IDENTITY_KEYS)},
        "causal_time_and_frame_order": "VALIDATED_DECLARED_PROVENANCE" if packets is not None else "INCONCLUSIVE",
        "target_in_prefix": prefix_target, "target_survives_tokenizer": tokenizer_target,
        "retained_frame_ids": frame_ids, "past_stream_ids": past_stream_ids,
        "cross_stream_prefix": mixing, "prefix_saturation": saturation,
        "tokenizer_identity": tokenizer_identity, "label_rule_status": label_status,
        "label_rule_sha256": label_rule_sha256, "missing_evidence": missing,
        "causal_attribution": "NOT_ESTABLISHED",
        "interpretation": "Compare preselected missed and correct queries; observations alone do not establish an error cause.",
        "source_bytes_verified": False, "real_source_reads": 0, "model_forwards": 0,
    }
