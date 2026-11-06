"""Persist the bounded launch and exact file allowlist; never stage private data."""
import ast,base64,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs'
OLD=ROOT/'runs/source_risk_preservation_pilot_v1_20261106'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_bytes(s.encode('utf-8'))
def js(p,v):write(p,json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
    state=json.loads((HERE/'CHAIN_STATE.json').read_text());assert state['stage']!='STOP'
    assert state['dependency_gate']['status']=='PASS'
    delivery=json.loads((HERE/'DELIVERY.json').read_text())
    for name,h in delivery['pins'].items():
        b=(HERE/name).read_bytes();assert sha(HERE/name)==h and base64.b64decode(base64.b64encode(b))==b
        assert b'\r' not in b,'PAYLOAD_LF_ONLY'
        if name.endswith('.py'):ast.parse(b.decode())
    assert (OLD/'SPEC.json').read_bytes()==(HERE/'SPEC.json').read_bytes()
    assert (OLD/'worker.py').read_bytes()==(HERE/'worker.py').read_bytes()
    assert (OLD/'risk_core.py').read_bytes()==(HERE/'risk_core.py').read_bytes()
    js(HERE/'LOCAL_DELIVERY_AUDIT.json',dict(status='PASS',payloads=len(delivery['pins']),base64_exact_roundtrip=True,lf_only=True,
        method_spec_and_worker_and_loss_byte_identical_to_v1=True,dependency_regression='PASS',real_remote_gate=state['dependency_gate'],
        v1_failure='182576 COMPUTE_STARTUP_FAILURE 3 seconds; no training',runtime_test_import='explicit file module; tested with parent-first sys.path'))
    js(HERE/'LAUNCH_SNAPSHOT.json',state)
    for phase in ['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']:
        for kind in ['JOB','SCHEDULER']:
            value=state.get(phase+'_'+kind)
            if value:js(HERE/(phase+'_'+kind+'.json'),value)
    jobs=', '.join(state[p+'_JOB']['job_id'] for p in ['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT'] if state.get(p+'_JOB'))
    body=f'''结果：源域风险与攻击能力保护小试已封存并启动，当前调度快照为{state['stage']}；已见作业{jobs}。
影响：45项远端依赖提交前核验通过；原v1的本地验收脚本误列依赖已修复，训练目标/worker/损失与v1字节相同。当前不是科学效果验收。
下一步：按既定三阶段自动链完成真实训练预检及源域小试；失败停止，模型/数组留超算。

# 2026-11-06 源域小试交付回执

方法见[设计卡](20261106_source_risk_preservation_pilot_design_codex.md)。运行版本为`runs/source_risk_preservation_pilot_v2_20261106`，1CPU/8GiB，三阶段30/30/60分钟。仅授权固定三种子各5轮×64批，不自动扩展全量训练或外部评价。

首版182576因远端缺少仅本地使用的`audit_completion.py`在3秒内失败，分类COMPUTE_STARTUP_FAILURE，实际优化更新0、可复用科学输出0。根因为遍历本地全部.py作为远端依赖。v1源码及回执保留；v2改为既有DELIVERY明确交付清单，并在sbatch前检查路径范围、存在性、SHA，缺失/错SHA/路径逃逸负例回归均通过。45项真实远端核验PASS已在本轮新提交前执行。

同时将本地测试的worker导入改为明确文件路径，避免父目录插在sys.path首位时误导入同名父worker；已模拟该入口顺序通过测试。它不改训练实现。

本地10项科学/数值/实际优化/评价回归和4项依赖门回归通过；上传负载LF、AST、base64字节往返与SHA通过。它们不能替代后续真实Linux结果。分数复现/有效梯度/实际参数更新/保存重读/源评价与预算门由TRAIN_PREFLIGHT真实执行。

用户既有连接已复用，无新认证。右侧进度页http://127.0.0.1:18806/由普通程序更新，源码和小回执进Git，头、逐样本数组和逐轮检查点留超算。
'''
    report=DOC/'collab/20261106_source_risk_preservation_pilot_launch_codex.md';write(report,body)
    design=DOC/'collab/20261106_source_risk_preservation_pilot_design_codex.md'
    for p in [report,design]:write(p.with_suffix(p.suffix+'.sha256'),sha(p)+'  '+p.name+'\n')
    attr=DOC/'.gitattributes';rule=b'/collab/20261106_source_risk_preservation_* -text\n'
    if rule not in attr.read_bytes():attr.write_bytes(attr.read_bytes()+rule)
    oldstart=(DOC/'NEW_CHAT_START_HERE.md').read_bytes();history=DOC/'START_HERE_HISTORY.md'
    marker=b'## 2026-11-06 before source risk preservation pilot\n\n'
    assert marker not in history.read_bytes(),'DO_NOT_DUPLICATE_HISTORY'
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+oldstart)
    start=f'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **源域小试已启动**：v2；作业{jobs}，当前{state['stage']}。1CPU/8GiB，三阶段总预算2小时；尚未科学验收。
2. **固定方法**：原融合790起步，正常高分尾部风险＋攻击分数单侧保护＋正向8维贡献保护；冻结编码器、归一化及原阈值。每种子16,384行、5轮/320更新，27/127/227全报。
3. **自动门**：真实编码距离评价→三种子各8批训练/保存重读/源评价/预算→固定小试。45项远端依赖提交前PASS；失败停止，不自动全量训练或外部评价。
4. **失败与修复**：v1作业182576在3秒内因误列本地验收脚本失败，训练0。v2使用已交付依赖清单并提前核验；方法与worker字节不变，负例回归PASS。
5. **证据/存储**：[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)、[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)，`runs/source_risk_preservation_pilot_v2_20261106`；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
'''
    write(DOC/'NEW_CHAT_START_HERE.md',start)
    lead=f'''## 2026-11-06：源域正常风险与攻击能力保护小试启动

原融合790起步；固定正常尾部单侧风险＋攻击分数/正向8维贡献保护，源FIT每类8192行、三种子各5轮320更新。原阈值/编码器/归一化冻结，无外部候选评价。v1作业182576误列本地审计依赖，3秒失败、训练0；v2方法字节不变，45项远端依赖提交前PASS，当前作业{jobs}、{state['stage']}。自动真实工程→真实训练预算门→源小试，1CPU/8GiB总上限2小时；不自动全量训练，尚无科学结论。见[设计卡](collab/20261106_source_risk_preservation_pilot_design_codex.md)及[启动回执](collab/20261106_source_risk_preservation_pilot_launch_codex.md)。

---

'''
    for n in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/n;p.write_bytes(lead.encode()+p.read_bytes())
    ledger=DOC/'hpc_failure_ledger_and_launch_gate_20260725.md'
    failure='''## 2026-11-06 SOURCE_RISK_PILOT_V1：本地审计脚本误列运行依赖

- 作业182576，DECODE_PREFLIGHT，COMPUTE_STARTUP_FAILURE，FAILED/1:0，3秒；训练更新0，无可复用科学产物。调度MaxRSS仅1032KiB，启动采样不足，不能作为模型内存占用。
- 根因：本地glob全部.py把仅本地audit_completion.py等误列为远端必备；运行入口校验正确拒绝。
- 永久门：依赖来自已封存DELIVERY显式清单，提交前逐项路径范围/存在性/SHA校验；缺文件、错SHA、路径逃逸负例必须拒绝。45项真实远端核验已通过。
- 独立v2：source_risk_preservation_pilot_v2_20261106；SPEC/worker/risk_core字节不变，测试导入采用显式路径防止同名父worker遮蔽；源域小试目标/数据/步数不变。
- 旧失败原目录/回执保留；需要重新执行真实工程门，不能沿用本次未执行结果。

---

'''
    ledger.write_bytes(failure.encode()+ledger.read_bytes())
    lists={
        OLD:['.gitattributes','worker.py','risk_core.py','test_risk.py','build_package.py','prepare_delivery.py','receiver.py','chain_client.py','progress.html','SPEC.json','INPUT_PINS.json','LOCAL_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','DECODE_PREFLIGHT_JOB.json','DECODE_PREFLIGHT_SCHEDULER.json','DECODE_PREFLIGHT_STOP.json','FAILURE_ACCEPTANCE.json'],
        HERE:['.gitattributes','worker.py','risk_core.py','test_risk.py','dependency_gate.py','test_dependencies.py','build_package.py','prepare_delivery.py','receiver.py','chain_client.py','publish_launch.py','progress.html','SPEC.json','INPUT_PINS.json','LOCAL_REGRESSION.json','DEPENDENCY_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','FAILURE_PARENT.json','LOCAL_DELIVERY_AUDIT.json','LAUNCH_SNAPSHOT.json']}
    paths=[]
    for folder,names in lists.items():
        names += [p.name for p in folder.glob('*_JOB.json') if p.name not in names]
        names += [p.name for p in folder.glob('*_SCHEDULER.json') if p.name not in names]
        for n in names:assert (folder/n).is_file(),n
        manifest={n:sha(folder/n) for n in names};js(folder/'ARTIFACT_SHA256.json',manifest)
        paths += [str((folder/n).relative_to(ROOT)).replace('\\','/') for n in names+['ARTIFACT_SHA256.json']]
    paths += ['runs/device_context_training_v1_20261105/index.html']
    paths += ['runs/mainline_docs/'+n for n in ['.gitattributes','NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md','hpc_failure_ledger_and_launch_gate_20260725.md']]
    paths += [p.relative_to(ROOT).as_posix() for p in [report,design,report.with_suffix('.md.sha256'),design.with_suffix('.md.sha256')]]
    write(HERE/'.private/STAGE_PATHS.txt','\n'.join(paths)+'\n')
    print(json.dumps(dict(status='SEALED',files=len(paths),jobs=jobs,state=state['stage'])))
if __name__=='__main__':main()
