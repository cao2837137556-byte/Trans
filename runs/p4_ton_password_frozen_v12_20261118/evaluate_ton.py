"""Read-only frozen head inference and paired CCNR evaluation, in separate Python processes."""

from collections import defaultdict
import json

import numpy as np

from common_ton import HERE, HEADS, NS, artifact, csv_table, dump, read, require, sha, uid_hash
from frozen_env import store
from representations import open_seal

ORDER = "CASE p.kind WHEN 'reference' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,p.frame"
QUERY = (
    """SELECT p.role,p.frame,p.ts,p.host,p.owner,p.proto,p.comp,p.uid,p.kind,p.conn,p.off,p.data,p.crossing,
                p.ctx,f.q,c.keyjson FROM point p JOIN feature f USING(uid) JOIN components c USING(comp)
                WHERE p.selected=1 ORDER BY """
    + ORDER
)


def check_frozen_head(s, model, method, progress):
    from reference_assets import forward

    path = s.get("CIC_DEV:query_e3")
    z = np.load(path, mmap_mode="r", allow_pickle=False)[:, :768]
    q = np.load(s.get("CIC_DEV:query_q"), mmap_mode="r", allow_pickle=False)
    x = np.load(s.get("CIC_DEV:query_context"), mmap_mode="r", allow_pickle=False)
    with np.load(s.get("CIC_DEV:query_scores"), allow_pickle=False) as old:
        ids = old["uid"].astype("U64")
        raw = old["RAW"][:1024]
    with np.load(s.get("CIC_DEV:query_context_uids"), allow_pickle=False) as meta:
        require(np.array_equal(meta["uid"].astype("U64"), ids), "CIC_CONTROL_FEATURE_UID_ORDER")
    with np.load(s.get("CIC_DEV:query_array"), allow_pickle=False) as a:
        require(np.array_equal(a["uid"], ids) and np.array_equal(a["q"], q), "CIC_CONTROL_Q14")
    ix = np.arange(1024)
    new = forward(model, z[:1024], q[:1024], x[:1024], ix, progress, "ORIGINAL_MLP_WITNESS")
    delta = float(np.max(np.abs(new - raw)))
    require(
        delta <= 2e-4 and np.array_equal(new > method["cuts"], raw > method["cuts"]),
        "FROZEN_QUERY_SCORE_AND_ALARM",
    )
    return dict(
        rows=len(ix),
        uid_order_sha256=uid_hash(ids[:1024].tolist()),
        max_abs_score_error=delta,
        head_decision_differences=[0] * 4,
        heads=list(HEADS),
        source_cuts=method["cuts"],
    )


def score(project, folder, freeze, cfg, progress):
    from reference_assets import model_setup, forward

    s = store(project, freeze)
    model = model_setup(s, cfg)
    proof = check_frozen_head(s, model, cfg["method"], progress)
    db, seal = open_seal(folder)
    n = seal["rows"]
    zpath = folder / "ORDERED_E3.npy"
    z = np.lib.format.open_memmap(zpath, mode="w+", dtype=np.float32, shape=(n, 768))
    q = np.empty((n, 14), dtype=np.float32)
    x = np.empty((n, 8), dtype=np.float64)
    ids = {}
    for i, row in enumerate(db.execute(QUERY)):
        uid = row[7]
        require(uid not in ids, "DUPLICATE_SCORE_UID")
        ids[uid] = i
        q[i] = np.frombuffer(row[14], "<f4")
        x[i] = np.frombuffer(row[13], "<f8")
    db.close()
    require(len(ids) == n, "INPUT_POPULATION_ORDER")
    seen = np.zeros(n, dtype=bool)
    plan = read(folder / "ENCODING_PLAN.json")
    encoded = []
    for i in range(plan["shards"]):
        root = folder / "encoded" / f"{i:03d}"
        rec = read(root / "COMPLETE.json")
        require(
            rec["shards"] == plan["shards"]
            and rec["index"] == i
            and rec["input_sha256"] == seal["database"]["sha256"],
            "SHARD_IDENTITY",
        )
        for pin in rec["blocks"]:
            path = root / pin["file"]
            require(sha(path) == pin["sha256"] and path.stat().st_size == pin["bytes"], "ENCODED_BLOCK_SHA")
            with np.load(path, allow_pickle=False) as f:
                uu = f["uid"].astype("U64").tolist()
                ix = np.asarray([ids[u] for u in uu])
                require(len(set(uu)) == len(ix) and not seen[ix].any(), "ENCODED_UID_DUPLICATE")
                z[ix] = f["e3"]
                seen[ix] = True
        encoded.append(artifact(root / "COMPLETE.json"))
    require(seen.all(), "COMPLETE_ENCODED_UID_COVERAGE")
    z.flush()
    raw = forward(model, z, q, x, np.arange(n), progress, "FROZEN_FUSION790")
    require(raw.shape == (n, 4) and np.isfinite(raw).all(), "FUSION790_OUTPUT")
    np.save(folder / "RAW.npy", raw, allow_pickle=False)
    result = dict(
        status="PASS",
        source_witness=proof,
        population_order_sha256=uid_hash(ids),
        rows=n,
        encoded_shards=encoded,
        ordered_e3=artifact(zpath),
        raw=artifact(folder / "RAW.npy"),
        inputs=s.checked,
    )
    dump(folder / "RAW_PROOF.json", result)
    from report_ton import build_tables

    card = read(HERE / "DIAGNOSTIC_CARD.json")
    admission = read(folder / "ADMISSION.json")
    metadata = defaultdict(list)
    connection, _ = open_seal(folder, verify=False)
    sql = (
        """SELECT p.host,p.uid,p.kind,p.conn,p.off,p.data,p.crossing FROM point p
             WHERE p.selected=1 AND p.kind!='reference' ORDER BY """
        + ORDER
    )
    for host, uid, kind, conn, off, data, cross in connection.execute(sql):
        metadata[host].append(dict(uid=uid, kind=kind, conn=conn, off=off, data=data, crossing=cross))
    connection.close()
    base_rows = []
    for host in card["hosts"]:
        rr = metadata[host]
        ix = np.asarray([ids[row["uid"]] for row in rr], dtype=int)
        rows = build_tables(
            host,
            rr,
            None,
            None,
            raw[ix] > cfg["method"]["cuts"],
            None,
            None,
            None,
            card,
            dict(counts=admission["counts"], cuts=cfg["method"]["cuts"]),
        )
        base_rows.extend(rows["raw"])
    csv_table(folder / "RAW_TARGETS.csv", base_rows)
    raw_receipt = dict(
        status="PASS",
        rows=n,
        source_witness=proof,
        raw_table=artifact(folder / "RAW_TARGETS.csv"),
        uid_order_sha256=result["population_order_sha256"],
    )
    dump(folder / "RAW_INFERENCE.json", raw_receipt)
    if folder.name == "formal":
        import shutil

        for name in ("RAW_TARGETS.csv", "RAW_INFERENCE.json"):
            shutil.copyfile(folder / name, folder.parent / name)
        dump(
            folder.parent / "RETURN.json",
            dict(files={n: artifact(folder.parent / n) for n in ("RAW_TARGETS.csv", "RAW_INFERENCE.json")}),
        )


def evaluate(project, folder, freeze, cfg, geometry, card, progress, pilot):
    from reference_inputs import normalized_context
    from replay_geometry import replay, radii
    from vendor import constrained_onboarding_core_v3 as core, geometry_frozen, p4_worker
    from report_ton import build_tables, aggregate, verify

    db, seal = open_seal(folder)
    sc = read(folder / "RAW_PROOF.json")
    ad = read(folder / "ADMISSION.json")
    for k in ("raw", "ordered_e3"):
        require(artifact(folder / sc[k]["file"]) == sc[k], "FORMAL_SCORE_FEATURE_SHA")
    raw = np.load(folder / "RAW.npy", mmap_mode="r")
    z = np.load(folder / "ORDERED_E3.npy", mmap_mode="r")
    s = store(project, freeze)

    def norm(name):
        with np.load(s.get(name), allow_pickle=False) as a:
            return a["mean"], a["scale"]

    zn = norm("e3_normalizer")
    cn = norm("context_normalizer")
    by_host = defaultdict(list)
    all_ids = []
    for i, row in enumerate(db.execute(QUERY)):
        role, frame, ts, host, owner, proto, component, uid, kind, conn, off, data, cross, ctx, qq, key = row
        meta = dict(
            uid=uid,
            frame=frame,
            timestamp=ts / NS,
            device=host,
            owner=owner,
            protocol=proto,
            component_id=component,
            capture_id=role,
            partition="EXTERNAL_ARCHIVAL_EVALUATION",
            canonical_key=json.loads(key),
            label=int(kind == "attack"),
            use="REFERENCE" if kind == "reference" else "QUERY",
            kind=kind,
            conn=conn,
            off=bool(off),
            data=bool(data),
            crossing=bool(cross),
        )
        if kind == "reference":
            meta.update(
                reference_end=card["hosts"][host]["window_end_ns"] / NS, bank_end_frame=ad["cut_frames"][host]
            )
        by_host[host].append((i, meta, np.frombuffer(qq, "<f4"), np.frombuffer(ctx, "<f8")))
        all_ids.append(uid)
    db.close()
    require(uid_hash(all_ids) == sc["population_order_sha256"], "SCORING_TO_EVALUATION_ORDER")
    buckets = {k: [] for k in ("raw", "main", "supplement", "boundary")}
    oracle_errors = {}
    arrays = {}
    for host in card["hosts"]:
        allrows = by_host[host]
        rr = [r for r in allrows if r[1]["kind"] == "reference"]
        qr = [r for r in allrows if r[1]["kind"] != "reference"]
        rows = [r[1] for r in qr]
        pts = np.asarray([r[0] for r in qr], dtype=int)
        q = np.asarray([r[2] for r in qr], dtype=np.float32).reshape((-1, 14))
        ref_info = ad["references"][host]
        ready_proto = {int(k) for k, v in ref_info.get("protocols", {}).items() if v["components"] >= 2}
        ready = np.array([r["protocol"] in ready_proto for r in rows], bool)
        support = np.zeros(len(rows))
        opened = np.zeros(len(rows), bool)
        peak = 0.0
        if rr and qr:
            refs = [r[1] for r in rr]
            rids = [r["uid"] for r in refs]
            bank = core.ReferenceBank(
                refs,
                z[[r[0] for r in rr]],
                np.stack([r[2] for r in rr]),
                zn,
                feature_uids=rids,
                q_uids=rids,
                allow_prebank_history=True,
            )
            rc = normalized_context(np.stack([r[3] for r in rr]), cn)
            d = dict(rows=rows, z=z[pts], q=q, context=normalized_context(np.stack([r[3] for r in qr]), cn))
            g = replay(d, bank, rc, geometry, progress, "FROZEN_3D_DISTANCE")
            support = g["support3"]
            opened = (g["opening"] == "") & g["geometry_ready"]
            require(
                np.all(support[~ready] == 0) and np.all(support[~opened] == 0), "REFERENCE_GATE_AND_FALLBACK"
            )
            for j in np.unique(
                np.linspace(0, len(rows) - 1, len(rows) if pilot else min(24, len(rows)), dtype=int)
            ):
                r = rows[j]
                legal = []
                dist = 0.0
                if r["timestamp"] > bank.ends.get((r["partition"], host), float("inf")):
                    legal = bank.groups.get((r["partition"], host, r["protocol"]), [])
                if len({refs[i]["component_id"] for i in legal}) >= 2:
                    radii2, rhoc = radii(geometry, r["protocol"])
                    if radii2 and rhoc is not None:
                        zz = core._unit(d["z"][j : j + 1], bank.normalizer)
                        dz = np.clip(1.0 - zz @ bank.z[legal].T, 0.0, 2.0)[0]
                        dq = geometry_frozen.rms(q[j : j + 1], bank.q14[legal])[0]
                        dc = geometry_frozen.rms(d["context"][j : j + 1], rc[legal])[0]
                        all_dist = np.maximum.reduce(
                            (core._ratio(dz, radii2[0]), core._ratio(dq, radii2[1]), core._ratio(dc, rhoc))
                        )
                        minima = {}
                        for k, v in zip(legal, all_dist):
                            c = refs[k]["component_id"]
                            minima[c] = min(minima.get(c, np.inf), v)
                        dist = np.clip(1.0 - sorted(minima.values())[1], 0.0, 1.0)
                peak = max(peak, abs(dist - support[j]))
            require(peak <= 2e-10, "INDEPENDENT_TWO_COMPONENT_GEOMETRY")
        scores = np.asarray(raw[pts])
        method = cfg["method"]
        cuts = method["cuts"]
        base = scores > cuts
        corrected = p4_worker.correct(scores, support, q, method["scales"], True, power=4)
        off = np.asarray([r["off"] for r in rows], bool)
        require(
            np.array_equal(~off, (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0))
            and np.all(corrected <= scores)
            and np.array_equal(corrected[~off], scores[~off]),
            "GUARD_AND_MONOTONE",
        )
        group = build_tables(
            host,
            rows,
            support,
            scores,
            base,
            corrected,
            opened,
            ready,
            card,
            dict(
                counts=ad["counts"],
                cuts=cuts,
                ready=bool(ready_proto.intersection(card["hosts"][host]["tested_protocols"])),
            ),
        )
        # Pilot only scores a deterministic real slice; its full-prefix candidate counts are diagnostic.
        for k, v in group.items():
            buckets[k].extend(v)
        path = folder / (host + "_QUERY_DECISIONS.npz")
        np.savez(
            path,
            uid=np.array([r["uid"] for r in rows], dtype="S64"),
            index=pts,
            support=support,
            opened=opened,
            reference_eligible=ready,
            off_bypass=off,
            transport_data=np.array([r["data"] for r in rows]),
            raw=scores,
            ccnr=corrected,
            raw_alarm=base,
            ccnr_alarm=corrected > cuts,
        )
        arrays[host] = dict(path=str(path), **artifact(path))
        oracle_errors[host] = float(peak)
    for k in ("main", "supplement"):
        buckets[k].extend(aggregate(buckets[k]))
    names = dict(
        raw="RAW_TARGETS.csv",
        main="CCNR_MAIN.csv",
        supplement="CCNR_PAIRED.csv",
        boundary="NORMAL_BOUNDARY.csv",
    )
    for k, name in names.items():
        csv_table(folder / name, buckets[k])
    require(
        artifact(folder / "RAW_TARGETS.csv") == read(folder / "RAW_INFERENCE.json")["raw_table"],
        "INDEPENDENT_RAW_RELEASE",
    )
    csv_table(folder / "ADMISSION_COUNTS.csv", ad["counts"])
    identity = []
    for host, v in card["hosts"].items():
        addresses = v["reverse_sll_addresses"]
        identity.append(
            dict(
                host=host,
                role=v["role"],
                main_identity=v["main_identity"],
                supplemental_identity=v["supplement_identity"],
                reverse_sender_changed=v["reverse_sll_changed"],
                normal_1_sll_senders=" | ".join(addresses["normal1"]),
                normal_2_sll_senders=" | ".join(addresses["normal2"]),
                password_sll_senders=" | ".join(addresses["password"]),
                cross_capture_identity_witnesses=v["independent_cross_capture_evidence_count"],
                normal_window_start_ns=v["window_start_ns"],
                normal_window_end_ns=v["window_end_ns"],
                normal_reference_scope=ad["references"][host].get("reason", "正常参考窗口已核定"),
            )
        )
    csv_table(folder / "TARGET_IDENTITY.csv", identity)
    checks = verify(folder, card)
    result = dict(
        status="PASS",
        pilot=pilot,
        rows=seal["rows"],
        query_populations=seal["populations"],
        frozen_head_witness=sc["source_witness"],
        numerical_oracle=oracle_errors,
        large_decision_arrays=arrays,
        references=ad["references"],
        checks=checks,
        small_outputs={
            n: artifact(folder / n) for n in [*names.values(), "ADMISSION_COUNTS.csv", "TARGET_IDENTITY.csv"]
        },
    )
    dump(folder / "EVALUATION.json", result)
    return result
