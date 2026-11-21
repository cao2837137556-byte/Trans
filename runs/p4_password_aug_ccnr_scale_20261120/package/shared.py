"""Integrity and table primitives for the frozen-score replay."""
import csv
import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = "p4_password_aug_v1_20261120_r1"
MODELS = ("v12", "r1")
HEADS = ("27", "127", "227", "ensemble")
ARMS = ("original", "self_span", "standardized")


def read(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(4 << 20), b""):
            h.update(block)
    return h.hexdigest()


def artifact(path):
    return dict(file=path.name, bytes=path.stat().st_size, sha256=sha(path))


def check(path, spec):
    assert path.stat().st_size == spec["bytes"] and sha(path) == spec["sha256"], str(path)
    return path


def write(path, obj):
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    temp.write_bytes((json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False)+"\n").encode())
    temp.replace(path)


def table(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(path, rows):
    assert rows, path
    with path.open("w", encoding="utf8", newline="") as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def uid_sha(ids):
    return hashlib.sha256("".join(str(u)+"\n" for u in ids).encode()).hexdigest()
