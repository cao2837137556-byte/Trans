"""Dispatch the two cache-only phases after verifying their run identity."""

import fcntl
import getpass
from pathlib import Path
import sys
import time
import traceback

from common_round1 import artifact, dump, load, sha, verify_artifact
from result_checks import SMALL, tables_read, paper, require
from slurm_base import command, wait_job, live

HERE = Path(__file__).resolve().parent
RUN = "p4_ton_connection_lambda_v1_20261119"


def submit(project, out, phase, wall):
    name = "p04-tcl19-" + phase
    user = getpass.getuser()
    snapshots = [
        command(["squeue", "-h", "-u", user, "-o", "%i|%j"]),
        command(["sacct", "-X", "-n", "-P", "-S", "2026-11-19", "-u", user, "-o", "JobIDRaw,JobName%80"]),
    ]
    require(all(v["returncode"] == 0 for v in snapshots), "SLURM_LOOKUP")
    matches = {
        r[0]
        for s in snapshots
        for line in s["stdout"].splitlines()
        for r in [line.split("|")]
        if len(r) >= 2 and r[1] == name and r[0].isdigit()
    }
    jobfile = out / f"JOB_{phase}.json"
    intent = out / f"SUBMIT_INTENT_{phase}.json"
    if jobfile.is_file():
        job = load(jobfile)["job_id"]
        require(intent.exists() and matches <= {job}, "AMBIGUOUS_JOB")
        return job
    if intent.exists():
        require(len(matches) == 1, "SUBMISSION_INTENT_WITHOUT_UNIQUE_JOB")
        job = matches.pop()
    else:
        require(not matches, "ALREADY_REGISTERED_JOB")
        hh, rem = divmod(wall, 3600)
        mm, ss = divmod(rem, 60)
        args = [
            "sbatch",
            "--partition=amd",
            "--no-requeue",
            "--nodes=1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--mem=4096M",
            f"--time={hh:02d}:{mm:02d}:{ss:02d}",
            "--job-name=" + name,
            "--chdir=" + str(HERE),
            "--output=" + str(out / (phase + "-%j.out")),
            "--error=" + str(out / (phase + "-%j.err")),
            str(HERE / "run.slurm"),
            phase,
            str(project),
            str(out),
        ]
        check = command(["sbatch", "--test-only", *args[1:]])
        dump(out / f"TEST_ONLY_{phase}.json", check)
        require(check["returncode"] == 0, "SBATCH_TEST_ONLY:" + check["stderr"])
        dump(intent, dict(timestamp=time.time(), argv=args))
        call = command(["sbatch", "--parsable", *args[1:]])
        dump(out / f"SBATCH_{phase}.json", call)
        job = call["stdout"].strip().split(";")[0]
        require(call["returncode"] == 0 and job.isdigit(), "SBATCH:" + call["stderr"])
    dump(jobfile, dict(job_id=job, phase=phase, job_name=name, requested_wall_seconds=wall))
    return job


def manifest(out):
    files = {n: artifact(out / n) for n in sorted(SMALL) if (out / n).is_file()}
    require(all(v["bytes"] < 32 * 1024**2 for v in files.values()), "RESULT_SIZE")
    dump(out / "RETURN.json", dict(files=files))


def main(project, out):
    require(out == project / "runs" / RUN and HERE == out / "package", "EXPERIMENT_SCOPE")
    with (out / ".controller.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (out / "ACCEPTANCE.json").exists():
            return
        try:
            live(out, "VALIDATE_SUBMISSION", phase="preflight")
            mh = sha(HERE / "PACKAGE_MANIFEST.json")
            for n, h in load(HERE / "PACKAGE_MANIFEST.json")["files"].items():
                require(sha(HERE / n) == h, "PACKAGE_SHA:" + n)
            jobs = {}
            for phase in ("preflight", "formal"):
                jobs[phase] = submit(project, out, phase, 3600)
                wait_job(out, phase, jobs[phase])
                result = load(out / ("PREFLIGHT.json" if phase == "preflight" else "FORMAL.json"))
                require(
                    result["status"] == "PASS"
                    and result["job_id"] == jobs[phase]
                    and result["package_sha256"] == mh,
                    "PHASE_RECEIPT",
                )
                if phase == "preflight":
                    require(
                        result["rows"] > 0
                        and result["literal_flag_rows"] > 0
                        and len(result["slice_witness"]) == 4,
                        "REAL_CONNECTION_SLICE",
                    )
            for p in result["outputs"].values():
                verify_artifact(out, p)
            tables, checks = tables_read(out)
            require(
                checks == result["checks"]
                and paper(*tables) == (out / "RESULTS_FOR_PAPER.md").read_text(encoding="utf8"),
                "FINAL_RECOUNT",
            )
            dump(
                out / "ACCEPTANCE.json",
                dict(
                    status="PASS",
                    jobs=jobs,
                    queries=result["rows"],
                    package_sha256=mh,
                    checks=checks,
                    preflight=artifact(out / "PREFLIGHT.json"),
                    science=artifact(out / "FORMAL.json"),
                    source_job="185491",
                ),
            )
            manifest(out)
            live(out, "COMPLETE", jobs=jobs, job_id=jobs["formal"])
        except Exception as e:
            dump(out / "CONTROLLER_FAILURE.json", dict(error=str(e), traceback=traceback.format_exc()))
            manifest(out)
            live(out, "STOP", error=str(e))
            raise


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:]))
