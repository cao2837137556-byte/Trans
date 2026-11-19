"""Run the D-drive receiver and supply only SHA-matched existing files requested by the HPC inventory."""

from hashlib import sha256
import http.client
from pathlib import Path
import subprocess
import time
import zlib

from common_ton import HERE, RUN, artifact, dump, read, require, sha
from report_ton import verify, paper
from transport_ton import config, get_client, INPUT_PORT


def state(stage, **v):
    dump(HERE / "LOCAL_PROGRESS.json", dict(stage=stage, updated_unix=time.time(), **v))


def receive(channel, remote):
    from launch_names import SMALL_OUTPUTS

    man = channel.request("manifest-ton")
    files = man["files"]
    dest = HERE / "received"
    require(dest.resolve().drive.upper() == "D:", "D_DRIVE_DESTINATION")
    dest.mkdir(exist_ok=True)
    require(files and set(files) <= set(SMALL_OUTPUTS), "REGISTERED_SMALL_RESULTS")
    for n, s in files.items():
        require(n == Path(n).name == s["file"] and s["bytes"] < 32 * 1024**2, "RESULT_SCOPE")
        p = dest / n
        if not p.exists() or artifact(p) != s:
            channel.request("file-ton-" + n, destination=(p, s), timeout=90)
        require(artifact(p) == s, "RETURN_SHA:" + n)
    dump(dest / "RETURN.json", man)
    if remote["chain"]["stage"] == "STOP":
        state("STOP", remote=remote, local_files=len(files))
        return
    a = read(dest / "ACCEPTANCE.json")
    sc = read(dest / "SCIENCE.json")
    card = read(HERE / "DIAGNOSTIC_CARD.json")
    require(
        a == remote["acceptance"]
        and a["status"] == "PASS"
        and a["card_sha256"] == sha(HERE / "DIAGNOSTIC_CARD.json")
        and a["package_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json")
        and a["science"] == files["SCIENCE.json"]
        and a["paper"] == files["RESULTS_FOR_PAPER.md"]
        and a["arrays"] == files["HPC_ARTIFACT_SHA.json"]
        and all(files[n] == v for n, v in sc["small_outputs"].items()),
        "ACCEPTED_REMOTE_AND_LOCAL_IDENTITY",
    )
    sched = read(dest / "SCHEDULER.json")
    jobs = a["jobs"]
    for job in (jobs["preflight"], jobs["prepare"], jobs["evaluate"], *jobs["encode"].values()):
        r = sched[job]
        require(
            r["state"] == "COMPLETED" and any(v[:3] == [job, "COMPLETED", "0:0"] for v in r["account_rows"]),
            "SLURM_EXIT",
        )
    checks = verify(dest, card)
    require(
        checks == a["checks"]
        and (dest / "RESULTS_FOR_PAPER.md").read_text(encoding="utf8") == paper(dest, card),
        "INDEPENDENT_LOCAL_TABLE_RECOUNT",
    )
    dump(
        dest / "LOCAL_ACCEPTANCE.json",
        dict(
            status="PASS",
            jobs=jobs,
            checks=checks,
            files=len(files),
            manifest_sha256=sha(dest / "RETURN.json"),
            package_sha256=a["package_sha256"],
        ),
    )
    try:
        from archive_ton import publish

        backup = dict(status="PUSHED", commit=publish("results"))
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as e:
        backup = dict(status="PENDING", error=str(e))
    dump(dest / "BACKUP_STATUS.json", backup)
    state("ACCEPTED", remote=remote, local_files=len(files), backup=backup)


def transfer(channel, remote, verified):
    cfg = read(HERE / "SCOPED_INPUTS.json")["sources"]
    paths = read(HERE / ".private/LOCAL_INPUTS.json")
    inventory = channel.request("state", timeout=10)
    require(inventory["run"] == RUN, "INGRESS_SCOPE")
    needed = inventory["needed"]
    total = sum(v["bytes"] for v in needed.values())
    done = sum(v["offset"] for v in needed.values())
    for key, s in needed.items():
        p = Path(paths[key])
        pin = cfg[key]
        require(
            s["bytes"] == pin["bytes"] and s["sha256"] == pin["sha256"] and 0 <= s["offset"] <= s["bytes"],
            "INPUT_SCOPE",
        )
        if key not in verified:
            require(p.stat().st_size == pin["bytes"] and sha(p) == pin["sha256"], "LOCAL_EXISTING_INPUT_SHA")
            verified.add(key)
        with p.open("rb") as f:
            offset = s["offset"]
            f.seek(offset)
            while data := f.read(4 << 20):
                zipped = zlib.compress(data, 1)
                compress = len(zipped) < len(data)
                headers = {
                    "X-Offset": str(offset),
                    "X-SHA256": sha256(data).hexdigest(),
                    "X-Raw-Bytes": str(len(data)),
                }
                if compress:
                    headers["Content-Encoding"] = "deflate"
                reply = channel.request(
                    "put-" + key, "POST", zipped if compress else data, headers, timeout=120
                )
                offset += len(data)
                done += len(data)
                require(reply["offset"] == offset, "UPLOAD_RECEIPT_OFFSET")
                state(
                    "AWAITING_EXISTING_ASSETS",
                    remote=remote,
                    note=f"正在交付已有的 {pin['file']}，{done / 2**20:,.0f} / {total / 2**20:,.0f} MiB",
                    uploaded_raw_bytes=done,
                    total_raw_bytes=total,
                )


def main():
    api = get_client()
    connect = api.transport()
    port = None
    last = None
    verified = set()
    integrity_retry = False
    archive = HERE / ".private/package.tar.gz"
    pack_sha = sha(archive)
    require(pack_sha == read(HERE / "LOCAL_VALIDATION.json")["archive_sha256"], "ONLY_VALIDATED_PACKAGE")
    while True:
        try:
            ports = [port] if port is not None else api.ssh_socks_ports()
            channel = None
            for candidate in ports:
                c = api.Relay(config(), candidate, connect)
                try:
                    remote = c.request("state-ton", timeout=8)
                except (OSError, http.client.HTTPException):
                    continue
                channel = c
                port = candidate
                break
            if channel is None:
                state(
                    "CONNECTION_PAUSED" if last else "WAITING_TERMINAL" if ports else "WAITING_SSH",
                    remote=last,
                )
                port = None
                time.sleep(10)
                continue
            if not remote.get("install"):
                state("UPLOADING", note="正在交付已封存的实验包")
                install = channel.request(
                    "install-ton", "POST", archive.read_bytes(), {"X-SHA256": pack_sha}, timeout=100
                )
                require(
                    install["archive_sha256"] == pack_sha
                    and install["manifest_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json"),
                    "INSTALL_RECEIPT",
                )
                dump(HERE / "INSTALL_READBACK.json", install)
                remote = channel.request("state-ton")
            i = remote["install"]
            require(
                i["run"] == RUN
                and i["archive_sha256"] == pack_sha
                and i["manifest_sha256"] == sha(HERE / "PACKAGE_MANIFEST.json"),
                "REMOTE_RUN_IDENTITY",
            )
            if not (HERE / "INSTALL_READBACK.json").exists():
                dump(HERE / "INSTALL_READBACK.json", i)
            last = remote
            chain = remote.get("chain") or {}
            stage = chain.get("stage", "INSTALLED")
            state(stage, remote=remote)
            if (
                chain.get("raw_ready")
                and stage not in ("COMPLETE", "STOP")
                and not (HERE / "received/RAW_INFERENCE.json").is_file()
            ):
                early = channel.request("manifest-ton")
                if early and {"RAW_INFERENCE.json", "RAW_TARGETS.csv"} <= set(early["files"]):
                    dest = HERE / "received"
                    require(dest.resolve().drive.upper() == "D:", "D_DRIVE_DESTINATION")
                    dest.mkdir(exist_ok=True)
                    for n in ("RAW_TARGETS.csv", "RAW_INFERENCE.json"):
                        pin = early["files"][n]
                        require(n == pin["file"] and pin["bytes"] < 32 * 1024**2, "RAW_RECEIPT_SCOPE")
                        channel.request("file-ton-" + n, destination=(dest / n, pin), timeout=90)
                        require(artifact(dest / n) == pin, "EARLY_RAW_SHA")
            if stage == "AWAITING_EXISTING_ASSETS" and (chain.get("inputs") or {}).get("needed"):
                transfer(api.Relay(config(INPUT_PORT), port, connect), remote, verified)
            if stage in ("COMPLETE", "STOP"):
                state("VERIFYING_RETURN", remote=remote)
                receive(channel, remote)
                return
            time.sleep(6)
        except (OSError, http.client.HTTPException, subprocess.TimeoutExpired):
            port = None
            state("CONNECTION_PAUSED", remote=last)
            time.sleep(6)
        except ValueError as e:
            if "OFFSET" in str(e) and "RELAY_ACTION_REJECTED" in str(e):
                time.sleep(2)
                continue
            if "COMPLETE_INPUT_SHA" in str(e) and not integrity_retry:
                integrity_retry = True
                verified.clear()
                time.sleep(2)
                continue
            raise


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        state("LOCAL_STOP", error=str(e))
        raise
