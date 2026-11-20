"""Dispatch the measured preflight, immutable training jobs and freeze receipt."""
import fcntl
import getpass
import json
from pathlib import Path
import sys
import traceback

from common_round1 import artifact, dump, load, sha
from slurm_base import command, live, wait_job

HERE = Path(__file__).resolve().parent
BASE_RUN = "p4_password_aug_v1_20261120"
PHASES = ("preflight","prepare","train_27","train_127","train_227","freeze","windows","regression",
          "edge_prepare",*[f"edge_{j}" for j in range(8)],"edge_assess")


def submit(project, out, phase):
    attempt=load(HERE/"PACKAGE_MANIFEST.json")["attempt"]
    name=f"p4-aug20-r{attempt}-{phase}"
    existing=command(["sacct","-X","-n","-P","-S","2026-11-20","-u",getpass.getuser(),
                      "-o","JobIDRaw,JobName%80"])
    queue=command(["squeue","-h","-u",getpass.getuser(),"-o","%i|%j"])
    assert existing["returncode"]==queue["returncode"]==0
    jobs={r[0] for status in (existing,queue) for line in status["stdout"].splitlines()
          for r in [line.strip().split("|")] if len(r)>1 and r[0].isdigit() and r[1]==name}
    receipt=out/("JOB_"+phase+".json")
    intent=out/("SUBMIT_INTENT_"+phase+".json")
    if receipt.exists():
        job=load(receipt)["job_id"]
        assert jobs <= {job}
        return job
    if intent.exists():
        if len(jobs)!=1: raise RuntimeError("unresolved prior submission: "+phase)
        job=jobs.pop()
    else:
        assert not jobs
        args=["--partition=amd","--no-requeue","--nodes=1","--ntasks=1","--cpus-per-task=4",
              "--mem=24G","--time="+("08:00:00" if phase in ("regression","edge_prepare","edge_assess") else "04:00:00"),
              "--job-name="+name,"--chdir="+str(HERE),
              "--output="+str(out/(phase+"-%j.out")),"--error="+str(out/(phase+"-%j.err")),
              str(HERE/"run.slurm"),phase,str(project),str(out),"0"]
        check=command(["sbatch","--test-only",*args])
        assert check["returncode"]==0,check["stderr"]
        dump(intent,dict(args=args))
        reply=command(["sbatch","--parsable",*args])
        job=reply["stdout"].strip().split(";")[0]
        assert reply["returncode"]==0 and job.isdigit(),reply["stderr"]
    dump(receipt,dict(job_id=job,phase=phase))
    return job


def main(project,out):
    manifest=load(HERE/"PACKAGE_MANIFEST.json")
    attempt=manifest["attempt"]
    run=BASE_RUN if attempt==0 else f"{BASE_RUN}_r{attempt}"
    assert attempt in range(5) and manifest["run"]==run and HERE==out/"package" and out==project/"runs"/run
    mh=sha(HERE/"PACKAGE_MANIFEST.json")
    for n,h in load(HERE/"PACKAGE_MANIFEST.json")["files"].items():
        assert sha(HERE/n)==h
    with (out/".controller.lock").open("a") as f:
        fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
        jobs={}
        try:
            for group in [("preflight",),("prepare",),("train_27","train_127","train_227"),("freeze",),
                          ("windows","regression"),("edge_prepare",),tuple(f"edge_{j}" for j in range(8)),("edge_assess",)]:
                if group==("edge_prepare",):
                    import asset_ingress
                    spec=load(HERE/"EDGE_ASSET.json")
                    asset_ingress.ensure(project,out,{"edgezip":dict(file="password-v5.zip",paths=[],**spec)},
                                         lambda stage,**kwargs:live(out,stage,**kwargs))
                for phase in group:
                    jobs[phase]=submit(project,out,phase)
                for phase in group:
                    wait_job(out,phase,jobs[phase])
                    receipt=load(out/(phase.upper()+".json"))
                    assert receipt["job"]==jobs[phase] and receipt["package"]==mh and receipt["status"]=="PASS"
                    if phase=="preflight":
                        assert receipt["node"] and receipt["original_frames_replayed"]==12 and receipt["train_updates"]>0
                        assert receipt["frozen_control_sha256"]==sha(out/"V12_BASELINE.csv")
            from final_report import report
            report(out)
            dump(out/"ACCEPTANCE.json",dict(status="PASS",scope="TRAINED_FROZEN_AND_EVALUATED",jobs=jobs,
                 package_sha256=mh,freeze=artifact(out/"CANDIDATE_FREEZE.json"), paper=artifact(out/"RESULTS_FOR_PAPER.md")))
            stage="COMPLETE"
        except Exception as err:
            dump(out/"CONTROLLER_FAILURE.json",dict(error=str(err) or repr(err),traceback=traceback.format_exc()))
            stage="STOP"
            traces={}
            for phase,job in jobs.items():
                path=out/f"{phase}-{job}.err"
                if path.is_file() and path.stat().st_size:
                    with path.open("rb") as f:
                        f.seek(max(0,path.stat().st_size-24576))
                        traces[phase]=f.read().decode("utf8","replace")
            dump(out/"COMPUTE_ERRORS.json",dict(jobs=jobs,stderr=traces))
        names={"INSTALL.json","ACCEPTANCE.json","CANDIDATE_FREEZE.json","CONTROLLER_FAILURE.json","EDGE_INPUTS.json",
               "EDGE_PASSWORD.csv","WINDOWS_CONNECTIONS.csv","FLOOD_NORMAL.csv","V12_BASELINE.csv",
               "TRAINING_INPUTS.json","VERIFIED_INPUTS.json","RESULTS_FOR_PAPER.md","COMPUTE_ERRORS.json","BASELINE_IMPORT.json"}
        for phase in PHASES:
            names.update((phase.upper()+".json",f"SCHEDULER_{phase}.json",f"JOB_{phase}.json",f"FAILURE_{phase}.json"))
        dump(out/"RETURN.json",dict(files={n:artifact(out/n) for n in sorted(names) if (out/n).is_file()}))
        live(out,stage,jobs=jobs,error=(load(out/"CONTROLLER_FAILURE.json")["error"] if stage=="STOP" else None))


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
