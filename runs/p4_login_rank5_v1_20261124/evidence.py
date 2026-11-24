"""Validate the archived comparator and bind one row to each scored POST."""
import csv
import json

import numpy as np

from protocol import CAL_CONNECTIONS, FIXED, OLD_CONNECTIONS, PRIOR, RANK, ROOT, SOURCE_ID, registration
from assessment import arrays, connection_scores, get_array, roster, saved_formal, KEPT
from frozen_score import digest_order
from schedule import BURST, RATES
from sources import ARMS, HEADS, check_seal, identity, read, save, table


def verified_archive(folder):
    stamp=read(folder/"RUN_STATUS.json")
    assert stamp["stage"]=="ACCEPTED" and stamp["acceptance"]==identity(folder/"ACCEPTANCE.json")
    assert stamp["hash_manifest"]==identity(folder/"SHA256SUMS")
    files={}
    for row in (folder/"SHA256SUMS").read_text("ascii").splitlines():
        sha,name=row.split("  ",1)
        path=(folder/name).resolve()
        assert path.is_relative_to(folder.resolve()) and name not in files and identity(path)["sha256"]==sha
        files[name]=sha
    answer=read(folder/"ACCEPTANCE.json")
    assert answer["status"]=="PASS"
    return files,answer


def aligned_rows(path):
    with path.open(encoding="utf8") as stream:
        records=[json.loads(line) for line in stream]
    answer=roster(records)
    assert len(answer)==len(records) and all(r["normal"] for r in answer)
    return answer


def scored(path,alignment,name,count):
    q=get_array(path)
    align=aligned_rows(alignment)
    uid,streams=arrays(align)
    assert len(uid)==len(set(uid)) and len(set(streams))==count
    assert np.array_equal(q["uid"],uid) and np.array_equal(q["stream"],streams)
    assert tuple(q["arms"])==ARMS and q["scores"].shape==(len(ARMS),len(uid),len(HEADS))
    assert np.isfinite(q["scores"]).all()
    return dict(name=name,uid=uid,stream=streams,scores=q["scores"],rows=align,connections=count)


def subset(data,mask,name):
    ids=data["stream"][mask]
    return dict(name=name,uid=data["uid"][mask],stream=ids,scores=data["scores"][:,mask,:],
                rows=[r for r,keep in zip(data["rows"],mask) if keep],connections=len(set(ids)))


def combine(items,name):
    offset=0
    ids=set()
    streams=[]
    for item in items:
        distinct,inverse=np.unique(item["stream"],return_inverse=True)
        assert len(distinct)==item["connections"] and not ids.intersection(item["uid"])
        ids.update(item["uid"])
        streams.append(inverse+offset)
        offset+=len(distinct)
    return dict(name=name,uid=np.concatenate([x["uid"] for x in items]),stream=np.concatenate(streams),
                scores=np.concatenate([x["scores"] for x in items],axis=1),
                rows=[r for x in items for r in x["rows"]],connections=offset)


def old_data(out):
    ref=out.parent/SOURCE_ID
    prior=out.parent/PRIOR
    fixed=out.parent/FIXED
    bank,first,final,ref_files=check_seal(ref)
    previous_files,previous=verified_archive(prior)
    fixed_files,ext=verified_archive(fixed)
    old=read(prior/"THRESHOLDS.json")
    assert ext["thresholds"]==identity(prior/"THRESHOLDS.json")==identity(fixed/"THRESHOLDS.json")
    assert old["calibration_connections"]==OLD_CONNECTIONS==206
    assert old["comparison"]=="strict_greater_than" and old["reference"]==bank["reference"]
    required={"THRESHOLDS.json","calibration/SCORES.npz","calibration/ALIGNMENT.jsonl","holdout/SCORES.npz",
              "holdout/ALIGNMENT.jsonl","ATTACK_QUALIFICATION.json","ATTACK_QUALIFICATION.csv"}
    assert required<=previous_files.keys()
    cal_path=prior/"calibration/SCORES.npz"
    cal=scored(cal_path,prior/"calibration/ALIGNMENT.jsonl","original_calibration",206)
    assert old["calibration_scores"]==identity(cal_path)
    assert old["calibration_uid_order"]==digest_order(cal["uid"])
    assert tuple(old["arms"])==ARMS and tuple(old["heads"])==HEADS
    cut=np.array(old["thresholds"])
    assert cut.shape==(len(ARMS),len(HEADS)) and np.isfinite(cut).all()
    maxes=connection_scores(cal["scores"],cal["stream"])
    assert np.array_equal((maxes>cut[:,None,:]).sum(1),np.array(old["calibration_fp"]))
    assert previous["holdout_connections"]==194 and ext["total_connections"]==1107
    hold=[scored(prior/"holdout/SCORES.npz",prior/"holdout/ALIGNMENT.jsonl","original_holdout",194)]
    endpoints=[[v["ip"],v["mac"]] for v in first["endpoints"]]
    latest=read(prior/"holdout/CAPTURE.json")["capture"]["end_ns"]
    instances={first["service_instance"],read(prior/"holdout/CAPTURE.json")["service_instance"]}
    paths={}
    for i,item in enumerate(ext["batches"],1):
        receipt=fixed/item["receipt"]
        assert fixed_files[item["receipt"]]==item["sha256"]==identity(receipt)["sha256"]
        folder=receipt.parent
        cap=read(folder/"holdout/CAPTURE.json")
        record=read(receipt)
        assert record["status"]=="PASS" and record["batch"]==i and record["connections"]==item["connections"]
        assert record["start_ns"]>latest+60*10**9 and record["capture_instance"] not in instances
        assert [[v["ip"],v["mac"]] for v in cap["endpoints"]]==endpoints
        instances.add(record["capture_instance"])
        latest=record["end_ns"]
        hold.append(scored(folder/"SCORES.npz",folder/"holdout/ALIGNMENT.jsonl",f"old_holdout_{i:02}",record["connections"]))
        paths[hold[-1]["name"]]=identity(folder/"SCORES.npz")
    all_hold=combine(hold,"old_daily")
    assert all_hold["connections"]==1107 and not set(cal["uid"])&set(all_hold["uid"])
    align,stored=saved_formal(ref)
    raw=dict(name="old_formal",uid=stored["uid"],stream=stored["stream"],
             rows=align,scores=stored["scores"][KEPT])
    stress=subset(raw,np.array([r["scenario"]==BURST for r in align]),"old_stress")
    assert stress["connections"]==len(stress["rows"])==51
    assert [sum(r["scheduled_rate"]==i for r in stress["rows"]) for i in RATES]==[3,9,15,24]
    assert not set(stress["uid"])&(set(cal["uid"])|set(all_hold["uid"]))
    assert all(row["confirmed"] and row["scheduled"]==row["actual"] for row in read(ref/"ACCEPTANCE.json")["minutes"])
    assert np.array_equal((connection_scores(all_hold["scores"],all_hold["stream"])>cut[:,None,:]).sum(1)[:,3],[22,22,22])
    assert np.array_equal((connection_scores(stress["scores"],stress["stream"])>cut[:,None,:]).sum(1)[:,3],[0,0,6])
    pin=dict(reference_archive=SOURCE_ID,previous=PRIOR,fixed_comparator=FIXED,reference=bank["reference"],
             reference_files=len(ref_files),previous_files=len(previous_files),fixed_files=len(fixed_files),
             previous_thresholds=identity(prior/"THRESHOLDS.json"),previous_calibration=identity(cal_path),
             previous_holdout=identity(prior/"holdout/SCORES.npz"),fixed_holdout=paths,
             stress_source=identity(ref/"evaluation/DECISIONS.npz"),old_cic_cuts=old["cic_cuts"],
             first_after_ns=max(latest,final["capture"]["end_ns"]),used_instances=sorted(instances),
             endpoints=endpoints,server_port=first["server_port"],kernel=first["kernel"])
    return pin,cal,hold,all_hold,stress,cut


def freeze(out,pin):
    contract=dict(**pin,old_count=OLD_CONNECTIONS,calibration_count=CAL_CONNECTIONS,rank=RANK,
                  batches=registration(),code={p.name:identity(p) for p in sorted(ROOT.glob("*.py"))},
                  protocol=identity(ROOT/"METHOD.md"))
    dest=out/"INPUTS.json"
    if dest.exists():
        assert read(dest)==contract
    else:
        save(dest,contract)
    for name,source in {"METHOD.md":ROOT/"METHOD.md",
                        "THRESHOLDS_206.json":out.parent/PRIOR/"THRESHOLDS.json"}.items():
        path=out/name
        if not path.exists():
            path.write_bytes(source.read_bytes())
        assert identity(path)==identity(source)
    return contract


def attack_inventory(out,pin):
    past=out.parent/PRIOR
    info=read(past/"ATTACK_QUALIFICATION.json")
    target=f"{pin['endpoints'][0][0]}:{pin['server_port']}/login"
    assert info["target"]==target and info["status"]=="PENDING_ATTACK_EVALUATION"
    known={*info["known_local_capture_roots"],PRIOR,FIXED,out.name}
    files=[p for p in out.parent.rglob("*") if p.is_file() and p.suffix.lower() in (".pcap",".pcapng",".cap")]
    names=sorted(p.relative_to(out.parent).as_posix() for p in files)
    remaining=[p for p in names if p.split("/")[0] not in known]
    external=out.parent.parent
    for p in external.rglob("*"):
        if p.is_file() and not p.is_relative_to(out.parent) and p.suffix.lower() in (".pcap",".pcapng",".cap"):
            path=p.relative_to(external).as_posix().lower()
            if ("same_service" in path or "login" in path) and ("attack" in path or "password" in path):
                remaining.append(p.relative_to(external).as_posix())
    with (past/"ATTACK_QUALIFICATION.csv").open(encoding="utf8") as stream:
        rows=list(csv.DictReader(stream))
    for path in sorted(set(remaining)):
        rows.append(dict(record=path,endpoint="UNVERIFIED",
                         request_connection_alignment="requires independent scenario labels and POST/stream binding",
                         independence="UNVERIFIED",disposition="PENDING_QUALIFICATION"))
    table(out/"ATTACK_QUALIFICATION.csv",rows)
    save(out/"ATTACK_QUALIFICATION.json",dict(status="PENDING_ATTACK_EVALUATION",target=target,
         eligibility="same endpoint, independent bidirectional capture, authoritative labels bound to POST and TCP stream",
         new_candidates=sorted(set(remaining)),inventory=names,earlier_qualification=identity(past/"ATTACK_QUALIFICATION.json"),
         requested_batches_at_least=3,requested_qualified_connections_per_registered_scenario=600,
         eligible_attack_connections=None))
