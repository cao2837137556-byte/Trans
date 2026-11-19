"""Resolve connection-label joins, then audit raw headers and target identity before any model scores."""

from collections import Counter, defaultdict
import csv
from decimal import Decimal
import hashlib
import ipaddress
from pathlib import Path

from capture import frames, decode, iptext
from common_ton import HERE, NS, POOLS, dump, read, require

TOL = 10_000_000


def zeek_rows(path):
    fields = None
    with path.open(encoding="utf-8-sig", newline="") as stream:
        line_id = 0
        for line in stream:
            if line.startswith("#fields"):
                fields = line.rstrip("\r\n").split("\t")[1:]
            if not line.strip() or line.startswith("#"):
                continue
            values = line.rstrip("\r\n").split("\t")
            require(fields and len(values) == len(fields), "ZEEK_CONN_SCHEMA")
            yield line_id, dict(zip(fields, values))
            line_id += 1


def rawip(s):
    return int(ipaddress.IPv4Address(s))


def reverse(k):
    p, s, sp, d, dp = k
    return p, d, dp, s, sp


def tick(s):
    return int(Decimal(s) * NS)


def label_index(paths, cfg):
    hosts = set(cfg["registered_hosts"])
    sources = set(cfg["registered_origins"])
    spec = cfg["sources"]["password"]
    windows = defaultdict(list)
    by_key = defaultdict(list)
    selected = {}
    sampled = {r["line"]: r["key_sha256"] for r in read(HERE / "PASSWORD_SAMPLE.json")}
    for line, r in zeek_rows(paths["zeek"]):
        src, dst = r["id.orig_h"], r["id.resp_h"]
        direct = src in sources and dst in hosts
        if r["proto"] not in ("tcp", "udp") or not (direct or src in hosts and dst in sources):
            continue
        proto = {"tcp": 6, "udp": 17}[r["proto"]]
        sp, dp = int(r["id.orig_p"]), int(r["id.resp_p"])
        ts = tick(r["ts"])
        known = r["duration"] not in ("", "-")
        end = ts + (tick(r["duration"]) if known else 0)
        possible = end if known else ts + 50_000_000
        k = (proto, rawip(src), sp, rawip(dst), dp)
        key = (ts // NS, src, str(sp), dst, str(dp), r["proto"])
        if line in sampled:
            require(
                hashlib.sha256("\x1f".join(map(str, key)).encode()).hexdigest() == sampled[line],
                "OLD_SAMPLE_KEY_SHA",
            )
        record = (ts, end, possible, line, k)
        windows[k].append(record)
        windows[reverse(k)].append(record)
        if direct:
            by_key[key].append(line)
            if spec["min_ns"] <= ts <= end <= spec["max_ns"] and possible + TOL <= spec["max_ns"]:
                selected[line] = (r["uid"], possible + TOL)
    hits = Counter()
    correct = set()
    with paths["events"].open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if r["src_ip"] not in sources or r["dst_ip"] not in hosts or r["proto"] not in ("tcp", "udp"):
                continue
            key = (
                tick(r["ts"]) // NS,
                r["src_ip"],
                str(int(float(r["src_port"]))),
                r["dst_ip"],
                str(int(float(r["dst_port"]))),
                r["proto"],
            )
            lines = by_key.get(key, ())
            if len(lines) != 1 or lines[0] not in selected:
                continue
            line = lines[0]
            hits[line] += 1
            if r["type"].strip().lower() == "password":
                correct.add(line)
    valid = {i: selected[i][0] for i in correct if hits[i] == 1}
    require(
        len(valid) == 81384 and len(set(valid.values())) == len(valid), "UNIQUE_PASSWORD_CONNECTION_LABELS"
    )
    return windows, valid, max(selected[i][1] for i in valid), sampled


def match(k, t, windows, valid):
    candidates = windows.get(k)
    if not candidates:
        return None
    nearby = [w for w in candidates if w[0] - TOL <= t <= w[2] + TOL]
    if len(nearby) == 1:
        start, end, _, line, direction = nearby[0]
        if line in valid and direction == k and start <= t <= end:
            return line
    return None


def layers(h):
    return (0, 1, 2) if h.off and h.data > 0 else (0, 1) if h.off else (0,)


def audit_capture(role, path, cfg, windows, valid, sampled, progress):
    spec = cfg["sources"][role]
    hosts = set(map(rawip, cfg["registered_hosts"]))
    counts = defaultdict(lambda: [0, 0, 0])
    conns = defaultdict(lambda: [set(), set(), set()])
    sample_counts = defaultdict(lambda: [0, 0, 0])
    sample_conns = defaultdict(lambda: [set(), set(), set()])
    directions = defaultdict(Counter)
    senders = defaultdict(Counter)
    spans = {}
    marks = {}
    segments = defaultdict(list)
    boundary_keys = set()
    first_ts = last_ts = prev_max = None
    biggest_gap = 0
    for frame, ts, wire, b in frames(path, spec):
        first_ts = ts if first_ts is None else min(first_ts, ts)
        last_ts = ts if last_ts is None else max(last_ts, ts)
        if prev_max is not None:
            biggest_gap = max(biggest_gap, ts - prev_max)
        prev_max = ts if prev_max is None else max(prev_max, ts)
        h = decode(b)
        if h is None:
            continue
        src, dst = h.src, h.dst
        if src not in hosts and dst not in hosts:
            continue
        for target, direction in ((src, "out"), (dst, "in")):
            if target not in hosts:
                continue
            directions[target][direction] += 1
            if src != dst:
                t = spans.setdefault(target, [ts, ts, 0])
                t[2] = max(t[2], ts - t[1])
                t[1] = max(t[1], ts)
                t[0] = min(t[0], ts)
                ss = segments[target]
                if not ss or ts - ss[-1][1] > 3600 * NS:
                    ss.append([ts, ts])
                else:
                    ss[-1][1] = max(ss[-1][1], ts)
            if direction == "out" and h.sender:
                senders[target][h.sender] += 1
            marks.setdefault((target, direction), frame)
            if (
                role != "password"
                and abs(ts - (spec["max_ns"] if role == "normal1" else spec["min_ns"])) <= 60 * NS
            ):
                boundary_keys.add((target, h.proto, tuple(sorted(((src, h.sport), (dst, h.dport))))))
        if dst not in hosts:
            continue
        line = match(h.key, ts, windows, valid) if role == "password" else None
        if role == "password" and line is None:
            continue
        key = (dst, h.proto)
        marks.setdefault((dst, f"query{h.proto}"), frame)
        for j in layers(h):
            counts[key][j] += 1
            if counts[key][j] in (1, 16, 64, 256):
                marks[(dst, f"{h.proto}_layer{j}_{counts[key][j]}")] = frame
            if role == "password":
                conns[key][j].add(line)
                if line in sampled:
                    sample_counts[key][j] += 1
                    sample_conns[key][j].add(line)
        if frame % 100000 == 0:
            progress("IDENTITY_" + role, frame, spec["complete_packets"])
    require(first_ts == spec["min_ns"] and last_ts == spec["max_ns"], "FULL_CAPTURE_CLOCK_BINDING:" + role)
    return dict(
        counts=counts,
        conns=conns,
        sample_counts=sample_counts,
        sample_conns=sample_conns,
        directions=directions,
        senders=senders,
        spans=spans,
        marks=marks,
        boundary_keys=boundary_keys,
        segments=segments,
        max_gap_ns=biggest_gap,
        tail_time=ts,
    )


def census(paths, cfg, progress):
    windows, valid, last, sampled = label_index(paths, cfg)
    scans = {k: audit_capture(k, paths[k], cfg, windows, valid, sampled, progress) for k in POOLS}
    raw = scans["password"]
    pairs = sorted(set(scans["normal1"]["counts"]) & set(scans["normal2"]["counts"]) & set(raw["counts"]))
    hosts = sorted({i for i, _ in pairs})
    require(len(hosts) == 4, "FOUR_OVERLAPPING_TARGETS")
    counts = [sum(raw["counts"][k][j] for k in pairs) for j in range(3)]
    connections = [len(set.union(*(raw["conns"][k][j] for k in pairs))) for j in range(3)]
    require(
        counts == [326961, 246398, 62087] and connections == [76677, 58794, 58114],
        "ALL_NAMED_CENSUS_REPRODUCTION",
    )
    legacy = cfg["original_sample"]
    sample_counts = [sum(raw["sample_counts"][k][j] for k in pairs) for j in range(3)]
    sample_conns = [len(set.union(*(raw["sample_conns"][k][j] for k in pairs))) for j in range(3)]
    metrics = ("frames", "off_guard", "off_guard_with_transport_data")
    require(
        sample_counts == [legacy[k] for k in metrics]
        and sample_conns == [legacy["connections_" + k] for k in metrics],
        "2000_CONNECTION_HISTORICAL_CONTROL",
    )
    normal = [sum(scans[k]["counts"][p][0] for p in pairs) for k in POOLS[:2]]
    require(
        normal == cfg["matching_normal_inbound"] and raw["tail_time"] >= last,
        f"NORMAL_COUNTS_AND_COMPLETE_ATTACK_WINDOW:{normal}/{cfg['matching_normal_inbound']}, {raw['tail_time']}/{last}",
    )
    groups = []
    ownership = {}
    for ip in hosts:
        label = iptext(ip)
        per = {}
        for role, x in scans.items():
            per[role] = dict(
                observed_directions=dict(x["directions"][ip]),
                source_addresses=dict(x["senders"][ip]),
                observed_clock_ns=x["spans"].get(ip),
                continuous_intervals_ns=x["segments"][ip],
                probe_frames={k[1]: v for k, v in x["marks"].items() if k[0] == ip},
            )
        ownership[label] = per
    for ip, proto in pairs:
        groups.append(
            dict(
                host=iptext(ip),
                protocol=proto,
                attack_counts=raw["counts"][ip, proto],
                attack_connections=[len(s) for s in raw["conns"][ip, proto]],
                normal1=scans["normal1"]["counts"][ip, proto],
                normal2=scans["normal2"]["counts"][ip, proto],
            )
        )
    report = dict(
        status="CENSUS_VERIFIED",
        identity_evidence=ownership,
        groups=groups,
        attack_candidate=counts,
        candidate_connections=connections,
        old_sample_counts=sample_counts,
        old_sample_connections=sample_conns,
        verified_password_windows=len(valid),
        last_verified_attack_deadline_ns=last,
        complete_prefix_last_ns=raw["tail_time"],
        normal_capture_max_gap_ns={k: scans[k]["max_gap_ns"] for k in POOLS[:2]},
        boundary_tuple_count=len(scans["normal1"]["boundary_keys"] & scans["normal2"]["boundary_keys"]),
    )
    return report


if __name__ == "__main__":
    cfg = read(HERE / "SCOPED_INPUTS.json")
    local = {k: Path(v) for k, v in read(HERE / ".private/LOCAL_INPUTS.json").items()}
    report = census(local, cfg, lambda *args: None)
    dump(HERE / "LOCAL_CENSUS.json", report)
    print(report["attack_candidate"], report["candidate_connections"])
    for host, p in report["identity_evidence"].items():
        print(host, {k: v["source_addresses"] for k, v in p.items()})
