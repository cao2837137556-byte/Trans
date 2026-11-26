"""Drive capture, raw-window checks and frozen scoring from the locked single-client plan."""
import argparse
import ctypes
import msvcrt
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from single_inputs import HERE, build_inputs
from evaluate_single import score, verified
from reconnect_controller import RESERVE, state, wsl
from single_protocol import QUIET_SECONDS
from single_results import NAMES, deliver, handoff, sha_all
from sources import identity, read, save

NS = 10**9


def linux(mode,attempt,*args):
    return ["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
            wsl(HERE/"collect_single.py"),mode,wsl(attempt),*args]


def batch(root,item,pin,after,done):
    evidence = root/"evidence"
    key = item["key"]
    region = evidence/key if key=="preflight" else evidence/"batches"/key
    region.mkdir(parents=True,exist_ok=True)
    attempts = sorted(region.glob("attempt_*"))
    last = attempts[-1] if attempts else None
    display = dict(batch=key,connections=done,client=item["client"],scheduled_rate=item["scheduled_rate"])
    if last is None or not (last/"COLLECTION_DONE.json").is_file():
        if last is not None:
            check = subprocess.run(linux("probe",last),capture_output=True,timeout=15)
            assert check.returncode==1, "Previous collector is active or its identity could not be checked"
            after = max([after,*(p.stat().st_mtime_ns for p in last.rglob("*") if p.is_file())])
        earliest = after+QUIET_SECONDS*NS
        if time.time_ns()<=earliest:
            state(root,"BETWEEN_BATCHES",next_start_ns=earliest,**display)
        while time.time_ns()<=earliest:
            time.sleep(1)
        assert shutil.disk_usage(root).free>RESERVE
        last = region/f"attempt_{len(attempts)+1:02}"
        last.mkdir()
        state(root,"CAPTURING",attempt=last.relative_to(root).as_posix(),**display)
        subprocess.run(linux("capture",last,key,wsl(evidence)),check=True,
                       timeout=item["schedule"]["duration_seconds"]+120)
    if not (last/"BATCH_ACCEPTANCE.json").is_file():
        state(root,"SCORING",attempt=last.relative_to(root).as_posix(),**display)
        cmd = [sys.executable,"-B","-X","utf8",str(HERE/"run_single.py"),str(root),"--score",key,"--attempt",str(last)]
        subprocess.run(cmd,check=True,timeout=360)
    result,data = verified(last,item,pin,evidence/"REGISTRATION.json")
    assert result["start_ns"]>after+60*NS and result["end_ns"]>=result["last_frame_ns"]>result["start_ns"]
    return last,result,data


def run(root,preflight_only):
    evidence = root/"evidence"
    register = evidence/"REGISTRATION.json"
    state(root,"VERIFYING",connections=0)
    pin,prior,sync = build_inputs(root.parent)
    if register.is_file():
        existing = read(register)
        assert {k:v for k,v in existing.items() if k!="registered_at_ns"}==pin
        pin = existing
    else:
        pin["registered_at_ns"] = time.time_ns()
        save(register,pin)
        (evidence/"METHOD.md").write_bytes((HERE/"METHOD.md").read_bytes())
    assert identity(evidence/"METHOD.md")==identity(HERE/"METHOD.md")
    plan = pin["single_plan"]
    after = max(pin["last_prior_capture_ns"],pin["registered_at_ns"]-QUIET_SECONDS*NS)
    path,pre,data = batch(root,plan["preflight"],pin,after,0)
    proof = dict(status="PASS",client=pre["client"],reconnects=pre["connections"],setup=1,duplex=pre["duplex"],
                 capture_drops=0,unaligned_posts=0,authenticated=pre["authenticated"],feature_dims=790,
                 one_source_1s=pre["one_source_1s"],one_source_10s=pre["one_source_10s"],device_8d_parity=pre["device_8d_parity"],
                 flags=pre["flags"],candidate=identity(path/"BATCH_ACCEPTANCE.json"),
                 source_windows=pre["source_windows"],registration=identity(register),path=path.relative_to(evidence).as_posix())
    pre_file = evidence/"PREFLIGHT.json"
    if pre_file.is_file():
        assert read(pre_file)==proof
    else:
        save(pre_file,proof)
    if preflight_only:
        state(root,"PREFLIGHT_PASSED",connections=0,preflight=proof)
        return
    after = pre["end_ns"]
    used = {*pin["prior_service_instances"],pre["instance"]}
    uids = set(data["uid"])
    for old in [*prior.values(),*(x[2] for x in sync)]:
        assert uids.isdisjoint(old["uid"])
        uids.update(old["uid"])
    results,records = [],[]
    for index,item in enumerate(plan["formal"]):
        path,receipt,data = batch(root,item,pin,after,40*index)
        assert receipt["instance"] not in used and uids.isdisjoint(data["uid"])
        used.add(receipt["instance"])
        uids.update(data["uid"])
        gap = (receipt["start_ns"]-after)/NS
        assert gap>60
        after = receipt["end_ns"]
        results.append((item,receipt,data))
        file = path/"BATCH_ACCEPTANCE.json"
        records.append(dict(batch=item["key"],client=item["client"],rate=item["scheduled_rate"],connections=40,
                            one_source_1s=receipt["one_source_1s"],one_source_10s=receipt["one_source_10s"],
                            device_8d_parity=receipt["device_8d_parity"],start_ns=receipt["start_ns"],
                            end_ns=after,silence_seconds=gap,receipt=identity(file),path=file.relative_to(evidence).as_posix()))
    state(root,"VERIFYING_OUTPUTS",connections=600)
    totals,frequency,text = deliver(root,pin,results,sync,prior)
    final = dict(status="PASS",connections=600,batches=records,preflight=identity(pre_file),
                 registration=identity(register),reference=pin["reference"],thresholds=pin["rank5_thresholds"],
                 control_sources=dict(synchronized=pin["synchronized"],benchmark=pin["benchmark"]),
                 setup=15,duplex=615,authenticated=615,capture_drops=0,unaligned_posts=0,
                 one_source_1s=sum(b["one_source_1s"] for b in records),one_source_10s=sum(b["one_source_10s"] for b in records),
                 device_8d_parity=sum(b["device_8d_parity"] for b in records),min_silence_seconds=min(b["silence_seconds"] for b in records),
                 output={n:identity(evidence/n) for n in NAMES})
    assert final["one_source_1s"]==final["one_source_10s"]==final["device_8d_parity"]==600
    save(evidence/"ACCEPTANCE.json",final)
    count = sha_all(evidence)
    from publish_single import copy_receipts, push

    copy_receipts(evidence,final=True)
    doc = handoff(root,pin,totals,frequency,text)
    state(root,"ACCEPTED",connections=600,conclusion=text,evidence_files=count,manifest=identity(evidence/"SHA256SUMS"),
          handoff=str(doc))
    try:
        push(root/"live",doc)
    except Exception:
        save(root/"live/BACKUP_STATUS.json",dict(status="PENDING",error=traceback.format_exc()))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root",type=Path)
    parser.add_argument("--preflight-only",action="store_true")
    parser.add_argument("--score")
    parser.add_argument("--attempt",type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    if args.score:
        pin = read(root/"evidence/REGISTRATION.json")
        plan = pin["single_plan"]
        item, = (x for x in [plan["preflight"],*plan["formal"]] if x["key"]==args.score)
        assert args.attempt.resolve().is_relative_to((root/"evidence").resolve())
        score(root,args.attempt,item,pin)
        return
    with (root/"live/controller.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            run(root,args.preflight_only)
        except Exception as exc:
            save(root/"live/FAILURE.json",dict(error=repr(exc),traceback=traceback.format_exc(),at_ns=time.time_ns()))
            state(root,"FAILED",error=repr(exc))
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=="__main__":
    main()
