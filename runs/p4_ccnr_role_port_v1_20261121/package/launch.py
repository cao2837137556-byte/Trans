"""Run each real-data preflight, jointly seal its results, then submit all replay jobs."""
import fcntl
from pathlib import Path
import sys
import traceback

import slurm_base
from history_common import HERE, artifact, check, read, save, sha, write
from report_roles import paper, rows

STEMS=("cic","unsw","edge","ton","password")
CHECKS=tuple("check_"+p for p in STEMS)
ALL=CHECKS+STEMS
POOLS=("CIC_DEV","UNSW_DEV","EDGE","TON","EDGE_PASSWORD")


def collect(out,project,certificates):
    expected=read(HERE/"BASELINE.json")
    assert sum(v["baseline_views"] for v in certificates.values())==len(expected)==30
    small={}
    large={}
    for phase,c in certificates.items():
        for n,pin in c["tables"].items():
            check(out/n,pin)
            assert n not in small
            small[n]=pin
        large[phase]=c["large"]
    for suffix in ("PAIRED","MECHANISM","HANDSHAKE"):
        all_rows=[]
        for pool in POOLS:
            p=out/f"{pool}_{suffix}.csv"
            if p.is_file():
                all_rows.extend(rows(p))
        if suffix=="HANDSHAKE":
            source=read(out/"CHECK_CIC.json").get("source_handshake")
            if source:
                all_rows.append(source)
        save(out/f"{suffix}.csv",all_rows)
    write(out/"HPC_ARRAY_SHA.json",dict(decisions=large))
    text=paper(out)
    (out/"RESULTS_FOR_PAPER.md").write_bytes(text.encode("utf8"))


def main(project,out):
    manifest=read(HERE/"PACKAGE_MANIFEST.json")
    assert out==project/"runs"/manifest["run"] and HERE==out/"package"
    package=sha(HERE/"PACKAGE_MANIFEST.json")
    for n,h in manifest["files"].items():
        check(HERE/n,{"sha256":h})
    slurm_base.NAMES={p:f"p4-role21-{manifest['attempt']}-{p}" for p in ALL}
    jobs={}
    with (out/".dispatch.lock").open("a") as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            for series in (CHECKS,STEMS):
                for p in series:
                    slurm_base.live(out,"VALIDATE_SUBMISSION",phase=p,jobs=jobs)
                    jobs[p]=slurm_base.submission(project,out,p)
                accepted={}
                for p in series:
                    j=jobs[p]
                    slurm_base.wait_job(out,p,j)
                    v=read(out/(p.upper()+".json"))
                    assert v["status"]=="PASS" and v["package"]==package and v["job"]==j and v["node"]
                    accepted[p]=v
                if series==CHECKS:
                    coverage=[]
                    for p,v in accepted.items():
                        assert v["raw"]["raw_samples"]>0 and v["small_slice"]>0 and v["geometry"]["matrix_pairs"]>0
                        coverage.extend(v["coverage"])
                    assert sum(v["baseline_views"] for v in accepted.values())==30
                    save(out/"ROLE_COVERAGE.csv",coverage)
                    write(out/"PREP_RECEIPT.json",dict(status="PASS",method="R2_U1",role_scope="full",
                        checks_sha256={p[6:]:sha(out/(p.upper()+".json")) for p in accepted},
                        coverage=coverage,coverage_table=artifact(out/"ROLE_COVERAGE.csv")))
            collect(out,project,accepted)
            write(out/"ACCEPTANCE.json",dict(status="PASS",scope="ROLE_PORT_FROZEN_V12_PAIRED",main="R2_U1",
                jobs=jobs,manifest_sha256=package,paper=artifact(out/"RESULTS_FOR_PAPER.md"),
                independent_validation_or_model_change=False))
            stage="COMPLETE"
        except Exception as e:
            logs={}
            for p,j in jobs.items():
                f=out/f"{p}-{j}.err"
                if f.is_file():
                    with f.open("rb") as stream:
                        stream.seek(max(0,f.stat().st_size-16000))
                        logs[p]=stream.read().decode("utf8","replace")
            write(out/"FAILURE.json",dict(error=str(e) or repr(e),traceback=traceback.format_exc(),stderr=logs))
            stage="STOP"
        names=["INSTALL.json","ACCEPTANCE.json","FAILURE.json","PREP_RECEIPT.json","ROLE_COVERAGE.csv",
               "PAIRED.csv","MECHANISM.csv","HANDSHAKE.csv","HPC_ARRAY_SHA.json","RESULTS_FOR_PAPER.md",
               "EDGE_NORMAL_BY_SERVICE.csv","EDGE_NORMAL_MECHANISM_BY_SERVICE.csv","EDGE_502_443.csv"]
        for p in ALL:
            names.extend([p.upper()+".json",f"JOB_{p}.json",f"SCHEDULER_{p}.json",f"FAILURE_{p}.json"])
        for pool in POOLS:
            names.extend((pool+"_ROLE_CENSUS.json",pool+"_RAW_ANCHORS.json"))
        write(out/"RETURN.json",dict(files={n:artifact(out/n) for n in names if (out/n).is_file()}))
        slurm_base.live(out,stage,jobs=jobs,error=(read(out/"FAILURE.json")["error"] if stage=="STOP" else None))


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
