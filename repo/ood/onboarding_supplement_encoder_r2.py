"""Frozen UID supplement encoder. No training, scoring, CAL or target evaluation.

Benchmark mode records local timing only. Production requires an explicit
approval file bound to the package manifest and exact original104 byte parity.
Snapshots join by UID; disk spooling bounds token memory independently of N.
"""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import threading
import time

import numpy as np

CHECKPOINT_SHA = 'e6237f49ce58840f8bf7d0cafa5ae80f58d05ea158053d031792d0369d7f5105'
_JSON_LOCK = threading.RLock()


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(8*1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def read_rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def write_json(path, value):
    with _JSON_LOCK:
        path = Path(path)
        temp = path.with_suffix(path.suffix+'.tmp')
        temp.write_text(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False)+'\n', encoding='utf-8')
        os.replace(temp, path)


def output_bytes(root):
    total = 0
    pending = [Path(root)]
    while pending:
        folder = pending.pop()
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            if entry.name != 'runtime':
                                pending.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            # Windows DirEntry caches the enumeration metadata,
                            # avoiding a handle that can block os.replace.
                            total += entry.stat(follow_symlinks=False).st_size
                    except FileNotFoundError:
                        continue
        except FileNotFoundError:
            # An atomic status *.tmp or directory can vanish while counting.
            continue
    return total


def checked_file(root, relative):
    path = (Path(root)/relative).resolve()
    require(path.is_relative_to(Path(root).resolve()), 'PACKAGE_PATH_ESCAPE')
    return path


def validate_approval(approval, package_sha):
    require(approval.get('package_sha256') == package_sha
            and approval.get('user_authorized') is True
            and approval.get('scope') in ('SUPPLEMENT_E3_ONLY', 'R2_SUPPLEMENT_AND_SOURCE_CAL'),
            'APPROVAL_SCOPE_OR_IDENTITY')


def verify_package(root):
    root = Path(root)
    manifest = root/'SHA256SUMS'
    seen = set()
    for line in manifest.read_text(encoding='utf-8').splitlines():
        checksum, relative = line.split('  ', 1)
        require(relative not in seen, 'MANIFEST_DUPLICATE')
        seen.add(relative)
        require(sha(checked_file(root, relative)) == checksum, 'PACKAGE_SHA:'+relative)
    actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p != manifest}
    require(actual == seen, 'PACKAGE_MEMBERS_CHANGED')
    return sha(manifest)


def load_dataset(root, spec):
    rows = read_rows(checked_file(root, spec['metadata']))
    uids = [r['uid'] for r in rows]
    require(len(uids) == len(set(uids)), 'METADATA_DUPLICATE_UID')
    with np.load(checked_file(root, spec['q14']), allow_pickle=False) as data:
        quids = data['uid'].tolist()
        q = data['q14'].copy()
    require(len(quids) == len(set(quids)) and q.shape == (len(quids), 14)
            and q.dtype == np.float32 and np.isfinite(q).all(), 'Q14_SCHEMA')
    qby = {u: q[i] for i, u in enumerate(quids)}
    require(set(uids) <= set(qby), 'Q14_UID_COVERAGE')
    return rows, {r['uid']: r for r in rows}, qby


def spool_dataset(root, spec, db, tokenizer, progress):
    from continuous_features_v3 import tokenize
    from continuous_input_v3 import verify_tokenized
    from constrained_onboarding_reference_v1 import reference_descriptor
    rows, by, qby = load_dataset(root, spec)
    seen = set()
    with gzip.open(checked_file(root, spec['snapshots']), 'rt', encoding='utf-8') as f:
        for line in f:
            item = json.loads(line)
            uid = item['uid']
            if uid not in by:
                continue
            require(uid not in seen, 'SNAPSHOT_DUPLICATE_UID')
            body, row = item['body'], by[uid]
            descriptor, _ = reference_descriptor(body, row)
            require(np.array_equal(descriptor, qby[uid]), 'Q14_REPLAY:'+uid)
            example = tokenize(tokenizer, body['flow'])
            verify_tokenized(body['flow'], body['provenance'], example)
            key = (int(row['protocol']), max(example['dataset_burst_sizes'])+1,
                   len(example['dataset_burst_sizes']))
            db.execute('INSERT INTO tokens VALUES(?,?,?,?,?,?)',
                       (spec['name'], uid, *key, json.dumps(example, separators=(',', ':'))))
            seen.add(uid)
            progress(stage='TOKENIZE_'+spec['name'], completed=len(seen), total=len(rows))
    require(seen == set(by), 'SNAPSHOT_UID_COVERAGE')
    db.commit()
    return rows, by, qby


def sample_indices(db, name, limit):
    """Label-free deterministic shape-stratified sample; no target scores."""
    groups = defaultdict(list)
    for uid, proto, width, bursts in db.execute(
            'SELECT uid,proto,width,bursts FROM tokens WHERE name=? ORDER BY proto,width,bursts,uid', (name,)):
        groups[(proto, width, bursts)].append(uid)
    selected = []
    # Include the most expensive token shape as well as prevalent shapes.
    keys = sorted(groups, key=lambda k: (-len(groups[k]), k))
    if keys:
        largest = max(keys, key=lambda k: (k[1]*k[2], k))
        keys.remove(largest)
        keys.insert(0, largest)
    offset = 0
    while len(selected) < limit:
        added = 0
        for key in keys:
            batch = groups[key][offset:offset+16]
            batch = batch[:limit-len(selected)]
            selected.extend(batch)
            added += len(batch)
        if not added:
            break
        offset += 16
    return set(selected), {str(k): len(v) for k, v in groups.items()}


def merge_bank(root, out, spec):
    """Consume the frozen order, with exact reused vectors and no reselection."""
    rows, _, qby = load_dataset(root, spec)
    wanted = [r['uid'] for r in rows]
    vectors, descriptors = {}, {}
    for path in (checked_file(root, spec['existing_bank']), out/(spec['supplement_dataset']+'.npz')):
        with np.load(path, allow_pickle=False) as data:
            ids = data['uid'].tolist()
            e3, q14 = data['e3'], data['q14']
            require(len(ids) == len(set(ids)) and e3.shape == (len(ids), 768)
                    and e3.dtype == np.float32 and np.isfinite(e3).all(), 'MERGE_E3_SCHEMA')
            for i, uid in enumerate(ids):
                require(uid not in vectors, 'EXISTING_SUPPLEMENT_UID_OVERLAP')
                require(uid in qby and np.array_equal(q14[i], qby[uid]), 'MERGE_Q14_IDENTITY')
                vectors[uid], descriptors[uid] = e3[i].copy(), q14[i].copy()
    require(set(vectors) == set(wanted), 'FROZEN_BANK_UID_COVERAGE')
    bankout = out/'banks'/spec['name']
    bankout.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(bankout/'bank.npz', uid=np.asarray(wanted, dtype='<U64'),
                        e3=np.asarray([vectors[u] for u in wanted], dtype=np.float32),
                        q14=np.asarray([descriptors[u] for u in wanted], dtype=np.float32))
    shutil.copyfile(checked_file(root, spec['metadata']), bankout/'references.jsonl.gz')
    write_json(bankout/'receipt.json', dict(status='COMPLETE', rows=len(wanted),
        bank_sha256=sha(bankout/'bank.npz'), metadata_sha256=sha(bankout/'references.jsonl.gz'),
        frozen_selection=True, existing_vectors_unchanged=True, reselection=False))
    return dict(name=spec['name'], rows=len(wanted), bank_sha256=sha(bankout/'bank.npz'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--checkpoint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mode', choices=('benchmark', 'encode'), required=True)
    parser.add_argument('--approval-file')
    args = parser.parse_args(argv)
    root, out = Path(args.package).resolve(), Path(args.output).resolve()
    require(not out.exists() and not out.is_relative_to(root), 'NEW_EXTERNAL_OUTPUT_REQUIRED')
    package_sha = verify_package(root)
    config = json.loads((root/'config.json').read_text(encoding='utf-8'))
    if args.mode == 'encode':
        require(args.approval_file is not None, 'CLOUD_USER_APPROVAL_REQUIRED')
        approval = json.loads(Path(args.approval_file).read_text(encoding='utf-8'))
        validate_approval(approval, package_sha)
    require(sha(args.checkpoint) == CHECKPOINT_SHA, 'CHECKPOINT_SHA')
    out.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    closed = threading.Event()
    latest = dict(status='RUNNING', stage='STARTUP', mode=args.mode, retries=0)
    peak = [0]
    error = []
    def guard():
        import psutil
        rss = psutil.Process().memory_info().rss
        peak[0] = max(peak[0], rss)
        require(rss <= config['limits']['memory_gib']*1024**3, 'RSS_LIMIT')
        require(time.monotonic()-started <= config['limits']['encoding_wall_seconds'], 'WALL_LIMIT')
        require(shutil.disk_usage(out).free >= config['limits']['min_free_gib']*1024**3, 'DISK_FREE_LIMIT')
        require(not (out/'STOP_REQUESTED').exists(), 'USER_STOP_REQUESTED')
        require(not error, 'WATCHDOG_STOP')
    last = [0.]
    def progress(**values):
        with _JSON_LOCK:
            guard()
            latest.update(values)
            if time.monotonic()-last[0] >= 5 or latest['status'] != 'RUNNING':
                last[0] = time.monotonic()
                write_json(out/'status.json', dict(latest, elapsed_seconds=time.monotonic()-started,
                                                  peak_rss_bytes=peak[0], updated_epoch=time.time()))
    def watch():
        while not closed.wait(2):
            try:
                guard()
                used = output_bytes(out)
                require(used < config['limits']['output_gib']*1024**3, 'OUTPUT_LIMIT')
                progress(output_bytes=used)
            except BaseException as exc:
                error.append(repr(exc))
                latest.update(status='EXCEPTION_STOP', error=repr(exc))
                write_json(out/'status.json', latest)
                # Do not let an ongoing long forward exceed a resource budget.
                os._exit(70)
    thread = threading.Thread(target=watch, daemon=True)
    thread.start()
    db = None
    try:
        runtime = out/'runtime'
        shutil.copytree(root/'runtime', runtime)
        weights = runtime/'vendor/netFound-base/model.safetensors'
        if os.name == 'nt':
            os.link(Path(args.checkpoint).resolve(), weights)
        else:
            weights.symlink_to(Path(args.checkpoint).resolve())
        os.environ['HF_HUB_OFFLINE'] = '1'
        os.environ['TRANSFORMERS_OFFLINE'] = '1'
        if args.mode == 'encode':
            import importlib.metadata
            for name, expected in config['production_runtime_versions'].items():
                package_name = name.replace('_', '-')
                actual = importlib.metadata.version(package_name).split('+')[0]
                require(actual == expected, 'PRODUCTION_RUNTIME_VERSION:'+name)
        from legacy_unsw_archival_runtime_v1 import e3_runtime
        from constrained_onboarding_reference_v2 import _environment
        from continuous_features_v3 import verify_batch, tensor_hash
        cold_start = time.monotonic()
        embed, _, model, tokenizer, collator = e3_runtime(runtime)
        startup_seconds = time.monotonic()-cold_start
        write_json(out/'environment.json', _environment())
        db = sqlite3.connect(str(out/'tokens.sqlite'))
        db.execute('CREATE TABLE tokens(name TEXT,uid TEXT,proto INTEGER,width INTEGER,bursts INTEGER,example TEXT,PRIMARY KEY(name,uid))')
        datasets = {}
        spool_start = time.monotonic()
        for spec in config['datasets']:
            datasets[spec['name']] = spool_dataset(root, spec, db, tokenizer, progress)
        db.execute('CREATE INDEX shapes ON tokens(name,proto,width,bursts,uid)')
        db.commit()
        tokenize_seconds = time.monotonic()-spool_start
        benchmarks = []
        source_verified = False
        # The original104 identity gate must precede supplemental production forwards.
        ordered_specs = sorted(config['datasets'], key=lambda s: (not s.get('original104_check', False), s['name']))
        for spec in ordered_specs:
            name = spec['name']
            rows, by, qby = datasets[name]
            check = bool(spec.get('original104_check', False))
            require(check or args.mode == 'benchmark' or source_verified, 'ORIGINAL104_GATE_NOT_PASSED')
            selected, shapes = sample_indices(db, name, len(rows) if check or args.mode == 'encode' else config['benchmark_rows_per_dataset'])
            features = np.empty((len(selected), 768), dtype=np.float32)
            ordered_uids = []
            timings = []
            receipt_path = out/(name+'.tensor_receipts.jsonl.gz')
            with gzip.open(receipt_path, 'xt', encoding='utf-8') as receipt:
                shape_rows = db.execute('SELECT DISTINCT proto,width,bursts FROM tokens WHERE name=? ORDER BY proto,width,bursts', (name,)).fetchall()
                for shape in shape_rows:
                    query = 'SELECT uid,example FROM tokens WHERE name=? AND proto=? AND width=? AND bursts=? ORDER BY uid'
                    pending = []
                    def flush():
                        if not pending:
                            return
                        progress(stage='E3_'+name, completed=len(ordered_uids), total=len(selected))
                        examples = [json.loads(e) for _, e in pending]
                        batch = collator(examples)
                        verify_batch(examples, batch)
                        t = time.monotonic()
                        values = embed.core.e3_forward_batches(model, [batch], 'cpu')
                        seconds = time.monotonic()-t
                        require(isinstance(values, np.ndarray) and values.dtype == np.float32
                                and values.shape == (len(pending), 768) and np.isfinite(values).all(), 'E3_SCHEMA')
                        offset = len(ordered_uids)
                        features[offset:offset+len(pending)] = values
                        timings.append(dict(shape=list(shape), rows=len(pending), seconds=seconds))
                        for j, (uid, _) in enumerate(pending):
                            ordered_uids.append(uid)
                            receipt.write(json.dumps(dict(uid=uid, shape=list(shape), actual_tensor_sha256=tensor_hash(batch, j),
                                feature_sha256=hashlib.sha256(values[j].tobytes()).hexdigest()))+'\n')
                        pending.clear()
                    for uid, example in db.execute(query, (name, *shape)):
                        if uid in selected:
                            pending.append((uid, example))
                            if len(pending) == 16:
                                flush()
                    flush()
            require(len(ordered_uids) == len(selected), 'FEATURE_COVERAGE')
            progress(stage='E3_'+name, completed=len(ordered_uids), total=len(selected))
            parity = None
            if check:
                with np.load(checked_file(root, spec['expected_bank']), allow_pickle=False) as old:
                    old_by = {u: old['e3'][i].copy() for i, u in enumerate(old['uid'].tolist())}
                require(set(old_by) == set(ordered_uids) and len(old_by) == 104, 'ORIGINAL104_COVERAGE')
                mismatches = [u for i, u in enumerate(ordered_uids) if features[i].tobytes() != old_by[u].tobytes()]
                parity = dict(original104_exact_bytes=not mismatches, mismatch_count=len(mismatches),
                    max_abs_error=max(float(np.max(np.abs(features[i]-old_by[u]))) for i, u in enumerate(ordered_uids)),
                    local_benchmark_does_not_authorize_production=True)
                write_json(out/'ORIGINAL104_PARITY.json', parity)
                if args.mode == 'encode':
                    require(not mismatches, 'ORIGINAL104_NUMERICAL_IDENTITY_STOP')
                source_verified = not mismatches
            np.savez_compressed(out/(name+'.npz'), uid=np.asarray(ordered_uids, dtype='<U64'), e3=features,
                                q14=np.asarray([qby[u] for u in ordered_uids], dtype=np.float32))
            total_time = sum(v['seconds'] for v in timings)
            benchmarks.append(dict(name=name, full_rows=len(rows), measured_rows=len(selected),
                batch_count=len(timings), e3_seconds=total_time, rows_per_second=len(selected)/total_time,
                all_shape_counts=shapes, batches=timings, original104_parity=parity))
        db.close()
        db = None
        merged = []
        if args.mode == 'encode':
            for spec in config['banks']:
                merged.append(merge_bank(root, out, spec))
        completed = sum(s['measured_rows'] for s in benchmarks)
        progress(status='COMPLETE', stage='ENCODING_COMPLETE' if args.mode == 'encode' else 'BENCHMARK_COMPLETE',
                 completed=completed, total=completed)
        write_json(out/'RESULT.json', dict(status='COMPLETE', mode=args.mode, package_sha256=package_sha,
            checkpoint_sha256=CHECKPOINT_SHA, startup_seconds=startup_seconds, tokenize_seconds=tokenize_seconds,
            elapsed_seconds=time.monotonic()-started, peak_rss_bytes=peak[0], datasets=benchmarks,
            benchmark_features_must_not_be_used_for_production=args.mode == 'benchmark',
            banks=merged, no_training=True, classifier_forwards=0, CAL_run=False, target_evaluation=False, retries=0))
    except BaseException as exc:
        latest.update(status='EXCEPTION_STOP', error=repr(exc))
        write_json(out/'status.json', dict(latest, elapsed_seconds=time.monotonic()-started, retries=0))
        raise
    finally:
        closed.set()
        thread.join(timeout=5)
        if db is not None:
            db.close()


if __name__ == '__main__':
    main()
