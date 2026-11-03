"""Freeze the one C2 scope and only the existing inputs actually needed."""
import ast
from pathlib import Path

from common import HERE, ROOT, CANDIDATE, need, read, sha, write, progress


def main():
    need(not (HERE / 'EXECUTION_ATTEMPT.json').exists(), 'CANNOT_CHANGE_CONTRACT_AFTER_ATTEMPT')
    files = {}

    def add(relative, expected=None):
        actual = sha(ROOT / relative)
        if expected is not None:
            need(actual == expected, 'PREPARATION_SHA:' + relative)
        need(relative not in files or files[relative] == actual, 'CONFLICTING_PIN')
        files[relative] = actual

    rel = HERE.relative_to(ROOT).as_posix()
    request = read(HERE / 'EXPORT_REQUEST.json')
    for item in request['files']:
        add(rel + '/retrieved/' + item['local_relative_path'], item['sha256'])
    source = read(HERE / 'retrieved/source/INPUT_SEAL.json')['inputs_sha256']
    source_inputs = ['runs/diagnostics_d1_d2_v1_20261022/assets/heads/run/prepared/' + n
                     for n in ('LEARN.jsonl.gz', 'LEARN_q.npy')]
    source_inputs += ['runs/source_controls_base_ctx_v1_20261026/config/FROZEN_INDICES.npz']
    endpoints = 'runs/source_controls_base_ctx_repair_v2_20261026/result_retrieval_20261027/evidence179460/'
    source_inputs += [endpoints + f'endpoints/{f}_BASE_{s}/evaluation.json'
                      for f in ('G0', 'G1') for s in (27, 127, 227)]
    source_inputs += [endpoints + f'ensemble_{f}_BASE.json' for f in ('G0', 'G1')]
    for path in source_inputs:
        add(path, source[path])
    c1path = 'runs/history_normal_reference_keyrepair_v1_20261031/config/ASSETS.json'
    add(c1path)
    c1 = read(ROOT / c1path)
    for name in ('cuts', 'scales'):
        item = c1['calibration'][name]
        add(item['path'], item['sha256'])
    for pool, spec in c1['pools'].items():
        for name in ('rows', 'q14', 'q_uids'):
            item = spec['query'][name]
            add(item['path'], item['sha256'])
        for name in ('baseline_decisions', 'baseline_result'):
            item = spec[name]
            add(item['path'], item['sha256'])
    old = 'runs/history_normal_reference_d2_trace_v1_20261031/retrieved/'
    pins = {r['path']: r['sha256'] for r in read(ROOT / old / 'REMOTE_TRACE_INVENTORY.json')['files']}
    for name in ('RESULT.json', 'dev/DEV_DECISIONS.npz', 'dev/QUERIES.jsonl.gz',
                 'ab/CIC_DEV/DECISIONS.npz', 'ab/UNSW_DEV/DECISIONS.npz'):
        add(old + name, pins[name])
    shared = ['repo/ood/constrained_onboarding_core_v3.py',
              'runs/history_normal_reference_keyrepair_v1_20261031/hnr/__init__.py',
              'runs/history_normal_reference_keyrepair_v1_20261031/hnr/assets.py',
              'runs/history_normal_reference_keyrepair_v1_20261031/hnr/common.py',
              'runs/history_normal_reference_keyrepair_v1_20261031/hnr/evaluation.py',
              'runs/dense_reference_ab_stage_candidate_v1_20261028/src/metrics.py',
              'runs/local_geometry_budgeted_v2_replay_repair_r1_20261029/lg/metrics.py']
    for path in shared:
        add(path)
    review = 'runs/mainline_docs/collab/20261031_history_normal_reference_d2_review_reply_codex.md'
    add(review, 'cc27fc36416b37ec57cfcd8df429af6f76fc8db28360bd0b945a744929ef597b')
    code = {}
    for name in ('common.py', 'run.py', 'guarded_run.py', 'test_c2.py', 'build_contract.py'):
        ast.parse((HERE / name).read_text('utf-8'))
        code[name] = sha(HERE / name)
    contract = dict(candidate=CANDIDATE, status='FIXED_AUTHORIZED_FOR_ONE_EXECUTION',
                    authorization='User: 应该可以动手了; implement and run the fixed C2 using seven saved arrays.',
                    scope='ALL_DEVICES_ALL_QUERY_ROLES', guard='q14[0]==1 & q14[2]==1 & q14[5]==0',
                    parameter_search=False, new_E3=0, new_distances=0, training=0, raw_decode=0,
                    frozen_lambda=.25, stages=['SOURCE_SAVED_PRECHECK', 'HIST_DEV_GATE', 'CONDITIONAL_AB_ONCE'],
                    source_role='180228 Q/N/C and historical D0 diagnostic only, no source branch revival',
                    dev_gate='each device corrected_FP < RAW_FP; pooled relative reduction >= 50%',
                    ab_primary='7200s post_window_primary; full also reported',
                    attack_protection='four heads: cumulative device<=1pp; activity/annotation<=5pp; low RAW recall zero withdrawal',
                    evidence='CONSUMED_DEVELOPMENT_ONLY', no_c3=True, no_auto_retry=True,
                    limits=dict(cpus=4, rss_bytes=4*1024**3, wall_seconds=900, output_bytes=512*1024**2),
                    input_manifest_sha256=None, code_sha256=code)
    manifest = dict(schema='c2-saved-input-pins-v1', files=files, c1_asset_spec=c1path, endpoints=endpoints)
    write(HERE / 'INPUT_MANIFEST.json', manifest)
    contract['input_manifest_sha256'] = sha(HERE / 'INPUT_MANIFEST.json')
    write(HERE / 'EXECUTION_CARD.json', contract)
    progress('READY', '实现及输入合同已冻结，等待工程检查后执行', pinned_files=len(files))
    print('CONTRACT_SHA256 ' + sha(HERE / 'EXECUTION_CARD.json'), flush=True)


if __name__ == '__main__':
    main()
