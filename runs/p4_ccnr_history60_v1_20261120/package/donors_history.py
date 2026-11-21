"""Resolve the original three-space donors of withdrawn alerts, with missing-role accounting."""
from collections import Counter, defaultdict
import hashlib
from pathlib import Path

import numpy as np

from history_common import HERE, HOSTS, EDGE_PW, TON, artifact, check, read, save, sha, write, uid_sha
from inputs_history import PIN, geometry_setup, ton, edge_pw, flat, npz
from paired_history import load_metrics, severity, correct


def head_withdrawn(a,contract):
    raw=a["v12"];cut=np.asarray(contract["cuts"])
    return a["active"] & (raw[:,3]>cut[3]) & ~correct(raw,severity(a),np.asarray(contract["scales"]),.25,cut)[:,3]


def endpoint(record):
    role=int(record[6])
    ingress=bool(record[3])
    if role==1:
        return int(record[7]),int(record[8]),int(record[9]),int(record[10]),"protected_responder" if ingress else "protected_client"
    if role==2:
        return int(record[9]),int(record[10]),int(record[7]),int(record[8]),"protected_client" if ingress else "protected_responder"
    return None


def descriptor(record):
    v=endpoint(record)
    return v[-1] if v else "unknown", v[3] if v else "unknown"


def summarize(records, reference_evidence, meta, indices, matched, guard, scope):
    by_peer=Counter()
    result=Counter()
    assert len(indices)==len(matched)
    for j, (left,right), actual in zip(indices, matched, guard):
        group=scope(j)
        if not group:
            continue
        p=[record_from_arrays(records,j),reference_evidence.get(meta[left]["uid"]) if left>=0 else None,
           reference_evidence.get(meta[right]["uid"]) if right>=0 else None]
        members=all(i is not None for i in p[1:])
        qrole,qport=descriptor(p[0])
        other=[descriptor(i) if i is not None else ("missing","missing") for i in p[1:]]
        t1,t2=[endpoint(i) if i is not None else None for i in p[1:]]
        known=bool(t1 and t2)
        only=known and t1[0]==t2[0] and t1[2:4]==t2[2:4] and t1[1]!=t2[1]
        dyn=only and all(49152<=v[1]<=65535 for v in (t1,t2))
        shared=known and qport!="unknown" and t1[3]==t2[3]==qport
        qstr=dict(query_service=qport,query_role=qrole,
                  donor1_service=other[0][1],donor1_role=other[0][0],
                  donor2_service=other[1][1],donor2_role=other[1][0])
        by_peer[(group,*(str(v) for v in qstr.values()))]+=1
        result[group,"withdrawn"]+=1
        result[group,"donor_pair_bound"]+=int(members)
        result[group,"donor_roles_known"]+=int(known)
        result[group,"query_service_known"]+=int(qport!="unknown")
        result[group,"both_match_query_service"]+=int(shared)
        result[group,"only_client_port_differs"]+=int(only)
        result[group,"only_client_port_differs_both_IANA_dynamic"]+=int(dyn)
        result[group,"query_history_over_threshold"]+=int(actual)
    columns=("withdrawn","donor_pair_bound","donor_roles_known","query_service_known",
             "both_match_query_service","only_client_port_differs","only_client_port_differs_both_IANA_dynamic",
             "query_history_over_threshold")
    names=("query_service","query_role","donor1_service","donor1_role","donor2_service","donor2_role")
    a=[dict(group=g,**{k:result[g,k] for k in columns}) for g in sorted({k for k,_ in result})]
    b=[dict(group=k[0],**dict(zip(names,k[1:])),withdrawn=n) for k,n in sorted(by_peer.items())]
    return a,b


def record_from_arrays(a,j):
    return [a[k][j] for k in ("count","handshake","clock","inbound","proto","payload","role","src","sport","dst","dport")]


def normalize_points(coords):
    q=np.stack([np.frombuffer(r["q"],"<f4") for r in coords])
    x=np.stack([np.frombuffer(r["x"],"<f8") for r in coords])
    return q,x


def ton_geometry(project):
    win=PIN["ton"]["win_reference"]
    rows,a,refs,_=ton(project)
    for r in refs:
        r.update(reference_end=win["reference_end"],bank_end_frame=win["frame_end"])
    assert len(refs)==4232 and uid_sha(sorted(r["uid"] for r in refs))==PIN["ton"]["win_ref_order"]
    f=PIN["ton"]["arrays"]["ORDERED_E3.npy"]
    z=np.load(check(Path(f["path"]),f),mmap_mode="r",allow_pickle=False)
    rq,rx=normalize_points(refs)
    for r in [*rows,*refs]:
        r["owner"]=r["geometry_owner"]
    refz=z[[v["index"] for v in refs]]
    return (rows,a,z,refs,refz,rq,rx)


def edge_geometry(project,store,cfg,refs,a,select,which):
    if which=="EDGE":
        from original_v12_inputs import edge_features
        rows,_=flat("EDGE",project)
        with np.load(store.get("EDGE:query_array"),allow_pickle=False) as data:
            assert np.array_equal(data["uid"].astype("U64"),a["uid"])
            q=data["q"]
        # The accepted feature loader verifies the entire physical-context
        # UID order. Slice all three spaces only after that check.
        z,x=edge_features(store,rows,[r["uid"] for r in rows],q)
        return [rows[i] for i in select],z[select],q[select],x[select]
    rows,_,_=edge_pw(project)
    chosen=[rows[i] for i in select]
    # This is the original Edge password row schema. Endpoint role comes from the replayed header.
    own=refs[0]
    scope=PIN["edge_pw"]
    from common_ton import digest
    for r in chosen:
        r.update(owner=own["owner"],device=own["device"],partition=own["partition"],label=1,use="QUERY",
                  capture_id="edge-password-v5",
                  component_id=digest([own["owner"],[6,*sorted(((scope["source_ip"],r["sport"]),(scope["target_ip"],80)))]]))
    q,x=normalize_points(chosen)
    lookup={r["uid"]:i for i,r in enumerate(chosen)}
    z=np.empty((len(chosen),768),np.float32);seen=np.zeros(len(chosen),bool)
    for part,pin in PIN["scale"]["edge_shards"].items():
        path=project/"runs"/EDGE_PW/"edge"/f"e3_{part}.npz"
        with np.load(check(path,pin),allow_pickle=False) as data:
            ids=data["uid"].astype("U64")
            assert uid_sha(ids)==pin["uid_order"] and data["z"].shape==(pin["rows"],768)
            pairs=[(j,lookup[u]) for j,u in enumerate(ids) if u in lookup]
            if not pairs:
                continue
            src,dst=np.asarray(pairs).T
            assert len(set(dst))==len(dst) and not seen[dst].any()
            z[dst]=data["z"][src]
            seen[dst]=True
    assert seen.all()
    return chosen,z,q,x


def audit(project,out,contract,pilot=False):
    from history_common import progress
    store,cfg,geometry=geometry_setup(project)
    from reference_assets import bank as accepted_bank
    from paired_replay import ref_bank
    from reference_inputs import normalized_context
    from donor_geometry import top_two, direct
    with np.load(store.get("e3_normalizer"),allow_pickle=False) as v:
        zn=v["mean"],v["scale"]
    with np.load(store.get("context_normalizer"),allow_pickle=False) as v:
        xn=v["mean"],v["scale"]
    edge_refs,erz,erq,erx=accepted_bank(store,cfg,"EDGE",lambda *a:None)
    stats=[];service=[];missing=[];pins={};proof={}
    for which in ("TON","EDGE","EDGE_PASSWORD"):
        progress(out,"donors" if not pilot else "preflight","复算原 CCNR 实际支持组件",pool=which)
        if which=="TON":
            ton_rows,a,z,refs,rz,rq,rx=ton_geometry(project)
            choose=(a["activity"]==HOSTS[2]) & head_withdrawn(a,contract)
        else:
            _,a=flat("EDGE",project) if which=="EDGE" else edge_pw(project)[:2]
            refs,rz,rq,rx=edge_refs,erz,erq,erx
            choose=head_withdrawn(a,contract)
            if which=="EDGE":
                choose &= a["kind"]=="normal"
        idx=np.flatnonzero(choose)
        if pilot:
            if which=="TON":
                idx=np.r_[idx[a["kind"][idx]=="normal"][:4],idx[a["kind"][idx]=="attack"][:4]]
            else:
                idx=idx[:5]
        if not len(idx):
            proof[which]=dict(queries=0)
            continue
        try:
            if which=="TON":
                rows=[ton_rows[i] for i in idx]
                qq,xx=normalize_points(rows)
                zz=z[[r["index"] for r in rows]]
            else:
                rows,zz,qq,xx=edge_geometry(project,store,cfg,refs,a,idx,which)
        except FileNotFoundError as exc:
            if pilot:
                raise
            missing.append(dict(group=which,withdrawn_queries=len(idx),reason=str(exc)))
            continue
        assert all(a["uid"][i]==row["uid"] for i,row in zip(idx,rows))
        bank=ref_bank(refs,rz,rq,zn)
        x=normalized_context(xx,xn);reference_context=normalized_context(rx,xn)
        result=top_two(rows,zz,qq,x,bank,reference_context,geometry,lambda *a,**kw:None)
        delta=float(np.max(np.abs(result["weak"]-a["support"][idx]),initial=0))
        assert delta<=2e-10 and result["gate"].all() and (result["donors"]>=0).all(),(which,delta)
        proof[which]=dict(queries=len(idx),max_support_difference=delta,pairs=result["pairs"])
        if pilot:
            _,_,error=direct(rows,zz,qq,x,bank,reference_context,geometry,result)
            proof[which]["direct_max_error"]=error
            continue
        rname="TON" if which=="TON" else "EDGE"
        p=read(out/f"{rname}_REF_ENDPOINTS.json")
        ev=npz(check(out/p["file"],p))
        evidence=dict(zip(ev["uid"],ev["evidence"]))
        aa=load_metrics(out,which)
        assert np.array_equal(aa["uid"],a["uid"])
        rev=np.asarray(result["donors"])
        hit=aa["inbound"][idx]&(aa["proto"][idx]==6)&(aa["count"][idx]>read(out/"THRESHOLD.json")["threshold"])
        path=out/f"{which}_DONOR_ROWS.npz"
        np.savez(path,uid=a["uid"][idx],donor=np.asarray([r["uid"] for r in refs])[rev],distance=result["m"])
        pins[path.name]=artifact(path)
        if which=="TON":
            groups=[lambda j:"Win10."+str(a["kind"][j]),
                    lambda j:"Win10.payload.attack" if a["kind"][j]=="attack" and a["off"][j] and a["data"][j] else None]
        elif which=="EDGE":
            groups=[lambda j:"Edge.normal"]
        else:
            groups=[lambda j:"Edge.password",lambda j:"Edge.POST" if a["post"][j] else None]
        for fn in groups:
            s,t=summarize(aa,evidence,refs,idx,rev,hit,fn)
            stats.extend(s);service.extend(t)
    if pilot:
        return proof
    if stats:
        save(out/"DONORS.csv",stats)
        save(out/"DONOR_SERVICES.csv",service)
        normal=Counter()
        attack=Counter()
        for r in service:
            group=r["group"]
            bed=group.split(".",1)[0]
            scope=(bed,r["query_service"],r["query_role"])
            if group.endswith(".normal"):
                normal[scope]+=r["withdrawn"]
            else:
                attack[scope,group]+=r["withdrawn"]
        compare=[]
        for (scope,group),n in sorted(attack.items(),key=lambda x:str(x[0])):
            bed,port,role=scope
            available=port!="unknown" and role!="unknown"
            compare.append(dict(target=bed,attack_group=group,service=port,role=role,
                attack_withdrawn_queries=n,normal_withdrawn_same_service_role=normal[scope] if available else "",
                status=("same_service_same_role_observed" if normal[scope] else "no_same_service_normal_withdrawal")
                    if available else "query_role_or_service_unknown"))
        if compare:
            save(out/"DONOR_MATCHED_COMPARISON.csv",compare)
    write(out/"DONOR_DIAGNOSTIC.json",dict(proof=proof,missing=missing,large_files=pins,
           scope="withdrawn RAW-positive queries, v12 original; Win10 logical identity, Edge same device",
           donor_role_unknown="partial trace or handshake not confirmed at donor frame",
           client_port_only="equal endpoint IPs, equal server port and confirmed client role; IANA-range subset descriptive"))
    return proof
