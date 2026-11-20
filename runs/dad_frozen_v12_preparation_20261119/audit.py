"""Audit the pinned DAD release without loading an encoder or a detection head."""
import argparse
import csv
import hashlib
import io
import ipaddress
import json
import math
import subprocess
import sys
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "device_context_training_v2_20261105"))
sys.path.insert(0, str(HERE.parents[1] / "repo" / "ood"))
from packet_reader import packets
from stream_core import Engine, NS
import issue27ckbu_unified_tshark_causal_frontend_v1 as ethernet
from continuous_input_v3 import Contexts, digest as canonical_digest
from constrained_onboarding_reference_v2 import VERSION, plan_banks
from onboarding_dense_reference_v1 import plan_dense_positions

BROKER = "10.6.56.1"
OWNER = "000c292c84ac"
OWNER_MAC = "00:0c:29:2c:84:ac"
DAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
COMMON = "ip.src ip.dst ip.hdr_len ip.dsfield ip.len ip.flags ip.ttl".split()
TCP = "tcp.srcport tcp.dstport tcp.flags tcp.window_size_value tcp.seq_raw tcp.ack_raw tcp.urgent_pointer tcp.hdr_len".split()
UDP = "udp.srcport udp.dstport udp.length".split()
FIELDS = ("frame.number frame.time_epoch frame.len frame.cap_len eth.src eth.dst ip.proto tcp.len tcp.stream "
          "mqtt.msgtype mqtt.msgid mqtt.clientid").split() + COMMON + TCP + UDP
RATE_NAMES = ("pps_1", "ip_Bps_1", "pps_10", "ip_Bps_10")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def decode(path, tshark):
    cmd = [tshark, "-n", "-r", str(path), "-T", "fields", "-E", "header=y", "-E", "occurrence=f"]
    for field in FIELDS:
        cmd.extend(["-e", field])
    result = subprocess.run(cmd, check=True, capture_output=True)
    return csv.DictReader(io.StringIO(result.stdout.decode("utf-8")), delimiter="\t")


@dataclass(frozen=True)
class Point:
    day: str
    frame: int
    ns: int
    comp: tuple
    flag: int
    publish: bool
    client: str
    rates: tuple

    @property
    def bypass(self):
        return (self.flag & 0x12) == 0x02


def summarize(points):
    series = {}
    for k, name in enumerate(RATE_NAMES):
        values = sorted(p.rates[k] for p in points)
        if not values:
            continue
        qs = [values[max(0, math.ceil(len(values) * q / 100) - 1)] for q in (5, 25, 50, 75, 95)]
        series[name] = dict(p05=qs[0], p25=qs[1], p50=qs[2], p75=qs[3], p95=qs[4],
                            min=values[0], max=values[-1], value_counts=sorted(Counter(values).items()))
    return dict(n=len(points), off=sum(not p.bypass for p in points),
                publish=sum(p.publish for p in points), components=len({p.comp for p in points}),
                rates=series)


def select_bank(events, source, start, end, cut_frame):
    scope = dict(device=BROKER, capture_id="mon", source_sha256=source,
                 partition="EXTERNAL_ARCHIVAL_EVALUATION", start=start/NS, end=end/NS,
                 reference_end=end/NS, frame_end=cut_frame)
    candidates, last = [], {}
    for frame, ns, comp in events:
        uid = canonical_digest([source, frame, OWNER_MAC])
        row = dict(uid=uid, device=BROKER, capture_id="mon", source_sha256=source,
                   partition=scope["partition"], owner=OWNER_MAC, canonical_key=comp,
                   component_id=canonical_digest([OWNER_MAC, comp]), session_id=canonical_digest([OWNER_MAC, "mon", comp]),
                   protocol=comp[0], frame=frame, timestamp=ns/NS, use="REFERENCE", label=0,
                   reference_end=end/NS, bank_end_frame=cut_frame, activity="UNKNOWN", activity_verified=False)
        candidates.append(row)
        last[comp] = row
    ordered = sorted(last.values(), key=lambda r: (r["device"], r["protocol"], r["component_id"]))
    census = dict(generator_version=VERSION, status="COMPLETE", enumeration="ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT",
                  window_closed=True, duration_seconds=7200, t0=start/NS, cutoff=end/NS, cutoff_frame=cut_frame,
                  capture_id="mon", candidate_rows=len(ordered), candidates_sha256=canonical_digest(ordered),
                  source_sha256=source, normality_evidence="Publisher attack-free Monday, all labels 0",
                  device_registry=[dict(device=BROKER, owner=OWNER_MAC, partition=scope["partition"])],
                  decoder_identity={"pcap": "Ethernet", "prefix": "continuous_input_v3"})
    sparse = plan_banks(ordered, census, t0=start/NS, policy="B2")
    anchors = {r["uid"] for r in sparse["rows"]}
    plan = plan_dense_positions(candidates, [scope], encoded_uids=anchors, mandatory_uids=anchors)
    require(set(plan["selected_uids"]) == {r["uid"] for r in candidates}, "DAD bank below cap")
    return dict(anchors=len(anchors), selected=len(plan["selected_uids"]), groups=plan["groups"],
                selected_uid_sha256=plan["selected_uid_sha256"], extra_history=0)


def audit(cache, tshark):
    pins = json.loads((HERE / "INPUTS.json").read_text(encoding="utf-8"))["files"]
    for name, meta in pins.items():
        data = (cache / name).read_bytes()
        require(len(data) == meta["bytes"] and hashlib.sha256(data).hexdigest() == meta["sha256"], name)
        require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == meta["git_blob"], name)

    groups = defaultdict(list)
    rosters = defaultdict(list)
    days = {}
    carry_client = {}
    client_end_seq = {}
    missing_tuple = []
    cross_day_ids = Counter()
    reference = defaultdict(Counter)
    reference_events = []
    commission_components = defaultdict(set)
    timestamps = []
    all_target_tcp = []
    start = cutoff = None

    def register(frame, kind, source):
        rosters[kind].append(canonical_digest([source, frame, OWNER_MAC]) + "\n")

    for i, day in enumerate(DAYS):
        stem = f"capture_1910{21+i}0000"
        path = cache / f"{stem}_{day}.pcap"
        digest = pins[path.name]["sha256"]
        labels = list(csv.DictReader((cache / (stem + "_labels.csv")).read_text(encoding="utf-8-sig").splitlines(),
                                     delimiter=";"))
        engine = Engine()
        contexts = Contexts(day, [OWNER_MAC], ethernet)
        stats = Counter()
        publish_by_source_client = Counter()
        ns_list, cumulative = [], [0]
        seen_local, checked_directions = set(), set()
        component_clock = {}
        previous_raw = None
        label_counts, positives, tcp_offsets = Counter(), [], []
        for trio in zip_longest(packets(path), decode(path, tshark), labels):
            require(all(x is not None for x in trio), f"{day}: PCAP/CSV row count")
            (frame, ns, header, reason), row, lab = trio
            require(int(row["frame.number"]) == frame == int(lab["frame.number"]), f"{day}:{frame}: identity")
            require(ns == int(Decimal(row["frame.time_epoch"]) * NS), "clock decoder discrepancy")
            require(row["frame.cap_len"] == row["frame.len"], "truncated frame")
            contexts.append({k: v for k, v in row.items() if not k.startswith("mqtt.")})
            if frame == 1:
                first = ns
            if previous_raw is not None and ns < previous_raw:
                stats["adjacent_clock_regressions"] += 1
            previous_raw = ns
            expected_clock = max(engine.clock, ns) if engine.clock is not None else ns
            stats["max_clock_adjustment_ns"] = max(stats["max_clock_adjustment_ns"], expected_clock - ns)
            flag_label = int(lab["label"])
            require(flag_label in (0, 1), "non-binary label")
            label_counts[flag_label] += 1
            expected_sp = row["tcp.srcport"] or row["udp.srcport"]
            if lab["ip.src"] or lab["tcp.srcport"]:
                require((lab["ip.src"], lab["tcp.srcport"]) == (row["ip.src"], expected_sp),
                        f"{day}:{frame}: label source")
            elif row["ip.src"] or expected_sp:
                missing_tuple.append([day, frame, row["ip.src"], row["ip.dst"], row["ip.proto"]])
                require(not flag_label and row["ip.dst"] != BROKER, "missing tuple on evaluation target")
            if lab["mqtt.msgid"]:
                require(row["mqtt.msgid"] == lab["mqtt.msgid"], f"{day}:{frame}: packet identifier")
            sm, dm = row["eth.src"].replace(":", ""), row["eth.dst"].replace(":", "")
            src, dst = row["ip.src"], row["ip.dst"]
            require((src == BROKER) == (sm == OWNER) and (dst == BROKER) == (dm == OWNER), "IP/MAC conflict")
            event, comp = None, None
            if header is not None:
                proto, size, srcint, dstint, sp, dp, dmac, smac = header
                require((str(ipaddress.IPv4Address(srcint)), str(ipaddress.IPv4Address(dstint)), size, smac, dmac)
                        == (src, dst, int(row["ip.len"]), sm, dm), "L3 identity/length mismatch")
                fields = TCP if proto == 6 else UDP
                require(int(row["ip.proto"]) == proto and all(row[key] for key in COMMON + fields), "incomplete header")
                require((sp, dp) == (int(row[fields[0]]), int(row[fields[1]])), "L4 mismatch")
                comp = (proto, *sorted(((src, sp), (dst, dp))))
                require(ns >= component_clock.get(comp, -1), "component clock regression needs frozen exclusion")
                component_clock[comp] = ns
                if dst == BROKER and src != BROKER:
                    event = (OWNER, proto, size, srcint, (proto, srcint, sp, dstint, dp))
            else:
                require(reason == "NON_IPV4" or row["ip.proto"] not in ("6", "17"), f"rejected transport: {reason}")
            clock = engine.advance(frame, ns, day, event)
            require(clock == expected_clock, "causal prefix clock")
            require(contexts.query_allowed == bool(header and OWNER in (sm, dm)), "RECENT admission mismatch")
            if start is None and event is not None:
                require(day == "mon", "no commissioning origin")
                start, cutoff = ns, ns + 7200 * NS
            if day == "mon" and clock <= cutoff:
                cut_frame = frame
                if comp and OWNER in (sm, dm):
                    reference[str(proto)]["both_directions"] += 1
                    commission_components[str(proto)].add(comp)
                    reference_events.append((frame, ns, comp))
                    register(frame, f"reference_candidates_{proto}", digest)
                    if event:
                        reference[str(proto)]["inbound"] += 1
            if not event or proto != 6:
                require(flag_label == 0, f"{day}:{frame}: non-broker positive")
                continue
            flags = int(row["tcp.flags"], 16)
            publish = row["mqtt.msgtype"] == "3"
            if (flags & 0x12) == 2:
                carry_client.pop(comp, None)
                client_end_seq.pop(comp, None)
            seq, length = int(row["tcp.seq_raw"]), int(row["tcp.len"])
            if comp not in checked_directions and comp in client_end_seq:
                require(seq == client_end_seq[comp], f"{day}:{frame}: cross-day TCP sequence")
            checked_directions.add(comp)
            client_end_seq[comp] = (seq + length + int(bool(flags & 2)) + int(bool(flags & 1))) % (2**32)
            if row["mqtt.clientid"]:
                carry_client[comp] = row["mqtt.clientid"]
                seen_local.add(comp)
            if lab["mqtt.clientid"]:
                require(carry_client.get(comp) == lab["mqtt.clientid"], f"{day}:{frame}: MQTT client")
                if comp not in seen_local:
                    cross_day_ids[day] += 1
                if src == "10.6.56.41" and publish:
                    publish_by_source_client[lab["mqtt.clientid"]] += 1
            ns_list.append(clock)
            cumulative.append(cumulative[-1] + size)
            values = engine.features(OWNER, proto)
            rates = (values[0], values[1], values[4], values[5])
            for j, width in enumerate((1, 10)):
                left = bisect_right(ns_list, clock - width * NS)
                require((len(ns_list) - left) / width == rates[2*j]
                        and (cumulative[-1] - cumulative[left]) / width == rates[2*j+1], "window parity")
            pt = Point(day, frame, ns, comp, flags, publish, lab["mqtt.clientid"], rates)
            all_target_tcp.append(clock)
            tcp_offsets.append(frame)
            if flag_label:
                require(src == "10.6.56.41" and dp == 1883 and publish and lab["mqtt.msgid"]
                        and lab["mqtt.clientid"], "anomalous frame lost event binding")
                groups[day].append(pt)
                positives.append(frame)
                register(frame, day + "_positive", digest)
            elif day == "mon" and clock <= cutoff:
                groups["reference_tcp_in"].append(pt)
                timestamps.append(clock)
            elif day in ("mon", "sun"):
                groups[day + "_normal"].append(pt)
                register(frame, day + "_normal", digest)
            elif day == "tue":
                groups["tue_observed"].append(pt)
            stats["inbound_tcp"] += 1
            stats["inbound_publish"] += publish
            stats["inbound_bypass"] += pt.bypass
        days[day] = dict(frames=len(labels), first_ns=first, last_ns=ns, labels=dict(label_counts), **stats,
                         first_in_tcp=tcp_offsets[0], last_in_tcp=tcp_offsets[-1],
                         source41_publish_by_client=publish_by_source_client,
                         positive_frame_range=[positives[0], positives[-1]] if positives else [],
                         positive_ns_range=[groups[day][0].ns, groups[day][-1].ns] if positives else [],
                         positive_flags=dict(Counter(hex(p.flag) for p in groups[day])))

    groups["clean_normal"] = groups["mon_normal"] + groups["sun_normal"]
    groups["clean_off_guard"] = [p for p in groups["clean_normal"] if not p.bypass]
    groups["clean_publish"] = [p for p in groups["clean_normal"] if p.publish]
    groups["clean_publish_source41"] = [p for p in groups["clean_publish"] if ("10.6.56.41" in (p.comp[1][0], p.comp[2][0]))]
    groups["positives"] = [p for day in DAYS[2:6] for p in groups[day]]
    metrics = {k: summarize(v) for k, v in groups.items() if v}
    for baseline in ("mon_normal", "clean_normal", "clean_publish_source41"):
        bounds = metrics[baseline]["rates"]
        for group in (*DAYS[2:6], "positives"):
            same = sum(all(bounds[key]["p05"] <= x <= bounds[key]["p95"] for key, x in zip(RATE_NAMES, p.rates))
                       for p in groups[group])
            metrics[group].setdefault("inside_four_marginal_p05_p95", {})[baseline] = same
            high = sum(any(x > bounds[key]["p95"] for key, x in zip(RATE_NAMES, p.rates)) for p in groups[group])
            metrics[group].setdefault("above_any_marginal_p95", {})[baseline] = high
    ordered_uids = [uid for members in rosters.values() for uid in members]
    require(len(set(ordered_uids)) == len(ordered_uids), "reference/query or cross-view UID collision")
    first_query = groups["mon_normal"][0]
    times = timestamps + [first_query.ns]
    require(timestamps[0] == start and timestamps[-1] <= cutoff < first_query.ns, "Monday boundary")
    require(max(b-a for a,b in zip(times,times[1:])) <= 3600*NS, "Monday gap")
    require(all(a<=b for a,b in zip(all_target_tcp,all_target_tcp[1:])), "file order")
    return dict(inputs_sha256=hashlib.sha256((HERE/"INPUTS.json").read_bytes()).hexdigest(),
                quantiles="empirical nearest rank; equal weight per query; current included",
                daily=days, missing_author_tuple=missing_tuple, cross_day_client_bindings=dict(cross_day_ids),
                commissioning=dict(start_ns=start, cutoff_ns=cutoff, last_reference_frame=cut_frame,
                    last_inbound_ns=timestamps[-1], first_query_frame=first_query.frame, first_query_ns=first_query.ns,
                    last_mon_tcp_query_ns=groups["mon_normal"][-1].ns,
                    max_observed_gap_through_first_query_ns=max(b-a for a,b in zip(times,times[1:])),
                    week_max_inbound_tcp_gap_ns=max(b-a for a,b in zip(all_target_tcp,all_target_tcp[1:])),
                    by_protocol=reference, component_roster={k:sorted(v) for k,v in commission_components.items()}),
                selected_bank=select_bank(reference_events, pins["capture_1910210000_mon.pcap"]["sha256"],
                                          start, cutoff, cut_frame),
                groups=metrics, roster_digest_scheme="canonical_digest([fileSHA256,1basedFrame,colonMAC]); roster SHA256 of UIDs each followed by LF, in capture order",
                rosters={k:dict(rows=len(v),sha256=hashlib.sha256("".join(v).encode("ascii")).hexdigest()) for k,v in rosters.items()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cache", type=Path)
    parser.add_argument("--tshark", default="tshark")
    args = parser.parse_args()
    report = audit(args.cache, args.tshark)
    output = HERE / "AUDIT.json"
    receipt = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    if output.exists():
        require(output.read_bytes() == receipt, "replay differs from the sealed audit")
    else:
        with output.open("xb") as destination:
            destination.write(receipt)
    print(output)
