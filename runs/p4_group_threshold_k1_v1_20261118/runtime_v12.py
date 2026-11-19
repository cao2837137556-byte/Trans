"""Load the accepted 183937 and 184893 inputs and run the common compute-node pilot."""

import importlib.util
import os
from pathlib import Path
import sys

import numpy as np

from common_round1 import artifact, dump, load, read_rows, require, sha, uid_sha, verify_artifact, write_rows

HERE = Path(__file__).resolve().parent
POOLS = ("CIC_DEV", "UNSW_DEV", "EDGE")
PHASES = ("preflight", "groups", "k1", "ports")


def boot(project, out, phase):
    from common_round1 import verify_package

    manifest = verify_package(HERE)
    cfg = load(HERE / "ASSETS.json")
    rule = load(HERE / "EXPERIMENT_CARD.json")
    require(
        sha(HERE / "EXPERIMENT_CARD.json")
        == load(HERE / "RULE_FREEZE.json")["card_sha256"]
        == cfg["rule_sha256"]
        and manifest["run"] == out.name,
        "SEALED_EXPERIMENT_IDENTITY",
    )
    prior = project / "runs" / cfg["geometry_run"] / "package"
    require(sha(prior / "PACKAGE_MANIFEST.json") == cfg["geometry_package"], "PREDECESSOR_184893_PACKAGE")
    for name, digest in load(prior / "PACKAGE_MANIFEST.json")["files"].items():
        require(sha(prior / name) == digest, "PREDECESSOR_SOURCE_SHA:" + name)
    sys.path.insert(1, str(prior))
    spec = importlib.util.spec_from_file_location("paired_184893", prior / "worker.py")
    previous = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(previous)
    folder = out / phase
    folder.mkdir(exist_ok=True)
    old, contract, tshark = previous.bind_runtime(project, folder, phase)
    sys.path.remove(str(prior))
    sys.path.insert(1, str(prior))
    from runtime_support import Progress

    receipt = load(folder / f"RUNTIME_{phase}.json")
    receipt.update(run_package_sha256=sha(HERE / "PACKAGE_MANIFEST.json"), rule_sha256=cfg["rule_sha256"])
    dump(out / f"RUNTIME_{phase}.json", receipt)
    return (
        previous,
        contract,
        load(old / "CONFIG.json"),
        load(old / "GEOMETRY.json"),
        cfg,
        rule,
        tshark,
        Progress(folder, phase),
    )


def pinned(project, spec):
    path = (project / spec["path"]).resolve()
    require(
        path.is_relative_to(project) and path.is_file() and sha(path) == spec["sha256"],
        "PINNED_INPUT:" + spec["path"],
    )
    return path


def load_cache(project, pool, d, assets):
    path = pinned(project, assets["paired"][pool])
    with np.load(path, allow_pickle=False) as z:
        require(z["uid"].tolist() == d["ids"], "184893_CACHE_QUERY_ORDER")
        return {
            k: z[k]
            for k in (
                "m1",
                "m2",
                "bank_rows",
                "opening",
                "geometry_ready",
                "legal_components",
                "admitted",
                "weak",
                "scores_a",
                "scores_b",
                "alarms_a",
                "alarms_b",
            )
        }


def seal_groups(project, out, cfg, assets, rule, progress):
    from calibration import fit, four, WITH_GUARD
    from group_threshold import fit_groups
    from reference_assets import bank
    from runtime_support import Store

    store = Store(project, ("reference",))
    prior = load(pinned(project, assets["original_thresholds"]))
    require(
        prior["status"] == "PASS"
        and prior["evaluation_used"] is False
        and prior["source_cuts"] == cfg["method"]["cuts"],
        "183937_REFERENCE_THRESHOLD_SEAL",
    )
    art = out / "artifacts"
    art.mkdir(exist_ok=True)
    result = {}
    for pool in POOLS:
        with progress.measure("FIT_REFERENCE_ONLY_" + pool):
            rows, z, q, x = bank(store, cfg, pool, progress)
            del z, x
            pin = assets["reference_scores"][pool]
            ids = [r["uid"] for r in rows]
            with np.load(pinned(project, pin), allow_pickle=False) as arr:
                require(
                    arr["uid"].tolist() == ids
                    and len(set(ids)) == len(ids) == pin["rows"]
                    and uid_sha(ids) == cfg["reference"][pool]["full_bank"]["uid_sha256"],
                    "183937_REF_SCORE_ORDER",
                )
                scores = arr["raw"]
            source = cfg["method"]["cuts"]
            require(
                scores.dtype == np.float64
                and scores.shape == (len(rows), 4)
                and np.isfinite(scores).all()
                and np.array_equal(scores, four(scores[:, :3])),
                "REFERENCE_HEAD_ORDER",
            )
            witness = fit(rows, scores, q, source)["fits"][WITH_GUARD]
            original = prior["pools"][pool]
            require(
                witness == original["fits"][WITH_GUARD] and original["reference_uid_sha256"] == uid_sha(ids),
                "183937_TESTBED_GUARDED_REPRODUCTION",
            )
            pooled = [r["cut"] for r in witness["heads"]]
            devices = sorted(
                {r["device"] for r in rows} | {w["device"] for w in cfg["windows"].get(pool, [])}
            )
            groups = fit_groups(rows, scores, q, source, pooled, devices, rule)
            if pool == "CIC_DEV":
                require(groups["Eufy Home Base|6"]["reason"] == "EMPTY", "CIC_EMPTY_TCP")
            if pool == "EDGE":
                udp = [g for g in groups.values() if g["protocol"] == 17]
                require(
                    len(udp) == 1
                    and udp[0]["reference_rows"] == 28
                    and udp[0]["components"] == 12
                    and udp[0]["reason"] == "SMALL",
                    "EDGE_UDP_SMALL_GROUP",
                )
            row_path = art / (pool + "_refs.jsonl.gz")
            n = write_rows(row_path, rows)
            q_path = art / (pool + "_ref_q14.npy")
            np.save(q_path, q, allow_pickle=False)
            result[pool] = dict(
                groups=groups,
                pooled=pooled,
                ref_rows=artifact(row_path, n),
                ref_q14=artifact(q_path, len(q)),
                reference_uid_sha256=uid_sha(ids),
                original_ref_score_sha256=pin["sha256"],
            )
    require(all(store.specs[k]["group"] == "reference" for k in store.checked), "REFERENCE_FIT_INPUT_ROLES")
    seal = dict(
        status="SEALED",
        rule_sha256=assets["rule_sha256"],
        reference_only=True,
        preflight_job=os.environ["SLURM_JOB_ID"],
        prior_threshold_sha256=assets["original_thresholds"]["sha256"],
        source_cuts=cfg["method"]["cuts"],
        pools=result,
        reference_inputs=store.checked,
    )
    dump(out / "GROUP_THRESHOLDS.json", seal)
    require(load(out / "GROUP_THRESHOLDS.json") == seal, "THRESHOLD_ROUNDTRIP")
    return seal


def read_full(project, out, pool, store, cfg, assets, seal):
    from evaluation import load_query

    ref = seal["pools"][pool]
    refs = read_rows(verify_artifact(out / "artifacts", ref["ref_rows"]))
    require(
        uid_sha([r["uid"] for r in refs]) == ref["reference_uid_sha256"] == assets["bank_uid_sha256"][pool],
        "184893_BANK_ROW_ORDER",
    )
    rows, ids, raw, p4, q, active, views, expansion, pop = load_query(store, cfg, pool, refs)
    require(uid_sha(ids) == assets["query_uid_sha256"][pool], "ACCEPTED_FULL_QUERY_ORDER")
    with np.load(store.get(pool + ":query_array"), allow_pickle=False) as a:
        saved = a["support3"]
    d = dict(
        rows=rows,
        ids=ids,
        raw=raw,
        p4=p4,
        q=q,
        active=active,
        views=views,
        expansion=expansion,
        population=pop,
        saved=saved,
    )
    return d, refs


def distance_witness(d, geo, cache, geom):
    from geometry import direct
    from replay_geometry import radii
    from vendor import constrained_onboarding_core_v3 as core, geometry_frozen

    _, _, direct_error = direct(d["rows"], d["z"], d["q"], d["x"], d["bank"], d["rc"], geom, geo)
    expected = np.column_stack((cache["m1"], cache["m2"]))
    require(
        np.allclose(geo["m"], expected, rtol=0, atol=2e-10)
        and np.array_equal(geo["legal_component_count"], cache["legal_components"])
        and np.array_equal(geo["gate"], cache["admitted"]),
        "DIRECT_TO_ARCHIVED_TOP_TWO",
    )
    # A different GEMM batch can choose another tied donor; verify the archived donor's actual value.
    bank = d["bank"]
    for i, row in enumerate(d["rows"]):
        loc = cache["bank_rows"][i]
        valid = loc >= 0
        rr = loc[valid]
        if not len(rr):
            continue
        rq, rc = radii(geom, row["protocol"])
        dz = np.clip(1 - core._unit(d["z"][i : i + 1], bank.normalizer) @ bank.z[rr].T, 0.0, 2.0)[0]
        dq = geometry_frozen.rms(d["q"][i : i + 1], bank.q14[rr])[0]
        dc = geometry_frozen.rms(d["x"][i : i + 1], d["rc"][rr])[0]
        actual = np.maximum.reduce((core._ratio(dz, rq[0]), core._ratio(dq, rq[1]), core._ratio(dc, rc)))
        require(np.allclose(actual, expected[i, valid], rtol=0, atol=2e-10), "DIRECT_ARCHIVED_DONOR_VALUES")
    return direct_error


def preflight(project, out, previous, contract, cfg, geom, assets, rule, tshark, progress):
    from analysis_core import guard
    from geometry import top_two
    from group_threshold import apply_groups, group_key, PRIMARY, SENS, POOL_ARM
    from inputs import load_pool, raw_slice, store_for
    from mechanism import K1, K2, replay, validate_donors
    from port_audit import run as ports
    from tables_v12 import comparison_tables
    from paired_stats import check_pairs
    from regressions import boundaries

    boundaries()
    seal = seal_groups(project, out, cfg, assets, rule, progress)
    store = store_for(project, contract)
    for h in rule["heads"][:3]:
        store.get("head_" + h)
    norms = []
    for name in ("e3_normalizer", "context_normalizer"):
        with np.load(store.get(name), allow_pickle=False) as a:
            norms.append((a["mean"], a["scale"]))
    baseline = load(pinned(project, assets["baseline_expected"]))
    results = {}
    for pool in POOLS:
        with progress.measure("FULL_BASELINE_AND_REAL_SLICE_" + pool):
            d, frozen = load_pool(store, pool, cfg, contract, norms, progress)
            refs, _, qref, _ = frozen
            base = previous.frozen_baseline(pool, d, cfg["method"], baseline)
            cache = load_cache(project, pool, d, assets)
            if pool == "CIC_DEV":
                frontend = raw_slice(store, frozen, norms, d, out / "preflight", tshark, progress)
            ix = set(previous.pick_slice(d).tolist())
            one = cache["m1"] < 1.0
            for mask in (
                one & ~cache["admitted"],
                cache["legal_components"] == 1,
                cache["admitted"] & (cache["m1"] < cache["m2"]),
                cache["admitted"] & ~guard(d["q"]),
            ):
                pos = np.flatnonzero(mask)
                if len(pos):
                    ix.update(pos[np.linspace(0, len(pos) - 1, min(8, len(pos)), dtype=int)].tolist())
            ix = np.asarray(sorted(ix))
            tiny = previous.subset(d, ix)
            small = {k: v[ix] for k, v in cache.items()}
            g = top_two(
                tiny["rows"], tiny["z"], tiny["q"], tiny["x"], tiny["bank"], tiny["rc"], geom, progress
            )
            validate_donors(tiny, small, refs)
            err = distance_witness(tiny, g, small, geom)
            values = replay(tiny, small, cfg["method"])
            direct_s1 = np.where(
                (g["opening"] == "") & g["geometry_ready"] & (g["legal_component_count"] >= 1),
                np.clip(1 - g["m"][:, 0], 0, 1),
                0.0,
            )
            independent = previous.independent_scores(tiny, direct_s1, cfg["method"])
            require(
                np.array_equal(independent > cfg["method"]["cuts"], values["k1"]), "DIRECT_K1_KERNEL_AND_CUT"
            )
            fitted = seal["pools"][pool]
            predictions, route = apply_groups(tiny, fitted["groups"], cfg["method"], fitted["pooled"])
            for j, (row, protected) in enumerate(zip(tiny["rows"], guard(tiny["q"]))):
                item = fitted["groups"].get(group_key(row["device"], row["protocol"]))
                for arm, field, default in (
                    (PRIMARY, "primary", cfg["method"]["cuts"]),
                    (SENS, "sensitivity", fitted["pooled"]),
                ):
                    cuts = cfg["method"]["cuts"]
                    if tiny["active"][j] and not protected:
                        cuts = [item["heads"][h][field]["cut"] for h in rule["heads"]] if item else default
                    require(np.array_equal(tiny["raw"][j] > cuts, predictions[arm][j]), "DIRECT_QUERY_ROUTE")
            predictions[K1] = values["k1"]
            m, p = comparison_tables(
                pool, tiny, predictions, [(K2, K1), (POOL_ARM, PRIMARY), (PRIMARY, SENS)], {}
            )
            check_pairs(m, p)
            counts, _, _ = ports(pool, tiny, refs, qref, small, values, store, assets, header_lookup=False)
            path = out / "artifacts" / (pool + "_pilot.npz")
            np.savez(
                path,
                ix=ix,
                uid=np.asarray(tiny["ids"]),
                k1=values["k1"],
                k2=values["k2"],
                route=route,
                group_source=predictions[PRIMARY],
                group_pool=predictions[SENS],
            )
            results[pool] = dict(
                rows=len(ix),
                baseline=base,
                oracle_abs_error=err,
                paired_cells=len(p),
                port_cells=len(counts),
                witness=artifact(path),
            )
            del d, frozen, refs, qref, tiny, cache, small, g
    require(frontend["actual_forwards"] > 0 and frontend["decoded_frames"] > 0, "REAL_DECODER_ENCODER")
    return dict(
        status="PASS",
        job_id=os.environ["SLURM_JOB_ID"],
        rule_sha256=assets["rule_sha256"],
        package_sha256=sha(HERE / "PACKAGE_MANIFEST.json"),
        thresholds=artifact(out / "GROUP_THRESHOLDS.json"),
        actual_frontend=frontend,
        pools=results,
    )
