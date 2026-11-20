"""Evaluate identical query rows after the candidate heads and cuts are sealed."""
from dataclasses import dataclass
import tempfile
import csv
import json
from pathlib import Path
import sqlite3
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
HEADS=("27","127","227","ensemble")


def environment(project):
    parent=project/"runs/p4_ton_password_frozen_v12_20261118/package"
    sys.path.insert(0,str(parent))
    from frozen_env import setup,store
    _,freeze,cfg,geometry=setup(project)
    st=store(project,freeze)
    bindings=json.loads((HERE/"REGRESSION_PINS.json").read_bytes())
    for pool, expected in bindings["metadata_sha"].items():
        st.specs[pool+":query_context_uids"]["sha256"]=expected
    return st,cfg,geometry


@dataclass
class Controls:
    project: Path
    out: Path
    store: object
    cfg: dict
    geometry: dict
    z_norm: tuple
    x_norm: tuple
    cuts: np.ndarray
    baseline_only: bool


def controls(project,out,*,baseline_only=False):
    st,cfg,geometry=environment(project)
    from vendor import constrained_onboarding_core_v3 as core
    assert Path(core.__file__).resolve().parent.name=="vendor"
    norms=[]
    for name,width in (("e3_normalizer",768),("context_normalizer",8)):
        with np.load(st.get(name),allow_pickle=False) as a:
            mean,scale=a["mean"],a["scale"]
        assert mean.shape==scale.shape==(width,) and np.isfinite(mean).all()
        assert np.isfinite(scale).all() and (scale>0).all()
        norms.append((mean,scale))
    cuts=np.asarray(cfg["method"]["cuts"] if baseline_only else candidate_seal(out)["cuts"])
    return Controls(project,out,st,cfg,geometry,*norms,cuts,baseline_only)


def candidate_seal(out):
    from auxiliary import sha
    candidate=json.loads((out/"CANDIDATE_FREEZE.json").read_bytes())
    assert candidate["method_sha256"]==sha(HERE/"EXPERIMENT.json")
    assert len(candidate["cuts"])==4 and np.isfinite(candidate["cuts"]).all() and candidate["cal_queries"]==33147
    return candidate


def head_forward(project,out,folder,baseline_only):
    """Only this fresh interpreter loads the estimator's pinned legacy modules."""
    from auxiliary import sha
    st,cfg,_=environment(project)
    from reference_assets import model_setup
    baseline=model_setup(st,cfg)
    assert "vendor" not in sys.modules
    z,q,x=[np.load(folder/(name+".npy"),mmap_mode="r",allow_pickle=False) for name in ("z","q","x")]
    ids=np.load(folder/"uid.npy",allow_pickle=False)
    assert len(set(ids))==len(ids)==len(z)==len(q)==len(x)
    old=scores(baseline,z,q,x)
    if baseline_only:
        new=old
    else:
        import torch
        candidate=candidate_seal(out)
        nets=[]
        for seed in (27,127,227):
            path=out/"formal"/f"head_{seed}.npz"
            assert candidate["head_sha256"][str(seed)]==sha(path)
            net=baseline[0].classifier(seed,790)
            with np.load(path,allow_pickle=False) as weights:
                net.load_state_dict({k:torch.from_numpy(weights[k]) for k in weights.files})
            nets.append(net.eval().requires_grad_(False))
        new=scores((baseline[0],nets,*baseline[2:]),z,q,x)
    assert old.shape==new.shape==(len(ids),4) and np.isfinite(old).all() and np.isfinite(new).all()
    np.savez(folder/"scores.npz",uid=ids,old=old,new=new)


def raw_pair(stuff,ids,z,q,x):
    from compute import run_child
    with tempfile.TemporaryDirectory(dir=stuff.out,prefix="head-input-") as temp:
        folder=Path(temp)
        for name,values in (("uid",np.asarray(ids,dtype="U64")),("z",z),("q",q),("x",x)):
            np.save(folder/(name+".npy"),values,allow_pickle=False)
        run_child([sys.executable,"-B",str(HERE/"compare.py"),str(stuff.project),str(stuff.out),
                   str(folder),"baseline" if stuff.baseline_only else "paired"],stuff.out,"head-"+folder.name)
        with np.load(folder/"scores.npz",allow_pickle=False) as a:
            assert np.array_equal(a["uid"],ids)
            return a["old"],a["new"]


def count_pairs(old,new,groups=None):
    if groups is not None:
        ids,inv=np.unique(groups,return_inverse=True)
        a=np.zeros(len(ids),bool);b=a.copy()
        np.logical_or.at(a,inv,old);np.logical_or.at(b,inv,new)
        old,new=a,b
    gain=int((~old & new).sum());loss=int((old & ~new).sum())
    return dict(total=len(old),v12=int(old.sum()),candidate=int(new.sum()),gained=gain,lost=loss,
                retained=int((old&new).sum()),neither=int((~old&~new).sum()),delta=gain-loss)


def scores(model,z,q,x):
    from reference_assets import forward
    return forward(model,z,q,x,np.arange(len(q)),lambda *args:None,"SEALED_EVALUATION")


def paired(stuff,raw,q,support):
    from vendor import p4_worker
    cfg=stuff.cfg
    cuts=stuff.cuts
    old,new=raw
    kwargs=dict(guard=True,power=4)
    old2=p4_worker.correct(old,support,q,cfg["method"]["scales"],**kwargs)
    new2=p4_worker.correct(new,support,q,cfg["method"]["scales"],**kwargs)
    return [("RAW",old>cfg["method"]["cuts"],new>cuts),("CCNR",old2>cfg["method"]["cuts"],new2>cuts)],old,old2


def by_seed(comparisons):
    for stage,old,new in comparisons:
        for j,seed in enumerate(HEADS):
            yield stage,seed,old[:,j],new[:,j]


def windows(project,stuff):
    from evaluate_ton import QUERY
    from auxiliary import sha
    pins=json.loads((HERE/"TON_PINS.json").read_bytes())
    for n in ("192.168.1.195","snapshots.sqlite","ORDERED_E3.npy"):
        assert sha(Path(pins[n]["path"]))==pins[n]["sha256"]
    host="192.168.1.195"
    db=sqlite3.connect(Path(pins["snapshots.sqlite"]["path"]).as_uri()+"?mode=ro&immutable=1",uri=True)
    z=np.load(pins["ORDERED_E3.npy"]["path"],mmap_mode="r");rows=[]
    for i,r in enumerate(db.execute(QUERY)):
        if r[3]==host and r[8]!="reference":
            rows.append((i,r[7],r[8],r[9],r[10],r[11],r[14],r[13]))
    db.close()
    ix,ids,kind,conn,off,data,q,x=zip(*rows)
    q=np.stack([np.frombuffer(b,"<f4") for b in q]);x=np.stack([np.frombuffer(b,"<f8") for b in x])
    kind=np.asarray(kind);conn=np.asarray(conn);off=np.asarray(off,bool);data=np.asarray(data,bool)
    with np.load(pins[host]["path"],allow_pickle=False) as a:
        assert np.array_equal(ix,a["index"]) and np.array_equal(ids,a["uid"].astype("U64"))
        raw=raw_pair(stuff,ids,z[list(ix)],q,x)
        all_scores,old,old2=paired(stuff,raw,q,a["support"])
        assert np.allclose(old,a["raw"],atol=2e-4,rtol=0)
        assert np.allclose(old2,a["ccnr"],atol=2e-4,rtol=0)
        assert np.array_equal(off,a["off_bypass"]) and np.array_equal(data,a["transport_data"])
        assert np.array_equal(all_scores[0][1],a["raw_alarm"]) and np.array_equal(all_scores[1][1],a["ccnr_alarm"])
    results=[]
    for name,seed,before,after in by_seed(all_scores):
        for cohort in ("attack","normal"):
            for view,m in [("all",kind==cohort),("off_bypass_payload_packets",(kind==cohort)&off&data)]:
                cnt=count_pairs(before[m],after[m],conn[m])
                if cohort=="attack" and view!="all": assert cnt["total"]==18194
                results.append(dict(source="ToN Windows 10",head=name,seed=seed,kind=cohort,view=view,unit="connection",**cnt))
            # Attack connections selected by having a labelled data frame; count all eligible frames on those connections.
            has_data=np.unique(conn[(kind==cohort)&off&data])
            take=(kind==cohort)&np.isin(conn,has_data)
            cnt=count_pairs(before[take],after[take],conn[take])
            if cohort=="attack": assert cnt["total"]==18194
            results.append(dict(source="ToN Windows 10",head=name,seed=seed,kind=cohort,view="data_connections_any_packet",
                                unit="connection",**cnt))
    return results


def regressions(project,stuff):
    from common_round1 import read_rows,uid_sha
    from original_v12_inputs import edge_features
    from evaluation import after_open
    from reference_assets import bank as accepted_bank
    from paired_replay import ref_bank,effective_history
    from reference_inputs import normalized_context
    from replay_geometry import replay
    from auxiliary import sha
    from compute import write,progress
    st,cfg=stuff.store,stuff.cfg
    rows_out=[]
    bindings=json.loads((HERE/"REGRESSION_PINS.json").read_bytes())
    for pool in ("CIC_DEV","UNSW_DEV","EDGE"):
        prefix=pool+":query_"
        rows=read_rows(st.get(prefix+"rows"));ids=[r["uid"] for r in rows]
        assert len(set(ids))==len(ids)==cfg["query_counts"][pool][0]
        assert uid_sha(ids)==bindings["query_uid_sha256"][pool]
        with np.load(st.get(prefix+"array"),allow_pickle=False) as a:
            assert np.array_equal(a["uid"].astype("U64"),ids)
            q=a["q"].copy()
            support=a["support3"].copy()
        if pool=="EDGE":
            z,x=edge_features(st,rows,ids,q)
        else:
            with np.load(st.get(prefix+"context_uids"),allow_pickle=False) as f:
                assert np.array_equal(f["uid"].astype("U64"),ids)
            z=np.load(st.get(prefix+"e3"),mmap_mode="r")[:,:768]
            x=np.load(st.get(prefix+"context"),mmap_mode="r")
            assert np.array_equal(np.load(st.get(prefix+"q"),mmap_mode="r"),q)
        assert z.shape==(len(ids),768) and q.shape==(len(ids),14) and x.shape==(len(ids),8)
        active=after_open(rows,cfg,pool)
        assert int(active.sum())==cfg["query_counts"][pool][1] and (support[~active]==0).all()
        with np.load(st.get(prefix+"scores"),allow_pickle=False) as a:
            assert np.array_equal(a["uid"].astype("U64"),ids)
            from evaluation import RAW,P4
            base_raw=a[RAW];base_ccnr=a[P4]
        raw=raw_pair(stuff,ids,z,q,x)
        old_new,old,old2=paired(stuff,raw,q,support)
        assert np.allclose(old,base_raw,rtol=0,atol=2e-4) and np.allclose(old2,base_ccnr,rtol=0,atol=2e-4),pool
        assert np.array_equal(old_new[0][1],base_raw>cfg["method"]["cuts"])
        if not np.array_equal(old_new[1][1],base_ccnr>cfg["method"]["cuts"]):
            raise ValueError(pool+" frozen CCNR control could not be reproduced")
        if stuff.baseline_only:
            reached=HERE.parent/"BASELINE_IMPORT.json"
            if not reached.exists():
                write(reached,dict(pool=pool,rows=len(ids),uid_order_sha256=uid_sha(ids),
                      isolated_head_forward=True,raw_and_ccnr_alarm_differences=0))
            progress(stuff.out,"preflight",pool+" 的原模型与参考库已分进程核验，逐查询判决一致")
        if pool!="EDGE":
            candidate_sha=json.loads((HERE/"MAIN_BANK.json").read_bytes())
            candidate_dir=project/"runs/unified_reference_bank_k8192_v1_20261113_uidfix_184105/candidate"
            if not (candidate_dir/"CANDIDATE.json").is_file():
                candidate_dir=project/"runs/unified_reference_bank_k8192_v1_20261113_early_183987/candidate"
            assert sha(candidate_dir/"CANDIDATE.json")==candidate_sha["receipt"]["sha256"]
            source=candidate_dir/(pool+"_HISTORY.jsonl.gz")
            path=candidate_dir/pool/"REFERENCES.npz"
            assert sha(source)==candidate_sha["sources"][pool]["rows"]["sha256"]
            assert sha(path)==candidate_sha["features"][pool]["feature"]["arrays"]["sha256"]
            rr,rz,rq,rx=accepted_bank(st,cfg,pool,lambda *a:None)
            dense=cfg["reference"][pool]["commission_rows"]
            hr=read_rows(source)
            with np.load(path,allow_pickle=False) as a:
                assert a["uid"].tolist()==[r["uid"] for r in hr]
                bank=ref_bank(rr[:dense]+effective_history(hr,cfg["windows"][pool]),
                              np.concatenate([rz[:dense],a["e3"]]),np.concatenate([rq[:dense],a["q14"]]),stuff.z_norm)
                rc=normalized_context(np.concatenate([rx[:dense],a["context"]]),stuff.x_norm)
            base=ref_bank(rr,rz,rq,stuff.z_norm)
            assert bank.ends==base.ends
            for key,frame in base.frame_ends.items():
                assert bank.frame_ends.setdefault(key,frame)==frame
            g=replay(dict(rows=rows,z=z,q=q,context=normalized_context(x,stuff.x_norm)),
                     bank,rc,stuff.geometry,lambda *a,**kw:None,"frozen_unified_reference")
            old_new,_,_=paired(stuff,raw,q,g["support3"])
        y=np.array([r["label"] for r in rows])
        activity=np.array([(r["source_role"] if pool=="EDGE" else r.get("activity")) or "unknown" for r in rows])
        for name,seed,a,b in by_seed(old_new):
            for label in (0,1):
                cohort="attack" if label else "normal"; sel=(y==label)&active
                if pool=="EDGE" and label==0:
                    with np.load(HERE/"normal_streams.npz",allow_pickle=False) as stream_index:
                        selected=[rows[i] for i in np.flatnonzero(sel)]
                        assert {r["source_sha256"] for r in selected}=={str(stream_index["source_sha"])}
                        streams=stream_index["stream"][[r["frame"] for r in selected]]
                    assert np.all(streams!=0) and len(streams)==20000 and len(np.unique(streams))==bindings["edge"]["represented_normal_connections"]
                    rows_out.append(dict(source=pool,head=name,seed=seed,kind=cohort,view="post_sampled_normal",
                                         unit="represented_connection",**count_pairs(a[sel],b[sel],streams)))
                for tag in [None,*sorted(set(activity[sel]))]:
                    m=sel if tag is None else sel&(activity==tag)
                    rows_out.append(dict(source=pool,head=name,seed=seed,kind=cohort,view="post_"+(str(tag) if tag is not None else "all"),
                                         unit="query",**count_pairs(a[m],b[m])))
    for expected in bindings["baseline"]:
        group=expected["group"]
        view="post_"+group if group in ("HTTP","UDP") else "post_all"
        kind="normal" if group=="NORMAL" else "attack"
        matching=[r for r in rows_out if (r["source"],r["head"],r["seed"],r["kind"],r["view"])==
                  (expected["pool"],"CCNR",expected["head"],kind,view)]
        assert len(matching)==1 and (matching[0]["total"],matching[0]["v12"])==(
            int(expected["rows"]),int(expected["alarm_count"])),expected
    return rows_out


def save(path,rows):
    with path.open("w",newline="",encoding="utf8") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n");writer.writeheader();writer.writerows(rows)


if __name__=="__main__":
    project,out,folder=map(Path,sys.argv[1:4])
    mode=sys.argv[4]
    assert mode in ("baseline","paired")
    head_forward(project,out,folder,mode=="baseline")
