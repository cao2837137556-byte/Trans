"""Submit all three formal jobs after a successful, receipt-verified Slurm pilot."""

import fcntl
import getpass
from pathlib import Path
import sys
import time
import traceback

import slurm_base as scheduler
from common_round1 import artifact, dump, load, require, sha, verify_artifact
from accept_v12 import TASKS, paper, verify_results

HERE = Path(__file__).resolve().parent
RUN = "p4_group_threshold_k1_v1_20261118"
NAMES = dict(
    preflight="p04-v12n18-pre", groups="p04-v12n18-group", k1="p04-v12n18-k1", ports="p04-v12n18-ports"
)
scheduler.NAMES = NAMES
OUTPUTS = (
    "GROUP_HEADLINE.csv",
    "GROUP_METRICS.csv",
    "GROUP_PAIRS.csv",
    "GROUP_THRESHOLDS.json",
    "K1_HEADLINE.csv",
    "K1_METRICS.csv",
    "K1_PAIRS.csv",
    "K1_PATHWAYS.csv",
    "PORT_HEADLINE.csv",
    "PORT_BY_DEVICE.csv",
)


def state(out, stage, tasks, error=None):
    dump(out / "CHAIN_STATE.json", dict(stage=stage, tasks=tasks, updated_unix=time.time(), error=error))


def wait(out, phases, jobs, tasks):
    remaining = set(phases)
    ids = ",".join(jobs[p] for p in phases)
    while remaining:
        q = scheduler.command(["squeue", "-h", "-u", getpass.getuser(), "-o", "%i|%T|%R"])
        a = scheduler.command(
            [
                "sacct",
                "-n",
                "-P",
                "-j",
                ids,
                "-o",
                "JobIDRaw,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem",
            ]
        )
        queue = {x[0]: x for row in q["stdout"].splitlines() for x in [row.split("|")] if len(x) >= 2}
        account = [x for row in a["stdout"].splitlines() for x in [row.split("|")] if len(x) >= 3]
        for phase in sorted(remaining):
            job = jobs[phase]
            rows = [x for x in account if x[0] == job]
            flag = rows[-1][1].split()[0].rstrip("+") if rows else "SUBMITTED"
            if job in queue and flag != "COMPLETED" and flag not in scheduler.FAIL:
                flag = queue[job][1]
            specific = [x for x in account if x[0] == job or x[0].startswith(job + ".")]
            dump(
                out / f"SCHEDULER_{phase}.json",
                dict(
                    job_id=job,
                    state=flag,
                    account_rows=specific,
                    queue=queue.get(job),
                    updated_unix=time.time(),
                ),
            )
            progress = out / phase / "PROGRESS.json"
            tasks[phase] = dict(
                job_id=job, state=flag, progress=load(progress) if progress.exists() else None
            )
            if flag in scheduler.FAIL or flag == "COMPLETED":
                if flag == "COMPLETED" and rows[-1][2] != "0:0":
                    tasks[phase]["state"] = "FAILED"
                remaining.remove(phase)
        state(out, "PARALLEL" if len(phases) > 1 else tasks[phases[0]]["state"], tasks)
        if remaining:
            time.sleep(12)
    require(
        all(tasks[p]["state"] == "COMPLETED" for p in phases),
        "SLURM_FAILURE:" + str({p: tasks[p]["state"] for p in phases if tasks[p]["state"] != "COMPLETED"}),
    )


def return_manifest(out):
    names = set(OUTPUTS) | {
        "INSTALL.json",
        "PREFLIGHT.json",
        "RESULTS_FOR_PAPER.md",
        "ACCEPTANCE.json",
        "CONTROLLER_FAILURE.json",
    }
    for p in TASKS:
        for prefix in (
            "JOB",
            "SCHEDULER",
            "SBATCH",
            "TEST_ONLY",
            "SUBMIT_INTENT",
            "FAILURE",
            "SLURM_STOP",
            "RESOURCES",
            "RUNTIME",
            "SCIENCE",
        ):
            names.add(prefix + "_" + p + ".json")
    files = {name: artifact(out / name) for name in sorted(names) if (out / name).is_file()}
    require(all(v["bytes"] < 32 * 1024**2 for v in files.values()), "SMALL_RETURN_BOUND")
    dump(out / "RETURN.json", dict(files=files))


def run(project, out):
    require(out == project / "runs" / RUN and HERE == out / "package", "SCOPED_OUTPUT")
    with (out / ".dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (out / "ACCEPTANCE.json").is_file():
            return
        jobs = {}
        tasks = {p: dict(state="READY" if p == "preflight" else "WAIT") for p in TASKS}
        try:
            state(out, "SUBMITTING", tasks)
            jobs["preflight"] = scheduler.submission(project, out, "preflight")
            wait(out, ["preflight"], jobs, tasks)
            pre = load(out / "PREFLIGHT.json")
            require(
                pre["status"] == "PASS"
                and pre["job_id"] == jobs["preflight"]
                and pre["package_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json")
                and pre["rule_sha256"] == sha(HERE / "EXPERIMENT_CARD.json")
                and pre["actual_frontend"]["actual_forwards"] > 0,
                "REAL_COMPUTE_PREFLIGHT",
            )
            verify_artifact(out, pre["thresholds"])
            for p in pre["pools"].values():
                verify_artifact(out / "artifacts", p["witness"])
            failures = {}
            for phase in TASKS[1:]:
                try:
                    jobs[phase] = scheduler.submission(project, out, phase)
                    tasks[phase] = dict(job_id=jobs[phase], state="SUBMITTED")
                except Exception as e:
                    failures[phase] = str(e)
                    tasks[phase] = dict(state="FAILED", error=str(e))
                state(out, "SUBMITTING", tasks)
            submitted = [p for p in TASKS[1:] if p in jobs]
            if submitted:
                wait(out, submitted, jobs, tasks)
            require(not failures, "FORMAL_SUBMISSION_FAILURE:" + str(failures))
            receipts = {}
            for phase in TASKS[1:]:
                p = out / f"SCIENCE_{phase}.json"
                s = load(p)
                require(
                    s["job_id"] == jobs[phase]
                    and s["preflight_job"] == jobs["preflight"]
                    and s["status"] == "PASS"
                    and s["package_sha256"] == pre["package_sha256"]
                    and s["rule_sha256"] == pre["rule_sha256"]
                    and sum(i["rows"] for i in s["pools"].values()) == 388202,
                    "FORMAL_IDENTITY:" + phase,
                )
                for v in s["outputs"].values():
                    verify_artifact(out, v)
                receipts[phase] = artifact(p)
            checks = verify_results(out, load(HERE / "ASSETS.json"))
            (out / "RESULTS_FOR_PAPER.md").write_text(paper(out, jobs), encoding="utf-8")
            dump(
                out / "ACCEPTANCE.json",
                dict(
                    status="PASS",
                    jobs=jobs,
                    queries=388202,
                    rule_sha256=pre["rule_sha256"],
                    package_sha256=pre["package_sha256"],
                    preflight=artifact(out / "PREFLIGHT.json"),
                    science=receipts,
                    thresholds=pre["thresholds"],
                    checks=checks,
                    paper=artifact(out / "RESULTS_FOR_PAPER.md"),
                ),
            )
            return_manifest(out)
            state(out, "COMPLETE", tasks)
        except Exception as e:
            dump(
                out / "CONTROLLER_FAILURE.json",
                dict(error=str(e), traceback=traceback.format_exc(), jobs=jobs),
            )
            return_manifest(out)
            state(out, "STOP", tasks, error=str(e))
            raise


if __name__ == "__main__":
    run(*map(Path, sys.argv[1:]))
