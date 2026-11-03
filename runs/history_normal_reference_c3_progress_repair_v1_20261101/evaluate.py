"""One terminal C3 evaluation; frozen saved heads, C2 guard, no retuning."""
import gc
from common import *
from hnr.assets import load_assets, joined, helpers
from hnr import evaluation as ev
import constrained_onboarding_core_v3 as core


class PairBudget:
    def __init__(self, previous_upper_bound=0):
        self.total = 0
        self.previous_upper_bound = previous_upper_bound
    def pairs(self, n):
        need(self.previous_upper_bound + self.total + n <= LIMITS['distance_pairs'], 'DISTANCE_PAIR_LIMIT')
        self.total += n
    def update(self, stage, **values):
        progress(stage, '正在计算唯一 C3 的参考支持', **values, total_distance_pairs=self.total,
                 cumulative_distance_pairs_upper_bound=self.previous_upper_bound + self.total)


def saved_c2(pool, rr):
    with np.load(C2 / f'output/ab/{pool}/DECISIONS.npz', allow_pickle=False) as z:
        result = {k: z[k].copy() for k in z.files}
    need(result['uid'].tolist() == [r['uid'] for r in rr], 'C2_UID_JOIN')
    return result


def validate_dev():
    # No B reference changed: recheck the saved gate without running distances.
    old_gate = read(C2 / 'output/dev/GATE.json')
    rr = list(rows(D2 / 'retrieved/dev/QUERIES.jsonl.gz'))
    with np.load(C2 / 'output/dev/DECISIONS.npz', allow_pickle=False) as z:
        need(z['uid'].tolist() == [r['uid'] for r in rr], 'HIST_DEV_UID_JOIN')
        gate = ev.dev_gate(rr, z['base'][:, 3], z['corrected'][:, 3])
    for name in ('status', 'pooled', 'devices', 'query_uid_sha256'):
        need(gate[name] == old_gate[name], 'HIST_DEV_REUSE_REPLAY')
    need(gate['status'] == 'PASS_DEV', 'HIST_DEV_FAILED')
    gate.update(reused_unchanged_B_refs=True, new_distances=0, A_attack_safety_proven=False)
    return gate


def report(pool, rr, saved, corrected, support, eligible, spec, frozen):
    metrics = helpers().metrics
    metrics.validate_full_weights(rr, pool)
    keep = np.flatnonzero(metrics.post_window_mask(rr, spec['windows']))
    views = {}
    for view, ix in [('full', np.arange(len(rr))), (ev.PRIMARY, keep)]:
        subset = [rr[int(i)] for i in ix]
        weights = metrics.original_weights(rr) if view == 'full' else metrics.hierarchical_weights(subset, pool)
        reports = {}
        for j, head in enumerate(ev.SUFFIXES):
            one = metrics.report(subset, saved['base'][ix, j], corrected[ix, j], weights, eligible[ix], support[ix])
            one['protection'] = ev.protection_gate(one)
            normal = np.array([r['label'] == 0 for r in subset])
            old, new = saved['corrected'][ix, j], corrected[ix, j]
            one['relative_C2'] = dict(normal_fixed=int((normal & old & ~new).sum()),
                added_normal_alarms=int((normal & ~old & new).sum()),
                new_attack_misses=int((~normal & old & ~new).sum()),
                newly_missed_uids=[subset[k]['uid'] for k in np.flatnonzero(~normal & old & ~new)])
            reports[head] = one
        views[view] = dict(rows=len(ix), retained_uid_sha256=core._uid_hash([r['uid'] for r in subset]),
            weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(), reports=reports)
    return dict(pool=pool, query_rows=len(rr), original_devices=sorted({r['device'] for r in rr if r['label'] == 0}), views=views)


def main():
    card, manifest = verify_contract()
    need(read(HERE / 'IMPLEMENTATION_CHECK.json')['status'] == 'PASS', 'ENGINEERING_REQUIRED')
    encoded = HERE / 'retrieved/encoded'
    receipt = read(encoded / 'ENCODE_RESULT.json')
    need(receipt['status'] == 'COMPLETE' and receipt['candidate'] == CANDIDATE, 'ENCODING_REQUIRED')
    recovery = card['technical_recovery']
    parent = ROOT / recovery['parent_directory']
    need(sha(parent / 'EXECUTION_CARD.json') == recovery['encoder_execution_card_sha256'], 'PARENT_CONTRACT_PIN')
    need(receipt['execution_card_sha256'] == recovery['encoder_execution_card_sha256'], 'ENCODER_CONTRACT_PIN')
    for rel, digest in recovery['parent_evidence_sha256'].items():
        need(sha(parent / rel) == digest, 'PARENT_EVIDENCE_PIN:' + rel)
    need(not (parent / 'output/RESULT.json').exists() and not (parent / 'output/ab').exists(), 'NO_PRIOR_CANDIDATE_RESULT')
    need(receipt['request_sha256'] == sha(HERE / 'ENCODE_REQUEST.json'), 'ENCODER_REQUEST_PIN')
    for name, expected in receipt['files'].items(): need(sha(encoded / name) == expected, 'ENCODED_RESULT_PIN')
    new_rows = list(rows(encoded / 'references.jsonl.gz'))
    need(new_rows == list(rows(HERE / 'prepared/REFERENCES.jsonl.gz')), 'ENCODED_SELECTION_CHANGED')
    with np.load(encoded / 'references.npz', allow_pickle=False) as z:
        need(z['uid'].tolist() == [r['uid'] for r in new_rows], 'NEW_REFERENCE_UID_JOIN')
        new = joined(new_rows, z['e3'].copy(), z['q14'].copy())
    need(0 < len(new_rows) <= 278 and all(r['device'] == HEIM and r['use'] == 'REFERENCE' and r['label'] == 0 for r in new_rows), 'NEW_REFERENCE_SCOPE')
    out = HERE / 'output'; out.mkdir(exist_ok=False)
    progress('HIST_DEV', '正在核对未改动的历史开发门')
    dev = validate_dev(); write(out / 'DEV_GATE.json', dev)
    write(out / 'AB_ATTEMPT.json', dict(candidate=CANDIDATE, retries=0, dev_gate_sha256=sha(out / 'DEV_GATE.json')), exclusive=True)
    assets = load_assets(); frozen = assets.calibration(); previous = read(C2 / 'output/RESULT.json')['pools']
    runtime = PairBudget(recovery['previous_distance_pairs_upper_bound']); results = {}
    for pool in ev.POOLS:
        item = assets.spec['pools'][pool]
        rr = assets.inputs.rows(item['query']['rows'])
        saved = saved_c2(pool, rr)
        q = np.load(assets.inputs.pin(item['query']['q14']), allow_pickle=False)
        need(np.array_equal(saved['guard'], (q[:, 0] == 1) & (q[:, 2] == 1) & (q[:, 5] == 0)), 'C2_GUARD')
        need(np.array_equal(ev.decisions(saved['raw_logits'], frozen), saved['base']), 'RAW_VERDICT_REPLAY')
        support, eligible = saved['support'].copy(), saved['eligible'].copy()
        changed = saved['corrected_logits'].copy()
        selected = np.array([], dtype=np.int64)
        if pool == 'CIC_DEV':
            data = assets.queries(pool)
            need(np.array_equal(data['logits'], saved['raw_logits']), 'FROZEN_HEAD_LOGITS')
            need(not {r['uid'] for r in new_rows} & {r['uid'] for r in rr}, 'NEW_REF_QUERY_OVERLAP')
            dense, old = assets.dense(pool), assets.a_history()
            from hnr.encoding import concatenate
            history = concatenate([old, new]); history = joined(history['rows'], history['e3'], history['q14'])
            merged = ev.union_bank(dense, history)
            bank = ev._bank(merged, frozen['normalizer'], history_replay=True)
            # Guarded scores are RAW by definition. No distance is necessary for them.
            selected = np.flatnonzero(np.array([r['device'] == HEIM for r in rr]) & ~saved['guard'])
            subset = ev._subset(data, selected)
            static_pairs = ev._actual_pairs(bank, subset['rows'])
            need(runtime.previous_upper_bound + static_pairs <= LIMITS['distance_pairs'], 'STATIC_DISTANCE_BOUND')
            write(out / 'PAIR_PLAN.json', dict(rows=len(selected), pairs=static_pairs, limit=LIMITS['distance_pairs'],
                previous_distance_pairs_upper_bound=runtime.previous_upper_bound,
                cumulative_upper_bound=runtime.previous_upper_bound + static_pairs, guard_distances_skipped=True))
            trace = ev.support_once(bank, subset, frozen['geometry'], runtime, 'A_SUPPORT')
            need(trace['distance_pairs'] == static_pairs, 'ACTUAL_PAIR_COUNT')
            need(np.all(trace['support'] >= support[selected] - 1e-12), 'SUPPORT_NOT_MONOTONE')
            support[selected], eligible[selected] = trace['support'], trace['eligible']
            changed[selected] = core.apply_correction(saved['raw_logits'][selected], support[selected], frozen['scales'], .25)
            del data, subset, dense, old, history, merged, bank, trace
        after = ev.decisions(changed, frozen)
        untouched = np.ones(len(rr), dtype=bool); untouched[selected] = False
        need(np.array_equal(changed[untouched], saved['corrected_logits'][untouched]), 'UNTOUCHED_SCORE_CHANGED')
        need(np.array_equal(after[saved['guard']], saved['base'][saved['guard']]), 'SYN_GUARD_VIOLATED')
        need(not np.any(after & ~saved['base']), 'RAW_MONOTONICITY')
        result = report(pool, rr, saved, after, support, eligible, item, frozen)
        result.update(candidate=CANDIDATE, untouched_scores_exact=True, new_reference_rows=len(new_rows) if pool == 'CIC_DEV' else 0)
        destination = out / 'ab' / pool; destination.mkdir(parents=True)
        np.savez_compressed(destination / 'DECISIONS.npz', uid=saved['uid'], raw_logits=saved['raw_logits'],
            corrected_logits=changed, corrected=after, c2_corrected=saved['corrected'], guard=saved['guard'],
            base=saved['base'], support=support, eligible=eligible, selected_lambda=np.asarray(.25))
        write(destination / 'RESULT.json', result); results[pool] = result
        progress('POOL_COMPLETE', '本池一次评价完成', pool=pool,
                 primary_FPR=result['views'][ev.PRIMARY]['reports']['ensemble']['corrected']['normal']['weighted_rate'])
        del rr, saved, q, changed, support, eligible, after; gc.collect()
    result = ev.terminal_gate(results)
    gate = c3_gate(results, previous)
    result.update(candidate=CANDIDATE, pools=results, adoption=gate, dev=dev, new_E3_rows=len(new_rows),
        distance_pairs=runtime.total, new_query_encoding=0, training=0, calibration_refit=0,
        AB_evaluated=True, evidence='CONSUMED_DEVELOPMENT_ONLY', method_frozen=True)
    result['technical_recovery'] = dict(parent_directory=recovery['parent_directory'],
        evaluation_attempt=2, first_completed_candidate_evaluation=True,
        previous_distance_pairs_upper_bound=runtime.previous_upper_bound,
        cumulative_distance_pairs_upper_bound=runtime.previous_upper_bound + runtime.total,
        previous_elapsed_seconds=recovery['previous_elapsed_seconds'], new_HPC_jobs=0,
        new_reference_selection=False, new_encoding=False)
    assets.immutable(); verify_contract()
    write(out / 'RESULT.json', result)
    write(out / 'METHOD_FREEZE.json', dict(**gate, candidate_result_sha256=sha(out / 'RESULT.json'),
        baseline_C2_result_sha256=sha(C2 / 'output/RESULT.json'), next_work=['untouched_external_validation', 'strong_baselines', 'paper']))
    write(out / 'ARTIFACTS.json', {p.relative_to(out).as_posix(): dict(sha256=sha(p), bytes=p.stat().st_size) for p in out.rglob('*') if p.is_file()})
    progress('COMPLETE', '唯一 C3 已完成，结果待独立验收；方法已按预设规则冻结', adoption=gate['status'], frozen_method=gate['frozen_method'], scientific_status=result['status'])


if __name__ == '__main__': main()
