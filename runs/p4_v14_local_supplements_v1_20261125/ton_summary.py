"""Assemble ToN Table 7 using connection deduplication and the frozen boundary tags."""
from pathlib import Path
import sys
import numpy as np

from archive_audits import REL, TON, read, records, save, table, verify_return
from sources import HEADS, identity

HOSTS=("152","190","195")
FIRST="FIRST_SEEN_IN_NORMAL_2"
CROSS="CROSSES_NORMAL_FILE_BOUNDARY"
LAYERS=("all","off_bypass_with_transport_data")


def num(row,*keys):
    return tuple(int(row[k]) for k in keys)


def summarize(out,raw):
    for f in ("RAW_TARGETS.csv","NORMAL_BOUNDARY.csv","CCNR_PAIRED.csv"):
        verify_return(TON,f)
    verify_return(REL,"PAIRED.csv")
    proof=read(out/"TON_MIDDLEWARE_LOCAL_PROOF.json")
    assert proof["status"]=="PASS" and proof["array"]==identity(raw)
    with np.load(raw,allow_pickle=False) as a:
        stream,off,data=a["conn"],a["off"],a["data"]
        base,adj=a["raw"]>a["cuts"],a["ccnr"]>a["cuts"]
    boundary=records(TON/"NORMAL_BOUNDARY.csv")
    first={(r["host"].split(".")[-1],r["head"],r["layer"]):r for r in boundary if r["boundary"]==FIRST}
    cross={(r["host"].split(".")[-1],r["head"],r["layer"]):r for r in boundary if r["boundary"]==CROSS}
    ra={(r["host"].split(".")[-1],r["head"],r["layer"]):r for r in records(TON/"RAW_TARGETS.csv")}
    pa={(r["host"].split(".")[-1],r["head"],r["layer"]):r for r in records(TON/"CCNR_PAIRED.csv")}
    ms={(r["group"],r["seed"],r["arm"]):r for r in records(REL/"PAIRED.csv")}
    owners=np.unique(stream[off&data])
    extra=np.isin(stream,owners)
    table_rows=[]
    def append(cohort,h,j,scope,values):
        n,q,r,qraw,c,qcc=values
        assert n and q and 0<=c<=r<=n and 0<=qcc<=qraw<=q
        table_rows.append(dict(cohort=cohort,host=h,head=j,query_scope=scope,
             connections=n,queries=q,raw_fp_connections=r,seconds_ccnr_fp_connections=c,
             multiscale_fp_connections=c,raw_fpr=r/n,seconds_ccnr_fpr=c/n,multiscale_fpr=c/n,
             raw_fp_queries=qraw,seconds_ccnr_fp_queries=qcc,multiscale_fp_queries=qcc))
    for h in HOSTS:
        for j,s in enumerate(HEADS):
            rr=ra[h,s,"all"]
            bb=pa[h,s,"all"]
            n,q,r,rq=num(rr,"normal_connections","normal_included","normal_connections_with_false_alarm","FP")
            c,cq=int(ms[f"TON.{h}.normal.c",s,"v12"]["alarm"]),int(bb["normal_fp_ccnr"])
            assert num(ms[f"TON.{h}.normal.c",s,"v12_H60"],"total","alarm")== (n,c)
            assert num(ms[f"TON.{h}.normal.q",s,"v12_H60"],"total","alarm","added_vs_v12")== (q,cq,0)
            assert int(ms[f"TON.{h}.normal.q",s,"v12"]["alarm"])==cq
            append("all_normal",h,s,"all_admitted",(n,q,r,rq,c,cq))
            for layer in LAYERS:
                f=first[h,s,layer]
                x=cross[h,s,layer]
                n,q,rq,cq=num(f,"normal_connections","normal_n","raw_fp","logical_ccnr_fp")
                if h=="152":
                    mask=np.ones(len(stream),dtype=bool) if layer=="all" else off&data
                    r,c=len(set(stream[mask&base[:,j]])),len(set(stream[mask&adj[:,j]]))
                    assert (int(mask.sum()),len(set(stream[mask])),int(base[mask,j].sum()),int(adj[mask,j].sum()))==(q,n,rq,cq)
                else:
                    assert num(x,"raw_fp","logical_ccnr_fp")== (0,0) and cq==0
                    r,c=int(ra[h,s,layer]["normal_connections_with_false_alarm"]),0
                cohort="first_seen_normal2" if layer=="all" else "first_seen_with_data"
                append(cohort,h,s,layer,(n,q,r,rq,c,cq))
            if h=="152":
                aq=len(set(stream[extra]))
                rq,cq=int(base[extra,j].sum()),int(adj[extra,j].sum())
                r,c=len(set(stream[extra&base[:,j]])),len(set(stream[extra&adj[:,j]]))
                append("first_seen_data_connections_any_packet",h,s,"all_admitted_on_data_connections",
                       (aq,int(extra.sum()),r,rq,c,cq))
            else:
                n1,q1,r1,c1=num(first[h,s,"all"],"normal_connections","normal_n","raw_fp","logical_ccnr_fp")
                assert n1==int(first[h,s,LAYERS[1]]["normal_connections"]) and c1==0
                append("first_seen_data_connections_any_packet",h,s,"all_admitted_on_data_connections",
                       (n1,q1,int(ra[h,s,"all"]["normal_connections_with_false_alarm"]),r1,0,c1))
    count_keys=("connections","queries","raw_fp_connections","raw_fp_queries",
                "seconds_ccnr_fp_connections","seconds_ccnr_fp_queries")
    scopes={r["cohort"]:r["query_scope"] for r in table_rows}
    for cohort,scope in scopes.items():
        for s in HEADS:
            group=[r for r in table_rows if r["cohort"]==cohort and r["head"]==s and r["host"] in HOSTS]
            assert len(group)==3
            values=tuple(sum(r[k] for r in group) for k in count_keys)
            append(cohort,"ALL",s,scope,values)
    en={r["cohort"]:r for r in table_rows if r["head"]=="ensemble" and r["host"]=="ALL"}
    assert num(en["all_normal"],"connections","raw_fp_connections","seconds_ccnr_fp_connections")== (96,25,3)
    assert num(en["first_seen_normal2"],"connections","queries","seconds_ccnr_fp_queries")== (93,1025,2)
    assert num(en["first_seen_with_data"],"connections","queries","seconds_ccnr_fp_connections")== (92,545,0)
    take=adj[:,HEADS.index("ensemble")]
    residual=[dict(connection=str(k),nondata_false_alarms=int((take&(stream==k)&~(off&data)).sum()),
                   eligible_data_queries=int((off&data&(stream==k)).sum())) for k in np.unique(stream[take])]
    assert len(residual)==1 and residual[0]["nondata_false_alarms"]==2 and residual[0]["eligible_data_queries"]>0
    table(out/"TON_TABLE7_VERIFIED.csv",table_rows)
    save(out/"TON_TABLE7_CHECK.json",dict(status="PASS",scope="logical host pairing, original CIC source thresholds",
         sums=en,local_middleware=identity(out/"TON_MIDDLEWARE_LOCAL_PROOF.json"),
         first_seen="normal_2 TCP stream absent from the appended normal_1 stream prefix",
         middleware_ensemble_first_seen_residual=residual,
         ms_same_as_seconds="verified same normal-query alarm set by nested decisions and zero added alarms"))
    print({k:(v["seconds_ccnr_fp_connections"],v["connections"]) for k,v in en.items()},flush=True)


if __name__=="__main__":
    summarize(*map(Path,sys.argv[1:3]))
