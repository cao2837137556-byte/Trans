"""Score the two normal DAD captures using frozen source cuts on a local CPU."""

import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tarfile
import time
import traceback
import types

import numpy as np

from normal_frames import DAD, DAYS, FORMAL, HAND, HERE, HISTORY, PREP, RUNS
from normal_frames import bind_sources, load_reader, pin, read, walk_day
from frozen_score import FROZEN, adjusted, calibration, digest_order, e3_batch, inputs790, models, scores, sealed_runtime
from bank import match
from audit import save

ASSETS = RUNS.parents[2] / "data_external/login_pilot/formal_20261122_402788/frozen_quick_check_assets"
HEADS = ("27", "127", "227", "ensemble")
CHUNK = 1024


def status(out, stage, **fields):
    save(out / "RUN_STATUS.json", dict(stage=stage, time=time.time(), **fields))


def freeze(out, sources, ref_order):
    official = read(DAD / "received/RETURN.json")["files"]
    records = ("ACCEPTANCE.json", "FORMAL.json", "DAILY_METRICS.csv", "DATA_BINDING.json")
    for name in records:
        assert pin(DAD / "received" / name)["sha256"] == official[name]["sha256"]
    binding = read(DAD / "received/DATA_BINDING.json")
    assert binding["bank_order"] == read(DAD / "DAD_CARD.json")["bank_uid_order"]
    assert read(DAD / "received/ACCEPTANCE.json")["status"] == "PASS"
    source_cfg = read(FROZEN / "CONFIG.json")["method"]
    assert source_cfg["cuts"] == read(DAD / "received/FORMAL.json")["cic_witness"]["source_cuts"]
    assert source_cfg["p"] == 4 and source_cfg["lambda_value"] == .25
    h_pins = read(HAND / "PACKAGE_MANIFEST.json")["files"]
    assert pin(HISTORY / "history_stream.py")["sha256"] == h_pins["history_stream.py"]
    assert pin(HAND / "handshake_geometry.py")["sha256"] == h_pins["handshake_geometry.py"]
    heads = {}
    for seed, expected in read(DAD / "received/FORMAL.json")["cic_witness"]["models"].items():
        heads[seed] = pin(ASSETS / (seed + ".npz"))
        assert heads[seed]["sha256"] == expected["sha256"]
    contract = dict(inputs=sources, old_metrics=pin(DAD / "received/DAILY_METRICS.csv"),
                    old_binding=pin(DAD / "received/DATA_BINDING.json"), source_heads=heads,
                    source_method=source_cfg, geometry=pin(FROZEN / "GEOMETRY.json"),
                    reference_tcp_order=digest_order(ref_order), reference_count=1264, query_counts=[8448,9325],
                    code={p.name:pin(p) for p in (HERE/"replay.py", HERE/"normal_frames.py", HERE/"METHOD.md",
                        PREP/"audit.py", FORMAL/"bank.py", FORMAL/"frozen_score.py", HISTORY/"history_stream.py",
                        HAND/"handshake_geometry.py", RUNS/"p4_login_pilot_v1_20261121/feature_witness.py")})
    target = out / "INPUTS.json"
    if target.exists():
        assert read(target) == contract, "The batch belongs to another data or code freeze"
    else:
        save(target, contract)
    return contract


class FeatureCache:
    """Each completed chunk is reusable for the same frozen inputs and encoder."""
    def __init__(self, out, pins, pilot):
        self.folder = out / "features"
        self.folder.mkdir(exist_ok=True)
        self.contract = pin(out / "INPUTS.json")
        self.pins = pins
        self.out = out
        self.phase = "preflight" if pilot else "formal"
        self.values = {}
        self.rows = {}
        self.info = {}
        self.pending = []
        for stamp in sorted(self.folder.glob("*.json")):
            record = read(stamp)
            assert record["contract"] == self.contract
            file = stamp.with_suffix(".npz")
            assert pin(file) == record["array"]
            with np.load(file, allow_pickle=False) as data:
                self.merge(data["uid"], data["z"], data["q"], data["x"])

    def merge(self, uids, z, q, x):
        n = len(uids)
        assert n and z.shape == (n, 768) and q.shape == (n, 14) and x.shape == (n, 8)
        assert np.isfinite(z).all() and np.isfinite(q).all() and np.isfinite(x).all()
        assert len(set(uids)) == n and not set(uids).intersection(self.values)
        self.values.update((u, (ez, eq, ex)) for u, ez, eq, ex in zip(uids, z, q, x, strict=True))

    def add(self, row, info, snapshot):
        uid = row["uid"]
        assert uid not in self.rows
        self.rows[uid], self.info[uid] = row, info
        if uid not in self.values:
            self.pending.append(snapshot())
            if len(self.pending) >= CHUNK:
                self.flush()

    def flush(self):
        if not self.pending:
            return
        batch = self.pending
        def report(done, total):
            if done == total or done % 128 == 0:
                status(self.out, "ENCODING", phase=self.phase, encoded=len(self.values),
                       chunk_done=done, chunk_total=total)
        report(0, len(batch))
        z, encoder, steps = e3_batch(batch, self.pins, report)
        uids = np.asarray([r[0] for r in batch])
        q = np.stack([r[4] for r in batch]).astype(np.float32)
        x = np.asarray([r[5] for r in batch], dtype=np.float64)
        self.merge(uids, z, q, x)
        name = digest_order(uids)
        path = self.folder / (name + ".npz")
        tmp = path.with_suffix(".npz.tmp")
        with tmp.open("wb") as f:
            np.savez(f, uid=uids, z=z, q=q, x=x)
        tmp.replace(path)
        save(path.with_suffix(".json"), dict(contract=self.contract, rows=len(uids), encoder=encoder,
                                             physical_batches=steps, array=pin(path)))
        self.pending.clear()

    def matrix(self, order):
        v = [self.values[u] for u in order]
        info = [self.info[u] for u in order]
        return dict(uid=np.asarray(order), z=np.stack([t[0] for t in v]), q=np.stack([t[1] for t in v]),
                    physical=np.stack([t[2] for t in v]),
                    **{k:np.asarray([row[k] for row in info]) for k in ("component","frame","h","clock","day","guard","role","port")})


def original_dad_geometry():
    manifest = read(DAD / "PACKAGE_MANIFEST.json")["files"]
    with tarfile.open(DAD / ".private/package.tar.gz", "r|gz") as archive:
        for member in archive:
            if member.name == "dad_geometry.py" and member.isfile():
                source = archive.extractfile(member).read()
                break
        else:
            raise FileNotFoundError("Frozen DAD geometry")
    assert hashlib.sha256(source).hexdigest() == manifest["dad_geometry.py"]
    module = types.ModuleType("dad_normal_geometry_oracle")
    exec(compile(source, "pinned/dad_geometry.py", "exec"), module.__dict__)
    return module


def geometry_check(q, r, cache, indices, supports, cfg):
    from reference_inputs import normalized_context
    from replay_geometry import plan_queries
    from vendor.constrained_onboarding_core_v3 import ReferenceBank
    sys.path[:0] = [str(HAND), str(RUNS / "p4_ccnr_role_port_v1_20261121")]
    from handshake_geometry import replay
    original = original_dad_geometry()
    norm = calibration(cache.pins)
    rr = [cache.rows[u] for u in r["uid"]]
    qr = [cache.rows[q["uid"][i]] for i in indices]
    bank = ReferenceBank(rr, r["z"], r["q"], norm[:2], feature_uids=r["uid"], q_uids=r["uid"],
                         allow_prebank_history=True)
    geo = read(FROZEN / "GEOMETRY.json")
    rx = normalized_context(r["physical"], norm[2:])
    x = normalized_context(q["physical"][indices], norm[2:])
    z, attrs = q["z"][indices], q["q"][indices]
    quiet = lambda *args, **kwargs: None
    plans, allowed = plan_queries(bank, qr, geo)
    assert (allowed["opening"] == "").all() and (allowed["legal_component_count"] == 16).all()
    assert (allowed["legal_rows"] == 1264).all() and allowed["geometry_ready"].all()
    base = original.top_two(qr, z, attrs, x, bank, rx, geo, quiet)
    _, _, distance_error = original.direct(qr, z, attrs, x, bank, rx, geo, base)
    # Both slots use the unrestricted bank; the publication uses its first (no role filter) arm.
    roles_q = np.full((len(qr),1), -1)
    roles_r = np.full((len(rr),1), -1)
    h, _, enabled, _ = replay(qr, z, attrs, x, dict(bank=bank, rc=rx, geom=geo),
                             roles_q, roles_r, q["h"][indices], r["h"],
                             np.stack((base["weak"],base["weak"])), quiet)
    assert enabled.all() and np.array_equal(h[0],h[1])
    diff = np.max(np.abs(supports[[0,2]][:,indices] - np.stack((base["weak"],h[0]))))
    assert diff <= 2e-10, ("independent supports", diff)
    return dict(rows=len(indices), v12_distance_max_error=float(distance_error),
                v12_and_H60_support_max_error=float(diff))


def summarize(q, raw, base, h_scores, cuts, support, pilot):
    out = []
    observed = (raw > cuts, base > cuts, h_scores > cuts)
    assert np.all(observed[1] <= observed[2]) and np.all(observed[2] <= observed[0])
    with (DAD / "received/DAILY_METRICS.csv").open(encoding="utf-8-sig", newline="") as stream:
        frozen = {(row["group"],row["head"]):row for row in csv.DictReader(stream)}
    for day in ("mon", "sun", "normal"):
        take = np.ones(len(raw),bool) if day == "normal" else q["day"] == day
        for j, head in enumerate(HEADS):
            a, b, h = [v[take,j] for v in observed]
            row = dict(group=day,head=head,queries=int(take.sum()),raw_fp=int(a.sum()),
                       v12_fp=int(b.sum()),h60_fp=int(h.sum()),added_vs_v12=int((~b & h).sum()),
                       removed_vs_v12=int((b & ~h).sum()),bypassed=int(q["guard"][take].sum()),
                       v12_positive_support=int((support[0,take]>0).sum()),
                       h60_positive_support=int((support[2,take]>0).sum()))
            old = frozen[day,head]
            assert row["v12_fp"] == int(old["ccnr_FP"]) == 0
            if not pilot:
                assert (row["queries"], row["raw_fp"], row["bypassed"], row["v12_positive_support"]) == tuple(
                    int(old[k]) for k in ("N","raw_FP","bypassed","positive_support")), (day, head, row, old)
            out.append(row)
    return out


def run(out, phase):
    pilot = phase == "preflight"
    status(out,"VERIFYING",phase=phase)
    cache_path, pins, truth, ref_order = bind_sources()
    contract = freeze(out, pins, ref_order)
    if not pilot:
        pre = read(out / "PREFLIGHT.json")
        assert pre["status"] == "PASS" and pre["contract"] == pin(out/"INPUTS.json")
    with sealed_runtime() as (cfg, weights):
        import torch
        torch.set_num_threads(4)
        torch.use_deterministic_algorithms(True)
        reader = load_reader()
        values = FeatureCache(out, weights, pilot)
        source_rows = {}
        for day in DAYS:
            status(out,"READING",phase=phase,day=day,encoded=len(values.values))
            source_rows[day] = walk_day(day,reader,cache_path,pins,truth,values.add,pilot)
        values.flush()
        assert set(ref_order) == {u for u,v in values.info.items() if v["reference"]}
        query_order = [u for u,v in values.info.items() if not v["reference"]]
        assert not set(ref_order).intersection(query_order)
        if not pilot:
            assert len(query_order) == sum(contract["query_counts"])
        ref, query = values.matrix(ref_order), values.matrix(query_order)
        assert len(set(ref["component"])) == 16 and np.all(ref["clock"] <= truth["commissioning"]["cutoff_ns"])
        assert np.all(query["clock"] > truth["commissioning"]["cutoff_ns"])
        assert np.array_equal(query["guard"], (query["q"][:,0]==1)&(query["q"][:,2]==1)&(query["q"][:,5]==0))
        status(out,"SCORING",phase=phase,queries=len(query_order),references=len(ref_order))
        norm = calibration(weights)
        raw = scores(models(ASSETS), inputs790(query["z"], query["q"], query["physical"], norm))
        support, legal, compatible = match(query, ref, cfg, norm)
        assert (legal[0] == 16).all() and (legal[2] == 16).all()
        base = adjusted(raw, support[0], query["guard"], cfg["method"])
        h_scores = adjusted(raw, support[2], query["guard"], cfg["method"])
        ix = np.arange(len(query_order)) if pilot else np.unique(np.r_[
            np.linspace(0,len(query_order)-1,32,dtype=int), np.flatnonzero(query["guard"])])
        check = geometry_check(query, ref, values, ix, support, cfg)
        cuts = np.asarray(cfg["method"]["cuts"])
        rows = summarize(query,raw,base,h_scores,cuts,support,pilot)
    stem = "PREFLIGHT" if pilot else "NORMAL"
    table = out / (stem + "_METRICS.csv")
    with table.open("w",encoding="utf8",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    array = out / (stem + "_DECISIONS.npz")
    np.savez_compressed(array, uid=query["uid"], day=query["day"], frame=query["frame"], guard=query["guard"],
                        h=query["h"], raw=raw,v12=base,h60=h_scores,cuts=cuts,
                        v12_support=support[0],h60_support=support[2],h60_components=compatible[2])
    accepted = dict(status="PASS", phase=phase, contract=pin(out/"INPUTS.json"), reference_rows=len(ref_order),
                    references_order=digest_order(ref_order), evaluated_queries=len(query_order),
                    evaluated_order=digest_order(query_order), frames=source_rows, independent_check=check,
                    ensemble=[r for r in rows if r["head"]=="ensemble"], table=pin(table),decisions=pin(array))
    if pilot:
        assert all(x["raw_fp"]>0 and x["v12_fp"]==0 for x in accepted["ensemble"])
        save(out/"PREFLIGHT.json",accepted)
        status(out,"PREFLIGHT_PASS",queries=len(query_order))
    else:
        accepted["preflight"]=pin(out/"PREFLIGHT.json")
        save(out/"ACCEPTANCE.json",accepted)
        names = ["INPUTS.json","PREFLIGHT.json","PREFLIGHT_METRICS.csv","PREFLIGHT_DECISIONS.npz",
                 "NORMAL_METRICS.csv","NORMAL_DECISIONS.npz","ACCEPTANCE.json"]
        names += sorted(p.relative_to(out).as_posix() for p in values.folder.iterdir() if p.suffix in (".json",".npz"))
        manifest = {name:pin(out/name)["sha256"] for name in names}
        (out/"SHA256SUMS").write_bytes("".join(f"{sha}  {name}\n" for name,sha in manifest.items()).encode("ascii"))
        assert all(pin(out/name)["sha256"]==sha for name,sha in manifest.items())
        status(out,"ACCEPTED",receipt=pin(out/"ACCEPTANCE.json"),manifest=pin(out/"SHA256SUMS"))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("preflight","formal"))
    parser.add_argument("out",type=Path)
    args=parser.parse_args()
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    assert shutil.disk_usage(out).free>2*2**30
    import msvcrt
    with (out/".lock").open("a+b") as lock:
        lock.seek(0)
        msvcrt.locking(lock.fileno(),msvcrt.LK_NBLCK,1)
        try:
            run(out,args.phase)
        except Exception as error:
            save(out/f"FAILURE_{time.time_ns()}.json",dict(phase=args.phase,error=repr(error),trace=traceback.format_exc()))
            status(out,"STOP",phase=args.phase,error=repr(error))
            raise
