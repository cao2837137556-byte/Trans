"""Sequence the captures, fixed-bank scoring and sealed threshold handoff."""
import argparse
import ctypes
import msvcrt
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from sources import HERE, FORMAL, PILOT, identity, read, save
from controller import wsl, wait_file


def state(out,stage,**details):
    save(out/"RUN_STATUS.json",dict(stage=stage,updated_unix=time.time(),**details))


def command(op,out):
    return ["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
            wsl(HERE/"capture.py"),op,wsl(out)]


def service_alive(out):
    if (out/"COLLECTION_FAILURE.json").exists() or not (out/"COLLECTOR_IDENTITY.json").exists():
        return False
    try:
        return subprocess.run(command("probe",out),capture_output=True,timeout=8).returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


def analysis(mode,out,base):
    subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"assessment.py"),mode,str(out),str(base)],check=True)


def await_completion(out,child):
    done=out/"COLLECTION_DONE.json"
    if child is not None:
        wait_file(done,child,out)
        assert child.wait(timeout=15)==0
        return
    while not done.is_file():
        if (out/"COLLECTION_FAILURE.json").is_file():
            raise RuntimeError(read(out/"COLLECTION_FAILURE.json")["error"])
        p=read(out/"COLLECTION_PROGRESS.json")
        if time.time_ns()-p.get("keeper_heartbeat_ns",0)>30*10**9 and not service_alive(out):
            raise RuntimeError("The original WSL process is unavailable.")
        time.sleep(2)


def run(out,base,resume):
    pre=read(out/"PREFLIGHT.json")
    assert pre["status"]=="PASS" and pre["archive"]==base.name
    assert pre["manifest"]==identity(base/"SHA256SUMS")
    assert pre["reference"]==identity(base/"enrollment/REFERENCE.npz")
    assert shutil.disk_usage(out).free>2*2**30
    power=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        child=None
        if resume:
            status=read(out/"RUN_STATUS.json")["stage"]
            assert status in ("CALIBRATION_PAUSED","HOLDOUT_SCORING_PAUSED")
            if status=="CALIBRATION_PAUSED":
                assert not (out/"holdout").exists() and service_alive(out)
            previous=out/"FAILURE.json"
            with (out/f"scoring_failure_{time.time_ns()}.json").open("xb") as stream:
                stream.write(previous.read_bytes())
        else:
            (out/"METHOD.md").write_bytes((HERE/"METHOD.md").read_bytes())
            sources=[HERE/n for n in ("assessment.py","capture.py","plans.py","runner.py","sources.py","METHOD.md")]
            sources.extend(FORMAL/p for p in ("audit_formal.py","collect_formal.py","bank.py","frozen_score.py"))
            sources.extend(PILOT/p for p in ("collect.py","feature_witness.py"))
            assert not (out/"EXECUTION.json").exists()
            save(out/"EXECUTION.json",dict(stage="START",source=pre["archive"],reference=pre["reference"],
                                           preflight=identity(out/"PREFLIGHT.json"),
                                           code={x.name:identity(x) for x in sources}))
            state(out,"STARTING_WSL")
            child=subprocess.Popen(command("run",out))
            wait_file(out/"calibration/CAPTURE.json",child,out)

        if not (out/"COLLECTION_DONE.json").is_file():
            state(out,"CALIBRATING")
            analysis("calibration",out,base)
            state(out,"READY_FOR_HOLDOUT",thresholds=identity(out/"THRESHOLDS.json"))
            await_completion(out,child)

        state(out,"SCORING_HOLDOUT")
        analysis("holdout",out,base)
        assert read(out/"ACCEPTANCE.json")["status"]=="PASS"
        state(out,"ACCEPTED",acceptance=identity(out/"ACCEPTANCE.json"),hash_manifest=identity(out/"SHA256SUMS"))
    finally:
        if power:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("out",type=Path)
    parser.add_argument("base",type=Path)
    parser.add_argument("--resume",action="store_true")
    args=parser.parse_args()
    out=args.out
    with (out/".controller.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            run(out,args.base,args.resume)
        except Exception as exc:
            save(out/"FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
            current=read(out/"RUN_STATUS.json")["stage"] if (out/"RUN_STATUS.json").exists() else ""
            if current=="CALIBRATING" and not (out/"holdout").exists() and service_alive(out):
                status="CALIBRATION_PAUSED"
            elif current=="SCORING_HOLDOUT" and (out/"COLLECTION_DONE.json").is_file():
                status="HOLDOUT_SCORING_PAUSED"
            else:
                status="STOP"
            state(out,status,error=str(exc) or repr(exc))
            raise


if __name__=="__main__":
    main()
