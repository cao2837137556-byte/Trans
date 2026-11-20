"""Verify genuine input prefixes and frame bindings locally without model inference."""
import csv
import gzip
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
from zipfile import ZipFile

from auxiliary import sha
from snapshot_gotham import snapshots, nanos

HERE = Path(__file__).resolve().parent


def main():
    private = HERE / ".private"
    exe = "C:/Program Files/Wireshark/tshark.exe"
    source = json.loads((HERE / "GOTHAM_SNAPSHOTS.json").read_bytes())
    pilot, = [s for s in source if "raw/benign/iotsim-air-quality-1_" in s["member"]]
    with (HERE / "GOTHAM_CONNECTIONS.csv").open(newline="") as f:
        anchors = {int(r["frame"]):r for r in csv.DictReader(f) if r["member"]==pilot["member"]}
    with gzip.open(private / pilot["file"], "rt") as f:
        expected = [json.loads(line) for line in f]
    pin = json.loads((HERE / "EDGE_ASSET.json").read_bytes())
    asset = Path(os.environ["LOCALAPPDATA"]) / "Paper04/datasets/Edge-IIoTset/password-v5.zip"
    assert asset.stat().st_size == pin["bytes"] and sha(asset) == pin["sha256"]
    with (HERE / "EDGE_POSTS.csv").open(newline="") as f:
        posts = {int(r["post_frame"]):int(r["tcp_stream"]) for r in list(csv.DictReader(f))[:3]}
    with tempfile.TemporaryDirectory(dir=private) as folder:
        raw = Path(folder) / "pilot.pcap"
        gotham=HERE.parents[3]/"datasets/gotham2025/raw/GothamDataset2025.zip"
        with ZipFile(gotham) as archive, archive.open(pilot["member"]) as src, raw.open("wb") as out:
            shutil.copyfileobj(src, out)
        assert sha(raw) == pilot["raw_sha256"]
        observed = list(snapshots(raw,pilot["member"],anchors,pilot["raw_sha256"],exe))
        assert len(observed)==12 and json.loads(json.dumps(observed))==expected
        with ZipFile(asset) as archive, archive.open(archive.infolist()[0]) as src, raw.open("wb") as out:
            header=src.read(24)
            order="<" if header[:4] in (bytes.fromhex("d4c3b2a1"),bytes.fromhex("4d3cb2a1")) else ">"
            out.write(header)
            for _ in range(max(posts)):
                record=src.read(16)
                size=struct.unpack(order+"IIII",record)[2]
                packet=src.read(size)
                assert len(packet)==size
                out.write(record+packet)
        fields=("frame.number","frame.time_epoch","tcp.stream","eth.dst","ip.src","ip.dst","tcp.srcport","tcp.dstport")
        cmd=[exe,"-n","-r",str(raw),"-T","fields","-E","occurrence=f"]
        for name in fields: cmd.extend(["-e",name])
        ts = subprocess.run(cmd,check=True,capture_output=True,text=True).stdout
        bindings={}
        for line in ts.splitlines():
            frame,epoch,stream,mac,src,dst,sp,dp=line.split("\t")
            if int(frame) not in posts: continue
            assert int(stream)==posts[int(frame)] and mac=="dc:a6:32:fb:69:b5"
            bindings[int(frame)]=dict(target=dst,mac=mac,source=src,source_port=int(sp),target_port=int(dp),
                                      timestamp_ns=nanos(epoch),device=dst,connection=int(stream),label=1)
        excluded=[]
        samples=list(snapshots(raw,"edge-password-v5",bindings,pin["pcap_sha256"],exe,excluded=excluded))
        assert set(bindings)==set(posts) and len(samples)+len(excluded)==len(posts) and samples
    receipt=dict(status="PASS_LOCAL_FRONTEND",gotham_real_anchors=len(observed),gotham_pcap_sha256=pilot["raw_sha256"],
                 edge_metadata_anchors=len(posts),edge_admitted=len(samples),edge_excluded=excluded,
                 edge_scored=False,encoding_or_training_performed=False)
    local_check=private/"heldout_context_local.json"
    if local_check.is_file(): receipt["original_Windows10_inbound_contributions"]=json.loads(local_check.read_bytes())
    (HERE/"LOCAL_FRONTEND_AUDIT.json").write_bytes((json.dumps(receipt,indent=2)+"\n").encode())
    print(receipt["status"],len(observed),len(samples))


if __name__=="__main__":
    main()
