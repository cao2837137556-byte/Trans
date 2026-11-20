"""Read-only replay from verified cached packet scores, connection keys and literal TCP flags."""

from collections import defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time
import traceback
import zlib

import numpy as np
from common_round1 import artifact, dump, load, sha
from connection_tables import (
    LEVELS,
    require,
    summarize_host,
    finish_sweep,
    finish_misses,
    frozen_packet_marginals,
)
from result_checks import validate, tables_read, paper, FILES

HERE = Path(__file__).resolve().parent


def selected_connections(d):
    """Sample whole connections deterministically, including both endpoint outcomes."""
    keep = np.zeros(len(d["uid"]), bool)
    for kind in (False, True):
        ix = np.flatnonzero(d["attack"] == kind)
        names, inv = np.unique(d["conn"][ix], return_inverse=True)
        masks = []
        for v in (
            d["raw_alarm"][ix, 3],
            d["ccnr_alarm"][ix, 3],
            d["transport_data"][ix],
            d["off_bypass"][ix],
            d["support"][ix] > 0,
        ):
            val = np.zeros(len(names), bool)
            np.logical_or.at(val, inv, v)
            masks.append(val)
        codes = sum(v.astype(int) * (1 << j) for j, v in enumerate(masks))
        take = set()
        for code in np.unique(codes):
            group = np.flatnonzero(codes == code)
            take.update(group[np.linspace(0, len(group) - 1, min(3, len(group)), dtype=int)].tolist())
        keep[ix] = np.isin(inv, list(take))
    return {k: v[keep] for k, v in d.items()}


def check_pilot_direct(d, rows, miss, quant, method, eligible, host):
    # Independent scalar ensemble aggregation, with no dependence on packet-array ordering.
    records = defaultdict(list)
    cut = method["cuts"][3]
    for i, k in enumerate(d["conn"]):
        records[bool(d["attack"][i]), k].append(i)
    rawsets = {k for k, ix in records.items() if any(d["raw_alarm"][i, 3] for i in ix)}
    oldsets = {k for k, ix in records.items() if any(d["ccnr_alarm"][i, 3] for i in ix)}
    missed = [ix for k, ix in records.items() if k[0] and k not in rawsets]
    require(
        miss["entirely_missed"] == len(missed)
        and miss["has_data_connections"] == sum(any(d["transport_data"][i] for i in ix) for ix in missed),
        "PILOT_INDEPENDENT_MISSES",
    )
    if not eligible:
        return
    for lam in LEVELS:
        active = set()
        for k, ix in records.items():
            for i in ix:
                g = 1 - (1 - float(d["support"][i])) ** 4 if d["off_bypass"][i] else 0.0
                value = (
                    sum(float(d["raw"][i, j]) - (lam * span) * g for j, span in enumerate(method["scales"]))
                    / 3
                )
                if value > cut:
                    active.add(k)
                    break
        row = next(r for r in rows if r["head"] == "ensemble" and r["lambda_value"] == lam)
        for flag, prefix in ((True, "attack"), (False, "normal")):
            require(
                row[prefix + "_restored_vs_025"] == sum(k[0] == flag for k in active - oldsets),
                "PILOT_THRESHOLD_ORACLE",
            )
    if quant:
        is_attack = host == "192.168.1.195"
        groups = [
            [i for i in ix if d["raw_alarm"][i, 3]]
            for k, ix in records.items()
            if k[0] == is_attack and k in rawsets - oldsets
        ]
        first = [min(ix, key=lambda i: d["frame"][i]) for ix in groups]
        for r in quant:
            selected = first if r["weighting"].startswith("first_") else [i for ix in groups for i in ix]
            require(r["observations"] == len(selected), "PILOT_FIRST_RAW_PACKET_PER_CONNECTION")
            for attr, x in [("margin", d["raw"][selected, 3] - cut), ("support", d["support"][selected])]:
                for p, col in ((0.25, "P25"), (0.5, "median"), (0.75, "P75")):
                    if len(x):
                        ordered = sorted(x)
                        t = p * (len(x) - 1)
                        lo = int(t)
                        hi = int(np.ceil(t))
                        expected = ordered[lo] + (ordered[hi] - ordered[lo]) * (t - lo)
                        require(abs(r[attr + "_" + col] - expected) <= 2e-10, "PILOT_QUANTILE_ORACLE")


def bind(project, out, phase):
    from common_round1 import NUMPY_RUNTIME, PYTHON

    require(
        sys.platform.startswith("linux")
        and os.environ.get("SLURM_JOB_ID", "").isdigit()
        and not sys.flags.optimize
        and sys.version_info[:2] == (3, 11)
        and np.__version__ == "2.0.1"
        and Path(sys.executable).resolve() == PYTHON.resolve()
        and Path(np.__file__).resolve().is_relative_to((project / NUMPY_RUNTIME).resolve()),
        "SAME_SLURM_RUNTIME",
    )
    for n, h in load(HERE / "PACKAGE_MANIFEST.json")["files"].items():
        require(sha(HERE / n) == h, "PACKAGE_SHA:" + n)
    card = load(HERE / "CACHE_PINS.json")
    parent = project / "runs" / card["parent"]
    require(
        parent != out and sha(parent / "package/FROZEN.json") == card["freeze_sha256"], "ORIGINAL_FREEZE_SHA"
    )
    method = load(parent / "package/FROZEN.json")["method"]
    require(method == card["method"] and method["p"] == 4, "SOURCE_THRESHOLDS_AND_SCALES")
    paths = {}
    for k, p in card["inputs"].items():
        path = parent / "formal" / p["file"]
        require(
            path.is_file() and path.stat().st_size == p["bytes"] and sha(path) == p["sha256"],
            "CACHE_SHA:" + k,
        )
        paths[k] = path
    seal = load(paths["INPUT_SEAL.json"])
    proof = load(paths["RAW_PROOF.json"])
    require(
        seal["status"] == "SEALED"
        and not seal["pilot"]
        and seal["populations"] == card["populations"]
        and seal["database"]["sha256"] == card["inputs"]["snapshots.sqlite"]["sha256"]
        and proof["status"] == "PASS"
        and proof["population_order_sha256"] == card["order"]
        and proof["raw"]["sha256"] == card["inputs"]["RAW.npy"]["sha256"],
        "ACCEPTED_CACHE_LINEAGE",
    )
    dump(
        out / f"RUNTIME_{phase}.json",
        dict(
            status="PASS",
            job=os.environ["SLURM_JOB_ID"],
            node=os.environ["SLURMD_NODENAME"],
            numpy=np.__version__,
            python=sys.version,
            inputs=card["inputs"],
            package_sha256=sha(HERE / "PACKAGE_MANIFEST.json"),
        ),
    )
    return method, card, paths


def metadata(db, card):
    by = defaultdict(list)
    hashes = defaultdict(hashlib.sha256)
    overall = hashlib.sha256()
    counts = defaultdict(int)
    order = "CASE p.kind WHEN 'reference' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END,p.frame"
    sql = (
        """SELECT p.kind,p.uid,p.host,p.role,p.frame,p.conn,p.proto,p.off,p.data,p.owner,f.q
           FROM point p JOIN feature f USING(uid) WHERE p.selected=1 ORDER BY """
        + order
    )
    for i, (kind, uid, host, role, frame, conn, proto, off, data, owner, qbytes) in enumerate(
        db.execute(sql)
    ):
        tag = (uid + "\n").encode("ascii")
        overall.update(tag)
        hashes[kind].update(tag)
        counts[kind] += 1
        if kind == "reference":
            continue
        require(
            (kind, role) in (("attack", "password"), ("normal", "normal2"))
            and host in card["hosts"]
            and owner == card["hosts"][host]["owner"]
            and conn
            and proto in (6, 17)
            and off in (0, 1)
            and data in (0, 1),
            "CACHED_ROLES",
        )
        q = np.frombuffer(qbytes, "<f4")
        require(
            q.shape == (14,) and ((q[:10] == 0) | (q[:10] == 1)).all() and bool(q[0]) == (proto == 6),
            "ORIGINAL_Q14_FLAGS",
        )
        flags = int(q[1:10] @ BITS)
        require(bool(off) == (not (proto == 6 and flags & 2 and not flags & 16)), "ACTUAL_BYPASS")
        by[host].append((i, uid, kind == "attack", frame, conn, proto, off, data, flags))
    require(
        overall.hexdigest() == card["order"]
        and dict(counts) == {k: v["rows"] for k, v in card["populations"].items()}
        and all(h.hexdigest() == card["populations"][k]["uid_order_sha256"] for k, h in hashes.items()),
        "ALL_ORDERED_UID_HASHES",
    )
    return by


BITS = np.array([1 << i for i in range(9)])


def join(rows, path, raw, eligible):
    ix, ids, attack, frame, conn, proto, off, data, flags = map(np.asarray, zip(*rows))
    with np.load(path, allow_pickle=False) as f:
        d = {
            k: f[k]
            for k in (
                "index",
                "raw",
                "ccnr",
                "raw_alarm",
                "ccnr_alarm",
                "support",
                "opened",
                "reference_eligible",
                "off_bypass",
                "transport_data",
            )
        }
    with np.load(path, allow_pickle=False) as f:
        require(np.array_equal(f["uid"].astype("U64"), ids), "HOST_UID_ORDER")
    require(
        np.array_equal(d["index"], ix)
        and np.array_equal(d["raw"], raw[ix])
        and np.array_equal(d["off_bypass"], off)
        and np.array_equal(d["transport_data"], data)
        and np.all(d["reference_eligible"] == eligible)
        and np.all(d["support"][~(d["reference_eligible"] & d["opened"])] == 0),
        "SEALED_ROW_BINDING",
    )
    d.update(uid=ids, attack=attack, frame=frame, conn=conn, proto=proto, flags=flags)
    return d


def cached_flags(db, d):
    # Cross-check all zero-data RAW-silent attack connections against stored literal TCP flags.
    ix = np.flatnonzero(d["attack"])
    active = set(d["conn"][ix[d["raw_alarm"][ix, 3] | d["transport_data"][ix]]])
    n = 0
    for i in ix:
        if d["conn"][i] in active or d["proto"][i] != 6:
            continue
        blob = db.execute(
            "SELECT body FROM event WHERE role='password' AND frame=?", (int(d["frame"][i]),)
        ).fetchone()
        require(blob is not None, "ORIGINAL_EVENT")
        row = json.loads(zlib.decompress(blob[0]))
        require(
            int(row["frame.number"]) == d["frame"][i] and int(row["tcp.flags"], 0) == d["flags"][i],
            "LITERAL_FLAGS",
        )
        n += 1
    return n


def check_old(host, packet, card):
    for r in packet:
        key = (host, r["head"], r["layer"])
        base = card["raw_checks"][key]
        kind = r["kind"]
        n = r["N"]
        require(
            n == int(base[kind + "_included"])
            and r["connections"] == int(base[kind + "_connections"])
            and r["raw_positive"] == int(base["TP" if kind == "attack" else "FP"])
            and r["raw_positive_connections"]
            == int(
                base[
                    "attack_connections_with_detection"
                    if kind == "attack"
                    else "normal_connections_with_false_alarm"
                ]
            ),
            "ACCEPTED_RAW_DENOMINATORS",
        )
        pair = card["ccnr_checks"][key]
        if pair["status"] == "已评价":
            keys = (
                ("A", "B", "W", "retained")
                if kind == "attack"
                else ("normal_fp_raw", "normal_fp_reduced", "normal_fp_ccnr")
            )
            actual = (
                [r["raw_positive"], r["B"], r["withdrawn"], r["ccnr_positive"]]
                if kind == "attack"
                else [r["raw_positive"], r["withdrawn"], r["ccnr_positive"]]
            )
            require(
                actual == [int(pair[k]) for k in keys] and n == int(pair[kind + "_n"]),
                "ACCEPTED_025_MARGINALS",
            )


def run(phase, project, out):
    method, card, paths = bind(project, out, phase)
    pilot = phase == "preflight"
    pkg = sha(HERE / "PACKAGE_MANIFEST.json")
    if not pilot:
        pre = load(out / "PREFLIGHT.json")
        require(
            pre["status"] == "PASS"
            and pre["job_id"] == load(out / "JOB_preflight.json")["job_id"]
            and pre["package_sha256"] == pkg,
            "REAL_PILOT_REQUIRED",
        )
    for key, name in [("raw_checks", "RAW_TARGETS.csv"), ("ccnr_checks", "CCNR_PAIRED.csv")]:
        with (HERE / name).open(encoding="utf8", newline="") as f:
            card[key] = {(r["host"], r["head"], r["layer"]): r for r in csv.DictReader(f)}
    raw = np.load(paths["RAW.npy"], mmap_mode="r", allow_pickle=False)
    require(
        raw.shape == (sum(v["rows"] for v in card["populations"].values()), 4) and raw.dtype == np.float64,
        "GLOBAL_RAW_SCHEMA",
    )
    db = sqlite3.connect(paths["snapshots.sqlite"].resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.execute("PRAGMA query_only=ON")
    by = metadata(db, card)
    one = []
    two = []
    three = []
    witness = {}
    all_rows = 0
    flag_rows = 0
    for h, host in enumerate(sorted(by)):
        dump(
            out / "PROGRESS.json",
            dict(
                phase=phase, stage="REPLAY", done=h, total=4, description="核对连接身份及六档扣分 · " + host
            ),
        )
        eligible = host in card["paired_hosts"]
        full = join(by[host], paths[host], raw, eligible)
        if pilot:
            check_old(host, frozen_packet_marginals(full, host), card)
        small = selected_connections(full)
        signature = hashlib.sha256()
        for v in (small["uid"].astype("S64"), small["frame"], small["support"], small["transport_data"]):
            signature.update(v.tobytes())
        from connection_tables import predictions

        for _, p in predictions(small, method):
            signature.update(p.tobytes())
        witness[host] = dict(rows=len(small["uid"]), sha256=signature.hexdigest())
        d = small if pilot else full
        rows, miss, quant, packet = summarize_host(d, host, method, eligible)
        flag_rows += cached_flags(db, d)
        all_rows += len(d["uid"])
        if pilot:
            check_pilot_direct(d, rows, miss, quant, method, eligible, host)
        else:
            check_old(host, packet, card)
        one.extend(rows)
        two.append(miss)
        three.extend(quant)
    db.close()
    tables = (finish_sweep(one), finish_misses(two), three)
    checks = validate(*tables, formal=not pilot)
    receipt = dict(
        status="PASS",
        job_id=os.environ["SLURM_JOB_ID"],
        package_sha256=pkg,
        slice_witness=witness,
        rows=all_rows,
        literal_flag_rows=flag_rows,
        checks=checks,
        method=method,
        cache_order_sha256=card["order"],
    )
    if pilot:
        require(all_rows > 0 and flag_rows > 0 and len(three) == 4, "REAL_COHORT_SLICE")
        dump(out / "PREFLIGHT.json", receipt)
    else:
        require(witness == pre["slice_witness"] and all_rows == 363191, "FORMAL_TO_REAL_SLICE")
        from common_ton import csv_table

        for n, items in zip(FILES, tables):
            csv_table(out / n, items)
        outputs, recount = tables_read(out)
        require(recount == checks, "SERIALIZED_COUNT_CHECK")
        (out / "RESULTS_FOR_PAPER.md").write_text(paper(*outputs), encoding="utf8")
        receipt["outputs"] = {n: artifact(out / n) for n in (*FILES, "RESULTS_FOR_PAPER.md")}
        dump(out / "FORMAL.json", receipt)


if __name__ == "__main__":
    import resource

    phase, project, folder = sys.argv[1:]
    out = Path(folder)
    start = time.monotonic()
    try:
        require(phase in ("preflight", "formal"), "PHASE")
        run(phase, Path(project), out)
    except Exception as exc:
        dump(out / f"FAILURE_{phase}.json", dict(error=str(exc), traceback=traceback.format_exc()))
        raise
    finally:
        dump(
            out / f"RESOURCES_{phase}.json",
            dict(
                job=os.environ.get("SLURM_JOB_ID"),
                seconds=time.monotonic() - start,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            ),
        )
