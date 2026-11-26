"""Rebuild .152's fixed bank and only its previously unseen normal streams."""
import csv
import json
from pathlib import Path
import sqlite3
import struct
import sys
import zlib

import numpy as np

HERE=Path(__file__).resolve().parent
RUNS=HERE.parent
TON=RUNS/"p4_ton_password_frozen_v12_20261118"
sys.path[:0]=[str(RUNS/"p4_login_formal_v1_20261121")]
from frozen_score import FROZEN, calibration, e3_batch, inputs790, models, scores, sealed_runtime
from audit import identity, read, save

TARGET="192.168.1.152"
HEADS=("27","127","227","ensemble")
LAYERS=("all","off_bypass_with_transport_data")
ASSETS=RUNS.parents[2]/"data_external/login_pilot/formal_20261122_402788/frozen_quick_check_assets"


def write_csv(file,rows):
    with file.open("w",encoding="utf8",newline="\n") as f:
        wr=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        wr.writeheader()
        wr.writerows(rows)


def build_db(out,paths,cfg,site,cut_expected):
    from frontend import bind_direction, db_create, new_context, q_context_event
    from common_ton import digest
    from admission import rawip
    from wire import stream
    from vendor.stream_core import Engine
    import ton_recent
    registry={x:w["owner"] for x,w in site["hosts"].items()}
    num={rawip(x):w for x,w in registry.items()}
    info=site["hosts"][TARGET]
    owner=info["owner"]
    addr=rawip(TARGET)
    reduced=dict(site,hosts={TARGET:info})
    limits={role:cfg["sources"][role]["complete_packets"] for role in paths}
    exe=Path("C:/Program Files/Wireshark/tshark.exe")
    starts=info["window_start_ns"]
    stops=info["window_end_ns"]
    cut=0
    normal1=set()
    components=set()
    before=None
    db=db_create(out/"positions.sqlite")
    for role,frame,ts,wire,cap,row,h in stream(
            ("normal1","normal2"),paths,cfg,reduced,exe,out/"wire",limits):
        if role!=before:
            ctx=new_context(role,set(registry.values()),False)
            engine=Engine()
            before=role
        if frame%250000==0:
            print("ToN source positions",role,frame,flush=True)
            db.commit()
        l4=None
        if row is not None and h is not None:
            protocol="tcp" if h.proto==6 else "udp"
            s=row[protocol+".stream"]
            if s:
                l4=protocol+"-"+s
                if role=="normal1":
                    normal1.add(l4)
        if role=="normal1" and frame>cut_expected:
            continue
        event=q_context_event(h,num)
        clock=engine.advance(frame,ts,role,event)
        if role=="normal1" and clock<=stops:
            cut=frame
        if row is None:
            assert ctx.frame+1==frame
            ctx.frame,ctx.previous_ns=frame,ts
            continue
        who,namespace,_=ctx.append(bind_direction(row,h,registry))
        if who!=owner or ctx.query_reason not in ("VALID","PAYLOAD_TRUNCATED_QUERY"):
            continue
        assert h is not None and row["ton.owner.src"]!=row["ton.owner.dst"]
        key=namespace[-1]
        component=digest([who,key])
        if component not in components:
            db.execute("INSERT INTO components VALUES(?,?)",(component,json.dumps(key,separators=(",",":"))))
            components.add(component)
        fields={k:row.get(k,"") for k in ton_recent.FIELDS}
        if any(x["kind"]=="MISSING_HEADER_TAINT_RESET" for x in ctx.events):
            fields["_fresh_after_taint"]=True
        body=zlib.compress(json.dumps(fields,separators=(",",":")).encode(),1)
        db.execute("INSERT INTO event VALUES(?,?,?,?,?,?)",(role,frame,ts,who,component,body))
        if not ctx.query_allowed:
            continue
        reference=role=="normal1" and starts<=ts and clock<=stops
        new=role=="normal2" and h.dst==addr and h.proto==6 and l4 is not None and l4 not in normal1
        if not (reference or new):
            continue
        uid=digest([cfg["sources"][role]["sha256"],frame,who])
        x=struct.pack("<8d",*engine.features(who,h.proto))
        db.execute("INSERT INTO point VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (role,frame,ts,TARGET,who,h.proto,component,uid,"reference" if reference else "normal",
                    "" if reference else l4,int(h.off),int(h.data>0),0,x,int(new),""))
    assert cut==cut_expected
    db.commit()
    return db


def select_bank(db,cfg,site,expected):
    from frontend import reference_selection
    import onboarding_dense_reference_v1 as selector

    def exact_uniform(rows,count,salt):
        ranks={r["uid"]:selector._rank(r["uid"],salt) for r in rows}
        order=sorted(rows,key=lambda r:(r["timestamp"],ranks[r["uid"]]))
        if len(order)==count:
            return order
        times=np.array([r["timestamp"] for r in order],dtype=np.float64)
        lo,hi=order[0]["timestamp"],order[-1]["timestamp"]
        times_at=[(lo+hi)/2] if count==1 else [lo+(hi-lo)*j/(count-1) for j in range(count)]
        result=[]
        start=0
        for j,when in enumerate(times_at):
            stop=len(order)-(count-j-1)
            distances=np.abs(times[start:stop]-when)
            eligible=np.flatnonzero(distances==distances.min())+start
            i=min(eligible,key=lambda k:ranks[order[k]["uid"]])
            result.append(order[i])
            start=i+1
        return result

    original=selector._uniform_time
    fixture=[dict(uid=f"{i:064x}",timestamp=1554220324.759+(i//3)*.000123) for i in range(90)]
    for slots in (1,2,7,51,90):
        assert exact_uniform(fixture,slots,selector.SALT)==original(fixture,slots,selector.SALT)
    cuts={TARGET:expected["window"]["frame_end"]}
    reduced=dict(site,hosts={TARGET:site["hosts"][TARGET]})
    # Vectorize the exact comparison and retain the byte-pinned selected UID order.
    selector._uniform_time=exact_uniform
    db.execute("UPDATE point SET selected=0 WHERE kind='reference'")
    try:
        refs=reference_selection(db,cfg,reduced,cuts,pilot=False)[TARGET]
    finally:
        selector._uniform_time=original
    assert refs==expected, "frozen .152 bank roster"
    db.execute("UPDATE point SET selected=0 WHERE proto!=6")
    assert db.execute("SELECT COUNT(*) FROM point WHERE selected=1 AND kind='normal'").fetchone()[0]==504
    assert db.execute("SELECT COUNT(*) FROM point WHERE selected=1 AND kind='reference'").fetchone()[0]==4096
    db.commit()
    return cuts,refs


def features(db,cfg,site,cuts,pins,expected_rows):
    from frontend import meta
    from representations import reconstructed
    # A stopped local replay may already have created this derived index.
    db.execute("DROP INDEX IF EXISTS event_by_component")
    data={}
    for role,frame,ts,host,owner,proto,cid,uid,kind,conn,off,payload,ctx,key in db.execute(
         """SELECT p.role,p.frame,p.ts,p.host,p.owner,p.proto,p.comp,p.uid,p.kind,p.conn,p.off,p.data,p.ctx,c.keyjson
            FROM point p JOIN components c ON p.comp=c.comp WHERE p.selected=1 ORDER BY p.role,p.frame"""):
        key=json.loads(key)
        row=meta(cfg,role,frame,ts,owner,host,proto,key,kind,cuts.get(host),site["hosts"][host]["window_end_ns"])
        assert row["uid"]==uid and row["component_id"]==cid
        row.update(conn=conn,off=bool(off),data=bool(payload))
        data[uid]=(row,np.frombuffer(ctx,"<f8"))
    tuples=[]
    for uid,proto,q,flow,proof,witness in reconstructed(db,cfg,site,{"cut_frames":cuts}):
        assert proto==6 and not witness
        row,x=data[uid]
        tuples.append((uid,row["frame"],flow,proof,q,x))
    assert len(tuples)==len(data)==expected_rows
    tuples.sort(key=lambda a:a[0])
    def show(done,total):
        if done==total or done%256==0:
            print("ToN frozen E3",done,total,flush=True)
    z,enc,batches=e3_batch(tuples,pins,show)
    q=np.stack([a[4] for a in tuples])
    x=np.stack([a[5] for a in tuples])
    rows=[data[a[0]][0] for a in tuples]
    return rows,z,q,x,enc,batches


def report(rows,raw,cc,cuts,out):
    with (TON/"received/NORMAL_BOUNDARY.csv").open(encoding="utf-8-sig",newline="") as f:
        old={(r["head"],r["layer"]):r for r in csv.DictReader(f)
             if r["host"]==TARGET and r["boundary"]=="FIRST_SEEN_IN_NORMAL_2"}
    a,b=raw>cuts,cc>cuts
    assert (b<=a).all()
    conn=np.array([r["conn"] for r in rows])
    output=[]
    for layer in LAYERS:
        mask=np.ones(len(rows),dtype=bool) if layer=="all" else np.array([r["off"] and r["data"] for r in rows])
        n,m=int(mask.sum()),len(set(conn[mask]))
        for j,h in enumerate(HEADS):
            ra,co=int(a[mask,j].sum()),int(b[mask,j].sum())
            assert (n,m,ra,co)==tuple(int(old[h,layer][key]) for key in
                         ("normal_n","normal_connections","raw_fp","logical_ccnr_fp")), (h,layer,ra,co)
            output.append(dict(host=TARGET,head=h,layer=layer,queries=n,connections=m,raw_fp_queries=ra,ccnr_fp_queries=co,
                           raw_fp_connections=len(set(conn[mask&a[:,j]])),ccnr_fp_connections=len(set(conn[mask&b[:,j]]))))
    write_csv(out/"TON_MIDDLEWARE_BOUNDARY_LOCAL.csv",output)
    return output


def run(out,table,spool=None):
    archive=RUNS.parents[2]/"datasets/external/ton_iot_raw_network/raw_pcap_pilot_v1"
    paths={r:archive/n for r,n in (("normal1","normal_1.pcap"),("normal2","normal_2.pcap"))}
    source=read(TON/"received/VERIFIED_INPUTS.json")["inputs"]
    for r,pcap in paths.items():
        assert identity(pcap)=={k:source[r][k] for k in ("sha256","bytes")}
    cfg=read(TON/"SCOPED_INPUTS.json")
    site=read(TON/"DIAGNOSTIC_CARD.json")
    old=read(TON/"received/SCIENCE.json")["references"][TARGET]
    resume=spool is not None and spool.resolve()==out.resolve()
    out.mkdir(parents=True,exist_ok=resume)
    print("ToN both original captures SHA-256 verified",flush=True)
    with sealed_runtime() as (frozen,pins):
        from replay_geometry import replay
        from reference_inputs import normalized_context
        from vendor import constrained_onboarding_core_v3 as core,p4_worker
        if spool is None:
            db=build_db(out,paths,cfg,site,old["window"]["frame_end"])
        else:
            db=sqlite3.connect(out/"positions.sqlite")
            if not resume:
                with sqlite3.connect(spool/"positions.sqlite") as previous:
                    previous.backup(db)
            assert db.execute("PRAGMA quick_check").fetchone()[0]=="ok"
            sizes=dict(db.execute("SELECT kind,COUNT(*) FROM point GROUP BY kind"))
            assert sizes=={"normal":504,"reference":109385}
        cuts,refs=select_bank(db,cfg,site,old)
        print("ToN original bank UID order verified",refs["ordered_roster_sha256"],flush=True)
        rows,z,q,x,enc,batches=features(db,cfg,site,cuts,pins,4600)
        db.close()
        bankids=np.array([i for i,r in enumerate(rows) if r["use"]=="REFERENCE"])
        queries=np.array([i for i,r in enumerate(rows) if r["use"]=="QUERY"])
        rr=[rows[i] for i in bankids]
        qr=[rows[i] for i in queries]
        zn=calibration(pins)
        rids=[r["uid"] for r in rr]
        bank=core.ReferenceBank(rr,z[bankids],q[bankids],zn[:2],feature_uids=rids,q_uids=rids,allow_prebank_history=True)
        ref_context=normalized_context(x[bankids],zn[2:])
        d=dict(rows=qr,z=z[queries],q=q[queries],context=normalized_context(x[queries],zn[2:]))
        geo=read(FROZEN/"GEOMETRY.json")
        g=replay(d,bank,ref_context,geo,lambda *a,**kw:None,"V14_NORMAL_BOUNDARY")
        raw=scores(models(ASSETS),inputs790(d["z"],d["q"],x[queries],zn))
        cfg=frozen["method"]
        cuts=np.asarray(cfg["cuts"])
        assert cuts.tolist()==read(TON/"received/MODEL_FREEZE_CHECK.json")["cuts"]
        cc=p4_worker.correct(raw,g["support3"],d["q"],cfg["scales"],True,power=cfg["p"])
        obs=report(qr,raw,cc,cuts,table)
        np.savez_compressed(out/"NEW_NORMAL_DECISIONS.npz",uid=[r["uid"] for r in qr],conn=[r["conn"] for r in qr],
                            data=[r["data"] for r in qr],off=[r["off"] for r in qr],raw=raw,ccnr=cc,cuts=cuts)
    save(table/"TON_MIDDLEWARE_LOCAL_PROOF.json",dict(status="PASS",scope=".152 first-seen normal queries, original capture prefixes",
         source_inputs={k:identity(p) for k,p in paths.items()},reference=refs,
         encoded_reference_rows=len(rr),queries=len(qr),thresholds=cuts.tolist(),encoder=enc,physical_batches=batches,
         reused_frame_scan=str(spool.resolve()) if spool else None,
         count_parity="original per-seed packet totals for both layers",source_result=str(out.resolve()),
         array=identity(out/"NEW_NORMAL_DECISIONS.npz"),ensemble=[r for r in obs if r["head"]=="ensemble"]))
    print("ToN new-flow count verified",[r for r in obs if r["head"]=="ensemble"],flush=True)


if __name__=="__main__":
    run(*map(Path,sys.argv[1:]))
