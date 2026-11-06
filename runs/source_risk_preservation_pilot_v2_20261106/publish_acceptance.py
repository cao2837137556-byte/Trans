"""Persist pilot acceptance and update handoff without altering frozen training."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,t):p.write_bytes(t.encode())
def main():
    acceptance=json.loads((HERE/'FINAL_PILOT_ACCEPTANCE.json').read_text());assert acceptance['scientific']=='SOURCE_PILOT_NO_GO'
    report=DOC/'collab/20261106_source_risk_preservation_pilot_acceptance_codex.md'
    write(report.with_suffix('.md.sha256'),sha(report)+'  '+report.name+'\n')
    start=DOC/'NEW_CHAT_START_HERE.md';history=DOC/'START_HERE_HISTORY.md'
    marker=b'## 2026-11-06 before source pilot final acceptance\n\n'
    assert marker not in history.read_bytes()
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+start.read_bytes())
    write(start,'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试已验收**：182579完成2:32；三种子各320更新。工程PASS、科学NO_GO，原融合790仍保留，无新作业。
2. **误报下降但加权不足**：CAL集成普通294→161条、0.8870%→0.4857%；加权0.9998%→0.9507%，相对降4.91%未达10%。剩余加权误报87.53%来自SimCam。
3. **检出/8维总体保留**：源FIT/CAL全种子及集成攻击召回100%、撤警0；CAL正向8维贡献保留101.73%—101.89%。个别样本仍下降，不能归因于几乎未激活的LC项。
4. **未通过项/下一步**：全种子攻击分数p01下降略超0.01尺度门；集成CAL有1410条超限，尚未漏报。先查源FIT高权重正常分支覆盖和攻击尾部保护，不放宽门、不自动全量或外部评价。
5. **证据/边界**：[验收报告](collab/20261106_source_risk_preservation_pilot_acceptance_codex.md)、`runs/source_risk_preservation_pilot_v2_20261106/FINAL_PILOT_ACCEPTANCE.json`；仅源域固定阈值RAW，A/B/Edge和C5新效果未知。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
''')
    lead='''## 2026-11-06：源域风险保护小试验收，改善但科学NO_GO

182579完成2:32，三种子共960更新；成功链5:35，工程PASS。CAL集成普通FPR 0.8870%→0.4857%，加权0.9998%→0.9507%（相对降4.91%，未达10%）；所有源攻击召回100%、撤警0，正向8维贡献约101.8%保留。全部种子攻击分数p01下降仍略超0.01原尺度门，不能放宽门或用召回替代；LC几乎未激活，不能宣称其因果作用。下一步只建议源FIT高权重正常覆盖与攻击尾部约束排查，不自动新训练/外部评价。无新作业，大文件留超算。见[验收报告](collab/20261106_source_risk_preservation_pilot_acceptance_codex.md)。

---

'''
    for name in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/name;p.write_bytes(lead.encode()+p.read_bytes())
    display=ROOT/'runs/device_context_training_v1_20261105/index.html';page=display.read_text()
    page=page.replace('源域小试完成，等待结果验收','小试已验收：工程通过，科学标准未全部通过')
    page=page.replace('<strong>本轮在做什么</strong>','<strong>本轮执行流程（已完成）</strong>')
    card='''<div class="card"><strong>验收结果：有改善，但还不能升级模型</strong><p>CAL普通误报294→161条（0.8870%→0.4857%）；加权误报0.9998%→0.9507%，相对降4.91%，未达到10%门。</p><p>三个种子及集成源攻击召回保持100%，未撤回攻击报警；正向8维贡献总量约保留101.8%。但攻击分数尾部仍有小幅超限，集成CAL有1,410条下降超过0.01原尺度。</p><p>小试实际2分32秒；成功链5分35秒。工程PASS、科学NO_GO。保留原融合790，无新作业；尚无A/B/Edge或C5新成绩。</p></div>
'''
    assert '验收结果：有改善' not in page
    page=page.replace('<div class="card"><strong>本轮执行流程（已完成）',card+'<div class="card"><strong>本轮执行流程（已完成）')
    write(display,page)
    names=['audit_pilot.py','publish_acceptance.py','PILOT_ACCEPTANCE_SUMMARY.json','FINAL_PILOT_ACCEPTANCE.json','PILOT_COMPLETION.json','RETRIEVAL.json','PILOT_RESULT.json','PILOT_SCHEDULER.json']
    manifest=json.loads((HERE/'ARTIFACT_SHA256.json').read_text())
    for name in list(manifest)+names:manifest[name]=sha(HERE/name)
    write(HERE/'ARTIFACT_SHA256.json',json.dumps(manifest,indent=2)+'\n')
    paths=[(HERE/n).relative_to(ROOT).as_posix() for n in names+['ARTIFACT_SHA256.json']]
    paths += [(DOC/n).relative_to(ROOT).as_posix() for n in ['NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths += [p.relative_to(ROOT).as_posix() for p in [report,report.with_suffix('.md.sha256'),display]]
    write(HERE/'.private/ACCEPTANCE_STAGE_PATHS.txt','\n'.join(paths)+'\n')
    print(json.dumps(dict(status='DOCUMENTED',files=len(paths),new_jobs=0)))
if __name__=='__main__':main()
