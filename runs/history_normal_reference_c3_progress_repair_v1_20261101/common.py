"""Frozen C3 plumbing. Importing this file does not run science."""
import os
for _key in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_key] = '4'
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['TRANSFORMERS_OFFLINE'] = '1'
from datetime import datetime, timezone
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
C1 = ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'
C2 = ROOT / 'runs/history_normal_reference_c2_syn_guard_v1_20261031'
D2 = ROOT / 'runs/history_normal_reference_d2_trace_v1_20261031'
for _path in (ROOT / 'repo/ood', C1):
    sys.path.insert(0, str(_path))
CANDIDATE = 'C3_ADMITTED_SMALL_BANK_COMPLETE'
HEIM = 'HeimVision Camera'
CAP = 4096
LIMITS = dict(cpu=4, rss_bytes=8 * 2**30, wall_seconds=7200, output_bytes=2 * 2**30,
              encoded_new_rows=278, distance_pairs=400_000_000)


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def serial(value):
    if isinstance(value, np.ndarray): return serial(value.tolist())
    if isinstance(value, np.generic): return serial(value.item())
    if isinstance(value, dict): return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)): return [serial(v) for v in value]
    return value


def write(path, value, *, exclusive=False):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    target = path if exclusive else path.with_name(path.name + '.tmp')
    with target.open('x' if exclusive else 'w', encoding='utf-8') as stream:
        json.dump(serial(value), stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write('\n')
    if not exclusive: target.replace(path)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        for line in stream:
            if line.strip(): yield json.loads(line)


def write_rows(path, rr):
    need(not Path(path).exists(), 'OUTPUT_ALREADY_EXISTS')
    with gzip.open(path, 'wt', encoding='utf-8') as stream:
        for row in rr: stream.write(json.dumps(serial(row), ensure_ascii=False, allow_nan=False) + '\n')


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def verify_contract(*, remote=False):
    card = read(HERE / 'EXECUTION_CARD.json')
    need(card['candidate'] == CANDIDATE and card['limits'] == LIMITS, 'FIXED_C3_CARD')
    need(sha(HERE / 'INPUT_MANIFEST.json') == card['input_manifest_sha256'], 'INPUT_MANIFEST_PIN')
    for rel, expected in card['code_sha256'].items():
        need(sha(HERE / rel) == expected, 'CODE_PIN:' + rel)
    manifest = read(HERE / 'INPUT_MANIFEST.json')
    pins = manifest['encoder_source_sha256'] if remote else manifest['input_sha256']
    for relative, expected in pins.items():
        need(sha(ROOT / relative) == expected, 'INPUT_PIN:' + relative)
    return card, manifest


def progress(stage, message, **extra):
    state = dict(candidate=CANDIDATE, stage=stage, message=message,
                 updated_utc=datetime.now(timezone.utc).isoformat(), **extra)
    # Windows readers may briefly deny rename/delete sharing. A display update
    # must not abort science; scientific artifacts still use strict write().
    warnings = []
    try:
        write(HERE / 'STATUS.json', state)
    except OSError as error:
        warnings.append('STATUS.json: ' + repr(error))
    lines = ['# C3 实验进度', '', '**' + message + '**', '',
             '唯一候选：补全已准入的小参考库；保留 C2 攻击保护，固定阈值与修正强度。', '',
             '顺序：实现检查 → 原包及合法帧验收 → 超算编码 → HIST_DEV 一致性门 → 一次 A/B → 验收并冻结。', '',
             '阶段：' + stage, '']
    lines += [str(k) + '：' + str(v) for k, v in extra.items()]
    try:
        (HERE / 'PROGRESS.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    except OSError as error:
        warnings.append('PROGRESS.md: ' + repr(error))
    if warnings:
        state['display_write_warnings'] = warnings
    print(json.dumps(serial(state), ensure_ascii=False), flush=True)


def same_physical(row):
    return row['source_sha256'], row['frame'], row['owner']


def complete_small_group(candidates, old):
    """Only source-internal inputs; no query, labels-as-feedback or scores."""
    need(len({r['uid'] for r in candidates}) == len(candidates), 'DUPLICATE_CANDIDATE_UID')
    need(len({same_physical(r) for r in candidates}) == len(candidates), 'DUPLICATE_PHYSICAL_ENDPOINT')
    by_physical = {same_physical(r): r for r in candidates}
    need(len({same_physical(r) for r in old}) == len(old), 'DUPLICATE_OLD_ENDPOINT')
    for row in old:
        need(same_physical(row) in by_physical, 'OLD_REFERENCE_NOT_IN_LEGAL_DOMAIN')
        candidate = by_physical[same_physical(row)]
        need(all(candidate[k] == row[k] for k in ('uid', 'component_id', 'session_id', 'protocol', 'device')),
             'OLD_REFERENCE_IDENTITY_CHANGED')
    if len(candidates) > CAP:
        return [], 'FROZEN_OLD_SELECTION'
    old_keys = {same_physical(r) for r in old}
    return sorted((r for r in candidates if same_physical(r) not in old_keys), key=lambda r: r['uid']), 'COMPLETE_SMALL_GROUP'


def c3_gate(pools, previous):
    """C3 adoption is separate from the original all-device 2% target."""
    failures = []
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        for view in ('full', 'post_window_primary'):
            a, b = pools[pool]['views'][view], previous[pool]['views'][view]
            need(a['retained_uid_sha256'] == b['retained_uid_sha256'] and a['weights_sha256'] == b['weights_sha256'], 'POPULATION_OR_WEIGHT_CHANGED')
            for head in ('27', '127', '227', 'ensemble'):
                now, old = a['reports'][head], b['reports'][head]
                if now['protection']['status'] != 'PASS': failures.append(f'{pool}/{view}/{head}/PROTECTION')
                # Compare population and every device, not only a pool average.
                scopes = [('pool', now, old)]
                old_by = {g['group']['device']: g for g in old['groups']['device']}
                need(set(old_by) == {g['group']['device'] for g in now['groups']['device']}, 'DEVICE_REMOVED')
                scopes += [(g['group']['device'], g, old_by[g['group']['device']]) for g in now['groups']['device']]
                for name, new_scope, old_scope in scopes:
                    nr, br = new_scope['corrected']['normal'], old_scope['corrected']['normal']
                    need(nr['rows'] == br['rows'], 'NORMAL_DENOMINATOR_CHANGED')
                    if br['rows'] and (nr['positive'] > br['positive'] or nr['weighted_rate'] > br['weighted_rate'] + 1e-14):
                        failures.append(f'{pool}/{view}/{head}/{name}/NORMAL_REGRESSION')
    def heim_rate(value):
        return next(g for g in value['CIC_DEV']['views']['post_window_primary']['reports']['ensemble']['groups']['device']
                    if g['group']['device'] == HEIM)['corrected']['normal']['weighted_rate']
    before, after = heim_rate(previous), heim_rate(pools)
    if not after < before: failures.append('HEIM_NOT_STRICTLY_IMPROVED')
    return dict(status='PASS_C3_IMPROVEMENT' if not failures else 'REJECT_C3_KEEP_C2',
                frozen_method=CANDIDATE if not failures else 'C2_QUERY_SYN_NO_ACK_KEEP_RAW',
                failures=failures, heim_before=before, heim_after=after, heim_target_met=after <= .02,
                method_frozen=True, further_AB_method_search=False)
