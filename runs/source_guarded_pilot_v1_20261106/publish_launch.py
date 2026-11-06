"""Seal launch evidence and source-only update-guard contract with exact allowlist."""
import ast,base64,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs';OLD=ROOT/'runs/source_stratified_pilot_v1_20261106'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_bytes(s.encode())
def js(p,v):write(p,json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def main():
    state=json.loads((HERE/'CHAIN_STATE.json').read_text());assert state['stage'] not in ['STOP','WAITING_UPLOAD'] and state['dependency_gate']['status']=='PASS'
    delivery=json.loads((HERE/'DELIVERY.json').read_text())
    for n,h in delivery['pins'].items():
        b=(HERE/n).read_bytes();assert sha(HERE/n)==h and b'\r' not in b and base64.b64decode(base64.b64encode(b))==b
        if n.endswith('.py'):ast.parse(b.decode())
    def funcs(p):return {v.name:ast.dump(v,include_attributes=False) for v in ast.parse(p.read_text()).body if isinstance(v,ast.FunctionDef)}
    old,new=funcs(OLD/'worker.py'),funcs(HERE/'worker.py')
    for n in ['load_head','zero_scores','measures','criteria','ensemble']:assert old[n]==new[n]
    for n in ['risk_core.py','sampling_core.py']:assert (OLD/n).read_bytes()==(HERE/n).read_bytes()
    regressions={}
    for n in ['LOCAL_REGRESSION','SAMPLING_REGRESSION','GUARD_REGRESSION','DEPENDENCY_REGRESSION']:
        v=json.loads((HERE/(n+'.json')).read_text());assert v['status']=='PASS';regressions[n]=len(v['tests'])
    js(HERE/'LOCAL_DELIVERY_AUDIT.json',dict(status='PASS',payloads=len(delivery['pins']),payload_sha_LF_AST_base64_verified=True,
        loss_and_sampling_byte_identical=True,metric_gate_and_scoring_AST_identical=True,local_regressions=regressions,remote_dependency_gate=state['dependency_gate']))
    js(HERE/'LAUNCH_SNAPSHOT.json',state);phases=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']
    for phase in phases:
        for kind in ['JOB','SCHEDULER']:
            value=state.get(phase+'_'+kind)
            if value:js(HERE/(phase+'_'+kind+'.json'),value)
    jobs=', '.join(state[p+'_JOB']['job_id'] for p in phases if state.get(p+'_JOB'));dep=state['dependency_gate']['files_checked']
    report=DOC/'collab/20261106_source_guarded_pilot_launch_codex.md'
    write(report,f'''结果：源域受限更新小试已封存并提交，作业{jobs}，启动快照{state['stage']}；尚未科学验收。
影响：固定分层抽样/原损失，新增每轮全FIT接受检查和四档步长回退。全部FIT参与优化反馈，不再宣称未抽中梯度样本是验证集；CAL不参与更新接受。
下一步：真实旧工程门→真实源提案/全源保护/强制拒绝恢复/预算门→固定三种子五轮提案；工程失败停止，无可行进展停止，大文件留超算。

# 2026-11-06 受限更新小试启动回执

版本`runs/source_guarded_pilot_v1_20261106`，见[执行卡](20261106_source_guarded_pilot_design_codex.md)。1CPU/8GiB，三阶段30/30/60分钟，总运行上限2小时，排队另计，无自动作业重试。

{dep}项远端依赖提交前核验PASS。本地原训练/评价10项、抽样8项、更新守卫7项、依赖4项回归PASS，载荷SHA/LF/AST/base64通过。真实Linux预检仍独立执行，不能用本地测试替代。

每种子固定五轮×64批名义提案，每轮从相同完整起点尝试lr倍率1、1/2、1/4、1/8，最多实际1280步，保留≤320步。每次失败都恢复模型、Adam矩/步数及Torch随机状态；全部失败则保留原轮起点。按源FIT原保护条件和正常尾部风险不增接受，不参考CAL。对照为封存分层小试，实际算力不同，必须分别记账。

真实训练预检各头8批名义提案，另4次强制拒绝的真实1批更新验证完整恢复；源风险确实下降、保护通过且最坏耗时≤60分钟才提交正式小试。五轮最终保留端点全报，不选轮次、种子或外部成绩。

复用用户既有SSH连接；普通程序维护[进度页](http://127.0.0.1:18806/)和回执取回。头、成员、逐行分数留超算，无新A/B/Edge/C5评价。源码与小回执按明确清单封存。
''')
    design=DOC/'collab/20261106_source_guarded_pilot_design_codex.md'
    for p in [report,design]:write(p.with_suffix('.md.sha256'),sha(p)+'  '+p.name+'\n')
    attr=DOC/'.gitattributes';rule=b'/collab/20261106_source_guarded_pilot_* -text\n'
    if rule not in attr.read_bytes():attr.write_bytes(attr.read_bytes()+rule)
    history=DOC/'START_HERE_HISTORY.md';marker=b'## 2026-11-06 before source guarded pilot\n\n';assert marker not in history.read_bytes()
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+(DOC/'NEW_CHAT_START_HERE.md').read_bytes())
    write(DOC/'NEW_CHAT_START_HERE.md',f'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **受限更新小试已提交**：作业{jobs}，快照{state['stage']}；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚无新科学结论。
2. **固定算法**：分层样本/原损失保持；每轮64批后全FIT保护验收，lr倍率1/0.5/0.25/0.125，失败恢复模型/Adam/RNG，全部拒绝则回退。三种子固定5轮保留端点。
3. **角色/成本变化**：全部FIT参与更新判断；未抽中梯度FIT不是验证集。每头名义320步、实际最多1280步、保留≤320步分别记账。CAL不决定更新，原科学门不放宽。
4. **自动门**：{dep}项远端依赖及本地29项回归PASS；真实工程→真实源提案/全源检查/强制拒绝恢复/最坏预算→小试。失败或无可行进展停止，不自动扩量或外部评价。
5. **证据/存储**：[执行卡](collab/20261106_source_guarded_pilot_design_codex.md)、[启动回执](collab/20261106_source_guarded_pilot_launch_codex.md)；前序分层小试仍NO_GO、原FUSION790保留，大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
''')
    lead=f'''## 2026-11-06：源域受限更新小试启动

作业{jobs}，启动快照{state['stage']}。固定分层样本和原损失，每轮全FIT核验原保护门及正常尾部风险不增；四档lr倍率重放，完整恢复模型/Adam/RNG，五轮保留端点全报。全部FIT参与优化反馈，未抽中梯度FIT非验证集；CAL不参与接受。每头名义320、实际≤1280、保留≤320步分别记账。{dep}项远端依赖和本地29项回归PASS，真实工程/源提案/强制恢复/预算门后自动小试，1CPU/8GiB总上限2小时。原分层NO_GO保留，无新外部成绩。见[执行卡](collab/20261106_source_guarded_pilot_design_codex.md)和[启动回执](collab/20261106_source_guarded_pilot_launch_codex.md)。

---

'''
    for n in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/n;p.write_bytes(lead.encode()+p.read_bytes())
    names=['.gitattributes','worker.py','risk_core.py','sampling_core.py','guard_core.py','guarded_training.py','test_risk.py','test_sampling.py','test_guard.py','dependency_gate.py','test_dependencies.py','build_package.py','prepare_delivery.py','receiver.py','chain_client.py','publish_launch.py','progress.html','SPEC.json','INPUT_PINS.json','LOCAL_REGRESSION.json','SAMPLING_REGRESSION.json','GUARD_REGRESSION.json','DEPENDENCY_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','LOCAL_DELIVERY_AUDIT.json','LAUNCH_SNAPSHOT.json']
    names += [p.name for p in HERE.glob('*_JOB.json')]+[p.name for p in HERE.glob('*_SCHEDULER.json')]
    js(HERE/'ARTIFACT_SHA256.json',{n:sha(HERE/n) for n in names})
    paths=[(HERE/n).relative_to(ROOT).as_posix() for n in names+['ARTIFACT_SHA256.json']]
    paths+=['runs/device_context_training_v1_20261105/index.html']
    paths+=['runs/mainline_docs/'+n for n in ['.gitattributes','NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths+=[p.relative_to(ROOT).as_posix() for p in [report,design,report.with_suffix('.md.sha256'),design.with_suffix('.md.sha256')]]
    write(HERE/'.private/STAGE_PATHS.txt','\n'.join(paths)+'\n');print(json.dumps(dict(status='SEALED',files=len(paths),jobs=jobs,stage=state['stage'])))
if __name__=='__main__':main()
