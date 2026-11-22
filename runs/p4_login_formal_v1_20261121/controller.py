"""Run the formal WSL data chain and score the frozen evaluation automatically."""
import argparse
import ctypes
import json
import msvcrt
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_login_pilot_v1_20261121"))
from audit import identity, read, save


def wsl(path):
    absolute=path.resolve().as_posix()
    assert absolute[1:3]==":/"
    return "/mnt/"+absolute[0].lower()+absolute[2:]


def state(out,phase,**extra):
    save(out/"RUN_STATUS.json",dict(stage=phase,updated_unix=time.time(),**extra))


def collector_command(mode,out):
    return ["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
            wsl(HERE/"collect_formal.py"),mode,wsl(out)]


def collector_is_live(out):
    if not (out/"COLLECTOR_IDENTITY.json").is_file() or (out/"COLLECTION_FAILURE.json").is_file():
        return False
    try:
        return subprocess.run(collector_command("probe",out),capture_output=True,timeout=8).returncode==0
    except (OSError,subprocess.TimeoutExpired):
        return False


def wait_file(found,p,out):
    while not found.is_file():
        aborted=out/"COLLECTION_FAILURE.json"
        if aborted.is_file():
            raise RuntimeError(read(aborted)["error"])
        if p is not None and p.poll() is not None:
            raise RuntimeError(f"WSL ended before {found.name}, exit {p.returncode}")
        if p is None:
            observed=read(out/"COLLECTION_PROGRESS.json")
            if time.time_ns()-observed.get("keeper_heartbeat_ns",0)>30*10**9 and not collector_is_live(out):
                raise RuntimeError("The original WSL collector is unavailable.")
        time.sleep(2)


def live_reference_keeper(out):
    return not (out/"evaluation").exists() and collector_is_live(out)


def run(out,resume,preflight_source,pilot):
    assert read(out/"QUICK_CHECK.json")["status"]==read(out/"ENGINEERING_SLICE.json")["status"]=="PASS"
    repaired=read(out/"WINDOWS_REPAIR.json")
    feature=identity(HERE.parent/"p4_login_pilot_v1_20261121/feature_witness.py")
    assert repaired["status"]=="PASS" and repaired["implementation"]==feature
    contention=read(out/"PROGRESS_CONTENTION_CHECK.json")
    assert contention["status"]=="PASS" and contention["implementation"]==identity(HERE/"collect_formal.py")
    assert shutil.disk_usage(out).free>2*2**30
    source=out/"frozen_quick_check_assets"
    assert read(source/"LOCAL_RECEIPT.json")["manifest_sha256"]
    if resume:
        assert read(out/"RUN_STATUS.json")["stage"]=="REFERENCE_SEAL_PAUSED"
        assert live_reference_keeper(out),"The service instance that recorded enrollment is unavailable."
        previous=out/"FAILURE.json"
        with (out/f"reference_failure_{time.time_ns()}.json").open("xb") as f:
            f.write(previous.read_bytes())
    else:
        if preflight_source is not None:
            assert pilot is not None
            state(out,"VERIFYING_ARCHIVED_BANK",source=preflight_source.name)
            subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"windows_regression.py"),
                            str(preflight_source),str(out),"--full",str(pilot)],check=True)
        archive_check=read(out/"SEALED_REFERENCE_CHECK.json")
        assert archive_check["status"]=="PASS" and archive_check["implementation"]==feature
        (out/"METHOD.md").write_bytes((HERE/"METHOD.md").read_bytes())
        version={n:identity(HERE/n) for n in ("controller.py","collect_formal.py","schedule.py","audit_formal.py",
                                              "bank.py","science.py","frozen_score.py","windows_regression.py","METHOD.md")}
        with (out/"EXECUTION.json").open("x",encoding="utf8") as f:
            json.dump(dict(stage="START",method_files=version,numeric_repair=identity(out/"WINDOWS_REPAIR.json"),
                           archive_replay=identity(out/"SEALED_REFERENCE_CHECK.json"),
                           contention=identity(out/"PROGRESS_CONTENTION_CHECK.json")),f,indent=2)
        state(out,"STARTING_WSL")
    mode=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        p=None
        if not resume:
            p=subprocess.Popen(collector_command("run",out))
            wait_file(out/"enrollment/CAPTURE.json",p,out)
        if (out/"COLLECTION_FAILURE.json").is_file():
            raise RuntimeError(read(out/"COLLECTION_FAILURE.json")["error"])
        state(out,"SEALING_REFERENCE",enrollment=identity(out/"enrollment/CAPTURE.json"))
        subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"science.py"),"enrollment",str(out),str(source)],check=True)
        assert read(out/"BANK_READY.json")["status"]=="PASS"
        state(out,"READY_FOR_EVALUATION",reference=identity(out/"BANK_READY.json"))
        wait_file(out/"COLLECTION_DONE.json",p,out)
        if p is not None:
            assert p.wait(timeout=15)==0
        state(out,"SCORING_EVALUATION")
        subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"science.py"),"evaluation",str(out),str(source)],check=True)
        assert read(out/"ACCEPTANCE.json")["status"]=="PASS"
        state(out,"ACCEPTED",acceptance=identity(out/"ACCEPTANCE.json"),hash_manifest=identity(out/"SHA256SUMS"))
    finally:
        if mode:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("out",type=Path)
    parser.add_argument("--resume",action="store_true")
    parser.add_argument("--preflight-source",type=Path)
    parser.add_argument("--pilot",type=Path)
    args=parser.parse_args()
    out=args.out
    with (out/".controller.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            run(out,args.resume,args.preflight_source,args.pilot)
        except Exception as exc:
            save(out/"FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
            paused=(out/"RUN_STATUS.json").is_file() and read(out/"RUN_STATUS.json")["stage"]=="SEALING_REFERENCE"
            state(out,"REFERENCE_SEAL_PAUSED" if paused and live_reference_keeper(out) else "STOP",
                  error=str(exc) or repr(exc))
            raise


if __name__=="__main__":
    main()
