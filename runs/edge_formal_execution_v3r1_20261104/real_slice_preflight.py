"""Fresh fixed real fixture through the actual v3 packed spool and backend.

78 pre-model selected endpoints; no official external quality retained. This
small fixture never substitutes for the full 73-shape/recovery engineering gate.
"""
import argparse
from contextlib import contextmanager
from pathlib import Path
import sys
import time
import worker
from checkpoint import PackedRoleSpool, atomic_json, require, sha
from streaming import ROOT, FrozenBackend, make_plan, module, run_encoding
from worker import Guard, read, runtime_identity
from progress_io import install
from engineering_gate import require_engineering_authorization, supervise
from runtime_control import Attempt, attempt_directory, child_scratch, current_status

SLICE = 'runs/edge_query_selection_v1_20261103/shapes_v3/SLICE_CARD.json'
SLICE_SHA = 'fcd8837370be480b2a09f75e82f0431069982ee4702590fe9901aa3409a51465'
STAGES = ('INPUTS', 'REAL_DECODE_PACKED_SPOOL', 'V3_FROZEN_ENCODING',
          'SOURCE_PARITY', 'DISTANCE_EVALUATION_INTERFACES', 'FINAL_IDENTITY')


def validate_candidate(value, card_sha, identity):
    require(value.get('status') == 'CANDIDATE_SUCCESS' and value.get('card_sha256') == card_sha
            and value.get('kind') == 'V3_REAL_SLICE_E2E'
            and value.get('runtime_identity') == identity and value.get('slice_sha256') == SLICE_SHA
            and value.get('logical_rows') == 78 and value.get('external_quality_retained') is False
            and value.get('actual_v3_packed_backend') is True, 'PREFLIGHT_CANDIDATE_FIELDS')
    require([s.get('name') for s in value.get('stages', [])] == list(STAGES)
            and all(s.get('status') == 'PASS' and s.get('seconds', -1) >= 0 for s in value['stages']),
            'PREFLIGHT_ALL_REAL_STAGES_REQUIRED')


class Progress:
    def __init__(self, guard):
        self.guard, self.out, self.stages = guard, guard.out, []

    def save(self, stage, **kw):
        self.guard.progress('PREFLIGHT_'+stage, **kw)

    @contextmanager
    def stage(self, name):
        started = time.monotonic()
        record = dict(name=name, status='RUNNING')
        self.stages.append(record)
        self.save(name)
        try:
            yield
        except BaseException:
            record.update(status='FAIL', seconds=time.monotonic()-started)
            raise
        else:
            record.update(status='PASS', seconds=time.monotonic()-started)
        finally:
            atomic_json(self.out/'PREFLIGHT_STAGES.json', self.stages)


def execute(args):
    import numpy as np
    card = require_engineering_authorization(args.card, args.authorization)
    runtime = read(args.runtime)
    output = Path(args.output)
    scratch = child_scratch(output, args.attempt_id, 'main', sha(args.card))
    budget = dict(card['budget'], wall_seconds=max(0, args.deadline-time.monotonic()))
    guard = Guard(output, scratch, budget, formal=False)
    guard.attempt_id, guard.card_sha256 = args.attempt_id, sha(args.card)
    progress = Progress(guard)
    with progress.stage('INPUTS'):
        identity = runtime_identity(runtime['tshark'])
        require(identity == card['runtime_identity'], 'PREFLIGHT_FROZEN_RUNTIME')
        require(sha(ROOT/SLICE) == SLICE_SHA, 'PREFLIGHT_FIXED_SLICE_SHA')
        fixture = read(ROOT/SLICE)
        require(fixture['mode'] == 'FIXED_HEADER_ONLY_ENGINEERING_SLICE'
                and sum(len(s['frames']) for s in fixture['slices']) == 78, 'PREFLIGHT_FIXED_78')
        adapter = module('_v3_slice_adapter', ROOT/'runs/edge_external_test1_engineering_v1_20261103/adapter/edge_adapter.py')
        source = adapter.card()
        before = {}
        for role, raw in source['raw_inputs'].items():
            path = Path(runtime['raw_paths'][role])
            require(path.stat().st_size == raw['bytes'] and sha(path) == raw['sha256'], 'PREFLIGHT_RAW_PIN')
            raw['path'] = str(path)
            before[role] = path.stat().st_mtime_ns
        engine = module('_v3_fixture_engine', ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight/engine.py')
        freeze, assets, normalizer, pins = engine.frozen_assets()
    headers, spools = [], {}
    binding = dict(scope='FIXED_ENGINEERING_FIXTURE_NOT_FULL_ROLE', card_sha256=sha(args.card), slice_sha256=SLICE_SHA)
    with progress.stage('REAL_DECODE_PACKED_SPOOL'):
        replay = module('_v3_slice_replay', ROOT/'runs/edge_preflight_io_repair_v1_20261103/replay_io.py')
        with install(replay, worker, output), replay.install(adapter, output=output/'replay_status',
                cache_root=output/'unused_cache', scratch_root=scratch,
                deadline=guard.started+budget['wall_seconds']-120, guard=guard, heartbeat=guard.progress) as patched:
            for spec in fixture['slices']:
                role = spec['role']
                patched.active = dict(role=role, frame=0, start=time.monotonic(),
                    append_seconds=0., decoder_next_seconds=0., selected_persisted=0)
                stream = patched.original['selected_snapshots'](role, spec['frames'], output/('decode_'+role),
                    reference_frames=spec.get('reference_frames', ()), value=source,
                    tshark=Path(runtime['tshark']), deadline=guard.started+budget['wall_seconds']-120)
                try:
                    entries = list(stream)  # fixture is bounded to 78 endpoints before any model call
                finally:
                    stream.close()
                require(sorted(s['row']['frame'] for s in entries) == sorted(spec['frames']), 'PREFLIGHT_EXACT_FRAMES')
                require(len({s['uid'] for s in entries}) == len(entries), 'PREFLIGHT_UIDS')
                spool = PackedRoleSpool(output/'fixture_spools'/role, binding, role, sorted(s['uid'] for s in entries))
                for snapshot in entries:
                    guard(); spool.append(snapshot)
                raw = source['raw_inputs'][role]
                require(sha(raw['path']) == raw['sha256'], 'PREFLIGHT_FINAL_ROLE_RAW')
                spool.complete(generator_exhausted=True, raw_final_identity_pass=True)
                for header in spool.headers():
                    require(header['uid'] not in spools, 'PREFLIGHT_CROSS_ROLE_UID')
                    headers.append(header); spools[header['uid']] = spool
                del entries
        require(len(headers) == 78, 'PREFLIGHT_DECODED_78')
    with progress.stage('V3_FROZEN_ENCODING'):
        plan = make_plan(headers)
        store, encoded = run_encoding(plan, lambda uid: spools[uid].load(uid), FrozenBackend,
            output/'fixture_batches', binding, guard=guard, progress=progress.save)
        entries, zs, qs = [], [], []
        for batch in plan:
            value = store.load(batch['batch_id'], batch['uids'])
            entries.extend(dict(uid=r['uid'], row=r) for r in value['rows'])
            zs.append(value['e3']); qs.append(value['q14'])
        e3, q14 = np.concatenate(zs), np.concatenate(qs)
        require(len(entries) == 78 and encoded['new_rows'] == 78, 'PREFLIGHT_ENCODED_78')
    with progress.stage('SOURCE_PARITY'):
        parity = engine.source_parity(assets, normalizer, freeze, progress)
        require(parity['four_head_decision_exact'] and parity['tolerance_1e_4_pass'], 'PREFLIGHT_SOURCE_PARITY')
    with progress.stage('DISTANCE_EVALUATION_INTERFACES'):
        interfaces = engine.evaluate_fixture(entries, e3, q14, assets, normalizer, freeze, progress)
    with progress.stage('FINAL_IDENTITY'):
        from dependency_identity import verify
        verify(card, ROOT)
        for role, raw in source['raw_inputs'].items():
            path = Path(raw['path'])
            require(path.stat().st_size == raw['bytes'] and path.stat().st_mtime_ns == before[role]
                    and sha(path) == raw['sha256'], 'PREFLIGHT_IMMUTABLE_RAW')
    candidate = dict(status='CANDIDATE_SUCCESS', kind='V3_REAL_SLICE_E2E', attempt_id=args.attempt_id,
        card_sha256=sha(args.card), runtime_identity=identity, slice_sha256=SLICE_SHA, logical_rows=78,
        actual_v3_packed_backend=True, stages=progress.stages, source_parity=parity, interfaces=interfaces,
        encoding=encoded, elapsed_seconds=time.monotonic()-guard.started,
        external_quality_retained=False, formal_evaluation=False,
        coverage='Fixed78 fixture; full73-shape throughput and crash recovery remain mandatory in next job')
    validate_candidate(candidate, sha(args.card), identity)
    atomic_json(attempt_directory(output, args.attempt_id)/'CANDIDATE.json', candidate)


def run(card_path, auth_path, runtime_path, output):
    started = time.monotonic()
    attempt = Attempt(output, sha(card_path))
    try:
        card = require_engineering_authorization(card_path, auth_path)
        auth = read(auth_path)
        require(auth.get('real_slice_preflight_required') is True and auth.get('preflight_wall_seconds') == 600,
                'PREFLIGHT_AUTHORIZATION')
        attempt.allocate_scratch(Path(read(runtime_path)['scratch_root']).resolve())
        deadline = started+570
        command = [sys.executable, '-X', 'utf8', '-B', str(Path(__file__).resolve()), '--child',
            '--card', str(card_path), '--authorization', str(auth_path), '--runtime', str(runtime_path),
            '--output', str(output), '--attempt-id', attempt.id, '--deadline', str(deadline)]
        return supervise(attempt, command, deadline, dict(card['budget'], wall_seconds=600))
    except BaseException as exc:
        if current_status(output, attempt_id=attempt.id)['status'] == 'RUNNING':
            try:
                cleaned = dict(complete=True, removed=attempt.cleanup())
            except BaseException as error:
                cleaned = dict(complete=False, reason=str(error))
            attempt.publish('STOP', reason=type(exc).__name__+':'+str(exc), scratch_cleanup=cleaned)
        raise
    finally:
        attempt.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for field in ('card', 'authorization', 'runtime', 'output'):
        parser.add_argument('--'+field, type=Path, required=True)
    parser.add_argument('--child', action='store_true')
    parser.add_argument('--attempt-id')
    parser.add_argument('--deadline', type=float)
    args = parser.parse_args()
    if args.child:
        execute(args)
    else:
        run(args.card, args.authorization, args.runtime, args.output)
