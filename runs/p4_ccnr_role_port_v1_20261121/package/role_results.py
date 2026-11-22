"""Produce paired counts, independent mechanism attribution, and the Edge service audit."""
from collections import Counter
from pathlib import Path
import csv

import numpy as np

from history_common import HEADS, artifact, check, save, read, write
from role_inputs import CACHE, HISTORY, npz, role_receipt
from roles import NAMES, RESPONDER, CLIENT, UNKNOWN
from paired_history import unit_views, verify_base
from screen_geometry import ARMS


def group_count(flags,out,rs,group,unit,category):
    for h,seed in enumerate(HEADS):
        raw=int(flags["RAW"][:,h].sum());base=int(flags["v12"][:,h].sum())
        for arm in ARMS:
            accepted=int(flags[arm][:,h].sum())
            assert base<=accepted<=raw<=len(flags[arm])
            assert np.all(flags["v12"][:,h]<=flags[arm][:,h])
            out.append(dict(seed=seed,group=group,kind=category,unit=unit,arm=arm,total=len(flags[arm]),
                raw=raw,original=base,alert=accepted,added=accepted-base,
                lost=int((flags["v12"][:,h] & ~flags[arm][:,h]).sum()),
                retention_vs_raw=(accepted/raw if raw else ""),
                detection_or_fpr=(accepted/len(flags[arm]) if len(flags[arm]) else "")))
        for u in ("U1","U2"):
            cov=flags[f"COVER_R2_{u}"][:,h]
            r2=flags[f"R2_{u}"][:,h]
            b=flags["v12"][:,h]
            nogate=int((cov & ~b).sum())
            recalc=int((r2 & ~cov).sum())
            all_add=int((r2 & ~b).sum())
            assert nogate+recalc==all_add
            rs.append(dict(seed=seed,group=group,kind=category,unit=unit,membership=u,total=len(b),
                           raw=raw,original=base,coverage=nogate,rematch=recalc,total_added=all_add))


def role_coverage(pool,qroles,rroles,a,refs):
    def counts(group,roster,v):
        c=Counter(v[:,0].tolist())
        n=int(len(v));udp=c[3]
        tcp=n-udp
        return dict(pool=pool,group=group,roster=roster,total=n,tcp=tcp,udp=udp,service=c[1],client=c[2],
                    unknown=c[0],service_pct_tcp=(100*c[1]/tcp if tcp else ""),
                    client_pct_tcp=(100*c[2]/tcp if tcp else ""),
                    unknown_pct_tcp=(100*c[0]/tcp if tcp else ""))
    result=[counts(pool,"reference",rroles),counts(pool,"query_all",qroles),
            counts(pool,"query_evaluation",qroles[a["active"]])]
    if pool=="TON":
        h=np.array([r["device"] for r in refs])
        for host in sorted(set(a["activity"])):
            result.extend((counts(host,"reference",rroles[h==host]),
                           counts(host,"query_evaluation",qroles[a["activity"]==host])))
    if pool=="EDGE":
        result.append(counts("Edge normal","query_evaluation",qroles[(a["kind"]=="normal") & a["active"]]))
    return result


def per_service(a,roles,scores):
    take=np.flatnonzero((a["kind"]=="normal")&a["active"])
    groups={}
    for j in take:
        r,p=roles[j,:2]
        groups.setdefault((int(r),int(p)),[]).append(j)
    out=[];attrib=[]
    for (role,port),idx in sorted(groups.items()):
        arms={n:scores[n][idx] for n in ARMS}
        name=NAMES[role]+"/"+(str(port) if port>=0 else "not_applicable")
        group_count(arms,out,attrib,name,"query","normal")
    assert sum(x["total"] for x in out if x["seed"]=="ensemble" and x["arm"]=="R2_U1")==20000
    return out,attrib


def historic_endpoint(old,j):
    who=int(old["role"][j]);inbound=bool(old["inbound"][j])
    if who not in (1,2):
        return "",-1
    role="server" if (who==1)==inbound else "client"
    return role,int(old["dport"][j] if who==1 else old["sport"][j])


def edge_focal_indices(project,a):
    base=project/"runs"/HISTORY
    pin=CACHE["old_donors"]
    bridge=npz(check(base/pin["file"],pin))
    meta=read(base/"EDGE_REF_ENDPOINTS.json")
    r=npz(check(base/meta["file"],meta))
    index={u:i for i,u in enumerate(a["uid"])}
    rd={u:x for u,x in zip(r["uid"],r["evidence"])}
    assert len(index)==60000 and len(rd)==len(r["uid"])==4124 and bridge["donor"].shape==(16699,2)
    # Bind the cohort to the accepted history run, with the old full-handshake
    # role view used only to reproduce the reported 73 and 1 set memberships.
    focus={502:[],443:[]}
    for u,(i1,i2) in zip(bridge["uid"],bridge["donor"]):
        j=index[u]
        assert a["kind"][j]=="normal" and a["active"][j]
        role,service=historic_endpoint(a,j)
        if not ((role,service) in (("server",502),("client",443))):
            continue
        # old endpoint has columns from the original accepted scan.
        left,right=[rd[i] for i in (i1,i2)]
        def old_server1883(row):
            who=int(row[6]);inbound=bool(row[3])
            return (who in (1,2) and (who==1)==inbound and int(row[10] if who==1 else row[8])==1883)
        if all(old_server1883(row) for row in (left,right)):
            focus[service].append(j)
    assert {k:len(v) for k,v in focus.items()}=={502:73,443:1}, {k:len(v) for k,v in focus.items()}
    return focus


def edge_focus(project,a,qroles,rroles,refs,scores,masks):
    focus=edge_focal_indices(project,a)
    rc=np.asarray([r["component_id"] for r in refs])
    rq=np.array([r["protocol"] for r in refs])
    out=[]
    for service,idx in focus.items():
        assert scores["RAW"][idx,3].all() and not scores["v12"][idx,3].any()
        for u, (s,counts) in masks.items():
            c=counts[idx]
            out.append(dict(historical_service=service,unit="query",head="ensemble",unknown_policy=u,total=len(idx),
                v12_raw=len(idx),v12_ccnr=0,
                ref_TCP_server_same_port_rows=int(((rq==6)&(rroles[:,0]==RESPONDER)&(rroles[:,1]==service)).sum()),
                ref_TCP_server_same_port_components=len(set(rc[(rq==6)&(rroles[:,0]==RESPONDER)&(rroles[:,1]==service)])),
                ref_TCP_client_remote_same_port_components=len(set(rc[(rq==6)&(rroles[:,0]==CLIENT)&(rroles[:,1]==service)])),
                queries_new_server_role=int((qroles[idx,0]==RESPONDER).sum()),
                queries_new_client_role=int((qroles[idx,0]==CLIENT).sum()),
                queries_new_unknown_role=int((qroles[idx,0]==UNKNOWN).sum()),
                legal_r2_components_min=int(min(c)),legal_r2_components_max=int(max(c)),
                replacement_two_compatible=int((s[1,idx]>0).sum()),
                queries_without_two_legal=int((c<2).sum()),added_coverage=int(scores[f"COVER_R2_{u}"][idx,3].sum()),
                added_rematch=int((scores[f"R2_{u}"][idx,3] & ~scores[f"COVER_R2_{u}"][idx,3]).sum()),
                new_fp_total=int(scores[f"R2_{u}"][idx,3].sum()),
                R1_fp=int(scores[f"R1_{u}"][idx,3].sum()),R3_fp=int(scores[f"R3_{u}"][idx,3].sum())))
    return out


def handshakes(a,pool):
    out=[]
    for name,u in unit_views(pool,a).items():
        if u.view.kind=="attack_flood":
            continue
        if u.view.unit=="query":
            cell=a["handshake"][u.take]
        else:
            cell=u.maximum(a["handshake"])
        assert len(cell)==u.n
        if not len(cell):
            continue
        p=np.percentile(cell,[50,90,99,99.9,100])
        out.append(dict(group=name,kind=u.view.kind,unit=u.view.unit,
             aggregation="maximum_of_view_queries" if u.view.unit=="connection" else "one_value_per_query",total=len(cell),
             P50=p[0],P90=p[1],P99=p[2],P999=p[3],Max=p[4]))
    return out


def summarize_pool(project,out,pool,data,qroles,rroles,scores,masks):
    a=data["a"]
    rows=[];attrib=[]
    for name,u in unit_views(pool,a).items():
        x={arm:u.any(values) for arm,values in scores.items()}
        group_count(x,rows,attrib,name,u.view.unit,u.view.kind)
    path=out/(pool+"_PAIRED.csv");save(path,rows)
    pp=out/(pool+"_MECHANISM.csv");save(pp,attrib)
    pins={path.name:artifact(path),pp.name:artifact(pp)}
    if "handshake" in a:
        h=out/(pool+"_HANDSHAKE.csv");save(h,handshakes(a,pool));pins[h.name]=artifact(h)
    if pool=="EDGE":
        ss,aa=per_service(a,qroles,scores)
        for name,data_ in (("EDGE_NORMAL_BY_SERVICE.csv",ss),("EDGE_NORMAL_MECHANISM_BY_SERVICE.csv",aa),
                           ("EDGE_502_443.csv",edge_focus(project,a,qroles,rroles,data["refs"],scores,masks))):
            f=out/name;save(f,data_);pins[name]=artifact(f)
    return pins
