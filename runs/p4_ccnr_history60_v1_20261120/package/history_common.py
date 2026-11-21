"""Small integrity and receipt helpers for the frozen replay."""
from pathlib import Path
import json
import hashlib
import csv
import os
import time

HERE = Path(__file__).resolve().parent
RUN = "p4_ccnr_history60_v1_20261120"
TON = "p4_ton_password_frozen_v12_20261118"
SCALE = "p4_password_aug_v1_20261120_r4"
EDGE_PW = "p4_password_aug_v1_20261120_r1"
SOURCE = "device_context_training_v2_20261105"
HEADS = ("27", "127", "227", "ensemble")
HOSTS = ("192.168.1.152", "192.168.1.190", "192.168.1.195")
POOLS = ("CIC_DEV", "UNSW_DEV", "EDGE", "TON", "EDGE_PASSWORD")
NS = 10**9
WINDOW = 60 * NS


def remote_run(attempt):
    if type(attempt) is not int or not 0 <= attempt <= 4:
        raise ValueError("unknown deployment attempt")
    return RUN if not attempt else f"{RUN}_r{attempt}"


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(4 << 20), b""):
            h.update(b)
    return h.hexdigest()


def artifact(path):
    return dict(file=path.name, bytes=path.stat().st_size, sha256=sha(path))


def check(path, pin):
    if not path.is_file():
        raise FileNotFoundError(path)
    if ("bytes" in pin and path.stat().st_size != pin["bytes"]) or sha(path) != pin["sha256"]:
        raise ValueError(f"封存资产校验失败 {path}")
    return path


def uid_sha(ids):
    h = hashlib.sha256()
    for uid in ids:
        h.update((str(uid) + "\n").encode("ascii"))
    return h.hexdigest()


def write(path, obj):
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf8"))
    tmp.replace(path)


def save(path, rows):
    with path.open("w", encoding="utf8", newline="") as f:
        dw = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator="\n")
        dw.writeheader()
        dw.writerows(rows)


def progress(out, phase, description, **more):
    msg = dict(phase=phase, job_id=os.environ.get("SLURM_JOB_ID"),
               description=description, updated_unix=time.time(), **more)
    write(out / f"{phase}_PROGRESS.json", msg)
    write(out / "PROGRESS.json", msg)
