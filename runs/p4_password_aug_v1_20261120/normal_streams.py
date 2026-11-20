"""Bind the previously sampled Edge normal frames to capture-level TCP/UDP streams."""
import json
from pathlib import Path
import subprocess
import numpy as np
from auxiliary import sha

HERE=Path(__file__).resolve().parent


if __name__=="__main__":
    audit=HERE.parent/"edge_iiotset_raw_qualification_v1_20261102"
    root=Path(json.loads((audit/"APPROVED_CARD.json").read_bytes())["prospective_destination"])
    p=root/"Temperature_and_Humidity.pcap"
    pin=json.loads((audit/"TRANSFER_3.json").read_bytes())["raw_sha256"]
    assert sha(p)==pin
    args=["C:/Program Files/Wireshark/tshark.exe","-n","-r",str(p),"-T","fields","-E","occurrence=f",
          "-e","frame.number","-e","tcp.stream","-e","udp.stream"]
    values=[0]
    with subprocess.Popen(args,stdout=subprocess.PIPE) as child:
        for line in child.stdout:
            f,t,u=line.rstrip(b"\r\n").split(b"\t")
            assert int(f)==len(values)
            values.append(1+int(t) if t else -(1+int(u)) if u else 0)
        assert child.wait()==0
    assert len(values)==1_629_749+1
    np.savez_compressed(HERE/".private/normal_streams.npz",source_sha=pin,stream=np.array(values,dtype=np.int32))
