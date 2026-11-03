"""Prepare the fixed AB evaluation scope without opening historical report data.

Only the explicit ALLOWED files may be hashed/read. Historical report artifacts
are inventoried with stat and their recorded SHA256SUMS entries, never opened.
No numerical packages, model deserialization, feature reads, raw replay or inference.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = 'runs/frontend_paired_train_v3_20260910/'
META = 'runs/frontend_paired_metadata_v3_20260909/'
IMPL = 'runs/frontend_paired_train_implementation_v3_20260910/'
OLD = 'runs/.issue27ckda_d1_representation_probe_v1_2026-08-14_localwin_cpu.stage/'
OUTPUT = 'runs/frontend_expanded_eval_scope_v1_20260910'
HEAD = '4b28747b09480471e2bac1beb3a9badf27280efb'
ALLOWED = {
    RUN + 'candidate_AB.pt': 'a9e8e0c6aa50a25fe589d1733a9e9d788f380db64e90e8df71b3edde389ed325',
    RUN + 'candidate_AB.receipt.json': 'c9653d81b3dd986ba39de09474ef369777b9549ca77e8b3fbee65d71f284a958',
    RUN + 'check_predictions.json': '477d0530b0586cd11ce9bf355efa2f635074b09690aba15d0322d9c794166f68',
    RUN + 'postfit_predictions.json': '090cae3378fe0a9264b140a4a163fd3c4420e8d050f66dd57578025c6b1e1a46',
    META + 'membership.csv': '3766778032f9317f471939434868ac28b39cf0c88728130e42679f4f0c990418',
    IMPL + 'execution_config.json': '4113910a8d9493db640c40a3e1c04b78b50740e819a59820682507aa75cff140',
    'repo/ood/issue27frontend_paired_train_model_v1.py': '970028cdef7ff9f0098930e6d378a3e517c7d47b95105223b9120361e58d8d71',
    # This is a checksum catalog, not any report payload.
    OLD + 'SHA256SUMS': None,
}
REPORT_REFERENCES = {
    'ckda_d1_report_plan.csv': '3b97498c505cea5c646e91ecf247972926eb8c8fe4a6c51ef61a17e940a93c70',
    'ckda_d1_report_target_metadata.csv': '628c542108b4b582e74cd6ed0e5474a5f69225bd6a7c054200998d7448bfe65e',
    'ckda_d1_report_scores.csv.gz': '7ed1c0e9ebd0cbfc95669a064dcf1f57dd343fc4106611216575232432a0e6f9',
}
REPORT_ROLES = {
    'support_val': 69, 'same_file_query': 2486, 'future_query': 131391,
    'sealed_final_attack': 110104, 'ood_val': 3000,
    'sealed_final_ood': 3000, 'aux_report': 9000, 'ood_stress': 3000,
}
POOLS = [
    {'pool': 'GLOBAL_ATTACK_PRESERVATION', 'targets': 244050, 'kind': 'attack',
     'historical_roles': 'support_val;same_file_query;future_query;sealed_final_attack'},
    {'pool': 'iotsim-hydraulic-system', 'targets': 3000, 'kind': 'benign_ood', 'historical_roles': 'ood_val'},
    {'pool': 'iotsim-ip-camera-street', 'targets': 3000, 'kind': 'benign_ood', 'historical_roles': 'sealed_final_ood'},
    {'pool': 'iotsim-predictive-maintenance', 'targets': 9000, 'kind': 'benign_ood', 'historical_roles': 'aux_report'},
    {'pool': 'iotsim-stream-consumer', 'targets': 3000, 'kind': 'benign_ood', 'historical_roles': 'ood_stress'},
]


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class Reader:
    def __init__(self, root):
        self.root, self.ledger = root, []

    def read(self, relative):
        require(relative in ALLOWED, 'NOT_IN_PREOPEN_READ_ALLOWLIST: ' + relative)
        path = self.root / relative
        require(path.resolve().is_relative_to(self.root.resolve()), 'PATH_ESCAPE')
        raw = path.read_bytes()
        actual = sha(raw)
        expected = ALLOWED[relative]
        require(expected is None or actual == expected, 'INPUT_HASH_DRIFT: ' + relative)
        self.ledger.append({'path': relative, 'bytes': len(raw), 'sha256': actual})
        return raw


def summarize_id(membership, fit, check):
    """Reuse sealed AB outcomes; never repeat their model forward."""
    wanted = {r['uid']: r for r in membership if r['uid'].startswith('id_calib:')}
    require(len(wanted) == 809, 'ID_COUNT_NOT_809')
    result = []
    for role, predictions, total in (('train', fit, 15073), ('check', check, 3193)):
        by_uid = {r['uid']: r for r in predictions}
        require(len(by_uid) == len(predictions) == total, 'PREDICTION_DUPLICATE_OR_COUNT')
        require(set(by_uid) == {r['uid'] for r in membership if r['new_role'] == role}, 'V3_MEMBERSHIP_JOIN')
        part = []
        for uid, row in wanted.items():
            if row['new_role'] != role:
                continue
            p = by_uid[uid]
            require(int(row['label']) == p['label'] == 0, 'ID_NOT_BENIGN')
            require(p['context_key'] == row['context_key'] and p['source_group'] == row['source_group'], 'ID_LINEAGE')
            require(p['hard'] in (0, 1) and p['hard'] == int(p['logit'] >= 0), 'HARD_RULE')
            part.append(p)
        result.append({'role': role, 'targets': len(part),
                       'contexts': len({p['context_key'] for p in part}),
                       'sources': len({p['source_group'] for p in part}),
                       'false_alarms': sum(p['hard'] for p in part),
                       'evidence': 'EXISTING_V3_FIT' if role == 'train' else 'EXISTING_V3_EXPOSED_CHECK'})
    require(sum(r['targets'] for r in result) == 809, 'ID_CONSERVATION')
    return result


def json_write(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def build(root):
    getgit = lambda *args: subprocess.check_output(['git', *args], cwd=str(root), text=True).strip()
    require(getgit('rev-parse', 'HEAD') == HEAD, 'HEAD_DRIFT')
    require(getgit('branch', '--show-current') == 'codex/exp-mainline', 'BRANCH_DRIFT')
    reader = Reader(root)
    reader.read(RUN + 'candidate_AB.pt')  # byte identity only, no torch.load
    candidate = json.loads(reader.read(RUN + 'candidate_AB.receipt.json'))
    reader.read('repo/ood/issue27frontend_paired_train_model_v1.py')
    config = json.loads(reader.read(IMPL + 'execution_config.json'))
    membership = list(csv.DictReader(io.StringIO(reader.read(META + 'membership.csv').decode('utf-8-sig'))))
    require(len(membership) == len({r['uid'] for r in membership}) == 18266, 'MEMBERSHIP_COUNT')
    require(Counter(r['new_role'] for r in membership) == {'train': 15073, 'check': 3193}, 'V3_SPLIT')
    fit = json.loads(reader.read(RUN + 'postfit_predictions.json'))['AB']
    check = json.loads(reader.read(RUN + 'check_predictions.json'))['AB']
    ids = summarize_id(membership, fit, check)
    catalog = dict((line.split('  ', 1)[1], line.split('  ', 1)[0])
                   for line in reader.read(OLD + 'SHA256SUMS').decode().splitlines())
    references = []
    for name, expected in REPORT_REFERENCES.items():
        require(catalog.get(name) == expected, 'HISTORICAL_CATALOG_DRIFT: ' + name)
        path = root / OLD / name
        references.append({'path': OLD + name, 'exists': path.is_file(),
                           'bytes_from_stat': path.stat().st_size if path.is_file() else None,
                           'recorded_sha256': expected, 'payload_opened': False,
                           'payload_hash_verified': False})
    require(all(r['exists'] for r in references), 'HISTORICAL_REFERENCE_MISSING')
    require(sum(REPORT_ROLES.values()) == sum(p['targets'] for p in POOLS) == 262050, 'REPORT_CENSUS')
    tracked = getgit('diff', '--name-only', '--', 'runs/issue27by_runtime_optimized_1m_or_slurm_materialization_2026-06-12')
    unrelated = {name: sha((root / name).read_bytes()) for name in tracked.splitlines()}
    return {
        'status': 'PREOPEN_SCOPE_READY_SPECIFIC_HISTORICAL_REPORT_ACCESS_UNRESOLVED',
        'head': HEAD, 'branch': 'codex/exp-mainline', 'candidate': candidate,
        'candidate_path': RUN + 'candidate_AB.pt', 'hard_rule': 'logit >= 0',
        'primary_candidate_only': 'AB', 'training_requested': False,
        'proposed_historical_report_targets': 262050, 'proposed_pool_counts': POOLS,
        'historical_role_counts': REPORT_ROLES,
        'count_basis': 'DISCLOSED_FROZEN_CONTRACT_AND_SOURCE_CONSTANTS_NOT_NEW_ROW_CENSUS',
        'existing_id_results': ids, 'existing_id_targets': 809,
        'id_note': 'Existing fit/check evidence, not 809 fresh independent ID test targets.',
        'feature_inputs': config['feature_sources'],
        'current_f4_targets': 18266, 'current_f4_contexts': 12889,
        'historical_input_note': 'Old 768D E3 embeddings cannot be supplied to the 131D F4 GRU.',
        'expanded_f4_materialization': 'NOT_IMPLEMENTED_OR_EXECUTED',
        'report_artifacts': references,
        'proposed_reference': 'Existing P2 categorical outcomes on the exact same target UIDs; no teacher forward.',
        'exposure_audit_pending': ['target_UID', 'source_member', 'semantic_context', 'causal_prefix', 'attack_mechanism'],
        'forbidden_final': ['cooler-motor', 'seed37', 'seed_37', 'seed-37', 'seed47', 'seed_47', 'seed-47'],
        'legacy_sealed_names': '110104 sealed_final_attack and 3000 sealed_final_ood rows are explicitly in the old disclosed report. Reuse still requires specific access clarification; their names do not silently grant access.',
        'independent_confirmation': False, 'new_device_test': False,
        'wall_estimate': 'UNKNOWN_UNTIL_ALLOWED_TARGET_MEMBER_CUTOFF_CENSUS',
        'action_counts': {'historical_report_payload_files_opened': 0, 'raw_packets_decoded': 0,
                          'feature_files_decoded': 0, 'model_loads': 0, 'model_forwards': 0,
                          'optimizer_steps': 0, 'historical_experiments_rerun': 0},
        'read_ledger': reader.ledger, 'unrelated_tracked_sha256': unrelated,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=OUTPUT)
    args = parser.parse_args()
    out = (ROOT / args.out).resolve()
    require(out.is_relative_to((ROOT / 'runs').resolve()) and not out.exists(), 'NEW_RUN_DIRECTORY_REQUIRED')
    result = build(ROOT)
    out.mkdir()
    json_write(out / 'scope_readiness.json', result)
    json_write(out / 'existing_id_results.json', result['existing_id_results'])
    with (out / 'proposed_pools.csv').open('x', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(POOLS[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(POOLS)
    with (out / 'SHA256SUMS').open('x', encoding='ascii', newline='\n') as handle:
        for path in sorted(out.iterdir()):
            if path.name != 'SHA256SUMS':
                handle.write(sha(path.read_bytes()) + '  ' + path.name + '\n')
    print(json.dumps({'status': result['status'], 'existing_id_results': result['existing_id_results'],
                      'proposed_report_targets': 262050, 'action_counts': result['action_counts']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
