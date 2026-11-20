"""Attach a header-only snapshot observer to the frozen DAD admission replay."""

from collections import Counter, defaultdict
import hashlib
import json
import sqlite3
import zlib

import numpy as np

from dad_stats import require


def uid_hash(values):
    return hashlib.sha256("".join(u + "\n" for u in values).encode()).hexdigest()


def replay_inputs(folder, package, exe, pilot, progress, tokenizer=None):
    import dad_audit as audit
    from continuous_input_v3 import verify_tokenized, digest
    from constrained_onboarding_reference_v2 import query_descriptor, reference_descriptor

    if tokenizer is not None:
        from continuous_features_v3 import tokenize
    truth = json.loads((package / "AUDIT.json").read_bytes())
    cut = truth["commissioning"]
    groups = truth["selected_bank"]["groups"]
    ref_order = [u for g in groups for u in g["selected_uids"]]
    require(uid_hash(ref_order) == truth["selected_bank"]["selected_uid_sha256"], "REFERENCE_SELECTION_ORDER")
    ref_set = set(ref_order)
    groups_seen = defaultdict(list)
    seen = Counter()
    last_ns = {}
    marks = set()
    regression = None
    points = []
    previous_day = None
    db = sqlite3.connect(folder / "examples.sqlite")
    db.executescript(
        "CREATE TABLE feature(uid TEXT PRIMARY KEY, shape TEXT,example BLOB);CREATE TABLE batch(batch INTEGER,slot INTEGER,uid TEXT UNIQUE,PRIMARY KEY(batch,slot));"
    )

    def observe(day, frame, ns, ctx, engine, comp, event, start, cutoff, clock, flag_label, source):
        nonlocal regression, previous_day
        if previous_day != day:
            progress(
                "CAUSAL_REPLAY",
                audit.DAYS.index(day),
                7,
                description="逐帧核对输入与查询顺序 · " + day,
                force=True,
            )
            previous_day = day
        back = day in last_ns and ns < last_ns[day]
        last_ns[day] = ns
        if back and regression is None:
            regression = dict(day=day, frame=frame, raw_ns=ns, prefix_clock_ns=clock)
        if not ctx.query_allowed or comp is None:
            return
        uid = digest([source, frame, audit.OWNER_MAC])
        if uid in ref_set:
            kind = "reference"
            group = "reference_candidates_" + str(comp[0])
        elif event and comp[0] == 6 and day in ("mon", "sun") and (day != "mon" or clock > cutoff):
            kind = "normal"
            group = day + "_normal"
        elif event and comp[0] == 6 and flag_label and day in ("wed", "thu", "fri", "sat"):
            kind = "attack"
            group = day + "_positive"
        else:
            return
        groups_seen[group].append(uid)
        namespace = (audit.OWNER_MAC, day, comp)
        state = ctx.states[namespace]
        # Pilot captures deliberate frames plus positions spread across each daily roster.
        special = (day, frame) in {("mon", 1304), ("mon", 1305), ("mon", 14429), ("wed", 2707), ("thu", 2047)}
        sample = (
            seen[group] < 8 or len(groups_seen[group]) % max(1, truth["rosters"][group]["rows"] // 12) == 0
        )
        if day == "sun" and event and not marks.intersection({"sun_syn"}):
            # The first SYN is located from frozen header attributes, independent of model scores.
            burst = state.snapshot()[2]["bursts"]
            flags = next(h[5] for b in burst for f, h in zip(b["frames"], b["headers"]) if f == frame)
            if flags & 0x12 == 2:
                marks.add("sun_syn")
                special = True
        seen[group] += 1
        if special:
            marks.add(f"{day}:{frame}")
        if pilot and not (special or sample or back):
            return
        flow, numeric, provenance = state.snapshot()
        row = dict(
            uid=uid,
            source_sha256=source,
            frame=frame,
            timestamp=ns / audit.NS,
            capture_id=day,
            partition="EXTERNAL_ARCHIVAL_EVALUATION",
            owner=audit.OWNER_MAC,
            device=audit.BROKER,
            protocol=comp[0],
            canonical_key=comp,
            component_id=digest([audit.OWNER_MAC, comp]),
            session_id=digest(namespace),
            use="REFERENCE" if kind == "reference" else "QUERY",
            label=int(kind == "attack"),
        )
        if kind == "reference":
            row.update(reference_end=cutoff / audit.NS, bank_end_frame=cut["last_reference_frame"])
        body = dict(flow=flow, state=numeric, provenance=provenance, source_sha256=source)
        q, _ = (reference_descriptor if kind == "reference" else query_descriptor)(body, row)
        x = np.asarray(engine.features(audit.OWNER, comp[0]), dtype=np.float64)
        require(x.shape == (8,) and np.isfinite(x).all(), "PHYSICAL_CONTEXT8")
        if tokenizer is not None:
            ex = tokenize(tokenizer, flow)
            verify_tokenized(flow, provenance, ex)
            shape = (
                f"{comp[0]:02d}-{max(ex['dataset_burst_sizes']) + 1:04d}-{len(ex['dataset_burst_sizes']):03d}"
            )
            blob = json.dumps(
                ex, separators=(",", ":"), default=lambda x: x.tolist(), allow_nan=False
            ).encode()
            db.execute("INSERT INTO feature VALUES(?,?,?)", (uid, shape, zlib.compress(blob, 1)))
        points.append((row, q, x))

    observed = audit.audit(package / "raw", str(exe), observer=observe)
    require(
        hashlib.sha256((json.dumps(observed, indent=2) + "\n").encode()).hexdigest()
        == hashlib.sha256((package / "AUDIT.json").read_bytes()).hexdigest(),
        "FULL_FROZEN_DATA_AUDIT",
    )
    require(
        set(groups_seen) == set(truth["rosters"])
        and all(
            len(v) == truth["rosters"][k]["rows"] and uid_hash(v) == truth["rosters"][k]["sha256"]
            for k, v in groups_seen.items()
        ),
        "ALL_UID_ORDERS",
    )
    require(
        {"mon:1304", "mon:1305", "mon:14429", "wed:2707", "thu:2047", "sun_syn"} <= marks
        and regression
        and regression["prefix_clock_ns"] > regression["raw_ns"],
        "MANDATORY_PILOT_WITNESSES",
    )
    # References retain selector order, queries retain original day and frame order.
    loc = {v[0]["uid"]: v for v in points}
    ordered = [loc[u] for u in ref_order if u in loc] + [v for v in points if v[0]["use"] == "QUERY"]
    rows = [r for r, q, x in ordered]
    with (folder / "rows.jsonl").open("w", encoding="utf8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    np.savez(
        folder / "input.npz",
        uid=np.array([r["uid"] for r in rows]),
        q=np.stack([q for r, q, x in ordered]),
        x=np.stack([x for r, q, x in ordered]),
    )
    batches = 0
    if tokenizer is not None:
        db.execute("CREATE INDEX by_shape ON feature(shape,uid)")
        for (shape,) in db.execute("SELECT DISTINCT shape FROM feature ORDER BY shape").fetchall():
            cursor = db.execute("SELECT uid FROM feature WHERE shape=? ORDER BY uid", (shape,))
            while chunk := cursor.fetchmany(16):
                db.executemany(
                    "INSERT INTO batch VALUES(?,?,?)", [(batches, j, u) for j, (u,) in enumerate(chunk)]
                )
                batches += 1
    db.commit()
    db.close()
    nref = sum(r["use"] == "REFERENCE" for r in rows)
    require(
        len(loc) == len(rows) and (pilot or (nref == 1304 and len(rows) - nref == 18317)),
        "SELECTED_UID_COVERAGE",
    )
    return dict(
        references=nref,
        queries=len(rows) - nref,
        batches=batches,
        selected_uid_order=uid_hash([r["uid"] for r in rows]),
        query_orders=truth["rosters"],
        bank_order=uid_hash(ref_order),
        pilot_witnesses=sorted(marks),
        cross_component_regression=regression,
        monday_cut_frame=1304,
        monday_first_query=1305,
        tuesday=dict(
            inbound_tcp=truth["daily"]["tue"]["inbound_tcp"],
            observed_positive=truth["daily"]["tue"]["labels"].get("1", 0),
            evaluation_queries=0,
            recall="不适用",
        ),
    )
