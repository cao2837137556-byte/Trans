"""Seal original-frame endpoints and header-only snapshots; the encoder reads only this seal."""

from collections import Counter, defaultdict
import json
import sqlite3
import struct
from types import SimpleNamespace
import zlib


from admission import label_index, layers, match, rawip
from capture import iptext
from common_ton import HERE, LAYERS, NS, POOLS, digest, read, require, uid_hash
from wire import integer, stream

PART = "EXTERNAL_ARCHIVAL_EVALUATION"


class NumericSink:
    """Keep the frozen admission ledgers, defer numeric RECENT replay per component."""

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return self

    def append(self, row):
        pass

    def pop(self, key, default=None):
        return default


class EventAPI:
    @staticmethod
    def event_from_tshark(row):
        proto = int(row.get("ip.proto") or 0)
        transport = "tcp" if proto == 6 else "udp"
        return SimpleNamespace(
            timestamp=float(row["frame.time_epoch"]),
            frame_len=int(row["frame.len"]),
            ip_version=4 if row.get("ip.src") else 0,
            ip_proto=proto,
            src=row.get("ip.src", ""),
            dst=row.get("ip.dst", ""),
            src_port=int(row.get(transport + ".srcport") or 0),
            dst_port=int(row.get(transport + ".dstport") or 0),
        )


def owner_fields(row, registry):
    for ip_side, owner_side in (("ip.src", "ton.owner.src"), ("ip.dst", "ton.owner.dst")):
        row[owner_side] = registry.get(row.get(ip_side, ""), "")
    return row


def new_context(role, owners, numeric):
    from ton_recent import Contexts

    ctx = Contexts(role, owners, EventAPI, max_states=4_000_000, required_owners=owners)
    if not numeric:
        ctx.states = NumericSink()
    return ctx


def db_create(path):
    require(not path.exists(), "NEW_SPOOL_REQUIRED")
    db = sqlite3.connect(path)
    db.executescript("""
      PRAGMA journal_mode=DELETE; PRAGMA synchronous=NORMAL;
      CREATE TABLE event(role TEXT,frame INTEGER,ts INTEGER,owner TEXT,comp TEXT,body BLOB,PRIMARY KEY(role,frame));
      CREATE TABLE point(role TEXT,frame INTEGER,ts INTEGER,host TEXT,owner TEXT,proto INTEGER,comp TEXT,
         uid TEXT UNIQUE,kind TEXT,conn TEXT,off INTEGER,data INTEGER,crossing INTEGER,ctx BLOB,
         selected INTEGER,oracle TEXT,PRIMARY KEY(role,frame));
      CREATE TABLE feature(uid TEXT PRIMARY KEY,shape TEXT,example BLOB,q BLOB);
      CREATE TABLE components(comp TEXT PRIMARY KEY,keyjson TEXT);
      CREATE TABLE batch(batch INTEGER,slot INTEGER,uid TEXT UNIQUE,PRIMARY KEY(batch,slot));
    """)
    return db


def meta(cfg, role, frame, ts, owner, host, proto, key, kind, cutframe=None, cutns=None):
    source = cfg["sources"][role]["sha256"]
    row = dict(
        uid=digest([source, frame, owner]),
        frame=frame,
        timestamp=ts / NS,
        timestamp_ns=ts,
        owner=owner,
        device=host,
        partition=PART,
        protocol=proto,
        capture_id=role,
        source_sha256=source,
        canonical_key=key,
        session_id=digest([owner, role, key]),
        component_id=digest([owner, key]),
        label=int(kind == "attack"),
        use="REFERENCE" if kind == "reference" else "QUERY",
        activity="UNKNOWN",
        activity_verified=False,
    )
    if kind == "reference":
        row.update(reference_end=cutns / NS, bank_end_frame=cutframe)
    return row


def q_context_event(h, owners):
    if not h or h.dst == h.src or h.dst not in owners:
        return None
    return (
        owners[h.dst],
        h.proto,
        h.iplen,
        h.src,
        struct.pack("!BIIHH", h.proto, h.src, h.dst, h.sport, h.dport),
    )


def pilot_selected(count):
    return count <= 6 or count in (16, 32, 128, 512, 2048)


def bind_direction(row, h, registry):
    # Only endpoint identity uses the logical IP-to-role binding. No Ethernet fields are written.
    owner_fields(row, registry)
    p = row.get("ip.proto")
    if row.get("ip.frag_offset", "") not in ("", "0") or (
        row.get("ip.flags") and integer(row["ip.flags"]) & 1
    ):
        row["ton.owner.src"] = row["ton.owner.dst"] = ""
    side = "tcp" if p == "6" else "udp"
    if p in ("6", "17") and not (row.get(side + ".srcport") and row.get(side + ".dstport")):
        row["ton.owner.src"] = row["ton.owner.dst"] = ""
    if h and h.src == h.dst:
        row["ton.owner.src"] = row["ton.owner.dst"] = ""
    return row


def collect(db, paths, cfg, card, folder, exe, pilot, progress):
    from vendor.stream_core import Engine
    import ton_recent

    evidence = read(HERE / "LOCAL_CENSUS.json")
    windows, valid, last_deadline, _ = label_index(paths, cfg)
    registry = {h: v["owner"] for h, v in card["hosts"].items()}
    reverse = {v: k for k, v in registry.items()}
    num = {rawip(ip): owner for ip, owner in registry.items()}
    tested = {(rawip(ip), p) for ip, v in card["hosts"].items() for p in v["tested_protocols"]}
    stats = defaultdict(Counter)
    connsets = defaultdict(set)
    sample = Counter()
    cuts = {}
    normal_streams = set()
    sample_oracles = 0
    decoded = 0
    seen_components = set()
    limits = {k: cfg["sources"][k]["complete_packets"] for k in POOLS}
    if pilot:
        limits = {
            k: max(
                30000,
                max(x[k]["probe_frames"].get("query6", 1) for x in evidence["identity_evidence"].values())
                + 15000,
            )
            for k in POOLS
        }
    groups = [["normal1"], ["normal2"], ["password"]] if pilot else [["normal1", "normal2"], ["password"]]
    for series in groups:
        current_role = None
        for role, frame, ts, wire, cap, row, h in stream(
            series, paths, cfg, card, exe, folder / ("wire_" + series[0]), limits
        ):
            if role != current_role:
                ctx = new_context(role, set(registry.values()), pilot)
                if pilot:
                    ind = new_context(role, set(registry.values()), True)
                    other_engine = Engine()
                engine = Engine()
                current_role = role
            decoded += 1
            ce = q_context_event(h, num)
            clock = engine.advance(frame, ts, role, ce)
            if role == "normal1":
                for host, v in card["hosts"].items():
                    end = v["window_end_ns"]
                    if end is not None and clock <= end:
                        cuts[host] = frame
            if row is None:
                require(ctx.frame + 1 == frame, "OUTSIDE_ORIGINAL_FRAME_ORDER")
                ctx.frame, ctx.previous_ns = frame, ts
                if pilot:
                    ind.frame, ind.previous_ns = frame, ts
                    other_engine.advance(frame, ts, role, None)
                continue
            row = bind_direction(row, h, registry)
            owner, namespace, event = ctx.append(row)
            if pilot:
                independently = h.fields(frame, ts, wire, cap) if h else dict(row)
                bind_direction(independently, h, registry)
                alt, ans, _ = ind.append(independently)
                x = None
                if h and row["ip.dst"] in registry and row["ip.src"] != row["ip.dst"]:
                    p = int(row["ip.proto"])
                    s = rawip(row["ip.src"])
                    t = rawip(row["ip.dst"])
                    side = "tcp" if p == 6 else "udp"
                    x = (
                        registry[row["ip.dst"]],
                        p,
                        int(row["ip.len"]),
                        s,
                        struct.pack(
                            "!BIIHH", p, s, t, int(row[side + ".srcport"]), int(row[side + ".dstport"])
                        ),
                    )
                other_engine.advance(frame, ts, role, x)
                require(
                    (owner, namespace, ctx.query_allowed) == (alt, ans, ind.query_allowed),
                    "SLL_NATIVE_TSHARK_OWNER_OR_ADMISSION",
                )
            kind = None
            conn = ""
            cross = 0
            pair = (h.dst, h.proto) if h else None
            l4stream = None
            if h and role != "password":
                side = "tcp" if h.proto == 6 else "udp"
                number = row.get(side + ".stream", "")
                if number != "":
                    l4stream = side + "-" + number
                    if role == "normal1":
                        normal_streams.add(l4stream)
            if h and role == "password" and pair in tested:
                line = match(h.key, ts, windows, valid)
                if line is not None:
                    kind = "attack"
                    conn = valid[line]
            elif h and role == "normal2" and pair in tested:
                kind = "normal"
                require(l4stream is not None, "NORMAL_TRANSPORT_STREAM_BINDING")
                conn = l4stream
                cross = int(not pilot and conn in normal_streams)
            elif h and role == "normal1" and owner is not None:
                host = reverse[owner]
                start = card["hosts"][host]["window_start_ns"]
                end = card["hosts"][host]["window_end_ns"]
                if start is not None and start <= ts and clock <= end:
                    kind = "reference"
            if kind in ("attack", "normal"):
                host = iptext(h.dst)
                for j in layers(h):
                    tag = (host, kind, LAYERS[j])
                    stats[tag]["candidate"] += 1
                    connsets[tag + ("candidate",)].add(conn)
                    if owner != registry[host] or not ctx.query_allowed:
                        reason = "SELF_OR_MULTIPLE_OWNER" if owner is None else ctx.query_reason
                        stats[tag]["excluded_" + reason] += 1
                    else:
                        stats[tag]["included"] += 1
                        connsets[tag + ("included",)].add(conn)
            if not owner or ctx.query_reason not in ("VALID", "PAYLOAD_TRUNCATED_QUERY"):
                continue
            host = reverse[owner]
            key = namespace[-1]
            component = digest([owner, key])
            if component not in seen_components:
                db.execute(
                    "INSERT INTO components VALUES(?,?)", (component, json.dumps(key, separators=(",", ":")))
                )
                seen_components.add(component)
            require(row["ton.owner.src"] != row["ton.owner.dst"], "UNIQUE_IP_OWNER_DIRECTION")
            fields = {k: row.get(k, "") for k in ton_recent.FIELDS}
            if any(x["kind"] == "MISSING_HEADER_TAINT_RESET" for x in ctx.events):
                fields["_fresh_after_taint"] = True
            body = zlib.compress(json.dumps(fields, separators=(",", ":")).encode(), 1)
            db.execute("INSERT INTO event VALUES(?,?,?,?,?,?)", (role, frame, ts, owner, component, body))
            if kind and ctx.query_allowed and h and (kind == "reference" or host == iptext(h.dst)):
                group = role, host, h.proto, h.off, h.data > 0
                sample[group] += 1
                if not pilot or pilot_selected(sample[group]):
                    uid = digest([cfg["sources"][role]["sha256"], frame, owner])
                    xc = engine.features(owner, h.proto)
                    oracle = ""
                    if pilot:
                        sa, sb = ctx.states[namespace].snapshot(), ind.states[namespace].snapshot()
                        require(
                            sa == sb and xc == other_engine.features(owner, h.proto),
                            "INDEPENDENT_SAME_L3_RECENT_Q14_CONTEXT",
                        )
                        oracle = digest(sa)
                        sample_oracles += 1
                    db.execute(
                        "INSERT INTO point VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            role,
                            frame,
                            ts,
                            host,
                            owner,
                            h.proto,
                            component,
                            uid,
                            kind,
                            conn,
                            int(h.off),
                            int(h.data > 0),
                            cross,
                            struct.pack("<8d", *xc),
                            int(kind != "reference"),
                            oracle,
                        ),
                    )
            if frame % 65536 == 0:
                db.commit()
                progress(
                    "DECODE_AND_BIND",
                    decoded,
                    sum(limits.values()),
                    description="按原始帧序核对方向和设备入站状态",
                )
        db.commit()
    if not pilot:
        for g in evidence["groups"]:
            for label, kind in [("attack_counts", "attack"), ("normal2", "normal")]:
                for j, l in enumerate(LAYERS):
                    require(
                        stats[g["host"], kind, l]["candidate"] == g[label][j],
                        "FULL_PER_TARGET_CANDIDATE_CENSUS",
                    )
                    if kind == "attack":
                        require(
                            len(connsets[g["host"], kind, l, "candidate"]) == g["attack_connections"][j],
                            "PASSWORD_CONNECTION_DENOMINATOR",
                        )
        require(ts >= last_deadline, "LAST_COMPLETE_ATTACK_HORIZON")
    report = []
    for tag, v in sorted(stats.items()):
        excludes = sum(n for k, n in v.items() if k.startswith("excluded_"))
        require(v["candidate"] == v["included"] + excludes, "ELIGIBILITY_ACCOUNTING")
        report.append(
            dict(
                host=tag[0],
                kind=tag[1],
                layer=tag[2],
                **v,
                candidate_connections=len(connsets[tag + ("candidate",)]),
                included_connections=len(connsets[tag + ("included",)]),
            )
        )
    return dict(
        counts=report,
        cut_frames=cuts,
        decoded_frames=decoded,
        independent_snapshots=sample_oracles,
        normal_stream_policy="Wireshark transport streams on append-order normal_1 + normal_2; v12 feature state resets at each source file.",
    )


def reference_selection(db, cfg, card, cuts, pilot):
    from constrained_onboarding_reference_v2 import VERSION, plan_banks
    from onboarding_dense_reference_v1 import plan_dense_positions

    info = {}
    for host, spec in card["hosts"].items():
        if spec["window_start_ns"] is None or host not in cuts:
            info[host] = dict(ready=False, reason="NO_7200S_SAME_TARGET_NORMAL_WINDOW")
            continue
        start, stop = spec["window_start_ns"] / NS, spec["window_end_ns"] / NS
        candidates = []
        latest = {}
        sql = """SELECT p.frame,p.ts,p.owner,p.proto,c.keyjson FROM point p JOIN components c USING(comp)
               WHERE p.kind='reference' AND p.host=? ORDER BY p.frame"""
        for frame, ts, owner, proto, keytext in db.execute(sql, (host,)):
            key = json.loads(keytext)
            r = meta(
                cfg,
                "normal1",
                frame,
                ts,
                owner,
                host,
                proto,
                key,
                "reference",
                cuts[host],
                spec["window_end_ns"],
            )
            candidates.append(r)
            prev = latest.get(r["component_id"])
            if prev is None or (r["timestamp"], frame, r["uid"]) > (
                prev["timestamp"],
                prev["frame"],
                prev["uid"],
            ):
                latest[r["component_id"]] = r
        if not candidates:
            info[host] = dict(ready=False, reason="NO_ELIGIBLE_NORMAL_REFERENCE")
            continue
        ordered = sorted(latest.values(), key=lambda r: (r["device"], r["protocol"], r["component_id"]))
        window = dict(
            partition=PART,
            device=host,
            capture_id="normal1",
            source_sha256=cfg["sources"]["normal1"]["sha256"],
            start=start,
            end=stop,
            reference_end=stop,
            frame_end=cuts[host],
        )
        census = dict(
            generator_version=VERSION,
            status="COMPLETE",
            enumeration="ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT",
            window_closed=True,
            duration_seconds=7200,
            t0=start,
            cutoff=start + 7200,
            candidate_rows=len(ordered),
            candidates_sha256=digest(ordered),
            decoder_identity={"reader": "frozen_RECENT_SLL"},
            source_sha256=window["source_sha256"],
            normality_evidence="Publisher normal_1; verified target time coverage",
            device_registry=[dict(device=host, owner=spec["owner"], partition=PART)],
            capture_id="normal1",
            cutoff_frame=cuts[host],
        )
        if pilot:
            selected = [r["uid"] for r in candidates]
        else:
            sparse = plan_banks(ordered, census, t0=start, policy="B2")
            anchors = {r["uid"] for r in sparse["rows"]}
            dense = plan_dense_positions(candidates, [window], encoded_uids=anchors, mandatory_uids=anchors)
            selected = dense["selected_uids"]
        db.executemany("UPDATE point SET selected=1 WHERE uid=?", ((u,) for u in selected))
        keep = set(selected)
        protocols = {
            str(proto): dict(
                rows=sum(r["protocol"] == proto and r["uid"] in keep for r in candidates),
                components=len(
                    {r["component_id"] for r in candidates if r["protocol"] == proto and r["uid"] in keep}
                ),
            )
            for proto in (6, 17)
        }
        info[host] = dict(
            ready=True,
            window=window,
            candidates=len(candidates),
            selected=len(selected),
            protocols=protocols,
            ordered_roster_sha256=uid_hash(sorted(selected)),
            history_rows=0,
            engineering_slice=pilot,
        )
    db.commit()
    return info
