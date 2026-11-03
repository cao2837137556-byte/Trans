"""One-shot, source-only memory revision validation using stopped V3 assets.

No optimizer, CAL, target loader, experiment resume, or write to V3 is allowed.
Outputs live only in this diagnostic's new source_validation directory.
"""
import datetime
import argparse
import gc
import gzip
import hashlib
import json
import os
import shutil
from pathlib import Path
import sys
import threading
import time
import traceback
from array import array
from collections import defaultdict

HERE = Path(__file__).resolve().parent
ROOT = HERE/'staging'
PACKAGE = Path('runs/learned_onboarding_v1_20261023')
OLD_ROOT = Path('/srv/paper04/learned_onboarding_20261024_v3')
OLD_PACKAGE = OLD_ROOT/PACKAGE
FIT = OLD_PACKAGE/'results/fit'
ASSETS = OLD_PACKAGE/'results/source_assets'
CONFIG = OLD_PACKAGE/'deployment_20261024/remote_config.json'
OUT = HERE/'source_validation'
RSS_LIMIT = 8*1024**3
TIME_LIMIT = 3600
OUTPUT_LIMIT = 2*1024**3
START = time.monotonic()
PEAK = 0
PHASE = 'starting'
STOP = threading.Event()
sys.dont_write_bytecode = True
for key in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[key] = '4'
sys.path.insert(0, str(ROOT/'repo/ood'))
sys.path.insert(0, str(ROOT/PACKAGE/'src'))


def write(name, value):
    target = OUT/name
    temporary = target.with_suffix(target.suffix+'.tmp')
    with temporary.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(temporary, target)


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def verify_revision_manifest():
    manifest_path = ROOT/'MEMORY_REVISION_MANIFEST.json'
    with manifest_path.open(encoding='utf-8-sig') as stream:
        manifest = json.load(stream)
    if not isinstance(manifest.get('files'), dict) or not manifest['files']:
        raise ValueError('MEMORY_REVISION_MANIFEST_FILES')
    for name, item in manifest['files'].items():
        target = (ROOT/name).resolve()
        if ROOT.resolve() not in target.parents:
            raise ValueError('MEMORY_REVISION_MANIFEST_PATH_ESCAPE:'+name)
        if sha(target) != item['sha256'] or target.stat().st_size != item['bytes']:
            raise ValueError('MEMORY_REVISION_MANIFEST_IDENTITY:'+name)
    return sha(manifest_path)


def tick(phase, **extra):
    global PHASE
    PHASE = phase
    value = dict(status='RUNNING_SOURCE_DIAGNOSTIC', phase=phase,
        elapsed_seconds=time.monotonic()-START, peak_process_tree_rss=PEAK,
        production_optimizer_updates=0, target_queries_read=0, **extra)
    write('status.json', value)
    print(json.dumps(value, ensure_ascii=False), flush=True)


def guard():
    global PEAK
    import psutil
    process = psutil.Process()
    while not STOP.is_set():
        total = 0
        for child in [process]+process.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.NoSuchProcess:
                pass
        PEAK = max(PEAK, total)
        output_bytes = 0
        for path in OUT.rglob('*'):
            try:
                if path.is_file():
                    output_bytes += path.stat().st_size
            except FileNotFoundError:
                pass  # Atomic status replacement between discovery and stat.
        free = shutil.disk_usage(HERE).free
        minimum_free = 2*max(0, OUTPUT_LIMIT-output_bytes)
        if (total > RSS_LIMIT or time.monotonic()-START > TIME_LIMIT or
                output_bytes > OUTPUT_LIMIT or free < minimum_free):
            write('RESOURCE_EXCEPTION.json', dict(status='EXCEPTION_STOP', phase=PHASE,
                rss=total, rss_limit=RSS_LIMIT, elapsed_seconds=time.monotonic()-START,
                time_limit_seconds=TIME_LIMIT, output_bytes=output_bytes,
                output_limit_bytes=OUTPUT_LIMIT, disk_free_bytes=free,
                minimum_disk_free_bytes=minimum_free, automatic_retry=False))
            os._exit(73)
        STOP.wait(.2)


def mmap_touch(values, np):
    checksum = 0.
    for start in range(0, len(values), 4096):
        checksum += float(np.sum(values[start:start+4096], dtype=np.float64))
    return checksum


def legacy_record(store, i, view, scores, statistics, folds, auxiliary_statistics):
    """V3 constructor, independent of CompactTaskRecord field lookup."""
    row = store.rows[i]
    own = store.key_index[(row['partition'], row['device'], row['protocol'])]
    columns = ([own] if row['label'] == 0 else
               [j for j, eligible in enumerate(store.eligible[i]) if eligible])
    columns = [j for j in columns if store.eligible[i, j]]
    if not columns:
        return None
    stat = statistics[folds[row['uid']]['fold']] if view == 0 else auxiliary_statistics[row['device']]
    record = {key: row[key] for key in ('uid', 'device', 'label', 'protocol', 'activity',
        'capture_id', 'source_sha256', 'session_id', 'component_id')}
    record.update(view=view, fit_role='FIT', partition='LEARN',
        fold=folds[row['uid']]['fold'], group=folds[row['uid']]['group'],
        source_slot=i, own_bank=bool(store.eligible[i, own]), eligible=True,
        score=float(scores[view][i]), t=stat['t'], s=stat['s'],
        banks=__import__('pipeline').BankCandidates(store, view, i, columns))
    return record


def annotated_legacy(record, hard):
    """V3 per-row mining annotations, including both insertion orders."""
    import math
    if record['s'] <= 0:
        record['hard_difficulty'] = None
        record['hard_worst_bank_key'] = None
    else:
        margin = (record['score']-record['t'])/record['s']
        if record['label'] == 0:
            record['hard_worst_bank_key'] = None
            difficulty = margin
        else:
            banks = sorted(record['banks'], key=lambda b: b.get('bank_key', ()))
            worst = max(banks, key=lambda b: (1.-b['d2'])*math.exp(-abs(margin)))
            record['hard_worst_bank_key'] = worst.get('bank_key')
            difficulty = (1.-worst['d2'])*math.exp(-abs(margin))
        record['hard_difficulty'] = float(difficulty)
    record['hard'] = (record['view'], record['uid']) in hard
    return record


def main(argv=None):
    global OLD_ROOT, OLD_PACKAGE, FIT, ASSETS, CONFIG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old-root', type=Path, default=OLD_ROOT,
                        help='Stopped V3 root, read-only; defaults to the registered V3 path')
    args = parser.parse_args(argv)
    OLD_ROOT = args.old_root.resolve()
    OLD_PACKAGE = OLD_ROOT/PACKAGE
    FIT = OLD_PACKAGE/'results/fit'
    ASSETS = OLD_PACKAGE/'results/source_assets'
    CONFIG = OLD_PACKAGE/'deployment_20261024/remote_config.json'
    if OLD_ROOT == OUT.resolve() or OLD_ROOT in OUT.resolve().parents or OUT.resolve() in OLD_ROOT.parents:
        raise ValueError('DIAGNOSTIC_OUTPUT_OVERLAPS_OLD_ROOT')
    OUT.mkdir(exist_ok=False)
    threading.Thread(target=guard, daemon=True).start()
    revision_manifest_hash = verify_revision_manifest()
    import numpy as np
    import common as c
    import learning
    import pipeline
    import source_inputs
    import tasks
    from task_storage import CompactTaskRecord

    source_code_hashes = {path.name: sha(path) for path in sorted((ROOT/PACKAGE/'src').glob('*.py'))}

    # Refuse a missing extracted member before prepare_source can write it.
    # Its normal existing-member branch still hashes archive bytes and files.
    c.require(ASSETS.is_dir(), 'ORIGINAL_SOURCE_ASSETS_MISSING')
    config = c.read(CONFIG)
    inventory = source_inputs.archive_members(config['source']['archive'], verify=True)
    for name in source_inputs.ARCHIVE_WANTED:
        if name in inventory:
            c.require((ASSETS/name).is_file(), 'READONLY_ASSET_NOT_ALREADY_EXTRACTED:'+name)
    protected = sorted(p for p in ASSETS.rglob('*') if p.is_file())
    protected += [FIT/name/'final.pt' for name in ('AUX_G0', 'AUX_G1')]
    geometry_folder = FIT/'source_geometry'
    protected += sorted(p for p in geometry_folder.iterdir() if p.is_file())
    protected_hashes = {str(p): sha(p) for p in protected}
    c.check_spec()
    learning._setup()
    tick('prepare_source_existing_v3_assets')
    source = source_inputs.prepare_source(config['source'], output_dir=ASSETS, validate_only=False)
    c.require(source['binding'] == c.read(FIT/'input_binding.json'), 'V3_SOURCE_BINDING_CHANGED')
    tick('touch_full_original_source_mappings')
    touch = dict(e3=mmap_touch(source['e3'], np), q14=mmap_touch(source['q14'], np))
    fi = np.asarray(source['fit_indices'], np.int64)
    rows = [source['rows'][int(i)] for i in fi]
    c.require(len(rows) == 617908, 'FIT_ROW_COUNT')
    z, q = pipeline.IndexedRows(source['e3'], fi), pipeline.IndexedRows(source['q14'], fi)
    folds = tasks.dependency_folds(rows)
    old_folds = c.read(FIT/'dependency_folds.json')
    c.require(folds == old_folds, 'V3_FOLD_DRIFT')
    del old_folds
    gc.collect()
    tick('formal_scores_and_statistics')
    formal_scores = np.asarray(source['score_main'](fi), np.float64)
    statistics = tasks.fit_statistics(rows, formal_scores, folds)
    aux_scores, split_scores = np.empty(len(rows), np.float64), np.empty(len(rows), np.float64)
    auxiliary, group_receipts = {}, []
    # Keep the source plus final loaded head alive as fit_source does.
    for group_index, devices in enumerate(c.GROUPS):
        name = 'AUX_G'+str(group_index)
        tick('auxiliary_source_scores', head=name)
        checkpoint_path = FIT/name/'final.pt'
        c.verify_seal(FIT/name)
        isolation = c.read(FIT/name/'isolation.json')
        train = np.asarray([i for i, row in enumerate(rows) if row['device'] in devices], np.int64)
        held = np.asarray([i for i, row in enumerate(rows) if row['device'] not in devices], np.int64)
        model, mean, scale, checkpoint = learning.load_auxiliary_head(checkpoint_path)
        train_uids = [rows[int(i)]['uid'] for i in train]
        held_uids = [rows[int(i)]['uid'] for i in held]
        c.require(checkpoint['fit_uids'] == train_uids and
            c.uid_hash(train_uids, ordered=True) == isolation['fit_uid_sha256'] and
            c.uid_hash(held_uids, ordered=True) == isolation['held_uid_sha256'], 'AUX_SOURCE_UID_BINDING')
        fitted = learning.score_auxiliary_head(checkpoint_path,
            pipeline.IndexedRows(z, train), pipeline.IndexedRows(q, train))
        stat = tasks._statistics([rows[int(i)] for i in train], fitted)
        aux_scores[held] = learning.score_auxiliary_head(checkpoint_path,
            pipeline.IndexedRows(z, held), pipeline.IndexedRows(q, held))
        split_scores[held] = learning.score_auxiliary_head(checkpoint_path,
            pipeline.IndexedRows(z, held), pipeline.IndexedRows(q, held), batch_size=127)
        c.require(np.array_equal(aux_scores[held], split_scores[held]), 'AUX_NATIVE_256_127_DRIFT')
        for i in held:
            auxiliary[rows[int(i)]['device']] = stat
        group_receipts.append(dict(head=name, training_rows=len(train), held_rows=len(held),
            checkpoint_sha256=sha(checkpoint_path), statistics=stat, native_batches_bitwise=True))

    tick('open_v3_geometry_readonly')
    store = pipeline.GeometryStore.__new__(pipeline.GeometryStore)
    store.folder, store.rows, store.e3, store.q14, store.refs = geometry_folder, rows, z, q, source['references']
    index = c.read(geometry_folder/'qualification_index.json')
    c.require(index['ordered_query_uid_sha256'] == c.uid_hash([r['uid'] for r in rows], ordered=True),
              'GEOMETRY_ORDERED_UID_BINDING')
    c.require(index['references'] == store.refs['rows'] and
              index['reference_uids'] == store.refs['feature_uids'], 'GEOMETRY_REFERENCE_BINDING')
    store.keys = [tuple(key) for key in index['bank_keys']]
    c.require(store.keys == sorted({(r['partition'], r['device'], r['protocol']) for r in store.refs['rows']}),
              'GEOMETRY_BANK_KEYS')
    store.key_index = {key: i for i, key in enumerate(store.keys)}
    store.ref_index = {r['uid']: i for i, r in enumerate(store.refs['rows'])}
    store.bank_ends = {key: next(r['reference_end'] for r in store.refs['rows']
        if (r['partition'], r['device'], r['protocol']) == key) for key in store.keys}
    store.bank_frame_ends = {(r['partition'], r['device'], r['capture_id']): r['bank_end_frame']
                            for r in store.refs['rows'] if 'bank_end_frame' in r}
    store.reason_codes = index['reason_codes']
    store.eligible = np.load(geometry_folder/'eligible.npy', mmap_mode='r', allow_pickle=False)
    store.count = np.load(geometry_folder/'components.npy', mmap_mode='r', allow_pickle=False)
    store.reasons = np.load(geometry_folder/'reasons.npy', mmap_mode='r', allow_pickle=False)
    store.views = {view: tuple(np.load(geometry_folder/(prefix+'_'+str(view)+'.npy'),
                  mmap_mode='r', allow_pickle=False) for prefix in ('pairs', 'distances')) for view in (0, 1)}
    n, k = len(rows), len(store.keys)
    c.require(store.eligible.shape == store.count.shape == store.reasons.shape == (n, k), 'GEOMETRY_SHAPE')
    for view, (pairs, distances) in store.views.items():
        c.require(pairs.shape == (n, k, 2) and distances.shape == (n, k, 2, 2), 'GEOMETRY_VIEW_SHAPE')
        mmap_touch(pairs, np)
        mmap_touch(distances, np)
    for values in (store.eligible, store.count, store.reasons):
        mmap_touch(values, np)
    scores = {0: formal_scores, 1: aux_scores}
    tick('full_two_view_compact_task_records')
    records = store.task_records(scores, statistics, folds, auxiliary,
        lambda **progress: tick('full_two_view_compact_task_records', **progress)
        if progress.get('completed', 0) % 65536 == 0 else None)
    tick('independent_v3_constructor_check', task_count=len(records))
    # Exact UID order and eligibility check independently enumerates all source rows.
    source_order = sorted(range(len(rows)), key=lambda i: rows[i]['uid'])
    position = 0
    for view in (0, 1):
        for i in source_order:
            expected = legacy_record(store, i, view, scores, statistics, folds, auxiliary)
            if expected is None:
                continue
            actual = records[position]
            c.require(list(expected) == list(actual) and all(expected[key] == actual[key]
                for key in expected if key != 'banks'), 'V3_BASE_TASK_VALUE_OR_ORDER_DRIFT')
            c.require(expected['banks'].columns == actual['banks'].columns, 'V3_BANK_COLUMNS_DRIFT')
            position += 1
    c.require(position == len(records), 'V3_TASK_COUNT_DRIFT')
    del source_order, expected, actual
    gc.collect()

    # Full grouped legacy dictionary oracle bounds temporary memory by one
    # registered group; no row, candidate, tie, group or weight is omitted.
    groups = defaultdict(lambda: array('I'))
    for i, task in enumerate(records):
        key = (task['view'], task['fold'], task['device'], task['protocol'], task['label'])
        groups[key].append(i)
    def legacy_h_oracle(active_scores):
        result, receipt = set(), []
        for key in sorted(groups):
            old = [legacy_record(store, records[int(i)]['source_slot'], key[0],
                      active_scores, statistics, folds, auxiliary) for i in groups[key]]
            selected, group_receipt = tasks.mine_hard_tasks(old)
            result.update(selected)
            receipt.extend(group_receipt)
            del old, selected, group_receipt
        return result, receipt

    tick('alternate_127_full_h_and_legacy_oracle')
    for task in records:
        if task['view'] == 1:
            task['score'] = float(split_scores[task['source_slot']])
    alternate_h, alternate_receipt = tasks.mine_hard_tasks(records)
    oracle_h, oracle_receipt = legacy_h_oracle({0: formal_scores, 1: split_scores})
    c.require(alternate_h == oracle_h and alternate_receipt == oracle_receipt, 'V3_ALTERNATE_H_DRIFT')
    del oracle_h, oracle_receipt
    tick('primary_256_full_h_and_legacy_oracle')
    for task in records:
        if task['view'] == 1:
            task['score'] = float(aux_scores[task['source_slot']])
    hard, hard_receipt = tasks.mine_hard_tasks(records)
    c.require(hard == alternate_h, 'QUERY_BATCH_H_SET_DRIFT')
    oracle_h, oracle_receipt = legacy_h_oracle(scores)
    c.require(hard == oracle_h and hard_receipt == oracle_receipt, 'V3_PRIMARY_H_DRIFT')
    del alternate_h, alternate_receipt, oracle_h, oracle_receipt, split_scores, groups
    for task in records:
        task['hard'] = (task['view'], task['uid']) in hard
    gc.collect()
    tick('full_source_residual_signal')
    signal = tasks.residual_signal(records)
    write('SOURCE_SIGNAL.json', signal)

    tick('all_task_json_streaming_v3_exact_comparison')
    def encode(value):
        return json.dumps(value, ensure_ascii=False, allow_nan=False,
            default=lambda x: x.artifact() if isinstance(x, (CompactTaskRecord, pipeline.BankCandidates))
                              else c._json_default(x))+'\n'
    new_digest, old_digest = hashlib.sha256(), hashlib.sha256()
    container_sizes = None
    with gzip.open(OUT/'source_tasks_validation.jsonl.gz', 'wt', encoding='utf-8', newline='\n') as stream:
        for i, actual in enumerate(records):
            expected = annotated_legacy(legacy_record(store, actual['source_slot'], actual['view'],
                scores, statistics, folds, auxiliary), hard)
            original_json, compact_json = encode(expected), encode(actual)
            c.require(original_json == compact_json, 'V3_TASK_JSON_DRIFT:'+actual['uid'])
            old_digest.update(original_json.encode('utf-8'))
            new_digest.update(compact_json.encode('utf-8'))
            stream.write(compact_json)
            if container_sizes is None:
                container_sizes = dict(legacy_dict_bytes=sys.getsizeof(expected), compact_record_bytes=sys.getsizeof(actual))
            if (i+1) % 65536 == 0:
                tick('all_task_json_streaming_v3_exact_comparison', completed=i+1, total=len(records))
    del actual, expected, original_json, compact_json
    gc.collect()
    tick('full_sampling_distribution_and_training_preparation_peak')
    ordered, p0, ph = tasks.build_task_distribution(records, hard)
    # Independent legacy probability construction uses source-row metadata;
    # these hierarchy fields are exactly the ones the old dictionary copied.
    legacy_p0, legacy_ph = np.zeros(len(ordered), np.float64), np.zeros(len(ordered), np.float64)
    for view in (0, 1):
        for label in (0, 1):
            indices = [i for i, task in enumerate(ordered) if task['view'] == view and task['label'] == label]
            basic = tasks.hierarchical_weights([rows[ordered[i]['source_slot']] for i in indices])
            legacy_p0[indices] = .25*basic
            hard_indices = [i for i in indices if (view, ordered[i]['uid']) in hard]
            if hard_indices:
                legacy_ph[indices] = .125*basic
                legacy_ph[hard_indices] += .125*tasks.hierarchical_weights(
                    [rows[ordered[i]['source_slot']] for i in hard_indices])
            else:
                legacy_ph[indices] = .25*basic
    c.require(np.array_equal(p0, legacy_p0) and np.array_equal(ph, legacy_ph), 'V3_FULL_DISTRIBUTION_DRIFT')
    del indices, hard_indices, basic
    # train_modules repeats distribution construction while caller-owned arrays
    # remain alive. Retain both copies to exercise that real peak.
    training_order, training_p0, training_ph = tasks.build_task_distribution(ordered, hard)
    c.require(all(a is b for a, b in zip(ordered, training_order)), 'SECOND_DISTRIBUTION_ORDER')
    c.require(np.array_equal(p0, training_p0) and np.array_equal(ph, training_ph), 'SECOND_DISTRIBUTION_VALUES')
    uniforms = tasks.uniform_stream(4000, 256)
    schedules = {name: tasks.sample_indices(probability, uniforms) for name, probability in
                 (('L_STANDARD', training_p0), ('L_HARD', training_ph), ('L_QUERY_ONLY', training_ph))}
    for name, probability in (('L_STANDARD', legacy_p0), ('L_HARD', legacy_ph), ('L_QUERY_ONLY', legacy_ph)):
        c.require(np.array_equal(schedules[name], tasks.sample_indices(probability, uniforms)),
                  'V3_FULL_UNIFORM_SCHEDULE_DRIFT:'+name)
    c.require(np.array_equal(schedules['L_HARD'], schedules['L_QUERY_ONLY']), 'PAIRED_UNIFORM_SCHEDULE')
    tick('batch_features_labels_256_127_and_v3_oracle')
    probes = []
    for start in (0, 256, 511*256, 3999*256):
        for arm, schedule in schedules.items():
            selected = schedule[start:start+256]
            compact = store.batch(training_order, selected)
            old = [annotated_legacy(legacy_record(store, training_order[int(i)]['source_slot'],
                training_order[int(i)]['view'], scores, statistics, folds, auxiliary), hard) for i in selected]
            legacy = store.batch(old, np.arange(len(old)))
            # Bank width may differ by sub-batch; pad with the exact fallback.
            split_parts = [store.batch(training_order, selected[j:j+127]) for j in range(0, len(selected), 127)]
            for key in compact:
                c.require(np.array_equal(compact[key], legacy[key]), 'V3_BATCH_VALUE_DRIFT:'+key)
                if compact[key].ndim > 1:
                    padded = []
                    for part in split_parts:
                        value = part[key]
                        shape = (len(value), compact[key].shape[1])+value.shape[2:]
                        out = np.zeros(shape, dtype=value.dtype)
                        out[:, :value.shape[1]] = value
                        padded.append(out)
                    split = np.concatenate(padded)
                else:
                    split = np.concatenate([part[key] for part in split_parts])
                c.require(np.array_equal(compact[key], split), 'BATCH_256_127_FEATURE_DRIFT:'+key)
            probes.append(dict(arm=arm, update=start//256+1, rows=len(selected),
                features_bitwise_v3=True, query_batch_256_127_bitwise=True))
    tick('protected_v3_assets_final_identity_check')
    c.require(all(sha(path) == expected for path, expected in protected_hashes.items()), 'PROTECTED_V3_INPUT_CHANGED')
    c.require(source_code_hashes == {path.name: sha(path) for path in sorted((ROOT/PACKAGE/'src').glob('*.py'))},
              'SOURCE_CODE_CHANGED_DURING_VALIDATION')
    c.require(verify_revision_manifest() == revision_manifest_hash, 'MEMORY_REVISION_MANIFEST_CHANGED')
    write('SOURCE_VALIDATION.json', dict(schema='paper04-learned-memory-source-validation-v4',
        status='PASS_FULL_SOURCE_MEMORY_NO_TRAINING',
        recorded_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        source_code_sha256=source_code_hashes,
        memory_revision_manifest_sha256=revision_manifest_hash,
        source_identity={key: source['binding'][key] for key in ('input_manifest_sha256',
            'feature_manifest_sha256', 'spool_sha256', 'learn_feature_sha256',
            'q14_sha256', 'head_sha256', 'normalizer_sha256')},
        runtime=c.environment(), full_original_source_rows=len(source['rows']), fit_rows=len(rows),
        task_count=len(records), tasks=len(records), full_workload_complete=True,
        hard_count=len(hard), groups=group_receipts, source_signal=signal,
        source_mapping_touch_checksums=touch, legacy_task_json_sha256=old_digest.hexdigest(),
        compact_task_json_sha256=new_digest.hexdigest(), task_container_sizes=container_sizes,
        full_h_two_batches_exact=True, full_legacy_h_oracle_exact=True,
        full_legacy_sampling_probabilities_and_schedules_exact=True,
        second_training_distribution_peak_exercised=True, schedule_rows_per_arm=len(uniforms),
        schedules_sha256={name: hashlib.sha256(value.tobytes()).hexdigest() for name, value in schedules.items()},
        batch_probes=probes, peak_process_tree_rss=PEAK, rss_guard_bytes=RSS_LIMIT,
        diagnostic_peak_includes_legacy_group_materialization=True,
        output_limit_bytes=OUTPUT_LIMIT,
        elapsed_seconds=time.monotonic()-START, time_limit_seconds=TIME_LIMIT,
        protected_files=len(protected_hashes), protected_files_unchanged=True,
        production_optimizer_updates=0, cal_queries_scored=0, target_queries_read=0,
        original_experiment_resumed=False, automatic_retry=False,
        remaining=['three module optimizer training', 'CAL lambda selection', 'A/B target evaluation']))
    STOP.set()
    write('status.json', dict(status='PASS_FULL_SOURCE_MEMORY_NO_TRAINING',
        phase='complete', peak_process_tree_rss=PEAK, elapsed_seconds=time.monotonic()-START))
    print('PASS: complete FIT task path, no optimizer/CAL/target or V3 writes', flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException:
        STOP.set()
        if OUT.is_dir():
            write('VALIDATION_EXCEPTION.json', dict(status='EXCEPTION_STOP', phase=PHASE,
                traceback=traceback.format_exc(), elapsed_seconds=time.monotonic()-START,
                peak_process_tree_rss=PEAK, automatic_retry=False))
        raise
