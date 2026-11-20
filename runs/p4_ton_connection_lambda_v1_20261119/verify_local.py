"""Exercise the packaged replay with exact, independently predictable connection outcomes."""

import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import zlib


def smoke(root):
    import numpy as np

    sys.path.insert(0, str(root))
    from cached_replay import metadata, join, cached_flags, selected_connections, check_pilot_direct
    from connection_tables import summarize_host, finish_sweep, finish_misses, WIN, MID
    from result_checks import validate

    card = json.loads((root / "CACHE_PINS.json").read_bytes())
    method = card["method"]
    cuts = np.asarray(method["cuts"])
    scale = np.asarray(method["scales"])
    by = {}
    source = []
    db = sqlite3.connect(":memory:")
    db.executescript(
        "CREATE TABLE point(kind,uid,host,role,frame,conn,proto,off,data,owner,selected);CREATE TABLE feature(uid,q);CREATE TABLE event(role,frame,body);"
    )
    pops = {}
    uids = []
    inputs = {}
    # Three eligible attack connections: a withdrawn two-alert connection, a no-data miss and a data miss.
    # A low first frame with no RAW alert must not become the representative.
    event = 0
    templates = [
        ("normal", "reused", [(1.0, 0.9, 16, 0), (2.0, 0.95, 24, 1)]),
        ("attack", "reused", [(-1.0, 0.0, 2, 0), (2.0, 0.8, 16, 0), (3.0, 0.9, 24, 1)]),
        ("attack", "syn", [(-1.0, 0.0, 2, 0)]),
        ("attack", "data", [(-1.0, 0.0, 16, 1)]),
        ("attack", "control", [(-1.0, 0.0, 16, 0)]),
        ("attack", "partial", [(2.0, 0.8, 24, 1), (3.0, 0.0, 2, 0)]),
    ]
    for kind in ("normal", "attack"):
        kind_uids = []
        for host in card["hosts"]:
            for typ, conn, pks in templates:
                if kind != typ:
                    continue
                if host == "192.168.1.193" and kind == "normal":
                    continue
                for margin, sup, flags, data in pks:
                    event += 1
                    role = "password" if kind == "attack" else "normal2"
                    uid = hashlib.sha256(str(event).encode()).hexdigest()
                    q = np.zeros(14, "<f4")
                    q[0] = 1
                    q[1:10] = [(flags >> j) & 1 for j in range(9)]
                    off = (flags & 18) != 2
                    ready = host in card["paired_hosts"]
                    if not ready:
                        sup = 0
                    # Different frozen head cuts; use a common ensemble raw margin.
                    raw = np.array([cuts[3] + margin] * 3)
                    raw = np.r_[raw, raw.mean()]
                    x = raw[:3] - (0.25 * scale) * (1 - np.power(1.0 - sup, 4)) if off else raw[:3].copy()
                    cc = np.r_[x, x.mean()]
                    db.execute(
                        "insert into point values(?,?,?,?,?,?,?,?,?,?,?)",
                        (
                            kind,
                            uid,
                            host,
                            role,
                            event,
                            conn,
                            6,
                            int(off),
                            data,
                            card["hosts"][host]["owner"],
                            1,
                        ),
                    )
                    db.execute("insert into feature values(?,?)", (uid, q.tobytes()))
                    db.execute(
                        "insert into event values(?,?,?)",
                        (
                            role,
                            event,
                            zlib.compress(
                                json.dumps({"frame.number": str(event), "tcp.flags": hex(flags)}).encode()
                            ),
                        ),
                    )
                    h = inputs.setdefault(host, {})
                    row = dict(
                        uid=np.bytes_(uid),
                        index=len(source),
                        raw=raw,
                        ccnr=cc,
                        raw_alarm=raw > cuts,
                        ccnr_alarm=cc > cuts,
                        support=sup,
                        opened=ready,
                        reference_eligible=ready,
                        off_bypass=off,
                        transport_data=bool(data),
                    )
                    for k, v in row.items():
                        h.setdefault(k, []).append(v)
                    source.append(raw)
                    uids.append(uid)
                    kind_uids.append(uid)
        pops[kind] = dict(
            rows=len(kind_uids),
            uid_order_sha256=hashlib.sha256("".join(u + "\n" for u in kind_uids).encode()).hexdigest(),
        )
    card.update(populations=pops, order=hashlib.sha256("".join(u + "\n" for u in uids).encode()).hexdigest())
    by = metadata(db, card)
    one = []
    two = []
    three = []
    for host in by:
        path = root / (host + ".npz")
        np.savez(path, **inputs[host])
        d = join(by[host], path, np.asarray(source), host in card["paired_hosts"])
        assert cached_flags(db, d) > 0
        # Deliberately reverse the physical array order to exercise earliest-frame selection.
        ds = selected_connections({k: v[::-1] for k, v in d.items()})
        rows, m, q, _ = summarize_host(ds, host, method, host in card["paired_hosts"])
        check_pilot_direct(ds, rows, m, q, method, host in card["paired_hosts"], host)
        assert (
            m["entirely_missed"],
            m["pure_SYN_only"],
            m["other_zero_data"],
            m["has_data_connections"],
        ) == (3, 1, 1, 1)
        if host == WIN:
            assert (
                q[0]["cohort_connections"] == 1
                and q[0]["original_alarm_packets"] == 2
                and q[0]["margin_median"] == 2
                and q[1]["margin_median"] == 2.5
            )
        if host == MID:
            assert (
                q[0]["cohort_connections"] == 1
                and q[0]["margin_median"] == 1
                and q[1]["margin_median"] == 1.5
            )
        one.extend(rows)
        two.append(m)
        three.extend(q)
    db.close()
    checks = validate(finish_sweep(one), finish_misses(two), three, formal=False)
    print(json.dumps(checks))


def main():
    from pack import HERE, PRIVATE, hexdigest, encode

    data = PRIVATE / "package.tar.gz"
    with tempfile.TemporaryDirectory(dir=PRIVATE, prefix="qa-") as tmp:
        root = Path(tmp)
        with tarfile.open(data) as t:
            for m in t:
                p = root / m.name
                assert m.isfile() and p.resolve().parent == root
                p.write_bytes(t.extractfile(m).read())
        for k, v in json.loads((root / "PACKAGE_MANIFEST.json").read_bytes())["files"].items():
            assert hexdigest((root / k).read_bytes()) == v
        result = subprocess.run(
            [sys.executable, "-X", "utf8", "-B", str(Path(__file__).resolve()), "smoke", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        if result.returncode:
            raise RuntimeError(result.stderr)
        checks = json.loads(result.stdout)
    v = dict(
        status="PASS",
        checks=checks,
        scientific_results=False,
        cache_fixture=True,
        archive_sha256=hexdigest(data.read_bytes()),
        package_manifest_sha256=hexdigest((HERE / "PACKAGE_MANIFEST.json").read_bytes()),
    )
    (HERE / "LOCAL_VALIDATION.json").write_bytes(encode(v))
    print(v)


if __name__ == "__main__":
    if sys.argv[1:2] == ["smoke"]:
        smoke(Path(sys.argv[2]))
    else:
        main()
