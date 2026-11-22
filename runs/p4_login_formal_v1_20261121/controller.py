"""Run the formal WSL data chain and score the frozen evaluation automatically."""
import ctypes
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


def wait_file(found,p,out):
    while not found.is_file():
        aborted=out/"COLLECTION_FAILURE.json"
        if aborted.is_file():
            raise RuntimeError(read(aborted)["error"])
        if p.poll() is not None:
            raise RuntimeError(f"WSL ended before {found.name}, exit {p.returncode}")
        time.sleep(2)


def run(out,pilot):
    assert read(out/"QUICK_CHECK.json")["status"]==read(out/"ENGINEERING_SLICE.json")["status"]=="PASS"
    assert shutil.disk_usage(out).free>2*2**30
    source=out/"frozen_quick_check_assets"
    assert read(source/"LOCAL_RECEIPT.json")["manifest_sha256"]
    (out/"METHOD.md").write_bytes((HERE/"METHOD.md").read_bytes())
    version={n:identity(HERE/n) for n in ("controller.py","collect_formal.py","schedule.py","audit_formal.py",
                                          "bank.py","science.py","frozen_score.py","METHOD.md")}
    with (out/"EXECUTION.json").open("x",encoding="utf8") as f:
        import json
        json.dump(dict(stage="START",method_files=version),f,indent=2)
    state(out,"STARTING_WSL")
    mode=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        p=subprocess.Popen(["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
                            wsl(HERE/"collect_formal.py"),"run",wsl(out)])
        wait_file(out/"enrollment/CAPTURE.json",p,out)
        if (out/"COLLECTION_FAILURE.json").is_file():
            raise RuntimeError(read(out/"COLLECTION_FAILURE.json")["error"])
        state(out,"SEALING_REFERENCE",enrollment=identity(out/"enrollment/CAPTURE.json"))
        subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"science.py"),"enrollment",str(out),str(source)],check=True)
        assert read(out/"BANK_READY.json")["status"]=="PASS"
        state(out,"READY_FOR_EVALUATION",reference=identity(out/"BANK_READY.json"))
        wait_file(out/"COLLECTION_DONE.json",p,out)
        assert p.wait(timeout=15)==0
        state(out,"SCORING_EVALUATION")
        subprocess.run([sys.executable,"-X","utf8","-B",str(HERE/"science.py"),"evaluation",str(out),str(source)],check=True)
        assert read(out/"ACCEPTANCE.json")["status"]=="PASS"
        state(out,"ACCEPTED",acceptance=identity(out/"ACCEPTANCE.json"),hash_manifest=identity(out/"SHA256SUMS"))
    finally:
        if mode:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=="__main__":
    out,pilot=map(Path,sys.argv[1:])
    try:
        run(out,pilot)
    except Exception as exc:
        save(out/"FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
        state(out,"STOP",error=str(exc) or repr(exc))
        raise
