"""Frozen saved-score dense-reference matrix; no model/FIT/encoding entrypoint.

Run after successful supplemental encoding and dense source CAL. Every input is
SHA-bound, source operating points are consumed unchanged, support is evaluated
once per reference arm and reused by all four epsilon values. A scientific FAIL
is data and never interrupts registered cells. Identity/numerical errors stop.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
for candidate in (PACKAGE / 'vendor/encoding_v2/repo/ood', PACKAGE.parents[1] / 'repo/ood'):
    if candidate.is_dir():
        sys.path.insert(0, str(candidate))
        break
import constrained_onboarding_core_v3 as core
import onboarding_budget_v1 as budget
from indexed_features_v1 import IndexedMatrix
import metrics

SCHEMA = 'dense-reference-ab-stage-input-v1'
STAGE_SCOPE = 'AB_DENSE_STAGE_PENDING_THIRD_POOL'
AB_POOLS = ('CIC_DEV', 'UNSW_DEV')
THIRD_POOL = 'CIC_THREE_DEVICE_REGRESSION_CONSUMED'
EPSILONS = (0., .05, .1, .2)
ARMS = ('R-B2', 'R-DENSE', 'R-DENSE-WRONG')
require = core.require


def sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def jsonable(value):
    if isinstance(value, np.ndarray):
        return jsonable(value.tolist())
    if isinstance(value, np.generic):
        return jsonable(value.item())
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [jsonable(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(jsonable(value), sort_keys=True, indent=2,
                                    ensure_ascii=False, allow_nan=False)+'\n', encoding='utf-8')
    temporary.replace(path)


class Inputs:
    def __init__(self, root, derived_runtime_roots=()):
        self.root = Path(root).resolve()
        self.derived_runtime_roots = tuple(Path(p).resolve() for p in derived_runtime_roots)
        self.pins = {}

    def pin(self, spec):
        require(isinstance(spec, dict) and isinstance(spec.get('path'), str) and
                isinstance(spec.get('sha256'), str) and len(spec['sha256']) == 64, 'PIN_SPEC')
        path = (self.root / spec['path']).resolve()
        allowed = path.is_relative_to(self.root)
        if spec.get('derived_runtime') is True:
            allowed = any(path.is_relative_to(p) for p in self.derived_runtime_roots)
        require(allowed, 'INPUT_OUTSIDE_ROOT')
        require(path.is_file(), 'MISSING_INPUT:' + str(path))
        if path not in self.pins:
            require(sha(path) == spec['sha256'], 'INPUT_SHA256:' + str(path))
            self.pins[path] = spec['sha256']
        else:
            require(self.pins[path] == spec['sha256'], 'CONTRADICTORY_INPUT_PIN')
        return path

    def json(self, spec):
        return read(self.pin(spec))

    def array(self, spec):
        path = self.pin(spec)
        if path.suffix == '.npz':
            require(isinstance(spec.get('key'), str), 'NPZ_ARRAY_KEY')
            with np.load(path, allow_pickle=False) as saved:
                arr = saved[spec['key']].copy()
        else:
            arr = np.load(path, mmap_mode='r', allow_pickle=False)
        if 'indices' in spec:
            indices = self.array(spec['indices'])
            require(indices.ndim == 1 and indices.dtype.kind in 'iu', 'ROW_INDEX_SCHEMA')
            arr = IndexedMatrix(arr, indices)
        if 'column_slice' in spec:
            first, last = spec['column_slice']
            require(type(first) is type(last) is int and 0 <= first < last <= arr.shape[1], 'COLUMN_SLICE')
            arr = IndexedMatrix(arr, np.arange(len(arr)), slice(first, last))
        return arr

    def rows(self, spec):
        path = self.pin(spec)
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as stream:
            rows = [json.loads(line) for line in stream if line.strip()]
        require(rows and len({r['uid'] for r in rows}) == len(rows), 'ROWS_UID_IDENTITY')
        return rows

    def dataset(self, spec, *, logits=False):
        rows = self.rows(spec['rows'])
        uids = [r['uid'] for r in rows]
        expected = core._uid_hash(uids)
        features = {}
        for field in ('e3', 'q14'):
            arr = self.array(spec[field])
            if self.pin(spec[field]).suffix == '.npz':
                with np.load(self.pin(spec[field]), allow_pickle=False) as saved:
                    uid_key = spec[field].get('uid_key', 'uid')
                    require(uid_key in saved.files and saved[uid_key].tolist() == uids,
                            'FEATURE_NPZ_UID_JOIN:' + field)
            uid_key = 'feature_uids' if field == 'e3' else 'q_uids'
            hash_key = 'feature_uid_sha256' if field == 'e3' else 'q_uid_sha256'
            if uid_key in spec:
                joined = self.json(spec[uid_key])
                require(joined == uids, 'ORDERED_FEATURE_UID_JOIN:' + field)
            else:
                require(spec.get(hash_key) == expected, 'ORDERED_FEATURE_UID_PIN:' + field)
            features[field] = arr
        core._joined(rows, features['e3'], features['q14'], uids, uids)
        data = dict(rows=rows, feature_uids=uids, q_uids=uids, **features)
        if logits:
            pin, keys = spec['logits'], spec['logits'].get('keys')
            with np.load(self.pin(pin), allow_pickle=False) as saved:
                require(saved[pin.get('uid_key', 'uid')].tolist() == uids, 'SAVED_LOGIT_UID_JOIN')
                if 'key' in pin:
                    x = core._logits(saved[pin['key']], len(rows), core.SEEDS)
                else:
                    require(isinstance(keys, dict) and set(keys) == set(metrics.SUFFIXES), 'SAVED_LOGIT_KEYS')
                    x = core._logits(np.column_stack([saved[keys[str(s)]] for s in core.SEEDS]), len(rows), core.SEEDS)
                    actual = np.asarray(saved[keys['ensemble']])
                    calculated = core.ordered_ensemble(x)
                    require(actual.dtype == calculated.dtype and actual.shape == calculated.shape and
                            actual.tobytes() == calculated.tobytes(), 'SAVED_ENSEMBLE_BITWISE_JOIN')
            data['logits'] = x
        return data

    def immutable(self):
        for path, checksum in self.pins.items():
            require(sha(path) == checksum, 'INPUT_CHANGED_DURING_EVALUATION:' + str(path))


def decisions(logits, cuts, ensemble_cut):
    x = core._logits(logits, len(logits), core.SEEDS)
    return np.column_stack((x > core._cuts(cuts), core.ordered_ensemble(x) > ensemble_cut))


def validate_stage_scope(manifest):
    require(manifest.get('evaluation_scope') == STAGE_SCOPE, 'AB_STAGE_SCOPE_REQUIRED')
    require(manifest.get('full_matrix_ready') is False and
            manifest.get('original_registered_matrix_complete') is False,
            'FULL_REGISTERED_MATRIX_MUST_REMAIN_INCOMPLETE')
    pools = manifest.get('pools', [])
    require(len(pools) == 2 and [p.get('pool_id') for p in pools] == list(AB_POOLS) and
            all(p.get('mode') == 'DENSE_MATRIX' for p in pools), 'EXACT_AB_STAGE_POOL_REGISTRY')
    deferred = manifest.get('third_pool_deferred', {})
    require(deferred.get('pool_id') == THIRD_POOL and
            deferred.get('status') == 'DEFERRED_MISSING_FROZEN_BASE_B2' and
            deferred.get('original_registered_matrix_complete') is False,
            'THIRD_POOL_DEFERRED_STATUS_REQUIRED')


def check_authorization(manifest, manifest_sha, source_sha, authorization, synthetic):
    validate_stage_scope(manifest)
    if synthetic:
        require(manifest.get('synthetic_only') is True and manifest.get('synthetic_fixture_kind') ==
                'AB_STAGE_UNIT_TEST_ONLY', 'SYNTHETIC_CANNOT_LOAD_REAL_TARGETS')
        return
    require(manifest.get('synthetic_only') is False, 'REAL_MANIFEST_REQUIRED')
    require(isinstance(authorization, dict) and authorization.get('schema') ==
            'dense-reference-ab-stage-authorization-v1' and authorization.get('status') == 'AUTHORIZED' and
            authorization.get('scope') == STAGE_SCOPE and
            authorization.get('protocol_amendment_confirmed') is True and
            authorization.get('evaluated_pools') == list(AB_POOLS) and
            authorization.get('deferred_pool') == THIRD_POOL and
            authorization.get('allow_target_evaluation') is True and
            authorization.get('manifest_sha256') == manifest_sha and
            authorization.get('source_cal_result_sha256') == source_sha and
            bool(authorization.get('evidence')), 'AB_STAGE_TARGET_AUTHORIZATION_REQUIRED')


def source_workpoints(result, preparations):
    require(result.get('status') == 'SOURCE_CAL_COMPLETE' and result.get('no_AB_loaded') is True and
            result.get('no_model_forward') is True, 'SOURCE_CAL_RESULT_REQUIRED')
    answer = {}
    for arm in ('R-B2', 'R-DENSE'):
        saved = result['arms'][arm]['selections']
        require(set(saved) == {str(e) for e in EPSILONS}, 'SOURCE_EPSILON_GRID')
        preparation = preparations[arm]
        selections = {}
        for e in EPSILONS:
            point = saved[str(e)]
            # Read-only reproducibility check; the saved source point is the
            # only consumed point. No target values enter this function.
            require(point == budget.select_budget_lambda(preparation, e), 'SOURCE_WORKPOINT_REPLAY_MISMATCH')
            require(point.get('no_target_scores_used') is True and point.get('epsilon_pp') == e,
                    'SOURCE_WORKPOINT_SCOPE')
            lam = point['selected_lambda']
            require(lam is None or lam in core.LAMBDAS, 'SOURCE_UNREGISTERED_LAMBDA')
            selections[str(e)] = point
        answer[arm] = selections
    answer['R-DENSE-WRONG'] = answer['R-DENSE']
    return answer


def bank_from(data, normalizer):
    return core.ReferenceBank(data['rows'], data['e3'], data['q14'], normalizer,
                              feature_uids=data['feature_uids'], q_uids=data['q_uids'],
                              allow_prebank_history=True,
                              allowed_partitions={'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 'HOLDOUT'})


def own_trace(bank, data, geometry, override=None):
    return bank.own(data['rows'], data['e3'], data['q14'], geometry,
                    feature_uids=data['feature_uids'], q_uids=data['q_uids'], override=override)


def wrong_override(bank, rows, wrong_groups):
    override, statuses = {}, []
    by_group = {}
    for entry in wrong_groups:
        device = entry.get('device_id', entry.get('device'))
        key = (device, int(entry['protocol']))
        require(key not in by_group, 'DUPLICATE_WRONG_GROUP')
        by_group[key] = entry
    for row in rows:
        device, protocol, partition = row['device'], row['protocol'], row['partition']
        key = (partition, device, protocol)
        if key in override:
            continue
        entry = by_group.get((device, protocol))
        if entry is None and key not in bank.groups:
            override[key] = []
            statuses.append(dict(device=device, protocol=protocol, status='NOT_EVALUABLE', reason='NO_OWN_DENSE_GROUP'))
            continue
        require(entry is not None, 'FROZEN_WRONG_PLAN_MISSING_GROUP')
        if entry['status'] not in ('READY', 'EVALUABLE'):
            require(entry['status'] in ('NOT_EVALUABLE', 'NO_DONOR'), 'WRONG_PLAN_STATUS')
            override[key] = []
            statuses.append(dict(device=device, protocol=protocol, status='NOT_EVALUABLE', reason=entry.get('reason', 'NO_DONOR')))
            continue
        donor = entry.get('donor_device_id', entry.get('donor_device'))
        uids = entry['selected_uids']
        require(donor != device and uids and len(set(uids)) == len(uids), 'WRONG_DONOR_IDENTITY')
        require(entry.get('uid_sha256') == core._uid_hash(uids), 'WRONG_UID_PLAN_HASH')
        require(all(u in bank.by_uid for u in uids), 'WRONG_UID_NOT_IN_FROZEN_DENSE_BANK')
        refs = [bank.rows[bank.by_uid[u]] for u in uids]
        require(all(r['device'] == donor and r['partition'] == partition and r['protocol'] == protocol for r in refs),
                'WRONG_OWNER_PROTOCOL_PARTITION')
        own = bank.groups.get(key, [])
        require(own, 'WRONG_TARGET_DENSE_GROUP_MISSING')
        own_rows = [bank.rows[i] for i in own]
        require({r['reference_end'] for r in refs} == {r['reference_end'] for r in own_rows}, 'WRONG_WINDOW_END')
        require({r.get('observation_t0') for r in refs} == {r.get('observation_t0') for r in own_rows}, 'WRONG_WINDOW_START')
        require(len(uids) == min(len(own), entry['donor_n']) and
                entry.get('target_n', entry.get('target_positions')) == len(own), 'WRONG_DENSITY_BUDGET')
        override[key] = uids
        statuses.append(dict(device=device, protocol=protocol, donor_device=donor, status='READY',
                             target_positions=len(own), donor_positions=len(uids), density_ratio=len(uids)/len(own),
                             target_components=len({r['component_id'] for r in own_rows}),
                             donor_components=len({r['component_id'] for r in refs})))
    return override, statuses


def _write_trace(path, rows, trace):
    with gzip.open(path, 'wt', encoding='utf-8', newline='\n') as stream:
        for i, row in enumerate(rows):
            item = dict(uid=row['uid'])
            for key, value in trace.items():
                if isinstance(value, np.ndarray) and len(value) == len(rows):
                    item[key] = value[i]
            stream.write(json.dumps(jsonable(item), sort_keys=True, allow_nan=False)+'\n')


def evaluate_pool(pool, data, traces, points, cuts, ensemble_cut, scales, windows, output,
                  progress=None):
    """Pure saved-input evaluation; every arm/epsilon runs despite scientific FAIL."""
    rows, logits = data['rows'], data['logits']
    metrics.validate_full_weights(rows, pool)
    before = decisions(logits, cuts, ensemble_cut)
    full_weights = metrics.original_weights(rows)
    views = {'full': (np.arange(len(rows)), rows, full_weights)}
    if windows:
        ix = np.flatnonzero(metrics.post_window_mask(rows, windows))
        rr = [rows[i] for i in ix]
        views['post_window_primary'] = (ix, rr, metrics.hierarchical_weights(rr, pool))
    else:
        require(pool == 'CIC_THREE_DEVICE_REGRESSION_CONSUMED', 'PRIMARY_WINDOW_REQUIRED')
    results, corrected_cache, corrected_score_cache = {}, {}, {}
    for arm in ARMS:
        if arm not in traces:
            results[arm] = dict(status='NOT_APPLICABLE', reason='NO_FROZEN_THIRD_POOL_WINDOW')
            continue
        results[arm] = {}
        trace = traces[arm]
        for epsilon in EPSILONS:
            point = points[arm][str(epsilon)]
            lam = point['selected_lambda']
            if lam is None:
                results[arm][str(epsilon)] = dict(status='NOT_EVALUABLE', reason='NO_FEASIBLE_SOURCE_WORKPOINT')
                continue
            cache_key = (arm, lam)
            if cache_key not in corrected_cache:
                changed = core.apply_correction(logits, trace['support'], scales, lam)
                require(np.all(changed <= logits) and np.array_equal(changed[trace['support'] == 0],
                        logits[trace['support'] == 0]), 'CORRECTION_NOOP_OR_MONOTONICITY')
                corrected_cache[cache_key] = decisions(changed, cuts, ensemble_cut)
                corrected_score_cache[cache_key] = changed
            after = corrected_cache[cache_key]
            entry = dict(status='EVALUATED', selected_lambda=lam, source_acceptance=point['selected_budget_acceptance'],
                         shared_dense_workpoint=(arm == 'R-DENSE-WRONG'), views={})
            for name, (ix, rr, weights) in views.items():
                suffixes = {}
                for j, suffix in enumerate(metrics.SUFFIXES):
                    report = metrics.report(rr, before[ix, j], after[ix, j], weights,
                                            trace['eligible'][ix], trace['support'][ix])
                    report['gate'] = metrics.target_gate(report, epsilon)
                    suffixes[suffix] = report
                entry['views'][name] = dict(rows=len(rr),
                    retained_uid_sha256=core._uid_hash([r['uid'] for r in rr]),
                    float64_weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(),
                    retained_original_class_weight_mass={str(label): math.fsum(full_weights[ix][
                        np.asarray([r['label'] == label for r in rr], dtype=bool)]) for label in (0, 1)},
                    weight_rule='original saved denominators' if name == 'full' else
                    'original pool hierarchy rebuilt within each retained class and nonempty branch',
                    reports=suffixes)
            results[arm][str(epsilon)] = entry
            np.savez_compressed(output / (arm + '_epsilon_' + str(epsilon).replace('.', 'p') + '_decisions.npz'),
                                uid=np.asarray([r['uid'] for r in rows]), base=before, corrected=after,
                                raw_logits=logits, corrected_logits=corrected_score_cache[cache_key],
                                raw_ensemble_logits=core.ordered_ensemble(logits),
                                corrected_ensemble_logits=core.ordered_ensemble(corrected_score_cache[cache_key]),
                                seeds=np.asarray(core.SEEDS, dtype=np.int64),
                                cuts=np.asarray(cuts, dtype=np.float64),
                                ensemble_cut=np.asarray(ensemble_cut, dtype=np.float64),
                                selected_lambda=np.asarray(lam, dtype=np.float64),
                                support=np.asarray(trace['support']),
                                eligible=np.asarray(trace['eligible'], dtype=bool))
            if progress:
                progress(arm, epsilon)
    comparisons = {}
    if 'R-DENSE' in traces and 'R-DENSE-WRONG' in traces:
        for epsilon in EPSILONS:
            lam = points['R-DENSE'][str(epsilon)]['selected_lambda']
            if lam is None:
                comparisons[str(epsilon)] = dict(status='NOT_EVALUABLE', reason='NO_SOURCE_WORKPOINT')
                continue
            own, wrong = corrected_cache[('R-DENSE', lam)], corrected_cache[('R-DENSE-WRONG', lam)]
            comparisons[str(epsilon)] = {}
            for name, (ix, rr, weights) in views.items():
                comparisons[str(epsilon)][name] = {suffix: metrics.paired_own_wrong(rr, own[ix, j], wrong[ix, j], weights,
                        traces['R-DENSE']['eligible'][ix], traces['R-DENSE-WRONG']['eligible'][ix])
                    for j, suffix in enumerate(metrics.SUFFIXES)}
    claims = {}
    if 'R-DENSE' in traces:
        for epsilon in EPSILONS:
            e = str(epsilon)
            claims[e] = {}
            dense_entry, b2_entry = results['R-DENSE'][e], results['R-B2'][e]
            if dense_entry['status'] != 'EVALUATED' or b2_entry['status'] != 'EVALUATED':
                claims[e] = dict(status='NOT_EVALUABLE')
                continue
            for view in dense_entry['views']:
                claims[e][view] = {}
                for suffix in metrics.SUFFIXES:
                    own_rate = dense_entry['views'][view]['reports'][suffix]['corrected']['normal']['weighted_rate']
                    b2_rate = b2_entry['views'][view]['reports'][suffix]['corrected']['normal']['weighted_rate']
                    paired = comparisons[e][view][suffix]
                    po = paired['own']['normal']['weighted_rate']
                    pw = paired['wrong']['normal']['weighted_rate']
                    claims[e][view][suffix] = dict(
                        dense_reduces_fpr_vs_b2=None if own_rate is None or b2_rate is None else own_rate < b2_rate,
                        own_better_than_wrong_on_common_eligible=None if po is None or pw is None else po < pw,
                        paired_normal_weight_coverage=paired['coverage']['normal']['weight_coverage'],
                        target_attacks_within_budget=dense_entry['views'][view]['reports'][suffix]['gate']['attack']['status'])
    evaluated = sum(1 for arm in results.values() if isinstance(arm, dict)
                    for item in arm.values() if isinstance(item, dict) and item.get('status') == 'EVALUATED')
    unavailable = sum(1 for arm in results.values() if isinstance(arm, dict)
                      for item in arm.values() if isinstance(item, dict) and item.get('status') == 'NOT_EVALUABLE')
    return dict(pool=pool, query_rows=len(rows), arms=results, own_wrong_paired=comparisons,
                registered_claim_conditions=claims,
                completeness=dict(expected_arm_epsilon_cells=len(traces)*len(EPSILONS),
                                  evaluated_arm_epsilon_cells=evaluated,
                                  not_evaluable_arm_epsilon_cells=unavailable,
                                  expected_suffixes=list(metrics.SUFFIXES), views=list(views)),
                primary_view='post_window_primary' if windows else 'NOT_APPLICABLE_NO_FROZEN_WINDOW',
                source_selected_only=True, parameters_refit=False, evidence='CONSUMED_DEVELOPMENT_ONLY')


def run(args):
    manifest_path = Path(args.manifest).resolve()
    manifest_sha = sha(manifest_path)
    manifest = read(manifest_path)
    require(manifest.get('schema') == SCHEMA, 'MATRIX_INPUT_SCHEMA')
    source_path = Path(args.source_cal_result).resolve()
    source_sha = sha(source_path)
    authorization = read(args.authorization) if args.authorization else None
    # Gate occurs before target data/scores are opened.
    check_authorization(manifest, manifest_sha, source_sha, authorization, args.synthetic_dry_run)
    if not args.synthetic_dry_run:
        require(not any(p.get('mode', '').startswith('BLOCKED') for p in manifest.get('pools', [])),
                'MATRIX_FROZEN_THIRD_POOL_INPUTS_MISSING')
        require(manifest.get('stage_matrix_ready') is True and manifest.get('supplement_encoding_complete') is True and
                manifest.get('dense_source_cal_complete') is True, 'AB_STAGE_MATERIALIZATION_REQUIRED')
    output = Path(args.output).resolve()
    require(not output.exists(), 'OUTPUT_ALREADY_EXISTS_NEVER_OVERWRITE')
    inputs = Inputs(args.root, manifest.get('derived_runtime_roots', ()))
    require(source_path == inputs.pin(manifest['source_cal_result']), 'SOURCE_RESULT_MANIFEST_BINDING')
    source = read(source_path)
    preparations = {arm: inputs.json(manifest['source_preparations'][arm]) for arm in ('R-B2', 'R-DENSE')}
    points = source_workpoints(source, preparations)
    calibration = manifest['calibration']
    cuts = inputs.json(calibration['cuts'])
    scales = inputs.json(calibration['scales'])
    geometry = inputs.json(calibration['geometry'])
    require(cuts.get('seeds') == list(core.SEEDS) and cuts.get('moved') is False, 'FROZEN_CUTS_REQUIRED')
    cut, scale = core._cuts(cuts['cuts']), core._scales(scales)
    ensemble_cut = float(cuts['ensemble_cut'])
    require(math.isfinite(ensemble_cut), 'ENSEMBLE_CUT_FINITE')
    with np.load(inputs.pin(calibration['normalizer']), allow_pickle=False) as saved:
        normalizer = core._normalizer((saved['mean'], saved['scale']))
    validate_stage_scope(manifest)
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write(output/'status.json', dict(status='RUNNING', stage='IDENTITY_VALIDATED', manifest_sha256=manifest_sha))
    try:
        pools, blocked = {}, [THIRD_POOL]
        for pool_spec in manifest['pools']:
            pool, mode = pool_spec['pool_id'], pool_spec['mode']
            if mode == 'BLOCKED_MISSING_FROZEN_BASE_B2':
                require(pool == 'CIC_THREE_DEVICE_REGRESSION_CONSUMED', 'ONLY_THIRD_POOL_MAY_BE_BLOCKED')
                pools[pool] = dict(status=mode, reason=pool_spec.get('reason'), arms={})
                blocked.append(pool)
                continue
            require(mode in ('DENSE_MATRIX', 'B2_REGRESSION_ONLY'), 'POOL_MODE')
            if args.synthetic_dry_run:
                # Synthetic mode may inspect fixture metadata only until all
                # query/reference rows attest their synthetic identity.
                for field in ('query', 'b2_bank', 'dense_bank'):
                    fixture_rows = inputs.rows(pool_spec[field]['rows'])
                    require(len(fixture_rows) <= 256 and all(r.get('synthetic_fixture') is True and
                            r['uid'].startswith('SYNTHETIC|') for r in fixture_rows),
                            'SYNTHETIC_FIXTURE_METADATA_REQUIRED')
            data = inputs.dataset(pool_spec['query'], logits=True)
            if args.synthetic_dry_run:
                require(len(data['rows']) <= 256, 'SYNTHETIC_SIZE_BOUND')
            partition = {'CIC_DEV': 'DEV', 'UNSW_DEV': 'EXTERNAL_ARCHIVAL_EVALUATION',
                         'CIC_THREE_DEVICE_REGRESSION_CONSUMED': 'HOLDOUT'}[pool]
            require(all(r['partition'] == partition for r in data['rows']), 'TARGET_PARTITION_SCOPE')
            folder = output/pool
            folder.mkdir()
            traces = {}
            b2 = bank_from(inputs.dataset(pool_spec['b2_bank']), normalizer)
            write(output/'status.json', dict(status='RUNNING', stage='SUPPORT_R-B2', pool=pool))
            traces['R-B2'] = own_trace(b2, data, geometry)
            if mode == 'DENSE_MATRIX':
                dense = bank_from(inputs.dataset(pool_spec['dense_bank']), normalizer)
                override, statuses = wrong_override(dense, data['rows'], pool_spec['wrong_groups'])
                write(folder/'WRONG_ROSTER.json', statuses)
                for arm, control in (('R-DENSE', None), ('R-DENSE-WRONG', override)):
                    write(output/'status.json', dict(status='RUNNING', stage='SUPPORT_' + arm, pool=pool))
                    traces[arm] = own_trace(dense, data, geometry, control)
            for arm, trace in traces.items():
                _write_trace(folder/(arm+'_support.jsonl.gz'), data['rows'], trace)
            def progress(arm, epsilon):
                write(output/'status.json', dict(status='RUNNING', stage='METRICS', pool=pool,
                                                arm=arm, epsilon_pp=epsilon))
            pools[pool] = evaluate_pool(pool, data, traces, points, cut, ensemble_cut, scale,
                pool_spec.get('windows'), folder, progress)
            write(folder/'RESULT.json', pools[pool])
        inputs.immutable()
        required_gates = []
        for pool in pools.values():
            arms = pool.get('arms', {})
            if not arms:
                continue
            main_arm = 'R-DENSE' if 'R-DENSE' in arms and '0.1' in arms['R-DENSE'] else 'R-B2'
            entry = arms[main_arm]['0.1']
            if entry.get('status') != 'EVALUATED':
                required_gates.append('NOT_EVALUABLE')
                continue
            view = entry['views'].get('post_window_primary', entry['views']['full'])
            required_gates.extend(r['gate']['status'] for r in view['reports'].values())
            if entry.get('source_acceptance', {}).get('passes') is False:
                required_gates.append('FAIL')
        stage_scientific = ('FAIL' if 'FAIL' in required_gates else 'NOT_EVALUABLE' if
                            'NOT_EVALUABLE' in required_gates or not required_gates else 'PASS')
        pools[THIRD_POOL] = dict(status='DEFERRED_MISSING_FROZEN_BASE_B2', arms={}, evaluated=False)
        result = dict(schema='dense-reference-ab-stage-result-v1',
            status='AB_STAGE_COMPLETE_THIRD_POOL_PENDING', technical_status='COMPLETE',
            evaluation_scope=STAGE_SCOPE, stage_scientific_status=stage_scientific,
            original_registered_matrix_complete=False, full_matrix_ready=False,
            original_registered_matrix_scientific_status='NOT_EVALUATED_MISSING_THIRD_POOL',
            third_pool_deferred=manifest['third_pool_deferred'],
            scientific_status='FAIL' if 'FAIL' in required_gates else 'NOT_EVALUABLE' if blocked or
                'NOT_EVALUABLE' in required_gates or not required_gates else 'PASS',
            missing_pools=blocked, pools=pools, manifest_sha256=manifest_sha,
            source_cal_result_sha256=source_sha, completed_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-started, synthetic_only=args.synthetic_dry_run,
            model_forward_calls=0, training_updates=0, geometry_scale_cut_fit_calls=0,
            source_workpoints=points, main_epsilon_pp=.1,
            scientific_status_scope='A/B stage only: R-DENSE main epsilon post-window all four suffixes. Original three-pool matrix remains incomplete. WRONG is a negative control, not a primary target gate.',
            score_trace_persisted=True, threshold_refit_calls=0, recall99_threshold_selection=False,
            authorization=authorization,
            scientific_fail_continues=True, automatic_promotion=False, retries=0)
        write(output/'RESULT.json', result)
        write(output/'INPUT_SEAL.json', {str(p): s for p, s in inputs.pins.items()})
        files = sorted(p for p in output.rglob('*') if p.is_file() and p.name not in ('status.json', 'SHA256SUMS'))
        (output/'SHA256SUMS').write_text(''.join(sha(p)+'  '+p.relative_to(output).as_posix()+'\n' for p in files), encoding='utf-8')
        write(output/'status.json', dict(status=result['status'], stage='MATRIX_TERMINAL',
              technical_status='COMPLETE', scientific_status=result['scientific_status'],
              evaluation_scope=STAGE_SCOPE, stage_scientific_status=stage_scientific,
              original_registered_matrix_complete=False, missing_pools=blocked,
              result_sha256=sha(output/'RESULT.json'), terminal=True, retries=0))
        return result
    except BaseException as exc:
        write(output/'status.json', dict(status='EXCEPTION_STOP', terminal=True, error_type=type(exc).__name__,
                                        error=str(exc), retries=0, preserve_scene=True))
        raise


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True, help='Relocatable input asset root; every asset path must stay inside.')
    p.add_argument('--manifest', required=True, help='Frozen SHA-bound dense-reference-ab-stage-input-v1 JSON.')
    p.add_argument('--source-cal-result', required=True, help='Existing SOURCE_CAL_COMPLETE RESULT.json; no source fitting here.')
    p.add_argument('--authorization', help='Manifest/result-bound user authorization JSON, required for real evaluation.')
    p.add_argument('--synthetic-dry-run', action='store_true', help='Only synthetic_only=true manifests, <=256 rows per pool.')
    p.add_argument('--output', required=True, help='New absent output directory; never overwrite or resume partial attempts.')
    return p


if __name__ == '__main__':
    run(parser().parse_args())
