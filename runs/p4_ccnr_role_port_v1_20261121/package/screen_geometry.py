"""Apply R1/R2/R3 to the complete time-legal bank before component reduction."""
from collections import defaultdict
import numpy as np

from roles import RESPONDER, CLIENT, UNKNOWN
from history_common import progress

ARMS=("v12","R1_U1","COVER_R2_U1","R2_U1","R3_U1",
      "R1_U2","COVER_R2_U2","R2_U2","R3_U2","RAW")
CHECKS=(("v12","R1_U1","R2_U1","R3_U1","RAW"),
        ("v12","R1_U2","R2_U2","R3_U2","RAW"),
        ("v12","COVER_R2_U1","R2_U1"),
        ("v12","COVER_R2_U2","R2_U2"))
TOL=2e-10


def reference_columns(roles, ports, query_role, service):
    same=roles==query_role
    at_service=same & (ports==service)
    return (np.flatnonzero(same),
            np.flatnonzero(at_service if query_role==RESPONDER else same),
            np.flatnonzero(at_service if query_role in (RESPONDER,CLIENT) else same))


def supports(rows, z, q, x, qroles, rroles, bank, rc, geom, original, progress_fn, pilot=False):
    from replay_geometry import plan_queries, radii
    from vendor import constrained_onboarding_core_v3 as core, geometry_frozen
    from vendor.fast_geometry import Reducer

    ids=[r["uid"] for r in rows]
    z,q=bank._queries(rows,z,q,ids,ids)
    plans,flags=plan_queries(bank,rows,geom)
    p=np.asarray([r["protocol"] for r in rows])
    tcp=p==6
    ref_role=rroles[:,0]
    ref_port=rroles[:,1]
    s=np.zeros((3,len(rows)),dtype=np.float64)
    s[:,~tcp]=original[None,~tcp]
    r2legal=flags["legal_component_count"].copy()
    r2legal[tcp]=0
    if pilot:
        from replay_geometry import replay
        frozen=replay(dict(rows=rows,z=z,q=q,context=x),bank,rc,geom,lambda *args,**kwargs:None,"ROLE_BASELINE")
        err=float(np.max(np.abs(frozen["support3"]-original),initial=0.))
        assert err<=TOL, ("BASELINE_PRODUCTION_SUPPORT",err)
    else:
        err=0.
    proof=dict(matrix_pairs=0,checked_positive_tcp=0,max_original_support_diff=err)
    n_done=0
    for key,patterns in plans.items():
        if key[-1]!=6:
            continue
        radii2,rho=radii(geom,key[-1])
        for legal,positions in patterns.items():
            ri=np.asarray(legal,dtype=np.int64)
            components=np.asarray([bank.rows[j]["component_id"] for j in ri])
            local_roles,local_ports=ref_role[ri],ref_port[ri]
            groups=defaultdict(list)
            for i in positions:
                groups[(int(qroles[i,0]),int(qroles[i,1]))].append(i)
            rules={}
            subsets={}
            def build_subset(role,port):
                name=(role,port)
                if name not in subsets:
                    cols=np.flatnonzero(local_roles==role) if port is None else np.flatnonzero(
                        (local_roles==role)&(local_ports==port))
                    comp=components[cols].tolist()
                    known=len(set(comp))
                    subsets[name]=(cols,Reducer(comp) if known>=2 else None,known)
                return subsets[name]
            for key_,indices in groups.items():
                r,service=key_
                same=build_subset(r,None)
                port_specific=build_subset(r,service) if r in (RESPONDER,CLIENT) else same
                reducers=(same,port_specific if r==RESPONDER else same,port_specific)
                r2legal[indices]=reducers[1][2]
                rules[key_]=reducers
            if radii2 is None or rho is None or len(set(components))<2:
                assert (original[positions]==0).all()
                continue
            # A subset of a zero-support bank can only have zero support.
            # Still measure legal R2 coverage independently for every row.
            selected=np.asarray([i for i in positions if original[i]>0 or pilot],dtype=np.int64)
            if not len(selected):
                continue
            base=Reducer(components.tolist())
            zref,qref,cref=bank.z[ri].T,bank.q14[ri],rc[ri]
            stride=max(1,min(core.BLOCK_ROWS,core.PAIR_BUDGET//len(ri)))
            for offset in range(0,len(selected),stride):
                use=selected[offset:offset+stride]
                dz=np.clip(1.-core._unit(z[use],bank.normalizer)@zref,0.,2.)
                dq=geometry_frozen.rms(q[use],qref)
                dc=geometry_frozen.rms(x[use],cref)
                joint=np.maximum.reduce((core._ratio(dz,radii2[0]),core._ratio(dq,radii2[1]),core._ratio(dc,rho)))
                s0=base.second(joint)
                old=original[use]
                error=float(np.max(np.abs(np.clip(1.-s0,0.,1.)-old),initial=0.))
                assert error<=TOL,("DIRECT_BASE_SUPPORT",error)
                proof["max_original_support_diff"]=max(proof["max_original_support_diff"],error)
                proof["matrix_pairs"]+=len(use)*len(ri)
                proof["checked_positive_tcp"]+=int((old>0).sum())
                use_groups=defaultdict(list)
                for j,i in enumerate(use):
                    use_groups[(int(qroles[i,0]),int(qroles[i,1]))].append(j)
                for key_,loc in use_groups.items():
                    rids=use[np.array(loc)]
                    for k,(cols,reducer,_) in enumerate(rules[key_]):
                        if reducer is None:
                            continue
                        second=reducer.second(joint[np.ix_(loc,cols)])
                        # Equal second minimum preserves the archived value bit for bit.
                        value=np.clip(1.-second,0.,1.)
                        same=second==s0[loc]
                        s[k,rids]=np.where(same,original[rids],np.minimum(value,original[rids]))
                        if pilot:
                            for row,joint_row,m2 in zip(rids,joint[loc],second):
                                minima={}
                                for col in cols:
                                    c=str(components[col]);v=joint_row[col]
                                    minima[c]=min(minima.get(c,np.inf),v)
                                assert len(minima)>=2 and abs(sorted(minima.values())[1]-m2)<=TOL,("DIRECT_MASKED_SECOND",row,k)
                n_done+=len(use)
                if offset==0 or offset%max(stride*20,1)==0:
                    progress_fn(n_done)
    assert (s[0]<=original).all() and (s[1]<=s[0]).all() and (s[2]<=s[1]).all()
    assert np.array_equal(s[:,~tcp],np.broadcast_to(original[~tcp],s[:,~tcp].shape))
    assert np.all((r2legal<2) <= (s[1]==0))
    assert proof["checked_positive_tcp"]==int(np.sum(tcp & (original>0)))
    ans={"U1":(s,r2legal)}
    s2=s.copy();n2=r2legal.copy()
    unknown=tcp & (qroles[:,0]==UNKNOWN)
    s2[:,unknown]=0.;n2[unknown]=0
    ans["U2"]=(s2,n2)
    return ans,proof


def decisions(a,masks,contract):
    from paired_history import correct,severity
    raw=a["v12"];scales=np.asarray(contract["scales"]);cuts=np.asarray(contract["cuts"])
    base=correct(raw,severity(a),scales,.25,cuts)
    raw_alarm=raw>cuts
    if "raw_alarm" in a:
        assert np.array_equal(raw_alarm,a["raw_alarm"]) and np.array_equal(base,a["ccnr_alarm"])
    result={"v12":base,"RAW":raw_alarm}
    for u,(s,count) in masks.items():
        for j in range(3):
            g=severity(dict(support=s[j],guard=a["guard"]))
            result[f"R{j+1}_{u}"]=correct(raw,g,scales,.25,cuts)
        result[f"COVER_R2_{u}"]=np.where((count<2)[:,None],raw_alarm,base)
    for arm in CHECKS:
        for left,right in zip(arm,arm[1:]):
            assert np.all(result[left]<=result[right]),("ALARM_NESTING",left,right)
    udp=a["proto"]==17
    for arm in ARMS[1:-1]:
        assert np.array_equal(result[arm][udp],base[udp])
    return result
