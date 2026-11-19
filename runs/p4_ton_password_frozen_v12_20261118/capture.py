"""Read SLL v1 headers in physical frame order. No application data leaves the reader."""

from dataclasses import dataclass
from functools import lru_cache
import socket
import struct

from common_ton import NS, require

SHB = b"\x0a\x0d\x0d\x0a"
MAGICS = {
    bytes.fromhex(v): (e, s)
    for v, e, s in [
        ("d4c3b2a1", "<", 1000),
        ("a1b2c3d4", ">", 1000),
        ("4d3cb2a1", "<", 1),
        ("a1b23c4d", ">", 1),
    ]
}


@lru_cache(maxsize=65536)
def iptext(n):
    return socket.inet_ntoa(struct.pack("!I", n))


def ns_text(ns):
    sec, sub = divmod(ns, NS)
    return f"{sec}.{sub:09d}"


def classic(f, spec):
    global_header = f.read(24)
    endian, mult = MAGICS[global_header[:4]]
    require(
        len(global_header) == 24 and struct.unpack_from(endian + "I", global_header, 20)[0] == 113,
        "SLL_GLOBAL_HEADER",
    )
    records = struct.Struct(endian + "IIII")
    for i in range(1, spec["complete_packets"] + 1):
        h = f.read(16)
        require(len(h) == 16, "EARLY_TRUNCATED_RECORD_HEADER")
        sec, sub, cap, wire = records.unpack(h)
        require(0 < cap <= wire and cap <= 16 * 1024**2, "PCAP_RECORD_SIZE")
        b = f.read(cap)
        require(len(b) == cap, "EARLY_TRUNCATED_RECORD_BODY")
        yield i, sec * NS + sub * mult, wire, b
    tail = spec.get("tail")
    if tail:
        require(f.tell() == tail["partial_record_start_bytes"], "VERIFIED_PREFIX_END")
        h = f.read(16)
        require(len(h) == 16, "TERMINAL_RECORD_HEADER")
        cap = records.unpack(h)[2]
        require(
            cap == tail["declared_captured_bytes"]
            and len(f.read(cap + 1)) == tail["available_record_body_bytes"],
            "EXACT_PINNED_TERMINAL_TRUNCATION",
        )
    require(not f.read(1), "UNEXPECTED_COMPLETE_RECORDS")


def pcapng(f, spec):
    endian = None
    interfaces = []
    i = 0
    while h := f.read(12):
        require(len(h) == 12, "PCAPNG_BLOCK_HEADER")
        if h[:4] == SHB:
            endian = {b"\x4d\x3c\x2b\x1a": "<", b"\x1a\x2b\x3c\x4d": ">"}[h[8:12]]
            interfaces = []
        require(endian is not None, "SECTION_HEADER_REQUIRED")
        kind, size = struct.unpack_from(endian + "II", h)
        require(12 <= size <= 64 * 1024**2 and size % 4 == 0, "PCAPNG_BLOCK_SIZE")
        b = h + f.read(size - 12)
        require(len(b) == size and struct.unpack_from(endian + "I", b, size - 4)[0] == size, "PCAPNG_TRAILER")
        if kind == 1:
            link, _, snap = struct.unpack_from(endian + "HHI", b, 8)
            require(link == 113, "ALL_INTERFACES_SLL_V1")
            denominator = 10**6
            offset = 0
            pos = 16
            while pos + 4 <= size - 4:
                typ, length = struct.unpack_from(endian + "HH", b, pos)
                pos += 4
                require(pos + length <= size - 4, "IDB_OPTION_LENGTH")
                if typ == 0:
                    break
                if typ == 9:
                    require(length == 1, "CLOCK_RESOLUTION_FIELD")
                    v = b[pos]
                    denominator = (2 if v & 128 else 10) ** (v & 127)
                if typ == 14:
                    require(length == 8, "CLOCK_OFFSET_FIELD")
                    offset = struct.unpack_from(endian + "q", b, pos)[0]
                pos += (length + 3) // 4 * 4
            interfaces.append((snap, denominator, offset))
        elif kind in (2, 6):
            ix = struct.unpack_from(endian + ("H" if kind == 2 else "I"), b, 8)[0]
            hi, lo, cap, wire = struct.unpack_from(endian + "IIII", b, 12)
            snap, den, off = interfaces[ix]
            require(
                cap <= wire and (not snap or cap <= snap) and 28 + ((cap + 3) // 4) * 4 <= size - 4,
                "NG_PACKET_SIZE",
            )
            ticks = ((hi << 32) | lo) * NS
            require(ticks % den == 0, "SUB_NANOSECOND_CLOCK")
            i += 1
            yield i, ticks // den + off * NS, wire, b[28 : 28 + cap]
        elif kind == 3:
            raise ValueError("UNTIMED_PACKET")
    require(i == spec["complete_packets"], "COMPLETE_PACKET_COUNT")


def frames(path, spec):
    with path.open("rb") as f:
        magic = f.read(4)
        f.seek(0)
        require((magic == SHB) == (spec["container"] == "pcapng"), "CONTAINER_IDENTITY")
        yield from (pcapng(f, spec) if magic == SHB else classic(f, spec))


@dataclass(slots=True)
class Header:
    proto: int
    src: int
    sport: int
    dst: int
    dport: int
    iplen: int
    ihl: int
    ds: int
    ipflags: int
    ttl: int
    flags: int
    window: int
    seq: int
    ack: int
    urg: int
    l4len: int
    data: int
    sender: str
    pkttype: int

    @property
    def key(self):
        return self.proto, self.src, self.sport, self.dst, self.dport

    @property
    def off(self):
        return self.proto != 6 or not (self.flags & 2 and not self.flags & 16)

    def fields(self, frame, ts, wire, cap):
        row = {
            "frame.number": str(frame),
            "frame.time_epoch": ns_text(ts),
            "frame.len": str(wire),
            "frame.cap_len": str(cap),
            "ip.src": iptext(self.src),
            "ip.dst": iptext(self.dst),
            "ip.version": "4",
            "ip.proto": str(self.proto),
            "ip.hdr_len": str(self.ihl),
            "ip.dsfield": str(self.ds),
            "ip.len": str(self.iplen),
            "ip.flags": str(self.ipflags),
            "ip.ttl": str(self.ttl),
        }
        if self.proto == 6:
            row.update(
                {
                    "tcp.srcport": str(self.sport),
                    "tcp.dstport": str(self.dport),
                    "tcp.flags": str(self.flags),
                    "tcp.window_size_value": str(self.window),
                    "tcp.seq_raw": str(self.seq),
                    "tcp.ack_raw": str(self.ack),
                    "tcp.urgent_pointer": str(self.urg),
                    "tcp.hdr_len": str(self.l4len),
                }
            )
        else:
            row.update(
                {
                    "udp.srcport": str(self.sport),
                    "udp.dstport": str(self.dport),
                    "udp.length": str(self.l4len),
                }
            )
        return row


def decode(raw):
    if len(raw) < 16:
        return None
    ptype, hatype, halen = struct.unpack_from("!HHH", raw)
    sender = raw[6:12].hex(":") if hatype == 1 and halen == 6 else ""
    etype = struct.unpack_from("!H", raw, 14)[0]
    p = 16
    while etype in (0x8100, 0x88A8):
        if len(raw) < p + 4:
            return None
        etype = struct.unpack_from("!H", raw, p + 2)[0]
        p += 4
    if etype != 0x800 or len(raw) < p + 20 or raw[p] >> 4 != 4:
        return None
    ihl = (raw[p] & 15) * 4
    iplen = struct.unpack_from("!H", raw, p + 2)[0]
    frag = struct.unpack_from("!H", raw, p + 6)[0]
    proto = raw[p + 9]
    o = p + ihl
    if (
        proto not in (6, 17)
        or ihl < 20
        or frag & 0x3FFF
        or iplen < ihl + (20 if proto == 6 else 8)
        or len(raw) < p + iplen
    ):
        return None
    src, dst = struct.unpack_from("!II", raw, p + 12)
    sp, dp = struct.unpack_from("!HH", raw, o)
    flags = win = seq = ack = urg = 0
    if proto == 6:
        th = (raw[o + 12] >> 4) * 4
        if th < 20 or th > iplen - ihl:
            return None
        flags = struct.unpack_from("!H", raw, o + 12)[0] & 0x1FF
        seq, ack = struct.unpack_from("!II", raw, o + 4)
        win = struct.unpack_from("!H", raw, o + 14)[0]
        urg = struct.unpack_from("!H", raw, o + 18)[0]
        data = iplen - ihl - th
    else:
        th = struct.unpack_from("!H", raw, o + 4)[0]
        if th < 8 or th > iplen - ihl:
            return None
        data = th - 8
    return Header(
        proto,
        src,
        sp,
        dst,
        dp,
        iplen,
        ihl,
        raw[p + 1],
        frag >> 13,
        raw[p + 8],
        flags,
        win,
        seq,
        ack,
        urg,
        th,
        data,
        sender,
        ptype,
    )
