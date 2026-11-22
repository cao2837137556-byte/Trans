"""Run real-data preflight and four paired frozen replay arms on Slurm."""
import os
from pathlib import Path
import resource
import sys
import time
import traceback

import numpy as np

from history_common import HERE, artifact, check, progress, read, sha, uid_sha, write

STEMS = {"cic": "CIC_DEV", "unsw": "UNSW_DEV", "edge": "EDGE", "ton": "TON", "password": "EDGE_PASSWORD"}


def checkpoints(a, roles, histories):
    found = {}
    for i, h in enumerate(histories):
        evidence = -1 if h[0] < 0 else int(h[0] > 0)
        label = (str(a["kind"][i]), int(roles[i, 0]), bool(a["support"][i] > 0.),
                 bool(a["guard"][i]), evidence, int(h[1]))
        take = found.setdefault(label, [])
        if len(take) < 3:
            take.append(i)
    return np.asarray(sorted(i for group in found.values() for i in group))


def dispatch(phase, project, out, package):
    from handshake_geometry import alarms, replay
    from handshake_inputs import accepted_parent, rebuild
    from handshake_tables import distribution, summarize
    from paired_history import verify_base
    from role_inputs import materialize, npz, structure
    from unsw_audit import audit

    pilot = phase.startswith("check_")
    stem = phase[6:] if pilot else phase
    pool = STEMS[stem]
    cfg = read(HERE / "CONTRACT.json")
    pins = read(HERE / "HANDSHAKE_PINS.json")
    assert sha(HERE / "METHOD.md") == cfg["method_sha256"] and cfg["p"] == 4 and cfg["lambda"] == .25
    data = structure(project, pool, cfg)
    a = data["a"]
    role, parent = accepted_parent(project, pool, data, pins)
    qr, rr = role["query"], role["ref"]
    raw, original, _, views, seen = verify_base(pool, a, cfg, read(HERE / "BASELINE.json"))
    assert np.array_equal(raw, parent["RAW"]) and np.array_equal(original, parent["v12"])
    for name, v in views.items():
        expected = pins["paired_R1"][name]
        got = np.column_stack((np.full(4, v.n), v.any(raw).sum(axis=0), v.any(parent["R1_U1"]).sum(axis=0)))
        assert np.array_equal(got, expected), ("R1_SUMMARY_PARITY", name)

    rf = [r["uid"] for r in data["refs"]]
    cache = out / f"{pool}_HISTORY.npz"
    geometry_input = out / f"{pool}_HISTORY_SHA.json"
    if pilot:
        audit_tables = audit(out, data, parent, qr) if pool == "UNSW_DEV" else {}
        h, proof = rebuild(out, phase, pool, data)
        raw_sample_count = sum(len(x["samples"]) for x in proof["captures"].values())
        assert raw_sample_count > 0
        np.savez(cache, query_uid=a["uid"], ref_uid=rf, **h)
        raw_path = out / f"{pool}_FRAME_PROOF.json"
        write(raw_path, proof)
        coverage = distribution(pool, data, h)
        write(geometry_input, dict(**artifact(cache), coverage=coverage, raw_proof=artifact(raw_path),
                                   identical_inbound_tcp=proof["identical_inbound_tcp"],
                                   query_digest=uid_sha(a["uid"]), reference_digest=uid_sha(rf)))
        take = checkpoints(a, qr, h["query"])
        progress(out, phase, "真实小切片校验 790 维输入、原支持度和四空间检索", rows=len(take))
    else:
        f = out / f"CHECK_{stem.upper()}.json"
        p = read(f)
        prep = read(out / "PREP_RECEIPT.json")
        assert p["status"] == prep["status"] == "PASS" and p["package"] == package
        assert prep["checks_sha256"][stem] == sha(f) and p["history_sha256"] == sha(geometry_input)
        h = npz(check(cache, read(geometry_input)))
        assert np.array_equal(h["query_uid"], a["uid"]) and np.array_equal(h["ref_uid"], rf)
        take = np.arange(len(a["uid"]))
        progress(out, phase, "正在逐查询回放四组配置", rows=len(take))

    rows, z, q, x = materialize(project, data, take)
    assert np.array_equal(a["uid"][take], [r["uid"] for r in rows])
    assert z.shape[1] + q.shape[1] + x.shape[1] == 790
    qh = h["query"][take, 0]
    support = np.stack((a["support"][take], parent["U1_support"][0, take]))
    new, evidence, enabled, geometry = replay(
        rows, z, q, x, data, qr[take], rr, qh, h["reference"][:, 0], support,
        lambda n: progress(out, phase, "四空间距离、双组件检索和冻结判决", matrix_pairs=n), pilot=pilot)
    scores = alarms({k: v[take] for k, v in a.items()}, cfg, support, new, evidence, enabled)
    for arm in ("RAW","v12","R1_U1"):
        assert np.array_equal(scores[arm], parent[arm][take]), ("DECISION_PARITY", pool, arm)
    if pilot:
        assert geometry["precheck"]["matrix_pairs"] > 0
        return dict(baseline_views=seen, both_baselines_query_parity=True, geometry=geometry,
                    input_790_real_rows=len(take), raw_sample_count=raw_sample_count,
                    identical_inbound_tcp=proof["identical_inbound_tcp"],
                    history_sha256=sha(geometry_input), coverage=coverage, audit_tables=audit_tables,
                    sample_uid_order_sha256=uid_sha(r["uid"] for r in rows))
    large = out / f"{pool}_DECISIONS.npz"
    np.savez(large, uid=a["uid"], ref_uid=rf, support_base=support, support_handshake=new,
             counts=evidence, **scores)
    tables = summarize(out, pool, a, scores, evidence, qh)
    return dict(baseline_views=seen, both_baselines_query_parity=True, geometry=geometry,
                tables=tables, decisions=artifact(large), histories=artifact(cache),
                query_uid_order_sha256=uid_sha(a["uid"]), ref_uid_order_sha256=uid_sha(rf))


def main(phase, project, out):
    manifest = read(HERE / "PACKAGE_MANIFEST.json")
    assert manifest["experiment"] == "p4_ccnr_relative_handshake_v1_20261121"
    assert HERE == out / "package" and out == project / "runs" / manifest["run"]
    assert not sys.flags.optimize and os.environ["SLURM_JOB_ID"].isdigit() and os.environ["SLURMD_NODENAME"]
    for name, pin in manifest["files"].items():
        check(HERE / name, {"sha256": pin})
    package = sha(HERE / "PACKAGE_MANIFEST.json")
    start = time.monotonic()
    progress(out, phase, "真实计算节点核验输入 SHA、UID 顺序和冻结分母")
    result = dispatch(phase, project, out, package)
    write(out / f"{phase.upper()}.json", dict(status="PASS", phase=phase, package=package,
          job=os.environ["SLURM_JOB_ID"], node=os.environ["SLURMD_NODENAME"],
          seconds=time.monotonic()-start, max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss, **result))
    progress(out, phase, "已写通过回执")


if __name__ == "__main__":
    phase = sys.argv[1]
    project, out = map(Path, sys.argv[2:4])
    try:
        main(phase, project, out)
    except Exception as exc:
        write(out/f"FAILURE_{phase}.json", dict(error=str(exc) or repr(exc), traceback=traceback.format_exc()))
        raise
