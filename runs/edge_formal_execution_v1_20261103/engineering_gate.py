"""Authorized Linux engineering only: replay, throughput, real crash recovery.

Never evaluates external quality, exports external E3, or submits a job. Heads
are exercised only against 16 saved source CAL rows. Large spools stay on HPC.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import gc
import hashlib
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'

from checkpoint import atomic_json, canonical, require, sha
from streaming import FrozenBackend, ROOT, make_plan, module, run_encoding
from worker import Guard, input_binding, prepare_inputs, read, runtime_identity, SELECTION_SHA

HERE = Path(__file__).resolve().parent
SCOPE = 'EDGE_FORMAL_WORKER_ENGINEERING_GATE'
READY = 'FROZEN_WORKER_ENGINEERING_GATE_READY_FOR_AUTHORIZATION'
GIB = 1024**3
EXPECTED_SHAPES = 73
SYNTHETIC_SEED = 20261103


def require_engineering_authorization(card_path, authorization_path, root=ROOT):
    card = read(card_path)
    require(card.get('status') == READY, 'ENGINEERING_GATE_CARD_NOT_READY')
    auth = read(authorization_path)
    require(auth.get('scope') == SCOPE and auth.get('user_authorized') is True
            and auth.get('card_sha256') == sha(card_path),
            'ACTUAL_BOUND_ENGINEERING_AUTHORIZATION_REQUIRED')
    require(card.get('independent_review', {}).get('status') == 'PASS',
            'ENGINEERING_INDEPENDENT_REVIEW_REQUIRED')
    budget = card.get('budget', {})
    require(budget.get('cpu') == 1 and budget.get('rss_bytes') == 8*GIB
            and budget.get('wall_seconds') == 7200
            and type(budget.get('scratch_bytes')) is int and 0 < budget['scratch_bytes'] <= 32*GIB
            and type(budget.get('disk_bytes')) is int and 0 < budget['disk_bytes'] <= 32*GIB
            and budget.get('automatic_resubmit') is False
            and budget.get('automatic_extension') is False, 'ENGINEERING_RESOURCE_CONTRACT')
    require(card.get('selection_seal_sha256') == SELECTION_SHA, 'ENGINEERING_SELECTION_SEAL')
    for field in ('artifact_pins', 'scientific_input_artifact_pins'):
        pins = card.get(field)
        require(type(pins) is dict and bool(pins), 'ENGINEERING_PINS_REQUIRED:'+field)
        for relative, expected in pins.items():
            path = (Path(root)/relative).resolve()
            require(path.is_relative_to(Path(root).resolve()) and path.is_file()
                    and sha(path) == expected, 'ENGINEERING_ARTIFACT_PIN:'+relative)
    return card


def probe_plan(headers, expected_shapes=EXPECTED_SHAPES):
    """Each presealed shape contributes its lexicographically first <=16 UIDs."""
    groups = defaultdict(list)
    for header in headers:
        groups[tuple(header['shape'])].append(header)
    require(len(groups) == expected_shapes, 'ENGINEERING_SHAPE_CENSUS_COUNT')
    chosen = []
    for shape in sorted(groups):
        chosen.extend(sorted(groups[shape], key=lambda h: h['uid'])[:16])
    plan = make_plan(chosen)
    require(len(plan) == expected_shapes, 'ENGINEERING_ONE_BATCH_PER_SHAPE')
    return plan


def throughput(plan, load, backend, guard, progress):
    results = []
    for entry in plan:
        guard()
        snapshots = [load(uid) for uid in entry['uids']]
        started = time.monotonic()
        e3, q14, receipt = backend.encode(snapshots, tuple(entry['shape']))
        seconds = time.monotonic()-started
        guard()
        require(receipt['physical_rows'] == entry['physical_rows'], 'PROBE_PHYSICAL_ROWS')
        require(e3.shape == (len(snapshots), 768) and q14.shape == (len(snapshots), 14),
                'PROBE_ENCODER_SHAPE')
        results.append(dict(shape=entry['shape'], logical_rows=len(snapshots),
            physical_rows=entry['physical_rows'], seconds=seconds,
            ordered_uid_sha256=hashlib.sha256(canonical(entry['uids'])).hexdigest(),
            input_tensor_sha256=[r['input_tensor_sha256'] for r in receipt['inputs']]))
        progress('ENGINEERING_SHAPE_COMPLETE', completed_shapes=len(results),
                 total_shapes=len(plan), logical_rows=len(snapshots))
        # External embeddings are discarded and never handed to a detector.
        del snapshots, e3, q14, receipt
    return results


def committed_files(root):
    root = Path(root)
    return {str(p.relative_to(root)): dict(bytes=p.stat().st_size, sha256=sha(p))
            for p in sorted(root.rglob('*')) if p.is_file() and 'pending' not in p.relative_to(root).parts}


def kill_tree(process):
    import psutil
    try:
        parent = psutil.Process(process.pid)
        children = parent.children(recursive=True)
    except psutil.NoSuchProcess:
        children = []
    for child in reversed(children):
        try:
            child.kill()
        except psutil.NoSuchProcess:
            pass
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)


def bounded_process(command, log_path, deadline, on_exit=None):
    """All subprocesses inherit the original absolute monotonic deadline."""
    remaining = deadline-time.monotonic()
    require(remaining > 5, 'ENGINEERING_DEADLINE_BEFORE_CHILD')
    with Path(log_path).open('ab') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        try:
            return process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            kill_tree(process)
            raise RuntimeError('ENGINEERING_HARD_DEADLINE')
        finally:
            if on_exit is not None and process.poll() is not None:
                on_exit(process.pid)


def recovery_root(output, attempt_id):
    require(type(attempt_id) is str and len(attempt_id) == 32
            and all(c in '0123456789abcdef' for c in attempt_id), 'RECOVERY_ATTEMPT_ID')
    return Path(output)/'engineering_recovery'/('attempt-'+attempt_id)


def cleanup_child_scratch(marker_path, scratch_root, output, child_pid):
    """Clean only the exact exited child's marked, matching ownership directory."""
    import shutil
    if not Path(marker_path).exists():
        return  # No exact child-owned directory is known; never enumerate.
    marker = read(marker_path)
    require(marker.get('scope') == SCOPE and marker.get('pid') == child_pid
            and marker.get('output') == str(Path(output).resolve()), 'CHILD_SCRATCH_MARKER_OWNER')
    candidate = Path(marker['scratch'])
    require(candidate.is_absolute() and candidate.parent.resolve() == Path(scratch_root).resolve()
            and candidate.name.startswith('edge-gate-owned-') and not candidate.is_symlink(),
            'CHILD_SCRATCH_MARKER_SCOPE')
    if candidate.exists():
        owner = read(candidate/'OWNERSHIP.json')
        require(owner.get('scope') == SCOPE and owner.get('pid') == child_pid
                and owner.get('output') == str(Path(output).resolve()), 'CHILD_SCRATCH_DIRECTORY_OWNER')
        shutil.rmtree(candidate)


def recovery_binding(card_path, identity):
    return dict(schema='EDGE_ENGINEERING_RECOVERY_V1', card_sha256=sha(card_path),
                runtime_identity=identity, selection_seal_sha256=SELECTION_SHA)


def synthetic_distances(guard, *, reference_counts=(4096, 28), query_count=128):
    """Real frozen core and kNN kernels over fixed-seed synthetic data only."""
    import numpy as np
    sys.path.insert(0, str(ROOT/'repo/ood'))
    import constrained_onboarding_core_v3 as core
    knn = module('_edge_engineering_synthetic_knn',
                 ROOT/'runs/edge_external_test1_engineering_v1_20261103/baselines/knn5.py')
    rng = np.random.default_rng(SYNTHETIC_SEED)
    normalizer = (np.zeros(768), np.ones(768))
    geometry = dict(protocols={str(p): dict(status='READY', rho_z=1., rho_q=1.) for p in (6, 17)})
    records = []
    for protocol, n in zip((6, 17), reference_counts):
        guard()
        refs = [dict(uid='synthetic-r-%d-%06d'%(protocol, i), partition='DEV',
            device='SYNTHETIC_ONLY', protocol=protocol, component_id='c%06d'%i,
            capture_id='synthetic-reference', timestamp=0., frame=i+1,
            use='REFERENCE', label=0, reference_end=1.) for i in range(n)]
        query = [dict(uid='synthetic-q-%d-%06d'%(protocol, i), partition='DEV',
            device='SYNTHETIC_ONLY', protocol=protocol, component_id='q%06d'%i,
            capture_id='synthetic-query', timestamp=2., frame=i+10000,
            use='QUERY') for i in range(query_count)]
        r = rng.normal(size=(n, 768)).astype(np.float32)
        q = rng.normal(size=(query_count, 768)).astype(np.float32)
        rq = rng.integers(0, 2, size=(n, 14)).astype(np.float32)
        qq = rng.integers(0, 2, size=(query_count, 14)).astype(np.float32)
        ru, qu = [x['uid'] for x in refs], [x['uid'] for x in query]
        before = time.monotonic()
        bank = core.ReferenceBank(refs, r, rq, normalizer, feature_uids=ru, q_uids=ru)
        support = bank.own(query, q, qq, geometry, feature_uids=qu, q_uids=qu)
        core_seconds = time.monotonic()-before
        guard()
        before = time.monotonic()
        knn_bank = knn.KNN5Bank(refs, r, normalizer, feature_uids=ru)
        distance = knn_bank.distances(query, q, feature_uids=qu, progress=lambda pairs: guard())
        knn_seconds = time.monotonic()-before
        guard()
        require(distance['pairs'] == n*query_count, 'SYNTHETIC_DISTANCE_PAIRS')
        records.append(dict(protocol=protocol, reference_rows=n, query_rows=query_count,
            distance_pairs_each=n*query_count, core_seconds=core_seconds, knn_seconds=knn_seconds,
            synthetic_input_sha256=hashlib.sha256(r.tobytes()+q.tobytes()+rq.tobytes()+qq.tobytes()).hexdigest(),
            core_output_sha256=hashlib.sha256(support['support'].tobytes()).hexdigest(),
            knn_output_sha256=hashlib.sha256(distance['distance'].tobytes()).hexdigest()))
    return dict(seed=SYNTHETIC_SEED, data='SYNTHETIC_ONLY_NO_EXTERNAL_FEATURES', records=records)


def compare_source_scores(cached, old, saved, cached_pred, old_pred, saved_pred):
    import numpy as np
    require(cached.shape == old.shape == saved.shape == (16, 3), 'SOURCE_HEAD_PARITY_SHAPE')
    require(cached_pred.shape == old_pred.shape == saved_pred.shape == (16, 4), 'SOURCE_DECISION_PARITY_SHAPE')
    value = dict(cache_vs_old_bit_exact=bool(np.array_equal(cached, old)),
        cache_vs_old_max_absolute_error=float(np.max(np.abs(cached-old))),
        cache_vs_old_tolerance_1e_4_pass=bool(np.allclose(cached, old, atol=1e-4, rtol=0)),
        cache_vs_old_four_head_decision_exact=bool(np.array_equal(cached_pred, old_pred)),
        source_saved_max_absolute_error=float(np.max(np.abs(cached-saved))),
        source_saved_bit_exact=bool(np.array_equal(cached, saved)),
        source_saved_tolerance_1e_4_pass=bool(np.allclose(cached, saved, atol=1e-4, rtol=0)),
        source_saved_four_head_decision_exact=bool(np.array_equal(cached_pred, saved_pred)))
    require(value['cache_vs_old_tolerance_1e_4_pass'] and value['cache_vs_old_four_head_decision_exact']
            and value['source_saved_tolerance_1e_4_pass'] and value['source_saved_four_head_decision_exact'],
            'SOURCE_CACHED_HEAD_PARITY_FAILED')
    return value


def source_cached_head_parity(guard):
    import numpy as np
    sys.path.insert(0, str(ROOT/'repo/ood'))
    from evaluate import FrozenHeads
    engine = module('_edge_engineering_source_parity',
        ROOT/'runs/edge_external_test1_engineering_v1_20261103/preflight/engine.py')
    freeze, spec, normalizer, pins = engine.frozen_assets()
    source = ROOT/'runs/c5_kernel_independent_replay_codex_20261102/source_cal'
    inputs = {}
    for name in ('CAL_FIXED_INPUTS.npz', 'CAL_E3.npy'):
        path = source/name
        expected = (source/(name+'.sha256')).read_text(encoding='utf-8-sig').split()[0]
        require(sha(path) == expected, 'SOURCE_HEAD_PIN:'+name)
        inputs[name] = expected
        guard()
    with np.load(source/'CAL_FIXED_INPUTS.npz', allow_pickle=False) as saved:
        q14, logits, predictions = (saved[key][:16].copy() for key in ('q14', 'raw_logits', 'raw_decisions'))
        uids = saved['uid'][:16].tolist()
    e3 = np.load(source/'CAL_E3.npy', allow_pickle=False, mmap_mode='r')[:16].copy()
    heads = FrozenHeads(spec, normalizer)
    cached = heads.scores(e3, q14)
    require(np.array_equal(cached, heads.scores(e3, q14)), 'SOURCE_HEAD_CACHE_REPEAT_NOT_EXACT')
    guard()
    old = engine.score_heads(e3, q14, spec, normalizer)
    _, cached_pred = engine.c5(cached, np.zeros(16), q14, freeze)
    _, old_pred = engine.c5(old, np.zeros(16), q14, freeze)
    value = compare_source_scores(cached, old, logits, cached_pred, old_pred, predictions)
    value.update(rows=16, input_sha256=inputs, ordered_uid_sha256=hashlib.sha256(canonical(uids)).hexdigest(),
        scope='Saved source CAL E3/q14 through frozen heads only; not raw-to-E3 source parity')
    guard()
    return value


def runtime_setup(card, runtime, output, deadline):
    require(platform.system() == 'Linux', 'ENGINEERING_LINUX_ONLY')
    require(0 < deadline-time.monotonic() <= 7200, 'ENGINEERING_ABSOLUTE_DEADLINE')
    import psutil
    require(len(psutil.Process().cpu_affinity()) == 1, 'ENGINEERING_CPU_AFFINITY_ONE')
    identity = runtime_identity(Path(runtime['tshark']).resolve())
    require(identity == card['runtime_identity'], 'ENGINEERING_PINNED_RUNTIME')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    scratch_root = Path(runtime['scratch_root']).resolve()
    require(scratch_root.is_dir() and scratch_root.stat().st_dev != output.stat().st_dev,
            'ENGINEERING_NODE_LOCAL_SCRATCH_REQUIRED')
    scratch = scratch_root/('edge-gate-owned-'+uuid.uuid4().hex)
    scratch.mkdir()
    atomic_json(scratch/'OWNERSHIP.json', dict(output=str(output), pid=os.getpid(), scope=SCOPE))
    budget = dict(card['budget'], wall_seconds=min(7200, deadline-time.monotonic()))
    guard = Guard(output, scratch, budget, formal=False)
    return output, scratch_root, scratch, guard, identity


def execute(card_path, auth_path, runtime_path, output, deadline, phase='main', attempt_id=None):
    card = require_engineering_authorization(card_path, auth_path)
    runtime = read(runtime_path)
    output, scratch_root, scratch, guard, identity = runtime_setup(card, runtime, output, deadline)
    try:
        if phase == 'main':
            attempt_id = uuid.uuid4().hex
        recovery = recovery_root(output, attempt_id)
        recovery.mkdir(parents=True, exist_ok=True)
        if phase in ('crash', 'resume'):
            atomic_json(recovery/('SCRATCH_'+phase+'.json'), dict(scope=SCOPE,
                pid=os.getpid(), output=str(output), scratch=str(scratch)))
        prepared = prepare_inputs(card, runtime, output, scratch, guard, identity, replay_to_eof=True)
        plan = probe_plan(prepared['headers'])
        binding = recovery_binding(card_path, identity)
        recovery_plan = plan[:2]
        require(len(recovery_plan) == 2, 'TWO_RECOVERY_BATCHES_REQUIRED')
        if phase in ('crash', 'resume'):
            def fault(name):
                if phase == 'crash' and name == 'after_commit':
                    os._exit(75)
            _, receipt = run_encoding(recovery_plan, prepared['load'], FrozenBackend,
                recovery/'resumed', binding, guard, guard.progress, failpoint=fault)
            atomic_json(recovery/'RESUME.json', receipt)
            return
        guard.progress('ENGINEERING_REPLAY_COMPLETE', complete_roles=['NORMAL', 'HTTP', 'UDP'])
        before = time.monotonic()
        backend = FrozenBackend()
        model_load_seconds = time.monotonic()-before
        timings = throughput(plan, prepared['load'], backend, guard, guard.progress)
        run_encoding(recovery_plan, prepared['load'], lambda: backend,
                     recovery/'baseline', binding, guard, guard.progress)
        del backend
        gc.collect()
        for mode, expected_code in (('crash', 75), ('resume', 0)):
            command = [sys.executable, '-X', 'utf8', '-B', str(HERE/'engineering_gate.py'),
                '--card', str(card_path), '--authorization', str(auth_path), '--runtime', str(runtime_path),
                '--output', str(output), '--phase', mode, '--attempt-id', attempt_id,
                '--deadline-monotonic', str(deadline)]
            code = bounded_process(command, recovery/('RECOVERY_'+mode+'.log'), deadline,
                on_exit=lambda pid: cleanup_child_scratch(recovery/('SCRATCH_'+mode+'.json'), scratch_root, output, pid))
            require(code == expected_code, 'ENGINEERING_RECOVERY_CHILD_EXIT:'+mode+':'+str(code))
        original = committed_files(recovery/'baseline')
        resumed = committed_files(recovery/'resumed')
        require(original == resumed, 'ENGINEERING_RECOVERY_NOT_BYTE_IDENTICAL')
        resume_receipt = read(recovery/'RESUME.json')
        require(resume_receipt['reused_rows'] == len(recovery_plan[0]['uids'])
                and resume_receipt['new_rows'] == len(recovery_plan[1]['uids']), 'RECOVERY_REUSE_EXACT')
        source_parity = source_cached_head_parity(guard)
        synthetic = synthetic_distances(guard)
        guard()
        receipt = dict(schema='EDGE_FORMAL_WORKER_ENGINEERING_GATE_RECEIPT_V1', status='PASS',
            scope=SCOPE, card_sha256=sha(card_path), runtime_identity=identity,
            input_binding=prepared['input_binding'], complete_roles=['NORMAL', 'HTTP', 'UDP'],
            logical_spool_rows=len(prepared['headers']), shape_count=len(plan),
            model_load_seconds=model_load_seconds, throughput=timings,
            recovery=dict(actual_process_exit=75, phase='after_commit', batches=2, attempt_id=attempt_id,
                committed_files_byte_identical=True, committed_files=len(original),
                reused_rows=resume_receipt['reused_rows'], new_rows=resume_receipt['new_rows']),
            source_cached_head_parity=source_parity,
            replay_coverage={role: read(output/'spools'/role/'REPLAY_COVERAGE.json')
                             for role in ('NORMAL', 'HTTP', 'UDP')},
            synthetic_distance=synthetic, elapsed_seconds=time.monotonic()-guard.started,
            max_tree_rss_bytes=guard.max_rss, external_quality_computed=False,
            output_disk_bytes_60s_sampled_max=guard.max_output_disk_bytes,
            scratch_disk_bytes_60s_sampled_max=guard.max_scratch_disk_bytes,
            disk_peak_scope='60s sampled maxima, not strict instantaneous peaks',
            external_e3_exported=False,
            external_e3_scope='Recovery-only encoded batches retained on HPC; no local export or quality evaluation',
            evaluation_authorized=False,
            automatic_resubmit=False, automatic_extension=False)
        atomic_json(output/'ENGINEERING_GATE_RECEIPT.json', receipt)
        guard.progress('ENGINEERING_GATE_PASS', external_quality_computed=False)
    except BaseException as exc:
        atomic_json(output/'ENGINEERING_STOP.json', dict(scope=SCOPE,
            reason=type(exc).__name__+':'+str(exc), complete_roles_preserved=True,
            partial_roles_reusable=False, external_quality_computed=False, automatic_resubmit=False))
        raise
    finally:
        import shutil
        require(scratch.parent == scratch_root and scratch.name.startswith('edge-gate-owned-')
                and not scratch.is_symlink(), 'ENGINEERING_SCRATCH_CLEANUP_SCOPE')
        shutil.rmtree(scratch)


def run(card_path, auth_path, runtime_path, output):
    """Top-level watchdog includes all replay/encoding/recovery/distance work."""
    started = time.monotonic()
    require_engineering_authorization(card_path, auth_path)
    require(platform.system() == 'Linux', 'ENGINEERING_LINUX_ONLY')
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    deadline = started+7200-30  # reserve for kill, stop receipt and cleanup
    command = [sys.executable, '-X', 'utf8', '-B', str(HERE/'engineering_gate.py'),
        '--card', str(card_path), '--authorization', str(auth_path), '--runtime', str(runtime_path),
        '--output', str(output), '--phase', 'main', '--deadline-monotonic', str(deadline)]
    try:
        require(bounded_process(command, output/'ENGINEERING_WORKER.log', deadline) == 0,
                'ENGINEERING_WORKER_FAILED')
    except BaseException as exc:
        atomic_json(output/'ENGINEERING_SUPERVISOR_STOP.json', dict(scope=SCOPE,
            reason=type(exc).__name__+':'+str(exc), elapsed_seconds=time.monotonic()-started,
            external_quality_computed=False, automatic_resubmit=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--card', type=Path, required=True)
    parser.add_argument('--authorization', type=Path, required=True)
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--phase', choices=('main', 'crash', 'resume'))
    parser.add_argument('--deadline-monotonic', type=float)
    parser.add_argument('--attempt-id')
    args = parser.parse_args()
    if args.phase is None:
        require(args.deadline_monotonic is None and args.attempt_id is None, 'INTERNAL_OPTIONS_WITHOUT_PHASE')
        run(args.card, args.authorization, args.runtime, args.output)
    else:
        require(args.deadline_monotonic is not None, 'CHILD_ABSOLUTE_DEADLINE_REQUIRED')
        require(args.phase == 'main' or args.attempt_id is not None, 'RECOVERY_ATTEMPT_REQUIRED')
        execute(args.card, args.authorization, args.runtime, args.output, args.deadline_monotonic,
                args.phase, args.attempt_id)
