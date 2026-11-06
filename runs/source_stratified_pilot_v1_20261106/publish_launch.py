"""Seal authorized source-only sampling pilot launch and explicit Git allowlist."""
import ast,base64,hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];DOC=ROOT/'runs/mainline_docs';OLD=ROOT/'runs/source_risk_preservation_pilot_v2_20261106'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):p.write_bytes(s.encode('utf-8'))
def js(p,v):write(p,json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def main():
    state=json.loads((HERE/'CHAIN_STATE.json').read_text());assert state['stage'] not in ['STOP','WAITING_UPLOAD']
    assert state['dependency_gate']['status']=='PASS'
    delivery=json.loads((HERE/'DELIVERY.json').read_text())
    for n,h in delivery['pins'].items():
        b=(HERE/n).read_bytes();assert sha(HERE/n)==h and b'\r' not in b and base64.b64decode(base64.b64encode(b))==b
        if n.endswith('.py'):ast.parse(b.decode())
    def funcs(p):return {v.name:ast.dump(v,include_attributes=False) for v in ast.parse(p.read_text()).body if isinstance(v,ast.FunctionDef)}
    old,new=funcs(OLD/'worker.py'),funcs(HERE/'worker.py')
    for n in ['load_head','zero_scores','measures','criteria','ensemble']:assert old[n]==new[n]
    assert (OLD/'risk_core.py').read_bytes()==(HERE/'risk_core.py').read_bytes()
    regressions={}
    for n in ['LOCAL_REGRESSION','SAMPLING_REGRESSION','DEPENDENCY_REGRESSION']:
        v=json.loads((HERE/(n+'.json')).read_text());assert v['status']=='PASS';regressions[n]=len(v['tests'])
    js(HERE/'LOCAL_DELIVERY_AUDIT.json',dict(status='PASS',payloads=len(delivery['pins']),payload_sha_LF_AST_base64_verified=True,
        loss_byte_identical=True,metric_gate_and_scoring_AST_identical=True,local_regressions=regressions,remote_dependency_gate=state['dependency_gate']))
    js(HERE/'LAUNCH_SNAPSHOT.json',state)
    phases=['DECODE_PREFLIGHT','TRAIN_PREFLIGHT','PILOT']
    for phase in phases:
        for kind in ['JOB','SCHEDULER']:
            value=state.get(phase+'_'+kind)
            if value:js(HERE/(phase+'_'+kind+'.json'),value)
    jobs=', '.join(state[p+'_JOB']['job_id'] for p in phases if state.get(p+'_JOB'))
    dep=state['dependency_gate']['files_checked']
    report=DOC/'collab/20261106_source_stratified_pilot_launch_codex.md'
    write(report,f'''结果：源域分层抽样与权重校正小试已封存并启动，作业{jobs}，快照{state['stage']}；尚未完成真实预检或科学验收。
影响：每类8192个样本位、三种子各320更新；损失代数、模型起点、阈值、优化器及科学门保持，只联合修订抽样与估计器。历史均匀小试作锁定对照。
下一步：真实旧工程门→真实三种子8批训练/保存重读/源评价与预算门→固定第5轮小试，失败停止，大文件留超算。

# 2026-11-06 分层小试启动回执

版本`runs/source_stratified_pilot_v1_20261106`；[执行卡](20261106_source_stratified_pilot_design_codex.md)。1CPU/8GiB，三阶段30/30/60分钟，总上限2小时，排队另计，无自动重试。

{dep}项真实远端依赖在sbatch前核验PASS。本地原损失/训练/评价10项、估计器8项、依赖门4项回归PASS。上传载荷SHA/LF/AST/base64字节往返通过；risk_core与原小试字节相同，加载/评分/评价/门函数AST相同。这些不能替代后续真实Linux预检。

固定语义组配额，组内按原权重有放回抽样，每个样本位使用Wg/ng，避免重复加权。样本只由源FIT身份/权重定义；实际不同UID数另报，固定样本集重复5轮，采样前固定参数的期望正确不代表自适应优化过程无偏。历史对照锁定SHA，运行时核对起点/阈值/上界。

复用用户既有SSH，不启动新认证。普通程序更新[进度页](http://127.0.0.1:18806/)并取回小摘要。原始流量、模型、成员数组、逐样本分数留超算。没有A/B/Edge新候选或C5评价，不自动转全量训练。
''')
    design=DOC/'collab/20261106_source_stratified_pilot_design_codex.md'
    for p in [report,design]:write(p.with_suffix('.md.sha256'),sha(p)+'  '+p.name+'\n')
    attr=DOC/'.gitattributes';rule=b'/collab/20261106_source_stratified_pilot_* -text\n'
    if rule not in attr.read_bytes():attr.write_bytes(attr.read_bytes()+rule)
    history=DOC/'START_HERE_HISTORY.md';marker=b'## 2026-11-06 before source stratified pilot\n\n'
    assert marker not in history.read_bytes()
    history.write_bytes(history.read_bytes()+b'\n\n'+marker+(DOC/'NEW_CHAT_START_HERE.md').read_bytes())
    write(DOC/'NEW_CHAT_START_HERE.md',f'''# 当前状态

更新：2026-11-06（America/Los_Angeles）。固定五项，历史另存。

1. **分层小试已启动**：作业{jobs}，快照{state['stage']}；1CPU/8GiB，30＋30＋60分钟总上限2小时，尚未科学验收。
2. **固定改动**：源FIT按设备/活动/协议配额，组内原权重有放回抽样，样本位损失权重Wg/ng；每类8192位，独立UID另报。三种子各5轮320更新，原损失/阈值/优化器保持。
3. **科学对照/门**：复用封存均匀小试固定第5轮；起点/上界/阈值核验。保持正常误报不增、攻击尾部/召回/8维贡献保护及集成CAL加权误报相对降10%的全部原门，不选种子轮次。
4. **自动工程门**：{dep}项远端依赖PASS；本地10＋8＋4项回归PASS。真实旧工程→真实训练8批/保存重读/源评价/预算→小试；失败停止，不自动全量或外部评价。
5. **证据/边界**：[执行卡](collab/20261106_source_stratified_pilot_design_codex.md)、[启动回执](collab/20261106_source_stratified_pilot_launch_codex.md)；CAL仅开发核验，不参与选样本；大文件留超算，[进度页](http://127.0.0.1:18806/)。

[历史记录](START_HERE_HISTORY.md) · [主线交接](mainline_handoff.md) · [实验地图](mainline_experiment_map.md)
''')
    lead=f'''## 2026-11-06：源域分层抽样与权重校正小试启动

用户授权后启动独立v1，作业{jobs}、快照{state['stage']}。修订源FIT语义分层配额及组内有放回PPS抽样，使用Wg/ng损失权重；每类8192样本位、三种子各320更新，原损失/优化器/起点/阈值/科学门保持，历史均匀小试锁定对照。{dep}项远端依赖及本地22项回归通过；1CPU/8GiB三阶段预算2小时，真实工程和训练预算门通过才自动小试。大文件留超算，无新外部候选评价；当前尚无新效果结论。见[执行卡](collab/20261106_source_stratified_pilot_design_codex.md)及[启动回执](collab/20261106_source_stratified_pilot_launch_codex.md)。

---

'''
    for n in ['mainline_handoff.md','mainline_experiment_map.md']:
        p=DOC/n;p.write_bytes(lead.encode()+p.read_bytes())
    names=['.gitattributes','worker.py','risk_core.py','sampling_core.py','test_risk.py','test_sampling.py','dependency_gate.py','test_dependencies.py','build_package.py','prepare_delivery.py','receiver.py','chain_client.py','publish_launch.py','progress.html','SPEC.json','INPUT_PINS.json','LOCAL_REGRESSION.json','SAMPLING_REGRESSION.json','DEPENDENCY_REGRESSION.json','DELIVERY.json','STARTUP_RECEIPT.json','START_RECEIPT.json','LOCAL_DELIVERY_AUDIT.json','LAUNCH_SNAPSHOT.json']
    names += [p.name for p in HERE.glob('*_JOB.json')]+[p.name for p in HERE.glob('*_SCHEDULER.json')]
    js(HERE/'ARTIFACT_SHA256.json',{n:sha(HERE/n) for n in names})
    paths=[(HERE/n).relative_to(ROOT).as_posix() for n in names+['ARTIFACT_SHA256.json']]
    paths+=['runs/device_context_training_v1_20261105/index.html']
    paths+=['runs/mainline_docs/'+n for n in ['.gitattributes','NEW_CHAT_START_HERE.md','START_HERE_HISTORY.md','mainline_handoff.md','mainline_experiment_map.md']]
    paths+=[p.relative_to(ROOT).as_posix() for p in [report,design,report.with_suffix('.md.sha256'),design.with_suffix('.md.sha256')]]
    write(HERE/'.private/STAGE_PATHS.txt','\n'.join(paths)+'\n')
    print(json.dumps(dict(status='SEALED',files=len(paths),jobs=jobs,stage=state['stage'])))
if __name__=='__main__':main()
