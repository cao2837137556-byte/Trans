"""Bind completed encoding/source-CAL outputs to a frozen metadata template.

Only future, derived file pins are filled. Frozen metadata, scientific settings,
donors and original asset SHA values remain unchanged. No target scores/models
are loaded and no evaluation starts in this module.
"""
import argparse
import copy
import json
from pathlib import Path

import numpy as np

import matrix
import binding

require = matrix.require


def _derived(path, roots, **extra):
    path = Path(path).resolve()
    require(any(path.is_relative_to(r) for r in roots), 'DERIVED_INPUT_OUTSIDE_RUNTIME_ROOTS')
    require(path.is_file(), 'DERIVED_INPUT_MISSING:' + str(path))
    return dict(path=path.as_posix(), sha256=matrix.sha(path), derived_runtime=True, **extra)


def materialize_runtime(template_path, encoding_output_dir, source_cal_output_dir,
                        output_path, *, asset_root=None):
    template_path, output_path = Path(template_path).resolve(), Path(output_path).resolve()
    require(not output_path.exists(), 'RUNTIME_MANIFEST_ALREADY_EXISTS')
    template = matrix.read(template_path)
    require(template.get('schema') == matrix.SCHEMA and template.get('source_cal_result') is None and
            template.get('source_preparations') is None, 'UNMATERIALIZED_TEMPLATE_REQUIRED')
    root = Path(asset_root if asset_root is not None else template['root']).resolve()
    require(root.is_dir(), 'ASSET_ROOT_MISSING')
    enc, cal = Path(encoding_output_dir).resolve(), Path(source_cal_output_dir).resolve()
    require(enc.is_dir() and cal.is_dir() and enc != cal, 'DISTINCT_RUNTIME_OUTPUT_ROOTS_REQUIRED')
    roots = (enc, cal)
    inputs = matrix.Inputs(root, roots)
    encoding_result_pin = _derived(enc/'RESULT.json', roots)
    source_result_pin = _derived(cal/'RESULT.json', roots)
    encoding, source = inputs.json(encoding_result_pin), inputs.json(source_result_pin)
    require(encoding.get('status') == 'COMPLETE' and encoding.get('mode') == 'encode' and
            encoding.get('benchmark_features_must_not_be_used_for_production') is False and
            encoding.get('no_training') is True and encoding.get('target_evaluation') is False,
            'PRODUCTION_ENCODING_COMPLETE_REQUIRED')
    if template.get('encoding_package_sha256') is not None:
        require(encoding.get('package_sha256') == template['encoding_package_sha256'], 'ENCODING_PACKAGE_IDENTITY')
    original104 = inputs.json(_derived(enc/'ORIGINAL104_PARITY.json', roots))
    require(original104.get('original104_exact_bytes') is True and original104.get('mismatch_count') == 0,
            'ORIGINAL104_BYTE_GATE_REQUIRED')
    require(source.get('status') == 'SOURCE_CAL_COMPLETE' and source.get('no_AB_loaded') is True and
            source.get('no_model_forward') is True, 'SOURCE_CAL_COMPLETE_REQUIRED')
    source_seal = inputs.json(_derived(cal/'INPUT_SEAL.json', roots))
    encoding_pins = [(p, checksum) for p, checksum in source_seal.items()
                     if Path(p).resolve() == (enc/'RESULT.json').resolve()]
    require(len(encoding_pins) == 1 and encoding_pins[0][1] == encoding_result_pin['sha256'],
            'SOURCE_CAL_NOT_BOUND_TO_ENCODING_RESULT')
    for name, pin in template['calibration'].items():
        path = inputs.pin(pin)
        require(source_seal.get(str(path)) == pin['sha256'],
                'SOURCE_CAL_FIXED_PARAMETER_IDENTITY:' + name)
    for name, pin in template.get('source_assets', {}).items():
        path = inputs.pin(pin)
        require(source_seal.get(str(path)) == pin['sha256'],
                'SOURCE_CAL_FROZEN_SOURCE_ASSET_IDENTITY:' + name)
    # The CAL working points must have consumed this exact newly merged source
    # bank, rather than any other bank with coincidentally equal selected lambdas.
    source_bank_dir = enc/'banks/SOURCE_REFS'
    source_receipt = inputs.json(_derived(source_bank_dir/'receipt.json', roots))
    require(source_receipt.get('status') == 'COMPLETE' and source_receipt.get('frozen_selection') is True and
            source_receipt.get('reselection') is False, 'SOURCE_BANK_ENCODING_RECEIPT')
    for name, checksum_key in (('bank.npz', 'bank_sha256'), ('references.jsonl.gz', 'metadata_sha256')):
        pin = _derived(source_bank_dir/name, roots)
        path = inputs.pin(pin)
        require(source_receipt.get(checksum_key) == pin['sha256'] and
                source_seal.get(str(path)) == pin['sha256'], 'SOURCE_CAL_DENSE_BANK_IDENTITY:' + name)
    result = copy.deepcopy(template)
    result['source_cal_result'] = source_result_pin
    preparations = {}
    for arm in ('R-B2', 'R-DENSE'):
        preparations[arm] = _derived(cal/arm/'PREPARATION.json', roots)
        parity = inputs.json(_derived(cal/arm/'EPS0_PARITY.json', roots))
        require(parity.get('epsilon_zero_full_CAL_same_environment_legacy_bytes_equal') is True,
                'SOURCE_EPS0_BYTE_PARITY_REQUIRED:' + arm)
    matrix.source_workpoints(source, {arm: inputs.json(pin) for arm, pin in preparations.items()})
    result['source_preparations'] = preparations
    for pool in result['pools']:
        if pool['mode'] != 'DENSE_MATRIX':
            continue
        original = pool['dense_bank']
        require(original.get('status') == 'BLOCKED_SUPPLEMENT_ENCODING_REQUIRED' and original.get('e3') is None,
                'DENSE_TEMPLATE_STATE')
        selected = inputs.rows(original['rows'])
        uids = [r['uid'] for r in selected]
        require(len(uids) == original['expected_rows'] and matrix.core._uid_hash(uids) ==
                original['expected_ordered_uid_sha256'], 'FROZEN_SELECTED_UID_IDENTITY')
        binding.verify_wrong_plan(inputs.json(pool['wrong_plan']), pool['pool_id'], selected, pool['windows'])
        bank_dir = enc/'banks'/pool['pool_id']
        receipt_pin = _derived(bank_dir/'receipt.json', roots)
        receipt = inputs.json(receipt_pin)
        bank_pin = _derived(bank_dir/'bank.npz', roots, uid_key='uid')
        metadata_pin = _derived(bank_dir/'references.jsonl.gz', roots)
        require(receipt.get('status') == 'COMPLETE' and receipt.get('frozen_selection') is True and
                receipt.get('existing_vectors_unchanged') is True and receipt.get('reselection') is False and
                receipt.get('rows') == len(selected), 'DENSE_ENCODING_RECEIPT')
        require(receipt.get('bank_sha256') == bank_pin['sha256'] and
                receipt.get('metadata_sha256') == metadata_pin['sha256'] == original['rows']['sha256'],
                'DENSE_ENCODING_RECEIPT_HASH')
        encoded_rows = inputs.rows(metadata_pin)
        require(encoded_rows == selected, 'DENSE_ENCODED_METADATA_CHANGED')
        with np.load(inputs.pin(original['q14']), allow_pickle=False) as frozen:
            require(frozen[original['q14'].get('uid_key', 'uid')].tolist() == uids, 'FROZEN_DENSE_Q_UIDS')
            frozen_q = frozen[original['q14'].get('key', 'q14')].copy()
        with np.load(inputs.pin(bank_pin), allow_pickle=False) as saved:
            require(saved['uid'].tolist() == uids, 'ENCODED_DENSE_BANK_UID_ORDER')
            e, q = saved['e3'], saved['q14']
            require(e.shape == (len(selected), 768) and q.shape == (len(selected), 14) and
                    e.dtype == q.dtype == np.float32 and np.isfinite(e).all() and np.isfinite(q).all() and
                    np.all((q >= 0) & (q <= 1)), 'ENCODED_DENSE_BANK_SCHEMA')
            require(q.dtype == frozen_q.dtype and q.tobytes() == frozen_q.tobytes(), 'FROZEN_DENSE_Q_BYTES_CHANGED')
        # Keep the exact frozen metadata pin, UID hash, and all donor/window
        # fields; replace only missing E3 and the verified merged q14 asset.
        pool['dense_bank'].update(status='COMPLETE_DERIVED_ENCODING',
            e3=dict(bank_pin, key='e3'), q14=dict(bank_pin, key='q14'), producer_receipt=receipt_pin,
            feature_uid_sha256=matrix.core._uid_hash(uids), q_uid_sha256=matrix.core._uid_hash(uids))
    inputs.immutable()
    result.update(root=root.as_posix(), synthetic_only=False,
        status='RUNTIME_INPUTS_MATERIALIZED', supplement_encoding_complete=True, dense_source_cal_complete=True,
        derived_runtime_roots=[p.as_posix() for p in roots],
        materialization=dict(template_path=template_path.as_posix(), template_sha256=matrix.sha(template_path),
            encoding_result=encoding_result_pin, source_cal_result=source_result_pin,
            frozen_scientific_fields_changed=False, metadata_donor_selection_repeated_only_for_identity_check=True,
            target_scores_loaded=False, model_forwards=0, training_updates=0))
    result['full_matrix_ready'] = not any(p['mode'].startswith('BLOCKED') for p in result['pools'])
    result['blockers'] = [b for b in result.get('blockers', []) if b not in
                         ('SUPPLEMENT_E3_AND_ORIGINAL104_BYTE_GATE_PENDING', 'TRUE_DENSE_SOURCE_CAL_PENDING')]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matrix.write(output_path, result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--template', required=True)
    p.add_argument('--encoding-output', required=True)
    p.add_argument('--source-cal-output', required=True)
    p.add_argument('--asset-root', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    materialize_runtime(args.template, args.encoding_output, args.source_cal_output,
                        args.output, asset_root=args.asset_root)
