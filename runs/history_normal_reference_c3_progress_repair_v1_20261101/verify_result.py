"""Independently verify saved C3 score arithmetic and original weighted metrics."""
from common import *
from hnr import evaluation as ev
from hnr.assets import helpers
import constrained_onboarding_core_v3 as core


def main():
    card, manifest = verify_contract()
    out = HERE / 'output'; result = read(out / 'RESULT.json')
    runtime = read(HERE / 'EVALUATE_RUNTIME.json')
    need(runtime['status'] == 'COMPLETE' and runtime['returncode'] == 0, 'EVALUATION_RUNTIME_COMPLETE')
    recovery = card['technical_recovery']
    need(runtime['cumulative_elapsed_seconds'] <= LIMITS['wall_seconds'], 'CUMULATIVE_WALL_BUDGET')
    need(result['distance_pairs'] + recovery['previous_distance_pairs_upper_bound'] ==
         result['technical_recovery']['cumulative_distance_pairs_upper_bound'] <= LIMITS['distance_pairs'], 'CUMULATIVE_PAIR_BUDGET')
    parent = ROOT / recovery['parent_directory']
    for rel, digest in recovery['parent_evidence_sha256'].items():
        need(sha(parent / rel) == digest, 'ORIGINAL_ATTEMPT_PRESERVED')
    for rel, digest in recovery['reused_assets_sha256'].items():
        need(sha(HERE / rel) == digest, 'REUSED_ASSET_UNCHANGED')
    for rel, meta in read(out / 'ARTIFACTS.json').items():
        need(sha(out / rel) == meta['sha256'] and (out / rel).stat().st_size == meta['bytes'], 'OUTPUT_SEAL')
    assets = read(C1 / 'config/ASSETS.json')
    cuts, scales = (read(ROOT / assets['calibration'][k]['path']) for k in ('cuts', 'scales'))
    metrics = helpers().metrics; count = 0
    for pool in ev.POOLS:
        spec = assets['pools'][pool]; rr = list(rows(ROOT / spec['query']['rows']['path']))
        with np.load(out / f'ab/{pool}/DECISIONS.npz', allow_pickle=False) as z:
            now = {k: z[k].copy() for k in z.files}
        with np.load(C2 / f'output/ab/{pool}/DECISIONS.npz', allow_pickle=False) as z:
            old = {k: z[k].copy() for k in z.files}
        q = np.load(ROOT / spec['query']['q14']['path'], allow_pickle=False)
        decoded_flags = (q[:, 1:10].astype(np.int64) * (1 << np.arange(9))).sum(axis=1)
        guard = (q[:, 0] == 1) & ((decoded_flags & 2) != 0) & ((decoded_flags & 16) == 0)
        need(np.array_equal(guard, now['guard']), 'INDEPENDENT_FLAG_DECODE')
        need(now['uid'].tolist() == old['uid'].tolist() == [r['uid'] for r in rr], 'QUERY_UID_ORDER')
        need(np.array_equal(now['raw_logits'], old['raw_logits']), 'RAW_UNCHANGED')
        need(np.array_equal(now['corrected_logits'][guard], now['raw_logits'][guard]), 'C2_RAW_GUARD')
        changed = core.apply_correction(now['raw_logits'], now['support'], scales, .25)
        need(np.array_equal(changed, now['corrected_logits']), 'SAVED_CORRECTION_ARITHMETIC')
        pred = np.column_stack((changed > np.array(cuts['cuts']), core.ordered_ensemble(changed) > cuts['ensemble_cut']))
        need(np.array_equal(pred, now['corrected']), 'STRICT_THRESHOLD')
        untouched = np.array([r['device'] != HEIM or pool != 'CIC_DEV' for r in rr])
        need(np.array_equal(now['corrected_logits'][untouched], old['corrected_logits'][untouched]), 'UNTOUCHED_ALL_SCORES_EXACT')
        for view, ix in [('full', np.arange(len(rr))), (ev.PRIMARY, np.flatnonzero(metrics.post_window_mask(rr, spec['windows'])))]:
            subset = [rr[int(i)] for i in ix]
            weights = metrics.original_weights(rr) if view == 'full' else metrics.hierarchical_weights(subset, pool)
            expected = result['pools'][pool]['views'][view]
            need(core._uid_hash([r['uid'] for r in subset]) == expected['retained_uid_sha256'], 'VIEW_UID_REPLAY')
            need(hashlib.sha256(weights.tobytes()).hexdigest() == expected['weights_sha256'], 'WEIGHT_REPLAY')
            for j, suffix in enumerate(ev.SUFFIXES):
                check = metrics.report(subset, now['base'][ix, j], pred[ix, j], weights, now['eligible'][ix], now['support'][ix])
                actual = expected['reports'][suffix]
                for key, value in check.items(): need(value == actual[key], 'INDEPENDENT_METRIC:' + key)
                need(ev.protection_gate(check) == actual['protection'], 'INDEPENDENT_PROTECTION')
        count += len(rr)
    expected_gate = c3_gate(result['pools'], read(C2 / 'output/RESULT.json')['pools'])
    need(expected_gate == result['adoption'], 'ADOPTION_GATE_REPLAY')
    freeze = read(out / 'METHOD_FREEZE.json')
    need(freeze['frozen_method'] == expected_gate['frozen_method'] and freeze['candidate_result_sha256'] == sha(out / 'RESULT.json'), 'METHOD_FREEZE_BINDING')
    verify_contract()
    write(HERE / 'FINAL_ACCEPTANCE.json', dict(status='PASS', scientific_status=result['status'],
        adoption=expected_gate, query_rows=count, views_per_pool=2, heads_per_view=4,
        input_pins_unchanged=len(manifest['input_sha256']), model_forwards=0, new_distances=0,
        evaluation_attempt=2, first_completed_candidate_evaluation=True,
        original_attempt_preserved=True, reused_encoded_rows=278,
        cumulative_distance_pairs_upper_bound=result['technical_recovery']['cumulative_distance_pairs_upper_bound'],
        result_sha256=sha(out / 'RESULT.json'), verifier_sha256=sha(Path(__file__))))
    progress('VERIFIED_COMPLETE', 'C3 结果已独立验收，最终方法冻结完成', adoption=expected_gate['status'], frozen_method=expected_gate['frozen_method'])


if __name__ == '__main__': main()
