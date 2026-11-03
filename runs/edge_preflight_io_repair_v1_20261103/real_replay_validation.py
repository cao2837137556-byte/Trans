"""Local D-drive, no-model numerical snapshot and bounded raw-prefix checks."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import time

import replay_io

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
HTTP_FRAMES = [1, 2, 3, 4, 8, 26, 60, 192, 4201, 4202, 4203, 4204, 7296, 12140]


def exact(a, b, path='snapshot'):
    if type(a) is not type(b):
        raise AssertionError('TYPE:'+path+':'+str(type(a))+':'+str(type(b)))
    if type(a) is dict:
        if set(a) != set(b):
            raise AssertionError('KEYS:'+path)
        for key in a:
            exact(a[key], b[key], path+'/'+str(key))
    elif type(a) in (list, tuple):
        if len(a) != len(b):
            raise AssertionError('LENGTH:'+path)
        for index, (left, right) in enumerate(zip(a, b)):
            exact(left, right, path+'/'+str(index))
    elif a != b:
        raise AssertionError('VALUE:'+path)


def main(endpoints_only=False):
    start = time.monotonic()
    deadline = start+180
    spec = importlib.util.spec_from_file_location('edge_replay_validation_adapter',
        ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
    edge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edge)
    owned = Path(tempfile.mkdtemp(prefix='local-validation-owned-', dir=str(HERE)))
    last = [0.0]
    peak = [0]
    def guard():
        if time.monotonic() >= deadline:
            raise TimeoutError('LOCAL_VALIDATION_180_SECONDS')
        if time.monotonic()-last[0] >= 1:
            used = sum(p.stat().st_size for p in owned.rglob('*') if p.is_file())
            peak[0] = max(peak[0], used)
            last[0] = time.monotonic()
            if used > 512*1024**2:
                raise OSError('LOCAL_VALIDATION_512_MIB_TEMP_LIMIT')
    result = dict(version='LOCAL_REPLAY_VALIDATION_V1', model_calls=0,
                  repair_source_sha256=replay_io.sha(replay_io.__file__),
                  hard_wall_seconds=180, hard_temporary_bytes=512*1024**2,
                  original_sources_modified=False, endpoint_comparison={}, prefix_runs={})
    try:
        before = time.monotonic()
        original = list(edge.selected_snapshots('HTTP', HTTP_FRAMES,
            owned/'original-http', deadline=deadline))
        result['original_http_seconds'] = time.monotonic()-before
        with replay_io.install(edge, output=owned/'output', cache_root=owned/'cache',
                               scratch_root=owned, deadline=deadline, guard=guard) as repair:
            before = time.monotonic()
            fixed = list(edge.selected_snapshots('HTTP', HTTP_FRAMES, owned/'repaired-http'))
            result['repaired_http_seconds'] = time.monotonic()-before
            exact(original, fixed)
            result['endpoint_comparison'] = dict(passed=True, frames=HTTP_FRAMES,
                                                 exact_recursive_values_and_types=True)
            cached = list(edge.selected_snapshots('HTTP', HTTP_FRAMES, owned/'unused-cache-work'))
            exact(original, cached)
            result['completed_http_cache_reuse_exact'] = True
            prefixes = () if endpoints_only else (('NORMAL', 255220), ('HTTP', 228978), ('UDP', 16))
            for role, frame in prefixes:
                guard()
                before = time.monotonic()
                generated = list(edge.selected_snapshots(role, [frame], owned/('prefix-'+role)))
                result['prefix_runs'][role] = dict(prefix_frames=frame,
                    selected_snapshots=len(generated), seconds=time.monotonic()-before)
                # This run proves raw-prefix replay only, never encoder throughput.
            result['final_replay_status'] = json.loads((owned/'output/REPLAY_HEARTBEAT.json').read_text())
        result['passed'] = True
    except BaseException as exc:
        result['passed'] = False
        result['failure'] = type(exc).__name__+':'+str(exc)
        if (owned/'output/REPLAY_HEARTBEAT.json').exists():
            result['final_replay_status'] = json.loads((owned/'output/REPLAY_HEARTBEAT.json').read_text())
    finally:
        result['seconds'] = time.monotonic()-start
        result['peak_temporary_bytes_observed'] = peak[0]
        shutil.rmtree(owned)
        result['owned_temporary_removed'] = not owned.exists()
        path = HERE/('REAL_ENDPOINT_FINAL_VALIDATION.json' if endpoints_only else 'REAL_REPLAY_VALIDATION.json')
        replay_io._write_json(path, result)
        path.with_suffix('.json.sha256').write_text(replay_io.sha(path)+'  '+path.name+'\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--endpoints-only', action='store_true')
    raise SystemExit(main(parser.parse_args().endpoints_only))
