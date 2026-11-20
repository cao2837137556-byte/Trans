"""Score complete, predeclared Edge password connections only after the three-head freeze."""
from collections import Counter
import csv
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from zipfile import ZipFile
import zlib

import numpy as np
from auxiliary import sha

HERE=Path(__file__).resolve().parent
SOURCE="192.168.0.170"
TARGET="192.168.0.128"
OWNER="dc:a6:32:fb:69:b5"


def prepare(project,out):
    assert (out/"CANDIDATE_FREEZE.json").is_file()
    parent=project/"runs/p4_ton_password_frozen_v12_20261118/package"
    sys.path.insert(0,str(parent))
    from frozen_env import setup,decoder
    _,freeze,_,_=setup(project)
    sys.path.insert(0,str(project/"runs/device_context_training_v2_20261105"))
    from snapshot_gotham import snapshots
    from continuous_input_v3 import nanos,verify_tokenized
    from continuous_features_v3 import tokenize
    from representations import encoder
    pin=json.loads((HERE/"EDGE_ASSET.json").read_bytes())
    zip_path=Path(json.loads((out/"VERIFIED_INPUTS.json").read_bytes())["inputs"]["edgezip"]["path"])
    assert sha(zip_path)==pin["sha256"]
    output=out/"edge";output.mkdir(exist_ok=True)
    p=output/"password.pcap"
    with ZipFile(zip_path) as z:
        info,=z.infolist()
        assert info.file_size==pin["pcap_bytes"]
        with z.open(info) as src,p.open("wb") as dst: shutil.copyfileobj(src,dst,4<<20)
    assert sha(p)==pin["pcap_sha256"]
    with (HERE/"EDGE_POSTS.csv").open(newline="") as f:
        post={int(r["post_frame"]):int(r["tcp_stream"]) for r in csv.DictReader(f)}
    streams=set(post.values())
    assert len(streams)==len(post)==23650
    exe=decoder()
    command=[str(exe),"-n","-r",str(p),"-Y",f"ip.src=={SOURCE} && ip.dst=={TARGET} && eth.dst=={OWNER} && tcp.dstport==80",
             "-T","fields","-E","occurrence=f"]
    for field in ("frame.number","tcp.stream","frame.time_epoch","tcp.srcport"):
        command.extend(["-e",field])
    mapping={}
    with subprocess.Popen(command,stdout=subprocess.PIPE,text=True,encoding="utf8") as child:
        for line in child.stdout:
            frame,stream,epoch,sport=line.rstrip().split("\t")
            frame=int(frame);stream=int(stream)
            if stream in streams:
                mapping[frame]=dict(target=TARGET,mac=OWNER,source=SOURCE,source_port=int(sport),target_port=80,
                                    timestamp_ns=nanos(epoch),device=TARGET,connection=stream,label=1)
        assert child.wait()==0
    assert all(mapping[f]["connection"]==c for f,c in post.items())
    rt,_=encoder(project,freeze)
    import tempfile
    db_file=tempfile.NamedTemporaryFile(dir=output,prefix="queries-",suffix=".sqlite",delete=False)
    db_file.close()
    temporary=Path(db_file.name)
    db=sqlite3.connect(temporary)
    db.executescript("CREATE TABLE feature(uid TEXT PRIMARY KEY,shape TEXT,example BLOB); "
                     "CREATE TABLE metadata(uid TEXT PRIMARY KEY,frame INTEGER UNIQUE,stream INTEGER,ns INTEGER,post INTEGER,q BLOB,x BLOB,sport INTEGER);"
                     "CREATE TABLE batch(batch INTEGER,slot INTEGER,uid TEXT UNIQUE);")
    excluded=[]
    for row in snapshots(p,"edge-password-v5",mapping,pin["pcap_sha256"],exe,excluded=excluded):
        uid=row["uid"];frame=row["frame"];flow=row["flow"]
        ex=tokenize(rt[3],flow);verify_tokenized(flow,row["provenance"],ex)
        shape=f"06-{max(ex['dataset_burst_sizes'])+1:04d}-{len(ex['dataset_burst_sizes']):02d}"
        blob=json.dumps(ex,separators=(",",":"),default=lambda a:a.tolist()).encode()
        db.execute("INSERT INTO feature VALUES(?,?,?)",(uid,shape,zlib.compress(blob,1)))
        db.execute("INSERT INTO metadata VALUES(?,?,?,?,?,?,?,?)",(uid,frame,row["connection"],
                   mapping[frame]["timestamp_ns"],int(frame in post),np.asarray(row["q"],"<f4").tobytes(),
                   np.asarray(row["context"],"<f8").tobytes(),mapping[frame]["source_port"]))
    db.execute("CREATE INDEX byshape ON feature(shape,uid)")
    batch=0
    for (shape,) in list(db.execute("SELECT DISTINCT shape FROM feature ORDER BY shape")):
        cursor=db.execute("SELECT uid FROM feature WHERE shape=? ORDER BY uid",(shape,))
        while chunk:=cursor.fetchmany(16):
            db.executemany("INSERT INTO batch VALUES(?,?,?)",[(batch,i,r[0]) for i,r in enumerate(chunk)])
            batch+=1
    n,conns,posts=db.execute("SELECT count(*),count(distinct stream),sum(post) FROM metadata").fetchone()
    assert n+len(excluded)==len(mapping) and n>0
    excluded_frames={f for f,_ in excluded}
    eligible_connections={v["connection"] for frame,v in mapping.items() if frame not in excluded_frames}
    missing=streams-eligible_connections
    assert conns==len(eligible_connections) and posts+len(set(post)&excluded_frames)==23650
    db.commit();db.close()
    temporary.replace(output/"queries.sqlite")
    from compute import write
    write(output/"INPUTS.json",dict(queries=n,connections=conns,posts=posts,batches=batch,
         capture_connections=23650,unscorable_connections=len(missing),excluded_posts=23650-posts,
         excluded_frames=len(excluded),reasons=dict(Counter(reason for _,reason in excluded)),
         database_sha=sha(output/"queries.sqlite"),input_sha=pin["pcap_sha256"]))


def encode(project,out,part):
    from compute import progress
    sys.path.insert(0,str(project/"runs/p4_ton_password_frozen_v12_20261118/package"))
    from frozen_env import setup
    from representations import encoder,forward_batch
    _,fr,_,_=setup(project)
    rt,_=encoder(project,fr)
    folder=out/"edge"
    pin=json.loads((folder/"INPUTS.json").read_bytes())
    path=folder/"queries.sqlite"
    assert sha(path)==pin["database_sha"]
    db=sqlite3.connect(path.resolve().as_uri()+"?mode=ro&immutable=1",uri=True)
    ids=[];vectors=[]
    for b in range(part,pin["batches"],8):
        u,z,_=forward_batch(db,b,rt);ids.extend(u);vectors.append(z)
        if len(vectors)%64==0:
            progress(out,f"edge_{part}","冻结编码器正在处理 Edge 密码查询",len(vectors),len(range(part,pin["batches"],8)))
    db.close()
    z=np.concatenate(vectors)
    assert z.shape==(len(ids),768)
    np.savez(folder/f"e3_{part}.npz",uid=np.asarray(ids,dtype="S64"),z=z)


def assess(project,out):
    from compare import controls, raw_pair, paired, by_seed, count_pairs, save
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
    results=[]
    for name,seed,a,b in by_seed(comparisons):
        for view,ix in [("any_eligible_inbound",np.ones(len(ids),bool)),("confirmed_login_POST",np.asarray(posts,bool))]:
            cnt=count_pairs(a[ix],b[ix],np.asarray(stream)[ix])
            results.append(dict(source="Edge Password",head=name,seed=seed,kind="attack",view=view,unit="connection",
                                confirmed_connections=23650,without_eligible_query=23650-cnt["total"],**cnt))
    save(out/"EDGE_PASSWORD.csv",results)
    shutil.copyfile(folder/"INPUTS.json",out/"EDGE_INPUTS.json")
