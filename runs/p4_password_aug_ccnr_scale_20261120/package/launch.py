"""Separate submissions, with an accepted compute receipt before each next stage."""
import fcntl
from pathlib import Path
import sys
import traceback
import slurm_base
from shared import HERE,read,write,artifact,sha
from report import paper


def main(project,out):
    m=read(HERE/"PACKAGE_MANIFEST.json")
    assert out==project/"runs"/m["run"] and HERE==out/"package"
    mh=sha(HERE/"PACKAGE_MANIFEST.json")
    for n,h in m["files"].items():assert sha(HERE/n)==h,n
    phases=("preflight","reproduce","formal")
    slurm_base.NAMES={k:"pwscale-"+m["run"].split("_")[-1]+"-"+k for k in phases}
    jobs={}
    with (out/".dispatch.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            for phase in phases:
                job=slurm_base.submission(project,out,phase)
                jobs[phase]=job
                slurm_base.wait_job(out,phase,job)
                v=read(out/(phase.upper()+".json"))
                assert v["job"]==job and v["package"]==mh and v["status"]=="PASS"
                if phase=="preflight": assert v["seed_and_ensemble_parity"] and v["real_queries"]>0
                if phase=="reproduce":
                    assert v["reproduction_sha"]==sha(out/"REPRODUCTION.json")
                    assert sum(read(out/"REPRODUCTION.json")["rows_checked"].values())==192
            assert (out/"RESULTS_FOR_PAPER.md").read_bytes()==paper(out).encode("utf8")
            write(out/"ACCEPTANCE.json",dict(status="PASS",scope="NO_TRAINING_PAIRED_SCALE_REPLAY",
                  jobs=jobs,manifest_sha=mh,paper=artifact(out/"RESULTS_FOR_PAPER.md")))
            stage="COMPLETE"
        except Exception as e:
            details={}
            for ph,j in jobs.items():
                p=out/f"{ph}-{j}.err"
                if p.exists():
                    with p.open("rb") as f:
                        f.seek(max(0,p.stat().st_size-16384));details[ph]=f.read().decode("utf8","replace")
            write(out/"FAILURE.json",dict(error=str(e) or repr(e),traceback=traceback.format_exc(),stderr=details))
            stage="STOP"
        names=["INSTALL.json","ACCEPTANCE.json","FAILURE.json","SOURCE.json","REPRODUCTION.json","HPC_MARGIN_SHA.json",
               "SCALES.csv","METRICS.csv","FOCUS.csv","NORMAL_ATTRIBUTION.csv","WINDOWS_MARGIN_QUANTILES.csv","RESULTS_FOR_PAPER.md"]
        for ph in phases:
            names.extend([ph.upper()+".json",f"SCHEDULER_{ph}.json",f"JOB_{ph}.json",f"FAILURE_{ph}.json"])
        write(out/"RETURN.json",dict(files={n:artifact(out/n) for n in names if (out/n).is_file()}))
        slurm_base.live(out,stage,jobs=jobs,error=(read(out/"FAILURE.json")["error"] if stage=="STOP" else None))


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
