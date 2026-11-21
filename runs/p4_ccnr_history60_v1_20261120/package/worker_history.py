"""Slurm worker. Preflight and source calibration are mandatory before target replay."""
import os
from pathlib import Path
import resource
import subprocess
import sys
import time
import traceback

from history_common import HERE, remote_run, sha, read, write, check, progress

EXTRACTIONS={"cic":"CIC_DEV","unsw":"UNSW_DEV","edge":"EDGE","ton":"TON","password":"EDGE_PASSWORD"}


def dispatch(phase,project,out,package):
    contract=read(HERE/"CONTRACT.json")
    expected=read(HERE/"BASELINE.json")
    assert contract["rule_sha256"]==sha(HERE/"METHOD.md")
    if phase not in ("preflight","donor_probe"):
        pre=read(out/"PREFLIGHT.json")
        assert pre["status"]=="PASS" and pre["package"]==package
    if phase not in ("preflight","donor_probe","calibrate"):
        assert read(out/"CALIBRATE.json")["threshold_sha256"]==sha(out/"THRESHOLD.json")
    if phase=="preflight":
        from extract_history import preflight
        proof=preflight(project,out,contract,expected)
        subprocess.run([sys.executable,"-B",str(__file__),"donor_probe",str(project),str(out)],check=True)
        proof["real_donor_probe"]=read(out/"DONOR_PROBE.json")["proof"]
        assert all(int(v["queries"])>0 for v in proof["real_donor_probe"].values())
        return proof
    if phase=="donor_probe":
        from donors_history import audit
        return dict(proof=audit(project,out,contract,pilot=True))
    if phase=="calibrate":
        from extract_history import calibrate
        return calibrate(project,out)
    if phase in EXTRACTIONS:
        from extract_history import process
        return process(project,out,phase,EXTRACTIONS[phase],contract,expected)
    for step,pool in EXTRACTIONS.items():
        p=read(out/(step.upper()+".json"))
        assert p["status"]=="PASS" and p["package"]==package
        assert p["input_sha256"]==sha(out/(pool+"_INPUT.json"))
    if phase=="donors":
        from donors_history import audit
        return dict(proof=audit(project,out,contract))
    if phase=="formal":
        from paired_history import evaluate
        evaluate(out,contract,expected)
        return dict(result_sha256=sha(out/"RESULT.json"))
    raise ValueError(f"未知阶段 {phase}")


def main(phase,project,out):
    manifest=read(HERE/"PACKAGE_MANIFEST.json")
    run=remote_run(manifest["attempt"])
    assert manifest["run"]==run and out==project/"runs"/run and HERE==out/"package"
    assert not sys.flags.optimize and os.environ["SLURM_JOB_ID"].isdigit() and os.environ["SLURMD_NODENAME"]
    for n,h in manifest["files"].items():
        check(HERE/n,{"sha256":h})
    package=sha(HERE/"PACKAGE_MANIFEST.json")
    # Keep geometry and decoder process imports separated. All jobs use the
    # established byte-pinned Slurm environment.
    sys.path.append(str(project/"runs/p4_ton_password_frozen_v12_20261118/package"))
    from frozen_env import setup
    setup(project)
    progress(out,phase,"真实计算节点正在核验封存资产")
    start=time.monotonic()
    proof=dispatch(phase,project,out,package)
    proof.pop("status",None)
    write(out/(phase.upper()+".json"),dict(status="PASS",package=package,phase=phase,
        job=os.environ["SLURM_JOB_ID"],node=os.environ["SLURMD_NODENAME"],seconds=time.monotonic()-start,
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,**proof))
    progress(out,phase,"本阶段已写出通过回执")


if __name__=="__main__":
    phase=sys.argv[1];project,out=map(Path,sys.argv[2:4])
    try:
        main(phase,project,out)
    except Exception as exc:
        write(out/f"FAILURE_{phase}.json",dict(error=str(exc) or repr(exc),traceback=traceback.format_exc()))
        raise
