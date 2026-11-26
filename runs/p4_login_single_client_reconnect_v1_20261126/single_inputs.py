"""Pin the frozen scoring stack, the archived synchronized control and its benchmark."""
from pathlib import Path
import sys

import numpy as np

from single_protocol import SYNC_ROOT, registration

HERE = Path(__file__).resolve().parent
RUNS = HERE.parent
BASE = RUNS/"p4_login_legal_reconnect_v1_20261126"
sys.path.insert(0,str(BASE))
from frozen_assets import combine, registry, scoring_runtime
from evaluate_reconnect import verified_batch as verify_sync_batch
from results_reconnect import verdict
from sources import identity, read


def verified_files(folder, manifest):
    stamps = {}
    for line in manifest.read_text("ascii").splitlines():
        sha,name = line.split("  ",1)
        actual = (folder/name).resolve()
        assert name not in stamps and actual.is_relative_to(folder.resolve())
        assert identity(actual)["sha256"]==sha
        stamps[name] = sha
    assert stamps
    return stamps


def build_inputs(login):
    base, prior = registry(login)
    sync = login/SYNC_ROOT
    source = sync/"evidence"
    status = read(sync/"live/RUN_STATUS.json")
    manifest = source/"SHA256SUMS"
    assert status["stage"]=="ACCEPTED" and status["manifest"]==identity(manifest)
    checked = verified_files(source,manifest)
    accepted = read(source/"ACCEPTANCE.json")
    sync_pin = read(source/"REGISTRATION.json")
    assert accepted["status"]=="PASS" and accepted["connections"]==600 and len(accepted["batches"])==15
    assert accepted["registration"]==identity(source/"REGISTRATION.json")
    assert base["reference"]==accepted["reference"] and base["rank5_thresholds"]==accepted["thresholds"]
    assert base["cuts"]==sync_pin["cuts"] and base["handshake_threshold"]==accepted["h60_cut"]==4
    used = set(base["prior_service_instances"])
    latest = base["last_prior_capture_ns"]
    sync_rows = []
    for item,link in zip(sync_pin["plan"]["formal"],accepted["batches"],strict=True):
        receipt = source/link["path"]
        assert receipt.resolve().is_relative_to(source.resolve()) and identity(receipt)==link["receipt"]
        assert item["key"]==link["batch"] and link["silence_seconds"]>60
        actions = item["schedule"]["actions"]
        assert len(actions)==3 and sorted(a["client"] for a in actions)==[0,1,2]
        shortest = min(len(a["within_minute_s"]) for a in actions)
        assert all(a["within_minute_s"][:shortest]==actions[0]["within_minute_s"][:shortest] for a in actions)
        info, data = verify_sync_batch(receipt.parent,item,sync_pin,source/"REGISTRATION.json")
        assert info["instance"] not in used and info["start_ns"]>latest+60*10**9
        used.add(info["instance"])
        latest = info["end_ns"]
        sync_rows.append((item,info,data))
    sync_data = combine([x[2] for x in sync_rows],"synchronized_600")
    assert verdict(sync_data,np.asarray(base["cuts"]))[1].sum(axis=0).tolist()==[5,46,293,372]

    bench_state = read(sync/"live/BENCHMARK_STATUS.json")
    assert bench_state["status"]=="PASS"
    performance = Path(bench_state["table"]).resolve().parent
    assert performance.is_relative_to(sync.resolve())
    perf_files = verified_files(performance,performance/"SHA256SUMS")
    bench = read(performance/"ACCEPTANCE.json")
    assert bench["status"]=="PASS" and bench["source"]==identity(source/"ACCEPTANCE.json")
    assert bench["verdict_check"]["decision_mismatches"]==0
    assert bench["result"]==identity(performance/"PERFORMANCE.csv")

    primary = ("single_protocol.py","collect_single.py","single_inputs.py","evaluate_single.py",
               "run_single.py","single_results.py","METHOD.md")
    files = {f"{HERE.name}/{name}":identity(HERE/name) for name in primary}
    base.update(single_plan=registration(),sync_root=SYNC_ROOT,prior_service_instances=sorted(used),
                last_prior_capture_ns=latest,
                synchronized=dict(acceptance=identity(source/"ACCEPTANCE.json"),manifest=identity(manifest),
                                  files_checked=len(checked),capture_design="three clients with fixed phase offsets"),
                benchmark=dict(directory=performance.as_posix(),files_checked=len(perf_files),
                               table=bench["result"],acceptance=identity(performance/"ACCEPTANCE.json"),
                               manifest=identity(performance/"SHA256SUMS"),capture_design="synchronized normal reconnect"),
                files={**base["files"],**files})
    del base["plan"]
    return base,prior,sync_rows
