"""Bind client and authentication events to the actual Ethernet PCAP."""
from collections import Counter, defaultdict
from decimal import Decimal
import csv
import hashlib
import ipaddress
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
HISTORY = HERE.parent/"p4_ccnr_history60_v1_20261120"
HEADERS = (
    "frame.number", "frame.time_epoch", "frame.len", "frame.cap_len", "eth.src", "eth.dst",
    "ip.src", "ip.dst", "ip.proto", "ip.hdr_len", "ip.dsfield", "ip.len", "ip.flags", "ip.frag_offset", "ip.ttl",
    "ipv6.src", "ipv6.dst", "tcp.srcport", "tcp.dstport", "tcp.flags", "tcp.len", "tcp.hdr_len", "tcp.stream",
    "tcp.seq_raw", "tcp.ack_raw", "tcp.window_size_value", "tcp.urgent_pointer", "http.request.method",
    "http.request.uri", "http.content_type", "http.response.code", "http.request_in",
)
SCENARIOS = ("successful_login", "mistake_then_retry", "disconnect_then_reconnect")
NS = 10**9
SKEW = 5_000_000


def read(path):
    return json.loads(path.read_bytes())


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    return dict(sha256=sha(path.read_bytes()), bytes=path.stat().st_size)


def save(path, value):
    tmp = path.with_suffix(path.suffix+".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False)+"\n", encoding="utf8")
    tmp.replace(path)


def entries(path):
    return [json.loads(line) for line in path.read_text(encoding="utf8").splitlines()]


def timestamp(row):
    return int(Decimal(row["frame.time_epoch"]) * NS)


def inside(start, event, end):
    return start-SKEW <= event <= end+SKEW


def tshark_fields(path, port):
    program = Path(shutil.which("tshark") or "C:/Program Files/Wireshark/tshark.exe")
    if not program.is_file():
        raise FileNotFoundError("TShark")
    command = [str(program), "-n", "-2", "-r", str(path), "-d", f"tcp.port=={port},http",
               "-T","fields","-E","header=y","-E","occurrence=a"]
    for field in HEADERS:
        command += ["-e", field]
    decoder = subprocess.run(command, encoding="utf8", capture_output=True, check=True, timeout=60)
    rows = csv.DictReader(decoder.stdout.splitlines(), delimiter="\t")
    assert rows.fieldnames == list(HEADERS)
    parsed = list(rows)
    assert all(None not in r and None not in r.values() and int(r["frame.number"]) == i
               for i,r in enumerate(parsed,1))
    return parsed


def raw_evidence(pcap, fields, topology):
    expected = read(HISTORY/"PACKAGE_MANIFEST.json")["files"]
    code = {name:identity(HISTORY/name) for name in ("history_common.py","history_stream.py")}
    assert all(v["sha256"] == expected[n] for n,v in code.items())
    sys.path.insert(0, str(HISTORY))
    from history_stream import History, records, decode

    state = History()
    host, *customers = topology["endpoints"]
    loyal = {e["ip"]: e["mac"] for e in customers}
    streams = defaultdict(list)
    h = {}
    directions = Counter()
    source = int(ipaddress.IPv4Address(host["ip"]))
    owner = host["mac"].replace(":","")
    for (frame,ns,packet), row in zip(records(pcap), fields, strict=True):
        assert frame == int(row["frame.number"]) and ns == timestamp(row)
        assert len(packet) == int(row["frame.cap_len"])
        state.advance(ns)
        decoded = decode(packet, False)
        if not row["tcp.stream"]:
            assert not decoded or decoded.proto != 6
            continue
        a, b = decoded.endpoints
        assert decoded.proto == 6 and {int(row["tcp.srcport"]),int(row["tcp.dstport"])} == {a[1],b[1]}
        incoming = b[0] == source
        other = row["ip.src" if incoming else "ip.dst"]
        assert other in loyal
        assert (row["eth.dst"], row["eth.src"]) == ((host["mac"], loyal[other]) if incoming else (loyal[other],host["mac"]))
        assert (b[1] if incoming else a[1]) == topology["server_port"]
        state.observe(owner, decoded, incoming)
        stream = int(row["tcp.stream"])
        flags = int(row["tcp.flags"],16)
        assert flags == decoded.flags
        events = dict(frame=frame, ns=ns, incoming=incoming, flags=flags, seq=decoded.seq, ack=decoded.ack,
                      peer=(other, a[1] if incoming else b[1]), size=decoded.data)
        streams[stream].append(events)
        directions[(other, "ingress" if incoming else "egress")] += 1
        if row["http.request.method"]:
            assert incoming and decoded.data > 0
            activity, count, _ = state.value(owner, decoded, incoming)
            h[frame] = (state.clock, count, activity)
    return streams, h, directions, code


def handshake(packets):
    sent = next((p for p in packets if p["incoming"] and p["flags"] & 0x12 == 2), None)
    if not sent:
        return None
    next_seq = (sent["seq"]+1) & 0xffffffff
    recv = next((p for p in packets if p["frame"] > sent["frame"] and not p["incoming"]
                 and p["flags"] & 0x12 == 0x12 and p["ack"] == next_seq), None)
    if not recv:
        return None
    reply_seq = (recv["seq"]+1) & 0xffffffff
    ack = next((p for p in packets if p["frame"] > recv["frame"] and p["incoming"]
                and p["flags"] & 0x16 == 0x10 and p["seq"] == next_seq and p["ack"] == reply_seq), None)
    return (sent, recv, ack) if ack else None


def summarize_pilot(result, case, handshakes, packets):
    by_scenario = defaultdict(list)
    for row in result:
        by_scenario[row["scenario_id"]].append(row)
    case_counts = defaultdict(Counter)
    for ident, attempts in by_scenario.items():
        label = attempts[0]["scenario"]
        c = case_counts[label]
        c["cases"] += 1
        if not all(a["aligned"] for a in attempts):
            c["incomplete"] += 1
            continue
        if label == "successful_login":
            c["proved"] += int(len(attempts) == 1 and attempts[0]["observed_status"] == 200)
        elif label == "mistake_then_retry":
            c["proved"] += int(len(attempts) == 2
                and attempts[0]["tcp_stream"] == attempts[1]["tcp_stream"]
                and [a["observed_status"] for a in attempts] == [401,200]
                and [a["request_index"] for a in attempts] == [1,2])
        else:
            drop = [e for e in case[ident] if e["event"] == "disconnect"]
            reset = [p for p in packets[attempts[0]["tcp_stream"]] if p["incoming"] and p["flags"] & 4]
            fresh = (len(attempts) == 2 and len(drop) == 1 and attempts[0]["tcp_stream"] != attempts[1]["tcp_stream"]
                     and all(a["observed_status"] == 200 and a["request_index"] == 1 for a in attempts))
            if fresh:
                t = drop[0]["time_ns"]
                new = handshakes[attempts[1]["tcp_stream"]][0]
                c["proved"] += int(tuple(drop[0]["peer"]) == tuple(attempts[0]["peer"])
                                   and any(p["frame"] < new["frame"] and inside(t,p["ns"],new["ns"]) for p in reset))
    groups = []
    for label in SCENARIOS:
        attempts = [x for x in result if x["scenario"] == label]
        matched = [x for x in attempts if x["aligned"]]
        c = case_counts[label]
        groups.append(dict(scenario=label, cases=c["cases"], proved_cases=c["proved"], requests=len(attempts),
                      connections=len({(tuple(a["peer"]),a["connect_start_ns"]) for a in attempts if a["peer"]}),
                      aligned=len(matched), unaligned=len(attempts)-len(matched),
                      observed_200=sum(a["observed_status"] == 200 for a in matched),
                      observed_401=sum(a["observed_status"] == 401 for a in matched)))
    return groups


def join(out, capture, scenario_summary=None):
    pcap = out/"login.pcap"
    pcap_id = identity(pcap)
    rows = tshark_fields(pcap, capture["server_port"])
    packets, history, directions, code = raw_evidence(pcap, rows, capture)
    handshakes = {k:handshake(p) for k,p in packets.items()}
    sockets = defaultdict(list)
    requests = defaultdict(list)
    responses = defaultdict(list)
    for k,v in handshakes.items():
        if v:
            sockets[v[0]["peer"]].append(k)
    for r in rows:
        if r["http.request.method"]:
            assert r["http.request.method"] == "POST" and r["http.request.uri"] == "/login"
            assert r["http.content_type"] == "application/x-www-form-urlencoded"
            requests[int(r["tcp.stream"])].append(r)
        if r["http.response.code"]:
            responses[int(r["http.request_in"])].append(r)
    assert len(history) == sum(map(len, requests.values()))

    services = defaultdict(list)
    for event in entries(out/"server.jsonl"):
        assert event["event"] == "auth"
        assert event["local"] == [capture["endpoints"][0]["ip"],capture["server_port"]]
        services[(tuple(event["peer"]),event["request_index"])].append(event)
    all_clients = [e for n in range(1,4) for e in entries(out/f"client_{n}.jsonl")]
    case = defaultdict(list)
    result = []
    matched_frames = set()
    matched_server = set()
    for e in all_clients:
        case[e["scenario_id"]].append(e)
        if e["event"] != "request":
            continue
        row = dict(**e, aligned=False)
        result.append(row)
        if e["peer"] is None:
            row["reason"] = "CLIENT_SOCKET_UNBOUND"
            continue
        peer = tuple(e["peer"])
        options = [k for k in sockets[peer] if inside(e["connect_start_ns"], handshakes[k][0]["ns"],e["done_ns"])]
        if len(options) != 1:
            row["reason"] = "CONNECTION_NOT_UNIQUE"
            continue
        stream, = options
        syn,syn_ack,ack = handshakes[stream]
        row["tcp_stream"] = stream
        idx = e["request_index"]
        if not 1 <= idx <= len(requests[stream]):
            row["reason"] = "REQUEST_ORDINAL_MISSING"
            continue
        request = requests[stream][idx-1]
        frame = int(request["frame.number"])
        reply = responses[frame]
        if len(reply) != 1 or int(reply[0]["tcp.stream"]) != stream:
            row["reason"] = "PCAP_RESPONSE_UNBOUND"
            continue
        server = [s for s in services[(peer,idx)]
                  if inside(syn["ns"],s["socket_open_ns"],e["done_ns"])
                  and inside(e["start_ns"],s["decision_ns"],e["done_ns"])]
        if len(server) != 1:
            row["reason"] = "AUTH_LOG_NOT_UNIQUE"
            continue
        s, = server
        seen = int(reply[0]["http.response.code"])
        if not (seen == s["status"] == e["observed_status"] == e["expected_status"]
                and s["authenticated"] == (seen==200)):
            row["reason"] = "AUTH_RESULT_MISMATCH"
            continue
        reqtime = timestamp(request)
        rtime = timestamp(reply[0])
        if not (ack["frame"] <= frame < int(reply[0]["frame.number"])
                and inside(e["start_ns"], reqtime, s["decision_ns"])
                and inside(s["decision_ns"],rtime,e["done_ns"])):
            row["reason"] = "TIMESTAMP_ORDER"
            continue
        clock, count, active = history[frame]
        latest = {}
        for v in handshakes.values():
            if v and v[0]["peer"][0] == peer[0] and v[0]["frame"] <= frame:
                key = v[0]["peer"]
                if key not in latest or v[0]["frame"] > latest[key][0]["frame"]:
                    latest[key] = v
        check = sum(v[0]["ns"] > clock-60*NS and v[2]["frame"] <= frame for v in latest.values())
        assert count == check and 1 <= count <= active, ("HANDSHAKE_PREFIX_PARITY",frame,count,check)
        uid = sha(json.dumps([pcap_id["sha256"],frame,capture["endpoints"][0]["mac"]],
                             separators=(",",":")).encode("ascii"))
        assert frame not in matched_frames and id(s) not in matched_server
        matched_frames.add(frame)
        matched_server.add(id(s))
        row.update(aligned=True, frame=frame, response_frame=int(reply[0]["frame.number"]), frame_ns=reqtime,
                   response_ns=rtime, authenticated=s["authenticated"], server_decision_ns=s["decision_ns"],
                   syn_frame=syn["frame"], synack_frame=syn_ack["frame"], ack_frame=ack["frame"],
                   capture_uid=uid, handshakes_60s=count, active_tuples_60s=active)
    groups = (scenario_summary or summarize_pilot)(result, case, handshakes, packets)
    match = sorted((x for x in result if x["aligned"]), key=lambda x: x["frame"])
    unexpected_raw = len(history)-len(matched_frames)
    unexpected_auth = sum(map(len, services.values()))-len(matched_server)
    checks = dict(total_frames=len(rows), tcp_connections=len(handshakes),
                  complete_duplex_handshakes=sum(v is not None for v in handshakes.values()),
                  direction_counts={e["ip"]: {d:directions[(e["ip"],d)] for d in ("ingress","egress")}
                                    for e in capture["endpoints"][1:]},
                  unmatched_pcap_requests=unexpected_raw, unmatched_server_auth=unexpected_auth,
                  aligned_requests=len(match), handshake_60s_oracle_identical=len(match),
                  h60_min=min((e["handshakes_60s"] for e in match),default=None),
                  h60_max=max((e["handshakes_60s"] for e in match),default=None),
                  h60_histogram=dict(sorted(Counter(x["handshakes_60s"] for x in match).items())),
                  request_uid_order_sha256=sha("".join(x["capture_uid"]+"\n" for x in match).encode("ascii")),
                  verified_history_source=code)
    assert len(rows) == capture["capture"]["captured_ingress"] + capture["capture"]["captured_egress"]
    good = (not unexpected_raw and not unexpected_auth and all(v is not None for v in handshakes.values())
            and not capture["capture"]["capture_kernel_drops"]
            and all(g["unaligned"] == 0 and g["proved_cases"] == g["cases"] for g in groups))
    return dict(status="PASS" if good else "REVIEW", pcap=pcap_id, checks=checks, scenarios=groups), result, rows


def write_tables(out, report, pairs):
    with (out/"SCENARIOS.csv").open("w", encoding="utf8", newline="") as stream:
        w = csv.DictWriter(stream, fieldnames=list(report["scenarios"][0]),lineterminator="\n")
        w.writeheader()
        w.writerows(report["scenarios"])
    with (out/"ALIGNMENT.jsonl").open("w", encoding="utf8", newline="\n") as stream:
        for row in pairs:
            stream.write(json.dumps(row, separators=(",",":"))+"\n")
    save(out/"PACKET_ACCEPTANCE.json", report)


if __name__ == "__main__":
    destination = Path(sys.argv[1])
    capture = read(destination/"CAPTURE.json")
    report, pairs, _ = join(destination,capture)
    write_tables(destination,report,pairs)
    print(json.dumps({"status":report["status"],"scenarios":report["scenarios"],
                      "handshakes":report["checks"]["complete_duplex_handshakes"]}, ensure_ascii=False))
