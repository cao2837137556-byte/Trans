"""Independent TShark dissection and source-packet reader share only the physical frame index."""

from contextlib import contextmanager
import csv
from itertools import islice
import subprocess

from capture import decode, frames, iptext
from common_ton import require
from admission import tick

FIELDS = (
    "frame.number",
    "frame.time_epoch",
    "frame.len",
    "frame.cap_len",
    "sll.pkttype",
    "sll.src.eth",
    "ip.src",
    "ip.dst",
    "ip.version",
    "ip.proto",
    "ip.hdr_len",
    "ip.dsfield",
    "ip.len",
    "ip.flags",
    "ip.ttl",
    "ip.frag_offset",
    "tcp.srcport",
    "tcp.dstport",
    "tcp.flags",
    "tcp.window_size_value",
    "tcp.seq_raw",
    "tcp.ack_raw",
    "tcp.urgent_pointer",
    "tcp.hdr_len",
    "tcp.len",
    "udp.srcport",
    "udp.dstport",
    "udp.length",
    "tcp.stream",
    "udp.stream",
)


@contextmanager
def dissect(exe, files, hosts, limit, folder):
    folder.mkdir(parents=True, exist_ok=True)
    merge = None
    with (folder / "merge.stderr").open("wb") as em, (folder / "tshark.stderr").open("wb") as et:
        if len(files) == 2:
            ext = ".exe" if exe.suffix.lower() == ".exe" else ""
            merge = subprocess.Popen(
                [str(exe.with_name("mergecap" + ext)), "-a", "-w", "-", *map(str, files)],
                stdout=subprocess.PIPE,
                stderr=em,
            )
        try:
            args = [
                str(exe),
                "-n",
                "-o",
                "ip.defragment:FALSE",
                "-o",
                "tcp.desegment_tcp_streams:FALSE",
                "-r",
                "-" if merge else str(files[0]),
                "-c",
                str(limit),
                "-Y",
                " || ".join("ip.addr==" + h for h in hosts),
                "-T",
                "fields",
                "-E",
                "separator=/t",
                "-E",
                "occurrence=f",
                "-E",
                "quote=d",
            ]
            for name in FIELDS:
                args.extend(["-e", name])
            with subprocess.Popen(
                args,
                stdin=merge.stdout if merge else subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=et,
                text=True,
                encoding="utf-8",
                errors="strict",
            ) as child:
                if merge:
                    merge.stdout.close()
                try:
                    yield csv.DictReader(child.stdout, fieldnames=FIELDS, delimiter="\t", quotechar='"')
                    code = child.wait(timeout=90)
                    require(
                        code == 0,
                        "TSHARK_PREFIX_EXIT:"
                        + str(code)
                        + ":"
                        + (folder / "tshark.stderr").read_text(errors="replace")[-300:],
                    )
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.wait()
        finally:
            if merge:
                if merge.poll() is None:
                    try:
                        merge.wait(timeout=30)
                    except subprocess.TimeoutExpired:
                        merge.kill()
                        merge.wait()
                # The consumer stops at the last complete packet and can close just before padding/EOF.
                require(merge.returncode == 0, "APPENDED_NORMAL_STREAM_EXIT:" + str(merge.returncode))


def integer(s):
    return int(s, 16) if s.lower().startswith("0x") else int(s)


def check_header(row, h):
    p = "tcp" if h.proto == 6 else "udp"
    require(
        row["ip.src"] == iptext(h.src)
        and row["ip.dst"] == iptext(h.dst)
        and (integer(row["ip.proto"]), integer(row[p + ".srcport"]), integer(row[p + ".dstport"]))
        == (h.proto, h.sport, h.dport),
        "INDEPENDENT_OWNER_TUPLE",
    )
    pairs = [
        ("ip.hdr_len", h.ihl),
        ("ip.dsfield", h.ds),
        ("ip.len", h.iplen),
        ("ip.flags", h.ipflags),
        ("ip.ttl", h.ttl),
        ("sll.pkttype", h.pkttype),
    ]
    if h.proto == 6:
        pairs.extend(
            [
                ("tcp.hdr_len", h.l4len),
                ("tcp.flags", h.flags),
                ("tcp.window_size_value", h.window),
                ("tcp.seq_raw", h.seq),
                ("tcp.ack_raw", h.ack),
                ("tcp.urgent_pointer", h.urg),
                ("tcp.len", h.data),
            ]
        )
    else:
        pairs.append(("udp.length", h.l4len))
    require(all(row[k] and integer(row[k]) == v for k, v in pairs), "INDEPENDENT_FIELDS_OR_IP_LENGTH")
    if h.sender:
        require(row["sll.src.eth"].lower() == h.sender, "INDEPENDENT_SLL_SENDER")


def stream(roles, paths, cfg, card, exe, folder, limits):
    count = sum(limits[k] for k in roles)
    hosts = set(card["hosts"])
    numbers = {int.from_bytes(bytes(map(int, x.split("."))), "big") for x in hosts}
    with dissect(exe, [paths[k] for k in roles], sorted(hosts), count, folder) as decoded:
        current = next(decoded, None)
        global_frame = 0
        for role in roles:
            spec = cfg["sources"][role]
            original = frames(paths[role], spec)
            items = original if limits[role] == spec["complete_packets"] else islice(original, limits[role])
            for frame, ts, wire, raw in items:
                global_frame += 1
                h = decode(raw)
                row = None
                if current is not None and int(current["frame.number"]) == global_frame:
                    row = current
                    current = next(decoded, None)
                    require(
                        tick(row["frame.time_epoch"]) == ts
                        and int(row["frame.len"]) == wire
                        and int(row["frame.cap_len"]) == len(raw),
                        "ORIGINAL_FRAME_TIME_LENGTH",
                    )
                    if h and (h.src in numbers or h.dst in numbers):
                        check_header(row, h)
                    row["frame.number"] = str(frame)
                elif h and (h.src in numbers or h.dst in numbers):
                    raise ValueError(f"MISSING_INDEPENDENT_DECODE:{role}:{frame}")
                yield role, frame, ts, wire, len(raw), row, h
            original.close()
        require(current is None and global_frame == count, "MERGE_OR_PREFIX_POSITION")
