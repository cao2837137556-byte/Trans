"""Pin the accepted role replay and package the new source for isolated retries."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROLE = HERE.parent/"p4_ccnr_role_port_v1_20261121"
sys.path.insert(0, str(HERE.parent/"p4_ccnr_history60_v1_20261120"))
from history_common import HEADS, POOLS, artifact, check, read, sha, write
sys.path.pop(0)


def build(slot):
    assert 0 <= slot < 5
    old = ROLE/"received"
    returns = old/"RETURN.json"
    assert sha(returns) == read(old/"LOCAL_ACCEPTANCE.json")["return_sha256"]
    for name, pin in read(returns)["files"].items():
        check(old/name, pin)
    base = read(old/"ACCEPTANCE.json")
    old_seal = read(ROLE/"LOCAL_SEAL.json")
    src = check(ROLE/".private/package.tar.gz", old_seal["package"])
    with tarfile.open(src) as t:
        raw_manifest = t.extractfile("PACKAGE_MANIFEST.json").read()
        digest = hashlib.sha256(raw_manifest).hexdigest()
        assert digest == base["manifest_sha256"] == old_seal["manifest_sha256"]
        manifest = json.loads(raw_manifest)
        assert manifest["run"] == read(old/"INSTALL.json")["run"]
        bootstrap = ("history_common.py","history_stream.py","paired_history.py","inputs_history.py","role_inputs.py",
                     "roles.py","screen_geometry.py","common_round1.py","reports.py","slurm_base.py","run.slurm",
                     "INPUT_PINS.json","ROLE_PINS.json","BASELINE.json")
        files = {n:t.extractfile(n).read() for n in bootstrap}
        assert all(hashlib.sha256(b).hexdigest() == manifest["files"][n] for n,b in files.items())
        cfg = json.loads(t.extractfile("CONTRACT.json").read())
    cells = {}
    with (old/"PAIRED.csv").open(encoding="utf8", newline="") as stream:
        for r in csv.DictReader(stream):
            if r["arm"] == "R1_U1":
                k = (r["group"],r["seed"])
                assert k not in cells
                cells[k] = [int(r[c]) for c in ("total","raw","alert")]
    groups = {g:[cells[g, seed] for seed in HEADS] for g in sorted({g for g,_ in cells})}
    assert groups["TON.195.payload.c"][-1] == [18194,14024,14024]
    assert json.loads(files["BASELINE.json"])["TON.195.payload.c"][-1] == [18194,14024,245]
    array = read(old/"HPC_ARRAY_SHA.json")["decisions"]
    tables = {}
    for phase,pool in zip(("cic","unsw","edge","ton","password"),POOLS):
        pin = read(old/f"{pool}_ROLE_CENSUS.json")
        tables[pool] = {"roles": {k:pin[k] for k in ("file","bytes","sha256")}, "decisions":array[phase]}
    frozen = {k:cfg[k] for k in ("cuts","scales")}
    pins = dict(run=manifest["run"], manifest=digest, score=frozen, pools=tables, paired_R1=groups,
                parent_return_sha256=sha(returns))
    write(HERE/"HANDSHAKE_PINS.json", pins)
    method = (HERE/"METHOD.md").read_bytes().replace(b"\r\n",b"\n")
    write(HERE/"CONTRACT.json", {**frozen, "method_sha256":hashlib.sha256(method).hexdigest(),
          "p":4, "lambda":.25, "handshake_divisor":3, "window_seconds":60, "training":False,
          "query_unavailable":"unchanged_baseline","reference_unavailable":"omit_from_handshake_search"})
    for n in ("METHOD.md","HANDSHAKE_PINS.json","CONTRACT.json","launch.py","worker_handshake.py","handshake_inputs.py",
              "handshake_geometry.py","handshake_tables.py","report_handshake.py","unsw_audit.py"):
        files[n] = (HERE/n).read_bytes().replace(b"\r\n",b"\n")
    assert files["run.slurm"].count(b"/worker_roles.py") == 1
    files["run.slurm"] = files["run.slurm"].replace(b"/worker_roles.py", b"/worker_handshake.py")
    scheduler = files["slurm_base.py"]
    assert scheduler.count(b"phase == 'preflight'") >= 2
    files["slurm_base.py"] = scheduler.replace(b"wall = 2700 if phase == 'preflight'",
        b"wall = 2700 if phase.startswith('check_')").replace(
        b"'00:45:00' if phase == 'preflight'", b"'00:45:00' if phase.startswith('check_')")
    assert files["slurm_base.py"] != scheduler
    for n,b in files.items():
        assert b"\r\n" not in b
        if n.endswith(".py"):
            compile(b,n,"exec")
    run = HERE.name + f"_r{slot}"
    seal = dict(run=run, experiment=HERE.name, attempt=slot,
                files={k:hashlib.sha256(v).hexdigest() for k,v in sorted(files.items())})
    write(HERE/"PACKAGE_MANIFEST.json", seal)
    files["PACKAGE_MANIFEST.json"] = (HERE/"PACKAGE_MANIFEST.json").read_bytes()
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w") as t:
        for n,b in sorted(files.items()):
            info = tarfile.TarInfo(n)
            info.size = len(b)
            info.mode = 0o600
            t.addfile(info, io.BytesIO(b))
    private = HERE/".private"
    private.mkdir(exist_ok=True)
    archive = private/"package.tar.gz"
    archive.write_bytes(gzip.compress(out.getvalue(), mtime=0))
    with tarfile.open(archive) as t:
        assert set(t.getnames()) == set(files)
        assert all(t.extractfile(n).read() == b for n,b in files.items())
    write(HERE/"LOCAL_SEAL.json", dict(run=run, slot=slot, archive=artifact(archive),
          manifest_sha256=sha(HERE/"PACKAGE_MANIFEST.json"), method_sha256=sha(HERE/"METHOD.md")))
    print(run, len(files), archive.stat().st_size, sha(archive))


if __name__ == "__main__":
    build(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
