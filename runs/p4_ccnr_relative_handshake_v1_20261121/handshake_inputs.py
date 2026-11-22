"""Read causal handshake histories at the original query and bank frames."""
from collections import defaultdict
import ipaddress
from itertools import islice
from pathlib import Path

import numpy as np

from history_common import WINDOW, check, progress, read, uid_sha
from history_stream import History, decode, records
from role_inputs import npz, physical_anchor
from roles import attribution

MISSING = -1
UDP = -2


def accepted_parent(project, pool, data, pins):
    from paired_history import correct, severity

    previous = project / "runs" / pins["run"]
    check(previous / "PACKAGE_MANIFEST.json", {"sha256": pins["manifest"]}) if (
        previous / "PACKAGE_MANIFEST.json").is_file() else check(
        previous / "package/PACKAGE_MANIFEST.json", {"sha256": pins["manifest"]})
    bundle = pins["pools"][pool]
    role = npz(check(previous / bundle["roles"]["file"], bundle["roles"]))
    decisions = npz(check(previous / bundle["decisions"]["file"], bundle["decisions"]))
    a = data["a"]
    ref_uid = [r["uid"] for r in data["refs"]]
    assert np.array_equal(role["query_uid"], a["uid"])
    assert np.array_equal(decisions["uid"], a["uid"])
    assert np.array_equal(role["ref_uid"], ref_uid)
    assert np.array_equal(decisions["reference_uid"], ref_uid)
    assert role["query"].shape == (len(a["uid"]), 3)
    assert role["ref"].shape == (len(ref_uid), 3)
    assert np.array_equal(role["query"][:, 0] == 3, a["proto"] == 17)
    assert np.array_equal(role["ref"][:, 0] == 3, [r["protocol"] == 17 for r in data["refs"]])
    s = decisions["U1_support"][0]
    assert np.isfinite(s).all() and ((s >= 0.) & (s <= a["support"])).all()
    p = read(previous / "ACCEPTANCE.json")
    assert p["status"] == "PASS" and p["manifest_sha256"] == pins["manifest"]
    cfg = pins["score"]
    r1 = correct(a["v12"], severity(dict(support=s, guard=a["guard"])),
                 np.array(cfg["scales"]), .25, np.array(cfg["cuts"]))
    assert np.array_equal(r1, decisions["R1_U1"]), "PARENT_R1_ROW_PARITY"
    return role, decisions


def scan(spec, targets, tick, audit_controls=False):
    source = Path(spec["path"])
    if not source.is_file():
        return {}, dict(status="missing_capture", assigned=0, requested=len(targets),
                        raw_sha256=spec["pin"]["sha256"], samples=[])
    check(source, spec["pin"])
    by_frame = defaultdict(list)
    for point in targets:
        assert int(point["frame"]) > 0
        by_frame[point["frame"]].append(point)
    owners = {point["owner"] for point in targets}
    cooked = spec.get("cooked")
    chosen = max(by_frame)
    boundaries = set(spec.get("edges", ()))
    stage = History()
    first = None
    evidence = {}
    samples = {}
    frame = 0
    for frame, ts, raw in islice(records(source, cooked), chosen):
        if frame in boundaries:
            stage = History()
            first = None
        stage.advance(ts)
        if first is None:
            first = stage.clock
        p = decode(raw, cooked is not None)
        directions = {}
        if p:
            ends = (p.macs if cooked is None else
                    tuple(str(ipaddress.IPv4Address(e[0])) for e in p.endpoints))
            if ends[0] != ends[1]:
                for side, owner in enumerate(ends):
                    if owner in owners:
                        directions[owner] = side == 1
                        stage.observe(owner, p, side == 1)
        for point in by_frame.get(frame, ()):
            attribution(point, p, ts, directions)
            owner = point["owner"]
            inbound = directions[owner]
            h = UDP
            clock = stage.clock
            if p.proto == 6:
                oriented = p.endpoints if inbound else p.endpoints[::-1]
                g = stage.group(owner, oriented)
                h = stage.handshakes[g]
                assert 0 <= h <= stage.active_count[g]
                if inbound:
                    assert h == stage.value(owner, p, True)[1]
            label = point["roster"], inbound, p.proto, h > 0
            if audit_controls and label not in samples:
                samples[label] = dict(roster=point["roster"], uid=point["uid"], raw_frame=frame,
                                      protocol=p.proto, inbound=inbound, count=h,
                                      clock_ns=clock, prefix_ns=clock-first, real=True)
            key = point["roster"], point["uid"]
            assert key not in evidence
            evidence[key] = h, int(inbound), int(clock-first < WINDOW), clock
        if frame % 250000 == 0:
            tick(frame, chosen)
    assert frame == chosen and len(evidence) == len(targets), ("RAW_FRAME_BIND", frame, chosen)
    return evidence, dict(status="PASS", assigned=len(evidence), requested=len(targets),
                          frames=frame, raw_sha256=spec["pin"]["sha256"],
                          roster_uid_sha256=uid_sha(p["uid"] for p in targets), samples=list(samples.values()))


def rebuild(out, phase, pool, data):
    by_capture = defaultdict(list)
    rosters = {"query": data["rows"], "reference": data["refs"]}
    unresolved = []
    for roster, items in rosters.items():
        for row in items:
            cap, point = physical_anchor(row, roster, pool, data["inputs"])
            if cap not in data["inputs"]:
                unresolved.append((roster, row["uid"], cap))
                continue
            by_capture[cap].append(point)
    proof = {}
    found = {}
    for j, (cap, targets) in enumerate(by_capture.items(), 1):
        def tick(frame, total):
            progress(out, phase, "按原始帧重建 60 秒握手基线", source=j, sources=len(by_capture),
                     frame=frame, last_frame=total)

        tick(0, max(p["frame"] for p in targets))
        m, cert = scan(data["inputs"][cap], targets, tick, audit_controls=True)
        assert not (m.keys() & found.keys())
        found.update(m)
        proof[cap] = cert
    arrays = {}
    for roster, rows in rosters.items():
        missing = lambda r: (UDP if r["protocol"] == 17 else MISSING, -1, -1, -1)
        arrays[roster] = np.array([found.get((roster, r["uid"]), missing(r)) for r in rows], dtype=np.int64)
    q = arrays["query"]
    a = data["a"]
    bound = q[:, 1] >= 0
    inbound_tcp = bound & a["inbound"] & (a["proto"] == 6)
    assert np.array_equal(q[bound, 1], a["inbound"][bound]), "HISTORY_DIRECTION_PARITY"
    assert np.array_equal(q[bound, 3], a["clock"][bound]), "HISTORY_CLOCK_PARITY"
    assert np.array_equal(q[inbound_tcp, 0], a["handshake"][inbound_tcp]), "HISTORY_HANDSHAKE_PARITY"
    missing = dict(unregistered_anchors=len(unresolved), missing_capture_rows=sum(
        r["requested"] for r in proof.values() if r["status"] == "missing_capture"))
    return arrays, dict(captures=proof, unsupported=missing, identical_inbound_tcp=int(inbound_tcp.sum()),
                        identical_query_direction_and_clock=int(bound.sum()))
