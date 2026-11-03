"""Seal the user-approved engineering recovery; run no scientific computation."""
import ast
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT/'runs/history_sample_coverage_c4_header_repair_v1_20261101'
AUDIT = ROOT/'runs/history_sample_coverage_c4_resume_audit_20261102'


def read(p):
    return json.loads(p.read_text(encoding='utf-8-sig'))


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def write(p, v):
    p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    assert not (HERE/'BUDGET_SEAL_RECEIPT.json').exists(), 'SEAL_ONCE'
    approval = read(HERE/'EXECUTION_AUTHORIZATION.json')
    assert approval['additional_wall_seconds'] == 18000 and approval['user_approved']
    original = read(SOURCE/'EXECUTION_CARD.json')
    card = copy.deepcopy(original)
    report = read(AUDIT/'REMOTE_REPORT.json')
    state = read(ROOT/'runs/history_sample_coverage_c4_preflight_repair_20261102/STATE_RECEIPT.json')['STATUS.json']
    assert state['error'] == 'WALL_SECONDS_LIMIT' and state['pairs'] == 0
    assert report['files']['history/NETATMO/PREPARE_RESULT.json']['sha256']
    card['limits'].update(total_wall_seconds=46861, encoded=37442)
    r = card['recovery']
    r.update(prior_wall_seconds_charged=28861, remaining_seconds=18000,
             additional_wall_seconds=18000, prior_encoded_rows_charged=25154,
             reused_encoded_rows=20480, new_encoded_rows=12288,
             prepared_source_package=SOURCE.relative_to(ROOT).as_posix(),
             prepared_source_card_sha256=sha(SOURCE/'EXECUTION_CARD.json'),
             prepared_source_status_sha256=report['files']['STATUS.json']['sha256'],
             prepared_source_receipt_sha256=report['files']['history/NETATMO/PREPARE_RESULT.json']['sha256'],
             prepared_source_job='180670',
             replay_netatmo_snapshot_pass_from_frame_one=False,
             reuse_netatmo_complete_preparation=True,
             discard_legacy_unpersisted_netatmo_E3_rows=4658,
             durable_new_E3_batches=True)
    r['prior_attempts'].append(dict(job='180670', observed_seconds=state['elapsed_seconds'], charged_seconds=4327))
    r['prior_wall_seconds_observed'] += state['elapsed_seconds']
    assert sum(a['charged_seconds'] for a in r['prior_attempts']) == 28861
    card['authorization_sha256'] = sha(HERE/'EXECUTION_AUTHORIZATION.json')
    card['budget_amendment'] = dict(original_wall_limit_seconds=28800, additional_wall_seconds=18000,
                                    retained_prior_charged_seconds=28861,
                                    new_total_wall_ceiling_seconds=46861,
                                    original_encoded_cap=36864, amended_encoded_cap=37442,
                                    extra_charged_E3_allowance=578, no_automatic_retry=True)
    config = read(HERE/'config/EXECUTION.json')
    config['assets_manifest'] = str(HERE/'config/ASSETS.json')
    write(HERE/'config/EXECUTION.json', config)
    import run
    from hnr.common import digest
    assert digest(run.semantic(config)) == original['config_semantic_sha256'], 'SCIENCE_CONFIG_UNCHANGED'
    for path in HERE.glob('*.py'):
        ast.parse(path.read_text(encoding='utf-8'))
    script = (SOURCE/'hpc/run_encode.slurm').read_text(encoding='utf-8')
    script = script.replace('history_sample_coverage_c4_header_repair_v1_20261101', HERE.name)
    script = script.replace('#SBATCH --time=01:11:06', '#SBATCH --time=05:00:00')
    assert '#SBATCH --time=05:00:00' in script
    (HERE/'hpc/run_encode.slurm').write_text(script, encoding='utf-8', newline='\n')
    names = sorted(set(original['code_sha256']) | {p.relative_to(HERE).as_posix()
              for p in [*HERE.glob('*.py'), *HERE.glob('hnr/*.py')]}
              | {'EXECUTION_AUTHORIZATION.json'})
    card['code_sha256'] = {n:sha(HERE/n) for n in names}
    unchanged = {k:v for k,v in original.items() if k not in ('code_sha256', 'recovery', 'limits')}
    assert all(card[k] == v for k,v in unchanged.items()), 'FROZEN_SCIENTIFIC_FIELDS'
    write(HERE/'COPIED_PRIOR_CARD.json', read(HERE/'EXECUTION_CARD.json'))
    write(HERE/'EXECUTION_CARD.json', card)
    (HERE/'EXECUTION_CARD.json.sha256').write_text(sha(HERE/'EXECUTION_CARD.json')+'  EXECUTION_CARD.json\n', encoding='utf-8')
    run.verify('encode')
    receipt = dict(status='BUDGET_AMENDMENT_SEALED', execution_card_sha256=sha(HERE/'EXECUTION_CARD.json'),
                   user_approved=True, prior_charged_seconds=28861, additional_wall_seconds=18000,
                   cumulative_wall_ceiling_seconds=46861, cumulative_charged_E3_cap=37442,
                   source_card_sha256=sha(SOURCE/'EXECUTION_CARD.json'),
                   scientific_fields_unchanged=True, new_model_forwards=0, new_distance_pairs=0,
                   uploaded=False, submitted=False)
    write(HERE/'BUDGET_SEAL_RECEIPT.json', receipt)
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
