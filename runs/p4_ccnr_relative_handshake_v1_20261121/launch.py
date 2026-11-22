"""Gate formal jobs on real-data preflight and publish a small verified return."""
import fcntl
from pathlib import Path
import sys
import traceback

from history_common import HERE, POOLS, artifact, check, read, save, sha, write
from report_handshake import paper, rows
import slurm_base

STEPS = ("cic", "unsw", "edge", "ton", "password")
CHECKS = tuple("check_"+x for x in STEPS)
ACTIONS = CHECKS + STEPS


def complete_preflight(out, certs):
    assert sum(c["baseline_views"] for c in certs.values()) == len(read(HERE / "BASELINE.json")) == 30
    assert all(c["raw_sample_count"] > 0 and c["input_790_real_rows"] > 0 and c["both_baselines_query_parity"]
               for c in certs.values())
    assert sum(c["geometry"]["oracle_comparisons"] for c in certs.values()) > 0
    for c in certs.values():
        for name, pin in c["audit_tables"].items():
            check(out / name, pin)
    coverage = out / "H_COVERAGE.csv"
    save(coverage, [x for c in certs.values() for x in c["coverage"]])
    write(out / "PREP_RECEIPT.json", dict(status="PASS", experiment=HERE.parent.name.rsplit("_r", 1)[0],
          checks_sha256={p[6:]:sha(out / (p.upper()+".json")) for p in certs},
          jobs={p:c["job"] for p,c in certs.items()}, coverage=artifact(coverage),
          unsw_attribution=artifact(out / "UNSW_ATTRIBUTION.json")))


def finalize(out, certs):
    for c in certs.values():
        for name, pin in c["tables"].items():
            check(out / name, pin)
    for name in ("PAIRED", "MECHANISM"):
        save(out / f"{name}.csv", [x for pool in POOLS for x in rows(out / f"{pool}_{name}.csv")])
    write(out / "HPC_ARRAY_SHA.json", dict(pools={pool: {v:certs[step][v] for v in ("decisions","histories")}
         for step,pool in zip(STEPS,POOLS)}, unsw_uid_audit=read(out/"UNSW_ATTRIBUTION.json")["sha"]))
    p = out / "RESULTS_FOR_PAPER.md"
    p.write_bytes(paper(out).encode("utf8"))
    return artifact(p)


def return_manifest(out):
    names = ["INSTALL.json", "ACCEPTANCE.json", "FAILURE.json", "PREP_RECEIPT.json",
             "H_COVERAGE.csv", "PAIRED.csv", "MECHANISM.csv", "HPC_ARRAY_SHA.json", "RESULTS_FOR_PAPER.md",
             "UNSW_ATTRIBUTION.json", "UNSW_ATTRIBUTION_BY_DEVICE_ROLE_PORT.csv", "UNSW_ATTRIBUTION_BY_CONNECTION.csv"]
    for phase in ACTIONS:
        names.extend((phase.upper()+".json", f"JOB_{phase}.json", f"SCHEDULER_{phase}.json", f"FAILURE_{phase}.json"))
    for pool in POOLS:
        names.extend((pool+"_HISTORY_SHA.json", pool+"_FRAME_PROOF.json"))
    write(out / "RETURN.json", dict(files={n: artifact(out/n) for n in names if (out/n).is_file()}))


def main(project, out):
    manifest = read(HERE / "PACKAGE_MANIFEST.json")
    assert HERE == out/"package" and out == project/"runs"/manifest["run"]
    for name, pin in manifest["files"].items():
        check(HERE/name, {"sha256":pin})
    package = sha(HERE/"PACKAGE_MANIFEST.json")
    slurm_base.NAMES = {p:f"p4-hrel21-{manifest['attempt']}-{p}" for p in ACTIONS}
    jobs = {}
    with (out/".dispatch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            for series in (CHECKS, STEPS):
                for phase in series:
                    slurm_base.live(out, "VALIDATE_SUBMISSION", phase=phase, jobs=jobs)
                    jobs[phase] = slurm_base.submission(project, out, phase)
                certs = {}
                for phase in series:
                    job = jobs[phase]
                    slurm_base.wait_job(out, phase, job)
                    c = read(out / (phase.upper()+".json"))
                    assert c["status"] == "PASS" and c["job"] == job and c["node"] and c["package"] == package
                    certs[phase] = c
                if series == CHECKS:
                    complete_preflight(out, certs)
            headline = finalize(out, certs)
            write(out/"ACCEPTANCE.json", dict(status="PASS", scope="FROZEN_V12_DEVICE_LOCAL_HANDSHAKES",
                  jobs=jobs, manifest_sha256=package, paper=headline, training=False,
                  preflight=artifact(out/"PREP_RECEIPT.json")))
            stage, error = "COMPLETE", None
        except Exception as exc:
            error = str(exc) or repr(exc)
            logs = {}
            for phase, job in jobs.items():
                f = out/f"{phase}-{job}.err"
                if f.is_file():
                    with f.open("rb") as stream:
                        stream.seek(max(0,f.stat().st_size-16000))
                        logs[phase] = stream.read().decode("utf8","replace")
            write(out/"FAILURE.json", dict(error=error, traceback=traceback.format_exc(), stderr=logs))
            stage = "STOP"
        return_manifest(out)
        slurm_base.live(out, stage, jobs=jobs, error=error)
        if stage == "STOP":
            sys.exit(1)


if __name__ == "__main__":
    main(*map(Path, sys.argv[1:]))
