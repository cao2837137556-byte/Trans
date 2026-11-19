"""One verified pilot, then independent threshold, one-component, and donor-audit jobs."""

import gc
import os
from pathlib import Path
import sys
import traceback

import numpy as np

from common_round1 import artifact, dump, load, require, sha, verify_artifact, write_rows
from runtime_v12 import HERE, POOLS, PHASES, boot, load_cache, pinned, preflight, read_full


def changed_queries(out, tag, pool, ids, arms, comparisons):
    any_change = np.logical_or.reduce([np.any(arms[a] != arms[b], axis=1) for a, b in comparisons])
    indices = np.flatnonzero(any_change)
    path = out / "artifacts" / f"{tag}_{pool}_changed.jsonl.gz"
    count = write_rows(
        path,
        (
            dict(row=int(i), uid=ids[i], alarms={arm: m[i].tolist() for arm, m in arms.items()})
            for i in indices
        ),
    )
    return dict(path=str(path), **artifact(path, count))


def group_phase(pool, d, seal, method, previous_metrics, witness, out):
    from group_threshold import apply_groups, PRIMARY, SENS, POOL_ARM
    from tables_v12 import comparison_tables
    from paired_stats import expected_cells

    predictions, route = apply_groups(d, seal["groups"], method, seal["pooled"])
    routes = {
        "APPLIED_" + name: route == name
        for name in ("FIT", "EMPTY", "ALL_BYPASS", "SMALL", "PRE_OPEN", "BYPASS")
    }
    require(sum(int(v.sum()) for v in routes.values()) == len(route), "EXHAUSTIVE_QUERY_ROUTES")
    with np.load(witness, allow_pickle=False) as z:
        ix = z["ix"]
        require(
            np.array_equal(z["uid"], np.asarray(d["ids"])[ix])
            and np.array_equal(z["route"], route[ix])
            and np.array_equal(z["group_source"], predictions[PRIMARY][ix])
            and np.array_equal(z["group_pool"], predictions[SENS][ix]),
            "FORMAL_THRESHOLD_REAL_SLICE",
        )
    controls = ("RAW", POOL_ARM, "P4_MAIN")
    comparisons = [(left, right) for left in controls for right in (PRIMARY, SENS)] + [(PRIMARY, SENS)]
    metrics, pairs = comparison_tables(pool, d, predictions, comparisons, routes)
    result = dict(
        original_metric_rows=expected_cells(metrics, previous_metrics, controls),
        query_routes={k: int(v.sum()) for k, v in routes.items()},
        changed=changed_queries(out, "groups", pool, d["ids"], predictions, comparisons),
    )
    return metrics, pairs, result


def execute(phase, project, out):
    previous, contract, cfg, geom, inputs, rule, tshark, progress = boot(project, out, phase)
    try:
        if phase == "preflight":
            with progress.measure("QUALIFY_AND_SEAL"):
                result = preflight(
                    project, out, previous, contract, cfg, geom, inputs, rule, tshark, progress
                )
            dump(out / "PREFLIGHT.json", result)
            require(load(out / "PREFLIGHT.json") == result, "PREFLIGHT_READBACK")
            return
        from inputs import store_for
        from mechanism import replay, validate_donors, K1, K2
        from port_audit import run as port_analysis
        from tables_v12 import comparison_tables, views_by_outcome
        from paired_stats import check_pairs, csv_write, expected_cells

        pilot = load(out / "PREFLIGHT.json")
        require(
            pilot["status"] == "PASS"
            and pilot["job_id"] == load(out / "JOB_preflight.json")["job_id"]
            and pilot["package_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json")
            and sha(out / "GROUP_THRESHOLDS.json") == pilot["thresholds"]["sha256"],
            "ADMITTED_PILOT_AND_THRESHOLDS",
        )
        seal = load(out / "GROUP_THRESHOLDS.json")
        require(seal["rule_sha256"] == inputs["rule_sha256"] and seal["reference_only"], "FROZEN_GROUP_RULE")
        store = store_for(project, contract)
        original = load(pinned(project, inputs["original_metrics"]))
        all_metrics, all_pairs, extra, port_detail = [], [], [], []
        info = {}
        for pool in POOLS:
            with progress.measure("VERIFIED_INPUTS_" + pool):
                d, refs = read_full(project, out, pool, store, cfg, inputs, seal)
                slice_path = verify_artifact(out / "artifacts", pilot["pools"][pool]["witness"])
                expected = [r for r in original if r["pool"] == pool]
            with progress.measure(phase.upper() + "_" + pool):
                if phase == "groups":
                    m, p, info[pool] = group_phase(
                        pool, d, seal["pools"][pool], cfg["method"], expected, slice_path, out
                    )
                else:
                    cache = load_cache(project, pool, d, inputs)
                    geo = replay(d, cache, cfg["method"])
                    validate_donors(d, cache, refs)
                    with np.load(slice_path, allow_pickle=False) as z:
                        ix = z["ix"]
                        require(
                            np.array_equal(z["uid"], np.asarray(d["ids"])[ix])
                            and np.array_equal(z["k1"], geo["k1"][ix])
                            and np.array_equal(z["k2"], geo["k2"][ix]),
                            "FORMAL_K1_REAL_SLICE",
                        )
                    if phase == "k1":
                        arms = {K2: geo["k2"], K1: geo["k1"]}
                        comparisons = [(K2, K1)]
                        routes = {
                            k: geo["pathway"] == k
                            for k in ("new_positive_from_zero", "stronger_existing_dual", "equal_or_zero")
                        }
                        m, p = comparison_tables(pool, d, arms, comparisons, routes)
                        extra.extend(views_by_outcome(pool, d, geo))
                        info[pool] = dict(
                            original_metric_rows=expected_cells(m, expected, [K2]),
                            subset_violations=0,
                            changed=changed_queries(out, "k1", pool, d["ids"], arms, comparisons),
                        )
                    else:
                        qref = np.load(
                            verify_artifact(out / "artifacts", seal["pools"][pool]["ref_q14"]),
                            allow_pickle=False,
                        )
                        totals, details, info[pool] = port_analysis(
                            pool,
                            d,
                            refs,
                            qref,
                            cache,
                            geo,
                            store,
                            inputs,
                            detail_path=out / "artifacts" / (pool + "_changed_donors.jsonl.gz"),
                        )
                        extra.extend(totals)
                        port_detail.extend(details)
                    del geo, cache
                if phase != "ports":
                    all_metrics.extend(m)
                    all_pairs.extend(p)
                info[pool]["rows"] = len(d["ids"])
                info[pool]["query_uid_sha256"] = inputs["query_uid_sha256"][pool]
                info[pool]["reference_uid_sha256"] = inputs["bank_uid_sha256"][pool]
                del d, refs
            gc.collect()
        names = []

        def table(name, records):
            filename = name + ".csv"
            csv_write(
                out / filename,
                records,
                ("pool", "view", "scope", "head", "device", "protocol", "label", "rows"),
            )
            names.append(filename)

        if phase == "ports":
            table("PORT_HEADLINE", extra)
            table("PORT_BY_DEVICE", port_detail)
        else:
            prefix = "GROUP" if phase == "groups" else "K1"
            headlines = check_pairs(all_metrics, all_pairs, subset=phase == "k1")
            table(prefix + "_HEADLINE", headlines)
            table(prefix + "_METRICS", all_metrics)
            table(prefix + "_PAIRS", all_pairs)
            if phase == "k1":
                table("K1_PATHWAYS", extra)
        result = dict(
            status="PASS",
            job_id=os.environ["SLURM_JOB_ID"],
            preflight_job=pilot["job_id"],
            rule_sha256=inputs["rule_sha256"],
            package_sha256=pilot["package_sha256"],
            pools=info,
            outputs={n: artifact(out / n) for n in names},
            inputs=store.checked,
        )
        dump(out / f"SCIENCE_{phase}.json", result)
        progress("COMPLETE", 1, 1, force=True)
    finally:
        src = out / phase / f"RESOURCES_{phase}.json"
        if src.exists():
            dump(out / f"RESOURCES_{phase}.json", load(src))


if __name__ == "__main__":
    phase, project, target = sys.argv[1:]
    out = Path(target)
    try:
        require(phase in PHASES, "UNKNOWN_PHASE")
        execute(phase, Path(project), out)
    except Exception as e:
        dump(
            out / f"FAILURE_{phase}.json",
            dict(error=str(e), traceback=traceback.format_exc(), job_id=os.environ.get("SLURM_JOB_ID")),
        )
        raise
