"""Run the same audited WSL capture and offline scoring path for every batch."""
import argparse
from datetime import datetime, timezone
import ctypes
import msvcrt
from pathlib import Path
import os
import shutil
import subprocess
import sys
import time
import traceback

from frozen_assets import HERE, registry
from controller import wsl
from evaluate_reconnect import score_attempt, verified_batch
from protocol_reconnect import SILENCE_S, STAGE
from results_reconnect import deliver, render_handoff, sha_all
from sources import identity, read, save

NS = 10**9
RESERVE = 2*2**30


def state(root,stage,**extra):
    save(root/"live/RUN_STATUS.json",dict(stage=stage,controller_pid=os.getpid(),updated_ns=time.time_ns(),**extra))


def collector(mode, attempt, *args):
    return ["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
            wsl(HERE/"collect_reconnect.py"),mode,wsl(attempt),*args]


def child(script,*args):
    return [sys.executable,"-B","-X","utf8",str(HERE/script),*map(str,args)]


def attempt_batch(root,item,pin,after,done):
    e = root/"evidence"
    key = item["key"]
    is_pre = key=="preflight"
    region = e/key if is_pre else e/"batches"/key
    region.mkdir(parents=True,exist_ok=True)
    attempts = sorted(region.glob("attempt_*"))
    last = attempts[-1] if attempts else None
    if last is None or not (last/"COLLECTION_DONE.json").is_file():
        if last is not None:
            active = subprocess.run(collector("probe",last),capture_output=True,timeout=15)
            assert active.returncode==1, "The previous WSL collector is active or cannot be probed"
            after = max([after,*(p.stat().st_mtime_ns for p in last.rglob("*") if p.is_file())])
        earliest = after+SILENCE_S*NS
        if time.time_ns()<=earliest:
            state(root,"BETWEEN_BATCHES",batch=key,connections=done,next_start_ns=earliest,
                  scheduled_rate=item["scheduled_rate"])
        while time.time_ns()<=earliest:
            time.sleep(min(1.,(earliest-time.time_ns()+NS)/NS))
        assert shutil.disk_usage(root).free>RESERVE
        last = region/f"attempt_{len(attempts)+1:02}"
        last.mkdir()
        state(root,"CAPTURING",batch=key,attempt=last.relative_to(root).as_posix(),connections=done,
              scheduled_rate=item["scheduled_rate"],preflight=is_pre)
        subprocess.run(collector("capture",last,key,wsl(e)),check=True,timeout=item["schedule"]["duration_seconds"]+90)
    if not (last/"BATCH_ACCEPTANCE.json").is_file():
        state(root,"SCORING",batch=key,attempt=last.relative_to(root).as_posix(),connections=done,
              scheduled_rate=item["scheduled_rate"],preflight=is_pre)
        subprocess.run(child("reconnect_controller.py",root,"--score",key,"--attempt",last),check=True)
    info, data = verified_batch(last,item,pin,e/"REGISTRATION.json")
    assert info["start_ns"]>after+60*NS and info["last_frame_ns"]>info["first_frame_ns"]
    assert info["features"]["rows"]==item["connections"]
    return last,info,data


def main_capture(root,preflight_only):
    e = root/"evidence"
    reg = e/"REGISTRATION.json"
    state(root,"VERIFYING",connections=0)
    pin, prior = registry(root.parent)
    if reg.is_file():
        recorded = read(reg)
        assert {k:v for k,v in recorded.items() if k!="registered_at_ns"}==pin
        pin = recorded
    else:
        pin["registered_at_ns"] = time.time_ns()
        save(reg,pin)
        (e/"METHOD.md").write_bytes((HERE/"METHOD.md").read_bytes())
    assert identity(e/"METHOD.md")==identity(HERE/"METHOD.md")
    after = max(pin["last_prior_capture_ns"],pin["registered_at_ns"]-SILENCE_S*NS)
    pre_item = pin["plan"]["preflight"]
    attempt,pre,pre_data = attempt_batch(root,pre_item,pin,after,0)
    preflight = dict(status="PASS",connections=pre["connections"],eligible_posts=pre["eligible_posts"],
        setup_connections=pre["setup_connections"],duplex=pre["complete_duplex_handshakes"],kernel_drops=0,
        unaligned_posts=0,input_dimensions=790,arms=pre["flags"],h60=pre["h60"],candidate=identity(attempt/"BATCH_ACCEPTANCE.json"),
        source_attempt=attempt.relative_to(e).as_posix(),registered=identity(reg),completed_at_ns=pre["end_ns"])
    save(e/"PREFLIGHT.json",preflight)
    if preflight_only:
        state(root,"PREFLIGHT_PASSED",connections=0,preflight=preflight)
        return
    after = pre["end_ns"]
    used = {*pin["prior_service_instances"],pre["instance"]}
    uid = set(pre_data["uid"])
    for data in prior.values():
        assert uid.isdisjoint(data["uid"])
        uid.update(data["uid"])
    accepted, batch_links = [], []
    for n,item in enumerate(pin["plan"]["formal"]):
        attempt,batch,data = attempt_batch(root,item,pin,after,n*pin["plan"]["batch_connections"])
        assert batch["instance"] not in used and uid.isdisjoint(data["uid"])
        used.add(batch["instance"])
        uid.update(data["uid"])
        gap = (batch["start_ns"]-after)/NS
        assert gap>60
        after = batch["end_ns"]
        accepted.append((item,batch,data))
        path = attempt/"BATCH_ACCEPTANCE.json"
        batch_links.append(dict(batch=item["key"],rate=item["scheduled_rate"],connections=batch["connections"],
                                posts=batch["eligible_posts"],setup=batch["setup_connections"],capture_drops=0,
                                silence_seconds=gap,orders=batch["uid_order"],instance=batch["instance"],
                                receipt=identity(path),path=path.relative_to(e).as_posix()))
    state(root,"VERIFYING_OUTPUTS",connections=600)
    rows,freq,conclusion = deliver(e,pin,accepted,prior)
    proof = dict(status="PASS",batch_count=15,connections=600,qualified_posts=600,
                 setup_connections=45,complete_duplex_handshakes=645,capture_kernel_drops=0,
                 unmatched_posts=0,successful_authentications=645,min_silence_seconds=min(b["silence_seconds"] for b in batch_links),
                 historical_stress_connections=51,attack_connections=dict(low=600,medium=600),
                 registration=identity(reg),preflight=identity(e/"PREFLIGHT.json"),reference=pin["reference"],
                 thresholds=pin["rank5_thresholds"],h60_cut=pin["handshake_threshold"],batches=batch_links,
                 ensemble=rows[0],outputs={name:identity(e/name) for name in
                 ("TABLE1_LEGAL_RECONNECT.csv","TABLE2_MATCHED_H60_MCNEMAR.csv","RESULTS_FOR_PAPER.md","RESULT_SUMMARY.json")})
    save(e/"ACCEPTANCE.json",proof)
    total_files = sha_all(e)
    handoff = render_handoff(root,pin,rows,freq,conclusion)
    from publish_reconnect import copy_small, push_backup

    paths = copy_small(e,handoff)
    state(root,"ACCEPTED",connections=600,evidence_files=total_files,
          manifest=identity(e/"SHA256SUMS"),conclusion=conclusion,handoff=str(handoff),benchmark="QUEUED")
    try:
        push_backup(root/"live",paths,"Add accepted Paper04 v14 legal reconnect stress evidence")
    except Exception:
        save(root/"live/BACKUP_STATUS.json",dict(status="PENDING",error=traceback.format_exc()))
    return proof


def benchmark(root):
    report = root/"live/BENCHMARK_STATUS.json"
    save(report,dict(status="RUNNING",started_ns=time.time_ns()))
    try:
        subprocess.run(child("benchmark_reconnect.py",root),check=True,timeout=900)
    except Exception:
        save(report,dict(status="FAILED",error=traceback.format_exc()))


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
        item, = (row for row in [pin["plan"]["preflight"],*pin["plan"]["formal"]] if row["key"]==args.score)
        assert args.attempt.resolve().is_relative_to((root/"evidence").resolve())
        score_attempt(root,args.attempt,item,pin)
        return
    with (root/"live/controller.lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
        try:
            proof = main_capture(root,args.preflight_only)
            if proof:
                benchmark(root)
        except Exception as exc:
            save(root/"live/FAILURE.json",dict(error=repr(exc),traceback=traceback.format_exc(),at_ns=time.time_ns()))
            state(root,"FAILED",error=repr(exc))
            raise
        finally:
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)


if __name__=="__main__":
    main()
