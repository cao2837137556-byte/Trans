"""Run independent WSL holdouts and score them under the accepted fixed policy."""

import argparse
from collections import defaultdict
import csv
import ctypes
import msvcrt
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

from design import CALIBRATION_ID, HERE, PRIOR_CONNECTIONS, SEEDS, TARGET_CONNECTIONS
from design import expected_connections, schedule
from assessment import arrays, collect_aligned, get_array, pairing, roster, scores_for
from controller import wsl
from frozen_score import sealed_runtime
from runner import state
from sources import ARMS, HEADS, SOURCE_ID, check_seal, identity, read, save, table
from audit import NS

import numpy as np


def verified_archive(directory):
    stamp = read(directory / "RUN_STATUS.json")
    assert stamp["stage"] == "ACCEPTED"
    assert stamp["acceptance"] == identity(directory / "ACCEPTANCE.json")
    assert stamp["hash_manifest"] == identity(directory / "SHA256SUMS")
    entries = {}
    for row in (directory / "SHA256SUMS").read_text("ascii").splitlines():
        sha, name = row.split("  ", 1)
        path = directory / name
        assert path.resolve().is_relative_to(directory.resolve()) and name not in entries
        assert identity(path)["sha256"] == sha
        entries[name] = sha
    assert read(directory / "ACCEPTANCE.json")["status"] == "PASS"
    return entries


def freeze_inputs(out, reference, previous):
    bank, enrollment, _, refs = check_seal(reference)
    archive = verified_archive(previous)
    required = {"THRESHOLDS.json", "holdout/SCORES.npz", "calibration/SCORES.npz",
                "holdout/CAPTURE.json", "STRESS_PAIRED.csv", "PAIRED.csv",
                "ATTACK_QUALIFICATION.json", "ATTACK_QUALIFICATION.csv"}
    assert required <= archive.keys()
    policy = read(previous / "THRESHOLDS.json")
    assert tuple(policy["arms"]) == ARMS and tuple(policy["heads"]) == HEADS
    assert policy["comparison"] == "strict_greater_than"
    assert policy["budget_numerator"] == 1 and policy["budget_denominator"] == 100
    assert policy["reference"] == bank["reference"]
    assert np.asarray(policy["thresholds"]).shape == (len(ARMS), len(HEADS))
    assert np.isfinite(policy["thresholds"]).all()
    assert policy["calibration_scores"] == identity(previous / "calibration/SCORES.npz")
    accepted = read(previous / "ACCEPTANCE.json")
    assert accepted["holdout_connections"] == PRIOR_CONNECTIONS
    assert accepted["holdout_scores"] == identity(previous / "holdout/SCORES.npz")
    counts = [expected_connections(schedule(batch)) for batch in range(1, len(SEEDS))]
    assert PRIOR_CONNECTIONS + sum(counts) >= TARGET_CONNECTIONS
    contract = dict(
        reference_archive=reference.name, reference=bank["reference"], reference_files_verified=len(refs),
        calibration_archive=previous.name, calibration_files_verified=len(archive),
        thresholds=identity(previous / "THRESHOLDS.json"),
        old_holdout=accepted["holdout_scores"], prior_connections=PRIOR_CONNECTIONS,
        target_connections=TARGET_CONNECTIONS, scheduled_connections=counts,
        endpoints=[[x["ip"], x["mac"]] for x in enrollment["endpoints"]],
        kernel=enrollment["kernel"], server_port=enrollment["server_port"],
        schedules=[schedule(batch) for batch in range(len(SEEDS))],
        code={path.name: identity(path) for path in sorted(HERE.glob("*.py"))},
    )
    path = out / "INPUTS.json"
    if path.exists():
        assert read(path) == contract
    else:
        save(path, contract)
    copies = {"METHOD.md": HERE / "METHOD.md"}
    for name in ("THRESHOLDS.json", "STRESS_PAIRED.csv", "ATTACK_QUALIFICATION.csv"):
        copies[name] = previous / name
    for name, source in copies.items():
        target = out / name
        if not target.is_file():
            shutil.copyfile(source, target)
        assert identity(target) == identity(source)
    assert identity(out / "THRESHOLDS.json") == contract["thresholds"]
    return contract, policy


def score_batch(out, attempt, batch):
    contract = read(out / "INPUTS.json")
    policy = read(out / "THRESHOLDS.json")
    assert identity(out / "THRESHOLDS.json") == contract["thresholds"]
    reference = out.parent / contract["reference_archive"]
    assert identity(reference / "enrollment/REFERENCE.npz") == contract["reference"]
    stage = attempt / "holdout"
    assert read(stage / "SCHEDULE.json") == contract["schedules"][batch] == schedule(batch)
    cap, report, alignment, fields = collect_aligned(stage)
    ended = read(attempt / "COLLECTION_DONE.json")
    assert ended == dict(status="PASS", service_instance=cap["service_instance"], namespaces_released=True)
    assert cap["scope"] == "holdout" and cap["capture"]["capture_kernel_drops"] == 0
    assert [[x["ip"], x["mac"]] for x in cap["endpoints"]] == contract["endpoints"]
    assert cap["server_port"] == contract["server_port"] and cap["kernel"] == contract["kernel"]
    aligned = roster(alignment)
    uid, streams = arrays(aligned)
    n = expected_connections(schedule(batch))
    assert len(set(streams)) == report["checks"]["tcp_connections"] == n
    assert len(uid) == report["checks"]["aligned_requests"] and all(r["normal"] for r in aligned)
    with sealed_runtime() as (cfg, pins):
        assert cfg["method"]["cuts"] == policy["cic_cuts"]
        q, feature_proof = scores_for(reference, stage, cap, fields, aligned, cfg, pins)
    scores = attempt / "SCORES.npz"
    np.savez_compressed(scores, **q, arms=np.array(ARMS), cic_cuts=np.array(policy["cic_cuts"]))
    table(attempt / "PAIRED.csv", pairing(f"batch_{batch:02}", aligned, q, np.array(policy["thresholds"]),
                                       np.array(policy["cic_cuts"])))
    evidence = {path.relative_to(attempt).as_posix(): identity(path)
                for path in sorted([*(p for p in stage.iterdir() if p.is_file()),
                                     attempt / "COLLECTION_DONE.json", scores, attempt / "PAIRED.csv"])}
    save(attempt / "BATCH_ACCEPTANCE.json",
         dict(status="PASS", batch=batch, capture_instance=cap["service_instance"], seed=cap["random_seed"],
              start_ns=cap["capture"]["first_qualifying_ns"], end_ns=cap["capture"]["end_ns"],
              requests=len(uid), connections=n, features=feature_proof, files=evidence))


def capture_and_score(out, batch, previous_end, completed):
    folder = out / f"batch_{batch:02}"
    folder.mkdir(exist_ok=True)
    attempts = sorted(folder.glob("attempt_*"))
    attempt = attempts[-1] if attempts else None
    if attempt is None or not (attempt / "COLLECTION_DONE.json").is_file():
        if attempt is not None and (attempt / "COLLECTION_PROGRESS.json").is_file():
            age = time.time_ns() - read(attempt / "COLLECTION_PROGRESS.json")["keeper_heartbeat_ns"]
            assert age > 30 * NS, "The previous collector still has a fresh heartbeat."
        while time.time_ns() <= previous_end + 60 * NS:
            state(out, "BETWEEN_BATCHES", batch=batch, completed=completed)
            time.sleep(1)
        attempt = folder / f"attempt_{len(attempts) + 1:02}"
        attempt.mkdir()
        state(out, "CAPTURING", batch=batch, completed=completed, attempt=attempt.relative_to(out).as_posix())
        command = ["wsl.exe", "-d", "Ubuntu-24.04", "-u", "root", "--cd", "/", "--exec",
                   "python3", "-B", wsl(HERE / "collect_holdout.py"), wsl(attempt), str(batch),
                   wsl(out / "INPUTS.json")]
        subprocess.run(command, check=True, timeout=schedule(batch)["duration_seconds"] + 120)
    receipt = attempt / "BATCH_ACCEPTANCE.json"
    if not receipt.is_file():
        state(out, "SCORING", batch=batch, completed=completed, attempt=attempt.relative_to(out).as_posix())
        subprocess.run([sys.executable, "-X", "utf8", "-B", str(HERE / "run.py"),
                        str(out), "--score", str(batch), "--attempt", str(attempt)], check=True)
    result = read(receipt)
    assert result["status"] == "PASS" and result["batch"] == batch
    assert result["start_ns"] > previous_end + 60 * NS
    assert all(identity(attempt / name) == pin for name, pin in result["files"].items())
    return attempt, result


def rows_from(path, split):
    with path.open(encoding="utf8", newline="") as file:
        return [dict(row, split=split) for row in csv.DictReader(file)]


def pooled(rows, label):
    keys = ("group", "mode", "arm", "head", "unit")
    counts = ("denominator", "false_positives", "raw_false_positives",
              "both_alarm", "raw_only", "arm_only", "neither")
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[key] for key in keys)].append(row)
    merged = []
    for group in groups.values():
        nums = {key: sum(int(row[key]) for row in group) for key in counts}
        n, fp = nums["denominator"], nums["false_positives"]
        assert n == nums["both_alarm"] + nums["raw_only"] + nums["arm_only"] + nums["neither"]
        assert fp == nums["both_alarm"] + nums["arm_only"]
        row = dict(group[0], **nums, split=label, fpr=fp / n)
        row["meets_one_pct_budget"] = fp * 100 <= n if row["unit"] == "connection" else ""
        merged.append(row)
    return merged


def attack_inventory(out, previous):
    saved = read(previous / "ATTACK_QUALIFICATION.json")
    excluded = {*saved["known_local_capture_roots"], previous.name, out.name}
    paths = sorted(path.relative_to(out.parent).as_posix() for path in out.parent.glob("**/login.pcap")
                   if path.relative_to(out.parent).parts[0] not in excluded)
    save(out / "ATTACK_QUALIFICATION.json",
         dict(status="PENDING_ATTACK_EVALUATION", endpoint=saved["target"],
              prior_qualification=identity(previous / "ATTACK_QUALIFICATION.json"),
              additional_paths_for_label_check=paths))


def finish(out, previous, batches, preflight):
    prior = rows_from(previous / "PAIRED.csv", "prior_holdout")
    new = [row for path, receipt in batches for row in rows_from(path / "PAIRED.csv", f"batch_{receipt['batch']:02}")]
    totals = pooled(new, "new_holdout") + pooled(prior + new, "all_holdout")
    table(out / "PAIRED.csv", prior + new + totals)
    count = PRIOR_CONNECTIONS + sum(item["connections"] for _, item in batches)
    assert count >= TARGET_CONNECTIONS
    lines = ["# 同服务登录正常留出扩充", "",
             f"四个独立服务实例与原有 194 条留出共 {count:,} 条正常连接。"
             "三组使用此前冻结的本地阈值。", "",
             "| 普通留出 | 三种子集成 | 误报连接 / 总连接 | 误报率 | 1% 预算 |",
             "|---|---|---:|---:|---|"]
    for row in prior + new + totals:
        if (row["group"], row["mode"], row["head"], row["unit"]) != (
                "overall", "login_calibrated", "ensemble", "connection"):
            continue
        n, fp = int(row["denominator"]), int(row["false_positives"])
        lines.append(f"| {row['split']} | {row['arm']} | {fp} / {n} | {fp / n:.2%} | "
                     f"{'达到' if fp * 100 <= n else '超出'} |")
    lines += ["", "合法重连压力测试仍按原 51 条连接单列。攻击侧同端点独立标签记录待补。"]
    (out / "RESULTS_FOR_PAPER.md").write_text("\n".join(lines) + "\n", encoding="utf8")
    gate = preflight[0] / "BATCH_ACCEPTANCE.json"
    save(out / "ACCEPTANCE.json",
         dict(status="PASS", prior_connections=PRIOR_CONNECTIONS, total_connections=count,
              thresholds=identity(out / "THRESHOLDS.json"), preflight=identity(gate),
              batches=[dict(receipt=str((path / "BATCH_ACCEPTANCE.json").relative_to(out).as_posix()),
                            sha256=identity(path / "BATCH_ACCEPTANCE.json")["sha256"],
                            connections=result["connections"]) for path, result in batches],
              stress=identity(out / "STRESS_PAIRED.csv"), paired=identity(out / "PAIRED.csv"),
              attack_evaluation="PENDING_ATTACK_EVALUATION"))
    files = [p for p in out.iterdir() if p.is_file() and p.suffix in (".md", ".json", ".csv")
             and p.name not in ("RUN_STATUS.json", "FAILURE.json")]
    for path, receipt in [preflight, *batches]:
        files.extend([path / "BATCH_ACCEPTANCE.json", *(path / name for name in receipt["files"])])
    manifest = out / "SHA256SUMS"
    pins = {path.relative_to(out).as_posix(): identity(path)["sha256"] for path in sorted(files)}
    manifest.write_bytes("".join(f"{sha}  {name}\n" for name, sha in pins.items()).encode("ascii"))
    assert all(identity(out / name)["sha256"] == sha for name, sha in pins.items())
    state(out, "ACCEPTED", completed=count, acceptance=identity(out / "ACCEPTANCE.json"),
          hash_manifest=identity(out / "SHA256SUMS"))


def run(out):
    previous = out.parent / CALIBRATION_ID
    reference = out.parent / SOURCE_ID
    state(out, "PREFLIGHT", completed=PRIOR_CONNECTIONS)
    freeze_inputs(out, reference, previous)
    attack_inventory(out, previous)
    completed = PRIOR_CONNECTIONS
    previous_end = read(previous / "holdout/CAPTURE.json")["capture"]["end_ns"]
    uids = set(get_array(previous / "holdout/SCORES.npz")["uid"])
    cal = set(get_array(previous / "calibration/SCORES.npz")["uid"])
    assert not uids & cal
    uids.update(cal)
    instances = {read(previous / "holdout/CAPTURE.json")["service_instance"],
                 read(reference / "enrollment/CAPTURE.json")["service_instance"]}
    batches = []
    for batch in range(len(SEEDS)):
        path, receipt = capture_and_score(out, batch, previous_end, completed)
        batch_uids = set(get_array(path / "SCORES.npz")["uid"])
        assert len(batch_uids) == receipt["requests"] and not batch_uids & uids
        assert receipt["capture_instance"] not in instances
        instances.add(receipt["capture_instance"])
        uids.update(batch_uids)
        previous_end = receipt["end_ns"]
        if batch == 0:
            preflight = path, receipt
        else:
            batches.append((path, receipt))
            completed += receipt["connections"]
    finish(out, previous, batches, preflight)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("out", type=Path)
    parser.add_argument("--score", type=int)
    parser.add_argument("--attempt", type=Path)
    args = parser.parse_args()
    if args.score is not None:
        score_batch(args.out, args.attempt, args.score)
    else:
        with (args.out / ".controller.lock").open("a+b") as lock:
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            power = ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            try:
                assert shutil.disk_usage(args.out).free > 2 * 2**30
                run(args.out)
            except Exception as exc:
                save(args.out / "FAILURE.json", dict(error=str(exc) or repr(exc), trace=traceback.format_exc()))
                state(args.out, "STOP", error=str(exc) or repr(exc))
                raise
            finally:
                if power:
                    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
