"""Score the handshake-only arm and verify the three frozen POST-score caches."""
import csv
import json
from pathlib import Path
import sys

import numpy as np

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_login_rank5_v1_20261124"))
from evidence import aligned_rows, old_data, verified_archive
from assessment import KEPT, arrays, connection_scores, get_array, roster, saved_formal
from schedule import BURST
from sources import ARMS, HEADS, identity, read, save, table

RANK_RUN="rank5_20261124_022354"
ATTACK_RUN="attack_eval_20261126"
ARM_LABELS=(*ARMS,"handshake_only")


def dataset(name,q,rows,normal,expected):
    uid,stream=arrays(rows)
    assert len(rows)==len(set(uid)) and np.array_equal(q["uid"],uid)
    assert np.array_equal(q["stream"],stream) and tuple(q["arms"])==ARMS
    assert all(r["normal"] is normal for r in rows)
    assert len(set(stream))==expected
    h=np.array([r["handshakes_60s"] for r in rows],dtype=np.int64)
    assert np.array_equal(q["h"],h) and (h>=0).all()
    scores=q["scores"]
    assert scores.shape==(3,len(uid),4) and np.isfinite(scores).all()
    return dict(name=name,uid=uid,stream=stream,score=scores,h=h,normal=normal)


def read_batch(root,row,files,scope,normal):
    name=row["path"]
    receipt=root/name
    assert identity(receipt)==row["receipt"] and files[name]==row["receipt"]["sha256"]
    batch=read(receipt)
    assert batch["status"]=="PASS"
    folder=receipt.parent
    for n,proof in batch["files"].items():
        assert identity(folder/n)==proof
    q=get_array(folder/"SCORES.npz")
    frame_dir=folder/scope
    if normal:
        records=aligned_rows(frame_dir/"ALIGNMENT.jsonl")
    else:
        with (frame_dir/"ALIGNMENT.jsonl").open(encoding="utf8") as f:
            all_rows=[json.loads(line) for line in f]
        records=roster(all_rows)
        assert len(records)==len(all_rows)
        assert all(r["scenario"]==batch["tier"] and r["normal"] is False for r in records)
        assert identity(frame_dir/"SCENARIO_MANIFEST.json")==batch["scenario_manifest"]
        manifest=read(frame_dir/"SCENARIO_MANIFEST.json")
        assert manifest["service_instance"]==batch["instance"] and manifest["tier"]==batch["tier"]
        labels={x["event_id"]:x for x in manifest["events"]}
        assert len(labels)==manifest["event_count"]==len(records)
        assert labels.keys()=={r["scenario_id"] for r in records}
        for r in records:
            named=labels[r["scenario_id"]]
            assert all(named[k]==r[k] for k in ("scenario","client","peer","request_index","normal",
                                                 "connect_start_ns","start_ns","done_ns","observed_status"))
        assert len(records)==batch["requests"]==batch["connections"]==200
    cap=read(frame_dir/"CAPTURE.json")
    aligned=read(frame_dir/"PACKET_ACCEPTANCE.json")
    assert not cap["capture"]["capture_kernel_drops"] and aligned["status"]=="PASS"
    assert aligned["checks"]["aligned_requests"]==len(records)
    data=dataset(batch["batch"],q,records,normal,batch["connections"])
    data.update(instance=batch["instance"],start_ns=batch["start_ns"],end_ns=batch["end_ns"],
                endpoints=cap["endpoints"],port=cap["server_port"])
    return data


def combine(parts,name):
    offset=0
    used=set()
    streams=[]
    for row in parts:
        assert not used.intersection(row["uid"])
        used.update(row["uid"])
        key,index=np.unique(row["stream"],return_inverse=True)
        streams.append(index+offset)
        offset+=len(key)
    assert all(x["normal"] is parts[0]["normal"] for x in parts)
    return dict(name=name,uid=np.concatenate([x["uid"] for x in parts]),stream=np.concatenate(streams),
                score=np.concatenate([x["score"] for x in parts],axis=1),
                h=np.concatenate([x["h"] for x in parts]),normal=parts[0]["normal"])


def subset(row,mask,name):
    return dict(row,name=name,uid=row["uid"][mask],stream=row["stream"][mask],h=row["h"][mask],score=row["score"][:,mask,:])


def reduced(data,unit="connection"):
    if unit=="POST":
        return data["h"],data["score"]
    keys,index=np.unique(data["stream"],return_inverse=True)
    h=np.zeros(len(keys),dtype=np.int64)
    np.maximum.at(h,index,data["h"])
    return h,connection_scores(data["score"],data["stream"])


def fifth_highest(x,axis):
    assert x.shape[axis]==1000
    return np.take(np.partition(x,995,axis=axis),995,axis=axis)


def from_previous(item,stored):
    return dataset(item["name"],stored,item["rows"],True,item["connections"])


def trial_identity(data,first,seal_ns,instances):
    assert data["start_ns"]>seal_ns and data["start_ns"]<data["end_ns"] and data["instance"] not in instances
    assert [[r["ip"],r["mac"]] for r in data["endpoints"]]==first["endpoints"] and data["port"]==first["server_port"]
    instances.add(data["instance"])


def run(login,out):
    rank=login/RANK_RUN
    attack=login/ATTACK_RUN
    pin,old_cal,older_parts,_,_,old=old_data(rank)
    rank_files,rank_receipt=verified_archive(rank)
    attack_files,attack_receipt=verified_archive(attack)
    assert rank_receipt["thresholds"]==attack_receipt["rank5_thresholds"]==identity(rank/"THRESHOLDS.json")
    assert attack_receipt["reference"]==rank_receipt["reference"]==pin["reference"]
    qualification=read(attack/"ATTACK_QUALIFICATION.json")
    assert qualification["status"]=="PASS"
    assert qualification["target"]==f"{pin['endpoints'][0][0]}:{pin['server_port']}/login"
    older_cal=from_previous(old_cal,get_array(login/pin["previous"]/"calibration/SCORES.npz"))
    previous=[from_previous(older_parts[0],get_array(login/pin["previous"]/"holdout/SCORES.npz"))]
    extension=login/pin["fixed_comparator"]
    for info,row in zip(read(extension/"ACCEPTANCE.json")["batches"],older_parts[1:],strict=True):
        previous.append(from_previous(row,get_array((extension/info["receipt"]).parent/"SCORES.npz")))
    formal=login/pin["reference_archive"]
    base_rows,base_cache=saved_formal(formal)
    f=dataset("early_formal",dict(base_cache,scores=base_cache["scores"][KEPT],arms=base_cache["arms"][KEPT]),
              base_rows,True,207)
    mask=np.array([r["scenario"]==BURST for r in base_rows])
    stress=subset(f,mask,"legal_reconnect_stress")
    early_daily=subset(f,~mask,"early_formal_daily")
    assert len(reduced(stress)[0])==51 and len(reduced(early_daily)[0])==156
    seal_ns=read(rank/"THRESHOLD_SEAL.json")["sealed_at_ns"]
    instances=set(pin["used_instances"])
    new_cal=[]
    new_holdout=[]
    for receipt in rank_receipt["batches"]:
        stage=receipt["path"].split("/")[0]
        if stage.startswith("calibration_"):
            d=read_batch(rank,receipt,rank_files,"calibration",True)
            trial_identity(d,pin,pin["first_after_ns"],instances)
            assert d["end_ns"]<seal_ns
            new_cal.append(d)
        elif stage.startswith("holdout_"):
            d=read_batch(rank,receipt,rank_files,"holdout",True)
            trial_identity(d,pin,seal_ns,instances)
            new_holdout.append(d)
    assert len(new_cal)==len(new_holdout)==4
    low=[]
    medium=[]
    for receipt in attack_receipt["batches"]:
        stage=receipt["path"].split("/")[0]
        if stage.startswith(("low_","medium_")):
            d=read_batch(attack,receipt,attack_files,"attack",False)
            trial_identity(d,pin,max(x["end_ns"] for x in new_holdout),instances)
            (low if stage.startswith("low_") else medium).append(d)
    assert [x["name"] for x in [*low,*medium]]==qualification["batches"]
    assert len(low)==len(medium)==3
    used=set()
    for x in [older_cal,*new_cal,*new_holdout,*previous,f,*low,*medium]:
        assert not used.intersection(x["uid"])
        used.update(x["uid"])
    cals=combine([older_cal,*new_cal],"calibration_rank5")
    hcal,scal=reduced(cals)
    assert len(hcal)==1000 and sum(len(reduced(x)[0]) for x in new_cal)==794
    h_cut=int(fifth_highest(hcal,axis=0))
    cuts=np.array(read(rank/"THRESHOLDS.json")["thresholds"])
    assert np.array_equal(fifth_highest(scal,axis=1),cuts)
    n_high,n_equal=int((hcal>h_cut).sum()),int((hcal==h_cut).sum())
    assert n_high<=4 and n_high+n_equal>=5
    threshold_rows=[dict(arm=a,head=h,threshold=cuts[i,j],source="frozen_rank5_1000",
                   calibration_n=1000,strictly_above=int((scal[i,:,j]>cuts[i,j]).sum()),
                   at_threshold=int((scal[i,:,j]==cuts[i,j]).sum()))
                   for i,a in enumerate(ARMS) for j,h in enumerate(HEADS)]
    threshold_rows.append(dict(arm="handshake_only",head="one_rule",threshold=h_cut,source="fresh_rank5_same_1000",
                               calibration_n=1000,strictly_above=n_high,at_threshold=n_equal))
    table(out/"WSL_THRESHOLDS.csv",threshold_rows)

    hold=combine(new_holdout,"new_daily")
    low_all=combine(low,"low_attack")
    med_all=combine(medium,"medium_attack")
    cohorts=[hold,stress,low_all,med_all]
    assert [len(reduced(x)[0]) for x in cohorts]==[1000,51,600,600]
    counts=[]
    for raw in [*cohorts,*new_holdout,*low,*medium]:
        hs,ss=reduced(raw)
        flags=np.column_stack((ss[:,:,3].T>cuts[:,3],hs>h_cut))
        for i,arm in enumerate(ARM_LABELS):
            counts.append(dict(cohort=raw["name"],unit="connection",arm=arm,
                metric="false_positives" if raw["normal"] else "detections",n=int(flags[:,i].sum()),
                denominator=len(hs),rate=float(flags[:,i].mean()),
                threshold=h_cut if i==3 else cuts[i,3]))
    saved=read_counts(attack/"DAILY_AND_ATTACK_COMPLETE.csv")
    for row in counts:
        if row["cohort"] in saved and row["arm"] in saved[row["cohort"]]:
            assert row["n"]==saved[row["cohort"]][row["arm"]]
    table(out/"WSL_H60_FOUR_ARMS.csv",counts)

    cond=[]
    for unit in ("connection","POST"):
        for legit in (hold,stress):
            for anomalous in (low_all,med_all):
                lh,ls=reduced(legit,unit)
                ah,aps=reduced(anomalous,unit)
                lp=np.column_stack((ls[:,:,3].T>cuts[:,3],lh>h_cut))
                ap=np.column_stack((aps[:,:,3].T>cuts[:,3],ah>h_cut))
                for freq in sorted(set(lh)&set(ah)):
                    l,a=lh==freq,ah==freq
                    for i,arm in enumerate(ARM_LABELS):
                        cond.append(dict(unit=unit,normal_cohort=legit["name"],attack_cohort=anomalous["name"],
                            h60=int(freq),arm=arm,normal_fp=int(lp[l,i].sum()),normal_n=int(l.sum()),
                            normal_rate=float(lp[l,i].mean()),attack_tp=int(ap[a,i].sum()),
                            attack_n=int(a.sum()),attack_rate=float(ap[a,i].mean())))
    assert cond
    table(out/"WSL_MATCHED_H60.csv",cond)

    archived=combine(previous,"archived_daily_total")
    defined=[("CIC_source",np.broadcast_to(pin["old_cic_cuts"],(3,4))),
             ("local_206",old),("local_rank5_1000",cuts)]
    timeline=[]
    sections=[(f,"early_207_includes_stress"),(early_daily,"early_daily_only"),(stress,"separate_stress")]
    sections.extend((x,"heldout_daily") for x in [*previous,archived,*new_holdout,hold])
    for raw,group in sections:
        _,ss=reduced(raw)
        for threshold,values in defined:
            for i,a in enumerate(ARMS):
                for j,h in enumerate(HEADS):
                    for unit,source in (("connection",ss),("POST",raw["score"])):
                        alerts=source[i,:,j]>values[i,j]
                        timeline.append(dict(batch=raw["name"],scope=group,threshold_source=threshold,arm=a,head=h,
                                             threshold=values[i,j],unit=unit,n=int(alerts.sum()),
                                             denominator=len(alerts),rate=float(alerts.mean())))
    table(out/"WSL_THRESHOLD_HISTORY.csv",timeline)
    save(out/"WSL_REPLAY.json",dict(status="PASS",rank_manifest=identity(rank/"SHA256SUMS"),
        checked_rank_files=len(rank_files),attack_manifest=identity(attack/"SHA256SUMS"),
        checked_attack_files=len(attack_files),formal_inputs=pin,rank5=identity(rank/"THRESHOLDS.json"),
        comparison="strict greater-than",h_score="maximum over the same connection's admitted login POSTs",
        h_cut=h_cut,h_calibration_n=len(hcal),h_calibration_above=n_high,h_calibration_equal=n_equal,
        denom={x["name"]:len(reduced(x)[0]) for x in cohorts},
        h_ranges={x["name"]:[int(reduced(x)[0].min()),int(reduced(x)[0].max())] for x in cohorts},
        attack_labels=identity(attack/"ATTACK_QUALIFICATION.json"),
        ordinary_fixed_source_check=pin["old_cic_cuts"],early_formal_scope=207))
    print("WSL replay PASS",h_cut,n_high,n_equal)


def read_counts(path):
    groups={"new_daily":"daily_fp","legal_reconnect_stress":"stress_fp","low_attack":"low_rate_detected",
            "medium_attack":"medium_rate_detected"}
    with path.open(encoding="utf8") as file:
        rows={r["arm"]:r for r in csv.DictReader(file) if r["threshold"]=="新 1,000 条"}
    assert set(rows)==set(ARMS)
    return {k:{a:int(r[v]) for a,r in rows.items()} for k,v in groups.items()}


if __name__=="__main__":
    output=Path(sys.argv[2])
    output.mkdir(parents=True,exist_ok=True)
    run(Path(sys.argv[1]),output)
