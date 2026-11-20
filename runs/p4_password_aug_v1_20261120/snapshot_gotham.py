"""Build causal, payload-free training snapshots from original Gotham packet prefixes."""
import csv
import gzip
import hashlib
import json
from itertools import islice
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from zipfile import ZipFile

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
sys.path.insert(0, str(RUNS / "device_context_training_v2_20261105"))
sys.path.insert(0, str(RUNS.parent / "repo/ood"))
sys.path.insert(0, str(RUNS / "p4_gotham_password_source_readiness_20261120"))
from continuous_input_v3 import Contexts, digest, nanos
from constrained_onboarding_reference_v2 import query_descriptor
from packet_reader import packets
from stream_core import Engine
import issue27ckbu_unified_tshark_causal_frontend_v1 as ethernet

FIELDS = ("frame.number frame.time_epoch frame.cap_len frame.len eth.src eth.dst ip.src ip.dst "
          "ip.version ip.proto ip.hdr_len ip.dsfield ip.len ip.flags ip.ttl ipv6.src ipv6.dst "
          "ipv6.tclass ipv6.plen ipv6.hlim ipv6.nxt tcp.srcport tcp.dstport tcp.flags "
          "tcp.window_size_value tcp.seq_raw tcp.ack_raw tcp.urgent_pointer tcp.hdr_len "
          "tcp.len udp.srcport udp.dstport udp.length").split()


def snapshots(path, member, anchors, source_sha, executable="C:/Program Files/Wireshark/tshark.exe",
              *, excluded=None):
    probe = next(iter(anchors.values()))
    owner = probe["mac"]
    owner_hex = owner.replace(":", "")
    ctx = Contexts(member, [owner], ethernet)
    engine = Engine()
    last = max(anchors)
    cmd = [str(executable), "-n", "-o", "ip.defragment:FALSE",
           "-o", "tcp.desegment_tcp_streams:FALSE", "-r", str(path), "-c", str(last),
           "-T", "fields", "-E", "occurrence=f"]
    for field in FIELDS:
        cmd.extend(["-e", field])
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True, encoding="utf-8") as proc:
        rows = csv.DictReader(proc.stdout, fieldnames=FIELDS, delimiter="\t", quoting=csv.QUOTE_NONE)
        for frame, ns, header, _ in islice(packets(path), last):
            row = next(rows)
            assert int(row["frame.number"]) == frame and nanos(row["frame.time_epoch"]) == ns
            _, namespace, _ = ctx.append(row)
            event = None
            if header:
                proto, length, src, dst, sp, dp, dmac, smac = header
                if dmac == owner_hex and smac != owner_hex and src != dst:
                    event = (owner_hex, proto, length, src, (proto, src, sp, dst, dp))
            engine.advance(frame, ns, member, event)
            if frame not in anchors:
                continue
            a = anchors[frame]
            if excluded is not None and (not event or not ctx.query_allowed):
                excluded.append((frame,ctx.query_reason))
                continue
            assert event and ctx.query_allowed and row["ip.dst"] == a["target"] and row["ip.src"] == a["source"]
            assert ns == int(a["timestamp_ns"]) and sp == int(a["source_port"]) and dp == int(a["target_port"])
            if excluded is None:
                assert int(row["tcp.len"]) > 0 and int(row["tcp.flags"], 16) & 0x12 != 2
            flow, state, proof = ctx.states[namespace].snapshot()
            key = namespace[-1]
            uid = digest([source_sha, frame, owner])
            meta = dict(uid=uid, frame=frame, owner=owner, device=a["target"], capture_id=member,
                        session_id=digest(namespace), component_id=digest([owner, key]), canonical_key=key,
                        source_sha256=source_sha, timestamp=ns/1_000_000_000, partition="DEV", protocol=6,
                        label=int(a["label"]), use="QUERY")
            q, _ = query_descriptor(dict(flow=flow, state=state, provenance=proof, source_sha256=source_sha), meta)
            yield dict(uid=uid, frame=frame, member=member, device=a["device"], connection=a["connection"],
                       label=meta["label"], flow=flow, provenance=proof, q=q.tolist(), context=engine.features(owner_hex, 6))
        assert next(rows, None) is None and proc.wait() == 0


def main():
    from count_connections import ARCHIVE
    data = {}
    with (HERE / "GOTHAM_CONNECTIONS.csv").open(encoding="utf8", newline="") as stream:
        for row in csv.DictReader(stream):
            group = data.setdefault(row["member"], {})
            assert int(row["frame"]) not in group
            group[int(row["frame"])] = row
    dest = HERE / ".private"
    dest.mkdir(exist_ok=True)
    records = []
    with ZipFile(ARCHIVE) as archive, tempfile.TemporaryDirectory(prefix="p04-gotham-") as folder:
        for member, anchors in data.items():
            key = Path(member).stem
            suffix = "attack" if next(iter(anchors.values()))["label"] == "1" else "normal"
            output = dest / f"{key}_{suffix}.jsonl.gz"
            receipt = output.with_suffix(".receipt.json")
            if output.exists() and receipt.exists():
                previous = json.loads(receipt.read_bytes())
                if (previous["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
                        and previous["csv_sha256"] == hashlib.sha256((HERE/"GOTHAM_CONNECTIONS.csv").read_bytes()).hexdigest()
                        and previous["reader_sha256"] == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()):
                    records.append(previous)
                    continue
            raw = Path(folder) / "capture.pcap"
            with archive.open(member) as stream, raw.open("wb") as out:
                shutil.copyfileobj(stream, out, 2**20)
            with raw.open("rb") as f:
                sha = hashlib.sha256()
                for block in iter(lambda: f.read(4*2**20), b""):
                    sha.update(block)
            tmp = output.with_suffix(".tmp")
            n = 0
            with gzip.open(tmp, "wt", encoding="utf8", newline="\n") as out:
                for row in snapshots(raw, member, anchors, sha.hexdigest()):
                    out.write(json.dumps(row, separators=(",", ":"))+"\n")
                    n += 1
            if n != len(anchors):
                raise ValueError(f"snapshot coverage mismatch in {member}")
            tmp.replace(output)
            result = dict(file=output.name, rows=n, raw_sha256=sha.hexdigest(), member=member,
                          sha256=hashlib.sha256(output.read_bytes()).hexdigest(),
                          csv_sha256=hashlib.sha256((HERE/"GOTHAM_CONNECTIONS.csv").read_bytes()).hexdigest(),
                          reader_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
            receipt.write_text(json.dumps(result, indent=2)+"\n", encoding="utf8")
            records.append(result)
            print(member, n, flush=True)
    assert sum(r["rows"] for r in records) == 1567
    (HERE / "GOTHAM_SNAPSHOTS.json").write_text(json.dumps(records, indent=2)+"\n", encoding="utf8")


if __name__ == "__main__":
    main()
