"""Execute sealed source-only R-B2/R-DENSE budget CAL after supplement encoding.

No A/B loading, E3/model forward, FIT fitting or parameter changes. A completed
encoding receipt and explicit cloud authorization receipt are prerequisites.
This entry was prepared, not run against the future dense bank, on 2026-10-25.
"""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import sys
import time

for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS', 'NUMEXPR_NUM_THREADS'):
    os.environ[_name] = '4'
sys.dont_write_bytecode = True
import numpy as np


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024**2), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=True, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    os.replace(temporary, path)


def rows(path):
    with gzip.open(path, 'rt', encoding='utf-8') as stream:
        return [json.loads(line) for line in stream]


def validate_bank(metadata, bank, plan, original_rows, original_bank):
    """UID join, frozen position set and byte-exact original104 reuse gate."""
    uids = [r['uid'] for r in metadata]
    require(len(uids) == len(set(uids)) == 4728, 'SOURCE_DENSE_POSITION_COUNT_UIDS')
    require(set(uids) == set(plan['selected_uids']) and len(plan['selected_uids']) == len(uids),
            'FROZEN_SOURCE_POSITION_SET')
    require(bank['uid'].tolist() == uids, 'SOURCE_BANK_METADATA_ARRAY_ORDER')
    require(bank['e3'].shape == (len(uids), 768) and bank['q14'].shape == (len(uids), 14)
            and bank['e3'].dtype == bank['q14'].dtype == np.float32
            and np.isfinite(bank['e3']).all() and np.isfinite(bank['q14']).all(), 'SOURCE_BANK_ARRAY_SCHEMA')
    require(all(r.get('partition') == 'LEARN' and r.get('label') == 0 and r.get('use') == 'REFERENCE'
                and r['timestamp'] <= r['reference_end'] for r in metadata), 'SOURCE_REFERENCE_ROLE_TIME')
    old_uids = [r['uid'] for r in original_rows]
    require(len(old_uids) == 104 and original_bank['uid'].tolist() == old_uids, 'ORIGINAL104_IDENTITY')
    lookup = {uid: i for i, uid in enumerate(uids)}
    for i, uid in enumerate(old_uids):
        require(uid in lookup, 'ORIGINAL104_MISSING')
        j = lookup[uid]
        for name in ('e3', 'q14'):
            require(bank[name][j].tobytes() == original_bank[name][i].tobytes(), 'ORIGINAL104_BYTES:' + name)
        identity_fields = ('uid', 'capture_id', 'source_sha256', 'frame', 'timestamp', 'device', 'owner',
                           'partition', 'use', 'label', 'activity', 'session_id', 'component_id',
                           'protocol', 'canonical_key', 'reference_end')
        require(all(metadata[j].get(field) == original_rows[i].get(field) for field in identity_fields),
                'ORIGINAL104_SCIENTIFIC_METADATA_CHANGED')


class RecordingBank:
    def __init__(self, bank):
        self.bank, self.rows = bank, bank.rows
        self.attack_matrix, self.normal_own = None, None

    def matrix(self, *args, **kwargs):
        require(self.attack_matrix is None, 'ATTACK_MATRIX_RECOMPUTED')
        self.attack_matrix = self.bank.matrix(*args, **kwargs)
        return self.attack_matrix

    def own(self, *args, **kwargs):
        require(self.normal_own is None, 'NORMAL_SUPPORT_RECOMPUTED')
        self.normal_own = self.bank.own(*args, **kwargs)
        return self.normal_own


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True, help='Repository/portable tree root with sealed saved assets')
    parser.add_argument('--dense-bank', required=True, help='Future encoder banks/SOURCE_REFS directory')
    parser.add_argument('--encoding-result', required=True)
    parser.add_argument('--approval-file', required=True)
    parser.add_argument('--source-plan', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    root, dense, output = Path(args.root).resolve(), Path(args.dense_bank).resolve(), Path(args.output).resolve()
    require(not output.exists() and not output.is_relative_to(dense), 'NEW_OUTPUT_OUTSIDE_ENCODING_INPUT')
    approval = read(args.approval_file)
    require(approval.get('user_authorized') is True and approval.get('dense_source_cal') is True,
            'DENSE_SOURCE_CAL_NOT_AUTHORIZED')
    encoded = read(args.encoding_result)
    require(encoded.get('status') == 'COMPLETE' and encoded.get('mode') == 'encode', 'ENCODING_NOT_COMPLETE')
    parity_datasets = [item for item in encoded.get('datasets', []) if item.get('original104_parity') is not None]
    require(len(parity_datasets) == 1 and parity_datasets[0].get('measured_rows') == 104
            and parity_datasets[0].get('original104_parity', {}).get('original104_exact_bytes') is True
            and parity_datasets[0].get('original104_parity', {}).get('mismatch_count') == 0,
            'ENCODER_ORIGINAL104_REENCODE_PARITY_NOT_VERIFIED')
    require(approval.get('package_sha256') == encoded.get('package_sha256'), 'AUTHORIZATION_ENCODING_PACKAGE_IDENTITY')
    require(approval.get('source_plan_sha256') == sha(args.source_plan), 'AUTHORIZATION_SOURCE_PLAN_IDENTITY')
    receipt = read(dense / 'receipt.json')
    require(receipt.get('status') == 'COMPLETE' and receipt.get('frozen_selection') is True
            and receipt.get('reselection') is False, 'DENSE_BANK_ENCODING_RECEIPT')
    require(receipt['bank_sha256'] == sha(dense / 'bank.npz')
            and receipt['metadata_sha256'] == sha(dense / 'references.jsonl.gz'), 'DENSE_BANK_ENCODING_SHA')
    sys.path.insert(0, str(root / 'repo/ood'))
    import constrained_onboarding_core_v3 as core
    import onboarding_budget_v1 as budget
    from indexed_features_v1 import IndexedMatrix

    assets = root / 'runs/diagnostics_d1_d2_v1_20261022/assets'
    prepared = assets / 'heads/run/prepared'
    calibration = assets / 'onboarding/run/evaluation/calibration'
    references = assets / 'reference_scores'
    features = root / 'runs/ecs_cache_resume_v1_20261020/verified_cache_20261022/features/LEARN.npy'
    trace_path = root / 'runs/diagnostics_d1_d2_v1_20261022/output/d1/r2/source_actual_trace.npz'
    paths = [prepared / n for n in ('LEARN.jsonl.gz', 'LEARN_q.npy', 'CAL.npz', 'normalizer.npz')]
    paths += [calibration / (n + '.json') for n in ('cuts', 'geometry', 'scales', 'protection')]
    paths += [references / n for n in ('SOURCE_REFS.jsonl.gz', 'SOURCE_REFS.npz')]
    paths += [features, trace_path, dense / 'bank.npz', dense / 'references.jsonl.gz', dense / 'receipt.json',
              Path(args.source_plan), Path(args.encoding_result), root / 'repo/ood/constrained_onboarding_core_v3.py',
              root / 'repo/ood/onboarding_budget_v1.py']
    initial = {str(p): sha(p) for p in paths}
    prior_seal = read(root / 'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/INPUT_SEAL.json')
    expected_inputs = {str((root / entry['path']).resolve()): entry['sha256'] for entry in prior_seal['inputs']}
    for path, checksum in initial.items():
        resolved = str(Path(path).resolve())
        if resolved in expected_inputs:
            require(checksum == expected_inputs[resolved], 'PRIOR_SOURCE_INPUT_IDENTITY:' + path)
    protected = (prepared, calibration.parent, references, features.parent, dense)
    require(not any(output.is_relative_to(path) for path in protected), 'OUTPUT_INSIDE_FROZEN_ASSETS')
    binding = read(assets / 'heads/run/cache_binding.json')
    require(binding['feature_files']['LEARN.npy'] == initial[str(features)], 'SOURCE_CACHE_BINDING')
    require(binding['normalizer_files']['RECENT.npz'] == initial[str(prepared / 'normalizer.npz')], 'NORMALIZER_BINDING')
    for seal_root in (prepared, calibration.parent):
        seal = dict(line.split('  ', 1)[::-1] for line in (seal_root / 'SHA256SUMS').read_text().splitlines() if line)
        for path in paths:
            if path.is_relative_to(seal_root) and path.relative_to(seal_root).as_posix() in seal:
                require(initial[str(path)] == seal[path.relative_to(seal_root).as_posix()], 'FROZEN_SAVED_ASSET_SHA')
    frozen_core = root / 'runs/onboarding_new_lineage_v1_20261022/package_v3/constrained_onboarding_core_v3.py'
    require(sha(frozen_core) == sha(root / 'repo/ood/constrained_onboarding_core_v3.py'), 'FROZEN_V3_CORE_CHANGED')
    old_rows, dense_rows = rows(references / 'SOURCE_REFS.jsonl.gz'), rows(dense / 'references.jsonl.gz')
    with np.load(references / 'SOURCE_REFS.npz', allow_pickle=False) as data:
        old_bank = {k: data[k].copy() for k in ('uid', 'e3', 'q14')}
    with np.load(dense / 'bank.npz', allow_pickle=False) as data:
        dense_bank = {k: data[k].copy() for k in ('uid', 'e3', 'q14')}
    validate_bank(dense_rows, dense_bank, read(args.source_plan), old_rows, old_bank)
    with np.load(prepared / 'CAL.npz', allow_pickle=False) as data:
        cal_indices = data['indices'].copy()
    require(len(cal_indices) == 148819 and np.array_equal(cal_indices, np.sort(np.unique(cal_indices))), 'FULL_CAL_INDICES')
    cal_set = set(cal_indices.tolist())
    cal_rows = []
    with gzip.open(prepared / 'LEARN.jsonl.gz', 'rt', encoding='utf-8') as stream:
        for index, line in enumerate(stream):
            row = json.loads(line)
            require((row.get('fit_role') == 'CAL') == (index in cal_set), 'CAL_ROLE_INDEX_JOIN')
            if index in cal_set:
                cal_rows.append(row)
    require(len(cal_rows) == 148819, 'FULL_CAL_ROWS')
    with np.load(trace_path, allow_pickle=False) as data:
        require(data['uid'].tolist() == [r['uid'] for r in cal_rows], 'SAVED_LOGIT_CAL_UID_JOIN')
        logits, saved = data['original_logits'].copy(), data['original_decisions'].copy()
    cuts, geometry, scales = (read(calibration / (n + '.json')) for n in ('cuts', 'geometry', 'scales'))
    require(cuts['seeds'] == list(core.SEEDS) and not cuts['moved'], 'CUTS_SEEDS_FROZEN')
    baseline = np.column_stack((logits > cuts['cuts'], core.ordered_ensemble(logits) > cuts['ensemble_cut']))
    require(baseline.tobytes() == saved.tobytes(), 'SAVED_CAL_HEAD_DECISION_PARITY')
    with np.load(prepared / 'normalizer.npz', allow_pickle=False) as data:
        normalizer = data['mean'].copy(), data['scale'].copy()
    feature_array = np.load(features, mmap_mode='r', allow_pickle=False)
    q_array = np.load(prepared / 'LEARN_q.npy', mmap_mode='r', allow_pickle=False)
    attacks_ix = np.flatnonzero([r['label'] == 1 for r in cal_rows])
    normals_ix = np.flatnonzero([r['label'] == 0 for r in cal_rows])
    require(len(attacks_ix) == 115672 and len(normals_ix) == 33147, 'FULL_CAL_CLASSES')
    attacks, normals = [cal_rows[i] for i in attacks_ix], [cal_rows[i] for i in normals_ix]
    feature_kwargs = dict(feature_uids=[r['uid'] for r in attacks], q_uids=[r['uid'] for r in attacks],
                          normal_feature_uids=[r['uid'] for r in normals], normal_q_uids=[r['uid'] for r in normals])
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    write(output / 'INPUT_SEAL.json', initial)
    try:
        summaries = {}
        for arm, rr, arrays in (('R-B2', old_rows, old_bank), ('R-DENSE', dense_rows, dense_bank)):
            write(output / 'status.json', dict(status='RUNNING', stage='SOURCE_CAL_' + arm, retries=0))
            bank = RecordingBank(core.ReferenceBank(rr, arrays['e3'], arrays['q14'], normalizer,
                feature_uids=arrays['uid'].tolist(), q_uids=arrays['uid'].tolist(), allowed_partitions={'LEARN'})
                )
            preparation = budget.prepare_budget_calibration(attacks, logits[attacks_ix], cuts['cuts'], cuts['ensemble_cut'],
                scales['scales'], bank, IndexedMatrix(feature_array, cal_indices[attacks_ix], slice(0, 768)),
                IndexedMatrix(q_array, cal_indices[attacks_ix]), geometry, cal_normal_rows=normals,
                normal_logits=logits[normals_ix], normal_e3=IndexedMatrix(feature_array, cal_indices[normals_ix], slice(0, 768)),
                normal_q14=IndexedMatrix(q_array, cal_indices[normals_ix]), **feature_kwargs)
            target = output / arm
            target.mkdir()
            write(target / 'PREPARATION.json', preparation)
            selections = {str(e): budget.select_budget_lambda(preparation, e) for e in budget.EPSILON_PP_CANDIDATES}
            legacy = preparation['legacy_protection']
            support = np.zeros(len(cal_rows))
            support[normals_ix] = bank.normal_own['support']
            lookup = {(r['partition'], r['device'], r['protocol']): j
                      for j, r in enumerate(bank.attack_matrix['roster'])}
            for i, row in enumerate(attacks):
                j = lookup.get((row['partition'], row['device'], row['protocol']))
                if j is not None:
                    support[attacks_ix[i]] = bank.attack_matrix['support'][i, j]
            corrected_legacy = core.apply_correction(logits, support, scales['scales'], legacy['selected_lambda'])
            corrected_zero = core.apply_correction(logits, support, scales['scales'], selections['0.0']['selected_lambda'])
            require(corrected_legacy.tobytes() == corrected_zero.tobytes(), 'EPS0_SAME_ENVIRONMENT_FULL_CAL_BYTES')
            zero_decisions = np.column_stack((corrected_zero > cuts['cuts'],
                core.ordered_ensemble(corrected_zero) > cuts['ensemble_cut']))
            score_sha = hashlib.sha256(corrected_zero.tobytes()).hexdigest()
            decision_sha = hashlib.sha256(zero_decisions.tobytes()).hexdigest()
            parity = dict(epsilon_zero_full_CAL_same_environment_legacy_bytes_equal=True,
                          corrected_logits_sha256=score_sha, corrected_decisions_sha256=decision_sha)
            if arm == 'R-B2':
                frozen = read(calibration / 'protection.json')
                require(legacy['selected_lambda'] == frozen['selected_lambda'], 'R_B2_ORIGINAL_LAMBDA_PARITY')
                for new, old in zip(legacy['candidates'], frozen['candidates']):
                    for name in ('lambda_value', 'passes', 'new_miss_count', 'new_miss_pair_count',
                                 'newly_missed_uids', 'cap_reachable_detected_attack_count'):
                        require(new[name] == old[name], 'R_B2_ORIGINAL_PROTECTION_PARITY:' + name)
                prior = read(root / 'runs/diagnostics_c2b_c4_step2_v1_20261025/source_cal/RESULT.json')
                parity['prior_local_environment_logits_bytes_equal_report_only'] = score_sha == prior['parity']['CAL_corrected_logits_sha256']
                parity['prior_local_environment_decisions_bytes_equal'] = decision_sha == prior['parity']['CAL_corrected_decisions_sha256']
                require(parity['prior_local_environment_decisions_bytes_equal'], 'R_B2_PRIOR_SCIENTIFIC_DECISIONS_CHANGED')
            write(target / 'EPS0_PARITY.json', parity)
            for epsilon, selection in selections.items():
                write(target / ('EPSILON_' + epsilon.replace('.', 'p') + '.json'), selection)
            summaries[arm] = dict(reference_rows=len(rr), selections=selections,
                zero_epsilon_matches_this_bank_legacy=selections['0.0']['epsilon_zero_matches_legacy_selection'], parity=parity)
        require(all(sha(path) == checksum for path, checksum in initial.items()), 'IMMUTABLE_INPUT_CHANGED')
        result = dict(status='SOURCE_CAL_COMPLETE', created_utc=datetime.now(timezone.utc).isoformat(),
            elapsed_seconds=time.monotonic()-started, arms=summaries, no_AB_loaded=True, no_model_forward=True,
            no_FIT_geometry_scale_cut_fit=True, true_dense_reference_rows=4728, optimizer_updates=0, retries=0,
            scientific_fail_must_not_abort_registered_target_matrix=True,
            matrix_execution_ready=False, matrix_blocker='REQUIRES_SEPARATE_VERIFIED_MATRIX_MANIFEST',
            adaptation='new HPC chain; prior seal comparisons resolve canonical-view symlinks')
        write(output / 'RESULT.json', result)
        write(output / 'status.json', dict(status='COMPLETE', stage='SOURCE_CAL_COMPLETE', retries=0))
    except BaseException as exc:
        write(output / 'status.json', dict(status='EXCEPTION_STOP', error_type=type(exc).__name__, error=str(exc), retries=0))
        raise


if __name__ == '__main__':
    main()
