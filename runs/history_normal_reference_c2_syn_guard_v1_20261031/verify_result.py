"""Independent saved-array checks and concise C2 readout; no candidate rerun."""
import gc
import hashlib
import json
import math

import numpy as np

from common import HERE, ROOT, OUTPUT, SUFFIXES, load_module, need, read, rows, sha, write


def main():
    card = read(HERE / 'EXECUTION_CARD.json')
    manifest = read(HERE / 'INPUT_MANIFEST.json')
    need(sha(HERE / 'INPUT_MANIFEST.json') == card['input_manifest_sha256'], 'MANIFEST_SEAL')
    for name, expected in card['code_sha256'].items():
        need(sha(HERE / name) == expected, 'CODE_SEAL:' + name)
    for name, expected in manifest['files'].items():
        need(sha(ROOT / name) == expected, 'INPUT_SEAL:' + name)
    artifacts = read(OUTPUT / 'ARTIFACTS.json')
    for name, expected in artifacts.items():
        path = OUTPUT / name
        need(path.stat().st_size == expected['bytes'] and sha(path) == expected['sha256'], 'ARTIFACT_SEAL:' + name)
    runtime = read(HERE / 'RUNTIME_RECEIPT.json')
    need(runtime['status'] == 'COMPLETE' and runtime['returncode'] == 0, 'RUNTIME_FAILURE')
    need(runtime['wall_seconds'] <= card['limits']['wall_seconds'] and runtime['peak_rss_bytes'] <= card['limits']['rss_bytes'], 'RUNTIME_BUDGET')
    result = read(OUTPUT / 'RESULT.json')
    need(result['dev']['status'] == 'PASS_DEV' and result['AB_evaluated'], 'STAGE_ORDER')
    spec = read(ROOT / manifest['c1_asset_spec'])
    cuts = read(ROOT / spec['calibration']['cuts']['path'])
    thresholds = np.asarray(cuts['cuts'] + [cuts['ensemble_cut']], dtype=np.float64)
    metrics = load_module('_c2_independent_weights', ROOT / 'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py')
    readout, checked = {}, 0
    for pool in ('CIC_DEV', 'UNSW_DEV'):
        item = spec['pools'][pool]
        with np.load(OUTPUT / 'ab' / pool / 'DECISIONS.npz', allow_pickle=False) as z:
            actual = {k: z[k].copy() for k in z.files}
        with np.load(ROOT / 'runs/history_normal_reference_d2_trace_v1_20261031/retrieved/ab' / pool / 'DECISIONS.npz', allow_pickle=False) as z:
            old = {k: z[k].copy() for k in ('uid', 'raw_logits', 'corrected_logits', 'base', 'corrected', 'support', 'eligible')}
        need(np.array_equal(actual['uid'], old['uid']), 'UID_IDENTITY')
        q = np.load(ROOT / item['query']['q14']['path'], mmap_mode='r', allow_pickle=False)
        flags = sum(q[:, i + 1].astype(np.uint16) << i for i in range(9))
        guard = (q[:, 0] == 1) & ((flags & 2) != 0) & ((flags & 16) == 0)
        need(np.array_equal(guard, actual['guard']), 'INDEPENDENT_FLAG_DECODE')
        expected = old['corrected_logits'].copy()
        expected[guard] = old['raw_logits'][guard]
        need(np.array_equal(actual['corrected_logits'], expected), 'INDEPENDENT_SCORE_SWITCH')
        expected_scores = np.column_stack([expected, np.stack([expected[:, i] for i in range(3)]).mean(0, dtype=np.float64)])
        need(np.array_equal(actual['corrected'], expected_scores > thresholds), 'INDEPENDENT_STRICT_DECISIONS')
        for name in ('raw_logits', 'base', 'eligible'):
            need(np.array_equal(actual[name], old[name]), 'UNCHANGED:' + name)
        need(np.array_equal(actual['original_support'], old['support']), 'ORIGINAL_SUPPORT')
        need(np.array_equal(actual['support'], np.where(guard, 0., old['support'])), 'EFFECTIVE_SUPPORT')
        rr = list(rows(ROOT / item['query']['rows']['path']))
        need(actual['uid'].tolist() == [r['uid'] for r in rr], 'METADATA_UID_JOIN')
        checked += len(rr)
        views = {}
        for view, ix in (('full', np.ones(len(rr), dtype=bool)), ('post_window_primary', metrics.post_window_mask(rr, item['windows']))):
            ids = np.flatnonzero(ix)
            subset = [rr[int(i)] for i in ids]
            weights = metrics.original_weights(subset) if view == 'full' else metrics.hierarchical_weights(subset, pool)
            normal = np.asarray([r['label'] == 0 for r in subset])
            reports = result['pools'][pool]['views'][view]['reports']
            for j, suffix in enumerate(SUFFIXES):
                for label_name, mask in (('normal', normal), ('attack', ~normal)):
                    values = actual['corrected'][ids, j]
                    den = math.fsum(weights[mask])
                    rate = math.fsum(weights[mask & values]) / den if den else None
                    reported = reports[suffix]['corrected'][label_name]
                    need(int((mask & values).sum()) == reported['positive'], 'INDEPENDENT_COUNT')
                    need((rate is None and reported['weighted_rate'] is None) or math.isclose(rate, reported['weighted_rate'], rel_tol=0, abs_tol=1e-12), 'INDEPENDENT_WEIGHTED_RATE')
                need(reports[suffix]['protection']['status'] == 'PASS', 'PROTECTION_FAILURE')
            ensemble = reports['ensemble']
            views[view] = dict(fpr=ensemble['corrected']['normal']['weighted_rate'],
                               recall=ensemble['corrected']['attack']['weighted_rate'],
                               attack_FN=ensemble['corrected']['attack']['negative'],
                               raw_attack_FN=ensemble['base']['attack']['negative'],
                               added_attack_misses=ensemble['added_attack_misses'],
                               guard=result['pools'][pool]['guard_audit'][view],
                               per_head={s: result['pools'][pool]['comparison_C1'][view][s] for s in SUFFIXES},
                               devices=[dict(device=d['group']['device'], fpr=d['corrected']['normal']['weighted_rate'],
                                             recall=d['corrected']['attack']['weighted_rate'], attack_loss_pp=d['attack_recall_loss_pp'])
                                        for d in ensemble['groups']['device']])
        readout[pool] = views
        del actual, old, q, rr, expected, expected_scores, guard, flags
        gc.collect()
    acceptance = dict(status='PASS', query_rows=checked, pools=2, views_per_pool=2, heads_per_view=4,
                      pinned_inputs_unchanged=len(manifest['files']), artifacts_verified=len(artifacts),
                      guard_decoded_independently=True, score_switch_exact=True, strict_decisions_exact=True,
                      weighted_rates_and_counts_rechecked=True, all_reported_protection_gates_pass=True,
                      candidate_rerun=False, new_model_forwards=0, new_distances=0,
                      scientific_status=result['status'], protection_stage_status=result['protection_stage_status'],
                      source_limitation='G1/S C-own source FPR rises; source diagnostic is not a generalization pass.',
                      result_sha256=sha(OUTPUT / 'RESULT.json'), verifier_sha256=sha(HERE / 'verify_result.py'))
    write(HERE / 'FINAL_ACCEPTANCE.json', acceptance)
    write(HERE / 'RESULT_READOUT.json', dict(acceptance=acceptance, runtime=runtime, pools=readout,
                                            source=read(OUTPUT / 'source/SUMMARY.json'), dev=result['dev'],
                                            target_failures=result['target_failures']))
    print(json.dumps(acceptance), flush=True)


if __name__ == '__main__':
    main()
