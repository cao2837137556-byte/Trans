"""Produce immutable query snapshots and deterministic shape-matched netFound batches on HPC."""

from collections import Counter
import json
import math
import sqlite3
import time
import zlib

import numpy as np

from common_ton import HERE, artifact, digest, dump, read, require, sha, uid_hash
from frontend import db_create, collect, reference_selection, meta


def json_value(v):
    if hasattr(v, "tolist"):
        return v.tolist()
    raise TypeError(type(v).__name__)


def encoder(project, freeze):
    from frozen_env import store
    from reference_features import encoder_config
    from hnr.encoding import new_encoder

    s = store(project, freeze)
    runtime, identity = new_encoder(encoder_config(s))
    return runtime, identity


def reconstructed(db, cfg, card, coverage):
    import ton_recent
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor

    db.executescript("""
      CREATE INDEX event_by_component ON event(role,comp,frame);
      CREATE TEMP TABLE needed AS SELECT DISTINCT role,comp FROM point WHERE selected=1;
      CREATE UNIQUE INDEX needed_id ON needed(role,comp);
    """)
    last = None
    selects = """SELECT e.role,e.frame,e.ts,e.owner,e.comp,e.body,c.keyjson,p.uid,p.host,p.proto,p.kind,p.oracle
      FROM needed g JOIN event e ON e.role=g.role AND e.comp=g.comp JOIN components c ON c.comp=e.comp
      LEFT JOIN point p ON p.role=e.role AND p.frame=e.frame AND p.selected=1
      ORDER BY e.role,e.comp,e.frame"""
    for role, frame, ts, owner, comp, payload, keytext, uid, host, proto, kind, witness in db.execute(
        selects
    ):
        fields = json.loads(zlib.decompress(payload))
        fresh = fields.pop("_fresh_after_taint", False)
        if last != (role, comp) or fresh:
            key = json.loads(keytext)
            namespace = (owner, role, (key[0], tuple(key[1]), tuple(key[2])))
            state = ton_recent.RecentState(owner, namespace, key[0])
            last = (role, comp)
        state.append(fields)
        if uid is None:
            continue
        flow, numeric, provenance = state.snapshot()
        if witness:
            require(witness == digest((flow, numeric, provenance)), "DEFERRED_AND_DIRECT_REAL_SNAPSHOT")
        body = dict(
            flow=flow, state=numeric, provenance=provenance, source_sha256=cfg["sources"][role]["sha256"]
        )
        ref = card["hosts"][host]
        row = meta(
            cfg,
            role,
            frame,
            ts,
            owner,
            host,
            proto,
            key,
            kind,
            coverage["cut_frames"].get(host),
            ref["window_end_ns"],
        )
        require(row["uid"] == uid and row["component_id"] == comp, "SNAPSHOT_QUERY_OR_REFERENCE_UID")
        q, _ = reference_descriptor(body, row) if kind == "reference" else query_descriptor(body, row)
        yield uid, proto, q, flow, provenance, bool(witness)


def snapshots(db, cfg, card, coverage, tokenizer, progress):
    import ton_recent
    from continuous_features_v3 import tokenize

    total = db.execute("SELECT count(*) FROM point WHERE selected=1").fetchone()[0]
    processed = oracle = 0
    for uid, proto, q, flow, provenance, witness in reconstructed(db, cfg, card, coverage):
        oracle += int(witness)
        example = tokenize(tokenizer, flow)
        ton_recent.verify_tokenized(flow, provenance, example)
        shape = "%02d-%04d-%02d" % (
            proto,
            max(example["dataset_burst_sizes"]) + 1,
            len(example["dataset_burst_sizes"]),
        )
        blob = zlib.compress(
            json.dumps(example, separators=(",", ":"), default=json_value, allow_nan=False).encode(), 1
        )
        db.execute("INSERT INTO feature VALUES(?,?,?,?)", (uid, shape, blob, q.astype("<f4").tobytes()))
        processed += 1
        if processed % 512 == 0:
            progress(
                "SEAL_790_INPUTS", processed, total, description="生成并核验冻结通信输入、包属性与设备状态"
            )
    require(total == processed and total > 0, "FEATURE_ROSTER_COVERAGE")
    db.commit()
    return oracle


def roster(db, folder, progress):
    db.execute("CREATE INDEX feature_shape_uid ON feature(shape,uid)")
    groups = Counter()
    batch = 0
    for (shape,) in db.execute("SELECT DISTINCT shape FROM feature ORDER BY shape").fetchall():
        cursor = db.execute("SELECT uid FROM feature WHERE shape=? ORDER BY uid", (shape,))
        while uids := cursor.fetchmany(16):
            db.executemany("INSERT INTO batch VALUES(?,?,?)", ((batch, j, u[0]) for j, u in enumerate(uids)))
            batch += 1
            groups[shape] += 1
    db.execute("CREATE UNIQUE INDEX feature_batch_uid ON batch(uid)")
    db.commit()
    rows = {}
    for kind in ("reference", "normal", "attack"):
        ordered = [
            x[0]
            for x in db.execute(
                "SELECT uid FROM point WHERE kind=? AND selected=1 ORDER BY role,frame", (kind,)
            )
        ]
        rows[kind] = dict(rows=len(ordered), uid_order_sha256=uid_hash(ordered))
    n = sum(x["rows"] for x in rows.values())
    require(db.execute("SELECT count(*) FROM batch").fetchone()[0] == n, "PLANNED_UIDS")
    return dict(populations=rows, rows=n, batches=batch, shape_batches=dict(groups))


def prepare(project, out, folder, paths, cfg, card, freeze, exe, pilot, progress):
    folder.mkdir(parents=True, exist_ok=True)
    dbpath = folder / "snapshots.sqlite"
    start = time.monotonic()
    with db_create(dbpath) as db:
        coverage = collect(db, paths, cfg, card, folder, exe, pilot, progress)
        decode_seconds = time.monotonic() - start
        refs = reference_selection(db, cfg, card, coverage["cut_frames"], pilot)
        dump(folder / "ADMISSION.json", dict(pilot=pilot, **coverage, references=refs))
        enc, enc_id = encoder(project, freeze)
        before = time.monotonic()
        checks = snapshots(db, cfg, card, coverage, enc[3], progress)
        plan = roster(db, folder, progress)
        snapshot_seconds = time.monotonic() - before
        require(not pilot or checks == plan["rows"], "PILOT_ALL_INPUTS_DOUBLE_READ")
    db.close()
    sealed = dict(
        status="SEALED",
        pilot=pilot,
        decoder_frames=coverage["decoded_frames"],
        decode_seconds=decode_seconds,
        snapshot_seconds=snapshot_seconds,
        independent_real_input_checks=checks,
        encoder=enc_id,
        card_sha256=sha(HERE / "DIAGNOSTIC_CARD.json"),
        admission=artifact(folder / "ADMISSION.json"),
        database=artifact(dbpath),
        **plan,
    )
    dump(folder / "INPUT_SEAL.json", sealed)
    return enc, sealed


def open_seal(folder, verify=True):
    seal = read(folder / "INPUT_SEAL.json")
    p = folder / seal["database"]["file"]
    require(
        p.stat().st_size == seal["database"]["bytes"]
        and (not verify or sha(p) == seal["database"]["sha256"]),
        "IMMUTABLE_SNAPSHOT_SEAL",
    )
    db = sqlite3.connect(p.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    return db, seal


def forward_batch(db, bid, runtime):
    from continuous_features_v3 import tensor_hash, verify_batch
    from hnr.encoding import physical_batch

    embed, _, net, _, collator = runtime
    data = db.execute(
        "SELECT f.uid,f.example,f.shape FROM batch b JOIN feature f USING(uid) WHERE b.batch=? ORDER BY b.slot",
        (bid,),
    ).fetchall()
    require(0 < len(data) <= 16 and len({e[2] for e in data}) == 1, "FROZEN_PHYSICAL_BATCH_SHAPE")
    examples = [json.loads(zlib.decompress(e[1])) for e in data]
    b = collator(examples)
    verify_batch(examples, b)
    actual, count = physical_batch(b, len(data), tensor_hash)
    output = embed.core.e3_forward_batches(net, [actual], "cpu")
    require(
        output.dtype == np.float32 and output.shape == (count, 768) and np.isfinite(output).all(),
        "E3_FORWARD",
    )
    if len(data) == 1:
        require(all(np.array_equal(output[0], r) for r in output[1:]), "SINGLETON_CLONE")
    return [e[0] for e in data], output[: len(data)], data[0][2]


def calibrate(folder, runtime, progress):
    db, seal = open_seal(folder)
    timing = {}
    # Use the fullest actual batch per shape; a one-row remainder can be physically padded to 16.
    for shape, n in seal["shape_batches"].items():
        bid = db.execute(
            "SELECT b.batch FROM feature f JOIN batch b USING(uid) WHERE f.shape=? ORDER BY b.batch LIMIT 1",
            (shape,),
        ).fetchone()[0]
        started = time.monotonic()
        ids, _, _ = forward_batch(db, bid, runtime)
        timing[shape] = dict(batch_seconds=time.monotonic() - started, batches=n, logical_rows=len(ids))
        progress(
            "TIME_REAL_SHAPES",
            len(timing),
            len(seal["shape_batches"]),
            description="按实际批形计时并估算正式编码资源",
        )
    db.close()
    estimate = sum(v["batch_seconds"] * v["batches"] for v in timing.values())
    shards = max(1, min(seal["batches"], math.ceil(estimate * 2.5 / 5400)))
    wall = max(3600, math.ceil((estimate * 2.5 / shards + 1200) / 600) * 600)
    plan = dict(
        shards=shards,
        wall_seconds=wall,
        estimated_cpu_worker_seconds=estimate,
        shape_timing=timing,
        parallel_jobs=min(4, shards),
        input_sha256=seal["database"]["sha256"],
    )
    dump(folder / "ENCODING_PLAN.json", plan)
    return plan


def encode_shard(project, folder, freeze, index, shards, progress, runtime=None):
    db, seal = open_seal(folder)
    if runtime is None:
        runtime, _ = encoder(project, freeze)
    destination = folder / "encoded" / f"{index:03d}"
    destination.mkdir(parents=True, exist_ok=True)
    batch_ids = range(index, seal["batches"], shards)
    files = []
    seconds = 0.0
    for offset in range(0, len(batch_ids), 128):
        bids = batch_ids[offset : offset + 128]
        path = destination / f"block-{offset:07d}.npz"
        receipt = path.with_suffix(".json")
        if receipt.is_file():
            saved = read(receipt)
            require(
                saved["input_sha256"] == seal["database"]["sha256"]
                and saved["shards"] == shards
                and saved["batches"] == list(bids)
                and artifact(path) == saved["array"],
                "ENCODER_BLOCK_RESUME_IDENTITY",
            )
        else:
            start = time.monotonic()
            uids = []
            vectors = []
            for bid in bids:
                ids, values, _ = forward_batch(db, bid, runtime)
                uids.extend(ids)
                vectors.append(values)
                progress(
                    "FROZEN_NETFOUND",
                    offset + len(vectors),
                    len(batch_ids),
                    description="运行冻结的 768 维通信编码",
                )
            temp = path.with_suffix(".part")
            with temp.open("wb") as f:
                np.savez(f, uid=np.asarray(uids, dtype="S64"), e3=np.concatenate(vectors))
            temp.replace(path)
            saved = dict(
                input_sha256=seal["database"]["sha256"],
                shards=shards,
                batches=list(bids),
                rows=len(uids),
                seconds=time.monotonic() - start,
                array=artifact(path),
            )
            dump(receipt, saved)
        seconds += saved["seconds"]
        files.append(dict(path=str(path), **saved["array"]))
    db.close()
    result = dict(
        status="PASS",
        index=index,
        shards=shards,
        blocks=files,
        seconds=seconds,
        input_sha256=seal["database"]["sha256"],
    )
    dump(destination / "COMPLETE.json", result)
    return result
