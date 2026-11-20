"""Run the full scientific phase only after a completed real-node pilot."""
import fcntl
import getpass
import json
from pathlib import Path
import sys
import time
import traceback

from common_round1 import artifact, dump, load, sha, verify_artifact
from slurm_base import command, wait_job, live
from metrics import SMALL, validate_files
from seal import check as require, COUNTS, GROUPS

HERE=Path(__file__).resolve().parent
RUN="p4_elegant_frozen_v12_20261119"

def submit(project, out, phase, wall):
    name = "p04-eleg19-" + phase
    user = getpass.getuser()
    snapshots = [
        command(["squeue", "-h", "-u", user, "-o", "%i|%j"]),
        command(["sacct", "-X", "-n", "-P", "-S", "2026-11-19", "-u", user, "-o", "JobIDRaw,JobName%80"]),
    ]
    require(all(v["returncode"] == 0 for v in snapshots), "SLURM_LOOKUP")
    matches = {
        r[0]
        for s in snapshots
        for line in s["stdout"].splitlines()
        for r in [line.split("|")]
        if len(r) >= 2 and r[1] == name and r[0].isdigit()
    }
    jobfile = out / f"JOB_{phase}.json"
    intent = out / f"SUBMIT_INTENT_{phase}.json"
    if jobfile.is_file():
        job = load(jobfile)["job_id"]
        require(intent.exists() and matches <= {job}, "AMBIGUOUS_JOB")
        return job
    if intent.exists():
        require(len(matches) == 1, "SUBMISSION_INTENT_WITHOUT_UNIQUE_JOB")
        job = matches.pop()
    else:
        require(not matches, "ALREADY_REGISTERED_JOB")
        hh, rem = divmod(wall, 3600)
        mm, ss = divmod(rem, 60)
        args = [
            "sbatch",
            "--partition=amd",
            "--no-requeue",
            "--nodes=1",
            "--ntasks=1",
            "--cpus-per-task=4",
            "--mem=16384M",
            f"--time={hh:02d}:{mm:02d}:{ss:02d}",
            "--job-name=" + name,
            "--chdir=" + str(HERE),
            "--output=" + str(out / (phase + "-%j.out")),
            "--error=" + str(out / (phase + "-%j.err")),
            str(HERE / "run.slurm"),
            phase,
            str(project),
            str(out),
        ]
        check = command(["sbatch", "--test-only", *args[1:]])
        dump(out / f"TEST_ONLY_{phase}.json", check)
        require(check["returncode"] == 0, "SBATCH_TEST_ONLY:" + check["stderr"])
        dump(intent, dict(timestamp=time.time(), argv=args))
        call = command(["sbatch", "--parsable", *args[1:]])
        dump(out / f"SBATCH_{phase}.json", call)
        job = call["stdout"].strip().split(";")[0]
        require(call["returncode"] == 0 and job.isdigit(), "SBATCH:" + call["stderr"])
    dump(jobfile, dict(job_id=job, phase=phase, job_name=name, requested_wall_seconds=wall))
    return job


def controller(project,out):
    require(out==project/"runs"/RUN and HERE==out/"package","RUN_DIRECTORY")
    with (out/".controller.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        if (out/"ACCEPTANCE.json").exists():return
        try:
            pkg=sha(HERE/"PACKAGE_MANIFEST.json")
            for n,h in load(HERE/"PACKAGE_MANIFEST.json")["files"].items():require(sha(HERE/n)==h,"INSTALL_SHA:"+n)
            truth=load(HERE/"INPUT_SEAL.json")
            jobs={};receipts={};schedulers={};wall=7200
            for phase in ("preflight","formal"):
                live(out,"VALIDATE_SUBMISSION",phase=phase)
                jobs[phase]=submit(project,out,phase,wall)
                wait_job(out,phase,jobs[phase])
                sched=load(out/f"SCHEDULER_{phase}.json")
                require(sched["state"]=="COMPLETED" and any(l.split("|")[:3]==[jobs[phase],"COMPLETED","0:0"]
                        for l in sched["account"]["stdout"].splitlines()),"SLURM_FINAL_EXIT")
                schedulers[phase]={"job_id":jobs[phase],"state":sched["state"],"exit":"0:0"}
                proof=load(out/("PREFLIGHT.json" if phase=="preflight" else "FORMAL.json"))
                require(proof["status"]=="PASS" and proof["job"]==jobs[phase] and proof["package_sha256"]==pkg
                        and proof["source_seal_sha256"]==sha(HERE/"INPUT_SEAL.json") and proof["components"]==1
                        and proof["CIC"]["head_decision_differences"]==[0]*4 and proof["max_distance_error"]<=2e-10,
                        "NODE_AND_FROZEN_CHECK")
                verify_artifact(out/phase,proof["input_seal"])
                receipts[phase]={k:proof[k] for k in ("job","node","queries","references","components","selected_uid_order") if k in proof}
                receipts[phase].update(input_seal=proof["input_seal"],tshark=proof["tshark"],
                    cic_witness=proof["CIC"],reference_order=proof["bank_order"],query_order=proof["query_order"],
                    resources=load(out/f"RESOURCES_{phase}.json"),receipt=artifact(out/("PREFLIGHT.json" if phase=="preflight" else "FORMAL.json")))
                if phase=="preflight":
                    require(proof["queries"]+proof["references"]==load(HERE/"LOCAL_REPLAY.json")["pilot_positions"]
                            and all(v["nonzero_support"]==v["max_abs_score_delta"]==v["decision_flips"]==0 for v in proof["uid_zero_checks"]),
                            "REAL_ZERO_SUPPORT_PILOT")
                    receipts[phase]["witnesses"]=proof["pilot_witnesses"];wall=proof["formal_wall_seconds"]
            require(proof["queries"]==15016 and proof["references"]==4096 and proof["group_orders"]==truth["query_orders"]
                    and proof["query_order"]==truth["all_query_order"] and proof["bank_order"]==truth["reference_order"],"FORMAL_UIDS")
            for s in proof["outputs"].values():verify_artifact(out,s)
            checks=validate_files(out);require(checks==proof["checks"],"LOCAL_TABLE_RECOUNT")
            dump(out/"ACCEPTANCE.json",dict(status="PASS",run=RUN,jobs=jobs,scheduler=schedulers,
                 package_sha256=pkg,input_sha256=sha(HERE/"INPUT_SEAL.json"),outputs=proof["outputs"],
                 physical_query_orders=truth["query_orders"],phases=receipts,checks=checks,
                 model_updates=0,threshold_updates=0,decision_cache=proof["decisions"],hpc_dir=str(out),
                 conclusion="单组件条件下按冻结规则回退"))
            dump(out/"RETURN.json",dict(files={n:artifact(out/n) for n in sorted(SMALL)}))
            live(out,"COMPLETE",jobs=jobs,job_id=jobs["formal"])
        except Exception as exc:
            error=str(exc)
            for phase in ("formal","preflight"):
                fp=out/f"FAILURE_{phase}.json"
                if fp.exists():
                    error+=" · "+str(load(fp).get("error",""));break
            dump(out/"CONTROLLER_FAILURE.json",dict(error=error,traceback=traceback.format_exc()))
            dump(out/"ACCEPTANCE.json",dict(status="FAIL",run=RUN,error=error,hpc_dir=str(out)))
            dump(out/"RETURN.json",dict(files={"ACCEPTANCE.json":artifact(out/"ACCEPTANCE.json")}))
            live(out,"STOP",error=error)
            raise


if __name__=="__main__":
    controller(*map(Path,sys.argv[1:]))


