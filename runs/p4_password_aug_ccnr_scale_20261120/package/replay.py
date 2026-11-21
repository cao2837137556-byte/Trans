"""Compare all rules on the same packet IDs, connection sets and original withheld cohorts."""
from pathlib import Path
import numpy as np
from shared import MODELS,HEADS,ARMS,read,write,save,table,check,uid_sha,artifact,sha


def decisions(raw,s,guard,baseline,source):
    cuts=np.asarray(source["cuts"],float)
    span=np.asarray(source["span"],float)
    weight=np.where(guard,0.,.25*(1.-np.power(1.-s,4)))
    z=(raw[:,:3]-cuts[:3])/span
    std_raw=np.column_stack((z,z.mean(axis=1)))
    std_cuts=np.r_[np.zeros(3),source["standard_cut"]]
    results={}
    for arm,scale in ((ARMS[0],baseline),(ARMS[1],span)):
        adj=raw[:,:3]-weight[:,None]*scale
        final=np.column_stack((adj,adj.mean(axis=1)))
        results[arm]=(raw-cuts,final-cuts)
    std_final=z-weight[:,None]
    results[ARMS[2]]=(std_raw-std_cuts,np.column_stack((std_final,std_final.mean(axis=1)))-std_cuts)
    for index in (0,1):
        a,b=results[ARMS[1]][index],results[ARMS[2]][index]
        np.testing.assert_array_equal(a[:,:3]>0,b[:,:3]>0)
    for a,b in results.values():
        assert np.all((b<=0)|(a>0)) and np.array_equal(a[weight==0],b[weight==0])
    delta=span.mean()-np.mean(baseline)
    old=results[ARMS[0]][1][:,3]>0;own=results[ARMS[1]][1][:,3]>0
    assert not ((own & ~old) if delta>=0 else (old & ~own)).any()
    return results


def groups_for(pool,a):
    active=a["active"]
    for kind in ("attack","normal"):
        sel=(a["kind"]==kind)&active
        if not sel.any():continue
        if pool=="WINDOWS":
            connected=np.unique(a["group"][sel&a["off"]&a["data"]])
            for view,mask in (("all",sel),("off_bypass_payload_packets",sel&a["off"]&a["data"]),
                              ("data_connections_any_packet",sel&np.isin(a["group"],connected))):
                yield kind,view,mask,"connection"
        elif pool=="EDGE_PASSWORD":
            yield kind,"any_eligible_inbound",sel,"connection"
            yield kind,"confirmed_login_POST",sel&a["post"],"connection"
        else:
            yield kind,"post_all",sel,"query"
            for name in np.unique(a["activity"][sel]):
                yield kind,"post_"+str(name),sel&(a["activity"]==name),"query"
            if pool=="EDGE" and kind=="normal":
                yield kind,"post_sampled_normal",sel,"represented_connection"


def unit_alarms(packet,mask,inverse,count):
    sub=packet[mask]>0
    if inverse is None:return sub
    out=np.zeros((count,4),bool)
    np.logical_or.at(out,inverse,sub)
    return out


def n(mask):
    return int(np.count_nonzero(mask))


def changes(before,after):
    return dict(total=len(before),before=n(before),after=n(after),gained=n(~before&after),lost=n(before&~after),
                retained=n(before&after),neither=n(~before&~after))


def verify_original_caches(out,parent):
    expected={}
    for file in ("WINDOWS_CONNECTIONS.csv","FLOOD_NORMAL.csv","EDGE_PASSWORD.csv"):
        for r in table(parent/file):
            key=tuple(r[k] for k in ("source","kind","view","unit","head","seed"))
            assert key not in expected
            expected[key]=[int(r[k]) for k in ("total","v12","candidate","gained","lost","retained","neither")]
    spec=read(out/"SOURCE.json");seen=set()
    for pool in ("WINDOWS","CIC_DEV","UNSW_DEV","EDGE","EDGE_PASSWORD"):
        tag={"WINDOWS":"ToN Windows 10","EDGE_PASSWORD":"Edge Password"}.get(pool,pool)
        reg=read(out/(pool+"_INDEX.json"))
        with np.load(check(out/(pool+".npz"),reg["cache"]),allow_pickle=False) as z:
            a={k:z[k] for k in z.files}
        assert uid_sha(a["uid"])==reg["uid_order"]
        baseline=np.asarray(spec["baseline"])
        w=np.where(a["guard"],0.,.25*(1-np.power(1-a["support"],4)))
        old={}
        for model in MODELS:
            raw=a[model]
            corrected=raw[:,:3]-w[:,None]*baseline
            old[model]=(raw-spec["models"][model]["cuts"],np.column_stack((corrected,corrected.mean(axis=1)))-spec["models"][model]["cuts"])
        for kind,view,mask,unit in groups_for(pool,a):
            if unit=="query":
                inv=None;count=n(mask)
            else:
                grp,inv=np.unique(a["group"][mask],return_inverse=True);count=len(grp)
            for j,stage in enumerate(("RAW","CCNR")):
                v,r=[unit_alarms(old[m][j],mask,inv,count) for m in MODELS]
                for k,head in enumerate(HEADS):
                    key=(tag,kind,view,unit,stage,head)
                    pair=changes(v[:,k],r[:,k])
                    actual=[pair[f] for f in ("total","before","after","gained","lost","retained","neither")]
                    assert key not in seen and actual==expected[key],(key,actual)
                    seen.add(key)
    assert seen==set(expected) and len(seen)==192
    return len(seen)


def margins(out,a,mask,ids,inv,fixed,distrib,summary):
    # Reference packets for the fixed cohort are precisely the original r1 ensemble RAW alarm packets.
    chosen=np.flatnonzero(mask)
    base_raw=distrib["r1"]["original"][0][:,3]
    eligible=fixed[inv]&(base_raw[chosen]>0)
    packets=chosen[eligible];ix=inv[eligible]
    assert len(np.unique(ix))==15849
    artifacts={}
    for model in MODELS:
        for arm in ARMS:
            raw,final=distrib[model][arm]
            for k,head in enumerate(HEADS):
                # lexsort groups by connection, then descending corrected margin, then first original frame.
                order=np.lexsort((a["frame"][packets],-final[packets,k],ix))
                new=np.r_[True,ix[order][1:]!=ix[order][:-1]]
                pick=packets[order[new]]
                assert len(pick)==15849
                measures=dict(max_corrected_margin=final[pick,k],same_packet_raw_margin=raw[pick,k],
                              same_packet_support=a["support"][pick],actual_deduction=raw[pick,k]-final[pick,k])
                for key,v in measures.items():
                    lo,med,hi=np.percentile(v,[25,50,75])
                    summary.append(dict(model=model,arm=arm,seed=head,measure=key,connections=len(pick),
                                        p25=float(lo),median=float(med),p75=float(hi)))
                path=out/f"win_margin_{model}_{arm}_{head}.npz"
                np.savez(path,connection=ids[ix[order[new]]],uid=a["uid"][pick],frame=a["frame"][pick],**measures)
                artifacts[path.name]=artifact(path)
    return artifacts


def evaluate(out):
    source=read(out/"SOURCE.json")
    orig=np.array(source["baseline"])
    witness=read(out/"REPRODUCTION.json")
    assert sha(out/"SOURCE.json")==witness["source_sha"]
    metrics=[];focus=[];attribution=[];quantiles=[];large={}
    for pool,reg in witness["caches"].items():
        path=check(out/reg["cache"]["file"],reg["cache"])
        with np.load(path,allow_pickle=False) as z:
            a={k:z[k] for k in z.files}
        assert uid_sha(a["uid"])==reg["uid_order"]
        dist={m:decisions(a[m],a["support"],a["guard"],orig,source["models"][m]) for m in MODELS}
        for kind,view,mask,unit in groups_for(pool,a):
            if unit=="query":
                ids=a["uid"][mask];inv=None
            else:
                ids,inv=np.unique(a["group"][mask],return_inverse=True)
            alarms={(m,arm,stage):unit_alarms(v[j],mask,inv,len(ids)) for m in MODELS
                    for arm,v in dist[m].items() for j,stage in enumerate(("RAW","CCNR"))}
            rraw=alarms["r1","original","RAW"][:,3]
            rfinal=alarms["r1","original","CCNR"][:,3]
            vfinal=alarms["v12","original","CCNR"][:,3]
            win=pool=="WINDOWS" and kind=="attack" and view=="data_connections_any_packet"
            benign=pool in ("EDGE","UNSW_DEV") and kind=="normal" and view in ("post_all","post_sampled_normal")
            edge=pool=="EDGE_PASSWORD"
            if win:
                fixed=rraw&~rfinal
                assert len(ids)==18194 and n(fixed)==15849
                large.update(margins(out,a,mask,ids,inv,fixed,dist,quantiles))
            if benign:
                fixed=rfinal&~vfinal
                assert n(fixed)==(214 if pool=="EDGE" else 1336)
                if unit=="query":
                    qidx=np.flatnonzero(mask)[fixed]
                    r0=dist["r1"]["original"][0][qidx,3]
                    r2=dist["r1"]["original"][1][qidx,3]
                    v0=dist["v12"]["original"][0][qidx,3]
                    assert (r0>0).all() and (r2>0).all()
                    no=a["guard"][qidx]|(a["support"][qidx]==0)
                    cls=np.where(no,0,np.where(r0>.25*orig.mean(),1,2))
                    assert len(qidx)==n(fixed)
                    for was in (False,True):
                        for i,label in enumerate(("bypass_or_zero_support","margin_over_cap","deduction_below_margin")):
                            attribution.append(dict(pool=pool,unit=unit,denominator=len(qidx),
                                raw_origin="both_alert" if was else "new_r1_raw_alert",reason=label,
                                count=n(((v0>0)==was)&(cls==i))))
            for (m,arm,stage),matrix in alarms.items():
                before=alarms[m,"original",stage]
                for k,head in enumerate(HEADS):
                    alert=matrix[:,k]
                    tags=dict(pool=pool,kind=kind,view=view,unit=unit,model=m,arm=arm,stage=stage,seed=head)
                    metrics.append(dict(**tags,**changes(before[:,k],alert)))
                    if win or benign or edge:
                        cohort=fixed if (win or benign) else rfinal
                        focus.append(dict(**tags,total=len(ids),alerts=n(alert),fixed_cohort=n(cohort),
                            cohort_alerted=n(alert&cohort),cohort_silent=n(~alert&cohort),
                            added_vs_r1_original_final=n(alert&~rfinal),removed_vs_r1_original_final=n(~alert&rfinal),
                            added_vs_both_original_finals=n(alert&~rfinal&~vfinal)))
    save(out/"METRICS.csv",metrics);save(out/"FOCUS.csv",focus);save(out/"NORMAL_ATTRIBUTION.csv",attribution)
    save(out/"WINDOWS_MARGIN_QUANTILES.csv",quantiles)
    write(out/"HPC_MARGIN_SHA.json",large)
    rows=[]
    for m,entry in source["models"].items():
        for j,seed in enumerate(HEADS[:3]):
            lo,med,hi=entry["quantiles"][j]
            rows.append(dict(model=m,seed=seed,q10=lo,median=med,q90=hi,span=entry["span"][j],
                 original_scale=orig[j],seed_cut=entry["cuts"][j],original_ensemble_cut=entry["cuts"][3],
                 standardized_ensemble_cut=entry["standard_cut"],standardized_cal_fpr=entry["standard_cal_fpr"]))
    save(out/"SCALES.csv",rows)
