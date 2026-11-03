"""Read only sealed Job176975 caches. No decoder, tokenizer, model, or fitting API."""
import argparse
from collections import defaultdict
import gzip
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import signal
import sys
import time
import traceback

import numpy as np
from legacy_unsw_saved_cache_delivery_v1 import export_output

RUN = 'runs/real_evaluation/'
CONTENT_KEYS = ('burst_tokens', 'directions', 'bytes', 'iats', 'counts', 'protocol')
SCORES = ('Q', 'Q_27', 'Q_127', 'Q_227', 'RAW', 'FULL', 'FULL_27', 'FULL_127',
          'FULL_227', 'NO_CF', 'NO_CF_27', 'NO_CF_127', 'NO_CF_227')
META = ('uid', 'device', 'display_name', 'label', 'use', 'protocol', 'component_id',
        'session_id', 'annotation_id', 'attack_rate', 'timestamp', 'frame')


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def digest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=True, allow_nan=False).encode('ascii')
    return hashlib.sha256(encoded).hexdigest()


def sha(path, guard=lambda: None):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            guard()
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    tmp = path.with_name(path.name + '.next')
    with tmp.open('w', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    os.replace(str(tmp), str(path))


def inside(root, relative):
    rel = PurePosixPath(relative)
    require(not rel.is_absolute() and '..' not in rel.parts and
            '\\' not in relative and ':' not in relative and bool(rel.parts), 'UNSAFE_INPUT_PATH')
    target = root.joinpath(*rel.parts)
    current = root
    for part in rel.parts:
        current = current/part
        require(not current.is_symlink(), 'SYMLINK_INPUT')
    require(root in target.resolve().parents, 'INPUT_PATH_ESCAPE')
    return target


class Progress:
    def __init__(self, out, wall_seconds):
        self.out, self.limit = out, wall_seconds
        self.start, self.last = time.monotonic(), 0
        self.stage, self.completed, self.total = 'INITIALIZE', 0, 1

    def guard(self):
        require(time.monotonic()-self.start < self.limit, 'WALL_TIME_LIMIT')
        require(not (self.out/'STOP_REQUESTED').exists(), 'USER_STOP_REQUESTED')

    def tick(self, stage, completed, total, force=False):
        self.guard()
        changed = stage != self.stage
        self.stage, self.completed, self.total = stage, completed, total
        if force or changed or time.monotonic()-self.last >= 10:
            self.emit('RUNNING')

    def emit(self, status, error=None):
        self.last = time.monotonic()
        state = dict(status=status, stage=self.stage, completed=self.completed, total=self.total,
                     percent=100*self.completed/self.total if self.total else 100.,
                     percent_scope='current stage only', elapsed_seconds=self.last-self.start,
                     error=error, retries=0, model_forwards=0, optimizer_updates=0,
                     raw_decodes=0, calibration_updates=0, actual_tensor_hashing='NOT_ENABLED')
        write(self.out/'status.json', state)
        print('%s %s %d/%d (%.1f%%)' %
              (status, self.stage, self.completed, self.total, state['percent']), flush=True)


def verify_inputs(source, contract, progress, stage):
    result = {}
    items = sorted(contract['input_files'].items())
    for index, (relative, pin) in enumerate(items):
        progress.tick(stage, index, len(items))
        path = inside(source, relative)
        require(path.is_file(), 'MISSING_CACHE:'+relative)
        require(path.stat().st_size == pin['bytes'], 'SIZE_MISMATCH:'+relative)
        value = sha(path, progress.guard)
        require(value == pin['sha256'], 'SHA_MISMATCH:'+relative)
        result[relative] = dict(sha256=value, bytes=pin['bytes'])
    progress.tick(stage, len(items), len(items), True)
    return result


def manifest_rows(source, contract, progress):
    rows = []
    for filename, use in (('queries', 'QUERY'), ('references', 'REFERENCE')):
        with gzip.open(source/(RUN+'manifests/'+filename+'.jsonl.gz'), 'rt', encoding='utf-8') as stream:
            part = []
            for line in stream:
                if len(part) % 1024 == 0:
                    progress.guard()
                raw = json.loads(line)
                require(raw['use'] == use and raw['label'] in (0, 1), 'MANIFEST_ROLE_LABEL')
                require(use != 'REFERENCE' or raw['label'] == 0, 'ATTACK_REFERENCE')
                require(math.isfinite(raw['timestamp']) and type(raw['frame']) is int, 'MANIFEST_TIME')
                require(raw['protocol'] in (6, 17), 'MANIFEST_PROTOCOL')
                part.append({key: raw.get(key) for key in META})
        require(len(part) == contract['counts'][filename], 'MANIFEST_COUNT:'+filename)
        require([r['uid'] for r in part] == sorted(r['uid'] for r in part), 'MANIFEST_ORDER')
        rows.extend(part)
    require(len({r['uid'] for r in rows}) == len(rows), 'DUPLICATE_MANIFEST_UID')
    require(sum(r['label'] for r in rows) == contract['counts']['attacks'], 'ATTACK_COUNT')
    require({r['device'] for r in rows} == set(contract['devices']), 'DEVICE_ROSTER')
    return rows


def content_hash(flow, protocol):
    require(set(flow) == set(CONTENT_KEYS) | {'flow_duration'}, 'FLOW_SCHEMA')
    require(flow['protocol'] == protocol, 'FLOW_PROTOCOL')
    require(type(flow['flow_duration']) is int and flow['flow_duration'] >= 0, 'FLOW_DURATION')
    n = len(flow['counts'])
    require(0 < n <= 12 and all(len(flow[k]) == n for k in CONTENT_KEYS if k != 'protocol'), 'FLOW_BURSTS')
    require(all(type(v) is int and 0 < v <= 6 for v in flow['counts']), 'FLOW_PACKET_COUNTS')
    require(all(type(v) is bool for v in flow['directions']), 'FLOW_DIRECTIONS')
    require(all(type(v) is int and v >= 0 for k in ('bytes', 'iats') for v in flow[k]), 'FLOW_NUMERICS')
    require(all(isinstance(burst, list) and len(burst) <= 256 and
                all(type(v) is int and 0 <= v <= 65535 for v in burst)
                for burst in flow['burst_tokens']), 'FLOW_TOKENS')
    return digest({key: flow[key] for key in CONTENT_KEYS})


def tail_start(values):
    """Earliest index of the constant final run; no detection threshold involved."""
    index = len(values)-1
    while index > 0 and values[index-1] == values[-1]:
        index -= 1
    return index+1


def describe(indices, rows):
    order = sorted(indices, key=lambda i: (rows[i]['timestamp'], rows[i]['frame'], rows[i]['uid']))
    rs = [rows[i] for i in order]
    result = dict(rows=len(rs), components=len({r['component_id'] for r in rs}),
                  sessions=len({r['session_id'] for r in rs}),
                  timestamp_range=[rs[0]['timestamp'], rs[-1]['timestamp']],
                  duration_range=[min(r['flow_duration'] for r in rs), max(r['flow_duration'] for r in rs)],
                  translated_packet_range=[min(r['translated_packets'] for r in rs), max(r['translated_packets'] for r in rs)])
    result['query_reference_valid_counts'] = dict(
        valid=sum(r['reference_valid'] is True for r in rs),
        invalid=sum(r['reference_valid'] is False for r in rs),
        not_applicable=sum(r['reference_valid'] is None for r in rs))
    for key in ('semantic_source_sha256', 'feature_sha256', 'saved_score_sha256'):
        values = [r[key] for r in rs]
        if values[0] is None:
            result[key] = dict(status='NOT_APPLICABLE_REFERENCE')
        else:
            result[key] = dict(unique=len(set(values)), constant_tail_start_1based=tail_start(values),
                               consecutive_changes=sum(a != b for a, b in zip(values, values[1:])))
    # Evidence for distinguishing representation mapping, never a causal root-cause verdict.
    source_to_features = defaultdict(set)
    feature_to_sources = defaultdict(set)
    for r in rs:
        source_to_features[r['semantic_source_sha256']].add(r['feature_sha256'])
        feature_to_sources[r['feature_sha256']].add(r['semantic_source_sha256'])
    result['source_hashes_with_multiple_features'] = sum(len(v) > 1 for v in source_to_features.values())
    result['feature_hashes_with_multiple_sources'] = sum(len(v) > 1 for v in feature_to_sources.values())
    return result, order


def summarize(rows, progress):
    groups = {}
    schemes = [('device', 'use', 'label'), ('device', 'protocol', 'use', 'label'),
               ('device', 'component_id', 'use', 'label'), ('device', 'annotation_id', 'attack_rate')]
    for step, fields in enumerate(schemes):
        progress.tick('SUMMARIZE', step, len(schemes))
        buckets = defaultdict(list)
        for i, row in enumerate(rows):
            if 'attack_rate' in fields and row['label'] != 1:
                continue
            buckets[tuple(row[k] for k in fields)].append(i)
        entries = []
        for key, indices in sorted(buckets.items(), key=lambda kv: repr(kv[0])):
            progress.guard()
            entry, order = describe(indices, rows)
            entry['group'] = dict(zip(fields, key))
            if rows[indices[0]]['label'] == 1:
                positions = sorted(set(range(min(7, len(order)))) | {len(order)-1})
                entry['chronology_examples'] = [dict(position_1based=k+1, **rows[order[k]]) for k in positions]
            entries.append(entry)
        groups['/'.join(fields)] = entries
    progress.tick('SUMMARIZE', len(schemes), len(schemes), True)
    return groups


def seal(folder):
    files = sorted(p for p in folder.rglob('*') if p.is_file() and p.name != 'SHA256SUMS')
    (folder/'SHA256SUMS').write_bytes(''.join(sha(p)+'  '+p.relative_to(folder).as_posix()+'\n'
                                            for p in files).encode('utf-8'))


def audit(source, output, contract, authorized=False):
    require(authorized is True, 'READ_ONLY_CACHE_AUDIT_NOT_AUTHORIZED')
    source, output = Path(source).resolve(), Path(output).resolve()
    require(source != output and source not in output.parents and output not in source.parents, 'OUTPUT_OVERLAPS_SOURCE')
    output.mkdir(parents=True, exist_ok=False)
    progress = Progress(output, contract['wall_seconds'])
    try:
        require(contract['actual_tensor_hashing'] == 'NOT_ENABLED', 'UNFROZEN_TENSOR_SCOPE')
        pins = verify_inputs(source, contract, progress, 'VERIFY_INPUT_BYTES')
        require((source/'job.id').read_text().strip() == str(contract['source_job']), 'WRONG_SOURCE_JOB')
        require((source/'exit_code.txt').read_text().strip() == '0', 'SOURCE_NOT_SUCCESSFUL')
        require(read(source/(RUN+'status.json'))['status'] == 'COMPLETE', 'SOURCE_NOT_COMPLETE')
        progress.tick('READ_MANIFESTS', 0, contract['counts']['queries'] + contract['counts']['references'], True)
        rows = manifest_rows(source, contract, progress)
        all_uids = [r['uid'] for r in rows]
        require(read(source/(RUN+'features/uids.json')) == all_uids, 'FEATURE_UID_ORDER')
        receipt = read(source/(RUN+'features/receipt.json'))
        require(receipt == dict(rows=len(rows), recipe_sha256=contract['recipe_sha256'],
                manifest_seal_sha256=pins[RUN+'manifests/SHA256SUMS']['sha256'],
                flows_seal_sha256=pins[RUN+'flows/SHA256SUMS']['sha256']), 'FEATURE_RECEIPT_IDENTITY')
        index = read(source/(RUN+'flows/index.json'))
        require(index == dict(shards=contract['shards'], total=len(rows),
                manifest_seal_sha256=pins[RUN+'manifests/SHA256SUMS']['sha256'],
                immutable_causal_snapshots=True), 'FLOW_INDEX_IDENTITY')
        progress.tick('READ_SAVED_FEATURES', 0, len(rows), True)
        features = np.load(source/(RUN+'features/features.npy'), mmap_mode='r', allow_pickle=False)
        require(features.shape == (len(rows), 768) and features.dtype == np.dtype('<f4'), 'FEATURE_SHAPE_DTYPE')
        for start in range(0, len(rows), 1024):
            batch = features[start:start+1024]
            require(np.isfinite(batch).all(), 'FEATURE_NONFINITE')
            for offset, value in enumerate(batch):
                rows[start+offset]['feature_sha256'] = hashlib.sha256(value.tobytes(order='C')).hexdigest()
            progress.tick('READ_SAVED_FEATURES', min(start+1024, len(rows)), len(rows))
        del features
        qn = contract['counts']['queries']
        progress.tick('READ_SAVED_SCORES', 0, qn, True)
        with np.load(source/(RUN+'evaluation/decisions.npz'), allow_pickle=False) as decisions:
            require(decisions['uid'].tolist() == all_uids[:qn], 'SAVED_SCORE_UID_ORDER')
        with np.load(source/(RUN+'evaluation/evidence.npz'), allow_pickle=False) as evidence:
            require(set(evidence.files) == set(SCORES) | {'valid'}, 'SAVED_SCORE_KEYS')
            require(all(evidence[k].shape == (qn,) and np.isfinite(evidence[k]).all() for k in SCORES), 'SAVED_SCORE_SHAPE')
            values = np.stack([evidence[k] for k in SCORES], axis=1).astype('<f8')
            valid = evidence['valid']
            require(valid.shape == (qn,) and valid.dtype == np.bool_, 'REFERENCE_MASK')
            for i, row in enumerate(rows):
                if i % 1024 == 0:
                    progress.tick('READ_SAVED_SCORES', min(i, qn), qn)
                row['saved_score_sha256'] = hashlib.sha256(values[i].tobytes()).hexdigest() if i < qn else None
                row['reference_valid'] = bool(valid[i]) if i < qn else None
        lookup, seen = {r['uid']:r for r in rows}, set()
        progress.tick('READ_SAVED_FLOWS', 0, len(rows), True)
        for ordinal, spec in enumerate(index['shards']):
            count = 0
            relative = RUN+'flows/'+spec['file']
            require(relative in pins, 'UNPINNED_SHARD')
            with gzip.open(inside(source, relative), 'rt', encoding='utf-8') as stream:
                for line in stream:
                    item = json.loads(line)
                    require(set(item) == {'uid', 'flow'}, 'SNAPSHOT_SCHEMA')
                    uid = item['uid']
                    require(uid in lookup and uid not in seen, 'SNAPSHOT_UID_COVERAGE')
                    row, flow = lookup[uid], item['flow']
                    row.update(semantic_source_sha256=content_hash(flow, row['protocol']),
                               flow_duration=flow['flow_duration'], burst_count=len(flow['counts']),
                               translated_packets=sum(flow['counts']), shard=ordinal,
                               shard_row_0based=count, original_batch_0based=count//16,
                               original_batch_position_0based=count%16)
                    seen.add(uid)
                    count += 1
                    if count % 256 == 0:
                        progress.tick('READ_SAVED_FLOWS', len(seen), len(rows))
            require(count == spec['count'], 'SHARD_ROW_COUNT')
        require(seen == set(lookup), 'MISSING_SNAPSHOT_UID')
        progress.tick('READ_SAVED_FLOWS', len(rows), len(rows), True)
        groups = summarize(rows, progress)
        write(output/'grouped_summary.json', groups)
        progress.tick('WRITE_UID_HASHES', 0, len(rows), True)
        with gzip.open(output/'per_uid_hashes.jsonl.gz', 'wt', encoding='utf-8', newline='\n') as stream:
            for i, row in enumerate(rows):
                if i % 1024 == 0:
                    progress.tick('WRITE_UID_HASHES', i, len(rows))
                stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')
        # A second byte verification also detects input mutation while parsing.
        require(verify_inputs(source, contract, progress, 'REVERIFY_UNCHANGED_INPUTS') == pins, 'INPUT_CHANGED')
        write(output/'input_verification.json', dict(before=pins, after_equal=True,
              source_job=contract['source_job'], source_root=str(source), contract_sha256=digest(contract)))
        summary = dict(status='CACHE_AUDIT_COMPLETE', counts=contract['counts'],
                       source_job=contract['source_job'], input_file_count=len(pins),
                       source_bytes=sum(x['bytes'] for x in pins.values()),
                       attack_devices=[x for x in groups['device/use/label'] if x['group']['label'] == 1],
                       actual_tensor_hashing='NOT_ENABLED', target_frame_to_token_provenance='UNAVAILABLE',
                       source_hash_is_not_tensor_hash=True, model_forwards=0, optimizer_updates=0,
                       invalid_reference_scores='Saved verifier zeros are placeholders, not measured compatibility',
                       raw_decodes=0, calibration_updates=0, threshold_searches=0,
                       performance_improvement_measured=False, historical_scientific_FAIL_unchanged=True,
                       independence='Consumed development evidence; not new independent confirmation')
        write(output/'summary.json', summary)
        lines = ['# 已保存缓存核验', '', '只读核验完成；没有新推理、训练、阈值选择或性能提升结论。', '',
                 '| 设备 | 攻击查询 | 源字段种类 | 特征种类 | 保存分数种类 | 源字段恒定尾段起点 | 特征恒定尾段起点 |',
                 '|---|---:|---:|---:|---:|---:|---:|']
        for entry in summary['attack_devices']:
            examples = entry['chronology_examples']
            fields = [entry[k] for k in ('semantic_source_sha256','feature_sha256','saved_score_sha256')]
            lines.append('| %s | %d | %d | %d | %d | %d | %d |' % (
                examples[0]['display_name'], entry['rows'], fields[0]['unique'], fields[1]['unique'],
                fields[2]['unique'], fields[0]['constant_tail_start_1based'], fields[1]['constant_tail_start_1based']))
        lines += ['', '源字段哈希排除未消费的 flow_duration，但不是实际 E3 张量哈希。',
                  '相同哈希不能证明目标包未保留，也不能证明哪些原始变化被遗漏；原帧到 token 映射未保存。',
                  '正常查询、参考、组件和三个速率的完整摘要在 grouped_summary.json。',
                  '所有原始 UID 保留；每 UID 对应见 per_uid_hashes.jsonl.gz。',
                  'reference_valid=false 时，参考验证分数为原保存占位值，不代表实测相似度。',
                  '恢复到本次 Q 不是最终能力目标；当前工具只定位信息重复层级。']
        (output/'result.md').write_bytes(('\n'.join(lines)+'\n').encode('utf-8'))
        progress.tick('COMPLETE', 1, 1, True)
        progress.emit('COMPLETE')
        seal(output)
        return summary
    except BaseException as exc:
        write(output/'first_failure.json', dict(error=repr(exc), traceback=traceback.format_exc(),
              stage=progress.stage, retries=0))
        progress.emit('STOPPED_NO_RETRY', repr(exc))
        seal(output)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('run', 'export'))
    parser.add_argument('--audit-saved-job176975', action='store_true')
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parent
    if args.command == 'export':
        export_output(root)
        return
    require(args.audit_saved_job176975, 'READ_ONLY_CACHE_AUDIT_NOT_AUTHORIZED')
    expected, name = (root/'input_contract.json.sha256').read_text().strip().split()
    require(name == 'input_contract.json' and sha(root/name) == expected, 'CONTRACT_SHA')
    contract = read(root/name)
    require(contract['source_job'] == 176975, 'CONTRACT_JOB')
    def terminate(signum, frame):
        raise RuntimeError('TERMINATED_SIGNAL:'+str(signum))
    signal.signal(signal.SIGTERM, terminate)
    audit(contract['source_root'], root/'runs/cache_audit', contract, authorized=True)


if __name__ == '__main__':
    main()
