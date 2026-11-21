"""Submit scoped jobs, release each phase only after its compute receipt passes."""
from pathlib import Path
import fcntl
import sys
import traceback

import slurm_base
from history_common import HERE, remote_run, read, write, sha, artifact
from report_history import paper

BATCHES=(("preflight",),("calibrate",),("cic","unsw","edge","ton","password"),("donors","formal"))
PHASES=tuple(p for group in BATCHES for p in group)


def main(project,out):
    mf=read(HERE/"PACKAGE_MANIFEST.json")
    run=remote_run(mf["attempt"])
    assert mf["run"]==run and out==project/"runs"/run and HERE==out/"package"
    package=sha(HERE/"PACKAGE_MANIFEST.json")
    for n,h in mf["files"].items():
        assert sha(HERE/n)==h
    slurm_base.NAMES={phase:f"p04-history60-{mf['attempt']}-{phase}" for phase in PHASES}
    jobs={}
    with (out/".dispatch.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            for phases in BATCHES:
                for phase in phases:
                    slurm_base.live(out,"VALIDATE_SUBMISSION",phase=phase,jobs=jobs)
                    jobs[phase]=slurm_base.submission(project,out,phase)
                for phase in phases:
                    j=jobs[phase]
                    slurm_base.wait_job(out,phase,j)
                    cert=read(out/(phase.upper()+".json"))
                    assert cert["status"]=="PASS" and cert["job"]==j and cert["package"]==package and cert["node"]
                    if phase=="preflight":
                        assert cert["baseline_cells"]==len(read(HERE/"BASELINE.json"))
                        assert set(cert["real_donor_probe"])=={"TON","EDGE","EDGE_PASSWORD"}
            proof=read(out/"RESULT.json")
            assert proof["all_alerts_monotone"] and proof["baseline_cells"]==len(read(HERE/"BASELINE.json"))
            (out/"RESULTS_FOR_PAPER.md").write_bytes(paper(out).encode("utf8"))
            write(out/"ACCEPTANCE.json",dict(status="PASS",scope="FROZEN_V12_HISTORY60_REPLAY",jobs=jobs,
                   manifest_sha256=package,paper=artifact(out/"RESULTS_FOR_PAPER.md"),gate=proof["advance"]))
            stage="COMPLETE"
        except Exception as e:
            tails={}
            for phase,j in jobs.items():
                p=out/f"{phase}-{j}.err"
                if p.is_file():
                    with p.open("rb") as stream:
                        stream.seek(max(0,p.stat().st_size-16000))
                        tails[phase]=stream.read().decode("utf8","replace")
            write(out/"FAILURE.json",dict(error=str(e) or repr(e),traceback=traceback.format_exc(),stderr=tails))
            stage="STOP"
        names=["INSTALL.json","ACCEPTANCE.json","FAILURE.json","DONOR_PROBE.json",
               "THRESHOLD.json","RESULT.json","RESULTS_FOR_PAPER.md","PAIRED.csv","EQUAL_COST.csv",
               "HISTORY_COVERAGE.csv","FIRST_ALERT.csv","DONORS.csv","DONOR_SERVICES.csv","DONOR_MATCHED_COMPARISON.csv",
               "DONOR_DIAGNOSTIC.json"]
        names.extend(f"{pool}_INPUT.json" for pool in ("CIC_DEV","UNSW_DEV","EDGE","TON","EDGE_PASSWORD"))
        for phase in PHASES:
            names.extend((phase.upper()+".json",f"SCHEDULER_{phase}.json",f"JOB_{phase}.json",f"FAILURE_{phase}.json"))
        write(out/"RETURN.json",dict(files={n:artifact(out/n) for n in names if (out/n).is_file()}))
        slurm_base.live(out,stage,jobs=jobs,error=(read(out/"FAILURE.json")["error"] if stage=="STOP" else None))


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
