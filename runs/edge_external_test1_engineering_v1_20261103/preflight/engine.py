"""Bounded engineering inference; frozen core and no external quality metrics.

The subset reference bank is an interface fixture, not an external evaluation.
This file never optimizes, fits, changes cuts, or chooses rows using scores.
"""
from collections import defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
OOD = ROOT / 'repo/ood'
sys.path.insert(0, str(OOD))


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 ** 2), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def c5(raw, support, q14, freeze, p=3):
    """Independent adapter of frozen arithmetic, verified against sealed audit."""
    import numpy as np
    import constrained_onboarding_core_v3 as core
    raw = np.asarray(raw, dtype=np.float64)
    s = np.asarray(support, dtype=np.float64)
    require(p in (1, 3), 'ENGINEERING_P_ONLY_ONE_AND_FROZEN_THREE')
    require(s.shape == (len(raw),) and np.isfinite(s).all() and
            np.all((s >= 0) & (s <= 1)), 'SUPPORT_RANGE')
    g = s.copy() if p == 1 else np.where(s > 0, 1. - np.power(1. - s, 3), 0.)
    result = raw.copy()
    active = g > 0
    scales = freeze['calibration']['scales']['scales']
    for j in range(3):
        result[active, j] = raw[active, j] - (.25 * scales[j]) * g[active]
    guard = (q14[:, 0] == 1) & (q14[:, 2] == 1) & (q14[:, 5] == 0)
    result[guard] = raw[guard]
    cuts = freeze['calibration']['cuts']
    decisions = np.column_stack((result > cuts['cuts'],
        core.ordered_ensemble(result) > cuts['ensemble_cut']))
    return result, decisions


def frozen_assets():
    freeze_path = ROOT / 'runs/c5_method_freeze_v1_20261102/METHOD_FREEZE.json'
    require(sha(freeze_path) == 'ee11f25079cd03ee8b9d6dbbafd67e7fc96dd4402373808fc1c0b9f53b5c05e7',
            'C5_FREEZE_SHA')
    frozen = read(freeze_path)
    spec = read(ROOT / 'runs/history_sample_coverage_c4_batch_resume_v1_20261102/config/ASSETS.json')
    pins = {}
    for category in ('calibration', 'heads'):
        def collect(value):
            if isinstance(value, dict):
                if 'path' in value and 'sha256' in value:
                    path = ROOT / value['path']
                    require(sha(path) == value['sha256'], 'FROZEN_ASSET_SHA:' + str(path))
                    pins[value['path']] = value['sha256']
                else:
                    for entry in value.values():
                        collect(entry)
        collect(spec[category])
    import numpy as np
    with np.load(ROOT / spec['calibration']['normalizer']['path'], allow_pickle=False) as saved:
        normalizer = saved['mean'].copy(), saved['scale'].copy()
    return frozen, spec, normalizer, pins


def score_heads(e3, q14, spec, normalizer):
    import numpy as np
    import torch
    import query_tail_core_v2 as head_core
    import constrained_onboarding_query_tail_adapter_v2 as adapter
    design = read(ROOT / spec['heads']['design']['path'])
    outputs = []
    for seed in (27, 127, 227):
        endpoint = spec['heads']['endpoints'][str(seed)]
        path = ROOT / endpoint['head.npz']['path']
        adapter._endpoint(path.parent, 'QUERY_TAIL', seed, design, normalizer)
        model = head_core.classifier(seed, 782)
        with np.load(path, allow_pickle=False) as saved:
            require(set(saved.files) == set(model.state_dict()), 'HEAD_KEYS')
            model.load_state_dict({key: torch.from_numpy(saved[key].copy()) for key in saved.files})
        model.eval().requires_grad_(False)
        outputs.append(head_core.scores(model, e3, q14, np.arange(len(e3)), normalizer, 782))
    return np.column_stack(outputs).astype(np.float64)


def encode_snapshots(entries, runtime, progress):
    import numpy as np
    import torch
    import continuous_input_v3 as inp
    from continuous_features_v3 import tokenize, verify_batch, tensor_hash
    from constrained_onboarding_reference_v2 import reference_descriptor, query_descriptor
    encoder_root = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'
    sys.path.insert(0, str(encoder_root))
    from hnr.encoding import new_encoder, physical_batch
    config = read(encoder_root / 'config/EXECUTION.json')['encoder']
    # Paths are resolved from this checkout for a portable same-delivery worker.
    config['runtime_root'] = str(ROOT / 'runs/diagnostics_c5_step2_package_v1_20261025/local_benchmark_v1/runtime')
    config['normalizer'] = str(ROOT / 'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/normalizer.npz')
    config['runtime_files_manifest']['path'] = str(encoder_root / 'config/ENCODER_RUNTIME_FILES.json')
    torch.set_num_threads(1)
    torch.set_num_interop_threads(1)
    torch.use_deterministic_algorithms(True)
    encoder, identity = new_encoder(config)
    # Existing runtime sets four threads internally; bound it again for this run.
    torch.set_num_threads(1)
    embed, _, model, tokenizer, collator = encoder
    groups = defaultdict(list)
    examples = {}
    q14 = np.empty((len(entries), 14), dtype=np.float32)
    for i, entry in enumerate(entries):
        row, body = entry['row'], entry['body']
        fn = reference_descriptor if row['use'] == 'REFERENCE' else query_descriptor
        q14[i] = fn(body, row)[0]
        require(np.array_equal(q14[i], np.asarray(entry['q14'], dtype=np.float32)), 'DESCRIPTOR_PARITY')
        example = tokenize(tokenizer, body['flow'])
        inp.verify_tokenized(body['flow'], body['provenance'], example)
        shape = row['protocol'], max(example['dataset_burst_sizes']) + 1, len(example['dataset_burst_sizes'])
        groups[shape].append(i)
        examples[i] = example
    e3 = np.empty((len(entries), 768), dtype=np.float32)
    batches = []
    hash_outputs = {}
    duplicate_inputs = 0
    duplicate_outputs_exact = True
    input_hashes = []
    for shape, indices in sorted(groups.items()):
        indices.sort(key=lambda i: entries[i]['uid'])
        for start in range(0, len(indices), 16):
            ix = indices[start:start + 16]
            batch_examples = [examples[i] for i in ix]
            batch = collator(batch_examples)
            verify_batch(batch_examples, batch)
            actual, physical = physical_batch(batch, len(ix), tensor_hash)
            progress.guard()
            runtime['logical_reserved'] += len(ix)
            runtime['physical_reserved'] += physical
            require(runtime['logical_reserved'] <= 100, 'ENCODING_ROW_HARD_CAP')
            attempt = dict(status='ATTEMPT', batch=len(batches), shape=list(shape),
                logical_rows=len(ix), physical_rows=physical,
                uids=[entries[i]['uid'] for i in ix], logical_reserved=runtime['logical_reserved'],
                physical_reserved=runtime['physical_reserved'])
            with (progress.out / 'ENCODING_BATCH_LEDGER.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(attempt) + '\n')
            progress.save('ENCODE_BATCH_RESERVED', logical_rows=runtime['logical_reserved'],
                          physical_rows=runtime['physical_reserved'])
            before = time.monotonic()
            values = embed.core.e3_forward_batches(model, [actual], 'cpu')
            seconds = time.monotonic() - before
            require(values.shape == (physical, 768) and values.dtype == np.float32 and
                    np.isfinite(values).all(), 'E3_SCHEMA_FINITE')
            if len(ix) == 1:
                identical = all(v.tobytes() == values[0].tobytes() for v in values)
                if not identical:
                    diagnosis = dict(attempt, status='FAIL_SINGLETON_CLONE_OUTPUT', seconds=seconds,
                        input_tensor_sha256=[tensor_hash(actual, j) for j in range(physical)],
                        output_sha256=[hashlib.sha256(v.tobytes()).hexdigest() for v in values],
                        max_absolute_output_difference=float(np.max(np.abs(values - values[:1]))),
                        completed_batches=batches, strict_gate_unchanged=True,
                        backend_adjusted=False, scores_or_quality_computed=False)
                    path = progress.out / 'CLONE_FAILURE_DIAGNOSIS.json'
                    path.write_text(json.dumps(diagnosis, indent=2) + '\n', encoding='utf-8')
                require(identical, 'SINGLETON_CLONES_OUTPUT_EXACT')
            for j, i in enumerate(ix):
                e3[i] = values[j]
                input_hash = tensor_hash(actual, j)
                feature_hash = hashlib.sha256(values[j].tobytes()).hexdigest()
                if input_hash in hash_outputs:
                    duplicate_inputs += 1
                    duplicate_outputs_exact &= hash_outputs[input_hash] == feature_hash
                else:
                    hash_outputs[input_hash] = feature_hash
                input_hashes.append(dict(uid=entries[i]['uid'], input_tensor_sha256=input_hash,
                                         feature_sha256=feature_hash))
            batches.append(dict(shape=list(shape), logical_rows=len(ix), physical_rows=physical,
                                seconds=seconds, singleton_clone_exact=(len(ix) == 1)))
            with (progress.out / 'ENCODING_BATCH_LEDGER.jsonl').open('a', encoding='utf-8') as stream:
                stream.write(json.dumps(dict(attempt, status='COMPLETE', seconds=seconds)) + '\n')
            progress.guard()
    return e3, q14, dict(encoder_identity=identity, batches=batches,
        logical_rows=runtime['logical_reserved'], physical_rows=runtime['physical_reserved'],
        tensor_receipts=input_hashes, distinct_input_tensors=len(hash_outputs),
        repeated_input_tensors=duplicate_inputs,
        repeated_input_outputs_bit_exact=duplicate_outputs_exact if duplicate_inputs else None,
        dedup_enabled=False,
        dedup_scope='Diagnostic only. No metadata/reference/query/component/UID collapsed.')


def source_parity(spec, normalizer, freeze, progress):
    """Consume only 16 already-consumed source CAL rows; no new source fitting."""
    import numpy as np
    source = ROOT / 'runs/c5_kernel_independent_replay_codex_20261102/source_cal'
    pin_paths = ['CAL_FIXED_INPUTS.npz', 'CAL_E3.npy']
    pins = {}
    for name in pin_paths:
        path = source / name
        expected = (source / (name + '.sha256')).read_text(encoding='utf-8-sig').split()[0]
        require(sha(path) == expected, 'SOURCE_PARITY_INPUT_SHA:' + name)
        pins[name] = expected
    with np.load(source / 'CAL_FIXED_INPUTS.npz', allow_pickle=False) as saved:
        q = saved['q14'][:16].copy()
        raw = saved['raw_logits'][:16].copy()
        expected_decisions = saved['raw_decisions'][:16].copy()
        uids = saved['uid'][:16].copy()
    z = np.load(source / 'CAL_E3.npy', mmap_mode='r', allow_pickle=False)[:16].copy()
    actual = score_heads(z, q, spec, normalizer)
    _, pred = c5(actual, np.zeros(16), q, freeze)
    # Runtime and batch shape may change float32 GEMM roundoff. Preserve the
    # observed error separately; never relabel it bit-exact source identity.
    error = float(np.max(np.abs(actual - raw)))
    return dict(rows=16, input_sha256=pins, head_score_bit_exact=np.array_equal(actual, raw),
                max_absolute_score_error=error,
                four_head_decision_exact=bool(np.array_equal(pred, expected_decisions)),
                tolerance_1e_4_pass=bool(np.allclose(actual, raw, atol=1e-4, rtol=0)),
                uid_sha256=hashlib.sha256(('\n'.join(uids) + '\n').encode()).hexdigest(),
                scope='Source CAL saved features through frozen three heads; not raw-to-E3 source parity')


def evaluate_fixture(entries, e3, q14, spec, normalizer, freeze, progress):
    import numpy as np
    import constrained_onboarding_core_v3 as core
    refs = [i for i, entry in enumerate(entries) if entry['row']['use'] == 'REFERENCE']
    queries = [i for i, entry in enumerate(entries) if entry['row']['use'] != 'REFERENCE']
    require(refs and queries, 'BOTH_ROLES_REQUIRED')
    rr = [entries[i]['row'] for i in refs]
    qr = [entries[i]['row'] for i in queries]
    require(len({r['component_id'] for r in rr}) >= 2, 'REAL_FIXTURE_TWO_COMPONENTS_REQUIRED')
    ids = [r['uid'] for r in rr]
    qids = [r['uid'] for r in qr]
    require(not set(ids) & set(qids), 'PREFLIGHT_ROLE_OVERLAP')
    bank = core.ReferenceBank(rr, e3[refs], q14[refs], normalizer,
                             feature_uids=ids, q_uids=ids)
    # A conservative reservation is sufficient for this tiny fixture.
    pairs = sum(sum(r['protocol'] == q['protocol'] for r in rr) for q in qr)
    require(pairs <= 10000, 'PREFLIGHT_PAIR_LIMIT')
    progress.save('DISTANCE_RESERVED', distance_pairs_reserved=pairs)
    found = bank.own(qr, e3[queries], q14[queries], freeze['calibration']['geometry'],
                     feature_uids=qids, q_uids=qids)
    raw = score_heads(e3[queries], q14[queries], spec, normalizer)
    out, decisions = c5(raw, found['support'], q14[queries], freeze)
    audit = load_module('_edge_sealed_c5_arithmetic', ROOT /
        'runs/c5_kernel_independent_replay_codex_20261102/ab/replay.py')
    guard = (q14[queries, 0] == 1) & (q14[queries, 2] == 1) & (q14[queries, 5] == 0)
    expected, expected_pred, _ = audit.calculate(raw, found['support'], guard,
        np.asarray(freeze['calibration']['scales']['scales']), freeze['calibration']['cuts'], 3)
    require(np.array_equal(out, expected) and np.array_equal(decisions, expected_pred), 'C5_FROZEN_ARITHMETIC_PARITY')
    require(np.array_equal(out[guard], raw[guard]), 'GUARD_EXACT_RAW')
    require(np.array_equal(out[found['support'] == 0], raw[found['support'] == 0]), 'ZERO_SUPPORT_EXACT_RAW')
    baseline_dir = Path(__file__).resolve().parents[1] / 'baselines'
    baseline = load_module('_edge_fixed_knn5_baseline', baseline_dir / 'knn5.py')
    calibration = read(baseline_dir / 'SOURCE_CALIBRATION.json')
    baseline_bank = baseline.KNN5Bank(rr, e3[refs], normalizer, feature_uids=ids)
    baseline_result = baseline_bank.distances(qr, e3[queries], feature_uids=qids)
    _, raw_decisions = c5(raw, np.zeros(len(queries)), q14[queries], freeze)
    baseline_cuts = calibration['cuts']
    baseline_pred = baseline.decisions(baseline_result['distance'], raw_decisions, baseline_cuts)
    require(baseline_pred.shape == decisions.shape and baseline_pred.dtype == bool, 'BASELINE_FOUR_CUT_SCHEMA')
    # Full-view commissioning rows may also be selected references. Their
    # original UID remains a query UID and must follow the exact RAW branch.
    # This is a separately exercised real-row replay, never a renamed UID.
    replay_row = dict(rr[0], use='QUERY')
    replay_e3, replay_q14 = e3[refs[:1]], q14[refs[:1]]
    replay_uid = [replay_row['uid']]
    replay_bank = core.ReferenceBank(rr, e3[refs], q14[refs], normalizer,
        feature_uids=ids, q_uids=ids, allow_prebank_history=True)
    replay_support = replay_bank.own([replay_row], replay_e3, replay_q14,
        freeze['calibration']['geometry'], feature_uids=replay_uid, q_uids=replay_uid)
    require(not replay_support['eligible'][0] and replay_support['support'][0] == 0,
            'REAL_PREBANK_REFERENCE_QUERY_REPLAY_SUPPORT')
    replay_raw = score_heads(replay_e3, replay_q14, spec, normalizer)
    replay_out, _ = c5(replay_raw, replay_support['support'], replay_q14, freeze)
    require(np.array_equal(replay_raw, replay_out), 'REAL_PREBANK_REFERENCE_QUERY_REPLAY_RAW')
    replay_knn = baseline_bank.distances([replay_row], replay_e3, feature_uids=replay_uid)
    require(np.isnan(replay_knn['distance'][0]) and replay_knn['reason'][0] == 'REFERENCE_QUERY_REPLAY_RAW',
            'REAL_PREBANK_KNN_REFERENCE_QUERY_REPLAY_RAW')
    evaluation = load_module('_edge_fixed_external_reporting', Path(__file__).resolve().parents[1] / 'evaluation.py')
    metric_rows = [dict(r, scenario=r['source_role']) for r in qr]
    weights = evaluation.class_weights(metric_rows)
    for label in (0, 1):
        label_mask = np.asarray([r['label'] == label for r in metric_rows])
        if label_mask.any():
            require(np.isclose(weights[label_mask].sum(), 1., rtol=0, atol=1e-12), 'REPORTING_WEIGHT_MASS')
    for j in range(4):
        measured = evaluation.measure(metric_rows, decisions[:, j], weights)
        require(set(measured) == {'normal', 'attack_associated'}, 'REPORTING_METRIC_SCHEMA')
        require(sum(group['rows'] for group in measured.values()) == len(metric_rows), 'REPORTING_QUERY_DENOMINATOR')
        require(all(group['alarm_count'] + group['no_alarm_count'] == group['rows']
                    for group in measured.values()), 'REPORTING_COUNT_CONSERVATION')
        protected = evaluation.paired_safety(metric_rows, raw_decisions[:, j], decisions[:, j], weights)
        require(set(protected) == {'status', 'groups', 'independent_official_event_gate'}, 'REPORTING_SAFETY_SCHEMA')
    # Transient metric/gate values are deliberately discarded: this tiny
    # engineering fixture cannot estimate external detection performance.
    # Exercise the unchanged head decision path, but keep all external quality
    # statistics and individual decisions out of the engineering report.
    return dict(reference_rows=len(refs), query_rows=len(queries),
        distinct_reference_components=len({r['component_id'] for r in rr}),
        distance_pairs_reserved=pairs, four_heads_evaluated=True,
        finite_scores=True, finite_support=True, frozen_c5_arithmetic_bit_exact=True,
        zero_support_raw_exact=True, guard_raw_exact=True,
        knn5_baseline_interface_pass=True, knn5_distance_pairs=int(baseline_result['pairs']),
        real_reference_replayed_as_prebank_query_raw_exact=True,
        reporting_weight_metric_safety_interface_pass=True,
        transient_engineering_metrics_discarded=True, external_quality_reported_or_used=False,
        external_decisions_exported=False,
        bank_scope='Fixed small engineering subset, not official external reference bank')
