"""Bind the experiment to accepted inputs and audit available test material."""
import csv
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
FORMAL=HERE.parent/"p4_login_formal_v1_20261121"
PILOT=HERE.parent/"p4_login_pilot_v1_20261121"
sys.path[:0]=[str(FORMAL),str(PILOT)]
from audit import identity, read, save

ARMS=("RAW","v12_CCNR","relative_handshake")
HEADS=("27","127","227","ensemble")
SOURCE_ID="formal_20261122_402788"


def table(path,rows):
    assert rows
    with path.open("w",encoding="utf8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def check_seal(base):
    assert base.name==SOURCE_ID
    state=read(base/"RUN_STATUS.json")
    assert state["stage"]=="ACCEPTED" and state["hash_manifest"]==identity(base/"SHA256SUMS")
    manifest={}
    for line in (base/"SHA256SUMS").read_text("ascii").splitlines():
        sha,name=line.split("  ",1)
        p=(base/name).resolve()
        assert p.is_relative_to(base.resolve()) and name not in manifest
        assert identity(p)["sha256"]==sha
        manifest[name]=sha
    accepted=read(base/"ACCEPTANCE.json")
    ref=read(base/"BANK_READY.json")
    first=read(base/"enrollment/CAPTURE.json")
    final=read(base/"evaluation/CAPTURE.json")
    assert state["acceptance"]==identity(base/"ACCEPTANCE.json")
    assert accepted["status"]==ref["status"]=="PASS"
    assert ref["reference"]==identity(base/"enrollment/REFERENCE.npz")
    assert ref["reference_rows"]==4096 and ref["same_service_components"]==393
    assert first["service_instance"]==final["service_instance"]==ref["service_instance"]==accepted["service_instance"]
    assert read(base/"COLLECTION_DONE.json")["namespaces_released"]
    comparable=read(base/"EXECUTION.json")["method_files"]["collect_formal.py"]
    assert comparable==identity(FORMAL/"collect_formal.py")
    return ref, first, final, manifest


def check_attacks(out,base,first):
    edge=read(base/"frozen_quick_check_assets/ACCEPTANCE.json")
    assert edge["status"]=="PASS" and edge["scope"]=="SEALED_EDGE_PASSWORD_READBACK"
    dir_=base.parent
    existing=sorted(p.relative_to(dir_).as_posix() for p in dir_.glob("**/login.pcap"))
    covered={"pilot_20261121_025fdd","formal_20261121_fedb00","formal_20261122_2a4ee7",SOURCE_ID}
    def local_record(name):
        p=dir_/name
        folders=[p] if name.startswith("pilot_") else [p/"enrollment",p/"evaluation"]
        entries=[]
        for f in folders:
            seal=f/"PACKET_ACCEPTANCE.json"
            if seal.is_file():
                x=read(seal)
                entries.append(dict(file=seal.relative_to(dir_).as_posix(), rows=x["checks"]["aligned_requests"],
                                    status=x["status"], sha256=identity(seal)["sha256"]))
        return entries
    receipts=[x for n in sorted(covered) for x in local_record(n)]
    ton=HERE.parent/"p4_ton_password_frozen_v12_20261118/received/TARGET_IDENTITY.csv"
    proof=HERE.parent/"p4_ccnr_relative_handshake_v1_20261121/received/LOGIN_QUALIFICATION.md"
    assert ton.is_file() and proof.is_file()
    host=first["endpoints"][0]
    rows=[
        dict(record="WSL local login captures", endpoint=f"{host['ip']}:{first['server_port']}/login",
             request_connection_alignment="verified normal captures, including planned password corrections",
             independence="pilot and established batches tracked individually", disposition="NORMAL_ONLY"),
        dict(record="Edge password archive",endpoint="192.168.0.128:80/DVWA/login.php",
             request_connection_alignment="confirmed prior POST associations; frozen fixture has 29 rows",
             independence="publisher attack capture",disposition="DIFFERENT_ENDPOINT"),
        dict(record="ToN password archive",endpoint="ToN registered targets .152/.190/.195",
             request_connection_alignment="archived logical target and direction records",
             independence="publisher network captures",disposition="DIFFERENT_ENDPOINT"),
        dict(record="Gotham password archive",endpoint="Gotham Telnet targets",
             request_connection_alignment="prior paired source receipts",
             independence="publisher captures",disposition="DIFFERENT_AUTH_SERVICE"),
    ]
    table(out/"ATTACK_QUALIFICATION.csv",rows)
    verdict=dict(status="PENDING_ATTACK_EVALUATION",eligible_attacks=None,
                 target=f"{host['ip']}:{first['server_port']}/login",local_pcap_inventory=existing,
                 local_normal_receipts=receipts,known_local_capture_roots=sorted(covered),
                 other_local_paths=[p for p in existing if p.split("/")[0] not in covered],
                 previous_evidence=dict(edge=edge["source_sha256"],ton=identity(ton),same_service_review=identity(proof)),
                 criterion="same endpoint, independent capture, labels bound to request and connection")
    save(out/"ATTACK_QUALIFICATION.json",verdict)
    return verdict


def archived_pair(name):
    folder=HERE.parent/name/"received"
    local=read(folder/"LOCAL_ACCEPTANCE.json")
    returned=read(folder/"RETURN.json")
    assert local["status"]=="PASS" and local["return_sha256"]==identity(folder/"RETURN.json")["sha256"]
    def pin(n):
        proof=returned["files"][n]
        assert identity(folder/n)=={k:v for k,v in proof.items() if k in ("sha256","bytes")}
    for part in ("ACCEPTANCE.json","PAIRED.csv"):
        pin(part)
    assert read(folder/"ACCEPTANCE.json")["status"]=="PASS"
    with (folder/"PAIRED.csv").open(encoding="utf8",newline="") as stream:
        rows={(r["group"],r["seed"],r["arm"]):r for r in csv.DictReader(stream)}
    return rows,identity(folder/"PAIRED.csv")


def flood(out):
    first,rel=archived_pair("p4_ccnr_relative_handshake_v1_20261121")
    second,role=archived_pair("p4_ccnr_role_port_v1_20261121")
    groups=[f"{d}.{s}" for d in ("CIC_DEV","UNSW_DEV","EDGE") for s in ("flood.q","normal.q","normal.c")]
    groups+=["EDGE.HTTP.q","EDGE.UDP.q"]
    answer=[]
    for group in groups:
        for seed in HEADS:
            expected={a:second[group,seed,a] for a in ("RAW","v12")}
            for name in expected:
                row=first[group,seed,name]
                assert (row["total"],row["alarm"])==(expected[name]["total"],expected[name]["alert"])
            base=first[group,seed,"RAW"]
            cc=first[group,seed,"v12"]
            relrow=first[group,seed,"v12_H60"]
            assert cc["total"]==relrow["total"]==base["total"]
            assert int(cc["alarm"])<=int(relrow["alarm"])<=int(base["alarm"])
            for arm,row in zip(ARMS,(base,cc,relrow)):
                answer.append(dict(group=group,head=seed,arm=arm,unit=row["unit"],kind=row["kind"],
                                   denominator=int(row["total"]),alarm=int(row["alarm"]),
                                   rate=float(row["alarm"])/int(row["total"]),threshold_scope="CIC_source"))
    p=out/"ORIGINAL_FLOOD_CHECK.csv"
    table(p,answer)
    save(out/"FLOOD_CHECK.json",dict(status="PASS",source_scope="cross-checked accepted frozen original paired tables",
         checked_groups=groups,head_count=len(HEADS),relative_handshake_table=rel,independent_original_table=role,
         output=identity(p)))
