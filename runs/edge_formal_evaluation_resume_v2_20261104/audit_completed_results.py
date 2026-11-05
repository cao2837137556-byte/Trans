"""Read-only verification of retrieved receipts and the presealed query set.

Writes only derived VERIFIED_ACCEPTANCE.json and RESULT_READOUT.json locally.
Does not load or download HPC arrays, rerun models, or change frozen science.
"""
import hashlib
import json
from pathlib import Path
import sys
import tarfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(1, str(ROOT / 'runs/edge_formal_execution_v4_20261104'))
from checkpoint import sha, require
from worker import read, selection_inputs
from formal_acceptance import validate_outputs
from runtime_control import current_status


def main():
    receipt = read(HERE / 'FINAL_ACCEPTANCE.json')
    retrieved = HERE / 'retrieved'
    manifest = read(retrieved / 'RESULT_MANIFEST.json')
    archive = HERE / '.private/results.tar'
    require(receipt['status'] == 'PASS' and receipt['acceptance_error'] is None, 'FINAL_PASS')
    require(sha(archive) == receipt['result_archive']['sha256'] and
            archive.stat().st_size == receipt['result_archive']['bytes'], 'ARCHIVE_SHA_SIZE')
    with tarfile.open(archive) as bundle:
        members = bundle.getmembers()
        require(len(members) == receipt['result_members'] + 1 and
                len(manifest['files']) == receipt['result_members'] and
                len({m.name for m in members}) == len(members), 'ARCHIVE_MEMBERS')
        require({m.name for m in members} == set(manifest['files']) | {'RESULT_MANIFEST.json'}, 'ARCHIVE_SET')
        for member in members:
            require(member.isfile(), 'REGULAR_FILES_ONLY')
            local = (retrieved / member.name).resolve()
            require(local.is_relative_to(retrieved.resolve()), 'LOCAL_MEMBER_PATH')
            digest = hashlib.sha256(bundle.extractfile(member).read()).hexdigest()
            require(sha(local) == digest, 'ARCHIVE_LOCAL_SHA:' + member.name)
            if member.name in manifest['files']:
                expected = manifest['files'][member.name]
                require(digest == expected['sha256'] and local.stat().st_size == expected['bytes'],
                        'MANIFEST_SHA_SIZE:' + member.name)
    jobout = retrieved / 'outputs/gate_182089'
    card_sha = sha(HERE / 'ENGINEERING_CARD.json')
    old_sha = sha(ROOT / 'runs/edge_formal_evaluation_v1_20261104/ENGINEERING_CARD.json')
    require(card_sha == receipt['card_sha256'], 'CARD_SHA')
    current = current_status(jobout, card_sha256=card_sha)
    require(current == receipt['attempt'] and current['status'] == 'PASS', 'AUTHORITATIVE_CURRENT')
    require(manifest['scheduler'] == receipt['scheduler'] and
            '182089|COMPLETED|0:0|' in receipt['scheduler']['stdout'], 'SCHEDULER_SUCCESS')
    preflight = read(retrieved / 'PREFLIGHT_ACCEPTANCE.json')
    require(preflight['status'] == 'PASS', 'REAL_PREFLIGHT_PASS')
    require(current_status(retrieved / 'outputs/preflight_182071', card_sha256=card_sha)['status'] == 'PASS',
            'AUTHORITATIVE_PREFLIGHT_PASS')
    checks = validate_outputs(jobout, card_sha, encoding_card_sha=old_sha)
    report = read(jobout / 'evaluation/METRICS.json')
    _, refs, selected = selection_inputs()
    expected_queries = [r['uid'] for role in ('NORMAL', 'HTTP', 'UDP') for r in selected[role]]
    require(report['ordered_query_uids'] == expected_queries, 'PRESEALED_QUERY_EXACT_ORDER')
    encoded = read(jobout / 'encoded/COMPLETE.json')
    actual_encoded = {u for b in encoded['batches'] for u in b['uids']}
    require(actual_encoded == set(expected_queries) | {r['uid'] for r in refs}, 'PRESEALED_ENCODING_EXACT_SET')
    imported = read(jobout / 'ENCODING_IMPORT.json')
    require(imported['pending_imported'] is False and imported['source_pointer_unchanged'] is True,
            'COMMITTED_IMPORT_ONLY_SOURCE_UNCHANGED')
    summary = {
        'result': '工程与完整性验收PASS；C5 p3及p1预设召回损失检查FAIL。',
        'impact': '误报大幅下降伴随HTTP攻击关联召回损失；UDP在RAW及所有方法/种子下均为0。',
        'next': '只读诊断UDP基线盲区及HTTP撤警分层；保留冻结方法和全部外部结果。',
        'job_id': '182089', 'scheduler': receipt['scheduler'],
        'sampled_resources': current['resources'],
        'encoding_rows': encoded['rows'], 'reused_encoding_rows': imported['rows'],
        'new_encoding_rows': encoded['rows'] - imported['rows'],
        'reused_committed_batches': imported['batches'],
        'metrics_sha256': checks['metrics_sha256'],
        'methods': {},
        'views': report['views'],
        'independent_attack_event_recall': report['independent_attack_event_recall'],
        'uncertainty': report['uncertainty'],
        'limitations': [
            '样本率、HT总体估计、预设安全门的层次加权损失是不同口径，不能互换。',
            '每角色20000条固定抽样；未抽样行不作为正确阴性。',
            '攻击指标为ATTACK_ASSOCIATED_RECALL，不等同独立攻击事件召回。',
            '时间区间仅为条件时间敏感性，不宣称完整抽样设计95%覆盖。',
            '本地复核覆盖取回文件和封存选择；完整数组验证采用远端回执，数组保留超算。',
            '未修改p、阈值、数据角色或外部候选选择。'],
        'hpc_output': manifest['job']['output_directory'],
    }
    for method, value in report['methods'].items():
        heads = {}
        for name, head in value['heads'].items():
            roles = {}
            for role, metric in head['roles'].items():
                require(metric['alarm_count'] + metric['no_alarm_count'] == metric['selected_rows'], 'ROLE_COUNTS')
                require(abs(metric['alarm_count'] / metric['selected_rows'] - metric['exact_selected_sample_alarm_rate']) < 1e-12,
                        'EXACT_SAMPLE_RATE')
                require(abs(metric['ht_expanded_alarm_count'] / metric['population_count'] - metric['ht_population_alarm_estimate']) < 1e-12,
                        'HT_FIXED_DENOMINATOR')
                roles[role] = {k: metric[k] for k in ('metric', 'selected_rows', 'alarm_count',
                    'exact_selected_sample_alarm_rate', 'population_count', 'ht_population_alarm_estimate',
                    'normal_component_equal_alarm_rate', 'selected_hierarchical_alarm_rate', 'strata')}
            heads[name] = dict(roles=roles, raw_cumulative_safety=head['raw_cumulative_safety'])
        summary['methods'][method] = dict(heads=heads)
    verified = dict(status='PASS', checks=checks, archive_members_verified=len(members),
        archive_sha256=sha(archive), result_manifest_sha256=sha(retrieved / 'RESULT_MANIFEST.json'),
        exact_presealed_query_order=True, exact_presealed_encoding_uid_set=True,
        authoritative_attempt_id=current['attempt_id'], preflight_status='PASS',
        local_raw_arrays_verified=False, scope='Retrieved summaries/receipts and frozen local selection; no new model execution')
    for name, value in [('VERIFIED_ACCEPTANCE.json', verified), ('RESULT_READOUT.json', summary)]:
        (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(verified, ensure_ascii=False))


if __name__ == '__main__':
    main()
