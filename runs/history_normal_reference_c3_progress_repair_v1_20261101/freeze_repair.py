"""Seal a user-authorized technical restart, keeping the failed attempt intact."""
from common import *


def main():
    need(not (HERE / 'EXECUTION_CARD.json').exists(), 'REPAIR_ALREADY_FROZEN')
    parent = HERE.parent / 'history_normal_reference_c3_small_bank_v1_20261101'
    card = read(parent / 'EXECUTION_CARD.json')
    for name, digest in card['code_sha256'].items():
        need(sha(parent / name) == digest, 'ORIGINAL_CODE_CHANGED')
    runtime = read(parent / 'EVALUATE_RUNTIME.json')
    need(runtime['status'] == 'TECHNICAL_FAILURE_NO_RETRY', 'PARENT_NOT_TECHNICAL_FAILURE')
    need(not (parent / 'output/RESULT.json').exists() and not (parent / 'output/ab').exists(), 'NO_PRIOR_AB_RESULT')
    log = (parent / 'EVALUATE.log').read_text(encoding='utf-8')
    need('PermissionError: [WinError 5]' in log and 'STATUS.json.tmp' in log, 'EXPECTED_DISPLAY_FAILURE')
    reused = {}
    for name in ('prepared', 'retrieved'):
        for path in (parent / name).rglob('*'):
            if path.is_file():
                rel = path.relative_to(parent).as_posix()
                need(sha(HERE / rel) == sha(path), 'REUSED_ASSET_CHANGED:' + rel)
                reused[rel] = sha(path)
    for name in ('INPUT_MANIFEST.json', 'ENCODE_REQUEST.json'):
        need(sha(HERE / name) == sha(parent / name), 'FROZEN_REQUEST_CHANGED')
    plan = read(parent / 'output/PAIR_PLAN.json')
    # Reserve the *entire* aborted plan, not just the last logged chunk. This
    # conservatively covers the chunk whose progress write failed.
    previous_upper_bound = plan['pairs']
    need(previous_upper_bound * 2 <= LIMITS['distance_pairs'], 'CUMULATIVE_PAIRS_EXCEEDED')
    evidence = {name: sha(parent / name) for name in (
        'EXECUTION_CARD.json', 'INPUT_MANIFEST.json', 'ENCODE_REQUEST.json',
        'EVALUATE.log', 'EVALUATE_RUNTIME.json', 'EVALUATE_GUARD_ATTEMPT.json',
        'output/AB_ATTEMPT.json', 'output/DEV_GATE.json', 'output/PAIR_PLAN.json')}
    evidence.update({name: sha(parent / name) for name in card['code_sha256']})
    evidence.update(reused)
    card['technical_recovery'] = dict(
        parent_directory=parent.relative_to(ROOT).as_posix(),
        user_instruction='修复然后重新提交。',
        reason='Windows STATUS.json atomic replacement denied; no candidate metrics or decisions saved.',
        evaluation_attempt=2, new_scientific_candidate=False, new_HPC_jobs=0,
        encoder_execution_card_sha256=sha(parent / 'EXECUTION_CARD.json'),
        previous_distance_pairs_upper_bound=previous_upper_bound,
        expected_cumulative_distance_pairs_upper_bound=previous_upper_bound * 2,
        previous_elapsed_seconds=runtime['elapsed_seconds'],
        parent_evidence_sha256=evidence, reused_assets_sha256=reused,
        method_parameters_unchanged=True, original_attempt_preserved=True)
    card['code_sha256'] = {p.name: sha(p) for p in [*HERE.glob('*.py'), *HERE.glob('*.slurm')]}
    card['stages'] = ['reuse_verified_preparation_and_HPC_encoding', 'saved_input_AB_local_recovery_once', 'verify_and_freeze']
    write(HERE / 'EXECUTION_CARD.json', card, exclusive=True)
    (HERE / 'EXECUTION_CARD.json.sha256').write_text(sha(HERE / 'EXECUTION_CARD.json') + '  EXECUTION_CARD.json\n', encoding='utf-8')
    verify_contract()
    print(json.dumps(dict(status='REPAIR_FROZEN', previous_compute_reservation=previous_upper_bound,
        cumulative_pair_upper_bound=previous_upper_bound * 2, reused_files=len(reused),
        execution_card_sha256=sha(HERE / 'EXECUTION_CARD.json'))), flush=True)


if __name__ == '__main__':
    main()
