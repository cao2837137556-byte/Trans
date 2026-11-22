"""Exact paired decisions and a floating-point-complete uniform-λ comparator."""
from dataclasses import dataclass
from datetime import datetime, timezone
import numpy as np

from history_common import HEADS, HOSTS, POOLS, save, write, read, check, sha


@dataclass(frozen=True)
class View:
    name: str
    mask: np.ndarray
    unit: str
    kind: str


def views(pool, a):
    n=(a["kind"]=="normal") & a["active"]
    f=(a["kind"]=="attack") & a["active"]
    if pool in ("CIC_DEV","UNSW_DEV","EDGE"):
        yield View(pool+".normal.q",n,"query","normal")
        yield View(pool+".normal.c",n,"connection","normal")
        if pool=="EDGE":
            for role in ("HTTP","UDP"):
                yield View("EDGE."+role+".q",f & (a["activity"]==role),"query","attack_flood")
        yield View(pool+".flood.q",f,"query","attack_flood")
    elif pool=="EDGE_PASSWORD":
        yield View("EDGE.password.any",f,"connection","attack_password")
        yield View("EDGE.password.POST",f & a["post"],"connection","attack_password")
        yield View("EDGE.password.POST.q",f & a["post"],"query","attack_password")
        yield View("EDGE.password.any.q",f,"query","attack_password")
    elif pool=="TON":
        yield View("TON.normal.all.c",n,"connection","normal")
        yield View("TON.normal.all.q",n,"query","normal")
        for host in HOSTS:
            label="TON."+host.rsplit(".",1)[1]
            select=a["activity"]==host
            for suffix,mask in (("normal",n),("password",f)):
                kind="normal" if suffix=="normal" else "attack_password"
                yield View(label+"."+suffix+".c",mask & select,"connection",kind)
                yield View(label+"."+suffix+".q",mask & select,"query",kind)
            data=f & select & a["off"] & a["data"]
            yield View(label+".payload.c",data,"connection","attack_password")
            yield View(label+".payload.q",data,"query","attack_password")


class Units:
    def __init__(self, view, a):
        self.view=view
        self.take=np.flatnonzero(view.mask)
        self.groups=None
        self.n=len(self.take)
        if view.unit=="connection":
            ids,self.groups=np.unique(a["group"][self.take],return_inverse=True)
            self.n=len(ids)

    def any(self,b):
        a=b[self.take]
        if self.groups is None:
            return a
        y=np.zeros((self.n,*a.shape[1:]),bool)
        np.logical_or.at(y,self.groups,a)
        return y

    def maximum(self,values):
        values=values[self.take]
        if self.groups is None:
            return values
        out=np.full(self.n,-1.,dtype=np.float64)
        np.maximum.at(out,self.groups,values)
        return out


def unit_views(pool,a):
    return {v.name:Units(v,a) for v in views(pool,a)}


def severity(a):
    s=a["support"]
    return np.where(a["guard"] | (s==0),0.,1.-np.power(1.-s,4))


def correct(raw,g,scales,lam,cut):
    seeds=raw[:,:3] - (np.asarray(lam)*scales)*g[:,None]
    return np.column_stack((seeds,seeds.mean(axis=1,dtype=np.float64))) > cut


def boundaries(raw,g,scales,cut,start,k):
    """Greatest representable λ at which a previously lost alert turns on."""
    use=(raw[:,k]>cut[k]) & ~start[:,k] & (g>0)
    result=np.full(len(raw),-1.,dtype=np.float64)
    if not use.any():
        return result
    r=raw[use,:3];s=g[use];n=len(s)
    hi=np.full(n,np.float64(.25).view(np.uint64),np.uint64)
    lo=np.zeros(n,np.uint64)
    while (hi-lo>1).any():
        selected=(hi-lo)>1
        mid=lo+(hi-lo)//2
        lam=mid.view(np.float64)
        if k<3:
            alert=(r[:,k]-(lam*scales[k])*s)>cut[k]
        else:
            corrected=r-(lam[:,None]*scales)*s[:,None]
            alert=corrected.mean(axis=1,dtype=np.float64)>cut[k]
        lo=np.where(selected & alert,mid,lo)
        hi=np.where(selected & ~alert,mid,hi)
    assert np.array_equal(lo+1,hi)
    result[use]=lo.view(np.float64)
    return result


def min_lambda(events_by_group,budgets):
    lower={}
    for name,values in events_by_group.items():
        actual=values[values>=0]
        budget=budgets[name]
        if len(actual)<=budget:
            lower[name]=0.
        else:
            # Positive ties at the boundary count together. The next float switches the whole tie off.
            pos=len(actual)-budget-1
            lower[name]=float(np.nextafter(np.partition(actual,pos)[pos],np.inf))
    return max(lower.values(),default=0.),lower


def restore_times(a, units, start, changed, raw, group, head, arm):
    if units.groups is None or units.view.kind!="attack_password":
        return None
    keep=~units.any(start) & units.any(changed)
    if not keep.any():
        return None
    mark=units.take
    minimum=np.iinfo(np.int64).max
    t=a["clock"][mark]
    first=np.full(units.n,minimum,np.int64)
    alert=first.copy()
    old=first.copy()
    np.minimum.at(first,units.groups,t)
    np.minimum.at(alert,units.groups,np.where(changed[mark],t,minimum))
    np.minimum.at(old,units.groups,np.where(raw[mark],t,minimum))
    new=alert[keep];delays=(new-first[keep])/1e9;late=(new-old[keep])/1e9
    assert (delays>=0).all() and (late>=0).all()
    def utc(value):
        return datetime.fromtimestamp(int(value)//10**9,timezone.utc).isoformat()
    sec=np.percentile(delays,[25,50,75,90,100]);raw_sec=np.percentile(late,[25,50,75,90,100])
    return dict(group=group,seed=head,arm=arm,rescued=len(new),
                first_observed_utc=utc(new.min()),last_observed_utc=utc(new.max()),
                sec_from_eligible_p25=sec[0],sec_from_eligible_median=sec[1],sec_from_eligible_p75=sec[2],
                sec_from_eligible_p90=sec[3],sec_from_eligible_max=sec[4],
                sec_from_raw_p25=raw_sec[0],sec_from_raw_median=raw_sec[1],sec_from_raw_p75=raw_sec[2],
                sec_from_raw_p90=raw_sec[3],sec_from_raw_max=raw_sec[4])


def load_metrics(out,pool):
    cert=read(out/(pool+"_INPUT.json"))
    p=check(out/cert["file"],cert)
    with np.load(p,allow_pickle=False) as z:
        a={k:z[k] for k in z.files}
    return a


def verify_base(pool,a,contract,expected):
    cut=np.array(contract["cuts"]);scales=np.array(contract["scales"])
    g=severity(a);scores=a["v12"]
    raw=scores>cut
    start=correct(scores,g,scales,.25,cut)
    if pool=="TON":
        assert np.array_equal(raw,a["raw_alarm"]) and np.array_equal(start,a["ccnr_alarm"])
    uv=unit_views(pool,a)
    found=0
    for name,u in uv.items():
        if name not in expected:
            continue
        cells=np.column_stack((np.full(4,u.n),u.any(raw).sum(0),u.any(start).sum(0)))
        assert np.array_equal(cells,expected[name]),(name,cells,expected[name])
        found+=1
    assert np.array_equal(raw,correct(scores,g,scales,0.,cut))
    return raw,start,g,uv,found


def evaluate(out,contract,expected):
    cuts=np.array(contract["cuts"]);scales=np.array(contract["scales"])
    source=read(out/"THRESHOLD.json")
    theta=source["threshold"]
    recipe=read(out/"CALIBRATE.json")
    assert recipe["threshold_sha256"]==sha(out/"THRESHOLD.json")
    capacity=contract["budgets"]
    pools={}
    total=0
    for pool in POOLS:
        a=load_metrics(out,pool)
        raw,start,g,units,seen=verify_base(pool,a,contract,expected)
        total+=seen
        guard=a["inbound"] & (a["proto"]==6) & (a["count"]>theta)
        revised=start | (guard[:,None] & raw)
        assert (start<=revised).all() and (revised<=raw).all()
        pools[pool]=(a,raw,start,g,units,revised)
    assert total==len(expected)
    stats=[];limits=[];times=[];coverage=[];panels={}
    for k,head in enumerate(HEADS):
        new_cost={}
        breakpoints={}
        for pool,(a,raw,start,g,units,revised) in pools.items():
            base=start[:,k];new=revised[:,k]
            b=boundaries(a["v12"],g,scales,cuts,start,k)
            for name,u in units.items():
                if name in capacity:
                    changed=u.any(new) & ~u.any(base)
                    new_cost[name]=int(changed.sum())
                    v=u.maximum(b)
                    v[u.any(base)]=-1
                    breakpoints[name]=v
        assert new_cost.keys()==capacity.keys()
        matched,limits_by_group=min_lambda(breakpoints,new_cost)
        assert 0.<=matched<=.25
        # Exact lower neighbour cannot meet every budget unless we already reached λ=0.
        if matched>0:
            prior=float(np.nextafter(matched,0.))
            assert any(int(np.count_nonzero(v>=prior))>new_cost[n] for n,v in breakpoints.items())
        for name in capacity:
            matched_cost=int(np.count_nonzero(breakpoints[name]>=matched))
            assert matched_cost<=new_cost[name]
            limits.append(dict(seed=head,normal_group=name,max_budget=capacity[name],
                               history_added=new_cost[name],lambda_added=matched_cost,
                               group_min_lambda=limits_by_group[name],joint_lambda=matched))
        figures={}
        for pool,(a,raw,start,g,units,revised) in pools.items():
            base=start[:,k]
            vals={"v12":base,"history60":revised[:,k],"lambda_equal_cost":correct(a["v12"],g,scales,matched,cuts)[:,k]}
            vals.update({f"lambda_{x:g}":correct(a["v12"],g,scales,x,cuts)[:,k] for x in (.25,.20,.15,.10,.05,0.)})
            assert np.array_equal(vals["lambda_0"],raw[:,k])
            assert np.array_equal(vals["lambda_0.25"],base)
            for group,u in units.items():
                original=u.any(base);control=u.any(raw[:,k]);eligible=u.take
                mask_group=group in capacity
                if head=="ensemble":
                    is_guard=a["inbound"] & (a["proto"]==6) & (a["count"]>theta)
                    coverage.append(dict(group=group,query_rows=len(eligible),
                        tcp_inbound=int((a["inbound"][eligible] & (a["proto"][eligible]==6)).sum()),
                        history_gate_queries=int(is_guard[eligible].sum()),
                        confirmed_handshake_count_median=float(np.median(a["handshake"][eligible])) if len(eligible) else None))
                for arm,pred in vals.items():
                    now=u.any(pred)
                    gained=int((~original & now).sum());lost=int((original & ~now).sum())
                    assert lost==0 and np.all(now<=control)
                    if arm=="lambda_equal_cost" and mask_group:
                        assert gained==int(np.count_nonzero(breakpoints[group]>=matched))
                    stats.append(dict(seed=head,group=group,kind=u.view.kind,unit=u.view.unit,n=u.n,
                                      arm=arm,raw=int(control.sum()),original=int(original.sum()),
                                      alarm=int(now.sum()),added=gained,lost=lost))
                    if arm in ("history60","lambda_equal_cost"):
                        time=restore_times(a,u,base,pred,raw[:,k],group,head,arm)
                        if time is not None:
                            times.append(time)
                        if head=="ensemble":
                            figures.setdefault(group,{})[arm]=dict(total=u.n,raw=int(control.sum()),
                                original=int(original.sum()),alarms=int(now.sum()),added=gained)
        if head=="ensemble":
            panels=figures
    save(out/"PAIRED.csv",stats)
    save(out/"EQUAL_COST.csv",limits)
    save(out/"HISTORY_COVERAGE.csv",coverage)
    if times:
        save(out/"FIRST_ALERT.csv",times)
    primary=panels["TON.195.payload.c"]
    h=primary["history60"];l=primary["lambda_equal_cost"]
    assert (h["total"],h["raw"],h["original"])==(18194,14024,245)
    within=all(panels[n]["history60"]["added"]<=budget for n,budget in capacity.items())
    decision=bool(within and h["alarms"]>=7012 and h["alarms"]>l["alarms"])
    write(out/"RESULT.json",dict(primary=primary,rows=panels,within_budgets=within,
          superiority_default_metric=h["alarms"]>l["alarms"],meeting_recovery=h["alarms"]>=7012,
          advance=decision,threshold=theta,cal_rows=source["rows"],baseline_cells=total,
          first_alert_rows=len(times),all_alerts_monotone=True))
