"""Build the fixed two-hour bank and replay the three frozen matching rules."""
import csv
import ipaddress
from pathlib import Path
import struct
import sys

import numpy as np

from frozen_score import FROZEN, adjusted, calibration, digest_order, e3_batch, inputs790, models, scores
from audit import NS, identity, read, save, timestamp

HERE=Path(__file__).resolve().parent
PRIOR_ROLE=HERE.parent/"p4_ccnr_role_port_v1_20261121"
ARMS=("RAW","v12_CCNR","R2_U1","relative_handshake")


def boundary(c, fields):
    evidence=c["capture"]
    first=evidence["first_qualifying_frame"]
    cross=evidence["crossing_frame"]
    end=evidence["reference_end_ns"]
    server,*clients=c["endpoints"]
    def incoming(r):
        return (r["eth.dst"]==server["mac"] and r["ip.dst"]==server["ip"] and
                r["ip.src"] in {x["ip"] for x in clients} and r["tcp.dstport"]==str(c["server_port"]))
    at=next(r for r in fields if incoming(r))
    later=next(r for r in fields if incoming(r) and timestamp(r)>end)
    assert int(at["frame.number"])==first and timestamp(at)==evidence["first_qualifying_ns"]
    assert int(later["frame.number"])==cross and timestamp(later)==evidence["crossing_ns"]
    assert end-timestamp(at)==7200*NS and timestamp(later)>end
    frames=[i for i,r in enumerate(fields[:cross-1],1) if timestamp(r)<=end]
    assert frames
    return dict(first_qualifying_frame=first,first_qualifying_ns=timestamp(at),reference_end_ns=end,
                cutoff_frame=max(frames),last_observed_frame_before_crossing=cross-1,
                crossing_frame=cross,crossing_ns=timestamp(later),window_seconds=7200)


def packet_stream(pcap,c,fields,source):
    from frontend import meta, new_context
    from vendor.stream_core import Engine
    from history_stream import History, decode, records

    pin=read(PRIOR_ROLE/"PACKAGE_MANIFEST.json")["files"]["roles.py"]
    assert identity(PRIOR_ROLE/"roles.py")["sha256"]==pin
    sys.path.insert(0,str(PRIOR_ROLE))
    from roles import PrefixRoles
    assert Path(sys.modules["roles"].__file__).parent==PRIOR_ROLE

    owner=c["endpoints"][0]["mac"]
    device=c["endpoints"][0]["ip"]
    no_sep=owner.replace(":","")
    scope="login_"+c.get("scope","pilot")
    ctx=new_context(scope,{owner},numeric=True)
    engine=Engine()
    history=History()
    roles=PrefixRoles()
    reference=source is not None
    pcap_sha=identity(pcap)["sha256"]
    cfg=dict(sources={scope:dict(sha256=pcap_sha)})
    for (f,epoch,raw),row in zip(records(pcap),fields,strict=True):
        assert f==int(row["frame.number"]) and epoch==timestamp(row)
        if reference and f>source["cutoff_frame"]:
            break
        history.advance(epoch)
        if not row["tcp.stream"]:
            assert ctx.frame+1==f
            ctx.frame,ctx.previous_ns=f,epoch
            engine.advance(f,epoch,scope)
            continue
        p=decode(raw,False)
        assert p and p.proto==6
        inbound=row["eth.dst"]==owner
        assert (row["eth.src"]==owner)!=inbound
        row["ton.owner.src"]="" if inbound else owner
        row["ton.owner.dst"]=owner if inbound else ""
        event=None
        if inbound:
            s,d=[int(ipaddress.IPv4Address(row[k])) for k in ("ip.src","ip.dst")]
            sp,dp=[int(row[k]) for k in ("tcp.srcport","tcp.dstport")]
            event=(owner,6,int(row["ip.len"]),s,struct.pack("!BIIHH",6,s,d,sp,dp))
        engine.advance(f,epoch,scope,event)
        history.observe(no_sep,p,inbound)
        group=History.group(no_sep,p.endpoints if inbound else p.endpoints[::-1])
        role,port,syn=roles.observe(no_sep,p,inbound,f)
        kept,session,_=ctx.append(row)
        if not ctx.query_allowed or (reference and (epoch>source["reference_end_ns"] or
                                  engine.clock>source["reference_end_ns"] or epoch<source["first_qualifying_ns"])):
            continue
        assert kept==owner
        extra=(source["cutoff_frame"],source["reference_end_ns"]) if reference else ()
        metadata=meta(cfg,scope,f,epoch,owner,device,6,session[-1],"reference" if reference else "normal",*extra)
        yield (metadata,ctx.states[session],engine.features(owner,6),history.handshakes[group],
               int(role),int(port),int(syn),bool(inbound))


def select_frozen(candidates,source):
    from common_ton import digest
    from constrained_onboarding_reference_v2 import VERSION, plan_banks
    from onboarding_dense_reference_v1 import plan_dense_positions

    first=candidates[0]
    latest={}
    for row in candidates:
        assert row["source_sha256"]==first["source_sha256"] and row["device"]==first["device"]
        k=row["component_id"]
        last=latest.get(k)
        if last is None or (row["timestamp"],row["frame"],row["uid"])>(last["timestamp"],last["frame"],last["uid"]):
            latest[k]=row
    useful=sorted(latest.values(),key=lambda r:(r["device"],r["protocol"],r["component_id"]))
    t0=source["first_qualifying_ns"]/NS
    stop=source["reference_end_ns"]/NS
    census=dict(generator_version=VERSION,status="COMPLETE",enumeration="ALL_LEGAL_ENDPOINTS_LAST_PER_COMPONENT",
                window_closed=True,duration_seconds=7200,t0=t0,cutoff=t0+7200,candidate_rows=len(useful),
                candidates_sha256=digest(useful),decoder_identity={"reader":"frozen_RECENT_Ethernet"},
                source_sha256=first["source_sha256"],normality_evidence="Isolated test service and aligned client/server records",
                device_registry=[dict(device=first["device"],owner=first["owner"],partition=first["partition"])],
                capture_id=first["capture_id"],cutoff_frame=source["cutoff_frame"])
    anchors={r["uid"] for r in plan_banks(useful,census,t0=t0,policy="B2")["rows"]}
    window=dict(partition=first["partition"],device=first["device"],capture_id=first["capture_id"],
                source_sha256=first["source_sha256"],start=t0,end=stop,reference_end=stop,
                frame_end=source["cutoff_frame"])
    position=plan_dense_positions(candidates,[window],encoded_uids=anchors,mandatory_uids=anchors)
    chosen=set(position["selected_uids"])
    assert chosen and anchors<=chosen
    return [r for r in candidates if r["uid"] in chosen],len(latest),len(anchors)


def materialize(pcap,c,fields,cutoff,chosen,pins):
    from constrained_onboarding_reference_v2 import query_descriptor, reference_descriptor

    extract=reference_descriptor if cutoff else query_descriptor
    visited={}
    encoder=[]
    for row,state,x,h,role,port,syn,inbound in packet_stream(pcap,c,fields,cutoff):
        if row["frame"] not in chosen:
            continue
        assert chosen[row["frame"]]==row["uid"] and (cutoff or inbound) and syn<=row["frame"]
        if not cutoff:
            flags=int(fields[row["frame"]-1]["tcp.flags"],16)
            assert flags&0x12!=2 and int(fields[row["frame"]-1]["tcp.len"])>0
        flow,numeric,proof=state.snapshot()
        body=dict(flow=flow,state=numeric,provenance=proof,source_sha256=row["source_sha256"])
        q,_=extract(body,row)
        encoder.append((row["uid"],row["frame"],flow,proof,q,x))
        visited[row["frame"]]=(row["uid"],row["component_id"],row["timestamp_ns"],h,role,port,inbound)
    assert visited.keys()==chosen.keys()
    z,encoder_id,batches=e3_batch(encoder,pins)
    columns=list(zip(*visited.values(),strict=True))
    matrix=dict(frame=np.array(list(visited)),uid=np.array(columns[0]),component=np.array(columns[1]),
                clock=np.array(columns[2]),h=np.array(columns[3]),role=np.array(columns[4]),port=np.array(columns[5]),
                inbound=np.array(columns[6]),z=z,q=np.stack([x[-2] for x in encoder]).astype(np.float32),
                physical=np.asarray([x[-1] for x in encoder],dtype=np.float64))
    return matrix,dict(encoder=encoder_id,batches=batches,rows=len(z),uid_order_sha256=digest_order(matrix["uid"]))


def open_bank(folder,c,fields,pins):
    pcap=folder/"login.pcap"
    cut=boundary(c,fields)
    candidates=[r[0] for r in packet_stream(pcap,c,fields,cut)]
    assert candidates and candidates[0]["frame"]==cut["first_qualifying_frame"]
    selected,total,anchors=select_frozen(candidates,cut)
    b,features=materialize(pcap,c,fields,cut,{r["frame"]:r["uid"] for r in selected},pins)
    service=(b["role"]==1)&(b["port"]==c["server_port"])
    target=folder/"REFERENCE.npz"
    np.savez_compressed(target,**b)
    assert len(set(b["uid"]))==len(b["uid"])
    receipt=dict(status="PASS",service_instance=c["service_instance"],server_endpoint=c["endpoints"][0],
                 server_port=c["server_port"],reference_end_ns=cut["reference_end_ns"],boundary=cut,
                 candidates=len(candidates),available_components=total,sparse_anchors=anchors,
                 reference_rows=len(b["uid"]),reference_components=len(set(b["component"])),
                 same_service_rows=int(service.sum()),same_service_components=len(set(b["component"][service])),
                 inbound_reference_rows=int(b["inbound"].sum()),outbound_reference_rows=int((~b["inbound"]).sum()),
                 capture=identity(pcap),reference=identity(target),features=features)
    save(folder/"REFERENCE_SEAL.json",receipt)
    return receipt


def match(query,ref,cfg,norm):
    from vendor import constrained_onboarding_core_v3 as core, geometry_frozen

    geometry=read(FROZEN/"GEOMETRY.json")
    assert all(geometry["method"][k]==v for k,v in cfg["method"].items())
    tcp=geometry["geometry"]["protocols"]["6"]
    context=geometry["context_radii"]["6"]
    assert tcp["status"]==context["status"]=="READY"
    a,b,xc,xs=norm
    rz=core._unit(ref["z"],(a,b)).T
    qz=core._unit(query["z"],(a,b))
    rc=((np.log1p(ref["physical"])-xc)/xs).astype(np.float32)
    qc=((np.log1p(query["physical"])-xc)/xs).astype(np.float32)
    _,components=np.unique(ref["component"],return_inverse=True)
    support=np.zeros((3,len(qz)),dtype=np.float64)
    legal=np.zeros_like(support,dtype=np.int64)
    compatible=np.zeros_like(support,dtype=np.int64)
    all_refs=np.ones(len(rz.T),bool)
    logarithm=np.log1p(ref["h"])
    stride=max(1,min(core.BLOCK_ROWS,core.PAIR_BUDGET//len(all_refs)))
    for start in range(0,len(qz),stride):
        i=np.arange(start,min(start+stride,len(qz)))
        dz=np.clip(1.-qz[i]@rz,0.,2.)
        dq=geometry_frozen.rms(query["q"][i],ref["q"])
        dc=geometry_frozen.rms(qc[i],rc)
        joint=np.maximum.reduce([core._ratio(dz,tcp["rho_z"]),core._ratio(dq,tcp["rho_q"]),core._ratio(dc,context["rho_c"])])
        for j,idx in enumerate(i):
            role=query["role"][idx]
            same=ref["role"]==role
            r2=(same & (ref["port"]==query["port"][idx])) if role==1 else same
            present=int(query["h"][idx])
            band=np.maximum(present+1,ref["h"]+1)<3*np.minimum(present+1,ref["h"]+1)
            hd=np.abs(np.log1p(present)-logarithm)/np.log(3.)
            extra=np.maximum(joint[j],np.where(band,np.minimum(hd,np.nextafter(1.,0.)),np.inf))
            for arm,(use,distance) in enumerate(((all_refs,joint[j]),(r2,joint[j]),(all_refs,extra))):
                legal[arm,idx]=len(np.unique(components[use]))
                qualified=use&(distance<1.)
                compatible[arm,idx]=len(np.unique(components[qualified]))
                if compatible[arm,idx]>=2:
                    _,index=np.unique(components[qualified],return_inverse=True)
                    low=np.full(compatible[arm,idx],np.inf)
                    np.minimum.at(low,index,distance[qualified])
                    m2=np.partition(low,1)[1]
                    support[arm,idx]=1.-m2
    assert (support[1:]<=support[0]).all()
    assert np.array_equal(compatible>=2,support>0)
    return support,legal,compatible


def evaluate_pairs(query,ref,cfg,pins,assets):
    norm=calibration(pins)
    base=scores(models(assets),inputs790(query["z"],query["q"],query["physical"],norm))
    s,legal,compatible=match(query,ref,cfg,norm)
    method=cfg["method"]
    gates=np.asarray(method["cuts"])
    q_guard=np.zeros(len(base),bool)  # These are original complete POST request anchors.
    by_arm=[base,*(adjusted(base,row,q_guard,method) for row in s)]
    decision=np.stack([x>gates for x in by_arm])
    assert np.all(decision[1]<=decision[2:]) and np.all(decision[1:]<=decision[0])
    return np.stack(by_arm),decision,s,legal,compatible
