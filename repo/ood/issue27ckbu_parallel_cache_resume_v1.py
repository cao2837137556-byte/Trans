#!/usr/bin/env python3
"""Parallel, resumable execution wrapper for the frozen CKBU frontend.

This module changes execution only.  It never reads labels, changes target
plans, or changes feature/model code.  A predecessor cache is reused only
after its metadata, SHA-256, target coverage, and NPZ schema all validate.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
from types import SimpleNamespace
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Sequence

import numpy as np


FEATURE_DIM = 51
STATUS_BY_KIND = {
    "gotham": "CKBU_GOTHAM_SOURCE_COMPLETE",
    "auxiliary": "CKBU_AUXILIARY_SOURCE_COMPLETE",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_plan(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError(f"empty source plan: {path}")
    return rows


def cache_paths(cache_dir: Path, key: str) -> tuple[Path, Path]:
    return cache_dir / f"{key}.npz", cache_dir / f"{key}.json"


def validate_pair(kind: str, row: dict[str, str], cache_dir: Path) -> tuple[bool, str]:
    key = str(row["source_cache_key"])
    source = str(row["source_group"])
    expected_rows = int(row["target_rows"])
    npz, meta = cache_paths(cache_dir, key)
    if not npz.is_file() or not meta.is_file():
        return False, "missing_pair"
    try:
        summary = json.loads(meta.read_text(encoding="utf-8"))
        if summary.get("status") != STATUS_BY_KIND[kind]:
            return False, "status"
        if str(summary.get("source_group")) != source:
            return False, "source"
        if str(summary.get("source_cache_key")) != key:
            return False, "key"
        if int(summary.get("target_rows", -1)) != expected_rows:
            return False, "target_rows"
        if not bool(summary.get("target_positions_complete")):
            return False, "target_positions"
        if bool(summary.get("raw_label_column_read", True)):
            return False, "raw_label"
        if str(summary.get("cache_sha256")) != sha256_file(npz):
            return False, "sha256"
        with np.load(npz, allow_pickle=False) as values:
            shape = tuple(values["causal_features"].shape)
            names = values["feature_names"].astype(str).tolist()
        if shape != (expected_rows, FEATURE_DIM) or len(names) != FEATURE_DIM:
            return False, f"schema:{shape}:{len(names)}"
    except Exception as exc:  # a partial/corrupt cache must never be reused
        return False, f"exception:{type(exc).__name__}"
    return True, "valid"


def atomic_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.copy-{os.getpid()}")
    shutil.copy2(source, temporary)
    os.replace(temporary, target)


def reuse_valid_pairs(
    kind: str,
    plan: list[dict[str, str]],
    cache_dir: Path,
    reuse_dirs: Sequence[Path],
) -> list[dict[str, Any]]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    audit: list[dict[str, Any]] = []
    for row in plan:
        key = str(row["source_cache_key"])
        valid, reason = validate_pair(kind, row, cache_dir)
        if valid:
            audit.append(
                {
                    "source_group": row["source_group"],
                    "source_cache_key": key,
                    "reused": True,
                    "reused_from": str(cache_dir),
                    "reason": "already_valid_destination",
                }
            )
            continue
        if reason != "missing_pair":
            raise RuntimeError(
                f"invalid destination cache must not be overwritten: {row['source_group']}: {reason}"
            )
        copied = False
        last_reason = "no_predecessor"
        for predecessor in reuse_dirs:
            valid, last_reason = validate_pair(kind, row, predecessor)
            if not valid:
                continue
            source_npz, source_meta = cache_paths(predecessor, key)
            target_npz, target_meta = cache_paths(cache_dir, key)
            atomic_copy(source_npz, target_npz)
            summary = json.loads(source_meta.read_text(encoding="utf-8"))
            summary["cache_npz"] = str(target_npz)
            summary["reused_from"] = str(predecessor)
            temporary = target_meta.with_name(f".{target_meta.name}.copy-{os.getpid()}")
            temporary.write_text(
                json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            os.replace(temporary, target_meta)
            valid, last_reason = validate_pair(kind, row, cache_dir)
            if not valid:
                raise RuntimeError(
                    f"copied cache failed destination validation: {row['source_group']}: {last_reason}"
                )
            copied = True
            audit.append(
                {
                    "source_group": row["source_group"],
                    "source_cache_key": key,
                    "reused": True,
                    "reused_from": str(predecessor),
                    "reason": "validated_predecessor_copy",
                }
            )
            break
        if not copied:
            audit.append(
                {
                    "source_group": row["source_group"],
                    "source_cache_key": key,
                    "reused": False,
                    "reused_from": "",
                    "reason": last_reason,
                }
            )
    return audit


def task_bytes(kind: str, row: dict[str, str], archive: zipfile.ZipFile) -> int:
    if kind == "gotham":
        members = json.loads(row["pcap_members_json"])
        return sum(archive.getinfo(str(member)).file_size for member in members)
    return archive.getinfo(str(row["raw_source_path"])).file_size


def build_command(args: argparse.Namespace, kind: str, index: int) -> list[str]:
    worker_out = args.worker_out if args.worker_out is not None else args.out
    command = [
        sys.executable,
        str(args.frontend),
        "--mode",
        "materialize-gotham-source" if kind == "gotham" else "materialize-auxiliary-source",
        "--out",
        str(worker_out),
        "--gotham-zip",
        str(args.gotham_zip),
        "--source-plan",
        str(args.source_plan),
        "--source-index",
        str(index),
        "--cache-dir",
        str(args.cache_dir),
        "--tshark",
        str(args.tshark),
    ]
    if kind == "gotham":
        for target in args.targets:
            command.extend(["--targets", str(target)])
    return command


def run_one(
    args: argparse.Namespace, kind: str, index: int, row: dict[str, str], size: int
) -> dict[str, Any]:
    key = str(row["source_cache_key"])
    logs = Path(args.out) / "parallel_source_logs"
    logs.mkdir(parents=True, exist_ok=True)
    stdout_path = logs / f"{kind}_{index:03d}_{key}.out"
    stderr_path = logs / f"{kind}_{index:03d}_{key}.err"
    started = time.time()
    environment = dict(os.environ)
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[name] = "1"
    with stdout_path.open("w", encoding="utf-8") as stdout, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr:
        result = subprocess.run(
            build_command(args, kind, index),
            stdout=stdout,
            stderr=stderr,
            env=environment,
            check=False,
        )
    valid, reason = validate_pair(kind, row, Path(args.cache_dir))
    if result.returncode != 0 or not valid:
        tail = stderr_path.read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(
            f"{kind} source failed index={index} source={row['source_group']} "
            f"returncode={result.returncode} cache={reason}\n{tail}"
        )
    return {
        "index": index,
        "source_group": row["source_group"],
        "source_cache_key": key,
        "pcap_bytes": size,
        "seconds": time.time() - started,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"refusing empty CSV: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_parallel(args: argparse.Namespace, kind: str) -> None:
    started = time.time()
    plan = read_plan(Path(args.source_plan))
    reuse_dirs = [Path(path) for path in args.reuse_cache_dir if Path(path).is_dir()]
    audit = reuse_valid_pairs(kind, plan, Path(args.cache_dir), reuse_dirs)
    reused = sum(bool(row["reused"]) for row in audit)
    with zipfile.ZipFile(Path(args.gotham_zip)) as archive:
        pending = [
            (task_bytes(kind, row, archive), index, row)
            for index, row in enumerate(plan)
            if not validate_pair(kind, row, Path(args.cache_dir))[0]
        ]
    pending.sort(key=lambda item: (-item[0], item[1]))
    print(
        f"CKBU_PARALLEL_START kind={kind} sources={len(plan)} reused={reused} "
        f"pending={len(pending)} workers={args.max_workers}",
        flush=True,
    )
    results: list[dict[str, Any]] = []
    failures: list[str] = []
    with ThreadPoolExecutor(max_workers=int(args.max_workers)) as pool:
        futures = {
            pool.submit(run_one, args, kind, index, row, size): (index, row)
            for size, index, row in pending
        }
        for future in as_completed(futures):
            index, row = futures[future]
            try:
                result = future.result()
                results.append(result)
                print(
                    f"CKBU_PARALLEL_SOURCE_COMPLETE kind={kind} index={index} "
                    f"source={row['source_group']} seconds={result['seconds']:.3f}",
                    flush=True,
                )
            except Exception as exc:
                failures.append(str(exc))
                print(f"CKBU_PARALLEL_SOURCE_FAILED {exc}", file=sys.stderr, flush=True)
    if failures:
        raise RuntimeError("; ".join(failures))
    invalid = [
        f"{row['source_group']}:{validate_pair(kind, row, Path(args.cache_dir))[1]}"
        for row in plan
        if not validate_pair(kind, row, Path(args.cache_dir))[0]
    ]
    if invalid:
        raise RuntimeError(f"parallel stage incomplete: {invalid}")
    out = Path(args.out)
    write_csv(out / f"ckbu_{kind}_parallel_reuse_audit.csv", audit)
    if results:
        write_csv(out / f"ckbu_{kind}_parallel_runtime.csv", sorted(results, key=lambda r: r["index"]))
    summary = {
        "status": f"CKBU_{kind.upper()}_PARALLEL_COMPLETE",
        "kind": kind,
        "sources": len(plan),
        "reused_sources": reused,
        "materialized_sources": len(results),
        "workers": int(args.max_workers),
        "largest_first": True,
        "seconds": time.time() - started,
        "scientific_protocol_changed": False,
    }
    (out / f"ckbu_{kind}_parallel_ready.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2, sort_keys=True), flush=True)


def unit_tests() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        cache = root / "cache"
        cache.mkdir()
        source = "processed/test.csv"
        key = "abc"
        row = {"source_group": source, "source_cache_key": key, "target_rows": "2"}
        npz, meta = cache_paths(cache, key)
        np.savez_compressed(
            npz,
            causal_features=np.zeros((2, FEATURE_DIM), dtype=np.float32),
            feature_names=np.asarray([f"f{i}" for i in range(FEATURE_DIM)]),
        )
        meta.write_text(
            json.dumps(
                {
                    "status": STATUS_BY_KIND["gotham"],
                    "source_group": source,
                    "source_cache_key": key,
                    "target_rows": 2,
                    "target_positions_complete": True,
                    "raw_label_column_read": False,
                    "cache_sha256": sha256_file(npz),
                }
            ),
            encoding="utf-8",
        )
        valid, reason = validate_pair("gotham", row, cache)
        if not valid:
            raise RuntimeError(f"valid synthetic cache rejected: {reason}")
        summary = json.loads(meta.read_text(encoding="utf-8"))
        summary["raw_label_column_read"] = True
        meta.write_text(json.dumps(summary), encoding="utf-8")
        valid, _ = validate_pair("gotham", row, cache)
        if valid:
            raise RuntimeError("raw-label cache accepted")
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        archive_path = root / "tiny.zip"
        with zipfile.ZipFile(archive_path, "w") as archive:
            archive.writestr("a.pcap", b"a" * 100)
            archive.writestr("b.pcap", b"b" * 200)
        plan_path = root / "plan.csv"
        plan_rows = [
            {
                "source_group": f"processed/source-{index}.csv",
                "source_cache_key": f"k{index}",
                "target_rows": "2",
                "pcap_members_json": json.dumps([member]),
            }
            for index, member in enumerate(("a.pcap", "b.pcap"))
        ]
        write_csv(plan_path, plan_rows)
        fake = root / "fake_frontend.py"
        fake.write_text(
            textwrap.dedent(
                f"""
                import argparse, csv, hashlib, json
                from pathlib import Path
                import numpy as np
                p=argparse.ArgumentParser()
                for name in ('mode','out','gotham_zip','source_plan','source_index','cache_dir','tshark'):
                    p.add_argument('--'+name.replace('_','-'))
                p.add_argument('--targets', action='append', default=[])
                a=p.parse_args(); rows=list(csv.DictReader(open(a.source_plan, encoding='utf-8')))
                row=rows[int(a.source_index)]; cache=Path(a.cache_dir); cache.mkdir(parents=True,exist_ok=True)
                npz=cache/(row['source_cache_key']+'.npz')
                np.savez_compressed(npz, causal_features=np.zeros((2,{FEATURE_DIM}),dtype=np.float32),
                    feature_names=np.asarray(['f'+str(i) for i in range({FEATURE_DIM})]))
                h=hashlib.sha256(npz.read_bytes()).hexdigest()
                meta={{'status':'CKBU_GOTHAM_SOURCE_COMPLETE','source_group':row['source_group'],
                    'source_cache_key':row['source_cache_key'],'target_rows':2,
                    'target_positions_complete':True,'raw_label_column_read':False,'cache_sha256':h}}
                (cache/(row['source_cache_key']+'.json')).write_text(json.dumps(meta),encoding='utf-8')
                """
            ),
            encoding="utf-8",
        )
        args = SimpleNamespace(
            frontend=fake,
            out=root / "out",
            worker_out=root / "workers",
            gotham_zip=archive_path,
            source_plan=plan_path,
            cache_dir=root / "destination",
            reuse_cache_dir=[],
            targets=["targets.csv"],
            tshark="unused",
            max_workers=2,
        )
        run_parallel(args, "gotham")
        if not (args.out / "ckbu_gotham_parallel_ready.json").is_file():
            raise RuntimeError("parallel subprocess regression did not finish")
    print(
        json.dumps(
            {
                "status": "CKBU_PARALLEL_CACHE_UNIT_PASS",
                "feature_dim": FEATURE_DIM,
                "validated_reuse_only": True,
                "largest_first": True,
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("unit", "run-gotham", "run-auxiliary"), default="unit")
    parser.add_argument("--frontend", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--worker-out", type=Path)
    parser.add_argument("--gotham-zip", type=Path)
    parser.add_argument("--source-plan", type=Path)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--reuse-cache-dir", action="append", default=[])
    parser.add_argument("--targets", action="append", default=[])
    parser.add_argument("--tshark", default="tshark")
    parser.add_argument("--max-workers", type=int, default=4)
    args = parser.parse_args()
    if args.mode == "unit":
        unit_tests()
        return
    for name in ("frontend", "out", "gotham_zip", "source_plan", "cache_dir"):
        if getattr(args, name) is None:
            raise RuntimeError(f"missing --{name.replace('_', '-')}")
    if args.max_workers < 1:
        raise RuntimeError("max workers must be positive")
    if args.mode == "run-gotham" and not args.targets:
        raise RuntimeError("Gotham run requires --targets")
    run_parallel(args, "gotham" if args.mode == "run-gotham" else "auxiliary")


if __name__ == "__main__":
    main()
