"""Read original frame prefixes and anchor role at the initial SYN of each observed lifetime."""
from collections import Counter, defaultdict
from dataclasses import dataclass
from itertools import islice
from pathlib import Path
import ipaddress
import time

import numpy as np

from history_common import check, uid_sha
from history_stream import decode, records, timestamp_ok

UNKNOWN, RESPONDER, CLIENT, UDP = range(4)
NAMES = ("unknown", "service", "client", "UDP")


@dataclass(slots=True)
class Lifetime:
    origin: tuple
    isn: int
    first_frame: int
    replied: bool = False
    closed: bool = False
    fins: int = 0


class PrefixRoles:
    def __init__(self):
        self.active = {}
        self.counts = Counter()

    def observe(self, owner, packet, direction, frame):
        if packet.proto != 6:
            return UDP, -1, 0
        src, dst = packet.endpoints
        key = owner, min(src, dst), max(src, dst)
        life = self.active.get(key)
        if packet.syn:
            same = life is not None and life.origin == src and life.isn == packet.seq
            both_open = life is not None and not life.closed and life.origin != src and not life.replied
            if both_open:
                self.counts["opposite_open_before_reply"] += 1
            elif life is None or life.closed or not same:
                self.counts["new_initial_syn"] += 1
                life = self.active[key] = Lifetime(src, packet.seq, frame)
            else:
                self.counts["syn_retransmissions"] += 1
        if life is None:
            return UNKNOWN, -1, 0
        if frame > life.first_frame and not packet.syn:
            life.replied |= bool(packet.flags & 16)
        if packet.flags & 1:
            life.fins |= 1 if src == life.origin else 2
        if packet.flags & 4 or life.fins == 3:
            life.closed = True
        protected = dst if direction else src
        service = dst if life.origin == src else src
        role = CLIENT if protected == life.origin else RESPONDER
        return role, service[1], life.first_frame


def attribution(anchor, packet, timestamp, directions):
    owner=anchor["owner"]
    assert packet is not None and owner in directions and packet.proto==anchor["protocol"], ("RAW_OWNER_PROTOCOL", anchor["uid"],anchor["frame"])
    assert timestamp_ok(anchor,timestamp), ("RAW_TIMESTAMP",anchor["uid"],anchor["frame"],timestamp,anchor.get("timestamp_ns",anchor.get("timestamp")))
    if "guard" in anchor:
        assert bool(anchor["guard"]) == (packet.proto==6 and packet.syn), ("RAW_SYN_PARITY",anchor["uid"])
    if anchor.get("expect_inbound"):
        assert directions[owner]
    if "sport" in anchor:
        assert anchor["sport"] == packet.endpoints[0][1]


def scan(spec, points, tick, audit_controls=False):
    path=check(Path(spec["path"]), spec["pin"])
    cooked=spec.get("cooked")
    wanted=defaultdict(list)
    for point in points:
        wanted[point["frame"]].append(point)
    owners={r["owner"] for r in points}
    last=max(wanted)
    reset=set(spec.get("edges",()))
    evidence={}
    samples={}
    begin=time.monotonic()
    stage=PrefixRoles()
    counts=Counter()
    for frame,ts,raw in islice(records(path,cooked),last):
        if frame in reset:
            counts.update(stage.counts)
            stage=PrefixRoles()
        pkt=decode(raw,cooked is not None)
        sides={}
        roles={}
        if pkt:
            ends=pkt.macs if cooked is None else tuple(str(ipaddress.IPv4Address(p[0])) for p in pkt.endpoints)
            if ends[0]!=ends[1]:
                for i,owner in enumerate(ends):
                    if owner not in owners:
                        continue
                    inbound=i==1
                    sides[owner]=inbound
                    roles[owner]=stage.observe(owner,pkt,inbound,frame)
        for p in wanted.get(frame,()):
            attribution(p,pkt,ts,sides)
            role, port, syn = roles[p["owner"]]
            assert (role in (UNKNOWN,UDP) and syn==0 and port==-1) or (0<syn<=frame and 0<=port<=65535)
            evidence[(p["roster"],p["uid"])]=(role,port,syn)
            label=(p["roster"],NAMES[role])
            if audit_controls and label not in samples:
                samples[label]=dict(point=p["uid"],frame=frame,synthetic=False,role=NAMES[role],syn_frame=syn,
                                    service_port=port,original_protocol=pkt.proto,initial_syn_on_current_frame=pkt.syn,
                                    inbound=sides[p["owner"]],sequence=pkt.seq)
        if frame%250000==0:
            tick(frame,last)
    counts.update(stage.counts)
    assert frame==last
    assert len(evidence)==len(points)
    return evidence,dict(rows=len(evidence),frames=last,role_events=dict(counts),
          roster_uid_sha256=uid_sha(r["uid"] for r in points),raw_sha256=spec["pin"]["sha256"],
          elapsed=time.monotonic()-begin,samples=list(samples.values()))


def role_columns(mapping, rows, roster):
    xyz=np.array([mapping[(roster,r["uid"])] for r in rows],dtype=np.int64)
    assert xyz.shape==(len(rows),3)
    return xyz
