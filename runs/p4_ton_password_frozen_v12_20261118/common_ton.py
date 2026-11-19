"""Shared receipt and integrity primitives for the offline ToN diagnostic."""

import csv
import hashlib
import json
import os
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
RUN = "p4_ton_password_frozen_v12_20261118"
POOLS = ("normal1", "normal2", "password")
NS = 10**9
LAYERS = ("all", "off_bypass", "off_bypass_with_transport_data")
HEADS = ("27", "127", "227", "ensemble")


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def uid_hash(ids):
    return hashlib.sha256("".join(v + "\n" for v in ids).encode()).hexdigest()


def read(path):
    return json.loads(Path(path).read_bytes().decode("utf-8-sig"))


def dump(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode())
    os.replace(tmp, path)


def artifact(path):
    path = Path(path)
    return dict(file=path.name, bytes=path.stat().st_size, sha256=sha(path))


def csv_table(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


class Progress:
    def __init__(self, folder, phase):
        self.folder = Path(folder)
        self.phase = phase
        self.start = time.monotonic()
        self.last = 0.0
        self.stage = ""
        self.job = os.environ.get("SLURM_JOB_ID")

    def __call__(self, stage, done=0, total=1, *, force=False, **details):
        t = time.monotonic()
        if self.stage == stage and not force and t - self.last < 4:
            return
        self.stage = stage
        self.last = t
        dump(
            self.folder / "PROGRESS.json",
            dict(
                stage=stage,
                phase=self.phase,
                job=self.job,
                done=int(done),
                total=int(total),
                elapsed_seconds=t - self.start,
                updated_unix=time.time(),
                **details,
            ),
        )
