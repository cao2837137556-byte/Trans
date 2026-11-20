"""Frozen-CPU audit, encodings, isolated head scoring and paired evaluation."""

import json
import os
from pathlib import Path
import resource
import sqlite3
import subprocess
import sys
import time
import traceback

import numpy as np
from common_ton import HERE, Progress, artifact, csv_table, dump, read, require, sha
from dad_stats import load_tables, paper, table, validate


def boot(project):
    from frozen_env import setup

    parent = project / "runs/p4_ton_password_frozen_v12_20261118/package"
    require(
        sha(parent / "PACKAGE_MANIFEST.json") == read(HERE / "DAD_CARD.json")["ton_package_sha256"],
        "FROZEN_ENCODER_WORKER",
    )
    for n, h in read(parent / "PACKAGE_MANIFEST.json")["files"].items():
        require(sha(parent / n) == h, "PARENT_SHA:" + n)
    older, freeze, cfg, geom = setup(project)
    sys.path.append(str(parent))
    return older, freeze, cfg, geom


def score(project, folder, freeze, cfg, progress, baseline_only=False):
    # Load the original head package in a process separate from all packet/geometry modules.
    from frozen_env import store
    from reference_assets import forward, model_setup
    from evaluate_ton import check_frozen_head

    s = store(project, freeze)
    model = model_setup(s, cfg)
    proof = check_frozen_head(s, model, cfg["method"], progress)
    dump(
        folder / "CIC_WITNESS.json",
        dict(proof, models={k: v for k, v in s.checked.items() if k.startswith("head_")}),
    )
    if baseline_only:
        return
    with np.load(folder / "input.npz", allow_pickle=False) as a:
        uid, q, x = a["uid"], a["q"], a["x"]
    with np.load(folder / "encoded.npz", allow_pickle=False) as e:
        require(np.array_equal(e["uid"], uid), "ENCODED_SCORE_UID_ORDER")
        z = e["e3"]
    raw = forward(model, z, q, x, np.arange(len(uid)), progress, "FROZEN_790")
    require(raw.shape == (len(uid), 4) and np.isfinite(raw).all(), "RAW_SCHEMA")
    np.savez(folder / "scores.npz", uid=uid, raw=raw)


def child(project, folder, mode):
    subprocess.run(
        [sys.executable, "-X", "utf8", "-B", str(HERE / "dad_worker.py"), mode, str(project), str(folder)],
        check=True,
    )


def compute(phase, project, out):
    older, freeze, cfg, geom = boot(project)
    pilot = phase == "preflight"
    if phase in ("score", "baseline"):
        return score(project, out, freeze, cfg, Progress(out, phase), phase == "baseline")
    require(pilot or phase == "formal", "SCIENTIFIC_PHASE")
    folder = out / phase
    folder.mkdir(exist_ok=False)
    progress = Progress(out, phase)
    from frozen_env import decoder, store

    pkg_sha = sha(HERE / "PACKAGE_MANIFEST.json")
    if not pilot:
        pre = read(out / "PREFLIGHT.json")
        require(
            pre["status"] == "PASS"
            and pre["package_sha256"] == pkg_sha
            and pre["job_id"] == read(out / "JOB_preflight.json")["job_id"],
            "PRECHECK_BEFORE_FORMAL",
        )
    # Ensure the original two-hop imports resolve to the pinned production paths.
    from vendor import packet_reader

    require(Path(packet_reader.__file__).resolve().parent == older / "vendor", "PINNED_ETHERNET_READER")
    from representations import encoder, forward_batch
    from dad_frontend import replay_inputs
    from dad_geometry import top_two, direct
    from reference_inputs import normalized_context
    from vendor import constrained_onboarding_core_v3 as core, p4_worker
    from analysis_core import guard

    exe = decoder()
    dump(
        out / f"RUNTIME_{phase}.json",
        dict(
            job_id=os.environ["SLURM_JOB_ID"],
            node=os.environ["SLURMD_NODENAME"],
            python=sys.version,
            numpy=np.__version__,
            tshark=artifact(exe),
            package_sha256=pkg_sha,
        ),
    )
    progress("BASELINE", description="复现原 CIC 查询和四个源阈值判决", force=True)
    child(project, folder, "baseline")
    runtime, encoder_id = encoder(project, freeze)
    begin = time.monotonic()
    seal = replay_inputs(folder, HERE, exe, pilot, progress, runtime[3])
    seal.update(
        encoder=encoder_id,
        package_sha256=pkg_sha,
        files={n: artifact(folder / n) for n in ("input.npz", "rows.jsonl", "examples.sqlite")},
    )
    dump(folder / "INPUT_SEAL.json", seal)
    prep_seconds = time.monotonic() - begin
    with np.load(folder / "input.npz", allow_pickle=False) as s:
        ids, q, x = s["uid"], s["q"], s["x"]
    positions = {u: i for i, u in enumerate(ids.tolist())}
    rows = [json.loads(l) for l in (folder / "rows.jsonl").read_text(encoding="utf8").splitlines()]
    require([r["uid"] for r in rows] == ids.tolist() and len(positions) == len(rows), "INPUT_SEAL_ORDER")
    z = np.empty((len(ids), 768), np.float32)
    seen = np.zeros(len(ids), bool)
    db = sqlite3.connect((folder / "examples.sqlite").resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    begin = time.monotonic()
    batch_max = 0.0
    for bid in range(seal["batches"]):
        t = time.monotonic()
        u, values, _ = forward_batch(db, bid, runtime)
        batch_max = max(batch_max, time.monotonic() - t)
        ix = np.array([positions[k] for k in u])
        require(len(set(u)) == len(u) and not seen[ix].any(), "DUPLICATE_ENCODER_SLOT")
        z[ix] = values
        seen[ix] = True
        progress("ENCODING", bid + 1, seal["batches"], description="冻结 netFound 编码")
    db.close()
    require(seen.all(), "ENCODED_UIDS")
    encode_seconds = time.monotonic() - begin
    del runtime
    np.savez(folder / "encoded.npz", uid=ids, e3=z)
    child(project, folder, "score")
    with np.load(folder / "scores.npz", allow_pickle=False) as sc:
        require(np.array_equal(sc["uid"], ids), "RAW_TO_CCNR_JOIN")
        raw = sc["raw"]
    s = store(project, freeze)

    def norm(key):
        with np.load(s.get(key), allow_pickle=False) as f:
            return f["mean"], f["scale"]

    context = normalized_context(x, norm("context_normalizer"))
    n = seal["references"]
    refs = rows[:n]
    queries = rows[n:]
    rr = ids[:n].tolist()
    bank = core.ReferenceBank(
        refs, z[:n], q[:n], norm("e3_normalizer"), feature_uids=rr, q_uids=rr, allow_prebank_history=True
    )
    from replay_geometry import plan_queries

    boundary = next(r for r in refs if r["frame"] == 1304)
    first = next(r for r in queries if r["capture_id"] == "mon" and r["frame"] == 1305)
    _, limits = plan_queries(bank, [dict(boundary, use="QUERY"), first], geom)
    require(
        limits["opening"][0] != "" and limits["opening"][1] == "" and limits["legal_component_count"][0] == 0,
        "STRICT_COMMISSION_BOUNDARY",
    )
    g = top_two(queries, z[n:], q[n:], context[n:], bank, context[:n], geom, progress)
    require(
        np.all(g["opening"] == "")
        and np.all(g["geometry_ready"])
        and not set(rr).intersection(ids[n:].tolist()),
        "REFERENCE_OPEN",
    )
    # Direct per-record oracle for the same bank, including the first post-window query.
    sl = (
        np.arange(len(queries))
        if pilot
        else np.unique(
            np.r_[
                0,
                np.linspace(0, len(queries) - 1, 64, dtype=int),
                np.flatnonzero([r["capture_id"] == "thu" for r in queries]),
            ]
        )
    )
    sub = {k: v[sl] for k, v in g.items() if isinstance(v, np.ndarray)}
    _, _, err = direct(
        [queries[i] for i in sl], z[n:][sl], q[n:][sl], context[n:][sl], bank, context[:n], geom, sub
    )
    support = g["weak"]
    method = cfg["method"]
    base = raw[n:]
    flags = guard(q[n:])
    cuts = np.asarray(method["cuts"])
    corrected = p4_worker.correct(base, support, q[n:], method["scales"], True, power=4)
    by_head = base[:, :3] - (0.25 * np.asarray(method["scales"])) * (1 - (1 - support[:, None]) ** 4)
    by_head[flags] = base[flags, :3]
    oracle = p4_worker.four(by_head)
    require(
        np.allclose(oracle, corrected, atol=2e-10, rtol=0)
        and np.array_equal(oracle > cuts, corrected > cuts),
        "FIXED_KERNEL_THRESHOLDS",
    )
    decisions = folder / "QUERY_DECISIONS.npz"
    np.savez(
        decisions,
        uid=ids[n:],
        day=[r["capture_id"] for r in queries],
        frame=[r["frame"] for r in queries],
        label=[r["label"] for r in queries],
        raw=base,
        ccnr=corrected,
        raw_alarm=base > cuts,
        ccnr_alarm=corrected > cuts,
        support=support,
        bypass=flags,
        donor_rows=g["donors"],
        m=g["m"],
    )
    result = table(queries, base, corrected, support, flags, cuts)
    thu = [r for r in result if r["group"] == "thu"]
    checks = validate(result, thu, formal=not pilot)
    receipt = dict(
        status="PASS",
        job_id=os.environ["SLURM_JOB_ID"],
        package_sha256=pkg_sha,
        real_queries=len(queries),
        references=n,
        direct_oracle_rows=len(sl),
        max_distance_error=err,
        cic_witness=read(folder / "CIC_WITNESS.json"),
        frontend_seconds=prep_seconds,
        encoding_seconds=encode_seconds,
        max_batch_seconds=batch_max,
        batches=seal["batches"],
        seal=artifact(folder / "INPUT_SEAL.json"),
        checks=checks,
    )
    if pilot:
        require(len(queries) > 0 and len(thu) == 4 and any(r["N"] > 0 for r in thu), "REAL_THURSDAY_SLICE")
        receipt.update(
            probe_frames=seal["pilot_witnesses"], clock_regression=seal["cross_component_regression"]
        )
        receipt["formal_wall_seconds"] = max(
            7200, int((prep_seconds + 1800 + 3 * encode_seconds * (19621 / len(ids))) / 600 + 1) * 600
        )
        dump(out / "PREFLIGHT.json", receipt)
    else:
        with np.load(out / "preflight" / "QUERY_DECISIONS.npz", allow_pickle=False) as p:
            ix = np.array([positions[k] - n for k in p["uid"].tolist()])
            require(
                (ix >= 0).all()
                and np.allclose(base[ix], p["raw"], rtol=0, atol=2e-4)
                and np.array_equal(base[ix] > cuts, p["raw_alarm"]),
                "FORMAL_TO_REAL_SLICE_BASELINE",
            )
        csv_table(out / "DAILY_METRICS.csv", result)
        # Preserve the same CSV columns for the extracted Thursday rows.
        cols = dict.fromkeys(dict.fromkeys(k for r in result for k in r), "")
        csv_table(out / "THURSDAY_DUPLICATION.csv", [dict(cols, **r) for r in thu])
        summary, recount = load_tables(out)
        require(checks == recount, "TABLE_READBACK")
        (out / "RESULTS_FOR_PAPER.md").write_text(paper(summary), encoding="utf8")
        dump(out / "TUESDAY_DIAGNOSTIC.json", seal["tuesday"])
        dump(
            out / "DATA_BINDING.json",
            {
                k: seal[k]
                for k in (
                    "references",
                    "queries",
                    "query_orders",
                    "bank_order",
                    "selected_uid_order",
                    "monday_cut_frame",
                    "monday_first_query",
                )
            },
        )
        index = {
            str(p.relative_to(out)): artifact(p)
            for f in (out / "preflight", folder)
            for p in f.iterdir()
            if p.is_file()
        }
        dump(out / "ARTIFACT_SHA.json", dict(hpc_directory=str(out), files=index))
        receipt["outputs"] = {
            k: artifact(out / k)
            for k in (
                "DAILY_METRICS.csv",
                "THURSDAY_DUPLICATION.csv",
                "RESULTS_FOR_PAPER.md",
                "DATA_BINDING.json",
                "TUESDAY_DIAGNOSTIC.json",
                "ARTIFACT_SHA.json",
            )
        }
        dump(out / "FORMAL.json", receipt)
    progress("COMPLETE", 1, 1, description="配对核验完成", force=True)


if __name__ == "__main__":
    phase, project, target = sys.argv[1:]
    out = Path(target)
    t = time.monotonic()
    try:
        compute(phase, Path(project), out)
    except Exception as e:
        dump(
            out / f"FAILURE_{phase}.json",
            dict(error=str(e), traceback=traceback.format_exc(), job=os.environ.get("SLURM_JOB_ID")),
        )
        raise
    finally:
        if phase in ("preflight", "formal"):
            dump(
                out / f"RESOURCES_{phase}.json",
                dict(
                    seconds=time.monotonic() - t,
                    maxrss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                    child_maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                ),
            )
