"""Seal the read-only audit launch, preserving raw previous handoff bytes."""
import ast,base64,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_bytes(s.encode('utf-8'))
def js(p,v):write(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    state=json.loads((HERE/'CHAIN_STATE.json').read_text())
    assert state['stage']!='STOP' and state['dependency_gate']['status']=='PASS'
    delivery=json.loads((HERE/'DELIVERY.json').read_text())
    for n,h in delivery['pins'].items():
        b=(HERE/n).read_bytes();assert sha(HERE/n)==h
        assert base64.b64decode(base64.b64encode(b))==b and b'\r' not in b
        if n.endswith('.py'):ast.parse(b.decode())
    js(HERE/'LOCAL_DELIVERY_AUDIT.json',dict(status='PASS',payloads=len(delivery['pins']),lf_only=True,base64_exact=True,
        local_coverage_checks=6,dependency_regression_checks=4,remote_dependency_gate=state['dependency_gate'],
        optimizer_updates=0,external_candidate_scoring=False))
    js(HERE/'LAUNCH_SNAPSHOT.json',state)
    for phase in ['PREFLIGHT','COVERAGE']:
        for kind in ['JOB','SCHEDULER']:
            v=state.get(phase+'_'+kind)
            if v:js(HERE/(phase+'_'+kind+'.json'),v)
    jobs=', '.join(state[p+'_JOB']['job_id'] for p in ['PREFLIGHT','COVERAGE'] if state.get(p+'_JOB'))
    body=f'''结果：源FIT覆盖与攻击分数尾部只读诊断已封存并提交；作业{jobs}，启动快照{state['stage']}。
影响：52项远端依赖提交前核验PASS；本轮无参数更新、阈值重拟合或新外部候选评价。尚未完成诊断解释。
下一步：真实旧工程回放与源结果预检通过后自动完整诊断；失败停止，汇总取回，详细数组留超算。

# 2026-11-06 源域覆盖诊断启动回执

版本`runs/source_coverage_audit_v1_20261106`，方法见[设计卡](20261106_source_coverage_audit_design_codex.md)。1CPU/8GiB，PREFLIGHT 30分钟、COVERAGE 60分钟，总运行预算90分钟，排队另计；无自动重试。完整阶段只在真实预检和耗时预算门通过后提交。

读取已封存原模型与小试第5轮分数、身份、权重和回执，复核SHA、计数及分数变化。三种子27/127/227及固定集成全部报告。比较实际每类8192行、同样本数按源层级权重抽样、均匀每类16384行，全部仅由FIT构造成员。CAL仅描述性关联源域语义支持，不用于挑训练样本。覆盖改善不是训练效果证明。

本地6项覆盖/数值/确定性回归、4项依赖门回归已通过；上传载荷LF/AST/base64往返/SHA检查通过。它们不能替代真实Linux预检。只读输出分数导数不是神经网络参数梯度，不据此宣称梯度冲突因果。

复用用户既有SSH连接。普通程序负责上传、门控提交、进度更新和小回执取回；[进度页](http://127.0.0.1:18806/)沿用原入口。完整分组表、成员数组及原模型留超算，仅小摘要和SHA进Git。结果验收后再决定改采样、扩大FIT用量或修订保护约束，不自动进入新训练。
'''
    report=DOC/'collab/20261106_source_coverage_audit_launch_codex.md';write(report,body)
    design=DOC/'collab/20261106_source_coverage_audit_design_codex.md'
    for p in [report,design]:write(p.with_suffix('.md.sha256'),sha(p)+'  '+p.name+'\n')
    attr=DOC/'.gitattributes';rule=b'/collab/20261106_source_coverage_audit_* -text\n'
    if rule not in attr.read_bytes():attr.write_bytes(attr.read_bytes()+rule)
    history=DOC/'START_HERE_HISTORY.md';marker=b'## 2026-11-06 before source coverage audit\n\n'
    assert marker not in history.read_bytes(),'DO_NOT_DUPLICATE_HISTORY'
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+(DOC/'NEW_CHAT_START_HERE.md').read_bytes())
    write(DOC/'NEW_CHAT_START_HERE.md',f'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **覆盖诊断已提交**：v1，作业{jobs}，启动快照{state['stage']}；1CPU/8GiB，预检30＋完整60分钟。尚未完成解释验收。
2. **回答的问题**：源FIT缺语义支持、实际小试遗漏/低覆盖，还是已覆盖仍有误报与攻击分数下降；先查原因，再改训练。
3. **固定对照/边界**：原每类8192行、同样本数层级加权抽样、均匀每类16384行；只由FIT构造成员。三种子及集成全报；训练更新0，CAL仅描述，不做新外部评价。
4. **前序小试结论**：源攻击召回100%、8维总体贡献保留；CAL加权误报仅相对降4.91%，攻击p01下降略超门，科学NO_GO。原融合790仍保留。
5. **证据/执行**：[设计卡](collab/20261106_source_coverage_audit_design_codex.md)、[启动回执](collab/20261106_source_coverage_audit_launch_codex.md)；52项远端依赖PASS，真实预检通过后自动诊断、失败停止。大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
''')
    lead=f'''## 2026-11-06：源FIT覆盖与攻击尾部只读诊断启动

源小试科学NO_GO后，用户授权先查覆盖。v1作业{jobs}、启动快照{state['stage']}；52项远端依赖提交前PASS，1CPU/8GiB总预算90分钟，真实工程/源结果预检通过才自动完整诊断。三种子及集成、实际抽样/等量层级抽样/两倍均匀抽样；成员仅由FIT构造，CAL描述性关联，模型更新0、阈值重拟合0、新外部候选评价0。完整分组明细留超算，当前无最终诊断结论。见[设计卡](collab/20261106_source_coverage_audit_design_codex.md)和[启动回执](collab/20261106_source_coverage_audit_launch_codex.md)。

---

'''
    for n in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/n;p.write_bytes(lead.encode()+p.read_bytes())
    names=['.gitattributes','worker.py','coverage_core.py','test_coverage.py','dependency_gate.py','test_dependencies.py','build_package.py','prepare_delivery.py','receiver.py','chain_client.py','publish_launch.py','progress.html','SPEC.json','INPUT_PINS.json','LOCAL_REGRESSION.json','DEPENDENCY_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','LOCAL_DELIVERY_AUDIT.json','LAUNCH_SNAPSHOT.json']
    names += [p.name for p in HERE.glob('*_JOB.json')]+[p.name for p in HERE.glob('*_SCHEDULER.json')]
    js(HERE/'ARTIFACT_SHA256.json',{n:sha(HERE/n) for n in names})
    paths=[(HERE/n).relative_to(ROOT).as_posix() for n in names+['ARTIFACT_SHA256.json']]
    paths+=['runs/device_context_training_v1_20261105/index.html']
    paths+=['runs/mainline_docs/'+n for n in ['.gitattributes','NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths+=[p.relative_to(ROOT).as_posix() for p in [report,design,report.with_suffix('.md.sha256'),design.with_suffix('.md.sha256')]]
    write(HERE/'.private/STAGE_PATHS.txt','\n'.join(paths)+'\n')
    print(json.dumps(dict(status='SEALED',files=len(paths),jobs=jobs,stage=state['stage'])))
if __name__=='__main__':main()
