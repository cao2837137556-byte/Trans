"""Prepare an explicitly UNAUTHORIZED A/B stage proposal from accepted outputs.

Only hashes, reference metadata/arrays and saved source selections are inspected.
Target score arrays are never opened, support is not computed, and source seals
are preserved byte for byte. No production authorization is created.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORIGINAL = ROOT / 'runs/dense_reference_matrix_v1_20261027'
RETRIEVAL = ROOT / 'runs/dense_reference_batch_repair_deployment_20261027/result_retrieval_r2_20261027'
SCIENCE = RETRIEVAL / 'evidence179602/science'
ENC, CAL = SCIENCE / 'encode', SCIENCE / 'source_cal'
REMOTE_SCIENCE = '/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_batch_repair_v1_20261027_runtime/job_179602/science/'
REMOTE_PACKAGE = '/public/home/jiangxinwei.zr/work/paper04/runs/dense_reference_matrix_v1_20261027/'
SCOPE = 'AB_DENSE_STAGE_PENDING_THIRD_POOL'
THIRD = 'CIC_THREE_DEVICE_REGRESSION_CONSUMED'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False)
        stream.write('\n')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def require(condition, reason):
    if not condition:
        raise RuntimeError(reason)


def pins(value):
    if isinstance(value, dict):
        if isinstance(value.get('path'), str) and isinstance(value.get('sha256'), str):
            yield value
        for child in value.values():
            yield from pins(child)
    elif isinstance(value, list):
        for child in value:
            yield from pins(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', default='preparation')
    args = parser.parse_args()
    output = (HERE / args.output).resolve()
    require(output.is_relative_to(HERE) and output != HERE, 'PREPARATION_OUTPUT_SCOPE')
    require(not output.exists(), 'PREPARATION_ALREADY_EXISTS_NEVER_OVERWRITE')
    checks = {}
    acceptance = read(RETRIEVAL / 'RESULT_ACCEPTANCE.json')
    manifest_path = RETRIEVAL / 'manifest.json'
    require(sha(manifest_path) == acceptance['manifest_sha256'] ==
        '8ff70fedb1e4c0892acd066c937a7aeed9d3c0b38ccd22956862c50c3a67b72d',
        'ACCEPTED_RETRIEVAL_MANIFEST_IDENTITY')
    accepted_files = {entry['path']: entry for entry in read(manifest_path)['files']}
    evidence = RETRIEVAL / 'evidence179602'

    def check(path, expected):
        path = Path(path).resolve()
        require(path.is_file() and path.is_relative_to(ROOT), 'MISSING_OR_OUTSIDE_INPUT:' + str(path))
        if path.is_relative_to(evidence):
            accepted = accepted_files.get(path.relative_to(evidence).as_posix())
            require(accepted is not None and accepted['sha256'] == expected and
                accepted['bytes'] == path.stat().st_size, 'NOT_ORIGINAL_ACCEPTED_OUTPUT:' + str(path))
        if path.as_posix() not in checks:
            require(sha(path) == expected, 'INPUT_SHA256:' + str(path))
            checks[path.as_posix()] = dict(path=path.relative_to(ROOT).as_posix(),
                bytes=path.stat().st_size, sha256=expected)
        else:
            require(checks[path.as_posix()]['sha256'] == expected, 'CONTRADICTORY_PIN')
        return path

    def derived(path, **extra):
        path = Path(path).resolve()
        checksum = sha(path)
        check(path, checksum)
        return dict(path=path.as_posix(), sha256=checksum, derived_runtime=True, **extra)

    require(acceptance['status'] == 'PASS' and acceptance['job_id'] == '179602' and
        acceptance['original104_byte_exact'] is True, 'ACCEPTED_ENCODING_REQUIRED')
    consumed = ['encode/RESULT.json', 'encode/ORIGINAL104_PARITY.json',
        'source_cal/INPUT_SEAL.json', 'source_cal/RESULT.json']
    consumed += [f'source_cal/{arm}/{name}' for arm in ('R-B2', 'R-DENSE')
        for name in ('PREPARATION.json', 'EPS0_PARITY.json')]
    consumed += [f'encode/banks/{pool}/{name}' for pool in ('SOURCE_REFS', 'CIC_DEV', 'UNSW_DEV')
        for name in ('bank.npz', 'receipt.json', 'references.jsonl.gz')]
    for relative in consumed:
        path = SCIENCE / relative
        expected = accepted_files['science/' + relative]['sha256']
        check(path, expected)
    for name, key in (('analysis/INDEPENDENT_AUDIT.json', 'independent_audit_sha256'),
                      ('analysis/SOURCE_NORMAL_READOUT.json', 'source_normal_readout_sha256')):
        check(RETRIEVAL / name, acceptance[key])
    template_path = ORIGINAL / 'config/MATRIX_TEMPLATE.json'
    original_template_sha = sha(template_path)
    template = read(template_path)
    require(template['schema'] == 'dense-reference-matrix-input-v1', 'ORIGINAL_TEMPLATE_SCHEMA')
    third = [p for p in template['pools'] if p['pool_id'] == THIRD]
    require(len(third) == 1 and third[0]['mode'] == 'BLOCKED_MISSING_FROZEN_BASE_B2',
        'MISSING_THIRD_POOL_MUST_BE_RECORDED')
    result = copy.deepcopy(template)
    result['pools'] = [p for p in result['pools'] if p['pool_id'] in ('CIC_DEV', 'UNSW_DEV')]
    require([p['pool_id'] for p in result['pools']] == ['CIC_DEV', 'UNSW_DEV'], 'EXACT_AB_POOL_ORDER')
    for pin in pins(result):
        check(ROOT / pin['path'], pin['sha256'])

    # Preserve the production INPUT_SEAL; record explicit, checked aliases.
    seal_path = CAL / 'INPUT_SEAL.json'
    seal_sha = sha(seal_path)
    alias_rows = []
    for remote, checksum in read(seal_path).items():
        if remote.startswith(REMOTE_SCIENCE + 'readonly_view/'):
            local = ROOT / remote[len(REMOTE_SCIENCE + 'readonly_view/'):]
        elif remote.startswith(REMOTE_SCIENCE):
            local = SCIENCE / remote[len(REMOTE_SCIENCE):]
        elif remote.startswith(REMOTE_PACKAGE):
            local = ORIGINAL / remote[len(REMOTE_PACKAGE):]
        else:
            raise RuntimeError('UNREGISTERED_SOURCE_SEAL_PATH:' + remote)
        local = check(local, checksum)
        alias_rows.append(dict(original_path=remote, local_path=local.as_posix(), sha256=checksum))
    require(len(alias_rows) == 19 and sha(seal_path) == seal_sha, 'SOURCE_SEAL_CHANGED_OR_INCOMPLETE')
    encoding = read(ENC / 'RESULT.json')
    source = read(CAL / 'RESULT.json')
    require(encoding['status'] == 'COMPLETE' and encoding['mode'] == 'encode' and
        encoding['target_evaluation'] is False and encoding['no_training'] is True and
        source['status'] == 'SOURCE_CAL_COMPLETE' and source['no_AB_loaded'] is True,
        'PRODUCTION_PREFIX_REQUIRED')
    encoder_sha = sha(ORIGINAL / 'vendor/encoding_v2/SHA256SUMS')
    require(encoding['package_sha256'] == template.get('encoding_package_sha256', encoder_sha)
        == encoder_sha, 'ENCODER_PACKAGE_IDENTITY')
    parity = read(ENC / 'ORIGINAL104_PARITY.json')
    require(parity['original104_exact_bytes'] is True and parity['mismatch_count'] == 0,
        'ORIGINAL104_REQUIRED')
    result['source_cal_result'] = derived(CAL / 'RESULT.json')
    result['source_preparations'] = {}
    for arm in ('R-B2', 'R-DENSE'):
        result['source_preparations'][arm] = derived(CAL / arm / 'PREPARATION.json')
        require(read(CAL / arm / 'EPS0_PARITY.json')[
            'epsilon_zero_full_CAL_same_environment_legacy_bytes_equal'] is True,
            'SOURCE_EPS0_BYTE_PARITY:' + arm)
    for pool in result['pools']:
        original = pool['dense_bank']
        bank_dir = ENC / 'banks' / pool['pool_id']
        receipt = read(bank_dir / 'receipt.json')
        source_bound_bank = [entry for entry in encoding['banks'] if entry['name'] == pool['pool_id']]
        require(len(source_bound_bank) == 1 and
            source_bound_bank[0]['bank_sha256'] == receipt['bank_sha256'] and
            source_bound_bank[0]['rows'] == receipt['rows'], 'ENCODING_RESULT_BANK_BINDING')
        require(receipt['status'] == 'COMPLETE' and receipt['frozen_selection'] is True and
            receipt['existing_vectors_unchanged'] is True and receipt['reselection'] is False and
            receipt['rows'] == original['expected_rows'], 'DENSE_RECEIPT:' + pool['pool_id'])
        check(bank_dir / 'bank.npz', receipt['bank_sha256'])
        require(receipt['metadata_sha256'] == original['rows']['sha256'], 'DENSE_METADATA_IDENTITY')
        check(bank_dir / 'references.jsonl.gz', receipt['metadata_sha256'])
        bank_pin = derived(bank_dir / 'bank.npz', uid_key='uid')
        original.update(status='COMPLETE_DERIVED_ENCODING', e3=dict(bank_pin, key='e3'),
            q14=dict(bank_pin, key='q14'), producer_receipt=derived(bank_dir / 'receipt.json'),
            feature_uid_sha256=original['expected_ordered_uid_sha256'],
            q_uid_sha256=original['expected_ordered_uid_sha256'])

    result.update(schema='dense-reference-ab-stage-input-v1', root=ROOT.as_posix(),
        evaluation_scope=SCOPE, status='CANDIDATE_AWAITING_PROTOCOL_AND_CLOUD_APPROVAL',
        synthetic_only=False, stage_matrix_ready=True, full_matrix_ready=False,
        original_registered_matrix_complete=False, supplement_encoding_complete=True,
        dense_source_cal_complete=True, derived_runtime_roots=[ENC.as_posix(), CAL.as_posix()],
        third_pool_deferred=dict(pool_id=THIRD, status='DEFERRED_MISSING_FROZEN_BASE_B2',
            original_registered_matrix_complete=False,
            reason='No frozen historical third-pool BASE/B2/receipt; explicitly proposed stage only.'),
        blockers=['PROTOCOL_SCOPE_AMENDMENT_CONFIRMATION_REQUIRED', 'NEW_CLOUD_EXECUTION_APPROVAL_REQUIRED'],
        preparation=dict(original_template_path=template_path.relative_to(ROOT).as_posix(),
            original_template_sha256=original_template_sha, original_scientific_parameters_changed=False,
            source_seal_sha256=seal_sha, source_seal_bytes_modified=False, original_pool_specs_replaced=False,
            accepted_retrieval_manifest_sha256=sha(RETRIEVAL / 'manifest.json'),
            target_scores_loaded=False, distance_support_calls=0, model_forwards=0, training_updates=0,
            target_evaluations=0))
    require(sha(template_path) == original_template_sha, 'ORIGINAL_TEMPLATE_CHANGED')
    budget = read(ORIGINAL / 'preparation/PAIR_BUDGET.json')
    pair_counts = {pool: budget['pools'][pool]['total_distance_pairs'] for pool in ('CIC_DEV', 'UNSW_DEV')}
    require(sum(pair_counts.values()) == 912302797, 'FROZEN_PAIR_BUDGET_CHANGED')
    manifest_path = output / 'MATRIX_CANDIDATE_LOCAL.json'
    write(manifest_path, result)
    write(output / 'SOURCE_SEAL_ALIASES.json', dict(original_seal_sha256=seal_sha,
        original_seal_bytes_modified=False, aliases=alias_rows))
    files = sorted(checks.values(), key=lambda p:p['path'])
    write(output / 'INPUT_READINESS.json', dict(status='PASS_LOCAL_SHA_IDENTITY_ONLY',
        candidate_manifest_sha256=sha(manifest_path), source_cal_result_sha256=sha(CAL / 'RESULT.json'),
        files=files, file_count=len(files), total_input_bytes=sum(p['bytes'] for p in files),
        distance_pairs=pair_counts, total_distance_pairs=sum(pair_counts.values()),
        source_seal_checked_files=len(alias_rows), original_registered_matrix_complete=False,
        consumed_accepted_science_files=len(consumed),
        target_evaluations=0, target_score_arrays_opened=0, model_forwards=0,
        training_updates=0, new_CAL_runs=0, new_remote_operations=0,
        authorization_status='NOT_AUTHORIZED_CANDIDATE_ONLY',
        remote_target_asset_presence='NOT_CHECKED',
        created_utc=datetime.now(timezone.utc).isoformat()))
    print(json.dumps(dict(status='PASS_LOCAL_SHA_IDENTITY_ONLY', checked_files=len(files),
        total_bytes=sum(p['bytes'] for p in files), target_evaluations=0,
        manifest_sha256=sha(manifest_path)), ensure_ascii=False))


if __name__ == '__main__':
    main()
