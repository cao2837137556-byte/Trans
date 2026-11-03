"""Validate and consume sealed teacher/guard caches; never derive new targets."""
import math
import struct
import numpy as np
import torch
import issue27frontend_abstart_support_v1 as s


def load_guard(contexts, r, budget):
    value = s.read_json(s.pin(r['teacher_cache']['guard'], budget.check))
    groups, scale, cfg = value['groups'], value['scale'], r['losses']['A_guard']
    actual = {t['uid']: t for t in s.targets(contexts) if t['owner'] == 'A'}
    seen, counts, enriched = set(), {0: 0, 1: 0}, {}
    for key, rows in groups.items():
        s.require(rows and [t['uid'] for t in rows] == sorted(t['uid'] for t in rows), 'GUARD_ORDER')
        enriched[key] = []
        for row in rows:
            uid = row['uid']
            s.require(uid in actual and uid not in seen, 'GUARD_UID')
            t = actual[uid]; seen.add(uid)
            s.require(all(row[k] == t[k] for k in ('uid','context_key','label','component_id','event'))
                      and key == t['context_key'], 'GUARD_JOIN')
            s.require(math.isfinite(row['logit']) and int(row['logit'] >= 0) == t['label'], 'GUARD_HARD')
            counts[t['label']] += 1; enriched[key].append(dict(t, logit=row['logit']))
    s.require(len(groups) == cfg['eligible_contexts'] and len(seen) == cfg['eligible_targets']
              and counts == {0: cfg['eligible_benign'], 1: cfg['eligible_attack']}, 'GUARD_COUNTS')
    s.require(math.isfinite(scale) and scale == cfg['s_A'], 'GUARD_SCALE')
    return enriched, scale


def load_prepared(contexts, r, budget):
    spec, cfg = r['prepared_teacher_reuse'], r['teacher_cache']
    manifest = s.pin(spec['manifest'], budget.check)
    entries = s.manifest(manifest.parent, spec['manifest']['sha256'], budget.check)
    for key in ('receipt','terminal','index','margins'):
        path = s.pin(spec[key], budget.check)
        s.require(path.parent == manifest.parent and entries[path.name] == spec[key]['sha256'], 'REUSE_MANIFEST_JOIN')
    receipt = s.read_json(s.ROOT/spec['receipt']['path'])
    s.require(s.read_json(s.ROOT/spec['terminal']['path'])['status'] == 'COMPLETE', 'OLD_P_NOT_COMPLETE')
    s.require(receipt['status'] == 'TASK_TARGETS_DERIVED'
              and receipt['recipe_sha256'] == spec['producer_recipe_sha256'], 'REUSE_PRODUCER_IDENTITY')
    for key in ('tau_T','s_q64','s_q32','s_q32_hex','s_T','targets'):
        s.require(receipt[key] == spec[key], 'REUSE_FIXED_VALUE:'+key)
    s.require(receipt['denominator'] == spec['class_context_counts']
              and receipt['boundary_mismatches'] == 0, 'REUSE_DENOMINATOR_BOUNDARY')
    s.require(receipt['index_sha256'] == spec['index']['sha256']
              and receipt['margins_sha256'] == spec['margins']['sha256']
              and receipt['source_manifest_sha256'] == cfg['manifest']['sha256'], 'REUSE_SOURCE_IDENTITY')
    original_manifest = s.pin(cfg['manifest'], budget.check)
    original_entries = s.manifest(original_manifest.parent, cfg['manifest']['sha256'], budget.check)
    s.require(s.read_json(original_manifest.parent/'supervisor_terminal.json')['status'] == 'COMPLETE', 'SOURCE_P_NOT_COMPLETE')
    for key in ('index','values','guard'):
        path = s.pin(cfg[key], budget.check)
        s.require(path.parent == original_manifest.parent and original_entries[path.name] == cfg[key]['sha256'], 'SOURCE_MANIFEST_JOIN')
    original = s.read_json(s.ROOT/cfg['index']['path'])
    rows = s.read_json(s.ROOT/spec['index']['path'])
    targets = s.teacher_targets(contexts, r)
    values = np.fromfile(s.ROOT/cfg['values']['path'], dtype='<f4')
    margins = np.fromfile(s.ROOT/spec['margins']['path'], dtype='<f4')
    n = cfg['expected_targets']
    s.require(len(rows) == len(original) == len(targets) == n and values.size == n*128
              and margins.size == n and np.isfinite(values).all() and np.isfinite(margins).all(), 'REUSE_SHAPE_FINITE')
    s.require(struct.pack('<f', receipt['s_q32']).hex() == spec['s_q32_hex']
              and math.isfinite(receipt['s_q32']) and receipt['s_q32'] >= 1, 'REUSE_SCALE_BITS')
    for i, (row, old, target) in enumerate(zip(rows, original, targets)):
        s.require(row['row'] == old['row'] == i and all(row[k] == target[k] for k in ('uid','context_key','label'))
                  and all(row[k] == v for k,v in old.items()), 'REUSE_ROW_JOIN')
        q, prob = old['canonical_logit'], old['canonical_probability']
        s.require(math.isfinite(q) and math.isfinite(prob) and 0 <= prob <= 1, 'REUSE_CANONICAL_FINITE')
        hard = prob >= r['losses']['task_score']['p_T']
        s.require(hard == bool(target['old_hard']) == bool(target['label']), 'REUSE_HARD')
        s.require(math.isfinite(row['margin64']) and math.isfinite(row['margin32'])
                  and struct.pack('<f', float(margins[i])).hex() == row['margin32_hex']
                  and float(margins[i]) == row['margin32']
                  and struct.pack('<f', row['margin64']).hex() == row['margin32_hex'], 'REUSE_MARGIN_BITS')
        s.require(bool(margins[i] >= 0) == bool(row['margin64'] >= 0) == hard, 'REUSE_MARGIN_SIGN')
    scale = torch.tensor(receipt['s_q32'], dtype=torch.float32)
    tensors = torch.from_numpy(values.reshape(n,128))
    budget.access['reused_teacher_rows'] = n
    return {t['uid']:dict(margin=torch.tensor(margins[i],dtype=torch.float32),
                         target=tensors[i],scale=scale) for i,t in enumerate(targets)}


def preflight(r, contexts, out, budget):
    budget.check(True, phase='ENTRY_REUSE_PREFLIGHT')
    s.pin(r['inputs']['membership'], budget.check)
    manifest = s.pin(r['inputs']['historical_train_manifest'], budget.check)
    entries = s.manifest(manifest.parent, r['inputs']['historical_train_manifest']['sha256'], budget.check)
    for key in ('initial_AB','initial_AB_receipt','initial_AB_terminal'):
        path = s.pin(r['inputs'][key], budget.check)
        s.require(path.parent == manifest.parent and entries[path.name] == r['inputs'][key]['sha256'], 'AB_MANIFEST_JOIN')
    receipt = s.read_json(s.ROOT/r['inputs']['initial_AB_receipt']['path'])
    terminal = s.read_json(s.ROOT/r['inputs']['initial_AB_terminal']['path'])
    expected = r['inputs']['initial_AB_receipt']
    s.require(terminal['verdict']['status'] == 'PAIRED_COMPARISON_COMPLETE', 'AB_NATIVE_TERMINAL')
    s.require(all(receipt[k] == expected[k] for k in ('epoch','updates','initial_state_sha256'))
              and receipt['state_sha256'] == r['inputs']['initial_AB']['state_sha256']
              and receipt['file_sha256'] == r['inputs']['initial_AB']['sha256'], 'AB_RECEIPT')
    s.require((s.ROOT/r['inputs']['initial_AB']['path']).stat().st_size == r['inputs']['initial_AB']['bytes'], 'AB_SIZE')
    guard = load_guard(contexts, r, budget)
    cache = load_prepared(contexts, r, budget)
    s.atomic_json(out/'reuse_receipt.json', dict(status='SEALED_INPUTS_REUSED',recipe_sha256=s.RECIPE_SHA,
        producer_recipe_sha256=r['prepared_teacher_reuse']['producer_recipe_sha256'],
        prepared_manifest_sha256=r['prepared_teacher_reuse']['manifest']['sha256'],
        initial_AB_file_sha256=r['inputs']['initial_AB']['sha256'],reused_teacher_rows=len(cache),
        derived_teacher_rows=0,student_forwards=0,optimizer_steps=0,new_P_stage=False))
    return guard, cache
