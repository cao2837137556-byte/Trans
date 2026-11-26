"""Reconstruct only the frozen DAD Monday and Sunday TCP rosters."""

import csv
import hashlib
import importlib.util
import ipaddress
import json
import os
from collections import Counter
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
PREP = RUNS / "dad_frozen_v12_preparation_20261119"
DAD = RUNS / "p4_dad_frozen_v12_20261119"
HAND = RUNS / "p4_ccnr_relative_handshake_v1_20261121"
HISTORY = RUNS / "p4_ccnr_history60_v1_20261120"
FORMAL = RUNS / "p4_login_formal_v1_20261121"
sys.path[:0] = [str(FORMAL), str(HISTORY)]

from frozen_score import FROZEN, digest_order
from history_stream import History, decode, records

DAYS = {"mon": "capture_1910210000", "sun": "capture_1910270000"}
OWNER = "000c292c84ac"
OWNER_MAC = "00:0c:29:2c:84:ac"
BROKER = "10.6.56.1"


def read(path):
    return json.loads(path.read_bytes())


def pin(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "bytes": path.stat().st_size}


def load_reader():
    # DAD's original reader imports these modules by their unqualified names.
    # Resolve them inside the frozen vendor tree before its local path setup.
    import vendor
    import packet_reader
    import stream_core
    import continuous_input_v3
    import constrained_onboarding_reference_v2
    import issue27ckbu_unified_tshark_causal_frontend_v1

    for module in (vendor, packet_reader, stream_core):
        assert Path(module.__file__).resolve().parent == (FROZEN / "vendor").resolve()
    for module in (continuous_input_v3, constrained_onboarding_reference_v2,
                   issue27ckbu_unified_tshark_causal_frontend_v1):
        assert pin(Path(module.__file__)) == pin(FROZEN / "repo/ood" / Path(module.__file__).name)
    source = PREP / "audit.py"
    assert pin(source)["sha256"] == read(DAD / "DAD_CARD.json")["audit_source_sha256"]
    spec = importlib.util.spec_from_file_location("dad_normal_pinned_reader", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    search_path = sys.path.copy()
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = search_path
    assert (module.OWNER, module.OWNER_MAC, module.BROKER) == (OWNER, OWNER_MAC, BROKER)
    return module


def bind_sources():
    manifest = read(PREP / "INPUTS.json")
    card = read(DAD / "DAD_CARD.json")
    assert manifest["commit"] == card["source_commit"]
    cache = Path(os.environ["LOCALAPPDATA"]) / "Paper04/datasets/DAD" / manifest["commit"]
    truth = read(PREP / "AUDIT.json")
    parent = read(DAD / "PACKAGE_MANIFEST.json")["files"]
    for name in ("INPUTS.json", "AUDIT.json"):
        assert pin(PREP / name)["sha256"] == parent[name]
    files = {}
    for day, stem in DAYS.items():
        for name in (f"{stem}_{day}.pcap", stem + "_labels.csv"):
            actual = pin(cache / name)
            assert all(actual[k] == manifest["files"][name][k] for k in actual)
            files[name] = actual
    group, = [g for g in truth["selected_bank"]["groups"] if g["protocol"] == 6]
    ordered = group["selected_uids"]
    assert len(ordered) == len(set(ordered)) == 1264 and group["selected_components"] == 16
    all_groups = [u for g in truth["selected_bank"]["groups"] for u in g["selected_uids"]]
    assert digest_order(all_groups) == card["bank_uid_order"]
    return cache, files, truth, ordered


def walk_day(day, reader, cache, files, truth, collect, pilot):
    """Check every frame and invoke collect on selected causal snapshots."""
    from constrained_onboarding_reference_v2 import query_descriptor, reference_descriptor
    from continuous_input_v3 import digest

    stem = DAYS[day]
    capture = cache / f"{stem}_{day}.pcap"
    labels = cache / (stem + "_labels.csv")
    source = files[capture.name]["sha256"]
    tshark = Path("C:/Program Files/Wireshark/tshark.exe")
    context = reader.Contexts(day, [OWNER_MAC], reader.ethernet)
    device = reader.Engine()
    history = History()
    broker = int(ipaddress.IPv4Address(BROKER))
    cutoff = truth["commissioning"]["cutoff_ns"]
    count = truth["rosters"][day + "_normal"]["rows"]
    pilot_indices = set(range(8)) | {i * (count - 1) // 15 for i in range(16)}
    reference_uids, query_uids = [], []
    distribution = {"reference": Counter(), "query": Counter()}
    first_inbound = None
    cut_frame = 0
    last = 0
    timestamps = {}
    with labels.open(encoding="utf-8-sig", newline="") as labfile:
        paired = zip_longest(records(capture), reader.decode(capture, str(tshark)),
                             csv.DictReader(labfile, delimiter=";"))
        for item, fields, label in paired:
            assert item is not None and fields is not None and label is not None
            frame, timestamp, raw = item
            assert frame == last + 1 == int(fields["frame.number"]) == int(label["frame.number"])
            last = frame
            assert int(label["label"]) == 0 and fields["frame.cap_len"] == fields["frame.len"]
            assert timestamp == int(Decimal(fields["frame.time_epoch"]) * reader.NS)
            if label["ip.src"] or label["tcp.srcport"]:
                assert (label["ip.src"], label["tcp.srcport"]) == (
                    fields["ip.src"], fields["tcp.srcport"] or fields["udp.srcport"])
            if label["mqtt.msgid"]:
                assert fields["mqtt.msgid"] == label["mqtt.msgid"]
            context.append({k: v for k, v in fields.items() if not k.startswith("mqtt.")})
            history.advance(timestamp)
            packet = decode(raw, False)
            owner_frame = packet is not None and packet.macs[0] != packet.macs[1] and OWNER in packet.macs
            assert bool(context.query_allowed) == owner_frame
            event = None
            if owner_frame:
                inbound = packet.macs[1] == OWNER
                (src, sp), (dst, dp) = packet.endpoints
                assert (src == broker) == (packet.macs[0] == OWNER)
                assert (dst == broker) == inbound
                ports = "tcp" if packet.proto == 6 else "udp"
                assert (sp, dp) == (int(fields[ports + ".srcport"]), int(fields[ports + ".dstport"]))
                assert (str(ipaddress.IPv4Address(src)), str(ipaddress.IPv4Address(dst))) == (
                    fields["ip.src"], fields["ip.dst"])
                component = (packet.proto, *sorted(((fields["ip.src"], sp), (fields["ip.dst"], dp))))
                assert timestamp >= timestamps.get(component, -1)
                timestamps[component] = timestamp
                history.observe(OWNER, packet, inbound)
                if inbound:
                    if first_inbound is None:
                        first_inbound = timestamp
                    event = (OWNER, packet.proto, int(fields["ip.len"]), src, (packet.proto, src, sp, dst, dp))
            clock = device.advance(frame, timestamp, day, event)
            assert clock == history.clock
            during_bank = day == "mon" and clock <= cutoff
            if during_bank:
                cut_frame = frame
            if not owner_frame or packet.proto != 6 or not (during_bank or inbound):
                continue
            uid = digest([source, frame, OWNER_MAC])
            oriented = packet.endpoints if inbound else packet.endpoints[::-1]
            h = int(history.handshakes[history.group(OWNER, oriented)])
            if inbound:
                assert h == history.value(OWNER, packet, True)[1]
            reference = during_bank
            roster = reference_uids if reference else query_uids
            roster.append(uid)
            distribution["reference" if reference else "query"][h] += 1
            if pilot and not reference and len(roster) - 1 not in pilot_indices and not packet.syn:
                continue
            namespace = (OWNER_MAC, day, component)
            row = dict(uid=uid, frame=frame, timestamp=timestamp / reader.NS, capture_id=day,
                       partition="EXTERNAL_ARCHIVAL_EVALUATION", device=BROKER, owner=OWNER_MAC,
                       protocol=6, component_id=digest([OWNER_MAC, component]),
                       session_id=digest(namespace), canonical_key=component, source_sha256=source,
                       use="REFERENCE" if reference else "QUERY", label=0)
            if reference:
                row.update(reference_end=cutoff / reader.NS, bank_end_frame=truth["commissioning"]["last_reference_frame"])
            info = dict(day=day, frame=frame, clock=clock, h=h, guard=bool(packet.syn),
                        component=row["component_id"], port=oriented[1][1],
                        role=int(history.value(OWNER, packet, inbound)[2]), reference=reference)
            # The caller may reuse an already encoded UID after verifying its frame metadata.
            def snapshot():
                flow, numeric, provenance = context.states[namespace].snapshot()
                body = dict(flow=flow, state=numeric, provenance=provenance, source_sha256=source)
                descriptor = reference_descriptor if reference else query_descriptor
                q, features = descriptor(body, row)
                assert bool(features["syn_no_ack"]) == info["guard"]
                x = device.features(OWNER, 6)
                return (uid, frame, flow, provenance, q, x)
            collect(row, info, snapshot)
    assert last == truth["daily"][day]["frames"]
    original = truth["rosters"][day + "_normal"]
    assert (len(query_uids), digest_order(query_uids)) == (original["rows"], original["sha256"])
    if day == "mon":
        assert cutoff == first_inbound + 7200 * reader.NS
        assert cut_frame == truth["commissioning"]["last_reference_frame"] == 1304
        assert len(reference_uids) == 1264 and digest_order(reference_uids) == truth["rosters"]["reference_candidates_6"]["sha256"]
    return dict(frames=last, reference=len(reference_uids), queries=len(query_uids),
                query_order=digest_order(query_uids), handshake_counts=distribution)
