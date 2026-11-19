"""Stage approved inputs and submit only receipt-qualified Slurm phases."""

import fcntl
import getpass
from pathlib import Path
import subprocess
import sys
import time
import traceback

from asset_ingress import ensure
from common_ton import HERE, RUN, artifact, dump, read, require, sha
from report_ton import verify, paper
from launch_names import SMALL_OUTPUTS

FAIL = {
    "FAILED",
    "CANCELLED",
    "TIMEOUT",
    "OUT_OF_MEMORY",
    "NODE_FAIL",
    "PREEMPTED",
    "BOOT_FAIL",
    "DEADLINE",
    "REVOKED",
}
PHASES = ("preflight", "prepare", "encode", "evaluate")


def run_cmd(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=75)
    return dict(code=r.returncode, stdout=r.stdout, stderr=r.stderr)


def scheduler_read(args):
    for attempt in range(3):
        try:
            p = run_cmd(args)
            if p["code"] == 0:
                return p
        except subprocess.TimeoutExpired:
            pass
        time.sleep(2 + attempt)
    return dict(code=1, stdout="", stderr="scheduler read temporarily unavailable")


def job_submit(project, out, phase, argument, wall):
    suffix = phase if phase != "encode" else f"enc{int(argument):02d}"
    name = "p04-tonpw18-" + suffix
    jobs = out / "jobs"
    jobs.mkdir(exist_ok=True)
    receipt = jobs / (suffix + ".json")
    intent = jobs / (suffix + "_intent.json")
    user = getpass.getuser()
    q = scheduler_read(["squeue", "-h", "-u", user, "-o", "%i|%j"])
    a = scheduler_read(
        ["sacct", "-X", "-n", "-P", "-u", user, "-S", "2026-11-18", "-o", "JobIDRaw,JobName%80"]
    )
    require(q["code"] == a["code"] == 0, "DUPLICATE_JOB_LOOKUP")
    matches = {
        r[0]
        for text in (q["stdout"], a["stdout"])
        for l in text.splitlines()
        for r in [l.strip().split("|")]
        if len(r) >= 2 and r[0].isdigit() and r[1] == name
    }
    if receipt.exists():
        job = read(receipt)["job_id"]
        require(intent.exists() and matches <= {job}, "EXISTING_JOB_CONFLICT")
        return job
    if intent.exists():
        require(len(matches) == 1, "SUBMISSION_INTENT_NEEDS_RECONCILIATION:" + suffix)
        job = matches.pop()
    else:
        require(not matches, "EXISTING_UNBOUND_JOB:" + name)
        hh, rem = divmod(int(wall), 3600)
        mm, ss = divmod(rem, 60)
        argv = [
            "sbatch",
            "--no-requeue",
            "--partition=amd",
            "--nodes=1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--mem=16384M",
            f"--time={hh:02d}:{mm:02d}:{ss:02d}",
            "--job-name=" + name,
            "--chdir=" + str(HERE),
            "--output=" + str(jobs / (suffix + "-%j.out")),
            "--error=" + str(jobs / (suffix + "-%j.err")),
            str(HERE / "run.slurm"),
            phase,
            str(project),
            str(out),
            str(argument),
        ]
        test = run_cmd(["sbatch", "--test-only", *argv[1:]])
        dump(jobs / (suffix + "_test.json"), test)
        require(test["code"] == 0, "SBATCH_TEST_ONLY:" + test["stderr"])
        dump(intent, dict(argv=argv, unix=time.time()))
        r = run_cmd(["sbatch", "--parsable", *argv[1:]])
        job = r["stdout"].strip().split(";")[0]
        require(r["code"] == 0 and job.isdigit(), "SBATCH_SUBMIT:" + r["stderr"])
    dump(receipt, dict(job_id=job, name=name, phase=phase, argument=argument, wall_seconds=wall))
    return job


def scheduler(ids):
    q = scheduler_read(["squeue", "-h", "-u", getpass.getuser(), "-o", "%i|%T|%R"])
    a = scheduler_read(
        [
            "sacct",
            "-n",
            "-P",
            "-j",
            ",".join(ids),
            "-o",
            "JobIDRaw,State%32,ExitCode,ElapsedRaw,TotalCPU,MaxRSS,AllocCPUS,ReqMem",
        ]
    )
    queue = {r[0]: r for l in q["stdout"].splitlines() for r in [l.split("|")] if len(r) >= 2}
    lines = [r for l in a["stdout"].splitlines() for r in [l.split("|")] if len(r) >= 3]
    return {
        job: dict(
            job_id=job,
            account_rows=[r for r in lines if r[0] == job or r[0].startswith(job + ".")],
            queue=queue.get(job),
        )
        for job in ids
    }


def job_state(s):
    main = next((r for r in s["account_rows"] if r[0] == s["job_id"]), None)
    status = main[1].split()[0].rstrip("+") if main else "SUBMITTED"
    if status == "COMPLETED":
        return status if main[2] == "0:0" else "FAILED"
    return s["queue"][1] if s["queue"] and status not in FAIL else status


def manifest(out):
    files = {n: artifact(out / n) for n in sorted(SMALL_OUTPUTS) if (out / n).is_file()}
    require(all(p["bytes"] < 32 * 1024**2 for p in files.values()), "BOUNDED_RETURN_ONLY")
    dump(out / "RETURN.json", dict(files=files))


def controller(project, out):
    require(HERE == out / "package" and out == project / "runs" / RUN, "CONTROLLER_SCOPE")
    tasks = {p: dict(state="WAIT") for p in PHASES}
    jobs = {}
    records = {}

    def live(stage, **kwargs):
        dump(out / "CHAIN_STATE.json", dict(stage=stage, tasks=tasks, updated_unix=time.time(), **kwargs))

    def track(phase, running):
        outcomes = scheduler(list(running.values()))
        for idx, job in running.items():
            s = outcomes[job]
            s["state"] = job_state(s)
            records[job] = s
            if s["state"] in FAIL:
                raise RuntimeError(f"{phase} Slurm {job} {s['state']}")
        dump(out / "SCHEDULER.json", records)
        return {k: records[j]["state"] for k, j in running.items()}

    def tick(phase, status_name):
        keys = [status_name]
        if phase in ("evaluate", "preflight"):
            keys += ["score", "metrics"]
        found = [
            read(out / "status" / k / "PROGRESS.json")
            for k in keys
            if (out / "status" / k / "PROGRESS.json").is_file()
        ]
        return max(found, key=lambda r: r["updated_unix"]) if found else {}

    def single(phase, wall):
        jobs[phase] = job_submit(project, out, phase, "-", wall)
        job = jobs[phase]
        tasks[phase] = dict(state="SUBMITTED", job_id=job)
        live("SUBMITTED")
        while True:
            state = track(phase, {phase: job})[phase]
            tasks[phase] = dict(state=state, job_id=job)
            live(state, progress=tick(phase, phase), raw_ready=(out / "RAW_INFERENCE.json").is_file())
            if state == "COMPLETED":
                return
            time.sleep(12)

    with (out / ".dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (out / "ACCEPTANCE.json").is_file():
            return
        try:
            live("VERIFY_INPUTS")
            cfg = read(HERE / "SCOPED_INPUTS.json")
            card = read(HERE / "DIAGNOSTIC_CARD.json")
            freeze = read(HERE / "FROZEN.json")
            original = project / freeze["runtime_package"]
            require(
                sha(original / "PACKAGE_MANIFEST.json") == freeze["runtime_manifest_sha256"],
                "FROZEN_HPC_RUNTIME_MANIFEST",
            )
            head_pins = {}
            for seed in ("27", "127", "227"):
                pin = freeze["extra_pins"]["head_" + seed]
                path = next(
                    (
                        project / n
                        for n in pin["paths"]
                        if (project / n).is_file() and sha(project / n) == pin["sha256"]
                    ),
                    None,
                )
                require(path is not None, "FROZEN_HPC_MLP_HEAD:" + seed)
                head_pins[seed] = dict(path=str(path), **artifact(path))
            dump(
                out / "MODEL_FREEZE_CHECK.json",
                dict(
                    status="PASS",
                    heads=head_pins,
                    cuts=freeze["method"]["cuts"],
                    scales=freeze["method"]["scales"],
                    runtime_sha256=freeze["runtime_manifest_sha256"],
                ),
            )
            ensure(project, out, cfg["sources"], live)
            single("preflight", 7200)
            pre = read(out / "PREFLIGHT.json")
            require(
                pre["status"] == "PASS"
                and pre["job_id"] == jobs["preflight"]
                and pre["real_inputs"] > 0
                and pre["original_head_witness"]["head_decision_differences"] == [0] * 4
                and pre["package_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json"),
                "PILOT_RECEIPT_BEFORE_FORMAL",
            )
            single("prepare", pre["prepare_wall_seconds"])
            prep = read(out / "PREPARATION.json")
            require(
                prep["job_id"] == jobs["prepare"]
                and prep["pilot_job"] == jobs["preflight"]
                and prep["rows"] > 0
                and prep["card_sha256"] == sha(HERE / "DIAGNOSTIC_CARD.json"),
                "QUERY_REFERENCE_SEAL",
            )
            plan = prep["actual_shape_plan"]
            remaining = list(range(plan["shards"]))
            active = {}
            completed = {}
            while remaining or active:
                while remaining and len(active) < plan["parallel_jobs"]:
                    i = remaining.pop(0)
                    active[i] = job_submit(project, out, "encode", i, plan["wall_seconds"])
                states = track("encode", active)
                progress = []
                for i, v in list(states.items()):
                    if v == "COMPLETED":
                        rec = read(out / "formal/encoded" / f"{i:03d}" / "COMPLETE.json")
                        require(
                            rec["status"] == "PASS"
                            and rec["index"] == i
                            and rec["input_sha256"] == plan["input_sha256"],
                            "SHARD_COMPLETION",
                        )
                        completed[str(i)] = active.pop(i)
                    else:
                        progress.append(tick("encode", "encode-" + str(i)))
                tasks["encode"] = dict(
                    state="RUNNING" if active or remaining else "COMPLETED",
                    job_id=",".join(active.values()) if active else ",".join(completed.values()),
                    completed=len(completed),
                    total=plan["shards"],
                )
                live(
                    "RUNNING",
                    progress=dict(
                        description=f"冻结编码分片 {len(completed)}/{plan['shards']} 完成",
                        done=len(completed),
                        total=plan["shards"],
                        workers=progress,
                    ),
                )
                if active:
                    time.sleep(12)
            jobs["encode"] = completed
            dump(out / "ENCODING_RECEIPT.json", dict(status="PASS", jobs=completed, plan=plan))
            single("evaluate", 4 * 3600)
            sc = read(out / "SCIENCE.json")
            require(
                sc["status"] == "PASS"
                and sc["job_id"] == jobs["evaluate"]
                and sc["pilot_job"] == jobs["preflight"]
                and sc["package_sha256"] == pre["package_sha256"]
                and sc["checks"] == verify(out, card)
                and sc["paper"] == artifact(out / "RESULTS_FOR_PAPER.md")
                and sc["artifact_index"] == artifact(out / "HPC_ARTIFACT_SHA.json"),
                "FORMAL_ACCEPTANCE",
            )
            require(
                all(artifact(out / n) == v for n, v in sc["small_outputs"].items())
                and (out / "RESULTS_FOR_PAPER.md").read_text(encoding="utf8") == paper(out, card),
                "FORMAL_OUTPUT_INTEGRITY",
            )
            dump(out / "RESOURCES.json", {p.stem: read(p) for p in (out / "resources").glob("*.json")})
            dump(
                out / "ACCEPTANCE.json",
                dict(
                    status="PASS",
                    jobs=jobs,
                    package_sha256=pre["package_sha256"],
                    card_sha256=sha(HERE / "DIAGNOSTIC_CARD.json"),
                    checks=sc["checks"],
                    science=artifact(out / "SCIENCE.json"),
                    paper=sc["paper"],
                    arrays=sc["artifact_index"],
                    model_updates=0,
                    threshold_changes=0,
                ),
            )
            manifest(out)
            live("COMPLETE")
        except Exception as e:
            dumps = {p.name: read(p) for p in out.glob("FAILURE_*.json") if p.name != "FAILURE_DETAIL.json"}
            dump(out / "FAILURE_DETAIL.json", dumps)
            dump(
                out / "CONTROLLER_FAILURE.json",
                dict(error=str(e), traceback=traceback.format_exc(), jobs=jobs),
            )
            manifest(out)
            live("STOP", error=str(e))
            raise


if __name__ == "__main__":
    controller(*map(Path, sys.argv[1:]))
