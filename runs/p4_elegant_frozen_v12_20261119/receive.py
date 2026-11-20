"""Verify the five permitted classes of small results over the user's existing tunnel."""
from pathlib import Path
from transport import channel,HERE
from metrics import SMALL,validate_files
from seal import check,read


def receive(c,remote,manifest):
    files=manifest["files"];failure=remote["chain"]["stage"]=="STOP"
    check(set(files)==({"ACCEPTANCE.json"} if failure else SMALL),"RETURN_ALLOWLIST")
    dst=HERE/"received";check(dst.resolve().drive.upper()=="D:","RETURN_DRIVE")
    dst.mkdir(exist_ok=True)
    for n,s in files.items():
        check(n==Path(n).name==s["file"] and 0<s["bytes"]<2*1024**2,"FILE_SCOPE")
        path=dst/n
        if not path.is_file() or channel.digest(path)!=s["sha256"] or path.stat().st_size!=s["bytes"]:
            c.request("file-dual-"+n,destination=(path,s),timeout=90)
        check(channel.digest(path)==s["sha256"] and path.stat().st_size==s["bytes"],"RETURN_SHA:"+n)
    channel.save(dst/"SHA256.json",manifest)
    a=read(dst/"ACCEPTANCE.json")
    check(a==remote["acceptance"] and a["run"]==HERE.name,"RETURN_RUN_ID")
    if failure:
        channel.state("STOP",error=a["error"],remote=remote);return
    checks=validate_files(dst)
    truth=read(HERE/"INPUT_SEAL.json")
    check(a["status"]=="PASS" and a["checks"]==checks and a["package_sha256"]==channel.digest(HERE/"PACKAGE_MANIFEST.json")
          and a["input_sha256"]==channel.digest(HERE/"INPUT_SEAL.json") and a["physical_query_orders"]==truth["query_orders"],"LOCAL_ACCEPTANCE")
    check(a["outputs"]=={n:s for n,s in files.items() if n.endswith(".csv")} and a["phases"]["formal"]["query_order"]==truth["all_query_order"]
          and a["phases"]["formal"]["reference_order"]==truth["reference_order"],"OUTPUT_BINDING")
    import csv
    with (dst/"UID_CONSISTENCY.csv").open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            group=row["group"]
            if group in truth["query_orders"]:check(row["uid_order_sha256"]==truth["query_orders"][group],"TABLE_UID_ORDER")
            if group=="all":check(row["uid_order_sha256"]==truth["all_query_order"],"ALL_UIDS")
    check(all(v["state"]=="COMPLETED" and v["exit"]=="0:0" and v["job_id"]==a["jobs"][p] for p,v in a["scheduler"].items()),"SCHEDULER_RETURN")
    channel.save(dst/"LOCAL_ACCEPTANCE.json",dict(status="PASS",jobs=a["jobs"],sha256_manifest=channel.digest(dst/"SHA256.json"),
                  verified_files=files,checks=checks))
    channel.state("ACCEPTED",remote=remote,local_files=len(files))
    from archive_elegant import publish
    try:
        commit=publish("results")
        channel.state("ACCEPTED",remote=remote,local_files=len(files),backup={"status":"PUSHED","commit":commit})
    except Exception as exc:
        channel.state("ACCEPTED",remote=remote,local_files=len(files),backup={"status":"PENDING","error":str(exc)})


if __name__=="__main__":
    channel.receive=receive
    try:
        check(channel.digest(HERE/".private/package.tar.gz")==read(HERE/"LOCAL_VALIDATION.json")["archive_sha256"],"VALIDATED_BUNDLE")
        channel.watch()
    except Exception as e:
        channel.state("LOCAL_STOP",error=str(e));raise
