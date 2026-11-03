"""Independent saved-output audit: no model forward, distance CAL, or target evaluation.

Reconstructs reference merges and attack-risk summaries from frozen source rows,
saved head logits, and the reported withdrawal UIDs. It deliberately does not
claim to recreate support/normal-correction traces that were not persisted.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

SUFFIXES = ('27', '127', '227', 'ensemble')
GRID = (0.0, 0.05, 0.1, 0.25)
EPSILONS = (0.0, 0.05, 0.1, 0.2)


def check(value, label):
    if not value:
        raise AssertionError(label)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode()


def uid_hash(uids):
    return hashlib.sha256(('\n'.join(uids) + '\n').encode()).hexdigest()


def arrays(path):
    with np.load(path, allow_pickle=False) as data:
        result = {key: data[key].copy() for key in data.files}
    ids = result['uid'].tolist()
    check(len(ids) == len(set(ids)), 'ARRAY_UID_UNIQUENESS:' + str(path))
    check(result['e3'].shape == (len(ids), 768) and result['q14'].shape == (len(ids), 14), 'ARRAY_SHAPES')
    check(result['e3'].dtype == result['q14'].dtype == np.dtype('float32'), 'ARRAY_DTYPES')
    check(np.isfinite(result['e3']).all() and np.isfinite(result['q14']).all(), 'ARRAY_FINITE')
    check(np.all((result['q14'] >= 0) & (result['q14'] <= 1)), 'Q14_RANGE')
    return result


def weights(rr):
    branches = defaultdict(set)
    counts = Counter()
    keys = [tuple(r[f] for f in ('device', 'activity', 'capture_id', 'session_id')) for r in rr]
    for key in keys:
        for depth in range(4):
            branches[key[:depth]].add(key[depth])
        counts[key] += 1
    return np.asarray([1 / (counts[key] * math.prod(len(branches[key[:d]]) for d in range(4)))
                       for key in keys], dtype=np.float64)


def risk(base, lost, ws, ix):
    ix = np.asarray(ix, dtype=np.int64)
    total = math.fsum(ws[ix])
    out = dict(rows=len(ix), weight_mass=total, suffixes={})
    for k, suffix in enumerate(SUFFIXES):
        detected = math.fsum(ws[ix][base[ix, k]])
        withdrawn = math.fsum(ws[ix][lost[ix, k]])
        retained = math.fsum(ws[ix][base[ix, k] & ~lost[ix, k]])
        out['suffixes'][suffix] = dict(baseline_detected_weight=detected,
            added_fn_weight=withdrawn, remaining_detected_weight=retained,
            baseline_recall=None if total == 0 else detected / total,
            corrected_recall=None if total == 0 else retained / total,
            recall_loss_pp=None if total == 0 else 100.0 * (withdrawn / total),
            added_fn_count=int(lost[ix, k].sum()))
    return out


def acceptance(candidate, epsilon):
    failures = []
    for suffix, item in candidate['overall']['suffixes'].items():
        if item['corrected_recall'] < 0.99:
            failures.append('ABSOLUTE_RECALL:' + suffix)
        if item['recall_loss_pp'] > epsilon:
            failures.append('RELATIVE_LOSS:' + suffix)
    for field, cap in (('devices', 1.0), ('annotations', 5.0)):
        for group, group_risk in candidate[field].items():
            if group_risk['weight_mass'] == 0:
                continue
            for suffix, item in group_risk['suffixes'].items():
                if item['recall_loss_pp'] > cap:
                    failures.append(field.upper() + '_LOSS:' + group + ':' + suffix)
    return dict(passes=not failures, failures=failures)


def select(prep, epsilon):
    candidates = []
    for candidate in prep['candidates']:
        accepted = acceptance(candidate, epsilon)
        candidates.append(dict(lambda_value=candidate['lambda_value'],
            selection_pass=candidate['legacy_zero_withdrawal_pass'] if epsilon == 0 else accepted['passes'],
            budget_acceptance=accepted, normal_quality=candidate['normal_quality']))
    valid = [item for item in candidates if item['selection_pass']]
    selected = max(valid, key=lambda item: (item['normal_quality'], item['lambda_value'])) if valid else None
    return dict(version='onboarding-budget-selection-v1', epsilon_pp=epsilon, epsilon_fraction=epsilon / 100.0,
        status='NO_FEASIBLE_WORKPOINT' if selected is None else
               'SOURCE_DRY_RUN_WORKPOINT' if selected['budget_acceptance']['passes'] else
               'LEGACY_SELECTION_FAILS_NEW_ACCEPTANCE',
        selected_lambda=None if selected is None else selected['lambda_value'],
        selected_budget_acceptance=None if selected is None else selected['budget_acceptance'],
        selected_can_evaluate=False,
        selection_mode='LEGACY_ZERO_WITHDRAWAL_COMPATIBILITY' if epsilon == 0 else 'WEIGHTED_BUDGET',
        candidates=candidates, epsilon_zero_matches_legacy_selection=epsilon == 0,
        no_target_scores_used=True, target_evaluation_authorized=False)


def audit(science, root, package):
    enc, cal = science / 'encode', science / 'source_cal'
    vendor = package / 'vendor/encoding_v2'
    outer, encoded, source = (read(p / 'RESULT.json') for p in (science, enc, cal))
    check(outer['status'] == 'COMPLETE' and outer['stages'] == ['runtime', 'encode', 'source_cal'], 'PREFIX_COMPLETE')
    check(outer['evaluation_scope'] == 'AUTHORIZED_STAGE_PREFIX_ONLY' and outer['optimizer_updates'] == 0, 'PREFIX_SCOPE')
    check(encoded['status'] == 'COMPLETE' and encoded['mode'] == 'encode' and encoded['batch_repair_verified'], 'ENCODING_COMPLETE')
    check(encoded['no_training'] and not encoded['target_evaluation'] and encoded['classifier_forwards'] == 0, 'ENCODING_SCOPE')
    check(source['status'] == 'SOURCE_CAL_COMPLETE' and source['no_AB_loaded'] and source['no_model_forward'], 'SOURCE_CAL_COMPLETE')
    config = read(vendor / 'config.json')
    summary = dict(scope='saved outputs only; no model/distance forward or target evaluation', banks={}, datasets={})
    new_arrays, tensor_receipts = {}, {}
    for spec in config['datasets']:
        name = spec['name']
        rr = rows(vendor / spec['metadata'])
        data = arrays(enc / (name + '.npz'))
        ids = data['uid'].tolist()
        check(set(ids) == {r['uid'] for r in rr} and len(ids) == len(rr), 'ENCODED_REQUEST_SET:' + name)
        receipt = rows(enc / (name + '.tensor_receipts.jsonl.gz'))
        check([item['uid'] for item in receipt] == ids, 'TENSOR_RECEIPT_UID_ORDER:' + name)
        for i, item in enumerate(receipt):
            check(item['feature_sha256'] == hashlib.sha256(data['e3'][i].tobytes()).hexdigest(), 'VECTOR_RECEIPT_SHA:' + name)
        with np.load(vendor / spec['q14'], allow_pickle=False) as frozen:
            qmap = {u: frozen['q14'][i].copy() for i, u in enumerate(frozen['uid'].tolist())}
        check(all(data['q14'][i].tobytes() == qmap[uid].tobytes() for i, uid in enumerate(ids)), 'REQUEST_Q14_BYTES:' + name)
        new_arrays[name] = data
        tensor_receipts[name] = receipt
        summary['datasets'][name] = dict(rows=len(ids), feature_receipts_verified=len(receipt), uid_sha256=uid_hash(ids))
    banks = {}
    for spec in config['banks']:
        name = spec['name']
        bankdir = enc / 'banks' / name
        receipt = read(bankdir / 'receipt.json')
        check(receipt['status'] == 'COMPLETE' and not receipt['reselection'] and receipt['existing_vectors_unchanged'], 'BANK_RECEIPT')
        check(receipt['bank_sha256'] == sha(bankdir / 'bank.npz') and receipt['metadata_sha256'] == sha(bankdir / 'references.jsonl.gz'), 'BANK_SHA')
        check(sha(bankdir / 'references.jsonl.gz') == sha(vendor / spec['metadata']), 'BANK_FROZEN_METADATA_BYTES:' + name)
        rr = rows(bankdir / 'references.jsonl.gz')
        bank = arrays(bankdir / 'bank.npz')
        ids = [r['uid'] for r in rr]
        check(ids == bank['uid'].tolist() and len(ids) == receipt['rows'], 'BANK_UID_ORDER:' + name)
        check(all(r['use'] == 'REFERENCE' and r['label'] == 0 and r['timestamp'] <= r['reference_end'] for r in rr), 'REFERENCE_ROLE_TIME')
        old = arrays(vendor / spec['existing_bank'])
        fresh = new_arrays[spec['supplement_dataset']]
        oldmap = {u: i for i, u in enumerate(old['uid'].tolist())}
        freshmap = {u: i for i, u in enumerate(fresh['uid'].tolist())}
        check(not set(oldmap).intersection(freshmap) and set(oldmap).union(freshmap) == set(ids), 'MERGE_PARTITION:' + name)
        for i, uid in enumerate(ids):
            src, j = (old, oldmap[uid]) if uid in oldmap else (fresh, freshmap[uid])
            check(all(bank[key][i].tobytes() == src[key][j].tobytes() for key in ('e3', 'q14')), 'MERGED_VECTOR_BYTES:' + name)
        banks[name] = rr, bank
        summary['banks'][name] = dict(rows=len(ids), reused=len(oldmap), new=len(freshmap), sha256=sha(bankdir / 'bank.npz'))
    old = arrays(vendor / 'data/SOURCE_REFS/EXISTING_BANK.npz')
    replay = new_arrays['ORIGINAL104']
    replaymap = {uid: i for i, uid in enumerate(replay['uid'].tolist())}
    check(all(old['e3'][i].tobytes() == replay['e3'][replaymap[uid]].tobytes() for i, uid in enumerate(old['uid'].tolist())), 'ORIGINAL104_INDEPENDENT_BYTES')
    parity = read(enc / 'ORIGINAL104_PARITY.json')
    check(parity['original104_exact_bytes'] and parity['mismatch_count'] == 0 and parity['max_abs_error'] == 0, 'ORIGINAL104_RECEIPT')
    batch = read(enc / 'BATCH_REPAIR_RECEIPT.json')
    budget_file = root / 'runs/dense_reference_batch_repair_v1_20261027/ENCODER_PHYSICAL_BUDGET.json'
    budget = read(budget_file)
    check(batch['budget_sha256'] == sha(budget_file) and
          batch['budget_content_sha256'] == hashlib.sha256(canonical(budget)).hexdigest() and
          batch['totals'] == budget['totals'] and batch['policy'] == budget['policy'], 'FROZEN_PHYSICAL_BUDGET')
    for dataset in budget['datasets']:
        grouped = defaultdict(list)
        for item in tensor_receipts[dataset['name']]:
            grouped[tuple(item['shape'])].append(item['uid'])
        queue = []
        for shape in sorted(grouped):
            ids = sorted(grouped[shape])
            for start in range(0, len(ids), 16):
                queue.append(dict(shape=list(shape), uids=ids[start:start+16]))
        check(hashlib.sha256(canonical(queue)).hexdigest() == dataset['queue_sha256'], 'FROZEN_BATCH_QUEUE_UID_SHAPES')
    check(batch['batch_ledger_sha256'] == sha(enc / 'BATCH_REPAIR_BATCHES.jsonl') and
          encoded['batch_repair_receipt_sha256'] == sha(enc / 'BATCH_REPAIR_RECEIPT.json'), 'BATCH_SEAL')
    ledger = [json.loads(line) for line in (enc / 'BATCH_REPAIR_BATCHES.jsonl').read_text().splitlines()]
    check(len(ledger) == 2 * batch['totals']['batches'], 'BATCH_LEDGER_COUNT')
    counts = Counter()
    offsets, batch_indices = Counter(), Counter()
    for k in range(0, len(ledger), 2):
        a, b = ledger[k:k+2]
        check(a['status'] == 'FORWARD_ATTEMPT' and b['status'] == 'FORWARD_COMPLETE' and
              (a['dataset'], a['batch_index']) == (b['dataset'], b['batch_index']), 'BATCH_ATTEMPT_COMPLETE')
        logical = a['logical_rows']
        name = a['dataset']
        offset = offsets[name]
        segment = tensor_receipts[name][offset:offset+logical]
        check(a['batch_index'] == batch_indices[name] and len(segment) == logical and
              a['uid_sha256'] == hashlib.sha256(canonical([r['uid'] for r in segment])).hexdigest() and
              all(r['shape'] == a['shape'] for r in segment), 'LEDGER_TENSOR_UID_SHAPE_BINDING')
        check(b['first_feature_sha256'] == segment[0]['feature_sha256'], 'LEDGER_FIRST_VECTOR_SHA')
        check(a['physical_positions'] == (16 if logical == 1 else logical), 'BATCH_PHYSICAL_SIZE')
        check(a['clone_positions'] == a['physical_positions'] - logical and a['singleton_clone'] == (logical == 1), 'BATCH_CLONE_RULE')
        if logical == 1:
            check(b['all_cloned_input_tensors_equal'] and b['all_16_clone_outputs_byte_equal'], 'CLONE_BYTES_PROOF')
            check(a['input_tensor_sha256'] == segment[0]['actual_tensor_sha256'], 'SINGLETON_LOGICAL_INPUT_SHA')
        counts.update(logical_rows=logical, physical_positions=a['physical_positions'], clone_positions=a['clone_positions'],
                      singleton_batches=int(logical == 1), batches=1)
        offsets[name] += logical
        batch_indices[name] += 1
    check(dict(counts) == batch['totals'] and batch['clone_rows_in_bank'] == 0 and batch['target_query_inputs'] == 0, 'BATCH_TOTALS')
    check(all(offsets[name] == len(data['uid']) for name, data in new_arrays.items()), 'LEDGER_ALL_LOGICAL_UIDS_ACCOUNTED')
    summary['batch_totals'] = dict(counts)

    prepared = root / 'runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared'
    trace = root / 'runs/diagnostics_d1_d2_v1_20261022/output/d1/r2/source_actual_trace.npz'
    calibr = root / 'runs/diagnostics_d1_d2_v1_20261022/assets/onboarding/run/evaluation/calibration'
    refs = root / 'runs/diagnostics_d1_d2_v1_20261022/assets/reference_scores'
    required_inputs = [prepared / name for name in ('LEARN.jsonl.gz', 'LEARN_q.npy', 'CAL.npz', 'normalizer.npz')]
    required_inputs += [calibr / (name + '.json') for name in ('cuts', 'geometry', 'scales', 'protection')]
    required_inputs += [refs / name for name in ('SOURCE_REFS.jsonl.gz', 'SOURCE_REFS.npz')]
    required_inputs += [root / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy',
        trace, enc / 'banks/SOURCE_REFS/bank.npz', enc / 'banks/SOURCE_REFS/references.jsonl.gz',
        enc / 'banks/SOURCE_REFS/receipt.json', vendor / 'data/SOURCE_REFS/DENSE_PLAN.json',
        enc / 'RESULT.json', root / 'repo/ood/constrained_onboarding_core_v3.py',
        root / 'repo/ood/onboarding_budget_v1.py']
    source_seal = read(cal / 'INPUT_SEAL.json')
    # Remote absolute paths may resolve through symlinks; exact checksum
    # multisets preserve every consumed input without fabricating local paths.
    local_seal = {p.as_posix(): sha(p) for p in required_inputs}
    check(Counter(local_seal.values()) == Counter(source_seal.values()), 'COMPLETE_SOURCE_INPUT_SEAL_BYTES')
    summary['source_input_seal'] = dict(input_count=len(local_seal), all_consumed_bytes_match_local_frozen_assets=True,
        remote_seal_sha256=sha(cal / 'INPUT_SEAL.json'), local_inputs=local_seal)
    with np.load(prepared / 'CAL.npz', allow_pickle=False) as data:
        ix = data['indices'].copy()
    check(len(ix) == 148819 and np.array_equal(ix, np.unique(ix)), 'CAL_INDICES')
    wanted = set(ix.tolist())
    calrows = []
    with gzip.open(prepared / 'LEARN.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for i, line in enumerate(stream):
            row = json.loads(line)
            check((row['fit_role'] == 'CAL') == (i in wanted), 'CAL_ROLE_INDEX_BINDING')
            if i in wanted:
                calrows.append(row)
    with np.load(trace, allow_pickle=False) as data:
        check(data['uid'].tolist() == [r['uid'] for r in calrows], 'TRACE_UID_ORDER')
        logits, saved = data['original_logits'].copy(), data['original_decisions'].copy()
    cuts = read(calibr / 'cuts.json')
    ensemble = np.stack([logits[:, j].astype(np.float64) for j in range(3)]).mean(0, dtype=np.float64)
    base = np.column_stack((logits > cuts['cuts'], ensemble > cuts['ensemble_cut']))
    check(base.tobytes() == saved.tobytes(), 'BASE_DECISION_BYTES')
    ai = np.flatnonzero([r['label'] == 1 for r in calrows])
    ni = np.flatnonzero([r['label'] == 0 for r in calrows])
    attacks, normals = [calrows[i] for i in ai], [calrows[i] for i in ni]
    check((len(attacks), len(normals)) == (115672, 33147), 'CAL_CLASS_COUNTS')
    aw, nw = weights(attacks), weights(normals)
    attackmap = {r['uid']: i for i, r in enumerate(attacks)}
    groups = {f: {name: [i for i, r in enumerate(attacks) if r[f] == name] for name in sorted({r[f] for r in attacks})}
              for f in ('device', 'activity')}
    source_components = {r['component_id'] for r in banks['SOURCE_REFS'][0]}
    check(not source_components.intersection(r['component_id'] for r in calrows), 'REFERENCE_CAL_COMPONENT_ISOLATION')
    source_uid = {r['uid'] for r in banks['SOURCE_REFS'][0]}
    check(not source_uid.intersection(r['uid'] for r in calrows), 'REFERENCE_CAL_UID_ISOLATION')
    old_protection = read(calibr / 'protection.json')
    summary['source_cal'] = {}
    for arm in ('R-B2', 'R-DENSE'):
        prep = read(cal / arm / 'PREPARATION.json')
        check(prep['lambda_grid'] == list(GRID) and prep['seed_order'] == [27, 127, 227], 'PREPARATION_GRID')
        for name, rr, ws in (('attack', attacks, aw), ('normal', normals, nw)):
            check(prep['weight_identity'][name] == dict(rows=len(rr), total=math.fsum(ws),
                uid_sha256=uid_hash([r['uid'] for r in rr]), float64_sha256=hashlib.sha256(ws.tobytes()).hexdigest()), 'WEIGHT_IDENTITY:' + arm)
        check([c['lambda_value'] for c in prep['candidates']] == list(GRID), 'CANDIDATE_GRID')
        previous = np.zeros((len(attacks), 4), dtype=bool)
        candidates = []
        for candidate, legacy in zip(prep['candidates'], prep['legacy_protection']['candidates']):
            lost = np.zeros_like(previous)
            for k, suffix in enumerate(SUFFIXES):
                uids = candidate['newly_missed_uids'][suffix]
                loc = [attackmap[u] for u in uids]
                check(loc == sorted(set(loc)), 'ADDED_FN_UID_ORDER_UNIQUENESS')
                lost[loc, k] = True
            check(not np.any(lost & ~base[ai]) and not np.any(previous & ~lost), 'FN_BASE_SUBSET_MONOTONE')
            check(candidate['overall'] == risk(base[ai], lost, aw, range(len(attacks))), 'POOL_RISK_EXACT:' + arm)
            for field, rowfield in (('devices', 'device'), ('annotations', 'activity')):
                expected = {g: risk(base[ai], lost, aw, gi) for g, gi in groups[rowfield].items()}
                check(candidate[field] == expected, 'GROUP_RISK_EXACT:' + arm + ':' + field)
            check(candidate['newly_missed_uids'] == legacy['newly_missed_uids'] and
                  candidate['legacy_zero_withdrawal_pass'] == (not lost.any()) == legacy['passes'], 'LEGACY_FN_COMPATIBILITY')
            quality = candidate['normal_fp_reduction']
            check(set(quality) == set(SUFFIXES) and all(0 <= quality[s] <= 1 for s in SUFFIXES) and
                  candidate['normal_quality'] == math.fsum(quality.values()) / 4, 'NORMAL_SUMMARY_CONSISTENCY')
            candidates.append(dict(lambda_value=candidate['lambda_value'], added_fn={s: int(lost[:, k].sum()) for k, s in enumerate(SUFFIXES)},
                                   normal_fp_reduction=quality, pool_risk=candidate['overall']['suffixes']))
            previous = lost
        legacy_lambda = max(c['lambda_value'] for c in prep['candidates'] if c['legacy_zero_withdrawal_pass'])
        check(legacy_lambda == prep['legacy_protection']['selected_lambda'], 'LEGACY_SELECTOR_REPLAY')
        if arm == 'R-B2':
            check(legacy_lambda == old_protection['selected_lambda'], 'B2_ORIGINAL_LAMBDA')
            for new, old in zip(prep['legacy_protection']['candidates'], old_protection['candidates']):
                for field in ('lambda_value', 'passes', 'new_miss_count', 'new_miss_pair_count', 'newly_missed_uids', 'cap_reachable_detected_attack_count'):
                    check(new[field] == old[field], 'B2_ORIGINAL_PROTECTION:' + field)
        points = {}
        for epsilon in EPSILONS:
            point = select(prep, epsilon)
            check(point == read(cal / arm / ('EPSILON_' + str(epsilon).replace('.', 'p') + '.json')) ==
                  source['arms'][arm]['selections'][str(epsilon)], 'INDEPENDENT_WORKPOINT_EXACT:' + arm)
            points[str(epsilon)] = dict(selected_lambda=point['selected_lambda'], status=point['status'],
                                        budget_acceptance=point['selected_budget_acceptance'])
        zero = read(cal / arm / 'EPS0_PARITY.json')
        check(zero['epsilon_zero_full_CAL_same_environment_legacy_bytes_equal'], 'EXECUTED_EPS0_PARITY_PROOF')
        if arm == 'R-B2':
            check(zero['prior_local_environment_decisions_bytes_equal'], 'B2_PRIOR_DECISIONS_PROOF')
        summary['source_cal'][arm] = dict(candidates=candidates, workpoints=points,
            epsilon_zero_parity_execution_proof=zero, independent_full_support_recomputed=False)
    summary['limitations'] = [
        'No model forward or full distance/support recalibration was repeated.',
        'Added-FN membership was consumed from saved candidate UID sets; all source/group weights, fixed head decisions, counts, losses and selections were independently reconstructed.',
        'Normal-query support/corrected UID traces were not persisted; normal FP-reduction values were checked for consistency, not independently recreated.',
        'Dense full-CAL epsilon-zero corrected-logit byte parity is supported by execution proofs; offline support/logit hashes were not independently recreated.',
        'No new A/B FPR or attack recall exists in this prefix result.'
    ]
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--science', required=True)
    parser.add_argument('--root', required=True)
    parser.add_argument('--package', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    check(not output.exists(), 'FRESH_AUDIT_OUTPUT')
    result = dict(status='PASS', created_utc=datetime.now(timezone.utc).isoformat(),
                  script_sha256=sha(__file__), numpy=np.__version__, python=sys.version,
                  science=Path(args.science).resolve().as_posix())
    try:
        result.update(audit(Path(args.science).resolve(), Path(args.root).resolve(), Path(args.package).resolve()))
    except BaseException as exc:
        result.update(status='FAIL', error_type=type(exc).__name__, error=str(exc))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
        raise
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps(dict(status=result['status'], banks=result['banks'], batch_totals=result['batch_totals'],
        workpoints={arm: item['workpoints'] for arm, item in result['source_cal'].items()}), ensure_ascii=False))


if __name__ == '__main__':
    main()
