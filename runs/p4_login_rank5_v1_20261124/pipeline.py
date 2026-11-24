"""Run WSL calibration, seal rank five, then run the untouched daily holdout."""
import argparse
import ctypes
import msvcrt
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

import numpy as np

from protocol import OLD_CONNECTIONS, ROOT
from assessment import arrays, collect_aligned, connection_scores, roster, scores_for
from audit import NS
from controller import wsl
from evidence import attack_inventory, combine, freeze, old_data, scored
from frozen_score import digest_order, sealed_runtime
from rank_stats import check_rank5, compare, rank5, seal, tables
from sources import ARMS, identity, read, save, table


def state(out,stage,**extra):
    save(out/"RUN_STATUS.json",dict(stage=stage,updated_unix=time.time(),**extra))


def scope_root(attempt,plan):
    return attempt/("holdout" if plan["stage"]=="preflight" else plan["stage"])


def score_worker(out,attempt,key):
    pin=read(out/"INPUTS.json")
    stage=pin["batches"][key]
    folder=scope_root(attempt,stage)
    cap,report,joined,fields=collect_aligned(folder)
    assert read(folder/"SCHEDULE.json")==stage["schedule"]
    assert cap["registered_batch"]==key and cap["capture"]["capture_kernel_drops"]==0
    assert cap["scope"]==folder.name and cap["server_port"]==pin["server_port"] and cap["kernel"]==pin["kernel"]
    assert [[x["ip"],x["mac"]] for x in cap["endpoints"]]==pin["endpoints"]
    assert read(attempt/"COLLECTION_DONE.json")==dict(status="PASS",service_instance=cap["service_instance"],namespaces_released=True)
    aligned=roster(joined)
    ids,streams=arrays(aligned)
    assert len(ids)==len(joined)==report["checks"]["aligned_requests"] and all(r["normal"] for r in aligned)
    assert len(set(streams))==report["checks"]["tcp_connections"]==stage["connections"]
    groups={}
    for row in aligned:
        groups.setdefault(str(row["tcp_stream"]),[]).append(row["capture_uid"])
    record=dict(status="PASS",selection="qualification and chronological POST order before scoring",
                batch=key,capture=identity(folder/"login.pcap"),uid_order=digest_order(ids),connections=groups)
    listing=attempt/"QUALIFIED_ROSTER.json"
    if listing.is_file():
        assert read(listing)==record
    else:
        save(listing,record)
    ref=out.parent/pin["reference_archive"]
    assert identity(ref/"enrollment/REFERENCE.npz")==pin["reference"]
    with sealed_runtime() as (cfg,pins):
        assert cfg["method"]["cuts"]==pin["old_cic_cuts"]
        q,proof=scores_for(ref,folder,cap,fields,aligned,cfg,pins)
    np.savez_compressed(attempt/"SCORES.npz",**q,arms=np.array(ARMS))
    files=[*(p for p in folder.iterdir() if p.is_file()),listing,attempt/"SCORES.npz",
           attempt/"COLLECTOR_IDENTITY.json",attempt/"COLLECTION_DONE.json"]
    save(attempt/"BATCH_ACCEPTANCE.json",dict(status="PASS",batch=key,connections=stage["connections"],
         requests=len(aligned),ordered_uid_sha256=record["uid_order"],instance=cap["service_instance"],
         start_ns=cap["capture"]["first_qualifying_ns"],end_ns=cap["capture"]["end_ns"],features=proof,
         files={p.relative_to(attempt).as_posix():identity(p) for p in sorted(files)}))


def collector(mode,at,*args):
    return ["wsl.exe","-d","Ubuntu-24.04","-u","root","--cd","/","--exec","python3","-B",
            wsl(ROOT/"collect_rank5.py"),mode,wsl(at),*args]


def active(attempt):
    if (attempt/"COLLECTOR_IDENTITY.json").is_file():
        return subprocess.run(collector("probe",attempt),capture_output=True,timeout=12).returncode==0
    progress=attempt/"COLLECTION_PROGRESS.json"
    return progress.is_file() and abs(time.time_ns()-read(progress)["keeper_heartbeat_ns"])<30*NS


def run_batch(out,key,plan,after,tallies):
    root=out/key
    root.mkdir(exist_ok=True)
    tries=sorted(root.glob("attempt_*"))
    attempt=tries[-1] if tries else None
    if attempt is None or not (attempt/"COLLECTION_DONE.json").is_file():
        if attempt is not None:
            assert not active(attempt),"Previous collector still owns this batch"
        if time.time_ns()<=after+60*NS:
            state(out,"BETWEEN_BATCHES",batch=key,**tallies)
            while time.time_ns()<=after+60*NS:
                time.sleep(1.)
        assert shutil.disk_usage(out).free>2*2**30
        attempt=root/f"attempt_{len(tries)+1:02}"
        attempt.mkdir()
        state(out,"CAPTURING",batch=key,attempt=attempt.relative_to(out).as_posix(),**tallies)
        subprocess.run(collector("capture",attempt,key,wsl(out)),check=True,timeout=plan["schedule"]["duration_seconds"]+120)
    proof=attempt/"BATCH_ACCEPTANCE.json"
    if not proof.is_file():
        state(out,"SCORING",batch=key,attempt=attempt.relative_to(out).as_posix(),**tallies)
        subprocess.run([sys.executable,"-X","utf8","-B",str(ROOT/"pipeline.py"),str(out),"--score",key,
                        "--attempt",str(attempt)],check=True)
    record=read(proof)
    assert record["status"]=="PASS" and record["batch"]==key and record["connections"]==plan["connections"]
    assert record["start_ns"]>after+60*NS
    if plan["stage"]=="holdout":
        release=read(out/"THRESHOLD_SEAL.json")
        assert record["start_ns"]>release["sealed_at_ns"]
    for n,p in record["files"].items():
        file=attempt/n
        assert file.resolve().is_relative_to(attempt.resolve()) and identity(file)==p
    data=scored(attempt/"SCORES.npz",scope_root(attempt,plan)/"ALIGNMENT.jsonl",key,plan["connections"])
    assert digest_order(data["uid"])==record["ordered_uid_sha256"]
    data["score_sha"]=record["files"]["SCORES.npz"]
    return attempt,record,data


def thresholds(out,prior,added,old,pin):
    ready=out/"THRESHOLD_SEAL.json"
    if not ready.is_file():
        return seal(out,prior,added,old,pin)
    status=read(ready)
    assert status["status"]=="PASS" and status["input_manifest"]==identity(out/"INPUTS.json")
    assert status["thresholds"]==identity(out/"THRESHOLDS.json")
    policy=read(out/"THRESHOLDS.json")
    assert policy["added_scores"]==[x["score_sha"] for x in added]
    a=combine([prior,*added],"calibration")
    refit,_,_=rank5(connection_scores(a["scores"],a["stream"]))
    assert np.array_equal(refit,np.asarray(policy["thresholds"]))
    return np.asarray(policy["thresholds"])


def finish(out,completed,pin,holdout):
    save(out/"ACCEPTANCE.json",dict(status="PASS",old_calibration=OLD_CONNECTIONS,added_calibration=794,
          total_calibration=1000,descending_rank=5,holdout_connections=sum(d["connections"] for d in holdout),
          archived_holdout=1107,stress_connections=51,attack_status="PENDING_ATTACK_EVALUATION",
          input_manifest=identity(out/"INPUTS.json"),thresholds=identity(out/"THRESHOLDS.json"),
          reference=pin["reference"],summary=identity(out/"DAILY_AND_ATTACK.csv"),
          batches=[dict(path=(a/"BATCH_ACCEPTANCE.json").relative_to(out).as_posix(),
                        receipt=identity(a/"BATCH_ACCEPTANCE.json")) for a,_ in completed]))
    top=("INPUTS.json","METHOD.md","PREFLIGHT.json","ATTACK_QUALIFICATION.json","ATTACK_QUALIFICATION.csv",
         "THRESHOLDS_206.json","THRESHOLDS.json","THRESHOLD_COMPARISON.csv","THRESHOLD_SEAL.json",
         "PREFLIGHT_PAIRED.csv","PAIRED.csv","STRESS_PAIRED.csv","DAILY_AND_ATTACK.csv","RESULTS_FOR_PAPER.md","ACCEPTANCE.json")
    files=[out/n for n in top]
    for a,proof in completed:
        files.extend([a/"BATCH_ACCEPTANCE.json",*(a/n for n in proof["files"])])
    manifest={p.relative_to(out).as_posix():identity(p)["sha256"] for p in sorted(files)}
    (out/"SHA256SUMS").write_bytes("".join(f"{h}  {n}\n" for n,h in manifest.items()).encode("ascii"))
    assert all(identity(out/n)["sha256"]==h for n,h in manifest.items())
    state(out,"ACCEPTED",calibration_connections=1000,holdout_connections=1000,
          acceptance=identity(out/"ACCEPTANCE.json"),hash_manifest=identity(out/"SHA256SUMS"))


def run(out):
    state(out,"VERIFYING",calibration_connections=OLD_CONNECTIONS,holdout_connections=0)
    assert shutil.disk_usage(out).free>2*2**30
    pin,prior,fixed,old_daily,stress,old=old_data(out)
    contract=freeze(out,pin)
    attack_inventory(out,pin)
    check_rank5()
    start=pin["first_after_ns"]
    instances=set(pin["used_instances"])
    used=set(prior["uid"])|set(old_daily["uid"])|set(stress["uid"])
    completed=[]
    new_cal=[]
    holdout=[]
    tau=None
    for key,plan in contract["batches"].items():
        if plan["stage"]=="holdout" and tau is None:
            state(out,"SEALING_THRESHOLD",calibration_connections=1000,holdout_connections=0)
            tau=thresholds(out,prior,new_cal,old,pin)
        tally=dict(calibration_connections=OLD_CONNECTIONS+sum(d["connections"] for d in new_cal),
                   holdout_connections=sum(d["connections"] for d in holdout))
        attempt,record,data=run_batch(out,key,plan,start,tally)
        start=record["end_ns"]
        assert record["instance"] not in instances and not used.intersection(data["uid"])
        used.update(data["uid"])
        instances.add(record["instance"])
        completed.append((attempt,record))
        if plan["stage"]=="preflight":
            table(out/"PREFLIGHT_PAIRED.csv",compare(data,old,old))
            save(out/"PREFLIGHT.json",dict(status="PASS",normal_connections=data["connections"],
                 requests=record["requests"],reference=pin["reference"],old_calibration=pin["previous_calibration"],
                 old_thresholds=pin["previous_thresholds"],old_daily=1107,stress=51,
                 row_proof=identity(attempt/"BATCH_ACCEPTANCE.json"),
                 paired=identity(out/"PREFLIGHT_PAIRED.csv"),rank_check="fifth largest including tied values"))
        elif plan["stage"]=="calibration":
            new_cal.append(data)
        else:
            holdout.append(data)
    assert sum(d["connections"] for d in new_cal)==794 and sum(d["connections"] for d in holdout)==1000
    state(out,"VERIFYING_OUTPUTS",calibration_connections=1000,holdout_connections=1000)
    attack_inventory(out,pin)
    tables(out,holdout,fixed,old_daily,stress,old,tau)
    finish(out,completed,pin,holdout)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("out",type=Path)
    parser.add_argument("--score")
    parser.add_argument("--attempt",type=Path)
    args=parser.parse_args()
    if args.score:
        score_worker(args.out,args.attempt,args.score)
    else:
        with (args.out/".controller.lock").open("a+b") as lock:
            lock.seek(0)
            msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
            power=ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            try:
                run(args.out)
            except Exception as exc:
                save(args.out/"FAILURE.json",dict(error=str(exc) or repr(exc),trace=traceback.format_exc()))
                state(args.out,"STOP",error=str(exc) or repr(exc))
                raise
            finally:
                if power:
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
