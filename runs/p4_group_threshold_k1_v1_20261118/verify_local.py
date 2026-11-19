"""Verify the actual packed entry points, return arithmetic and original reference identities."""

import hashlib
import json
from pathlib import Path
import sys
import tarfile
import tempfile

import numpy as np

from pack_v12 import HERE, PRIVATE, DUAL, RECAL, BASE, digest, read


def extract(archive, root, allow):
    with tarfile.open(archive, "r:gz") as tar:
        for m in tar:
            if not allow(m.name):
                continue
            path = root / m.name
            assert path.resolve().is_relative_to(root) and m.isfile()
            path.parent.mkdir(exist_ok=True, parents=True)
            path.write_bytes(tar.extractfile(m).read())


def exercise_reports(out):
    from calibration import four
    from common_round1 import dump
    from group_threshold import fit_groups, apply_groups, PRIMARY, SENS, POOL_ARM
    from mechanism import replay, validate_donors, K1, K2
    from port_audit import run as ports
    from tables_v12 import comparison_tables, views_by_outcome
    from paired_stats import csv_write, check_pairs
    from accept_v12 import verify_results, paper
    from worker import group_phase
    from vendor import p4_worker

    (out / "artifacts").mkdir()
    whole = {}
    gm = []
    gp = []
    km = []
    kp = []
    paths = []
    donor = []
    numbers = []
    for pool in ("CIC_DEV", "UNSW_DEV", "EDGE"):
        refs = []
        for proto, n in ((6, 100), (17, 4)):
            for i in range(n):
                key = [proto, ["192.0.2.1", 4100 + i], ["192.0.2.2", 53]]
                cid = hashlib.sha256(json.dumps(["fixture", key], separators=(",", ":")).encode()).hexdigest()
                refs.append(
                    dict(
                        uid="r" + str(len(refs)),
                        device="fixture",
                        capture_id="refcap",
                        component_id=cid,
                        partition="DEV",
                        protocol=proto,
                        reference_end=1.0,
                        frame=1,
                        timestamp=1.0,
                        use="REFERENCE",
                        label=0,
                        owner="fixture",
                        canonical_key=key,
                        source_sha256="fixture",
                    )
                )
        source = [0.1] * 4
        pooled = [0.9] * 4
        method = dict(cuts=source, scales=[4.0] * 3)
        rq = np.zeros((len(refs), 14))
        groups = fit_groups(
            refs,
            four(np.repeat(np.linspace(0.1, 0.6, len(refs))[:, None], 3, 1)),
            rq,
            source,
            pooled,
            ["fixture", "empty"],
            dict(budget=0.01, min_neff=100, protocols=[6, 17]),
        )
        f = dict(groups=groups, pooled=pooled)
        whole[pool] = f
        rows = [
            dict(
                uid=f"q{i}",
                device="fixture",
                capture_id="query",
                component_id="q",
                partition="DEV",
                protocol=17 if i in (4, 5) else 6,
                frame=i + 1,
                timestamp=2.0,
                label=int(i >= 3),
                source_role="NORMAL" if i < 3 else "UDP" if i in (4, 5) else "HTTP",
            )
            for i in range(8)
        ]
        n = len(rows)
        ids = [r["uid"] for r in rows]
        q = np.zeros((n, 14))
        q[6, [0, 2]] = 1
        active = np.ones(n, bool)
        active[7] = False
        raw = four(np.full((n, 3), 0.8))
        first = np.array([0.1, 0.1, 0.2, 0.2, 0.2, 0.2, 0.2, np.inf])
        second = np.array([np.inf, 0.75, 1.0, 0.75, 0.75, 1.0, 0.75, np.inf])
        idx = np.array([[0, -1], [0, 1], [0, 1], [0, 1], [100, 101], [100, 101], [0, 1], [-1, -1]])
        ca = dict(
            m1=first,
            m2=second,
            bank_rows=idx,
            opening=np.where(active, "", "TIME"),
            geometry_ready=active.copy(),
            legal_components=np.where(idx[:, 1] >= 0, 2, np.where(idx[:, 0] >= 0, 1, 0)),
            admitted=second < 1.0,
        )
        weak = ca["weak"] = np.where(ca["admitted"], 1 - second, 0.0)
        ca["scores_a"] = p4_worker.correct(raw, weak, q, method["scales"], True, power=4)
        ca["alarms_a"] = ca["scores_a"] > source
        ca["scores_b"] = ca["scores_a"]
        ca["alarms_b"] = ca["alarms_a"]
        views = {"full": (np.arange(n), np.arange(1.0, n + 1))}
        if pool != "EDGE":
            views["post_window_primary"] = (np.flatnonzero(active), np.arange(1.0, n + 1) * active)
        d = dict(
            ids=ids,
            rows=rows,
            raw=raw,
            p4=ca["scores_a"],
            q=q,
            active=active,
            saved=weak,
            views=views,
            expansion=np.ones(n) if pool == "EDGE" else None,
            population={"NORMAL": 3, "HTTP": 3, "UDP": 2} if pool == "EDGE" else None,
        )
        validate_donors(d, ca, refs)
        a = replay(d, ca, method)
        ps, route = apply_groups(d, groups, method, pooled)
        order = np.arange(n)
        sample = out / "pilot.npz"
        np.savez(sample, uid=ids, ix=order, group_source=ps[PRIMARY], group_pool=ps[SENS], route=route)
        expected, _ = comparison_tables(pool, d, {k: ps[k] for k in ("RAW", K2, POOL_ARM)}, [], {})
        m, p, _ = group_phase(pool, d, f, method, expected, sample, out)
        gm += m
        gp += p
        m, p = comparison_tables(pool, d, {K2: a["k2"], K1: a["k1"]}, [(K2, K1)], {})
        km += m
        kp += p
        paths += views_by_outcome(pool, d, a)
        lookup = dict(edge_binding=dict(owner="fixture", ip="192.0.2.1"))
        total, detail, info = ports(pool, d, refs, rq, ca, a, None, lookup, header_lookup=False)
        donor += total
        numbers.append(int((a["k2"][:6] & ~a["k1"][:6]).sum()))
        assert (
            info["canonical_unknown"] == 0
            and numbers[-1] > 0
            and any(int(x["same_ips_ports_differ"]) for x in total)
        )
    dump(out / "GROUP_THRESHOLDS.json", dict(pools=whole, source_cuts=source))
    for prefix, metrics, pairs in (("GROUP", gm, gp), ("K1", km, kp)):
        csv_write(out / (prefix + "_METRICS.csv"), metrics)
        csv_write(out / (prefix + "_PAIRS.csv"), pairs)
        csv_write(out / (prefix + "_HEADLINE.csv"), check_pairs(metrics, pairs, subset=prefix == "K1"))
    csv_write(out / "K1_PATHWAYS.csv", paths)
    csv_write(out / "PORT_HEADLINE.csv", donor)
    result = verify_results(out, dict(accepted_weak_mean_headlines=[]))
    assert "小样本回退" in paper(out, dict.fromkeys(("preflight", "groups", "k1", "ports"), "fixture"))
    return result


def main():
    archive = PRIVATE / "package.tar.gz"
    with tempfile.TemporaryDirectory(prefix="check-", dir=PRIVATE) as tmp:
        root = Path(tmp)
        new = root / "new"
        prev = root / "prev"
        old = root / "old"
        out = root / "fixture"
        out.mkdir()
        extract(archive, new, lambda _: True)
        older = BASE / ".private/package_early_183987.tar.gz"
        assert (
            digest(older.read_bytes()) == "7e86ae2700c8620105c99d995815fb7a88ab8369b06a7a56d963d47e51e7956f"
        )
        extract(older, old, lambda n: n.endswith(".py") or n in ("CONFIG.json", "PACKAGE_MANIFEST.json"))
        prior_archive = DUAL / ".private/package.tar.gz"
        assert digest(prior_archive.read_bytes()) == read(DUAL / "INSTALL_READBACK.json")["archive_sha256"]
        extract(prior_archive, prev, lambda _: True)
        sys.path[:0] = [str(new), str(prev), str(old), str(old / "repo/ood")]
        from common_round1 import verify_package, Inputs
        from reference_assets import bank
        from port_audit import identity
        from regressions import boundaries

        manifest = verify_package(new)
        assert (
            manifest["run"] == HERE.name
            and digest((prev / "PACKAGE_MANIFEST.json").read_bytes())
            == read(HERE / "ASSETS.json")["geometry_package"]
        )
        validations = boundaries()
        report = exercise_reports(out)
        from pack_v12 import RUNS

        store = Inputs(RUNS.parent, read(RECAL / "INPUT_PINS.json"), ("reference",), local=True)
        counts = {}
        for pool in ("CIC_DEV", "UNSW_DEV", "EDGE"):
            refs, *_ = bank(
                store, read(RECAL / "CONFIG.json"), pool, lambda *a, **k: None, local_partial=True
            )
            counts[pool] = dict(rows=len(refs), canonical_id_bound=sum(identity(r) is not None for r in refs))
        assert sum(v["rows"] for v in counts.values()) == 79069
    result = dict(
        status="PASS",
        environment="local_fixtures_and_real_reference_rosters",
        scientific_results=False,
        rule_sha256=read(HERE / "RULE_FREEZE.json")["card_sha256"],
        package_sha256=digest(archive.read_bytes()),
        regressions=validations,
        fixture_report_recounts=report,
        real_reference_identity=counts,
    )
    (HERE / "LOCAL_VALIDATION.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
