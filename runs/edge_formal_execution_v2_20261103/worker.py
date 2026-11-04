"""Formal Edge entry point. A draft card can never start an external evaluation.

Large snapshots/arrays stay in the caller's HPC output directory. No transport,
SSH login, submission, retry or budget extension is implemented here.
"""
from __future__ import annotations

import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

import argparse
import gzip
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time
import uuid

from checkpoint import atomic_json, canonical, require, sha
from streaming import ROOT, FrozenBackend, make_plan, module, run_encoding

HERE = Path(__file__).resolve().parent
SELECTION = ROOT/'runs/edge_query_selection_v1_20261103/seal20k/QUERY_SELECTION_SEAL.json'
SELECTION_SHA = 'ecb7bd84ae1ff2005e98bb750f1d4f5aac10f09487189e489ad73c583efa6f08'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            yield json.loads(line)


def selection_inputs():
    require(sha(SELECTION) == SELECTION_SHA, 'BASE_SELECTION_SEAL_SHA')
    seal = read(SELECTION)
    selected = {}
    for role, spec in seal['roles'].items():
        path = SELECTION.parent/spec['selected_file']
        require(sha(path) == spec['selected_sha256'], 'SELECTED_ROWS_SHA:'+role)
        value = list(rows(path))
        require(len(value) == spec['selected_rows'] and
                [r['uid'] for r in value] == sorted(r['uid'] for r in value) and
                len({r['uid'] for r in value}) == len(value), 'SELECTED_EXACT_UID_ORDER')
        selected[role] = value
    spec = seal['references']
    path = ROOT/spec['source_path']
    require(sha(path) == spec['source_sha256'], 'REFERENCE_ROWS_SHA')
    refs = list(rows(path))
    require(len(refs) == spec['rows'], 'REFERENCE_EXACT_ROWS')
    uids = [r['uid'] for r in refs] + [r['uid'] for group in selected.values() for r in group]
    require(len(uids) == len(set(uids)), 'ALL_LOGICAL_UIDS_DISJOINT')
    return seal, refs, selected


def merge_selected(snapshot, expected):
    actual = snapshot['row']
    for name in ('uid', 'frame', 'timestamp_ns', 'protocol', 'capture_id', 'component_id',
                 'source_role', 'use', 'owner', 'source_sha256'):
        require(actual.get(name) == expected.get(name), 'RAW_TO_SELECTION_IDENTITY:'+name)
    for key in set(actual) & set(expected):
        left, right = actual[key], expected[key]
        # Raw namespace keys are tuples; sealed JSON represents them as lists.
        equal = canonical(left) == canonical(right) if isinstance(left, (tuple, list, dict)) else left == right
        require(equal, 'RAW_TO_SEALED_METADATA:'+key)
    if 'tcp_flags' in expected:
        flags = sum(int(snapshot['q14'][1+b]) << b for b in range(9)) if actual['protocol'] == 6 else 0
        require(flags == expected['tcp_flags'], 'SEALED_QUERY_TCP_FLAGS')
    # Only score-independent, presealed inclusion/stratum metadata is added.
    snapshot = dict(snapshot, row=dict(actual, **expected))
    return snapshot


class Guard:
    def __init__(self, output, scratch, budget, formal=True):
        import psutil
        self.psutil, self.process = psutil, psutil.Process()
        self.out, self.scratch, self.budget = Path(output), Path(scratch), budget
        self.started, self.last = time.monotonic(), 0.
        self.max_rss = 0
        self.max_output_disk_bytes, self.max_scratch_disk_bytes = 0, 0
        self.formal, self.last_disk = formal, 0.

    def __call__(self):
        require(time.monotonic()-self.started < self.budget['wall_seconds']-120, 'WALL_BUDGET_STOP')
        if time.monotonic()-self.last < 2:
            return
        self.last = time.monotonic()
        processes = [self.process] + self.process.children(recursive=True)
        rss = 0
        for proc in processes:
            try:
                rss += proc.memory_info().rss
            except self.psutil.NoSuchProcess:
                pass
        self.max_rss = max(self.max_rss, rss)
        require(rss <= self.budget['rss_bytes'], 'RSS_BUDGET_STOP')
        require(shutil.disk_usage(self.out).free >= 2*1024**3 and
                shutil.disk_usage(self.scratch).free >= 2*1024**3, 'DISK_FREE_STOP')
        # Avoid rescanning thousands of shared-disk checkpoint files per packet.
        # Slurm/site quotas remain the storage hard boundary; this sampled
        # application check has a 60s maximum interval and a 2GiB free reserve.
        if time.monotonic()-self.last_disk >= 60:
            self.last_disk = time.monotonic()
            for root, limit in ((self.out, self.budget['disk_bytes']),
                                (self.scratch, self.budget['scratch_bytes'])):
                total = sum(p.stat().st_size for p in root.rglob('*') if p.is_file() and not p.is_symlink())
                field = 'max_output_disk_bytes' if root == self.out else 'max_scratch_disk_bytes'
                setattr(self, field, max(getattr(self, field), total))
                require(total <= limit, 'DISK_BUDGET_STOP:'+str(root))

    def progress(self, stage, **extra):
        self()
        value = dict(extra)
        if 'elapsed_seconds' in value:
            value['replay_elapsed_seconds'] = value.pop('elapsed_seconds')
        value.update(stage=stage, elapsed_seconds=time.monotonic()-self.started,
                     max_tree_rss_bytes=self.max_rss, formal_evaluation=self.formal,
                     output_disk_bytes_60s_sampled_max=getattr(self, 'max_output_disk_bytes', 0),
                     scratch_disk_bytes_60s_sampled_max=getattr(self, 'max_scratch_disk_bytes', 0),
                     automatic_resubmit=False)
        if hasattr(self, 'attempt_id'):
            value.update(attempt_id=self.attempt_id, card_sha256=self.card_sha256)
        atomic_json(self.out/'PROGRESS.json', value)


def runtime_identity(tshark):
    return dict(system=platform.system(), python=platform.python_version(),
        versions={name: importlib.metadata.version(name)
                  for name in ('numpy', 'torch', 'transformers', 'safetensors', 'psutil', 'dpkt', 'pandas')},
        tshark_first_line=subprocess.run([str(tshark), '--version'], capture_output=True,
                                        text=True, check=True, timeout=30).stdout.splitlines()[0])


def input_binding(card, identity, source_card):
    """Scientific snapshot identity is independent of any execution card SHA."""
    pins = card.get('scientific_input_artifact_pins')
    require(type(pins) is dict and bool(pins), 'SCIENTIFIC_INPUT_ARTIFACT_PINS_REQUIRED')
    return dict(schema='EDGE_SCIENTIFIC_INPUT_BINDING_V2',
        dependency_envelope=card['dependency_envelope'],
        selection_seal_sha256=SELECTION_SHA, runtime_identity=identity,
        scientific_artifact_pins=pins,
        raw_pins={role: dict(bytes=source_card['raw_inputs'][role]['bytes'],
                            sha256=source_card['raw_inputs'][role]['sha256'])
                  for role in ('NORMAL', 'HTTP', 'UDP')})


def prepare_inputs(card, runtime, output, scratch, guard, identity, *, replay_to_eof=False):
    """Shared gate/formal replay. Only exhausted, final-raw-checked roles load."""
    from dependency_identity import verify
    verify(card, ROOT)  # must run even when every role spool already exists
    output, scratch = Path(output), Path(scratch)
    seal, refs, selected = selection_inputs()
    require(card['selection_seal_sha256'] == SELECTION_SHA, 'CARD_SELECTION_BINDING')
    adapter = module('_edge_formal_adapter', ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
    source_card = adapter.card()
    tshark = Path(runtime['tshark']).resolve()
    for role in ('NORMAL', 'HTTP', 'UDP'):
        guard()
        path = Path(runtime['raw_paths'][role]).resolve()
        spec = source_card['raw_inputs'][role]
        require(path.stat().st_size == spec['bytes'] and sha(path) == spec['sha256'], 'RAW_PIN:'+role)
        spec['path'] = str(path)
    binding = input_binding(card, identity, source_card)
    from checkpoint import PackedRoleSpool
    replay = module('_edge_formal_replay_io', ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
    all_headers, spools, uid_roles = [], {}, {}
    for role in ('NORMAL', 'HTTP', 'UDP'):
        expected = sorted((refs if role == 'NORMAL' else [])+selected[role], key=lambda r: r['uid'])
        expected_by_uid = {r['uid']: r for r in expected}
        spool = PackedRoleSpool(output/'spools'/role, binding, role, list(expected_by_uid))
        spools[role] = spool
        complete = spool.is_complete()
        coverage_path = output/'spools'/role/'REPLAY_COVERAGE.json'
        coverage = read(coverage_path) if coverage_path.exists() else {}
        eof_complete = (coverage.get('raw_sha256') == source_card['raw_inputs'][role]['sha256']
                        and coverage.get('last_frame') == source_card['raw_inputs'][role]['records']
                        and coverage.get('generator_exhausted') is True)
        if not complete or (replay_to_eof and not eof_complete):
            work = output/'replay_attempts'/(role+'-'+uuid.uuid4().hex)
            work.parent.mkdir(exist_ok=True)
            # Bypass the old per-snapshot cache, while retaining its tested
            # node-local numerical DB and per-physical-frame deadline hooks.
            with replay.install(adapter, output=output/'replay_status', cache_root=output/'unused_legacy_cache',
                scratch_root=scratch, deadline=guard.started+guard.budget['wall_seconds']-120,
                guard=guard, heartbeat=guard.progress) as patched:
                patched.active = dict(role=role, frame=0, start=time.monotonic(),
                    append_seconds=0., decoder_next_seconds=0., selected_persisted=0)
                if replay_to_eof:
                    def decode_to_eof(*args, **kwargs):
                        kwargs['stop_after'] = source_card['raw_inputs'][role]['records']
                        return patched.decode_rows(*args, **kwargs)
                    adapter.decode_rows = decode_to_eof
                stream = patched.original['selected_snapshots'](role,
                    [r['frame'] for r in expected], work, tshark=tshark,
                    reference_frames=[r['frame'] for r in refs] if role == 'NORMAL' else [],
                    value=source_card, deadline=guard.started+guard.budget['wall_seconds']-120)
                try:
                    for snapshot in stream:
                        guard()
                        require(snapshot['uid'] in expected_by_uid, 'REPLAY_EXTRA_UID')
                        merged = merge_selected(snapshot, expected_by_uid[snapshot['uid']])
                        if complete:
                            require(canonical(spool._header(merged)) ==
                                    canonical(spool._header(spool.load(merged['uid']))),
                                    'EOF_REPLAY_HEADER_PARITY')
                        else:
                            spool.append(merged)
                        patched.active['selected_persisted'] += 1
                    # Exhaustion follows the original generator's final raw
                    # size/mtime/SHA check. A partial role never reaches here.
                    spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
                    last_frame = patched.active['frame']
                    require(not replay_to_eof or last_frame == source_card['raw_inputs'][role]['records'],
                            'FULL_EOF_REPLAY_RECORD_COUNT')
                    atomic_json(coverage_path, dict(role=role,
                        raw_sha256=source_card['raw_inputs'][role]['sha256'],
                        last_frame=last_frame, expected_records=source_card['raw_inputs'][role]['records'],
                        generator_exhausted=True, replay_to_eof=bool(replay_to_eof),
                        final_raw_identity_pass=True))
                finally:
                    stream.close()
        headers = list(spool.headers())
        all_headers.extend(headers)
        uid_roles.update({h['uid']: role for h in headers})
        guard.progress('ROLE_SPOOL_COMPLETE', role=role, rows=len(headers))
    plan = make_plan(all_headers)
    def load(uid):
        return spools[uid_roles[uid]].load(uid)
    return dict(headers=all_headers, plan=plan, load=load, spools=spools,
                uid_roles=uid_roles, input_binding=binding)

def run(card_path, authorization_path, runtime_path, output):
    gate = module('_edge_formal_execution_gate', ROOT/'runs/edge_external_test1_engineering_v1_20261103/execution_gate.py')
    gate.require_evaluation_authorization(card_path, authorization_path, ROOT)
    card, runtime = read(card_path), read(runtime_path)
    from dependency_identity import verify
    verify(card, ROOT)
    # The new worker needs its own actual Linux recovery/parity gate. 181418
    # alone proved the old tiny fixture, not this implementation's restart.
    require(card.get('formal_worker_linux_recovery', {}).get('status') == 'PASS',
            'FORMAL_WORKER_LINUX_RECOVERY_PENDING')
    require(card.get('independent_review', {}).get('status') == 'PASS', 'INDEPENDENT_REVIEW_PENDING')
    require(platform.system() == 'Linux', 'FORMAL_LINUX_ONLY')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    require(not output.is_symlink(), 'OUTPUT_SYMLINK')
    scratch_root = Path(runtime['scratch_root']).resolve()
    require(scratch_root.is_dir() and scratch_root.stat().st_dev != output.stat().st_dev,
            'NODE_LOCAL_SCRATCH_DIFFERENT_DEVICE_REQUIRED')
    tshark = Path(runtime['tshark']).resolve()
    identity = runtime_identity(tshark)
    require(identity == card['runtime_identity'], 'PINNED_RUNTIME_IDENTITY')
    budget = card['budget']
    import psutil
    require(len(psutil.Process().cpu_affinity()) == budget['cpu'] == 1, 'CPU_AFFINITY_ONE')
    seal, refs, selected = selection_inputs()
    require(card['selection_seal_sha256'] == SELECTION_SHA, 'CARD_SELECTION_BINDING')
    require(sum(len(v) for v in selected.values())+len(refs) == budget['encoding_rows'], 'ENCODING_BUDGET_BINDING')
    binding = dict(execution_card_sha256=sha(card_path), selection_seal_sha256=SELECTION_SHA,
                   runtime_identity=identity, artifact_pins=card['artifact_pins'])
    scratch = scratch_root/('edge-formal-owned-'+uuid.uuid4().hex)
    scratch.mkdir()
    atomic_json(scratch/'OWNERSHIP.json', dict(output=str(output), pid=os.getpid()))
    guard = Guard(output, scratch, budget)
    try:
        prepared = prepare_inputs(card, runtime, output, scratch, guard, identity)
        plan, load = prepared['plan'], prepared['load']
        atomic_json(output/'BATCH_PLAN.json', plan)
        store, encoding_receipt = run_encoding(plan, load, FrozenBackend, output/'encoded', binding,
                                               guard, guard.progress)
        atomic_json(output/'ENCODING_ATTEMPT.json', encoding_receipt)
        guard.progress('ENCODING_COMPLETE', logical_rows=budget['encoding_rows'])
        census_spec = card['population_census']
        census_path = ROOT/census_spec['path']
        require(sha(census_path) == census_spec['sha256'], 'POPULATION_CENSUS_SHA')
        from evaluate import evaluate
        metrics = evaluate(store, plan, output/'evaluation', binding, read(census_path),
                           budget['distance_pairs'], guard, guard.progress)
        guard.progress('COMPLETE', metrics_sha256=sha(metrics), methods_frozen=True)
    except BaseException as exc:
        atomic_json(output/'STOP.json', dict(reason=type(exc).__name__+':'+str(exc),
            elapsed_seconds=time.monotonic()-guard.started, max_tree_rss_bytes=guard.max_rss,
            completed_batch_outputs_preserved=True, partial_roles_reusable=False,
            automatic_resubmit=False, automatic_extension=False))
        raise
    finally:
        require(scratch.parent == scratch_root and scratch.name.startswith('edge-formal-owned-')
                and not scratch.is_symlink(), 'SCRATCH_CLEANUP_SCOPE')
        shutil.rmtree(scratch)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.card, args.authorization, args.runtime, args.output)
