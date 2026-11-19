"""Compute-node gate and phase entry points; score and geometry use isolated production imports."""

import gc
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

from common_ton import HERE, Progress, artifact, dump, read, require, sha
from frozen_env import decoder, setup


def subprocess_stage(stage, project, out, folder):
    child = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "-B",
            str(HERE / "worker_ton.py"),
            stage,
            str(project),
            str(out),
            str(folder),
        ],
        cwd=HERE,
        check=False,
    )
    require(child.returncode == 0, "CHILD_PHASE:" + stage)


def phase_main(phase, project, out, arg):
    _, freeze, cfg, geom = setup(project)
    contract = read(HERE / "SCOPED_INPUTS.json")
    card = read(HERE / "DIAGNOSTIC_CARD.json")
    stage = phase if phase != "encode" else "encode-" + str(arg)
    progress_dir = out / "status" / stage
    progress_dir.mkdir(parents=True, exist_ok=True)
    log = Progress(progress_dir, stage)
    log("START", 0, 1, description="正在核验冻结工件", force=True)
    source = read(out / "VERIFIED_INPUTS.json")["inputs"]
    paths = {k: Path(v["path"]) for k, v in source.items()}
    if phase in ("preflight", "prepare"):
        for k, p in paths.items():
            require(
                p.stat().st_size == contract["sources"][k]["bytes"]
                and sha(p) == contract["sources"][k]["sha256"],
                "COMPUTE_INPUT_SHA:" + k,
            )
    if phase in ("score", "metrics"):
        from evaluate_ton import score, evaluate

        folder = Path(arg)
        pilot = folder == out / "pilot"
        require(pilot or folder == out / "formal", "SCIENTIFIC_OUTPUT_SCOPE")
        if phase == "score":
            score(project, folder, freeze, cfg, log)
        else:
            evaluate(project, folder, freeze, cfg, geom, card, log, pilot)
        return
    from representations import prepare, calibrate, encode_shard

    if phase == "preflight":
        folder = out / "pilot"
        t0 = time.monotonic()
        # Actual normal conn logs must belong to the two original time intervals.
        from admission import zeek_rows, tick

        logs = {}
        for role in ("normal1", "normal2"):
            starts = [tick(r["ts"]) for _, r in zeek_rows(paths[role + "log"])]
            ss = contract["sources"][role]
            require(
                starts and min(starts) >= ss["min_ns"] and max(starts) <= ss["max_ns"], "NORMAL_LOG_TIME_ROLE"
            )
            logs[role] = dict(connections=len(starts), first_ns=min(starts), last_start_ns=max(starts))
        runtime, seal = prepare(project, out, folder, paths, contract, card, freeze, decoder(), True, log)
        require(seal["independent_real_input_checks"] == seal["rows"] > 0, "REAL_NATIVE_AND_TSHARK_WITNESS")
        estimate = calibrate(folder, runtime, log)
        dump(folder / "ENCODING_PLAN.json", dict(estimate, shards=1))
        encode_shard(project, folder, freeze, 0, 1, log, runtime)
        del runtime
        gc.collect()
        subprocess_stage("score", project, out, folder)
        subprocess_stage("metrics", project, out, folder)
        ev = read(folder / "EVALUATION.json")
        require(
            ev["status"] == "PASS"
            and ev["pilot"]
            and ev["frozen_head_witness"]["head_decision_differences"] == [0] * 4,
            "REAL_END_TO_END_ACCEPTANCE",
        )
        predicted_frames = sum(
            contract["sources"][r]["complete_packets"] for r in ("normal1", "normal2", "password")
        )
        estimated_rows = (
            contract["candidate_counts"]["frames"] + contract["matching_normal_inbound"][1] + 32768
        )
        seconds = (
            seal["decode_seconds"] * predicted_frames / seal["decoder_frames"]
            + seal["snapshot_seconds"] * estimated_rows / seal["rows"]
        )
        # Include full census, seek/index, hashing and the post-seal real-shape benchmark.
        wall = max(7200, ((int(seconds * 2.5) + 3599) // 1800) * 1800 + 1800)
        dump(
            out / "PREFLIGHT.json",
            dict(
                status="PASS",
                job_id=os.environ["SLURM_JOB_ID"],
                package_sha256=sha(HERE / "PACKAGE_MANIFEST.json"),
                source_sha256={k: v["sha256"] for k, v in source.items()},
                normal_logs=logs,
                input_seal=artifact(folder / "INPUT_SEAL.json"),
                real_decoded_frames=seal["decoder_frames"],
                real_inputs=seal["rows"],
                original_head_witness=ev["frozen_head_witness"],
                real_geometry_error=ev["numerical_oracle"],
                checks=ev["checks"],
                timed_shapes=estimate["shape_timing"],
                preparation_estimate_seconds=seconds,
                prepare_wall_seconds=wall,
                elapsed_seconds=time.monotonic() - t0,
                peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                child_peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                measured_spool_bytes=seal["database"]["bytes"],
                allocated_cpus=4,
                allocated_ram_mib=16384,
            ),
        )
    elif phase == "prepare":
        gate = read(out / "PREFLIGHT.json")
        require(
            gate["status"] == "PASS" and gate["package_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json"),
            "PILOT_BEFORE_FORMAL",
        )
        from admission import census

        audit = census(paths, contract, log)
        require(audit == read(HERE / "LOCAL_CENSUS.json"), "FULL_TARGET_IDENTITY_AND_ARCHIVED_CENSUS_LINUX")
        folder = out / "formal"
        runtime, seal = prepare(project, out, folder, paths, contract, card, freeze, decoder(), False, log)
        plan = calibrate(folder, runtime, log)
        dump(
            out / "PREPARATION.json",
            dict(
                status="PASS",
                job_id=os.environ["SLURM_JOB_ID"],
                pilot_job=gate["job_id"],
                populations=seal["populations"],
                rows=seal["rows"],
                batches=seal["batches"],
                input_seal=artifact(folder / "INPUT_SEAL.json"),
                reference_admission=artifact(folder / "ADMISSION.json"),
                sources=gate["source_sha256"],
                actual_shape_plan=plan,
                card_sha256=sha(HERE / "DIAGNOSTIC_CARD.json"),
            ),
        )
    elif phase == "encode":
        plan = read(out / "formal/ENCODING_PLAN.json")
        require(
            0 <= int(arg) < plan["shards"] and read(out / "PREPARATION.json")["status"] == "PASS",
            "ENCODE_DAG",
        )
        encode_shard(project, out / "formal", freeze, int(arg), plan["shards"], log)
    elif phase == "evaluate":
        folder = out / "formal"
        subprocess_stage("score", project, out, folder)
        subprocess_stage("metrics", project, out, folder)
        ev = read(folder / "EVALUATION.json")
        require(ev["status"] == "PASS" and not ev["pilot"], "FORMAL_EVALUATION")
        import shutil

        for n, spec in ev["small_outputs"].items():
            require(artifact(folder / n) == spec, "FORMAL_TABLE_SHA")
            shutil.copyfile(folder / n, out / n)
        from report_ton import verify, paper

        checked = verify(out, card)
        require(checked == ev["checks"], "TABLE_READBACK")
        (out / "RESULTS_FOR_PAPER.md").write_text(paper(out, card), encoding="utf-8")
        assets = {
            name: dict(path=str(folder / name), **artifact(folder / name))
            for name in (
                "snapshots.sqlite",
                "ORDERED_E3.npy",
                "RAW.npy",
                "INPUT_SEAL.json",
                "RAW_PROOF.json",
                "ENCODING_PLAN.json",
            )
        }
        assets.update({host: v for host, v in ev["large_decision_arrays"].items()})
        assets["encoded_blocks"] = [
            p for f in sorted((folder / "encoded").glob("*/COMPLETE.json")) for p in read(f)["blocks"]
        ]
        dump(out / "HPC_ARTIFACT_SHA.json", assets)
        dump(
            out / "SCIENCE.json",
            dict(
                ev,
                job_id=os.environ["SLURM_JOB_ID"],
                pilot_job=read(out / "PREFLIGHT.json")["job_id"],
                input_seal=artifact(folder / "INPUT_SEAL.json"),
                artifact_index=artifact(out / "HPC_ARTIFACT_SHA.json"),
                paper=artifact(out / "RESULTS_FOR_PAPER.md"),
                package_sha256=sha(HERE / "PACKAGE_MANIFEST.json"),
            ),
        )
    else:
        raise ValueError("UNKNOWN_PHASE")
    log("COMPLETE", 1, 1, force=True, description="本阶段已写出回执")


if __name__ == "__main__":
    phase, project, target, arg = sys.argv[1:]
    out = Path(target)
    key = phase if phase != "encode" else "encode-" + arg
    start = time.monotonic()
    try:
        phase_main(phase, Path(project), out, arg)
    except Exception as e:
        dump(
            out / ("FAILURE_" + key + ".json"),
            dict(
                error=str(e), traceback=traceback.format_exc(), phase=key, job=os.environ.get("SLURM_JOB_ID")
            ),
        )
        raise
    finally:
        dump(
            out / "resources" / (key + ".json"),
            dict(
                phase=key,
                job=os.environ.get("SLURM_JOB_ID"),
                elapsed=time.monotonic() - start,
                own_peak_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                child_peak_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
            ),
        )
