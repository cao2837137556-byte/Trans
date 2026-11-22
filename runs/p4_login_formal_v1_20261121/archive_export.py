"""Export a bounded replay fixture and the three pinned, already fitted heads."""
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import traceback

import numpy as np

HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_bytes())


def write(path, obj):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf8")
    tmp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for data in iter(lambda: stream.read(4 << 20), b""):
            h.update(data)
    return h.hexdigest()


def verify(path, pin):
    assert path.is_file() and (not pin.get("bytes") or path.stat().st_size == pin["bytes"])
    assert sha(path) == pin["sha256"], path.name
    return path


def order(values):
    return hashlib.sha256("".join(str(x)+"\n" for x in values).encode("ascii")).hexdigest()


def asset(path):
    return dict(file=path.name, sha256=sha(path), bytes=path.stat().st_size)


def export(root, out, pins):
    for i, pin in pins["heads"].items():
        src = verify(root/pin["paths"][0],pin)
        assert 0 < src.stat().st_size < 2*2**20
        shutil.copyfile(src, out/f"head_{i}.npz")
    backbone = root/"runs"/pins["history_run"]
    attacked = pins["history"]
    with np.load(verify(backbone/attacked["file"],attacked),allow_pickle=False) as a:
        data = {k:a[k] for k in ("uid","v12","support","guard","kind","active","post","frame","handshake")}
    assert len(data["uid"]) == attacked["rows"] and order(data["uid"]) == attacked["uid_order"]
    archived = root/"runs"/pins["decision_run"]
    archived_pin = pins["decision"]
    with np.load(verify(archived/archived_pin["file"],archived_pin),allow_pickle=False) as a:
        assert np.array_equal(a["uid"],data["uid"])
        raw, original = a["RAW"], a["v12"]
    assert raw.shape == original.shape == data["v12"].shape
    score = pins["method"]
    assert np.array_equal(data["v12"]>score["cuts"],raw)
    g = np.where(data["guard"],0.,1.-np.power(1.-data["support"],4))
    corrected = data["v12"][:,:3]-(.25*np.array(score["scales"]))[None,:]*g[:,None]
    assert np.array_equal(np.column_stack((corrected,corrected.mean(1)))>score["cuts"],original)
    scope = (data["kind"]=="attack") & data["active"]
    post = scope & data["post"] & ~data["guard"]
    stratification = (("withdrawn_post", post & raw[:,3] & ~original[:,3], 12),
                      ("kept_post", post & original[:,3], 12),
                      ("missed_post", post & ~raw[:,3], 8),
                      ("syn_bypass", scope & data["guard"] & raw[:,3], 8))
    strata = {str(data["uid"][j]): name for name,mask,top in stratification for j in np.flatnonzero(mask)[:top]}
    take = np.flatnonzero(np.isin(data["uid"],list(strata)))
    ids = data["uid"][take]
    assert 24 <= len(ids) <= 40 and len(ids)==len(strata)
    indices = {str(u):i for i,u in enumerate(ids)}

    folder = root/"runs"/pins["edge_source_run"]
    edge = pins["edge_inputs"]
    source = read(verify(folder/edge["file"],edge))
    assert source["input_sha"] == pins["edge_raw_sha256"]
    db = verify(folder/"edge/queries.sqlite",dict(sha256=source["database_sha"]))
    with sqlite3.connect(db.resolve().as_uri()+"?mode=ro&immutable=1",uri=True) as sql:
        rows = [sql.execute("SELECT uid,frame,q,x FROM metadata WHERE uid=?", (str(u),)).fetchone() for u in ids]
    assert all(row is not None for row in rows)
    assert np.array_equal([x[0] for x in rows],ids) and np.array_equal([x[1] for x in rows],data["frame"][take])
    q = np.stack([np.frombuffer(x[2],"<f4") for x in rows])
    physical = np.stack([np.frombuffer(x[3],"<f8") for x in rows])
    assert q.shape == (len(ids),14) and physical.shape == (len(ids),8)
    z = np.empty((len(ids),768),np.float32)
    found = set()
    for shard,pin in pins["edge_shards"].items():
        with np.load(verify(folder/f"edge/e3_{shard}.npz",pin),allow_pickle=False) as f:
            u = f["uid"].astype("U64")
            assert len(u)==pin["rows"] and order(u)==pin["uid_order"]
            matches=[(p,indices[str(s)]) for p,s in enumerate(u) if str(s) in indices]
            if matches:
                loc,ix=np.asarray(matches).T
                assert not (set(ix)&found)
                z[ix]=f["z"][loc]
                found.update(ix)
    assert len(found)==len(ids) and np.isfinite(z).all()
    np.savez(out/"ATTACK_FIXTURE.npz", uid=ids, stratum=[strata[str(u)] for u in ids],
             expected_raw=raw[take], expected_v12=original[take], scores=data["v12"][take],
             support=data["support"][take], guard=data["guard"][take], post=data["post"][take],
             frame=data["frame"][take], handshake=data["handshake"][take], label=np.ones(len(ids),np.int8),
             z=z, q=q, physical=physical)
    return dict(status="PASS", scope="SEALED_EDGE_PASSWORD_READBACK", rows=len(ids),
                uid_order_sha256=order(ids), source_sha256=source["input_sha"], database_sha256=source["database_sha"],
                history_sha256=attacked["sha256"], original_decisions_sha256=archived_pin["sha256"],
                original_decision_rule="seed scores and the same frozen penalty/aggregation; strict score > threshold",
                selected={name:sum(v==name for v in strata.values()) for name,_,_ in stratification})


def main(project,out):
    try:
        write(out/"CHAIN_STATE.json", dict(stage="EXPORTING"))
        receipt = export(project,out,read(HERE/"ARCHIVE_PINS.json"))
        write(out/"ACCEPTANCE.json",receipt)
        names=["INSTALL.json","ACCEPTANCE.json","ATTACK_FIXTURE.npz"]+[f"head_{i}.npz" for i in (27,127,227)]
        write(out/"RETURN.json", dict(files={n:asset(out/n) for n in names}))
        write(out/"CHAIN_STATE.json", dict(stage="COMPLETE"))
    except Exception as exc:
        write(out/"FAILURE.json",dict(error=str(exc) or repr(exc), trace=traceback.format_exc()))
        write(out/"RETURN.json",dict(files={"FAILURE.json":asset(out/"FAILURE.json")}))
        write(out/"CHAIN_STATE.json",dict(stage="STOP",error=str(exc) or repr(exc)))
        raise


if __name__=="__main__":
    main(*map(Path,sys.argv[1:]))
