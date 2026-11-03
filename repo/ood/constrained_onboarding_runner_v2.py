"""Source-only fitting and paired development entry point; no training/downloads.

The QUERY_TAIL adapter supplies verified current-input caches directly. A sealed
portable bundle is supported only for synthetic verification. Later heads need
their own verified producer before production use.
New reference policies require real, joined RECENT reference features.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import sys
import numpy as np
from indexed_features_v1 import matrix, take, hash_matrix
import continuous_common_v3 as c
import constrained_onboarding_core_v2 as core
import constrained_onboarding_evaluate_v1 as evaluation

PROTOCOL_SHA = '2fae0e1c8e1b5d6c04de8a972bfe0212ecfad27dbaf91066d267ccc746aaa4b5'
INPUT_VERSION = 'continuous-input-core-repair-design-v3-20260929'
SCHEMA = 'constrained-onboarding-bundle-v1'
POLICIES = ('OLD_BANK', 'B0', 'B1', 'B2')


def json_value(value):
    if isinstance(value, np.ndarray):
        return json_value(value.tolist())
    if isinstance(value, np.generic):
        return json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    return value


def _uids(data):
    return [r['uid'] for r in data['rows']]


def _joined(data, *, logits=False):
    rows = data['rows']; uids = _uids(data)
    c.require(len(set(uids)) == len(rows), 'DUPLICATE_UID')
    c.require(list(data['feature_uids']) == list(data['q_uids']) == uids, 'ASSET_UID_JOIN')
    c.require(matrix(data['e3']).shape == (len(rows), 768) and
              matrix(data['q14']).shape == (len(rows), 14), 'ASSET_SHAPE')
    if logits:
        x = np.asarray(data['logits'])
        c.require(x.shape == (len(rows), 3) and np.isfinite(x).all(), 'HEAD_LOGITS')


def subset(data, indices):
    ix = np.asarray(indices, dtype=np.int64)
    rows = [data['rows'][int(i)] for i in ix]
    return dict(rows=rows, e3=take(data['e3'], ix), q14=take(data['q14'], ix),
                feature_uids=[r['uid'] for r in rows], q_uids=[r['uid'] for r in rows])


def bank_from(data, normalizer, source=False):
    _joined(data)
    return core.ReferenceBank(data['rows'], data['e3'], data['q14'], normalizer,
                              feature_uids=data['feature_uids'], q_uids=data['q_uids'],
                              allowed_partitions={'LEARN'} if source else {'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 'HOLDOUT'})


def support_for(bank, data, geometry, override=None):
    return bank.own(data['rows'], data['e3'], data['q14'], geometry,
                    feature_uids=data['feature_uids'], q_uids=data['q_uids'], override=override)


def _bank_identity(data):
    h = hashlib.sha256()
    h.update(c.digest(data['rows']).encode())
    for key in ('e3', 'q14'):
        hash_matrix(h, data[key])
    return h.hexdigest()


def _validate_bundle(bundle, protocol):
    c.require(bundle.get('schema') == SCHEMA and bundle.get('input_version') == INPUT_VERSION, 'CURRENT_INPUT_REQUIRED')
    c.require(bundle.get('protocol_sha256') == PROTOCOL_SHA, 'ONBOARDING_PROTOCOL_IDENTITY')
    c.require(type(bundle.get('synthetic_only')) is bool, 'SYNTHETIC_FLAG_REQUIRED')
    c.require(bundle.get('head_family') in ('QUERY_TAIL', 'QUERY_BCE', 'RECENT_TAIL', 'MLP_QUERY_BCE', 'TabM', 'LightGBM'), 'HEAD_FAMILY')
    c.require(set(bundle['targets']) <= set(evaluation.REQUIRED_POOLS) and bool(bundle['targets']), 'TARGET_POOL_SCOPE')
    for key, role in (('source_fit', 'FIT'), ('source_cal', 'CAL')):
        data = bundle[key]; _joined(data, logits=True)
        c.require(all(r['partition'] == 'LEARN' and r.get('fit_role') == role and
                      r['use'] != 'REFERENCE' for r in data['rows']), 'SOURCE_ROLE:'+role)
        c.require({r['label'] for r in data['rows']} == {0, 1}, 'SOURCE_CLASSES:'+role)
    fit, cal = bundle['source_fit']['rows'], bundle['source_cal']['rows']
    c.require(not {r['uid'] for r in fit} & {r['uid'] for r in cal}, 'FIT_CAL_UID_OVERLAP')
    c.require(not {r['component_id'] for r in fit} & {r['component_id'] for r in cal}, 'FIT_CAL_COMPONENT_OVERLAP')
    _joined(bundle['source_references'])
    all_query_uids = {r['uid'] for r in fit+cal}
    all_reference_uids = set(_uids(bundle['source_references']))
    for pool, data in bundle['targets'].items():
        _joined(data, logits=True)
        c.require(not all_query_uids & set(_uids(data)), 'CROSS_POOL_UID_OVERLAP')
        all_query_uids.update(_uids(data))
        partition = 'EXTERNAL_ARCHIVAL_EVALUATION' if pool == 'UNSW_DEV' else 'DEV' if pool == 'CIC_DEV' else 'HOLDOUT'
        c.require(all(r['partition'] == partition and r['use'] != 'REFERENCE' for r in data['rows']), 'TARGET_ROLE')
        c.require(set(data['banks']) <= set(POLICIES) and 'OLD_BANK' in data['banks'], 'BANK_POLICIES')
        for policy, bank in data['banks'].items():
            _joined(bank)
            all_reference_uids.update(_uids(bank))
            c.require(all(r['partition'] == partition for r in bank['rows']), 'BANK_PARTITION')
            c.require(not all_query_uids & set(_uids(bank)), 'REFERENCE_QUERY_UID_OVERLAP')
            if policy != 'OLD_BANK':
                receipt = bank.get('preparation_receipt', {})
                feature_ready = receipt.get('real_recent_features') is True or (
                    bundle['synthetic_only'] and receipt.get('synthetic_only') is True and
                    receipt.get('status') == 'SYNTHETIC_COMPLETE')
                c.require(receipt.get('policy') == policy and receipt.get('input_version') == INPUT_VERSION and
                          feature_ready and
                          receipt.get('complete_candidate_census') is True, 'UNIFIED_BANK_PREPARATION_REQUIRED')
                if not bundle['synthetic_only']:
                    c.require(receipt.get('synthetic_only') is False and receipt.get('status') == 'COMPLETE', 'REAL_BANK_RECEIPT')
                    t0_key = 'CIC_t0' if pool == 'CIC_DEV' else 'UNSW_t0' if pool == 'UNSW_DEV' else None
                    c.require(t0_key is not None, 'THREE_DEVICE_UNIFIED_WINDOW_NOT_REGISTERED')
                    t0 = protocol['reference_experiments']['unified_policy'][t0_key]
                    cutoff = t0+protocol['reference_experiments'][policy]['duration_seconds']
                    c.require(receipt.get('t0') == t0 and receipt.get('cutoff') == cutoff and
                              all(t0 <= r['timestamp'] <= cutoff and r['reference_end'] == cutoff
                                  for r in bank['rows']), 'REGISTERED_REFERENCE_WINDOW')
    c.require(not all_query_uids & all_reference_uids, 'REFERENCE_QUERY_UID_OVERLAP')
    if bundle['synthetic_only']:
        c.require(max(len(fit), len(cal), *(len(d['rows']) for d in bundle['targets'].values())) <= 256, 'SYNTHETIC_SIZE_BOUND')
        return
    c.require(len(fit) == 617908 and len(cal) == 148819 and len(bundle['source_references']['rows']) == 104, 'FULL_SOURCE_COUNTS')
    c.require(sum(r['label'] == 0 for r in fit) == 134493 and sum(r['label'] == 0 for r in cal) == 33147, 'FULL_SOURCE_CLASS_COUNTS')
    for pool, count in protocol['evaluation']['first_development_pools'].items():
        c.require(pool in bundle['targets'] and len(bundle['targets'][pool]['rows']) == count, 'FULL_TARGET_COUNT:'+pool)
    c.require(bundle.get('provenance', {}).get('verified_current_parent') is True, 'VERIFIED_PARENT_REQUIRED')


def _write_trace(path, rows, trace, head, corrected):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as stream:
        for i, row in enumerate(rows):
            entry = {key: value[i] for key, value in trace.items() if isinstance(value, np.ndarray) and len(value) == len(rows)}
            entry.update(uid=row['uid'], head_logits=head[i], corrected_logits=corrected[i], correction=head[i]-corrected[i])
            stream.write(json.dumps(json_value(entry), ensure_ascii=True, allow_nan=False, separators=(',', ':'))+'\n')


def _decisions(logits, cuts, ensemble_cut):
    x = np.asarray(logits, dtype=np.float64)
    return np.column_stack((x > np.asarray(cuts), core.ordered_ensemble(x) > ensemble_cut))


def wrong_reference_controls(data, bank, geometry, scales, selected_lambda, cuts, ensemble_cut, pool):
    """Only explicit metadata-frozen plans; no target-score donor selection."""
    # The caller passes exactly one policy's assets, never a global UID roster.
    plans = data.get('wrong_reference_controls', [])
    if not plans:
        return [dict(status='NOT_AVAILABLE', reason='NO_PREDECLARED_MATCHED_DONOR_PLAN')]
    answer = []
    lookup = {r['uid']: r for r in bank.rows}
    for plan in plans:
        proto, device, donor = plan['protocol'], plan['device'], plan['donor_device']
        c.require(device != donor and plan.get('selection_basis') == 'METADATA_ONLY_BEFORE_TARGET_SCORES', 'CONTROL_PLAN_SCOPE')
        correct, wrong = plan['correct_reference_uids'], plan['wrong_reference_uids']
        c.require(len(correct) == len(wrong) >= 2 and len(set(correct)) == len(correct) and len(set(wrong)) == len(wrong), 'CONTROL_BUDGET')
        refs = [[lookup[u] for u in ids] for ids in (correct, wrong)]
        for rr, owner in zip(refs, (device, donor)):
            c.require(all(r['device'] == owner and r['protocol'] == proto for r in rr) and
                      len({r['component_id'] for r in rr}) == len(rr), 'CONTROL_OWNER_COMPONENTS')
        c.require({r['reference_end'] for r in refs[0]} == {r['reference_end'] for r in refs[1]} and
                  len({r['partition'] for rr in refs for r in rr}) == 1, 'CONTROL_TIME_PARTITION_MATCH')
        if any('observation_t0' in r for rr in refs for r in rr):
            c.require(all('observation_t0' in r for rr in refs for r in rr) and
                      len({r['observation_t0'] for rr in refs for r in rr}) == 1, 'CONTROL_OBSERVATION_BUDGET')
        ix = [i for i, r in enumerate(data['rows']) if r['device'] == device and r['protocol'] == proto]
        if not ix:
            answer.append(dict(status='NOT_AVAILABLE', device=device, protocol=proto, reason='NO_QUERY_ROWS'))
            continue
        sub = subset(data, ix); head = np.asarray(data['logits'])[ix]
        entry = dict(status='MATCHED_METADATA_PLAN', device=device, protocol=proto, donor_device=donor)
        for which, ids in (('correct', correct), ('wrong', wrong)):
            key = (sub['rows'][0]['partition'], device, proto)
            trace = support_for(bank, sub, geometry, override={key: ids})
            changed = core.apply_correction(head, trace['support'], scales, selected_lambda)
            entry[which] = evaluation.paired_report(sub['rows'], head, changed, cuts, ensemble_cut, trace, pool)[0]
        answer.append(entry)
    return answer


def run_development(bundle, output, protocol_path):
    """Run fixed source fitting then all declared target policies, without retries."""
    protocol = c.read(c.pin(protocol_path, PROTOCOL_SHA))
    _validate_bundle(bundle, protocol)
    out = Path(output).resolve()
    for protected in bundle.get('provenance', {}).get('protected_paths', []):
        c.require(not out.is_relative_to(Path(protected).resolve()), 'OUTPUT_INSIDE_INPUT')
    out.mkdir(parents=True, exist_ok=False)
    phase = 'SOURCE_FITTING'
    def progress(stage):
        nonlocal phase
        phase = stage
        c.write(out/'status.json', dict(stage=stage, status='RUNNING', synthetic_only=bundle['synthetic_only'],
                                       optimizer_updates=0, retries=0), replace=True)
    try:
        c.write(out/'input_identity.json', json_value(dict(schema=SCHEMA, head_family=bundle['head_family'],
            protocol_sha256=PROTOCOL_SHA, synthetic_only=bundle['synthetic_only'], provenance=bundle.get('provenance', {}),
            source_reference_identity=_bank_identity(bundle['source_references']),
            normalizer_digest=c.digest([np.asarray(x).tolist() for x in bundle['normalizer']]),
            original_cuts=list(bundle['cuts']), original_ensemble_cut=bundle['ensemble_cut'],
            source_fit_uid=c.uid_sha(_uids(bundle['source_fit'])), source_cal_uid=c.uid_sha(_uids(bundle['source_cal'])),
            targets={p:dict(uid_sha256=c.uid_sha(_uids(d)), policies={name:_bank_identity(b) for name,b in d['banks'].items()},
                            wrong_reference_controls={name:b.get('wrong_reference_controls', []) for name,b in d['banks'].items()})
                     for p,d in bundle['targets'].items()})))
        progress('SOURCE_GEOMETRY')
        fit, cal = bundle['source_fit'], bundle['source_cal']
        source_bank = bank_from(bundle['source_references'], bundle['normalizer'], source=True)
        normal = subset(fit, [i for i, r in enumerate(fit['rows']) if r['label'] == 0])
        geometry = core.fit_geometry(normal['rows'], normal['e3'], normal['q14'], source_bank,
                                     feature_uids=normal['feature_uids'], q_uids=normal['q_uids'])
        del normal
        scales = core.fit_scales(fit['rows'], fit['logits'])
        progress('SOURCE_ATTACK_PROTECTION')
        ix = [i for i, r in enumerate(cal['rows']) if r['label'] == 1]
        attacks = subset(cal, ix)
        cuts, ensemble_cut = np.asarray(bundle['cuts'], dtype=np.float64), float(bundle['ensemble_cut'])
        protection = core.choose_lambda(attacks['rows'], np.asarray(cal['logits'])[ix], cuts, ensemble_cut,
                                         scales, source_bank, attacks['e3'], attacks['q14'], geometry,
                                         feature_uids=attacks['feature_uids'], q_uids=attacks['q_uids'])
        del attacks
        if not bundle['synthetic_only']:
            expected = protocol['source_protection']['verified_metadata_support']
            for proto, field in [('6', 'FIT_normal_TCP_radius_rows'), ('17', 'FIT_normal_UDP_radius_rows')]:
                c.require(geometry['protocols'][proto]['rows'] == expected[field], 'SOURCE_GEOMETRY_DENOMINATOR')
            c.require(protection['eligible_pairs'] == expected['CAL_attack_source_bank_pairs'], 'SOURCE_DONOR_DENOMINATOR')
        calibration = out/'calibration'; calibration.mkdir()
        c.write(calibration/'geometry.json', geometry); c.write(calibration/'scales.json', scales)
        c.write(calibration/'protection.json', protection)
        c.write(calibration/'cuts.json', dict(seeds=core.SEEDS, cuts=cuts.tolist(), ensemble_cut=ensemble_cut, moved=False))
        c.seal(calibration); c.verify(calibration)
        selected_lambda = protection['selected_lambda']
        source_checks = []
        if 'recent_decisions' in cal:
            trace = support_for(source_bank, cal, geometry)
            scores = core.apply_correction(cal['logits'], trace['support'], scales, selected_lambda)
            source_checks = evaluation.protocol_regressions(cal['rows'], cal['recent_decisions'],
                                                            _decisions(scores, cuts, ensemble_cut), 'CAL')
        policy_results, policy_checks = {}, {}
        for pool, data in bundle['targets'].items():
            # Source calibration is already sealed; target labels cannot select parameters.
            cache = {}
            late_cutoff = ({'CIC_DEV': protocol['reference_experiments']['unified_policy']['CIC_t0'],
                            'UNSW_DEV': protocol['reference_experiments']['unified_policy']['UNSW_t0']}.get(pool))
            if late_cutoff is not None:
                late_cutoff += 7200
            for policy in POLICIES:
                if policy not in data['banks']:
                    continue
                progress('TARGET_'+pool+'_'+policy)
                assets = data['banks'][policy]; identity = _bank_identity(assets)
                dest = out/pool/policy; dest.mkdir(parents=True)
                if identity in cache:
                    original, result, checks = cache[identity]
                    c.write(dest/'equivalence.json', dict(reused_from=original, bank_identity=identity,
                        meaning='Identical actual reference rows, features and q14; no independent evidence'))
                else:
                    bank = bank_from(assets, bundle['normalizer'])
                    trace = support_for(bank, data, geometry)
                    corrected = core.apply_correction(data['logits'], trace['support'], scales, selected_lambda)
                    result, before, after = evaluation.paired_report(data['rows'], data['logits'], corrected,
                        cuts, ensemble_cut, trace, pool, late_cutoff=late_cutoff)
                    checks = evaluation.protocol_regressions(data['rows'], data['recent_decisions'], after, pool) \
                        if pool == 'CIC_DEV' and 'recent_decisions' in data else []
                    c.save_arrays(dest/'scores.npz', uid=np.asarray(_uids(data)), head=np.asarray(data['logits']), corrected=corrected)
                    c.save_arrays(dest/'decisions.npz', uid=np.asarray(_uids(data)), head=before, full=after)
                    _write_trace(dest/'trace.jsonl.gz', data['rows'], trace, np.asarray(data['logits'], dtype=np.float64), corrected)
                    c.write(dest/'reports.json', json_value(result))
                    c.write(dest/'bank.json', json_value(dict(identity=identity, roster=bank.roster(),
                        preparation_receipt=assets.get('preparation_receipt'),
                        empty_reference_exact_fallback=bool(np.array_equal(
                            core.apply_correction(data['logits'], np.zeros(len(data['rows'])), scales, selected_lambda),
                            np.asarray(data['logits'], dtype=np.float64))))))
                    cache[identity] = (policy, result, checks)
                # Controls have policy-specific rosters even when main scores reuse.
                bank = bank_from(assets, bundle['normalizer'])
                control_data = dict(data, wrong_reference_controls=assets.get('wrong_reference_controls', []))
                controls = wrong_reference_controls(control_data, bank, geometry, scales, selected_lambda, cuts, ensemble_cut, pool)
                c.write(dest/'wrong_reference_controls.json', json_value(controls))
                c.write(dest/'gate.json', evaluation.pool_gate(result)); c.seal(dest); c.verify(dest)
                policy_results.setdefault(policy, {})[pool] = result
                policy_checks.setdefault(policy, []).extend(checks)
        decisions = {policy: evaluation.complete_system_gate(results, source_checks+policy_checks.get(policy, []))
                     for policy, results in policy_results.items()}
        receipt = dict(status='COMPLETE', scientific_decisions=decisions, selected_lambda=selected_lambda,
                       synthetic_only=bundle['synthetic_only'], optimizer_updates=0, retries=0,
                       missing_bank_policies={p:[s for s in POLICIES if s not in d['banks']] for p,d in bundle['targets'].items()},
                       independent_confirmation='NOT_RUN', automatic_model_selection=False)
        c.write(out/'result.json', json_value(receipt)); c.seal(out); c.verify(out)
        c.write(out/'status.json', dict(status='COMPLETE', stage='COMPLETE', result_sha256=c.sha(out/'result.json'),
                                       synthetic_only=bundle['synthetic_only'], optimizer_updates=0, retries=0), replace=True)
        return receipt
    except Exception as exc:
        c.write(out/'status.json', dict(status='STOPPED_NO_RETRY', stage=phase,
                                       error=str(exc), synthetic_only=bundle['synthetic_only'], retries=0), replace=True)
        raise


def _pinned(root, spec):
    path = (root/spec['path']).resolve()
    c.require(path.is_relative_to(root.resolve()), 'BUNDLE_PATH_ESCAPE')
    return c.pin(path, spec['sha256'])


def load_bundle(path):
    """Portable, explicit UID-joined NPZ inputs for synthetic checks only."""
    path = Path(path).resolve(); root = path.parent; manifest = c.read(path)
    c.require(manifest.get('synthetic_only') is True,
              'PORTABLE_PRODUCTION_NOT_SUPPORTED_USE_VERIFIED_QUERY_TAIL_ADAPTER')
    def asset(spec, scored=False):
        metadata = _pinned(root, spec['metadata'])
        if metadata.suffix == '.gz':
            rows = list(c.rows(metadata))
        else:
            rows = c.read(metadata)
        with np.load(_pinned(root, spec['arrays']), allow_pickle=False) as f:
            keys = ('e3', 'q14', 'logits') if scored else ('e3', 'q14')
            result = {k: f[k].copy() for k in keys}
            result.update(rows=rows, feature_uids=f['uid'].tolist(), q_uids=f['uid'].tolist())
            if 'recent_decisions' in f:
                result['recent_decisions'] = f['recent_decisions'].copy()
        if 'preparation_receipt' in spec:
            result['preparation_receipt'] = c.read(_pinned(root, spec['preparation_receipt']))
        return result
    with np.load(_pinned(root, manifest['normalizer']), allow_pickle=False) as f:
        normalizer = f['mean'].copy(), f['scale'].copy()
    bundle = {k: manifest[k] for k in ('schema', 'synthetic_only', 'input_version', 'protocol_sha256', 'head_family', 'cuts', 'ensemble_cut')}
    bundle.update(normalizer=normalizer, source_fit=asset(manifest['source_fit'], True),
                  source_cal=asset(manifest['source_cal'], True), source_references=asset(manifest['source_references']),
                  targets={}, provenance=dict(manifest.get('provenance', {}), bundle_sha256=c.sha(path), protected_paths=[str(root)]))
    for pool, spec in manifest['targets'].items():
        data = asset(spec, True)
        data['banks'] = {policy: dict(asset(bank), wrong_reference_controls=bank.get('wrong_reference_controls', []))
                         for policy, bank in spec['banks'].items()}
        bundle['targets'][pool] = data
    return bundle


def attach_reference_banks(bundle, manifest_path):
    """Load policy-specific outputs of reference.encode_selected with fixed pins."""
    manifest_path = Path(manifest_path).resolve()
    spec = c.read(manifest_path)
    c.require(set(spec) == {'pools'}, 'BANK_MANIFEST_SCHEMA')
    for pool, policies in spec['pools'].items():
        c.require(pool in bundle['targets'], 'BANK_TARGET_NOT_LOADED')
        for policy, location in policies.items():
            c.require(policy in ('B0', 'B1', 'B2') and policy not in bundle['targets'][pool]['banks'], 'BANK_POLICY_DUPLICATE')
            root = (manifest_path.parent/location['path']).resolve()
            receipt = c.read(c.pin(root/'receipt.json', location['receipt_sha256']))
            c.require(receipt.get('policy') == policy and receipt.get('input_version') == INPUT_VERSION and
                      receipt.get('synthetic_only') == bundle['synthetic_only'], 'BANK_PRODUCER_IDENTITY')
            if not bundle['synthetic_only']:
                c.require(receipt.get('real_recent_features') is True and receipt.get('status') == 'COMPLETE' and
                          receipt.get('normalizer_sha256') == bundle['provenance']['normalizer_sha256'], 'BANK_FEATURE_NORMALIZER_IDENTITY')
            rows = list(c.rows(c.pin(root/'references.jsonl.gz', receipt['metadata_sha256'])))
            c.pin(root/'tensor_receipts.jsonl.gz', receipt['tensor_receipts_sha256'])
            c.pin(root/'environment.json', receipt['environment_sha256'])
            with np.load(c.pin(root/'bank.npz', receipt['bank_npz_sha256']), allow_pickle=False) as f:
                bank = dict(rows=rows, e3=f['e3'].copy(), q14=f['q14'].copy(),
                            feature_uids=f['uid'].tolist(), q_uids=f['uid'].tolist(), preparation_receipt=receipt,
                            wrong_reference_controls=location.get('wrong_reference_controls', []))
            _joined(bank)
            c.require(len(rows) == receipt['rows'], 'BANK_ROW_COUNT')
            bundle['targets'][pool]['banks'][policy] = bank
            bundle['provenance'].setdefault('protected_paths', []).append(str(root))
    bundle['provenance']['bank_manifest_sha256'] = c.sha(manifest_path)
    return bundle


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--protocol', type=Path, default=Path(__file__).resolve().parents[2]/'runs/onboarding_materials_and_protocol_20261015/protocol.json')
    args = parser.parse_args(argv)
    result = run_development(load_bundle(args.bundle), args.output, args.protocol)
    print(json.dumps(json_value(result), ensure_ascii=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
