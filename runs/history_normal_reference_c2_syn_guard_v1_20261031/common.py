"""Small saved-score-only C2 operations; no model or distance implementation."""
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT = HERE / 'output'
SUFFIXES = ('27', '127', '227', 'ensemble')
CANDIDATE = 'C2_QUERY_SYN_NO_ACK_KEEP_RAW'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    return value


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(serial(value), ensure_ascii=False, allow_nan=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def rows(path, fields=None):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            item = json.loads(line)
            yield item if fields is None else {k: item[k] for k in fields if k in item}


def uid_hash(values):
    return hashlib.sha256('\n'.join(map(str, values)).encode()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def syn_guard(q14):
    q = np.asarray(q14)
    need(q.ndim == 2 and q.shape[1] == 14 and np.isfinite(q).all(), 'Q14_SCHEMA')
    need(np.all((q[:, :10] == 0) | (q[:, :10] == 1)), 'PROTOCOL_FLAG_BITS_NOT_BINARY')
    return (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0)


def restore_raw(raw, corrected, guard):
    raw, corrected, guard = np.asarray(raw), np.asarray(corrected), np.asarray(guard)
    need(raw.shape == corrected.shape and raw.ndim == 2 and raw.shape[1] in (3, 4), 'SCORE_SHAPE')
    need(np.isfinite(raw).all() and np.isfinite(corrected).all(), 'NONFINITE_SCORE')
    need(np.all(corrected <= raw), 'OLD_CORRECTION_NOT_MONOTONE')
    need(guard.dtype == np.bool_ and guard.shape == (len(raw),), 'GUARD_SHAPE')
    out = corrected.copy()
    out[guard] = raw[guard]
    need(np.array_equal(out[~guard], corrected[~guard]) and np.array_equal(out[guard], raw[guard]), 'RAW_RESTORE_IDENTITY')
    need(np.all(corrected <= out) and np.all(out <= raw), 'C2_SCORE_MONOTONICITY')
    return out


def align_q(uids, shards):
    uids = list(map(str, uids))
    need(len(uids) == len(set(uids)), 'DUPLICATE_QUERY_UID')
    lookup = {}
    for ids, q in shards:
        ids, q = list(map(str, ids)), np.asarray(q)
        need(q.shape == (len(ids), 14), 'SHARD_SHAPE')
        for i, uid in enumerate(ids):
            need(uid not in lookup, 'DUPLICATE_SHARD_UID')
            lookup[uid] = q[i]
    need(set(lookup) == set(uids), 'QUERY_SHARD_UID_SET_MISMATCH')
    result = np.stack([lookup[uid] for uid in uids])
    syn_guard(result)
    return result


def require_dev_pass(dev):
    need(dev.get('status') == 'PASS_DEV' and dev.get('no_AB_loaded') is True,
         'DEV_GATE_REQUIRED_BEFORE_AB_LOAD')


class Inputs:
    def __init__(self, manifest):
        self.manifest = manifest
        self.seen = {}

    def pin(self, relative):
        need(relative in self.manifest['files'], 'UNREGISTERED_INPUT:' + relative)
        path = (ROOT / relative).resolve()
        need(path.is_relative_to(ROOT.resolve()), 'INPUT_PATH_ESCAPE')
        expected = self.manifest['files'][relative]
        need(path.is_file() and sha(path) == expected, 'INPUT_SHA_MISMATCH:' + relative)
        self.seen[relative] = expected
        return path

    def json(self, relative):
        return read(self.pin(relative))

    def immutable(self):
        for relative, expected in self.seen.items():
            need(sha(ROOT / relative) == expected, 'INPUT_CHANGED:' + relative)
        return dict(files=len(self.seen), status='UNCHANGED')


def progress(stage, text, **extra):
    now = datetime.now(timezone.utc).isoformat()
    current = dict(candidate=CANDIDATE, stage=stage, message=text, updated_utc=now, **extra)
    write(HERE / 'STATUS.json', current)
    path = HERE / 'PROGRESS.md'
    lines = ['# C2 实验进度', '', '**' + text + '**', '', '更新时间（UTC）：' + now,
             '', '固定方法：所有设备的 TCP SYN 且 ACK=0 查询恢复 RAW，其他行沿用 C1。',
             '', '阶段顺序：旧产物校验 → 源域保存结果预检 → HIST_DEV 门 → 通过后一次 A/B → 完成校验。',
             '', '本机复用旧数组；不训练、不提取新特征、不重新计算邻居距离。', '']
    for key, value in extra.items():
        lines.append('- ' + key + '：' + str(value))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(json.dumps(current, ensure_ascii=False), flush=True)
