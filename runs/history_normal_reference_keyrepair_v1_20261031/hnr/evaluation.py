"""Single C1 evaluation: historical DEV gate, then one saved-input A/B terminal.

No recalibration, target encoding, selection, retries, or fallback lives here.
The only target intervention is own-bank support for the four named devices.
"""
from collections import defaultdict
import hashlib
import math
from pathlib import Path

import numpy as np

from .common import ROOT, TARGETS, HEIM, LAMBDA, require, write, write_rows, digest, sha
from .assets import helpers, joined, load_assets
import constrained_onboarding_core_v3 as core

SUFFIXES = ('27', '127', '227', 'ensemble')
POOLS = ('CIC_DEV', 'UNSW_DEV')
PRIMARY = 'post_window_primary'
PROTECTION_SCHEMA = 'history-normal-reference-protection-v1'
PROTECTION_GROUP_FIELDS = {'device': ['device'], 'attack_type': ['activity'],
                           'annotation': ['annotation_id']}


def _update(runtime, stage, **values):
    if runtime is not None:
        runtime.update(stage, **values)


def decisions(logits, frozen):
    x = core._logits(logits, len(logits), core.SEEDS)
    cuts = frozen['cuts']
    return np.column_stack((x > core._cuts(cuts['cuts']),
                            core.ordered_ensemble(x) > float(cuts['ensemble_cut'])))


def _subset(data, ix):
    ix = np.asarray(ix, dtype=np.int64)
    values = joined([data['rows'][int(i)] for i in ix], data['e3'][ix], data['q14'][ix])
    if 'logits' in data:
        values['logits'] = data['logits'][ix]
    return values


def _actual_pairs(bank, rows):
    """Count the exact row-reference pairs the frozen core will calculate.

    Time/frame-ineligible rows and groups with fewer than two legal components
    never enter its distance loop. dz/dq/joint are one shared pair population.
    """
    total = 0
    for row in rows:
        key = row['partition'], row['device'], row['protocol']
        indices = bank.groups.get(key, [])
        if not indices or not bank.ends[key[:2]] < row['timestamp']:
            continue
        end = bank.frame_ends.get(key[:2] + (row['capture_id'],))
        if end is not None and row['frame'] <= end:
            continue
        legal = [j for j in indices if bank.rows[j]['capture_id'] != row['capture_id']
                 or bank.rows[j]['frame'] < row['frame']]
        if len({bank.rows[j]['component_id'] for j in legal}) >= 2:
            total += len(legal)
    return total


def support_once(bank, data, geometry, runtime=None, stage='SUPPORT', chunk=128):
    """Bound distance calls with progress and one count, reused by all heads/views."""
    n = len(data['rows'])
    result = dict(support=np.zeros(n, dtype=np.float64), eligible=np.zeros(n, dtype=bool))
    pairs = 0
    for start in range(0, n, chunk):
        ix = np.arange(start, min(start + chunk, n))
        part = _subset(data, ix)
        count = _actual_pairs(bank, part['rows'])
        if runtime is not None:
            runtime.pairs(count)
        trace = bank.own(part['rows'], part['e3'], part['q14'], geometry,
                         feature_uids=part['feature_uids'], q_uids=part['q_uids'])
        for field in result:
            result[field][ix] = trace[field]
        pairs += count
        _update(runtime, stage, completed=int(ix[-1]) + 1, total=n, distance_pairs=pairs)
    result['distance_pairs'] = pairs
    return result


def _bank(data, normalizer, *, history_replay=False):
    return core.ReferenceBank(data['rows'], data['e3'], data['q14'], normalizer,
                              feature_uids=data['feature_uids'], q_uids=data['q_uids'],
                              allow_prebank_history=history_replay,
                              allowed_partitions={'DEV', 'EXTERNAL_ARCHIVAL_EVALUATION', 'LEARN'})


def dev_gate(rows, before, after):
    """Pure normal-only gate; pooled FPR is weighted by selected DEV row counts."""
    require(rows and len({r['uid'] for r in rows}) == len(rows), 'EMPTY_OR_DUPLICATE_DEV')
    require(all(r['label'] == 0 and r['use'] != 'REFERENCE' for r in rows), 'DEV_NORMAL_ONLY')
    before, after = np.asarray(before), np.asarray(after)
    require(before.dtype == after.dtype == np.bool_ and before.shape == after.shape == (len(rows),),
            'DEV_DECISION_SHAPE')
    require(not np.any(~before & after), 'DEV_CORRECTION_CANNOT_ADD_ALARMS')
    expected = {item['device'] for item in TARGETS.values()}
    require({r['device'] for r in rows} == expected, 'EXACT_THREE_DEV_DEVICES')
    devices, failures = [], []
    for device in sorted(expected):
        ix = np.asarray([r['device'] == device for r in rows], dtype=bool)
        n, raw, corrected = int(ix.sum()), int(before[ix].sum()), int(after[ix].sum())
        require(0 < n <= 4096, 'DEV_PER_DEVICE_TOTAL_CAP')
        status = 'STOP_DEV_NO_ROOM' if raw == 0 else 'PASS' if corrected < raw else 'STOP_DEV_FAIL'
        if status != 'PASS':
            failures.append(status + ':' + device)
        devices.append(dict(device=device, rows=n, raw_fp=raw, corrected_fp=corrected,
                            raw_fpr=raw / n, corrected_fpr=corrected / n, status=status))
    raw, corrected = int(before.sum()), int(after.sum())
    reduction = (raw - corrected) / raw if raw else None
    if reduction is None or reduction < .5:
        failures.append('POOLED_RELATIVE_FPR_REDUCTION_BELOW_50_PERCENT')
    return dict(schema='history-normal-reference-dev-gate-v1',
                status='STOP_DEV_FAIL' if failures else 'PASS_DEV', devices=devices,
                pooled=dict(rows=len(rows), raw_fp=raw, corrected_fp=corrected,
                            raw_fpr=raw / len(rows), corrected_fpr=corrected / len(rows),
                            relative_fpr_reduction=reduction, weighting='selected DEV row count'),
                failures=failures, no_AB_loaded=True,
                query_uid_sha256=core._uid_hash([r['uid'] for r in rows]))


def evaluate_dev(queries, references, frozen, runtime=None, output=None):
    if output is not None:
        output = Path(output)
        require(not output.exists(), 'DEV_AUDIT_OUTPUT_ALREADY_EXISTS')
        if runtime is not None and hasattr(runtime, 'output'):
            require(output.resolve().is_relative_to(Path(runtime.output).resolve()), 'DEV_AUDIT_OUTSIDE_RUN')
        output.mkdir(parents=True, exist_ok=False)
    require(queries['rows'] and references['rows'], 'EMPTY_HISTORY_ROLE_STOP')
    require(not {r['uid'] for r in queries['rows']} & {r['uid'] for r in references['rows']},
            'HIST_REF_DEV_UID_OVERLAP')
    expected = {(r['partition'], r['device']) for r in TARGETS.values()}
    require({(r['partition'], r['device']) for r in references['rows']} == expected,
            'HIST_DEV_BANK_EXACT_THREE_DEVICES')
    for target in TARGETS.values():
        rr = [r for r in references['rows'] if r['device'] == target['device']]
        qq = [r for r in queries['rows'] if r['device'] == target['device']]
        cutoff = target['reference_end_us'] / 1e6
        require(qq and all(r['reference_end'] == cutoff and r['bank_end_frame'] == target['bank_end_frame']
                           and r['frame'] <= target['bank_end_frame'] for r in rr), 'HIST_DEV_BANK_CUTOFF')
        require(all(r['timestamp'] > cutoff and r['frame'] > target['bank_end_frame'] for r in qq),
                'HIST_DEV_CAUSAL_QUERY')
    bank = _bank(references, frozen['normalizer'])
    trace = support_once(bank, queries, frozen['geometry'], runtime, 'DEV_SUPPORT')
    changed = core.apply_correction(queries['logits'], trace['support'], frozen['scales'], LAMBDA)
    before, after = decisions(queries['logits'], frozen), decisions(changed, frozen)
    result = dev_gate(queries['rows'], before[:, 3], after[:, 3])
    result.update(selected_lambda=LAMBDA, distance_pairs=trace['distance_pairs'],
                  reference_uid_sha256=core._uid_hash([r['uid'] for r in references['rows']]),
                  eligible_rows=int(trace['eligible'].sum()),
                  positive_support_rows=int((trace['support'] > 0).sum()),
                  all_suffixes={s: dict(raw_fp=int(before[:, j].sum()), corrected_fp=int(after[:, j].sum()))
                                for j, s in enumerate(SUFFIXES)})
    if output is not None:
        ids = [r['uid'] for r in queries['rows']]
        arrays = output / 'DEV_DECISIONS.npz'
        metadata = output / 'QUERIES.jsonl.gz'
        with arrays.open('xb') as stream:
            np.savez_compressed(stream, uid=np.asarray(ids), raw_logits=queries['logits'],
                                corrected_logits=changed, support=trace['support'], eligible=trace['eligible'],
                                base=before, corrected=after, seeds=np.asarray(core.SEEDS),
                                cuts=core._cuts(frozen['cuts']['cuts']),
                                ensemble_cut=np.asarray(frozen['cuts']['ensemble_cut']),
                                selected_lambda=np.asarray(LAMBDA))
        write_rows(metadata, queries['rows'])
        # These fingerprints identify the consumed numeric configuration.
        # Original file SHA pins are retained by the experiment input seal.
        configuration = dict(geometry_digest=digest(frozen['geometry']), cuts_digest=digest(frozen['cuts']),
                             scales_digest=digest(frozen['scales']), normalizer_arrays=[
                                 dict(dtype=str(v.dtype), shape=list(v.shape),
                                      sha256=hashlib.sha256(v.tobytes()).hexdigest())
                                 for v in map(np.asarray, frozen['normalizer'])])
        result['audit'] = dict(decisions=dict(path=arrays.name, sha256=sha(arrays)),
                               queries=dict(path=metadata.name, sha256=sha(metadata)), frozen=configuration)
        write(output / 'RESULT.json', result)
        write(output / 'AUDIT_RECEIPT.json', dict(schema='history-normal-reference-dev-audit-v1',
              rows=len(ids), query_uid_sha256=result['query_uid_sha256'],
              reference_uid_sha256=result['reference_uid_sha256'],
              result_sha256=sha(output / 'RESULT.json'), files=result['audit'],
              additional_forwards=0, additional_distance_pairs=0, preserved_query_source_metadata=True))
    _update(runtime, 'DEV_GATE', status=result['status'], gate=result)
    return result


def protection_gate(report):
    """Per-group cumulative withdrawals vs RAW, deliberately without pool epsilon."""
    failures, missing = [], []
    for kind, allowance in (('device', 1.), ('attack_type', 5.), ('annotation', 5.)):
        for group in report['groups'][kind]:
            base = group['base']['attack']
            if base['rows'] == 0:
                continue
            identity = '|'.join(group['group'].values())
            raw_recall = base['weighted_rate']
            loss = group['attack_recall_loss_pp']
            if raw_recall is None or loss is None:
                missing.append(kind + ':' + identity)
                continue
            if loss > allowance + 1e-12:
                failures.append(kind + '_WITHDRAWAL_BUDGET:' + identity)
            # Under monotone correction each withdrawn TP strictly lowers the
            # group positive count; use counts to avoid rounding away a TP.
            withdrawn = base['positive'] - group['corrected']['attack']['positive']
            if raw_recall < .99 and withdrawn:
                failures.append(kind + '_RAW_BELOW_99_REQUIRES_ZERO_WITHDRAWAL:' + identity)
    return dict(schema=PROTECTION_SCHEMA,
                status='FAIL' if failures else 'NOT_EVALUABLE' if missing else 'PASS',
                failures=failures, missing=missing, pool_epsilon_enforced=False,
                device_loss_budget_pp=1., activity_annotation_loss_budget_pp=5.,
                low_raw_recall_zero_tp_withdrawal=True,
                group_fields=PROTECTION_GROUP_FIELDS)


def terminal_gate(pool_results):
    require(set(pool_results) == set(POOLS), 'EXACT_AB_POOLS')
    protection_failures, target_failures = [], []
    rates = {}
    for pool in POOLS:
        view = pool_results[pool]['views'][PRIMARY]
        require(set(view['reports']) == set(SUFFIXES), 'EXACT_FOUR_AB_HEAD_REPORTS')
        for suffix, report in view['reports'].items():
            gate = report['protection']
            if gate['status'] != 'PASS':
                protection_failures.append(dict(pool=pool, suffix=suffix, gate=gate))
        ensemble = view['reports']['ensemble']
        normal = ensemble['corrected']['normal']['weighted_rate']
        attack = ensemble['corrected']['attack']['weighted_rate']
        rates[pool] = normal
        if normal is None or normal > .02:
            target_failures.append(pool + ':POOL_FPR_ABOVE_2_OR_MISSING')
        if attack is None or attack < .99:
            target_failures.append(pool + ':POOL_RECALL_BELOW_99_OR_MISSING')
        # Every original normal-evaluation device needs a nonempty primary
        # denominator; deleting a branch cannot turn it into a passing device.
        groups = {g['group']['device']: g for g in ensemble['groups']['device']}
        for device in pool_results[pool]['original_devices']:
            group = groups.get(device)
            if group is None or not group['corrected']['normal']['rows']:
                target_failures.append(pool + ':DEVICE_PRIMARY_NORMAL_MISSING:' + device)
                continue
            value = group['corrected']['normal']['weighted_rate']
            if value is None or value > .02:
                target_failures.append(pool + ':DEVICE_FPR_ABOVE_2_OR_MISSING:' + group['group']['device'])
    improved = ((rates['UNSW_DEV'] is not None and rates['UNSW_DEV'] <= .09019653949) or
                (rates['CIC_DEV'] is not None and rates['CIC_DEV'] <= .03493481531))
    status = ('FAIL_PROTECTION' if protection_failures else 'PASS' if not target_failures else
              'IMPROVED_NOT_PASS' if improved else 'NOT_IMPROVED')
    return dict(schema='history-normal-reference-ab-gate-v1', status=status,
                primary_view=PRIMARY, protection_failures=protection_failures,
                target_failures=target_failures, selected_lambda=LAMBDA,
                no_retune=True, no_retry=True, evidence='CONSUMED_DEVELOPMENT_ONLY')


def union_bank(dense, history):
    """Original dense rows are byte-for-byte retained; historical cutoff view only changes."""
    ends = {}
    for row in dense['rows']:
        key = row['partition'], row['device']
        require(ends.setdefault(key, row['reference_end']) == row['reference_end'], 'DENSE_END_MISMATCH')
    old = {r['uid'] for r in dense['rows']}
    extra, indices = [], []
    for i, original in enumerate(history['rows']):
        key = original['partition'], original['device']
        if key not in ends:
            continue
        require(original['uid'] not in old, 'HISTORY_DENSE_DUPLICATE_UID')
        row = dict(original, reference_end=ends[key], historical_reference_end=original['reference_end'])
        extra.append(row); indices.append(i)
    require(extra, 'MISSING_TARGET_HISTORICAL_REFERENCES')
    rows = dense['rows'] + extra
    require(len({r['uid'] for r in rows}) == len(rows), 'UNION_DUPLICATE_UID')
    return joined(rows, np.concatenate((dense['e3'][:], history['e3'][indices])),
                  np.concatenate((dense['q14'][:], history['q14'][indices])))


def _pool_report(pool, data, trace, frozen, windows):
    metrics = helpers().metrics
    rows = data['rows']
    metrics.validate_full_weights(rows, pool)
    changed = core.apply_correction(data['logits'], trace['support'], frozen['scales'], LAMBDA)
    before, after = decisions(data['logits'], frozen), decisions(changed, frozen)
    require(not np.any(~before & after), 'CORRECTION_CANNOT_ADD_ALARMS')
    keep = np.flatnonzero(metrics.post_window_mask(rows, windows))
    require(len(keep), 'EMPTY_PRIMARY_VIEW')
    rr = [rows[int(i)] for i in keep]
    views = {}
    for name, ix, subset, weights in (
            ('full', np.arange(len(rows)), rows, metrics.original_weights(rows)),
            (PRIMARY, keep, rr, metrics.hierarchical_weights(rr, pool))):
        reports = {}
        for j, suffix in enumerate(SUFFIXES):
            report = metrics.report(subset, before[ix, j], after[ix, j], weights,
                                    trace['eligible'][ix], trace['support'][ix])
            report['protection'] = protection_gate(report)
            reports[suffix] = report
        views[name] = dict(rows=len(subset), retained_uid_sha256=core._uid_hash([r['uid'] for r in subset]),
                           weights_sha256=hashlib.sha256(weights.tobytes()).hexdigest(), reports=reports)
    return dict(pool=pool, query_rows=len(rows), views=views,
                original_devices=sorted({r['device'] for r in rows if r['label'] == 0})), before, after, changed


def evaluate_ab(root, output, historical_dataset, dev_result, runtime=None, manifest=None):
    """One terminal evaluation; failed DEV never constructs an A/B loader."""
    require(dev_result.get('status') == 'PASS_DEV' and dev_result.get('no_AB_loaded') is True,
            'DEV_GATE_REQUIRED_BEFORE_AB_LOAD')
    targets = {HEIM['device']} | {t['device'] for t in TARGETS.values()}
    require(historical_dataset['rows'] and
            {r['device'] for r in historical_dataset['rows']} == targets and
            all(r['use'] == 'REFERENCE' and r['label'] == 0 for r in historical_dataset['rows']),
            'AB_HISTORY_EXACT_FOUR_NORMAL_TARGETS')
    output = Path(output)
    require(not output.exists(), 'AB_ONCE_OUTPUT_ALREADY_EXISTS')
    output.mkdir(parents=True, exist_ok=False)
    # Persist attempt before loading any AB values. No resume/retry entrypoint.
    write(output / 'AB_ATTEMPT.json', dict(status='AB_ATTEMPT_STARTED', candidate='C1', retries=0,
                                         dev_query_uid_sha256=dev_result['query_uid_sha256']))
    assets = load_assets(root, manifest)
    frozen = assets.calibration()
    results = {}
    target_devices = targets
    pairs = 0
    for pool in POOLS:
        _update(runtime, 'AB_LOAD', pool=pool)
        data = assets.queries(pool)
        uids = [r['uid'] for r in data['rows']]
        require(not set(uids) & {r['uid'] for r in historical_dataset['rows']}, 'NEW_HISTORY_AB_UID_OVERLAP')
        old, baseline_result = assets.baseline(pool, uids)
        require(np.array_equal(old['raw_logits'], data['logits']) and
                np.array_equal(old['base'], decisions(data['logits'], frozen)), 'RAW_BASELINE_REPLAY')
        dense = assets.dense(pool)
        merged = union_bank(dense, historical_dataset)
        bank = _bank(merged, frozen['normalizer'], history_replay=True)
        selected = np.asarray([i for i, r in enumerate(data['rows']) if r['device'] in target_devices], dtype=np.int64)
        require(len(selected), 'MISSING_TARGET_AB_QUERIES')
        new = support_once(bank, _subset(data, selected), frozen['geometry'], runtime, 'AB_SUPPORT_' + pool)
        trace = dict(support=old['support'].copy(), eligible=old['eligible'].copy())
        trace['support'][selected], trace['eligible'][selected] = new['support'], new['eligible']
        pairs += new['distance_pairs']
        result, before, after, changed = _pool_report(pool, data, trace, frozen, assets.spec['pools'][pool]['windows'])
        untouched = np.ones(len(uids), dtype=bool); untouched[selected] = False
        require(np.array_equal(after[untouched], old['corrected'][untouched]), 'UNTOUCHED_BASELINE_DECISION_REPLAY')
        old_views = baseline_result['arms']['R-DENSE']['0.1']['views']
        result['comparison_179700'] = {name: {
            suffix: dict(old_fpr=old_views[name]['reports'][suffix]['corrected']['normal']['weighted_rate'],
                         new_fpr=result['views'][name]['reports'][suffix]['corrected']['normal']['weighted_rate'])
            for suffix in SUFFIXES} for name in result['views']}
        result.update(new_support_rows=len(selected), reused_support_rows=int(untouched.sum()),
                      distance_pairs=new['distance_pairs'], untouched_decisions_exact=True,
                      original_dense_rows_retained=len(dense['rows']), union_rows=len(merged['rows']))
        pool_out = output / pool; pool_out.mkdir()
        np.savez_compressed(pool_out / 'DECISIONS.npz', uid=np.asarray(uids), raw_logits=data['logits'],
                            corrected_logits=changed, base=before, corrected=after,
                            support=trace['support'], eligible=trace['eligible'], selected_lambda=np.asarray(LAMBDA))
        helpers().write(pool_out / 'RESULT.json', result)
        results[pool] = result
        _update(runtime, 'AB_POOL_COMPLETE', pool=pool, primary_fpr=result['views'][PRIMARY]['reports']['ensemble']['corrected']['normal']['weighted_rate'])
        del data, old, dense, merged, bank, trace, before, after, changed
    result = terminal_gate(results)
    result.update(pools=results, distance_pairs=pairs, candidate='C1', path='P-DEVONLY',
                  primary_goal_fpr=.02, new_AB_encoding=0, new_base_head_training=0,
                  source_bank_modified=False, calibration_refit=0, terminal=True)
    assets.immutable()
    helpers().write(output / 'RESULT.json', result)
    write(output / 'INPUT_SEAL.json', {str(p): s for p, s in assets.inputs.pins.items()})
    _update(runtime, 'AB_TERMINAL', status=result['status'])
    return result
