"""Retain only the compressed publisher member in the local external-data cache."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
from zipfile import ZipFile
import requests

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/"p4_edge_password_connection_count_20261120"))
import count_connections as previous


def asset_path():
    return Path(os.environ["LOCALAPPDATA"])/"Paper04"/"datasets"/"Edge-IIoTset"/"password-v5.zip"


def prepare():
    path=asset_path()
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.is_file():
        headers={"Range":f"bytes=0-{previous.ZIP_BYTES-1}","User-Agent":"kaggle-api-v1.7.4"}
        with requests.get(previous.URL,headers=headers,stream=True,timeout=(15,90)) as response:
            response.raise_for_status()
            if response.status_code==206:
                assert response.headers["Content-Range"]==f"bytes 0-{previous.ZIP_BYTES-1}/{previous.ZIP_BYTES}"
            tmp=path.with_suffix(".part")
            with tmp.open("wb") as f:
                for block in response.iter_content(1024**2):
                    f.write(block)
                    assert f.tell()<=previous.ZIP_BYTES
            assert tmp.stat().st_size==previous.ZIP_BYTES
            tmp.replace(path)
    assert path.stat().st_size==previous.ZIP_BYTES
    a=json.loads((previous.ROOT/"COUNT.json").read_bytes())
    with ZipFile(path) as z:
        member,=z.infolist()
        assert member.file_size==a["pcap_bytes"]
        data=z.read(member)
    assert hashlib.sha256(data).hexdigest()==a["pcap_sha256"]
    confirmed={}
    check=previous.count(data,json.loads(previous.SAMPLE.read_bytes()),on_confirmed=confirmed.update)
    assert check==a
    lines="post_frame,tcp_stream\n"+"".join(f"{frame},{stream}\n" for frame,stream in sorted(confirmed.items()))
    (HERE/"EDGE_POSTS.csv").write_bytes(lines.encode("ascii"))
    pin=dict(bytes=path.stat().st_size,sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
             pcap_sha256=a["pcap_sha256"],pcap_bytes=a["pcap_bytes"],connections=len(set(confirmed.values())))
    (HERE/"EDGE_ASSET.json").write_text(json.dumps(pin,indent=2)+"\n",encoding="utf8")
    print("Edge connection bindings verified",pin["connections"])


if __name__=="__main__":
    prepare()
