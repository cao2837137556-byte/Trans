"""Exercise the packed snapshot reader and the requested conditional denominators on D."""

import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

import numpy as np


def unpack(p, d):
    with tarfile.open(p, "r:gz") as t:
        for m in t:
            target = d / m.name
            if not m.isfile() or not target.resolve().is_relative_to(d):
                raise ValueError("ARCHIVE_SCOPE")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(t.extractfile(m).read())


def table_fixture(out):
    from report_ton import build_tables, aggregate, verify, fill
    from common_ton import LAYERS, csv_table, require

    hosts = {
        "h": dict(role="fixture host", main_identity="UNCONFIRMED", reverse_sll_changed=True),
        "e": dict(role="fixture empty", main_identity="CONFIRMED", reverse_sll_changed=False),
    }
    card = dict(hosts=hosts)
    allrows = {k: [] for k in ("raw", "main", "supplement", "boundary")}
    for host in hosts:
        rows = [
            dict(
                kind="attack" if i < 5 else "normal",
                conn=str(i // 2),
                off=i != 0,
                data=i in (1, 2, 5),
                crossing=i == 5,
            )
            for i in range(7)
        ]
        raw = np.ones((7, 4))
        raw[4] = -1
        fixed = raw.copy()
        fixed[[1, 5]] = -1
        support = np.array([0.5, 0.7, 0.0, 0.2, 0.4, 0.3, 0.0])
        if host == "e":
            raw[:] = -1.0
            fixed = raw.copy()
            support[:] = 0.0
        admission = []
        for k in ("attack", "normal"):
            for layer in LAYERS:
                rr = [
                    r
                    for r in rows
                    if r["kind"] == k
                    and (layer == "all" or r["off"] and (layer == "off_bypass" or r["data"]))
                ]
                admission.append(
                    dict(
                        host=host,
                        kind=k,
                        layer=layer,
                        candidate=len(rr),
                        candidate_connections=len({r["conn"] for r in rr}),
                    )
                )
        result = build_tables(
            host,
            rows,
            support,
            raw,
            raw > 0,
            fixed,
            np.ones(7, bool),
            np.ones(7, bool),
            card,
            dict(counts=admission, cuts=[0.0] * 4, ready=True),
        )
        for k in result:
            allrows[k].extend(result[k])

    def cell(k, host, layer):
        return next(r for r in allrows[k] if (r["host"], r["head"], r["layer"]) == (host, "ensemble", layer))

    require(cell("main", "h", "off_bypass")["A"] == "未评价", "UNKNOWN_IS_NOT_ZERO")
    a = cell("supplement", "h", "off_bypass")
    b = cell("supplement", "h", "off_bypass_with_transport_data")
    require(
        (
            a["A"],
            a["B"],
            a["W"],
            a["overall_retention"],
            a["withdrawal_given_positive_support"],
            a["normal_fp_reduced"],
        )
        == (3, 2, 1, 2 / 3, 0.5, 1),
        "A_B_W_ABOVE_SUPPORT",
    )
    require((b["A"], b["B"], b["W"]) == (2, 1, 1), "DATA_SUBSET_DENOMINATOR")
    require(cell("main", "e", "off_bypass")["overall_retention"] == "不适用", "ZERO_A")
    test = dict(a)
    test.update(B=0, W=0, retained=test["A"])
    require(fill({}, test)["withdrawal_given_positive_support"] == "不适用", "ZERO_B")
    for k in ("main", "supplement"):
        allrows[k].extend(aggregate(allrows[k]))
    for k, n in [
        ("raw", "RAW_TARGETS.csv"),
        ("main", "CCNR_MAIN.csv"),
        ("supplement", "CCNR_PAIRED.csv"),
        ("boundary", "NORMAL_BOUNDARY.csv"),
    ]:
        csv_table(out / n, allrows[k])
    return verify(out, card)


def smoke(new, old, target):
    # Use the actual executable package and the production source closure.
    sys.path.insert(0, str(new))
    from common_ton import read, dump, require
    from frozen_env import setup

    root = Path(__file__).resolve().parent
    setup(root.parents[1], local_runtime=old)
    from frontend import collect, reference_selection, db_create
    from representations import reconstructed

    cfg, card = read(new / "SCOPED_INPUTS.json"), read(new / "DIAGNOSTIC_CARD.json")
    paths = {k: Path(p) for k, p in read(root / ".private/LOCAL_INPUTS.json").items()}
    db = db_create(target / "slice.sqlite")
    v = collect(
        db,
        paths,
        cfg,
        card,
        target,
        Path("C:/Program Files/Wireshark/tshark.exe"),
        True,
        lambda *a, **k: None,
    )
    ref = reference_selection(db, cfg, card, v["cut_frames"], True)
    n = 0
    for uid, proto, q, flow, prov, witness in reconstructed(db, cfg, card, v):
        off, ctx = db.execute("SELECT off,ctx FROM point WHERE uid=?", (uid,)).fetchone()
        require(
            witness
            and len(q) == 14
            and len(np.frombuffer(ctx, "<f8")) == 8
            and bool(off) == (not (q[0] == 1 and q[2] == 1 and q[5] == 0)),
            "LOCAL_REAL_DESCRIPTOR_AND_GUARD",
        )
        n += 1
    db.close()
    require(n == v["independent_snapshots"] and n > 0, "LOCAL_REBUILT_REAL_SLICE")
    report = dict(
        real_frames=v["decoded_frames"],
        identical_snapshots=n,
        selected_references={k: x["selected"] for k, x in ref.items()},
        conditional_metric_fixture=table_fixture(target),
        local_neural_forwards=0,
    )
    dump(target / "VALIDATED.json", report)


def main():
    root = Path(__file__).resolve().parent
    private = root / ".private"
    archive = private / "package.tar.gz"
    old_archive = (
        root.parent / "unified_reference_bank_k8192_v1_20261113/.private/package_early_183987.tar.gz"
    )
    with tempfile.TemporaryDirectory(prefix="ton-qa-", dir=private) as t:
        d = Path(t)
        new = d / "new"
        old = d / "old"
        out = d / "checks"
        out.mkdir()
        unpack(old_archive, old)
        unpack(archive, new)
        subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(Path(__file__).resolve()),
                "smoke",
                str(new),
                str(old),
                str(out),
            ],
            check=True,
        )
        result = json.loads((out / "VALIDATED.json").read_bytes())
    from common_ton import dump, sha

    result.update(
        status="PASS",
        tested_artifact="extracted real sources, not a submitted HPC job",
        archive_sha256=sha(archive),
        manifest_sha256=sha(root / "PACKAGE_MANIFEST.json"),
    )
    dump(root / "LOCAL_VALIDATION.json", result)
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    if sys.argv[1:2] == ["smoke"]:
        smoke(*map(Path, sys.argv[2:]))
    else:
        main()
