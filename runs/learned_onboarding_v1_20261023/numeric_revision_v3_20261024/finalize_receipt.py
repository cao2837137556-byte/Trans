"""Verify downloaded validation evidence and publish an accurate handoff snapshot."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

REV=Path(__file__).resolve().parent
ROOT=REV.parents[2]
EVIDENCE=REV/'remote_validation'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    manifest=read(EVIDENCE/'EVIDENCE_MANIFEST.json')
    for name,value in manifest['files'].items():
        assert sha(EVIDENCE/name)==value['sha256'],'EVIDENCE_SHA:'+name
    run=read(EVIDENCE/'VALIDATION_RECEIPT.json')
    source=read(EVIDENCE/'source_validation/SOURCE_VALIDATION.json')
    identity=read(EVIDENCE/'SOURCE_IDENTITY_SUPPLEMENT.json')
    assert run['status']=='PASS_VALIDATION_ONLY'
    assert source['status']=='PASS_SOURCE_FORWARD_ONLY_NOT_EXPERIMENT_RESTART'
    assert identity['status']=='PASS' and identity['fit_ordered_metadata_rows_matched']==617908
    assert all(g['score_bitwise_native_256_127'] and g['score_bitwise_reloaded'] for g in source['groups'])
    assert sum(g['held_rows'] for g in source['groups'])==617908
    identity_groups={g['head']:g for g in identity['groups']}
    for group in source['groups']:
        joined=identity_groups[group['head']]
        assert group['checkpoint_sha256']==joined['checkpoint_sha256']
        assert group['train_rows']==joined['train_rows'] and group['held_rows']==joined['held_rows']
    original_log=(EVIDENCE/'original_tests.log').read_text()
    numeric_log=(EVIDENCE/'numeric_tests.log').read_text()
    assert 'Ran 49 tests' in original_log and original_log.rstrip().endswith('OK')
    assert 'Ran 5 tests' in numeric_log and numeric_log.rstrip().endswith('OK')
    candidate_manifest=REV/'staging/NUMERIC_REVISION_MANIFEST.json'
    assert sha(candidate_manifest)==source['revision_manifest_sha256']
    for name,info in read(candidate_manifest)['files'].items():
        assert sha(REV/'staging'/name)==info['sha256'],'LOCAL_CANDIDATE_CHANGED:'+name
    receipt=dict(schema='paper04-numeric-repair-receipt-v3',
        status='NUMERIC_FIX_VERIFIED_SOURCE_ONLY_EXPERIMENT_STILL_STOPPED',
        recorded_at=datetime.now(timezone.utc).isoformat(),
        original_diagnosis_sha256=sha(REV/'diagnostic_evidence/DIAGNOSIS.json'),
        evidence_manifest_sha256=sha(EVIDENCE/'EVIDENCE_MANIFEST.json'),
        source_validation_sha256=sha(EVIDENCE/'source_validation/SOURCE_VALIDATION.json'),
        input_identity_supplement_sha256=sha(EVIDENCE/'SOURCE_IDENTITY_SUPPLEMENT.json'),
        candidate_manifest_sha256=sha(candidate_manifest),
        candidate_archive_sha256=sha(REV/'numeric_validation_v3.zip'),
        test_runtime=dict(python=source['runtime']['python'],torch=source['runtime']['torch']),
        remote_original_tests=49,remote_numeric_tests=5,
        real_auxiliary_heads=2,real_held_rows=617908,
        revised_native_batches_bitwise_equal=True,reloaded_checkpoint_scores_bitwise_equal=True,
        groups=source['groups'],source_forward_seconds=source['elapsed_seconds'],
        peak_source_process_tree_rss=source['peak_process_tree_rss'],
        production_optimizer_updates=0,target_queries_read=0,
        old_checkpoint_weights_preserved=True,original_experiment_resumed=False,
        scientific_results='NOT_AVAILABLE',full_H_geometry_and_pipeline='NOT_RUN',
        automatic_relaunch=False,
        next_step='Separate explicitly authorized execution with revised numeric identity; never resume or overwrite V2 silently')
    with (REV/'REPAIR_RECEIPT.json').open('x',encoding='utf-8') as stream:
        json.dump(receipt,stream,indent=2,allow_nan=False)
    note=(
        '**10月24日最新数值修复回执：** V2 的 G1 异常已独立复现：108,675 条源侧留出样本中 1 条超原容差；'
        '输入、前一 Linear/ReLU 均逐位相同，差异出在末 Linear，原 FIT 伪阈值下零判决翻转、零新增攻击漏检。'
        'V3 使用独立逐条 float32 推理，保留真正 256/127 两路径、各自尾批与原门，未改训练公式/权重或正式头路径。'
        '云端实际 Python 3.9/Torch 2.5.1 原49＋新增5项通过；两个既有辅助头共617,908条留出样本，'
        '新版256/127及独立重载分数全部逐位相等，输入SHA/原FIT索引/元数据/检查点训练UID补充核验通过。'
        '跨版本分数不宣称逐位保留，具体差分与资源以 [修复回执](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/REPAIR_RECEIPT.json)'
        '／[审查说明](../learned_onboarding_v1_20261023/numeric_revision_v3_20261024/NUMERIC_REPAIR_REVIEW.md) 为准。'
        '**本轮仅诊断、修订和前向验证，实验仍停止，未重训或自动续跑；完整源几何/H、源困难信号、三模块、CAL和A/B仍待正式执行，科学收益未知。**'
    )
    for name in ('NEW_CHAT_START_HERE.md','mainline_handoff.md','mainline_experiment_map.md'):
        path=ROOT/'runs/mainline_docs'/name
        body=path.read_text(encoding='utf-8-sig')
        body=body.replace('## 2026-10-24 最新：V2数值回放异常停止，本地页面已恢复',
                          '## 2026-10-24 历史：V2数值回放异常停止，本地页面已恢复',1)
        if name=='NEW_CHAT_START_HERE.md':
            body=body.replace('独立兼容V2后来在AUX_G1数值回放异常停止；本地进度页面已恢复，全部实验现场保留，未自动重跑。',
                              'V2数值异常已定位，V3数值修订通过源侧验证；本地页面已恢复，原实验仍停止，全部现场保留，未自动重跑。',1)
        title,remainder=body.split('\n',1)
        addition='\n'+('## 2026-10-24 最新：数值修订已验收，实验未重启\n\n' if name!='NEW_CHAT_START_HERE.md' else '')+note+'\n'
        path.write_text(title+'\n'+addition+remainder,encoding='utf-8',newline='\n')
    review=REV/'NUMERIC_REPAIR_REVIEW.md'
    with review.open('a',encoding='utf-8') as stream:
        stream.write('\n## 实际云端验证回执\n\n原49项＋新增5项测试全部通过。两个既有辅助头的617,908条留出行，256/127与独立重载均逐位相同；'
                     '输入文件SHA、FIT索引/元数据和checkpoint训练UID独立补充审计通过。未改旧checkpoint，未恢复实验。\n\n')
        for group in source['groups']:
            stream.write(f"- {group['head']}：留出{group['held_rows']}行，耗时{group['elapsed_seconds']:.2f}秒；"
                         f"相对V2（各自FIT伪阈值）源侧判决变化{group['cross_version_changed_source_decisions']}行，"
                         f"新增源攻击FN {group['cross_version_source_new_fn']}条。\n")
        stream.write(f"\n源侧前向总耗时{source['elapsed_seconds']:.2f}秒，RSS峰值{source['peak_process_tree_rss']} bytes；"
                     '逐条推理额外耗时必须纳入后续执行预算。完整H/几何与科学指标仍未验证。详见 REPAIR_RECEIPT.json。\n')
    print(json.dumps({key:receipt[key] for key in ('status','remote_original_tests','remote_numeric_tests',
        'real_auxiliary_heads','real_held_rows','source_forward_seconds','peak_source_process_tree_rss')}))


if __name__=='__main__':
    main()
