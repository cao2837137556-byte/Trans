"""Four small telemetry writes inside the existing allocation; no model/data."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

from progress_io import live_json


def main(deploy):
    deploy = Path(deploy)
    assert os.environ['SLURM_JOB_ID'] == '181645'
    allowed = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(allowed)})
    source = deploy/'checkout/runs/edge_preflight_io_repair_v1_20261103/replay_io.py'
    spec = importlib.util.spec_from_file_location('frozen_replay', source)
    frozen = importlib.util.module_from_spec(spec); spec.loader.exec_module(frozen)
    root = deploy/'diagnostic_progress_io_v1'
    root.mkdir(exist_ok=True)
    report = dict(schema='EDGE_SHARED_FS_TELEMETRY_MICROBENCH_V1',
        scope='FOUR_SMALL_WRITES_NOT_SCIENTIFIC_OR_FULL_LINUX_GATE',
        job_id=os.environ['SLURM_JOB_ID'], cpu_affinity=sorted(os.sched_getaffinity(0)),
        model_calls=0, original_replay_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        candidate_sha256=hashlib.sha256(Path(__file__).with_name('progress_io.py').read_bytes()).hexdigest(),
        measurements=[], status='RUNNING')
    payload = dict(stage='RAW_PREFIX_REPLAY', role='UDP', frame=777777,
                   counters={'append_seconds': 900.25, 'selected_persisted': 4500},
                   note='diagnostic synthetic telemetry only', padding='x'*1024)
    for i, mode in enumerate(('live', 'durable', 'live', 'durable')):
        report['pending_mode'] = mode
        live_json(root/'BENCHMARK.json', report)
        path = root/(str(i)+'-'+mode+'.json')
        start = time.monotonic()
        (live_json if mode == 'live' else frozen._write_json)(path, payload)
        report['measurements'].append(dict(mode=mode, seconds=time.monotonic()-start,
            bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        live_json(root/'BENCHMARK.json', report)
    assert len({x['sha256'] for x in report['measurements']}) == 1
    report.update(status='PASS_BYTE_IDENTICAL_TELEMETRY', pending_mode=None)
    live_json(root/'BENCHMARK.json', report)
    print(json.dumps(report, sort_keys=True))


if __name__ == '__main__':
    main(sys.argv[1])
