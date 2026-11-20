"""Recount all four heads from the UID-bound decision arrays on the compute node."""
import csv
from pathlib import Path
import numpy as np
from seal import COUNTS, GROUPS, check, order

HEADS=("27","127","227","ensemble")
SMALL={"EVENTS.csv","NORMAL.csv","UID_CONSISTENCY.csv","ACCEPTANCE.json"}


def tables(path, formal):
    with np.load(path,allow_pickle=False) as a:
        ids, groups, raw, new, support, cuts=(a[k] for k in ("uid","group","raw","ccnr","support","cuts"))
        raw_votes, new_votes = a["raw_alarm"],a["ccnr_alarm"]
        check(len(set(ids.tolist()))==len(ids) and raw.shape==new.shape==(len(ids),4),"DECISION_UID_SHAPE")
        check(np.isfinite(raw).all() and np.isfinite(new).all() and np.isfinite(support).all(),"NONFINITE_SCORES")
        check(np.array_equal(raw_votes,raw>cuts) and np.array_equal(new_votes,new>cuts),"RECORDED_CUTS")
        check(set(groups.tolist())==set(GROUPS),"MISSING_EVENT_OR_NORMAL")
        check(np.all(a["legal_components"]==1) and np.all(a["donors"][:,1]==-1) and
              np.all(np.isposinf(a["distances"][:,1])),"ONE_LEGAL_COMPONENT")
        check(not a["bypass"].any(),"BYPASS_QUERY")
    events=[];normal=[];consistency=[]
    parts={name:groups==name for name in GROUPS}
    parts["attacks"]=groups!="normal";parts["all"]=np.ones(len(ids),bool)
    for name,mask in parts.items():
        n=int(mask.sum());check(n>0,"EMPTY:"+name)
        if formal and name in COUNTS:check(n==COUNTS[name],"DENOMINATOR:"+name)
        uid_order=order(ids[mask].tolist())
        for h,head in enumerate(HEADS):
            old=raw_votes[mask,h];corrected=new_votes[mask,h]
            changes=int(np.count_nonzero(old!=corrected))
            diff=float(np.max(np.abs(new[mask,h]-raw[mask,h])))
            nz=int(np.count_nonzero(support[mask]))
            consistency.append(dict(group=name,head=head,queries=n,nonzero_support=nz,max_abs_score_delta=diff,
                                    decision_flips=changes,uid_order_sha256=uid_order))
            if changes or diff!=0 or nz:
                bad=((support!=0)|(new[:,h]!=raw[:,h])|(raw_votes[:,h]!=new_votes[:,h])) & mask
                i=int(np.flatnonzero(bad)[0])
                raise ValueError(f"UID_PARITY:{ids[i]}:{head}:support={support[i]}:raw={raw[i,h]}:ccnr={new[i,h]}")
            hits=int(old.sum())
            if name=="normal":
                normal.append(dict(group=name,head=head,queries=n,false_alarms=hits,fpr=hits/n))
            elif name!="all":
                detected=sum(bool(raw_votes[groups==g,h].any()) for g in GROUPS[1:] if name in ("attacks",g))
                events.append(dict(group=name,head=head,attack_packets=n,detected_packets=hits,missed_packets=n-hits,
                                   packet_recall=hits/n,events_detected=detected,events=3 if name=="attacks" else 1))
    return events,normal,consistency


def validate_files(folder):
    def readrows(name):
        with (Path(folder)/name).open(encoding="utf-8-sig",newline="") as f:return list(csv.DictReader(f))
    e=readrows("EVENTS.csv");n=readrows("NORMAL.csv");a=readrows("UID_CONSISTENCY.csv")
    check(len(e)==16 and len(n)==4 and len(a)==24,"RESULT_TABLE_SIZE")
    for head in HEADS:
        ev={r["group"]:r for r in e if r["head"]==head}
        nz=[r for r in n if r["head"]==head]
        audit={r["group"]:r for r in a if r["head"]==head}
        check(set(ev)==set(GROUPS[1:])|{"attacks"} and len(nz)==1 and set(audit)==set(GROUPS)|{"all","attacks"},"TABLE_ROWS")
        for group,r in ev.items():
            count=sum(COUNTS[g] for g in GROUPS[1:]) if group=="attacks" else COUNTS[group]
            hits=int(r["detected_packets"])
            check(int(r["attack_packets"])==count and 0<=hits<=count and int(r["missed_packets"])==count-hits
                  and float(r["packet_recall"])==hits/count,"RECOUNT_ATTACK")
            if group!="attacks":check(int(r["events"])==1 and int(r["events_detected"])==int(hits>0),"EVENT_FLAG")
        check(int(ev["attacks"]["detected_packets"])==sum(int(ev[g]["detected_packets"]) for g in GROUPS[1:])
              and int(ev["attacks"]["events"])==3 and int(ev["attacks"]["events_detected"])==sum(int(ev[g]["events_detected"]) for g in GROUPS[1:]),"EVENT_TOTAL")
        r=nz[0];fp=int(r["false_alarms"]);check(int(r["queries"])==3334 and 0<=fp<=3334 and float(r["fpr"])==fp/3334,"NORMAL_RECOUNT")
        for group,r in audit.items():
            count=COUNTS.get(group,15016 if group=="all" else 11682)
            check(int(r["queries"])==count and int(r["nonzero_support"])==int(r["decision_flips"])==0
                  and float(r["max_abs_score_delta"])==0,"UID_RECOUNT")
    return dict(queries=15016,attacks=11682,normal=3334,events=3,heads=4,nonzero_support=0,
                max_abs_score_delta=0.0,decision_flips=0)
