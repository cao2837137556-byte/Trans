"""Receive only the registered small results into this experiment's D-drive folder."""

from pathlib import Path
import subprocess
import sys

from transport import HERE, transport, save

sys.path.append(str(HERE.parent / "same_information_recalibration_v1_20261113"))
from common_round1 import require
from accept_v12 import TASKS, paper, verify_results

read, digest = transport.read, transport.digest
EXPECTED = {
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
    "INSTALL.json",
    "PREFLIGHT.json",
    "RESULTS_FOR_PAPER.md",
    "ACCEPTANCE.json",
    "CONTROLLER_FAILURE.json",
}


def receive(channel, remote, manifest):
    dest = HERE / "received"
    require(dest.resolve().drive.upper() == "D:", "LOCAL_D_DRIVE_OUTPUT")
    dest.mkdir(exist_ok=True)
    keys = (
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
    )
    allowed = EXPECTED | {k + "_" + p + ".json" for k in keys for p in TASKS}
    files = manifest["files"]
    require(files and set(files) <= allowed, "SMALL_RETURN_SCOPE")
    for n, spec in files.items():
        p = dest / n
        require(
            spec["file"] == n and Path(n).name == n and 0 <= spec["bytes"] < 32 * 1024**2, "RETURN_FILENAME"
        )
        if not p.is_file() or p.stat().st_size != spec["bytes"] or digest(p) != spec["sha256"]:
            channel.request("file-dual-" + n, destination=(p, spec), timeout=90)
        require(digest(p) == spec["sha256"], "LOCAL_SHA:" + n)
    save(dest / "RETURN.json", manifest)
    if remote["chain"]["stage"] == "STOP":
        transport.state("STOP", remote=remote, local_files=len(files))
        return
    acc = read(dest / "ACCEPTANCE.json")
    require(
        acc == remote["acceptance"]
        and acc["status"] == "PASS"
        and acc["queries"] == 388202
        and acc["rule_sha256"] == digest(HERE / "EXPERIMENT_CARD.json")
        and acc["package_sha256"] == digest(HERE / "PACKAGE_MANIFEST.json")
        and acc["paper"] == files["RESULTS_FOR_PAPER.md"]
        and acc["preflight"] == files["PREFLIGHT.json"]
        and acc["thresholds"] == files["GROUP_THRESHOLDS.json"],
        "ACCEPTANCE_DOCUMENTS",
    )
    for phase, job in acc["jobs"].items():
        sched = read(dest / f"SCHEDULER_{phase}.json")
        require(
            sched["state"] == "COMPLETED"
            and sched["job_id"] == job
            and any(row[:3] == [job, "COMPLETED", "0:0"] for row in sched["account_rows"]),
            "SLURM_READBACK",
        )
        if phase != "preflight":
            sc = read(dest / f"SCIENCE_{phase}.json")
            require(
                acc["science"][phase] == files[f"SCIENCE_{phase}.json"]
                and sc["job_id"] == job
                and all(files.get(n) == s for n, s in sc["outputs"].items()),
                "SCIENCE_RETURN_LINKS",
            )
    checks = verify_results(dest, read(HERE / "ASSETS.json"))
    require(
        acc["checks"] == checks
        and (dest / "RESULTS_FOR_PAPER.md").read_text(encoding="utf-8") == paper(dest, acc["jobs"]),
        "D_DRIVE_INDEPENDENT_RECOUNT",
    )
    save(
        dest / "LOCAL_ACCEPTANCE.json",
        dict(
            status="PASS",
            jobs=acc["jobs"],
            files=len(files),
            checks=checks,
            return_sha256=digest(dest / "RETURN.json"),
            package_sha256=acc["package_sha256"],
            queries=acc["queries"],
        ),
    )
    try:
        from publish_v12 import publish

        backup = dict(status="PUSHED", commit=publish("results"))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as e:
        backup = dict(status="PENDING", error=str(e))
    save(dest / "BACKUP_STATUS.json", backup)
    transport.state("ACCEPTED", remote=remote, local_files=len(files), backup=backup)


if __name__ == "__main__":
    transport.receive = receive
    try:
        transport.watch()
    except Exception as e:
        transport.state("LOCAL_STOP", error=str(e))
        raise
