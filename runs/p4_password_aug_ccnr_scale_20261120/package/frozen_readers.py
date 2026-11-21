import json, os, sqlite3
from pathlib import Path
import numpy as np
from compare import by_seed, count_pairs, paired
from collect_inputs import capture,capture_pool,raw_pair
HERE=Path(os.environ["ACCEPTED_R1"])/"package"
from edge_evaluation import SOURCE,TARGET,OWNER
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
            rows.append((i,r[7],r[8],r[9],r[10],r[11],r[14],r[13],r[1]))
    db.close()
    ix,ids,kind,conn,off,data,q,x,frames=zip(*rows)
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
        zeros=np.zeros(len(ids),bool)
        capture("WINDOWS",ids,raw,a["support"],q,frames,kind,~zeros,conn,off,data,zeros,kind)
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
        capture_pool(pool,rows,raw,g["support3"] if pool!="EDGE" else support,q,active,HERE)
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

def assess(project,out):
    from compare import controls, paired, by_seed, count_pairs, save
    stuff=controls(project,out)
    from reference_assets import bank as accepted_bank
    from reference_inputs import normalized_context
    from paired_replay import ref_bank
    from replay_geometry import replay
    folder=out/"edge";s,cfg,geometry=stuff.store,stuff.cfg,stuff.geometry
    ref,zr,qr,xr=accepted_bank(s,cfg,"EDGE",lambda *args:None)
    assert len(ref)==4124 and sum(r["protocol"]==6 for r in ref)==4096 and len({r["device"] for r in ref})==1
    owner=ref[0]
    assert owner["owner"]==OWNER
    bank=ref_bank(ref,zr,qr,stuff.z_norm)
    db=sqlite3.connect((folder/"queries.sqlite").resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    metadata=list(db.execute("SELECT uid,frame,stream,ns,post,q,x,sport FROM metadata ORDER BY frame"))
    db.close()
    ids,frames,stream,ns,posts,q,x,sports=zip(*metadata)
    q=np.stack([np.frombuffer(t,"<f4") for t in q]);x=np.stack([np.frombuffer(t,"<f8") for t in x])
    pin=json.loads((HERE/"EDGE_ASSET.json").read_bytes())
    from common_ton import digest
    rows=[dict(uid=u,partition=owner["partition"],device=owner["device"],protocol=6,frame=f,timestamp=t/1_000_000_000,
               component_id=digest([owner["owner"],[6,*sorted(((SOURCE,sp),(TARGET,80)))]]),
               owner=owner["owner"],source_sha256=pin["pcap_sha256"],capture_id="edge-password-v5",label=1,use="QUERY")
          for u,f,t,sp in zip(ids,frames,ns,sports)]
    lookup={u:i for i,u in enumerate(ids)}
    z=np.empty((len(ids),768),np.float32);seen=np.zeros(len(ids),bool)
    for shard in range(8):
        with np.load(folder/f"e3_{shard}.npz",allow_pickle=False) as a:
            ix=[lookup[u] for u in a["uid"].astype("U64")]
            assert len(set(ix))==len(ix) and not seen[ix].any()
            seen[ix]=True;z[ix]=a["z"]
    assert seen.all()
    g=replay(dict(rows=rows,z=z,q=q,context=normalized_context(x,stuff.x_norm)),bank,
             normalized_context(xr,stuff.x_norm),geometry,lambda *a,**kw:None,"Edge Password")
    assert (g["legal_component_count"]>=2).all()
    raw=raw_pair(stuff,ids,z,q,x)
    comparisons,_,_=paired(stuff,raw,q,g["support3"])
    off=~((q[:,0]==1)&(q[:,2]==1)&(q[:,5]==0))
    capture("EDGE_PASSWORD",ids,raw,g["support3"],q,frames,np.repeat("attack",len(ids)),
            np.ones(len(ids),bool),stream,off,np.asarray(posts,bool),np.asarray(posts,bool),np.repeat("password",len(ids)))
    results=[]
    for name,seed,a,b in by_seed(comparisons):
        for view,ix in [("any_eligible_inbound",np.ones(len(ids),bool)),("confirmed_login_POST",np.asarray(posts,bool))]:
            cnt=count_pairs(a[ix],b[ix],np.asarray(stream)[ix])
            results.append(dict(source="Edge Password",head=name,seed=seed,kind="attack",view=view,unit="connection",
                                confirmed_connections=23650,without_eligible_query=23650-cnt["total"],**cnt))
    return results
