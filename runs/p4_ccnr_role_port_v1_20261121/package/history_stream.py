"""Replay original header order and count eligible inbound TCP tuples at each anchor."""
from collections import Counter, OrderedDict, defaultdict, deque
from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import islice
import ipaddress
import struct
import time

from history_common import WINDOW, check

MAGIC = {
    b"\xd4\xc3\xb2\xa1": ("<", 1000),
    b"\xa1\xb2\xc3\xd4": (">", 1000),
    b"\x4d\x3c\xb2\xa1": ("<", 1),
    b"\xa1\xb2\x3c\x4d": (">", 1),
}
MASK32 = (1 << 32) - 1


@dataclass(slots=True)
class Packet:
    proto: int
    endpoints: tuple
    macs: tuple
    flags: int
    seq: int
    ack: int
    data: int

    @property
    def syn(self):
        return self.flags & 0x12 == 2


def decode(raw, cooked):
    etype_pos = 14 if cooked else 12
    if len(raw) < etype_pos + 2:
        return None
    etype = struct.unpack_from("!H", raw, etype_pos)[0]
    beg = etype_pos + 2
    while etype in (0x8100, 0x88a8):
        if len(raw) < beg + 4:
            return None
        etype = struct.unpack_from("!H", raw, beg + 2)[0]
        beg += 4
    if etype != 0x0800 or len(raw) < beg + 20 or raw[beg] >> 4 != 4:
        return None
    ihl = 4 * (raw[beg] & 15)
    iplen = struct.unpack_from("!H", raw, beg + 2)[0]
    frag = struct.unpack_from("!H", raw, beg + 6)[0]
    proto = raw[beg+9]
    if proto not in (6, 17) or ihl < 20 or frag & 0x3fff or len(raw) < beg + iplen:
        return None
    off = beg + ihl
    if iplen < ihl + (20 if proto == 6 else 8):
        return None
    src, dst = struct.unpack_from("!II", raw, beg + 12)
    sp, dp = struct.unpack_from("!HH", raw, off)
    if proto == 6:
        h = (raw[off+12] >> 4) * 4
        if h < 20 or iplen < ihl + h:
            return None
        flags = struct.unpack_from("!H", raw, off + 12)[0] & 0x1ff
        seq, ack = struct.unpack_from("!II", raw, off + 4)
        data = iplen - ihl - h
    else:
        ulen = struct.unpack_from("!H", raw, off + 4)[0]
        if not 8 <= ulen <= iplen - ihl:
            return None
        flags, seq, ack, data = 0, 0, 0, ulen-8
    macs = () if cooked else (raw[6:12].hex(), raw[:6].hex())
    return Packet(proto, ((src, sp), (dst, dp)), macs, flags, seq, ack, data)


def records(path, cooked_spec=None):
    if cooked_spec is not None:
        from capture import frames
        for frame, timestamp, _, packet in frames(path, cooked_spec):
            yield frame, timestamp, packet
        return
    with path.open("rb") as f:
        hdr = f.read(24)
        if hdr[:4] != b"\x0a\x0d\x0d\x0a":
            order, unit = MAGIC[hdr[:4]]
            assert struct.unpack_from(order + "I", hdr, 20)[0] == 1
            packet = struct.Struct(order+"IIII")
            frame = 0
            while head := f.read(16):
                seconds, sub, captured, wire = packet.unpack(head)
                assert 0 < captured <= wire and captured <= 16 * 1024**2
                raw = f.read(captured)
                assert len(raw) == captured
                frame += 1
                yield frame, seconds*10**9 + sub*unit, raw
            return
    from source_packets import pcapng_records
    yield from pcapng_records(path)


@dataclass(slots=True)
class Connection:
    last: int
    initiator: tuple | None = None
    opening: int = -1
    expected_ack: int = -1
    responder_ack: int = -1
    confirmed: bool = False
    closed: bool = False


class History:
    def __init__(self):
        self.clock = 0
        self.recent = OrderedDict()
        self.connections = OrderedDict()
        self.completed = {}
        self.expirations = []
        self.active_count = Counter()
        self.handshakes = Counter()

    @staticmethod
    def group(owner, endpoints):
        return owner, endpoints[0][0], endpoints[1][1]

    def advance(self, timestamp):
        self.clock = max(timestamp, self.clock)
        lower = self.clock - WINDOW
        while self.recent and next(iter(self.recent.values())) <= lower:
            (owner, endpoints), _ = self.recent.popitem(last=False)
            self.active_count[self.group(owner, endpoints)] -= 1
            if self.active_count[self.group(owner, endpoints)] == 0:
                del self.active_count[self.group(owner, endpoints)]
        while self.connections and next(iter(self.connections.values())).last <= lower:
            self.connections.popitem(last=False)
        while self.expirations and self.expirations[0][0] <= lower:
            born, k = heappop(self.expirations)
            if self.completed.get(k) == born:
                self.uncomplete(k)

    def uncomplete(self, key):
        if key in self.completed:
            del self.completed[key]
            g = self.group(*key)
            self.handshakes[g] -= 1
            if self.handshakes[g] == 0:
                del self.handshakes[g]

    def observe(self, owner, p, inbound):
        if p.proto != 6 or p.endpoints[0] == p.endpoints[1]:
            return
        key = (owner, p.endpoints)
        if inbound:
            if key not in self.recent:
                self.active_count[self.group(*key)] += 1
            self.recent[key] = self.clock
            self.recent.move_to_end(key)
        left, right = p.endpoints
        conn_key = (owner, min(left, right), max(left, right))
        rec = self.connections.get(conn_key)
        if rec is None:
            rec = Connection(self.clock)
            self.connections[conn_key] = rec
        rec.last = self.clock
        self.connections.move_to_end(conn_key)
        if p.syn:
            expect = (p.seq+1) & MASK32
            if rec.closed or rec.initiator != left or rec.expected_ack != expect:
                self.uncomplete((owner, (left, right)))
                self.uncomplete((owner, (right, left)))
                rec.initiator, rec.opening, rec.expected_ack = left, self.clock, expect
                rec.responder_ack, rec.confirmed, rec.closed = -1, False, False
        elif not rec.closed and rec.initiator is not None and not rec.confirmed:
            if p.flags & 0x12 == 0x12 and right == rec.initiator and p.ack == rec.expected_ack:
                rec.responder_ack = (p.seq+1) & MASK32
            if (p.flags & 0x12 == 0x10 and not p.flags & 4 and left == rec.initiator
                    and p.seq == rec.expected_ack and p.ack == rec.responder_ack):
                rec.confirmed = True
                if inbound and rec.opening > self.clock - WINDOW:
                    self.completed[key] = rec.opening
                    self.handshakes[self.group(*key)] += 1
                    heappush(self.expirations, (rec.opening, key))
        if p.flags & 5:
            rec.closed = True

    def value(self, owner, p, inbound):
        left, right = p.endpoints
        rec = self.connections.get((owner, min(left, right), max(left, right))) if p.proto == 6 else None
        role = 0 if rec is None or not rec.confirmed else (1 if rec.initiator == left else 2)
        if p.proto != 6 or not inbound:
            return 0, 0, role
        g = self.group(owner, p.endpoints)
        return self.active_count[g], self.handshakes[g], role


def timestamp_ok(point, ns):
    if point.get("timestamp_ns") is not None:
        return int(point["timestamp_ns"]) == ns
    return abs(float(point["timestamp"])-ns/10**9) <= 1e-6


def trace(path, pin, rows, *, cooked=None, edges=(), expected_owners=(), pilot=False, report=None):
    check(path, pin)
    target = defaultdict(list)
    for row in rows:
        target[row["frame"]].append(row)
    owners = {r["owner"] for r in rows} | set(expected_owners)
    last = max(target)
    begin = time.monotonic()
    state = History()
    answer = {}
    oracle = deque()
    edge = iter(edges)
    boundary = next(edge, 0)
    peak = 0
    for frame, timestamp, raw in islice(records(path, cooked), last):
        if frame == boundary:
            state = History()
            oracle.clear()
            boundary = next(edge, 0)
        state.advance(timestamp)
        p = decode(raw, cooked is not None)
        assigned = {}
        if p:
            if cooked is not None:
                ends = tuple(str(ipaddress.IPv4Address(x[0])) for x in p.endpoints)
            else:
                ends = p.macs
            for i, owner in enumerate(ends):
                if owner in owners and ends[0] != ends[1]:
                    inbound = i == 1
                    assigned[owner] = inbound
                    state.observe(owner, p, inbound)
                    if pilot and inbound and p.proto == 6:
                        oracle.append((state.clock, owner, p.endpoints))
        for row in target.get(frame, ()):
            owner = row["owner"]
            assert p and owner in assigned and p.proto == row["protocol"] and timestamp_ok(row, timestamp), (frame, row["uid"])
            inbound = assigned[owner]
            count, handshakes, role = state.value(owner, p, inbound)
            assert 0 <= handshakes <= count
            if "guard" in row:
                assert bool(row["guard"]) == (p.proto == 6 and p.syn)
            if row.get("expect_inbound"):
                assert inbound, (frame, row["uid"])
                if "data" in row:
                    assert bool(row["data"]) == (p.data > 0), (frame, row["uid"])
            if "sport" in row:
                assert p.endpoints[0][1] == row["sport"]
            if pilot and inbound and p.proto == 6:
                while oracle and oracle[0][0] <= state.clock-WINDOW:
                    oracle.popleft()
                wanted = state.group(owner, p.endpoints)
                brute = {e for _, o, e in oracle if state.group(o, e) == wanted}
                assert count == len(brute)
            answer[row["uid"]] = (count, handshakes, state.clock, inbound, p.proto, p.data, role, *p.endpoints[0], *p.endpoints[1])
        if frame % 200000 == 0:
            peak = max(peak, len(state.recent))
            if report:
                report(frame, last)
    assert frame == last and len(answer) == len(rows)
    return answer, dict(rows=len(rows), frames=last, seconds=time.monotonic()-begin, active_peak_sampled=peak)
