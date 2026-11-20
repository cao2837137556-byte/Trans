"""Exercise the sealed input membership and zero-denominator reporting on D."""

import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile


def unpack(archive, root):
    with tarfile.open(archive, "r:gz") as t:
        for member in t:
            path = root / member.name
            if not member.isfile() or not path.resolve().is_relative_to(root):
                raise ValueError("ARCHIVE_SCOPE")
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(t.extractfile(member).read())


def fixture():
    import numpy as np
    from dad_stats import COUNTS, table, validate

    rows = [dict(capture_id=day) for day, n in COUNTS.items() for i in range(n)]
    votes = np.zeros((len(rows), 4))
    new = votes.copy()
    support = np.zeros(len(rows))
    bypass = np.zeros(len(rows), bool)
    ix = np.flatnonzero([r["capture_id"] == "thu" for r in rows])
    votes[ix[:10], :3] = 1
    new[:] = votes
    support[ix[:5]] = 1
    new[ix[:3], :2] = -1
    votes[:, 3] = votes[:, :3].mean(1)
    new[:, 3] = new[:, :3].mean(1)
    bypass[np.flatnonzero([r["capture_id"] == "sun" for r in rows])[:16]] = True
    out = table(rows, votes, new, support, bypass, np.zeros(4))
    th = [r for r in out if r["group"] == "thu"]
    validate(out, th)
    x = th[-1]
    assert (x["A"], x["B"], x["W"], x["retained"], x["retention"], x["withdrawal_given_support"]) == (
        10,
        5,
        3,
        7,
        0.7,
        0.6,
    )
    for raw, s in [(votes * 0, support), (votes, support * 0)]:
        o = table(rows, raw, raw, s, bypass, np.zeros(4))
        d = next(r for r in o if r["group"] == "thu" and r["head"] == "ensemble")
        assert d["W"] == 0 and d["withdrawal_given_support"] == "不适用"
        assert d["retention"] == ("不适用" if d["A"] == 0 else 1)
    return True


def replay(pkg, old, folder):
    import numpy as np

    sys.path[:0] = [str(pkg), str(old), str(old / "repo/ood"), str(old / "vendor")]
    from common_ton import read, dump, sha
    from dad_frontend import replay_inputs

    exe = Path("C:/Program Files/Wireshark/tshark.exe")
    assert sha(old / "PACKAGE_MANIFEST.json") == read(pkg / "FROZEN.json")["runtime_manifest_sha256"]
    for n, h in read(pkg / "PACKAGE_MANIFEST.json")["files"].items():
        assert sha(pkg / n) == h
    receipts = {}
    for pilot in (True, False):
        f = folder / ("pilot" if pilot else "full")
        f.mkdir()
        s = replay_inputs(f, pkg, exe, pilot, lambda *a, **k: None)
        with np.load(f / "input.npz", allow_pickle=False) as data:
            assert data["q"].shape == (s["queries"] + s["references"], 14) and data["x"].shape == (
                len(data["q"]),
                8,
            )
            if pilot:
                pids = data["uid"]
                pq = data["q"]
                px = data["x"]
            else:
                lookup = {u: i for i, u in enumerate(data["uid"])}
                ix = [lookup[u] for u in pids]
                assert np.array_equal(pq, data["q"][ix]) and np.array_equal(px, data["x"][ix])
        receipts["pilot" if pilot else "full"] = {
            k: s[k]
            for k in (
                "references",
                "queries",
                "selected_uid_order",
                "bank_order",
                "pilot_witnesses",
                "cross_component_regression",
            )
        }
    dump(
        folder / "test.json",
        dict(status="PASS", local_neural_forwards=0, frontend=receipts, conditional_counts=fixture()),
    )


def main():
    from pack import HERE, PRIVATE, RUNS, hexdigest

    archive = PRIVATE / "package.tar.gz"
    previous = RUNS / "unified_reference_bank_k8192_v1_20261113/.private/package_early_183987.tar.gz"
    assert (
        hexdigest(previous.read_bytes()) == "7e86ae2700c8620105c99d995815fb7a88ab8369b06a7a56d963d47e51e7956f"
    )
    with tempfile.TemporaryDirectory(dir=PRIVATE, prefix="verify-") as tmp:
        root = Path(tmp)
        pkg = root / "package"
        old = root / "frozen"
        unpack(archive, pkg)
        unpack(previous, old)
        subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-B",
                str(Path(__file__).resolve()),
                "test",
                str(pkg),
                str(old),
                str(root),
            ],
            check=True,
        )
        v = json.loads((root / "test.json").read_bytes())
    v.update(
        archive_sha256=hexdigest(archive.read_bytes()),
        manifest_sha256=hexdigest((HERE / "PACKAGE_MANIFEST.json").read_bytes()),
    )
    (HERE / "LOCAL_VALIDATION.json").write_bytes(
        (json.dumps(v, ensure_ascii=False, indent=2) + "\n").encode()
    )
    print(v)


if __name__ == "__main__":
    if sys.argv[1:2] == ["test"]:
        replay(*map(Path, sys.argv[2:]))
    else:
        main()
