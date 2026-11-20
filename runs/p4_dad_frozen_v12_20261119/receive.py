"""Resume the scoped upload and verify every registered small result on D."""

from pathlib import Path
import subprocess
from transport import channel, HERE
from dad_stats import SMALL, require, load_tables, paper


def save(path, obj):
    import json, os

    path = Path(path)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes((json.dumps(obj, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode())
    tmp.replace(path)


def pull(c, remote, manifest):
    dest = HERE / "received"
    require(dest.resolve().drive.upper() == "D:", "DESTINATION_DRIVE")
    dest.mkdir(exist_ok=True)
    files = manifest["files"]
    require(files and set(files) <= SMALL, "SMALL_FILE_ALLOWLIST")
    for n, s in files.items():
        require(n == s["file"] == Path(n).name and 0 <= s["bytes"] < 32 * 1024**2, "RETURN_FILENAME_SIZE")
        path = dest / n
        if not path.exists() or path.stat().st_size != s["bytes"] or channel.digest(path) != s["sha256"]:
            c.request("file-dual-" + n, destination=(path, s), timeout=90)
        require(channel.digest(path) == s["sha256"] and path.stat().st_size == s["bytes"], "LOCAL_SHA:" + n)
    save(dest / "RETURN.json", manifest)
    if remote["chain"]["stage"] == "STOP":
        channel.state("STOP", remote=remote, local_files=len(files))
        return
    a = channel.read(dest / "ACCEPTANCE.json")
    f = channel.read(dest / "FORMAL.json")
    require(
        a == remote["acceptance"]
        and a["status"] == "PASS"
        and a["science"] == files["FORMAL.json"]
        and a["preflight"] == files["PREFLIGHT.json"]
        and a["queries"] == 18317
        and a["package_sha256"] == channel.digest(HERE / "PACKAGE_MANIFEST.json")
        and all(files[n] == v for n, v in f["outputs"].items()),
        "MATCH_SIGNED_RETURN",
    )
    rows, counts = load_tables(dest)
    require(
        a["checks"] == counts and (dest / "RESULTS_FOR_PAPER.md").read_text(encoding="utf8") == paper(rows),
        "LOCAL_RECOUNT",
    )
    for phase, job in a["jobs"].items():
        s = channel.read(dest / f"SCHEDULER_{phase}.json")
        require(
            s["job_id"] == job
            and s["state"] == "COMPLETED"
            and any(
                x.split("|")[:3] == [job, "COMPLETED", "0:0"] for x in s["account"]["stdout"].splitlines()
            ),
            "SLURM_RECEIPT",
        )
    save(
        dest / "LOCAL_ACCEPTANCE.json",
        dict(
            status="PASS",
            jobs=a["jobs"],
            files=len(files),
            queries=18317,
            checks=counts,
            return_sha256=channel.digest(dest / "RETURN.json"),
            package_sha256=a["package_sha256"],
        ),
    )
    try:
        from archive_dad import publish

        backup = dict(status="PUSHED", commit=publish("results"))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        backup = dict(status="PENDING", error=str(exc))
    save(dest / "BACKUP_STATUS.json", backup)
    channel.state("ACCEPTED", remote=remote, local_files=len(files), backup=backup)


if __name__ == "__main__":
    channel.save = save
    channel.receive = pull
    try:
        require(
            channel.digest(HERE / ".private/package.tar.gz")
            == channel.read(HERE / "LOCAL_VALIDATION.json")["archive_sha256"],
            "LOCAL_PACKAGE_UNCHECKED",
        )
        channel.watch()
    except Exception as e:
        channel.state("LOCAL_STOP", error=str(e))
        raise
