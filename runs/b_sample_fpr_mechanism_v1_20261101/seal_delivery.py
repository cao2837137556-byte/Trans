"""Seal completed diagnosis and explicitly partial C4 engineering delivery."""
import audit as a
from pathlib import Path
import json

root=a.ROOT
c4=root/'runs/history_sample_coverage_c4_v1_20261101'
e=a.read(a.HERE/'EVIDENCE.json')
t=a.read(a.HERE/'TRACE_SUMMARY_RECOVERED.json')
raw=a.read(a.HERE/'NETATMO_RAW_ACCEPTANCE.json')
chron=a.read(a.HERE/'NETATMO_CHRONOLOGY_AND_ROLE_PROPOSAL.json')
for path,digest in e['input_sha256'].items():assert a.sha(path)==digest,path
for mapping in (t['input_sha256'],t['asset_input_sha256']):
    for path,digest in mapping.items():assert a.sha(path)==digest,path
assert a.sha(a.HERE/'NETATMO_NEIGHBORS.jsonl.gz')==t['trace_sha256']
assert a.sha(a.HERE/'NetatmoWelcome_70ee50183443.raw_stats.json')==raw['statistics_sha256']
for key in ('packet_index','chronological_order'):
    assert a.sha(chron['index_receipt'][key])==chron['index_receipt'][key+'_sha256']
base=root/'runs/history_normal_reference_c3_progress_repair_v1_20261101/output/RESULT.json'
assert a.sha(base)=='cbedc30311604b0f168a967619982054249568299321e1985cf6fd054f276f8c'
assert e['required_repairs_without_new_fp']==7006 and e['optimistic_support_one_remaining_fp']==844
config=a.read(root/'runs/history_normal_reference_keyrepair_v1_20261031/config/EXECUTION.json')
admitted={d['device']:dict(raw_sha256=d['raw']['sha256'],raw_path=d['raw']['path'],owner=d['owner'],
    reference_end_us=d['reference_end_us'],bank_end_frame=d['bank_end_frame']) for d in config['devices']}
admitted['unsw-attack-traces-2018:70:ee:50:18:34:43']=dict(raw_sha256=raw['member']['sha256'],
    raw_path=raw['member']['path'],owner=raw['member']['owner_MAC'],
    reference_end_us=chron['role_proposal']['reference_end_us'],bank_end_frame=chron['role_proposal']['bank_end_frame'])
status=dict(status='SELECTOR_IMPLEMENTED_RAW_READY_FULL_RUNNER_PENDING',candidate='C4_HISTORY_SAMPLE_COVERAGE_TOPUP',
    source_inputs_for_integration=admitted,cap_per_device_protocol=4096,maximum_new_references=32768,
    tests=dict(passed=8,command='python -X utf8 -B -m unittest -v test_selection',data='synthetic only'),
    code_sha256={p.name:a.sha(p) for p in (c4/'selection.py',c4/'test_selection.py')},
    complete_runner=False,new_model_forwards=0,new_AB_evaluations=0,remote_submissions=0,
    remaining=['Integrate complete legal endpoint census with disk-backed global UID/origin uniqueness.',
        'Create selected snapshots and encode new references plus Netatmo historical DEV with frozen HPC runtime.',
        'Integrate historical DEV comparison, immutable C3 union, full A/B and stricter B attack gate.',
        'Calculate exact resource budget and validate full runner before submission.'])
with (c4/'IMPLEMENTATION_STATUS.json').open('x',encoding='utf-8') as f:json.dump(status,f,ensure_ascii=False,indent=2)
doc=root/'runs/mainline_docs/collab/20261101_b_sample_fpr_reopened_diagnosis_and_c4_codex.md'
doc.with_name(doc.name+'.sha256').write_text(a.sha(doc)+'  '+doc.name+'\n',encoding='utf-8')
files=[p for p in a.HERE.iterdir() if p.is_file() and p.name!='DELIVERY_SHA256.json']
files += [p for p in c4.iterdir() if p.is_file()]
files += [doc,doc.with_name(doc.name+'.sha256')]
a.write('DELIVERY_SHA256.json',dict(status='PASS_COMPLETED_DIAGNOSTIC_DELIVERY',
    c3_result_unchanged=True,full_C4_runner_pending=True,files={str(p.relative_to(root)):a.sha(p) for p in files},
    preserved_incomplete_artifact='TRACE_SUMMARY.json is an intentionally preserved failed serialization; use TRACE_SUMMARY_RECOVERED.json.',
    new_distance_pairs=437734,new_feature_rows=0,new_experiments=0,new_downloads=0))
pointer='**2026-11-01 用户已重新开启逐样本误报开发：** [B 逐样本误报诊断、材料核验与 C4 实现进展](collab/20261101_b_sample_fpr_reopened_diagnosis_and_c4_codex.md)。B 主视图 8494/74444=11.409919%，1.750526% 是另一加权口径，不能替代。到池级 2% 至少还需修复 7006 条。Netatmo/Samsung/Power 贡献 98.28% 残留；本轮完成保存数组审计、320 条 Netatmo 邻居重放和已下载 Netatmo 历史包/稳定时序核验。C4 固定选择器已实现、8 项合成检查通过，完整 runner 尚待接通，未编码/补库/新 A/B/提交超算。用户新指令取代下方“不再开发”的当前行动限制，C3 封存结果仍保留为历史基准；A/B 仍为消费过的开发数据。\n\n'
for name in ('NEW_CHAT_START_HERE.md','CURRENT_PROBLEM_BRIEF_20261025.md'):
    path=root/'runs/mainline_docs'/name
    before=path.read_bytes();text=before.decode('utf-8-sig')
    assert pointer not in text
    heading,rest=text.split('\n',1)
    assert path.read_bytes()==before,'CONCURRENT_DOCUMENT_EDIT'
    path.write_text(heading+'\n\n'+pointer+rest.lstrip('\r\n'),encoding='utf-8')
print(json.dumps(dict(status='DELIVERY_SEALED',diagnostic_files=len(files),doc_sha256=a.sha(doc)),ensure_ascii=False))
