"""One C2 run using saved scores only: source diagnostic, DEV, conditional A/B."""
import gc
import hashlib
import sys
import traceback

import numpy as np

from common import (HERE, ROOT, OUTPUT, CANDIDATE, SUFFIXES, Inputs, align_q,
                    load_module, need, progress, read, require_dev_pass, restore_raw,
                    rows, sha, syn_guard, uid_hash, write)

OLD = 'runs/history_normal_reference_d2_trace_v1_20261031/retrieved/'
LOCAL = HERE.relative_to(ROOT).as_posix() + '/retrieved/'
PREP = 'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/'


def equal_tree(a, b, location='value'):
    if isinstance(a, dict):
        need(isinstance(b, dict) and set(a) == set(b), 'REPLAY_KEYS:' + location)
        for key in a:
            equal_tree(a[key], b[key], location + '/' + key)
    elif isinstance(a, list):
        need(isinstance(b, list) and len(a) == len(b), 'REPLAY_LIST:' + location)
        for i, (x, y) in enumerate(zip(a, b)):
            equal_tree(x, y, location + '/' + str(i))
    elif isinstance(a, float):
        need(isinstance(b, (float, int)) and np.isclose(a, b, rtol=0, atol=1e-12), 'REPLAY_FLOAT:' + location)
    else:
        need(a == b, 'REPLAY_VALUE:' + location)


def source_precheck(inputs, manifest, sm):
    progress('SOURCE_LOAD', '正在核验源域行身份与冻结角色')
    fields = ('uid', 'device', 'partition', 'fit_role', 'label', 'activity', 'annotation', 'annotation_id')
    metadata = list(rows(inputs.pin(PREP + 'LEARN.jsonl.gz'), fields))
    q = np.load(inputs.pin(PREP + 'LEARN_q.npy'), mmap_mode='r', allow_pickle=False)
    need(q.shape == (len(metadata), 14), 'SOURCE_Q14_ROWS')
    indices_path = inputs.pin('runs/source_controls_base_ctx_v1_20261026/config/FROZEN_INDICES.npz')
    with np.load(indices_path, allow_pickle=False) as z:
        indices = {k: z[k].copy() for k in z.files}
    endpoint = manifest['endpoints']
    summary = {}
    for fold in ('G0', 'G1'):
        cut = [inputs.json(endpoint + f'endpoints/{fold}_BASE_{s}/evaluation.json')['CAL']['threshold']
               for s in (27, 127, 227)]
        cut.append(inputs.json(endpoint + f'ensemble_{fold}_BASE.json')['CAL']['threshold'])
        cut = np.asarray(cut, dtype=np.float64)
        for role in ('CAL', 'S'):
            name = fold + '/' + role
            progress('SOURCE_PRECHECK', '正在预检源域保存分数（不重跑源模型）', population=name)
            expected = indices[fold + '_CAL'] if role == 'CAL' else indices[('G1' if fold == 'G0' else 'G0') + '_FIT']
            path = inputs.pin(LOCAL + 'source/' + name + '/SCORES.npz')
            keys = ['uid', 'source_index', 'denominators', 'phases', 'labels', 'raw']
            keys += [a + '_' + v for a in ('Q', 'N', 'C') for v in ('own', 'safety')]
            with np.load(path, allow_pickle=False) as z:
                saved = {k: z[k].copy() for k in keys}
                if 'historical_D0' in z:
                    saved['historical_D0'] = z['historical_D0'].copy()
            need(np.array_equal(saved['source_index'], expected), 'SOURCE_ROLE_INDEX:' + name)
            rr = [metadata[int(i)] for i in expected]
            need(saved['uid'].tolist() == [r['uid'] for r in rr], 'SOURCE_UID_JOIN:' + name)
            need(all(r['partition'] == 'LEARN' and r['fit_role'] == ('CAL' if role == 'CAL' else 'FIT') for r in rr), 'SOURCE_ROLE:' + name)
            labels = np.asarray([r['label'] for r in rr])
            need(np.array_equal(labels, saved['labels']), 'SOURCE_LABEL_JOIN')
            old = inputs.json(LOCAL + 'source/' + name + '/REPORT.json')
            need(old['uid_order_sha256'] == uid_hash(saved['uid']), 'SOURCE_REPORT_UID')
            guard = syn_guard(q[expected])
            raw = saved['raw']
            need(np.array_equal(raw[:, 3], sm.ensemble(raw[:, :3], 'source')), 'SOURCE_ENSEMBLE_ARITHMETIC')
            den = saved['denominators']
            weights = sm._ExactWeights(1.0 / den.astype(np.float64), den)
            mask = np.ones(len(rr), dtype=bool)
            groups = {}
            for field in ('device', 'activity'):
                values = np.asarray([r.get(field, 'NOT_AVAILABLE') for r in rr])
                groups[field] = {str(v): values == v for v in sorted(set(values.tolist()))}
            groups['phase'] = {str(v): saved['phases'] == v for v in sorted(set(saved['phases'].tolist()))}
            result = dict(status='REPORT_ONLY', rows=len(rr), cuts=cut.tolist(), guard_rows=int(guard.sum()),
                          normal_guard_rows=int((guard & (labels == 0)).sum()),
                          attack_guard_rows=int((guard & (labels == 1)).sum()),
                          uid_sha256=uid_hash(saved['uid']), original_roles='CAL' if role == 'CAL' else 'HELD_ORIGINAL_FIT',
                          raw={}, comparisons={}, original_QNC_branch_revived=False)
            arrays = dict(uid=saved['uid'], source_index=expected, guard=guard, raw=raw > cut)
            for j, suffix in enumerate(SUFFIXES):
                baseline = sm._rates(labels, weights, raw[:, j] > cut[j], mask)
                equal_tree(baseline, old['metrics']['RAW'][suffix], name + '/RAW/' + suffix)
                result['raw'][suffix] = baseline
            for arm in ('Q', 'N', 'C', 'historical_D0'):
                if arm == 'historical_D0' and arm not in saved:
                    continue
                views = ('own',) if arm == 'historical_D0' else ('own', 'safety')
                result['comparisons'][arm] = {}
                for view in views:
                    key = arm if arm == 'historical_D0' else arm + '_' + view
                    before = saved[key]
                    after = restore_raw(raw, before, guard)
                    old_pred, new_pred = before > cut, after > cut
                    need(not np.any(old_pred & ~new_pred), 'SOURCE_NEW_WITHDRAWAL')
                    arrays[key + '_old'] = old_pred
                    arrays[key + '_c2'] = new_pred
                    stats = {}
                    for j, suffix in enumerate(SUFFIXES):
                        prior = sm._rates(labels, weights, old_pred[:, j], mask)
                        expected_metric = old['reporting_only_D0'][suffix] if arm == 'historical_D0' else old['metrics' if view == 'own' else 'safety_metrics'][arm][suffix]
                        equal_tree(prior, expected_metric, name + '/' + key + '/' + suffix)
                        current = sm._rates(labels, weights, new_pred[:, j], mask)
                        stats[suffix] = dict(before=prior, after=current,
                                             restored_attack_count=int(((labels == 1) & ~old_pred[:, j] & new_pred[:, j]).sum()),
                                             returned_normal_alarm_count=int(((labels == 0) & ~old_pred[:, j] & new_pred[:, j]).sum()),
                                             groups={field: {value: dict(
                                                 after=sm._rates(labels, weights, new_pred[:, j], ix),
                                                 restored_attack_count=int((ix & (labels == 1) & ~old_pred[:, j] & new_pred[:, j]).sum()),
                                                 returned_normal_alarm_count=int((ix & (labels == 0) & ~old_pred[:, j] & new_pred[:, j]).sum()))
                                                 for value, ix in items.items()} for field, items in groups.items()})
                    result['comparisons'][arm][view] = stats
            result['old_pool_metrics_replayed'] = True
            result['non_guarded_scores_exact'] = True
            result['guarded_scores_equal_RAW'] = True
            write(OUTPUT / 'source' / fold / role / 'PRECHECK.json', result)
            np.savez_compressed(OUTPUT / 'source' / fold / role / 'GUARD_DECISIONS.npz', **arrays)
            summary[name] = dict(rows=len(rr), guard_rows=result['guard_rows'],
                                 C_own_ensemble=result['comparisons']['C']['own']['ensemble'],
                                 C_safety_ensemble=result['comparisons']['C']['safety']['ensemble'])
            del saved, rr, labels, old, guard, raw, weights, groups, result, arrays, after, before, old_pred, new_pred
            gc.collect()
    del metadata, q, indices
    gc.collect()
    result = dict(status='SOURCE_SAVED_PRECHECK_COMPLETE_REPORT_ONLY', populations=summary,
                  claim='Consumed source diagnostic on frozen 180228; not a new C1 source generalization pass.',
                  new_E3=0, model_forwards=0, distances=0, training=0)
    write(OUTPUT / 'source' / 'SUMMARY.json', result)
    return result


def dev_stage(inputs, frozen, ev):
    progress('HIST_DEV', '源域预检完成，正在验证历史正常集门槛')
    rr = list(rows(inputs.pin(OLD + 'dev/QUERIES.jsonl.gz')))
    with np.load(inputs.pin(OLD + 'dev/DEV_DECISIONS.npz'), allow_pickle=False) as z:
        saved = {k: z[k].copy() for k in z.files}
    need(len(rr) == 12288 and saved['uid'].tolist() == [r['uid'] for r in rr], 'DEV_UID_ROWS')
    shards = []
    for key in ('TP_LINK', 'SAMSUNG', 'WEMO_POWER'):
        with np.load(inputs.pin(LOCAL + 'history/' + key + '/queries.npz'), allow_pickle=False) as z:
            shards.append((z['uid'].copy(), z['q14'].copy()))
    q = align_q(saved['uid'], shards)
    need(np.array_equal(q[:, 0] == 1, np.asarray([r['protocol'] == 6 for r in rr])), 'DEV_PROTOCOL_JOIN')
    need(float(saved['selected_lambda']) == .25 and saved['seeds'].tolist() == [27, 127, 227], 'DEV_FROZEN_POINT')
    need(np.array_equal(saved['cuts'], frozen['cuts']['cuts']) and float(saved['ensemble_cut']) == frozen['cuts']['ensemble_cut'], 'DEV_CUTS')
    need(np.array_equal(ev.decisions(saved['raw_logits'], frozen), saved['base']), 'DEV_RAW_REPLAY')
    need(np.array_equal(ev.core.apply_correction(saved['raw_logits'], saved['support'], frozen['scales'], .25), saved['corrected_logits']), 'DEV_C1_SCORES_REPLAY')
    need(np.array_equal(ev.decisions(saved['corrected_logits'], frozen), saved['corrected']), 'DEV_C1_DECISIONS_REPLAY')
    old_gate = ev.dev_gate(rr, saved['base'][:, 3], saved['corrected'][:, 3])
    need(old_gate['status'] == 'PASS_DEV', 'DEV_OLD_GATE_REPLAY')
    guard = syn_guard(q)
    changed = restore_raw(saved['raw_logits'], saved['corrected_logits'], guard)
    effective = np.where(guard, 0., saved['support'])
    need(np.array_equal(changed, ev.core.apply_correction(saved['raw_logits'], effective, frozen['scales'], .25)), 'DEV_EFFECTIVE_SUPPORT_EQUIVALENCE')
    after = ev.decisions(changed, frozen)
    gate = ev.dev_gate(rr, saved['base'][:, 3], after[:, 3])
    gate.update(candidate=CANDIDATE, original_gate=old_gate, guard_rows=int(guard.sum()),
                returned_normal_alarms={s: int((~saved['corrected'][:, j] & after[:, j]).sum()) for j, s in enumerate(SUFFIXES)},
                new_distances=0, new_E3=0)
    write(OUTPUT / 'dev' / 'GATE.json', gate)
    np.savez_compressed(OUTPUT / 'dev' / 'DECISIONS.npz', uid=saved['uid'], q14=q, guard=guard,
                        raw_logits=saved['raw_logits'], corrected_logits=changed, base=saved['base'],
                        c1_corrected=saved['corrected'], corrected=after, original_support=saved['support'],
                        support=effective, eligible=saved['eligible'])
    return gate


def pool_report(pool, rr, base, corrected, eligible, support, windows, metrics, ev):
    metrics.validate_full_weights(rr, pool)
    keep = np.flatnonzero(metrics.post_window_mask(rr, windows))
    need(len(keep), 'EMPTY_PRIMARY_VIEW')
    primary = [rr[int(i)] for i in keep]
    result = dict(pool=pool, query_rows=len(rr), original_devices=sorted({r['device'] for r in rr if r['label'] == 0}), views={})
    for name, ix, subset, weights in (
            ('full', np.arange(len(rr)), rr, metrics.original_weights(rr)),
            (ev.PRIMARY, keep, primary, metrics.hierarchical_weights(primary, pool))):
        reports = {}
        for j, suffix in enumerate(SUFFIXES):
            report = metrics.report(subset, base[ix, j], corrected[ix, j], weights, eligible[ix], support[ix])
            report['protection'] = ev.protection_gate(report)
            reports[suffix] = report
        result['views'][name] = dict(rows=len(subset), retained_uid_sha256=ev.core._uid_hash([r['uid'] for r in subset]),
                                    weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(), reports=reports)
    return result


def ab_stage(inputs, spec, frozen, dev, metrics, ev):
    require_dev_pass(dev)
    need(not (OUTPUT / 'ab').exists(), 'AB_ALREADY_ATTEMPTED')
    write(OUTPUT / 'ab' / 'AB_ATTEMPT.json', dict(candidate=CANDIDATE, dev_gate_sha256=sha(OUTPUT / 'dev/GATE.json'), retries=0))
    old_result = inputs.json(OLD + 'RESULT.json')
    targets = {'HeimVision Camera', 'unsw-attack-traces-2018:50:c7:bf:00:56:39',
               'unsw-attack-traces-2018:ec:1a:59:79:f4:89', 'unsw-attack-traces-2018:00:16:6c:ab:6b:88'}
    pools = {}
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        progress('AB', 'HIST_DEV 已通过，正在执行一次 A/B 评价', pool=pool)
        item = spec['pools'][pool]
        rr = list(rows(inputs.pin(item['query']['rows']['path'])))
        q = np.load(inputs.pin(item['query']['q14']['path']), mmap_mode='r', allow_pickle=False)
        q_uids = inputs.json(item['query']['q_uids']['path'])
        need(isinstance(q_uids, list), 'Q_UID_ARRAY_SCHEMA')
        with np.load(inputs.pin(OLD + 'ab/' + pool + '/DECISIONS.npz'), allow_pickle=False) as z:
            saved = {k: z[k].copy() for k in z.files}
        need(saved['uid'].tolist() == q_uids == [r['uid'] for r in rr], 'AB_UID_JOIN')
        need(q.shape == (len(rr), 14) and float(saved['selected_lambda']) == .25, 'AB_ARRAY_SCHEMA')
        need(np.array_equal(q[:, 0] == 1, [r['protocol'] == 6 for r in rr]), 'AB_PROTOCOL_JOIN')
        with np.load(inputs.pin(item['baseline_decisions']['path']), allow_pickle=False) as z:
            old = {k: z[k].copy() for k in ('uid', 'base', 'corrected', 'raw_logits')}
        need(np.array_equal(old['uid'], saved['uid']) and np.array_equal(old['base'], saved['base']) and
             np.array_equal(old['raw_logits'], saved['raw_logits']), 'AB_RAW_179700_REPLAY')
        need(np.array_equal(ev.decisions(saved['raw_logits'], frozen), saved['base']), 'AB_RAW_CUT_REPLAY')
        need(np.array_equal(ev.core.apply_correction(saved['raw_logits'], saved['support'], frozen['scales'], .25), saved['corrected_logits']), 'AB_C1_SCORE_REPLAY')
        need(np.array_equal(ev.decisions(saved['corrected_logits'], frozen), saved['corrected']), 'AB_C1_DECISION_REPLAY')
        prior = pool_report(pool, rr, saved['base'], saved['corrected'], saved['eligible'], saved['support'], item['windows'], metrics, ev)
        equal_tree(prior['views'], old_result['pools'][pool]['views'], pool + '/C1_FULL_METRIC_REPLAY')
        guard = syn_guard(q)
        effective = np.where(guard, 0., saved['support'])
        changed = restore_raw(saved['raw_logits'], saved['corrected_logits'], guard)
        need(np.array_equal(changed, ev.core.apply_correction(saved['raw_logits'], effective, frozen['scales'], .25)), 'AB_EFFECTIVE_SUPPORT_EQUIVALENCE')
        after = ev.decisions(changed, frozen)
        need(np.array_equal(after[guard], saved['base'][guard]) and
             np.array_equal(after[~guard], saved['corrected'][~guard]), 'AB_GUARD_ALL_HEADS')
        untouched = np.asarray([r['device'] not in targets for r in rr]) & ~guard
        need(np.array_equal(after[untouched], old['corrected'][untouched]), 'AB_UNTOUCHED_NON_GUARD_179700_REPLAY')
        result = pool_report(pool, rr, saved['base'], after, saved['eligible'], effective, item['windows'], metrics, ev)
        normal = np.asarray([r['label'] == 0 for r in rr])
        audit = {}
        for view, ix in (('full', np.ones(len(rr), dtype=bool)), (ev.PRIMARY, metrics.post_window_mask(rr, item['windows']))):
            audit[view] = dict(guard_rows=int((guard & ix).sum()),
                              normal_guard_rows=int((guard & ix & normal).sum()),
                              attack_guard_rows=int((guard & ix & ~normal).sum()),
                              restored_attacks={s: int((ix & ~normal & ~saved['corrected'][:, j] & after[:, j]).sum()) for j, s in enumerate(SUFFIXES)},
                              returned_normal_alarms={s: int((ix & normal & ~saved['corrected'][:, j] & after[:, j]).sum()) for j, s in enumerate(SUFFIXES)},
                              devices={device: dict(guard_rows=int((ix & guard & np.asarray([r['device'] == device for r in rr])).sum()))
                                       for device in sorted({r['device'] for r in rr})})
        result.update(candidate=CANDIDATE, guard_audit=audit, new_distance_pairs=0,
                      c1_full_metric_replay=True, non_guarded_c1_exact=True, untouched_non_guarded_179700_exact=True)
        result['comparison_C1'] = {view: {s: dict(old_fpr=prior['views'][view]['reports'][s]['corrected']['normal']['weighted_rate'],
                                                new_fpr=result['views'][view]['reports'][s]['corrected']['normal']['weighted_rate'],
                                                old_recall=prior['views'][view]['reports'][s]['corrected']['attack']['weighted_rate'],
                                                new_recall=result['views'][view]['reports'][s]['corrected']['attack']['weighted_rate'])
                                              for s in SUFFIXES} for view in prior['views']}
        write(OUTPUT / 'ab' / pool / 'RESULT.json', result)
        np.savez_compressed(OUTPUT / 'ab' / pool / 'DECISIONS.npz', uid=saved['uid'], guard=guard,
                            raw_logits=saved['raw_logits'], corrected_logits=changed, base=saved['base'],
                            c1_corrected=saved['corrected'], corrected=after, original_support=saved['support'],
                            support=effective, eligible=saved['eligible'], selected_lambda=np.asarray(.25))
        pools[pool] = result
        del rr, q, q_uids, saved, old, prior, guard, effective, changed, after, normal, untouched
        gc.collect()
    result = ev.terminal_gate(pools)
    result.update(candidate=CANDIDATE, pools=pools, AB_evaluated=True, new_distances=0, new_E3=0,
                  model_forwards=0, training=0, reference_changed=False, calibration_refit=0)
    b = pools['UNSW_DEV']['views'][ev.PRIMARY]['reports']['ensemble']['corrected']
    result['protection_stage_status'] = ('PASS_C2_PROTECTION_AND_B_POOL' if not result['protection_failures'] and
                                          b['normal']['weighted_rate'] <= .02 and b['attack']['weighted_rate'] >= .99
                                        else 'FAIL_C2_PROTECTION_OR_B_POOL')
    write(OUTPUT / 'ab' / 'RESULT.json', result)
    return result


def main():
    card = read(HERE / 'EXECUTION_CARD.json')
    need(sha(HERE / 'INPUT_MANIFEST.json') == card['input_manifest_sha256'], 'INPUT_MANIFEST_CHANGED')
    for name, expected in card['code_sha256'].items():
        need(sha(HERE / name) == expected, 'CODE_CHANGED:' + name)
    manifest = read(HERE / 'INPUT_MANIFEST.json')
    inputs = Inputs(manifest)
    need(not OUTPUT.exists(), 'ONE_RUN_OUTPUT_ALREADY_EXISTS')
    OUTPUT.mkdir()
    # Verify shared modules before import. These functions only perform arithmetic.
    for path in manifest['files']:
        if path.endswith('.py'):
            inputs.pin(path)
    sys.path.insert(0, str(ROOT / 'runs/history_normal_reference_keyrepair_v1_20261031'))
    from hnr import evaluation as ev
    metrics = load_module('_c2_ab_metrics', ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py')
    sm = load_module('_c2_source_metrics', ROOT / 'runs/local_geometry_budgeted_v2_replay_repair_r1_20261029/lg/metrics.py')
    try:
        spec = inputs.json(manifest['c1_asset_spec'])
        frozen = {key: inputs.json(spec['calibration'][key]['path']) for key in ('cuts', 'scales')}
        source = source_precheck(inputs, manifest, sm)
        dev = dev_stage(inputs, frozen, ev)
        if dev['status'] != 'PASS_DEV':
            result = dict(status='STOP_DEV_FAIL', candidate=CANDIDATE, AB_evaluated=False,
                          source_status=source['status'], dev=dev, evidence='CONSUMED_DEVELOPMENT_ONLY',
                          new_distances=0, new_E3=0, model_forwards=0, training=0)
        else:
            result = ab_stage(inputs, spec, frozen, dev, metrics, ev)
            result.update(source_status=source['status'], dev=dev)
        result['input_immutability'] = inputs.immutable()
        result['execution_card_sha256'] = sha(HERE / 'EXECUTION_CARD.json')
        write(OUTPUT / 'RESULT.json', result)
        write(OUTPUT / 'ARTIFACTS.json', {p.relative_to(OUTPUT).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size)
                                         for p in OUTPUT.rglob('*') if p.is_file()})
        progress('COMPLETE', 'C2 已完成，结果和验收回执已保存', scientific_status=result['status'],
                 protection_stage_status=result.get('protection_stage_status', '未进入 A/B'), AB_evaluated=result['AB_evaluated'])
    except Exception as exc:
        progress('TECHNICAL_FAILURE', '执行已停止，保留故障现场；未自动重试', error=type(exc).__name__ + ': ' + str(exc))
        (OUTPUT / 'ERROR.txt').write_text(traceback.format_exc(), encoding='utf-8')
        raise


if __name__ == '__main__':
    main()
