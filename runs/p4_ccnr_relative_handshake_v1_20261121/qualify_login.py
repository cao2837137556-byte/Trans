"""Check same-service normal coverage without retaining authentication values."""
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import struct
import sys
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
TON = RUNS/"p4_ton_password_frozen_v12_20261118"
sys.path.insert(0, str(TON))
from admission import label_index, zeek_rows

HOSTS = tuple(f"192.168.1.{x}" for x in (152,190,193,195))
LOGIN_PATH = re.compile(r"/(?:log[-_]?in|sign[-_]?in|authenticate|auth|logon)(?:[/?._-]|$)", re.I)


def stamp(n):
    return datetime.fromtimestamp(n/1e9, timezone.utc).isoformat()


def asset(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(4<<20), b""):
            h.update(b)
    return dict(sha256=h.hexdigest(), bytes=path.stat().st_size)


def ton(root):
    cfg = json.loads((TON/"SCOPED_INPUTS.json").read_bytes())
    paths = {key:root/cfg["sources"][key]["paths"][0].split("extracted/", 1)[1]
             for key in ("zeek","events","normal1log","normal2log")}
    pinned = {}
    for k,path in paths.items():
        actual = asset(path)
        assert all(v == cfg["sources"][k][x] for x,v in actual.items())
        pinned[str(path.relative_to(root))] = actual
    windows, approved, _, _ = label_index(paths, cfg)
    target = {int(ipaddress.IPv4Address(h)): h for h in HOSTS}
    direction = {line:r for key, items in windows.items() if key[0] == 6 and key[3] in target
                 for r in items for line in (r[3],) if line in approved and r[4] == key}
    ports = {h:Counter() for h in HOSTS}
    services = {h:Counter() for h in HOSTS}
    for line,row in zeek_rows(paths["zeek"]):
        if line in direction:
            h = row["id.resp_h"]
            ports[h][int(row["id.resp_p"])] += 1
            services[h][row["service"] if row["service"] not in ("-", "(empty)", "") else "unknown"] += 1
    base = root/"Network_dataset_Bro/normal_Bro"
    normals = sorted(base.glob("*/conn.log"))
    assert len(normals) == 15
    endpoint, by_port, http = {}, {}, {}
    for log in normals:
        pinned[str(log.relative_to(root))] = asset(log)
        by_host = defaultdict(set)
        by_service = defaultdict(set)
        for _,r in zeek_rows(log):
            h = r["id.resp_h"]
            port = int(r["id.resp_p"])
            if h in ports and r["proto"] == "tcp" and port in ports[h]:
                by_host[h].add(r["uid"])
                by_service[(h,port)].add(r["uid"])
        endpoint[log.parent.name] = {h:len(by_host[h]) for h in HOSTS}
        by_port[log.parent.name] = {f"{h}:{port}":len(ids) for (h,port),ids in sorted(by_service.items())}
        web = log.with_name("http.log")
        pinned[str(web.relative_to(root))] = asset(web)
        selected, hint, denied, fields = (defaultdict(set) for _ in range(4))
        for _,r in zeek_rows(web):
            h = r["id.resp_h"]
            if h not in by_host or r["uid"] not in by_host[h] or int(r["id.resp_p"]) not in ports[h]:
                continue
            u = r["uid"]
            selected[h].add(u)
            if LOGIN_PATH.search(r["uri"]):
                hint[h].add(u)
            if r["status_code"] in ("401", "403"):
                denied[h].add(u)
            if r["username"] not in ("-", "(empty)", ""):
                fields[h].add(u)
        http[web.parent.name] = {h:dict(http_connections=len(selected[h]), login_path_hint=len(hint[h]),
             http_401_or_403=len(denied[h]), auth_identity_field_present=len(fields[h])) for h in HOSTS}
    clock = {role:[stamp(cfg["sources"][role][edge]) for edge in ("min_ns","max_ns")] for role in
             ("normal1","normal2","password")}
    return dict(attack_clock_and_normals_utc=clock, verified_attack_zeek_tcp_count_by_port=ports,
                attack_zeek_tcp_service_tag_counts=services, normal_conn_log_files=len(normals),
                normal_tcp_same_target_and_port=endpoint, normal_by_endpoint=by_port, normal_http_hints_same_endpoint=http,
                auth_success_retry_reconnect_confirmed=False, file_sha256=pinned,
                identity="Per-capture target IP validated; cross-capture instance unproven.")


def member_clock(archive, pin):
    name = pin["member"]
    obj = archive.getinfo(name)
    assert obj.file_size == pin["bytes"] and f"{obj.CRC:08x}" == pin["crc32"]
    with archive.open(obj) as f:
        head = f.read(24)
        order, unit = {b"\xd4\xc3\xb2\xa1":("<",1000), b"\xa1\xb2\xc3\xd4":(">",1000),
                       b"\x4d\x3c\xb2\xa1":("<",1), b"\xa1\xb2\x3c\x4d":(">",1)}[head[:4]]
        packet = struct.Struct(order+"IIII")
        first, last, frames = None, None, 0
        while hdr := f.read(packet.size):
            sec, offset, captured, wire = packet.unpack(hdr)
            assert 0 < captured <= wire and len(f.read(captured)) == captured
            now = sec*10**9 + offset*unit
            first = now if first is None else min(now,first)
            last = now if last is None else max(now,last)
            frames += 1
    assert frames == pin["raw_frames_read"]
    return dict(member=name, frames=frames, observed_utc=[stamp(first),stamp(last)], bytes=obj.file_size, crc32=pin["crc32"])


def gotham(archive_path):
    root = RUNS/"p4_gotham_password_source_readiness_20261120"
    src = root/"CONFIRMED_ATTACK_ANCHORS.csv"
    times = defaultdict(list)
    with src.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            times[(r["device"],r["member"])].append(int(r["epoch_ns"]))
    audit = json.loads((root/"CENSUS.json").read_bytes())
    with ZipFile(archive_path) as z:
        clocks = {device:{k:member_clock(z,pin) for k,pin in group.items()
                          if k in ("attack","pure_benign") and pin and pin.get("member")}
                  for device,group in audit.items()}
    return dict(scope="Clock span from existing original ZIP members; labels and counts from full source audit.",
                captured_clock_utc=clocks,
                anchor_times_utc=[dict(device=d, file=m, anchors=len(t), from_utc=stamp(min(t)), to_utc=stamp(max(t)))
                                  for (d,m),t in sorted(times.items())],
                tagged_attack_connections=sum(v["attack"]["matched"]["connections"] for v in audit.values()),
                off_bypass_with_data=sum(v["attack"]["matched"]["connections_off_guard_data"] for v in audit.values()),
                normal_same_target_telnet=0,
                evidence_sha256={f.name:asset(f) for f in (src,root/"CENSUS.json",root/"AUX_NORMAL.json")})


def main(root, dest):
    dest.mkdir(exist_ok=True, parents=True)
    note = dest/"LOGIN_LOCAL_EVIDENCE.json"
    archive_path = root.parents[2]/"gotham2025/raw/GothamDataset2025.zip"
    note.write_bytes((json.dumps(dict(ToN=ton(root), Gotham=gotham(archive_path)), ensure_ascii=False, indent=2)+"\n").encode("utf8"))
    print(note, asset(note)["sha256"])


if __name__ == "__main__":
    main(Path(sys.argv[1]), HERE/"received")
