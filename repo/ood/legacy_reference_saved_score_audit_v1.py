"""Read-only audit of job 172780 and statistics from its already saved scores.

No encoder/model forward, optimizer, Slurm submission, or HOLDOUT access.
The failed source run is never changed. Output is a separate analysis receipt.
"""
from pathlib import Path
from collections import Counter
import copy
import json
import numpy as np
import torch
import legacy_reference_executor_common_v1 as c
import legacy_reference_executor_evaluate_v1 as ev
from legacy_reference_executor_model_v1 import probability

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / 'runs/legacy_reference_hpc_preparation_v1_20260918'
SAMPLE = ROOT / 'runs/legacy_reference_sample_preparation_v1_20260917'
OUT = ROOT / 'runs/legacy_reference_hpc_saved_score_audit_v1_20260922'


def load_scores(path, rows, seeds, with_uid):
    names = ['R'] + [a+'_'+str(s) for a in ('Q', 'M', 'C') for s in seeds] + ['Q', 'M', 'C']
    with np.load(path, allow_pickle=False) as source:
        c.require(set(source.files) == set(names) | ({'uid'} if with_uid else set()), 'SCORE_KEYS')
        if with_uid:
            c.require(np.array_equal(source['uid'], np.array([r['uid'] for r in rows])), 'SCORE_UID_ORDER')
        values = {k: source[k].copy() for k in names}
    for k, v in values.items():
        c.require(v.shape == (len(rows),) and v.dtype == np.float32 and np.isfinite(v).all(), 'SCORE_SHAPE_FINITE:'+k)
    # All devices in this run have references; verify the frozen 3-seed mean.
    for arm in ('Q', 'M', 'C'):
        mean = np.stack([values[arm+'_'+str(s)] for s in seeds]).mean(0, dtype=np.float32)
        c.require(np.array_equal(mean, values[arm]), 'ENSEMBLE_DRIFT:'+arm)
    return values


def reports(rows, values, theta):
    for k, v in values.items():
        # Reject threshold decisions sensitive to float32 sigmoid implementation.
        p64 = 1. / (1. + np.exp(-v.astype(np.float64)))
        c.require(np.array_equal(probability(v) >= theta, p64 >= theta), 'THRESHOLD_NUMERIC_AMBIGUITY:'+k)
    return {k: ev.report(rows, v, theta, values['R']) for k, v in values.items()}


def compare_saved_report(actual, expected, path=''):
    """Counts/identities exact; only weighted float sums can differ by roundoff."""
    if isinstance(actual, dict):
        c.require(isinstance(expected, dict) and set(actual) == set(expected), 'REPORT_KEYS:'+path)
        return max((compare_saved_report(actual[k], expected[k], path+'/'+k) for k in actual), default=0.)
    if isinstance(actual, list):
        c.require(isinstance(expected, list) and len(actual) == len(expected), 'REPORT_LENGTH:'+path)
        return max((compare_saved_report(a, b, path+'/'+str(i)) for i, (a, b) in enumerate(zip(actual, expected))), default=0.)
    if path.endswith('/weighted_rate') and actual is not None and expected is not None:
        difference = abs(actual-expected)
        c.require(np.isfinite(difference) and difference <= 1e-12, 'REPORT_WEIGHTED_SUM:'+path)
        return difference
    c.require(actual == expected, 'REPORT_EXACT_FIELD:'+path)
    return 0.


def main():
    c.require(not OUT.exists(), 'ANALYSIS_OUTPUT_EXISTS')
    torch.set_num_threads(4)
    folder = PREP/'pullback'; extracted = folder/'extracted'; run = extracted/'runs/real_dev'
    archive_sha = (folder/'pullback.tar.gz.sha256').read_text().split()[0]
    c.pin(folder/'pullback.tar.gz', archive_sha)
    manifest = c.load(extracted/'EXPORT_MANIFEST.json')
    for item in manifest['included']:
        path = c.confined(extracted, item['path'])
        c.require(path.stat().st_size == item['bytes'], 'EXPORT_SIZE'); c.pin(path, item['sha256'])
    omissions = {x['path'] for x in manifest['omitted']}
    verified_seal_entries = 0
    for line in (run/'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ', 1); path = c.confined(run, name)
        if path.exists():
            c.pin(path, sha); verified_seal_entries += 1
        else:
            c.require(path.relative_to(extracted).as_posix() in omissions, 'UNDECLARED_MISSING_FILE')
    c.verify_seal(extracted/'runs/preflight')
    preflight = c.load(extracted/'runs/preflight/PASS.json')
    c.require(preflight['status'] == 'PASS' and preflight['checked_inputs'] == 221, 'PREFLIGHT')
    original = c.recipe(); effective = c.load(run/'recipe.json')
    restored = copy.deepcopy(effective)
    for role in original['data']['manifests']:
        restored['data']['manifests'][role]['path'] = original['data']['manifests'][role]['path']
    restored['legacy']['probe_state_path'] = original['legacy']['probe_state_path']
    for key in ('source_root', 'checkpoint_dir', 'vendor_source_manifest'):
        restored['legacy']['model'][key] = original['legacy']['model'][key]
    c.require(restored == original, 'NON_PATH_RECIPE_DRIFT')
    code_root = PREP/'bundle/legacy_reference_hpc_dev_v1_20260918'
    c.verify_seal(code_root)
    for name in ('legacy_reference_executor_evaluate_v1.py', 'legacy_reference_executor_model_v1.py',
                 'legacy_reference_executor_train_v1.py', 'legacy_reference_executor_common_v1.py'):
        c.require(c.sha(ROOT/'repo/ood'/name) == c.sha(code_root/'repo/ood'/name), 'SOURCE_DRIFT:'+name)
    endpoints = ev.check_endpoints(run, effective)
    failure = c.load(run/'failure.json')
    c.require(failure['error'] == "Stop('WORKER_FAILED:EVALUATE_DEV')" and not failure['heldout_opened'], 'SOURCE_STATUS')
    pins = {n: h for h, n in (line.split('  ', 1) for line in (SAMPLE/'SHA256SUMS').read_text().splitlines())}
    for name in ('capture_receipts.json', 'finalized/excluded_capture_modes.json'):
        c.pin(SAMPLE/name, pins[name])
    context_reasons = Counter()
    for receipt in c.load(SAMPLE/'capture_receipts.json'):
        context_reasons.update(receipt.get('context_reasons', {}))
    theta = effective['legacy']['threshold_probability']; seeds = effective['optimization']['seeds']
    cache = c.load(run/'features_LEARN_DEV/cache.json')
    results = {}; budget_verified = False; intervention_results = []; directional = False
    for role in ('DEV', 'LEARN'):
        spec = original['data']['manifests'][role]; path = c.confined(ROOT, spec['path']); c.pin(path, spec['sha256'])
        rows = list(c.rows(path))
        c.require(len(rows) == spec['rows'] and c.uid_sha(r['uid'] for r in rows) == spec['sorted_uid_lines_sha256'], 'MANIFEST_UID_COUNT')
        c.require(len({r['uid'] for r in rows}) == len(rows), 'DUPLICATE_UID')
        c.require(all(r['partition'] == role and r['use'] != 'REFERENCE' for r in rows), 'ROLE')
        c.require(cache['roles'][role]['rows'] == len(rows) and cache['roles'][role]['uid_sha256'] == spec['sorted_uid_lines_sha256'], 'CACHE_IDENTITY')
        c.require(all(d['references'] > 0 for d in effective['data']['devices'] if d['partition'] == role), 'ABSENT_REFERENCE_UNSUPPORTED')
        folder = run/('evaluation_'+role)
        values = load_scores(folder/'logits.npz', rows, seeds, True)
        computed = reports(rows, values, theta)
        # The exported feature annotations were intentionally omitted. They affect
        # only the Philips TCP80 control, not the general/device/mode statistics.
        philips = any(r['device'] == 'Philips Hue Bridge' for r in rows)
        if philips:
            for report in computed.values():
                report['philips_local_inbound_tcp80'] = {'status': 'UNAVAILABLE_EXPORTED_ANNOTATIONS_OMITTED'}
        if role == 'DEV':
            c.require(not philips, 'DEV_ANNOTATIONS_REQUIRED')
            small = load_scores(folder/'budget16_logits.npz', rows, seeds, False)
            budget = reports(rows, small, theta)
            weighted_roundoff = compare_saved_report(budget, c.load(folder/'budget16.json'))
            budget_verified = True
            for control in effective['evaluation']['interventions']:
                if control.get('partition') != role:
                    if control.get('device') in {r['device'] for r in rows} and control['status'] != 'DEFINED':
                        intervention_results.append(control)
                    continue
                subset = [r for r in rows if r['device'] == control['device'] and r['timestamp'] > control['applicable_after']]
                c.require(len(subset) == control['applicable_query_count'] and c.digest(sorted(r['uid'] for r in subset)) == control['applicable_query_uid_hash'], 'INTERVENTION_UID')
                comparisons = {}
                for label in ('correct', 'wrong'):
                    saved = load_scores(folder/(control['device'].replace(' ', '_')+'_'+label+'.npz'), subset, seeds, False)
                    comparisons[label] = reports(subset, saved, theta)
                a = comparisons['correct']['C']['overall']; b = comparisons['wrong']['C']['overall']
                support = (a['normal']['weighted_rate'] is not None and b['normal']['weighted_rate'] is not None
                           and a['normal']['weighted_rate'] < b['normal']['weighted_rate']
                           and a['attack']['weighted_rate'] is not None
                           and a['attack']['weighted_rate'] >= b['attack']['weighted_rate']-.01-1e-12)
                directional |= support
                intervention_results.append(dict(device=control['device'], status='DEFINED', directional_support=support, comparisons=comparisons, control=control))
            gate = ev.gate_from_reports(computed, effective['data']['devices'], c.digest(effective), True)
            gate['endpoint_receipt_pins'] = endpoints
            gate['C_mechanism_claim_supported'] = bool('C' in gate['passing_arms'] and gate['C_vs_M_joint_comparison_pass'] and directional)
            gate['intervention_direction_rule'] = 'Correct reference lowers normal FPR versus equal-budget wrong reference with at most 1pp overall attack loss on >=1 DEV device; report every mode separately, no significance claim.'
        results[role] = dict(role=role, rows=len(rows), in_sample=role == 'LEARN', reports=computed,
                             recipe_digest=c.digest(effective), threshold_probability=theta,
                             protocol_counts=dict(Counter(r['protocol'] for r in rows)),
                             annotations_omitted_control_unavailable=philips)
        print('SAVED_SCORE_STATISTICS_READY', role, len(rows), flush=True)
        del rows, values, computed
    OUT.mkdir()
    for role, result in results.items(): c.atomic_json(OUT/(role+'_saved_score_statistics.json'), result)
    c.atomic_json(OUT/'DEV_gate.json', gate)
    c.atomic_json(OUT/'DEV_interventions.json', intervention_results)
    c.atomic_json(OUT/'coverage_metadata.json', dict(excluded_capture_modes=c.load(SAMPLE/'finalized/excluded_capture_modes.json'),
        preparation_context_exclusions_287_indexed_captures=dict(context_reasons),
        counts_scope='Original preparation metadata across indexed captures; not scored packet denominators.'))
    receipt = dict(status='SAVED_SCORE_ANALYSIS_COMPLETE', source_slurm_status='FAILED', job_id=172780,
        archive_sha256=archive_sha, included_files_verified=len(manifest['included']), declared_omissions=len(omissions),
        available_run_seal_entries_verified=verified_seal_entries, full_feature_cache_locally_reverified=False,
        nine_endpoints_verified=True, numerical_preflight=preflight, frozen_recipe_sha256=c.RECIPE_SHA,
        budget16_counts_and_nonweighted_fields_exact_match=budget_verified,
        budget16_weighted_rate_max_absolute_difference=weighted_roundoff,
        weighted_sum_check_tolerance=1e-12, scientific_gate_tolerances_unchanged=True,
        real_model_forwards=0, optimizer_steps=0, heldout_opened=False,
        original_run_modified=False, gate_open=gate['open'],
        limitations=['Original job remains FAILED; this is saved-score analysis, not a rerun or repaired full chain.',
                    'Feature arrays and packet annotations were excluded from export; full remote cache seal not locally reproducible.',
                    'LEARN Philips inbound TCP80 control unavailable; DEV has no Philips rows.',
                    'DEV and intervention scores already existed. No new predictions, threshold search, or HOLDOUT decision.'],
        source_pins={str(p.relative_to(ROOT)).replace('\\','/'): c.sha(p) for p in
                     [Path(__file__), extracted/'EXPORT_MANIFEST.json', run/'SHA256SUMS', SAMPLE/'SHA256SUMS']})
    c.atomic_json(OUT/'audit_receipt.json', receipt); c.seal(OUT)
    print(json.dumps({'output':str(OUT),'gate':gate}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
